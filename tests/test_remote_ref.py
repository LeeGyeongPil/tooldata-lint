"""A remote ``$ref`` in a tool schema is never downloaded; it is reported as S001."""

from __future__ import annotations

import http.server
import json
import threading
import warnings

import pytest

from tooldata_lint import lint_record


@pytest.fixture
def recording_server():
    hits: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            body = json.dumps({"type": "object", "required": ["zzz"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1], hits
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def record(parameters, arguments="{}"):
    return {
        "messages": [{"role": "assistant", "tool_calls": [
            {"type": "function", "function": {"name": "x", "arguments": arguments}}]}],
        "tools": [{"type": "function", "function": {"name": "x", "parameters": parameters}}],
    }


def test_remote_ref_is_s001_without_any_request(recording_server):
    port, hits = recording_server
    rec = record({"$ref": f"http://127.0.0.1:{port}/s.json"})
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any DeprecationWarning fails the test
        issues = lint_record(rec)
    assert [i.code for i in issues] == ["S001"]
    assert hits == []


def test_builtin_metaschema_ref_still_reports_v001():
    rec = record({"$ref": "https://json-schema.org/draft/2020-12/schema"}, arguments="[1]")
    codes = [i.code for i in lint_record(rec)]
    assert "V001" in codes and "S001" not in codes


def test_local_defs_ref_still_reports_v001():
    schema = {"$ref": "#/$defs/a", "$defs": {"a": {"type": "object", "required": ["city"]}}}
    codes = [i.code for i in lint_record(record(schema))]
    assert "V001" in codes and "S001" not in codes
