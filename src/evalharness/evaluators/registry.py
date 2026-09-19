from __future__ import annotations

from typing import Any

from evalharness.evaluators.base import Evaluator, EvaluatorError
from evalharness.evaluators.composite import CompositeEvaluator
from evalharness.evaluators.exact import ExactMatchEvaluator
from evalharness.evaluators.fields import RequiredFieldsEvaluator
from evalharness.evaluators.json_schema import JsonSchemaEvaluator
from evalharness.evaluators.numeric import NumericToleranceEvaluator
from evalharness.evaluators.overlap import TokenOverlapEvaluator
from evalharness.evaluators.regex_eval import RegexEvaluator
from evalharness.evaluators.substring import ContainsEvaluator, NotContainsEvaluator

_REGISTRY: dict[str, type[Evaluator]] = {
    ContainsEvaluator.name: ContainsEvaluator,
    CompositeEvaluator.name: CompositeEvaluator,
    ExactMatchEvaluator.name: ExactMatchEvaluator,
    JsonSchemaEvaluator.name: JsonSchemaEvaluator,
    NotContainsEvaluator.name: NotContainsEvaluator,
    NumericToleranceEvaluator.name: NumericToleranceEvaluator,
    RegexEvaluator.name: RegexEvaluator,
    RequiredFieldsEvaluator.name: RequiredFieldsEvaluator,
    TokenOverlapEvaluator.name: TokenOverlapEvaluator,
}


def available_evaluators() -> list[str]:
    return sorted(_REGISTRY)


def build_evaluator(kind: str, config: dict[str, Any], *, depth: int = 0) -> Evaluator:
    try:
        factory = _REGISTRY[kind]
    except KeyError:
        raise EvaluatorError(
            f"unknown evaluator type {kind!r}; available: {', '.join(available_evaluators())}"
        ) from None
    if factory is CompositeEvaluator:
        return CompositeEvaluator(config, depth=depth)
    return factory(config)
