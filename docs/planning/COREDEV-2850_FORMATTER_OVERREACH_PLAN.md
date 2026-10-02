# COREDEV-2850 + COREDEV-2860 — the required gate's effective scope is not its declared scope

**Tickets:** COREDEV-2850 (High, blocks COREDEV-2780 M4) · COREDEV-2860 (Highest, security)
**Epic:** COREDEV-2485 · **Branch:** `fix/COREDEV-2850-formatter-overreach` · **Base:** `main` (`5f877ec`)
**Status:** planning — not implemented

---

## §0 — Why these two are one change

They are the same property from opposite sides:

| | ticket | the gate's effective scope vs its declared scope |
|---|---|---|
| **over-enforcement** | 2850 | blocks on findings the author did not introduce |
| **under-enforcement** | 2860 | two security linters read configs nothing freezes |

**The overlap is measured, not asserted.** COREDEV-2860 touches **exactly one file**, and it is one
of COREDEV-2850's: `scripts/tests/test_trunk_check_workflow.py`. **§A5's table is the single
authority for Part A's file set — this section deliberately states no count** (gemini, r2: §0 said
"nine changed plus one unchanged" while §A5 listed eleven plus one, and a count duplicated across two
sections is a derived value that goes stale, which this repository has been bitten by three times in
one PR). Within it, 2850 edits
`ARGUMENTS_LITERAL` and 2860 edits `TRUNK_CONFIG_DIR` / `_config_tree_digest` /
`EXPECTED_CONFIG_TREE_DIGEST`.

Splitting them means running the mandatory dual-review gate twice over the same module, taking two
version bumps, and rebasing the second onto the first in the same file. Bundled: one gate, one bump,
one contract revision.

**The risk of bundling is stated:** 2860 is a live security weakening at Highest, and bundling makes
it wait on 2850's review rounds. Accepted because they are reviewed in the same rounds — the
wall-clock is the same — and because a half-revised contract file is its own hazard.

---

# PART A — COREDEV-2850: the gate over-reaches

## A1 — The defect

COREDEV-2780 §7 cell 3 is titled **"The gate does not over-reach"**. It does.

Under `trunk check --ci --upstream=<sha>`:

| family | linters | on a touched file |
|---|---|---|
| **lint** | shellcheck, markdownlint, ruff, mypy, bandit, … | pre-existing reported as `N existing issues` and **suppressed** — correct |
| **format** | `black`, `isort`, `prettier`, `shfmt`, `taplo` | evaluated **whole-file**, reported as **NEW** on any modified file |

A formatter has no per-issue novelty — the "issue" *is* the file being unformatted — so diff-scoping
degrades to per-file. **An otherwise clean edit to an already-misformatted file fails the gate for
debt it did not introduce.**

## A2 — Why it blocks M4

M4 promotes `trunk-check` to a required context with `bypass_actors: []`. Measured on a bounded
sample of 22 tracked files (`trunk check --all` is prohibited): **16 of 22 — 73% — are unformatted**,
including `agents/*.md`, `skills/*/SKILL.md`, `scripts/lib/*.sh`, `scripts/tests/*.py`. Corroborated
by `trunk fmt --all` having rewritten **191 files** (COREDEV-2771).

Promoting today blocks most PRs in this repository for pre-existing debt.

## A3 — Options, and why option 1

**Option 2 — format the repository.** Rejected: `trunk fmt --all` took the mutation suite from OK to
**211 failures + 5 errors** (shfmt alone = 182), because those tests `.replace()` exact shell bytes,
and separately rotted 9 of 38 plan citations. Its own project, with its own gate.
**Option 3 — narrow cell 3's criterion and accept.** Rejected: documents the hazard away while M4
ships a gate that blocks unrelated edits.
**Option 1 — exclude formatters from the REQUIRED job only.** Chosen.

### Validated by measurement, four arms

Same finding-neutral edit to `scripts/validate-hooks.py` (55 pre-existing findings, unformatted):

```
A  current args   --filter=-markdown-link-check
     -> 55 existing issues / ✖ 2 unformatted files                       RED   (the defect)
B  formatters excluded (+ -black,-isort,-prettier,-shfmt,-taplo)
     -> 55 existing issues / ✔ No new issues                             GREEN
C  CONTROL: arm B + one genuinely new finding (an unused import — `import codecs`)
     -> ruff/E402 (module level import not at top of file)
        + ruff/F401 (`codecs` imported but unused) / ✖ 2 new lint issues  RED   (still catches)
D  SECURITY CONTROL: arm B + an AWS-shaped key in a new file
     -> gitleaks/aws-access-token, high / ✖ 1 new lint issue             RED   (§4 cell 3 holds;
        note trunk counts gitleaks under LINT issues, not "security issues")
```

**Arm C is the one that matters.** Without it, B is indistinguishable from disabling the gate.

## A4 — Where formatting stays enforced

| site | formatters | why |
|---|---|---|
| `.githooks/pre-commit` (`trunk check --index`) | **CHECKED, not enforced** | staged diff at commit time, fixable with a scoped `trunk fmt <file>` — and it works: it rejects §A5's own edit. But COREDEV-2780 §3b classifies it as a local convenience, not a policy boundary: it needs a **manual per-clone `core.hooksPath`** (nothing in the tree installs it, and no CI job verifies it ran), an executable hook, and `git commit --no-verify` bypasses it outright |
| `trunk-check-push.yml` (canary) | **POST-MERGE ONLY** | `on: push: branches: [main, alpha]` — it never runs on a PR — and job-scoped `continue-on-error: true`, so the workflow RUN is green and the failure is a job `conclusion` readable only through the REST API. It records formatter findings after the fact; it does not hold any line during review |
| `trunk-check.yml` (**required**) | **EXCLUDE** | the only site where a formatter blocks work the author did not cause |

**After Part A no BLOCKING surface enforces formatting.** That is the honest version, and it is
stronger than "bypassable with `--no-verify`" because it can be checked: the hook is a manual
per-clone local convenience with three independent defeaters, and the canary is post-merge and
non-failing. Bought: the required gate stops false-blocking ~73% of the tree, and stops blocking
edits the author did not cause. Sold: formatting is CHECKED, not enforced, and a newly introduced
formatting defect no longer reds the required gate (§5).

Every *security* linter is untouched by Part A **as a matter of the value shipped, not of the
tests**: cell 4(d) is what makes that true going forward. One caveat belongs here rather than in a
reviewer's head — `--filter` denies by linter NAME, and of the five excluded names only `taplo`
carries a second, non-formatter command (`taplo lint ${target}`, no `formatter: true`). So the
required job loses TOML *linting* as well as TOML formatting, on the two tracked `.toml` files:
`.gitleaks.toml` — the security config Part B exists to freeze — and `.trunk/configs/ruff.toml`.
Accepted, and named. If a missing PR-time signal is too weak, the cheap addition is a
non-required PR-time advisory job carrying the formatters, which would also make cell 6 observable
on the surface that matters.

## A5 — The change

```
--filter=-markdown-link-check,-black,-isort,-prettier,-shfmt,-taplo
```

**In the required workflow only.**

| file | change |
|---|---|
| `.github/workflows/trunk-check.yml` | the `arguments:` input |
| `.github/workflows/trunk-check-push.yml` | the VALUE is unchanged — but it is no longer the same constant (see the split below) |
| `.github/workflows/trunk-parity-harness.yml` | the deliberately-failing fixture — see §A6 |
| `scripts/tests/test_trunk_check_workflow.py` | `ARGUMENTS_LITERAL`; **new** `CANARY_ARGUMENTS_LITERAL = "--filter=-markdown-link-check"`; `contract_problems` selects on `is_canary` for `arguments`; `EXCLUDED_LINTER` (singular) → `EXCLUDED_LINTERS` (frozenset) at its three call sites; a new `_canary_mutants` case covering the canary arguments branch; the comment above `EXPECTED_LINTERS` ("20 enabled minus §6.4's declared exclusion" — now minus SIX, and five of the frozen nineteen are enabled but no longer RUN in the required job) |
| `scripts/tests/test_trunk_upstream_parity.py` | `ARGUMENTS_LITERAL` |
| `scripts/tests/test_python39_floor.py` | re-pin **TWO** job digests, not one (codex, r3 P2):
`_JOB_DIGESTS[("trunk-parity-harness.yml","parity")]` as well, because §A6 necessarily changes that
job's fixture step and `test_every_job_matches_its_frozen_definition` hashes the WHOLE job. Codex
confirmed in-memory that the shipped pin matches and a fixture-body change moves it, so following the
single-re-pin instruction **cannot pass the full local gate**. The parity re-pin must come AFTER the
replacement fixture is validated (§A6), never before. And re-pin `_JOB_DIGESTS[("trunk-check.yml","trunk-check")]` → `ba363bdaf13c60d1a19c8b5cee9926f73420a495193c764c57b5ec58ec1b9194`. `_WORKFLOW_LEVEL_DIGESTS["trunk-check.yml"]` does **not** move — do not "fix" the wrong constant |
| `docs/planning/COREDEV-2780-contract.yaml` | re-pin `action_inputs_digest` `cc125ae6…` → `2e74b4a7806b1b4c579e14bc59038e1707dbad23a171cdae0d6ea495308931fe`; split `C4.arguments-required-literal` into a `required` and a `canary` obligation (or widen `entries:` and give each its own `literal_source`) so cell 11 generates a mutant for the new canary branch; amend the obligation's `statement` and its `/absent` case, which today say absence means "`markdown-link-check` runs in the required job" |
| `docs/planning/COREDEV-2780_REPO_GATING_HYGIENE_PLAN.md` §6.4 | **the literal's bytes live HERE**, not in the contract yaml. §6.4 must declare BOTH literals and why they differ, and its sentences "That exact scalar is the whole permitted value of the job's `arguments:` input" and "cell 13 asserts the SAME literal in the pre-commit invocation" must be rewritten. Editing a gated `*_PLAN.md` changes the bytes `review-verdict.py` binds to COREDEV-2780's recorded verdict — a cheaper SPLIT of authority is to move the bytes into the contract yaml as `required_literal` / `canary_literal` keys that a test READS (nothing reads `literal_source:` today) — but that is **not** an escape from the §6.4 rewrite above (codex, r4): YAML keys do not supersede §6.4's own "whole permitted value" and shared-hook sentences, so EITHER route updates and RE-GATES COREDEV-2780 during this migration. Budget that re-gate; do not plan around it |
| `docs/planning/evidence/parity-pull_request.json`, `parity-push.json` | RE-RECORDED by a harness run. They carry the OLD canonical form + digest and the old literal in `invocations[1]`. Hand-editing them forges sensor output; **deleting** them is worse — the judge then SKIPS and the module reports `OK (skipped=1)`, silently regressing COREDEV-2780 M2c to "cells 1 and 5 unowned" |
| `scripts/review/callers-scan-exemptions.tsv` | regenerated LAST in every commit (`python3 scripts/review/generate-callers-exemptions.py`) |
| `docs/planning/evidence/COREDEV-2780-rollout.json` | cell 3's `stillOpenForM3` residual resolves to COREDEV-2850 and §6 step 4 edits it — so it belongs in this table (codex, r3) |
| `scripts/tests/test_precommit_trunk_gate.py` | the ASSERTION is unchanged — it asserts the HOOK's literal, which keeps formatters — but `test_it_passes_the_declared_exclusion_literal`'s DOCSTRING must be rewritten (codex, r5): it says §6.4's literal "is required on BOTH surfaces", and after Part A the two surfaces differ BY DESIGN, so the docstring states the opposite of the property the suite now enforces. "Unchanged" was wrong about the module, not about the assertion |

