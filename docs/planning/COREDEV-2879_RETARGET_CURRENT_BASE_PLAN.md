# COREDEV-2879 — A retargeted PR must not satisfy `Control` with contexts computed against its OLD base

**Status:** Planning, revision 3. Round 2: codex `REQUEST_CHANGES` (Q1: 2); gemini produced no review again (see the log).
**Ticket:** COREDEV-2879 (High). Found while observing COREDEV-2780 M4.
**Branch / worktree:** `feat/COREDEV-2879-retarget-current-base`, `.claude/worktrees/2879-retarget`, cut
from `origin/main` at `665796e`.

## Review log

- **Round 1 (revision 1), codex `REQUEST_CHANGES`, Q1: 2.** Both Q1 findings were real. Revision 2 redesigns
  around them.
  1. **A title or body edit released the gate.** Revision 1's Part A failed only the retarget event itself.
     A later `edited` (title) run classified "no", passed Part B on a now-fresh merge ref, and turned
     `trunk-check` green, while plugin-ci, which does not run on `edited`, still held five pre-retarget
     results. **Fix:** plugin-ci gains `edited` (§2.2), so every event that runs `trunk-check` runs all six
     required contexts on the same merge commit. Part A is withdrawn: it is no longer needed and it forced a
     manual reopen on every retarget.
  2. **Part B checked the EVENT's base, not the PR's current base.** A re-run of a pre-retarget event keeps
     its payload (`GITHUB_BASE_REF=main`) and its merge commit. Part B then fetched live `main` and accepted
     a main-based parent on a PR that now targets alpha. **Fix:** a second reference, the PR's CURRENT
     `refs/pull/<n>/merge`, whose first parent is the current base once GitHub has recomputed it (§2.1,
     check 2). Executed against real objects (F8, case R2).
  3. **(Q2) The §4 procedure ran resolver mutations against digest-pinned tests, and V8 named the wrong
     check.** **Fix:** behaviour mutants run against the behaviour module only, and V8 executes the C6a
     guard and asserts `digest mismatch` (§4).
- **Round 2 (revision 2), codex `REQUEST_CHANGES`, Q1: 2.** Both Q1 findings were real.
  1. **Ancestry does not identify a BRANCH.** alpha's `10d57dd` has main's `dd84d82` as its SECOND parent (a
     catch-up merge), so an old main tip is an ancestor of BOTH bases. Revision 2 then failed in two ways:
     a re-run of a pre-retarget run passed both checks after recomputation (F8 R9), and the race passed too
     (R8). **Fix:** both checks use FIRST-PARENT membership (§2.1), since a branch advances along its first
     parents and a catch-up brings the other branch in as parent 2. Executed: R8 and R9 are now refused, and
     R10 (a main merge on an older main tip) is still accepted.
  2. **Runs created before this ships** re-run with their OLD resolver, which performs neither check. §6 now
     states this boundary and §5 adds the mitigation: refresh every PR open at ship time. The residual is
     ticketed.
  3. **(Q2) Two re-pins were missing:** `test_python39_floor.py`'s `_JOB_DIGESTS` freezes both trunk jobs
     whole, so changing the `expected=` literals changes both (codex measured `ba363bda… → 05ad3a6c…` and
     `aaea3498… → 83c605ce…`). Added to §2.4, §3 and §7.
  4. **(Q2) V8 did not assert its reason.** The unit test copies a mutated resolver into its own
     positive-control fixture and fails before reaching `digest mismatch`. **Fix:** V8 executes the extracted
     guard body directly and asserts rc and reason (§4).
- **Round 2, gemini: no review, again a 307-byte `read_file` denial.** The likely cause is the prompt, not
  agy: it invited the reviewer to read the draft files under `~/.claude/handoffs/`, which lie OUTSIDE agy's
  `--add-dir` sandbox. Round 3's agy prompt withdraws that invitation. Codex's sandbox can read them.
- **Round 1, gemini: no review.** The transcript was 307 bytes: agy's headless `read_file` was auto-denied,
  a known transient signature, not a finding. The `.model` sidecar recorded `gemini-3.8-flash-high newest`. It was
  not re-run on revision 1, which this revision supersedes.

## 0. The defect, and what "fixed" means

`trunk-check` is a required context in ruleset `Control`, which protects `main` and `alpha` (COREDEV-2780 M4,
applied 2026-10-09). The other five required contexts (`validate`, `py39-smoke`, `secret-scan`, `load-check`
and `redactor-equivalence (ubuntu-latest)`) come from `plugin-ci.yml`. COREDEV-2780 §7 cell 2 asks for the
context that satisfies the rule to be a new run against the new base's range after a retarget. On
2026-10-09 that held only in part:

