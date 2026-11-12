"""Adapter for ShareGPT-style records as used by LLaMA-Factory.

Tool calls live in turns whose role is ``function_call`` (value: a JSON object
``{"name", "arguments"}`` or a JSON array of them for parallel calls); tool results are
``observation`` turns. ShareGPT has no call ids, so calls and observations pair by order.
"""

from __future__ import annotations

import json
from typing import Any

from ..model import Call, Finding, Record, Response
from .common import normalize_tools

_CALL_ROLES = {"function_call"}
_RESPONSE_ROLES = {"observation", "tool"}


def parse(raw: dict[str, Any]) -> Record:
    tools, present, findings = normalize_tools(raw.get("tools"))
    turns = raw["conversations"]
    rec = Record("sharegpt", tools, present, findings=findings, last_turn=len(turns) - 1)
    call_no = response_no = 0
    for i, turn in enumerate(turns):
        if not isinstance(turn, dict):
            where = f"conversations[{i}]"
            rec.findings.append(Finding("S001", {"where": where}, variant="item_type", location=where))
            continue
        role = turn.get("from", turn.get("role"))
        value = turn.get("value", turn.get("content"))
        if role in _CALL_ROLES:
            items = value
            if isinstance(value, str):
                try:
                    items = json.loads(value)
                except ValueError:
                    rec.findings.append(
                        Finding("A001", variant="turn", location=f"conversations[{i}]")
                    )
                    continue
            batch = items if isinstance(items, list) else [items]
            for j, item in enumerate(batch):
                loc = f"conversations[{i}]" + (f"[{j}]" if isinstance(items, list) else "")
                if not isinstance(item, dict):
                    rec.findings.append(
                        Finding("S001", {"where": loc}, variant="item_type", location=loc)
                    )
                    continue
                call_no += 1
                rec.events.append(
                    (
                        "call",
                        Call(
                            name=item.get("name") if isinstance(item.get("name"), str) else None,
                            id=None,
                            arguments=item.get("arguments"),
                            turn=i,
                            location=loc,
                            index=call_no,
                        ),
                    )
                )
        elif role in _RESPONSE_ROLES:
            response_no += 1
            rec.events.append(
                ("response", Response(None, f"conversations[{i}]", response_no, answers_turn=True))
            )
    return rec
