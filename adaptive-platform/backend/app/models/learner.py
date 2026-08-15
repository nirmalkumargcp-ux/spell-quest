"""The learner model (spec §12–13) — the core intellectual property.

State is kept at three levels: subject, skill and concept. Concept state is
further split by *dimension* (recognition / meaning / context / spelling),
because a child can know what a word means and still not be able to spell it —
the fundamental requirement in spec §22.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDMixin, enum_col


class MasteryStatus(enum.StrEnum):
    unknown = "unknown"
    introduced = "introduced"
    learning = "learning"
    developing = "developing"
    mastered = "mastered"
    needs_review = "needs_review"


class Dimension(enum.StrEnum):
    """The four ways a vocabulary concept can be known (design §07)."""

    recognition = "recognition"
    meaning = "meaning"
    context = "context"
    spelling = "spelling"


class LearnerConceptState(UUIDMixin, TimestampMixin, Base):
    """One row per child × concept × dimension."""

    __tablename__ = "learner_concept_states"

    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True, nullable=False
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    dimension: Mapped[Dimension] = mapped_column(enum_col(Dimension, 20), default=Dimension.recognition, nullable=False)

    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[MasteryStatus] = mapped_column(enum_col(MasteryStatus, 20), default=MasteryStatus.unknown, nullable=False, index=True)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hint_usage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_response_time_ms: Mapped[float | None] = mapped_column(Float)

    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_correct_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Spaced repetition (spec §23)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    review_interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    meta: Mapped[dict] = mapped_column(JSONType, default=dict)

    __table_args__ = (
        UniqueConstraint("child_id", "concept_id", "dimension", name="uq_learner_concept_dimension"),
        Index("ix_learner_concept_due", "child_id", "next_review_at"),
    )

    concept = relationship("Concept")


class LearnerSkillState(UUIDMixin, TimestampMixin, Base):
    """Rolled-up ability per skill — drives difficulty targeting (spec §19)."""

    __tablename__ = "learner_skill_states"

    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True, nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), index=True, nullable=False
    )

    ability: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)

    __table_args__ = (UniqueConstraint("child_id", "skill_id", name="uq_learner_skill"),)

    skill = relationship("Skill")


class LearnerSubjectState(UUIDMixin, TimestampMixin, Base):
    """Subject-level summary, including the vocabulary estimate (spec §20–21)."""

    __tablename__ = "learner_subject_states"

    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )

    ability: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    concepts_mastered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vocabulary_estimate: Mapped[int | None] = mapped_column(Integer)
    vocabulary_confidence: Mapped[float | None] = mapped_column(Float)
    vocabulary_band: Mapped[str | None] = mapped_column(String(40))
    diagnostic_completed: Mapped[bool] = mapped_column(default=False, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)

    __table_args__ = (UniqueConstraint("child_id", "subject_id", name="uq_learner_subject"),)
