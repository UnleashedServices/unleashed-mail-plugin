# COREDEV-2605 — Narrow AGENT_CONTRACTS §13 to client-facing output only

**Status:** Planning — **round 15 gated** (**both arms**). **Step 4 survived a round intact** — both arms verified the nearest-enclosing-heading walk for all nine rows — and both then broke **step 3**: a gate storing each fingerprint's line `F` and reusing M12i's `+1` delta passes every existing mutant while failing on a harmless blank line. Step 3 now mandates a **content-driven search of the current file**, no stored or derived line, **exactly one** occurrence — with **M12j**, the positive body-shift case, as its proof. Fences are now CommonMark-**complete** (≤3-space indent, matching delimiter char), the taxonomy says **three** kinds, and §4.5 names an **eighth** at-risk test. See §24. Previously — **round 14 gated** (**gemini 2 High · codex 3 High + 2 Medium**). gemini tried to build a wrong gate and **failed** (M12g caught it) — **codex built one that survives**: a *shift-aware* equality gate that accepts the clean document and every M12i parameterisation without ever resolving a section. So **the gate's ALGORITHM is now mandated** rather than inferred from its mutants, with a new step 4 — **the anchor must be the NEAREST ENCLOSING real heading of the fingerprint** (a sole-H1 anchor passed all three old checks). Positive metamorphic cases are now a **third proof kind** (M12i/M1p/M3p) propagated to every polarity statement; fences are **CommonMark**, not substring toggles; and §4.5 names **seven** at-risk tests. See §23. Previously — **round 13 gated** (**codex `REQUEST_CHANGES` 1 High + 2 Medium; the gemini arm IMPLEMENTED the plan instead of reviewing it — contained by the isolation harness, no verdict, not counted**). Two real defects in round 12's own fix: the mutants are all **rejection-only**, so an anchor-**equality** gate still passes every one of them — closed by **M12i**, a *positive* metamorphic case the gate must **accept**; and **all five fingerprints live inside code fences**, so a non-fence-aware scanner terminates each section before reaching them and **rejects the clean document** — section boundaries are now fence-aware. §4.5 itself now names **four** at-risk tests. See §22. Previously — **round 12 gated** (**both arms `REQUEST_CHANGES`; codex 3 High + 1 Medium**). Two more wrong gates, both narrower than round 11's: **all four anchor mutants targeted `verdict-report`**, so a gate resolving only that row passed every one of them — mutants are now **parameterised across all nine rows**; and **four `out` surfaces shared the generic `## Output Format` fingerprint**, so a security↔concurrency swap was accepted — fingerprints are now **unique per surface** (verified) with **M12h** proving it. Step 2's residual anchor-equality wording is scoped to the triple, and §4.5 must name both pinned test maps. See §21. Previously — **round 11 gated** (**gemini `REQUEST_CHANGES` 3 High + 2 Medium · codex `REQUEST_CHANGES` 2 High + 1 Medium**). **Both arms independently constructed a wrong gate that passes every mutant the plan had** — so the **anchor column is no longer equality-checked** (triples are; anchors are resolution-checked), and **M12f** (swap two anchors → pins check (iii) to the table) and **M12g** (non-heading anchor → pins check (ii)) are added. M3's **exactly one** classifier is now mandated by step 5 itself; **M4** was pinned to the Scope paragraph the narrowing deletes; step 6 now orders M5's **isolated** regressions; and intra-document references are **by name, never by line**. See §20. Previously — **round 10 gated** (**gemini `REQUEST_CHANGES` 2 High · codex `REQUEST_CHANGES` 1 High**). **M3's marker failed for the third time, the same way twice:** `**Adapted**` was pinned to a value §4.4 permits the narrowing to change (rule 3 may legitimately become `**Adopted**`), so the strong gate would fail on the **clean** document. M3 is now a **membership** test — each row carries exactly one classifier from the closed vocabulary — which is invariant under every rewrite step 5 allows. **M12d retargeted to `agents/swift-reviewer.md:439`**, a real heading whose section lacks `### Verdict:`, so it passes the heading check and fails the fingerprint check, proving check (iii) reads the anchor **from the table**. Rounds 7-10 are in §16-§19. Previously — **round 9 gated** (**gemini `REQUEST_CHANGES` 1 High · codex `REQUEST_CHANGES` 3 High + 1 Medium**). **Every finding is against round 8's own fixes.** Step 2 mandated four columns and shipped a **five**-column table (the fingerprints now live in the gate, test-only, with the literal four-column §13 table separate); **M2's mutant row was three cells** and is now the full four-column row with the anchor retained; **M3's marker was not guaranteed to survive** the simplification step 5 orders, so it is now the disposition classifier `**Adapted**` with step 5 **pinning the classifier vocabulary**; and **M12d proved nothing about the fingerprint** (`:538` is a blockquote, not a heading), so **M12e** is added. Rounds 7-9 are in §16-§18. Previously — **round 8 gated** (**gemini `REQUEST_CHANGES` 1 High + 1 Medium · codex
`REQUEST_CHANGES` 2 High + 1 Medium**). Both reviewers again found the **same High**, and it is the same
*class* as round 6's: **round 7's `anchor` column reached §4.2 and never reached §7 step 2**, which still
mandated a three-column table — so **M12d had no column to mutate**. Step 2 now ships the four-column
table with the **exact nine anchors and fingerprints**, `verdict-report` anchored at
`agents/swift-reviewer.md:590` (not the broad `:439`, which also contains the tool input at `:538`).
**M2's differential is fixed on the mutated side too** — round 7 fixed the clean document and broke the
mutant, because a deleted `out` name makes the fail-closed parser raise; the mutation is now a
`producer_id` **re-pairing**, which keeps nine parseable rows. **M3 gets a concrete marker** — `per the
payload-region invariant`, present in five rule rows. Rounds 7 and 8 are in §16 and §17; **§16 was
reconstructed in round 8 from the transcripts, having never been written.** Previously — round 6 gated
(**gemini REQUEST_CHANGES / codex REQUEST_CHANGES**). Both
reviewers found the **same High**: the two-column `surface → scope` instruction still contradicted the
three-column triple schema. Also — the §13/§14 split and §14's creation are **one indivisible step**
(either ordering breaks: a lagging helper swallows §14; a leading one raises `ValueError` **during
implementation, in the window before §14 exists**); **M2** moved to gate-adequacy; the round-5
digest was the round-4 value copied forward. See §15.
*(Round 7 correction: this header previously attributed that `ValueError` to **M8's `v2.6.1` revert**.
That is wrong, and §16 rejects it — M8 replaces **only §13** (`:389`, `:414`, `:426`), so `## 14.`
survives the revert and `text.index` resolves. The hazard is real but lives in the implementation
window, not in M8.)* Previously — round 5 gated
(**gemini REQUEST_CHANGES / codex REQUEST_CHANGES**): adding §14
**breaks `_section13()`**, which ends at `## Cross-references` and would swallow it; M5's ticket example
has **two independent rejection causes** that mask each other; and M1/M3 are gate-adequacy comparisons,
not candidate mutants. See §14. Previously — round 4 gated (**gemini REQUEST_CHANGES ×5 / codex REQUEST_CHANGES ×4**). The
schema now validates approved **triples**, not independent column allowlists; **M5b's polarity was
backwards** and is corrected; and `BLOCKED — …` gets a **new shared section §14**. See §13. Previously —
round 3 gated (**gemini REQUEST_CHANGES ×3 / codex REQUEST_CHANGES ×4**). The
scope table gains a **closed lexical schema** (free text cannot reject paraphrase); M5's
"exists and is collected" is strengthened because collection permits a no-op; and `BLOCKED — …` is
reframed — it has no **shared** owner in `AGENT_CONTRACTS.md`, but real contracts in two agent bodies.
See §12. Rounds 1-2 are in §10-§11; rounds 3-6 are in §12-§15.
**Ticket:** `COREDEV-2605` (Epic `COREDEV-2485`) · follow-up to `COREDEV-2602`, which shipped §13 in v2.6.1
**Blocks:** `COREDEV-2604` (per the ticket, 2604 shrinks once this lands)
**Last Updated:** 2026-07-31 (round 15, post-gate revision — step 3 content-driven; M12j body-shift case)
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
- **M2** *(gate-adequacy; weak predicate corrected in round 7, mutation corrected in round 8)* replace the
  row-level assertions with a **weak predicate the clean §13 is GUARANTEED to satisfy** — `the parsed
  table has exactly nine rows` — and mutate by **re-pairing one row's `producer_id` with another
  allowlisted `producer_id`**, keeping every other cell **including the anchor** byte-identical:

  `| security-findings | concurrency-reviewer | out | agents/security-reviewer.md:203 |`

  The strong triple-set gate **fails**, the weak row-count gate **passes**, and on the clean document
  both pass — a complete differential with a valid baseline on both documents.
  *(Round 9: this mutant was written as a **three**-cell row, `| security-findings | concurrency-reviewer
  | out |`, which under the four-column schema is **malformed** — so the fail-closed parser raises and
  the weak side fails on the mutated document all over again. That is the **third** consecutive round in
  which M2's mutant has broken its own baseline, and the second time by the same mechanism. Root cause:
  the mutant row was written in round 8 against the three-column schema and never updated when the
  `anchor` column landed in the same round. **The anchor is retained deliberately** — mutating it too
  would make this M12d, not M2.)*
  **This is M12c's mutation run as a differential**, exactly as M1 reuses M9's `VALID_AGENTS` mutation:
  the mutation is shared, the two proofs are not — M12c asserts the clean gate rejects it, M2 asserts the
  weakened gate does not.
  *(Round 8: round 7 fixed the clean-document half and broke the mutated half. Its mutation deleted an
  `out` **name**, which produces a row the fail-closed `_scope_rows` parser must **raise** on by design
  (`:252`) — so the weak side **failed on the mutated document** and the differential still had no valid
  baseline. Under a fail-closed parser the only usable mutation is one that keeps all nine rows
  **parseable and allowlisted**, which re-pairing does and deletion cannot. Round 7's own rule — a
  gate-adequacy mutant is meaningful only when its weak side passes — applies to **both** documents.)*
