#!/usr/bin/env python3
"""Zero-dependency stdio MCP server: deterministic review synthesis.

MCP over stdio is newline-delimited JSON-RPC 2.0 — a small, stable surface — so
this implements it with the standard library only. No `mcp` SDK, no `uvx`, no pip:
it runs on the same bare `python3` as the rest of this plugin's scripts. Claude
Code spawns it as a subprocess when the plugin is enabled and tears it down with
the session. It is NOT a hosted service: no port, no network, no secrets.

DIVISION OF LABOUR (important): this server is pure compute with **no repo
access**. It owns the part that can silently drop a finding — dedup, scope,
ownership routing, merge — and returns a *provisional* verdict plus the list of
blockers to verify. The orchestrator (`swift-reviewer`, which has Read/Grep) owns
the verify gate: it opens each `blockersToVerify` entry against the code, confirms
or downgrades it, and computes the final verdict. See agents/swift-reviewer.md
Step 5.

Protocol: read one JSON object per line on stdin; write one per line on stdout.
All logging goes to stderr — stdout is the protocol channel, never print to it.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find schema/synthesize

from schema import FINDING_JSON_SCHEMA, parse_finding  # noqa: E402
from synthesize import render_report, synthesize          # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "review-synthesizer", "version": "0.1.0"}

TOOL = {
    "name": "synthesize_review",
    "title": "Deterministic review synthesizer",
    "description": (
        "Merge every reviewer's findings into one consolidated report + a "
        "PROVISIONAL verdict, deterministically. Dedup is category-aware with "
        "line-range overlap; ownership rules re-route (never drop); scope honours "
        "`structural-pipeline`; schema-invalid rows are quarantined, never dropped. "
        "This server has no repo access, so it does NOT run the verify gate — it "
        "returns `blockersToVerify` for the caller to confirm against the code, "
        "then finalise the verdict. Call this instead of doing Step-5 dedup in prose."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "findings": {
                "type": "array",
                "description": "Every reviewer's findings + your parity/test/verification rows.",
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


def _blockers_to_verify(review) -> list[dict]:
    """The actual blocker findings, flat, for the caller's verify gate. Emits the
    real blocker finding(s) of each gating cluster — NOT the ownership-routed
    `primary`, which on a mixed-severity cluster can be the lower-severity finding
    (the agent must verify the blocker's own `file:line`, not a warning's). The
    server can't open files, so it hands these back with confidence + cluster size."""
    out = []
    for c in review.clusters:
        if c.severity != "blocker":
            continue
        for f in c.findings:
            if f.severity != "blocker":
                continue
            out.append({
                "file": f.file, "line": f.line, "lineEnd": f.lineEnd,
                "category": f.category, "sourceAgent": f.sourceAgent,
                "confidence": f.confidence, "finding": f.finding,
                "clusterSeverity": c.severity, "clusterSize": len(c.findings),
            })
    return out


def _call_synthesize(arguments: dict) -> dict:
    findings, quarantined = [], []
    for d in arguments.get("findings", []):
        try:
            findings.append(parse_finding(d))
        except Exception as exc:  # noqa: BLE001 - quarantine, never drop
            quarantined.append((d, str(exc)))
    changed = set(arguments.get("changed_files", []))
    # PROVISIONAL: assume every blocker is real (verify=lambda f: True). The caller
    # confirms blockersToVerify against the repo, then computes the final verdict.
    review = synthesize(findings, changed, quarantined=quarantined, verify=lambda f: True)
    structured = {
        "provisionalVerdict": review.verdict.decision,
        "blockersToVerify": _blockers_to_verify(review),
        "clusters": len(review.clusters),
        "preExisting": len(review.pre_existing),
        "quarantined": len(review.quarantined),
    }
    return {
        # findings table only — no verdict / Needs-Confirmation (the caller owns those)
        "content": [{"type": "text", "text": render_report(review)}],
        "structuredContent": structured,
        "isError": False,
    }


class _RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


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


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


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
        if not isinstance(msg, dict):  # e.g. a bare `[]` — don't crash on msg.get()
            _log("ignored non-object JSON-RPC message")
            continue
        mid = msg.get("id")
        try:
            result = _handle(msg.get("method", ""), msg.get("params") or {})
        except _RpcError as e:
            if mid is not None:
                _send({"jsonrpc": "2.0", "id": mid, "error": {"code": e.code, "message": e.message}})
            continue
        except Exception as e:  # noqa: BLE001 - tool/internal failure
            if mid is not None:
                _send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}})
            continue
        if mid is not None and result is not None:  # requests reply; notifications don't
            _send({"jsonrpc": "2.0", "id": mid, "result": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
