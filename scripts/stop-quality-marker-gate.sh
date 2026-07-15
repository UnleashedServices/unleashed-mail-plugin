#!/usr/bin/env bash
# Stop-gate on a cached build/lint marker (Item 4, COREDEV-2324).
#
# Reads ONLY cached markers — runs NO xcodebuild and NO swiftlint — so it costs
# milliseconds, never the 13+ s a real build would. It blocks the turn (root-level
# {"decision":"block"}) only when a marker is fail + fresh + commit-matches.
#
# Warn-first: the default mode logs a silent diagnostic line and exits 0 with no
# stdout (on Stop, stdout/additionalContext are NOT passive, so warn must not use
# them). Two loop guards prevent wedging a session.
#
# Kill switch:  UNLEASHED_STOP_GATE=off                  -> exit 0
# Mode:         UNLEASHED_STOP_GATE_MODE=warn|enforce|off  -> default enforce (COREDEV-2489/P1c-12):
#               a lint-fail marker blocks the turn ONCE via {"decision":"block","reason":...} (the
#               only model-visible Stop mechanism), fail-open + TTL/commit-guarded so it can't wedge.
# TTL seconds:  UNLEASHED_STOP_GATE_TTL_SEC               -> default 600
set -uo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
. "$_DIR/lib/hook-io.sh"
# shellcheck source=scripts/lib/marker.sh
. "$_DIR/lib/marker.sh"

[ "${UNLEASHED_STOP_GATE:-on}" = "off" ] && exit 0
MODE="${UNLEASHED_STOP_GATE_MODE:-enforce}"
[ "$MODE" = "off" ] && exit 0   # `_MODE=off` also disables (parity with the README kill-switch cell)
TTL="${UNLEASHED_STOP_GATE_TTL_SEC:-600}"
# Reject a non-numeric TTL so the later `[ "$AGE" -lt "$TTL" ]` never errors to stderr.
case "$TTL" in
    ''|*[!0-9]*) TTL=600 ;;
esac

hook_io_read

# Loop guard #1: never re-block while CC is already re-invoking us in a stop loop.
[ "$(hook_bool stop_hook_active)" = "true" ] && exit 0

NOW="$(date +%s 2>/dev/null)" || NOW=0
# If we cannot read the clock we cannot assess freshness — fail open (no block).
case "$NOW" in
    ''|*[!0-9]*) exit 0 ;;
    0) exit 0 ;;
esac

HEAD_COMMIT="$(git rev-parse --short HEAD 2>/dev/null)" || HEAD_COMMIT=""
# No commit context (not a git repo) — cannot match marker.commit, so never block.
[ -n "$HEAD_COMMIT" ] || exit 0

REPO_HASH="$(marker_repo_hash)"
SENTINEL="$(marker_dir)/stop-last-blocked-${REPO_HASH}"

BLOCKED_KIND=""
BLOCKED_AGE=""
for KIND in lint build; do
    [ "$(marker_status "$KIND")" = "fail" ] || continue
    MTIME="$(marker_mtime "$KIND")"
    case "$MTIME" in
        ''|*[!0-9]*|0) AGE=999999 ;;
        *) AGE=$(( NOW - MTIME )) ;;
    esac
    [ "$AGE" -ge 0 ] 2>/dev/null || AGE=999999
    [ "$AGE" -lt "$TTL" ] || continue
    [ "$(marker_commit "$KIND")" = "$HEAD_COMMIT" ] || continue
    BLOCKED_KIND="$KIND"
    BLOCKED_AGE="$AGE"
    break
done

[ -n "$BLOCKED_KIND" ] || exit 0

# Loop guard #2: a stateful sentinel so a genuinely-broken build can still be
# abandoned after it has blocked once on this commit.
if [ -f "$SENTINEL" ] && [ "$(cat "$SENTINEL" 2>/dev/null)" = "$HEAD_COMMIT" ]; then
    exit 0
fi

if [ "$BLOCKED_KIND" = "build" ]; then
    REMEDY="xcodebuild build -scheme \"Unleashed Mail\" -destination 'platform=macOS'"
else
    REMEDY="swiftlint --quiet (or fix the reported violations)"
fi
REASON="Last ${BLOCKED_KIND} check FAILED (${BLOCKED_AGE}s ago, commit ${HEAD_COMMIT}). Fix it before stopping. Run: ${REMEDY}"

if [ "$MODE" = "enforce" ]; then
    # Only block once loop-guard #2 is durably recorded. If the sentinel can't be
    # written (data dir unwritable/full), DON'T block — otherwise a later Stop on
    # this same commit could keep re-blocking. Fail open to the warn-log path.
    if printf '%s' "$HEAD_COMMIT" > "$SENTINEL" 2>/dev/null; then
        hook_emit_block "$REASON"
        exit 0
    fi
fi

# warn mode (default): silent diagnostic log only — no stdout, no decision.
LOGDIR="$(marker_base)/logs"
mkdir -p "$LOGDIR" 2>/dev/null || exit 0
printf '%s stop-gate would-block kind=%s age=%s commit=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" "$BLOCKED_KIND" "$BLOCKED_AGE" "$HEAD_COMMIT" \
    >> "$LOGDIR/stop-gate.log" 2>/dev/null || true
exit 0
