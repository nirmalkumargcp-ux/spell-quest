"""Concrete evaluators, one per question type."""
from __future__ import annotations

from typing import Any

from app.adaptive.evaluation.base import AnswerEvaluator, EvaluationResult, register
from app.models.content import Question, QuestionType


class ChoiceEvaluator(AnswerEvaluator):
    """Multiple choice / image choice / true-false all compare against options."""

    question_type = QuestionType.multiple_choice

    def evaluate(self, question: Question, raw_answer: Any) -> EvaluationResult:
        given = self.normalize(raw_answer)
        correct_values = [self.normalize(o.value) for o in question.options if o.is_correct]
        # Answers may arrive as the option id rather than its value.
        correct_ids = [str(o.id) for o in question.options if o.is_correct]
        is_correct = given in correct_values or str(raw_answer) in correct_ids
        return EvaluationResult(
            is_correct=is_correct,
            normalized_answer=given,
            expected=correct_values[0] if correct_values else None,
        )


class ImageChoiceEvaluator(ChoiceEvaluator):
    question_type = QuestionType.image_choice


class TrueFalseEvaluator(ChoiceEvaluator):
    question_type = QuestionType.true_false


class SpellingEvaluator(AnswerEvaluator):
    """V1 is exact match after normalisation; the raw answer is preserved so
    typo/phonetic analysis (spec §26) can be added without a migration."""

    question_type = QuestionType.spelling

    def evaluate(self, question: Question, raw_answer: Any) -> EvaluationResult:
        expected = self.normalize(question.answer.get("value", ""))
        given = self.normalize(raw_answer)
        detail: dict[str, Any] = {}
        if not given == expected and expected:
            detail["error_kind"] = _classify_spelling_error(given, expected)
        return EvaluationResult(
            is_correct=given == expected,
            normalized_answer=given,
            expected=expected,
            detail=detail,
        )


class TextInputEvaluator(AnswerEvaluator):
    question_type = QuestionType.text_input

    def evaluate(self, question: Question, raw_answer: Any) -> EvaluationResult:
        expected = self.normalize(question.answer.get("value", ""))
        accepted = {expected} | {
            self.normalize(a) for a in question.answer.get("accepts", [])
        }
        given = self.normalize(raw_answer)
        return EvaluationResult(is_correct=given in accepted, normalized_answer=given, expected=expected)


class NumericEvaluator(AnswerEvaluator):
    question_type = QuestionType.numeric_input

    def evaluate(self, question: Question, raw_answer: Any) -> EvaluationResult:
        expected_raw = question.answer.get("value")
        tolerance = float(question.answer.get("tolerance", 0))
        try:
            given_num = float(str(raw_answer).strip())
            expected_num = float(expected_raw)
            is_correct = abs(given_num - expected_num) <= tolerance
        except (TypeError, ValueError):
            is_correct = False
        return EvaluationResult(
            is_correct=is_correct,
            normalized_answer=self.normalize(raw_answer),
            expected=str(expected_raw),
        )


class OrderingEvaluator(AnswerEvaluator):
    question_type = QuestionType.ordering

    def evaluate(self, question: Question, raw_answer: Any) -> EvaluationResult:
        expected = [self.normalize(v) for v in question.answer.get("value", [])]
        if isinstance(raw_answer, str):
            given = [self.normalize(v) for v in raw_answer.split(",")]
        else:
            given = [self.normalize(v) for v in (raw_answer or [])]
        return EvaluationResult(
            is_correct=given == expected,
            normalized_answer=",".join(given),
            expected=",".join(expected),
        )


class MatchingEvaluator(AnswerEvaluator):
    question_type = QuestionType.matching

    def evaluate(self, question: Question, raw_answer: Any) -> EvaluationResult:
        expected = {
            self.normalize(k): self.normalize(v)
            for k, v in (question.answer.get("value") or {}).items()
        }
        given = {
            self.normalize(k): self.normalize(v)
            for k, v in (raw_answer or {}).items()
        } if isinstance(raw_answer, dict) else {}
        return EvaluationResult(
            is_correct=given == expected,
            normalized_answer=str(sorted(given.items())),
            expected=str(sorted(expected.items())),
        )


class AudioResponseEvaluator(TextInputEvaluator):
    question_type = QuestionType.audio_response


def _classify_spelling_error(given: str, expected: str) -> str:
    """Cheap, useful signal for later analysis — not used for scoring in V1."""
    if not given:
        return "blank"
    if sorted(given) == sorted(expected):
        return "transposition"
    if len(given) == len(expected) - 1:
        return "omission"
    if len(given) == len(expected) + 1:
        return "insertion"
    if len(given) == len(expected):
        diffs = sum(1 for a, b in zip(given, expected) if a != b)
        if diffs == 1:
            return "substitution"
    return "other"


for _evaluator in (
    ChoiceEvaluator(), ImageChoiceEvaluator(), TrueFalseEvaluator(), SpellingEvaluator(),
    TextInputEvaluator(), NumericEvaluator(), OrderingEvaluator(), MatchingEvaluator(),
    AudioResponseEvaluator(),
):
    register(_evaluator)
