# COREDEV-2869 part 1 — Generate cell 11's mutants from the registry

**Status:** Implemented. The plan gate PASSED on revision 4: combined verdict APPROVE_WITH_NOTES,
reproduced on byte-identical bytes (`76185a4e8398`) in rounds 5 and 6. Every edit to this file after
round 6 is ungated by construction; the implementation note lists them.
**Ticket:** COREDEV-2869 (parent Epic COREDEV-2485). Parts 2 and 3 shipped in v2.8.27 (PR #104):
actionlint now runs over every mutant in `validate`, and cell 15's sentinel test exists.
**Branch / worktree:** `feat/COREDEV-2869-registry-generated-mutants`, `.claude/worktrees/2869-generated-mutants`,
cut from `origin/main` at `dd84d82`.
**Created:** 2026-10-03

## Review log

> **r1** `1b075f7` (revision 1): agy `APPROVE`, codex `REQUEST_CHANGES` (3 blocking). codex reproduced
> F1, F3, F4, F6, F7 and F8 independently, and F2's 220 constructions and 220 diagnostics.
> 1. §2.3's postconditions were impossible for two existing cases. An `insert` targets the `steps` list,
>    so reading the target back cannot equal its one-step payload. A step `move` keeps its name, so its
>    source can never become absent. My draft never implemented the postconditions, so it could not
>    catch this.
> 2. `append` and `duplicate` had no postcondition. An executor keeping the old `body + "\n" + line`, or
>    duplicating `checkout` BEFORE the guards, still produces the case's diagnostic. codex confirmed
>    the second against the checker. So the declared placement was a property nothing checked.
> 3. V7 could not prove that the raw cases depend on the registry's payload. `save-annotations: yes`
>    and `: on` produce the same diagnostic, so an executor that ignored a payload edit stays green.
>
> Notes, all applied:
> * F5 named four target spellings, and there is a fifth (`before trunk`).
> * §2.1's "cannot go unexecuted" claimed more than set equality shows.
> * `step-name` had no grammar production.
> * Nothing verified that the companion job FAILS.
> * The family patch must raise DURING `_resolve_once`, not while its return value is prepared.
> * V3 was incomplete.
> * V9 needs declaration-aware inspection, because a substring check matches its own literals.
>
> **Revision 2** replaces §2.3's single postcondition sentence with a per-operator table. Each row is a
> VALUE check plus a FRAME check: nothing outside the declared edit changed. The table includes step
> placement. Revision 2 also adds a span postcondition and a payload-substitution control for the raw
> cases (§2.7), and EXECUTES the companion job's body (§2.5). It specifies the family patch as a
> callable `side_effect` (§2.8), and completes V3, V4, V7 and V9.
>
> **r2** `3c41aee` (revision 2): agy `APPROVE`, codex `REQUEST_CHANGES` (1 blocking). codex judged
> every Round 1 blocker resolved and re-derived F1 through F8.
> 1. §2.10 kept the registry's `BASH_ENV: /tmp/x` for `C5.no-env-any-scope/step` and called the 2780
>    plan silent. It is not. Cell 11's minimum list requires "`env: {TRUNK_PATH: /bin/true}` at
>    **workflow** level, at job level, and at step level", and the recipe follows it. Both payloads
>    produce the same diagnostic, so V5 and V6 could never have shown the loss of the prescribed
>    launcher-bypass probe.
>
> The cause was method, not one oversight. I tested "the plan is silent" by searching the plan for
> each payload string. The minimum list states payloads per CLAUSE, and the search could not find
> those. **Revision 3** reads that list in full, as the normative enumeration it is (§2.10). C5 is the
> only additional conflict: every other payload it names matches the registry. It applies the
> plan-first rule to C5. Two non-blocking clarifications are applied as well: §2.7 validates the whole
> raw target before reducing it to `PINNED_PATHS`, and V3 gains the non-mapping `insert` payload and
> the non-sequence insertion target.
>
> **r3** `0e546fb` (revision 3): agy `APPROVE`, codex `APPROVE_WITH_NOTES`, the first double approval.
> codex re-derived every count, including F2's 12 actionlint findings with 0 stale. Its two notes were
> held back so that round 4 could reproduce on byte-identical bytes:
> 1. §2.5 executes the companion, but a future declaration could add a step-level
>    `continue-on-error: true`, keep the non-zero exit, and still let the support job succeed.
> 2. The evidence wording is broader than the evidence:
>    * the family patch replaces `_resolve_target_set`, which wraps the live read AND resolution, not
>      the live read alone;
>    * §1 said §7 asserts every count, but F3's recipe comparison has no standing form once the recipes
>      are deleted;
>    * F9's "all four raw payload shapes" are four representative shapes of seven distinct spellings.
>
> **r4** `0e546fb`, a byte-identical reproduction of r3: agy `APPROVE`, codex `REQUEST_CHANGES` (1
> blocking). **The double approval did not reproduce.**
> 1. Nothing runs the RAW mutants through actionlint. §2.6 feeds the generator's dictionaries to the
>    existing actionlint test, and §2.7 builds raw mutants separately, as text. codex reproduced a
>    survivor: a raw `lfs` payload of `"[]"` satisfies §2.7's span and frame checks and produces its
>    own diagnostic, and actionlint rejects it (`syntax-check`). Cell 11's constructibility rule
>    covers every mutant.
>
> Notes:
> * §2.4's YAML-parsing rule should say it applies to STRUCTURAL payloads only.
> * The frame checks need recursive, type-strict equality. Python's `==` would hide an unrelated
>   `False` → `0` or `15` → `15.0` edit.
>
> **Revision 4** lints every raw mutant as SOURCE TEXT. Measured: 304 raw mutants (8 cases × 2
> entries × 19 permitted source spellings) give 0 findings, and the `"[]"` control is caught. Revision
> 4 also:
> * applies all six notes from r3 and r4;
> * restricts the companion to its declared shape (§2.5);
> * makes the frame equality recursive and type-strict, executed in the draft: 220/220 pass, and a
>   type-only stray `15` → `15.0` edit that `==` misses is caught.

## Implementation note (post-gate, ungated)

**Notes applied from rounds 5 and 6** (codex, `APPROVE_WITH_NOTES` both times):
* §2.8(2) now describes the substituted function accurately: the live read, the default-branch lookup
  and the resolution. It also says "three arithmetic tests" where it said "other three".
* V9's label is narrowed to what its check covers.
* V6 asserts the 222 structural lint files explicitly.
* V3 names invalid `before` anchors: malformed, not a step, another job, absent, ambiguous, and the
  placed step itself.
* V1's `rename` example uses a local case.

**Found by executing the red controls, and implemented more strictly than §7 states.** The first
battery ran 51 controls and 9 SURVIVED:
* **6 were V3 guards masked by later guards.** A control that accepted any failure naming the case
  passed with its guard deleted, because a downstream guard raised instead. This is the
  defence-in-depth masking the 2780 campaign keeps meeting. Each V3 control now asserts its own
  REASON.
* **The two step-placement postconditions covered for each other.** Every wrong-placement control broke
  both, so either could be deleted unnoticed. V4 gains two discriminating controls:
  * a correct duplicate whose copy is MODIFIED, which only the placement value check sees;
  * a correct duplicate plus a stray edit to another step, which only the step frame sees.

  V4 also requires the failure to be a postcondition, not a precondition.
* **V6's raw count measured intent, not effect.** A counter beside the write kept counting when the
  write was dropped. The count is now the files in the lint tree.

**Other implementation detail:** `before` must be `$.jobs.<job>.steps[name]`, naming a step in the
same job, and never the step being placed.

**Final battery: 51 controls, 51 red,** run against the formatted code that ships. By cell:
* V1: 3
* V2: 1
* V3: 21 guards
* V4: 9 weakenings
* V5: 4
* V6: 4
* V7: 2
* V8: 3
* V9: 2
* §2.5: 2

One mutant is EQUIVALENT and is not counted as a survivor. The `else` branches of `_mutate_key` and
`_mutate_steps` are unreachable behind `_check_operator_fields`' unknown-op guard.

**PR #108 review (codex, P2), fixed.** A rooted `edit_bytes` case in an obligation of any kind other
than `yaml` or `raw_text` would be classified `raw` and counted as executed. Both raw classes filter by
their own KIND, though, so nothing diagnosed it. Reproduced: with the obligation's `kind: yaml` changed
to `yml_typo`, or to `content_digest`, the suite stayed green. Three changes close it:
* obligation kinds are a CLOSED set (`OBLIGATION_KINDS`);
* raw cases count as executed only if their obligation's kind is one a raw class runs
  (`_RAW_CLASS_KINDS`);
* `_raw_problems` fails closed on any other kind.

Both reproductions now go red. With the accounting fix deleted, the `content_digest` reproduction goes
green again, so that fix is the one doing the catching. Both reproductions are now in the battery.

**PR #108 second review (codex, two P2s), fixed.**
* **A remote case was `injected` whatever its `op` said.** The cell-16 test hard-codes its injection,
  so `op: typo` on `C16.canary-not-required/present` stayed green. Reproduced. Two changes close it.
  First, the `injected` row now selects only the shape cell 16 implements: an `add` to the injected
  ruleset observation. Second, `_injected_context` requires the payload to be `{context: <string>}`.
  Cell 16 reads its context from the case, and a check that never skips requires that context to be
  the canary's. Cell 16's own execution can still skip without an authenticated ruleset read.
* **A raw case could count as executed with no entry to run on.** Codex's example,
  `C3.runner-and-timeout-pinned` with `entries: []`, was caught, but only INCIDENTALLY: the obligation
  also has structural cases, and the 222 count dropped. A raw-only `yaml` obligation with no entries
  escaped: probed, all 130 tests stayed green. Two changes close it. Every obligation now declares at
  least one known entry. The raw helper also tracks execution per (case, entry), so an empty or partial
  list is reported per case, not hidden in an aggregate.

All three reproductions are in the battery, which stands at 56 controls, all 56 red.

**Registry migration:** 157 fields across 95 cases, self-verified. The script reloads the result,
requires every case to equal its specified form, and requires every other key to be unchanged.

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
* 28 recipes build a different mutant from the one the registry declares (§2.10);
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
output). §7's cells turn the counts that describe the END STATE into executed assertions: F1's census
(V1), F2's 220 and its actionlint result (V5, V6), F6's 24 (V8) and V5's 222. F3, F4 and F5 describe
the MIGRATION, comparing the recipes and the registry as they are today. They have no standing form,
because the recipes are deleted. §2.10's table is their record.

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
* **F3 — what generation changes.** With the registry corrected as §3 specifies, 171 of the 220
  generated mutants are byte-identical, after `yaml.safe_dump(sort_keys=True)`, to the recipe they
  replace. The other 49 executions (25 cases) differ. Each difference is listed in §2.10 and resolved
  by the rule stated there.
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
* **F5 — targets come in five spellings.** `$.`-rooted paths, bare `steps[<name>]…`, `.with.<key>`
  relative to the Trunk step, bare names (`guard-launcher-path`, `continue-on-error`), and the
  `insert` case's prose `before trunk`. Of the
  `structural` and `raw` cases, 80 targets are not `$`-rooted. §3 rewrites 83 targets: those 80, the
  two `defaults` parents (F4), and the literal canary job id, which becomes `<job>`.
