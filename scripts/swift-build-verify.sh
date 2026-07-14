#!/bin/bash
# PostToolUse hook for Bash: detect test/build commands and verify results.
# Runs after Bash tool invocations to catch failed builds and test runs.
#
# UnleashedMail is an Xcode project — `xcodebuild` is the canonical tool.
# `swift build`/`swift test` are flagged as advisories (likely user error invoking
# the wrong tool against this xcodeproj).
#
# PostToolUse plain stdout is NOT shown to the model, so the build/test advisory is
# delivered via hookSpecificOutput.additionalContext (COREDEV-2486, audit hooks-scripts.3);
# JSON output is only processed on exit 0.
#
# COREDEV-2324: input read migrated to the shared hook-io helper (stdin-JSON first,
# CLAUDE_TOOL_ARG_* fallback) so this hook is not silently inert if the installed
# Claude Code build delivers stdin JSON only.
#
# COREDEV-2325 (Item 10): on the PostToolUse (non-failure) path, also append a bounded
# build-CLASS line with failed=false — the "attempted/non-failure" side that pairs with
# scripts/build-failure-log.sh (PostToolUseFailure, failed=true). Class only, never the
# raw command. Gated by UNLEASHED_FAILURE_LOG.

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
[ -f "$_DIR/lib/hook-io.sh" ] && . "$_DIR/lib/hook-io.sh"
# shellcheck source=scripts/lib/log.sh
[ -f "$_DIR/lib/log.sh" ] && . "$_DIR/lib/log.sh"

# Defensive fallback if the shared lib is unavailable (it ships alongside this hook).
command -v hook_emit_posttool_context >/dev/null 2>&1 || hook_emit_posttool_context() { printf '%s\n' "$1" >&2; }

if command -v hook_io_read >/dev/null 2>&1; then
    hook_io_read
    COMMAND="$(hook_command)"
else
    COMMAND="${CLAUDE_TOOL_ARG_command:-}"
fi

# Classify via the SHARED build_class (lockstep with build-failure-log.sh), so a command can never
# change class on success vs. failure. Both the advisory and the success log line derive from it.
CLASS=""
command -v build_class >/dev/null 2>&1 && CLASS="$(build_class "$COMMAND")"

ADVISORY=""
case "$CLASS" in
    xcodebuild-build)
        ADVISORY="🔨 xcodebuild build detected — verify BUILD SUCCEEDED in the output above."
        ;;
    xcodebuild-test)
        ADVISORY="🧪 xcodebuild test detected — verify all tests passed in the output above. If tests failed, fix the failures before proceeding."
        ;;
    swift-build)
        ADVISORY="⚠️  'swift build' detected — but this project is an Xcode project, not a SwiftPM package. Use: xcodebuild build -scheme \"Unleashed Mail\" -destination 'platform=macOS'"
        ;;
    swift-test)
        ADVISORY="⚠️  'swift test' detected — but this project is an Xcode project, not a SwiftPM package. Use: xcodebuild test -scheme \"Unleashed Mail\" -destination 'platform=macOS'"
        ;;
    xcodebuild-other) ;;   # analyze/archive/clean — logged for pairing, no build/test advisory
    *) exit 0 ;;           # not a build/test command
esac

# Append the "attempted" build-class line (failed=false) — class only, never the command. Pairs with
# build-failure-log.sh (failed=true). Gated by UNLEASHED_FAILURE_LOG.
if [ "${UNLEASHED_FAILURE_LOG:-on}" != "off" ] && command -v log_append >/dev/null 2>&1; then
    log_append "build-log.jsonl" "$(printf '{"ts":"%s","kind":"build","class":"%s","failed":false}' "$(log_ts)" "$CLASS")"
fi

# Deliver the advisory to the model via additionalContext (invisible on plain stdout for PostToolUse).
if [ -n "$ADVISORY" ]; then
    hook_emit_posttool_context "$ADVISORY"
fi
exit 0
