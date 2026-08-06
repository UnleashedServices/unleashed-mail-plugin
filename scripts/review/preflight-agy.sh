#!/usr/bin/env bash
# Health-check the `agy` CLI through the PTY wrapper, into a path this script allocates.
#
# WHY THIS EXISTS
# `gemini-review` granted `Bash(agy *)` and `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)`. The first
# lets `agy` run directly, outside `isolated-agy-review.sh` — and this PR documents that agy has NO
# read-only mode and has already implemented a plan instead of reviewing it. The second pre-approves
# `pty-capture.py <any path> -- <any command>` (deep review, P1).
#
# This script is the exact entrypoint that replaces both for the preflight path. It takes NO caller
# input, hard-codes the `-p "ping"` prompt, and allocates its own output.
#
# Usage:
#   preflight-agy.sh          # prints the ping transcript path, then the healthy/unavailable verdict
#
# Exit: 0 the CLI answered `pong` · 1 agy is absent, unauthenticated, or answered something else.
# A non-zero exit is NOT a waiver: the gate is fail-closed and the operator chooses the recovery.
set -uo pipefail

die() { printf 'agy preflight: %s\n' "$1" >&2; exit 1; }

command -v agy >/dev/null 2>&1 || die "agy is not on PATH — the gate is fail-closed, not waived"

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SCRIPTS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)" || exit 1

# PER-RUN ping path. A shared one lets a preflight that died before writing leave the PREVIOUS run's
# `pong` in place, so a dead CLI reads as healthy — and the preflight is what decides whether the
# mandatory gate can run at all (deep review, P2).
PING="$(mktemp "${TMPDIR:-/tmp}/agy-ping.XXXXXX")" || die "could not allocate a ping path"
printf '%s\n' "$PING"

python3 "${SCRIPTS_DIR}/pty-capture.py" --timeout 60 "$PING" -- agy -p "ping"

# Case-INSENSITIVE, and the `!` is not required: across 3 measured runs agy answered `Pong! How can I
# help you today?`, a bare lowercase `pong`, and `Pong! Let me know…`. A `Pong!`-exact check calls a
# healthy CLI unavailable about one run in three.
if grep -qi pong "$PING"; then
    printf 'agy preflight: healthy\n'
    exit 0
fi
printf 'agy preflight: no pong in %s — agy is unavailable or unauthenticated. Run `agy` interactively\n' "$PING" >&2
printf 'once to re-login. The gate is FAIL-CLOSED: do not count this as APPROVE, and do not self-waive.\n' >&2
exit 1
