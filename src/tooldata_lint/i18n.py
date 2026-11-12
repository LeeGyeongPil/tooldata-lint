"""Language selection and every user-visible string (English and Korean).

Machine-readable output (JSON keys, rule codes, SARIF) never changes with the language;
only human-readable text does. Korean sentences use one style (hapnida) throughout.
"""

from __future__ import annotations

import errno
import os
from collections.abc import Mapping
from typing import Any

LANGS = ("en", "ko")
ENV_VAR = "TOOLDATA_LINT_LANG"


def normalize(value: str | None) -> str | None:
    """Map a locale-like value (``ko_KR.UTF-8``, ``en``, ``C``) to ``ko`` / ``en`` / None."""
    if not value:
        return None
    return "ko" if value.strip().lower().startswith("ko") else "en"


def resolve_lang(cli_value: str | None = None, env: Mapping[str, str] | None = None) -> str:
    """``--lang`` > TOOLDATA_LINT_LANG > LC_ALL > LC_MESSAGES > LANG; not Korean -> English."""
    env = os.environ if env is None else env
    if cli_value in LANGS:
        return cli_value  # type: ignore[return-value]
    for name in (ENV_VAR, "LC_ALL", "LC_MESSAGES", "LANG"):
        found = normalize(env.get(name))
        if found:
            return found
    return "en"


def prescan_lang(argv: list[str]) -> str | None:
    """Find ``--lang X`` / ``--lang=X`` in raw argv so help and errors can be localized."""
    for i, arg in enumerate(argv):
        if arg == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--lang="):
            return arg.split("=", 1)[1]
    return None


def t(lang: str, key: str, **params: Any) -> str:
    """Look up ``key`` in the catalog for ``lang`` and fill in the placeholders."""
    return MESSAGES[lang][key].format(**params)


