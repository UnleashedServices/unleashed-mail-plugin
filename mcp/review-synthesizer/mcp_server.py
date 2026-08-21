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
import select
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find schema/synthesize

from schema import canonical_path, is_abs_or_traversal, parse_finding  # noqa: E402
from synthesize import render_report, synthesize          # noqa: E402

# Absolute / `..`-traversal detection lives in `schema.is_abs_or_traversal` — ONE shared helper used here
# on `changed_files` AND in `parse_finding` on each finding's `file`, so the two sides can't disagree
# (COREDEV-2503 F2/F3). It folds `\`->`/` (matching canonical_path), closing the fail-open where a
# backslash entry slipped this guard's old raw-path check yet canonicalized to an absolute path.

# Advertise the current finalized MCP revision, but still negotiate the prior one so older
# clients keep working (COREDEV-2488 / audit mcp-server). Nothing this server uses (stdio
# framing, tools/list, tools/call shapes) changed between these revisions.
PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = frozenset({"2025-11-25", "2025-06-18"})
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
                "description": (
                    "Every reviewer's findings + your parity/test/verification rows. Each item is a "
                    "finding object: severity, confidence, sourceAgent, category, file, line, lineEnd, "
                    "scope?, finding, evidence, fix. Items are deliberately UNVALIDATED here (accept "
                    "ANY JSON) so a malformed row — even a non-object like null/string/array — reaches "
                    "the server and is quarantined individually; a stricter item schema would let a "
                    "schema-aware client reject the whole call client-side and defeat that."
                ),
                "items": {},   # empty schema = accept any JSON value (object-or-not)
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


_STDERR_DEAD = False


