# Trunk Lint Configuration Plan (COREDEV-2771)

**Status:** Planning
**Created:** 2026-08-27
**Last Updated:** 2026-08-27
**Revision:** 26 — remediates round 25, where **both arms independently found the same High**.

**M9's artipacked assertion could not fail.** Step 7b greped Trunk's output using zizmor's own
`--format=plain` header shape (`^[a-z]+\[artipacked\]:`). Trunk renders the audit as
`zizmor/zizmor/artipacked`, so the pattern matched **0 of 7** real findings and `-eq 0` passed
unconditionally. Measured both ways. Now uses the Trunk form, and — because a `-eq 0` assertion is
worthless unless the pattern can be non-zero — it is controlled first against `template-injection`,
which survives M8 and is rendered by the same code path. The assertion correctly **fails today** (7
findings) and can pass only once M8 lands.

**Two line counts are not an association.** `grep -c 'actions/checkout@'` = 7 and
`grep -c 'persist-credentials: false'` = 7 both hold when one step lacks the setting and another
carries it twice. Replaced with a parse of the workflow that checks each checkout step individually,
proven with both controls: seven-correct passes, one-missing fails and names the step.

Also: the `case "$rc" in 0|1)` gate was dropped when the summary-line check was added, so an unexpected
status accompanied by a summary would have passed — both are now required. A later revision built
`$manifest`/`$digests` inside the sequence from a literal path list; that whole sequence has since been
cut as scaffolding (see M9), so the fix is recorded only as history.

## Overview

Make Trunk's linter configuration correct, verified and version-controlled for this repo,
and fix four defects in how Trunk invokes its linters. They are **not one category**, and revision 2
was wrong to call them all "configuration-reachability" bugs — only gitleaks is that. Precisely:

| Override            | Category                                                                  |
| ------------------- | ------------------------------------------------------------------------- |
| gitleaks            | config genuinely unreachable — no `--config`, sandboxed target copy        |
| markdown-link-check | no config was ever passed; there was nothing to make reachable            |
| trufflehog          | **not a definitions override at all** — a path-scoped `lint.ignore` (see A2)  |
| zizmor              | **persona** — a strictness setting, not a config defect                    |

Trunk is installed here (CLI 1.25.0, plugins v1.11.0) with 16 linters enabled, but `.trunk/` is
untracked and nothing in `plugin-ci.yml` runs `trunk check`. It is therefore invisible to CI and to
every other machine — while simultaneously producing 5,113 findings locally that CI does not enforce.

This plan does three things: fix the wiring, add the four linters worth adding, and commit the
result. **Enforcing it in CI is COREDEV-2780**, split out after the gate showed that work needed a
different kind of verification than this does.

## Problem statement — all measured, none inferred

Baseline, `trunk check --all` over 212 files, measured in an isolated clone at the plan's base
(see "Measured outcome" for why the tree matters): Trunk reports **588 security + 4,525 lint issues
(3,290 auto-fixable)** — **5,113 findings** in total.

### P1 — Three linters invoked in ways that defeat their intended behaviour

| Linter              | How Trunk invokes it                                                                          | Consequence                                                                                                                                 |
| ------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| gitleaks            | `gitleaks detect --no-git --source=<target>`, **no `--config`**, `sandbox_type: copy_targets` | The repo's tuned `.gitleaks.toml` is never read. Its allowlists for the redactor's synthetic fixture corpus never apply. 3 false positives. |
| trufflehog          | `trufflehog filesystem --only-verified …`, no detector filter                                 | **Not a config-reachability defect** — listed here only because it shares the fixture-corpus cause. The `Lob` detector fires on strings `redactor_model.py` _generates_ to be secret-shaped. **26** findings, 0 real. The fix below is a path-scoped `lint.ignore`, **not** a `lint.definitions` override: no detector filter is disabled repository-wide, but the whole linter is skipped inside the two named test paths. |
| markdown-link-check | `markdown-link-check -q "<target>"`, **no `-c`**                                              | No config at all: no timeout, no 429 retry, no way to exempt deliberate cross-repo links.                                                   |

A precision note, because revision 1 put this too broadly. `.gitleaks.toml` carries **two kinds** of
allowlist: `commits`-scoped entries (the accepted historical `firebase-debug.log` exposure), which
indeed cannot fire on a working-tree scan, and **global `regexes` entries** (the redactor fixture
shapes, the GCP project id), which fire in any scan mode. The second kind is what suppresses these
findings once a config is read at all. The defect was never "the allowlists are the wrong kind" — it
was that **no config was being read**.

Verified in isolation, with Trunk and its `lint.ignore` rules removed from the picture entirely — the
two fixture files scanned directly: **2 findings without the config, 0 with `GITLEAKS_CONFIG` set.**
(`GITLEAKS_CONFIG` is a documented gitleaks config source, listed in its own `--help` directly after
`--config/-c`.)

### P2 — bandit's config file was silently inert

Trunk _always_ passes `--ini .bandit`. `--ini` is documented as "path to a .bandit file that supplies
command line arguments": an INI whose keys are CLI option names and whose values are **bare and
comma-separated**. Bandit's _other_ config format (the YAML one used by `-c/--configfile`) spells
exclusions `exclude_dirs: [...]`. Given that form, bandit parses the file, honours nothing, and
**reports no error**. A nonexistent `--ini` path is likewise silent.

Verified by mutation: `skips: B404` removes B404 from the output; `skips = ["B404"]` does not.

### P3 — shellcheck diverges from CI in the noisiest possible direction

`.trunk/configs/.shellcheckrc` sets `enable=all`. Every one of the 3,633 shellcheck findings is
severity `low`, and 3,593 of them come from four optional style checks:

| Code   | Count | Check                                                        |
| ------ | ----- | ------------------------------------------------------------ |
| SC2250 | 2509  | prefer `${var}` over `$var`                                  |
| SC2292 | 680   | prefer `[[ ]]` over `[ ]`                                    |
| SC2312 | 348   | consider invoking separately to avoid masking a return value |
| SC2249 | 56    | consider adding a default `*)` case                          |

CI runs `shellcheck -s bash -S warning`, which excludes all four. That is 79% of the baseline LINT findings (3,593 / 4,525) and 70% of all 5,113 baseline findings;
revision 1 called it 79% of the entire baseline, which mixed the two denominators. Either way it is
none of it enforced anywhere.

### P4 — coverage gaps

- **No type checking** across 66 Python files. CI byte-compiles on 3.9 and 3.12, which catches syntax only.
- **No GitHub Actions security analysis.** actionlint and checkov both report 0 findings; neither audits
  for credential persistence or template injection.
- **No link checking** across 77 markdown files, in a repo whose product largely _is_ markdown and whose
  documented recurring defect is a reference whose target was deleted.

## Approach

### A. Four configuration changes — three `lint.definitions` overrides, plus one path-scoped ignore

Trunk supports overriding a linter definition by name; overrides apply on the
`[name, version, platforms]` tuple. Four overrides in `.trunk/trunk.yaml`:

1. **gitleaks** — add `environment: GITLEAKS_CONFIG = ${workspace}/.gitleaks.toml`, so the repo config
   is read by absolute path and survives the target-copy sandbox.
