# Verify the Transcripts, Not Just the Claim

**Status:** Planning — round 2, awaiting re-gate
**Created:** 2026-07-30
**Last Updated:** 2026-07-30 (round 2)
**Ticket:** `COREDEV-2497` — `verify` never checks the transcripts; a hand-written artifact passes
**Epic:** `COREDEV-2485` — Plugin audit remediation / agent-skill-hook-CI modernization
**Branch:** `feat/COREDEV-2497-verify-transcripts`
**Target version:** `2.6.3` → **`2.6.4`** (patch: gate hardening, no asset-count change).
**Sequencing:** independent of `COREDEV-2605`/`2604`. Touches `scripts/review-verdict.py`, which
`COREDEV-2603` last changed at `schemaVersion` 3 — rebase on that, do not revert it.

---

## 1. Context — reproduced, not inherited

The ticket has carried a warning since it was filed: *"the investigator's evidence was partly
fabricated — verify before acting."* So everything below was re-executed against HEAD.

**The result, verbatim from the shipped script:**

```
review-verdict: GATE OK — APPROVE on docs/planning/FAKE_PLAN.md [gemini=APPROVE, codex=APPROVE]
  exit=0
```

That artifact was hand-written for a plan **no reviewer has ever read**. It carried literal
`"aaaa…"` / `"bbbb…"` transcript digests and `transcriptPath` values pointing at
`/nonexistent/gemini.txt` and `/nonexistent/codex.txt` — confirmed absent by `ls` in the same run.

**The two failed attempts matter more than the success**, because they bound the defect precisely:

| attempt | result |
|---|---|
| wrong `schemaVersion` | `GATE FAILED — artifact schemaVersion != 3` |
| reviewers with `status` only, no transcript fields | `GATE FAILED — an APPROVING combined verdict requires a transcript per reviewer; missing for codex, gemini` |
| **fabricated `transcriptSha256` + `transcriptPath` added** | **`GATE OK`** |

## 2. The defect, stated exactly

**`verify` checks that transcript metadata is PRESENT. It never checks that it RESOLVES.**

This is narrower than the ticket's own summary ("verify never checks the transcripts") and the
difference is load-bearing for the fix. Verified in-tree:

- `cmd_verify`'s only textual reference to a transcript field is **a comment** (`review-verdict.py:621`; `cmd_verify` begins at `:555`).
- The real check is `_quorum_problem`, which runs on **both** paths and does reject a missing or
  duplicated transcript (`:119`, `:177`, `:198`). It was not inert; my second forgery attempt died on it.
- What no one checks on verify: that `transcriptPath` **exists**, that it is **non-empty**, or that its
  bytes still **hash to** the recorded `transcriptSha256`.

**Every defence lives on the write path and none is re-checked where the gate actually runs.**
`_parse_reviewer` requires the file to exist (`os.path.isfile`) and to be non-empty — with a comment
explaining that `agy` writes exactly 0 bytes from a non-TTY on failure — and `cmd_write` additionally
enforces ≥2 reviewers, reviewer identity, quorum and the pre-review `--reviewed-sha256` snapshot.
`verify` re-runs only `_quorum_problem`.

So the gate's real guarantee is: *"the caller asserted two reviewers approved, and the plan has not
changed since"* — **not** *"two reviewers approved this plan."*

## 3. Guiding principle

> **Re-verify at the point of use, not only at the point of record.** An artifact is an assertion by
> whoever wrote it. A gate that consumes it must re-establish what it can, or it is trusting the
> caller it exists to check.

**Corollary — state the ceiling honestly, in the code.** This cannot be made unforgeable. Anyone who
can write `<plan-dir>/.verdicts/` can also write transcript files. The fix raises the cost from
*"invent two JSON strings"* to *"fabricate two full transcripts whose bytes hash correctly"* — real,
bounded, and **not** a security boundary. §5 says so where a reader will meet it.

## 4. Findings, fixes, and proofs

### 4.1 — `verify` does not resolve `transcriptPath` (High)

