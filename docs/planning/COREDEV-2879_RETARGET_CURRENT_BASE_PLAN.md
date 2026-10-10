# COREDEV-2879 — A retargeted PR must not satisfy `trunk-check` with a run against its OLD base

**Status:** Planning, revision 1. Not yet gated.
**Ticket:** COREDEV-2879 (High). Found while observing COREDEV-2780 M4.
**Branch / worktree:** `feat/COREDEV-2879-retarget-current-base`, `.claude/worktrees/2879-retarget`, cut
from `origin/main` at `665796e`.

## Review log

*(none yet)*

## 0. The defect, and what "fixed" means

`trunk-check` is a required context in ruleset `Control`, which protects `main` and `alpha` (COREDEV-2780 M4,
applied 2026-10-09). COREDEV-2780 §7 cell 2 asks for **the context that satisfies the rule to be a new run
against the new base's range** after a retarget. On 2026-10-09 that was observed to hold only in part:

| Observed on PR #110, retargeted main → alpha at 21:28:57Z | Holds? |
|---|---|
| While the new `trunk-check` run was pending, the PR read `BLOCKED` with `trunk-check` the only required context not passing. The rule IS evaluated against the new run, not the earlier same-SHA success. | yes |
| The new run (workflow run `37993706657`) checked out a merge commit whose `HEAD^1` was `665796e`, main's tip, while alpha's tip was `10d57dd`. It linted a 1-file range. Against alpha the range would have included the 46 files `main..alpha` differ in. It went green and the PR read `CLEAN` on base `alpha`. | **no** |

A second, pre-existing hole is in the same class. The other five required contexts (`validate`, `py39-smoke`,
`secret-scan`, `load-check` and `redactor-equivalence (ubuntu-latest)`) come from `plugin-ci.yml`. Its
`pull_request` trigger takes the default activity types, which exclude `edited`, so those contexts **do not
re-run on a retarget at all**. Their old-base results go on satisfying the new base's rule.

**The property this plan establishes:** a PR can satisfy `Control` after a retarget only through required
contexts produced by an event that came AFTER the retarget, and `trunk-check`'s upstream is always on the PR's
CURRENT base branch.

## 1. Verified facts (2026-10-09, on `665796e`)

- **F1. The action lints whatever `HEAD` is checked out.** `trunk-io/trunk-action` at the pinned
  `e1234e67a86010d61ddac8d8ebf4b783e2ffd2fa`, `pull_request.sh` lines 14-21: on the merge ref it takes
  `head_sha=$(git rev-parse HEAD)`, fetches it at depth 2, and uses `HEAD^1` as `--upstream`. It never
  re-fetches `refs/pull/<n>/merge`. So whatever merge commit `actions/checkout` placed in the workspace
  decides the range, and the resolver (`scripts/ci/resolve-trunk-range.sh`) already reads the same `HEAD^1`.
  Guard/action parity therefore holds as long as both judge the same `HEAD`.
- **F2. The checked-out merge commit is the EVENT's `github.sha`, and a re-run reuses it.** `actions/checkout`
  with no `ref:` (C8 forbids one) checks out the event's commit. A re-run keeps the original event and SHA,
  so **a re-run can never repair a stale merge commit**. Only a NEW event (a push, i.e. `synchronize`, or a
  close/reopen, i.e. `reopened`) gets a freshly computed merge commit.
- **F3. GitHub recomputes `refs/pull/<n>/merge` asynchronously after a base change.** Observed: the run
  `37993706657`, created 1 s after the retarget, checked out the old-base merge commit (log line
  `Detected merge commit, using HEAD^1 (665796e…) as upstream`). M3's #99 retarget (2026-09-07) fired 4 s
  after its retarget and happened to see the new merge ref, and its `doesNotEstablish` named this race as
  unobserved.
- **F4. A base change is identifiable from the event payload.** GitHub's webhook reference
  (`github/docs`, the per-plan `src/webhooks/data/*/pull_request.json` and its child-params file): `edited` fires when "the title or body … was
  edited, or the base branch … was changed", and for a base change the payload carries `changes.base.ref.from`
  and `changes.base.sha.from`. Title and body edits carry `changes.title` / `changes.body` instead.
  `GITHUB_EVENT_PATH` is runner-provided on every step, so reading it needs no `env:` block, which C5 forbids.
- **F5. `GITHUB_BASE_REF` is runner-provided on every `pull_request` step**, and `pull_request.base.sha` is
  NOT a live value: GitHub's docs say the base commit is set when the PR is opened and is not updated when the
  base branch moves. That is why the action prefers `HEAD^1`, and why this plan reads the base's LIVE tip by
  fetching the branch rather than trusting `base.sha`.
