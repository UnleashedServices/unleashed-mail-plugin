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
#   capture-gemini-review.sh <ticket> <round> <prompt-file> [timeout-seconds]
#
# Prints the allocator's `UNLEASHED_TRANSCRIPT=<path>` marker on stdout, byte-for-byte, BEFORE the
# capture starts: synthesis binds that exact path, and it must survive a capture that later times out.
#
# THE PROMPT FILE IS REQUIRED AND MUST BE PER-ROUND. It defaulted to a fixed `.agy-prompt.md`, which is
# the same MAJ-10 hazard as a fixed transcript: two concurrent rounds each get a unique transcript leaf,
# but the second overwrites the shared prompt before the first wrapper reads it, so the first round
# records a fresh, valid transcript OF THE OTHER PLAN under its own ticket and round (deep review, P1).
#
# The prompt's digest is recorded beside the transcript as `<transcript>.promptsha256`, so a cross-wire
# is not only prevented but DETECTABLE after the fact.
#
# Exit: the allocator's own status if allocation fails · 1 on a missing operand, an unreadable or empty
#       prompt, or a malformed marker · otherwise the isolation harness's status (3 = the reviewer
#       MUTATED the working tree, round void).
set -uo pipefail

TICKET="${1-}"
ROUND="${2-}"
PROMPT="${3-}"
TIMEOUT="${4-1800}"   # must EXCEED agy --print-timeout (28m=1680s) or the wrapper kills a live run

die() { printf 'gemini-review: %s\n' "$1" >&2; exit 1; }

# Operands first, and BEFORE allocation: a round that cannot run must not consume a reserved leaf.
[ -n "$TICKET" ] || die "bind TICKET to the --ticket operand"
[ -n "$ROUND" ]  || die "bind ROUND to the --round operand"
[ -n "$PROMPT" ] || die "name the PER-ROUND prompt file — there is no shared default"
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
# Bind the prompt to THIS transcript, BEFORE the capture runs: a round that later times out still
# leaves the record of which prompt it was reviewing. `shasum -a 256` is on macOS, `sha256sum` on GNU.
_prompt_digest() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
    else python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
    fi
}
printf '%s  %s\n' "$(_prompt_digest "$PROMPT")" "$PROMPT" > "${GEMINI_TRANSCRIPT}.promptsha256"
exec bash "${SCRIPT_DIR}/isolated-agy-review.sh" "$PROMPT" "$GEMINI_TRANSCRIPT" "$TIMEOUT"
