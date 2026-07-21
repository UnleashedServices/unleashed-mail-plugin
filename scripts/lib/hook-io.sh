#!/usr/bin/env bash
# shellcheck shell=bash
# Shared hook I/O for unleashed-mail Claude Code hooks (Phase 1, COREDEV-2324).
#
# This file is SOURCED, never executed. It lets every hook read tool input the
# same way and emit the exact JSON shapes Claude Code expects.
#
# Input contract: the current Claude Code hooks reference delivers command-hook
# input as STDIN JSON; older builds populated CLAUDE_TOOL_ARG_* env vars. We read
# stdin JSON first and fall back to the env vars, so a hook is correct on both.
#
# Output contract (verified against https://code.claude.com/docs/en/hooks):
#   PreToolUse ask  -> {"hookSpecificOutput":{"hookEventName":"PreToolUse",
#                        "permissionDecision":"ask","permissionDecisionReason":"..."}}
#   Stop block      -> {"decision":"block","reason":"..."}
#   NEVER emit permissionDecision:"allow" on a no-match — "allow" BYPASSES the
#   permission prompt (auto-approves). No-match/warn/off emit no decision.
#
# Every probe is `2>/dev/null` and fail-open: a hook must never spew tool
# diagnostics and must never block/ask spuriously.

HOOK_STDIN="${HOOK_STDIN:-}"
_HOOK_IO_READ_DONE="${_HOOK_IO_READ_DONE:-}"

# Slurp stdin once into HOOK_STDIN. TTY-guarded so a manual run never hangs on a
# terminal stdin even when GNU `timeout` is absent (macOS default).
hook_io_read() {
    [ -n "$_HOOK_IO_READ_DONE" ] && return 0
    _HOOK_IO_READ_DONE=1
    if [ -t 0 ]; then
        HOOK_STDIN='{}'
    else
        # Pure-bash, timeout-bounded slurp of all stdin (NUL delimiter reads through
        # newlines). Avoids a GNU `timeout` dependency and any hang on an open pipe
        # (gemini PR #12). `read` returns non-zero at EOF but still populates the var.
        IFS= read -r -t 3 -d '' HOOK_STDIN 2>/dev/null || true
    fi
    [ -n "$HOOK_STDIN" ] || HOOK_STDIN='{}'
}

# python3 JSON accessor fallback. $1 = mode (tool_name|file_path|command|bool),
# $2 = (bool only) the top-level key. Prints the value or nothing.
_hook_py_get() {
    command -v python3 >/dev/null 2>&1 || return 1
    printf '%s' "$HOOK_STDIN" | python3 -c '
import json, sys
mode = sys.argv[1]
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(d, dict):
    sys.exit(0)
ti = d.get("tool_input") or {}
if not isinstance(ti, dict):
    ti = {}
if mode == "tool_name":
    v = d.get("tool_name")
elif mode == "file_path":
    v = ti.get("file_path") or ti.get("path")
elif mode == "command":
    v = ti.get("command")
elif mode == "bool":
    raw = d.get(sys.argv[2])
    v = "true" if raw is True else ("false" if raw is False else "")
else:
    v = None
if v:
    sys.stdout.write(str(v))
' "$@" 2>/dev/null
}

# Last-resort grep/sed JSON extractor when neither jq nor python3 exists.
# Best-effort: a "command" value containing escaped quotes truncates at the first
# \" — acceptable, because a missed write target only fails OPEN (no spurious ask).
# $1 = mode (tool_name|file_path|command|bool), $2 = (bool only) the key.
_hook_grep_get() {
    local mode="$1" key="${2:-}" v=""
    case "$mode" in
        tool_name)
            v="$(printf '%s' "$HOOK_STDIN" | grep -oE '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' 2>/dev/null | head -1 | sed -E 's/.*:[[:space:]]*"//; s/"$//')"
            ;;
        file_path)
            v="$(printf '%s' "$HOOK_STDIN" | grep -oE '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' 2>/dev/null | head -1 | sed -E 's/.*:[[:space:]]*"//; s/"$//')"
            [ -n "$v" ] || v="$(printf '%s' "$HOOK_STDIN" | grep -oE '"path"[[:space:]]*:[[:space:]]*"[^"]*"' 2>/dev/null | head -1 | sed -E 's/.*:[[:space:]]*"//; s/"$//')"
            ;;
        command)
            v="$(printf '%s' "$HOOK_STDIN" | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]*"' 2>/dev/null | head -1 | sed -E 's/.*:[[:space:]]*"//; s/"$//')"
            ;;
        bool)
            v="$(printf '%s' "$HOOK_STDIN" | grep -oE "\"$key\"[[:space:]]*:[[:space:]]*(true|false)" 2>/dev/null | head -1 | grep -oE '(true|false)' | head -1)"
            ;;
    esac
    printf '%s' "$v"
}

