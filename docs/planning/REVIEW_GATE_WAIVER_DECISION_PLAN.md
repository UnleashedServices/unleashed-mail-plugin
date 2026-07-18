# Plan Review Gate — the WAIVED path: wire it, or drop the claim?

**Status:** ✅ DECIDED — **Option B** (drop the scripted waiver). Both reviewers concurred (R1 codex
`APPROVE_WITH_NOTES` choosing B; R2 confirmed). Implemented on `feat/plugin-waiver-decision`.
**Epic:** COREDEV-2485 · **Ticket:** COREDEV-2493 · Branch `feat/plugin-waiver-decision`, **stacked on
`feat/plugin-workflow-usability` (#41)**, ultimately targeting `alpha`.

## Round history

**R1 — codex `APPROVE_WITH_NOTES`, and it chose Option B.** It also corrected the plan on three points,
all folded into v2 and all verified against the code before accepting:

1. **My central argument was overstated** (the most useful catch). I argued Option A creates a "false
   audit trail". Codex: *"Existing approval artifacts are already cooperative attestations: an
   adversarial agent able to write transcripts and invoke `write` could fabricate two approvals too.
   Option A would add a convenient, officially sanctioned bypass, but it would not introduce the gate's
   first forgeability."* Correct — I was implying the current artifact is trustworthy in a way it isn't.
   v2 drops that framing and rests B on **honest semantics, lower complexity, and this repo's low
   availability risk**.
2. **Blast radius was wrong** — v1 said "§2 only". A case-insensitive sweep (codex's point: don't grep
   only uppercase `WAIVED`) finds the promise repeated in **`skills/codex-review/SKILL.md:10`** and
   **`skills/gemini-review/SKILL.md:19`** ("Only the *user* may waive it… Never self-waive"). Four files
   carry waiver terminology, not one.
3. **`implement` never invokes `review-verdict.py verify`** — codex read `alpha` and found the gate
   inert. This **independently confirms** the Item-11 regression found by this session's post-merge
   audit; it is already fixed in **PR #41 / COREDEV-2492** (unmerged at the time codex reviewed). No
   further action here, but v2 no longer describes a call chain that `alpha` doesn't yet have.

**R1 — gemini: `Error: timeout waiting for response` (exit 1).** Not counted as approval, per §2 and
`review-synthesis`'s "a missing/empty transcript is never APPROVE". Cause: two concurrent `agy`
instances; a PTY-wrapped preflight ping right after returned `Pong!`, so the CLI is healthy. Re-run
serially for R2. *(Noted for the irony: the gate hit exactly the reviewer-unavailable scenario this plan
is about — and the fail-closed default worked. The recovery was to fix the invocation, not to waive.)*

## The problem: a documented escape hatch that does not exist

`AGENT_CONTRACTS.md` §2 ("Preflight & waiver") promises:

> The gate depends on the `agy` (gemini) and `codex` CLIs being installed and authenticated. On a fresh
> machine or in CI they may be absent — the gate must NOT silently pass, and **must NOT hard-wedge the
> dev loop with no escape**. […] **Waiver — explicit, scoped, recorded (never automatic):** only the
> **user** […] may waive an unavailable reviewer […] recorded in the Combined-verdict block as
> `WAIVED: <reviewer> | <reason> | <session/plan>`.

**Nothing in the chain implements any of it.** Verified on `alpha`:

| Component | WAIVED support |
|---|---|
| `AGENT_CONTRACTS.md` §2 | describes the marker + its rules |
| `skills/review-synthesis/SKILL.md` (emits the Combined block) | **zero mentions** — never parses or emits it |
| `scripts/review-verdict.py` (validates + persists) | **zero support**: `WAIVED` ∉ `VERDICTS`; `_quorum_problem` requires gemini **and** codex, each APPROVING |

So the contract is not merely aspirational — it is **contradicted**. A waived reviewer can never produce
an approving artifact, so `implement`'s Design Gate blocks forever: **exactly the hard-wedge §2 forbids.**

This must be resolved one way or the other. A safety contract that documents a control nobody implements
is worse than either alternative, because readers plan around a mechanism that isn't there.

## The core tension (why this needs a decision, not just an implementation)

§2's central requirement is **"only the user may waive — never an agent, never automatic."**

**No script can enforce that.** The agent is the process invoking `review-verdict.py`. Any flag a human
could type, the agent can type unprompted. A `WAIVED:` line in the artifact is therefore **attestation,
not enforcement**.

**But (R1 correction — this bounds the argument):** that is *already true of the whole gate*. An agent
able to write transcripts and invoke `write` can fabricate two approvals just as easily. The existing
artifact is a cooperative attestation too, and the PreToolUse-token approach that might have changed
that was dropped as over-engineering (R5). So Option A would **not** introduce the gate's first
forgeability — it would add a *convenient, officially sanctioned* bypass to a system that already relies
on cooperation. The case against A is therefore **not** "it breaks a trustworthy audit trail" (it
doesn't; there isn't one). It is narrower and honest:

- a sanctioned one-click waiver is far likelier to be taken than a fabrication is to be authored, and
- §2's stated guarantee ("only the user may waive") would be **written down as if enforced** while being
  unenforceable — the doc would misdescribe the system, which is the same class of defect this ticket
  exists to fix.

Codex (R1) also confirmed no practical unforgeable channel exists here: `disable-model-invocation` stops
skill invocation but not equivalent Bash; a TTY proves terminal attachment, not human presence (**this
repo's own PTY wrapper lets an agent create one**); env vars and human-created files are forgeable with
ordinary write access. A genuinely resistant design needs new trust infrastructure (an external signer
holding a key the agent can't reach, releasing a plan-digest-bound token on user presence) —
disproportionate for a single-developer, non-CI workflow.

## Option A — wire the waiver

Add `WAIVED` as a **reviewer status** (not a combined verdict); allow **at most one** waived reviewer with
the other **APPROVING**; require a non-empty reason; record it in the artifact; make `verify` print a loud
degraded-pass warning. Then teach `review-synthesis` to parse/emit the `WAIVED:` line and `brainstorm` to
mention it.

- **Pros:** honors §2 as written; the dev loop survives a missing CLI; a recorded waiver beats the
  realistic alternative (a wedged gate → human says "just skip it" → **nothing** recorded anywhere).
- **Cons:** creates a self-serve bypass button in the one place fail-closed matters; "user-authorized" is
  unenforceable, so §2 would document a guarantee the code cannot keep; adds surface area to a
  security-relevant script for a scenario this team has not actually hit.
- **Parity/blast radius:** `review-verdict.py` (+tests), `review-synthesis`, `brainstorm`, §2,
  `codex-review`, `gemini-review`.
- **Shape if chosen (R1, codex):** `verify` must **exit zero** on a valid waiver — otherwise it isn't an
  escape hatch at all — while printing a degraded-pass warning and forcing the combined verdict to
  `APPROVE_WITH_NOTES`; invalid / expired / double-waived / waiver-plus-rejection must exit non-zero.
  Note §2's **time/session scoping cannot currently be enforced**: `createdAt` is caller-supplied and
  optional (`review-verdict.py:141`), so expiry would need an internally generated timestamp/session
  binding. A one-reviewer gate is meaningful only as *"single review + user risk acceptance"*, never as
  a successful dual review — encoding it as an ordinary approving artifact invites exactly that
  confusion.

## Option B — drop the mechanical claim, keep the intent **(Recommended)**

Rewrite §2 to describe the escape that **actually exists and is genuinely user-authorized**: the gate is
fail-closed with **no scripted bypass**; if a reviewer CLI is unavailable the gate does not pass, and the
resolution is a **human decision made in conversation** — install/authenticate the CLI, run the review on
another machine, or the user explicitly directs the work outside the gated skill. Keep the preflight
guidance (it is real and useful) and keep "a missing transcript is never APPROVE".

- **Pros:** honest — the docs stop describing a control that doesn't exist; the escape is user-authorized
  **by construction** (a conversation is real consent in a way a flag never is); zero new bypass surface;
  smallest change; lowest complexity in a security-relevant script.
- **Cons:** reverses a deliberate design decision the team wrote down; a machine genuinely missing a CLI
  can't run `/implement` until a human intervenes.
- **Blast radius (corrected at R1 — v1 said "§2 only" and was wrong):** four files —
  `AGENT_CONTRACTS.md` §2, `skills/codex-review/SKILL.md:10`, `skills/gemini-review/SKILL.md:19`
  (both currently promise "Only the *user* may waive it… Never self-waive"), and the header note in
  `scripts/review-verdict.py` that forward-references "a future user-authorized waiver". `implement`
  should additionally state the recovery choices.

**Substantive §2 replacement (drafted by codex at R1, adopted):**

> If either reviewer is unavailable or unauthenticated, **stop**: a missing or empty transcript never
> counts as approval, and **no scripted waiver is recognized**. The **user** chooses the recovery —
> install/authenticate the CLI, obtain and capture the review on another machine, or explicitly direct
> work outside `/implement`. That last choice is a **workflow exception, not a passed Plan Review Gate**:
> record it as such in the plan's progress log and do **not** emit an approving Combined verdict. An
> agent may present these choices but must never select or infer the exception.

This keeps §2's real intent (never wedge with no way out; never silently pass) while removing the promise
no code can honor. The shape we want is "record the exception in the progress log **without** claiming the
gate passed."

> **Not an endorsement of `OCTO_ADOPTION_PLAN.md` as an exemplar.** An earlier draft cited it as the
> proven shape. It is the opposite: that plan excluded gemini and then declared **"GATE SATISFIED"** on
> codex alone — an exclusion *plus* a gate-passed claim, precisely what this decision forbids
> (`AGENT_CONTRACTS.md` §2 records the same correction). The "record the exception" half is worth
> keeping; OCTO's "and call the gate passed" half is the anti-pattern. The citation is removed to avoid
> holding it up as a model (full review, #42).

## Recommendation — **Option B** (codex concurred at R1)

§2's "no escape" concern is real but already satisfied: the escape is the human. Option A's escape is a
flag the agent can set itself, which adds the *appearance* of authorization rather than authorization.
Option B keeps the intent (never wedge with no way out; never silently pass) while removing a promise no
code can honor.

**The counter-argument, and why it loses.** In practice a wedged gate gets bypassed by a human saying
"skip it", leaving no record — whereas Option A leaves one. R1 (codex) answered this directly and
convincingly: *"Option B can preserve a record without claiming the gate passed"* — record the exception
in the plan's progress log (the audit record), **without** the gate-passed claim (which OCTO wrongly
made — see the note above). The two goods are separable, so
we do not have to buy a sanctioned bypass to get an audit record. **This is the argument that settles the
decision** — not the (overstated) false-audit-trail framing v1 leaned on.

## Decision criteria for the reviewers

1. Is "user-authorized" enforceable in **any** way I've missed (something an agent structurally cannot
   forge — an env var it can't set, an interactive TTY prompt, a signed token)? If yes, Option A's
   objection weakens and A likely wins.
2. Which failure is worse for **this** repo: a wedged gate on a CLI-less machine (A solves), or a
   forgeable `WAIVED:` line that reads as human-authorized (B solves)?
3. Does Option B leave `implement` genuinely unusable in any **realistic** setup here — noting CI does not
   run `/implement`, and the one dev machine has both CLIs installed and authenticated?
4. If Option A: is "at most one waived, the other must APPROVE, reason required, loud warning" the right
   shape — or is any waiver too much?

## Verification (either option)
- `scripts/tests/` suite green; assembly + hooks + version-sync validators green.
- **Option A only:** tests that both-waived is rejected, a waived+REQUEST_CHANGES pair is rejected, a
  reason is required, and `verify` exits non-zero for any waiver shape §2 forbids; plus an adversarial
  pass (the pattern that caught real holes in #38/#39) attacking the waiver as a quorum bypass.
- **Option B only:** a **case-insensitive** sweep for *all* waiver terminology — `grep -rniE 'waiv'`, not
  just uppercase `WAIVED` — proves no stale promise survives outside a historical note. (v1's uppercase
  grep is precisely what produced the wrong blast radius; the check must not repeat the bug it missed.)
  Confirm all four sites are updated: §2, `codex-review:10`, `gemini-review:19`, `review-verdict.py`'s
  header, plus `implement`'s recovery text.

## Risk
**LOW either way** in code terms — the risk is the **decision**, not the diff. Option A's risk is a
weakened gate; Option B's is a contract edit the team may not want. Both are cheaply reversible; the
current contradicted state is the only genuinely bad option.
