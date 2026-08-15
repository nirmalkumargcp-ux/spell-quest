"""Every tunable number for the adaptive engine, in one place (spec §14).

Nothing here may be duplicated elsewhere in the codebase. Tests import these
same values, so tuning a threshold cannot silently break a test's assumptions.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MasteryConfig:
    """Score bands (spec §14). Order matters: checked high to low."""

    introduced: float = 0.20
    learning: float = 0.40
    developing: float = 0.65
    mastered: float = 0.85

    # Weighted-update parameters (spec §15)
    base_learning_rate: float = 0.30
    # Early attempts move the estimate more than later ones.
    learning_rate_decay: float = 0.06
    min_learning_rate: float = 0.10

    hint_penalty: float = 0.45          # hints reduce evidence, never count as wrong
    fast_response_bonus: float = 0.10
    slow_response_penalty: float = 0.05
    fast_response_ms: int = 4000
    slow_response_ms: int = 20000

    # Confidence grows with evidence; used to gate milestones and estimates.
    confidence_per_attempt: float = 0.18
    confidence_max: float = 0.98


@dataclass(frozen=True)
class SelectionWeights:
    """Candidate scoring weights (spec §18)."""

    review_due: float = 1.00
    weak_concept: float = 0.85
    learning_priority: float = 0.70
    new_concept: float = 0.55
    retention: float = 0.25

    difficulty_fit: float = 0.90
    variety: float = 0.45
    prerequisite: float = 0.60

    # Controlled randomness — pick from the top-N rather than always the max.
    top_n: int = 4
    jitter: float = 0.12

    # Target questions slightly above demonstrated ability (spec §19).
    difficulty_stretch: float = 0.08
    difficulty_tolerance: float = 0.25


@dataclass(frozen=True)
class ReviewConfig:
    """Spaced repetition intervals in days (spec §23)."""

    intervals: tuple[float, ...] = (1, 3, 7, 14, 30)
    lapse_factor: float = 0.4       # interval shrinks after a miss
    min_interval_days: float = 0.5
    # A miss schedules the concept sooner than the normal first interval.
    relearn_interval_days: float = 0.5


@dataclass(frozen=True)
class DiagnosticConfig:
    """Initial assessment (spec §20). Deliberately short."""

    question_count: int = 6
    start_difficulty: float = 0.25
    step_up: float = 0.15
    step_down: float = 0.12
    # Stop early once the ability estimate stops moving.
    stability_threshold: float = 0.05


@dataclass(frozen=True)
class SessionConfig:
    default_questions: int = 5
    max_questions: int = 12
    # Two consecutive misses on a skill drop difficulty and re-teach (design §10).
    consecutive_miss_drop: int = 2


@dataclass(frozen=True)
class VocabularyConfig:
    """Bands are a communication device, not the learner model (spec §21)."""

    bands: tuple[tuple[int, int, str], ...] = (
        (0, 500, "0–500"),
        (500, 1000, "500–1,000"),
        (1000, 1500, "1,000–1,500"),
        (1500, 2000, "1,500–2,000"),
        (2000, 3000, "2,000–3,000"),
        (3000, 5000, "3,000–5,000"),
        (5000, 100000, "5,000+"),
    )
    # Each mastered concept stands for this many words of real vocabulary,
    # because the bank samples a frequency band rather than covering it.
    words_per_mastered_concept: int = 12


@dataclass(frozen=True)
class AdaptiveConfig:
    mastery: MasteryConfig = field(default_factory=MasteryConfig)
    weights: SelectionWeights = field(default_factory=SelectionWeights)
    review: ReviewConfig = field(default_factory=ReviewConfig)
    diagnostic: DiagnosticConfig = field(default_factory=DiagnosticConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    vocabulary: VocabularyConfig = field(default_factory=VocabularyConfig)


CONFIG = AdaptiveConfig()
