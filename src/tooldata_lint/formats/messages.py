"""Adapter for ``messages`` records (OpenAI fine-tuning, HF/TRL, Axolotl)."""

from __future__ import annotations

from typing import Any

from ..model import Call, Finding, Record, Response
from .common import normalize_tools


def _id(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _shape(variant: str, where: str) -> Finding:
    """A structurally broken container (not a list / not an object) at ``where``."""
    return Finding("S001", {"where": where}, variant=variant, location=where)


def parse(raw: dict[str, Any]) -> Record:
    tools, present, findings = normalize_tools(raw.get("tools"))
    messages = raw["messages"]
    rec = Record("messages", tools, present, findings=findings, last_turn=len(messages) - 1)
    call_no = response_no = 0
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            rec.findings.append(_shape("item_type", f"messages[{i}]"))
            continue
        role = msg.get("role")
        if role == "assistant" and "tool_calls" in msg and msg["tool_calls"] is not None:
            if not isinstance(msg["tool_calls"], list):
                rec.findings.append(_shape("calls_type", f"messages[{i}].tool_calls"))
                continue
            for j, tc in enumerate(msg["tool_calls"]):
                where = f"messages[{i}].tool_calls[{j}]"
                if not isinstance(tc, dict):
                    rec.findings.append(_shape("item_type", where))
                    continue
                # OpenAI nests name/arguments under "function"; some HF data is flat.
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else tc
                call_no += 1
                call = Call(
                    name=fn.get("name") if isinstance(fn.get("name"), str) else None,
                    id=_id(tc.get("id")),
                    arguments=fn.get("arguments"),
                    turn=i,
                    location=where,
                    index=call_no,
                )
                rec.events.append(("call", call))
        elif role == "tool":
            response_no += 1
            rec.events.append(
                (
                    "response",
                    Response(_id(msg.get("tool_call_id")), f"messages[{i}]", response_no),
                )
            )
    return rec
