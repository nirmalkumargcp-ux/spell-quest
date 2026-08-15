"""The learning loop endpoints (spec §30–31).

The client asks for "the next question", never for a specific one.
"""
from __future__ import annotations

import random
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_attempt, get_child, get_session_obj, get_subject_by_slug
from app.db import get_db
from app.models import (
    Child, Concept, LearningSession, Question, QuestionAttempt, Reward, SessionStatus, SessionType,
)
from app.models.learner import Dimension
from app.schemas import (
    AnswerIn, AnswerOut, HintOut, OptionOut, QuestionOut, RewardOut, SessionCreate, SessionOut,
    SessionSummary,
)
from app.services.events import emit
from app.services.session_service import SessionService

router = APIRouter(tags=["learning"])

# Plausible near-miss letters for spelling tiles, so the distractors teach.
_PHONIC_NEIGHBOURS = {
    "a": "eu", "e": "ai", "i": "ey", "o": "au", "u": "oa",
    "c": "ks", "k": "cq", "s": "cz", "f": "vph", "v": "fb", "b": "dp",
    "d": "bt", "g": "jq", "j": "g", "m": "n", "n": "mr", "p": "bq",
    "t": "dp", "y": "ie", "z": "s", "l": "r", "r": "lw", "h": "n", "w": "vr",
    "x": "ks", "q": "kg",
}


def _letter_tiles(word: str, rng: random.Random) -> list[str]:
    """The word's letters plus a few phonics traps (design §03 Question)."""
    tiles = list(word)
    extras: list[str] = []
    for ch in dict.fromkeys(word):
        for cand in _PHONIC_NEIGHBOURS.get(ch, ""):
            if cand not in tiles and cand not in extras:
                extras.append(cand)
    rng.shuffle(extras)
    target_extra = 2 if len(word) <= 5 else 3
    tiles += extras[:target_extra]
    rng.shuffle(tiles)
    return tiles


@router.post("/children/{child_id}/sessions", response_model=SessionOut, status_code=201)
def create_session(
    payload: SessionCreate,
    child: Child = Depends(get_child),
    db: Session = Depends(get_db),
) -> LearningSession:
    subject = get_subject_by_slug(db, payload.subject)
    svc = SessionService(db)
    session_type = SessionType(payload.session_type) if payload.session_type else None
    return svc.start_session(child, subject, session_type)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def read_session(session: LearningSession = Depends(get_session_obj)) -> LearningSession:
    return session


@router.post("/sessions/{session_id}/next-question", response_model=QuestionOut | None)
def next_question(
    session: LearningSession = Depends(get_session_obj),
    db: Session = Depends(get_db),
):
    if session.status is not SessionStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Session is not active")

    svc = SessionService(db)
    nxt = svc.next_question(session)
    if nxt is None:
        return None

    q = nxt.question
    concept = db.get(Concept, q.concept_id) if q.concept_id else None
    rng = random.Random(str(nxt.attempt.id))

    options = [
        OptionOut(id=o.id, value=o.value, label=o.label, media=o.media or {})
        for o in q.options
    ]
    # Options arrive pre-shuffled per attempt so position carries no information.
    rng.shuffle(options)

    letters = None
    if str(q.question_type) == "spelling" and concept:
        letters = _letter_tiles(concept.name, rng)

    return QuestionOut(
        attempt_id=nxt.attempt.id,
        question_id=q.id,
        type=str(q.question_type),
        dimension=nxt.dimension.value,
        concept=concept.name if concept else None,
        prompt=q.prompt,
        media=q.media or {},
        options=options,
        letters=letters,
        hint_available=bool(q.hints),
        session_progress=nxt.session_progress,
        continue_session=nxt.continue_session,
    )


