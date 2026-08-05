# COREDEV-2642 — PR #63 remediation handoff

**PR:** #63 · branch `claude/plugin-opus5-review-xs81o0` → `main`
**State at handoff:** 38 commits, **529 tests green**, `callers_scan --root .` exits 0,
full validator sweep clean
**Last commit:** `9666d50`

> **Second pass, 2026-08-05.** Everything §3 listed as open is now closed except **the gemini
> capture recipe** (§3) — see §2b. The two maintainer decisions were made: the gemini arm is to be
> **replaced by Kimi K3** (planned in `KIMI_REVIEW_ARM_PLAN.md`, deliberately not implemented), and
> the CHANGELOG's two false gate claims are corrected.

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

## 2b. Closed in the second pass (2026-08-05)

| was | closed by |
|---|---|
| **1. `review-verdict.py` TOCTOU** | `_regular_file_info` returns the digest read from the SAME `O_NOFOLLOW` descriptor it fstat'd; freshness hands back a `_VerifiedTranscript(path, sha256)` the caller records instead of re-resolving the name. Proved by swapping the leaf at the instant validation reads the descriptor's metadata — an fstat trigger, not a close trigger, so a re-open placed between fstat and return cannot sail past it. Both places the re-open can creep back are mutated. |
| **3. `callers_scan` over-selection** | anchors narrowed to `/unleashed-mail:`, `gemini-review`, `codex-review`. 1409 candidates -> 294. Measured all four options first; the `/`-prefixed variant is smaller but stops selecting `unleashed-mail:gemini-review …` and bare `gemini-review --ticket …`, which ARE invocation spellings, so it narrows past the defect. Proved a STRICT SUBSET that retains every exact production. |
| **4. classifier judgement call** | accepted as fail-closed, with the reasoning in the docstring: conditioning the filename branch on the directory would let an allocated transcript COPIED out of the layout skip the check entirely. |
| **7. exemption manifest** | shipped, generated last (302 records at this writing; the count moves with any edit to a scanned file, which is the point). `scripts/review/generate-callers-exemptions.py` is a maintainer tool outside the module. CI ran only `--help`, which loads no manifest — it now runs `--root .`. |
| **8. gemini arm** | maintainer decision: **replace with Kimi K3**. `docs/planning/KIMI_REVIEW_ARM_PLAN.md` — measured surface, verified CLI facts, ordered steps with a stop-gate before any rename. Not implemented; needs its own ticket and the plan gate. |
| **9. gaps 18-19** | both CHANGELOG entries corrected to match their plans. |
| **2. helper extraction** | **4 of 5 sites.** Only the gemini capture recipe is left — see below. |

## 3. Open — ranked

**1. The gemini CAPTURE recipe** (`skills/gemini-review/SKILL.md`) — the LAST of the five extraction
sites. Still a compound block (`: "${TICKET:?…}"` guards, an `if`/`else` around the allocator, a `case`
on the marker), so it matches no `allowed-tools` grant and still prompts. The other four are done:
`review-synthesis` and `brainstorm` call `persist-verdict.sh`, `implement`'s Phase 1 fence calls
`resolve-plan-gate.sh`, and codex's capture calls `capture-codex-review.sh`.

**Do it inside `KIMI_REVIEW_ARM_PLAN.md` step 1, not before.** That plan replaces the whole arm, so
extracting the recipe now and renaming it in step 3 is the same work twice.

The pattern is in this branch twice over. Move the logic to a script; stage that script in the
fixtures (`install_capture_helper` / `stage_plugin_root` in `test_transcript_path_threading.py`) and
re-point each mutation anchor at whichever layer now owns its rule, naming the layer explicitly rather
than inferring it from the reviewer. Expect M5.1/M5.2/M5.7/M5.9 to move, plus M5.14 in
`test_callers_scan.py` and the M3.1 destinations.

Two things the codex extraction learned that will recur:

- **The M3.1 manifest now has an optional `destination.path`**, added because two codex destinations
  moved to a different FILE and the schema had only one `path` serving as both source and destination.
  Use it. The alternatives are pointing a destination at a line that merely MENTIONS the rule — a
  contract check passing on prose — or deleting the site and editing the frozen counts, which loses the
  record that the rewrite happened.
- **S-PRECLEAN rejects a destination region containing `rm -f`, including inside a comment forbidding
  it.** That is the guard working. Put the retry/re-allocate rule above the allocation rather than
  beside the capture, and the region stays clean.

**Nothing else is open.** Everything below in §4-§6 still applies and has been extended.

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

Added in the second pass:

- **Check that a mutant is not a no-op.** Probing the shipped-manifest test, one of my three mutations
  was `backup.replace(b"\t116\t", …)` on a file containing no `\t116\t`. It rewrote nothing, the test
  passed, and I nearly recorded the test as blind. `assert mutated != backup` before drawing any
  conclusion — a mutation proof and its own probe are both code, and the probe is not privileged.
- **A frozen line number in a test asserts the file's layout, not the property.** Three broke here
  when unrelated edits shifted lines (`assertEqual(169, …)`, `source_start = 119`, the §13 anchor).
  Where the subject can be found by search, find it by search and assert the derivation against the
  tree; keep the frozen form only where the freeze is itself the contract.
- **`git add -A` is not safe in this repo.** It staged 17 untracked reviewer scratch files, and two
  reached a generated manifest before anyone noticed. The `.gitignore` already recorded this happening
  once before with different names — both times the globs had been narrowed by the second word
  (`.agy-prompt*`), and both times a new suffix escaped. They are keyed by TOOL prefix now
  (`.agy-*.md`, `.codex-*.md`, `.kimi-*.md`). The commit that staged them was rewritten out before the
  branch was pushed, so no scratch file is in history — which is only cheap because it was caught
  while the commits were still local. Past that point the choice is between a force-push and living
  with it.
- **When a check has a cheap mode and a real mode, CI must run the real one.** `callers_scan --help`
  was green for the whole of PR #63 while `--root .` exited 2. A smoke test that loads no input
  proves the file parses, nothing more.
