# COREDEV-2642 — PR #63 remediation handoff

**PR:** #63 · branch `claude/plugin-opus5-review-xs81o0` → `main`
**State at handoff:** 28 commits pushed, **500 tests green**, all 6 CI checks green
**Last commit:** `427a916`

---

## 1. What this is

PR #63 drew **four independent reviews**: `gemini-code-assist` (2 inline), `atlassian`/Rovo (1),
`chatgpt-codex-connector` (4 inline), and a multi-agent pass over the full 90-file delta that filed
**30 gaps** (2 high / 19 medium / 9 low) plus triage of the other three reviews' 7 threads.

**27 of the 30 gaps are done**, including both Highs.

The remediation was then reviewed **twice more**: codex re-reviewed it and filed **13 P2s** (5 closed),
and **Kimi K3 at max effort** reviewed the 20-commit diff — the first look by a family other than codex
— and filed **5 findings, all closed**.

**The two families found different classes, and that is the argument for using both.** Codex found
protocol and security defects: a TOCTOU, reservation timing, a parser form, a symlinked allocator
parent. Kimi found **claims that did not hold** — four of its five were commit messages that
overstated what the commit achieved:

| Kimi finding | claimed vs actual |
|---|---|
| cleanup resumability | claimed the tool recoverable; only the FILE phase was, the directory phase still aborted |
| test guards | 8 files defined classes after `unittest.main()`; direct execution ran 13 of 43 |
| 18m→28m sweep | claimed the class swept; only `skills/` had been grepped |
| CHANGELOG note | described a permission risk closed two commits later |
| kind-binding | gap 22 said "deleted OR SKIPPED"; only deletion was closed |

Three of those five are the same error: **closing half of something and describing it as closed.**
When a finding names two things, verify both halves before writing the commit message.

## 2. Done

| | |
|---|---|
| **Gap 2** (High) | allocated leaf resurrected the previous run's `VERDICT` — `ftruncate` + wrapper refusal |
| **Gap 1** (High) | model-invocable skills held unscoped `Write`/`Edit`/`Bash` — grants scoped |
| Gap 4 + threads 3, 6 | classifier bypasses (symlink, case-mangling) skipped the freshness gate |
| Gaps 6, 10–14 + thread 4 | timeouts, pre-clean doctrine, model selection |
| Gaps 17, 20, 21, 28 | release record and contracts |
| Gaps 3, 5, 15, 16 | makedirs mode, cleanup resume/`--check`, zsh CI coverage, Design-Gate prose |
| Gaps 22–27, 29, 30 | the low sweep |
| Threads 1–3 | answered on the PR; **1 and 2 deliberately NOT applied** (see §5) |
| 2nd round | bare `<reviewer>=MISSING`; allocated reservation preflight |

## 3. Open — ranked

**Needs a fresh session (delicate):**

1. **`review-verdict.py` TOCTOU.** `_transcript_freshness_problem` validates by path, then
   `_sha256_bytes` **re-opens by path** — the leaf can be swapped between them, so the check
   validates one file and the digest records another. A correct fix threads ONE `O_NOFOLLOW`
   descriptor through `islink` → `realpath` → `_regular_file_info` → the hash. This is the
   fail-closed gate's core with 30 freshness mutation proofs around it. Not attempted at depth.
2. **Helper extraction — gaps 7–9, thread 7, AND the `implement` gate fence.** Now FIVE sites, not
   four: scoping `implement`'s grant (gap 1) left its mandatory Phase 1 Design Gate fence — which
   opens `ARG="$(cat <<'UM_IMPLEMENT_ARG_EOF'` and uses functions, `tr`, `ls` — matching no grant, so
   the one block that must run before any implementation now prompts every time. That fence is the
   HIGHEST-RISK extraction of the five: it carries the MAJ-9 quoted-heredoc argument binding and the
   physical-containment guard that has already been bypassed four different ways. Preserve both
   exactly. `scripts/review/persist-verdict.sh` EXISTS and its
   fail-closed matrix is verified. Wiring it in broke 14 tests, because the M5 proofs
   (`test_m5_path_contract.py`, `test_transcript_path_threading.py`) **extract and mutate the inline
   shell** — anchors like `transcript="${rest#*:}"`. Moving the logic deletes their anchors. The
   refactor is: recipe → one granted call, AND re-point all 14 anchors at the helper, in ONE commit.
   Attempted and reverted once; the tree was left green.

**Nothing bounded remains.** Everything left needs a proof set or a core path redesigned ALONGSIDE
the fix — attempting one without the other is how you get a half-fix with a confident commit message.

3. **`callers_scan.py:269` over-selection — MEASURED, attempted, reverted.** `ANCHORS` uses `any()`,
   so the bare `-review` anchor matches `security-reviewer`, `pr-review`, `code-review` in prose.
   Measured tree-wide:

   | anchors | candidates | real invocations |
   |---|---|---|
   | current (`/unleashed-mail:`, `-review`) | **1407** | 14 |
   | namespace only | 101 | 14 |
   | namespace + `/gemini-review`, `/codex-review` | **193** | 14 |

   **This is the blocker on item 7.** Narrowing keeps all 14 real invocations and takes the exemption
   manifest from ~1393 entries to ~179 — from "generate an enormous artifact" to something a person
   can review. Do NOT use `all()`: M5.13 mutates `any()`→`all()` and asserts the mutant is rejected,
   because `/unleashed-mail:review-synthesis` contains no `-review`. Reverted because changing
   `ANCHORS` fails **14 proof methods** across M5.13/14/15b — the whole S-CALLERS proof set, which
   encodes the current anchor semantics via an independent reference implementation.

