# Repo Gating Hygiene Plan — trunk in CI, pin drift, and stale install resolution

**Status:** Planning, revision 5
**Created:** 2026-08-28
**Last Updated:** 2026-08-28
**Basis:** `c913303` (origin/main, plugin 2.8.3) · **Tickets:** COREDEV-2780, COREDEV-2798, COREDEV-2801

> **r1** `04048c7`: codex + agy both `REQUEST_CHANGES`. Concordant: §2's fix was wrong for
> `rewrite`-class sites, and the M1→M2 precondition was false.
> **r2** `b2ca1b0`: codex `REQUEST_CHANGES` (7 DESIGN) + agy `REQUEST_CHANGES` (2 DESIGN), concordant
> on the alpha landing precondition and on §6.1 option (b) being unimplementable as written. codex
> read the pinned action's **source at its SHA** and found two self-contradictions in this plan.
> Revision 3 closed all nine.
> **r4** never launched: the capture wrapper rejected a malformed round operand and failed closed
> before either reviewer started, so no transcript exists and no round was consumed. Revision 5 then
> closed §6.1 and §6.3 with maintainer decisions, so round 5 reviews a decision-complete plan.
> **r3** `8d79fa7`: codex `REQUEST_CHANGES` (4 DESIGN) + agy `REQUEST_CHANGES` (4 DESIGN).
> **Concordant, and confirmed independently: revision 3's `workflow_dispatch` fix was a job-level
> `on:`, which GitHub Actions does not have** — the contradiction was relocated, not resolved. codex
> additionally found a confounded negative control (cell 7), that the job never reaches `alpha` at
> all, and a missing outcome in §3b's table. agy additionally found `arguments:` ungoverned.
> **Two of agy's four claims were refuted against the pinned action's source** — see §6.1 and §5 cell
> 1; recorded so a later round does not re-raise them. **kimi is unavailable until 2026-08-31 (weekly
> limit); the mandatory gate is codex + agy, which is unaffected.**

## Overview

Three defects that share one shape: **a static assertion about the tree, or about which bytes are
running, that is either absent, self-invalidating, or authoritative over the truth it should track.**

| ticket | defect | today |
|---|---|---|
| COREDEV-2780 | 20 trunk linters configured, wired into **nothing** | bad lints merge freely |
| COREDEV-2798 | the COREDEV-2619 inventory pins line numbers in files that are *prepended to* | **every release** reds the test |
| COREDEV-2801 | a plugin version no source serves is still reachable | fixes silently do not reach sessions |

They are planned together because they are one review's worth of argument. **They do not sequence**
— revision 1 claimed COREDEV-2798 gated COREDEV-2780; both arms showed that false, since `trunk check`
never executes `test_transcript_path_inventory.py`, which already runs in the existing `validate` job
(`plugin-ci.yml:86`, `:588` on Darwin). M1 and M2 are independent.

## §1 — COREDEV-2780: trunk gates the DIFF, never the tree

### The measurement that constrains everything

`trunk check --all` on a clean tree at `c913303`: **240 unformatted files · 562 security issues ·
9027 lint issues** across 226 files.

So **`--all` can never be the required gate.** A gate red by default trains people to ignore it —
this repo owns that specimen: COREDEV-2641's plan-citation linter fails on 26 of 27 plans, was never
adopted locally as a result, and that is how a shifted line pin reached CI red on PR #67.

### Diff-scoped and REQUIRED, with the losing option's cost stated

Both arms agreed. Rejected option (all-scoped advisory) costs alert fatigue — new regressions
invisible inside a 9027-issue backlog. **Chosen option costs continuous visibility into untouched
debt and blindness to global effects from linter upgrades.** That visibility must live somewhere: a
scheduled `--all` trend report under COREDEV-2787 / COREDEV-2778, never in the required PR context.

### THE SIX DEFECTS INHERITED FROM COREDEV-2771 — PROHIBITED AND TESTED, NOT RESTATED

Revision 2 tabled these; codex r2 correctly observed that **1 and 4 were merely restated**. Each row
now names the prohibition and the cell that enforces it:

