from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"


class Assertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator: str
    passed: bool
    score: float
    weight: float
    detail: str = ""

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    status: Status
    score: float
    threshold: float
    duration_ms: float
    assertions: list[Assertion] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.status is Status.PASSED

    @property
    def failed_assertions(self) -> list[Assertion]:
        return [assertion for assertion in self.assertions if not assertion.passed]


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[EvaluationResult] = Field(default_factory=list)
    duration_ms: float = 0.0
    fail_under: float | None = None
    stopped_early: bool = False

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for result in self.results if result.status is Status.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for result in self.results if result.status is Status.FAILED)

    @property
    def errored(self) -> int:
        return sum(1 for result in self.results if result.status is Status.ERRORED)

    @property
    def score(self) -> float:
        if not self.results:
            return 0.0
        return sum(result.score for result in self.results) / len(self.results)

    @property
    def meets_gate(self) -> bool:
        if self.errored:
            return False
        if self.fail_under is not None:
            return self.score >= self.fail_under
        return self.failed == 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "errored": self.errored,
                "score": round(self.score, 6),
                "duration_ms": round(self.duration_ms, 3),
                "fail_under": self.fail_under,
                "stopped_early": self.stopped_early,
                "meets_gate": self.meets_gate,
            },
            "cases": [
                {
                    "id": result.case_id,
                    "status": str(result.status),
                    "score": round(result.score, 6),
                    "threshold": result.threshold,
                    "duration_ms": round(result.duration_ms, 3),
                    "tags": result.tags,
                    "error": result.error,
                    "assertions": [
                        {
                            "evaluator": assertion.evaluator,
                            "passed": assertion.passed,
                            "score": round(assertion.score, 6),
                            "weight": assertion.weight,
                            "detail": assertion.detail,
                        }
                        for assertion in result.assertions
                    ],
                }
                for result in self.results
            ],
        }
