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

# Resolve a segment's EFFECTIVE command word: strip any directory (`/usr/bin/rm` -> `rm`) and unwrap a
# leading `VAR=val …` and/or `env …` prefix (`FOO=1 rm X`, `env python3 -c …`, `FOO=1 env -u BAR sh …`
# -> `rm` / `python3` / `sh`) so ONE verb list covers `/bin/rm`, `env python3`, `FOO=1 rm`, etc. — the
# earlier `/*rm|/*python*` path-glob list was fragile and incomplete (round 1); a bare `FOO=1 rm` was
# still mis-classified as verb `FOO=1`, and `env -u NAME rm` as verb `NAME` (round 2: codex + gemini).
_effective_verb() {
    local -a a=()
    read -ra a <<<"$1"
    local n=${#a[@]} i=0 tok v=""
    # Skip a leading run of `VAR=val` assignment prefixes (`FOO=1 BAR=2 cmd …`), with or without `env`.
    while [ "$i" -lt "$n" ]; do
        case "${a[$i]}" in
            -*) break ;;             # a flag => the command word already started
            *=*) i=$((i + 1)) ;;     # VAR=val assignment prefix — skip
            *) break ;;
        esac
    done
    v="${a[$i]:-}"; v="${v##*/}"
    # Unwrap `env [OPTION]... [NAME=VALUE]... COMMAND`: skip env, its flags, the ARG consumed by
    # -u/--unset/-C/--chdir/-S/--split-string (space-separated), and any VAR=val, to the command word.
    if [ "$v" = "env" ]; then
        i=$((i + 1))
        while [ "$i" -lt "$n" ]; do
            tok="${a[$i]}"
            case "$tok" in
                --) i=$((i + 1)); break ;;                               # explicit end-of-options
                -u|--unset|-C|--chdir|-S|--split-string) i=$((i + 2)) ;; # option + its argument
                -*) i=$((i + 1)) ;;                                      # other flag / =-joined form
                *=*) i=$((i + 1)) ;;                                     # VAR=val
                *) break ;;                                              # the command word
            esac
        done
        v="${a[$i]:-}"; v="${v##*/}"
    fi
    printf '%s' "$v"
}

# True if an interpreter SEGMENT carries inline code — a `-c`/`-e` cluster (`-c`, `-xc`, `perl -we`,
# `perl -pe's/…/'`, code adjacent as `-c"…"`) or a heredoc (`<<`). Inline code can write a file NAMED
# INSIDE it, so the broad fail-closed scan must run for it. A plain `python3 script.py` (no inline code)
# writes nothing we can textually see and must NOT trigger the scan; an interpreter whose only mutation
# is a redirect has its target captured precisely above, so scanning its read args would over-fire
# (round 2: codex). The old `-(c|e)([space]|=)` missed combined and quote-adjacent flags (round 1).
_seg_has_inline_code() {
    printf '%s' "$1" | grep -qE '(^|[[:space:]])-[[:alnum:]]*[ce]([^[:alnum:]]|$)|<<'
}

# Best-effort: print the basename of a sensitive WRITE target in a Bash command, else nothing. Reads
# (grep/cat) and a file used only as a SOURCE (`cp Keychain.swift /backup/`) print nothing. Phase-1
# heuristic; the robust guard is the Edit/Write file_path path — arbitrary shell can always evade text.
guard_bash_write_target() {
    local cmd="$1" cand="" seg="" line="" t="" bn="" base_verb="" tok="" last="" bt="" _bcheck=0
    local seen_cmd=0 skipnext=0
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
        # Effective command word (dir stripped, `env`/`VAR=val` unwrapped) so `/bin/cp`, `env mv`, etc.
        # reach the right parse arm — not just the bare-word forms.
        base_verb="$(_effective_verb "$seg")"
        case "$base_verb" in
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
                # tee writes to ALL its FILE operands. Collect each non-flag token AFTER the command word
                # (matched by basename, so `/usr/bin/tee` / `env tee` work) — the old sed anchored at a
                # literal leading `tee` recorded `/usr/bin/tee`/`env` for the prefixed forms (round 2: codex).
                seen_cmd=0
                for tok in "${toks[@]}"; do
                    if [ "$seen_cmd" = 0 ]; then
                        case "${tok##*/}" in tee) seen_cmd=1 ;; esac
                        continue
                    fi
                    case "$tok" in -*) ;; *) cand="${cand}
${tok}" ;; esac
                done
                ;;
            touch)
                # touch's targets are its non-flag operands, EXCLUDING the arg consumed by -r/--reference
                # (a READ reference file), -d/--date, and -t (a timestamp) — `touch -r SENSITIVE marker`
                # reads SENSITIVE, it does not modify it (round 2: codex). Skip the command word first.
                seen_cmd=0; skipnext=0
                for tok in "${toks[@]}"; do
                    if [ "$seen_cmd" = 0 ]; then
                        case "${tok##*/}" in touch) seen_cmd=1 ;; esac
                        continue
                    fi
                    if [ "$skipnext" = 1 ]; then skipnext=0; continue; fi
                    case "$tok" in
                        -r|--reference|-d|--date|-t) skipnext=1 ;;   # option consumes the next token
                        --reference=*|--date=*) ;;                    # =-joined arg, not a target
                        -*) ;;                                        # other touch flag (-a/-c/-m/-h)
                        *) cand="${cand}
${tok}" ;;
                    esac
                done
                ;;
        esac
        # FAIL CLOSED for the mutating verbs the precise parse above CANNOT target by shape: deletion
        # (`rm`/`unlink`/`shred`), symlink clobber (`ln`), and interpreter one-liners that write a file
        # NAMED INSIDE inline code (`python3 -c 'open("X","w")'`). For these, ANY sensitive basename in
        # the segment is treated as the mutated file. NOT run for cp/mv/install/sed/tee/touch/redirects —
        # those extract their precise target(s) above, and a broad scan there would wrongly flag a READ
        # (`cp KeychainManager.swift /backup/`, or `python3 report.py X.swift > out` whose write is `out`,
        # not `X.swift`). An interpreter with only a redirect (no inline code) is skipped for the same
        # reason (round 2: codex). So `cat X`/`grep foo X` never trip it (#44 review §6).
        _bcheck=0
        case "$base_verb" in
            rm|unlink|shred|ln) _bcheck=1 ;;
            python|python2|python3|perl|ruby|node|nodejs|osascript|bash|sh|zsh)
                _seg_has_inline_code "$seg" && _bcheck=1 ;;
        esac
        if [ "$_bcheck" = 1 ]; then
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