def _log(msg: str) -> None:
    """Best-effort. A broken LOG channel must never affect the PROTOCOL on stdout (codex, PR #69).

    Two failures came from letting it: with only stderr closed, a malformed request got no
    `-32700` response at all — the diagnostic raised, the outer `except BrokenPipeError` mistook a
    dead log channel for dead protocol stdout, redirected healthy stdout and exited 0; and closing
    both read ends BEFORE the startup "ready" line still exited 120, because that log sits ahead of
    the loop's guard. Swallowing here fixes both, and is correct on the merits: stderr is
    diagnostics, stdout is the protocol, and the two must fail independently.

    On the first failure stderr is pointed at devnull, because a raised write leaves the text
    BUFFERED and the interpreter's exit-time flush would raise again — which CPython reports as
    rc 120. The flag then keeps every later call cheap.
    """
    global _STDERR_DEAD
    if _STDERR_DEAD:
        return
    # NO FLAG IS EVER CHANGED ON fd 2. The obvious repair — dup the descriptor and set O_NONBLOCK
    # on the copy — DOES NOT WORK: `dup` shares the open file DESCRIPTION, and `F_SETFL` mutates
    # exactly that, so the launcher's stderr went non-blocking anyway (measured; the first attempt
    # at this fix failed its own test). Writability is TESTED instead, which changes nothing that
    # any other process can observe. A diagnostic is one short line, well under PIPE_BUF, so a pipe
    # reported writable accepts it without blocking (codex, PR #69 rounds 3-4).
    try:
        if not select.select([], [sys.stderr.fileno()], [], 0)[1]:
            return                      # reader is not keeping up; drop this line, keep serving
    except (OSError, ValueError):
        pass
    try:
        # RAW os.write, NOT print(). `print(..., flush=True)` on a non-blocking fd leaves the failed
        # write sitting in TextIOWrapper's buffer, and the interpreter's EOF flush retries it and
        # exits **120** — the full-pipe case answered the queued ping and then died anyway
        # (codex, PR #69 round 3). os.write has no buffer to leave anything in: EAGAIN surfaces here
        # and the line is simply dropped.
        os.write(sys.stderr.fileno(), f"[review-synthesizer] {msg}\n".encode("utf-8", "replace"))
    except BlockingIOError:
        # The reader is alive but not keeping up. Drop this line and keep serving; do NOT mark
        # stderr dead, because the condition is transient.
        return
    except OSError:
        _STDERR_DEAD = True
        try:
            _devnull = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(_devnull, sys.stderr.fileno())
            finally:
                os.close(_devnull)
        except OSError:
            pass


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
    if not isinstance(arguments, dict):
        # a non-dict (e.g. a number) would TypeError on `in`/`[]` -> -32603 crash
        raise _RpcError(-32602, "arguments must be an object")
    # Both are required by inputSchema; a MISSING one is a malformed call, not a
    # reason to silently APPROVE — a missing changed_files defaults to [] and would
    # mis-scope every finding to pre-existing, hiding real blockers behind an APPROVE.
    if "findings" not in arguments or "changed_files" not in arguments:
        raise _RpcError(-32602, "findings and changed_files are required")
    findings_in = arguments["findings"]
    if not isinstance(findings_in, list):
        # A lone finding object would iterate as dict KEYS and quarantine silently.
        raise _RpcError(-32602, "findings must be an array")
    changed_files = arguments["changed_files"]
    if not isinstance(changed_files, list) or not all(isinstance(p, str) for p in changed_files):
        # Fail CLOSED: a string/None would set()-coerce to characters/empty and
        # silently push every real finding to pre-existing -> a provisional APPROVE.
        raise _RpcError(-32602, "changed_files must be an array of strings")
    # Fail CLOSED on an EFFECTIVELY-empty changeset carrying findings. `changed_files: []` — or a
    # list whose entries all canonicalize to "" (`[""]`, `["   "]`, `["./"]`) — scopes EVERY finding
    # to pre-existing (nothing is in-scope), so the synthesizer would return a provisional APPROVE
    # while blockers exist. Canonicalize with the SAME function synthesize() scopes against so the
    # two sides agree: a plain `not changed_files` list-truthiness check let `[""]`/`["./"]` slip a
    # real blocker straight to APPROVE (adversarial verify, Item 17). An empty changeset legitimately
    # has nothing to review and therefore no findings; a genuinely clean review sends findings: [].
    if findings_in and not {p for p in (canonical_path(c) for c in changed_files) if p}:
        raise _RpcError(
            -32602,
            "changed_files is empty (or all-blank/'.'-only) but findings were provided; refusing "
            "to synthesize (every finding would mis-scope to pre-existing and yield a bogus APPROVE)",
        )
    # Fail CLOSED on ABSOLUTE or TRAVERSAL entries. `git diff --name-only` only ever emits repo-relative
    # paths with no leading `/` and no `..` component. An absolute path (`/etc/passwd`) or `../..` escape
    # matches no finding's repo-relative `file`, so it survives the empty-changeset guard above and scopes
    # every real blocker to pre-existing -> a bogus provisional APPROVE (#44 independent review §5). The
    # empty-changeset guard only fires when ALL entries collapse to "" — a bare `..`/`/` MIXED with a real
    # file (`["A.swift", ".."]`) slips it, and canonical_path collapses `..`/`/` to "" so a canonical-based
    # check would drop them too. `is_abs_or_traversal` catches them (it strips leading `./` but preserves
    # `..`/absolute markers before canonicalization). Reject the call rather than filter — a caller sending
    # impossible diff paths is untrustworthy input.
    _bad = sorted({c for c in changed_files if is_abs_or_traversal(c)})
    if _bad:
        raise _RpcError(
            -32602,
            "changed_files contains absolute or traversal paths "
            f"({', '.join(_bad)}); `git diff --name-only` never emits these, so they cannot be a real "
            "changeset — refusing to synthesize (they would mis-scope findings to a bogus APPROVE)",
        )
    findings, quarantined = [], []
    for d in findings_in:
        try:
            findings.append(parse_finding(d, reject_abs_traversal=True))  # F3: gating path quarantines abs/traversal
        except Exception as exc:  # noqa: BLE001 - quarantine, never drop
            quarantined.append((d, str(exc)))
    changed = set(changed_files)
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
    # Mirror the verify data into a SECOND text block as well as structuredContent —
    # not every MCP client surfaces structuredContent, and the Step-5 caller needs the
    # provisional verdict + blockersToVerify either way. content[0] stays the table.
    verify_text = ("Provisional verify data (the caller runs the verify gate and "
                   "finalises the verdict):\n```json\n"
                   + json.dumps({"provisionalVerdict": structured["provisionalVerdict"],
                                 "blockersToVerify": structured["blockersToVerify"]}, indent=2)
                   + "\n```")
    return {
        # content[0] = findings table only (no verdict — the caller owns that);
        # content[1] = the verify data mirrored from structuredContent for text-only clients.
        "content": [
            {"type": "text", "text": render_report(review)},
            {"type": "text", "text": verify_text},
        ],
        "structuredContent": structured,
        "isError": False,
    }


