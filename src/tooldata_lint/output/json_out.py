"""JSON report with stable keys (only ``message`` strings depend on the language)."""

from __future__ import annotations

import json

from .. import __version__
from ..core import Report


def render(report: Report) -> str:
    data = {"tool": "tooldata-lint", "version": __version__, **report.to_dict()}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