**Fix.** For every reviewer in an **approving** artifact, `verify` must:

**Do NOT reuse `_read_regular_file`, and this is the single most important instruction in the plan.**
Round 1 said to. It is a UTF-8 text reader **capped at 65,536 characters** (`scripts/review-verdict.py:211`,
returning `None` past `_MAX_TRUSTED_READ_BYTES` — verified by reading the function, not a `grep` offset).
Executed against the real thing: `/tmp/codex-out.txt`, the codex transcript of **this plan's round-1
review**, is **769,988 bytes** — 11× the cap, so `_read_regular_file` returns `None` for it. Reusing it
would have rejected *every legitimate codex review*: the fix breaking the gate it repairs.

> **Measured, and it narrows the fix:** that transcript **is valid UTF-8**, and so is the gemini one. The
> blocker is the **size cap alone**, not decoding. Do not justify this change on encoding grounds — see
> C5, where non-UTF-8 remains a *defensive* case (a PTY capture killed mid-multibyte-sequence at timeout
> is realistic) rather than the typical one.

Chaining `_read_regular_file` for validation and then `_sha256_bytes` for the digest is also wrong:
two opens is a replacement race.

**FACTOR, do not rewrite.** `_read_regular_file`'s *prologue* is correct and expensively earned — the
atomic `O_NOFOLLOW` symlink refusal (no `islink()`-then-open TOCTOU window), `O_NONBLOCK` so a planted
FIFO cannot block, and the `fstat` `S_ISREG` check, each landed in a named round of COREDEV-2503's
review. A hand-rolled replacement would silently drop those. Split it:

1. extract the shared prologue → returns a validated fd for a regular file;
2. `_read_regular_file` keeps its decode + cap epilogue, **unchanged**, for the sidecars it guards;
3. the new transcript path takes the same fd and **streams raw bytes** through `hashlib` — no cap, no
   decode, no re-open — with `st_size` from that same `fstat` serving the **non-empty** check.

Then require the digest equals the recorded `transcriptSha256`. Non-empty comes from the `fstat`, never
a second `getsize`. **Regression duty:** every existing `_read_regular_file` test must still pass after
the extraction — it guards `planPath` and the sidecars, and this refactor touches shared code.

**Fail closed with a DISTINCT message per cause.** "Transcript missing" and "transcript changed since
approval" need different recoveries — re-run the reviewer versus re-run the gate — and a single
message conflates them.

**Proof — and the mutant is not a revert.** Delete `transcriptPath`'s file after a legitimate `write`
and re-run `verify`: it must fail. Truncate it to 0 bytes: must fail. Append one byte: must fail on the
digest. **Then the forgery itself**: hand-write the round-2 artifact shape (fabricated digests,
nonexistent paths) and confirm it now FAILS where it currently returns `GATE OK`.

### 4.2 — Non-approving artifacts must not be tightened (Medium)

`_quorum_problem` deliberately skips non-approving verdicts, because a `REQUEST_CHANGES` artifact
records *whatever ran* and is never gate-passing. **§4.1's checks must skip them too.**

Getting this wrong would break the recovery path: a reviewer that produced an empty transcript is
recorded as `MISSING`, and the operator's next step is reading that artifact. Making it unreadable
because the transcript is empty would remove the diagnosis while changing no security property.

**Proof.** A `REQUEST_CHANGES` artifact whose transcript has since been deleted must still `verify`
to its existing non-approving outcome — the same failure text as today, not a new one.

### 4.3 — The transcripts are the artifact's only unbound evidence (Medium)

`planSha256` binds the plan. `planPathKind` + `planPath` bind the identity (`COREDEV-2603`). The
reviewer **statuses** are caller-supplied and the transcripts are the only evidence behind them —
which is exactly why they are worth re-checking, and exactly why re-checking them is not sufficient.

**Decision, REVERSED in round 2: DO cross-check the verdict token against the recorded status**, for
approving artifacts only.

