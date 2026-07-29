# Agent Output Style Plan

**Status:** Planning — **round 11**, revised after ten dual-gate rounds. Round 10: **both**
`REQUEST_CHANGES`, converging on the same defect — the invariant was introduced but only two of the five
rows actually referenced it, and its own marker was not literal in its own clause.
**Created:** 2026-07-29
**Last Updated:** 2026-07-29
**Ticket:** `COREDEV-2602` — AGENT_CONTRACTS: add an agent output-style section
**Epic:** `COREDEV-2485` — Plugin audit remediation / agent-skill-hook-CI modernization
**Branch:** `feat/COREDEV-2602-agent-output-style`
**Target version:** `2.6.0` → **`2.6.1`** (patch: documentation only, no asset-count change).
**Depends on:** `OPUS5_ALIGNMENT_PLAN.md` (`COREDEV-2583`, **APPROVED**) — lands first; it edits §5 and
§11 of the same file, disjoint from this insertion point.
**Source:** `github.com/ayghri/i-have-adhd`, MIT, pinned at commit
**`07684c4ab625dd7d1ea6e99e065f60bc0ac6a1ba`** (2026-07-28). Only the **Claude portion** is in scope.

---

## 1. Context

`ayghri/i-have-adhd` is a Claude Code plugin (MIT, ~13k★) whose single skill shapes model output for a
reader with ADHD. Its rules are good. **This plan does not migrate them — it adapts them**, because
this plugin's output is mostly consumed by *software*, not read by a person.

That distinction is the whole ticket. Five reviewers emit JSON findings arrays that `synthesize_review`
dedups and merges; each is preceded by a `Status:` line that `swift-reviewer` reads *before* the
findings, and a detail trailer (`Remaining:` and friends) that the roster forwards as safety
information; the plan-review gate parses a trailing `VERDICT:` line deterministically; and a subagent
with no user channel signals by prefixing its result `BLOCKED — …`. **Every one of those is a place
where a well-meaning output-style rule can silently destroy a signal we depend on** (§4.2).

**Maintainer decisions (2026-07-29), locked:**

| Decision | Value |
|---|---|
| Mechanism | Rules go in **`AGENT_CONTRACTS.md`**, not a 22nd skill |
| Source scope | **Claude portion only** — no multi-harness distribution |
| Posture | **Adapt, do not migrate.** Do not break what already works. |
| Asset counts | Unchanged: `21 / 21 / 0 / 1` |

**Why the contract rather than a skill** — corrected in round 2. The round-1 draft claimed a skill is
"necessarily opt-in and per-session". **That is false**: upstream ships a `SessionStart` hook plus an
opt-in flag file (`~/.claude/.i-have-adhd-always`) that injects the ruleset every session, so a skill
*can* be made persistent. The real reasons are: a 22nd skill moves the counts and collides with the
release chain `COREDEV-2583` locked; house style for 21 agents belongs in the document that already
governs cross-agent behaviour; and **importing upstream's persistence hook is deliberately excluded**
(this plugin already registers 10 hook events and is not taking an 11th for output styling).

## 2. Scope

**In:** one new numbered section in `AGENT_CONTRACTS.md` carrying an explicit disposition for **all ten**
upstream rules, the precedence carve-out naming **all six** protected machine contracts, and
doc-gate assertions with per-rule and per-contract mutation coverage. Attribution to the pinned source.

**Out:** any new skill or agent; any change to the reviewers' JSON schema, `synthesize_review`, the
`Status:`/`VERDICT:` contracts, or `hooks/hooks.json`.

**Decided, not overlooked:** upstream's multi-harness distribution (`.cursor/`, `.codex-plugin/`,
`.agents/`, `gemini-extension.json`, `cursor-skill-sync.yml`) — this plugin is Claude Code-specific and
has no second harness. Upstream's `evals/` harness, `plugin-load-check.yml`, and the drift-guard pattern
are owned by `COREDEV-2599`, `COREDEV-2598`, `COREDEV-2600` respectively.

## 3. Guiding principle

> **The shape is house style; the contract is law.** Where an output rule and a machine-readable
> contract disagree, the contract wins and the rule yields. Completeness and position of a
> machine-consumed payload are never traded for brevity.

Upstream states the same precedence for itself — *"A rule fights the harness… the constraint wins, the
shape stays"* — which is why its rules are safe to adapt **provided the carve-out comes with them, and
names our contracts specifically**. Adopting the rules without that is the one way this ticket does harm.

---

## 4. Findings, fixes, and proofs

### 4.1 — Agent output style is undocumented; all ten upstream rules need an explicit disposition (Medium)

**Root cause.** `AGENT_CONTRACTS.md` governs ownership, tool floors, tiering, CFR labelling and pipeline
order — but says nothing about the *shape* of what an agent writes, so a new agent has nothing to
conform to.

**Round-2 correction.** The round-1 draft listed eight rules and **silently omitted upstream rules 2 and
3** while §1 implied numbered work was adopted. Omission-by-silence is migration's failure mode, not
adaptation. Every upstream rule now carries a recorded disposition:

