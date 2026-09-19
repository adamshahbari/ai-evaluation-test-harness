from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from tests.conftest import make_case

from evalharness.domain.models import Dataset, EvaluatorSpec
from evalharness.engine.runner import run_dataset
from evalharness.reporting import console, json_report, junit


def summary_fixture():
    return run_dataset(
        Dataset(
            cases=[
                make_case(id="ok", expected="a", actual="a", tags=["t"]),
                make_case(id="bad", expected="a", actual="b"),
                make_case(
                    id="broken",
                    actual="x",
                    evaluators=[EvaluatorSpec(type="required_fields", config={"fields": ["a"]})],
                ),
            ]
        ),
        fail_under=0.9,
    )


class TestConsole:
    def test_lists_every_case(self):
        text = console.render(summary_fixture())
        assert "ok" in text and "bad" in text and "broken" in text

    def test_marks_status(self):
        text = console.render(summary_fixture())
        assert "PASS " in text and "FAIL " in text and "ERROR" in text

    def test_shows_failure_detail(self):
        assert "expected" in console.render(summary_fixture())

    def test_hides_passing_assertions_by_default(self):
        assert "[ok]" not in console.render(summary_fixture())

    def test_verbose_shows_passing_assertions(self):
        assert "[ok]" in console.render(summary_fixture(), verbose=True)

    def test_reports_error_text(self):
        assert "error:" in console.render(summary_fixture())

    def test_includes_totals_and_gate(self):
        text = console.render(summary_fixture())
        assert "3 case(s)" in text
        assert "Gate --fail-under" in text

    def test_gate_omitted_when_not_set(self):
        summary = run_dataset(Dataset(cases=[make_case(id="a", expected="x", actual="x")]))
        assert "Gate" not in console.render(summary)

    def test_fail_fast_notice(self):
        summary = run_dataset(
            Dataset(cases=[make_case(id="a", expected="x", actual="y"), make_case(id="b")]),
            fail_fast=True,
        )
        assert "Stopped early" in console.render(summary)


class TestJsonReport:
    def test_output_is_valid_json(self):
        assert isinstance(json.loads(json_report.render(summary_fixture())), dict)

    def test_carries_schema_version(self):
        assert json.loads(json_report.render(summary_fixture()))["schema_version"] == "1.0"

    def test_summary_counts(self):
        payload = json.loads(json_report.render(summary_fixture()))["summary"]
        assert (payload["total"], payload["passed"], payload["failed"], payload["errored"]) == (
            3,
            1,
            1,
            1,
        )

    def test_case_entries_carry_assertions(self):
        cases = json.loads(json_report.render(summary_fixture()))["cases"]
        ok = next(c for c in cases if c["id"] == "ok")
        assert ok["assertions"][0]["evaluator"] == "exact_match"

    def test_error_is_serialised(self):
        cases = json.loads(json_report.render(summary_fixture()))["cases"]
        broken = next(c for c in cases if c["id"] == "broken")
        assert broken["status"] == "errored"
        assert broken["error"]

    def test_tags_are_serialised(self):
        cases = json.loads(json_report.render(summary_fixture()))["cases"]
        assert next(c for c in cases if c["id"] == "ok")["tags"] == ["t"]


class TestJunit:
    def test_output_parses_as_xml(self):
        root = ET.fromstring(junit.render(summary_fixture()))
        assert root.tag == "testsuite"

    def test_attributes_report_counts(self):
        root = ET.fromstring(junit.render(summary_fixture()))
        assert root.attrib["tests"] == "3"
        assert root.attrib["failures"] == "1"
        assert root.attrib["errors"] == "1"

    def test_one_testcase_per_result(self):
        root = ET.fromstring(junit.render(summary_fixture()))
        assert len(root.findall("testcase")) == 3

    def test_failure_element_present(self):
        root = ET.fromstring(junit.render(summary_fixture()))
        bad = root.find("./testcase[@name='bad']")
        assert bad.find("failure") is not None

    def test_error_element_present(self):
        root = ET.fromstring(junit.render(summary_fixture()))
        broken = root.find("./testcase[@name='broken']")
        assert broken.find("error") is not None

    def test_passing_case_has_no_child_elements(self):
        root = ET.fromstring(junit.render(summary_fixture()))
        assert list(root.find("./testcase[@name='ok']")) == []

    def test_has_xml_declaration(self):
        assert junit.render(summary_fixture()).startswith("<?xml")