> *Round 1 rejected this on three grounds, and the load-bearing one was **false**.* It claimed "the
> anchored `^VERDICT: …$` grep is already known to mis-fire". **The opposite is true, and this repo
> says so in the file I wrote the same day:** `scripts/review/isolated-agy-review.sh:108` reads
> *"Anchored, never a loose `grep VERDICT:` — that matches the prompt's own echoed template"*. A
> **loose** grep misfires; **anchored is the mitigation**. I inverted my own guidance.
>
> The other two reasons are weaker than round 1 presented, as the reviewer pointed out:
> `review-synthesis`'s `MISSING` normalisation is **irrelevant to an approving artifact** (an approving
> verdict already requires a transcript per reviewer, so `MISSING` cannot arise there); and formatting
> drift **should** fail closed, because both review skills mandate an explicit verdict line.

**What the cross-check buys, precisely.** Re-digesting proves *these bytes are unchanged*. It does not
prove *these bytes say APPROVE*. The reviewer **status** is caller-supplied — that is the original
hole — so without this, an artifact recording `gemini=APPROVE` against a transcript ending
`VERDICT: REQUEST_CHANGES` passes. The cross-check closes exactly that: a **mis-recording caller**.

**What it does not buy, stated so it is not oversold.** It does not prove the transcript reviewed
*this* plan. Two real transcripts from a different plan's review that both say `APPROVE` still pass.
That is the residual, and it is why §3's ceiling stands.

**Spec, and it must be a BYTES match — §4.1 deliberately never decodes.** Decoding the transcript to
apply a `str` regex would reintroduce the exact `_read_regular_file` failure §4.1 exists to avoid, on a
file measured at 769,988 bytes. Match on the bytes already in hand.

> **What the capture actually contains — read from the writer, which corrected two guesses.**
> `scripts/pty-capture.py:314` is `cleaned = ANSI_RE.sub(b'', bytes(raw)).replace(b'\r\n', b'\n')`. So the
> stored transcript has **ANSI escapes stripped** and **CRLF normalised to LF** *at capture time*. An
> earlier draft of this section justified the match on "ANSI escapes throughout" and "PTY lines end
> `\r\n`" — **both are removed before the bytes ever reach disk.** The line-ending tolerance is still
> worth having, and now for a precise reason: that `.replace` is a single non-recursive pass, so a
> `\r\r\n` sequence leaves a residual `\r\n` — which is exactly the 12 CRLFs measured in
> `/tmp/codex-out.txt` against 13,724 bare-LF lines.

- Scan with a **bytes** pattern on the bytes already being streamed for the digest — `rb'(?m)^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[ \t\r]*$'`. **One pass, one descriptor**: the
  cross-check consumes the same read as the digest, not a second open.
- Trailing `[ \t\r]*` mirrors `scripts/review/isolated-agy-review.sh:110`, and it is **defensive, not
  load-bearing** — measured: a strict `…$` matches **1/1** on both round-1 transcripts, because of the
  normalisation above. It costs nothing and it covers the `\r\r\n` residual. Calling it "required"
  would have been a fabricated justification for a correct decision.
- Take the **last** match: a review may discuss candidate verdicts before declaring one.
- Compare to the recorded `status`. Mismatch → fail. **Absent token on an approving artifact → fail
  closed**, per §8's contested point.
- Streaming caveat to respect in implementation: a chunked scan must **carry over** a tail of at least
  the pattern's maximum match length between chunks, or a `VERDICT:` line straddling a chunk boundary is
  silently missed — an artifact-dependent inert gate. Buffer only candidate lines, never the whole file.

### 4.4 — Problem 2: shared fixed-name `/tmp` transcript paths (Medium)

**FOUR skills, plus the README and the contracts** — round 1 said three and omitted the one that
matters most. Verified by `grep -rln`:

| surface | role |
|---|---|
| `skills/codex-review/SKILL.md` | producer |
| `skills/gemini-review/SKILL.md` | producer (+ the `agy-ping.txt` preflight) |
| `skills/brainstorm/SKILL.md` | passes the paths to `review-verdict.py write` |
| **`skills/review-synthesis/SKILL.md`** | **the CONSUMER** — reads both at `:23-24` and `:38`. Omitting it would have migrated the producers and left the consumer reading the old paths |
| `README.md`, `AGENT_CONTRACTS.md:113` | document them |

**`context_reviews_dir()` alone does NOT fix this.** It keys on `context_repo_hash()` — **per
checkout** (`scripts/lib/context.sh:54`). Two concurrent gate rounds *in the same checkout* still
collide on a fixed filename beneath it. The path needs a **per-run** discriminator, and the acceptance
test must cover same-checkout concurrency, not merely two worktrees.

**This interacts with §4.1 and that is the reason to fix it here rather than separately.** Once verify
re-digests, a *clobbered* transcript stops being a silent provenance hole and becomes a hard gate
failure — good, but the operator deserves the collision not to happen. `context_reviews_dir()` is
already the production convention for code-review captures (`agents/swift-reviewer.md:247`,
`scripts/capture-reviewer-verdict.sh:45`, `precompact-snapshot.sh`), and the repo's own policy forbids fixed
`/tmp` in three places (`marker.sh:7`, `log.sh:7`, `context.sh:17`). Plan-review transcripts are the
sole holdout.

**Note for the reviewer.** `COREDEV-2607` already moved the gemini half onto
`scripts/review/isolated-agy-review.sh`, which takes an explicit out-path — so the wrapper exists; what
remains is choosing the path and updating the four skills — including `review-synthesis`, the
consumer, whose omission from round 1 would have left it reading the old paths.

**ORDER REVERSED, and it resolves a direct reviewer disagreement.** gemini said *do not split* —
once §4.1 re-digests, a clobbered transcript becomes a hard gate failure, so shipping §4.1 alone makes
legitimate concurrent sessions fail. codex said *do split* — §4.4 is a four-skill, README, contracts
and session-handoff migration, and the focused fix should not wait for it.

**Both are right, and the resolution is to land §4.4 FIRST rather than to choose.** Per-run transcript
paths are independently safe and land without §4.1. Doing them first removes the collision *before*
§4.1 makes collisions fatal — which is gemini's concern — while keeping the two changes separately
reviewable, which is codex's. §7 reflects the new order.

**Proof.** Two concurrent gate rounds **in the SAME checkout** must not overwrite each other's
transcript — the case `context_reviews_dir()` alone does not cover. Assert the *paths are distinct*,
not merely that both runs succeed.

### 4.5 — Corrections to the ticket body itself (two of its three carried-forward items are now stale)

The ticket warns that its own investigator fabricated evidence, so every carried-forward item was
re-checked against HEAD. **Two are no longer true**, and acting on either would waste a round:

- **`agy-ping` — the ticket says `grep -rn agy-ping` returns zero hits. It does not, any more.**
  `/tmp/agy-ping.txt` is now a documented preflight in `AGENT_CONTRACTS.md:113` and
  `skills/gemini-review/SKILL.md:24` — a legitimate `agy` health probe, not a fabrication. The
  consequence is the opposite of the ticket's: it is a **third fixed-name `/tmp` path** and therefore
  belongs in §4.4's scope alongside `agy-out.txt` and `codex-out.txt`. Its collision risk is lower (a
  4-byte `pong` probe, not a transcript), but the same argument applies.
- **The `0o600`-on-a-pre-existing-file defect is ALREADY FIXED.** `pty-capture.py:83` calls
  `os.fchmod(fd, 0o600)` with the exact reasoning at `:69` — *"O_CREAT only applies the mode on
  creation, so an existing 0644 file is tightened."* Do not re-implement it; do not carry it as scope.