* **F6 — the resolver family already executes correctly; only its wording differs.** The draft ran all 24
  (`applies_to` × `sides` × `forms`) executions. Each one went through the real `_resolve_once` boundary,
  with only the live ruleset read substituted. Every one reached the right verdict class: 8 equality
  forms produced exactly one problem for their entry, and 16 refusal forms raised. "Substituted" means
  that `_resolve_target_set` was replaced. That wrapper performs the live read, the default-branch
  lookup AND the resolution, so the substitute calls the REAL `_resolve_ref_name` on the injected
  observation. Resolution is therefore still the shipped code. Neither message
  matches the registry's `diagnostics`. The comparator says "…is not the ruleset's resolved target
  set…", and the resolver says "target set unresolvable: refusing to enumerate …".
* **F7 — the plan, not the registry, is normative on three payloads.** The 2780 plan's cell-11 rule
  names "the six `if: false` cases (`job-if` and the five `step-if-*`), whose constant `false` IS the
  hazard". It also names "the three `shell: sh` mutants (`C3.no-defaults-run/workflow` and `/job`,
  `C8.run-bodies-frozen/changed-shell`)". The registry's own `job-if` case contradicts itself: its
  comment and its `actionlint_allow: [if-cond]` describe a constant, while its payload is the expression
  `github.event_name != 'workflow_dispatch'`. Its `defaults` payloads are `shell: bash -e {0}` and
  `working-directory: /tmp`. Cell 11's minimum list requires "`env: {TRUNK_PATH: /bin/true}` at
  **workflow** level, at job level, and at step level". The registry's step case says
  `BASH_ENV: /tmp/x`. The hand-written recipes follow the plan on all three points.
