#!/usr/bin/env bash
# One implementation of "did anything in this checkout change while the reviewer ran".
#
# WHY THIS IS SHARED AND NOT COPIED (PR #63 recheck, P1/P2). The COREDEV-2607 detector — a reviewer in
# agent mode that IMPLEMENTS the plan instead of reviewing it — exists in three places: the agy
# preflight and both isolation harnesses. Each fingerprinted with `git status --porcelain` alone, which
# reports ONE LINE PER PATH (` M file`): editing an ALREADY-DIRTY tracked file leaves that line
# byte-identical, so the before/after compared equal while the bytes changed.
#
# That was found and fixed in the preflight first, as a local shell function. The two harnesses — where
# the detector is gate-bearing and its failure VOIDS the round — kept the status-only comparison, which
# is the same "a rule that lives in one script is a rule the next entrypoint will not have" failure this
# repo keeps recording. The rule lives here now, and all three source it.
#
# Pairing the status with `git diff HEAD` folds the actual content of every tracked change into the
# fingerprint. A created or removed path still moves a status line; the diff covers the case the status
# line cannot see. Untracked files are the residual: `??` announces one, but a second edit to an
# already-untracked file is invisible to both halves. The harnesses close that separately, by verifying
# the round's BASIS files (plan, prompt) against the digests recorded before launch.

# Print the content-aware fingerprint of the checkout rooted at $1.
# THE DEFAULT UNTRACKED MODE, DELIBERATELY — this function fingerprints the LIVE checkout.
#
# Git collapses an untracked directory to a single `?? dir/` line, which hides a file created beneath
# one; `--untracked-files=all` expands it, and that IS the right answer for the disposable review
# checkout, where the harnesses use it (PR #63 recheck, P2). It is the wrong answer here: the allocator
# writes its own per-run files — the reserved leaf, `.captureid`, the sidecars — into the transcript
# state tree BETWEEN this function's before and after calls, and when that tree sits inside the
# repository (`XDG_STATE_HOME` under the checkout, which the harness fixtures use and a developer may
# too) every one of them appears as a new line and VOIDS a clean round. Reproduced: six harness tests
# failed with `GATE FAILED — the reviewer MUTATED the working tree` naming a `.captureid` the harness
# itself had just created.
#
# RESIDUAL, stated rather than traded away: a reviewer writing inside an ALREADY-untracked directory of
# the live checkout is not seen here. The `git diff HEAD` half below covers every tracked change, the
# disposable checkout — where the reviewer actually runs — is compared with `-uall`, and the round's
# basis files are content-verified against their recorded digests. A guard that fails every honest
# round is one that gets switched off, which is the worse failure.
# A FAILED PROBE IS NOT A CLEAN TREE — the LIVE-checkout half of the same finding (PR #63 recheck, P1).
# Both commands suppressed their status, so a shell-capable reviewer that deleted or corrupted the live
# checkout's `.git` through an absolute path made BOTH fail: the fingerprint became the bare record
# separator, identical to the one taken before, and the comparison found no mutation. Reproduced by the
# reviewer. The disposable-checkout probe was fixed for exactly this one commit earlier and this one
# was not — the sibling-sweep failure this campaign keeps repeating.
#
# Returns non-zero when either probe fails; callers treat that as a void round, never as a clean tree.
tree_fingerprint() {
    # HEAD FIRST. `status --porcelain` and `diff HEAD` are both EMPTY before and after a clean commit
    # made during the review — the working tree matches the (new) HEAD — so an author who edited and
    # committed while the arms ran left the fingerprint byte-identical, and the round certified a review
    # of a repository that had changed under it, contrary to the "an author commit voids the round"
    # rule the harnesses print. The resolved commit is part of the checkout's identity (codex, PR #67
    # pass 8 — reproduced).
    git -C "$1" rev-parse HEAD 2>/dev/null || return 1
    git -C "$1" status --porcelain 2>/dev/null || return 1
    printf '\036\n'   # a record separator so status and diff cannot alias across the boundary
    git -C "$1" diff HEAD 2>/dev/null || return 1
    # THE ONE GITIGNORED PATH THAT IS GATE-BEARING. `docs/planning/.verdicts/` holds the Combined-verdict
    # artefact the plan gate READS, and it is ignored at the repo root — so a reviewer with a shell that
    # wrote a forged approval there was invisible to both halves above (adversarial verification, PR #67
    # pass 6). Only the synthesis step writes it, after both arms have landed, so during a round it must
    # not change. Fingerprinted by CONTENT through the same helper the disposable checkout uses. Other
    # ignored paths (`__pycache__`, the transcript state tree when it sits inside the checkout) are NOT
    # included: the harness's own python and allocator write there between the before and after calls,
    # and a guard that voids every honest round is one that gets switched off. That residual is stated.
    if [ -d "$1/docs/planning/.verdicts" ]; then
        printf '\036\n'
        disposable_fingerprint "$1/docs/planning/.verdicts" || return 1
    fi
}

