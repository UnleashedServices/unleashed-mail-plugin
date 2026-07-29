# Opus 5 Alignment Plan

**Status:** Planning — awaiting dual plan-review gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29
**Ticket:** `COREDEV-2583` — Opus 5 alignment: effort pinning, three-tier model policy, validator
coverage, CI pin
**Epic:** `COREDEV-2582` — Opus 5 readiness and autonomous end-to-end mode
**Branch:** `feat/COREDEV-2583-opus5-alignment`
**Siblings:** `AUTONOMOUS_END_TO_END_PLAN.md` (`COREDEV-2584`), `DECISION_JOURNAL_PLAN.md`
(`COREDEV-2585`) — this plan lands **first**; neither sibling may be implemented before it.

---

## 1. Context

The plugin was authored against Claude Code as it behaved under Opus 4.8. Opus 5 shipped alongside a
run of Claude Code releases that changed defaults the plugin silently depends on. A review of the
shipped assets against the current documentation (code.claude.com/docs, re-verified 2026-07-29 against
CLI 2.1.220) found the plugin **functionally healthy but drifted**:

- All six gates pass on the current tree: `validate-plugin-assembly --strict` (21/21/0/1),
  `validate-hooks --strict --require-manifest` (10 events), `validate-version-sync` (2.5.3),
  `test-hooks.sh` (302 passed), the synthesizer suite (191), the scripts suite (243).
- All 21 agents use exactly the current documented sub-agent frontmatter key set.
- All 10 declared hook events are real, and every agent's declared `tools:` survives the new
  background-subagent tool filter (verified per-agent — no zero-tool spawn failures).

What has drifted is **model/effort policy, validator coverage, and documentation**. None of it is
caught by CI, because the validators check counts and key syntax — not whether the policy the docs
describe is the policy the assets implement. This is the same class of defect the model-tier check
was added to catch (`check_model_tiering`, added after the docs-engineer/jira-manager/release-manager
drift went unnoticed), and it has recurred on a new axis.

**Maintainer decisions locked before this plan was written** (do not re-litigate in review):

| Decision | Value |
|---|---|
| Effort floor | **Nothing below `xhigh`, ever.** Cost explicitly accepted. |
| Model tiers | **Three**, see §4.2 |
| Provider | **Direct Anthropic API only** — no Bedrock / Foundry / GCP |
| Org effort caps | Confirmed **not** in play |
| Long context | **In scope** — `opus[1m]` must be a legal value |
| CLI pin | **2.1.220** |

## 2. Scope

**In:** effort pinning across agents + workflow skills; the three-tier model policy in
`AGENT_CONTRACTS.md` §11 and its CI enforcement; four validator gaps in
`scripts/validate-plugin-assembly.py`; the CI CLI pin; declaring the subagent spawn-depth dependency;
four verified documentation defects; version bump + CHANGELOG.

**Out:** the autonomous end-to-end mode and the decision journal (separate tickets — this plan must
not touch `hooks/hooks.json`, and must not change the asset counts). No new agents or skills. Asset
counts stay **21 / 21 / 0 / 1**.

**Explicitly out of scope after verification:** the background-subagent tool filter. Each of the 21
agents' `tools:`/`disallowedTools:` lists was checked against the documented background-subagent
built-in allowlist; all survive. No change is required and none should be made.

## 3. Guiding principle

> **The policy in the docs and the policy in the assets must be the same object, and CI must be able
> to tell.** Every item below either aligns the two or teaches a validator to notice when they
> diverge. A fix that changes an asset without extending the check that would have caught it is
> incomplete.

Corollary, inherited from the repo's existing posture: where a gate cannot determine an answer, it
fails **closed** and says so. New in this plan — where a *silent environmental override* can defeat a
guarantee the plugin makes (§4.7), the plan documents it honestly rather than implying a guarantee
the plugin cannot deliver.

---

## 4. Findings, fixes, and proofs

### 4.1 — Effort is unset everywhere, on every asset (High)

