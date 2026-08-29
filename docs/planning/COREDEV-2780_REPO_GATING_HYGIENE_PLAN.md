# Repo Gating Hygiene Plan — trunk in CI, pin drift, and stale install resolution

**Status:** Planning, revision 12
**Created:** 2026-08-28
**Last Updated:** 2026-08-28
**Basis:** `c913303` (origin/main, plugin 2.8.3) · **Tickets:** COREDEV-2780, COREDEV-2798, COREDEV-2801

> **r1** `04048c7`: codex + agy both `REQUEST_CHANGES`. Concordant: §2's fix was wrong for
> `rewrite`-class sites, and the M1→M2 precondition was false.
> **r2** `b2ca1b0`: codex `REQUEST_CHANGES` (7 DESIGN) + agy `REQUEST_CHANGES` (2 DESIGN), concordant
> on the alpha landing precondition and on §6.1 option (b) being unimplementable as written. codex
> read the pinned action's **source at its SHA** and found two self-contradictions in this plan.
> Revision 3 closed all nine.
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
> `uses: ./.trunk/setup-ci` is at `action.yaml:289` at the pinned SHA, exactly as cited — **it
> repeated the claim in r11 with a third number (266, then 267), and the citation was re-verified
> from two independent fetches (the contents API and `raw.githubusercontent.com`) that are
> byte-identical. The line is 289.**
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
whose `on:` contains `pull_request` and `push` and *no* `workflow_dispatch`.** The job is then
unreachable on dispatch by construction rather than by condition, so there is no skipped-success
state to exploit.

**BRANCH filters are required; PATH filters are prohibited (codex, r6).** Revision 6 said `push` was
scoped "to the gated bases" *and* banned every filter — **authorising no configuration at all**. The
distinction the GitHub doc actually draws is what the two kinds of filter skip on:

* **`branches: [main, alpha]`** — REQUIRED, on both `pull_request` and `push`, and it must match the
  ruleset's target set exactly. A PR into an ungated base does not need the context, so nothing is
  left pending; a mismatch in either direction is the COREDEV-2767 shape.
* **`paths:` / `paths-ignore:`** — PROHIBITED. These skip on *changed files*, so a PR into a gated
  base that touches only excluded paths requires a context the workflow never produces, leaving it
  **Pending, which blocks merging** — a false pass traded for a permanent block.