| # | Upstream rule (pinned `07684c4a`) | Disposition | Molded to this tool |
|---|---|---|---|
| 1 | Lead with the next action | **Adapt — carve-out** | For a reviewer the "action" is the finding or verdict — which is exactly why this cannot be bare: *leading* with the finding would push `Status:` after it (§4.2-B), and leading with the verdict would move `VERDICT:` off the final line (§4.2-C/E). *Lead the human-facing prose with the actionable point; **never reorder a mandated payload** to do it — the lead goes before `Status:`, per the payload-region invariant.* |
| 2 | Number multi-step tasks | **Adapt — carve-out** | Matches the existing phase/step vocabulary — but the Output Contract trailer is parsed **one value per single field line**, and `What Was Attempted: <the steps you tried>` is literally a step list. *Number human-facing prose only — **and only before `Status:`, per the payload-region invariant**; machine trailer fields and JSON values keep their mandated single-line/schema shape.* A numbered step inside the payload region breaks the parse even though it is not prose (executed). See §4.2-F |
| 3 | End with one concrete next action | **Adapt — carve-out** | *The next action goes **before `Status:`, per the payload-region invariant** — not merely before the fence.* **Proven necessary:** `Status: COMPLETE` / `Next: run the tests.` / fence returns `None` from `extract_status`, because only blank or detail-field lines may sit between `Status:` and the fence. Placing it before `Status:` parses correctly. See §4.2-B/C/E/F |
| 4 | Suppress tangents | **Adapt — carve-out** | Upstream offers a second issue "as a separate question". In a review, an independent **in-scope** finding deferred that way leaves the JSON array — the same failure §4.2-A protects. *Suppress out-of-scope tangents; **never** defer an in-scope finding out of the current array.* See §4.2-A |
| 5 | Restate state every turn | **Adapt — carve-out** | High value here: a 5-round review gate is exactly where "round 3 of 5" gets lost. But a subagent opening with a state summary would displace the `BLOCKED — …` prefix its result must *begin* with (§4.2-D). *Restate state in prose; **never before a mandated result prefix**, and never between `Status:` and the fence (payload-region invariant).* |
| 6 | Give specific time estimates | **Adapt** | Our agents advise; they rarely execute. Estimates address **whoever runs the steps** — upstream's own rule-6 carve-out says the same |
| 7 | Make completed work visible | **Adopt** | |
| 8 | Matter-of-fact tone for errors | **Adopt** | |
| 9 | Cap lists at 5 items | **Adapt — restate positively** | Upstream says **split** a long list into "do now" vs "later" — it does not say drop. But a *deferred* item is still absent from a findings array, so: *rank prose for readability; **never** cap, split, omit, or defer machine-consumed findings.* Prose only. See §4.2-A |
| 10 | No preamble, no recap, no closing pleasantries | **Adapt — carve-out** | `Status:` and `BLOCKED — …` are **payload, not preamble** — and per the **payload-region invariant** the cure for an unwanted opener is to delete it, never to move it below `Status:`. See §4.2-B/D |

