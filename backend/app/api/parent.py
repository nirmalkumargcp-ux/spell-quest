"""Parent analytics (spec §33) and the developer debug view (spec §50).

The parent sees real numbers; the child never does.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adaptive.config import CONFIG
from app.adaptive.learner_model import LearnerModel
from app.api.deps import get_child, get_subject_by_slug
from app.db import get_db
from app.models import (
    Child, Concept, LearnerConceptState, LearnerSkillState, LearningSession, QuestionAttempt, Skill,
)
from app.models.learner import MasteryStatus
from app.schemas import (
    ActivityItem, ChildOut, LearnerStateOut, ParentSkillStat, ParentSummaryOut,
)

router = APIRouter(tags=["parent"])


@router.get("/children/{child_id}/parent-summary", response_model=ParentSummaryOut)
def parent_summary(
    child: Child = Depends(get_child),
    subject_slug: str = Query("english", alias="subject"),
    db: Session = Depends(get_db),
) -> ParentSummaryOut:
    subject = get_subject_by_slug(db, subject_slug)
    learner = LearnerModel(db)
    state = learner.refresh_subject_state(child.id, subject.id)

    skills = db.scalars(
        select(Skill).where(Skill.subject_id == subject.id, Skill.level == 1)
        .order_by(Skill.display_order)
    ).all()
    skill_states = {
        s.skill_id: s
        for s in db.scalars(select(LearnerSkillState).where(LearnerSkillState.child_id == child.id)).all()
    }

    stats: list[ParentSkillStat] = []
    for skill in skills:
        st = skill_states.get(skill.id)
        stats.append(ParentSkillStat(
            skill=skill.name,
            ability=round(st.ability, 3) if st else 0.0,
            attempts=st.attempt_count if st else 0,
            accuracy=round(st.correct_count / st.attempt_count, 3) if st and st.attempt_count else None,
        ))

    measured = [s for s in stats if s.attempts >= 3]
    ranked = sorted(measured, key=lambda s: s.ability, reverse=True)
    strongest = [s.skill for s in ranked[:2]]
    weakest = [s.skill for s in ranked[-2:][::-1]] if len(ranked) > 2 else []

    learning = db.scalar(
        select(func.count(func.distinct(LearnerConceptState.concept_id)))
        .join(Concept, Concept.id == LearnerConceptState.concept_id)
        .where(
            LearnerConceptState.child_id == child.id,
            Concept.subject_id == subject.id,
            LearnerConceptState.status.in_([MasteryStatus.learning, MasteryStatus.developing]),
        )
    ) or 0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    sessions = db.scalars(
        select(LearningSession).where(
            LearningSession.child_id == child.id, LearningSession.started_at >= week_ago
        )
    ).all()
    minutes = 0.0
    for s in sessions:
        if s.completed_at and s.started_at:
            minutes += (s.completed_at - s.started_at).total_seconds() / 60.0

    return ParentSummaryOut(
        child=ChildOut.model_validate(child),
        vocabulary_estimate=state.vocabulary_estimate,
        vocabulary_confidence=state.vocabulary_confidence,
        vocabulary_band=state.vocabulary_band,
        concepts_mastered=state.concepts_mastered,
        concepts_learning=learning,
        skills=stats,
        strongest=strongest,
        weakest=weakest,
        sessions_this_week=len(sessions),
        minutes_this_week=round(minutes, 1),
        narrative=_narrative(child, state, strongest, weakest, len(sessions), minutes),
    )


@router.get("/children/{child_id}/recent-activity", response_model=list[ActivityItem])
def recent_activity(
    child: Child = Depends(get_child),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
) -> list[ActivityItem]:
    sessions = db.scalars(
        select(LearningSession).where(LearningSession.child_id == child.id)
        .order_by(LearningSession.started_at.desc()).limit(limit)
    ).all()
    return [
        ActivityItem(
            at=s.started_at, session_id=s.id, session_type=str(s.session_type),
            presented=s.questions_presented, correct=s.questions_correct,
        )
        for s in sessions
    ]


@router.get("/children/{child_id}/debug/learner-state", response_model=LearnerStateOut, tags=["developer"])
def learner_state(
    child: Child = Depends(get_child),
    subject_slug: str = Query("english", alias="subject"),
    db: Session = Depends(get_db),
) -> LearnerStateOut:
    """Answers 'why did the system give this question to this child?' (spec §50)."""
    subject = get_subject_by_slug(db, subject_slug)
    learner = LearnerModel(db)
    state = learner.refresh_subject_state(child.id, subject.id)

    rows = db.execute(
        select(LearnerConceptState, Concept)
        .join(Concept, Concept.id == LearnerConceptState.concept_id)
        .where(LearnerConceptState.child_id == child.id, Concept.subject_id == subject.id)
    ).all()

    def item(s, c):
        return {
            "concept": c.name, "dimension": str(s.dimension),
            "mastery": round(s.mastery_score, 3), "status": str(s.status),
            "attempts": s.attempt_count,
        }

    strong = sorted(
        [item(s, c) for s, c in rows if s.mastery_score >= CONFIG.mastery.developing],
        key=lambda d: d["mastery"], reverse=True,
    )[:10]
    learning_items = sorted(
        [item(s, c) for s, c in rows if CONFIG.mastery.introduced <= s.mastery_score < CONFIG.mastery.developing],
        key=lambda d: d["mastery"], reverse=True,
    )[:10]
    weak = sorted(
        [item(s, c) for s, c in rows if s.mastery_score < CONFIG.mastery.introduced and s.attempt_count > 0],
        key=lambda d: d["mastery"],
    )[:10]

    from app.adaptive.spaced_repetition import SpacedRepetitionScheduler
    sched = SpacedRepetitionScheduler()
    due = [item(s, c) for s, c in rows if sched.is_due(s.next_review_at)][:10]

    return LearnerStateOut(
        child=child.name,
        subject=subject.name,
        ability=round(state.ability, 3),
        vocabulary_estimate=state.vocabulary_estimate,
        strong=strong,
        learning=learning_items,
        weak=weak,
        due_for_review=due,
        next_recommended=(weak or learning_items or [None])[0],
    )


def _narrative(child, state, strongest, weakest, sessions: int, minutes: float) -> str:
    parts = []
    if state.vocabulary_estimate:
        parts.append(f"Estimated vocabulary around {state.vocabulary_estimate:,} words")
        if state.vocabulary_confidence:
            parts[-1] += f" (confidence {int(state.vocabulary_confidence * 100)}%)"
        parts[-1] += "."
    if strongest:
        parts.append(f"Strongest at {', '.join(strongest).lower()}.")
    if weakest:
        parts.append(f"{', '.join(weakest)} needs the most practice.")
    if sessions:
        parts.append(f"{sessions} session{'s' if sessions != 1 else ''} this week, {round(minutes)} minutes.")
    else:
        parts.append("No sessions yet this week.")
    return " ".join(parts) or "Not enough data yet."
