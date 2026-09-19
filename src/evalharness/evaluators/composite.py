from __future__ import annotations

from typing import Any

from evalharness.domain.models import TestCase
from evalharness.evaluators.base import Evaluator, EvaluatorError, Outcome

MAX_DEPTH = 5


class CompositeEvaluator(Evaluator):
    """Combines child evaluators under all / any / weighted semantics."""

    name = "composite"

    def __init__(self, config: dict[str, Any] | None = None, *, depth: int = 0) -> None:
        self._depth = depth
        super().__init__(config)

    def validate_config(self) -> None:
        if self._depth >= MAX_DEPTH:
            raise EvaluatorError(
                f"{self.name}: nesting deeper than {MAX_DEPTH} levels is not supported"
            )
        mode = self.option("mode", "weighted")
        if mode not in {"all", "any", "weighted"}:
            raise EvaluatorError(
                f"{self.name}: mode must be 'all', 'any' or 'weighted', got {mode!r}"
            )
        children = self.required("evaluators")
        if not isinstance(children, list) or not children:
            raise EvaluatorError(f"{self.name}: 'evaluators' must be a non-empty list")
        self._children = [self._build(child) for child in children]
        if mode == "weighted" and all(weight == 0 for _, weight in self._children):
            raise EvaluatorError(f"{self.name}: child weights must not all be zero")

    def _build(self, spec: Any) -> tuple[Evaluator, float]:
        from evalharness.evaluators.registry import build_evaluator

        if not isinstance(spec, dict):
            raise EvaluatorError(f"{self.name}: each child must be a mapping")
        kind = spec.get("type")
        if not isinstance(kind, str) or not kind.strip():
            raise EvaluatorError(f"{self.name}: each child needs a 'type'")
        weight = spec.get("weight", 1.0)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise EvaluatorError(f"{self.name}: child 'weight' must be numeric")
        if weight < 0:
            raise EvaluatorError(f"{self.name}: child 'weight' must not be negative")
        config = spec.get("config", {})
        if not isinstance(config, dict):
            raise EvaluatorError(f"{self.name}: child 'config' must be a mapping")
        return build_evaluator(kind, config, depth=self._depth + 1), float(weight)

    def evaluate(self, case: TestCase) -> Outcome:
        mode = self.option("mode", "weighted")
        scores: list[tuple[str, float, float, bool]] = []
        for child, weight in self._children:
            outcome = child.evaluate(case)
            scores.append((child.name, outcome.score, weight, child.passes(outcome.score)))

        if mode == "all":
            passed = all(item[3] for item in scores)
            failing = [item[0] for item in scores if not item[3]]
            return (
                Outcome.hit(f"all {len(scores)} child evaluator(s) passed")
                if passed
                else Outcome.miss(f"child evaluator(s) failed: {failing}")
            )

        if mode == "any":
            winners = [item[0] for item in scores if item[3]]
            return (
                Outcome.hit(f"child evaluator(s) passed: {winners}")
                if winners
                else Outcome.miss(f"no child evaluator passed ({[i[0] for i in scores]})")
            )

        total_weight = sum(item[2] for item in scores)
        weighted = sum(item[1] * item[2] for item in scores) / total_weight
        breakdown = ", ".join(f"{name}={score:.3f}*{weight:g}" for name, score, weight, _ in scores)
        return Outcome(weighted, f"weighted {weighted:.3f} [{breakdown}]")
