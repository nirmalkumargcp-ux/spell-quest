"""Milestones, rewards and the immutable event log (spec §28–29, §32).

Rewards are a presentation layer derived from learning events — never the
source of truth. The learner model is.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDMixin


class MilestoneKind(str, enum.Enum):
    concepts_mastered = "concepts_mastered"
    vocabulary_estimate = "vocabulary_estimate"
    skill_mastered = "skill_mastered"
    streak = "streak"


class Milestone(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "milestones"

    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[MilestoneKind] = mapped_column(String(30), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(40))


class ChildMilestone(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "child_milestones"

    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True, nullable=False
    )
    milestone_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("milestones.id", ondelete="CASCADE"), index=True, nullable=False
    )
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (UniqueConstraint("child_id", "milestone_id", name="uq_child_milestone"),)

    milestone: Mapped[Milestone] = relationship()


class Reward(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rewards"

    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)   # concept_mastered, badge, …
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    seen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Event(UUIDMixin, Base):
    """Append-only analytics stream (spec §32). No updated_at: events never change."""

    __tablename__ = "events"

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    child_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)

    __table_args__ = (Index("ix_event_child_name", "child_id", "name"),)
