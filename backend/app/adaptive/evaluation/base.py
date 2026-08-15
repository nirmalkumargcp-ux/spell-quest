"""Answer evaluation (spec §26).

Evaluators register themselves against a QuestionType. Nothing else in the
codebase switches on question type — adding a type means adding a module.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models.content import Question, QuestionType


@dataclass
class EvaluationResult:
    is_correct: bool
    normalized_answer: str
    expected: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class AnswerEvaluator(ABC):
    question_type: QuestionType

    @abstractmethod
    def evaluate(self, question: Question, raw_answer: Any) -> EvaluationResult: ...

    @staticmethod
    def normalize(value: Any) -> str:
        """Case and whitespace normalisation — the V1 baseline in the spec."""
        return " ".join(str(value or "").strip().lower().split())


_REGISTRY: dict[QuestionType, AnswerEvaluator] = {}


def register(evaluator: AnswerEvaluator) -> AnswerEvaluator:
    _REGISTRY[evaluator.question_type] = evaluator
    return evaluator


def get_evaluator(question_type: QuestionType | str) -> AnswerEvaluator:
    key = QuestionType(question_type) if isinstance(question_type, str) else question_type
    if key not in _REGISTRY:
        raise KeyError(f"No evaluator registered for question type {key!r}")
    return _REGISTRY[key]


def evaluate_answer(question: Question, raw_answer: Any) -> EvaluationResult:
    return get_evaluator(question.question_type).evaluate(question, raw_answer)
