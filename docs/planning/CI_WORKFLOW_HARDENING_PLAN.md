# CI & Workflow Hardening Plan

**Status:** Planning — round 2, awaiting re-gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29 (round 2)
**Tickets (batched — see §1 for why):**
- `COREDEV-2598` — CI proves the plugin **loads**, not just that it validates
- `COREDEV-2600` — CI drift guard for duplicated primitives
- `COREDEV-2603` — the plan-review verdict is bound to an absolute path

**Epic:** `COREDEV-2485` — Plugin audit remediation / agent-skill-hook-CI modernization
**Branch:** `feat/COREDEV-2598-ci-workflow-hardening`
**Target version:** `2.6.1` → **`2.6.2` or `2.6.3`** (see sequencing).

> **Item A and C are CI/tooling only. Item B touches shipped assets.**
> `scripts/lib/{marker,log,context}.sh` and `scripts/precompact-snapshot.sh` all run from
> `${CLAUDE_PLUGIN_ROOT}` in an installed plugin (`hooks/hooks.json:101`; `README.md:378` lists the
> script in the shipped hook table; `plugin.json` has no `files`/`include` filter and there is no
> `.gitattributes`, so nothing excludes them). Under §4.2's chosen fixes the PreCompact hook's `round`
> field changes from `"09"` to `9` — a **shipped behaviour change**, which belongs in the CHANGELOG
> under *Changed*, not *Fixed*, and must be mutation-proved as such.
> *(Round 1 asserted "no shipped-asset behaviour change". That was wrong on the files, and it also
> pre-decided an outcome §8 Q2 had not yet resolved.)*

**Sequencing note.** 2.6.1 is **already released** (COREDEV-2602, commit `04f906d` — `plugin.json`,
`README.md:1`, `CHANGELOG.md:16` all agree), so neither this plan nor `COREDEV-2597` can take it. Both
branch from 2.6.1 and are independent: **whichever merges first is `2.6.2`; the second rebases and
becomes `2.6.3`.** The version is not load-bearing for any item here — do not hard-code it in a commit
message or a test until the merge order is known.

---

## 1. Context, and why these three are one plan

Three findings from the same review pass, sharing one root cause: **a gate that cannot fail, or cannot
be reached, is not a gate.** Each is small, independent in code, and would otherwise cost its own
multi-round review for a handful of lines.

| | Ticket | The gate that does not work |
|---|---|---|
| A | 2598 | We validate the plugin's **schema** but never prove it **loads** |
| B | 2600 | Duplicated primitives can silently diverge; three provably already have |
| C | 2603 | An approval cannot survive the worktree move the repo's own conventions mandate |

They touch disjoint files — `.github/workflows/plugin-ci.yml` (A), `scripts/lib/` + tests (B),
`scripts/review-verdict.py` + docs (C) — so batching costs nothing in merge risk.

**Round-2 note on C.** Round 1 flagged C as "the one with teeth" because it looked security-relevant.
**It is not** (§4.3), so it stays in the batch — but it becomes the item that changes *two* things,
docs and code, in that order.

**What batching does not do:** it does not lower the bar per item. Each keeps its own mutation proof and
its own acceptance criteria, and any reviewer may split one back out.

## 2. Scope

**In:** a scratch-install load check in CI that tests **the checkout's own bytes**; single-sourcing of
the duplicated base-path expansion and round scanner and normalisation of the `mtime` idiom; and
repo-relative plan identity in the verdict artifact, preceded by the documentation ordering that makes
it unnecessary in the happy path.

**Out:** the **redactor** parity fixture — that is `COREDEV-2597` §4.4, on the same files this plan's
item B touches. B covers the base-path copies, the round scanners and the `mtime` idioms **only**.
*(2597 §2 now agrees; in round 1 the two plans contradicted each other on this.)*

**Out:** weakening the verdict's **digest** binding. Approval ↔ exact reviewed bytes is correct and
stays. Only *identity* changes (§4.3).