**No `if:` on the job, and none on the Trunk step** — see cell 11 for the full prohibition set.

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
* **THE WORKFLOW CONTRACT — stated here once, and referenced (never restated) everywhere else.**
  Revision 8 copied the event set and the input allowlist into §1, M2, cell 11 and §7, **and they had
  already diverged** — only cell 11 permitted `merge_group` (codex, r8). This block is the single
  authority; cell 11 asserts these clauses by name.

  **C1 — events.** Exactly `pull_request` and `push`. Not a prohibition of two triggers: an exact
  set, so a trigger nobody thought of is excluded by default. **`merge_group` is NOT permitted** —
  see C7.

  **C2 — branches.** `branches:` present on both events, equal to the ruleset's target set.
  **No `paths:`/`paths-ignore:`** — path filtering leaves a required context Pending, which blocks.

  **C3 — nothing skips or masks.** No `if:` on the job or on the Trunk step; no `needs:`; no
  `strategy.matrix`; no `continue-on-error` at job or Trunk-step level. Exactly one unconditional
  Trunk invocation.

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
  exits 0. Forbidding `env:` outright at both levels closes it without depending on the precedence
  between job `env:` and `GITHUB_ENV`.

  **C6 — the REPOSITORY may not supply the tool that tests it (codex, r8).** Verified at the pinned
  SHA: `setup/locate_trunk.sh` uses a checked-out `.trunk/bin/trunk`, `tools/trunk` or `./trunk` in
  preference to downloading, and `action.yaml:289` *executes* a checked-out `.trunk/setup-ci` as a
  composite action, which can rewrite `TRUNK_PATH` through `GITHUB_ENV`. A PR adding any of those
  greens its own required gate. **The job therefore carries a guard step, immediately before the
  action, that fails if any of those four paths exists in the checked-out tree** — and that also
  fails on the presence of **`.trunk/user.yaml`** or **`.trunk/env.yaml`**, which override the
  configuration cell 4 freezes (both arms, r9).

  **C8 — the job's step sequence is an allowlist, in order.** Exactly: `actions/checkout` (SHA-pinned)
  → the empty-diff guard (cell 1) → **the C6 guard** → the action. No other step may exist.

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
  are not there. That is an *accident*, squarely inside §0's threat model. Only `fetch-depth` may be
  set; every other input must be absent.

  **And the two permitted `run:` steps are frozen BY CONTENT, not merely by position (codex, r11).**
  Freezing the sequence stopped a *new* step being added; it did nothing about what the allowed steps
  *do*. Either may write `TRUNK_PATH=/bin/true` or `BASH_ENV=…` to `$GITHUB_ENV`, and the C6 guard
  inspects paths, not inherited runner state — so the action would resolve a no-op launcher while
  every clause C1–C9 passed. **Each run body is pinned by digest, and neither may write to
  `$GITHUB_ENV` or `$GITHUB_PATH` at all.** Changing either step is then a reviewed change, which is
  the same standing the workflow itself has. Revision 9
  banned `env:` but nothing stopped an *extra step* from appending to `GITHUB_PATH`, setting
  `BASH_ENV` through `GITHUB_ENV`, or creating one of C6's prohibited paths **after** the guard had
  already run (codex, r9). Freezing the sequence closes the ordering hole and the injection hole
  together; the guard's adjacency to the action is part of the assertion, not a convention.

  **C9 — the action itself is pinned by exact SHA.** `trunk-io/trunk-action@e1234e67…` — nothing in
  C1–C8 required it, and cell 9 asserted only that `actions/checkout` was pinned, so a tag or a
  different SHA satisfied every other clause (codex, r9).

  **C7 — a merge queue is a STOP, not a configuration (codex, r8).** Revision 8 let M4 add
  `merge_group` if the preflight found a queue. At the pinned SHA that is the forbidden false
  success: `determine_check_mode.sh` matches `merge_group` in **no** branch, so it falls through to
  `check_mode=none`, every real step is skipped, and the composite action **succeeds** — and C4
  forbids forcing `check-mode` to repair it. So if M4's preflight finds a merge queue on `Control`,
  **stop and redesign** — a compatible action revision, or an explicitly validated mode, chosen and
  tested before the context is required. Never add the trigger and hope.

  **Residual risks, named rather than implied.** *(a)* This contract enumerates the extension points
  that exist **at the pinned SHA**; a future version may add another, so a Dependabot pin bump must
  re-run cell 11's mutants rather than being merged as routine. *(b)* For `pull_request` events the
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
against dead code. **The callers are `.githooks/pre-commit` and the project `SessionStart` hook** —
revision 7 added the second surface below while this sentence still named one, and §6.3 repeated the
single-caller claim (codex, r7).

**Why that one, and why it survives the bootstrap problem.** A session bound to 2.7.0 cannot execute
a detector shipped only in 2.8.4+. The hook is not shipped by the plugin — it lives in the
**checkout** and runs from it, so it is current regardless of which install a session loaded. It
compares `~/.claude/plugins/installed_plugins.json` against the repo's
`.claude-plugin/plugin.json`, needing no session environment and no plugin code.

**Which copy of that manifest, per surface (codex, r7).** The pre-commit surface claims to catch "a
version claim about to be committed" — so it must read the **staged** manifest,
`git show :.claude-plugin/plugin.json`, not the worktree file. Reading the worktree would warn, or
stay silent, about bytes that are not being committed, and it is the same index-versus-worktree
confusion cell 13 already forbids for the trunk check. The `SessionStart` surface reads the
**worktree**, because that is what the live editing session observes — **not** because it lacks an
index; a normal checkout has one, and revision 8's rationale was simply false even though the
behaviour it justified is right (codex, r8).

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

**Table A — the detector at runtime.** Evaluated per scope entry; `expected` is the version in
`.claude-plugin/plugin.json`.