- **M3** *(differential made executable in round 8)* section-scoped rather than row-scoped per-rule
  assertions → a deleted disposition must still be detectable (COREDEV-2602's round-7 defect, documented
  at `scripts/tests/test_doc_gates.py:287-290`).
  **Marker:** *any* classifier from the closed vocabulary — a **membership** test, never a fixed token.
  **Row-scoped (strong) assertion:** `rows[N]` contains **exactly one** of `{**Adapted**, **Adopted**,
  **Restated positively**}`, for every N in 1..10 — and **§7 step 5 mandates exactly that**, so the
  assertion and the document requirement are the same sentence. *(Round 14, both arms: step 5 previously
  required only "an explicit classifier from" the vocabulary, which a disposition like `**Adopted** —
  formerly **Adapted** for the removed parser carve-out` satisfies while carrying **two** tokens and
  failing the strong assertion **on the clean document**. Requiring exactly one in the operative step is
  what makes the differential's baseline hold; asserting it in the test alone would have re-created the
  same defect a third time.)* **Section-scoped (weak) assertion:** the section
  contains at least one of them. **Mutation:** delete rule **3**'s disposition cell.
  **Why it discriminates:** after the deletion `rows[3]` carries **no** classifier, so the strong
  assertion **fails**; the other nine rows still carry theirs, so the weak assertion **passes**. On the
  clean document both pass — whatever classifier each rule ends up with.
  **The proof is guaranteed because §7 step 5 pins the classifier vocabulary** — every one of the ten
  dispositions keeps exactly one explicit classifier drawn from `{**Adapted**, **Adopted**, **Restated
  positively**}. M3 asserts *that mandated property*, never a particular value of it.
  *(Round 13, from BOTH arms: round 12 hardcoded `**Adapted**` for rule 3. But §4.4 (`:414`) expressly
  permits simplifying rule 3's carve-out, and that carve-out is the **only reason** its disposition is
  currently *Adapted* (`AGENT_CONTRACTS.md:494`) — so a compliant narrowed row could legitimately read
  `**Adopted** — end with one concrete next action.`, satisfying the pinned vocabulary while making the
  strong assertion fail **on the clean document, before any mutation**. That is the third marker M3 has
  had, and the first two failed identically: **the differential was pinned to a value this plan permits
  the narrowing to change.** Membership is invariant under every rewrite step 5 allows.)*
  *(Round 9, from codex: the round-8 marker was the prose phrase `per the payload-region invariant`,
  present today in rules 1, 2, 3, 5 and 10. Round 8 argued it survives because §7 step 5 keeps "all ten
  dispositions explicit" — but **explicit is not the same as unchanged**. §4.4 (`:390`) expressly permits
  simplifying those carve-outs and step 5 (`:619`) operationally orders it, and the payload-region
  invariant is itself being **relocated to §5** by §4.3 — so the rules that cite it are exactly the ones
  whose wording the plan expects to change. Rule 3 could legitimately lose the phrase, and then the
  **strong** row-scoped gate fails on the clean narrowed document. Round 8 fixed round 7's "no guaranteed
  survivor" defect with another marker that merely looks durable; the classifier is durable **by
  mandate**.)*
- **M9** *(round 1)* add `swift-reviewer` to `VALID_AGENTS` **without** editing §13 → the disjointness
  assertion must fail.
- **M1p** *(positive metamorphic, round 14)* add a **harmless unrelated** captured specialist to
  `VALID_AGENTS` — one that appears nowhere in §13's `in` set — and the gate must **PASS**. *(codex: M1
  and M9 both mutate the tuple by adding the *dangerous* `swift-reviewer`, so a gate that simply asserted
  `VALID_AGENTS == EXPECTED_FIVE` satisfies both while violating §4.1's decision that **disjointness**,
  not equality, is the boundary. Only a mutation the gate must **accept** separates them — the same
  argument that produced M12i, applied to the other deliberately-non-equality mechanism in this plan.)*
- **M3p** *(positive metamorphic, round 14)* change one rule's classifier to a **different member** of the
  closed vocabulary — e.g. rule 3 `**Adapted**` → `**Adopted**` — and the gate must **PASS**. *(codex: an
  implementer could satisfy M3 with an updated **exact per-rule classifier map**, which passes the clean
  document and rejects M3's deletion while violating the membership-only design §4.1 mandates. M3p is
  what makes the map fail.)* This is the exact future change §4.1 exists to catch, and it is the one M1 only
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

**Proof.** **M4** — delete one in-scope surface's **row from the scope table**; the doc-gate must fail.
Assert each of the four `in` rows is present individually, so removing one is not masked by the other
three. *(Round 14, from gemini: M4 read "delete one in-scope surface from the **Scope paragraph**" — but
§4.2 and §7 step 2 **replace that paragraph entirely** with the parseable four-column table, so the
mutant targeted text the narrowing deletes and was unimplementable. Same class as M3's three markers:
**a proof pinned to a value this plan itself changes.** The sweep §7 asked for found this one; M1, M2,
M5, M9-M13 were re-checked and are stated against the table or the parser, not against prose.)*

> **Round 1: M1/M2/M4 do not prove scope POLARITY, and this is a High finding codex constructed and
> executed.** All three are **presence-only** assertions — they check that a name appears in the
> section. A paragraph that lists all four intended surfaces as *"out of scope"* and all five reviewers
> as *"in scope"* contains every required name and **passes every one of them**, while stating the exact
> inverse of the plan's intent. No mutation in the M-list flips polarity or moves a name into unrelated
> explanatory prose.
>
> **Fix — a parseable scope table, not a prose paragraph.** §13's Scope becomes a **three-column** table
> (`surface_id | producer_id | scope`) — see the exact schema below, which supersedes the two-column
> sketch this paragraph originally carried — and the gate asserts on the parsed table rather than on
> substring presence:
>
> **CLOSED LEXICAL SCHEMA — round 3 made it concrete; round 4 made it CLOSED.**
>
> **Round 4: independent column allowlists are not a closed schema.** Both reviewers showed the same
> hole from different sides — validating `surface_id`, `producer_id` and `scope` *separately* permits
> false Cartesian products. gemini's counterexample `| brainstorm-summary | implement | in |` passes
> every check (all three terms are valid, the `in` surface set still matches exactly, and `implement`
> is disjoint from `VALID_AGENTS`) while asserting that `implement` produces the brainstorm summary.
> codex reached the same conclusion via M12b's blind spot for same-scope false pairings.
>
> **So the schema validates an exact finite set of approved `(surface_id, producer_id, scope)` TRIPLES**,
> not membership in three independent vocabularies. Any triple outside the approved set is a hard
> failure, and **M12c** *(round 4)* is its mutant: swap the `producer_id` of one `in` row for another
> valid producer → the gate must fail. A free-text two-column table cannot reject
> semantic paraphrase; codex's counterexample row `| every report emitted by the review orchestrator,
> including its Step-5 report | out |` leaves the exact `in` set and tuple-disjointness unchanged and
> passes. So the table's columns are **`surface_id | producer_id | scope`**, every field drawn from a
> **finite allowlist**, and **any unknown key is a hard failure**. Prose descriptions are not row
> content; they may sit outside the table.
>
> > **Round 7 High — the triples bind tokens to tokens, never a token to a SURFACE.** Allowing prose
> > definitions to sit outside the table (the sentence immediately above) leaves every `surface_id`
> > **ungrounded**, and the gate cannot see it. codex's counterexample: define `verdict-report` as *the
> > JSON object passed to the synthesizer* (`agents/swift-reviewer.md:538`) and keep the approved row
> > `verdict-report | swift-reviewer | in` untouched. **Every check still passes** — the allowlists,
> > uniqueness, polarity, disjointness, and M4/M10-M12 — while §13 has been silently redirected from the
> > client-facing Step-5 report onto **tool input**, which is the precise confusion §4.1's own trap
> > warning records. Round 4 closed *false pairings between tokens*; this is a false binding **beneath**
> > a correct token.
> >
> > **Fix — every `surface_id` carries a gated repository anchor.** The table gains a fourth column,
> > `anchor`, holding a `path:line` (or an exact heading) that identifies the surface in the repo, and
> > the gate asserts each anchor **resolves** and matches a per-surface expected fingerprint. A prose
> > definition elsewhere is then not authoritative and cannot redirect the ID.
> > **M12d (round 7; retargeted round 13):** leave all nine triples byte-identical and change one
> > surface's **anchor** to `agents/swift-reviewer.md:439` — a real heading whose section carries no
> > `### Verdict:` — and the gate must **fail on the fingerprint check**. *(It targeted `:538` until
> > round 13; `:538` is a blockquote, so the heading check killed it before the fingerprint was ever
> > consulted. **Round 14 note:** round 13 retargeted it in §7 step 2 and left this design-section copy
> > pointing at `:538` — §9's defect class, running in the opposite direction for once. The operative
> > definitions of the whole M12d/e/f/g series live in §7 step 2.)*
> > **M12e (round 9):** leave the table **entirely untouched** and instead rename or delete the
> > fingerprint `### Verdict:` at `agents/swift-reviewer.md:660`; the gate must **fail**.
> > **M12f/M12g/M12h and the positive M12i (rounds 11-13), plus the mandated resolution ALGORITHM and the
> > fence-aware section definition, are all specified in §7 step 2** — swap two anchors; point an anchor
> > at a non-heading; swap two same-fingerprint anchors; and shift a source heading with the anchor
> > updated to match, which the gate must **accept**.
> > *(Round 14, gemini: this design section stopped at M12e while four further mutants, the positive
> > case, the nearest-enclosing-heading algorithm and the fence rules had all landed in the operative
> > step — **§9's defect class running from OPERATIVE back to DESIGN**, the second time in this plan it
> > has run that direction. Full definitions stay in step 2, which is where an implementer reads; this
> > is the pointer that keeps §4.2 from contradicting it by omission.)*
> > *(M12d alone proves only that the **anchor** is load-bearing. `:538` is a blockquoted instruction
> > line, **not a heading**, so the gate's "anchor line is a heading" check rejects it before the
> > fingerprint is ever consulted — meaning the fingerprint half of this fix had no mutant at all.
> > The operative form of both mutants is in §7 step 2; the fingerprints themselves are **test-only**
> > metadata and never ship inside `AGENT_CONTRACTS.md`.)*
> - **all nine approved triples are required** — the four `in` rows and the five `out` rows — not only
>   the `in` set. Round 5: M2 is "not guaranteed" until the full triple set is mandatory, because a
>   deleted `out` row is otherwise invisible.
> - the **in** set equals exactly the four named `surface_id`s, by **canonical producer identity**;
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
> **M12** *(round 2, made concrete in round 3)* — two named mutants, not an abstraction:
> **M12a** add a row whose `surface_id` is not in the allowlist (the catch-all/paraphrase shape);
> **M12b** add a second row with an **existing `producer_id` but the opposite `scope`**;
> **M12c** *(round 4)* re-pair a valid `surface_id` with a **different valid `producer_id`** at the same
> scope — the false-Cartesian-product shape neither M12a nor M12b catches. All three must fail. M10/M11 catch only wholesale inversion and name relocation.
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

0. **Split the ticket example into ISOLATED bad cases first — round 5's finding.** The §1 example
   carries **two independent rejection causes**: the multiline `Remaining:` block *and* the trailing
   `Next:` line. `extract_status` walks up from the JSON fence over blank + detail-field lines and stops
   at either (`mcp/review-synthesizer/capture.py:399`). So a parser mutant that starts accepting a
   numbered `Remaining:` leaves the named regression **green**, because `Next:` still aborts the parse.
   Add one isolated fixture per cause, and **one M5b mutant per cause**.
1. Add the **exact ticket regression** to `TestExtractStatus`
   (`mcp/review-synthesizer/tests/test_capture.py:459` is the class heading): the §1 non-compliant
   multiline `Remaining:` block must yield `None`, and the compliant single-line form the full dict.
   **This test does not exist yet** — verified. `:512` covers the compliant single-line case and `:541`
   covers generic multiline wrap; neither is the ticket's example.
2. The relocated invariant in §5 **names that test**.
3. **M5** asserts the named test **exists, is collected, and actually exercises the ticket example** —
   round 3's finding: *collection permits a no-op*, so a renamed shim or an assertion-free body would
   satisfy "exists and is collected". Assert the reference resolves **and** that the test's own
   mutation holds:
   - **M5a** delete or rename the referenced test → the **doc-gate** fails.
   - **M5b** *(polarity corrected in round 4)* mutate the **parser** (`mcp/review-synthesizer/capture.py`)
     so it accepts the non-compliant payload → the **named test** fails.
   - **M5c** *(round 4; made exact in round 5)* delete or falsify the invariant's **prose** in §5,
     leaving the cross-reference string intact → the doc-gate must fail. **The oracle must be exact:**
     compare the **complete verbatim invariant block**, or an explicitly enumerated set of clauses.
     "Falsify the prose" left the test's own design as a semantic judgement, which is how an inert
     gate gets written.

   > **Round 4 caught M5b pointing the wrong way.** It previously said "strip the ticket example's
   > assertions from that test → the parser suite fails". Stripping assertions makes a test pass
   > **vacuously** — the suite goes green, not red. To prove the test is load-bearing you must mutate
   > the *production parser* and watch the test reject it. Both reviewers flagged this, and it is the
   > same polarity error round 3 corrected in §6's verification wording — the second instance.
   >
   > **M5c exists because round 3's pair gated only the reference, never the rule.** gemini: delete the
   > invariant's prose but keep the cross-reference and both M5a and M5b still pass, leaving the
   > document's actual rule text ungated.

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

**EIGHT are directly at risk — round 15 added `test_remaining_is_marked_safety_information`.**

*(Both arms, round 15: `scripts/tests/test_doc_gates.py:388` asserts `"never a list to shorten"` inside
`_section13()`. That phrase is the `Remaining:` safety protection, and §7 step 4 moves the precedence
clause's six protections — `Remaining:` among them — out of §13 to their owning sections. It therefore
fails on the clean narrowed document unless re-derived against §5. **Four consecutive rounds have each
added an entry to this list**, which is itself the finding: the at-risk sweep must be run as a **query
over the test file** — every assertion scoped to `_section13()` whose target text this plan relocates —
not as a reviewer-by-reviewer recollection.)*

