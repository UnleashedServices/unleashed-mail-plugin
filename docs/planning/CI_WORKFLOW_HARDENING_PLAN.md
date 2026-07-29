# CI & Workflow Hardening Plan

**Status:** Planning — awaiting dual plan-review gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29
**Tickets (batched — see §1 for why):**
- `COREDEV-2598` — CI proves the plugin **loads**, not just that it validates
- `COREDEV-2600` — CI drift guard for duplicated primitives
- `COREDEV-2603` — the plan-review verdict is bound to an absolute path

**Epic:** `COREDEV-2485` — Plugin audit remediation / agent-skill-hook-CI modernization
**Branch:** `feat/COREDEV-2598-ci-workflow-hardening`
**Target version:** `2.6.1` → **`2.6.2`** (patch: CI + tooling only, no shipped-asset behaviour change).
**Sequencing note:** `COREDEV-2597` also lands on 2.6.1. If it merges first this becomes 2.6.2; if not,
renumber — the version is not load-bearing for any item here.

---

## 1. Context, and why these three are one plan

Three findings from the same review pass, sharing one root cause: **a gate that cannot fail, or cannot
be reached, is not a gate.** Each is small, independent in code, and would otherwise cost its own
multi-round review for a handful of lines.

| | Ticket | The gate that does not work |
|---|---|---|
| A | 2598 | We validate the plugin's **schema** but never prove it **loads** |
| B | 2600 | Duplicated primitives can silently diverge; two provably already have |
| C | 2603 | An approval cannot survive the worktree move the repo's own conventions mandate |

They touch disjoint files — `.github/workflows/plugin-ci.yml` (A), `scripts/lib/` + tests (B),
`scripts/review-verdict.py` (C) — so batching costs nothing in merge risk. **C is the one with teeth**:
it changes a security-relevant provenance path, and §4.3 keeps it conservative for that reason.

**What batching does not do:** it does not lower the bar per item. Each keeps its own mutation proof and
its own acceptance criteria, and any reviewer may split one back out.

## 2. Scope

**In:** a scratch-install load check in CI; a drift guard for the duplicated base-path expansion and the
divergent `mtime`/round-scan idioms; and repo-relative plan identity in the verdict artifact.

**Out:** the **redactor** parity fixture — that is `COREDEV-2597` §4.4, on the same files this plan's
item B touches. B covers the base-path copies, the round scanners and the `mtime` idioms **only**.

**Out:** weakening the verdict's **digest** binding. Approval ↔ exact reviewed bytes is correct and
stays. Only *identity* changes (§4.3).

## 3. Guiding principle

> **A gate must be able to fail, and must be reachable by the workflow the repo tells you to use.** Item
> A adds a gate that can fail where none existed; B makes silent divergence loud; C removes a false
> failure that the documented workflow provokes.

Corollary, learned the hard way this cycle: **a new gate must itself be mutation-proved.** Two checks
written in this epic looked correct, passed on a clean tree, and were inert — one because it ran before
the data it checked existed, one because its marker also appeared elsewhere. Every item below states how
it is made to fail.

---

## 4. Findings, fixes, and proofs

### 4.1 — A: CI never proves the plugin loads (Medium)

**Root cause.** `.github/workflows/plugin-ci.yml` runs `claude plugin validate --strict .` (`:96`) and
`claude plugin validate .claude-plugin/plugin.json` (`:104`). Both are **schema** validation. Nothing
installs the plugin and confirms it reaches an enabled state.

That matters here specifically: we ship **21 agents, 21 skills, 12 hook invocations across 10 events,
and a bundled stdio MCP server**. A load-layer failure — a duplicate declaration, a manifest the loader
rejects, an MCP server that fails to start — passes schema validation and reaches users.

Adopted from `ayghri/i-have-adhd` (MIT), whose workflow comment records exactly this: *"Catches
load-layer breakage that schema validation misses, e.g. the duplicate hooks declaration in #61."*

**Fix.** A step in the existing `plugin-ci.yml` (not a separate workflow — keep one CI surface) that
installs from the checkout into a scratch `CLAUDE_CONFIG_DIR` and asserts the plugin is enabled. Reuse
the existing `CLAUDE_CODE_VERSION` pin (now `2.1.220`) so the load check and the schema checks run on
the **same** CLI.

**Note for the reviewer — do not copy the source's assertion.** Theirs greps for the literal `✔ enabled`
glyph. That is a presentation detail of `claude plugin list`, and this repo pins a CLI it intends to
bump; a cosmetic change would silently turn the gate into a no-op. Prefer a machine-readable form if
2.1.220 offers one (`--json` or equivalent — **check, do not assume**), else assert on the plugin name
plus a non-enabled sentinel being absent.

**Proof.** A deliberately broken manifest in a scratch copy must fail the job. **A load check that
cannot fail is worse than none** — this is the item most at risk of shipping inert.

### 4.2 — B: duplicated primitives can silently diverge (Medium)

**Root cause.** Verified in-tree:

- **Three copies** of the plugin-data base expansion, none referencing each other:
  `scripts/lib/marker.sh:19`, `scripts/lib/log.sh:17`, `scripts/lib/context.sh:23`. Currently identical
  — including the `${HOME:-}` inner guard that exists so `set -u` cannot abort a hook. An edit dropping
  that guard in one copy breaks only the paths routing through that lib.
- **Two round scanners** that already disagree: `precompact-snapshot.sh`'s inline loop vs
  `context.sh::context_highest_round`. With a `round-09` directory the snapshot records `"09"` where the
  shared helper returns `9`.
