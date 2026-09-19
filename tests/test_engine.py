from __future__ import annotations

import pytest

from evalharness.domain.models import Dataset, EvaluatorSpec
from evalharness.domain.results import Assertion, RunSummary, Status
from evalharness.engine.runner import evaluate_case, run_dataset
from evalharness.engine.scoring import weighted_score
from tests.helpers import make_case


def spec(kind: str, weight: float = 1.0, **config) -> EvaluatorSpec:
    return EvaluatorSpec(type=kind, weight=weight, config=config)


class TestScoring:
    def test_equal_weights_average(self):
        assertions = [
            Assertion(evaluator="a", passed=True, score=1.0, weight=1),
            Assertion(evaluator="b", passed=False, score=0.0, weight=1),
        ]
        assert weighted_score(assertions) == 0.5

    def test_weights_bias_the_mean(self):
        assertions = [
            Assertion(evaluator="a", passed=True, score=1.0, weight=3),
            Assertion(evaluator="b", passed=False, score=0.0, weight=1),
        ]
        assert weighted_score(assertions) == 0.75

    def test_zero_weight_assertion_is_ignored(self):
        assertions = [
            Assertion(evaluator="a", passed=True, score=1.0, weight=1),
            Assertion(evaluator="b", passed=False, score=0.0, weight=0),
        ]
        assert weighted_score(assertions) == 1.0

    def test_all_zero_weights_score_zero(self):
        assertions = [Assertion(evaluator="a", passed=True, score=1.0, weight=0)]
        assert weighted_score(assertions) == 0.0

    def test_empty_assertions_score_zero(self):
        assert weighted_score([]) == 0.0


class TestEvaluateCase:
    def test_passing_case(self):
        result = evaluate_case(make_case(expected="a", actual="a"))
        assert result.status is Status.PASSED
        assert result.score == 1.0

    def test_failing_case(self):
        result = evaluate_case(make_case(expected="a", actual="b"))
        assert result.status is Status.FAILED
        assert result.failed_assertions

    def test_score_exactly_at_threshold_passes(self):
        case = make_case(
            actual="a",
            threshold=0.5,
            evaluators=[spec("contains", values=["a"]), spec("contains", values=["zz"])],
        )
        result = evaluate_case(case)
        assert result.score == 0.5
        assert result.status is Status.PASSED

    def test_score_just_below_threshold_fails(self):
        case = make_case(
            actual="a",
            threshold=0.51,
            evaluators=[spec("contains", values=["a"]), spec("contains", values=["zz"])],
        )
        assert evaluate_case(case).status is Status.FAILED

    def test_zero_threshold_always_passes(self):
        case = make_case(expected="a", actual="b", threshold=0.0)
        assert evaluate_case(case).status is Status.PASSED

    def test_runtime_evaluator_error_marks_case_errored(self):
        case = make_case(actual="not json", evaluators=[spec("required_fields", fields=["a"])])
        result = evaluate_case(case)
        assert result.status is Status.ERRORED
        assert "required_fields" in result.error

    def test_errored_case_scores_zero(self):
        case = make_case(actual="x", evaluators=[spec("numeric_tolerance")], expected="y")
        assert evaluate_case(case).score == 0.0

    def test_error_stops_later_evaluators(self):
        case = make_case(
            expected="q",
            actual="no digits",
            evaluators=[spec("numeric_tolerance"), spec("exact_match")],
        )
        assert evaluate_case(case).assertions == []

    def test_tags_are_carried_into_result(self):
        assert evaluate_case(make_case(tags=["t"])).tags == ["t"]

    def test_duration_is_recorded(self):
        assert evaluate_case(make_case()).duration_ms >= 0.0

    def test_assertion_order_matches_spec_order(self):
        case = make_case(
            actual="a b",
            evaluators=[spec("contains", values=["a"]), spec("regex", pattern="b")],
        )
        assert [a.evaluator for a in evaluate_case(case).assertions] == ["contains", "regex"]


class TestRunDataset:
    def _dataset(self) -> Dataset:
        return Dataset(
            cases=[
                make_case(id="pass", expected="a", actual="a"),
                make_case(id="fail", expected="a", actual="b"),
                make_case(id="pass2", expected="c", actual="c"),
            ]
        )

    def test_counts(self):
        summary = run_dataset(self._dataset())
        assert (summary.total, summary.passed, summary.failed) == (3, 2, 1)

    def test_mean_score(self):
        assert run_dataset(self._dataset()).score == pytest.approx(2 / 3)

    def test_fail_fast_stops_at_first_failure(self):
        summary = run_dataset(self._dataset(), fail_fast=True)
        assert summary.total == 2
        assert summary.stopped_early

    def test_without_fail_fast_runs_everything(self):
        assert not run_dataset(self._dataset()).stopped_early

    def test_gate_fails_when_a_case_fails(self):
        assert not run_dataset(self._dataset()).meets_gate

    def test_gate_passes_when_all_pass(self):
        dataset = Dataset(cases=[make_case(id="a", expected="x", actual="x")])
        assert run_dataset(dataset).meets_gate

    def test_fail_under_gate_met(self):
        summary = run_dataset(self._dataset(), fail_under=0.6)
        assert summary.meets_gate

    def test_fail_under_gate_not_met(self):
        summary = run_dataset(self._dataset(), fail_under=0.9)
        assert not summary.meets_gate

    def test_errored_case_fails_gate_regardless_of_fail_under(self):
        dataset = Dataset(
            cases=[
                make_case(id="e", actual="x", evaluators=[spec("required_fields", fields=["a"])])
            ]
        )
        summary = run_dataset(dataset, fail_under=0.0)
        assert summary.errored == 1
        assert not summary.meets_gate

    def test_empty_summary_scores_zero(self):
        assert RunSummary().score == 0.0

    def test_payload_shape(self):
        payload = run_dataset(self._dataset()).to_payload()
        assert set(payload) == {"summary", "cases"}
        assert payload["summary"]["total"] == 3
        assert len(payload["cases"]) == 3
