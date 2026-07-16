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

# Kill switch (COREDEV-2494) — this was the only BLOCKING hook without one, despite emitting
# `decision:block` and arming the Stop gate. A blocking hook with no escape is exactly the thing a user
# needs to be able to turn off. (Most hooks here honour a `UNLEASHED_*` switch, but NOT all: this
# comment used to claim "every other hook" does. `swift-build-verify.sh` has none — its
# `UNLEASHED_FAILURE_LOG` gates only the log side-effect, and the advisory still fires; `test-runner.sh`
# and `pre-commit-checks.sh` have none either. Verified, pre-merge audit.)
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
LINT_OUTPUT=""
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

    # force_try / force_cast BLOCK at whatever severity SwiftLint assigned them (codex, #43 review).
    # This hook enforces the PROJECT's policy ("no force-try in production", CLAUDE.md) and uses
    # SwiftLint only as the ORACLE for "is there an UNWAIVED violation here". Severity is a per-repo
    # config knob — `force_try: severity: warning` is explicitly supported — and the app's current
    # `severity: error` is the only reason the error branch below catches these at all. Inheriting that
    # choice made a policy control silently configurable away: reported as a warning, an unwaived
    # `try!` produced an advisory with no `lint=fail` marker, so the Stop gate never armed. Reproduced.
    # PRODUCTION ONLY — the policy is "no force-try in PRODUCTION code" (CLAUDE.md), and force-try in a
    # test is legitimate (a fixture that must fail loudly). The grep fallback below has always carried
    # this guard; my stage-2 elevation did not, so a `try!` in an XCTestCase started BLOCKING — a
    # regression against alpha, which guards tests in all three places (gemini, #43 review; reproduced).
    FORCED=""
    if [[ "$FILE_PATH" != *Tests/* ]] && [[ "$FILE_PATH" != *Test.swift ]]; then
        FORCED=$(printf '%s' "$LINT_OUTPUT" | grep -E ": (error|warning):.*\((force_try|force_cast)\)" || true)
    fi
    if [ -n "$FORCED" ]; then
        add_block "❌ Force try/cast in production code — $FILE_PATH:
$(printf '%s' "$FORCED" | head -10)"
    fi

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
        # ...and DO NOT claim swiftlint ran (PR #43 review). `SWIFTLINT_RAN=1` was set on
        # `command -v swiftlint` ALONE, so a broken CLI skipped the try!/as! grep fallback below and
        # an unwaived `try!` got only this non-blocking advisory — no `lint=fail` marker, so the Stop
        # gate was left UNARMED. On alpha the greps ran unconditionally and DID block, so that was a
        # regression this PR introduced. Falling back to the greps restores alpha's behaviour exactly.
        #
        # Deliberately NOT `add_block` here: that would block EVERY Swift edit whenever the CLI is
        # misconfigured, including clean files. Handing the decision back to the greps blocks only on a
        # real, unwaived violation — fail-closed where it matters, quiet where it doesn't.
        SWIFTLINT_RAN=0
    fi
fi

# Does $1 (a source line) waive rule $2? A directive waives only the rules it NAMES; a bare
# `swiftlint:disable`/`:next` with no rule list is a blanket waiver. Prefix-strip, not `case`
# (COREDEV-2492/2494: a `)` in a case pattern collides with an enclosing `$( )`, and bash 3.2 cannot
# parse case-in-while-in-$() at all).
# Is $1 a REAL SwiftLint directive comment? If so, echo the directive body; else fail.
#
# The directive must BE the comment, not merely appear inside it. `_waives` and `_in_disabled_region`
# both used a bare "contains swiftlint:disable" test, so ordinary prose acted as a directive
# (codex, #43 review — reproduced):
#     // TODO: remove any swiftlint:disable force_try here      -> WAIVED a real try!
#     // we should swiftlint:disable force_try but we did not   -> WAIVED a real try!
#     // NOTE: we used to swiftlint:disable force_try here      -> opened a disable REGION
# All three are FAIL-OPEN: a comment ABOUT the linter silenced the linter.
#
# Anchor to the start of the COMMENT CONTENT, not the line: SwiftLint documents trailing directives
# (`let x = y as! Int // swiftlint:disable:this force_cast`), so requiring the LINE to start with `//`
# would miss those. Everything after the first `//`, minus leading blanks, must begin `swiftlint:`.
_directive_body() {
    case "$1" in *"//"*) ;; *) return 1 ;; esac
    _c="${1#*//}"
    while :; do
        case "$_c" in
            " "*) _c="${_c# }" ;;
            "	"*) _c="${_c#	}" ;;
            *) break ;;
        esac
    done
    case "$_c" in
        swiftlint:disable*|swiftlint:enable*) printf '%s' "$_c"; return 0 ;;
    esac
    return 1
}