- **Two `mtime` idioms**, one documented as wrong: `marker.sh` branches on `uname == Darwin`;
  `context.sh::_context_file_mtime` and `sessionstart-restore.sh` feature-detect, with a comment
  explaining that not all BSDs report Darwin.

**Fix.** Not forced deduplication — some duplication is legitimate (different runtimes, different
call sites). The goal is that **divergence becomes visible and intentional**:

1. Single-source or assert byte-equality for the base expansion.
2. Make `precompact-snapshot.sh` use the shared `context_highest_round`, or document why it must not.
3. Name the feature-detect `mtime` form canonical and assert `marker.sh` matches, or record the
   exception.

**Note for the reviewer.** Pattern adopted from the same MIT source's `cursor-skill-sync.yml`, which
fails CI when two copies of a file drift. We have no second harness to sync, but the **guard** shape
transfers.

**Proof.** Edit one base expansion without the others → CI fails naming both files. Change one `mtime`
idiom → fails. Each assertion mutation-proved individually.

### 4.3 — C: an approval cannot survive the mandated worktree move (Medium)

**Root cause.** Two mandatory `CLAUDE.md` conventions contradict each other. It requires working in a
dedicated `.claude/worktrees/<name>` worktree, **and** requires `implement`'s verify step to pass — but
the verdict artifact records the plan's **absolute** path:

```json
"planPath": "/Users/…/.claude/worktrees/opus5-review/docs/planning/OPUS5_ALIGNMENT_PLAN.md"
```

Hit directly this cycle: gating `COREDEV-2583` in one worktree and creating a feature worktree to
implement in produced `GATE FAILED — artifact was written for a different plan`, with **byte-identical**
plan content (both `a6f89ba0d37e…`) and a genuine five-round approval. The artifact also lives in
git-ignored `.verdicts/`, so it does not travel with the branch either.

Consequences: CI can never verify an approval; renaming the repo directory invalidates every existing
one; a second developer cannot verify at all.

**Fix — deliberately the conservative option.** Store the plan identity **repo-relative**
(`docs/planning/X_PLAN.md`) and keep the SHA-256 digest binding exactly as-is. The digest already
prevents substitution — the path only needs to say *which* plan, not *where on this disk*.

**Note for the reviewer — this is the item that needs the most scrutiny.** The absolute path is
presumably part of the COREDEV-2499 provenance work, so the questions are: (a) does anything rely on the
path being absolute; (b) can a repo-relative path be spoofed in a way the digest does not already
prevent; (c) should the artifact record *both*, with the absolute one advisory? **If the reviewers judge
this insufficiently safe, the zero-code fallback is §8 Q3** — document the constraint loudly and require
creating the feature worktree *before* gating.

**Proof.** Same bytes, different path → the chosen behaviour is asserted **explicitly**, not incidental.
Plus a negative: different bytes, same path → still fails.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The load check ships inert (asserts nothing) | **High** | §4.1's proof is a deliberately broken manifest; the glyph-grep is called out as the specific trap |
| The load check is flaky in CI (network install) | Medium | Bounded runtime, pinned CLI; it is an install, not a session. If flaky, quarantine rather than weaken the assertion |
| Relaxing the verdict path weakens provenance | **Medium** | Digest binding untouched; §8 Q3 keeps a zero-code fallback if reviewers disagree |
| B's guard fights legitimate divergence | Medium | Goal is *visible and intentional*, not identical: exemptions are enumerated and commented |
| Overlap with 2597 §4.4 (redactor parity) | Medium | Explicitly out of scope here (§2); if 2597 lands first this contributes fixtures instead |
| Batching hides a weak item behind two strong ones | Medium | Each keeps its own acceptance criteria and mutation proof; any reviewer may split one out |

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

Baselines to hold: `test-hooks.sh` **302**, synthesizer **191**, scripts **269**, counts `21/21/0/1`,
hook events **10**.

**Mutation proof required for every item.** §3's corollary is not rhetorical — two checks written in
this epic were inert while passing on a clean tree.

## 7. Implementation order

1. §4.2 (B) — pure test/lib work, no external dependency.
2. §4.1 (A) — the CI job, including its deliberate-failure proof.
3. §4.3 (C) — last, because it is the only security-relevant change and benefits from the other two
   being green first.
4. Version bump + CHANGELOG.

## 8. Open questions for the reviewers

1. **Is `claude plugin list` machine-readable on 2.1.220?** If it offers `--json`, the load assertion
   should use it. If not, what is the most change-resistant assertion that can still genuinely fail?
2. **Should B force deduplication or only detect divergence?** Detection preserves legitimate
   differences but leaves three copies to keep in step. Single-sourcing the base expansion is a
   two-line change with a wider blast radius across hook paths.
3. **Is repo-relative plan identity acceptable, or should the constraint just be documented?** §4.3
   argues the digest already carries the security. The zero-code alternative — require creating the
   feature worktree before gating, and say so in `implement`/`review-synthesis` — costs nothing and
   changes no provenance code. **This is the maintainer's call as much as the reviewers'.**

## 9. Notes

- Every claim was verified in-tree this cycle: the missing load check, the three base-path copies, the
  two divergent round scanners and `mtime` idioms, and the verdict-path failure (reproduced with
  byte-identical plans).
- Items A and B adopt patterns from `ayghri/i-have-adhd` (MIT). No code is copied; the designs are
  reimplemented against this repo's conventions.
- `COREDEV-2599` (evals harness) is deliberately **not** batched here: it is large, costs money to run,
  and needs its own plan.
