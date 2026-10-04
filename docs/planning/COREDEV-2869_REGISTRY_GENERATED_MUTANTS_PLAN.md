# COREDEV-2869 part 1 — Generate cell 11's mutants from the registry

**Status:** Planning, revision 1. Not yet reviewed.
**Ticket:** COREDEV-2869 (parent Epic COREDEV-2485). Parts 2 and 3 shipped in v2.8.27 (PR #104):
actionlint now runs over every mutant in `validate`, and cell 15's sentinel test exists.
**Branch / worktree:** `feat/COREDEV-2869-registry-generated-mutants`, `.claude/worktrees/2869-generated-mutants`,
cut from `origin/main` at `dd84d82`.
**Created:** 2026-10-03

## Review log

*(empty)*

## 0. The defect, in one paragraph

`docs/planning/COREDEV-2780-contract.yaml` (the registry) says, in its own header, that "cell 11
GENERATES one mutant per mutation CASE by iterating `cases`". It does not. In
`scripts/tests/test_trunk_check_workflow.py`, `_yaml_mutants()` and `_canary_mutants()` together hold
130 hand-written recipes, keyed by registry case id. A further 8 hand-written tuples live in
`RawYamlSynonymsAreNotThePinnedBooleans.CASES` and `RawWorkflowTextIsUntaggedAndCanonical.CASES`. None
of these recipes reads the registry's `op`, `target` or `payload`. Each recipe also carries its own
expected diagnostic, so the registry's `diagnostic` field is never executed either. The two have
drifted, and nothing can see it:

* 11 recipes assert a different diagnostic from the registry's, over 21 (case, entry) executions. The
  2780 plan already reports this as "diagnostic debt", and it is re-derived in §1;
* 26 recipes build a different mutant from the one the registry declares (§1, F3);
* 19 registry cases declare an operator the recipe could not have used as written (§1, F4).

The 2780 plan's status block lists this as outstanding (`COREDEV-2780_REPO_GATING_HYGIENE_PLAN.md`,
"Not yet implemented", first bullet). The same bullet also names the `(side, form)` resolver family:
24 registry-expanded executions that do not run. One hand-written test raises on the four refusal
payloads on both sides, and no test runs an equality form through the comparator or checks either
family diagnostic.

This plan makes the registry the only source of every YAML-level mutant, its diagnostic, and the
resolver family's executions. Once it lands, a recipe cannot drift from its case, because no recipe
exists apart from the case.

## 1. Verified facts (measured 2026-10-03 at `dd84d82`)

Every count below was produced by an executed draft of the generator this plan specifies. The draft
was run against the shipped workflows and the hand-written recipes it replaces (`measure.py` and
`draft_generator.py`, kept outside the repository under `~/.claude/handoffs/coredev-2869/` with their
output). §7's cells make each of these counts an executed assertion, not a restated number.

* **F1 — the case census.** 149 cases. 130 are built by the two recipe methods. 8 are raw-text cases
  (`edit_bytes` on a workflow path). 8 are fixture cases (7 `materialise` plus C6a's `edit_bytes` on
  `scripts/ci/resolve-trunk-range.sh`). 3 are in `CELL16_INJECTED_CASES`. The registry has no `cases`
  outside `obligations`.
* **F2 — the generator works on today's cases.** A grammar-strict generator (§2) builds every one of the
  130 recipe cases on every entry its obligation declares: **220 (case, entry) mutants, 0 construction
  errors**. That needs the registry edits in §3. At milestone M3, the milestone of the shipped positive
  control, **220/220 produce the registry's diagnostic**. That needs the diagnostic reconciliation in
  §2.9. Under `actionlint -shellcheck= -pyflakes=`, the generated set reports **12 findings, all
  declared** (`if-cond` on the six `if: false` cases × 2 entries), and **0 stale allowances**.
* **F3 — what generation changes.** 169 of the 220 generated mutants are byte-identical, after
  `yaml.safe_dump(sort_keys=True)`, to the recipe they replace. The other 51 executions (26 cases)
  differ. Each difference is listed in §2.10 and resolved by the rule stated there.
