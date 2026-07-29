# CI & Workflow Hardening Plan

**Status:** Planning — round 5, awaiting re-gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29 (round 5)
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
> field changes from the JSON string `"09"` to the JSON string `"9"` — a **shipped behaviour change**,
> which belongs in the CHANGELOG under *Changed*, not *Fixed*, and must be mutation-proved as such.
> *(Rounds 1–3 wrote this as `"09"` → numeric `9`. Wrong: `precompact-snapshot.sh:67` serialises with
> `printf '…"round":"%s"…'`, so the field is **always** a JSON string regardless of the scanner.
> Reusing `context_highest_round` normalises the VALUE, not the TYPE. Confirmed by execution. If a
> numeric `round` is actually wanted, that is a separate serialisation change with its own
> compatibility tests against `sessionstart-restore.sh`'s reader — this plan does not propose it.)*
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
of their `plugin-load-check.yml` **as of commit-pinned `abdd61f`** — see the note in §9) then
`claude plugin install` — against **our** manifest **git-cloned
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

**(b) Assert installed-BYTE identity, not version equality.** **Open question 1 is answered:
`claude plugin list --json` IS supported on the pinned 2.1.220** (both reviewers confirmed; fields
`id`, `version`, `scope`, `enabled`, `installPath`, `installedAt`, `lastUpdated`, `mcpServers`).
Require exactly one entry matching `unleashed-mail@<scratch-marketplace-name>` with `enabled == true`
**and its `errors` field absent or empty.** The key is not present on a healthy local install, but a
reviewer observed an entry carrying `enabled: true` **together with a non-empty `errors` array** during
a read-only cache refresh — so the shape exists, and without the check the machine-readable gate can
approve an entry the CLI is simultaneously reporting as broken.
Do **not** grep for `✔ enabled`: the glyph does exist on 2.1.220, so a naïve port passes today and
gives false confidence, which is exactly the brittleness this plan warned about.

**The identity assertion must be byte-based.** Version equality is **not** a sufficient backstop:
`main` and the branch share a version for every change that does not bump it, which is most of them, so
a `source: github` regression would install remote bytes and still pass. Round 2's version check caught
only today's accidental 2.5.3/2.6.1 skew.

Assert instead that the **installed tree derives from the scratch checkout's bytes**, via a
**per-run sentinel**. One mechanism, mandated — not a choice:

> Before `marketplace add`, append `# ci-load-sentinel: $GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT` as a
> trailing comment line to `scripts/precompact-snapshot.sh` **in the scratch copy**. After install,
> assert that exact string is present in `<installPath>/scripts/precompact-snapshot.sh`.

Why this one, stated so it is not re-litigated:

- **A remote clone cannot satisfy it.** The token is unique per run and exists only in the scratch
  copy, so a `source: github` regression fails on content, not on a version that may coincide.
- **The carrier is provably shipped** — `hooks/hooks.json:101` invokes it from `${CLAUDE_PLUGIN_ROOT}`,
  so if it is missing from the install the plugin is broken anyway. A shell `#` comment cannot affect
  parsing, validation or behaviour.
- **The rejected alternative, and why.** A digest comparison (`git ls-files -s` over the scratch source
  versus a walk of `installPath`) is stateless and appealing, but it must first establish which file
  set the installer actually copies and how it normalises modes and line endings. Every one of those is
  a source of false failures in a gate whose whole purpose is to be trustworthy when it goes red. The
  sentinel needs none of that. *(Round 3 offered both and left the choice open; a reviewer correctly
  called that a re-introduction of the "X or Y" defect this plan spent two rounds removing. A plan
  resolves design ambiguity — it does not hand the implementer a multiple-choice question.)*

Keep the version equality check as well — it is nearly free — but label it a smoke check, not the
backstop.

**(c) `enabled` is registry state — necessary, not sufficient.** Proven twice over: with `.mcp.json`
repointed at a nonexistent file the install still exits 0 and reports `enabled: true` (and the reported
`mcpServers` still contains a literal **unexpanded** `${CLAUDE_PLUGIN_ROOT}` — it is an echo of the
manifest, not runtime state); and **issue #61's own duplicate-hooks defect installs, reports
`enabled: true`, and passes `claude plugin validate --strict`**, because that error surfaces on
**reload**, not install. So the step must additionally assert:

