from __future__ import annotations

import pytest
from pydantic import ValidationError

from evalharness.domain.models import Dataset, EvaluatorSpec, TestCase
from tests.helpers import make_case


def test_case_defaults_to_full_threshold():
    assert make_case().threshold == 1.0


def test_case_rejects_blank_id():
    with pytest.raises(ValidationError, match="must not be empty"):
        make_case(id="   ")


def test_case_strips_id_whitespace():
    assert make_case(id="  spaced  ").id == "spaced"


def test_case_requires_at_least_one_evaluator():
    with pytest.raises(ValidationError, match="at least one evaluator"):
        make_case(evaluators=[])


@pytest.mark.parametrize("value", [-0.1, 1.1, 2.0])
def test_case_rejects_out_of_range_threshold(value):
    with pytest.raises(ValidationError, match=r"between 0\.0 and 1\.0"):
        make_case(threshold=value)


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
def test_case_accepts_boundary_thresholds(value):
    assert make_case(threshold=value).threshold == value


def test_case_rejects_unknown_field():
    with pytest.raises(ValidationError):
        TestCase(id="x", evaluators=[EvaluatorSpec(type="exact_match")], nonsense=1)


def test_case_rejects_all_zero_weights():
    with pytest.raises(ValidationError, match="must not all be zero"):
        make_case(evaluators=[EvaluatorSpec(type="exact_match", weight=0)])


def test_case_allows_one_zero_weight_among_several():
    built = make_case(
        evaluators=[
            EvaluatorSpec(type="exact_match", weight=0),
            EvaluatorSpec(type="exact_match", weight=1),
        ]
    )
    assert [spec.weight for spec in built.evaluators] == [0.0, 1.0]


def test_evaluator_spec_rejects_negative_weight():
    with pytest.raises(ValidationError, match="must not be negative"):
        EvaluatorSpec(type="exact_match", weight=-1)


def test_evaluator_spec_rejects_blank_type():
    with pytest.raises(ValidationError, match="must not be empty"):
        EvaluatorSpec(type="  ")


def test_has_any_tag():
    built = make_case(tags=["a", "b"])
    assert built.has_any_tag({"b", "z"})
    assert not built.has_any_tag({"z"})


def test_dataset_filter_by_tags_returns_matching_cases():
    dataset = Dataset(cases=[make_case(id="a", tags=["x"]), make_case(id="b", tags=["y"])])
    assert [c.id for c in dataset.filter_by_tags({"x"})] == ["a"]


def test_dataset_filter_with_empty_tags_is_identity():
    dataset = Dataset(cases=[make_case(id="a"), make_case(id="b")])
    assert len(dataset.filter_by_tags(set())) == 2


def test_dataset_get_returns_none_for_unknown_id():
    assert Dataset(cases=[make_case(id="a")]).get("missing") is None


def test_dataset_get_returns_case():
    assert Dataset(cases=[make_case(id="a")]).get("a").id == "a"
