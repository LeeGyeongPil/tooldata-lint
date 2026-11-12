"""Regression tests for the first review round (Q-1 .. Q-6) and the exit-code contract."""

from __future__ import annotations

import json

import pytest

from tooldata_lint import LintOptions, lint_lines, lint_record
from tooldata_lint import rules
from tooldata_lint.cli import main
from tooldata_lint.formats import common

from ._support import run_cli

PARAMS = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
}
TOOL = {"type": "function", "function": {"name": "get_weather", "parameters": PARAMS}}


def call(args='{"city": "Seoul"}', call_id="call_1"):
    return {"id": call_id, "type": "function",
            "function": {"name": "get_weather", "arguments": args}}


def codes(issues):
    return [i.code for i in issues]


def lint_text(*records, lang="en", options=None):
    options = options or LintOptions(lang=lang)
    return lint_lines([json.dumps(r) for r in records], options=options)


# --- Q-1: a call as the last turn is a label, not a missing response --------------------


def test_q1_trailing_call_openai():
    rec = {"tools": [TOOL], "messages": [
        {"role": "user", "content": "weather?"},
        {"role": "assistant", "tool_calls": [call()]}]}
    assert lint_record(rec) == []


def test_q1_trailing_parallel_calls_openai():
    rec = {"tools": [TOOL], "messages": [
        {"role": "user", "content": "weather?"},
        {"role": "assistant", "tool_calls": [call(call_id="a"), call(call_id="b")]}]}
    assert lint_record(rec) == []


def test_q1_trailing_call_hf_object_arguments_without_ids():
    flat = {"function": {"name": "get_weather", "arguments": {"city": "Seoul"}}}
    rec = {"tools": [TOOL], "messages": [
        {"role": "user", "content": "weather?"},
        {"role": "assistant", "tool_calls": [flat]}]}
    assert lint_record(rec) == []


def test_q1_trailing_call_sharegpt():
    rec = {"tools": [TOOL], "conversations": [
        {"from": "human", "value": "weather?"},
        {"from": "function_call",
         "value": json.dumps({"name": "get_weather", "arguments": {"city": "Seoul"}})}]}
    assert lint_record(rec) == []


@pytest.mark.parametrize("fmt", ["openai", "sharegpt"])
def test_q1_call_followed_by_more_turns_without_response_is_still_p001(fmt):
    if fmt == "openai":
        rec = {"tools": [TOOL], "messages": [
            {"role": "user", "content": "q"},
            {"role": "assistant", "tool_calls": [call()]},
            {"role": "assistant", "content": "I just answer."}]}
    else:
        rec = {"tools": [TOOL], "conversations": [
            {"from": "human", "value": "q"},
            {"from": "function_call",
             "value": json.dumps({"name": "get_weather", "arguments": {"city": "x"}})},
            {"from": "gpt", "value": "I just answer."}]}
    assert codes(lint_record(rec)) == ["P001"]


def test_q1_trailing_call_still_gets_argument_checks():
    rec = {"tools": [TOOL], "messages": [
        {"role": "user", "content": "q"},
        {"role": "assistant", "tool_calls": [call(args="{}")]}]}
    assert codes(lint_record(rec)) == ["V001"]


# --- Q-2: unresolvable $ref is a finding, not a traceback -------------------------------


@pytest.mark.parametrize("ref", ["#/$defs/missing", "http://127.0.0.1:8765/s.json"])
def test_q2_unresolvable_ref_is_s001_and_linting_goes_on(ref):
    bad_tool = {"type": "function", "function": {"name": "get_weather", "parameters": {"$ref": ref}}}
    first = {"tools": [bad_tool], "messages": [
        {"role": "user", "content": "q"},
        {"role": "assistant", "tool_calls": [call(), call(call_id="call_2")]},
        {"role": "tool", "tool_call_id": "call_1", "content": "a"},
        {"role": "tool", "tool_call_id": "call_2", "content": "b"}]}
    broken_json_next = {"messages": "oops"}
    report = lint_text(first, broken_json_next)
    s001 = [i for i in report.issues if i.code == "S001" and i.line == 1]
    assert len(s001) == 1  # reported once per tool, the second call is skipped
    assert "$ref" in s001[0].message
    assert any(i.line == 2 and i.code == "U001" for i in report.issues)  # next line was linted


def test_q2_cli_exit_code_is_1_not_a_crash(tmp_path):
    bad_tool = {"type": "function", "function": {"name": "get_weather", "parameters": {"$ref": "#/nope"}}}
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({"tools": [bad_tool], "messages": [
        {"role": "assistant", "tool_calls": [call()]}]}) + "\n", encoding="utf-8")
    result = run_cli(str(path))
    assert result.returncode == 1 and "Traceback" not in result.stderr
    assert "S001" in result.stdout


def test_internal_bug_exits_2_with_message_not_traceback(monkeypatch, tmp_path, capsys):
    def boom(rec):
        raise RuntimeError("boom")

    monkeypatch.setattr(rules, "check_record", boom)
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({"messages": []}) + "\n", encoding="utf-8")
    assert main([str(path), "--lang", "en"]) == 2
    err = capsys.readouterr().err
    assert "Internal error" in err and "line 1" in err and "Traceback" not in err
    assert main([str(path), "--lang", "ko"]) == 2
    assert "내부 오류" in capsys.readouterr().err


def test_exit_code_contract(tmp_path):
    """0 clean, 1 problems found, 2 tool/usage/input error."""
    clean = run_cli("examples/clean.jsonl")
    assert clean.returncode == 0
    assert run_cli("examples/defects.jsonl").returncode == 1
    assert run_cli("no-such-file.jsonl").returncode == 2
    assert run_cli("--format", "xml", "examples/clean.jsonl").returncode == 2


