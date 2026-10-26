---
name: create-feature-plan
description: Scaffold a new FEATURE_NAME_PLAN.md under docs/planning/ using the project template.
# Grants mirror brainstorm's plan-writing surface (2026-08-17 audit, AF-4): the snapshot step goes
# through the CONTAINED snapshot-plan.sh entrypoint (the raw `review-verdict.py snapshot` call this
# skill used to document let the model choose any --plan operand, e.g. under /tmp — the hole PR #63
# recheck P1 closed for brainstorm), and Edit(docs/planning/**) pre-approves the scaffold write
# (Edit-form, not Write-form — Write(path) rules are never consulted on CLI >= 2.1.210; AF-27).
# The .verdicts carve-out keeps the gate's verdict state writable only via granted entrypoints (AF-8).
allowed-tools: Read, Grep, Glob, Edit(docs/planning/**), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/snapshot-plan.sh *)
disallowed-tools: Edit(docs/planning/.verdicts/**)
---

# Create Feature Plan

Required for any feature, refactor, or multi-step development — no exceptions.

## Location

`docs/planning/` in the **consumer project** (a plain project-relative path — not a link, which from
this skill would resolve into the plugin's own install dir) with filename `FEATURE_NAME_PLAN.md`
(SCREAMING_SNAKE_CASE).

## Template (copy into the new file)

~~~markdown
# [Feature Name] Plan

**Status:** Planning | In Progress | Complete
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD

## Overview
Brief description of what this feature/refactor accomplishes.

## Approach
High-level strategy and key decisions.

## Milestones

- [ ] Milestone 1: Description
- [ ] Milestone 2: Description
- [ ] Milestone 3: Description

## Progress Log

### YYYY-MM-DD
- What was done
- Blockers encountered
- Next steps

## Files Changed
List of files created/modified (update as work progresses).

## Testing
How this will be tested; link to test files when complete.

## Notes
Open questions, alternatives considered, lessons learned.
~~~

## Before scaffolding

0. **Confirm you are inside the dedicated `.claude/worktrees/<name>` worktree for this ticket.** If you
   are not, create it and scaffold the plan there. Everything that follows — the digest snapshot, both
   reviews, the synthesis and the implementation — must happen in that SAME directory. The
   Combined-verdict artifact is per-directory session state under `docs/planning/.verdicts/`; it is
   git-ignored twice over and does **not** follow a later `git worktree add`, so scaffolding here and
   implementing elsewhere fails the gate on a genuine approval (`AGENT_CONTRACTS.md` §2 step 00).
   `create-feature-plan` makes no path assumptions and `implement`'s containment guard anchors to
   `realpath(".")`, so running the whole sequence inside the feature worktree works today with no
   additional flags.

## After scaffolding

1. Update the Jira ticket (Task / Bug) with a link to the plan file.
2. **Snapshot the plan's digest BEFORE dispatching the reviews** — this binds the eventual approval to
   the exact bytes the reviewers saw. It must persist to a FILE, not a shell variable: each skill step
   runs as a separate tool invocation, so a `REVIEWED_PLAN_SHA256=…` shell-local would be gone by the
   time `/unleashed-mail:review-synthesis` runs (COREDEV-2499). Use the **contained wrapper** — it
   validates the operand (a non-symlink regular file under `docs/planning` in THIS repository) before
   delegating to the `snapshot` subcommand of `${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py`, and
   it is what this skill's `allowed-tools` grants, so the step runs without a permission prompt (the
   raw `review-verdict.py snapshot` invocation accepted any path on disk and re-prompted every time —
   2026-08-17 audit, AF-4):
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/snapshot-plan.sh" docs/planning/FEATURE_NAME_PLAN.md
   ```
   `review-verdict.py write` auto-reads that sidecar and refuses to record an approval if the plan
   changed after the snapshot — so the synthesis step needs no `--reviewed-sha256` argument.
3. /unleashed-mail:gemini-review --ticket <T> --round <N> <plan>
   - /unleashed-mail:codex-review --ticket <T> --round <N> <plan>
4. Incorporate reviewer feedback into the plan doc before the implementation batch begins. If you
   revise the plan in response to feedback, the reviews **and** the `snapshot` (step 2) must be **re-run**
   on the new bytes — an approval is only valid for the exact plan the reviewers saw (re-running
   `snapshot` overwrites the sidecar atomically).
