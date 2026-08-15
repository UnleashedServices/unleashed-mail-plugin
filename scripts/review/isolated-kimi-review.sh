#!/usr/bin/env bash
# Run a Kimi (K3) plan review WITHOUT letting it write to the tree under review, and PROVE the
# reasoning effort it actually used.
#
# WHY THIS EXISTS AT ALL, AND WHY IN THE REPO
# An earlier copy of this harness ran for a whole campaign out of a session scratchpad under /tmp and
# was destroyed when the scratchpad was cleared, along with the plan validator. This repo already
# carries that lesson for review transcripts; a harness that gates a plan is at least as load-bearing,
# so it lives beside `isolated-agy-review.sh` and `isolated-codex-review.sh`.
#
# WHY ISOLATION
# `kimi` is an agent and can write. The defect this guards is COREDEV-2607: on 2026-07-29 a plan review
# IMPLEMENTED the plan instead of reviewing it — 6 shipped scripts modified, 5 files created. The
# reviewer therefore sees a DISPOSABLE detached checkout of the reviewed commit, and the real working
# tree is asserted unchanged afterwards. A mutation FAILS the round rather than being cleaned up.
#
# WHY THE EFFORT ASSERTION
# `--output-format stream-json` does NOT expose the effort a run used, and the config sets it in TWO
# places (a per-model `default_effort` and a global `[thinking] effort`), so a hand-edit to one is
# invisible. The tier a run really used is recorded in that session's wire log as `thinkingEffort`.
# A review whose tier cannot be asserted is not evidence about that tier, so this exits 4 rather than
# reporting a number it never verified.
#
# THE FAILURE MODES THIS ENCODES, EACH MEASURED ON THIS TICKET
#   * A round is VOID if the worktree changes during the review. Kimi's round-37 run tripped this
#     because the author committed while it was still reading — the harness was right and the author
#     was wrong. Hold tree edits until every arm has landed.
#   * Kimi reads the commit it is GIVEN. When a prompt pinned a stale commit, kimi noticed the
#     mismatch, trusted the pin over the working tree, and reviewed a three-round-old document. The
#     BASIS line below records what was staged; it does NOT prove what the reviewer chose to read.
#   * `EXIT=1` with a large transcript is usually the billing-cycle quota (a 403 in the tail), not a
#     review failure. Check the tail before treating it as one.
#
# Usage: isolated-kimi-review.sh <prompt-file> <out-transcript> <commit> [timeout-seconds]
#   <prompt-file>  path to the review prompt, RELATIVE TO THE REPO ROOT
#   <out-transcript>  where to write the transcript — NEVER under /tmp
# Exit: 0 captured · 1 setup failure · 3 round VOID (tree or staged basis mutated) · 4 effort unassertable
set -uo pipefail

[ "$#" -ge 3 ] || { echo "usage: $0 <prompt-file> <out-transcript> <commit> [timeout]" >&2; exit 1; }
PROMPT_REL="$1"; OUT="$2"; COMMIT="$3"; TIMEOUT="${4:-3300}"
PLAN_REL="docs/planning/COREDEV-2617_PLUGIN_STATE_BASE_DIR_PLAN.md"

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repo" >&2; exit 1; }
cd "$REPO" || exit 1
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
# THE PROMPT OPERAND IS CONTAINED — the shared helper proves it is a non-symlink regular file inside the
# repository and returns the resolved absolute path, which is the ONLY spelling used from here on. A bare
# `[ -r "$PROMPT_REL" ]` followed `../secret.txt` and an in-repo symlink to any readable file, and sent
# those bytes to the external reviewer as the prompt (codex, PR #67 pass 12).
PROMPT_ABS="$(python3 "${SCRIPT_DIR}/containment.py" --tool isolated-kimi-review --label prompt --absolute -- "$PROMPT_REL")" || exit 1
# THE PRIVATE SCRATCH DIRECTORY COMES FIRST — before the prompt snapshot it holds and before the live
# fingerprint below (a TMPDIR inside the repository would otherwise put a new untracked directory into
# AFTER that BEFORE never saw — the agy and codex harnesses create theirs first for the same reason).
TREE="$(mktemp -d "${TMPDIR:-/tmp}/kimi-review.XXXXXX")" || exit 1
cleanup() {
    rm -rf "$TREE" 2>/dev/null || :
}
trap cleanup EXIT INT TERM HUP

