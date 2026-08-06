#!/usr/bin/env bash
# Run a gemini (`agy`) plan review WITHOUT letting it write to the tree under review (COREDEV-2607).
#
# THE DEFECT THIS EXISTS FOR
# `agy` is not read-only, and there is no flag that makes it so. On 2026-07-29 a plan review
# IMPLEMENTED the plan instead of reviewing it: 6 shipped scripts modified, 5 files created, including
# a stray `marketplace.json` at the repo root. It emitted no `VERDICT:` line, so the gate failed closed
# — the fortunate failure mode — but the edits persisted and had to be reverted by hand. The concurrent
# `codex` review recorded "Concurrent implementation edits appeared during review, so citations were
# rechecked against committed HEAD"; its verdict was trustworthy only because it independently
# re-anchored. Nothing in the gate design required that.
#
# FLAGS THAT DO NOT WORK — TESTED, DO NOT RE-TRY THEM
# Each was run against a scratch dir with the prompt "Create a file named PROOF.txt … Do it now.":
#   agy (no flags)            -> file created
#   agy --mode plan           -> file created
#   agy --sandbox             -> file created
#   agy --sandbox --mode plan -> file created
# All four exited 0. `--help` describes `--mode` as "agent execution mode (accept-edits, plan)" and
# `--sandbox` as "Run in a sandbox with terminal restrictions enabled"; neither restricts file writes
# in print mode. This is the asymmetry with `codex`, which the gate already runs `-s read-only`.
#
# SO: ISOLATE, DO NOT CONSTRAIN. The reviewer is pointed at a disposable detached checkout of the
# reviewed commit, and the real working tree is asserted unchanged afterwards. A tree mutation FAILS
# the round rather than being cleaned up silently — the same rule `AGENT_CONTRACTS.md` §2 step 0b
# applies to the author, applied to the reviewer.
#
# Usage: isolated-agy-review.sh <prompt-file> <allocated-path> [timeout-seconds] [plan-file]
#   <prompt-file>  path to the review prompt, RELATIVE TO THE REPO ROOT (e.g. .agy-prompt-2597r4.md)
#   <allocated-path>  exact reserved transcript leaf received from allocate-transcript.sh
# Exit: 0 review captured · 1 setup/prompt failure · 3 the reviewer MUTATED the working tree (round void)
set -uo pipefail

[ "$#" -ge 2 ] || { echo "usage: $0 <prompt-file> <allocated-path> [timeout]" >&2; exit 1; }
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
PLUGIN_WRITER="${SCRIPT_DIR}/../pty-capture.py"
PROMPT_REL="$1"
OUT="$2"
TIMEOUT="${3:-1800}"   # must EXCEED agy --print-timeout (28m=1680s) or the wrapper kills a live run
PLAN_REL="${4-}"       # optional: the plan the run is BOUND to (see the copy below)
# Reviewer model. Switched from gemini-3.1-pro to gemini-3.6-flash-high after that arm failed to emit a
# parseable verdict in 5 of 6 rounds (invented tokens REJECTED/PASS, two degenerations leaking
# system-prompt tokens, two runs that implemented the plan instead of reviewing it). Those are token-level
# and agent-mode failures, not reasoning failures — but they void rounds either way. `agy models` lists the
# valid names; the isolation harness and the $HOME leak monitor stay regardless of model, because the
# implement-instead-of-review failure comes from agy's agent mode, not from the model.
#
# For three months this comment described that switch while the line below still read
# `gemini-3.1-pro-high`, so every wrapper round ran the arm documented as failing (PR #63 review, item
# 8; deep review, P2). The default now matches the rationale, and `test_doc_gates` pins the two to each
# other so they cannot drift apart again. Replacing this arm entirely is planned separately
# (`docs/planning/KIMI_REVIEW_ARM_PLAN.md`) — a future plan is not a fix for the arm shipping today.
MODEL="${MODEL:-gemini-3.6-flash-high}"

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO="$PWD"
cd "$REPO" || exit 1
[ -r "$PROMPT_REL" ] || { echo "prompt not readable: $REPO/$PROMPT_REL" >&2; exit 1; }

SCR="$(mktemp -d)"
cleanup() {
    git worktree remove --force "$SCR/tree" >/dev/null 2>&1
    rm -rf "$SCR"
}
trap cleanup EXIT

# --- before: fingerprint the real tree --------------------------------------------------------
BEFORE="$(git status --porcelain)"

# --- disposable detached checkout at the exact reviewed commit --------------------------------
SHA="$(git rev-parse HEAD)"
git worktree add --detach "$SCR/tree" "$SHA" >/dev/null 2>&1 \
    || { echo "could not create the review checkout" >&2; exit 1; }
TREE="$SCR/tree"

