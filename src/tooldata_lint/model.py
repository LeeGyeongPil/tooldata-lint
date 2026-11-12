"""Data classes shared by every module: the normalized record and the findings."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class Severity(str, enum.Enum):
    """Severity of an issue. Values are stable strings used in JSON output."""

    ERROR = "error"
    WARNING = "warning"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


# Default severity per rule code. Codes are part of the public interface.
SEVERITY: dict[str, Severity] = {
    "J001": Severity.ERROR,
    "U001": Severity.WARNING,
    "S001": Severity.ERROR,
    "T001": Severity.ERROR,
    "T002": Severity.ERROR,
    "V001": Severity.ERROR,
    "A001": Severity.ERROR,
    "A002": Severity.ERROR,
    "A003": Severity.WARNING,
    "P001": Severity.ERROR,
    "P002": Severity.ERROR,
    "P003": Severity.ERROR,
    "P004": Severity.WARNING,
}

RULE_CODES: tuple[str, ...] = tuple(SEVERITY)


@dataclass(frozen=True)
class Issue:
    """One finding, tied to a 1-based line of the input file."""

    file: str
    line: int
    code: str
    severity: Severity
    message: str
    location: str | None = None
    json_path: str | None = None
    keyword: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready dict. Keys never depend on the output language."""
        return {
            "file": self.file,
            "line": self.line,
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "location": self.location,
            "json_path": self.json_path,
            "keyword": self.keyword,
            "detail": self.detail,
        }


@dataclass
class Finding:
    """A language-neutral finding. Rendered into an Issue by ``core``."""

    code: str
    params: dict[str, Any] = field(default_factory=dict)
    variant: str | None = None
    location: str | None = None
    json_path: str | None = None
    keyword: str | None = None
    detail: str | None = None


@dataclass
class ToolDef:
    """A tool definition normalized from any supported ``tools`` shape."""

    name: str
    description: str | None
    parameters: Any
    schema_ok: bool = True


@dataclass
class Call:
    """One tool call found in a record."""

    name: str | None
    id: str | None
    arguments: Any
    turn: int
    location: str
    index: int  # 1-based position among the calls of the record


@dataclass
class Response:
    """One tool response (role ``tool`` / ``observation``)."""

    id: str | None
    location: str
    index: int  # 1-based position among the responses of the record
    answers_turn: bool = False  # one response answers every call of a turn (ShareGPT)


@dataclass
class Record:
    """Format-independent view of one training record."""

    format: str
    tools: dict[str, ToolDef] = field(default_factory=dict)
    tools_present: bool = False
    # Calls and responses in conversation order: ("call", Call) or ("response", Response)
    events: list[tuple[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    # Index of the last message/turn of the record; a call in that turn is a "trailing call".
    last_turn: int = -1

    @property
    def calls(self) -> list[Call]:
        return [e for kind, e in self.events if kind == "call"]

    @property
    def responses(self) -> list[Response]:
        return [e for kind, e in self.events if kind == "response"]


@dataclass
class Summary:
    """Distribution summary over everything that was linted."""

    lines: int = 0
    records: int = 0
    formats: dict[str, int] = field(default_factory=dict)
    calls: int = 0
    calls_per_tool: dict[str, int] = field(default_factory=dict)
    no_call_records: int = 0
    parallel_call_records: int = 0
    arguments_encoding: dict[str, int] = field(
        default_factory=lambda: {"string": 0, "object": 0, "other": 0}
    )

    def add_record(self, rec: Record) -> None:
        self.records += 1
        self.formats[rec.format] = self.formats.get(rec.format, 0) + 1
        calls = rec.calls
        self.calls += len(calls)
        if not calls:
            self.no_call_records += 1
        turns: dict[int, int] = {}
        for call in calls:
            key = call.name if isinstance(call.name, str) else "?"
            self.calls_per_tool[key] = self.calls_per_tool.get(key, 0) + 1
            turns[call.turn] = turns.get(call.turn, 0) + 1
            self.arguments_encoding[encoding_of(call.arguments)] += 1
        if any(n >= 2 for n in turns.values()):
            self.parallel_call_records += 1

    def merge(self, other: Summary) -> None:
        self.lines += other.lines
        self.records += other.records
        self.calls += other.calls
        self.no_call_records += other.no_call_records
        self.parallel_call_records += other.parallel_call_records
        for src, dst in (
            (other.formats, self.formats),
            (other.calls_per_tool, self.calls_per_tool),
            (other.arguments_encoding, self.arguments_encoding),
        ):
            for k, v in src.items():
                dst[k] = dst.get(k, 0) + v

    def to_dict(self) -> dict[str, Any]:
        rec = self.records or 1
        return {
            "lines": self.lines,
            "records": self.records,
            "formats": dict(sorted(self.formats.items())),
            "calls": self.calls,
            "calls_per_tool": dict(sorted(self.calls_per_tool.items())),
            "no_call_records": self.no_call_records,
            "no_call_ratio": round(self.no_call_records / rec, 4) if self.records else 0.0,
            "parallel_call_records": self.parallel_call_records,
            "parallel_call_ratio": (
                round(self.parallel_call_records / rec, 4) if self.records else 0.0
            ),
            "arguments_encoding": dict(self.arguments_encoding),
        }


def encoding_of(arguments: Any) -> str:
    """``string`` (OpenAI style), ``object`` (HF style) or ``other``."""
    if isinstance(arguments, str):
        return "string"
    if isinstance(arguments, dict):
        return "object"
    return "other"
