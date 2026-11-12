"""Format-independent rules. Input is a ``Record``, output is a list of ``Finding``.

Order matters to avoid cascades: call/response pairing is decided first (from ids only), so
a defect in the arguments (A001/A002/V001) can never make a call look unanswered.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing.exceptions import Unresolvable

from .formats.common import json_path
from .model import Call, Finding, Record, Response, ToolDef, encoding_of

_CACHE_LIMIT = 512
_validators: OrderedDict[str, Draft202012Validator] = OrderedDict()


def _validator(schema: Any) -> Draft202012Validator:
    """Validator cached by canonical schema text (bounded, least recently used first out)."""
    key = json.dumps(schema, sort_keys=True, default=str)
    cached = _validators.get(key)
    if cached is not None:
        _validators.move_to_end(key)
        return cached
    validator = Draft202012Validator(schema)
    _validators[key] = validator
    if len(_validators) > _CACHE_LIMIT:
        _validators.popitem(last=False)
    return validator


def check_record(rec: Record) -> list[Finding]:
    """Run every rule on one normalized record."""
    findings = list(rec.findings)
    calls = rec.calls
    tools_broken = any(
        f.code == "S001" and f.variant in ("tools_json", "tools_type") for f in rec.findings
    )
    # No T002 when `tools` itself was unparseable: S001 already names that root cause.
    if calls and not rec.tools_present and not tools_broken:
        findings.append(Finding("T002", {"n": len(calls)}))
    findings.extend(_pairing(rec))
    for call in calls:
        findings.extend(_check_call(rec, call))
    findings.extend(_mixed_encoding(calls))
    return findings


# --- pairing -----------------------------------------------------------------------------


def _pairing(rec: Record) -> list[Finding]:
    out: list[Finding] = []
    uses_ids = any(c.id for c in rec.calls) or any(r.id for r in rec.responses)
    pending: list[Call] = []
    seen_ids: set[str] = set()
    for kind, item in rec.events:
        if kind == "call":
            call: Call = item
            if call.id is None:
                if uses_ids:
                    out.append(_p004(call))
            elif call.id in seen_ids:
                out.append(
                    Finding("P003", {"id": call.id}, location=call.location)
                )
            else:
                seen_ids.add(call.id)
            pending.append(call)
            continue
        resp: Response = item
        matched = _match(pending, resp)
        if not matched:
            out.append(
                Finding("P002", {"id": resp.id, "n": resp.index}, location=resp.location)
            )
    for call in pending:
        if call.turn == rec.last_turn:
            # The record ends with this call turn: the call is the training label (OpenAI
            # fine-tuning layout), so a missing response is expected, not a defect.
            continue
        out.append(
            Finding(
                "P001",
                {"tool": call.name, "id": call.id, "n": call.index},
                location=call.location,
            )
        )
    return out


def _p004(call: Call) -> Finding:
    return Finding("P004", {"tool": call.name, "n": call.index}, location=call.location)


def _match(pending: list[Call], resp: Response) -> bool:
    """Remove the call(s) answered by ``resp`` from ``pending``; False if there is none."""
    if not pending:
        return False
    if resp.id is not None:
        for i, call in enumerate(pending):
            if call.id == resp.id:
                del pending[i]
                return True
        return False
    first = pending[0]
    if resp.answers_turn:
        pending[:] = [c for c in pending if c.turn != first.turn]
    else:
        del pending[0]
    return True


# --- per-call checks ---------------------------------------------------------------------


def _check_call(rec: Record, call: Call) -> list[Finding]:
    out: list[Finding] = []
    tool: ToolDef | None = None
    if call.name is None:
        out.append(Finding("T001", variant="noname", location=call.location))
    elif call.name in rec.tools:
        tool = rec.tools[call.name]
    elif rec.tools_present:
        defined = ", ".join(sorted(rec.tools)[:5]) + (", ..." if len(rec.tools) > 5 else "")
        out.append(
            Finding(
                "T001",
                {"tool": call.name, "defined": defined},
                location=call.location,
            )
        )

    args, problem = _decode_arguments(call)
    if problem is not None:
        out.append(problem)
        return out
    if tool is None or not tool.schema_ok:
        return out  # nothing to validate against (T001/T002/S001 already say why)
    out.extend(_schema_errors(call, tool, args))
    return out


def _decode_arguments(call: Call) -> tuple[Any, Finding | None]:
    """Return ``(arguments value, problem)``; a problem means schema validation is skipped."""
    args = call.arguments
    name = call.name
    if args is None:
        return None, Finding("A001", {"tool": name}, variant="missing", location=call.location)
    if not isinstance(args, str):
        return args, None
    try:
        decoded = json.loads(args)
    except ValueError as exc:
        return None, Finding(
            "A001", {"tool": name}, location=call.location, detail=str(exc)
        )
    if isinstance(decoded, str):
        # A JSON string that itself decodes to a string: encoded twice.
        return None, Finding("A002", {"tool": name}, location=call.location)
    return decoded, None


def _schema_errors(call: Call, tool: ToolDef, args: Any) -> list[Finding]:
    try:
        errors = sorted(
            _validator(tool.parameters).iter_errors(args),
            key=lambda e: (json_path(e.absolute_path), str(e.validator)),
        )
    except Unresolvable as exc:  # a $ref that points nowhere (references are never fetched)
        tool.schema_ok = False  # report once; later calls to this tool are not validated
        return [
            Finding(
                "S001",
                {"tool": call.name, "ref": str(exc)[:120]},
                variant="ref",
                location=call.location,
                detail=str(exc),
            )
        ]
    return [
        Finding(
            "V001",
            {"tool": call.name, "path": json_path(e.absolute_path), "keyword": e.validator,
             "detail": e.message, "kw": _keyword_params(e)},
            location=call.location,
            json_path=json_path(e.absolute_path),
            keyword=str(e.validator),
            detail=e.message,
        )
        for e in errors
    ]


def _short(value: Any, limit: int = 60) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _keyword_params(err: ValidationError) -> dict[str, str]:
    """Values for the localized per-keyword sentence (see ``i18n`` ``kw.*``)."""
    kw = err.validator
    expected = err.validator_value
    instance = err.instance
    params: dict[str, str] = {"value": _short(instance), "limit": _short(expected)}
    if kw == "required" and isinstance(instance, dict) and isinstance(expected, list):
        params["missing"] = ", ".join(repr(k) for k in expected if k not in instance)
    elif kw == "additionalProperties" and isinstance(instance, dict):
        props = err.schema.get("properties", {}) if isinstance(err.schema, dict) else {}
        patterns = err.schema.get("patternProperties", {}) if isinstance(err.schema, dict) else {}
        extra = [
            k for k in instance
            if k not in props and not any(re.search(p, k) for p in patterns)
        ]
        params["extra"] = ", ".join(repr(k) for k in extra)
    elif kw == "enum":
        params["allowed"] = _short(expected, 80)
    elif kw == "type":
        params["expected"] = (
            " | ".join(expected) if isinstance(expected, list) else str(expected)
        )
    return params


# --- record-level checks -----------------------------------------------------------------


def _mixed_encoding(calls: list[Call]) -> list[Finding]:
    kinds = [encoding_of(c.arguments) for c in calls]
    strings, objects = kinds.count("string"), kinds.count("object")
    if strings and objects:
        return [Finding("A003", {"strings": strings, "objects": objects})]
    return []