**Out — and this is the honest scoping round 1 got wrong:** making the verdict artifact **travel**.
`.verdicts/` is git-ignored twice over — at the repo root (`.gitignore:7`) *and* self-ignored by a `*`
`.gitignore` that `_ensure_secure_dir` (`review-verdict.py:298-304`) deliberately writes inside the
directory. Verified: a fresh `git clone` and a fresh `git worktree add` both produce a `docs/planning/`
containing only the plan. **CI-side and second-developer verification are impossible under any path
scheme** and are not addressed here; fixing them means reversing the never-commit decision from PR #39,
which this plan does not propose.

**Out, but must be declared:** `DECISION_JOURNAL_PLAN.md` (`COREDEV-2585`) §4.1 identifies the *same*
`precompact-snapshot.sh` round-scan defect with the *same* `round-09` experiment, and its
§4.3/§4.4/§4.9/§4.10/§4.11 rewrite `sessionstart-restore.sh`, `scripts/lib/context.sh` and the
atomic-write idiom. 2585 is **PAUSED** and chained 2583 → 2584 → 2585 at 2.7.1, so **this plan lands
first by construction** — nothing needs deciding about ordering. What was missing was any
cross-reference at all: round 1 cited 2597 three times and 2585 **zero** times. Item B must therefore
(a) stay a *guard/consolidation*, not a redesign, so 2585 rebases onto it rather than reverting it, and
(b) if §4.2's round-scanner fix lands here, **2585 §4.1's round bullet is resolved and must be struck**
when 2585 unpauses.

## 3. Guiding principle

> **A gate must be able to fail, and must be reachable by the workflow the repo tells you to use.** Item
> A adds a gate that can fail where none existed; B makes silent divergence impossible rather than
> merely visible; C removes a false failure that the documented workflow provokes.

Corollary, learned the hard way this cycle: **a new gate must itself be mutation-proved, and the
mutation must be one a real implementer might write.** Round 1's own proofs failed this — §4.1's
assertion passes against the very defect it cites, §4.2's proof presupposes the duplicates survive, and
both of §4.3's proofs pass with identity checking deleted entirely. Every item below states the mutant
it rejects.

---

## 4. Findings, fixes, and proofs

### 4.1 — A: CI never proves the plugin loads (Medium → High after round 2)

**Root cause.** `.github/workflows/plugin-ci.yml` runs `claude plugin validate --strict .` (`:96`) and
`claude plugin validate .claude-plugin/plugin.json` (`:104`). Both are **schema** validation. Nothing
installs the plugin and confirms it reaches an enabled state.

That matters here specifically: we ship **21 agents, 21 skills, 12 hook invocations across 10 events,
and a bundled stdio MCP server**. A load-layer failure passes schema validation and reaches users.

Adopted from `ayghri/i-have-adhd` (MIT), whose workflow comment records exactly this: *"Catches
load-layer breakage that schema validation misses, e.g. the duplicate hooks declaration in #61."*

**Round 2 raises the severity, because the naïve adoption was reproduced and it silently passes.**
Running upstream's own recipe — `claude plugin marketplace add "$GITHUB_WORKSPACE"` (verbatim line 27
of their `plugin-load-check.yml`) then `claude plugin install` — against **our** manifest **git-cloned
`UnleashedServices/unleashed-mail-plugin` main** into the cache and reported `enabled: true`. The
installed tree was **v2.5.3**, not the branch's 2.6.1, and this plan file was absent from it. Upstream
can use that recipe only because their marketplace entry is `"source": "./"`; ours
(`.claude-plugin/marketplace.json:13-16`) is `{"source":"github","repo":"UnleashedServices/…"}`. A green
check over the wrong bytes is worse than no check.

**Fix — three parts, each independently mutation-proved.**

**(a) Install the checkout's own bytes.** CI must `rsync` the checkout to `$RUNNER_TEMP/plugin-src`,
rewrite **that copy's** `plugins[*].source` to `"./"`, and add *that* directory as a scratch
marketplace under a scratch `CLAUDE_CONFIG_DIR`. Absolute-path and `../`-relative sources are both
rejected by the loader (`plugins.0.source: Invalid input`), so `"./"` in a copy is the only expressible
form. **Never mutate `$GITHUB_WORKSPACE` itself.** Accept and state the fidelity gap: CI then tests a
manifest differing from the shipped one by one field, so the `source: github` path is never exercised —
that path is GitHub's job, not ours. Say so in the workflow comment so nobody later "fixes" it back.

