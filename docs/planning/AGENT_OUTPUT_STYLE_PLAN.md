# Agent Output Style Plan

**Status:** Planning — **round 3**, revised after two dual-gate rounds. Round 2: gemini `APPROVE`,
codex `REQUEST_CHANGES` (two High findings, both confirmed by execution and fixed here).
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
| 1 | Lead with the next action | **Adopt** | For a reviewer the "action" is the finding or verdict, not a shell command |
| 2 | Number multi-step tasks | **Adopt** | Matches the existing phase/step vocabulary in `swift-reviewer` and the workflow skills |
| 3 | End with one concrete next action | **Adapt — carve-out** | Where an output has a **mandated final element** (`VERDICT:` line, final fenced JSON block), the next action goes *before* it. Never last. See §4.2-C/E |
| 4 | Suppress tangents | **Adopt** | |
| 5 | Restate state every turn | **Adopt** | High value here: a 5-round review gate is exactly where "round 3 of 5" gets lost |
| 6 | Give specific time estimates | **Adapt** | Our agents advise; they rarely execute. Estimates address **whoever runs the steps** — upstream's own rule-6 carve-out says the same |
| 7 | Make completed work visible | **Adopt** | |
| 8 | Matter-of-fact tone for errors | **Adopt** | |
| 9 | Cap lists at 5 items | **Adapt — restate positively** | *Rank prose for readability; **never** cap, omit, or defer machine-consumed findings.* The cap applies to prose only. See §4.2-A |
| 10 | No preamble, no recap, no closing pleasantries | **Adapt — carve-out** | `Status:` and `BLOCKED — …` are **payload, not preamble**. See §4.2-B/D |

Nothing is omitted; three rules are adapted and one is restated positively. **Pin the upstream commit in
the section** so this audit is reproducible when upstream moves.

**Proof.** A `test_doc_gates.py` case that extracts **the new section specifically** — not the whole
file — and asserts each rule is present **together with a required normative marker for its
disposition**. Section-scoped extraction is required because `AGENT_CONTRACTS.md` already mentions JSON
findings, statuses and verdicts elsewhere (`:90`, `:242`), so a whole-file grep would false-pass.

**Round-2 correction.** Asserting rule *titles* is not enough: reverting rule 9's positive restatement,
deleting rule 3's mandated-final-element placement, or flipping an adapted rule back to a bare adopt
would leave all ten titles intact and still pass. Each of the four **adapted** rules (3, 6, 9, 10) needs
a marker phrase asserted and mutation-tested independently of its title — e.g. rule 3's "before it,
never last", rule 9's "never cap, omit, or defer", rule 10's "payload, not preamble".

### 4.2 — Six machine contracts would be damaged by the rules as written (High)

**Root cause — the load-bearing finding.** Round 1 named three collisions; round 2 named five. There are
**six**. Two are *position* contracts, attacked from opposite ends of a response by "no preamble" and
"end with a next action"; the sixth (**F**) is a *completeness* contract on a field whose truncation
silently downgrades a gate.

| | Contract | Where | What a naive rule does |
|---|---|---|---|
| **A** | **JSON findings array completeness** | five reviewers → `synthesize_review` | "Cap lists at 5" makes a reviewer drop findings to hit a count. The synthesizer dedups/merges **assuming the array is complete** — this is a correctness regression, not concision |
| **B** | **`Status: COMPLETE \| BLOCKED \| PARTIAL`, read *before* the findings** | `AGENT_CONTRACTS.md:242`; emitted at e.g. `agents/security-reviewer.md:265-278` | "No preamble" strips it. **It does not become a clean pass** — see the round-2 correction below — but attribution is lost: a bare array is not a handoff (`agents/swift-reviewer.md:148`, "THE STATUS IS THE ATTRIBUTION"), a statusless capture leaves its sidecar absent (`capture.py:513`), and an absent sidecar is `UNATTRIBUTED` (`reviewer-roster.sh:188`). Cost is **mandatory re-dispatch → `NEEDS DISCUSSION`**: wasted work and a degraded verdict |
| **F** | **The Output Contract detail trailer** — `Blocker Description`, `What Was Attempted`, `Completed`, `Remaining`, `Confidence` | `agents/security-reviewer.md:280-287`; parsed by `capture.py` `_STATUS_FIELDS`; forwarded by `reviewer-roster.sh:238` | Rule 9 caps a long `Remaining:` list; rules 4/10 suppress the fields as "metadata". **This is the one that can actually downgrade a gate**: a held PARTIAL with structural remainder escalates to `NEEDS DISCUSSION`, and the roster is *"the ONLY sidecar reader — if it does not forward `remaining`, nothing can preserve it"*. Truncated remainder can become a non-gating warning |
| **C** | **`VERDICT:` as the exact final line** | `skills/{gemini,codex}-review`, parsed by `review-synthesis` | "End with one concrete next action" puts something *after* it; deterministic parsing degrades to prose inference |
| **D** | **`BLOCKED — …` result prefix** | `agents/graph-api-debugger.md:20-22`, `agents/jira-manager.md:252` | "No preamble" strips the house signal for a subagent with **no user channel** |
| **E** | **Final fenced JSON block position** | all five reviewers | Same attack as C, from rule 3 |

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
`test_verdict_vocab_consistent_across_all_three` discipline in that file (13 cases pass today).

