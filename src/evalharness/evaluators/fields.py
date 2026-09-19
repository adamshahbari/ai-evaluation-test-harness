from __future__ import annotations

from typing import Any

from evalharness.domain.models import TestCase
from evalharness.evaluators.base import Evaluator, EvaluatorError, Outcome, as_json

_MISSING = object()


def resolve_path(document: Any, path: str) -> Any:
    current = document
    for segment in path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                return _MISSING
            current = current[segment]
        elif isinstance(current, list):
            try:
                index = int(segment)
            except ValueError:
                return _MISSING
            if not -len(current) <= index < len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


class RequiredFieldsEvaluator(Evaluator):
    name = "required_fields"

    def validate_config(self) -> None:
        fields = self.option("fields", [])
        values = self.option("values", {})
        if not isinstance(fields, list) or not all(isinstance(item, str) for item in fields):
            raise EvaluatorError(f"{self.name}: 'fields' must be a list of strings")
        if not isinstance(values, dict):
            raise EvaluatorError(f"{self.name}: 'values' must be a mapping")
        if not fields and not values:
            raise EvaluatorError(f"{self.name}: provide at least one of 'fields' or 'values'")

    def evaluate(self, case: TestCase) -> Outcome:
        document = as_json(case.actual, field="actual")
        fields: list[str] = self.option("fields", [])
        values: dict[str, Any] = self.option("values", {})

        checks = 0
        problems: list[str] = []

        for path in fields:
            checks += 1
            if resolve_path(document, path) is _MISSING:
                problems.append(f"missing field '{path}'")

        for path, expected in values.items():
            checks += 1
            found = resolve_path(document, path)
            if found is _MISSING:
                problems.append(f"missing field '{path}'")
            elif found != expected:
                problems.append(f"'{path}' expected {expected!r}, got {found!r}")

        if not problems:
            return Outcome.hit(f"all {checks} field check(s) satisfied")
        score = (checks - len(problems)) / checks
        return Outcome(score, "; ".join(problems))
