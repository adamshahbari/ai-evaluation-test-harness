from __future__ import annotations

import math
import re

from evalharness.domain.models import TestCase
from evalharness.evaluators.base import Evaluator, EvaluatorError, Outcome, as_text

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def extract_number(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise EvaluatorError(f"{field} is a boolean, not a number")
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER.search(as_text(value).replace(",", ""))
    if not match:
        raise EvaluatorError(f"no number found in {field}")
    return float(match.group(0))


class NumericToleranceEvaluator(Evaluator):
    name = "numeric_tolerance"

    def validate_config(self) -> None:
        mode = self.option("mode", "absolute")
        if mode not in {"absolute", "relative"}:
            raise EvaluatorError(
                f"{self.name}: mode must be 'absolute' or 'relative', got {mode!r}"
            )
        tolerance = self.option("tolerance", 0.0)
        if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool):
            raise EvaluatorError(f"{self.name}: 'tolerance' must be numeric")
        if tolerance < 0:
            raise EvaluatorError(f"{self.name}: 'tolerance' must not be negative")

    def evaluate(self, case: TestCase) -> Outcome:
        expected = extract_number(case.expected, field="expected")
        actual = extract_number(case.actual, field="actual")
        tolerance = float(self.option("tolerance", 0.0))
        mode = self.option("mode", "absolute")

        if mode == "relative":
            if expected == 0:
                # A relative tolerance around zero has no meaningful denominator,
                # so the comparison degrades to an exact one rather than dividing.
                delta = abs(actual)
                within = delta <= tolerance
                return (
                    Outcome.hit(f"actual {actual} within {tolerance} of zero")
                    if within
                    else Outcome.miss(f"expected 0, got {actual} (relative tolerance undefined)")
                )
            delta = abs(actual - expected) / abs(expected)
        else:
            delta = abs(actual - expected)

        if math.isnan(delta):
            return Outcome.miss("comparison produced NaN")
        # abs(1.1 - 1.0) is 0.1000000000000000888, so a bare <= would reject a
        # difference that is exactly the stated tolerance in decimal terms.
        if delta <= tolerance or math.isclose(delta, tolerance, rel_tol=1e-9, abs_tol=1e-12):
            return Outcome.hit(f"{actual} within {mode} tolerance {tolerance} of {expected}")
        return Outcome.miss(
            f"{actual} differs from {expected} by {delta:.6g} ({mode} tolerance {tolerance})"
        )
