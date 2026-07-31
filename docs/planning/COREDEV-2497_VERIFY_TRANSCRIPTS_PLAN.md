# COREDEV-2497 — `verify` must re-check the transcripts it approved

**Status:** Planning — **round 17 gated** (**both arms, one finding**). Round 16's narrowing note was placed **immediately below a sentence making the exact claim it narrows** — "re-opening becomes structurally unavailable inside `_digest_transcript_fd`". Five operative sites now narrowed: the invariants constrain the **interface**, not the body; **ARCH-2** establishes one seam call with an unchanged argument, **not** one resolution; ARCH-3's "module globals are irrelevant" is qualified to the fixtures' own verdicts. **Both arms independently re-derived the residue set with reachability AND discrimination and confirmed 2, 5b, 6b**, plus the counts (16 rows / 17 mutants / 13 cases). *A claim that a propagation is complete is not a propagation.* See §24. Previously — **round 16 gated** (**both arms `REQUEST_CHANGES`**). Round 15's reopening of row 2 **held**, and both arms then found the plan still **over-reads ARCH-1** everywhere else: a parameter-list check bounds the *interface*, never the *body*, and §6.0 row 2 is the plan's own counterexample (path smuggled through module state keyed by the fd). Every operative ARCH-1 claim is narrowed. **codex supplied a full branch-reachability re-derivation of all sixteen rows — the first end-to-end check of this table — and it confirms residues 2, 5b, 6b.** New method rule: **reachability and discrimination are separate requirements** (row 6b reached its branch and still could not be told apart). See §23. Previously — **round 15 gated — A CORRECTION REVERSED.** Round 14 closed §6.0 row 2 on a codex finding; round 15 **reopens** it, with **codex reversing itself** and gemini reaching the same place independently. I18 never reaches the **success branch** a post-hash probe runs on, *and* ARCH-1 inspects only the parameter list — so the path can be smuggled through module state and the probe can live **inside** the helper I18 stubs away. Residues are back to **three (2, 5b, 6b)**. The method lesson: **a re-derivation must establish BRANCH REACHABILITY, not just fixture level.** See §22. Previously — **round 14 gated** (**gemini `APPROVE` · codex `REQUEST_CHANGES` 1 High**). **Row 2 is closed too**: ARCH-1 makes the helper **fd-only**, so its `Path.open()` probe cannot be inside the helper — it is caller-side, and I18's zero-path-reads limb rejects it. Residues are now **5b and 6b** — two. **Four consecutive rounds, four residue corrections, none of which needed a new proof** — only a re-reading of proofs already present (I18 r7, C15 r11, C4a/C4b r4, ARCH-1 r5). See §21. Previously — **round 13 gated** (**both arms `REQUEST_CHANGES`, same High**). **Row 5b was over-broad**: C4a closes its symlink limb (differing target bytes → digest mismatch, not the exact `SYMLINK` message) and C4b closes its not-regular limb (`io.open` lacks `O_NONBLOCK` → blocks → the timeout fires). Row 5 is now split **four** ways — 5a permission (C15), **5b missing (the only genuinely unreachable limb)**, 5c symlink (C4a), 5d not-regular (C4b); count 14 → 16. **C4a and C4b are not new — they date from round 4, and row 5 had simply never been checked against them.** The standing rule is therefore *re-derive every residue against the WHOLE proof set*. See §20. Previously — **round 12 gated** (**gemini `APPROVE` · codex `REQUEST_CHANGES` 1 High**) — and the split verdict is the point: gemini approved with zero findings after confirming round 11's re-classification row by row, while codex found that **C15, added in round 11, closes row 5's permission limb**. Row 5 is now split **5a** (CLOSED by C15) / **5b** (accepted); residues stay three but are **2, 5b, 6b**. Twice in two rounds a newly added proof has invalidated a classification made before it existed — *a proof added is a classification invalidated.* See §19. Previously — **round 11 gated** (**gemini `REQUEST_CHANGES` ×2 High · codex `REQUEST_CHANGES`
1 High, 2 Medium, 1 Low**). Round 11 **inverts** the round-9/10 defect: instead of a closure claim that
outran the fixtures, the `ACCEPTED-NOT-CLOSED` set **outlived the fixture that closed it**. **I18 is a
caller-level test** (added round 7) and its two-limbed oracle — *caller fails* **and** *zero path reads* —
closes §6.0 rows **1**, **6a**, **7**, row **9's caller half** and mutant **I12b**; residues drop
**six → three** (rows 2, 5, 6b) and row 6 is split. Round 10's I12 split had also never reached §6's
mutant preamble or C12's pairing; and C12 alone cannot reject `st_size`/`getsize` at all — **F2** does,
per the plan's own measurement at `:1017`. The mandated **`DENIED`** cause had no case and no mutant for
seven rounds: **C15/I19** added, so counts are now **17 mutants / 13 cases**. See §18.
Previously — round 10 gated (**gemini REQUEST_CHANGES / codex REQUEST_CHANGES**), and the
High was again unanimous: **round 9's narrowing was still not fully propagated** — §6.0 **row 9** (and,
per codex, **row 5**) still credited closure to mechanisms that never reach a caller. Both rows are now
`ACCEPTED-NOT-CLOSED`; **I12 is split a/b** exactly as I16 was, because its caller half had no live
mechanism; C9's "THE PROOF" bullet is **qualified to the helper** rather than claiming end-to-end
closure; and I18's short-read arrangement now returns **`(D, 0)`** instead of a positive count that
inverted §4.1's own contract. See §17. Previously — round 9 gated
(**gemini REQUEST_CHANGES ×4 / codex REQUEST_CHANGES ×3**), and
the finding was unanimous: **round 8's narrowing was not propagated**. Six rows are now marked
**accepted-not-closed**, **F3 is restored** to ARCH-3's body (it had been dropped while §7 still mandated
it), and every remaining F5/F5b reference is removed from operative text. See §16. Previously — round 8
gated (**gemini REQUEST_CHANGES ×4 / codex REQUEST_CHANGES ×5**), and
the **maintainer has decided §8 Q8: NARROW THE GUARANTEE.** Both reviewers independently reached the same
answer. F5/F5b are **removed from the gating suite**; F1–F4 stay; §3 now states plainly what this plan
does **not** prove. See §15. Rounds 4-17 are in §11-§24.
**Ticket:** `COREDEV-2497` (Epic `COREDEV-2485`)
**Split out on 2026-07-30 (maintainer decision):** `COREDEV-2618` (verdict-token cross-check) ·
`COREDEV-2619` (per-run transcript paths). **This plan is now §4.1 + §4.2 only.**
**Sequencing:** `COREDEV-2619` should land **first** — see §7.
**Measured against:** HEAD `b2496a8` (v2.6.4). Worktree `.claude/worktrees/opus5-review`.
**Last Updated:** 2026-07-31 (round 17, post-gate revision — all five invariant overclaim sites narrowed)

---

## 0. Why this plan was rescoped, and what it cost

Rounds 1 and 2 each found more than the previous round claimed existed — **4 findings, then 8, then an
adversarial sweep returned 37.** That is the same signal as `COREDEV-2597`, where rounds 3 and 4 each
found more redactor divergences than the round before had claimed were possible, and where iterating was
abandoned for a model-based sweep. Iterating a fourth time would have been the wrong move.

The sweep also showed two of the four original sections are not the small additions this ticket assumed:

- **§4.3 (verdict cross-check) → `COREDEV-2618`.** As specified it accepts a verdict the reviewer
  **quoted** rather than emitted, rejects `APPROVE_WITH_NITS` (which `review-synthesis` *mandates* be
  recorded as `APPROVE_WITH_NOTES`), is case-sensitive on a label the shipped gemini prompt writes as
  `Verdict:`, and fails closed on absent tokens that `review-synthesis:45-48` explicitly licenses via
  prose inference. Fixing it means changing three shipped skills' contracts.
- **§4.4 (per-run paths) → `COREDEV-2619`.** 20 sites across 6 files, including two `allowed-tools`
  literal-prefix grants that a naive migration silently breaks.

**The cost, stated plainly because it is this plan's most important evidence.** Round 2's headline
measurement cited the **wrong file**. I reported "the codex transcript of this plan's round-1 review" as
**769,988 bytes**, having read `/tmp/codex-out.txt` — which by then held a **LumaWake** plan review (**628**
matches for `lumawake`, **zero** for `COREDEV-2497`), because another project's gate round had
overwritten the shared fixed path. The real transcript is `/tmp/rev/2497r1-codex.txt`, **512,723 bytes**,
25 mentions of the ticket. Round 2 then "corrected" 512,723 → 769,988, **inverting the truth**, and both
reviewers assessed a plan whose central number pointed at another project's file.

> That is `COREDEV-2619`'s justification, produced by accident: the collision is not hypothetical, it
> silently corrupted this gate's own evidence and survived two review rounds. **§4.1's conclusion is
> unaffected** — 512,723 is still 7.8× the 65,536 cap, and
> `_read_regular_file('/tmp/rev/2497r1-codex.txt')` returns `None` (executed).

## 1. Context — reproduced, not inherited

The verdict artifact is **forgeable**. Reproduced in 3 attempts: a hand-written artifact carrying
fabricated transcript digests and paths that do not exist returns `GATE OK — APPROVE`, exit 0.

`write` is well defended (digest binding, distinct-transcript rule, `O_NOFOLLOW` writes, snapshot
binding). The gap is that **`verify` never re-checks the transcript files** — it validates the artifact's
*shape* and the *plan* digest, and takes the transcript fields on trust.

## 2. The defect, stated exactly

`cmd_verify` (`scripts/review-verdict.py:555`) re-derives the plan identity and digest (`:736-748`) and
calls `_quorum_problem` at **`:728`** — the function is defined at **`:74`** and runs to **`:200`** (the
next top-level `def` is `_sha256_bytes` at `:202`). Its checks span
`:84-199`: reviewer **count/shape** (`:84`), duplicate and stray **names** (`:86`, `:95`), **status
membership** (`:99-100`), the empty-file hash (`:121-122`), digest **syntax** (`:144`), and — through the
nested `_provenance` helper (`:155`) — that each reviewer carries a **distinct** `transcriptPath`,
`captureId` and `transcriptSha256` (`:174-199`). Every one of those provenance checks reads the artifact's
own fields; **none of them opens a transcript.** It **never resolves
`transcriptPath`** — the only filesystem calls in `cmd_verify`'s body touch the plan and the artifact
(`:557`, `:562`, `:564`, `:567`, `:747`) — so:

> **Round 4 correction.** Earlier drafts cited `_quorum_problem` as `:99`, which is neither its
> definition nor its call site but one line *inside* it. gemini reported this citation as verified.
> Eighth of the class §9 tracks.

- a `transcriptPath` that does not exist passes;
- a transcript modified or replaced after approval passes;
- a `transcriptSha256` that never matched anything passes, provided it is 64 hex characters and not the
  empty-file hash.

The ticket's framing ("verify never checks the transcripts") is slightly too strong — `_quorum_problem`
does run there. This is the precise version; the imprecise one sends an implementer to the wrong
function.

## 3. Guiding principle, and the ceiling

Re-checking the transcripts raises the **cost** of forgery. It is not a boundary: **anyone who can write
`docs/planning/.verdicts/` can also write transcript files.** Say so in the code and the CHANGELOG, so
nobody later reads this as making the gate unforgeable.

**A measured floor on that ceiling:** a **17-byte** file (`VERDICT: APPROVE\n`) is non-empty, has a real
digest, and satisfies every check this plan adds — measured on two real files under `/tmp/rev/`. So the
forger's remaining work is *17 bytes per reviewer*, not zero.

### 3.1 — What this plan does NOT prove (maintainer decision, round 8)

**This ticket is a consistency and provenance hardening. It is not a security boundary, and it does not
prove that the implementation reads each transcript in a single forward pass.**

Eight rounds established that the single-pass property is observable only in three ways, and that each
is unavailable here:

| route | why it fails |
|---|---|
| **instrumentation** (patch `os.open`/`lseek`/`io`) | routable around — a file-object `seek` never reaches `os.lseek`, `io.FileIO` is an immutable C type, a cached alias bypasses the wrapper *and* false-rejects correct code. Rounds 5-6, executed |
| **a non-production fixture** (pipe, non-zero offset) | an implementation can branch on production's shape and take the correct path only when tested. Round 7, executed |
| **a race at production configuration** (F5) | defeated outright by a *stable multi-pass* reader that retries until two reads agree; and its trial statistics are neither stationary nor independent, so no finite trial count bounds the false-pass rate. Round 8, codex |

**So the guarantee is narrowed rather than faked.** `verify` will resolve and re-digest every transcript,
per reviewer entry, fail closed with distinct causes, and reject every defect F1–F4 catch. It will **not**
detect an implementation that reads a transcript twice. Given §3's ceiling that is an acceptable trade:
the attacker who could exploit a two-pass race already has the strictly easier 17-byte forgery above.

**The CHANGELOG must say this** (§7 step 6). A reader who sees only the ticket title will otherwise assume
a boundary that does not exist.

## 4. Findings, fixes, and proofs

### 4.1 — `verify` does not resolve `transcriptPath` (High)

**Do NOT reuse `_read_regular_file`.** It is a UTF-8 text reader capped at 65,536 **characters**
(`scripts/review-verdict.py:211`, returning `None` past `_MAX_TRUSTED_READ_BYTES`). Executed against the
real round-1 codex transcript (512,723 bytes): returns `None`. Reusing it would reject *every legitimate
codex review* — the fix breaking the gate it repairs.

> **The blocker is the size cap alone.** Both round-1 transcripts are valid UTF-8. Do not justify this
> change on encoding grounds; non-UTF-8 survives only as a *defensive* case (C5b).

**FACTOR, do not rewrite — and name the seam.** `_read_regular_file`'s prologue is correct and
expensively earned: atomic `O_NOFOLLOW` symlink refusal (no `islink()`-then-open TOCTOU window),
`O_NONBLOCK` so a planted FIFO cannot block, and an `fstat` `S_ISREG` check — each landed in a named
round of `COREDEV-2503`'s review. A hand-rolled replacement would silently drop them.

1. Extract the prologue as **`_open_regular_fd(path) -> tuple[int | None, Cause]`** — a *stable
   module-level name*, so the single-descriptor property has a test seam. Round 2 described this split
   but never named it, which is why no case could pin it. **The typed `Cause` is mandatory** (ARCH-2);
   round 7 caught this step still specifying the bare `int | None` form the round-6 rewrite replaced.
2. `_read_regular_file` keeps its decode + cap epilogue **unchanged**, for the two sidecars it guards.
3. **MANDATORY SIGNATURE — not a preference.** The digest routine is
   **`_digest_transcript_fd(fd: int) -> tuple[str, int]`**: it takes the raw descriptor and **nothing
   else**. No path parameter, no opener parameter, no default-bound callable, no keyword fallback. It
   streams raw bytes through `hashlib` in **one forward pass**: no cap, no decode, no seek, no re-read,
   **no re-open**. It returns the hex digest **and the number of bytes actually streamed**.
4. **The streamed count — not `st_size` — is the sole basis for the "empty" diagnosis.** Use the
   `fstat` for the `S_ISREG` check only. This propagates §8 Q3's round-3 answer, which earlier drafts
   recorded as adopted while §4.1 and I10 still specified `st_size`; a shrink/grow race is precisely
   when the two disagree and the streamed count is the truthful one.
5. **No second resolution of the recorded path, on any branch.** Once `transcriptPath` has been opened
   through the seam, the *name* must never be touched again — not by `os.path.exists`, `os.path.getsize`,
   `os.stat`, `os.lstat`, `os.path.realpath`, `open`, `io.open` or `pathlib`, and not on the failure
   branch to "classify the cause", not on a retry, and not as a short-read fallback. **No retry on digest
   mismatch and no short-read fallback exist at all** — round 7 showed a correct helper can sit behind a
   caller that reopens on mismatch and passes every fixture, so the prohibition must be stated as a
   contract and tested at the caller level by **I18's deterministic red-branch test**, not inferred. *(Round 7: this step previously claimed
   "§6's ARCH-1 invariant asserts this at the source level" — source inspection was deleted in round 5.)*
6. **Never normalise the recorded path before opening it.** `os.path.realpath()` (or any resolve-then-open
   split) performs exactly the lookup-then-open sequence `O_NOFOLLOW` exists to eliminate, leaving the
   flag decorative. Open the recorded string as given.

**Correction to round 2, which misstated the regression risk.** `_read_regular_file` does **not** guard
`planPath`. Executed — it has exactly **two** callers: `:385` (the `captureId` sidecar) and `:480` (the
reviewed-digest sidecar). Plan identity and digest use `_plan_identity` + `_sha256_bytes` (`:747`) and
never touch it. **Regression duty:** both sidecar paths must keep the capped decode, and two existing
tests must be handled explicitly — see §4.5.

**Fail closed with a DISTINCT message per cause.** "Transcript missing", "transcript is empty" and
"transcript changed since approval" imply different recoveries; one message conflates them, and a shared
message makes the empty-check unfalsifiable (see I10).

### 4.2 — Non-approving artifacts must not be tightened (Medium)

