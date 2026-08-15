"""Shared route dependencies."""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Child, LearningSession, QuestionAttempt, Subject


def get_child(child_id: uuid.UUID = Path(...), db: Session = Depends(get_db)) -> Child:
    child = db.get(Child, child_id)
    if child is None or not child.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Child not found")
    return child


def get_session_obj(session_id: uuid.UUID = Path(...), db: Session = Depends(get_db)) -> LearningSession:
    session = db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


def get_subject_by_slug(db: Session, slug: str) -> Subject:
    subject = db.scalar(select(Subject).where(Subject.slug == slug))
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown subject {slug!r}")
    return subject


def get_attempt(db: Session, attempt_id: uuid.UUID, session: LearningSession) -> QuestionAttempt:
    attempt = db.get(QuestionAttempt, attempt_id)
    if attempt is None or attempt.session_id != session.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found in this session")
    if attempt.answered_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This question was already answered")
    return attempt
