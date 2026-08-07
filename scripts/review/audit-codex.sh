#!/usr/bin/env bash
# Run a read-only codex audit through the PTY wrapper, into a path this script allocates.
#
# WHY THIS EXISTS
# `codex-review` granted `Bash(codex *)` and `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)`. Those are
# command-string wildcards, not a restriction to the documented recipe: the first pre-approves ANY
# codex invocation — including `-s danger-full-access` — outside every wrapper, and the second
# pre-approves `pty-capture.py <any path> -- <any command>`, i.e. arbitrary child execution writing to
# an arbitrary file, plus the destructive cleanup tool with `--apply` (deep review, P1).
#
# This script is the exact entrypoint that replaces both for the audit path. It hard-codes the safe
# flags — `-s read-only` and `model_reasoning_effort=xhigh` cannot be overridden by a caller — and
# ALLOCATES its own output rather than accepting one, so the grant cannot be used to write elsewhere.
#
# Usage:
#   audit-codex.sh <reviewer-slash-command> [in-repo files...]
#     e.g. audit-codex.sh /security-reviewer Sources/Mail/Sync.swift
#
# Every operand after the reviewer must be a non-symlink regular file beneath this repository. Free-form
# text is not accepted: it is not a filename, and in this position it is prompt injection.
#
# Prints the audit transcript path on stdout. Exit: pty-capture's status (codex's), or 1 on bad input.
set -uo pipefail

die() { printf 'codex audit: %s\n' "$1" >&2; exit 1; }

[ "$#" -ge 1 ] || die "name the reviewer slash-command to run, e.g. /security-reviewer"

REVIEWER="$1"
shift
# An allowlist, not a pattern: these are the audit personas `codex-review` documents. A free-form
# prompt here would put arbitrary text into the codex invocation this grant pre-approves.
case "$REVIEWER" in
    /security-reviewer|/concurrency-reviewer|/ux-perf-reviewer|/accessibility-auditor|/prompt-review) ;;
    *) die "unknown reviewer $REVIEWER — allowed: /security-reviewer /concurrency-reviewer /ux-perf-reviewer /accessibility-auditor /prompt-review" ;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SCRIPTS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)" || exit 1

# PER-RUN output, allocated here. A fixed path is the MAJ-10 hazard in miniature: an audit that dies
# before writing leaves the PREVIOUS audit's file for the next reader to take as fresh findings. The
# TEMPLATE form, not `-t`: `mktemp -t name` is a BSD shorthand GNU rejects, and `-t name.XXXXXX`
# leaves the X's literal on BSD (deep review, P2).
AUDIT_OUT="$(mktemp "${TMPDIR:-/tmp}/codex-audit.XXXXXX")" || die "could not allocate an audit path"

# CONTAIN THE FILE OPERANDS. The reviewer name was allowlisted and everything after it was not: `$*`
# folded the rest into one free-form string that went straight into the codex prompt this grant
# pre-approves. Reproduced at head `3498f43` with an exact stub — `/etc/passwd` was accepted, exit 0,
# and `codex exec … "/security-reviewer /etc/passwd"` was invoked; so was a plain
# "ignore prior instructions …" operand, which is prompt injection rather than a filename. `-s read-only`
# stops writes; it is not a repository-read boundary and does not stop disclosure to an external
# service (PR #63 recheck, P1).
#
# `containment.py` is the SAME module `bind-prompt.py` uses. That sharing is the actual fix: the
# prompt-operand hole was closed a day earlier and this sibling — written in the same batch — did not
# inherit it, because the rule lived inside the other script.
# SNAPSHOT THE OPERANDS, do not just validate them (PR #63 recheck, P1). Validating with
# `containment.py` and then handing codex the repo-relative PATH left a validate-then-open race: a
# same-account process replaced an accepted file with a symlink to an outside secret between the check
# and codex's open, and `codex exec -s read-only` followed it and disclosed the outside file. Reproduced
# end to end. `snapshot-operands.py` validates AND reads each operand through one `O_NOFOLLOW` descriptor
# into a private disposable tree, and codex is pointed at those immutable copies — no later swap can
# change what it reads, and a swap landing during the read is refused rather than followed. `-s
# read-only` stops writes; it was never a validate-then-open boundary.
CONTAINED=""
SNAP_DIR=""
if [ "$#" -gt 0 ]; then
    SNAP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/codex-audit-src.XXXXXX")" || die "could not allocate a snapshot dir"
    CONTAINED="$(python3 "${SCRIPT_DIR}/snapshot-operands.py" --tool "codex audit" --dest "$SNAP_DIR" -- "$@")" \
        || die "refusing to audit: an operand is not an in-repo file (see the message above)"
fi
cleanup() { [ -n "$SNAP_DIR" ] && rm -rf "$SNAP_DIR"; }
trap cleanup EXIT

# One path per line, from the SNAPSHOT output rather than from the caller's argv, so codex opens the
# immutable copies. Newlines are safe here because `containment.py` rejects control characters, which is
# also what stops a crafted filename forging an extra operand.
PROMPT="$REVIEWER"
if [ -n "$CONTAINED" ]; then
    PROMPT="$(printf '%s\n%s' "$REVIEWER" "$CONTAINED")"
fi

printf '%s\n' "$AUDIT_OUT"
# `exec` would drop the EXIT trap that cleans the snapshot dir, so run-and-propagate instead.
python3 "${SCRIPTS_DIR}/pty-capture.py" --timeout 1200 "$AUDIT_OUT" -- \
    codex exec -c model_reasoning_effort=xhigh -s read-only "$PROMPT"
exit $?
