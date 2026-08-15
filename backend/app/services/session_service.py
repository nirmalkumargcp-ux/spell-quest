"""The learning loop: start a session, serve the next question, take an answer.

This is where the spec's most important rule is enforced — the backend decides
what comes next; the frontend only renders it (spec §31, §51).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adaptive.config import CONFIG
from app.adaptive.evaluation import evaluate_answer
from app.adaptive.learner_model import LearnerModel
from app.adaptive.question_selector import QuestionSelector, SelectionContext, _dimension_for
from app.config import get_settings
from app.models import (
    Child, ChildMilestone, Concept, LearningSession, Milestone, MilestoneKind, Question,
    QuestionAttempt, Reward, SessionStatus, SessionType, Subject,
)
from app.models.learner import Dimension, LearnerSubjectState, MasteryStatus
from app.services.events import emit

settings = get_settings()


@dataclass
class NextQuestion:
    question: Question
    dimension: Dimension
    attempt: QuestionAttempt
    selection_reason: dict[str, float]
    session_progress: float
    continue_session: bool


@dataclass
class AnswerOutcome:
    attempt: QuestionAttempt
    is_correct: bool
    expected: str | None
    explanation: str | None
    mastery_before: float
    mastery_after: float
    status: MasteryStatus
    concept_mastered: bool
    milestones: list[Milestone]
    continue_session: bool


class SessionService:
    def __init__(self, db: Session, seed: int | None = None):
        self.db = db
        self.learner = LearnerModel(db)
        self.seed = seed if seed is not None else settings.adaptive_seed

    # ------------------------------------------------------------------ #
    def start_session(
        self, child: Child, subject: Subject, session_type: SessionType | None = None
    ) -> LearningSession:
        subject_state = self.learner.get_or_create_subject_state(child.id, subject.id)

        if session_type is None:
            # A child who has never been assessed gets the short diagnostic first.
            session_type = (
                SessionType.practice if subject_state.diagnostic_completed else SessionType.diagnostic
            )

        planned = (
            CONFIG.diagnostic.question_count
            if session_type is SessionType.diagnostic
            else CONFIG.session.default_questions
        )

        session = LearningSession(
            child_id=child.id,
            subject_id=subject.id,
            session_type=session_type,
            status=SessionStatus.active,
            started_at=datetime.now(timezone.utc),
            planned_questions=planned,
        )
        self.db.add(session)
        self.db.flush()

        child.last_active_at = datetime.now(timezone.utc)
        emit(self.db, "session_started", child_id=child.id, session_id=session.id,
             session_type=session_type.value, planned=planned)
        return session

    # ------------------------------------------------------------------ #
    def next_question(self, session: LearningSession) -> NextQuestion | None:
        if session.status is not SessionStatus.active:
            return None
        if session.questions_presented >= CONFIG.session.max_questions:
            return None

        # Query directly rather than via session.attempts: the relationship is
        # cached from the first access and would not show attempts added since,
        # which made the selector re-offer questions already asked.
        attempts = list(
            self.db.scalars(
                select(QuestionAttempt)
                .where(QuestionAttempt.session_id == session.id)
                .order_by(QuestionAttempt.started_at)
            ).all()
        )
        asked_ids = [a.question_id for a in attempts]

        questions = self.db.scalars(
            select(Question)
            .options(selectinload(Question.options))
            .where(
                Question.subject_id == session.subject_id,
                Question.active.is_(True),
            )
        ).all()

        ctx = SelectionContext(
            ability_by_skill=self.learner.ability_by_skill(session.child_id),
            states=self.learner.concept_states(session.child_id),
            recent_question_ids=asked_ids,
            recent_types=[str(self.db.get(Question, a.question_id).question_type) for a in attempts[-3:]],
            recent_concept_ids=[a.concept_id for a in attempts if a.concept_id],
            recent_dimensions=[Dimension(a.dimension) for a in attempts[-2:] if a.dimension],
            unmet_prerequisites=self.learner.unmet_prerequisites(session.child_id, session.subject_id),
        )
        if session.session_type is SessionType.diagnostic:
            ctx.prefer_dimension, ctx.ability_override = self._diagnostic_step(session, attempts)

        selector = QuestionSelector(seed=self._question_seed(session))
        candidate = selector.select(list(questions), ctx)
        if candidate is None:
            return None

        question = candidate.question
        dimension = candidate.dimension or _dimension_for(question)
        state = ctx.states.get((question.concept_id, dimension))

        attempt = QuestionAttempt(
            session_id=session.id,
            child_id=session.child_id,
            question_id=question.id,
            concept_id=question.concept_id,
            skill_id=question.skill_id,
            dimension=dimension,
            started_at=datetime.now(timezone.utc),
            attempt_number=sum(1 for a in attempts if a.question_id == question.id) + 1,
            difficulty_at_attempt=question.effective_difficulty,
            mastery_before=state.mastery_score if state else 0.0,
            selection_reason=candidate.reason | {"source": candidate.source.value},
        )
        self.db.add(attempt)
        session.questions_presented += 1
        self.db.flush()

        emit(self.db, "question_presented", child_id=session.child_id, session_id=session.id,
             question_id=str(question.id), source=candidate.source.value,
             difficulty=question.effective_difficulty)

        return NextQuestion(
            question=question,
            dimension=dimension,
            attempt=attempt,
            selection_reason=attempt.selection_reason,
            session_progress=min(1.0, session.questions_presented / max(1, session.planned_questions)),
            continue_session=True,
        )

    # ------------------------------------------------------------------ #
    def submit_answer(
        self,
        session: LearningSession,
        attempt: QuestionAttempt,
        raw_answer: Any,
        *,
        response_time_ms: int | None = None,
        hint_used: bool = False,
        hint_level: int = 0,
    ) -> AnswerOutcome:
        question = self.db.get(Question, attempt.question_id)
        result = evaluate_answer(question, raw_answer)

        now = datetime.now(timezone.utc)
        if response_time_ms is None and attempt.started_at:
            started = attempt.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            response_time_ms = int((now - started).total_seconds() * 1000)

        dimension = Dimension(attempt.dimension) if attempt.dimension else _dimension_for(question)

        before, after, status = self.learner.record_answer(
            child_id=session.child_id,
            question=question,
            dimension=dimension,
            correct=result.is_correct,
            response_time_ms=response_time_ms,
            hint_used=hint_used,
            now=now,
        )

        # The attempt row is written once and never revised (spec §25).
        attempt.answered_at = now
        attempt.raw_answer = str(raw_answer)
        attempt.normalized_answer = result.normalized_answer
        attempt.is_correct = result.is_correct
        attempt.response_time_ms = response_time_ms
        attempt.hint_used = hint_used
        attempt.hint_level = hint_level
        attempt.mastery_after = after
        attempt.evaluation = result.detail

        if result.is_correct:
            session.questions_correct += 1

        subject_state = self.learner.refresh_subject_state(session.child_id, session.subject_id)

        concept_mastered = (
            status is MasteryStatus.mastered and before < CONFIG.mastery.mastered <= after
        )
        if concept_mastered:
            concept = self.db.get(Concept, question.concept_id)
            self.db.add(Reward(
                child_id=session.child_id, session_id=session.id,
                kind="concept_mastered", label=f"Collected “{concept.name}”",
                payload={"concept": concept.name, "image": (concept.media or {}).get("image")},
            ))
            emit(self.db, "concept_mastered", child_id=session.child_id, session_id=session.id,
                 concept=concept.name)

        milestones = self._check_milestones(session, subject_state)

        emit(self.db, "question_answered", child_id=session.child_id, session_id=session.id,
             question_id=str(question.id), correct=result.is_correct,
             mastery_before=round(before, 4), mastery_after=round(after, 4))

        self.db.flush()
        return AnswerOutcome(
            attempt=attempt,
            is_correct=result.is_correct,
            expected=result.expected,
            explanation=question.explanation,
            mastery_before=before,
            mastery_after=after,
            status=status,
            concept_mastered=concept_mastered,
            milestones=milestones,
            continue_session=self._should_continue(session),
        )

    # ------------------------------------------------------------------ #
    def complete_session(self, session: LearningSession) -> LearningSession:
        session.status = SessionStatus.completed
        session.completed_at = datetime.now(timezone.utc)

        if session.session_type is SessionType.diagnostic:
            state = self.learner.get_or_create_subject_state(session.child_id, session.subject_id)
            state.diagnostic_completed = True

        self.learner.refresh_subject_state(session.child_id, session.subject_id)
        emit(self.db, "session_completed", child_id=session.child_id, session_id=session.id,
             presented=session.questions_presented, correct=session.questions_correct)
        self.db.flush()
        return session

    # ------------------------------------------------------------------ #
    def _should_continue(self, session: LearningSession) -> bool:
        """Sessions end on a natural boundary, not a fixed counter (spec §24)."""
        if session.questions_presented >= CONFIG.session.max_questions:
            return False
        return session.questions_presented < session.planned_questions

    def _diagnostic_step(
        self, session: LearningSession, attempts: list[QuestionAttempt]
    ) -> tuple[Dimension, float]:
        """Walk the four dimensions in turn, easy first, stepping with performance.

        Recognition is asked before spelling so a young child meets something
        answerable first, and every dimension gets sampled — that is what makes
        "strong meaning, weak spelling" visible (spec §20, §22).
        """
        order = [Dimension.recognition, Dimension.meaning, Dimension.context, Dimension.spelling]
        dimension = order[session.questions_presented % len(order)]

        cfg = CONFIG.diagnostic
        ability = cfg.start_difficulty
        # Only answers on this dimension inform this dimension's ramp.
        for a in attempts:
            if a.dimension and Dimension(a.dimension) is dimension and a.is_correct is not None:
                ability += cfg.step_up if a.is_correct else -cfg.step_down
        return dimension, max(0.05, min(0.95, ability))

    def _question_seed(self, session: LearningSession) -> int | None:
        """Deterministic per (session, position) when a seed is configured."""
        if self.seed is None:
            return None
        return self.seed + session.questions_presented + (session.id.int % 1000)

    def _check_milestones(
        self, session: LearningSession, subject_state: LearnerSubjectState
    ) -> list[Milestone]:
        achieved: list[Milestone] = []
        milestones = self.db.scalars(
            select(Milestone).where(Milestone.subject_id == session.subject_id)
        ).all()
        already = {
            cm.milestone_id
            for cm in self.db.scalars(
                select(ChildMilestone).where(ChildMilestone.child_id == session.child_id)
            ).all()
        }
        for milestone in milestones:
            if milestone.id in already:
                continue
            value = {
                MilestoneKind.concepts_mastered: subject_state.concepts_mastered,
                MilestoneKind.vocabulary_estimate: subject_state.vocabulary_estimate or 0,
            }.get(MilestoneKind(milestone.kind))
            if value is not None and value >= milestone.threshold:
                self.db.add(ChildMilestone(
                    child_id=session.child_id, milestone_id=milestone.id,
                    achieved_at=datetime.now(timezone.utc),
                ))
                self.db.add(Reward(
                    child_id=session.child_id, session_id=session.id,
                    kind="milestone", label=milestone.name,
                    payload={"milestone": milestone.slug, "icon": milestone.icon},
                ))
                emit(self.db, "milestone_reached", child_id=session.child_id,
                     session_id=session.id, milestone=milestone.slug)
                achieved.append(milestone)
        return achieved
