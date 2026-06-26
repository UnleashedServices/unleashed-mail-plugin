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

[ "${UNLEASHED_COMPACT_RESTORE:-on}" = "off" ] && exit 0

hook_io_read

SOURCE="$(hook_str source)"
case "$SOURCE" in
    compact|resume|startup) ;;
    *) exit 0 ;;
esac

SNAP="$(context_state_dir)/work-context-snapshot.json"
[ -f "$SNAP" ] || exit 0

# Freshness via the snapshot FILE's mtime (BSD/GNU split). Stale (>=600s) -> silent exit,
# leaving the file for the next PreCompact to overwrite. Fail-open on any clock/stat error.
NOW="$(date +%s 2>/dev/null)" || NOW=0
case "$NOW" in ''|*[!0-9]*|0) exit 0 ;; esac
if [ "$(uname 2>/dev/null)" = "Darwin" ]; then
    MTIME="$(stat -f %m "$SNAP" 2>/dev/null)"
else
    MTIME="$(stat -c %Y "$SNAP" 2>/dev/null)"
fi
case "$MTIME" in ''|*[!0-9]*) exit 0 ;; esac
AGE=$(( NOW - MTIME ))
[ "$AGE" -ge 0 ] 2>/dev/null || exit 0
[ "$AGE" -lt 600 ] || exit 0

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
HINT="$(hook_redact_pii "$HINT" | cut -c1-400)"

hook_emit_session_context "$HINT"

# Restore exactly once.
rm -f "$SNAP" 2>/dev/null || true
exit 0