The whole-string match is retained; C4's mutant (`payload: " --fix"`) stays and still produces its
own diagnostic under the six-name literal.

**§A5b — what `--filter` actually accepts.** Three measured facts, because two of them change what
cell 4 has to check and one is a new coupling this change creates:

1. **Names are validated against `lint.enabled`.** An excluded name that is not enabled aborts the
   run with EXIT 2 — an argument error, not a lint failure. Today one name carries that coupling;
   Part A makes it six, and dropping any of the five from `lint.enabled` is a plausible follow-up
   edit *precisely because* they no longer run in the required job. Cell 4 should extend the
   existing `assertIn(EXCLUDED_LINTER, self.names)` to all six.
2. **Issue codes are accepted and NOT validated.** `-bandit/B9999` is taken silently; a real code
   silently suppresses. This is why cell 4(c) rejects any entry containing `/`.
3. **Mixed sign and globs are refused** (`✖ [--filter] cannot contain a mix of linters to include
   and exclude`; `'b*' is not a supported linter`), so the "one stray positive entry turns the
   minus-list into an allowlist" hazard is NOT reachable. Recorded as verified, not left unstated.

**The literal now exists in two places with DIFFERENT values by design.** That is the hazard this
introduces, and a comment does not close it: with the split in place, collapsing the two literals
passes. Cell 4(b) is the assertion that makes "identical again" fail; §6.4 is where the two
literals and the reason they differ are declared.

**§A5's edit must then be re-formatted before it can be committed.** black rejects BOTH test
modules after the literal change, in OPPOSITE directions: `test_trunk_check_workflow.py`'s
parenthesised assignment must COLLAPSE to one line, `test_trunk_upstream_parity.py`'s one-line
assignment must EXPAND into parens. Run `trunk fmt` on those two files only — scoped, never
`--all` (COREDEV-2771).

## A6 — The parity harness inherits the exclusion, and its fixture stops working

`.github/workflows/trunk-parity-harness.yml` deliberately EXTRACTS `arguments:` from
`trunk-check.yml` ("the harness must run what ships") and `raise SystemExit`s if the contract's
`action_inputs_digest` does not match. So Part A changes the harness twice over:

