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
# The bridge is the FIFTH resolver copy (FAM-1) and it NEVER PUBLISHES (PUB-1) — but row 65 requires
# it to READ: with empty $1, paths.sh absent, and one valid entry in the store, the fence must
# resolve that entry and report all four protocol variables, not report OK=0. It locates the
# machinery through $2, the plugin root the fence passes in, because neither CLAUDE_PLUGIN_ROOT nor
# BASH_SOURCE exists in a zsh Bash-tool shell.
_ueb_state_load() {
    [ -n "${_UNLEASHED_STATE_LOADED:-}" ] && return "${_UNLEASHED_STATE_RC:-0}"
    _UNLEASHED_STATE_LOADED=1
    _UNLEASHED_STATE_RC=1
    # $1 here is the PLUGIN ROOT the caller passes — the function's own parameter, not the
    # file's; the file-level $2 is forwarded at the call site below.
    for _ueb_f in plugin-state-auth plugin-state-store plugin-state-reader plugin-state-publisher; do
        [ -r "${1-}/scripts/lib/$_ueb_f.sh" ] || return 1
        # shellcheck source=/dev/null
        . "${1-}/scripts/lib/$_ueb_f.sh"
    done
    _UNLEASHED_STATE_RC=0
    return 0
}
if [ -z "${_UNLEASHED_BASE_OK:-}" ]; then
    if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
        _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
        _UNLEASHED_BASE_OK=1
        _UNLEASHED_BASE_SOURCE='env'
        _UNLEASHED_POINTER_STATE=none
    else
        _ueb_home_ok=0
        case "${HOME:-}" in /*) _ueb_home_ok=1 ;; esac
        if [ "$_ueb_home_ok" = 1 ] && _ueb_state_load "${2-}"; then
            _UNLEASHED_UNRESOLVED_PREFIX='CLAUDE_PLUGIN_DATA is unset and '
            _unleashed_read_store "${HOME:-}/.claude/unleashed-mail/bases"
        else
            _UNLEASHED_BASE_RESOLVED='/dev/null/unresolved-plugin-base'
            _UNLEASHED_BASE_OK=0
            _UNLEASHED_BASE_SOURCE=unresolved
            _UNLEASHED_POINTER_STATE=none
            if [ -z "${_UNLEASHED_BASE_DIAGNOSED:-}" ]; then
                _UNLEASHED_BASE_DIAGNOSED=1
                printf 'unleashed-mail: CLAUDE_PLUGIN_DATA is unset; plugin state will not be read or written this run\n' >&2
            fi
        fi
    fi
fi

# The sanctioned state test, for consumers that source only this bridge.
if ! command -v unleashed_base_ok >/dev/null 2>&1; then
    unleashed_base_ok() { [ "${_UNLEASHED_BASE_OK:-0}" = 1 ]; }
fi
