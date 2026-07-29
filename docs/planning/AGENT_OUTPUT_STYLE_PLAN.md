# Agent Output Style Plan

**Status:** Planning — awaiting dual plan-review gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29
**Ticket:** `COREDEV-2602` — AGENT_CONTRACTS: add an agent output-style section (adapted from
`i-have-adhd`)
**Epic:** `COREDEV-2485` — Plugin audit remediation / agent-skill-hook-CI modernization
**Branch:** `feat/COREDEV-2602-agent-output-style`
**Target version:** `2.6.0` → **`2.6.1`** (patch: documentation only, no asset-count change).
**Depends on:** `OPUS5_ALIGNMENT_PLAN.md` (`COREDEV-2583`, **APPROVED**) — **must land first**. It also
edits `AGENT_CONTRACTS.md` (§11 rewrite, §5 spawn-depth declaration), so this plan rebases onto it
rather than racing it.
**Source:** `github.com/ayghri/i-have-adhd` (MIT). Only the **Claude portion** is in scope.

---

## 1. Context

`ayghri/i-have-adhd` is a Claude Code plugin (MIT, ~13k★) whose single skill shapes model output for a
reader with ADHD: lead with the next action, number multi-step work, restate state across turns,
suppress tangents, give concrete estimates, cut preamble and closers.

Reviewing it against this plugin, the **rules** are largely transferable but the **delivery mechanism**
is not. Three reasons the mechanism is wrong for us:

1. Installing it as a skill takes the counts `21/21/0/1` → `21/22/0/1`, which collides with the release
   chain `COREDEV-2583` just locked, and touches nine documented count sites of which only three are
   gated.
2. Its skill body is written for a *human reader in a chat transcript*. Most of this plugin's output is
   consumed by **other software** — five reviewers emit JSON findings arrays that `synthesize_review`
   parses, and the review gate parses a literal `VERDICT:` line.
3. A skill is an *opt-in, per-session* artifact. House style for 21 agents belongs in the document that
   already governs cross-agent behaviour.

**Maintainer decision (2026-07-29), locked:** adopt the rules into `AGENT_CONTRACTS.md` as a numbered
section; do **not** ship a 22nd skill; do **not** adopt the multi-harness distribution.

## 2. Scope

**In:** one new numbered section in `AGENT_CONTRACTS.md` stating the output-style rules that apply to
agent-authored prose, the explicit carve-out where those rules yield to a machine-readable contract, and
a doc-gate assertion so the carve-out cannot be silently dropped. Attribution to the MIT source.

**Out:** any new skill or agent (counts stay `21/21/0/1`). Any change to the five reviewers' JSON
schema, to `synthesize_review`, or to the `VERDICT:` contract. Any change to `hooks/hooks.json`.

**Explicitly out of scope, decided rather than overlooked:** the source repo's multi-harness
distribution — `.cursor/skills/`, `.codex-plugin/`, `.agents/plugins/`, `gemini-extension.json`, and the
`cursor-skill-sync.yml` workflow that keeps the Cursor copy in step. This plugin is Claude Code-specific
(sub-agents, hook events, a bundled stdio MCP server); there is no second harness to sync to. *(The
drift-guard **pattern** in that workflow is separately valuable and is owned by `COREDEV-2600` — this
plan does not touch it.)*

## 3. Guiding principle

> **The shape is house style; the contract is law.** Where an output rule and a machine-readable
> contract disagree, the contract wins and the rule yields — silently truncating a findings array or
> dropping a `VERDICT:` line to satisfy a style rule is a correctness regression, not concision.

