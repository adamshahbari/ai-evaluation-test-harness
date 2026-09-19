from __future__ import annotations

import time

from evalharness.domain.models import Dataset, TestCase
from evalharness.domain.results import Assertion, EvaluationResult, RunSummary, Status
from evalharness.engine.scoring import weighted_score
from evalharness.evaluators.base import EvaluatorError
from evalharness.evaluators.registry import build_evaluator


def evaluate_case(case: TestCase) -> EvaluationResult:
    started = time.perf_counter()
    assertions: list[Assertion] = []

    for spec in case.evaluators:
        try:
            evaluator = build_evaluator(spec.type, spec.config)
            outcome = evaluator.evaluate(case)
        except EvaluatorError as exc:
            return EvaluationResult(
                case_id=case.id,
                status=Status.ERRORED,
                score=0.0,
                threshold=case.threshold,
                duration_ms=(time.perf_counter() - started) * 1000,
                assertions=assertions,
                tags=case.tags,
                error=f"{spec.type}: {exc}",
            )
        assertions.append(
            Assertion(
                evaluator=spec.type,
                passed=evaluator.passes(outcome.score),
                score=outcome.score,
                weight=spec.weight,
                detail=outcome.detail,
            )
        )

    score = weighted_score(assertions)
    status = Status.PASSED if score >= case.threshold else Status.FAILED
    return EvaluationResult(
        case_id=case.id,
        status=status,
        score=score,
        threshold=case.threshold,
        duration_ms=(time.perf_counter() - started) * 1000,
        assertions=assertions,
        tags=case.tags,
    )


def run_dataset(
    dataset: Dataset,
    *,
    fail_fast: bool = False,
    fail_under: float | None = None,
) -> RunSummary:
    started = time.perf_counter()
    results: list[EvaluationResult] = []
    stopped_early = False

    for case in dataset:
        result = evaluate_case(case)
        results.append(result)
        if fail_fast and result.status is not Status.PASSED:
            stopped_early = True
            break

    return RunSummary(
        results=results,
        duration_ms=(time.perf_counter() - started) * 1000,
        fail_under=fail_under,
        stopped_early=stopped_early,
    )