1. Its `inputs` step hard-fails on the stale digest until the contract is re-pinned.
2. Its deliberately-failing fixture stops failing. `harness-fixtures/fixable.sh` is a mis-indented
   shell file whose ONLY finding is shfmt's whole-file `fmt` — under the six-name literal it
   produces nothing, the Trunk step concludes `success`, and `primary_diagnostic()` returns None.
   The judge then refuses the record on two counts ("the deliberately-fixable fixture did not make
   the pinned action fail"; "the primary run named no diagnostic on the fixture"), so COREDEV-2780's
   cells 1 and 5 become structurally unprovable — the sensor cannot emit acceptable evidence at all.

**The fix:** replace the shfmt fixture with one that satisfies BOTH properties, not just the
obvious one. A surviving diagnostic alone does NOT preserve COREDEV-2780 cell 5 (codex, r1): the
harness's `autofix-positive-control` step must be able to CHANGE the fixture using the same shipped
inputs plus `--fix`. So the replacement must be (i) reported under the six-name literal — the harness
already contemplates a positional linter — AND (ii) **autofixable by that same invocation**.
**`shellcheck/SC2086` satisfies (i) and FAILS (ii)** (gemini, r2): trunk does not autofix unquoted
expansions, so choosing the harness's existing example would red `autofix-positive-control`. Pick a
rule from an enabled non-formatter linter that trunk CAN autofix — `codespell`, or an autofixable
`ruff` rule — and verify the choice by running the shipped inputs plus `--fix` against the candidate
fixture BEFORE committing it. A diagnostic that survives the filter but cannot be
autofixed leaves the control unable to move the file. This currently fails CLOSED — `parity_problems()`
rejects an unchanged control — so the omission would surface as a confusing judge refusal rather than
a silent pass, but it must be designed for, not discovered.

The judge's `test_an_absent_position_is_accepted_because_shfmt_reports_none` and its `-:-` rationale
become stale in the OPPOSITE direction and need re-wording, not deletion. **`ARGUMENTS_LITERAL` and
the diagnostic parsing in `test_trunk_upstream_parity.py` move in the SAME COMMIT as the fixture and
the harness** (gemini, r1) — split across commits, the judge validates a fixture that no longer
matches the literal it is parsing for.

**Sequence in §6, before the version bump:** harness fixture change → `action_inputs_digest`
re-pin → re-run the harness on its permanent refs (`pull_request` to `harness-base`, `push` to
`harness/**`) → accept the regenerated `parity-*.json` → only then is Part A shippable without
regressing M2c.

---

# PART B — COREDEV-2860: two security linters read unfrozen configs

## B1 — The defect

Cell 4b freezes `.trunk/configs/**`. But `.trunk/trunk.yaml` wires two security linters to configs
**outside** that tree (only zizmor carries trunk's `is_security` flag; gitleaks does not — cell 4(d)):

- `gitleaks` — `environment: GITLEAKS_CONFIG = ${workspace}/.gitleaks.toml`
- `zizmor` — `.github/zizmor.yml`, found **by convention** (see B3)

Both tracked. Neither frozen.

**Measured:** a blanket `[[allowlists]]` (`regexes`/`paths` = `.*`) in `.gitleaks.toml` plus a
blanket `ignore` in `.github/zizmor.yml` leaves `test_trunk_check_workflow` at **70 tests OK**. The
freeze does not move; cell 4 and cell 4b both pass.

## B2 — Why it is worse than the original

The `.gitleaks.toml` half **also disarms `plugin-ci.yml`'s separate `secret-scan` job**, which
passes the same `--config`. One unfrozen tracked file therefore defeats **one of the five contexts
ruleset `Control` requires today — `secret-scan` — AND the `trunk-check` gate M4 is about to make
the sixth**, i.e. the repository's only automated secret detection on both of its surfaces. A PR
could introduce a credential and pass every required check.

**What cells 7-11 do and do not buy.** They convert "weakened silently" into "weakened in a commit
that also updates a 64-hex constant". A digest freeze is a CHANGE detector, and this module's own
documented procedure is to re-pin it "in the same commit, with the reason" — measured on the
shipped mechanism Part B extends. So §B2's severity is closed against ACCIDENTS, not against
intent, and the ticket must not be recorded as closing a Highest security hole it makes visible.
Closing it against intent needs at least one cell over the CONTENT rather than the digest:
`.gitleaks.toml` carries no allowlist whose `regexes`/`paths` is `.*`, and `.github/zizmor.yml` no
blanket ignore.

## B3 — The wrinkle that makes the obvious fix fail OPEN

COREDEV-2860 recommends *deriving* the frozen set from `trunk.yaml`'s own config references rather
than hard-coding a second directory. That is right, and **insufficient on its own**:

- `gitleaks` **is** derivable from `trunk.yaml` — `definitions[].environment[].value` names
  `${workspace}/.gitleaks.toml`.
- `zizmor` **is not** — but not because it is "found by convention". `.github/zizmor.yml` is a
  `direct_configs` entry of trunk's own zizmor plugin definition, and this repo's
  `.github/zizmor.yml` says so on line 1: "Trunk discovers this at .github/zizmor.yml (a
  `direct_config`)". The reason a test cannot derive it is that those definitions live under
  `.trunk/plugins/**`, which `.trunk/.gitignore` excludes (`git ls-files .trunk/plugins` -> 0) and
  which the CI job running this suite never materialises. So the declared list stands in for an
  artifact the test cannot read — which is why its members must be ENUMERATED from that definition
  (via `trunk config print`) and pinned, not invented one linter at a time. Getting the reason
  wrong is what hid `.gitleaksignore` (§B3(2)).
- `direct_config` is worth naming as a shape with no live instance: `grep -c direct_config
  .trunk/trunk.yaml` -> 0.

**So the frozen set is a UNION of two sources, and each needs its own guard:**

1. **Derived** — every path referenced by `lint.definitions[].direct_config(s)`,
   `environment[].value`, or a `${workspace}`-rooted token inside `commands[].run`, ADJUDICATED by the
   procedure below. The workspace root itself is never a member (a bare `${workspace}` would make the
   entire repository the frozen census).
   **Adjudication — no step resolves a path, collapses `..`, or compares paths as strings** (codex, r5
   P1 and r6 P1; gemini, r6). Revision 6 specified "`.`/`..` normalisation", and that normalisation was
   itself the next hole.
   (i) Substitute `${workspace}` with the workspace ANCHOR as given; take a relative operand relative to
   the anchor. The anchor is never examined or resolved — a platform alias ABOVE it (macOS
   `/var -> /private/var`) is not a component of any reference.
   (ii) **REFUSE any operand with a `..` component beneath the anchor.** Lexical normalisation and the
   filesystem DISAGREE whenever an earlier component is a symlink: with `workspace/policy ->
   outside/child`, `${workspace}/policy/../security.toml` normalises to `workspace/security.toml`, but
   the linter follows `policy` first and reads `outside/security.toml`. Normalising first hashes a file
   the linter never reads and leaves every edit to the one it does read invisible (codex, r6 P1 —
   measured on this host: `/var/../private` resolves to `/private/private`, where lexical normalisation
   yields `/private`). Refusing `..` REMOVES the ambiguity rather than adjudicating it. `.` components are
   dropped; they never traverse.
   (iii) **Containment is COMPONENT-WISE** — `PurePosixPath(operand).relative_to(anchor)` — never
   `str.startswith`, which admits a sibling sharing the anchor's spelling (`${workspace}_extra/x`). An
   operand not relative to the anchor is OUT OF SCOPE and is RECORDED as out of scope, never dropped
   silently.
   (iv) **`lstat` every component beneath the anchor, top-down, and REFUSE a symlink at ANY of them** —
   the leaf or an ancestor. `Path.is_symlink()` inspects the final component only, so a leaf-only check
   reads `${workspace}/sym_dir/config.toml` straight through a symlinked `sym_dir` (gemini, r6). This
   step applies to EVERY member, whatever its source — DECLARED paths and `.trunk/configs/**` included.
   **An absent component ENDS the walk; it does not refuse** (codex, r7). `lstat` raising `ENOENT` or
   `ENOTDIR` means nothing at or below that component exists, so nothing below it can be a symlink; the
   member is handed on whole, and an absent OPTIONAL CANDIDATE reaches `_digest_of_member` and
   contributes its `missing` marker. Any OTHER `lstat` error REFUSES (fail closed). A literal,
   unconditional `os.lstat` walk raises instead on every absent candidate — `.gitleaksignore`,
   `zizmor.yaml` — and reds the shipped tree, because optional candidates are absent by definition.
   (v) Hand the surviving member path to `_digest_of_member`.
   **Every ambiguous or link-bearing reference REDS the suite; none is dropped** (codex, r5 P1).
   Resolving for containment would DISCARD `${workspace}/policy/security.toml -> /outside/security.toml`
   — lexically inside, target outside — and a discarded reference never reaches `_digest_of_member`:
   §B4's refusal never fires, `REQUIRED_OCCUPIED_MEMBERS | OPTIONAL_CANDIDATE_MEMBERS` equals the
   TRUNCATED enumeration so COVERING passes, and every later edit to that target is invisible.
   **COVERING cannot protect a path enumeration has already thrown away.** Only an operand outside the
   anchor's LEXICAL namespace is out of scope — and that namespace is a spelling, not an inode (codex,
   r7). An absolute operand that reaches the workspace by another spelling, `/var/...` against an anchor
   spelled `/private/var/...`, is recorded OUT OF SCOPE although `samefile()` is true. That is the
   accepted price of never resolving. It is recorded rather than dropped, and introducing such an
   operand is itself an edit to `.trunk/trunk.yaml`, which moves that file's frozen digest and needs a
   reviewed re-pin (codex measured the `/var` versus `/private/var` change: the digest moves).
   **That freeze has one more blind spot, disclosed here because revision 8 denied it** (codex, r8 —
   reproduced). `_normalised_trunk_config` does NOT normalise only version fields: line 488 runs
   `re.sub(r"@\d+[\w.\-+]*", "@<version>", ...)` over the WHOLE dumped document, so a reference
   repointed from `${workspace}/policy/plain@1.toml` to `plain@2.toml` normalises identically and the
   `trunk.yaml` digest does not move. **Part B closes this only PARTLY — revision 9 overstated it**
   (codex, r9). Because every member contribution is an unforgeable `[kind, rel, digest]` record (§B4),
   a repoint that CHANGES THE UNION moves the aggregate — a guarantee that revision 10's
   delimiter-joined encoding did NOT actually provide (codex, r10). Two cases stay unfrozen until COREDEV-2867 lands:
   - **switching between references that are ALL already enumerated** — e.g. `direct_configs` lists both
     `policy/plain@1.toml` and `policy/plain@2.toml`, and `environment[].value` moves from the first to
     the second. The union, every member contribution and the normalised `trunk.yaml` are all identical,
     yet the linter now reads a different policy. Member-path labels cannot see a SELECTION change;
     only freezing the raw reference selection can, and that is COREDEV-2867's fix, not this plan's;
   - **an out-of-scope reference** contributes no member at all, so its `@1` → `@2` repoint is invisible.
   Both need a config path containing `@<digit>`, which no shipped reference has. Narrowing the regex to
   actual version fields changes shipped normaliser code and is OUT of this plan's scope — it is
   ticketed as **COREDEV-2867** rather than folded in.
   **None of (ii)-(iv) reds the shipped tree** (verified 2026-10-02): its only two live references,
   `${workspace}/.gitleaks.toml` (`.trunk/trunk.yaml:67`) and
   `${workspace}/.trunk/configs/markdown-link-check.json` (`:77`), contain no `..`, and no member, no
   ancestor of a member, and no tracked path is a symlink.
   Guard: **the derivation must be proven to reach the DIGEST, not merely to parse** (codex, r1 P1).
   Two separate premises were wrong. (a) "The derivation yields exactly ONE path" is false —
   `.trunk/trunk.yaml`'s `markdown-link-check` command also references
   `${workspace}/.trunk/configs/markdown-link-check.json`, which is already directory-covered. (b)
   Every currently-derived path is ALSO covered by another source: `.gitleaks.toml` is DECLARED, and
   the markdown-link-check config is under `.trunk/configs/**`. **So an implementation that parses
   DERIVED perfectly and then hashes only DECLARED + `.trunk/configs/**` passes every parse-level
   assertion, and no shipped input can expose it.** A guard on the parse certifies a fix that is not
   wired up.
   The guard is therefore an END-TO-END digest control, run against a synthetic workspace: place a
   config at a path that is outside DECLARED **and** outside `.trunk/configs/**`, reference it from a
   synthetic `trunk.yaml`, and assert the **production aggregate digest** changes when that target is
   CREATED, when its bytes are EDITED, and when it is DELETED. Then assert the negative: a mutant
   whose union discards the DERIVED contribution entirely must FAIL this cell. Parse-level checks
   (a second reference appears; removing `GITLEAKS_CONFIG` shrinks the result) remain as a floor,
   never as the whole test.
2. **Declared** — the `direct_configs` CANDIDATE PATHS of the enabled security linters, taken from
   trunk's own plugin definitions at the pinned `plugins.sources.ref` and then PINNED as a frozen
   literal set.

   **The declared set MUST be bound to the RAW plugin provenance, not the normalised one** (codex,
   r1 P1). `_normalised_trunk_config` deliberately erases a canonical `plugins.sources[].ref` so a
   routine `trunk upgrade` does not red the gate. That erasure is correct for its own purpose and
   catastrophic here: **a permitted upgrade can change which `direct_configs` a linter declares while
   both frozen digests stay byte-identical.** Cell 9 would go on approving yesterday's candidate set,
   cell 8 cannot see references that live inside the plugin, and a config planted at a
   newly-supported path escapes the census entirely.
   So a THIRD pin is required — `EXPECTED_PLUGIN_PROVENANCE`, over the RAW, UN-NORMALISED
   `plugins.sources[].uri` + `ref` (and `cli.version` where native discovery supplies candidates).
   When it moves, the declared enumeration must be re-derived and re-pinned in the same commit; the
   cell's diagnostic must say that, because "re-pin the digest" is the instruction that produced this
   class of defect twice already. This coexists with the version-normalisation policy rather than
   reversing it: normalisation governs what reds the LINT config digest, this pin governs when the
   candidate ENUMERATION is stale.
   **State the pin's LIMIT rather than over-claiming it** (codex, r3). `uri` + `ref` close drift in
   trunk's own plugin DEFINITIONS. They do not close drift in a linter's NATIVE discovery, which
   belongs to the linter's own version and can move without either pin or `cli.version` moving. No
   current bypass by that route was demonstrated, so the honest record is: this pin covers
   definition-declared candidates, native-discovery candidates fall outside its scope, and pinning the
   relevant linter versions is the follow-up if that gap is judged live.

   Today the declared set is, at minimum:
   `.gitleaks.config`, `.gitleaks.toml`, `.gitleaksignore`, `zizmor.yml`, `zizmor.yaml`,
   `.github/zizmor.yml`, `.github/zizmor.yaml`, `.checkov.yml`, `.checkov.yaml`, `.bandit`.
   **Those ten are a MINIMUM, not the enumeration** (codex, r1). The first seven were what one
   linter pair declared; the cached pinned definitions at `v1.11.0` also declare Checkov's
   `.checkov.yml` / `.checkov.yaml` and Bandit's `.bandit`. The rule is "every `direct_configs`
   candidate of every ENABLED security linter, enumerated from the pinned definitions" — and the
   derivation controls must exercise EVERY declared reference SHAPE (`direct_config`,
   `direct_configs`, `environment[].value`, a `${workspace}` token inside `commands[].run`), not
   just the one shape that happens to be live.
   Hand-listing one path per linter is what produced the hole this bullet exists to close:
   **`.gitleaksignore` is a live suppression lever that BOTH sources miss.** It is not referenced
   from `trunk.yaml` (so B3(1) misses it), is not `.github/zizmor.yml` (so a one-member declared
   list misses it), is not under `.trunk/configs/**`, and is not in `.gitignore` — so it can be
   committed, and a single line naming a finding's fingerprint turns `plugin-ci`'s `secret-scan`
   from red to green with the frozen digest unmoved. COREDEV-2860's own defect, surviving
   COREDEV-2860's fix.
   Guards, and BOTH of them apply to BOTH sources: (i) every member that exists must be tracked and
   non-empty; (ii) every candidate path — including ones holding nothing today — contributes to the
   digest, so CREATING one moves it. A guard keyed only on "whatever the tuple names exists and is
   tracked" is satisfied by substituting any other tracked path, and the digest that moves with it
   is re-pinned by the substituting commit.

