#!/usr/bin/env bash
# SubagentStop reviewer-verdict capture (Item 6, COREDEV-2325).
#
# When one of the four SPECIALIST reviewers finishes, persist its findings array to a
# per-round, per-agent file directly consumable by mcp/review-synthesizer/synthesize.py —
# closing the synthesizer's producer gap. EXCLUDES `swift-reviewer` (it is the synthesizer's
# CONSUMER/orchestrator; capturing it would feed the synthesizer its own output).
#
# The reviewer's final message comes from `last_assistant_message`, else the SUBAGENT
# transcript `agent_transcript_path` (NOT `transcript_path`, which is the parent session).
# All validation, PII-redaction, and the path-traversal guard live in capture.py.
# Observe-only: a missed capture never blocks (the orchestrator still collects findings).
#
# Kill switch:  UNLEASHED_CAPTURE_REVIEWERS=off  -> exit 0
set -uo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
. "$_DIR/lib/hook-io.sh"
# shellcheck source=scripts/lib/context.sh
. "$_DIR/lib/context.sh"

CAPTURE_PY="$_DIR/../mcp/review-synthesizer/capture.py"

[ "${UNLEASHED_CAPTURE_REVIEWERS:-on}" = "off" ] && exit 0
command -v python3 >/dev/null 2>&1 || exit 0
[ -f "$CAPTURE_PY" ] || exit 0

hook_io_read

AGENT="$(hook_str agent_type)"
case "$AGENT" in
    security-reviewer|concurrency-reviewer|ux-perf-reviewer|accessibility-auditor) ;;
    *) exit 0 ;;   # EXCLUDE swift-reviewer + everything else
esac

SLUG="$(context_branch_slug "$(context_branch)")"
ROOT="$(context_reviews_dir)"

MSG="$(hook_str last_assistant_message)"
if [ -n "$MSG" ]; then
    printf '%s' "$MSG" | python3 "$CAPTURE_PY" --root "$ROOT" --slug "$SLUG" --agent "$AGENT" >/dev/null 2>&1 || true
else
    TP="$(hook_str agent_transcript_path)"
    if [ -n "$TP" ] && [ -f "$TP" ]; then
        python3 "$CAPTURE_PY" --root "$ROOT" --slug "$SLUG" --agent "$AGENT" --transcript "$TP" >/dev/null 2>&1 || true
    fi
fi
exit 0