- **F6. The resolver is shared and digest-pinned.** It is invoked by `trunk-check.yml` (`guard-empty-diff`),
  `trunk-check-push.yml` (the canary, `push` branch only) and `trunk-parity-harness.yml` (`pull_request` into
  `harness-base`). Its sha256 is pinned in the `guard-resolver-digest` step of `trunk-check.yml` and
  `trunk-check-push.yml`, and `test_trunk_check_workflow.py` freezes those steps' run-body digests.
- **F7. `plugin-ci.yml`'s `pull_request` has no `types:`**, so the defaults apply: `opened`, `synchronize`,
  `reopened`. A push or a close/reopen re-runs it; a retarget does not.
- **F8. The draft below was EXECUTED against real objects** (`~/.claude/handoffs/coredev-2879/exec/`). I fetched
  main `665796e`, alpha `10d57dd` and #110's head `942013a`, and built merge commits with
  `git merge-tree --write-tree`. Each was then cloned at depth 2, as checkout does, with `origin` pointed at the
  real repository. Results:

  | # | Case | Shipped resolver | Draft |
  |---|---|---|---|
  | 1 | stale merge (head + main) while base is alpha, `synchronize` | `upstream=665796e` (the bug) | rc 1, `STALE MERGE REF` |
  | 2 | fresh merge (head + alpha), `synchronize` | `10d57dd` | `10d57dd` |
  | 3 | fresh merge, `edited` with `changes.base` | `10d57dd` | rc 1, `RETARGET` |
  | 4 | fresh merge, `edited` with `changes.title` | `10d57dd` | `10d57dd` |
  | 5 | stale merge, `reopened` | `665796e` (the bug) | rc 1, `STALE MERGE REF` |
  | 6 | merge against `alpha^1` (`7ed1a6e`): the base merely ADVANCED | `7ed1a6e` | `7ed1a6e` (accepted) |
  | 7 | a main PR, normal | `665796e` | `665796e` |
  | 8 | no `GITHUB_EVENT_PATH` | `10d57dd` | rc 1, payload unreadable |
  | 9 | no `GITHUB_BASE_REF` | `10d57dd` | rc 1, base ref unset |

## 2. Design

Both parts live in the `pull_request` branch of `scripts/ci/resolve-trunk-range.sh`. They do not go in a new
workflow step, for three reasons:

- C8 holds the job to an allowlist of exactly five steps in order, and the resolver is already executed by the
  step positioned for it (`guard-empty-diff`).
- By F1 the action lints the checked-out `HEAD`, which the resolver already inspects.
- Failing in the resolver fails `guard-empty-diff`, so `trunk-check` concludes failure BEFORE the action runs.

### 2.1 Part A — a retarget fails closed, and names the remedy

On a `pull_request` event, the resolver reads `GITHUB_EVENT_PATH`. If `action == "edited"` and `"base" in
changes`, it exits 1 with a message that says this run is a retarget and gives the remedy: push a commit, or
close and reopen the PR. The message also says a re-run reuses the stale merge commit (F2).

This one rule covers both holes:

- **trunk-check's own stale range (F3).** The retarget run is red, so it cannot satisfy the rule.
- **plugin-ci's stale contexts (F7).** `trunk-check` stays red until the remedy, so the PR cannot merge in the
  window where plugin-ci's contexts are still old-base results. The remedy (`synchronize` or `reopened`) is an
  event plugin-ci DOES run on, so it re-runs all five against a freshly computed merge commit. Both workflows
  check out the same event's `github.sha`, so Part B's certification of that commit (§2.2) covers plugin-ci's
  checkout too.

**The payload is mandatory on `pull_request`.** If it is unreadable or does not parse, the resolver fails
closed: an event it cannot classify is not an event it may green. A title or body `edited` is classified "no"
and proceeds normally (F8 case 4).

### 2.2 Part B — the upstream must be on the PR's CURRENT base

On the merge-ref branch, after `upstream=$(git rev-parse HEAD^1)`:

1. `base_ref="${GITHUB_BASE_REF-}"`. If it is empty, fail closed.
2. `git fetch --quiet --no-tags --depth=64 origin "refs/heads/${base_ref}"`. If the fetch fails, fail closed.
   The fetch writes `FETCH_HEAD` and creates no ref.
3. `git merge-base --is-ancestor "${upstream}" FETCH_HEAD`. If that fails, exit 1 with `STALE MERGE REF`,
   naming `HEAD^1`, the base ref and its live tip, plus the same remedy text.

