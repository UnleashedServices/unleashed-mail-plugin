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

# Idempotent: these libs are frequently sourced more than once in a single shell.
if [ -z "${_UNLEASHED_PATHS_SH_LOADED:-}" ]; then
    _UNLEASHED_PATHS_SH_LOADED=1

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
        [ -n "${_UNLEASHED_STATE_LOADED:-}" ] && return "${_UNLEASHED_STATE_RC:-0}"
        _UNLEASHED_STATE_LOADED=1
        _usm_d="$_UNLEASHED_LIB_DIR"
        for _usm_f in plugin-state-auth plugin-state-store plugin-state-reader plugin-state-publisher; do
            if [ -r "$_usm_d/$_usm_f.sh" ]; then
                # shellcheck source=/dev/null
                . "$_usm_d/$_usm_f.sh"
            else
                _UNLEASHED_STATE_RC=1
                return 1
            fi
        done
        _UNLEASHED_STATE_RC=0
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
        [ -n "${_UNLEASHED_BASE_OK:-}" ] && return 0        # already resolved in this shell
        if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
            # Step 1 — the variable wins, and it is the ONLY branch from which a publish is
            # reachable (PUB-1). The publish is a side effect of having resolved, never a condition
            # of it: whatever it reports, this shell's base is the variable's value.
            _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
            _UNLEASHED_BASE_OK=1
            _UNLEASHED_BASE_SOURCE='env'
            _UNLEASHED_POINTER_STATE=none
            if [ "${_UNLEASHED_PUBLISH_OK:-1}" != 0 ] && _unleashed_home_ok \
               && _unleashed_load_state_machinery; then
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

    unleashed_resolve_base        # EAGER — at source time, in the sourcing shell.
fi