4. **`review-verdict.py:385`** — the classifier widening means any basename ending `-<32 hex>.txt`
   takes the per-run branch, so a custom or historical transcript outside the allocator directory is
   now treated as per-run and must carry a `.launch`. Judgement call: acceptable fail-closed, or a
   regression for legacy transcripts.

**Must be LAST, before push:**

7. **`callers-scan-exemptions.tsv` is not shipped** (thread 5, confirmed). Production
   `callers_scan.py --root .` exits 2 before scanning. The manifest identity is
   `(path, FINAL line, SHA-256(payload))` and is deliberately **not** shift-stable, so it must be
   generated only after every other edit is final. An empty manifest yields **1368** rejects.
   The module states production must never derive it automatically — any generator lives outside it.

**Maintainer decision, not mine:**

8. **The gemini arm runs the model its own comment says was abandoned.**
   `scripts/review/isolated-agy-review.sh:40-46` reads:

   > Switched from gemini-3.1-pro to **gemini-3.6-flash-high** after that arm failed to emit a
   > parseable verdict in **5 of 6 rounds** (invented tokens REJECTED/PASS, two degenerations leaking
   > system-prompt tokens, two runs that implemented the plan instead of reviewing it).

   …and the next line is `MODEL="${MODEL:-gemini-3.1-pro-high}"`. Verified against ground truth:
   `agy models` lists BOTH names, so neither is invalid — the code and its rationale simply
   disagree, and every wrapper round has been running the arm documented as failing.

   **Not changed here.** Which model gates plans is a capability decision with real consequences,
   and this campaign has already shown how much model/effort choice matters (a controlled A/B on
   Kimi K3 flipped `APPROVE_WITH_NOTES` → `REQUEST_CHANGES` on byte-identical input at a higher
   effort). Either apply the documented switch, or delete the stale rationale — but decide it, do
   not let the contradiction stand. Note the current state is WASTEFUL, not unsafe: an unparseable
   verdict fails closed.

9. **Gaps 18–19.** `CHANGELOG.md` claims COREDEV-2605 and COREDEV-2617 passed their gates; the
   in-tree plans say otherwise (2605's last verdict on shipped bytes is `REQUEST_CHANGES` with the
   second arm uncounted; 2617 claims 19 rounds where the plan records 18). Correcting a release
   record to say a gate did **not** pass is a maintainer call. Left untouched.

## 4. Things that will bite you

**This repo has line-bound and content-bound frozen contracts, and they are duplicated.** Three
attempts were reverted or reworked because of them:

- `callers_scan` anchors each command block by the **sha256 of the line before and after**, and that
  data lives in BOTH production `callers_scan.py` AND `test_callers_scan.py`. Updating one leaves the
  scanner matching nothing (`preceding idx=[] following idx=[]`).
- The four `/unleashed-mail:{gemini,codex}-review` lines in `implement/SKILL.md` are **content**-frozen.
  Re-indenting them or adding an alignment space silently invalidates their digests.
- `AGENT_CONTRACTS.md` §13 pins heading anchors by line number; `validate-plugin-assembly.py` requires
  an **exact sentence** in §11.
- The M3.1 inventory re-anchors after almost any edit. Drive it from
  `test_transcript_path_inventory._tree_problems`, never a hand-rolled reimplementation — mine was
  wrong twice.

**The cheapest way through:** where possible, fix prose **without changing the line count**. Gap 16
succeeded that way (350 → 350 lines) after failing when it inserted lines.

## 5. Reviewer fixes that are WRONG as written

Three of the reviewers' proposed remedies were not applied, deliberately:

- Gemini's `continue` for deleted-but-tracked files is a **fail-open** — `rm` of a file containing a
  REJECT line would produce a green scan.
- "Restore the historical text" for the README would **re-introduce the `/tmp` literals** that
  COREDEV-2619 exists to remove, and trip the output-literal guard.
- My own first version of gap 25's guard flagged any line *containing* an invisible byte, which swept
  in every plan document that discusses CRLF/BOM. Narrowed to "only when stripping REVEALS an anchor".

**A reviewer's fix is a claim.** Verify the mechanism before applying the remedy.

## 6. Verification discipline that paid off

- **Mutation-test every new assertion.** A test that passes with the fix reverted proves nothing. One
  type-guard test here was blind — the outcome was preserved by a *different* mechanism downstream.
- **Fixture-validity assertions.** `assert the raw anchors do NOT match, or this proves nothing`
  caught two useless fixtures in a row.
- **Test where it runs.** A CI step verified under a plain shell failed under Actions'
  `bash -eo pipefail`; capture an expected failure with `|| status=$?`.
- **`Ran 1 test in 0.000s`** for a multi-test class is a loader error, not a passing suite. A non-zero
  exit is not evidence the test discriminated.