This rule states the property, not one mechanism. A stale merge commit reached by ANY event is refused: a
scripted reopen inside the recomputation window (F8 case 5), or a title edit in the same window. The check
is **ancestor-or-equal, not equal** on purpose. A base that ADVANCED after the merge ref was computed is the
ordinary case, and refusing it would red unrelated PRs whenever another PR merges (F8 case 6). Depth 64 bounds
the fetch. A base that advanced more than 64 commits between the merge-ref computation and the job is refused,
and a push or reopen recovers. The `merge-base` walk starts at the fetched tip, so the depth-2 shallow
boundary at `HEAD^1` does not affect it (F8 cases 1, 2, 6).

The fetch is anonymous. The checkout sets `persist-credentials: false`, and this repository is public. On a
private repository the fetch would fail, and the resolver fails CLOSED, which is the safe direction (§6).

### 2.3 The exact resolver change

Insert at the top of the `pull_request)` arm, before `ref_name=…`:

```bash
	[[ -r ${GITHUB_EVENT_PATH-} ]] || die "GITHUB_EVENT_PATH is unreadable — cannot tell whether this pull_request event is a retarget"
	retarget="$(python3 -c 'import json, os
with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
    payload = json.load(handle)
changes = payload.get("changes") or {}
print("yes" if payload.get("action") == "edited" and "base" in changes else "no")' 2>/dev/null)" ||
		die "the event payload does not parse — cannot tell whether this pull_request event is a retarget"
	case "${retarget}" in
	yes) die "this run is a RETARGET: the other required contexts did not re-run and this merge ref may predate the new base. Push a commit, or close and reopen the PR, to re-run every required check against the new base (a re-run reuses this stale merge commit)" ;;
	no) ;;
	*) die "could not classify the event payload (got '${retarget}')" ;;
	esac
```

Insert directly after `upstream="$(git rev-parse HEAD^1)" || die …` in the merge-ref branch:

```bash
		base_ref="${GITHUB_BASE_REF-}"
		[[ -n ${base_ref} ]] || die "GITHUB_BASE_REF is unset on a pull_request event"
		git fetch --quiet --no-tags --depth=64 origin "refs/heads/${base_ref}" ||
			die "could not fetch the PR's current base \`${base_ref}\` to check the merge ref against it"
		if ! git merge-base --is-ancestor "${upstream}" FETCH_HEAD; then
			die "STALE MERGE REF: HEAD^1 ${upstream} is not on the PR's current base \`${base_ref}\` (tip $(git rev-parse FETCH_HEAD)) — GitHub had not recomputed refs/pull/<n>/merge. Push a commit, or close and reopen the PR (a re-run reuses this merge commit)"
		fi
```

Each insertion carries a comment stating its reason (F2-F5), in the file's existing style. The `push` branch
and the non-merge-ref `pull_request` fallback are unchanged, apart from Part A running before the fallback,
which C8 makes unreachable in the required workflow anyway.

### 2.4 Consequences for the three callers

- **`trunk-check.yml`**: behaviour as above. On success the resolver still prints exactly `upstream=$(git
  rev-parse HEAD^1)`, so cell 1's guard/action parity is unchanged.
- **`trunk-check-push.yml`** (canary): it uses only the `push` arm, so its behaviour is unchanged. Its
  `guard-resolver-digest` literal is re-pinned because the file's bytes change.
- **`trunk-parity-harness.yml`**: it runs on `pull_request` into `harness-base`, so Part B fetches
  `harness-base` and Part A reads its payload. It is `continue-on-error: true` and is not a required context.
  PR #89 is its only open PR, and it may need a push to refresh.

### 2.5 Digest re-pins and what they touch

- The new sha256 of `scripts/ci/resolve-trunk-range.sh` replaces `bb3218ba…` in the `expected=` literal of
  `guard-resolver-digest`, in both `trunk-check.yml` and `trunk-check-push.yml`.
- That changes both steps' run bodies, so the frozen run-body digests in `test_trunk_check_workflow.py`
  (`guard-resolver-digest` for `required` and `canary`) are re-derived.
- Nothing else in either workflow changes: no step is added, moved or renamed, and no `with:`, permission or
  trigger changes.
- `scripts/review/callers-scan-exemptions.tsv` is regenerated LAST and must reach a fixed point.

## 3. Tests

All tests run locally against a `file://` bare origin, with no network access.

**`scripts/tests/test_trunk_upstream_parity.py`, which already owns the resolver's behaviour:**

- **Fixture extended.** The merge-ref fixture gains a bare `origin` holding the base branch, sets
  `GITHUB_BASE_REF` and writes an event payload to a temp file, because Parts A and B make both mandatory.
  The existing merge-ref tests keep their assertions, including `upstream == HEAD^1` and pattern detection
  over `1/merge`, `84/merge` and `99999/merge`.
