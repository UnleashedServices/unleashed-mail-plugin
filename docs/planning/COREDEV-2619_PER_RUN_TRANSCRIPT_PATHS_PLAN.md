# COREDEV-2619 — Per-run transcript paths

**Status:** Planning — **not yet gated.** Blocks `COREDEV-2497`, whose §7 step 1 requires this to land
first: once `verify` re-digests every transcript, a clobbered transcript stops being a confusing
measurement and becomes a **hard gate failure**.
**Ticket:** `COREDEV-2619` (Epic `COREDEV-2485`) · **High** — a live defect, reproduced twice on this
machine, once destructively.
**Measured against:** HEAD `51f6050` (v2.6.6), worktree `.claude/worktrees/opus5-review`.
**Last Updated:** 2026-07-31 (initial draft, pre-gate)

---

## 1. The defect, reproduced

The shipped review recipes write every transcript to a **fixed, shared, world-readable path** —
`/tmp/agy-out.txt` and `/tmp/codex-out.txt`. Every review of every plan, in every project, on this
machine, writes to those two names.

**Reproduced, twice, both times on this campaign:**

1. **Cross-project clobber (COREDEV-2497 round 2).** A round-1 codex transcript was measured at
   769,988 bytes from `/tmp/codex-out.txt`. By the time it was read, that file held **a different
   project's plan review** — 628 occurrences of `lumawake`, **zero** of `COREDEV-2497`. Another
   project's gate round had overwritten the shared path between the run and the read. The headline
   measurement of a gate round was taken from the wrong file, and the error was then "corrected" in the
   wrong direction before anyone noticed.
2. **Destructive loss under disk pressure.** With all transcripts under `/tmp`, macOS purged
   `/private/tmp` when the root volume filled and destroyed **105 captured transcripts** of this
   campaign between two tool calls. Two rounds' findings were lost unread.

**A third hazard is documented in the code but not in the recipes.** `scripts/pty-capture.py:314-320`
notes that "the recipes use predictable `/tmp` paths, so a pre-created symlink or a 0644 file is a local
hazard" — another user can pre-seed `/tmp/agy-out.txt` as a symlink and redirect a capture that may quote
message bodies or tokens. The wrapper already defends itself with `O_NOFOLLOW` + mode `0600`; the
**predictability** it is defending against is what this ticket removes.

## 2. Why now — 2497 turns a confusion into a failure

Today a clobbered transcript produces a *wrong measurement*: a human reads the wrong bytes and may not
notice. After `COREDEV-2497` §4.1 lands, `verify` **re-digests every transcript recorded in an approving
artifact**. A transcript overwritten between capture and verification then fails its digest check, and
the gate fails closed — correctly, but with a diagnosis ("digest mismatch") that points at the reviewer
rather than at the collision that actually caused it.

**So the ordering is not stylistic.** 2619 removes the collision while it is still merely confusing.
Landing 2497 first converts a latent measurement bug into an intermittent, misattributed gate failure.

## 3. Guiding principle, and the ceiling

**Principle: a capture's path must be unique to the run that produced it.** Not unique per plan, per
ticket or per day — per *run*, because the reproduced defect is two runs sharing one name.

**Ceiling — what this ticket does NOT do.** It does not make a transcript tamper-proof, and it is not a
security boundary. Anyone who can write the transcript directory can write a transcript; `2497` is what
detects a *changed* transcript, and `2618` is what cross-checks the verdict token inside it. This ticket
removes an **accidental** collision, and with it the predictability that makes the symlink hazard cheap.

## 4. Findings and fixes

### 4.1 — The path scheme (High)

**Fix.** Captures go to a per-run path under a durable, private directory:

```
~/.claude/review-transcripts/<ticket>r<round>-<reviewer>.txt
```

with `<out>.captureid` beside it, exactly as today.

Three properties, each load-bearing:

- **Durable, not `/tmp`.** `/tmp` is purged under disk pressure — that is finding 1's second
  reproduction, and it destroyed 105 transcripts. `~/.claude/` is not swept by the OS.
- **Named for the round.** `2497r11b-codex.txt` cannot be clobbered by `2605r8-codex.txt`, and a human
  reading a finding three rounds later can still open the exact file it came from.
- **Private.** `pty-capture.py` already forces `0600`; the directory is created `0700`.

