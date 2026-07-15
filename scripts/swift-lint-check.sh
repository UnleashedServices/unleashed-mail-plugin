#!/bin/bash
# PostToolUse hook: validate Swift files after Write/Edit operations.
#
# PostToolUse runs AFTER the write and cannot prevent it, so findings are fed back to the
# model via the documented JSON contract (COREDEV-2486, audit hooks-scripts.2/.3):
#   - blocking violations -> {"decision":"block","reason":...}  (surfaces the reason to Claude)
#   - advisories          -> hookSpecificOutput.additionalContext (delivered next to the result)
# Plain stdout is NOT shown to the model on PostToolUse, so every finding travels as JSON and
# the script exits 0 (JSON output is only processed on exit 0). A per-kind lint marker is still
# written for the Stop-gate (scripts/stop-quality-marker-gate.sh) on any blocking violation.
#
# COREDEV-2324: input read migrated to the shared hook-io helper (stdin-JSON first,
# CLAUDE_TOOL_ARG_* fallback) and a per-kind lint marker is written for the Stop-gate.

# Kill switch (COREDEV-2494) — this was the ONE hook without one, despite emitting `decision:block`
# and arming the Stop gate. Every other hook here honours a `UNLEASHED_*` off switch; a blocking hook
# with no escape is exactly the thing a user needs to be able to turn off.
[ "${UNLEASHED_LINT_CHECK:-on}" = "off" ] && exit 0

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
[ -f "$_DIR/lib/hook-io.sh" ] && . "$_DIR/lib/hook-io.sh"
# shellcheck source=scripts/lib/marker.sh
[ -f "$_DIR/lib/marker.sh" ] && . "$_DIR/lib/marker.sh"

# Defensive fallbacks if the shared lib is unavailable (it ships alongside this hook).
# Degraded mode emits to stderr; JSON feedback requires hook-io.sh.
if ! command -v hook_emit_posttool_block >/dev/null 2>&1; then
    hook_emit_posttool_block() { printf '%s\n' "$1" >&2; }
fi
if ! command -v hook_emit_posttool_context >/dev/null 2>&1; then
    hook_emit_posttool_context() { printf '%s\n' "$1" >&2; }
fi

if command -v hook_io_read >/dev/null 2>&1; then
    hook_io_read
    FILE_PATH="$(hook_file_path)"
else
    FILE_PATH="${CLAUDE_TOOL_ARG_file_path:-${CLAUDE_TOOL_ARG_path:-}}"
fi

# Only process .swift files
if [[ "$FILE_PATH" != *.swift ]]; then
    exit 0
fi

