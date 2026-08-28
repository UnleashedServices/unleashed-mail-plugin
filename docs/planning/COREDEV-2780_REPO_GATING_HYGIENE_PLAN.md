# Repo Gating Hygiene Plan — trunk in CI, pin drift, and stale install resolution

**Status:** Planning, revision 2
**Created:** 2026-08-28
**Last Updated:** 2026-08-28
**Basis:** `c913303` (origin/main, plugin 2.8.3) · **Tickets:** COREDEV-2780, COREDEV-2798, COREDEV-2801

> **r1** `04048c7`: codex + agy both `REQUEST_CHANGES`, concordant on two things — §2's fix was
> wrong for `rewrite`-class sites, and the M1→M2 precondition was false. Both verified against the
> tree. Revision 2 also carries the six defects COREDEV-2771's plan explicitly handed to this ticket,
> **which revision 1 did not read**; codex found them by reading that plan. Everything in §1's hazard
> table below already existed, in this repo, addressed to this ticket.

## Overview

Three defects that share one shape: **a static assertion about the tree, or about which bytes are
running, that is either absent, self-invalidating, or authoritative over the truth it should track.**

| ticket | defect | today |
|---|---|---|
| COREDEV-2780 | 20 trunk linters configured, wired into **nothing** | bad lints merge freely |
| COREDEV-2798 | the COREDEV-2619 inventory pins line numbers in files that are *prepended to* | **every release** reds the test |
| COREDEV-2801 | a plugin version no source serves is still reachable | fixes silently do not reach sessions |

**They are planned together because they are one review's worth of argument, NOT because they
sequence.** Revision 1 claimed COREDEV-2798 was a precondition for COREDEV-2780. **That was false and
both arms caught it:** `trunk check` is a static linter and never executes
`test_transcript_path_inventory.py`, which already runs in the existing `validate` job
(`plugin-ci.yml:86`, and `:588` on Darwin). M1 and M2 are independent and may proceed in parallel.

## §1 — COREDEV-2780: trunk gates the DIFF, never the tree

### The measurement that constrains everything

`trunk check --all` on a clean tree at `c913303`:

    Checked 226 files
    240 unformatted files · 562 security issues · 9027 lint issues (3968 auto-fixable)

So **`--all` can never be the gate.** A gate that is red by default trains people to ignore it — this
repo already owns that specimen: COREDEV-2641's plan-citation linter fails on 26 of 27 plans, was
therefore never adopted into the local gate, and that is how a shifted line pin reached CI red on
PR #67.

### Diff-scoped and REQUIRED, with the losing option's cost stated

Both arms agreed. The cost of the rejected option (all-scoped advisory) is alert fatigue: new
regressions become invisible inside a 9027-issue backlog. The cost of the chosen option is **loss of
continuous visibility into untouched debt, and blindness to global effects from linter upgrades**.
That visibility is real and must live somewhere — a **scheduled, trend-oriented `--all` report**
under COREDEV-2787 / COREDEV-2778, never in the required PR context.

### THE SIX DEFECTS INHERITED FROM COREDEV-2771 (its plan, §"The CI job is out of scope")

Its own gate found these across three rounds **by reading, not by running** — a CI job cannot be
executed without pushing a branch and watching a real workflow. They are inputs, not discoveries:

| # | defect | why it matters |
|---|---|---|
| 1 | `check-mode: popular` | not a valid value for this action |
| 2 | `--upstream origin/${{ github.base_ref }}` | `base_ref` is **empty on `push`** |
| 3 | `--upstream origin/${{ github.ref_name }}` | equals HEAD ⇒ **EMPTY diff: it passes having checked nothing** |
| 4 | `post-annotations: true` on the check job | a fork-only `workflow_run` input |
| 5 | a custom `--upstream` at all | the action injects one, so PRs get two |
| 6 | `contents: read` alone | the action passes `--github-annotate` on non-fork PRs |

**Defect 3 is the one this plan is most at risk of repeating**, and it is the reason §5's cells are
written the way they are: a gate that checks an empty diff and reports green is indistinguishable
from a working gate by any cell that only asserts "the job passed".

### The job contract

* **Action pinned by full SHA** per `AGENT_CONTRACTS.md` §6 — `trunk-io/trunk-action` v2.0.0 =
  `e1234e67a86010d61ddac8d8ebf4b783e2ffd2fa`. (v1.3.0 and v1.3.1 resolve to the *same* SHA, i.e. tags
  in this action have moved — which is precisely why §6 requires SHAs. Dependabot updates the pin.)
* **No custom `--upstream`** (defect 5). The action supplies it; PR, push and `workflow_dispatch`
  base behaviour is the action's, verified per event type in §5.
* **Stable job + context name** — `trunk-check`, so the ruleset context is nameable and does not
  drift. Runner `ubuntu-latest`, explicit `timeout-minutes`.
