---
name: implement
description: Implement a feature using specialized coding agents (db, logic, UI) with TDD and modern standards
argument-hint: [feature name or docs/planning/PLAN.md path]
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, Agent
disable-model-invocation: true
---

# Implement: $ARGUMENTS

This command orchestrates implementation across specialized coding agents.

## Phase 1: Design Gate (fail-closed)

Implementation without a **reviewed** plan violates CLAUDE.md's mandatory Plan Review Gate. Resolve the
plan **for this feature**, then **verify its Combined-verdict artifact deterministically**, before writing
any code:

```bash
# Resolve THE plan for $ARGUMENTS — never let an unrelated approved plan satisfy the gate.
# $ARGUMENTS is the feature name (e.g. "dark mode") or a repo-relative docs/planning path.

# PHYSICAL CONTAINMENT — the one guard, used by BOTH resolution branches.
#
# The plan's BYTES must live under <repo-root>/docs/planning. Everything else here is convenience; this
# is the tracked-plan mandate (CLAUDE.md:68) and it has been bypassed four different ways, each time
# because the previous guard checked a PROXY for containment instead of containment:
#   /tmp/OUTSIDE_PLAN.md                        -> `-f` accepts any existing file      (textual fix)
#   docs/planning/../../evil/OUTSIDE_PLAN.md    -> `..` wears the prefix               (added `..` case)
#   docs/planning/EVIL_PLAN.md -> /tmp/...      -> a symlink wears the prefix          (added realpath)
#   docs/planning -> /tmp/...                   -> a symlinked ROOT: realpath'ing the BASE resolved it
#                                                  through the same link, so both sides matched
# Resolve the plan, but anchor the base to the PHYSICAL repo root and do NOT resolve the base itself —
# then a symlinked docs/planning cannot launder its own target. (codex, #41 review; all reproduced.)
_contained() {
    python3 - "$1" <<'PYEOF'
import os, sys
root = os.path.realpath(".")
base = os.path.join(root, "docs", "planning")   # deliberately NOT realpath'd
real = os.path.realpath(sys.argv[1])
sys.exit(0 if real == base or real.startswith(base + os.sep) else 1)
PYEOF
}
_refuse_uncontained() {
    { echo "REFUSED: '$1' does not live under <repo-root>/docs/planning."
      echo "A tracked plan's BYTES must be in the repo — a symlink, a ../ escape, or a symlinked"
      echo "docs/planning is not a tracked plan (CLAUDE.md's Plan Review Gate)."; } >&2
    exit 1
}

if [ -f "$ARGUMENTS" ]; then
    _p="${ARGUMENTS#./}"
    case "$_p" in
        docs/planning/*PLAN*.md) ;;
        *) { echo "REFUSED: '$ARGUMENTS' is not a tracked plan."
             echo "The Plan Review Gate requires a repo-relative docs/planning/*PLAN*.md (CLAUDE.md)."; } >&2
           exit 1 ;;
    esac
    _contained "$_p" || _refuse_uncontained "$ARGUMENTS"
    PLAN="$_p"
else
    # One tr, not two: `[:upper:]`->`[:lower:]` positionally, then ` `/`.`/`-` -> `_` (gemini, #41).
    # THE DASH MUST COME LAST: in a tr SET a dash BETWEEN two characters is a RANGE, so ` -.` meant
    # space(32)..dot(46) — 15 characters — and `/implement "c+dark"` then matched C-DARK_PLAN.md, i.e.
    # the gate verified a plan nobody named (gemini, #41 review). Trailing `-` is a literal.
    KEY=$(printf '%s' "$ARGUMENTS" | tr '[:upper:] .-' '[:lower:]___')
    # THE CONTENT GUARD IS LOAD-BEARING AND IS THE LOOP'S GATE — do not "simplify" it to `-n "$KEY"`.
    # `[[ "$b" == *""* ]]` matches EVERY plan, so an empty KEY resolves to the first plan on disk: a
    # fail-OPEN. `-n` alone is not enough either — `tr` maps ' ', '-' and '.' to '_' BEFORE this runs, so
    # ARGUMENTS=" " yields KEY="_", which is non-empty and `*_*` matches most plan filenames. `*[!_]*`
    # states the real property ("not composed solely of what tr just mapped to _") and is
    # locale-independent, where the earlier `*[a-z0-9]*` was an ASCII proxy that refused `日本語`.
    # EXACT STEM matches are collected separately from mere SUBSTRING matches. A unique substring used
    # to resolve silently as identity — `/implement mode` picked DARK_MODE_PLAN.md — so a coincidental
    # fragment could satisfy the gate against a plan the user did not name (full review, #41). Now a
    # full/exact feature name always wins, and a pure substring must be named explicitly.
    #
    # For each plan, three stems the arg may exactly equal:
    #   full   — the basename minus the `_PLAN.md` suffix            (coredev_2328_reviewer_status_capture)
    #   desc   — full minus a leading `coredev_<digits>_` ticket     (reviewer_status_capture)
    #   ticket — the `coredev_<digits>` prefix alone                 (coredev_2328)
    EXACT=(); SUBSTR=()
    if [[ "$KEY" == *[!_]* ]]; then
        for p in docs/planning/*PLAN*.md; do
            [ -e "$p" ] || continue                 # unmatched glob stays literal -> skip
            # THE SAME CONTAINMENT GUARD AS THE DIRECT BRANCH. Without it `/implement evil` selected
            # `docs/planning/EVIL_PLAN.md -> /tmp/OUTSIDE_PLAN.md` and returned GATE OK — the direct
            # branch refused that exact symlink while the glob branch happily took it (codex, #41
            # review; reproduced). Filtering here so an out-of-tree symlink cannot even reach a match.
            _contained "$p" || continue
            # `b` is the NORMALIZED basename: tr already mapped ` `/`.`/`-` -> `_`, so `.md` is `_md`
            # here and the suffix to strip is `_plan_md`, not `_plan.md`.
            b=$(printf '%s' "${p##*/}" | tr '[:upper:] .-' '[:lower:]___')
            full="${b%_plan_md}"
            desc="$full"; ticket=""
            case "$full" in
                coredev_[0-9]*)
                    rest="${full#coredev_}"      # 2328_reviewer_status_capture
                    ticket="coredev_${rest%%_*}" # coredev_2328
                    desc="${rest#*_}"            # reviewer_status_capture
                    ;;
            esac
            if [ "$KEY" = "$full" ] || [ "$KEY" = "$desc" ] || [ "$KEY" = "$ticket" ]; then
                EXACT+=("$p")
            elif [[ "$b" == *"$KEY"* ]]; then
                SUBSTR+=("$p")
            fi
        done
    fi
    # Prefer EXACT: a full name wins over any coincidental substring.
    if [ "${#EXACT[@]}" -gt 1 ]; then
        { echo "AMBIGUOUS: '$ARGUMENTS' exactly names ${#EXACT[@]} plans — name a path:"; printf '%s\n' "${EXACT[@]}"; } >&2
        exit 2
    elif [ "${#EXACT[@]}" -eq 1 ]; then
        PLAN="${EXACT[0]}"
    elif [ "${#SUBSTR[@]}" -ge 1 ]; then
        # A PURE SUBSTRING is NOT identity. Do not auto-resolve it — the gate would then verify a plan
        # the user only partially named. Require an exact name (full review, #41).
        { echo "No plan is named exactly '$ARGUMENTS'. Did you mean one of these? Name it exactly:"
          printf '%s\n' "${SUBSTR[@]}"; } >&2
        exit 2
    fi
    # No EXACT and no SUBSTR -> empty PLAN -> the fail-closed branch below.
fi
if [ -z "$PLAN" ]; then
    # exit 1, and to stderr: the old form fell through with `ls`'s status, which is 0 whenever ANY
    # plan exists — so a FAILED resolution reported success.
    { echo "No plan matches '$ARGUMENTS'. Available:"; ls docs/planning/*PLAN*.md 2>/dev/null; } >&2
    exit 1
else
    echo "Plan: $PLAN"
    # Verify the persisted, digest-bound verdict for THAT plan. `:-.` so the recipe DOES what the prose
    # says — unset would resolve to the absolute /scripts/review-verdict.py and fail (gemini, #41).
    python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/review-verdict.py" verify --plan "$PLAN"
fi
```