class _RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _handle(method: str, params: dict):
    """Return a result dict. Never None: in JSON-RPC 2.0 every message carrying an `id` is a
    Request and MUST receive a Response, so a handler that returned None for one would leave the
    client hanging. Notifications are discriminated by the ABSENCE of `id` in the main loop, not by
    a None return (gemini-code-assist, PR #69).
    """
    if not isinstance(params, dict):
        # JSON-RPC permits array params, but every method here is by-name; reject a
        # non-object `params` with Invalid Params instead of crashing on .get() (-32603).
        raise _RpcError(-32602, "params must be an object")
    if method == "initialize":
        # Echo the client's version only if we actually support it; otherwise reply
        # with the version we DO speak (per MCP spec) instead of pretending to match.
        requested = params.get("protocolVersion")
        negotiated = (requested if isinstance(requested, str)
                      and requested in SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION)
        return {
            "protocolVersion": negotiated,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }
    if method == "notifications/initialized":
        # A well-behaved client sends this as a NOTIFICATION (no id) and the main loop stays
        # silent. Returning {} instead of None means a buggy client that attaches an id still
        # gets the JSON-RPC-required response instead of hanging forever on the suppressed
        # reply (2026-08-17 audit, AF-21).
        return {}
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
    # The protocol + the report emoji (🔴🟡🔵) are UTF-8; pin all three streams so a
    # non-UTF-8 locale (minimal CI containers, some Windows/POSIX) can't raise a
    # UnicodeError. errors="replace" degrades a malformed byte on stdin to U+FFFD
    # (then json.loads drops the line) rather than crashing readline().
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # not a TextIOWrapper / already detached
            pass
    _log("ready (stdio)")
    # readline() loop, NOT `for line in sys.stdin` — the file iterator's read-ahead
    # buffering can deadlock a bidirectional pipe protocol (it blocks filling its
    # buffer before yielding a line). readline returns each line as soon as it lands.
    try:
        while True:
            line = sys.stdin.readline()
            if not line:        # EOF — client closed the pipe
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # JSON-RPC 2.0 prescribes a Parse Error reply with `id: null` — a client that
                # sent a malformed REQUEST would otherwise wait until its own timeout on a
                # silent drop (2026-08-17 audit, AF-20). Still logged for the debug trail.
                _log("non-JSON line — replying -32700")
                _send({"jsonrpc": "2.0", "id": None,
                       "error": {"code": -32700, "message": "parse error: invalid JSON"}})
                continue
            if not isinstance(msg, dict):  # e.g. a bare `[]` — don't crash on msg.get()
                _log("ignored non-object JSON-RPC message")
                continue
            # A notification is a request with NO `id` member; an explicit `id: null`
            # is still a request and must get a reply. Distinguish by membership, not None.
            has_id = "id" in msg
            mid = msg.get("id")
            try:
                # default only when `params` is ABSENT; a present `[]`/null reaches the
                # dict-guard in _handle and is rejected (don't let `or {}` mask them).
                result = _handle(msg.get("method", ""), msg.get("params", {}))
            except _RpcError as e:
                if has_id:
                    _send({"jsonrpc": "2.0", "id": mid, "error": {"code": e.code, "message": e.message}})
                continue
            except Exception as e:  # noqa: BLE001 - tool/internal failure
                if has_id:
                    _send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}})
                continue
            if has_id:  # a Request ALWAYS replies; notifications (no id) stay silent
                _send({"jsonrpc": "2.0", "id": mid, "result": result})
    except BrokenPipeError:
        # The client closed the read end while we were writing (teardown race). The reader is
        # gone, so nothing is lost — exit cleanly instead of dying with a traceback and rc 1
        # (2026-08-17 audit, AF-19). Point stdout at devnull so the interpreter's exit-time
        # flush of the broken stream cannot raise a second BrokenPipeError.
        try:
            _devnull = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(_devnull, sys.stdout.fileno())
            finally:
                os.close(_devnull)
        except OSError:
            pass
        # The diagnostic goes to STDERR, which on a real client teardown is broken too — both pipe
        # read ends close together. `print(..., flush=True)` then raises a SECOND BrokenPipeError,
        # and merely catching it is NOT enough: the failed write leaves the text buffered and the
        # interpreter's exit-time flush raises again, which CPython reports as **rc 120**, not 1.
        # Measured, all four builds: shipped 120; catching alone 120; redirecting stderr
        # unconditionally exits 0 but LOSES the diagnostic even when stderr is healthy. So: try to
        # say it, and only if that fails point stderr at devnull so nothing remains to flush.
        _log("client closed the pipe mid-write — exiting cleanly")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