EN: dict[str, str] = {
    # --- issues (message per rule code) ---
    "issue.J001": "Line is not valid JSON (syntax error at column {col}).",
    "issue.J001.utf8": "Line is not valid UTF-8.",
    "issue.U001": "Unrecognized record format (expected a 'messages' or 'conversations' list); record skipped.",
    "issue.U001.empty": "File has no records (it is empty or contains only blank lines).",
    "issue.S001": "Parameters of tool '{tool}' are not a valid JSON Schema (at {path}, keyword {keyword}).",
    "issue.S001.tools_json": "'tools' is a string but not valid JSON.",
    "issue.S001.tools_type": "'tools' must be a list of tool definitions.",
    "issue.S001.tools_shape": "tools[{index}] is not a tool definition with a name.",
    "issue.S001.calls_type": "{where} must be a list of tool calls.",
    "issue.S001.item_type": "{where} is not an object.",
    "issue.S001.ref": "Schema of tool '{tool}' has a $ref that cannot be resolved ({ref}); its calls are not validated.",
    "issue.T001": "Call to undefined tool '{tool}' (defined: {defined}).",
    "issue.T001.noname": "Tool call has no tool name.",
    "issue.T002": "Record has {n} tool call(s) but defines no tools.",
    "issue.V001": "Arguments for '{tool}' violate its schema at {path} [{keyword}]: {detail}",
    "issue.A001": "Arguments of '{tool}' are a string that is not valid JSON.",
    "issue.A001.turn": "The function_call turn is not valid JSON.",
    "issue.A001.missing": "Tool call '{tool}' has no arguments (the field is missing or null).",
    "issue.A002": "Arguments of '{tool}' are double-encoded (the JSON string decodes to another string).",
    "issue.A003": "Record mixes string and object arguments ({strings} string, {objects} object).",
    "issue.P001": "Tool call {call} has no matching tool response.",
    "issue.P002": "Tool response ({ref}) has no matching tool call.",
    "issue.P003": "Duplicate tool call id '{id}'.",
    "issue.P004": "Tool call '{tool}' has no id although other calls or responses in this record use ids.",
    "ui.noname": "<no name>",
    "ref.id": "id {id}",
    "ref.pos": "#{n}",
    "call.id": "'{tool}' (id {id})",
    "call.pos": "'{tool}' (call #{n})",
    # --- per-keyword reasons (used for Korean V001 only; English shows the jsonschema text) ---
    "kw.default": "The schema condition '{keyword}' is not satisfied.",
    "kw.required": "Missing required property: {missing}.",
    "kw.additionalProperties": "Unexpected property: {extra}.",
    "kw.enum": "Value {value} is not one of {allowed}.",
    "kw.type": "Expected type {expected} but got {value}.",
    "kw.const": "Value {value} is not the required constant {limit}.",
    "kw.minimum": "Value {value} is below the minimum {limit}.",
    "kw.maximum": "Value {value} is above the maximum {limit}.",
    "kw.minLength": "Value {value} is shorter than {limit}.",
    "kw.maxLength": "Value {value} is longer than {limit}.",
    "kw.pattern": "Value {value} does not match the pattern {limit}.",
    "kw.minItems": "Array {value} has fewer than {limit} items.",
    "kw.maxItems": "Array {value} has more than {limit} items.",
    # --- severity words, summary and verdict ---
    "sev.error": "error",
    "sev.warning": "warning",
    "ui.no_problems": "No problems found",
    "ui.problems.one": "{total} problem ({parts})",
    "ui.problems.many": "{total} problems ({parts})",
    "ui.word.error": "{n} error",
    "ui.word.errors": "{n} errors",
    "ui.word.warning": "{n} warning",
    "ui.word.warnings": "{n} warnings",
    "ui.summary": "Summary",
    "ui.summary.records": "records",
    "ui.summary.formats": "formats",
    "ui.summary.calls": "tool calls",
    "ui.summary.per_tool": "calls per tool",
    "ui.summary.no_call": "records without calls",
    "ui.summary.parallel": "records with parallel calls",
    "ui.summary.encoding": "arguments encoding",
    "ui.summary.none": "none",
    "ui.encoding.string": "string",
    "ui.encoding.object": "object",
    "ui.encoding.other": "other",
    "ui.wrote": "Report written to {path}.",
    # --- errors ---
    "err.prefix": "error",
    "err.input.not_found": "Cannot open '{path}': the file does not exist.",
    "err.input.permission": "Cannot open '{path}': permission denied.",
    "err.input.is_dir": "Cannot open '{path}': it is a directory.",
    "err.input.other": "Cannot open '{path}': {detail}",
    "err.output": "Cannot write '{path}': {detail}",
    "err.internal": "Internal error while checking {file} line {line}: {cause}. This is a bug in tooldata-lint; please report it with that line.",
    "os.ENOENT": "the path or its directory does not exist",
    "os.EACCES": "permission denied",
    "os.EPERM": "operation not permitted",
    "os.EISDIR": "the path is a directory",
    "os.ENOTDIR": "a part of the path is not a directory",
    "os.ENOSPC": "no space left on the device",
    "os.EROFS": "the file system is read-only",
    "os.ENAMETOOLONG": "the file name is too long",
    "os.EMFILE": "too many open files",
    "os.other": "operating system error {errno}",
    "err.stdin_twice": "Standard input ('-') can only be given once.",
    "err.arg.required": "the following arguments are required: {names}",
    "err.arg.choice": "argument {name}: invalid choice: {value} (choose from {choices})",
    "err.arg.unrecognized": "unrecognized arguments: {args}",
    "err.arg.expected": "argument {name}: expected one argument",
    "err.arg.ambiguous": "ambiguous option: {option} could match {candidates}",
    "err.arg.explicit": "argument {name}: ignored explicit argument {value}",
    "err.arg.other": "{message}",
    # --- command line help ---
    "help.usage": "usage: ",
    "help.positional": "positional arguments",
    "help.options": "options",
    "help.description": "Lint tool-calling fine-tuning data (JSONL) before training.",
    "help.files": "JSONL files to check; '-' reads standard input.",
    "help.format": "Output format.",
    "help.output": "Write the report to this file instead of standard output.",
    "help.fail_on": "Lowest severity that makes the exit code 1.",
    "help.ignore": "Comma-separated rule codes to ignore, for example J001,P004.",
    "help.exit_zero": "Always exit with 0, even if problems are found.",
    "help.lang": "Output language (default: from TOOLDATA_LINT_LANG, LC_ALL, LC_MESSAGES, LANG).",
    "help.version": "Show the version and exit.",
    "help.help": "Show this help message and exit.",
    "help.epilog": "Exit codes: 0 no problems at the chosen level, 1 problems found, 2 usage or input error.",
    "err.ignore_unknown": "Unknown rule code(s) in --ignore: {codes}. Known codes: {known}.",
}

