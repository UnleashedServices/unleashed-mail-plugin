# COREDEV-2619 — Implementation handoff

**Status:** Implementation authorised by the maintainer **without a passed Plan Review Gate.**
**Plan:** `docs/planning/COREDEV-2619_PER_RUN_TRANSCRIPT_PATHS_PLAN.md`
**Frozen at:** `a0ffd69` · **sha256:** `156442a0f97557a37445be0cfc5883bdff98038d96db1300ff71c4a71f02bfb8`
**Worktree:** `.claude/worktrees/opus5-review` · **Last Updated:** 2026-08-03

---

## 1. The gate decision — read this first

**The gate did not pass.** 84 rounds were run. The best result was `xhigh` returning
`APPROVE_WITH_NOTES` for three consecutive rounds (78–80) while `max` returned `REQUEST_CHANGES`
every round. There is **no Combined-verdict artifact** at
`docs/planning/.verdicts/COREDEV-2619_PER_RUN_TRANSCRIPT_PATHS_PLAN.md.verdict.json`.

**Consequence: codex's `implement` skill will refuse to start.** It is fail-closed by design and
already refused once with `GATE FAILED — no Combined-verdict artifact for this plan`. That refusal
was correct and must not be worked around by fabricating a verdict file.

**The maintainer has explicitly authorised proceeding outside the `implement` workflow**, on the
reasoning that a working implementation is now more informative than an 85th review round. Per
`AGENT_CONTRACTS.md` §2 this is a **workflow exception chosen by the user**, not a passed gate and
not a self-waiver. Record it as such in any Jira note or PR description.

**What this costs:** COREDEV-2497 is blocked on 2619 landing and will inherit the same question.
Decide there separately rather than by precedent.

---

## 2. What is ready

§7's ten steps are the buildable-alone contract. Three were **not** buildable and now are — this was
the single most valuable outcome of the late rounds:

| step | state |
|---|---|
| `S-INVENTORY` | **Now buildable.** Carries the closed frozen manifest with per-file counts. The locked premise is derivable rather than asserted: `5+5+5+3+2+1 = 21` rewrites, `4+1+1+1+1+1+1 = 10` quote-keeps, **31 sites across 13 files**. |
| `S-ALLOC` | Buildable since round 52 (run-ID construction pinned: lowercase hex of ≥16 CSPRNG bytes, encoding only). |
| `S-RELEASE` | **Now buildable.** Carries the closed 39-entry leak manifest with expected object types. |
| the other seven | Audited against the buildable-alone bar in rounds 80–81; no further failures found. |

**The one externally verified artifact.** The `S-RELEASE` leak manifest was checked **set-equal
against the real filesystem** — 39 files in the plan, 39 on disk, nothing in either direction. It is
the only artifact here validated against reality rather than internal consistency, and the only one
that never needed rework. Re-verify it before running the cleanup; the fixtures still exist at
`~/.local/state/unleashed-mail/review-transcripts/`.

---

## 3. Implementation order

Follow §7. Do **not** batch steps — each of the three buildability defects was found on a step that
was queued for implementation, and they were only visible because the step was read in isolation.

1. `S-INVENTORY` — classify the 31 sites; `M3.1` diffs against the frozen manifest.
2. `S-ALLOC` — `pty-capture.py --allocate`.
3. `S-WRAPPER` — `$0`-relative lib resolution; **`${CLAUDE_PLUGIN_ROOT}` is unset in an ordinary Bash
   tool shell** (this broke a fix in round 14; do not reintroduce it).
4. `S-CALLERS` — the closed full-line matcher, default-deny.
5. `S-CAPTURE` — honour the reservation: **no `O_CREAT`, no `O_TRUNC`** in allocated mode.
6. `S-THREAD` — path threaded as one opaque shell argument.
7. `S-PRECLEAN` · 8. `S-M5` · 9. `S-FRESH` · 10. `S-RELEASE`.

A prepared prompt for step 1 exists at `.codex-impl-2619-S-INVENTORY.md`. It scopes the agents
correctly: this is Python and Bash in a plugin repo, so `db-engineer`/`logic-engineer`/`ui-engineer`
do not apply; `tester`, `code-simplifier` and `context7-mcp` do.

---

## 4. Residuals to carry as implementation-time checks

These are unresolved at freeze. None blocks starting; each should be settled by the code rather than
by another review round.

- **Caller-scan exemption manifest.** Identity is `(repo-relative path, FINAL physical-line number,
  SHA-256(line payload))`, bound **only after every implementation, test, doc, inventory and caller
  edit is final**. It is **deliberately not shift-stable** — any later shift or move must fail and
  demand an explicit reviewed update. **Generate it last.** Do not re-propose a shift-stable identity
  without addressing the `hooks/hooks.json:121`/`:133` collision (byte-identical candidates, identical
  neighbours — a content-only identity is not injective on this tree).
- **Round 84's findings** — the round was in flight at freeze. Fold them in here when it lands.
- Anything `xhigh` raised as a *note* while approving rounds 78–80.

---

## 5. Tooling built during the campaign

All outside the worktree, in `~/.claude/review-transcripts/`:

| file | purpose |
|---|---|
| `run-2619-dual.sh` | both codex tiers concurrently on one prompt; gate condition evaluated in-script |
| `build-round-prompts.py` | one prompt for both arms; **derives the §6.1 invariant from the document** rather than asserting it |
| `build-apply-prompt.py` | union of both arms' remediations, digest frozen automatically |
| `isolated-kimi-review.sh` | Kimi K3 behind a disposable-worktree harness (K3 has **no sandbox flag**) |
| `chk-2619-60.py` / `chk-2619-61.py` | §6.0 canonical-token and §6.1 cell/row invariants |
| `remediation-section.md` | canonical remediation block, appended fresh each round so it cannot drift |

---

## 6. Hard-won constraints — violating these has cost rounds

- **`codex exec` must pass `-c model_reasoning_effort=max` explicitly.** The config default is
  `xhigh` and has silently reset to `low` before. Every runner pins it.
- **Never `pkill -f pty-capture.py`** — shared by codex, agy and Kimi. Match distinguishing args.
- **Do not edit the worktree while a review round is in flight**, including tooling files.
- **Transcripts must not live in `/tmp`** — macOS purged them once, and purged the checkers twice.
- **codex's `workspace-write` sandbox cannot read `$HOME`.** Anything requiring evidence outside the
  workspace (the leak manifest) must be produced outside the apply.
- **Verify by testing the deletion, not the presence**, and **check the actual tree, not the
  reasoning**. My own checkers were wrong **eleven times** in this campaign, always the same way:
  assuming the shape of the thing being searched for, then reporting absence as proof.

---

## 7. Method notes worth keeping

- **Two tiers of the same model disagreed on roughly three-quarters of findings.** `xhigh` approved
  documents `max` found Highs in, on byte-identical prompts. The higher tier buys depth, not variance.
- **An independent family (Kimi K3) found a real defect both codex arms missed** — stale `file:line`
  citations — but **approved a document containing a genuine High**. Useful as a hygiene sweep; not
  gate-worthy.
- **Prefer deleting an overclaim to inventing a bigger proof.** Three rounds resolved that way, every
  time on a reviewer's recommendation.
- **A positive proved at a boundary does not prove the region** — and the fix for that defect was
  itself a boundary positive one level deeper, twice.
