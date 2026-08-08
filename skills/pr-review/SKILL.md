---
name: pr-review
description: Run a multi-agent code review on the current branch (security + concurrency + UX/perf + accessibility + AI-prompt-safety + parity)
argument-hint: [PR number or branch (defaults to current branch)]
# COREDEV-2642: model-invocable, so every tool here is PRE-APPROVED with no user gesture. `Bash(git *)`
# was every git command — reset/clean/push and the git-to-shell trampolines — while this workflow reads
# untrusted PR content (deep review, P1). It is replaced by one audited read-only wrapper, and `Agent` is
# enumerated to the reviewers this body actually spawns rather than every subagent installed.
allowed-tools: Read, Grep, Glob, Agent(swift-reviewer), Agent(unleashed-mail:swift-reviewer), Agent(security-reviewer), Agent(unleashed-mail:security-reviewer), Agent(concurrency-reviewer), Agent(unleashed-mail:concurrency-reviewer), Agent(ux-perf-reviewer), Agent(unleashed-mail:ux-perf-reviewer), Agent(accessibility-auditor), Agent(unleashed-mail:accessibility-auditor), Agent(prompt-review), Agent(unleashed-mail:prompt-review), Agent(jira-manager), Agent(unleashed-mail:jira-manager), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/changeset.sh *)
---

# PR Review: $ARGUMENTS

## Step 1: Identify the Changeset

```bash
# ONE granted command. This was a compound program — `detect_base()` with `local`, `grep`, `tr`, then
# two more git calls — under a `Bash(git *)` grant that pre-approved EVERY git command, including
# `reset --hard`, `clean` and `push`, while this workflow reads untrusted PR content (deep review, P1).
# `changeset.sh` performs base detection and the diff, and can run no other git verb.
bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/changeset.sh" files
bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/changeset.sh" stat
```

Categorize the changes:
- Database layer (models, migrations)
- Service/logic layer (providers, ViewModels, services)
- UI layer (views, components, WKWebView)
- Tests
- CI/pipeline
- Configuration

## Step 2: Launch the Multi-Agent Review

Invoke the **`swift-reviewer`** orchestrator agent. It will:

1. Spawn **`security-reviewer`** — scans for credential exposure, OAuth flaws,
   WKWebView injection, CI pipeline risks, entitlement issues
2. Spawn **`concurrency-reviewer`** — checks actor isolation, async/await correctness,
   GRDB threading, deprecated APIs, race conditions
3. Spawn **`ux-perf-reviewer`** — evaluates main-thread responsiveness, SwiftUI
   rendering efficiency, query performance, UX patterns
4. Spawn **`accessibility-auditor`** — VoiceOver, keyboard nav, Dynamic Type,
   dual-implementation a11y parity
5. Spawn **`prompt-review`** — AI prompt/call-site safety: jailbreak/injection surface,
   refusal paths, unsanitized ingress, tool scoping, PII-in-logs (static, read-only)
6. Run **provider parity audit** — checks Gmail ↔ Graph implementation symmetry
7. Spawn **`jira-manager`** — logs the review on the corresponding ticket

All seven streams run in parallel and produce independent reports.

The orchestrator synthesizes them into a unified review with deduplicated findings,
a consolidated issue table, and a single verdict.

## Step 3: Base Branch + Test-Coverage Check

The build / lint / **test** suite runs exactly **once** — inside the `swift-reviewer` orchestrator's
Step 4 ([`build-verify.sh`](../../scripts/review/build-verify.sh)), which Step 2 launches. pr-review does
**not** run a second `xcodebuild test`; that redundant double test-suite run is eliminated (its verdict
arrives in the unified review). Here we only resolve the base branch and do the cheap missing-test scan:

```bash
# Same wrapper, coverage mode. Each bash block is a fresh shell, so the base is re-detected inside the
# script rather than carried in a variable.
bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/changeset.sh" untested
```

## Step 4: Compile the Final Report

Merge the orchestrator's unified review with the test coverage assessment:

```
## PR Review — UnleashedMail

**Branch**: [branch name]
**PR**: $ARGUMENTS
**Files Changed**: [count]
**Tests**: [pass/fail count]

### Review Agents
| Agent | Status | Findings |
|---|---|---|
| security-reviewer | ✅/⚠️ | X blockers, Y warnings |
| concurrency-reviewer | ✅/⚠️ | X blockers, Y warnings |
| ux-perf-reviewer | ✅/⚠️ | X blockers, Y warnings |
| accessibility-auditor | ✅/⚠️ | X blockers, Y warnings |
| prompt-review | ✅/⚠️ | X blockers, Y warnings |
| parity-audit | ✅/⚠️ | X blockers, Y warnings |

### [Full unified review from swift-reviewer orchestrator]

### Test Coverage Assessment
[Your analysis of test coverage gaps]

### Final Verdict: [APPROVE / REQUEST CHANGES / NEEDS DISCUSSION]
```

If $ARGUMENTS includes a PR number or URL, offer to post the review as a
GitHub PR comment via `gh pr review`.
