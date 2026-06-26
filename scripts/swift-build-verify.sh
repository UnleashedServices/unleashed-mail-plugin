#!/bin/bash
# PostToolUse hook for Bash: detect test/build commands and verify results.
# Runs after Bash tool invocations to catch failed builds and test runs.
#
# UnleashedMail is an Xcode project — `xcodebuild` is the canonical tool.
# `swift build`/`swift test` are flagged as warnings (likely user error invoking
# the wrong tool against this xcodeproj).
#
# COREDEV-2324: input read migrated to the shared hook-io helper (stdin-JSON first,
# CLAUDE_TOOL_ARG_* fallback) so this hook is not silently inert if the installed
# Claude Code build delivers stdin JSON only. (Item-10 build-class logging stays
# deferred to Phase 2 — this change is the input-read migration only.)

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
[ -f "$_DIR/lib/hook-io.sh" ] && . "$_DIR/lib/hook-io.sh"

if command -v hook_io_read >/dev/null 2>&1; then
    hook_io_read
    COMMAND="$(hook_command)"
else
    COMMAND="${CLAUDE_TOOL_ARG_command:-}"
fi

case "$COMMAND" in
    *"xcodebuild"*"build"*)
        echo "🔨 xcodebuild build detected — verify BUILD SUCCEEDED in the output above."
        ;;
    *"xcodebuild"*"test"*)
        echo "🧪 xcodebuild test detected — verify all tests passed in the output above."
        echo "   If tests failed, fix the failures before proceeding."
        ;;
    *"swift build"*)
        echo "⚠️  'swift build' detected — but this project is an Xcode project, not a SwiftPM package."
        echo "   Use: xcodebuild build -scheme \"Unleashed Mail\" -destination 'platform=macOS'"
        ;;
    *"swift test"*)
        echo "⚠️  'swift test' detected — but this project is an Xcode project, not a SwiftPM package."
        echo "   Use: xcodebuild test -scheme \"Unleashed Mail\" -destination 'platform=macOS'"
        ;;
    *)
        # Not a build/test command — no action
        exit 0
        ;;
esac

exit 0