* **No autofix.** `trunk fmt` / `trunk-fmt-pre-commit` stays disabled, as COREDEV-2771 requires.
* **Enabled-linter-set contract** — the job must run the linters `trunk.yaml` enables, with **no
  `--filter`**. Asserted in §5 cell 4, because a job filtered to one linter passes a naive cell.

### Permissions — A STRUCTURAL DECISION, SEE §6

The workflow grants `contents: read` globally (`plugin-ci.yml:22-23`). Defect 6 says the action
passes `--github-annotate` on non-fork PRs, which needs `checks: write`. **Two options, and this is
not mine to pick unilaterally** — see §6.1.

## §2 — COREDEV-2798: identity is CLASS-SPECIFIC, and revision 1 got it wrong

Revision 1 proposed "exactly one line in the file hashes to `sourceSha256`" for prepend-only files.
**Both arms rejected it, correctly: that would fail against a currently-correct tree.**

The inventory has two site classes and they carry identity in different fields:

| class | live identity | `sourceSha256` must |
|---|---|---|
| `quote-keep` (`CHANGELOG.md:2140`) | the source line itself | **match exactly once** |
| `rewrite` (`README.md:187` → dest 292) | `destination.payloads` | **match NOTHING** — the legacy source was deliberately deleted |

`test_transcript_path_inventory.py:349` already enforces source-absence for rewrites. Searching
`README.md` for its `sourceSha256` would therefore fail on a healthy tree — revision 1 would have
broken the check it claimed to repair.

**The corrected fix, per class:**

* **quote-keep** — assert exactly one line matching `sourceSha256`; `line` becomes a re-derived hint.
* **rewrite** — retain the source-absent assertion **unchanged**, and assert exactly one matching
  destination payload block; `destination.line` becomes a re-derived hint.
* **anchors too (agy, r1)** — `precedingAnchorLine` / `followingAnchorLine` shift on prepend
  identically and are demoted to hints alongside the others. Revision 1 missed them entirely.
* Scope the demotion to **prepend-only files** (`CHANGELOG.md`, `README.md`). Every other site keeps
  its line assertion; nothing else in the repo grows at the top.

**What must NOT change:** a genuine content edit still fails, for both classes. §5 cells 6–7 pair a
relocation (must pass) against a content change (must fail), **per class**, because revision 1's
single CHANGELOG-only relocation cell would not have covered README's different path at all.

## §3 — COREDEV-2801: a diagnostic and a detector, not a remedy

**Cause not identified. Four hypotheses tested and eliminated** (stale scopes; stale fork; a
release/tag pin; VS Code caching) — recorded on the ticket so they are not re-tried. Established:
`2.7.0` exists in exactly one file; `main` has not served it since `13d5c2b` (Aug 7); that file **is**
rewritten by updates and the stale entries survive the rewrite; four live sessions were bound to it.

### §3a — the experiment (blocks any remedy)

`claude plugin update` at **user scope**, outside any project; re-read the record.

**Recovery is not root cause (codex, r1).** Revision 1 said a successful advance implies the remedy
is "documentation plus cache pruning". It implies no such thing — it proves only that a user-scope
update repairs *current* state and that nothing reverted it *immediately*. It does not explain how
the stale entries survived earlier rewrites. Outcomes are therefore recorded as **containment**, and
root cause stays open.

### §3b — the detector, and the bootstrap problem revision 1 ignored

A preflight comparing the **loaded** plugin version against the repo's `plugin.json`, emitting a
diagnostic on mismatch.

**codex's finding, which is fatal to the naive design: a session bound to 2.7.0 cannot execute a
detector shipped only in 2.8.4+.** The detector must therefore live where a *stale* session still
reaches it. Options, to be settled during implementation with the §3a evidence:

1. a repo-side script run from the **current checkout** (not the installed plugin) — always current,
   but only fires when someone runs it;
2. a check inside an already-loaded hook — fires automatically, but is subject to the same staleness;
3. a CI/release-time assertion — cannot help a live session at all.

Option 1 is the only one that is correct-by-construction for the stale case, and is the presumptive
choice. **A caller must be named**: revision 1 specified a script with no invoker, so its cell could
have passed against dead code nothing runs.

## §4 — Milestones

- [ ] **M1** (parallel) — COREDEV-2798 class-specific content-addressing, anchors demoted, cells 6–7.
- [ ] **M2** (parallel) — add the `trunk-check` job, diff-scoped, `continue-on-error: true`.
- [ ] **M3** — remove `continue-on-error` and observe **one genuinely strict green run and one
      deliberately red run** before any promotion. *Revision 1 would have promoted a context observed
      only while failures were suppressed — a context that had never been able to fail (codex, r1).*