- **Truncate-at-start is largely redundant** — `pty-capture.py`'s capture helper writes through a
  `finally` (`:225`) that always runs, so round N already wipes round N-1. It helps only in the
  SIGKILL/early-crash window. This one still holds.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The fix is read as making the gate unforgeable | **High** | §3's corollary, stated in the code and the CHANGELOG: anyone who can write `.verdicts/` can write transcripts. This raises cost, it is not a boundary |
| Tightening breaks the non-approving recovery path | **Medium** | §4.2 skips non-approving artifacts, with a test that a stale `REQUEST_CHANGES` still reads |
| A legitimate re-run trips the new check | Medium | The digest is recorded at `write` from the same bytes; only deletion/modification after approval trips it, which is the intended signal |
| The `VERDICT:` cross-check is read as proving the reviewer read *this* plan | **High** | §4.3 states the residual explicitly: two real transcripts from a *different* plan's review, both saying APPROVE, still pass |
| The cross-check rejects a legitimate approval whose format drifted | Medium | Contested openly in §8. Both review skills mandate the line; C6's positive half proves a real PTY-shaped transcript passes |
| Fixing `/tmp` paths breaks a skill recipe mid-round | Medium | §4.4 lands **first** and alone, so a recipe break surfaces before the digest check can turn it into a gate failure; `isolated-agy-review.sh` already takes an explicit out-path |
| Factoring `_read_regular_file` regresses `planPath`/sidecar validation | Medium | The decode+cap epilogue is untouched and every existing test for it must still pass — §4.1's regression duty |
| The whole change is inert because tests only cover `write` | **High** | Every §4.1 proof drives `verify` **after** a legitimate `write`, never a synthesised artifact — see §6 |

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

Baselines **as measured at `eead2f6`**: `test-hooks.sh` **304**, synthesizer **222**, scripts **312**,
counts `21/21/0/1`, hook events **10**. Floors, not equalities — re-derive at implementation time and
print `pwd` + `git rev-parse HEAD` beside any measurement.

**Mutation proof required for every fix, and it must reject a plausible wrong implementation, not only
a revert.** Named mutants:

*(Round 1 listed four, and they were insufficient — see I4 below, which passes all four. Round 1 also
mixed implementation mutations and input cases in one numbered list, which is how a proof set acquires a
gap nobody notices. They are now separated and renumbered: **I**mplementation mutants must be
REJECTED; input **C**ases must be carried by the suite.)*

**Implementation mutants — each must be caught by an existing test:**

- **I1** `os.path.exists` instead of re-digesting → *C2's append-one-byte* case must still fail.
- **I2** re-digest only the first reviewer → the second reviewer's deleted transcript must still fail.
- **I3** apply the checks to non-approving artifacts too → §4.2's stale `REQUEST_CHANGES` test fails.
- **I4** **`if path: verify(path)`** — skip the check when `transcriptPath` is absent. **This mutant
  passes every round-1 proof**, because `_quorum_problem("APPROVE", …)` returns `None` for reviewers
  carrying valid-looking digests and *no* `transcriptPath` (executed), and the round-1 forgery
  *included* paths. Caught only by C3.
- **I5** `os.path.isfile` + `_sha256_bytes` instead of the single-descriptor helper → C4's **symlink**
  case must still fail (`isfile` follows links).
- **I6** use `_read_regular_file` (or keep its cap in the extracted prologue) → C5's **>64 KiB**
  case must still VERIFY; a mutant that rejects it must be caught.
- **I7** *(new, guards §4.3)* drop the verdict cross-check, or decode-then-`str`-regex, or anchor
  `…$` with no trailing `[ \t\r]*` → C6 must fail. Three distinct wrong implementations, one case.