* **F9 — revision 2's postconditions are executed, not just specified.** The draft implements §2.3's
  table. All 220 executions satisfy it, and each of these seven wrong-effect controls is caught:
  * a duplicate placed before the guards;
  * an append with an extra newline;
  * an insert after the anchor;
  * a write to the parent key;
  * a write of `None`;
  * a step moved to the wrong index;
  * a stray second edit.

  §2.7's span check holds for four representative raw payload shapes, `yes`, `017`, `TRUE` and
  `!!int 1_5`. The eight raw cases hold seven distinct spellings. The
  `yes` → `on` substitution changes the text while the diagnostic stays the same, which is codex's
  r1 point, measured.
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
classifier derives. So a fixture case added to the registry fails the suite until it is listed in the
set that the per-entry accounting checks, and the set cannot name a case the registry does not
classify there. That is ownership bookkeeping, not a witness that the fixture ran. Execution remains
the fixture tests' own business, as it is today (§6). `RAW_YAML_CASES` is deleted, and the raw class is
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
step-name := [A-Za-z0-9_-]+
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

`payload` is REQUIRED on `add`, `set`, `append` and `insert`.

**A postcondition on every write: the declared VALUE, and nothing else changed.** The diagnostic
assertion cannot see what the mutant is. A generator that wrote the payload to the wrong key, kept a
superseded separator, or placed a duplicate before the guards would still produce some case's
diagnostic. codex confirmed the duplicate placement against the checker (r1). So after each write,
`_mutate` reads the mutant and compares it with the base it started from, independently of how the
write was made. A failure names the case.

