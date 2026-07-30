# Verify the Transcripts, Not Just the Claim

**Status:** Planning — draft, awaiting the dual plan-review gate
**Created:** 2026-07-30
**Last Updated:** 2026-07-30
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

1. resolve `transcriptPath` and require a **regular file** (reuse `_read_regular_file`, which already
   refuses symlinks/FIFOs — do not hand-roll an `os.path.isfile` check);
2. require it **non-empty** (the 0-byte case is `agy`'s documented failure mode);
3. re-digest it and require equality with the recorded `transcriptSha256`.

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

**Decision, made here rather than deferred:** do **not** extract `VERDICT:` from the transcript and
compare it to the recorded `status`. It is tempting and it is a trap:

- the anchored `^VERDICT: …$` grep is already known to mis-fire on a **timed-out transcript that
  echoes the prompt's own template** — this repo has been bitten by exactly that;
- `review-synthesis` normalises *both* "reviewer never returned" *and* "empty/unparseable transcript"
  to `MISSING`, so a transcript legitimately may not contain a parseable verdict;
- it would make the gate depend on reviewer output **formatting**, converting a formatting drift into
  a gate failure.

Re-digesting proves *these bytes are the ones that were reviewed*. Parsing them proves less than it
appears to. Record this rejection so it is not re-proposed.

### 4.4 — Problem 2: shared fixed-name `/tmp` transcript paths (Medium)

**THREE** fixed-name paths, not two — `/tmp/agy-out.txt`, `/tmp/codex-out.txt` and
`/tmp/agy-ping.txt` (see §4.5). All shared, world-readable, and colliding across concurrent sessions
and worktrees. Present in `skills/codex-review/SKILL.md:48-51`, `skills/brainstorm/SKILL.md:194`,
`skills/gemini-review/SKILL.md:24` and `AGENT_CONTRACTS.md:113`.

**This interacts with §4.1 and that is the reason to fix it here rather than separately.** Once verify
re-digests, a *clobbered* transcript stops being a silent provenance hole and becomes a hard gate
failure — good, but the operator deserves the collision not to happen. `context_reviews_dir()` is
already the production convention for code-review captures (`swift-reviewer.md:160`,
`capture-reviewer-verdict.sh:43`, `precompact-snapshot.sh`), and the repo's own policy forbids fixed
`/tmp` in three places (`marker.sh:7`, `log.sh:7`, `context.sh:17`). Plan-review transcripts are the
sole holdout.

**Note for the reviewer.** `COREDEV-2607` already moved the gemini half onto
`scripts/review/isolated-agy-review.sh`, which takes an explicit out-path — so the wrapper exists; what
remains is choosing the path and updating the three skills.

**Proof.** Two concurrent gate rounds in different worktrees must not overwrite each other's
transcript. Assert on the *paths* being distinct, not merely on both runs succeeding.

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
| `VERDICT:` parsing gets added later "for completeness" | Medium | §4.3 records the rejection and its three reasons |
| Fixing `/tmp` paths breaks a skill recipe mid-round | Medium | §4.4 lands after §4.1, and `isolated-agy-review.sh` already takes an explicit out-path |
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

1. check `os.path.exists` instead of re-digesting → the *append-one-byte* case must still fail;
2. re-digest only the first reviewer → the second reviewer's deleted transcript must still fail;
3. apply the checks to non-approving artifacts too → §4.2's stale `REQUEST_CHANGES` test must fail;
4. **the forgery itself** — the exact artifact that returns `GATE OK` today must fail.

**The trap this ticket is most likely to fall into:** `scripts/tests/test_review_verdict.py`'s fixture
calls `_write` before verifying, so the transcripts always exist and always match. A test suite built
that way goes green against an implementation that checks nothing. **Every §4.1 test must mutate the
transcript on disk between `write` and `verify`.**

## 7. Implementation order

1. §4.1 — resolve, non-empty, re-digest, on approving artifacts only, with per-cause messages.
2. §4.2 — the non-approving skip, with the stale-`REQUEST_CHANGES` test.
3. Mutants 1–4, each shown failing before the fix and passing after.
4. §4.4 — per-checkout transcript paths + the three skill updates.
5. Version bump + CHANGELOG, stating the ceiling explicitly.

## 8. Open questions for the reviewers

1. **Should `captureId` be re-checked too?** It is per-run provenance from `pty-capture.py` and is
   already read with `O_NOFOLLOW` at write time. Re-checking it would catch "same bytes, replayed from
   a different run", but it is optional and absent for hand-run reviews — so enforcing it could fail
   legitimate gates. This plan leaves it advisory. Right call?
2. **Should §4.4 (`/tmp` paths) be split out?** It is the ticket's Problem 2 and is independent of the
   transcript check. Batching costs a larger diff on the skills; splitting risks it never landing,
   since it has already outlived one ticket.
3. **Is `2.6.4` right, or should this wait for the `2497`-aware authenticity work?** The artifact stays
   forgeable after this change. If a reviewer thinks shipping a partial hardening invites
   over-confidence, the alternative is to hold it and do authenticity properly — at considerably more
   cost.

## 9. Notes

- Every claim here was executed against HEAD `eead2f6`, and doing so caught **three wrong citations and one stale scope item in this plan's own first draft** — a comment line number taken from a `sed`-relative offset rather than the file, a `pty-capture.py` range that pointed at a `waitpid` loop, an `agy-ping` claim inherited from the ticket that has since become false, and an already-shipped `fchmod` fix listed as outstanding. The checks were: the forgery, the two failed attempts that bound
  it, the `_quorum_problem` behaviour on the verify path, the absence of any transcript resolution in
  `cmd_verify`, and the surviving `/tmp` paths in three skills.
- `COREDEV-2603` moved the artifact to `schemaVersion` 3 and added `planPathKind`. This plan adds **no**
  new fields, so no further schema bump is needed — the transcript fields it re-checks already exist.
- The ticket's own framing ("verify never checks the transcripts") is slightly too strong;
  `_quorum_problem` does run there. §2 states the precise version, because the imprecise one would send
  an implementer to the wrong function.