| # | defect | prohibition | cell |
|---|---|---|---|
| 1 | `check-mode: popular` | `check-mode` **omitted entirely**; asserted absent from the job block | 9 |
| 2 | `--upstream origin/${{ github.base_ref }}` (empty on push) | **no custom `--upstream`** | 1, 9 |
| 3 | `--upstream origin/${{ github.ref_name }}` ⇒ **empty diff, passes having checked nothing** | as 2; plus a non-empty-diff assertion per event | 1 |
| 4 | `post-annotations: true` | **absent or false**; asserted in the job block | 9 |
| 5 | a custom `--upstream` at all (action injects one) | as 2 | 9 |
| 6 | `contents: read` alone vs `--github-annotate` | resolved by §6.1's chosen mechanism, asserted | 10 |

**Defect 3 remains the one this plan is most at risk of repeating.** A gate that checks an empty diff
and reports green is indistinguishable from a working gate by any cell that only asserts "the job
passed" — which is why cell 1 asserts the *resolved diff*, not the job outcome.

### `workflow_dispatch` — the seventh hazard, found in the action's source (codex, r2)

The pinned action **autodetects `workflow_dispatch` as `check-mode=all`**
(`determine_check_mode.sh` @ `e1234e67`). That would re-litigate all 9027 findings and directly
contradict this section's central claim.

**Resolution: a job-level `if:` guard.** Revision 3 wrote this as a job-level `on:` — **a key
GitHub Actions does not support at job scope.** `on:` is a workflow key; `plugin-ci.yml:10` declares
it with `workflow_dispatch:` under it at `:20`, so *every* job in that file is reachable on dispatch.
Revision 3 therefore relocated the contradiction into a construct that cannot exist. Both arms caught
it (codex + agy, r3), and it was confirmed against the workflow directly.

The mechanism:

```yaml
jobs:
  trunk-check:
    if: github.event_name != 'workflow_dispatch'
```

Cell 11 asserts **that exact guard expression on `jobs.trunk-check`** — not the prose property "not
reachable on dispatch", which no parser can check and which revision 3's wording would have satisfied
with an unsupported key. If a manual full-tree run is ever wanted it belongs in the scheduled
COREDEV-2787 report, under its own non-required context.

### The job contract

* **Action pinned by full SHA** per `AGENT_CONTRACTS.md` §6 — `trunk-io/trunk-action` v2.0.0 =
  `e1234e67a86010d61ddac8d8ebf4b783e2ffd2fa`. (v1.3.0 and v1.3.1 resolve to the *same* SHA — tags in
  this action have moved, which is exactly why §6 requires SHAs. Dependabot updates the pin.)
* **SHA-pinned `actions/checkout`** in the job. The action does not check out the caller's repo
  itself; its internal checkout is conditional on a separate target-checkout mode (codex, r2).
* **Omitted:** `check-mode`, `post-annotations`, any custom `--upstream`, any `--fix`.
* **`arguments:` is GOVERNED, not merely unmentioned (agy, r3).** Verified at the pinned SHA:
  `INPUT_ARGUMENTS` is word-split into the `trunk check` command line in **both** `pull_request.sh`
  and `push.sh`, so §6.4's exclusion necessarily travels through this input — and revision 3's
  contract never named it, leaving cell 9 unable to distinguish the authorised filter from an
  arbitrary one. **The contract: `arguments:` is either absent, or *exactly* §6.4's declared
  exclusion filter** — asserted by cell 9 as a literal whole-string match, never a substring or a
  "contains `--filter`" test, both of which an added argument would still satisfy.
* **Stable job + context name** — `trunk-check`, so the ruleset context is nameable and cannot drift.
  Runner `ubuntu-latest`, explicit `timeout-minutes`.
* **No autofix.** `trunk fmt` / `trunk-fmt-pre-commit` stays disabled, per COREDEV-2771.
* **Linter-set contract — NO *UNDECLARED* FILTER.** See §1's exclusion rule immediately below.

### The linter-set rule, restated to remove revision 2's contradiction (codex, r2)

Revision 2 said "no `--filter`" in §1 while §6.4 recommended splitting `markdown-link-check` out —
**and that linter is in the enabled set, so the two could not both hold.** codex caught it; revision 2
recommended two mutually exclusive things.

The rule that survives: **no *undeclared* filter.** A silent reduction to one linter is the hazard;
a declared, justified, cell-enforced exclusion is not the same thing. Concretely, cell 4 asserts the
job runs **exactly** the configured set minus an **explicitly enumerated** exclusion list, and fails
if any linter outside that list is missing **or** if the exclusion list grows without a plan change.

