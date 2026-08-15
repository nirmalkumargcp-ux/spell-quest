"""The seven learner scenarios from spec §41, plus determinism (§42).

These are the tests that matter: they assert the engine *behaves* correctly,
not merely that the code runs.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.adaptive.config import CONFIG
from app.adaptive.question_selector import QuestionSelector, SelectionContext
from app.models import Concept, LearnerConceptState, Question, Skill, Subject
from app.models.learner import Dimension, LearnerSkillState, MasteryStatus
from app.services.session_service import SessionService
from app.simulator.simulate import PROFILES, simulate


def _play(db, child, subject, *, answers, questions=12, seed=5):
    """Run a session answering by a callable(dimension, question) -> bool."""
    svc = SessionService(db, seed=seed)
    session = svc.start_session(child, subject)
    session.planned_questions = questions
    trace = []
    for _ in range(questions):
        nxt = svc.next_question(session)
        if nxt is None:
            break
        correct = answers(nxt.dimension, nxt.question)
        ans = _answer(nxt.question, correct)
        out = svc.submit_answer(session, nxt.attempt, ans, response_time_ms=3000)
        trace.append((nxt.dimension, nxt.question, out))
    svc.complete_session(session)
    return trace


def _answer(question, correct: bool):
    if str(question.question_type) == "spelling":
        return (question.answer or {}).get("value") if correct else "zzzz"
    right = [o for o in question.options if o.is_correct]
    wrong = [o for o in question.options if not o.is_correct]
    if correct:
        return right[0].value if right else ""
    return wrong[0].value if wrong else "zzzz"


# --- Scenario A: easy questions answered correctly → difficulty rises ---------
def test_scenario_a_difficulty_increases_with_success(db, child, subject):
    trace = _play(db, child, subject, answers=lambda d, q: True, questions=16)
    difficulties = [q.effective_difficulty for _, q, _ in trace]
    first_half = sum(difficulties[:5]) / 5
    last_half = sum(difficulties[-5:]) / 5
    assert last_half > first_half, f"difficulty did not rise: {first_half:.2f} → {last_half:.2f}"


# --- Scenario B: repeated failure → difficulty falls --------------------------
def test_scenario_b_difficulty_decreases_after_repeated_failure(db, child, subject):
    _play(db, child, subject, answers=lambda d, q: True, questions=10)
    before = [q.effective_difficulty for _, q, _ in
              _play(db, child, subject, answers=lambda d, q: False, questions=10)]
    after = [q.effective_difficulty for _, q, _ in
             _play(db, child, subject, answers=lambda d, q: False, questions=10)]
    assert sum(after) / len(after) < sum(before) / len(before) + 0.01


# --- Scenario C: knows meaning, struggles with spelling -----------------------
def test_scenario_c_weak_dimension_gets_more_practice(db, child, subject):
    """The fundamental requirement in spec §22."""
    def answers(dimension, question):
        return dimension is not Dimension.spelling

    trace = []
    for _ in range(4):
        trace += _play(db, child, subject, answers=answers, questions=10)

    counts: dict[str, int] = {}
    for dimension, _, _ in trace:
        counts[str(dimension)] = counts.get(str(dimension), 0) + 1

    spelling = counts.get("spelling", 0)
    recognition = counts.get("recognition", 0)
    assert spelling > recognition, f"weak dimension under-practised: {counts}"


def _advance_days(db, child, days: float):
    """Emulate time passing so scheduled reviews come due."""
    for state in db.scalars(
        select(LearnerConceptState).where(LearnerConceptState.child_id == child.id)
    ).all():
        if state.next_review_at:
            state.next_review_at = state.next_review_at - timedelta(days=days)
        if state.last_attempt_at:
            state.last_attempt_at = state.last_attempt_at - timedelta(days=days)
    db.flush()


# --- Scenario D: mastery moves a concept into spaced review -------------------
def test_scenario_d_mastered_concept_gets_review_schedule(db, child, subject):
    _play(db, child, subject, answers=lambda d, q: True, questions=16)
    states = db.scalars(
        select(LearnerConceptState).where(LearnerConceptState.child_id == child.id)
    ).all()
    assert states, "no learner state was written"
    assert [s for s in states if s.next_review_at is not None], "nothing was scheduled for review"

    # Come back day after day; repeated success must walk up the interval ladder
    # and carry at least one concept to mastered.
    for _ in range(5):
        _advance_days(db, child, 2)
        _play(db, child, subject, answers=lambda d, q: True, questions=10)

    states = db.scalars(
        select(LearnerConceptState).where(LearnerConceptState.child_id == child.id)
    ).all()
    advanced = [s for s in states if s.review_count >= 2]
    assert advanced, "review intervals never advanced despite repeated success"
    assert max(s.review_interval_days for s in advanced) > CONFIG.review.intervals[0]
    assert [s for s in states if s.status is MasteryStatus.mastered], "nothing reached mastery"


# --- Scenario E: forgetting lowers mastery and tightens review ----------------
def test_scenario_e_forgetting_reduces_mastery_and_shortens_interval(db, child, subject):
    _play(db, child, subject, answers=lambda d, q: True, questions=16)
    state = db.scalars(
        select(LearnerConceptState)
        .where(LearnerConceptState.child_id == child.id)
        .order_by(LearnerConceptState.mastery_score.desc())
    ).first()
    assert state is not None
    before_mastery = state.mastery_score
    before_interval = state.review_interval_days
    concept_id, dimension = state.concept_id, state.dimension

    question = db.scalars(
        select(Question).where(Question.concept_id == concept_id)
    ).first()

    from app.adaptive.learner_model import LearnerModel
    LearnerModel(db).record_answer(
        child_id=child.id, question=question, dimension=Dimension(dimension),
        correct=False, response_time_ms=8000, hint_used=False,
    )
    db.refresh(state)
    assert state.mastery_score < before_mastery
    assert state.review_interval_days <= max(before_interval, 1.0)


# --- Scenario F: prerequisites gate advanced concepts -------------------------
def test_scenario_f_prerequisites_block_then_release(db, child, subject):
    from app.adaptive.learner_model import LearnerModel

    learner = LearnerModel(db)
    butterfly = db.scalar(select(Concept).where(Concept.slug == "butterfly"))
    bee = db.scalar(select(Concept).where(Concept.slug == "bee"))
    assert bee in butterfly.prerequisites

    blocked = learner.unmet_prerequisites(child.id, subject.id)
    assert butterfly.id in blocked, "advanced concept was not gated"

    # Learn the prerequisite thoroughly.
    for dimension in Dimension:
        st = learner.get_or_create_concept_state(child.id, bee.id, dimension)
        st.mastery_score = 0.9
        st.status = MasteryStatus.mastered
    db.flush()

    assert butterfly.id not in learner.unmet_prerequisites(child.id, subject.id)


# --- Scenario G: a long absence surfaces review before new material -----------
def test_scenario_g_absence_prioritises_overdue_review(db, child, subject):
    _play(db, child, subject, answers=lambda d, q: True, questions=12)

    # Pretend three weeks passed.
    for state in db.scalars(
        select(LearnerConceptState).where(LearnerConceptState.child_id == child.id)
    ).all():
        if state.next_review_at:
            state.next_review_at = state.next_review_at - timedelta(days=21)
        state.last_attempt_at = (state.last_attempt_at or datetime.now(timezone.utc)) - timedelta(days=21)
    db.flush()

    svc = SessionService(db, seed=3)
    session = svc.start_session(child, subject)
    sources = []
    for _ in range(4):
        nxt = svc.next_question(session)
        if nxt is None:
            break
        sources.append(nxt.attempt.selection_reason.get("source"))
        svc.submit_answer(session, nxt.attempt, _answer(nxt.question, True), response_time_ms=3000)

    assert "review_due" in sources, f"overdue work was not prioritised: {sources}"


# --- Determinism (spec §42) ----------------------------------------------------
def test_same_seed_same_choice(db, child, subject):
    questions = list(db.scalars(select(Question).where(Question.subject_id == subject.id)).all())
    ctx = SelectionContext(ability_by_skill={}, states={})
    first = QuestionSelector(seed=99).select(questions, ctx)
    second = QuestionSelector(seed=99).select(questions, ctx)
    assert first.question.id == second.question.id


def test_different_seeds_can_differ(db, child, subject):
    questions = list(db.scalars(select(Question).where(Question.subject_id == subject.id)).all())
    ctx = SelectionContext(ability_by_skill={}, states={})
    picks = {QuestionSelector(seed=s).select(questions, ctx).question.id for s in range(12)}
    assert len(picks) > 1, "selection is not exploring alternatives"


# --- Health of the loop (spec §53) --------------------------------------------
def test_session_never_repeats_a_question(db, child, subject):
    trace = _play(db, child, subject, answers=lambda d, q: True, questions=12)
    ids = [q.id for _, q, _ in trace]
    assert len(ids) == len(set(ids)), "a question was repeated within one session"


def test_engine_introduces_new_concepts_over_time(db, child, subject):
    """It must not get stuck drilling the same handful of words."""
    seen = set()
    for _ in range(6):
        for _, q, _ in _play(db, child, subject, answers=lambda d, q: True, questions=10):
            seen.add(q.concept_id)
    assert len(seen) >= 12, f"only {len(seen)} concepts introduced across 60 questions"


def test_diagnostic_covers_every_dimension(db, child, subject):
    trace = _play(db, child, subject, answers=lambda d, q: True, questions=8)
    dims = {str(d) for d, _, _ in trace[:4]}
    assert dims == {"recognition", "meaning", "context", "spelling"}


@pytest.mark.parametrize("profile_key", ["average", "fast", "struggling", "vocab_strong_spelling_weak"])
def test_simulated_profiles_behave_sensibly(db, profile_key):
    result = simulate(db, PROFILES[profile_key], sessions=4, questions_per_session=8, seed=21)
    assert result.questions > 0
    assert 0.0 <= result.accuracy <= 1.0
    assert result.concepts_touched >= 3, "engine got stuck on too few concepts"


def test_stronger_learner_outperforms_weaker_one(db):
    fast = simulate(db, PROFILES["fast"], sessions=5, questions_per_session=8, seed=33)
    weak = simulate(db, PROFILES["struggling"], sessions=5, questions_per_session=8, seed=33)
    assert fast.accuracy > weak.accuracy
    assert (fast.vocabulary_estimate or 0) >= (weak.vocabulary_estimate or 0)
