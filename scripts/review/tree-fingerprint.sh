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
tree_fingerprint() {
    git -C "$1" status --porcelain 2>/dev/null
    printf '\036\n'   # a record separator so status and diff cannot alias across the boundary
    git -C "$1" diff HEAD 2>/dev/null
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