## §2 — COREDEV-2798: identity is CLASS-SPECIFIC

Revision 1 proposed "exactly one line hashes to `sourceSha256`" for prepend-only files. Both arms
rejected it: that fails against a currently-correct tree.

| class | live identity | `sourceSha256` must |
|---|---|---|
| `quote-keep` (`CHANGELOG.md:2140`) | the source line itself | **match exactly once** |
| `rewrite` (`README.md:187` → dest 292) | `destination.payloads` | **match NOTHING** — the legacy source was deliberately deleted |

`test_transcript_path_inventory.py:349` already enforces source-absence for rewrites.

**The fix, per class:**

* **quote-keep** — assert **exactly one** line matching `sourceSha256`; `line` becomes a re-derived hint.
* **rewrite** — retain the source-absent assertion **unchanged**, and assert **exactly one** matching
  destination payload block; `destination.line` becomes a re-derived hint.
* **anchors** (agy, r1) — `precedingAnchorLine` / `followingAnchorLine` shift identically on prepend
  and are demoted to hints too.
* Scope the demotion to **prepend-only files** (`CHANGELOG.md`, `README.md`). Every other site keeps
  its line assertion.

**Two existing line dependencies must change with it** (codex, r2): the observed-site set comparison
at `test_transcript_path_inventory.py:342` and the fixed-line hash check at `:355`.

**Exactly-one, not at-least-one.** Cells 6–7 in revision 2 passed against three wrong
implementations; §5 cells 6–7 now carry the negative controls that kill them.

## §3 — COREDEV-2801: a diagnostic and a detector, not a remedy

**Cause not identified. Four hypotheses tested and eliminated** (stale scopes; stale fork; a
release/tag pin; VS Code caching) — on the ticket, so they are not re-tried. Established: `2.7.0`
exists in exactly one file; `main` has not served it since `13d5c2b` (Aug 7); that file **is**
rewritten by updates and the stale entries survive the rewrite; four live sessions were bound to it.

### §3a — the experiment (blocks any remedy)

`claude plugin update` at **user scope**, outside any project; re-read the record.

**Recovery is not root cause.** A successful advance proves only that a user-scope update repairs
*current* state and that nothing reverted it *immediately*. It does not explain how stale entries
survived earlier rewrites. Outcomes are recorded as **containment**; root cause stays open.

### §3b — the detector, with its caller NAMED (codex, r2)

Revision 2 left the caller "to be settled", so cell 8 had no entry point and could have passed
against dead code. **The caller is `.githooks/pre-commit`.**

**Why that one, and why it survives the bootstrap problem.** A session bound to 2.7.0 cannot execute
a detector shipped only in 2.8.4+. The hook is not shipped by the plugin — it lives in the
**checkout** and runs from it, so it is current regardless of which install a session loaded. It
compares `~/.claude/plugins/installed_plugins.json` against the repo's
`.claude-plugin/plugin.json`, needing no session environment and no plugin code.

**Reachability is a PRECONDITION, not a property (codex, r3).** The hook runs only where
`git config core.hooksPath .githooks` has been set — a **manual, per-clone** step documented at
`CLAUDE.md:78`, not a repo-wide setting; it is set in the working clone today and unset in any fresh
one. Revision 3 also called these "two files it can always read", which **its own unreadable-state
row contradicts**; that claim is withdrawn.

**Decision table, so §3a's outcome selects the posture rather than reopening the design:**

| §3a outcome | detector posture |
|---|---|
| both entries advance and stay advanced | **warn** — drift is operator-recoverable; the hook surfaces it |
| a 2.7.0 entry reappears | **warn + record**; the reappearance is the root-cause signal, and COREDEV-2801 stays open with the detector as the instrument |
| **user advances, project stays stale** | **warn** — and this is the *expected* shape: §3a updates **user scope only**, while the record holds separate user and project entries both at `2.7.0`. Revision 3's table omitted the outcome its own experiment was most likely to produce (codex, r3) |
| **nothing advances / the update fails** | **warn + record**, and §3a's containment claim is **not** established; COREDEV-2801 keeps the remedy blocked |
| the record's shape is not as expected (schema drift, entries absent) | **silent no-op**, and record the observed shape — an unrecognised record is not evidence of drift |
| entries cannot be read at all | **silent no-op** — never fail a commit on absent plugin state |