**Say which axis each guard watches.** B3(1) watches the trunk.yaml REFERENCE — delete
`.gitleaks.toml` from disk and the derivation still returns it. B3(2) watches the FILE. Neither
watches the other's axis until both guards apply to both sources. The union is what the per-member
digest (§B4) hashes, alongside `.trunk/configs/**`.

## B4 — The change

| file | change |
|---|---|
| `scripts/tests/test_trunk_check_workflow.py` | replace `TRUNK_CONFIG_DIR` census with the union of B3(1)+B3(2)+`.trunk/configs/**`; re-pin `EXPECTED_CONFIG_TREE_DIGEST`; add the two source guards |

`_digest_of_tree(root)` is a DIRECTORY traversal: it iterates `root.rglob("*")`, which yields
nothing for a file. On a FILE root it returns `sha256(b"")`, and so does a root that does not
exist. Both new union members are files. **Reusing it per root therefore hashes nothing for exactly
the two configs this ticket exists to freeze, leaves the B1 mutant undetected, and makes "deleted"
byte-identical to "present".** That is the founding hazard of the whole 2780 family, one level down.

The union is hashed per MEMBER KIND, by a new `_digest_of_member(path)`:

| kind | contribution |
|---|---|
| directory | the record `["tree", rel, _digest_of_tree(path)]`, **with the tree's symlink branch changed to REFUSE** — see below |
| symlink | **REFUSED** — see below |
| regular file | the record `["file", rel, sha256(path.read_bytes())]` |
| missing | the record `["missing", rel, null]` — a DISTINCT kind, never the empty-tree constant |
| anything else — FIFO, socket, device | **REFUSED** at the member itself, before any read, naming the path and its kind |

**Every contribution carries the member's `rel`, directories included** (codex, r9). `_digest_of_tree`
labels descendants relative to the DIRECTORY's own root, so revision 9's bare `_digest_of_tree(path)`
gave two equal-content directories the same contribution, and repointing a reference from one to the
other moved nothing.

**Every record that feeds the aggregate is canonical JSON — `json.dumps([...], separators=(",", ":"))` —
never a delimiter-joined string** (codex, r10). Revision 10 encoded contributions as `f"{rel}:tree:{t}"`
and claimed the `tree:` tag kept a directory from colliding with a file. **That claim was false.** A
`rel` can itself contain `:tree`, so a DIRECTORY `policy_dir` holding `x.toml` and a regular FILE named
`policy_dir:tree` whose bytes are exactly the tree's input produce the identical string — no hash
collision needed; codex reproduced it. The same flaw is in the SHIPPED `_digest_of_tree`, which joins
`f"{relative}:{digest}"` entries with `\n`: a filename containing a newline forges a record boundary,
so one file named `a:<sha256(C1)>\nb` collides with the pair `a`, `b`. JSON QUOTES each field, so a `:`
inside a `rel` is data rather than a delimiter, and it ESCAPES an embedded `\n` (codex, r11), so the KIND, the `rel` and the record boundary are all unforgeable. The rule covers
both levels: each member contribution is `[kind, rel, digest]`, each `_digest_of_tree` entry is
`[relative, digest]`, and the aggregate is `sha256` over the sorted records joined with `\n`.
This changes `_digest_of_tree`'s output, which is absorbed by the `EXPECTED_CONFIG_TREE_DIGEST` re-pin
this plan already requires; every caller is in `scripts/tests/test_trunk_check_workflow.py` (the pinned
assertion, and mirror tests that compare before against after and are format-independent).
Cell 8(f) rows 17, 19, 20, 23 and 24 verify the directory member, missing versus empty, the repoint,
the cross-kind forgery and the in-tree boundary forgery.

**`_digest_of_tree` MUST ALSO REFUSE SYMLINKS — refusing only at `_digest_of_member` leaves the
bypass open one directory down** (gemini, r2 BLOCKER). `_digest_of_tree` hashes a symlink as
`b"symlink:" + link_target`, i.e. by SPELLING, and the table above delegates `.trunk/configs/**` to
it "unchanged". So a symlink at `.trunk/configs/ruff.toml` pointing outside the tree is still hashed
by spelling, and mutating its target leaves the digest unmoved — the exact defect the member-level
refusal was added to close, surviving inside the one member that was left alone. The refusal belongs
in `_digest_of_tree` as well, and the target-only mutation control must be run for a symlink planted
INSIDE `.trunk/configs/**`, not only for a top-level member.

**A member of ANY kind that is not a regular file, a directory, or missing is REFUSED.** The table
enumerates three kinds; a derived or declared candidate that is a DIRECTORY outside
`.trunk/configs/**` (e.g. `.config/checkov/`) would otherwise fall through to the regular-file branch
and raise `IsADirectoryError` at test time (gemini, r2). Directories are hashed with
`_digest_of_tree`; anything else — socket, fifo, symlink — is refused with a diagnostic naming the
path and its kind.

**THE REFUSAL MUST BE RECURSIVE, not only at member dispatch** (codex, r3). `_digest_of_tree`'s
non-symlink branch calls `path.read_bytes()`, so a FIFO planted as a DESCENDANT of a directory member
**blocks the test run indefinitely** and a socket **raises** — neither produces the diagnostic this
section promises, and a hang is worse than a failure because it carries no message at all. Kind
classification therefore happens for every traversed descendant, not just for top-level members, and
the controls include a nested FIFO and a nested socket.

**Symlinked config members are REFUSED, not hashed** (codex, r1 P1). Hashing `os.readlink(path)`
freezes the link's SPELLING and leaves the TARGET's contents unfrozen. The attack needs no forgery:
a reviewed relocation of `.github/zizmor.yml` to a symlink at `policy/zizmor.yml`, with the
prescribed re-pin, is legitimate — and a LATER target-only blanket-ignore edit then changes what
zizmor reads while **neither frozen digest moves and no re-pin is required at all**. That is strictly
worse than §B2's acknowledged coordinated-re-pin limitation, which at least demands a reviewed commit.
Resolving targets transitively instead was considered and rejected for this change: it needs escape
and cycle handling, and an incomplete resolver fails OPEN. Refusal fails CLOSED, and every config
member is a regular file today, so the refusal is inert until someone introduces the shape — at which
point they get a diagnostic instead of a silent hole. A target-only mutation control accompanies it:
plant a symlink member, mutate ONLY its target, and assert the census REFUSES rather than passing.
The refusal covers EVERY component beneath the workspace anchor, not only a member's final one
(§B3(1)(iv)): a symlinked ANCESTOR is refused exactly like a symlinked member, because a check on the
final component alone reads straight through it (gemini, r6).

and cell 4b's own anti-truncation guard,
`test_the_census_covers_every_config_the_repository_ships` — whose docstring is "A digest over an
empty or truncated census is a digest that cannot fail" — is extended from `TRUNK_CONFIG_DIR` to
every REQUIRED OCCUPIED member: each exists, is tracked, is non-empty, and contributes a digest
`!= sha256(b"")`. Leaving that guard scoped to the one member that did not need it is how this fails
silently.

**REQUIRED OCCUPIED and OPTIONAL CANDIDATE are different member classes, and conflating them makes
the census permanently red** (codex, r1 P2). §B3(2)(ii) deliberately admits candidate paths that hold
nothing today — that is what makes CREATING one move the digest — while an unqualified "every union
member exists and is non-empty" contradicts it directly. Following both literally reds the shipped
tree; deleting the absent candidates to recover green reopens the planting bypass the candidates
exist to close. So:

| class | membership | anti-truncation guard |
|---|---|---|
| **required occupied** | exists in the shipped tree and is load-bearing today — `.gitleaks.toml`, `.github/zizmor.yml`, `.trunk/configs/**` | MUST exist, be tracked, be non-empty, digest `!= sha256(b"")` |
| **optional candidate** | a union member that holds nothing in the shipped tree, WHATEVER its source — a declared `direct_configs` path, a DEMOTED `.trunk/configs/**` member, or a DERIVED-only path — e.g. `.gitleaksignore`, `zizmor.yaml`, `.checkov.yml` | MUST contribute a `missing` marker; CREATING it must move the digest; it is NOT required to exist |