| Observed on PR #110, retargeted main → alpha at 21:28:57Z | Holds? |
|---|---|
| While the new `trunk-check` run was pending, the PR read `BLOCKED` with `trunk-check` the only required context not passing: the NEWER run decides, not the earlier same-SHA success. | yes |
| That run (workflow run `37993706657`) checked out a merge commit whose `HEAD^1` was `665796e`, main's tip, while alpha's tip was `10d57dd`. It linted a 1-file range (against alpha: 46 files) and went green, and the PR read `CLEAN` on base `alpha`. | **no** |
| plugin-ci did not run at all (no `edited` in its triggers), so its five contexts stayed pre-retarget results. | **no** |

**The property this plan establishes.** Every required context that can satisfy `Control` comes from a run
whose checked-out merge commit's first parent lies on the FIRST-PARENT CHAIN of the PR's CURRENT base, so it
was once a tip of that branch. A run that cannot show that is red. "Current" means two things: the live tip
of the event's base branch, and the first parent of the PR's current merge ref. The boundaries are stated in
§6, including runs created before this ships.

## 1. Verified facts (2026-10-09, on `665796e`)

- **F1. The action lints whatever `HEAD` is checked out.** `trunk-io/trunk-action` at the pinned
  `e1234e67a86010d61ddac8d8ebf4b783e2ffd2fa`, `pull_request.sh` lines 14-21: on the merge ref it takes
  `head_sha=$(git rev-parse HEAD)`, fetches it at depth 2 and uses `HEAD^1` as `--upstream`. It never
  re-fetches `refs/pull/<n>/merge`. The resolver (`scripts/ci/resolve-trunk-range.sh`) reads the same
  `HEAD^1`, so guard/action parity holds while both judge the same `HEAD`.
- **F2. A re-run keeps the original event's `GITHUB_SHA`, `GITHUB_REF` and payload.** GitHub's docs
  (`re-run-workflows-and-jobs.md`): "The workflow will also use the same `GITHUB_SHA` (commit SHA) and
  `GITHUB_REF` (git ref) of the original event." So a re-run of a pre-retarget event checks out the
  pre-retarget merge commit, and `GITHUB_BASE_REF` still names the OLD base.
