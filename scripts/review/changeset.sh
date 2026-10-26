#!/usr/bin/env bash
# Resolve the review base branch and report the changeset. READ-ONLY with respect to the work tree.
#
# WHY THIS EXISTS
# `skills/pr-review/SKILL.md` is model-invocable and granted `Bash(git *)`. Under Claude Code's
# permission semantics that is EVERY git command — `reset --hard`, `clean -fdx`, `push`, and the
# git-to-shell trampolines (aliases, `-c core.pager=…`, hooks) — pre-approved with no user gesture,
# while the workflow is reading untrusted PR content (deep review, P1). The body only ever needed
# base detection, a diff and a fetch of two specific refspecs.
#
# Its git blocks were ALSO compound programs (`detect_base()` with `local`, `sed`, a `while` loop), so
# a merely narrowed `Bash(git …)` grant would still have reprompted every run. One wrapper fixes both:
# the skill calls it as a single command, and the only git verbs that can run are the ones below.
#
# Usage:
#   changeset.sh files      # base line + changed file names
#   changeset.sh stat       # base line + diff stat
#   changeset.sh untested   # base line + changed Swift sources lacking a matching test file
#   changeset.sh base       # just the resolved base
#
# Exit: 0 · 1 on an unknown mode or a non-repository.
set -uo pipefail

# THE GIT ENVIRONMENT IS SANITISED BEFORE THE FIRST `git`. Inherited `GIT_DIR`/`GIT_WORK_TREE`
# silently redirect which repository this script reads, and `GIT_CONFIG_COUNT` can inject
# executable config (`core.fsmonitor`, `url.<ext::cmd>.insteadOf`). `changeset.sh` was shown
# reporting a base commit from a DIFFERENT worktree under exactly that (codex, PR #69 round 7);
# these three siblings invoke git too and had the same exposure, so the whole class is closed
# here rather than the one instance. The helper fails CLOSED if it cannot clear.
_CS_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=scripts/review/tree-fingerprint.sh
. "${_CS_DIR}/tree-fingerprint.sh"

MODE="${1-}"

die() { printf 'pr-review changeset: %s\n' "$1" >&2; exit 1; }

case "$MODE" in
    files|stat|untested|base) ;;
    *) die "usage: changeset.sh files|stat|untested|base" ;;
esac

git rev-parse --git-dir >/dev/null 2>&1 || die "not a git repository"

# Base-branch detection per AGENT_CONTRACTS.md §1+§5 (matches swift-reviewer):
#   1. If on a 1.0X/feature-name branch, target the matching 1.0X.0000 version branch
#   2. Else fall back to `git merge-base $(current) origin/main`
# A USABLE BASE IS A PROPER ANCESTOR OF HEAD (PR #63 recheck, P1 — reproduced).
#
# `git merge-base A B` succeeds whenever the two share ANY common ancestor, which a stale local
# `${prefix}.0000` that has ADVANCED PAST the feature branch still does — after a local test merge it
# may contain HEAD outright. The check below passed, the remote fetch was skipped as unnecessary, and
# `git diff "$BASE"...HEAD` then took HEAD itself as the merge base and reported an EMPTY changeset:
# `pr-review` approves having inspected nothing. Reproduced on a two-commit branch whose local base
# had been fast-forwarded to its tip — `changeset.sh files` printed the heading and no files.
#
# `--is-ancestor` asks the question that actually matters ("is the first one an ancestor of the
# other?"), and the equality clause is required with it: a base fast-forwarded to exactly HEAD IS an
# ancestor of HEAD, and still yields an empty diff. Refusing there is right — a review whose range is
# empty must fail, not pass quietly.
_usable_base() {
    git rev-parse --verify "$1^{commit}" >/dev/null 2>&1 || return 1
    git merge-base --is-ancestor "$1" HEAD >/dev/null 2>&1 || return 1
    [ "$(git rev-parse "$1")" != "$(git rev-parse HEAD)" ]
}

