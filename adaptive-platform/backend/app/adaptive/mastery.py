"""Mastery estimation (spec §14–16).

A deliberately transparent, rules-based model. `MasteryEngine` is the seam:
swapping in Bayesian Knowledge Tracing later means implementing this interface,
not touching the rest of the application.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.adaptive.config import CONFIG, MasteryConfig
from app.models.learner import MasteryStatus


@dataclass
class Evidence:
    """Everything one answer tells us about a concept."""

    correct: bool
    difficulty: float = 0.5
    response_time_ms: int | None = None
    hint_used: bool = False
    prior_attempts: int = 0
    prior_streak: int = 0


@dataclass
class MasteryUpdate:
    mastery_before: float
    mastery_after: float
    confidence: float
    status: MasteryStatus
    evidence_value: float
    learning_rate: float


class MasteryEngine(ABC):
    """The interface named in spec §16."""

    @abstractmethod
    def update(self, current: float, confidence: float, evidence: Evidence) -> MasteryUpdate: ...

    @abstractmethod
    def estimate(self, current: float) -> MasteryStatus: ...


class RuleBasedMasteryEngine(MasteryEngine):
    """V1: `new = old + learning_rate × evidence`, all terms explainable."""

    def __init__(self, config: MasteryConfig | None = None):
        self.cfg = config or CONFIG.mastery

    # -- helpers -----------------------------------------------------------
    def _learning_rate(self, prior_attempts: int) -> float:
        """Early evidence moves the estimate more than the twentieth attempt."""
        rate = self.cfg.base_learning_rate - self.cfg.learning_rate_decay * prior_attempts
        return max(self.cfg.min_learning_rate, rate)

    def _evidence_value(self, ev: Evidence, current: float) -> float:
        """Signed evidence in roughly [-1, 1].

        Correct answers on hard questions are worth more than correct answers on
        easy ones; incorrect answers on easy questions cost more than on hard.
        """
        if ev.correct:
            # Surprise: how much harder was this than the child's current level?
            value = 0.55 + 0.9 * max(0.0, ev.difficulty - current)
            if ev.prior_streak >= 2:
                value += 0.10                       # repeated success
            if ev.response_time_ms is not None:
                if ev.response_time_ms <= self.cfg.fast_response_ms:
                    value += self.cfg.fast_response_bonus
                elif ev.response_time_ms >= self.cfg.slow_response_ms:
                    value -= self.cfg.slow_response_penalty
            if ev.hint_used:
                value *= (1.0 - self.cfg.hint_penalty)
        else:
            # Missing something easy is stronger evidence than missing something hard.
            value = -(0.55 + 0.9 * max(0.0, current - ev.difficulty))
            if ev.hint_used:
                # A miss after a hint is a weaker negative — they were still trying.
                value *= (1.0 - self.cfg.hint_penalty * 0.5)
        return max(-1.0, min(1.2, value))

    # -- interface ---------------------------------------------------------
    def update(self, current: float, confidence: float, evidence: Evidence) -> MasteryUpdate:
        lr = self._learning_rate(evidence.prior_attempts)
        value = self._evidence_value(evidence, current)
        new = current + lr * value
        new = max(0.0, min(1.0, new))

        new_conf = min(
            self.cfg.confidence_max,
            confidence + self.cfg.confidence_per_attempt * (1.0 - confidence),
        )
        return MasteryUpdate(
            mastery_before=current,
            mastery_after=new,
            confidence=new_conf,
            status=self.estimate(new),
            evidence_value=value,
            learning_rate=lr,
        )

    def estimate(self, current: float) -> MasteryStatus:
        c = self.cfg
        if current >= c.mastered:
            return MasteryStatus.mastered
        if current >= c.developing:
            return MasteryStatus.developing
        if current >= c.learning:
            return MasteryStatus.learning
        if current >= c.introduced:
            return MasteryStatus.introduced
        return MasteryStatus.unknown


def decay_for_absence(mastery: float, days_since_review: float, half_life_days: float = 45.0) -> float:
    """Gentle forgetting curve so a long absence surfaces review work (spec §41-G).

    Never drops below 0.15 — the child has still met the concept before.
    """
    if days_since_review <= 0:
        return mastery
    factor = 0.5 ** (days_since_review / half_life_days)
    return max(0.15, mastery * factor)


def status_for(mastery: float, engine: MasteryEngine | None = None) -> MasteryStatus:
    return (engine or RuleBasedMasteryEngine()).estimate(mastery)


def child_band(mastery: float) -> str:
    """Four named bands shown to the child — never a percentage (design §08)."""
    if mastery >= CONFIG.mastery.developing:
        return "really good"
    if mastery >= CONFIG.mastery.learning:
        return "good"
    if mastery >= CONFIG.mastery.introduced:
        return "getting there"
    return "just started"