# COPY THE BOUND PLAN INTO THE CHECKOUT. The tree above is detached at HEAD, so `agy` reads the
# COMMITTED plan — while `bind-prompt.py` hashed the WORKING-TREE plan into `<transcript>.plan`. With
# uncommitted edits, which is the normal state during the documented review iteration, the transcript
# approved the committed version and the artifact recorded it as evidence for the edited one: two
# correct digests describing different bytes (PR #63 recheck, P1).
#
# Copying rather than refusing keeps the iterate-then-review loop working, and it makes the binding
# TRUE rather than merely checkable — the reviewer now reads exactly the bytes the sidecar attests to.
if [ -n "$PLAN_REL" ]; then
    [ -r "$PLAN_REL" ] || { echo "plan not readable: $REPO/$PLAN_REL" >&2; exit 1; }
    mkdir -p "$(dirname "$TREE/$PLAN_REL")"
    cp "$PLAN_REL" "$TREE/$PLAN_REL" \
        || { echo "could not place the bound plan in the review checkout" >&2; exit 1; }
    if ! cmp -s "$PLAN_REL" "$TREE/$PLAN_REL"; then
        echo "the review checkout's plan does not match the bound plan" >&2; exit 1
    fi
fi

# --- rewrite absolute paths, then prepend the read-only guard ---------------------------------
mkdir -p "$(dirname "$TREE/$PROMPT_REL")"
sed "s#$REPO#$TREE#g" "$PROMPT_REL" > "$TREE/$PROMPT_REL"
if grep -q "$REPO" "$TREE/$PROMPT_REL"; then
    echo "prompt still references the real worktree after rewrite" >&2; exit 1
fi
python3 - "$TREE/$PROMPT_REL" <<'PY' || exit 1
import sys
p = sys.argv[1]
guard = ("READ-ONLY REVIEW — CONSTRAINT, NOT A TASK. You have READ access only: do NOT create, modify, "
         "delete or move any file, and do NOT implement any part of the plan. Producing the written "
         "review demanded by the instructions that follow is your ONLY deliverable. If you find "
         "yourself editing a file, stop — that is a failed review.\n"
         "The full task follows immediately below; read on.\n\n")
# READ FIRST. `open(p,'w')` truncates on open, so `open(p,'w').write(guard + open(p).read())` evaluates
# the truncating open BEFORE the read and silently yields a guard-only prompt. That wasted two review
# rounds: the reviewer replied "the file ends immediately after…", which reads like a wording problem.
body = open(p, encoding="utf-8").read()
assert body.strip(), f"refusing to write a guard-only prompt: {p} read back empty"
with open(p, "w", encoding="utf-8") as fh:
    fh.write(guard + body)
PY
# Fail in a second rather than after a 20-minute review on a truncated prompt.
BYTES="$(wc -c < "$TREE/$PROMPT_REL" | tr -d ' ')"
[ "$BYTES" -ge 1000 ] || { echo "assembled prompt is only ${BYTES} bytes — truncated" >&2; exit 1; }

# --- run --------------------------------------------------------------------------------------
# The reserved leaf must be EMPTY. It is created 0-byte by the allocator, and nothing but this
# capture may write it. A non-empty leaf means it has already been used, and reusing it is how a
# failed round gets reported as an approval: `--allocated` deliberately omits O_CREAT (to preserve
# the reservation), so before PR #63 it also omitted truncation, and a shorter second write left the
# first round's tail — including its `VERDICT:` line — for the `tail -1` below to find. Reproduced:
# a 19-byte failed round left 55 bytes reading `VERDICT: APPROVE`. pty-capture.py now ftruncates, so
# this is defence in depth; it also catches the case where the leaf was written by something else
# entirely. Refuse rather than clean: deleting the leaf would destroy the reservation, and silently
# overwriting would hide that the caller reused a path it should have re-allocated.
if [ -s "$OUT" ]; then
    echo "refusing to reuse a non-empty reserved leaf: $OUT" >&2
    echo "(it already holds $(wc -c < "$OUT" | tr -d ' ') bytes — allocate a fresh leaf for this round)" >&2
    exit 1
fi
# Preserve the allocator's reserved leaf for pty-capture.py --allocated to open.
( cd "$TREE" && python3 "$PLUGIN_WRITER" --timeout "$TIMEOUT" --allocated "$OUT" -- \
    agy --add-dir "$TREE" --model "$MODEL" --print-timeout 28m -p "Read and follow $TREE/$PROMPT_REL" ) >/dev/null 2>&1
RC=$?

# --- after: the assertion that would have caught COREDEV-2607 --------------------------------
AFTER="$(git status --porcelain)"
if [ "$BEFORE" != "$AFTER" ]; then
    echo "GATE FAILED — the reviewer MUTATED the working tree during the review:" >&2
    diff <(printf '%s\n' "$BEFORE") <(printf '%s\n' "$AFTER") >&2
    echo "(round is void — see COREDEV-2607)" >&2
    exit 3
fi

# Informational: what it wrote inside the disposable copy, which is discarded.
DIRTY="$(git -C "$TREE" status --porcelain 2>/dev/null | grep -v "$(basename "$PROMPT_REL")" || true)"
[ -n "$DIRTY" ] && { echo "NOTE: reviewer wrote inside the disposable checkout (discarded):"; printf '%s\n' "$DIRTY"; }

BYTES_OUT="$(wc -c < "$OUT" 2>/dev/null | tr -d ' ')"
# Anchored, never a loose `grep VERDICT:` — that matches the prompt's own echoed template in a
# timed-out transcript and reads as a real verdict.
VERDICT="$(grep -aE '^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$' "$OUT" 2>/dev/null | tail -1)"
echo "EXIT=$RC BYTES=${BYTES_OUT:-0} TREE=clean VERDICT=${VERDICT:-<none — FAILED REVIEW>}"
