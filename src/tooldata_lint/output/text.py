"""Human-readable report: one line per issue, a distribution summary, a verdict line."""

from __future__ import annotations

import unicodedata

from .. import i18n
from ..core import Report
from ..model import Issue


def verdict(report: Report) -> str:
    """``No problems found`` or ``12 problems (11 errors, 1 warning)`` in the report language."""
    lang = report.lang
    total = len(report.issues)
    if total == 0:
        return i18n.t(lang, "ui.no_problems")
    parts = []
    if report.errors:
        key = "ui.word.error" if report.errors == 1 else "ui.word.errors"
        parts.append(i18n.t(lang, key, n=report.errors))
    if report.warnings:
        key = "ui.word.warning" if report.warnings == 1 else "ui.word.warnings"
        parts.append(i18n.t(lang, key, n=report.warnings))
    key = "ui.problems.one" if total == 1 else "ui.problems.many"
    return i18n.t(lang, key, total=total, parts=", ".join(parts))


def _issue_line(issue: Issue, lang: str) -> str:
    sev = i18n.t(lang, f"sev.{issue.severity.value}")
    where = f"  @ {issue.location}" if issue.location else ""
    return f"{issue.file}:{issue.line}  {issue.code}  {sev}  {issue.message}{where}"


def _summary_lines(report: Report) -> list[str]:
    lang = report.lang
    s = report.summary.to_dict()
    none = i18n.t(lang, "ui.summary.none")

    def pairs(d: dict[str, int], label: str | None = None) -> str:
        if not d:
            return none
        return ", ".join(
            f"{i18n.t(lang, f'ui.encoding.{k}') if label else k} {v}" for k, v in d.items()
        )

    rows = [
        (i18n.t(lang, "ui.summary.records"), f"{s['records']}"),
        (i18n.t(lang, "ui.summary.formats"), pairs(s["formats"])),
        (i18n.t(lang, "ui.summary.calls"), f"{s['calls']}"),
        (i18n.t(lang, "ui.summary.per_tool"), pairs(s["calls_per_tool"])),
        (
            i18n.t(lang, "ui.summary.no_call"),
            f"{s['no_call_records']} ({s['no_call_ratio'] * 100:.1f}%)",
        ),
        (
            i18n.t(lang, "ui.summary.parallel"),
            f"{s['parallel_call_records']} ({s['parallel_call_ratio'] * 100:.1f}%)",
        ),
        (i18n.t(lang, "ui.summary.encoding"), pairs(s["arguments_encoding"], "enc")),
    ]
    width = max(_display_width(label) for label, _ in rows)
    return [f"  {label}{' ' * (width - _display_width(label))}  {value}" for label, value in rows]


def _display_width(text: str) -> int:
    """Terminal columns: Hangul and other wide characters count as two."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def render(report: Report) -> str:
    lang = report.lang
    lines = [_issue_line(i, lang) for i in report.issues]
    if lines:
        lines.append("")
    lines.append(i18n.t(lang, "ui.summary"))
    lines.extend(_summary_lines(report))
    lines.append("")
    lines.append(verdict(report))
    return "\n".join(lines) + "\n"
