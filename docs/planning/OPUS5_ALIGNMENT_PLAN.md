# Opus 5 Alignment Plan

**Status:** Planning — round 2, revised after the round-1 dual gate (gemini `APPROVE_WITH_NOTES`,
codex `REQUEST_CHANGES`). Round-1 transcripts are captured under
`docs/planning/reviews/COREDEV-2583_{gemini,codex}_plan_review_r1.txt`, which is **gitignored**
(`.gitignore:29 reviews/`) — they are local working artifacts, not committed. Every round-1 finding
acted on is restated inline below, so this document stands alone without them. (Note:
`COREDEV-2503_GATE_FAILOPEN_REMEDIATION_PLAN.md:15` cites the same directory as though it were
committed; no such file has ever been in git. That dangling citation is not repeated here.)
**Created:** 2026-07-29
**Last Updated:** 2026-07-29
**Ticket:** `COREDEV-2583` — Opus 5 alignment: effort pinning, three-tier model policy, validator
coverage, CI pin
**Epic:** `COREDEV-2582` — Opus 5 readiness and autonomous end-to-end mode
**Branch:** `feat/COREDEV-2583-opus5-alignment`
**Target version:** `2.5.3` → **`2.6.0`** (minor: fleet-wide model/effort policy change, no asset-count
change). The epic's release chain is **2.6.0 (this) → 2.7.0 (`COREDEV-2584`, takes skills to 22) →
2.7.1 (`COREDEV-2585`)**.
**Siblings, in required landing order:** this plan **first**, then `AUTONOMOUS_END_TO_END_PLAN.md`
(`COREDEV-2584`), then `DECISION_JOURNAL_PLAN.md` (`COREDEV-2585`). 2584 before 2585 because 2584 owns
the brainstorm fork sidecar that 2585's checkpoint records rationale against.

---

## 1. Context

The plugin was authored against Claude Code as it behaved under Opus 4.8. Opus 5 shipped alongside a
run of Claude Code releases that changed defaults the plugin silently depends on. A review of the
shipped assets against the current documentation (re-verified 2026-07-29 against CLI 2.1.220) found the
plugin **functionally healthy but drifted**:

- All six gates pass on the current tree: `validate-plugin-assembly --strict` (21/21/0/1),
  `validate-hooks --strict --require-manifest` (10 events), `validate-version-sync` (2.5.3),
  `test-hooks.sh` (302 passed), the synthesizer suite (191), the scripts suite (243).
- All 21 agents use exactly the current documented sub-agent frontmatter key set.
- All 10 declared hook events are real.

What has drifted is **model/effort policy, validator coverage, and documentation**. None of it is
caught by CI, because the validators check counts and key syntax — not whether the policy the docs
describe is the policy the assets implement. This is the same class of defect the model-tier check
was added to catch (`check_model_tiering`), and it has recurred on a new axis.

**Maintainer decisions locked before this plan was written** (do not re-litigate in review):

| Decision | Value |
|---|---|
| Effort floor | **Nothing below `xhigh`, ever.** Cost explicitly accepted. |
| Effort scope | **Every executable asset** — all 21 agents **and all 21 skills** (settled round 2; see §4.1) |
| Model tiers | **Three**, see §4.2 |
| Provider | **Direct Anthropic API only** — no Bedrock / Foundry / GCP |
| Org effort caps | Confirmed **not** in play |
| Long context | **In scope** — `opus[1m]` must be a legal value |
| CLI pin | **2.1.220** |

## 2. Scope

**In:** effort pinning across every agent and skill; the three-tier model policy in
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
guarantee the plugin makes (§5), the plan documents it honestly rather than implying a guarantee
the plugin cannot deliver.

Corollary added in round 2: **a validator must be built from the pinned runtime's real schema, never
from a hand-written guess.** Round 1 caught this plan asserting a skill-key behaviour the runtime
contradicts (§4.6). Any new key set in this ticket is derived from the 2.1.220 bundle and cited as such.