**The two sets must be asserted DISJOINT and COVERING** (codex, r3): their intersection is empty and
their union equals the **PRODUCTION** aggregate's membership — production, because cell 8(e)'s
synthetic workspace deliberately carries a member in neither set. Without both halves a member can be
in NEITHER set — silently escaping every class guard while still contributing to the digest — or in
BOTH, where the required and optional rules contradict. Two scope corrections are ALREADY FOLDED INTO
the table above and into cell 9, and are recorded here as rationale, not as pending work: the optional
class is stated as a property of the MEMBER rather than of its source, because "declared
`direct_configs` paths" cannot accommodate a demoted `.trunk/configs/**` member or a future
DERIVED-only one; and **cell 9's tracked/non-empty guard applies to EXISTING members only** — applied
to an absent optional candidate it reds the shipped tree, which is the §B3/§B4 contradiction over
again.

Both classes are verified THROUGH the aggregate digest, not beside it — the cells observe the
digest MOVING, while the class assertions themselves live in the TEST, over the PRODUCTION member
enumeration. The two sets are frozen constants in `test_trunk_check_workflow.py` —
`REQUIRED_OCCUPIED_MEMBERS` and `OPTIONAL_CANDIDATE_MEMBERS`, both `frozenset` — so a class change
is a reviewed source edit rather than an emergent property of the tree (gemini, r2).

**The property verified here is ADMISSIBILITY, and only admissibility** (codex, r6 P2/P3 — this
SUPERSEDES the location rule of revisions 4-6, and keeps the goal of codex's r4 recommendation, which
was admissibility, while dropping the mechanism it was turned into). The aggregate digest must be
computable for a workspace whose membership includes a path in NEITHER frozenset; cell 8's synthetic
DERIVED path is the case that matters. That fails when something on the digest path enforces COVERING
over the digest call's OWN membership and so rejects the unclassified member. Cell 8(e) observes it,
and its mutant — unconditional COVERING over the call's own argument — discriminates.

**"No class validation anywhere in the digest helper" is WITHDRAWN as a verified rule.** Revisions 4-6
justified it by saying that disjointness, covering or the anti-truncation guard enforced inside the
digest seam would mean cell 8 "could never pass". That is false (codex, r6 P3): disjointness alone
never rejects an unclassified member, and validation scoped to the PRODUCTION enumeration passes on
cell 8's synthetic input. The rule is a MECHANISM, not a property, and it protects nothing this plan
claims. Production-scoped validation, wherever it runs, passes on a correctly classified tree and reds
on a misclassified one exactly as the test-level assertion does; that assertion is independently
required and independently mutated (cell 11c), so an extra copy elsewhere can only ADD failures, never
remove one — provided it has no side effect on membership, class bindings or hashed bytes. Validation
WITH such a side effect is not licensed by this withdrawal: it violates the admissibility, derivation
and candidate-planting invariants that cells 8(e), 8(a) and 11 assert (codex, r7). Nor is the rule checkable: rounds 5 and 6 found FOUR placements — a test-environment
predicate, a scope-preserving relocation, disjointness alone, and inlined literal copies of the
frozensets — each invisible to a name-based call-graph walk, the last reproduced in memory by codex. A
check that cannot establish its property is not evidence, so revision 6's call-graph check is DELETED
rather than patched a fifth time. Class assertions belong in the test, over the production enumeration
— a design note, which no cell asserts.

**Both directions of class change are reviewed edits, and DEMOTION was missing** (gemini, r2).
PROMOTION — a candidate becomes occupied — is a re-pin plus moving the path between the two
constants. DEMOTION — a required occupied member is deleted — is NOT resolvable by re-pinning the
digest alone: the anti-truncation guard ("must exist, be tracked, be non-empty") still fails, and an
engineer who only re-pins is left with a red suite and no instruction. Deleting a required member
therefore requires moving it into `OPTIONAL_CANDIDATE_MEMBERS` **in the same commit** as the re-pin,
which is the reviewed statement "this config is no longer load-bearing". The cell's diagnostic must
say which class it found, which it expected, and which of the two edits is missing.

---

## §4 — Verification cells (both parts)

**Part A**

1. **The over-reach is gone.** A PR whose only change is a finding-neutral edit to a named
   unformatted tracked file goes GREEN on the required job. Bound to a file with a *recorded*
   pre-existing formatter finding, so green cannot mean "already formatted".
2. **A new LINT finding still reds it** — arm C, as a CI observation, bound to a named diagnostic
   with file/line/column.
2b. **ARM E — the accepted loss, observed in both directions.** A file that is formatter-CLEAN at
   base, into which the PR introduces a format-only defect, goes GREEN on the required job and RED
   on the hook. Its canary half is bound by cell 6's stimulus constraint — without a controlled push
   environment the canary side of arm E is deferred, not observed. Without arm E the trade is
   evidenced only on the side that helps.
3. **A new SECURITY finding still reds it.** Formatters are excluded; `gitleaks`, `trufflehog`,
   `zizmor`, `bandit`, `checkov` are not. Without this, the exclusion list could be wider than
   intended and nothing would say so.