- **MCP actually starts — launched from the installed `.mcp.json`, not from a known path.** Read
  `<installPath>/.mcp.json`, substitute `installPath` for `${CLAUDE_PLUGIN_ROOT}` in its **declared**
  command and arguments, and launch exactly that. Then drive `initialize` +
  `notifications/initialized` + `tools/list` and assert the negotiated `protocolVersion`,
  `serverInfo.name == "review-synthesizer"` and `tools == ["synthesize_review"]`. The readiness banner
  is on **stderr**, so stdout stays clean JSON-lines; run under `set -o pipefail`.
  **Why the indirection is mandatory:** if the check hard-codes
  `<installPath>/mcp/review-synthesizer/mcp_server.py`, then repointing `.mcp.json` at a nonexistent
  file still starts the real server and **mutant 2 below goes green** — the assertion would test that a
  file exists, not that the plugin's own declaration resolves. Driving the declaration is the whole
  point.
- **Hooks load** — the CLI exposes no reload/hook-load surface, so use the existing
  `scripts/validate-hooks.py --strict --require-manifest` **plus an explicit assertion that
  `plugin.json` has no `hooks` key**, since `hooks/hooks.json` is auto-loaded and re-declaring it
  silently drops the whole hook set. That is #61's exact defect class, and it is the one the MCP
  handshake alone does **not** catch.
  **Run both against the INSTALLED tree** (`installPath`), not the workspace. A workspace-only
  assertion proves the source is well-formed, which the schema validators already cover; it proves
  nothing about what the loader actually installed, which is the entire subject of §4.1.

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
   reports `enabled: true`. **This mutant only discriminates if the handshake launches the declaration
   rather than a known path** — see (c).
3. `marketplace.json` source left as `github` → **(b) byte-identity assertion** fails. Note the mutant
   must be run **without** relying on the version differing: bump the scratch copy's `plugin.json` to
   match `main` first, so the mutant reproduces the realistic case where the two versions agree. If it
   only fails on the version check, the identity assertion is not doing the work.
4. **Each assertion is removed in turn, one at a time** → the mutant it owns must start passing, and no
   other mutant may change.

   **This requires a mutant PER ASSERTION, and rounds 3–4 did not have one.** §4.1 mandates eight
   independent assertions — unique entry, `enabled == true`, `errors` absent/empty, `version` smoke
   check, the sentinel, `protocolVersion`, `serverInfo.name`, `tools == ["synthesize_review"]`, plus the
   hooks pair — against **four** mutants, so the one-to-one claim was arithmetically impossible.
   Deleting the `errors` assertion, or any single MCP handshake assertion, changed no mutant at all.
   The full mapping, each mutant scoped to exactly one assertion:

   | mutant (applied to the scratch copy) | the ONLY assertion that may fail |
   |---|---|
   | `plugin.json` gains a `hooks` key | no-`hooks`-key |
   | `.mcp.json` repointed at a nonexistent file | MCP launch-from-declaration |
   | `marketplace.json` source left as `github`, **versions made equal** | sentinel |
   | `.mcp.json` `name` changed | `serverInfo.name` |
   | a second tool added to the MCP server | `tools == [...]` |
   | `protocolVersion` echoed as a bogus string | `protocolVersion` |
   | plugin installed twice under two marketplace names | unique-entry |
   | `plugin.json` version desynced from the checkout | `version` smoke check |
   | a stray file dropped in the cache to force a cache-refresh error | `errors` absent/empty |
   | `hooks/hooks.json` given a duplicate event key | `validate-hooks --strict` |

   If a mutant fails more than one assertion the assertions overlap and one is redundant; if it fails
   none, that assertion is decoration. **Author the mutants first and watch each fail**, then write the
   assertion — the reverse order is how round 1 shipped an assertion that passed against the very
   defect it cited.
   *(Round 3 wrote "the check itself is deleted → the job must still fail, because mutants 1–3 target
   its assertions" — which is circular: delete the check and nothing is left to reject anything. A
   reviewer caught it. The durable form is the mapping above, run by a negative-test harness asserting
   the **outer** exit status of the load-check step, so "the step was deleted" is itself a failure
   rather than a vacuous pass.)*