| # | condition | detector |
|---|---|---|
| 1 | `expected` cannot be read, or the manifest is malformed | **silent**, record — with no expected value there is nothing to compare against (codex, r7) |
| 2 | the record is unreadable, or its schema is unrecognised | **silent**, record the observed shape |
| 3 | the entry is absent | **silent** |
| 4 | either version is present but **not comparable** | **silent**, record — revision 7 assumed comparability and left this unassigned (codex, r7). **Comparable means parseable under SemVer 2.0.0**, and rows 6–8 order by its precedence rules (agy, r8) |
| 5 | the versions are of **equal precedence but not identical** — SemVer ignores build metadata, so `2.8.3+local` and `2.8.3+repo` are neither `<` nor `>` nor the same string | **silent**, record. Revision 9 called row 5 "exact version" while ordering by precedence, so this pair reached the `> expected` catch-all whose description was false of it (codex, r9). `==` in rows 6–8 means **exact identity**; equal-precedence-but-different is handled here |
| 6 | `installed == expected` | **silent** — the healthy state is not a warning |
| 7 | `installed < expected` | **warn** — the drift this detector exists for |
| 8 | otherwise (`installed > expected`) | **silent** — a locally newer install is not drift; warning here fires on every development clone |

The hook warns if **any** entry reaches row 7, and never blocks.

**Table B — what the §3a experiment establishes.** The experiment runs `claude plugin update` at
**user scope** and re-reads the record; `u` and `p` are the user and project entries.

| # | condition | establishes |
|---|---|---|
| 1 | the command exits **nonzero** | **update-failure** — first, so a partial mutation followed by a failure is never read as success. Containment **not** established |
| 2 | the record is unreadable, its schema is unrecognised, **either `u` or `p` is absent**, or **either** version is not comparable | **no outcome**; record the observed shape. "Either", explicitly: revision 8 said "a targeted entry", which left `u == expected` with `p` absent falling to a catch-all whose description was false (codex, r8) |
| 3 | the persistence interval has not elapsed | **PENDING — not an outcome.** No later row may be claimed yet |
| 4 | **`p` changed at all** — either direction, whether or not `u` moved | **the update acted on a scope it did not target.** Evaluated before the reversion row because a *downward* move in `p` is both, and revision 9's ordering recorded it only as a reversion, losing the untargeted-scope signal (codex, r9; the row it then collided with was **revision 7's** row 5, not this table's — codex, r11). Record both facts; classify here |
| 5 | any entry moved **downward** from a previously observed value | **reversion — the root-cause signal.** COREDEV-2801 stays open with the detector as its instrument. Covers reversion to *any* lower version, not only `2.7.0`, and by ordering it can no longer collide with row 5 as it did in revision 7 |
| 6 | any entry is `> expected` | **not drift**; the run is non-evidence rather than a result |
| 7 | `u` changed to a version of **equal precedence but different identity** (`2.8.2+old` → `2.8.2+new`) **and `u != expected`** | **no outcome**; record. It moved, so the final row's "did not move" is false of it; it did not advance, so no advance row is true either. Revision 10 left this input matching **nothing** (codex, r10), the mirror of Table A's row 5. The
`u != expected` qualifier is load-bearing: without it the row **stole a genuine containment result**
— if `expected` itself carries build metadata, `u` arriving exactly at it is an equal-precedence
identity change *and* a success, and row 7 would have reported "no outcome" (codex, r11) |
| 8 | `u == expected` and `p == expected` | containment established for both, though the experiment aimed at one |
| 9 | `u == expected` and `p < expected` | the **expected shape**, since only user scope was updated. Containment established **for user scope only** |
| 10 | `u` moved **upward** but is still `< expected` | **partial advance** — it changed without arriving. Containment **not** established. *Upward* is explicit: revision 7 classified a downward move as a partial advance (codex, r7) |
| 11 | otherwise — `u` is `< expected` and did not move, `p` unchanged | the update **did not act on the scope it targeted**. Containment **not** established. Reachable only after rows 1–9, so its description is now true of everything that reaches it |

**The terms both tables depend on** (codex + agy, r5 and r6 — earlier versions were neither
exhaustive nor mutually exclusive):

