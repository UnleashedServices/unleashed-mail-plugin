# COREDEV-2617 — Plugin state splits across two base directories

**Status:** Planning — draft, awaiting the dual plan-review gate
**Ticket:** `COREDEV-2617` (Epic `COREDEV-2485`) · **High** — a live defect, reproduced on this machine
**Last Updated:** 2026-07-30
**Measured against:** HEAD `5a532b1` (v2.6.4), worktree `.claude/worktrees/opus5-review`, plugin `2.6.4`

---

## 1. The defect, reproduced

Every persistent artefact the plugin writes — quality markers, logs, reviewer captures, Stop-gate state —
resolves its base directory through one expansion, duplicated verbatim in four shell libraries:

```sh
printf '%s' "${CLAUDE_PLUGIN_DATA:-${HOME:-}/.claude/unleashed-mail}"
```

`scripts/lib/paths.sh:35` · `scripts/lib/marker.sh:29` · `scripts/lib/log.sh:27` ·
`scripts/lib/context.sh:36`

**`CLAUDE_PLUGIN_DATA` is exported only to hook and MCP invocations.** Executed in an ordinary Bash-tool
shell — the one an agent, a skill, a validator or a human uses:

```
CLAUDE_PLUGIN_ROOT=<unset>
CLAUDE_PLUGIN_DATA=<unset>
```

So the *same script* writes to `~/.claude/plugins/data/unleashed-mail-<id>/` when a hook runs it and to
`~/.claude/unleashed-mail/` when anything else does. The base is chosen by **invocation path**, not by
repository, plugin or user.

## 2. The evidence — three live bases, and one repo's state disagreeing with itself

Measured on this machine, 2026-07-30:

| base | files | newest write |
|---|---|---|
| `~/.claude/plugins/data/unleashed-mail-npranson-unleashed-mail-plugin/` | **76** | 2026-07-30 12:10 |
| `~/.claude/unleashed-mail/` (the fallback) | **21** | 2026-07-17 15:58 |
| `~/.claude/plugins/data/unleashed-mail-inline/` | **1** | 2026-07-17 16:08 |

**Three**, not two — the same plugin has two install ids on one machine (`-inline` from a project-scoped
install, `-npranson-…` from the marketplace), so any scheme that derives the id must disambiguate them.

**The finding that makes this High.** The marker filename encodes a `repo_hash`, so the same repository
must have exactly one marker. `quality-marker-lint-df57b844116d.json` exists in **two** bases with
**divergent contents**:

```
hook base : {"status":"fail","kind":"lint","ts":"2026-07-13T02:22:01Z","commit":"e6f1f0ab","repo_hash":"df57b844116d"}
fallback  : {"status":"fail","kind":"lint","ts":"2026-07-16T00:43:35Z","commit":"a39790f5","repo_hash":"df57b844116d"}
```

Same repo, **different commits, three days apart**. Whichever a reader consults depends on whether the
reader happened to be a hook. This is not a theoretical race — it is the current state of the machine.

**Stop-gate state is stranded.** `.state/stop-last-blocked-*` exists in the **fallback only** (1 file);
the hook base has **zero**. The Stop gate now writes to the hook base, so the record of what it last
blocked is in a directory nothing reads any more.

**21 files are orphaned.** The fallback stopped receiving writes on 2026-07-17 — when the install was
corrected — and its contents have been invisible since.

> This defect already cost a debugging session. Concluding "no hook has fired since Jul 17" from the
> fallback directory was wrong; hooks were firing normally into the other base. That misdiagnosis is
> recorded in `precompact-hook-does-not-fire` and is what filed this ticket.

## 3. What is NOT the defect — stated so the fix does not chase the wrong thing

- **It is not drift between the four copies.** They are byte-identical and
  `scripts/tests/test_shell_primitive_drift.py:85` already gates that, with a four-environment matrix
  (`:92-95`) that specifically rejects the `${CLAUDE_PLUGIN_DATA-…}` single-dash form. That test is
  correct and stays.
- **It is not the `:-` / `${HOME:-}` details.** `scripts/lib/paths.sh:23-28` documents both and they are
  right.
- **The expansion is wrong at a level the drift test cannot see:** all four copies agree, and all four
  are wrong together whenever the variable is unset. **A consistency test over four identical wrong
  answers passes.** That is this campaign's inert-gate signature, in a new place.

## 4. Findings and fixes

### 4.1 — The fallback is silent, and silence is the defect (High)

When `CLAUDE_PLUGIN_DATA` is unset the code does not fail, warn, or record that it took the fallback. It
writes a complete, plausible, parallel store. Every downstream reader then reports confidently from
whichever half it happened to land in.

**Fix.** Whatever base is chosen (§4.2), taking the fallback must be **observable**: a one-line diagnostic
to the plugin's own log, and a field in the marker/log record naming the base that produced it. A reader
can then tell "no marker" from "marker in the other store".

**Proof — N1:** unset `CLAUDE_PLUGIN_DATA`, run a marker write, and assert the record names its base.
A build that writes the same bytes in both modes fails.

### 4.2 — The base must be derivable without the env var (High) — **the decision this plan needs**

Four candidate resolutions, with what each costs. **This plan does not pick one silently**; §8 puts it to
the reviewers, and the answer must be settled *in the gate* — not during implementation, which would
invalidate the reviewed digest (`AGENT_CONTRACTS.md:92`).

