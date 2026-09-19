from __future__ import annotations

import pytest

from evalharness.evaluators.base import EvaluatorError
from evalharness.evaluators.composite import MAX_DEPTH, CompositeEvaluator
from evalharness.evaluators.overlap import TokenOverlapEvaluator, tokenize
from evalharness.evaluators.registry import available_evaluators, build_evaluator
from tests.helpers import make_case


class TestTokenOverlap:
    def test_identical_text_scores_one(self):
        case = make_case(expected="alpha beta", actual="alpha beta")
        assert TokenOverlapEvaluator({}).evaluate(case).score == 1.0

    def test_disjoint_text_scores_zero(self):
        case = make_case(expected="alpha beta", actual="gamma delta")
        assert TokenOverlapEvaluator({}).evaluate(case).score == 0.0

    def test_word_order_is_ignored(self):
        case = make_case(expected="alpha beta", actual="beta alpha")
        assert TokenOverlapEvaluator({}).evaluate(case).score == 1.0

    def test_case_and_punctuation_are_normalised(self):
        case = make_case(expected="Alpha, beta!", actual="alpha beta")
        assert TokenOverlapEvaluator({}).evaluate(case).score == 1.0

    def test_jaccard_differs_from_f1(self):
        case = make_case(expected="a b c d", actual="a b")
        f1 = TokenOverlapEvaluator({"method": "f1"}).evaluate(case).score
        jaccard = TokenOverlapEvaluator({"method": "jaccard"}).evaluate(case).score
        assert f1 == pytest.approx(2 / 3)
        assert jaccard == pytest.approx(0.5)

    def test_negation_is_not_detected(self):
        """The documented weakness: opposite meaning, near-identical tokens."""
        case = make_case(expected="the refund is approved", actual="the refund is not approved")
        assert TokenOverlapEvaluator({"method": "f1"}).evaluate(case).score == pytest.approx(
            0.8889, abs=1e-4
        )

    def test_stopwords_are_removed(self):
        case = make_case(expected="the alpha", actual="alpha")
        evaluator = TokenOverlapEvaluator({"stopwords": ["the"]})
        assert evaluator.evaluate(case).score == 1.0

    def test_both_sides_empty_scores_one(self):
        assert TokenOverlapEvaluator({}).evaluate(make_case(expected="", actual="")).score == 1.0

    def test_one_side_empty_scores_zero(self):
        case = make_case(expected="alpha", actual="")
        assert TokenOverlapEvaluator({}).evaluate(case).score == 0.0

    def test_default_min_score_is_below_one(self):
        assert TokenOverlapEvaluator({}).min_score == 0.8

    def test_min_score_controls_pass(self):
        evaluator = TokenOverlapEvaluator({"min_score": 0.5})
        case = make_case(expected="a b c d", actual="a b")
        assert evaluator.passes(evaluator.evaluate(case).score)

    def test_invalid_method_raises(self):
        with pytest.raises(EvaluatorError, match="method must be"):
            TokenOverlapEvaluator({"method": "cosine"})

    def test_invalid_stopwords_raise(self):
        with pytest.raises(EvaluatorError, match="list of strings"):
            TokenOverlapEvaluator({"stopwords": "the"})

    @pytest.mark.parametrize("value", [-0.1, 1.5, "high", True])
    def test_invalid_min_score_raises(self, value):
        with pytest.raises(EvaluatorError, match="min_score"):
            TokenOverlapEvaluator({"min_score": value})

    def test_tokenize_keeps_apostrophes_and_digits(self):
        assert tokenize("It's 30 days!") == ["it's", "30", "days"]


