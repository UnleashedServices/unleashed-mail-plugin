---
name: implement
description: Implement a feature using specialized coding agents (db, logic, UI) with TDD and modern standards
argument-hint: [feature name or docs/planning/PLAN.md path]
# COREDEV-2642 (PR #63 review, gap 1): this skill is model-invocable, so every tool listed here
# is PRE-APPROVED with no user gesture — including one the model opened by deciding a task "is an
# implementation", a decision injected content in a reviewed file can steer. The body ORCHESTRATES:
# it delegates all file writing to db-engineer / logic-engineer / ui-engineer via Agent, which carry
# their own tools. So blanket Write/Edit/Bash were pre-approval this skill never exercises itself.
# `allowed-tools` is a pre-approval grant, NOT a restriction — narrowing it does not disable
# anything, it just means those calls need the normal user gesture. That is the correct posture for
# a model-reachable workflow.
allowed-tools: Read, Grep, Glob, Agent(db-engineer), Agent(unleashed-mail:db-engineer), Agent(logic-engineer), Agent(unleashed-mail:logic-engineer), Agent(ui-engineer), Agent(unleashed-mail:ui-engineer), Agent(swift-reviewer), Agent(unleashed-mail:swift-reviewer), Agent(security-reviewer), Agent(unleashed-mail:security-reviewer), Agent(concurrency-reviewer), Agent(unleashed-mail:concurrency-reviewer), Agent(ux-perf-reviewer), Agent(unleashed-mail:ux-perf-reviewer), Agent(accessibility-auditor), Agent(unleashed-mail:accessibility-auditor), Agent(prompt-review), Agent(unleashed-mail:prompt-review), Agent(jira-manager), Agent(unleashed-mail:jira-manager), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/resolve-plan-gate.sh *)
---

# Implement: $ARGUMENTS

This command orchestrates implementation across specialized coding agents.

## Phase 1: Design Gate (fail-closed)

Implementation without a **reviewed** plan violates CLAUDE.md's mandatory Plan Review Gate. Resolve the
plan **for this feature**, then **verify its Combined-verdict artifact deterministically**, before writing
any code:

**Do NOT paste the user's argument into a shell command.** Resolve the plan yourself first — with
`Glob` over `docs/planning/*_PLAN.md` and `Read` — then invoke the gate with the concrete path you
resolved, as a single operand:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/resolve-plan-gate.sh" docs/planning/FEATURE_NAME_PLAN.md
```

The script owns the resolution fallback, the physical-containment guard (the plan's bytes must live
under `<repo-root>/docs/planning`) and the deterministic verify. It is ONE command, so the scoped grant
above covers it; when this was ~135 lines of inline functions and branches it matched no grant at all,
so the one block that must run before any implementation prompted every time.

> **Why the argument is no longer substituted here (PR #63 recheck, P1).** This fence used to bind the
> argument through a quoted heredoc, which kept shell metacharacters (`"`, `$( )`, backticks) as literal
> data. What that could not defend was the DELIMITER: the placeholder is substituted **textually across
> this entire fence before the shell runs**, so an argument containing a line exactly equal to the
> heredoc delimiter closed the body early and every following line was parsed as a shell command — with
> the skill model-invocable, that needed no user gesture. A quoted delimiter stops expansion inside the
> body; it does not stop the body from ending. No quoting fixes it, because the fault sits one level
> above the quoting: untrusted text in shell *syntax*. The remedy is to keep it out of syntax entirely,
> which is why you resolve the path and pass a real one.


- **No plan matching `$ARGUMENTS`?** STOP and hand back to the user: *"No planning doc found for
  `$ARGUMENTS` — run `/unleashed-mail:brainstorm` first to produce one, then gate it with:*
    /unleashed-mail:gemini-review --ticket <T> --round <N> <plan>
    /unleashed-mail:codex-review --ticket <T> --round <N> <plan>
  *and then `/unleashed-mail:review-synthesis`. Those review skills are model-invocable, but per the
  AGENT_CONTRACTS §2 gate I run them under the plan-review workflow rather than self-approving here."*
  Do NOT proceed to Phase 2, and do **not** fall back to some other feature's plan.