**A load check that cannot fail is worse than none** — this remains the item most at risk of shipping
inert. **Author the mutants first and watch them fail**, then write the assertions; the reverse order
is how round 1's version shipped an assertion that passed against the defect it cited.

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
   inert against the harness copy) becomes a real gate rather than a tautology.
   **`sessionstart-restore.sh:41-44` is deliberately left unchanged** — decided, not deferred. Its
   probe-then-rerun shape is a third idiom, but it is already feature-detecting rather than
   `uname`-branching, so it is not the defect this item fixes, and it is the one caller whose output
   reaches model context — the smallest possible diff there is the right risk posture. Record that
   reasoning in a comment at the site so the next reader does not "finish the job". *(Round 2 left this
   as "normalised too or deliberately left alone", which is exactly the X-or-Y contract defect round 2
   was supposed to eliminate.)*

**Proof — behavioural, per item. No assertion in this section may be source-line equality.**
*(Round 1's "edit one base expansion without the others → CI fails naming both files" presupposes the
copies survive, so it cannot mutation-prove the single-source branch at all.)*

- **Item 1 — two vectors, and the second is the one that matters.**
  (i) *Shared path:* under `env -u HOME -u CLAUDE_PLUGIN_DATA` with `set -euo pipefail`, all three
  bases return `/.claude/unleashed-mail` with **empty stderr**; drop the `${HOME:-}` guard and the
  affected copy emits `HOME: unbound variable`. **State plainly that this vector does not break
  today** — it is regression-proofing, not a fix.
  (ii) *Fallback path — mandatory, and it must run the SAME environment matrix as (i):* **with
  `paths.sh` absent**, source each of `marker.sh`, `log.sh` and `context.sh` **individually** (they are
  sourced standalone in real usage — `agents/swift-reviewer.md:245-246` and
  `scripts/test-hooks.sh:39,42`) and assert each exits 0, leaves stderr empty, and returns the correct
  base **across three environments**:

  | environment | required result |
  |---|---|
  | `env -u HOME -u CLAUDE_PLUGIN_DATA` | `/.claude/unleashed-mail` |
  | `HOME=/probe`, no `CLAUDE_PLUGIN_DATA` | `/probe/.claude/unleashed-mail` |
  | `CLAUDE_PLUGIN_DATA=/custom/d` | `/custom/d` |
  | `HOME=/probe`, `CLAUDE_PLUGIN_DATA=` (set but EMPTY) | `/probe/.claude/unleashed-mail` |

  **The fourth row is not padding — it is the only row that rejects `${CLAUDE_PLUGIN_DATA-…}`**, the
  single-dash form. Executed: that expansion passes rows 1–3 identically to the correct `:-` form and
  fails only here, returning empty. A three-row matrix accepts it, and an empty base silently relocates
  every marker, log and snapshot to a relative path.

  **A single-environment assertion is not enough, and this is not theoretical.** An implementer who
  hard-codes the literal `/.claude/unleashed-mail` as the "fallback" produces a function that is
  **indistinguishable from the correct one** under `env -u HOME` alone — it exits 0, stderr is empty,
  and the string matches. Executed: the hard-coded mutant passes row 1 and fails rows 2 and 3. Round 3
  specified only the unset-`HOME` case and would have accepted the mutant.

  Without vector (ii) at all, the suite exercises the shared helper and never the three inline
  fallbacks — so a fallback written wrong, or omitted entirely, passes. Since the fallback exists
  precisely to stop the dedup from converting three independent fail-open paths into one shared point
  of failure, an untested fallback defeats the reason the fallback was required.
- **Item 2:** with `round-3`, `round-09` and `round-999…9` (20 digits) present, the hook currently emits
  the `integer expression expected` stderr line and records `"round":"09"`; after the change stderr is
  empty and it records `"round":"9"` — **still a JSON string**, normalised in value only. **Assert
  both**, and assert the **type** explicitly (a test that accepts either `"9"` or `9` would not notice
  a serialisation change), beside the existing round-08/09 and oversized-suffix cases at
  `test-hooks.sh:745-768`.
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
4. **New:** a plan **outside every git repository** — reached directly, and again via a symlink from
   inside the repo whose target is outside it — records `planPath` **absolute**, and no stored identity
   ever begins with `..`. Assert on the stored string.
