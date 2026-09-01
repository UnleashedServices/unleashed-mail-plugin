#!/usr/bin/env bash
# Resolve the SAME `--upstream` value the pinned trunk-action passes to `trunk check`.
#
# WHY THIS FILE EXISTS AT ALL (COREDEV-2780 §1 cell 1, C6a).
# `trunk check` exits 0 when the resolved diff matches no files, so the action alone reports GREEN
# HAVING CHECKED NOTHING — inherited defect 3, the one this plan is most at risk of repeating. The
# workflow therefore carries a guard that resolves the diff and fails when it is empty, BEFORE the
# action runs. But a guard that checks a DIFFERENT range than the one linted asserts nothing about the
# lint, and two independently-correct-looking resolvers drift. So there is exactly ONE implementation:
# the required workflow's guard, the push canary's guard and `trunk-parity-harness.yml` all invoke
# THIS script, and cell 1 proves parity by comparing the captured action argv byte-for-byte against
# this script's output.
#
# WHY IT IS PINNED BY DIGEST (C6a). This script lives in the checked-out tree, so C8's run-body digest
# CANNOT reach it: a `run:` body that invokes it hashes identically whatever this file contains. A
# pull request could edit this resolver so the empty-diff guard passes on a range the action never
# lints — inherited defect 3 wearing a new file name, on C6's own premise that the repository may not
# supply the tool that tests it. The workflow therefore verifies this file's sha256 in a step that runs
# BEFORE the step that executes it. Editing this file means updating that pinned digest, which is a
# reviewed change.
#
# THE LOGIC IS TRANSCRIBED FROM THE ACTION AT ITS PINNED SHA
# (trunk-io/trunk-action@e1234e67a86010d61ddac8d8ebf4b783e2ffd2fa), `pull_request.sh` and `push.sh`.
# It is not a reimplementation of what the action "should" do; a Dependabot pin bump must re-read those
# two files and re-run cell 1's parity harness rather than being merged as routine.
#
# Usage:  resolve-trunk-range.sh            # reads GITHUB_* from the environment
# Output: `upstream=<sha>` on stdout, one line. Nothing else goes to stdout.
# Exit:   0 resolved · 1 unresolvable (FAIL CLOSED — see the zero-`before` case below).

set -euo pipefail

die() {
    printf 'resolve-trunk-range: %s\n' "$1" >&2
    exit 1
}

event="${GITHUB_EVENT_NAME-}"
[ -n "${event}" ] || die "GITHUB_EVENT_NAME is unset — refusing to guess the event"

case "${event}" in
pull_request)
    # `pull_request.sh`: when the MERGE ref is checked out — which it always is here, because C8's
    # checkout-input allowlist forbids `ref:` — the action fetches depth=2 and uses HEAD^1 as the
    # upstream, deliberately in preference to `github.event.pull_request.base.sha`, "which can be
    # incorrect sometimes". The workflow sets `fetch-depth: 2` so HEAD^1 is already present.
    ref_name="${GITHUB_REF_NAME-}"
    pr_number="${GITHUB_EVENT_PULL_REQUEST_NUMBER-}"
    if [ -n "${pr_number}" ] && [ "${ref_name}" = "${pr_number}/merge" ]; then
        upstream="$(git rev-parse HEAD^1)" || die "HEAD^1 is unavailable — fetch-depth must be >= 2"
    else
        # The action's fallback. Unreachable in this repository's workflows (C8 forbids `ref:`), so it
        # is transcribed for parity and fails closed rather than silently resolving something else.
        upstream="${GITHUB_EVENT_PULL_REQUEST_BASE_SHA-}"
        [ -n "${upstream}" ] || die "not on the merge ref and no base SHA — cannot resolve an upstream"
    fi
    ;;
push)
    before="${GITHUB_EVENT_BEFORE-}"
    [ -n "${before}" ] || die "GITHUB_EVENT_BEFORE is unset on a push event"
    # THE ZERO-`before` CASE, AND WHY IT FAILS RATHER THAN RESOLVING (cell 1, C1's canary contract).
    # GitHub sends all zeros when a branch is CREATED or a TAG is pushed. At the pinned SHA `push.sh`
    # branches on exactly that and runs `trunk check --ci --all` — the 9027-finding whole-tree run §1
    # forbids, and a gate that is red by default is a gate people learn to ignore. This branch is
    # reachable only from the push canary; the required workflow has no push event at all. Fail closed:
    # a push whose diff cannot be resolved is not a push that gets to lint the tree.
    if [ "${before}" = "0000000000000000000000000000000000000000" ]; then
        die "zero \`before\` (branch creation or tag push) would send the action down its --all branch"
    fi
    if [[ ${GITHUB_REF_NAME-} == gh-readonly-queue/* ]]; then
        # `push.sh`: on the merge queue `github.event.before` is inaccurate, so the action uses HEAD^1.
        upstream="$(git rev-parse HEAD^1)" || die "HEAD^1 is unavailable on a merge-queue ref"
    else
        upstream="${before}"
    fi
    ;;
*)
    # `determine_check_mode.sh` maps `workflow_dispatch` to check-mode=all and `merge_group` to no
    # branch at all (falling through to check_mode=none — a skipped-but-SUCCESSFUL action, the exact
    # false pass this gate exists to prevent). Neither is permitted by C1/C7, so neither is resolved.
    die "unsupported event \`${event}\` — only pull_request and push resolve a range"
    ;;
esac

[ -n "${upstream}" ] || die "resolved an empty upstream"
printf 'upstream=%s\n' "${upstream}"
