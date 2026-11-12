"""AC-6: English / Korean output."""

from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest

from tooldata_lint import i18n

from ._support import ROOT, run_cli


def test_lang_precedence():
    env = {"TOOLDATA_LINT_LANG": "en", "LC_ALL": "ko_KR.UTF-8", "LC_MESSAGES": "ko", "LANG": "ko"}
    assert i18n.resolve_lang("ko", env) == "ko"          # --lang wins
    assert i18n.resolve_lang(None, env) == "en"          # then TOOLDATA_LINT_LANG
    env.pop("TOOLDATA_LINT_LANG")
    assert i18n.resolve_lang(None, env) == "ko"          # then LC_ALL
    assert i18n.resolve_lang(None, {"LC_ALL": "en_US.UTF-8", "LANG": "ko_KR"}) == "en"
    assert i18n.resolve_lang(None, {"LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US"}) == "ko"
    assert i18n.resolve_lang(None, {"LANG": "ko_KR.UTF-8"}) == "ko"
    assert i18n.resolve_lang(None, {"LANG": "fr_FR.UTF-8"}) == "en"   # not Korean -> English
    assert i18n.resolve_lang(None, {"LANG": "C"}) == "en"
    assert i18n.resolve_lang(None, {}) == "en"


def test_lang_flag_beats_environment_in_the_cli():
    env = {"TOOLDATA_LINT_LANG": "ko"}
    assert "문제" in run_cli("examples/defects.jsonl", "--exit-zero", env=env).stdout
    assert "problems" in run_cli("examples/defects.jsonl", "--exit-zero", "--lang", "en", env=env).stdout
    assert "문제 12건 (오류 11건, 경고 1건)" in run_cli(
        "examples/defects.jsonl", "--exit-zero", "--lang=ko").stdout


def test_locale_variable_selects_korean():
    out = run_cli("examples/clean.jsonl", env={"TOOLDATA_LINT_LANG": "", "LANG": "ko_KR.UTF-8"})
    assert "문제가 없습니다" in out.stdout


def test_help_localized():
    ko = run_cli("--help", "--lang", "ko").stdout
    assert "사용법" in ko and "옵션" in ko and "usage" not in ko and "options" not in ko
    en = run_cli("--help", "--lang", "en").stdout
    assert "usage" in en and "options" in en and "사용법" not in en
    assert not re.search(r"[가-힣]", en)


def test_argparse_errors_localized():
    ko = run_cli("examples/clean.jsonl", "--format", "xml", "--lang", "ko")
    assert ko.returncode == 2 and "잘못된 선택" in ko.stderr and "사용법" in ko.stderr
    en = run_cli("examples/clean.jsonl", "--format", "xml", "--lang", "en")
    assert en.returncode == 2 and "invalid choice" in en.stderr and "usage" in en.stderr

    missing = run_cli("--lang", "ko")
    assert missing.returncode == 2 and "필수 인자가 빠졌습니다" in missing.stderr
    unknown = run_cli("examples/clean.jsonl", "--nope", "--lang", "ko")
    assert "알 수 없는 인자" in unknown.stderr
    no_value = run_cli("examples/clean.jsonl", "--format", "--lang", "ko")
    assert no_value.returncode == 2 and "값이 하나 필요합니다" in no_value.stderr
    bad_lang = run_cli("examples/clean.jsonl", "--lang", "fr")
    assert bad_lang.returncode == 2 and "invalid choice" in bad_lang.stderr


def test_input_errors_localized():
    ko = run_cli("nope.jsonl", "--lang", "ko")
    assert ko.returncode == 2 and "파일이 없습니다" in ko.stderr and "오류" in ko.stderr
    assert "도구 호출" not in ko.stderr
    assert "디렉터리입니다" in run_cli("examples", "--lang", "ko").stderr
    bad_ignore = run_cli("examples/clean.jsonl", "--ignore", "Z1", "--lang", "ko")
    assert "알 수 없는 규칙 코드" in bad_ignore.stderr


def test_catalog_keys_match():
    assert set(i18n.EN) == set(i18n.KO)
    for key in i18n.EN:
        en_fields = set(re.findall(r"{(\w+)}", i18n.EN[key]))
        ko_fields = set(re.findall(r"{(\w+)}", i18n.KO[key]))
        # the English V001 shows jsonschema's text; Korean builds a reason sentence instead
        if key == "issue.V001":
            continue
        if key.startswith("err.arg."):
            continue  # patterns of argparse's own English text
        assert en_fields == ko_fields, key


SENTENCE = re.compile(r"^(issue|err|help|kw)\.")
NOT_SENTENCES = {"help.usage", "help.positional", "help.options", "err.prefix"}


def test_ko_uses_hapnida_style():
    for key, text in i18n.KO.items():
        if not SENTENCE.match(key) or key in NOT_SENTENCES:
            continue
        if text.rstrip().endswith("}"):
            continue  # ends with a placeholder (checked on rendered output below)
        assert re.search(r"니다\.$|니까\?$", text), f"{key}: {text}"
        assert not re.search(r"요\.$|[해]라\.$|한다\.$|이다\.$|[는은]다\.$", text), key


def test_ko_rendered_output_ends_in_hapnida():
    out = run_cli("examples/defects.jsonl", "--lang", "ko", "--exit-zero").stdout
    for line in out.splitlines():
        if ":" in line.split("  ")[0] and "  @ " in line or re.match(r"\S+:\d+  [A-Z]\d{3}", line):
            message = line.split("  ", 3)[3].split("  @ ")[0]
            assert re.search(r"니다\.$", message), message
            assert not re.search(r"요\.$", message), message


def test_machine_output_is_language_independent():
    en = json.loads(run_cli("examples/defects.jsonl", "--format", "json", "--exit-zero", "--lang", "en").stdout)
    ko = json.loads(run_cli("examples/defects.jsonl", "--format", "json", "--exit-zero", "--lang", "ko").stdout)

    def strip(d):
        return {**d, "issues": [{k: v for k, v in i.items() if k != "message"} for i in d["issues"]]}

    assert strip(en) == strip(ko)
    assert en["issues"][0]["message"] != ko["issues"][0]["message"]
    assert {i["severity"] for i in ko["issues"]} == {"error", "warning"}


def test_every_issue_message_has_both_languages():
    keys = [k for k in i18n.EN if k.startswith("issue.")]
    assert keys and all(k in i18n.KO for k in keys)


def test_ko_text_has_no_english_labels():
    out = run_cli("examples/defects.jsonl", "--lang", "ko", "--exit-zero").stdout
    for word in ("Summary", "records", "problems", "error "):
        assert word not in out, word


@pytest.mark.parametrize("runner", ["unittest"])
def test_language_pinned_under_unittest(runner):
    """A Korean locale in the parent must not leak into ``python -m unittest``."""
    import os

    env = {**os.environ, "LANG": "ko_KR.UTF-8", "LC_ALL": "ko_KR.UTF-8", "PYTHONUTF8": "1"}
    env.pop("TOOLDATA_LINT_LANG", None)
    # Pinning happens when tests/_support is imported (tests/__init__.py), so the
    # child below must still see English although it starts with a Korean locale.
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "tests._lang_probe", "-v"],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stderr
