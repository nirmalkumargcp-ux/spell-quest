"""Content: subjects, the skill hierarchy, concepts and the question bank.

Content describes *what a question is*. It never stores how well a particular
child knows something — that lives in the learner model (spec §2 Principle 2).
"""
import enum
import uuid

from sqlalchemy import (
    Boolean, Float, ForeignKey, Integer, String, Table, Text, Column, Uuid, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDMixin


class QuestionType(str, enum.Enum):
    """Extensible — evaluators are registered by type, never switched on inline."""

    multiple_choice = "multiple_choice"
    image_choice = "image_choice"
    text_input = "text_input"
    spelling = "spelling"
    true_false = "true_false"
    ordering = "ordering"
    matching = "matching"
    audio_response = "audio_response"
    numeric_input = "numeric_input"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    approved = "approved"
    published = "published"
    retired = "retired"


# A concept can belong to more than one skill (spec §9).
concept_skills = Table(
    "concept_skills",
    Base.metadata,
    Column("concept_id", Uuid(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)

# Explicit prerequisite edges between concepts (spec §28).
concept_prerequisites = Table(
    "concept_prerequisites",
    Base.metadata,
    Column("concept_id", Uuid(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
    Column("prerequisite_id", Uuid(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
)


class Subject(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subjects"

    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(40))
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    skills: Mapped[list["Skill"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Skill(UUIDMixin, TimestampMixin, Base):
    """Self-referencing hierarchy: English → Vocabulary → Spelling → …"""

    __tablename__ = "skills"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Child-facing wording, e.g. "Knowing words" for Vocabulary (design §08).
    child_name: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)

    __table_args__ = (UniqueConstraint("subject_id", "slug", name="uq_skill_subject_slug"),)

    subject: Mapped[Subject] = relationship(back_populates="skills")
    parent: Mapped["Skill | None"] = relationship(remote_side="Skill.id", back_populates="children")
    children: Mapped[list["Skill"]] = relationship(back_populates="parent")
    questions: Mapped[list["Question"]] = relationship(back_populates="skill")


class Concept(UUIDMixin, TimestampMixin, Base):
    """Something masterable: the word BUTTERFLY, or 'addition with carrying'."""

    __tablename__ = "concepts"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    primary_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="SET NULL"), index=True
    )
    slug: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    # Vocabulary band this word belongs to, e.g. 500 → the 0–500 band (spec §21).
    frequency_band: Mapped[int | None] = mapped_column(Integer, index=True)
    media: Mapped[dict] = mapped_column(JSONType, default=dict)   # {image, audio, plate}
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("subject_id", "slug", name="uq_concept_subject_slug"),)

    subject: Mapped[Subject] = relationship()
    primary_skill: Mapped[Skill | None] = relationship()
    skills: Mapped[list[Skill]] = relationship(secondary=concept_skills)
    questions: Mapped[list["Question"]] = relationship(back_populates="concept")
    prerequisites: Mapped[list["Concept"]] = relationship(
        secondary=concept_prerequisites,
        primaryjoin=lambda: Concept.id == concept_prerequisites.c.concept_id,
        secondaryjoin=lambda: Concept.id == concept_prerequisites.c.prerequisite_id,
    )


class Question(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "questions"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="SET NULL"), index=True
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    question_type: Mapped[QuestionType] = mapped_column(String(32), index=True, nullable=False)

    # Author's estimate; `observed_difficulty` is recalibrated from attempts (spec §36).
    difficulty: Mapped[float] = mapped_column(Float, default=0.5, nullable=False, index=True)
    observed_difficulty: Mapped[float | None] = mapped_column(Float)
    observed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observed_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    age_min: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    age_max: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[dict] = mapped_column(JSONType, default=dict)      # evaluator-specific
    explanation: Mapped[str | None] = mapped_column(Text)
    hints: Mapped[list] = mapped_column(JSONType, default=list)       # progressive levels (spec §27)
    media: Mapped[dict] = mapped_column(JSONType, default=dict)
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)

    status: Mapped[ContentStatus] = mapped_column(String(16), default=ContentStatus.published, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    skill: Mapped[Skill | None] = relationship(back_populates="questions")
    concept: Mapped[Concept | None] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QuestionOption.display_order"
    )

    @property
    def effective_difficulty(self) -> float:
        """Observed difficulty once there is enough evidence, else the author's."""
        if self.observed_difficulty is not None and self.observed_attempts >= 30:
            return self.observed_difficulty
        return self.difficulty


class QuestionOption(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "question_options"

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))
    media: Mapped[dict] = mapped_column(JSONType, default=dict)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    question: Mapped[Question] = relationship(back_populates="options")
