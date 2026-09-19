from __future__ import annotations

import re

from evalharness.domain.models import TestCase
from evalharness.evaluators.base import Evaluator, EvaluatorError, Outcome, as_text

_FLAGS = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
}


class RegexEvaluator(Evaluator):
    name = "regex"

    def validate_config(self) -> None:
        pattern = self.required("pattern")
        if not isinstance(pattern, str):
            raise EvaluatorError(f"{self.name}: 'pattern' must be a string")
        try:
            re.compile(pattern, self._flags())
        except re.error as exc:
            raise EvaluatorError(f"{self.name}: invalid pattern: {exc}") from exc
        mode = self.option("mode", "search")
        if mode not in {"search", "fullmatch"}:
            raise EvaluatorError(f"{self.name}: mode must be 'search' or 'fullmatch', got {mode!r}")

    def _flags(self) -> int:
        raw = self.option("flags", [])
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            raise EvaluatorError(f"{self.name}: 'flags' must be a string or list of strings")
        flags = 0
        for item in raw:
            key = str(item).upper()
            if key not in _FLAGS:
                raise EvaluatorError(f"{self.name}: unknown flag {item!r}")
            flags |= _FLAGS[key]
        return flags

    def evaluate(self, case: TestCase) -> Outcome:
        pattern = re.compile(self.config["pattern"], self._flags())
        actual = as_text(case.actual)
        fullmatch = self.option("mode", "search") == "fullmatch"
        matcher = pattern.fullmatch if fullmatch else pattern.search
        match = matcher(actual)
        should_match = bool(self.option("should_match", True))

        if bool(match) is should_match:
            if match:
                return Outcome.hit(f"matched {match.group(0)!r}")
            return Outcome.hit("pattern correctly absent")
        if should_match:
            return Outcome.miss(f"pattern {pattern.pattern!r} did not match")
        return Outcome.miss(f"pattern {pattern.pattern!r} matched but should not have")
