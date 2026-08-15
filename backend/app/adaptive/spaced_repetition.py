"""Spaced repetition scheduling (spec §23).

Simple, configurable interval ladder. A miss shortens the interval rather than
resetting the concept — forgetting is a scheduling signal, not a punishment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.adaptive.config import CONFIG, ReviewConfig


@dataclass
class ReviewUpdate:
    next_review_at: datetime
    interval_days: float
    review_count: int


class SpacedRepetitionScheduler:
    def __init__(self, config: ReviewConfig | None = None):
        self.cfg = config or CONFIG.review

    def schedule(
        self,
        *,
        correct: bool,
        review_count: int,
        current_interval_days: float,
        now: datetime | None = None,
    ) -> ReviewUpdate:
        now = now or datetime.now(timezone.utc)

        if correct:
            # Step up the ladder; stay on the last rung once past the end.
            idx = min(review_count, len(self.cfg.intervals) - 1)
            interval = float(self.cfg.intervals[idx])
            new_count = review_count + 1
        else:
            # Lapse: shrink what we had, and come back soon.
            shrunk = current_interval_days * self.cfg.lapse_factor
            interval = max(self.cfg.min_interval_days, min(shrunk, self.cfg.relearn_interval_days))
            new_count = max(0, review_count - 1)

        interval = max(self.cfg.min_interval_days, interval)
        return ReviewUpdate(
            next_review_at=now + timedelta(days=interval),
            interval_days=interval,
            review_count=new_count,
        )

    @staticmethod
    def is_due(next_review_at: datetime | None, now: datetime | None = None) -> bool:
        if next_review_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        if next_review_at.tzinfo is None:
            next_review_at = next_review_at.replace(tzinfo=timezone.utc)
        return next_review_at <= now

    @staticmethod
    def overdue_days(next_review_at: datetime | None, now: datetime | None = None) -> float:
        if next_review_at is None:
            return 0.0
        now = now or datetime.now(timezone.utc)
        if next_review_at.tzinfo is None:
            next_review_at = next_review_at.replace(tzinfo=timezone.utc)
        return max(0.0, (now - next_review_at).total_seconds() / 86400.0)
