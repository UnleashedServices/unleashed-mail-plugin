# shellcheck shell=bash
# Single source of the plugin-data base path (COREDEV-2600 item 1).
#
# WHY THIS FILE EXISTS
# The same expansion was copied into marker.sh, log.sh and context.sh with no cross-reference. The
# copies were identical, but nothing kept them that way — and the sibling primitives in these very
# libs had ALREADY diverged twice (the PreCompact round scanner leaked to stderr; `marker_mtime`
# returned its failure sentinel on FreeBSD, which silently disabled a quality gate). Copies that are
# identical today are a latent defect, not a safe state.
#
# WHY EACH CALLER STILL KEEPS AN INLINE FALLBACK
# These libs are sourced STANDALONE, not only through hook-io.sh:
#   * agents/swift-reviewer.md sources context.sh alone into a zsh Bash-tool context;
#   * scripts/test-hooks.sh sources marker.sh and context.sh without hook-io.sh;
#   * scripts/{capture-reviewer-verdict,capture-reviewer-round-start,build-failure-log,
#     permission-denied-log}.sh each source one lib directly.
# Making any of them ABORT when paths.sh cannot be located would convert three independent
# fail-open paths into one shared point of failure — a strictly worse posture than the triplication
# it replaces, for a defect that has never fired. So every caller keeps the literal expansion as a
# fallback, and this file is an optimisation of maintenance, not a load-bearing dependency.
#
# THE EXPANSION ITSELF — two details are load-bearing:
#   * `:-` NOT `-`. The single-dash form treats an explicitly-EMPTY CLAUDE_PLUGIN_DATA as "set" and
#     returns empty, which relocates every marker, log and snapshot to a relative path. It passes a
#     three-environment matrix identically to the correct form and fails only on the set-but-empty
#     case, which is why scripts/tests/test_shell_primitive_drift.py tests four environments.
#   * `${HOME:-}` inner guard, so a missing HOME under `set -u` never aborts a hook. With both unset
#     the path becomes "/.claude/unleashed-mail" and the later mkdir simply fails open.

# Idempotent: these libs are frequently sourced more than once in a single shell.
if [ -z "${_UNLEASHED_PATHS_SH_LOADED:-}" ]; then
    _UNLEASHED_PATHS_SH_LOADED=1

    unleashed_plugin_base() {
        printf '%s' "${CLAUDE_PLUGIN_DATA:-${HOME:-}/.claude/unleashed-mail}"
    }
fi