**(b) Assert on parsed JSON.** **Open question 1 is answered: `claude plugin list --json` IS supported
on the pinned 2.1.220** (both reviewers confirmed; fields `id`, `version`, `scope`, `enabled`,
`installPath`, `installedAt`, `lastUpdated`, `mcpServers`). Require exactly one entry matching
`unleashed-mail@<scratch-marketplace-name>` with `enabled == true`, **and** assert `version` equals the
checkout's `plugin.json` version — that second assertion is what catches the remote-clone regression in
(a). Do **not** grep for `✔ enabled`: the glyph does exist on 2.1.220, so a naïve port passes today and
gives false confidence, which is exactly the brittleness this plan warned about.

**(c) `enabled` is registry state — necessary, not sufficient.** Proven twice over: with `.mcp.json`
repointed at a nonexistent file the install still exits 0 and reports `enabled: true` (and the reported
`mcpServers` still contains a literal **unexpanded** `${CLAUDE_PLUGIN_ROOT}` — it is an echo of the
manifest, not runtime state); and **issue #61's own duplicate-hooks defect installs, reports
`enabled: true`, and passes `claude plugin validate --strict`**, because that error surfaces on
**reload**, not install. So the step must additionally assert:

- **MCP actually starts** — drive an `initialize` + `notifications/initialized` + `tools/list`
  handshake against `mcp/review-synthesizer/mcp_server.py` resolved from the reported `installPath`,
  and assert the negotiated `protocolVersion`, `serverInfo.name == "review-synthesizer"` and
  `tools == ["synthesize_review"]`. The server's readiness banner is on **stderr**, so stdout stays
  clean JSON-lines; run under `set -o pipefail`.
- **Hooks load** — the CLI exposes no reload/hook-load surface, so use the existing
  `scripts/validate-hooks.py --strict --require-manifest` **plus an explicit assertion that
  `plugin.json` has no `hooks` key**, since `hooks/hooks.json` is auto-loaded and re-declaring it
  silently drops the whole hook set. That is #61's exact defect class, and it is the one the MCP
  handshake alone does **not** catch.

*(Round 1's §4.1 claimed the check would catch "an MCP server that fails to start" while proposing only
an enabled assertion. Round 2 either proves it or drops it — it proves it.)*

**Proof.** A deliberately broken manifest in the scratch copy must fail the job, and **the mutation must
be at the top of the mutated file.** Trap hit while verifying: `mcp_server.py` ends with
`raise SystemExit(main())`, so appending broken code at EOF is dead code and the check passes green —
the first attempted "failing" case passed for exactly this reason. Three named mutants, each must fail
a *different* assertion:

1. `plugin.json` gains a `hooks` key (#61's defect) → **(c) hooks assertion** fails; `validate --strict`
   and `enabled` both still pass, which is the point.
2. `.mcp.json` repointed at a nonexistent server file → **(c) MCP handshake** fails; install still
   reports `enabled: true`.
3. `marketplace.json` source left as `github` → **(b) version assertion** fails, because the installed
   version is main's, not the checkout's.

**A load check that cannot fail is worse than none** — this remains the item most at risk of shipping
inert, and it now has three specific mutants instead of one adjective.

### 4.2 — B: duplicated primitives have already diverged (Medium)

**Root cause.** Verified in-tree, with round-2 corrections to the counts:

- **Three copies** of the plugin-data base expansion: `scripts/lib/marker.sh:19`, `scripts/lib/log.sh:17`,
  `scripts/lib/context.sh:23`. The **expression** is byte-identical in all three (same md5), but the
  **lines are not** — `context.sh:23` is a one-line function definition while the other two are bare
  `printf` lines (`cmp` reports "differ: char 1"). *(Round 1 said "currently identical". A literal
  byte-equality gate would therefore be **red on an unmodified checkout**.)*
- **Three bash round scanners**, not two: `context.sh:119` (`context_latest_round_dir`),
  `context.sh:153` (`context_highest_round`), and `precompact-snapshot.sh:45-51` (inline) — plus a
  fourth in Python at `capture.py:216`/`:238`.
- **Four `mtime` sites in three shapes**, not two idioms: `marker.sh:175` branches on `uname == Darwin`;
  `context.sh:182-183` is try-BSD-then-GNU; `sessionstart-restore.sh:41-44` is probe-then-rerun; and
  **`scripts/test-hooks.sh:695` uses the wrong `uname` shape too** — the harness that would have to
  prove the fix is itself a diverged copy.

**The motivating symptom was the wrong one.** Round 1 led with `"09"` vs `9`, which is **cosmetic** —
that value reaches only a human-readable hint string (`sessionstart-restore.sh:74,76`). The load-bearing
divergence, named by neither reviewer: **the inline copy lacks `context_highest_round`'s `??????*`
digit cap and its `10#` decimal normalisation**, so a `round-<20-digit>` directory — producible through
shipped code via `UNLEASHED_REVIEW_ROUND` (`capture.py:230`/`:172`) — makes the PreCompact hook print
`[: …: integer expression expected` to **stderr**, violating the stderr-clean fail-open invariant.
Lead with that.

**Fix — three separate decisions, not three "X or Y"s.** *(Round 1's "single-source **or** compare",
"reuse **or** document", "assert **or** record an exception" is what made this unimplementable.)*

1. **Base expansion — single-source.** Add `scripts/lib/paths.sh` defining `unleashed_plugin_base()`
   (the one expansion, `${HOME:-}` guard comment included) with an idempotent include guard;
   `marker_base` / `log_base` / `context_base` each become a one-line delegate, locating the sibling
   with the `"$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"` idiom already used at
   `context.sh:210`. **A missing `paths.sh` must fall back to the inline expansion, never abort** —
   `agents/swift-reviewer.md:245-246` sources `context.sh` standalone into a zsh Bash tool, and
   `scripts/test-hooks.sh:39,42` source `marker.sh`/`context.sh` without `hook-io.sh`. Without that
   fallback the dedup converts three independent fail-open paths into one shared point of failure,
   which would be a net regression for a defect that has never fired. **Byte-equality assertions are
   forbidden** (see the root cause).
2. **Round scanner — single-source. Not a choice.** `precompact-snapshot.sh:44-51` replaces its inline
   loop with `context_highest_round` (`context.sh` is already sourced at `:17` — no new dependency).
   This is a two-line diff, strictly smaller than any detector, which is why the round-1 reviewer
   suggestion of "detection is appropriate for the round scanners" is declined.
3. **`mtime` — normalise the shape, do not hoist a shared primitive.** Change `marker.sh:175-179` to
   the same try-BSD-then-GNU form as `context.sh:182-183`, keeping marker's `0` sentinel via the
   existing `${m:-0}`. Do **not** extract a shared helper: `marker.sh` does not source `context.sh`,
   the sentinels differ (`0` vs `""`), and `stop-quality-marker-gate.sh` sources only `hook-io` +
   `marker`. Apply the same change to `scripts/test-hooks.sh:695`. Then a one-line CI grep asserting no
   `uname` + `Darwin` branch survives **anywhere under `scripts/`** (not just `scripts/lib/`, or it is
   inert against the harness copy) becomes a real gate rather than a tautology. State whether
   `sessionstart-restore.sh:41-44`'s third shape is normalised too or deliberately left alone.

**Proof — behavioural, per item. No assertion in this section may be source-line equality.**
*(Round 1's "edit one base expansion without the others → CI fails naming both files" presupposes the
copies survive, so it cannot mutation-prove the single-source branch at all.)*

- **Item 1:** under `env -u HOME -u CLAUDE_PLUGIN_DATA` with `set -euo pipefail`, all three bases return
  `/.claude/unleashed-mail` with **empty stderr**; drop the `${HOME:-}` guard in any one copy and that
  copy emits `HOME: unbound variable` and returns empty. **State plainly that this vector does not break
  today** — it is regression-proofing, not a fix.
- **Item 2:** with `round-3`, `round-09` and `round-999…9` (20 digits) present, the hook currently emits
  the `integer expression expected` stderr line and records `"round":"09"`; after the change stderr is
  empty and it records `9`. **Assert both**, beside the existing round-08/09 and oversized-suffix cases
  at `test-hooks.sh:745-768`.
- **Item 3:** stub `uname() { echo FreeBSD; }` with BSD `stat` on `PATH` — today `marker_mtime` returns
  `0`, which makes `stop-quality-marker-gate.sh:77-81` compute `AGE=999999` and **skip the gate
  entirely**; after the change it returns the real mtime. Also assert the GNU path explicitly: coreutils
  `stat -f %m FILE` exits 1, and it is that exit status the `|| m=""` fallthrough depends on.

**Round-2 correction on the reviewer's own vectors.** Three of the four behavioural vectors round 1's
reviewer proposed are **inert on current code** — unset `HOME` under `set -u` works (all three bases
return the fallback, hook exit 0, stderr empty), a plugin-data path containing a space works, and
`round-09` reproduces but is cosmetic. Only FreeBSD-style `stat` breaks anything, and only on a platform
neither the macOS dev host nor Ubuntu CI hits. Adopting that list verbatim would have produced a suite
that is green before *and* after the fix for the item that matters.

**Note for the reviewer.** Pattern adopted from the same MIT source's `cursor-skill-sync.yml`, which
fails CI when two copies of a file drift. We have no second harness to sync, so only the **guard shape**
transfers — and for two of the three primitives, consolidation turns out to be smaller than detection.

### 4.3 — C: an approval cannot survive the mandated worktree move (Medium)

**Root cause.** Two mandatory `CLAUDE.md` conventions contradict each other. It requires working in a
dedicated `.claude/worktrees/<name>` worktree, **and** requires `implement`'s verify step to pass — but
the verdict artifact records the plan's **absolute** path (`review-verdict.py:474`,
`"planPath": os.path.realpath(plan)`), and verify compares it directly (`:686`).