5. **New:** plan in a directory with **no `.git` ancestor** → recorded absolute (fallback), and verify
   still round-trips.

6. **New:** `planPathKind` is **present, correct, and consistent with `planPath`** — `"repo-relative"`
   for the in-repo and worktree cases, `"absolute"` for both fallback cases — and `verify` **rejects**
   an artifact whose `planPathKind` is missing, unknown, or inconsistent with the recorded path.
   *(Rounds 3–4 required the field in §4.3's Fix and asserted it nowhere: an implementation that never
   wrote it, or wrote it wrong, passed the entire five-assertion set. A field nothing checks is a
   comment.)*

**Schema decision — made here, not left to the implementer.** The artifact is `schemaVersion: 2` and
`verify` hard-compares it (`review-verdict.py:521`, `!= SCHEMA_VERSION`), so adding a required field is
a schema change. **Bump to `schemaVersion: 3` and let the existing hard comparison reject version-2
artifacts.** Rationale: the artifact is git-ignored, per-directory session state with no migration path
and a lifetime of one review cycle, so "re-run the gate" is the correct and already-implemented
recovery — the failure message even says so. Do **not** add a compatibility branch that accepts a
version-2 artifact without `planPathKind`; that is the one shape where verify would compare a relative
string against an absolute one and pass or fail by accident.

**Mutation proof:** revert `_plan_identity` to `os.path.realpath` → **assertion 3 must fail**; omit
`planPathKind` from the written artifact → **assertion 6 must fail**; leave `SCHEMA_VERSION` at 2 →
a stale round-2 artifact must be **accepted**, which assertion 6 must catch. Each shown failing, not
assumed.

> *Round-3 correction — round 2 claimed a second mutation that is impossible by construction.* It said
> "drop the `..` guard → assertion 4 must fail". **It cannot.** `_repo_root(real)` returns an *ancestor*
> of `real`, so `relpath(real, root)` can never escape with `..`; and when no root is found,
> `_plan_identity` returns the absolute path **before** the guard is reached. Executed both with and
> without the guard on an in-repo plan and on a symlink pointing outside the repo: **byte-identical
> output in both cases.** The guard is therefore **unproved defence-in-depth** and must be labelled as
> such — keep it (it costs nothing and protects against a future `_repo_root` that returns a
> non-ancestor), but do **not** claim a mutation proof for it. This is the same inert-gate class §3's
> corollary exists to catch, and round 2 wrote one into its own replacement proof.
>
> Assertion 4 is also narrowed for a real reason: a symlink into a **different checkout** resolves
> repo-relative to *that* checkout, which is correct behaviour, not a `..` escape. Only "outside every
> git repository" produces the absolute form the assertion is about.

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
| The load check silently tests the wrong bytes | **High — reproduced** | §4.1(a)'s scratch-marketplace source rewrite, plus the **per-run sentinel** in (b) as the backstop. Version equality is only a smoke check — `main` and the branch share a version for most changes |
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

4. **Round 2's question — should the ordering be C1 → C2 → `COREDEV-2497`, or C1 → 2497 → C2?**
   **Answered — `C1 → C2 → 2497`, and both reviewers agreed independently.** C2 introduces **zero net
   security risk**, because the artifact is already entirely forgeable; blocking a genuine usability
   fix behind authenticity work would be the wrong trade. And 2497 should authenticate the *final*
   identity representation rather than authenticate the absolute-path schema and then have to revise
   it. §7 reflects this ordering.

5. **Round 3's question — does offering two byte-identity mechanisms re-introduce the "X or Y" defect?**
   **Answered — YES, and it is fixed.** Both reviewers said so independently: a plan resolves design
   ambiguity, it does not hand the implementer a multiple-choice question, and the two forms were not
   equivalent (one stateless but dependent on `git ls-files` normalisation, the other stateful).
   §4.1(b) now mandates exactly one — the per-run sentinel — and records why the digest was rejected.