- **New tests, one per F8 row, built from real merge commits in the fixture rather than stubs.** Each failing
  case asserts its REASON text, not just rc 1:
  - stale merge → `STALE MERGE REF`;
  - retarget payload → `RETARGET`;
  - title edit → resolves;
  - base merely advanced → resolves;
  - no payload → payload unreadable;
  - malformed payload → does not parse;
  - no `GITHUB_BASE_REF` → base ref unset;
  - fetch failure (no such base branch on origin) → could not fetch.
- **The push arm is unaffected.** A canary-style `push` run with no `GITHUB_BASE_REF` and no origin still
  resolves `before`. That proves Part B is scoped to the merge-ref branch.

**`scripts/tests/test_trunk_check_workflow.py`:** the two `guard-resolver-digest` run-body digests are
re-derived with the file's own derivation, never typed. The C6a case (`edit-resolver`) is unchanged and must
still go red.

## 4. Verification cells (each must be seen red, for the stated reason)

Each cell is a mutation of the shipped resolver, run against §3's tests, with `PYTHONDONTWRITEBYTECODE=1`.
Every cell is two-sided: the over-broad mutants guard against a fix that "passes" by refusing too much.

| # | Mutation | Must go red | For this reason |
|---|---|---|---|
| V1 | delete Part A's `yes)` die | the retarget test | resolves instead of `RETARGET` |
| V2 | delete Part B's `is-ancestor` check | the stale-merge test | resolves `665796e`-shaped upstream |
| V3 | Part B uses EQUALITY with the tip instead of ancestry | the base-advanced test | over-strict: refuses a legitimate advanced base |
| V4 | Part A matches ANY `edited` (drop `"base" in changes`) | the title-edit test | over-broad: refuses a title edit |
| V5 | Part A treats an unreadable payload as "no" | the no-payload test | fails OPEN |
| V6 | Part B skips when `GITHUB_BASE_REF` is empty | the no-base-ref test | fails OPEN |
| V7 | Part B ignores a fetch failure | the fetch-failure test | fails OPEN |
| V8 | resolver edited, digest NOT re-pinned | `guard-resolver-digest` step digest test | C6a/C8 |
| V9 (equivalent) | depth 64 → 128 | nothing | must SURVIVE; depth is a bound, not a property |

## 5. Rollout

1. Gate this plan with dual review, reproduced on byte-identical bytes, then synthesize and persist the verdict.
2. Implement §2 and §3, then run the §4 battery.
3. Run CI's thirteen-command local gate, then a local `codex review --base origin/main`.
4. **Version bump to 2.8.32**, because shipped workflow and script bytes change: `plugin.json`,
   `marketplace.json`, the README H1 and What's-New, and the CHANGELOG.
5. Open a PR to `main`, watch CI and triage the bots. **Merge needs the maintainer's word.**
6. **After merge, re-observe cell 2 live** with the M4a witness method (read-only, no merge):
   1. Open a green PR to `main` and retarget it to `alpha`.
   2. Expect the retarget run RED, naming `RETARGET`.
   3. Close and reopen the PR. Expect `trunk-check` green, with the action's echoed upstream equal to alpha's
      tip, and plugin-ci re-run.
   4. Record the observation in `COREDEV-2780-rollout.json` and close the `stillOpenForM3` item
      (`resolvesAt: COREDEV-2879`).
7. **alpha catch-up.** alpha keeps the old resolver until it is caught up to `main`, through a PR into `alpha`
   that needs the maintainer's word. Until then, PRs whose merge ref uses alpha's workflow bytes are not
   covered. Note this on the ticket.

## 6. Out of scope, and boundaries stated rather than covered

- **plugin-ci gets no stale-merge-ref guard of its own.** It is covered by §2.1: `trunk-check` stays red until
  an event plugin-ci runs on. Part B certifies that event's `github.sha`, and plugin-ci checks out the same
  commit.
- **Private repositories.** The anonymous base fetch fails there, and the resolver fails closed.
- **Merge queue.** C7 forbids it, and `Control` has no merge-queue rule (M4 preflight).
- **A base that advanced more than 64 commits** between the merge-ref computation and the job is refused, and
  a push or reopen recovers.

## 7. Files changed

- `scripts/ci/resolve-trunk-range.sh`: §2.3.
- `.github/workflows/trunk-check.yml`, `.github/workflows/trunk-check-push.yml`: the `expected=` digest literal
  only.
- `scripts/tests/test_trunk_upstream_parity.py`: fixture and new tests (§3).
- `scripts/tests/test_trunk_check_workflow.py`: the two run-body digests.
- `scripts/review/callers-scan-exemptions.tsv`: regenerated.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`, `CHANGELOG.md`: 2.8.32.
- After merge: `docs/planning/evidence/COREDEV-2780-rollout.json` (§5 step 6), on its own PR.
