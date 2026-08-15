"""Seed the database with the English curriculum.

Every word becomes one Concept and four Questions — one per knowledge
dimension — so the engine can discover that a child recognises a word but
cannot spell it (spec §22).
"""
from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Concept, Milestone, MilestoneKind, Question, QuestionOption, QuestionType, Skill, Subject,
)
from app.models.learner import Dimension
from app.seed.data.english import MILESTONES, PREREQUISITES, SKILL_TREE, WORDS

settings = get_settings()

# Question difficulty is the concept difficulty shifted by how demanding the
# dimension is: spotting a picture is easier than spelling from memory.
DIMENSION_OFFSET = {
    Dimension.recognition: -0.18,
    Dimension.meaning: -0.05,
    Dimension.context: +0.05,
    Dimension.spelling: +0.15,
}

DIMENSION_SKILL = {
    Dimension.recognition: "recognition",
    Dimension.meaning: "meaning",
    Dimension.context: "context",
}


def media_for(word: str) -> dict:
    base = settings.media_base_url.rstrip("/")
    return {"image": f"{base}/images/{word}.jpg", "audio": f"{base}/audio/{word}.m4a", "plate": None}


def seed_all(db: Session, *, reset: bool = False) -> dict[str, int]:
    if reset:
        for model in (QuestionOption, Question, Concept, Skill, Subject, Milestone):
            db.query(model).delete()
        db.flush()

    if db.scalar(select(Subject).where(Subject.slug == "english")):
        return {"skipped": 1}

    rng = random.Random(20260815)   # deterministic seed content

    subject = Subject(
        slug=SKILL_TREE["slug"], name=SKILL_TREE["name"],
        icon=SKILL_TREE["icon"], display_order=0,
        description="Vocabulary, meaning, using words and spelling.",
    )
    db.add(subject)
    db.flush()

    # -- skills ------------------------------------------------------------
    skills: dict[str, Skill] = {}
    for order, node in enumerate(SKILL_TREE["skills"]):
        parent = Skill(
            subject_id=subject.id, slug=node["slug"], name=node["name"],
            child_name=node["child_name"], level=0, display_order=order,
        )
        db.add(parent)
        db.flush()
        skills[node["slug"]] = parent
        for child_order, child in enumerate(node.get("children", [])):
            sk = Skill(
                subject_id=subject.id, parent_skill_id=parent.id, slug=child["slug"],
                name=child["name"], child_name=child["child_name"], level=1, display_order=child_order,
            )
            db.add(sk)
            db.flush()
            skills[child["slug"]] = sk

    # -- concepts ----------------------------------------------------------
    concepts: dict[str, Concept] = {}
    for word, meaning, sentence, band, difficulty in WORDS:
        concept = Concept(
            subject_id=subject.id,
            primary_skill_id=skills["vocabulary"].id,
            slug=word, name=word, description=meaning,
            difficulty=difficulty, frequency_band=band,
            media=media_for(word),
            meta={"sentence": sentence},
        )
        concept.skills = [skills["vocabulary"], skills["spelling"]]
        db.add(concept)
        db.flush()
        concepts[word] = concept

    for word, prereqs in PREREQUISITES.items():
        if word in concepts:
            concepts[word].prerequisites = [concepts[p] for p in prereqs if p in concepts]
    db.flush()

    # -- questions ---------------------------------------------------------
    all_words = [w[0] for w in WORDS]
    by_band: dict[int, list[str]] = {}
    for word, _, _, band, _ in WORDS:
        by_band.setdefault(band, []).append(word)
    meanings = {w: m for w, m, _, _, _ in WORDS}

    def distractors(word: str, band: int, n: int) -> list[str]:
        """Prefer same-band words so the wrong answers are plausible."""
        pool = [w for w in by_band.get(band, []) if w != word]
        if len(pool) < n:
            pool += [w for w in all_words if w != word and w not in pool]
        return rng.sample(pool, min(n, len(pool)))

    question_count = 0
    for word, meaning, sentence, band, difficulty in WORDS:
        concept = concepts[word]
        media = media_for(word)

        for dimension in Dimension:
            diff = max(0.05, min(0.95, difficulty + DIMENSION_OFFSET[dimension]))
            skill = skills[DIMENSION_SKILL.get(dimension, "spelling")] if dimension is not Dimension.spelling else (
                skills["simple-words"] if len(word) <= 5 else skills["word-patterns"]
            )

            if dimension is Dimension.recognition:
                q = Question(
                    subject_id=subject.id, skill_id=skill.id, concept_id=concept.id,
                    question_type=QuestionType.image_choice, difficulty=diff,
                    prompt=f"Which one is the {word}?",
                    answer={"value": word},
                    media={"audio": media["audio"]},
                    hints=[{"level": 1, "text": f"It starts with the sound '{word[0]}'."}],
                    meta={"dimension": dimension.value},
                    age_min=4, age_max=8,
                )
                db.add(q); db.flush()
                choices = [word] + distractors(word, band, 3)
                rng.shuffle(choices)
                for i, choice in enumerate(choices):
                    db.add(QuestionOption(
                        question_id=q.id, value=choice, label=choice,
                        media={"image": media_for(choice)["image"]},
                        is_correct=(choice == word), display_order=i,
                    ))

            elif dimension is Dimension.meaning:
                q = Question(
                    subject_id=subject.id, skill_id=skill.id, concept_id=concept.id,
                    question_type=QuestionType.multiple_choice, difficulty=diff,
                    prompt=f"What does “{word}” mean?",
                    answer={"value": meaning},
                    explanation=f"{word.capitalize()} means {meaning}.",
                    media={"audio": media["audio"], "image": media["image"]},
                    hints=[{"level": 1, "text": "Picture the word in your head."}],
                    meta={"dimension": dimension.value},
                    age_min=4, age_max=10,
                )
                db.add(q); db.flush()
                choices = [meaning] + [meanings[d] for d in distractors(word, band, 2)]
                rng.shuffle(choices)
                for i, choice in enumerate(choices):
                    db.add(QuestionOption(
                        question_id=q.id, value=choice, label=choice,
                        is_correct=(choice == meaning), display_order=i,
                    ))

            elif dimension is Dimension.context:
                q = Question(
                    subject_id=subject.id, skill_id=skill.id, concept_id=concept.id,
                    question_type=QuestionType.multiple_choice, difficulty=diff,
                    prompt=f"Which word fits? {sentence}",
                    answer={"value": word},
                    explanation=sentence.replace("___", word),
                    media={"audio": media["audio"]},
                    hints=[{"level": 1, "text": "Read the sentence again slowly."}],
                    meta={"dimension": dimension.value},
                    age_min=5, age_max=10,
                )
                db.add(q); db.flush()
                choices = [word] + distractors(word, band, 2)
                rng.shuffle(choices)
                for i, choice in enumerate(choices):
                    db.add(QuestionOption(
                        question_id=q.id, value=choice, label=choice,
                        is_correct=(choice == word), display_order=i,
                    ))

            else:  # spelling
                q = Question(
                    subject_id=subject.id, skill_id=skill.id, concept_id=concept.id,
                    question_type=QuestionType.spelling, difficulty=diff,
                    prompt="Spell the word you hear",
                    answer={"value": word},
                    explanation=f"{word} — {meaning}.",
                    media={"audio": media["audio"], "image": media["image"]},
                    hints=[
                        {"level": 1, "text": f"It starts with the sound '{word[0]}'."},
                        {"level": 2, "text": f"The word starts with {word[0].upper()}."},
                        {"level": 3, "text": word[0].upper() + " " + " ".join("_" * (len(word) - 1))},
                    ],
                    meta={"dimension": dimension.value, "letters": len(word)},
                    age_min=5, age_max=10,
                )
                db.add(q); db.flush()

            question_count += 1

    # -- milestones --------------------------------------------------------
    for order, (slug, name, kind, threshold, icon) in enumerate(MILESTONES):
        db.add(Milestone(
            subject_id=subject.id, slug=slug, name=name,
            kind=MilestoneKind(kind), threshold=float(threshold),
            display_order=order, icon=icon,
        ))

    db.flush()
    return {
        "subjects": 1,
        "skills": len(skills),
        "concepts": len(concepts),
        "questions": question_count,
        "milestones": len(MILESTONES),
    }


if __name__ == "__main__":
    from app.db import SessionLocal, engine
    from app.models import Base

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        result = seed_all(session)
        session.commit()
        print("seeded:", result)