---

## 4. Findings, fixes, and proofs

### 4.1 — Effort is unset everywhere, on every asset (High)

**Root cause.** `effort:` is a real sub-agent and skill frontmatter key. In the pinned runtime the
skill/command schema declares it as `effort:<string>().optional()` with the description "Thinking
effort for the model: `low`, `medium`, `high`, `max`, or an integer". The validator
already accepts it — `KNOWN_AGENT_KEYS` at `scripts/validate-plugin-assembly.py:43` includes
`"effort"` — but **zero of the 21 agents and zero of the 21 skills set it**. Every agent and skill
therefore runs at whatever the session happens to carry, including `low`.

This is sharpest at the review gate. `skills/codex-review/SKILL.md:28` forces
`model_reasoning_effort=xhigh` on the *external* Codex reviewer and documents a silent reset to `low`
as an under-powered gate with no error to notice — while the plugin's own five reviewers, its verify
gate, and the two review-driver skills have no equivalent protection.

**Fix.** Pin `effort: xhigh` in the frontmatter of **all 21 `agents/*.md` and all 21
`skills/*/SKILL.md`**.

**Round-2 change, and why.** The round-1 plan pinned only the three invoke-only workflow skills and
argued the other 18 are "injected context, not an execution step". Codex rejected that, correctly: the
justification only holds when the session is already at or above `xhigh`, and **the finding exists
precisely because a session may be at `low`**. Several of the supposedly passive skills are operational
in practice — `codex-review` and `gemini-review` *are* the review gate, and `create-feature-plan` and
`review-synthesis` drive the plan pipeline. The maintainer settled it in favour of the unconditional
rule: there is no effort tiering, and no per-skill judgement call for a future maintainer to get wrong.

**Note on semantics, which the implementer must not get wrong.** Frontmatter effort is an
**override, not a floor** — it moves the level in *both* directions. Under the locked "never below
`xhigh`" rule this is correct and desirable: a session launched at `low` is pulled *up*. But it also
means a session at `max` is pulled *down* to `xhigh` for these assets. That is the accepted trade, and
with the pin now on all 42 assets it applies fleet-wide — see the §5 risk row.

