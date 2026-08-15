# shellcheck shell=bash
# Single source of the plugin-data base path (COREDEV-2600 item 1; D′ resolution COREDEV-2617).
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
# ── COREDEV-2617: D′ — AN UNRESOLVED BASE PERSISTS NOTHING ────────────────────────────────────────
# CLAUDE_PLUGIN_DATA is exported to hooks and MCP subprocesses but NOT to an ordinary shell, so state
# written outside a hook landed in a SECOND directory and the two never saw each other. D′: when the
# variable is unset the base does not resolve, and nothing is read or written — no silent second store.
#
# THE SENTINEL, and why it is not the empty string.
# A path-returning primitive that returns "" still composes a ROOT path at the call site:
# "$(marker_dir)/x" becomes "/x". So an unresolved base returns a POISONED, non-empty, non-root value:
#   /dev/null/unresolved-plugin-base
# /dev/null is a character device, so EVERY path beneath it is ENOTDIR — mkdir, mktemp, redirect and
# open all fail harmlessly and loudly at a fixed, greppable location, `[ -f ]` is false, and an
# UNGUARDED caller can never touch `/`. Verified by execution (plan §7).
#
# THE PROTOCOL — three shared variables, set once, in the SOURCING shell:
#   _UNLEASHED_BASE_RESOLVED  the base to use (real path, or the sentinel)
#   _UNLEASHED_BASE_OK        1 = resolved, 0 = sentinel in force. Primitives branch on THIS,
#                             never on a string comparison against the sentinel — otherwise a caller
#                             could fake resolution by exporting the sentinel text.
#   _UNLEASHED_BASE_DIAGNOSED  guards the ONE diagnostic per process.
#   _UNLEASHED_BASE_PID       the pid of the process that resolved — half of the once-per-process key;
#                             the other half is the FUNCTION `_unleashed_resolved_in_process`, defined
#                             at resolution time and never at definition time. `exec` keeps `$$` and
#                             an `allexport` wrapper carries every variable across it, so a hook exec'd
#                             after such a wrapper inherited a matching PID and the wrapper's stale base
#                             (codex, PR #67 pass 11 — reproduced); functions do not cross exec, so the
#                             marker function is what a fresh shell instance cannot have inherited.
# NOTHING HERE IS KEYED ON A BARE FLAG, because a flag is inheritable and a function is not (codex,
# PR #67 pass 7 — each of these was reproduced): a child process that inherited
# `_UNLEASHED_BASE_OK=1` alone skipped resolution and `marker_dir` returned `/.state` — the ROOT
# path D′ exists to prevent; an inherited `_UNLEASHED_STATE_LOADED=1` made the loader report the
# machinery present in a shell where `_unleashed_read_store` was undefined; an inherited
# `_UNLEASHED_PATHS_SH_LOADED=1` made this file define nothing at all. So: "already sourced" is
# `command -v` on a function this file defines; "machinery loaded" is `command -v` on its four
# entry functions; "resolved in this process" is `_UNLEASHED_BASE_PID = $$` — a subshell shares
# `$$` and the resolution, a child process has its own and resolves afresh, and an environment
# cannot carry the right value by accident. The resolver RESETS `_UNLEASHED_BASE_DIAGNOSED` on
# entry for the same reason: cache only on state the entry point itself resets.
# EAGER: resolution runs at source time, in the sourcing shell — not on first use. A value first
# assigned inside `$(marker_dir)` lives in that subshell and is gone on return, so a lazily-built
# "cache" silently re-resolves on every call.
# The cardinality guard is the FLAG, not this file: each lib's inline fallback emits the diagnostic
# only while _UNLEASHED_BASE_OK is unset, so exactly one is emitted whether or not paths.sh was found.
#
# THE LEGACY EXPANSION is retained as `unleashed_plugin_legacy_base` for the drift matrix only. It is
# NOT the resolver any more:
#   * `:-` NOT `-`. The single-dash form treats an explicitly-EMPTY CLAUDE_PLUGIN_DATA as "set" and
#     returns empty, which relocated every marker, log and snapshot to a relative path.
#   * `${HOME:-}` inner guard, so a missing HOME under `set -u` never aborts a hook.

# The poisoned sentinel. Literal, fixed and greppable — tests assert on this exact string.
_UNLEASHED_BASE_SENTINEL='/dev/null/unresolved-plugin-base'

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

