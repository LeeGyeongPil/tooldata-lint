"""A $ref cycle that never consumes the value is a data defect (S001), not an internal error."""

from __future__ import annotations

import json

import pytest

from tooldata_lint import lint_record

from ._support import run_cli

SELF = {"$ref": "#"}
CYCLE = {"$ref": "#/$defs/a", "$defs": {"a": {"$ref": "#/$defs/b"}, "b": {"$ref": "#/$defs/a"}}}
RECURSIVE_OK = {
    "type": "object",
    "properties": {"children": {"type": "array", "items": {"$ref": "#/$defs/node"}}},
    "$defs": {"node": {"type": "object", "required": ["id"],
                       "properties": {"children": {"type": "array", "items": {"$ref": "#/$defs/node"}}}}},
}


def record(parameters, arguments="{}"):
    return {
        "messages": [{"role": "assistant", "tool_calls": [
            {"type": "function", "function": {"name": "f", "arguments": arguments}}]}],
        "tools": [{"type": "function", "function": {"name": "f", "parameters": parameters}}],
    }


@pytest.mark.parametrize("params", [SELF, CYCLE], ids=["self", "cycle"])
def test_ref_cycle_is_s001(params):
    issues = lint_record(record(params))
    assert [(i.code) for i in issues] == ["S001"]


@pytest.mark.parametrize("params", [SELF, CYCLE], ids=["self", "cycle"])
def test_cli_continues_after_cycle(tmp_path, params):
    bad = record({"type": "object", "required": ["zzz"]})
    path = tmp_path / "x.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in (bad, record(params), bad)) + "\n", encoding="utf-8")
    res = run_cli(str(path))
    assert res.returncode == 1
    assert "Internal error" not in res.stderr
    assert res.stdout.count("V001") + res.stdout.count("violate") >= 2
    assert "$ref cycle" in res.stdout


def test_cycle_reported_once_per_tool():
    rec = record(SELF)
    rec["messages"][0]["tool_calls"] *= 2
    assert [i.code for i in lint_record(rec)] == ["S001"]


def test_legit_recursive_schema_still_validated():
    ok = lint_record(record(RECURSIVE_OK, json.dumps({"children": [{"id": 1}]})))
    assert ok == []
    bad = lint_record(record(RECURSIVE_OK, json.dumps({"children": [{}]})))
    assert [i.code for i in bad] == ["V001"]