* **"advance"** means the entry equals **the exact version expected** — not merely "changed", and
  not "greater". "Moved but short of expected" is its own outcome, not an advance.
* **Comparison is directional**, per Table A: below expected is drift, above it is not.
* **The command's exit code outranks the record** — the first row of Table B, evaluated before any
  entry is compared.
* **Persistence needs a named interval**, recorded with the run; before it elapses the result is
  *pending*, which is why Table B carries an explicit interim row rather than leaving a gap.
* The **record's readability and schema** are captured on every run, so an unrecognised shape is
  distinguishable from drift in both tables.

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
    `${XDG_STATE_HOME:-$HOME/.local/state}/unleashed-mail/drift-warned/<session_id>` — **not**
    `${CLAUDE_PLUGIN_DATA}`, which revision 10 used and which is scoped to *plugin*-associated hooks
    while this hook deliberately lives in project `.claude/settings.json` (codex, r10). The chosen
    path needs no plugin identity and matches the convention this repo already uses for review
    transcripts. It is created with `O_EXCL` **before** the warning is
    emitted, so two concurrent invocations cannot both warn and a crash between create and emit fails
    silent rather than warning twice. Markers older than **7 days** are swept on entry.
  * **Output protocol** — the warning is emitted as **`{"systemMessage": "…"}`**, not bare stdout
    (agy, r8). A `SessionStart` hook's plain stdout is injected into the **agent's context**, so a
    warning printed that way is read by the model and never seen by the developer — a detector whose
    output only the assistant can see does not warn anyone.
  * **Timeout** — **`timeout: 5`** (seconds), declared on the hook entry. The default for a
    synchronous command hook is **600 seconds**, and a detector that can hang a session start for ten
    minutes is worse than the drift it reports. Five seconds is ~100x the detector's work (two small
    JSON reads); anything slower than that is a broken detector, and failing fast is the right answer.
  * **Mode selection** — the detector takes an explicit mode operand (`--index` for the pre-commit
    surface, `--worktree` for this one) rather than inferring it from the environment; the two
    surfaces read different bytes on purpose, and inference is how they would silently converge.

  Cell 8 exercises the matcher set, the timeout against a sleeping detector, the dedup marker under
  concurrent invocation, and the `systemMessage` shape;
* **`.githooks/pre-commit`** — catches a version claim about to be committed, and covers the case
  where hooks are disabled in the session but not in git.

**M6 is unconditional** because §6.3 is decided, not because no alternative existed — and the
alternative turned out to be complementary rather than competing.

## §4 — Milestones

- [ ] **M0** — *(decided, §6.0; refined in r3)* bring `alpha` up to date with `main` (611 commits,
      0 ahead). **This alone lands the trunk configuration on `alpha`**, because `.trunk/trunk.yaml`
      is already present on `origin/main` — verified. COREDEV-2771's separate-PR requirement is still
      met: the config arrives on the sync PR, which is not the PR that adds the job. Revision 3's
      second step was therefore redundant work on an already-satisfied precondition.
- [ ] **M1** (independent of M0/M2) — COREDEV-2798 class-specific content-addressing, anchors
      demoted, `:342`/`:355` updated, cells 6–7 with negative controls.
- [ ] **M2** (**after M0**) — add the `trunk-check` job, diff-scoped, `continue-on-error: true`, in
      its **own workflow file** `.github/workflows/trunk-check.yml`, satisfying **every clause of
      §1's contract, C1 through C9 — except C3's `continue-on-error` prohibition, which M2 is
      deliberately and temporarily exempt from** (codex, r10: M2 ships `continue-on-error: true` while
      C3 forbids that exact key, so an unqualified "every clause" contradicted the milestone it
      described). The exemption ends at M3, where cell 11's C3 mutants are enabled. This list deliberately does **not** restate their values
      (codex, r9): revision 9 claimed the contract was stated once and then copied it into M2 and §7,
      which is how the trigger set diverged in the first place. §1 is the authority; cell 11 is the
      enforcement. Read them, do not paraphrase them.