2. **trufflehog** — scope it away from the two test directories with Trunk's own path-scoped
   `lint.ignore`, and leave every detector enabled. Revisions 2-4 disabled the `Lob` detector
   repository-wide instead, which cost real coverage; that is now withdrawn.

   The reasoning that led there was wrong in an instructive way. trufflehog's own
   `-x/--exclude-paths` genuinely does not work through Trunk (measured in six forms, including a
   pattern matching every path), and from that I concluded no narrow fix existed. But Trunk has a
   *second*, independent mechanism — `lint.ignore` accepts `linters:` **and** `paths:` — which this
   plan already uses for `.claude/**`. I never tried it for trufflehog. Measured:

   | Configuration                                                | trufflehog findings |
   | ------------------------------------------------------------ | ------------------- |
   | no exception                                                 | 26 (all fixtures)   |
   | `lint.ignore` scoped to `[trufflehog]` + the two test dirs    | **0**               |
   | same, with a flagged file copied to a **non-ignored** path     | **4**, all `Lob`    |

   The third row is the retained positive: Lob is still live everywhere outside the ignored paths.

   **The exact ignore, and its real cost.** The paths are `scripts/tests/**` and
   `mcp/review-synthesizer/tests/**`, scoped to `linters: [trufflehog]`. Saying "no coverage is lost"
   would be **false**: a `lint.ignore` suppresses *every* trufflehog detector inside those two
   directories, not only Lob. So the trade is a **repository-wide loss of one detector** exchanged for
   a **localized loss of all detectors in two test directories**. That is a substantial improvement —
   the rest of the repo, including every production path, keeps full detection — but it is not free,
   and a real credential pasted into a test file would not be reported by Trunk. The history-aware
   gitleaks CI job still scans those paths under its own rules.

3. **markdown-link-check** — pass `-c ${workspace}/.trunk/configs/markdown-link-check.json`.
4. **zizmor** — run `--persona=auditor`, its most aggressive mode, rather than the default `regular`.

### B. Add four linters

| Linter                  | Why                                                                                    | Findings |
| ----------------------- | -------------------------------------------------------------------------------------- | -------- |
| **zizmor**              | GitHub Actions security. Purpose-built for the class actionlint and checkov both miss. | 30       |
| **mypy**                | Static types over 66 Python files, `python_version = 3.9` to mirror the CI floor.      | 2,308    |
| **markdown-link-check** | The automated half of the cross-reference check.                                       | 4        |
| **codespell**           | Typos across 77 md + 66 py.                                                            | 2        |

mypy's count is **findings**. It also emits 1,380 explanatory `note` lines, which Trunk reports
separately as non-blocking and which are not findings; an earlier revision conflated the two and
labelled their sum as findings. All four counts are from the isolated clone, like every other figure
in this document.

Measured and **rejected**: `osv-scanner` (0 findings — zero-dependency repo), `trunk-toolbox` (0 findings).

### C. Configure aggressively, verify every config by positive control

A config that is not read is indistinguishable from a config that finds nothing. Each config file gets
a mutation that must change the output; P2 above is exactly the defect this discipline catches.

### D. ~~Clear the auto-fixable backlog with `trunk fmt`~~ — WITHDRAWN

Revision 1 listed this as a step. It was executed, it produced 216 failures and errors across 192
distinct tests, and it is withdrawn — see
"trunk fmt is unsafe here". Do **not** run `trunk fmt` on this repository.

### E. Land the `artipacked` fixes, then commit `.trunk/`

## Decisions and their reasons

### D1 — Keep `enable=all` for shellcheck (Trunk runs stricter than CI)

Deliberate. Trunk is the stricter **local** check; CI's `-S warning` remains the enforced gate.
(Whether Trunk ever gates a PR is COREDEV-2780's question, not this plan's — an earlier revision said
"local/PR gate" here, which the CI sweep missed.) The backlog
gets burned down over time rather than hidden. `external-sources=true` + `source-path=SCRIPTDIR` are
added so shellcheck follows the 10 sourced libraries in `scripts/lib/`, which is what makes the newly
enabled SC2154 accurate instead of a false-positive generator.

### D2 — Four rules turned OFF because they are wrong for this repo

Aggressive does not mean "obey rules that would break the build".

- **`ruff/PT009` (4005 findings) — actively harmful.** It rewrites every `self.assertEqual` to a bare
  `assert`. This is a unittest codebase (`python3 -m unittest discover`), and `plugin-ci.yml` carries the
  warning _"No bare `assert`: python3 -O / PYTHONOPTIMIZE strips those and the step would exit 0 over a
  red suite."_ Obeying PT009 would create the exact failure mode the repo keeps a gate for. `PT027` is
  the same mistake for `assertRaises`.
- **`mypy/no-untyped-call` — disabled for backlog control, NOT because it is redundant.** Revision 1
  called it "the same unannotated definitions counted a second time" (quoting a figure that was
  itself measured in the wrong tree). That is wrong:
  `no-untyped-def` reports unannotated *definitions*, while `no-untyped-call` reports **typed callers
  crossing into untyped code** — a genuine call-boundary control, documented as distinct. Disabling it
  means new typed code may call pre-existing untyped functions with no diagnostic. That is a real
  loss, accepted deliberately so the ~350 actual type bugs (`attr-defined`, `union-attr`, `arg-type`,
  `possibly-undefined`) stay visible during rollout instead of being buried. mypy's
  `untyped_calls_exclude` can re-enable it while exempting named legacy modules; that is the intended
  end state (Q3).
- **`ruff/N802` in test dirs only.** This suite capitalises for emphasis on purpose
  (`test_the_anchor_is_NOT_widened`), and unittest's own `setUp`/`tearDown` are camelCase by API
  contract. N802 stays on for production code.

### D3 — WITHDRAWN. bandit runs everywhere; nothing is suppressed

Revision 1 of this plan ignored `bandit` on `scripts/tests/**` and
`mcp/review-synthesizer/tests/**`, on the stated premise that B101 (`assert_used`) "accounts for
nearly all 414 bandit findings" and that assert *is* the API in a test. **That premise was false and
the decision is withdrawn.** Measured directly with bandit's own JSON output:

All figures are Trunk's own (`trunk check --filter=bandit`) from the isolated clone at the plan's
base. A direct `bandit -r` over a different file set reports slightly different totals; that series is
not used here.

| Scope                                       | bandit findings | of which B101 |
| ------------------------------------------- | --------------- | ------------- |
| `scripts/tests/` + `mcp/**/tests/`          | 541             | **17** (3.1%) |
| production (`scripts/`, `mcp/`, tests excl.) | 21             | **2**         |
| repo-wide                                    | 562             | **19** (3.4%) |

The ignore was therefore suppressing **541 findings in total**, of which **524 were non-B101
collateral** — B603 (255), B607 (159), B404 (47), B103 (28),
B108 (20), B604 (14), B610 (1) — to silence 17 assertions. Seventeen findings need no mechanism at
all. `lint.ignore` really is path-scoped and really does reject `linters: [bandit/B101]` (that part
was verified), but the constraint never mattered, because there was nothing worth suppressing.

The `lint.ignore` block for bandit has been removed. Bandit now runs on every Python file in the
repo, and the 17 B101 sites are ordinary backlog. If they ever become noise the mechanism is
`# nosec B101` on those 17 lines — not a config change, and not a path ignore.

**The generalisable error:** the original figure came from counting bandit rows in a `trunk check`
transcript with a regex, then assuming the majority rule. It was never checked against bandit's own
per-rule output. A decision to disable a security linter should not rest on a derived count.

### D4 — Cross-repo links exempted, everything else strict

`agents/*.md` link into the sibling UnleashedMail **app** repo via `../../Unleashed Mail/`. The plugin
cannot contain the app, so these are unresolvable by construction rather than broken. A permanently
unfixable finding trains readers to ignore the linter, so these are exempted by pattern, with the
reason recorded in the config. Every other link stays checked.

## Milestones

- [x] M1: Audit the current Trunk config and measure a baseline
- [x] M2: Measure each candidate linter before adopting it
- [x] M3: Add the three `lint.definitions` overrides (gitleaks — config reachability;
      markdown-link-check — no config was passed; zizmor — persona) plus the trufflehog path ignore
