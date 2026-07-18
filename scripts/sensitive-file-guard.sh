#!/usr/bin/env bash
# PreToolUse sensitive-file guard (Item 3, COREDEV-2324).
#
# On Edit/Write/MultiEdit (and Bash commands that WRITE to a target), checks whether
# the target's BASENAME matches a CLAUDE.md "Ask Before Modifying" / Security-table
# asset and, if so, asks the user to confirm. Basename matching sidesteps the space
# in "Unleashed Mail/Sources/".
#
# It NEVER emits permissionDecision:"allow" (that bypasses the prompt and would
# auto-approve every unmatched tool call) and never "deny" — the user is always in
# the loop. No-match / warn-mode / kill-switch-off emit no decision.
#
# Kill switch:  UNLEASHED_SENSITIVE_GUARD=off            -> emit nothing, exit 0
# Mode:         UNLEASHED_SENSITIVE_GUARD_MODE=warn|ask|off  -> default ask (permission prompt;
#               COREDEV-2489/P1c-12). In non-interactive / dontAsk / -p contexts an "ask" DENIES
#               the operation that would prompt — that is the intended fail-safe for sensitive files.
set -uo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
. "$_DIR/lib/hook-io.sh"

# True if a basename matches the sensitive signature set. Excludes tests and docs.
is_sensitive_basename() {
    local b="$1"
    case "$b" in
        *Tests.swift|*Test.swift) return 1 ;;
        *.md) return 1 ;;
    esac
    case "$b" in
        Info.plist|project.pbxproj) return 0 ;;
        *.entitlements|*.mobileprovision|*.xcodeproj) return 0 ;;
    esac
    # .swift stem allowlist — explicit high-signal stems only (no broad *auth* that
    # would hit Author/Authorization).
    case "$b" in
        Keychain*.swift|*Keychain*.swift) return 0 ;;
        MSAL*.swift|OAuth*.swift|*TokenStore*.swift|*AuthService*.swift) return 0 ;;
        DatabaseService*.swift|*Migration*.swift|*Repository*.swift|*SQLCipher*.swift) return 0 ;;
        *WebView*.swift|*EmailWeb*.swift|HTMLSanitiz*.swift) return 0 ;;
    esac
    return 1
}

# A short human category for the confirmation reason (no path, no contents).
sensitive_category() {
    local b="$1"
    case "$b" in
        Info.plist) printf 'the app Info.plist' ;;
        project.pbxproj|*.xcodeproj) printf 'Xcode project structure' ;;
        *.entitlements|*.mobileprovision) printf 'app entitlements/provisioning' ;;
        Keychain*|*Keychain*|MSAL*|OAuth*|*TokenStore*|*AuthService*) printf 'auth / token / Keychain handling' ;;
        DatabaseService*|*Migration*|*Repository*|*SQLCipher*) printf 'database / migration code' ;;
        *WebView*|*EmailWeb*|HTMLSanitiz*) printf 'WebView / HTML-sanitization code' ;;
        *) printf 'a protected asset' ;;
    esac
}

# COREDEV-2503 F4: the guard's Bash write-target extraction was an O(n^2) per-char segmenter plus
# quote-BLIND greps that both over-asked on a quoted operator (`echo '> Keychain.swift'`) and bypassed on a
# mid-word quote (`rm Key"chain".swift`). It is replaced by ONE structured, quote/escape/operator-aware
# linear lexer in `lib/bash-write-scan.py`, which prints the (de-quoted) write-target words; this function
# just applies the sensitive-basename policy. Best-effort by design (arbitrary shell can evade any textual
# heuristic — the robust guard is the Edit/Write file_path path).
#
# Return: prints the first sensitive write-target basename (empty if none); exit status 2 means the lexer
# could not parse the command -> the caller FAILS CLOSED (deny). If python3 is unavailable the best-effort
# Bash heuristic is skipped (empty, status 0) — never a blanket deny of every command.
guard_bash_write_target() {
    local cmd="$1" out="" t="" bn=""
    command -v python3 >/dev/null 2>&1 || return 0
    out="$(printf '%s' "$cmd" | python3 "$_DIR/lib/bash-write-scan.py")" || return 2
    while IFS= read -r t; do
        [ -n "$t" ] || continue
        bn="${t##*/}"
        if is_sensitive_basename "$bn"; then
            printf '%s' "$bn"
            return 0
        fi
    done <<< "$out"
    return 0
}

[ "${UNLEASHED_SENSITIVE_GUARD:-on}" = "off" ] && exit 0
MODE="${UNLEASHED_SENSITIVE_GUARD_MODE:-ask}"
[ "$MODE" = "off" ] && exit 0   # `_MODE=off` also disables (parity with the README kill-switch cell)

hook_io_read
TOOL="$(hook_tool_name)"

TARGET=""
case "$TOOL" in
    Edit|Write|MultiEdit)
        FP="$(hook_file_path)"
        [ -n "$FP" ] && TARGET="${FP##*/}"
        ;;
    Bash)
        CMD="$(hook_command)"
        if [ -n "$CMD" ]; then
            # F4 DoS backstop: a command too large to parse within the 10s hook timeout must NOT time out
            # (a killed hook fails open). Over 256 KiB (bytes, LC_ALL=C) -> ask unconditionally, fail-closed.
            NBYTES=$(LC_ALL=C printf '%s' "$CMD" | wc -c | tr -d ' ')
            if [ "${NBYTES:-0}" -gt 262144 ]; then
                if [ "$MODE" = ask ]; then
                    hook_emit_ask "This command is very large (${NBYTES} bytes); the sensitive-file guard cannot fully parse it in time. Proceed?"
                else
                    hook_emit_warn "Very large command (${NBYTES} bytes) — the sensitive-file guard could not fully scan it."
                fi
                exit 0
            fi
            TARGET="$(guard_bash_write_target "$CMD")"; GRC=$?
            # F4 exit-contract: a lexer PARSE FAILURE (not a mere no-match) is undecidable -> FAIL CLOSED
            # with an exit-2 deny + stderr reason (Claude Code ignores stdout JSON on exit 2, so an `ask`
            # cannot be exit-2; a hard deny can). python3-absent is handled inside as a best-effort skip.
            if [ "$GRC" -eq 2 ]; then
                printf 'sensitive-file guard: could not parse this Bash command; blocking (fail-closed).\n' >&2
                exit 2
            fi
        fi
        ;;
    *)
        exit 0
        ;;
esac

[ -n "$TARGET" ] || exit 0

if is_sensitive_basename "$TARGET"; then
    CATEGORY="$(sensitive_category "$TARGET")"
    case "$MODE" in
        ask)
            hook_emit_ask "Editing ${TARGET} touches ${CATEGORY}. CLAUDE.md requires confirmation before modifying it. Proceed?"
            ;;
        *)
            hook_emit_warn "${TARGET} is a sensitive asset (${CATEGORY}) — review before saving."
            ;;
    esac
fi
exit 0
