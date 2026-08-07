# Replace the gemini review arm with Kimi K3

**Status:** Planning — **not gated, not implemented.** `COREDEV-2645` **exists** (created 2026-08-06,
`To Do`); this document was written under `COREDEV-2642` as the resolution of PR #63 review item 8.
**Last updated:** 2026-08-06 — re-baselined against the tree after `COREDEV-2642` landed changes this
plan had described as pending. Everything below now states the CURRENT tree, not the tree as it was
when the plan was drafted (PR #63 recheck, P3).

> **This plan is not part of the 2.7.0 release.** It ships as a plan only — no `COREDEV-2645` code is
> in this PR. The PR's six-ticket table covers the code; this document is the seventh entry and is
> explicitly *plan-only, not gated, not implemented*.

---

## 1. The decision, and what it replaces

The Plan Review Gate runs two arms: `gemini` (Antigravity CLI `agy`) and `codex`. The maintainer's
decision is to **replace the gemini arm with Kimi K3**.

This supersedes the contradiction PR #63 found and item 8 recorded.
`scripts/review/isolated-agy-review.sh:40-46` documents a switch away from `gemini-3.1-pro`:

> Switched from gemini-3.1-pro to **gemini-3.6-flash-high** after that arm failed to emit a parseable
> verdict in **5 of 6 rounds** (invented tokens REJECTED/PASS, two degenerations leaking system-prompt
> tokens, two runs that implemented the plan instead of reviewing it).

**That contradiction is now RESOLVED, and this paragraph is kept as the origin rather than the current
state.** When this plan was drafted the next line still read `MODEL="${MODEL:-gemini-3.1-pro-high}"`,
so every wrapper round ran the arm its own comment documented as failing. `COREDEV-2642` applied the
documented switch: the wrapper now reads `MODEL="${MODEL:-gemini-3.6-flash-high}"`.

So the case for replacing the arm no longer rests on a code/comment disagreement — that is fixed. It
rests on the measured failure record above (5 of 6 rounds unparseable, two runs that *implemented* the
plan) and on the two-review-family evidence in §2. A reader who checked the wrapper today and found
3.6 would otherwise conclude this plan's premise had evaporated.

**The current state is wasteful, not unsafe.** An unparseable verdict fails closed. That is why this
is a planned change rather than a hotfix, and why the contradiction can stand in the tree until this
plan is gated — see §7.

### Why a second family at all

PR #63 is the evidence. Codex re-reviewed the remediation and found protocol and security defects: a
TOCTOU, reservation timing, a parser form, a symlinked allocator parent. Kimi K3 reviewed the same
diff and found a different class entirely — **claims that did not hold**, four of its five being
commit messages that overstated what the commit achieved. Neither family found the other's. The gate
wants two families; the question is only which second family.

---

## 2. Ground truth about the Kimi CLI

Verified by execution on 2026-08-05, not from memory:

| Fact | Value | Source |
|---|---|---|
| Binary / version | `kimi` 0.32.0 at `~/.kimi-code/bin/kimi` | `kimi --version` |
| Non-interactive run | `-p, --prompt <prompt>` — "Run one prompt non-interactively and print the response" | `kimi --help` |
| Output format | `--output-format text\|stream-json` (default `text`) | `kimi --help` |
| Model selection | `-m, --model <alias>`; default from `default_model` in `config.toml` (currently `kimi-code/k3`) | `kimi --help`, `config.toml` |
| K3 effort tiers | `support_efforts = [ "low", "high", "max" ]`, `default_effort = "high"` | `~/.kimi-code/config.toml` |
| Effort CLI flag | **None.** `--help` exposes no effort option | `kimi --help` |
| Global effort | `[thinking] enabled = true`, `effort = "high"` | `~/.kimi-code/config.toml` |
| K3 context | `max_context_size = 1048576` | `config.toml` |
| Read-only mode | **No `-s read-only` equivalent.** Closest are `--plan` (plan mode) and the permission modes `--yolo` / `--auto` | `kimi --help` |

### Two facts that shape the design

**Effort is config-only, and the config can be migrated underneath you.**
`~/.kimi-code/migrations-effort.json` contains
`{"thinking-effort-max-to-high": "2026-08-03T10:21:31.572Z"}` — an installer migration that reset the
global thinking effort from `max` to `high` two days before this was written. Effort therefore cannot
be treated as pinned by having set it once. Both the per-model `default_effort` and the global
`[thinking] effort` must be pinned, and the harness must **assert the effort it actually ran at** and
void the round if it cannot, exactly as the freeze-label defect taught: a label naming different
content than the digest voids the round.

This matters because effort is not cosmetic here. A controlled A/B on byte-identical input found both
tiers returning five findings, overlapping on three — `high` returned `APPROVE_WITH_NOTES` with all
Lows, `max` returned `REQUEST_CHANGES` including the only High. Extra effort bought **depth, not
count**, at 2.09× output. A gate arm that silently drops to `high` still emits a parseable verdict;
it just stops finding the structural defects. That is a silent weakening, which is worse than the
current wasteful-but-fail-closed state.

**There is no sandbox flag.** `codex exec -s read-only` has no Kimi equivalent. The gemini arm needed
`scripts/review/isolated-agy-review.sh` for the same reason — it caught a reviewer that *implemented*
the plan instead of reviewing it — and that harness's git-worktree isolation, `$HOME` leak monitor and
exit-3 mutation detector must be **reused, not reinvented**, with its two known limits carried
forward: it shares the git object database (dangling commits survive) and it must demand the verdict
line FIRST or a short approving review gets summarised away.

---

## 3. Measured surface

`gemini` is not a model name in this repo — it is a **reviewer identity**. Measured over the tracked
tree (excluding `docs/planning/` and `docs/audits/`, which are historical records and must NOT be
rewritten):

| File | Occurrences | What they are |
|---|---|---|
| `skills/gemini-review/SKILL.md` | 86 | the skill itself — directory name, body, capture recipe |
| `scripts/tests/test_review_verdict.py` | 80 | artifact assertions |
| `scripts/tests/test_transcript_path_threading.py` | 58 | capture/persist proofs |
| `scripts/tests/test_m5_path_contract.py` | 56 | M5 path propagation proofs |
| `scripts/review-verdict.py` | 28 | incl. `REQUIRED_REVIEWERS = {"gemini", "codex"}` |
| `scripts/tests/test_callers_scan.py` | 21 | incl. six duplicated frozen digests |
| `scripts/review/cleanup_coredev_2619_leaks.py` | 19 | |
| `README.md` / `CHANGELOG.md` | 19 / 19 | current entries only; released entries are history |
| `scripts/tests/test_doc_gates.py` | 15 | |
| `scripts/review/isolated-agy-review.sh` | 14 | the harness itself |
| `scripts/test-hooks.sh` | 13 | |
| `skills/review-synthesis/SKILL.md` | 12 | |
| `AGENT_CONTRACTS.md` | 12 | §2 gate steps |
| `scripts/review/callers_scan.py` | 12 | incl. `PRODUCTIONS` and six `MigrationDestination` rows |
| `scripts/pty-capture.py` | 10 | |
| `skills/implement/SKILL.md` | 8 | **content-frozen** invocation lines |
| `skills/codex-review/SKILL.md` | 8 | cross-references |
| `scripts/review/persist-verdict.sh` | 8 | `GEMINI_SPEC`, `GEMINI_PERSIST_SPEC` |
| `scripts/lib/bash-write-scan.py` | 8 | |

≈450 live occurrences across ~30 tracked files.

### The four frozen contracts this crosses

Each has already caused a revert in this campaign. They are the reason this is a planned change.

1. **`callers_scan.py` `MIGRATION_DESTINATIONS`** — six rows carrying `reviewer="gemini"` plus
   `frozen_source_line`, `preceding_sha256`, `following_sha256`, and the same data is **duplicated**
   in `test_callers_scan.py`. Updating one leaves the scanner matching nothing
   (`preceding idx=[] following idx=[]`). `PRODUCTIONS` also pins the literal
   `b"/unleashed-mail:gemini-review --ticket <T> --round <N> <plan>"`.
2. **`skills/implement/SKILL.md`'s invocation lines** are **content**-frozen — re-indenting one or
   adding an alignment space silently invalidates its digest.
3. **The M3.1 inventory** (`COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json`) binds destinations by
   `(path, line, payload sha256)` and carries five `skills/gemini-review/SKILL.md` entries. Renaming
   that directory changes every `location` key AND every payload containing the old command string.
   Drive re-anchoring from `test_transcript_path_inventory._tree_problems`, **never** a hand-rolled
   reimplementation.
4. **`AGENT_CONTRACTS.md` §13** pins heading anchors by line number, and
   `validate-plugin-assembly.py` requires an exact sentence in §11.

### Collision with the exemption manifest

`scripts/review/callers-scan-exemptions.tsv` is keyed by `(path, FINAL line, SHA-256(payload))` and is
deliberately **not shift-stable**. Every rename in this plan moves lines and changes payloads, so the
manifest must be regenerated as the **last** step — after the rename, not during it.

---

## 4. Ordered work plan

Each step ends green. Do not start the next until the previous one's suite passes.

**Step 0 — ticket and worktree.** Create the `COREDEV-2645` ticket, associate it with the Epic, and
create the worktree FIRST, then this plan's gate artifacts inside it (`CLAUDE.md`'s ordering rule —
`.verdicts/` is per-directory session state and does not follow a later `git worktree add`).