# Is line $2 of file $1 inside an OPEN `swiftlint:disable <rule>` REGION?
#
# `_waives` only ever inspects the PRECEDING line, which covers `:next` and a blanket directive directly
# above. It does NOT cover the REGION form, which is what 15 real app files actually use:
#     // swiftlint:disable force_try
#     let a = try! ...        <- prev line IS the directive -> _waives says waived
#     let b = try! ...        <- prev line is CODE          -> _waives says NOT waived  == FALSE POSITIVE
#     // swiftlint:enable force_try
# That false block reached the developer only after this PR stopped gating the greps on SWIFTLINT_RAN,
# i.e. the region gap and the widened fallback are individually correct and jointly a regression — the
# 120-false-positive class the suppression used to hide. Found by pre-merge audit, not by the bots.
#
# Scope suffixes (:next/:this/:previous) are LINE-scoped and never open a region — only a bare
# `swiftlint:disable` does, until a matching `swiftlint:enable`.
_in_disabled_region() {
    awk -v n="$2" -v rule="$3" '
        NR >= n { exit }
        {
            line = $0
            # The directive must BE the comment, not appear in it. Anchor to the start of the COMMENT
            # CONTENT (after the first //), so prose like `// NOTE: we used to swiftlint:disable
            # force_try here` no longer OPENS A REGION and silences every hit below it (codex, #43).
            i = index(line, "//")
            if (i == 0) next
            body = substr(line, i + 2)
            sub(/^[ \t]+/, "", body)
            if (body !~ /^swiftlint:(disable|enable)/) next
            act  = (body ~ /^swiftlint:disable/) ? "d" : "e"
            tail = (act == "d") ? substr(body, length("swiftlint:disable") + 1) \
                                : substr(body, length("swiftlint:enable") + 1)
            if (act == "d" && tail ~ /^:(next|this|previous)/) next   # line-scoped, never a region
            sub(/ - .*$/, "", tail)                                   # drop the mandated ` - <rationale>`
            gsub(/[:,]/, " ", tail)
            names = " " tail " "
            gsub(/[ \t]+/, " ", names)
            blanket = (names ~ /^ *$/)
            # `all` is a DOCUMENTED SwiftLint keyword for every rule, in BOTH directions. Without it,
            # `disable force_try` ... `enable all` left the region OPEN and waived every hit after it
            # (fail-open), and `disable all` waived nothing (fail-closed). Verified against the docs.
            hit = blanket || index(names, " " rule " ") || index(names, " all ")
            if (hit) open = (act == "d") ? 1 : 0
        }
        END { exit (open ? 0 : 1) }
    ' "$1"
}

