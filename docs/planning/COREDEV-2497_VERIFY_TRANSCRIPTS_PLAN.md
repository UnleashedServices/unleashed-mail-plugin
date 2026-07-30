# COREDEV-2497 — `verify` must re-check the transcripts it approved

**Status:** Planning — round 4 gated (**gemini REQUEST_CHANGES ×3 / codex REQUEST_CHANGES ×6**, plus an
adversarial sweep that defeated the §6 proof set with **12 distinct implementations, all executed**). §6 is
restructured in response — see §11. Awaiting round 5.
**Ticket:** `COREDEV-2497` (Epic `COREDEV-2485`)
**Split out on 2026-07-30 (maintainer decision):** `COREDEV-2618` (verdict-token cross-check) ·
`COREDEV-2619` (per-run transcript paths). **This plan is now §4.1 + §4.2 only.**
**Sequencing:** `COREDEV-2619` should land **first** — see §7.
**Measured against:** HEAD `7447d79` (v2.6.4). Worktree `.claude/worktrees/opus5-review`.
**Last Updated:** 2026-07-30 (round 4, post-gate revision)

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
calls `_quorum_problem` at **`:728`** — the function is defined at **`:74`**, and its checks span
`:84-147`: reviewer **count/shape** (`:84`), duplicate and stray **names** (`:86`, `:95`), **status
membership** (`:99`), the empty-file hash (`:121`) and digest **syntax** (`:144`). It **never resolves
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

1. Extract the prologue as **`_open_regular_fd(path) -> int | None`** — a *stable module-level name*, so
   the single-descriptor property has a test seam. Round 2 described this split but never named it, which
   is why no case could pin it.
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
   branch to "classify the cause", not on a retry, and not as a short-read fallback. §6's ARCH-1
   invariant asserts this at the source level, because the sweep showed every one of those forms passes
   a behavioural case set.
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

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The fix is read as making the gate unforgeable | **High** | §3's ceiling in code + CHANGELOG, with the measured 17-byte floor |
| A legitimate large or non-UTF-8 transcript is rejected — the fix worse than the defect | **High** | C5's two halves must **PASS**; I6 is the mutant that reintroduces the cap |
| The digest check is silently gutted while repairing §4.5(a) | **High** | §4.5 names the trap and the correct repair; C2c must FAIL for any C-case green to mean anything |
| Tightening breaks the non-approving recovery path | Medium | §4.2 + C8, and **C11** for the case-sensitivity variant |
| A validate-then-reopen implementation ships green | **High** | **ARCH-1 + ARCH-2**, not I9/C9. Round 4 proved behavioural detection insufficient four times over — see §6.0 |
| Factoring regresses the sidecars | Medium | Epilogue untouched; §4.5 now names **all five** tests — `:200`, `:218`, `:757`, `:773`, `:811` — not just the two symlink ones |
| The whole change is inert because tests only cover `write` | **High** | Every §4.1 test must mutate the transcript on disk **between** `write` and `verify` — see §6's trap |
| **The proof set is defeated again in round 5** | **High** | §6.0's structural invariants close the *class*. The residual behavioural cases (C11–C14) cover only what lives outside the fd-only helper |

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

Adding a case per escape is the move that produced rounds 2, 3 and 4. **So the class is closed
structurally instead**, and the behavioural cases are kept only for what genuinely lives outside the
sealed helper.

**Fairly stated, the existing set does work for what it targets.** The sweep confirmed by execution that
each control mutant is caught by exactly the case §6 claims: I1 only by C2c, I2 only by C2a-on-reviewer-2,
I3 only by C8, I4 only by C3, I6 only by C5a, I9 only by C9a, I11 only by C10. Round 3's C9a seam-assert
is real and load-bearing. The set is not wrong; it is **incomplete in a way more cases cannot fix.**

#### The two structural invariants — these are acceptance conditions, not preferences

