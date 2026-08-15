"""Ability estimation and difficulty fit (spec §19, §36)."""
from __future__ import annotations

from app.adaptive.config import CONFIG, SelectionWeights


def target_difficulty(ability: float, weights: SelectionWeights | None = None) -> float:
    """Aim slightly above demonstrated ability — the productive struggle zone."""
    w = weights or CONFIG.weights
    return max(0.05, min(0.98, ability + w.difficulty_stretch))


def difficulty_fit(question_difficulty: float, ability: float, weights: SelectionWeights | None = None) -> float:
    """1.0 at the target, falling off linearly outside the tolerance window."""
    w = weights or CONFIG.weights
    distance = abs(question_difficulty - target_difficulty(ability, w))
    if distance >= w.difficulty_tolerance:
        return 0.0
    return 1.0 - (distance / w.difficulty_tolerance)


def update_ability(current: float, correct: bool, question_difficulty: float, attempts: int) -> float:
    """Elo-flavoured nudge: beating a hard question moves ability more."""
    k = max(0.04, 0.18 - 0.004 * attempts)
    expected = 1.0 / (1.0 + 10 ** ((question_difficulty - current) * 4))
    actual = 1.0 if correct else 0.0
    return max(0.02, min(0.99, current + k * (actual - expected)))


def observed_difficulty(correct: int, attempts: int) -> float | None:
    """Difficulty implied by real performance: 1 - proportion correct (spec §36)."""
    if attempts <= 0:
        return None
    return max(0.02, min(0.98, 1.0 - (correct / attempts)))