# Build a PRIVATE disposable checkout of commit $2 of the repository at $1, at path $3 (must not exist).
#
# NOT `git worktree add`. A linked worktree's `.git` is a FILE pointing INTO THE MAINTAINER'S REAL
# REPOSITORY, and every git operation a shell-capable reviewer runs inside it lands there: `git config
# core.hooksPath` from the disposable checkout wrote the LIVE repo's `.git/config`, so the maintainer's
# next real commit would have run a reviewer-planted hook; `git commit`/`git stash`/`update-ref` wrote
# refs and objects into the shared database (the "dangling commits survive" note the agy harness carried
# was this same class); and repointing the `.git` file made every later `git status` answer about a
# DIFFERENT repository (adversarial verification, PR #67 pass 6 — reproduced). A `git clone --local`
# would HARDLINK the object files, and a hardlinked object rewritten in the clone is rewritten in the
# source; `--shared` publishes the source's path in `objects/info/alternates`. So: `git init`, then FETCH
# the one commit over the local transport (upload-pack on the source is read-only; a detached source
# HEAD is advertised, so the harnesses' `git rev-parse HEAD` is always fetchable — measured), then a
# detached checkout. No remote, no alternates, no hardlinks; `FETCH_HEAD` — the one file that names the
# source path — is removed. The reviewer's git is fully usable and fully private. Measured: 3.8 MB and
# under a second for this repository.
disposable_checkout() {
    _dc_repo="$1"; _dc_sha="$2"; _dc_dest="$3"
    [ ! -e "$_dc_dest" ] || return 1
    git init -q -- "$_dc_dest" >/dev/null 2>&1 || return 1
    git -C "$_dc_dest" fetch -q --no-tags -- "$_dc_repo" "$_dc_sha" >/dev/null 2>&1 || return 1
    git -C "$_dc_dest" checkout -q --detach FETCH_HEAD >/dev/null 2>&1 || return 1
    rm -f "$_dc_dest/.git/FETCH_HEAD"
    [ "$(git -C "$_dc_dest" rev-parse HEAD 2>/dev/null)" = "$_dc_sha" ] || return 1
}