- **I8** *(new, guards §4.3's streaming)* scan chunk-by-chunk with no carry-over → C7 must fail.

**Input cases the suite must carry:**

- **C1** **the forgery itself** — the exact artifact that returns `GATE OK` today.
- **C2** delete / truncate-to-zero / append-one-byte, between `write` and `verify`.
- **C3** `transcriptPath` **absent**, `null`, and `""` — three shapes, all must fail.
- **C4** a **symlink** and a **FIFO** at the transcript path.
- **C5** a **non-UTF-8** transcript and one **larger than 64 KiB** — both must VERIFY **successfully**.
  The >64 KiB half is the *typical* case (measured: 769,988 bytes); the non-UTF-8 half is *defensive*
  (a timeout-killed PTY capture can end mid-multibyte). This is the case that catches a fix worse than
  the defect, and I8's `_read_regular_file` mutant dies on the first half alone.
- **C6** *(new)* transcript whose last `VERDICT:` line disagrees with the recorded `status` → fail; and
  a real PTY-shaped transcript with `\r\n` line endings + an ANSI reset after the verdict → must PASS.
- **C7** *(new)* a verdict line straddling the read-chunk boundary → must still be found.
- **C8** both approving verdicts (`APPROVE`, `APPROVE_WITH_NOTES`), each reviewer mutated independently.

**The trap this ticket is most likely to fall into:** `scripts/tests/test_review_verdict.py`'s fixture
calls `_write` before verifying, so the transcripts always exist and always match. A test suite built
that way goes green against an implementation that checks nothing. **Every §4.1 test must mutate the
transcript on disk between `write` and `verify`.**

## 7. Implementation order

1. **§4.4 FIRST** — per-**run** transcript paths across all four skills + README + contracts. Lands
   independently and removes the collision before §4.1 makes it fatal.
2. §4.1 — the single-descriptor binary helper; resolve, non-empty, re-digest. Approving artifacts only.
3. §4.3 — the verdict-token cross-check against the recorded status.
4. §4.2 — the non-approving carve-out, tested on `REQUEST_CHANGES` **and** `DISAGREEMENT`, including a
   `MISSING` reviewer.
5. All **8 implementation mutants (I1–I8)** and **8 input cases (C1–C8)** from §6 — each mutant shown
   caught by its named case, and C5/C6's positive halves shown PASSING (a fix that rejects real
   transcripts is worse than the defect).
6. Version bump + CHANGELOG — describing this as **consistency/provenance hardening**, explicitly NOT
   as proof that a reviewer read the plan.

## 8. Open questions — round 1's three are answered

1. **Re-check `captureId`?** **No — keep it advisory.** Both reviewers agreed: it is optional and
   absent for hand-run reviews, so mandating it would reject legitimate approvals, and it is
   unauthenticated so it proves little. codex adds a good refinement: compare it **when present**, as a
   cheap detector of accidental clobbering. Adopted as advisory-compare.
2. **Split §4.4 out?** **Neither — reorder.** The reviewers disagreed (gemini: don't split, §4.1 makes
   collisions fatal; codex: do split, §4.4 is underdesigned). §4.4 now lands **first**, which satisfies
   both — see §4.4.
3. **Ship `2.6.4` or wait for authenticity?** **Ship**, both agreed — provided the ceiling is stated.
   codex's wording is adopted verbatim in §7 step 6: describe it as **consistency/provenance
   hardening**, not as proof a reviewer read the plan.

**New for round 2 — what reviewers should contest now.** §4.3 was REVERSED: round 1 rejected the
verdict-token cross-check on a premise that was simply false (it claimed anchored parsing misfires;
this repo says the opposite, in a file written the same day). The cross-check is now adopted. **Is
failing closed on an ABSENT verdict token correct?** It is the one case where a legitimate,
well-behaved reviewer whose output format drifts would block an approval — and the counter-argument is
that both review skills mandate the line, so drift is a real defect rather than noise.

## 9. Notes

- Every claim here was executed against HEAD `eead2f6`. **Round 2's own re-execution corrected four
  more of my statements**, which is why this section exists: a `512,723`-byte transcript figure that was
  really **769,988**; "non-UTF-8 by nature" (both transcripts **are** valid UTF-8 — the blocker is the
  size cap alone); "ANSI escapes throughout" and "PTY lines end `\r\n`" (both **stripped and normalised
  at capture time**, `scripts/pty-capture.py:314`). Each was a plausible generalisation about PTY
  captures that the writer's own source refutes in one line.