*(gemini, round 14: `test_payload_region_invariant_is_present_on_one_physical_line`,
`test_invariant_covers_non_prose_payloads_too` and `test_precedence_clause_states_the_contract_wins` all
live in the same `COREDEV2602_AgentOutputStyle` class and assert against **§13** text. This plan
**relocates the payload-region invariant verbatim to §5** (§4.3) and **moves the precedence protections
out of §13** (§4.5's own fix) — so all three assert against text that is no longer in the section they
scope to, and **fail on the clean document**. Three consecutive rounds have now added entries to this
list: two pinned maps in round 13, these three in round 14. The sweep for "proofs pinned to a value the
narrowing changes" has to cover the **existing test suite**, not only the M-list.)*

- **`test_doc_gates.py`'s per-rule classifier map (`:328-338`)** hard-codes each rule's *current*
  disposition. §7 step 5 permits the narrowing to change any of them within the closed vocabulary, so
  this map must be **replaced by M3's membership assertion** — exactly one classifier per row — not
  merely updated to new values.
- **The adjacent per-rule marker map (`:341-356`)** pins parser-specific phrases that §4.4 permits step 5
  to remove. It must be re-derived against the narrowed §13 or deleted with its rule.

*(Round 13, codex: the round-12 revision put this correction in **step 5** and left this list unchanged,
so the list an implementer actually reads still said "two". A corrective instruction stored somewhere
else is the design/operative drift this plan keeps hitting — recorded in §9 as the dominant defect class
and committed here for the third time.)*

`test_parser_touching_rules_reference_the_invariant_by_name` asserts that
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
| `BLOCKED — …` result prefix | **NEW SECTION `## 14. Blocked Subagent Handoff Contract`** — decided in round 4; both reviewers converged. No shared owner existed — it occurs there only at `:501`, `:509`, `:513`, all inside §13. *(Round 3 correction: real contracts DO exist, in agent bodies — `agents/graph-api-debugger.md:20-25` and `agents/jira-manager.md:249-260`. "No owner exists" was wrong.)* A shared handoff contract must be created and the protection assigned to it **before** implementation — §8 Q7 |

**Round 2's finding: the relocation had no preservation proof.** Asserting only that §13 *stops*
enumerating the six would pass if a protection were relocated **and then deleted**, and M8 reverts only
§13 so it cannot see content moved elsewhere.

**M13** *(round 2)* — **one mutation-tested assertion per protection, in its destination section.**
Delete any one relocated protection from its new home; its assertion must fail. Six assertions, six
mutations.

`test_precedence_clause_names_all_six_contracts` is **replaced**, not deleted: assert the short pointer
is present, that §13 no longer enumerates the six, **and** that all six survive at their destinations.

**The `_section13()` boundary and §14's creation are ONE INDIVISIBLE change — round 6 supersedes round
5's "BEFORE" instruction, and round 7 marks it superseded here, at the operative site.** Round 5 said the
boundary "must move BEFORE §14 is added"; obeyed literally that raises `ValueError` in the window where
the edited helper looks for a `## 14.` that does not yet exist. §7 step 1 is authoritative: **one step,
not two.** The helper
extracts from `## 13. Agent Output Style` to **`## Cross-references`**
(`scripts/tests/test_doc_gates.py:293-296`, read and confirmed). Inserting §14 between them puts the
whole of §14 *inside* `_section13()`, with three consequences: a test asserting §13 no longer enumerates
`BLOCKED — …` would still find the prefix; **M13's sixth assertion would not prove the prefix is in §14**;
and section-scoped tests could false-pass against content moved into the wrong section.

**So:** end `_section13()` at `## 14.`, add a separately bounded **`_section14()`**, and point M13's
sixth assertion and its deletion mutant at `_section14()`.

**Fix.** Rewrite in place, preserving the existing helpers (`_section13`, `_rows`) — with the boundary
change above — `_rows` derives its
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
| The doc-gate goes inert (this campaign's most repeated failure — **seven** instances, M5 being the newest) | **High** | **M4–M13** (bar the positive cases M12i/M1p/M3p, which must PASS — round 14) are candidate mutants the clean gate **rejects**; **M1/M2/M3** are differential gate-adequacy comparisons (§6) — the two are not interchangeable, and this row must not restate them as one kind. M1/M9 bind to the imported tuple; **M5 is the cross-reference form** (M5a/M5b/**M5c**), because round 2 proved a document-carried fixture validates fixture-against-oracle rather than the invariant |
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

**THREE kinds of proof — two separated in round 5, the positive metamorphic cases added in round 14 — they were conflated and the instructions were not
executable.** Round 4 noted this as framing; round 5 showed §6 and §7 step 6 still instruct "every mutant
must fail", which cannot be satisfied by M1 or M3.

- **Candidate mutants** (M4–M13, **except M12i and M12j**, which are positive): each removes or corrupts
  something the contract requires, and the clean gate must **reject** it.
- **Positive metamorphic cases** (**M12i**, **M12j**, **M1p**, **M3p**): each changes the artifact or the
  roster in a way that leaves the contract **satisfied**, and the clean gate must **PASS**. They exclude
  implementations that compare stored values instead of computing. *(Round 15, codex: M1p and M3p were
  written as exceptions "to M4-M13" although they are not members of that range — they mutate
  `VALID_AGENTS` and a classifier, not the scope table.)* *(Round 7: the discriminator is **what the mutation does to the
  contract**, not which artifact it edits. The earlier wording said candidates "mutate the document or
  the parser", which misclassifies **M5a** — it deletes or renames a **test** (`:304`) and is still
  properly a candidate, because it removes a required evidence artifact **without weakening the gate**.)*
- **Gate-adequacy comparisons** (M1, **M2**, M3): these deliberately *weaken the gate* and show it stops
  catching something. They are run as a **differential** — e.g. M1 runs the same `VALID_AGENTS` mutation
  against **both** the live-import gate and a hardcoded weak gate, and asserts the live gate fails while
  the weak gate passes. Stating them as "mutants that must fail" is a category error.

  **Round 6 moved M2 into this group.** M2 mutates the **test**, not the document or the parser, and is
  structurally identical to M1 and M3. Under a weakened assertion the mutated document does **not** fail,
  which is the whole point: it is a differential showing the weak form is inert, not a mutant the clean
  gate rejects. Listing it as a candidate mutant made §6 and §7 step 7 unsatisfiable for M2 for exactly
  the reason round 5 identified for M1/M3.

  **M2's operative definition is the one in §4.1's proof list — cited BY NAME, not by line: see the
  `- **M2**` bullet under §4.1's "Proof" heading. Reproduced here because §7 step 7 routes the
  implementer through this section** — weak predicate **`the parsed table has exactly nine rows`**,
  mutation **re-pair one row's `producer_id` with another allowlisted `producer_id`**. M3's marker and
  mutation are likewise fixed in §4.1's `- **M3**` bullet.
  *(Round 14, from gemini: these pointers read `:154` and `:161`, which by then resolved to M2's preamble
  and **M1's** definition — the implementer this paragraph exists to route was being sent to unrelated
  text. Every round shifts these lines, so **intra-document references are now by section and identifier
  name, never by line number.** The mechanical citation checker validates `path:line` citations into the
  repo; it cannot see a plan-internal `:NNN` drift, which is why this survived six rounds.)*
  *(Round 8: this paragraph still defined M2 as the round-5 "the section contains the word *excluded*"
  check — the very predicate round 7 superseded at `:154` for never passing on the clean document.
  Because step 7 sends implementation here, **the superseded predicate is the one that would have
  shipped**. That is the third time in this plan a decision was fixed in a design section and left
  standing in the operative one — two-column→three-column in round 6, the `anchor` column in round 8, and
  this. The class is recorded in §9; the standing instruction is to grep every operative restatement
  before declaring a design change propagated.)*

**Polarity, corrected in round 2, amended in round 14:** the clean post-fix implementation must **PASS**,
and then **each candidate mutant must FAIL — with the sole exception of the POSITIVE metamorphic cases,
which must PASS.** Those are **M12i** (shift a source heading and update the anchor to match), **M1p**
and **M3p** (below). *(codex, round 14: M12i was added to §7 step 2 requiring a **pass**, while the risk
register, this taxonomy, this polarity rule and step 7 all still said every M4-M13 mutant must fail.
Following the operative steps literally would require M12i to fail — which is exactly the equality gate
it exists to exclude. A positive case is a third proof kind and had no home in the taxonomy.)*

**Three kinds of proof, then:** *candidate mutants* (must fail), *gate-adequacy differentials* (M1/M2/M3
— weak side passes, strong side fails), and **positive metamorphic cases** (must PASS — they prove the
gate computes rather than compares). Round 1's wording ("each must be shown failing before
the fix and passing after") describes a regression test, not a mutation proof, and would have been
satisfied by a suite that never rejects a mutant.

## 7. Implementation order

1. **Split the §13/§14 boundary and create §14 as ONE indivisible change.** Change `_section13()` to end
   at `## 14.`, add a bounded `_section14()` (`## 14.` → `## Cross-references`), **and** create
   `## 14. Blocked Subagent Handoff Contract` in the same step. Round 5 established that the helper must
   not lag §14's insertion (§4.5, `:399`) — otherwise §14 sits inside `_section13()` and M13's sixth
   assertion proves nothing. **The converse is equally fatal:** ending `_section13()` at `## 14.` while
   §14 does not yet exist makes `text.index("## 14.", start)` raise `ValueError`, which is a suite
   *error*, not a controlled result. Neither sequencing is safe, so this is **one step, not two** —
   round 6 replaces "move the helper split ahead of §14" with atomicity.
2. Rewrite §13's Scope as a **parseable FOUR-column table** — `surface_id | producer_id | scope |
   anchor` — whose **triples** are exactly the nine approved ones. **The finite allowlist and the
   exact-set equality gate apply to `surface_id`, `producer_id` and `scope` ONLY — never to `anchor`.**
   Any unknown key is a hard failure and any `(surface_id, producer_id, scope)` triple outside the
   approved set is a hard failure. The **`anchor`** column is constrained solely by its **syntax**
   (`path:line`) and by the per-row **resolution** rules below — never by equality, never by an
   allowlist. *(Round 15, codex: this step said "content is exactly these nine rows" and "every field
   drawn from a finite allowlist", which read across the anchor column and **re-created the round-11
   wrong gate** — full-row equality rejects M12d/f/g and a fixed-locus fingerprint search rejects M12e,
   so the resolution logic is never exercised. Those words contradicted the note four lines below them.)*

   > **What is equality-checked, and what is not — round 14, and the M12 series depends on it.**
   > The gate asserts **exact set equality on the nine `(surface_id, producer_id, scope)` TRIPLES**, as
   > §4.2 has said since round 4. The **`anchor` column is NOT equality-checked**: it is validated by
   > *resolution* — checks (i) path exists, (ii) the line is a heading, (iii) that heading's section
   > contains the surface's recorded fingerprint. *(codex, round 14: if anchors were equality-checked
   > too, a wrong gate could assert `rows == EXPECTED_ROWS` and then look for each fingerprint at a
   > **hard-coded** locus. Every anchor mutant would die on row equality, every fingerprint mutant on the
   > hard-coded search, the clean document would pass — and check (iii) would never once read the table.
   > Equality on the anchor column makes the whole anchor mechanism untestable.)*

   **THE LITERAL §13 TABLE — exactly four columns, exactly these nine rows. Copy this, nothing else:**

   | `surface_id` | `producer_id` | `scope` | `anchor` |
   |---|---|---|---|
   | `verdict-report` | `swift-reviewer` | `in` | `agents/swift-reviewer.md:590` |
   | `brainstorm-summary` | `brainstorm` | `in` | `skills/brainstorm/SKILL.md:143` |
   | `implement-wrapup` | `implement` | `in` | `skills/implement/SKILL.md:342` |
   | `pr-review-report` | `pr-review` | `in` | `skills/pr-review/SKILL.md:133` |
   | `security-findings` | `security-reviewer` | `out` | `agents/security-reviewer.md:203` |
   | `concurrency-findings` | `concurrency-reviewer` | `out` | `agents/concurrency-reviewer.md:264` |
   | `ux-perf-findings` | `ux-perf-reviewer` | `out` | `agents/ux-perf-reviewer.md:199` |
   | `accessibility-findings` | `accessibility-auditor` | `out` | `agents/accessibility-auditor.md:210` |
   | `prompt-safety-findings` | `prompt-review` | `out` | `agents/prompt-review.md:96` |

   **TEST-ONLY metadata — the expected fingerprints. These live in the GATE, never in `AGENT_CONTRACTS.md`.**
   **Every fingerprint must be UNIQUE to its surface — round 15.** *(codex: four of the five `out` rows
   carried the generic `## Output Format`, so **swapping `security-findings` and `concurrency-findings`
   preserves every triple, leaves both anchors valid headings, and leaves both sections containing that
   same fingerprint — the gate accepts the wrong binding.** A fingerprint shared by four surfaces cannot
   discriminate between them, which is the column's entire job. The unique headings below were opened and
   verified at the frozen commit.)*

   | `surface_id` | fingerprint the anchored section must contain |
   |---|---|
   | `verdict-report` | `### Verdict:` |
   | `brainstorm-summary` | `## Step 8: Summary for Approval` |
   | `implement-wrapup` | `## Phase 6: Wrap Up` |
   | `pr-review-report` | `## Step 4: Compile the Final Report` |
   | `security-findings` | `## Security Review` *(`agents/security-reviewer.md:206`)* |
   | `concurrency-findings` | `## Correctness & Concurrency Review` *(`agents/concurrency-reviewer.md:267`)* |
   | `ux-perf-findings` | `## Performance & UX Review` *(`agents/ux-perf-reviewer.md:202`)* |
   | `accessibility-findings` | `## Accessibility Audit` *(`agents/accessibility-auditor.md:213`)* |
   | `prompt-safety-findings` | `## Structured Findings (orchestrator handoff)` |

   > **Round 9 split these two tables, and the split is the fix.** Round 8 mandated "a **FOUR**-column
   > table" and then shipped a **five**-column one — the fingerprint column — labelled as "content is
   > exactly these rows". An implementer copying it verbatim produces a five-column §13 that the
   > four-column `_scope_rows` parser must reject, so the step contradicted itself in the same breath.
   > Both reviewers caught it. The fingerprints were never meant to ship in the contract: they are the
   > gate's expected values. **Two tables, two homes, and the shipped one is unambiguous.**

   > **Round 8 — the `anchor` column had not reached this step, so M12d was unimplementable.** §4.2's
   > round-7 fix added the fourth column and defined **M12d** to mutate it, but this step still mandated a
   > "three-column table" and shipped a nine-row three-column body. An implementer following §7 literally
   > would never create the anchor column, and M12d would have nothing to mutate — while §4.2 claimed the
   > redirect was closed. Both reviewers found this independently and both named the same two sites.
   >
   > **The anchors above are the "exact nine" codex asked for, opened and verified at `b2496a8`** — not a
   > formula for deriving them. Two of them are the point of the whole column:
   > - `verdict-report`'s anchor is **`agents/swift-reviewer.md:590`** (`## Output Format`), **not the
   >   `:439` Step-5 heading** §4.2 cites as the surface's locus. `:439` opens a section that contains
   >   *both* the synthesizer **tool input** (`:538`) and the client-facing **report format** (`:590`), so
   >   an anchor at `:439` would still admit codex's counterexample — define `verdict-report` as the JSON
   >   object passed to the tool and every check passes. Anchoring at `:590`, with the fingerprint
   >   `### Verdict:` (`:660`, inside that section and absent from the tool-input region), makes the
   >   redirect fail the gate. **A broad anchor is not an anchor.**
   > - `prompt-safety-findings` anchors at `## Structured Findings (orchestrator handoff)`, not an
   >   `## Output Format` heading, because `prompt-review` has none — evidence that these are read off the
   >   repository rather than pattern-filled.
   >
   > **SECTION BOUNDARIES ARE FENCE-AWARE — round 13, and the clean document fails without this.**
   > *(codex: **all five fingerprints live inside fenced code blocks** — they are pseudo-headings in output
   > templates, not Markdown headings. Verified at the frozen commit: `## Security Review`
   > (`agents/security-reviewer.md:206`), `## Correctness & Concurrency Review` (`:267`),
   > `## Performance & UX Review` (`:202`), `## Accessibility Audit` (`:213`) and `### Verdict:`
   > (`agents/swift-reviewer.md:660`) each sit after an odd number of ``` markers. A heading scanner that
   > is not fence-aware treats the first fenced `##` line as the next heading, **terminates the anchor's
   > section before its fingerprint, and rejects the clean document.** The round-12 fix picked unique
   > fingerprints without checking they were reachable.)*
   >
   > So the gate defines a section as: from the anchor line, to the next line that is a heading
   > **at the same or shallower depth AND outside any fence**.
   >
   > **Fence detection is CommonMark, not substring — round 14.** A fence delimiter is a **line** whose
   > first non-whitespace run is **three or more** backticks or tildes; an opener may carry an info
   > string, a closer may not, and a closer must be at least as long as its opener. **Inline triple
   > backticks inside prose are NOT delimiters.** Completing the rules — round 15, codex: the delimiter
   > may be indented **at most three spaces** (four or more makes it an indented code line, not a fence),
   > and a **closer must use the same delimiter character as its opener** (a `~~~` cannot close a
   > ```` ``` ````). *(The round-14 wording said "first non-whitespace run", which accepts a
   > four-space-indented line as a fence and is silent on mismatched characters. Either error
   > misclassifies the fence state and the clean document is rejected.)* An implementation may instead
   > delegate to a CommonMark parser, which is the safer choice. *(codex: `agents/swift-reviewer.md` contains
   > `` ```json `` and `` ```jsonc `` inline in sentences at `:304`, `:453` and `:455`, well before the
   > real fence at `:599`-`:665`. A "track ``` toggles" implementation reading substrings computes the
   > **inverted** fence state and rejects the clean document — the same class of defect as the round-13
   > fingerprints, one layer down.)* **The anchor itself must also be outside a fence**, not only the
   > boundary headings. The **fingerprint search covers the whole section body, fenced content included**; only
   > *boundary detection* ignores fenced `#` lines. **All nine anchors are real headings outside fences**
   > (verified), so check (ii) is unaffected.
   >
   > **THE GATE'S ALGORITHM IS MANDATED, NOT INFERRED FROM ITS MUTANTS — round 14.**
   > *(codex built a **shift-aware equality gate** that survives everything: hard-code expected anchor `E`,
   > heading text `H` and fingerprint line `F` per row; set `delta = 1` when line `E` went blank and
   > `E+1 == H`; then require `anchor == E+delta` and look for the fingerprint at `F+delta`. That accepts
   > the clean document **and every M12i parameterisation**, while rejecting M12d/f/g/h on the anchor
   > comparison and M12e at the fixed locus — never once resolving a section. **A finite mutant set cannot
   > exclude every wrong gate**; a sufficiently tailored one defeats any fixed list. So the plan specifies
   > what the gate must **do**, and the mutants test that algorithm rather than trying to enumerate its
   > complement.)*
   >
   > **Required algorithm, per row, in order:**
   > 1. Parse the four-column table; take `anchor` as `path:line`.
   > 2. Open `path`. Assert `line` is a **real heading** — an ATX heading **outside any fence**.
   > 3. Locate the row's **fingerprint** by **searching the current file's content** — scan the file as it
   >    is now, from the top, for the fingerprint string. **No stored fingerprint line, no line number
   >    derived from one, no offset carried from a previous run.** Assert the fingerprint occurs
   >    **exactly once** outside the boundary-detection sense; more than one occurrence is a hard failure
   >    rather than a "take the first" choice.
   >    *(Round 15, BOTH arms. codex: a gate could store each fingerprint's original line `F`, reuse the
   >    same `+1` delta M12i teaches it, inspect only `F+delta`, and then genuinely perform steps 2, 4 and
   >    5 from there — passing the clean document and **every** M12d-M12i parameterisation, while failing
   >    the moment a harmless blank line is inserted **between** an anchor and its fingerprint. gemini
   >    reached the same place from multiplicity: `find()` vs `rfind()` is unspecified, so a duplicate
   >    fingerprint would silently resolve the wrong instance and walk up to an unrelated heading.
   >    "Locate" was doing far too much work as a single word.)*
   > 4. **Assert the anchor line IS the nearest enclosing real heading of that fingerprint** — walk up
   >    from the fingerprint to the first real heading at any depth; it must be exactly `line`.
   > 5. Assert the fingerprint lies within the section that heading opens (fence-aware, below).
   >
   > **Step 4 is the load-bearing one, and it is new in round 14.** *(codex: the round-13 predicate —
   > exists, is-a-heading, section-contains-fingerprint — **accepts an anchor far too broad to identify
   > the surface**. Repointing `brainstorm-summary` from `skills/brainstorm/SKILL.md:143` to that file's
   > **sole H1 at `:10`** passes all three checks: the path exists, `:10` is a real heading, and its
   > section runs to EOF (no later H1) and therefore contains the fingerprint at `:143`. Verified: the
   > file has exactly one H1 and 201 lines. The plan's own words — "**a broad anchor is not an anchor**" —
   > were contradicted by its formal rules. Nearest-enclosing makes the binding exact, and it also raises
   > the floor for a wrong gate: step 4 requires **finding** the fingerprint and **walking up**, which no
   > fixed-locus or shift-tolerant comparison performs.)*
   >
   > **And stated plainly, because three rounds of wrong gates earned it:** mutation testing **bounds**
   > gate correctness, it does not prove it. The mandated algorithm is the specification; the mutants are
   > evidence that an implementation of it discriminates. Neither alone is sufficient, and the plan no
   > longer implies the mutant list is exhaustive.
   >
   > **The gate asserts, per row:** (i) the anchor path exists; (ii) the anchor line is a **heading**;
   > and (iii) the section that heading opens **contains the recorded fingerprint**. A prose definition
   > elsewhere is then not authoritative and cannot redirect the ID.
   >
   > **Two mutants, because one cannot prove both checks — round 9.**
   > - **M12d** leaves all nine triples byte-identical and repoints one anchor to
   >   **`agents/swift-reviewer.md:439`** — `### Step 5: Synthesize Unified Review`, a **real heading**
   >   whose section (`:439`-`:589`) contains **no** `### Verdict:` (verified at the frozen commit). It
   >   therefore passes checks (i) and (ii) and must fail on **(iii)**, proving the fingerprint check
   >   **reads the anchor from the table**.
   >   *(Round 13, from gemini: M12d previously targeted `:538`, a blockquote. Check (ii) rejects a
   >   non-heading before (iii) is consulted — so a gate that read the table for (ii) but **hard-coded
   >   `:590`** for (iii) would pass M12d *and* M12e, leaving the fingerprint's coupling to the table
   >   untested. Round 9 moved this mutant off `:538` for the anchor's sake and left the same line in
   >   place for the fingerprint's. `:439` is the round-7 counterexample locus, which makes it the most
   >   meaningful target available.)*
   > - **M12e** leaves the table **entirely untouched** — anchor still `:590` — and instead changes the
   >   artifact: rename or delete `### Verdict:` at `agents/swift-reviewer.md:660`. The gate must fail on
   >   check (iii). This proves the fingerprint is **consulted at all**.
   > - **M12f** *(round 14)* **SWAPS two rows' anchors** — `verdict-report` ↔ `security-findings`, so
   >   `verdict-report` points at `agents/security-reviewer.md:203` and vice versa. Both remain valid
   >   headings, so checks (i) and (ii) pass; `verdict-report`'s fingerprint `### Verdict:` is absent from
   >   security-reviewer's Output Format section, so the gate must fail on **(iii)**. A gate that
   >   hard-codes each surface's locus does **not** notice a swap, so this is the mutant that proves
   >   check (iii) **reads the anchor from the table**.
   > - **M12g** *(round 14)* points one anchor at a **non-heading** line — `agents/swift-reviewer.md:591`,
   >   blank, immediately under `## Output Format`, whose *enclosing* section still contains the
   >   fingerprint. Check (iii) would therefore pass; the gate must fail on **(ii)**. This is the only
   >   mutant that proves check (ii) reads the anchor from the table rather than asserting
   >   `is_heading(590)` unconditionally.
   >
   > - **M12h** *(round 15)* the **same-generic-fingerprint swap**: swap the `security-findings` and
   >   `concurrency-findings` anchors. Under round 14's shared `## Output Format` fingerprint this
   >   **passed**; under the unique fingerprints above it must **fail**. This is what proves the
   >   fingerprints discriminate *surfaces* rather than merely existing.
   >
   > - **M12j — the POSITIVE BODY-SHIFT case, round 15.** Insert a blank line **between** an anchor and its
   >   fingerprint, changing **neither** the table nor the heading. The binding is still correct, so the
   >   gate must **PASS**. A gate that stores or derives the fingerprint's line number fails this; only a
   >   content-driven search of the current file passes it. *(This is the case that excludes codex's
   >   stored-`F`-plus-delta gate, which M12i alone could not.)*
   > - **M12i — the POSITIVE metamorphic case, round 13. This is the one that excludes an equality gate.**
   >   Insert a blank line immediately **before** a source heading (say `agents/security-reviewer.md:203`),
   >   then **increment that row's anchor** to match (`:203` → `:204`). The document and the artifact now
   >   agree, so **the gate must still PASS**. A gate asserting `anchor == EXPECTED_ANCHOR[surface_id]`
   >   **fails** this, because the anchor moved; a genuinely resolution-checked gate passes.
   >   *(codex, round 13: M12d/f/g/h are all **rejection-only**, so a wrong gate can assert anchor equality
   >   and then search fingerprints at fixed loci — every rejection mutant dies at the equality check and
   >   M12e dies at the fixed search, on all nine rows. Parameterising rejection mutants across nine rows
   >   expands coverage but **cannot** distinguish equality from resolution: only a mutation the gate must
   >   **accept** can. Three rounds of adding rejection mutants could not have closed this.)*
   >
   > **EVERY anchor mutant above is run against ALL NINE rows, not only `verdict-report` — round 15.**
   > *(codex: a gate that validates just that one row — `assert parsed_triples == EXPECTED_TRIPLES`, then
   > resolve `verdict-report` — passes the clean document **and all four** of M12d/e/f/g, because every
   > one of them targets `verdict-report`; the other eight anchors are never inspected. Pinning "the gate
   > reads the table" for one row does not pin the **per-row iteration** step 2 requires. Each mutant is
   > therefore parameterised across the nine rows, and every parameterisation must fail.)*
   >
   > *(Round 14: gemini and codex each constructed a **wrong gate that passes every earlier mutant**.
   > gemini's hard-codes check (ii) and does (iii) properly — both M12d and M12e die on (iii), so the
   > hard-coding is never exposed. codex's asserts `rows == EXPECTED_ROWS` then searches each fingerprint
   > at a fixed locus — M12d dies on row equality, M12e on the fixed search. **Two mutants cannot pin
   > three checks**, and equality on the anchor column masked the difference. M12f and M12g close it, and
   > the anchor is now resolution-checked rather than equality-checked.)*
   >
   > *(Round 9, from codex: M12d alone proves nothing about the fingerprint. `agents/swift-reviewer.md:538`
   > is `> Call \`mcp__…synthesize_review\` with` — a **blockquoted instruction line, not a heading** — so
   > check (ii) rejects it even if fingerprint validation were absent entirely. The mutant that was
   > supposed to justify adding the fingerprint column is killed by a different check before the
   > fingerprint is ever consulted. **A gate whose mutant is caught by an unrelated assertion is
   > untested** — the same shape as 2617's N5a this round, and as I18's inverted oracle in round 10.)*

   The five `out` rows' **reason** (they emit structured JSON; style guidance was always a poor fit) and
   the note on what is deliberately lost are prose **outside** the table — prose is not row content.
   The four `in` `producer_id`s are disjoint from `capture.VALID_AGENTS`, which is exactly the five
   `out` `producer_id`s. §4.4's determination is already settled in this plan; do **not** re-open it,
   and do not edit the plan during implementation (that invalidates the reviewed digest).
3. **Move** the payload-region invariant verbatim to `## 5. Code Review Pipeline`
   (`AGENT_CONTRACTS.md:247`), **naming the `test_capture.py` regression that owns its evidence** — no
   fixture block in the contract; round 2 rejected that design. §13 keeps no copy.
4. Move the precedence clause's six protections to their owning sections; §13 keeps a one-sentence
   pointer. §14 — the destination for `BLOCKED — …` — already exists from step 1.
5. Simplify the carve-outs §4.4 proved out-of-scope; all ten dispositions stay explicit, and rules 4/9
   keep protecting the consolidated issue table on contract grounds.
   **Each of the ten dispositions must retain EXACTLY ONE classifier from the closed vocabulary
   `{**Adapted**, **Adopted**, **Restated positively**}`** — exactly one, not at least one: a second
   token anywhere in the cell breaks M3's clean-document baseline. This is a gated property, not a
   formatting habit. **§4.5 now names both maps directly — round 13.** *(codex: the round-12 revision left the
   correction as an instruction **here**, in step 5, while §4.5 itself still listed only
   `test_parser_touching_rules_reference_the_invariant_by_name` and
   `test_precedence_clause_names_all_six_contracts` as directly at risk. Leaving a corrective instruction
   in the operative step, and not fixing the list an implementer actually reads, **is the exact
   design/operative drift this revision claims to close.** §4.5 carries both entries now; this sentence is
   the cross-reference, not the fix.)*
   **Also replace `test_doc_gates.py`'s hard-coded per-rule classifier map
   (`:328-338`)** with the membership assertion, **and the adjacent per-rule marker map (`:341`)**, whose
   phrases are the parser-specific wording §4.4 permits this step to remove. **§4.5 must name both tests
   explicitly** — it currently claims only two tests are directly at risk and neither of these is among
   them. *(Round 15, codex: relying on step 6's generic "rewrite the 11 tests" is exactly how a pinned
   test survives a narrowing; §4.5 is the list an implementer actually checks.)* *(Round 9: step 5 previously said only that the
   dispositions "stay explicit", which permits rewriting their prose freely — and M3's round-8 marker was
   a prose phrase inside four of those very cells. Pinning the vocabulary is what makes a row-scoped
   marker durable across the simplification this step orders.)*
6. Rewrite the 11 tests; add the disjointness gate, the `_scope_rows` schema gate, and the
   **cross-reference** M5 gate. Add to `test_capture.py` **the isolated regressions §4 requires — one
   fixture per independent rejection cause, plus both M5b parser mutants — not only the combined "exact
   ticket" case.** *(Round 14, codex: `extract_status` stops on **either** kind of intervening content
   (`mcp/review-synthesizer/capture.py:399-403`), so a single combined fixture passes while masking a
   parser that handles only one cause — the documented false-pass §4 exists to prevent. Ordering only the
   combined case here re-creates it, since step 6 is what an implementer follows.)*
7. Run **M4–M13** as candidate mutants (clean gate rejects each) **except the positive metamorphic cases
   M12i, M1p and M3p, which the clean gate must ACCEPT**; and **M1/M2/M3** as differential gate-adequacy
   comparisons — see §6's **three**-kinds note. *(Round 14: this step said "M4-M13 … rejects each",
   which contradicted M12i's required pass.)*
8. Version bump + CHANGELOG. State that this is a **scope narrowing, not a relaxation** — the
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

7. ~~Where does `BLOCKED — …` get its shared contract?~~ **ANSWERED in round 4 — a NEW section.** Both
   reviewers converged on the same destination and the same reasoning: §2 is specifically the
   Plan → Implement contract (`AGENT_CONTRACTS.md:71-175`), while the real uses cover diagnostic
   confirmation (`agents/graph-api-debugger.md:20-25`) and Jira-tool failure
   (`agents/jira-manager.md:249-260`) — a subagent pausing to hand control back for external action.
   Leaving it in §13 would forfeit the whole point of the ticket.

   **Create `## 14. Blocked Subagent Handoff Contract`**, after §13 and before Cross-references, owning:
   the exact leading prefix `BLOCKED — <reason>`; diagnosis, attempted work, required user action and
   remaining work; and the invoking session's obligation to surface the result and gate affected work.
   M13's sixth assertion and its deletion mutant target §14.

## 9. Notes

- Every claim here was executed or read from the file at HEAD `adda52d`. *(Round 4 correction: the
  intervening commits did **not** touch "only CHANGELOG/README/plugin.json" — the range also contains
  four planning-document changes. The conclusion still holds: **none of the cited source files
  changed**.)* Doing so corrected **four of
  the ticket's own figures**: `swift-reviewer` Step 5 at **`:439`** not `~:140`; `implement` Phase 6 at
  **`:342`** not `~:333`; **11** §13 tests not 14; **9** skills referencing the contracts not 8. The
  ticket's *reasoning* held up in every case — only its numbers drifted.
- The `~:140` error is instructive: `grep -n 'Step 5' agents/swift-reviewer.md` returns `:140` first,
  and `:140` is a passing mention inside a different step. Taking the first `grep` hit as the heading is
  the single most repeated citation error in this campaign.
- `capture.py`'s `VALID_AGENTS` contains **`prompt-review`**, not `swift-reviewer` — so "the five
  reviewers" is security/concurrency/ux-perf/accessibility/**prompt-review**. Any prose naming the five
  must use that list, not the four specialists plus the orchestrator.

> **The dominant defect class in this plan: a decision fixed in the DESIGN section and left standing in
> the OPERATIVE one.** Three instances, each caught a round or more after the "fix":
>
> | round | decided in §4 | still wrong in | consequence had it shipped |
> |---|---|---|---|
> | 6 | scope table becomes **three**-column (`surface_id \| producer_id \| scope`) | §7 step 1's two-column instruction | M12c has no `producer_id` to mutate |
> | 8 | scope table gains a fourth **`anchor`** column + M12d | §7 step 2's three-column table and nine-row body | **M12d unimplementable** — the column it mutates never exists |
> | 8 | M2's weak predicate becomes "exactly nine rows" | §6's `excluded` definition, which step 7 routes through | the **superseded** predicate is the one that ships |
>
> Each was found by an adversarial reviewer, not by the edit that made the decision. The pattern is
> structural, not careless: §4 is where the argument is won, §6/§7 are where an implementer actually
> reads, and editing the first feels like finishing.
>
> **Standing counter-measure — after changing any design decision, grep for every operative restatement
> of it before declaring it propagated.** For a table-shaped decision that means every occurrence of the
> column count, every shipped instance of the table, and every step that tells an implementer to build
> it. The check is mechanical and cheap; three rounds were spent not doing it.

> **Transcript-path notice (2026-07-30).** Every `/tmp/rev/…` path cited in the round histories below
> **no longer exists**: the machine's root volume filled, and macOS purged `/private/tmp`, destroying all
> 105 captured transcripts of this campaign in one event. The byte counts and hit counts recorded here
> were taken from those transcripts while they existed and are left as the historical record — but they
> are **no longer independently reopenable**, and a reviewer should treat them as claims, not evidence.
> Codex's own rollout logs under `~/.codex/sessions/` survived and were used to recover the affected
> round's findings. Captures from this round forward go to `~/.claude/review-transcripts/`.

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

## 12. Round-3 gate outcome

**gemini `REQUEST_CHANGES` (3) · codex `REQUEST_CHANGES` (4).** Frozen at `1485c54d…`, sha256
`1e4cbe36…`; both re-verified the digest. Transcripts: `/tmp/rev/2605r3-agy.txt` (2,898 B, `TREE=clean`)
and `/tmp/rev/2605r3-codex.txt` (277,093 B — **67** ticket-key occurrences; §12 first said 51, corrected in round 4).

| # | finding | verified | fix |
|---|---|---|---|
| 1 | **M12 had no implementable schema** — a free-text table cannot reject semantic paraphrase | **confirmed** — codex's row `\| every report emitted by the review orchestrator… \| out \|` passes while leaving the `in` set and disjointness untouched | a **closed lexical schema** (`surface_id \| producer_id \| scope`, finite allowlists, unknown key = hard failure) and concrete **M12a/M12b** mutants |
| 2 | **M5's "exists and is collected" permits a no-op** — a shim or assertion-free body satisfies it | **confirmed** | split into **M5a** (delete/rename the referenced test → doc-gate fails) and **M5b** (strip the ticket example's assertions → parser suite fails) |
| 3 | **`BLOCKED — …` is not ownerless** — real contracts live in `agents/graph-api-debugger.md:20-25` and `agents/jira-manager.md:249-260`; what is missing is a **shared** owner in `AGENT_CONTRACTS.md` | **confirmed** — my round-2 framing was wrong | reframed; §8 Q7 now asks for the shared contract, and M13 cannot complete without it |
| 4 | **the rejected fixture design was still operative** — the risk register and §7 steps 2/5 still mandated a document fixture block, and the risk row still said M1–M11 with the superseded polarity | **confirmed** | all propagated; these were instructions, not history |