# Tool name from stdin JSON, else inferred from the env-var fallback.
hook_tool_name() {
    local v=""
    if command -v jq >/dev/null 2>&1; then
        v="$(printf '%s' "$HOOK_STDIN" | jq -r '.tool_name // empty' 2>/dev/null)"
    fi
    [ -n "$v" ] || v="$(_hook_py_get tool_name)"
    [ -n "$v" ] || v="$(_hook_grep_get tool_name)"
    if [ -z "$v" ]; then
        if [ -n "${CLAUDE_TOOL_ARG_command:-}" ]; then
            v="Bash"
        elif [ -n "${CLAUDE_TOOL_ARG_file_path:-}${CLAUDE_TOOL_ARG_path:-}" ]; then
            v="Edit"
        fi
    fi
    printf '%s' "$v"
}

# tool_input.file_path (// .tool_input.path), env fallback.
hook_file_path() {
    local v=""
    if command -v jq >/dev/null 2>&1; then
        v="$(printf '%s' "$HOOK_STDIN" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)"
    fi
    [ -n "$v" ] || v="$(_hook_py_get file_path)"
    [ -n "$v" ] || v="$(_hook_grep_get file_path)"
    [ -n "$v" ] || v="${CLAUDE_TOOL_ARG_file_path:-${CLAUDE_TOOL_ARG_path:-}}"
    printf '%s' "$v"
}

# tool_input.command, env fallback.
hook_command() {
    local v=""
    if command -v jq >/dev/null 2>&1; then
        v="$(printf '%s' "$HOOK_STDIN" | jq -r '.tool_input.command // empty' 2>/dev/null)"
    fi
    [ -n "$v" ] || v="$(_hook_py_get command)"
    [ -n "$v" ] || v="$(_hook_grep_get command)"
    [ -n "$v" ] || v="${CLAUDE_TOOL_ARG_command:-}"
    printf '%s' "$v"
}

# A top-level boolean field as the literal string "true"/"false"/"". $1 = key.
hook_bool() {
    local key="$1" v=""
    if command -v jq >/dev/null 2>&1; then
        v="$(printf '%s' "$HOOK_STDIN" | jq -r --arg k "$key" '.[$k] | if . == true then "true" elif . == false then "false" else empty end' 2>/dev/null)"
    fi
    [ -n "$v" ] || v="$(_hook_py_get bool "$key")"
    [ -n "$v" ] || v="$(_hook_grep_get bool "$key")"
    printf '%s' "$v"
}

# Emit a value as a safe, fully-escaped JSON string (quotes included).
json_escape() {
    local s="$1" clean=""
    if command -v python3 >/dev/null 2>&1; then
        printf '%s' "$s" | python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.stdin.read()))' 2>/dev/null && return 0
    fi
    if command -v jq >/dev/null 2>&1; then
        printf '%s' "$s" | jq -Rs . 2>/dev/null && return 0
    fi
    # Last-resort manual escape: drop the only characters that would break JSON,
    # keep printable bytes, wrap in quotes. Reasons are fixed template + basename.
    clean="$(printf '%s' "$s" | tr -d '\\"' | tr -cd '[:print:]')"
    printf '"%s"' "$clean"
}

# PreToolUse: ask the user to confirm (the only deciding output this guard emits).
hook_emit_ask() {
    local reason
    reason="$(json_escape "$1")"
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":%s}}\n' "$reason"
}

# PreToolUse warn mode: a non-deciding advisory. permissionDecision is OMITTED so
# the standard permission prompt still applies. Safe even if CC ignores it.
hook_emit_warn() {
    local msg
    msg="$(json_escape "$1")"
    printf '{"systemMessage":%s}\n' "$msg"
}

# Stop: block the turn (root-level decision, NOT nested in hookSpecificOutput).
hook_emit_block() {
    local reason
    reason="$(json_escape "$1")"
    printf '{"decision":"block","reason":%s}\n' "$reason"
}

# --- Phase 2 (COREDEV-2325) additions ---------------------------------------

