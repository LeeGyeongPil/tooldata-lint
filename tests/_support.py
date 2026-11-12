"""Shared test helpers.

Importing this module pins the output language to English *at import time* and removes
locale variables, so ``pytest`` and ``python -m unittest`` give the same results on a
machine whose locale is Korean (``LANG=ko_KR.UTF-8``). ``tests/__init__.py`` imports it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ["TOOLDATA_LINT_LANG"] = "en"
for _name in ("LC_ALL", "LC_MESSAGES", "LANG"):
    os.environ.pop(_name, None)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
FIXTURES = ROOT / "tests" / "fixtures"
DEFECTS = EXAMPLES / "defects.jsonl"
CLEAN = EXAMPLES / "clean.jsonl"

# The (line, code) set documented for examples/defects.jsonl (see README, "What it checks").
DEFECT_CODES = {
    (3, "V001"), (4, "T001"), (5, "P001"), (5, "P002"), (6, "A002"),
    (7, "J001"), (9, "V001"), (10, "A003"), (11, "S001"), (12, "A001"),
}


def run_cli(*args: str, env: dict[str, str] | None = None, stdin: str | None = None):
    """Run the CLI in a child process; output is decoded as UTF-8 explicitly."""
    child_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    if env:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "tooldata_lint", *args],
        cwd=ROOT, env=child_env, input=stdin, capture_output=True,
        text=True, encoding="utf-8", timeout=120,
    )