class TestComposite:
    def _spec(self, **over):
        base = {
            "mode": "all",
            "evaluators": [
                {"type": "contains", "config": {"values": ["a"]}},
                {"type": "contains", "config": {"values": ["b"]}},
            ],
        }
        base.update(over)
        return base

    def test_all_mode_requires_every_child(self):
        evaluator = CompositeEvaluator(self._spec())
        assert evaluator.evaluate(make_case(actual="a b")).score == 1.0
        assert evaluator.evaluate(make_case(actual="a")).score == 0.0

    def test_any_mode_requires_one_child(self):
        evaluator = CompositeEvaluator(self._spec(mode="any"))
        assert evaluator.evaluate(make_case(actual="a")).score == 1.0
        assert evaluator.evaluate(make_case(actual="z")).score == 0.0

    def test_weighted_mode_blends_scores(self):
        evaluator = CompositeEvaluator(
            {
                "mode": "weighted",
                "evaluators": [
                    {"type": "contains", "weight": 3, "config": {"values": ["a"]}},
                    {"type": "contains", "weight": 1, "config": {"values": ["zz"]}},
                ],
            }
        )
        assert evaluator.evaluate(make_case(actual="a")).score == pytest.approx(0.75)

    def test_weighted_detail_lists_children(self):
        evaluator = CompositeEvaluator(self._spec(mode="weighted"))
        assert "contains=" in evaluator.evaluate(make_case(actual="a b")).detail

    def test_nesting_is_supported(self):
        evaluator = CompositeEvaluator(
            {
                "mode": "all",
                "evaluators": [
                    {
                        "type": "composite",
                        "config": {
                            "mode": "any",
                            "evaluators": [{"type": "contains", "config": {"values": ["a"]}}],
                        },
                    }
                ],
            }
        )
        assert evaluator.evaluate(make_case(actual="a")).score == 1.0

    def test_nesting_beyond_limit_raises(self):
        spec: dict = {
            "mode": "all",
            "evaluators": [{"type": "contains", "config": {"values": ["a"]}}],
        }
        for _ in range(MAX_DEPTH + 1):
            spec = {"mode": "all", "evaluators": [{"type": "composite", "config": spec}]}
        with pytest.raises(EvaluatorError, match="nesting deeper"):
            CompositeEvaluator(spec)

    def test_missing_children_raises(self):
        with pytest.raises(EvaluatorError, match="missing required option"):
            CompositeEvaluator({"mode": "all"})

    def test_empty_children_raises(self):
        with pytest.raises(EvaluatorError, match="non-empty list"):
            CompositeEvaluator({"evaluators": []})

    def test_child_without_type_raises(self):
        with pytest.raises(EvaluatorError, match="needs a 'type'"):
            CompositeEvaluator({"evaluators": [{"config": {}}]})

    def test_non_mapping_child_raises(self):
        with pytest.raises(EvaluatorError, match="must be a mapping"):
            CompositeEvaluator({"evaluators": ["contains"]})

    def test_negative_child_weight_raises(self):
        with pytest.raises(EvaluatorError, match="must not be negative"):
            CompositeEvaluator(
                {"evaluators": [{"type": "contains", "weight": -1, "config": {"values": ["a"]}}]}
            )

    def test_all_zero_child_weights_raise(self):
        with pytest.raises(EvaluatorError, match="must not all be zero"):
            CompositeEvaluator(
                {
                    "mode": "weighted",
                    "evaluators": [{"type": "contains", "weight": 0, "config": {"values": ["a"]}}],
                }
            )

    def test_invalid_mode_raises(self):
        with pytest.raises(EvaluatorError, match="mode must be"):
            CompositeEvaluator({"mode": "most", "evaluators": [{"type": "exact_match"}]})

    def test_child_config_errors_propagate(self):
        with pytest.raises(EvaluatorError, match="invalid pattern"):
            CompositeEvaluator({"evaluators": [{"type": "regex", "config": {"pattern": "(["}}]})


class TestRegistry:
    def test_all_nine_evaluators_are_registered(self):
        assert len(available_evaluators()) == 9

    def test_registry_is_sorted(self):
        assert available_evaluators() == sorted(available_evaluators())

    def test_build_returns_requested_type(self):
        assert build_evaluator("exact_match", {}).name == "exact_match"

    def test_unknown_type_lists_alternatives(self):
        with pytest.raises(EvaluatorError, match="available:"):
            build_evaluator("telepathy", {})

    def test_composite_receives_depth(self):
        built = build_evaluator(
            "composite", {"evaluators": [{"type": "exact_match"}]}, depth=MAX_DEPTH - 1
        )
        assert isinstance(built, CompositeEvaluator)
