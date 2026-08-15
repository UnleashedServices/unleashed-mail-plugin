#!/usr/bin/env bash
# shellcheck shell=bash
# Shared bounded-JSONL logger for the Item-10 diagnostic hooks (Phase 2, COREDEV-2325).
#
# This file is SOURCED, never executed.
#
# Logs live OUTSIDE the repo, under the plugin data dir — never /tmp, never the repo.
# Every record is PII-free BY CONSTRUCTION: callers pass only enums / command-classes /
# pre-sanitized text (see scripts/lib/hook-io.sh `hook_redact_pii`). The base dir is
# space-free but CLAUDE_PLUGIN_DATA may not be, so every path is quoted. Every probe and
# write is `2>/dev/null` and fail-open: a logging failure must never abort a hook or leak
# a path to stderr.

# ── COREDEV-2617 / D': resolve the plugin-data base ONCE, EAGERLY, at source time ────────────────
# Prefer the single source (scripts/lib/paths.sh). If it cannot be located this lib establishes the
# SAME protocol itself rather than aborting — these libs are sourced standalone (see paths.sh's
# header), so aborting would turn three independent fail-open paths into one shared point of failure.
#
# The duplication below is deliberate and bounded: it is the D' protocol, not the legacy expansion.
# An unresolved base yields the POISONED SENTINEL (non-empty, non-root, ENOTDIR beneath it), never
# the empty string — an empty base composes a ROOT path at the call site.
#
# The one-diagnostic-per-process guard is the shared FLAG, not this file: with paths.sh absent, two
# or three libs sourced in one shell would otherwise each emit one.
if [ -z "${_UNLEASHED_PATHS_SH_LOADED:-}" ]; then
    _upb_d="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _upb_d="."
    # shellcheck source=scripts/lib/paths.sh
    [ -r "$_upb_d/paths.sh" ] && . "$_upb_d/paths.sh"