4. **The exclusion literal is a frozen SET, and nothing security-bearing is in it.** Standing
   assertions in `test_trunk_check_workflow.py` — not a probe-PR observation, because only a unit
   test survives the merge:
   a. Parse the required job's `arguments:` and assert the excluded ENTRY SET equals
      `frozenset({"markdown-link-check","black","isort","prettier","shfmt","taplo"})` — SIX entries:
      one declared exclusion plus the five `formatter: true` linters. This replaces the singular
      `EXCLUDED_LINTER` at its three call sites; the surviving `assertIn(EXCLUDED_LINTER,
      ARGUMENTS_LITERAL)` is a substring test that a seven-name literal also satisfies.
   b. Assert `ARGUMENTS_LITERAL != CANARY_ARGUMENTS_LITERAL`, with
      `required_names - canary_names == THE_FIVE_FORMATTERS` and
      `canary_names - required_names == set()`. THIS, not a comment, is what makes "identical
      again" fail — in both directions, naming which linters moved.
   c. Assert no excluded entry contains `/`. `--filter` accepts issue codes as well as linter names
      (`trunk check --help`: "comma separated list of linters and/or issue codes … e.g.
      '-eslint,-shellcheck/SC2301'") and trunk does NOT validate codes, so a code-scoped entry is a
      security-rule suppression that a name-set check cannot see.
   d. Assert the excluded set is disjoint from a HAND-LISTED security set
      `{gitleaks, trufflehog, zizmor, bandit, checkov}`. Hand-listed deliberately: `is_security` is
      not a usable selector — in trunk's own v1.11.0 definitions **gitleaks carries no `is_security`
      flag** (bandit, checkov, trufflehog and zizmor do), and gitleaks findings are counted as
      "lint issues", so both an `is_security`-derived guard and an oracle bound to the word
      "security" miss the one exclusion that disarms `secret-scan`.
   e. Assert all SIX excluded names are present in `lint.enabled` (gemini, r1). `--filter` validates
      names against the enabled set and aborts with **EXIT 2 — an argument error, not a lint
      failure** — when an excluded name is not enabled. Today one name carries that coupling; Part A
      makes it six, and dropping one of the five from `lint.enabled` is a plausible follow-up edit
      *precisely because* they no longer run in the required job.
   f. Mutants, each with its own diagnostic: a seventh entry; a formatter name dropped; a security
      name added; a code-scoped entry added; the two entries' literals swapped; an excluded name
      removed from `lint.enabled`.
5. **The pre-commit hook still blocks an unformatted staged file** — executed, not asserted. The
   whole of A4 rests on formatting still being caught somewhere.
6. **The canary still reports formatter findings — and needs a REACHABLE stimulus** (codex, r1).
   `trunk-check-push.yml` fires on `push` to `[main, alpha]` only, so a **never-merged probe PR
   cannot trigger it at all**; the check-runs API supplies an oracle, not an execution path. This
   cell therefore needs an explicit controlled push environment — the provenance-bound disposable
   fork already described in the rollout record (default branch named `main`, same workflow at the
   same SHA pins, **GitHub Actions explicitly ENABLED** — they are off by default on forks, and
   without enabling them the stimulus silently produces nothing and the cell is unfalsifiable).
   If that environment is not stood up, this cell is NOT satisfiable and must be recorded as
   deferred rather than quietly closed on the API oracle. The same constraint governs arm E's
   canary half (§5).

**Part B**

These are implemented as `C2850_Cell7_…` through `C2850_Cell11_…`. The module already owns
`Cell9_TheShippedWorkflowMeetsItsContract` and `Cell10_PermissionsArePinnedByValueAtBothScopes` for
COREDEV-2780's numbering; two `Cell9_*` classes in one file leaves no way to say which "cell 9" is
meant.

7. **The B1 mutant now reds.** Blanket `[[allowlists]]` (`regexes`/`paths` = `.*`) appended to
   `.gitleaks.toml` must move the digest; same for a blanket `ignore` in `.github/zizmor.yml`. Run
   against a COPY — and the mirror must copy each member BY TYPE: cell 4b's idiom is
   `shutil.copytree(TRUNK_CONFIG_DIR, mirror)`, which raises `NotADirectoryError` on a file member,
   so "as cell 4b already does" cannot be followed for the two new ones. The mutant paths stay
   independent literals, not read from the declared list, or the cell stops holding the line the
   moment someone "de-duplicates" it.
8. **The DERIVED contribution reaches the PRODUCTION aggregate digest** — an end-to-end control, not
   a parse test (gemini, r2 BLOCKER: revision 2 repaired §B3(1)'s prose and left this cell stating
   the superseded, insufficient version. An implementation computing
   `hash(DECLARED + .trunk/configs/**)` while keeping a separate, correct `parse_derived_paths()`
   passed the old wording).
   a. In a synthetic workspace, place a config at a path outside DECLARED **and** outside
      `.trunk/configs/**`, reference it from a synthetic `trunk.yaml`, and assert the **production
      aggregate digest** changes on CREATE, on EDIT of its bytes, and on DELETE.
   b. NEGATIVE MUTANT: an implementation whose union omits the DERIVED contribution entirely must
      FAIL this cell. Without (b), (a) is satisfiable by a digest that happens to cover the path
      through another source.
   c. **PARAMETERISED ACROSS ALL FOUR REFERENCE SHAPES** (codex, r3 P2). §B3(1) requires coverage of
      `direct_config`, `direct_configs`, `environment[].value`, and a `${workspace}` token inside
      `commands[].run`. Revision 3's cell specified ONE synthetic reference of unspecified shape — and
      a parser handling only the two shapes that are LIVE in the shipped `trunk.yaml` passes every
      observation here if the synthetic reference happens to use `environment[].value`. **The shipped
      config contains neither `direct_config` nor `direct_configs`, so no real input can expose that
      omission.** Run (a) once per shape, and add a PER-SHAPE OMISSION MUTANT: a parser that ignores
      exactly one shape must fail the cell for that shape.
   d. Parse-level checks — stub-to-`[]`, a synthetic second reference appearing, `GITLEAKS_CONFIG`
      removed shrinking the result — remain as a FLOOR beneath (a)-(c), never as the cell.
   e. **ADMISSIBILITY — the digest is computable for a member in NEITHER frozenset** (codex, r4-r6).
      The references this cell creates are, by design, in neither set, and the class assertions are
      test-level over the PRODUCTION enumeration (§B4, cell 11c); classifying the digest call's OWN
      membership is not a prerequisite of computing its digest (codex, r7). An implementation that raises, refuses, or silently DROPS such a member fails this cell.
      MUTANT: an UNCONDITIONAL COVERING check over the membership of the digest call's OWN argument —
      not over production — must red (e); that is the mutant (e) discriminates (codex, r5 P2,
      confirmed r6). (e) proves admissibility and nothing more. It does not prove — and this plan no
      longer asks anything to prove — WHERE class validation lives; §B4 explains why that rule was
      withdrawn rather than verified.
   f. **AGGREGATE-LEVEL ADJUDICATION controls, DERIVED-ONLY — and every exclusion rule in §B3(1) has a
      positive control at its ADJACENT boundary** (codex, r5-r8; gemini, r6). Rounds 7 and 8 each found
      one missing boundary row; revision 9 enumerates the CLASS instead. For every rule that excludes or
      refuses — root exclusion, `..` refusal, `.` dropping, symlink refusal, absent-component handling,
      containment — the nearest input that must NOT be excluded is a row.
      **Fixture.** ONE temporary outer directory holding sibling `workspace/` and `outside/` directories,
      both alive for the whole assertion (`symlink_to` already runs on both suite platforms at
      `scripts/tests/test_trunk_check_workflow.py:2295`, and `plugin-ci.yml` runs the scripts suite on
      Ubuntu and macOS). Each row's reference appears ONLY in the synthetic `trunk.yaml` — not at a
      DECLARED path, not under `.trunk/configs/**` — and every outcome is observed on the PRODUCTION
      aggregate, `DECLARED | DERIVED`. The background DECLARED set includes one PRESENT member and one
      ABSENT optional candidate, because step (iv) walks every member.
      **Observation rules — a row's observation is exactly what is written here, no stricter and no looser**
      (codex, r8: twice a draft observation stricter than the spec hid a gap the spec left open).
      - **Baseline first.** The aggregate over the background alone must SUCCEED. Without it, an unrelated
        refusal satisfies every REFUSE row vacuously.
      - **REFUSE** means the aggregate raises the freeze's DEDICATED refusal exception — one named
        exception class, raised deliberately — AND that exception names THIS row's operand. **An
        incidental exception never counts, even when its message names the path** (codex, r11).
        `read_bytes()` on a Unix socket raises `OSError: [Errno 102] Operation not supported on socket:
        '<path>'`, and a propagated `lstat` error carries its filename the same way, so revision 11's
        rule ("raises, and the diagnostic names the operand") passed the fall-through mutant on row 22 and
        a propagated `EIO` on row 16. Both were measured passing under that rule.
      - **Rows 21 and 22 additionally SPY on reads, and any read of the probe path is a failure.** "Refuse
        before any read" (§B4) is the property; an implementation that catches the read's `OSError` and
        re-raises it AS the dedicated exception satisfies a type check while having read the member.
      - **MEMBER** means the probe path is in aggregate membership — nothing else.
        So rows 9 and 11 prove the absent member is ADMITTED; that its contribution is the distinct
        `missing` marker is row 19's to prove (codex, r9).
      - **Row 16 injects its error by patching `os.lstat` for one named component, never with
        `chmod 000`.** A root runner bypasses permission bits, so a `chmod` fixture would stop exercising
        the branch under root while still passing. **The injected error must carry the filename,
        exactly as a real one does** — `OSError(errno.EIO, os.strerror(errno.EIO), path)`. An injection
        without it makes a lax observation look strict: the first draft of this harness raised a bare
        `OSError(EIO, "injected")`, and that hid the row-16 case of codex's r11 finding.
      - **Row 21 runs in a subprocess under a timeout, and a timeout is a FAILURE.** An implementation
        that falls through to `read_bytes()` on a FIFO blocks forever; run in-process, that hangs the
        suite instead of reddening it — a test that can hang is worse than the bug it looks for.
      - **Rows 23 and 24 compare the SAME `rel` where the defect needs it.** Row 24 holds the reference
        fixed and changes the filesystem: comparing two DIFFERENT references would let the `rel` label
        alone separate them and MASK the in-tree collision — the first draft of this row did exactly that
        and caught nothing. Row 23 carries one forgery per tree format, because a delimiter-joined member
        encoding is forgeable over either.
      - **not a member, no record** (row 6) means the probe is absent from membership AND nothing was
        recorded out of scope. Recording the root as out of scope is a failure.
      - **OUT OF SCOPE, recorded** (row 7) means the probe is absent from membership AND the out-of-scope
        record is exactly this row's operand.

      | # | adjacent to | reference | required outcome |
      |---|---|---|---|
      | 1 | symlink refusal (leaf) | `${workspace}/policy/security.toml`, itself a link into `outside/` | REFUSE |
      | 2 | symlink refusal (ancestor) | `${workspace}/sym_dir/config.toml`, `sym_dir` a link to `outside/` | REFUSE |
      | 3 | `..` after a symlink | `${workspace}/plink/../security.toml`, `plink` a link to `outside/child/` | REFUSE |
      | 4 | `..` refusal | `${workspace}/real_dir/../security.toml`, no link anywhere | REFUSE |
      | 5 | `..` above the anchor | `${workspace}/../outside.toml` | REFUSE |
      | 6 | root exclusion | `${workspace}/.` | not a member, no record |
      | 7 | containment | `${workspace}_extra/x.toml`, a spelling-prefix sibling | OUT OF SCOPE, recorded |
      | 8 | symlink refusal | `${workspace}/policy/plain.toml`, a regular file at depth two | MEMBER |
      | 9 | absent component (`ENOENT`) | `${workspace}/no_such_dir/absent.toml` | MEMBER |
      | 10 | **root exclusion** | `${workspace}/ordinary.toml`, a DIRECT child | MEMBER, and the aggregate digest moves on CREATE, EDIT and DELETE |
      | 11 | absent component (`ENOTDIR`) | `${workspace}/plain_file/x.toml`, `plain_file` a regular file | MEMBER |
      | 12 | `..` refusal | `${workspace}/a..b.toml` — `..` inside a NAME, not a component | MEMBER |
      | 13 | root exclusion, dotfiles | `${workspace}/.hidden.toml` — the shipped `.gitleaks.toml` shape | MEMBER |
      | 14 | `.` dropping | `${workspace}/./policy/other.toml` | MEMBER, as `policy/other.toml` |
      | 15 | anchor-relative operand | `direct_config: policy/rel.toml` — no `${workspace}` token | MEMBER, and the digest moves on CREATE, EDIT and DELETE |
      | 16 | other `lstat` errors refuse | `${workspace}/locked/inner.toml`, `os.lstat` patched to raise `EIO` on that component | REFUSE |
      | 17 | directory dispatch | `${workspace}/policy_dir`, a DERIVED-only DIRECTORY | MEMBER, and the digest moves on a descendant's CREATE, EDIT and DELETE |
      | 18 | symlink refusal, DANGLING | `${workspace}/dangle/x.toml`, `dangle` a link to a path that does not exist | REFUSE |
      | 19 | missing is not empty | `${workspace}/maybe_dir`, absent, then an EMPTY directory | the aggregate digest differs between the two |
      | 20 | directory contribution carries `rel` | `${workspace}/dirA` vs `${workspace}/dirB`, identical contents | the aggregate digest differs between the two |
      | 21 | member-level kind refusal | `${workspace}/pipe`, a FIFO | REFUSE — run in a SUBPROCESS under a timeout |
      | 22 | member-level kind refusal | `${workspace}/sock`, a Unix-domain socket | REFUSE |
      | 23 | records unforgeable ACROSS kinds | two pairs: directory `coll_a` vs FILE `coll_a:tree` holding a line-format tree input, and directory `coll_b` vs FILE `coll_b:tree` holding a JSON-record tree input | within each pair, the aggregate digests differ |
      | 24 | records unforgeable WITHIN a tree | ONE reference `${workspace}/forge`, in two states: files `a`, `b`; then one file named `a:<sha256 of a>\nb` with `b`'s bytes | the aggregate digest differs between the two states |

      **Row 10 is codex's r8 blocker.** Rows 8 and 9 sit at depth two, so an implementation that excluded
      the root AND every direct child (`if len(rel.parts) < 2: continue`) passed all nine revision-8 rows.
      That is not hypothetical: the shipped `GITLEAKS_CONFIG=${workspace}/.gitleaks.toml` IS a direct-child
      DERIVED reference, and its loss would be masked by DECLARED. **Row 8 must stay DERIVED-only**
      (codex, r7): a DECLARED probe is supplied by DECLARED whether or not derivation found it.
      **MUTANTS — EXECUTED, not reasoned** (2026-10-02, macOS, anchor beneath a `/var -> /private/var`
      alias, through `DECLARED | DERIVED`, each row observed exactly as written above). The correct
      procedure passes the baseline and all twenty-four rows, and each of the twenty-four mutants below fails at
      least one. Each mutant must fail EXACTLY the rows named.
      **Every set below comes from ONE harness running every mutant against every row** (codex, r10):
      revision 10 measured rows 15-20 against only its six new mutants, never the twelve older ones, and
      SEVEN of the previously stated sets were wrong once all rows existed.

      | mutant | fails on |
      |---|---|
      | containment by `Path.resolve()`, anchor and operand resolved ALIKE | 1-5, 16, 18 |
      | containment by `Path.resolve()`, operand only | 1-6, 8-24 — the WRONG reason; see below |
      | `..` collapsed by `os.path.normpath` before adjudication | 3, 4, 5 |
      | LEAF-only `Path.is_symlink()` | 2, 16, 18 |
      | `str.startswith` containment | 7, 15 |
      | unconditional `os.lstat` on the row's own walk | 9, 10, 11, 15, 16, 19 |
      | unconditional `os.lstat` on EVERY member, DECLARED included | the BASELINE (the absent candidate) |
      | discard direct children, `len(rel.parts) < 2` | 10, 12, 13, 17, 19-24 |
      | `ENOENT` handled, `ENOTDIR` refused | 11 |
      | `..` tested as a SUBSTRING | 12 |
      | skip any component starting with `.` | 13 |
      | refuse a `.` component as if it were `..` | 6, 14, 15 |
      | drop operands lacking `${workspace}` | 15 |
      | treat ANY `lstat` error as absent (`except OSError: break`) | 16 |
      | omit DERIVED directories | 17, 20, 24 |
      | `exists()` before walking — it follows links, so a dangling one reads as missing | 18 |
      | a missing member contributes the empty-tree digest | 19 |
      | directory contribution without its `rel` | 20 |
      | fall through to `read_bytes()` for an unsupported kind | 21 (by timeout), 22 |
      | read first, then re-raise the read's `OSError` AS the dedicated refusal | 21 (by timeout), 22 (by the read spy) |
      | let a non-`ENOENT`/`ENOTDIR` `lstat` error propagate instead of refusing | 16 |
      | revision 10's encoding: `f"{rel}:..."` members over the shipped `f"{relative}:{digest}"` tree | 23, 24 |
      | `f"{rel}:..."` members over JSON-record trees | 23 |
      | JSON members over the shipped `f"{relative}:{digest}"` tree lines | 24 |

      **The `Path.resolve()` mutant must resolve both sides alike** (codex, r6). Resolving the operand alone
      discards every reference on macOS, ordinary ones included, so it fails for the WRONG reason; rows
      8-14 are what tell the two apart. Row 4 is refused although harmless: refusing every `..` is what
      removes the ambiguity, and the shipped tree contains none. The unconditional-`lstat` mutant has TWO
      scopes because codex (r8) showed the scope decides the failure set: applied to every member, it
      fails at the baseline before any row runs.
      **What this table claims to be complete AGAINST** (revision 10). Rounds 7, 8 and 9 each found more
      rows because each was asked whether ANY realistic implementation error survived — a question with
      no fixed point, since a reviewer can always construct another bug. The completeness claim is
      therefore scoped to a FINITE list: codex's r9 inventory of every rule in §B3(1)(i)-(v) and in §B4's
      member layer that excludes, refuses, drops or records an input. Every rule on that list now has a
      control at its adjacent boundary:

      | rule (§B3(1) / §B4) | rows / cell |
      |---|---|
      | exclude the workspace root | 6; adjacent positives 10, 13 |
      | anchor taken as given, never examined | the `/var`-alias execution context; baseline |
      | join a relative operand to the anchor | 15 |
      | refuse a `..` component | 3, 4, 5; adjacent positive 12 |
      | drop a `.` component | 14; root-dot 6 |
      | exclude and RECORD a lexical outsider | 7; adjacent positives 8, 10 |
      | refuse a symlink at any component, dangling included | 1, 2, 18; adjacent positive 8 |
      | end the walk on `ENOENT`/`ENOTDIR` | 9, 11 |
      | refuse every other `lstat` error | 16 |
      | dispatch the survivor by kind | 8, 10 (file); 17 (directory) |
      | refuse symlinks and other kinds inside a tree | cell 11c's nested controls |
      | refuse unsupported kinds at the MEMBER itself (FIFO, socket) | 21, 22 |
      | records unforgeable across kinds and within a tree | 23, 24 |
      | missing is distinct from an empty tree | 19 |
      | every contribution carries `rel` | 20 |
      | required members exist, are tracked, non-empty | cells 9, 11c |
      | optional absence admitted; planting observed | background candidate; cell 11 |
      | classes disjoint and covering over production | cell 11c, both mutants |
      | unclassified synthetic members admissible | cell 8(e) |
      | promotion and demotion are paired edits | cell 11c |

      Bugs outside this inventory are caught where every other implementation bug is caught — by
      §6 step 2a's mutation pass over the REAL implementation, not by growing this table.
9. **The declared list's CONTENT is pinned.** Existence + tracked + non-empty are properties of
   whatever the tuple names, so swapping `.github/zizmor.yml` for any other tracked path satisfies
   them and the only thing that moves is a digest the swapping commit re-pins. Assert the declared
   set equals a literal set. A renamed or untracked declared path reds.
10. **Deleting a frozen config moves the digest.** Without this, absence and emptiness are the same
    value (§B4).
11b. **The RAW plugin provenance is pinned** (gemini, r2 BLOCKER: §B3(2) mandates
    `EXPECTED_PLUGIN_PROVENANCE` and §4 asserted it nowhere, so an implementer building cells 7-11
    from this section would never create it and an upstream `ref` change would go undetected).
    Assert the RAW, un-normalised `plugins.sources[].uri` + `ref` (and `cli.version` where native
    discovery supplies candidates) equals `EXPECTED_PLUGIN_PROVENANCE`. Read it from the RAW
    document — **not** through `_normalised_trunk_config`, which erases exactly the canonical `ref`
    this cell exists to catch. Mutants: bump `ref` to another canonical version (must red — this is
    the case the lint digest deliberately tolerates); repoint `uri`; bump `cli.version`. The
    diagnostic must say **re-enumerate the declared candidate set**, not merely "re-pin", because
    "re-pin the digest" is the instruction that produced this defect class twice already.

11c. **§B4's refusal and class rules have NAMED OWNERS here** (codex, r3: they were specified in §B4
    and owned by no cell — and §4 is what an implementer builds from, which is precisely the
    prose-versus-cell gap that produced revision 3). Owned by this cell: symlink refusal at BOTH
    `_digest_of_member` AND `_digest_of_tree`, and at EVERY component beneath the workspace anchor
    (§B3(1)(iv)) — with a control that plants a symlinked ANCESTOR of a DECLARED member in a mirror and
    asserts refusal, because cell 8(f) exercises DERIVED references only and (iv) claims every source;
    the nested target-only mutation control; recursive kind classification with nested FIFO and socket
    controls — the nested FIFO run, like row 21, in a subprocess under a timeout that counts as failure;
    controls; promotion and demotion each requiring the paired constant edit plus the re-pin; and
    cell 9's guard scoped to existing members.
    **The class assertion is TWO-SIDED, and it is the control** (codex, r6). With the location rule
    withdrawn (§B4), this assertion carries the whole weight, so both halves are stated: over the
    PRODUCTION member enumeration, assert DISJOINT and COVERING. MUTANTS: an enumerated production
    member placed in NEITHER frozenset must red COVERING; a path placed in BOTH must red DISJOINT. A
    suite that reds only one of the two has verified half the rule.
    **No location check** (codex, r6 P2 — supersedes revisions 5 and 6). Revision 5's "a class
    assertion relocated into the digest helper must red cell 8(e)" was false, and revision 6's
    replacement — a `co_names`/`co_consts` walk of the helper's call graph — was defeated by inlined
    literal copies of the frozensets: the fourth placement in two rounds that a name-based walk cannot
    see. §B4 shows the rule protects nothing this plan claims, so it is withdrawn rather than patched a
    fifth time. Admissibility, the property it was standing in for, is cell 8(e)'s.