| op | value check | frame check: nothing outside the edit changed |
|---|---|---|
| `add`, `set` | the target equals `parse(payload)`, type-strict | deleting the target key from base and mutant leaves equal documents |
| `remove` (key) | the key is absent | deleting the key from the base yields the mutant |
| `append` | the target equals `old + payload`, exactly | as for `set` |
| `move` (key) | the source is absent, and `to` equals the source's old value | deleting the source from the base and `to` from the mutant leaves equal documents |
| `remove` (step) | the sequence is one shorter, and no step has that name | deleting that one element from the base sequence yields the mutant sequence |
| `move` (step) | the step stands IMMEDIATELY before the anchor (or last, for `at: end`), and is equal to its old value | deleting it from both sequences leaves equal sequences, with the order preserved |
| `duplicate` | the sequence is one longer; the new element equals the original and stands IMMEDIATELY before the anchor (or last); the name now matches two steps | deleting the new element yields the base sequence |
| `insert` | the sequence is one longer, and the element IMMEDIATELY before the anchor (or last) equals `parse(payload)` | deleting that element yields the base sequence |

**Equality throughout this table is recursive and TYPE-STRICT.** Two values are equal only if they
have the same type at every depth: `False` ≠ `0`, `15` ≠ `15.0`, and a mapping equals a mapping only
when its keys and values do. Python's `==` would let an unrelated `timeout-minutes: 15` → `15.0`
edit pass a frame check. The draft catches exactly that edit with the strict comparison (F9).

