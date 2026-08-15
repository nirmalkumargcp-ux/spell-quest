"""Unit tests for the adaptive engine's building blocks."""
from datetime import datetime, timedelta, timezone

import pytest

from app.adaptive.config import CONFIG
from app.adaptive.difficulty import difficulty_fit, target_difficulty, update_ability
from app.adaptive.evaluation import evaluate_answer
from app.adaptive.mastery import Evidence, RuleBasedMasteryEngine, child_band, decay_for_absence
from app.adaptive.progression import band_for, estimate_vocabulary
from app.adaptive.spaced_repetition import SpacedRepetitionScheduler
from app.models.content import Question, QuestionOption, QuestionType
from app.models.learner import MasteryStatus


# --- mastery -----------------------------------------------------------------
def test_repeated_success_reaches_mastery():
    engine = RuleBasedMasteryEngine()
    m, conf = 0.0, 0.0
    for i in range(8):
        u = engine.update(m, conf, Evidence(correct=True, difficulty=0.5, prior_attempts=i, prior_streak=i))
        m, conf = u.mastery_after, u.confidence
    assert m >= CONFIG.mastery.mastered
    assert engine.estimate(m) is MasteryStatus.mastered


def test_hint_reduces_evidence_but_is_not_a_failure():
    engine = RuleBasedMasteryEngine()
    without = engine.update(0.4, 0.5, Evidence(correct=True, difficulty=0.5))
    with_hint = engine.update(0.4, 0.5, Evidence(correct=True, difficulty=0.5, hint_used=True))
    assert with_hint.mastery_after < without.mastery_after
    assert with_hint.mastery_after > 0.4, "a hinted correct answer still counts as progress"


def test_hard_question_correct_is_worth_more_than_easy():
    engine = RuleBasedMasteryEngine()
    easy = engine.update(0.5, 0.5, Evidence(correct=True, difficulty=0.2))
    hard = engine.update(0.5, 0.5, Evidence(correct=True, difficulty=0.9))
    assert hard.mastery_after > easy.mastery_after


def test_missing_an_easy_question_costs_more_than_a_hard_one():
    engine = RuleBasedMasteryEngine()
    easy = engine.update(0.7, 0.5, Evidence(correct=False, difficulty=0.2))
    hard = engine.update(0.7, 0.5, Evidence(correct=False, difficulty=0.95))
    assert easy.mastery_after < hard.mastery_after


def test_mastery_stays_in_range():
    engine = RuleBasedMasteryEngine()
    assert engine.update(0.99, 0.9, Evidence(correct=True, difficulty=0.9)).mastery_after <= 1.0
    assert engine.update(0.01, 0.1, Evidence(correct=False, difficulty=0.1)).mastery_after >= 0.0


def test_absence_decays_but_never_erases():
    assert decay_for_absence(0.9, 0) == 0.9
    assert decay_for_absence(0.9, 45) < 0.9
    assert decay_for_absence(0.9, 3650) >= 0.15


def test_child_band_never_shows_numbers():
    assert child_band(0.05) == "just started"
    assert child_band(0.3) == "getting there"
    assert child_band(0.5) == "good"
    assert child_band(0.9) == "really good"


# --- difficulty ---------------------------------------------------------------
def test_target_difficulty_is_above_ability():
    assert target_difficulty(0.5) > 0.5


def test_difficulty_fit_peaks_at_target_and_falls_away():
    ability = 0.5
    at_target = difficulty_fit(target_difficulty(ability), ability)
    far = difficulty_fit(0.99, ability)
    assert at_target == pytest.approx(1.0)
    assert far == 0.0


def test_ability_rises_on_success_and_falls_on_failure():
    up = update_ability(0.5, True, 0.6, attempts=3)
    down = update_ability(0.5, False, 0.6, attempts=3)
    assert up > 0.5 > down


# --- spaced repetition ---------------------------------------------------------
def test_review_intervals_follow_the_ladder():
    s = SpacedRepetitionScheduler()
    now = datetime.now(timezone.utc)
    intervals = []
    count, current = 0, 0.0
    for _ in range(5):
        u = s.schedule(correct=True, review_count=count, current_interval_days=current, now=now)
        intervals.append(u.interval_days)
        count, current = u.review_count, u.interval_days
    assert intervals == list(CONFIG.review.intervals)


def test_a_miss_shortens_the_interval():
    s = SpacedRepetitionScheduler()
    now = datetime.now(timezone.utc)
    lapse = s.schedule(correct=False, review_count=4, current_interval_days=30, now=now)
    assert lapse.interval_days <= CONFIG.review.relearn_interval_days
    assert lapse.review_count < 4


def test_due_detection():
    s = SpacedRepetitionScheduler()
    now = datetime.now(timezone.utc)
    assert s.is_due(now - timedelta(days=1), now)
    assert not s.is_due(now + timedelta(days=1), now)
    assert s.overdue_days(now - timedelta(days=3), now) == pytest.approx(3, abs=0.01)


# --- vocabulary ----------------------------------------------------------------
def test_vocabulary_estimate_grows_with_mastery_and_has_confidence():
    small = estimate_vocabulary(mastered_concepts=5, developing_concepts=2, average_confidence=0.4)
    large = estimate_vocabulary(mastered_concepts=80, developing_concepts=10, average_confidence=0.9)
    assert large.words > small.words
    assert large.confidence > small.confidence
    assert band_for(1200) == "1,000–1,500"


# --- evaluators ----------------------------------------------------------------
def _spelling_question(word="butterfly"):
    return Question(
        subject_id=None, question_type=QuestionType.spelling, prompt="Spell it",
        answer={"value": word}, hints=[], media={}, meta={},
    )


def test_spelling_is_case_and_space_insensitive():
    q = _spelling_question()
    assert evaluate_answer(q, "  Butterfly ").is_correct
    assert not evaluate_answer(q, "buterfly").is_correct


def test_spelling_classifies_the_error_for_later_analysis():
    q = _spelling_question("cat")
    assert evaluate_answer(q, "cta").detail["error_kind"] == "transposition"
    assert evaluate_answer(q, "ca").detail["error_kind"] == "omission"
    assert evaluate_answer(q, "cap").detail["error_kind"] == "substitution"


def test_choice_matches_by_value_or_id():
    q = Question(
        subject_id=None, question_type=QuestionType.multiple_choice, prompt="?",
        answer={}, hints=[], media={}, meta={},
    )
    right = QuestionOption(value="very big", is_correct=True)
    wrong = QuestionOption(value="very fast", is_correct=False)
    q.options = [right, wrong]
    assert evaluate_answer(q, "Very Big").is_correct
    assert not evaluate_answer(q, "very fast").is_correct


def test_unknown_question_type_raises_rather_than_guessing():
    from app.adaptive.evaluation.base import get_evaluator

    with pytest.raises(ValueError):
        get_evaluator("not_a_real_type")
