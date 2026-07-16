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
# $ARGUMENTS is the feature name (e.g. "dark mode") or a direct path to the plan.
if [ -f "$ARGUMENTS" ]; then
    PLAN="$ARGUMENTS"
else
    # One tr, not two: `[:upper:]`->`[:lower:]` positionally, then ` `/`.`/`-` -> `_` (gemini, #41).
    # `.` is normalized too, or `/implement "OAuth 2.0"` (KEY `oauth_2.0`) never matches
    # OAUTH_2_0_PLAN.md (`oauth_2_0_plan.md`) and the gate reports "no plan" for a plan that exists
    # (codex, #41 review). `.md` -> `_md` on both sides is harmless: this is a substring test.
    #
    # THE DASH MUST COME LAST. In a tr SET, a dash BETWEEN two characters is a RANGE, so the ` -.` I
    # first wrote meant space(32)..dot(46) — silently mapping 15 characters (!"#$%&'()*+,-.) to `_` on
    # BOTH BSD and GNU tr, not the three I intended. That is not cosmetic: it widens the equivalence
    # class and resolves the WRONG plan — `/implement "c+dark"` -> KEY `c_dark` -> matches
    # C-DARK_PLAN.md, so the gate verifies a plan nobody named (gemini, #41 review; the exact fail-open
    # this block exists to prevent). Trailing `-` is a literal; ` .-` maps space, dot and dash only.
    KEY=$(printf '%s' "$ARGUMENTS" | tr '[:upper:] .-' '[:lower:]___')
    # LITERAL substring match. NOT `case` (bash 3.2 — what macOS ships — cannot parse `case … esac`
    # nested inside a `while` inside `$( )`), and NOT `${b#*$KEY}` (that expands $KEY as a GLOB, so
    # `d*k` and `dark?mode` both false-match DARK_MODE_PLAN.md).
    #
    # THE `-n "$KEY"` GUARD IS LOAD-BEARING — DO NOT "SIMPLIFY" IT AWAY. `[[ "$b" == *""* ]]` matches
    # EVERY plan, so without it an empty $ARGUMENTS silently resolves to the first plan on disk and
    # satisfies the Design Gate: a fail-OPEN. (The old prefix-strip form was only *accidentally*
    # fail-closed on an empty key; this makes the property explicit.)
    # A direct glob, NOT `ls | while read` — parsing ls breaks on a filename with spaces/newlines, and
    # the subshell also swallowed any variable set inside it (gemini, #41 review). bash 3.2-safe.
    # An ARRAY, not a newline-joined string: `grep -c .` counted a filename CONTAINING a newline as two
    # matches and reported a false AMBIGUOUS, and ${p##*/} drops a basename subshell per file (gemini).
    # THE CONTENT GUARD IS LOAD-BEARING AND IS THE LOOP'S GATE — do not "simplify" it to `-n "$KEY"`,
    # and do not drop it. `[[ "$b" == *""* ]]` matches EVERY plan, so an empty KEY silently resolves to
    # the first plan on disk and satisfies the Design Gate: a fail-OPEN. `-n` alone is NOT enough either,
    # because `tr` above maps ' ', '-' and '.' to '_' BEFORE this runs — so ARGUMENTS=" " (or "-", or
    # " - ") yields KEY="_", which is non-empty, passes `-n`, and `*_*` then matches most plan filenames.
    # `/implement " "` therefore resolved to an arbitrary plan and verified THAT plan's artifact: if it
    # happened to be approved, the gate PASSED for a feature nobody named.
    #
    # `*[!_]*` — "KEY is not composed SOLELY of the characters tr just mapped to underscore" — states
    # that property directly. It replaced `*[a-z0-9]*`, which tested an ASCII-shaped PROXY for it and so
    # rejected a legitimate all-non-ASCII feature name (`日本語` -> no [a-z0-9] -> treated as content-free
    # and refused; `café`/`Grüße` were fine, having ASCII letters). That direction is fail-CLOSED — the
    # user gets "No plan matches" and the plan list — so it was usability, not a hole (gemini, #41
    # review). Verified identical to the old guard on every content-free input ('', ' ', '-', '.', ' - ',
    # '--', '...', '_', '___') and locale-independent.
    # Hoisted out of the loop so a junk KEY costs zero subshells (gemini, #41 review).
    MATCHES=()
    if [[ "$KEY" == *[!_]* ]]; then
        for p in docs/planning/*PLAN*.md; do
            [ -e "$p" ] || continue                 # unmatched glob stays literal -> skip
            b=$(printf '%s' "${p##*/}" | tr '[:upper:] .-' '[:lower:]___')
            [[ "$b" == *"$KEY"* ]] && MATCHES+=("$p")
        done
    fi
    N=${#MATCHES[@]}
    # AMBIGUITY IS NOT A PASS. `head -1` would silently pick the alphabetically-first of N matches, so
    # `/implement review` could verify an approved-but-WRONG plan while the intended one stays ungated
    # — defeating this block's whole purpose. Make the human disambiguate.
    if [ "$N" -gt 1 ]; then
        { echo "AMBIGUOUS: '$ARGUMENTS' matches $N plans — name one exactly:"; printf '%s\n' "${MATCHES[@]}"; } >&2
        exit 2
    fi
    PLAN="${MATCHES[0]}"          # empty array -> empty PLAN -> the fail-closed branch below
fi
if [ -z "$PLAN" ]; then
    # exit 1, and to stderr: the old form fell through with `ls`'s status, which is 0 whenever ANY
    # plan exists — so a FAILED resolution reported success.
    { echo "No plan matches '$ARGUMENTS'. Available:"; ls docs/planning/*PLAN*.md 2>/dev/null; } >&2
    exit 1
else
    echo "Plan: $PLAN"
    # Verify the persisted, digest-bound verdict for THAT plan:
    # :-. so the recipe DOES what the prose below says — unset would otherwise resolve to the
    # absolute /scripts/review-verdict.py and fail (gemini, #41 review). Matches the other skills.
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
