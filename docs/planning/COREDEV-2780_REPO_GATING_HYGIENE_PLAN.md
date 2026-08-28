# Repo Gating Hygiene Plan — trunk in CI, pin drift, and stale install resolution

**Status:** Planning, revision 3
**Created:** 2026-08-28
**Last Updated:** 2026-08-28
**Basis:** `c913303` (origin/main, plugin 2.8.3) · **Tickets:** COREDEV-2780, COREDEV-2798, COREDEV-2801

> **r1** `04048c7`: codex + agy both `REQUEST_CHANGES`. Concordant: §2's fix was wrong for
> `rewrite`-class sites, and the M1→M2 precondition was false.
> **r2** `b2ca1b0`: codex `REQUEST_CHANGES` (7 DESIGN) + agy `REQUEST_CHANGES` (2 DESIGN), concordant
> on the alpha landing precondition and on §6.1 option (b) being unimplementable as written. codex
> read the pinned action's **source at its SHA** and found two self-contradictions in this plan.
> Revision 3 closes all nine. **kimi is unavailable until 2026-08-31 (weekly limit); the mandatory
> gate is codex + agy, which is unaffected.**

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

**Resolution: the `trunk-check` job does not run on `workflow_dispatch`.** Its `on:` is
`pull_request` and `push` to the gated bases only. Asserted by cell 11, which fails if the job is
reachable on dispatch. If a manual full-tree run is ever wanted it belongs in the scheduled
COREDEV-2787 report, under its own non-required context.

### The job contract

* **Action pinned by full SHA** per `AGENT_CONTRACTS.md` §6 — `trunk-io/trunk-action` v2.0.0 =
  `e1234e67a86010d61ddac8d8ebf4b783e2ffd2fa`. (v1.3.0 and v1.3.1 resolve to the *same* SHA — tags in
  this action have moved, which is exactly why §6 requires SHAs. Dependabot updates the pin.)
* **SHA-pinned `actions/checkout`** in the job. The action does not check out the caller's repo
  itself; its internal checkout is conditional on a separate target-checkout mode (codex, r2).
* **Omitted:** `check-mode`, `post-annotations`, any custom `--upstream`, any `--fix`.
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
compares two files it can always read: `~/.claude/plugins/installed_plugins.json` against the repo's
`.claude-plugin/plugin.json`. It needs no session environment and no plugin code.

**Decision table, so §3a's outcome selects the posture rather than reopening the design:**

| §3a outcome | detector posture |
|---|---|
| both entries advance and stay advanced | **warn** — drift is operator-recoverable; the hook surfaces it |
| a 2.7.0 entry reappears | **warn + record**; the reappearance is the root-cause signal, and COREDEV-2801 stays open with the detector as the instrument |
| entries cannot be read at all | **silent no-op** — never fail a commit on absent plugin state |

It **never blocks a commit.** A version-drift detector that fails `git commit` would be a worse
defect than the one it reports.

**Dependency:** this makes §3b contingent on §6.3. If §6.3 is decided "CI-only, do not wire the
hook", §3b needs a different caller and the decision table above is the input to choosing it.

## §4 — Milestones

- [ ] **M0** — *(decided, §6.0)* bring `alpha` up to date with `main` (611 commits), then land the
      trunk configuration on `alpha` **as its own PR**, per COREDEV-2771's separate-PR requirement.
      **M2 is blocked on this**: `.trunk/trunk.yaml` is ABSENT on `origin/alpha`, so the job cannot
      diff there.
- [ ] **M1** (independent of M0/M2) — COREDEV-2798 class-specific content-addressing, anchors
      demoted, `:342`/`:355` updated, cells 6–7 with negative controls.
- [ ] **M2** (**after M0**) — add the `trunk-check` job, diff-scoped, `continue-on-error: true`.
- [ ] **M3** — remove `continue-on-error`, then observe **one genuinely strict green run and one
      deliberately red run**. *Revision 1 would have promoted a context observed only while failures
      were suppressed — one that had never been able to fail.*
- [ ] **M4** — add the required context to ruleset `Control`, **only after M3's red run**, and only
      with explicit maintainer instruction (§6.2). **State the bases at the time of the change**:
      `Control` targets `main` and `alpha`, and the context must be satisfiable on both — which M0
      makes true.
- [ ] **M5** — run §3a; record the outcome on COREDEV-2801 as containment.
- [ ] **M6** — implement §3b with the named caller, posture per §3a's decision table.

M3 and M4 are gated on evidence, not schedule.

## §5 — Testing

Cells 1–3 exist because of inherited defect 3 — a gate over an empty diff passes having checked nothing.

1. **The diff is non-empty and correct per event.** Assert the *resolved* upstream/diff on
   `pull_request`, `push` to `main`, and `push` to `alpha`. An empty diff **fails**.
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
   green. Then: payload change → red; **duplicate destination block → red**; **restored legacy source
   → red** (kills deleting the source-absence assertion, which both current fixtures satisfy
   vacuously).