- [x] M4: Write aggressive per-linter configs
- [x] M5: Verify every config by positive control
- [x] M6: Run `trunk fmt` and review the diff — **DONE, NEGATIVE RESULT. `trunk fmt` is unsafe on
      this repo as configured; see the "trunk fmt is unsafe here" section. The change was reverted.**
- [x] M6a: **Out of scope, and not tracked here.** Any future `trunk fmt` work must cover every
      enabled formatter (shfmt, black, isort, prettier, taplo), regenerate the shipped manifests in
      the same change, and take the full `scripts/tests` suite as its acceptance test — `shfmt -i 4`
      alone is insufficient. Recorded in the `trunk fmt` section; no ticket is opened because nobody
      is asking for formatting. The operative instruction is simply: do not run `trunk fmt`.
- [ ] M7: Plan Review Gate — `/unleashed-mail:gemini-review` + `/unleashed-mail:codex-review` to
      APPROVE / APPROVE_WITH_NOTES, then `/unleashed-mail:review-synthesis`
- [ ] M8: Land the seven `persist-credentials: false` fixes in `plugin-ci.yml`. **One PR, merged
      before M9's PR is opened** — the fixes must already be on the base branch when zizmor starts
      running against it.
      **The acceptance test must not go through `trunk check`.** Three revisions each fixed one
      obstacle and hit the next: the main checkout lacks the PR's changes pre-merge;
      `.claude/worktrees/*` has them but zizmor is inert there (COREDEV-2779); and a clone at M8's own
      head has neither, because the configuration that *enables* zizmor does not land until M9 —
      `origin/main`'s `trunk.yaml` contains no zizmor entry at all (verified).
      **Invoke the zizmor binary directly.** Note that `zizmor` is **not on `PATH`**: the pinned
      1.29.0 binary is provisioned by Trunk and lives under
      `~/.cache/trunk/tools/zizmor/<version>-<hash>/bin/zizmor`. Resolve it explicitly — either that
      path, or any independently pinned 1.29.0 install — and record which was used. This avoids
      `trunk check`, not Trunk's tool provisioning; an earlier revision claimed it needed "no Trunk"
      at all, which was false.
      **The control must be rule-specific, not merely non-empty.** "Some findings exist" does not
      prove the `artipacked` audit is live. Run the same binary on the **unmodified** file first and
      require exactly **seven** `artipacked` findings; then apply the fixes and require **zero**.
      Note that zizmor exits non-zero while reporting findings, so capture the exit status
      deliberately rather than letting it fail the step.

      A wildcard in a variable assignment is **not** expanded — under zsh
      `ZIZMOR=~/.cache/trunk/tools/zizmor/1.29.0-*/bin/zizmor` stays literal and every later
      invocation fails; under bash it is ambiguous if more than one hash directory matches. Resolve
      deterministically instead (verified working under both `bash` and `zsh`):

      ```sh
      set -euo pipefail   # as in M9: without this, a failed pre-edit assertion continues
                          # to the post-edit one and the milestone passes having proved nothing.
      resolve_zizmor() {
        local found count
        found="$(find "$HOME/.cache/trunk/tools/zizmor" -type f -perm -u+x -name zizmor 2>/dev/null | sort)"
        count="$(printf '%s\n' "$found" | grep -c .)"
        [ "$count" -eq 1 ] || { echo "expected exactly 1 zizmor binary, found $count" >&2; return 1; }
        ZIZMOR="$found"
        # Exact match: `grep -q '1\.29\.0'` also accepts 1.29.0-dev, 1.29.01 and 11.29.0, and the
        # accepted exit codes and output parsing below are version-specific.
        test "$("$ZIZMOR" --version 2>/dev/null)" = "zizmor 1.29.0" \
          || { echo "expected exactly 'zizmor 1.29.0'" >&2; return 1; }
      }
      resolve_zizmor || exit 1
      # ONE `|| true`, on the `grep -c` only: it exits 1 when the count is 0, which is exactly the
      # post-fix expectation. zizmor's own non-zero status is handled by the `case` below, NOT by
      # `|| true` -- adding one there would discard the status and recreate the documented fail-open.
      # Measured exit codes for the pinned 1.29.0: completed scan WITH findings = 13, completed scan
      # with none = 0, invalid input = 1, malformed YAML = 3. An earlier revision suppressed stderr
      # and swallowed the status, so a FATAL error produced a count of 0 and the post-edit assertion
      # PASSED on a broken binary -- a fail-open in the one control meant to be decisive.
      count_artipacked() {
        local out st
        # `out="$(cmd)"` INHERITS cmd's status, so under `set -e` a scan that exits 13 (findings
        # present -- the normal pre-edit case) kills the shell before `st` is ever set. Verified in
        # both bash and zsh. The `|| st=$?` guard is what lets the case below run at all.
        st=0
        out="$("$ZIZMOR" --persona=auditor --format=plain .github/workflows/plugin-ci.yml 2>&1)" || st=$?
        case "$st" in
          0|13) : ;;                                                   # scan completed
          *) echo "zizmor did not complete: exit $st" >&2; printf '%s\n' "$out" >&2; return 1 ;;
        esac
        printf '%s\n' "$out" | grep -cE '^[a-z]+\[artipacked\]:' || true
      }
      # Count DIAGNOSTIC HEADERS only. A bare `grep -c artipacked` returns 14 for seven findings,
      # because the plain format prints the audit name twice per finding: once in the
      # `warning[artipacked]:` header and once in the `= help: ... #artipacked` documentation URL.
      # count_artipacked returns non-zero on a failed scan, so assign first and check the status --
      # comparing "$(...)" directly would discard it.
      c="$(count_artipacked)" || exit 1;  test "$c" -eq 7   # pre-edit control
      # ... apply the seven fixes ...
      c="$(count_artipacked)" || exit 1;  test "$c" -eq 0   # post-edit assertion
      ```

      Assert, in order: (1) **pre-edit control** — `count_artipacked` returns exactly **7** on the
      unmodified file; (2) `plugin-ci.yml` contains exactly seven `actions/checkout` uses, every one
      carrying `persist-credentials: false`; (3) `count_artipacked` returns **0** afterwards.

      **Precondition:** `resolve_zizmor` searches Trunk's tool cache, so it fails with "found 0" on a
      machine where Trunk has never provisioned zizmor. Run `trunk check --filter=zizmor` once (or
      install zizmor 1.29.0 independently) before M8, and treat "found 0" as a provisioning error
      rather than a missing binary.
- [ ] M9: Commit the configuration. **One PR, after M8 has merged.** Staged set — **thirteen** paths,
      twelve of them the digest-controlled configuration: `.trunk/trunk.yaml`, `.trunk/.gitignore`,
      the **nine** files in `.trunk/configs/` (`.bandit`, `.codespellrc`, `.isort.cfg`,
      `.markdownlint.yaml`, `.mypy.ini`, `.shellcheckrc`, `.yamllint.yaml`,
      `markdown-link-check.json`, `ruff.toml`), and `.github/zizmor.yml` — plus this plan document,
      committed with them but not part of the digest-controlled set.

      **M9 was executed on 2026-08-28; this records what it verified.** The elaborate
      clone-and-recount sequence earlier revisions specified here has been cut. It was scaffolding:
      a run-once script, executed by the same person who wrote it, which consumed thirteen review
      rounds (r14–r26) without changing a single byte that ships. Two defects the last round found
      — an unpopulated `$digests` (which made `shasum -c` abort, not pass) and a macOS-only
      `sed -i ''` — were defects *in the ceremony*, not in the configuration. What follows is the
      evidence that actually matters.

      **Commit:** `f1193ac feat(COREDEV-2771): configure trunk with 20 linters` — 12 files.

      **1. The staged set was exactly the twelve configuration files.** No path under
      `.trunk/out|logs|actions|notifications|tools|plugins` was staged; `.trunk/.gitignore` excludes
      all six, which is why `.trunk/` collapses to two tracked entries.

      **2. Digests of the blobs as committed** (read from the object database via
      `git cat-file blob HEAD:<path>`, not from the working tree, so they describe the commit rather
      than the disk):

      ```
      13ea2a519e657e42f6acaa9d3c341115b25f0e23d445960bd34c67d1ee9f79b1  .github/zizmor.yml
      a3a6850a4d3873929d6296fb261801a240eaa67247f219894da802b45359fd7e  .trunk/.gitignore
      8793071d20f4ac5f3c043e124b6368b9a6c1e2db1bdd388c5ec971ed24a2c040  .trunk/configs/.bandit
      89016ad7c2fae90f6e0a20e64e47fa3ebd7dd331bdab2232729d9be5841ea536  .trunk/configs/.codespellrc
      968e1af82279fb9bb4b6fd697ad2a83763eb6ca524403c42cf1f6f99707de619  .trunk/configs/.isort.cfg
      609c2d10b047f857a41c0086fe446b134a12bfc3ce4c873136dcb2f69d9a4f2c  .trunk/configs/.markdownlint.yaml
      91cd1cdb77113ed655aaa1c228179986d15bab76e53e2fce719901728435ef1b  .trunk/configs/.mypy.ini
      092cbe6d47cf03d414f077caab74f6dc88c5fd711c10d62dfd73e4e60e4b7358  .trunk/configs/.shellcheckrc
      b0f8d92da844b43cb2578786a84a7adfe7d9501b7f336d111c5da3a605b53584  .trunk/configs/.yamllint.yaml
      2679b0d00b3fac7da6c1845f91c2c1745023919d46ae8e03d03899fa526d5f13  .trunk/configs/markdown-link-check.json
      fb6be6430f6a3ff0ce94a40feee3e655fc2a9c0fc8530bbcc5df07cc4c9c2ce9  .trunk/configs/ruff.toml
      a213d35d7b2b2b411c6c8eb37d3be758c62381865429dc81a6d89a0e709f089f  .trunk/trunk.yaml
      ```

      **3. The gate passed before the commit, not after.** `git diff --cached --check` (whitespace,
      as CI checks it), `validate-plugin-assembly.py --strict`, `validate-hooks.py --strict
      --require-manifest`, `VERSION_SYNC_ENFORCE=strict validate-version-sync.sh`, and a YAML/JSON
      parse of all five structured configs. The pre-commit hook re-ran the three validators plus
      `gitleaks --staged` at commit time: all green.

      **What this does NOT establish.** The 4,525 → 10,839 measurement was taken in a separate
      isolated clone at `2631845`, not in this worktree, and it is a *count*, not a claim that any
      finding is correct. Nothing here verifies the linters' output — only that the configuration
      parses, is live, and is the tree that got committed. Verifying zizmor is not silently inert is
      COREDEV-2779; CI wiring is COREDEV-2780.

      **What the cut ceremony was guarding against, kept because the incidents were real.** While
      measuring this plan the isolated clone silently carried stale `.mypy.ini`/`.bandit` bytes for several
      rounds (comment-only, so no figure moved), and a later cleanup deleted 26 tracked planning documents
      from it — caught only because a re-measure returned 179 files instead of 206. The lesson is that a
      measurement is evidence only about the tree it ran on; it does not justify a bespoke verification
      ceremony, which is what thirteen review rounds were spent perfecting.

      **zizmor is inert in a `.claude/worktrees/*` checkout** (COREDEV-2779, cause not established). Any
      future measurement must run in a standalone clone outside the parent repository and assert a non-zero
      zizmor total to prove the linter was live — a zero there is indistinguishable from a clean tree.

      **Identity is by full digest, not by totals.** Equal `trunk check` totals do not establish byte
      identity — different configurations can produce the same counts. The digests recorded above are read
      from the object database, so they describe the commit rather than the working tree.
      COREDEV-2780 additionally needs this configuration on **both** gated bases (`main` and `alpha`)
      before its `--ci` job can diff against anything, and needs that landing to be a separate PR from
      the one adding the job — recorded there as an input, not tracked here.
- [x] M10-M11b: **Split out to COREDEV-2780** — the CI job, the required-vs-advisory decision,
      and the ruleset change. Q5 resolved: split.
- [x] M12: **Split out to COREDEV-2778** — the scheduled, non-blocking `markdown-link-check` job.
      It was never implementation-ready (needs its own workflow file, a schedule guard, a cadence and
      `continue-on-error`), so it is a ticket rather than a milestone of this plan.
- [x] M13: **Retired, not split.** It was the required-vs-advisory decision; that question went to
      COREDEV-2780 with the CI job, and the step that depended on it is now M11a immediately before
      M11b. The number is recorded here so the sequence has no unexplained gap.
- [x] M14: **Split out to COREDEV-2779** — zizmor reporting nothing inside a nested linked
      worktree. The cause is not established, so no mechanism, target file or acceptance test can be
      named here; the ticket carries the full four-cell isolation.
- [x] M15: **Split out to COREDEV-2780** — the CLAUDE.md gate-list update belongs with the CI job
      it must mirror.

## Verification — positive controls

A config that is not read is indistinguishable from a config that finds nothing.

**Two tiers, stated separately, because an earlier revision claimed uniformity the table did not
have.** The **eleven** rows below are **primary**: three-state (restored → mutated → restored), run
through Trunk **from the isolated clone at the plan's base** — the same tree every figure in
"Measured outcome" comes from — with a sha256 of the mutated artifact compared before and after — an equal finding count does not prove byte-identical restoration. The **two** below them are
**secondary**: two-state comparisons that establish behaviour rather than Trunk-side discovery.
Every **reachability-sensitive** config is now in the primary tier. `ruff.toml` and `.codespellrc`
both used to sit in the secondary one — their controls invoked the linter directly, or compared two
configurations, proving the tool understood the file but not that **Trunk** supplies it, which is the
exact failure class this discipline exists to catch. Both now have Trunk-mediated three-state
controls.

**Why the `.mypy.ini` control lands on 76 rather than 0.** Every other suppression row falls to zero,
so 76 survivors look like an incomplete control. They are not: `disallow_incomplete_defs` emits the
**same `no-untyped-def` code** for *partially* annotated functions, and that setting is still `True`
in the mutated state. Measured — `disallow_untyped_defs=False` alone leaves 76; setting *both* to
False gives **0**; restoring gives 1,956. The control is discriminating (1,956 → 76 is unambiguous);
the residue is a second setting sharing one error code, not a leak.

**Every mutation here is semantic — none renames a key.** That distinction is the difference between
a control and an illusion, and this table got it wrong twice before getting it right:

- The codespell control first renamed `ignore-words-list`. The count fell 2 → 0, which looked
  discriminating but was codespell *rejecting the file*. The valid mutation shrinks the list, so the
  count must **rise** (2 → 110).
- The yamllint control first renamed `empty-values`. Measured: yamllint 1.38.0 answers
  `invalid config: no such rule` and exits **255** — so its 1 → 0 → 1 was a parse error too. The valid
  mutation sets `empty-values: disable`, and the configuration parses in all three states.

Both were the same technique, and the second survived a round *after* the first was documented,
because the fix was applied to the row that prompted it rather than to every row using that technique.
The mutation column now states the technique for each row so the distinction is checkable at a glance,
and a control whose linter fails to complete is not evidence regardless of what the count does.

Primary rows were counted with, substituting the row's own linter name:

```
trunk check --all --no-fix --no-progress --color=false --cache=false --filter=LINTER
```

and the "counted diagnostic" column says which of **four** kinds of figure it is: a single rule, a
rule family, a linter total, or a **marker total** (isort emits only `fmt` markers, which Trunk does
not count as issues at all). They are not interchangeable. Only linter totals are comparable with
"Measured outcome"; marker totals are comparable with nothing there.

**Primary — three-state, through Trunk, digest-checked**

| Config / override          | Mutation                                    | Counted diagnostic   | Result           | Restored |
| -------------------------- | ------------------------------------------- | -------------------- | ---------------- | -------- |
| `.bandit`                  | append `skips: B404`                        | one rule: `bandit/B404` | 51 → **0** → 51  | sha256 ✓ |
| `.markdownlint.yaml`       | `MD013: false` → `true`                     | one rule: `markdownlint/MD013` | 0 → **15,745** → 0 | sha256 ✓ |
| `.shellcheckrc`            | `external-sources` true → false             | one rule: `shellcheck/SC1091` | 0 → **50** → 0   | sha256 ✓ |
| `.github/zizmor.yml`       | suppress the `artipacked` audit             | one rule: `zizmor/…/artipacked` | 7 → **0** → 7    | sha256 ✓ |
| `.mypy.ini`                | `disallow_untyped_defs` True → False        | one rule: `mypy/no-untyped-def` | 1,956 → **76** → 1,956 (see note) | sha256 ✓ |
| `markdown-link-check.json` | empty `ignorePatterns`                      | linter total         | 4 → **10** → 4 | sha256 ✓ |
| `.yamllint.yaml`           | `empty-values` → `disable` (config stays valid) | one rule: `yamllint/empty-values` | 1 → **0** → 1 | sha256 ✓ |
| `.isort.cfg`               | `profile=black` → `profile=google`, `force_single_line` | marker total: isort `fmt` rows | 29 → **45** → 29 | sha256 ✓ |
| gitleaks override          | remove the `environment:` block from `trunk.yaml` | linter total   | 0 → **3** → 0    | sha256 ✓ |
| `ruff.toml`                | drop `"PTH"` from `[lint] select`            | rule family: `ruff/PTH*` | 2,543 → **0** → 2,543 | sha256 ✓ |
| `.codespellrc`             | shrink `ignore-words-list` to one unused word | linter total    | 2 → **110** → 2  | sha256 ✓ |

**If the `.github/zizmor.yml` control is re-run after M8, it must not key on `artipacked`.** M8 removes
all seven, so the mutation would read 0 → 0 → 0 — non-discriminating, and indistinguishable from a
config that is not read at all. Re-key it on an audit M8 leaves in place: `template-injection` (15) or
`anonymous-definition` (6). The row above is the pre-M8 measurement.


**Secondary — two-state, or not through Trunk**

| Config / override          | Comparison                                  | Counted diagnostic   | Result           | Caveat |
| -------------------------- | ------------------------------------------- | -------------------- | ---------------- | ------ |
| trufflehog path ignore     | copy a flagged file to a non-ignored path, then delete it | one rule: `trufflehog/Lob` | ignored path **0**, non-ignored path **4** | no config mutated, so nothing to digest |
| zizmor persona override    | default `regular` → `--persona=auditor`     | linter total         | 11 → **30**      | 2-state |

`bandit/B404` = 51 is the repo-wide B404 count and reconciles with the residue breakdown (47 in
tests + 4 in production). The single-rule figures are deliberately not comparable with the per-linter
totals in "Measured outcome"; the rows marked *linter total* are.

### The three that were wrong, and why

- **markdownlint.** The old control was a probe file with a broken anchor, an undefined reference, an
  unused definition and "click here", showing MD051/052/053/059 all firing. They fire on that probe
  **with no configuration at all** — markdownlint enables them by default. It proved nothing. The
  replacement keys on `MD013`, which this config uniquely sets.
- **shellcheck.** The old control cited SC2154 going 0 → 7. But SC2154 measures **7 in both states** —
  the change came from removing the old `disable=SC2154`, not from `source-path`/`external-sources`.
  SC1091 ("not following sourced file") is the discriminating signal, and it moves 0 → 50 → 0.
- **zizmor.** There was no control at all; the 11 → 31 row proves the *persona command override*, not
  that `.github/zizmor.yml` is discovered. A separate audit-suppression control now proves discovery.
  (That row read `11 → 31` before revision 10; `31` came from the contaminated checkout and the
  isolated-clone figure is `11 → 30`.)

MD051/052/053/059 report **zero** on this repository. That remains a genuine clean result — it is just
not evidence about the config.

## Measured outcome

**Where these were measured, and why it changed.** Revisions 1-9 took their figures from the main
checkout. That was wrong twice over: it sits at `37a03c7`, one merge *behind* this plan's base, and it
carries an untracked `.github/workflows/codeql.yml` that M9 never stages. The reported `zizmor: 31`
was 29 findings from a **six**-checkout `plugin-ci.yml` plus 2 from that untracked file — including
the sole `undocumented-permissions` finding, which exists nowhere in the tracked tree.

Every figure below is re-measured in an **isolated standalone clone** at the plan's actual base,
`2631845acb661cdc4649210e6adf3c71f31f10ad`: `.git` a real directory, not nested inside the parent
repository, one workflow file, and **zero untracked files**. Both configurations were run in that same
clone, so the two columns differ only by the configuration.

```
trunk check --all --no-fix --no-progress --color=false --cache=false
```

|                                  | Baseline (16 linters) | After (20 linters) |
| -------------------------------- | --------------------- | ------------------ |
| Files checked                    | 212                   | 206                |
| Security issues                  | 588                   | **592**            |
| Lint issues                      | 4,525                 | **10,839**         |
| **Total findings**               | **5,113**             | **11,431**         |
| `fmt` markers (not issues)       | 220                   | 220                |
| mypy `note` lines (non-blocking) | 0                     | 1,380              |

Both columns reconcile **exactly** against Trunk's own headline totals (588 + 4,525 = 5,113;
592 + 10,839 = 11,431). The 212 → 206 file-count change is the new `lint.ignore` excluding
`.claude/**` and `.trunk/**`; same tree, same commit, different file set.

A note on categorisation: 588/4,525 are Trunk's headline categories. A semantic re-classification that
counts gitleaks as security gives 591/4,522 for the baseline. Only the **total** is
categorisation-independent, and only the total is used for comparison.

| Linter              | Baseline | After     |          |
| ------------------- | -------- | --------- | -------- |
| ruff                | 292      | **4,339** |          |
| shellcheck          | 3,633    | 3,641     |          |
| mypy                | —        | **2,308** |          |
| bandit              | 562      | 562       | security |
| markdownlint        | 591      | 538       |          |
| zizmor              | —        | **30**    | security |
| yamllint            | 6        | 7         |          |
| markdown-link-check | —        | 4         |          |
| codespell           | —        | 2         |          |
| trufflehog          | 26       | **0**     | security |
| gitleaks            | 3        | **0**     |          |

prettier, black, isort, shfmt and taplo produce **no findings at all** — only the 220 per-file `fmt`
markers, which Trunk does not count as issues.

### This plan is itself a lint target

M9 commits this document, and it is markdown: markdownlint and codespell both read it. So committing
it changes the numbers it reports. Measured directly — the same isolated clone, with and without this
file present:

|                    | without the plan | with the plan | delta   |
| ------------------ | ---------------- | ------------- | ------- |
| Files checked      | 206              | 207           | +1      |
| markdownlint       | 538              | 576           | **+38** |
| codespell          | 2                | 2             | 0       |
| **Total findings** | 11,431           | **11,469**    | **+38** |

Re-measured at revision 24. Earlier revisions recorded **+40**, because the document then spelled the
two fixture words — once, and later twice, taking codespell from +2 to +4 unnoticed. It no longer
reproduces them at all, so codespell's contribution is now zero and only markdownlint's remains.

Earlier revisions of this section *spelled* the two fixture words while explaining them, so the
explanation tripped the checker it describes — and a later revision spelled them a second time, taking
the contribution from two hits to four without anyone noticing. This document now refers to them
without reproducing them: they are a transposed spelling of "Read" and the past participle of
"re-tune", both deliberate near-misses living in the repo's test fixtures. That removes codespell from
the self-reference entirely rather than tracking a number this document keeps changing.

**This is a regress, and it is stated rather than solved.** Every edit to this document changes its own
contribution, so no figure written here can be exact about the tree that contains it. The measurement
above is for *this revision*, and the committed tree was never re-measured against it. **Every figure
in this section is therefore a projection, not a measurement of what was committed** — the honest
statement, now that the recount that was supposed to settle it has been cut as scaffolding.

### The "After" column is PRE-M8, and M8 changes it

Every figure above is measured before M8 lands the seven `persist-credentials: false` fixes. Those
seven are `artipacked` findings zizmor itself reports, all seven in the tracked `plugin-ci.yml`:

|                    | After (pre-M8) | After M8 (projected) |
| ------------------ | -------------- | -------------------- |
| zizmor             | 30             | **23**               |
| Security issues    | 592            | **585**              |
| **Total findings** | 11,431         | **11,424**           |

Those totals exclude this document. With it staged the same subtraction runs from 11,469, giving
**11,462** — and both figures move again if this document is edited further. The committed
configuration was not re-measured, so these stay projections.

The projection is arithmetic, not a measurement: it assumes all seven land and nothing else changes.
**M8's acceptance test does not verify it** — the pre/post `artipacked` control proves those findings
are gone, not that zizmor totals 23 or the repository totals 11,424 with no other workflow-sensitive
refutes nothing yet: the configuration was committed at `f1193ac` without a post-commit re-measure,
so these three numbers remain arithmetic. Confirming them needs a repeatable measurement, which is
COREDEV-2780's CI leg, not a hand-run recount.

### The security column, honestly

Revision 1 reported security dropping 585 → 52; that figure existed only because a withdrawn
`lint.ignore` was hiding 538 bandit findings in test directories. With bandit restored everywhere the
pre-M8 picture is **588 → 592**, and the arithmetic has to respect Trunk's own categories: **26**
trufflehog false positives leave the *security* column and 30 genuine zizmor findings enter it
(588 − 26 + 30 = 592). The 3 gitleaks false positives disappear too, but they were never in the
security column — Trunk files gitleaks under *lint*, as stated above — so they come off that side
instead. Counting all 29 against security yields 589 and is wrong. The configuration eliminated false positives and added real
coverage; on its own it did not shrink the backlog. **After M8, 588 → 585** — a small genuine
improvement, and the seven findings it removes are the highest-value output of the whole exercise.

### What the residue actually is

- **ruff 4,339** — **2,543** is the `PTH` family (`os.path` → `pathlib`), a mechanical modernisation
  backlog rather than defects; then RUF059, E702, TRY003.
- **mypy 2,308 findings** (plus 1,380 `note` lines, which Trunk reports separately as non-blocking and
  which are **not** findings) — 1,956 `no-untyped-def` and ~350 genuine type bugs: `attr-defined`,
  `union-attr`, `type-arg`, `var-annotated`, `arg-type`, `assignment`, `possibly-undefined`,
  `no-any-return`. Among them a `Match[bytes] | None` dereferenced without a None check, an assignment
  from `set.add()` (which returns None), and `module_from_spec` called with a possibly-None spec.
- **bandit 562** — 541 in the two test directories, 21 in production; none suppressed. B101 is 19 of
  them repo-wide.
- **zizmor 30** — **7 `artipacked` (medium) are the actionable ones**; the rest are 15
  template-injection, 6 anonymous-definition and 2 adhoc-packages, all auditor-persona low-confidence.
  7 + 15 + 6 + 2 = 30. (An earlier revision reported 31, adding an `undocumented-permissions` finding
  that came from the untracked `codeql.yml`.)
- **codespell 2** — both intentional near-misses in the repo's test fixtures (see the lint-target
  section, which deliberately does not reproduce the words). Codespell found **zero** genuine typos.

## The headline security finding

zizmor's 7 `artipacked` findings: all seven `actions/checkout` uses in the tracked `plugin-ci.yml`
at the plan's base (`2631845`) lack
`persist-credentials: false`, so the `GITHUB_TOKEN` stays available to everything that runs later in
the job — including the step that installs and runs a pinned third-party Claude Code CLI. (At the
pinned `actions/checkout` v7.0.1 the token is written to a separate file under `$RUNNER_TEMP` rather
than into `.git/config`, as earlier revisions of this plan said; the storage location changed, the
exposure and the `persist-credentials: false` remedy did not.) actionlint and checkov
both miss this class entirely. This is the single highest-value output of the whole exercise.

## trunk fmt is unsafe here — measured, then reverted

`trunk fmt --all` was run in this worktree off a clean `origin/main`
(`SOURCE_SHA=2631845acb661cdc4649210e6adf3c71f31f10ad`). It rewrote **191 files**
(+32,794 / -17,980). Four trees were then built from that same patch and the full `scripts/tests`
suite run against each, recording the **identity of every failing test**, not just counts.

| Tree             | files modified | unittest summary                     | unique failing tests |
| ---------------- | -------------- | ------------------------------------ | -------------------- |
| clean (control)  | 0              | **OK (skipped=1)**, 1178 tests       | 0                    |
| shell only       | 43             | FAILED - 182 failures, 4 errors      | 178                  |
| python only      | 66             | FAILED - 9 failures                  | 9                    |
| full             | 191            | FAILED - 211 failures, 5 errors      | 192                  |

(Failure *events* exceed failing *tests* because this suite uses `subTest`; both are reported.)

### Set relations — demonstrated, not inferred

Revision 1 asserted that shfmt "accounts for 182 of the 211 failures". That was arithmetic on two
counts and did not establish a partition. Comparing the actual identifier sets:

- `shell ⊆ full` — **true** (`shell - full` = 0)
- `python ⊆ full` — **true** (`python - full` = 0)
- `shell ∩ python` = **6** — the two are **not** disjoint
- `|shell ∪ python|` = 181, `|full|` = **192** — **11 tests fail only in the combined tree**

So the inclusion claim holds and the partition claim does not.

**The 11 full-only failures are UNATTRIBUTED.** Revision 2 called them "emergent", claiming a
shell x python interaction the evidence does not support. Revision 3 replaced that with an
attribution to the 82 markdown/JSON/YAML/TOML files that `full` formats and neither comparison tree
touches — which merely swapped one unproven hypothesis for another. No prettier/taplo-only tree was
run, so **neither explanation is established**. What is known: `full` modifies 191 files, the two
measured trees cover 109 of them, and 82 are unexamined. Attributing the 11 would require a
formatter-isolated tree and a per-test mapping; that work is not done and is not claimed.

The two mechanisms described below are **the mechanisms observed in sampled failures**, not a
classification of all 192. Mapping every failing test to a mechanism would need per-formatter trees
including a prettier/taplo-only tree; that is not done here.

What **is** established, and is sufficient for the decision: both measured comparison trees are
already red (note the `python` tree bundles black **and** isort, and prettier/taplo were never
isolated, so no single-formatter claim is made), `python`-only formatting breaks 9 tests on its own so "it is all shfmt" is false, and the full
tree is redder than the union of the two trees that were measured.

### Mechanism — two, both evidenced

**1. Shipped-manifest / frozen-inventory drift (dominant).** This repo ships manifests that record
per-file identity, and tests assert the live tree still matches them. Formatting changes file bytes,
so the recorded size and digest stop matching. Observed directly:

```
FAIL: test_shipped_manifest_is_the_exact_complement_of_the_tracked_tree
AssertionError: Lists differ: [...py\t1333\t4be709...] != [...py\t1221\t4be709...]
                                     ^^^^ the file-SIZE field

FAIL: test_current_tree_matches_every_frozen_destination_identity
AssertionError: Lists differ: [] != ['scripts/review-verdict.py:131: quote-kee...ted']
                                     ^^^^ a LINE-PINNED inventory entry
```

This is why python-only formatting fails at all — those tests never touch shell. The same class also
breaks the CLAUDE.md gate command
`generate-callers-exemptions.py && git diff --exit-code -- scripts/review/callers-scan-exemptions.tsv`.

**2. Mutation-anchor drift (real, but narrower than revision 1 claimed).** Files under
`scripts/tests/` read a shell script's source and perform exact-string `.replace()` on it. shfmt
rewrites those bytes: 4-space indent -> tabs, `$( { ... ; } )` -> `$({ ...; })`, case patterns
`"declare -"*r*|"typeset -"*r*` -> `... | ...`.

Revision 1 said such a drift "does not fail loudly - it silently becomes a no-op". **That was
overstated.** `with_mutation` asserts that its outer anchor occurs exactly the expected number of
times, so most anchor drift fails loudly and visibly. Only a *nested* replacement — the
`with_mutation(parse, parse.replace(...))` shape, where the inner `.replace` is unchecked — can
silently yield an unchanged mutant. The silent-no-op hazard is real but is a subset, not the
explanation for 178 failures.

### Consequence for this plan

The auto-fixable findings are **not** safely auto-fixable as configured. The formatters impose
defaults (shfmt tabs, black line-length 88, prettier prose reflow) that contradict this repo's
established style and, more importantly, invalidate content-addressed manifests that are themselves
gate-bearing.

M6a must therefore do more than pin indent width. `shfmt -i 4` was revision 1's proposed fix; it is
insufficient, because shfmt normalises AST-level constructs (case-pattern spacing, command
substitution) regardless of indentation. Any viable approach has to **regenerate the shipped
manifests as part of the same change** and re-run the full suite as the acceptance test.

**`trunk check` yes, `trunk fmt` no.** The `trunk-fmt-pre-commit` action is already
disabled in `trunk.yaml` and must stay disabled.

## The CI job is out of scope — split to COREDEV-2780

Revisions 2-5 carried a full specification for a `trunk check` job in `plugin-ci.yml`. **It is
removed from this plan.** Q5 is resolved: split.

The gate made the reason unarguable. Six distinct defects across three rounds, in that section alone:

| Round | Defect                                                                                      |
| ----- | ------------------------------------------------------------------------------------------- |
| 2     | `check-mode: popular` — not a valid value for this action                                    |
| 2     | `--upstream origin/${{ github.base_ref }}` — `base_ref` is empty on `push`                    |
| 3     | `--upstream origin/${{ github.ref_name }}` — equals HEAD, so an EMPTY diff: it would pass having checked nothing |
| 3     | `post-annotations: true` on the check job — a fork-only `workflow_run` input                  |
| 3     | a custom `--upstream` at all — the action injects one, so PRs got two                        |
| 4     | `contents: read` alone — the action passes `--github-annotate` on non-fork PRs                |

**Every one was found by reading, not by running**, because a CI job cannot be executed without
pushing a branch and watching a real workflow. That is a different activity from configuring linters,
where every claim in this plan was settled by running a command. Keeping the two together meant a
verified configuration change waited on an unverifiable one.

COREDEV-2780 owns the CI job, the required-vs-advisory decision, and the CLAUDE.md gate-list update.
It carries the six defects above and the measured constraints as inputs, so none of that work is lost.

## zizmor is inert in a worktree nested inside its own repository

Revision 2 claimed "Trunk lints no GitHub workflow inside a linked git worktree". Round 2 rejected that
as under-determined, and revision 3's replacement was **also wrong** — it said both workflow linters go
inert. Running the missing control settles it.

Separating the two variables (all cells lint the same workflow file, same config, same Trunk build):

| Cell                                                | `.git`    | zizmor | actionlint |
| --------------------------------------------------- | --------- | ------ | ---------- |
| main checkout                                       | directory | 31     | 1          |
| linked worktree **outside** the repo (`/tmp/…`)     | file      | 30     | 1          |
| **normal clone** nested at `.claude/worktrees/…`    | directory | 29     | 1          |
| **linked worktree** nested at `.claude/worktrees/…` | file      | **0**  | **1**      |

The actionlint column is a *positive control*: every cell lints a workflow carrying a deliberate
`nonexistent.context` reference, and every cell reports it — **including the failing cell**.

So the finding is narrower than either previous revision claimed:

- **Of the two linters tested, only zizmor is affected.** actionlint runs correctly in all four
  cells. The other 18 enabled linters were not tested per-cell.
- The condition needs **both** linked-ness and nesting inside the parent repo; neither alone fails.
- A second hypothesis, that this plan's own `lint.ignore: .claude/**` was matching the worktree's
  files, was tested and **refuted** — removing that rule leaves zizmor at 0.

The mechanism is **not established**, only the reproducible condition. Stated as a condition.

**Why revision 3 got this wrong**, recorded because the same mistake produced two wrong conclusions:
its actionlint evidence was confounded. The control cells carried a mutated workflow and the failing
cell did not, so actionlint's `0` there was a clean workflow correctly yielding nothing — not evidence
of inertness. A control that cannot produce a positive in the cell under test proves nothing about
that cell.

**Operationally** this still matters: `.claude/worktrees/<name>` is the mandated layout and is exactly
the failing cell, so a `trunk check` run as CLAUDE.md instructs performs **no zizmor analysis** and
says nothing about having skipped it — and zizmor is the linter that found the 7 `artipacked`
findings. actionlint is unaffected — that is the one other linter tested across all four cells. **No claim is
made about the remaining 18**; they were not measured per-cell, and the earlier assertion that
"checkov and every other linter are unaffected" went beyond the evidence. COREDEV-2779 tracks fixing or
fail-closing it, scoped to zizmor. COREDEV-2780's CI job is unaffected: GitHub Actions checks out an ordinary
repository.

## Files changed

M9 stages **thirteen** paths: the twelve configuration files below, plus this plan document. The plan
is committed with them but is not part of the digest-controlled configuration set.

Of the twelve: **five new, five modified, two unchanged-but-committed.** `.isort.cfg` and
`.trunk/.gitignore` are unchanged — this plan did not author them — but they belong to the staged set,
and earlier revisions omitted both, which is why M9's count and this inventory disagreed.

| Path                                      | Status    |
| ----------------------------------------- | --------- |
| `.trunk/trunk.yaml`                       | modified  |
| `.trunk/.gitignore`                       | unchanged |
| `.trunk/configs/.bandit`                  | **new**   |
| `.trunk/configs/.codespellrc`             | **new**   |
| `.trunk/configs/.isort.cfg`               | unchanged |
| `.trunk/configs/.markdownlint.yaml`       | modified  |
| `.trunk/configs/.mypy.ini`                | **new**   |
| `.trunk/configs/.shellcheckrc`            | modified  |
| `.trunk/configs/.yamllint.yaml`           | modified  |
| `.trunk/configs/markdown-link-check.json` | **new**   |
| `.trunk/configs/ruff.toml`                | modified  |
| `.github/zizmor.yml`                      | **new**   |

**Digest manifest.** Full SHA-256 of the exact bytes every measurement in this document was taken
against — full digests, not prefixes, because a 64-bit prefix is not an identity proof. M9 compares
the staged blobs to these; any mismatch means the committed configuration is not the measured one.

```
a213d35d7b2b2b411c6c8eb37d3be758c62381865429dc81a6d89a0e709f089f  .trunk/trunk.yaml
a3a6850a4d3873929d6296fb261801a240eaa67247f219894da802b45359fd7e  .trunk/.gitignore
8793071d20f4ac5f3c043e124b6368b9a6c1e2db1bdd388c5ec971ed24a2c040  .trunk/configs/.bandit
89016ad7c2fae90f6e0a20e64e47fa3ebd7dd331bdab2232729d9be5841ea536  .trunk/configs/.codespellrc
968e1af82279fb9bb4b6fd697ad2a83763eb6ca524403c42cf1f6f99707de619  .trunk/configs/.isort.cfg
609c2d10b047f857a41c0086fe446b134a12bfc3ce4c873136dcb2f69d9a4f2c  .trunk/configs/.markdownlint.yaml
91cd1cdb77113ed655aaa1c228179986d15bab76e53e2fce719901728435ef1b  .trunk/configs/.mypy.ini
092cbe6d47cf03d414f077caab74f6dc88c5fd711c10d62dfd73e4e60e4b7358  .trunk/configs/.shellcheckrc
b0f8d92da844b43cb2578786a84a7adfe7d9501b7f336d111c5da3a605b53584  .trunk/configs/.yamllint.yaml
2679b0d00b3fac7da6c1845f91c2c1745023919d46ae8e03d03899fa526d5f13  .trunk/configs/markdown-link-check.json
fb6be6430f6a3ff0ce94a40feee3e655fc2a9c0fc8530bbcc5df07cc4c9c2ce9  .trunk/configs/ruff.toml
13ea2a519e657e42f6acaa9d3c341115b25f0e23d445960bd34c67d1ee9f79b1  .github/zizmor.yml
```

Modified by M8, and by nothing else here: `.github/workflows/plugin-ci.yml` — **seven action inputs,
twelve added YAML lines.** Only two of the seven `actions/checkout` steps already carry a `with:`
block (lines 37 and 601); the other five need `with:` added as well, so those are two lines each.
Describing them as "seven one-line additions", as earlier revisions did, would produce five invalid
step keys if taken literally.

## Testing

- `trunk check --all` is the test; the positive-control table above is the adequacy argument.
- **Do not run `trunk fmt`** — see "trunk fmt is unsafe here". `trunk check` is the command under
  test; `trunk fmt` is out of scope for this plan until M6a.
- The full CLAUDE.md local gate is re-run before commit — not the first six commands, the whole list.
- **The whitespace gate is fail-open for staged changes, so it does not cover M8/M9 as written.**
  `git diff --check "$(git merge-base origin/main HEAD)" HEAD` compares committed history; before the
  M8/M9 commit exists, `HEAD` does not contain the staged bytes and the command passes having examined
  none of them. This matters more here than usual because `.trunk/**` is excluded from Trunk's own
  linting, so those files get no other whitespace check. Either run `git diff --cached --check` once
  the staged set is final, or commit first and run the whole gate against that immutable commit before
  pushing. Do not rely on the `HEAD`-based form alone.
- Because Trunk's own linters do not all apply inside `.claude/worktrees/*` (see the nested-worktree
  section), any `trunk check` used as evidence must state where it ran.
- `python3 scripts/validate-plan-citations.py docs/planning/COREDEV-2771_TRUNK_LINT_CONFIG_PLAN.md`
  — **known-red and qualified.** It exits 1 on every plan in this repo except COREDEV-2617's, because
  its `ENUMS` list is hardcoded to two enums only that plan declares (COREDEV-2776). The acceptance
  criterion is therefore: *exactly* the two `[enum]` problems and no others. Any third line, or any
  `[cite-*]` problem, is a real failure. Reading the exit code alone would accept a genuine citation
  defect.
- **M8's acceptance test runs the zizmor binary directly, not `trunk check`** — see M8 for the
  resolved binary path, the exact command, and the three assertions. The pre-edit control requires
  exactly seven `artipacked` findings before the fixes, so a later zero proves the audit ran rather
  than merely that the tool was quiet.

## Risks

1. **REALISED, not hypothetical — `trunk fmt` produced 211 failures + 5 errors across 192 distinct
   tests, and rotted 9 plan citations.** See the
   "trunk fmt is unsafe here" section. The run was reverted and both the worktree and the main checkout
   were verified clean against `origin/main`. The lesson generalises: "auto-fixable" is a claim the
   linter makes about itself, not about this repo. Any future formatter run gets the full suite as its
   acceptance test.
2. **Three risks moved to COREDEV-2780 with the work they belong to.** The link checker's network
   flakiness in a blocking job, the hold-the-line/base-branch bootstrap, and the runner choice are all
   properties of a CI job this plan no longer contains. They are recorded on that ticket, with the
   measured constraints, rather than left here describing something out of scope.
3. **The seven `artipacked` fixes (M8) touch a workflow this plan otherwise does not.** They are the
   only change here to `plugin-ci.yml`. Five of the seven `actions/checkout` steps have no `with:`
   block, so those need two lines each — twelve added lines in total, not seven. The risk is a
   mis-edit rather than a design question, and M8's acceptance test is structural (see Testing).

## Open questions

- Q1: ~~required check or advisory?~~ **MOVED to COREDEV-2780**, which owns the CI job that
  question is about.
- Q2: Should the `PTH` family (2,543) be scheduled as its own migration ticket, or left as ambient backlog?
- Q3: Does the annotation backlog (1,956 `no-untyped-def`) warrant its own ticket, so mypy's ~350 real
  type bugs become visible in the meantime?
- Q4: ~~Can the Lob detector be kept while suppressing the fixture noise?~~ **ANSWERED — yes.** Not
  via trufflehog's own `--exclude-paths` (which does not work through Trunk), but via Trunk's
  path-scoped `lint.ignore`. **No detector filter is disabled repository-wide** — which was the whole
  point — but the entire linter is skipped inside `scripts/tests/**` and
  `mcp/review-synthesizer/tests/**`, so all trufflehog detectors are off in those two directories.
- Q5: ~~Should the CI milestones be split out?~~ **ANSWERED — yes, split.** COREDEV-2780 owns the CI
  job, the required-vs-advisory decision and the CLAUDE.md update. M8 (the `artipacked` fixes) and M9
  (committing the configuration) stay here: they are this plan's own output, not CI wiring.

## Notes

- **COREDEV-2776** was filed while running this plan's gate: `validate-plan-citations.py` fails on 23
  of 24 plans because its `ENUMS` list is hardcoded to COREDEV-2617's two enums. This plan reports
  those 2 problems and `0 assertions`; it has no citation defects of its own. Both CLAUDE.md gate
  commands still pass, so it is not a blocker here.

- `.trunk/configs/*` files are symlinked into the workspace root during `trunk check`, but **only if the
  filename appears in that linter's `direct_configs`**. Every config filename here was checked against
  the plugin definitions before being written.
- Trunk exposes no JSON/SARIF output mode on the CLI; measurements above come from parsing
  `trunk check --no-progress --color=false` text output with a consistent method on both sides.
