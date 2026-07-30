# COREDEV-2605 — Narrow AGENT_CONTRACTS §13 to client-facing output only

**Status:** Planning — draft, awaiting the dual plan-review gate
**Ticket:** `COREDEV-2605` (Epic `COREDEV-2485`) · follow-up to `COREDEV-2602`, which shipped §13 in v2.6.1
**Blocks:** `COREDEV-2604` (per the ticket, 2604 shrinks once this lands)
**Last Updated:** 2026-07-30
**Measured against:** HEAD `adda52d` (v2.6.4, merged to main as `ff83f02`), worktree `.claude/worktrees/opus5-review`, plugin `2.6.3`

---

## 1. Context

§13 currently governs *"human-facing prose written by agents, and by workflow skills while producing
reader-facing output"* (`AGENT_CONTRACTS.md:465-517`) — ten style rules, of which **four carry
carve-outs** and one is restated, plus a precedence clause protecting **six** machine contracts.

The maintainer's decision (2026-07-29) is to **narrow the scope** rather than keep defending it with
carve-outs. This plan implements that decision.

**Why the carve-outs are the risk.** The design asks an agent to apply ten rules *and* correctly except
six contracts. COREDEV-2602's gate spent **eleven rounds** demonstrating how hard that is: rule 3's
carve-out said "before the final fenced JSON block", which *sounded* right and still returned `None`;
rule 2 was marked a safe bare adopt, yet numbering `What Was Attempted:` destroys the status parse.

**The worked example is real — executed, not argued.** The ticket's non-compliant output:

```
Status: PARTIAL
Completed: KeychainManager.swift, TokenStore.swift
Remaining:
1. MSALBridge.swift
2. GraphClient.swift
Confidence: 80

Next: re-run once the toolchain is available.
```

`capture.extract_status(...)` → **`None`**, executed here. The compliant single-line `Remaining:` form
returns the full dict. So a diligent agent following rules 2 and 3 produces output that is *more*
readable to a human and **unattributable to the pipeline** — `UNATTRIBUTED` → a re-dispatch, or
`NEEDS DISCUSSION` once the retry budget is spent. The blocker is still in the JSON array; it just is
not attributable any more.

## 2. Why now: the blast radius is zero, and that is the whole window

Verified three ways:

1. **§13 is not preloaded, and cannot be.** `skills:` preloads a *skill body*; `AGENT_CONTRACTS.md` is
   not a skill, so no `skills:` list can reach it.
2. **§13's text is not reproduced in any skill body or agent body** — `grep -rln 'payload-region
   invariant\|Agent Output Style' skills/*/SKILL.md agents/*.md` returns **nothing**.
3. The two agents that both declare `skills:` and mention the contracts (`modern-standards-planner` →
   `create-feature-plan`, `tester` → `swift-tdd`) preload skills that do **not** contain §13.

So §13 changes no behaviour today: an agent sees it only if it reads the file. **The narrowing is free
right now and gets expensive the moment anything preloads it.**

> **Correction to the ticket's own figures** — verified by `grep -rl`: the contracts file is referenced
> by **9 of 21 agents** (ticket: 9 ✔) and **9 of 21 skills** (ticket: 8 ✘). One-off, immaterial to the
> decision, recorded because this campaign's citations have been wrong six times.

## 3. Guiding principle

> The design should become **"these rules apply only where nothing parses the output"** — which cannot
> break the pipeline even when misapplied — instead of **"ten rules plus six exceptions an agent must
> get right."**

**This is a scope change, not a rules change.** Every one of the ten rules keeps an explicit
disposition; none is dropped. What changes is *where they apply*.

## 4. Findings, fixes, and proofs

### 4.1 — The exclusion is sound, but it silently depends on `VALID_AGENTS` (High)

The ticket says "exclude the five reviewers". Verified what that actually means in code:

```python
VALID_AGENTS = ('accessibility-auditor', 'concurrency-reviewer', 'prompt-review',
                'security-reviewer', 'ux-perf-reviewer')      # capture.py:130
```

— five agents, and **`swift-reviewer` is deliberately NOT among them**
(`mcp/review-synthesizer/capture.py:514` rejects any other name; `scripts/capture-reviewer-round-start.sh:9` documents the
exclusion: *"EXCLUDES `swift-reviewer` (the orchestrator/consumer)"*). That is what makes the ticket's
in-scope table defensible: swift-reviewer's Step-5 report is genuinely unparsed by `capture.py`.

> **A trap I fell into and had to execute my way out of, recorded so a reviewer does not repeat it:**
> `agents/swift-reviewer.md:539` shows a fenced JSON array, which looks like a parsed payload on
> swift-reviewer's output. It is the **input** to the
> `mcp__plugin_unleashed-mail_review-synthesizer__synthesize_review` tool call, not something
> swift-reviewer emits for a parser. The `VALID_AGENTS` allowlist is the authority here, not the
> presence of a JSON fence in the file.

**The gap the ticket does not close.** §13's scope would name the five reviewers in *prose*, while the
fact that makes the exclusion correct lives in a Python tuple. Add `swift-reviewer` to `VALID_AGENTS`
later — a plausible future change, since it *is* a reviewer by name — and §13's scope statement becomes
silently wrong, with no test failing.

