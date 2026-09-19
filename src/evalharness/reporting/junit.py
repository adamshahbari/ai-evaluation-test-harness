from __future__ import annotations

from xml.etree import ElementTree as ET

from evalharness.domain.results import RunSummary, Status


def render(summary: RunSummary) -> str:
    suite = ET.Element(
        "testsuite",
        {
            "name": "evalharness",
            "tests": str(summary.total),
            "failures": str(summary.failed),
            "errors": str(summary.errored),
            "time": f"{summary.duration_ms / 1000:.3f}",
        },
    )

    for result in summary.results:
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "name": result.case_id,
                "classname": "evalharness.case",
                "time": f"{result.duration_ms / 1000:.3f}",
            },
        )
        if result.status is Status.ERRORED:
            error = ET.SubElement(case, "error", {"message": result.error or "evaluator error"})
            error.text = result.error or ""
        elif result.status is Status.FAILED:
            detail = (
                "; ".join(f"{a.evaluator}: {a.detail}" for a in result.failed_assertions)
                or "score below threshold"
            )
            failure = ET.SubElement(
                case,
                "failure",
                {"message": f"score {result.score:.3f} < threshold {result.threshold:.3f}"},
            )
            failure.text = detail

    ET.indent(suite, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(suite, encoding="unicode")