# Accumulate blocking violations and non-blocking advisories separately, then emit ONE JSON
# object at the end (a hook can only emit a single JSON result).
BLOCK=""
ADVISORY=""
add_block()    { if [ -n "$BLOCK" ]; then BLOCK="$BLOCK
$1"; else BLOCK="$1"; fi; }
add_advisory() { if [ -n "$ADVISORY" ]; then ADVISORY="$ADVISORY
$1"; else ADVISORY="$1"; fi; }

# --- 1. Syntax check (fast, catches parse errors) ---
if command -v swiftc &> /dev/null; then
    RESULT=$(swiftc -parse "$FILE_PATH" 2>&1)
    if [ $? -ne 0 ]; then
        add_block "❌ Swift syntax error in $FILE_PATH:
$(printf '%s' "$RESULT" | head -10)"
        # A syntax error is a real lint failure; record the marker and stop — further lint/grep
        # checks on an unparseable file are meaningless.
        command -v marker_write >/dev/null 2>&1 && marker_write lint fail
        hook_emit_posttool_block "$BLOCK"
        exit 0
    fi
fi

# --- 2. SwiftLint check (if available) ---
SWIFTLINT_RAN=0
if command -v swiftlint &> /dev/null; then
    SWIFTLINT_RAN=1
    # COREDEV-2486 (audit hooks-scripts.1): `--path` was deprecated in SwiftLint 0.48 and REMOVED
    # in 0.56 (current is 0.65). Use the positional form; capturing the exit code lets a future CLI
    # break surface as an advisory instead of silently disabling the stage.
    LINT_OUTPUT=$(swiftlint lint --quiet --force-exclude "$FILE_PATH" 2>&1)
    LINT_RC=$?

    # Count errors vs warnings. `grep -c PATTERN || true` guards pipefail on no-match.
    ERROR_COUNT=$(printf '%s' "$LINT_OUTPUT" | grep -c ": error:" 2>/dev/null || true)
    WARNING_COUNT=$(printf '%s' "$LINT_OUTPUT" | grep -c ": warning:" 2>/dev/null || true)
    ERROR_COUNT=${ERROR_COUNT:-0}
    WARNING_COUNT=${WARNING_COUNT:-0}

    if [ "$ERROR_COUNT" -gt 0 ]; then
        add_block "❌ SwiftLint errors in $FILE_PATH:
$(printf '%s' "$LINT_OUTPUT" | grep ": error:" | head -10)"
    elif [ "$WARNING_COUNT" -gt 0 ]; then
        add_advisory "⚠️  SwiftLint warnings in $FILE_PATH:
$(printf '%s' "$LINT_OUTPUT" | grep ": warning:" | head -5)"
    fi

    # Guard: a non-zero swiftlint exit with zero parsed findings means the CLI itself failed
    # (unknown flag, bad config, missing toolchain) — surface it instead of passing silently.
    if [ "$LINT_RC" -ne 0 ] && [ "$ERROR_COUNT" -eq 0 ] && [ "$WARNING_COUNT" -eq 0 ]; then
        add_advisory "⚠️  swiftlint exited $LINT_RC with no parsed findings — the lint stage may be misconfigured (check the SwiftLint CLI/version):
$(printf '%s' "$LINT_OUTPUT" | head -3)"
    fi
fi

# --- 3 & 4. try! / as! greps: FALLBACK ONLY, when SwiftLint did not run (COREDEV-2494).
#
# These greps cannot see `// swiftlint:disable:next force_try` — they filter only lines that are
# THEMSELVES comments, so a directive on line N never protects line N+1. Measured against the consumer
# app: 120 of 273 production `try!` sites carry that exact waiver, so the greps produced 120 FALSE
# POSITIVES and told the model "❌ Found 'try!' in production code" for code the project's own CLAUDE.md
# REQUIRES to be waived (the regex-migration epic — piecemeal NSRegularExpression conversion risks
# Sendable regressions). The hook then poisons a `lint=fail` marker that blocks Stop.
#
# When swiftlint ran (stage 2) it is authoritative: it honours the directives, and BOTH rules are
# default-error rules (`force_try` / `force_cast`), so a genuinely UNWAIVED site still surfaces as
# `: error:` and stage 2 already blocks on it. Detection is preserved; the false-positive class is not.
if [ "$SWIFTLINT_RAN" -eq 0 ] && [[ "$FILE_PATH" != *Tests/* ]] && [[ "$FILE_PATH" != *Test.swift ]]; then
    # No toolchain: keep a coarse net, but honour an explicit waiver on the preceding line so the
    # fallback cannot demand a policy-violating edit either. -A1 pairs directive->site.
    TRY_BANG=$(grep -nE 'try!' "$FILE_PATH" 2>/dev/null | grep -vE '^[0-9]+:[[:space:]]*//' \
        | while IFS= read -r hit; do
            n="${hit%%:*}"
            prev=$(sed -n "$((n - 1))p" "$FILE_PATH" 2>/dev/null)
            # Prefix-strip, NOT `case`: a `)` in a case pattern collides with the closing `)` of the
            # enclosing `$( )` (and bash 3.2 — what macOS ships — cannot parse case-in-while-in-$() at
            # all). Same fix as COREDEV-2492. "${prev#*swiftlint:disable}" != "$prev" == "contains it".
            if [ "${prev#*swiftlint:disable}" = "$prev" ]; then printf '%s\n' "$hit"; fi
        done)
    if [ -n "$TRY_BANG" ]; then
        add_block "❌ Found 'try!' in production code (swiftlint unavailable — grep fallback) — $FILE_PATH:
$TRY_BANG"
    fi

    FORCE_CAST=$(grep -nE 'as!' "$FILE_PATH" 2>/dev/null | grep -vE '^[0-9]+:[[:space:]]*//' \
        | while IFS= read -r hit; do
            n="${hit%%:*}"
            prev=$(sed -n "$((n - 1))p" "$FILE_PATH" 2>/dev/null)
            # Prefix-strip, NOT `case`: a `)` in a case pattern collides with the closing `)` of the
            # enclosing `$( )` (and bash 3.2 — what macOS ships — cannot parse case-in-while-in-$() at
            # all). Same fix as COREDEV-2492. "${prev#*swiftlint:disable}" != "$prev" == "contains it".
            if [ "${prev#*swiftlint:disable}" = "$prev" ]; then printf '%s\n' "$hit"; fi
        done)
    if [ -n "$FORCE_CAST" ]; then
        add_block "❌ Found 'as!' (force cast) in production code (swiftlint unavailable — grep fallback) — $FILE_PATH:
$FORCE_CAST"
    fi
fi

# --- 5. Token/secret logging check (BLOCKS) ---
TOKEN_LOG=$(grep -nE 'print.*[Tt]oken|NSLog.*[Tt]oken|Logger.*accessToken|Logger.*refreshToken' "$FILE_PATH" 2>/dev/null | grep -vE '^[0-9]+:[[:space:]]*//')
if [ -n "$TOKEN_LOG" ]; then
    add_block "❌ Potential token value in log statement — $FILE_PATH:
$TOKEN_LOG"
fi

# --- 6. Test file existence check (WARNING only, does not block) ---
# UnleashedMail layout: production code lives under "Unleashed Mail/Sources/",
# tests under "Unleashed MailTests/" (note the space). Swift package layout would be
# "Sources/" -> "Tests/"; we accept both forms so the hook is portable to other repos.
case "$FILE_PATH" in
    *"Unleashed Mail/Sources/"*.swift)
        TEST_PATH=$(echo "$FILE_PATH" | sed 's|Unleashed Mail/Sources/|Unleashed MailTests/|' | sed 's|\.swift$|Tests.swift|')
        if [ ! -f "$TEST_PATH" ]; then
            add_advisory "⚠️  No test file found for $(basename "$FILE_PATH") (expected: $TEST_PATH)"
        fi
        ;;
    *Sources/*.swift)
        case "$FILE_PATH" in
            *Tests/*) ;;  # already a test file
            *)
                TEST_PATH=$(echo "$FILE_PATH" | sed 's|Sources/|Tests/|' | sed 's|\.swift$|Tests.swift|')
                if [ ! -f "$TEST_PATH" ]; then
                    add_advisory "⚠️  No test file found for $(basename "$FILE_PATH") (expected: $TEST_PATH)"
                fi
                ;;
        esac
        ;;
esac

# --- Emit findings via the PostToolUse JSON contract (COREDEV-2486) ---
# COREDEV-2324: this per-FILE hook must NOT write lint=pass (one clean file can't prove the
# repo lints; overwriting a global fail would let the Stop-gate be bypassed). Write only
# lint=fail — fail-closed. The pass/clear comes from the full-project pre-commit lint.
if [ -n "$BLOCK" ]; then
    command -v marker_write >/dev/null 2>&1 && marker_write lint fail
    [ -n "$ADVISORY" ] && BLOCK="$BLOCK
$ADVISORY"
    hook_emit_posttool_block "$BLOCK"
    exit 0
fi

if [ -n "$ADVISORY" ]; then
    hook_emit_posttool_context "$ADVISORY"
fi
exit 0