`_quorum_problem` deliberately skips non-approving verdicts, because a `REQUEST_CHANGES` artifact records
*whatever ran* and is never gate-passing. **§4.1's checks must skip them too.**

Getting this wrong breaks the recovery path: a reviewer that produced an empty transcript is recorded
`MISSING`, and the operator's next step is reading that artifact. Making it unreadable because a
transcript is empty removes the diagnosis while changing no security property.

**This is a property of §4.1, not separate work** — §7 lands it in the same step, with tests.

### 4.3 / 4.4 — moved out

→ **`COREDEV-2618`** (verdict-token cross-check) and **`COREDEV-2619`** (per-run transcript paths). Both
carry the measured evidence from this plan's sweep. Do **not** re-add either here; 2619 is a prerequisite
(§7).

### 4.5 — One existing test breaks, and the naive repair guts the fix (High)

Round 2's regression duty said "every existing `_read_regular_file` test must still pass" without naming
anything. **One** test breaks under §4.1 — (a) below. (b) was moved to `COREDEV-2618` in round 3 and is
retained here only as the record of why; **this ticket has exactly one test repair**, and §7 step 4 says
so (round 4 caught it still ordering "two").

**(a) `test_uppercase_and_padded_digests_are_normalized_not_rejected`
(`scripts/tests/test_review_verdict.py:123-141`).** After a legitimate `_write`, it rewrites
`transcriptSha256` to `"A"*64` and `" " + "a"*64 + " "`, sets reviewer 1's to `"b"*64`, and asserts
`returncode == 0`. Under §4.1 those digests no longer match the fixture transcripts, so **verify fails
and this test breaks.** Its purpose is legitimate — proving the hex check is not over-strict, because a
false GATE FAILED is its own outage.

> **The trap:** the path of least resistance is to loosen the digest comparison, which guts §4.1
> entirely. **The correct repair** keeps the test's purpose — prove the hex check is not over-strict —
> while satisfying equality.

**Round 4 rewrote this repair, because the round-3 version was not executable.** It said "set the
recorded digest to the real digest of the fixture transcript, uppercased and space-padded
(`_sha256_bytes(self.tx).upper()`)". Three defects, all confirmed by opening the file:

1. **`_sha256_bytes` is not reachable from the test module.** It appears **zero** times in
   `scripts/tests/test_review_verdict.py`, which drives the script as a **subprocess** (`SCRIPT`, `:10`)
   and imports only `json, os, stat, subprocess, sys, tempfile, unittest` (`:2-8`). The prescribed call
   would `NameError`.
2. **`.upper()` alone drops half the test's purpose.** The test asserts **two** forms — `"A"*64` *and*
   `" " + "a"*64 + " "`. Uppercasing exercises case; nothing exercises padding.
3. **It repairs one reviewer and leaves the other broken.** `:137` is
   `r["transcriptSha256"] = good if i == 0 else "b" * 64` — the loop overwrites **both** entries.
   Reviewer 1's `"b"*64` is equally fabricated and equally fails a §4.1 re-digest of `tx2` (whose real
   digest is `f5edc4ed…`), so verify still fails and the test still breaks.

> **The correct repair, stated so it can be executed.** Compute each reviewer's digest the way the
> test already gets everything else — from the artifact the legitimate `_write` just produced. Read the
> two recorded digests out of the JSON, then write back **transforms of each reviewer's own real
> digest**: reviewer 0 gets `recorded0.upper()` in one subtest and `" " + recorded0 + " "` in the other,
> and reviewer 1 keeps `recorded1` **unchanged**. Both forms are still "a real digest in a different
> skin", both still prove normalisation, and neither fabricates a value that §4.1 must reject.

**(b) The default fixture's status/transcript mismatch → MOVED to `COREDEV-2618`.** Round 3 was right on
both counts. `self.tx2` ends `VERDICT: APPROVE` while `_write`'s default records
`codex=APPROVE_WITH_NOTES` — but it **does not break under §4.1** (the digests still match; only a verdict
*token* comparison would care), so it is 2618 preparation, not this ticket's work. And the proposed repair
would not have achieved self-consistency anyway: many tests pair `codex=APPROVE` with `tx2`, so changing
`tx2` to end `APPROVE_WITH_NOTES` would simply move the inconsistency onto those. Recorded on
`COREDEV-2618`, which has to decide the whole vocabulary anyway.

> **Round 4 corrected the evidence for that conclusion — it was wrong in both directions.** The claim
> was "**five** tests explicitly pair `codex=APPROVE` with `tx2` (`:66`, `:831`, `:904`, `:909`,
> `:989`)". Measured, with each line printed from the file:
>
> - **`:66` and `:909` attach no transcript at all.** Both are direct `run("write", …)` calls passing a
>   bare `"codex=APPROVE"`, and both assert `returncode != 0` — `:66` is
>   `test_approving_artifact_requires_a_transcript_per_reviewer`, `:909` is
>   `test_missing_plan_on_write_rejected`. `tx2` is never involved. Two of the five cited sites are not
>   pairings.
> - **`:904`** does pass `tx2` to codex via `_write`, but the run aborts on `gemini=MAYBE` before an
>   approving pairing is exercised.
> - Of the five cited, **`:831` and `:989`** are the ones that actually exercise it.
> - **Nine uncited sites pair explicitly**, via `codex=APPROVE:{self.tx2}`: `:87`, `:213`, `:229`,
>   `:518`, `:520`, `:560`, `:796`, `:807`, `:1060`.
>
> The **conclusion is unchanged and in fact strengthened** — there are far more than five — but the
> count and four of the five citations were not evidence. gemini reported all five as verified.

**The sidecar regression inventory — completed in round 4.** The prologue extraction must leave every
test that pins `_read_regular_file`'s behaviour green. Round 3 named only the two **symlink** tests, which
cover just one of the three properties §4.1 promises to preserve:

| test | line | property it pins |
|---|---|---|
| `test_a_symlinked_captureid_sidecar_is_ignored_not_trusted` | `:200` | `O_NOFOLLOW` (captureId sidecar) |
| `test_symlinked_snapshot_sidecar_is_ignored` | `:757` | `O_NOFOLLOW` (snapshot sidecar) |
| `test_an_oversized_captureid_sidecar_is_refused_not_trusted` | `:218` | the 65,536-char **cap** — the epilogue §4.1 keeps unchanged |
| `test_fifo_snapshot_sidecar_is_ignored` | `:773` | `O_NONBLOCK` + `S_ISREG` — the FIFO refusal |
| `test_invalid_utf8_snapshot_sidecar_does_not_traceback` | `:811` | the **decode** epilogue |

All five must stay green. The last three are the ones that actually exercise the cap, the non-blocking
regular-file check and the decode — precisely the properties a hand-rolled replacement would drop.