Nothing is omitted. **Seven** rules are adapted (1, 2, 3, 4, 5, 6, 10), one is restated positively (9),
and only **two** remain bare adopts — 7 ("make completed work visible") and 8 ("matter-of-fact tone for
errors"). Both were audited against all six contracts by both reviewers. Rule 8: agreement, no path.
Rule 7: the reviewers **disagreed** — one alleged a path into contract F — and **execution resolved it**
(the alleged mechanism does not occur; the real effect is inert). See §15. **Pin the upstream commit in
the section** so this audit is reproducible when upstream moves.

**Proof — a TWO-STAGE extraction; the stages are not interchangeable.**

1. **Bound to §13.** A whole-file grep would false-pass because `AGENT_CONTRACTS.md` already mentions
   JSON findings, statuses and verdicts elsewhere (`:90`, `:242`).
2. **Then row-scope every per-rule assertion** — §13 → the disposition table → the single row for rule
   N — and assert the marker *within that row*. Section scope is reserved **solely** for the
   per-contract assertions in the precedence clause.

Stage 1 alone is the known-broken design: rule 10's marker also occurs in the precedence clause and a
risk row, so deleting its disposition would still find the phrase somewhere in §13.

**Round-2 correction.** Asserting rule *titles* is not enough: reverting rule 9's positive restatement,
deleting rule 3's mandated-final-element placement, or flipping an adapted rule back to a bare adopt
would leave all ten titles intact and still pass. Each of the **eight** rules that are not a bare adopt
(1, 2, 3, 4, 5, 6, 9, 10) needs a marker phrase asserted and mutation-tested independently of its title.

**Extraction must be ROW-scoped, not section-scoped.** Round 7 found that a section-scoped marker
assertion false-passes whenever the same phrase appears elsewhere in §13 — rule 10's marker
(`payload, not preamble`) also occurs in the precedence clause and a risk row, so deleting rule 10's
disposition would still find it. The test therefore extracts **§13 → the disposition table → the single
row for rule N**, and asserts the marker *within that row*. Phrase collisions elsewhere in the section
then cannot mask a deleted disposition.

| Rule | Required marker — a **literal** substring of that rule's own row |
|---|---|
| 1 | `never reorder a mandated payload` |
| 2 | `keep their mandated single-line/schema shape` |
| 3 | `per the payload-region invariant` — occurs in rule 3's row and, by design, in rows 1/2/5/10 too, so this one is asserted **row-scoped** |
| — | plus the **payload-region invariant** itself: `Within it, nothing but detail fields and blank lines.` — one physical line by construction; asserted once, section-scoped, deletion-mutated |
| 4 | `defer an in-scope finding out of the current array` |
| 5 | `never before a mandated result prefix` |
| 6 | `whoever runs the steps` |
| 9 | `cap, split, omit, or defer` — the token `split` asserted separately |
| 10 | `payload, not preamble` |

Each marker must be verified to appear **verbatim** in its row. Round 7 also found the inverse defect:
rules 3 and 4 had idealised markers (`"before it, never last"`, `"never defer an in-scope finding…"`)
that did **not** occur literally in their dispositions, because markdown emphasis (`*before* it`,
`**never** defer`) broke the string. A marker that does not match its own row is worse than none — it
fails on a correct document.

**Round-5 correction, retained.** Rule 9's marker previously omitted `split`, so reverting the row to its
round-4 wording — dropping both the source's split characterisation *and* the prohibition on splitting
machine findings — would have satisfied every described test. The `split` token is now its own assertion.

### 4.2 — Six machine contracts would be damaged by the rules as written (High)

**Root cause — the load-bearing finding.** Round 1 named three collisions; round 2 named five. There are
**six**. Two are *position* contracts, which rules 10 and 3 pressure from opposite ends of a response;
the rest are *completeness* contracts. **Two of the six (A and F) can downgrade a gate verdict** —
proven by execution, not asserted (see the note below the table).

Each row states the **mechanism** the rule can set in motion and the **conditional** outcome, per §11.

**The payload-region invariant — one rule that subsumes five carve-outs.** Executing every
parser-touching adaptation against `capture.py::extract_status` (not reasoning about it) showed they all
fail the same way:

| what an adapted rule might emit | result |
|---|---|
| prose **before** `Status:` | parses |
| a finding, next action, or state line **between** `Status:` and the fence | **`None`** |
| a **numbered** `What Was Attempted:` / `Remaining:` | **`None`** |
| `Status:` dropped entirely | **`None`** |

So the boundary is structural, not per-rule:

> **The payload region is the span from the `Status:` line to the final fenced JSON block.**
> **Within it, nothing but detail fields and blank lines.**
> Not prose, not a numbered step, not a next action, not a state restatement, and **not another machine
> payload** — a `VERDICT:` line there breaks the parse exactly as prose does. Everything else an agent
> emits goes **before** `Status:`.

Rules 1, 2, 3, 5 and 10 each reference this one invariant **by name** rather than restating an
approximate boundary of their own — verified mechanically, not asserted (each row must contain the
literal `payload-region invariant`). Round 9 proved why that matters: rule 3's carve-out said "before the final fenced JSON
block", which *sounds* correct and still returns `None`.

| | Contract | Where | Mechanism, and the conditional cost |
|---|---|---|---|
| **A** | **JSON findings array completeness** | five reviewers → `synthesize_review` | Rule 9 can prompt a reviewer to **split or defer** a long findings list (upstream says "split into *do now* vs *later*", not drop — but a deferred item is absent from the array all the same). The synthesizer dedups/merges assuming the array is complete, so **if** a deferred finding was a blocker, the verdict can downgrade. **Executed proof:** six findings including a blocker → `REQUEST_CHANGES`; the same set capped to five → `APPROVE_WITH_SUGGESTIONS` |
| **B** | **`Status: COMPLETE \| BLOCKED \| PARTIAL`, read *before* the findings** | `AGENT_CONTRACTS.md:242`; emitted at e.g. `agents/security-reviewer.md:266-279` | Rule 10 can prompt dropping it as preamble. **It does not become a clean pass** — a bare array is not a handoff (`agents/swift-reviewer.md:149`, "THE STATUS IS THE ATTRIBUTION"), a statusless capture leaves its sidecar absent (`capture.py:513`), and an absent sidecar is `UNATTRIBUTED` (`reviewer-roster.sh:193`). It requests **up to one** re-dispatch, whose *fresh* report is then used (`swift-reviewer.md:218`) — but the bound is *"at most ONE spawn per reviewer per review"*, and **if that reviewer's single retry is already spent, no further spawn is permitted**: it goes straight to Needs Confirmation → `NEEDS DISCUSSION` (`swift-reviewer.md:487-490`). So the cost is a retry *if the budget is unspent*, and a degraded verdict *if it is not* |
| **C** | **`VERDICT:` as the exact final line** | `skills/{gemini,codex}-review`, parsed by `review-synthesis` | Rule 3 can prompt appending a next action *after* it, breaching the mandated final-line contract and risking ambiguity. **Not** guaranteed prose inference: `review-synthesis` extracts the token when present and infers only when **absent**, and `review-verdict.py` takes reviewer statuses as explicit CLI arguments rather than by transcript position |
| **D** | **`BLOCKED — …` result prefix** | `agents/graph-api-debugger.md:21-23`, `agents/jira-manager.md:253` | Rule 10 can prompt treating it as preamble. It is the standardised signal a subagent uses to hand back — it has no `AskUserQuestion`. **If** dropped, the invoking session sees an ordinary result rather than a recognisable hand-back. Note the body normally still carries the diagnosis and proposed edit (`graph-api-debugger.md:21-25`), so the substance is not necessarily lost — what is lost is the machine-recognisable marker that this needs a human, which is what makes the omission easy to miss |
| **E** | **Final fenced JSON block position** | all five reviewers | Same mechanism as C, from rule 3: content appended after the block breaches its mandated final position |
| **F** | **The Output Contract detail trailer** — `Blocker Description`, `What Was Attempted`, `Completed`, `Remaining`, `Confidence` | `agents/security-reviewer.md:281-287`; parsed by `capture.py` `_STATUS_FIELDS`; forwarded at `reviewer-roster.sh:244` | **Rule 2 is the sharpest path here and is proven:** the trailer is parsed one value per single field line, so numbering a multi-step `What Was Attempted:` or `Remaining:` **terminates the trailer scan and returns no status at all** — verified by execution (`Remaining: B.swift, C.swift` → full status; `Remaining:` + `1. B.swift` / `2. C.swift` → `None`). That is an absent sidecar → `UNATTRIBUTED` → a retry, or `NEEDS DISCUSSION` when the budget is spent. Separately, rule 9 can prompt splitting a long `Remaining:` list, and rules 4/10 can prompt suppressing the fields as metadata. A held PARTIAL with structural remainder escalates to `NEEDS DISCUSSION`, and the roster is *"the ONLY sidecar reader — so if it does not forward `remaining`, nothing can preserve it"* (`reviewer-roster.sh:239-242`). **If** the truncated portion held the structural remainder, that escalation can become a non-gating warning |

**Note on the two gate-downgrading contracts.** A and F are the pair that can change a verdict rather
than merely cost work. **A is proven**: a round-4 reviewer executed the synthesizer with six findings
including a blocker (`REQUEST_CHANGES`), then with the list capped to five (`APPROVE_WITH_SUGGESTIONS`).
F is the same shape, on the `Remaining:` field. Earlier drafts called F "the one" gate-downgrading
case; that exclusivity was wrong.

**Round-2 correction to an overstated claim.** Round 1 attributed C to upstream's *"End when the answer
is done"*. That sentence does **not** instruct an agent to omit a mandated verdict, and upstream
explicitly says harness constraints win. The real conflict is upstream **rule 3** ("End with one
concrete next action"), which is a *positional* requirement. Attributing it to the wrong sentence would
have sent an implementer looking for a rule that does not say what the plan claimed.

**Fix.** The section carries a normative precedence clause naming **all six**:

> These rules govern **prose written for a human reader**. Where a rule conflicts with a
> machine-readable contract — the completeness of a JSON findings array, the `Status:` line that
> precedes it, the **Output Contract detail trailer** that follows it (`Blocker Description`,
> `What Was Attempted`, `Completed`, `Remaining`, `Confidence`), the `VERDICT:` line that must end a
> review transcript, the final fenced JSON block, or a `BLOCKED — …` result prefix — **the contract wins
> and the rule yields**. Completeness and position of a machine-consumed payload are never traded for
> brevity. In particular `Remaining:` is **safety information, never a list to shorten**. `Status:`,
> the trailer, and `BLOCKED — …` are payload, not preamble.

**Proof.** A doc-gate case asserting the clause exists **and names all six contracts**, with **one
deletion mutation per contract** — remove any single name → the case fails. For **F**, additionally
assert the five trailer field names and the "never a list to shorten" clause for `Remaining:`. Mirrors the existing
`test_verdict_vocab_consistent_across_all_three` discipline in that file (20 cases pass today).

### 4.3 — Placement (Low)

**Root cause.** `AGENT_CONTRACTS.md` runs §1–§12 (`:12`–`:411`), then an **unnumbered**
`## Cross-references` at `:453`; 475 lines total, no §13. **(Re-derived after `COREDEV-2583` landed —
it rewrote §11 and extended §5, and pinning `effort` shifted every agent file by one line. The plan
predicted this shift; the numbers below are the post-2583 truth.)**

**Fix.** Insert as **§13**, after §12's body and before `## Cross-references`.

**Note for the reviewer.** Verified independently by both round-1 reviewers. `COREDEV-2583` is approved
and edits §5 (`:235`) and §11 (`:368`) of this file — disjoint from the insertion point, but line
numbers shifted when it shipped (v2.6.0), so cite the **section number** in anything durable. (One round-1 reviewer
reported 444 lines; `wc -l` gives 443, corroborated by the other reviewer.)

### 4.4 — Attribution and reproducibility (Low)

**Fix.** Name the source, its MIT licence, and the **pinned commit** `07684c4a` in the section header.
No code is copied — the rules are restated in this repo's vocabulary and **eight of the ten carry a non-bare disposition** (seven adapted, one positively restated) —
so a section-level notice suffices; no `LICENSE` vendoring.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| A reviewer splits or defers findings to satisfy a list cap, and a deferred item was a blocker | **High** without the carve-out | §4.2-A — **one of two contracts that can downgrade a verdict**, and the only one proven by execution (6 findings → `REQUEST_CHANGES`; capped to 5 → `APPROVE_WITH_SUGGESTIONS`). Rule 9 is restated positively so the prose-only boundary sits in the rule itself, not only the carve-out |
| A reviewer omits `Status:`, losing attribution | Medium | §4.2-B. **Corrected across rounds 3–5:** not a fail-open (`test_absent_sidecar_is_unattributed` proves it fails **closed**), and not a guaranteed `NEEDS DISCUSSION` — it requests **up to one** re-dispatch, bounded by the "at most ONE spawn per reviewer" budget; the verdict degrades only when that budget is already spent or the retry is still unusable |
| A reviewer splits `Remaining:` and the structural remainder falls in the deferred half | **High** without the carve-out | §4.2-F — the **other** contract that can downgrade a verdict: a held PARTIAL with structural remainder escalates to `NEEDS DISCUSSION`, and `reviewer-roster.sh` is the only reader that can preserve it. Earlier drafts wrongly called this the *only* such case |
| Something is emitted after the `VERDICT:` line | Medium | §4.2-C/E; rule 3 is adapted to place the next action *before* a mandated final element |
| An agent drops its `BLOCKED — …` prefix as preamble | Medium | §4.2-D; the body normally still carries the diagnosis, so the substance survives — what is lost is the machine-recognisable hand-back marker, which is precisely what makes the loss easy to miss. The clause states these are payload, not preamble |
| Style rules read as binding on JSON payload *content* | Medium | The section scopes itself to "prose written for a human reader" in its first sentence |
| **Ships documentation and a presence gate, but no behavioural change** | **Medium — accepted and stated** | Raised from Low in round 2. This ticket adds no runtime injection and no compliance evaluation. The doc gate proves the text is *present*, never that agents *obey* it. Obedience is a `COREDEV-2599` eval obligation, recorded there |
| Upstream moves and the audit becomes unreproducible | Low | Commit pinned in the section (§4.4) |
| Merge conflict with `COREDEV-2583` | **Resolved** | 2583 **shipped** as v2.6.0; this plan's citations were re-derived against the post-2583 tree and the §13 insertion point (before `## Cross-references`) is untouched by it |

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

Counts stay **21 / 21 / 0 / 1**; hook events stay **10**.

**Mutation proof — per item, not per section.** Round 1's proof only mutated whole-section presence and
three contract names, so deleting an individual adopted rule would still have passed. Required now:
**one deletion mutation per adopted rule** (§4.1) and **one per protected contract** (§4.2), against a
**row-scoped** extraction for per-rule assertions (§13 → disposition table → the single row for rule N)
and **section-scoped** extraction for the per-contract assertions in the precedence clause. The two are
not interchangeable: a section-scoped per-rule assertion re-creates rule 10's false-pass, because its
marker also appears in the precedence clause and a risk row.

## 7. Implementation order

1. §4.3 — insert §13 with the ten-rule disposition.
2. §4.2 — the precedence clause naming all six contracts. **Not separable from step 1**; the rules must
   never land without it.
3. §4.4 — attribution + pinned commit.
4. §4.1 + §4.2 — the doc-gate cases. **Per-rule assertions are row-scoped; per-contract assertions are
   section-scoped.** Each case must additionally parse the disposition table's four cells, require
   exactly one row per rule number 1–10, and assert the **exact disposition value** for every rule —
   not only its title and marker. Round 8 modelled the gap: blanking rule 1's `Adapt — carve-out` cell,
   or rule 7's `Adopt` cell, left every other described assertion green.
5. Version bump to 2.6.1 + CHANGELOG, last.

## 8. Round-1 resolutions

The three round-1 open questions are settled; recorded so round 2 does not reopen them.

1. **Scope — resolved: agents *and* output-producing workflow skills.** Both reviewers agreed. Covers
   human-facing prose emitted by agents and while executing workflow skills; **excludes skill-body
   documentation itself** (that is injected context, not output). The machine-contract precedence clause
   applies throughout.
2. **Doc-gate adequacy — resolved: ship now.** Both agreed not to wait for `COREDEV-2599`. The gate is
   explicitly **drift protection for the contract text**, not a compliance test; §5 now says so, and
   behavioural compliance is recorded as a 2599 eval obligation.
3. **"Cap lists at 5" — resolved: keep, restated positively** (codex), *not* dropped (gemini). Codex's
   framing preserves the rule's value while making the boundary part of the rule: rank prose for
   readability; never cap, omit or defer machine-consumed findings. Dropping it entirely would have lost
   a useful prose rule to avoid a hazard the carve-out already handles.

## 9. Notes

- Round 1: gemini `REQUEST_CHANGES` (found contract **B**), codex `REQUEST_CHANGES` (found the missing
  rule dispositions, contracts **C/E**, the overstated attribution, the non-mutation-proof proof, and
  the false "skills are necessarily per-session" claim). Both independently confirmed the §4.3
  placement facts and both `BLOCKED` citations.
- Every structural claim re-verified against the worktree at `58e7205`. Codex additionally executed a
  six-finding synthesizer probe (six in, six retained) and ran the existing doc gates (13/13 at the
  time; the suite is 20 cases after COREDEV-2583 added the §4.10 gates).
- This plan changes no runtime behaviour. It is documentation plus a drift gate — deliberately, and
  §5 records that limit rather than implying more.

---

## 10. Round-2 gate outcome

**gemini `APPROVE`.** Cloned upstream at the pinned commit, confirmed exactly ten rules with ten
dispositions, verified contracts A–E against the tree, **searched for a sixth and reported none**, and
confirmed the whole-file-grep false-pass by showing `findings|status|verdict` appear dozens of times
outside the insertion point.

**codex `REQUEST_CHANGES`** — two High findings, both confirmed here by execution, both fixed above:

1. **Contract B's consequence was factually wrong.** The draft claimed stripping `Status:` makes a
   `BLOCKED` reviewer's `[]` read as a clean pass. It does not. The COREDEV-2490 roster redesign already
   closed that: a bare array is not a handoff (`agents/swift-reviewer.md:149` — "THE STATUS IS THE
   ATTRIBUTION"), a statusless capture leaves its sidecar absent (`capture.py:513`), an absent sidecar is
   `UNATTRIBUTED` (`reviewer-roster.sh:193`), and `scripts/tests/test_reviewer_roster.py:216`
   (`test_absent_sidecar_is_unattributed`) proves it fails **closed**. Verified by running the roster:
   absent status → five `UNATTRIBUTED`, exit 3. The plan had invented a fail-open that does not exist.
2. **A sixth contract was missing** — the Output Contract detail trailer. Confirmed real:
   `agents/security-reviewer.md:281-287` mandates `Blocker Description` / `What Was Attempted` /
   `Completed` / `Remaining` / `Confidence`; `capture.py` parses them via `_STATUS_FIELDS`; and
   `reviewer-roster.sh:239-242` states it is *"the ONLY sidecar reader — so if it does not forward
   `remaining`, nothing can preserve it. Discard the ATTRIBUTION, never the INFORMATION."*, forwarding
   it at `:244`. Rule 9 could split a long `Remaining:` list, and **if** the structural remainder fell
   in the deferred half a gating `NEEDS DISCUSSION` could become a non-gating warning. *(Round 4
   correction: this record originally called F "the genuinely dangerous case" and cited `:280-287` /
   `:238`. Both were wrong — see §12. **A** can downgrade a verdict too, and is proven by execution.)*

Codex's third (Medium) finding — that asserting rule *titles* would let an adapted rule silently revert
— is fixed in §4.1's round-2 correction: each adapted rule now needs its own mutation-tested marker.

**Pattern worth recording:** the draft was wrong in *both* directions at once — it overstated B's
severity (claiming a fail-open the codebase had already closed) while understating coverage (missing F
entirely). Severity inflation and coverage gaps are not opposite errors; both come from reasoning about
the contract from the plan rather than from the code.

---

## 11. Round-3 gate outcome — and a pattern in this plan's own errors

**gemini `APPROVE`.** Verified every round-2 correction against the tree, and searched for a seventh
contract, finding none.

**codex `REQUEST_CHANGES`** — three findings, all confirmed here and fixed:

1. **High — B's consequence was still overstated.** "Mandatory re-dispatch → `NEEDS DISCUSSION`" is not
   the rule. `agents/swift-reviewer.md:218` says `UNATTRIBUTED` triggers **one** re-dispatch *"and use
   its fresh report"*; `NEEDS DISCUSSION` follows only when that retry is unavailable, exhausted, or
   still unusable. A successful fresh `COMPLETE` preserves an ordinary verdict.
2. **Medium — C's consequence was overstated.** `review-synthesis` extracts the `VERDICT:` token when
   present and falls back to prose inference only when it is **absent**; `review-verdict.py` takes
   reviewer statuses as explicit CLI arguments, not by transcript position. C is still a real positional
   violation, but the harm is contract breach and ambiguity, not guaranteed inference.
3. **Low — a miscited line.** `reviewer-roster.sh:188` merely constructs the sidecar path; the
   absent-sidecar branch runs `:189-194` with `emit_unattributed` at **`:193`**. Corrected in both
   places.

**The pattern worth naming, because this plan has now made the same error three times.** Round 2
claimed a fail-open that COREDEV-2490 had already closed. Round 3 replaced it with a guaranteed
`NEEDS DISCUSSION` that the recovery ladder does not guarantee. Round 3 also asserted guaranteed prose
inference that the synthesis contract does not produce. Each time the correction of an overstatement
introduced a *smaller* overstatement, because the consequence was reasoned about from the plan's own
narrative rather than traced through the code path.

The rule this plan should be read under, and which an implementer should carry into §13's own wording:
**state the mechanism, then the conditional outcome — never a guaranteed outcome.** A contract is worth
protecting because of what it *can* cost, not because of the worst thing imaginable if it is missing.

---

## 12. Round-4 gate outcome

**Both `REQUEST_CHANGES`** — and both found the plan violating the rule it had itself introduced in §11
one round earlier. That is the finding, more than any individual line.

**gemini:** §4.2-A said a dropped finding *"is a correctness regression, not concision"* — guaranteed
phrasing, and false for a duplicate or trivial finding. §4.2-D said rule 10 *"strips the house signal"*
and then never stated what that costs.

**codex:** three findings, all confirmed:

1. **High — F was wrongly claimed to be the *only* gate-downgrading contract** (asserted in §4.2, §5 and
   §10). **A can downgrade too, and codex proved it by execution**: six findings including a blocker
   produced `REQUEST_CHANGES`; the same set capped to five produced `APPROVE_WITH_SUGGESTIONS`. The
   exclusivity claim is retracted; both are now described conditionally.
2. **Medium — §4.2 still used guaranteed verbs** ("makes", "caps", "suppresses", "puts", "strips").
   Rewritten so every row states a mechanism the rule *can* set in motion and the outcome that follows
   *if* it hides a blocker or structural remainder. Also a **fidelity error against the source**:
   upstream rule 9 says to **split** an over-long list, not to drop items — the plan had been
   paraphrasing it as a cap. A deferred item is still missing from an array, so the adaptation stands,
   but the characterisation of upstream was wrong.
3. **Low — two F citations overran.** `agents/security-reviewer.md` ends at line 286, so `280-287` was
   out of range; and `reviewer-roster.sh:238` only opens the `PARTIAL` branch — the "only sidecar
   reader" comment is `:239-242` and `REMAINING` is forwarded at `:244`.

**Why this round mattered.** §11 named a pattern of overstatement; round 4 showed the pattern survived
the naming of it, in the rows earlier rounds had not scrutinised. The rule only took effect once it was
applied row-by-row rather than stated once. That is worth carrying into §13's implementation: a
precedence clause is not self-enforcing, which is exactly why each rule and each contract gets its own
mutation test rather than one assertion for the section.

---

## 13. Round-5 gate outcome

**gemini `APPROVE`**, no findings — it re-cloned upstream to verify rule 9's wording and read all six
rows adversarially for residual guaranteed phrasing.

**codex `REQUEST_CHANGES`** — three findings, all confirmed and fixed:

1. **High — rule 4 was a bare adopt that reopens §4.2-A.** Upstream rule 4 says to finish the first
   issue and *"offer the second as a separate question"*. In a code review, an independent **in-scope**
   finding deferred that way is absent from the current JSON array — exactly the failure A protects, and
   exactly the failure proven to downgrade a verdict. Rule 4 is now **adapted**, distinguishing an
   out-of-scope tangent (suppress) from an in-scope finding (never defer out of the array), with its own
   mutation-tested marker. Five rounds of review passed over this because attention was on the rules
   already flagged as dangerous; a bare adopt attracted none.
2. **Medium — B and D still carried guaranteed outcomes.** B said omission "costs one re-dispatch";
   the real bound is *"at most ONE spawn per reviewer per review"* and **if that retry is already spent
   no further spawn is permitted** (`swift-reviewer.md:487-490`) — so it is *up to* one, and a spent
   budget degrades the verdict immediately. D said the confirmation is "silently never surfaced"; in
   fact the body normally still carries the diagnosis and proposed edit (`graph-api-debugger.md:21-25`),
   so what is lost is the machine-recognisable marker, not necessarily the substance.
3. **Medium — the round-4 fidelity fix was not itself mutation-proved.** Rule 9's text gained "never
   cap, **split**, omit, or defer", but the required marker omitted `split` — so reverting the row to its
   round-4 wording would have satisfied every described test. `split` is now an independent assertion,
   and §4.1 carries an explicit marker table rather than an "e.g." list.

**The lesson this round adds.** Rounds 1–4 hardened the rules already known to be dangerous. Round 5
found the risk in a rule marked **safe** — a bare adopt, which by construction has no carve-out, no
marker, and no test. *Every* rule needed a disposition, and a disposition of "adopt" is a claim that
must be defended, not a default. §4.1's table now carries five non-bare dispositions where round 1
carried none.

---

## 14. Round-6 gate outcome — the bare-adopt audit

Round 5 concluded that a disposition of "adopt" is a claim to be defended. Round 6 tested that by
auditing **all five** remaining bare adopts. Three of the five reached a machine contract.

**codex `REQUEST_CHANGES` — High, proven by execution.** Rule 2 ("Number multi-step tasks") breaks
contract F *and* destroys the status parse entirely. The trailer is parsed **one value per single field
line** (`capture.py:295`), and any numbered continuation before the JSON fence terminates the scan — documented
at `capture.py:327` ("ANY other content … ") and implemented by the stop branch at `capture.py:369`.
Reproduced independently:

| trailer form | `extract_status` |
|---|---|
| `Remaining: B.swift, C.swift` | full status dict |
| `Remaining:` then `1. B.swift` / `2. C.swift` | **`None`** |
| `What Was Attempted:` then numbered steps | **`None`** |

`None` → absent sidecar → `UNATTRIBUTED` → a retry, or `NEEDS DISCUSSION` when the budget is spent.
This was the *least* suspicious rule in the set: it was marked adopt with the note "matches the existing
phase/step vocabulary", and `What Was Attempted: <the steps you tried>` is literally a step list.

**gemini `REQUEST_CHANGES` — two positional bare adopts.** Rule 1 ("Lead with the next action") is
dangerous *because of this plan's own adaptation note*: having said the "action" is the finding or
verdict, leading with either displaces `Status:` (B) or moves `VERDICT:` off the final line (C/E). Rule
5 ("Restate state every turn") would have a subagent open with a state summary, displacing the
`BLOCKED — …` prefix its result must *begin* with (D).

**Reviewer disagreement, resolved toward caution.** Codex judged rules 1, 5, 7, 8 as having no
*independent* path — reasoning that rule 3's carve-out and the global precedence clause already cover
positional conflicts. Gemini judged 1 and 5 as needing their own carve-outs. **Gemini's position is
adopted**, because §12 already concluded a precedence clause is not self-enforcing, and a marker costs
one line. Both reviewers agree 7 and 8 are safe, and they are the only bare adopts left.

Final tally: **two adopt, seven adapt, one positive restatement** — where round 1 had eight rules, no
markers, and three contracts.

---

## 15. Round-7 gate outcome — the mutation proof was not itself sound

Both `REQUEST_CHANGES`, and both landed on the same High finding: **the marker assertions did not work.**

**Rule 10's marker collided** (found independently by both reviewers). `payload, not preamble` appears in
rule 10's disposition, in the global precedence clause, and in a §5 risk row. A section-scoped assertion
would still find it after rule 10's disposition was deleted — so the per-rule mutation test this plan
insisted on could not actually fail.

**Sweeping every marker found the inverse defect too** (neither reviewer caught this; it surfaced from
counting occurrences): rules 3 and 4 had markers that appear **only in the marker table** and not in
their own dispositions, because markdown emphasis broke the literal string. Those assertions would have
failed against a *correct* document.

Fix: extraction is now **row-scoped** — §13 → disposition table → the single row for rule N — so
collisions elsewhere cannot mask a deletion, and every marker is required to be a literal substring of
its own row.

**Rule 7 — reviewers disagreed; execution settled it.** Gemini argued rule 7 ("Make completed work
visible") breaks contract F by prompting `Completed:` prose that corrupts the trailer scan and drops the
status — "the same `UNATTRIBUTED` failure mode proven for Rule 2". Codex audited 7 and 8 and found no
independent path. **Tested directly:**

| input | `extract_status` |
|---|---|
| `Completed:` prose *before* `Status:` | `{'status': 'COMPLETE'}` — unaffected |
| real PARTIAL trailer, then `Completed:` prose | real values retained; first occurrence wins |
| `Status: COMPLETE` + `Remaining: nothing — everything shipped.` | `{'status':'COMPLETE','remaining':'…'}` — **a spurious field is injected** |

So gemini's *mechanism* was wrong (no status loss), but a stray trailer keyword in prose **can** inject a
field. It is inert in practice: `reviewer-roster.sh:244` emits `REMAINING` only inside the `PARTIAL`
branch, so a spurious `remaining` on a `COMPLETE` is never forwarded. **Rule 7 stays a bare adopt**, and
this evidence is recorded so the question is not re-derived a third time.

Two Low findings also fixed: §4.4 still said "four are deliberately altered" (now eight non-bare
dispositions), and `capture.py:323` is the function declaration — the rule is documented at `:327` and
implemented at `:369`.

---

## 16. Round-8 gate outcome

**gemini `APPROVE`**, no findings — confirmed the row-scoped design closes both the false-pass and
false-fail modes, and independently re-derived the `reviewer-roster.sh` PARTIAL-only reasoning.

**codex `REQUEST_CHANGES`** — three findings, all confirmed:

1. **High — the plan still handed the implementer the known-broken design.** §4.1 says extraction "must
   be ROW-scoped, not section-scoped", but §6 and §7 step 4 *still said section-scoped*. An implementer
   following the later, more operational instructions would have re-created rule 10's false-pass
   exactly. Both now distinguish **row-scoped per-rule** assertions from **section-scoped per-contract**
   assertions and say why they are not interchangeable.
2. **Medium — a blanked Disposition cell still passed everything.** Row scoping catches a deleted row or
   a deleted marker, but the described tests only asserted titles plus markers. Codex modelled it:
   blanking rule 1's `Adapt — carve-out` cell, or rule 7's `Adopt` cell, left every assertion green —
   defeating the plan's own requirement that all ten dispositions be explicit. The test must now parse
   the four cells, require exactly one row per number 1–10, and assert the **exact disposition value**.
3. **Low — §4.1 misstated the rule-7 history**, claiming both reviewers found no path. §15 records
   correctly that one alleged a path and execution disproved the mechanism. §4.1 now matches §15.

**Why the same defect kept regenerating.** Rounds 5–8 each fixed a proof mechanism and each left a
weaker copy of the old instruction somewhere downstream: the marker table was fixed while §6/§7 still
said section-scoped; row scoping was added while the *cell* remained unasserted. A plan that specifies
its own test in three places will drift between them. **The implementer should write the doc-gate test
first, from §4.1's table alone, and treat §6/§7 as summaries of it — not as independent specifications.**

---

## 17. Round-9 gate outcome — the adaptation itself was still unsafe

**gemini `APPROVE`**, no findings; it re-verified every citation against the post-2583 tree.

**codex `REQUEST_CHANGES`** — three findings, all confirmed, one by execution:

1. **High — §4.1's proof paragraph still said "Section-scoped extraction is required"**, ten lines above
   the row-scoped correction that condemns it. Rounds 8 and 9 fixed §6 and §7 but left the paragraph
   that *introduces* the proof. Now an explicit two-stage operation: bound to §13, **then** row-scope
   every per-rule assertion; section scope only for per-contract assertions.
2. **High — rule 3's adaptation was still unsafe, and codex proved it.** The rule said the next action
   goes "before the final fenced JSON block". That is not enough — only blank or detail-field lines may
   sit between `Status:` and the fence, so a next action placed there destroys the **entire trailer**:

   | placement | `extract_status` |
   |---|---|
   | before `Status:` | `{'status': 'COMPLETE'}` |
   | after `Status:`, before the fence | **`None`** |
   | after a full PARTIAL trailer | **`None`** |

   Reproduced independently. The rule now says **before the entire mandated payload** — the `Status:`
   line, its trailer, and the fence — and the marker changed from `Never last.` (which the unsafe
   wording satisfied) to `before the entire mandated payload`.
3. **Low — stale "post-2583 truth".** §12 is `:411` not `:379`; §11 is `:368` not `:354`; the file is
   475 lines not 476; the doc-gate suite is 20 cases not 13 (COREDEV-2583 added the §4.10 gates).

**The lesson this round adds — and it is the sharpest one.** Every previous round found the *plan's*
machinery wrong. This round found an **adaptation itself** wrong: rule 3 had a carve-out, a marker and a
planned mutation test, and was still unsafe, because the carve-out named the wrong boundary. A
protection that names an approximate boundary is not a protection. **Every adaptation's boundary must be
executed against the real parser, not reasoned about** — which is exactly how rule 2's hazard was found
two rounds earlier, and would have found this one sooner had it been applied to all seven adaptations
rather than only the rule under suspicion.

**Round-9 addendum — what the probe changed.** Codex's lesson was that a boundary must be *executed*,
not reasoned about. Applying that to **all** parser-touching adaptations (not just rule 3, the one under
suspicion) showed they share a single failure mode, so five approximate carve-outs collapse into one
structural invariant stated above §4.2's table. That is strictly stronger: an implementer can no longer
satisfy a rule's wording while violating the parser, because the wording now *is* the parser's rule.

---

## 18. Round-10 gate outcome — the invariant was announced, not applied

Both `REQUEST_CHANGES`, converging on one defect: **round 9 introduced the payload-region invariant and
then only wired two of the five rows to it.**

**Both reviewers, independently:** §4.2 claimed "Rules 1, 2, 3, 5 and 10 each reference this one
invariant". Only **1 and 5** did. Rule 3 *restated* the boundary in its own words; rules **2 and 10 did
not mention it at all**. A claim about the plan's own structure, contradicted by the plan's own table.

**codex — High, executed.** Rule 2's wording was satisfiable while breaking the parser:

```text
Status: COMPLETE
1. Run the tests.        ← numbered "human-facing prose", per rule 2 as written
```json
[]
```
```

→ `None`. Moving the numbered line before `Status:` → `{'status': 'COMPLETE'}`. Rule 2 said to number
prose and keep *machine fields* single-line — it never bound the **prose** to the payload region.

**codex — Medium, and the sharpest irony of the gate.** The invariant's own required marker occurred
**only in the marker table**, never in its normative clause, because a hard Markdown line break split
`detail-field` from `lines`. That is *exactly* round 7's false-fail class — recreated by the fix for
round 9. The clause is restructured so the marker sits on **one physical line by construction**.

**gemini — High, mechanism right, attribution wrong** (a recurring shape for this reviewer). It argued
`prompt-review` could emit `Status:` then `VERDICT:` and lose the status. The **parser behaviour is
real** — verified — but **no code reviewer emits `VERDICT:`**; that belongs to the plan-review CLIs
(`gemini-review`, `codex-review`, `review-synthesis`). The scenario is hypothetical; the **wording
defect is not**, because the invariant said "human-facing *prose*" while the parser breaks on *any*
non-detail content. The clause now says so explicitly, naming a stray `VERDICT:` as an example.

**Fixes.** Rows 1, 2, 3, 5 and 10 now reference the invariant **by name**; rule 3 references instead of
restating; the claim is verified mechanically rather than asserted; the invariant marker is one physical
line; and 2583's shipped status is current throughout.

**A note on verifying the verification.** After fixing the markers, a first check reported all eight
literal — but it compared against the marker list *in the checking script*, not the marker **table** in
the document. Re-running it against the table found rule 3's entry still carrying the pre-fix wording.
**A check that restates its expectations instead of reading them from the artifact is not a check.**
Same class as the two inert gates this epic has already produced.