**Root cause.** `effort:` is a real sub-agent and skill frontmatter key
(`low|medium|high|xhigh|max`; Opus 5 and Sonnet 5 support all five; default `high`). The validator
already accepts it — `KNOWN_AGENT_KEYS` at `scripts/validate-plugin-assembly.py:43` includes
`"effort"` — but **zero of the 21 agents and zero of the 21 skills set it**. Every agent therefore
runs at whatever the session happens to carry, including `low`.

This is sharpest at the review gate. `skills/codex-review/SKILL.md:28` forces
`model_reasoning_effort=xhigh` on the *external* Codex reviewer and documents a silent reset to `low`
as an under-powered gate with no error to notice — while the plugin's own five reviewers and its
verify gate have no equivalent protection.

**Fix.** Pin `effort: xhigh` in the frontmatter of:
- all 21 `agents/*.md`
- the three invoke-only workflow skills: `skills/brainstorm/SKILL.md`,
  `skills/implement/SKILL.md`, `skills/pr-review/SKILL.md`

The 18 auto-triggering knowledge skills are **left alone**: their bodies are injected context, not an
execution step, and pinning there adds churn without changing behaviour under a session that is
already at or above `xhigh`.

**Note on semantics, which the implementer must not get wrong.** Frontmatter effort is an
**override, not a floor** — it moves the level in *both* directions. Under the locked "never below
`xhigh`" rule this is correct and desirable: a session launched at `low` is pulled *up*. But it also
means a session at `max` is pulled *down* to `xhigh` for these agents. That is the accepted trade,
and it is the reason the pin is deliberate rather than incidental.

**Proof.** A new validator assertion (§4.3) fails when any agent or workflow skill omits
`effort: xhigh`. Revert any single pin → the validator fails naming that file.

### 4.2 — §11 Model Tiering Policy: two tiers become three (High)

**Root cause.** `AGENT_CONTRACTS.md:354` §11 files every agent under one of two tiers
(`AGENT_CONTRACTS.md:364` is the table header). The three agents that own the highest-consequence
review categories are all in the `sonnet` row:

- `security-reviewer` — credentials, OAuth, injection, CI
- `prompt-review` — AI prompt/call-site safety, injection, PII-in-logs
- `concurrency-reviewer` — the declared **correctness owner**, absorbing the logic and
  error-handling findings the other reviewers explicitly punt

Separately, §11's stated rationale is a **cost** argument ("cost-efficient, consistent breadth"; "a
costlier session model is wasted", `AGENT_CONTRACTS.md:370-375`). Cost is no longer a constraint, so
that rationale no longer holds on its own terms and must be rewritten rather than left standing.

**Fix.** Three tiers:

| Tier | `model:` | Agents | Count |
|---|---|---|---|
| Deep-review specialists | `opus` | security-reviewer, prompt-review, concurrency-reviewer | 3 |
| Orchestrator + implementation/diagnostic | `inherit` | swift-reviewer, ai-engineer, ci-engineer, code-simplifier, db-engineer, graph-api-debugger, logic-engineer, modern-standards-planner, tester, ui-engineer, xcode-build-fixer | 11 |
| First-pass reviewers, personas, fixed-scope managers | `sonnet` | accessibility-auditor, ux-perf-reviewer, docs-engineer, enterprise-stakeholder, jira-manager, release-manager, smb-entrepreneur | 7 |

3 + 11 + 7 = 21. Only three frontmatter values change:
`agents/security-reviewer.md:11`, `agents/prompt-review.md:16`, `agents/concurrency-reviewer.md:11`,
each `sonnet` → `opus`. The other 18 keep their current value.

Rewrite the §11 rationale prose to the capability argument that now applies, and add a one-line
effort policy: *every agent and workflow skill pins `effort: xhigh`; there is no effort tiering.*

**Parser check (verified, not assumed).** `_TIER_ROW`
(`scripts/validate-plugin-assembly.py:247`) matches any `| … | \`model\` | agents |` row, capturing
`[a-z]+` from inside the backticks — `opus` matches. The only structural assertion in
`check_model_tiering` (`:251`) is `rows < 2`. **A third tier row parses with no parser change.**

