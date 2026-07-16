---
name: create-feature-plan
description: Scaffold a new FEATURE_NAME_PLAN.md under docs/planning/ using the project template.
---

# Create Feature Plan

Required for any feature, refactor, or multi-step development — no exceptions.

## Location

[`docs/planning/`](../../docs/planning/) with filename `FEATURE_NAME_PLAN.md` (SCREAMING_SNAKE_CASE).

### Subfolders

- `completed/` — move finished plans here
- `testing/` — plans in testing / validation
- `backlog/` — plans queued but not active
- `docs-archive/` — archived reference documentation

The canonical template lives at [`docs/planning/TEMPLATE.md`](../../docs/planning/TEMPLATE.md).

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

## After scaffolding

1. Update the Jira ticket (Task / Bug) with a link to the plan file.
2. **Snapshot the plan's digest BEFORE dispatching the reviews** — this is what binds the eventual
   approval to the exact bytes the reviewers saw. Capture it here, at the gate launch, because the later
   `/unleashed-mail:review-synthesis` step runs *after* the reviews and cannot reconstruct the
   pre-review bytes (COREDEV-2499):
   ```bash
   REVIEWED_PLAN_SHA256="$(shasum -a 256 docs/planning/FEATURE_NAME_PLAN.md | cut -d' ' -f1)"
   ```
   Keep `REVIEWED_PLAN_SHA256` for the synthesis step; it flows through to `review-verdict.py write
   --reviewed-sha256`, which refuses to record an approval if the plan changed after this snapshot.
3. Run `/gemini-review` and `/codex-review` on the plan before any code is written.
4. Incorporate reviewer feedback into the plan doc before the implementation batch begins. If you
   revise the plan in response to feedback, the reviews (and the snapshot in step 2) must be **re-run**
   on the new bytes — an approval is only valid for the exact plan the reviewers saw.
