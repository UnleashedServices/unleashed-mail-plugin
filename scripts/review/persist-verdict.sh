#!/usr/bin/env bash
# Persist a Combined plan-review verdict, fail-closed.
#
# WHY THIS EXISTS
# This logic used to be a compound shell block pasted into four SKILL.md bodies
# (review-synthesis, codex-review, gemini-review, brainstorm). Each block defined
# functions and used `case`/`if`, so it matched none of those skills' `allowed-tools`
# Bash shapes — meaning the one block every gate round must run prompted for
# permission every time, re-creating the reprompting problem MIN-27 documents as
# fixed and pressuring operators toward blanket `Bash` grants (PR #63 review, gaps
# 7-9 and bot thread 7). As one committed script it is covered by the existing
# `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)` grant, so each recipe reduces
# to a single granted command — and the rule lives in ONE place instead of four
# copies that can drift apart.
#
# Usage:
#   persist-verdict.sh --plan PATH --verdict V \
#       --reviewer gemini=STATUS:TRANSCRIPT --reviewer codex=STATUS:TRANSCRIPT \
#       [--created-at ISO8601]
#
# STATUS is APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES | MISSING.
#
# Exit: 0 persisted · 1 invalid input, or an approval that a missing transcript
# cannot support.
set -uo pipefail

PLAN_PATH=""
COMBINED_VERDICT=""
CREATED_AT="${CREATED_AT:-}"
GEMINI_SPEC=""
CODEX_SPEC=""

die() { printf 'review synthesis: %s\n' "$1" >&2; exit 1; }

while [ "$#" -gt 0 ]; do
    case "$1" in
        --plan)       [ "$#" -ge 2 ] || die "--plan needs a value"; PLAN_PATH="$2"; shift 2 ;;
        --verdict)    [ "$#" -ge 2 ] || die "--verdict needs a value"; COMBINED_VERDICT="$2"; shift 2 ;;
        --created-at) [ "$#" -ge 2 ] || die "--created-at needs a value"; CREATED_AT="$2"; shift 2 ;;
        --reviewer)
            [ "$#" -ge 2 ] || die "--reviewer needs a value"
            case "$2" in
                gemini=*) GEMINI_SPEC="$2" ;;
                codex=*)  CODEX_SPEC="$2" ;;
                *)        die "unknown reviewer in specification: $2" ;;
            esac
            shift 2 ;;
        *) die "unexpected argument: $1" ;;
    esac
done

[ -n "$PLAN_PATH" ]        || die "bind --plan to the reviewed plan"
[ -n "$COMBINED_VERDICT" ] || die "bind --verdict to the synthesis result"
[ -n "$GEMINI_SPEC" ]      || die "bind the complete gemini reviewer argument"
[ -n "$CODEX_SPEC" ]       || die "bind the complete codex reviewer argument"

# Parse `name=STATUS:TRANSCRIPT` and echo the spec to persist. A reviewer whose status is
# MISSING, or whose transcript is absent/empty, is persisted as `name=MISSING` — an empty
# transcript is a FAILED review, never a silent pass (MAJ-10: absent, never stale).
persist_reviewer_spec() {
    spec="$1"; expected_name="$2"
    case "$spec" in *=*) ;; *) die "malformed reviewer specification" ;; esac
    name="${spec%%=*}"
    rest="${spec#*=}"
    case "$rest" in *:*) ;; *) die "reviewer specification lacks a transcript path" ;; esac
    status="${rest%%:*}"
    transcript="${rest#*:}"
    if [ "$name" != "$expected_name" ] || [ -z "$transcript" ]; then
        die "invalid reviewer specification"
    fi
    case "$status" in
        APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES|MISSING) ;;
        *) die "invalid reviewer status" ;;
    esac
    if [ "$status" = MISSING ] || [ ! -s "$transcript" ]; then
        printf '%s=MISSING' "$name"
    else
        printf '%s' "$spec"
    fi
}

GEMINI_PERSIST_SPEC="$(persist_reviewer_spec "$GEMINI_SPEC" gemini)" || exit 1
CODEX_PERSIST_SPEC="$(persist_reviewer_spec "$CODEX_SPEC" codex)" || exit 1

# The gate's core invariant: an absent or empty transcript can never be counted as approval.
if [ "$GEMINI_PERSIST_SPEC" = gemini=MISSING ] || [ "$CODEX_PERSIST_SPEC" = codex=MISSING ]; then
    case "$COMBINED_VERDICT" in
        APPROVE|APPROVE_WITH_NOTES)
            die "a missing transcript cannot produce approval" ;;
    esac
fi

# `${CLAUDE_PLUGIN_ROOT}` is unset in an ordinary Bash tool shell, so resolve relative to
# this script instead (COREDEV-2619 round 14 — do not reintroduce the variable here).
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"

exec python3 "${SCRIPT_DIR}/../review-verdict.py" write \
    --plan "$PLAN_PATH" \
    --verdict "$COMBINED_VERDICT" \
    --reviewer "$GEMINI_PERSIST_SPEC" \
    --reviewer "$CODEX_PERSIST_SPEC" \
    --created-at "${CREATED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
