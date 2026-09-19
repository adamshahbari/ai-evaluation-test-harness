from __future__ import annotations

from evalharness.domain.models import TestCase
from evalharness.evaluators.base import Evaluator, Outcome, as_text, normalise


class ExactMatchEvaluator(Evaluator):
    name = "exact_match"

    def evaluate(self, case: TestCase) -> Outcome:
        options = {
            "ignore_case": bool(self.option("ignore_case", False)),
            "strip": bool(self.option("strip", True)),
            "collapse_whitespace": bool(self.option("collapse_whitespace", False)),
        }
        expected = normalise(as_text(case.expected), **options)
        actual = normalise(as_text(case.actual), **options)
        if expected == actual:
            return Outcome.hit("actual matches expected")
        return Outcome.miss(f"expected {expected!r}, got {actual!r}")