- **No plan matching `$ARGUMENTS`?** STOP and hand back to the user: *"No planning doc found for
  `$ARGUMENTS` — run `/unleashed-mail:brainstorm` first (it's `disable-model-invocation: true`, so it's
  user-run only), then the Plan Review Gate (`/gemini-review` + `/codex-review` →
  `/unleashed-mail:review-synthesis`). Those two review skills are model-invocable, but per the
  AGENT_CONTRACTS §2 gate I run them under the plan-review workflow rather than self-approving here."*
  Do NOT proceed to Phase 2, and do **not** fall back to some other feature's plan.
- **`verify` exits non-zero?** STOP — read the `GATE FAILED` reason on stderr and act on it:
  - *no artifact* → the gate never ran (or ran in another checkout); ask the user to run
    `/gemini-review` + `/codex-review` → `/unleashed-mail:review-synthesis` to convergence.
  - *not an approving verdict* → the plan was `REQUEST_CHANGES`/`DISAGREEMENT`; iterate the plan + gate.
  - *plan has CHANGED since approval (digest mismatch)* → the plan was edited after approval
    (**approve-then-edit is blocked**); re-run the gate on the current plan.
  - *written for a different plan* → the artifact isn't this plan's; run the gate on `$PLAN`.
- **`verify` exits 0?** The artifact is an approving verdict bound to the plan's current bytes. Read the
  plan, re-verify the modern-standards recommendations are still current (via Context7), then proceed.

