from __future__ import annotations

from evalharness.domain.models import TestCase
from evalharness.evaluators.base import Evaluator, EvaluatorError, Outcome, as_text


def _terms(raw: object, *, field: str) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        if not raw:
            raise EvaluatorError(f"'{field}' must not be an empty list")
        return list(raw)
    raise EvaluatorError(f"'{field}' must be a string or a list of strings")


class ContainsEvaluator(Evaluator):
    name = "contains"

    def validate_config(self) -> None:
        _terms(self.required("values"), field="values")
        mode = self.option("mode", "all")
        if mode not in {"all", "any"}:
            raise EvaluatorError(f"{self.name}: mode must be 'all' or 'any', got {mode!r}")

    def evaluate(self, case: TestCase) -> Outcome:
        values = _terms(self.config["values"], field="values")
        ignore_case = bool(self.option("ignore_case", False))
        haystack = as_text(case.actual)
        if ignore_case:
            haystack = haystack.casefold()
            values = [value.casefold() for value in values]

        found = [value for value in values if value in haystack]
        missing = [value for value in values if value not in haystack]

        if self.option("mode", "all") == "any":
            if found:
                return Outcome.hit(f"found {found[0]!r}")
            return Outcome.miss(f"none of {values!r} present in actual")

        if not missing:
            return Outcome.hit(f"all {len(values)} term(s) present")
        return Outcome(len(found) / len(values), f"missing {missing!r}")


class NotContainsEvaluator(Evaluator):
    name = "not_contains"

    def validate_config(self) -> None:
        _terms(self.required("values"), field="values")

    def evaluate(self, case: TestCase) -> Outcome:
        values = _terms(self.config["values"], field="values")
        ignore_case = bool(self.option("ignore_case", False))
        haystack = as_text(case.actual)
        if ignore_case:
            haystack = haystack.casefold()
            values = [value.casefold() for value in values]

        present = [value for value in values if value in haystack]
        if not present:
            return Outcome.hit(f"none of {len(values)} forbidden term(s) present")
        return Outcome.miss(f"forbidden term(s) present: {present!r}")
