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

# THE BRIDGE NEVER PUBLISHES (PUB-1), AND THIS IS THE STATEMENT THAT MAKES IT TRUE — placed FIRST,
# before the value is exported and before paths.sh is sourced, because paths.sh publishes EAGERLY
# at source time when the value is non-empty. The value the fence passes in is whatever the agent
# content substituted — not necessarily authoritative, and possibly stale — so letting it publish
# could create a durable SECOND entry and leave every ordinary reader in `conflict`; even the
# normal case would perform the publication walk and could emit failure output into the agent's
# shell (codex, PR #67). PUB-9 E0 maps this to `none`, which is exactly what a bridge should report.
_UNLEASHED_PUBLISH_OK=0
export CLAUDE_PLUGIN_DATA="${1-}"          # empty is PRESERVED, not unset — see below

# Prefer the shared resolver so the bridge and the libs run one code path. GUARDED: paths.sh is an
# optimisation of maintenance, not a load-bearing dependency, and an unguarded `.` on a missing file
# returns 1 in Bash / 127 in zsh and terminates an `errexit` caller.
# THE INSTANCE CHECK — once per sourcing, before anything trusts a resolution it may have inherited.
# `exec` keeps `$$`, an `allexport` wrapper carries every variable across it, and in bash `set -a`
# carries every FUNCTION too — so after such a wrapper the exec'd hook held a matching pid, the marker
# function, and the wrapper's stale base (codex, PR #67 pass 11 — reproduced). What NO environment
# carries is a variable's READONLY attribute: `declare -p` / `typeset -p` show `-r` only in the shell
# instance that set it (measured: `declare -rx` becomes `declare -x` across exec in bash, `export -r`
# becomes `export` in zsh; a subshell keeps it). Resolution sets `readonly _UNLEASHED_BASE_INSTANCE`;
# a value present WITHOUT the attribute is inherited, and the inherited resolution is discarded here.
# One `declare -p` capture per SOURCING — the per-call guard below stays fork-free.
if [ -n "${_UNLEASHED_BASE_INSTANCE+set}" ]; then
    case "$( { declare -p _UNLEASHED_BASE_INSTANCE 2>/dev/null || typeset -p _UNLEASHED_BASE_INSTANCE 2>/dev/null; } )" in
        "declare -"*r*" _UNLEASHED_BASE_INSTANCE="*|"typeset -"*r*" _UNLEASHED_BASE_INSTANCE="*|"export -"*r*" _UNLEASHED_BASE_INSTANCE="*|"readonly "*) : ;;
        *)  unset -f _unleashed_resolved_in_process 2>/dev/null; _UNLEASHED_BASE_PID=; unset _UNLEASHED_BASE_INSTANCE 2>/dev/null ;;
    esac
fi
# "paths.sh already sourced" is the COMPLETE resolver API, never a flag (codex, PR #67 passes 7 and 11).
if ! { command -v unleashed_resolve_base >/dev/null 2>&1 && command -v unleashed_plugin_base >/dev/null 2>&1 \
    && command -v unleashed_base_ok >/dev/null 2>&1 && command -v _unleashed_load_state_machinery >/dev/null 2>&1; } && [ -r "$2/scripts/lib/paths.sh" ]; then
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
    # LOADED means THE FUNCTIONS EXIST — never a flag. A flag lives in the environment and a child
    # process inherits it while inheriting no functions; keyed on the flag, this returned "loaded"
    # into a shell where `_unleashed_read_store` was undefined, and the resolver died with
    # `command not found`, every protocol variable unset (codex, PR #67 pass 7 — reproduced).
    if command -v _unleashed_key >/dev/null 2>&1 && command -v _unleashed_auth_chain >/dev/null 2>&1 \
        && command -v _unleashed_read_store >/dev/null 2>&1 && command -v _unleashed_publish >/dev/null 2>&1; then
        return 0
    fi
    # $1 here is the PLUGIN ROOT the caller passes — the function's own parameter, not the
    # file's; the file-level $2 is forwarded at the call site below.
    for _ueb_f in plugin-state-auth plugin-state-store plugin-state-reader plugin-state-publisher; do
        [ -r "${1-}/scripts/lib/$_ueb_f.sh" ] || return 1
        # shellcheck source=/dev/null
        . "${1-}/scripts/lib/$_ueb_f.sh"
    done
    return 0
}
if [ "${_UNLEASHED_BASE_PID:-}" != "$$" ] || ! command -v _unleashed_resolved_in_process >/dev/null 2>&1; then   # pid + marker function
    _UNLEASHED_BASE_DIAGNOSED=                          # the entry point resets what it caches on
    if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
        _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
        _UNLEASHED_BASE_OK=1
        _UNLEASHED_BASE_SOURCE='host-env'
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
    _UNLEASHED_BASE_PID=$$
    _unleashed_resolved_in_process() { :; }
    readonly _UNLEASHED_BASE_INSTANCE=1 2>/dev/null       # the attribute no environment can carry across exec
fi

# The sanctioned state test, for consumers that source only this bridge.
if ! command -v unleashed_base_ok >/dev/null 2>&1; then
    unleashed_base_ok() { [ "${_UNLEASHED_BASE_OK:-0}" = 1 ]; }
fi