- **The citation-error tally across both drafts is six**, all the same shape: a number taken from a
  `grep -n`/`sed` offset instead of from the file. Four self-caught, two by codex
  (`agents/swift-reviewer.md:160`→`:247`, `scripts/capture-reviewer-verdict.sh:43`→`:45`). Plus three
  scope errors: an `agy-ping` claim inherited from the ticket that had become false, an already-shipped
  `fchmod` fix listed as outstanding, and "three skills" where there are **four**.
- Checks executed: the forgery; the two failed attempts that bound it; `_quorum_problem`'s behaviour on
  the verify path — including the `APPROVE`-with-no-`transcriptPath` case that defeats a naive fix; the
  absence of any transcript resolution in `cmd_verify`; `_read_regular_file` against a 70,000-byte file
  and against the real transcript; the anchored-vs-strict verdict match on both transcripts; and
  `grep -rln` for the surviving `/tmp` paths across **four** skills, the README and the contracts.
- `COREDEV-2603` moved the artifact to `schemaVersion` 3 and added `planPathKind`. This plan adds **no**
  new fields and needs no `schemaVersion` bump: it re-checks fields that already exist, and §4.4 changes
  only the *values* written into `transcriptPath`, never its presence or type, so old artifacts stay readable.
- The ticket's own framing ("verify never checks the transcripts") is slightly too strong;
  `_quorum_problem` does run there. §2 states the precise version, because the imprecise one would send
  an implementer to the wrong function.

## 10. Round-1 gate outcome

**gemini `APPROVE` · codex `REQUEST_CHANGES` (4 findings).** Both re-verified the plan's citations
independently; all four codex findings were then re-executed here before the plan was touched, and
**all four held**.

| # | finding | verified | round-2 change |
|---|---|---|---|
| 1 | §4.1 mandates a helper that cannot digest real transcripts | **confirmed — the worst one** | `_read_regular_file` is a 64 KiB UTF-8 text reader; executed, it returns `None` for a 70,000-byte file **and for the 769,988-byte codex transcript of this plan's own round-1 review** — 11× the cap. Round 1 would have rejected every legitimate codex review. Remedy: **factor** the reader's hard-won `O_NOFOLLOW`/`S_ISREG` prologue and stream bytes past it, rather than hand-roll a replacement that would drop those protections |
| 2 | the four mutants are insufficient | **confirmed by execution** | `_quorum_problem("APPROVE", …)` returns `None` for digests with **no** `transcriptPath`, so `if path: verify(path)` passes every round-1 mutant. Now 7 implementation mutants + 5 input-case groups, and the two kinds are no longer mixed in one list |
| 3 | §4.4 is incomplete | **confirmed** | **four** skills not three — `review-synthesis` is the CONSUMER and was omitted — plus README and contracts. And `context_reviews_dir()` is per-**checkout**, so same-checkout concurrency still collides; the path needs a per-**run** id |
| 4 | §4.3's factual basis is wrong | **confirmed, and it was my own inversion** | the repo says a **loose** grep misfires and **anchored** is the mitigation — `scripts/review/isolated-agy-review.sh:108`, written the same day. §4.3 claimed the opposite. The rejection is REVERSED and the cross-check adopted |

**Two more wrong citations**, caught by codex: `swift-reviewer.md:160` (blank; the call is at `:247`)
and `capture-reviewer-verdict.sh:43` (blank; `:45`). With the four this plan's own §9 already records,
that is **six wrong citations in one plan across two drafts** — every one an off-by-a-few from reading
a `grep -n` offset rather than opening the file. The lesson is mechanical, not attitudinal: *print the
line you are citing, from the file, before writing the number down.*

**The reviewers disagreed on §4.4's split and both were right about different things.** Resolved by
reordering rather than choosing: §4.4 lands first, so the collision is gone before §4.1 makes it fatal,
and the two remain separately reviewable.
