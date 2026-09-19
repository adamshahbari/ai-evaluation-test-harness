from __future__ import annotations

from evalharness.domain.models import EvaluatorSpec, TestCase


def make_case(**overrides) -> TestCase:
    payload = {
        "id": "case-1",
        "evaluators": [EvaluatorSpec(type="exact_match")],
        "expected": "hello",
        "actual": "hello",
    }
    payload.update(overrides)
    return TestCase(**payload)
