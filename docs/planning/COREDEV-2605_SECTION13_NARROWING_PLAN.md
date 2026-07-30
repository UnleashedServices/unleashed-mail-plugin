# COREDEV-2605 — Narrow AGENT_CONTRACTS §13 to client-facing output only

**Status:** Planning — **round 2 gated** (**gemini REQUEST_CHANGES ×5 / codex REQUEST_CHANGES ×6**), all
findings verified and fixed. M5 switches to the **cross-reference** form both reviewers preferred; the
scope table becomes an **exclusive schema** with canonical producer identities; the relocated precedence
protections gain a **preservation proof** — see §11. Round 1 is in §10. Awaiting round 3.
**Ticket:** `COREDEV-2605` (Epic `COREDEV-2485`) · follow-up to `COREDEV-2602`, which shipped §13 in v2.6.1
**Blocks:** `COREDEV-2604` (per the ticket, 2604 shrinks once this lands)
**Last Updated:** 2026-07-30 (round 2, post-gate revision)
**Measured against:** HEAD `adda52d` (v2.6.4, merged to main as `ff83f02`), worktree
`.claude/worktrees/opus5-review`, plugin **`2.6.4`** — round 1 caught this header saying `2.6.3`; the
frozen commit's manifest reads `2.6.4` (`.claude-plugin/plugin.json:3`).

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
> `agents/swift-reviewer.md:539` shows a JSON object that looks like a parsed payload on
> swift-reviewer's output. (Round 1 correction: it is an **unfenced blockquote**, not "a fenced JSON
> array" as earlier drafts described it — the conclusion held, the description did not.) It is the
> **input** to the
> `mcp__plugin_unleashed-mail_review-synthesizer__synthesize_review` tool call, not something
> swift-reviewer emits for a parser. The `VALID_AGENTS` allowlist is the authority here, not the
> presence of a JSON fence in the file.

**The gap the ticket does not close.** §13's scope would name the five reviewers in *prose*, while the
fact that makes the exclusion correct lives in a Python tuple. Add `swift-reviewer` to `VALID_AGENTS`
later — a plausible future change, since it *is* a reviewer by name — and §13's scope statement becomes
silently wrong, with no test failing.

**Fix — DISJOINTNESS, not equality. Round 1 changed this.** The doc-gate must assert the **coupling**,
but the safety property is not that §13's exclusion roster *equals* `capture.VALID_AGENTS`. It is that
**no in-scope producer is accepted by `capture`**. Assert two things, both against the tuple imported
from the module at test time:

1. the **four in-scope surfaces** are named exactly — an exact positive allowlist, asserted per surface,
   each carrying a **canonical producer identity** (the agent/skill name `capture` would see), not a
   prose description;
2. that set of producer identities has **empty intersection** with `capture.VALID_AGENTS`.

> **Round 2 removed a third condition that undid the first two.** Round 1 also required *"the `out` set
> contains every member of `capture.VALID_AGENTS`"*. Both reviewers independently showed that recreates
> exactly the prose churn §4.1 rejects equality for — the `out` column would have to grow whenever the
> tuple does — **and** it masks **M9**: adding `swift-reviewer` to the tuple already fails the
> containment assertion, so M9 could not distinguish a gate that checks the intersection from one that
> never does. The containment condition is **deleted**. Only the `in` set is compared against the tuple.

> **Why equality is wrong.** codex's argument, adopted: `VALID_AGENTS` is the canonical capture roster
> (`mcp/review-synthesizer/capture.py:130`) and the assembly validator already keeps its six
> implementation copies synchronised (`scripts/validate-plugin-assembly.py:426`,
> `check_reviewer_roster`). Requiring §13's prose roster to *equal* the tuple means adding any future
> captured specialist forces §13 prose churn — even though that specialist is already out of scope by
> virtue of the positive allowlist. Disjointness catches the dangerous change (`swift-reviewer` joining
> `VALID_AGENTS` while still named in scope) without coupling to changes that are harmless.
>
> gemini took the opposite position — that exact equality is "exactly the right boundary". This is a
> mechanism-level call and codex's reasoning is the stronger one; see §10.