The `review-verdict.py verify` check is deterministic (raw-byte plan digest + dual-reviewer approval),
so it catches a stale/edited/absent/unrelated approval a prose check would miss. It stays
**workflow-level** fail-closed — `implement` declines to proceed; a skill cannot mechanically enforce a
tool boundary on its own (the gate deliberately drops the heavier PreToolUse-token approach as
over-engineering for this cooperative workflow). If `${CLAUDE_PLUGIN_ROOT}` is unset, use the
repo-relative `scripts/review-verdict.py`.

## Phase 2: Implementation Plan

Break the feature into tasks, organized by the agent that will own each task.
Order by dependency — database first, then logic, then UI.

```
=== Database Layer (db-engineer) ===
Task 1: [Schema design + migration]
Task 2: [Record types + query extensions]
Task 3: [Database tests]

=== Logic Layer (logic-engineer) ===
Task 4: [Service protocol definition]
Task 5: [Gmail provider implementation]
Task 6: [Graph provider implementation]
Task 7: [ViewModel with state management]
Task 8: [Mock implementations + logic tests]

=== UI Layer (ui-engineer) ===
Task 9: [View hierarchy + layout]
Task 10: [Loading/error/empty states]
Task 11: [Accessibility + animations]
Task 12: [UI integration tests]
```

Present the plan and wait for approval. Note which tasks can run in parallel
(e.g., Gmail and Graph implementations can be parallel after the protocol is defined).

## Phase 3: Execute with Specialized Agents

### Database tasks → `db-engineer` agent

Launch the `db-engineer` agent for Tasks 1-3:
> Implement the following database changes for [feature]. Follow the `grdb-patterns`
> skill and `swift-tdd` skill (write failing tests first). [task details]

Wait for completion. The db-engineer will produce: migration, Record types, query
extensions, and database tests.

### Logic tasks → `logic-engineer` agent

Launch the `logic-engineer` agent for Tasks 4-8:
> Implement the service layer and ViewModel for [feature]. The database layer is
> already done — here are the Record types and query extensions available: [summary].
> Follow `provider-parity` skill for dual-provider implementation. Use `swift-tdd`
> skill for testing. [task details]

The logic-engineer will produce: protocol, both provider implementations, ViewModel,
mocks, and logic tests.

### UI tasks → `ui-engineer` agent

Launch the `ui-engineer` agent for Tasks 9-12:
> Build the UI for [feature]. The ViewModel is already done — here is its public
> interface: [summary of properties and methods]. Follow `swiftui-mvvm` skill.
> Include accessibility and all view states. [task details]

The ui-engineer will produce: SwiftUI views, subcomponents, accessibility config,
and state views.

## Phase 4: Integration

After all three agents complete:

1. **Wire it together** — Ensure the View instantiates the ViewModel with the correct
   service and database dependencies.

2. **Run the full test suite**:
   ```bash
   set -o pipefail   # without it, `| tail` returns 0 and masks a failing xcodebuild
   xcodebuild test -scheme "Unleashed Mail" -destination 'platform=macOS' 2>&1 | tail -30
   ```

3. **Verify provider parity**:
   ```bash
   grep -rn "TODO: PARITY" --include='*.swift' "Unleashed Mail/Sources/"
   grep -rn "GmailService\|MicrosoftGraphService" --include='*.swift' "Unleashed Mail/Sources/ViewModels/" "Unleashed Mail/Sources/Views/"
   ```

4. **Commit with conventional format** (the COREDEV ticket key is mandatory, not optional):
   ```bash
   git add <specific-changed-files>
   git commit -m "feat(COREDEV-XXXX): [description]"
   ```

## Phase 5: Multi-Agent Review

Launch the `swift-reviewer` orchestrator agent, which will spawn five
specialized reviewers in parallel:
- `security-reviewer` — credentials, OAuth, pipeline, injection
- `concurrency-reviewer` — races, actors, deprecated APIs
- `ux-perf-reviewer` — responsiveness, rendering, query perf
- `accessibility-auditor` — VoiceOver, keyboard nav, a11y labels, dual-impl parity
- `prompt-review` — AI prompt/call-site safety: injection, refusal, ingress, tool scoping, PII-in-logs

Plus the `jira-manager` to log the review results on the ticket.

The orchestrator also runs the provider parity audit and produces a unified verdict.

Address any blockers or warnings before proceeding.

## Phase 6: Wrap Up

- Update `docs/planning/FEATURE_NAME_PLAN.md` status to "Complete" (or "In Review")
- Summarize what was implemented across all three layers
- List all commits made
- Note any follow-up items, tech debt, or deferred parity stubs
- Update Jira ticket via `jira-manager` with final status and follow-up tickets
- Offer to create a PR via `gh pr create`
