"""Immutable event stream (spec §32) and structured logging (spec §49)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.progression import Event

log = logging.getLogger("adaptive.events")


def emit(
    db: Session,
    name: str,
    *,
    child_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    **payload: Any,
) -> Event:
    event = Event(
        created_at=datetime.now(timezone.utc),
        name=name,
        child_id=child_id,
        session_id=session_id,
        payload=payload,
    )
    db.add(event)
    # Child identifiers stay out of the log line itself (spec §39).
    log.info("event=%s session=%s %s", name, session_id, payload)
    return event