# BIND THE PROMPT NOW — before any fingerprint, ONCE, BYTE-PRESERVING. The prompt is a git-ignored
# file, so the live-tree fingerprint cannot see it change; reading it at LAUNCH time meant an edit
# made between the fingerprint and the launch reached the reviewer while the round read clean, and
# nothing recorded which bytes were reviewed (codex, PR #67 pass 9). The first fix captured the text
# and then HASHED THE SOURCE FILE THROUGH A SECOND OPEN — a change between the two left the reviewer
# with A and the digest describing B; and command substitution strips trailing newlines, so the file's
# digest never matched the argument the reviewer actually received (codex, PR #67 pass 10). So: ONE
# `cp` of the source into the private directory is the snapshot; the reviewer's argument is derived
# from that snapshot and nothing else; PROMPT= is the digest OF THE ARGUMENT BYTES; and after the run
# the source file is compared byte-for-byte with the snapshot — a prompt that changed underneath the
# round voids it, as the staged plan does, because the round's basis must survive the round.
PROMPT_SNAP="$TREE/prompt.snapshot"
cp -- "$PROMPT_ABS" "$PROMPT_SNAP" || { echo "prompt unreadable: $PROMPT_ABS" >&2; exit 1; }
PROMPT_TEXT="$(cat "$PROMPT_SNAP")"
[ -n "$PROMPT_TEXT" ] || { echo "prompt is empty: $REPO/$PROMPT_REL" >&2; exit 1; }
PROMPT_SHA="$(printf '%s' "$PROMPT_TEXT" | python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')"

# NOTHING IS CREATED BEFORE THE OPERAND IS CONTAINED. The parent used to be `mkdir -p`'d first, so a
# refused operand (`$REPO/new/nested/kimi.txt`, or a parent symlinked into the checkout or its .git)
# left its missing components created inside the protected tree before the refusal (codex, PR #67 pass
# 13). The physical path is computed WITHOUT creating anything — the nearest EXISTING ancestor is resolved
# with `cd -P`, the missing tail is re-appended — the refusals are applied to that, and only then is the
# parent created.
_out_dir="$(dirname -- "$OUT")"; _out_missing=""
while [ ! -d "$_out_dir" ]; do
    _out_missing="$(basename -- "$_out_dir")/$_out_missing"
    _out_parent="$(dirname -- "$_out_dir")"
    [ "$_out_parent" != "$_out_dir" ] || { echo "cannot resolve the transcript's parent: $OUT" >&2; exit 1; }
    _out_dir="$_out_parent"