- [ ] **M2a** (**after M2 — the step revision 3 was missing entirely, codex r3**) — land the job on
      `alpha` too. GitHub runs the workflow **version present at the event's ref**, so a job merged
      only to `main` never executes for an `alpha` PR: `alpha` would carry the config but emit no
      `trunk-check` check run. Requiring the context at M4 would then make it **unsatisfiable on
      `alpha`** — COREDEV-2767's exact failure, aimed at the other protected base.
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

      **Immediately before the ruleset edit, re-fetch both base tips** and confirm each still carries
      a byte-equivalent strict job. **"Immediately before" is still a read/edit race**, so verify
      again *after* the edit — both tips, the effective check name, the required context and its
      expected integration, **and the ruleset's own target conditions** (the `main`/`alpha` set is
      live configuration, not a constant this plan may assume — codex, r7) — and roll the rule back
      if any of them moved.

      **Open PRs predating M2/M2a** will not have produced the context and will sit pending until
      rebased or updated (agy, r6). Enumerate and rebase them as part of the change, not after it.
- [ ] **M5** — run §3a; record the outcome on COREDEV-2801 as containment.
- [ ] **M5a** (**§6.3 decided**) — wire the trunk check into `.githooks/pre-commit`: **`--index`**
      (the staged content, not the worktree), **`--no-fix`**, §6.4's exclusion literal, a
      macOS-portable timeout, and **exit-code aggregation that cannot mask an earlier hook
      failure**. Blocking on newly introduced findings, never `--all`. Update `CLAUDE.md`'s gate
      list. Independent of M2/M4 — it gates commits, not merges. Cell 13 carries the controls.
- [ ] **M6** — implement §3b's detector and wire it to **both** surfaces (§3b): the project
      `SessionStart` hook, which fires when a stale install starts running — the defect as actually
      reported — and `.githooks/pre-commit` (§6.3 decided: wire it). Runtime behaviour per **Table
      A**; the §3a experiment is read against **Table B**. Unconditional as of revision 5.

M3 and M4 are gated on evidence, not schedule.

## §5 — Testing

Cells 1–3 exist because of inherited defect 3 — a gate over an empty diff passes having checked nothing.

1. **The diff is non-empty and correct per event — and the job, not just the test, detects it.**
   Assert the *resolved* upstream/diff on `pull_request`, `push` to `main`, and `push` to `alpha`.
   **The mechanism was missing in revision 3 (agy, r3, in part):** `trunk check` exits **0** when the
   resolved diff matches no files, so the action alone reports green having checked nothing — which
   *is* inherited defect 3. The job therefore carries an explicit step that resolves the diff and
   **fails when it is empty**, before the action runs. **That step's computed range must be proven
   identical to the range the pinned action passes to Trunk** (codex, r6) — two independently
   correct-looking resolvers drift, and a guard that checks a *different* range than the one linted
   asserts nothing about the lint. **"Proven" must name a harness, not a hope (codex, r7):** run the
   pinned action against per-event fixtures with `trunk-path` pointing at an instrumented launcher
   that records its argv, then compare the captured range arguments **byte-for-byte** against the
   guard step's output.

   **One push subdomain runs `--all`, and the guard must refuse it (codex, r9).** At the pinned SHA,
   `push.sh` branches on `GITHUB_EVENT_BEFORE == 0000…0` — the shape GitHub sends when a branch is
   created or a tag is pushed — and runs `trunk check --ci --all`, which is precisely the 9027-finding
   whole-tree run §1 forbids, inside the required context. The empty-diff guard therefore **also fails
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
   * **at M2** — assert the **Trunk step's own outcome** is `failure`;
   * **from M3** — assert the **job's conclusion** is `failure`, which is the property that actually
     blocks a merge.
3. **The gate does not over-reach.** (a) A PR touching one clean file passes with the 9027-issue
   backlog present. (b) A PR touching a **historically dirty** file passes for its pre-existing
   findings while still failing for newly introduced ones.
