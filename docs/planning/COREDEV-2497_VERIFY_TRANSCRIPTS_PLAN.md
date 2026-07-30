# COREDEV-2497 — `verify` must re-check the transcripts it approved

**Status:** Planning — round 3, RESCOPED. Awaiting the dual gate.
**Ticket:** `COREDEV-2497` (Epic `COREDEV-2485`)
**Split out on 2026-07-30 (maintainer decision):** `COREDEV-2618` (verdict-token cross-check) ·
`COREDEV-2619` (per-run transcript paths). **This plan is now §4.1 + §4.2 only.**
**Sequencing:** `COREDEV-2619` should land **first** — see §7.
**Measured against:** HEAD `2dc7f5c` (v2.6.4). Worktree `.claude/worktrees/opus5-review`.
**Last Updated:** 2026-07-30 (round 3)

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
**769,988 bytes**, having read `/tmp/codex-out.txt` — which by then held a **LumaWake** plan review (638
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
calls `_quorum_problem` (`:99`), which checks reviewer **count**, **status membership**, digest
**syntax**, and rejects the empty-file hash. It **never resolves `transcriptPath`**, so:

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
3. The transcript checker **accepts the fd** (or an injectable opener) — **never a path** — and streams
   raw bytes through `hashlib`: no cap, no decode, **no re-open**. `st_size` from that same `fstat`
   serves the non-empty check, never a second `getsize`.

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

### 4.5 — Two existing tests break, and the naive repair guts the fix (High)

Round 2's regression duty said "every existing `_read_regular_file` test must still pass" without naming
anything. Two specific tests are affected, both **read and confirmed**:

**(a) `test_uppercase_and_padded_digests_are_normalized_not_rejected`
(`scripts/tests/test_review_verdict.py:123-141`).** After a legitimate `_write`, it rewrites
`transcriptSha256` to `"A"*64` and `" " + "a"*64 + " "`, sets reviewer 1's to `"b"*64`, and asserts
`returncode == 0`. Under §4.1 those digests no longer match the fixture transcripts, so **verify fails
and this test breaks.** Its purpose is legitimate — proving the hex check is not over-strict, because a
false GATE FAILED is its own outage.

> **The trap:** the path of least resistance is to loosen the digest comparison, which guts §4.1
> entirely. **The correct repair** keeps the test's purpose: set the recorded digest to the *real* digest
> of the fixture transcript, uppercased and space-padded (`_sha256_bytes(self.tx).upper()`), so it still
> proves normalisation while satisfying equality.

**(b) The default fixture is self-inconsistent (`:36`, `:43`, `:55`).** `self.tx2` ends
`VERDICT: APPROVE`, while `_write`'s default records `codex=APPROVE_WITH_NOTES` for the reviewer that
gets `tx2`. Harmless for §4.1 (digests still match), but it means the fixture **forces approving-token
*membership* rather than equality**, which is exactly the hole `COREDEV-2618` must not inherit. Fix the
fixture here — make `tx2` end `VERDICT: APPROVE_WITH_NOTES` — so 2618 starts from a self-consistent base.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The fix is read as making the gate unforgeable | **High** | §3's ceiling in code + CHANGELOG, with the measured 17-byte floor |
| A legitimate large or non-UTF-8 transcript is rejected — the fix worse than the defect | **High** | C5's two halves must **PASS**; I6 is the mutant that reintroduces the cap |
| The digest check is silently gutted while repairing §4.5(a) | **High** | §4.5 names the trap and the correct repair; C2c must FAIL for any C-case green to mean anything |
| Tightening breaks the non-approving recovery path | Medium | §4.2 + C8 |
| A validate-then-reopen implementation ships green | Medium | I9 + C9, and §4.1's named seam makes it testable at all |
| Factoring regresses the two sidecars | Medium | Epilogue untouched; both sidecar tests named in §4.5 |
| The whole change is inert because tests only cover `write` | **High** | Every §4.1 test must mutate the transcript on disk **between** `write` and `verify` — see §6's trap |

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
  path** for hashing. Passes C1–C8 as written while keeping the replacement race §4.1 forbids in four
  places. Caught only by C9.
- **I10** *(new)* delete the `st_size` non-empty check, or emit one shared message for all three causes →
  C2b must fail on the **exact** message. Without distinct messages this mutant is unobservable, because
  `_quorum_problem` already rejects the empty-file hash (`_EMPTY_SHA256`, `:36`).
- **I11** *(new)* compare the digests as **sets/multisets** rather than per reviewer entry → C10 must
  fail. A plausible order-insensitive one-liner that permits the two reviewers' transcripts to be swapped.

**Input cases the suite must carry:**

- **C1** the forgery itself — the exact artifact that returns `GATE OK` today.
- **C2** three *separately named* cases, each asserting its **distinct** message: **(a)** delete,
  **(b)** truncate to zero, **(c)** append one byte. Splitting them is what makes I10 observable.
- **C3** `transcriptPath` **absent**, `null`, and `""` — three shapes, all must fail.
- **C4** **(a)** a symlink and **(b)** a FIFO at the transcript path.
- **C5** both must **VERIFY SUCCESSFULLY**: **(a)** a transcript **larger than 64 KiB** — the *typical*
  case, measured at 512,723 bytes; **(b)** a **non-UTF-8** transcript — *defensive*, since a
  timeout-killed PTY capture can end mid-multibyte. This is the case that catches a fix worse than the
  defect.
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
  - **C9b structural** — wrap `os.open`/`builtins.open` and assert **exactly one** `os.open` of each
    transcript path, with `O_NOFOLLOW|O_NONBLOCK` in its flags, and **zero** further opens of it.
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
2. `_open_regular_fd` extraction, with the two sidecars unchanged and their tests still green.
3. §4.1 + §4.2 together — resolve, non-empty, re-digest, per-reviewer, approving artifacts only, distinct
   messages per cause. §4.2 is the same code path, not a later step.
4. §4.5's two test repairs, using the stated correct repair for (a).
5. All mutants **I1–I11** and cases **C1–C10**, each mutant shown caught by its named case, and C5's two
   halves shown **PASSING**.
6. Version bump + CHANGELOG — **consistency/provenance hardening**, explicitly NOT proof that a reviewer
   read the plan. State §3's ceiling and the 17-byte floor.
7. `COREDEV-2618` afterwards, on the seam this plan creates.

## 8. Open questions for the reviewers

1. **Is `_open_regular_fd` returning a raw fd the right seam**, or should the transcript checker take an
   injectable opener callable? The fd form is simpler; the callable is easier to assert on. C9b works
   either way — which fails more usefully?
2. **Is C9a's `os.replace`-inside-the-opener a legitimate proof**, or does patching the seam make it
   tautological? It is the only deterministic construction I found for a property that is otherwise only
   observable by winning a race.
3. **Should the non-empty check use `st_size` from the `fstat`, or bytes actually streamed?** They differ
   if the file shrinks mid-read. Streamed bytes are the honest measure but need the digest loop to report
   a count.
4. **Is `captureId` advisory-compare worth doing here at all?** Round 2 declared it "adopted" and then
   never specified it, gave it no step and no case — a decision with no implementation, which is how
   plans acquire phantom scope. Either specify it here (compare when both exist, **warn** never fail,
   since `pty-capture.py:322-327` writes the sidecar best-effort) or explicitly defer it. It should not
   stay "adopted" in name only.

## 9. Notes — the citation record, kept because it keeps mattering

- **Seven wrong citations across three drafts**, every one the same shape: a number taken from a
  `grep -n`/`sed` offset instead of from the file. Four self-caught; three by codex
  (`agents/swift-reviewer.md:160`→`:247`, `scripts/capture-reviewer-verdict.sh:43`→`:45`, and
  `AGENT_CONTRACTS.md:113`, which documents the `agy-ping` preflight and **never mentions the transcript
  paths at all**).
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
