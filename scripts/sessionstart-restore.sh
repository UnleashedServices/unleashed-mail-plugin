#!/usr/bin/env bash
# SessionStart work-context restore (Item 5, COREDEV-2325).
#
# The documented post-compaction context-delivery point: PostCompact CANNOT inject context
# (decision-control "None"), so restore lives on SessionStart with source=="compact" (and,
# as a freshness-windowed bonus, resume/startup). If the PreCompact snapshot is fresh
# (<10 min) inject a one-line resume hint via additionalContext, then DELETE the snapshot so
# it restores exactly once. Strictly NON-BLOCKING — never decision:block. All snapshot
# fields are already PII-safe; the hint is redacted+capped again defensively.
#
# Kill switch:  UNLEASHED_COMPACT_RESTORE=off  -> exit 0
set -uo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
. "$_DIR/lib/hook-io.sh"
# shellcheck source=scripts/lib/context.sh
. "$_DIR/lib/context.sh"

# COREDEV-2617 §4.2a SS-1 — the SessionStart notice, BEFORE the snapshot-only early exits below.
# The resolver now records `conflict`, `stale` and `failed`, and publishers observing `conflict` or
# `stale` are deliberately SILENT — so this hook is the one place the documented "visible conflict"
# actually reaches a person (codex, PR #67: nothing else in production read the state). The
# predicate is exactly SS-1's six-value partition: notice on {conflict, stale, failed}, silence on
# {created, current, none} — `none` is also unresolved, and is deliberately quiet, because a
# machine that has never published is the ordinary first-run case and not a fault. ONE line,
# non-blocking, exit 0 regardless; the notice does not depend on a snapshot existing.
# The notice is CAPTURED, not emitted-and-exited: a hook run emits ONE additionalContext object, and
# an environment-backed publisher observing `conflict` still has a usable base — so a fresh
# snapshot must still be restored (and deleted) beneath a persistent conflict, or every session
# would repeat the warning while post-compaction context was never delivered (codex, PR #67). The
# notice is prepended to whatever this hook would otherwise say, and emitted alone only when the
# snapshot paths below have nothing to add.
STORE_NOTICE=""
case "${_UNLEASHED_POINTER_STATE:-none}" in
    conflict|stale|failed)
        STORE_NOTICE="unleashed-mail plugin state: the base store is ${_UNLEASHED_POINTER_STATE} — shells that do not receive the plugin-data environment (git hooks, plain terminals) cannot resolve plugin state until it is repaired. Inspect ~/.claude/unleashed-mail/bases/ (a conflict is two entries naming different bases; remove the stale one). " ;;
esac
# Every silent exit below becomes "emit the notice, then exit" when a notice is pending.
_ss_exit() { [ -n "$STORE_NOTICE" ] && hook_emit_session_context "${STORE_NOTICE% }"; exit 0; }

# THE NOTICE COMES BEFORE THE KILL SWITCH AND BEFORE THE SOURCE FILTER. Both used to `exit 0` above
# it, so a valid SessionStart with `source=clear` — and any run with restore switched off — never
# reached the notice, and `conflict`/`stale`/`failed` stayed invisible on exactly those sessions
# although SS-1's six-value partition has no source restriction (codex, PR #67 pass 9). The kill
# switch disables snapshot RESTORATION, not the store notice.
[ "${UNLEASHED_COMPACT_RESTORE:-on}" = "off" ] && _ss_exit

hook_io_read

SOURCE="$(hook_str source)"
case "$SOURCE" in
    compact|resume|startup) ;;
    *) _ss_exit ;;
esac


# COREDEV-2617 / D': nothing was persisted, so there is nothing to restore. Exit 0 silently —
# carrying the store notice if one is pending.
unleashed_base_ok || _ss_exit
SNAP="$(context_snapshot_path)"   # per-checkout snapshot (repo-hash namespaced)
[ -f "$SNAP" ] || _ss_exit

# Freshness via the snapshot FILE's mtime (BSD/GNU split). Stale (>=600s) -> silent exit,
# leaving the file for the next PreCompact to overwrite. Fail-open on any clock/stat error.
NOW="$(date +%s 2>/dev/null)" || NOW=0
case "$NOW" in ''|*[!0-9]*|0) _ss_exit ;; esac
# Feature-detect the mtime flavor rather than branching on `uname == Darwin`: BSD stat (macOS,
# FreeBSD, NetBSD — not all report "Darwin") uses `-f %m`, GNU stat uses `-c %Y`. Probe `-f %m`
# first (it errors out on GNU because `%m` is treated as a missing file operand) and fall back to
# `-c %Y`. ($SNAP already exists — checked above — so the probe reflects the stat flavor, not absence.)
if stat -f %m "$SNAP" >/dev/null 2>&1; then
    MTIME="$(stat -f %m "$SNAP" 2>/dev/null)"
else
    MTIME="$(stat -c %Y "$SNAP" 2>/dev/null)"
fi
case "$MTIME" in ''|*[!0-9]*) _ss_exit ;; esac
AGE=$(( NOW - MTIME ))
[ "$AGE" -ge 0 ] 2>/dev/null || _ss_exit
[ "$AGE" -lt 600 ] || _ss_exit

# Read one snapshot field (jq -> python3), defaulting to "unknown".
_snap_field() {
    local f="$1"
    if command -v jq >/dev/null 2>&1; then
        jq -r --arg f "$f" '.[$f] // "unknown"' "$SNAP" 2>/dev/null
    elif command -v python3 >/dev/null 2>&1; then
        _SNAP_F="$f" python3 -c 'import json, os, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:  # explicit UTF-8 in: locale-independent
        d = json.load(fh)
    v = d.get(os.environ.get("_SNAP_F", ""), "unknown")
    out = "unknown" if v is None else str(v)
    sys.stdout.buffer.write(out.encode("utf-8"))       # bytes out: avoid ASCII-locale encode error
except Exception:
    sys.stdout.buffer.write(b"unknown")' "$SNAP" 2>/dev/null
    else
        printf 'unknown'
    fi
}

TICKET="$(_snap_field ticket)";       [ -n "$TICKET" ] || TICKET="unknown"
SLUG="$(_snap_field branch_slug)";    [ -n "$SLUG" ]   || SLUG="unknown"
PLAN="$(_snap_field plan)";           [ -n "$PLAN" ]   || PLAN="unknown"
ROUND="$(_snap_field round)";         [ -n "$ROUND" ]  || ROUND="unknown"

HINT="Context restored after compaction — resume prior work: ticket=${TICKET}, branch=${SLUG}, plan=${PLAN}, round=${ROUND}. Re-read the plan/ticket before continuing."
HINT="$(hook_redact_pii "$HINT")"
HINT="${HINT:0:400}"   # bash substring (char-aware, no cut subprocess / BSD `cut -c` quirk)

hook_emit_session_context "${STORE_NOTICE}${HINT}"

# Restore exactly once.
rm -f "$SNAP" 2>/dev/null || true
exit 0