4. **The configured linter set MEMBERSHIP is frozen in the test, not derived from the configuration
   under test**
   (codex, r5). Revision 5 said "the configured set minus the declared exclusions", which reads the
   expectation out of `.trunk/trunk.yaml` — **making a silently reduced configuration authoritative
   over the assertion meant to detect it**, the exact shape this plan's Overview names. The cell
   instead carries **the 19 expected linter names as literals** (20 enabled, minus
   `markdown-link-check`) **and a frozen digest over the entire `lint:` block**. Fails if any of the
   19 is missing, if an unlisted linter appears, if the exclusion list grows, or if the block's bytes
   change at all — **and it fails when `.trunk/trunk.yaml` is reduced**, which the revision-5 wording
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
   touch the oracle, because the oracle holds names, not versions. A coordinated edit to config and
   oracle together is out of this cell's reach by construction — that is what review is for.
5. **No autofix: the job introduces no tracked-source mutation.** Narrower than revision 9's "never
   mutates the tree", which was false (codex, r9) — the pinned action itself creates `.trunk/setup-ci`
   and appends it to `.git/info/exclude`. The invariant that matters, and that is tested: **no tracked
   file's bytes change**, and no autofix is applied.

   **The fixture must be deliberately fixable (codex, r10).** Running the job over already-canonical
   files proves nothing — autofix would produce no byte change there either, so the cell *reaches* the
   wrong implementation without killing it. The case therefore stages a file a formatter would
   certainly rewrite (mis-indented, unsorted imports) and asserts it is **byte-identical afterwards**.
   Cell 9's static `--fix` prohibition is a separate, weaker check on the configuration; this one is
   about what the run did.
6. **quote-keep — relocation passes, and three wrong implementations fail, each for the RIGHT
   reason** (codex + agy, r5). Prepend to `CHANGELOG.md` → green with no edit. Then: content change →
   red; **duplicate source line → red** (kills "at least one"); and the `:342`/`:355` dependencies
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
     emulator, which is precisely the direct-unit-call this cell forbids. **Split the claim honestly**:
     CI asserts the *declaration* (matcher set, `${CLAUDE_PROJECT_DIR}` resolution, `timeout`, the
     `systemMessage` shape, the `O_EXCL` marker under concurrent invocation **and under aged-marker
     resumption** — a session whose marker was swept past the retention window warns again, which is
     exactly why the promise is per-window rather than per-session (codex, r11) — and the mode
     operand) against the documented stdin contract; and the *real* session-start invocation is recorded once as a
     **committed evidence artifact**, the same standing cells 10 and 12 have. Claiming a CI proof this
     repo's pipeline cannot produce would be a cell that cannot pass.
9. **The job block prohibits what COREDEV-2771 measured.** `check-mode` absent, `post-annotations`
   absent-or-false, no custom `--upstream`, no `--fix`, `actions/checkout` SHA-pinned — and
   **`arguments:` PRESENT and equal to §6.4's declared literal as a whole string** (§1) — absence is
   a failure, not a permitted variant (codex, r5), and an appended argument cannot pass a substring
   test — **and `trunk-io/trunk-action` is pinned to the exact SHA of §1's C9**, with tag-reference
   and different-SHA mutants. Revision 9 asserted only that `actions/checkout` was pinned, so a
   re-tagged or swapped action satisfied every other clause (codex, r9).
10. **The chosen §6.1 annotation mechanism is present and works** on a non-fork PR — no 403. Under
    option (b) that is checkable rather than merely observed: assert the run takes the
    `--github-annotate-file` branch (**not** `--github-annotate`) and that the `trunk-annotations`
    artifact is produced, uploaded by the action's own SHA-pinned `actions/upload-artifact` step
    under `if: always() && env.TRUNK_UPLOAD_ANNOTATIONS == 'true'`. **No added token scope**: the
    upload uses the Actions runtime, not `GITHUB_TOKEN` permissions, so `contents: read` stands.
