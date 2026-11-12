"""Report renderers: ``text`` for people, ``json`` for tools."""

from __future__ import annotations

from ..core import Report
from . import json_out, text


def render(report: Report, fmt: str) -> str:
    """Render ``report`` as ``text`` or ``json``."""
    if fmt == "json":
        return json_out.render(report)
    if fmt == "text":
        return text.render(report)
    raise ValueError(f"unknown output format: {fmt!r} (use 'text' or 'json')")
