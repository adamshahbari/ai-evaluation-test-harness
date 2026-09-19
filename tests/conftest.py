from __future__ import annotations

from pathlib import Path

import pytest

from evalharness.domain.models import EvaluatorSpec, TestCase

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def make_case(**overrides) -> TestCase:
    payload = {
        "id": "case-1",
        "evaluators": [EvaluatorSpec(type="exact_match")],
        "expected": "hello",
        "actual": "hello",
    }
    payload.update(overrides)
    return TestCase(**payload)


@pytest.fixture
def case():
    return make_case


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def suite(tmp_path: Path):
    def _write(body: str, name: str = "suite.yaml") -> Path:
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        return path

    return _write
