# COREDEV-2780 Follow-up — the eight carried defects, and the rollout that is still owed

**Ticket:** COREDEV-2780 (Epic COREDEV-2485) · children COREDEV-2804 … COREDEV-2813
**Branch:** `feat/COREDEV-2780-gating-followup` · **PR:** #85 · **Base:** `main`
**Status:** implementation complete for COREDEV-2804 … 2811; milestones M2a, **M2b-evidence**, M2c-evidence
and M3 outstanding. M2b's *static* half is accepted (`cell16CanaryNotRequired` in
`docs/planning/evidence/COREDEV-2780-rollout.json`); its **runtime** half — a controlled canary
failure — has never been produced, and revision 1 of this plan omitted it entirely (codex, r1).

---

## §0 — What this plan is, and why it is late

This plan is **retrospective for its first half and prospective for its second**, and that split is
itself a defect being declared rather than a structure being defended.

`CLAUDE.md` requires that any feature/refactor/multi-step change gets a `docs/planning/*_PLAN.md`
reviewed by **both** arms before implementation. Twenty commits on this branch were written without
one. They are real work — eight tickets closed, each mutation-proven — but they were **implemented
ungated**, and no review arm has ever seen a statement of intent for them, only the diffs.

So this document does two different jobs and labels which is which:

- **§1 is a retrospective statement of work already committed.** It is submitted so the arms can
  review the *intent* against the *implementation*, which is the check that was skipped. Approval
  here does not certify the code — PR #85's own review rounds do that. It certifies that the
  intent was sound and that the implementation matches it.
- **§3 is a genuine forward plan**, with one qualification that the first revision got wrong by
  stating it flatly: *none of §3's milestones are complete*, but parts of their groundwork already
  exist on `main` — the canary and harness workflows are present, M2b's static half is accepted in
  the committed rollout evidence, and M2a's ancestry is measured rather than assumed. "Nothing has
  been implemented" was false as written (PR #85 audit).

**The correction rule applies to this document.** Where §1 records a decision that a reviewer
overturns, the fix is to change the implementation and re-state §1 — not to annotate §1 with a note
while leaving the normative sentence intact.

### The three process failures this plan exists to record

1. **The plan-review gate was skipped for twenty commits**, including the commit that retargeted
   both review wrappers to a different model at a different effort tier. A change to the *gate's own
   instrument* is the last change that should go ungated.
2. **Two commits were pushed that broke CI.** The local gate passed both times. It passed because it
   did not mirror CI: the 3.9-floor cell behaves differently under `CI=1`, and the local gate ran
   only the unset branch. The gate now runs the suite in **both** states, which is the only reason
   this class is catchable before a push. This is the second time on this ticket that a local
   "full gate" has been narrower than CI's.
3. **`trunk fmt` was run on the review shell scripts** against a standing prohibition recorded from
   COREDEV-2771. It rewrote them, broke thirteen inventory tests, and — the part that matters —
   **silently disarmed a mutation proof**: the proof's `_replace_once` began raising inside its own
   `assertRaises(AssertionError)`, so the cell passed while testing nothing. A reformat is not a
   no-op on a suite whose proofs anchor on exact bytes.

---

## §1 — Retrospective: the eight tickets, and what each one actually turned out to be

Each entry states the **property** that was wrong, not the mechanism that was changed, because on
this campaign the mechanism has repeatedly been the thing that drifted while the property stayed
true. Each was proven old-vs-new: the pre-fix code fails the new cell, the post-fix code passes.

### COREDEV-2804 — the freeze covered a subset of what it named (M4 blocker)

`.trunk/trunk.yaml`'s digest covered only the `lint:` block. Repointing `plugins.sources[].uri` at a
different repository therefore left the digest **byte-identical** with all 1384 tests green — the
gate's own supply chain was outside the thing that freezes the gate.

