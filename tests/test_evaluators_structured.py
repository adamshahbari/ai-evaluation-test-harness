from __future__ import annotations

import pytest
from tests.conftest import make_case

from evalharness.evaluators.base import EvaluatorError
from evalharness.evaluators.fields import RequiredFieldsEvaluator, resolve_path
from evalharness.evaluators.json_schema import JsonSchemaEvaluator
from evalharness.evaluators.numeric import NumericToleranceEvaluator, extract_number
from evalharness.evaluators.regex_eval import RegexEvaluator

OBJECT_SCHEMA = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}


class TestRegex:
    def test_search_matches_substring(self):
        assert RegexEvaluator({"pattern": "b.d"}).evaluate(make_case(actual="abcd")).score == 1.0

    def test_no_match_scores_zero(self):
        outcome = RegexEvaluator({"pattern": "zzz"}).evaluate(make_case(actual="abc"))
        assert outcome.score == 0.0

    def test_fullmatch_mode_requires_whole_string(self):
        evaluator = RegexEvaluator({"pattern": "abc", "mode": "fullmatch"})
        assert evaluator.evaluate(make_case(actual="abcd")).score == 0.0
        assert evaluator.evaluate(make_case(actual="abc")).score == 1.0

    def test_ignorecase_flag(self):
        evaluator = RegexEvaluator({"pattern": "abc", "flags": ["IGNORECASE"]})
        assert evaluator.evaluate(make_case(actual="ABC")).score == 1.0

    def test_flags_accept_single_string(self):
        evaluator = RegexEvaluator({"pattern": "a.c", "flags": "DOTALL"})
        assert evaluator.evaluate(make_case(actual="a\nc")).score == 1.0

    def test_should_match_false_inverts(self):
        evaluator = RegexEvaluator({"pattern": "bad", "should_match": False})
        assert evaluator.evaluate(make_case(actual="good")).score == 1.0
        assert evaluator.evaluate(make_case(actual="bad")).score == 0.0

    def test_invalid_pattern_raises(self):
        with pytest.raises(EvaluatorError, match="invalid pattern"):
            RegexEvaluator({"pattern": "([unclosed"})

    def test_unknown_flag_raises(self):
        with pytest.raises(EvaluatorError, match="unknown flag"):
            RegexEvaluator({"pattern": "a", "flags": ["NOPE"]})

    def test_non_string_pattern_raises(self):
        with pytest.raises(EvaluatorError, match="must be a string"):
            RegexEvaluator({"pattern": 5})

    def test_invalid_mode_raises(self):
        with pytest.raises(EvaluatorError, match="mode must be"):
            RegexEvaluator({"pattern": "a", "mode": "match"})


class TestJsonSchema:
    def test_valid_document_passes(self):
        evaluator = JsonSchemaEvaluator({"schema": OBJECT_SCHEMA})
        assert evaluator.evaluate(make_case(actual='{"a": 1}')).score == 1.0

    def test_dict_actual_is_accepted_without_parsing(self):
        evaluator = JsonSchemaEvaluator({"schema": OBJECT_SCHEMA})
        assert evaluator.evaluate(make_case(actual={"a": 1})).score == 1.0

    def test_missing_required_property_fails(self):
        evaluator = JsonSchemaEvaluator({"schema": OBJECT_SCHEMA})
        outcome = evaluator.evaluate(make_case(actual="{}"))
        assert outcome.score == 0.0
        assert "required" in outcome.detail

    def test_wrong_type_reports_path(self):
        evaluator = JsonSchemaEvaluator({"schema": OBJECT_SCHEMA})
        outcome = evaluator.evaluate(make_case(actual='{"a": "no"}'))
        assert "a:" in outcome.detail

    def test_non_json_actual_raises(self):
        evaluator = JsonSchemaEvaluator({"schema": OBJECT_SCHEMA})
        with pytest.raises(EvaluatorError, match="not valid JSON"):
            evaluator.evaluate(make_case(actual="not json at all"))

    def test_empty_actual_raises(self):
        evaluator = JsonSchemaEvaluator({"schema": OBJECT_SCHEMA})
        with pytest.raises(EvaluatorError, match="empty"):
            evaluator.evaluate(make_case(actual="   "))

    def test_invalid_schema_raises_at_construction(self):
        with pytest.raises(EvaluatorError, match="invalid JSON Schema"):
            JsonSchemaEvaluator({"schema": {"type": "nonsense"}})

    def test_non_mapping_schema_raises(self):
        with pytest.raises(EvaluatorError, match="must be a mapping"):
            JsonSchemaEvaluator({"schema": []})

    def test_many_errors_are_truncated(self):
        schema = {
            "type": "object",
            "required": ["a", "b", "c", "d", "e"],
        }
        outcome = JsonSchemaEvaluator({"schema": schema}).evaluate(make_case(actual="{}"))
        assert "more)" in outcome.detail


