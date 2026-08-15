"""Learner simulator (spec §53).

Runs synthetic children through real sessions so engine behaviour can be
verified before any real child sees it. Profiles differ per *dimension*, which
is how "strong meaning, weak spelling" gets exercised.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Child, Concept, Family, Question, Subject
from app.models.learner import Dimension
from app.services.session_service import SessionService


@dataclass
class LearnerProfile:
    """Probability of answering correctly, per dimension, at matched difficulty."""

    name: str
    skill: dict[Dimension, float]
    # How much harder-than-ability questions hurt.
    difficulty_sensitivity: float = 1.6
    # Chance of remembering a concept seen before (drives review behaviour).
    retention: float = 0.9
    learning_rate: float = 0.06        # improves as they practise
    seed: int = 7

    def probability(self, dimension: Dimension, difficulty: float, exposure: int) -> float:
        base = self.skill.get(dimension, 0.5) + self.learning_rate * min(exposure, 6)
        penalty = self.difficulty_sensitivity * max(0.0, difficulty - base)
        return max(0.02, min(0.98, base - penalty))


PROFILES = {
    "average": LearnerProfile("Average learner", {
        Dimension.recognition: 0.65, Dimension.meaning: 0.6,
        Dimension.context: 0.55, Dimension.spelling: 0.5,
    }),
    "fast": LearnerProfile("Fast learner", {
        Dimension.recognition: 0.85, Dimension.meaning: 0.82,
        Dimension.context: 0.8, Dimension.spelling: 0.78,
    }, learning_rate=0.09),
    "struggling": LearnerProfile("Struggling learner", {
        Dimension.recognition: 0.42, Dimension.meaning: 0.36,
        Dimension.context: 0.3, Dimension.spelling: 0.25,
    }, learning_rate=0.03),
    "vocab_strong_spelling_weak": LearnerProfile("Strong vocabulary, weak spelling", {
        Dimension.recognition: 0.9, Dimension.meaning: 0.88,
        Dimension.context: 0.8, Dimension.spelling: 0.22,
    }, learning_rate=0.04),
    "forgetful": LearnerProfile("Forgetful learner", {
        Dimension.recognition: 0.7, Dimension.meaning: 0.65,
        Dimension.context: 0.6, Dimension.spelling: 0.55,
    }, retention=0.45),
}


@dataclass
class SimulationResult:
    profile: str
    sessions: int
    questions: int
    correct: int
    by_dimension: dict[str, tuple[int, int]] = field(default_factory=dict)
    difficulty_trace: list[float] = field(default_factory=list)
    unique_questions: int = 0
    concepts_touched: int = 0
    vocabulary_estimate: int | None = None
    ability_by_skill: dict[str, float] = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        return self.correct / self.questions if self.questions else 0.0


def simulate(
    db: Session,
    profile: LearnerProfile,
    *,
    sessions: int = 10,
    questions_per_session: int = 8,
    seed: int = 11,
    day_gap: float = 1.0,
) -> SimulationResult:
    rng = random.Random(seed)
    subject = db.scalar(select(Subject).where(Subject.slug == "english"))

    family = Family(name=f"Sim {profile.name}")
    db.add(family)
    db.flush()
    child = Child(family_id=family.id, name=profile.name, birth_year=2020)
    db.add(child)
    db.flush()

    result = SimulationResult(profile=profile.name, sessions=sessions, questions=0, correct=0)
    exposure: dict[tuple, int] = {}
    seen_questions: set = set()
    concepts: set = set()

    svc = SessionService(db, seed=seed)
    for s_i in range(sessions):
        session = svc.start_session(child, subject)
        session.planned_questions = questions_per_session

        for _ in range(questions_per_session):
            nxt = svc.next_question(session)
            if nxt is None:
                break
            q, dim = nxt.question, nxt.dimension
            key = (q.concept_id, dim)
            exp = exposure.get(key, 0)

            p = profile.probability(dim, q.effective_difficulty, exp)
            # Forgetting between sessions for low-retention profiles.
            if exp > 0 and rng.random() > profile.retention:
                p *= 0.5
            correct = rng.random() < p

            concept = db.get(Concept, q.concept_id)
            answer = _answer_for(db, q, concept, correct, rng)
            svc.submit_answer(session, nxt.attempt, answer, response_time_ms=rng.randint(1500, 9000))

            exposure[key] = exp + 1
            seen_questions.add(q.id)
            concepts.add(q.concept_id)
            result.questions += 1
            result.correct += int(correct)
            result.difficulty_trace.append(q.effective_difficulty)
            hits, total = result.by_dimension.get(str(dim), (0, 0))
            result.by_dimension[str(dim)] = (hits + int(correct), total + 1)

        svc.complete_session(session)
        # Advance the clock so review scheduling actually matters.
        if day_gap:
            _shift_clock(db, child.id, days=day_gap)

    state = svc.learner.refresh_subject_state(child.id, subject.id)
    result.vocabulary_estimate = state.vocabulary_estimate
    result.unique_questions = len(seen_questions)
    result.concepts_touched = len(concepts)

    from app.models import Skill
    from app.models.learner import LearnerSkillState

    for ss in db.scalars(select(LearnerSkillState).where(LearnerSkillState.child_id == child.id)).all():
        result.ability_by_skill[db.get(Skill, ss.skill_id).name] = round(ss.ability, 3)

    db.flush()
    return result


def _answer_for(db: Session, question: Question, concept, correct: bool, rng: random.Random):
    """Produce a plausible right or wrong answer for this question type."""
    qtype = str(question.question_type)
    if qtype == "spelling":
        word = (question.answer or {}).get("value", "")
        if correct:
            return word
        if len(word) > 2:                      # a realistic near-miss
            i = rng.randrange(1, len(word))
            return word[:i] + word[i + 1:]
        return "zz"
    options = list(question.options)
    if not options:
        return "" if not correct else (question.answer or {}).get("value", "")
    right = [o for o in options if o.is_correct]
    wrong = [o for o in options if not o.is_correct]
    if correct and right:
        return right[0].value
    if wrong:
        return rng.choice(wrong).value
    return ""


def _shift_clock(db: Session, child_id, days: float) -> None:
    """Pull review dates backwards to emulate time passing."""
    from app.models.learner import LearnerConceptState

    delta = timedelta(days=days)
    for state in db.scalars(
        select(LearnerConceptState).where(LearnerConceptState.child_id == child_id)
    ).all():
        if state.next_review_at:
            state.next_review_at = state.next_review_at - delta
        if state.last_attempt_at:
            state.last_attempt_at = state.last_attempt_at - delta
    db.flush()


def run_all(db: Session, **kwargs) -> list[SimulationResult]:
    return [simulate(db, profile, **kwargs) for profile in PROFILES.values()]


if __name__ == "__main__":
    from app.db import SessionLocal, engine
    from app.models import Base
    from app.seed.seed import seed_all

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_all(session)
        session.commit()
        print(f"{'profile':34} {'acc':>6} {'qs':>5} {'uniq':>5} {'concepts':>9} {'vocab':>7}")
        print("-" * 72)
        for r in run_all(session, sessions=8, questions_per_session=8):
            print(f"{r.profile:34} {r.accuracy:6.0%} {r.questions:5} {r.unique_questions:5} "
                  f"{r.concepts_touched:9} {r.vocabulary_estimate or 0:7}")
            dims = "  ".join(
                f"{d[:4]}={c}/{t}" for d, (c, t) in sorted(r.by_dimension.items())
            )
            print(f"{'':34} {dims}")
        session.rollback()
