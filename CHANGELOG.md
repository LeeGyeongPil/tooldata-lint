# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-11-13

### Fixed
- A remote `$ref` in a tool schema was downloaded during linting, contrary to the documented
  behavior. It is now reported as S001 without any network request, and the deprecation
  warning from the schema library is gone. Local `$ref` and the built-in metaschema still work.

## [0.1.0] - 2026-11-12

### Added
- JSONL reader that reports broken lines (J001) and keeps going; 1-based file line numbers.
- Adapters for `messages` (OpenAI, HF/TRL, Axolotl) and ShareGPT (LLaMA-Factory) records.
- Rules S001, T001, T002, V001 (every JSON Schema violation of a call, with path and keyword),
  A001-A003, P001-P004, U001.
- Distribution summary, text and JSON output, `--fail-on`, `--ignore`, `--exit-zero`.
- English and Korean output (`--lang`, `TOOLDATA_LINT_LANG`, locale variables), including help
  and argument errors.
- Python API: `lint_file`, `lint_lines`, `lint_record`.
- Robust handling of unusual input: a tool call in the last message of a record is not reported
  as P001; an unresolvable `$ref` or a malformed container is reported as S001 instead of
  crashing; an empty file gives a U001 warning; schema validators are cached.
