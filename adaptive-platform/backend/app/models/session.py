"""Learning sessions and the immutable attempt log (spec §24–25)."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDMixin, enum_col
from app.models.learner import Dimension


class SessionType(enum.StrEnum):
    diagnostic = "diagnostic"
    practice = "practice"
    review = "review"
    challenge = "challenge"
    mixed = "mixed"


class SessionStatus(enum.StrEnum):
    active = "active"
    completed = "completed"
    abandoned = "abandoned"


class LearningSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "learning_sessions"

    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="SET NULL")
    )

    session_type: Mapped[SessionType] = mapped_column(enum_col(SessionType, 20), default=SessionType.practice, nullable=False)
    status: Mapped[SessionStatus] = mapped_column(enum_col(SessionStatus, 20), default=SessionStatus.active, nullable=False, index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Soft target — the engine may stop earlier when the estimate stabilises.
    planned_questions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    questions_presented: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    meta: Mapped[dict] = mapped_column(JSONType, default=dict)

    attempts: Mapped[list["QuestionAttempt"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="QuestionAttempt.created_at"
    )


class QuestionAttempt(UUIDMixin, TimestampMixin, Base):
    """Immutable record of one interaction. Never updated after answering."""

    __tablename__ = "question_attempts"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"), index=True
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="SET NULL"), index=True
    )
    dimension: Mapped[Dimension | None] = mapped_column(enum_col(Dimension, 20))

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    raw_answer: Mapped[str | None] = mapped_column(Text)          # preserved verbatim (spec §26)
    normalized_answer: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, index=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)

    hint_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hint_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    difficulty_at_attempt: Mapped[float | None] = mapped_column(Float)
    mastery_before: Mapped[float | None] = mapped_column(Float)
    mastery_after: Mapped[float | None] = mapped_column(Float)

    # Why the engine chose this question (spec §43) — developer-facing only.
    selection_reason: Mapped[dict] = mapped_column(JSONType, default=dict)
    evaluation: Mapped[dict] = mapped_column(JSONType, default=dict)

    session: Mapped[LearningSession] = relationship(back_populates="attempts")

    __table_args__ = (Index("ix_attempt_child_created", "child_id", "created_at"),)