11. **There is no state in which `trunk-check` reports a *merge-satisfying* conclusion without the
    real Trunk having run.** GitHub counts **`success`, `skipped` and `neutral`** as satisfying a
    required check (codex, r7) — revision 7 said "success", which is narrower than the set that
    actually lets a merge through.

    **This cell asserts §1's contract clause by clause — C1 through C9 — and does not restate their
    values** (codex, r8: revision 8's copies had already diverged from §1 on `merge_group`). One
    mutant per clause, each a configuration that satisfies every *other* clause:
    **One mutant per ATOMIC rule, not per clause** (codex, r9: a single mutant cannot exercise the
    independent parser paths inside a multi-part clause):
    * **C1** — a third trigger added; and, separately, a *required* trigger missing.
    * **C2** — `branches:` absent; `branches:` present but unequal to the ruleset set; `paths:`
      present; `paths-ignore:` present.
    * **C3** — job-level `if:`; Trunk-step `if:`; `needs:` with a failing dependency;
      `strategy.matrix`; job-level `continue-on-error`; step-level `continue-on-error`; **zero** Trunk
      invocations; **two** Trunk invocations.
    * **C4** — each of `trunk-path` and `post-init`; plus one arbitrary unlisted key.
    * **C5** — `env: {TRUNK_PATH: /bin/true}` at **workflow** level, at job level, and at step
      level: three independent mutants, because revision 10's clause covered only two of the scopes.
    * **C6** — each of the four launcher paths in turn, and each of `.trunk/user.yaml`,
      `.trunk/env.yaml`. **The `.trunk/setup-ci` fixture must be a VALID composite action that exits
      green** (codex, r9) — `uses: ./.trunk/setup-ci` expects an action directory, so a bare no-op
      executable reds because it is *malformed*, and the mutant would survive deletion of C6 while
      still appearing to be caught.
    * **C7** — `merge_group` present at all.
    * **C8** — an extra step inserted before the action; the C6 guard moved away from its adjacency;
      **a mutation inside a permitted `run:` step** — in **both** permitted steps, and in three
      forms: creating one of C6's paths (the case revision 10's ordering made unkillable), writing
      `TRUNK_PATH=/bin/true` to `$GITHUB_ENV`, and writing `BASH_ENV=…` to `$GITHUB_ENV` (codex, r11:
      freezing the sequence never constrained what the allowed steps *do*); and, on `actions/checkout`, each of `sparse-checkout`,
      `ref`, `repository` and `path` in turn.
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
    fixture step fail and the cell still sees red. The evidence must name the Trunk step's own failed
    outcome and its expected diagnostic. **Each observation is bound to its provenance**: the
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
    * the check runs under its declared timeout, using a **macOS-portable** mechanism, exercised
      against a sleeping fake `trunk` on the PATH;
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

    **Two cases the simple formula still gets wrong (codex, r7).** A job that calls a **reusable
    workflow** is reported as `<caller job name> / <reusable job name>`, so its effective context is
    neither name alone; and a `name:` containing an **expression** cannot be resolved by a static
    census at all. The census must model the reusable-workflow form and **fail closed** — never
    silently count zero — on any name it cannot resolve statically.

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

**Accepted cost:** ~7s added to each commit, against sub-second today.

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

**Losing cost, previously unstated (codex, r2): no merge-time detection of newly broken links.** A
PR may introduce a dead link and merge; the scheduled job reports it afterwards. Accepted, because a
required gate that fails on someone else's outage is worse — but it is a real loss, not a free win.

## §7 — Files Changed

* **`.github/workflows/trunk-check.yml` — NEW.** The `trunk-check` job lives in its own workflow and
  satisfies **§1's contract, clauses C1–C9** — the event set, the branch filters, the absence of
  anything that skips or masks, the `with:` allowlist, the `env:` prohibition, the
  repository-supplied-launcher guard, the merge-queue stop, the frozen step sequence, and the action's
  exact SHA pin. Plus §6.1's `save-annotations: true` with `contents: read`, §6.4's `arguments:`
  literal, and cell 1's empty-diff guard step. **Values are stated in §1 and §6, never here** — this
  is a file inventory, and revision 9's copy of the contract into this entry is exactly the
  divergence risk §1's singularity exists to remove (codex, r9).
* `.github/workflows/plugin-ci.yml` — unchanged by this ticket; it keeps its `workflow_dispatch`,
  which is exactly why `trunk-check` may not live in it
* `scripts/tests/test_transcript_path_inventory.py` — class-specific content-addressing; `:342` and
  `:355` updated
