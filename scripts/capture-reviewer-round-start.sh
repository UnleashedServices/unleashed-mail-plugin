#!/usr/bin/env bash
# SubagentStart reviewer round-binding producer (COREDEV-2326).
#
# When one of the four SPECIALIST reviewers is SPAWNED, freeze the current review-cycle round for that
# subagent — keyed by its unique `agent_id` — under the plugin data dir. The SubagentStop capture
# (`scripts/capture-reviewer-verdict.sh`) later looks the round up by the SAME `agent_id` and exports
# UNLEASHED_REVIEW_ROUND, so each reviewer's findings bind to the round it was spawned in, even when a
# late reviewer from an earlier cycle stops AFTER a later cycle advanced (the interleaving the round
# INFERENCE in mcp/review-synthesizer/capture.py cannot perfectly group). EXCLUDES `swift-reviewer`
# (the orchestrator/consumer) and every non-reviewer subagent, exactly like the capture hook.
#
# Observe-only: a missed binding is non-fatal — capture.py falls back to round inference (the shipped
# default). All round-binding logic, the atomic write, and the bounded GC live in scripts/lib/context.sh.
#
# Kill switches:  UNLEASHED_REVIEW_ROUND_SIGNAL=off  OR  UNLEASHED_CAPTURE_REVIEWERS=off  -> exit 0
set -uo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
. "$_DIR/lib/hook-io.sh"
# shellcheck source=scripts/lib/context.sh
. "$_DIR/lib/context.sh"

[ "${UNLEASHED_REVIEW_ROUND_SIGNAL:-on}" = "off" ] && exit 0
[ "${UNLEASHED_CAPTURE_REVIEWERS:-on}" = "off" ] && exit 0   # whole capture path off -> no producer
command -v python3 >/dev/null 2>&1 || exit 0

hook_io_read

AGENT="$(hook_str agent_type)"
# COREDEV-2486 (audit hooks-scripts.4): plugin-shipped subagents surface with a
# plugin-scoped agent_type (e.g. "unleashed-mail:security-reviewer"), not the bare
# frontmatter name. Strip ONLY THIS plugin's prefix (not any "<plugin>:") so the bare-name
# case below matches under normal install, while a DIFFERENT plugin's reviewer
# (e.g. "other-plugin:security-reviewer") stays prefixed, fails the case, and cannot pollute
# this review round. capture.py's VALID_AGENTS allowlist is bare-name too.
AGENT="${AGENT#unleashed-mail:}"
case "$AGENT" in
    security-reviewer|concurrency-reviewer|ux-perf-reviewer|accessibility-auditor|prompt-review) ;;
    *) exit 0 ;;   # EXCLUDE swift-reviewer + everything else
esac

AGENT_ID="$(hook_str agent_id)"
[ -n "$AGENT_ID" ] || exit 0   # no id to bind -> inference covers this capture

# NO HOOK-LEVEL D' GUARD HERE, DELIBERATELY (COREDEV-2617 / COREDEV-2691). Its sibling
# `capture-reviewer-verdict.sh:48` DOES carry the hook-level base-ok skip, and that asymmetry was
# flagged as undocumented. It is correct, and the sibling's own comment says why: that hook "passes
# the composed root into Python and otherwise continues through lookup, capture and clear, so it
# needs an explicit skip rather than relying on a primitive no-op". THIS hook composes no root,
# calls no Python, and continues through nothing — the next statement is `exit 0`. It delegates to
# exactly ONE primitive, `context_review_round_bind`, which carries the guard at context.sh:419.
# Adding a second guard here would be cargo-cult symmetry, not defence.
# MEASURED under an unresolved base with a `mkdir`-counting PATH shim: shipped -> 0 calls; with
# context.sh:419's guard deleted -> 1 call, `mkdir -p /dev/null/unresolved-plugin-base/.state`.
# So the lib guard is load-bearing FOR THIS HOOK and is what makes the omission safe. Pinned by
# `test_plugin_state_base.py`'s hook-level cell — if that cell goes, so does this justification.
context_review_round_bind "$AGENT" "$AGENT_ID" "$(hook_str session_id)" >/dev/null 2>&1 || true
exit 0