### 4.3 — Placement (Low)

**Root cause.** `AGENT_CONTRACTS.md` runs §1–§12 (`:12`–`:379`), then an **unnumbered**
`## Cross-references` at `:421`; 443 lines total, no §13.

**Fix.** Insert as **§13**, after §12's body and before `## Cross-references`.

**Note for the reviewer.** Verified independently by both round-1 reviewers. `COREDEV-2583` is approved
and edits §5 (`:235`) and §11 (`:354`) of this file — disjoint from the insertion point, but line
numbers shift once it lands, so cite the **section number** in anything durable. (One round-1 reviewer
reported 444 lines; `wc -l` gives 443, corroborated by the other reviewer.)

### 4.4 — Attribution and reproducibility (Low)

**Fix.** Name the source, its MIT licence, and the **pinned commit** `07684c4a` in the section header.
No code is copied — the rules are restated in this repo's vocabulary and four are deliberately altered —
so a section-level notice suffices; no `LICENSE` vendoring.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| A reviewer truncates a findings array to satisfy a list cap | **High** without the carve-out | §4.2-A, and rule 9 is restated positively so the prose-only boundary is in the rule itself, not only the carve-out |
| A reviewer omits `Status:`, losing attribution | Medium | §4.2-B. **Corrected in round 3:** this is *not* a fail-open — `test_absent_sidecar_is_unattributed` proves an absent status fails **closed** to `UNATTRIBUTED`. The real cost is mandatory re-dispatch and a degraded `NEEDS DISCUSSION`, not a clean pass |
| A reviewer truncates `Remaining:` in the Output Contract trailer | **High** without the carve-out | §4.2-F — the one genuinely gate-downgrading case: a held PARTIAL with structural remainder escalates to `NEEDS DISCUSSION`, and `reviewer-roster.sh` is the only reader that can preserve it |
| Something is emitted after the `VERDICT:` line | Medium | §4.2-C/E; rule 3 is adapted to place the next action *before* a mandated final element |
| An agent strips its `BLOCKED — …` prefix as preamble | Medium | §4.2-D; the clause states these are payload, not preamble |
| Style rules read as binding on JSON payload *content* | Medium | The section scopes itself to "prose written for a human reader" in its first sentence |
| **Ships documentation and a presence gate, but no behavioural change** | **Medium — accepted and stated** | Raised from Low in round 2. This ticket adds no runtime injection and no compliance evaluation. The doc gate proves the text is *present*, never that agents *obey* it. Obedience is a `COREDEV-2599` eval obligation, recorded there |
| Upstream moves and the audit becomes unreproducible | Low | Commit pinned in the section (§4.4) |
| Merge conflict with `COREDEV-2583` | Medium | 2583 lands first; insertion point is disjoint from §5/§11 |

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
**section-scoped** extraction of §13.

## 7. Implementation order

1. §4.3 — insert §13 with the ten-rule disposition.
2. §4.2 — the precedence clause naming all six contracts. **Not separable from step 1**; the rules must
   never land without it.
3. §4.4 — attribution + pinned commit.
4. §4.1 + §4.2 — the section-scoped doc-gate cases with per-rule and per-contract mutations.
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
  six-finding synthesizer probe (six in, six retained) and ran the existing doc gates (13/13).
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
   closed that: a bare array is not a handoff (`agents/swift-reviewer.md:148` — "THE STATUS IS THE
   ATTRIBUTION"), a statusless capture leaves its sidecar absent (`capture.py:513`), an absent sidecar is
   `UNATTRIBUTED` (`reviewer-roster.sh:188`), and `scripts/tests/test_reviewer_roster.py:216`
   (`test_absent_sidecar_is_unattributed`) proves it fails **closed**. Verified by running the roster:
   absent status → five `UNATTRIBUTED`, exit 3. The plan had invented a fail-open that does not exist.
2. **A sixth contract was missing** — the Output Contract detail trailer. Confirmed real:
   `agents/security-reviewer.md:280-287` mandates `Blocker Description` / `What Was Attempted` /
   `Completed` / `Remaining` / `Confidence`; `capture.py` parses them via `_STATUS_FIELDS`; and
   `reviewer-roster.sh:238` states it is *"the ONLY sidecar reader — so if it does not forward
   `remaining`, nothing can preserve it. Discard the ATTRIBUTION, never the INFORMATION."* Rule 9 could
   cap a long `Remaining:` list, downgrading a gating `NEEDS DISCUSSION` to a non-gating warning. This
   is the genuinely dangerous case, and it is the one gemini's sixth-contract search missed.

Codex's third (Medium) finding — that asserting rule *titles* would let an adapted rule silently revert
— is fixed in §4.1's round-2 correction: each adapted rule now needs its own mutation-tested marker.

**Pattern worth recording:** the draft was wrong in *both* directions at once — it overstated B's
severity (claiming a fail-open the codebase had already closed) while understating coverage (missing F
entirely). Severity inflation and coverage gaps are not opposite errors; both come from reasoning about
the contract from the plan rather than from the code.