# Does the directive on line $1 waive rule $2 for the line at scope $3 (next|this|previous)?
#
# SwiftLint documents THREE line scopes, and the fallback only ever read the PRECEDING line — so two of
# them were ignored and legitimately-waived code was blocked (codex, #43 review; both reproduced):
#     let r = try! ... // swiftlint:disable:this force_try      <- same line   (16 sites in the app)
#     let r = try! ...
#     // swiftlint:disable:previous force_try                   <- following line
# Both are FALSE POSITIVES, so the gate stayed closed — but a hook that demands an edit the project's own
# convention forbids is broken in the direction that wastes a developer's afternoon.
_waives_scoped() {
    _line="$1"; _rule="$2"; _want="$3"
    _body=$(_directive_body "$_line") || return 1
    case "$_body" in swiftlint:disable*) ;; *) return 1 ;; esac   # an `enable` never waives
    _tail="${_body#swiftlint:disable}"
    case "$_tail" in
        :next*)     _got=next;     _tail="${_tail#:next}" ;;
        :this*)     _got=this;     _tail="${_tail#:this}" ;;
        :previous*) _got=previous; _tail="${_tail#:previous}" ;;
        *)          _got=region ;;
    esac
    # An unscoped `swiftlint:disable` opens a REGION, which also covers the line right after it.
    if [ "$_want" = next ]; then
        [ "$_got" = next ] || [ "$_got" = region ] || return 1
    else
        [ "$_got" = "$_want" ] || return 1
    fi
    # CUT THE RATIONALE FIRST — this project MANDATES `<rule> - <ticket>` (CLAUDE.md), and scanning the
    # prose as a rule list falsely waived (gemini, #43 review). Rule IDs never contain " - ".
    _rules="${_tail%% - *}"
    _stripped="$(printf '%s' "$_rules" | tr -d '[:space:]')"
    [ -z "$_stripped" ] && return 0                 # blanket disable, no rule list
    _norm=" $(printf '%s' "$_rules" | tr ',' ' ' | tr -s '[:space:]' ' ') "
    [ "${_norm#* all }" != "$_norm" ] && return 0   # documented `all` keyword
    # QUOTE the needle: unquoted, $_rule expands as a GLOB inside ${..} (SC2295).
    [ "${_norm#* "$_rule" }" != "$_norm" ] && return 0
    return 1
}

# Back-compat shim: the preceding line waiving THIS line == scope `next`.
_waives() { _waives_scoped "$1" "$2" next; }