- **`verify` exits non-zero?** STOP — read the `GATE FAILED` reason on stderr and act on it:
  - *no artifact* → the gate never ran, **or it ran in a DIFFERENT checkout/worktree**. The artifact
    lives under `<plan-dir>/.verdicts/` and is **not carried by git** — it is ignored at the repo root
    and self-ignored by a `*` `.gitignore` the tool writes inside that directory, so a fresh
    `git worktree add` or `git clone` contains only the plan. If you gated elsewhere, either re-run the
    gate in THIS worktree or copy `docs/planning/.verdicts/` across from the checkout that gated. To
    avoid this entirely, create the worktree BEFORE the plan (§2 step 00). **ASK THE USER to run these — do NOT run the gate here: with no artifact, self-gating is indistinguishable from self-approving:**
    /unleashed-mail:gemini-review --ticket <T> --round <N> <plan>
    /unleashed-mail:codex-review --ticket <T> --round <N> <plan>
    then `/unleashed-mail:review-synthesis`, iterated to convergence.
    If the gate never ran **because a reviewer CLI was unavailable**, see **Unavailable reviewer** below.
  - *not an approving verdict* → `REQUEST_CHANGES`/`DISAGREEMENT`; iterate the plan + gate. If the reason
    names a reviewer as `MISSING`, that reviewer produced **no usable verdict** (it never ran, *or* its
    transcript was empty/unparseable) — see **Unavailable reviewer** below. Read the
    whole reason before acting: a `MISSING` reviewer **and** a rejecting one is **two** problems, and
    `verify` says so explicitly (`TWO SEPARATE problems: …`). Resolving either alone will not pass.
  - *plan has CHANGED since approval (digest mismatch)* → the plan was edited after approval
    (**approve-then-edit is blocked**); re-run the gate on the current plan.
  - *written for a different plan* → the artifact isn't this plan's; run the gate on `$PLAN`. This also
    appears when a `.verdicts/` directory was **copied between checkouts** and the recorded plan
    identity no longer matches this one — byte-identical plan content does not help, because the
    identity is compared as well as the digest. Re-run the gate here.

**Unavailable reviewer.** There is **no scripted waiver** (COREDEV-2493), and `verify` can never report on
CLI availability — it only ever inspects the artifact — so an unavailable reviewer reaches you as **one of
two different failures**, depending on how far the user got:

| What the user did | `verify` says |
|---|---|
| Never ran `/unleashed-mail:review-synthesis` | *no artifact* |
| Ran it, recording `<reviewer>=MISSING` | *not an approving verdict* … `<reviewer> recorded MISSING: no usable verdict` |

**`MISSING` means one of two things**, and `review-synthesis` records both the same way (its
normalization table maps *missing / empty / **unparseable** transcript* → `MISSING`):

1. the reviewer **never ran** — install/authenticate the CLI, or capture the review elsewhere;
2. it ran but the transcript was **empty or unparseable** — re-capture it (`agy` writes exactly 0 bytes
   from a non-TTY on failure, and needs `--print-timeout 28m`; a tiny transcript is a failure, not a
   verdict).

Check the transcript before assuming (1): the fix for (2) is a re-run, not an install. What they share —
and it is the load-bearing half — is that **no plan edit clears either**.

Both are the **same situation**. Do not read the second as a plan problem — iterating the plan cannot clear
a reviewer that never ran (that misread is the wedge COREDEV-2493 exists to remove).

**But do not over-correct**: if the OTHER reviewer ran and rejected, that rejection is a real plan problem
and stands on its own. `verify` reports that case as `TWO SEPARATE problems: …` — address the requested
changes *and* recover the missing reviewer. Neither alone passes the gate.

First **rule out a bad invocation**: a PTY-wrapped `agy -p "ping"` that answers a **`pong`** means the CLI is healthy
and the review call was wrong (`agy` needs `--print-timeout 28m`; a tiny transcript is a failure, not a
verdict). A healthy ping plus a failed review is a **you** problem, not an availability problem — fix the
flag and re-run.

> **Match the ping with `grep -qi pong` — case-insensitive, and do not require the `!`.** Across three
> measured runs `agy` answered `Pong! How can I help you today?`, a bare lowercase `pong`, and `Pong! Let
> me know how I can help you today.` A `Pong!`-exact check reports a **healthy** CLI as unavailable
> roughly one run in three — sending you down this recovery path (and escalating to the user) when the
> only real problem was a missing `--print-timeout 28m`. That is the exact misdiagnosis this step exists
> to prevent.

If it is genuinely unavailable, STOP and present the recovery choices to the **user** — install/authenticate
the CLI, capture the review on another machine, or explicitly direct the work outside `/implement`. That last
one is a **workflow exception, not a passed gate**: record it in the plan's progress log and do NOT emit an
approving Combined verdict. Never select or infer the exception yourself, and never self-waive.
See AGENT_CONTRACTS §2.
- **`verify` exits 0?** The artifact is an approving verdict bound to the plan's current bytes. Read the
  plan, re-verify the modern-standards recommendations are still current (via Context7), then proceed.

The `review-verdict.py verify` check is deterministic (raw-byte plan digest + dual-reviewer approval),
so it catches a stale/edited/absent/unrelated approval a prose check would miss. It stays
**workflow-level** fail-closed — `implement` declines to proceed; a skill cannot mechanically enforce a
tool boundary on its own (the gate deliberately drops the heavier PreToolUse-token approach as
over-engineering for this cooperative workflow). If `${CLAUDE_PLUGIN_ROOT}` is unset, use the
repo-relative `scripts/review/resolve-plan-gate.sh` — **not** `review-verdict.py` directly. Calling the
writer skips this gate's name resolution and its physical-containment guard, which is the whole point
of the fence (deep review, P2).

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