codex's M1–M13 audit found M1–M4, M6–M11 sound, M12 not executable until the schema was defined, M13
structurally sound but blocked on the `BLOCKED — …` destination. It also confirmed that deleting
`out ⊇ VALID_AGENTS` **loses no protection**: the exact `in` identities include `swift-reviewer`, so
adding it to the tuple makes the intersection non-empty and M9 fails without any containment assertion.

## 13. Round-4 gate outcome

**gemini `REQUEST_CHANGES` (5) · codex `REQUEST_CHANGES` (4).** Frozen at `51642a49…`, sha256
`325dc5ed…`. Transcripts: `/tmp/rev/2605r4-agy.txt` (3,860 B, `TREE=clean`) and
`/tmp/rev/2605r4-codex.txt` (305,541 B).

> **gemini's first attempt at this round FAILED and was re-run.** It returned 262 bytes —
> `Error: timeout waiting for response` — after starting a background mutation harness and blowing
> `agy`'s 18-minute print timeout. It also wrote `scripts/tests/update.py` and `test_m9.py`, **into the
> disposable checkout**, so `TREE=clean` held: `isolated-agy-review.sh` did exactly what COREDEV-2607
> built it for. The prompt was amended with an explicit execution budget (read, do not implement, no
> background jobs) and the re-run succeeded. A 262-byte transcript is a failed run, not a verdict.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **the "closed" schema was not closed** — independent column allowlists permit false Cartesian products. gemini: `\| brainstorm-summary \| implement \| in \|` passes everything while asserting the wrong producer | **confirmed** | the schema validates an exact set of approved **triples**; **M12c** added for the re-pairing shape |
| 2 | **both** | **M5b's polarity was backwards** — "strip the test's assertions → the parser suite fails" is wrong; stripping assertions makes it pass **vacuously** | **confirmed** | M5b now mutates the **production parser** and expects the named test to fail. Second instance of this polarity error in two rounds |
| 3 | gemini | **M5a/M5b never gate the invariant's prose** — delete the rule text, keep the cross-reference, both pass | **confirmed** | **M5c** added |
| 4 | **both** | `BLOCKED — …` needs a **new shared section**, not §2 and not §13 | **confirmed**, with identical reasoning from each | **`## 14. Blocked Subagent Handoff Contract`**, scope specified; M13's sixth assertion targets it |
| 5 | codex | §12 recorded **51** ticket-key occurrences; the transcript has **67** | **confirmed** | corrected |
| 6 | codex | §9's "intervening commits touched only CHANGELOG/README/plugin.json" is **false** — four planning-doc changes | **confirmed** | corrected; the conclusion (no cited source file changed) holds |
| 7 | gemini | M1/M2/M3 are framed as candidate mutants but mutate the **test suite** | noted — a framing issue, not a defect in the proofs themselves | recorded; §6's polarity wording already says the clean candidate must reject each mutant |

