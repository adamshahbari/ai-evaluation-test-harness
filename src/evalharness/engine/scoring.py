from __future__ import annotations

from evalharness.domain.results import Assertion


def weighted_score(assertions: list[Assertion]) -> float:
    """Weighted mean of assertion scores.

    Zero-weight assertions still report a score but contribute nothing, which is
    how an evaluator is kept visible in reports without gating the case.
    """
    total_weight = sum(assertion.weight for assertion in assertions)
    if total_weight == 0:
        return 0.0
    return sum(assertion.weighted_score for assertion in assertions) / total_weight
