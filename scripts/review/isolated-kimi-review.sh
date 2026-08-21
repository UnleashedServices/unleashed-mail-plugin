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
# reporting a number it never verified. SCOPE, stated once here and again at the assertion: that log
# sits inside the reviewed process's own writable session tree, so the tier is SELF-REPORTED — it
# defends against a run that quietly used the default tier, not against a reviewer that lies about it.
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
# Usage: isolated-kimi-review.sh <prompt-file> <out-transcript> <commit> [timeout-seconds] [plan]
#   <prompt-file>  path to the review prompt, RELATIVE TO THE REPO ROOT
#   <out-transcript>  where to write the transcript — NEVER under /tmp
#   [plan]  repo-relative plan to stage and basis-check (default: the COREDEV-2617 plan this harness
#           was built for). PASS YOUR PLAN when reviewing anything else — the basis check asserts the
#           integrity of the plan named HERE, not of whatever the prompt talks about, so a defaulted
#           plan under a different prompt certifies the wrong document (2026-08-17 audit, AF-12).
# Exit: 0 captured · 1 setup failure · 3 round VOID (tree or staged basis mutated) · 4 effort unassertable
set -uo pipefail

[ "$#" -ge 3 ] || { echo "usage: $0 <prompt-file> <out-transcript> <commit> [timeout] [plan]" >&2; exit 1; }
PROMPT_REL="$1"; OUT="$2"; COMMIT="$3"; TIMEOUT="${4:-3300}"
# `${5-...}`, NOT `${5:-...}`: the colon form substitutes the default for an EXPLICITLY EMPTY
# operand too, so the `""` arm below was DEAD and an empty model-supplied operand silently
# certified the default plan — the exact mismatch this guard exists to prevent (codex, PR #69).
PLAN_REL="${5-docs/planning/COREDEV-2617_PLUGIN_STATE_BASE_DIR_PLAN.md}"
# THE PLAN OPERAND IS CONTAINED TOO. It was not, and it is model-chosen: `codex-review/SKILL.md`
# says the stand-in is invoked "always passing <plan>". Unlike the prompt four lines below it went
# straight into `$TREE/tree/$PLAN_REL`, so `../../etc/passwd` or an absolute path made the round's
# printed BASIS digest certify bytes OUTSIDE the reviewed commit — the exact class the prompt
# operand's containment exists to stop. The spelling is checked here (the staged checkout does not
# exist yet); the OBJECT is re-checked against $TREE/tree below, because a spelling that cannot
# escape is not the same claim as a file that is not a symlink.
case "$PLAN_REL" in
    /*)        echo "plan operand must be repository-relative, not absolute: $PLAN_REL" >&2; exit 1 ;;
    ..|../*|*/..|*/../*) echo "plan operand must not traverse upward: $PLAN_REL" >&2; exit 1 ;;
    "")        echo "plan operand must not be empty" >&2; exit 1 ;;
esac
# A NEWLINE in the operand forged a multiline "BASIS plan = ..." diagnostic, so the printed basis
# could claim one plan while the digest covered another (codex, PR #69). Refuse any control byte.
case "$PLAN_REL" in
    *[[:cntrl:]]*) echo "plan operand must not contain control characters" >&2; exit 1 ;;
esac
# Name the basis-checked plan LOUDLY so a stand-in round (e.g. kimi covering a codex quota outage)
# cannot silently basis-check the default while the prompt reviews something else.
printf 'kimi-review: BASIS plan = %s\n' "$PLAN_REL" >&2

# GIT'S REPOSITORY-SELECTION ENVIRONMENT IS CLEARED BEFORE ANY git RUNS (codex, PR #69 round 2).
# `git -C "$REPO"` does NOT anchor the repository: with `GIT_DIR` and `GIT_WORK_TREE` inherited,
# `--show-toplevel` still answers THIS checkout while every object lookup resolves in ANOTHER
# repository — measured, `cat-file blob HEAD:README.md` returned a different digest entirely. That
# matters here because the BASIS is now read from git objects, so a poisoned environment would let
# the round certify bytes from a repository nobody reviewed. Unsetting is done once, at the top,
# before the first `git` call, so no later command can be the first to see a stale value.
# EVERY `GIT_*` VARIABLE IS CLEARED, not a hand-picked list. Naming them one at a time was wrong
# twice over: the first list covered repository SELECTION and missed configuration INJECTION, and
# `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` are UNBOUNDED, so no fixed list can be
# complete. Measured: with those three set, `core.hooksPath` survived the old unset block
# (`git config --show-origin core.hooksPath` -> `command line: /attacker/hooks`), which means
# `disposable_checkout`'s `git checkout` would run an attacker `post-checkout` INSIDE the private
# tree BEFORE `TREE_BASELINE` is captured — mutation the baseline then treats as pristine
# (codex, PR #69 round 3). Enumerating the environment and clearing the whole namespace is the only
# form of this that cannot be outrun by a variable someone adds later.
# ...AND THE SHARED BOUNDARY IS SOURCED BEFORE THE FIRST `git`, not after it. This script used to
# carry its own copy of the clearing loop here and source tree-fingerprint.sh two hundred lines
# later, which meant the claim "all four consumers source the boundary before their first git call"
# was FALSE for this one (codex, PR #69 round 7). SCRIPT_DIR is therefore established here rather
# than further down, and sourcing runs `_tf_sanitize_git_env`, which fails CLOSED.
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=scripts/review/tree-fingerprint.sh
. "${SCRIPT_DIR}/tree-fingerprint.sh"
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repo" >&2; exit 1; }
# ...and the gitdir must belong to the checkout we just resolved, so a future edit that reintroduces
# an inherited selection variable fails loudly instead of silently reading elsewhere.
_REPO_GITDIR="$(git -C "$REPO" rev-parse --absolute-git-dir 2>/dev/null)" || {
    echo "could not resolve the gitdir for $REPO" >&2; exit 1; }
case "$_REPO_GITDIR" in
    "$REPO"/.git|"$REPO"/.git/*) : ;;
    *) # a linked worktree's gitdir lives under the MAIN repo, which is legitimate; prove the link
       _MAIN_TOP="$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
       case "$_REPO_GITDIR" in
           "${_MAIN_TOP%/.git}"/.git/worktrees/*|"$_MAIN_TOP"/worktrees/*) : ;;
           *) echo "gitdir $_REPO_GITDIR does not belong to $REPO — refusing" >&2; exit 1 ;;
       esac ;;
esac
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
# A NUL IN THE PROMPT IS REFUSED AT THE SOURCE, exactly as `bind-prompt.py` already does for the
# plan skills. Command substitution SILENTLY DELETES NULs, so the reviewer receives different bytes
# than PROMPT_SHA digests — the binding says one thing and the transport delivers another
# (codex, PR #69 round 14 at effort=max: documented_expected_len=91 bash_argv_len=90,
# bytes_equal=False). Refused here rather than escaped at the call site: a review prompt containing
# a NUL is never legitimate, and every transport added later would otherwise need its own defence.
# Detected in python3, NOT with a shell pattern: bash cannot hold a NUL in a variable, so the
# obvious `grep -q $'\000'` compiles to an EMPTY pattern that matches every file — a guard that
# refuses everything and detects nothing. (Written that way first here; the control caught it.)
if python3 -c 'import sys; sys.exit(0 if b"\x00" in open(sys.argv[1],"rb").read() else 1)' "$PROMPT_SNAP"; then
    echo "prompt contains a NUL byte, which shell command substitution deletes — the reviewer would" >&2
    echo "receive different bytes than are being bound: $PROMPT_REL" >&2
    exit 1
fi
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
# The `|| exit 1` used to sit on THIS assignment and was inert: for an assignment the status is that of
# the LAST command substitution, which was `basename` — it succeeds even when the `cd -P` before it
# failed, so an unenterable parent silently re-rooted OUT at `/` and the reviewer was launched anyway
# (codex sweep, PR #67 pass 14 — reproduced). The physical prefix is captured and tested on its own.
_out_base="$(CDPATH='' cd -P -- "$_out_dir" 2>/dev/null && pwd -P)" || _out_base=""
[ -n "$_out_base" ] || { echo "cannot enter the transcript's physical parent: $_out_dir" >&2; exit 1; }
OUT="$_out_base/${_out_missing}$(basename -- "$OUT")"
# ...AND THE RESULT IS NORMALISED LEXICALLY. The re-appended missing tail was kept verbatim, so
# `/x/missing/../repo/f` stopped at `/x`, retained `missing/..`, passed the repository-prefix check
# below — and `mkdir -p` then created `missing` and resolved the write INTO the live checkout: a tracked
# file was overwritten before the post-run fingerprint reported it (codex, PR #67 pass 14 — reproduced).
# No component of the missing tail exists, so collapsing `.` and `..` lexically is exactly what the
# kernel does after the mkdir, and the existing prefix is already physical.
# NORMALISED, AND A LEADING `//` COLLAPSED. POSIX leaves a path beginning with exactly two slashes
# implementation-defined and `os.path.normpath` PRESERVES it, so when the nearest existing ancestor was
# `/` the reconstruction produced `//tmp/x` or `//<repo>/tracked` — neither of which matches the `/tmp/*`
# or `"$REPO_P"/*` refusals below, while the kernel resolves them to exactly those places (codex sweep,
# PR #67 pass 14 — reproduced: a tracked file was overwritten). Both refusals are applied to this value.
OUT="$(python3 -c 'import os, re, sys; print(re.sub(r"^//+", "/", os.path.normpath(sys.argv[1])))' "$OUT")" || exit 1
# The reconstruction is only meaningful if it produced an absolute path; anything else means a step
# above failed and the refusals below would be testing a relative string.
case "$OUT" in /*) : ;; *) echo "cannot resolve the transcript's physical path: $OUT" >&2; exit 1 ;; esac
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
# THE BASIS IS DIGESTED FROM THE GIT OBJECT, NOT FROM A PATH IN THE CHECKOUT (codex, PR #69).
# Filesystem tests on `$TREE/tree/$PLAN_REL` cannot establish what this digest has to mean, which
# is "these bytes are in the reviewed commit". Three ways they failed, each reproduced:
#   * `-L`/`-f`/`-r` all PASS for `.git/config` — `disposable_checkout` uses `git init`, so that
#     path exists in the staged tree and is not a commit object at all;
#   * `-L` tests only the LEAF, so an INTERMEDIATE symlinked component (`escape -> /outside`,
#     committed in the tree) is followed straight out of the checkout;
#   * containment of the spelling says nothing about what the kernel resolves.
# `git cat-file` answers the actual question. The mode check keeps a committed SYMLINK (mode
# 120000, whose blob content is its target path) from being digested as though it were the plan.
PLAN_MODE="$(git -C "$REPO" ls-tree --format='%(objectmode)' "$SHA" -- "$PLAN_REL" 2>/dev/null)"
case "$PLAN_MODE" in
    100644|100755) : ;;
    "")  echo "plan is not tracked in the reviewed commit $SHA: $PLAN_REL" >&2; exit 1 ;;
    120000) echo "plan is a symlink in the reviewed commit: $PLAN_REL" >&2; exit 1 ;;
    *)   echo "plan is not a regular file in the reviewed commit (mode $PLAN_MODE): $PLAN_REL" >&2; exit 1 ;;
esac
# THE PROMPT MUST DECLARE THE DOCUMENT THE BASIS CERTIFIES, ANCHORED.
# A substring test was not enough and was bypassed four ways (codex, PR #69 round 3): a `.bak`
# suffix, an `old-` path prefix, the path quoted inside a sentence that then says "actual review:
# README.md", and a prompt naming TWO documents. Proving the operand appears SOMEWHERE says nothing
# about what the reviewer was told to read. So: exactly ONE declaration line, and its whole value
# must equal the operand — the same boundary-aware shape `bind-prompt.py` enforces for the plan
# skills, rather than a second, weaker copy of that rule.
_BIND_RC=0
PLAN_REL="$PLAN_REL" python3 - "$PROMPT_SNAP" <<'PYBIND' || _BIND_RC=$?
import os, sys
want = os.environ["PLAN_REL"]
raw = open(sys.argv[1], "rb").read()

# A RIGID FORMAT, NOT A MARKDOWN PARSER.
# Four rounds were spent hardening a prose scanner and it lost every time: substring match, then
# fenced quotation, then fence length and trailing text, then list containers, HTML comments and
# space-then-tab indentation — and that last set included a REFUSE -> ACCEPT regression, where
# blanking merged two raw declarations into one acceptable one. Deciding which prose is "operative"
# means reimplementing CommonMark, and a partial CommonMark is a bypass generator.
#
# So the declaration is not searched for. It IS the first line, byte-exactly:
#
#     Plan under review: <repo-relative path>
#
# No leading whitespace, no quoting, no alternate keyword, nothing before it. Every other byte in
# the prompt is free text this check never inspects, so no construct anywhere in the body can forge,
# hide or duplicate a declaration.
#
# SCOPE, STATED PLAINLY. This binds the DECLARATION to the BASIS: they cannot disagree, and the
# declaration cannot be forged by formatting. It does NOT police the BODY, and deliberately so —
# a prompt whose first line declares A and whose prose then discusses B is ACCEPTED, because the
# BASIS honestly certifies A. Two cases that the old scanner refused are therefore accepted now,
# and that is the correct answer under this property rather than a regression: what the reviewer
# chooses to read has never been knowable from here, which is exactly what the BASIS line's own
# header comment has said since round 1. Policing prose was the thing that kept failing.
PREFIX = b"Plan under review: "
first = raw.split(b"\n", 1)[0]
if first.endswith(b"\r"):
    first = first[:-1]
if not first.startswith(PREFIX):
    sys.stderr.write("the prompt's FIRST line must be exactly:\n  Plan under review: %s\n"
                     "(found: %r)\n" % (want, first[:120].decode("utf-8", "replace")))
    raise SystemExit(1)
# COMPARED AS BYTES, because "byte-exact" was not true of the previous version (codex, PR #69
# round 7): `.decode("utf-8", "replace")` maps ANY invalid byte to U+FFFD, so `\xff` aliased a real
# U+FFFD filename and was accepted as the same declaration; and `.rstrip()` accepted extra trailing
# spaces while making a tracked filename that ENDS in a space impossible to declare. Only the
# intentional CRLF handling above touches the bytes; nothing else is normalised.
declared = first[len(PREFIX):]
want_bytes = os.fsencode(want)
if declared != want_bytes:
    sys.stderr.write("the prompt declares %r but the BASIS would certify %r — refusing to review one "
                     "document and certify another\n"
                     % (declared.decode("utf-8", "backslashreplace"), want))
    raise SystemExit(1)
PYBIND
[ "$_BIND_RC" = 0 ] || exit 1
BASIS="$(git -C "$REPO" cat-file blob "$SHA:$PLAN_REL" \
    | python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')" || {
    echo "could not digest the plan blob from $SHA" >&2; exit 1; }
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
# reserved by allocate-transcript.sh, and --allocated REQUIRES the leaf to pre-exist. THAT IS WHY
# IT IS NOT GRANTED to the codex-review skill: a pre-approved `Bash(... isolated-kimi-review.sh *)`
# let a nominally read-only review skill create-and-truncate an ARBITRARY single-linked user file
# with no further prompt (codex, PR #69 — reproduced under ~/Documents with the write mocked). The
# fix is at the permission layer: the stand-in is invoked with explicit per-round approval until a
# `capture-kimi-review.sh` exists that owns its allocation, as agy and codex have.
# THE SESSIONS THAT EXIST BEFORE THE RUN — the effort assertion below binds to the ONE session this
# invocation creates, by set difference, never to an identifier read out of the transcript.
SESSIONS_BEFORE="$(ls -d "$HOME"/.kimi-code/sessions/*/session_* 2>/dev/null | LC_ALL=C sort)"
( cd "$TREE/tree" && python3 "$PLUGIN_WRITER" --timeout "$TIMEOUT" "$OUT" -- \
    kimi -p "$PROMPT_TEXT" --output-format text ) >/dev/null