done
OUT="$(CDPATH='' cd -P -- "$_out_dir" 2>/dev/null && pwd -P)/${_out_missing}$(basename -- "$OUT")" || exit 1
# OUT is made ABSOLUTE here, before any `cd`: the capture below runs inside the disposable
# checkout, so a relative path such as `.verdicts/kimi.txt` would land the transcript under the
# temporary worktree — where the later grep/wc could not find it, the run would end EFFORT=UNKNOWN
# / exit 4, and cleanup would delete the only capture (codex, PR #67).
# EVERY operand — relative OR absolute — has its parent resolved PHYSICALLY (`cd -P … && pwd -P`):
# an absolute `/repo/../../tmp/x` or a parent that is a symlink into /tmp did not match the guard
# below while the capture was physically written there (codex, PR #67 pass 10 — reproduced); the
# earlier fix normalised relative operands only, and with a logical `pwd`.
# (OUT is already physical — see the resolution above, which created nothing.)
# THE /tmp REFUSAL IS APPLIED TO THE PHYSICAL PATH — a relative operand with parent traversal
# (`../../tmp/kimi.txt`) does not match `/tmp/*` before normalisation and resolves to `/tmp/kimi.txt`
# after it, defeating the guard exactly where it matters (codex, PR #67). `pwd -P` also resolves
# `/tmp` -> `/private/tmp` on Darwin, so both spellings are covered.
case "$OUT" in
    /tmp/*|/private/tmp/*)
        echo "refusing to write the transcript under /tmp — macOS has destroyed campaign transcripts there" >&2
        exit 1 ;;
esac
# ...AND NEVER INSIDE THE LIVE CHECKOUT: the live fingerprint is taken before pty-capture creates or
# overwrites the transcript, so a capture written into the compared tree voids an otherwise clean round
# as a live-tree mutation the harness itself caused — and an operand naming a TRACKED file would be
# overwritten before the void was reported (codex, PR #67 pass 12). Physical prefix, physical repo.
REPO_P="$(CDPATH='' cd -P -- "$REPO" && pwd -P)" || exit 1
case "$OUT" in
    "$REPO_P"/*)
        echo "refusing to write the transcript inside the live checkout ($REPO_P) — it is the tree the round is compared against" >&2
        exit 1 ;;
esac
# Only NOW — every refusal has been applied to the physical operand — is the parent created.
mkdir -p "$(dirname -- "$OUT")" || exit 1

_sha256() { python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }
# shellcheck source=scripts/review/tree-fingerprint.sh
. "${SCRIPT_DIR}/tree-fingerprint.sh"

# Fingerprint the REAL tree before handing anything to the reviewer — CONTENT-AWARE, through the
# shared helper the agy and codex harnesses use, not a hash of `git status --porcelain` lines.
# A status-line hash cannot see a reviewer changing the CONTENT of a file that was already `M`
# when the harness started: BEFORE and AFTER stay identical and the round reads as clean. The
# helper includes `git diff HEAD` precisely for that case (PR #63 recheck, P1; codex, PR #67).
if ! BEFORE="$(tree_fingerprint "$REPO")"; then
    echo "GATE FAILED — could not fingerprint the live checkout before the review" >&2; exit 1
fi

# A PRIVATE clone of the reviewed commit — never a linked worktree, whose `.git` file points into the
# maintainer's real repository so every git operation the reviewer runs lands there (see
# disposable_checkout in tree-fingerprint.sh; adversarial verification, PR #67 pass 6).
SHA="$(git rev-parse --verify "${COMMIT}^{commit}" 2>/dev/null)" || {
    echo "not a commit: $COMMIT" >&2; exit 1; }
disposable_checkout "$REPO" "$SHA" "$TREE/tree" || {
    echo "could not build the private review checkout for $COMMIT" >&2; exit 1; }
[ -r "$TREE/tree/$PLAN_REL" ] || { echo "plan missing in the staged checkout" >&2; exit 1; }
BASIS="$(_sha256 "$TREE/tree/$PLAN_REL")"
# The disposable checkout's CONTENT fingerprint — every path, hashed — so that a reviewer which
# IMPLEMENTS the plan and leaves any file created or edited other than the plan itself voids the
# round. Checking only the plan's digest recreates the COREDEV-2607 failure the isolation exists to
# catch: the plan is untouched, the review looks clean, and six scripts have been rewritten beside it.
# NOT `git status`: that is metadata the reviewer controls (commit, assume-unchanged, a nested
# `.gitignore`, a repointed `.git`) — see disposable_fingerprint. FAIL CLOSED if the probe fails.
if ! TREE_BASELINE="$(disposable_fingerprint "$TREE/tree")"; then
    echo "GATE FAILED — could not fingerprint the disposable checkout before the review" >&2; exit 1
fi

# Through the repository's pty-capture.py --timeout, as the agy and codex harnesses are: `timeout`
# is GNU coreutils and is NOT on stock macOS, so a bare `timeout` exits 127 before Kimi starts and
# the harness captures nothing (codex, PR #67). The wrapper also owns the allocated transcript leaf.
PLUGIN_WRITER="${SCRIPT_DIR}/../pty-capture.py"
# No `--allocated`: this harness takes an <out-transcript> path it creates itself, not a leaf
# reserved by allocate-transcript.sh, and --allocated REQUIRES the leaf to pre-exist.
# THE SESSIONS THAT EXIST BEFORE THE RUN — the effort assertion below binds to the ONE session this
# invocation creates, by set difference, never to an identifier read out of the transcript.
SESSIONS_BEFORE="$(ls -d "$HOME"/.kimi-code/sessions/*/session_* 2>/dev/null | LC_ALL=C sort)"
( cd "$TREE/tree" && python3 "$PLUGIN_WRITER" --timeout "$TIMEOUT" "$OUT" -- \
    kimi -p "$PROMPT_TEXT" --output-format text ) >/dev/null 2>&1
STATUS=$?

# The prompt file must still be the bytes this round was launched with — compared byte-for-byte with
# the snapshot the reviewer's argument was derived from (PROMPT= on the summary line is that argument's digest).
if cmp -s -- "$PROMPT_ABS" "$PROMPT_SNAP" 2>/dev/null; then PROMPT_INTACT=1; else PROMPT_INTACT=0; fi