**Proof.** `check_model_tiering` already asserts frontmatter equals the tier table in both
directions. Move any one agent between rows without editing its frontmatter → strict validation
fails.

### 4.3 — `check_model_tiering` does not know about effort (High)

**Root cause.** The function at `scripts/validate-plugin-assembly.py:251` asserts model-tier
alignment only. With effort now load-bearing (§4.1), an agent silently losing its `effort: xhigh` pin
— or a new agent landing without one — is invisible to CI. That is exactly the failure mode this
function was written to end, one axis over.

**Fix.** Extend it (or add a sibling `check_effort_policy`) to assert:
1. every `agents/*.md` declares `effort: xhigh`;
2. each of the three workflow skills declares `effort: xhigh`;
3. §11's effort policy line is present and states `xhigh`.

Keep it a **hard** assertion, not a warning — a silent under-powered gate is precisely the defect.

**Proof.** New unit cases in `scripts/tests/test_validate_plugin_assembly.py` mirroring the existing
tiering tests (which already prove the model axis, e.g. the `jira-manager`/`opus` mismatch case).
Each new case must fail when the fix is reverted.

### 4.4 — `MODEL_ALIASES` and the model-id regex reject legal values (High — blocker for long context)

**Root cause.** `scripts/validate-plugin-assembly.py:48`:

```python
MODEL_ALIASES = {"sonnet", "opus", "haiku", "fable", "inherit"}
```

and the id pattern `re.fullmatch(r"[a-z]+-[a-z0-9-]*\d[a-z0-9-]*", model)`.

Sub-agent `model:` accepts *the same values as the `--model` flag*, which includes `best`, `default`,
`opusplan`, and the bracketed long-context aliases `opus[1m]` / `sonnet[1m]`. None of the bracketed
forms match the regex (no `[`/`]` in the character classes) and none of the extra aliases are in the
set. **`model: opus[1m]` fails the plugin's own CI.**

Long context is in scope for this project, so this is a live blocker rather than a theoretical gap.

**Fix.** Add `best`, `default`, `opusplan` to `MODEL_ALIASES`, and accept an optional bracketed
context suffix on both aliases and ids. The regex must stay **anchored at both ends** — the
`re.fullmatch` (not `re.match`) discipline introduced by COREDEV-2503 F10 exists to stop
`claude-opus-4-8 rm -rf` and trailing-newline injection from passing, and the suffix must not
reintroduce that hole.

**Proof.** Extend `scripts/tests/test_validate_plugin_assembly.py`: accept `opus[1m]`,
`sonnet[1m]`, `claude-opus-5`, `best`, `opusplan`; continue rejecting `claude-opus-5 rm -rf`,
`claude-opus-5; evil`, `claude-opus-5\nmalicious`, and a malformed suffix such as `opus[1m` or
`opus[]`.

### 4.5 — `KNOWN_TOOLS` is stale and actively false-rejects two current tools (Medium)

**Root cause.** `scripts/validate-plugin-assembly.py:53`. An unknown non-MCP entry is normally
accepted, but the `difflib.get_close_matches(..., cutoff=0.7)` typo guard rejects anything that looks
like a near-miss of a known name. Executing that guard against the current tool surface:

| Current tool | Result today |
|---|---|
| `TaskOutput` | **rejected** as a typo of `BashOutput` |
| `EnterPlanMode` | **rejected** as a typo of `ExitPlanMode` |
| `ToolSearch`, `Monitor`, `SendMessage`, `TaskCreate/Get/List/Update/Stop`, `Artifact`, `EnterWorktree`, `ExitWorktree`, `PowerShell`, `Workflow`, `ScheduleWakeup`, `WaitForMcpServers`, `EndConversation`, `CronCreate/Delete/List` | accepted only as *unknown* |