**Step 1 — the harness, before any rename.** Add `scripts/review/isolated-kimi-review.sh`, modelled on
`isolated-agy-review.sh`, keeping the worktree isolation, the `$HOME` leak monitor and the exit-3
"reviewer mutated the tree" detector. Route through `scripts/pty-capture.py` as the other arms do.
Establish, with tests:
   * the effort assertion from §2 — pin per-model `default_effort` and global `[thinking] effort`, and
     **void the round** if the run cannot be shown to have used the pinned tier;
   * the verdict-line-FIRST prompt rule;
   * a timeout that exceeds the CLI's own, as `isolated-agy-review.sh` documents for `agy`.
   This step ships alongside the gemini arm and changes no identity. It is independently valuable and
   independently revertible.

**Step 2 — measure before committing.** Run both arms on the same frozen plan for at least three
rounds. The gate is non-deterministic — 2 of 3 re-runs on byte-identical input have flipped a verdict
— so a single round proves nothing. Record parseable-verdict rate and finding classes. **If Kimi's
parseable-verdict rate is not clearly better than the arm it replaces, stop here and report**: the
premise of the switch is that the gemini arm fails to emit parseable verdicts.

**Step 3 — the identity rename**, in one commit per contract family, in this order:
   1. `REQUIRED_REVIEWERS` and `review-verdict.py`, with its tests
   2. `persist-verdict.sh` (`GEMINI_SPEC` → `KIMI_SPEC`) and the two persistence recipes
   3. `skills/gemini-review/` → `skills/kimi-review/`, with `plugin.json`/README counts re-verified
      (`VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh`)
   4. `callers_scan.py` `PRODUCTIONS` + the six `MigrationDestination` rows **and** their duplicates
      in `test_callers_scan.py`, in the SAME commit
   5. the M3.1 inventory, re-anchored via `_tree_problems`
   6. `AGENT_CONTRACTS.md`, `CLAUDE.md`, `README.md`, `CHANGELOG.md` — current entries only

