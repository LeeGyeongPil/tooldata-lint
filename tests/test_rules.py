"""AC-1, AC-2 and the individual rules."""

from __future__ import annotations

import json

import pytest

from tooldata_lint import LintOptions, lint_file, lint_lines, lint_record

from ._support import DEFECT_CODES, DEFECTS

TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}, "n": {"type": "integer", "minimum": 1}},
            "required": ["city"],
            "additionalProperties": False,
        },
    },
}


def record(args, *, call_id="c1", answered=True, tools=(TOOL,), name="get_weather"):
    call = {"type": "function", "function": {"name": name, "arguments": args}}
    if call_id:
        call["id"] = call_id
    msgs = [{"role": "user", "content": "q"}, {"role": "assistant", "tool_calls": [call]}]
    if answered:
        tool = {"role": "tool", "content": "ok"}
        if call_id:
            tool["tool_call_id"] = call_id
        msgs.append(tool)
    out = {"messages": msgs}
    if tools is not None:
        out["tools"] = list(tools)
    return out


def codes(issues):
    return [i.code for i in issues]


def test_v001_reports_all_schema_errors():
    report = lint_file(DEFECTS)
    line3 = {(i.code, i.json_path, i.keyword) for i in report.issues if i.line == 3}
    assert line3 == {
        ("V001", "$.unit", "enum"),
        ("V001", "$", "required"),
        ("V001", "$", "additionalProperties"),
    }
    assert len([i for i in report.issues if i.line == 3]) == 3


def test_defect_fixture_exact_codes():
    report = lint_file(DEFECTS)
    got = [(i.line, i.code) for i in report.issues]
    assert set(got) == DEFECT_CODES
    assert got.count((3, "V001")) == 3  # three separate findings on line 3
    assert len(got) == 12
    assert not [i for i in report.issues if i.line == 6 and i.code == "P002"]  # no cascade
    assert not [i for i in report.issues if i.line == 13]
    assert (8, "J001") not in got  # the broken line is line 7; line 8 is still checked


def test_broken_line_does_not_stop_processing():
    lines = ["{broken", json.dumps(record({"city": "Seoul"})), "[1, 2]", ""]
    report = lint_lines(lines)
    assert [(i.line, i.code) for i in report.issues] == [(1, "J001"), (3, "U001")]
    assert report.summary.records == 2 and report.summary.lines == 3


def test_invalid_utf8_line_is_j001_and_processing_continues():
    good = json.dumps(record({"city": "Seoul"})).encode()
    report = lint_lines([b"\xff\xfe{}", good])
    assert [(i.line, i.code) for i in report.issues] == [(1, "J001")]
    assert report.summary.records == 1


def test_bom_on_first_line_is_ignored():
    text = "﻿" + json.dumps(record({"city": "Seoul"}))
    assert lint_lines([text]).issues == []


def test_line_numbers_count_blank_lines():
    lines = ["", json.dumps(record({"city": "Seoul"})), "", "{x"]
    assert [(i.line, i.code) for i in lint_lines(lines).issues] == [(4, "J001")]


def test_a001_not_json_string_skips_schema_check():
    assert codes(lint_record(record("{city: Seoul"))) == ["A001"]


def test_a002_double_encoding_has_no_cascade():
    args = json.dumps(json.dumps({"city": "Seoul"}))
    assert codes(lint_record(record(args))) == ["A002"]


def test_non_object_arguments_violate_schema_type():
    issues = lint_record(record("[1, 2]"))
    assert [(i.code, i.keyword) for i in issues] == [("V001", "type")]


def test_nested_schema_path_and_keyword():
    issues = lint_record(record({"city": "Seoul", "n": 0}))
    assert [(i.code, i.json_path, i.keyword) for i in issues] == [("V001", "$.n", "minimum")]


def test_t002_when_no_tools_and_no_t001_cascade():
    issues = lint_record(record({"city": "Seoul"}, tools=None))
    assert codes(issues) == ["T002"]


def test_t001_lists_defined_tools():
    issues = lint_record(record({"x": 1}, name="nope"))
    assert codes(issues) == ["T001"] and "get_weather" in issues[0].message


def test_s001_invalid_schema_skips_v001():
    bad = {"type": "function", "function": {"name": "get_weather", "parameters": {"type": "objekt"}}}
    assert codes(lint_record(record({"anything": 1}, tools=(bad,)))) == ["S001"]


def test_tools_as_json_string_is_accepted():
    rec = record({"city": "Seoul"})
    rec["tools"] = json.dumps(rec["tools"])
    assert lint_record(rec) == []
    rec["tools"] = "{not json"
    assert codes(lint_record(rec)) == ["S001"]  # T002 would only repeat the same root cause


def test_flat_tool_definitions_are_accepted():
    flat = {"name": "get_weather", "parameters": TOOL["function"]["parameters"]}
    assert lint_record(record({"city": "Seoul"}, tools=(flat,))) == []
    assert codes(lint_record(record({}, tools=(flat,)))) == ["V001"]


def test_tool_without_parameters_accepts_any_arguments():
    bare = {"type": "function", "function": {"name": "get_weather"}}
    assert lint_record(record({"whatever": 1}, tools=(bare,))) == []


def test_p003_duplicate_ids():
    rec = record({"city": "Seoul"})
    rec["messages"][1]["tool_calls"].append(rec["messages"][1]["tool_calls"][0])
    assert "P003" in codes(lint_record(rec))


def test_p004_only_calls_missing_ids_when_others_use_ids():
    rec = record({"city": "Seoul"})
    second = {"type": "function", "function": {"name": "get_weather", "arguments": {"city": "B"}}}
    rec["messages"][1]["tool_calls"].append(second)
    rec["messages"].append({"role": "tool", "content": "ok"})
    assert codes(lint_record(rec)) == ["P004"]


def test_p001_and_p002_for_unanswered_and_orphan():
    # A call as the last turn is the training label (OpenAI layout): not a defect.
    assert codes(lint_record(record({"city": "Seoul"}, answered=False))) == []
    unanswered = record({"city": "Seoul"}, answered=False)
    unanswered["messages"].append({"role": "user", "content": "and then?"})
    assert codes(lint_record(unanswered)) == ["P001"]
    rec = record({"city": "Seoul"})
    rec["messages"].append({"role": "tool", "tool_call_id": "zzz", "content": "?"})
    assert codes(lint_record(rec)) == ["P002"]


def test_a003_mixed_encoding_is_a_warning():
    rec = record({"city": "Seoul"})
    rec["messages"][1]["tool_calls"].append(
        {"id": "c2", "type": "function",
         "function": {"name": "get_weather", "arguments": json.dumps({"city": "B"})}}
    )
    rec["messages"].append({"role": "tool", "tool_call_id": "c2", "content": "ok"})
    issues = lint_record(rec)
    assert codes(issues) == ["A003"] and issues[0].severity.value == "warning"


def test_ignore_drops_codes():
    issues = lint_record(record("{bad"), options=LintOptions(ignore=frozenset({"A001"})))
    assert issues == []


def test_validator_cache_is_bounded():
    from tooldata_lint import rules

    for n in range(rules._CACHE_LIMIT + 50):
        schema = {"type": "object", "properties": {f"p{n}": {"type": "string"}}}
        rules._validator(schema)
    assert len(rules._validators) <= rules._CACHE_LIMIT


@pytest.mark.parametrize("bad", [None, 5, "x", {"a": 1}])
def test_non_dict_records_are_u001(bad):
    assert codes(lint_record(bad)) == ["U001"]
