"""Pydantic request/response models.

Child-facing payloads deliberately omit mastery numbers — the child sees named
bands, the parent sees percentages (design §16).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- children ----------------------------------------------------------------
class ChildCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    birth_year: int | None = Field(default=None, ge=2000, le=2030)
    avatar: str = "owl"


class ChildUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar: str | None = None
    active: bool | None = None


class ChildOut(ORMModel):
    id: uuid.UUID
    name: str
    avatar: str
    birth_year: int | None = None
    active: bool
    last_active_at: datetime | None = None


# --- content -----------------------------------------------------------------
class SubjectOut(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    icon: str | None = None
    description: str | None = None


class SkillOut(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    child_name: str | None = None
    parent_skill_id: uuid.UUID | None = None
    level: int


class OptionOut(BaseModel):
    id: uuid.UUID
    value: str
    label: str | None = None
    media: dict[str, Any] = {}


class QuestionOut(BaseModel):
    """What the child app renders. No answer, no mastery, no difficulty."""

    attempt_id: uuid.UUID
    question_id: uuid.UUID
    type: str
    dimension: str
    concept: str | None = None
    prompt: str
    media: dict[str, Any] = {}
    options: list[OptionOut] = []
    letters: list[str] | None = None      # spelling tiles
    hint_available: bool = True
    session_progress: float
    continue_session: bool


class SessionCreate(BaseModel):
    subject: str = "english"
    session_type: Literal["diagnostic", "practice", "review", "challenge", "mixed"] | None = None


class SessionOut(ORMModel):
    id: uuid.UUID
    child_id: uuid.UUID
    subject_id: uuid.UUID
    session_type: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    planned_questions: int
    questions_presented: int
    questions_correct: int


class AnswerIn(BaseModel):
    attempt_id: uuid.UUID
    answer: Any
    response_time_ms: int | None = None
    hint_used: bool = False
    hint_level: int = 0


class RewardOut(BaseModel):
    kind: str
    label: str
    payload: dict[str, Any] = {}


class AnswerOut(BaseModel):
    is_correct: bool
    # Child-facing wording: never "wrong" (design §10).
    verdict: Literal["yes", "not_yet"]
    expected: str | None = None
    explanation: str | None = None
    concept_mastered: bool = False
    rewards: list[RewardOut] = []
    continue_session: bool


class HintOut(BaseModel):
    level: int
    text: str
    remaining_levels: int


class SessionSummary(BaseModel):
    session_id: uuid.UUID
    questions_presented: int
    questions_correct: int
    new_specimens: list[dict[str, Any]] = []
    milestones: list[dict[str, Any]] = []
    improvement: str | None = None
    vocabulary_estimate: int | None = None
    vocabulary_band: str | None = None
    next_milestone: dict[str, Any] | None = None


# --- progress (child voice) ---------------------------------------------------
class SkillBand(BaseModel):
    skill: str
    child_name: str
    band: Literal["just started", "getting there", "good", "really good"]
    fraction: float          # for the bar only, never shown as a number


class SpecimenOut(BaseModel):
    concept: str
    definition: str | None = None
    image: str | None = None
    status: Literal["mastered", "learning", "needs_review", "not_found"]
    dimensions: dict[str, float] = {}


class ChildProgressOut(BaseModel):
    child: ChildOut
    words_known: int
    specimens_total: int
    skills: list[SkillBand]
    next_milestone: dict[str, Any] | None = None
    streak_days: int = 0


# --- parent (numbers allowed) -------------------------------------------------
class ParentSkillStat(BaseModel):
    skill: str
    ability: float
    attempts: int
    accuracy: float | None = None


class ParentSummaryOut(BaseModel):
    child: ChildOut
    vocabulary_estimate: int | None
    vocabulary_confidence: float | None
    vocabulary_band: str | None
    concepts_mastered: int
    concepts_learning: int
    skills: list[ParentSkillStat]
    strongest: list[str]
    weakest: list[str]
    sessions_this_week: int
    minutes_this_week: float
    narrative: str


class ActivityItem(BaseModel):
    at: datetime
    session_id: uuid.UUID
    session_type: str
    presented: int
    correct: int


# --- developer ----------------------------------------------------------------
class LearnerStateOut(BaseModel):
    """The debugging view from spec §50."""

    child: str
    subject: str
    ability: float
    vocabulary_estimate: int | None
    strong: list[dict[str, Any]]
    learning: list[dict[str, Any]]
    weak: list[dict[str, Any]]
    due_for_review: list[dict[str, Any]]
    next_recommended: dict[str, Any] | None = None