8. **The detector fires from `.githooks/pre-commit`**, not from a direct unit call — and **never
   blocks the commit**, asserted by a mismatch case whose commit still succeeds.
9. **The job block prohibits what COREDEV-2771 measured.** `check-mode` absent, `post-annotations`
   absent-or-false, no custom `--upstream`, no `--fix`, `actions/checkout` SHA-pinned.
10. **The chosen §6.1 annotation mechanism is present and works** on a non-fork PR — no 403.
11. **The job is unreachable on `workflow_dispatch`**, so it can never run in `check-mode=all`.

## §6 — STRUCTURAL DECISIONS

### 6.0 — DECIDED 2026-08-28 (maintainer): the alpha base

`alpha` is a protected base under ruleset `Control`, has **no** `.trunk/trunk.yaml`, and is **611
commits behind `main`, 0 ahead**. Decision, in order: **(1)** bring `alpha` up to date with `main`;
**(2)** land the trunk configuration there as its own PR; **(3)** gate `main`.

This is M0, and it dissolves the §6.2 hazard rather than deferring it: `Control` targets both bases,
so a required context would otherwise have demanded something `alpha` could not satisfy — the
COREDEV-2767 failure aimed at a different branch.

### 6.1 — annotations vs token scope — OPEN, and revision 2's option (b) was not implementable

Both arms found this. Keeping `contents: read` does **not** by itself stop the action passing
`--github-annotate` on a non-fork PR; it would attempt to annotate and fail 403.

* **(a) `checks: write`, scoped to the `trunk-check` job only** — inline annotations on the diff.
  Widens that job's token scope.
* **(b) `contents: read` + `save-annotations: true`** — the action **writes and uploads an annotation
  artifact instead of posting it** (codex, r2, from `pull_request.sh` @ the pinned SHA). No scope
  change. **Named cost:** an artifact per run, with its storage and retention, and findings reachable
  only by downloading it or reading the job log.

*Recommendation: (b).* The gate's value is blocking, not annotating. **Open for review**: if inline
annotations are what make a lint gate usable in practice, (b) is wrong and I would rather be told.

### 6.2 — Adding a required context to ruleset `Control`

`Control` (16082567) protects `main` and `alpha` with **`bypass_actors: []` — no escape hatch.** A
failing required check blocks every merge with no override, and adding a context before the workflow
emits check runs previously made `main` unmergeable (COREDEV-2767). M4 is gated on M3's evidence
**and** on maintainer instruction.

### 6.3 — `.githooks/pre-commit` — OPEN, and §3b now depends on it

Local diff-scoped check measured at **7s for one changed file**; every current hook validator is
sub-second. Documenting it in `CLAUDE.md` without wiring the hook would describe something that does
not run. **§3b's detector names this hook as its caller**, so "CI-only" also sends §3b back for a
different caller. **Decision needed.**

### 6.4 — `markdown-link-check` — RESOLVED as a declared exclusion

Revision 2's recommendation contradicted §1. Under §1's corrected rule (no *undeclared* filter), the
resolution is a **declared, enumerated, cell-enforced exclusion**: `markdown-link-check` is excluded
from the required job and runs in the scheduled advisory job (COREDEV-2778).

**Losing cost, previously unstated (codex, r2): no merge-time detection of newly broken links.** A
PR may introduce a dead link and merge; the scheduled job reports it afterwards. Accepted, because a
required gate that fails on someone else's outage is worse — but it is a real loss, not a free win.

## §7 — Files Changed

* `.github/workflows/plugin-ci.yml` — `trunk-check` job: SHA-pinned action + checkout, no
  `check-mode`/`post-annotations`/custom upstream, not reachable on `workflow_dispatch`
* `scripts/tests/test_transcript_path_inventory.py` — class-specific content-addressing; `:342` and
  `:355` updated
* `docs/planning/COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json` — `line`, `destination.line` and both
  anchor lines demoted to hints for prepend-only sites
* `CLAUDE.md` — gate-list update
* `.githooks/pre-commit` — the trunk check **if §6.3 says wire it**, and the §3b detector call
* the §3b detector script

## §8 — Notes

**Revision 1's largest defect was not technical.** It was written without reading COREDEV-2771's
planning document, which contains a section addressed to this ticket handing over six reviewed
defects. Both reviewers re-derived that work. Grep `docs/planning/` for the predecessor first.

**Revision 2's largest defect was self-contradiction.** Two of codex's seven findings were this plan
disagreeing with itself — `workflow_dispatch` forcing the `--all` mode §1 forbids, and §6.4
recommending a split §1's no-filter rule prohibited. Both were found by reading the pinned action's
source and this document's own sections against each other.

**Review arms run SERIALLY** (COREDEV-2772). **kimi is out until 2026-08-31**; the mandatory gate is
codex + agy and is unaffected — and per COREDEV-2777 kimi could not enter the verdict artifact anyway.

**A review prompt must not name a second `*_PLAN.md`** — `bind-prompt.py` extracts every such token
and refuses on disagreement. Refer to a predecessor by ticket plus filename *prefix*. This cost a
full round at r2.
