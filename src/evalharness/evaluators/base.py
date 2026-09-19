from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from evalharness.domain.models import TestCase


class EvaluatorError(Exception):
    """Raised when an evaluator is misconfigured or cannot run."""


class Outcome:
    __slots__ = ("detail", "score")

    def __init__(self, score: float, detail: str = "") -> None:
        if not 0.0 <= score <= 1.0:
            raise EvaluatorError(f"evaluator produced out-of-range score {score}")
        self.score = score
        self.detail = detail

    @classmethod
    def hit(cls, detail: str = "") -> Outcome:
        return cls(1.0, detail)

    @classmethod
    def miss(cls, detail: str) -> Outcome:
        return cls(0.0, detail)


class Evaluator(ABC):
    name: str

    #: Graded evaluators lower this so a partial score can still pass.
    default_min_score: float = 1.0

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._check_min_score()
        self.validate_config()

    def _check_min_score(self) -> None:
        raw = self.config.get("min_score", self.default_min_score)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise EvaluatorError(f"{self.name}: 'min_score' must be numeric")
        if not 0.0 <= float(raw) <= 1.0:
            raise EvaluatorError(f"{self.name}: 'min_score' must be between 0.0 and 1.0")

    @property
    def min_score(self) -> float:
        return float(self.config.get("min_score", self.default_min_score))

    def passes(self, score: float) -> bool:
        return score >= self.min_score

    def validate_config(self) -> None:
        return None

    @abstractmethod
    def evaluate(self, case: TestCase) -> Outcome: ...

    def option(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def required(self, key: str) -> Any:
        if key not in self.config:
            raise EvaluatorError(f"{self.name}: missing required option '{key}'")
        return self.config[key]


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def as_json(value: Any, *, field: str) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = as_text(value).strip()
    if not text:
        raise EvaluatorError(f"{field} is empty and cannot be parsed as JSON")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise EvaluatorError(f"{field} is not valid JSON: {exc.msg}") from exc


def normalise(text: str, *, ignore_case: bool, strip: bool, collapse_whitespace: bool) -> str:
    result = text
    if ignore_case:
        result = result.casefold()
    if collapse_whitespace:
        result = " ".join(result.split())
    if strip:
        result = result.strip()
    return result