# --- 3 & 4. try! / as! greps: FALLBACK ONLY, when SwiftLint did not run (COREDEV-2494).
#
# These greps cannot see `// swiftlint:disable:next force_try` — they filter only lines that are
# THEMSELVES comments, so a directive on line N never protects line N+1. Measured against the consumer
# app: 120 of 273 production `try!` sites carry that exact waiver, so the greps produced 120 FALSE
# POSITIVES and told the model "❌ Found 'try!' in production code" for code the project's own CLAUDE.md
# REQUIRES to be waived (the regex-migration epic — piecemeal NSRegularExpression conversion risks
# Sendable regressions). The hook then poisons a `lint=fail` marker that blocks Stop.
#
# SUPERSEDED (round 5) — kept only to record why the old reasoning was wrong, because it reads
# plausibly and a maintainer "restoring" it would reopen a real hole. It used to say: "When swiftlint ran
# it is authoritative: it honours the directives, and BOTH rules are default-error rules, so an UNWAIVED
# site still surfaces as `: error:` and stage 2 already blocks." The flaw: "swiftlint ran" does not mean
# these rules ran. `disabled_rules`/`only_rules`/`excluded:` all make swiftlint exit 0 with NO output,
# which is indistinguishable from a clean file — so the fallback was dropped for exactly the files
# swiftlint never policed. The gate is now per-rule and evidence-based: see `_lint_proved`.
# SILENCE IS NOT PROOF. `SWIFTLINT_RAN` only says the binary executed — it does NOT say these rules
# policed THIS file. The repo config can disable them (`disabled_rules`/`only_rules`) or exclude the
# path (`excluded:` — the consumer app excludes GRDB/SwiftSoup/Vendor/build/.build), and swiftlint then
# exits 0 with NO output, indistinguishable from a clean file. Gating the fallback on SWIFTLINT_RAN
# therefore dropped the net for exactly the files swiftlint never policed (codex, #43 review).
#
# Only a real FINDING proves the rule was enforced. Per-rule, because force_try and force_cast are
# independent: one being enforced says nothing about the other.
#
# Safe to widen now ONLY because the greps became waiver-aware: the 120 measured false positives came
# from waived sites, and `_waives` + `_in_disabled_region` filter those directly, so suppression is no
# longer load-bearing. (Both are required: `_waives` covers `:next`/adjacent directives, and
# `_in_disabled_region` covers the disable/enable REGION form that 15 real app files use. Crediting
# `_waives` alone was stale attribution — the region half landed later, in def02a4.)
_lint_proved() {
    [ "$SWIFTLINT_RAN" -eq 1 ] || return 1
    printf '%s' "$LINT_OUTPUT" | grep -qE "\($1\)"
}
if [[ "$FILE_PATH" != *Tests/* ]] && [[ "$FILE_PATH" != *Test.swift ]]; then
    # No toolchain: keep a coarse net, but honour an explicit waiver on the preceding line so the
    # fallback cannot demand a policy-violating edit either. -A1 pairs directive->site.
    TRY_BANG=""
    _lint_proved force_try || TRY_BANG=$(grep -nE 'try!' "$FILE_PATH" 2>/dev/null | grep -vE '^[0-9]+:[[:space:]]*//' \
        | while IFS= read -r hit; do
            n="${hit%%:*}"
            # A hit on line 1 has no preceding line, so there is nothing to waive. Guarding avoids
            # spawning a pointless `sed -n 0p` (gemini, #43 review). NOTE: gemini said this "prints an
            # error to stderr on BSD and GNU sed" — on BSD sed it actually exits 0 SILENTLY (verified),
            # so this is efficiency, not a bug: prev="" already yielded the correct not-waived answer.
            prev=""
            [ "$n" -gt 1 ] && prev=$(sed -n "$((n - 1))p" "$FILE_PATH" 2>/dev/null)
            # Prefix-strip, NOT `case`: a `)` in a case pattern collides with the closing `)` of the
            # enclosing `$( )` (and bash 3.2 — what macOS ships — cannot parse case-in-while-in-$() at
            # all). Same fix as COREDEV-2492. "${prev#*swiftlint:disable}" != "$prev" == "contains it".
            # The directive must name THIS rule (or be a blanket `swiftlint:disable` with no rule
            # list). `swiftlint:disable:next no_legacy_nsregex` before a `try! NSRegularExpression(...)`
            # is a REAL pattern in this codebase (the regex-migration epic) and must NOT be read as a
            # force_try waiver (PR #43 review).
            cur=$(sed -n "${n}p" "$FILE_PATH" 2>/dev/null)
            nxt=$(sed -n "$((n + 1))p" "$FILE_PATH" 2>/dev/null)
            if ! _waives "$prev" force_try \
               && ! _waives_scoped "$cur" force_try this \
               && ! _waives_scoped "$nxt" force_try previous \
               && ! _in_disabled_region "$FILE_PATH" "$n" force_try; then printf '%s\n' "$hit"; fi
        done)
    if [ -n "$TRY_BANG" ]; then
        add_block "❌ Found 'try!' in production code (swiftlint did not enforce force_try here — grep fallback) — $FILE_PATH:
$TRY_BANG"
    fi

    FORCE_CAST=""
    _lint_proved force_cast || FORCE_CAST=$(grep -nE 'as!' "$FILE_PATH" 2>/dev/null | grep -vE '^[0-9]+:[[:space:]]*//' \
        | while IFS= read -r hit; do
            n="${hit%%:*}"
            # A hit on line 1 has no preceding line, so there is nothing to waive. Guarding avoids
            # spawning a pointless `sed -n 0p` (gemini, #43 review). NOTE: gemini said this "prints an
            # error to stderr on BSD and GNU sed" — on BSD sed it actually exits 0 SILENTLY (verified),
            # so this is efficiency, not a bug: prev="" already yielded the correct not-waived answer.
            prev=""
            [ "$n" -gt 1 ] && prev=$(sed -n "$((n - 1))p" "$FILE_PATH" 2>/dev/null)
            # Prefix-strip, NOT `case`: a `)` in a case pattern collides with the closing `)` of the
            # enclosing `$( )` (and bash 3.2 — what macOS ships — cannot parse case-in-while-in-$() at
            # all). Same fix as COREDEV-2492. "${prev#*swiftlint:disable}" != "$prev" == "contains it".
            cur=$(sed -n "${n}p" "$FILE_PATH" 2>/dev/null)
            nxt=$(sed -n "$((n + 1))p" "$FILE_PATH" 2>/dev/null)
            if ! _waives "$prev" force_cast \
               && ! _waives_scoped "$cur" force_cast this \
               && ! _waives_scoped "$nxt" force_cast previous \
               && ! _in_disabled_region "$FILE_PATH" "$n" force_cast; then printf '%s\n' "$hit"; fi
        done)
    if [ -n "$FORCE_CAST" ]; then
        add_block "❌ Found 'as!' (force cast) in production code (swiftlint did not enforce force_cast here — grep fallback) — $FILE_PATH:
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