The source skill states the same precedence for itself ("A rule fights the harness… the constraint wins,
the shape stays"), which is why its rules are safe to adopt *provided the carve-out comes with them*.
Adopting the rules without the carve-out is the single way this ticket could do damage.

---

## 4. Findings, fixes, and proofs

### 4.1 — Agent output style is undocumented and inconsistent (Medium)

**Root cause.** `AGENT_CONTRACTS.md` governs ownership, tool floors, model tiering, CFR labelling and
pipeline order — but says nothing about the *shape* of what an agent writes. Individual agents carry ad
hoc guidance; there is no shared statement, so a new agent has nothing to conform to.

**Fix.** Add a numbered section adopting these rules for **agent-authored prose**:

1. **Lead with the next action.** The first line is something the reader can act on, not context.
2. **Restate state.** Do not assume the reader holds "round 3 of 5" across turns — a multi-round review
   gate makes this acute.
3. **Concrete estimates.** "About 15 minutes if tests already cover this" beats "some work".
4. **Suppress tangents.** Finish the first issue; offer the second separately.
5. **Matter-of-fact errors.** State cause and fix. No "Uh oh".
6. **No preamble, no recap, no closing pleasantries.**
7. **Rank rather than pad.** Five ranked items beat ten unranked. *(Applies to prose; see §4.2.)*
8. **Make completed work concrete.** What now works, and how to see it.

**Proof.** Doc-gate assertion in `scripts/tests/test_doc_gates.py` that the section exists and names its
carve-out (§4.2). Delete the section → the test fails.

### 4.2 — Three of the source rules would break shipped contracts (High)

**Root cause — this is the finding that matters.** Adopted verbatim, three rules actively damage
machine-consumed output:

| Source rule | Collides with | Consequence |
|---|---|---|
| "Cap lists at 5 items" | the five reviewers' **JSON findings arrays**, consumed by `synthesize_review` | a reviewer dropping findings to hit a count is a **correctness regression**, and the synthesizer dedups/merges on the assumption the array is complete |
| "End when the answer is done" | the review gate's required trailing **`VERDICT:` line** | the synthesis parses that line deterministically; without it the verdict must be inferred from prose |
| "No preamble" | the **`BLOCKED — …`** result prefix (`agents/graph-api-debugger.md:20-22`, `agents/jira-manager.md:252`) | that prefix *is* the house pattern for a subagent with no user channel; stripping it as preamble destroys the signal the invoking session reads |

This is not hypothetical: this session's own gate saw a reviewer return a bare 17-byte
`VERDICT: APPROVE` with no body, and `skills/gemini-review/SKILL.md` already classifies a tiny
transcript as a **failure, never an approval**. A style rule pushing toward terseness in that direction
makes that failure mode more likely, not less.

**Fix.** The section must carry an explicit precedence clause, in normative language:

> These rules govern **prose written for a human reader**. Where a rule conflicts with a
> machine-readable contract — a JSON findings array, a required `VERDICT:` line, a `BLOCKED — …` result
> prefix — **the contract wins and the rule yields**. Completeness of a machine-consumed payload is
> never traded for brevity.

**Proof.** A `test_doc_gates.py` case asserting the section contains the precedence clause **and** names
all three contracts. Remove any one name → the test fails. This mirrors the existing
`test_verdict_vocab_consistent_across_all_three` discipline in that file.

### 4.3 — Placement (Low)

**Root cause.** `AGENT_CONTRACTS.md` runs §1–§12 (`:12`–`:379`) followed by an **unnumbered**
`## Cross-references` at `:421`, 443 lines total. There is no §13.

**Fix.** Insert the new section as **§13**, after §12's body and **before** `## Cross-references`.

**Note for the reviewer.** `COREDEV-2583` is approved and edits the same file (§11 rewrite at `:354`,
§5 spawn-depth declaration at `:235`). Neither touches §12's tail or the cross-references block, so the
insertion point is stable — but line numbers **will** shift once 2583 lands. Cite the section number,
not the line, in anything durable.

### 4.4 — Attribution (Low)

**Root cause.** The rules are adapted from an MIT-licensed third-party project.

**Fix.** Name the source and its licence in the section header. No code is copied — the rules are
restated in this repo's own vocabulary and the three conflicting rules are deliberately altered — so a
notice in the section is sufficient; no `LICENSE` vendoring is required.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| A reviewer truncates a findings array to satisfy "rank rather than pad" | **High** if the carve-out is dropped | §4.2's precedence clause is the entire mitigation, and it is doc-gated so it cannot be quietly removed |
| A reviewer omits the trailing `VERDICT:` line as a "closer" | Medium | Named explicitly in the carve-out; `gemini-review`/`codex-review` already treat a missing verdict as a failure |
| An agent strips its `BLOCKED — …` prefix as "preamble" | Medium | Named explicitly in the carve-out |
| Merge conflict with `COREDEV-2583` in `AGENT_CONTRACTS.md` | Medium | 2583 lands first and this rebases; the insertion point (§12 tail) is disjoint from 2583's edits (§5, §11) |
| Style rules are read as binding on JSON payload *content* | Medium | The section scopes itself to "prose written for a human reader" in its first sentence |
| Adds churn without changing behaviour | Low | Accepted: the section is the reference a new agent conforms to; today there is none |

## 6. Verification

```bash
python3 scripts/validate-plugin-assembly.py --root . --strict
python3 scripts/validate-hooks.py --root . --strict --require-manifest
VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh
bash scripts/test-hooks.sh
python3 -m unittest discover -s mcp/review-synthesizer/tests
python3 -m unittest discover -s scripts/tests
shellcheck -s bash -S warning scripts/*.sh scripts/lib/*.sh scripts/review/*.sh .githooks/pre-commit
```

Counts must remain **21 / 21 / 0 / 1** and hook events **10** — this ticket changes neither.

**Mutation proof required** for §4.1 and §4.2: delete the section, or remove any one of the three named
contracts from the carve-out, and the new `test_doc_gates.py` case must fail.

## 7. Implementation order

1. §4.3 — insert §13 with the eight rules.
2. §4.2 — add the precedence clause naming all three contracts. **Not separable from step 1**; the rules
   must not land without it.
3. §4.4 — attribution line.
4. §4.1 + §4.2 — the `test_doc_gates.py` assertions.
5. Version bump to 2.6.1 + CHANGELOG, last.

## 8. Open questions for the reviewers

1. **Should the rules bind agents, or agents *and* skills?** This plan scopes them to agent-authored
   prose. Skill bodies are injected context rather than output, so they arguably do not need it — but
   `swift-reviewer`'s Step-5 prose and the workflow skills do produce reader-facing text. Is a single
   section covering both clearer than a boundary reviewers will have to adjudicate later?
2. **Is a doc-gate assertion strong enough for §4.2?** It proves the clause is *present*, not that
   agents *obey* it. Obedience is exactly what `COREDEV-2599`'s evals harness would measure. Should this
   ticket wait for that, ship as documentation now, or ship now and add an eval case later?
3. **Is "rank rather than pad" worth keeping at all**, given it is the rule most likely to be
   misapplied to a findings array? Dropping it costs little; keeping it needs the carve-out to be
   unmissable.

## 9. Notes

- Every structural claim was verified against the worktree: `AGENT_CONTRACTS.md` §1–§12 with
  `## Cross-references` unnumbered at `:421` (443 lines, no §13); the `BLOCKED — …` pattern at
  `agents/graph-api-debugger.md:20-22` and `agents/jira-manager.md:252`; and
  `scripts/tests/test_doc_gates.py` existing with unittest classes including
  `test_verdict_vocab_consistent_across_all_three`.
- The source repo's `evals/` harness and its `plugin-load-check.yml` are **not** part of this ticket;
  they are `COREDEV-2599` and `COREDEV-2598` respectively. Its duplicate-drift guard pattern is
  `COREDEV-2600`.
- `COREDEV-2584` and `COREDEV-2585` are paused; their 2.7.0 / 2.7.1 version slots are provisional, so
  this ticket takes 2.6.1 rather than assuming a slot after them.
