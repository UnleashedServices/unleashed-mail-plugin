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
# Exit: 0 review captured · 1 setup/prompt failure · 3 round VOID — the reviewer mutated the working
#       tree, modified the round's staged basis (plan or prompt) inside the disposable checkout, or
#       wrote anything else there (a reviewer in agent mode is the COREDEV-2607 signature)
set -uo pipefail

_sha256() { python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }

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
# CAPTURED BEFORE THE `cd`. `bind-prompt.py` accepted the plan operand relative to the CALLER'S
# directory; this script then changed to the repository root and reinterpreted the same string there,
# so a plan the binder had just accepted became unreadable here (PR #63 recheck, P2 — see the
# resolution below).
CALLER_PWD="$PWD"
cd "$REPO" || exit 1
[ -r "$PROMPT_REL" ] || { echo "prompt not readable: $REPO/$PROMPT_REL" >&2; exit 1; }

# Repo-relative identity of $1 interpreted against base $2, or non-zero if it does not exist there or
# resolves outside the repository. Only the PARENT is resolved through `pwd -P`: a symlinked leaf must
# still reach the readability check rather than be laundered into a clean-looking relative path here.
resolve_in_repo() {
    local candidate="$1" base="$2" parent leaf
    case "$candidate" in /*) ;; *) candidate="$base/$candidate" ;; esac
    [ -e "$candidate" ] || return 1
    parent="$(CDPATH='' cd -- "$(dirname -- "$candidate")" 2>/dev/null && pwd -P)" || return 1
    leaf="$parent/$(basename -- "$candidate")"
    case "$leaf" in
        "$REPO"/*) printf '%s\n' "${leaf#"$REPO"/}" ;;
        *) return 1 ;;
    esac
}

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
    # NORMALIZE AGAINST THE CALLER, THEN THE ROOT. Two spellings reached this line and each broke a
    # different way:
    #   * an ABSOLUTE in-repo path pasted into "$TREE/$PLAN_REL" built a nested destination like
    #     `$TREE/Users/…/docs/planning/X.md` while the rewritten prompt still pointed `agy` at
    #     `$TREE/docs/planning/X.md`, so the copy landed where the reviewer never looks and it read the
    #     COMMITTED plan again — the very defect the copy was added to fix; and
    #   * a CALLER-RELATIVE path such as `../docs/planning/X_PLAN.md` passed from `scripts/`, which
    #     `bind-prompt.py` had already accepted, died here as "plan not readable" because this script had
    #     `cd`'d to the root first. Reproduced from `scripts/` (PR #63 recheck, P2).
    #
    # Caller-relative is tried FIRST because the binder is the authority on what was bound. Root-relative
    # stays as a fallback so callers that pass a root-relative path from a subdirectory keep working, and
    # the ambiguous case — both exist and name DIFFERENT files — is refused rather than silently resolved
    # to whichever branch happens to be tested first.
    PLAN_OPERAND="$PLAN_REL"
    FROM_CALLER="$(resolve_in_repo "$PLAN_OPERAND" "$CALLER_PWD")" || FROM_CALLER=""
    FROM_ROOT="$(resolve_in_repo "$PLAN_OPERAND" "$REPO")" || FROM_ROOT=""
    if [ -n "$FROM_CALLER" ] && [ -n "$FROM_ROOT" ] && [ "$FROM_CALLER" != "$FROM_ROOT" ]; then
        echo "ambiguous plan operand: '$PLAN_OPERAND' names $FROM_CALLER from the caller's directory" >&2
        echo "and $FROM_ROOT from the repository root — pass an absolute path" >&2
        exit 1
    fi
    PLAN_REL="${FROM_CALLER:-$FROM_ROOT}"
    [ -n "$PLAN_REL" ] \
        || { echo "plan not readable, or outside the repository: $PLAN_OPERAND" >&2; exit 1; }
    [ -r "$PLAN_REL" ] || { echo "plan not readable: $REPO/$PLAN_REL" >&2; exit 1; }
    # The staging destination is built by a DESCRIPTOR WALK inside the python below, not a `mkdir -p` +
    # `open("$TREE/$PLAN_REL")`. `git worktree add --detach` MATERIALIZES committed tree entries — so if
    # HEAD records the plan path as a SYMLINK (or any parent as one), the checkout recreates that link,
    # and a plain open followed it to overwrite an outside victim. Reproduced: HEAD carries
    # `docs/planning/X_PLAN.md -> /outside/victim`, the live worktree replaces it with a real plan, and
    # staging clobbered the victim (PR #63 recheck, P1). Every component is now opened O_NOFOLLOW and
    # the leaf is unlinked-then-O_EXCL-created, so no symlink is ever traversed.
    # STAGE THE BINDER'S SNAPSHOT, not the live path. `bind-prompt.py` kept the exact bytes it hashed
    # in `<transcript>.planbytes`; copying the working-tree path instead re-read a mutable source, so a
    # plan edited after binding and restored before synthesis could reach the reviewer while both the
    # sidecar and the final digest described the restored bytes. The old `cmp` re-opened that same path
    # and so proved only that two reads agreed at copy time (PR #63 recheck, P1).
    PLAN_SNAPSHOT="${OUT}.planbytes"
    if [ -r "$PLAN_SNAPSHOT" ]; then
        # AUTHENTICATE THE SNAPSHOT AGAINST ITS RECORD, and deliver the bytes that were authenticated.
        # `cp` followed by `cmp` compared the snapshot only with its own copy: a same-account process
        # rewriting `.planbytes` between the binder returning and this staging was read by BOTH, so the
        # comparison passed and `agy` reviewed substituted bytes. Nothing downstream caught it either —
        # `review-verdict.py` validates the `.plan` RECORD against the live plan and never hashes
        # `.planbytes` — so that review could approve the original plan (PR #63 recheck, P1).
        #
        # This is the fifth "recorded and never compared" on this branch: `.plan` carried the digest of
        # these exact bytes the whole time and nothing read it. One descriptor, read once, hashed and
        # written — so the bytes the reviewer receives are provably the bytes the record attests to,
        # with no second open to race.
        #
        # The authenticated digest is CAPTURED, because the round is not done with it: the post-run
        # basis check below re-verifies the staged copy against this value, which is what catches a
        # reviewer that rewrites the plan mid-review (PR #63 recheck, P1 — see below).
        EXPECTED_PLAN_SHA="$(python3 - "$PLAN_SNAPSHOT" "${OUT}.plan" "$TREE" "$PLAN_REL" <<'PY'

import hashlib
import os
import stat
import sys

snapshot, record, tree_root, rel = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]


def read_nofollow(path: str, label: str) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        sys.exit(f"cannot read the {label}: {path}: {error}")
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            sys.exit(f"the {label} is not a regular file: {path}")
        parts = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            parts.append(chunk)
    finally:
        os.close(fd)
    return b"".join(parts)


def stage_no_follow(tree_root: str, rel: str, payload: bytes) -> None:
    """Write `payload` to tree_root/rel, refusing to traverse ANY symlink component.

    `git worktree add --detach` recreates committed symlinks, so neither the leaf nor a parent can be
    trusted to be a real path just because we made the tree. Every directory is opened
    O_DIRECTORY|O_NOFOLLOW relative to the previous one (a symlinked parent fails ELOOP), and the leaf
    is unlinked-without-following then created O_CREAT|O_EXCL|O_NOFOLLOW — so a materialized symlink
    leaf is removed as a link, never written through.
    """
    components = [c for c in rel.split("/") if c and c != "."]
    if not components or ".." in components:
        sys.exit(f"refusing an unsafe staging path: {rel}")
    dir_fd = os.open(tree_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for comp in components[:-1]:
            try:
                os.mkdir(comp, 0o755, dir_fd=dir_fd)
            except FileExistsError:
                pass
            next_fd = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = next_fd
        leaf = components[-1]
        try:
            os.unlink(leaf, dir_fd=dir_fd)   # never follows; removes a materialized symlink as a link
        except FileNotFoundError:
            pass
        fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
        try:
            written = 0
            while written < len(payload):
                written += os.write(fd, payload[written:])
        finally:
            os.close(fd)
    finally:
        os.close(dir_fd)


payload = read_nofollow(snapshot, "bound plan snapshot")
fields = read_nofollow(record, "plan binding record").decode("utf-8", "replace").split()
if not fields:
    sys.exit(f"the plan binding record is empty, so the snapshot cannot be authenticated: {record}")
expected, actual = fields[0], hashlib.sha256(payload).hexdigest()
if actual != expected:
    sys.exit(
        "the bound plan snapshot does not match its recorded digest — refusing to review substituted "
        f"bytes: {snapshot} hashes {actual[:12]}…, {record} records {expected[:12]}…"
    )
stage_no_follow(tree_root, rel, payload)
print(actual)
PY
)" || exit 1
    else
        # No snapshot: an older capture, or a direct call. Fall back to the live path and SAY SO, rather
        # than silently accepting the weaker guarantee. Still staged through the SAME no-follow descriptor
        # walk — the symlink-leaf escape does not depend on where the bytes came from. The digest of what
        # was ACTUALLY staged anchors the post-run basis check — weaker provenance, same integrity.
        echo "note: no bound plan snapshot beside the transcript; staging the working-tree plan" >&2
        EXPECTED_PLAN_SHA="$(python3 - "$PLAN_REL" "$TREE" "$PLAN_REL" <<'PY'
import hashlib
import os
import stat
import sys

live, tree_root, rel = sys.argv[1], sys.argv[2], sys.argv[3]


def read_nofollow(path: str) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            sys.exit(f"the plan is not a regular file: {path}")
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


def stage_no_follow(tree_root: str, rel: str, payload: bytes) -> None:
    components = [c for c in rel.split("/") if c and c != "."]
    if not components or ".." in components:
        sys.exit(f"refusing an unsafe staging path: {rel}")
    dir_fd = os.open(tree_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for comp in components[:-1]:
            try:
                os.mkdir(comp, 0o755, dir_fd=dir_fd)
            except FileExistsError:
                pass
            next_fd = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = next_fd
        leaf = components[-1]
        try:
            os.unlink(leaf, dir_fd=dir_fd)
        except FileNotFoundError:
            pass
        fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
        try:
            written = 0
            while written < len(payload):
                written += os.write(fd, payload[written:])
        finally:
            os.close(fd)
    finally:
        os.close(dir_fd)


payload = read_nofollow(live)
stage_no_follow(tree_root, rel, payload)
print(hashlib.sha256(payload).hexdigest())
PY
)" || { echo "could not place the bound plan in the review checkout" >&2; exit 1; }
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
# The assembled prompt is basis too: verified after the run exactly like the staged plan.
PROMPT_TREE_SHA="$(_sha256 "$TREE/$PROMPT_REL")" || exit 1

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
# The baseline: everything the HARNESS put in the tree (the prompt, the staged plan). Anything beyond
# this after the run is the reviewer's doing.
TREE_BASELINE="$(git -C "$TREE" status --porcelain 2>/dev/null || true)"

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

# THE ROUND'S BASIS MUST SURVIVE THE ROUND (PR #63 recheck, P1). A reviewer that rewrote the staged
# plan and then emitted `VERDICT: APPROVE` produced a valid-looking capture of a review of DIFFERENT
# bytes, while synthesis validates only the `.plan` record against the live plan — which nobody
# touched. And the status diff below could not even SEE it: `git status --porcelain` is STATUS-line
# based, and the staged plan is already `M` in the baseline, so re-modifying its content changes
# nothing the diff compares. Reproduced both ways. So the basis files are verified by CONTENT against
# the digests recorded before launch — the same digest the `.plan` record attests to, now checked at a
# third point in the round's life.
if [ -n "$PLAN_REL" ]; then
    ACTUAL_PLAN_SHA="$(_sha256 "$TREE/$PLAN_REL" 2>/dev/null)" || ACTUAL_PLAN_SHA="unreadable"
    if [ "$ACTUAL_PLAN_SHA" != "$EXPECTED_PLAN_SHA" ]; then
        { echo "GATE FAILED — the STAGED PLAN was modified during the review (round void):"
          echo "(staged ${EXPECTED_PLAN_SHA}, post-run ${ACTUAL_PLAN_SHA} — the transcript reviewed"
          echo "bytes the binding does not attest to; see COREDEV-2607 for why this voids the round)"; } >&2
        exit 3
    fi
fi
ACTUAL_PROMPT_SHA="$(_sha256 "$TREE/$PROMPT_REL" 2>/dev/null)" || ACTUAL_PROMPT_SHA="unreadable"
if [ "$ACTUAL_PROMPT_SHA" != "$PROMPT_TREE_SHA" ]; then
    echo "GATE FAILED — the assembled PROMPT was modified during the review (round void)" >&2
    exit 3
fi
# ANY other write inside the disposable copy voids the round too — no longer a note. Writing files is
# the COREDEV-2607 signature (a reviewer in agent mode, implementing instead of reviewing), and a
# review produced that way is untrustworthy whether or not the copy is discarded afterwards. The
# earlier informational form existed because comparing against HEAD reported the HARNESS'S OWN staged
# input as a reviewer write — a detector that cries wolf on its own inputs is one nobody reads. That
# concern is solved by the POST-STAGING BASELINE, not by softening the verdict: everything the harness
# placed is in the baseline, so anything beyond it is the reviewer's doing, and it fails the round.
# (The old form also excluded the prompt's basename from the diff — which would have HIDDEN a reviewer
# tampering with any file sharing that name. The content checks above cover the prompt now.)
TREE_AFTER="$(git -C "$TREE" status --porcelain 2>/dev/null || true)"
DIRTY="$(printf '%s\n' "$TREE_AFTER" | grep -vxF -- "$TREE_BASELINE" || true)"
if [ -n "$DIRTY" ]; then
    { echo "GATE FAILED — the reviewer WROTE inside the disposable checkout (round void — agent-mode"
      echo "behaviour, the COREDEV-2607 signature):"
      printf '%s\n' "$DIRTY"; } >&2
    exit 3
fi

BYTES_OUT="$(wc -c < "$OUT" 2>/dev/null | tr -d ' ')"
# Anchored, never a loose `grep VERDICT:` — that matches the prompt's own echoed template in a
# timed-out transcript and reads as a real verdict.
VERDICT="$(grep -aE '^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$' "$OUT" 2>/dev/null | tail -1)"
echo "EXIT=$RC BYTES=${BYTES_OUT:-0} TREE=clean VERDICT=${VERDICT:-<none — FAILED REVIEW>}"
# RETURN IT. The status was captured in `RC` and then thrown away by the successful `echo` above, so a
# stub exiting 23 printed `EXIT=23 … FAILED REVIEW` while this script — and `capture-gemini-review.sh`
# with it — reported success. The caller then could not tell a completed review from an auth, model or
# timeout failure, which is exactly the distinction the gate depends on (PR #63 recheck, P2). The
# mutation detector above keeps its own separate exit path; this only propagates the CAPTURE status.
exit "$RC"