- [ ] **M4** — add the required context to ruleset `Control`, **only after M3's red run proves it can
      fail**, and only with explicit maintainer instruction (§6.2).
- [ ] **M5** — run §3a; record the outcome on COREDEV-2801 as containment.
- [ ] **M6** — implement §3b with a named caller, per §3a's evidence.

M3 and M4 are gated on evidence, not schedule.

## §5 — Testing

The first three cells exist because of inherited defect 3 — a gate over an empty diff passes having
checked nothing:

1. **The diff is non-empty and correct per event.** Assert the resolved upstream/diff on
   `pull_request`, on `push` to `main`, and on `push` to `alpha`. A run whose diff is empty **fails**.
2. **The gate bites.** A deliberately bad changed file fails the job.
3. **The gate does not over-reach.** A PR touching one clean file passes **with the 9027-issue
   backlog present** — and, separately, a PR touching a **historically dirty** file passes for the
   pre-existing findings while still failing for newly introduced ones (codex, r1: "one clean file"
   proves nothing about suppression).
4. **The enabled-linter set is the configured set.** No `--filter`; a per-linter positive control, so
   a job silently reduced to one linter cannot pass cells 2–3.
5. **No autofix.** The job never mutates the tree.
6. **quote-keep: relocation passes / content change fails.** Prepend to `CHANGELOG.md` → green with
   no edit; alter the pinned line's content → red.
7. **rewrite: relocation passes / payload change fails.** Prepend to `README.md` → green; alter the
   destination payload → red; **and the legacy source remains absent** in both.
8. **Version-mismatch detector fires from its real caller** — not from a direct unit call, which
   would pass against code nothing invokes.

## §6 — STRUCTURAL DECISIONS FOR THE MAINTAINER

These change the repo's security or merge posture. **None is taken unilaterally.**

### 6.1 — `checks: write` on the CI workflow

The workflow is `contents: read` today. To annotate PRs the action needs `checks: write`.

* **(a) Grant `checks: write`, scoped to the `trunk-check` job only** — inline annotations on the
  diff; widens that job's token scope.
* **(b) Annotation-free** — keep `contents: read`; findings appear only in the job log. No scope
  change, worse ergonomics.

*Recommendation: (b) to start.* The gate's value is blocking, not annotating, and a read-only
workflow is a smaller target. Revisit if log-only proves unusable.

### 6.2 — Adding a required context to ruleset `Control`

Ruleset `Control` (16082567) protects `main` and `alpha` with **`bypass_actors: []` — no escape
hatch**. Adding `trunk-check` as required means a failure blocks every merge with no override, and
**adding a context before the workflow emits check runs previously made `main` unmergeable**
(COREDEV-2767). M4 is therefore explicitly gated on M3's evidence **and on maintainer instruction.**

### 6.3 — `.githooks/pre-commit` gains a trunk check

Local diff-scoped check measured at **7s for one changed file** — viable. But it changes every
commit's cost, and the hook currently runs validators that are all sub-second. agy's r1 note stands:
documenting it in `CLAUDE.md` without wiring `.githooks/pre-commit` would describe a hook that does
not run. **Decision needed: wire it, or document it as CI-only.**

### 6.4 — `markdown-link-check` in a required set

It is **network-dependent**, and COREDEV-2771 explicitly transferred its flakiness risk here. A
required gate that fails on someone else's outage is a bad gate. **Options:** keep it required with a
defined retry/re-run posture, or split it into the scheduled advisory job (COREDEV-2778).
*Recommendation: split it out.*

## §7 — Files Changed

* `.github/workflows/plugin-ci.yml` — `trunk-check` job, SHA-pinned action, per-event base behaviour
* `scripts/tests/test_transcript_path_inventory.py` — class-specific content-addressed assertions
* `docs/planning/COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json` — `line`, `destination.line` and both
  anchor lines demoted to hints for prepend-only sites
* `CLAUDE.md` — gate-list update
* `.githooks/pre-commit` — **only if §6.3 is decided "wire it"**
* a §3b preflight script **plus its named caller** — path pending §3a

## §8 — Notes

**Revision 1's largest defect was not technical.** It was written without reading
`COREDEV-2771_TRUNK_LINT_CONFIG_PLAN.md`, which contains a section addressed to this ticket handing
over six reviewed defects and the measured constraints. Both reviewers then re-derived that work.
Before planning anything here, grep `docs/planning/` for the predecessor.

**Review arms run SERIALLY** (COREDEV-2772): concurrent arms mutate the shared `.git` that the tree
fingerprint hashes; all three r13 arms on COREDEV-2711 voided that way, and serial re-runs were clean
three for three.

**Still open for review.** §6.1's recommendation (annotation-free) trades ergonomics for a smaller
token scope. If inline annotations are what makes a lint gate usable in practice, (b) is the wrong
call and I would rather be told so than ship a gate people route around.
