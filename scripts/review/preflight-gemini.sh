#!/usr/bin/env bash
# Health-check the plan gate's Gemini arm (the `gemini` CLI, COREDEV-2887) into a path this script
# allocates, through the SAME adapter a review runs through, so the model assertion applies here too.
#
# WHY AN EXACT ENTRYPOINT
# A grant like `Bash(gemini *)` would let the CLI run outside `isolated-gemini-review.sh`, and headless
# plan mode is NOT read-only (plan §1 F4: observed leaving plan mode and writing). This script takes NO
# caller input, hard-codes the ping prompt, loads the deny policy, runs in a scratch directory, and
# fingerprints the caller's checkout before and after.
#
# Usage:
#   preflight-gemini.sh       # prints the ping transcript path, then the healthy/unavailable verdict
#
# Exit: 0 the CLI answered `pong` AS the gate's model · 1 the CLI is absent, unauthenticated, out of
# quota, answered with another model, or answered something else. A non-zero exit is NOT a waiver: the
# gate is fail-closed and the operator chooses the recovery.
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SCRIPTS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)" || exit 1
# THE GATE'S MODEL, from the harness that runs the review — one literal, never a second copy here. Read FIRST,
# so that EVERY failure line below names it (codex, plan rounds 2 to 4; §0.4).
MODEL="$(sed -nE 's/^DEFAULT_MODEL="([A-Za-z0-9][A-Za-z0-9._-]*)"$/\1/p' "${SCRIPT_DIR}/isolated-gemini-review.sh")"

die() {
	printf 'gemini preflight (%s): %s\n' "${MODEL:-<no model>}" "$1" >&2
	exit 1
}

command -v gemini >/dev/null 2>&1 || die "the gemini CLI is not on PATH — the gate is fail-closed, not waived"

# PER-RUN ping path. A shared one lets a preflight that died before writing leave the PREVIOUS run's
# `pong` in place, so a dead CLI reads as healthy — and the preflight is what decides whether the
# mandatory gate can run at all (deep review, P2).
PING="$(mktemp "${TMPDIR:-/tmp}/gemini-ping.XXXXXX")" || die "could not allocate a ping path"
printf '%s\n' "${PING}"

# CHECK THE CAPTURE'S STATUS, not just its output. An `agy` that prints text containing `pong` and
# then exits non-zero — or a wrapper that times out after emitting it — left this unguarded and the
# grep below reported `healthy` with exit 0. Reproduced with a stub printing `Pong` and exiting 23
# (deep review, P2). A preflight is what decides whether the mandatory gate may run; it fails closed.
# RUN IT SOMEWHERE DISPOSABLE. This launched `agy` in the CALLER'S WORKING DIRECTORY — the reviewed
# checkout — while the same skill documents that agy has no read-only mode and has already once
# implemented a plan instead of reviewing it. A stub that touched a file in its cwd left that file in
# the checkout and this script still printed `healthy` (PR #63 recheck, P2 — reproduced). A ping needs
# no repository, so it gets an empty directory and the checkout is never exposed to it.
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/gemini-preflight.XXXXXX")" || die "could not allocate a scratch dir"
# shellcheck disable=SC2329 # invoked by the EXIT trap on the next line
cleanup_scratch() { rm -rf "${SCRATCH}"; }
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
	BEFORE="$(tree_fingerprint "${REPO_ROOT}")" || {
		printf 'gemini preflight (%s): FAILED — could not fingerprint the checkout before the ping.\n' "${MODEL:-<no model>}" >&2
		exit 1
	}
	# Same untracked mode as `tree_fingerprint`: comparing a collapsed baseline against an expanded
	# "after" would print every file under an untracked directory as newly added.
	BEFORE_STATUS="$(git -C "${REPO_ROOT}" status --porcelain 2>/dev/null)"
fi

