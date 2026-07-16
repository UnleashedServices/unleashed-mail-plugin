# COREDEV-2490 — the capture fail-open: Positive-Attribution Roster Gate

**Status:** v9 — APPROVED at R10 (`GATE OK — APPROVE [gemini=APPROVE, codex=APPROVE]`), then AMENDED by
the mandated adversarial pass, which found a real fail-open in the INVOCATION. Re-gated at R11.
**Epic:** COREDEV-2485 · **Bug:** COREDEV-2490 · Branch off the audit stack tip.

## Adversarial pass (post-approval, MANDATED by this plan) — it found a real fail-open

The plan requires an adversarial pass and says a hole would be *"a design break, not a tuning miss"*.
It found one — **not in the script, in the INVOCATION**, and it is the reason this section exists:

**`UNRESOLVED` was never assigned.** The consumer recipe piped `"${UNRESOLVED[@]}"` to the roster, but
that variable had **five prose mentions, one use, and zero assignments** — and `swift-reviewer.md`
itself documents why it never could have one: *"a shell var cannot survive this block"*, so a name the
model reasons out cannot reach a later Bash block. An unset array still emits **one blank line**, the
loop skips it, and the script **exits 0** — byte-identical to the documented happy path. Reproduced: a
reviewer whose spawn silently failed read as a **clean pass**, with `reviewer-roster.sh` entirely
correct. The same slip via `argv` (`roster.sh <name> </dev/null`) did the same thing.