Additionally `MultiEdit` is still listed as known but is no longer a real tool — and it appears in a
live deny-list at `agents/jira-manager.md:15`, where it is now a no-op line.

**Fix.** Refresh `KNOWN_TOOLS` to the current built-in set, remove `MultiEdit`, and leave the
`STALE_TOOLS` hard-reject for `Task` intact (the `Agent`-not-`Task` rule is unrelated and still
correct).

**Proof.** A unit case asserting every name in the refreshed set validates clean, plus explicit
regression cases for `TaskOutput` and `EnterPlanMode` that fail if the stale set is restored.

### 4.6 — Skills have no unknown-key check (Medium)

**Root cause.** `check_agent_fields` (`scripts/validate-plugin-assembly.py:80`) is agent-only *by
design* — `allowed-tools` is legal for skills and illegal for agents, so the check cannot be shared.
The consequence is that **skills have no key validation at all** beyond `name`/`description`.

This is asymmetric with the bug the agent check exists to prevent. The agent check was written
because `allowed-tools` in an agent is silently ignored and nullifies every tool restriction. The
mirror-image defect is unguarded: a skill written with camelCase `disallowedTools:` instead of kebab
`disallowed-tools:` passes CI and silently does nothing. Skills now carry seventeen documented keys
(`name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`,
`user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`,
`background`, `hooks`, `paths`, `shell`), several of which are new and easy to misspell.

The sibling autonomous-mode ticket depends on `disallowed-tools` working correctly, which makes this
a prerequisite rather than a nicety.

**Fix.** Add `KNOWN_SKILL_KEYS` and a `check_skill_fields` mirroring the agent path, including a
targeted hint when a camelCase agent-style key (`disallowedTools`, `allowedTools`) appears in a
skill.

**Proof.** Unit cases: a skill with `disallowedTools:` fails with the camelCase hint; a skill using
every legal key validates clean.

### 4.7 — Plugin-ignored frontmatter keys are accepted without warning (Low, but load-bearing for the sibling ticket)

**Root cause.** `KNOWN_AGENT_KEYS` (`:43`) accepts `permissionMode`, `mcpServers`, and `hooks`.
Claude Code **ignores all three for plugin sub-agents** for security reasons. No agent uses them
today, so nothing is broken — but these are precisely the keys someone reaches for when building an
autonomous mode, and the failure is silent.

**Fix.** Keep them in the known set (they are legal *keys*, just inert here) and emit a warning when
they appear, naming the plugin-subagent exemption and pointing at the alternatives.

**Proof.** Unit case: an agent declaring `permissionMode: bypassPermissions` produces the warning.

### 4.8 — CI pins a Claude Code that cannot run Opus 5 (High)

**Root cause.** `.github/workflows/plugin-ci.yml:85` pins `CLAUDE_CODE_VERSION: 2.1.209`. **Opus 5
requires 2.1.219 or later.** The pin drives `claude plugin validate`, the workflow's own
authoritative schema check, so the schema authority is eleven releases behind the floor the plugin
now targets. The pin is manual — there is no `package.json`, so Dependabot does not cover it (the
comment at `:82-84` says as much).

**Fix.** `2.1.209` → `2.1.220`, and record the minimum-CC-version floor durably (README plus
`CLAUDE.md`), since nothing in `plugin.json` expresses it.

**Pre-verified.** CLI 2.1.220 was installed and both validation steps were run against this tree
before this plan was written: `claude plugin validate --strict .` → passed; `claude plugin validate
.claude-plugin/plugin.json` → passed with exactly the one pre-existing expected warning (root
`CLAUDE.md` not loaded as project context), which `:93-96` already documents. **The bump surfaces no
new schema findings.**

**Note for the reviewer.** `2.1.220` is the `latest` dist-tag; `stable` is `2.1.212`. Pinning ahead
of the stable channel is a deliberate choice, taken because `stable` is below the Opus 5 floor.

### 4.9 — The five-reviewer panel depends on an undeclared, recently-changed default (High)

