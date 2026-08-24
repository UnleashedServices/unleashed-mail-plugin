#!/usr/bin/env bash
# shellcheck shell=bash
# Shared quality-marker reader/writer for the Stop-gate (Item 4, COREDEV-2324).
#
# This file is SOURCED, never executed.
#
# Markers live OUTSIDE the repo, under the plugin data dir — never /tmp, never the
# repo. The body is PII-free: status/kind/ts/short-sha + a repo HASH only; the
# absolute repo path is consumed solely to compute the hash and is never written,
# emitted, or echoed to stderr. Every probe and state write is `2>/dev/null` and
# fail-open so a failed mkdir/redirect/mv can never leak a path or abort a hook.
#
# Marker body: {"status":"pass|fail","kind":"lint|build","ts":"…Z","commit":"<short>","repo_hash":"<12hex>"}
# Freshness source of truth is the marker FILE's mtime, not the `ts` field.

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


marker_base() {
    # COREDEV-2617 / D': the base was resolved ONCE, at source time, by the block above. Just print
    # it. Never re-resolve here — this function is invoked as $(...), so anything assigned inside it
    # lives in a subshell and is gone on return (the round-6 "cache" defect).
    printf '%s' "$_UNLEASHED_BASE_RESOLVED"
}

marker_dir() {
    printf '%s/.state' "$(marker_base)"
}

# Pure-bash 32-bit djb2 hash (hex) of a string. Used ONLY when no hashing binary
# exists. It emits a hash, never any path-derived characters, so the absolute path
# is never exposed (a `tr`-slug fallback would leak e.g. the username).
_marker_bash_hash() {
    local s="$1" i=0 len="${#1}" h=5381 c=0 ch=""
    while [ "$i" -lt "$len" ]; do
        ch="${s:$i:1}"
        # A single-quote char makes `printf '%d' "'${ch}"` the invalid constant "''"
        # which fails to 0; handle it explicitly so paths with quotes still hash (PR #12).
        if [ "$ch" = "'" ]; then
            c=39
        else
            c=0
            printf -v c '%d' "'$ch" 2>/dev/null || true  # printf -v: no per-char subshell (gemini PR #12)
        fi
        h=$(( (h * 33 + ${c:-0}) & 0xffffffff ))
        i=$(( i + 1 ))
    done
    printf '%x' "$h"
}

# 12-hex sha1 of the repo's absolute path. The path is hashed, never surfaced.
# Cached per-process: the Stop hook calls this several times per invocation (gemini PR #12).
_MARKER_REPO_HASH_CACHE=""
marker_repo_hash() {
    [ -n "$_MARKER_REPO_HASH_CACHE" ] && { printf '%s' "$_MARKER_REPO_HASH_CACHE"; return 0; }
    local root="" h=""
    root="$(git rev-parse --show-toplevel 2>/dev/null)" || root=""
    [ -n "$root" ] || root="$PWD"
    if command -v shasum >/dev/null 2>&1; then
        h="$(printf '%s' "$root" | shasum 2>/dev/null | cut -d' ' -f1)"
    elif command -v sha1sum >/dev/null 2>&1; then
        h="$(printf '%s' "$root" | sha1sum 2>/dev/null | cut -d' ' -f1)"
    elif command -v openssl >/dev/null 2>&1; then
        h="$(printf '%s' "$root" | openssl dgst -sha1 2>/dev/null | awk '{print $NF}')"
    elif command -v python3 >/dev/null 2>&1; then
        h="$(printf '%s' "$root" | python3 -c 'import hashlib,sys; sys.stdout.write(hashlib.sha1(sys.stdin.buffer.read()).hexdigest())' 2>/dev/null)"
    fi
    # Fail-open but NEVER empty: an empty hash would drop the per-repo discriminator
    # from the marker path/body. Fall back to cksum, then a path-derived slug.
    if [ -z "$h" ] && command -v cksum >/dev/null 2>&1; then
        h="$(printf '%s' "$root" | cksum 2>/dev/null | tr -cd '0-9')"
    fi
    # Final resort: a pure-bash hash of the path — PII-free (never path characters),
    # always available. Guarantees a non-empty, per-repo discriminator.
    [ -n "$h" ] || h="$(_marker_bash_hash "$root")"
    _MARKER_REPO_HASH_CACHE="${h:0:12}"
    printf '%s' "$_MARKER_REPO_HASH_CACHE"
}