class TestNumericTolerance:
    def test_exact_equality_within_zero_tolerance(self):
        case = make_case(expected=1.0, actual=1.0)
        assert NumericToleranceEvaluator({}).evaluate(case).score == 1.0

    def test_absolute_tolerance_boundary_is_inclusive(self):
        evaluator = NumericToleranceEvaluator({"tolerance": 0.1})
        assert evaluator.evaluate(make_case(expected=1.0, actual=1.1)).score == 1.0

    def test_just_outside_absolute_tolerance_fails(self):
        evaluator = NumericToleranceEvaluator({"tolerance": 0.1})
        assert evaluator.evaluate(make_case(expected=1.0, actual=1.2)).score == 0.0

    def test_relative_tolerance(self):
        evaluator = NumericToleranceEvaluator({"tolerance": 0.05, "mode": "relative"})
        assert evaluator.evaluate(make_case(expected=100, actual=104)).score == 1.0
        assert evaluator.evaluate(make_case(expected=100, actual=110)).score == 0.0

    def test_relative_tolerance_against_zero_degrades_to_absolute(self):
        evaluator = NumericToleranceEvaluator({"tolerance": 0.5, "mode": "relative"})
        assert evaluator.evaluate(make_case(expected=0, actual=0.25)).score == 1.0
        outcome = evaluator.evaluate(make_case(expected=0, actual=5))
        assert outcome.score == 0.0
        assert "undefined" in outcome.detail

    def test_number_extracted_from_prose(self):
        case = make_case(expected=154.2, actual="The total is 154.20 pounds")
        assert NumericToleranceEvaluator({"tolerance": 0.01}).evaluate(case).score == 1.0

    def test_thousands_separators_are_handled(self):
        case = make_case(expected=1042.75, actual="£1,042.75")
        assert NumericToleranceEvaluator({}).evaluate(case).score == 1.0

    def test_negative_numbers(self):
        case = make_case(expected=-5, actual="minus five is -5")
        assert NumericToleranceEvaluator({}).evaluate(case).score == 1.0

    def test_missing_number_raises(self):
        with pytest.raises(EvaluatorError, match="no number found"):
            NumericToleranceEvaluator({}).evaluate(make_case(expected=1, actual="no digits"))

    def test_boolean_is_rejected_as_number(self):
        with pytest.raises(EvaluatorError, match="boolean"):
            extract_number(True, field="actual")

    def test_negative_tolerance_raises(self):
        with pytest.raises(EvaluatorError, match="must not be negative"):
            NumericToleranceEvaluator({"tolerance": -1})

    def test_non_numeric_tolerance_raises(self):
        with pytest.raises(EvaluatorError, match="must be numeric"):
            NumericToleranceEvaluator({"tolerance": "loose"})

    def test_invalid_mode_raises(self):
        with pytest.raises(EvaluatorError, match="mode must be"):
            NumericToleranceEvaluator({"mode": "fuzzy"})

    def test_scientific_notation(self):
        case = make_case(expected=1500.0, actual="1.5e3")
        assert NumericToleranceEvaluator({}).evaluate(case).score == 1.0


class TestRequiredFields:
    def test_present_fields_pass(self):
        evaluator = RequiredFieldsEvaluator({"fields": ["a", "b"]})
        assert evaluator.evaluate(make_case(actual='{"a":1,"b":2}')).score == 1.0

    def test_missing_field_scores_fraction(self):
        evaluator = RequiredFieldsEvaluator({"fields": ["a", "b"]})
        outcome = evaluator.evaluate(make_case(actual='{"a":1}'))
        assert outcome.score == 0.5
        assert "missing field 'b'" in outcome.detail

    def test_value_equality(self):
        evaluator = RequiredFieldsEvaluator({"values": {"a": 1}})
        assert evaluator.evaluate(make_case(actual='{"a":1}')).score == 1.0

    def test_value_mismatch_is_reported(self):
        evaluator = RequiredFieldsEvaluator({"values": {"a": 1}})
        outcome = evaluator.evaluate(make_case(actual='{"a":2}'))
        assert outcome.score == 0.0
        assert "expected 1" in outcome.detail

    def test_dotted_path_into_nested_object(self):
        evaluator = RequiredFieldsEvaluator({"fields": ["a.b.c"]})
        assert evaluator.evaluate(make_case(actual='{"a":{"b":{"c":1}}}')).score == 1.0

    def test_list_index_path(self):
        evaluator = RequiredFieldsEvaluator({"values": {"items.1.sku": "X"}})
        assert (
            evaluator.evaluate(make_case(actual='{"items":[{"sku":"A"},{"sku":"X"}]}')).score == 1.0
        )

    def test_out_of_range_index_is_missing(self):
        evaluator = RequiredFieldsEvaluator({"fields": ["items.9"]})
        assert evaluator.evaluate(make_case(actual='{"items":[1]}')).score == 0.0

    def test_path_through_scalar_is_missing(self):
        evaluator = RequiredFieldsEvaluator({"fields": ["a.b"]})
        assert evaluator.evaluate(make_case(actual='{"a":5}')).score == 0.0

    def test_null_value_counts_as_present(self):
        evaluator = RequiredFieldsEvaluator({"fields": ["a"]})
        assert evaluator.evaluate(make_case(actual='{"a":null}')).score == 1.0

    def test_no_criteria_raises(self):
        with pytest.raises(EvaluatorError, match="at least one"):
            RequiredFieldsEvaluator({})

    def test_non_list_fields_raises(self):
        with pytest.raises(EvaluatorError, match="list of strings"):
            RequiredFieldsEvaluator({"fields": "a"})

    def test_non_mapping_values_raises(self):
        with pytest.raises(EvaluatorError, match="must be a mapping"):
            RequiredFieldsEvaluator({"values": ["a"]})

    def test_resolve_path_non_integer_list_segment_is_missing(self):
        evaluator = RequiredFieldsEvaluator({"fields": ["a.x"]})
        assert evaluator.evaluate(make_case(actual='{"a":[1]}')).score == 0.0

    def test_resolve_path_returns_nested_value(self):
        assert resolve_path({"a": {"b": 7}}, "a.b") == 7
