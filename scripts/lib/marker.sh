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
        _UNLEASHED_BASE_SOURCE='env'
        _UNLEASHED_POINTER_STATE=none
        # PUB-1: this file is one of the four PUBLISHING family files, and the publish is reachable
        # ONLY from this branch. The publish is a side effect of having resolved, never a condition.
        case "${HOME:-}" in /*)
            if [ "${_UNLEASHED_PUBLISH_OK:-1}" != 0 ] && _upb_state_load; then
                _unleashed_publish "${HOME:-}/.claude/unleashed-mail/bases" "$CLAUDE_PLUGIN_DATA"
                _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
                _UNLEASHED_BASE_OK=1
            fi ;;
        esac
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
    local kind="$1" status="$2" dir="" path="" tmp="" commit="" ts="" hash=""
    dir="$(marker_dir)"
    mkdir -p "$dir" 2>/dev/null || return 0
    path="$(marker_path "$kind")"
    tmp="${path}.tmp.$$"
    commit="$(git rev-parse --short HEAD 2>/dev/null)" || commit=""
    [ -n "$commit" ] || commit="unknown"
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    hash="$(marker_repo_hash)"
    printf '{"status":"%s","kind":"%s","ts":"%s","commit":"%s","repo_hash":"%s"}\n' \
        "$status" "$kind" "$ts" "$commit" "$hash" > "$tmp" 2>/dev/null || { rm -f "$tmp" 2>/dev/null; return 0; }
    mv "$tmp" "$path" 2>/dev/null || { rm -f "$tmp" 2>/dev/null; return 0; }
    # On a pass, clear the Stop-gate's last-blocked sentinel so a later regression on
    # the same commit can block again (gemini PR #12) — but ONLY when no marker kind is
    # still failing, so a build pass can't unblock a still-failing lint marker (codex PR #12).
    if [ "$status" = "pass" ]; then
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
            rm -f "$dir/stop-last-blocked-${hash}" "$dir/stop-last-blocked-${hash}"-* 2>/dev/null || true
        fi
    fi
}

# Read one string field from a marker file. $1 = kind, $2 = field. Empty if absent.
marker_field() {
    local kind="$1" field="$2" path="" line=""
    path="$(marker_path "$kind")"
    [ -f "$path" ] || return 0
    # Fast path: the marker is a known single-line JSON — parse with bash's built-in
    # regex to avoid spawning jq/python3 on every call (gemini PR #12, perf).
    # Anchor the key to a JSON delimiter ({ or ,) so searching "status" can't match
    # a future field like "custom_status" (gemini PR #12).
    if read -r line < "$path" 2>/dev/null && [[ "$line" =~ [{,][[:space:]]*\"$field\":\"([^\"]+)\" ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
        return 0
    fi
    if command -v jq >/dev/null 2>&1; then
        jq -r --arg f "$field" '.[$f] // empty' "$path" 2>/dev/null
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,sys
try:
    d=json.load(open(sys.argv[1]))
    v=d.get(sys.argv[2],"")
    sys.stdout.write("" if v is None else str(v))
except Exception:
    pass' "$path" "$field" 2>/dev/null
    else
        grep -o "\"$field\":\"[^\"]*\"" "$path" 2>/dev/null | head -1 | sed 's/.*:"//; s/"$//'
    fi
}

marker_status() { marker_field "$1" status; }
marker_commit() { marker_field "$1" commit; }

# Marker file mtime in epoch seconds — the freshness source of truth. 0 on error.
marker_mtime() {
    local path="" m=""
    path="$(marker_path "$1")"
    [ -f "$path" ] || { printf '0'; return 0; }
    # FEATURE-DETECT, do not branch on `uname` (COREDEV-2600 item 3). The old
    # `uname == Darwin` form assumed only Darwin has BSD `stat`, so on FreeBSD it took the GNU
    # branch, `stat -c %Y` failed, and this returned the `0` sentinel. Reproduced: with `uname`
    # reporting FreeBSD the uname shape yields EMPTY while the form below yields the real mtime.
    # A `0` here is not benign — `stop-quality-marker-gate.sh:77-81` computes AGE=999999 from it
    # and SKIPS THE GATE ENTIRELY, so a platform quirk silently disabled a quality gate.
    # Same shape as `context.sh::_context_file_mtime`; the `${m:-0}` sentinel is marker.sh's own
    # contract and is preserved (context.sh returns "" instead — that difference is deliberate).
    m="$(stat -f %m "$path" 2>/dev/null)" || m=""
    [ -n "$m" ] || m="$(stat -c %Y "$path" 2>/dev/null)" || m=""
    printf '%s' "${m:-0}"
}