For step operators, the document outside the job's `steps` must equal the base's. The §2.5 companion
is applied first, and the frame for the primary edit is taken from the base WITH the companion.

### 2.4 Payloads

`payload` must be a **string** in the loaded registry. A non-string fails, naming the case. That
includes PyYAML 1.1 reading an unquoted `yes` or `017`, which is how the registry is loaded. The
parsing rule below is for STRUCTURAL cases only. A `raw` case's payload is never parsed: it is the
bytes written into the source (§2.7). For every structural op except `append`, the string is YAML TEXT, parsed by `_load_actions_yaml`, the same YAML 1.2
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

Its validity, "the support job must fail", is EXECUTED. The test runs the companion's run body with
`bash` and requires a non-zero exit. A non-zero step exit fails the job only if nothing masks it, so
the companion's SHAPE is closed as well:
* the declared mapping holds exactly `id`, `why`, `runs-on` and `steps`;
* `steps` holds exactly one element;
* that element holds exactly the key `run`.

So a later declaration cannot add `continue-on-error` or `if` at job or step level, or a second step,
and still pass. Anything else fails, naming the case (codex, r3). The mutant's `$.jobs.<id>` must also equal the declared mapping,
minus `id` and `why` (§2.3's frame).

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

The 8 `raw` cases are built from the registry. A diagnostic does not show which bytes a raw case wrote:
`save-annotations: yes` and `: on` fail identically. So each raw mutation has its own postcondition.
Let `[start, end)` be the pinned value's span in the SOURCE text. The mutated text must hold `payload`
byte for byte at `[start, start + len(payload))`. The text before `start` must equal the source's,
and the text after the payload must equal the source's text after `end`. The check uses the source
offsets, not a re-parse of the mutant, because a tagged payload such as `!!int 1_5` re-composes to a
node whose span excludes the tag. A payload-substitution control then changes one raw
case's payload in a COPY of the registry, to a different hazardous spelling (`yes` → `on`). It
requires the regenerated text to carry the new token in that span, and to differ from the text the
original payload produced.

Before any reduction, the WHOLE raw target is validated against the entry it runs on. It must parse
in the §2.2 grammar, `<job>` must resolve to that entry's job id, and a step selector must match
exactly one step there. This matters because `_pinned_pairs`, which `_respell` uses, searches every
job and every matching step, so a target naming the wrong job or step would otherwise reduce to the
same tuple. The generator then derives the pinned path from the canonical
target: `(step, key)` for `$.jobs.<job>.steps[<step>].with.<key>`, and `(key,)` for
`$.jobs.<job>.<key>`. That path must be one of `PINNED_PATHS`' values, or the case fails by name.
Today each tuple carries only the target's last segment, and the registry's target is never read, so
a registry target naming the wrong step would pass unnoticed. The replacement is `payload`, verbatim.
The checker comes from the obligation's kind: `raw_text` → `raw_workflow_problems`, `yaml` →
`contract_problems`.

**Raw mutants are linted AS TEXT.** Cell 11's constructibility rule covers them too. A span and frame
check cannot see a payload GitHub would reject: `lfs: []` keeps the frame, produces its own
diagnostic, and fails actionlint's `syntax-check` (codex, r4, reproduced). Parsing and re-dumping a
raw mutant would erase the very spelling it exists to test. So the actionlint test writes each raw
mutant's TEXT, for every (case, entry, permitted spelling), into the same lint tree as the structural
dumps. The same allowlist rules apply, through the case's own `actionlint_allow`. Measured: 304 raw
texts, 0 findings. The two classes keep their
other tests (the decoy, every-spelling and positive-control tests), and their `CASES` become the
derived lists. F1: today all 8 registry cases agree with their tuples field for field, so this
changes no executed mutant.

### 2.8 The resolver family: 24 executions

For each obligation in `families.target_set_resolution.applies_to`, its single entry, each `side` and
each `form`:

1. injected := the recorded raw target set (`c2AndCell16RemoteHalves.rawTargetSet` in the rollout
   evidence), with `injected[side]` replaced by `[form.payload]`. The default branch is `main`, a
   fixture value: the evidence does not record one, and each form's outcome is checked below;
2. `_resolve_target_set` (the live read, the default-branch lookup AND the resolution) is patched with a CALLABLE `side_effect` that
   evaluates `_resolve_ref_name(injected, "main")` when it is called. A refusal therefore raises
   inside `_resolve_once`, not while the patch is prepared. `_resolve_once`, `_target_set_results` and
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
is deleted. The class's three arithmetic tests stay (alias and prefix expansion, exclude veto, and
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
declared. Four cases fall under the first half (F7): `job-if`, the two `defaults` cases and
`C5.no-env-any-scope/step`. The other 24 fall under the second.

**Where the normative text is, and how "silent" was established.** Cell 11's minimum list in the 2780
plan's §7 (the bullets after "The generator must at minimum produce") enumerates, clause by clause,
the mutants the generator owes. Revision 3 reads that list in full. A search for each payload string
could not find payloads stated per clause, and that is how revision 2 missed C5 (codex, r2).

Every value the list names, with what the registry says:
* **Matches the registry:** `if: false` and `continue-on-error: true` on each of the five steps;
  `run: ":"`; `TRUNK_PATH` at workflow and job scope; `TRUNK_PATH=/bin/true` and `BASH_ENV=…` written
  to `$GITHUB_ENV`; the `schedule` event; the `container`, `id` and `timeout-minutes` keys; and
  `lfs: false` and `persist-credentials: true`.
* **Contradicts the registry:** the four F7 cases.
* **No value named:** every other bullet names a key or an event and no value.

Elsewhere in the plan, three lines name a case id next to a code span. Two of them are F7's `shell: sh`
sentence. The third is `C16.canary-not-required/present`, which stays `injected`.

| case(s) | executions | recipe built | generated (resolution) |
|---|---|---|---|
| `C3.nothing-skips-or-masks/job-if` | 2 | `if: 'false'` | `if: false`. **Plan wins** (F7). The registry's payload and `validity` are corrected, and its comment and allowance are already right |
| `C3.no-defaults-run/workflow`, `/job` | 4 | `defaults: {run: {shell: sh}}` | the same. **Plan wins** (F7). The registry payloads `shell: bash -e {0}` / `working-directory: /tmp` are corrected, and the targets move to `$.defaults` / `$.jobs.<job>.defaults` (F4) |
| the five `step-if-*` | 10 | the string `'false'` | the boolean `false`, the registry's payload and the plan's `if: false` |
| `C0.no-concurrency/workflow`, `/job` | 4 | `group: x` | `group: trunk-check` |
| `C5.no-env-any-scope/step` | 2 | `env: {TRUNK_PATH: /bin/true}` | the same. **Plan wins** (F7). The registry's `BASH_ENV: /tmp/x` and its `validity` are corrected |
| `C8.step-sequence-allowlist/extra-step` | 2 | `{name: extra, run: echo hi}` | `{run: echo hi}` |
| `C1.single-event/add-push` | 1 | `branches: [main]` | `branches: [main, alpha]` |
| the 15 run-body appends (`creates-c6-path`, `github-env-*`, `github-path`, `body-digest-*`, per step) | 30 | body + `"\n"` + line | body + line. The body already ends in a newline, so the recipe's extra `"\n"` was a blank line. `github-path` on `guard-empty-diff` also takes the registry's `/tmp/fake` |

That is 55 executions in total. The four `defaults` executions and the two C5 executions come out
identical to their recipe once the registry is corrected, which leaves F3's 49 executions (25 cases). `job-if` still differs
from its recipe, by type: the boolean `false` replaces the string `'false'`, as it does on the five
steps.

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
   `':'` → `"':'"`; `body-digest-*` gain `":"`; and `job-if`, `defaults` and C5's step case follow
   §2.10. 30 in total, counting the 9 prose payloads item 3 removes.
5. **Diagnostics:** the 11 cases of §2.9, plus C16 `local-divergence`. The family's `diagnostics` are
   unchanged, because the checker moves to them (§2.8).
6. **`validity` text that described a removed payload.** `job-if`'s stops saying "strictly worse than
   the hazard it was written to fix", which described the expression. C5's step case stops saying
   "alters every Bash process the action spawns", which described `BASH_ENV`. It names the
   launcher redirect instead: the action reads `TRUNK_PATH`, so `/bin/true` runs in its place.
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
| V3 | the generator fails closed on each requirement in §2.2–§2.4 | one synthetic case per requirement, each `assertRaises` with the case id in the message | each guard is deleted, one at a time. The guards: unparseable target; step 0 matches; step 2 matches; `add` on a present key; `set` on an absent key; `set` to an equal value; `remove` of an absent key or step; `append` to a non-string; `move` from an absent source; `move` to a present `to`; a non-string payload; a MISSING payload on each of `add`, `set`, `append` and `insert`; a payload on `remove`, `move` and `duplicate`; an `insert` payload that does not parse to a mapping; an `insert` target that is not a sequence; `to` on anything but a key `move`; both `before` and `at`; neither; an `at` other than `end`; an unknown op. Separately, the set-equal TYPE comparison is dropped, and `timeout-float` must then fail to build |
| V4 | every §2.3 postcondition, value and frame, with type-strict equality | after every structural write, plus one synthetic wrong-effect control for EVERY row of §2.3's table, and a type-only stray edit (`15` → `15.0`) that `==` would pass | `_mutate` writes `parse(payload)` to the PARENT key (frame); writes `None` (value); appends `"\n" + payload` (append value); places a duplicate at index 1, before the guards (placement); inserts AFTER the anchor (placement); moves a step to the wrong index (placement); drops the companion's `exit 1` (§2.5's executed failure); adds `continue-on-error: true` to the companion's step (§2.5's closed shape); compares with `==` instead of strictly (the type-only control) |
| V5 | every structural (case, entry) builds, differs from its base, and yields its registry diagnostic at M3: 222 executions (220 + the two `local-divergence`) | the per-entry test, with its count asserted | one §3 diagnostic edit is reverted; `<job>` resolves to the other entry's job id; the M3 constant becomes M2 (the `no-job-continue-on-error` case must red) |
| V6 | actionlint accepts every generated mutant, structural AND raw, apart from declared allowances, and no allowance is stale | the existing test, now over the generator's output: structural mutants dumped, raw mutants written as their source TEXT (§2.7). The count of raw texts is asserted as cases × entries × permitted spellings | `job-if`'s payload reverts to the expression (a stale `if-cond` allowance); a `needs` case is built without its companion (`job-needs`); a raw case's payload becomes `"[]"` (`syntax-check`, although its span, frame and diagnostic all still pass); raw mutants are dropped from the lint tree (the asserted count reds) |
| V7 | the raw cases are derived; the pinned path agrees with the target; the span holds the payload verbatim, and nothing else changed | the two raw classes, the span postcondition, and the substitution control (§2.7) | a raw target names the wrong step; the executor keeps the OLD token when the registry's payload changes (`yes` → `on`: the substitution control must red, although the diagnostic alone stays green); the executor writes outside the span |
| V8 | the family: 24 executions; verdict class and diagnostic per form; distinguishable | the family test, with its count asserted | the resolver treats `~ALL` as a literal; the comparator ignores `resolved`; both family diagnostics are made equal |
| V9 | none of the retired recipe declarations is declared again | a DECLARATION-aware check: parse the module with `ast` and require that no function, method or assignment target is named `_yaml_mutants`, `_canary_mutants`, `RAW_YAML_CASES` or `test_patterns_and_all_fail_closed_on_both_sides`, and that no class assigns a literal tuple to `CASES`. It inspects declarations, not text, so the check's own name list cannot trip it | any of them is declared again |
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