KO: dict[str, str] = {
    "issue.J001": "이 줄은 올바른 JSON 이 아닙니다. {col}번째 열에서 구문 오류가 발생했습니다.",
    "issue.J001.utf8": "이 줄은 올바른 UTF-8 이 아닙니다.",
    "issue.U001": "알 수 없는 레코드 형식이므로 건너뜁니다. 'messages' 또는 'conversations' 목록이 필요합니다.",
    "issue.U001.empty": "파일에 레코드가 없습니다. 파일이 비어 있거나 빈 줄만 있습니다.",
    "issue.S001": "도구 '{tool}' 의 parameters 가 올바른 JSON Schema 가 아닙니다. 위반 위치는 {path}, 키워드는 {keyword}입니다.",
    "issue.S001.tools_json": "'tools' 가 문자열이지만 올바른 JSON 이 아닙니다.",
    "issue.S001.tools_type": "'tools' 는 도구 정의 목록이어야 합니다.",
    "issue.S001.tools_shape": "tools[{index}] 는 이름이 있는 도구 정의가 아닙니다.",
    "issue.S001.calls_type": "{where}: 도구 호출 목록(list)이어야 합니다.",
    "issue.S001.item_type": "{where}: 객체(object)가 아닙니다.",
    "issue.S001.ref": "도구 '{tool}' 의 스키마에 해석할 수 없는 $ref 가 있어 이 도구의 호출은 검사하지 않습니다. 상세는 {ref}입니다.",
    "issue.T001": "정의에 없는 도구를 호출합니다. 호출한 도구는 '{tool}', 정의된 도구는 {defined}입니다.",
    "issue.T001.noname": "도구 호출에 도구 이름이 없습니다.",
    "issue.T002": "도구 호출이 {n}건 있지만 레코드에 tools 정의가 없습니다.",
    "issue.V001": "도구 '{tool}' 의 인자가 스키마를 위반합니다. 위치는 {path}, 키워드는 {keyword}입니다. {reason}",
    "issue.A001": "도구 '{tool}' 의 arguments 문자열이 올바른 JSON 이 아닙니다.",
    "issue.A001.turn": "function_call 턴의 값이 올바른 JSON 이 아닙니다.",
    "issue.A001.missing": "도구 '{tool}' 호출에 arguments 가 없습니다. 필드가 없거나 null 입니다.",
    "issue.A002": "도구 '{tool}' 의 arguments 가 이중 인코딩되어 있습니다. JSON 문자열을 풀어도 다시 문자열이 나옵니다.",
    "issue.A003": "한 레코드에 문자열 arguments {strings}건과 객체 arguments {objects}건이 섞여 있습니다.",
    "issue.P001": "도구 호출 {call} 에 짝이 되는 도구 응답이 없습니다.",
    "issue.P002": "도구 응답 ({ref}) 에 짝이 되는 도구 호출이 없습니다.",
    "issue.P003": "도구 호출 id '{id}' 가 중복됩니다.",
    "issue.P004": "이 레코드는 다른 호출이나 응답에서 id 를 쓰는데 도구 '{tool}' 호출에는 id 가 없습니다.",
    "ui.noname": "<이름 없음>",
    "ref.id": "id {id}",
    "ref.pos": "{n}번째",
    "call.id": "'{tool}' (id {id})",
    "call.pos": "'{tool}' ({n}번째 호출)",
    "kw.default": "스키마의 '{keyword}' 조건을 만족하지 않습니다.",
    "kw.required": "필수 속성 {missing} 이(가) 없습니다.",
    "kw.additionalProperties": "허용되지 않은 속성 {extra} 이(가) 있습니다.",
    "kw.enum": "값 {value} 은(는) 허용 값 {allowed} 중 하나가 아닙니다.",
    "kw.type": "타입은 {expected} 이어야 하지만 값은 {value} 입니다.",
    "kw.const": "값 {value} 은(는) 고정 값 {limit} 과(와) 다릅니다.",
    "kw.minimum": "값 {value} 이(가) 최솟값 {limit} 보다 작습니다.",
    "kw.maximum": "값 {value} 이(가) 최댓값 {limit} 보다 큽니다.",
    "kw.minLength": "값 {value} 의 길이가 {limit} 보다 짧습니다.",
    "kw.maxLength": "값 {value} 의 길이가 {limit} 보다 깁니다.",
    "kw.pattern": "값 {value} 이(가) 패턴 {limit} 과(와) 맞지 않습니다.",
    "kw.minItems": "배열 {value} 의 항목이 {limit}개보다 적습니다.",
    "kw.maxItems": "배열 {value} 의 항목이 {limit}개보다 많습니다.",
    "sev.error": "오류",
    "sev.warning": "경고",
    "ui.no_problems": "문제가 없습니다",
    "ui.problems.one": "문제 {total}건 ({parts})",
    "ui.problems.many": "문제 {total}건 ({parts})",
    "ui.word.error": "오류 {n}건",
    "ui.word.errors": "오류 {n}건",
    "ui.word.warning": "경고 {n}건",
    "ui.word.warnings": "경고 {n}건",
    "ui.summary": "요약",
    "ui.summary.records": "레코드",
    "ui.summary.formats": "형식",
    "ui.summary.calls": "도구 호출",
    "ui.summary.per_tool": "도구별 호출",
    "ui.summary.no_call": "호출 없는 레코드",
    "ui.summary.parallel": "병렬 호출 레코드",
    "ui.summary.encoding": "arguments 인코딩",
    "ui.summary.none": "없음",
    "ui.encoding.string": "문자열",
    "ui.encoding.object": "객체",
    "ui.encoding.other": "기타",
    "ui.wrote": "보고서를 {path} 에 저장했습니다.",
    "err.prefix": "오류",
    "err.input.not_found": "'{path}' 파일을 열 수 없습니다. 파일이 없습니다.",
    "err.input.permission": "'{path}' 파일을 열 수 없습니다. 권한이 없습니다.",
    "err.input.is_dir": "'{path}' 파일을 열 수 없습니다. 디렉터리입니다.",
    "err.input.other": "'{path}' 파일을 열 수 없습니다. {detail}",
    "err.output": "'{path}' 파일에 쓸 수 없습니다. {detail}",
    "err.internal": "{file} 의 {line}번째 줄을 검사하는 중 내부 오류가 발생했습니다. 원인은 {cause}입니다. tooldata-lint 의 버그이므로 해당 줄과 함께 제보해 주시기 바랍니다.",
    "os.ENOENT": "경로 또는 상위 디렉터리가 없습니다.",
    "os.EACCES": "권한이 없습니다.",
    "os.EPERM": "허용되지 않는 작업입니다.",
    "os.EISDIR": "경로가 디렉터리입니다.",
    "os.ENOTDIR": "경로의 일부가 디렉터리가 아닙니다.",
    "os.ENOSPC": "저장 장치에 남은 공간이 없습니다.",
    "os.EROFS": "읽기 전용 파일 시스템입니다.",
    "os.ENAMETOOLONG": "파일 이름이 너무 깁니다.",
    "os.EMFILE": "열려 있는 파일이 너무 많습니다.",
    "os.other": "운영체제 오류가 발생했습니다. 오류 번호는 {errno}입니다.",
    "err.stdin_twice": "표준 입력('-')은 한 번만 줄 수 있습니다.",
    "err.arg.required": "필수 인자가 빠졌습니다. 빠진 인자는 {names}입니다.",
    "err.arg.choice": "인자 {name}: 잘못된 선택입니다. {value} 값은 사용할 수 없으며 {choices} 중 하나여야 합니다.",
    "err.arg.unrecognized": "알 수 없는 인자가 있습니다. 해당 인자는 {args}입니다.",
    "err.arg.expected": "인자 {name}: 값이 하나 필요합니다.",
    "err.arg.ambiguous": "모호한 옵션입니다. {option} 에 해당하는 후보는 {candidates}입니다.",
    "err.arg.explicit": "인자 {name}: 값을 받지 않는 옵션에 값 {value} 이(가) 주어졌습니다.",
    "err.arg.other": "인자 오류입니다. 원문은 {message} 입니다.",
    "help.usage": "사용법: ",
    "help.positional": "위치 인자",
    "help.options": "옵션",
    "help.description": "학습 전에 도구 호출 학습 데이터(JSONL)를 검사합니다.",
    "help.files": "검사할 JSONL 파일입니다. '-' 는 표준 입력을 읽습니다.",
    "help.format": "출력 형식을 고릅니다.",
    "help.output": "보고서를 표준 출력 대신 이 파일에 씁니다.",
    "help.fail_on": "종료 코드를 1로 만드는 가장 낮은 심각도를 정합니다.",
    "help.ignore": "무시할 규칙 코드를 쉼표로 구분해 줍니다. 예는 J001,P004 입니다.",
    "help.exit_zero": "문제가 있어도 항상 종료 코드 0으로 끝냅니다.",
    "help.lang": "출력 언어를 정합니다. 기본값은 TOOLDATA_LINT_LANG, LC_ALL, LC_MESSAGES, LANG 순으로 정합니다.",
    "help.version": "버전을 표시하고 끝냅니다.",
    "help.help": "이 도움말을 표시하고 끝냅니다.",
    "help.epilog": "종료 코드는 0이 문제 없음, 1이 문제 발견, 2가 사용법 또는 입력 오류입니다.",
    "err.ignore_unknown": "--ignore 에 알 수 없는 규칙 코드가 있습니다: {codes}. 사용할 수 있는 코드는 {known}입니다.",
}