* **F4 — operators that cannot be executed as written.** 16 cases say `set` on a key the shipped
  workflow does not have: the five `step-if-*` cases, the four `step-continue-on-error-<step>`
  cases, the six `changed-shell`/`changed-working-directory` cases, and `sibling-key`. Three cases say
  `edit_bytes` for a body edit that is a plain append (the `body-digest-*` cases). Eleven cases need
  a position or a destination that the generator can read:
  * nine carry it as prose in `payload`: `to branches-ignore` (×2), `to steps[trunk]`,
    `before guard-empty-diff`, `` immediately before `trunk`, AFTER the guards `` (×4) and `at the end`;
  * the `insert` case carries it as its target, `before trunk`;
  * `C3.exactly-one-trunk-invocation/two` carries none.

  Two `defaults.run` targets name a key below an absent parent.
* **F5 — targets come in four spellings.** `$.`-rooted paths, bare `steps[<name>]…`, `.with.<key>`
  relative to the Trunk step, and bare names (`guard-launcher-path`, `continue-on-error`). Of the
  `structural` and `raw` cases, 80 targets are not `$`-rooted. §3 rewrites 83 targets: those 80, the
  two `defaults` parents (F4), and the literal canary job id, which becomes `<job>`.
* **F6 — the resolver family already executes correctly; only its wording differs.** The draft ran all 24
  (`applies_to` × `sides` × `forms`) executions. Each one went through the real `_resolve_once` boundary,
  with only the live ruleset read substituted. Every one reached the right verdict class: 8 equality
  forms produced exactly one problem for their entry, and 16 refusal forms raised. Neither message
  matches the registry's `diagnostics`. The comparator says "…is not the ruleset's resolved target
  set…", and the resolver says "target set unresolvable: refusing to enumerate …".
* **F7 — the plan, not the registry, is normative on two payloads.** The 2780 plan's cell-11 rule
  names "the six `if: false` cases (`job-if` and the five `step-if-*`), whose constant `false` IS the
  hazard". It also names "the three `shell: sh` mutants (`C3.no-defaults-run/workflow` and `/job`,
  `C8.run-bodies-frozen/changed-shell`)". The registry's own `job-if` case contradicts itself: its
  comment and its `actionlint_allow: [if-cond]` describe a constant, while its payload is the expression
  `github.event_name != 'workflow_dispatch'`. Its `defaults` payloads are `shell: bash -e {0}` and
  `working-directory: /tmp`. The hand-written recipes follow the plan on both points.
* **F8 — the `local-divergence` cases never execute their declared op.**
  `C2.branches-equal-resolved-target-set/local-divergence` and its C16 sibling declare `set` of
  `branches` to `[main]` on the LOCAL side. They are counted as executed because they appear in
  `CELL16_INJECTED_CASES`. The test that "executes" the C16 one instead resolves a remote observation
  against another default branch, and the C2 one has no test at all. Neither asserts a diagnostic.
  Measured: both mutants build, and `contract_problems` reports NOTHING for either. Only the relation
  comparator catches them (`… ['main'] is not the ruleset's resolved target set ['alpha', 'main']`).

## 2. Design

### 2.1 Classification: total, and fail-closed

Every case is assigned to exactly one executor by its `(op, side, target)` shape. A case that matches
no row, or more than one, fails the suite and is named:

| class | selected by | executor | today |
|---|---|---|---|
| `structural` | `side: local`, op ∈ {`add`, `set`, `remove`, `append`, `move`, `duplicate`, `insert`}, `$`-rooted target | the generator (§2.2–§2.6) | the 130 recipes |
| `raw` | `side: local`, op `edit_bytes`, `$`-rooted target | `_respell` + the checker the obligation's kind names (§2.7) | 8 hand-written tuples |
| `fixture` | `side: local`, op `materialise`; or op `edit_bytes` with a repository-path target | the existing fixture tests | `FIXTURE_EXECUTED_CASES` |
| `injected` | `side: remote` | the existing cell-16 test | `C16.canary-not-required/present` |

The two `local-divergence` cases move from `injected` to `structural` (F8): their op is a local `set`.

Two of these classes stay owned by hand-maintained sets, `FIXTURE_EXECUTED_CASES` and
`CELL16_INJECTED_CASES`. For each, the test asserts in both directions that the set EQUALS what the
classifier derives, so a fixture case added to the registry cannot go unexecuted, and the set cannot
name a case the registry does not classify there. `RAW_YAML_CASES` is deleted, and the raw class is
derived.

**Why a table and not a per-case `executor:` field.** A declared field would be more explicit. It
would also add 149 lines whose only content is a value the four columns already decide. The table is
total and disjoint, and its else-branch fails. So an unclassifiable case fails closed exactly as an
undeclared one would, with nothing to keep in step.