- **F3. The NEWEST run of a context decides it, by creation, not by completion.** On #110 (§0 row 1), the
  earlier completed success did not satisfy the rule while a newer run was in progress. A re-run CREATES a
  new run, so a re-run of an obsolete event becomes the deciding run. That is why every deciding run must
  certify its own checkout (F2 + F3 = round 1's finding 2).
- **F4. GitHub recomputes `refs/pull/<n>/merge` asynchronously after a base change.** Run `37993706657`,
  created 1 s after the retarget, checked out the old-base merge commit (its log:
  `Detected merge commit, using HEAD^1 (665796e…) as upstream`). M3's #99 retarget (2026-09-07) fired 4 s
  after its retarget and happened to see the new merge ref, and its `doesNotEstablish` named this race as
  unobserved.
- **F5. `pull_request` events for one webhook delivery share `github.sha`**, the merge commit GitHub had at
  that moment. `trunk-check.yml` and `plugin-ci.yml` therefore check out the same commit for the same event,
  and a verdict about that commit's base applies to both.
- **F6. `plugin-ci.yml`'s `pull_request` has no `types:`**, so it runs on the defaults, `opened`,
  `synchronize` and `reopened`, and NOT on `edited`. `trunk-check.yml` runs on those plus `edited` (C2).
  `test_python39_floor.py` freezes `plugin-ci.yml`'s workflow-level keys, `on:` included, by digest.
- **F7. `GITHUB_BASE_REF` and `GITHUB_REF_NAME` are runner-provided on every `pull_request` step.** On the
  merge ref, `GITHUB_REF_NAME` is `<n>/merge` (the resolver already relies on this). `pull_request.base.sha`
  is NOT live: GitHub's docs say the base commit is set when the PR is opened and is not updated when the
  base branch moves. So this plan reads live references by fetching them.
- **F8. Both checks were EXECUTED against real objects** (`~/.claude/handoffs/coredev-2879/exec/`). The
  fixtures are real main `665796e`, alpha `10d57dd` and #110's head `942013a`, merged with
  `git merge-tree --write-tree`. Each fixture is cloned at depth 2, as checkout does, against a bare origin
  carrying `refs/heads/{main,alpha}` and a settable `refs/pull/110/merge`. `resolver.draft2.sh` is §2.1's
  text.

  | # | Case | Shipped resolver | §2.1 |
  |---|---|---|---|
  | R1 | race: event base alpha, HEAD = head+main, the merge ref not yet recomputed | `upstream=665796e` (the bug) | rc 1, `STALE MERGE REF` |
  | R2 | re-run of a pre-retarget event: base main, HEAD = head+main, merge ref now head+alpha | `665796e` (the bug) | rc 1, `OBSOLETE EVENT` |
  | R3 | normal: base alpha, HEAD = merge ref = head+alpha | `10d57dd` | `10d57dd` |
  | R4 | base ADVANCED: HEAD = head+`alpha^1`, merge ref = head+alpha | `7ed1a6e` | `7ed1a6e` (accepted) |
  | R5 | normal main PR | `665796e` | `665796e` |
  | R6 | no merge ref on origin | `10d57dd` | rc 1, could not fetch |
  | R8 | CATCH-UP race: event base alpha, HEAD = head+`dd84d82` (an old main tip that alpha contains as a second parent), merge ref not yet recomputed | `dd84d82` (the bug; revision 2's ancestry check also accepted it) | rc 1, `STALE MERGE REF` |
  | R9 | CATCH-UP obsolete re-run: base main, HEAD = head+`dd84d82`, merge ref recomputed to head+alpha | `dd84d82` (the bug; revision 2 also accepted it) | rc 1, `OBSOLETE EVENT` |
  | R10 | a main merge on the older main tip `dd84d82` (5th on main's first-parent chain), merge ref the same | `dd84d82` | `dd84d82` (accepted: the base advanced) |

  An earlier draft (revision 1's Part A) also passed nine payload cases. Those cases were withdrawn with
  Part A.
- **F9. The resolver is shared and digest-pinned.** It is invoked by `trunk-check.yml` (`guard-empty-diff`),
  `trunk-check-push.yml` (the canary, `push` arm only) and `trunk-parity-harness.yml` (`pull_request` into
  `harness-base`). Its sha256 is pinned in the `guard-resolver-digest` step of the first two, and
  `test_trunk_check_workflow.py`'s `EXPECTED_RUN_BODY_DIGESTS` freezes those steps' run bodies.

## 2. Design

### 2.1 `trunk-check` certifies its checkout against TWO live references

The checks go in the merge-ref branch of the resolver's `pull_request` arm, directly after
`upstream="$(git rev-parse HEAD^1)"`. They do not go in a new workflow step: C8 allows exactly five steps in
order, the resolver already runs in `guard-empty-diff`, and failing there fails `trunk-check` BEFORE the
action runs.

```bash
		base_ref="${GITHUB_BASE_REF-}"
		[[ -n ${base_ref} ]] || die "GITHUB_BASE_REF is unset on a pull_request event"
		pr="${ref_name%/merge}"
		[[ ${pr} =~ ^[0-9]+$ ]] || die "cannot read a PR number from GITHUB_REF_NAME '${ref_name}'"
		git fetch --quiet --no-tags --depth=64 origin \
			"+refs/heads/${base_ref}:refs/trunk-gate/base" "+refs/pull/${pr}/merge:refs/trunk-gate/merge" ||
			die "could not fetch the PR's current base \`${base_ref}\` and refs/pull/${pr}/merge to check the merge ref against them"
		if ! on_first_parent_chain "${upstream}" refs/trunk-gate/base; then
			die "STALE MERGE REF: HEAD^1 ${upstream} is not on the event's base \`${base_ref}\` (tip $(git rev-parse refs/trunk-gate/base)) — GitHub had not recomputed refs/pull/${pr}/merge. Push a commit, or close and reopen the PR (a re-run reuses this merge commit)"
		fi
		current_base="$(git rev-parse refs/trunk-gate/merge^1)" || die "refs/pull/${pr}/merge has no first parent"
		if ! on_first_parent_chain "${upstream}" "${current_base}"; then
			die "OBSOLETE EVENT: HEAD^1 ${upstream} is not on the base of the PR's CURRENT merge ref (${current_base}) — this run belongs to an event from before a retarget. Push a commit, or close and reopen the PR"
		fi
```

**Membership is on the FIRST-PARENT chain, not ancestry** (round 2). GitHub's merge commit takes the base's
previous tip as parent 1, and squash and rebase merges are linear, so a branch's own past tips are exactly its
first-parent chain. A catch-up merge (main into alpha) brings the other branch in as parent 2, which plain
ancestry cannot tell apart. Both checks therefore use:

```bash
on_first_parent_chain() {
	local chain
	chain="$(git rev-list --first-parent --max-count=64 "$2")" || return 1
	[[ $'\n'"${chain}"$'\n' == *$'\n'"$1"$'\n'* ]]
}
```

The chain is captured, not piped into `grep -q`: under `pipefail`, an early grep exit can SIGPIPE `rev-list`
and report a MATCH as a failure. The helper is defined once, above the `case`, and the block above calls it
for both checks.

Each reference covers a case the other cannot:

- **Check 1, the live tip of the event's base branch.** It catches the race (F4). The event is the retarget,
  the payload names the new base, and the merge commit predates it. In that window the merge ref itself is
  still stale, so check 2 alone would pass (F8, R1).
- **Check 2, the base of the PR's current merge ref.** It catches a re-run of a pre-retarget event (F2, F3).
  The payload names the old base, so check 1 alone would pass (F8, R2).

**First-parent membership, never equality.** A base that ADVANCED after the merge commit was computed is the
ordinary case (F8, R4 and R10). Refusing it would red unrelated PRs every time another PR merges. Depth 64 bounds the
fetch: a base more than 64 commits ahead of the run's merge commit is refused, and a push or reopen
recovers.

Mechanics:

- The `merge-base` walks start at the fetched tips, so the depth-2 shallow boundary at `HEAD^1` does not
  affect them.
- The fetch writes only under `refs/trunk-gate/`. That is not under `.trunk/`, so C6's
  `guard-launcher-path` is unaffected.
- The fetch is anonymous: the checkout sets `persist-credentials: false`, and this repository is public. A
  failed fetch fails CLOSED (F8, R6). On a private repository that means red, the safe direction (§6).
- On success the resolver prints exactly `upstream=$(git rev-parse HEAD^1)`, as now, so cell 1's
  guard/action parity is unchanged.

Each block carries a comment stating its reason, in the file's existing style.

### 2.2 plugin-ci runs on exactly the events `trunk-check` runs on

```yaml
  pull_request:
    branches: [main, alpha]
    types: [opened, synchronize, reopened, edited]
```

Combined with F5, every event that produces a `trunk-check` run also produces all five plugin-ci contexts, on
the same merge commit, and §2.1 certifies that commit or turns `trunk-check` red. The cases:

- **A retarget whose merge ref is already fresh.** All six re-run against the new base and can go green with
  no manual step. Revision 1's Part A forced a reopen here.
- **A retarget that hits the race (R1).** plugin-ci's five contexts may be green against the old base, but
  `trunk-check` is red. The PR stays blocked until the next event (a push, a reopen, or even a title edit,
  which now re-runs plugin-ci as well), which re-runs all six on a freshly computed merge commit.
- **A title or body edit at any time.** All six re-run on that event's merge commit. That is round 1's
  finding 1, closed.

**Cost, stated.** Every title or body edit on a PR into `main` or `alpha` now runs the full plugin-ci matrix,
`darwin-suite` included. The repository is public, so Actions minutes are not billed, but runner queue time
is real.

### 2.3 Consequences for the three resolver callers

- **`trunk-check.yml`:** behaviour as in §2.1. The `guard-resolver-digest` `expected=` literal is re-pinned.
- **`trunk-check-push.yml` (canary):** it uses only the `push` arm, so its behaviour is unchanged. Its digest
  literal is re-pinned.
- **`trunk-parity-harness.yml`:** `pull_request` into `harness-base`, so §2.1 fetches `harness-base` and
  `refs/pull/<n>/merge`. It is `continue-on-error: true` and is not a required context. Its open PR #89 may
  need a push to refresh.

### 2.4 Re-pins, all derived and never typed

- The resolver's new sha256 goes into both `expected=` literals.
- The two `guard-resolver-digest` entries in `EXPECTED_RUN_BODY_DIGESTS` are re-derived.
- The `on:` freeze in `test_python39_floor.py` is re-derived for plugin-ci's `types:` line.
- `test_python39_floor.py`'s `_JOB_DIGESTS` entries for the two trunk jobs (required and canary) are
  re-derived, since each job's `guard-resolver-digest` literal changes (round 2).
- `scripts/review/callers-scan-exemptions.tsv` is regenerated LAST, to a fixed point.

## 3. Tests

**`scripts/tests/test_trunk_upstream_parity.py`, which already owns the resolver's behaviour.** All tests
run against a `file://` bare origin, with no network access.

- **Fixture extended.** The merge-ref fixture gains a bare `origin` holding the base branch and a
  `refs/pull/<n>/merge`, and sets `GITHUB_BASE_REF`. The existing merge-ref tests keep their assertions:
  `upstream == HEAD^1`, and pattern detection over `1/merge`, `84/merge` and `99999/merge`. Their fixture
  places `refs/pull/<n>/merge` for each `n` used.
- **New tests, one per F8 row, built from real merge commits in the fixture rather than stubs.** Each
  failing case asserts its REASON text:
  - R1 → `STALE MERGE REF`;
  - R2 → `OBSOLETE EVENT`;
  - R3, R4 and R5 → resolve to `HEAD^1`;
  - R6 → could not fetch;
  - plus `GITHUB_BASE_REF` unset → base ref unset, and a non-numeric `GITHUB_REF_NAME` prefix → cannot read
    a PR number.
- **The push arm is untouched.** A canary-style `push` run with no `GITHUB_BASE_REF` and no origin still
  resolves `before`.

**New fixture rows R8, R9 and R10** (§1 F8) use a catch-up topology built in the fixture: the base branch
holds a merge whose SECOND parent is the other branch's older tip. R8 → `STALE MERGE REF`, R9 →
`OBSOLETE EVENT`, R10 → resolves.

**`scripts/tests/test_python39_floor.py`:** `_JOB_DIGESTS` for both trunk jobs, and plugin-ci's `on:` freeze,
re-derived.

**`scripts/tests/test_trunk_check_workflow.py`:** the two `guard-resolver-digest` run-body digests are
re-derived. The C6a case (`edit-resolver`) is unchanged and must still go red.

**plugin-ci's trigger, a new test in `test_trunk_check_workflow.py`** (it already reads several workflows):
`plugin-ci.yml`'s `pull_request.types` must EQUAL `trunk-check.yml`'s. This is set equality, read through the
file's existing YAML 1.2 loader. The two trigger sets are the invariant §2.2 depends on, so the test names it
rather than pinning one literal.

## 4. Verification cells (each must be seen red, for the stated reason)

**Procedure** (round 1, finding 3):

- **Behaviour mutants** (V1-V6, V9) edit the resolver and run ONLY `test_trunk_upstream_parity.py`'s
  behaviour tests. That module asserts no digest, so a mutant is judged on behaviour alone.
- **V7 and V8 are structural.** They run the named test only.
- Every run uses `PYTHONDONTWRITEBYTECODE=1`, and every red must show the stated reason.
- V1-V6 were EXECUTED against the F8 fixtures before this revision; the table records what each actually
  did.

| # | Mutation | Must go red | For this reason |
|---|---|---|---|
| V1 | delete check 1 | the R1 test | resolves `665796e` instead of `STALE MERGE REF` |
| V2 | delete check 2 | the R2 test | resolves instead of `OBSOLETE EVENT` |
| V3 | check 1 uses EQUALITY with the tip | the R4 test | over-strict: refuses an advanced base |
| V4 | check 2 compares against `refs/trunk-gate/merge` (the merge commit) instead of its first parent | the R2 test | resolves `665796e`: the merge commit's SECOND parent is the PR head, cut from main, so main's tip is its ancestor and only first-parent identity separates the bases (executed: rc 0) |
| V5 | the fetch failure is ignored | the R6 test | the REASON: it still exits 1, but as `STALE MERGE REF`. The later checks find no refs and misreport a fetch failure as staleness (executed). Only the reason assertion separates it; an rc-only cell would pass it |
| V6 | an empty `GITHUB_BASE_REF` skips the checks | the base-ref-unset test | fails OPEN |
| V7 | plugin-ci's `types:` loses `edited` | the trigger-equality test | §2.2's invariant |
| V8 | resolver edited, digest NOT re-pinned | the `guard-resolver-digest` run body, EXTRACTED from `trunk-check.yml` and executed directly against the mutated tree (not via the unit test, which copies the mutation into its own positive control and fails before the reason) | rc ≠ 0 AND stderr contains `digest mismatch` |
| V10 | first-parent membership replaced by plain ancestry (`git merge-base --is-ancestor`) in both checks | the R8 and R9 tests | resolves `dd84d82`: ancestry cannot tell a branch from one it absorbed (executed: revision 2's resolver accepted both) |
| V9 (equivalent) | depth 64 → 128 | nothing | must SURVIVE: depth is a bound, not a property |

## 5. Rollout

1. Gate this plan with dual review, reproduced on byte-identical bytes, then synthesize and persist the verdict.
2. Implement §2 and §3, then run the §4 battery.
3. Run CI's thirteen-command local gate, then a local `codex review --base origin/main`.
4. **Version bump to 2.8.32**, because shipped workflow and script bytes change: `plugin.json`,
   `marketplace.json`, the README H1 and What's-New, and the CHANGELOG.
5. Open a PR to `main`, watch CI and triage the bots. **Merge needs the maintainer's word.** This PR is itself
   the first to run plugin-ci on `edited`: editing its body after CI must start a fresh plugin-ci run, and
   that is observed and recorded.
6. **After merge, re-observe cell 2 live** with the M4a witness method (read-only, no merge):
   1. Open a green PR to `main` and retarget it to `alpha`.
   2. Record whether the retarget run saw a fresh or a stale merge ref. Fresh → all six green against alpha,
      with the action's echoed upstream equal to alpha's tip. Stale → `trunk-check` red `STALE MERGE REF`;
      a title edit then re-runs all six on a fresh merge commit.
   3. Re-run an obsolete pre-retarget `trunk-check` run → red `OBSOLETE EVENT`.
   4. Record the observation in `COREDEV-2780-rollout.json` and close its `stillOpenForM3` item.
7. **Refresh every PR open on `main` or `alpha` at ship time** (§6), by close/reopen or a push, and record
   which PRs were refreshed. Ticket the residual.
8. **alpha catch-up.** alpha keeps the old resolver and plugin-ci triggers until it is caught up to `main`,
   through a PR into `alpha` that needs the maintainer's word. Until then, PRs whose merge ref uses alpha's
   workflow bytes are not covered. Note this on the ticket.

## 6. Out of scope, and boundaries stated rather than covered

- **Runs created BEFORE this ships.** A re-run reuses the original merge commit, and with it the OLD
  resolver, which performs neither check (F2). On a PR that is open when this merges, a later retarget plus a
  manual re-run of one of its pre-ship `trunk-check` runs could therefore create the deciding run with an
  old-base range. **Mitigation in §5:** after the merge, refresh every open PR on `main` and `alpha` by
  close/reopen or a push, so its newest runs come from the fixed workflow. **Residual:** a manual re-run of a
  pre-ship run, from the Actions history, on a PR that was open at ship time. It is low-odds, so it is
  **ticketed**.
- **A manual re-run of an obsolete PLUGIN-CI run.** plugin-ci jobs do not certify their own checkout. A
  maintainer who opens the Actions history and re-runs a plugin-ci run from before a retarget creates the
  deciding run (F3) on a pre-retarget merge commit. The PR's checks tab offers re-runs of the LATEST runs
  only. Closing this would add the §2.1 check to every plugin-ci job, which needs `fetch-depth: 2` in five
  checkouts and five digest re-pins. That is a low-odds path, so under the standing remediation rule it is
  **ticketed, not fixed here**. The same applies to a re-run of an obsolete `trunk-check` inside the
  recomputation window (seconds), where both references can still be stale.
- **Private repositories.** The anonymous fetch fails there, and `trunk-check` fails closed.
- **Merge queue.** C7 forbids it, and `Control` has no merge-queue rule (M4 preflight).
- **A base that advanced more than 64 commits** between the merge commit and the job is refused, and a push
  or reopen recovers.

## 7. Files changed

- `scripts/ci/resolve-trunk-range.sh`: §2.1.
- `.github/workflows/trunk-check.yml`, `.github/workflows/trunk-check-push.yml`: the `expected=` digest
  literal only.
- `.github/workflows/plugin-ci.yml`: the `types:` line (§2.2).
- `scripts/tests/test_trunk_upstream_parity.py`: fixture and new tests (§3).
- `scripts/tests/test_trunk_check_workflow.py`: the two run-body digests, and the trigger-equality test.
- `scripts/tests/test_python39_floor.py`: plugin-ci's `on:` freeze, and `_JOB_DIGESTS` for both trunk jobs.
- `scripts/review/callers-scan-exemptions.tsv`: regenerated.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`, `CHANGELOG.md`: 2.8.32.
- After merge: `docs/planning/evidence/COREDEV-2780-rollout.json` (§5 step 6), on its own PR.
