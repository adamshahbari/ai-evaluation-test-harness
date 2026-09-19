from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner

from evalharness import __version__
from evalharness.cli import app
from evalharness.exit_codes import ExitCode

runner = CliRunner()

PASSING = """
cases:
  - id: good
    expected: hello
    actual: hello
    tags: [alpha]
    evaluators: [{type: exact_match}]
"""

FAILING = """
cases:
  - id: good
    expected: hello
    actual: hello
    tags: [alpha]
    evaluators: [{type: exact_match}]
  - id: bad
    expected: hello
    actual: goodbye
    tags: [beta]
    evaluators: [{type: exact_match}]
"""


@pytest.fixture
def passing(suite) -> Path:
    return suite(PASSING)


@pytest.fixture
def failing(suite) -> Path:
    return suite(FAILING)


class TestRunExitCodes:
    def test_all_passing_exits_zero(self, passing):
        result = runner.invoke(app, ["run", str(passing)])
        assert result.exit_code == ExitCode.SUCCESS

    def test_failure_exits_one(self, failing):
        result = runner.invoke(app, ["run", str(failing)])
        assert result.exit_code == ExitCode.EVALUATION_FAILED

    def test_no_exit_code_suppresses_failure(self, failing):
        result = runner.invoke(app, ["run", str(failing), "--no-exit-code"])
        assert result.exit_code == ExitCode.SUCCESS

    def test_missing_path_exits_three(self, tmp_path):
        result = runner.invoke(app, ["run", str(tmp_path / "nope.yaml")])
        assert result.exit_code == ExitCode.INVALID_DATASET

    def test_malformed_suite_exits_three(self, suite):
        result = runner.invoke(app, ["run", str(suite("cases: [broken"))])
        assert result.exit_code == ExitCode.INVALID_DATASET

    def test_unknown_evaluator_exits_three(self, suite):
        body = "cases:\n  - id: x\n    evaluators: [{type: telepathy}]\n"
        result = runner.invoke(app, ["run", str(suite(body))])
        assert result.exit_code == ExitCode.INVALID_DATASET

    def test_unknown_format_exits_two(self, passing):
        result = runner.invoke(app, ["run", str(passing), "--format", "pdf"])
        assert result.exit_code == ExitCode.USAGE_ERROR

    def test_out_of_range_fail_under_exits_two(self, passing):
        result = runner.invoke(app, ["run", str(passing), "--fail-under", "2"])
        assert result.exit_code == ExitCode.USAGE_ERROR

    def test_unmatched_tags_exit_two(self, passing):
        result = runner.invoke(app, ["run", str(passing), "--tags", "nothing"])
        assert result.exit_code == ExitCode.USAGE_ERROR

    def test_dataset_error_is_distinct_from_failure(self, failing, suite):
        broken = runner.invoke(app, ["run", str(suite("cases: [broken", "b.yaml"))])
        regressed = runner.invoke(app, ["run", str(failing)])
        assert broken.exit_code != regressed.exit_code


class TestRunOptions:
    def test_fail_under_met_exits_zero(self, failing):
        result = runner.invoke(app, ["run", str(failing), "--fail-under", "0.5"])
        assert result.exit_code == ExitCode.SUCCESS

    def test_fail_under_not_met_exits_one(self, failing):
        result = runner.invoke(app, ["run", str(failing), "--fail-under", "0.9"])
        assert result.exit_code == ExitCode.EVALUATION_FAILED

    def test_fail_fast_stops_early(self, failing):
        result = runner.invoke(app, ["run", str(failing), "--fail-fast"])
        assert "Stopped early" in result.stdout

    def test_tags_filter_selects_subset(self, failing):
        result = runner.invoke(app, ["run", str(failing), "--tags", "alpha"])
        assert "good" in result.stdout and "bad" not in result.stdout

    def test_verbose_shows_passing_assertions(self, passing):
        result = runner.invoke(app, ["run", str(passing), "--verbose"])
        assert "[ok]" in result.stdout

    def test_json_format_is_parseable(self, passing):
        result = runner.invoke(app, ["run", str(passing), "--format", "json"])
        assert json.loads(result.stdout)["summary"]["total"] == 1

    def test_junit_format_is_parseable(self, passing):
        result = runner.invoke(app, ["run", str(passing), "--format", "junit"])
        assert ET.fromstring(result.stdout).tag == "testsuite"

    def test_output_writes_file(self, passing, tmp_path):
        target = tmp_path / "out" / "report.json"
        result = runner.invoke(
            app, ["run", str(passing), "--format", "json", "--output", str(target)]
        )
        assert result.exit_code == ExitCode.SUCCESS
        assert json.loads(target.read_text())["summary"]["passed"] == 1

    def test_output_creates_parent_directory(self, passing, tmp_path):
        target = tmp_path / "deep" / "nested" / "r.json"
        runner.invoke(app, ["run", str(passing), "--format", "json", "--output", str(target)])
        assert target.exists()


class TestOtherCommands:
    def test_validate_reports_case_count(self, passing):
        result = runner.invoke(app, ["validate", str(passing)])
        assert result.exit_code == ExitCode.SUCCESS
        assert "1 case(s) valid" in result.stdout

    def test_validate_rejects_broken_suite(self, suite):
        result = runner.invoke(app, ["validate", str(suite("cases: 5"))])
        assert result.exit_code == ExitCode.INVALID_DATASET

    def test_list_shows_ids_and_evaluators(self, failing):
        result = runner.invoke(app, ["list", str(failing)])
        assert "good" in result.stdout and "exact_match" in result.stdout

    def test_list_honours_tags(self, failing):
        result = runner.invoke(app, ["list", str(failing), "--tags", "beta"])
        assert "bad" in result.stdout and "good" not in result.stdout

    def test_inspect_emits_json_for_case(self, passing):
        result = runner.invoke(app, ["inspect", str(passing), "good"])
        assert json.loads(result.stdout)["id"] == "good"

    def test_inspect_unknown_case_exits_two(self, passing):
        result = runner.invoke(app, ["inspect", str(passing), "missing"])
        assert result.exit_code == ExitCode.USAGE_ERROR

    def test_report_rerenders_stored_json(self, passing, tmp_path):
        target = tmp_path / "r.json"
        runner.invoke(app, ["run", str(passing), "--format", "json", "--output", str(target)])
        result = runner.invoke(app, ["report", str(target)])
        assert "1 case(s)" in result.stdout

    def test_report_json_passthrough(self, passing, tmp_path):
        target = tmp_path / "r.json"
        runner.invoke(app, ["run", str(passing), "--format", "json", "--output", str(target)])
        result = runner.invoke(app, ["report", str(target), "--format", "json"])
        assert json.loads(result.stdout)["schema_version"] == "1.0"

    def test_report_rejects_non_report_json(self, tmp_path):
        target = tmp_path / "other.json"
        target.write_text('{"unrelated": true}', encoding="utf-8")
        result = runner.invoke(app, ["report", str(target)])
        assert result.exit_code == ExitCode.INVALID_DATASET

    def test_report_rejects_invalid_json(self, tmp_path):
        target = tmp_path / "bad.json"
        target.write_text("{nope", encoding="utf-8")
        result = runner.invoke(app, ["report", str(target)])
        assert result.exit_code == ExitCode.INVALID_DATASET

    def test_evaluators_lists_all_nine(self):
        result = runner.invoke(app, ["evaluators"])
        assert len(result.stdout.strip().splitlines()) == 9

    def test_version_matches_package(self):
        result = runner.invoke(app, ["version"])
        assert result.stdout.strip() == __version__

    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        assert "Usage" in result.stdout
