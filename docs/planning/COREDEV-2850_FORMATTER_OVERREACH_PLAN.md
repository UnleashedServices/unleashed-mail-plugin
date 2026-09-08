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
of COREDEV-2850's nine: `scripts/tests/test_trunk_check_workflow.py`. (Part A's file count is nine
changed plus one deliberately unchanged — see §A5; the earlier "five" was measured before the
canary split, the two frozen digests, the two parity artifacts, §6.4 and the harness fixture were
found.) Within it, 2850 edits
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

### Validated by measurement, three arms

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
| `scripts/tests/test_python39_floor.py` | re-pin `_JOB_DIGESTS[("trunk-check.yml","trunk-check")]` → `ba363bdaf13c60d1a19c8b5cee9926f73420a495193c764c57b5ec58ec1b9194`. `_WORKFLOW_LEVEL_DIGESTS["trunk-check.yml"]` does **not** move — do not "fix" the wrong constant |
| `docs/planning/COREDEV-2780-contract.yaml` | re-pin `action_inputs_digest` `cc125ae6…` → `2e74b4a7806b1b4c579e14bc59038e1707dbad23a171cdae0d6ea495308931fe`; split `C4.arguments-required-literal` into a `required` and a `canary` obligation (or widen `entries:` and give each its own `literal_source`) so cell 11 generates a mutant for the new canary branch; amend the obligation's `statement` and its `/absent` case, which today say absence means "`markdown-link-check` runs in the required job" |
| `docs/planning/COREDEV-2780_REPO_GATING_HYGIENE_PLAN.md` §6.4 | **the literal's bytes live HERE**, not in the contract yaml. §6.4 must declare BOTH literals and why they differ, and its sentences "That exact scalar is the whole permitted value of the job's `arguments:` input" and "cell 13 asserts the SAME literal in the pre-commit invocation" must be rewritten. Editing a gated `*_PLAN.md` changes the bytes `review-verdict.py` binds to COREDEV-2780's recorded verdict — the cheaper alternative is to move the bytes into the contract yaml as `required_literal` / `canary_literal` keys that a test READS (nothing reads `literal_source:` today) |
| `docs/planning/evidence/parity-pull_request.json`, `parity-push.json` | RE-RECORDED by a harness run. They carry the OLD canonical form + digest and the old literal in `invocations[1]`. Hand-editing them forges sensor output; **deleting** them is worse — the judge then SKIPS and the module reports `OK (skipped=1)`, silently regressing COREDEV-2780 M2c to "cells 1 and 5 unowned" |
| `scripts/review/callers-scan-exemptions.tsv` | regenerated LAST in every commit (`python3 scripts/review/generate-callers-exemptions.py`) |
| `scripts/tests/test_precommit_trunk_gate.py` | **unchanged** — asserts the HOOK's literal, which keeps formatters |

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

The whole-string match is retained; C4's mutant (`payload: " --fix"`) stays, so an appended argument
still fails.

**The literal now exists in two places with DIFFERENT values by design.** That is the hazard this
introduces. Cell 4's contract must state **both** literals and **why they differ**, so that making
them identical again is what fails the test — otherwise a future reader "fixes" the drift.

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
already contemplates a positional linter, `harness-fixtures/probe.sh:13:6 shellcheck/SC2086` — AND
(ii) **autofixable by that same invocation**. A diagnostic that survives the filter but cannot be
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

Cell 4b freezes `.trunk/configs/**`. But `.trunk/trunk.yaml` wires two `is_security` linters to
configs **outside** that tree:

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
   `environment[].value`, or a `${workspace}`-rooted token inside `commands[].run`, that resolves
   inside the workspace and is **not** the workspace root itself (a bare `${workspace}` would make
   the entire repository the frozen census).
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
| directory | `_digest_of_tree(path)` — unchanged, for `.trunk/configs/**` |
| symlink | **REFUSED** — see below |
| regular file | `f"{rel}:{sha256(path.read_bytes())}"` |
| missing | `f"{rel}:missing"` — a DISTINCT marker, never the empty-tree constant |

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
| **optional candidate** | a declared `direct_configs` path holding nothing today — e.g. `.gitleaksignore`, `zizmor.yaml`, `.checkov.yml` | MUST contribute a `missing` marker; CREATING it must move the digest; it is NOT required to exist |

Both classes are verified THROUGH the aggregate digest, not beside it. A member's class is fixed by
the shipped tree at pin time, and a candidate that becomes occupied is a reviewed re-pin — the cell's
diagnostic must say which class it found and which it expected, so a promotion is legible rather than
a mysterious digest move.

---

## §4 — Verification cells (both parts)

**Part A**

1. **The over-reach is gone.** A PR whose only change is a finding-neutral edit to a named
   unformatted tracked file goes GREEN on the required job. Bound to a file with a *recorded*
   pre-existing formatter finding, so green cannot mean "already formatted".
2. **A new LINT finding still reds it** — arm C, as a CI observation, bound to a named diagnostic
   with file/line/column.
2b. **ARM D — the accepted loss, observed in both directions.** A file that is formatter-CLEAN at
   base, into which the PR introduces a format-only defect, goes GREEN on the required job and RED
   on the hook. Its canary half is bound by cell 6's stimulus constraint — without a controlled push
   environment the canary side of arm D is deferred, not observed. Without arm D the trade is
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
   deferred rather than quietly closed on the API oracle. The same constraint governs arm D's
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
8. **The derivation cannot silently empty — and cannot be hard-coded.** See §B3(1): the stub-to-`[]`
   case is the floor; the discriminating cases are a synthetic second reference appearing and the
   `GITLEAKS_CONFIG` entry removed shrinking the result.
9. **The declared list's CONTENT is pinned.** Existence + tracked + non-empty are properties of
   whatever the tuple names, so swapping `.github/zizmor.yml` for any other tracked path satisfies
   them and the only thing that moves is a digest the swapping commit re-pins. Assert the declared
   set equals a literal set. A renamed or untracked declared path reds.
10. **Deleting a frozen config moves the digest.** Without this, absence and emptiness are the same
    value (§B4).
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
2. Implement Part A (workflow → the two-literal split → the four re-pins → §A6's harness fixture →
   re-record the parity artifacts), then Part B, then §4's cells. Run CI's **full** local gate after
   each commit, not the first six commands — including
   `python3 scripts/review/generate-callers-exemptions.py && git diff --exit-code -- scripts/review/callers-scan-exemptions.tsv`,
   LAST, after every other edit. Note that committing THIS plan document already reds
   `test_callers_scan`, so the first red is expected and is not Part A's.
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
      leaves the governing cell still claiming the wider property. The same digest-binding caution as
      §A5 applies: prefer superseding it from the contract yaml / evidence record over editing the
      gated `*_PLAN.md` bytes, and if the bytes must change, re-gate that plan rather than pretending
      its recorded verdict still covers them.
5. Version bump (four sync points + CHANGELOG).
6. **LAND ATOMICALLY** (codex, r1). Step 2 orders IMPLEMENTATION A→B; it did not order MERGES.
   Part A, Part B, §4's cells and the accepted evidence land together, in one PR. **If they are ever
   split, Part B goes FIRST** — landing A first removes formatter and TOML-lint enforcement from the
   required gate while the unfrozen security-config hole is still open, which is the one ordering
   that makes the gate weaker in both directions simultaneously. The maintainer asked for this work
   bundled; this step is what makes "bundled" mean something at merge time rather than only in the
   plan document.
7. Only then is M4 unblocked, and M4 still needs its own maintainer decisions.