### 2.2 Target grammar

```text
target   := "$" segment+
segment  := "." name | ".<job>" | ".steps[" step-name "]"
name     := [A-Za-z0-9_-]+
```

* `<job>` is the entry's job id, read from the registry's own `entries.<entry>.job`. It is never
  inferred from the workflow, and the workflow must contain that key. A literal job id stays legal,
  because `$.jobs.context-decoy` and the companion job (§2.5) need one.
* `.steps[x]` selects, from the CURRENT node's `steps` sequence, the one element whose `name` equals
  `x`. Zero matches or two matches is an error. Today's `_step()` returns the first match silently,
  and the duplicate-step cases exist because that hid a second `checkout` (2780 plan, revision 44).
* `on` is looked up as the key `on`. The bases are loaded with `_load_actions_yaml`, which is YAML 1.2,
  so `on` is a string key. The generator does not use `_on()`'s YAML 1.1 fallback to `True`.
* Any target that does not parse is an error naming the case.

### 2.3 Operators, and the closed case schema

A case's fields are a closed set: `id`, `op`, `side`, `target`, `payload`, `to`, `before`, `at`,
`validity`, `diagnostic`, `actionlint_allow`, `declares_support_job` and `fixture`. Any other key is
an error: a misspelt or invented key, such as `anchor:` where `before:` was meant, must not
silently become "no anchor".

| op | target | requires | effect |
|---|---|---|---|
| `add` | key | key ABSENT; `payload` | key := parse(payload) |
| `set` | key | key PRESENT; `payload`; new value ≠ old value, with the TYPE compared too (`15.0` ≠ `15`, `False` ≠ `0`) | key := parse(payload) |
| `remove` | key, or step | present | delete it |
| `append` | key | present, and a string; `payload` | value := value + payload, **verbatim** (not parsed) |
| `move` | key | present; `to` = an ABSENT key path | the value moves to `to` |
| `move` | step | present; exactly one of `before` / `at` | the step is removed and reinserted |
| `duplicate` | step | present; exactly one of `before` / `at` | a deep copy is inserted |
| `insert` | the `steps` key | `payload` (a step mapping); exactly one of `before` / `at` | the payload is inserted |

`before` is a step target (`$.jobs.<job>.steps[trunk]`), and `at` takes exactly one value, `end`.
`payload` is FORBIDDEN on `remove`, `move` and `duplicate`. `to` is legal only on a key `move`.

**A postcondition on every write.** After an `add`, `set` or `insert`, the generator reads the target
back and requires it to equal `parse(payload)`. After a `remove`, the target must be absent. After a
`move`, the source must be absent and the destination must hold the moved value. A generator that
ignored the payload or wrote it elsewhere would still produce a mutant that fails some diagnostic, so
the diagnostic assertion alone cannot detect it. The read-back can.

### 2.4 Payloads

`payload` must be a **string** in the loaded registry. A non-string fails, naming the case. That
includes PyYAML 1.1 reading an unquoted `yes` or `017`, which is how the registry is loaded. For
every op except `append`, the string is YAML TEXT, parsed by `_load_actions_yaml`, the same YAML 1.2
core loader the workflows use. So `"false"` is the boolean, `"'false'"` the string, `"1"` the integer,
`"':'"` the one-character string, and `"run: {shell: sh}"` a mapping. `append` concatenates the string
verbatim, because what it carries is source text: `' --fix'` keeps its leading space, and a run-body
line is appended after the body's own trailing newline.

### 2.5 The one companion edit