# Hash an arbitrary string ($1) to a stable 12-char slug via the same cascade as marker_repo_hash (PII-free
# in the pure-bash fallback). Used for the Stop-gate's SESSION component (COREDEV-2503 F5) so a broken
# commit's block-once budget is per-(session, commit), not global-per-commit.
marker_hash_str() {
    local s="$1" h=""
    if command -v shasum >/dev/null 2>&1; then
        h="$(printf '%s' "$s" | shasum 2>/dev/null | cut -d' ' -f1)"
    elif command -v sha1sum >/dev/null 2>&1; then
        h="$(printf '%s' "$s" | sha1sum 2>/dev/null | cut -d' ' -f1)"
    elif command -v openssl >/dev/null 2>&1; then
        h="$(printf '%s' "$s" | openssl dgst -sha1 2>/dev/null | awk '{print $NF}')"
    elif command -v python3 >/dev/null 2>&1; then
        h="$(printf '%s' "$s" | python3 -c 'import hashlib,sys; sys.stdout.write(hashlib.sha1(sys.stdin.buffer.read()).hexdigest())' 2>/dev/null)"
    fi
    if [ -z "$h" ] && command -v cksum >/dev/null 2>&1; then
        h="$(printf '%s' "$s" | cksum 2>/dev/null | tr -cd '0-9')"
    fi
    [ -n "$h" ] || h="$(_marker_bash_hash "$s")"
    printf '%s' "${h:0:12}"
}

# Absolute path of a marker file. $1 = kind (lint|build).
marker_path() {
    printf '%s/quality-marker-%s-%s.json' "$(marker_dir)" "$1" "$(marker_repo_hash)"
}

# Write a marker atomically. $1 = kind (lint|build), $2 = status (pass|fail).
# status/kind are controlled tokens (no escaping needed). Fail-open on any error.
marker_write() {
    unleashed_base_ok || return 0        # D' (COREDEV-2617): unresolved base persists nothing.
    local kind="$1" _mw_status="$2" dir="" _mw_path="" tmp="" commit="" ts="" hash=""
    dir="$(marker_dir)"
    mkdir -p "$dir" 2>/dev/null || return 0
    _mw_path="$(marker_path "$kind")"
    tmp="${_mw_path}.tmp.$$"
    commit="$(git rev-parse --short HEAD 2>/dev/null)" || commit=""
    [ -n "$commit" ] || commit="unknown"
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    hash="$(marker_repo_hash)"
    # COREDEV-2617 §4.2a: every persisted record carries `base_resolution` naming the resolution that
    # ACTUALLY ran (`host-env` from the variable, `pointer` from the store) — plan row 20. Without it
    # a record cannot say which world wrote it, which is the provenance this ticket exists to give.
    printf '{"status":"%s","kind":"%s","ts":"%s","commit":"%s","repo_hash":"%s","base_resolution":"%s"}\n' \
        "$_mw_status" "$kind" "$ts" "$commit" "$hash" "${_UNLEASHED_BASE_SOURCE:-unresolved}" 2>/dev/null > "$tmp" || { rm -f "$tmp" 2>/dev/null; return 0; }
    mv "$tmp" "$_mw_path" 2>/dev/null || { rm -f "$tmp" 2>/dev/null; return 0; }
    # On a pass, clear the Stop-gate's last-blocked sentinel so a later regression on
    # the same commit can block again (gemini PR #12) — but ONLY when no marker kind is
    # still failing, so a build pass can't unblock a still-failing lint marker (codex PR #12).
    if [ "$_mw_status" = "pass" ]; then
        local _k _any_fail=0
        for _k in lint build; do
            # Only a fail marker for THIS commit keeps the sentinel; a stale fail from
            # an older commit shouldn't (gemini PR #12).
            if [ "$(marker_status "$_k")" = "fail" ] && [ "$(marker_commit "$_k")" = "$commit" ]; then
                _any_fail=1
            fi
        done
        if [ "$_any_fail" = 0 ]; then
            # F5 (COREDEV-2503): clear ALL repo-matching session sentinels — this function has NO session
            # payload, so it cannot target one session's file. Glob-clears every `…-<session>` sentinel plus
            # the legacy un-suffixed name. Without this, a session-suffixed sentinel would survive a pass and
            # a later same-session regression would wrongly pass.
            # zsh aborts a command whose glob matches nothing (`nomatch`) — measured: `no matches found`
            # and the rm never ran; a local option scoped to this function, exactly as the reader does.
            [ -n "${ZSH_VERSION:-}" ] && setopt local_options no_nomatch
            rm -f "$dir/stop-last-blocked-${hash}" "$dir/stop-last-blocked-${hash}"-* 2>/dev/null || true
        fi
    fi
}

