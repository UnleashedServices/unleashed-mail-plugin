#!/usr/bin/env bash
# COREDEV-2767 — run the Darwin-only half of CI on THIS Mac and publish the verdict to GitHub as a
# commit status, so a pull request can be gated on evidence that never ran on a GitHub runner.
#
# WHY THIS EXISTS. `redactor-equivalence (macos-latest)` runs the full `scripts/tests` suite, and its
# matrix includes macOS only on `push` to `main`. Every @skipUnless(DARWIN) class — the real
# `_unleashed_auth_chain`, the real ACL arm, the mode and owner clauses — therefore runs AFTER a
# merge and never on the pull request that introduced it. This script closes that window locally.
#
# WHAT IT IS NOT. A commit status posted from a laptop is SELF-ATTESTED: anyone with push access can
# post `success` without running anything. This gates the maintainer's own mistakes, not an
# adversary. Say so out loud rather than letting a green tick imply more than it means. The
# non-self-attested equivalent is to run the macOS leg on `pull_request` in the workflow itself,
# which on this PUBLIC repo costs zero billable minutes (measured: run 32819402531 reports
# `MACOS.total_ms = 0`) and about 17 minutes of wall clock.
#
# IT ATTESTS A COMMIT, NOT A WORKING TREE. The checks run in a throwaway worktree checked out at the
# exact SHA being reported on, so a dirty or half-saved working tree cannot be reported as passing.
# This campaign has twice had a claim outlive the code it described; that is the whole reason.
#
#   bash scripts/local-gate.sh              # attest HEAD
#   bash scripts/local-gate.sh <sha>        # attest a specific commit
#   LOCAL_GATE_DRY_RUN=1 bash scripts/...   # run everything, post nothing
set -euo pipefail

REPO="${LOCAL_GATE_REPO:-UnleashedServices/unleashed-mail-plugin}"
CONTEXT="${LOCAL_GATE_CONTEXT:-darwin-suite (local)}"
LOGDIR="${LOCAL_GATE_LOGDIR:-$HOME/.claude/local-gate}"

die() { printf 'local-gate: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = Darwin ] || die "this gate exists to run the DARWIN classes; $(uname -s) cannot"
command -v gh >/dev/null 2>&1 || die "gh is not installed"
gh auth status >/dev/null 2>&1 || die "gh is not authenticated"

SHA="$(git rev-parse "${1:-HEAD}")"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/${SHA:0:12}.log"

post() {                                   # $1 state, $2 description
    [ -z "${LOCAL_GATE_DRY_RUN:-}" ] || { printf 'local-gate: DRY RUN, would post %s: %s\n' "$1" "$2"; return 0; }
    # `description` is capped at 140 characters by the API; truncate rather than fail the post.
    gh api -X POST "repos/$REPO/statuses/$SHA" \
        -f state="$1" -f context="$CONTEXT" -f description="$(printf '%.139s' "$2")" \
        >/dev/null || printf 'local-gate: WARNING could not post %s\n' "$1" >&2
}

# FAIL-CLOSED. Any exit that is not the explicit success path publishes a failure, so a killed run,
# a syntax error or a `set -e` abort can never leave the last word as a stale `pending`.
# A verdict is posted EXACTLY ONCE. Without the flag the failure path posted, fell through to the
# trap, posted again, and exited 0 — reporting a red gate with a green exit status, which is the
# precise shape of a bug this repo has already been bitten by twice.
# THE STATUS IS CAPTURED BY THE TRAP, NOT BY `finish`. The first spelling read `$?` inside `finish`,
# and the trap ran `cleanup_wt; finish` — so `$?` was the CLEANUP's status, not the script's. A run
# killed by a timeout reported `rc=0` in its own failure description. Same shape as a `| tee` that
# returns tee's status over a red gate, which this repo has been bitten by twice.
GATE_POSTED=0
_t=0                                        # pre-assigned: the trap assigns it, which SC2154 cannot see
finish() {
    _fin="${1:-1}"
    [ "$GATE_POSTED" = 1 ] && exit "$_fin"
    post failure "the local Darwin gate did not complete (rc=$_fin) — see $LOG"
    [ "$_fin" = 0 ] && exit 1
    exit "$_fin"
}
trap '_t=$?; finish "$_t"' EXIT

# THE WORKTREE IS THE POINT. Running in the current checkout would attest whatever happens to be on
# disk; this materialises exactly the commit being reported on.
WT="$(mktemp -d "$LOGDIR/wt-XXXXXXXX")"
cleanup_wt() { git worktree remove --force "$WT" >/dev/null 2>&1 || rm -rf "$WT"; }
trap '_t=$?; cleanup_wt; finish "$_t"' EXIT
rmdir "$WT"                                # `git worktree add` needs the path to not exist yet
git worktree add --detach --quiet "$WT" "$SHA" || die "could not check out $SHA"

post pending "running the Darwin suite locally on $(sw_vers -productVersion 2>/dev/null || echo macOS)"
printf 'local-gate: %s -> %s\n' "${SHA:0:12}" "$LOG"

: > "$LOG"
rc=0
run_step() {                               # $1 label, rest: command
    label="$1"; shift
    printf '\n=== %s ===\n' "$label" >> "$LOG"
    if ( cd "$WT" && "$@" ) >> "$LOG" 2>&1; then
        printf '  %-34s PASS\n' "$label"
    else
        printf '  %-34s FAIL\n' "$label"; rc=1
    fi
}

# The two steps the macOS leg runs and no other job does. Everything else in CI already runs on
# ubuntu for every pull request, so repeating it here would buy nothing.
run_step "scripts suite (Darwin classes)" python3 -m unittest discover -s scripts/tests -v
run_step "hook stdin-contract harness"    bash scripts/test-hooks.sh

# HOW MANY RAN, not just that nothing failed: a suite that collected nothing also reports OK, and a
# green tick that means "zero cells executed" is worse than no tick at all.
ran="$(sed -n 's/^Ran \([0-9][0-9]*\) test.*/\1/p' "$LOG" | awk '{t+=$1} END{print t+0}')"
skipped="$(sed -n 's/.*skipped=\([0-9][0-9]*\).*/\1/p' "$LOG" | awk '{t+=$1} END{print t+0}')"
[ "$ran" -gt 0 ] 2>/dev/null || { rc=1; printf '  %-34s FAIL (collected nothing)\n' "cell count"; }

if [ "$rc" = 0 ]; then
    post success "$ran cells on Darwin, $skipped skipped — SELF-ATTESTED from a laptop, not a runner"
    GATE_POSTED=1
    printf 'local-gate: PASS — %s cells, %s skipped\n' "$ran" "$skipped"
    exit 0
fi
post failure "the Darwin suite failed locally ($ran cells ran) — see $LOG"
GATE_POSTED=1
printf 'local-gate: FAIL — %s cells ran; %s\n' "$ran" "$LOG" >&2
exit 1