`C3.job-mapping-allowlist/needs` is the only case that needs a second edit: `needs:` must name a job
that exists and FAILS. Its `declares_support_job` mapping is that companion, and the generator reads
it. It adds `$.jobs.<declares_support_job.id>`, holding the mapping minus `id` and `why`, BEFORE the
primary edit, and that key must be absent. The plan already names this field ("C3's `needs:` case
declares the failing support job"), so the generator reads the declaration that exists rather than
adding a new one. No other case declares more than one edit (F2: 220 mutants built, 0 errors).

### 2.6 Execution

For each `structural` case, and each entry in its obligation's `entries`:

1. base := a fresh `_load_actions_yaml` parse of that entry's workflow;
2. mutant := the generator applied to a deep copy of the base (§2.3, with the §2.5 companion first);
3. the mutant must differ from the base, compared by `yaml.safe_dump(sort_keys=True)` (unchanged rule);
4. problems := `contract_problems(mutant, milestone="M3", entry=entry)`. For a `remote_relation`
   obligation, the problems also include the relation comparator's result for that entry. That
   comparator is `_target_set_problems(resolved, entry, _branches(mutant, entry))`, where `resolved`
   comes from ONE `_resolve_once` call per test. `_branches` is the per-workflow half of today's
   `_shipped_branches`: `pull_request` for `required`, `push` for `canary`. `_shipped_branches` is
   rewritten to call it, so the shipped and mutated reads share one extractor. If the mutant has no
   `branches`, the relation is not computed, because `contract_problems` already reports the absence;
5. the registry's `diagnostic` must be in `problems`. That is exact list membership, unchanged, for
   every message `contract_problems` emits. The relation comparator's message carries the observed
   sets as detail, so for that one source the match is `message == D or message.startswith(D + ": ")`
   (§2.8).

**Milestone M3 for every case.** It is the shipped milestone and the positive control's. Today every
recipe runs at the default `M2` except `C3.no-job-continue-on-error/present`, which carries an `"M3"`
override. M2 widens the job allowlist with `M2_ADVISORY_EXEMPTION`, a state no shipped workflow is in.
Measured, all 220 diagnostics hold at M3 (F2). The obligation's `milestone_exemption` (`until: M3`)
expired when M3 shipped, so the generator does not read it. The field stays as history.

The existing per-entry, actionlint and coverage tests consume the generator's output in place of the
two recipe methods. Their assertions do not change, except where §4 says so.

### 2.7 Raw-text cases

The 8 `raw` cases are built from the registry. The generator derives the pinned path from the canonical
target: `(step, key)` for `$.jobs.<job>.steps[<step>].with.<key>`, and `(key,)` for
`$.jobs.<job>.<key>`. That path must be one of `PINNED_PATHS`' values, or the case fails by name.
Today each tuple carries only the target's last segment, and the registry's target is never read, so
a registry target naming the wrong step would pass unnoticed. The replacement is `payload`, verbatim.
The checker comes from the obligation's kind: `raw_text` → `raw_workflow_problems`, `yaml` →
`contract_problems`. The two classes keep their
other tests (the decoy, every-spelling and positive-control tests), and their `CASES` become the
derived lists. F1: today all 8 registry cases agree with their tuples field for field, so this
changes no executed mutant.

### 2.8 The resolver family: 24 executions

For each obligation in `families.target_set_resolution.applies_to`, its single entry, each `side` and
each `form`:

1. injected := the recorded raw target set (`c2AndCell16RemoteHalves.rawTargetSet` in the rollout
   evidence), with `injected[side]` replaced by `[form.payload]`. The default branch is `main`, a
   fixture value: the evidence does not record one, and each form's outcome is checked below;
2. `_resolve_target_set` (the LIVE read, and only that) is patched to return
   `_resolve_ref_name(injected, "main")`. `_resolve_once`, `_target_set_results` and
   `_target_set_problems` run unmodified;
3. an `equality` form must yield exactly one problem for its entry, matching
   `diagnostics.equality`. A `refusal` form must raise `ValueError`, whose message matches
   `diagnostics.refusal`. Matching is by the §2.6 rule.

The family's `validity` says the two diagnostics must be DISTINGUISHABLE. The test asserts that
neither one is a prefix of the other.

**The two messages change in the checker, not the registry.** The registry's family diagnostics
cannot equal a message that carries sets, so the checker's messages become `D: detail`:

* comparator → `target set mismatch: workflow branches != resolved ruleset target set: <entry> branches <sorted>, resolved <sorted>`
* resolver → `target set unresolvable: refusing to compare an unenumerable pattern: <repr(entry)>`

The cell-15 sentinel test asserts `problems[0].startswith(f"{entry}: ")`. It changes to assert that
the message names `<entry>`. The property it guards, that the entry's diagnostic carries the
sentinel, is unchanged. The generated 16 refusal executions make
`Cell15_TargetSetResolution.test_patterns_and_all_fail_closed_on_both_sides` redundant. That test is a
hand-written list of the same four payloads (`~ALL`, `a*`, `mai?`, `mai[a-z]`) × both sides, and it
is deleted. The class's other three tests stay (alias and prefix expansion, exclude veto, and
same-cardinality retarget), because they pin specific resolver arithmetic that no family form states.

