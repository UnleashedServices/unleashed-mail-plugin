# COREDEV-2619 — Per-run transcript paths

**Status:** Planning — **round 3 gated (codex `REQUEST_CHANGES` 3 High + 2 Medium + 1 Low; the gemini
arm timed out at 36 bytes — the harness's `--print-timeout` is raised from 18m to 28m).** Blocks `COREDEV-2497`, whose §7 step 1 requires this to land
first.
**Ticket:** `COREDEV-2619` (Epic `COREDEV-2485`) · **High** — a live **gate bypass**, documented by the
2026-07-19 audit as MAJ-10 and reproduced twice on this campaign.
**Measured against:** HEAD `5187467` (v2.6.6), worktree `.claude/worktrees/opus5-review`.
**Last Updated:** 2026-07-31 (round 3, post-gate revision)

---

## 0. Prior art — this was already found, and the plan must not pretend otherwise

**`docs/audits/PLUGIN_AUDIT_2026-07-19.md` MAJ-10 identified this defect twelve days before this plan
was written**, with a sharper framing than the first draft had, and with a suggested fix this plan now
adopts. Round 1's first draft cited neither. The audit's material finding:

> *"The entire Plan Review Gate evidence chain runs through fixed, shared, never-pre-cleaned /tmp paths
> … so a stale transcript from a previous round, a different plan, or a concurrent session satisfies the
> dual-review gate as if it were this round's review."*

**That is the defect: a GATE BYPASS, not a measurement error.** §1 is rewritten around it.

## 1. The defect — a stale transcript satisfies the gate

Every review of every plan, in every project, on this machine writes to two fixed names:
`/tmp/agy-out.txt` and `/tmp/codex-out.txt`, plus their `.captureid` sidecars.

**The bypass, as the audit reconstructs it.** The documented flow is 2-6 review rounds per plan, each
overwriting the same two files. Revise the plan, re-snapshot, dispatch the reviews — and one CLI
invocation fails to *start* (auth expired, a Bash-tool-level kill before `pty-capture`'s finally-write,
a `command -v agy` short-circuit). **The previous round's non-empty transcript survives.**
`skills/review-synthesis/SKILL.md` maps only *missing, empty or unparseable* to `MISSING` — **stale is
none of those** — so the old `APPROVE` prose is read as this round's verdict, and
`review-verdict.py write --reviewer gemini=APPROVE:/tmp/agy-out.txt` passes every provenance check:
non-empty, real 64-hex digest, path and captureId distinct from codex's. **All of those checks are
intra-artifact.** The digest binding covers plan bytes, never transcript freshness.

**Two independent reproductions on this campaign:**

1. **Cross-project clobber.** A round-1 codex transcript measured at 769,988 bytes from
   `/tmp/codex-out.txt` held **another project's** plan review by the time it was read — 628 `lumawake`
   hits, **zero** `COREDEV-2497`. Another project's gate round had overwritten the shared path.
2. **Destructive loss.** macOS purged `/private/tmp` under disk pressure and destroyed **105**
   transcripts between two tool calls; two rounds' findings were lost unread.

**Everything else in this plugin is repo-hash namespaced** via `scripts/lib/context.sh`; these paths
are not.

## 2. Why now — 2497 changes the failure mode, and 2617 changed the options

Today a stale transcript passes the gate silently. After `COREDEV-2497` §4.1 lands, `verify` re-digests
every transcript in an approving artifact, so a *clobbered* transcript fails closed — correctly, but
diagnosed as "digest mismatch", pointing at the reviewer rather than the collision. **2619 removes the
collision while it is still fixable in one place.**

**`COREDEV-2617` (v2.6.5) also changed the design space**, which the first draft got wrong: it assumed
`${CLAUDE_PLUGIN_DATA}` was unusable because the variable is unset outside a hook. That conflates two
mechanisms — the **environment variable** is not exported to a Bash tool, but the **`${CLAUDE_PLUGIN_DATA}`
placeholder is substituted anywhere in plugin skill content and the directory is created on first
reference** (plugins reference; confirmed by codex round 1). So the plugin data dir *is* available to a
skill recipe.

## 3. Guiding principle, and the ceiling

**Principle: a capture's path must be unique to the RUN that produced it** — not to the ticket, not to
the round. Round 1's design was per ticket/round and failed on its own terms: a sequential retry of the
same round overwrites its predecessor, which is the defect.

**Ceiling — narrowed after round 1.** This ticket removes an **accidental collision** and makes a stale
capture impossible to mistake for a fresh one. It is **not** a security boundary, and the first draft
over-claimed on three counts, each corrected:

- Captures are **not world-readable** — `pty-capture.py` forces mode `0600`.
- A pre-created leaf symlink is **refused** by `O_NOFOLLOW`, not followed.
- A deterministic `<ticket>r<round>` name **is still predictable**, so "removing predictability" was
  never what this buys.

**And the freshness check (§4.5) is accidental-staleness detection, not operator provenance** — `cp` or
`touch` defeats an mtime comparison. *(Round 2.)*

**What it does buy, security-wise:** a correctly-owned `0700` parent and an **atomically allocated**
name, which together close the squat/pre-seed window on a multi-user host. Detecting a *changed*
transcript is `COREDEV-2497`; cross-checking the verdict token inside it is `COREDEV-2618`.

## 4. Findings and fixes

### 4.1 — The path scheme: per-RUN, atomically allocated (High — round 1, codex)

**Round 1 rejected the round-1 scheme.** `~/.claude/review-transcripts/<ticket>r<round>-<reviewer>.txt`
fails three ways:

- **`.claude` is a PROTECTED path.** Writes there **prompt in default mode and are denied in
  `dontAsk`**, and ordinary allow rules do not pre-approve them. The drift checks M3/M4 could pass while
  the real workflow stalls.
- **Per ticket/round is not per run.** A sequential retry overwrites; concurrent runs need a lock the
  plan never specified. **M1 (refuse) and M2 (same name re-runs cleanly) encoded contradictory
  semantics.**
- **Reservation is defeated by the existing callers.** `pty-capture.py` truncates its target, and
  `scripts/review/isolated-agy-review.sh:89` **deletes the target before launch** — so any scheme that
  reserves *the target itself* is undone by the caller.

**Fix — allocate, do not name.** `pty-capture.py` gains a `--allocate <dir>` mode: it creates the parent
`0700`, then allocates a fresh path with `O_CREAT|O_EXCL` in a retry loop, and **prints the allocated
path on stdout** so the caller propagates it rather than re-deriving it:

```
${XDG_STATE_HOME:-$HOME/.local/state}/unleashed-mail/review-transcripts/<repo-hash>/<ticket>r<round>-<reviewer>-<runid>.txt
```

- **Outside `.claude` entirely — round 2, and this is the SECOND directory this plan has got wrong.**
  Round 1 chose `~/.claude/review-transcripts/`; round 2's "fix" chose `${CLAUDE_PLUGIN_DATA}`, which
  **resolves to `~/.claude/plugins/data/{id}`** — *the same protected tree*. Verified on this machine:
  `/Users/nick/.claude/plugins/data/unleashed-mail-npranson-unleashed-mail-plugin`. Claude Code protects
  `.claude` except `.claude/worktrees`, so writes there prompt in default mode and are **denied** in
  `dontAsk`; "created on first reference" establishes provisioning, not write permission from a skill's
  Bash recipe. **`$HOME/.local/state` is confirmed absent from Claude Code's protected-path list** (round 3), so the
  **default** is correct. But **a set `XDG_STATE_HOME` is not guaranteed safe** — it can be relative,
  point inside `.claude`, or be unwritable. The allocator therefore **validates it: absolute, and outside
  every protected root — otherwise it falls back to `$HOME/.local/state` and says so.** The unqualified
  "outside every protected tree" claim of round 2 was too strong.
- **`<repo-hash>`** — reuse `context.sh`'s existing repo-hash slug, so two checkouts cannot collide.
  Everything else in the plugin is already namespaced this way.
- **`<runid>`** — the atomically allocated component. `O_EXCL` is what makes concurrency safe; refusal
  is **not** the right behaviour, because two legitimate concurrent captures must be able to coexist.
- **Ticket/round stay in the name** for human legibility, not for uniqueness.

**The allocator takes the metadata — round 2.** `--allocate <dir>` alone cannot own a
`<ticket>r<round>-<reviewer>-<runid>` name it is never told the parts of. Interface:
`--allocate --ticket <T> --round <R> --reviewer <name>`, and **the repo hash comes from one shared
helper**: `context.sh`'s slug is Bash and the allocator is Python, so it is exposed once
(`context_repo_hash`, called by the wrapper) rather than reimplemented — otherwise callers rebuild parts
of the path independently, which is the drift this design exists to remove.

**The path must reach synthesis.** `skills/review-synthesis/SKILL.md` currently has **no ticket/round
input contract** — it reads two fixed names. The allocated path is therefore threaded explicitly:
`--reviewer gemini=<STATUS>:<allocated-path>`, and the skill takes the two paths as inputs.

**Proof — M5 (new, round 3): the INTEGRATION mutation M1 cannot give.** A correct allocator whose
callers ignore its stdout and derive a fixed basename **passes M1**. So M5 drives both real paths — the
codex recipe and `isolated-agy-review.sh` — and asserts the **emitted** allocation is the capture
target, the synthesis input, **and** the artifact's `transcriptPath`. Mutate a caller to re-derive the
name: M5 must fail.

**The handoff must be specified before it can be tested**, and round 3 found three gaps: where each
skill obtains ticket/round; how the **codex** recipe reaches the Bash-only `context_repo_hash` when its
grant contains no shell-helper invocation; and how the allocated path is emitted beyond the allocating
invocation. **§8 Q2 carries these** — they are design, not detail.

**Proof — M1, rewritten in round 2 because the first version proved nothing.** Two random basenames are
distinct anyway, and "neither truncated" observes nothing when both files start empty — the assertion
could not fail. Instead: **pre-create a sentinel at the exact candidate the allocator will try first**
(seeded by stubbing the run-ID source), containing known bytes. The allocator must retry on `EEXIST`,
return a *different* path, and **leave the sentinel's bytes untouched**. Assert the parent is `0700`.
Must FAIL against ordinary `create/truncate` and against a name derived from ticket/round.
**Plus, round 3:** `ticket`/`round`/`reviewer` become **filename components**, so a rejection grammar is
required — a separator or `..` would otherwise escape the intended parent. And
`makedirs(mode=0o700, exist_ok=True)` **leaves an existing `0755` parent unchanged**, so M1 must include
a mutation with a **pre-existing mis-moded parent** and assert the allocator fails closed rather than
writing into it. Leaf creation is `0600`; retry is bounded.

### 4.2 — The `allowed-tools` grants are ALREADY broken (High — round 1, codex)

Round 1 established something worse than the first draft claimed. `${HOME}` and `${CLAUDE_PLUGIN_DATA}` are **not** substituted in `allowed-tools`; `${CLAUDE_PLUGIN_ROOT}`
**is** (fixed in Claude Code 2.1.0; this plugin pins 2.1.220).

**ROUND 2 REVERSED THIS — the grants are NOT inert, and the round-1 finding was wrong.**
`${CLAUDE_PLUGIN_ROOT}` substitution in plugin `allowed-tools` was **fixed in Claude Code 2.1.0**, and
this plugin pins **2.1.220** (verified: `claude --version` → `2.1.220`). So the shipped grants *do*
expand, the round-1 "pre-existing defect" does not exist, and the validator proposed in round 1 **would
have rejected a supported placeholder and forced the removal of working grants.**

*(Recorded rather than quietly dropped: codex found this defect in round 1 and refuted it in round 2,
having checked the changelog against the pinned version the second time. A reviewer's finding is a
claim — including when the reviewer is the reliable arm, and including when I have already acted on it.)*

**What remains true** is only that the `rm -f` grants name a literal `/tmp` path this ticket removes.
**`${CLAUDE_PLUGIN_ROOT}` grants are CORRECT and stay** — the validator idea from round 1 is withdrawn
entirely, not narrowed. *(Round 3: the reversal reached §4.2's opening and **three other sites still
asserted the opposite** — the "does not expand" line below, M2's validator, and §7 step 6's CHANGELOG
instruction. Applying a correction in one place and leaving its consequences standing is the exact
defect this campaign has hit in every plan; here I did it to a **reversal of a finding I had already
acted on**.)*

| skill | grant | disposition |
|---|---|---|
| `skills/codex-review/SKILL.md:7` | `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)` | **KEEP — expands correctly** (2.1.0+) |
| `skills/codex-review/SKILL.md:7` | `Bash(rm -f /tmp/codex-out.txt*)` | **DELETE** — allocation removes the need to pre-clean |
| `skills/gemini-review/SKILL.md:8` | `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)` | **KEEP — expands correctly** |
| `skills/gemini-review/SKILL.md:8` | `Bash(rm -f /tmp/agy-out.txt*)` | **DELETE** |

That is a **pre-existing defect this ticket surfaces**, not one it introduces — and it means the fix
cannot be "move the literal", because the literal was never doing what it appeared to do.

**Fix.** The pre-clean stops being a *grant* problem:

- **Allocation replaces cleaning.** With `O_EXCL` allocation there is nothing to pre-clean — a fresh
  path cannot hold a stale transcript. The `rm -f` grants are **deleted**, not rewritten.
- **The outer pre-clean is DELETED, not relocated — round 2.** Round 1 kept it, and codex showed that
  the retained `rm -f` **removes the very file `--allocate` just created with `O_EXCL`**, before
  `pty-capture.py` opens it: the atomic handoff does not survive its own caller. It is also unnecessary.
  **An allocated empty file already fails closed** — synthesis treats empty as `MISSING` — so the
  "wrapper never starts" case the audit reconstructs is covered by allocation itself, not by cleaning.
  A pre-clean only ever existed to compensate for a *shared* name.

**Proof — M2, rewritten twice.** A **runtime** check under a pinned **`dontAsk`** permission mode
(round 3: the round-2 form never named a mode, so a direct-shell check could pass while the shipped
workflow was denied): dispatch a real skill invocation and assert the capture lands. Assert also that no
`/tmp/` literal survives in any `allowed-tools` line. **No substitution validator** — round 1's would
have rejected `${CLAUDE_PLUGIN_ROOT}`, which is supported and correct.

### 4.3 — The site inventory, measured properly this time (Medium — round 1, codex)

**31 matched lines across 13 files**, at `78e28f2`, counting only the two output literals.

| file | lines | rewrite | quote-keep | note |
|---|---|---|---|---|
| `skills/review-synthesis/SKILL.md` | 5 | 5 | 0 | needs a ticket/round input contract (§4.1) |
| `skills/gemini-review/SKILL.md` | 5 | 5 | 0 | its `:24` is `/tmp/agy-ping.txt`, a **different** path, and is NOT among these 5 |
| `skills/codex-review/SKILL.md` | 5 | 5 | 0 | includes the `rm -f` grant, which is **deleted** not rewritten (§4.2) |
| `docs/audits/PLUGIN_AUDIT_2026-07-19.md` | 4 | 0 | 4 | MAJ-10 — the audit finding that named this defect |
| `scripts/pty-capture.py` | 3 | 3 | 0 | `:315-320` is **live implementation commentary** ("the recipes use predictable /tmp paths"), not a historical quote — leaving it after the recipes move would ship false current-state documentation *(round 2)* |
| `skills/brainstorm/SKILL.md` | 2 | 2 | 0 | `--reviewer` examples |
| `README.md` | 1 | 1 | 0 | feature blurb |
| `scripts/review-verdict.py` | 1 | 0 | 1 | `:129`, quotes the duplicate-transcript defect |
| `scripts/tests/test_review_verdict.py` | 1 | 0 | 1 | `:146`, same |
| `CHANGELOG.md` | 1 | 0 | 1 | a shipped release note |
| `docs/planning/OCTO_ADOPTION_PLAN.md` | 1 | 0 | 1 | historical |
| `docs/planning/HANDOFF.md` | 1 | 0 | 1 | historical |
| `docs/planning/COREDEV-2497_VERIFY_TRANSCRIPTS_PLAN.md` | 1 | 0 | 1 | historical |
| **TOTAL** | **31** | **21** | **10** | 13 files |

**Totals: 31 lines, 13 files — 21 rewrites, 10 quote-keeps.**

**`/tmp/agy-ping.txt` is a separate decision.** It is the preflight ping, not an evidence artifact; it is
also a fixed shared path. **Out of scope here, recorded so it is a decision and not an oversight.**

> *(This table has now been wrong **four times**. Round 2 found `pty-capture.py:315-320` misclassified
> as a historical quote when it is **live commentary describing the current recipes** — retaining it
> after the move would ship documentation that contradicts the code. Split: **21/10**. The risk register
> independently said "12 quote-keeps" while the table said 11, so two figures in one document disagreed
> and neither matched the rows. **The lesson has stopped being about arithmetic: a hand-maintained
> inventory in prose cannot be kept true across edits, which is why M3 pins it and why the split is now
> per-file.** Earlier history: the third version was the sharpest — with the line counts
> finally correct at 31/13, the rewrite/quote-keep split still read "19 rewrites, 12 quote-keeps" while
> the rows summed to **20/11**. Draft 1 said 23/7 from a partial grep; the "correction" still said 23/7
> because it **counted `/tmp/agy-ping.txt`** — a different path — and omitted `README.md`,
> `CHANGELOG.md`, the audit and three planning docs. **Every version was internally consistent**, which
> is exactly how a wrong inventory survives review. The per-file split above is now stated so the totals
> can be summed mechanically rather than asserted, and M3 checks them.*
>
> *(Original note:)* *This table has now been wrong twice. Draft 1 said 23/7 from a partial grep; the "correction" still
> said 23/7 because it **counted `/tmp/agy-ping.txt` toward the output-literal total** — a different
> path — and omitted `README.md`, `CHANGELOG.md`, the audit and three planning docs. Both times the
> total was internally consistent, which is how a wrong inventory survives. The figures above are
> `git ls-files | xargs grep -n` over the two literals only.)*

**Proof — M3 (was M5):** a drift check asserting no output literal survives outside the enumerated
`quote-keep` set, and that the set is exactly the one above.

### 4.4 — Two existing defences must keep working (Medium)

- **`review-verdict.py`'s distinct-evidence check** — recording the same transcript for both reviewers
  once produced a **GATE OK in which one review backed both approvals**.
- **`.captureid`** — a per-run random ID, already written fresh on every capture.

**Round 1 correction: neither of these is a pre-fix failure.** `test_review_verdict.py:143-155` already
covers the first, and `pty-capture.py:322-328` already writes a fresh ID every run. They are **regression
tests**, and this plan no longer describes them as proofs that fail before the fix.

### 4.5 — Freshness, which paths alone do not give (Medium — from the audit)

Per-run paths stop a stale transcript being *reused*; they do not prove the transcript is *newer than
the gate launch*. The audit's second suggestion covers that gap: **`review-verdict.py` records and checks
transcript mtime ≥ the snapshot sidecar's mtime**, so a transcript older than the gate launch fails
closed.

**Adopted as in scope, with two round-2 corrections.**

- **It is accidental-staleness detection, not operator provenance.** A determined operator can `cp` or
  `touch` an old transcript. The first draft claimed the stronger property; §3's ceiling now covers this.
- **The explicit `--reviewed-sha256` path has no freshness anchor at all.** That path deliberately
  permits an approving write *without* a snapshot sidecar (`scripts/review-verdict.py:469-493`,
  `skills/review-synthesis/SKILL.md:143-147`), while the proposed check compares only against the
  sidecar's mtime — so M4 could pass for the sidecar case while an implementation skips freshness
  entirely whenever the explicit digest is supplied. **Resolved in round 3, by codex:** a **per-allocation LAUNCH RECORD**, created with `O_EXCL` *before*
  dispatch and bound to the returned run ID, is the anchor — compared by `st_mtime_ns` on **both** digest
  paths. The snapshot sidecar is a poor anchor independently of this, because under concurrency a later
  snapshot overwrites its mtime. **A timestamp first written when the post-review artifact is created is
  not a launch anchor at all.**

**Proof — M4:** record a transcript whose mtime predates the launch anchor; the gate must fail. Run it
**on both paths** — sidecar and explicit-digest.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The chosen directory is protected or unwritable in some permission mode | **High** | §4.1 moved off `.claude`; M2 is a **runtime** check, not a string check |
| The `allowed-tools` grants are "fixed" by rewriting a literal that never expanded | **High** | §4.2 — the grants are **deleted**, and a validator rejects unsupported `${…}` |
| A historical quote is rewritten and the record of a real finding is corrupted | **High** | §4.3's **10** quote-keeps, pinned by M3 *(round 2: this cell said 12 while the table said 11 — the two were never reconciled, and both were wrong)* |
| Allocation is added but callers still derive the name | **High** | `--allocate` **prints** the path; M1 fails a derived name |
| Per-run paths are read as making the gate tamper-proof | Medium | §3's ceiling, in the CHANGELOG |
| Transcripts accumulate without bound | Low | out of scope, stated |

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

Baselines at `78e28f2`: `test-hooks.sh` **304**, synthesizer **227**, scripts **324**, counts
`21/21/0/1`, hook events **10**. Floors, not equalities.

**Mutation proofs M1–M4, each shown failing before the fix and passing after.** *(Round 1: the original
M1-M6 could not meet that bar — M2 and M6 already passed, M3/M4 tested strings rather than runtime
behaviour, and M5 was unsatisfiable against a wrong inventory. The set is rebuilt.)*

## 7. Implementation order

1. **Inventory and classify all 31 sites** and commit the classification — M3 asserts it.
2. **Add `pty-capture.py --allocate`**: `0700` parent, `O_CREAT|O_EXCL` retry loop, print the path.
   Add M1.
3. **Thread the allocated path** through `isolated-agy-review.sh`, both review skills, `brainstorm` and
   `review-synthesis` — including a ticket/round **input contract** for synthesis.
4. **Delete the two `rm -f` grants** and add the `allowed-tools` substitution validator. Add M2.
5. **Add the mtime freshness check** to `review-verdict.py`. Add M4.
6. Version bump + CHANGELOG — state the **ceiling** (§3). **Do not claim the `${CLAUDE_PLUGIN_ROOT}`
   grants were inert**: that was a round-1 finding, reversed in round 2 and verified against the pinned
   2.1.220 in round 3.

## 8. Open questions for round 4

1. **Is `${XDG_STATE_HOME:-$HOME/.local/state}` writable from a skill's Bash recipe in every permission
   mode, including `dontAsk`?** This is the **third** directory this plan has proposed — `~/.claude/`
   (protected), `${CLAUDE_PLUGIN_DATA}` (resolves *into* `~/.claude/plugins/data/`, equally protected),
   now XDG state. **Confirm it against the actual protected-path list rather than by reasoning**, and
   say so explicitly if it is also wrong.
2. **Does deleting the `rm -f` grants leave any path where a pre-clean is still required?**
   `isolated-agy-review.sh` pre-cleans a path it allocated — is that sufficient for the
   "wrapper never starts" case the audit reconstructs?
3. **Should `/tmp/agy-ping.txt` be in scope** after all? §4.3 rules it out as a non-evidence artifact.
4. **How should freshness be anchored on the explicit `--reviewed-sha256` path**, which permits an
   approving write with no snapshot sidecar? Require a launch-time sidecar anyway, or bind a launch
   timestamp into the artifact? §4.5 cannot be implemented until this is chosen.
5. **Does deleting the outer pre-clean actually cover "the wrapper never starts"?** §4.2 argues an
   allocated *empty* file fails closed because synthesis maps empty → `MISSING`. Verify that against
   `review-synthesis` and `review-verdict.py` rather than by assertion.