Hit directly this cycle: gating `COREDEV-2583` in one worktree and implementing in another, with
**byte-identical** plan content and a genuine five-round approval.

**Correct the incident narrative.** A plain worktree move produces `GATE FAILED — no Combined-verdict
artifact for this plan`. The `artifact was written for a different plan` message appears only once the
developer manually copies `.verdicts/` across — which *is* the case actually hit, and is the **only**
case repo-relative fixes.

**Consequences — rewritten, because round 1 sold a fix it does not deliver.** Of the three consequences
round 1 listed, repo-relative fixes exactly **one**:

| consequence | fixed by repo-relative? |
|---|---|
| the mandated worktree move (artifact copied) invalidates a genuine approval | **yes** — verified: ABS `GATE FAILED`, REL `GATE OK — APPROVE` |
| renaming the repo directory invalidates every existing artifact | **yes** — verified |
| CI can never verify an approval; a second developer cannot verify at all | **no — and nothing here can.** See §2's Out |

**§4.3 is not a security change.** Round 1 treated the absolute path as provenance and rated relaxing it
a Medium risk. **Reproduced against HEAD: the artifact is unauthenticated.** A hand-written
`.verdicts/*.verdict.json` carrying literal `"aaaa…"`/`"bbbb…"` transcript digests and `transcriptPath`
values pointing at files that do not exist produces `GATE OK — APPROVE`, exit 0, on a plan no reviewer
has ever read. `verify` checks that transcript metadata is *present*, never that it corresponds to a
real file. (`write` is well-defended — it requires real, non-empty transcripts — but `verify` is the
gate, and none of `write`'s defences are re-checked there.) So `planPath` is an **accident guard, not a
security control**, and the net security delta of this change is **zero**. Recorded on `COREDEV-2497`,
which already owns that defect; real authenticity binding is its work, not this ticket's.

**Fix — two parts, in order.**

**Part 1 (documentation, lands first, zero code).** The convention exists only at `CLAUDE.md:91`:
`grep -rn worktree skills/ AGENT_CONTRACTS.md` returns **zero hits**. Nothing tells the operator the
ordering that avoids the problem entirely.

- `CLAUDE.md` → Planning + Plan Review Gate: "Create the feature worktree **first**, then create the
  plan, snapshot, review, synthesize and implement **all inside that same worktree**. The
  Combined-verdict artifact is per-directory session state and does not follow a later
  `git worktree add`."
- `AGENT_CONTRACTS.md` §2 (Plan → Implement Contract) — the same ordering as a numbered contract clause.
  §2 currently contains zero occurrences of "worktree" or ".verdicts".
- `skills/create-feature-plan/SKILL.md` — a new step 0 before the existing snapshot step: confirm you
  are inside the dedicated worktree before scaffolding.
- `skills/implement/SKILL.md` — extend both the `written for a different plan` bullet and the
  `no artifact` bullet with "…or the gate ran in a **different** checkout/worktree. The artifact is not
  carried by git."
- `skills/review-synthesis/SKILL.md` — note that the artifact is written beside the plan in the
  **current** checkout and does not travel.

Verified expressible today with no code change: `create-feature-plan` makes no path assumptions, and
`implement`'s `_contained` guard anchors to `realpath(".")`, so running the whole sequence inside the
feature worktree already works.

**Part 2 (code, after Part 1 is green).** Store plan identity repo-relative, keeping the SHA-256 digest
binding exactly as-is. Two helper requirements are **load-bearing** and were specified by neither
reviewer:

- `_repo_root(path)` — walk up for an ancestor containing a `.git` entry, and **accept `.git` as a
  FILE, not only a directory**. A git worktree's `.git` *is* a file; a directory-only check resolves a
  nested worktree to the parent checkout.
- `_plan_identity(path)` — `real = realpath(path)`; `root = _repo_root(real)`; if no root, return
  `real`. Else `rel = relpath(real, realpath(root))`; **if `rel` starts with `..`, equals `..`, or is
  absolute, return `real`** — never emit a `../` identity. Otherwise return `rel` with separators
  POSIX-normalised so platforms agree.

Use it at exactly three sites: `:474` (write), `:686` (compare), `:688` (the message). Record which form
was used (e.g. `planPathKind: "repo-relative" | "absolute"`) so verify never silently compares a
relative string against an absolute one. Rewrite `:474`'s comment: `realpath` was chosen to distinguish
two same-basename plans in different directories — **repo-relative still does that** (proved) — and the
absolute form additionally bound the artifact to a disk location, which the mandated workflow breaks by
design.

**Proof — five assertions. Round 1's two are inert and are demoted.** Both round-1 proofs pass with
identity checking **deleted entirely** (same bytes across paths succeeds either way; changed bytes fail
on the digest alone), so neither discriminates.

1. The **existing** `scripts/tests/test_review_verdict.py::test_a_same_basename_plan_in_a_different_dir_cannot_reuse_the_artifact`
   (`:70-96`) must keep failing when identity checking is removed — it already does, and it is the real
   guard. It must pass **unmodified**.
2. Different bytes, same path → still fails on the digest.
3. **New:** a real `git worktree add`, artifact copied across, byte-identical plan → verify **passes**.
   This is the regression the item exists to fix and there is no test for it today.
4. **New:** plan reached via a symlink whose target is outside the repo root → `planPath` recorded
   **absolute**, and no stored identity ever begins with `..`. Assert on the stored string.
5. **New:** plan in a directory with **no `.git` ancestor** → recorded absolute (fallback), and verify
   still round-trips.

**Mutation proof:** revert `_plan_identity` to `os.path.realpath` → assertion 3 must fail; drop the `..`
guard → assertion 4 must fail. Both must be **shown** failing, not assumed.

**One trap that makes the whole suite inert.** The existing fixture uses `tempfile.mkdtemp()`, which is
**not a git repo** — under repo-relative it silently exercises only the absolute fallback. An
implementer who adds the code and sees the existing suite go green will have tested nothing about the
new branch. Assertions 3–5 must therefore be rooted in a real `git init` repo.

**On splitting C out.** Round 1's reviewer asked for it on the grounds that this is a security-relevant
provenance change. That premise is **false** (see above), the change is three call sites plus one
helper, and all 70 shipped `test_review_verdict.py` tests pass against a prototype unmodified. **C stays
in the batch**, as two commits: C1 the documentation ordering (no code, mergeable on its own so the
constraint is documented even if C2 slips), C2 the identity change plus its five assertions.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The load check ships inert (asserts nothing) | **High** | §4.1 names three mutants, each failing a different assertion; the EOF-mutation trap is documented because it already fooled one attempt |
| The load check silently tests the wrong bytes | **High — reproduced** | §4.1(a)'s scratch-marketplace source rewrite, plus the `version` equality assertion in (b) as the backstop |
| The load check is flaky in CI (network install) | Medium | Bounded runtime, pinned CLI. If flaky, quarantine rather than weaken the assertion |
| Item B's `paths.sh` becomes a new shared point of failure | **Medium** | Mandatory inline fallback when `paths.sh` cannot be located — `swift-reviewer` and `test-hooks.sh` both source these libs standalone |
| A byte-equality drift gate is red on an unmodified checkout | **High if adopted** | Explicitly forbidden in §4.2; the three base *lines* are not identical today, only the expression is |
| Item B pre-empts or is reverted by COREDEV-2585 §4.1/§4.11 | Medium | 2585 is paused and lands at 2.7.1; B stays a guard, and 2585's §4.1 round bullet is struck if B fixes it |
| Item B changes shipped hook output without saying so | Medium | Declared in the header; CHANGELOG entry goes under *Changed*, and the `"09"` → `9` transition is an asserted test |
| Relaxing the verdict path weakens provenance | **Low, not Medium** | The artifact is unsigned — a hand-written one already passes `verify` (reproduced). `planPath` is an accident guard; net security delta zero. Real authenticity binding is `COREDEV-2497` |
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

Baselines **as measured at `696a036`**: `test-hooks.sh` **302**, synthesizer **191**, scripts **280**,
counts `21/21/0/1`, hook events **10**. These are **floors, not equalities** — re-derive at
implementation time and record the new numbers; a *lower* count is the failure signal. Always print
`pwd` and `git rev-parse HEAD` beside a measurement.

*(Round 1 said 269 — the true v2.6.0 baseline. `04f906d` added 11 tests for COREDEV-2602 one commit
before these plans were written, and both plans inherited the stale figure. The stale main checkout
reports **227**, so a bare number with no commit anchor is genuinely ambiguous, which is plausibly how
269 survived review.)*

**Mutation proof required for every item**, and it must reject a mutant a real implementer might write,
not only a `git revert` — §3's corollary. Each item names its mutants above.

## 7. Implementation order

1. §4.2 (B) — pure lib/test work, no external dependency. Round scanner first (two lines, and it fixes
   the stderr leak), then the base expansion with its fallback, then the `mtime` shape.
2. §4.1 (A) — the CI job, including all three deliberate-failure mutants.
3. §4.3 (C) — last, in two commits: **C1** the documentation ordering (no code), **C2** the
   repo-relative identity plus its five assertions.
4. Version bump + CHANGELOG — item B's shipped behaviour change under *Changed*.

## 8. Open questions — answered in round 2

1. **Is `claude plugin list` machine-readable on 2.1.220?**
   **Answered — yes.** `--json` is supported and confirmed by both reviewers; `--available` also exists
   and requires `--json`. Assert on parsed JSON (`id`, `enabled`, and `version` against the checkout's
   `plugin.json`), never on the `✔ enabled` glyph.
2. **Should B force deduplication or only detect divergence?**
   **Answered per primitive, because the answer differs.** Single-source the base expansion (with a
   mandatory inline fallback) and the round scanner (a two-line diff into a lib the file already
   sources). Normalise — do not hoist — the `mtime` idiom, because the sentinels differ and `marker.sh`
   does not source `context.sh`. Detection survives only as the one-line CI grep backing item 3.
3. **Is repo-relative plan identity acceptable, or should the constraint just be documented?**
   **Answered — both, doc-first, and C stays in the batch.** The documentation ordering is correct under
   any path scheme and fills a real gap (zero occurrences of "worktree" under `skills/` or in
   `AGENT_CONTRACTS.md`). Repo-relative lands second as the backstop for when the ordering is not
   followed. **Neither enables CI or a second developer** — see §2's Out.

**New for round 2 — the thing reviewers should contest.** §4.3 Part 2 changes a provenance field on the
strength of the finding that the artifact is unsigned anyway. If a reviewer believes the artifact
*should* become authenticated first (`COREDEV-2497`), then C2 should wait behind it and only C1 lands
here. **Is the ordering C1 → C2 → 2497 right, or should it be C1 → 2497 → C2?**

## 9. Notes

- Every claim was verified in-tree this cycle, and every round-1 finding was **re-verified by
  execution** before this revision: the missing load check, the wrong-checkout install (reproduced,
  v2.5.3 over 2.6.1), the three base-path copies, the round-scanner stderr leak, the four `mtime` sites,
  and the verdict-path failure.
- Items A and B adopt patterns from `ayghri/i-have-adhd` (MIT). No code is copied; the designs are
  reimplemented against this repo's conventions — and §4.1 documents specifically where the upstream
  recipe must **not** be copied.
- `COREDEV-2599` (evals harness) is deliberately **not** batched here: it is large, costs money to run,
  and needs its own plan.
- The MCP handshake in §4.1(c) bypasses the CLI's own `${CLAUDE_PLUGIN_ROOT}` expansion (it substitutes
  `installPath` in shell), so it proves the server starts from the installed bytes but not that Claude
  Code's variable expansion resolves. Small residual gap, recorded rather than hidden.