**New for round 4 — nothing is deliberately left open.** Every §8 entry is now a decision. If a
reviewer finds a residual choice anywhere in §4, that is a finding: the round-3 review found two
("X or Y" in §4.2 item 3, and the identity mechanism here) after round 2 claimed none remained.

## 9. Notes

- Every claim was verified in-tree this cycle, and every round-1 finding was **re-verified by
  execution** before this revision: the missing load check, the wrong-checkout install (reproduced,
  v2.5.3 over 2.6.1), the three base-path copies, the round-scanner stderr leak, the four `mtime` sites,
  and the verdict-path failure.
- Upstream citations are pinned to `plugin-load-check.yml` sha256 `abdd61f6652ef882…` (33 lines,
  fetched 2026-07-29): `marketplace add "$GITHUB_WORKSPACE"` is line **27**, `plugin list` line 29.
  Re-fetch and re-pin before implementing rather than trusting the line number — it points into a
  live `main`.
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

## 10. Gate history — what each round changed

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

### Round 2 outcome

**gemini `APPROVE` · codex `REQUEST_CHANGES` (5 findings).** All five re-verified by execution;
**four confirmed, one refuted.**

| # | finding | verdict | round-3 change |
|---|---|---|---|
| 1 | the wrong-checkout proof is **version**-dependent, not byte-dependent | **confirmed** | `main` and the branch share a version for any change that does not bump it, so a `source: github` mutant passes. §4.1(b) now requires installed-byte identity (digest or per-run sentinel); version equality is demoted to a smoke check, and mutant 3 must be run with the versions deliberately equal |
| 2 | the MCP mutant is not bound to `.mcp.json` | **confirmed** | a hard-coded `<installPath>/mcp/.../mcp_server.py` starts the real server even when `.mcp.json` is repointed, so mutant 2 goes green. §4.1(c) now requires parsing the **installed** `.mcp.json` and launching its declaration; hooks assertions also move to the installed tree |
| 3 | §4.3's `..`-guard mutation proof is **impossible** | **confirmed** | `_repo_root` returns an ancestor, so `relpath` can never escape; with no root the function returns absolute before the guard. Executed with and without the guard — byte-identical. The guard is relabelled unproved defence-in-depth, and assertion 4 is narrowed to "outside every git repository" |
| 4 | §4.2 still has one "X or Y" and one unexercised fallback | **confirmed** | `sessionstart-restore.sh` is now **decided** (left unchanged, with the reasoning recorded at the site); item 1 gains a second vector that runs with `paths.sh` **absent**, so the three inline fallbacks are actually tested |
| 5 | the upstream line citation is wrong | **REFUTED** | fetched and checked: `marketplace add "$GITHUB_WORKSPACE"` **is** line 27, `plugin list` is line 29, and line 25 is the `export`. The citation stands unchanged |

**Finding 3 is the one worth dwelling on.** Round 2 replaced two inert proofs and wrote a third inert
proof into the replacement — a mutation that cannot fail under the plan's own helper definition. That
is precisely the failure §3's corollary exists to prevent, committed by the section that added the
corollary. It is the strongest argument in this plan for *executing* every mutation rather than
reasoning about it.

**gemini approved, and was wrong on one point** — it stated §4.2 "contains no X-or-Y ambiguities" when
item 3 still did. Recorded as calibration: its independent audit of `cmd_verify` and its confirmation
of the 20-digit stderr overflow were both correct and useful, but a clean APPROVE from it is not
sufficient evidence that a contract is complete.

**Process defect found during this round, and filed separately as `COREDEV-2607`:** the gemini reviewer
**implemented item B into the working tree instead of reviewing it** — 6 shipped scripts modified, 5
files created, including a stray root `marketplace.json`. It emitted no `VERDICT:` line, so the gate
failed closed correctly, but the side effects persisted and had to be reverted. `--mode plan`,
`--sandbox` and both combined were tested and **none prevents writes**. The round-2 gemini verdict
recorded above is from a clean re-run inside a **disposable detached checkout**, with a before/after
`git status --porcelain` assertion proving the real worktree was untouched.

### Round 3 outcome

**gemini `REQUEST_CHANGES` (2 findings) · codex `REQUEST_CHANGES` (5 findings, one a blocker).**
All re-verified by execution.

**gemini's two findings were both real, and both were answers to questions this plan asked it:**