detect_base() {
    local current prefix
    current=$(git rev-parse --abbrev-ref HEAD)
    prefix=$(printf '%s' "$current" | grep -oE '^1\.0[0-4]/' | tr -d '/')
    if [ -n "$prefix" ]; then
        # A RESOLVABLE REF IS NOT A BASE. A stale or orphaned `${prefix}.0000` resolves as a commit —
        # and so passes the `rev-parse --verify` added below — while sharing no history with this
        # branch, so `git diff base...HEAD` falls through to `HEAD~1` and reviews only the last commit
        # (PR #63 recheck, P2). Require a common ancestor, which is the thing a base actually is.
        # THE FETCHED REMOTE IS TRIED FIRST. The local ref was preferred, so a stale or advanced local
        # copy shadowed the branch the PR actually targets — and the fetch that would have corrected it
        # was skipped precisely because the stale ref "resolved". Explicit refspec: bare
        # `git fetch origin BRANCH` only writes FETCH_HEAD, not refs/remotes/origin/BRANCH. This and
        # the `main` fetch below are the ONLY writes this script performs, and both are to
        # remote-tracking refs; nothing here touches the work tree.
        git fetch origin --quiet \
            "refs/heads/${prefix}.0000:refs/remotes/origin/${prefix}.0000" 2>/dev/null || true
        if _usable_base "origin/${prefix}.0000"; then
            printf '%s' "origin/${prefix}.0000"; return
        fi
        if _usable_base "${prefix}.0000"; then
            printf '%s' "${prefix}.0000"; return
        fi
    fi
    git fetch origin --quiet \
        refs/heads/main:refs/remotes/origin/main 2>/dev/null || true
    # The MERGE BASE, not the branch tip — and it is validated the same way. A merge base is an
    # ancestor of HEAD by construction, but it EQUALS HEAD when the branch is fully merged into the
    # target, which is the same empty-range fail-open one resolution path over.
    _candidate="$(git merge-base "$current" origin/main 2>/dev/null || true)"
    if [ -n "$_candidate" ] && _usable_base "$_candidate"; then
        printf '%s' "$_candidate"; return
    fi
    # A LOCAL main is still a real base — use it before giving up.
    _candidate="$(git merge-base "$current" main 2>/dev/null || true)"
    if [ -n "$_candidate" ] && _usable_base "$_candidate"; then
        printf '%s' "$_candidate"; return
    fi
    # FAIL, do not invent one. This returned the literal string `main` as though resolution had
    # succeeded; with no remote and no local `main`, `files`/`stat` then fell through to `HEAD~1` and
    # reviewed ONLY THE LAST COMMIT of a multi-commit branch, while `untested` emitted nothing and
    # exited 0. Silently narrowing a review's scope is worse than refusing it: the reviewer reports a
    # clean pass over work it never saw (PR #63 recheck, P2 — reproduced on a two-commit branch with
    # no remote).
    printf '%s' ""
}

BASE_BRANCH="$(detect_base)"
[ -n "$BASE_BRANCH" ] || die "could not resolve a base branch — refusing to review a narrowed range.
No remote-tracking or local base was found, so any diff here would silently cover only part of the
branch. Fetch the base (\`git fetch origin main\`) or name one explicitly, then re-run."

# A resolved base must also be a REAL commit. `detect_base` can only return refs it verified, but a
# name that stopped resolving between then and now would otherwise reach `git diff` as an operand.
git rev-parse --verify "${BASE_BRANCH}^{commit}" >/dev/null 2>&1 \
    || die "resolved base is not a commit: ${BASE_BRANCH}"

if [ "$MODE" = "base" ]; then
    printf '%s\n' "$BASE_BRANCH"
    exit 0
fi

printf 'Base: %s\n' "$BASE_BRANCH"

# NO `HEAD~1` FALLBACK (PR #63 recheck, P2). `files` and `stat` ended in `|| git diff HEAD~1`, which
# silently narrowed the review to the LAST COMMIT whenever the authoritative diff failed — the exact
# narrowing `detect_base`'s own `die` above refuses to allow, reintroduced two lines later as an error
# handler. By this point the base is resolved AND verified to be a commit, so a failure here is a real
# git error and the honest answer is to report it, not to review a fraction of the branch and print the
# result under the same heading. `untested` never had the fallback, and its silent `2>/dev/null` had
# the same effect: an unreadable diff produced an EMPTY loop and a clean "no untested files" report.
_diff_or_die() {
    git diff "$BASE_BRANCH"...HEAD "$@" \
        || die "could not diff ${BASE_BRANCH}...HEAD — refusing to report a narrowed range"
}

case "$MODE" in
    files)
        printf '\n=== Changed files ===\n'
        _diff_or_die --name-only
        ;;
    stat)
        printf '\n=== Diff stats ===\n'
        _diff_or_die --stat
        ;;
    untested)
        printf '\n=== Changed source files without test coverage ===\n'
        # THE DIFF RUNS IN THIS SHELL, not in a process substitution. `done < <(_diff_or_die …)` looks
        # like it fails closed, but the substitution is a SUBSHELL: `die` there exits only the subshell,
        # the loop reads zero bytes, and the report prints "no untested files" for a diff that never
        # ran. Writing to a file first puts the failure in the shell that can actually stop.
        CHANGED_LIST="$(mktemp "${TMPDIR:-/tmp}/changeset.XXXXXX")" \
            || die "could not allocate a scratch file for the changed-file list"
        trap 'rm -f "$CHANGED_LIST"' EXIT
        _diff_or_die -z --name-only > "$CHANGED_LIST"
        while IFS= read -r -d '' changed; do
            case "$changed" in
                "Unleashed Mail/Sources/"*.swift) ;;
                *) continue ;;
            esac
            test_path="${changed#Unleashed Mail/Sources/}"
            test_path="Unleashed MailTests/${test_path%.swift}Tests.swift"
            [ -f "$test_path" ] || printf '⚠️  %s → missing %s\n' "$changed" "$test_path"
        done < "$CHANGED_LIST"
        ;;
esac
