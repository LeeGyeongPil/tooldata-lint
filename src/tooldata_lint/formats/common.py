"""Helpers shared by the format adapters (tool definitions are format independent)."""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from ..model import Finding, ToolDef


_CACHE_LIMIT = 512
# Result of ``check_schema`` by canonical schema text: None (valid) or the error fields.
_checked: OrderedDict[str, tuple[str, str | None, str] | None] = OrderedDict()


def check_schema_cached(schema: Any) -> tuple[str, str | None, str] | None:
    """``None`` if ``schema`` is a valid JSON Schema, else ``(path, keyword, message)``.

    ``Draft202012Validator.check_schema`` is slow and datasets repeat the same few tool
    schemas on every record, so results are kept in a bounded LRU cache.
    """
    key = json.dumps(schema, sort_keys=True, default=str)
    if key in _checked:
        _checked.move_to_end(key)
        return _checked[key]
    try:
        Draft202012Validator.check_schema(schema)
        result = None
    except SchemaError as exc:
        result = (json_path(exc.path), exc.validator, exc.message)
    _checked[key] = result
    if len(_checked) > _CACHE_LIMIT:
        _checked.popitem(last=False)
    return result


def json_path(parts: Any) -> str:
    """Render a jsonschema error path (deque of keys) as ``$.a[0].b``."""
    out = "$"
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


def normalize_tools(raw: Any) -> tuple[dict[str, ToolDef], bool, list[Finding]]:
    """Return ``(tools by name, tools_present, findings)`` for a record's ``tools``.

    Accepts a list (or a JSON string holding a list) of OpenAI-style
    ``{"type": "function", "function": {...}}`` or flat ``{"name", "parameters"}`` items.
    """
    findings: list[Finding] = []
    if raw is None:
        return {}, False, findings
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            findings.append(Finding("S001", variant="tools_json"))
            return {}, False, findings
    if not isinstance(raw, list):
        findings.append(Finding("S001", variant="tools_type"))
        return {}, False, findings

    tools: dict[str, ToolDef] = {}
    for index, item in enumerate(raw):
        body = item.get("function") if isinstance(item, dict) else None
        if not isinstance(body, dict):
            body = item
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name:
            findings.append(Finding("S001", {"index": index}, variant="tools_shape"))
            continue
        parameters = body.get("parameters", {})
        tool = ToolDef(name, body.get("description"), parameters)
        bad = check_schema_cached(parameters)
        if bad is not None:
            path, keyword, message = bad
            tool.schema_ok = False
            findings.append(
                Finding(
                    "S001",
                    {"tool": name, "path": path, "keyword": keyword},
                    location=f"tools[{index}]",
                    json_path=path,
                    keyword=keyword,
                    detail=message,
                )
            )
        tools.setdefault(name, tool)
    return tools, bool(raw), findings
