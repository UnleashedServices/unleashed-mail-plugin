#!/usr/bin/env bash
# PostToolUseFailure build/test-failure log (Item 10, COREDEV-2325).
#
# A FAILED xcodebuild never reaches PostToolUse (which fires only on tool SUCCESS), so the
# build/test pass-marker path can't see failures. PostToolUseFailure (matcher Bash) is the
# failure side: when a Bash build/test command fails, append ONE bounded JSONL line with a
# derived command CLASS + failed=true — NEVER the raw command (it can carry a signing
# identity, `-archivePath`, or source strings) and never the error text.
#
# Pairs with scripts/swift-build-verify.sh, which logs the same class with failed=false on
# the PostToolUse (success) path.
#
# Output/exit are ignored by CC (the tool already failed); pure side-effect.
#
# Kill switch:  UNLEASHED_FAILURE_LOG=off  -> exit 0
set -uo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
. "$_DIR/lib/hook-io.sh"
# shellcheck source=scripts/lib/log.sh
. "$_DIR/lib/log.sh"

[ "${UNLEASHED_FAILURE_LOG:-on}" = "off" ] && exit 0

hook_io_read

# Defensive: matcher already scopes to Bash, but ignore anything else. Read tool_name
# structurally top-level (hook_str, not hook_tool_name's grep fallback) so a nested
# tool_input value can never influence the gate.
TOOL="$(hook_str tool_name)"
case "$TOOL" in Bash|"") ;; *) exit 0 ;; esac

CMD="$(hook_command)"
# Derive the command CLASS via the SHARED classifier (lockstep with swift-build-verify.sh) — the raw
# command is never read into the log. Empty class = not a build/test command -> nothing to log.
CLASS="$(build_class "$CMD")"
[ -n "$CLASS" ] || exit 0

log_append "build-log.jsonl" "$(printf '{"ts":"%s","kind":"build","class":"%s","failed":true}' "$(log_ts)" "$CLASS")"
exit 0