AFTER_BASIS="$(_sha256 "$TREE/tree/$PLAN_REL" 2>/dev/null || echo MISSING)"
if ! AFTER="$(tree_fingerprint "$REPO")"; then
    echo "GATE FAILED — could not fingerprint the live checkout after the review (round void)" >&2; exit 3
fi
# FAIL CLOSED if the post-review probe itself fails. `|| true` turned a failed `git status` — a
# reviewer that deleted or corrupted the disposable checkout's `.git` file and then wrote whatever it
# liked — into an EMPTY string, which equals a clean baseline, so all three mutation checks passed
# and the round certified arbitrary writes: precisely what this gate exists to reject (codex, PR #67).
# The probe no longer consults git at all, but a tree that cannot be READ is still not evidence.
if ! TREE_AFTER="$(disposable_fingerprint "$TREE/tree")"; then
    echo "ROUND VOID: the disposable checkout could not be re-read after the review — it is not evidence" >&2
    exit 3
fi

if [ "$BEFORE" != "$AFTER" ]; then
    echo "ROUND VOID: the real worktree was mutated during the review" >&2
    echo "  (if that was your own commit, the round is still void — hold edits until every arm lands)" >&2
    exit 3
fi
if [ "$BASIS" != "$AFTER_BASIS" ]; then
    echo "ROUND VOID: the reviewer modified the staged plan — COREDEV-2607 signature" >&2
    exit 3
fi
if [ "$PROMPT_INTACT" != 1 ]; then
    echo "ROUND VOID: the prompt file changed during the review — the round's basis did not survive it" >&2
    exit 3
fi
if [ "$TREE_BASELINE" != "$TREE_AFTER" ]; then
    echo "ROUND VOID: the reviewer left edits inside the disposable checkout — COREDEV-2607 signature" >&2
    printf '%s\n' "$TREE_BASELINE" | diff - <(printf '%s\n' "$TREE_AFTER") | sed 's/^/  /' >&2 || :
    exit 3
fi

# Effort assertion, from the wire log of THE SESSION THIS RUN CREATED — resolved from the session id
# the transcript itself carries, never from global mtime. The newest wire.jsonl on disk belongs to
# whichever Kimi session wrote last: a concurrent session, or an older one if this invocation died
# before creating its own — either would certify THIS review as `max` on another session's evidence.
# No session id in the transcript means no evidence, and the assertion fails closed below.
# BOUND TO THE SESSION CREATED DURING THIS INVOCATION — the set difference of session directories
# before and after the run — and to nothing read out of the transcript: the earlier "first
# `session_<uuid>` in the transcript" was reviewer-controlled text, so a run whose output QUOTED an older
# session's id (a resume hint, an old transcript) selected that session's wire log and could certify
# this run as `max` on another run's evidence (codex, PR #67 pass 11). Exactly ONE new session is the
# only shape that is evidence; zero (the CLI created none) or several (a concurrent run) fail closed.
SESSIONS_AFTER="$(ls -d "$HOME"/.kimi-code/sessions/*/session_* 2>/dev/null | LC_ALL=C sort)"
NEW_SESSIONS="$(printf '%s\n' "$SESSIONS_AFTER" | grep -vxF -- "$SESSIONS_BEFORE" | grep -v '^$' || true)"
WIRE=""
if [ "$(printf '%s\n' "$NEW_SESSIONS" | grep -c .)" = 1 ]; then
    _w="$NEW_SESSIONS/agents/main/wire.jsonl"
    [ -r "$_w" ] && WIRE="$_w"
fi
EFFORTS=""
[ -n "$WIRE" ] && EFFORTS="$(grep -o '"thinkingEffort":"[a-z]*"' "$WIRE" 2>/dev/null \
    | sed 's/.*:"//;s/"//' | LC_ALL=C sort -u | tr '\n' ',')"

printf 'EXIT=%s BYTES=%s TREE=clean BASIS=%s PROMPT=%s EFFORT=%s\n' \
    "$STATUS" "$(wc -c < "$OUT" | tr -d ' ')" "${BASIS:0:12}" "${PROMPT_SHA:0:12}" "${EFFORTS:-UNKNOWN}"

if [ "$EFFORTS" != "max," ]; then
    echo "EFFORT NOT ASSERTED AS max (saw: ${EFFORTS:-none}) — this run is not evidence about max" >&2
    exit 4
fi
exit "$STATUS"