MESSAGES: dict[str, dict[str, str]] = {"en": EN, "ko": KO}


def reason_for(lang: str, keyword: str, kw: dict[str, str]) -> str:
    """Localized one-sentence explanation of a failed schema keyword."""
    key = f"kw.{keyword}"
    cat = MESSAGES[lang]
    template = cat.get(key) or cat["kw.default"]
    values = {"keyword": keyword, **kw}
    try:
        return template.format(**values)
    except KeyError:
        return cat["kw.default"].format(keyword=keyword)


def os_reason(lang: str, errno_: int | None, strerror: str = "") -> str:
    """Localized reason for an OS error number (known codes) with a safe fallback."""
    name = errno.errorcode.get(errno_) if errno_ is not None else None
    key = f"os.{name}"
    if key in MESSAGES[lang]:
        return t(lang, key)
    return t(lang, "os.other", strerror=strerror or "unknown error", errno=errno_ if errno_ is not None else "?")


def _call_label(lang: str, tool: Any, call_id: Any, n: Any) -> str:
    tool = tool or t(lang, "ui.noname")
    if call_id:
        return t(lang, "call.id", tool=tool, id=call_id)
    return t(lang, "call.pos", tool=tool, n=n)


def render_message(lang: str, code: str, variant: str | None, params: Mapping[str, Any]) -> str:
    """Build the human-readable message of a finding in ``lang``."""
    key = f"issue.{code}" + (f".{variant}" if variant else "")
    p = dict(params)
    if "tool" in p and not p["tool"]:
        p["tool"] = t(lang, "ui.noname")  # never print Python's None
    if code == "V001":
        p["reason"] = reason_for(lang, str(p["keyword"]), p.get("kw", {})) if lang == "ko" else ""
    elif code == "P001":
        p["call"] = _call_label(lang, p.get("tool"), p.get("id"), p.get("n"))
    elif code == "P002":
        p["ref"] = (
            t(lang, "ref.id", id=p["id"]) if p.get("id") else t(lang, "ref.pos", n=p.get("n"))
        )
    return t(lang, key, **p).rstrip()