**Root cause.** `agents/swift-reviewer.md` spawns five reviewer subagents (it is the only agent with
`Agent` in a `tools:` **allowlist**, at `:13` — `modern-standards-planner` also holds `Agent`, by
*inheritance*, since it omits `tools:` entirely and denies only `mcp__github`, which
`AGENT_CONTRACTS.md:326` records as deliberate). The orchestrator sits at depth 1, the reviewers at 2.
The subagent spawn-depth default has moved three times:

| Claude Code | Default depth | Effect on the panel |
|---|---|---|
| ≤ 2.1.216 | 5 (fixed) | works |
| 2.1.217 – 2.1.218 | **1** | **panel silently dead** |
| ≥ 2.1.219 | 3, tunable via `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | works |

At the depth limit Claude Code **withholds the `Agent` tool**. `swift-reviewer` would then perform
the review itself, the five `SubagentStop` capture hooks would never fire, Step 5 would read zero
captures — and it would emit a verdict that reads exactly like a five-reviewer panel. The failure is
silent, and wrong in the most expensive direction.

Nothing in the plugin declares, detects, or documents this dependency.

**Fix.** Two parts, both required:
1. **Document** the dependency (minimum CC version and the `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`
   requirement) in `AGENT_CONTRACTS.md` §5 alongside the review pipeline.
2. **Detect it at the gate.** `swift-reviewer` Step 5 already distinguishes a reviewer that returned
   `BLOCKED` from one that returned `[]`. Extend the same reasoning: if the panel was dispatched but
   *no* reviewer captures exist, that is a did-not-run condition, not a clean pass, and must surface
   as `NEEDS DISCUSSION` naming the probable cause — never as an implicit approval.

**Proof.** A test in `scripts/tests/` (or the `test-hooks.sh` harness, which already exercises the
capture pipeline across 302 cases) asserting the zero-captures-after-dispatch path does not produce
an approving verdict.

### 4.10 — Four verified documentation defects (Medium)

| # | Location | Defect |
|---|---|---|
| a | `README.md:104` | "All five review agents now run on `opus`." **False** — all five pin `sonnet` today. After §4.2 it becomes *partially* true (3 of 5), which is worse as a doc bug because it reads plausible. Rewrite to state the tiering explicitly. |
| b | `CLAUDE.md:35` | Alias list omits `best`, `opusplan`, and the bracketed forms; guidance says nothing about effort. |
| c | `CLAUDE.md:35` + `AGENT_CONTRACTS.md:375` | "Prefer `inherit`/`sonnet` over hard-pinning `opus`." `opus` is an **alias** that tracks the latest Opus and updates over time; `claude-opus-5` would be a hard pin. The guidance argues against something the alias does not do — and it now contradicts §4.2. Rewrite to distinguish alias from version pin. |
| d | `agents/ai-engineer.md:78` | `let defaultModel = "claude-sonnet-4-6"` — a stale model id in the illustrative provider that the AI-pipeline agent teaches from. |

**Proof.** `scripts/tests/test_doc_gates.py` already enforces doc conventions with mutation-proved
cases; add assertions for (a) and (c) so the claims cannot silently regress.

### 4.11 — Version bump and CHANGELOG (Low)

Bump `plugin.json` `version`, the README H1, and the What's-New heading together —
`validate-version-sync.sh` asserts all three plus the counts, and the counts are additionally
hardcoded in the `description` fields of both `plugin.json` and `marketplace.json`
(`scripts/validate-version-sync.sh:106,114-115`).

**Counts do not change in this ticket: 21 / 21 / 0 / 1.** The sibling autonomous-mode ticket is the
one that takes skills to 22; it must not be merged before this one, or the count assertions will
disagree about which version introduced the change.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| `CLAUDE_CODE_EFFORT_LEVEL` set below `xhigh` in a runner silently defeats every pin in §4.1 | Medium | **Cannot be fixed by frontmatter — the env var outranks it.** Documented here; the runtime guard is a preflight assertion owned by the autonomous-mode ticket. Do not claim a guarantee this plan cannot deliver. |
| Three reviewers moving to `opus` materially raises review wall-clock | High | Accepted. Cost and latency were explicitly accepted by the maintainer. Flagged so it is not mistaken for a regression. |
| Effort pin *lowers* effort for a maintainer running at `max` | Medium | Documented in §4.1 as the accepted trade of a deliberate pin. |
| Bracketed-alias regex change reopens the COREDEV-2503 F10 injection hole | Low | Both-end anchoring retained; explicit negative cases required in §4.4's proof. |
| Refreshed `KNOWN_TOOLS` goes stale again | High (over time) | Unavoidable — the tool surface moves. The typo guard's false-reject behaviour is the real defect; consider lowering its aggressiveness rather than chasing the list. |
| §4.9 detection changes verdict behaviour and breaks existing capture tests | Medium | The 302-case harness is the guard; any behavioural change must update contradicting assertions rather than leaving them inconsistent (COREDEV-2503 mutation-proof discipline). |
| Merged out of order with the sibling tickets | Medium | Stated in the header and §4.11: this plan lands first. |

## 6. Verification

Every gate below must pass before the change is proposed for merge:

```bash
python3 scripts/validate-plugin-assembly.py --root . --strict
python3 scripts/validate-hooks.py --root . --strict --require-manifest
VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh
bash scripts/test-hooks.sh
python3 -m unittest discover -s mcp/review-synthesizer/tests
python3 -m unittest discover -s scripts/tests
shellcheck -s bash -S warning scripts/*.sh scripts/lib/*.sh scripts/review/*.sh .githooks/pre-commit
```

Plus, on the pinned CLI (`npm install -g @anthropic-ai/claude-code@2.1.220`):

```bash
claude plugin validate --strict .
claude plugin validate .claude-plugin/plugin.json
```

**Mutation proof is required for every new assertion** (§4.3, §4.4, §4.5, §4.6, §4.7, §4.9, §4.10):
revert the fix, and the new test must fail. Where an existing test asserts the old behaviour it is
inverted or replaced — never left contradictory.

## 7. Implementation order

1. §4.4 – §4.7 — validator fixes first, so the later asset edits are checked as they land.
2. §4.2 — three `model:` values, plus the §11 three-tier table and rewritten rationale.
3. §4.1 — effort pins across 21 agents + 3 workflow skills.
4. §4.3 — the effort assertion (after the pins exist, so it goes green immediately).
5. §4.8 — CI pin, plus the documented version floor.
6. §4.9 — spawn-depth documentation and gate detection.
7. §4.10 — doc corrections and their gate tests.
8. §4.11 — version bump and CHANGELOG, last.

## 8. Open questions for the reviewers

1. **§4.9 detection placement.** Should the zero-captures-after-dispatch check live in
   `swift-reviewer`'s Step 5 prose, or be hardened into `scripts/review/reviewer-roster.sh` where the
   roster is already cross-checked in six places? The latter is harder to talk out of, and this plan
   leans that way — but it widens the blast radius.
2. **§4.5 typo-guard aggressiveness.** Refreshing the list fixes today's two false rejects but not
   the mechanism. Is `cutoff=0.7` on an inherently incomplete allowlist worth keeping at all, given a
   false reject blocks a legitimate tool and a missing name merely passes?
3. **§4.1 knowledge skills.** Leaving the 18 auto-triggering skills unpinned is a judgement call.
   Under a strict reading of "never below `xhigh`", should they be pinned too for completeness, at
   the cost of 18 files of churn that change nothing in practice?

## 9. Notes

- The audit that produced this plan verified all six gates green on `cce02e0` before proposing any
  change, so every finding here is drift rather than breakage.
- The background-subagent tool filter was checked per-agent and requires no change; it is recorded in
  §2 as explicitly out of scope so a future reader does not re-investigate it.
- `sessionstart-restore.sh`'s finding that `PostCompact` cannot inject context is correct and already
  correctly resolved; it is called out here only so the sibling journal ticket does not revisit it.