> **Round 5: `:773` does not safely pin `O_NONBLOCK`, and this must be fixed as part of step 2.** The
> shared subprocess helper `run()` (`scripts/tests/test_review_verdict.py:13-15`) passes **no timeout**,
> and the string `timeout` appears **zero** times in the whole module (measured). So a build that drops
> `O_NONBLOCK` **blocks inside `os.open`** before any assertion runs: the test hangs instead of failing.
> That is the same "a hang is not an assertion" defect this plan states for C4b — present in the existing
> test the plan is relying on. **Give `run()` a bounded timeout** and assert the FIFO cases on their
> message, not merely on exit status.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The fix is read as making the gate unforgeable | **High** | §3's ceiling in code + CHANGELOG, with the measured 17-byte floor |
| A legitimate large or non-UTF-8 transcript is rejected — the fix worse than the defect | **High** | C5's two halves must **PASS**; I6 is the mutant that reintroduces the cap |
| The digest check is silently gutted while repairing §4.5(a) | **High** | §4.5 names the trap and the correct repair; C2c must FAIL for any C-case green to mean anything |
| Tightening breaks the non-approving recovery path | Medium | §4.2 + C8, and **C11** for the case-sensitivity variant |
| A validate-then-reopen implementation ships green | **Accepted, not closed** | **§3.1 states this plainly.** ARCH-1 + ARCH-2's typed cause + F1-F4 + **I18** reject every defect found in rounds 4-7 **except (a)** a two-pass reader and **(b)** three residues §6.0 records as `ACCEPTED-NOT-CLOSED` — rows **2**, **5b** and **6b**. Eight rounds showed the single-pass property is not provable by instrumentation, by a non-production fixture, or by a race — so the plan narrows the guarantee instead of claiming one. *(Round 11: this row previously listed **six** residues — rows 1, 2, 5, 6, 7 and row 9's caller half — on the stated ground that **"no fixture exercises a caller."** That ground was false from round 7 onward: **I18 is a caller-level fixture**, and its two-limbed oracle closes rows 1, 6a, 7 and row 9's caller half. The residue set was never re-derived after the fixture that shrank it was added, so the plan under-claimed its own coverage for four rounds — the mirror image of the over-claiming this section exists to prevent, and equally a defect.)* |
| Factoring regresses the sidecars | Medium | Epilogue untouched; §4.5 now names **all five** tests — `:200`, `:218`, `:757`, `:773`, `:811` — not just the two symlink ones |
| The whole change is inert because tests only cover `write` | **High** | Every §4.1 test must mutate the transcript on disk **between** `write` and `verify` — see §6's trap |
| **The proof set is defeated again in round 5** | **High** | §6.0's structural invariants **constrain the helper's INTERFACE** — they do not seal its body *(round 17)*. §3.1 accepts the caller-side residue; **three** §6.0 rows are marked accepted-not-closed — **2**, **5b** and 6b *(round 11: was six; I18 closes 1, 6a, 7 and 9's caller half. Round 12: row 5 split — C15 closes its permission limb 5a)* |

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

Baselines at `2dc7f5c`: `test-hooks.sh` **304**, synthesizer **222**, scripts **312**, counts
`21/21/0/1`, hook events **10**. Floors, not equalities — re-derive at implementation time and print
`pwd` + `git rev-parse HEAD` beside any measurement.

**Every fix needs a mutation proof that rejects a plausible wrong implementation, not only a revert.**

### 6.0 — Why this section is structured differently now (round 4)

**Enumerating behavioural cases has failed four times.** Round 2's sixteen cases fell to
validate-then-reopen. Round 3 found C9a vacuous. Round 4's sweep — three independent adversarial passes,
each building a runnable harness that re-creates C1–C10 and running ~20 candidate implementations
against it — found **12 distinct wrong implementations that pass every enumerated mutant and case**,
executed, not argued. Both gate reviewers independently found a thirteenth.

The reason is a property of the technique, and it generalises:

> **C9a catches a re-open only if the re-opened bytes feed the digest *and* the read happens after the
> seam call. C9b catches a re-open only if it is routed through the `os.open` or `builtins.open` names.
> Everything else is invisible** — path resolutions that are not opens (`os.path.exists`,
> `os.path.getsize`, `os.lstat`, `os.path.realpath`), opens routed elsewhere (`pathlib.Path.open`, a
> cached `io.open`), reads that precede the seam, and re-opens hidden on a branch that a green-path test
> never takes (retry-on-mismatch, short-read fallback, failure-path re-classification).

Adding a case per escape is the move that produced rounds 2, 3 and 4. **So the class is addressed
structurally instead** — **constrained at the helper's interface**, not closed end-to-end: per §3.1 the
invariants bind `_digest_transcript_fd`'s **signature and seam**, not its body, and the residues they
cannot reach stay `ACCEPTED-NOT-CLOSED`. *(Round 17: this said "sealed at the helper" and "the structural
seal binds `_digest_transcript_fd`". A signature check binds what the function **accepts**; row 2's
module-state route shows the body can still resolve a path. "Seal" is the word that carried the
overclaim through five rounds.)*
**As of round 15 those are rows 2, 5b and 6b** — three. *(Round 14 closed row 2; **round 15 reopened it** — see the table.)* Rows 1, 6a, 7 and row 9's caller half are
closed by **I18**, the caller-level fixture round 7 added and whose reach nothing re-derived until round
11. The behavioural cases are kept only for what genuinely lives outside the sealed helper.

**Fairly stated, the existing set does work for what it targets.** The sweep confirmed by execution that
each control mutant is caught by exactly the case §6 claims: I1 only by C2c, I2 only by C2a-on-reviewer-2,
I3 only by C8, I4 only by C3, I6 only by C5a, I9 only by C9a, I11 only by C10. Round 3's C9a seam-assert
is real and load-bearing. The set is not wrong; it is **incomplete in a way more cases cannot fix.**

#### The three invariants — acceptance conditions, not preferences

> **Round 5 rewrote these.** The round-4 version of ARCH-1 asserted a **forbidden-name list** over the
> helper's source, and both reviewers defeated it — in both directions. Executed:
>
> - `os.lseek(fd, 0, SEEK_SET)` to make two passes over the same descriptor **passes** the name list,
>   and is a *real* defect: measured, the count came from pass 1 (100,000) while the digest came from
>   pass 2, which saw different bytes after an in-place write. `os.dup` is likewise absent from the list.
> - A **callee escape** passes: `_digest_transcript_fd(fd)` delegates to `_internal_hash(fd)`, and the
>   shallow body inspection never sees the forbidden call. codex extended this — the recorded path can be
>   smuggled through a **module global or class attribute** and re-opened in the callee via a cached
>   `io.open`, and a **delegated cap** (`_digest_impl(fd)`) defeats row 8's claimed closure the same way.
> - `__code__.co_names` does **not** rescue it: it does not inspect callees, and closure state lives in
>   `co_freevars`.
> - And it is **too strong**: a *correct* one-pass reader built on `io.FileIO(fd, closefd=False)` is
>   **rejected** by a list that bans `io` — a false GATE FAILED, §5's first and highest risk. Executed.
>
> A forbidden-name list is a **proxy for the property, not the property** — the same defect C9a had, one
> level up. So the name list is deleted. What replaces it asserts the property directly.

- **ARCH-1 — the sealed signature.** `_digest_transcript_fd(fd: int) -> tuple[str, int]`. A test asserts
  by `inspect.signature` that the parameter list is **exactly `(fd,)`** — no path, no opener, no
  default-bound callable, no `*args`/`**kwargs`, no keyword-only fallback. This is a **signature fact**,
  not a name match, so aliasing, callees and closures cannot evade it, and it cannot false-positive.
  It seals the *path* out of the helper. It does **not**, on its own, constrain what the helper does with
  the fd — ARCH-3 does that.
- **ARCH-2 — the caller resolves the recorded string exactly once, unchanged, and the seam reports the
  CAUSE.** *(Round 6 added the typed cause — without it the distinct-message cases are unsatisfiable
  except by re-resolving the path.)* The current prologue collapses both failure modes to `None`:
  `except OSError: return None` (`review-verdict.py:219-220`) and
  `if not stat.S_ISREG(...): return None` (`:222-223`). But C2 and C4 demand **distinct** messages for
  *missing*, *symlink/FIFO*, *empty* and *changed*. With a bare `None` the only way to tell them apart is
  `os.path.exists(path)` — a second resolution §4.1 step 5 forbids, which no instrumentation caught
  because it is a `stat`, not an open.
  **So `_open_regular_fd` must return a typed result** — `(fd | None, cause)` with `cause` in
  **`{OK, MISSING, SYMLINK, NOT_REGULAR, DENIED}`**, or a dedicated exception per cause, under this
  **explicit errno mapping**:

  | condition | cause |
  |---|---|
  | `ENOENT` / `ENOTDIR` | `MISSING` |
  | `ELOOP` (what `O_NOFOLLOW` raises on a symlink — measured, errno 62 on darwin) | `SYMLINK` |
  | open succeeds, `fstat` is not `S_ISREG` (a FIFO opens cleanly under `O_NONBLOCK` — measured) | `NOT_REGULAR` |
  | `EACCES` / `EPERM` | `DENIED` |
  | `OK` + streamed count 0 | *empty* (caller) |
  | `OK` + non-zero count + digest mismatch | *changed* (caller) |

  > **Round 7 added `SYMLINK` as a fifth value.** A four-value vocabulary collapses symlink and FIFO into
  > `NOT_REGULAR`, but C4a and C4b each demand a **distinct** message — so the caller would have to
  > `lstat` the path to tell them apart, the exact second resolution §4.1 step 5 forbids. The seam can
  > already distinguish them for free: measured, a symlink fails open with **ELOOP** while a FIFO opens
  > and reports `S_ISFIFO`. (codex judged four values sufficient; gemini caught that they are not, and
  > gemini is right on this one — the distinct-message requirement is what decides it.) The caller then produces every
  distinct message from what the seam already learned, and has **no reason** to touch the path again.
  Removing the motive is stronger than detecting the act.

  **ARCH-2 also owns the caller-side assertions:** that the caller bases its *empty* diagnosis on the
  count the helper returned (never on `st_size` or `getsize`), and that it performs **no retry and no
  short-read fallback** (I18's red-branch test).

  The rest of ARCH-2 is unchanged: The function that reads
  a reviewer's `transcriptPath` passes that **exact string** to `_open_regular_fd`, once per entry, and
  passes only the resulting fd onward.
  **What ARCH-2 establishes, exactly — round 17.** Its assertions prove **one seam call per entry with an
  unchanged argument**. They do **not** prove that only one *resolution* occurs: an implementation may
  resolve the path again by a route that never reaches the seam — `os.path.exists`, `getsize`, a second
  `io.open` — which is exactly what §6.0 rows **2**, **5b** and **6b** record as unclosed. *(codex, round
  17: ARCH-2 was described as proving exactly one resolution, so §5, §6.0, §7 and the header disagreed
  about what the invariant delivers. It removes the **motive** for a second resolution by supplying every
  distinct message from the first; removing a motive is not preventing an act.)*
  Assert both halves: the seam is called once per entry, **and** the
  argument it receives is byte-identical to the artifact's recorded value. Round 5 found the caller-only
  escape this closes: `p = entry["transcriptPath"].strip(); _open_regular_fd(p)` makes exactly one seam
  call and no other filesystem call, yet violates §4.1 step 6.
- **ARCH-3 — ADVERSARIAL FIXTURES, NOT INSTRUMENTATION. Rewritten in round 6.**

> **Round 6 defeated the previous ARCH-3, which wrapped `os.open`/`os.lseek`/`io.FileIO`.** That was the
> **fourth** proof mechanism to fail the same way (C9a → ARCH-1 → ARCH-3), and all of it is executed:
>
> - **A seek through a file object never reaches `os.lseek`.** `fh = os.fdopen(fd, "rb")` … `fh.seek(0)`
>   performs a real C-level seek while the wrapper observes **zero** `os.lseek` calls. Measured.
> - **`os.pread` twice needs no seek at all** — positional reads, no `lseek`, no `dup`, no reopen.
> - **`io.FileIO` cannot be patched**: `TypeError: cannot set 'read' attribute of immutable type
>   '_io.FileIO'`. Executed.
> - **A cached alias defeats it *and* false-rejects correct code.** `cached_open = os.open` taken before
>   patching bypasses the wrapper (codex executed this); a *correct* implementation using a cached alias
>   is then rejected because the test observes zero opens — §5's highest risk, realised.
> - `mmap`, `ctypes`, threads and child processes are outside any such accounting.
>
> **The lesson, stated once so a sixth attempt does not repeat it: every failed mechanism observed the
> implementation.** Instrumentation can always be routed around, and routing *legitimate* code around it
> produces false failures. So ARCH-3 no longer observes anything. It chooses **fixtures whose shape makes
> a wrong access pattern fail or return wrong values on its own** — and asserts only the helper's return
> value or the exception it raises. Aliasing, callees, closures, module globals, C-level calls, `ctypes`
> and subprocesses are then all irrelevant **to the fixtures' own verdicts**, because nothing is being
> watched. *(Round 17: this read "irrelevant" unqualified, which scans as a claim that those routes cannot
> defeat the plan at all. They cannot defeat **ARCH-3's fixtures** — F1's pipe and F2's non-zero offset
> return wrong values for a rewinding reader however it is spelled — but module state is exactly how §6.0
> row 2's accepted implementation reaches a path. The fixtures are robust; that does not make the plan
> complete.)*

  **Four fixtures — F1, F2, F3 and F4** — each passed to `_digest_transcript_fd` directly. A correct
  one-forward-pass helper
  satisfies all four naturally; every wrong shape found across rounds 4–6 fails at least one. **All results
  below are executed.**

  - **F1 — a NON-SEEKABLE fd (a pipe).** Write a known payload, close the write end, pass the read end.
    A forward-streaming helper returns the exact digest and count. Anything that seeks or `pread`s
    **raises `OSError` ESPIPE** — it cannot be caught by accident and needs no observation:

    | implementation | F1 |
    |---|---|
    | correct (one forward pass) | **PASS** |
    | seek-then-second-pass | **FAIL** — `ESPIPE` |
    | `os.pread` twice | **FAIL** — `Illegal seek`, errno 29 |

    A pipe also has **no pathname**, so a reopen-by-path is unconstructible, and it proves the helper
    never depends on `st_size` being meaningful.

    > **Honest limit, measured — do not overclaim F1.** On macOS `fstat` on a pipe reports the
    > *currently buffered* byte count, so an `st_size`-based helper **passed F1** when the whole payload
    > fitted in the pipe buffer. F1 does **not** discriminate the `st_size` mutant. F2 does.

  - **F2 — a regular fd PRE-POSITIONED at a non-zero offset K.** The contract is "read forward from the
    descriptor's current position to EOF", which the natural implementation satisfies without trying.
    Every wrong shape violates it observably:

    | implementation | F2 (K = 1000, file 50,004 B) |
    |---|---|
    | correct | **PASS** — count 49,004, digest of `bytes[K:]` |
    | `st_size` as the count | **FAIL** — count 50,004 |
    | seek-to-zero two-pass | **FAIL** — digest is of `bytes[0:]` |
    | `os.pread` from 0 | **FAIL** — count 50,004 *and* wrong digest |
    | `return len(last_chunk)` (round 5's mutant) | **FAIL** — count assertion |

    **F2 kills every count-and-digest defect found in rounds 4–6 that does not branch.** F1 is kept
    because it fails *loudly and content-independently*, which F2 does not.

    > **Round 7: F1+F2+F3 are jointly defeatable, and the reason matters.** codex executed
    > `if regular and current_offset == 0: <two passes> else: <one forward pass>`. F1 exercises the
    > non-regular branch; F2 deliberately exercises a **non-production** offset; F3 is static and cannot
    > tell one pass from two. **Production always supplies a regular fd at offset 0 — the one
    > configuration none of the three fixtures tests** — so production takes the forbidden branch.
    > gemini found a second escape of the same shape: recover the path *from the descriptor* and reopen
    > by name (`os.readlink(f"/proc/self/fd/{fd}")` on Linux — pure stdlib; on macOS it needs
    > `fcntl(F_GETPATH)`, which I could **not** invoke from Python here, so I am not claiming to have
    > reproduced it on darwin). CI is Linux, so it counts.
    >
    > A fixture only proves something about the configuration it presents. F4 and F5 exist because the
    > previous three all presented configurations production never sees.

  - **F3 — SIZE, with its ceiling stated.** Stream a payload larger than any plausible cap and assert
    success. **This cannot prove the absence of a cap** — no finite set of sizes does. So the plan states
    the bound instead of pretending: *"no cap is demonstrated up to N bytes"*, with N the largest size
    tested. Row 8 is closed **to that bound and no further**, in the same register as §3.1.
    *(Round 9 restored this bullet: ARCH-3's body defined F1, F2 and F4 while §7 mandated F3 — the
    fixture was mandated but never specified.)*

  - **F4 — an UNLINKED fd.** Open the transcript, then unlink the path, then call the helper. The inode
    stays readable through the descriptor. Measured: a correct one-pass helper returns the exact digest
    and count (49,004 bytes) on an unlinked fd.

    > **Round 8 correction — F4 is weaker than round 7 claimed, and the claim was wrong on Linux.**
    > Round 7 said path recovery fails "by construction". On Linux an unlinked inode is still reopenable
    > through **`/proc/self/fd/N`**, so F4 invalidates only the recovered *original pathname*, not every
    > descriptor-derived reopen. It still closes the `F_GETPATH`/`readlink`-then-`open(name)` shape,
    > which is the plausible one; it does not close a deliberate `/proc/self/fd` reopen. Stated, not
    > papered over.

  - **F5 / F5b — REMOVED FROM THE GATING SUITE in round 8. Recorded here as an option NOT taken.**

    F5 presented production's exact shape (a regular fd at offset 0) and asserted that the returned
    `(digest, count)` must describe **one** state of a file being alternated between two states of
    different lengths. It worked, and the measurements are kept because they cost real effort:

    | implementation | inconsistent `(digest, count)` pairs |
    |---|---|
    | one forward pass (correct) | **0 / 300**, and **0 / 1500** on a longer run |
    | round 7's branching two-pass | **22 / 300** — detected |

    **Both reviewers argued F5 would false-fail a correct reader because of torn reads. Both were
    wrong**, and the record should say so precisely: over 1,500 trials a correct reader produced **590
    torn reads and 0 false failures**, because the assertion fires only when a **known** state's digest
    arrives with a mismatched count — a torn read's digest matches neither state and is skipped.

    **It is removed for two better reasons:**

    1. **It is defeated outright**, not probabilistically. codex's *stable multi-pass* reader —
       `while True: seek0; a = read_all(); seek0; b = read_all(); if a == b: return sha256(b), len(a)` —
       always returns a self-consistent pair while reading repeatedly. A single `os.pread` of the whole
       file into memory does the same, and additionally violates "no cap".
    2. **No trial count bounds it.** The 22/300 rate is not stationary or independent — it depends on
       scheduling, machine load and CI runner behaviour — so the binomial arithmetic that would justify
       a trial count does not apply. A gate whose sensitivity varies with load is the eighth inert gate
       in a campaign that has already shipped or nearly shipped seven.

    **F5b is removed with it**, and for an additional reason of its own: it had **no distinguishing
    oracle**. With recorded digest A, a correct caller may read A and approve; a *retrying* caller may
    read B, retry until it sees A, and approve — both outcomes are "self-consistent", so the assertion
    cannot tell them apart.

    > **What replaces F5b for the caller-side retry class (I18).** codex's deterministic construction,
    > adopted: force the helper to return a **mismatching** digest while the recorded path contains
    > **matching** bytes, then assert the caller fails **without** a second helper call or path read.
    > That is mutation evidence, not a universal proof — and §3.1 already says the plan does not claim
    > one.

**Why fixtures and not more instrumentation:** the surviving implementations are behaviourally
indistinguishable from the correct one *on the inputs the plan previously chose*. They are trivially
distinguishable on inputs chosen to expose them. The fix was never a better observer — it was a better
input.

#### The 16 defeating implementations, and what closes each

*(Twelve until round 11, when row 6 split into **6a** (empty diagnosis — closed) and **6b** (missing
diagnosis — accepted): its two halves had different status, the same defect round 10 found in I12, I16
and row 9. **Round 12 split row 5** — C15 closes its permission limb (5a) — and **round 13 split it
again**: both arms showed the remaining limbs were *not* uniformly unreachable. **5c** (symlink) is closed
by **C4a**, whose target bytes differ so an `io.open` re-classification reports a digest mismatch instead
of the exact `SYMLINK` message; **5d** (not-regular) is closed by **C4b**, whose timeout catches the
blocking FIFO read. Only **5b**, the *missing* limb, is genuinely unreachable — `io.open` on an absent
path raises `ENOENT` and lands on the same `MISSING` diagnosis a correct implementation gives, so no case
can separate them. Three rows remain accepted-not-closed: **2, 5b, 6b**. *(Round 14 closed row 2 on a codex finding; **round 15 reopened it** when both arms — codex reversing itself — showed I18 reaches only the caller-side form and ARCH-1 does not force the probe caller-side. **Corrections have now run in both directions**, which is why every re-derivation must test reachability of the exact branch a defect lives on, not merely whether some fixture is caller-level.)*

**Rounds 11-14 each found the same defect (round 15 found its inverse): a residue classified against the proof set as it
stood, never re-derived as the proof set grew.** I18 (round 7) surfaced in round 11; C15 (round 11) in
round 12; C4a/C4b — present since round 4 — in round 13. The last one is the sharpest, because those
cases were not new at all: **row 5 had simply never been checked against them.** The instruction is
therefore stronger than "re-derive when a proof is added": **re-derive every residue against the WHOLE
proof set, not against the cases that happen to be under discussion.**)*

Every row was **executed** against a harness that re-creates C1, C2a/b/c, C3, C4a/b, C5a/b, C8, C9a
(with round 3's non-vacuity assertions), C9b and C10, and that a correct baseline passes.

| # | the wrong implementation | property it violates | closed by |
|---|---|---|---|
| 1 | digest via `pathlib.Path(path).read_bytes()` **first**, then "confirm" with the seam | the trusted bytes never come from the validated fd | **CLOSED by I18's retry arrangement** *(round 11; was ACCEPTED-NOT-CLOSED)* — that arrangement stubs the helper's **first** call to return a mismatching digest while the path on disk digests to the artifact's recorded `D`. A path-first caller trusts its own read, matches `D`, and **approves**, where the correct caller fails; and I18 asserts **zero path reads**, which a pre-read violates outright |
| 2 | hash from the fd, then a second `Path.open()` probe to re-check `S_ISREG` | second resolution of the name | **ACCEPTED-NOT-CLOSED** (§3.1) — **restored in round 15 after round 14 wrongly closed it. Both arms, from different angles.** gemini: the probe runs on the **success branch**, and *neither* I18 arrangement reaches it — the retry arrangement fails the caller on a digest mismatch and the short-read arrangement fails it on the empty diagnosis, so the probe never executes and the zero-path-reads assertion stays green. codex (**reversing its own round-14 finding**): ARCH-1 inspects only the **parameter list** (`:372-377`), so an implementation can smuggle the path through module state keyed by the fd — `_digest_transcript_fd(fd)` keeps its exact signature, hashes, then probes **inside the helper**, which I18 stubs away entirely. **Neither form is rejected.** The caller-side form escapes because the probe runs on the success branch that no I18 arrangement reaches; the in-helper form escapes because I18 stubs the helper. *(Round 16, gemini: the round-15 wording ended "I18 rejects only the caller-side form", contradicting the sentence before it — gemini's own argument is that the caller-side form escapes too. Merging two independent arguments left a claim neither supports.)* |
| 3 | retry-once: a second descriptor **only** when the digest disagrees | re-open, hidden on the red branch | **I18's deterministic red-branch test** (F5b removed in round 8 — it had no distinguishing oracle) |
| 4 | short-read fallback: re-open when fewer bytes stream than `fstat` promised | re-open, under exactly the shrink race Q3 names | the explicit **no-fallback contract** (§4.1 step 5) + I18's red-branch test |
| 5a | failure-path re-classification through `io.open`, on a **permission** failure | re-open on the red branch | **CLOSED by C15** *(round 12; was ACCEPTED-NOT-CLOSED)* — C15 stubs `os.open` to raise `EACCES`/`EPERM`, and an `io.open` retry **bypasses that stub** and reads the real file. The correct helper returns cause `DENIED`; this implementation re-classifies off the successful second open and returns something else, so C15's exact-cause assertion fails. The mutant is **I19**'s sibling: C15 discriminates them |
| 5b | failure-path re-classification through `io.open`, on the **missing** limb | re-open on the red branch | the **typed cause** removes the motive; **ACCEPTED-NOT-CLOSED** (§3.1) — `io.open` on an absent path raises `ENOENT`, so the re-classification lands on the *same* `MISSING` diagnosis a correct implementation gives. No case can separate them; this is the one genuinely unreachable limb |
| 5c | failure-path re-classification through `io.open`, on the **symlink** limb | re-open on the red branch | **CLOSED by C4a** *(round 13)* — C4a's symlink must point at a regular file whose bytes **differ** from the recorded transcript (`:786-788`). An `io.open` re-classification follows the link, reads the differing bytes and reports a **digest mismatch**, so C4a's exact `SYMLINK` message assertion rejects it |
| 5d | failure-path re-classification through `io.open`, on the **not-regular** limb | re-open on the red branch | **CLOSED by C4b** *(round 13)* — `io.open` lacks `O_NONBLOCK`, so a FIFO read **blocks forever**; C4b carries a timeout precisely for that (`:791-793`, measured `exit=124`) and rejects it |
| 6a | `os.path.getsize` for the **empty** diagnosis | second resolution; contradicts Q3 | **CLOSED by I18's short-read arrangement** *(round 11)* — against a stubbed `(D, 0)` it reads `getsize` = **100**, calls the file non-empty and **approves** where the correct caller fails; the `getsize` call is itself a path read |
| 6b | `os.path.exists` for the **missing** diagnosis | second resolution; contradicts Q3 | the **typed cause** removes the motive; **ACCEPTED-NOT-CLOSED** — *(round 16: the reason given was that "no fixture takes a missing-resolution branch", which is **false** — C1/C2a/C3 all reach it. The correct reason is that reaching the branch is not enough: on a genuinely missing path `os.path.exists` returns **False**, yielding the **same** `MISSING` diagnosis a correct implementation gives, so every case that reaches the branch observes an identical result. **Branch reachability without a behavioural difference is not closure** — the mirror image of the round-14 error.)* *(Round 11 split this row: its two halves have different status, which is the same defect round 10 found in I12, I16 and row 9.)* |
| 7 | `os.path.getsize(path)` for the non-empty check after hashing the fd | same, post-hash | **CLOSED by I18's short-read arrangement** *(round 11; was ACCEPTED-NOT-CLOSED)* — mechanically identical to row 6a: `getsize` returns 100 where the streamed count is 0, so this caller approves where the correct one fails |
| 8 | the cap **raised**, not removed (1 MiB / 64 MiB "DoS guard") | I6's defect above C5a's single measured point | **F3, TO ITS STATED BOUND ONLY.** Round 6: no finite set of sizes proves the absence of an arbitrary higher cap, and a delegated `_digest_impl(fd)` holds the cap in a callee. The plan states the bound rather than claiming closure |
| 9 | no byte count at all — "empty" inferred from the digest constant | Q3's streamed count absent | **F2 + C12 for the helper; CLOSED for the caller by I18's short-read arrangement** *(round 11; the caller half was ACCEPTED-NOT-CLOSED)* — against `(D, 0)` with `D ≠ _EMPTY_SHA256`, the constant-inferring caller calls the file non-empty and **approves**. *(Helper half restated in round 11: C12 alone rejects only a **fabricated** count; **F2** is what rejects `st_size`/`getsize` — see C12 and I12a)* |
| 10 | digests compared as 12-hex **prefixes** (reusing the display variables) | a 48-bit check, not 256-bit | **C13** |
| 11 | the comparison hoisted **out** of the per-entry loop (loop-variable reuse) | only the last entry's content is checked | **C13** |
| 12 | `except (OSError, ValueError, TypeError): continue` — a recorded path that *raises* silently skips the entry | fail-open; reachable with a NUL byte in `transcriptPath` | **C14** |

Two more were blocked, but only by a fixture detail §6 never pinned:

- `os.path.realpath()` before the hardened open (defeats `O_NOFOLLOW` while keeping the flags) is caught
  by C4a **only if** the symlink's target content differs from the recorded digest. §6 now pins that:
  **C4a's target must be a regular file whose bytes differ from the recorded transcript**, so the case
  fails for the right reason. §4.1 step 6 forbids the normalisation outright.
- A single shared failure message is caught by C2 **only if** C2a/b/c assert three mutually exclusive
  needles. §6 now says so explicitly rather than leaving "distinct message" to interpretation.

#### New cases — only for what lives outside the sealed helper

- **C11** an approving artifact whose reviewer `status` is `"approve"` (lowercase) or `"APPROVE "`
  (trailing space) → the transcripts **must still be checked**. `_quorum_problem` normalises with
  `.strip().upper()` (`:99-100`), so such an artifact passes quorum; a §4.2 skip written as
  `if r.get("status") not in APPROVING: continue` silently exempts it. Normalise identically or the
  skip becomes the bypass.
- **C12** the streamed-count contract. **Round 5 rewrote this case: as first written it was
  tautological.** `sha256(b"")` **is** `_EMPTY_SHA256` (`review-verdict.py:36`) — verified by execution —
  so "empty diagnosed from the streamed count" and "empty diagnosed from the digest constant" return the
  *same answer on every fixture*, and no artifact-level case can separate them. C12 is therefore
  **ARCH-3's direct helper test**, not a behavioural case: call the helper on zero-, one- and
  many-chunk fixtures and assert the **exact returned count** alongside the exact digest.
  **Paired mutant: `I12a` only — and C12 closes only PART of it; `F2` closes the rest.**
  C12 rejects a **fabricated** count — `len(last_chunk)`, a constant, an off-by-one. It **cannot** reject
  `st_size` or `os.path.getsize`, because on C12's static, offset-zero fixtures those are *equal* to the
  true streamed count. **This plan measured exactly that**: `:1017` records "`st_size` as the count |
  equals the streamed count on **every** static fixture (0 / 100 / 150,000)". What separates them is
  **F2's non-zero starting offset**, where the streamed count is strictly less than the file's size. So
  I12a's rejection is **F2 + C12**, and neither alone.
  *(Round 11, from gemini: C12's pairing was still the **unsplit `I12`** and still claimed it must fail on
  "infer emptiness from the digest constant" — which is **I12b**, whose own definition below states that
  C12 does not reach it. The plan asserted that a case rejects a mutant the same plan says the case cannot
  see. Round 10 split I12 and propagated the split into §7 and the mutant list, but not into here.)*
  *(Round 11, from codex: the "C12 must fail on it" claim was too strong for two of I12a's three forms,
  by the plan's **own** escape-analysis measurement. A proof that cannot fail on the implementation it
  names is not a proof — the same shape as the round-5 tautology this case was rewritten to escape.)*
  *(Round 7: the "caller bases its empty diagnosis on the returned count" assertion belongs to **ARCH-2**,
  not to C12 — §13 said it had moved and C12 still claimed it. It is now stated in ARCH-2.)*
- **C13** per-entry, full-width comparison: mutate **only reviewer 0's** transcript and separately **only
  reviewer 1's**, and additionally record a digest that shares its first 12 hex characters with the real
  one. All three must FAIL. Paired mutant **I13**: compare truncated digests, or compare once outside the
  loop → C13 must fail.
- **C14** fail-closed on unexpected errors: a `transcriptPath` containing a **NUL byte** (which raises
  `ValueError`, not `OSError`) must produce a gate **failure**, never a skipped entry. Paired mutant
  **I14**: swallow non-`OSError` exceptions and continue → C14 must fail.
- **C15** *(round 11, from codex)* **the `DENIED` cause has a case at last.** ARCH-2 mandates the errno
  mapping `EACCES`/`EPERM → DENIED` (`:385`), and §6 requires a mutation proof for **every** fix
  (`:310`) — yet across twelve cases and sixteen mutants **nothing exercised that branch**. An
  implementation mapping permission errors to `MISSING` satisfied the entire stated suite, and the one
  cause a CI runner is most likely to actually hit was the one with no test. C15 stubs `os.open` **in
  process** to raise `OSError(errno.EACCES)` — and separately `EPERM` — and asserts the returned cause is
  exactly `DENIED` and the message is the `DENIED` message, distinct from the other four.
  **In-process, not a chmod fixture:** a `chmod 000` file is readable by **root**, so the fixture silently
  passes for the wrong reason in a container — the same class as the round-6 canary that could not be
  planted. Paired mutant **I19**: map `EACCES`/`EPERM` to `MISSING` (or fold them into the bare
  `except OSError` prologue) → **C15 must fail**.
  **C15 also closes §6.0 row 5a** *(round 12)*: an implementation that re-classifies the failure path
  through `io.open` **bypasses the `os.open` stub**, reads the real file, and reports a cause other than
  `DENIED` — so C15's exact-cause assertion rejects it. That was not noticed when C15 was added in round
  11, which is the second time a new case silently closed a pre-existing residue. **Whenever a case or
  fixture is added to this plan, re-derive §6.0's classifications against it before shipping.**
- **C5a is measured at two sizes**, not one: 512,723 bytes **and** a file larger than any plausible
  "generous" cap (≥ 2 MiB). One measured point pins one threshold; row 8 lives above it.

**Implementation mutants — each must be caught by its named mechanism**, with **exactly one** stated
exception: **I16b**, whose *production-conditional / stable-multipass* residue §3.1 accepts as not closed.
**I16a's** unconditional `lseek`/`pread` forms **are** rejected, by F1 and F2. Every other mutant in this
list — **I9 included, and I12b as of round 11** — must be caught: the §6.0 sweep records I9 as caught by
C9a, and I18's short-read arrangement catches I12b.

*(Round 11, from gemini: this preamble named the exception as "**I16**" — the whole mutant rather than its
accepted half — and asserted "every other mutant, **I9 included**, must be caught", while §7 step 5
correctly named **two** residues, I16b **and** I12b. §6 and §7 disagreed on both the **count** and the
**identity** of the exceptions. Round 10 split I12 and I16 and propagated the split into §7 and into the
mutant definitions, but not into this preamble — the third time in this campaign a decision reached the
argument and not the operative restatement. Round 11 additionally **closes** I12b, so "exactly one
exception" is now true, for a different reason than the original wording gave.)*

- **I1** `os.path.exists` instead of re-digesting → C2c must fail.
- **I2** re-digest only the first reviewer → C2a on reviewer 2 must fail.
- **I3** apply the checks to non-approving artifacts too → C8 must fail.
- **I4** `if path: verify(path)` — skip when `transcriptPath` is absent. **This passes every round-1
  proof**: `_quorum_problem("APPROVE", …)` returns `None` for reviewers with valid-looking digests and
  *no* `transcriptPath` (executed). Caught only by C3.
- **I5** `os.path.isfile` + `_sha256_bytes` instead of the hardened opener → C4a must fail (`isfile`
  follows links).
- **I6** reuse `_read_regular_file`, or keep its cap inside `_open_regular_fd` → C5a must still **PASS**;
  a mutant that rejects it must be caught.
- **I9** *(the sweep's headline)* validate with `_open_regular_fd`, **close the fd, then reopen the path**
  for hashing. **C9a must fail on this mutant** — the §6.0 sweep records I9 as caught by C9a, and the
  reopened bytes feed the digest. It is a required rejection, not an accepted gap.
  *(Round 10 correction: round 9 marked I9 `ACCEPTED-NOT-CLOSED`, which contradicted this plan's own
  sweep. The accepted residue is not I9 as defined here — it is §6.0 **row 1's** path-**first** read,
  where the trusted bytes never come from the validated fd at all. Different mutant, different row.)*
- **I10** delete the non-empty check, or emit **one shared message** for all three causes → C2b must fail
  on the **exact** message. Without distinct messages this mutant is unobservable, because
  `_quorum_problem` already rejects the empty-file hash (`_EMPTY_SHA256`, `:36`).
  *(Round 4: reworded. I10 previously named "the `st_size` non-empty check", contradicting §8 Q3's
  adopted answer. The check is on the **streamed byte count** — see §4.1 step 4 and I12.)*
- **I11** compare the digests as **sets/multisets** rather than per reviewer entry → C10 must
  fail. A plausible order-insensitive one-liner that permits the two reviewers' transcripts to be swapped.
- **I12** *(round 4; split in round 10)* emptiness diagnosed from `st_size`, `os.path.getsize`, or the
  digest constant instead of the streamed count. **Split, because the two halves have different status —
  the same defect round 10 found in I16 and in §6.0 row 9:**
  - **I12a — the HELPER returns a derived count**: `st_size`, `os.path.getsize`, or `len(last_chunk)` in
    place of the true streamed count. **Rejected by `F2` AND `C12` together — neither alone.** **C12**
    calls the helper directly on zero-, one- and many-chunk fixtures and asserts the **exact returned
    count**, which kills a *fabricated* count (`len(last_chunk)`, a constant, an off-by-one). **F2** — an
    fd already advanced past byte 0 — is what kills `st_size` and `os.path.getsize`, because only there
    does the true streamed count differ from the file's size. **Required rejection.**
    *(Round 11: this half said "**C12** must fail on it" for all three forms. On C12's static offset-zero
    fixtures `st_size` **equals** the streamed count — the plan's own escape-analysis row `:1017` records
    that measurement — so C12 alone cannot reject two of the three forms it named. The mutant is
    unchanged; the mechanism that kills it is now stated correctly.)*
  - **I12b — the CALLER ignores the helper's count** and re-derives emptiness from `st_size`,
    `os.path.getsize`, or the digest constant. **CLOSED by I18's short-read arrangement — round 11.**
    That arrangement stubs the helper to return **`(D, 0)`** while the path on disk holds **100 bytes**
    whose digest **is** `D`. A caller re-deriving emptiness from `st_size`/`getsize` reads **100** →
    "non-empty" → digest matches → it **approves**; a caller inferring emptiness from the digest constant
    sees `D ≠ _EMPTY_SHA256` → "non-empty" → it **approves**. The correct caller uses the returned count
    `0`, diagnoses empty, and **fails**. I18 asserts the caller **fails** *and* performs **zero path
    reads**, so all three forms are rejected on both limbs of the oracle. **Required rejection.**
    *(Round 11, from codex: the round-10 classification rested on "**no fixture in this plan exercises a
    caller**" — a statement that stopped being true in round 7, when I18 was added as a
    **caller-level** test with a deterministic oracle. The plan carried a residue it had already closed,
    and repeated the claim in §5's risk register and §7 step 5. C12 genuinely cannot see I12b; I18 can,
    and nothing had re-checked the residues against the newer fixture.)*
  *(Round 10 fix: I12 previously read "diagnose emptiness … → C12 must fail" as a single mutant. That
  named a **caller** behaviour and attributed it to a **helper-only** case, so §7's rule that every
  non-accepted mutant is caught by its named mechanism could not hold for it.)*
- **I13** *(round 4)* compare truncated digests (the 12-hex display form), or perform the comparison once
  outside the per-entry loop → C13 must fail.
- **I14** *(round 4)* swallow non-`OSError` exceptions and skip the entry → C14 must fail.
- **I15** *(round 5)* keep `_read_regular_file`'s **UTF-8 decode** in the new helper
  (`review-verdict.py:224` is the current form) instead of streaming raw bytes → **C5b must fail**. C5b
  was required to PASS but had no mutant, so nothing proved it could ever fail; a decoding helper is the
  plausible wrong implementation it exists to kill.
- **I16** *(round 5; retargeted round 7; split in round 10)* a second pass over the same descriptor.
  **Split, because the two halves have different status:**
  - **I16a — unconditional second pass** by `lseek(0)` or `os.pread(…, 0)` before hashing. **F1 and F2
    must reject it**: F1 is a pipe-backed fd (unseekable — `lseek` raises `ESPIPE`) and F2 is an fd
    already advanced past byte 0, so a rewinding implementation returns the wrong digest. **Required
    rejection.**
  - **I16b — production-conditional or stable-multipass**: the second pass hides behind a branch that a
    fixture never takes (e.g. `if not sys.stdin.isatty()`), or reads the same bytes twice in a way that
    yields an identical digest. **No fixture in this plan rejects it.** F5 would have, and F5 was removed
    in round 8 as unboundable and itself defeatable. Per **§3.1 this residue is accepted, not closed.**

  *(Round 10 correction: round 9 marked all of I16 accepted-not-closed, which understated F1/F2 — they
  do reject the unconditional forms. I16 has now named two deleted mechanisms in two rounds: ARCH-3's
  accounting, then F5.)*
- **I17** *(round 7)* recover the path from the descriptor and reopen **by name** → **F4 must fail**.
  *(Round 8: a deliberate `/proc/self/fd/N` reopen on Linux is NOT caught — see F4's correction. I17
  covers the plausible shape, not every descriptor-derived reopen.)*
- **I18** *(round 7; retargeted round 8; fully specified round 9)* a caller that retries on digest
  mismatch, **or** falls back on a short read. Two arrangements, because one construction cannot trigger
  both branches:
  - **retry:** the transcript on disk is 100 bytes with digest `D`. Stub `_digest_transcript_fd` with a
    **two-element** side-effect list: first call returns `("0"*64, 100)` — a **mismatching** digest with a
    correct count — and the second returns `(D, 100)`. The artifact records `D`. Assert the caller
    **fails**, that it made **exactly one** helper call, and **zero** path reads. A retrying caller
    consumes the second element and approves, so the two results are what makes the mutant observable —
    with a single-element list the retrying caller would raise `StopIteration` and the test would pass
    for the wrong reason.
  - **short-read fallback:** the transcript on disk is 100 bytes with digest `D`, and the artifact
    records `D`. Stub the helper to return **`(D, 0)`** — the digest **matches**, but the streamed count
    is **0** against a promised `st_size` of **100**. Per §4.1 step 4 the streamed count is the sole basis
    for the "empty" diagnosis, so the correct caller **fails with the empty diagnostic** and performs
    **zero** path reads. A caller with a short-read fallback instead re-opens the path, recovers 100
    bytes, and approves.
    *(Round 11, from codex — Low: this read "fails with the **typed empty cause**", but the `cause`
    vocabulary is the five-value `{OK, MISSING, SYMLINK, NOT_REGULAR, DENIED}` (`:377`) and contains no
    `EMPTY`. Emptiness is deliberately a **caller** diagnosis derived from `OK` + `count == 0`, never a
    helper cause — so the sentence asked for a value the plan's own type forbids. The oracle is
    unaffected; only the name was wrong.)*

  **I18's oracle is worth more than round 9 credited it — round 11.** It has **two** limbs, *the caller
  fails* **and** *zero path reads*, and between them they reject every caller-side residue that re-derives
  emptiness by any route other than the returned count: §6.0 rows **6a**, **7** and **9's caller half**,
  plus mutant **I12b**. The retry arrangement rejects row **1** the same way. **Neither limb may be
  weakened to a single assertion** — `zero path reads` is what catches the pre-reading and `getsize`
  callers, and `the caller fails` is what catches the digest-constant one.
  Rows **2** and **5b** remain accepted *(round 14 closed row 2; round 15 reopened it — I18 stubs the helper, so an in-helper probe never runs, and neither arrangement reaches the success branch a caller-side probe would need)* *(round 13: this said "2 and 5", which stopped being true when C15 closed 5a and C4a/C4b closed 5c/5d — the sentence was I18-specific analysis, but it read as a residue list and contradicted the table, §5, §7 and the header)*: row 2's second `Path.open()` probe lives **inside** the helper
  that I18 stubs away, and neither arrangement enters a failure-path re-classification branch (round 10).
- **I19** *(round 11)* map `EACCES`/`EPERM` to `MISSING`, or leave them to the bare `except OSError`
  prologue, instead of the mandated `DENIED` → **C15 must fail**. The `DENIED` arm of ARCH-2's errno
  mapping had no mutant and no case for seven rounds.

    *(Round 10 fix: the previous wording returned a matching digest with a merely "smaller" positive
    count and asserted the correct caller fails. That inverts §4.1 — a positive count with a matching
    digest **should** approve, so the oracle contradicted the contract it was testing.)*

  *(F5b was removed in round 8: a retrying caller that eventually reads the recorded state is also
  "self-consistent", so it had no distinguishing oracle.)*

**Input cases the suite must carry:**

- **C1** the forgery itself — the exact artifact that returns `GATE OK` today.
- **C2** three *separately named* cases, each asserting its **distinct** message: **(a)** delete,
  **(b)** truncate to zero, **(c)** append one byte. Splitting them is what makes I10 observable.
  **The three needles must be mutually exclusive** — C2a asserts *missing*, C2b asserts *is empty*, C2c
  asserts *changed since approval*, and each must assert the other two do **not** appear. Round 4: a
  single shared message otherwise satisfies all three "assert your message" tests.
- **C3** `transcriptPath` **absent**, `null`, and `""` — three shapes, **each separately named**, all
  must fail. Round 4: C2's variants are named and C3's were not, so a partial C3 covering only *absent*
  would still leave I4 uncaught.
- **C4** **(a)** a symlink and **(b)** a FIFO at the transcript path, **each asserting its own distinct
  message**. Round 4 pins two fixture details the cases previously left open:
  - **C4a's symlink must point at a regular file whose bytes DIFFER from the recorded transcript.**
    With a same-content target the case passes against a `realpath()`-before-open implementation that has
    already defeated `O_NOFOLLOW`, so it would fail for the wrong reason — or not at all.
  - **C4b must assert the not-a-regular-file message, not merely a non-zero exit.** A seam extracted
    without the `fstat`/`S_ISREG` check still rejects a FIFO — via a digest mismatch on zero bytes — so
    exit-code-only assertions pass a build that dropped the check. **C4b must also carry a timeout**: an
    implementation that reads the path outside the `O_NONBLOCK` descriptor blocks forever rather than
    failing, and a hang is not an assertion (measured: `exit=124`).
- **C5** both must **VERIFY SUCCESSFULLY**: **(a)** a transcript larger than 64 KiB, at **two** sizes —
  the *typical* case measured at 512,723 bytes **and** one ≥ 2 MiB, because a single measured point pins
  a single threshold and a "generous" raised cap lives above it; **(b)** a **non-UTF-8** transcript —
  *defensive*, since a timeout-killed PTY capture can end mid-multibyte. This is the case that catches a
  fix worse than the defect.
- **C8** a non-approving artifact — `REQUEST_CHANGES` **and** `DISAGREEMENT`, including a `MISSING`
  reviewer — whose transcript has since been deleted must still `verify` to its existing outcome, with
  today's text.
- **C9** *(new)* the single-descriptor property, in-process because a subprocess `run()` offers no seam.
  The suite already loads the module in-process (`test_review_verdict.py:1001-1006`), so this needs no
  new dependency. Two halves:
  - **C9a behavioural** — monkeypatch `_open_regular_fd` with a wrapper that calls the real one and then
    `os.replace()`es different bytes over the path *before returning the fd*; `verify` must return **0**
    against the originally recorded digest. A single-descriptor implementation hashes the original inode
    and passes; I9 hashes the swapped bytes and fails. Deterministic — no sleeps, no thread races.
  - **C9a MUST ALSO ASSERT THE SEAM RAN.** Round 3 caught this and it is the whole point: as first
    written, C9a was **vacuous**. An implementation that ignores `_open_regular_fd` and issues its own
    `os.open(path, O_NOFOLLOW|O_NONBLOCK)`, closes it, then reopens via `pathlib.Path.open` **never
    triggers the monkeypatch**, so no replacement happens and C9a passes trivially — while keeping the
    exact race it exists to catch. Assert **exactly one `_open_regular_fd` call and exactly one
    replacement performed, per transcript**. A test that can pass without its own fixture firing is not
    a test.
  - **C9b structural** — wrap `os.open`/`builtins.open` and assert **exactly one** `os.open` of each
    transcript path, with `O_NOFOLLOW|O_NONBLOCK` in its flags, and **zero** further opens of it.
    **C9b alone is not sufficient either:** patching `builtins.open` does not intercept an already-cached
    `io.open` reference, so a reopen through `pathlib` is invisible to it.
  - **C9a and C9b are BOTH insufficient, individually and together — this is round 4's headline.**
    Executed: an implementation that hashes via `pathlib.Path(path).read_bytes()` *before* calling the
    seam passes C9a (one seam call, one replacement, digest taken pre-replacement → verify returns 0)
    **and** passes C9b (`pathlib` routes through a cached `io.open`, so neither `os.open` nor
    `builtins.open` records it). Both gate reviewers found the same class independently, and the sweep
    found ten more. **C9 is retained as a regression guard, not as the proof.**
  - **THE PROOF FOR THE HELPER IS ARCH-1 + ARCH-2 + ARCH-3 (§6.0), and they are MANDATORY.** The checker
    takes **only the raw fd** — never a path, never an opener, never a default-bound callable. That
    removes the *parameter-borne* routes to a path; it does **not** make re-opening unavailable inside the
    body, which can still reach module state, a class attribute or a closure. *(Round 17, both arms: this
    read "Re-opening becomes structurally unavailable **inside `_digest_transcript_fd`**" — the exact
    claim round 16 disproved, sitting in the sentence immediately **above** round 16's own note saying
    every such claim had been narrowed. Adding the correction next to the error is not narrowing it.)*
    This is a **signature constraint asserted by a test**, not a prose preference; §4.1 step 3 states the
    exact signature and §7 step 5 makes it an acceptance condition.
    **ARCH-1 PROVES ONE FACT AND NO MORE: the helper's parameter list is exactly `(fd,)`. Round 16.**
    *(codex: operative text here and in §5/§6.0 said ARCH-1 "seals" the helper and makes reopening
    "structurally unavailable" inside it. **It cannot establish that**, and §6.0 row 2 is this plan's own
    counterexample: the opener records `path_by_fd[fd]`, the helper retrieves it from module state, keeps
    its exact `(fd,)` signature, hashes, and probes. ARCH-1 passes; I18 stubs the helper; F1-F4 supply
    descriptors with no map entry; C9a sees a regular replacement and C9b cannot observe `Path.open`.
    **A parameter-list check bounds the INTERFACE, never the BODY.** Every operative claim is narrowed to
    the parameter-list fact, and rows 2/5b/6b are no longer called "caller-side" collectively — row 2 has
    an in-helper form.)* Round 3 wrote this as "prefer it" and
    round 4 was defeated through the gap that left.
    *(Round 10 correction: this bullet previously read "THE PROOF IS …" without qualification, which
    overclaimed against **§3.1**. The seal binds the **helper's signature**; it says nothing about a
    **caller** that re-opens the path before or after calling the helper. Per §3.1 and §6.0's
    `ACCEPTED-NOT-CLOSED` rows, the class is sealed **at the helper, not closed end-to-end**.)*
    *(Round 11: the round-10 note ended "no fixture in this plan exercises a caller." **That was already
    false when it was written** — I18, added in round 7, is precisely a caller-level fixture. The seal is
    still helper-only, so this bullet's conclusion stands, but the reason given was wrong and was the
    sentence §5 and §6.0 both copied when they over-counted the residues.)*
  - **Non-vacuity:** C9a must be stated beside C2c. A green C9a that came from a dead digest check proves
    nothing.
- **C10** *(new)* swap the two reviewers' `transcriptPath` values in a legitimately written artifact,
  leaving both digests in place → must **FAIL**. §4.1 must state that digests are compared **per reviewer
  entry**, never as aggregates.

**The trap this ticket is most likely to fall into:** `test_review_verdict.py`'s fixture calls `_write`
before verifying, so transcripts always exist and always match. A suite built that way goes green against
an implementation that checks nothing. **Every §4.1 test must mutate the transcript on disk between
`write` and `verify`.**

## 7. Implementation order

1. **`COREDEV-2619` first** (separate ticket). Once §4.1 re-digests, a clobbered transcript becomes a hard
   gate failure — so per-run paths must remove the collision *before* it turns fatal. Confirmed safe by
   both round-2 reviewers: the wrappers already accept arbitrary out-paths and `review-verdict.py`
   already records arbitrary transcript paths, so existing artifacts keep resolving.
2. `_open_regular_fd` extraction, with the **five** sidecar tests of §4.5 still green — `:200`, `:218`,
   `:757`, `:773`, `:811`, covering `O_NOFOLLOW`, the cap, `O_NONBLOCK`/`S_ISREG` and the decode epilogue.
3. §4.1 + §4.2 together — resolve, re-digest, per-reviewer, approving artifacts only, streamed-count
   emptiness, distinct messages per cause. §4.2 is the same code path, not a later step.
   **ARCH-1, ARCH-2 and ARCH-3 are acceptance conditions of this step**, not follow-up work: the step is
   not done until `_digest_transcript_fd(fd: int) -> tuple[str, int]` exists with exactly that signature,
   `_open_regular_fd` returns a typed cause from the five-value vocabulary, and the helper passes
   **F1** (pipe — ESPIPE on any seek/pread), **F2** (non-zero offset), **F3** (size, to a stated bound)
   and **F4** (unlinked fd — closes reopen-by-recovered-*name*). **§3.1's narrowed guarantee applies:**
   a two-pass reader is **not** rejected, and the CHANGELOG must say so.
   **Step 2 also gives `run()` a bounded timeout** (`test_review_verdict.py:13`) — without it the FIFO
   regression tests hang instead of failing.
4. §4.5's **one** test repair — (a) — using the executable repair stated there. *(Round 4: this step
   said "two"; (b) moved to `COREDEV-2618` in round 3.)*
5. All **seventeen** mutants — **I1, I2, I3, I4, I5, I6, I9, I10, I11, I12 (a/b), I13, I14, I15,
   I16 (a/b), I17, I18, I19** (I12 and I16 each count once, split into halves in round 10 as C2 and C5
   already are) — all
   **thirteen** cases — **C1, C2 (a/b/c), C3, C4 (a/b), C5 (a/b), C8, C9 (a/b), C10, C11, C12, C13, C14,
   C15** —
   all **three invariants — ARCH-1 (signature), ARCH-2 (unchanged string + typed cause + the caller-side
   assertions) and ARCH-3's fixtures F1, F2, F3 and F4** (F5/F5b removed in round 8 — §6.0). Enumerated, never as a range: the rescope deleted
   I7/I8 and C6/C7 with §4.3, round 3 caught stale ranges naming four identifiers the plan no longer
   defines, round 4 added six identifiers, round 5 added three (I15, I16, ARCH-3), and **round 11 added
   C15/I19 for the `DENIED` cause, which had been mandated by ARCH-2 since round 4 with no case and no
   mutant**. Each mutant shown caught by its named mechanism **except the ONE residue §3.1 accepts —
   I16b's production-conditional second pass, which is HELPER-side, not caller-side** *(round 16, gemini:
   this read "caller-side residue". I16b branches **inside** the helper on a condition no fixture takes;
   the caller-side residues are §6.0's rows. One word was describing two different kinds of residue)* *(round 11: I12b was the second exception and is
   now closed by I18's short-read arrangement)*; C5's halves
   shown **PASSING** at both sizes; and **each of §6.0's defeating implementations shown rejected**
   — that table is the acceptance suite for this step, not commentary, **except rows 2, 5b and 6b, whose
   closure §6.0 records as accepted-not-closed** *(round 11: was "rows whose closure … accepted-not-closed"
   without naming them, which let §5 and §6 carry different residue sets for four rounds — name them)*.
6. Version bump + CHANGELOG — **consistency/provenance hardening**, explicitly NOT proof that a reviewer
   read the plan. State §3's ceiling and the 17-byte floor.
7. `COREDEV-2618` afterwards, on the seam this plan creates.

## 8. Open questions for the reviewers

1. ~~fd vs injectable opener?~~ **ANSWERED in round 4 — the raw fd, and the opener alternative is
   removed.** Both reviewers answered independently and identically: monkeypatch the stable
   `_open_regular_fd` name for the seam, but never inject an opener into the digest routine. An
   injectable opener is a path-taking parameter wearing a callable's clothes, and §6.0's sweep defeated
   every variant that kept one. §4.1 step 3 now fixes the signature.
2. ~~Is C9a's `os.replace`-inside-the-opener a proof or a tautology?~~ **ANSWERED in round 4 — legitimate
   but insufficient, and not tautological.** Both reviewers agreed on all three parts. It is a valid
   deterministic TOCTOU construction *provided* the seam invocation and the replacement are asserted
   (round 3's fix). It is insufficient because a digest taken before the seam call, or a read routed
   around the patched names, passes it — see the C9 block and §6.0. Retained as a regression guard;
   ARCH-1/ARCH-2 are the proof.

5. ~~Is ARCH-1 the right shape of assertion (source inspection)?~~ **ANSWERED in rounds 5-6 — NO, and
   source inspection is gone.** ARCH-1 is now a signature assertion only; the forbidden-name list was
   defeated in both directions and deleted.

**New open questions for round 7:**

6. ~~Is F2's current-position contract legitimate?~~ **ANSWERED in round 7 — YES, but insufficient
   alone.** codex: it is the natural contract implied by "one forward pass, no seek", not test
   scaffolding. It is insufficient because an implementation can branch on production's offset-zero
   condition — which is why F5 exists.
7. ~~Is F3's stated ceiling acceptable?~~ **ANSWERED in round 7 — YES.** codex: a source-name assertion
   would revive the failed proxy approach; keep the bounded behavioural evidence, but drop any claim
   that I6 or arbitrary caps are *completely* closed. Done — row 8 and I6 now state the bound.

**New open question for round 8:**

8. ~~Is F5's probabilistic strength acceptable?~~ **ANSWERED in round 8 — NO. The guarantee is
   narrowed.** Both reviewers reached this independently; codex: *"no finite trial count is acceptable
   for a required non-flaky gate."* The maintainer confirmed. F5/F5b are out of the gating suite and
   §3.1 states what the plan does not prove. See §15.
3. ~~`st_size` vs streamed bytes?~~ **ANSWERED in round 3 — count bytes actually streamed.** Use the
   `fstat` for the `S_ISREG` check, but base the *empty* diagnosis on what was read: a shrink/grow race is
   precisely when the two disagree, and the streamed count is the truthful one. (gemini argued for
   `st_size` on early-exit grounds; codex's reasoning is stronger and is adopted.)
4. ~~`captureId` advisory-compare?~~ **ANSWERED in round 3 — explicitly DEFERRED to `COREDEV-2618`**, and
   removed from this plan's scope. Both reviewers agreed. `pty-capture.py:328` writes the sidecar inside a
   best-effort `try` opened at `:327`, so it cannot support a failing check, and adding warn-only behaviour here would
   reintroduce exactly the phantom scope round 2 created by declaring it "adopted" with no step and no
   case.

## 9. Notes — the citation record, kept because it keeps mattering

- **Eleven wrong citations across four drafts**, every one the same shape: a number taken from a
  `grep -n`/`sed` offset instead of from the file. Four self-caught; three by codex in round 3
  (`agents/swift-reviewer.md:160`→`:247`, `scripts/capture-reviewer-verdict.sh:43`→`:45`, and
  `AGENT_CONTRACTS.md:113`, which documents the `agy-ping` preflight and **never mentions the transcript
  paths at all**). **Round 4 added four more**, all in text written *by* round 3:
  `_quorum_problem` at `:99` (§2 — it is defined at `:74` and called at `:728`); `:66` and `:909` as
  `tx2` pairings (§4.5(b) — neither attaches a transcript); and §10 row 2's own `:195`/`:247`, which
  drifted the moment the plan was edited. **Three of the four were reported as VERIFIED by gemini.**
  The rule §9 exists for held again: *print the line you are citing, from the file, before writing it
  down* — and prefer a section name to a line number in text that will outlive the draft.
- **Round 2's four "self-corrections" included two that were themselves wrong.** The byte figure
  (512,723 was right; I "corrected" it to another project's file) and the claim that a strict `…$` anchor
  "matches 1/1 on both round-1 transcripts" — on the real transcript it matches **three** times, two of
  them another plan's verdicts quoted in the review body. Which means **"take the last match" is
  load-bearing, not defensive** — the opposite of what round 2 concluded. Both now belong to
  `COREDEV-2618`.
- The two claims that *did* hold: ANSI and CRLF are normalised at capture time
  (`scripts/pty-capture.py:314`) — though `ANSI_RE` at `:56` is **CSI-only**, so the guarantee is
  narrower than round 2 stated.
- `COREDEV-2603` moved the artifact to `schemaVersion` 3. This plan adds **no** new fields and needs no
  bump — it re-checks fields that already exist.
- Checks executed for this round: the forgery; `_quorum_problem`'s `APPROVE`-with-no-`transcriptPath`
  behaviour; the absence of transcript resolution in `cmd_verify`; `_read_regular_file` against the real
  512,723-byte transcript and its complete two-caller list; both affected tests read in full; and the
  17-byte satisfying-file measured on real corpus files.

> **Transcript-path notice (2026-07-30).** Every `/tmp/rev/…` path cited in the round histories below
> **no longer exists**: the machine's root volume filled, and macOS purged `/private/tmp`, destroying all
> 105 captured transcripts of this campaign in one event. The byte counts and hit counts recorded here
> were taken from those transcripts while they existed and are left as the historical record — but they
> are **no longer independently reopenable**, and a reviewer should treat them as claims, not evidence.
> Codex's own rollout logs under `~/.codex/sessions/` survived and were used to recover the affected
> round's findings. Captures from this round forward go to `~/.claude/review-transcripts/`.

## 10. Round-3 gate outcome

**gemini `APPROVE` · codex `REQUEST_CHANGES` (4 findings).** All four re-verified here before the plan
was touched; **all four held.** Both reviewers confirmed the frozen digest was unchanged for the round,
and the isolated `agy` harness reported `TREE=clean`.

| # | finding | verified | fix |
|---|---|---|---|
| 1 | **C9a is vacuous** — it monkeypatches `_open_regular_fd` but never asserts the seam was *called*, so an implementation that ignores it and does its own `os.open` → close → `pathlib` reopen passes trivially, race intact | **confirmed** | C9a now asserts one seam call + one replacement per transcript; C9b's own gap noted (patching `builtins.open` misses a cached `io.open`); and the **structural** fix — take only the raw fd — is stated as preferred over detecting the reopen |
| 2 | dangling ranges naming four identifiers the rescope deleted (I7, I8, C6, C7) — in the §6 mutant preamble and the §7 step-5 enumeration | **confirmed** | both enumerated explicitly rather than as ranges. *(Round 4: this row previously cited those two spots as `:195` and `:247`, which were the reviewed draft's line numbers and now resolve to unrelated lines — the §9 class, inside the table that records §9 fixes. Line numbers dropped in favour of the section names, which do not drift.)* |
| 3 | §4.5(b) belongs to `COREDEV-2618`, and the proposed repair would not have worked | **confirmed by execution** | many tests pair `codex=APPROVE` with `tx2`, so changing `tx2` moves the inconsistency rather than removing it. Moved to 2618. *(Round 4: the "five tests (`:66`, `:831`, `:904`, `:909`, `:989`)" evidence was wrong in both directions — see §4.5(b). Conclusion unchanged.)* |
| 4 | the risk register claimed §4.5 "names both sidecar tests"; it named neither | **confirmed** | now names `test_review_verdict.py:200` and `:757` |

**And a fifth, low but pointed:** §0's "638 `lumawake` matches" is **628**. The file is unchanged
(769,988 bytes), so this was not drift — **I propagated a subagent's number without re-measuring it**,
in the very section whose subject is having propagated an unverified measurement. Corrected.

**Where the two reviewers diverged.** gemini assessed C9a+C9b as "airtight … impossible for a
validate-then-reopen implementation to pass" and returned APPROVE. codex found the vacuity. Consistent
with the standing pattern: **on mechanism-level specifics, prefer codex.** gemini's answers to §8's open
questions were still useful and largely agreed with codex, diverging on Q3 (gemini: use `st_size`; codex:
count streamed bytes — **codex's is adopted**, since a shrink race is exactly when the two differ and the
streamed count is the honest one) and on Q4's destination ticket (2618 vs 2619 — filed to **2618**, which
owns the verdict/provenance vocabulary).

## 11. Round-4 gate outcome

**gemini `REQUEST_CHANGES` (3 findings) · codex `REQUEST_CHANGES` (6 findings).** Frozen at
`7447d79a504662a9522346b8dafdbe48f4ce4fb5`, plan sha256
`45bc5aa84a8aee2834a0e8035ee88f239a645414855195b16f1026162f17dc17`. Both reviewers re-verified the digest
themselves — codex at both ends of its run — and the isolated `agy` harness reported `TREE=clean`.
Transcripts: `/tmp/rev/2497r4-agy.txt` (3,965 B) and `/tmp/rev/2497r4-codex.txt` (580,832 B, 105
occurrences of the ticket key). Every finding below was **triaged by execution** before the plan was
touched.

### The headline: the proof set was defeated a fourth time, by twelve implementations

Alongside the gate, an adversarial sweep ran three independent passes, each **building a runnable harness
that re-creates C1–C10** (including C9a with round 3's non-vacuity assertions and C9b wrapping
`os.open`/`builtins.open`), verifying a correct baseline passes it, then running ~20 candidate
implementations against it. **Twelve pass every enumerated mutant and case while violating a property
§4.1 states.** Both reviewers independently found members of the same class. §6.0 tabulates all twelve
and what closes each.

That is the fourth consecutive round in which enumeration failed: round 2's sixteen cases fell to
validate-then-reopen, round 3 found C9a vacuous, round 4 found a reordering that survives the round-3
repair — and then eleven more. **Escalating round counts are this campaign's documented signal to stop
iterating and sweep the class**, which is why §6 is now anchored on two structural invariants (ARCH-1,
ARCH-2) with behavioural cases kept only for what lives outside the sealed helper.

### Findings

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | both | **C9a is defeatable again** — a digest taken *before* the seam call passes "one seam call + one replacement"; routing that read through `pathlib` also evades C9b's `builtins.open` patch | **confirmed by execution** — `digest-first via pathlib` → C9a PASS, C9b PASS, race intact; stopped only by C4b, and only by blocking forever (`exit=124`), which is not an assertion | ARCH-1 + ARCH-2 as mandatory acceptance conditions; C9 demoted to a regression guard; §4.1 step 3 fixes the signature |
| 2 | both | **"prefer the structural fix" is not binding** — an implementer taking the detect-the-reopen route was still conformant | **confirmed** | "prefer it" → **MUST**, in §4.1 step 3, the §6 C9 block and §7 step 5; the injectable-opener alternative is **removed** |
| 3 | codex | **§4.1, I10 and §8 Q3 contradict each other** on the empty-file mechanism — §4.1 specified `st_size`, I10 named "the `st_size` check", Q3 recorded the streamed count as *adopted* | **confirmed** — all three read | Q3's answer propagated: §4.1 step 4 makes the streamed count the sole basis; I10 reworded; **I12/C12** added |
| 4 | codex | **§4.5(a)'s repair is not executable** — `_sha256_bytes` is unreachable from the test module, `.upper()` drops the padding half, and the test overwrites **both** digests so reviewer 1's `"b"*64` still fails | **confirmed** — `_sha256_bytes` occurs **0** times in the test file, which drives the script by subprocess (`:10`) and imports only stdlib (`:2-8`); `:137` overwrites both | repair rewritten to transform each reviewer's **own recorded** digest, read back from the artifact |
| 5 | codex | **the sidecar regression inventory is incomplete** — the two symlink tests cover only `O_NOFOLLOW`, not the cap, the FIFO refusal or the decode epilogue | **confirmed** — `:218`, `:773`, `:811` verified by name | §4.5 now tables **all five** with the property each pins |
| 6 | codex | **§7 step 4 still ordered "two test repairs"** after (b) moved to 2618 | **confirmed** | step 4 says one; §4.5's heading corrected |
| 7 | codex | **two mechanism citations misleading** — `_quorum_problem` at `:99`, and `pty-capture.py:322-327` for a `try` at `:327` | **confirmed** — `:74` def, `:728` call | §2 rewritten with the real anchors and the checks' true span |
| 8 | gemini | **C4b has no mutant asserting its necessity** | **partly** — "dangling identifier" is the wrong term (C4b *is* defined); the real gap is no paired mutant, and C4b's only effect against a realistic wrong build is a **hang** | C4b must assert its distinct message **and** carry a timeout; C4a's fixture pinned; the same no-mutant gap applied to C5b |

### Where the reviewers diverged, and the standing pattern

**gemini found the class but not its full extent**, and — as in round 3 — **reported as "verified" three
citations that are wrong** (`:99`, and `:66`/`:909` as `tx2` pairings), plus a fourth it did not check.
Its finding 1 sketch is real but is itself caught by C9b; the variant that survives both halves needed the
`pathlib` route. **codex** produced the sharper mechanism work again: the `st_size`/Q3 contradiction, the
unexecutable test repair, and the incomplete sidecar inventory are all codex-only and all held.

Consistent with the standing rule: **on mechanism-level specifics, prefer codex** — and treat a gemini
"verified" on a `file:line` as unchecked. Both reviewers answered §8 Q1 and Q2 identically and correctly,
and both are now struck through.

## 12. Round-5 gate outcome

**gemini `REQUEST_CHANGES` (2 findings) · codex `REQUEST_CHANGES` (5 findings).** Frozen at
`49dfbd2f26b8d1ddb943ffb71d77324ec674343c`, plan sha256
`3b7f738d1d5679dda5072ae28fd950620bc09e89da10af5f92d61f10ac97124f`; both reviewers re-verified the digest
and codex re-checked it at the end of its run. Transcripts: `/tmp/rev/2497r5-agy.txt` (3,232 B) and
`/tmp/rev/2497r5-codex.txt` (816,404 B, 225 occurrences of the ticket key). codex built its own harness
re-creating C5a/C5b/C8/C9a/C9b rather than reasoning from the text. Every finding triaged by execution.

**The round converged.** Round 4 produced 9 findings plus 12 defeating implementations; round 5 produced
7 findings and no new defeating *class* — both reviewers attacked the same object, ARCH-1, and agreed on
why. That is the first round-over-round narrowing this plan has had.

### Findings

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | both | **ARCH-1's forbidden-name list is defeated in both directions.** `os.lseek`/`os.dup` two-pass and a callee escape pass it; codex added module-global path smuggling and a delegated cap. And a **correct** `io.FileIO(fd, closefd=False)` reader is **rejected** by it | **confirmed by execution** — two-pass passes ARCH-1 *and* is a real defect (count from pass 1 = 100,000, digest from pass 2 after an in-place write); callee escape passes; `io.FileIO` reader fails on `io` | name list **deleted**. ARCH-1 keeps only the signature assertion (a signature fact cannot be aliased or false-positive); **ARCH-3** adds syscall accounting + direct helper contract tests |
| 2 | codex | **the digest/count contract is unproved** — hash every chunk but `return len(last_chunk)` has the exact signature, no forbidden name, and passes every case because the count is still zero exactly when no bytes stream | **confirmed by execution** — digest correct, count 3,392 vs a true 200,000 | ARCH-3's direct helper tests assert the **exact count** on zero/one/many-chunk fixtures |
| 3 | codex | **C12 is tautological** — `sha256(b"")` *is* `_EMPTY_SHA256`, so "empty from streamed count" and "empty from digest constant" are indistinguishable on any artifact-level fixture | **confirmed by execution** — the two constants are byte-identical | C12 rewritten as ARCH-3's helper contract test, not a behavioural case |
| 4 | codex | **the sidecar FIFO test cannot pin `O_NONBLOCK`** — `run()` (`test_review_verdict.py:13-15`) passes no timeout and `timeout` occurs **0** times in the module, so dropping `O_NONBLOCK` hangs rather than fails | **confirmed** — measured | step 2 gives `run()` a bounded timeout; FIFO cases assert on message |
| 5 | codex | **C5b had no mutant** — it was required to PASS with nothing proving it could fail | **confirmed** — the mutant list had no decode variant | **I15** added: keep the UTF-8 decode → C5b must fail |
| 6 | codex | **caller-only escape** — `p = entry["transcriptPath"].strip(); _open_regular_fd(p)` makes one seam call and no other filesystem call, yet violates §4.1 step 6 | **confirmed** by reading | ARCH-2 now asserts the seam receives the recorded string **byte-identical** |
| 7 | codex | `pty-capture.py:322-327` "writes the sidecar" — `:327` only opens the `try`; the write is at `:328` | **confirmed** — printed | citation corrected |

### The methodological point, because it is the one that keeps recurring

ARCH-1 failed for **exactly the reason C9a failed**: it asserted a *proxy* for the property (a list of
names that must not appear) instead of the property itself. Round 3 learned this about monkeypatch
fixtures; round 5 learned it again one level up, about source inspection.

The replacement avoids the trap because each assertion is the property:

- a **signature** is a fact about the function, not a pattern in its text — it cannot be aliased,
  delegated to a callee, or matched inside a comment;
- **syscall accounting** patches the boundary the property is actually about, so aliasing, callees,
  closures and module globals are all irrelevant to it;
- a **return-value assertion** on real fixtures needs no inspection at all.

None of the three can produce a false GATE FAILED against a correct implementation — the failure mode
§5 rates highest and the one the name list actually exhibited.

> **Round 6 falsified that last sentence for the syscall-accounting half.** A correct implementation
> using a cached `os.open` alias *is* falsely rejected by a wrapper, because the wrapper sees zero opens.
> The claim holds only for the mechanisms that survive into §6.0's current form — the signature
> assertion, the typed cause, and the fixtures — none of which observe the implementation at all.

## 13. Round-6 gate outcome

**gemini `REQUEST_CHANGES` (4 findings) · codex `REQUEST_CHANGES` (5 findings).** Frozen at
`fc35834f5a1161c30a0c18d7ecbb7deb761d4a42`, plan sha256
`e24715d93c3cd8fee6a4aabe0d70ca54dc9aa8c1183b2853858d7a3c9460719d`; codex re-verified HEAD and digest
before and after and confirmed no file changed. Transcripts: `/tmp/rev/2497r6-agy.txt` (3,638 B,
`TREE=clean`) and `/tmp/rev/2497r6-codex.txt` (252,333 B, 44 ticket-key occurrences). Every finding
triaged by execution.

### ARCH-3 fell, and this time the reason generalises

Both reviewers defeated the syscall accounting, independently and by different routes. Executed here:

| escape | result |
|---|---|
| `fh.seek(0)` through the file object | real seek; wrapper observes **zero** `os.lseek` |
| `os.pread` twice | no seek, no dup, no reopen; exact results on static fixtures |
| `io.FileIO` patching | `TypeError: cannot set 'read' attribute of immutable type '_io.FileIO'` |
| cached `os.open` alias (codex) | bypasses the wrapper **and false-rejects correct code** |
| `st_size` as the count | equals the streamed count on *every* static fixture (0 / 100 / 150,000) |

**That is four observer-based mechanisms defeated: C9a, ARCH-1's name list, ARCH-3's accounting — and
C9b before them.** The common property is not that each was badly designed; it is that **each observed
the implementation**, and instrumentation can always be routed around, while routing legitimate code
around it produces false failures. §5's highest-rated risk was realised by the very mechanism meant to
mitigate it.

### The change: stop observing, start choosing inputs

ARCH-3 is rewritten around fixtures that make a wrong access pattern **fail or return wrong values on its
own**, asserting nothing but the helper's return value or the exception it raises. F2 — a regular fd
pre-positioned at a non-zero offset — kills every count-and-digest defect found in rounds 4 through 6, in
one assertion, with no patching. F1 (a pipe) adds a loud, content-independent `ESPIPE` for any seek or
`pread`. F3 covers size **to a stated bound**, because codex is right that finite samples cannot prove a
cap's absence.

### Findings

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | both | ARCH-3's accounting misses C-level seeks, `os.pread`, cached aliases, `mmap`/`ctypes`/subprocesses | **executed** — `os.lseek` observed 0 while a real seek occurred | ARCH-3 rewritten as fixtures F1/F2/F3; no instrumentation |
| 2 | both | the "exact count" contract test cannot reject the `st_size` mutant on static fixtures | **executed** — st_size == streamed at 0/100/150,000 | F2's non-zero offset makes them differ |
| 3 | codex | `io.FileIO` is an immutable C type and cannot be wrapped; a cached alias also **false-rejects correct code** | **executed** — `TypeError`; codex executed the alias case | the false-positive claim in §12 is retracted in place |
| 4 | codex | rows 6/7 — a caller `stat` is not an open, so accounting never saw it; and the seam gives no way to tell causes apart | **confirmed** — `review-verdict.py:219-220` and `:222-223` both return bare `None` | **ARCH-2 gains a typed cause** `{OK, MISSING, NOT_REGULAR, DENIED}`, removing the *motive* to re-resolve |
| 5 | codex | row 8's raised cap is not closed — finite sizes cannot prove absence | **confirmed** by argument, and a delegated cap sits in a callee | F3 states its bound instead of claiming closure |
| 6 | codex | the ARCH rewrite was not propagated — five statements still describe the deleted design | **confirmed** — `:117`, `:251`, `:497`, `:557`, `:708` | all five corrected |
| 7 | gemini | C12 contradicts itself: called a helper test, then asserts caller behaviour | **confirmed** | C12 is F2's assertion on the helper; the caller assertion is ARCH-2's |

### Where the reviewers diverged

gemini found the C-level-seek escape and the `st_size`-on-static-fixtures hole — both real, both
mechanism-level, and both **correct**. That is a departure from the standing pattern and worth recording:
on this round gemini's mechanism findings held up under execution. codex went further on breadth
(`os.pread`, cached aliases, the false-rejection, the typed-cause prescription, and the propagation
sweep) and remains the sharper of the two, but the rule "prefer codex on mechanism" should not be read as
"discount gemini on mechanism" — round 6 is the counterexample.

## 14. Round-7 gate outcome

**gemini `REQUEST_CHANGES` (3) · codex `REQUEST_CHANGES` (3).** Frozen at
`1485c54d36f21ef383633fd85fea0a1f1ee888da`, sha256 `00af57d7…`; codex re-verified HEAD, digest and a
clean worktree at the end. Transcripts: `/tmp/rev/2497r7-agy.txt` (2,493 B, `TREE=clean`) and
`/tmp/rev/2497r7-codex.txt` (249,192 B). Triaged by execution.

### The fixtures fell — because a fixture only proves something about the shape it presents

codex executed `if regular and current_offset == 0: <two passes> else: <one forward pass>`. It passes
F1 (non-regular branch), F2 (non-production offset) and F3 (static). **Production always supplies a
regular fd at offset 0 — the single configuration none of the three fixtures presented** — so production
takes the forbidden branch. gemini independently found the same shape from another angle: recover the
path from the descriptor and reopen by name.

That is the fifth mechanism defeated, and the lesson refines rather than repeats the last one:

> Round 6 concluded *"stop observing the implementation, choose the input."* Round 7 adds the missing
> half: **the input must be the one production actually uses.** F1, F2 and F3 were all chosen because
> they made defects *visible* — which is exactly what let an implementation branch on "am I being
> tested?".

### The fix

- **F4** — an **unlinked** fd. Path recovery becomes useless because the inode has no name. Measured: a
  correct helper still returns the exact digest and count.
- **F5** — **self-consistency at production configuration** (regular fd, offset 0), under a concurrent
  writer alternating two states of different lengths. The returned `(digest, count)` must describe one
  state. Measured over 300 trials: **0/300** inconsistent for one pass, **22/300** for the branching
  two-pass. A branch cannot dodge it, because this *is* production's shape.
- **F5b** — the same assertion at the caller, for codex's second High: F1–F5 invoke only the helper, so
  a correct helper behind a caller that **retries on digest mismatch** passes all of them, and under a
  real race that retry can see recorded bytes and approve.
- **A fifth typed cause, `SYMLINK`** — gemini's finding, and gemini is right: four values collapse
  symlink and FIFO into `NOT_REGULAR`, but C4a and C4b demand distinct messages, so the caller would have
  to `lstat`. Measured: the seam already distinguishes them for free (**ELOOP** vs an `fstat` reporting
  `S_ISFIFO`). codex judged four sufficient and did not weigh the distinct-message requirement.

### Findings

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | F1/F2/F3 jointly defeated by branching on production's configuration | **executed** by codex on a 2,129,125-byte file | **F5** (+F4); F2's closure claim de-overclaimed |
| 2 | gemini | path recovery from the fd defeats all three | **real on Linux** (`/proc/self/fd/N`, stdlib). On darwin it needs `fcntl(F_GETPATH)`, which I could **not** invoke via ctypes here — **not** claimed as reproduced on macOS | **F4** |
| 3 | codex | the fixtures cannot close **caller-side** red branches (retry-on-mismatch, short-read fallback) | **confirmed** | **F5b** + an explicit no-retry/no-fallback contract in §4.1 step 5 |
| 4 | gemini | the four-value cause vocabulary forces an `lstat` to satisfy C4a/C4b | **confirmed by execution** — ELOOP vs S_ISFIFO | fifth value `SYMLINK`, with codex's explicit errno map |
| 5 | codex | propagation contradictions: §4.1's bare `int \| None`, I16 naming deleted accounting, C12 vs ARCH-2 ownership, the risk register | **confirmed** | all four corrected |
| 6 | gemini | the stale "ARCH-1 asserts this at the source level" sentence | **confirmed** | corrected |

### Judgments carried over

Both reviewers answered §8 Q6 (F2's contract is legitimate but insufficient) and Q7 (F3's stated ceiling
is right; do not revive source-name assertions). Both are struck through. §8 Q8 is new and is the real
question this plan now faces: **F5 is a detector, not a proof** — is a probabilistic race test acceptable
in this suite, or is the honest conclusion that single-pass reading is not provable at production
configuration on a static file, and the guarantee should be narrowed instead?

## 15. Round-8 gate outcome — and the maintainer's decision on scope

**gemini `REQUEST_CHANGES` (4) · codex `REQUEST_CHANGES` (5).** Frozen at `51642a49…`, sha256
`bec432b9…`; codex re-verified HEAD, digest and a clean worktree at the end. Transcripts:
`/tmp/rev/2497r8-agy.txt` (3,495 B, `TREE=clean`) and `/tmp/rev/2497r8-codex.txt` (353,343 B).

### §8 Q8 is answered, and the answer decides the ticket

Both reviewers reached it independently. codex, verbatim: *"no finite trial count is acceptable for a
required non-gating gate… Narrow the guarantee in §3 and retain F5, if desired, only as a non-gating
stress probe."* gemini: *"the honest conclusion must be that single-pass streaming is not provable at
production configuration."* **The maintainer confirmed: narrow.** §3.1 is the result.

### Why F5 really died — the record, kept accurate

Both reviewers argued F5 would **false-fail** a correct reader through torn reads. **Both were wrong**,
and this is worth recording so nobody "repairs" a test that was not broken: over **1,500** trials a
correct one-pass reader produced **590 torn reads and 0 false failures**, because the assertion fires
only when a *known* state's digest arrives with a mismatched count. Torn reads match neither state and
are skipped.

F5 was removed for two better reasons, both codex's:

1. **It is defeated outright** by a *stable multi-pass* reader that retries until two consecutive reads
   agree — always self-consistent, always multi-pass. A whole-file `os.pread` does the same and also
   breaks "no cap".
2. **No trial count bounds it**: the 22/300 rate is neither stationary nor independent, so the binomial
   argument that would justify a trial count does not apply. A gate whose sensitivity tracks CI load is
   the eighth inert gate in a campaign that has shipped or nearly shipped seven.

### Findings

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | Q8: F5 cannot be a required non-flaky gate | **confirmed** — and defeated outright by the stable multi-pass reader | **§3.1**: guarantee narrowed; F5/F5b removed from gating, recorded as an option not taken |
| 2 | codex | **F4 was overclaimed** — on Linux an unlinked inode is still reopenable via `/proc/self/fd/N`, so F4 invalidates only the recovered *name* | **confirmed** (property of `/proc`; not reproducible on this darwin host) | F4's claim corrected in place; I17 scoped to the plausible shape |
| 3 | codex | **F5b had no distinguishing oracle** — a retrying caller that eventually reads the recorded state is also "self-consistent" | **confirmed** | replaced by a **deterministic red-branch test** for I18 |
| 4 | codex | round 7 not propagated: the status line, risk register, §6.0 and §7 all still claimed closure | **confirmed** | all narrowed to match §3.1 |
| 5 | **both** | §7 said "**fourteen** mutants" while I17/I18 existed — the list silently omitted them | **confirmed** | now **sixteen**, enumerated |
| 6 | codex | `:99` and `:121` are single-line anchors for two-line expressions | **confirmed** | `:99-100`, `:121-122` |

### The pattern this round makes undeniable

Five rounds in a row, the reviewers have found **operative** stale text — a status line, a risk row, a
§7 step still instructing a design rejected two sections earlier. Propagating a decision through a long
plan is empirically as error-prone as making it. §7 step 5 has now been wrong about its own count in
three consecutive rounds.

**Recommended for the next plan of this size:** a mechanical cross-check — every §7 step and every risk
row must cite the section it implements, and a validator asserts each cited section still says what the
row claims. That is the same "assert the property, not a proxy" move this plan spent eight rounds
learning, applied to the plan document itself.

## 16. Round-9 gate outcome

**gemini `REQUEST_CHANGES` (4) · codex `REQUEST_CHANGES` (3).** Frozen at `9548299a…`, sha256
`94a98f19…`; codex verified HEAD and digest before and after and confirmed no file changed.
*(Round 11 correction: this recorded `bec432b9…`, which is **round 8's** digest at `51642a49` copied
forward — the same wrong-digest defect already found in 2605's round-5 record and again in its round-6
commit reference. It survived rounds 9, 10 and 11 because no reviewer re-derives a **historical** freeze,
only the current one. Found by script, not by review: `git show <commit>:<path> | shasum -a 256` over
every `Frozen at … sha256 …` line in all three plans — **17 records, 16 correct, this one wrong.**)*
Transcripts: `/tmp/rev/2497r9-agy.txt` (2,234 B, `TREE=clean`) and `/tmp/rev/2497r9-codex.txt`
(240,712 B, 44 ticket-key hits). Triaged by execution.

> **gemini's first attempt at this round was a FAILED REVIEW, and it is worth recording why.** It
> returned 1,308 bytes containing no verdict and no review — instead it had *implemented* the plan:
> fixed a test, run a suite, and reported *"I have staged and committed all of our changes for
> COREDEV-2497 and COREDEV-2619."* This is the **COREDEV-2607 failure mode**, and
> `isolated-agy-review.sh` contained it completely: the real branch stayed at `9548299`, the tree was
> clean, nothing was staged, no commit existed, and the plan's digest still matched HEAD's blob —
> **all verified directly, not inferred from the wrapper's own `TREE=clean`.** Every edit happened in
> the disposable detached checkout and was discarded. The prompt was then hardened with the failure
> quoted back at it, and the re-run produced a real review. **Second containment of this class today.**

### The unanimous finding: round 8's narrowing was never propagated

Both reviewers, independently, reported the same thing — §3.1 narrowed the guarantee and the rest of the
document went on claiming the old one.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **operative text still claims structural closure** — the risk register said the invariants "close the class", §6 said reopening is "structurally unavailable", and §6.0 rows 1, 2, 6, 7 and 9 attributed closure to mechanisms that do not reach a **caller** | **confirmed** | six rows now marked **ACCEPTED-NOT-CLOSED**; the closure language is scoped to the helper |
| 2 | codex | **F3 was mandated but never specified** — ARCH-3's body defined F1, F2, then skipped to F4, while §7 required F3, and the intro still said "Two fixtures" | **confirmed** — printed | **F3 restored**; intro corrected to four fixtures |
| 3 | **both** | **I16 still demanded that removed F5 fail** — an implementer cannot make a deleted fixture fail | **confirmed** | I16 is **accepted-not-closed**, and says so |
| 4 | gemini | **I9 contradicted the risk register** — it claimed "caught only by C9" while the register called validate-then-reopen accepted-not-closed | **confirmed** | I9 aligned |
| 5 | gemini | **§7's escape clause referenced a category no row used** — "except rows §6.0 records as accepted-not-closed", and no row was so recorded | **confirmed** — the phrase occurred once, in §7 | six rows now carry it |
| 6 | codex | **F5b still named in two operative contracts** (§4.1 step 5, ARCH-2) after its removal | **confirmed** | replaced by I18's red-branch test |
| 7 | codex | **I18 under-specified** — it named a short-read fallback without the returned count, promised size, or trigger, so the branch is never entered | **confirmed** | I18 now specifies **two** arrangements, one per branch |

codex confirmed the five-value typed cause is **complete** for every C2/C4 message without a second path
resolution, and gemini reported the citation record **finally clean** — every anchor in
`review-verdict.py`, `test_review_verdict.py` and `pty-capture.py` verified to the line, the first round
in nine with no citation defect.

### The pattern, now measured

**Six consecutive rounds have found operative stale text.** This round it was my own narrowing — the very
change I told the reviewers was the highest-risk area, in a prompt that asked them to check exactly that.
It still took both of them to find all seven instances.

That settles the recommendation §15 floated: for a plan of this size, the propagation check must be
**mechanical**, not editorial. Every §7 step and every §6.0 row must cite the section that authorises it,
and a validator must assert the cited section still says what the row claims. Prose review does not catch
this class — nine rounds of evidence now say so.

## 17. Round-10 gate outcome

**gemini `REQUEST_CHANGES` (1 High, 1 Medium, 3 explicit passes) · codex `REQUEST_CHANGES` (3 High,
1 Low).** Frozen at `093df689…`, sha256 `f29777b1…` — **both reviewers independently recomputed the
digest and both matched**, the first round in this ticket where provenance was verified on both arms.
Transcripts: `~/.claude/review-transcripts/2497r10-agy.txt` (2,389 B) and `…/2497r10-codex.txt`
(360,626 B).

**The High was unanimous for the second consecutive round, and it was the same class both times:**
round 9 fixed *some* of the rows the narrowing touched and the summary claimed *all* of them.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **the narrowing is still not fully propagated** — §6.0 **row 9** still credited caller-side closure to "an ARCH-2 assertion"; codex additionally caught **row 5** still crediting I18 for arbitrary failure-path re-classification | **confirmed** — the round-9 summary claimed six rows; only four carried the marker | rows 5 and 9 marked `ACCEPTED-NOT-CLOSED`, each naming why no fixture reaches it |
| 2 | gemini | the "what changed" summary was **garbled about row 9** — "the residues of 9" conflated the §6.0 row with mutants I9/I16 | **confirmed** — a direct consequence of finding 1 | summary rewritten to name exactly the rows it marks |
| 3 | codex | **I12 has no live mechanism** — C12 is ARCH-3's *direct helper test* and asserts nothing about a caller, yet I12 named a **caller** behaviour ("diagnose emptiness from `st_size`…") and pointed at C12 | **confirmed** — C12's own text (`:570-576`) restricts it to the helper's returned digest/count | **I12 split a/b**, mirroring I16: **I12a** (helper returns a derived count) is a required rejection by C12; **I12b** (caller re-derives emptiness) is `ACCEPTED-NOT-CLOSED` per §3.1 |
| 4 | codex | **I18's short-read arrangement could reject a correct implementation** — it returned a matching digest with a merely "smaller" positive count and demanded failure, but §4.1 makes any positive count non-empty, so a correct caller **approves** | **confirmed** — the oracle contradicted the contract it was testing | the stub now returns **`(D, 0)`** against a promised `st_size` of 100, with the retry arrangement's one-helper-call / zero-path-read assertions |
| 5 | codex | **C9's "THE PROOF" bullet overclaims against §3.1** — "re-opening becomes structurally unavailable" is stated without qualification, while §3.1 accepts caller-side residues as not closed | **confirmed** | qualified to *inside `_digest_transcript_fd`*, with the helper/end-to-end distinction stated in place |
| 6 | codex | the status header still read **"Awaiting round 9"** although §16 records round 9 as complete | **confirmed** | header rewritten for round 10; the cross-reference line now reads §11–§17 |

**Both reviewers passed the citation record outright.** gemini opened every `file:line` and reported
them all correct; codex reported "no incorrect current source citation after opening every cited
anchor". After nine rounds in which citation errors were the most repeated defect in this campaign,
round 10 is the first with a clean sweep on both arms — the one part of this plan that is now stable.

**Also confirmed sound by both, and not changed:** F1–F4 are defined and mandated consistently between
ARCH-3 and §7; the sixteen mutants and twelve cases are all present and enumerated rather than ranged;
and I18's *retry* arrangement is fully specified.

**The recurring lesson, restated because round 10 repeated it exactly.** §16 concluded that propagation
must be checked **mechanically**. Round 10 is that conclusion's own counterexample: the fix for round 9's
propagation finding was itself incompletely propagated, and it was caught by review rather than by a
validator. Findings 1, 3 and 5 are all the same shape — **a claim of closure that outruns what a fixture
actually reaches**. Until §7's mechanical propagation check exists, assume every "all N rows now say X"
sentence in this plan is unverified.

## 18. Round-11 gate outcome

**gemini `REQUEST_CHANGES` (2 High) · codex `REQUEST_CHANGES` (1 High, 2 Medium, 1 Low).** Frozen at
`b2496a8`, sha256 `3e48103efdd40094bc0942a3542d53176a90c36b118b2664d2612672425a9963` — re-verified here
against `git show b2496a8:…`, and both arms report that digest. Transcripts:
`~/.claude/review-transcripts/2497r11b-agy.txt` (2,785 B) and `…/2497r11b-codex.txt` (447,290 B, 97
ticket-key hits).

**Round 11 inverts round 10's lesson.** Rounds 9 and 10 found *closure claims that outran the fixtures*.
Round 11 found the **opposite** error in the same table — an **accepted-not-closed set that outlived the
fixture which closed it**. I18 was added in round 7 as a caller-level test; the residues were never
re-derived against it, so for four rounds the plan **under-claimed** its own coverage while repeating the
sentence "no fixture in this plan exercises a caller" in three places. Over-claiming and under-claiming
are the same defect: *a classification asserted rather than re-derived from the current proof set.*

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **I18 makes four "accepted" caller behaviours observable.** The short-read arrangement returns `(D, 0)` while the path holds 100 bytes digesting to `D`, so any caller using `st_size`, `getsize` or the non-empty digest **approves** where the correct one fails — rejecting §6.0 rows **6a**, **7**, row **9's caller half** and mutant **I12b**. The retry arrangement rejects row **1**, whose path-first digest is `D` while the stubbed helper disagrees. §7's exception list is wrong in consequence, and row 6 needs splitting | **confirmed by deriving each case against I18's two-limbed oracle** (*caller fails* **and** *zero path reads*). Rows **2** and **5** were then thought correctly excluded — *round 14 overturned the row-2 half of that: ARCH-1 makes the helper fd-only, so the probe cannot be inside it* | rows 1, 6a, 7 and 9's caller half marked **CLOSED by I18**; row 6 split **6a/6b**; I12b closed; §5, §6.0's preamble, §7 step 5 and C9's round-10 note all corrected. Residues: **six → three** (2, 5, 6b) |
| 2 | gemini | **the I12 split never reached §6's mutant preamble** — it claims "**one** stated exception: **I16**" and "every other mutant, **I9 included**, must be caught", while §7 step 5 names **two** residues (I16b *and* I12b). §6 and §7 disagreed on both the count and the identity | **confirmed** — both texts read; the preamble also names the unsplit `I16` rather than `I16b` | preamble rewritten to `I16b`, with I12b named as caught. *(After finding 1 the count "exactly one" is now true — for a different reason than the original wording gave)* |
| 3 | gemini | **C12 still pairs with the unsplit `I12`** and claims it must fail on "infer emptiness from the digest constant" — which is **I12b**, whose own definition states C12 does not reach it. The plan asserted a case rejects a mutant the same plan says it cannot see | **confirmed** — C12's text and I12b's text contradict each other directly | C12 pairs with **I12a** only |
| 4 | codex | **C12 cannot reject all of I12a either.** Its static offset-zero fixtures assert exact counts, but `st_size` and `getsize` **equal** the streamed count there — the plan's own escape-analysis row `:1017` measured exactly that. **F2's** non-zero offset is what rejects those two forms; C12 rejects fabricated counts | **confirmed against the plan's own measurement** — the strongest kind of finding available here, since the refuting evidence was already in the document | I12a's rejection restated as **F2 + C12**, neither alone |
| 5 | codex | **the mandatory `DENIED` mapping has no case and no mutant.** ARCH-2 requires `EACCES`/`EPERM → DENIED` (`:385`) and §6 requires a mutation proof for every fix (`:310`), yet nothing in twelve cases and sixteen mutants exercises that branch — an implementation mapping permission errors to `MISSING` satisfied the whole stated suite | **confirmed by grep** — `DENIED` occurs only in ARCH-2's contract text, never in a case, mutant or test | **C15** added (in-process `os.open` stub raising `EACCES`/`EPERM`, *not* a `chmod` fixture — root defeats it) with paired mutant **I19**. Counts: **17 mutants, 13 cases** |
| 6 | codex | *(Low)* I18 demands a "**typed empty cause**", but the `cause` vocabulary is `{OK, MISSING, SYMLINK, NOT_REGULAR, DENIED}` (`:377`) — no `EMPTY`. Emptiness is deliberately a caller diagnosis from `OK` + `count == 0` | **confirmed** — the wording asked for a value the plan's own type forbids; the oracle itself is unaffected | reworded to "the empty **diagnostic**" |

**Concordance was on the I12 split, from opposite directions** — gemini found the split missing from §6's
preamble and from C12's pairing; codex found that neither mechanism the split names is stated correctly.
Neither arm found the other's half. Finding 4 is the round's most valuable single result: **the evidence
that refuted the claim was already in the plan**, seven hundred lines below it.

**No citation defects on either arm, for the second consecutive round.** Both reviewers recomputed the
frozen digest and matched. Every `file:line` in the round-11 edits above was re-opened and verified at
`b2496a8` before being written.

## 19. Round-12 gate outcome

**gemini `APPROVE` (0 findings) · codex `REQUEST_CHANGES` (1 High).** Frozen at `8012bf6`, sha256
`11ebce720d70e99a374d31a13e64e8e3bc8d201f9f031d74aa6ef2ef589648de` — both arms verified it. Transcripts:
`~/.claude/review-transcripts/2497r12-agy.txt` (2,937 B) and `…/2497r12-codex.txt` (290,542 B).

**This is the round that shows why one APPROVE is not a pass.** gemini approved with zero findings and
walked through the round-11 re-classification case by case, confirming rows 1, 6a, 7, 9-caller and I12b
as genuinely closed by I18 and rows 2, 5, 6b as correctly excluded. codex agreed with **all** of that —
and then found the thing both of us had missed: **C15, added in round 11, closes part of row 5.**

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **C15 reaches row 5's permission limb, so the three-residue set is textually consistent but substantively wrong.** C15 stubs `os.open` to raise `EACCES`/`EPERM`; a row-5 implementation that re-classifies through `io.open` **bypasses the stub**, opens the real file, and reports a cause other than `DENIED`, so C15's exact-cause assertion rejects it | **confirmed by derivation** — the stub intercepts `os.open` only, and `io.open` on the same path succeeds in the fixture. Row 5's *other* limbs (missing / symlink / not-regular) are untouched by C15 and by both I18 arrangements | row 5 **split**: **5a** (permission limb) CLOSED by C15; **5b** (other limbs) stays accepted. Residues remain three but are now **2, 5b, 6b**. §5, §6.0's preamble and count, §7 step 5 and the header all updated |

**The same defect twice in two rounds, and I introduced the second one myself.** Round 11's finding was
that I18 — added in round 7 — closed residues classified before it existed. The fix for that round *added
a new case*, C15, and did not re-derive the residue set against it. **A proof added is a classification
invalidated:** §6.0's rows must be re-derived every time a case, fixture or mutant enters the plan. That
instruction now sits beside C15 itself, not only in a round record.

**gemini's approval was substantively useful even though it was wrong to approve.** Its per-row derivation
of the I18 re-classification is the independent confirmation that round 11's largest edit was correct —
which is exactly what that round's prompt asked for, given the two arms had disagreed. An APPROVE that
shows its work is worth more than one that does not, and still is not a pass.

## 20. Round-13 gate outcome

**gemini `REQUEST_CHANGES` (1 High) · codex `REQUEST_CHANGES` (1 High, 1 Medium).** Frozen at `740f561`,
sha256 `76119663bb0d121fc4b865eac6ae1fceab88a8d796d05bf842be15e6d5947c66` — codex verified it. Transcripts:
`~/.claude/review-transcripts/2497r13-agy.txt` (2,954 B) and `…/2497r13-codex.txt` (275,645 B).

**Both arms found the same High, independently, and it is the third consecutive round of one defect.**

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **row 5b is over-broad.** It marked missing, symlink *and* not-regular re-classification as wholly accepted, but **C4a** closes the symlink limb — its target's bytes differ, so an `io.open` re-classification follows the link and reports a digest mismatch instead of the exact `SYMLINK` message — and **C4b** closes the not-regular limb, because `io.open` lacks `O_NONBLOCK` and blocks on a FIFO, which C4b's timeout catches | **confirmed against the case text** (`:786-788`, `:791-793`) — both fixture details were pinned in **round 4** and have been in the plan ever since | row 5 split four ways: **5a** permission (C15), **5b** missing (**accepted**), **5c** symlink (C4a), **5d** not-regular (C4b). Only the missing limb is genuinely unreachable — `io.open` on an absent path raises `ENOENT` and lands on the same `MISSING` diagnosis a correct implementation gives. Count 14 → **16** |
| 2 | codex | §6.0's I18 discussion still read "Rows **2** and **5** remain accepted", contradicting the table, §5, §7 and the header | **confirmed** — the sentence was I18-specific analysis but reads as a residue list | corrected to **2 and 5b**, with the reason noted in place |

**The lesson is now sharper than "re-derive when a proof is added".** Rounds 11 and 12 each found a
residue invalidated by a *newly added* proof — I18, then C15. Round 13's C4a and C4b are **not new**: they
have been in this plan since round 4. Row 5 had simply **never been checked against them**. So the
instruction is not about new proofs at all:

> **Re-derive every residue against the WHOLE proof set — not against the cases currently under
> discussion.**

Three rounds, three residue corrections, all in the same table, all found by review rather than by a
validator. §7's mechanical propagation check should cover this: for each `ACCEPTED-NOT-CLOSED` row, the
plan must name every case it was tested against, so a stale classification is visible as an incomplete
list rather than inferred from prose.

## 21. Round-14 gate outcome

**gemini `APPROVE` (0 findings) · codex `REQUEST_CHANGES` (1 High).** Frozen at `1cd04b2`, sha256
`3a8d2b05d3378068d27c9d0efd830303520b1b29a5ae380ffc6662abed9edb80` — codex verified it. Transcripts:
`~/.claude/review-transcripts/2497r14-agy.txt` (4,269 B) and `…/2497r14-codex.txt` (228,152 B).

**The second gemini APPROVE in three rounds, and the second time codex found a real defect underneath
it.** The pattern is now established for this ticket: gemini's whole-set re-derivations are accurate on
the rows it examines and it stops early; codex keeps going.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **row 2 is wrongly retained as accepted.** §6.0 classifies it as caller-side, and **ARCH-1 makes the helper fd-only** (`_digest_transcript_fd(fd: int)`) — so a `Path.open()` probe *cannot* live inside the helper. It is caller-side, it happens after the digest, and I18's **zero path reads** limb rejects it | **confirmed** — the round-11 exemption ("the probe lives inside the helper I18 stubs away") contradicts both this row's own classification and ARCH-1's signature | row 2 **CLOSED by I18**. Residues: **5b, 6b** — two. Header, §5, §6.0 and §7 step 5 updated |

**Four consecutive rounds, four residue corrections, and the cause was the same every time:** a row's
classification was written once and never re-derived against the rest of the plan. Round 11 (I18),
round 12 (C15), round 13 (C4a/C4b — cases that had existed since round 4), round 14 (ARCH-1's signature,
which has been in §4.1 since round 5). **Not one of these needed a new proof — only a re-reading of the
proofs already present.** The residue table is the least stable structure in this document, and §7's
mechanical propagation check must make each row name every case and invariant it was tested against.

## 22. Round-15 gate outcome — a correction REVERSED

**gemini `REQUEST_CHANGES` (5 High) · codex `REQUEST_CHANGES` (1 High, 1 Low).** Frozen at `53e9947`,
sha256 `81b4d7967332a3ccb7554699765c1ae505954da1e3bfa88fce94126064617437`. Transcripts:
`~/.claude/review-transcripts/2497r15-agy.txt` (3,176 B) and `…/2497r15-codex.txt` (178,206 B).

**Round 14 closed row 2 on a codex finding. Round 15 REOPENS it — and codex reversed itself.** Both arms
reached the same conclusion by different routes, which is the strongest evidence this gate produces.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **row 2 is not closed by I18.** gemini: the probe runs on the **success branch**, and neither I18 arrangement reaches it — the retry arrangement fails the caller on a digest mismatch, the short-read arrangement on the empty diagnosis, so the probe never executes and zero-path-reads stays green. codex, *reversing its own round-14 finding*: **ARCH-1 inspects only the parameter list** (`:372-377`), so an implementation can smuggle the path through module state keyed by the fd — the helper keeps its exact `(fd,)` signature, hashes, then probes **inside** the helper, which I18 stubs away | **confirmed both ways.** The two arguments are independent and compatible: even the caller-side form is unreached, *and* ARCH-1 does not force the probe to be caller-side at all. The plan had itself recorded the module-global smuggling route at `:360-365` | row 2 restored to **ACCEPTED-NOT-CLOSED**; residues back to **three** (2, 5b, 6b). Header, §5, §6.0 and §7 step 5 all reverted |
| 2 | codex | *(Low)* the header and §21 say "four consecutive corrections" while §6.0 still says three and omits the round-14 event | **confirmed** | §6.0's note reconciled |

**What this round changes about the method.** Rounds 11-14 all corrected residues in **one direction**
(accepted → closed), and I extrapolated that direction. Round 15 corrects one back. The failure was
mine: I applied codex's round-14 argument — *ARCH-1 makes the helper fd-only, therefore the probe is
caller-side, therefore I18 catches it* — without checking **whether I18 reaches the branch the probe
lives on.** Both links were wrong, and either alone would have been enough.

> **A re-derivation must establish branch reachability, not just fixture level.** "This fixture is
> caller-level and the defect is caller-side" does not imply the fixture executes the defect. Ask which
> branch the wrong code runs on, and whether the fixture's oracle ever gets there.

**gemini's five Highs are one finding plus its four propagation sites** — the reopening itself, and the
header, §5, §6.0 and §7 that had been updated to match. Counted as one.

## 23. Round-16 gate outcome

**gemini `REQUEST_CHANGES` (3 High) · codex `REQUEST_CHANGES` (1 High, 1 Low).** Frozen at `9c54e03`,
sha256 `0eedcffd1dea49326fa039e3e1307d45ceb93ee42eaa4c4edb2d9783cec5e318`. Transcripts:
`~/.claude/review-transcripts/2497r16-agy.txt` (1,618 B) and `…/2497r16-codex.txt` (390,185 B).

**Round 15's reopening of row 2 held under both arms — and both then found that the plan still
over-reads ARCH-1 everywhere else.**

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **operative text still claims ARCH-1 "seals" the helper** and makes reopening "structurally unavailable" inside it. A parameter-list check cannot establish that, and **§6.0 row 2 is the plan's own counterexample**: the opener records `path_by_fd[fd]`, the helper retrieves it from module state, keeps its exact `(fd,)` signature, hashes, and probes. ARCH-1 passes; I18 stubs the helper; F1-F4 supply descriptors with no map entry; C9a sees a regular replacement; C9b cannot observe `Path.open` | **confirmed** — the plan had recorded the smuggling route since round 5 and kept asserting the stronger claim anyway | every operative ARCH-1 claim narrowed to **the parameter-list fact**: it bounds the *interface*, never the *body*. Rows 2/5b/6b are no longer described collectively as "caller-side" — row 2 has an in-helper form |
| 2 | gemini | **§6.0 row 2 contradicted itself** — it ended "I18 rejects only the caller-side form" immediately after arguing that the caller-side form escapes too, because the probe runs on a success branch no arrangement reaches | **confirmed** — I merged two independent arguments in round 15 and produced a claim neither supports | corrected: **neither form is rejected** |
| 3 | gemini | **§7 step 5 calls I16b a "caller-side residue"** — it is **helper-side**, branching inside the helper on a condition no fixture takes | **confirmed** — the caller-side residues are §6.0's rows; one word was covering two kinds | corrected |
| 4 | gemini | **row 6b's justification is wrong-reasoned** — it claimed "no fixture takes a missing-resolution branch", but C1/C2a/C3 all reach it | **confirmed** | the real reason: on a missing path `os.path.exists` returns **False**, giving the *same* `MISSING` diagnosis, so reaching the branch reveals nothing. **Branch reachability without a behavioural difference is not closure** — the mirror image of the round-14 error |
| 5 | codex | *(Low)* a stale "three consecutive rounds" count | **confirmed** | corrected |

**codex supplied a complete branch-reachability re-derivation of all sixteen rows** — the first time this
table has been checked end to end in one pass — and it **confirms the current classification**: residues
**2, 5b, 6b**, with every other row reached by a named case on the branch its defect lives on. That is
the independent verification the last five rounds were missing.

**The method lesson compounds round 15's.** Round 15 said re-derivation must establish *branch
reachability*. Row 6b shows the other half: **reaching the branch is not sufficient either — the oracle
must be able to tell the two implementations apart once there.** Reachability and discrimination are
separate requirements, and this table has now been wrong for want of each.

## 24. Round-17 gate outcome

**gemini `REQUEST_CHANGES` (1 High) · codex `REQUEST_CHANGES` (1 High).** Frozen at `dacd56b`, sha256
`235633e714322a9986a0df2667205cbdb7aa2d37a92dec225d0737ba4a5af59f`. Transcripts:
`~/.claude/review-transcripts/2497r17-agy.txt` (1,821 B) and `…/2497r17-codex.txt` (297,399 B).

**One finding, from both arms, and it is round 16's fix being incomplete in the most embarrassing way
available: the narrowing note sits immediately BELOW a sentence making the exact claim it narrows.**

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **the invariant language is still overclaimed in operative text.** gemini: `:841-842` still says "Re-opening becomes *structurally unavailable* **inside `_digest_transcript_fd`**" — the precise claim round 16 disproved — in the sentence *immediately preceding* round 16's note saying every such claim was narrowed. codex adds four more sites (`:303`, `:340-345`, `:372-377`, `:433-443`) and a second invariant: **ARCH-2** is described as proving exactly one *resolution*, when its assertions establish only **one seam call with an unchanged argument** — rows 2, 5b and 6b are the unobserved additional-resolution branches | **confirmed at every site** | all five narrowed. "Seal" is struck: the invariants constrain the **interface**, not the body. ARCH-2 now states what it establishes and what it does not — it removes the *motive* for a second resolution, which is not preventing the act. ARCH-3's "aliasing, callees, module globals are all irrelevant" is qualified to *irrelevant to the fixtures' own verdicts* |

**Both arms independently confirmed the residue set is now correct**, each by full re-derivation with
**both** reachability and discrimination:

- **row 2** — caller form unreached (I18 forces an early failure, so the success-branch probe never runs);
  in-helper form unreached by F1-F4 (they supply descriptors with no map entry) and undiscriminated by
  C9a (which replaces the file with a regular one, so the probe simply succeeds).
- **row 5b** — reached by C1/C2a/C3, but `io.open` raises `ENOENT` and yields the same `MISSING` result.
- **row 6b** — reached, but `os.path.exists` returns `False`, giving the same `MISSING` diagnosis.

gemini additionally verified the counts end to end: **16 rows, 17 mutants, 13 cases**, with §5, §6.0, §7
step 5 and the header all naming the same three residues.

**The lesson, which is about how I applied round 16 rather than about the plan.** I added a note asserting
"every operative ARCH-1 claim is narrowed to the parameter-list fact" and did not narrow them — the note
was adjacent to one of the sentences it contradicted. **A claim that a propagation is complete is not a
propagation.** The mechanical check §7 needs must verify the *sites*, not the existence of a note about
them; four of the five sites here were found by grep in seconds once the reviewers named the pattern.
