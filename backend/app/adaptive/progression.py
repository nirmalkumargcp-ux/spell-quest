"""Progression: vocabulary estimation, bands and milestones (spec §20–21, §28)."""
from __future__ import annotations

from dataclasses import dataclass

from app.adaptive.config import CONFIG, VocabularyConfig


@dataclass
class VocabularyEstimate:
    words: int
    confidence: float
    band: str


def estimate_vocabulary(
    *,
    mastered_concepts: int,
    developing_concepts: int,
    average_confidence: float,
    config: VocabularyConfig | None = None,
) -> VocabularyEstimate:
    """Translate concept-level mastery into a headline word count.

    The learner model still operates per concept (spec §21) — this is purely a
    communication device for the child and parent.
    """
    cfg = config or CONFIG.vocabulary
    # Developing concepts count partially: the child half-knows them.
    effective = mastered_concepts + 0.4 * developing_concepts
    words = int(round(effective * cfg.words_per_mastered_concept))

    # Confidence rises with both evidence quality and sample size.
    sample_factor = min(1.0, (mastered_concepts + developing_concepts) / 40.0)
    confidence = round(min(0.95, 0.35 * sample_factor + 0.65 * average_confidence * sample_factor), 3)

    return VocabularyEstimate(words=words, confidence=confidence, band=band_for(words, cfg))


def band_for(words: int, config: VocabularyConfig | None = None) -> str:
    cfg = config or CONFIG.vocabulary
    for low, high, label in cfg.bands:
        if low <= words < high:
            return label
    return cfg.bands[-1][2]


def next_band(words: int, config: VocabularyConfig | None = None) -> tuple[int, str] | None:
    """Target the child is working towards, e.g. (1500, '1,000–1,500')."""
    cfg = config or CONFIG.vocabulary
    for low, high, label in cfg.bands:
        if low <= words < high:
            return high, label
    return None
