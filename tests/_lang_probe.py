"""Run by test_i18n through ``python -m unittest``; not collected by pytest (name)."""

import unittest

from tooldata_lint import i18n

from ._support import run_cli


class LanguagePinned(unittest.TestCase):
    def test_resolves_english(self) -> None:
        self.assertEqual(i18n.resolve_lang(), "en")

    def test_cli_prints_english(self) -> None:
        result = run_cli("examples/clean.jsonl")
        self.assertIn("No problems found", result.stdout)