It **never blocks a commit.** A version-drift detector that fails `git commit` would be a worse
defect than the one it reports.

**§6.3 is DECIDED — wire the hook — so this caller stands and M6 is unconditional.** The reasoning
below is retained because it is *why* no alternative caller exists, not a live branch:

* **§6.3 = wire the hook** *(the decision)* → §3b is built as described, caller
  `.githooks/pre-commit`.
* **§6.3 = CI-only** *(rejected)* → §3b would have been **dropped** entirely, COREDEV-2801 keeping
  the §3a diagnostic alone. There is no third caller. The detector must run **from the checkout** (the bootstrap
  constraint) and must read **local machine state** (`~/.claude/plugins/installed_plugins.json`).
  CI satisfies the first and cannot satisfy the second — a runner has no developer install record. A
  plugin-shipped hook satisfies the second and cannot satisfy the first — a session pinned to 2.7.0
  would run 2.7.0's copy, which is the very defect. **Git hooks are the only mechanism that is both**,
  so "a different caller" does not exist, and M6 is conditional rather than merely unscheduled.

## §4 — Milestones

- [ ] **M0** — *(decided, §6.0; refined in r3)* bring `alpha` up to date with `main` (611 commits,
      0 ahead). **This alone lands the trunk configuration on `alpha`**, because `.trunk/trunk.yaml`
      is already present on `origin/main` — verified. COREDEV-2771's separate-PR requirement is still
      met: the config arrives on the sync PR, which is not the PR that adds the job. Revision 3's
      second step was therefore redundant work on an already-satisfied precondition.
- [ ] **M1** (independent of M0/M2) — COREDEV-2798 class-specific content-addressing, anchors
      demoted, `:342`/`:355` updated, cells 6–7 with negative controls.
- [ ] **M2** (**after M0**) — add the `trunk-check` job, diff-scoped, `continue-on-error: true`,
      with the §1 `if:` dispatch guard.
- [ ] **M2a** (**after M2 — the step revision 3 was missing entirely, codex r3**) — land the job on
      `alpha` too. GitHub runs the workflow **version present at the event's ref**, so a job merged
      only to `main` never executes for an `alpha` PR: `alpha` would carry the config but emit no
      `trunk-check` check run. Requiring the context at M4 would then make it **unsatisfiable on
      `alpha`** — COREDEV-2767's exact failure, aimed at the other protected base.
- [ ] **M3** — remove `continue-on-error`, then observe **one genuinely strict green run and one
      deliberately red run**. *Revision 1 would have promoted a context observed only while failures
      were suppressed — one that had never been able to fail.*
- [ ] **M4** — add the required context to ruleset `Control`, **only after M3's red run**, and only
      with explicit maintainer instruction (§6.2). **State the bases at the time of the change**:
      `Control` targets `main` and `alpha`, and the context must be satisfiable on both — which M0
      **and M2a together** make true, not M0 alone. **Evidence required on BOTH bases before M4**:
      one strict green and one deliberately red `trunk-check` run observed on a `main` PR *and* on an
      `alpha` PR (cell 12). An unobserved base is an unsatisfiable-context risk, not an assumption.
- [ ] **M5** — run §3a; record the outcome on COREDEV-2801 as containment.
- [ ] **M5a** (**§6.3 decided**) — wire the diff-scoped trunk check into `.githooks/pre-commit`,
      blocking on newly introduced findings, never `--all`, with an explicit timeout; update
      `CLAUDE.md`'s gate list. Independent of M2/M4 — it gates commits, not merges.
- [ ] **M6** — implement §3b with caller `.githooks/pre-commit` (§6.3 decided: wire it), posture per
      §3a's decision table. Unconditional as of revision 5.

M3 and M4 are gated on evidence, not schedule.

## §5 — Testing

Cells 1–3 exist because of inherited defect 3 — a gate over an empty diff passes having checked nothing.

1. **The diff is non-empty and correct per event — and the job, not just the test, detects it.**
   Assert the *resolved* upstream/diff on `pull_request`, `push` to `main`, and `push` to `alpha`.
   **The mechanism was missing in revision 3 (agy, r3, in part):** `trunk check` exits **0** when the
   resolved diff matches no files, so the action alone reports green having checked nothing — which
   *is* inherited defect 3. The job therefore carries an explicit step that resolves the diff and
   **fails when it is empty**, before the action runs. (agy paired this with a claimed "§1 prohibition
   on custom step wrappers" — **no such prohibition exists in this document**; §1 constrains the
   action's *inputs*, not the job's steps. The mechanism gap was real, the contradiction was not.)
