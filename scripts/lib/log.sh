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

log_base() {
    # ${HOME:-} so a missing HOME under `set -u` never aborts a hook; if both are unset
    # the path becomes "/.claude/..." and the later mkdir simply fails open.
    printf '%s' "${CLAUDE_PLUGIN_DATA:-${HOME:-}/.claude/unleashed-mail}"
}

log_dir() {
    printf '%s/logs' "$(log_base)"
}

# Append one PRE-FORMED JSON line to logs/<name>, then cap the file by line count.
# $1 = log basename (e.g. error-log.jsonl), $2 = the JSON line (no trailing newline),
# $3 = max lines before rotation (default 500). On rotation the newest max/2 lines are
# kept (so we don't rotate on every subsequent write). Fail-open, stderr-clean.
log_append() {
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