**Note for the reviewer.** The 2.1.220 description string for this field omits `xhigh`, but the value
is legal: the field is validated as a **plain string**, not an enum, and `xhigh` appears throughout the
same bundle as a first-class level (`["low","medium","high","xhigh","max"]`, a per-model
`xhigh_effort` capability, and `/effort ultracode` documented as "xhigh + dynamic workflow
orchestration"). The description is abbreviated, not authoritative.

**Proof.** A new validator assertion (§4.3) fails when any agent or skill omits `effort: xhigh`.
Revert any single pin → the validator fails naming that file.

### 4.2 — §11 Model Tiering Policy: two tiers become three (High)

**Root cause.** `AGENT_CONTRACTS.md:354` opens §11, which files every agent under one of two tiers
(`AGENT_CONTRACTS.md:364` is the table header). The three agents that own the highest-consequence
review categories are all in the `sonnet` row:

- `security-reviewer` — credentials, OAuth, injection, CI
- `prompt-review` — AI prompt/call-site safety, injection, PII-in-logs
- `concurrency-reviewer` — the declared **correctness owner**, absorbing the logic and
  error-handling findings the other reviewers explicitly punt

Separately, §11's stated rationale is a **cost** argument ("cost-efficient, consistent breadth"; "a
costlier session model is wasted", `AGENT_CONTRACTS.md:370-375`). Cost is no longer a constraint, so
that rationale no longer holds on its own terms and must be rewritten rather than left standing.

**Fix.** Three tiers. The §11 table stays **exactly three columns** — see the parser note:

| Tier | `model:` | Agents |
|---|---|---|
| Deep-review specialists | `opus` | security-reviewer, prompt-review, concurrency-reviewer |
| Orchestrator + implementation/diagnostic | `inherit` | swift-reviewer, ai-engineer, ci-engineer, code-simplifier, db-engineer, graph-api-debugger, logic-engineer, modern-standards-planner, tester, ui-engineer, xcode-build-fixer |
| First-pass reviewers, personas, fixed-scope managers | `sonnet` | accessibility-auditor, ux-perf-reviewer, docs-engineer, enterprise-stakeholder, jira-manager, release-manager, smb-entrepreneur |

3 + 11 + 7 = 21. Only three frontmatter values change:
`agents/security-reviewer.md:11`, `agents/prompt-review.md:16`, `agents/concurrency-reviewer.md:11`,
each `sonnet` → `opus`. The other 18 keep their current value (verified against disk).

Rewrite the §11 rationale prose to the capability argument that now applies, and add a one-line
effort policy: *every agent and every skill pins `effort: xhigh`; there is no effort tiering.*

**Parser check — corrected in round 2.** `_TIER_ROW`
(`scripts/validate-plugin-assembly.py:247`) is
`^\|[^|]*\|\s*`([a-z]+)`[^|]*\|\s*([^|]+?)\s*\|\s*$` — it matches a **three-column** row only. The
round-1 draft displayed the proposed tiers as a **four-column** table (a trailing `Count` column), which
does **not** match; an implementer copying it verbatim would have produced a §11 table where
`check_model_tiering` sees **zero** tier rows. Executed both forms to confirm: 4-column → no match,
3-column → match. The table above is the shape that ships. The only structural assertion in
`check_model_tiering` is `rows < 2` at `:280`, so a third tier row parses with no parser change.

**Proof.** `check_model_tiering` already asserts frontmatter equals the tier table in both
directions. Move any one agent between rows without editing its frontmatter → strict validation
fails. **Additionally required (round 2):** the existing duplicate detection only reports when the
second occurrence carries a *different* model, so a name repeated within one row, or across two rows
with the same model, silently overwrites itself. Add mutation cases for both, and tighten the check to
flag any repeated agent name regardless of model.

### 4.3 — `check_model_tiering` does not know about effort (High)

**Root cause.** The function at `scripts/validate-plugin-assembly.py:251` asserts model-tier
alignment only. With effort now load-bearing (§4.1), an asset silently losing its `effort: xhigh` pin
— or a new one landing without one — is invisible to CI. That is exactly the failure mode this
function was written to end, one axis over.

**Fix.** Extend it (or add a sibling `check_effort_policy`) to assert:
1. every `agents/*.md` declares `effort: xhigh`;
2. **every `skills/*/SKILL.md`** declares `effort: xhigh`;
3. §11's effort policy line is present and states `xhigh`.

Keep it a **hard** assertion, not a warning — a silent under-powered gate is precisely the defect.

**Proof.** New unit cases in `scripts/tests/test_validate_plugin_assembly.py` mirroring the existing
tiering tests. Each must fail when the fix is reverted — including one case per axis (a missing agent
pin, a missing skill pin, a missing policy line).

### 4.4 — `MODEL_ALIASES` and the model-id regex reject legal values (High — blocker for long context)

**Root cause.** `scripts/validate-plugin-assembly.py:48`:

```python
MODEL_ALIASES = {"sonnet", "opus", "haiku", "fable", "inherit"}
```

and the id pattern `re.fullmatch(r"[a-z]+-[a-z0-9-]*\d[a-z0-9-]*", model)` at `:100`.

Sub-agent `model:` accepts *the same values as the `--model` flag*. The runtime's alias table (2.1.220 `h1e`) is
exactly `sonnet, opus, haiku, fable, best, sonnet[1m], opus[1m], fable[1m], opusplan` — note it
contains **no `default`**, and only three aliases take the `[1m]` long-context suffix.

**Executed against the live validator**, confirming the blocker rather than asserting it:

| Value | Today |
|---|---|
| `opus[1m]`, `sonnet[1m]`, `fable[1m]`, `best`, `opusplan` | **REJECTED** |
| `opus`, `inherit`, `claude-opus-5` | accepted |
| `claude-opus-5 rm -rf`, `claude-opus-5; evil`, `claude-opus-5\nmalicious` | REJECTED (correct) |

Long context is in scope, so `model: opus[1m]` failing the plugin's own CI is a live blocker.

**Fix — specified concretely in round 2, because "accept an optional bracketed suffix" is not
security-reviewable.** Do **not** widen the character class. Instead:

1. Replace `MODEL_ALIASES` with the runtime's **exact** alias table, transcribed from the 2.1.220
   bundle (`h1e`), plus `inherit` (a sub-agent-only value the runtime handles separately and which is
   **not** in that table):

   ```python
   # Transcribed verbatim from Claude Code 2.1.220 (`h1e`). Re-check on every CLI pin bump.
   MODEL_ALIASES = {
       "sonnet", "opus", "haiku", "fable", "best", "opusplan",
       "sonnet[1m]", "opus[1m]", "fable[1m]",
       "inherit",                      # sub-agent only; not part of the runtime alias table
   }
   ```

2. **Enumerate the bracketed forms; do not synthesise them.** Only `sonnet`, `opus` and `fable` take
   `[1m]` in the runtime table. A "strip the suffix then validate the base" rule would
   **over-accept** `haiku[1m]`, `best[1m]`, `opusplan[1m]` and `inherit[1m]`, none of which the runtime
   recognises.
3. Leave the model-**id** path (`re.fullmatch(r"[a-z]+-[a-z0-9-]*\d[a-z0-9-]*", …)`) completely
   unchanged. Because the bracketed forms are now literal set members, no bracket ever reaches the
   regex and the COREDEV-2503 F10 anchoring is untouched by construction.

**Round-2 correction (round-2 review).** The round-2 draft proposed adding **`default`** and stripping
`[1m]` from any base. Both are wrong: `default` does **not** appear in the runtime alias table, and
suffix-stripping over-accepts as above. The authoritative table is:

```js
h1e = ["sonnet","opus","haiku","fable","best","sonnet[1m]","opus[1m]","fable[1m]","opusplan"]
```

The `re.fullmatch` (not `re.match`) discipline introduced by COREDEV-2503 F10 exists to stop
`claude-opus-4-8 rm -rf` and trailing-newline injection from passing; because the suffix is stripped as
a literal and the remainder still goes through `fullmatch`, no new bracket body is ever accepted.

**Proof.** Extend `scripts/tests/test_validate_plugin_assembly.py`. Accept: the complete supported
bracketed set `sonnet[1m]`/`opus[1m]`/`fable[1m]`, `claude-opus-5`, `best`, `opusplan`. **Reject the
unsupported combinations** `haiku[1m]`, `best[1m]`, `opusplan[1m]`, `inherit[1m]`, and `default`
(not an alias). Continue
rejecting `claude-opus-5 rm -rf`, `claude-opus-5; evil`, `claude-opus-5\nmalicious`. **New hostile
cases required:** `opus[1m;evil]`, `opus[1m\nmalicious]`, `opus[rm-rf]`, `opus[1m][1m]` (doubled),
`opus[1m]x` (trailing content after a valid suffix), `opus[1m`, `opus[]`.

### 4.5 — `KNOWN_TOOLS` is stale and actively false-rejects two current tools (Medium)

**Root cause.** `scripts/validate-plugin-assembly.py:53`. An unknown non-MCP entry is normally
accepted, but the `difflib.get_close_matches(..., cutoff=0.7)` typo guard rejects anything that looks
like a near-miss of a known name. Executed against the current tool surface: `TaskOutput` is
**rejected** as a typo of `BashOutput`, and `EnterPlanMode` is **rejected** as a typo of
`ExitPlanMode`. `ToolSearch`, `Monitor`, `SendMessage`, `Artifact`, `EnterWorktree`, `ExitWorktree`,
`Workflow`, `ScheduleWakeup`, `CronCreate/Delete/List` are accepted only as *unknown*.

Additionally `MultiEdit` is still listed as known but is no longer a real tool — and it appears in a
live deny-list at `agents/jira-manager.md:15`.

**Fix.** Refresh `KNOWN_TOOLS` to the current built-in set and leave the `STALE_TOOLS` hard-reject for
`Task` intact.

**Round-2 correction.** Merely *removing* `MultiEdit` from `KNOWN_TOOLS` does not fix it — an unknown
tool is **accepted**, so `agents/jira-manager.md:15` would remain a silent no-op line. The fix must be
all three of: delete `MultiEdit` from that deny-list, add `MultiEdit` to `STALE_TOOLS` so it is
hard-rejected like `Task`, and mutation-test the rejection.

**Resolved from §8 (round 1).** Both reviewers agreed the `cutoff=0.7` guard should stop being a hard
failure over an inherently incomplete allowlist: a false reject blocks a legitimate tool, while a
missed typo merely passes as unknown. **Decision:** demote fuzzy similarity to **advisory** (a warning,
via §4.7's new channel), and keep hard rejection only for the explicit `STALE_TOOLS` set.

**Proof.** A unit case asserting every name in the refreshed set validates clean; explicit regression
cases for `TaskOutput` and `EnterPlanMode`; and a case asserting `MultiEdit` is hard-rejected that
fails if it is merely dropped from `KNOWN_TOOLS`.

### 4.6 — Skills have no unknown-key check — and the round-1 premise for it was wrong (Medium)

**Root cause.** `check_agent_fields` (`scripts/validate-plugin-assembly.py:80`) is agent-only *by
design* — `allowed-tools` is legal for skills and illegal for agents, so the check cannot be shared.
The consequence is that **skills have no key validation at all** beyond `name`/`description`
(`:82-84`: "Skills/commands are intentionally exempt").

**Round-2 correction — the motivating example was false, and the proposed fix would have caused the
bug it meant to prevent.** Round 1 asserted that a skill written with camelCase `disallowedTools:`
"passes CI and silently does nothing". It is not silent and it does not do nothing: the pinned 2.1.220
runtime declares it as a **first-class alias**, verbatim from the bundle's skill/command schema:

```js
disallowedTools: <string>().optional().describe("Canonical (normalized) alias of `disallowed-tools`.")
```

A validator built on the round-1 premise would have **rejected a legal field**. The round-1 draft also
enumerated seventeen skill keys from memory; the real schema additionally carries at least `version`,
`arguments`, `shell`, `paths`, `agent`, `created_by`, and `improved_by`.

The asymmetric case is real, though, and is the finding worth keeping: searching the same schema with a
delimiter-anchored match, `disallowedTools` appears as an alias while **`allowedTools` does not appear
at all**. So camelCase `allowedTools:` in a skill genuinely *is* ignored.

**Fix.** Add `KNOWN_SKILL_KEYS` and a `check_skill_fields` mirroring the agent path, with three
constraints:

1. **Derive the key set from the pinned runtime's schema**, not from a hand-written list, and cite the
   CLI version next to it so the next bump has an obvious update point.
2. **Accept `disallowedTools`** exactly as the runtime does.
3. Emit a **targeted error for `allowedTools`** — the one camelCase form that really is inert — naming
   the kebab spelling.

**Proof.** Unit cases: a skill using `allowedTools:` fails with the targeted hint; a skill using
`disallowedTools:` **passes**; a skill using every legal key from the derived set validates clean. The
second case is the mutation guard against reintroducing the round-1 error.

### 4.7 — Plugin-ignored frontmatter keys are accepted without warning (Low)

**Root cause.** `KNOWN_AGENT_KEYS` (`:43`) accepts `permissionMode`, `mcpServers`, and `hooks`.
Claude Code **ignores all three for plugin sub-agents** for security reasons. No agent uses them
today, so nothing is broken — but these are precisely the keys someone reaches for when building an
autonomous mode, and the failure is silent.

**Fix.** Keep them in the known set (they are legal *keys*, just inert here) and emit a warning when
they appear, naming the plugin-subagent exemption and pointing at the alternatives.

**Round-2 blocker.** The validator has **no warning channel** — it collects only `problems`, and
anything appended there fails strict mode. So "emit a warning" is not implementable as written. This
ticket must therefore **add a `warnings` list** that prints but does not affect the exit code
(mirroring `scripts/validate-hooks.py`, which already separates the two). §4.5's demoted fuzzy guard
depends on the same channel.

**Proof.** Unit case: an agent declaring `permissionMode: bypassPermissions` produces the warning **and
strict validation still exits 0**. Without the new channel that test cannot pass, which is the point.

### 4.8 — CI pins a Claude Code that cannot run Opus 5 (High)

**Root cause.** `.github/workflows/plugin-ci.yml:85` pins `CLAUDE_CODE_VERSION: 2.1.209`. **Opus 5
requires 2.1.219 or later.** The pin drives `claude plugin validate`, the workflow's own
authoritative schema check, so the schema authority is eleven releases behind the floor the plugin
now targets. The pin is manual — there is no `package.json`, so Dependabot does not cover it (the
comment at `:82-84` says as much).

**Fix.** `2.1.209` → `2.1.220`, and record the minimum-CC-version floor durably (README plus
`CLAUDE.md`), since nothing in `plugin.json` expresses it.

**Pre-verified.** CLI 2.1.220 was installed and both validation steps were run against this tree:
`claude plugin validate --strict .` → passed; `claude plugin validate .claude-plugin/plugin.json` →
passed with exactly the one pre-existing expected warning (root `CLAUDE.md` not loaded as project
context), which `:93-96` already documents. **The bump surfaces no new schema findings.**

**Note for the reviewer.** `2.1.220` is the `latest` dist-tag; `stable` is behind the Opus 5 floor.
Pinning ahead of the stable channel is deliberate.

### 4.9 — The five-reviewer panel depends on an undeclared, recently-changed default (High)

**Root cause.** `agents/swift-reviewer.md` spawns five reviewer subagents (it is the only agent with
`Agent` in a `tools:` **allowlist**, at `:13` — `modern-standards-planner` also holds `Agent`, by
*inheritance*, since it omits `tools:` entirely and denies only `mcp__github`, which
`AGENT_CONTRACTS.md:326` records as deliberate). The orchestrator sits at depth 1, the reviewers at 2.
The subagent spawn-depth default has moved three times:

| Claude Code | Default depth | Effect on the panel |
|---|---|---|
| ≤ 2.1.216 | 5 (fixed) | works |
| 2.1.217 – 2.1.218 | **1** | **panel cannot spawn** |
| ≥ 2.1.219 | 3, tunable via `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | works |

At the depth limit Claude Code **withholds the `Agent` tool**. Nothing in the plugin declares or
documents this dependency.

**Fix — reduced to documentation in round 2.** Declare the dependency (minimum CC version and the
`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` requirement) in `AGENT_CONTRACTS.md` §5 alongside the review
pipeline. **Do not add a "zero captures ⇒ NEEDS DISCUSSION" rule.**

**Round-2 correction — the proposed detection was invalid and the round-1 root cause overstated the
risk.** Round 1 claimed the panel would "emit a verdict that reads exactly like a five-reviewer panel".
It would not, and the existing design already covers it. Verified by execution and by reading the
cited tests:

- `scripts/review/reviewer-roster.sh` with **empty** held-report input classifies **all five**
  reviewers `UNATTRIBUTED` and exits **3** — run live, output confirmed. It is mutation-proved by
  `scripts/tests/test_reviewer_roster.py:105`
  (`test_empty_stdin_classifies_everyone_and_fails_closed`), with a missing capture separately covered
  at `:250`.
- More importantly, **zero captures does not imply the reviewers did not run.** Five readable
  in-session handoffs are *intentionally* sufficient even when the capture hooks fail — that path is
  the point of the positive-attribution model and is tested at
  `scripts/tests/test_reviewer_roster.py:98` (`test_all_five_held_is_zero_cost`). A raw zero-capture
  rule would fire a false failure on a healthy review and would contradict the capture-ratchet
  invariant in `AGENT_CONTRACTS.md:242` (a persisted capture may only ratchet toward caution, never
  certify completion).

So the genuine gap is **documentation only**; the detection already exists and must be left alone.
`AUTONOMOUS_END_TO_END_PLAN.md` carries the same overstated "dies while still emitting a normal-looking
verdict" phrasing and is corrected in the same change.

**Proof.** A test asserting the *existing* empty-roster path still fails closed (a regression guard for
the behaviour this ticket decided not to change), plus a doc-gate assertion that §5 states the version
floor and the env var.

### 4.10 — Four verified documentation defects (Medium)

| # | Location | Defect |
|---|---|---|
| a | `README.md:104` | "All five review agents now run on `opus`." **False** — all five pin `sonnet` today (verified). After §4.2 it becomes *partially* true (3 of 5), which is worse as a doc bug because it reads plausible. Rewrite to state the tiering explicitly. |
| b | `CLAUDE.md:35` | Alias list omits `best`, `opusplan`, and the three bracketed forms; guidance says nothing about effort. |
| c | `CLAUDE.md:35` + `AGENT_CONTRACTS.md:375` | "Prefer `inherit`/`sonnet` over hard-pinning `opus`." `opus` is an **alias** that tracks the latest Opus; `claude-opus-5` would be a hard pin. The guidance argues against something the alias does not do — and it now contradicts §4.2. Rewrite to distinguish alias from version pin. |
| d | `agents/ai-engineer.md:78` | `let defaultModel = "claude-sonnet-4-6"` — a stale model id in the illustrative provider that the AI-pipeline agent teaches from (verified verbatim). |

**Proof.** `scripts/tests/test_doc_gates.py` already enforces doc conventions with mutation-proved
cases. **Round-2 correction:** round 1 promised assertions for (a) and (c) only, which contradicts §3
and §6. Add a mutation-proved assertion for **all four** — including (b) that the alias list contains
the full legal set, and (d) that no agent body cites a model id outside the current generation.

### 4.11 — Version bump and CHANGELOG (Low)

Bump to **2.6.0**: `.claude-plugin/plugin.json` `version`, the `README.md:1` H1 (`Plugin vX.Y.Z`), and
the newest `### vX.Y.Z` What's-New heading together — `scripts/validate-version-sync.sh:53-56` asserts
all three — plus a `## [2.6.0]` CHANGELOG heading (`## [Unreleased]` does **not** satisfy the gate).
The counts are additionally hardcoded in the `description` fields of both `plugin.json` and
`marketplace.json` (`scripts/validate-version-sync.sh:106-115`).

**Counts do not change in this ticket: 21 / 21 / 0 / 1.** `COREDEV-2584` is the one that takes skills
to 22 at 2.7.0; it must not merge before this one.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| `CLAUDE_CODE_EFFORT_LEVEL` set below `xhigh` in a runner silently defeats every pin in §4.1 | Medium | **Cannot be fixed by frontmatter — the env var outranks it.** Documented here; the runtime guard is a preflight assertion owned by `COREDEV-2584`. Do not claim a guarantee this plan cannot deliver. |
| Effort pin *lowers* effort for a maintainer running at `max` — now on all 42 assets | **High** | Widened in round 2 from 24 assets to 42. Accepted as the cost of an unconditional floor: a per-asset exemption is exactly the judgement call the round-2 decision removed. Flagged so it is not mistaken for a regression. |
| Three reviewers moving to `opus` materially raises review wall-clock | High | Accepted. Cost and latency explicitly accepted by the maintainer. |
| Bracketed-alias change reopens the COREDEV-2503 F10 injection hole | Low | §4.4 strips a **literal** enumerated suffix and re-validates the remainder with the unchanged `fullmatch` rules; hostile bracket-body negatives are required. |
| A validator key set is written from memory rather than the runtime schema | **High** (demonstrated) | This is what round 1 got wrong in §4.6. §3's round-2 corollary and §4.6 fix 1 require deriving from the pinned bundle and citing the version. |
| Refreshed `KNOWN_TOOLS` goes stale again | High (over time) | Unavoidable — the tool surface moves. §4.5 demotes fuzzy matching to advisory so staleness degrades to a warning, not a false reject. |
| §4.9 detection change breaks existing capture tests | **Eliminated** | Round 2 drops the behavioural change entirely; only documentation is added. |
| Merged out of order with the siblings | Medium | Stated in the header: 2583 → 2584 → 2585, with the version chain 2.6.0 → 2.7.0 → 2.7.1. |

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

**Mutation proof is required for every new assertion** (§4.2–§4.7, §4.9, §4.10): revert the fix, and
the new test must fail. Where an existing test asserts the old behaviour it is inverted or replaced —
never left contradictory.

## 7. Implementation order

1. §4.7's **warnings channel** first — §4.5's advisory demotion depends on it existing.
2. §4.4 – §4.6 — the remaining validator fixes, so the later asset edits are checked as they land.
3. §4.2 — three `model:` values, plus the §11 **three-column** tier table and rewritten rationale.
4. §4.1 — effort pins across 21 agents + 21 skills.
5. §4.3 — the effort assertion (after the pins exist, so it goes green immediately).
6. §4.8 — CI pin, plus the documented version floor.
7. §4.9 — spawn-depth documentation only (no behavioural change).
8. §4.10 — doc corrections and all four gate tests.
9. §4.11 — version bump to 2.6.0 and CHANGELOG, last.

## 8. Round-1 review resolutions

The three open questions round 1 posed to the reviewers are now settled and are recorded here so
round 2 does not reopen them.

1. **§4.9 detection placement — resolved: neither.** The question asked whether zero-capture detection
   belonged in `swift-reviewer` Step 5 or in `reviewer-roster.sh`. Codex demonstrated the premise was
   wrong: the roster already fails closed on empty input, and zero captures does not imply the panel
   did not run. Gemini independently recommended keeping it out of the roster. §4.9 is now
   documentation-only.
2. **§4.5 typo-guard aggressiveness — resolved: demote to advisory.** Both reviewers agreed a hard
   failure over an inherently incomplete allowlist is the wrong trade. Fuzzy matches become warnings;
   only the explicit `STALE_TOOLS` set hard-fails.
3. **§4.1 knowledge skills — resolved: pin all 21.** The reviewers split (codex for pinning all,
   gemini for leaving the 18 alone). The maintainer settled it in favour of the unconditional rule;
   §4.1 records the reasoning.

## 9. Notes

- The audit that produced this plan verified all six gates green before proposing any change, so every
  finding here is drift rather than breakage.
- Round 2 re-verified every file:line and executed every behavioural claim: the validator's live
  accept/reject matrix for §4.4, the `_TIER_ROW` column-count experiment for §4.2, the live
  empty-roster run for §4.9, and the 2.1.220 bundle schema extraction for §4.6 and §4.1.
- The background-subagent tool filter was checked per-agent and requires no change; it is recorded in
  §2 as explicitly out of scope so a future reader does not re-investigate it.
- `sessionstart-restore.sh`'s finding that `PostCompact` cannot inject context is correct and already
  correctly resolved; it is called out here only so `COREDEV-2585` does not revisit it.
