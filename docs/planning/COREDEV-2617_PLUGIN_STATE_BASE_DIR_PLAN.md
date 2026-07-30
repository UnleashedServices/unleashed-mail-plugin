# COREDEV-2617 — Plugin state splits across two base directories

**Status:** Planning — **round 2 gated** (**gemini REQUEST_CHANGES ×2 / codex REQUEST_CHANGES ×3**). The
reviewers **split on the resolution** — gemini for the A+D hybrid, codex for D′ — and **D′ is adopted**;
see §11. N1 contradicted D′ and is rewritten; an empty base would have redirected writes to filesystem
root; the consumer enumeration is now in the implementation order. Round 1 is in §10. Awaiting round 3.
**Ticket:** `COREDEV-2617` (Epic `COREDEV-2485`) · **High** — a live defect, reproduced on this machine
**Last Updated:** 2026-07-30 (round 2, post-gate revision)
**Measured against:** HEAD `1485c54` (v2.6.4), worktree `.claude/worktrees/opus5-review`, plugin `2.6.4`

---

## 1. The defect, reproduced

Every persistent artefact the plugin writes — quality markers, logs, reviewer captures, Stop-gate state —
resolves its base directory through one expansion, which appears in four shell libraries:

```sh
printf '%s' "${CLAUDE_PLUGIN_DATA:-${HOME:-}/.claude/unleashed-mail}"
```

`scripts/lib/paths.sh:35` · `scripts/lib/marker.sh:29` · `scripts/lib/log.sh:27` ·
`scripts/lib/context.sh:36`

> **Round 1 correction — these are NOT four independent copies.** `marker.sh`, `log.sh` and `context.sh`
> each **source `paths.sh` and delegate** to `unleashed_plugin_base()`, keeping the literal expansion
> only as a fallback for when `paths.sh` cannot be located (`marker.sh:21-30`). Existing tests already
> cover both arrangements — `test_matrix_with_paths_sh_present` and `test_matrix_with_paths_sh_ABSENT`
> (`scripts/tests/test_shell_primitive_drift.py:122`, `:129`). The defect is **not** duplication. It is
> that the single shared answer is wrong whenever the variable is unset.

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

