# Repo Gating Hygiene Plan — trunk in CI, pin drift, and stale install resolution

**Status:** Planning, revision 28
**Created:** 2026-08-28
**Last Updated:** 2026-08-31
**Basis:** `c913303` (origin/main, plugin 2.8.3) · **Tickets:** COREDEV-2780, COREDEV-2798, COREDEV-2801

> **r1** `04048c7`: codex + agy both `REQUEST_CHANGES`. Concordant: §2's fix was wrong for
> `rewrite`-class sites, and the M1→M2 precondition was false.
> **r2** `b2ca1b0`: codex `REQUEST_CHANGES` (7 DESIGN) + agy `REQUEST_CHANGES` (2 DESIGN), concordant
> on the alpha landing precondition and on §6.1 option (b) being unimplementable as written. codex
> read the pinned action's **source at its SHA** and found two self-contradictions in this plan.
> Revision 3 closed all nine.
> **GATED at revision 27** (`0e3dccb`, digest `628beceeb2277ea6`): **r28** codex `APPROVE_WITH_NOTES`
> + agy `APPROVE_WITH_NOTES`, and **r29 REPRODUCED that double approval on byte-identical input** —
> the campaign's first approval to survive the reproduction the r16 double approval failed. Combined
> verdict persisted under `.verdicts/`. **Kimi K3 at `max`** (verified from `wire.jsonl`, not
> self-reported) then reviewed the same bytes as a **non-gating third lens** and also returned
> `APPROVE_WITH_NOTES` — finding two things twenty-nine rounds of diff-reading could not, because no
> edit ever touched them: **the plan never tested that a red check blocks a merge**, and **it had no
> way to turn the gate off**. Revision 28 folds those in, with codex's four r28 notes.
> **r27** `bcca42d`: codex `REQUEST_CHANGES` (3 ship-affecting + 1 document) + agy
> `APPROVE_WITH_NOTES`. **Two of the three were introduced by revision 26's own stimulus contracts** —
> and revision 26 is the one draft since r25 that was **not** run through the pre-commit check.
> Round 26 (checked) found zero self-introduced defects; round 27 (unchecked) found two. The check is
> now mandatory before every commit, not optional.
> **r26** `cc5e8e2`: **agy `APPROVE_WITH_NOTES` with [SUBJECT] 0** — "both document notes will
> naturally settle during implementation" — and codex `REQUEST_CHANGES` (7 findings). **None of
> codex's seven was traceable to revision 25's own edits** (grep-verified), the first revision in six
> where the author introduced nothing: revision 25's four-lens pre-commit check absorbed them before
> the gate saw them. The seven are pre-existing depth, mostly *executable-contract* gaps.
> **r24** `ff09b20`: codex `REQUEST_CHANGES` (4 [SUBJECT], 4 [DOCUMENT], down from 7/2) + agy
> `APPROVE_WITH_NOTES`. **Five of the eight were propagation failures from revision 24's own edits** —
> in the revision whose commit message said "derive the family by grep". The gap: I grepped the
> families the *review named*, not the invariants my *own edits established*. Pinning `permissions` at
> the root left the job level open; binding cell 2's M2 branch to a diagnostic left its M3 branch
> bare; expanding cell 16 left §7's inventory and M2b's "never" behind. Revision 25 greps every
> invariant it states, and its draft was checked for exactly that before commit.
> **r23** `b8f71a8`: codex `REQUEST_CHANGES` (7 [SUBJECT], 2 [DOCUMENT]) + agy `APPROVE`. Revision
> 23 deleted the append-vs-delete instance codex NAMED and left two more sites of the same family
> standing — the lesson landing on itself. Revision 24 derives each family by grep before editing, and
> **deletes the detector's mode operand outright**: with both surfaces reading the same two files it
> selected nothing, while colliding with trunk's unrelated `--index`.
> **r22** `bf13637`: codex `REQUEST_CHANGES` (5 [SUBJECT], 3 [DOCUMENT], down from 9/2) + agy
> `APPROVE_WITH_NOTES`. **codex dropped the `action.yaml` citation dispute** after five rounds, given
> the time to fetch the file and the instruction to paste what it found. Three of its five were mine,
> and all three were one shape: **revision 22 APPENDED a correction and left the superseded text
> standing**, so two contradictory normative statements coexisted and an implementer could follow
> either — §3b said both surfaces read `origin/main` *and* kept the paragraph sending pre-commit to
> the index; C0 was added while every authoritative range still read C1–C9; the new freshness rule
> contradicted Table A's "silent records nothing". **Revision 23 deletes rather than appends.**
> (r22's codex arm timed out at 1800s mid-verification — no verdict, so it counted as nothing; r23
> re-ran the same bytes at 3300s.)
> **r21** `c22991a`: codex `REQUEST_CHANGES` ([SUBJECT] 9) + agy `APPROVE_WITH_NOTES` ([SUBJECT] 2),
> **concordant on all three defects revision 21 introduced in its own repair** — C1 still forbade the
> `types:` that C2 now requires, cell 11's replacement mutant (`tags:`) is no more constructible under
> `pull_request` than the `push.tags` it replaced, and the `origin/main` fix reached Table A but not
> §3b. *Fixing a fix-one-site defect by fixing one site.* codex's tenth finding — a fifth attempt at
> the `action.yaml` citations, this time **quoting invented text** at all four lines — is refuted in §8
> against a fresh byte-identical fetch.
> **SWEEP** (pre-r21, not a gate round): a ten-lens adversarial pass over revision 20 by Claude
> subagents — 49 findings, and **eight of ten independent lenses converged on the same defect**:
> revision 20's push-leg split was applied to **C1 only**, leaving §1's Resolution, C2, cell 11's
> mutants, §4 and §7 all describing a two-event required workflow that no longer exists. The largest
> single-member-of-a-family miss of the campaign, and my own fix caused it. The sweep also found four
> defects twenty gate rounds had not: a retargeted PR never re-runs (`pull_request`'s default activity
> set excludes `edited`, and C1 forbids `types:`); `persist-credentials: false` is forbidden by C8 yet
> is the only remedy for zizmor's `artipacked`, so the gate's workflow trips the gate's own linter;
> Table A's `expected` is the working manifest, which the version-bump rule keeps one bump AHEAD, so
> the detector warns on every developer machine; and the pre-commit timeout is required in three
> places and valued in none.
> **r20** `e831240`: agy `APPROVE`, codex `REQUEST_CHANGES` (5 [SUBJECT], 1 [DOCUMENT]). Two matter.
> **Cross-event range substitution**: one workflow emitted the *same* required context for
> `pull_request` and `push`, so a PR could be satisfied by the `push` run on its head SHA — which
> lints `before..head`, not the larger PR range. The push leg now lives in its own **non-required**
> workflow. **And §7 omitted the mandatory version bump** — this repo's own rule that every shipping
> change moves `plugin.json`, both README sites and `CHANGELOG.md`, without which no install ever
> pulls the fix.
> **r19** `41c709c`: agy `APPROVE`, codex `REQUEST_CHANGES` (4 [SUBJECT], **0 [DOCUMENT]** — the
> document itself is now clean). All four are the *sensor* lesson recurring one level deeper: an event
> mapping allowlisted by name but not by option (`push.tags` is still permitted); an M2 assertion on a
> step `outcome` the REST API does not expose; a cell-5 harness whose launcher *records and exits* and
> so never gives the fixture a chance to change; and a Table B row that assumes `expected` is frozen.
> **r18** `5063429`: agy `APPROVE`, codex `REQUEST_CHANGES` (2 [SUBJECT], 3 [DOCUMENT]). Its first
> finding is the reproduction's lesson repeating: **cell 5's owner is a sink, not a sensor.** C8 makes
> the Trunk action the *final* step, so nothing after it can hash the fixture — a committed JSON
> artifact records what someone observed, and no permitted step observes it. Revision 15 moved cell 5
> to that artifact to satisfy the hybrid rule and thereby gave it an owner that cannot see.
> **r16** `3c739ec`: **BOTH ARMS `APPROVE`** — the campaign's first double approval — and the
> **REPRODUCTION on byte-identical input (r17) FAILED**: codex flipped to `REQUEST_CHANGES` and found
> **three [SUBJECT] defects the approving run had certified clean**, one of them a cell that *cannot
> pass*. agy held `APPROVE` across both. **This is the third time on this project that a double
> approval did not survive reproduction** — one approving round is not a gate pass, and the rule has
> now paid for itself three times.
> **r15** `e305caf`: **agy `APPROVE`** (fifth approving verdict) + codex `REQUEST_CHANGES`
> ([SUBJECT] 2, [DOCUMENT] 2). codex's finding completes revision 15's own idea: the registry typed
> the **target** but not the **mutation case**, while several obligations need more than one mutation
> (C1 add *and* remove a trigger; C2 diverge each side; C8's two steps in four forms). "One mutant per
> entry" therefore still under-covered. Cases are now first-class and the generator **iterates cases,
> not entries**.
> **r14** `b0353ae`: **agy `APPROVE_WITH_NOTES` with [SUBJECT] 0** — it found nothing that would ship
> wrong — and codex `REQUEST_CHANGES` ([SUBJECT] 3, [DOCUMENT] 3), down from 5/1. The two arms were
> **concordant on exactly one item**, a §7 inventory line. codex's substantive finding: the registry's
> schema (id, path, mode, value) can express ordinary YAML obligations but **not** C6's repository
> fixtures, C2's live-remote relation, or C8's digest and run-body semantics — so iterating entries
> did not make under-coverage impossible after all. Revision 15 gives the registry **typed kinds and
> mutation recipes**.
> **r13** `6caaea6`: **agy `APPROVE`** (fourth consecutive) + codex `REQUEST_CHANGES` ([SUBJECT] 5,
> [DOCUMENT] 1) — and it went after revision 13's two new *mechanisms*, as asked, holing both.
> **The derivation was asserted, not defined**: C1–C9 are unrestricted prose, so nothing can generate
> mutants from them, and a hand-written registry compared against mutant names just moves the drift up
> one level. **The ownership rule had no case for hybrids**: C2 compares local YAML against the *live*
> ruleset, which the Python owner cannot see. Revision 14 makes the contract a **structured registry
> that §1 renders**, so there is no prose to parse and nothing to drift from.
> **r12** `dd24ff8`: **agy `APPROVE`** (third consecutive) + codex `REQUEST_CHANGES` ([SUBJECT] 6,
> [DOCUMENT] 1). Two genuine design gaps — C3 constrained the job and the *Trunk* step but not the
> two **guard** steps (an `if: false` on a guard preserves the sequence and the body digest), and
> Table B still lacked Table A's equal-precedence-versus-`expected` classification. **The other four
> were gaps between a prohibition and its mutant, or between a cell and an owner that cannot observe
> it — so revision 13 closes those two CLASSES structurally**: the mutant set is now *derived* from
> the clause list, and ownership follows a stated rule rather than a per-cell assignment.
> **r11** `63d7b7b`: **agy `APPROVE`** (second consecutive) + codex `REQUEST_CHANGES` ([SUBJECT] 4,
> [DOCUMENT] 5). The remaining hole was the same shape one level in: C5 forbids YAML `env:`, but the
> **permitted `run:` bodies can write `TRUNK_PATH` to `$GITHUB_ENV`** — the guard checks paths, not
> runner state. C8 now freezes those bodies. codex repeated its `action.yaml:289` citation claim
> (line 266 in r9, 267 in r11); **refuted again, this time from two independent fetches that are
> byte-identical — the line is 289.**
> **r10** `c5b40d4`: **agy `APPROVE`** — the campaign's first — and codex `REQUEST_CHANGES`
> ([SUBJECT] 7, [DOCUMENT] 3). **codex explicitly accepted §0's scope** ("I did not count the three
> COREDEV-2803 supply-chain issues or variants"), so the threat model held and the findings are now
> narrow. It also found a contradiction agy walked straight past while describing both clauses: **C6
> required its guard immediately before the action while C8 put another step between them.** Two arms
> earn their cost here.
> **r9** `041f3fc`: codex `REQUEST_CHANGES` ([SUBJECT] 11) + agy `REQUEST_CHANGES` ([SUBJECT] 2).
> **All three of agy's findings were concordant with codex**, and those three are fixed here: five
> unowned cells, the `lint.definitions` command-override vector, and a C1→C7 cross-reference. codex's
> count *rose* because r9's prompt asked it to enumerate an open-ended attack surface end to end —
> and three of its findings (unverified launcher download, linter-plugin provenance, GHA cache
> provenance) are **properties of the tool, not defects in this plan**. Those are now **out of scope
> and tracked as COREDEV-2803**, under the threat model stated in §0. One codex claim was **refuted**:
> `uses: ./.trunk/setup-ci` is at `action.yaml:289` at the pinned SHA, exactly as cited. **codex has
> now made this claim in FIVE rounds, and in r21 escalated from asserting wrong numbers to QUOTING
> INVENTED TEXT at them** — claiming 289 held `run_with_timeout.sh pull_request.sh`, 267 held
> `if: env.INPUT_SETUP_DEPS == 'true'`, 81 held `post-annotations:` and 74 held `save-annotations:`.
> A fourth fetch, byte-identical to the previous three (430 lines, sha256 `c84c1c16f55a406c`), shows
> **74 `upload-series:`, 81 `save-annotations:`, 89 `post-annotations:`, 267
> `determine_check_mode.sh`, 289 `uses: ./.trunk/setup-ci`.** Its whole claim sits one input-block
> early. A quoted line is a checkable artifact like any other, and both arms have now fabricated
> one.** Settled by content rather than by counting: at that SHA the file is 430 lines and
> byte-identical across the contents API and `raw.githubusercontent.com`; **line 267 contains
> `${GITHUB_ACTION_PATH}/determine_check_mode.sh`** and line 289 contains `uses: ./.trunk/setup-ci`.
> The `save-annotations` citation is likewise 81, not 74 — **line 74 is `upload-series:`**. Naming
> what is at the disputed line is the form of this refutation that a fifth round cannot re-open.
> **r8** `0e02bfe`: codex `REQUEST_CHANGES` ([SUBJECT] 4, [DOCUMENT] 4) + agy `REQUEST_CHANGES`
> ([SUBJECT] 3, [DOCUMENT] 2). **The r7 allowlist closed the caller's door and left three others
> open**, all verified at the pinned SHA: `setup/locate_trunk.sh` prefers a *checked-out*
> `.trunk/bin/trunk`, `tools/trunk` or `./trunk` before downloading; `action.yaml:289` runs a
> checked-out `.trunk/setup-ci` via `uses:`; and job/step `env:` reaches the action's scripts. **A PR
> could supply the tool that tests it.** Separately, `determine_check_mode.sh` maps `merge_group` to
> no branch at all, so it falls to `check_mode=none` — every step skipped, composite action
> **succeeds** — which made r7's "conditionally add `merge_group`" the exact false success cell 11
> forbids. **Maintainer decision (2026-08-28): keep the pinned action and close the doors**, rather
> than dropping to a hash-pinned CLI invocation; the action's linter caching is worth the enumeration.
> **r7** `fe5281a`: codex `REQUEST_CHANGES` (5 DESIGN + 5 COMPLETENESS) + agy `REQUEST_CHANGES`
> (1 DESIGN + 3 COMPLETENESS, marking Q1/Q4/Q5 **CLOSED & SOUND**). codex found the prohibition set
> was a **blacklist**: the pinned action takes a caller-supplied `trunk-path` — *the launcher it
> executes* — and a `post-init` its own docs call "a caller-controlled escape hatch", so a no-op
> launcher returning 0 satisfies every prohibition while linting nothing. **Verified at the pinned
> SHA.** Revision 8 inverts it to an allowlist. Both arms also found Table B still not
> mutually exclusive, and the `job id` / effective-check-name split.
> **r6** `e16daff`: codex `REQUEST_CHANGES` (5 DESIGN + 5 COMPLETENESS) + agy `REQUEST_CHANGES`
> (5 DESIGN + 2 COMPLETENESS), **both confirming 19 is the right frozen linter count** by parsing the
> config independently. Removing the trigger was necessary but **not sufficient** — cell 11 asserted
> four structural keys while claiming a property about *all* paths, and a step-level `if:` or
> `continue-on-error` on the Trunk step still reports a conclusion without Trunk running. Revision 6
> also introduced a **fresh self-contradiction** (`push` "to the gated bases" vs a blanket ban on
> filters) and left **revision 4's `if:` guard described as current in §8**.
> **r5** `7b7a459`: codex `REQUEST_CHANGES` (5 DESIGN + 6 COMPLETENESS) + agy `REQUEST_CHANGES`
> (2 DESIGN + 4 COMPLETENESS). **codex inverted revision 4's central fix**: a job skipped by an `if:`
> reports **Success** to a required context, so the guard *created* the bypass it was meant to close,
> and cell 11 would have certified it. Verified against GitHub's own troubleshooting doc. Revision 6
> moves the job to its own workflow with no `workflow_dispatch` trigger. codex also found the r4
> cell-7 repair **impossible as written**, cell 6 confounded the same way cell 7 was, and §3b's
> "only mechanism" claim false.
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

## §0 — What this gate defends against, and what it does not

**Stated here because rounds 7-9 kept re-deriving it, each time deeper.** This plan makes `trunk
check` a diff-scoped required context. Its adversary is **the accident**: a lint regression nobody
noticed, a linter silently dropped from the config, a gate that reports green having checked nothing.
Every clause of §1's contract exists to close a way the gate could *look* like it ran when it did not.

**It is not a defence against someone who can open a pull request against this repo.** §1's residual
risk (b) is the reason: for `pull_request` events the workflow file itself comes from the PR, so
anyone who can propose a change can edit `.github/workflows/trunk-check.yml` outright. Against that
actor, the subtler routes are irrelevant — they would use the front door.

So three findings from r9 are **explicitly out of scope**, filed as **COREDEV-2803**: the Trunk
launcher is downloaded without a digest check (`locate_trunk.sh` curls and executes it); the linter
implementations come from a tag-pinned plugin source whose tool definitions fetch binaries without
declared digests; and GitHub Actions caches are unsigned by design. Each is real. None is closeable
without either abandoning the action the maintainer chose to keep, or work that only pays off after
`.github/` is under CODEOWNERS review — which is COREDEV-2803's first item.

**A reviewer noting these is right about the facts and wrong about the scope.** They are recorded
here so that observation resolves rather than re-opens.

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
| 4 | `post-annotations: true` | **absent** — C4's allowlist admits no unlisted key, so "or false" is superseded | 9 |
| 5 | a custom `--upstream` at all (action injects one) | as 2 | 9 |
| 6 | `contents: read` alone vs `--github-annotate` | resolved by §6.1's chosen mechanism, asserted | 10 |

**Defect 3 remains the one this plan is most at risk of repeating.** A gate that checks an empty diff
and reports green is indistinguishable from a working gate by any cell that only asserts "the job
passed" — which is why cell 1 asserts the *resolved diff*, not the job outcome.

### `workflow_dispatch` — the seventh hazard, found in the action's source (codex, r2)

The pinned action **autodetects `workflow_dispatch` as `check-mode=all`**
(`determine_check_mode.sh` @ `e1234e67`). That would re-litigate all 9027 findings and directly
contradict this section's central claim.

**This hazard has now defeated two fixes, each in a different way. The third does not guard the
job — it removes the trigger.**

* **Revision 3** wrote a job-level `on:`. **GitHub has no such key at job scope**, so the job stayed
  reachable on dispatch and the contradiction was merely relocated (codex + agy, r3).
* **Revision 4** replaced it with `if: github.event_name != 'workflow_dispatch'`. Valid syntax — and
  **strictly worse**, because it converts the hazard into a *silent pass* (codex, r5).

**Why the `if:` guard is a bypass, not a fix.** GitHub's own troubleshooting documentation states
that when *"a job is skipped by a conditional"*, **"the job reports 'Success'"** — and a required
context is satisfied by that success. `workflow_dispatch` can be aimed at any branch, so dispatching
`plugin-ci.yml` at an internal PR's head branch would attach a **successful, skipped** `trunk-check`
to that PR's head SHA **without Trunk ever running**. Cell 11, asserting the literal `if:`, would
have *certified* the bypass. The same doc gives the general rule directly: **"Avoid requiring
workflows that can be skipped."**

**Resolution: `trunk-check` moves to its own workflow file, `.github/workflows/trunk-check.yml`,
whose `on:` contains **`pull_request` only** and *no* `workflow_dispatch`.** (Revision 20 moved the
push leg out of the required context but left this sentence, C2, cell 11's cases, §4 and §7 all
describing the two-event workflow — the push leg's own home is `trunk-check-push.yml`, below.) The job is then
unreachable on dispatch by construction rather than by condition, so there is no skipped-success
state to exploit.

**BRANCH filters are required; PATH filters are prohibited (codex, r6).** Revision 6 said `push` was
scoped "to the gated bases" *and* banned every filter — **authorising no configuration at all**. The
distinction the GitHub doc actually draws is what the two kinds of filter skip on:

* **`branches: [main, alpha]`** — REQUIRED on the required workflow's single `pull_request` event
  (and, separately, on the non-required push canary), and it must match the
  ruleset's target set exactly. A PR into an ungated base does not need the context, so nothing is
  left pending; a mismatch in either direction is the COREDEV-2767 shape.
* **`paths:` / `paths-ignore:`** — PROHIBITED. These skip on *changed files*, so a PR into a gated
  base that touches only excluded paths requires a context the workflow never produces, leaving it
  **Pending, which blocks merging** — a false pass traded for a permanent block.

**No `if:` on the job, and none on ANY of the five steps** — C3 widened this after an `if: false` on
a *guard* step was found to preserve both the frozen sequence and the frozen body digests while
removing the guard entirely; the two-site wording that defect named survived here. See C3 and cell 11
for the full prohibition set.

This does not change the context name: a required check names a job's **effective check name** — its
`name:` where present, else the job id (cell 14) — never the workflow, so the context stays
`trunk-check`. It does mean the repo now has two workflows that must not both define a job by
that name — see cell 14's uniqueness census.

If a manual full-tree run is ever wanted it belongs in the scheduled COREDEV-2787 report, under its
own non-required context.

### The job contract

* **Action pinned by full SHA** per `AGENT_CONTRACTS.md` §6 — `trunk-io/trunk-action` v2.0.0 =
  `e1234e67a86010d61ddac8d8ebf4b783e2ffd2fa`. (v1.3.0 and v1.3.1 resolve to the *same* SHA — tags in
  this action have moved, which is exactly why §6 requires SHAs. Dependabot updates the pin.)
* **SHA-pinned `actions/checkout`** in the job. The action does not check out the caller's repo
  itself; its internal checkout is conditional on a separate target-checkout mode (codex, r2).
* **THE WORKFLOW CONTRACT IS A STRUCTURED REGISTRY, and the clauses below are RENDERED FROM IT.**
  `docs/planning/COREDEV-2780-contract.yaml` is the authority: one entry per **atomic obligation**,
  each with a stable id (`C3.step-if`, `C8.checkout-inputs`, …), a **typed target kind**, and the
  mutation recipe that kind implies.

  **The kinds exist because revision 14's flat schema could not express three of its own obligations**
  (codex, r14). `(id, yaml-path, required|prohibited, value)` covers ordinary workflow keys and
  nothing else, so C6's repository fixtures, C2's live-remote comparison and C8's digest semantics
  would have silently received a YAML-shaped mutant or none — under-coverage by *construction*, which
  is what the registry was meant to abolish:

  | kind | obligation it carries | how its mutant is built |
  |---|---|---|
  | `yaml` | a workflow key that must be present with a value, or absent | set / clear / alter the key at its path |
  | `repo_fixture` | a path that must not exist in the checked-out tree (C6) | materialise it — and for `.trunk/setup-ci`, as a **valid composite action that exits green**, not a bare executable |
  | `content_digest` | bytes that must hash to a pinned value (C8's run bodies, cell 4's `lint:` block, **C6a's shared resolver script**) | edit the bytes while preserving the surrounding shape |
  | `remote_relation` | local content that must equal live remote state (C2) | diverge the local half, and separately the remote half |

  **Mutation CASES are first-class, and the generator iterates cases rather than entries**
  (codex, r15). One mutant per *entry* still under-covers, because several obligations need more than
  one mutation to be exercised: C1 must both **add** a trigger and **remove** a required one; C2 must
  diverge the **local** side and the **remote** side separately; C8's two run steps need **four forms
  each**; and a generic `content_digest` byte edit passes while a validator that *normalises away*
  `$GITHUB_PATH` lines before hashing survives — only an independently encoded `$GITHUB_PATH` case
  kills that one.

  Each case declares its **operator and side**, its **target**, its **payload or fixture**, a
  **validity check**, and its **own expected diagnostic** — so every generated mutant is checked to be
  constructible, to change the intended property, and to fail with its own message. Two cases need
  more than a key edit and say so: C3's `needs:` case **declares the failing support job** it
  requires, and `remote_relation`'s remote-side case mutates an **injected ruleset observation**, never
  the live ruleset. Exact fixture bytes stay an implementation detail.

  **What this does NOT prove, drawn at the right boundary.** Cell 15 compares the rendered prose
  against the registry, and both derive from the same authority, so it **cannot prove the registry is
  semantically complete** — it cannot know an obligation nobody wrote down. Revision 15 said "nothing
  mechanical can catch a wrong registry", which is **overbroad** (codex, r15): a *specific* wrong
  registry is catchable, and two things do catch one —

  * **a survivor corpus**, maintained *independently of the rendered authority*: every mutant that has
    ever survived a round of this gate stays in a corpus that must keep failing. A registry edit that
    silently drops an obligation reddens the corpus even though the rendering lint is happy;
  * **the end-to-end behaviour cells** (1, 2, 3, 5, 12), which observe real runs and do not consult
    the registry at all.

  What remains genuinely unmechanisable is *arbitrary* completeness, and what guards that is the
  registry being small, diffable and reviewed.

  **Revision 13 said the mutant set was "derived from the clause text" — which is not a mechanism**
  (codex, r13). C1–C9 were unrestricted prose; no test can discover an obligation it cannot parse, and
  a hand-written registry checked against hand-written mutant *names* recreates exactly the drift the
  meta-assertion was supposed to remove. With a structured source there is nothing to parse and
  nothing to keep in step:
  * cell 11 **generates one mutant per mutation CASE** (§1's cases are first-class; several
    obligations declare more than one), so under-coverage is impossible by construction rather than
    by assertion;
  * the clause prose below is **rendered from the registry** and a lint fails if the rendered text
    and the registry disagree — the two cannot drift because only one of them is written by hand;
  * adding an obligation means adding a registry entry, which *automatically* produces its mutant.

  The clauses read as follows.

* **The rendered clauses — do not edit these by hand; edit the registry.**
  Revision 8 copied the event set and the input allowlist into §1, M2, cell 11 and §7, **and they had
  already diverged** — only cell 11 permitted `merge_group` (codex, r8). This block is the single
  authority; cell 11 asserts these clauses by name.

* **THE CONTRACT'S TEETH DEPEND ON `validate` STAYING A REQUIRED CONTEXT.** Every clause below is
  enforced by the Python suites, which run **only** inside `plugin-ci.yml`'s `validate` job. If that
  context were ever dropped from ruleset `Control`, a contract-breaking edit to `trunk-check.yml` would
  merge green behind a passing `trunk-check`, and nothing here would notice. **Verified live at
  revision 28**: `Control` requires `validate`, `py39-smoke`, `secret-scan`, `load-check` and
  `redactor-equivalence (ubuntu-latest)`, all under integration 15368. The dependency holds — but it
  was unstated, and an unstated dependency is one nobody re-checks (kimi, third lens). M4's readback
  compares the canonical ruleset, so a payload dropping `validate` is caught there.

  **C0 — the workflow ROOT mapping is an allowlist, and `permissions` is PINNED BY VALUE.** Only
  `name`, `on`, `permissions`, `jobs` — and `permissions:` must be exactly **`contents: read`**
  (§6.1's decision). Permitting the *key* without pinning its *value* let `permissions: write-all`
  satisfy every structural cell while contradicting §6.1, and cell 10 could not tell the difference:
  it observes the annotation artifact and the absence of a 403, which a wider token produces just as
  happily (codex, r24). Cell 10 is therefore **hybrid** — the evidence artifact keeps the runtime
  observation, and a static assertion pins the value, with `write-all`, a widened single scope, and
  an absent `permissions` key each mutated.
  **`concurrency` is prohibited at workflow and job level** (codex, r21): a constant concurrency group
  makes GitHub **cancel the in-flight run** when a new one starts, and a cancelled required check is
  not a passing one — a rapid second push would leave the context `cancelled` or pending on the SHA a
  merge is waiting on. Converting the job mapping to an allowlist in revision 21 left the root open,
  which is the same level-above defect one level further out.

  **C1 — one event, and its OPTIONS are an allowlist.** `.github/workflows/trunk-check.yml` is
  `pull_request` **only**, and within that mapping **only `branches:` and `types:`** — no `tags:`,
  no `tags-ignore:`, no `paths:`/`paths-ignore:`, no other option. **`types:` is permitted here
  because C2 REQUIRES it**; revision 21 added that requirement to C2 and left this clause forbidding
  it, so no workflow, registry entry or generated mutant could satisfy both (codex + agy, r21). The
  distinction C1 draws is not "no activity filters" but **no filter that NARROWS reachability** — a
  `types:` set that is a strict superset of the default widens it, and C2 pins the exact set.

  **What the widening does NOT close, stated rather than overclaimed (codex, r24; narrowed r25):**
  GitHub documents exceptions for automated `pull_request` `opened`, `synchronize` and `reopened`
  events, but **an `edited` event raised by `GITHUB_TOKEN` still produces no workflow run** — so an
  **automated** retarget performed by a workflow using that token fires `edited` without producing a
  run, and the required context keeps
  its old same-SHA result. Human, PAT and GitHub-App retargets are covered; that one is not. **No
  workflow in this repository retargets PRs**, so the gap is currently unreachable — it is recorded
  here, and COREDEV-2803 carries it, rather than being papered over by a claim that the hole is
  closed in general.

  **The `push` leg moved OUT of the required context (codex, r20).** Revision 19 emitted the same
  `trunk-check` context for both events, and required checks match on SHA and expected app — *not* on
  the triggering event. So a `main`→`alpha` PR could be satisfied by the **push** run on its head SHA,
  which lints `before..head` rather than the wider `alpha..head` PR range: a green required check over
  a strictly smaller diff. Cell 1 proved each range correct independently and could never prove *which
  run* satisfied the rule. The push leg is now `.github/workflows/trunk-check-push.yml` with job id
  **`trunk-check-push`** — a different context name, deliberately **not required**, kept as a
  post-merge canary. Only a pull request can satisfy `trunk-check`.

  **The canary is a SHIPPED FILE and is governed (sweep).** Revision 20 invented it in this paragraph
  and then left it in no milestone, no §7 inventory entry and under no clause — a workflow the plan
  requires to exist that nothing creates. Its contract is deliberately smaller: `on: push` with
  `branches:` equal to the ruleset's target set, the same SHA-pinned action and checkout as C4/C8/C9
  require, **the empty-diff guard AND the zero-`before` guard, both invoking C6a's SHARED resolver** —
  stated directly, not by reference to the required job, which is `pull_request`-only and carries no
  zero-`before` branch at all. The canary is the only leg that can reach `push.sh`'s `--all` branch, so
  the guard belongs where the hazard is — and it is the leg whose range drift is most expensive, which
  is why it uses the one shared implementation rather than a third independent one (draft check, r27).
  **The canary also carries C5's `env:` prohibition and C6's repository-launcher guard** — cell 16
  demands the C4/C5/C6 execution-integrity controls, and revision 22's "deliberately smaller" list
  omitted them, so the two disagreed about what the canary must satisfy. A shipped, push-triggered
  workflow that runs the pinned action needs them exactly as much as the required one does — and
  **`continue-on-error: true` permanently, AT JOB SCOPE**, so it can never block and nothing is
  tempted to require it later. **`permissions:` is pinned to exactly `contents: read` here as well**
  — the canary is the plan's other shipped workflow, and an invariant that holds only for the required
  one is half an invariant. **Scope is load-bearing and revision 22 left it unstated** (codex,
  r25): a *step*-scoped `continue-on-error` rewrites the Trunk step's reported `conclusion` to
  `success`, leaving only the in-job `outcome` as failure — the same API-visibility trap M2 already
  documents — producing a canary structurally incapable of showing the failure it exists to surface. **Cell 16 asserts it is absent from the ruleset's required contexts** — the
  property that keeps cross-event substitution closed.

  *(The option allowlist above is what revision 19 added after finding the event **names** allowlisted
  and their **mappings** open — `push.tags` beside `branches:`, a force-updated tag carrying a nonzero
  `before`, and Trunk greening a tag range against a SHA that may be a PR head, since required checks
  match on SHA and expected app rather than on the triggering ref type. That hazard now lives entirely
  in the canary's contract, because the required workflow no longer has a `push` event at all.)* **`merge_group` is NOT permitted** — see C7.

  **C2 — branches, and the activity set.** `branches:` present on the workflow's single
  `pull_request` event, equal to the ruleset's target set.

  **`types:` is REQUIRED here, not forbidden — and this reverses revision 19.** `pull_request`'s
  default activity set is `opened, synchronize, reopened`, which **excludes `edited`** — the event
  fired when a PR is **retargeted to a different base**. With the default set, retargeting produces no
  new run, so the required context keeps whatever the previous run reported *against the old base*: a
  green check computed over the wrong diff. So the workflow declares
  **`types: [opened, synchronize, reopened, edited]`** — an explicit *widening*. C1's prohibition is on
  filters that **narrow** reachability; this one is the opposite, and conflating the two would have
  shipped a stale-base pass.
  **No `paths:`/`paths-ignore:`** — path filtering leaves a required context Pending, which blocks.

  **C3 — the JOB mapping is an allowlist, and nothing skips or masks on any step.** The job's own
  keys are `runs-on`, `timeout-minutes`, `permissions`, `steps` — and nothing else, **with
  `permissions:` pinned to exactly `contents: read` here as well as at the root**. GitHub calculates
  the token workflow-level *then* job-level, so a job-level `permissions: write-all` widens the
  effective token while satisfying both allowlists — revision 24 pinned the value at C0 and left the
  key unconstrained here, the same defect one scope down (codex, r25). Mutated at **both** scopes:
  `write-all`, a single widened scope, and the key absent. **This was the
  last level still closed by a blacklist (sweep):** the event mapping, the action's inputs and the
  checkout's inputs were each converted to allowlists across revisions 8-20 while the job mapping kept
  enumerating *prohibited* keys, so a key nobody thought to forbid was permitted by default — the same
  shape, at the one level that had not yet been converted. The prohibitions below remain as the
  named-and-tested cases *within* that allowlist: No `if:` and no `continue-on-error` on the job or on
  **any of the five steps** — revision 12 named only the job and the Trunk step, so `if: false` on a
  *guard* step preserved both the frozen sequence and the frozen body digest while removing the guard
  entirely (codex, r12). No `needs:`; no `strategy.matrix`; **no workflow- or job-level
  `defaults.run`**, which can redirect `shell` or `working-directory` for every step at once. Exactly
  one unconditional Trunk invocation.

  **C4 — the action's `with:` inputs are an allowlist.** Only `arguments` (§6.4's literal),
  `save-annotations` (§6.1), and optionally `cache`/`cache-key`. Everything else absent — notably
  **`trunk-path`** (it names the executed launcher) and **`post-init`** (the action's own docs:
  "caller-controlled escape hatch").

  **C5 — no `env:` at workflow, job OR step scope (agy r8; scope corrected codex r10).**
  Revision 10 named only job and step. **Workflow-level `env:` is inherited by every step in every
  job**, so it reached the action untouched — a `BASH_ENV` there alters every Bash process the action
  spawns. All three scopes — workflow, job and step — or the clause is decorative. The action's scripts read `TRUNK_PATH`,
  `POST_INIT` and friends from the environment, so a `with:` allowlist alone does not constrain them:
  `env: {TRUNK_PATH: /bin/true}` satisfies every input rule and redirects execution to a binary that
  exits 0. Forbidding `env:` outright at **all three scopes** closes it without depending on the
  precedence between job `env:` and `GITHUB_ENV`.

  **C6 — the REPOSITORY may not supply the tool that tests it (codex, r8).** Verified at the pinned
  SHA: `setup/locate_trunk.sh` uses a checked-out `.trunk/bin/trunk`, `tools/trunk` or `./trunk` in
  preference to downloading, and `action.yaml:289` *executes* a checked-out `.trunk/setup-ci` as a
  composite action, which can rewrite `TRUNK_PATH` through `GITHUB_ENV`. A PR adding any of those
  greens its own required gate. **The job therefore carries a guard step, immediately before the
  action, that fails if any of those four paths exists in the checked-out tree** — and that also
  fails on the presence of **`.trunk/user.yaml`** or **`.trunk/env.yaml`**, which override the
  configuration cell 4 freezes (both arms, r9).

  **C8 — the job's step sequence is an allowlist, in order.** Exactly: `actions/checkout` (SHA-pinned)
  → **the C6a resolver-digest guard** → the empty-diff guard (cell 1) → **the C6 launcher-path guard**
  → the action. No other step may exist. The two guards are separate because their correct positions
  differ: C6a's must precede the step that *executes* the resolver, and C6's must be the last thing
  before the action so nothing can create a launcher path behind its back.

  **The order matters and revision 10 had it wrong (codex, r10).** C6 requires its guard *immediately*
  before the action; revision 10's C8 placed the empty-diff guard between the two, so a permitted,
  already-allowlisted step sat where it could create `tools/trunk` or `.trunk/setup-ci` **after** the
  guard had passed. The two clauses contradicted each other, and the "extra step" and "moved guard"
  mutants killed neither — the mutation lives *inside* a step the sequence allows. C6's guard is
  therefore last before the action, and cell 11 mutates the intervening step's body explicitly.

  **`actions/checkout`'s own inputs are allowlisted too.** Freezing its identity and SHA is not
  enough (codex, r10): it accepts `ref`, `repository`, `path`, `filter` and `sparse-checkout`, and a
  well-meaning sparse-checkout optimisation can leave changed files **absent from disk** while git
  metadata still yields a non-empty range — so the empty-diff guard passes and Trunk lints files that
  are not there. That is an *accident*, squarely inside §0's threat model. The permitted set is
  **`fetch-depth` (optional), `lfs: true` (required), and `persist-credentials: false` (required)**;
  every other input must be absent.

  **`persist-credentials: false` is required, and revision 20 forbade it (sweep).** `actions/checkout`
  persists the job's credential by default — **in `.git/config` below v6, and in `$RUNNER_TEMP` from
  v6** (codex, r21: revision 21 stated the storage location categorically while the plan pins no
  checkout generation). Either way it persists, and either way zizmor's **`artipacked`** rule reports
  it unless later steps genuinely need the credential — which none of these five steps do. C9's SHA
  pin fixes the generation, so the storage detail is determined at implementation and recorded there
  rather than asserted here — and zizmor is one of the **19 linters this gate itself requires**,
  running under the `auditor` persona. So revision 20's allowlist would have produced a workflow that
  **fails the gate it defines**, with the only in-workflow remedy prohibited. `.github/zizmor.yml` is
  deliberately empty of ignores and documents suppression as the last resort; setting the input is the
  first. It is a hardening, so requiring it costs nothing.

  **`lfs` is required, not merely permitted (codex, r13).** `actions/checkout` defaults it to
  `false`, so a PR that legitimately introduces `.gitattributes` with an LFS-tracked source checks out
  the **pointer file** rather than its content: the diff stays non-empty, the guard passes, and Trunk
  lints a 130-byte pointer and reports green. That is an accident, not an attack — squarely §0's
  threat model — and it is the one checkout input whose *default* is the hazard.

  **And the two permitted `run:` steps are frozen BY CONTENT, not merely by position (codex, r11).**
  Freezing the sequence stopped a *new* step being added; it did nothing about what the allowed steps
  *do*. Either may write `TRUNK_PATH=/bin/true` or `BASH_ENV=…` to `$GITHUB_ENV`, and the C6 guard
  inspects paths, not inherited runner state — so the action would resolve a no-op launcher while
  every clause C0–C9 passed. **Each run body is pinned by digest, and neither may write to
  `$GITHUB_ENV` or `$GITHUB_PATH` at all.** And it is the **complete step mapping** that is frozen,
  not the `run:` body alone (codex, r12): `shell`, `working-directory`, `if`, `continue-on-error`,
  `env` and every other key on each of the five steps, so a step cannot be neutralised by a sibling
  key while its body hashes unchanged. Changing either step is then a reviewed change, which is
  the same standing the workflow itself has. Revision 9
  banned `env:` but nothing stopped an *extra step* from appending to `GITHUB_PATH`, setting
  `BASH_ENV` through `GITHUB_ENV`, or creating one of C6's prohibited paths **after** the guard had
  already run (codex, r9). Freezing the sequence closes the ordering hole and the injection hole
  together; the guard's adjacency to the action is part of the assertion, not a convention.

  **C9 — the action itself is pinned by exact SHA.** `trunk-io/trunk-action@e1234e67…` — nothing in
  C1–C8 required it, and cell 9 asserted only that `actions/checkout` was pinned, so a tag or a
  different SHA satisfied every other clause (codex, r9).

  **C6a — the shared range resolver is REPOSITORY-SUPPLIED, and is governed like one.**
  `scripts/ci/resolve-trunk-range.sh` lives in the checked-out tree, so C8's run-body digest **cannot**
  reach it: a `run:` body that invokes the script hashes identically whatever the script contains, and
  moving the guard's substance there would re-open exactly the hole C8 exists to close — on C6's own
  premise that *the repository may not supply the tool that tests it*. A PR could edit the resolver so
  the empty-diff guard passes on a range the action never lints, which is inherited defect 3 wearing a
  new file name. **The script is therefore its own `content_digest` registry entry**, pinned by
  digest, with its own mutation case (edit the resolver, expect red) and its own diagnostic — and the
  digest is verified **before the step that EXECUTES the script**, which is not the same place as C6's
  launcher guard.

  **This needs two guard steps, and the plan had one** (regression check, r28). C6's guard must be
  **last** before the action, so nothing can create a prohibited launcher path after it has looked
  (r10). But the resolver is executed by the **empty-diff guard**, which C8 orders *earlier* — so a
  single guard placed before the action verifies the resolver's digest only after the resolver has
  already run. Under §0's threat model that still fails closed (the C6 guard reds the job and the
  action never runs), but "verify, then execute" is the property C6a exists for, and executing an
  edited script first is not it. **C8's sequence therefore becomes five steps:** `actions/checkout` →
  **the C6a resolver-digest guard** → the empty-diff guard → **the C6 launcher-path guard** → the
  action.

  **C7 — a merge queue is a STOP, not a configuration (codex, r8).** Revision 8 let M4 add
  `merge_group` if the preflight found a queue. At the pinned SHA that is the forbidden false
  success: `determine_check_mode.sh` matches `merge_group` in **no** branch, so it falls through to
  `check_mode=none`, every real step is skipped, and the composite action **succeeds** — and C4
  forbids forcing `check-mode` to repair it. So if M4's preflight finds a merge queue on `Control`,
  **stop and redesign** — a compatible action revision, or an explicitly validated mode, chosen and
  tested before the context is required. Never add the trigger and hope.

  **Residual risks, named rather than implied.** *(c)* **Twin-targeting one head at both bases.**
  Required checks match on **SHA + expected app**, not on the triggering event — which is the fact
  that forced push↔PR substitution closed, by giving the canary a different context name. The same mechanism survives
  *within* `pull_request`: if one branch is ever PR'd to `main` **and** `alpha` simultaneously, both
  runs post a check named `trunk-check` onto the same head SHA and the ruleset evaluates the latest, so
  a `main` PR can be satisfied by the run that linted the `alpha..head` range. Both are real Trunk
  runs, so this is a **wrong range**, never an absent lint, and post-M0 the two ranges are nearly
  identical — but it is exactly Q1's envelope, and no edit ever touched it, so twenty-nine rounds of
  diff-reading could not surface it (kimi, third lens). **The rule: never twin-target one head at both
  bases.** This repo's promotion flow is feature→`alpha`, then `alpha`→`main`, where the heads differ,
  so the rule costs nothing here. *(a)* This contract enumerates the extension points
  that exist **at the pinned SHA**; a future version may add another, so a Dependabot pin bump must
  re-run cell 11's mutants rather than being merged as routine — **and must RE-DERIVE the enumeration
  itself, which re-running mutants does not do** (kimi, third lens). C4, C5 and C6's extension-point
  list was obtained by reading the action's source *at the pinned SHA*; a new revision can add an
  input, a launcher-search path, or another `uses:` of a checked-out file, and the existing mutants
  would all still pass while the new door stood open. *(b)* For `pull_request` events the
  workflow file itself comes from the PR, so a same-repo PR can edit the gate — inherent to Actions
  gating, mitigated by review/CODEOWNERS on `.github/`, and **out of scope here** but real.
* **`arguments:` is GOVERNED, and its value is DECLARED (agy r3; corrected codex r5).** Verified at
  the pinned SHA: `INPUT_ARGUMENTS` is word-split into the `trunk check` command line in **both**
  `pull_request.sh` and `push.sh`, so §6.4's exclusion necessarily travels through this input.
  Revision 5 governed the input but left two holes codex found: it permitted `arguments:` to be
  **absent**, which after §6.4 was decided is no longer an authorised implementation (absent means
  `markdown-link-check` *runs* in the required job); and §6.4 never declared the literal bytes cell 9
  was told to match, so **the cell could not be executed as written**.

  **The contract:** `arguments:` **must be present and must equal §6.4's declared literal** — whose
  bytes are stated *only* in §6.4, so this section does not restate them (a derived value written
  twice goes stale, and two stale copies agree with each other). Asserted by cell 9 as a whole-string
  match — never a substring or a "contains `--filter`" test, both of which an appended argument would
  still satisfy. **Absence is a failure**, not a permitted variant.
* **Stable job + context name** — `trunk-check`, so the ruleset context is nameable and cannot drift.
  Runner `ubuntu-latest`, and **`timeout-minutes: 15`** — a concrete ceiling, stated here in the
  contract rather than only in the cell that asserts it. "Explicit `timeout-minutes`" alone is
  satisfied by GitHub's own 360-minute default, which changes nothing.
* **No autofix.** `trunk fmt` / `trunk-fmt-pre-commit` stays disabled, per COREDEV-2771.
* **Linter-set contract — NO *UNDECLARED* FILTER.** See §1's exclusion rule immediately below.

### The linter-set rule, restated to remove revision 2's contradiction (codex, r2)

Revision 2 said "no `--filter`" in §1 while §6.4 recommended splitting `markdown-link-check` out —
**and that linter is in the enabled set, so the two could not both hold.** codex caught it; revision 2
recommended two mutually exclusive things.

The rule that survives: **no *undeclared* filter.** A silent reduction to one linter is the hazard;
a declared, justified, cell-enforced exclusion is not the same thing.

**How cell 4 enforces it — NOT "the configured set minus the exclusions".** That revision-5
formulation stood here as normative §1 text long after cell 4 identified it as the defect and replaced
it: reading the expectation out of `.trunk/trunk.yaml` makes a **silently reduced configuration
authoritative over the assertion meant to detect it**, which is the primary hazard this ticket exists
to close. §1 is the declared authority, so an implementer following this paragraph built exactly the
blind oracle. Cell 4 instead carries **the 19 expected linter names as frozen literals plus a digest
over the `lint:` block with version specifiers normalised out**, and fails if a name is missing, an
unlisted linter appears, the exclusion list grows, or the block changes other than by a version pin.

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
at `test_transcript_path_inventory.py:342` (`quote_keep_sites = {_site_key(site) …}`) and the
fixed-line hash check at **`:358`** (`_sha256(lines[site["line"] - 1]) != site["sourceSha256"]`).
**Cited by content, with the line as a hint** — `:355` is the enclosing `class == "quote-keep"` guard,
not the hash, and this plan carried that wrong pin from revision 2 through the gate. Line pins rot;
that is COREDEV-2798's entire thesis, one section above.

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
against dead code. **The callers are `.githooks/pre-commit` and the project `SessionStart` hook** —
revision 7 added the second surface below while this sentence still named one, and §6.3 repeated the
single-caller claim (codex, r7).

**Why that one, and why it survives the bootstrap problem.** A session bound to 2.7.0 cannot execute
a detector shipped only in 2.8.4+. The hook is not shipped by the plugin — it lives in the
**checkout** and runs from it, so it is current regardless of which install a session loaded. It
compares `~/.claude/plugins/installed_plugins.json` against
**`.claude-plugin/plugin.json` as of `origin/main`**, needing no session environment and no plugin
code.

**Both surfaces read `origin/main`, and revision 21 propagated that to Table A only** (codex, r21).
Earlier revisions had pre-commit read the *staged* manifest and `SessionStart` the *worktree*; both
are wrong for the same reason Table A now states — the working tree and the index are where the
version-bump rule *raises* the version, so either would warn on the healthy state for a whole
branch's life. **The detector therefore has NO mode operand at all** (codex, r24). Revision 22 kept
one and redefined it as selecting "which installs to report on" without ever defining that mapping;
revision 23 deleted one site of the old semantics and left two more standing. There is nothing for a
mode to select — both surfaces compare the *same* installed record against the *same* `origin/main`
manifest, and differ only in **when they fire**. The operand is removed. *(Not to be confused with
trunk's `--index` in cell 13, which is a different flag on a different tool and is unaffected.)*

**`origin/main` is a local bookmark — a STATED LIMITATION, not a mechanism.** It is only as current
as the last `git fetch`, so a stale bookmark makes the detector under-report: it will miss a release
newer than the last fetch. Revision 22 tried to answer this by "recording the bookmark's age with
every run", which was **not implementable** — it defined no age, source, threshold or consequence —
and **contradicted Table A's rule that silent rows emit and record nothing** (codex, r23). Both are
withdrawn. The detector does **not** fetch (a read-only detector reaching the network on every
session start or commit would be a worse defect than the drift it reports), and it does **not**
record. Its failure mode is therefore **under-reporting on a stale clone, never a false positive** —
which is the correct direction for a non-blocking advisory, and is recorded here as an accepted
limit rather than dressed up as a control.

**Reachability is a PRECONDITION, not a property (codex, r3)** — *for the pre-commit surface*; the
`SessionStart` surface has its own, different preconditions, recorded in the alternatives table
(codex, r11). The **pre-commit hook** runs only where
`git config core.hooksPath .githooks` has been set — a **manual, per-clone** step documented at
`CLAUDE.md:78`, not a repo-wide setting; it is set in the working clone today and unset in any fresh
one. Revision 3 also called these "two files it can always read", which **its own unreadable-state
row contradicts**; that claim is withdrawn.

**Two tables, because revision 6 conflated two different things** (agy, r6). One maps the *one-time
§3a experiment* to what it establishes; the other maps a *runtime comparison* to what the detector
does. Revision 6's single table had "both entries advance and stay advanced → **warn**", which under
its own directionality rule is a false positive: if every entry equals the expected version there is
nothing to warn about.

**Both tables are ORDERED: the first matching row wins.** Revisions 6 and 7 tried to make the rows
disjoint by wording and failed twice — codex and agy each found pairs that matched simultaneously and
inputs that matched nothing. Ordering makes exclusivity **structural** rather than asserted, and a
final catch-all makes exhaustiveness structural too.

**Table A — the detector at runtime.** Evaluated per scope entry. **`expected` is
`.claude-plugin/plugin.json` as of `origin/main` — NOT the working tree (sweep).** The working tree is
where the version-bump rule *raises* the version, so it sits one bump **ahead** of anything a consumer
can pull for the whole life of a feature branch: reading it would make row 7 warn on every developer's
machine, every session, after every bump — a false positive on the healthy state, which is exactly the
"red by default, so people stop reading it" trap §1 rejects for CI. What the detector is *for* is an
install lagging what is **published**, so it compares against the published manifest.

| # | condition | detector |
|---|---|---|
| 1 | `expected` cannot be read, or the manifest is malformed | **silent** — with no expected value there is nothing to compare against (codex, r7) |
| 2 | the record is unreadable, or its schema is unrecognised | **silent** |
| 3 | the entry is absent | **silent** |
| 4 | either version is present but **not comparable** | **silent** — revision 7 assumed comparability and left this unassigned (codex, r7). **Comparable means parseable under SemVer 2.0.0**, and rows 6–8 order by its precedence rules (agy, r8) |
| 5 | the versions are of **equal precedence but not identical** — SemVer ignores build metadata, so `2.8.3+local` and `2.8.3+repo` are neither `<` nor `>` nor the same string | **silent**. Revision 9 called row 5 "exact version" while ordering by precedence, so this pair reached the `> expected` catch-all whose description was false of it (codex, r9). `==` in rows 6–8 means **exact identity**; equal-precedence-but-different is handled here |
| 6 | `installed == expected` | **silent** — the healthy state is not a warning |
| 7 | `installed < expected` | **warn** — the drift this detector exists for |
| 8 | otherwise (`installed > expected`) | **silent** — a locally newer install is not drift; warning here fires on every development clone |

The hook warns if **any** entry reaches row 7, and never blocks. **Silent means silent: it emits
nothing at all, and records nothing** (codex, r18). Revision 17's rows promised to "record the
observed shape" while cell 8 required silent rows to produce *no output* — a contradiction a detector
could satisfy by exiting quietly and recording nothing, passing every cell while violating the table.
Recording belongs to **Table B**, the one-time §3a experiment, whose observations are written to the
evidence artifact by a human-run measurement. The per-session detector has no sink and needs none.

**Table B — what the §3a experiment establishes.** The experiment runs `claude plugin update` at
**user scope** and re-reads the record; `u` and `p` are the user and project entries.

| # | condition | establishes |
|---|---|---|
| 1 | the command exits **nonzero** | **update-failure** — first, so a partial mutation followed by a failure is never read as success. Containment **not** established |
| 2 | **any of the three versions — `u`, `p` or `expected` — is unreadable, absent, malformed or not comparable, in EITHER the before or the after observation**; or the record's schema is unrecognised | **no outcome**; record the observed shape. Three widenings, each from a round that found the previous wording too narrow: "either entry" rather than "a targeted entry" (codex, r8); **`expected` itself**, which Table A row 1 covers and Table B did not, so an unreadable manifest left every later comparison unevaluable with no row owning it; and **the before observation**, so a `u` that was absent or malformed pre-update and is merely below `expected` after is not forced into "moved upward" or "did not move", neither of which is true of it (both codex, r15) |
| 3 | **`expected` differs between the before and after observations** | **no outcome**; the experiment compared against a moving target. Row 2 covers `expected` being *unreadable*; it said nothing about `expected` legitimately **changing** during the interval (codex, r19) — a release landing mid-experiment left `u = p = 2.8.3` against a new `expected = 2.8.4` reaching the final row and reporting that the update "did not act on the scope it targeted", when the install had matched the target at the moment the command ran. The alternative is to freeze `expected` for the run's duration and assert it unchanged; this row states the outcome when that assertion fails |
| 4 | the persistence interval has not elapsed | **PENDING — not an outcome.** No later row may be claimed yet |
| 5 | **`p` changed at all** — either direction, whether or not `u` moved | **the update acted on a scope it did not target.** Evaluated before the reversion row because a *downward* move in `p` is both, and revision 9's ordering recorded it only as a reversion, losing the untargeted-scope signal (codex, r9; the row it then collided with was **revision 7's** row 5, not this table's — codex, r11). Record both facts; classify here |
| 6 | any entry moved **downward** from a previously observed value | **reversion — the root-cause signal.** COREDEV-2801 stays open with the detector as its instrument. Covers reversion to *any* lower version, not only `2.7.0`, and by ordering it can no longer collide with row 5 as it did in revision 7 |
| 7 | any entry is `> expected` | **not drift**; the run is non-evidence rather than a result |
| 8 | `u` changed to a version of **equal precedence but different identity** (`2.8.2+old` → `2.8.2+new`) **and `u != expected`** | **no outcome**; record. It moved, so the final row's "did not move" is false of it; it did not advance, so no advance row is true either. Revision 10 left this input matching **nothing** (codex, r10), the mirror of Table A's row 5. The
`u != expected` qualifier is load-bearing: without it the row **stole a genuine containment result**
— if `expected` itself carries build metadata, `u` arriving exactly at it is an equal-precedence
identity change *and* a success, and row 8 would have reported "no outcome" (codex, r11) |
| 9 | `u == expected` and `p == expected` | containment established for both, though the experiment aimed at one |
| 10 | `u == expected` and `p < expected` | the **expected shape**, since only user scope was updated. Containment established **for user scope only** |
| 11 | `u` moved **upward** but is still `< expected` | **partial advance** — it changed without arriving. Containment **not** established. *Upward* is explicit: revision 7 classified a downward move as a partial advance (codex, r7) |
| 12 | **either `u` or `p` is of equal precedence to `expected` but not identical to it** (`expected = 2.8.3+repo`, entry `2.8.3+local`) | **no outcome**; record. Table A row 5 classifies this for the *detector*; revision 12 gave Table B no equivalent, so an unchanged `u = 2.8.3+local` fell through to the final row, whose "`u < expected`" is false of it (codex, r12). Row 8 covers an identity change *relative to the previous value*; this one covers the relationship *to `expected`* — different questions |
| 13 | otherwise — `u` is `< expected` and did not move, `p` unchanged | the update **did not act on the scope it targeted**. Containment **not** established. Reachable only after rows 1–12, so its description is true of everything that reaches it |

**The terms both tables depend on** (codex + agy, r5 and r6 — earlier versions were neither
exhaustive nor mutually exclusive):

* **"advance"** means the entry equals **the exact version expected** — not merely "changed", and
  not "greater". "Moved but short of expected" is its own outcome, not an advance.
* **Comparison is directional**, per Table A: below expected is drift, above it is not.
* **The command's exit code outranks the record** — the first row of Table B, evaluated before any
  entry is compared.
* **Persistence needs a named interval**, recorded with the run; before it elapses the result is
  *pending*, which is why Table B carries an explicit interim row rather than leaving a gap.
* The **record's readability and schema** are what Table A row 2 and Table B row 2 classify on. They
  are *observed*, not *recorded*: the runtime detector "emits nothing at all, and records nothing"
  (§3b), so only **Table B's one-time experiment** writes anything down, into the evidence artifact.
  Revision 18 withdrew the per-run recording promise and this bullet kept it — the same contradiction
  codex found at the rows, surviving at the terms list (draft check, r27).

It **never blocks a commit.** A version-drift detector that fails `git commit` would be a worse
defect than the one it reports.

**§6.3 is DECIDED — wire the hook — so this caller stands and M6 is unconditional.** The reasoning
below is retained as the record of a rejected §6.3 branch, **not** as a claim that no alternative
caller exists — one does, and revision 7 adopted it as a second surface rather than a substitute:

* **§6.3 = wire the hook** *(the decision)* → §3b is built as described, caller
  `.githooks/pre-commit`.
* **§6.3 = CI-only** *(rejected)* → §3b would have been **dropped** entirely, COREDEV-2801 keeping
  the §3a diagnostic alone.

**Alternatives compared, not dismissed (codex, r5).** Revision 5 claimed git hooks were **"the only
mechanism"** meeting both constraints — run **from the checkout** (the bootstrap constraint) and read
**local machine state** (`~/.claude/plugins/installed_plugins.json`). **That claim is false**, and
asserting impossibility where a comparison was owed is itself the defect, even though the conclusion
survives:

| candidate | from the checkout? | reads local state? | fires when | disablement / bypass |
|---|---|---|---|---|
| `.githooks/pre-commit` | yes | yes | a commit is made | needs a manual per-clone `core.hooksPath`; an executable hook; and **`git commit --no-verify` bypasses it outright** |
| project `.claude/settings.json` `SessionStart` hook | **yes** — committed config, command runs from the tree | **yes** | **a session starts** | inert under `disableAllHooks`, under an untrusted project, or under managed `allowManagedHooksOnly` |
| a CI job | yes | **no** — a runner has no developer install record | — | eliminated |
| a plugin-shipped hook | **no** — a 2.7.0-pinned session runs 2.7.0's copy | yes | — | eliminated: it *is* the defect |

**Both surviving candidates are advisory, not enforceable.** Revision 6 recorded only the
`SessionStart` candidate's trust cost while presenting `pre-commit` as the sound choice; codex r6
noted the asymmetry — a pre-commit hook is skippable with `--no-verify` and needs a manual
`core.hooksPath`. Neither is a policy boundary; both are local conveniences, and the plan says so.

**Use BOTH, because they fire at different moments and the defect lives at the other one (agy, r6).**
COREDEV-2801's actual failure is a **stale install running in an active session** — and `pre-commit`
only fires when someone commits, which may be hours or days into that session, or never. The
`SessionStart` hook fires *when the stale code begins running*, which is the moment the defect
exists. The detector is read-only, non-blocking and cheap, so it is wired to **both** surfaces:

* **`SessionStart`** — catches the live stale session, the defect as actually reported. **Its
  contract, specified rather than gestured at** (codex r7 and r8; agy r8):
  * **Paths** — both the hook entry in `.claude/settings.json` and the script it names are resolved
    through **`${CLAUDE_PROJECT_DIR}`**; hooks run in the *current* directory, not necessarily the
    project root.
  * **Matchers** — `startup` and `resume` **only**. `SessionStart` can also fire on `clear`,
    `compact` and `fork`; a drift warning repeated on every compaction is its own alert-fatigue
    defect, and the install cannot change mid-session, so the extra sources add noise and no signal.
  * **Deduplication** — **at most one warning per session per retention window**, with the literals
    declared rather than gestured at (codex, r9). The window qualifier is not pedantry: "one warning
    per session" and an unconditional sweep are **jointly impossible** (codex, r11) — a session
    resumed after the retention period finds its marker swept and warns a second time, and a
    concurrent session can sweep a live session's marker. Markers cannot be retained forever, so the
    promise is stated as what the mechanism can actually deliver. Cell 8 exercises the aged-marker
    resumption case, not only the concurrent-create case. The `session_id` arrives in the hook's JSON stdin. The marker is
    `${XDG_STATE_HOME:-$HOME/.local/state}/unleashed-mail/drift-warned/<sha256(session_id)>.<window>`
    — **time-bucketed and hashed**, for two reasons codex found in r13. *Bucketed*: revision 13 swept
    aged markers by unlinking them, which races with itself — two invocations of the same session both
    stat an aged marker, A unlinks and recreates it, B's already-decided unlink removes A's *fresh*
    marker, and B's `O_EXCL` create then succeeds, so both warn in the same new window. Encoding the
    window in the **name** means a live marker is never unlinked at all: the sweep removes only buckets
    strictly older than the current one, and the decision is a single `O_EXCL` create with no
    unlink-then-create sequence to lose.

    **`window` is `floor(unix_time / 604800)`** — fixed seven-day buckets from the epoch, declared
    because revision 14 named the field without defining it, and *daily* buckets under a seven-day
    cleanup would have passed every stated test while warning the same session **every day**
    (codex, r14). Cleanup removes markers whose window is strictly less than the current one.
    **Accepted boundary behaviour, stated rather than discovered later:** a session live across a
    bucket boundary may warn twice, seconds apart. That is the honest reading of "at most one warning
    per session per retention window", and the alternative — a rolling window anchored on the marker's
    own creation — reintroduces the unlink-then-create race this design exists to remove. Cell 8 tests
    repeated invocation *within* a bucket (one warning) and *across* a boundary at well under seven
    elapsed days (a second warning, expected). *Hashed*: `session_id` is documented as an opaque identifier
    with **no filename-safety contract**, so using it raw makes marker creation fail on a `/` or an
    over-long component — and this dedup fails **open**, warning on every invocation. — **not**
    `${CLAUDE_PLUGIN_DATA}`, which revision 10 used and which is scoped to *plugin*-associated hooks
    while this hook deliberately lives in project `.claude/settings.json` (codex, r10). The chosen
    path needs no plugin identity and matches the convention this repo already uses for review
    transcripts. It is created with `O_EXCL` **before** the warning is
    emitted, so two concurrent invocations cannot both warn and a crash between create and emit fails
    silent rather than warning twice. **Cleanup removes markers from any PRIOR window**, which is not the
    same statement as "older than 7 days" (codex, r17): just after a bucket boundary a marker seconds
    old belongs to the previous window and is swept. The window-comparison form is the implementable
    one; the age phrasing described a mechanism this design deliberately does not use.
  * **Output protocol** — the warning is emitted as **`{"systemMessage": "…"}`**, not bare stdout
    (agy, r8). A `SessionStart` hook's plain stdout is injected into the **agent's context**, so a
    warning printed that way is read by the model and never seen by the developer — a detector whose
    output only the assistant can see does not warn anyone.
  * **Timeout** — **`timeout: 5`** (seconds), declared on the hook entry. The default for a
    synchronous command hook is **600 seconds**, and a detector that can hang a session start for ten
    minutes is worse than the drift it reports. Five seconds is ~100x the detector's work (two small
    JSON reads); anything slower than that is a broken detector, and failing fast is the right answer.

  Cell 8 exercises the matcher set, the timeout against a sleeping detector, the dedup marker under
  concurrent invocation, and the `systemMessage` shape;
* **`.githooks/pre-commit`** — fires at commit time, and covers the case
  where hooks are disabled in the session but not in git.

**M6 is unconditional** because §6.3 is decided, not because no alternative existed — and the
alternative turned out to be complementary rather than competing.

## §4 — Milestones

- [ ] **M0** — *(decided, §6.0; refined in r3)* bring `alpha` up to date with `main` (611 commits,
      0 ahead). **This alone lands the trunk configuration on `alpha`**, because `.trunk/trunk.yaml`
      is already present on `origin/main` — verified. COREDEV-2771's separate-PR requirement is still
      met: the config arrives on the sync PR, which is not the PR that adds the job. Revision 3's
      second step was therefore redundant work on an already-satisfied precondition.
- [ ] **M0a** (**before M2 — required files that no milestone created**) — write
      `docs/planning/COREDEV-2780-contract.yaml` (the typed, case-bearing registry §1's clauses are
      rendered from and cell 11's mutants generated from) and
      `docs/planning/COREDEV-2780-survivors.yaml` (the independently-maintained survivor corpus). Cell
      11 and cell 15 cannot be written before these exist, and §7 required both while §4 scheduled
      neither.
- [ ] **M1** (independent of M0/M2) — COREDEV-2798 class-specific content-addressing, anchors
      demoted, `:342`/`:358` updated, cells 6–7 with negative controls.
- [ ] **M2** (**after M0**) — create **`scripts/ci/resolve-trunk-range.sh`** (C6a's shared resolver,
      which the guard invokes from the moment the workflow exists) and add the `trunk-check` job,
      diff-scoped, `continue-on-error: true` **at job scope**, in
      its **own workflow file** `.github/workflows/trunk-check.yml`, satisfying **every clause of
      §1's contract, C0 through C9 and C6a — except C3's `continue-on-error` prohibition, which M2 is
      deliberately and temporarily exempt from **at JOB scope only**. Step-scoped would make cell 2's
      M2 half unobservable (codex, r19): a step-level `continue-on-error` turns the step's *reported*
      `conclusion` into `success` while only the in-job `steps` context still shows
      `outcome: failure`, and C8 leaves no later step to report it — so nothing the REST API exposes
      could carry the claim. At job scope the Trunk step's `conclusion` stays `failure` in the
      workflow-jobs record, which the evidence artifact can bind to** (codex, r10: M2 ships `continue-on-error: true` while
      C3 forbids that exact key, so an unqualified "every clause" contradicted the milestone it
      described). The exemption ends at M3, where cell 11's C3 mutants are enabled. This list deliberately does **not** restate their values
      (codex, r9): revision 9 claimed the contract was stated once and then copied it into M2 and §7,
      which is how the trigger set diverged in the first place. §1 is the authority; cell 11 is the
      enforcement. Read them, do not paraphrase them.
- [ ] **M2a** (**after M2 — the step revision 3 was missing entirely, codex r3**) — land the job on
      `alpha` too, **and `scripts/ci/resolve-trunk-range.sh` with it**: the resolver is created "with
      M2" on `main`, and a literal or interrupted cherry-pick could otherwise place a workflow on
      `alpha` whose guard invokes a script that is not there (codex, r28). C6a's digest check and cell
      12 would block progression to M4, but the landing should not depend on a later gate to catch it. GitHub runs the workflow **version present at the event's ref**, so a job merged
      only to `main` never executes for an `alpha` PR: `alpha` would carry the config but emit no
      `trunk-check` check run. Requiring the context at M4 would then make it **unsatisfiable on
      `alpha`** — COREDEV-2767's exact failure, aimed at the other protected base.
- [ ] **M2b** (**with M2 — the file revision 20 required and never scheduled, sweep**) — create
      `.github/workflows/trunk-check-push.yml`: the non-required `trunk-check-push` canary, `on: push`
      satisfying **C1's canary contract in full** — `on: push` with the ruleset's branches, the
      C4/C8/C9 action and checkout pins, **C5's `env:` prohibition, C6's repository-launcher guard**,
      `permissions: contents: read`, the empty-diff and zero-`before` guards **both invoking C6a's
      shared resolver**, and `continue-on-error: true` permanently **at job scope**. This milestone is
      the build instruction, and it previously omitted the C5/C6 execution-integrity controls that C1
      requires and cell 16 asserts — so following it shipped a canary the cell believed was governed. Land it on both bases alongside M2a. Cell 16 asserts it **is not required at rollout** — not
      "never", which the cell explicitly declines to claim from a point-in-time ruleset read (codex,
      r25).
- [ ] **M2c** (**with M2 — required by §7 and by cells 1 and 5, and scheduled by nothing**) — create
      `.github/workflows/trunk-parity-harness.yml`, the **non-required** sensor that runs the pinned
      action against per-event fixtures with an instrumented launcher and publishes the captured argv
      and post-run tree hashes as an artifact. Cells 1 and 5 are unownable without it.

      **Its trigger must produce the EVENTS it measures** (codex, r27). Revision 26 made it
      `workflow_dispatch`-only, which is self-defeating: the pinned action maps `workflow_dispatch` to
      **`check-mode=all`** — the very reason dispatch is banned from `trunk-check` — and
      `GITHUB_EVENT_NAME` cannot be overridden, since GitHub forbids overriding `GITHUB_*` variables.
      Naming an artifact `parity-pull_request.json` does not make the action take its PR path, so the
      harness could never produce cell 1's PR/push ranges nor exercise the mode cell 5 assesses.
      **It therefore fires on REAL events, on dedicated fixture refs**: `pull_request` with
      `branches: [harness-base]`, and `push` with `branches: ['harness/**']`. Filters are safe here
      precisely because it is **non-required** — a skipped harness leaves no context pending. It is
      invoked at M2c and again before M4. **`harness-base` and `harness/**` are permanent repository
      citizens, not scratch refs** — they are needed again at every Dependabot pin bump to re-derive
      the extension-point enumeration, so they are documented in `CLAUDE.md` beside the gate list, and
      deleting them is a change rather than tidying (kimi, third lens). It writes
      `parity-<event>.json` with the captured argv, the resolved range and the
      pre/post tree hashes; and the milestone **accepts the artifact against that schema** before the
      cells that own it may be marked done.
- [ ] **M3** — remove `continue-on-error` **on `main` and on `alpha`**. **Cell 11's C3 assertion
      lands HERE, not at M2** (codex, r8): M2 deliberately ships `continue-on-error: true` while C3
      forbids it, so asserting C3 at M2 would make the suite intentionally red. The cell is written
      at M2 and enabled at M3, with M2's advisory window explicitly exempted. — revision 5 said only
      "remove `continue-on-error`" while M2a had landed the *advisory* job on `alpha`, so the second
      base would have stayed advisory forever and cell 12 would have blocked M4 rather than
      completing the rollout (codex, r5). Then observe **one genuinely strict green run and one
      deliberately red run on each base**. *Revision 1 would have promoted a context observed only while failures
      were suppressed — one that had never been able to fail.*
- [ ] **M4** — add the required context to ruleset `Control`, **only after M3's red runs on both
      bases**, and only with explicit maintainer instruction (§6.2). **This gates `main` AND `alpha`
      simultaneously** — `Control` targets both — so the context must be satisfiable on both, which
      **M0 + M2a + M3 together** make true; no one of them suffices. **Evidence required on BOTH
      bases**: one strict green and one deliberately red `trunk-check` run on a `main` PR *and* on an
      `alpha` PR, each bound to its workflow path, **effective check name** (not the YAML job id —
      agy, r7), head SHA and conclusion (cell 12). An
      unobserved base is an unsatisfiable-context risk, not an assumption.

      **Constrain the SOURCE, not just the name (codex, r6).** A required status check matched by
      name alone can be satisfied by *anything* with write access posting that context. The rule must
      pin the expected integration (GitHub Actions) via the ruleset's `integration_id` — a real,
      applicable field on required-status-check rules. **Obtain the integer rather than guessing it**
      (codex, r7): read `app.id` from the *same* provenance-checked check run cell 12 observed,
      confirm that app is GitHub Actions, write that integer, then **read the rule back and compare**.
      Cell 14's census governs this repo's workflows; it cannot govern what the *rule* accepts.

      **Preflight two conditions the four internal-PR observations never exercise.** First, whether
      `Control` requires a **merge queue**: if it does, **M4 STOPS** — per §1's C7, adding
      `merge_group` at the pinned SHA yields `check_mode=none`, a skipped-but-successful action, and
      the precise false pass this plan exists to prevent; and without the trigger the context is
      permanently pending in the queue. Either outcome is a redesign, not a configuration tweak.
      Second, the repository's **fork-approval policy**, since a fork PR awaiting approval produces no
      completed context.

      **Re-verify BEFORE and AFTER the ruleset edit** — "immediately before" alone is a read/edit
      race. The two reads check different things, because **one value is supposed to change: adding
      `trunk-check` IS the edit.** Revision 24 required all five to be identical across both reads,
      which meant either the pre-read failed or every successful edit was rolled back — a checklist
      that could not pass (codex, r25).

      **Must be UNCHANGED across both reads** — roll back if any differs:
      1. both base tips still carry a byte-equivalent strict job;
      2. the effective check name;
      3. the ruleset's own target conditions — the `main`/`alpha` set is live configuration, not a
         constant this plan may assume (codex, r7). **STOP if that set is wider than `{main, alpha}`**:
         a third protected base would need its own M0/M2a/M2b/M3 evidence before the context could be
         required there, and requiring it without that evidence is COREDEV-2767 exactly. C2's hybrid
         equality assertion would red on it at rollout, but the preflight should not depend on a later
         cell to notice (kimi, third lens);
      4. **`trunk-check-push` ABSENT from the required-context list**, before and after (cell 16's
         re-verification — an M4 payload could otherwise require the canary and still satisfy the
         readback, leaving ordinary PRs pending and giving a `main`→`alpha` PR a same-SHA substitute).

      **Must CHANGE, in exactly one direction** — roll back if not:
      5. `trunk-check` is **absent** from the required contexts in the pre-read and **present with its
         expected `integration_id`** in the post-read;
      6. **and NOTHING ELSE changes**: the canonical ruleset is byte-identical **except for that one
         entry** — which is what "exactly one semantic difference" means, and is not a demand that the
         ruleset be unchanged (that would be the same unsatisfiable readback revision 24 shipped, in a
         new form). Compare the two canonical documents, subtract the intended entry, require the
         remainder to be equal. This covers far more than the required-context The update API exposes the whole surface: enforcement, bypass actors, target
         conditions, name, and every other rule (review requirements, signing, deletion protection).
         A payload can add `trunk-check` while altering any of those and satisfy a five-field
         readback (codex, r26). **Compare canonical pre/post rulesets and require exactly one
         semantic difference — the intended required-status-check entry.** Narrowing the comparison to `trunk-check` alone (revision 25's
         repair of revision 24's impossible readback) meant a payload that **adds `trunk-check` while
         dropping another required context** passed both reads — the destructive outcome this readback
         most needs to catch, opened by the fix for a checklist that could not pass.

      **Every open PR whose latest `trunk-check` is not PROVABLY from the strict workflow must be
      refreshed — on both bases — not merely those with no context at all** (codex, r26; population
      corrected r27-draft). Stating the population by *timestamp* excluded the very case the
      correction below exists to close: a re-run of an advisory M2 run carries a **post-M3**
      timestamp, so it does not "predate the strict M3 deployment" and would never enter the
      refresh set. Two populations, and
      revision 25 handled one: PRs predating M2/M2a have no context and sit pending (agy, r6); but a
      PR opened *during* M2 already carries a **successful** `trunk-check` produced while the job was
      advisory, M3 does not re-run it, and a required check is satisfied by an existing success on the
      commit regardless of which workflow revision produced it. M4 would then require a green that was
      never strict.

      **The mechanism, because the obvious button does not work** (kimi, third lens): "Re-run" keeps
      the original `GITHUB_WORKFLOW_SHA`, so a re-run can **never** satisfy the provenance test below —
      an implementer can click it indefinitely. Only a **newly triggered** run qualifies: close/reopen,
      or a push. Two dispositions follow, both implied by the merge-ref model and neither previously
      stated: **stale same-repo PR branches do NOT need a rebase**, because the `pull_request` merge ref
      picks the workflow up from the base — close/reopen suffices; and a **fork PR with maintainer-edits
      disabled cannot be refreshed by the maintainer at all**, which under `bypass_actors: []` means the
      disposition is "close it, or wait for the author". Decide that before M4 blocks on one — it is the
      exact incident class (unmergeable PRs, no bypass) this plan cites as its motivation.

      **Qualify by workflow PROVENANCE, not by timestamp** (codex, r27): a maintainer can "refresh" an
      advisory M2 run by **re-running** it after M3, and a re-run retains the original `GITHUB_SHA` and
      `GITHUB_REF` while acquiring a post-M3 timestamp — so a time comparison accepts a check still
      bound to the advisory workflow revision. Require a **newly triggered** run bound to the strict
      workflow's bytes (`GITHUB_WORKFLOW_SHA` or equivalent), and require every affected PR to pass
      that test **before** the ruleset write. **M4 is also resumable**: after any interruption,
      re-audit both refresh provenance and canonical ruleset state before continuing, since a
      half-completed M4 is indistinguishable from an untouched one by timestamp alone.
- [ ] **M4a** (**immediately after M4 — the plan reached revision 27 requiring neither of these**) —
      **prove the gate does what it exists to do, then prove it can be turned off.**
      1. **Cell 17, the enforcement smoke test.** Attempt to merge the deliberately-red sacrificial PR
         and record that GitHub **refuses**; confirm a green PR merges. Every other observation in this
         plan is pre-requirement and verifies what the workflow and rule *contain* — this is the only
         one that verifies the ruleset's *behaviour*.
      2. **Rehearse the §6.2a rollback.** Remove the `trunk-check` context, confirm the previously
         blocked merge becomes possible, re-add it, and re-run cell 17. An untested rollback is a
         plan, not a remedy — and with `bypass_actors: []` it is the only remedy there is.
      Both outcomes land in the rollout evidence artifact. **If either fails, roll the ruleset back to
      its pre-M4 canonical state** and return to M3.
- [ ] **M5** — run §3a; record the outcome on COREDEV-2801 as containment.
- [ ] **M5a** (**§6.3 decided**) — wire the trunk check into `.githooks/pre-commit`: **`--index`**
      (the staged content, not the worktree), **`--no-fix`**, §6.4's exclusion literal, a
      a macOS-portable timeout whose **constant is fixed by MEASUREMENT, and measured FIRST**. The
      only datum behind revision 23's `120` was a single 7s one-file run, which says nothing about a
      cold linter-cache bootstrap or a large staged changeset — and this hook **blocks**, so a false
      timeout changes shipped behaviour. **M5a's first step is to measure a representative upper
      envelope** (cold cache, largest realistic staged set); the measured value, **plus explicit
      headroom for slower hardware**, is then **recorded in this plan and becomes the authoritative
      constant**, which cell 13 asserts and mutates. **The headroom is not optional** (kimi, third
      lens): the envelope is measured on one developer Mac while the constant is asserted in CI across
      a Linux leg and different Darwin hardware, so a value fitted tightly to the measurement makes
      cell 13's clean slow-path case **fail against a correct implementation** on a slower runner.
      Revision 23 wrote `120` into M5a, told cell 13 to assert the literal `120`, and *also* said the
      constant moves if the envelope exceeds it — three statements that cannot all hold (codex, r24).
      **If the envelope exceeds the recorded constant, the plan is revised and re-reviewed** rather
      than the constant silently changing under a cell that pins it — and **exit-code aggregation that cannot mask an earlier hook
      failure**. Blocking on newly introduced findings, never `--all`. Update `CLAUDE.md`'s gate
      list. Independent of M2/M4 — it gates commits, not merges. Cell 13 carries the controls.
- [ ] **M6** — implement §3b's detector and wire it to **both** surfaces (§3b): the project
      `SessionStart` hook, which fires when a stale install starts running — the defect as actually
      reported — and `.githooks/pre-commit` (§6.3 decided: wire it). Runtime behaviour per **Table
      A**; the §3a experiment is read against **Table B**. Unconditional as of revision 5.

- [ ] **MV — the version bump, on EVERY landing PR** (sweep). Revision 20 put the four-site bump in
      §7's file inventory and in no milestone, and this plan lands **at least seven shipping PRs** —
      **M0a**, M1, M2+M2b+**M2c**, M2a, **M3 on `main` and M3 on `alpha` (two)**, M5a, M6 — one bump
      cannot serve them; M0a ships the registry and survivor corpus, and M2c ships the harness workflow
      and its fixture refs.
      M3 edits the workflow on **both** bases and the plan specifies no single-PR mechanism for that,
      so it is two landings, not one (codex, r23). **Each PR that changes a
      shipped asset carries its own bump**: `plugin.json`, the README H1, the README's newest
      `### vX.Y.Z`, the README asset counts, and a `CHANGELOG.md` section. **M3 belongs on that list**
      — it edits the workflow on both bases to remove `continue-on-error`, a shipped-asset change that
      revision 21 omitted while demanding a bump on every such PR (codex, r21). **M0, M4, M4a and M5 are the
      only exceptions** — a branch sync, a ruleset edit, a ruleset rehearsal and running the §3a
      experiment ship no plugin asset. **This list is closed, so every milestone added later must be
      placed on one side of it explicitly**; M2c and M4a were both added without it being revisited; revision 21 listed M0
      as shipping and then exempted it two lines later. `validate-version-sync.sh`
      only checks the four sites **agree**, not that they **moved**, so agreement at a stale version
      passes: the bump is a milestone obligation, not something the validator will catch.

M3 and M4 are gated on evidence, not schedule.

## §5 — Testing

Cells 1–3 exist because of inherited defect 3 — a gate over an empty diff passes having checked nothing.

1. **The diff is non-empty and correct per event — and the job, not just the test, detects it.**
   *(Scope, corrected: the REQUIRED job runs on `pull_request` only, so its own case is the PR range.
   The `push` cases below belong to the canary and to the parity harness, which evaluates fixtures for
   both events — revision 21 left this cell describing a two-event required job, and put the push
   `--all` branch "inside the required context" where it no longer is (codex + agy, r21). **The
   zero-`before` guard is therefore a CANARY obligation**: it is the push leg that can reach
   `push.sh`'s `--all` branch, so C1's canary contract carries that guard and cell 16 observes it — a
   canary without it would ship while this cell's harness passed.)*
   Assert the *resolved* upstream/diff for the `pull_request` path and for the `push` path, **on the
   harness's fixture refs** — `harness-base` and `harness/**` — not on `push` to `main`/`alpha`
   (draft check, r27). Only the canary fires on those branches, and the canary carries no instrumented
   launcher (`trunk-path` is the harness's sole legitimate use; C4 forbids it elsewhere), so it cannot
   report the argv this cell's byte-for-byte parity needs. The *event path* through the pinned action
   is what matters and the fixture refs exercise it; naming the protected branches made the
   enumeration read as satisfiable when it was not.
   **The mechanism was missing in revision 3 (agy, r3, in part):** `trunk check` exits **0** when the
   resolved diff matches no files, so the action alone reports green having checked nothing — which
   *is* inherited defect 3. The job therefore carries an explicit step that resolves the diff and
   **fails when it is empty**, before the action runs. **That step's computed range must be proven
   identical to the range the pinned action passes to Trunk** (codex, r6) — two independently
   correct-looking resolvers drift, and a guard that checks a *different* range than the one linted
   asserts nothing about the lint. **The resolver lives in ONE shared shipped script** — `scripts/ci/resolve-trunk-range.sh`, governed
   by **C6a** — invoked by the required workflow's guard step, **the canary's guard step**, and the
   harness (codex, r26; the canary was missing from the invoker list, and its guard is the one whose
   drift is most expensive — draft check, r27): revision 25 digest-bound the harness's
   *action inputs* to the workflow and left its range resolution independent, so a correct oracle
   could agree with Trunk while the shipped guard used the wrong range — and C8 would merely freeze
   that wrong body. With one implementation, parity is a property rather than an agreement between two
   things that might both be wrong. **"Proven" must name a harness, not a hope (codex, r7):** run the
   pinned action against per-event fixtures with `trunk-path` pointing at an instrumented launcher
   that records its argv, then compare the captured range arguments **byte-for-byte** against the
   guard step's output.

   **One push subdomain runs `--all`, and the guard must refuse it (codex, r9).** At the pinned SHA,
   `push.sh` branches on `GITHUB_EVENT_BEFORE == 0000…0` — the shape GitHub sends when a branch is
   created or a tag is pushed — and runs `trunk check --ci --all`, which is precisely the 9027-finding
   whole-tree run §1 forbids. **That branch is reachable only from the CANARY** — the required
   workflow has no `push` event — so C1's canary contract carries this guard and cell 16 observes it;
   revision 21 corrected the scope at the head of this cell and left this sentence saying "inside the
   required context" (codex, r23). The empty-diff guard therefore **also fails
   when `github.event.before` is all zeros on a push**, rather than letting the action reach that
   branch. Fail-closed: a push whose diff cannot be resolved is not a push that gets to lint the tree.
   Its own fixture. *(That is the one legitimate use of `trunk-path` — inside the harness, never
   in the shipped workflow, where §1's allowlist forbids it.)* *(An r3 finding claimed §1 prohibited custom step wrappers, which was false at the time; note that
   **§1's C8 now does freeze the step sequence**, so the historical rebuttal no longer describes this
   plan — codex, r10.)*
2. **The gate bites — asserted at the level each milestone can actually deliver** (codex, r11). A
   deliberately bad changed file must produce a failure. But at **M2** the job ships
   `continue-on-error: true`, so the *job* still concludes green: an unqualified "fails the job" is a
   cell that **cannot pass at M2**, and revision 11 exempted only cell 11 from that window. So:
   * **at M2** — assert the Trunk step's **API-reported `conclusion`** is `failure` in the
     workflow-jobs record **and that the failure carries the expected lint diagnostic for the
     deliberately bad file**. Conclusion alone is not causation (codex, r24): a checkout, launcher or
     action-setup failure produces the same `failure` at M2 and the same job failure at M3, so an
     unqualified cell certifies a broken advisory workflow as a working gate. Cell 12 already binds to
     the diagnostic; this is its sibling and revision 22 fixed only the one codex named (not the in-job `outcome`, which no post-hoc observer can read — codex,
     r19). This is why M2's exemption is pinned to job scope;
   * **from M3** — assert the **job's conclusion** is `failure` **and that it carries the same
     expected lint diagnostic**. Revision 24 bound only the M2 branch, so a checkout, launcher or
     setup failure was killed at M2 and *reached* at M3 — the very sibling that fix's own explanation
     named (codex, r25). Both branches record it in the rollout artifact's **`trunk_step_diagnostic`** field, so the evidence
     shows causation and not merely a conclusion — revision 25 asserted that "both branches name the
     field" while neither named one.
   * **also from M3 — a real RETARGET case** (codex, r21). The `types:` widening is a *static* clause
     assertion; nothing yet observes that it works. Open a PR against one base, let `trunk-check`
     land, then **retarget it to the other base** and assert the context that satisfies the rule is a
     **new run against the new base's range** — not the earlier same-SHA result. Without `edited` in
     the set the old run persists and this case fails, which is the discrimination the clause needs.
3. **The gate does not over-reach** — *asserted from M3, when the job can actually fail*. At M2 the
   job ships `continue-on-error: true`, so its "passes" halves cannot fail and its "still failing"
   half cannot pass; like cell 2, this cell is milestone-qualified rather than unqualified (sweep). (a) A PR touching one clean file passes with the 9027-issue
   backlog present. (b) A PR touching a **historically dirty** file passes for its pre-existing
   findings while still failing for newly introduced ones.
4. **The configured linter set MEMBERSHIP is frozen in the test, not derived from the configuration
   under test**
   (codex, r5). Revision 5 said "the configured set minus the declared exclusions", which reads the
   expectation out of `.trunk/trunk.yaml` — **making a silently reduced configuration authoritative
   over the assertion meant to detect it**, the exact shape this plan's Overview names. The cell
   instead carries **the 19 expected linter names as literals** (20 enabled, minus
   `markdown-link-check`) **and a frozen digest over the `lint:` block with VERSION SPECIFIERS
   NORMALISED OUT**. Fails if any of the 19 is missing, if an unlisted linter appears, if the
   exclusion list grows, or if the block changes in any way other than a version pin — **and it fails when `.trunk/trunk.yaml` is reduced**, which the revision-5 wording
   could not.

   **Names alone were not enough (both arms, r9).** A PR can keep all 19 names and still disable
   every linter by overriding `lint.definitions[].commands[].run` to `exit 0`, widening
   `success_codes`, or adding a global `ignore`. A membership oracle sees nothing wrong. The digest
   over the whole block catches any of those, and C6 covers the sibling route of adding
   `.trunk/user.yaml` or `.trunk/env.yaml` to override the file entirely.

   **What this cell does and does not prove (codex + agy, r6).** It is a *membership* oracle over the
   configuration, not proof that each linter executes: a static parse cannot show that `shellcheck`
   actually diagnosed anything. **The claim is membership and nothing more.** Revision 7 narrowed the
   claim while still promising "per-linter positive controls" and an "explicitly listed" fixture set
   that §7 never assigned to any file (codex, r7) — a promise no cell owned. Execution coverage is
   **out of scope for this plan** and filed as COREDEV-2787 follow-up work; this cell does not claim
   it.

   **Maintenance rule, without which the freeze becomes the defect.** A frozen oracle fails on every
   *legitimate* linter change, and the obvious repair — regenerate it from the config — restores the
   very coupling the freeze removed. So: an intentional add, removal or rename updates the frozen 19
   **in the same commit, under review, with the reason recorded**; a **version-only** bump does not
   touch the oracle. **That carve-out and a whole-block byte digest cannot both hold** — verified:
   `.trunk/trunk.yaml` carries versions *inline* (`zizmor@1.29.0`, `gitleaks@8.30.1`, …), so a routine
   `trunk upgrade` changes the block's bytes and would red the cell with no plan change, and the
   obvious repair — regenerate the expectation from the config under test — is precisely the coupling
   the freeze exists to remove. Hence the digest normalises version specifiers before hashing: it
   still catches a changed `commands[].run`, a widened `success_codes`, an added `ignore`, or a
   dropped linter, and ignores the one edit that is routine. A coordinated edit to config and
   oracle together is out of this cell's reach by construction — that is what review is for.
5. **No autofix: the job introduces no tracked-source mutation.** Narrower than revision 9's "never
   mutates the tree", which was false (codex, r9) — the pinned action itself creates `.trunk/setup-ci`
   and appends it to `.git/info/exclude`. The invariant that matters, and that is tested: **no tracked
   file's bytes change**, and no autofix is applied.

   **The fixture must be deliberately fixable (codex, r10).** Running the job over already-canonical
   files proves nothing — autofix would produce no byte change there either, so the cell *reaches* the
   wrong implementation without killing it. The case therefore stages a file a formatter would
   certainly rewrite (mis-indented, unsorted imports) and asserts it is **byte-identical afterwards**.

   **This is a hybrid under §7's rule, and its runtime half needs a SENSOR, not a sink** (codex, r14
   then r18). The claim is about what the real run did, which a Python test cannot observe — but the
   rollout evidence artifact cannot observe it either: **C8 makes the Trunk action the final step**,
   GitHub exposes no API for an ephemeral runner's worktree, and a committed JSON file records what
   something else measured. Revision 15 satisfied the hybrid rule with an owner that cannot see.

   The runtime half therefore uses **cell 1's mechanism**: the instrumented pinned-action harness,
   which runs the action against fixtures **outside the required workflow** and can hash the tree
   afterwards because nothing constrains *its* step order. **But cell 1's launcher only records argv
   and exits zero, which for this cell is no stimulus at all** (codex, r19): a fixture is trivially
   unchanged when nothing ran, so a recorder-only harness reports green whether or not real Trunk
   would have rewritten it. For cell 5 the launcher must **record and then delegate to the real
   pinned Trunk**, and the case carries a **positive control**: enabling autofix must change the
   fixture and turn this cell red. A sensor that cannot register the thing it watches for is the
   sink problem wearing a different hat. Python still builds and hashes the fixture;
   the harness carries the post-invocation comparison. **Its collection and upload steps run under
   `if: always()`** (codex, r28): the deliberately-fixable fixture is *meant* to make the real Trunk
   step fail, and subsequent steps otherwise inherit the implicit `success()` condition and skip the
   post-run hashing entirely — the evidence would simply never be produced. The action's conclusion is
   recorded separately from the hash comparison. §7's rule gains the corollary that an evidence
   artifact is only a valid owner for something a real run **reports** — a conclusion, a check run —
   never for state that vanishes with the runner.
   Cell 9's static `--fix` prohibition is a separate, weaker check on the configuration; this one is
   about what the run did.
6. **quote-keep — relocation passes, and three wrong implementations fail, each for the RIGHT
   reason** (codex + agy, r5). Prepend to `CHANGELOG.md` → green with no edit. Then: content change →
   red; **duplicate source line → red** (kills "at least one"); and the `:342`/`:358` dependencies
   still hold.

   **Two of those three controls were confounded exactly as cell 7's was, and revision 4 fixed only
   cell 7.** A content change can red through the independent missing-literal census even with the
   exact-hash assertion deleted; a duplicated source literal can red as an unexpected observed site
   even against an "at least one" implementation. Both **reach** the branch under test without
   **proving** it caused the failure. So, as in cell 7: assert the **specific diagnostic** for each
   case, **or** mutate the zero-count and duplicate-count branches directly and show the diagnostic
   disappears.
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
   that branch by requiring **the diagnostic disappears**.

   **Not "the case goes green" — that is impossible here, and revision 4 wrote it (codex, r5).** The
   independent `:326` census still fires after the branch is deleted, so the case stays red no matter
   what; a mutation test demanding green could never pass. **A cell that cannot pass is the mirror of
   one that cannot fail, and worth as little.** The observable is the *presence or absence of the
   specific diagnostic*, which isolates the assertion under test from everything else in the case.
8. **The detector fires from its real entry points — with the two surfaces proved differently,
   because CI can only reach one of them.**
   * **pre-commit** is proved in CI: a real `git commit` runs the hook, a mismatch **never blocks**
     (the commit still succeeds), and Table A's silent rows produce **no output at all**, so an equal
     or locally-newer install cannot train people to ignore the warning.
   * **`SessionStart`** cannot be proved by the planned suite (codex, r10, refined r11): the
     repository *does* install Claude Code later in `plugin-ci.yml`, but **the Python suites run
     before that step**, and §7 leaves the workflow unchanged — so any "real entry point" assertion there would be a parser or
     emulator, which is precisely the direct-unit-call this cell forbids. **Split the claim honestly.**

     **CI asserts the DECLARATION**, against the documented stdin contract — rewritten as a list
     because successive revisions appended into one run-on sentence until its parentheses no longer
     balanced (codex, r26):
     * the matcher set, and `${CLAUDE_PROJECT_DIR}` resolution for both hook entry and script;
     * **`timeout: 5` as a literal, mutated as an operand** — asserting the key alone accepts the
       600-second default this contract exists to override, the same defect cell 15 had;
     * the **`systemMessage`** output shape;
     * **a filename-hostile `session_id`** — one containing `/`, one exceeding a path component's
       length limit — with a mutation that removes the hashing. The contract requires
       `sha256(session_id)` precisely because the identifier is opaque, and revision 16 tested that
       nowhere: an implementation using the raw id passes the matcher, concurrency and aged-marker
       cases and then **fails open** (codex, r17);
     * the `O_EXCL` marker under **concurrent invocation** and under **aged-marker resumption** — a
       session whose marker was swept past the retention window warns again, which is exactly why the
       promise is per-window rather than per-session (codex, r11);
     * **the retention constant, discriminated in the terms the design actually uses**: repeated
       invocation **within one bucket** warns once, invocation **across a bucket boundary** warns
       again *even minutes apart*, and the **bucket-width constant `604800` is mutated**. An
       aged-marker test alone is satisfied by a detector sweeping at six days — covering the line
       without covering its operand (codex, r12) — while the age-threshold phrasing that replaced it
       ("just under seven days must NOT sweep") described a mechanism §3b **abandoned at revision 13**
       for epoch buckets, and would fail against a correct implementation: under buckets a marker
       created shortly before a boundary is swept while hours old.

     **The real session-start invocation** is recorded once as a **committed evidence artifact**, the
     same standing cells 10 and 12 have. Claiming a CI proof this repo's pipeline cannot produce would
     be a cell that cannot pass.
9. **The job block prohibits what COREDEV-2771 measured.** `check-mode` absent, `post-annotations`
   **absent** (not "absent-or-false": C4 is an allowlist, and `post-annotations: false` is an unlisted
   key *present* in `with:`, which cell 11's arbitrary-unlisted-key mutant reds — the two cells
   disagreed while the blacklist wording stood), no custom `--upstream`, no `--fix`, `actions/checkout` SHA-pinned — and
   **`arguments:` PRESENT and equal to §6.4's declared literal as a whole string** (§1) — absence is
   a failure, not a permitted variant (codex, r5), and an appended argument cannot pass a substring
   test — **and `trunk-io/trunk-action` is pinned to the exact SHA of §1's C9**, with tag-reference
   and different-SHA mutants. Revision 9 asserted only that `actions/checkout` was pinned, so a
   re-tagged or swapped action satisfied every other clause (codex, r9).
10. **The chosen §6.1 annotation mechanism is present, permitted, and works** — a **hybrid**. The
    *static* half asserts `permissions:` equals `contents: read` at **both** workflow and job scope,
    because a wider token produces byte-identical runtime evidence and only a static check
    discriminates it. The *runtime* half observes a non-fork PR — no 403. Under
    option (b) that is checkable rather than merely observed: assert the run takes the
    `--github-annotate-file` branch (**not** `--github-annotate`) and that the `trunk-annotations`
    artifact is produced, uploaded by the action's own SHA-pinned `actions/upload-artifact` step
    under `if: always() && env.TRUNK_UPLOAD_ANNOTATIONS == 'true'`. **No added token scope**: the
    upload uses the Actions runtime, not `GITHUB_TOKEN` permissions, so `contents: read` stands.
11. **The workflow admits no configuration that would let `trunk-check` report a merge-satisfying
    conclusion without the real Trunk running** — a **structural** invariant over the workflow's
    bytes, which is what this cell's parse/mutation owner can actually observe (codex, r26). Revision
    25's title claimed the *runtime* property; that belongs to cells 2, 12 and 16, which watch real
    runs. The distinction matters because a cell whose title outruns its owner is how this plan
    repeatedly acquired assertions nothing could evaluate. GitHub counts **`success`, `skipped` and `neutral`** as satisfying a
    required check (codex, r7) — revision 7 said "success", which is narrower than the set that
    actually lets a merge through.

    **This cell asserts §1's contract clause by clause — C0 through C9 AND C6a — and does not restate their
    values** (codex, r8: revision 8's copies had already diverged from §1 on `merge_group`).

    **The mutant set is GENERATED from the contract registry** (`COREDEV-2780-contract.yaml`, §1) —
    one mutant per **mutation case**, keyed by its id; iterating *entries* still under-covered any
    obligation needing more than one mutation (codex, r15). **The survivor corpus runs alongside it**
    and must keep failing. Every round since r9 found the same gap
    somewhere new (`$GITHUB_PATH` declared but unmutated; checkout's `filter` named but unmutated; no
    arbitrary-unlisted-key case), because a hand-written list always drifts from the list it mirrors.
    Revision 13's answer — derive them from the clause *text* — was not a mechanism (codex, r13):
    unrestricted prose cannot be parsed, and a hand-written registry compared against hand-written
    mutant names moves the drift up a level rather than removing it. **Generating from structured
    entries makes under-coverage impossible by construction**, and the rendering lint keeps the prose
    honest to the registry rather than the other way round.

    Concretely, one mutant per declared **case** (codex, r9: a single mutant cannot exercise the
    independent parser paths inside a multi-part clause; codex, r15: one per *entry* under-covers any
    obligation needing several). **Each mutant must be constructible, must change the intended
    property, and must fail with its OWN diagnostic.** It need not satisfy every other clause — the
    clauses overlap by design, so `if: false` violates C3 *and* C8's mapping freeze, and a tagged
    action violates C9 *and* C8; demanding non-overlap would make most mutants unconstructible
    (codex, r14). The generator must at minimum produce:
    * **C0/C3 permissions** — `permissions: write-all` at the **root**; `write-all` at the **job**;
      a single widened scope at each; and the key **absent** at each. Six cases: revision 24 declared
      three static permission mutants in C0's prose and listed none here, so the minimum the generator
      had to produce omitted all of them (codex, r25).
    * **C6a** — edit `scripts/ci/resolve-trunk-range.sh` while leaving the invoking `run:` bodies
      untouched: the guard must red on the digest mismatch **and must do so BEFORE the empty-diff step
      executes the edited script** — assert the failing step is the C6a guard, not a later one, since
      a guard that reds after execution proves the wrong property. Without this case the script is
      repository-supplied and ungoverned, which is inherited defect 3 under a new file name.
    * **C0** — `concurrency` at the workflow root; `concurrency` on the job; and one arbitrary key
      outside the root allowlist.
    * **GENERIC UNLISTED-KEY mutants at EVERY allowlist boundary** (codex, r26). Naming only the keys
      this campaign happened to think of leaves a blacklist detector passing every listed mutant while
      violating the exact-key allowlists of C1, C3 and C8. One arbitrary *valid* unlisted key at each
      boundary: a **`schedule`** event; a job key such as **`container`**, `services` or
      `environment`; and a complete-step key such as **`id`** or `timeout-minutes`. **Revision 22 added C0 and left every authoritative range reading
      C1–C9** (codex, r23), so an implementation could omit it from the registry and ship the exact
      cancellation hazard C0 exists to prevent — a clause with no range and no mutant is decoration.
    * **C1/C2** — a second trigger added (`push`, `workflow_dispatch`); the `pull_request` event
      **removed**; **`paths:` added** (a real, valid `pull_request` option that narrows); **one
      arbitrary unlisted mapping option**; `branches:` **absent**; `branches:` unequal to the ruleset
      set; **`types:` reduced to the default set** (dropping `edited`, reintroducing the stale-base
      pass); and **`types:` REMOVED entirely** — its failure mode is omission, and a validator that
      checks the value only when the key is present rejects the reduced-set mutant while accepting an
      absent one (codex, r21).

      **The `tags:` mutant is dropped as unconstructible (agy, r21):** `tags:` is not a valid
      `pull_request` mapping option at all, so that mutant fails **schema** validation rather than
      contract validation — exactly the defect that retired `push.tags` one revision earlier, in the
      case written to replace it. A narrowing option that *is* valid under `pull_request` is `paths:`,
      which is what the case now uses.

      **Two of revision 20's cases were dead on arrival and are replaced (sweep).** "A valid
      `push.tags` mapping option" and "a `types:` activity filter" were written against the two-event
      clause; after revision 20 narrowed C1 to `pull_request` only, `push.tags` **cannot be
      constructed** in this workflow, and `types:` went from prohibited to *required* (C2). A mutant
      that cannot be built is not a mutant. *Generation cannot invent an absent registry case, and it
      cannot retire a stale one either* — a clause and its cases must land, and change, together.
    * **C2** — `branches:` absent; `branches:` present but unequal to the ruleset set; `paths:`
      present; `paths-ignore:` present.
    * **C3** — job-level `if:`; Trunk-step `if:`; `needs:` with a failing dependency;
      `strategy.matrix`; job-level `continue-on-error`; step-level `continue-on-error`; **zero** Trunk
      invocations; **two** Trunk invocations.
    * **C4** — each of `trunk-path` and `post-init`; one arbitrary unlisted key; **`arguments:`
      absent** (its failure mode is omission, not addition — absent means `markdown-link-check` runs
      in the required job); **and `save-annotations` absent, and set `false`** — §6.1 chose option
      (b), so its value is *required-present*, and absent means the action falls back to
      `--github-annotate` and 403s under `contents: read`.
    * **REQUIRED-PRESENT obligations need OMISSION cases, which revision 20 had none of (sweep).**
      Every checkout and input mutant was a *prohibited-key addition*; the obligations whose failure
      mode is a **missing** key were untested, so a validator checking only for forbidden keys passed
      everything. Add: `lfs:` **removed** and `lfs: false`; `persist-credentials:` **removed** and set
      `true`; `arguments:` removed (above); `branches:` removed (C1/C2 above); and **each of C8's FIVE steps DELETED, as five separate
      cases with their own diagnostics** — including the C6a resolver-digest guard, whose deletion
      un-verifies the script before it executes — cases are first-class and produce one mutant each, so
      revision 22's single "a step deleted" case (motivated by the empty-diff guard) left a validator
      that requires *that* step while accepting omission of the **C6 guard** passing every listed
      mutant, shipping the repository-launcher hole (codex, r24).
    * **C5** — `env: {TRUNK_PATH: /bin/true}` at **workflow** level, at job level, and at step
      level: three independent mutants, because revision 10's clause covered only two of the scopes.
    * **C6** — each of the four launcher paths in turn, and each of `.trunk/user.yaml`,
      `.trunk/env.yaml`. **The `.trunk/setup-ci` fixture must be a VALID composite action that exits
      green** (codex, r9) — `uses: ./.trunk/setup-ci` expects an action directory, so a bare no-op
      executable reds because it is *malformed*, and the mutant would survive deletion of C6 while
      still appearing to be caught.
    * **C7** — `merge_group` present at all.
    * **C8** — an extra step inserted before the action; the C6 guard moved away from its adjacency;
      **a mutation inside a permitted `run:` step** — in **both** permitted steps, and in four
      forms: creating one of C6's paths (the case revision 10's ordering made unkillable), writing
      `TRUNK_PATH=/bin/true` to `$GITHUB_ENV`, writing `BASH_ENV=…` to `$GITHUB_ENV`, and **writing
      to `$GITHUB_PATH`** (codex r11 and r12: freezing the sequence never constrained what the allowed
      steps *do*, and `$GITHUB_PATH` was prohibited without ever being mutated); on
      `actions/checkout`, each of `sparse-checkout`, `ref`, `repository`, `path`, **`filter`, and one
      arbitrary key outside the allowlist**; on **each of the five steps** an `if: false` and a
      `continue-on-error: true`; on the **two `run:` steps only**, a changed `shell` **and a changed
      `working-directory`**; and a `defaults.run` at workflow and at job level.

      **`shell` is valid only on `run:` steps** (codex, r17): `actions/checkout` and the Trunk action
      are `uses:` steps, where `actionlint` rejects `shell` as an unexpected key — so revision 16's
      "each of the four steps" (as it then was) produced two mutants that fail **schema validation** instead of with
      their own contract diagnostic, breaking this cell's own case-validity requirement and making
      **cell 11 unable to pass at M2**. The `uses:` steps are mutated through valid keys instead
      (their `with:` inputs and an added `env:`). And `working-directory` is frozen by C8 while
      revision 16 mutated it nowhere, so a validator that checks the body digest, `if`,
      `continue-on-error` and `shell` but *forgets* `working-directory` passed every case.
    * **C9** — the action referenced by tag; the action referenced by a different SHA.

    Each mutant must produce a **red cell** and — per the lesson of cells 6 and 7 — must be shown to
    do so **for its own reason**, identified by its own diagnostic, not through a sibling clause.

    The C6 mutants matter most, because they are the ones a **pull request** can introduce: the
    guard step must fail on a checked-out `.trunk/bin/trunk`, `tools/trunk`, `./trunk` or
    `.trunk/setup-ci`, and each must be exercised separately — a guard that catches three of four is
    a gate with one door open.

    **Scope the claim honestly.** Cancellation, job timeout and setup failure *do* report conclusions
    without Trunk running — `cancelled`, `timed_out`, `failure` — but every one of them **blocks**
    rather than satisfies, so they are outside this cell's property. Revision 6's "no conclusion can
    be reported" was false; revision 7's "cannot report success" was true but too narrow, since
    `skipped` and `neutral` also satisfy. The property is **no merge-satisfying conclusion without a
    real Trunk run**.

    **This cell has now been wrong three times, and every failure was in what it ASSERTED rather
    than in the design it tested.** Revision 3 asserted the prose property "the job is unreachable on
    dispatch", which an unsupported job-level `on:` satisfied. Revision 4 asserted the literal `if:`
    guard — present and correct on a job that a dispatch skips into a **reported Success**, so the
    cell would have certified the bypass. Revision 7 asserted a **blacklist** of caller inputs, which
    a repository-supplied launcher walks straight past. Each time the cell described a *mechanism*,
    and the mechanism moved. It now asserts the **property**, and every clause of §1's contract
    exists because some specific configuration satisfied the previous wording while defeating it.
12. **Both protected bases emit the context, from the intended producer** (M4's precondition, codex
    r3 + r5). Observe a real `trunk-check` check run on a `main` PR **and** on an `alpha` PR — green
    and red on each — before the context is required. Fails if either base produces no check run.

    **The red observation is bound to the Trunk STEP, not the job** (codex, r6). A job conclusion of
    `failure` proves only that *something* failed — suppress Trunk's failure and let an unrelated
    fixture step fail and the cell still sees red. The evidence must name the Trunk step's own
    **API-reported `conclusion`** and its expected diagnostic. **`conclusion`, not `outcome`**
    (codex, r20): the workflow-jobs API exposes the former and never the latter, so revision 19's
    wording — fixed for cell 2 and left standing here and in §7 — asked for an artifact field that
    cannot be produced. The same sibling-instance miss as cells 6/7, three revisions on. **Each observation is bound to its provenance**: the
    workflow **file path**, the **effective check name** (cell 14's identifier — *not* the YAML job id,
    which the check-run API does not expose; revision 7 said "job id" in this cell while cell 14
    correctly used the effective name, and the two must agree — agy, r7), the exact head **SHA**, and
    the reported **conclusion**. Without that
    binding a duplicate `trunk-check` defined elsewhere (cell 14) could supply the evidence while the
    intended job never ran. **And the evidence must come from the STRICT job**: re-fetch both base
    tips immediately before M4 and confirm each still contains a byte-equivalent strict job, since
    the plan otherwise permits drift between the observation and the ruleset change (codex, r5).
13. **The pre-commit hook runs the check against the INDEX, blocks, mutates nothing, and is
    bounded** (§6.3). Assert:
    * a **staged** file with a new finding **fails the commit** — and, as its discriminating pair, a
      file that is *bad in the worktree but clean in the index* **does not**, proving `--index` and
      not the worktree is what is checked;
    * a staged clean file commits with the 9027 backlog present (so the hook is not `--all`);
    * `--no-fix` is passed, and **neither the index nor the worktree is modified** by the hook — this
      Trunk version applies fixes automatically otherwise (codex, r5);
    * the check runs under its declared timeout — **asserted as M5a's recorded measured literal, not
      merely "some timeout"** (codex, r21): a test that derives its sleep threshold from whatever the
      implementation declares accepts any value, covering the line without covering its operand. The
      constant is mutated, and a **clean slow-path case** (cold cache, largest realistic staged set)
      must complete without tripping it, and the mechanism must be **macOS-portable**, exercised against a sleeping
      fake `trunk` on the PATH;
    * the hook's **exit code aggregates**, asserted by making an *earlier* hook command fail while
      the trunk check succeeds — appending a passing command after `.githooks/pre-commit:7` would
      otherwise mask its nonzero result.

    Fails if the hook is advisory, scopes to the whole tree, checks the worktree instead of the
    index, mutates either, is unbounded, or swallows a prior failure.
14. **Exactly one producer emits the context name `trunk-check`, repo-wide** (codex, r5 + r6).
    Census every file under `.github/workflows/` and assert exactly one job whose **effective check
    name** is `trunk-check` — that is, its explicit `name:` where present, **otherwise** its job id.
    **Keying on the job id alone is the wrong identifier** (codex, r6): a job declared
    `jobs.something-else` with `name: trunk-check` produces exactly the same required context, so an
    id-only census reports one producer while two exist. A second producer would let cell 9 validate
    the intended job while a duplicate satisfies the rule, and GitHub's protected-branch guidance
    warns that same-named required checks across workflows give ambiguous results. Fails on zero
    producers or more than one.

    **Those alternatives need FIXTURES, not prose (codex, r20).** Against the intended repository —
    whose job id *is* `trunk-check` — an id-only census passes, so the cell as described never kills
    the implementation it calls wrong. The controls are built: a second workflow declaring
    `jobs.something-else.name: trunk-check`; a reusable-workflow caller producing
    `<caller> / <reusable>`; **zero** producers; and an expression-valued `name:` that must
    **fail closed**. Note the census now counts producers of **`trunk-check`** only — the push leg's
    `trunk-check-push` is a different context and deliberately outside it (C1).

    **Two cases the simple formula still gets wrong (codex, r7).** A job that calls a **reusable
    workflow** is reported as `<caller job name> / <reusable job name>`, so its effective context is
    neither name alone; and a `name:` containing an **expression** cannot be resolved by a static
    census at all. The census must model the reusable-workflow form and **fail closed** — never
    silently count zero — on any name it cannot resolve statically.
15. **The job's runner and timeout are what §1 requires, and §1 matches its registry.** Assert
    `runs-on: ubuntu-latest` and **`timeout-minutes: 15`** — a *concrete* ceiling, mutated as an
    operand. Revision 21 required only that the key *exist*, which `timeout-minutes: 360` satisfies
    while being **GitHub's default six-hour ceiling** — a timeout that changes nothing (codex, r21).
    Fifteen minutes is ~6x the existing `validate` job's runtime; **and assert the rendered C0–C9 **and C6a** prose
    agrees with `COREDEV-2780-contract.yaml`**, so the registry cannot silently diverge from the
    document that explains it. §1 has required both since revision 2 and
    **nothing asserted either** — omitting them passed every other cell, and a job with no timeout can
    hang until the platform's six-hour ceiling while the required context sits pending.
16. **The push canary meets its whole contract, and is not a required context at rollout.**
    Revision 22 gave the canary a contract — event and branches, SHA pins, the empty-diff and
    zero-`before` guards, permanent **job-scoped** `continue-on-error` — and had this cell assert only
    **existence, `continue-on-error` and ruleset absence**, so a canary with the wrong branches, no zero-`before`
    guard, or `trunk-path: /bin/true` passed cells 1, 11 and 16 alike (codex, r24). **Every canary
    obligation is a registry entry with its own mutation cases**, including the C4/C5/C6
    execution-integrity controls that prove real Trunk ran — the canary is a shipped workflow, and a
    shipped workflow that nothing constrains is the hazard this plan exists to remove, whether or not
    it is required.

    On the ruleset half (sweep; scoped codex r21): A committed ruleset observation is a **point-in-time read** — it cannot prove "never",
    and claiming so would be a cell asserting more than its owner can see. The honest claim is
    rollout-time absence, **re-verified in M4's post-edit readback** alongside the other conditions
    checked there. Continuous monitoring is out of scope; nothing here prevents a later maintainer
    from requiring the canary, which is why §1's contract states the reason it must stay unrequired. Assert **every obligation C1's canary contract states** — it exists; `on: push` with `branches:`
    equal to the ruleset's target set; the C4/C8/C9 action and checkout pins; C5's `env:` prohibition;
    C6's repository-launcher guard; the empty-diff and zero-`before` guards, both invoking C6a's shared
    resolver; `permissions: contents: read`; `continue-on-error: true` **at job scope**; and that
    `trunk-check-push` is absent from ruleset `Control`'s required-status-check list. **The three-item
    form this instruction previously carried — existence, `continue-on-error`, ruleset absence — is
    exactly what r24 proved insufficient**, and it survived directly beneath the paragraph saying so — revision 20 required the
    file to exist while no milestone created it and no inventory listed it. This is the cell that
    keeps cross-event substitution closed: the split only works while the canary stays unrequired.

    **M2b must CAUSE a controlled canary failure, and the stimulus must be REACHABLE** (codex, r26,
    corrected r27). Revision 26 said "a scratch branch matching the canary's `branches:`" — but those
    branches are exactly the ruleset's target set, `main` and `alpha`, and `push.branches` matches the
    branch actually pushed, so no additional in-repo branch can match and the workflow would never
    run; the alternative — a lint-failing commit pushed straight to protected `main` — is what the
    ruleset exists to prevent. **The stimulus is a provenance-bound disposable fork** whose default
    branch is named `main`, carrying the same canary workflow at the same SHA pins; the failing commit
    lands there. **Enabling Actions in that fork is part of the step** — GitHub disables them on forks
    until someone turns them on, so without it the stimulus silently produces nothing and this cell's
    runtime half is quietly unfalsifiable (kimi, third lens). Record that the **Trunk step's `conclusion` is `failure` while the job's is
    `success`** — the job-versus-step `continue-on-error` distinction this cell exists to prove.
    Without a milestone that produces the stimulus, the evidence artifact stays empty and the cell
    is unfalsifiable.

17. **A red check actually BLOCKS a merge, and a green one does not** — observed after M4, against
    the live ruleset. Attempt to merge the deliberately-red sacrificial PR and record that **GitHub
    refuses**, **and that the stated reason names `trunk-check`** — not merely that some refusal
    occurred. `Control` requires five other contexts, so a merge attempt can be refused for reasons
    having nothing to do with this gate, and a cell that accepts any refusal is the confounded control
    this plan repaired in cells 6, 7 and 12 and then rebuilt in the cell added to test the gate itself
    (regression check, r28). The sacrificial PR must be green on every other required context, and the
    recorded evidence names the blocking check. Then confirm a green PR merges. Owner:
    `evidence/COREDEV-2780-rollout.json`.

    **This is the only cell that tests the ruleset's BEHAVIOUR rather than its bytes, and the plan
    reached revision 27 without it** (kimi, third lens). Every other observation here is
    *pre-requirement*: M3's green and red runs, cell 12's provenance-bound check runs, M4's canonical
    readback — all of them verify what the workflow and the rule *contain*, and none of them verifies
    the property the entire plan exists to produce. It is also the cheapest cell in the document. An
    absence like this cannot surface in a diff, which is why twenty-nine rounds of incremental review
    did not find it.

## §6 — STRUCTURAL DECISIONS

### 6.0 — DECIDED 2026-08-28 (maintainer): the alpha base

`alpha` is a protected base under ruleset `Control`, has **no** `.trunk/trunk.yaml`, and is **611
commits behind `main`, 0 ahead**. Decision, in order: **(1)** bring `alpha` up to date with `main`;
**(2)** land the trunk configuration there as its own PR; **(3)** gate `main`. *(That is the
decision as taken, recorded verbatim; steps (2) and (3) are corrected immediately below — read the
refinement, not this line, as the plan of record.)*

**Refined in r3, against what the repo actually contains — the decision stands, two of its steps
change.** Step (2) is **subsumed by step (1)**: `.trunk/trunk.yaml` is already on `origin/main`, so
syncing `alpha` to `main` lands the configuration there by construction. And a step was **missing**:
the `trunk-check` **job** must also reach `alpha` (M2a), because GitHub runs the workflow version at
the event's ref — syncing `alpha` *before* M2 brings the config but not the job.

So the sequence is: **(1)** sync `alpha` to `main` (lands the config) → **(2)** add the job on `main`
(M2, in its own workflow) → **(3)** land the job on `alpha` (M2a) → **(4)** make both bases strict
(M3) → **(5)** add the required context to ruleset `Control`, with evidence from both bases.

**Step (5) is not "gate `main`" (codex + agy, r5).** `Control` targets `main` *and* `alpha`, so
adding the context gates **both** simultaneously — which is precisely why steps (2)–(4) exist. The
"gate `main`" shorthand is stale wording from a revision that had not yet established the second
base, and it understates what the final step does.

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

### 6.2a — DAY-2 ROLLBACK: how the gate gets turned OFF

**The plan reached revision 27 with no answer to this, and it is the most conspicuous absence in the
document** (kimi, third lens). Everything in §4 concerns turning the gate *on* safely; nothing covered
the incident where it is on and wrong — a Trunk infrastructure outage, a linter upgrade that reds every
PR, a false-positive class nobody anticipated. With `bypass_actors: []` there is no override, so the
only remedy is an emergency ruleset edit, and "who can do that, and how" cannot live in one person's
head while `main` is unmergeable. This repository has already shipped that incident once.

* **The remedy** is to remove the `trunk-check` context from ruleset `Control`'s required-status-check
  rule — *not* to delete the workflow (a deleted workflow produces no check run, which leaves the
  required context **pending** and blocks merges just as hard, only less obviously).
* **Who can perform it:** an account with repository admin. Record the holders in the ticket, not here.
* **The call**, written out so it is not composed under pressure — read the ruleset, drop the one
  entry, write it back, and confirm by re-reading:
  `gh api repos/<owner>/<repo>/rulesets/16082567` → remove the `trunk-check` entry from the
  `required_status_checks` rule's parameters → `gh api --method PUT …/rulesets/16082567 --input -`.
* **Verify it works BEFORE relying on it.** M4 rehearses the rollback immediately after the smoke test
  of cell 17: remove the context, confirm a previously-blocked merge becomes possible, then re-add it
  and re-run cell 17. An untested rollback is a plan, not a remedy.
* **Both ruleset writes here carry M4's readback discipline** — the rehearsal in M4a and any real
  incident rollback. Capture the canonical ruleset before and after, admit **exactly one semantic
  difference** (the `trunk-check` entry appearing or disappearing), and confirm every other rule,
  enforcement setting, bypass list and target condition is byte-identical. An emergency edit made
  under pressure is *more* likely to carry an accidental change, not less, and this plan already
  requires that discipline of the M4 write that is made calmly.
* **Then re-enter at M3** — the gate returns only through the same evidence path that admitted it.

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
2. **§3b's detector has this caller**, so **M6 is unconditional** and COREDEV-2801 keeps its
   detector. **It is not the detector's only caller** — §3b wires a project `SessionStart` hook as
   well, because that is the surface that fires while a stale install is actually running. This
   section decided the *trunk check's* home; it did not make the detector single-surfaced, and
   revision 7 left that claim standing here (codex, r7).

**Accepted cost:** the measured single-file run was ~7s against sub-second today. **That is one
datum, not the envelope** — M5a measures the cold-cache and large-changeset upper bound before the
timeout constant is fixed, and the accepted per-commit cost is restated there from the measurement.

### 6.4 — `markdown-link-check` — RESOLVED as a declared exclusion

Revision 2's recommendation contradicted §1. Under §1's corrected rule (no *undeclared* filter), the
resolution is a **declared, enumerated, cell-enforced exclusion**: `markdown-link-check` is excluded
from the required job and runs in the scheduled advisory job (COREDEV-2778).

**THE DECLARED LITERAL — stated here once, and referenced everywhere else** (codex + agy, r5: §1 and
cell 9 both demanded a whole-string match against a value no section ever defined, so the cell was
unexecutable):

```
--filter=-markdown-link-check
```

That exact scalar is the whole permitted value of the job's `arguments:` input. §1 and cell 9 point
at this declaration rather than restating it — a derived value stated twice goes stale, and two stale
copies agree with each other.

**The local pre-commit check (§6.3) excludes it too**, for the same reason and one more: a network
round-trip per commit, failing on someone else's outage, is exactly the "gate red by default" trap
§1 rejects. Link-checking stays in the scheduled job on both surfaces.

**And it is ENFORCED on both surfaces, not only the CI one.** Cell 9 asserts the workflow's
`arguments:` equals this literal as a whole string; **cell 13 asserts the same literal in the
pre-commit invocation**, with the same whole-string match and the same mutants (appended flag, absent
argument). A literal that is required in two places and checked in one is a declaration, not a
control.

**Losing cost, previously unstated (codex, r2): no merge-time detection of newly broken links.** A
PR may introduce a dead link and merge; the scheduled job reports it afterwards. Accepted, because a
required gate that fails on someone else's outage is worse — but it is a real loss, not a free win.

## §7 — Files Changed

* **`scripts/ci/resolve-trunk-range.sh` — NEW.** The single shared range resolver (cell 1): the
  workflow's empty-diff guard step, the canary's guard step, and `trunk-parity-harness.yml` all invoke
  *this* script, so parity is a property of one implementation rather than an agreement between
  independently-written resolvers that might all be wrong.
  Pinned by **C6a's own `content_digest` entry** — *not* by C8's run-body digest, which cannot reach a
  file the body merely invokes (draft check, r27). **Created by M2**, because the required workflow's
  guard invokes it from the moment that workflow exists — M2a and M2b carry it to `alpha` and to the
  canary, and M2c's harness invokes the same file. Two statements previously named different creators
  (M2 and M2c), and under the M2c reading `main` would get a workflow whose guard invokes a script that
  is not there; named here
  because revision 26 required "one shared shipped script" and inventoried none (codex, r27).
* **`docs/planning/COREDEV-2780-contract.yaml` — NEW.** The structured contract registry: one entry
  per atomic obligation, each with a stable id, a **typed target kind** (`yaml`, `repo_fixture`,
  `content_digest`, `remote_relation`) and **one or more mutation cases** — operator and side, target,
  payload or fixture, validity check, and expected diagnostic. §1's C0–C9 **and C6a** prose is rendered from it,
  cell 11's mutants are generated by iterating its **cases**, and cell 15 asserts prose and registry
  agree. It exists because "derived from the clause text" is not a mechanism when the clause text is
  prose (codex, r13); it is typed and case-bearing because a flat `(id, path, value)` schema could not
  express C6's fixtures, C2's remote relation or C8's digests (codex, r14–r15). *This description was
  itself stale at revision 15 — it still recited the flat schema (codex, r15).*
* **`docs/planning/COREDEV-2780-survivors.yaml` — NEW.** The survivor corpus: every mutant that has
  survived a round of this gate, maintained **independently of the registry** so that a registry edit
  silently dropping an obligation reddens something the rendering lint cannot see (§1).
* **`.github/workflows/trunk-check.yml` — NEW.** The `trunk-check` job lives in its own workflow and
  satisfies **§1's contract, clauses C0–C9 and C6a** — the **workflow-root allowlist with `permissions`
  pinned by value**, the event set and its option allowlist, the branch filters and `types:` set, the
  absence of anything that skips or masks, the `with:` allowlist, the `env:` prohibition, the
  repository-supplied-launcher guard, the merge-queue stop, the frozen step sequence and run-body
  digests, and the action's exact SHA pin — **eleven clauses, C0 through C9 plus C6a** — the shared resolver's own
  `content_digest` obligation; the gloss said nine before C0 existed and ten before C6a did, and a
  count that trails the contract is how a clause ends up unenforced (codex, r28). Plus §6.1's `save-annotations: true` with `contents: read`, §6.4's `arguments:`
  literal, and the **five-step sequence** (checkout, the C6a resolver-digest guard, the empty-diff
  guard, the C6 launcher-path guard, the action). **Values are stated in §1 and §6, never here** — this
  is a file inventory, and revision 9's copy of the contract into this entry is exactly the
  divergence risk §1's singularity exists to remove (codex, r9).
* **`.github/workflows/trunk-check-push.yml` — NEW.** The non-required `trunk-check-push` canary
  (§1's C1): `on: push` with the ruleset's branches, the same SHA-pinned action and checkout,
  `continue-on-error: true` permanently at **job scope**. Created by M2b, asserted by cell 16. Revision 20 required
  this file to exist and listed it nowhere (sweep).
* `.github/workflows/plugin-ci.yml` — unchanged by this ticket; it keeps its `workflow_dispatch`,
  which is exactly why `trunk-check` may not live in it
* `scripts/tests/test_transcript_path_inventory.py` — class-specific content-addressing; `:342` and
  `:358` updated
* `docs/planning/COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json` — `line`, `destination.line` and both
  anchor lines demoted to hints for prepend-only sites
* `CLAUDE.md` — gate-list update
* **`.claude-plugin/plugin.json`, `README.md` (H1 + newest `### vX.Y.Z` + bold asset counts), and
  `CHANGELOG.md` — THE VERSION BUMP, which revision 19 omitted entirely** (codex, r20). This repo's
  rule is that **every change that ships bumps the version**, because `marketplace.json` carries no
  version field and `plugin.json` is the only signal an installed plugin has that anything changed —
  an unbumped fix is a fix nobody receives. The `.githooks/pre-commit` and detector changes here are
  exactly that kind of change, and as planned they could have landed without the signal consumers use
  to pull them. `validate-version-sync.sh` asserts all four sites (`warn` in pre-commit, `strict` in
  CI, so a partial bump commits cleanly and fails CI).
* `.githooks/pre-commit` — the `--index`-scoped, `--no-fix`, bounded, exit-code-aggregating trunk
  check (§6.3 decided: wire it), **and** the §3b detector call
* **`scripts/detect-plugin-version-drift.sh`** — the §3b detector, named here rather than left as
  "the detector script" (codex, r5), so cell 8 has a concrete entry point
* **`.claude/settings.json`** — a project `SessionStart` hook invoking that detector, the surface
  that fires while a stale install is actually running (§3b)
* **`scripts/tests/test_trunk_check_workflow.py`** — cells 4, 9, 11, 14 **and 15** (workflow parsing, the
  frozen membership set (cell 4 holds the names and the count — this list does not restate them),
  the `arguments:` literal, the producer census, **cell 10's static `permissions` assertion**,
  **cell 16's canary-shape assertions**, cell 15's runner/timeout and its registry-vs-rendered
  comparison, and the **generated** mutant set)
* **`scripts/tests/test_precommit_trunk_gate.py`** — cell 13's index/worktree, `--no-fix`, timeout
  and exit-aggregation controls, and cell 8's pre-commit entry point
* **`scripts/tests/test_trunk_check_behaviour.py`** — **new**: the *constructible* halves of cells 3
  and 5 — building the historically-dirty and deliberately-fixable fixtures and hashing them. It does
  **not** own cells 2 or 3's observed outcomes; the ownership table below is authoritative, and
  revision 17's inventory contradicted it (codex, r18)
* **`docs/planning/evidence/COREDEV-2780-rollout.json`** — **new**: cells 10 and 12, **cell 2's M2
  step-**conclusion** and M3 job-conclusion observations with their `trunk_step_diagnostic` field
  (the workflow-jobs API exposes `conclusion`, never `outcome` — codex, r20), **cell 16's ruleset read
  and its canary runtime control**, **cell 17's post-M4 enforcement smoke test and the §6.2a rollback
  rehearsal (M4a)**, cell 3's observed PR outcomes, C2's live-ruleset
  half**, and cell 8's real `SessionStart` invocation. Provenance-bound observations of things a real
  run **reports** — never runner-local state that vanishes with the job, which is why cell 5's
  post-invocation hash moved to the harness (codex, r18)
* **`.github/workflows/trunk-parity-harness.yml` (NEW, non-required) + `scripts/tests/test_trunk_upstream_parity.py`.**
  **A Python unittest cannot run a composite action (sweep)** — `uses:` is resolved by the Actions
  runner, not by `unittest`, so revision 20's owner could not execute the mechanism it described. The
  split: the **workflow** is the sensor — it runs the pinned action against per-event fixtures with an
  instrumented launcher, and uploads the captured argv and post-run tree hashes as an artifact; the
  **Python test** asserts against that artifact. Same shape as cells 10/12: a real run reports, a test
  judges. **The harness's action inputs are EXTRACTED from `.github/workflows/trunk-check.yml` and
  digest-bound to it, not written independently** (codex, r21): a harness that invokes its own
  non-fixing form proves only that *that* form does not mutate, while the shipped job could invoke an
  autofixing one and still reach this cell green. The harness must run what ships. Carries cell 1's range parity and cell 5's post-invocation comparison: it runs the pinned action against per-event fixtures
  with `trunk-path` pointed at a recording launcher and compares the captured range byte-for-byte
  against the guard step's output. *(The harness is the one legitimate use of `trunk-path`; §1's C4
  forbids it in the shipped workflow.)*
* **`scripts/tests/test_session_start_drift_hook.py`** — §3b's `SessionStart` contract: matcher set,
  `${CLAUDE_PROJECT_DIR}` resolution, the `O_EXCL` dedup marker under concurrent invocation, the
  `systemMessage` output shape, and the timeout against a sleeping detector (cell 8, SessionStart half)

**Ownership follows a RULE, and the table below applies it** — revision 9 claimed every cell had an
owner and five did not; revision 12 gave cell 2 an owner that **cannot observe what the cell
asserts** (codex, r12: a Python test cannot see a GitHub step outcome or a job's final conclusion).
Assigning owners one at a time reproduces that error, so the rule is stated first:

> **A cell asserting the outcome of a real GitHub run — a step conclusion, a job conclusion, a check
> run — is owned by the provenance-bound rollout evidence artifact; but only for what a run
> REPORTS, never for runner-local state that vanishes when the job ends (codex, r18). A cell asserting file or
> configuration content is owned by a Python test. A cell asserting a relationship between local
> content and REMOTE state is a HYBRID: it is split, and each half owned by whichever can observe it.
> No cell may be owned by something that cannot observe the thing it asserts.**

**The hybrid case was missing and C2 is one (codex, r13):** it requires the workflow's `branches:` to
*equal the live ruleset's target set*, and the workflow-parsing Python test can see the YAML but not
the remote ruleset — while this plan elsewhere insists those target conditions are live configuration
and must not be assumed. So C2 splits: the Python owner asserts the local shape and that the set is
non-empty; the **authenticated evidence artifact** asserts equality against the ruleset as read at
rollout time, alongside cell 12's other provenance-bound observations.

Applying it moves **cell 2** (both its M2 step-*conclusion* half and its M3 job-conclusion half) and the
observed-run parts of **cell 3** to the evidence artifact, alongside cells 10 and 12:

| cell | owner |
|---|---|
| 1 | **hybrid**: the `trunk-parity-harness.yml` workflow is the **sensor** — it runs the pinned action against per-event fixtures and reports the captured range; `test_trunk_upstream_parity.py` is the **judge**. Revision 22 named only the judge here while §7's inventory described the split correctly (codex, r23) |
| 2 | `evidence/COREDEV-2780-rollout.json` — **by the rule**: both halves assert a real run's outcome (the Trunk step at M2, the job conclusion at M3), which no Python test can observe |
| 3 | `evidence/COREDEV-2780-rollout.json` for the observed PR outcomes; `test_trunk_check_behaviour.py` for the fixture construction |
| 5 | **hybrid**: `test_trunk_check_behaviour.py` constructs and hashes the deliberately fixable fixture; the **`trunk-parity-harness.yml` workflow** runs the pinned action and reports the post-invocation hashes, which `test_trunk_upstream_parity.py` asserts against — a unittest cannot itself run a composite action (sweep). *Not* the evidence artifact — C8 makes the action the final step, so nothing in the required workflow can hash the tree afterwards, and an artifact records what something else observed (codex, r18) |
| 4, 9, 11, 14, 15 | `test_trunk_check_workflow.py` (parse + census + generated mutants + runner/timeout) |
| 17 | `evidence/COREDEV-2780-rollout.json` — **by the rule**: it asserts the live ruleset's *behaviour* (a merge attempt refused, then a green one accepted), which nothing static can observe |
| 16 | **hybrid**: `test_trunk_check_workflow.py` asserts the canary workflow's *static* shape — job-scoped permanent `continue-on-error`, SHA pins, both guards and their shared resolver, C5's `env:` prohibition, C6's launcher guard, `permissions` by value, and that `branches:` is well-formed and non-empty. **`branches:` EQUALLING the ruleset's live target set is a local-vs-remote comparison** and therefore hybrid under §7's own rule, exactly as C2 is for the required workflow — the evidence artifact carries that half; `evidence/COREDEV-2780-rollout.json` carries both *runtime* halves — the ruleset read showing `trunk-check-push` absent from the required contexts, **and** the control proving the Trunk step stays observably failed while the job stays non-blocking. Revision 25 assigned that runtime control to the Python owner, against the rule three paragraphs above |
| 6, 7 | `scripts/tests/test_transcript_path_inventory.py` — the existing suite, named here rather than implied |
| 8 | `test_session_start_drift_hook.py` (SessionStart *declaration*) + `test_precommit_trunk_gate.py` (pre-commit entry point) + `evidence/COREDEV-2780-rollout.json` (the one real session-start invocation — the runtime half, which no test file can carry; codex, r11) |
| 10 | **hybrid**: `test_trunk_check_workflow.py` pins `permissions` by value at both scopes (a wider token yields identical runtime evidence, so only a static check discriminates it — codex, r25); `evidence/COREDEV-2780-rollout.json` carries the annotation-artifact observation |
| 12 | `docs/planning/evidence/COREDEV-2780-rollout.json` — **evidence, not a unit test**: the annotation artifact and the dual-base provenance-bound check runs are observations of real runs, recorded as a committed artifact the way COREDEV-2711 §3a's measurement was. Saying so is what makes them ownable |
| 13 | `test_precommit_trunk_gate.py` |

## §8 — Notes

**Revision 1's largest defect was not technical.** It was written without reading COREDEV-2771's
planning document, which contains a section addressed to this ticket handing over six reviewed
defects. Both reviewers re-derived that work. Grep `docs/planning/` for the predecessor first.

**Revisions 20-22 share one mechanical failure: I APPENDED corrections instead of DELETING what they
replaced.** Each time the new rule and the superseded rule stood side by side as normative text, and
an implementer following either would be within the document — §3b told both surfaces to read
`origin/main` in one paragraph and sent pre-commit to the index in the next; C0 was added while every
authoritative range still enumerated C1–C9; cell 1 carried a corrected scope directly above a sentence
asserting the old one; a freshness rule was written that contradicted Table A's silence rule. This is
**distinct from the fix-one-site family**: there a sibling was *missed*, here the original was *left
standing deliberately*, as history, in a document whose reader cannot tell history from specification.
**A correction that does not delete is not a correction — it is a second opinion.** Revision 23
deletes, and the round records at the top of this document are where superseded designs belong.

**Revision 13's two new mechanisms were both holed by the round that reviewed them — and that is
the mechanisms working, not failing.** Asked to attack the derivation and the ownership rule directly
rather than hunt one more missing mutant, codex found that "derived from the clause text" **is not a
mechanism at all** when the clause text is unrestricted prose, and that the ownership rule had no case
for a **hybrid** assertion comparing local YAML to live remote state. Both are now closed by making
the contract *structured*: there is no prose to parse, mutants are generated rather than listed, and
the rendered clauses are linted against their source. **A rule that a reviewer can hole in one round
is better than a list that quietly under-covers for five** — the previous five rounds each found a
different missing mutant, and none of them found the reason there would always be another.

**Revision 10 is where the two arms stopped agreeing, and that was the point.** agy returned the
campaign's first `APPROVE`, walking clause by clause through C1–C9 and pronouncing the contract
complete — including a paragraph describing C6's guard adjacency and another describing C8's step
order, **without noticing that the two contradicted each other.** codex found it: C8 placed the
empty-diff step between C6's guard and the action, so an allowlisted step sat exactly where it could
create a prohibited path *after* the guard had run, and neither existing mutant could kill it. **An
approval is evidence, not proof** — and a reviewer that restates both halves of a contradiction in
adjacent sentences has demonstrated coverage without demonstrating discrimination, which is the same
defect this plan's own cells kept having.

**Revision 9's most useful finding was one this plan should NOT act on.** Asked to enumerate the
execution surface end to end, codex returned eleven [SUBJECT] findings — up from four — and three of
them were true statements about *Trunk and GitHub Actions* rather than defects in this plan: the
launcher is downloaded without a digest check, linters come from a tag-pinned plugin source, and
Actions caches are unsigned. All real. None closeable without abandoning the action the maintainer
chose to keep. **A review can be correct and still be answering a question the work is not asking**,
and the tell was the count rising as the prompt widened. §0 now states the threat model so that
observation resolves instead of re-opening, and COREDEV-2803 carries the work if the exposure ever
justifies it. The concordant signal was elsewhere and much smaller: both arms independently found the
five unowned cells, the `lint.definitions` override, and one wrong cross-reference.

**Revision 8's largest defect was closing one door on a hallway.** The r7 allowlist correctly
constrained what the *caller* passes — and the action takes its launcher from three other places the
caller never mentions: a checked-out `.trunk/bin/trunk`, `tools/trunk` or `./trunk`; a checked-out
`.trunk/setup-ci` that it *executes*; and `TRUNK_PATH` from the job or step `env:`. **A pull request
could supply the tool that tests it** — for a required merge gate, the gate handing its own authority
to the thing under test.

The general lesson, now paid for three rounds running: **an allowlist over one input channel is not
an allowlist over the execution.** Ask what the tool will actually *run*, and enumerate every place
that answer can come from — caller inputs, environment, and the repository being tested. The last of
those is the one that felt unthinkable and is the one an attacker controls.

**Revision 7's largest defect was that its prohibition set was a BLACKLIST.** Cell 11 named
everything it could think of that would let the job report green without linting — triggers,
conditionals, `needs:`, matrices, `continue-on-error` — and the pinned action simply offers another
door: `trunk-path` names *the launcher it executes*, and `post-init` is documented as "a
caller-controlled escape hatch". A no-op launcher exiting 0 satisfies every clause and lints nothing.
**This repo has paid for blacklists before**, on COREDEV-2626 and again on COREDEV-2691, where an
allowlist added in one round was escaped in the next. Enumerating what is *permitted* is the only
form that denies an input invented after the rule was written.

The same round showed the property itself had been under-stated twice: "no conclusion" was false
(cancellation reports one, and blocks), and "no success" was too narrow — GitHub counts `skipped` and
`neutral` as satisfying a required check too. **The property is what a merge accepts, not what a run
prints.**

**Revision 5's largest defect was that its fix made the hazard WORSE, silently.** Revision 4
replaced an unsupported job-level `on:` with a valid `if:` guard — and a job skipped by a conditional
**reports Success to a required context**. So the guard converted "the job runs in the wrong mode on
dispatch" into "the job reports green without running at all", and cell 11 asserted the guard, which
means **the cell certified the bypass**. Two revisions in a row, the cell tested the *mechanism I had
chosen* rather than *the property the mechanism was for*. The property — no state in which
`trunk-check` reports a **merge-satisfying** conclusion without a **real** Trunk run — is what cell
11 now asserts. Revision 7 still wrote it as "no conclusion", which is false (cancellation and
failure report conclusions; they just block) and too narrow (`skipped` and `neutral` satisfy a
required check as surely as `success`). It is met by removing the trigger, allowlisting the action's
inputs, and requiring one unconditional invocation of the real launcher — not by guarding.

**Revision 4 also replaced a confounded control with an impossible one.** Told that cell 7's
restored-legacy-source case reds through an independent check, I required a mutation test showing the
case "goes green" without the assertion under test — which that same independent check makes
unreachable. **A cell that cannot pass is the mirror of one that cannot fail.** The observable had to
be the specific diagnostic, not the case outcome.

**And the fix was applied to one member of a family.** Cell 7's confounding was repaired; cell 6 had
the identical defect in two of its three controls and was left alone, because the finding named 7.
That is the recurring shape in this repo — **derive the family, do not fix what the finding named.**

**Revision 3's largest defect was fixing a contradiction into an impossibility.** Told that
`workflow_dispatch` forces `check-mode=all`, revision 3 wrote a job-level `on:` — a key that does not
exist at job scope, so the job stayed reachable on dispatch and the cell that was supposed to catch
that asserted a prose property no parser could evaluate. **A fix expressed in a construct the platform
does not have is not a fix, and a cell phrased as prose cannot tell the difference.** Both arms caught
it. **That fix was itself superseded in revision 6** — the literal `if:` guard reported Success on a
skip, so the trigger was removed instead. This sentence described a design two revisions dead until
agy r6 caught it: **a correction written into the notes is not a correction to the design**, and
prose about superseded mechanisms is exactly where stale text hides from a diff.

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