1. **Offering two byte-identity mechanisms *is* an unresolved contract.** Ruled against the plan's own
   framing — "a plan resolves design ambiguity, it does not offer multiple-choice options". §4.1(b) now
   mandates one (the per-run sentinel) and records why the digest was rejected.
2. **§4.2 item 1's fallback proof accepts a hard-coded fallback.** Verified by construction: an
   implementer who hard-codes the literal `/.claude/unleashed-mail` is **indistinguishable** from the
   correct dynamic fallback under the single `env -u HOME` case round 3 specified. The proof is now a
   three-environment matrix that separates them on rows 2 and 3.

**codex — one blocker and four substantive:**

| # | finding | verdict | round-4 change |
|---|---|---|---|
| 1 | **Blocker — the review target changed during the review** | **confirmed, and it was my doing** | the plan was edited while codex was reading it. *"A mandatory digest-bound review cannot approve a moving target."* Round 4 is gated on **frozen** committed bytes |
| 2 | the sentinel decision was not propagated | **confirmed** | §8, the risk register and the gate history all still offered digest-or-sentinel; now consistent |
| 3 | mutant 4 is circular | **confirmed** | "delete the check → it must still fail, because mutants 1–3 target its assertions" — delete the check and nothing is left to reject anything. Replaced with a one-at-a-time assertion-removal mapping, run by a harness asserting the step's **outer** exit status |
| 4 | the `round` type claim is wrong | **confirmed** | `precompact-snapshot.sh:67` serialises `"round":"%s"`, so the field is **always** a JSON string. The change is `"09"` → `"9"`, a value normalisation, not `"09"` → numeric `9`. The test must assert the type, or a later serialisation change slips through |
| 5 | `plugin list --json` can report `errors` with `enabled: true` | **confirmed by the reviewer's own environment** | not reproducible on this install (`errors` is absent), but the shape exists and the guard is free. `errors` must be absent or empty |

**Finding 1 is the process lesson.** `COREDEV-2607` was filed this session because a *reviewer* mutated
the tree under review; finding 1 is the same defect committed by the *author*. The rule now applies both
ways: **a plan is frozen for the duration of a review round.** No edits between dispatching a review and
recording its verdict.

### Round 4 outcome

**gemini `APPROVE` (no findings) · codex `REQUEST_CHANGES` (4 findings).** Both confirmed the plan was
frozen — codex checked the target's working-tree and committed SHA-256 and found them equal, closing
round 3's blocker. All four re-verified by execution.

| # | finding | verdict | round-5 change |
|---|---|---|---|
| 1 | §4.1's mutation contract is still unsatisfiable | **confirmed by counting** — 8 assertions against 4 mutants, so "one-to-one" was arithmetically impossible, and deleting the `errors` or any MCP assertion changed no mutant | a 10-row mutant↔assertion table, one mutant per assertion |
| 2 | the fallback matrix accepts a plausible wrong expansion | **confirmed by execution** — `${CLAUDE_PLUGIN_DATA-…}` (single `-`) passes all three rows and fails only when the variable is set-but-EMPTY | fourth row added: `CLAUDE_PLUGIN_DATA=` → `/probe/.claude/unleashed-mail` |
| 3 | `planPathKind` is required and asserted nowhere | **confirmed** — the field appears once, in the Fix, and in none of the five assertions | assertion 6 added, plus the schema decision (bump to 3; the existing hard comparison rejects v2) |
| 4 | the upstream line citation has drifted | **REFUTED on the fact, remedy adopted** | re-fetched: `marketplace add` is line **27**, `plugin list` line 29, line 25 is the `export`; file unchanged at 33 lines, sha256 `abdd61f6…`. codex placed them at 25/27 in both rounds 3 and 4, in opposite directions. But a line number into a live `main` **is** fragile, so the citation is now commit-pinned |

**Finding 1 is the pattern worth naming.** Round 3 replaced a circular mutant with a mapping claim, and
the mapping claim was itself unsatisfiable — a *second* inert proof written into the fix for the first
one. Counting the assertions against the mutants would have caught it in ten seconds. The lesson the
plan now carries in §4.1: author the mutants first, watch each one fail, and only then write the
assertion.