11. **A config planted UNTRACKED at a CANDIDATE path moves the digest** — for the directory member
    (the existing cell 4b test) and, crucially, at candidate paths that hold nothing today
    (`.gitleaksignore`, `.gitleaks.config`, `zizmor.yml`, `.github/zizmor.yaml`). "Planted at a
    frozen path" is vacuous for the two occupied file members; the meaningful analogue for them is
    that UNTRACKING must NOT move the digest — the filesystem is the oracle — and cell 9's tracking
    guard is what reds.

## §5 — What this does NOT do

- Does **not** format the repository, nor reduce the 191-file backlog.
- Does **not** make cell 3's named property true in general — only for the **required gate**, which
  is the surface M4 promotes. COREDEV-2780's cell 3 record must say this rather than read as
  "fixed".
- **Stops the required gate catching a NEWLY INTRODUCED formatting defect**, not only pre-existing
  debt. Cell 3(b)'s second conjunct is "passes for its pre-existing findings WHILE STILL FAILING
  FOR NEWLY INTRODUCED ONES"; for the formatter family that conjunct becomes false. The rollout
  record's `resolvesAtMeans` offers exactly two closure routes — remedy the over-reach, OR narrow
  cell 3's criterion to lint findings AND accept the operational consequence IN WRITING. Part A is
  a hybrid: it takes route 1 for the first conjunct and performs route 2's narrowing on the second.
  This bullet is that acceptance; §6 step 4 must say so rather than record a clean route-1 closure.

