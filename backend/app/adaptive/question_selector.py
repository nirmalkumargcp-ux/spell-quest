"""Adaptive question selection (spec §17–18).

Candidates are generated from five sources, scored on independent weighted
signals, then drawn from the top N with controlled randomness. Given a fixed
seed the choice is fully reproducible (spec §42), and every selection carries
the reason it was made (spec §43).
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.adaptive.config import CONFIG, SelectionWeights
from app.adaptive.difficulty import difficulty_fit
from app.adaptive.spaced_repetition import SpacedRepetitionScheduler
from app.models.content import Question
from app.models.learner import Dimension, LearnerConceptState, MasteryStatus


class CandidateSource(str, Enum):
    review_due = "review_due"
    weak_concept = "weak_concept"
    learning = "learning"
    new_concept = "new_concept"
    retention = "retention"


@dataclass
class Candidate:
    question: Question
    source: CandidateSource
    concept_id: uuid.UUID | None
    dimension: Dimension | None
    mastery: float
    score: float = 0.0
    reason: dict[str, float] = field(default_factory=dict)


@dataclass
class SelectionContext:
    """Everything the selector needs, already loaded by the caller."""

    ability_by_skill: dict[uuid.UUID, float]
    states: dict[tuple[uuid.UUID, Dimension], LearnerConceptState]
    recent_question_ids: list[uuid.UUID] = field(default_factory=list)
    recent_types: list[str] = field(default_factory=list)
    recent_concept_ids: list[uuid.UUID] = field(default_factory=list)
    recent_dimensions: list[Dimension] = field(default_factory=list)
    unmet_prerequisites: set[uuid.UUID] = field(default_factory=set)
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Cold start: assume little ability, so the first questions are genuinely easy.
    default_ability: float = 0.15
    # The diagnostic walks every dimension so each can be estimated separately
    # (spec §20); practice sessions leave this unset and let the weights decide.
    prefer_dimension: Dimension | None = None
    # Overrides skill ability when targeting difficulty (used by the diagnostic ramp).
    ability_override: float | None = None


class QuestionSelector:
    def __init__(self, weights: SelectionWeights | None = None, seed: int | None = None):
        self.w = weights or CONFIG.weights
        self.rng = random.Random(seed)
        self.scheduler = SpacedRepetitionScheduler()

    # ------------------------------------------------------------------ #
    # candidate generation
    # ------------------------------------------------------------------ #
    def build_candidates(self, questions: list[Question], ctx: SelectionContext) -> list[Candidate]:
        candidates: list[Candidate] = []
        for q in questions:
            if not q.active or q.concept_id is None:
                continue
            # Prerequisites gate advanced concepts entirely (spec §17.7).
            if q.concept_id in ctx.unmet_prerequisites:
                continue

            dimension = _dimension_for(q)
            state = ctx.states.get((q.concept_id, dimension))
            mastery = state.mastery_score if state else 0.0
            source = self._classify(state, ctx)
            candidates.append(
                Candidate(
                    question=q,
                    source=source,
                    concept_id=q.concept_id,
                    dimension=dimension,
                    mastery=mastery,
                )
            )
        return candidates

    def _classify(self, state: LearnerConceptState | None, ctx: SelectionContext) -> CandidateSource:
        if state is None or state.attempt_count == 0:
            return CandidateSource.new_concept
        if self.scheduler.is_due(state.next_review_at, ctx.now):
            return CandidateSource.review_due
        if state.status == MasteryStatus.mastered:
            return CandidateSource.retention
        if state.mastery_score < CONFIG.mastery.learning:
            return CandidateSource.weak_concept
        return CandidateSource.learning

    # ------------------------------------------------------------------ #
    # scoring
    # ------------------------------------------------------------------ #
    def score(self, cand: Candidate, ctx: SelectionContext) -> Candidate:
        w = self.w
        reason: dict[str, float] = {}

        source_weight = {
            CandidateSource.review_due: w.review_due,
            CandidateSource.weak_concept: w.weak_concept,
            CandidateSource.learning: w.learning_priority,
            CandidateSource.new_concept: w.new_concept,
            CandidateSource.retention: w.retention,
        }[cand.source]
        reason[cand.source.value] = round(source_weight, 4)

        # Overdue review climbs above everything else the longer it waits.
        if cand.source is CandidateSource.review_due:
            state = ctx.states.get((cand.concept_id, cand.dimension))
            overdue = self.scheduler.overdue_days(state.next_review_at if state else None, ctx.now)
            bonus = min(0.5, overdue * 0.08)
            source_weight += bonus
            reason["review_overdue"] = round(bonus, 4)

        # The mastery gap: concepts near the learning edge are worth most.
        gap = 1.0 - abs(cand.mastery - 0.5) * 2.0 if cand.mastery > 0 else 0.6
        reason["mastery_gap"] = round(gap, 4)

        skill_id = cand.question.skill_id
        ability = (
            ctx.ability_override
            if ctx.ability_override is not None
            else ctx.ability_by_skill.get(skill_id, ctx.default_ability)
        )
        fit = difficulty_fit(cand.question.effective_difficulty, ability, w)
        reason["difficulty_fit"] = round(fit, 4)

        variety = self._variety(cand, ctx)
        reason["variety"] = round(variety, 4)

        dimension_pref = 0.0
        if ctx.prefer_dimension is not None:
            dimension_pref = 1.0 if cand.dimension is ctx.prefer_dimension else -0.8
            reason["dimension_target"] = round(dimension_pref, 4)

        total = (
            source_weight
            + gap * 0.35
            + fit * w.difficulty_fit
            + variety * w.variety
            + dimension_pref
        )
        cand.score = total
        cand.reason = reason
        return cand

    def _variety(self, cand: Candidate, ctx: SelectionContext) -> float:
        """Penalise repeating the same question, concept, type or dimension.

        Without the dimension term a cold-start child can be handed four
        spelling questions in a row purely because they fit the difficulty.
        """
        score = 1.0
        if cand.question.id in ctx.recent_question_ids:
            score -= 0.9
        if cand.concept_id in ctx.recent_concept_ids[-2:]:
            score -= 0.35
        qtype = str(cand.question.question_type)
        score -= 0.2 * sum(1 for t in ctx.recent_types[-3:] if t == qtype)
        score -= 0.3 * sum(1 for d in ctx.recent_dimensions[-2:] if d is cand.dimension)
        return max(0.0, score)

    # ------------------------------------------------------------------ #
    # selection
    # ------------------------------------------------------------------ #
    def select(self, questions: list[Question], ctx: SelectionContext) -> Candidate | None:
        candidates = [self.score(c, ctx) for c in self.build_candidates(questions, ctx)]
        if not candidates:
            return None

        # Never repeat a question already asked this session when alternatives exist.
        fresh = [c for c in candidates if c.question.id not in ctx.recent_question_ids]
        pool = fresh or candidates

        pool.sort(key=lambda c: c.score, reverse=True)
        top = pool[: max(1, self.w.top_n)]

        # Controlled randomness: jitter the top few, then take the best (spec §18).
        jittered = [(c.score + self.rng.uniform(0, self.w.jitter), c) for c in top]
        jittered.sort(key=lambda pair: pair[0], reverse=True)
        chosen = jittered[0][1]
        chosen.reason["selected_from_top"] = float(len(top))
        return chosen


def _dimension_for(question: Question) -> Dimension:
    """Which knowledge dimension a question exercises."""
    explicit = (question.meta or {}).get("dimension")
    if explicit:
        try:
            return Dimension(explicit)
        except ValueError:
            pass
    from app.models.content import QuestionType

    mapping = {
        QuestionType.spelling: Dimension.spelling,
        QuestionType.image_choice: Dimension.recognition,
        QuestionType.multiple_choice: Dimension.meaning,
        QuestionType.text_input: Dimension.spelling,
    }
    qt = question.question_type
    if isinstance(qt, str):
        qt = QuestionType(qt)
    return mapping.get(qt, Dimension.recognition)
