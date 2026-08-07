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

# CONTAIN THE PLAN. This is a granted entrypoint on the model-invocable `brainstorm` and
# `review-synthesis` skills, so the MODEL chooses `--plan`. Nothing enforced containment: a plan
# anywhere on disk was accepted, and even a non-approving call created and chmod'd a `.verdicts`
# directory beside it — reproduced against `/tmp`, which walked straight past the apparent
# `Write(docs/planning/**)` boundary with no user gesture (PR #63 recheck, P1).
#
# The check lives HERE and not in `review-verdict.py`: that tool has a designed, tested behaviour for
# a plan outside any git repo, and it is also the maintainer's own CLI. What must be bounded is the
# pre-approved path the model can enter.
SCRIPT_DIR_PV="$(cd -- "$(dirname -- "$0")" && pwd)"
# THE VALIDATED PATH IS THE ONE THAT GETS OPENED (PR #63 recheck, P1) — see `snapshot-plan.sh` for the
# same change and the reason. `PLAN_PATH` is REPLACED, not shadowed, so no later line can reach for the
# unvalidated spelling.
PLAN_PATH="$(python3 "${SCRIPT_DIR_PV}/containment.py" --tool "persist-verdict" --label "plan" \
    --under "docs/planning" --absolute -- "$PLAN_PATH")" \
    || die "refusing to persist: the plan is not an in-repo docs/planning file (see above)"
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
    # BARE `<name>=MISSING` is the DOCUMENTED form for a reviewer that never ran — there is no
    # transcript path to give (review-synthesis/SKILL.md: "record <reviewer>=MISSING **without** a
    # :transcript path"). Requiring a colon rejected precisely the unavailable-reviewer recovery
    # path the gate depends on, which is the one case where the caller has nothing else to offer.
    case "$rest" in
        MISSING) status=MISSING; transcript="" ;;
        *:*)     status="${rest%%:*}"; transcript="${rest#*:}" ;;
        *)       die "reviewer specification lacks a transcript path" ;;
    esac
    [ "$name" = "$expected_name" ] || die "invalid reviewer specification"
    case "$status" in
        # A status that CLAIMS a review happened must name the transcript it happened in.
        APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)
            [ -n "$transcript" ] || die "invalid reviewer specification" ;;
        MISSING) ;;
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
# Resolve the PARENT too rather than exec'ing a `…/review/../review-verdict.py` spelling: the writer
# is named in diagnostics and matched by path, and a non-canonical spelling of it is a different
# string to everything downstream even though it opens the same file.
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SCRIPTS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)" || exit 1

exec python3 "${SCRIPTS_DIR}/review-verdict.py" write \
    --plan "$PLAN_PATH" \
    --verdict "$COMBINED_VERDICT" \
    --reviewer "$GEMINI_PERSIST_SPEC" \
    --reviewer "$CODEX_PERSIST_SPEC" \
    --created-at "${CREATED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
