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
    git -C "$1" status --porcelain 2>/dev/null || return 1
    printf '\036\n'   # a record separator so status and diff cannot alias across the boundary
    git -C "$1" diff HEAD 2>/dev/null || return 1
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
        printf '(no new status line — the CONTENT of an already-modified tracked file changed)\n' >&2
    fi
}