## 14. Round-5 gate outcome

**gemini `REQUEST_CHANGES` · codex `REQUEST_CHANGES`.** Frozen at `9548299a…`, sha256 `d9723cb8…`.
*(Round 6 correction: this line recorded `325dc5ed…`, which is the digest of the **round-4** freeze
`51642a49` — the previous round's value copied forward. Same defect as `COREDEV-2617` §13; see §15.)*
Transcripts: `/tmp/rev/2605r5-agy.txt` (2,865 B, `TREE=clean`) and `/tmp/rev/2605r5-codex.txt`
(208,894 B, 89 ticket-key hits).

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **Adding §14 breaks `_section13()`** — it extracts to `## Cross-references`, so §14 would sit inside it; M13's sixth assertion would not prove the prefix is in §14 | **confirmed** — `test_doc_gates.py:293-296` read | `_section13()` ends at `## 14.`; a bounded `_section14()` is added and M13's sixth assertion targets it |
| 2 | codex | **M5's ticket example has two independent rejection causes** — multiline `Remaining:` *and* a trailing `Next:` — so a parser mutant accepting one leaves the test green on the other | **confirmed** — `capture.py:399` walks up over blank + detail lines and stops at either | isolated fixtures per cause, one M5b mutant per cause |
| 3 | codex | **M5c's oracle was a semantic judgement** — "falsify the prose" | **confirmed** | compare the **verbatim** invariant block or an enumerated clause set |
| 4 | codex | **M1/M3 are gate-adequacy comparisons, not candidate mutants**, yet §6 and §7 say "every mutant must fail" | **confirmed** | §6 now separates the two kinds; §7 step 6 runs them differently |
| 5 | codex | **M2 is not guaranteed until all nine triples are required** — a deleted `out` row is otherwise invisible | **confirmed** | the schema mandates the full nine-triple set |

§14's semantic scope was judged **correct and sufficient**; the defect was purely the extraction
boundary. M6–M11 are closed, M3–M4 closed, and every cited repository location verified.

## 15. Round-6 gate outcome

**gemini `REQUEST_CHANGES` (3 High, 1 Medium) · codex `REQUEST_CHANGES` (1 High, 4 Medium).**
Frozen at `093df689…`, sha256 `d4672051…`. *(Round 7: the commit was mistyped `093df68f…`, which
resolves to nothing — `git rev-parse --verify` returns "Needed a single revision". The digest was
correct.)* Transcripts:
`~/.claude/review-transcripts/2605r6-agy.txt` (3,021 B) and `…/2605r6-codex.txt`
(212,342 B, 71 ticket-key hits). Both transcripts are complete and reached an explicit verdict line;
neither round-6 arm needs re-running.

**Transcripts moved off `/tmp`.** Rounds 1–5 cite `/tmp/rev/…`, which macOS purged under disk
pressure — those transcripts are gone and their sizes here are the only surviving record. Round 6
onward captures to `~/.claude/review-transcripts/`.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **the two-column instruction still contradicts the three-column triple schema** — `:181`'s sketch and §7 step 1 both said `surface → in/out` | **confirmed** — both reviewers cite the *same two sites* independently; a nine-row two-column table can pass while producer identity is misstated, and M12c cannot observe the association without `producer_id` | §7 step 1 (now step 2) carries the **exact nine `(surface_id, producer_id, scope)` triples**; `:181`'s sketch is marked superseded rather than deleted, since it is round-3 history |
| 2 | gemini | **M2 is a gate-adequacy comparison, not a candidate mutant** — `:144` weakens the assertion to "contains the word *excluded*" | **confirmed** — M2 mutates the **test**, not the document or parser, and is structurally identical to M1/M3; as a "mutant that must fail" it is unsatisfiable | moved into the M1/**M2**/M3 differential group in §6; §7's mutation step now reads M4–M13 vs M1/M2/M3 |
| 3 | codex | the risk register restates **every proof M1–M13** as a mutant the clean candidate rejects, contradicting §6's own taxonomy | **confirmed** | row rewritten to name both kinds and to forbid restating them as one |
| 4 | codex | the same row names only **M5a/M5b**, dropping **M5c** — reopening round 4's prose-gating gap | **confirmed** | **M5c** restored to the row |
| 5 | codex | **§7's order contradicts its own prerequisite** — §14 is created at step 3 but the helper split is at step 5, while `:399` requires the split first | **confirmed** | **resolved by atomicity, not by reordering** — see below |
| 6 | codex | the round-5 record's digest `325dc5ed…` is the **round-4** value copied forward | **confirmed independently** — the blob at `9548299a` hashes to `d9723cb8a3e397f81f4654fd42bac564c79f3c0e6ceb0449cc9c82c4bef473d5` | corrected in §14 with the error noted in place |
| 7 | gemini | `test_section_13_exists_before_cross_references` (`test_doc_gates.py:319`) will no longer test what its name says once the boundary moves to `## 14.` | **confirmed** — the test exists at that line | renamed and re-pointed as part of §7's test-rewrite step |

**Finding 5 is fixed differently from how codex proposed it.** codex asked to *move the helper split
ahead of §14 creation*. That ordering is also broken: with §14 absent, `_section13()`'s new
`text.index("## 14.", start)` raises `ValueError`, and a suite **error** is not a controlled result.
Both orderings fail, in opposite directions, so §7 step 1 makes the boundary change and §14's creation
**one indivisible step**. This is a deliberate divergence from the reviewer's literal instruction and is
flagged here for round 7 rather than applied silently.

**One gemini High is REJECTED, with reasons.** gemini's H2 claimed the `_section13()` split "breaks the
test suite on M8 reversion" with a `ValueError`, because `## 14.` is absent from the `v2.6.1` text. It
does not: **M8 reverts only §13** (`:389`, `:414`, `:426`), not the whole document. §14 is a *separate*
section created after §13 (`:520`) and is untouched by M8, so `## 14.` is still present and
`text.index` still resolves. codex, reviewing the same design, judged the §13/§14 helper split sound.
gemini's instinct nonetheless located a **real** hazard at the wrong point in time — the identical
`ValueError` is reachable during *implementation* if the split lands before §14 exists, which is
precisely what finding 5's atomicity requirement now forecloses. The claim is recorded as rejected on
its stated grounds and credited for the hazard it surfaced.

**Consistent with this campaign's pattern:** codex was the more reliable arm on mechanical claims
(the digest error, the ordering contradiction), while gemini's one confirmed original finding (M2's
classification) was a taxonomy judgement. Concordance on finding 1 — the same High, from the same two
sites, reached independently — is the strongest signal in this round.