- All round-2 verification ran on macOS against CLI 2.1.220 — the version CI pins (`plugin-ci.yml:89`).
  The clone-from-GitHub behaviour in §4.1 should be re-confirmed once on an Ubuntu runner.

## 10. Round-1 gate outcome and what changed

**gemini `APPROVE` (no factual inaccuracies found) · codex `REQUEST_CHANGES` (4 findings).**

Every finding was re-verified by execution before this plan was touched. All four hold, but **two were
materially incomplete and one reviewer recommendation was refuted**:

| finding | verdict | what actually held |
|---|---|---|
| load check tests the wrong checkout | **confirmed** | …and reproduced: it installed **main v2.5.3** over the branch's 2.6.1 and reported `enabled: true`. Worse, #61's own hooks defect also passes `validate --strict`, so an MCP handshake alone is still inert against it |
| repo-relative does not solve artifact movement | **partial** | (i) and (ii) hold. **(iii) refuted** — the doc-fallback fixes strictly *less* than repo-relative and is equally useless for CI, so it does not dominate. And the "security-relevant" premise is false: the artifact is forgeable |
| §4.2 leaves mutually exclusive options | **partial** | correct, but the counts were wrong (three round scanners, four `mtime` sites), **three of the four proposed vectors are inert today**, and the one real defect — a stderr leak breaking the fail-open invariant — appears in neither review |
| four factual/sequencing corrections | **confirmed** | all four; the 2585 overlap is the *same defect with the same experiment*, and round 1 cited 2585 zero times |

**gemini approved a plan with four real defects in it**, including a stale baseline it re-derived
correctly elsewhere in its own review. Recorded as a calibration data point, not a criticism — its
`--json` confirmation and its `10#$n` round-scanner analysis were both independently correct and useful.

**The direct reviewer conflict on open question 3 was resolved against both reviewers** — adopt both,
doc-first, keep C batched — after reproducing the failure, the fix, and the inertness of both proposed
proofs.