### 2.9 Diagnostic reconciliation

**Rule.** The checker's message is kept when it belongs to the case's OWN obligation. The registry
then records that message verbatim. If a checker emitted only another clause's message for some case,
that would need a checker change, because "a case that fails through a sibling clause's message
proves reachability, not discrimination" (the registry's header). No case is in that position. In all
11, the checker emits a message of the case's own obligation:

| case | registry today | becomes (the checker's own message) |
|---|---|---|
| C0 root `write-all` / C3 job `write-all` | ``found `write-all` `` | `found 'write-all'` |
| C0 / C3 `widened-scope` | `found an extra scope` | `found {'contents': 'read', 'checks': 'write'}` |
| C0 / C3 `absent` | `key is absent` | `` expected `contents: read`, found None `` |
| `C5.no-env-any-scope/step` | `` step-level `env:` is prohibited `` | `` step `trunk`: `env:` is prohibited `` |
| `C9.action-pinned-by-sha/different-sha` | `action pin: unexpected SHA` | `action pin: not pinned to the expected SHA` |
| `C8.run-bodies-frozen/changed-shell` | `` step `guard-empty-diff`: complete step mapping changed `` | `` step `guard-empty-diff`: `shell:` is prohibited `` (as its two per-step siblings already say) |
| `C8.run-bodies-frozen/changed-working-directory` | likewise | `` …: `working-directory:` is prohibited `` |
| `C16.canary-continue-on-error-job-scope/step-scope` | `` canary: `continue-on-error` must be at JOB scope, not step scope `` | `` canary: job-scoped `continue-on-error` is absent `` — the same obligation's message, emitted because the move empties job scope |

The C2 and C16 `local-divergence` diagnostics are joined to the comparator's one message,
`target set mismatch: workflow branches != resolved ruleset target set`. C16's spelling, `canary
branches`, names a second message that no comparator emits, and there is one comparator.

### 2.10 Payload conflicts: the plan first, then the registry

**Rule.** Where the 2780 plan's normative text specifies a mutant, the registry is corrected to it.
Where the plan is silent, the registry's payload stands, and the generated mutant is what the case
declared. Three cases fall under the first half (F7): `job-if` and the two `defaults` cases. The
other 25 fall under the second.

| case(s) | executions | recipe built | generated (resolution) |
|---|---|---|---|
| `C3.nothing-skips-or-masks/job-if` | 2 | `if: 'false'` | `if: false`. **Plan wins** (F7). The registry's payload and `validity` are corrected, and its comment and allowance are already right |
| `C3.no-defaults-run/workflow`, `/job` | 4 | `defaults: {run: {shell: sh}}` | the same. **Plan wins** (F7). The registry payloads `shell: bash -e {0}` / `working-directory: /tmp` are corrected, and the targets move to `$.defaults` / `$.jobs.<job>.defaults` (F4) |
| the five `step-if-*` | 10 | the string `'false'` | the boolean `false`, the registry's payload and the plan's `if: false` |
| `C0.no-concurrency/workflow`, `/job` | 4 | `group: x` | `group: trunk-check` |
| `C5.no-env-any-scope/step` | 2 | `TRUNK_PATH: /bin/true` | `BASH_ENV: /tmp/x` |
| `C8.step-sequence-allowlist/extra-step` | 2 | `{name: extra, run: echo hi}` | `{run: echo hi}` |
| `C1.single-event/add-push` | 1 | `branches: [main]` | `branches: [main, alpha]` |
| the 15 run-body appends (`creates-c6-path`, `github-env-*`, `github-path`, `body-digest-*`, per step) | 30 | body + `"\n"` + line | body + line. The body already ends in a newline, so the recipe's extra `"\n"` was a blank line. `github-path` on `guard-empty-diff` also takes the registry's `/tmp/fake` |

That is 55 executions in total. The four `defaults` executions come out identical to their recipe
once the registry is corrected, which leaves F3's 51 executions (26 cases). `job-if` still differs
from its recipe, by type: the boolean `false` replaces the string `'false'`, as it does on the five
steps. The plan text that names a payload is cited in F7. For the other 25 cases, a reviewer can check
the claim "the plan is silent" by searching the plan for each payload.

### 2.11 What is deleted

`_yaml_mutants`, `_canary_mutants` (with the helpers nested in them), `RAW_YAML_CASES`, the two
hand-written `CASES` tuples, `test_patterns_and_all_fail_closed_on_both_sides` (§2.8), and
`test_every_generated_mutant_names_a_declared_registry_case`. That test is vacuous once every mutant
is built from a declared case. `test_every_canary_mutant_fails_with_its_own_diagnostic` is folded into
the per-entry test, which already runs the canary.

## 3. Registry edits (`docs/planning/COREDEV-2780-contract.yaml`)

These are derived field by field from the draft's canonicaliser (`edit-list.txt` in the handoff
directory). Comments and layout are preserved, and each edit is a line edit inside one case.

1. **83 targets** rewritten to the §2.2 form: the bare `steps[…]` and `.with.…` prefixes, the three
   bare names, the two `defaults` parents, and `$.jobs.trunk-check-push.continue-on-error` →
   `$.jobs.<job>.continue-on-error`. Fixture and remote targets are file paths or prose, which their
   own executors read, and they are not touched.
2. **19 ops:** 16 `set` → `add` (F4) and 3 `edit_bytes` → `append` (`body-digest-*`).
3. **Positions and destinations:** 3 `to:`, 6 `before:` and 2 `at: end`. The prose payloads they
   replace are removed.
4. **Payloads:** the non-string ones are quoted (`False` → `"false"`, `True` → `"true"`, `1` → `"1"`);
   `':'` → `"':'"`; `body-digest-*` gain `":"`; and `job-if` / `defaults` follow §2.10. 29 in total,
   counting the 9 prose payloads item 3 removes.
5. **Diagnostics:** the 11 cases of §2.9, plus C16 `local-divergence`. The family's `diagnostics` are
   unchanged, because the checker moves to them (§2.8).
6. **`job-if`'s `validity`** stops saying "strictly worse than the hazard it was written to fix". That
   described the expression payload this plan removes.
7. **The header** gains §2.2–§2.4's grammar, compressed. It stops claiming generation that does not
   happen: the claim becomes true, and the header says where the generator lives.

## 4. Test-file edits (`scripts/tests/test_trunk_check_workflow.py`)

* **New module-level functions,** beside `_step`: `_parse_target`, `_classify(case)`,
  `_mutate(workflow, case, entry, registry)` (with the postconditions), `_relation_problems`, and
  `_family_executions(registry)`. They are pure functions over the registry, so the config-freeze
  battery and future cells can call them.
* **`Cell11_MutantsAreGeneratedFromTheRegistry`** iterates `_classify` and `_mutate` in place of the
  recipe lists. It gains:
  * the generator's negative controls (§7, V3);
  * the classification-equality checks (§2.1);
  * the family executions (§2.8).
* **`_target_set_problems` and `_resolve_ref_name`** take the §2.8 messages. The sentinel assertion is
  adjusted as §2.8 states.
* **The raw-text classes'** `CASES` become derived from the registry (§2.7).
* **`CELL16_INJECTED_CASES`** drops the two `local-divergence` ids, leaving
  `C16.canary-not-required/present`. `Cell16_…test_an_injected_divergent_target_set_is_detected` stays,
  because it is a valid remote-side retarget probe, but its docstring stops naming the
  `local-divergence` case id it never executed.
* **`_branches(workflow, entry)`** is extracted from `_shipped_branches` (§2.6).
* **`test_every_declared_case_is_executed_here_or_provably_needs_external_machinery`** keeps its
  contract: every declared case has an executor, and the count of deferred cases is 0. It now derives
  "executed" from the classifier, not from the recipe ids.

## 5. Plan text

* `COREDEV-2780_REPO_GATING_HYGIENE_PLAN.md`, status block:
  * The first "Not yet implemented" bullet is replaced by an "Implemented (COREDEV-2869 part 1)"
    paragraph. That paragraph carries the counts §7 executes, and these facts:
    * the generated, diagnostic-matched and actionlint-clean mutants;
    * the 24 family executions;
    * the `local-divergence` cases now executing their declared op.
  * The "diagnostic debt" sentence goes, because the debt is reconciled.
  * The "Scope of that claim" sentence says "The three remote-relation pairs are injected per single
    entry". It becomes: one remote-relation pair (`C16.canary-not-required/present`) is injected, and
    the two `local-divergence` pairs execute their declared local op through the comparator.
  * Nothing else in the block changes. The C6/C6a fixture-diagnostic gap and every other bullet stay
    open (§6).
* Cell 11's rule (`§7`, the paragraph quoted in F7) is unchanged. It already states the six
  `if: false` cases and the `shell: sh` mutants, and the generated set now matches it.

## 6. Out of scope

* C6/C6a fixture tests asserting the registry's own diagnostics: a separate bullet in the 2780 status
  block (codex, r50).
* Executing the survivor corpus's mutants independently.
* Cells 3, 5, 8, 13 and 16's open items.
* `C16.canary-not-required/present`, which stays in `injected`.
* A second `job-if` case that uses a non-constant expression. Such a case would discriminate a
  checker that evaluates `if:` from one that prohibits it, which is a real argument. But it adds an
  obligation case, and the plan's cell-11 text names the constant. It would get a ticket of its own if
  wanted.
* Moving the registry's own loading from PyYAML 1.1 to the 1.2 loader. §2.4's string rule makes that
  irrelevant to payloads, and the other keys the registry holds are unaffected.

## 7. Verification cells

Each cell states the PROPERTY, how it is checked, and the mutation that must turn it red. Each red was
observed on a scratch copy before the cell counts as passing. Every count is asserted by the test that
produces it.

| # | property | checked by | must go red when |
|---|---|---|---|
| V1 | every case is classified into exactly one executor; fixture and injected sets EQUAL the derived classes | a test over all 149 cases | a case gets `op: rename`; a case is added to `FIXTURE_EXECUTED_CASES` only; the remote case is deleted from `CELL16_INJECTED_CASES` |
| V2 | the closed schema | a test over every case | a case gains `anchor:`; a `structural` case loses `diagnostic` |
| V3 | the generator fails closed on each requirement in §2.3 | one synthetic case per requirement, each `assertRaises` with the case id in the message | each guard in §2.2–§2.4 is deleted, one at a time: unparseable target, step 0 matches, step 2 matches, add-present, set-absent, set-equal, remove-absent, append on a non-string, move source absent, move-to-present, non-string payload, both `before`+`at`, neither, payload on `remove`, unknown op. Separately, the set-equal TYPE comparison is dropped: `timeout-float` must then fail to build |
| V4 | the postcondition binds the payload | per `add`/`set`/`insert` execution | `_mutate` writes `parse(payload)` to the PARENT key; `_mutate` writes `None` |
| V5 | every structural (case, entry) builds, differs from its base, and yields its registry diagnostic at M3: 222 executions (220 + the two `local-divergence`) | the per-entry test, with its count asserted | one §3 diagnostic edit is reverted; `<job>` resolves to the other entry's job id; the M3 constant becomes M2 (the `no-job-continue-on-error` case must red) |
| V6 | actionlint accepts every generated mutant, apart from declared allowances, and no allowance is stale | the existing test, now over the generator's output | `job-if`'s payload reverts to the expression (a stale `if-cond` allowance); a `needs` case is built without its companion (`job-needs`) |
| V7 | the raw cases are derived, and the pinned path agrees with the target | the two raw classes | a raw target names the wrong step; a raw payload is edited (the executed mutant must change with it) |
| V8 | the family: 24 executions; verdict class and diagnostic per form; distinguishable | the family test, with its count asserted | the resolver treats `~ALL` as a literal; the comparator ignores `resolved`; both family diagnostics are made equal |
| V9 | no recipe survives | a source assertion that `_yaml_mutants`, `_canary_mutants`, `RAW_YAML_CASES`, any `CASES = (` tuple and `test_patterns_and_all_fail_closed_on_both_sides` are absent from the module | any of them is reintroduced |
| V10 | the positive controls still pass: both shipped workflows at M3, every permitted spelling | the existing tests, unchanged | (unchanged controls) |
| V11 | the local gate, as CI runs it | CLAUDE.md's full list, including `trunk check` on the touched files, and the plan-citation linter's self-test | — |

V5's "222" and V8's "24" are asserted by the tests, not restated. If the registry gains a case, those
tests change with it.

## 8. Rollout

1. Implement in this worktree, after the gate passes and its verdict is persisted here.
2. Bump to the next patch version at merge time, keeping the version files, README and CHANGELOG in
   sync. Expected: 2.8.30 if #106 and #107 land first.
3. Open a PR into `main`, and run the full local gate first. Merge only on the maintainer's word.
4. Jira COREDEV-2869: progress notes at the gate, at implementation and at the PR. Close part 1 when it
   merges.