**Fix — invert the polarity, and make the RECIPE's default safe too.** stdin now carries the reviewers
the orchestrator **HOLDS**; the script classifies the **complement**. The shipped fence is **empty by
default** — every reviewer name is commented out, so **executing it verbatim classifies all five** and
only deliberate uncommenting shrinks the roster. (R11, codex: the first cut of the fence pre-filled all
five and said "delete the ones you don't hold" — which reinstated the fail-open at the one place a model
is likeliest to copy unedited. *A ready-made happy path is not a fail-closed default.* This defect has
now moved up a level four times — prose, then a stray sentence, then an unassigned variable, then the
recipe's default — which is itself the finding: **the default is the control.**) Silence therefore classifies **all five** and fails CLOSED; only a
**positive, in-band assertion** can shrink the roster. A held name that is unknown or duplicated is
**exit 4** (an input error routed to the same uncertainty branch), so a typo cannot silently resolve a
reviewer; the consumed list is echoed as `ROSTER-INPUT: held = …` for the transcript. Both invocation
slips are now dead: the unset-variable case AND the argv case classify everyone.

*The design is named **positive attribution**; it took an adversarial pass to notice the principle was
not applied to its own invocation. The default was "everything is fine" — the exact bug class this
ticket exists to kill.*

**What the pass could NOT break** (real signal, executed not asserted): *"The core invariant is
genuinely sound — I could not construct ANY filesystem state that certifies. Everything degrades to
UNATTRIBUTED + exit 3."* All five earlier fixes re-verified closed. Two further findings were confirmed
as **safe-direction only**: a >5-digit round dir is invisible to the reader (`context.sh:129` caps at 5
digits while `capture.py` does not) and an `agent_id`-less capture can be skipped — both lose a RATCHET,
neither can certify, **because COMPLETE never certifies**. That rule is load-bearing, not
belt-and-braces. Also hardened: `_printable` now applies to `RATCHET`'s description and `REMAINING`'s
payload — the only transcript-derived (prompt-injectable) fields, previously emitted raw.

## R12 (codex) — the fence printed a failure but the PROCESS exited 0

**Finding, accepted:** `ROSTER=$?` captured 3, then `echo` succeeded and became the fence's exit status,
so the block reported success while carrying `ROSTER=3`. `RecipeTestCase` missed it because
`_run_recipe()` returned stdout and **threw away `returncode`** — my gap, and the same shape as every
other fail-open here: *a control that reports success while carrying a failure.*

**Resolution: `exit "$ROSTER"`.** I first flagged this as reversing #43 (COREDEV-2494 M5), where both
skeptics rejected `exit "$BUILD_VERIFY"` in an agent Bash block. **On inspection that is not a conflict.**
#43's objection was explicitly about **retry cost** — *"a failed Bash call invites a retry -> a second
full `xcodebuild test`"*. Measured here: a roster re-run is **0.09s, read-only, no side effects**; a
build-verify re-run is **minutes**. The reasoning does not transfer; only the surface shape resembled it.
The general rule stands (#43's `echo`-only remains correct for build-verify) — the discriminator is
whether a retry is expensive, not whether `exit` is used.

Pinned: `test_shipped_recipe_run_VERBATIM_fails_closed` now asserts **rc == 3**, and
`test_recipe_propagates_the_roster_status_to_the_process` asserts a RATCHET reaches the process as 2.
Mutation-proved: dropping `exit "$ROSTER"` -> 2 failures.

**This was the FIFTH level this defect climbed** — prose, a stray sentence, an unassigned variable, the
recipe's default, and finally the exit code. Each fix was correct; each time the bug relocated one layer
out. **The default is the control**, at every layer that has one.

## R5 — three fixes accepted; one blocker ACCEPTED AS FACT but its proposed FIX REJECTED

gemini confirmed 3 of 4 R4 blockers closed ("the design is robust against the LLM misassembling the
roster"; "the cost pricing is finally honest"). Four items remained. v6 answers all four.

### R5-1 (codex, BLOCKER): cross-review erasure — **fact accepted, fix rejected, claim narrowed**

Codex is right about the mechanism, and **I reproduced it independently** rather than take it on trust:
round-1 holds a schema-valid finding F → the roster re-dispatches (new `agent_id`) → `select_round`
(`capture.py:234`) sees `is_final_capture(round-1)` and returns **round-2** → the hook writes `[]` there →
the next review's `context_latest_round_dir` selects round-2 → **F is gone from disk**. Verified with a
real finding lifted from `samples/security-reviewer.json` (my first attempt used a hand-written finding
that was **not** schema-valid, so `select_round` never advanced and the test proved nothing — worth
recording, because it is exactly how this reproduction gets faked).

**But its proposed fix — "union applicable captured findings across rounds" — is WRONG and v6 rejects
it.** Rounds exist *to supersede*: round N+1 is a re-review of possibly-**fixed** code. Unioning across
rounds resurrects every finding that was legitimately fixed, **forever** — permanent false positives in
the exact bucket humans learn to ignore. That is worse than the bug.

**The severity is also lower than stated, and this is checkable rather than rhetorical.** Codex wrote
that after erasure "another fresh COMPLETE + `[]` can then produce a clean pass". Walk it under v6's own
invariant:

| | v6 | today (no roster) |
|---|---|---|
| Review B reads round-2 `[]` + `COMPLETE` | **does not certify** → UNATTRIBUTED → **re-dispatch** → a fresh, attributed, in-session report decides | **face value → CLEAN PASS**, no re-dispatch |

So the erasure costs **corroboration, not safety** — nothing on disk ever certifies, so no false clean
follows from it — and on this precise vector **v6 is strictly better than the status quo**. The clean
pass codex describes is a *fresh reviewer's actual opinion*, which is the system working; the alternative
is a design where a finding can never be fixed.

**Therefore v6 narrows the claim instead of the mechanism** (the honest half of codex's note): *captures
add findings within the review that reads them; across reviews the newest round supersedes.* The
unqualified "they never subtract" is deleted — it was never true and could not be made true without
resurrecting fixed findings. Cross-review retention is out of scope and tracked separately.

### R5-2 (gemini, precise): the roster must FORWARD PARTIAL's `remaining`
*"It cannot preserve safety metadata it never sees."* Correct: v5 told the consumer to preserve a
persisted PARTIAL's structural `remaining`, while the roster printed only a reason and the rewrite of
`:148-184` removed the `.status` read. v6 makes the roster the **single sidecar reader** and has it
forward the payload (below).

### R5-3 (codex): "no documented contract is reversed" was OVERCLAIMED — mine
v6 **does** reverse the **consumer's** face-value contract at `AGENT_CONTRACTS.md:205`. That is the
entire point of the ticket. The accurate, narrower claim: **no PRODUCER/capture contract is reversed** —
`capture.py`'s "Observe-only, fail-open" stays literally true and is now *relied upon*.

### R5-4 (codex): the one-retry ledger conflicted with surviving recovery prose
`swift-reviewer.md:389` still commands another fresh run for unrecoverable findings, which licenses a
second retry. v6 rewrites `:389` to consult the **same** per-review ledger (below).

## R4 (both `REQUEST_CHANGES`) — the SPINE survived; the SPECIFICATION did not

Both reviewers accepted the invariant and **independently confirmed the linchpin by execution** (codex
also found the shipped test that pins it: `scripts/test-hooks.sh:507-513`). I re-proved it myself: a
round-2 where the agent wrote nothing → `context_latest_round_dir` selects round-1. So v5 keeps the
design and fixes what it *specified*. Five corrections, all accepted:

1. **BLOCKER — v4 deleted one block but left its contradictions alive.** Deleting `:148-184` leaves
   `:144-147` (*"skip spawning … do not re-run them"*) and `:354-357` (*"Work from the JSON arrays, not
   the prose reports … the source of truth"*) standing. Codex's vector needs no misbehaviour, only a
   choice between contradictory instructions: a genuinely BLOCKED reviewer emits `[]`; findings publish
   but `_write_status` fails silently; the external path supplies five bare arrays incl. that `[]`; the
   model follows the surviving *"do not re-run"* + *"arrays are source of truth"* → **clean pass**.
   → v5 **rewrites** `:144-147` and `:354-357`; positive attribution must unambiguously supersede both.
2. **BLOCKER — v4 violated its own invariant.** The roster emits only RATCHET/UNATTRIBUTED and Step 5
   said *"use its fresh in-session report"*. So: a captured array holds a REAL finding → UNATTRIBUTED →
   the fresh reviewer returns `COMPLETE` + `[]`, having missed it → the fresh report **replaces** the
   captured array → the finding vanishes. That directly contradicts v4's own *"captures add findings …
   they never subtract."* → v5: **captured schema-valid findings are RETAINED and MERGED**; only the
   fresh report's **status** attributes completion.
3. **HIGH — "only BLOCKED gates" is factually wrong** (mine and the panel's error). A held PARTIAL is
   normally non-gating, **but structural remaining scope explicitly escalates to NEEDS DISCUSSION**
   (`swift-reviewer.md:423-430` — the very range v4 cited while asserting the opposite). Treating a
   persisted PARTIAL as unattributed stays right, but its findings **and** its structural `remaining`
   metadata are real safety information and must survive until a fresh report demonstrably covers that
   scope.
4. **HIGH — v4's cost claim was false.** A stale BLOCKED ratchets straight to NEEDS DISCUSSION **without**
   re-dispatch, so it creates no fresh capture and **does not self-clear** — staleness moves from false
   *approval* to repeatable false *discussion*. And "self-clearing" is false for non-BLOCKED states
   generally: a newly captured COMPLETE stays UNATTRIBUTED **by design**, so it needs an in-session
   report next time too. → v5 prices both honestly instead of claiming they evaporate.
5. **MEDIUM — failure semantics undefined.** Unexpected script failure, output/exit disagreement, or a
   non-empty roster yielding a silent exit 0 must themselves become missing-reviewer uncertainty, never
   fall through. Also: shell tests cannot prove a *model* assembled the right roster → workflow-level
   vectors required.

Also corrected: the contract line is **`AGENT_CONTRACTS.md:205`**, not `:230` (both reviewers).

## Round history — three designs died; read this before proposing a fourth idea

- **v1 (killed):** relax the regex + "last valid status line wins". A contract echo or a stray trailing
  `Status: COMPLETE` overrides a real BLOCKED.
- **v2 (killed):** asymmetric resolver (BLOCKED/PARTIAL anywhere, COMPLETE only from the canonical
  trailer) but still "neither present → `None`". Reviewers proved **by execution** that the prefix class
  still misses `| Status: BLOCKED |`, `+ Status: BLOCKED`, `1. Status: BLOCKED`,
  `<strong>Status:</strong> BLOCKED`, `Status：BLOCKED`, and both fence-container forms → all `None` →
  all read clean. **Parser hardening is whack-a-mole; the unsafe DEFAULT was the bug.**
- **v3 (killed):** make it structural — always write a sidecar, `UNKNOWN` when unparseable, gate UNKNOWN,
  keep face-value for a genuinely absent sidecar. Killed by five findings, all verified:
  1. *"Making the call unconditional does not make the write unconditional."* `_write_status`
     (`capture.py:370-393`) swallows `OSError/TypeError/ValueError` and reports nothing; findings publish
     **first** (`:465`), so a parsed BLOCKED `[]` lands while its sidecar does not. **I reproduced this**:
     unwritable dir → no sidecar, no exception.
  2. **Reached too late:** invalid fenced JSON returns at `:457` *before* status handling; `[]` is
     non-final (`:239-258`) so the slot is reused and the OLD `COMPLETE`+`[]` survives and is selected.
  3. `Outcome: BLOCKED` + `Status: COMPLETE if the review ran` → accepted as COMPLETE.
  4. **The absent/back-compat split is unimplementable:** pre-2328 absence, a failed write, a deleted
     sidecar, an unreadable sidecar and a corrupt sidecar are **mutually indistinguishable on disk**.
  5. `_clear_status` also swallows failures — clear+write both failing leaves a stale COMPLETE.

**The decisive finding (why every producer-side fix is fixing the wrong file):**
`context_latest_round_dir` (`scripts/lib/context.sh:119-134`, decisively `:130`
`[ -f "$d/$agent.json" ] || continue`) selects the **highest round holding the agent's `.json` and
silently skips rounds where the agent wrote nothing** — so absence at round N resolves to *presence* at
round N-1. **No producer-side artifact can signal anything on the path where the producer is failing**,
because the reader never sees the round the producer failed in.

## The invariant

> **A persisted capture may RATCHET a review toward caution. It may never CERTIFY completion.
> Only an in-session reviewer report — read by the orchestrator with its own eyes — can produce a clean
> pass.**

This inverts the problem. `extract_status` and its sidecar **leave the trust path entirely**; their
reliability stops being a *correctness* parameter and becomes a *cost* parameter. That is the escape from
the trap v1/v2/v3 each died in: all three tried to make the parser (or its write) reliable enough to be
**trusted**, and the reviewers proved by execution that neither is achievable.

**The bug's actual home is one paragraph of prose** — `agents/swift-reviewer.md:176-184`:
> *"status absent / unparseable / mismatched … → do not fail closed: take the findings at face value …"*

**That paragraph is COREDEV-2490. It is deleted.**

## The design

### 1. New `scripts/review/reviewer-roster.sh` (read-only)

Mirrors the shipped Item-5 precedent (`scripts/review/build-verify.sh` + `scripts/tests/test_build_verify.py`):
mechanical classification moves out of agent prose into unit-tested shell.

**Input:** stdin, one agent name per line — **only reviewers whose in-session report the orchestrator does
NOT hold.** Empty stdin (the normal path) ⇒ exit 0, no output. Names not in `VALID_AGENTS`
(`capture.py:53-59`) are rejected, never path-joined.

| On-disk state for an unresolved agent | Directive | Exit |
|---|---|---|
| Sidecar parses **AND** `agent` matches **AND** `status == "BLOCKED"` | `RATCHET <agent> BLOCKED <blockerDescription>` | 2 |
| **Everything else** — valid `COMPLETE`, valid `PARTIAL`, `UNKNOWN`, absent, corrupt, truncated, agent-mismatch, unreadable, pre-2328 round, `[]`, non-empty findings, **no round dir at all** | `UNATTRIBUTED <agent> <reason>` | 3 |

`<reason>` ∈ `complete-does-not-certify` · `partial-does-not-certify` · `no-sidecar` · `corrupt-sidecar` ·
`agent-mismatch` · `unknown-status` · `no-round-dir` · `unreadable`.

**The roster is the SINGLE reader of `<agent>.status` (R5-2).** Nothing else parses a sidecar, so
"trust the sidecar" prose cannot creep back into an agent file. Because it is the only reader, it must
**forward** any safety payload it finds, or that payload is unreachable — *"it cannot preserve safety
metadata it never sees."* So a PARTIAL emits its structural scope alongside the directive:

```
UNATTRIBUTED accessibility-auditor partial-does-not-certify
REMAINING    accessibility-auditor Compose/HTMLWebViewEditor.swift Compose/NativeRichTextEditor.swift
```
A `REMAINING` line is emitted **only** for a parsed PARTIAL whose `remaining` is a non-empty **string**
(the producer persists every status field as a capped string — `capture.py:362`
`cap(redact_pii(field[1]), STATUS_FIELD_CAP)`; it is **never** a list, and a non-string value is
malformed input that is dropped rather than coerced). It is always
paired with that agent's `UNATTRIBUTED` line, and never changes the exit code. It is *information for the
consumer to preserve*, never an attribution. The same applies to `RATCHET`'s `<blockerDescription>` —
already forwarded, same reason. (PII-redaction and the field cap are the writer's job and already
applied; the roster forwards bytes verbatim.)
Exit: `0` nothing to act on · `2` ratchet only · `3` ≥1 UNATTRIBUTED (dominates).
**The script never prints `TRUST`. By design no on-disk artifact earns it.**

**Failure semantics — every unexpected outcome is uncertainty, never a fall-through (R4 blocker 5):**
any exit code other than 0/2/3, output that disagrees with the exit code, a malformed line, or a
**non-empty** roster that somehow yields a silent exit 0 ⇒ treat every reviewer on that roster as the
missing-reviewer case → Needs Confirmation → **NEEDS DISCUSSION**. The script is a convenience for
classification; its *failure* must never be readable as "nothing to act on".

**Only BLOCKED ratchets.** The lattice is BLOCKED > PARTIAL > COMPLETE, and the truth is not on disk —
there is nothing to take a max against. BLOCKED is the sole rung that cannot be a *downgrade* of
anything, so honoring it is the only genuinely monotone move. `RATCHET … PARTIAL` **would be a
certification** ("this reviewer ran, partially — do not gate"), and a stale one can mask a real BLOCKED.
Widening UNATTRIBUTED to swallow PARTIAL costs nothing on the noise axis *by the spine's own argument*:
UNATTRIBUTED is **work, not an alert**.

> **Correction (R4 blocker 3 — v4 asserted the opposite and was wrong).** It is **NOT** true that "only
> BLOCKED gates". A held PARTIAL is *normally* a non-gating warning, but **structural remaining scope
> escalates it to NEEDS DISCUSSION** (`swift-reviewer.md:423-430`). That does not change the ratchet
> decision — a persisted PARTIAL still cannot certify, so it is still UNATTRIBUTED — but it **does** mean
> a persisted PARTIAL carries real safety payload (its findings + its `remaining` **string**). Hence the
> retain-and-merge rule above: we discard PARTIAL's **attribution**, never its **information**.

`context_latest_round_dir` is reused **as-is** — no freshness heuristic, no mtime, no "reject rounds older
than N". Freshness heuristics in the trust path are how v3's killer 2 got in; staleness is **defanged,
not detected**.

### 2. Consumer — `agents/swift-reviewer.md`

**Two paths exist, and R4 proved v4 conflated them. v5 names them:**

- **Path A — swift-reviewer spawns the five itself (the common case).** It holds each `Agent` tool result
  **in-session**: that IS the held report. Roster ⇒ **empty stdin ⇒ exit 0 ⇒ zero re-dispatch, zero
  added cost.** Reading the array rather than the prose for synthesis (`:354-357`) does **not** make it
  unattributed — the report was returned to this agent, in this session.
- **Path B — "already provided to you" (`:143-147`), an external orchestrator having run them.**
  Attribution is **transitive from the caller — but ONLY when the caller hands over a FULL HANDOFF**:
  the reviewer's report **including a readable `Status:`**, per the handoff contract at
  `agent-orchestration/SKILL.md:205` (prose + array + status). **A bare array is NOT a handoff**, no
  matter who supplied it: it carries no status, so nobody has vouched that the reviewer *ran*.
  Prompt-supplied bare arrays are **UNRESOLVED** and go on the roster.

> **Attribution is about who vouches THAT THE REVIEWER RAN — and the vouching is carried by the
> `Status:`, never by the array.** In-session `Agent` result → swift-reviewer vouches. A caller-supplied
> **full handoff with a readable status** → the caller vouches. A bare array — from disk **or from the
> prompt** — → **UNATTRIBUTED**. The array is evidence of *findings*; only a status is evidence of
> *completion*. Conflating the two is the entire bug.

> **R6 correction (codex, BLOCKER — and it was my own contradiction).** v5/v6-draft said "arrays handed
> to swift-reviewer in its prompt are attributed" while *also* saying "a bare JSON array is NOT a held
> report". Codex's vector needs no misbehaviour, only that contradiction: `security-reviewer` returns
> `BLOCKED` + `[]`; the external orchestrator passes only the five arrays; swift-reviewer follows
> "caller vouches", builds an **empty roster**, re-dispatches nothing, and reads five empty arrays as
> **clean**. The R4 contradictory-prose defect had survived in a new form, one level up. Resolved by the
> rule above: **the status is the attribution.** Nothing else is.

- **(a) REWRITE, do not merely delete (R4 blocker 1).**
  - **`:148-184`** — delete the face-value rule (`:176-184`), the "trust a `<agent>.status` only when it
    validates" paragraph, and the status-trusting prose. **KEEP a findings read**: the loop's
    `cat "$rd/$agent.json"` (`:166`) is the only mechanism that fetches pre-collected findings, and
    findings can only **add** (R4 blocker 2). It is re-scoped to *"collect candidate findings; they never
    certify"* and must stop silently swallowing a wholly-missing reviewer via `[ -n "$rd" ] || continue`
    (`:163`) — a missing round dir now goes **on the roster**.
  - **`:144-147`** — *"skip spawning … do not re-run them"* is rewritten: skipping the **spawn** is fine
    when the caller supplied a **full handoff including a readable `Status:`**; it is **not** licence to
    treat bare arrays — scavenged from disk **or handed over in the prompt** — as a
    completed review. An unattributed reviewer **is** re-dispatched, and this rule **supersedes** the
    do-not-re-run text.
  - **`:354-357`** — *"Work from the JSON arrays, not the prose reports … source of truth"* is rewritten:
    the arrays remain the source of truth **for findings, dedup and the verdict**; they are **never** the
    source of truth for **whether the reviewer ran**. That is what the `Status:`/roster decides.
  - Net: the surviving prose can no longer contradict the new rule, so no model has to choose between
    two instructions — codex's clean-pass vector requires exactly that choice, and it is removed.
- **(b) Step-2** calls the roster script (stdin = unresolved reviewers only), mirroring Step 4's shipped
  convention, and **echoes** `ROSTER=$?` (a shell var cannot survive the block — the COREDEV-2494 lesson).
- **(c) New Step-5 "Positive attribution" subsection**, immediately before "Read each reviewer's Output
  Contract status first" (`:406`):
  - **Roster** = the reviewers dispatched in Step 2 (all five, or the explicit subset per
    `agent-orchestration/SKILL.md` Rule 4). If you cannot name it, it is the five in `capture.py:53-59`.
  - **Attributed** = you hold the reviewer's **report** — its prose *and* its array. **A bare JSON array
    is NOT a held report**: if all you have is the array, the reviewer is UNRESOLVED. For a genuinely
    held report, read its `Status:` yourself and apply the existing `:414-430` handling — **unchanged**.
  - `RATCHET … BLOCKED` → existing BLOCKED handling: Needs Confirmation quoting `blockerDescription` →
    **NEEDS DISCUSSION**.
  - `UNATTRIBUTED` → **re-dispatch that one reviewer** via the `Agent` tool (Step 5's existing recovery
    ladder, `:392-402`). **At most one re-dispatch per reviewer per review** — keep a per-review dispatch
    ledger (reviewer → count) and **name each spawn in the report**, so the bound is auditable rather
    than asserted. Still no readable report → missing-reviewer uncertainty → Needs Confirmation →
    **NEEDS DISCUSSION**. **Not** `category: verification` (that family is reserved for checks the
    orchestrator itself ran).
  - **`:389` must consult the SAME ledger (R5-4).** Step 5's existing recovery paragraph independently
    commands another fresh run for unrecoverable findings — so an attribution retry that returns a
    readable status but malformed JSON currently licenses a **second** spawn, disproving "one
    re-dispatch each". Rewrite `:389` to check the ledger first: **one spawn per reviewer per review,
    whichever path asks for it.** (Bounded, not recursive either way — the capture hook is telemetry and
    never dispatches, `hooks/hooks.json:133-139` — but the bound must be true as written.)
  - **MERGE, never replace — WITHIN THIS REVIEW (R4 blocker 2; scope corrected at R5-1).** The fresh
    report supplies the **status** (the attribution). It does **NOT** supplant the captured findings:
    **retain every schema-valid captured finding and union it with the fresh report's array** (existing
    dedup applies). A fresh `COMPLETE` + `[]` from a reviewer that missed what the capture caught must
    **not** erase it *from this review's output*. Likewise a persisted **PARTIAL**'s findings *and* the
    `REMAINING` scope the roster forwarded are preserved until a fresh report demonstrably covers that
    scope — a held PARTIAL with structural remaining **does** escalate to NEEDS DISCUSSION (`:423-430`),
    so that metadata is safety information, not bookkeeping.
    > **Scope, stated exactly (R5-1).** The claim is: *captures add findings **within the review that
    > reads them**.* It is **NOT** "captures never subtract, ever". Across reviews the newest round
    > **supersedes** — that is what rounds are *for*, and unioning across rounds would resurrect every
    > finding that was legitimately **fixed** between rounds, forever. The unqualified v5 wording was
    > false; this is the true, narrower claim, and the difference is load-bearing rather than cosmetic.
  - **New fourth bullet** closing the gap left by deleting `:176-184`: *"No readable `Status:` in a report
    you hold → re-dispatch once, then treat as the missing-reviewer case → NEEDS DISCUSSION. Never face
    value."*
  - Carry the invariant in one sentence: *"A captured `[]` is never a clean pass, and a captured
    `COMPLETE` never certifies one. Captures add findings or add caution; they never subtract either."*

### 3. `AGENT_CONTRACTS.md:205`

Replace *"…an absent/corrupt/unrecognized sidecar degrades to face value (never a false fail-closed)"*
with: *"…a **BLOCKED** sidecar is honored (it can only ratchet toward caution); **every other on-disk
state — COMPLETE, PARTIAL, absent, corrupt, mismatched — is UNATTRIBUTED and the reviewer is
re-dispatched, never taken at face value** (COREDEV-2490)."*
`CHANGELOG.md` and `COREDEV-2328_REVIEWER_STATUS_CAPTURE_PLAN.md` carry the same phrase but are
**historical records and correctly stay untouched**.

### 4. `skills/agent-orchestration/SKILL.md`

The `- Status:` template (`:223-226`) is **untouched** — we do not change the parser, so list form keeps
working (verified: `- Status: COMPLETE` → `{'status': 'COMPLETE'}`). Add one clause to the
"All reviewers → swift-reviewer" prose: the persisted capture is **corroboration only**; an unattributed
reviewer is **re-dispatched, not assumed clean**.

### 5. `mcp/review-synthesizer/capture.py` — ZERO functional lines

One comment amendment at `:261-266` so producer and consumer docs cannot drift. The header's
*"Observe-only, fail-open"* stays **literally true — we now rely on it** — and gains: *"— and the consumer
only ever ratchets on it: a BLOCKED sidecar is honored; nothing on disk certifies (COREDEV-2490)."*
`_write_status`'s *"NEVER raises so it can't flip `capture()`'s already-successful written result"*
remains true and load-bearing.

> **Precisely which contracts move (R5-3 — v5 overclaimed here, and it was my error).**
> - **PRODUCER / capture contract: NOT reversed.** `capture.py`'s "Observe-only, fail-open" stays
>   literally true and is now *relied upon* — a best-effort write that silently fails is exactly what
>   this design expects and tolerates. Zero functional Python change. v3 reversed this; v6 does not.
> - **CONSUMER contract: DELIBERATELY reversed.** `AGENT_CONTRACTS.md:205`'s *"an absent/corrupt/
>   unrecognized sidecar degrades to face value (never a false fail-closed)"* is **the bug**, and
>   reversing it is the entire point of this ticket. Saying "no documented contract is reversed" was
>   simply false. It is amended in the same commit so the docs never describe a control the code no
>   longer implements — the exact defect class COREDEV-2493 just fixed.

## Back-compat: the split is DELETED, not implemented

v3 needed *"genuinely absent (pre-2328) → face value"* to be separable from *"current write failed →
gate"*, and the reviewers proved the five states are mutually indistinguishable. Here **all five, plus a
valid COMPLETE, plus a valid PARTIAL, plus a valid `[]`, collapse into UNATTRIBUTED.** Nothing needs to be
told apart, so nothing unimplementable is specified. **The design never asks a question the filesystem
cannot answer.**

### Cost, priced honestly (R4 blocker 4 — v4's claim here was false)

- **Path A (the common case): zero.** All five reports held in-session ⇒ empty roster ⇒ exit 0 ⇒ no
  re-dispatch. This is the alert-fatigue defence and it is asserted as a test.
- **Path B with a vouching caller: zero — but ONLY for a FULL HANDOFF.** A caller-supplied report
  **with a readable `Status:`** is attributed (the caller vouches that the reviewer ran). **Bare
  prompt-supplied arrays are UNATTRIBUTED** and cost one re-dispatch each — they carry no status, so
  nobody vouched. *(This sentence previously read "arrays supplied in-prompt are attributed", which was
  the exact losing rule the rest of v7 reverses — codex caught it surviving here at R7. The status is
  the attribution; the array never is.)*
- **Scavenged-from-disk reviewers: one re-dispatch each, every review.** v4 called this "self-clearing";
  **it is not.** A freshly captured COMPLETE stays UNATTRIBUTED **by design**, so the next review that
  scavenges instead of holding a report pays again. That is the deliberate price of the invariant: disk
  never certifies, so disk-only reviews always cost a re-dispatch. State it, don't hide it.
- **Stale BLOCKED: a repeatable false alert, not a false pass.** A stale BLOCKED ratchets straight to
  NEEDS DISCUSSION *without* re-dispatch, creates no fresh capture, and therefore **recurs** on every
  later review of that slug until a fresh capture lands. This is a real regression in *noise* traded for
  a real gain in *safety* (today the same staleness produces a false **approval**). Accepted knowingly.
  If it bites in practice, the fix is a follow-up (`RATCHET` could also re-dispatch to refresh) — not a
  freshness heuristic in the trust path, which is how v3's killer 2 got in.

## How v3's five killers die

1. **Best-effort write** → **closed by NON-RELIANCE.** A failed write leaves the sidecar absent; absent →
   UNATTRIBUTED → re-dispatch. My reproduction now produces a re-run, not a clean pass. This killer is
   *unfixable from the writer side by construction* — which is the proof the fix belongs in the consumer.
2. **Reached too late / stale slot** → the surviving artifact is `[]` + `COMPLETE`; **neither certifies**
   → re-dispatch → the fresh report decides.
3. **Manufactured COMPLETE** (`Outcome: BLOCKED` / `Status: COMPLETE if the review ran`) → a captured
   COMPLETE never certifies, so the vector is inert **on the disk path**. It remains live for the
   in-session read → **split out as COREDEV-2495** (High, live today).
4. **Unimplementable back-compat split** → deleted (above).
5. **`_clear_status` failure leaving a stale COMPLETE** → a stale COMPLETE is UNATTRIBUTED → re-dispatch.

## Non-goals / preserved invariants
- Findings artifact stays a **bare JSON list**; `synthesize._load`, `is_final_capture`, the secure-write
  path, PII redaction + caps, and the no-fence branch are untouched.
- `PARTIAL` stays non-gating for a **held report** (`:423-430`); only its *on-disk* reading changes.
- The parser is **not touched**. Recall (COREDEV-2496) and soundness (COREDEV-2495) are split out — under
  this spine recall is a cost knob, so it can be tuned later on evidence with no gate riding on it.

## Verification
- **`scripts/tests/test_reviewer_roster.py`** (mirrors `test_build_verify.py`, no Xcode/app needed) — a
  fabricated round dir per case: BLOCKED sidecar → `RATCHET`/exit 2; **COMPLETE → UNATTRIBUTED** ;
  **PARTIAL → UNATTRIBUTED**; absent / corrupt JSON / truncated / agent-mismatch / unknown status /
  no round dir / unreadable dir → `UNATTRIBUTED` + the right reason; empty stdin → exit 0 silent;
  invalid agent name → rejected, never path-joined (incl. `../` traversal); mixed roster → exit 3
  dominates exit 2; **the script never prints `TRUST`**.
- **The decisive one:** for every v3 killer above, assert the outcome is `UNATTRIBUTED` (→ re-dispatch),
  **never** a clean pass — including the reproduced unwritable-dir case.
- **Noise:** the normal path (all five reports held) ⇒ empty stdin ⇒ exit 0, **zero re-dispatches**. This
  is the alert-fatigue defence and must be asserted.
- **`REMAINING` forwarding (R5-2):** a parsed PARTIAL with a non-empty `remaining` **string** emits a
  `REMAINING` line
  paired with its `UNATTRIBUTED` line and does not change the exit code; a PARTIAL **without** one emits
  no `REMAINING`; a corrupt sidecar emits neither.
- **Workflow-level vectors (R5-5 — shell tests cannot prove a MODEL decided correctly):**
  1. **Caller-supplied BARE arrays ⇒ UNRESOLVED ⇒ re-dispatch** (assertion REVERSED at R6 — the v6-draft
     asserted the opposite and that assertion *was* the bug). Codex's exact vector: a `BLOCKED`
     reviewer's `[]` among five prompt-supplied bare arrays must **NOT** produce a clean pass. A
     caller-supplied **full handoff with a readable `Status:`** ⇒ attributed ⇒ **zero** re-dispatch.
     The distinguishing input is the **status**, not the array. Also assert the rewritten
     `:144-147`/`:354-357` never license "scavenged disk arrays = a completed review".
  2. **Retain-and-merge**, in-review: a captured non-empty finding + a fresh `COMPLETE`+`[]` ⇒ the
     captured finding **survives in this review's output**.
  3. **The shared retry ledger:** an attribution retry returning readable status + malformed JSON must
     **not** trigger a second spawn via `:389`.
  4. **Cross-review supersession is EXPECTED, not a bug** (R5-1): after a re-dispatch advances the round,
     the next review reads `[]`+`COMPLETE` ⇒ **UNATTRIBUTED ⇒ re-dispatch**, never a clean pass. Assert
     the *outcome* (no false clean), and assert that we do **not** union across rounds — a finding fixed
     between rounds must **not** resurface.
- **Adversarial verification** (Workflow, ≥2 attackers, the pattern that caught real holes in #38/#39 and
  killed v1–v4): (i) any filesystem/timing state where a BLOCKED-or-unknown reviewer still reads clean —
  now a *design* break, not a tuning miss; (ii) any state causing an unbounded or double re-dispatch;
  (iii) any way `REMAINING`/`blockerDescription` forwarding can be turned into an attribution.
- Full MCP suite + scripts suite + `shellcheck` green; `bash -n` under **bash 3.2** for the new script
  (`case`-in-`$( )` is a live trap here — it bit COREDEV-2492 *and* COREDEV-2494 today).

## Risk
**LOW-MEDIUM**, and materially lower than v1–v3. Zero producer/Python behaviour change; ~80 lines of new
read-only shell; one deleted prose paragraph; isolated and revertible (drop the Step-2 call and the
Step-5 subsection). The residual risk is **cost, not safety**: a pre-2328 or write-failed round costs one
re-dispatch. **What it does NOT cover, stated plainly:** kill-windows and concurrent same-round captures
remain (COREDEV-2328's own plan already concedes them) — this design does not claim two-file atomicity,
it claims those windows are **non-load-bearing** because nothing on disk certifies.
