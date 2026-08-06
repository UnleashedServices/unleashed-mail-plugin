#!/usr/bin/env bash
# Allocate a per-run transcript leaf and capture a gemini plan review into it. Fail-closed.
#
# WHY THIS EXISTS
# The last of the five inline recipes (PR #63 review, gaps 7-9 and bot thread 7). This was two `:`
# guards, an `if`/`else` around the allocator and a `case` on the marker — a compound command, which
# Claude Code decomposes and wants a rule per subcommand for, so it matched none of this skill's
# `allowed-tools` shapes and prompted on every gate round. As one committed script the recipe reduces
# to a single command covered by an exact-entrypoint grant.
#
# Usage:
#   capture-gemini-review.sh <ticket> <round> <prompt-file> <plan> [timeout-seconds]
#
# Prints the allocator's `UNLEASHED_TRANSCRIPT=<path>` marker on stdout, byte-for-byte, BEFORE the
# capture starts: synthesis binds that exact path, and it must survive a capture that later times out.
#
# THE PROMPT FILE IS REQUIRED AND MUST BE PER-ROUND. It defaulted to a fixed `.agy-prompt.md`, which is
# the same MAJ-10 hazard as a fixed transcript: two concurrent rounds each get a unique transcript leaf,
# but the second overwrites the shared prompt before the first wrapper reads it, so the first round
# records a fresh, valid transcript OF THE OTHER PLAN under its own ticket and round (deep review, P1).
#
# `bind-prompt.py` records BOTH the prompt digest (`<transcript>.promptsha256`) and the plan this
# round reviews (`<transcript>.plan`). The plan binding is the ENFORCED one: `review-verdict.py
# write` refuses an approving verdict whose transcript reviewed different bytes. The earlier
# sidecar was written and read by nothing, so transcripts from an unrelated ticket still produced
# `GATE OK — APPROVE` (deep review, P1) — 'detectable' is only true if something looks.
#
# Exit: the allocator's own status if allocation fails · 1 on a missing operand, an unreadable or empty
#       prompt, or a malformed marker · otherwise the isolation harness's status (3 = the reviewer
#       MUTATED the working tree, round void).
set -uo pipefail

TICKET="${1-}"
ROUND="${2-}"
PROMPT="${3-}"
PLAN="${4-}"
TIMEOUT="${5-1800}"   # must EXCEED agy --print-timeout (28m=1680s) or the wrapper kills a live run

die() { printf 'gemini-review: %s\n' "$1" >&2; exit 1; }

# Operands first, and BEFORE allocation: a round that cannot run must not consume a reserved leaf.
[ -n "$TICKET" ] || die "bind TICKET to the --ticket operand"
[ -n "$ROUND" ]  || die "bind ROUND to the --round operand"
[ -n "$PROMPT" ] || die "name the PER-ROUND prompt file — there is no shared default"
[ -n "$PLAN" ]   || die "name the plan this round reviews — the transcript is bound to it"
[ -r "$PROMPT" ] || die "prompt file is not readable: $PROMPT"
[ -s "$PROMPT" ] || die "prompt file is EMPTY: $PROMPT"

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"

# RETRIES MUST RE-ALLOCATE, and must never delete the reserved leaf. The allocator creates it 0-byte
# and `pty-capture.py --allocated` opens it WITHOUT O_CREAT, so removing it makes the final write fail
# on a missing file AFTER the full review has run — the round is lost (PR #63 review, gap 14). The rule
# lives HERE, above the allocation, rather than beside the capture: re-allocation is what a retry does.
#
# The reviewer identity is a LITERAL, never a variable. It is what the allocator names the leaf after,
# so a runtime-derived value would let one arm allocate under the other's name and let a single review
# satisfy both halves of the gate.
if TRANSCRIPT_MARKER="$(bash "${SCRIPT_DIR}/allocate-transcript.sh" "$TICKET" "$ROUND" gemini)"; then
    :
else
    status="$?"
    exit "$status"
fi
case "$TRANSCRIPT_MARKER" in
    UNLEASHED_TRANSCRIPT=?*) ;;
    *) die "allocator returned an invalid marker" ;;
esac
GEMINI_TRANSCRIPT="${TRANSCRIPT_MARKER#UNLEASHED_TRANSCRIPT=}"
printf '%s\n' "$TRANSCRIPT_MARKER"
# Bind the prompt AND the plan to THIS transcript, BEFORE the capture runs. `bind-prompt.py` also
# CONTAINS the operands: the `-r`/`-s` pair this replaced accepted any readable path, including
# `../secret`, whose bytes the capture below would then have sent to the reviewer CLI verbatim — and
# this entrypoint is pre-approved on a model-invocable skill, so the model chooses that operand
# (deep review, P1). It writes both sidecars with O_NOFOLLOW|O_EXCL, which the shell redirect it
# replaced did not. A failed binding aborts here, before the reviewer launches.
python3 "${SCRIPT_DIR}/bind-prompt.py" \
    --prompt "$PROMPT" --transcript "${GEMINI_TRANSCRIPT}" --plan "$PLAN" \
    || die "refusing to review: the prompt/plan binding could not be established"
exec bash "${SCRIPT_DIR}/isolated-agy-review.sh" "$PROMPT" "$GEMINI_TRANSCRIPT" "$TIMEOUT"
