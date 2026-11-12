"""AC-4: exit codes and CLI options."""

from __future__ import annotations

import json

from ._support import CLEAN, DEFECTS, ROOT, run_cli


def test_exit_codes(tmp_path):
    clean = run_cli("examples/clean.jsonl")
    assert clean.returncode == 0 and "No problems found" in clean.stdout.splitlines()[-1]

    defects = run_cli("examples/defects.jsonl")
    assert defects.returncode == 1
    assert "12 problems (11 errors, 1 warning)" in defects.stdout

    missing = run_cli("no-such-file.jsonl")
    assert missing.returncode == 2
    assert "does not exist" in missing.stderr and missing.stdout == ""

    assert run_cli("examples/defects.jsonl", "--exit-zero").returncode == 0

    # Only a warning (A003): exit 0 by default, 1 with --fail-on warning.
    warn = tmp_path / "warn.jsonl"
    line10 = DEFECTS.read_text(encoding="utf-8").splitlines()[9]
    warn.write_text(line10 + "\n", encoding="utf-8")
    assert run_cli(str(warn)).returncode == 0
    assert run_cli(str(warn), "--fail-on", "warning").returncode == 1

    # --ignore removes codes from the output and from the exit code.
    only_a001 = tmp_path / "a001.jsonl"
    only_a001.write_text(DEFECTS.read_text(encoding="utf-8").splitlines()[11] + "\n", encoding="utf-8")
    assert run_cli(str(only_a001)).returncode == 1
    ignored = run_cli(str(only_a001), "--ignore", "a001")
    assert ignored.returncode == 0 and "A001" not in ignored.stdout


def test_directory_input_is_exit_2():
    result = run_cli("examples")
    assert result.returncode == 2 and "directory" in result.stderr


def test_unknown_ignore_code_is_a_usage_error():
    result = run_cli("examples/clean.jsonl", "--ignore", "X999")
    assert result.returncode == 2 and "X999" in result.stderr and "V001" in result.stderr


def test_reads_stdin_and_multiple_files():
    result = run_cli("-", "examples/clean.jsonl", stdin=DEFECTS.read_text(encoding="utf-8"))
    assert result.returncode == 1
    assert "<stdin>:3  V001" in result.stdout
    assert "records" in result.stdout


def test_stdin_twice_is_rejected():
    assert run_cli("-", "-", stdin="").returncode == 2


def test_output_file(tmp_path):
    out = tmp_path / "report.json"
    result = run_cli("examples/defects.jsonl", "--format", "json", "-o", str(out), "--exit-zero")
    assert result.returncode == 0 and result.stdout == ""
    assert json.loads(out.read_text(encoding="utf-8"))["counts"]["total"] == 12
    assert str(out) in result.stderr


def test_output_file_in_missing_directory_is_exit_2(tmp_path):
    result = run_cli("examples/clean.jsonl", "-o", str(tmp_path / "nope" / "r.txt"))
    assert result.returncode == 2 and "Cannot write" in result.stderr


def test_version_and_module_entry_point():
    result = run_cli("--version")
    assert result.returncode == 0 and result.stdout.startswith("tooldata-lint ")


def test_text_output_lines_have_file_line_code():
    out = run_cli("examples/defects.jsonl", "--exit-zero").stdout
    assert f"examples/defects.jsonl:12  A001  error  " in out
    assert CLEAN.exists() and ROOT.exists()