The digest now covers the whole document — **and precisely what that means was overstated in the
first revision (PR #85 audit).** The digest is taken over `safe_dump(safe_load(text))`, so it covers
the document's PARSED SEMANTICS, not its bytes: a comment-only edit does not move it, which is
deliberate, since a comment fix should not red the gate. The limit worth recording is that anything
PyYAML normalises away is outside the freeze, and whether trunk's own parser agrees with PyYAML on
a duplicate key is **unmeasured** — that is COREDEV-2818, not a claim made here. The `trunk upgrade` carve-out — which must let a version
bump through without letting a source swap through — needed **three** tightenings across review
rounds, and the progression is worth recording because each round's fix carried the next defect:

| Round | Accepted that it should not have |
|---|---|
| first | `123`, `1.2`, `9` — anything digit-shaped |
| second | `v01.2.3`, `1.2.3-01` — leading zeroes, which SemVer forbids and `git check-ref-format` accepts |
| third | *(current)* full SemVer grammar, reusing the detector's own production |

Two forgery channels were closed alongside it: writing the literal placeholder `<version>` into the
document reproduced a normalised document exactly, on **both** the named-key channel and the inline
`tool@version` channel. The normalisation now hashes a manifest of normalised paths as well as the
document, so a value that normalises to the same bytes no longer collides with the placeholder.

### COREDEV-2805 — a timeout that reported someone else's

`${SECONDS}` is an integer sampled **before the fork**, and the pre-commit hook used it to infer
"we timed out" from a child's exit status. A child exiting 124 on its own account was laundered into
the hook's own timeout path. Measured: **10 runs out of 10** fail-open before, **0 of 10** after.

The inference is gone rather than corrected. The deadline belongs to a watchdog that **records
before it acts**, so the record exists whether or not the kill lands; `timeout` is demoted to a
backstop at `seconds + 10`. A deadline inferred from an exit code is not a deadline.

### COREDEV-2806 — the marker channel was assumed, not probed

An unwritable `TMPDIR` turned a real timeout into "killed by signal 15" (`rc=143`); it now reports
`rc=124`. A later round found the repair carried its own defect: creating the private directory with
`mkdir -m 700` proved the *directory* was creatable, not that the *marker file* could be written.
The probe now writes the file itself and falls back if it cannot.

### COREDEV-2807 — four ways to finish green having linted nothing

Four silent-skip paths in the pre-commit gate. The measured one worth keeping: in a checkout with no
`.trunk/`, `trunk check --index` exits **1** with `Please run 'trunk init'` — which the gate
reported to the developer as findings **in their own diff**.

### COREDEV-2808 — an observation the module deferred to, that nothing held in place

The SessionStart observation is committed as evidence and bound by a test to the live
`.claude/settings.json`, so the two cannot drift. A missing `python3` no longer leaves the detector
silent, and in `--session-start` mode the notice goes through the `systemMessage` hook envelope
rather than to a stderr nobody reads.

### COREDEV-2809 — a census that counted the wrong things, and an assertion that matched too much

The exactly-one-producer census now refuses `uses:` (reusable-workflow) jobs, whose check names are
decided in another file entirely. Separately, `assertIn("--index", argv)` was satisfied by
`--index-only`; the gate's arguments are asserted as **tokens** now. *This is the same defect class
as §2.2 below, found in a different file — see the note there.*

### COREDEV-2810 — a floor that was never enforced, advertised as enforced

mypy 2.3.1 **refuses** `python_version = 3.9`: on the command line a hard error, from a config file a
note followed by a silent fall back to its own default. Measured with the floor set, a PEP-604
annotation type-checked as `Success: no issues found`.

An unenforced floor advertised as enforced is worse than an unstated one, because it stops anyone
looking for the real check. The config now names a version mypy accepts, and the floor is enforced
by a check **derived from the file list CI byte-compiles on 3.9** rather than a hand-maintained
copy of it.

### COREDEV-2811 — an unfrozen lever, and a fixture that made every mutant pass

`.trunk/configs/**` was outside the freeze while being fully able to change what the required check
does; it is digest-frozen now, with the filesystem as oracle because trunk reads an untracked
planted config identically to a tracked one.

The drift-detector fixture pointed `origin/main` at `HEAD`. Rows 6, 7 and 8 of its table therefore
**all passed against a detector that read the checkout** — the exact mutant they existed to catch.
The survivor corpus now binds each finding to concrete executable case ids instead of a prose clause.

### The recurring 2.7.0 reversion — the SELECTION root-caused, the rebuild not

Not a stale marketplace. `.claude-plugin/marketplace.json` declared **no `version` key**, and without
one the installed version is resolved by taking the **first entry of a raw directory read** of the
plugin cache — no sort, no semver comparison. Index 0 on this machine is `2.7.0`.

`version` is now declared and enforced as a **fifth** version-sync point, read by name so a decoy
entry cannot satisfy it. **Two limits, stated because they bound the claim:** pinning only takes
effect once that version is cached, and this fixes *which* value is chosen — not the wholesale
registry rebuild, whose trigger is still unproven.

---

## §2 — The defects found on this PR's own work, and their fixes

These were found by the codex arm against the working tree and are fixed in the same breath as this
plan. They are listed separately from §1 because they are defects **this PR introduced**, not
defects it inherited.

### 2.1 — the mypy install could not run on the runner it was added for (P1)

`darwin-suite` has no `setup-python` step, so its `python3` is the runner's system interpreter:
PEP 668 externally-managed, which **refuses** a plain `pip install`. The PyYAML step immediately
above it carries `--break-system-packages` for exactly this reason; the step this PR added did not.
It would have failed on every macOS run — and because the cell it feeds now *fails rather than
skips* under `CI`, the job could not have gone green either way.

**Fixed with a venv, not the flag.** The flag is the wrong instrument here: PyYAML only has to be
*importable*, whereas the floor cell resolves the mypy **binary** through `shutil.which`, and a
fallback install can land the console script somewhere off `PATH`. A venv is externally-managed on
no platform and puts the script at a path we compute.

**And the first version of that fix carried a P1 of its own (codex, r1 — reproduced).** It added
the venv's whole `bin` to `$GITHUB_PATH`. `$GITHUB_PATH` **prepends**, so every later step's
`python3` became the venv's python — which holds mypy and *nothing else*, while every module in
the scripts suite opens with `import yaml`. Both jobs would have failed with
`ModuleNotFoundError: No module named 'yaml'`.

The local gate could not see it, because `$GITHUB_PATH` does not exist locally. That is the third
time on this branch that a change of mine was invisible to the local gate and would have been red
on CI, and the first two are recorded in §0 as process failures. The rule this yields is narrower
than "mirror CI": **a fix that manipulates the runner's environment cannot be validated by a local
run at all**, and needs a cell asserting the property statically.

What ships now publishes a directory containing **only a `mypy` symlink**, so `shutil.which` finds
the pin and `python3` is left exactly as the steps above configured it.

### 2.2 — a version guard that accepted the releases it existed to reject (P2)

`if pinned in reported` is a substring test. Against a pin of `2.3.1` it is **true** of a mypy
reporting `2.3.10`, and true of `12.3.1`. The guard whose entire purpose is refusing an ambient
binary therefore admitted precisely the neighbouring releases whose behaviour differs. The same
defect sat in the assertion (`assertIn`) as well as the resolver.

Both now compare a **parsed token** for equality. *This is COREDEV-2809's `--index-only` defect
again, in a second file — a check keyed on a spelling is not a check on the property. The two are
recorded together so the family is closed rather than half-closed.*

### 2.3 — four encodings of a detector, then a declaration

The original defect was small: the census asked whether the literal string
`unittest discover -s scripts/tests` appeared in a step, so a trailing backslash made a job
**silently exempt** while the suite stayed green. Four encodings were then defeated in turn:

| encoding | defeated by | round |
|---|---|---|
| literal substring | a line continuation; padded whitespace | 1 |
| both tokens on one logical line | quoting; a flag between the words; no `discover`; and a false positive on `echo …; ls …` | 2 |
| `shlex` argv per command | a quoted `;`; `2>&1`; `-s=`; `./`; `unittest.main`; `timeout`/`sudo`/`env -u`; `pytest`; `coverage` | 3 |
| **a substring mention** | **`env:` holding the path**; `working-directory:`; `${{ matrix.* }}`; a `uses:` step with no `run:` at all; a wrapper script | 4 |

**The fourth row ends the argument.** A step can run the suite while its `run:` text names nothing,
because the path lives in `env:` three lines above — which is this repository's own house style for
shared values (`CLAUDE_CODE_VERSION`, `GITLEAKS_VERSION`), and is exactly what zizmor's
template-injection remediation tells contributors to do. The repo's own linter pushes people toward
the one spelling the guard could not see. No amount of reading `run:` finds it.

Worse, the audit reproduced the consequence end to end: refactoring the two duplicated suite
invocations to share a `$SUITE_DIR` and deleting `darwin-suite`'s pin install — **the original P1
restored** — left all three predicates reporting no offenders.

#### What replaced it, and what round 5 then broke

Round 4 removed the detector: every job either installed the pin or was declared. Round 5 broke
**both halves of that**, on both arms independently, and the two findings are the same mistake:

| round-5 evasion | found by | why it worked |
|---|---|---|
| `env: {RUNNER_TEMP: /tmp/fake}` on the frozen install step | agy | the digest covered `run:` only |
| `working-directory:` on the frozen suite step | agy | same |
| `shell: bash -c "bash {0}; exit 0"` — probe measured **17 → 0** | codex | same; and it swallows the exit code |
| job-level `if: ${{ false }}` on `darwin-suite` | codex | nothing read job-level scheduling |
| a **declared** job acquiring an unpinned suite step | both | a declaration was recorded once and never re-checked |
| a `.yaml` workflow | codex | `glob("*.yml")`, and the ">= 4 files" control still passed |

Freezing `run:` alone and trusting a declaration forever are the same error: each covered *part*
of what decides whether the suite runs, and reviewers found the rest. A declaration records why
something was true once; without a binding it silently outlives its reason.

**So the unit is the JOB, and the whole of it.** `yaml.safe_dump(job, sort_keys=True)` covers the
steps, their `env`, `shell`, `working-directory` and `if`, and the job's own `if`, `defaults`,
`container`, `strategy` and `continue-on-error`. A job absent from the freeze table, or whose
digest has moved, is an offender. A declared job that acquires a step breaks its own digest, so the
declaration cannot outlive its reason.

**Round 6 then showed that sentence had claimed too much, twice** — the first revision said the job
digest covered "every input that decides what runs", and it did not:

- **Workflow-level keys are outside every job.** Prepending
  `defaults: {run: {shell: 'bash -c "bash {0}; exit 0"'}}` to `plugin-ci.yml` leaves all ten job
  digests **byte-identical**; both suite steps inherit that shell; and a measured probe — `python3`
  stubbed to exit 17 — returned **17 normally and 0 under the wrapper**. The suite's failure would
  have been reported as success with every cell green (codex, r6). `on:`, `env:`, `defaults:`,
  `permissions:` and `concurrency:` are frozen per file now. *(Implementation note: YAML 1.1 reads
  a bare `on` as the boolean `True`, so keys are stringified before sorting — sorting them raw
  raises `TypeError`, which is how this was found.)*
- **The freeze covers the workflow, not what the workflow invokes.** A declared job runs
  `scripts/review/linux-primitive-probe.sh`; editing that script to run the suite leaves every
  digest intact (codex, r6). **This one is NOT closed, and the reason is a judgement, not an
  oversight:** the transitive closure of everything CI invokes is unbounded — a script calls a
  script — and freezing the nine scripts declared jobs currently invoke would put a digest bump in
  front of `resolve-trunk-range.sh`, which is under active development in this very campaign.

  What bounds it instead is stated positively and asserted:
  **the suite's believed verdict comes from jobs that install the pin and are neither advisory nor
  conditional**, and removing the suite from those jobs, making one advisory, or putting one behind
  an `if:` each moves a frozen digest. An extra unpinned run inside an advisory job is therefore
  noise — it cannot make a required check report green having tested nothing, which is the hazard
  this campaign exists for. The residue is **COREDEV-2821**.

**Both extensions are read**, and the vacuity control now compares what is READ against what is
ON DISK rather than asserting a count — the previous control passed with an invisible workflow.

**The cost is deliberate and worth stating.** Editing any CI job now requires updating its digest
here, and the failure message prints the new value so that is one paste. For the file that decides
what CI runs, a checkpoint on every change is the point rather than the price; it is the trade
COREDEV-2804 already made for `.trunk/trunk.yaml`. The alternative — partial coverage — has now
been defeated five times.

## §3 — Forward plan: the rollout that is still owed

### M2a — carry the gate to `alpha`

**Measured, not assumed:** `origin/alpha` is **62 commits behind `origin/main` and 0 ahead** — a
strict ancestor. `main` carries `trunk-check.yml`, `trunk-check-push.yml`,
`trunk-parity-harness.yml` and `scripts/ci/resolve-trunk-range.sh`; `alpha` carries **none** of them.

This **moots the hazard the original plan spent a round on**: it warned that a literal or
interrupted cherry-pick could leave `alpha` holding a workflow whose guard invokes an absent
resolver. Because `alpha` is an ancestor, M2a is a **fast-forward**, which carries all four files
together or not at all. There is no partial state to land in.

Why it is required at all: GitHub runs the workflow **version present at the event's ref**, so a job
merged only to `main` never executes for an `alpha` PR. `alpha` would carry the config and emit no
`trunk-check` check run — and since ruleset `Control` targets **both** bases, requiring the context
at M4 would make it unsatisfiable on `alpha`. That is COREDEV-2767's exact failure, aimed at the
other protected base.

- [ ] Fast-forward `alpha` to `main`. Confirm afterwards that all four paths are present on `alpha`.
- [ ] Confirm the advisory job actually *emits* a check run on an `alpha` PR — presence of the file
      is not evidence that the event fires.

### M2b-evidence — cause a controlled canary failure

The canary workflow exists on `main` and its **static** half is accepted: the rollout evidence
records `cell16CanaryNotRequired` from a point-in-time ruleset read. Its **runtime** half has never
been produced, and revision 1 of this plan did not list it at all (codex, r1).

The original plan is specific about why this is hard, and that reasoning is carried here rather
than re-derived: the canary's `branches:` are exactly the ruleset's resolved targets (`main`,
`alpha`), and `push.branches` matches the branch actually pushed — so **no additional in-repo
branch can match it**, and the other route, pushing a lint-failing commit straight to protected
`main`, is what the ruleset exists to prevent.

- [ ] Produce the stimulus in a **provenance-bound disposable fork** whose default branch is named
      `main`, carrying the same canary workflow at the same SHA pins; land the failing commit there.
- [ ] **Enable Actions in that fork** — GitHub disables them on forks until someone turns them on,
      so without this the stimulus silently produces nothing and the cell is quietly unfalsifiable.
- [ ] Record the tuple **Trunk step `failure` / canary job `failure` / workflow run not failed**.
      Job-level `continue-on-error` does *not* make the job conclude `success`; it stops the job's
      failure from failing the *run*. A step-`failure`/job-`success` tuple is not producible at that
      scope, and asking for one makes the cell unpassable.
- [ ] **Bind the failure to the expected lint diagnostic.** A checkout, setup, download or fetch
      failure yields the same three conclusions while Trunk never reached lint evaluation — an
      unbound cell certifies a canary that never linted anything.
- [ ] **Commit the resulting evidence under `docs/planning/evidence/`.** M2c carries this step and
      M2b did not, which is the same omission in a second place: an uncommitted artifact leaves the
      cell calling `skipTest`, and the milestone reads complete while proving nothing (agy, r2).

### M2c-evidence — accept the harness artifact against its schema

The harness workflow exists on `main`. What does **not** exist is the accepted artifact. Cells 1 and
5 are unownable without it, and the milestone is not complete until the artifact is accepted
**against the stated schema**, not merely produced.

- [ ] Fire the harness on its dedicated fixture refs — `pull_request` into `harness-base`, and
      `push` to `harness/**`. It must fire on **real events**: the action maps `workflow_dispatch`
      to `check-mode=all`, and `GITHUB_EVENT_NAME` cannot be overridden, so a dispatch-only harness
      measures a mode the gate never runs.
- [ ] **Download the artifact from the run and commit it under `docs/planning/evidence/`.**
      Revision 1 omitted this and the omission is load-bearing: the harness *uploads*
      `parity-*.json` to Actions artifact storage, while the acceptance cell reads
      `EVIDENCE_DIR = REPO / "docs/planning/evidence"` from disk. With no committed artifact the
      cell calls `self.skipTest(...)` and the milestone looks complete while proving nothing —
      the exact "produced vs accepted" conflation this plan's own risk table warns about, which
      revision 1 then committed (agy, r1).
- [ ] Accept `parity-<event>.json` against its schema: captured argv, resolved range, and pre/post
      tree hashes. **Both** event paths must appear — the cell asserts `{"pull_request", "push"}`,
      because they resolve their ranges differently.
- [ ] **Capture the PRIMARY invocation's diagnostic, and reject a setup-only failure (codex, r2).**
      The judge currently checks `outcome != "failure"` and that `controlPost` differs from the
      fixture's original hash, and neither binds the primary failure to a *lint* diagnostic:
      injecting `"HTTP 503 downloading linter; lint never started"` leaves `parity_problems()`
      empty for both events — reproduced. The plausible sequence is real: argv is recorded before
      `exec "${real_trunk}"`, the primary invocation dies before linting, and the autofix control
      — scheduled `if: always()` — still succeeds and changes the fixture. So the artifact must
      carry the primary diagnostic, and a record whose primary never reached lint evaluation must
      be **rejected**, not accepted.
- [ ] Confirm `harness-base` and `harness/**` are documented in `CLAUDE.md` as **permanent**
      repository citizens. They are needed again at every Dependabot pin bump to re-derive the
      extension-point enumeration; deleting them is a change, not tidying.

### M3 — make the gate strict on both bases

Remove `continue-on-error` on **`main` and on `alpha`** — two landings, one PR per base, each with
its own version bump.

- [ ] The C3 assertion is **written at M2, enabled at M3**. M2 deliberately ships
      `continue-on-error: true`, so asserting C3 any earlier makes the suite intentionally red.
- [ ] Both bases go strict. Landing only `main` leaves `alpha` advisory forever, and the M4 cell
      then blocks rather than completes the rollout.
- [ ] **Evidence on each base separately**: one genuinely strict green run **and one deliberately
      red run**. A context observed only while failures were suppressed is a context that has never
      been able to fail, and promoting it would certify nothing.
- [ ] **Record what the original contract requires, not merely "it went red" (codex, r1).** Generic
      red evidence is indistinguishable from a setup failure, so each observation binds: the Trunk
      step's **API-reported `conclusion`** *and* its **expected lint diagnostic**, together with the
      workflow path, the **effective check name** (not the YAML job id) and the **exact head SHA**.
- [ ] Include **a real RETARGET case** and the historically-dirty-file controls the original plan
      requires. A gate observed only on a freshly-created branch has not been observed against the
      condition that actually breaks range resolution.
- [ ] **State the route for the red run, because the obvious one is closed (agy, r2).** `Control`
      protects `main` and `alpha` with an empty `bypass_actors`, so a failing commit cannot be
      pushed to either, and once `continue-on-error` is gone a failing PR cannot merge. The
      evidence therefore comes from a **PR targeting** the base whose head is deliberately red and
      **is never merged** — the check runs on the PR head, so no broken commit ever lands. Any
      `push`-event red evidence belongs to the non-required canary, not to this milestone.
- [ ] **Schedule cell 10's annotation observation (codex, r2).** The original contract requires a
      **non-fork PR** (no 403), exercise of the `--github-annotate-file` branch, and a produced
      `trunk-annotations` artifact, and it assigns that observation to the committed rollout
      artifact. M3's criteria named the conclusion and diagnostic but never scheduled this.
- [ ] **Commit each observation under `docs/planning/evidence/`**, for the same reason M2b and M2c
      must: an uncommitted tuple leaves its cell skipping.

### M4 / M4a — NOT IN SCOPE OF THIS PLAN

M4 adds the required context to ruleset `Control`. It requires **explicit maintainer instruction**
and M3's red runs on both bases. It is named here only to state that it is *out of scope* and must
not be self-authorised. M4a observes mergeability **read-only**; the merge endpoint is not called.

---

## §4 — What could still go wrong

| Risk | Why it is plausible here | What would catch it |
|---|---|---|
| The fast-forward of `alpha` is done as a cherry-pick out of habit | The original plan was written when a cherry-pick was the expected shape, and its text still describes that hazard | Post-landing check that all four paths exist on `alpha`, not just the workflow |
| The advisory job lands on `alpha` but never fires | Presence of a workflow file is not evidence an event triggers it — this is precisely the `main`-only failure restated | Observe an actual check run on an `alpha` PR |
| The harness artifact is produced but not *accepted* | "Produced" and "accepted against a schema" have been conflated once already on this campaign | The milestone gate is acceptance, and it is written as a separate box above |
| M3's "green run" is observed while `continue-on-error` is still set | A suppressed-failure green is indistinguishable from a real one in the UI | The deliberately red run — a gate that cannot go red has not been observed |
| A claim about which CI legs run is carried from memory | Revision 1 asserted "the macOS leg is push-to-main only, so a PR does not run it". **That is false** (codex, r1): `plugin-ci.yml` declares `pull_request: branches: [main, alpha]` and `darwin-suite` carries no `if:` guard, so it runs on every PR to either base. The true statement belongs to a *different* workflow's macOS matrix leg | Read the trigger block, do not recall it |
| A runner-environment fix passes locally and breaks CI | **Measured twice on this branch.** `$GITHUB_PATH` does not exist locally, so no local run can evaluate it — this is not "the gate does not mirror CI", it is a class the gate *cannot* cover | A static cell over the workflow, asserted on the shape rather than the run — which is how the venv P1 is now held |

---

## §5 — Testing

The local gate mirrors CI's checks and runs the scripts suite **twice** — once with `CI` unset and
once with `CI=1` — because the 3.9-floor cell's behaviour differs between them, and a commit passed
all thirteen locally then went red on CI for exactly that reason.

**Stated precisely, because the first revision overclaimed it (PR #85 audit): that gate is a
maintainer-side script (`~/.claude/handoffs/coredev-2780-gate.sh`), NOT a file in this repository.**
Nothing in the repo runs the suite under `CI=1`, so a contributor without that script gets no
warning of the class it exists to catch. Treating it as a repository control would be wrong; it is
a personal harness, and closing that gap properly is COREDEV-2817.

Cells covering §2, after the whole-job freeze:

- `EveryJobIsFrozenAndClassified` — every job matches its frozen definition; every declaration
  (freeze table, reason table, advisory table) still describes a job that exists and behaves as
  declared; the two tables partition the same jobs; **what is read equals what is on disk**; the
  pin-installing jobs are named; and the `.yaml` reader is *exercised* on a scratch directory
  rather than asserted about — the first version of that cell checked a docstring for the string
  `*.yaml`, which is a check on a spelling, the exact defect this section exists to record.
- `TheStepsThatChangePathAreFrozen` — the `$GITHUB_PATH` step bodies are frozen, exactly two
  exist, the published directory is not inside a venv created there, and no pin-installing job is
  advisory or behind a job-level `if:`.
- `TheVersionGuardComparesTokensNotSubstrings` — runs a real stub binary rather than mocking.

**Five mutants, five reddenings**, one per round-5 evasion — `env:`, `working-directory:`,
`shell:`, a job-level `if:`, and a declared job acquiring a suite step.

**And one of those five initially passed because the PROBE was wrong, not the guard.** Inserting a
second `run:` key into an existing step produces a duplicate key that PyYAML resolves to the last
occurrence, so the parsed job never changed and nothing should have failed. A real added step
moves the digest. That is the fourth bad probe on this branch, and the lesson is the same each
time: **a probe that reports success without observing anything is indistinguishable from a pass**.

## §6 — Files changed

| Path | Change |
|---|---|
| `.github/workflows/plugin-ci.yml` | pinned-mypy install moved into a venv in **both** jobs that run the scripts suite |
| `scripts/tests/test_python39_floor.py` | **detection replaced by declaration**: every job in every workflow installs the pin or is declared; the two `$GITHUB_PATH` steps and the two suite steps are digest-frozen; structural `if:`/`continue-on-error` checks; vacuity controls; 26 cells |
| `docs/planning/COREDEV-2780_GATING_FOLLOWUP_PLAN.md` | this document |

---

## §7 — Open questions for the maintainer

1. **M2a's landing shape.** A fast-forward of `alpha` to `main` carries 62 commits, not just the
   four gate files. That is what "strict ancestor" means and it is the plan's own stated intent —
   but it is a larger movement than "land the job on alpha" sounds like, so it is surfaced rather
   than assumed.
2. **PR #85's merge.** Eight tickets are In Review against it. Merging requires explicit
   instruction, which has not been given and is not assumed here.
3. **COREDEV-2780's own status.** Its eight children are In Review; 2812 and 2813 remain open by
   design. The parent was left untransitioned because no single status is clearly supported by
   mixed evidence.

---

## §8 — Notes

- **Pre-gate round (against the tree before this plan existed).** `agy` returned
  `REQUEST_CHANGES` with two findings, **both refuted** against the file contents: the CI-fail
  guard it reported absent is present in both cells, and the install step it reported as landing in
  one job is in both. Its stated mechanism — that the ubuntu job "omits `-s` or spreads across
  multiple lines" — is contradicted by that job's own single-line command. Recorded so a later
  round does not re-raise them.
- **Round 1 of this plan's gate: `agy` APPROVE_WITH_NOTES, `codex` REQUEST_CHANGES.** Both arms
  were substantive and their findings were largely **disjoint**, which is the useful outcome —
  codex found the `$GITHUB_PATH` P1 and the argv-quoting evasions; agy found the missing M2c
  commit step and two evasions codex did not raise. Every finding acted on was reproduced locally
  before being accepted, and one of agy's three claimed evasions turned out to be caught by the
  predicate as written.
- The standing reliability note holds and is refined: **weight the arm that produces a
  reproduction** — but that is a rule about individual findings, not about arms. Weighting by arm
  would have discarded agy's round-1 findings on the strength of its round-0 record, and two of
  them were real.
- **agy voided two of six rounds with a `.mypy_cache/`, and the in-repo fix was built and then
  BACKED OUT.** The harnesses fingerprint the disposable checkout, so a reviewer that runs mypy to
  check a claim leaves a cache and the round is discarded — round 2 and round 6, the second time
  despite an explicit read-only instruction in the prompt, which is what proves the instruction was
  never the control. The harness already records the correct remedy for the identical `__pycache__`
  problem: *suppress at the source, never exclude a path from the manifest, because an exclusion is
  a blacklist a real mutation could hide behind.*

  I implemented that — `MYPY_CACHE_DIR` redirected outside the checkout in all three harnesses —
  and then reverted it, because **two of those three files carry pre-existing `shfmt` debt, so
  editing them at all turns the gate red, and paying that debt means reformatting files whose exact
  bytes ten test modules `.replace()` on.** That is the COREDEV-2771 hazard precisely: shfmt retabs,
  the anchors silently no-op, and mutation proofs go green while testing nothing (182 failures from
  shfmt alone, measured).

  The susceptibility is pre-existing — it voided COREDEV-2711 rounds too — so it is **COREDEV-2822**
  rather than in-flight work. Verified in the meantime: the harness does not sanitise its
  environment, so exporting `MYPY_CACHE_DIR` at the invocation redirects the cache and leaves the
  checkout clean. That is a workaround for this campaign's rounds, not a repository fix.

- **Post-gate fixes are ungated by construction.** Everything in §2 after a round is written in
  response to review and has not itself been through one. That is why round 2 exists, and why
  round 3 will.
- **Round 2: codex `REQUEST_CHANGES` (5 findings, all reproduced). agy's round was VOID.** The
  isolation harness exited 3: the reviewer left a `.mypy_cache/` directory — 19 files — inside the
  disposable checkout. That is the COREDEV-2607 signature, agent-mode behaviour, and it is exactly
  what the harness exists to catch. **A void round cannot count toward the gate**, so round 2 has
  one valid arm.
- The voided arm's *findings* were still triaged, because a defect does not stop being real
  because the round that surfaced it was invalidated — and they were checkable claims about file
  contents. Two of them (`-s=scripts/tests`, `-s ./scripts/tests`) I doubted and then confirmed by
  running the commands. They are fixed. **But they are not gate evidence**: agy must be re-run for
  a valid round.
- Round 2's findings landed almost entirely on **round 1's repairs**, which is where the prompt
  pointed both arms. Four consecutive fixes on this campaign have each introduced a defect; this
  round makes it six, counting the `PERF401` fix that produced a mypy error and the venv fix that
  produced the `$GITHUB_PATH` P1.
