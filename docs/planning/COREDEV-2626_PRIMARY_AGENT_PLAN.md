# Primary "Chief of Staff" Agent Plan

**Status:** Planning — round 2 (revised against codex round-1 REQUEST_CHANGES)
**Created:** 2026-07-30
**Last Updated:** 2026-07-30
**Ticket:** [COREDEV-2626](https://unleashedservices.atlassian.net/browse/COREDEV-2626) (Epic: COREDEV-2582)
**Split-out sibling:** [COREDEV-2627](https://unleashedservices.atlassian.net/browse/COREDEV-2627) — global activation, gated on evals
**Branch:** `feat/COREDEV-2626-primary-boss-agent` · worktree `.claude/worktrees/boss-agent`
**Base:** `origin/main` @ `ff83f02` (plugin v2.6.4, counts 21/21/0/1)

## Overview

The plugin ships 21 agents, 21 skills, a 5-reviewer panel, a deterministic synthesizer MCP server, and
a mandatory plan-review gate. All of it works. The problem is **activation**: the main thread sees only
a one-line `description` per asset, so the user must explicitly say "run the security reviewer", "use
Context7", "open a ticket". Every strong capability here is opt-in per prompt.

This plan adds a **22nd agent, `chief-of-staff`**, designed to be run as the main conversation thread so
the routing table is resident rather than latent.

> **Scope changed in round 2.** This ticket ships the agent **opt-in only**. The plugin-root
> `settings.json` that activates it globally moved to **COREDEV-2627**, gated on a passing
> boss-vs-stock eval. Rationale in §3.

## Approach

### 1. The mechanism — verified against the installed binary

A `settings.json` at the **plugin root** (sibling of `.claude-plugin/`, *not* inside it) with
`{"agent": "<name>"}` runs the main thread as that agent. Ground truth from
`strings ~/.local/share/claude/versions/2.1.220`:

| Evidence | Meaning |
| --- | --- |
| `Loaded settings from settings.json for plugin ` | plugin-root `settings.json` is read at load |
| `Failed to parse settings.json for plugin ` | parsed as JSON, with an error path |
| `Name of an agent (built-in or custom) to use for the main thread. Applies the agent's system prompt, tool restrictions, and model.` | the `agent` key and exactly what it applies |

Supported keys are **only** `agent` and `subagentStatusLine`; it takes priority over `plugin.json`; and
both `--agent` and project `.claude/settings.json` override it.

**This ticket does not create that file.** It is recorded here because it is the mechanism the agent is
designed for, and COREDEV-2627 will add it.

### 2. Opt-in usage (what this ticket delivers)

```bash
claude --agent unleashed-mail:chief-of-staff      # per session
```
or `"agent": "unleashed-mail:chief-of-staff"` in a project `.claude/settings.json`.

Bare-name resolution is confirmed working for the plugin's own `settings.json` (M0 Q5); the scoped form
above is the documented CLI-flag form for disambiguating across plugins.

### 3. Decisions

| # | Decision | Value | Notes |
| --- | --- | --- | --- |
| D1 | Rollout | **Opt-in now; global activation split to COREDEV-2627** | *Revised in round 2.* Codex: a hand-written body "cannot reliably reproduce undisclosed or evolving harness behavior", and M0 confirmed the built-in conduct sections are not surfaced under a main-thread agent. Activating globally before measuring is shipping a default-behavior change on assertion, not evidence. Splitting keeps the always-on goal but makes a passing A/B its trigger. |
| D2 | Autonomy | **Assertive on reads, confirm on writes** | Boundary rewritten in §5 — round 1 classified agents by *role label* instead of *effective capability*, which was wrong. |
| D3 | Personality | **Chief of staff** | Narrates the plan before executing, names which agent owns what and why, status at stage boundaries. Must conform to `AGENT_CONTRACTS.md` §13 (Agent Output Style), which **has already landed** — see Notes. |

### 4. The agent

`agents/chief-of-staff.md`. Frontmatter, every field load-bearing:

```yaml
---
name: chief-of-staff
description: >
  Main-thread orchestrator persona for UnleashedMail development. Routes user intent to the
  plugin's specialist agents and skills. Intended to be run AS the main thread
  (`claude --agent unleashed-mail:chief-of-staff`) — it is NOT a delegation target and must not
  be spawned as a subagent by another agent.
effort: xhigh          # mandatory — check_effort_policy hard-fails any other value (see C3)
model: inherit         # MUST NOT pin — see C2
skills:
  - agent-orchestration   # preload the CANONICAL registry rather than copying it (see §6)
# NO `tools:` key      # MUST NOT set — see C1
---
```

### 5. The confirmation boundary (D2) — corrected

Round 1 listed "planners and diagnostics" as read-only. **That was wrong**, and codex caught it:

* `modern-standards-planner` **omits `tools:`**, so it inherits Write, Edit, Bash, Agent and MCP.
* `xcode-build-fixer` and `graph-api-debugger` carry Write/Edit and may apply mechanical fixes.
* `jira-manager` mutates Jira by design.

Classification is therefore by **effective capability**, never by role label:

| Acts freely | Confirms first |
| --- | --- |
| Read, Grep, Glob, Explore | Any agent whose effective tool set includes Write/Edit/Bash-mutating |
| Context7, WebFetch, WebSearch | `db-engineer`, `logic-engineer`, `ui-engineer`, `ai-engineer`, `tester`, `code-simplifier`, `docs-engineer`, `ci-engineer`, `release-manager` |
| `git status/log/diff/fetch/show` | `modern-standards-planner`, `xcode-build-fixer`, `graph-api-debugger` (write-capable despite planner/diagnostic labels) |
| Read-only reviewers: `security-reviewer`, `concurrency-reviewer`, `ux-perf-reviewer`, `accessibility-auditor`, `prompt-review` | `jira-manager` (mutates Jira) |
| Personas: `smb-entrepreneur`, `enterprise-stakeholder` (`tools: Read, Grep, Glob`) | `git commit/push`, branch/worktree creation, PR create/merge |
| Reading plans, verdicts, contracts | Writing plan docs; editing any tracked file |

> **This is a behavioral convention, not an enforced security boundary.** Because the agent omits
> `tools:` (C1), it inherits the entire tool surface; nothing mechanically prevents a write. The plan
> states this plainly rather than implying enforcement. Consent scope, lifetime, and re-confirmation on
> scope expansion are specified in the agent body; COREDEV-2627 owns precedence against COREDEV-2584's
> future armed autonomous mode.

### 6. Routing — preload, do not duplicate

Round 1 proposed copying a dispatch table into the agent body. That creates a **second semantic
registry** with no equality check, free to drift from `skills/agent-orchestration/SKILL.md` (which *is*
CI-enforced set-equal to `agents/*.md`).

Instead: `skills: [agent-orchestration]` preloads the canonical SKILL.md body at startup. The agent body
carries only what the skill does not — intent-recognition triggers, the confirmation boundary, and
baseline conduct (§8). If any routing table is ever inlined, it requires a drift guard in
`validate-plugin-assembly.py`.

### 7. Concurrency and the `Workflow` tool

**Requirement (user, 2026-07-30): the agent must have `Workflow` access, and multi-agent work must run
concurrently rather than one at a time.**

**Access is automatic.** Because the agent omits `tools:` (C1) it inherits the session's entire tool
surface, `Workflow` included — nothing needs to be listed. (Worth noting the inverse is a CI hole:
COREDEV-2584 §4.10 finding 1 proves that *adding* `, Workflow` to an agent's `tools:` passes
`validate-plugin-assembly.py --strict` with no warning, because the difflib guard finds no near match and
unknown non-MCP entries are accepted. Not this ticket's to fix, but it is why access must be reasoned
about rather than assumed from the frontmatter.)

**Concurrency is mandated at three levels**, and the agent body states each as a default, not an option:

| Level | Mechanism | Cap |
| --- | --- | --- |
| Independent `Agent` dispatches | all in **one message**, never sequential awaits | session subagent budget |
| Within a workflow | `pipeline()` by default; `parallel()` only when a stage genuinely needs every prior result | `min(16, cpu_cores - 2)` — **10 on this machine** (12 cores) |
| Multiple workflows | `Workflow` returns immediately with a task id, so independent workflows are fired together and awaited via notification | shared agent counter / token budget |

The failure this guards against is a barrier that isn't needed: `parallel()` blocks on the slowest item
in every stage, so a 5-item fan-out where the slowest takes 3× the fastest wastes two-thirds of the fast
agents' wall-clock. `pipeline()` lets item A reach stage 3 while item B is still in stage 1.

**Boundary — `Workflow` must NOT orchestrate the review panel.** This is where the requirement meets a
documented High-severity gap. COREDEV-2584 §4.10 verified four collisions if a second orchestrator
dispatches reviewers:

1. CI does not notice a `Workflow` grant (above).
2. `scripts/review/reviewer-roster.sh:51` hardcodes a five-name allowlist — an unknown name yields
   `ROSTER-INPUT-INVALID` and **exit 4**, which `swift-reviewer` treats as uncertainty, never a pass.
3. `SubagentStart`/`SubagentStop` capture hooks match a hardcoded five-name regex
   (`hooks/hooks.json:121,133`); a Workflow-dispatched agent outside those five produces **no capture and
   no signal**.
4. The "at most ONE spawn per reviewer per review" bound is prose in the orchestrator's working memory
   with no on-disk ledger — two concurrent orchestrators are two ledgers, so the bound cannot hold.

So the split the agent body enforces:

* **`Workflow` is for breadth** — audits, sweeps, migrations, multi-file research, adversarial
  completeness passes. Fan out freely and concurrently.
* **`swift-reviewer` remains the sole orchestrator of the review panel.** The agent dispatches *to* it
  and never reproduces the panel through a workflow. This is the §9.2 invariant, and COREDEV-2584 owns
  writing it into AGENT_CONTRACTS.

**Honest limit on the M0 evidence.** The depth results in *M0 empirics* below were measured on the
**`Agent`-tool** dispatch path. COREDEV-2584 records that Workflow-dispatched agents do **not** count against the session subagent
budget, which means they are a different accounting path — so Q1's "no depth cost" result **does not
automatically extend to `Workflow`**. Stated rather than assumed, given round 1 over-claimed twice. If
the agent is ever expected to nest workflows under a gated pipeline, that path needs its own
discriminating probe.

**One constraint the user should know about.** The `Workflow` tool's own contract requires *explicit*
user opt-in per invocation ("ultracode" in the prompt, an ultracode session, or the user asking for a
workflow in their own words). The agent therefore **cannot self-authorize** a workflow, which is in
tension with the "stop directing me" goal. What it can do without opt-in: dispatch every independent
`Agent` call in parallel (the common case), and *propose* a workflow with a rough cost when one would
genuinely help. Standing opt-in comes from the user enabling ultracode.

## Hard constraints

Each is a **silent** session-breaker — nothing errors, behavior is just quietly wrong.

* **C1 — MUST omit `tools:`.** On a main-thread agent a `tools:` allowlist restricts the *entire user
  session*, stripping every MCP server (Atlassian, Context7, review-synthesizer). Only `jira-manager`
  and `modern-standards-planner` omit it today; this becomes the third.
* **C2 — MUST be `model: inherit`.** `model:` applies to the main thread and would override the user's
  `/model` in every session.
* **C3 — MUST pin `effort: xhigh`.** `check_effort_policy` (`validate-plugin-assembly.py:350`)
  hard-fails any agent or skill that is not `xhigh`, so this is not optional. **Consequence deferred to
  COREDEV-2627:** on an always-on main agent this may clamp a user's `max` session down to `xhigh`, with
  no `inherit` escape as C2 has. Harmless while opt-in — passing `--agent` opts into its effort too.
* **C4 — MUST NOT set `memory:`.** It auto-enables Read/Write/Edit as a side effect. **Now a validator
  assertion**, not just prose (round 1 listed it as a constraint but never checked it).
* **C5 — the body REPLACES the built-in conduct sections.** See §9.1.

## CI / assembly impact

| Site | Change |
| --- | --- |
| `README.md:5` bold counts line | `21 agents` → `22 agents` |
| `.claude-plugin/plugin.json` description | "21 specialized agents" → 22 |
| `.claude-plugin/marketplace.json` description | same string, second copy |
| `CLAUDE.md:17` | the `agents/ 21 subagents` box |
| `skills/agent-orchestration/SKILL.md` "## Agent Registry" | **required** — set-equality enforced (`validate-plugin-assembly.py:308`) |
| `AGENT_CONTRACTS.md` §11 | model/effort tier row for the new agent |
| `AGENT_CONTRACTS.md` (new §) | boss boundary vs. `swift-reviewer` and vs. Workflow (§9.2) |
| `scripts/validate-plugin-assembly.py` | new `settings.json` contract (below) |
| `CHANGELOG.md` + `plugin.json` | version bump — see Notes on the 2.7.0 collision |

**All of the above land in ONE commit with the agent** (see Milestones) — round 1 deferred the registry
row and counts to a later milestone, which would have left the trunk red in between.

### New validator coverage — hard-fail, not warn

`validate-plugin-assembly.py` has no `settings.json` awareness. Round 1 proposed warning on unknown
keys; codex correctly noted that `{"agnt": "chief-of-staff"}` would then pass `--strict` while doing
nothing — the exact silent failure this is meant to prevent. The contract **hard-fails** on:

1. A non-object root.
2. Missing, non-string, or empty `agent`.
3. Unknown keys (at minimum under `--strict`).
4. A namespace prefix that does not exactly match the plugin manifest `name`.
5. An `agent` that does not resolve to an existing `agents/*.md`.
6. A target that sets `tools:` (C1), a non-`inherit` `model:` (C2), or `memory:` (C4).
7. An invalid `subagentStatusLine` type, if present.

Tests in `scripts/tests/test_validate_plugin_assembly.py` using temporary plugin roots, each
mutation-proved. Note the file must tolerate `settings.json` being **absent** — that is the state
throughout this ticket, since activation ships in COREDEV-2627.

## Risks

### 9.1 The body replaces built-in conduct — measured, claim narrowed

Under a main-thread agent, the `Harness` and `Delivering work` sections were **not surfaced**, while the
stock control reported both (M0 Q3).

**Claim scope, per codex.** The evidence supports *"these two named conduct sections were not
surfaced"* — **not** a wholesale "all built-in instructions are replaced". The probe used post-hoc
discriminator selection and model self-report, both weak instruments. The plan no longer asserts the
stronger claim. What must be restated in the body is derived from the two confirmed sections plus
first-principles conduct:

* **Delivering work** — act on the actual request; don't silently narrow, widen, or transform scope;
  finish the whole task; report completion only when genuinely done; state what was left out and why.
* **Harness** — prefer dedicated file/search tools over shell equivalents; parallel independent tool
  calls; `file_path:line_number` references; treat a denied permission as a signal to adjust, not retry.
* **Faithful reporting** — failing tests reported with output; skipped steps named.
* **Confirmation discipline** for hard-to-reverse and outward-facing actions (the substrate D2 rests on).

**Mitigation is now structural, not just textual:** global activation cannot ship until a boss-vs-stock
A/B passes (COREDEV-2627). Opt-in exposure is bounded to sessions the user explicitly opts into.

### 9.2 Two orchestrators

`agent-orchestration` states "exactly one orchestrator, one verdict" — `swift-reviewer` owns the review
pipeline and its synthesis. `chief-of-staff` **dispatches to** it and must never re-synthesize or
re-adjudicate its findings. COREDEV-2584 §8 raises the same collision for ultracode's Workflow
orchestration. Both boundaries go in AGENT_CONTRACTS.

### 9.3 The agent is also spawnable

Every `agents/*.md` is delegatable, so `chief-of-staff` appears in the subagent list and could be spawned
recursively. Mitigated **by wording only** — the `description` states it is a main-thread persona, not a
delegation target. There is no frontmatter key that makes an agent non-delegatable.

### 9.4 Namespacing

M0 found that from **inside a subagent**, plugin agent types resolve namespaced (`plugin:agent`); bare
names fail with `Agent type '<name>' not found`. Any agent name the body or the orchestration skill
tells a subagent to spawn must use the scoped form, or every delegation fails at depth ≥ 1.

## M0 empirics — evidence

### Q1 — spawn-depth cost: **NO** (re-proved with a discriminating design)

Round 1's experiment was **not discriminating** and its conclusion was unsupported. Claude Code's
default depth is **3** (`AGENT_CONTRACTS.md:260`), so `main → mid → leaf` succeeds under *both*
hypotheses — no-cost reaches depth 2, costs-a-level reaches depth 3, and both fit. Codex caught this.

Re-run pinning `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, with a negative control proving the pin bites:

| Pin | Control (no boss) | Boss active |
| --- | --- | --- |
| **2** | `MID_SAW=LEAF_OK` | `MID_SAW=LEAF_OK` |
| **1** | `MID_NO_AGENT_TOOL` | `MID_NO_AGENT_TOOL` |

Identical in both arms at both limits; at 1 the `Agent` tool is withheld exactly as `AGENT_CONTRACTS.md:262`
documents. **A main-thread agent consumes no spawn-depth level.**

Panel width separately verified at the real shape — `boss(main) → panel-lead → 5 concurrent reviewers`
returned `PANEL=REV1_OK,REV2_OK,REV3_OK,REV4_OK,REV5_OK`. Relevant because
`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` and `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` are budgets separate
from depth.

### Q2–Q5

| # | Question | Answer | Evidence |
| --- | --- | --- | --- |
| Q2 | Project `CLAUDE.md` still loads? | **YES** | Boss answered `ZARQUON-7734`, present only in the workdir CLAUDE.md |
| Q3 | Built-in conduct sections surfaced? | **NO** (narrowed — see §9.1) | Control: `Harness` YES, `Delivering work` YES. Boss: NO to both |
| Q4 | Plugin hooks fire? | **A `SessionStart` hook fired** | `HOOK_FIRED` marker written. **Narrowed:** one hook on one event does not prove the whole hook/gate apparatus is unaffected — M6 runs `test-hooks.sh` for that |
| Q5 | Bare vs scoped `agent` value | **Bare works** in plugin `settings.json` | `{ "agent": "probe-boss" }` activated the persona |

**Reproducible fixture is a deliverable.** Round 1 deleted its probes, which codex flagged. M2 commits
the probe plugin + runner under `scripts/tests/` (or wires it into COREDEV-2598) so Q1/Q3 are regression
guards — both are answers a future CLI release could silently change.

## Milestones

- [x] **M0 — Empirics.** Q1 re-proved discriminatingly; Q3/Q4 claims narrowed.
- [ ] **M1 — Plan Review Gate.** Round 1: codex REQUEST_CHANGES (valid, incorporated); gemini **VOID** —
      the isolated wrapper reviews `HEAD` and the plan was untracked, so it reviewed nothing. Round 2
      runs both arms against the committed, re-snapshotted plan.
- [ ] **M2 — Validator + fixture first.** The `settings.json` contract (7 hard-fails), mutation-proved,
      plus the committed depth/persona probe fixture. Lands before the agent so the wiring is guarded
      the moment it exists — and is safe standalone because `settings.json` is absent.
- [ ] **M3 — The agent, landed atomically.** `agents/chief-of-staff.md` **together with** its Agent
      Registry row, AGENT_CONTRACTS §11 tier entry, and all four count/description sites, in ONE commit.
      Splitting these leaves the trunk red.
- [ ] **M4 — Contracts + docs.** AGENT_CONTRACTS §9.2 boundaries + §13 output-style conformance; README
      section documenting opt-in invocation; CHANGELOG.
- [ ] **M5 — Version bump.** After M3/M4, and after reconciling the 2.7.0 collision (Notes).
- [ ] **M6 — Verification.** Six repo gates + `shellcheck` + `claude plugin validate --strict .` on CLI
      2.1.220, `bash scripts/test-hooks.sh` (the real Q4 check), and a scratch-installed session via
      `claude --plugin-dir` proving the agent loads and routes. Runs **after** the version bump.
- [ ] **M7 — Hand off to COREDEV-2627** for eval-gated global activation.

## Scope guards

* **Does not** create the plugin-root `settings.json` — that is COREDEV-2627.
* **Does not** implement COREDEV-2584's autonomous/no-prompt mode. Plugin `settings.json` supports only
  `agent` and `subagentStatusLine` and cannot grant permissions; 2584's `PermissionRequest` design stands.
* **Does not** modify `hooks/hooks.json`.
* **Does not** alter the review pipeline, the synthesizer, or any reviewer agent.
* Skills/commands/MCP counts stay `21/0/1`; only the agent count moves (21 → 22).
* `subagentStatusLine` is out of scope.

## Testing

| Gate | Command |
| --- | --- |
| Assembly | `python3 scripts/validate-plugin-assembly.py --root . --strict` |
| Hooks | `python3 scripts/validate-hooks.py --root . --strict --require-manifest` |
| Version sync | `VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh` |
| Hook harness | `bash scripts/test-hooks.sh` |
| MCP suite | `python3 -m unittest discover -s mcp/review-synthesizer/tests` |
| Scripts suite | `python3 -m unittest discover -s scripts/tests` |
| Shell | `shellcheck -s bash -S warning scripts/*.sh scripts/lib/*.sh scripts/review/*.sh .githooks/pre-commit` |
| Load | `claude plugin validate --strict .` + `claude --plugin-dir` scratch session |

New tests: the seven `settings.json` assertions, each mutation-proved, plus the committed probe fixture.

## Notes

* **Sibling reconciliation (all verified at `ff83f02`):**
  * **COREDEV-2602 has already landed** — `AGENT_CONTRACTS.md:465 ## 13. Agent Output Style`. Round 1's
    "consider landing 2602 first" was stale. D3's voice must **conform to §13**, not re-invent it.
  * **COREDEV-2584 already claims `2.7.0`** (`AUTONOMOUS_END_TO_END_PLAN.md:13`) and moves counts to
    `21/22/0/1`; this ticket moves them to `22/21/0/1`. **Both cannot claim 2.7.0 or edit the count sites
    unreconciled.** Resolve with `release-manager` before M5. 2584 is currently paused at a
    request-changes gate.
  * **COREDEV-2598** — `claude --plugin-dir` already provides the scratch-install mechanism. Extending it
    with this ticket's fixture is an explicit M2 deliverable, not an optional "worth folding in".
  * **COREDEV-2599** — `claude plugin eval` exists natively with an automatic no-plugin baseline arm. It
    is a **prerequisite of COREDEV-2627**, not a note.
* **Gate defect found while running M1 (needs its own ticket):**
  `scripts/review/isolated-agy-review.sh` builds its disposable tree from `git rev-parse HEAD`, so an
  **untracked** review target is silently absent. Round 1 returned `EXIT=0 BYTES=3698 TREE=clean
  VERDICT=REQUEST_CHANGES` — a healthy-looking round on an artifact the reviewer never read. Had it said
  APPROVE the gate would have passed on nothing. It should fail closed when the target is missing from
  the disposable checkout.
* Local `main` was **62 commits stale** (v2.5.2 vs. origin v2.6.4) at session start; all findings are
  against `origin/main` @ `ff83f02`.
* Deliberately **not** using a `SessionStart`/`UserPromptSubmit` hook to inject a persona — the native
  `agent` key is supported, versioned, and user-overridable; a hook-injected persona is none of those.

## Progress Log

### 2026-07-30
- Verified the main-thread-agent mechanism against installed CLI 2.1.220 (binary strings + docs).
- Re-verified plugin state at `origin/main`; confirmed frontmatter conventions and that
  `validate-plugin-assembly.py` has no `settings.json` coverage.
- Created COREDEV-2626; worktree + branch established; M0 round 1 run.
- **Gate round 1:** codex **REQUEST_CHANGES** (valid, 386KB, line-cited) · gemini **VOID** (wrapper
  reviewed `HEAD`, plan untracked).
- **Codex critical #1 was correct: round 1's Q1 experiment could not falsify its own hypothesis.**
  Re-ran with `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` pinned plus a negative control; conclusion survives
  on evidence that could have refuted it. Also re-verified panel width at five concurrent reviewers.
- Verified three further codex claims independently — depth default 3, §13 already landed, 2584's 2.7.0
  claim. All correct.
- **Round-2 revisions:** D1 split to COREDEV-2627 (opt-in here, eval-gated activation there) · §5
  confirmation matrix reclassified by effective capability · validator moved from warn to seven
  hard-fails incl. C4 · routing preloaded via `skills:` instead of duplicated · milestones re-ordered to
  land the agent atomically · Q3/Q4 claims narrowed · fixture retention made a deliverable.
- **Added §7 (Workflow + concurrency)** on user requirement: `Workflow` access is automatic via the
  omitted `tools:`; concurrency mandated at all three levels (parallel `Agent` dispatch in one message ·
  `pipeline()` over `parallel()` inside a workflow · concurrent workflow invocations). Bounded by the
  COREDEV-2584 §4.10 collisions — `Workflow` is for breadth, `swift-reviewer` stays the sole panel
  orchestrator. Recorded that Q1's depth result does **not** extend to the Workflow dispatch path.
- **Next:** commit + re-snapshot, then gate round 2 on both arms.
