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
#   capture-codex-review.sh <ticket> <round> <prompt-file> [timeout-seconds]
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
# The prompt's digest is recorded beside the transcript as `<transcript>.promptsha256`, so a
# cross-wire is not only prevented but DETECTABLE after the fact.
#
# Exit: the allocator's own status if allocation fails · 1 on a missing operand, an unreadable or
#       empty prompt, or a malformed marker · otherwise pty-capture's status, which matches codex's.
set -uo pipefail

TICKET="${1-}"
ROUND="${2-}"
PROMPT="${3-}"
TIMEOUT="${4-1200}"   # xhigh reasoning survives this; 600 SIGTERMs it mid-review

die() { printf 'codex review: %s\n' "$1" >&2; exit 1; }

# Operands first, and BEFORE allocation: a round that cannot run must not consume a reserved leaf.
[ -n "$TICKET" ] || die "bind TICKET to the --ticket operand"
[ -n "$ROUND" ]  || die "bind ROUND to the --round operand"
[ -n "$PROMPT" ] || die "name the PER-ROUND prompt file — there is no shared default"
# Parity with the other arm, which has always checked this (`isolated-agy-review.sh`). `$(cat …)` on a
# missing file expands EMPTY, so without this codex would be handed an empty prompt and would review
# nothing — and whatever it said about nothing would be parsed for a verdict.
[ -r "$PROMPT" ] || die "prompt file is not readable: $PROMPT"
[ -s "$PROMPT" ] || die "prompt file is EMPTY: $PROMPT"

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SCRIPTS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)" || exit 1

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
# Bind the prompt to THIS transcript, BEFORE the capture runs: a round that later times out still
# leaves the record of which prompt it was reviewing. `shasum -a 256` is on macOS, `sha256sum` on
# GNU — take whichever exists, and record the prompt's own path alongside its digest.
_prompt_digest() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
    else python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
    fi
}
printf '%s  %s\n' "$(_prompt_digest "$PROMPT")" "$PROMPT" > "${CODEX_TRANSCRIPT}.promptsha256"
exec python3 "${SCRIPTS_DIR}/pty-capture.py" --timeout "$TIMEOUT" --allocated "$CODEX_TRANSCRIPT" -- \
    codex exec -c model_reasoning_effort=xhigh -s read-only "$(cat "$PROMPT")"