* `docs/planning/COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json` — `line`, `destination.line` and both
  anchor lines demoted to hints for prepend-only sites
* `CLAUDE.md` — gate-list update
* `.githooks/pre-commit` — the `--index`-scoped, `--no-fix`, bounded, exit-code-aggregating trunk
  check (§6.3 decided: wire it), **and** the §3b detector call
* **`scripts/detect-plugin-version-drift.sh`** — the §3b detector, named here rather than left as
  "the detector script" (codex, r5), so cell 8 has a concrete entry point
* **`.claude/settings.json`** — a project `SessionStart` hook invoking that detector, the surface
  that fires while a stale install is actually running (§3b)
* **`scripts/tests/test_trunk_check_workflow.py`** — cells 4, 9, 11 and 14 (workflow parsing, the
  frozen membership set (cell 4 holds the names and the count — this list does not restate them),
  the `arguments:` literal, the producer census)
* **`scripts/tests/test_precommit_trunk_gate.py`** — cell 13's index/worktree, `--no-fix`, timeout
  and exit-aggregation controls, and cell 8's pre-commit entry point
* **`scripts/tests/test_trunk_check_behaviour.py`** — **new**: cells 2, 3 and 5, the observed-run
  cells (the gate bites; it does not over-reach; it mutates no tracked file, against a deliberately
  fixable fixture)
* **`docs/planning/evidence/COREDEV-2780-rollout.json`** — **new**: cells 10 and 12, plus cell 8's
  real `SessionStart` invocation. Provenance-bound observations of real runs, not unit tests — both
  files were named by the owner table below while this inventory omitted them (codex, r10)
* **`scripts/tests/test_trunk_upstream_parity.py`** — cell 1's instrumented-launcher harness, which
  had no owning file in revision 8 (codex, r8): it runs the pinned action against per-event fixtures
  with `trunk-path` pointed at a recording launcher and compares the captured range byte-for-byte
  against the guard step's output. *(The harness is the one legitimate use of `trunk-path`; §1's C4
  forbids it in the shipped workflow.)*
* **`scripts/tests/test_session_start_drift_hook.py`** — §3b's `SessionStart` contract: matcher set,
  `${CLAUDE_PROJECT_DIR}` resolution, the `O_EXCL` dedup marker under concurrent invocation, the
  `systemMessage` output shape, and the timeout against a sleeping detector (cell 8, SessionStart half)

**Every cell's owner, stated explicitly** — revision 9 claimed each cell had one and **five did not**
(both arms, r9: cells 2, 3, 5, 10 and 12 were unassigned, and 6–7 only implied):

| cell | owner |
|---|---|
| 1 | `test_trunk_upstream_parity.py` (range parity, empty diff, the zero-before-sha subdomain) |
| 2, 3, 5 | `test_trunk_check_behaviour.py` — **new**: the gate bites, does not over-reach, and mutates no tracked file. These are *observed-run* cells, not parse cells, and revision 9 left them ownerless |
| 4, 9, 11, 14 | `test_trunk_check_workflow.py` (parse + census + mutants) |
| 6, 7 | `scripts/tests/test_transcript_path_inventory.py` — the existing suite, named here rather than implied |
| 8 | `test_session_start_drift_hook.py` (SessionStart *declaration*) + `test_precommit_trunk_gate.py` (pre-commit entry point) + `evidence/COREDEV-2780-rollout.json` (the one real session-start invocation — the runtime half, which no test file can carry; codex, r11) |
| 10, 12 | `docs/planning/evidence/COREDEV-2780-rollout.json` — **evidence, not a unit test**: the annotation artifact and the dual-base provenance-bound check runs are observations of real runs, recorded as a committed artifact the way COREDEV-2711 §3a's measurement was. Saying so is what makes them ownable |
| 13 | `test_precommit_trunk_gate.py` |

## §8 — Notes

**Revision 1's largest defect was not technical.** It was written without reading COREDEV-2771's
planning document, which contains a section addressed to this ticket handing over six reviewed
defects. Both reviewers re-derived that work. Grep `docs/planning/` for the predecessor first.

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