@router.post("/sessions/{session_id}/hint", response_model=HintOut)
def get_hint(
    attempt_id: uuid.UUID,
    level: int = 1,
    session: LearningSession = Depends(get_session_obj),
    db: Session = Depends(get_db),
) -> HintOut:
    """Hints are a learning signal, not a penalty (spec §27)."""
    attempt = db.get(QuestionAttempt, attempt_id)
    if attempt is None or attempt.session_id != session.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    question = db.get(Question, attempt.question_id)
    hints = question.hints or []
    if not hints:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hints for this question")

    idx = max(0, min(level, len(hints)) - 1)
    emit(db, "hint_requested", child_id=session.child_id, session_id=session.id,
         question_id=str(question.id), level=idx + 1)
    return HintOut(
        level=idx + 1,
        text=hints[idx].get("text", ""),
        remaining_levels=max(0, len(hints) - (idx + 1)),
    )


@router.post("/sessions/{session_id}/answer", response_model=AnswerOut)
def submit_answer(
    payload: AnswerIn,
    session: LearningSession = Depends(get_session_obj),
    db: Session = Depends(get_db),
) -> AnswerOut:
    if session.status is not SessionStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Session is not active")
    attempt = get_attempt(db, payload.attempt_id, session)

    svc = SessionService(db)
    outcome = svc.submit_answer(
        session, attempt, payload.answer,
        response_time_ms=payload.response_time_ms,
        hint_used=payload.hint_used,
        hint_level=payload.hint_level,
    )

    rewards = db.scalars(
        select(Reward).where(Reward.session_id == session.id, Reward.seen.is_(False))
    ).all()
    for r in rewards:
        r.seen = True

    return AnswerOut(
        is_correct=outcome.is_correct,
        verdict="yes" if outcome.is_correct else "not_yet",
        expected=outcome.expected,
        explanation=outcome.explanation,
        concept_mastered=outcome.concept_mastered,
        rewards=[RewardOut(kind=r.kind, label=r.label, payload=r.payload or {}) for r in rewards],
        continue_session=outcome.continue_session,
    )


@router.post("/sessions/{session_id}/complete", response_model=SessionSummary)
def complete_session(
    session: LearningSession = Depends(get_session_obj),
    db: Session = Depends(get_db),
) -> SessionSummary:
    svc = SessionService(db)
    if session.status is SessionStatus.active:
        svc.complete_session(session)

    state = svc.learner.get_or_create_subject_state(session.child_id, session.subject_id)
    rewards = db.scalars(select(Reward).where(Reward.session_id == session.id)).all()

    specimens = [
        {"concept": r.payload.get("concept"), "image": r.payload.get("image")}
        for r in rewards if r.kind == "concept_mastered"
    ]
    milestones = [
        {"name": r.label, "icon": (r.payload or {}).get("icon")}
        for r in rewards if r.kind == "milestone"
    ]

    from app.adaptive.progression import next_band
    nb = next_band(state.vocabulary_estimate or 0)

    return SessionSummary(
        session_id=session.id,
        questions_presented=session.questions_presented,
        questions_correct=session.questions_correct,
        new_specimens=specimens,
        milestones=milestones,
        improvement=_improvement_note(db, session),
        vocabulary_estimate=state.vocabulary_estimate,
        vocabulary_band=state.vocabulary_band,
        next_milestone={"target": nb[0], "band": nb[1]} if nb else None,
    )


def _improvement_note(db: Session, session: LearningSession) -> str | None:
    """One named improvement, measured against the child's own past (design §11)."""
    from datetime import datetime, timedelta, timezone

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    rows = db.scalars(
        select(QuestionAttempt).where(
            QuestionAttempt.child_id == session.child_id,
            QuestionAttempt.dimension == Dimension.spelling,
            QuestionAttempt.is_correct.isnot(None),
        )
    ).all()
    if len(rows) < 6:
        return None

    def acc(items):
        return sum(1 for a in items if a.is_correct) / len(items) if items else 0.0

    recent = [a for a in rows if a.created_at and a.created_at.replace(tzinfo=timezone.utc) >= week_ago]
    older = [a for a in rows if a not in recent]
    if len(recent) >= 3 and len(older) >= 3 and acc(recent) > acc(older) + 0.1:
        return (
            f"Spelling got easier — {round(acc(older)*10)} out of 10 before, "
            f"{round(acc(recent)*10)} out of 10 now."
        )
    return None
