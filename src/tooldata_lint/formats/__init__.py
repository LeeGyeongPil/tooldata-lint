"""Format detection and adapters. Every adapter returns the same ``Record``."""

from __future__ import annotations

from typing import Any

from ..model import Record
from . import messages, sharegpt


def detect(raw: Any) -> str | None:
    """Return the format name of a decoded JSON value, or ``None`` if unknown."""
    if isinstance(raw, dict):
        if isinstance(raw.get("messages"), list):
            return "messages"
        if isinstance(raw.get("conversations"), list):
            return "sharegpt"
    return None


def parse(raw: Any) -> Record | None:
    """Convert a decoded record to a ``Record``; ``None`` if the format is unknown."""
    fmt = detect(raw)
    if fmt == "messages":
        return messages.parse(raw)
    if fmt == "sharegpt":
        return sharegpt.parse(raw)
    return None
