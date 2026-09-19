from __future__ import annotations

from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from evalharness.domain.models import TestCase
from evalharness.evaluators.base import Evaluator, EvaluatorError, Outcome, as_json


class JsonSchemaEvaluator(Evaluator):
    name = "json_schema"

    def validate_config(self) -> None:
        schema = self.required("schema")
        if not isinstance(schema, dict):
            raise EvaluatorError(f"{self.name}: 'schema' must be a mapping")
        try:
            Draft202012Validator.check_schema(schema)
        except jsonschema.SchemaError as exc:
            raise EvaluatorError(f"{self.name}: invalid JSON Schema: {exc.message}") from exc

    def evaluate(self, case: TestCase) -> Outcome:
        document: Any = as_json(case.actual, field="actual")
        validator = Draft202012Validator(self.config["schema"])
        errors = sorted(validator.iter_errors(document), key=lambda err: list(err.absolute_path))
        if not errors:
            return Outcome.hit("document satisfies schema")

        summaries = []
        for error in errors[:3]:
            location = "/".join(str(part) for part in error.absolute_path) or "<root>"
            summaries.append(f"{location}: {error.message}")
        suffix = f" (+{len(errors) - 3} more)" if len(errors) > 3 else ""
        return Outcome.miss("; ".join(summaries) + suffix)
