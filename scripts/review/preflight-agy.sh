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

# CHECK THE CAPTURE'S STATUS, not just its output. An `agy` that prints text containing `pong` and
# then exits non-zero — or a wrapper that times out after emitting it — left this unguarded and the
# grep below reported `healthy` with exit 0. Reproduced with a stub printing `Pong` and exiting 23
# (deep review, P2). A preflight is what decides whether the mandatory gate may run; it fails closed.
# RUN IT SOMEWHERE DISPOSABLE. This launched `agy` in the CALLER'S WORKING DIRECTORY — the reviewed
# checkout — while the same skill documents that agy has no read-only mode and has already once
# implemented a plan instead of reviewing it. A stub that touched a file in its cwd left that file in
# the checkout and this script still printed `healthy` (PR #63 recheck, P2 — reproduced). A ping needs
# no repository, so it gets an empty directory and the checkout is never exposed to it.
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/agy-preflight.XXXXXX")" || die "could not allocate a scratch dir"
cleanup_scratch() { rm -rf "$SCRATCH"; }
trap cleanup_scratch EXIT

# Fingerprint the checkout so a violation is DETECTED, not merely made unlikely. `isolated-agy-review.sh`
# earns its keep with exactly this assertion; the preflight had no equivalent.
#
# CONTENT, NOT JUST STATUS CATEGORY (PR #63 recheck, P2) — and the rule lives in ONE file, because the
# two isolation harnesses carried the same status-only comparison where it is gate-bearing.
. "${SCRIPT_DIR}/tree-fingerprint.sh"
BEFORE=""
BEFORE_STATUS=""
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    BEFORE="$(tree_fingerprint "$REPO_ROOT")"
    # Same untracked mode as `tree_fingerprint`: comparing a collapsed baseline against an expanded
    # "after" would print every file under an untracked directory as newly added.
    BEFORE_STATUS="$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null)"
fi

# THE STATUS IS RETAINED, NOT ACTED ON YET (PR #63 recheck, P2). This used to `exit 1` right here, so
# an `agy` that MUTATED the reviewed checkout through an absolute path and then exited non-zero left
# the mutation in the tree while the preflight reported only "unavailable" — the fingerprint below, the
# safeguard that exists for exactly this shell-capable reviewer, never ran. A mutating build is the
# more serious finding of the two and must be reported whatever the exit status, so the comparison runs
# unconditionally and the capture failure is returned after it.
CAPTURE_RC=0
( cd "$SCRATCH" && python3 "${SCRIPTS_DIR}/pty-capture.py" --timeout 60 "$PING" -- agy -p "ping" ) \
    || CAPTURE_RC=$?

# Case-INSENSITIVE, and the `!` is not required: across 3 measured runs agy answered `Pong! How can I
# help you today?`, a bare lowercase `pong`, and `Pong! Let me know…`. A `Pong!`-exact check calls a
# healthy CLI unavailable about one run in three.
# THE CHECKOUT MUST BE UNCHANGED. Checked before the verdict, so a mutating agy cannot be reported
# healthy — the earlier version would have said `healthy` while a file it created sat in the tree.
if [ -n "$BEFORE" ] || [ -n "${REPO_ROOT:-}" ]; then
    AFTER="$(tree_fingerprint "${REPO_ROOT:-.}")"
    if [ "$BEFORE" != "$AFTER" ]; then
        printf 'agy preflight: FAILED — agy MUTATED the working tree during a ping:\n' >&2
        # Only what CHANGED at the STATUS level, for a readable summary — printing the whole status (or
        # the whole diff) buries the one new line. A content-only edit to an already-dirty file shows no
        # new status line, so say so rather than printing nothing.
        tree_fingerprint_report "${REPO_ROOT:-.}" "$BEFORE_STATUS"
        printf 'This is the COREDEV-2607 failure mode. Do not run a review with this agy build.\n' >&2
        exit 1
    fi
fi

if [ "$CAPTURE_RC" -ne 0 ]; then
    printf 'agy preflight: the capture exited non-zero — treating agy as UNAVAILABLE regardless of\n' >&2
    printf 'what landed in %s. The gate is FAIL-CLOSED; do not self-waive.\n' "$PING" >&2
    exit 1
fi

if grep -qi pong "$PING"; then
    printf 'agy preflight: healthy\n'
    exit 0
fi
printf 'agy preflight: no pong in %s — agy is unavailable or unauthenticated. Run `agy` interactively\n' "$PING" >&2
printf 'once to re-login. The gate is FAIL-CLOSED: do not count this as APPROVE, and do not self-waive.\n' >&2
exit 1
