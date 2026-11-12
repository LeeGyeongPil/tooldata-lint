"""AC-5: distribution summary in JSON and text output."""

from __future__ import annotations

import json

from tooldata_lint import lint_file

from ._support import DEFECTS, run_cli


def test_distribution_summary():
    result = run_cli("examples/defects.jsonl", "--format", "json", "--exit-zero")
    data = json.loads(result.stdout)
    s = data["summary"]
    assert s["records"] == 12
    assert s["formats"] == {"messages": 11, "sharegpt": 1}
    assert s["no_call_records"] == 2
    assert s["parallel_call_records"] == 1
    assert s["calls_per_tool"] == {"book_flight": 1, "get_time": 1, "get_weather": 9}
    assert s["calls"] == 11
    assert s["arguments_encoding"] == {"string": 4, "object": 7, "other": 0}
    assert data["counts"] == {"total": 12, "errors": 11, "warnings": 1}


def test_json_issue_keys_are_stable():
    data = json.loads(run_cli("examples/defects.jsonl", "--format", "json", "--exit-zero").stdout)
    assert set(data) == {"tool", "version", "files", "counts", "issues", "summary"}
    assert set(data["issues"][0]) == {
        "file", "line", "code", "severity", "message", "location", "json_path", "keyword", "detail"}


def test_text_output_ends_with_summary_table_and_verdict():
    lines = run_cli("examples/defects.jsonl", "--exit-zero").stdout.splitlines()
    assert "Summary" in lines
    assert any(l.strip().startswith("calls per tool") and "get_weather 9" in l for l in lines)
    assert lines[-1] == "12 problems (11 errors, 1 warning)"


def test_summary_across_two_files_adds_up():
    out = json.loads(run_cli("examples/defects.jsonl", "examples/clean.jsonl",
                             "--format", "json", "--exit-zero").stdout)
    assert out["summary"]["records"] == 18 and out["files"] == [
        "examples/defects.jsonl", "examples/clean.jsonl"]


def test_report_api_matches_cli():
    report = lint_file(DEFECTS)
    assert report.summary.to_dict()["records"] == 12
    assert report.exit_code() == 1 and report.exit_code("warning") == 1
