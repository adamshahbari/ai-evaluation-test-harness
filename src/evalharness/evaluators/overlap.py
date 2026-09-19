from __future__ import annotations

import re

from evalharness.domain.models import TestCase
from evalharness.evaluators.base import Evaluator, EvaluatorError, Outcome, as_text

_TOKEN = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold())


class TokenOverlapEvaluator(Evaluator):
    """Lexical token-overlap scoring.

    This measures word overlap, not meaning. It cannot distinguish a paraphrase
    from a contradiction: "the refund is approved" and "the refund is not
    approved" share most of their tokens and therefore score highly. Use it as a
    weighted drift signal alongside a stricter evaluator, never as a sole gate.
    """

    name = "token_overlap"
    default_min_score = 0.8

    def validate_config(self) -> None:
        method = self.option("method", "f1")
        if method not in {"f1", "jaccard"}:
            raise EvaluatorError(f"{self.name}: method must be 'f1' or 'jaccard', got {method!r}")
        stopwords = self.option("stopwords", [])
        if not isinstance(stopwords, list) or not all(isinstance(w, str) for w in stopwords):
            raise EvaluatorError(f"{self.name}: 'stopwords' must be a list of strings")

    def evaluate(self, case: TestCase) -> Outcome:
        stopwords = {word.casefold() for word in self.option("stopwords", [])}
        expected = {t for t in tokenize(as_text(case.expected)) if t not in stopwords}
        actual = {t for t in tokenize(as_text(case.actual)) if t not in stopwords}

        if not expected and not actual:
            return Outcome.hit("both expected and actual are empty after tokenisation")
        if not expected or not actual:
            return Outcome.miss("one side is empty after tokenisation")

        shared = expected & actual
        if self.option("method", "f1") == "jaccard":
            score = len(shared) / len(expected | actual)
        else:
            precision = len(shared) / len(actual)
            recall = len(shared) / len(expected)
            denominator = precision + recall
            score = 0.0 if denominator == 0 else 2 * precision * recall / denominator

        detail = (
            f"lexical overlap {score:.3f} "
            f"(min_score {self.min_score:.3f}, {len(shared)} shared token(s))"
        )
        return Outcome(score, detail)