**This is already the campaign's operational practice** — every transcript since the `/tmp` purge has
been captured this way. The defect is that **the shipped skills still document `/tmp`**: the plugin
teaches a recipe its own maintainers abandoned after losing two rounds of findings to it. A consumer
following `skills/gemini-review/SKILL.md` today gets the clobber and the purge.

**Proof — M1:** point two concurrent captures at the same ticket/round and assert the second is refused
rather than silently overwriting. **M2:** capture, then re-run the *same* command, and assert the
`.captureid` changes — proving the second run is a new capture and not a stale read.

### 4.2 — The `allowed-tools` grants break SILENTLY (High)

Two skills carry a **literal-prefix** permission grant:

| skill | grant |
|---|---|
| `skills/codex-review/SKILL.md:7` | `Bash(rm -f /tmp/codex-out.txt*)` |
| `skills/gemini-review/SKILL.md:8` | `Bash(rm -f /tmp/agy-out.txt*)` |

`allowed-tools` is a **pre-approval grant matched by literal prefix**. Change the path and the grant no
longer matches — the cleanup is no longer pre-approved, so mid-gate the run either prompts or is denied,
**depending on the consumer's permission mode**. Nothing fails loudly; a gate round stalls or silently
skips its pre-clean, and a *stale previous transcript* is then read as this round's verdict. That is the
exact failure mode `isolated-agy-review.sh:88-89` pre-cleans against ("a stale previous-round transcript
would be read as THIS round's verdict").

**Fix.** The grants move to the new prefix in the *same commit* as the paths:
`Bash(rm -f ${HOME}/.claude/review-transcripts/*)`. If placeholder expansion is not available in
`allowed-tools`, the pre-clean moves **into `pty-capture.py`** (which already pre-cleans `out_path` and
`out_path.captureid`) and the grant is dropped entirely — one mechanism, no literal path in a permission
string.

> **This is the item a naive migration misses.** Every other site is a path in prose or a command;
> these two are *permission* strings, and a mismatch there is invisible until a consumer hits it in a
> mode this repo's own CI never runs.

**Proof — M3:** rewrite the paths and **leave the grants** — assert the drift check flags the mismatch.
**M4:** rewrite both and assert no literal `/tmp/` path remains in any `allowed-tools` line.

### 4.3 — The measured site inventory (Medium)

**23 sites across 7 files**, measured at `51f6050` — not the "20 sites / 6 files" carried in the campaign
notes, which was an estimate:

| file | sites | lines | classification |
|---|---|---|---|
| `skills/gemini-review/SKILL.md` | 6 | `:8` `:24` `:71` `:137` `:197` `:199` | 1 **grant** (`:8`), 5 rewrite |
| `skills/codex-review/SKILL.md` | 5 | `:7` `:48` `:49` `:51` `:181` | 1 **grant** (`:7`), 4 rewrite |
| `skills/review-synthesis/SKILL.md` | 5 | `:23` `:24` `:38` `:137` `:138` | 5 rewrite |
| `skills/brainstorm/SKILL.md` | 2 | `:194` `:195` | 2 rewrite |
| `scripts/pty-capture.py` | 3 | `:27` `:31` `:317` | 2 rewrite (docstring examples), 1 **quote-keep** (`:317`, the symlink-hazard comment names the predictable path it defends against) |
| `scripts/review-verdict.py` | 1 | `:129` | 1 **quote-keep** |
| `scripts/tests/test_review_verdict.py` | 1 | `:146` | 1 **quote-keep** |

**Totals: 23 sites, 7 files — 2 grants, 18 rewrites, 3 quote-keeps.**

**Not every site is a rewrite.** `review-verdict.py:129` and `test_review_verdict.py:146` *quote the
historical defect* — `gemini=APPROVE:/tmp/agy-out.txt` recorded for **both** reviewers, the copy-paste
slip that once produced a GATE OK backed by one review. `pty-capture.py:317` names the predictable path
its `O_NOFOLLOW` defence exists for. Rewriting any of the three would corrupt the record of a real
finding or the rationale for live code. **Each site is classified before it is touched** — `rewrite`,
`quote-keep`, or `grant` — and the inventory is part of the change.

> *(The first draft of this table was wrong in three rows — it asserted 5/4/3 where the measured values
> are 6/5/1, having been written from an earlier partial grep. The totals happened to agree at 23, which
> is exactly how a wrong breakdown survives review. Every figure above is now `grep -n` output.)*

**Proof — M5:** a drift check asserts that no `/tmp/agy-out` or `/tmp/codex-out` literal survives
**outside** the sites classified `quote-keep`, and that the `quote-keep` set is exactly the enumerated
one. A new literal added anywhere else fails it.

### 4.4 — What already defends against a collision, and must keep working (Medium)

Two mechanisms exist and this change must not weaken either:

- **`review-verdict.py`'s distinct-evidence check.** Recording the *same* transcript for both reviewers
  (`gemini=APPROVE:/tmp/agy-out.txt` + `codex=APPROVE:/tmp/agy-out.txt` — one copy-paste slip in the
  documented two-file flow) once produced a **GATE OK in which one review backed both approvals**. Every
  prior check passed because they compared *labels*.
- **`.captureid`.** A per-run random ID written beside the transcript, used as content-independent proof
  that two reviewers were two separate wrapper runs.

Per-run paths make the copy-paste slip *harder*, not impossible — the operator still types both paths.
**Neither check may be relaxed on the grounds that paths are now distinct.**

**Proof — M6:** record the same per-run transcript for both reviewers and assert the distinct-evidence
check still fails the gate.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The `allowed-tools` grants are missed, and consumers stall mid-gate | **High** | §4.2 + M3/M4; the grants move in the same commit as the paths |
| A historical quote is "fixed" and the record of a real defect is corrupted | **High** | §4.3's per-site classification; M5 pins the `quote-keep` set |
| Per-run paths are read as making the gate tamper-proof | Medium | §3's ceiling, in the CHANGELOG |
| The directory is created world-readable | Medium | `0700` dir + `pty-capture.py`'s existing `0600` files; assert both |
| Transcripts accumulate without bound | Low | out of scope, stated: this ticket does not add retention. A follow-up may |

## 6. Verification

```bash
python3 scripts/validate-plugin-assembly.py --root . --strict
python3 scripts/validate-hooks.py --root . --strict --require-manifest
VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh
bash scripts/test-hooks.sh
python3 -m unittest discover -s mcp/review-synthesizer/tests
python3 -m unittest discover -s scripts/tests
shellcheck -s bash -S warning scripts/*.sh scripts/lib/*.sh scripts/review/*.sh .githooks/pre-commit
```

Baselines at `51f6050`: `test-hooks.sh` **304**, synthesizer **227**, scripts **324**, counts
`21/21/0/1`, hook events **10**. Floors, not equalities.

Mutation proofs **M1–M6**, each shown failing before the fix and passing after.

## 7. Implementation order

1. **Inventory and classify all 23 sites** (`rewrite` / `quote-keep` / `grant`) and commit the
   classification — M5 asserts it, so it is an artifact, not a note.
2. **Move the path scheme** into `pty-capture.py`'s documented recipes and the four skills, and create
   the directory `0700`. Add M1/M2.
3. **Move the two `allowed-tools` grants in the SAME commit**, or delete them by moving the pre-clean
   into the wrapper. Add M3/M4.
4. Add the drift check (M5) so a future `/tmp/agy-out.txt` cannot reappear unclassified.
5. Assert §4.4's two existing defences still fail their defects (M6).
6. Version bump + CHANGELOG — state the **ceiling** (§3): per-run paths remove an accidental collision;
   they do not make a transcript tamper-proof, and `COREDEV-2497` is what detects a changed one.

## 8. Open questions for the reviewers

1. **Does `allowed-tools` expand `${HOME}` or `${CLAUDE_PLUGIN_ROOT}`?** If not, §4.2's fallback (move
   the pre-clean into `pty-capture.py`, drop the grant) is the only correct option and should be the
   primary. **This is the question most likely to change the design.**
2. **Is `~/.claude/review-transcripts/` the right home**, or should transcripts live under the plugin
   data dir now that `COREDEV-2617` has made that resolve-or-refuse? The data dir is unresolved outside
   a hook — which is exactly when reviews run — so this plan assumes `~/.claude/`. Confirm.
3. **Should the round be in the filename or a directory?** `2497r11b-codex.txt` vs
   `2497/r11b/codex.txt`. The flat form is what the campaign has used for 100+ transcripts; the nested
   form sorts better at scale.
4. **Is any of the 23 sites misclassified** — in particular, are the two "historical quote" sites really
   quotes, or are they live examples a consumer would copy?