## 16. Round-7 gate outcome

> **Recorded retroactively in round 8.** Round 7's findings were applied in `b2496a8`, but that commit
> added **no round-7 section** — the fixes landed while the record did not, so the plan cited "Round 7:"
> corrections inline with nothing defining what round 7 was. Reconstructed here from the two surviving
> transcripts, not from memory. *(The audit trail is part of the artifact: a fix whose provenance is
> unrecorded is indistinguishable from an unreviewed edit — which is the defect COREDEV-2497 exists to
> close.)*

**gemini `REQUEST_CHANGES` (1 High, 0 Medium) · codex `REQUEST_CHANGES` (1 High, 3 Medium, 2 Low).**
Frozen at `57ff072`, sha256 `b79f0d45b5b7236801c5516b296c84933181d18bf74bd0ef4f2cc73b20b0c6ea` —
codex's transcript verifies that exact digest. Transcripts:
`~/.claude/review-transcripts/2605r7-agy.txt` (2,993 B) and `…/2605r7-codex.txt` (258,079 B, 66 ticket-key
hits). *(The agy transcript types the ticket key **zero** times and is nonetheless genuine — it opens and
verifies six `file:line` citations by content. Provenance greps must use markers that actually appear.)*

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **the nine triples bind tokens to tokens, never a token to a SURFACE** — prose definitions may sit outside the table (`:208`), leaving every `surface_id` ungrounded. Counterexample: define `verdict-report` as the JSON object passed to the synthesizer (`agents/swift-reviewer.md:538`) and keep the approved row untouched — allowlists, uniqueness, polarity, disjointness and M4/M10–M12 all still pass while §13 is redirected onto **tool input** | **confirmed** — the counterexample is constructed against the real file and every check does pass | §4.2 gains a fourth **`anchor`** column and **M12d**. *(Round 8: this fix reached §4.2 and **not** §7 step 2 — see §17 finding 1)* |
| 2 | codex | **M2's differential does not discriminate** — the clean §13 is not required to contain the literal `excluded`, so the **weak** side fails before any deletion and never produces the required pass | **confirmed** | weak predicate changed to `the parsed table has exactly nine rows`. *(Round 8: this fixed the clean half and broke the mutated half — see §17 finding 2)* |
| 3 | codex | **round-6's atomicity decision was not propagated** — `:407` still said the boundary "must move BEFORE" §14 while `:483` requires an indivisible change | **confirmed** | `:407` marked superseded by the atomic step |
| 4 | codex | the **header** (`:5`) says a leading boundary change raises during M8's revert, contradicting the correct rejection at `:757` | **confirmed** — with M8 replacing only §13, `## 14.` remains and `_section13()` resolves; the error exists only in the pre-§14 implementation state | header corrected |
| 5 | codex | the round-6 frozen **commit** is mistyped `093df68f…`, which resolves to nothing | **confirmed** — `git rev-parse --verify` returns "Needed a single revision"; the digest `d4672051…` belongs to `093df6892386e4c69c17d5f82532a2333a2e92d3` | corrected in §15 with the error noted in place |
| 6 | codex | the taxonomy says every M4–M13 candidate mutates only the document or parser, but **M5a** deletes or renames a **test** (`:304`) | **confirmed** — M5a is still properly a candidate (it removes required evidence **without weakening the gate**); the category definition used artifact type as the discriminator | §6's discriminator restated as *what the mutation does to the contract* |
| 7 | gemini | `_section13()` raises `ValueError` on a **full-file** reversion to a state with no `## 14.` — the atomic step fixes the implementation window but not the helper's robustness | **rejected on its stated grounds, credited for the hazard** — M8 reverts only §13, so `## 14.` survives; this is the same claim gemini made in round 6, re-raised against the same design after codex judged it sound. Recorded rather than re-litigated | none — the atomic step already forecloses the reachable form of the hazard |

**Both arms flipped nothing on re-read, and the one gemini High was a repeat of a round-6 claim already
rejected with reasons.** Round 7's signal came almost entirely from codex; concordance was absent, which
is itself the weaker evidence state and is why round 8 was run rather than treated as converging.

## 17. Round-8 gate outcome