| # | approach | cost / risk |
|---|---|---|
| **A** | Derive the id from `~/.claude/plugins/installed_plugins.json` (key `unleashed-mail@<marketplace>`, confirmed present) | adds a JSON parse to a **fail-open shell hook path**; needs a `jq`/`python3` dependency the hooks currently avoid |
| **B** | Glob `~/.claude/plugins/data/unleashed-mail-*` | **ambiguous today** — two dirs match. Needs a tie-break, and picking wrong is silent |
| **C** | Keep the env var authoritative; every non-hook entry point exports it | this is the **status quo workaround**, already copy-pasted into `agents/swift-reviewer.md:168-176` and `:239-244` (MAJ-6). Proven fragile: it requires every future call site to remember |
| **D** | Keep the env var authoritative but make the fallback **loud** (§4.1) and provide **one** documented bridge helper instead of per-agent copy-paste | smallest change; does not eliminate the split, makes it visible and recoverable |

**Recommendation: D, with C's bridge consolidated into a single helper** — and A rejected for the hook
path specifically, because a fail-open hook must not depend on parsing JSON. But this is the reviewers'
call, and B's ambiguity is itself an argument that *no* derivation is safe without an explicit id.

**Proof — N2:** whichever is chosen, a test must run the same write **twice** — once with the variable
set, once unset — and assert both land in the **same** base. Today they do not, which is the defect.

### 4.3 — The four copies should delegate, not duplicate (Medium)

`scripts/lib/paths.sh:20` states the duplication is deliberate: *"this file is an optimisation of
maintenance, not a load-bearing dependency"* — each lib must work if `paths.sh` is absent.

That reasoning is sound for a fail-open hook, and **the fix must not break it.** But it means one
decision lives in four places, and §3 shows the drift test cannot catch a shared error.

**Fix.** Keep the fallback-if-absent property; add a test asserting that when `paths.sh` **is** present
all four resolve identically **to `unleashed_plugin_base()`'s answer**, not merely to each other.

**Proof — N3:** change `paths.sh`'s expansion only; the three others must fail the new test. Today they
would pass, because they are compared to each other.

### 4.4 — The 21 orphaned files need a decision, not a migration script by default (Medium)

The fallback holds 21 files, newest 2026-07-17: quality markers, one `build-log.jsonl`, and the stranded
`stop-last-blocked-*`.

**Fix.** Do **not** auto-merge. The divergent marker in §2 shows merging would have to choose between two
truthful-looking records, and choosing wrong re-poisons the gate. Options in order of preference:
**(i)** leave them and document the directory as dead; **(ii)** move them to
`~/.claude/unleashed-mail.orphaned-2617/` so the path stops resolving; **(iii)** merge newest-wins, only
if §8 Q3 says so.

**Proof — N4:** whatever is chosen, a test asserts the fallback path is not silently readable afterwards.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The fix breaks the fail-open property of hooks | **High** | §4.3 keeps the absent-`paths.sh` fallback; A is rejected for the hook path |
| A derivation picks the wrong id where two exist | **High** | §2 measured two on this machine; B is called out as ambiguous rather than assumed safe |
| The change looks correct because all four libs still agree | **High** | §3 — agreement is what hid this. N3 compares to `unleashed_plugin_base()`, not to peers |
| Auto-migration overwrites the newer of two divergent markers | Medium | §4.4 forbids auto-merge by default |
| The gate goes inert: a test that sets `CLAUDE_PLUGIN_DATA` in its fixture proves nothing | **High** | **N2 must run the unset case**, which is the only case that reproduces the defect. `scripts/test-hooks.sh:33` exports it for isolation — a test inheriting that harness cannot see this bug |

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

Baselines at `5a532b1`: `test-hooks.sh` **304**, synthesizer **222**, scripts **312**, counts
`21/21/0/1`, hook events **10**. Floors, not equalities — re-derive and print `pwd` +
`git rev-parse HEAD` beside any measurement.

Mutation proofs **N1–N4**, each shown failing before the fix and passing after.

## 7. Implementation order

1. Settle §8 Q1 (which resolution) — **in the gate**, not during implementation.
2. Make the fallback observable (§4.1) and add N1.
3. Implement the chosen resolution; add N2 with the **unset** case.
4. Add N3's delegation test, preserving the absent-`paths.sh` fallback.
5. Execute §8 Q3's decision on the 21 orphans; add N4.
6. Version bump + CHANGELOG, stating plainly that state written before this fix may live in a second
   directory and how to find it.

## 8. Open questions for the reviewers

1. **Which resolution — A, B, C or D (§4.2)?** The recommendation is D plus a single consolidated bridge
   helper. Is that too little? A eliminates the split but puts JSON parsing in a fail-open hook path.
2. **Is `CLAUDE_PLUGIN_DATA` genuinely unset outside hooks/MCP, on every surface?** Executed here for the
   Bash tool (both it and `CLAUDE_PLUGIN_ROOT` unset). Verify for: a skill's `allowed-tools` Bash grant,
   the MCP server process, and CI. If any of those *does* export it, D's blast radius shrinks.
3. **The 21 orphaned files (§4.4)** — leave, quarantine, or merge newest-wins? The divergent marker in §2
   is the argument against merging.
4. **Should the marker/log record carry its base directory** (§4.1), or is a log line enough? Adding a
   field changes a persisted record shape; check whether anything parses these.

## 9. Notes

- Every figure here was executed on 2026-07-30 against HEAD `5a532b1`: the three base directories and
  their file counts, both copies of `quality-marker-lint-df57b844116d.json`, the unset environment in a
  Bash-tool shell, and the four resolver sites.
- `scripts/lib/paths.sh` already defines the intended single primitive, `unleashed_plugin_base()`
  (`:34-36`). This ticket is not about creating it; it is about the fact that its **answer** is wrong
  outside a hook, and that three other files re-derive the same wrong answer independently.
- The `-inline` base directory is the residue of the project-scoped install described in
  `precompact-hook-does-not-fire`. It is evidence for §4.2's ambiguity argument, not a separate defect.
