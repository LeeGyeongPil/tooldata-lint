"""Public API: ``lint_file``, ``lint_lines``, ``lint_record`` and the ``Report`` type."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from . import formats, i18n, rules
from .model import SEVERITY, Finding, Issue, Severity, Summary


class TooldataLintError(Exception):
    """Base class of every error raised on purpose by this package."""


class InputError(TooldataLintError):
    """An input file could not be opened. ``kind``: not_found, permission, is_dir, other."""

    def __init__(self, path: str, kind: str, detail: str = "", errno: int | None = None) -> None:
        self.path = path
        self.kind = kind
        self.detail = detail
        self.errno = errno
        super().__init__(f"cannot open {path!r}: {detail or kind.replace('_', ' ')}")


class InternalError(TooldataLintError):
    """A bug: a rule raised on one record. Carries the file and line so it can be reported."""

    def __init__(self, file: str, line: int, cause: Exception) -> None:
        self.file = file
        self.line = line
        self.cause_text = f"{type(cause).__name__}: {cause}"
        super().__init__(f"internal error at {file}:{line}: {self.cause_text}")


@dataclass(frozen=True)
class LintOptions:
    """Options shared by the lint functions.

    ``ignore`` holds rule codes to drop from the result; ``lang`` is ``en``, ``ko`` or
    ``None`` (resolve from the environment).
    """

    ignore: frozenset[str] = frozenset()
    lang: str | None = None

    def resolved_lang(self) -> str:
        return i18n.resolve_lang(self.lang)


@dataclass
class Report:
    """Result of linting: the issues, a distribution summary, and the language used."""

    issues: list[Issue] = field(default_factory=list)
    summary: Summary = field(default_factory=Summary)
    lang: str = "en"
    files: list[str] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for i in self.issues if i.severity is Severity.ERROR)

    @property
    def warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity is Severity.WARNING)

    def exit_code(self, fail_on: str = "error") -> int:
        """0 when clean at the chosen level, 1 otherwise (``fail_on``: error | warning)."""
        if fail_on not in ("error", "warning"):
            raise ValueError("fail_on must be 'error' or 'warning'")
        if self.errors or (fail_on == "warning" and self.warnings):
            return 1
        return 0

    def merge(self, other: Report) -> None:
        self.issues.extend(other.issues)
        self.summary.merge(other.summary)
        self.files.extend(other.files)

    def to_dict(self) -> dict[str, Any]:
        """Stable, language-independent structure (only ``message`` is localized)."""
        return {
            "files": list(self.files),
            "counts": {
                "total": len(self.issues),
                "errors": self.errors,
                "warnings": self.warnings,
            },
            "issues": [i.to_dict() for i in self.issues],
            "summary": self.summary.to_dict(),
        }


def _to_issue(f: Finding, file: str, line: int, lang: str) -> Issue:
    return Issue(
        file=file,
        line=line,
        code=f.code,
        severity=SEVERITY[f.code],
        message=i18n.render_message(lang, f.code, f.variant, f.params),
        location=f.location,
        json_path=f.json_path,
        keyword=f.keyword,
        detail=f.detail,
    )


def _lint_decoded(raw: Any, line: int, file: str, lang: str, summary: Summary) -> list[Issue]:
    try:
        rec = formats.parse(raw)
        if rec is None:
            summary.records += 1
            summary.formats["unknown"] = summary.formats.get("unknown", 0) + 1
            return [_to_issue(Finding("U001"), file, line, lang)]
        summary.add_record(rec)
        return [_to_issue(f, file, line, lang) for f in rules.check_record(rec)]
    except Exception as exc:  # a bug, not a data defect: never end as a raw traceback
        raise InternalError(file, line, exc) from exc


def lint_record(
    record: dict[str, Any], line: int = 1, options: LintOptions | None = None
) -> list[Issue]:
    """Lint one already-decoded record and return its issues (file is ``<record>``).

    Data defects are returned as issues; ``InternalError`` is raised only for a bug.
    """
    options = options or LintOptions()
    issues = _lint_decoded(record, line, "<record>", options.resolved_lang(), Summary())
    return [i for i in issues if i.code not in options.ignore]


def lint_lines(
    lines: Iterable[str | bytes], source: str = "<stdin>", options: LintOptions | None = None
) -> Report:
    """Lint JSONL text. A line that is not valid JSON becomes a J001 issue; linting goes on."""
    options = options or LintOptions()
    lang = options.resolved_lang()
    report = Report(lang=lang, files=[source])
    for number, line in enumerate(lines, start=1):
        issues = _lint_line(line, number, source, lang, report.summary)
        report.issues.extend(i for i in issues if i.code not in options.ignore)
    if report.summary.lines == 0 and "U001" not in options.ignore:
        # An empty file usually means an earlier pipeline step failed: make it visible.
        empty = Finding("U001", variant="empty")
        report.issues.append(_to_issue(empty, source, 1, lang))
    return report


def _lint_line(line: str | bytes, number: int, source: str, lang: str, summary: Summary) -> list[Issue]:
    if isinstance(line, bytes):
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError:
            summary.lines += 1
            return [_to_issue(Finding("J001", variant="utf8"), source, number, lang)]
    text = line.lstrip("﻿").strip() if number == 1 else line.strip()
    if not text:
        return []
    summary.lines += 1
    try:
        raw = json.loads(text)
    except (ValueError, RecursionError) as exc:  # RecursionError: absurdly deep nesting
        col = getattr(exc, "colno", 1)
        finding = Finding("J001", {"col": col}, detail=str(exc))
        return [_to_issue(finding, source, number, lang)]
    return _lint_decoded(raw, number, source, lang, summary)


def lint_file(path: str | os.PathLike[str], options: LintOptions | None = None) -> Report:
    """Lint a JSONL file. Raises ``InputError`` if it cannot be opened."""
    name = os.fspath(path)
    try:
        handle = open(name, "rb")
    except FileNotFoundError as exc:
        raise InputError(name, "not_found") from exc
    except IsADirectoryError as exc:
        raise InputError(name, "is_dir") from exc
    except PermissionError as exc:
        raise InputError(name, "permission") from exc
    except OSError as exc:
        raise InputError(
            name, "other", exc.strerror or type(exc).__name__, errno=exc.errno
        ) from exc
    with handle:
        return lint_lines(handle, source=name, options=options)
