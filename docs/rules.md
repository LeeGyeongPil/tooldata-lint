# Rule reference

Every finding has a rule code, a severity and a 1-based line number of the input file.
`error` makes the exit code 1; `warning` only does with `--fail-on warning`.
Use `--ignore CODE[,CODE]` to drop codes.

| Code | Severity | Meaning | Typical fix |
|---|---|---|---|
| J001 | error | The line is not valid JSON (or not UTF-8). Linting continues with the next line. | Fix or remove the line. |
| U001 | warning | Record is neither a `messages` nor a `conversations` record (skipped), or the file has no records at all (empty or blank lines only). | Convert it or exclude it from the file; check the step that wrote an empty file. |
| S001 | error | A tool's `parameters` is not a valid JSON Schema, has a `$ref` that cannot be resolved (references are never fetched), or `tools` has the wrong shape; also a `tool_calls` that is not a list or a message/call that is not an object. Calls to that tool are not validated. | Fix the schema; check the `path` and `keyword` in the message. |
| T001 | error | The call names a tool that is not in the record's `tools`. | Add the tool definition or fix the call name. |
| T002 | error | The record has tool calls but no `tools` at all (reported once per record). | Add `tools` to the record. |
| V001 | error | The call's arguments violate the tool's JSON Schema. One finding per violation, with `json_path` and the failing `keyword` (`enum`, `required`, `type`, `additionalProperties`, ...). | Fix the arguments or the schema. |
| A001 | error | `arguments` is a string that is not valid JSON, or is missing/null. | Produce valid JSON. |
| A002 | error | `arguments` is double-encoded: the JSON string decodes to another string. | Encode once. |
| A003 | warning | One record mixes string and object `arguments`. | Use one encoding per dataset. |
| P001 | error | A tool call has no tool response, although the conversation goes on after the call. A call in the **last** message of the record is the training label (OpenAI fine-tuning layout) and is not reported. | Add the response or remove the call. |
| P002 | error | A tool response has no matching call. | Fix the id or remove the response. |
| P003 | error | The same call id appears twice in one record. | Make ids unique. |
| P004 | warning | Some calls have ids and some do not. Records with no ids at all are paired by order and are not reported. | Add the missing ids. |

## Exit codes

`0` no problems at the chosen level, `1` problems found, `2` tool error (usage, unreadable input or output file, internal error).

## How calls and responses are paired

- If any call or response in the record has an id, responses are matched to calls by id.
- Otherwise they are matched in order (first response answers the oldest open call).
- In ShareGPT (LLaMA-Factory) one `observation` turn answers every call of the preceding
  `function_call` turn.

## Formats

| Format | Detected by | Notes |
|---|---|---|
| OpenAI / HF / TRL / Axolotl | `messages` list | `arguments` is a JSON string (OpenAI) or an object (HF); `tools` may be a list or a JSON string. |
| ShareGPT (LLaMA-Factory) | `conversations` list | `function_call` turns (object or array for parallel calls) and `observation` turns. |

The same rules run on every format.