**Fix.** The doc-gate must assert the **coupling**, not just the prose: the set of agents §13 excludes
must equal `capture.VALID_AGENTS`, read from the module at test time.

**Proof — and it must reject a plausible wrong implementation.**
- **M1** hardcode the five names in the test instead of importing `VALID_AGENTS` → mutate the tuple
  (add `swift-reviewer`) and the gate must still fail. A hardcoded list passes and is inert.
- **M2** assert only that the section contains the word "excluded" → deleting a *name* must still fail.
- **M3** section-scoped rather than row-scoped per-rule assertions → a deleted disposition must still be
  detectable (this is COREDEV-2602's round-7 defect, documented at `scripts/tests/test_doc_gates.py:287-290`).

### 4.2 — Scope rewrite: name the in-scope surfaces, with corrected citations (High)

The ticket's four in-scope surfaces are right; **three of its four line numbers are not.** Verified by
opening each file:

| Surface | ticket | **actual** |
|---|---|---|
| `swift-reviewer`'s final verdict report | `~:140` | **`agents/swift-reviewer.md:439`** (`### Step 5: Synthesize Unified Review`) — off by ~300 |
| brainstorm summary | `~:143` | `skills/brainstorm/SKILL.md:143` ✔ |
| implement wrap-up | `~:333` | **`skills/implement/SKILL.md:342`** |
| pr-review final report | `~:133` | `skills/pr-review/SKILL.md:133` ✔ |

The `~:140` figure is a `grep -n 'Step 5'` hit on a *passing mention* (`agents/swift-reviewer.md:140`),
not the heading — the exact error shape this campaign has now made **seven** times: a number taken from
a search offset instead of from the file. Every citation in the shipped §13 text must be opened.

**Fix.** Rewrite §13's Scope paragraph to name those four surfaces explicitly and mark the five
`VALID_AGENTS` reviewers out of scope, with the reason (they emit structured JSON; style guidance was
always a poor fit).

**Proof.** **M4** — delete one in-scope surface from the Scope paragraph; the doc-gate must fail. Assert
each of the four is named, individually, so removing one is not masked by the other three.

### 4.3 — The payload-region invariant is demoted, NOT deleted (Medium)

It stops being a carve-out and becomes a **boundary marker**: it states where §13 stops applying. It
stays because it is `capture.py::extract_status` (`mcp/review-synthesizer/capture.py:396`)'s real behaviour, and §1's executed example is the
evidence.

**The trap.** "Demote" reads like "soften". If the invariant's text is weakened while
`extract_status` is unchanged, the section documents a boundary that no longer matches the parser — and
the existing `test_payload_region_invariant_is_present_on_one_physical_line` gate could still pass.

**Fix.** Keep the invariant's wording and its executed evidence verbatim; change only its framing
sentence. **Proof — M5:** a test that the invariant text still round-trips against the parser, i.e. the
§1 example still yields `None` and the compliant form still parses. That binds the document to the code
rather than to itself, which is the only version of this test that cannot go inert.

### 4.4 — All ten dispositions must survive the simplification (Medium)

Carve-outs 1, 2, 3 and 5 exist to protect contracts that become out-of-scope. The temptation is to drop
those rows. **COREDEV-2602 §4.1 forbids it** — the table exists precisely so no rule is silently
dropped, and `test_exactly_ten_dispositions_one_row_each` enforces it.

**Fix.** Simplify a carve-out **only** where it protected an exclusively out-of-scope contract; keep any
that still protects an in-scope surface. Each of the ten keeps an explicit disposition.

**Determination still required at implementation time, stated as an open question rather than guessed:**
do the four in-scope surfaces carry *any* machine payload? If, say, `pr-review`'s Step-4 report ends in
a fenced block something reads, then rule 3's carve-out is still load-bearing and must stay. **This must
be settled by execution before the rows are touched** — §8 asks the reviewers to check it too.

**Proof.** **M6** — remove a rule row entirely → `test_exactly_ten_dispositions_one_row_each` fails.
**M7** — keep the row but strip its disposition marker → the row-scoped per-rule test fails.

### 4.5 — Update, never contradict, the 11 existing §13 tests (Medium)

`scripts/tests/test_doc_gates.py:284`, class `COREDEV2602_AgentOutputStyle`, carries **11** tests — the
ticket says 14. Enumerated:

`test_section_13_exists_before_cross_references` · `test_exactly_ten_dispositions_one_row_each` ·
`test_every_rule_declares_an_explicit_disposition` · `test_each_adapted_rule_carries_its_marker_in_its_own_row` ·
`test_parser_touching_rules_reference_the_invariant_by_name` ·
`test_payload_region_invariant_is_present_on_one_physical_line` ·
`test_invariant_covers_non_prose_payloads_too` · `test_precedence_clause_names_all_six_contracts` ·
`test_precedence_clause_states_the_contract_wins` · `test_remaining_is_marked_safety_information` ·
`test_attribution_names_the_source_licence_and_pinned_commit`

Two are directly at risk. `test_parser_touching_rules_reference_the_invariant_by_name` asserts that
parser-touching rules cite the invariant — if those carve-outs are simplified, the assertion must be
**inverted or replaced, never left asserting a removed carve-out**.
`test_precedence_clause_names_all_six_contracts` must be re-derived: if the reviewers are out of scope,
does the precedence clause still name six?

**Fix.** Rewrite in place, preserving the existing helpers (`_section13`, `_rows`) — `_rows` derives its
column count from the header specifically so a future column cannot make every row invisible and turn
the class into a no-op (`scripts/tests/test_doc_gates.py:305-308`). Reuse it; do not re-implement it.

**Proof.** **M8** — after the rewrite, revert §13 to its v2.6.1 text: the updated suite must **fail**.
A suite that passes against both the old and new section is asserting nothing about the change.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The doc-gate goes inert (this campaign's most repeated failure — six instances) | **High** | Every proof M1–M8 is a mutation shown failing *before* the fix, and M1/M5 bind the test to imported code rather than to restated expectations |
| `VALID_AGENTS` later gains `swift-reviewer`, silently invalidating §13's scope | Medium | §4.1's coupling test imports the tuple; M1 proves a hardcoded list would not catch it |
| A rule row is dropped as "no longer needed" | Medium | §4.4 + M6/M7; COREDEV-2602 §4.1 is the standing rule |
| A carve-out that still protects an in-scope surface is removed | **Medium** | §4.4's open determination must be executed before any row is edited — §8 puts it to the reviewers |
| Narrowing is read as "the reviewers may now write however they like" | Medium | State in §13 what is deliberately lost (rules 5 and 6 would have suited the reviewers) and that their *contracts* are unchanged and still mandatory |
| The change is cosmetic and nothing verifies it shipped | Medium | M8: the updated suite must fail against v2.6.1's §13 |

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

Baselines measured at `adda52d`: `test-hooks.sh` **304**, synthesizer **222**, scripts **312**, counts
`21/21/0/1`, hook events **10**. Floors, not equalities — re-derive at implementation time and print
`pwd` + `git rev-parse HEAD` beside any measurement.

Mutation proofs **M1–M8** above; each must be shown failing before the fix and passing after.

## 7. Implementation order

1. Execute §4.4's open determination: do any of the four in-scope surfaces carry a machine payload?
   Record the answer in the plan before editing rows.
2. Rewrite §13's Scope paragraph — four in-scope surfaces named, five `VALID_AGENTS` reviewers excluded
   with the reason, and what is deliberately lost.
3. Demote the payload-region invariant to a boundary statement, wording and evidence intact.
4. Simplify only the carve-outs step 1 proved out-of-scope; all ten dispositions stay explicit.
5. Rewrite the 11 tests; add the `VALID_AGENTS` coupling gate and the M5 parser round-trip.
6. Run M1–M8.
7. Version bump + CHANGELOG. State that this is a **scope narrowing, not a relaxation** — the
   reviewers' machine contracts are unchanged and still mandatory.

## 8. Open questions for the reviewers

1. **Do any of the four in-scope surfaces carry a machine payload?** §4.4 hangs on this and this plan
   deliberately does **not** guess. Check `agents/swift-reviewer.md:439`, `skills/brainstorm/SKILL.md:143`,
   `skills/implement/SKILL.md:342`, `skills/pr-review/SKILL.md:133`. If any does, which carve-outs must
   survive?
2. **Is the `VALID_AGENTS` coupling test the right boundary?** It ties a prose contract to a Python
   tuple. The alternative is asserting the four in-scope surfaces only and letting the exclusion be
   prose. Which fails more usefully?
3. **After narrowing, does the precedence clause still name six contracts** — or does naming contracts
   that no longer collide with any in-scope rule make the clause misleading?
4. **Is "demote, do not delete" the right call for the payload-region invariant**, given it now
   documents a boundary that no §13 rule can reach? The argument for keeping it is that it is executed
   truth about `extract_status` and the only place that truth is written down.

## 9. Notes

- Every claim here was executed or read from the file at HEAD `adda52d`; the intervening commits touched only CHANGELOG/README/plugin.json, so no cited line moved. Doing so corrected **four of
  the ticket's own figures**: `swift-reviewer` Step 5 at **`:439`** not `~:140`; `implement` Phase 6 at
  **`:342`** not `~:333`; **11** §13 tests not 14; **9** skills referencing the contracts not 8. The
  ticket's *reasoning* held up in every case — only its numbers drifted.
- The `~:140` error is instructive: `grep -n 'Step 5' agents/swift-reviewer.md` returns `:140` first,
  and `:140` is a passing mention inside a different step. Taking the first `grep` hit as the heading is
  the single most repeated citation error in this campaign.
- `capture.py`'s `VALID_AGENTS` contains **`prompt-review`**, not `swift-reviewer` — so "the five
  reviewers" is security/concurrency/ux-perf/accessibility/**prompt-review**. Any prose naming the five
  must use that list, not the four specialists plus the orchestrator.