2. **The gate bites.** A deliberately bad changed file fails the job.
3. **The gate does not over-reach.** (a) A PR touching one clean file passes with the 9027-issue
   backlog present. (b) A PR touching a **historically dirty** file passes for its pre-existing
   findings while still failing for newly introduced ones.
4. **The linter set is the configured set minus the declared exclusions** — and no more. Per-linter
   positive controls; fails if any non-excluded linter is missing, or if the exclusion list grows.
5. **No autofix.** The job never mutates the tree.
6. **quote-keep — relocation passes, and three wrong implementations fail.** Prepend to
   `CHANGELOG.md` → green with no edit. Then: content change → red; **duplicate source line → red**
   (kills "at least one"); and the `:342`/`:355` dependencies still hold.
7. **rewrite — relocation passes, and three wrong implementations fail.** Prepend to `README.md` →
   green. Then: payload change → red; **duplicate destination block → red**; and the
   restored-legacy-source control, **which revision 3 got wrong**.

   **The control was CONFOUNDED (codex, r3).** Restoring the legacy README source reintroduces both
   fixed transcript literals, so the *independent* observed-literal check at
   `test_transcript_path_inventory.py:326` fails **first** — codex reproduced both diagnostics
   (`README.md:591: output literal survives outside the quote-keep set` **and** `README.md:187:
   legacy source payload survives`). A test that reds for a different reason than the one under test
   proves reachability, not discrimination: deleting the source-absence assertion at `:362` would
   still leave the case red, and the control would still "pass".

   **The control as it must be written:** assert the **specific diagnostic** `legacy source payload
   survives` is emitted — not merely that the case is red — **and** mutation-test the deletion of
   that branch directly, confirming the case goes green without it.
8. **The detector fires from `.githooks/pre-commit`**, not from a direct unit call — and **never
   blocks the commit**, asserted by a mismatch case whose commit still succeeds.
9. **The job block prohibits what COREDEV-2771 measured.** `check-mode` absent, `post-annotations`
   absent-or-false, no custom `--upstream`, no `--fix`, `actions/checkout` SHA-pinned — and
   **`arguments:` absent or matching §6.4's declared filter as a whole string** (§1), so an appended
   argument cannot pass a substring test.
10. **The chosen §6.1 annotation mechanism is present and works** on a non-fork PR — no 403. Under
    option (b) that is checkable rather than merely observed: assert the run takes the
    `--github-annotate-file` branch (**not** `--github-annotate`) and that the `trunk-annotations`
    artifact is produced, uploaded by the action's own SHA-pinned `actions/upload-artifact` step
    under `if: always() && env.TRUNK_UPLOAD_ANNOTATIONS == 'true'`. **No added token scope**: the
    upload uses the Actions runtime, not `GITHUB_TOKEN` permissions, so `contents: read` stands.
11. **The job carries the literal dispatch guard.** Assert `jobs.trunk-check.if` is exactly
    `github.event_name != 'workflow_dispatch'`. **Asserting the prose property instead — "the job is
    unreachable on dispatch" — is what let revision 3 satisfy this cell with a job-level `on:` that
    GitHub ignores.** The cell must fail if the key is absent, renamed, or expressed as `on:`.
