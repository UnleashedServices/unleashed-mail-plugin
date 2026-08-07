#!/usr/bin/env bash
# Allocate a per-run transcript leaf and capture a codex plan review into it. Fail-closed.
#
# WHY THIS EXISTS
# This was a compound block inlined in `skills/codex-review/SKILL.md`: two `:` guards, an `if`/`else`
# around the allocator and a `case` on the marker. Claude Code decomposes a compound command and wants
# a rule per subcommand, so the block matched none of that skill's `allowed-tools` Bash shapes and
# prompted for permission on every gate round — the reprompting problem MIN-27 records as fixed, and
# the pressure toward blanket `Bash` grants (PR #63 review, gaps 7-9 and bot thread 7). As one
# committed script the recipe reduces to a single command covered by the existing
# `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)` grant.
#
# Usage:
#   capture-codex-review.sh <ticket> <round> <prompt-file> <plan> [timeout-seconds]
#
# Prints the allocator's `UNLEASHED_TRANSCRIPT=<path>` marker on stdout, byte-for-byte, BEFORE the
# capture starts: synthesis binds that exact path, and it must survive a capture that later times out.
#
# THE PROMPT FILE IS REQUIRED AND MUST BE PER-ROUND. It defaulted to a fixed `.codex-prompt.md`, which
# is the same MAJ-10 hazard as a fixed transcript: two concurrent rounds each get a unique transcript
# leaf, but the second overwrites the shared prompt before the first wrapper reads it, so the first
# round records a fresh, valid transcript OF THE OTHER PLAN under its own ticket and round — defeating
# the evidence association this whole ticket exists to establish (deep review, P1). The tree already
# worked this way in practice: 337 of the 339 prompt files on disk are per-round names.
#
# `bind-prompt.py` records BOTH the prompt digest (`<transcript>.promptsha256`) and the plan this
# round reviews (`<transcript>.plan`). The plan binding is the ENFORCED one: `review-verdict.py
# write` refuses an approving verdict whose transcript reviewed different bytes. The earlier
# sidecar was written and read by nothing, so transcripts from an unrelated ticket still produced
# `GATE OK — APPROVE` (deep review, P1) — 'detectable' is only true if something looks.
#
# Exit: the allocator's own status if allocation fails · 1 on a missing operand, an unreadable or
#       empty prompt, or a malformed marker · otherwise pty-capture's status, which matches codex's.
set -uo pipefail

TICKET="${1-}"
ROUND="${2-}"
PROMPT="${3-}"
PLAN="${4-}"
TIMEOUT="${5-1200}"   # xhigh reasoning survives this; 600 SIGTERMs it mid-review

die() { printf 'codex review: %s\n' "$1" >&2; exit 1; }

# Operands first, and BEFORE allocation: a round that cannot run must not consume a reserved leaf.
[ -n "$TICKET" ] || die "bind TICKET to the --ticket operand"
[ -n "$ROUND" ]  || die "bind ROUND to the --round operand"
[ -n "$PROMPT" ] || die "name the PER-ROUND prompt file — there is no shared default"
[ -n "$PLAN" ]   || die "name the plan this round reviews — the transcript is bound to it"
# Parity with the other arm, which has always checked this (`isolated-agy-review.sh`). `$(cat …)` on a
# missing file expands EMPTY, so without this codex would be handed an empty prompt and would review
# nothing — and whatever it said about nothing would be parsed for a verdict.
[ -r "$PROMPT" ] || die "prompt file is not readable: $PROMPT"
[ -s "$PROMPT" ] || die "prompt file is EMPTY: $PROMPT"
# THE PROMPT BECOMES ONE argv ELEMENT, and Linux caps a single argument at `MAX_ARG_STRLEN`
# (32 x PAGE_SIZE = 128 KiB) regardless of the far larger `ARG_MAX` (PR #63 recheck). `codex exec`
# takes the whole prompt as an argument, so an oversized bound prompt made the `execvp` inside
# `pty-capture.py` fail with E2BIG — AFTER a transcript leaf had been reserved and a disposable
# worktree built. Checked HERE, before allocation, so nothing is consumed by a round that cannot run.
# The gemini arm is unaffected: it passes `-p "Read and follow <path>"` and the reviewer opens the file.
PROMPT_BYTES="$(wc -c < "$PROMPT" | tr -d ' ')"
if [ "$PROMPT_BYTES" -gt 122880 ]; then
    die "prompt is ${PROMPT_BYTES} bytes; codex receives it as ONE argument and Linux caps that at
128 KiB, so the reviewer would fail to start after allocating a leaf. Shorten the prompt or point it
at files instead of inlining them: $PROMPT"
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"

# RETRIES MUST RE-ALLOCATE, and must never delete the reserved leaf. The allocator creates it 0-byte
# and `pty-capture.py --allocated` opens it WITHOUT O_CREAT, so removing it makes the final write fail
# on a missing file AFTER the full review has run — the round is lost (PR #63 review, gap 14). The rule
# lives HERE, above the allocation, rather than beside the capture: re-allocation is what a retry does.
#
# The reviewer identity is a LITERAL, never a variable. It is what the allocator names the leaf after,
# so a runtime-derived value would let one arm allocate under the other's name and let a single review
# satisfy both halves of the gate. Being compiled into a committed script rather than written in a
# skill body is strictly stronger than where it used to live.
if TRANSCRIPT_MARKER="$(bash "${SCRIPT_DIR}/allocate-transcript.sh" "$TICKET" "$ROUND" codex)"; then
    :
else
    status="$?"
    exit "$status"
fi
case "$TRANSCRIPT_MARKER" in
    UNLEASHED_TRANSCRIPT=?*) ;;
    *) die "allocator returned an invalid marker" ;;
esac
CODEX_TRANSCRIPT="${TRANSCRIPT_MARKER#UNLEASHED_TRANSCRIPT=}"
printf '%s\n' "$TRANSCRIPT_MARKER"
# Bind the prompt AND the plan to THIS transcript, BEFORE the capture runs. `bind-prompt.py` also
# CONTAINS the operands: the `-r`/`-s` pair this replaced accepted any readable path, including
# `../secret`, whose bytes the capture below would then have sent to the reviewer CLI verbatim — and
# this entrypoint is pre-approved on a model-invocable skill, so the model chooses that operand
# (deep review, P1). It writes both sidecars with O_NOFOLLOW|O_EXCL, which the shell redirect it
# replaced did not. A failed binding aborts here, before the reviewer launches.
python3 "${SCRIPT_DIR}/bind-prompt.py" \
    --prompt "$PROMPT" --transcript "${CODEX_TRANSCRIPT}" --plan "$PLAN" \
    || die "refusing to review: the prompt/plan binding could not be established"
#
# ISOLATE LIKE THE GEMINI ARM (PR #63 recheck, P1). codex used to run `-s read-only` in the LIVE tree,
# so the plan file it opened was the mutable working-tree one: an A->B->A swap during codex's read
# window let it review substituted bytes while `.plan` and the live plan both still hashed A, and the
# artifact attested a plan the reviewer never read. `isolated-codex-review.sh` runs codex against a
# disposable detached checkout with the authenticated `.planbytes` staged in through the SHARED
# `stage-bound-plan.py` — the same isolation and the same staging the gemini arm uses, so the two arms
# cannot drift again. It feeds the prompt SNAPSHOT (the O_EXCL `.prompt`), never the caller's path.
exec bash "${SCRIPT_DIR}/isolated-codex-review.sh" \
    "${CODEX_TRANSCRIPT}.prompt" "$CODEX_TRANSCRIPT" "$TIMEOUT" "$PLAN"
