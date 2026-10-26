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
    # THE FLAG LETTERS ONLY, never the whole line. `declare -p` prints `declare -<flags> NAME="<value>"`
    # and the VALUE is attacker-supplied: matched against the whole line, `"declare -"*r*" NAME="*` let a
    # value of `r _UNLEASHED_BASE_INSTANCE=` provide both the `r` and the name, so an inherited
    # `declare -x` passed as READONLY and the inherited resolution was trusted (codex sweep, PR #67
    # pass 14 — reproduced). Everything from the first ` _UNLEASHED_BASE_INSTANCE` on is dropped BEFORE
    # the test, so only the shell's own flags are read; absent output leaves the empty string, which
    # matches nothing and discards — the fail-safe direction. Measured shapes: bash `declare -r`,
    # `declare -rx`, inherited `declare -x`; zsh `typeset -r`, `export -r`, inherited `export`.
    _ubi_decl="$( { declare -p _UNLEASHED_BASE_INSTANCE 2>/dev/null || typeset -p _UNLEASHED_BASE_INSTANCE 2>/dev/null; } )"
    case "${_ubi_decl%% _UNLEASHED_BASE_INSTANCE*}" in
        "declare -"*r*|"typeset -"*r*|"export -"*r*|readonly) : ;;
        # `|| :` on BOTH: zsh's `unset -f` returns 1 for a function that is not defined, and under
        # `set -e` / `setopt err_return` that killed the sourcing of every copy the moment the stamp
        # arrived through the environment (codex sweep, PR #67 pass 14 — reproduced, zsh only).
        *)  unset -f _unleashed_resolved_in_process 2>/dev/null || :; _UNLEASHED_BASE_PID=; unset _UNLEASHED_BASE_INSTANCE 2>/dev/null || : ;;
    esac
    unset _ubi_decl 2>/dev/null || :
