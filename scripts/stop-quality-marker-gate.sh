#!/usr/bin/env bash
# Stop-gate on a cached build/lint marker (Item 4, COREDEV-2324).
#
# Reads ONLY cached markers — runs NO xcodebuild and NO swiftlint — so it costs
# milliseconds, never the 13+ s a real build would. It blocks the turn (root-level
# {"decision":"block"}) only when a marker is fail + fresh + commit-matches.
#
# Enforce-first (default): a lint-fail marker blocks the turn ONCE (`decision:block`+`reason`).
# `warn` is the opt-in fallback — it logs a silent diagnostic line and exits 0 with no stdout
# (on Stop, stdout/additionalContext are NOT passive, so warn must not use them). Two loop guards
# prevent wedging a session.
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
# F5 (COREDEV-2503): key loop-guard-#2 by SESSION, not just repo+commit. Without it, a broken commit that
# blocked once passes freely in EVERY later session — and with `enforce` the default that makes the sentinel
# load-bearing (and a plantable, cross-session bypass). Prefer the Stop payload's session_id; fall back to a
# STABLE hash of transcript_path (session-stable). NEVER a per-invocation nonce — that would re-block every
# retry and wedge the session. (Loop-guard #1, stop_hook_active, still prevents the in-loop wedge.)
SESSION_KEY="$(hook_str session_id)"
[ -n "$SESSION_KEY" ] || SESSION_KEY="$(hook_str transcript_path)"
# F5 (codex+gemini review of #53): an EMPTY session key (both fields absent) must NOT share a sentinel — a
# hash("") would collide EVERY anonymous session into one file, so the first anonymous block would unblock
# all later ones (cross-session bypass). With no identity, use NO sentinel; the enforce path below then
# falls through to the warn-log (fail OPEN) rather than blocking — no shared file to bypass through, and no
# wedge (the loop-guard cannot be durably recorded, so blocking would re-fire on every later Stop).
if [ -n "$SESSION_KEY" ]; then
    SESSION_HASH="$(marker_hash_str "$SESSION_KEY")"
    SENTINEL="$(marker_dir)/stop-last-blocked-${REPO_HASH}-${SESSION_HASH}"
else
    SENTINEL=""
fi

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
if [ -n "$SENTINEL" ] && [ -f "$SENTINEL" ] && [ ! -L "$SENTINEL" ] \
    && [ "$(cat "$SENTINEL" 2>/dev/null)" = "$HEAD_COMMIT" ]; then
    exit 0                                          # trust only a genuine regular file, never a symlink (A2)
fi

if [ "$BLOCKED_KIND" = "build" ]; then
    REMEDY="xcodebuild build -scheme \"Unleashed Mail\" -destination 'platform=macOS'"
else
    REMEDY="swiftlint --quiet (or fix the reported violations)"
fi
REASON="Last ${BLOCKED_KIND} check FAILED (${BLOCKED_AGE}s ago, commit ${HEAD_COMMIT}). Fix it before stopping. Run: ${REMEDY}"

# Block only when loop-guard #2 can be DURABLY, per-session recorded. Skip the block (fall through to the
# warn-log path — fail OPEN) when there is no session identity to key the sentinel (anonymous payload) OR
# the sentinel can't be written (dir unwritable/full) — otherwise a later Stop on this commit keeps
# re-blocking (a wedge). This satisfies BOTH review bots: codex #53 flagged the shared empty-key sentinel
# (a cross-session bypass) — with no identity NOTHING is written or read, so there is no shared file to
# bypass through; gemini #53 flagged that BLOCKING anonymously wedges — failing open avoids the wedge and
# matches the gate's own "can't record the loop-guard -> don't block" design.
if [ "$MODE" = "enforce" ] && [ -n "$SENTINEL" ]; then
    # A2 (audit of #53): never write THROUGH a pre-planted symlink/non-regular sentinel — a plain `> $SENTINEL`
    # follows the link and clobbers an attacker-chosen file with the gate's privileges (then chmod 600 it).
    # Drop any hostile pre-existing target, write to an UNPREDICTABLE temp (mktemp = O_EXCL, no-follow), then
    # atomically rename INTO place (rename replaces the path itself, never following a link). Any failure
    # falls through to the warn-log (preserving the fail-open-when-unwritable behavior).
    if [ -L "$SENTINEL" ] || { [ -e "$SENTINEL" ] && [ ! -f "$SENTINEL" ]; }; then
        rm -f "$SENTINEL" 2>/dev/null || true
    fi
    _STMP="$(mktemp "$(marker_dir)/.stopgate.XXXXXX" 2>/dev/null || true)"
    if [ -n "$_STMP" ] && printf '%s' "$HEAD_COMMIT" > "$_STMP" 2>/dev/null; then
        chmod 600 "$_STMP" 2>/dev/null || true      # not world-writable/plantable
        if mv -f "$_STMP" "$SENTINEL" 2>/dev/null; then
            hook_emit_block "$REASON"
            exit 0
        fi
        rm -f "$_STMP" 2>/dev/null || true          # rename failed -> don't leak the temp
    fi
fi

# warn mode (opt-in fallback): silent diagnostic log only — no stdout, no decision.
LOGDIR="$(marker_base)/logs"
mkdir -p "$LOGDIR" 2>/dev/null || exit 0
printf '%s stop-gate would-block kind=%s age=%s commit=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" "$BLOCKED_KIND" "$BLOCKED_AGE" "$HEAD_COMMIT" \
    >> "$LOGDIR/stop-gate.log" 2>/dev/null || true
exit 0
