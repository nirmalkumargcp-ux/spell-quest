"""Child profiles, content browsing, and the child-facing progress view."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adaptive.config import CONFIG
from app.adaptive.mastery import child_band
from app.adaptive.progression import next_band
from app.api.deps import get_child, get_subject_by_slug
from app.db import get_db
from app.models import (
    Child, Concept, Family, LearnerConceptState, LearnerSkillState, LearningSession, Skill, Subject,
)
from app.models.learner import Dimension, MasteryStatus
from app.schemas import (
    ChildCreate, ChildOut, ChildProgressOut, ChildUpdate, SkillBand, SkillOut, SpecimenOut, SubjectOut,
)
from app.services.events import emit

router = APIRouter(tags=["children"])


@router.post("/children", response_model=ChildOut, status_code=201)
def create_child(payload: ChildCreate, db: Session = Depends(get_db)) -> Child:
    # Single-family deployment for now; auth (spec §39) attaches the real family.
    family = db.scalar(select(Family).limit(1))
    if family is None:
        family = Family(name="Home")
        db.add(family)
        db.flush()
    child = Child(
        family_id=family.id, name=payload.name,
        birth_year=payload.birth_year, avatar=payload.avatar,
    )
    db.add(child)
    db.flush()
    emit(db, "child_created", child_id=child.id)
    return child


@router.get("/children", response_model=list[ChildOut])
def list_children(db: Session = Depends(get_db)) -> list[Child]:
    return list(db.scalars(select(Child).where(Child.active.is_(True)).order_by(Child.created_at)).all())


@router.get("/children/{child_id}", response_model=ChildOut)
def read_child(child: Child = Depends(get_child)) -> Child:
    return child


@router.patch("/children/{child_id}", response_model=ChildOut)
def update_child(
    payload: ChildUpdate, child: Child = Depends(get_child), db: Session = Depends(get_db)
) -> Child:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(child, field, value)
    db.flush()
    return child


@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db)) -> list[Subject]:
    return list(db.scalars(
        select(Subject).where(Subject.active.is_(True)).order_by(Subject.display_order)
    ).all())


@router.get("/subjects/{subject_slug}/skills", response_model=list[SkillOut])
def list_skills(subject_slug: str, db: Session = Depends(get_db)) -> list[Skill]:
    subject = get_subject_by_slug(db, subject_slug)
    return list(db.scalars(
        select(Skill).where(Skill.subject_id == subject.id).order_by(Skill.level, Skill.display_order)
    ).all())


@router.get("/children/{child_id}/progress", response_model=ChildProgressOut)
def child_progress(
    child: Child = Depends(get_child),
    subject_slug: str = Query("english", alias="subject"),
    db: Session = Depends(get_db),
) -> ChildProgressOut:
    """The child's own view: named bands, never percentages (design §08)."""
    subject = get_subject_by_slug(db, subject_slug)

    top_skills = db.scalars(
        select(Skill).where(Skill.subject_id == subject.id, Skill.level == 0)
        .order_by(Skill.display_order)
    ).all()
    abilities = {
        s.skill_id: s.ability
        for s in db.scalars(select(LearnerSkillState).where(LearnerSkillState.child_id == child.id)).all()
    }

    bands: list[SkillBand] = []
    for skill in top_skills:
        children_ids = [c.id for c in skill.children] or [skill.id]
        vals = [abilities[i] for i in children_ids if i in abilities]
        ability = sum(vals) / len(vals) if vals else 0.0
        bands.append(SkillBand(
            skill=skill.slug,
            child_name=skill.child_name or skill.name,
            band=child_band(ability),
            fraction=round(min(1.0, max(0.08, ability)), 3),
        ))

    mastered = db.scalar(
        select(func.count(func.distinct(LearnerConceptState.concept_id)))
        .join(Concept, Concept.id == LearnerConceptState.concept_id)
        .where(
            LearnerConceptState.child_id == child.id,
            Concept.subject_id == subject.id,
            LearnerConceptState.status == MasteryStatus.mastered,
        )
    ) or 0
    total = db.scalar(select(func.count(Concept.id)).where(Concept.subject_id == subject.id)) or 0

    from app.adaptive.learner_model import LearnerModel
    state = LearnerModel(db).get_or_create_subject_state(child.id, subject.id)
    nb = next_band(state.vocabulary_estimate or 0)

    return ChildProgressOut(
        child=ChildOut.model_validate(child),
        words_known=state.vocabulary_estimate or 0,
        specimens_total=total,
        skills=bands,
        next_milestone={"target": nb[0], "band": nb[1]} if nb else None,
        streak_days=_streak_days(db, child.id),
    )


@router.get("/children/{child_id}/notebook", response_model=list[SpecimenOut])
def notebook(
    child: Child = Depends(get_child),
    subject_slug: str = Query("english", alias="subject"),
    include_unfound: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[SpecimenOut]:
    """The collection — the learner model made visible (design §07)."""
    subject = get_subject_by_slug(db, subject_slug)
    concepts = db.scalars(
        select(Concept).where(Concept.subject_id == subject.id, Concept.active.is_(True))
        .order_by(Concept.frequency_band, Concept.difficulty)
    ).all()

    states: dict[uuid.UUID, dict[str, LearnerConceptState]] = {}
    for st in db.scalars(select(LearnerConceptState).where(LearnerConceptState.child_id == child.id)).all():
        states.setdefault(st.concept_id, {})[str(st.dimension)] = st

    out: list[SpecimenOut] = []
    for concept in concepts:
        dims = states.get(concept.id, {})
        if not dims and not include_unfound:
            continue
        # Always report all four dimensions so the card back is complete —
        # an untouched dimension is genuinely 0, not missing.
        scores = {
            d.value: round(dims[d.value].mastery_score, 3) if d.value in dims else 0.0
            for d in Dimension
        }
        if not dims:
            status = "not_found"
        else:
            lowest = min(s.mastery_score for s in dims.values())
            if any(s.status == MasteryStatus.needs_review for s in dims.values()):
                status = "needs_review"
            elif lowest >= CONFIG.mastery.mastered:
                status = "mastered"
            else:
                status = "learning"
        out.append(SpecimenOut(
            concept=concept.name,
            definition=concept.description,
            image=(concept.media or {}).get("image"),
            status=status,
            dimensions=scores,
        ))
    return out


def _streak_days(db: Session, child_id: uuid.UUID) -> int:
    rows = db.scalars(
        select(LearningSession.started_at)
        .where(LearningSession.child_id == child_id)
        .order_by(LearningSession.started_at.desc())
        .limit(120)
    ).all()
    if not rows:
        return 0
    days = sorted({r.date() for r in rows}, reverse=True)
    today = datetime.now(timezone.utc).date()
    if days[0] < today - timedelta(days=1):
        return 0
    streak, cursor = 0, days[0]
    for d in days:
        if d == cursor:
            streak += 1
            cursor -= timedelta(days=1)
        elif d < cursor:
            break
    return streak