**Step 4 — retire the gemini arm.** Delete `isolated-agy-review.sh` and the skill, or keep it as an
opt-in third arm. Decide explicitly; do not leave both wired.

**Step 5 — regenerate `callers-scan-exemptions.tsv` LAST**, and confirm
`python3 scripts/review/callers_scan.py --root .` exits 0.

**Step 6 — full validator sweep** per `CLAUDE.md`, plus `shellcheck` on the new harness.

---

## 5. What must NOT change

* **`docs/planning/**` and `docs/audits/**`.** They record what happened. A gemini round that
  happened stays a gemini round. This is the same rule that made PR #63 correct the CHANGELOG rather
  than rewrite the plans.
* **Released `CHANGELOG.md` entries**, for the same reason.
* **The two-arm gate shape.** `REQUIRED_REVIEWERS` is a set of exactly two and both `write` and
  `verify` enforce it symmetrically. This plan swaps a member; it does not add a third.
* **`any()` in `callers_scan.is_candidate`.** M5.13 mutates it to `all()` and requires the mutant to
  disagree.

---

## 6. Risks

| Risk | Why it bites | Mitigation |
|---|---|---|
| Silent effort downgrade | An installer migration already did this once, on 2026-08-03 | assert the effort actually used; void the round otherwise (§2) |
| Half-renamed frozen contract | `callers_scan.py` and its test duplicate the same digests; updating one leaves the scanner matching nothing | rename both in one commit; `callers_scan --root .` must exit 0 |
| Manifest regenerated too early | identity is `(path, FINAL line, payload sha)` and is not shift-stable | step 5 is last, and is the only step that touches the TSV |
| Kimi is no better | the switch's premise is the parseable-verdict rate, which has not been measured across rounds | step 2 is a stop-gate, before any rename |
| Reviewer implements the plan | observed on the gemini arm; Kimi has no `-s read-only` | reuse the isolation harness in step 1, before the rename |
| Losing the codex/second-family split | the two families demonstrably find different classes | step 2 records finding classes, not just verdicts |

---

## 7. Interaction with the rest of PR #63

* **The stale rationale in `isolated-agy-review.sh` is deliberately left in place.** Rewriting the
  comment to describe a switch that is about to be superseded would be churn, and deleting it would
  erase the evidence this plan rests on. §1 above is now the resolution of record. If this plan is
  **not** gated, the fallback is the original item-8 choice: apply the documented switch, or delete
  the rationale — but do not let the contradiction stand indefinitely.
* ~~**The two capture recipes** are still compound blocks that match no `allowed-tools` grant.~~
  **DONE in `COREDEV-2642`** — both extracted: `scripts/review/capture-gemini-review.sh` and
  `scripts/review/capture-codex-review.sh` ship, each a single granted call. The advice to "fold the
  gemini one into step 1 to avoid doing the work twice" is therefore spent: step 3's rename now
  operates on an existing helper rather than on an inline block, which is strictly less work than the
  plan assumed. Step 1's scope shrinks accordingly.

---

## 8. Open questions for the gate

1. **Reviewer name.** `kimi` or `kimi-k3`? The artifact records it forever and `REQUIRED_REVIEWERS`
   is compared lowercase. Recommendation: `kimi`, matching `codex`'s tool-not-model convention —
   the model is already recorded separately.
2. **Retire or retain the gemini arm** (step 4). Retaining it as an opt-in third arm costs a
   `REQUIRED_REVIEWERS` shape change the gate currently forbids.
3. **Does `--plan` mode plus the isolation harness give enough read-only assurance**, or should the
   harness also drop write capability at the filesystem level?