# A TOP-LEVEL string field, read STRUCTURALLY via jq -> python3 ONLY (never grep).
# A regex `"key":"…"` scan would also match a NESTED `tool_input.<key>` (e.g. a
# `tool_input.reason`), which would violate the "never read tool_input" invariant —
# so for PII-sensitive top-level reads (reason/source/agent_type/error_type/…) we
# only use a real JSON parser and return empty (fail-open) when neither exists. $1 = key.
hook_str() {
    local key="$1" v=""
    if command -v jq >/dev/null 2>&1; then
        v="$(printf '%s' "$HOOK_STDIN" | jq -r --arg k "$key" '.[$k] | select(type == "string")' 2>/dev/null)"
    fi
    if [ -z "$v" ] && command -v python3 >/dev/null 2>&1; then
        v="$(printf '%s' "$HOOK_STDIN" | _HOOK_STR_KEY="$key" python3 -c '
import json, os, sys
try:
    d = json.load(sys.stdin.buffer)  # bytes in -> json auto-detects UTF-8; locale-independent
except Exception:
    sys.exit(0)
if isinstance(d, dict):
    v = d.get(os.environ.get("_HOOK_STR_KEY", ""))
    if isinstance(v, str):
        sys.stdout.buffer.write(v.encode("utf-8"))  # bytes out: avoid ASCII-locale encode error
' 2>/dev/null)"
    fi
    printf '%s' "$v"
}

# Redact PII from a free-text string before it is persisted to a log/snapshot/capture.
# Collapses: emails; home-dir usernames (/Users/<n>, /home/<n>, ~<n>) so a
# `/Users/<name>/…` path or `-archivePath` cannot leak the user; full dot-segmented
# JWT/Bearer tokens (not just the first segment); sk-/pk_ secrets; api keys. Then
# folds newlines/tabs to spaces. BSD/GNU-portable `sed -E` (POSIX classes, no `\s`),
# `LC_ALL=C`. The Python `redact_pii` in mcp/review-synthesizer/capture.py mirrors
# these patterns, with TWO deliberate Python-only exemptions (MIN-13): its _EMAIL skips `@Nx` retina-asset
# filenames and its _TILDE skips Swift `~Copyable`/`~Escapable`. Those use regex lookahead, which POSIX ERE
# cannot express — and this shell redactor processes hook advisory text that never carries a finding's
# `file`/`evidence` literal, so it needs neither exemption. Every other pattern here is byte-identical.
# The caller caps length and json_escapes. $1 = string.
hook_redact_pii() {
    printf '%s' "$1" | LC_ALL=C sed -E \
        -e 's#[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}#[redacted-email]#g' \
        -e 's#/Users/[^/[:space:]"]+#/Users/[redacted]#g' \
        -e 's#/home/[^/[:space:]"]+#/home/[redacted]#g' \
        -e 's#~[A-Za-z0-9._-]+#~[redacted]#g' \
        -e 's#[Bb][Ee][Aa][Rr][Ee][Rr][[:space:]]+[A-Za-z0-9._-]{20,}#[redacted-token]#g' \
        -e 's#eyJ[A-Za-z0-9._-]{10,}#[redacted-jwt]#g' \
        -e 's#(sk-|pk_)[A-Za-z0-9._-]{8,}#[redacted-secret]#g' \
        -e 's#[Aa][Pp][Ii][[:space:]_-]?[Kk][Ee][Yy][[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]+#[redacted-key]#g' \
        2>/dev/null | tr '\n\r\t' '   '
}

# SessionStart: inject a one-line, non-blocking resume hint as additionalContext.
# SessionStart cannot block; this is the documented post-compaction context point. $1 = message.
hook_emit_session_context() {
    local ctx
    ctx="$(json_escape "$1")"
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":%s}}\n' "$ctx"
}

# PostToolUse: feed advisory context to Claude next to the tool result (non-blocking).
# COREDEV-2486 (audit hooks-scripts.3): PostToolUse plain stdout is NEVER shown to the
# model (only UserPromptSubmit/UserPromptExpansion/SessionStart stdout is), so advisories
# must travel via additionalContext. Delivered "next to the tool result"; JSON output is
# only processed on exit 0, so callers emit this then `exit 0`. $1 = message.
hook_emit_posttool_context() {
    local ctx
    ctx="$(json_escape "$1")"
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":%s}}\n' "$ctx"
}

# PostToolUse: feed a blocking finding back to Claude. PostToolUse cannot undo a write,
# but a top-level {"decision":"block","reason":...} surfaces the reason to the model
# (docs-supported for PostToolUse). JSON output requires exit 0. $1 = reason.
hook_emit_posttool_block() {
    local reason
    reason="$(json_escape "$1")"
    printf '{"decision":"block","reason":%s}\n' "$reason"
}