- **ARCH-1 — the sealed digest helper.** `_digest_transcript_fd(fd: int) -> tuple[str, int]` takes the
  descriptor and nothing else. A test inspects the shipped source (AST or
  `inspect.signature` + `inspect.getsource`) and asserts: its parameter list is exactly `(fd,)`; its body
  contains **no** reference to `open`, `io`, `pathlib`, `os.path`, `os.stat`, `os.lstat`, `os.open`,
  `os.replace` or any name bound to the transcript path; and it contains **no** comparison against a size
  constant. **This single assertion kills the re-open class, the second-resolution class and the
  raised-cap class at once** — they become unwriteable rather than undetectable.
- **ARCH-2 — the caller resolves the path exactly once.** The function that resolves a reviewer's
  `transcriptPath` calls the seam once per entry and passes only the resulting fd onward. A test asserts
  that between reading `transcriptPath` from the artifact and returning a verdict for that entry, the
  recorded string reaches **no** filesystem call other than the single `_open_regular_fd`. Assert it
  structurally (as ARCH-1) **and** behaviourally by counting seam calls per entry, so neither a source
  refactor nor a runtime trick alone can satisfy it.

**Why structural and not behavioural:** the sweep's surviving implementations are all *behaviourally
indistinguishable* from the correct one on every input the plan enumerates. They differ only in shape.
A shape defect is cheapest to assert on the shape.

#### The 12 defeating implementations, and what closes each

