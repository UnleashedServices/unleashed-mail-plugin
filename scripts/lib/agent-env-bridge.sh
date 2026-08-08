# shellcheck shell=bash
# Bridge CLAUDE_PLUGIN_DATA into an agent's Bash-tool shell (COREDEV-2617, §7 step 3).
#
# WHY THIS FILE EXISTS
# CLAUDE_PLUGIN_DATA is exported to hooks, MCP servers and their subprocesses — NOT to the Bash tool.
# Without a bridge, `reviewer-roster.sh` (which sources context.sh) resolves a different base from the
# SubagentStop capture hooks that wrote the state, and every persisted capture/.status/ratchet is
# invisible. Agent fences used to carry a copy-pasted `export CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}"`;
# D' requires ONE documented bridge instead of per-agent copy-paste.
#
# HOW IT IS CALLED — the fence passes BOTH values in:
#
#     source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/agent-env-bridge.sh" \
#            "${CLAUDE_PLUGIN_DATA}" "${CLAUDE_PLUGIN_ROOT}"
#
#   * Both placeholders are the EXACT braced tokens — the only form Claude Code substitutes — and both
#     sit in AGENT CONTENT, the only place it substitutes them. A `${CLAUDE_PLUGIN_DATA}` written
#     inside THIS file would never be substituted and would export an empty value.
#   * $2 is passed because CLAUDE_PLUGIN_ROOT is unset in an ordinary Bash-tool shell, so this file
#     cannot locate itself from the environment. It must not use ${BASH_SOURCE[0]} either: that is a
#     Bash-only array and the fence context is zsh (see paths.sh's header).
#
# $1 = CLAUDE_PLUGIN_DATA value (may be empty)   $2 = CLAUDE_PLUGIN_ROOT

export CLAUDE_PLUGIN_DATA="${1-}"          # empty is PRESERVED, not unset — see below

# Prefer the shared resolver so the bridge and the libs run one code path. GUARDED: paths.sh is an
# optimisation of maintenance, not a load-bearing dependency, and an unguarded `.` on a missing file
# returns 1 in Bash / 127 in zsh and terminates an `errexit` caller.
if [ -z "${_UNLEASHED_PATHS_SH_LOADED:-}" ] && [ -r "$2/scripts/lib/paths.sh" ]; then
    # shellcheck source=scripts/lib/paths.sh
    . "$2/scripts/lib/paths.sh"
fi

# ALWAYS establish the protocol, even when paths.sh was not found. The agent fence has NO inline
# fallback of its own — unlike marker.sh/log.sh/context.sh — so if this file returned without setting
# the flag, the consumer rule "unset ⇒ unresolved" would make the fence report NO CAPTURE on a
# PERFECTLY VALID base. That fail-open → fail-closed inversion is what COREDEV-2617's round-18
# reproduction caught; it must not be re-introduced here.
if [ -z "${_UNLEASHED_BASE_OK:-}" ]; then
    if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
        _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
        _UNLEASHED_BASE_OK=1
    else
        _UNLEASHED_BASE_RESOLVED='/dev/null/unresolved-plugin-base'
        _UNLEASHED_BASE_OK=0
        if [ -z "${_UNLEASHED_BASE_DIAGNOSED:-}" ]; then
            _UNLEASHED_BASE_DIAGNOSED=1
            printf 'unleashed-mail: CLAUDE_PLUGIN_DATA is unset; plugin state will not be read or written this run\n' >&2
        fi
    fi
fi

# The sanctioned state test, for consumers that source only this bridge.
if ! command -v unleashed_base_ok >/dev/null 2>&1; then
    unleashed_base_ok() { [ "${_UNLEASHED_BASE_OK:-0}" = 1 ]; }
fi
