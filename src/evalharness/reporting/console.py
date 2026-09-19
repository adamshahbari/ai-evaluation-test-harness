from __future__ import annotations

from evalharness.domain.results import RunSummary, Status

_MARK = {Status.PASSED: "PASS", Status.FAILED: "FAIL", Status.ERRORED: "ERROR"}


def render(summary: RunSummary, *, verbose: bool = False) -> str:
    lines: list[str] = []

    for result in summary.results:
        lines.append(
            f"{_MARK[result.status]:<5}  {result.case_id}  "
            f"score={result.score:.3f} threshold={result.threshold:.3f} "
            f"({result.duration_ms:.1f}ms)"
        )
        if result.error:
            lines.append(f"       error: {result.error}")
        shown = result.assertions if verbose else result.failed_assertions
        for assertion in shown:
            mark = "ok" if assertion.passed else "xx"
            lines.append(
                f"       [{mark}] {assertion.evaluator} "
                f"score={assertion.score:.3f} weight={assertion.weight:g}"
                + (f" - {assertion.detail}" if assertion.detail else "")
            )

    if summary.stopped_early:
        lines.append("")
        lines.append("Stopped early after first failure (--fail-fast).")

    lines.append("")
    lines.append(
        f"{summary.total} case(s): {summary.passed} passed, "
        f"{summary.failed} failed, {summary.errored} errored"
    )
    lines.append(f"Mean score: {summary.score:.3f}")
    if summary.fail_under is not None:
        verdict = "met" if summary.score >= summary.fail_under else "NOT met"
        lines.append(f"Gate --fail-under {summary.fail_under:.3f}: {verdict}")
    lines.append(f"Duration: {summary.duration_ms:.1f}ms")
    return "\n".join(lines)
