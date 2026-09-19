from __future__ import annotations

from pathlib import Path

import pytest

from evalharness.loading.errors import DatasetError
from evalharness.loading.loader import discover, load_dataset

VALID = """
cases:
  - id: one
    actual: hello
    evaluators:
      - type: contains
        config: {values: ["hello"]}
"""


def test_loads_mapping_with_cases_key(suite):
    dataset = load_dataset(suite(VALID))
    assert len(dataset) == 1
    assert dataset.cases[0].id == "one"


def test_loads_bare_list(suite):
    body = """
- id: one
  actual: hello
  evaluators:
    - type: exact_match
"""
    assert len(load_dataset(suite(body))) == 1


def test_loads_json_file(suite):
    body = '{"cases": [{"id": "one", "actual": "x", "evaluators": [{"type": "exact_match"}]}]}'
    assert len(load_dataset(suite(body, "suite.json"))) == 1


def test_records_source_paths(suite):
    dataset = load_dataset(suite(VALID))
    assert dataset.sources[0].name == "suite.yaml"


def test_directory_discovery_is_recursive(tmp_path: Path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "s.yaml").write_text(VALID, encoding="utf-8")
    assert len(load_dataset(tmp_path)) == 1


def test_discovery_is_deterministically_ordered(tmp_path: Path):
    for name in ["c.yaml", "a.yaml", "b.yaml"]:
        (tmp_path / name).write_text(VALID.replace("id: one", f"id: {name[0]}"), encoding="utf-8")
    assert [p.name for p in discover(tmp_path)] == ["a.yaml", "b.yaml", "c.yaml"]


def test_missing_path_raises(tmp_path: Path):
    with pytest.raises(DatasetError, match="does not exist"):
        load_dataset(tmp_path / "nope.yaml")


def test_unsupported_extension_raises(tmp_path: Path):
    path = tmp_path / "suite.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(DatasetError, match="unsupported extension"):
        load_dataset(path)


def test_empty_directory_raises(tmp_path: Path):
    with pytest.raises(DatasetError, match=r"no \.yaml"):
        load_dataset(tmp_path)


def test_empty_file_raises(suite):
    with pytest.raises(DatasetError, match="file is empty"):
        load_dataset(suite(""))


def test_invalid_yaml_raises(suite):
    with pytest.raises(DatasetError, match="invalid YAML"):
        load_dataset(suite("cases: [unclosed"))


def test_invalid_json_reports_line(suite):
    with pytest.raises(DatasetError, match="invalid JSON at line"):
        load_dataset(suite("{broken", "suite.json"))


def test_mapping_without_cases_key_raises(suite):
    with pytest.raises(DatasetError, match="'cases' key"):
        load_dataset(suite("other: 1"))


def test_non_list_cases_raises(suite):
    with pytest.raises(DatasetError, match="'cases' must be a list"):
        load_dataset(suite("cases: 5"))


def test_scalar_document_raises(suite):
    with pytest.raises(DatasetError, match="expected a list of cases"):
        load_dataset(suite("just a string"))


def test_non_mapping_case_raises(suite):
    with pytest.raises(DatasetError, match="must be a mapping"):
        load_dataset(suite("cases: ['a']"))


def test_duplicate_ids_raise(suite):
    body = """
cases:
  - id: dup
    evaluators: [{type: exact_match}]
  - id: dup
    evaluators: [{type: exact_match}]
"""
    with pytest.raises(DatasetError, match="duplicate case id"):
        load_dataset(suite(body))


def test_duplicate_ids_across_files_raise(tmp_path: Path):
    for name in ["a.yaml", "b.yaml"]:
        (tmp_path / name).write_text(
            "cases:\n  - id: same\n    evaluators: [{type: exact_match}]\n", encoding="utf-8"
        )
    with pytest.raises(DatasetError, match="also defined in"):
        load_dataset(tmp_path)


def test_missing_evaluators_raises(suite):
    with pytest.raises(DatasetError, match="evaluators"):
        load_dataset(suite("cases:\n  - id: x\n"))


def test_unknown_evaluator_type_raises(suite):
    body = "cases:\n  - id: x\n    evaluators: [{type: telepathy}]\n"
    with pytest.raises(DatasetError, match="unknown evaluator type"):
        load_dataset(suite(body))


def test_evaluator_config_error_is_caught_at_load(suite):
    body = "cases:\n  - id: x\n    evaluators: [{type: regex, config: {pattern: '(['}}]\n"
    with pytest.raises(DatasetError, match="invalid pattern"):
        load_dataset(suite(body))


def test_unknown_case_field_raises(suite):
    body = "cases:\n  - id: x\n    nonsense: 1\n    evaluators: [{type: exact_match}]\n"
    with pytest.raises(DatasetError, match="case 'x'"):
        load_dataset(suite(body))


def test_out_of_range_threshold_raises(suite):
    body = "cases:\n  - id: x\n    threshold: 5\n    evaluators: [{type: exact_match}]\n"
    with pytest.raises(DatasetError, match=r"between 0\.0 and 1\.0"):
        load_dataset(suite(body))


def test_error_message_includes_source_path(suite):
    path = suite("cases: 5")
    with pytest.raises(DatasetError) as excinfo:
        load_dataset(path)
    assert str(path) in str(excinfo.value)