Every row was **executed** against a harness that re-creates C1, C2a/b/c, C3, C4a/b, C5a/b, C8, C9a
(with round 3's non-vacuity assertions), C9b and C10, and that a correct baseline passes.

| # | the wrong implementation | property it violates | closed by |
|---|---|---|---|
| 1 | digest via `pathlib.Path(path).read_bytes()` **first**, then "confirm" with the seam | the trusted bytes never come from the validated fd | ARCH-1 |
| 2 | hash from the fd, then a second `Path.open()` probe to re-check `S_ISREG` | second resolution of the name | ARCH-1/2 |
| 3 | retry-once: a second descriptor **only** when the digest disagrees | re-open, hidden on the red branch | ARCH-1/2 |
| 4 | short-read fallback: re-open when fewer bytes stream than `fstat` promised | re-open, under exactly the shrink race Q3 names | ARCH-1/2 |
| 5 | failure-path re-classification through `io.open` | re-open on the red branch | ARCH-1 |
| 6 | `os.path.exists` + `os.path.getsize` for the missing/empty diagnosis | second resolution; contradicts Q3 | ARCH-1 + C12 |
| 7 | `os.path.getsize(path)` for the non-empty check after hashing the fd | same, post-hash | ARCH-1 + C12 |
| 8 | the cap **raised**, not removed (1 MiB / 64 MiB "DoS guard") | I6's defect above C5a's single measured point | ARCH-1 + **C5a at two sizes** |
| 9 | no byte count at all — "empty" inferred from the digest constant | Q3's streamed count absent | C12 |
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
- **C12** the streamed-count contract: a transcript that is **non-empty on disk but streams zero bytes**,
  and one whose `st_size` and streamed count disagree, must be diagnosed from the **streamed** count.
  Paired mutant **I12**: diagnose emptiness from `st_size`, from `os.path.getsize`, or from the digest
  constant → C12 must fail.
- **C13** per-entry, full-width comparison: mutate **only reviewer 0's** transcript and separately **only
  reviewer 1's**, and additionally record a digest that shares its first 12 hex characters with the real
  one. All three must FAIL. Paired mutant **I13**: compare truncated digests, or compare once outside the
  loop → C13 must fail.
- **C14** fail-closed on unexpected errors: a `transcriptPath` containing a **NUL byte** (which raises
  `ValueError`, not `OSError`) must produce a gate **failure**, never a skipped entry. Paired mutant
  **I14**: swallow non-`OSError` exceptions and continue → C14 must fail.
- **C5a is measured at two sizes**, not one: 512,723 bytes **and** a file larger than any plausible
  "generous" cap (≥ 2 MiB). One measured point pins one threshold; row 8 lives above it.

**Implementation mutants — each must be caught by its named case:**

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
- **I9** *(new — the sweep's headline)* validate with `_open_regular_fd`, **close the fd, then reopen the
  path** for hashing. Passes **every other case defined here** while keeping the replacement race §4.1
  forbids in four places. Caught only by C9.
- **I10** delete the non-empty check, or emit **one shared message** for all three causes → C2b must fail
  on the **exact** message. Without distinct messages this mutant is unobservable, because
  `_quorum_problem` already rejects the empty-file hash (`_EMPTY_SHA256`, `:36`).
  *(Round 4: reworded. I10 previously named "the `st_size` non-empty check", contradicting §8 Q3's
  adopted answer. The check is on the **streamed byte count** — see §4.1 step 4 and I12.)*
- **I11** compare the digests as **sets/multisets** rather than per reviewer entry → C10 must
  fail. A plausible order-insensitive one-liner that permits the two reviewers' transcripts to be swapped.
- **I12** *(round 4)* diagnose emptiness from `st_size`, `os.path.getsize`, or the digest constant instead
  of the streamed count → C12 must fail.
- **I13** *(round 4)* compare truncated digests (the 12-hex display form), or perform the comparison once
  outside the per-entry loop → C13 must fail.
- **I14** *(round 4)* swallow non-`OSError` exceptions and skip the entry → C14 must fail.

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
  - **THE PROOF IS ARCH-1 + ARCH-2 (§6.0), and they are MANDATORY.** The checker takes **only the raw
    fd** — never a path, never an opener, never a default-bound callable. Re-opening becomes
    *structurally unavailable* rather than merely detected. This is a **signature constraint asserted by
    a test**, not a prose preference; §4.1 step 3 states the exact signature and §7 step 5 makes it an
    acceptance condition. Round 3 wrote this as "prefer it" and round 4 was defeated through the gap that
    left.
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
   **ARCH-1 and ARCH-2 are acceptance conditions of this step**, not follow-up work: the step is not
   done until `_digest_transcript_fd(fd: int) -> tuple[str, int]` exists with exactly that signature and
   the two invariant tests pass.
4. §4.5's **one** test repair — (a) — using the executable repair stated there. *(Round 4: this step
   said "two"; (b) moved to `COREDEV-2618` in round 3.)*
5. All **twelve** mutants — **I1, I2, I3, I4, I5, I6, I9, I10, I11, I12, I13, I14** — all **twelve**
   cases — **C1, C2 (a/b/c), C3, C4 (a/b), C5 (a/b), C8, C9 (a/b), C10, C11, C12, C13, C14** — and both
   **structural invariants, ARCH-1 and ARCH-2**. Enumerated, never as a range: the rescope deleted
   I7/I8 and C6/C7 with §4.3, round 3 caught stale ranges naming four identifiers the plan no longer
   defines, and round 4 added six identifiers. Each mutant shown caught by its named case; C5's halves
   shown **PASSING** at both sizes; and **each of §6.0's twelve defeating implementations shown rejected**
   — that table is the acceptance suite for this step, not commentary.
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

**New open question for round 5:**

5. **Is ARCH-1 the right shape of assertion?** It inspects the shipped source (AST or `getsource`) for
   forbidden names inside `_digest_transcript_fd`. That is unusual for this suite, and source inspection
   has its own failure mode — a helper called *from* the sealed function could hold the forbidden call.
   The mitigation as written is that ARCH-1 asserts the parameter list too, so a path cannot reach any
   callee. Is that sufficient, or should ARCH-1 also assert the function's `__code__.co_names`?
3. ~~`st_size` vs streamed bytes?~~ **ANSWERED in round 3 — count bytes actually streamed.** Use the
   `fstat` for the `S_ISREG` check, but base the *empty* diagnosis on what was read: a shrink/grow race is
   precisely when the two disagree, and the streamed count is the truthful one. (gemini argued for
   `st_size` on early-exit grounds; codex's reasoning is stronger and is adopted.)
4. ~~`captureId` advisory-compare?~~ **ANSWERED in round 3 — explicitly DEFERRED to `COREDEV-2618`**, and
   removed from this plan's scope. Both reviewers agreed. `pty-capture.py:322-327` writes the sidecar
   best-effort, so it cannot support a failing check, and adding warn-only behaviour here would
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