**gemini `REQUEST_CHANGES` (1 High, 1 Medium) · codex `REQUEST_CHANGES` (2 High, 1 Medium).**
Frozen at `b2496a8`, sha256 `61d8d4e15a9d76814dab807000bedb87dc39ed14d70db6dac13def68b9691d04` — both
transcripts verify that digest. Transcripts: `~/.claude/review-transcripts/2605r8-agy.txt` (2,746 B) and
`…/2605r8-codex.txt` (181,541 B, 91 ticket-key hits).

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **the `anchor` column never reached §7 step 2, so M12d is unimplementable** — §4.2 adds the fourth column and M12d mutates it, while step 2 still mandated a "three-column table" and shipped a nine-row three-column body. Following §7 literally, the implementer never creates the column M12d must mutate. codex adds that the plan supplied **no exact anchors or fingerprints** anywhere, and that §4.2's `:439` locus is broad enough to contain both the tool input (`:538`) and the report format (`:590`) — so even an anchor column pointed at `:439` would still admit the round-7 counterexample | **confirmed** — the same High from the same two sites, reached independently by both arms; step 2's table was read and is three-column | step 2 now mandates a **four-column** table and ships the **exact nine anchors + fingerprints**, opened and verified at `b2496a8`. `verdict-report` anchors at **`:590`** with fingerprint `### Verdict:`, not at `:439` — a broad anchor is not an anchor |
| 2 | **both** | **M2's differential still has no valid baseline** — gemini: the round-7 weak predicate ("exactly nine rows") now fails on the **mutated** document, because deleting an `out` name yields a row the fail-closed `_scope_rows` parser must **raise** on (`:252`). codex: §6 (`:503`) *also* still defined M2 by the superseded `excluded` predicate, and **step 7 routes implementation through §6**, so the superseded form is the one that would ship | **confirmed on both halves** — round 7 fixed the clean-document side and broke the mutated side; and §6's definition was never updated | mutation changed to **re-pairing a `producer_id`** (M12c's shape), which keeps all nine rows parseable and allowlisted — the only shape that can pass a weak gate under a fail-closed parser. §6 no longer restates a superseded predicate and now points at §4.1 as operative |
| 3 | codex | **M3 has no executable differential for the narrowed document** — the historical false-pass it cites depended on the marker also appearing in the **precedence clause**, which §7 step 4 moves out of §13 (`:409`). No surviving marker is named, so if the deleted row held the marker's only instance **both** gates fail and no adequacy difference is proved | **confirmed** — `test_doc_gates.py:287-290` documents exactly that dependency, and the plan does move the clause | M3 now names marker **`per the payload-region invariant`** and mutation **delete rule 3's disposition cell**: the phrase occurs in rules **1, 2, 3, 5 and 10** (five rows, counted in the shipped §13), so four survive the deletion — section-scoped passes, row-scoped fails |

**Concordance on findings 1 and 2 is the round's strongest signal** — two independent arms, the same two
defects, and in finding 1 the same pair of sites. Both are instances of the same class: **a design
decision fixed in §4 and left unpropagated to the operative §6/§7 restatement.** Round 6 had it with
two-column→three-column; round 8 has it twice. §9 records the class and the standing counter-measure.

## 18. Round-9 gate outcome

**gemini `REQUEST_CHANGES` (1 High) · codex `REQUEST_CHANGES` (3 High, 1 Medium).** Frozen at `8012bf6`,
sha256 `e6f70ca666042595801ea21b7f65ccadb78bd8d5b458c3db3586915ffa5a1759` — codex verified it explicitly.
Transcripts: `~/.claude/review-transcripts/2605r9-agy.txt` (2,004 B) and `…/2605r9-codex.txt`
(254,994 B). *(The gemini arm attempted to write `.plan_review.md`; the isolation harness contained it to
the disposable checkout and the real tree was unchanged — COREDEV-2607's wrapper working as designed.)*

**Every finding this round is against round 8's own fixes.** Not one is a pre-existing defect.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **step 2 mandates FOUR columns and then ships a FIVE-column table.** Round 8 added the `anchor` column and, in the same edit, a fifth `fingerprint` column — under the words "content is exactly these **nine approved rows**". An implementer copying it produces a five-column §13 that the four-column `_scope_rows` parser must reject | **confirmed** — the instruction and the table contradict each other in adjacent lines | **two tables**: the literal four-column §13 table to be copied, and a separate **test-only** fingerprint table that lives in the gate and never ships in `AGENT_CONTRACTS.md` |
| 2 | codex | **M2's mutant row is malformed under the four-column schema** — it is written with three data cells, so the fail-closed parser raises and the weak side fails on the mutated document **again** | **confirmed** — the row was authored in round 8 against the three-column schema and never updated when `anchor` landed in that same round | the mutant is now the full four-column row with the **anchor retained byte-identical** (mutating it too would make it M12d, not M2) |
| 3 | codex | **M3's marker is not guaranteed to survive the narrowing this plan orders.** `per the payload-region invariant` sits in rules 1, 2, 3, 5, 10 — but §4.4 (`:390`) permits simplifying those carve-outs, step 5 (`:619`) orders it, and §4.3 **relocates the payload-region invariant to §5**. Rule 3 may legitimately lose the phrase, and then the **strong** row-scoped gate fails on the clean document | **confirmed** — "all ten dispositions stay explicit" does not mean "unchanged wording", and the cited rules are exactly the ones being rewritten | marker changed to the **disposition classifier `**Adapted**`** (7 occurrences: rules 1, 2, 3, 4, 5, 6, 10), and **step 5 now pins the classifier vocabulary** `{**Adapted**, **Adopted**, **Restated positively**}` as a gated property — durable by mandate, not by luck |
| 4 | codex | **M12d does not prove the fingerprint check is load-bearing.** Its target `agents/swift-reviewer.md:538` is a blockquoted instruction line, **not a heading**, so the gate's "anchor line is a heading" check rejects it before the fingerprint is consulted | **confirmed** — `:538` is `> Call \`mcp__…synthesize_review\` with` | **M12e added**: leave the table untouched and rename/delete `### Verdict:` at `agents/swift-reviewer.md:660`. M12d proves the anchor; M12e proves the fingerprint |

**Findings 3 and 4 are the same shape as 2617's N5a this round: a gate whose only mutant is killed by a
different assertion, or a marker that looks durable and is not.** Round 8 fixed round 7's "no guaranteed
survivor" defect in M3 by choosing another incidental phrase; round 9 fixes it by choosing something the
plan *mandates*. **When a proof depends on a property, require the property — do not observe that it
currently holds.**

**Confirmed sound and unchanged:** all nine anchors resolve at the frozen commit and their fingerprints
occur where claimed; `verdict-report` correctly anchors at `:590` with the tool input at `:538` and
`### Verdict:` at `:660`; and M2's re-pairing mutation is the right shape for a fail-closed parser.

## 19. Round-10 gate outcome

**gemini `REQUEST_CHANGES` (2 High) · codex `REQUEST_CHANGES` (1 High).** Frozen at `740f561`, sha256
`7b1de0adfc6971e35975735a1c6116ab16292cfac166e60cb6cb435b9d00b716`. Transcripts:
`~/.claude/review-transcripts/2605r10-agy.txt` (1,896 B) and `…/2605r10-codex.txt` (183,164 B).

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **M3's marker is still not durable.** Round 12 hardcoded `**Adapted**` for rule 3 — but §4.4 (`:414`) expressly permits simplifying rule 3's carve-out, and that carve-out is the **only reason** its disposition is currently *Adapted* (`AGENT_CONTRACTS.md:494`). A compliant narrowed row could legitimately read `**Adopted** — end with one concrete next action.`, satisfying step 5's pinned vocabulary while making the **strong** assertion fail on the **clean** document, before any mutation | **confirmed** — pinning the vocabulary constrains the *set*, not which member each row uses | M3 becomes a **membership** test: strong = `rows[N]` contains **exactly one** of the three classifiers, for every N; weak = the section contains at least one. Deleting rule 3's cell fails the strong and passes the weak, **whatever classifier each rule ends up with** |
| 2 | gemini | **M12d still does not prove the fingerprint reads the anchor FROM THE TABLE.** It targets `:538`, a blockquote, so check (ii) "anchor line is a heading" rejects it before check (iii) runs. A gate that read the table for (ii) but **hard-coded `:590`** for (iii) would pass M12d *and* M12e | **confirmed** — round 9 moved this mutant off `:538` for the anchor's sake and left the same line in place for the fingerprint's | M12d retargeted to **`agents/swift-reviewer.md:439`** — a real heading whose section `:439`-`:589` contains **no** `### Verdict:` (verified). It passes (i) and (ii) and must fail on (iii) |

**Three markers, three failures of the same kind.** `per the payload-region invariant` (round 8) and
`**Adapted**` (round 12) were both pinned to *values this plan permits the narrowing to change*; the
membership test is invariant under every rewrite §7 step 5 allows. **When a proof depends on a property,
assert the property — not an instance of it.** Finding 2 is the same shape one level down: a mutant that
appears to exercise a check while a different assertion kills it first.

**codex confirmed the rest sound and unchanged:** the two table destinations are explicit, M2 now
preserves four parseable cells and isolates the triple-pairing assertion, and M12d/M12e separately
exercise the anchor and fingerprint checks.

## 20. Round-11 gate outcome

**gemini `REQUEST_CHANGES` (3 High, 2 Medium) · codex `REQUEST_CHANGES` (2 High, 1 Medium).** Frozen at
`1cd04b2`, sha256 `70b20df2bfe2c3734e31af8c0078f7c3ab3c09081d09ba7564fe87a00019fca4`. Transcripts:
`~/.claude/review-transcripts/2605r11-agy.txt` (2,732 B) and `…/2605r11-codex.txt` (310,143 B).

**Both arms independently built a WRONG GATE that passes every mutant this plan had.** That is the
round's central result and it is worth more than any single finding.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **M12d and M12e cannot pin three checks.** gemini's counterexample hard-codes check (ii) and implements (iii) from the table — both mutants die on (iii), so the hard-coding is never exposed. codex's asserts `rows == EXPECTED_ROWS` then searches each fingerprint at a **fixed locus** — M12d dies on row equality, M12e on the fixed search, clean passes, and **check (iii) never reads the table** | **confirmed by construction** — two mutants cannot pin three checks, and equality on the anchor column masked the difference | **the anchor column is no longer equality-checked** — triples are, anchors are *resolution*-checked. **M12f** swaps two rows' anchors (a hard-coded gate cannot notice a swap → pins (iii) to the table); **M12g** points an anchor at a non-heading whose enclosing section still holds the fingerprint (→ pins (ii)) |
| 2 | **both** | **M3's "exactly one" was never propagated to step 5**, which required only "an explicit classifier from" the vocabulary. A disposition like `**Adopted** — formerly **Adapted** …` satisfies step 5, carries two tokens, and fails the strong assertion **on the clean document** | **confirmed** — the assertion and the document requirement had drifted apart in the same round they were introduced | step 5 now mandates **exactly one**, in the same words as the assertion. codex additionally: `test_doc_gates.py`'s hard-coded per-rule classifier map (`:328-338`) must be replaced, and §4.5's at-risk-test list must name it |
| 3 | gemini | **M4 is pinned to a value the narrowing deletes** — "delete one in-scope surface from the **Scope paragraph**", but §4.2 and step 2 replace that paragraph with the table | **confirmed** | M4 retargeted to deleting an `in` **row from the table**. M1/M2/M5/M9-M13 re-swept: all are stated against the table or the parser |
| 4 | codex | *(Medium)* **step 6 orders only M5's combined regression**, but `extract_status` stops on **either** kind of intervening content (`capture.py:399-403`), so one combined fixture masks a parser handling only one cause | **confirmed** — §4 requires isolated fixtures and both M5b mutants; step 6 is what an implementer follows | step 6 now orders the isolated regressions and both mutants |
| 5 | gemini | *(Medium)* **§4.2's M12d still targets `:538`** while step 2 targets `:439` | **confirmed** — §9's defect class, inverted: fixed in the OPERATIVE section, left stale in the DESIGN one | §4.2 synced, with the operative definitions pointed at step 2 |
| 6 | gemini | *(Medium)* **intra-document line refs are stale** — §6 sends the implementer to `:161` for M3 (that is M1) and `:154` for M2 | **confirmed** — every round shifts these | **intra-document references are now by section and identifier name, never by line.** The mechanical checker validates repo citations and is blind to plan-internal drift, which is how this survived six rounds |

**Findings 3 and 2 are the same defect M3 has now had four times: a proof pinned to a value this plan
itself changes.** The sweep §7 asked for caught M4; the rest of M1-M13 came back clean.

## 21. Round-12 gate outcome

**gemini `REQUEST_CHANGES` · codex `REQUEST_CHANGES` (3 High, 1 Medium).** Frozen at `53e9947`, sha256
`1f4e602bff6fbe1ef1f1e47bbddf32f964ed02f3285734de1641ad1749a16ed7` — codex verified it. Transcripts:
`~/.claude/review-transcripts/2605r12-agy.txt` (2,981 B) and `…/2605r12-codex.txt` (279,588 B).

**Round 11 asked "can you still build a wrong gate?" Round 12 built two more.** Both are narrower than
the last, which is the shape of convergence — but neither was hypothetical.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **a verdict-only gate passes the clean document and ALL FOUR of M12d/e/f/g** — every one of them targets `verdict-report`, so a gate that asserts triple equality and then resolves only that row never inspects the other eight anchors | **confirmed** — the mutants pinned "reads the table" for one row, never the **per-row iteration** step 2 requires | **every anchor mutant is parameterised across all nine rows**, and each parameterisation must fail |
| 2 | codex | **the fingerprints did not discriminate surfaces.** Four of the five `out` rows carried the generic `## Output Format`, so swapping `security-findings` ↔ `concurrency-findings` preserves every triple, leaves both anchors valid headings, and leaves both sections containing that same fingerprint — **the gate accepts the wrong binding** | **confirmed by grep** — all four files have exactly one `## Output Format` | **unique fingerprints**, opened and verified: `## Security Review` (`:206`), `## Correctness & Concurrency Review` (`:267`), `## Performance & UX Review` (`:202`), `## Accessibility Audit` (`:213`). **M12h** added: the same-generic-fingerprint swap, which passed under round 14's fingerprints and must now fail |
| 3 | codex | **step 2 still carried anchor-equality language** — "content is exactly these nine rows", "every field drawn from a finite allowlist" — contradicting the resolution note four lines below and **re-creating the round-11 wrong gate** | **confirmed** | the allowlist and exact-set gate are now explicitly scoped to `(surface_id, producer_id, scope)`; the anchor is constrained by syntax and per-row resolution only |
| 4 | codex | *(Medium)* **§4.5 names neither pinned test** — the classifier map (`test_doc_gates.py:328-338`) nor the adjacent per-rule marker map (`:341`), whose phrases §4.4 permits step 5 to remove | **confirmed** — §4.5 claims only two tests are at risk | §4.5 must name both; step 5 says so explicitly |

**Findings 1 and 2 are the same defect at different depths: a proof that appears to test a mechanism
while a cheaper property satisfies it.** Round 11's version was structural (anchors equality-checked);
round 12's are that the mutants all touch one row, and that four surfaces share one fingerprint. Each
time the fix has been to make the *proof* discriminate, not to add another assertion.

## 22. Round-13 gate outcome

**codex `REQUEST_CHANGES` (1 High, 2 Medium) · gemini — FAILED REVIEW, and it IMPLEMENTED THE PLAN.**
Frozen at `9c54e03`, sha256 `e4edb2a978aa16a78ee0387ef9599959c71c289af09e8e0912ffd6269e20cb24`.
Transcripts: `~/.claude/review-transcripts/2605r13-codex.txt` (160,092 B) and `…/2605r13-agy.txt`
(2,092 B).

**The gemini arm reproduced COREDEV-2607 exactly.** Instead of reviewing, it reported performing the
§13/§14 split, migrating the payload-region invariant, rewriting `_section13`/`_section14`, adding
`_scope_rows()`, adding a disjointness gate and an anchor-resolution gate, adding three `test_capture.py`
fixtures, and committing as `43bf60d`. **The real tree was untouched** — `TREE=clean`, HEAD unchanged at
`9c54e03`, and all three plan digests still matching their freezes — because the round ran in a
disposable checkout. The wrapper did its job. *(One limitation now known: `43bf60d` **exists** as an
object, unreachable from any ref. The harness isolates the working tree and shares the object database.)*
The arm emitted no verdict and is not counted.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **the mutation suite still admits an anchor-EQUALITY gate.** M12d/f/g/h are all **rejection-only**, so a wrong gate can assert `anchor == EXPECTED_ANCHOR[surface_id]` and then search fingerprints at fixed loci: every rejection mutant dies at the equality check, M12e dies at the fixed search, and the clean document passes — **on all nine rows**. Parameterising rejection mutants across nine rows expands coverage but cannot distinguish equality from resolution | **confirmed** — only a mutation the gate must **accept** can separate them | **M12i, the positive metamorphic case**: insert a blank line before a source heading and increment that row's anchor to match; document and artifact now agree, so the gate **must still PASS**. An equality gate fails it. Three rounds of adding rejection mutants could not have closed this |
| 2 | codex | **"the section that heading opens" is undefined for the actual fingerprints — they are inside FENCED blocks.** All five are pseudo-headings in output templates; a scanner that is not fence-aware terminates the anchor's section at the first fenced `##` and **rejects the clean document** | **confirmed by execution** — each of the five sits after an odd number of ``` markers; all nine *anchors*, by contrast, are real headings outside fences | section boundaries are now **fence-aware**: boundary detection ignores fenced `#` lines, while the fingerprint search covers the section body **including** fenced content |
| 3 | codex | **§4.5 still named only two at-risk tests.** Round 12 put the correction in step 5 and left the list an implementer reads unchanged | **confirmed** — the design/operative drift this plan keeps committing, for the third time | §4.5 itself now names **four**, including both pinned maps (`test_doc_gates.py:328-338` and `:341-356`) |

**Finding 2 is the sharpest kind: my round-12 fix chose unique fingerprints without checking they were
reachable.** The uniqueness requirement was right and the values were verified to exist — but existence
in the file is not the same as visibility to the gate's own section scanner. **A proof must be checked
against the mechanism that will evaluate it, not only against the artifact.**

## 23. Round-14 gate outcome

**gemini `REQUEST_CHANGES` (2 High) · codex `REQUEST_CHANGES` (3 High, 2 Medium).** Frozen at `dacd56b`,
sha256 `3cc19eb1efd261f7fe9055bbd74a385d8e60b98ba92ddac9f94fefd011c9d7a5`. Transcripts:
`~/.claude/review-transcripts/2605r14-agy.txt` (2,664 B) and `…/2605r14-codex.txt` (272,900 B).

**gemini tried to build a wrong gate and FAILED — the first time the suite has held.** Its attempt used
an anchor-equality check with a `+1` line tolerance plus a fixed-locus fingerprint check with the same
tolerance; it passes the clean document and M12i and rejects M12d/e/f/h, **but M12g catches it**, because
M12g points the anchor at `EXPECTED+1` while leaving the artifact unchanged. **codex then built one that
survives** — which is the round's central result and the reason the plan now mandates an algorithm.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **a SHIFT-AWARE equality gate defeats M12i.** Per row, hard-code expected anchor `E`, heading text `H`, fingerprint line `F`; set `delta = 1` when line `E` went blank and `E+1 == H`; require `anchor == E+delta` and search the fingerprint at `F+delta`. Accepts the clean document **and every M12i parameterisation**; rejects M12d/f/g/h on the comparison and M12e at the fixed locus; **never resolves a section** | **confirmed by construction** — a finite mutant set cannot exclude every wrong gate | **the gate's ALGORITHM is now mandated**, and the mutants test *that* rather than trying to enumerate its complement. The plan also states plainly that mutation testing **bounds** gate correctness rather than proving it |
| 2 | codex | **the resolution predicate accepts anchors too broad to identify the surface.** Repointing `brainstorm-summary` to `skills/brainstorm/SKILL.md:10` — the file's **sole H1** — passes all three checks, because that section runs to EOF and contains the fingerprint at `:143`. The plan's own "a broad anchor is not an anchor" was contradicted by its formal rules | **confirmed** — the file has exactly one H1 and 201 lines | **step 4 added: the anchor must be the NEAREST ENCLOSING real heading of the fingerprint.** This makes the binding exact and raises the floor for a wrong gate — it must *find* the fingerprint and *walk up*, which no fixed-locus or shift-tolerant comparison does |
| 3 | codex | **M12i's required PASS contradicts every operative polarity statement** — the risk register, the verification taxonomy, the polarity rule and step 7 all still said every M4-M13 mutant must fail. Following them literally requires M12i to fail, permitting the very gate it excludes | **confirmed** | a **third proof kind** is named — *positive metamorphic cases* — and propagated to all four sites |
| 4 | codex | *(Medium)* **M1/M9 and M3 are rejection-only too.** Both M1 and M9 add the *dangerous* `swift-reviewer`, so a `VALID_AGENTS == EXPECTED_FIVE` gate satisfies both while violating the disjointness decision; and an updated exact classifier map passes M3 while violating membership-only | **confirmed** | **M1p** (add a harmless unrelated captured specialist → must PASS) and **M3p** (change a classifier within the vocabulary → must PASS) |
| 5 | codex | *(Medium)* **"tracking ``` toggles" is not precise enough.** `agents/swift-reviewer.md` carries inline `` ```json ``/`` ```jsonc `` in prose at `:304`, `:453`, `:455`, before the real fence at `:599`-`:665`; a substring-toggle implementation computes the inverted state and **rejects the clean document** | **confirmed** | fence detection specified as **CommonMark**: a delimiter is a *line* whose first non-whitespace run is ≥3 backticks/tildes. The anchor itself must also be outside a fence |
| 6 | gemini | **three more tests pinned to values the narrowing changes** — `test_payload_region_invariant_is_present_on_one_physical_line`, `test_invariant_covers_non_prose_payloads_too`, `test_precedence_clause_states_the_contract_wins` all scope to §13 while the plan relocates the invariant to §5 and moves the precedence protections out | **confirmed** — all three are in `COREDEV2602_AgentOutputStyle` | §4.5 now names **seven** at-risk tests. **The sweep must cover the existing suite, not only the M-list** |
| 7 | gemini | **the fence logic and M12f/g/h/i are in §7 step 2 and absent from §4.2**, which stops at M12e — §9's defect class running **operative → design** | **confirmed**, the second time it has run that direction | §4.2 now points at the full series and the algorithm |

**Findings 1, 2 and 4 are one lesson at three depths: a proof that constrains an implementation must
constrain what it *does*, not merely reject a list of things it must not do.** Three rounds of adding
rejection mutants could not exclude an equality gate; specifying the algorithm and adding positive cases
does.

## 24. Round-15 gate outcome

**Both arms `REQUEST_CHANGES` — gemini 1 High + 1 Medium, codex 1 High + 1 Medium + 1 Low.** Frozen at
`4e6162f`, sha256 `7afee28da2161be1421882d6f78b6ec82935d1a61ac822f0571cfaae81f0d8ed`. Transcripts:
`~/.claude/review-transcripts/2605r15-agy.txt` (2,507 B) and `…/2605r15-codex.txt` (316,155 B).

**Step 4 is confirmed sound by both arms — the first mechanism in this plan to survive a round intact.**
gemini verified it for all nine rows: the five fingerprints that *are* real headings resolve to
themselves, and the four inside fences resolve to their preceding `## Output Format` because the
fence-aware walk ignores fenced pseudo-headings. codex concurred. The three proof kinds are also verified
consistent across the risk register, taxonomy, polarity rule and step 7.

**Then both arms attacked step 3, and both broke it.**

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **step 3's "Locate the row's fingerprint" is under-specified.** codex: a gate can store each fingerprint's original line `F`, reuse the same `+1` delta M12i teaches it, inspect only `F+delta`, then genuinely perform steps 2, 4 and 5 from there — passing the clean document and **every** M12d-M12i parameterisation, yet failing when a harmless blank line is inserted **between** an anchor and its fingerprint. gemini: `find()` vs `rfind()` is unspecified and multiplicity unconstrained, so a duplicate fingerprint resolves the wrong instance and walks to an unrelated heading | **confirmed by construction** | step 3 now mandates a **content-driven search of the current file** — no stored line, no derived offset — and **exactly one** occurrence. **M12j added**: the positive body-shift case (blank line between anchor and fingerprint, table untouched) that the stored-`F` gate fails and only a content search passes |
| 2 | **both** | **an eighth pinned test** — `test_remaining_is_marked_safety_information` (`test_doc_gates.py:388`) asserts `"never a list to shorten"` inside `_section13()`, and §7 step 4 moves the `Remaining:` protection out of §13 | **confirmed** | §4.5 names eight. **Four consecutive rounds have each added one**, so the sweep is respecified as a *query over the test file* — every assertion scoped to `_section13()` whose target text this plan relocates — not a recollection |
| 3 | codex | *(Medium)* **the fence recognizer is not CommonMark-complete** — "first non-whitespace run" accepts a four-space-indented line (which is an indented code line, not a fence), and the closer rules never require the same delimiter **character** as the opener | **confirmed** | indent ≤ 3 spaces and matching delimiter character specified; delegating to a CommonMark parser named as the safer option |
| 4 | codex | *(Low)* the taxonomy still called itself "**Two** kinds of proof", and M1p/M3p were framed as exceptions to `M4–M13` though they mutate `VALID_AGENTS` and a classifier, not the scope table | **confirmed** | three kinds, with the positive cases given their own bullet |

**The pattern in findings 1 and the M12 series generally:** each positive case excludes one family of
compare-instead-of-compute gates, and each round has found the next family. M12i excluded stored-anchor
equality; M12j excludes stored-fingerprint-line lookup. **That is convergence, but it is convergence by
enumeration**, which is what the mandated algorithm exists to replace — the algorithm is the
specification, and the positive cases are evidence an implementation of it computes rather than compares.