12. **Both protected bases emit the context** (M4's precondition, codex r3). Observe a real
    `trunk-check` check run on a `main` PR **and** on an `alpha` PR — green and red on each — before
    the context is required. Fails if either base produces no check run.
13. **The pre-commit hook runs the check diff-scoped, blocks, and is bounded** (§6.3). Assert: a
    staged file with a new finding **fails the commit**; a staged clean file commits with the 9027
    backlog present (so the hook is not `--all`); and the check runs under its declared timeout.
    Fails if the hook is advisory, if it scopes to the whole tree, or if it is unbounded.

## §6 — STRUCTURAL DECISIONS

### 6.0 — DECIDED 2026-08-28 (maintainer): the alpha base

`alpha` is a protected base under ruleset `Control`, has **no** `.trunk/trunk.yaml`, and is **611
commits behind `main`, 0 ahead**. Decision, in order: **(1)** bring `alpha` up to date with `main`;
**(2)** land the trunk configuration there as its own PR; **(3)** gate `main`.

**Refined in r3, against what the repo actually contains — the decision stands, two of its steps
change.** Step (2) is **subsumed by step (1)**: `.trunk/trunk.yaml` is already on `origin/main`, so
syncing `alpha` to `main` lands the configuration there by construction. And a step was **missing**:
the `trunk-check` **job** must also reach `alpha` (M2a), because GitHub runs the workflow version at
the event's ref — syncing `alpha` *before* M2 brings the config but not the job.

So the sequence is: **(1)** sync `alpha` to `main` (lands the config) → **(2)** add the job on `main`
(M2) → **(3)** land the job on `alpha` (M2a) → **(4)** gate `main`, with evidence from both bases.

This dissolves the §6.2 hazard rather than deferring it: `Control` targets both bases, so a required
context would otherwise have demanded something `alpha` could not satisfy — the COREDEV-2767 failure
aimed at a different branch. **M0 alone does not dissolve it; M0 + M2a do.**

### 6.1 — annotations vs token scope — **DECIDED 2026-08-28 (maintainer): option (b)**

Keeping `contents: read` does **not** by itself stop the action passing `--github-annotate` on a
non-fork PR; it would attempt to annotate and fail 403. That is what makes the mechanism, not the
permission alone, the deciding factor.

> **agy r3 claimed `save-annotations` does not exist in `trunk-io/trunk-action` v2.0.0 and that
> option (b) is unimplementable. REFUTED at the pinned SHA.** `action.yaml:81` defines
> `save-annotations` — *"Save annotations as an artifact instead of posting them from this action."*
> `pull_request.sh` branches on it: true ⇒ `--github-annotate-file=${TRUNK_TMPDIR}/annotations.bin`
> plus `TRUNK_UPLOAD_ANNOTATIONS=true`; false ⇒ `--github-annotate`. So the input **replaces** the
> API-posting flag rather than accompanying it, and there is no 403 to hit. Stronger still:
> `push.sh` passes **no annotation argument at all**, so the push leg never annotates under any
> setting. codex r2 was right and agy r3 was wrong; recorded here so a later round does not re-raise
> it. (Two of agy's four r3 claims were fabrications about checkable artifacts — see also §5 cell 1.)

* **(a) `checks: write`, scoped to the `trunk-check` job only** — inline annotations on the diff.
  Widens that job's token scope.
* **(b) `contents: read` + `save-annotations: true`** — the action **writes and uploads an annotation
  artifact instead of posting it** (codex, r2, from `pull_request.sh` @ the pinned SHA; re-verified
  in r3). No scope change — the upload runs on the Actions runtime, not on `GITHUB_TOKEN`
  permissions. **Named cost:** a `trunk-annotations` artifact per run, with its storage and retention
  against the repo's quota, and findings reachable only by downloading it or reading the job log.
  **Note the asymmetry:** this affects the `pull_request` leg only — `push.sh` passes no annotation
  argument at all, so pushes to `main`/`alpha` never annotate under either option.

**DECIDED: (b)** — `contents: read` + `save-annotations: true`. The gate's value is blocking, not
annotating, and the job's token scope stays minimal. **The accepted cost, restated so it is not
rediscovered as a defect later:** findings are reachable only from the job log or the
`trunk-annotations` artifact, never inline on the diff. If that proves to make the gate unusable in
practice, the remedy is a scope change to option (a) — a one-line permissions edit plus cell 10 —
not a redesign.

### 6.2 — Adding a required context to ruleset `Control`

`Control` (16082567) protects `main` and `alpha` with **`bypass_actors: []` — no escape hatch.** A
failing required check blocks every merge with no override, and adding a context before the workflow
emits check runs previously made `main` unmergeable (COREDEV-2767). M4 is gated on M3's evidence
**and** on maintainer instruction.

### 6.3 — `.githooks/pre-commit` — **DECIDED 2026-08-28 (maintainer): WIRE IT**

Local diff-scoped check measured at **7s for one changed file**; every current hook validator is
sub-second. Documenting it in `CLAUDE.md` without wiring the hook would describe something that does
not run.

**DECIDED: wire the diff-scoped trunk check into `.githooks/pre-commit`, blocking on failure.** Two
consequences follow, and both are now settled rather than open:

1. **Lint is a blocker locally as well as in CI**, consistent with this repo's strict posture — the
   hook fails the commit on a *newly introduced* finding in the staged diff. It must **not** run
   `--all`: the 9027-issue backlog would block every commit, which is the same trap §1 rejects for CI.
   Bounded by an explicit timeout, asserted by cell 13.
2. **§3b's detector has its caller**, so **M6 is unconditional** and COREDEV-2801 keeps its detector.
   The conditional branch in §3b is retained as the *rationale* for why no other caller exists, not
   as a live alternative.

**Accepted cost:** ~7s added to each commit, against sub-second today.

### 6.4 — `markdown-link-check` — RESOLVED as a declared exclusion

Revision 2's recommendation contradicted §1. Under §1's corrected rule (no *undeclared* filter), the
resolution is a **declared, enumerated, cell-enforced exclusion**: `markdown-link-check` is excluded
from the required job and runs in the scheduled advisory job (COREDEV-2778).

**Losing cost, previously unstated (codex, r2): no merge-time detection of newly broken links.** A
PR may introduce a dead link and merge; the scheduled job reports it afterwards. Accepted, because a
required gate that fails on someone else's outage is worse — but it is a real loss, not a free win.

## §7 — Files Changed

* `.github/workflows/plugin-ci.yml` — `trunk-check` job: SHA-pinned action + checkout, no
  `check-mode`/`post-annotations`/custom upstream, `arguments:` absent or exactly §6.4's filter, an
  explicit empty-diff guard step (cell 1), and `if: github.event_name != 'workflow_dispatch'`
  (**a job-level `if:`, never a job-level `on:` — GitHub has no such key**)
* `scripts/tests/test_transcript_path_inventory.py` — class-specific content-addressing; `:342` and
  `:355` updated
* `docs/planning/COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json` — `line`, `destination.line` and both
  anchor lines demoted to hints for prepend-only sites
* `CLAUDE.md` — gate-list update
* `.githooks/pre-commit` — the diff-scoped trunk check, blocking, bounded by an explicit timeout
  (§6.3 decided: wire it), **and** the §3b detector call
* the §3b detector script

## §8 — Notes

**Revision 1's largest defect was not technical.** It was written without reading COREDEV-2771's
planning document, which contains a section addressed to this ticket handing over six reviewed
defects. Both reviewers re-derived that work. Grep `docs/planning/` for the predecessor first.

**Revision 3's largest defect was fixing a contradiction into an impossibility.** Told that
`workflow_dispatch` forces `check-mode=all`, revision 3 wrote a job-level `on:` — a key that does not
exist at job scope, so the job stayed reachable on dispatch and the cell that was supposed to catch
that asserted a prose property no parser could evaluate. **A fix expressed in a construct the platform
does not have is not a fix, and a cell phrased as prose cannot tell the difference.** Both arms caught
it; the guard is now a literal `if:` expression and cell 11 asserts that literal.

**Revision 3's second defect was a negative control that reds for the wrong reason.** Cell 7's
restored-legacy-source case trips an independent check before reaching the assertion under test —
reachability standing in for discrimination, the same class this campaign has been chasing, in a cell
written to catch it. The remedy is to require the *specific diagnostic* and to mutation-test the
branch deletion.

**Two of agy's four r3 findings were fabrications about checkable artifacts** — a
`save-annotations` input that demonstrably exists at the pinned SHA, and a "prohibition on custom step
wrappers" that appears nowhere in this document. Both were settled by reading the action's source and
grepping this plan. **Weight a reviewer's claim by whether it is checkable, and check it** — the same
arm was simultaneously right about `arguments:` being ungoverned.

**Revision 2's largest defect was self-contradiction.** Two of codex's seven findings were this plan
disagreeing with itself — `workflow_dispatch` forcing the `--all` mode §1 forbids, and §6.4
recommending a split §1's no-filter rule prohibited. Both were found by reading the pinned action's
source and this document's own sections against each other.

**Review arms run SERIALLY** (COREDEV-2772). **kimi is out until 2026-08-31**; the mandatory gate is
codex + agy and is unaffected — and per COREDEV-2777 kimi could not enter the verdict artifact anyway.

**A review prompt must not name a second `*_PLAN.md`** — `bind-prompt.py` extracts every such token
and refuses on disagreement. Refer to a predecessor by ticket plus filename *prefix*. This cost a
full round at r2.