fi
# paths.sh is sourced UNCONDITIONALLY when readable — never behind "its API is already present":
# bash `set -a` exports every function, so a present namespace can be an inherited one, attacker's
# resolver included (codex, PR #67 pass 12). Sourcing it again is idempotent: it redefines its own
# functions and resolves only if this instance has not (see the instance check above).
# NO EXTERNAL COMMAND MAY TAKE PART IN THIS. `dirname` is resolved through PATH, and the parent
# that supplies a tampered function set supplies PATH too: with `/usr/bin` off it `dirname` was
# not found, the directory fell back to the caller's cwd, the four libraries "were not readable"
# although they sit right beside this file, and the loader's presence fallback then trusted the
# imported machinery — RESOLVED=/attacker in all five copies (codex sweep, PR #67 pass 14 —
# reproduced). The directory now comes from a parameter expansion, and `cd`/`pwd` are shell
# BUILTINS, so nothing on this path consults PATH.
_upb_d="${BASH_SOURCE[0]:-$0}"
case "$_upb_d" in
    */*) _upb_d="${_upb_d%/*}"; [ -n "$_upb_d" ] || _upb_d="/" ;;
    *)   _upb_d="." ;;
esac
_upb_d="$( { CDPATH='' cd -P -- "$_upb_d" && pwd -P; } 2>/dev/null )" || _upb_d="."
[ -n "$_upb_d" ] || _upb_d="."
# shellcheck source=scripts/lib/paths.sh
if [ -r "$_upb_d/paths.sh" ]; then . "$_upb_d/paths.sh"; fi
# COREDEV-2617 §4.2a: the fallback is the FULL three-step resolution, not the D′ two-step — this is
# one of the five resolver copies FAM-1 names, and arm equivalence (rows 99/100/103) requires all
# five to report ALL FOUR protocol variables identically in every cell. The machinery loads from
# this file's own directory; when it is absent the resolution degrades to the D′ envelope, which is
# never worse than the pre-2617 behaviour.
_upb_state_load() {
    # LOADED means THE FUNCTIONS EXIST — never a flag. A flag lives in the environment and a child
    # process inherits it while inheriting no functions; keyed on the flag, this returned "loaded"
    # into a shell where `_unleashed_read_store` was undefined, and the resolver died with
    # `command not found`, every protocol variable unset (codex, PR #67 pass 7 — reproduced).
    # AND "THE FUNCTIONS EXIST" IS NOT "THE FUNCTIONS ARE OURS": bash `set -a` exports functions, so
    # keyed on presence this skipped the libraries and trusted an imported `_unleashed_read_store`
    # (codex, PR #67 pass 14 — reproduced). Re-source from the files beside this loader whenever they
    # are readable; the functions already present are used only where the files are not.
    _upb_readable=1
    for _upb_f in plugin-state-auth plugin-state-store plugin-state-reader plugin-state-publisher; do
        [ -r "${_upb_d:-.}/$_upb_f.sh" ] || { _upb_readable=0; break; }
    done
    if [ "$_upb_readable" = 1 ]; then
        for _upb_f in plugin-state-auth plugin-state-store plugin-state-reader plugin-state-publisher; do
            # shellcheck source=/dev/null
            . "${_upb_d:-.}/$_upb_f.sh"
        done
        return 0
    fi
    if command -v _unleashed_key >/dev/null 2>&1 && command -v _unleashed_auth_chain >/dev/null 2>&1 \
        && command -v _unleashed_read_store >/dev/null 2>&1 && command -v _unleashed_publish >/dev/null 2>&1; then
        return 0
    fi
    return 1
}
if [ "${_UNLEASHED_BASE_PID:-}" != "$$" ] || ! command -v _unleashed_resolved_in_process >/dev/null 2>&1; then   # resolved in THIS shell instance? pid + marker function
    _UNLEASHED_BASE_DIAGNOSED=                          # the entry point resets what it caches on
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
    _UNLEASHED_BASE_PID=$$
    _UNLEASHED_BASE_ENV="${CLAUDE_PLUGIN_DATA:-}"           # the environment this resolution was made under
    _unleashed_resolved_in_process() { :; }
    # THE STAMP — the attribute NO environment carries (see top). Set ONCE, only when absent, and errexit-
    # safe: the bridge re-resolves an already-stamped instance, and bash treats `readonly X=1` on a readonly
    # X as a FATAL assignment error under `set -e`, even behind `|| :` — the sourcing shell exited (codex,
    # PR #67 pass 14 — reproduced). "Absent" is the right test because the sourcing-time check above already
    # discarded any inherited value, so a present value here is this instance's own. Under zsh the stamp is
    # declared GLOBAL: a bare `readonly` inside a function is function-local there, so the resolver's stamp
    # vanished at return and the zsh arm never held the attribute (measured, same pass).
    if [ -z "${_UNLEASHED_BASE_INSTANCE+set}" ]; then
        if [ -n "${ZSH_VERSION:-}" ]; then typeset -g -r _UNLEASHED_BASE_INSTANCE=1 2>/dev/null; else readonly _UNLEASHED_BASE_INSTANCE=1 2>/dev/null; fi
    fi
fi
# The state test MUST exist even when paths.sh was not found — otherwise `unleashed_base_ok` is an
# undefined command (exit 127) and every guarded writer would skip on a PERFECTLY VALID base. That
# fail-open -> fail-closed inversion is exactly what COREDEV-2617's round-18 reproduction caught in
# the agent fence; it must not be re-introduced one layer down.
# Defined UNCONDITIONALLY: an imported (`set -a`-exported) copy must be replaced, not kept; when
# paths.sh was sourced above this is the same one-line predicate again (codex, PR #67 pass 12).
unleashed_base_ok() { [ "${_UNLEASHED_BASE_OK:-0}" = 1 ]; }


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
#
# COREDEV-2617 §4.2a: EVERY persisted record carries `base_resolution` naming the resolution that
# actually ran (`host-env` | `pointer` | `unresolved`) — the markers, the round bindings and the
# PreCompact snapshot stamp it where they build their record. Log records are built by four separate
# producers (`stop-failure-log.sh`, `build-failure-log.sh`, `permission-denied-log.sh`,
# `swift-build-verify.sh`), and none of them did, so a record written under a `pointer` resolution
# was indistinguishable from one written under `host-env` (codex, PR #67 pass 7). The stamp is
# applied HERE, in the one writer every producer goes through — a rule that lives in one producer
# is a rule the next producer will not have — and it is applied only when the line is a JSON
# object without the field already: the last `}` is the object's close (a JSON object line always
# ends with it), the value is one of three fixed tokens, and an empty object takes no separator.
# A line that is not an object is written unchanged; the producer owns its shape.
log_append() {
    unleashed_base_ok || return 0        # D' (COREDEV-2617): unresolved base persists nothing.
    local name="$1" line="$2" max="${3:-500}" dir="" _la_path="" tmp="" keep="" n="" body=""
    case "$max" in ''|*[!0-9]*) max=500 ;; esac
    case "$line" in
        *'"base_resolution"'*) : ;;                       # the producer stamped it itself
        \{*\})
            body="${line#\{}"; body="${body%\}}"
            case "$body" in
                *[!\ ]*) line="{${body},\"base_resolution\":\"${_UNLEASHED_BASE_SOURCE:-unresolved}\"}" ;;
                *)       line="{\"base_resolution\":\"${_UNLEASHED_BASE_SOURCE:-unresolved}\"}" ;;
            esac ;;
    esac
    dir="$(log_dir)"
    mkdir -p "$dir" 2>/dev/null || return 0
    _la_path="$dir/$name"
    # `2>/dev/null` BEFORE the `>>` so an OPEN failure (path is a dir / unwritable) is also
    # suppressed — bash applies redirects left-to-right, so a trailing `2>/dev/null` would NOT
    # catch the open error and the shell would print the full (PII-bearing) path to stderr.
    printf '%s\n' "$line" 2>/dev/null >> "$_la_path" || return 0
    # `2>/dev/null` BEFORE the `<` input redirect so an open-for-read failure (e.g. the file is
    # write-only) can't print the path to stderr either.
    n="$(wc -l 2>/dev/null < "$_la_path" | tr -d '[:space:]')"
    case "$n" in ''|*[!0-9]*) return 0 ;; esac
    if [ "$n" -gt "$max" ]; then
        keep=$(( max / 2 ))
        [ "$keep" -gt 0 ] || keep=1
        tmp="${_la_path}.tmp.$$"
        if tail -n "$keep" "$_la_path" 2>/dev/null > "$tmp"; then
            mv "$tmp" "$_la_path" 2>/dev/null || rm -f "$tmp" 2>/dev/null
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