**Three bases**, from two data-directory names plus the legacy fallback. *(Rounds 1-2: the draft
attributed `-inline` to a project-scoped install — **withdrawn**, its provenance is unknown. And the live
registry holds exactly **one active** id, so "two install ids" overstates it: `-inline` is residue, not a
second active install. Its existence still matters for §4.2's ambiguity argument.)*

**The finding that makes this High.** The marker filename encodes a `repo_hash`, so the same repository
must have exactly one marker. `quality-marker-lint-df57b844116d.json` exists in **two** bases with
**divergent contents**:

```
hook base : {"status":"fail","kind":"lint","ts":"2026-07-13T02:22:01Z","commit":"e6f1f0ab","repo_hash":"df57b844116d"}
fallback  : {"status":"fail","kind":"lint","ts":"2026-07-16T00:43:35Z","commit":"a39790f5","repo_hash":"df57b844116d"}
```

Same repo, **different commits, three days apart**. Whichever a reader consults depends on whether the
reader happened to be a hook. This is not a theoretical race — it is the current state of the machine.

**A legacy Stop sentinel is orphaned.** `.state/stop-last-blocked-*` exists in the **fallback only**
(1 file); the hook base has **zero**.

> **Round 1 correction — this is weaker evidence than the draft claimed.** The orphan is the *legacy
> unsuffixed* form. The current gate reads only **session-suffixed** sentinels
> (`scripts/stop-quality-marker-gate.sh:64`), and the unsuffixed name is retained only for cleanup
> compatibility (`scripts/lib/marker.sh:141`). It would **not** become readable if moved to the active
> base. It is evidence of a *legacy orphan*, not of current Stop-gate partitioning. The divergent
> marker above remains the load-bearing evidence.

**21 files are orphaned.** The fallback stopped receiving writes on 2026-07-17 — when the install was
corrected — and its contents have been invisible since.

> This defect already cost a debugging session. Concluding "no hook has fired since Jul 17" from the
> fallback directory was wrong; hooks were firing normally into the other base. That misdiagnosis is
> recorded in `precompact-hook-does-not-fire` and is what filed this ticket.

## 3. What is NOT the defect — stated so the fix does not chase the wrong thing

- **It is not drift, and it is not duplication.** The three consumers delegate to `paths.sh` and keep the
  literal expansion only as an absent-file fallback (§1). `scripts/tests/test_shell_primitive_drift.py:85`
  gates the two forms across a four-environment matrix (`:92-95`) and specifically rejects the
  `${CLAUDE_PLUGIN_DATA-…}` single-dash form. That test is correct and stays.
- **It is not the `:-` / `${HOME:-}` details.** `scripts/lib/paths.sh:23-28` documents both and they are
  right.
- **The expansion is wrong at a level the drift test cannot see:** every site agrees, and every site is
  wrong together whenever the variable is unset. **A consistency test over identical wrong answers
  passes** — confirmed in round 1, where the drift test's fixed expected fallback (`:85`) passed while
  execution demonstrated the split. That is this campaign's inert-gate signature, in a new place.

## 4. Findings and fixes

### 4.1 — The fallback is silent, and silence is the defect (High)

When `CLAUDE_PLUGIN_DATA` is unset the code does not fail, warn, or record that it took the fallback. It
writes a complete, plausible, parallel store. Every downstream reader then reports confidently from
whichever half it happened to land in.

**Fix.** Whatever base is chosen (§4.2), taking the fallback must be **observable**: a one-line
diagnostic to the plugin's own log, and a field in the marker/log record naming **which resolution ran**.

> **Round 1: do NOT record the base directory itself.** Marker and log records are explicitly PII-free
> (`scripts/lib/marker.sh:7`, `scripts/lib/log.sh:7`; `context.sh` hashes the repo root for the same
> reason). An absolute base path contains the username and home directory. Record an **enum** —
> `host-env` / `derived-registry` / `legacy-fallback` — never the path. Extra marker fields are
> parser-safe (the reader selects named keys, `marker.sh:150`).
>
> And note the limit: a diagnostic written *into the wrong store* cannot tell a reader looking in the
> other one that it exists. The enum makes a found record self-describing; it does not make a missing
> one discoverable. Cross-store diagnostics are still needed.

**Proof — N1 (rewritten in round 2, because it contradicted D′).** N1 previously required an *unset*
invocation to **write a marker** naming its resolution — but D′ requires that same invocation to persist
**nothing**, and a "diagnostic to the plugin's own log" is itself forbidden persistence. The two could
not both hold. Restated:

- **Set:** the write lands **only** in the supplied host base, carrying `base_resolution=host-env`.
- **Unset or empty:** **no reads and no writes anywhere** — no legacy path, no root-derived path — the
  hook exits **fail-open**, and the diagnostic is **bounded and non-persistent** (stderr, not the log).
- Exercise **marker, log and context** paths, not a single marker write.

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

**ROUND 1 FINDING: no listed option satisfied N2, and D contradicted it outright.** §1 requires the base
to work without the variable; D admits it does not eliminate the split; N2 then demands set and unset
writes land together. Those three cannot all hold. Making the fallback *loud* does not make it
*correct*, and a bridge helper cannot reach an ordinary shell, CI, or a git hook unless each one calls
it — and `scripts/pre-commit-checks.sh:14` is the concrete counterexample that already writes
unreachable markers by default.

**Two corrections to this section's own reasoning, from round 1:**

- **A was rejected too quickly.** "A fail-open hook must not parse JSON" is overstated: *hooks already
  have the variable*, so a registry lookup would only ever run on the **fallback** path, where the
  alternative is being wrong. A is also **not ambiguous today** — the live registry holds exactly one
  active `unleashed-mail` key.
- **A and B both ignore supported relocation.** Neither accounts for `CLAUDE_CONFIG_DIR` or
  `CLAUDE_CODE_PLUGIN_CACHE_DIR`, both of which move the plugin registry and data roots. Any derivation
  must define precedence for both, plus missing/corrupt registries, `--plugin-dir`, and multiple active
  ids. **B remains genuinely ambiguous** — two `unleashed-mail-*` directories match on this filesystem.

**Revised resolution — D′, or an A+D hybrid.** D is the right *authority* boundary only if amended so
that an **unset variable yields no persistent read or write at all**, plus an observable diagnostic and
one explicit bridge. Then N2 becomes satisfiable and is restated:

> **N2 (revised):** with the variable **set**, a write lands in the host base. With it **unset**, the
> write lands **nowhere** and is diagnosed on stderr.

**DECIDED IN ROUND 2 — D′, over gemini's dissent.** gemini argued for the A+D hybrid because D′ would
stop `scripts/pre-commit-checks.sh` writing markers. codex's counter is decisive and is adopted: those
git-hook writes are **already documented as unreachable no-ops** (`scripts/pre-commit-checks.sh:14`), so
suppressing them removes nothing that works, while the hybrid imports registry/`CLAUDE_CONFIG_DIR`/
cache-root/`--plugin-dir` ambiguity in exchange for a contract that is not currently functioning.
`CLAUDE_PLUGIN_DATA` stays the only authoritative identity.

> **An empty base is NOT a safe "nowhere" — round 2 caught this.** With the present composition it
> redirects writes to **filesystem root**: `marker_dir` → `/.state` (`scripts/lib/marker.sh:33`),
> `log_dir` → `/logs` (`scripts/lib/log.sh:31`), context → `/.state` or `/reviews/…`
> (`scripts/lib/context.sh:39`). The Stop gate also builds and writes its own log directly
> (`scripts/stop-quality-marker-gate.sh:131`). D′ must therefore **refuse at the call site**, not return
> an empty string.

### 4.3 — The four copies should delegate, not duplicate (Medium)

`scripts/lib/paths.sh:20` states the duplication is deliberate: *"this file is an optimisation of
maintenance, not a load-bearing dependency"* — each lib must work if `paths.sh` is absent.

That reasoning is sound for a fail-open hook, and **the fix must not break it.** But it means one
decision lives in four places, and §3 shows the drift test cannot catch a shared error.

**RETRACTED IN ROUND 1 — the premise was wrong.** The three libs already delegate (see §1's correction),
and `test_matrix_with_paths_sh_present` / `_ABSENT` already cover both arrangements. N3 as drafted was a
**tautology**: change `paths.sh` and the delegating callers change with it, so a test comparing them to
`unleashed_plugin_base()` passes by construction.

**What remains worth doing.** The real risk is that a future edit *breaks* delegation in one lib and
leaves its inline fallback behind — which the existing matrix would not distinguish, because both arms
return the same string today.

**N3 (revised):** in one library, **bypass or remove the delegation** and inject a sentinel
`unleashed_plugin_base` that returns a distinctive value; that library must then **fail** a test
asserting it delegates when `paths.sh` is present. Keep the existing absent-file matrix unchanged so the
fail-open property is preserved.

### 4.4 — The 21 orphaned files need a decision, not a migration script by default (Medium)

The fallback holds 21 files, newest 2026-07-17: quality markers, one `build-log.jsonl`, and the stranded
`stop-last-blocked-*`.

**DECIDED IN ROUND 1 — QUARANTINE, after the resolver fix.** Both reviewers agreed independently, and
both rejected merging: the divergent marker means newest-wins must choose between two truthful-looking
records, and `build-log.jsonl` overlaps in both stores. Leaving them in place conflicts with N4 while the
fallback path still resolves.

**So:** move the 21 files to `~/.claude/unleashed-mail.orphaned-2617/` **after** §4.2's resolver lands,
preserving an **inventory and checksums** so nothing is lost. The one-file `-inline` residue needs its
own explicit disposition in the same step — round 1 noted the draft left it undecided.

**Proof — N4:** after quarantine, a test asserts the fallback path is not silently readable.

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

1. Settle §8 Q1 (**D′ or the A+D hybrid**) — **in the gate**, not during implementation. Round 1
   established that no *original* option satisfied N2.
2. Make the fallback observable (§4.1) and add N1.
3. Implement the chosen resolution; add N2 with the **unset** case.
4. Add N3's delegation test, preserving the absent-`paths.sh` fallback.
5. **Enumerate and guard every consumer** before quarantine — round 2 found §9 claims they are
   enumerated while §7 never acts on them:
   - markers: `swift-lint-check.sh`, `pre-commit-checks.sh`, `stop-quality-marker-gate.sh`
   - logs: `swift-build-verify.sh`, `build-failure-log.sh`, `stop-failure-log.sh`,
     `permission-denied-log.sh`, plus the Stop gate's direct log (`:131`)
   - context: PreCompact, SessionStart, both capture hooks, `reviewer-roster.sh`, both agent Bash blocks
   - docs/tests: README, `.gitignore`, pre-commit comments, the resolver matrix, hook/roster fixtures
6. Quarantine the 21 orphans with inventory and checksums, and quarantine the one `-inline` file
   **separately** with its own inventory — its provenance is unknown, so it must not be merged with the
   rest. Add N4.
7. Version bump + CHANGELOG, stating plainly that state written before this fix may live in a second
   directory and how to find it.

## 8. Open questions for the reviewers

1. ~~D′ or the A+D hybrid?~~ **ANSWERED in round 2 — D′.** The reviewers split; codex's argument is
   adopted (see §4.2). The maintainer may still overrule: D′ makes non-hook invocations
   **non-persistent**, which is a visible behaviour change even though the writes it suppresses are
   already unreachable.
2. ~~Is `CLAUDE_PLUGIN_DATA` unset outside hooks/MCP on every surface?~~ **ANSWERED in round 1 — yes.**
   Plain shell: both unset. An `allowed-tools` Bash grant does **not** export them; hooks and MCP/LSP
   subprocesses do receive them. CI has no global value — `test-hooks.sh:33` and
   `test_reviewer_roster.py:41` set it explicitly.
3. ~~Leave, quarantine, or merge the 21 orphans?~~ **ANSWERED in round 1 — QUARANTINE**, with inventory
   and checksums, after the resolver lands. See §4.4.
4. ~~Should the record carry its base directory?~~ **ANSWERED in round 1 — NO, an enum instead.** The
   raw path would leak the username into records documented as PII-free. See §4.1.

**New open question for round 2:**

5. ~~Is N2 (revised) right?~~ **ANSWERED in round 2 — direction yes, coverage no.** It now also requires
   marker, log **and** context paths, a non-persistent stderr diagnostic, and refusal at the call site
   rather than an empty base. See §4.1's N1 and §4.2.

**New open question for round 3:**

6. **Does D′ need an escape hatch?** With D′, a developer running a hook script by hand gets no
   persistence at all. Should `CLAUDE_PLUGIN_DATA` simply be documented as required for manual runs, or
   should there be an explicit opt-in (e.g. `UNLEASHED_ALLOW_LEGACY_BASE=1`) for local debugging?

## 9. Notes

- Every figure here was executed on 2026-07-30 against HEAD `5a532b1`: the three base directories and
  their file counts, both copies of `quality-marker-lint-df57b844116d.json`, the unset environment in a
  Bash-tool shell, and the four resolver sites.
- `scripts/lib/paths.sh` already defines the intended single primitive, `unleashed_plugin_base()`
  (`:34-36`). This ticket is not about creating it; it is about the fact that its **answer** is wrong
  outside a hook, and that three other files re-derive the same wrong answer independently.
- The `-inline` base directory is the residue of the project-scoped install described in
  `precompact-hook-does-not-fire`. It is evidence for §4.2's ambiguity argument, not a separate defect.

## 10. Round-1 gate outcome

**gemini `APPROVE_WITH_NOTES` · codex `REQUEST_CHANGES` (6 findings).** Frozen at
`fc35834f5a1161c30a0c18d7ecbb7deb761d4a42`, plan sha256 `b645ac0b…`; both reviewers re-verified the
digest and codex confirmed no file changed. Transcripts: `/tmp/rev/2617r1-agy.txt` (3,280 B,
`TREE=clean`) and `/tmp/rev/2617r1-codex.txt` (347,116 B, 37 ticket-key occurrences).

**The evidence survived independent reproduction.** Both reviewers re-measured the four expansion sites,
the three bases (**76 / 21 / 1**), the unset environment, and — critically — **the divergent marker**,
byte for byte: hook `e6f1f0ab`, fallback `a39790f5`, three days apart. codex additionally confirmed both
commits exist in the same app repository. The drift test was confirmed blind to it.

**But codex corrected three claims this draft made, and all three corrections held.**

| # | finding | verified | fix |
|---|---|---|---|
| 1 | **D contradicts N2.** §1 requires the base to work without the variable, §4.2 admits D does not eliminate the split, N2 demands set/unset writes land together. **No listed option satisfied N2** | **confirmed** — all four resolvers executed | §4.2 rewritten around **D′** (unset ⇒ persist nothing, diagnosed) or an **A+D hybrid**; N2 restated |
| 2 | **A was rejected too quickly, and A/B ignore relocation.** Hooks already hold the variable, so a registry lookup would run only on the fallback path; and neither A nor B accounts for `CLAUDE_CONFIG_DIR` or `CLAUDE_CODE_PLUGIN_CACHE_DIR` | **confirmed** — one active registry key; B genuinely ambiguous | §4.2 states the precedence rules any derivation must define |
| 3 | **The three libs already delegate** to `unleashed_plugin_base()`; N3 was a tautology | **confirmed** — `marker.sh:21-30`, and `test_matrix_with_paths_sh_present`/`_ABSENT` already cover it | §4.3 **retracted**; N3 revised to bypass delegation and inject a sentinel |
| 4 | **Recording the raw base leaks PII** into records documented as PII-free | **confirmed** — `marker.sh:7`, `log.sh:7` | record an **enum**, never the path |
| 5 | **The Stop sentinel is legacy unsuffixed state**, not live stranded state — the current gate reads only session-suffixed names | **confirmed** — `stop-quality-marker-gate.sh:64`, `marker.sh:141` | §2 relabels it; the divergent marker remains the load-bearing evidence |
| 6 | **Consumer scope incomplete** — the git pre-commit producer, `reviewer-roster.sh`, the two agent bridges, stale README/.gitignore docs, the `-inline` residue. Production Python does *not* derive the base independently | **confirmed** — `capture-reviewer-verdict.sh:44` computes it and passes it to Python at `:62` | enumerated; `-inline` given its own disposition; the `-inline` provenance claim withdrawn |

**gemini approved a plan containing an internal contradiction** (§4.2's D versus N2) while confirming
every measurement correctly. It also contributed the one finding codex framed differently — that
`scripts/pre-commit-checks.sh` is a git hook running entirely outside Claude Code's environment, and
therefore always takes the fallback. Both reviewers landed on **quarantine** for the 21 orphans, and
codex added the inventory-and-checksums requirement.

**Round 1 also answered §8 Q2, Q3 and Q4 outright**, leaving the resolution choice (Q1) and the revised
N2 (Q5) for round 2.

## 11. Round-2 gate outcome

**gemini `REQUEST_CHANGES` (2) · codex `REQUEST_CHANGES` (3).** Frozen at `1485c54d…`, sha256
`d984c782…`. Transcripts: `/tmp/rev/2617r2-agy.txt` (1,725 B, `TREE=clean`) and
`/tmp/rev/2617r2-codex.txt` (248,242 B).

**The reviewers split on the central decision, and this is the resolution.** gemini chose the **A+D
hybrid**, reasoning that D′ would break `scripts/pre-commit-checks.sh`, a git hook that runs outside
Claude Code and relies on the fallback. codex chose **D′**, and its counter is decisive: those writes are
**already documented as unreachable no-ops** at `pre-commit-checks.sh:14`, so suppressing them removes
nothing that functions — while the hybrid imports registry, `CLAUDE_CONFIG_DIR`, cache-root and
`--plugin-dir` ambiguity to preserve a contract that does not currently work. **D′ is adopted**, and §8
Q1 records that the maintainer may overrule, since D′ is a visible behaviour change.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **N1 contradicted D′** — N1 required an unset invocation to write a marker, D′ requires it to persist nothing, and the "diagnostic to the plugin's own log" is itself forbidden persistence | **confirmed** | N1 rewritten: stderr diagnostic, no persistence, and marker/log/context all exercised |
| 2 | codex | **an empty base is not "nowhere"** — it redirects to filesystem root (`/.state`, `/logs`, `/reviews/…`), and the Stop gate writes its own log directly | **confirmed** — `marker.sh:33`, `log.sh:31`, `context.sh:39`, `stop-quality-marker-gate.sh:131` | D′ must **refuse at the call site**, never return an empty string |
| 3 | codex | the consumer enumeration was claimed in §9 but **never acted on** in §7 | **confirmed** | §7 gains an explicit enumerate-and-guard step listing every marker, log, context and doc/test consumer |
| 4 | codex | retracted claims still active — "two install ids", "three libraries re-derive independently", the `-inline` provenance, and the deferred `-inline` disposition | **confirmed** | all corrected; the `-inline` file is quarantined **separately**, with its own inventory |
| 5 | codex | **N3 is a real mutation** — verified by execution, with the caveat that the sentinel must be injected *after* `paths.sh` is marked loaded | **confirmed** | noted in §4.3 |

**Evidence re-reproduced:** counts `76 / 21 / 1`; both marker bodies matching `e6f1f0ab` and `a39790f5`;
legacy sentinel `0 / 1`. One measurement moved — the active base's newest write is now later than the
recorded `12:10`, because this very session keeps writing to it. That does not weaken the divergent
marker, and it is recorded rather than quietly refreshed.