**Proof — and it must reject a plausible wrong implementation.**
- **M1** hardcode the five names in the test instead of importing `VALID_AGENTS` → mutate the tuple
  (add `swift-reviewer`) and the gate must still fail. A hardcoded list passes and is inert.
- **M2** assert only that the section contains the word "excluded" → deleting a *name* must still fail.
- **M3** section-scoped rather than row-scoped per-rule assertions → a deleted disposition must still be
  detectable (this is COREDEV-2602's round-7 defect, documented at `scripts/tests/test_doc_gates.py:287-290`).
- **M9** *(round 1)* add `swift-reviewer` to `VALID_AGENTS` **without** editing §13 → the disjointness
  assertion must fail. This is the exact future change §4.1 exists to catch, and it is the one M1 only
  half-covers.

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

> **Round 1: M1/M2/M4 do not prove scope POLARITY, and this is a High finding codex constructed and
> executed.** All three are **presence-only** assertions — they check that a name appears in the
> section. A paragraph that lists all four intended surfaces as *"out of scope"* and all five reviewers
> as *"in scope"* contains every required name and **passes every one of them**, while stating the exact
> inverse of the plan's intent. No mutation in the M-list flips polarity or moves a name into unrelated
> explanatory prose.
>
> **Fix — a parseable scope table, not a prose paragraph.** §13's Scope becomes a two-column table
> (surface → `in`/`out`), and the gate asserts on the parsed table rather than on substring presence:
>
> - the **in** set equals exactly the four named surfaces, by **canonical producer identity**;
> - that set is **disjoint** from `capture.VALID_AGENTS`;
> - the table is **EXCLUSIVE and NORMATIVE**: it is the *only* scope statement, every row is one of
>   exactly `in`/`out`, rows are duplicate-free, and **any row that is unparseable, catch-all, aliased or
>   semantically overlapping is a FAILURE, not a skip**. Round 2's counterexample: codex passed every
>   round-1 assertion with an added row that semantically excludes all four `in` entries (an alias like
>   "all swift-reviewer output" does the same).
>
> **Do NOT reuse `_rows`.** Round 2 executed it: `_rows` matches `^\| (\d+) \|` — *numbered rule rows
> only* — and derives its column count from a `| # |` header (`scripts/tests/test_doc_gates.py:299-316`).
> Given a simulated scope table it returned rules 1–10 and ignored the table entirely. A **separate,
> fail-closed `_scope_rows` parser** is required, which raises on a malformed or unrecognised row rather
> than skipping it.
>
> **M10** — invert the polarity column wholesale; the gate must fail.
> **M11** — move an in-scope surface's name out of the table into surrounding prose, leaving the
> substring present; the gate must fail.
> **M12** *(round 2)* — add a **catch-all or aliased** row that overlaps the four `in` entries; the gate
> must fail. M10/M11 catch only wholesale inversion and name relocation.
>
> **Known residual, stated rather than papered over.** A table gate gives structure, not semantics:
> surrounding prose could redefine what `in` and `out` mean. Making the table normative and exclusive
> narrows this; it does not eliminate it. Recorded as accepted risk in §5.

### 4.3 — The payload-region invariant MOVES to §5, verbatim (Medium — reversed in round 1)

**Round 1 reversed this section's decision.** It previously said "demote, do not delete" — keep the
invariant inside a narrowed §13 as a boundary marker. codex's counter-argument is adopted: **keeping
parser-specific detail under a section defined to apply only where nothing parses re-creates exactly the
conceptual coupling the narrowing exists to remove.** A reader arriving at §13 would still have to reason
about a parser that, by §13's own new scope statement, cannot be involved.

**Fix — relocate, do not demote, and do not weaken.** The invariant moves **verbatim** to
`## 5. Code Review Pipeline` (`AGENT_CONTRACTS.md:247`), which already owns the specialist JSON/status
flow and is the contract that actually governs the producers it constrains. Nothing is lost: the wording
and §1's executed evidence transfer unchanged. §13 retains no copy — one authority, not two.

> This satisfies the original "do not delete" instinct, which was right about the *content* and wrong
> about the *location*. The invariant is executed truth about `extract_status`
> (`mcp/review-synthesizer/capture.py:396`) and must stay written down somewhere; §5 is where its
> producers are already defined.

**The trap is unchanged and still applies.** If the invariant's text is weakened while `extract_status`
is not, the contract documents a boundary that no longer matches the parser — and
`test_payload_region_invariant_is_present_on_one_physical_line` could still pass.

**M5 must be redesigned — as written it is INERT, and both reviewers proved it.** The old M5 was "a test
that the invariant text still round-trips against the parser". It cannot be:

- §13 contains **no executed example** to extract. `AGENT_CONTRACTS.md:475-488` states the invariant in
  prose only; the `Status: PARTIAL` / `Remaining:` snippet from §1 is not in the file (the sole
  `Remaining:` occurrence is at `:510`, in the precedence clause, in a different sense). Verified.
- So M5 could only assert two *independent* facts: that some prose exists, and that hardcoded fixtures
  behave a certain way in `extract_status` (`capture.py:396`). **codex executed exactly that
  marker-plus-two-fixtures test against the unchanged v2.6.1 §13 and it PASSED** — the definition of
  inert. The parser semantics are already covered independently at
  `mcp/review-synthesizer/tests/test_capture.py:459`.
- **Natural-language invariant text cannot round-trip through a parser.** That was the error.

**Fix — M5 is the CROSS-REFERENCE form. Round 2 chose it; both reviewers preferred it.**

Round 1 proposed embedding a machine-readable fixture block in the contract and executing it. Round 2
prototyped that and found the fatal objection: **a co-located fixture and oracle validate consistency,
not the invariant.** codex executed a strict extractor — it correctly failed against unchanged v2.6.1
§13, but *replacing the examples and their expected values together* also passed. So the round-1 claim
that "weakening the document's example necessarily fails" is **false**. gemini found the same class from
the other side: an extractor that iterates found blocks makes **zero assertions** when the old §13
contains none, passing vacuously.

**So parser truth lives in one place — the test suite — and the document points at it:**

1. Add the **exact ticket regression** to `TestExtractStatus`
   (`mcp/review-synthesizer/tests/test_capture.py:459` is the class heading): the §1 non-compliant
   multiline `Remaining:` block must yield `None`, and the compliant single-line form the full dict.
   **This test does not exist yet** — verified. `:512` covers the compliant single-line case and `:541`
   covers generic multiline wrap; neither is the ticket's example.
2. The relocated invariant in §5 **names that test**.
3. **M5** asserts only that the named test **exists and is collected** — a reference to a deleted or
   renamed test must fail.

The document binds to the code through a name that CI resolves, and neither half can be weakened
without the other failing.

### 4.4 — All ten dispositions must survive the simplification (Medium)

Carve-outs 1, 2, 3 and 5 exist to protect contracts that become out-of-scope. The temptation is to drop
those rows. **COREDEV-2602 §4.1 forbids it** — the table exists precisely so no rule is silently
dropped, and `test_exactly_ten_dispositions_one_row_each` enforces it.

**Fix.** Simplify a carve-out **only** where it protected an exclusively out-of-scope contract; keep any
that still protects an in-scope surface. Each of the ten keeps an explicit disposition.

**DETERMINATION — SETTLED IN ROUND 1, by both reviewers independently and identically.** The question
was whether the four in-scope surfaces carry any machine payload. **None of them is software-parsed:**

| surface | what it emits | parsed by |
|---|---|---|
| `swift-reviewer` Step-5 report (`agents/swift-reviewer.md:439`) | a Markdown report (`:590` `## Output Format`) | **nothing** — the JSON at `:538-540` is the **input** to the synthesizer tool call, and `capture()` rejects `swift-reviewer` (`mcp/review-synthesizer/capture.py:514`) |
| brainstorm summary (`skills/brainstorm/SKILL.md:143`) | prose for human approval, feeding plan creation | **nothing** |
| implement wrap-up (`skills/implement/SKILL.md:342`) | ordinary prose and next actions | **nothing** |
| pr-review final report (`skills/pr-review/SKILL.md:133`) | Markdown, possibly posted to GitHub | **nothing** — no downstream parser |

**Therefore no parser-specific carve-out needs to survive.** Rules 1, 2, 3 and 5 may be simplified.

> **But codex's caveat is adopted and matters:** *lack of a parser does not license omission from a
> mandatory human report.* Rules 4 and 9 must still protect the completeness of `swift-reviewer`'s
> **All Issues (Consolidated)** table (`agents/swift-reviewer.md:592`, `:636`). The narrowing removes the
> *parser* justification for those rules, not the *contract* justification. Simplify the carve-out's
> stated reason; do not drop the protection.

**Process correction (codex, High).** §7 step 1 previously said to execute this determination during
implementation and *record the answer in the plan*. That edit would change the plan **after** approval,
invalidating the reviewed digest and forcing another round (`AGENT_CONTRACTS.md:92`). The determination
therefore had to be settled **in the gate**, which is what round 1 did — and §7 step 1 is removed.

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
`test_precedence_clause_names_all_six_contracts` must be re-derived. **Round 1 settled this: it must
not.** Both reviewers agreed the clause becomes misleading — it enumerates six contracts that, after the
narrowing, cannot collide with any in-scope rule, implying they might appear in in-scope text and must be
worked around. That is the confusion the narrowing exists to remove.

**Fix.** The six protections **move to their owning contract sections** (`AGENT_CONTRACTS.md:503-513` is
the current clause), and §13 retains a one-sentence statement that surfaces outside the four-item
allowlist remain governed by their existing contracts.

**Destinations, named — round 2 required this.** The six are: the JSON findings array's completeness,
the `Status:` line, the Output Contract detail trailer, the `VERDICT:` line, the final fenced JSON block,
and the `BLOCKED — …` result prefix (`AGENT_CONTRACTS.md:505-513`).

| protection | destination |
|---|---|
| JSON findings array · `Status:` line · detail trailer · final fenced JSON block | **§5 Code Review Pipeline** (`AGENT_CONTRACTS.md:247`), which already defines the specialist JSON/status flow |
| `VERDICT:` line | **§2 Plan → Implement Contract** (`AGENT_CONTRACTS.md:71`) |
| `BLOCKED — …` result prefix | **NO OWNER EXISTS** — verified: it occurs only at `:501`, `:509`, `:513`, all inside §13 itself. §8 Q7 asks where it belongs; it must be assigned before implementation, not discovered during it |

**Round 2's finding: the relocation had no preservation proof.** Asserting only that §13 *stops*
enumerating the six would pass if a protection were relocated **and then deleted**, and M8 reverts only
§13 so it cannot see content moved elsewhere.

**M13** *(round 2)* — **one mutation-tested assertion per protection, in its destination section.**
Delete any one relocated protection from its new home; its assertion must fail. Six assertions, six
mutations.

`test_precedence_clause_names_all_six_contracts` is **replaced**, not deleted: assert the short pointer
is present, that §13 no longer enumerates the six, **and** that all six survive at their destinations.

**Fix.** Rewrite in place, preserving the existing helpers (`_section13`, `_rows`) — `_rows` derives its
column count from the header specifically so a future column cannot make every row invisible and turn
the class into a no-op (`scripts/tests/test_doc_gates.py:305-308`). Reuse it; do not re-implement it.

**Proof.** **M8** — after the rewrite, revert §13 to its v2.6.1 text: the updated suite must **fail**.
A suite that passes against both the old and new section is asserting nothing about the change.
**M8 is the whole-suite backstop and must be run explicitly**; round 1 found no faithful whole-suite
old/new bypass, but confirmed that M5 and the scope semantics can each go inert *individually* without
M8 noticing, which is why M9/M10/M11 exist.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The doc-gate goes inert (this campaign's most repeated failure — **seven** instances, M5 being the newest) | **High** | Every proof M1–M11 is a mutation shown failing *before* the fix. M1/M9 bind to the imported tuple; M5 is redesigned to **execute** a fixture the document carries, because round 1 proved the previous form passed against unchanged v2.6.1 §13 |
| Presence-only assertions pass a scope statement of the **opposite** polarity | **High** | §4.2's exclusive normative table + M10/M11/M12, all executed counterexamples |
| A relocated protection is quietly deleted at its destination | **High** | M13 — one mutation-tested assertion per protection. M8 reverts only §13 and cannot see this |
| Prose around the scope table redefines `in`/`out` | Medium | **Accepted residual** — §4.2 states it. A structural gate cannot assert semantics; the table is made normative and exclusive to narrow the surface |
| `VALID_AGENTS` later gains `swift-reviewer`, silently invalidating §13's scope | Medium | §4.1's coupling test imports the tuple; M1 proves a hardcoded list would not catch it |
| A rule row is dropped as "no longer needed" | Medium | §4.4 + M6/M7; COREDEV-2602 §4.1 is the standing rule |
| A carve-out that still protects an in-scope surface is removed | **Medium** | §4.4's determination is **settled** (round 1, both reviewers): none of the four is parsed. Rules 4/9 keep protecting the consolidated issue table on contract grounds |
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

Mutation proofs **M1–M13** above. **Polarity, corrected in round 2:** the clean post-fix implementation
must **PASS**, and then **each mutant must FAIL**. Round 1's wording ("each must be shown failing before
the fix and passing after") describes a regression test, not a mutation proof, and would have been
satisfied by a suite that never rejects a mutant.

## 7. Implementation order

1. Rewrite §13's Scope as a **parseable two-column table** (surface → `in`/`out`) — the four in-scope
   surfaces, the five `VALID_AGENTS` reviewers marked out with the reason, and what is deliberately
   lost. §4.4's determination is already settled in this plan; do **not** re-open it, and do not edit
   the plan during implementation (that invalidates the reviewed digest).
2. **Move** the payload-region invariant verbatim to `## 5. Code Review Pipeline`
   (`AGENT_CONTRACTS.md:247`), with its machine-readable fixture block. §13 keeps no copy.
3. Move the precedence clause's six protections to their owning sections; §13 keeps a one-sentence
   pointer.
4. Simplify the carve-outs §4.4 proved out-of-scope; all ten dispositions stay explicit, and rules 4/9
   keep protecting the consolidated issue table on contract grounds.
5. Rewrite the 11 tests; add the disjointness gate, the scope-table polarity gate, and the redesigned
   M5 fixture-execution gate.
6. Run **M1–M13** with the corrected polarity: clean candidate passes, then every mutant fails.
7. Version bump + CHANGELOG. State that this is a **scope narrowing, not a relaxation** — the
   reviewers' machine contracts are unchanged and still mandatory.

## 8. Open questions for the reviewers

1. ~~Do any of the four in-scope surfaces carry a machine payload?~~ **ANSWERED in round 1 — none does.**
   Both reviewers checked all four independently and agreed. No parser carve-out survives; see §4.4's
   table. codex's caveat adopted: rules 4/9 still protect the consolidated issue table on *contract*
   grounds, not parser grounds.
2. ~~Is the `VALID_AGENTS` coupling the right boundary?~~ **ANSWERED in round 1 — coupling yes, EQUALITY
   no.** Assert an exact four-surface positive allowlist plus **empty intersection** with the tuple. The
   reviewers split here (gemini: equality is right; codex: over-coupled) and **codex is adopted** — see
   §4.1 and §10.
3. ~~Does the precedence clause still name six contracts?~~ **ANSWERED in round 1 — no.** Both reviewers
   called it misleading. The protections move to their owning sections; §13 keeps a one-sentence
   pointer. See §4.5.
4. ~~Is "demote, do not delete" right for the payload-region invariant?~~ **ANSWERED in round 1 —
   RELOCATE, verbatim.** "Do not delete" was right about the content and wrong about the location. See
   §4.3.

5. ~~Fixture block or cross-reference for M5?~~ **ANSWERED in round 2 — CROSS-REFERENCE.** Both
   reviewers preferred it, and codex's prototype showed the fixture form validates fixture/oracle
   consistency rather than the invariant. See §4.3.
6. ~~Does relocation leave §13 unable to state its boundary?~~ **ANSWERED in round 2 — NO.** Both
   reviewers: an exclusive positive allowlist plus a forward-reference to §5 is sufficient; §13 should
   not repeat parser mechanics.

**New open question for round 3:**

7. **Who owns `BLOCKED — …`?** Verified: it appears **only** inside §13 (`AGENT_CONTRACTS.md:501`,
   `:509`, `:513`), so relocating it has no obvious destination. It is a shared handoff prefix used by
   workflow skills rather than by the review pipeline, so §5 is the wrong home and §2 covers only the
   plan-review verdict. Options: give the Output Contract its own section; fold it into §2 as part of
   the implement handoff; or leave it in §13 as the one genuinely cross-cutting payload — which would
   weaken the "§13 mentions no machine payloads" property M13 otherwise gives.

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

## 10. Round-1 gate outcome

**gemini `REQUEST_CHANGES` (3 findings) · codex `REQUEST_CHANGES` (6 findings).** Frozen at
`2dc7f5c12ba901aa1db4bc7fc15f696f57098e28`, plan sha256 `9036f6b6…`; codex re-verified that both the
working file and the blob at that commit still hash to it, and that no file changed during the review.
Transcripts: `/tmp/rev/agy-2605r1.txt` (2,798 B) and `/tmp/rev/2605r1-codex.txt` (317,216 B, 28
occurrences of the ticket key). Every finding verified here before the plan was touched.

**A note on how this round was assembled.** gemini's review ran first and was interrupted before codex
finished. Rather than re-run both, the plan's digest was compared against gemini's freeze: **byte-
identical** (`9036f6b6…`), with `AGENT_CONTRACTS.md` and `mcp/review-synthesizer/capture.py` untouched
since. A review is bound to a plan by its **digest**, not by the HEAD it happened to run at, so gemini's
verdict still holds on exactly these bytes and only codex needed running.

### Findings

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **M5 is inert.** §13 contains no executed example to round-trip, so M5 could only assert two independent facts | **confirmed by execution** — codex ran the marker-plus-fixtures test against unchanged v2.6.1 §13 and it **PASSED**; and `Status: PARTIAL`/`Remaining:` appears nowhere in `AGENT_CONTRACTS.md` (sole `Remaining:` is `:510`, different sense) | M5 redesigned to embed a machine-readable fixture block and **execute** it; cross-reference alternative stated |
| 2 | **both** | **§4.4's determination**: do the four in-scope surfaces carry a machine payload? | **settled — none does**, both reviewers checked all four independently and agreed | §4.4 now states it as a table with the evidence; §7 step 1 removed |
| 3 | **both** | the precedence clause naming six contracts becomes **misleading** after narrowing | **confirmed** — `AGENT_CONTRACTS.md:503` | protections move to their owning sections; §13 keeps a one-sentence pointer; the test is **replaced**, not deleted |
| 4 | codex | **M1/M2/M4 do not prove scope POLARITY** — presence-only assertions pass a paragraph labelling all four surfaces "out of scope" and all five reviewers "in scope" | **confirmed** — codex constructed and executed the counterexample | §4.2 becomes a **parseable scope table**; M10/M11 added |
| 5 | codex | the payload invariant should **move** to `## 5. Code Review Pipeline`, not stay in a narrowed §13 | **confirmed** — `AGENT_CONTRACTS.md:247` is that section and already owns the specialist JSON/status flow | §4.3 **reversed**: relocate verbatim. See below |
| 6 | codex | exact equality with `VALID_AGENTS` is **over-coupled**; disjointness is the useful property | **confirmed** — `capture.py:130`; `validate-plugin-assembly.py:426` already syncs the six copies | §4.1 rewritten to allowlist + empty intersection; **M9** added |
| 7 | codex | §7 step 1 would have edited the plan **after** approval, invalidating the reviewed digest | **confirmed** — `AGENT_CONTRACTS.md:92` | determination settled in the gate; step 1 removed |
| 8 | codex | `swift-reviewer.md:539` is an **unfenced blockquote**, not "a fenced JSON array" | **confirmed** — printed | description corrected; conclusion unchanged |
| 9 | codex | the header says plugin `2.6.3`; the frozen manifest says `2.6.4` | **confirmed** | corrected |

### The one reversal, and why

§4.3 previously said **"demote, do not delete"** — keep the payload-region invariant inside a narrowed
§13 as a boundary marker. §8 Q4 asked the reviewers about exactly this. codex's answer is adopted:
keeping parser-specific detail under a section *defined to apply only where nothing parses* re-creates
the conceptual coupling the narrowing exists to remove.

The instinct behind "do not delete" was right about the **content** and wrong about the **location**. The
invariant is executed truth about `extract_status` and must stay written down; it now lives verbatim in
`## 5. Code Review Pipeline`, where its producers are already defined, and §13 keeps no copy.

### Where the reviewers diverged

Only on §8 Q2. gemini called exact equality with `VALID_AGENTS` "exactly the right boundary" and rated it
Low/approving; codex rated it Medium and argued for allowlist-plus-disjointness. **codex is adopted** —
it is a mechanism-level call, which is where the standing rule prefers codex, and its reasoning survives
inspection: equality forces §13 prose churn on changes that are already harmless under a positive
allowlist, while disjointness catches the one change that is actually dangerous.

Otherwise the two converged unusually closely — both independently settled Q1 identically, both called
the precedence clause misleading, and both found M5 inert by different routes (gemini by noticing §13 has
no example to extract; codex by executing the proposed test against the old section). Consistent with the
standing note that gemini is reliable on prose/contract work even where it is not on mechanism detail.

## 11. Round-2 gate outcome

**gemini `REQUEST_CHANGES` (5 findings) · codex `REQUEST_CHANGES` (6 findings).** Frozen at
`fc35834f5a1161c30a0c18d7ecbb7deb761d4a42`, plan sha256 `920ff994…`; both reviewers re-verified the
digest and codex confirmed no file changed. Transcripts: `/tmp/rev/2605r2-agy.txt` (3,194 B,
`TREE=clean`) and `/tmp/rev/2605r2-codex.txt` (269,257 B, 51 ticket-key occurrences). Every finding
triaged by execution.

**Both reviewers converged on the two design questions round 1 left open** — cross-reference over
embedded fixtures, and relocation to §5 — so §8 Q5 and Q6 are answered and struck through.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | §4.1 argues disjointness to avoid coupling, then §4.2 mandates `out ⊇ VALID_AGENTS`, **recreating the churn** — and it **masks M9**, since that mutation already fails containment | **confirmed** — found independently by each reviewer | the containment condition is **deleted**; only the `in` set is compared to the tuple, by canonical producer identity |
| 2 | **both** | the redesigned M5 does not bind document to code — a co-located fixture and oracle validate each other. codex: replacing examples *and* expectations together passes. gemini: an extractor iterating zero found blocks asserts nothing | **confirmed by execution** — codex prototyped the extractor | **M5 becomes the cross-reference form**; the exact ticket regression moves into `test_capture.py`, which **does not yet contain it** (`:512` is the compliant case, `:541` generic multiline wrap) |
| 3 | codex | the scope table is not exclusive — a catch-all or aliased row semantically excluding all four `in` entries passes M4/M10/M11 | **confirmed** — codex constructed it | table made **exclusive and normative**; **M12** added for catch-all/alias/overlap |
| 4 | codex | **`_rows` cannot parse the scope table** — it matches `^\| (\d+) \|` numbered rule rows only | **confirmed by execution** — given a simulated scope table it returned rules 1–10 and ignored it | a separate **fail-closed `_scope_rows`** parser is specified |
| 5 | codex | relocating the six protections has **no preservation proof** — deleting one after the move passes, and M8 reverts only §13 | **confirmed** | destinations tabled; **M13** adds one mutation-tested assertion per protection |
| 6 | codex | "each mutation must fail before the fix and pass after" is **backwards** for mutation testing | **confirmed** | corrected: the clean candidate passes, then every mutant fails |
| 7 | gemini | a structural table gate cannot stop surrounding prose redefining `in`/`out` | **confirmed, and irreducible** | recorded as an **accepted residual** in §5 rather than papered over |
| 8 | codex | the risk register still called §4.4 open, contradicting the settled determination | **confirmed** | corrected |
| 9 | codex | `test_capture.py:459` is the class heading, not the regression | **confirmed** — printed | §4.3 now cites it as the class and states the regression must be added |

**A gap round 2 surfaced that neither round had noticed:** `BLOCKED — …` has **no owning section**. It
occurs only at `AGENT_CONTRACTS.md:501`, `:509` and `:513`, all inside §13 — so "move each protection to
its owner" has no destination for it. §8 Q7 puts the choice to round 3 rather than inventing one.
