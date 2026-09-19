"""The bundled suites are documentation; these tests keep them honest."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from evalharness.cli import app
from evalharness.engine.runner import run_dataset
from evalharness.exit_codes import ExitCode
from evalharness.loading.loader import load_dataset

runner = CliRunner()

SUITES = [
    "support-quality",
    "json-extraction",
    "policy-regression",
    "classification",
    "numeric-answers",
]


@pytest.mark.parametrize("name", SUITES)
def test_each_example_suite_loads(examples_dir, name):
    assert len(load_dataset(examples_dir / name)) >= 1


@pytest.mark.parametrize("name", SUITES)
def test_each_example_suite_passes(examples_dir, name):
    summary = run_dataset(load_dataset(examples_dir / name))
    assert summary.meets_gate, f"{name}: {summary.failed} failed, {summary.errored} errored"


def test_all_examples_run_clean(examples_dir):
    summary = run_dataset(load_dataset(examples_dir))
    assert summary.errored == 0
    assert summary.failed == 0


def test_examples_exit_zero_through_cli(examples_dir):
    assert runner.invoke(app, ["run", str(examples_dir)]).exit_code == ExitCode.SUCCESS


def test_examples_have_unique_ids(examples_dir):
    dataset = load_dataset(examples_dir)
    ids = [case.id for case in dataset]
    assert len(ids) == len(set(ids))


def test_examples_exercise_every_evaluator(examples_dir):
    """A bundled example for each evaluator keeps the docs from drifting."""
    from evalharness.evaluators.registry import available_evaluators

    used: set[str] = set()

    def collect(config: dict) -> None:
        for child in config.get("evaluators", []):
            used.add(child["type"])
            collect(child.get("config", {}))

    for case in load_dataset(examples_dir):
        for spec in case.evaluators:
            used.add(spec.type)
            if spec.type == "composite":
                collect(spec.config)

    assert used == set(available_evaluators()), (
        f"not demonstrated: {set(available_evaluators()) - used}"
    )


def test_regressed_output_is_detected(examples_dir, tmp_path):
    """Flipping a recorded output must turn the run red."""
    source = (examples_dir / "policy-regression" / "refund-policy.yaml").read_text()
    regressed = source.replace(
        'actual: "The refund for order 8812 has been approved and will be processed."',
        'actual: "The refund for order 8812 has not been approved."',
    )
    assert regressed != source
    target = tmp_path / "regressed.yaml"
    target.write_text(regressed, encoding="utf-8")

    result = runner.invoke(app, ["run", str(target)])
    assert result.exit_code == ExitCode.EVALUATION_FAILED


def test_token_overlap_alone_would_miss_the_regression(examples_dir, tmp_path):
    """Justifies pairing token_overlap with a negation-sensitive check."""
    body = """
cases:
  - id: overlap-only
    expected: "The refund for order 8812 has been approved."
    actual: "The refund for order 8812 has not been approved."
    threshold: 0.8
    evaluators:
      - type: token_overlap
        config: {method: f1, min_score: 0.8}
"""
    target = tmp_path / "overlap-only.yaml"
    target.write_text(body, encoding="utf-8")
    summary = run_dataset(load_dataset(target))
    assert summary.meets_gate, "expected lexical overlap to miss the negation"


class TestCiFixtures:
    """These fixtures back assertions in the CI workflow; keep them in sync."""

    FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"

    def test_regressed_fixture_exits_one(self):
        result = runner.invoke(app, ["run", str(self.FIXTURES / "regressed.yaml")])
        assert result.exit_code == ExitCode.EVALUATION_FAILED

    def test_broken_fixture_exits_three(self):
        result = runner.invoke(app, ["run", str(self.FIXTURES / "broken.yaml")])
        assert result.exit_code == ExitCode.INVALID_DATASET

    def test_the_two_fixtures_exit_differently(self):
        regressed = runner.invoke(app, ["run", str(self.FIXTURES / "regressed.yaml")]).exit_code
        broken = runner.invoke(app, ["run", str(self.FIXTURES / "broken.yaml")]).exit_code
        assert regressed != broken