fi
# COREDEV-2617 §4.2a: the fallback is the FULL three-step resolution, not the D′ two-step — this is
# one of the five resolver copies FAM-1 names, and arm equivalence (rows 99/100/103) requires all
# five to report ALL FOUR protocol variables identically in every cell. The machinery loads from
# this file's own directory; when it is absent the resolution degrades to the D′ envelope, which is
# never worse than the pre-2617 behaviour.
_upb_state_load() {
    [ -n "${_UNLEASHED_STATE_LOADED:-}" ] && return "${_UNLEASHED_STATE_RC:-0}"
    _UNLEASHED_STATE_LOADED=1
    _UNLEASHED_STATE_RC=1
    for _upb_f in plugin-state-auth plugin-state-store plugin-state-reader plugin-state-publisher; do
        [ -r "${_upb_d:-.}/$_upb_f.sh" ] || return 1
        # shellcheck source=/dev/null
        . "${_upb_d:-.}/$_upb_f.sh"
    done
    _UNLEASHED_STATE_RC=0
    return 0
}
if [ -z "${_UNLEASHED_BASE_OK:-}" ]; then
    if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
        _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
        _UNLEASHED_BASE_OK=1
        _UNLEASHED_BASE_SOURCE='host-env'
        _UNLEASHED_POINTER_STATE=none
        # PUB-1: this file is one of the four PUBLISHING family files, and the publish is reachable
        # ONLY from this branch. The publish is a side effect of having resolved, never a condition.
        # PUB-9 E0 -> `none` silent; E1 (HOME unusable) -> `failed` with its diagnostic; else publish.
        if [ "${_UNLEASHED_PUBLISH_OK:-1}" = 0 ]; then
            :
        else
            case "${HOME:-}" in
                /*) if _upb_state_load; then
                        _unleashed_publish "${HOME:-}/.claude/unleashed-mail/bases" "$CLAUDE_PLUGIN_DATA"
                        _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
                        _UNLEASHED_BASE_OK=1
                    fi ;;
                *)  _UNLEASHED_POINTER_STATE=failed
                    printf 'unleashed-mail: plugin-state publication failed: HOME is empty or not absolute\n' >&2 ;;
            esac
        fi
    else
        _upb_home_ok=0
        case "${HOME:-}" in /*) _upb_home_ok=1 ;; esac
        if [ "$_upb_home_ok" = 1 ] && _upb_state_load; then
            # Step 2 — the store, through the ordered reader rules. The prefix keeps the D′ wording
            # contract; the reader itself never names the environment variable.
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
# The state test MUST exist even when paths.sh was not found — otherwise `unleashed_base_ok` is an
# undefined command (exit 127) and every guarded writer would skip on a PERFECTLY VALID base. That
# fail-open -> fail-closed inversion is exactly what COREDEV-2617's round-18 reproduction caught in
# the agent fence; it must not be re-introduced one layer down.
if ! command -v unleashed_base_ok >/dev/null 2>&1; then
    unleashed_base_ok() { [ "${_UNLEASHED_BASE_OK:-0}" = 1 ]; }
fi


log_base() {
    # COREDEV-2617 / D': the base was resolved ONCE, at source time, by the block above. Just print
    # it. Never re-resolve here — this function is invoked as $(...), so anything assigned inside it
    # lives in a subshell and is gone on return (the round-6 "cache" defect).
    printf '%s' "$_UNLEASHED_BASE_RESOLVED"
}

log_dir() {
    printf '%s/logs' "$(log_base)"
}

# Append one PRE-FORMED JSON line to logs/<name>, then cap the file by line count.
# $1 = log basename (e.g. error-log.jsonl), $2 = the JSON line (no trailing newline),
# $3 = max lines before rotation (default 500). On rotation the newest max/2 lines are
# kept (so we don't rotate on every subsequent write). Fail-open, stderr-clean.
log_append() {
    unleashed_base_ok || return 0        # D' (COREDEV-2617): unresolved base persists nothing.
    local name="$1" line="$2" max="${3:-500}" dir="" path="" tmp="" keep="" n=""
    case "$max" in ''|*[!0-9]*) max=500 ;; esac
    dir="$(log_dir)"
    mkdir -p "$dir" 2>/dev/null || return 0
    path="$dir/$name"
    # `2>/dev/null` BEFORE the `>>` so an OPEN failure (path is a dir / unwritable) is also
    # suppressed — bash applies redirects left-to-right, so a trailing `2>/dev/null` would NOT
    # catch the open error and the shell would print the full (PII-bearing) path to stderr.
    printf '%s\n' "$line" 2>/dev/null >> "$path" || return 0
    # `2>/dev/null` BEFORE the `<` input redirect so an open-for-read failure (e.g. the file is
    # write-only) can't print the path to stderr either.
    n="$(wc -l 2>/dev/null < "$path" | tr -d '[:space:]')"
    case "$n" in ''|*[!0-9]*) return 0 ;; esac
    if [ "$n" -gt "$max" ]; then
        keep=$(( max / 2 ))
        [ "$keep" -gt 0 ] || keep=1
        tmp="${path}.tmp.$$"
        if tail -n "$keep" "$path" 2>/dev/null > "$tmp"; then
            mv "$tmp" "$path" 2>/dev/null || rm -f "$tmp" 2>/dev/null
        else
            rm -f "$tmp" 2>/dev/null
        fi
    fi
    return 0
}

# UTC ISO-8601 timestamp, or "unknown" if the clock can't be read. Used as the `ts` field.
log_ts() {
    local t=""
    t="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    printf '%s' "${t:-unknown}"
}

# Classify a build/test command into a stable telemetry CLASS by its xcodebuild ACTION TOKEN — not a
# substring of the whole command, so a -scheme / -derivedDataPath / path value that happens to be
# "build" or "test" can't flip the class. SHARED by build-failure-log.sh + swift-build-verify.sh so
# one command ALWAYS classes the same on success and failure (codex PR review — no class split skews
# the build/test failure-rate telemetry). Prints the class, or nothing for a non-build/test command.
# $1 = the command string. The action is the first bare (non-flag, not a flag's value) token after
# `xcodebuild` matching a known action; build-for-testing -> build, test-without-building -> test.
build_class() {
    local cmd="$1" tok prev="" seen=0 has_test=0 has_build=0
    case "$cmd" in
        *xcodebuild*)
            local -a _toks=()
            local _split="" _line
            # Quote-aware tokenisation (python3 shlex) so a value-taking flag's VALUE with spaces
            # (e.g. -scheme "My build app") is ONE token, not split into a bare `build`/`test` token
            # that looks like an action (codex PR review). Fall back to a whitespace split if python3
            # is absent or shlex errors (unbalanced quotes) — best-effort, still consistent.
            if command -v python3 >/dev/null 2>&1; then
                # punctuation_chars=True separates shell operators ( ) ; & | < > so a compound form
                # like `xcodebuild build; echo` or `(xcodebuild test)` yields a clean `build`/`test`
                # token (codex PR review). posix=True still groups quoted values into one token.
                _split="$(printf '%s' "$cmd" | python3 -c 'import shlex, sys
try:
    lex = shlex.shlex(sys.stdin.read(), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    sys.stdout.write("\n".join(lex))
except Exception:
    sys.exit(1)' 2>/dev/null)" || _split=""
            fi
            if [ -n "$_split" ]; then
                while IFS= read -r _line; do _toks+=("$_line"); done <<<"$_split"
            else
                read -ra _toks <<<"$cmd"
            fi
            for tok in "${_toks[@]}"; do
                if [ "$seen" = 1 ]; then
                    case "$prev" in
                        # Skip the VALUE of a value-taking flag (so a -scheme/-derivedDataPath/path
                        # value named like an action isn't mistaken for one). Value-LESS flags
                        # (-quiet, -verbose, …) are NOT here, so an action right after one is still
                        # seen. xcodebuild allows MULTIPLE actions, so collect all (don't stop at a
                        # leading `clean`); test outranks build outranks other (codex PR review).
                        -scheme|-target|-project|-workspace|-configuration|-sdk|-destination|-arch|-derivedDataPath|-resultBundlePath|-archivePath|-exportPath|-exportOptionsPlist|-xcconfig|-toolchain|-testPlan|-only-testing|-skip-testing|-resultBundleVersion) ;;
                        *)
                            case "$tok" in
                                test|test-without-building) has_test=1 ;;
                                build|build-for-testing)    has_build=1 ;;
                            esac  # any other action (clean/analyze/archive/…) -> falls through to other
                            ;;
                    esac
                fi
                case "$tok" in *xcodebuild*) seen=1 ;; esac
                prev="$tok"
            done
            if   [ "$has_test"  = 1 ]; then printf 'xcodebuild-test'
            elif [ "$has_build" = 1 ]; then printf 'xcodebuild-build'
            else                            printf 'xcodebuild-other'
            fi
            ;;
        *"swift test"*)  printf 'swift-test' ;;
        *"swift build"*) printf 'swift-build' ;;
        *) ;;
    esac
}