- Does **not** address `.trunk/configs/**` *tolerance* beyond freezing it (already done), nor the
  `backed_by` free-text residue found on COREDEV-2811.
- Does **not** close COREDEV-2826 (the `defaults: run: shell:` suppression) — different mechanism.
- **Reduces** formatting enforcement for an author who bypasses their local hook (A4).

## §6 — Rollout

1. This plan through the mandatory dual-review gate (`/unleashed-mail:gemini-review` +
   `/unleashed-mail:codex-review`, then `/unleashed-mail:review-synthesis`) — **in this worktree**.
2. Implement Part A in this order: workflow → the two-literal split → §A6's harness fixture (validated
   with `--fix` BEFORE anything is pinned to it) → **the re-pins, counted rather than asserted** —
   `ARGUMENTS_LITERAL` in two test modules, the contract's `action_inputs_digest`, and the TWO
   `_JOB_DIGESTS` entries (`trunk-check.yml:trunk-check` AND `trunk-parity-harness.yml:parity`) →
   re-record the parity artifacts. Then Part B, then §4's cells. The earlier wording said "the four
   re-pins" and omitted the harness job entirely (codex, r3 P2); **derive the set from what the
   change touches rather than trusting a count in this sentence** — a stated count is a derived value
   and this document has had three go stale already. Run CI's **full** local gate after
   each commit, not the first six commands — including
   `python3 scripts/review/generate-callers-exemptions.py && git diff --exit-code -- scripts/review/callers-scan-exemptions.tsv`,
   LAST, after every other edit. Note that committing THIS plan document already reds
   `test_callers_scan`, so the first red is expected and is not Part A's.
2a. **Run cell 8(f)'s mutant battery against the REAL implementation**, not the model it was
   measured on (revision 10). The row sets in that table were executed against an in-memory model of
   the aggregate; the implementation can disagree with the model, and only running each mutant
   against the shipped `_config_tree_digest` / `_digest_of_member` shows it. Each mutant must fail
   EXACTLY its named rows. A mutant that fails NO row is a missing row — add the row, then rerun. A
   mutant that fails MORE rows than named means the model and the implementation diverged — find out
   why before merging; do not edit the table to match. **This verifies the TESTED mutants against the
   real code; it does not claim coverage of bugs nobody has written down** (codex, r10).
   **The battery SHIPS as an executed test**, each mutation operator applied by patching the real
   function, so the exact sets are reproduced by the suite itself rather than by a script outside the
   repo (codex, r11: "preserve the exact harness and mutation operators"). COREDEV-2617's mutant table
   became an executed suite the same way. The measurement model is NOT committed alongside the plan: a
   planning script would duplicate the table it measured, and duplicated values go stale. Its value is
   that the model the table was measured on cannot quietly disagree with what ships.
3. Observe the cells that need a real run on a probe PR, never merged; record under
   `docs/planning/evidence/`. Three constraints the earlier wording left implicit:
   - **Name the probe file and its recorded pre-existing formatter finding** for cell 1. It cannot
     be `scripts/tests/test_trunk_check_workflow.py` — the module both parts of this plan edit is
     black-clean at HEAD, so a green there would mean "already formatted". Use a file with a
     recorded arm-A transcript (e.g. `scripts/validate-hooks.py`, black + isort), committed under
     `docs/planning/evidence/` BEFORE the probe PR.
   - **Do not plant a credential.** `plugin-ci.yml`'s `secret-scan` runs on `pull_request` to
     main/alpha and scans FULL history with `gitleaks git`, so a secret-bearing probe PR reds a
     required context by design and the secret is permanently in a remote whose ruleset rejects
     branch deletion. Use a non-secret security fixture (bandit `B602`, or a zizmor
     template-injection workflow) and bind to the diagnostic ID, never to the summary's wording —
     gitleaks findings are printed as "lint issues", and textbook example keys such as
     `AKIAIOSFODNN7EXAMPLE` are not detected at all, so a green from one means "checked nothing".
   - **Bind each record to the run that produced it.** Evidence under `docs/planning/evidence/` is
     inert unless a test names it: the only glob consumer is `EVIDENCE_DIR.glob("parity-*.json")`.
     Each new record must carry the `action_inputs_digest` of its run and be refused when that is
     not what the shipped workflow now passes — copy the parity judge's `inputs:` clause. Otherwise
     an observation made with the six-name literal certifies a gate a later review round changed
     before merge.
   - For **cell 6**, state the oracle: the canary's JOB conclusion via `gh api .../check-runs`, not
     the PR checks UI — `continue-on-error: true` leaves the workflow RUN green.
   - For **cell 5**, the staged fixture's ONLY finding must be a formatter finding, and the same
     staged file under the required job's literal must exit 0. Without that second half the cell is
     satisfied by a run whose exit 1 was overdetermined by lint findings.
4. Update COREDEV-2780's `stillOpenForM3` cell-3 entry. Three things, not one:
   a. **Re-derive its `discriminator`.** It is currently a bare
      `trunk check --no-fix --ci --upstream=$(git rev-parse origin/main)` with **no `--filter`** —
      not the required job's invocation — so Part A cannot flip it by construction, and anyone
      re-triaging M4 readiness from this artifact still reads the item as OPEN. Replace it with a
      check over the surface that actually changed: read `arguments:` out of
      `.github/workflows/trunk-check.yml` and assert the five formatter names are excluded, or run
      the same `trunk check` WITH the shipped literal spliced in from the workflow.
      **Prefer the behavioural form** (codex, r1). Checking that five names appear in `arguments:`
      proves the MECHANISM is present, not that the named edit now passes — the property the item
      actually claims. Retain the runtime alternative (splice the shipped literal, run it against the
      recorded probe file, assert green) or consume cell 1's bound observation directly. A presence
      check is acceptable only as a companion to one of those, never as the whole discriminator.
   b. Say which of the record's two closure routes is being taken. The honest answer is a hybrid
      (see §5), and the record requires the narrowing half to be accepted in writing.
   c. Re-word `whatIsNOTObserved`, which after Part A describes formatter behaviour that no longer
      occurs on that surface.
   d. **Update or explicitly supersede COREDEV-2780's ORIGINAL cell 3 text**, not only the evidence
      record (codex, r1). §5 accepts losing newly-introduced formatting detection, and the rollout
      contract permits a written narrowing — but a narrowing recorded only in the evidence artifact
      leaves the governing cell still claiming the wider property. **No hedge about avoiding the gated
      bytes survives here** (codex, r5): §A5 already REQUIRES rewriting §6.4 and re-gating that plan
      under either authority route, so the re-gate is budgeted work, not a cost to route around.
      Supersede the cell-3 text in that same rewrite.
      **CORRECTION — the location revision 3 named DOES NOT EXIST** (codex, r3 P2). Revision 3 said
      to add a `superseded_by: COREDEV-2850` key to "cell 3's entry" in
      `COREDEV-2780-contract.yaml`. **That registry has no cell entries at all** — verified by parse,
      its top-level keys are `schemaVersion, ticket, renders, action_pin, action_inputs_digest,
      entries, families, obligations`, and its `C3.*` obligations are about job structure
      (`job-mapping-allowlist`, `nothing-skips-or-masks`, `no-defaults-run`, …), not cell 3's
      over-reach property. This instruction was taken from a review recommendation and written in
      without checking the location existed; the accompanying "confirm the loader tolerates an unknown
      key" check could not have caught it, because tolerating an unknown key says nothing about
      whether the ENTRY is there.
      **So there are exactly two honest routes for cell 3's SUPERSESSION, and a named key is neither
      of them.** Neither route touches the §6.4 rewrite and re-gate, which §A5 requires regardless
      (codex, r6):
      (i) put the supersession in the rollout evidence artifact — where cell 3's residual already
      lives as `stillOpenForM3[…].resolvesAt: COREDEV-2850` — and give it a READER, modelled on the
      existing `primaryDiagnostic` judge, so the supersession is asserted rather than asserted-about;
      or (ii) change the governing text in the gated plan and **re-gate that plan**, accepting the
      cost rather than pretending its recorded verdict still covers the new bytes.
      **Route (ii) is the one this plan takes.** That plan is being rewritten and re-gated for §6.4
      anyway, so the cell-3 supersession rides the same re-gate at no added cost (step 4(d)).
      Adding an inert key to a registry that has nowhere to put it would be the `backed_by` residue
      of COREDEV-2811 repeated exactly — an unvalidated field nothing reads.
5. Version bump (four sync points + CHANGELOG).
6. **LAND ATOMICALLY** (codex, r1). Step 2 orders IMPLEMENTATION A→B; it did not order MERGES.
   Part A, Part B, §4's cells and the accepted evidence land together, in one PR. **If they are ever
   split, Part B goes FIRST** — landing A first removes formatter and TOML-lint enforcement from the
   required gate while the unfrozen security-config hole is still open, which is the one ordering
   that makes the gate weaker in both directions simultaneously. The maintainer asked for this work
   bundled; this step is what makes "bundled" mean something at merge time rather than only in the
   plan document.
7. Only then is M4 unblocked, and M4 still needs its own maintainer decisions.
