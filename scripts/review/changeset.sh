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
detect_base() {
    local current prefix
    current=$(git rev-parse --abbrev-ref HEAD)
    prefix=$(printf '%s' "$current" | grep -oE '^1\.0[0-4]/' | tr -d '/')
    if [ -n "$prefix" ]; then
        if git rev-parse --verify "${prefix}.0000" >/dev/null 2>&1; then
            printf '%s' "${prefix}.0000"; return
        fi
        # Explicit refspec — bare `git fetch origin BRANCH` only writes FETCH_HEAD, not
        # refs/remotes/origin/BRANCH. This and the `main` fetch below are the ONLY writes this
        # script performs, and both are to remote-tracking refs; nothing here touches the work tree.
        git fetch origin --quiet \
            "refs/heads/${prefix}.0000:refs/remotes/origin/${prefix}.0000" 2>/dev/null || true
        if git rev-parse --verify "origin/${prefix}.0000" >/dev/null 2>&1; then
            printf '%s' "origin/${prefix}.0000"; return
        fi
    fi
    git fetch origin --quiet \
        refs/heads/main:refs/remotes/origin/main 2>/dev/null || true
    if git merge-base "$current" origin/main >/dev/null 2>&1; then
        git merge-base "$current" origin/main
    else
        printf '%s' "main"
    fi
}

BASE_BRANCH="$(detect_base)"
[ -n "$BASE_BRANCH" ] || die "could not resolve a base branch"

if [ "$MODE" = "base" ]; then
    printf '%s\n' "$BASE_BRANCH"
    exit 0
fi

printf 'Base: %s\n' "$BASE_BRANCH"

case "$MODE" in
    files)
        printf '\n=== Changed files ===\n'
        git diff "$BASE_BRANCH"...HEAD --name-only 2>/dev/null || git diff HEAD~1 --name-only
        ;;
    stat)
        printf '\n=== Diff stats ===\n'
        git diff "$BASE_BRANCH"...HEAD --stat 2>/dev/null || git diff HEAD~1 --stat
        ;;
    untested)
        printf '\n=== Changed source files without test coverage ===\n'
        while IFS= read -r -d '' changed; do
            case "$changed" in
                "Unleashed Mail/Sources/"*.swift) ;;
                *) continue ;;
            esac
            test_path="${changed#Unleashed Mail/Sources/}"
            test_path="Unleashed MailTests/${test_path%.swift}Tests.swift"
            [ -f "$test_path" ] || printf '⚠️  %s → missing %s\n' "$changed" "$test_path"
        done < <(git diff -z "$BASE_BRANCH"...HEAD --name-only 2>/dev/null)
        ;;
esac
