"""Command line interface. Help, usage, errors and results follow ``--lang``."""

from __future__ import annotations

import argparse
import re
import sys
from typing import NoReturn

from . import __version__, i18n
from .core import InputError, InternalError, LintOptions, Report, lint_file, lint_lines
from .model import RULE_CODES
from .output import render

PROG = "tooldata-lint"


def _formatter_for(lang: str) -> type[argparse.HelpFormatter]:
    """A help formatter whose ``usage:`` prefix is in the chosen language."""

    class Formatter(argparse.HelpFormatter):
        def add_usage(self, usage, actions, groups, prefix=None):  # type: ignore[no-untyped-def]
            super().add_usage(usage, actions, groups, prefix or i18n.t(lang, "help.usage"))

    return Formatter


# Patterns of the English messages argparse produces; Korean output rewrites them.
_ARG_PATTERNS = (
    (re.compile(r"the following arguments are required: (?P<names>.+)"), "err.arg.required"),
    (
        re.compile(r"argument (?P<name>.+?): invalid choice: (?P<value>.+?) \(choose from (?P<choices>.+)\)$"),
        "err.arg.choice",
    ),
    (re.compile(r"unrecognized arguments: (?P<args>.+)"), "err.arg.unrecognized"),
    (re.compile(r"argument (?P<name>.+?): expected one argument"), "err.arg.expected"),
    (
        re.compile(r"ambiguous option: (?P<option>\S+) could match (?P<candidates>.+)"),
        "err.arg.ambiguous",
    ),
    (
        re.compile(r"argument (?P<name>.+?): ignored explicit argument (?P<value>.+)"),
        "err.arg.explicit",
    ),
)


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that reports its errors in the chosen language."""

    def __init__(self, *args, lang: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.lang = lang
        super().__init__(*args, **kwargs)

    def localize(self, message: str) -> str:
        """Korean rewrite of argparse's English message; English stays as argparse wrote it."""
        if self.lang == "en":
            return message
        for pattern, key in _ARG_PATTERNS:
            found = pattern.match(message)
            if found:
                return i18n.t(self.lang, key, **found.groupdict())
        return i18n.t(self.lang, "err.arg.other", message=message)

    def fail(self, message: str) -> NoReturn:
        """Print usage and an already-localized message, then exit with code 2."""
        self.print_usage(sys.stderr)
        prefix = i18n.t(self.lang, "err.prefix")
        sys.stderr.write(f"{self.prog}: {prefix}: {message}\n")
        raise SystemExit(2)

    def error(self, message: str) -> NoReturn:
        self.fail(self.localize(message))


def build_parser(lang: str) -> _Parser:
    t = lambda key: i18n.t(lang, key)  # noqa: E731 - tiny local alias
    extra = {"color": False} if sys.version_info >= (3, 14) else {}
    parser = _Parser(
        prog=PROG,
        lang=lang,
        add_help=False,
        description=t("help.description"),
        epilog=t("help.epilog"),
        formatter_class=_formatter_for(lang),
        **extra,
    )
    # Own argument groups so that their titles are localized (argparse's defaults are not).
    files = parser.add_argument_group(t("help.positional"))
    opts = parser.add_argument_group(t("help.options"))
    files.add_argument("files", nargs="+", metavar="FILE", help=t("help.files"))
    opts.add_argument("--format", choices=["text", "json"], default="text", metavar="FORMAT",
                      help=t("help.format") + " (text, json)")
    opts.add_argument("-o", "--output", metavar="OUT", help=t("help.output"))
    opts.add_argument("--fail-on", choices=["error", "warning"], default="error",
                      metavar="LEVEL", help=t("help.fail_on") + " (error, warning)")
    opts.add_argument("--ignore", default="", metavar="CODES", help=t("help.ignore"))
    opts.add_argument("--exit-zero", action="store_true", help=t("help.exit_zero"))
    opts.add_argument("--lang", choices=list(i18n.LANGS), metavar="LANG",
                      help=t("help.lang") + " (en, ko)")
    opts.add_argument("--version", action="version", version=f"{PROG} {__version__}",
                      help=t("help.version"))
    opts.add_argument("-h", "--help", action="help", help=t("help.help"))
    return parser


def _parse_ignore(parser: _Parser, text: str) -> frozenset[str]:
    codes = [c.strip().upper() for c in text.split(",") if c.strip()]
    unknown = [c for c in codes if c not in RULE_CODES]
    if unknown:
        parser.fail(
            i18n.t(parser.lang, "err.ignore_unknown", codes=", ".join(unknown),
                   known=", ".join(RULE_CODES))
        )
    return frozenset(codes)


def _run(files: list[str], options: LintOptions) -> Report:
    merged: Report | None = None
    for name in files:
        if name == "-":
            report = lint_lines(sys.stdin.buffer, "<stdin>", options)
        else:
            report = lint_file(name, options)
        if merged is None:
            merged = report
        else:
            merged.merge(report)
    assert merged is not None  # argparse guarantees at least one file
    return merged


def main(argv: list[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)
    # Language is needed before parsing so that help and usage errors are localized too.
    lang = i18n.resolve_lang(i18n.prescan_lang(args_in))
    parser = build_parser(lang)
    ns = parser.parse_args(args_in)
    lang = i18n.resolve_lang(ns.lang)
    if ns.files.count("-") > 1:
        parser.fail(i18n.t(lang, "err.stdin_twice"))
    options = LintOptions(ignore=_parse_ignore(parser, ns.ignore), lang=lang)

    try:
        sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

    try:
        report = _run(ns.files, options)
    except InputError as exc:
        key = f"err.input.{exc.kind}"
        detail = i18n.os_reason(lang, exc.errno, exc.detail)
        message = i18n.t(lang, key, path=exc.path, detail=detail)
        sys.stderr.write(f"{PROG}: {i18n.t(lang, 'err.prefix')}: {message}\n")
        return 2
    except InternalError as exc:
        message = i18n.t(lang, "err.internal", file=exc.file, line=exc.line, cause=exc.cause_text)
        sys.stderr.write(f"{PROG}: {i18n.t(lang, 'err.prefix')}: {message}\n")
        return 2

    text = render(report, ns.format)
    try:
        if ns.output:
            try:
                with open(ns.output, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
            except OSError as exc:
                message = i18n.t(lang, "err.output", path=ns.output, detail=i18n.os_reason(lang, exc.errno, exc.strerror or ""))
                sys.stderr.write(f"{PROG}: {i18n.t(lang, 'err.prefix')}: {message}\n")
                return 2
            sys.stderr.write(i18n.t(lang, "ui.wrote", path=ns.output) + "\n")
        else:
            sys.stdout.write(text)
            sys.stdout.flush()
    except BrokenPipeError:  # e.g. `tooldata-lint x.jsonl | head`
        sys.stderr.close()
    return 0 if ns.exit_zero else report.exit_code(ns.fail_on)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