STATUS=$?

# The prompt file must still be the bytes this round was launched with — compared byte-for-byte with
# the snapshot the reviewer's argument was derived from (PROMPT= on the summary line is that argument's digest).
if cmp -s -- "$PROMPT_ABS" "$PROMPT_SNAP" 2>/dev/null; then PROMPT_INTACT=1; else PROMPT_INTACT=0; fi

AFTER_BASIS="$(git -C "$REPO" cat-file blob "$SHA:$PLAN_REL" 2>/dev/null \
    | python3 -c 'import hashlib,sys; d=sys.stdin.buffer.read(); print(hashlib.sha256(d).hexdigest() if d else "MISSING")' \
    || echo MISSING)"
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
# EXACTLY ONE NEW SESSION IS NOT PROOF THAT IT IS OURS. The set difference cannot tell a session
# THIS invocation created from one a CONCURRENT foreign `kimi` created in the same window: with the
# reviewer creating none and a stranger creating one, the difference is still exactly one and its
# wire log was read and reported as this round's effort (codex, PR #69 round 15 — reproduced:
# `reviewer_sessions_created=0 foreign_sessions_created=1 would_pass_max_gate=yes`).
#
# The cheap half is closable and is closed here: if THIS capture produced no bytes, the reviewer did
# not run, so no new session can be ours and none is selected. The expensive half — two processes
# both running, one of them ours — is NOT closable by set difference, and this line does not pretend
# otherwise. It is a STATED RESIDUAL: the effort token has always been printed
# `EFFORT=…(self-reported)`, and under concurrency its PROVENANCE is unproven as well as its value.
# Closing it needs an isolated session namespace per invocation, which is a change to how kimi is
# launched rather than to how its output is read.
if [ ! -s "$OUT" ]; then
    :   # no capture, so nothing this invocation produced — decline to attribute any session
