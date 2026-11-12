"""AC-3: the same defects give the same rule codes in every format."""

from __future__ import annotations

import json

import pytest

from tooldata_lint import lint_file, lint_lines

from ._support import FIXTURES

# Lines of tests/fixtures/formats/<format>.jsonl: missing required argument, undefined tool,
# unanswered call, double-encoded arguments, one clean record.
EXPECTED = [(1, "V001"), (2, "T001"), (3, "P001"), (4, "A002")]


@pytest.mark.parametrize("fmt", ["openai", "hf", "sharegpt"])
def test_same_defects_same_codes_across_formats(fmt):
    report = lint_file(FIXTURES / "formats" / f"{fmt}.jsonl")
    assert [(i.line, i.code) for i in report.issues] == EXPECTED
    # Same field checks everywhere: the V001 finding names the same path and keyword.
    first = report.issues[0]
    assert (first.json_path, first.keyword) == ("$", "required")


def test_code_sets_are_identical_between_formats():
    sets = {
        fmt: {i.code for i in lint_file(FIXTURES / "formats" / f"{fmt}.jsonl").issues}
        for fmt in ("openai", "hf", "sharegpt")
    }
    assert sets["openai"] == sets["hf"] == sets["sharegpt"]


TOOLS = [{"type": "function", "function": {"name": "f", "parameters": {
    "type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}}}]


def _call(args, name="f"):
    return {"type": "function", "function": {"name": name, "arguments": args}}


def test_orderly_pairing_without_ids_has_no_false_positive():
    hf = {"tools": TOOLS, "messages": [
        {"role": "user", "content": "q"},
        {"role": "assistant", "tool_calls": [_call({"x": 1}), _call({"x": 2})]},
        {"role": "tool", "content": "a"}, {"role": "tool", "content": "b"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "again"},
        {"role": "assistant", "tool_calls": [_call({"x": 3})]},
        {"role": "tool", "content": "c"},
    ]}
    sharegpt = {"tools": json.dumps(TOOLS), "conversations": [
        {"from": "human", "value": "q"},
        {"from": "function_call", "value": json.dumps([
            {"name": "f", "arguments": {"x": 1}}, {"name": "f", "arguments": {"x": 2}}])},
        {"from": "observation", "value": "ab"},  # one observation answers the whole turn
        {"from": "gpt", "value": "done"},
        {"from": "function_call", "value": json.dumps({"name": "f", "arguments": {"x": 3}})},
        {"from": "observation", "value": "c"},
    ]}
    report = lint_lines([json.dumps(hf), json.dumps(sharegpt)])
    assert report.issues == []


def test_orderly_pairing_still_finds_real_gaps():
    hf = {"tools": TOOLS, "messages": [
        {"role": "assistant", "tool_calls": [_call({"x": 1}), _call({"x": 2})]},
        {"role": "tool", "content": "a"},
    ]}
    assert [i.code for i in lint_lines([json.dumps(hf)]).issues] == ["P001"]
    orphan = {"tools": TOOLS, "messages": [{"role": "tool", "content": "a"}]}
    assert [i.code for i in lint_lines([json.dumps(orphan)]).issues] == ["P002"]


def test_sharegpt_function_call_turn_not_json():
    rec = {"tools": json.dumps(TOOLS), "conversations": [
        {"from": "function_call", "value": "{oops"}]}
    assert [i.code for i in lint_lines([json.dumps(rec)]).issues] == ["A001"]


def test_sharegpt_role_content_keys_are_accepted():
    rec = {"tools": TOOLS, "conversations": [
        {"role": "function_call", "content": {"name": "f", "arguments": {"x": "no"}}},
        {"role": "observation", "content": "r"}]}
    assert [(i.code, i.keyword) for i in lint_lines([json.dumps(rec)]).issues] == [("V001", "type")]
