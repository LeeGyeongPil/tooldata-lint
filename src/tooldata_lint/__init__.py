"""tooldata-lint: lint tool-calling fine-tuning data (JSONL) before training."""

from __future__ import annotations

from importlib import metadata as _metadata

from .core import (
    InputError,
    LintOptions,
    Report,
    TooldataLintError,
    lint_file,
    lint_lines,
    lint_record,
)
from .model import Issue, Severity, Summary

try:
    __version__ = _metadata.version("tooldata-lint")
except _metadata.PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0+unknown"

__all__ = [
    "InputError",
    "Issue",
    "LintOptions",
    "Report",
    "Severity",
    "Summary",
    "TooldataLintError",
    "__version__",
    "lint_file",
    "lint_lines",
    "lint_record",
]