# --- Q-3: malformed containers and placeholder messages ---------------------------------


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_q3_tool_calls_not_a_list_is_reported(lang):
    rec = {"messages": [{"role": "assistant", "tool_calls": "bad"}]}
    issues = lint_text(rec, lang=lang).issues
    assert codes(issues) == ["S001"] and issues[0].location == "messages[0].tool_calls"


def test_q3_non_object_items_are_reported():
    rec = {"tools": [TOOL], "messages": [None, 5, {"role": "assistant", "tool_calls": [None, 7]}]}
    issues = lint_record(rec)
    assert [i.location for i in issues if i.code == "S001"] == [
        "messages[0]", "messages[1]", "messages[2].tool_calls[0]", "messages[2].tool_calls[1]"]


def test_q3_sharegpt_non_object_items_are_reported():
    rec = {"conversations": [3, {"from": "function_call", "value": "[null]"},
                             {"from": "function_call", "value": "null"}]}
    locations = [i.location for i in lint_record(rec) if i.code == "S001"]
    assert locations == ["conversations[0]", "conversations[1][0]", "conversations[2]"]


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_q3_missing_name_never_prints_none(lang):
    rec = {"tools": [TOOL], "messages": [
        {"role": "assistant", "tool_calls": [{"id": "c", "function": None}]}]}
    messages = [i.message for i in lint_text(rec, lang=lang).issues]
    assert messages and all("None" not in m for m in messages)
    assert any(("<no name>" if lang == "en" else "<이름 없음>") in m for m in messages)


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_q3_missing_arguments_has_its_own_message(lang):
    rec = {"tools": [TOOL], "messages": [
        {"role": "assistant", "tool_calls": [{"id": "c", "function": {"name": "get_weather"}}]}]}
    issues = lint_text(rec, lang=lang).issues
    assert codes(issues) == ["A001"]
    assert "None" not in issues[0].message and "null" in issues[0].message


@pytest.mark.parametrize("tools", ["{not json", 42])
def test_q3_broken_tools_gives_one_finding_not_a_cascade(tools):
    rec = {"tools": tools, "messages": [{"role": "assistant", "tool_calls": [call()]}]}
    assert codes(lint_record(rec)) == ["S001"]


# --- Q-4: Korean error paths are Korean -------------------------------------------------


def test_q4_ko_output_error_has_no_english_reason(tmp_path):
    out = tmp_path / "missing-dir" / "r.json"
    result = run_cli("examples/clean.jsonl", "-o", str(out), "--lang", "ko")
    assert result.returncode == 2
    assert "No such file" not in result.stderr
    assert "경로 또는 상위 디렉터리가 없습니다" in result.stderr


def test_q4_en_output_error_is_english(tmp_path):
    out = tmp_path / "missing-dir" / "r.json"
    result = run_cli("examples/clean.jsonl", "-o", str(out), "--lang", "en")
    assert "does not exist" in result.stderr


def test_q4_ko_particles_and_ambiguous_option():
    bad = run_cli("--format", "xml", "examples/clean.jsonl", "--lang", "ko").stderr
    assert "'xml' 값은" in bad and "'xml' 는" not in bad
    amb = run_cli("--f", "x", "examples/clean.jsonl", "--lang", "ko").stderr
    assert "모호한 옵션입니다" in amb and "could match" not in amb


def test_q4_os_reason_covers_unknown_errnos_in_both_languages():
    from tooldata_lint import i18n

    assert "999" in i18n.os_reason("ko", 999, "Some English text")
    assert "Some English text" not in i18n.os_reason("ko", 999, "Some English text")
    assert i18n.os_reason("en", 28, "x") == i18n.t("en", "os.ENOSPC")


# --- Q-5: check_schema results are cached ------------------------------------------------


def test_q5_check_schema_runs_once_for_repeated_schemas(monkeypatch):
    calls = []
    real = common.Draft202012Validator.check_schema

    def counting(schema, *a, **k):
        calls.append(1)
        return real(schema, *a, **k)

    monkeypatch.setattr(common.Draft202012Validator, "check_schema", staticmethod(counting))
    common._checked.clear()
    rec = {"tools": [TOOL], "messages": [{"role": "user", "content": "q"}]}
    lint_lines([json.dumps(rec)] * 500)
    assert len(calls) == 1


def test_q5_check_schema_cache_is_bounded_and_keeps_errors():
    common._checked.clear()
    for n in range(common._CACHE_LIMIT + 20):
        assert common.check_schema_cached({"type": "object", "title": str(n)}) is None
    assert len(common._checked) == common._CACHE_LIMIT
    bad = common.check_schema_cached({"type": "objekt"})
    assert bad is not None and common.check_schema_cached({"type": "objekt"}) == bad


# --- Q-6: an empty file is a warning -----------------------------------------------------


@pytest.mark.parametrize("content", ["", "\n\n  \n"])
def test_q6_empty_file_warns(tmp_path, content):
    path = tmp_path / "empty.jsonl"
    path.write_text(content, encoding="utf-8")
    assert run_cli(str(path)).returncode == 0  # warning only
    strict = run_cli(str(path), "--fail-on", "warning")
    assert strict.returncode == 1 and "U001" in strict.stdout
    assert run_cli(str(path), "--fail-on", "warning", "--ignore", "U001").returncode == 0


def test_q6_empty_file_message_in_korean(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert "레코드가 없습니다" in run_cli(str(path), "--lang", "ko").stdout


def test_q6_file_with_records_has_no_empty_warning():
    assert lint_lines(['{"messages": []}']).issues == []