# THE STATUS IS RETAINED, NOT ACTED ON YET (PR #63 recheck, P2). This used to `exit 1` right here, so
# an `agy` that MUTATED the reviewed checkout through an absolute path and then exited non-zero left
# the mutation in the tree while the preflight reported only "unavailable" — the fingerprint below, the
# safeguard that exists for exactly this shell-capable reviewer, never ran. A mutating build is the
# more serious finding of the two and must be reported whatever the exit status, so the comparison runs
# unconditionally and the capture failure is returned after it.
CAPTURE_RC=0
# THE PING RUNS ON THE MODEL THE GATE WILL RUN (COREDEV-2875 §2.1). A bare `agy -p "ping"` used agy's
# global setting — `~/.gemini/settings.json`, or agy's built-in default when that names none — which the
# gate never runs, so a stale setting could pass or fail this preflight on the wrong model. This script
# takes no caller input by design (above), so it checks the resolved DEFAULT; a round run with an explicit
# model operand is not preflighted, and its failure shows as a tiny transcript, never a verdict.
# A resolution failure IS a preflight failure, retained like the capture status so the fingerprint
# comparison below still runs.
if [[ -n ${MODEL} ]]; then
	(cd "${SCRATCH}" && python3 "${SCRIPTS_DIR}/pty-capture.py" --timeout 120 "${PING}" -- \
		python3 "${SCRIPT_DIR}/gemini-review-run.py" --model "${MODEL}" \
		--policy "${SCRIPT_DIR}/gemini-review-policy.toml" --diagnostics "${PING}.diag" -- \
		"Reply with exactly the single word: pong") ||
		CAPTURE_RC=$?
else
	printf 'gemini preflight (<no model>): could not read DEFAULT_MODEL from isolated-gemini-review.sh — the ping did not run\n' >&2
	CAPTURE_RC=1
fi

# THE CHECKOUT MUST BE UNCHANGED. Checked before the verdict, so a mutating reviewer CLI cannot be reported
# healthy — the earlier version would have said `healthy` while a file it created sat in the tree.
if [[ -n ${BEFORE} ]] || [[ -n ${REPO_ROOT:-} ]]; then
	AFTER="$(tree_fingerprint "${REPO_ROOT:-.}")" || {
		printf 'gemini preflight (%s): FAILED — the gemini CLI left the checkout unreadable (its Git metadata is gone or\n' "${MODEL:-<no model>}" >&2
		printf 'corrupt). Do not run a review with this gemini CLI build.\n' >&2
		exit 1
	}
	if [[ ${BEFORE} != "${AFTER}" ]]; then
		printf 'gemini preflight (%s): FAILED — the gemini CLI MUTATED the working tree during a ping:\n' "${MODEL:-<no model>}" >&2
		# Only what CHANGED at the STATUS level, for a readable summary — printing the whole status (or
		# the whole diff) buries the one new line. A content-only edit to an already-dirty file shows no
		# new status line, so say so rather than printing nothing.
		tree_fingerprint_report "${REPO_ROOT:-.}" "${BEFORE_STATUS}" "${BEFORE%%$'\n'*}"
		printf 'This is the COREDEV-2607 failure mode. Do not run a review with this gemini CLI build.\n' >&2
		exit 1
	fi
fi

# EVERY FAILURE NAMES THE MODEL (codex, plan rounds 2 and 3) — including a ping that timed out or was killed
# before the adapter could write its own refusal. The adapter's refusal, when there is one, is in `<ping>.diag`
# (never in the ping transcript, which a refused run leaves empty), and is repeated here.
if [[ ${CAPTURE_RC} -ne 0 ]]; then
	REFUSAL="$(grep -a '^GEMINI ARM FAILED' "${PING}.diag" 2>/dev/null | tail -1)"
	printf 'gemini preflight (%s): the capture exited %s — %s\n' "${MODEL:-<no model>}" "${CAPTURE_RC}" \
		"${REFUSAL:-no adapter refusal was recorded (timed out or killed); see ${PING}.diag}" >&2
	printf 'Treating the Gemini arm as UNAVAILABLE regardless of what landed in %s. The gate is FAIL-CLOSED; do not self-waive.\n' "${PING}" >&2
	exit 1
fi

# THE WHOLE ANSWER, not a substring (codex, plan round 1, Q2): `grep -qi pong` passed `not pong` and
# `pong unavailable`. The answer must be `pong`, case-insensitive, optionally ending in one `.` or `!`, with
# surrounding whitespace ignored. The adapter has already asserted the model and refused a JSON error.
if python3 -c 'import re, sys; sys.exit(0 if re.fullmatch(r"(?i)pong[.!]?", open(sys.argv[1], errors="replace").read().strip()) else 1)' "${PING}"; then
	printf 'gemini preflight: healthy\n'
	exit 0
fi
# shellcheck disable=SC2016 # the backticks are literal text in the message, not an expansion
printf 'gemini preflight (%s): no pong in %s — the Gemini arm is unavailable or unauthenticated. Run `gemini`\n' "${MODEL}" "${PING}" >&2
printf 'interactively once to re-login. The gate is FAIL-CLOSED: do not count this as APPROVE, and do not self-waive.\n' >&2
exit 1
