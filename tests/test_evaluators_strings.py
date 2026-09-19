from __future__ import annotations

import pytest
from tests.conftest import make_case

from evalharness.evaluators.base import EvaluatorError
from evalharness.evaluators.exact import ExactMatchEvaluator
from evalharness.evaluators.substring import ContainsEvaluator, NotContainsEvaluator


class TestExactMatch:
    def test_identical_strings_score_one(self):
        outcome = ExactMatchEvaluator().evaluate(make_case(expected="a", actual="a"))
        assert outcome.score == 1.0

    def test_differing_strings_score_zero(self):
        outcome = ExactMatchEvaluator().evaluate(make_case(expected="a", actual="b"))
        assert outcome.score == 0.0
        assert "expected" in outcome.detail

    def test_strips_by_default(self):
        outcome = ExactMatchEvaluator().evaluate(make_case(expected="a", actual="  a  "))
        assert outcome.score == 1.0

    def test_case_sensitive_by_default(self):
        assert ExactMatchEvaluator().evaluate(make_case(expected="A", actual="a")).score == 0.0

    def test_ignore_case_option(self):
        evaluator = ExactMatchEvaluator({"ignore_case": True})
        assert evaluator.evaluate(make_case(expected="A", actual="a")).score == 1.0

    def test_collapse_whitespace_option(self):
        evaluator = ExactMatchEvaluator({"collapse_whitespace": True})
        case = make_case(expected="a b", actual="a    \n b")
        assert evaluator.evaluate(case).score == 1.0

    def test_none_actual_treated_as_empty_string(self):
        assert ExactMatchEvaluator().evaluate(make_case(expected="", actual=None)).score == 1.0

    def test_dict_values_compared_by_canonical_json(self):
        case = make_case(expected={"b": 1, "a": 2}, actual={"a": 2, "b": 1})
        assert ExactMatchEvaluator().evaluate(case).score == 1.0

    def test_unicode_compared_correctly(self):
        case = make_case(expected="café", actual="café")
        assert ExactMatchEvaluator().evaluate(case).score == 1.0


class TestContains:
    def test_all_terms_present(self):
        evaluator = ContainsEvaluator({"values": ["a", "b"]})
        assert evaluator.evaluate(make_case(actual="a and b")).score == 1.0

    def test_partial_match_scores_fraction(self):
        evaluator = ContainsEvaluator({"values": ["a", "b", "c", "d"]})
        outcome = evaluator.evaluate(make_case(actual="a b"))
        assert outcome.score == 0.5
        assert "missing" in outcome.detail

    def test_any_mode_passes_with_one_term(self):
        evaluator = ContainsEvaluator({"values": ["x", "b"], "mode": "any"})
        assert evaluator.evaluate(make_case(actual="b")).score == 1.0

    def test_any_mode_fails_with_no_terms(self):
        evaluator = ContainsEvaluator({"values": ["x", "y"], "mode": "any"})
        assert evaluator.evaluate(make_case(actual="b")).score == 0.0

    def test_ignore_case(self):
        evaluator = ContainsEvaluator({"values": ["ABC"], "ignore_case": True})
        assert evaluator.evaluate(make_case(actual="xabcx")).score == 1.0

    def test_string_value_is_accepted(self):
        assert ContainsEvaluator({"values": "a"}).evaluate(make_case(actual="a")).score == 1.0

    def test_missing_values_option_raises(self):
        with pytest.raises(EvaluatorError, match="missing required option"):
            ContainsEvaluator({})

    def test_empty_values_list_raises(self):
        with pytest.raises(EvaluatorError, match="empty list"):
            ContainsEvaluator({"values": []})

    def test_non_string_values_raise(self):
        with pytest.raises(EvaluatorError, match="list of strings"):
            ContainsEvaluator({"values": [1, 2]})

    def test_invalid_mode_raises(self):
        with pytest.raises(EvaluatorError, match="mode must be"):
            ContainsEvaluator({"values": ["a"], "mode": "some"})


class TestNotContains:
    def test_absent_terms_pass(self):
        evaluator = NotContainsEvaluator({"values": ["bad"]})
        assert evaluator.evaluate(make_case(actual="all good")).score == 1.0

    def test_present_term_fails(self):
        evaluator = NotContainsEvaluator({"values": ["bad"]})
        outcome = evaluator.evaluate(make_case(actual="this is bad"))
        assert outcome.score == 0.0
        assert "forbidden" in outcome.detail

    def test_ignore_case(self):
        evaluator = NotContainsEvaluator({"values": ["BAD"], "ignore_case": True})
        assert evaluator.evaluate(make_case(actual="bad")).score == 0.0

    def test_missing_values_raises(self):
        with pytest.raises(EvaluatorError):
            NotContainsEvaluator({})