# Idempotent: these libs are frequently sourced more than once in a single shell. Keyed on the
# COMPLETE resolver API being present, not on a flag and not on ONE function: bash `export -f` carries a
# single function through the environment, and a guard on that one function skipped this whole block
# in a shell where `unleashed_plugin_base` and `unleashed_base_ok` were undefined (codex, PR #67 pass
# 11). If any of the six is missing the block runs and (re)defines them all — an imported copy of the
# library's own function is replaced by the library's own definition, never trusted.
if ! { command -v unleashed_resolve_base >/dev/null 2>&1 && command -v unleashed_plugin_base >/dev/null 2>&1 \
    && command -v unleashed_base_ok >/dev/null 2>&1 && command -v _unleashed_load_state_machinery >/dev/null 2>&1 \
    && command -v _unleashed_home_ok >/dev/null 2>&1 && command -v unleashed_plugin_legacy_base >/dev/null 2>&1; }; then

    # The pre-2617 expansion. Kept ONLY so the drift matrix can assert the legacy behaviour it
    # documents; no primitive calls it.
    unleashed_plugin_legacy_base() {
        printf '%s' "${CLAUDE_PLUGIN_DATA:-${HOME:-}/.claude/unleashed-mail}"
    }

    # ── COREDEV-2617 §4.2a — the store, and why this is not just the D′ expansion ─────────────────
    # D′ made an unset variable resolve to the sentinel. That is safe but it is not a CAPABILITY: a
    # git hook or an ordinary terminal, which never receive the variable, still cannot find the base.
    # §4.2a adds the store — each publisher records its base under a name that is an injective
    # encoding of the value, so a reader can discover it and a disagreement is visible as a conflict
    # rather than as a silent second directory.
    #
    # The machinery lives in `plugin-state-{auth,store,reader,publisher}.sh`, NOT inline here, and it
    # is sourced independently of this file. That matters: the other family files must be able to
    # resolve from the store when THIS file cannot be located, so the machinery cannot hang off it.
    # If the machinery itself is missing, the resolution degrades to the D′ envelope — sentinel,
    # `OK=0`, one diagnostic — which is exactly the pre-2617 behaviour and is never worse than it.
    # THE DIRECTORY IS CAPTURED AT SOURCE TIME, NOT INSIDE THE FUNCTION, AND THAT IS LOAD-BEARING.
    # `${BASH_SOURCE[0]:-$0}` is cross-shell at TOP LEVEL — measured: bash sets BASH_SOURCE to the
    # sourced file and zsh sets `$0` to it, so `dirname` is correct in both, for absolute, relative
    # and nested-source invocations alike. INSIDE A FUNCTION the two diverge: bash's BASH_SOURCE[0]
    # is still the defining file, while zsh sets `$0` to the FUNCTION NAME (FUNCTION_ARGZERO, on by
    # default). Measured: the first version of this loader ran that expansion inside the function,
    # resolved its directory to `.`, found none of the four libraries, and silently degraded zsh to
    # the D′ envelope — the variable-set branch reported `none` instead of `created` and a subsequent
    # reader resolved nothing, while bash did the right thing.
    _UNLEASHED_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _UNLEASHED_LIB_DIR="."

    _unleashed_load_state_machinery() {
        # LOADED means THE FUNCTIONS EXIST — never a flag. A flag lives in the environment and a child
        # process inherits it while inheriting no functions; keyed on the flag, this returned "loaded"
        # into a shell where `_unleashed_read_store` was undefined, and the resolver died with
        # `command not found`, every protocol variable unset (codex, PR #67 pass 7 — reproduced).
        if command -v _unleashed_key >/dev/null 2>&1 && command -v _unleashed_auth_chain >/dev/null 2>&1 \
            && command -v _unleashed_read_store >/dev/null 2>&1 && command -v _unleashed_publish >/dev/null 2>&1; then
            return 0
        fi
        _usm_d="$_UNLEASHED_LIB_DIR"
        for _usm_f in plugin-state-auth plugin-state-store plugin-state-reader plugin-state-publisher; do
            [ -r "$_usm_d/$_usm_f.sh" ] || return 1
            # shellcheck source=/dev/null
            . "$_usm_d/$_usm_f.sh"
        done
        return 0
    }

    # PUB-2's precondition, computed once: HOME must be non-empty AND absolute. Every expansion of
    # HOME on this path uses `${HOME:-}` so a missing HOME under `set -u` never aborts a hook.
    _unleashed_home_ok() {
        case "${HOME:-}" in
            /*) return 0 ;;
            *)  return 1 ;;
        esac
    }

    # Eager, source-time resolution. Sets the four protocol variables exactly once per process.
    unleashed_resolve_base() {
        # already resolved in THIS shell instance: same pid AND the marker function this instance defined
        [ "${_UNLEASHED_BASE_PID:-}" = "$$" ] && command -v _unleashed_resolved_in_process >/dev/null 2>&1 && return 0
        _UNLEASHED_BASE_DIAGNOSED=                           # the entry point resets what it caches on
        if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
            # Step 1 — the variable wins, and it is the ONLY branch from which a publish is
            # reachable (PUB-1). The publish is a side effect of having resolved, never a condition
            # of it: whatever it reports, this shell's base is the variable's value.
            _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
            _UNLEASHED_BASE_OK=1
            _UNLEASHED_BASE_SOURCE='host-env'
            _UNLEASHED_POINTER_STATE=none
            # PUB-9's exits, in order: E0 (publishing disabled) -> `none`; E1 (HOME unusable) ->
            # `failed` WITH its one diagnostic — an unavailable publication must not read as one that
            # was deliberately disabled (codex, PR #67); otherwise publish, which sets the state.
            if [ "${_UNLEASHED_PUBLISH_OK:-1}" = 0 ]; then
                :                                            # E0: none, silent
            elif ! _unleashed_home_ok; then
                _UNLEASHED_POINTER_STATE=failed              # E1
                printf 'unleashed-mail: plugin-state publication failed: HOME is empty or not absolute\n' >&2
            elif _unleashed_load_state_machinery; then
                _unleashed_publish "${HOME:-}/.claude/unleashed-mail/bases" "$CLAUDE_PLUGIN_DATA"
                # The publish sets POINTER_STATE and may set SOURCE; the resolved value is unchanged.
                _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
                _UNLEASHED_BASE_OK=1
            fi
        elif _unleashed_home_ok && _unleashed_load_state_machinery; then
            # Step 2 — the store. The ordered reader rules set all four variables and emit at most
            # one diagnostic; rule 3 emits none, because a resolution is the ordinary case.
            # THIS file owns the wording about the environment variable — the reader is told the
            # prefix and never names it, which keeps N5's allowlist tight.
            _UNLEASHED_UNRESOLVED_PREFIX='CLAUDE_PLUGIN_DATA is unset and '
            _unleashed_read_store "${HOME:-}/.claude/unleashed-mail/bases"
        else
            # Step 3 — the D′ envelope: no variable, and no store to consult.
            _UNLEASHED_BASE_RESOLVED="$_UNLEASHED_BASE_SENTINEL"
            _UNLEASHED_BASE_OK=0
            _UNLEASHED_BASE_SOURCE=unresolved
            _UNLEASHED_POINTER_STATE=none
            if [ -z "${_UNLEASHED_BASE_DIAGNOSED:-}" ]; then
                _UNLEASHED_BASE_DIAGNOSED=1
                printf 'unleashed-mail: CLAUDE_PLUGIN_DATA is unset; plugin state will not be read or written this run\n' >&2
            fi
        fi
        _UNLEASHED_BASE_PID=$$
        _unleashed_resolved_in_process() { :; }             # the marker a fork/subshell keeps and exec drops
        readonly _UNLEASHED_BASE_INSTANCE=1 2>/dev/null     # the attribute NO environment carries (see top)
        return 0
    }

    # The resolver every primitive calls. Returns the sentinel when unresolved — never empty.
    unleashed_plugin_base() {
        unleashed_resolve_base
        printf '%s' "$_UNLEASHED_BASE_RESOLVED"
    }

    # True when the base resolved. The ONLY sanctioned way for a consumer to test the state.
    unleashed_base_ok() {
        [ "${_UNLEASHED_BASE_OK:-0}" = 1 ]
    }

fi
# EAGER — at source time, in the sourcing shell — and OUTSIDE the definition block, so a shell whose
# functions arrived through the environment (bash `set -a` + exec) still resolves afresh here after
# the instance check above discarded the inherited resolution. Fork-free when already resolved.
unleashed_resolve_base