# Read one string field from a marker file. $1 = kind, $2 = field. Empty if absent.
marker_field() {
    local kind="$1" field="$2" _mf_path="" line=""
    _mf_path="$(marker_path "$kind")"
    [ -f "$_mf_path" ] || return 0
    # Fast path: the marker is a known single-line JSON — parse with bash's built-in
    # regex to avoid spawning jq/python3 on every call (gemini PR #12, perf).
    # Anchor the key to a JSON delimiter ({ or ,) so searching "status" can't match
    # a future field like "custom_status" (gemini PR #12).
    if read -r line 2>/dev/null < "$_mf_path" && [[ "$line" =~ [{,][[:space:]]*\"$field\":\"([^\"]+)\" ]]; then
        # bash fills BASH_REMATCH; zsh fills `match` — under zsh BASH_REMATCH[1] was silently EMPTY, so
        # every marker field read as absent from a zsh consumer (measured, PR #67 pass 7).
        if [ -n "${ZSH_VERSION:-}" ]; then
            # shellcheck disable=SC2154  # `match` is zsh's capture array
            printf '%s' "${match[1]}"
        else
            printf '%s' "${BASH_REMATCH[1]}"
        fi
        return 0
    fi
    if command -v jq >/dev/null 2>&1; then
        jq -r --arg f "$field" '.[$f] // empty' "$_mf_path" 2>/dev/null
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,sys
try:
    d=json.load(open(sys.argv[1]))
    v=d.get(sys.argv[2],"")
    sys.stdout.write("" if v is None else str(v))
except Exception:
    pass' "$_mf_path" "$field" 2>/dev/null
    else
        grep -o "\"$field\":\"[^\"]*\"" "$_mf_path" 2>/dev/null | head -1 | sed 's/.*:"//; s/"$//'
    fi
}

marker_status() { marker_field "$1" status; }
marker_commit() { marker_field "$1" commit; }

# Marker file mtime in epoch seconds — the freshness source of truth. 0 on error.
marker_mtime() {
    local _mm_path="" m=""
    _mm_path="$(marker_path "$1")"
    [ -f "$_mm_path" ] || { printf '0'; return 0; }
    # FEATURE-DETECT, do not branch on `uname` (COREDEV-2600 item 3). The old
    # `uname == Darwin` form assumed only Darwin has BSD `stat`, so on FreeBSD it took the GNU
    # branch, `stat -c %Y` failed, and this returned the `0` sentinel. Reproduced: with `uname`
    # reporting FreeBSD the uname shape yields EMPTY while the form below yields the real mtime.
    # A `0` here is not benign — `stop-quality-marker-gate.sh:77-81` computes AGE=999999 from it
    # and SKIPS THE GATE ENTIRELY, so a platform quirk silently disabled a quality gate.
    # Same shape as `context.sh::_context_file_mtime`; the `${m:-0}` sentinel is marker.sh's own
    # contract and is preserved (context.sh returns "" instead — that difference is deliberate).
    m="$(stat -f %m "$_mm_path" 2>/dev/null)" || m=""
    [ -n "$m" ] || m="$(stat -c %Y "$_mm_path" 2>/dev/null)" || m=""
    printf '%s' "${m:-0}"
}
