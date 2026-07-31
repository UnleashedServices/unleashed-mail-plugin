# COREDEV-2619 — Per-run transcript paths

**Status:** Planning — **round 1 gated (codex `REQUEST_CHANGES` ×3 High + ×2 Medium; the gemini arm
degenerated and produced no verdict).** Blocks `COREDEV-2497`, whose §7 step 1 requires this to land
first.
**Ticket:** `COREDEV-2619` (Epic `COREDEV-2485`) · **High** — a live **gate bypass**, documented by the
2026-07-19 audit as MAJ-10 and reproduced twice on this campaign.
**Measured against:** HEAD `78e28f2` (v2.6.6), worktree `.claude/worktrees/opus5-review`.
**Last Updated:** 2026-07-31 (round 1, post-gate revision)

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
${CLAUDE_PLUGIN_DATA}/review-transcripts/<repo-hash>/<ticket>r<round>-<reviewer>-<runid>.txt
```

- **`${CLAUDE_PLUGIN_DATA}`** — substituted in skill content, created on first reference, and *not*
  protected. Replaces `~/.claude/`.
- **`<repo-hash>`** — reuse `context.sh`'s existing repo-hash slug, so two checkouts cannot collide.
  Everything else in the plugin is already namespaced this way.
- **`<runid>`** — the atomically allocated component. `O_EXCL` is what makes concurrency safe; refusal
  is **not** the right behaviour, because two legitimate concurrent captures must be able to coexist.
- **Ticket/round stay in the name** for human legibility, not for uniqueness.

**The path must reach synthesis.** `skills/review-synthesis/SKILL.md` currently has **no ticket/round
input contract** — it reads two fixed names. The allocated path is therefore threaded explicitly:
`--reviewer gemini=<STATUS>:<allocated-path>`, and the skill takes the two paths as inputs.

**Proof — M1 (new):** two concurrent `--allocate` calls in the same directory must yield **two distinct
paths, both created**, and neither truncated. Must FAIL against a scheme that derives the name from
ticket/round.

### 4.2 — The `allowed-tools` grants are ALREADY broken (High — round 1, codex)

Round 1 established something worse than the first draft claimed. `allowed-tools` documents substitution
for **`${CLAUDE_SKILL_DIR}` and `${CLAUDE_PROJECT_DIR}` only** — not `${HOME}`, not
`${CLAUDE_PLUGIN_ROOT}`, not `${CLAUDE_PLUGIN_DATA}`.

**So the two shipped grants are already unsupported substitutions, today:**

| skill | grant | status |
|---|---|---|
| `skills/codex-review/SKILL.md:7` | `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)`, `Bash(rm -f /tmp/codex-out.txt*)` | the `${CLAUDE_PLUGIN_ROOT}` prefix **does not expand** |
| `skills/gemini-review/SKILL.md:8` | `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)`, `Bash(rm -f /tmp/agy-out.txt*)` | same |

That is a **pre-existing defect this ticket surfaces**, not one it introduces — and it means the fix
cannot be "move the literal", because the literal was never doing what it appeared to do.

**Fix.** The pre-clean stops being a *grant* problem:

- **Allocation replaces cleaning.** With `O_EXCL` allocation there is nothing to pre-clean — a fresh
  path cannot hold a stale transcript. The `rm -f` grants are **deleted**, not rewritten.
- **The outer pre-clean stays where it must.** Moving it into `pty-capture.py` cannot cover
  "the wrapper never starts", which is exactly the case `isolated-agy-review.sh:86-91` exists for and
  exactly the audit's reconstructed bypass. That outer `rm -f` targets a path the harness itself just
  allocated, so it needs no literal-path grant.

**Proof — M2 (new, replaces the old M3/M4):** a **runtime** check, not a string check. Assert that the
gate completes with **no `/tmp/` literal and no unsupported substitution in any `allowed-tools` line**,
and that a validator rejects any `allowed-tools` value containing a `${…}` outside
`{CLAUDE_SKILL_DIR, CLAUDE_PROJECT_DIR}`. The old M3/M4 proved only string consistency and would have
passed while the workflow stalled.

### 4.3 — The site inventory, measured properly this time (Medium — round 1, codex)

**31 matched lines across 13 files**, at `78e28f2`, counting only the two output literals.

| file | lines | rewrite | quote-keep | note |
|---|---|---|---|---|
| `skills/review-synthesis/SKILL.md` | 5 | 5 | 0 | needs a ticket/round input contract (§4.1) |
| `skills/gemini-review/SKILL.md` | 5 | 5 | 0 | its `:24` is `/tmp/agy-ping.txt`, a **different** path, and is NOT among these 5 |
| `skills/codex-review/SKILL.md` | 5 | 5 | 0 | includes the `rm -f` grant, which is **deleted** not rewritten (§4.2) |
| `docs/audits/PLUGIN_AUDIT_2026-07-19.md` | 4 | 0 | 4 | MAJ-10 — the audit finding that named this defect |
| `scripts/pty-capture.py` | 3 | 2 | 1 | `:317` names the path its `O_NOFOLLOW` defends |
| `skills/brainstorm/SKILL.md` | 2 | 2 | 0 | `--reviewer` examples |
| `README.md` | 1 | 1 | 0 | feature blurb |
| `scripts/review-verdict.py` | 1 | 0 | 1 | `:129`, quotes the duplicate-transcript defect |
| `scripts/tests/test_review_verdict.py` | 1 | 0 | 1 | `:146`, same |
| `CHANGELOG.md` | 1 | 0 | 1 | a shipped release note |
| `docs/planning/OCTO_ADOPTION_PLAN.md` | 1 | 0 | 1 | historical |
| `docs/planning/HANDOFF.md` | 1 | 0 | 1 | historical |
| `docs/planning/COREDEV-2497_VERIFY_TRANSCRIPTS_PLAN.md` | 1 | 0 | 1 | historical |
| **TOTAL** | **31** | **20** | **11** | 13 files |

**Totals: 31 lines, 13 files — 20 rewrites, 11 quote-keeps.**

**`/tmp/agy-ping.txt` is a separate decision.** It is the preflight ping, not an evidence artifact; it is
also a fixed shared path. **Out of scope here, recorded so it is a decision and not an oversight.**

> *(This table has now been wrong **three times**, and the third is the sharpest: with the line counts
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

**Adopted as in scope**, because without it a determined operator can still hand the gate an old file by
path. **Proof — M4 (new):** record a transcript whose mtime predates the snapshot; the gate must fail.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The chosen directory is protected or unwritable in some permission mode | **High** | §4.1 moved off `.claude`; M2 is a **runtime** check, not a string check |
| The `allowed-tools` grants are "fixed" by rewriting a literal that never expanded | **High** | §4.2 — the grants are **deleted**, and a validator rejects unsupported `${…}` |
| A historical quote is rewritten and the record of a real finding is corrupted | **High** | §4.3's 12 quote-keeps, pinned by M3 |
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
6. Version bump + CHANGELOG — state the **ceiling** (§3) and that the `${CLAUDE_PLUGIN_ROOT}` grants
   were already inert.

## 8. Open questions for round 2

1. **Is `${CLAUDE_PLUGIN_DATA}` genuinely written-to-able from a skill recipe** in every permission
   mode, including `dontAsk`? §4.1 rests on it, and round 1 showed the first draft's directory choice
   was wrong for exactly this reason.
2. **Does deleting the `rm -f` grants leave any path where a pre-clean is still required?**
   `isolated-agy-review.sh` pre-cleans a path it allocated — is that sufficient for the
   "wrapper never starts" case the audit reconstructs?
3. **Should `/tmp/agy-ping.txt` be in scope** after all? §4.3 rules it out as a non-evidence artifact.
4. **Is the mtime check (§4.5) sound**, or does a legitimate re-capture ever produce an mtime older
   than the snapshot?
