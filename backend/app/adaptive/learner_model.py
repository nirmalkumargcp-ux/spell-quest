"""Reading and updating learner state — the service layer over the model.

This module is the only place that writes LearnerConceptState /
LearnerSkillState / LearnerSubjectState, so the update rules live in one place.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adaptive.config import CONFIG
from app.adaptive.difficulty import update_ability
from app.adaptive.mastery import Evidence, MasteryEngine, RuleBasedMasteryEngine, decay_for_absence
from app.adaptive.progression import estimate_vocabulary
from app.adaptive.spaced_repetition import SpacedRepetitionScheduler
from app.models.content import Concept, Question, Skill
from app.models.learner import (
    Dimension, LearnerConceptState, LearnerSkillState, LearnerSubjectState, MasteryStatus,
)


class LearnerModel:
    def __init__(
        self,
        db: Session,
        engine: MasteryEngine | None = None,
        scheduler: SpacedRepetitionScheduler | None = None,
    ):
        self.db = db
        self.engine = engine or RuleBasedMasteryEngine()
        self.scheduler = scheduler or SpacedRepetitionScheduler()

    # ------------------------------------------------------------------ #
    # reads
    # ------------------------------------------------------------------ #
    def concept_states(self, child_id: uuid.UUID) -> dict[tuple[uuid.UUID, Dimension], LearnerConceptState]:
        rows = self.db.scalars(
            select(LearnerConceptState).where(LearnerConceptState.child_id == child_id)
        ).all()
        return {(r.concept_id, Dimension(r.dimension)): r for r in rows}

    def ability_by_skill(self, child_id: uuid.UUID) -> dict[uuid.UUID, float]:
        rows = self.db.scalars(
            select(LearnerSkillState).where(LearnerSkillState.child_id == child_id)
        ).all()
        return {r.skill_id: r.ability for r in rows}

    def get_or_create_concept_state(
        self, child_id: uuid.UUID, concept_id: uuid.UUID, dimension: Dimension
    ) -> LearnerConceptState:
        state = self.db.scalar(
            select(LearnerConceptState).where(
                LearnerConceptState.child_id == child_id,
                LearnerConceptState.concept_id == concept_id,
                LearnerConceptState.dimension == dimension,
            )
        )
        if state is None:
            state = LearnerConceptState(
                child_id=child_id, concept_id=concept_id, dimension=dimension
            )
            self.db.add(state)
            self.db.flush()
        return state

    def get_or_create_skill_state(self, child_id: uuid.UUID, skill_id: uuid.UUID) -> LearnerSkillState:
        state = self.db.scalar(
            select(LearnerSkillState).where(
                LearnerSkillState.child_id == child_id, LearnerSkillState.skill_id == skill_id
            )
        )
        if state is None:
            state = LearnerSkillState(child_id=child_id, skill_id=skill_id)
            self.db.add(state)
            self.db.flush()
        return state

    def get_or_create_subject_state(self, child_id: uuid.UUID, subject_id: uuid.UUID) -> LearnerSubjectState:
        state = self.db.scalar(
            select(LearnerSubjectState).where(
                LearnerSubjectState.child_id == child_id,
                LearnerSubjectState.subject_id == subject_id,
            )
        )
        if state is None:
            state = LearnerSubjectState(child_id=child_id, subject_id=subject_id)
            self.db.add(state)
            self.db.flush()
        return state

    # ------------------------------------------------------------------ #
    # writes
    # ------------------------------------------------------------------ #
    def record_answer(
        self,
        *,
        child_id: uuid.UUID,
        question: Question,
        dimension: Dimension,
        correct: bool,
        response_time_ms: int | None,
        hint_used: bool,
        now: datetime | None = None,
    ) -> tuple[float, float, MasteryStatus]:
        """Apply one answer to concept, skill and subject state.

        Returns (mastery_before, mastery_after, status).
        """
        now = now or datetime.now(timezone.utc)
        state = self.get_or_create_concept_state(child_id, question.concept_id, dimension)

        # Apply forgetting before scoring, so a long gap is reflected honestly.
        before = state.mastery_score
        if state.last_attempt_at:
            last = state.last_attempt_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days = (now - last).total_seconds() / 86400.0
            if days > 7:
                before = decay_for_absence(before, days)

        update = self.engine.update(
            before,
            state.confidence,
            Evidence(
                correct=correct,
                difficulty=question.effective_difficulty,
                response_time_ms=response_time_ms,
                hint_used=hint_used,
                prior_attempts=state.attempt_count,
                prior_streak=state.streak,
            ),
        )

        state.mastery_score = update.mastery_after
        state.confidence = update.confidence
        state.status = update.status
        state.attempt_count += 1
        state.last_attempt_at = now
        if correct:
            state.correct_count += 1
            state.streak += 1
            state.best_streak = max(state.best_streak, state.streak)
            state.last_correct_at = now
        else:
            state.incorrect_count += 1
            state.streak = 0
        if hint_used:
            state.hint_usage += 1
        if response_time_ms is not None:
            prev = state.average_response_time_ms
            n = state.attempt_count
            state.average_response_time_ms = (
                response_time_ms if prev is None else (prev * (n - 1) + response_time_ms) / n
            )

        # Review scheduling: only once the concept is worth remembering.
        if correct and update.mastery_after >= CONFIG.mastery.learning:
            sched = self.scheduler.schedule(
                correct=True,
                review_count=state.review_count,
                current_interval_days=state.review_interval_days,
                now=now,
            )
        else:
            sched = self.scheduler.schedule(
                correct=False,
                review_count=state.review_count,
                current_interval_days=state.review_interval_days or 1.0,
                now=now,
            )
            if not correct and state.status == MasteryStatus.mastered:
                state.status = MasteryStatus.needs_review
        state.next_review_at = sched.next_review_at
        state.review_interval_days = sched.interval_days
        state.review_count = sched.review_count

        # Skill ability
        if question.skill_id:
            skill_state = self.get_or_create_skill_state(child_id, question.skill_id)
            skill_state.ability = update_ability(
                skill_state.ability, correct, question.effective_difficulty, skill_state.attempt_count
            )
            skill_state.attempt_count += 1
            if correct:
                skill_state.correct_count += 1
            skill_state.last_attempt_at = now
            skill_state.confidence = min(0.98, skill_state.confidence + 0.05 * (1 - skill_state.confidence))

        # Question calibration data (spec §36)
        question.observed_attempts += 1
        if correct:
            question.observed_correct += 1
        from app.adaptive.difficulty import observed_difficulty
        question.observed_difficulty = observed_difficulty(
            question.observed_correct, question.observed_attempts
        )

        self.db.flush()
        return update.mastery_before, update.mastery_after, update.status

    def refresh_subject_state(self, child_id: uuid.UUID, subject_id: uuid.UUID) -> LearnerSubjectState:
        """Recompute mastered counts and the vocabulary estimate."""
        subject_state = self.get_or_create_subject_state(child_id, subject_id)

        rows = self.db.execute(
            select(LearnerConceptState, Concept)
            .join(Concept, Concept.id == LearnerConceptState.concept_id)
            .where(LearnerConceptState.child_id == child_id, Concept.subject_id == subject_id)
        ).all()

        # A concept counts as mastered when its weakest measured dimension is mastered.
        by_concept: dict[uuid.UUID, list[LearnerConceptState]] = {}
        for state, concept in rows:
            by_concept.setdefault(concept.id, []).append(state)

        mastered = developing = 0
        confidences: list[float] = []
        for states in by_concept.values():
            lowest = min(s.mastery_score for s in states)
            confidences.append(sum(s.confidence for s in states) / len(states))
            if lowest >= CONFIG.mastery.mastered:
                mastered += 1
            elif lowest >= CONFIG.mastery.developing:
                developing += 1

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        estimate = estimate_vocabulary(
            mastered_concepts=mastered,
            developing_concepts=developing,
            average_confidence=avg_conf,
        )

        subject_state.concepts_mastered = mastered
        subject_state.vocabulary_estimate = estimate.words
        subject_state.vocabulary_confidence = estimate.confidence
        subject_state.vocabulary_band = estimate.band

        abilities = self.db.scalars(
            select(LearnerSkillState.ability)
            .join(Skill, Skill.id == LearnerSkillState.skill_id)
            .where(LearnerSkillState.child_id == child_id, Skill.subject_id == subject_id)
        ).all()
        if abilities:
            subject_state.ability = sum(abilities) / len(abilities)

        self.db.flush()
        return subject_state

    def unmet_prerequisites(self, child_id: uuid.UUID, subject_id: uuid.UUID) -> set[uuid.UUID]:
        """Concepts whose prerequisites are not yet understood (spec §17.7)."""
        concepts = self.db.scalars(
            select(Concept).where(Concept.subject_id == subject_id, Concept.active.is_(True))
        ).all()
        states = self.concept_states(child_id)

        blocked: set[uuid.UUID] = set()
        for concept in concepts:
            for prereq in concept.prerequisites:
                dims = [s for (cid, _), s in states.items() if cid == prereq.id]
                best = max((s.mastery_score for s in dims), default=0.0)
                if best < CONFIG.mastery.developing:
                    blocked.add(concept.id)
                    break
        return blocked
