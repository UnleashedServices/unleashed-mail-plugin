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

# Does this command SEGMENT mutate the filesystem? A precise per-verb parse (below) can only extract a
# target for the forms it knows (redirect / cp / mv / sed -i / tee). It missed deletion (`rm`), symlink
# clobber (`ln`), and interpreter one-liners (`python3 -c 'open("X","w")...'`, perl/ruby/node -e) —
# semantically-equivalent writes that slipped straight through (#44 independent review §6). This returns
# true for any of those, so the broad fail-closed scan below runs. Read-only commands (cat/grep/less)
# return false, so a sensitive file merely READ never prompts.
_seg_is_mutating() {
    local s="$1" v=""
    read -ra _mt <<<"$s"; v="${_mt[0]:-}"; v="${v##*/}"
    case "$v" in
        rm|unlink|shred|mv|rename|cp|install|dd|truncate|ln|tee|dded) return 0 ;;
    esac
    # An interpreter invoked with inline code (-c / -e) or a heredoc can write anything.
    case "$v" in
        python|python2|python3|perl|ruby|node|nodejs|osascript|bash|sh|zsh|env)
            printf '%s' "$s" | grep -qE '(^|[[:space:]])-(c|e)([[:space:]]|=)|<<' && return 0 ;;
    esac
    # Any redirection that writes/clobbers/appends, anywhere in the segment.
    printf '%s' "$s" | grep -qE '>>?|>\|' && return 0
    printf '%s' "$s" | grep -qE '(^|[[:space:]])sed[[:space:]]+-i' && return 0
    return 1
}

# Best-effort: print the basename of a sensitive WRITE target in a Bash command, else nothing. Reads
# (grep/cat) and a file used only as a SOURCE (`cp Keychain.swift /backup/`) print nothing. Phase-1
# heuristic; the robust guard is the Edit/Write file_path path — arbitrary shell can always evade text.
guard_bash_write_target() {
    local cmd="$1" cand="" seg="" line="" t="" bn="" verb="" tok="" last="" bt="" _bcheck=0
    local -a toks=()
    # Split on shell separators so a chained command (`cp a b && git diff`) is parsed
    # per-segment, not by a single trailing token (codex/gemini PR #12). Best-effort:
    # the Bash path is a warn-first speed-bump — the robust guard is the Edit/Write
    # file_path path; arbitrary shell can always evade a textual heuristic.
    while IFS= read -r seg; do
        [ -n "$seg" ] || continue
        # Redirection targets within the segment: >FILE / >>FILE (quoted or not).
        while IFS= read -r line; do
            line="$(printf '%s' "$line" | sed -E 's/^>>?[[:space:]]*//; s/^"//; s/"$//')"
            [ -n "$line" ] && cand="${cand}
${line}"
        done < <(printf '%s\n' "$seg" | grep -oE '>>?[[:space:]]*("[^"]+"|[^"[:space:]|&;]+)' 2>/dev/null)
        read -ra toks <<<"$seg"
        verb="${toks[0]:-}"
        case "$verb" in
            cp|install)
                # destination = last non-flag operand.
                last=""
                for tok in "${toks[@]}"; do
                    case "$tok" in -*) ;; *) last="$tok" ;; esac
                done
                [ -n "$last" ] && cand="${cand}
${last}"
                ;;
            mv|rename)
                # a rename can modify/remove the SOURCE too — check every non-flag operand.
                for tok in "${toks[@]:1}"; do
                    case "$tok" in -*) ;; *) cand="${cand}
${tok}" ;; esac
                done
                ;;
            sed)
                if printf '%s' "$seg" | grep -qE 'sed[[:space:]]+-i' 2>/dev/null; then
                    cand="${cand}
${toks[*]: -1}"
                fi
                ;;
            tee)
                cand="${cand}
$(printf '%s' "$seg" | sed -E 's/^[[:space:]]*tee[[:space:]]+(-a[[:space:]]+)?//; s/[[:space:]].*$//; s/^"//; s/"$//')"
                ;;
        esac
        # FAIL CLOSED for the mutating verbs the precise parse above CANNOT target: deletion
        # (`rm`/`unlink`/`shred`), symlink clobber (`ln`), and interpreter one-liners
        # (`python3 -c 'open("X","w")'`). For these, ANY sensitive basename named in the segment is
        # treated as the mutated file. Deliberately NOT run for cp/mv/install/sed/tee/redirects — those
        # already extracted their precise target(s) above, and a broad scan there would wrongly flag a
        # READ source (`cp KeychainManager.swift /backup/` reads it, does not modify it). Scoped to
        # mutation, so `cat X`/`grep foo X` never trip it (#44 review §6).
        case "$verb" in
            rm|unlink|shred|ln|python|python2|python3|perl|ruby|node|nodejs|osascript|bash|sh|zsh|env) _bcheck=1 ;;
            /*rm|/*python*|/*perl|/*ruby|/*node|/*unlink|/*shred|/*ln) _bcheck=1 ;;
            *) _bcheck=0 ;;
        esac
        if [ "$_bcheck" = 1 ] && _seg_is_mutating "$seg"; then
            while IFS= read -r bt; do
                [ -n "$bt" ] || continue
                cand="${cand}
${bt}"
            done < <(printf '%s\n' "$seg" | grep -oE '[A-Za-z0-9._-]+\.(swift|entitlements|plist|pbxproj|mobileprovision|xcodeproj)' 2>/dev/null)
        fi
    done < <(printf '%s\n' "$cmd" | sed -E 's/(\&\&|\|\||[;&|])/\n/g')
    # Evaluate candidates by basename (while-read avoids globbing on a `*` operand).
    while IFS= read -r t; do
        [ -n "$t" ] || continue
        t="${t#\"}"; t="${t%\"}"
        bn="${t##*/}"
        if is_sensitive_basename "$bn"; then
            printf '%s' "$bn"
            return 0
        fi
    done <<EOF
$cand
EOF
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
        [ -n "$CMD" ] && TARGET="$(guard_bash_write_target "$CMD")"
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