elif [ "$(printf '%s\n' "$NEW_SESSIONS" | grep -c .)" = 1 ]; then
    _w="$NEW_SESSIONS/agents/main/wire.jsonl"
    [ -r "$_w" ] && WIRE="$_w"
fi
EFFORTS=""
[ -n "$WIRE" ] && EFFORTS="$(grep -o '"thinkingEffort":"[a-z]*"' "$WIRE" 2>/dev/null \
    | sed 's/.*:"//;s/"//' | LC_ALL=C sort -u | tr '\n' ',')"

# WHAT THIS LINE IS EVIDENCE OF, EXACTLY. The wire log lives inside the session tree of the process it
# describes, and that process is shell-capable with this same `$HOME` and uid — it can rewrite the file
# to say `max` before this grep reads it (codex, PR #67 pass 15). No file under a HOME the reviewed
# process can write authenticates anything against that process, and neither does its own stdout; a
# channel it "cannot modify" does not exist at the same uid on the same machine. So the token is
# labelled for what it is — SELF-REPORTED — and the digest of the bytes this run actually read is
# printed beside it, so a later dispute has something fixed to point at. The assertion below still
# earns its keep against the failure it was written for (a run that silently used the default tier),
# and claims nothing about an adversarial one.
WIRE_SHA=""
[ -n "$WIRE" ] && WIRE_SHA="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$WIRE" 2>/dev/null)"

printf 'EXIT=%s BYTES=%s TREE=clean BASIS=%s PROMPT=%s EFFORT=%s(self-reported) WIRE=%s\n' \
    "$STATUS" "$(wc -c < "$OUT" | tr -d ' ')" "${BASIS:0:12}" "${PROMPT_SHA:0:12}" "${EFFORTS:-UNKNOWN}" "${WIRE_SHA:0:12}"

if [ "$EFFORTS" != "max," ]; then
    echo "EFFORT NOT ASSERTED AS max (saw: ${EFFORTS:-none}) — this run is not evidence about max" >&2
    exit 4
fi
exit "$STATUS"