# Content fingerprint of a DISPOSABLE checkout rooted at $1 — every path beneath it except `.git`,
# with its type, permission bits, size and content hash (the target, for a symlink), one line per
# entry, sorted. Compared for EQUALITY around the reviewer's run; a `diff` of the two outputs is the
# report.
#
# NEVER `git status`. Status is METADATA THE REVIEWER CONTROLS: after editing a file a reviewer can
# `git commit` it (status clean), `git update-index --assume-unchanged`/`--skip-worktree` it (hidden),
# drop a nested self-ignoring `.gitignore` or an `info/exclude` rule beside new files (not `??`), or
# `git stash` (working files revert; the edits live on in the reviewer's private clone). Every one of
# those passed the previous status-based probe (adversarial verification, PR #67 pass 6 — reproduced),
# and a probe that FAILED (`.git` deleted) had already been turned into an empty baseline by `|| true`
# in one harness (codex, PR #67). Hashing the bytes of what is actually in the tree is not something the
# reviewer can talk git out of. `.git` is recorded as an ENTRY — its type, and its bytes when it is a
# gitfile — but NOT descended: git's own bookkeeping (the `index` stat cache on every `git status` the
# reviewer runs) would void every honest round, and in a PRIVATE checkout nothing under `.git` can reach
# the maintainer; while a reviewer that DELETES or REPOINTS `.git` has still written inside the checkout
# and is caught. RESIDUAL, stated: an edit that is REVERTED before the run ends (edit; `git checkout
# --`) leaves no trace here; this detects edits that SURVIVE the run.
# THE SERIALISATION IS INJECTIVE: path and link-target fields are JSON-encoded (pure ASCII, quoted,
# escaped). A line-oriented record with a RAW path was not — a reviewer that deleted `b` and renamed
# `a` to `a<newline><b's whole record>` produced byte-identical output, and the before/after gate in
# all three harnesses accepted the altered checkout (codex, PR #67 pass 9 — reproduced).
disposable_fingerprint() {
    python3 - "$1" <<'PY' || return 1
import hashlib, json, os, stat, sys
root = sys.argv[1]
if not os.path.isdir(root):
    sys.exit(1)
lines = []
for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
    if dirpath == root:
        # `.git` is listed as an entry below but never descended.
        dirnames[:] = [d for d in dirnames if d != ".git"]
        if ".git" not in filenames and os.path.lexists(os.path.join(root, ".git")):
            filenames = filenames + [".git"]
    dirnames.sort()
    for name in sorted(dirnames + filenames):
        full = os.path.join(dirpath, name)
        rel = os.path.relpath(full, root)
        st = os.lstat(full)
        mode = "%04o" % stat.S_IMODE(st.st_mode)
        q = json.dumps(rel)                       # ensure_ascii: one unambiguous, newline-free token
        if stat.S_ISLNK(st.st_mode):
            lines.append("L %s %s -> %s" % (mode, q, json.dumps(os.readlink(full))))
        elif stat.S_ISDIR(st.st_mode):
            lines.append("D %s %s" % (mode, q))
        elif stat.S_ISREG(st.st_mode):
            h = hashlib.sha256()
            with open(full, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 16), b""):
                    h.update(chunk)
            lines.append("F %s %d %s %s" % (mode, st.st_size, h.hexdigest(), q))
        else:
            lines.append("O %s %s" % (mode, q))
sys.stdout.write("\n".join(lines) + ("\n" if lines else ""))
PY
}

# Print the human-readable summary of what changed between two fingerprints, to stderr.
# $1 = checkout root, $2 = the status portion captured before the run.
tree_fingerprint_report() {
    _tf_after_status="$(git -C "$1" status --porcelain 2>/dev/null)"
    # Only what CHANGED at the STATUS level, for a readable summary — printing the whole status (or the
    # whole diff) buries the one new line. A content-only edit to an already-dirty file shows no new
    # status line, so say so rather than printing nothing.
    _tf_new="$(printf '%s\n' "$_tf_after_status" | grep -vxF -- "$2" || true)"
    if [ -n "$_tf_new" ]; then
        printf '%s\n' "$_tf_new" >&2
    else
        # No new status line: either the CONTENT of an already-modified file changed, or — the case a
        # clean commit mid-round produces — HEAD itself moved. Say which, from the fingerprint's own
        # first line ($3 = the HEAD recorded before the run, when the caller has it).
        if [ -n "${3:-}" ] && [ "$(git -C "$1" rev-parse HEAD 2>/dev/null)" != "$3" ]; then
            printf '(no new status line — HEAD moved from %s to %s: a commit was made during the review)\n' \
                "$3" "$(git -C "$1" rev-parse HEAD 2>/dev/null)" >&2
        else
            printf '(no new status line — the CONTENT of an already-modified tracked file changed)\n' >&2
        fi
    fi
}
