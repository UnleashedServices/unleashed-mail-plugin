#!/usr/bin/env python3
"""Zero-dependency stdio MCP server wrapping the deterministic synthesizer.

MCP over stdio is newline-delimited JSON-RPC 2.0 — a small, stable surface — so
this implements it directly with the standard library. No `mcp` SDK, no `uvx`, no
pip: it runs on the same bare `python3` the rest of this plugin's scripts use.
(If you'd rather use the official SDK, see README "Option B — FastMCP + uvx".)

Claude Code spawns this as a subprocess when the plugin is enabled, sends
`initialize` → `tools/list` → `tools/call`, and tears it down with the session.
It is NOT a hosted service: no port, no network, no secrets.

Protocol: read one JSON object per line on stdin; write one JSON object per line
on stdout. All logging goes to stderr (stdout is the protocol channel — never
print to it).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find schema/synthesize

from schema import FINDING_JSON_SCHEMA, parse_finding  # noqa: E402
from synthesize import render_markdown, synthesize       # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "review-synthesizer", "version": "0.1.0"}

TOOL = {
    "name": "synthesize_review",
    "title": "Deterministic review synthesizer",
    "description": (
        "Merge the reviewers' findings into one verdict, deterministically. "
        "Dedup is category-aware with line-range overlap; ownership rules re-route "
        "(never drop); blockers run through a verify gate; scope honors "
        "structural-pipeline. Returns a consolidated markdown report plus a "
        "structured verdict. Call this instead of doing Step 5 dedup in prose."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "findings": {
                "type": "array",
                "description": "Every reviewer's findings (+ your parity/test/verification rows).",
                "items": FINDING_JSON_SCHEMA,
            },
            "changed_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Repo-relative paths in $CHANGED (drives the scope filter).",
            },
        },
        "required": ["findings", "changed_files"],
    },
}


def _log(msg: str) -> None:
    print(f"[review-synthesizer] {msg}", file=sys.stderr, flush=True)


def _call_synthesize(arguments: dict) -> dict:
    findings, quarantined = [], []
    for d in arguments.get("findings", []):
        try:
            findings.append(parse_finding(d))
        except Exception as exc:  # noqa: BLE001 - quarantine, never drop
            quarantined.append((d, str(exc)))
    changed = set(arguments.get("changed_files", []))
    review = synthesize(findings, changed, quarantined=quarantined)
    v = review.verdict
    structured = {
        "verdict": v.decision,
        "confirmedBlockers": len(v.confirmed_blockers),
        "needsConfirmation": len(v.needs_confirmation),
        "clusters": len(review.clusters),
        "preExisting": len(review.pre_existing),
        "quarantined": len(review.quarantined),
    }
    return {
        "content": [{"type": "text", "text": render_markdown(review)}],
        "structuredContent": structured,
        "isError": False,
    }


def _handle(method: str, params: dict):
    """Return a result dict, or None for notifications (no reply)."""
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }
    if method == "notifications/initialized":
        return None  # notification — no response
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [TOOL]}
    if method == "tools/call":
        if params.get("name") != "synthesize_review":
            raise _RpcError(-32602, f"unknown tool: {params.get('name')!r}")
        return _call_synthesize(params.get("arguments") or {})
    raise _RpcError(-32601, f"method not found: {method}")


class _RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def main() -> int:
    _log("ready (stdio)")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _log("dropped non-JSON line")
            continue
        mid = msg.get("id")
        method = msg.get("method", "")
        try:
            result = _handle(method, msg.get("params") or {})
        except _RpcError as e:
            if mid is not None:
                _send({"jsonrpc": "2.0", "id": mid, "error": {"code": e.code, "message": e.message}})
            continue
        except Exception as e:  # noqa: BLE001 - tool/internal failure
            if mid is not None:
                _send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}})
            continue
        if mid is not None and result is not None:  # requests get a reply; notifications don't
            _send({"jsonrpc": "2.0", "id": mid, "result": result})
    return 0


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
