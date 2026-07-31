# COREDEV-2617 — Plugin state splits across two base directories

**Status:** Planning — **round 12: FIRST DOUBLE APPROVAL (gemini `APPROVE` + codex `APPROVE_WITH_NOTES`) — AND IT DID NOT REPRODUCE.** Re-run at the **byte-identical** digest: gemini flipped to `REQUEST_CHANGES` and **found a real defect the approving run had certified clean** — five executable consumers (three log hooks, both capture hooks) had **no unresolved-base control flow at all**, sitting in a bullet list while step 5 demands one per consumer. All five are now table rows; the bullet list is **non-executable sites** only. codex held `APPROVE_WITH_NOTES` across both runs. **The maintainer's reproduce-at-the-same-digest rule paid for itself.** See §21. Previously — **round 11 gated: codex `APPROVE_WITH_NOTES` (1 Low) for the SECOND round running; gemini FAILED to emit a verdict line for the second round running — NOT A PASS.** codex traced all four directed checks clean: consumer scope complete, the mutator rule naming only real mutators, the envelope oracle holding for both new consumers, and N5 narrowed consistently through step 7. The one Low was terminology — `sessionstart-restore.sh` reads and deletes the snapshot, it does not write it. **gemini's failure is a CAPTURE failure, not a review failure** (a ~1 KB summary claiming it printed a critique it did not); both failures are on this ticket, the one where its answer is affirmative. See §20. Previously — **round 10 gated: codex `APPROVE_WITH_NOTES` (1 Low), gemini FAILED (no verdict line) — NOT A PASS.** The round-9 narrowing **held**: codex traced every production read back to an envelope return, found the envelope exhaustive and the `_UNLEASHED_BASE_OK` protocol correct, and raised only the CHANGELOG omission. gemini's arm wrote its critique to a file instead of stdout, so it must be re-run; its findings were triaged anyway and two were real — **there are no `context_snapshot*` writers** (that phrase is struck) and **`precompact-snapshot.sh`/`sessionstart-restore.sh` were absent from the consumer table** (both added). See §19. Previously — **round 9 gated** (**gemini `REQUEST_CHANGES` 5 High · codex `REQUEST_CHANGES` 1 High**). **Fourth consecutive round with a failed proof mechanism, so the claim is NARROWED rather than patched a fifth time.** codex **executed** a bypass with no lexical expansion at all (`n=CLAUDE_PLUGIN_; n="${n}DATA"; printenv "$n"`), proving path provenance is **not statically decidable in Bash**: N5 is now stated as a **lexical drift detector**, explicitly not a proof of accessor-only provenance — the §3.1 move from COREDEV-2497. The oracle asserts on the envelope's **printed return values** (readers' locals are invisible; `_context_round_advance` composes inline as a `python3` argv), and the one-diagnostic-per-process rule is guarded by the shared `_UNLEASHED_BASE_OK` flag so it holds with `paths.sh` absent. Two gemini Highs **rejected with reasons**. See §18. Previously — **round 8 gated** (**gemini `REQUEST_CHANGES` 5 High + 1 Medium · codex `REQUEST_CHANGES` 2 High**). **Round 7 rejected the canary as physically impossible; round 8 rejects its replacement as mechanically impossible** — a Bash shim cannot observe `read < "$path"` (the shell opens before the command runs) or pathname globbing. The oracle now asserts on the **composed path**, which is observable, and leans on the sentinel's executed `ENOTDIR` physics for the rest. **N5 is inverted from a shape blacklist to an enumerated allowlist** — both reviewers bypassed the round-7 predicate in one line each, and round 7's mutant used the one form it already caught. `_context_round_sweep` was missing from **both** the reader and mutator lists. See §17. Previously — **round 7 gated** (**gemini `REQUEST_CHANGES` 1 High + 1 Medium · codex
`REQUEST_CHANGES` 1 High + 2 Medium**). **Round 6's sentinel holds; the two proofs built on it did not.**
The planted canary was **physically impossible** — nothing can be created beneath `/dev/null`, so the
`ENOTDIR` property that makes the sentinel safe also makes the canary unplantable — and N5 was a
**spelling** check the tree already bypasses at `scripts/test-hooks.sh:446`. §7 now uses a mandatory
**instrumented read spy** (call count zero, adequacy proved by a non-zero count with the guard removed)
and an N5 predicate built on **path composition**, not on one expansion form. The envelope also called a
**reader** (`marker_commit`) a writer and omitted `context_review_round_bind`, which prints a round even
when its write fails. See §16. Previously — round 6 gated (**gemini `REQUEST_CHANGES` ×2 · codex
`REQUEST_CHANGES` 2 High, 1 Medium, 1 Low**). Round 5's per-primitive guard
was the **round-3 defect one layer down**: in Bash a primitive that "returns nothing" returns the **empty
string**, and the caller's own concatenation still composes a root path (`/logs`, `/reviews/<hash>`,
`mktemp /.stopgate.XXXXXX`). §7 now returns a **poisoned non-root sentinel**
(`/dev/null/unresolved-plugin-base`, `ENOTDIR` for everything beneath it) from path-returning primitives
and makes the writers **no-ops** — safe for an *unguarded* caller, which is the only property that
survives future code. Previously — round 5 gated: **"guard at
script entry" does not hold D′**: the state libraries are *sourced* and have no entry, so `marker_*`,
`log_*` and `context_*` still compose root paths for any caller — §7 guarded inside each **public
primitive** off a single validated cached base, and N1/N2 must call those primitives directly. The
`swift-reviewer.md` fence finally gets its control flow, and §13's round-4 digest was the round-3 value
copied forward. **Round 4's approving codex verdict did not reproduce on identical bytes — see §13's
retraction.** Previously — round 4 gated: **codex `APPROVE_WITH_NOTES` (no High/Medium)**, gemini
`REQUEST_CHANGES` on §7's consumer table, which was missing the **destructive** sites
(`mktemp`/`mv -f` on root-derived paths) and the pre-commit **pass** cases. Both now closed; the locked
decisions are closed out. See §13. Previously — round 3 gated (**gemini REQUEST_CHANGES ×1 / codex REQUEST_CHANGES ×5**).
Both confirm **D′** and no escape hatch, but "refuse at the call site" is **unsafe in Bash** — an empty
substitution still composes a root path. §4.2 and §7 now specify per-consumer control flow. See §12.
Previously — round 2 gated (**gemini REQUEST_CHANGES ×2 / codex REQUEST_CHANGES ×3**). The
reviewers **split on the resolution** — gemini for the A+D hybrid, codex for D′ — and **D′ is adopted**;
see §11. N1 contradicted D′ and is rewritten; an empty base would have redirected writes to filesystem
root; the consumer enumeration is now in the implementation order. Rounds 1-12 are in §10-§21.
**Ticket:** `COREDEV-2617` (Epic `COREDEV-2485`) · **High** — a live defect, reproduced on this machine
**Last Updated:** 2026-07-31 (round 12, post-gate revision — five consumers tabled after the reproduction flip)
**Measured against:** HEAD `b2496a8` (v2.6.4), worktree `.claude/worktrees/opus5-review`, plugin `2.6.4`

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

> **Round 3: this section's fix text is scoped to the SET case.** D′ means an *unset* variable persists
> nothing at all — so there is no record to carry an enum and no plugin-log diagnostic to write. The enum
> below applies when the base **resolves**; when it does not, the only output is the bounded stderr
> diagnostic N1 requires. Round 3 caught §4.1 still requiring a plugin-log diagnostic and
> derived/legacy enums that D′ makes unreachable.
>
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
> (`scripts/stop-quality-marker-gate.sh:131`).
>
> **Round 3: "refuse at the call site" does NOT fix this in Bash, and the round-2 wording was unsafe.**
> Returning non-zero from inside `$(marker_base)` does not halt the caller unless `set -e` is active —
> and `scripts/stop-quality-marker-gate.sh:18` uses `set -uo pipefail`, **without** `-e`. Executed:
> with a resolver that returns 1, `LOGDIR="$(marker_base)/logs"` still evaluates to **`/logs`** and the
> script continues. `marker.sh:34` composes `"$(marker_base)/.state"` the same way.
>
> **So D′ must be enforced at every CONSUMER, not only at the resolver.** Each call site must test for
> an empty/failed base **before composing any path**, and skip persistence rather than write. §7 lists
> them, with the control-flow requirement for each.

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
asserting it delegates when `paths.sh` is present.

> **Round 6 High — "keep the absent-file matrix unchanged" contradicts D′, and N3 was not sound.**
> Earlier drafts ended the paragraph above with *"keep the existing absent-file matrix unchanged so the
> fail-open property is preserved."* That cannot stand. The matrix
> (`scripts/tests/test_shell_primitive_drift.py:92`, and `:129` for the absent case) **explicitly expects
> the legacy base for both the unset and the empty variable** — the exact answer D′ forbids. And in
> absent-`paths.sh` mode the three libraries take their **inline** branches (`marker.sh:21`,
> `log.sh:19`, `context.sh:28`), which **bypass the cache §7 assigns to `paths.sh`** entirely. So the one
> supported mode where the accessor does not exist is precisely the mode with no guard.
>
> **The resolution:** the inline fallback is **not** exempt. Each library's inline branch must implement
> the *same* unresolved contract as the accessor — an unset or empty variable yields the poisoned
> sentinel (§7), never the legacy base — so `paths.sh`'s absence changes *who computes* the answer, never
> *what the answer is*. `paths.sh:20`'s "optimisation of maintenance, not a load-bearing dependency"
> survives intact; what does not survive is the matrix's expectation.
>
> **This plan therefore mandates a test change**, stated here so it is not discovered during
> implementation: `test_shell_primitive_drift.py`'s matrix rows for **unset** and **empty** must expect
> the **unresolved/no-persistence** result in *both* the present and absent arms (`:92`, `:129`). The
> `set` rows are unchanged. **N1/N2 must run the full cross-product** — `paths.sh` present *and* absent ×
> variable set, unset and empty — six cells, not two.

> **Load order is part of the mutation, not an implementation detail.** The sentinel must be injected
> **after** `_UNLEASHED_PATHS_SH_LOADED=1` is set, or sourcing `paths.sh` overwrites it and the mutation
> silently does not apply — reproduced by codex in round 3. §11 said this was noted here; it was not.

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

**Proof — N4 (strengthened in round 3):** asserting only that the fallback is unreadable is satisfied
the moment D′'s guards land, **even if the quarantine never happens**. So N4 must also prove the move
occurred safely: every source file **absent** from the old location, each quarantine directory holding
the **exact inventory**, and **every checksum matching**. The `-inline` file is quarantined separately
with its own inventory.

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

Mutation proofs **N1–N5**, each shown failing before the fix and passing after. *(Round 7: this list
said N1–N4, so N5 — the one purely structural check in the set, with no behavioural counterpart —
carried no adversarial mutant and could have shipped unproven. Its mutant is specified in §7 step 5.)*

## 7. Implementation order

1. **D′ is settled** (rounds 2-3, both reviewers; §8 Q1). Do **not** re-open it during implementation.
2. Make the fallback observable (§4.1) and add N1.
3. Implement the chosen resolution; add N2 with the **unset** case.
4. Add N3's delegation test, preserving the absent-`paths.sh` fallback.
5. **Enumerate and guard every consumer** before quarantine, each with its **required control flow** —
   round 2 found §9 claiming they were enumerated while §7 never acted on them, and round 3 established
   that suppressing persistence must not change any consumer's primary behaviour:

   | consumer | on an unresolved base |
   |---|---|
   | `pre-commit-checks.sh` (`:44`, `:69`) | skip the marker write; **must not** bypass its final `EXIT_CODE` (`:192`) |
   | `swift-lint-check.sh` (`:425`) | skip persistence; **still emit** the model-visible block |
   | `swift-build-verify.sh` (`:65-66`) | skip the log; **still emit** the advisory |
   | `reviewer-roster.sh` (`:33`, `:53`, `:256`) | deliberately **fail-closed** — classify reviewers `UNATTRIBUTED` and exit **3**, never fail open |
   | `stop-quality-marker-gate.sh` — **`:66`, `:74`, `:75`, `:117`, `:120`, `:123`, `:131-132`** | **the destructive ones.** `:66` composes `SENTINEL="$(marker_dir)/…"`; `:120` runs `mktemp "$(marker_dir)/.stopgate.XXXXXX"`; `:123` runs `mv -f "$_STMP" "$SENTINEL"`. On an unresolved base these **create and move files under `/.state/`**. Round 3 guarded only `:131-132`. Guard the whole script at entry |
   | `pre-commit-checks.sh` — **`:47` and `:72` too** | round 3 listed only the **fail** cases (`:44`, `:69`); the **pass** cases were unguarded, so a *successful* run wrote to a root path |
   | `swift-lint-check.sh` — **`:67` too** | the early syntax-error exit writes a marker before `:425` is reached |
   | `reviewer-roster.sh:53` | `BASE="$(context_reviews_dir)/…"` composes `/reviews/…` and passes it to `context_latest_round_dir` (`:180`) — a root-directory **read** |
   | `agents/swift-reviewer.md:247-249` | **perform no filesystem read at all** and emit the existing `NO CAPTURE (unresolved)` result for **each** reviewer — the fence composes the path *and reads through it*, so "compose nothing" is not by itself a complete instruction. *(Rounds 3 and 4 both left this row restating that no control flow was supplied; round 5 supplies it.)* |
   | `build-failure-log.sh` (`:40`) · `stop-failure-log.sh` (`:36`) · `permission-denied-log.sh` (`:40`) | **round 12 — these three had no control flow at all.** Each calls `log_append` exactly once as its terminal action. On an unresolved base `log_append` is a **no-op returning 0** (§7's writing-primitive rule), so the hook's own behaviour is unchanged: it still exits 0 and still emits whatever the hook contract requires. **No per-script guard is needed or wanted** — adding one would duplicate the primitive's contract. Stated explicitly because "the primitive handles it" is a decision, not an omission |
   | `capture-reviewer-round-start.sh` (`:46`) | calls `context_review_round_bind`, whose unresolved contract is **print nothing, return 0**. The call site already discards stdout and forces success (`>/dev/null 2>&1 \|\| true`), so the hook is unaffected. **Fail-open**: a missing round binding degrades to inference, which is the documented fallback |
   | `capture-reviewer-verdict.sh` (`:45`, `:62`) | composes `ROOT="$(context_reviews_dir)"` — a **sentinel** path when unresolved. **Skip the capture entirely and exit 0**; do **not** attempt the write, and do not fail the reviewer's own run. `capture.py` composes only beneath this `ROOT`, so it is covered transitively (codex, round 11) |
   | `precompact-snapshot.sh` (`:61`) · `sessionstart-restore.sh` (`:30`) | **round 10 — both were entirely absent from this table.** Each composes `SNAP="$(context_snapshot_path)"` and writes/reads the snapshot inline. On an unresolved base: **skip the snapshot write and the restore**, and leave every other behaviour (the hook's own output, its exit code) untouched |
   | `scripts/test-hooks.sh` — **`:624`, `:796`**, and **`:446`** | the harness itself calls `context_snapshot_path`. N1/N2 must run with the variable **unset**, so **the test that verifies D′ could compose root paths**. Guard before the fixtures run. *(Round 7 adds `:446` — `[ -s "$CLAUDE_PLUGIN_DATA/logs/stop-gate.log" ]` composes from the raw variable directly, not through a resolver, so it is a third site of a different kind and the one that proves N5's old predicate was blind.)* |
   | `swift-reviewer.md:247` and the roster's `:53` | both **append to the resolver result** — an empty result composes a root path |

   > **Round 5 supersedes "guard at script entry" — entry alone cannot hold D′.** Round 4 was right that
   > a per-line table is the wrong shape (round 3's named six of fourteen sites and missed every
   > destructive one), but "at entry" does not reach the code that actually composes the paths. The state
   > libraries are **sourced standalone** (`scripts/lib/paths.sh:12-16`) and **have no script entry**;
   > their public primitives compose before writing — `marker.sh:33-34,117-127`, `log.sh:31-32,42-58`,
   > `context.sh:39,54-55,190-191,267-286`. An entry check in one script does nothing for a *different*
   > script that sources the library later, and nothing for a `marker_write` added next month.
   > Entry-only early exits are also **wrong** for `pre-commit-checks.sh`, `swift-lint-check.sh`,
   > `swift-build-verify.sh` and `reviewer-roster.sh`, whose primary behaviour must continue.
   >
   > **Round 6 correction — "return nothing" is the round-3 defect one layer down, and is REJECTED.**
   > Round 5 said each primitive should return its "no-persistence result … and compose nothing." In Bash
   > a primitive is invoked as `$(marker_dir)`, so returning nothing returns the **empty string**, and the
   > caller's own concatenation still composes a **root** path. Every site round 5 claimed to protect is
   > still live: `stop-quality-marker-gate.sh:66` → `/stop-last-blocked-…`, `:120` →
   > `mktemp /.stopgate.XXXXXX`, `:132` → `/logs`, `context.sh:54` → `/reviews/<hash>`,
   > `reviewer-roster.sh:53` → `/<slug>`. This is exactly what round 3 established about call sites —
   > **an empty substitution composes a root path** — and it does not stop being true because the empty
   > string now originates one function deeper. A design that requires every caller to test for empty
   > before appending has not removed call-site enforcement; it has hidden it.
   >
   > **The mechanism must be safe for an UNGUARDED caller, because that is the only property that
   > survives future code.** Two rules, and the first is what makes it work:
   >
   > 1. **Path-returning primitives return a POISONED, non-empty, non-root sentinel** — the literal
   >    `/dev/null/unresolved-plugin-base`. `/dev/null` is a character device, so **every** path built
   >    beneath it is `ENOTDIR`: `mkdir -p` fails, `mktemp` fails, `mv -f` fails, `printf > …` fails,
   >    `[ -f … ]` is false, and a read yields nothing. An unguarded caller that concatenates and writes
   >    therefore fails **harmlessly and loudly at a fixed, greppable path**, and can never touch `/`.
   >    This holds for `marker_base`, `marker_dir`, `context_base`, `context_reviews_dir` and every
   >    derived form, including callers not yet written.
   >
   >    **Executed on this machine, 2026-07-31** — not argued:
   >
   >    ```
   >    $ mkdir -p /dev/null/unresolved-plugin-base/logs
   >    mkdir: /dev/null: Not a directory
   >    $ mktemp /dev/null/unresolved-plugin-base/.stopgate.XXXXXX
   >    mktemp: mkstemp failed on …/.stopgate.BOauuq: Not a directory
   >    $ printf 'x' > /dev/null/unresolved-plugin-base/m.json
   >    not a directory: /dev/null/unresolved-plugin-base/m.json
   >    $ [ -f /dev/null/unresolved-plugin-base/m.json ] ; echo $?      # 1 — false
   >    $ ls -d /logs /reviews /.state 2>/dev/null | wc -l              # 0 — nothing at root
   >    ```
   >
   >    The contrast that makes this load-bearing: with an **empty** base the same concatenation yields
   >    **`/logs`**; with the sentinel it yields `/dev/null/unresolved-plugin-base/logs`. Every
   >    destructive verb — `mkdir`, `mktemp`, redirect — fails `ENOTDIR`, and the `[ -f ]` guard that
   >    fail-open code already uses returns false, so readers take their existing absent-file path.
   > 2. **Writing primitives become no-ops** — `marker_write`, `log_append`, **`context_review_round_bind`** (`context.sh:263-291`) and
   >    **`context_review_round_clear`** (`context.sh:342-345`) return success **without** writing, so D′
   >    persists nothing and no consumer's primary behaviour changes. Readers return an empty result set.
   >
   >    **Round 7 — `marker_commit` is a READER and is struck from this list.** Round 6 said so in prose
   >    four paragraphs below and then left it standing in the operative rule; this is the same
   >    design-section-not-operative-section defect the plan has now hit three times.
   >    `marker_commit` (`marker.sh:179`) is `marker_field "$1" commit` — the line directly under
   >    `marker_status`, and `marker_field` (`:151`) only reads. It takes the **reader** contract (empty
   >    result), not the no-op-write contract. Calling a reader a writer is what let the two genuine
   >    round-binding mutators above go unlisted for two rounds.
   >
   >    **`context_review_round_bind` needs a stated contract, not just "skip the write".** It writes the
   >    binding *and prints the round on the way out*: `printf '%s' "$round"` (`context.sh:290`) executes
   >    unconditionally, **after** the `mv` arm has already failed. Under the sentinel `mkdir -p` and the
   >    redirect both fail `ENOTDIR`, the `rm -f` cleanup arm runs — and the function still prints a
   >    round number that was never stored, so a consumer binds to a round no reader can ever confirm.
   >    That is a fresh instance of the round-6 lesson (a value that survives a failed write is as bad as
   >    the write): its unresolved contract is **print nothing, return 0**, matching the empty result its
   >    reader half `context_review_round_lookup` (`:298`) already returns. `context_review_round_clear`
   >    is a bare `rm -f` (`:342-345`) — a no-op under the sentinel by construction, but it is a **state
   >    mutator**, so N1/N2 must assert that explicitly instead of inheriting it from `ENOTDIR`.
   >
   >    **There are no `context_snapshot*` WRITERS — round 10, and this rule named them for three rounds.**
   >    `context.sh` contains exactly one `context_snapshot*` function, `context_snapshot_path` (`:55`),
   >    and it is a **path builder**, not a writer. The snapshot writes happen **inline in the consumer
   >    scripts** — `precompact-snapshot.sh` **writes** it (`:61` composes, `:70-72` writes via tmp+`mv`)
   >    while `sessionstart-restore.sh` **reads and deletes** it (`:30` composes, `:31` `[ -f ]`, `:83`
   >    `rm -f`); neither is a library writer. *(Round 12, codex — terminology, not a mechanism gap: the
   >    round-11 wording called both consumers writers. The operative consumer table already said "write"
   >    and "restore" respectively and is correct.)* So `context_snapshot_path` belongs to the **path-returning envelope**
   >    (where it already is), and the *writes* are consumer control flow governed by §7 step 5's table —
   >    **which never listed those two scripts.** Both are added there. *(This is the third time this plan
   >    has named a non-existent or mis-typed primitive in the operative rule: `marker_commit` the reader
   >    in rounds 5-7, then the two round-binding mutators, now these. Every entry in an envelope must be
   >    opened and read before it is written down.)*
   >
   >    **`_context_round_sweep` (`context.sh:205`) is a mutator too — round 8, and it was missed twice.**
   >    It ends in `rm -f "$f"` (`:216`), deleting expired binding files. Round 7 added the two
   >    `context_review_round_*` functions on exactly the principle that a mutator must be asserted
   >    explicitly rather than inherit safety from `ENOTDIR` — and then left the third one, in the same
   >    file, unlisted. It is also a **reader** (see the coverage list below), which is presumably why it
   >    fell between the two lists. Same contract: under an unresolved base it does nothing and returns 0.
   >
   > **The envelope must be EXHAUSTIVE, and round 5's list was not.** It named `marker_commit`, which only
   > *delegates*, while omitting real public composers. The contract binds **every** function that returns
   > or builds a state path:
   >
   > | library | functions that MUST return the sentinel when unresolved |
   > |---|---|
   > | `paths.sh` | `unleashed_plugin_base` (`:34`) — the raw resolver |
   > | `marker.sh` | `marker_base` (`:16`), `marker_dir`, **`marker_path` (`:109`)** |
   > | `log.sh` | `log_base` (`:19`), **`log_dir` (`:31`)** |
   > | `context.sh` | `context_base` (`:28`), `context_reviews_dir` (`:54`), and every `context_*` path form |
   >
   > Because the sentinel is **non-empty**, an outer composer built on a guarded inner one stays poisoned
   > rather than rooted — `marker_path` on a sentinel `marker_base` yields
   > `/dev/null/unresolved-plugin-base/quality-marker-….json`, not `/quality-marker-….json`. That is the
   > property "return empty" could not provide, and it is why the sentinel — not the guard's placement —
   > is what actually holds D′.
   >
   > **A new primitive can still bypass the accessor and read `CLAUDE_PLUGIN_DATA` directly**, so the
   > contract needs an enforcement test, not just prose. **N5: a structural check.**
   >
   > **Round 7 — N5 as round 6 wrote it was a SPELLING check, and is rejected.** Asserting on the literal
   > `${CLAUDE_PLUGIN_DATA` catches one of the forms Bash accepts. `$CLAUDE_PLUGIN_DATA/x`,
   > `"${CLAUDE_PLUGIN_DATA}"`, `${CLAUDE_PLUGIN_DATA:?}`, `${CLAUDE_PLUGIN_DATA:-…}` and `${!ref}` all
   > evade it. This is not hypothetical: **`scripts/test-hooks.sh:446` already ships the unbraced form**
   > (`[ -s "$CLAUDE_PLUGIN_DATA/logs/stop-gate.log" ]`), so the tree contains a live instance of the very
   > bypass the check claimed to prevent, and the check would have passed over it.
   >
   > **Measured at `b2496a8`, so the test is written against a known tree, not a guess:** the identifier
   > occurs **45** times across `scripts/**`, `hooks/**`, `agents/**`, `skills/**` and `.githooks/**` —
   > `test-hooks.sh` 19, `test_shell_primitive_drift.py` 9, `agents/swift-reviewer.md` 5,
   > `pre-commit-checks.sh` 2 (comments), `paths.sh` 2, `log.sh` 2, `context.sh` 2,
   > `test_reviewer_roster.py` 1, `marker.sh` 1. **A name-only scan would therefore fail on ~36
   > legitimate sites** — which is why the predicate is not "the identifier appears".
   >
   > **ROUND 9 — WHAT N5 CAN AND CANNOT PROVE. Read this before trusting it.**
   >
   > codex **executed** a bypass that contains no lexical `CLAUDE_PLUGIN_DATA` expansion at all:
   >
   > ```bash
   > n=CLAUDE_PLUGIN_ ; n="${n}DATA" ; d="$(printenv "$n")"
   > printf '%s/%s' "$d" "m-$1.json"      # -> /m-lint.json when unset
   > ```
   >
   > It reads the environment through a **runtime-assembled name**, so no static scan over shell syntax
   > can see it. A hard-coded `"${HOME:-}/.claude/unleashed-mail"` fallback evades N5 equally, without
   > touching the variable at all. gemini found the same class independently (`printenv`, `env | grep`).
   >
   > **So N5's guarantee is narrowed, not patched a fourth time.** N5 is a **lexical drift detector**:
   > it proves that *within the scanned tree, at review time,* the identifier `CLAUDE_PLUGIN_DATA` is
   > expanded only at enumerated sites. That is worth having — it is exactly how a copy-paste of the
   > resolver into a new primitive gets caught, which is the failure this ticket is about. It is **not**
   > a proof of accessor-only provenance, and this plan no longer claims one. A primitive determined to
   > acquire the base by other means is outside N5, outside N1/N2's envelope, and therefore outside D′.
   >
   > **What actually holds D′ for code that exists** is the enumerated envelope plus the sentinel, both
   > of which are mechanically checked. What holds it for code not yet written is N5's drift detection
   > plus review — a *hardening*, not a boundary. **Stated plainly here so no reader infers a guarantee
   > that is not there** — the same move §3.1 of COREDEV-2497 made after five defeated mechanisms, and
   > for the same reason: four rounds have now shown this property is not statically decidable in Bash.
   >
   > *(The CHANGELOG must carry this distinction — see §7 step 7.)*
   >
   > - **Predicate — an ALLOWLIST of exact sites, not a pattern over spellings. Round 8.** N5 fails on
   >   **every expansion of `CLAUDE_PLUGIN_DATA` that is not at an enumerated allowlisted site.** Full
   >   stop. No suffix list, no "followed by `/`" test, no attempt to recognise the shapes of composition.
   >
   >   *(Round 8 rejected the round-7 predicate, which failed a line only when the expansion was
   >   immediately followed by `/` **or** assigned into a name ending `_DIR`/`_PATH`/`_BASE`/`_FILE`/`LOG`.
   >   Both reviewers broke it in one line. gemini: `d="$CLAUDE_PLUGIN_DATA"` then `mkdir -p "$d/logs"` —
   >   an unlisted variable name. codex: `printf '%s/%s' "${CLAUDE_PLUGIN_DATA-}" "m-$1.json"` — a
   >   split expression that composes a root path when unresolved and matches neither branch, with no
   >   `${!…}` or `eval` to trip the fail-closed arm. **This is the third round in which N5 has been a
   >   pattern that enumerates the bypasses it knows about.** A blacklist of shapes cannot bound an open
   >   set of shapes; the enumerated-allowlist form can, because the question becomes "is this line one of
   >   the N sites we approved" rather than "does this line look dangerous". Inverting a defeated
   >   blacklist into an allowlist is a move this campaign has already had to make once.)*
   >
   >   Merely **naming** the variable is still not a defect — but that permission now comes from being on
   >   the allowlist, not from a pattern judging intent. Comments, the `export X="${X}"` MAJ-6 bridge and
   >   `[ -n "$X" ]` tests are allowlisted **as specific lines**, so a later edit that appends a suffix to
   >   one of them fails N5 until the allowlist is deliberately updated.
   > - **The four resolver definitions are the allowlist's core**, and the plan's "four accessors" is
   >   correct as a count: `paths.sh:35` (canonical) plus the three **deliberate inline fallbacks** at
   >   `marker.sh:29`, `log.sh:27` and `context.sh:36`. Those three are load-bearing by design, not drift
   >   — `paths.sh:11-20` explains that these libs are sourced standalone and that making them abort would
   >   convert three fail-open paths into one shared point of failure. N5 must pin them, **not** delete
   >   them.
   > - **Scan set includes the executable fences in `agents/**` and `skills/**`.** An agent body that
   >   tells the model to compose the path is the same defect shipped as prose, and
   >   `agents/swift-reviewer.md:247-249` is already on §7's guard list for exactly that. The MAJ-6 bridge
   >   at `swift-reviewer.md:176` and `:244` (`export CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}"`)
   >   **propagates** the variable and composes nothing — allowlisted by the predicate above, and named
   >   explicitly so a future edit that appends a suffix to it fails.
   > - **Test fixtures are allowlisted by (file, reason), enumerated in the test source** — never by a
   >   `tests/` glob, which would let a future library file under a test path bypass the contract.
   >   `test-hooks.sh` **sets** the variable to a temp root (`:33`) and composes under **that**, which is
   >   the isolation mechanism itself; `test_shell_primitive_drift.py` gates the expansion **form** and
   >   must contain the literal; `test_reviewer_roster.py:41` sets it. Adding a site is then a visible
   >   diff, not a silently-widened pattern.
   > - **Indirection fails closed.** `${!…}` and `eval` over a name assembled at runtime cannot be decided
   >   statically, so N5 fails on any `${!` or `eval` in the scan set that is not itself allowlisted,
   >   rather than pretending to analyse it.
   >
   > **N5's mutants — THREE, and round 8 replaced the original set because it proved nothing.**
   > Each is added to `scripts/lib/marker.sh`; N5 must **fail** on each tree, and pass once the body is
   > rewritten onto `marker_path`:
   >
   > | # | mutant | the form it represents |
   > |---|---|---|
   > | **N5a** | `marker_write_v2() { printf '%s' "$2" > "$CLAUDE_PLUGIN_DATA/m-$1.json"; }` | unbraced, expansion immediately followed by `/` |
   > | **N5b** | `marker_path_v2() { printf '%s/%s' "${CLAUDE_PLUGIN_DATA-}" "m-$1.json"; }` | **split expression** — composes across a `printf` format with no `/` adjacency; yields `/m-lint.json` when unresolved (codex, round 8) |
   > | **N5c** | `marker_dir_v2() { local d="$CLAUDE_PLUGIN_DATA"; mkdir -p "$d/logs"; }` | **indirection through an unremarkable variable name** (gemini, round 8) |
   >
   > *(Round 8: the round-7 mutant set was **N5a alone** — and N5a is precisely the form the round-7
   > predicate already recognised, so it could only ever fail-then-pass. It demonstrated that the test
   > executes, not that it protects. The plan had already written down the rule it was breaking two lines
   > below: *a test that cannot distinguish the two trees is not evidence.* **N5b and N5c are the forms
   > that actually defeated the predicate** — each found by a different reviewer, neither using `${!…}`
   > or `eval` — and a mutant set that omits them is not a proof. Under the allowlist predicate all three
   > fail for one reason: the expansion is not at an approved site. One rule, not three patches.)*
   >
   > **The cache is EAGER and process-stable — round 6 Medium.** "Resolve once into a cached value" is
   > not implementable as written: the libraries source `paths.sh` lazily *from inside* the base
   > functions, and callers invoke those through command substitutions (`marker.sh:34`, `log.sh:32`,
   > `context.sh:39`). A variable first assigned there lives in the **subshell** and is gone on return, so
   > a "cache" would silently re-resolve on every call. Specify it exactly:
   >
   > - **Eager**: resolution runs at **source time**, in the sourcing shell, before any command
   >   substitution — not on first use.
   > - **Process-stable**: the resolved value is a plain shell variable in that shell
   >   (`_UNLEASHED_BASE_RESOLVED`), set once, never re-derived per call.
   > - **Status convention**: a companion `_UNLEASHED_BASE_OK` is `1` when resolved and `0` when the
   >   sentinel is in force. Primitives branch on that flag, never on string comparison against the
   >   sentinel — so a caller cannot fake resolution by exporting the sentinel text.
   > - **Diagnostic cardinality**: **exactly one** unresolved diagnostic per process, emitted at source
   >   time (§4.1's observability requirement), not one per primitive call.
   >   **This must hold in the absent-`paths.sh` mode too — round 9, gemini.** With `paths.sh` missing,
   >   `marker.sh`, `log.sh` and `context.sh` each take their own inline fallback, so sourcing two or
   >   three of them in one process would emit two or three diagnostics and break the cardinality this
   >   plan mandates. **The guard is the shared flag, not the file:** each lib emits the diagnostic only
   >   when `_UNLEASHED_BASE_OK` is still **unset**, and sets it in the same step. The flag lives in the
   >   sourcing shell and is therefore shared whether or not `paths.sh` was found — so the cardinality
   >   is a property of the resolution protocol, not of the optional file.
   >
   > **N1/N2 must source in a FRESH SHELL per cell.** The existing harness exports the variable *before*
   > sourcing the libraries (`scripts/test-hooks.sh:33`); with an eager cache, mutating the environment
   > afterwards cannot change the resolved value. Each of the six cells therefore starts a new shell,
   > sets the environment, *then* sources — anything else tests the harness's ordering, not the contract.
   >
   > **Proving "no reads" needs a positive signal, not an absence.** An unwritten root file makes an
   > illicit read observationally identical to a correctly skipped one.
   >
   > **Round 7 — the round-6 canary is PHYSICALLY IMPOSSIBLE and is rejected.** It required planting "a
   > readable file at the sentinel location", but the sentinel is `/dev/null/unresolved-plugin-base` and
   > **nothing can be created beneath a character device**. The `ENOTDIR` property that makes the sentinel
   > safe is the *same* property that makes the canary unplantable — the two requirements are mutually
   > exclusive, and §7's own executed evidence above (`mkdir`, `mktemp` and the redirect all fail
   > `Not a directory`) is the proof that they are. The round-6 wording made the impossibility the
   > load-bearing half of its own oracle. The fallback half is no better: planting at the **root** path is
   > conditional on being able to write to `/`, so on any machine where it is refused the oracle silently
   > degrades to asserting nothing.
   >
   > **`atime` is not an oracle here either — three independent reasons.** (a) It does not observe the
   > reads that actually occur: the state libraries probe with `[ -f "$path" ]` (`marker.sh:154`,
   > `marker.sh:185`) and `[ -d "$d" ]` / `[ -f "$d/$agent.json" ]` (`context.sh:142`, `context.sh:145`),
   > which `stat` the path without ever opening it. (b) macOS mounts do not promise an `atime` update on
   > `open`, so it can be unchanged **after** a genuine read — a false pass. (c) It is a global
   > side-channel: any unrelated process touching the file forges a failure.
   >
   > **Round 8 — the command-shim read spy is NOT IMPLEMENTABLE IN BASH, and is rejected.** Both
   > reviewers reached this independently, and the reason is a language fact, not an oversight:
   >
   > - **A redirect is not a command.** `read -r line < "$path"` (`marker.sh:159`) is performed by the
   >   **shell**, which opens the file *before* invoking `read`. A wrapped `read` receives the bound
   >   variable name and **never the pathname**; and if the open fails, the wrapper is never called at
   >   all. There is no shim position from which the redirect is observable.
   > - **Pathname expansion is not a command either.** `for d in "$base"/round-*/` (`context.sh:141`
   >   and `:172`) and `for f in "$dir"/review-round-*.json` (`context.sh:212`) make the shell
   >   `opendir`/`readdir` the state directory *before* any interceptable `[ -d ]` runs. Worse, that
   >   later `[ -d ]` would make the guard-removed adequacy count non-zero **while the glob access
   >   stayed invisible** — the spy would appear adequate on a mutation it cannot actually see.
   > - The verb list was also incomplete: `cat` (`stop-quality-marker-gate.sh:93`,
   >   `agents/swift-reviewer.md:252`), `[ -L ]` and `[ -r ]` were all missing.
   >
   > This is the round-7 lesson repeating one layer down. The canary was rejected for being physically
   > impossible; its replacement was **mechanically** impossible, and it was adopted from a reviewer
   > without being executed. *Applying "execute, don't assert" to the fix as well as to the design is now
   > a standing requirement of this plan.*
   >
   > **THE ORACLE ASSERTS ON THE ENVELOPE'S RETURN VALUES, NOT ON THE SYSCALL AND NOT ON READERS'
   > LOCALS.** *(Round 9 correction: round 8 said "the composed path", which gemini correctly read as
   > the `local path=…` **inside** a reader — and those are invisible to a calling harness.
   > `_context_round_advance` (`context.sh:236`) is the sharpest case: it never assigns a path at all,
   > composing `"$base/round-$highest/$agent.json"` inline as a `python3` argv (`:255`).)*
   >
   > Every path-returning primitive in the §7 envelope **prints its result to stdout** — that is how they
   > are invoked, `$(marker_dir)`, `$(context_reviews_dir)` — so their return values are **directly
   > capturable** by a harness with no interception whatsoever. And every internal composition, including
   > `_context_round_advance`'s inline argv, is built **from one of those return values**: its `base`
   > parameter is supplied by the caller from `context_reviews_dir`. So asserting on the envelope's
   > outputs bounds the readers' internals **by construction**, which is the property a shim could not
   > deliver and a local-variable oracle could not observe. N1/N2 therefore:
   >
   > 1. **Capture the return value of every path-returning primitive in the §7 envelope table** and
   >    assert **each begins with `/dev/null/unresolved-plugin-base`**. These are stdout values, not
   >    locals. A return that does not is the defect, whether or not a read follows it.
   > 2. **Rely on the sentinel's already-executed physics for the rest.** Under an `ENOTDIR` parent every
   >    verb in the list above — redirect, glob, `cat`, `stat`, `[ -f ]`, `[ -d ]`, `[ -L ]`, `[ -r ]` —
   >    fails or yields empty *by construction*. Once the composed path is proven to be under the
   >    sentinel, "no real read occurred" follows from §7's executed transcript rather than from an
   >    observer that cannot see redirects or globs.
   > 3. **Assert the negative directly where it is cheap:** nothing exists under `/` afterwards
   >    (`/logs`, `/reviews`, `/.state`, `/quality-marker-*.json`, `/stop-last-blocked-*`), and nothing
   >    is created outside the cell's own temp dir.
   >
   > **Coverage is enumerated per public reader, not sampled** — `marker_field` (`:151`, hence
   > `marker_status` `:178` and `marker_commit` `:179`), `marker_mtime` (`:182`),
   > `context_latest_round_dir` (`:134`), `context_highest_round` (`:168`),
   > `context_review_round_lookup` (`:298`), `_context_file_mtime` (`:195`),
   > `_context_round_advance` (`:236`) and **`_context_round_sweep` (`:205`)**, which round 7 missed:
   > it `[ -d ]`s its dir (`:207`), globs it (`:212`), `[ -f ]`s each hit (`:213`) — **and deletes**
   > (`:216`, below). A reader missing from that list is missing from the proof.
   >
   > **Adequacy is still proved by mutation, and now it CAN be:** with the guard removed the composed
   > path becomes a root path (`/logs`, `/reviews/<hash>`), so the assertion in (1) fails on the mutated
   > tree and passes on the fixed one — for **every** reader, including the two whose reads a shim could
   > never observe. That is the property the shim version could not deliver.
   >
   > Each consumer still resolves the base **once**, at entry, and takes its documented no-persistence path if
   > unresolved — so a newly added `marker_write` cannot silently reintroduce the defect.

   Remaining **non-executable** sites to update (documentation and fixtures only — every executable
   consumer is now a row in the table above):
   - docs/tests: README, `.gitignore`, pre-commit comments, the resolver matrix, hook/roster fixtures

   *(Round 12: this list previously carried **five executable scripts** — the three log hooks and both
   capture hooks — with no defined unresolved-base behaviour, while step 5's own instruction demands
   "each with its **required control flow**". An implementer would have had to invent whether they
   fail open or closed. It also still named **PreCompact** and **SessionStart** after round 10 moved
   them into the table. The list is now documentation-only, so anything appearing in it can never again
   be mistaken for a guarded consumer.)*
6. Quarantine the 21 orphans with inventory and checksums, and quarantine the one `-inline` file
   **separately** with its own inventory — its provenance is unknown, so it must not be merged with the
   rest. Add N4.
7. Version bump + CHANGELOG, stating plainly that state written before this fix may live in a second
   directory and how to find it — **and that N5 is lexical hardening, NOT a boundary** (§7's narrowed
   claim: it proves the identifier is expanded only at enumerated sites, and proves nothing about a
   primitive that acquires the base some other way). *(Round 10, codex: the narrowing said the
   CHANGELOG must carry it and this checklist did not, so the one operative step that reaches a
   reader would have shipped the old, broader impression.)*

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

6. ~~Does D′ need an escape hatch?~~ **ANSWERED in round 3 — NO.** Both reviewers: document
   `CLAUDE_PLUGIN_DATA` as required for manual persistence. codex noted an
   `UNLEASHED_ALLOW_LEGACY_BASE=1` opt-in would deliberately recreate the ambiguous second store; gemini
   noted a manual run then fails open and skips marker writes, which is how the git hooks already behave
   outside Claude Code.

**No open questions remain.** Round 4 returned `APPROVE_WITH_NOTES` from codex with no High or Medium
findings; gemini's High was §7's incomplete consumer table, now closed.

## 9. Notes

- Every figure here was executed on 2026-07-30 against HEAD `5a532b1`: the three base directories and
  their file counts, both copies of `quality-marker-lint-df57b844116d.json`, the unset environment in a
  Bash-tool shell, and the four resolver sites.
- `scripts/lib/paths.sh` already defines the intended single primitive, `unleashed_plugin_base()`
  (`:34-36`). This ticket is not about creating it; it is about the fact that its **answer** is wrong
  outside a hook. *(Round 3: this bullet previously said three files "re-derive the same wrong answer
  independently" — they **delegate** (`marker.sh:21`, `log.sh:19`, `context.sh:28`) and keep the literal
  form only as an absent-file fallback. §11 claimed this had been corrected; it had not been, here.)*
- The `-inline` base directory is residue of **unknown provenance** — evidence for §4.2's ambiguity
  argument, not a separate defect. *(Round 3: this bullet previously asserted a project-scoped origin,
  contradicting the withdrawal in §2. §11 claimed all retractions were applied; this one was not.)*

> **Transcript-path notice (2026-07-30).** Every `/tmp/rev/…` path cited in the round histories below
> **no longer exists**: the machine's root volume filled, and macOS purged `/private/tmp`, destroying all
> 105 captured transcripts of this campaign in one event. The byte counts and hit counts recorded here
> were taken from those transcripts while they existed and are left as the historical record — but they
> are **no longer independently reopenable**, and a reviewer should treat them as claims, not evidence.
> Codex's own rollout logs under `~/.codex/sessions/` survived and were used to recover the affected
> round's findings. Captures from this round forward go to `~/.claude/review-transcripts/`.

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

## 12. Round-3 gate outcome

**gemini `REQUEST_CHANGES` (1 High) · codex `REQUEST_CHANGES` (5).** Frozen at `51642a49…`, sha256
`e07fe1ec…`. Transcripts: `/tmp/rev/2617r3-agy.txt` (2,736 B, `TREE=clean`) and
`/tmp/rev/2617r3-codex.txt` (380,012 B).

**Both reviewers confirmed the round-2 decisions**: **D′** over the hybrid (gemini reversed its own
round-2 position after checking `pre-commit-checks.sh:14-18` and finding the marker writes documented as
unreachable no-ops), and **no escape hatch** for §8 Q6 — codex noting that `UNLEASHED_ALLOW_LEGACY_BASE`
would deliberately recreate the ambiguous second store.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | gemini | **"refuse at the call site" is unsafe in Bash** — without `set -e`, a non-zero return inside `$(…)` still yields an empty string and composes a root path | **confirmed by execution**: `stop-quality-marker-gate.sh:18` is `set -uo pipefail`; a refusing resolver still produced `LOGDIR=[/logs]` | D′ is enforced at **every consumer**; each must test before composing any path |
| 2 | codex | **per-consumer control flow was unspecified** — suppressing persistence must not change primary behaviour | **confirmed** | §7 gains a table: `pre-commit-checks.sh` must keep its `EXIT_CODE`, `swift-lint-check.sh` its model-visible block, `swift-build-verify.sh` its advisory, `reviewer-roster.sh` must stay **fail-closed** (`UNATTRIBUTED`, exit 3) |
| 3 | codex | **§4.1 still contradicted D′** — requiring a plugin-log diagnostic and derived/legacy enums that D′ makes unreachable | **confirmed** | §4.1 scoped to the resolves case; unset yields only the stderr diagnostic |
| 4 | codex | **§11 claimed corrections that were never applied** — §9 still said the libs re-derive independently and still assigned `-inline` a provenance | **confirmed** | both corrected at the source, and the false claim in §11 is noted here rather than silently fixed |
| 5 | codex | **N3 omitted its load-order requirement** — the sentinel must be injected after `_UNLEASHED_PATHS_SH_LOADED=1` or sourcing overwrites it | **confirmed** by codex's reproduction | stated in §4.3 |
| 6 | codex | **N4 did not prove the quarantine happened** — it becomes true the moment D′ lands | **confirmed** | N4 now requires sources absent, exact inventory, matching checksums |

**Evidence reproduced again:** `76 / 21 / 1`; the divergent marker exactly `e6f1f0ab` vs `a39790f5`;
sentinel counts `0 / 1`; both plugin variables unset in an ordinary shell; one active registry id. The
active base's newest write advanced again (now `13:36:55`) — the expected moving measurement, recorded
rather than quietly refreshed.

## 13. Round-4 gate outcome

**codex `APPROVE_WITH_NOTES` (no High or Medium) · gemini `REQUEST_CHANGES` (High).** Frozen at
`9548299a…`, sha256 `19fc4e43…`. *(Round 5 correction: this line recorded `e07fe1ec…`, the digest of the **round-3** freeze `51642a49` — the previous round's value copied forward. Identical defect in `COREDEV-2605` §14; both found in round 5/6.)* Transcripts: `/tmp/rev/2617r4-agy.txt` (3,767 B, `TREE=clean`) and
`/tmp/rev/2617r4-codex.txt` (417,546 B, 66 ticket-key hits).

> **Round 5 retraction — this verdict does not reproduce.** Re-running the *identical* round-4 codex
> prompt against the *same* frozen bytes returned **`REQUEST_CHANGES`**, and found a real design defect
> (entry-guards cannot reach the sourced state libraries — §7). The transcripts of both runs are
> byte-verified against the same digest, so this is reviewer non-determinism, not a changed plan.
> **Treat the line below as a sampled verdict, not as evidence the plan was sound at round 4.** The gate
> now requires an approving pair that **reproduces** across two consecutive rounds at the same digest.

**This was recorded as the campaign's first approving verdict**, and the split is instructive: codex judged D′ safely
implementable across the consumer set it had enumerated, while gemini went back to the scripts and found
the enumeration itself incomplete — including every destructive site.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | gemini | **§7's consumer table missed the destructive sites.** `stop-quality-marker-gate.sh:66` composes the sentinel path, `:120` runs `mktemp "$(marker_dir)/…"`, `:123` runs `mv -f` — all creating or moving files under `/.state/` on an unresolved base. Round 3 guarded only `:131-132` | **confirmed** — all six lines printed | the whole script is guarded at entry; the table lists them |
| 2 | gemini | **the pre-commit PASS cases were unguarded** — round 3 listed `:44`/`:69` (fail) and omitted `:47`/`:72` (pass), so a *successful* run wrote to a root path | **confirmed** — printed | both added |
| 3 | gemini | `swift-lint-check.sh:67` (early syntax-error exit), `reviewer-roster.sh:53` (composes `/reviews/…` for a root **read**), `swift-reviewer.md:247` (no control-flow requirement) | **confirmed** | all three added |
| 4 | gemini | **`test-hooks.sh:624`/`:796` call `context_snapshot_path`** — so the very tests that verify D′ could compose root paths, since N1/N2 must run with the variable unset | **confirmed** | guarded before the fixtures run |
| 5 | codex | editorial: §7 still said to re-settle D′, §8 Q6 still read as open, the header still said "Awaiting round 3" | **confirmed** | all closed out without reopening either decision |

**The structural lesson, applied:** a **per-line** guard table is the wrong shape — round 3's version
named six of fourteen sites and missed every destructive one. Each consumer now resolves the base **once
at entry** and takes its no-persistence path if unresolved, so a newly added `marker_write` cannot
silently reintroduce the defect.

One accuracy note on the evidence: gemini labelled `:117` as `rm -f "$SENTINEL"`; that line is actually
the symlink/type check. The substance — root-path operations across that block — holds; the label does
not. The same "reproduces the defect, mislabels the location" pattern this campaign has recorded
throughout.

codex reproduced the evidence again: HEAD, digest, `76/21/1`, sentinel `0/1`, the divergent
`e6f1f0ab`/`a39790f5` markers, one active registry id, both variables unset. It found **no independent
production-Python resolver**, confirming the capture hook computes the base in shell and passes it in.

## 14. Round-5 gate outcome

**gemini `APPROVE` · codex `REQUEST_CHANGES`.** Frozen at `093df689…`, sha256 `d0df8515…`.

**The round that established the gate is non-deterministic.** This round's codex run was a *re-run* of
round 4's prompt against byte-identical bytes, forced by the transcript loss (see the transcript-path
notice above). It returned `REQUEST_CHANGES` where round 4 returned `APPROVE_WITH_NOTES` with no High or
Medium — and the finding it added was real. §13 carries the retraction; the campaign's gate now requires
an approving pair that **reproduces**.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **"guard at script entry" cannot hold D′** — the state libraries are *sourced* (`paths.sh:12-16`) and have **no entry**, so `marker_*`, `log_*` and `context_*` still compose for any caller; entry-only exits are also wrong for consumers whose primary behaviour must continue | **confirmed** — `marker.sh:33-34,117-127`, `log.sh:31-32,42-58`, `context.sh:39,54-55,190-191,267-286` | §7 moves the guard inside each **public primitive**, off one validated cached base |
| 2 | codex | the `swift-reviewer.md` fence's row **restated that no control flow was supplied** rather than supplying it; the fence composes *and reads through* the path | **confirmed** — `agents/swift-reviewer.md:247-249` | the row now mandates no filesystem read and `NO CAPTURE (unresolved)` per reviewer |
| 3 | codex | §13's round-4 digest was `e07fe1ec…`, the **round-3** freeze's value copied forward | **confirmed** — `51642a4`→`e07fe1ec`, `9548299`→`19fc4e43` | corrected in §13; the identical defect in `COREDEV-2605` §14 was fixed the same round |
| 4 | codex | stale anchors: the final pre-commit exit is `:192`, the late lint marker `:425`, the build-log call `:65-66`; `:117` is the type check, `:118` the removal | **confirmed** by execution | all corrected |

## 15. Round-6 gate outcome

**gemini `REQUEST_CHANGES` (2 High) · codex `REQUEST_CHANGES` (2 High, 1 Medium, 1 Low).** Frozen at
`57ff072f…`, sha256 `e0861f6a…`. Transcripts: `~/.claude/review-transcripts/2617r6-agy.txt` (2,420 B,
`TREE=clean`) and `…/2617r6-codex.txt` (5,303 lines).

**Round 5's fix was the round-3 defect one layer down, and both reviewers said so independently.**
Returning "no persistence result" from a primitive returns the **empty string** in Bash, and the caller's
own concatenation still composes a root path. This is the campaign's clearest instance of a fix that
relocates a defect instead of removing it.

*(Process note: a concurrent agent committed `b9b63c6` to this worktree mid-round. It touched only
`COREDEV-2497`'s plan. gemini's run was voided by the harness's tree-mutation assertion; codex detected
the moving `HEAD`, re-verified this plan byte-identical to `57ff072` at `e0861f6a…`, and correctly bound
its review to the immutable commit object rather than the checkout.)*

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **"return nothing" still composes a root path.** `$(marker_dir)` returning empty yields `/stop-last-blocked-…` (`:66`), `mktemp /.stopgate.XXXXXX` (`:120`), `/logs` (`:132`), `/reviews/<hash>` (`context.sh:54`), `/<slug>` (`reviewer-roster.sh:53`) | **confirmed** — the same property round 3 established about call sites | path-returning primitives now return a **poisoned non-root sentinel** `/dev/null/unresolved-plugin-base` (`ENOTDIR` beneath it); writers become no-ops |
| 2 | codex | **the absent-`paths.sh` matrix contradicts D′.** `test_shell_primitive_drift.py:92`/`:129` expect the **legacy base** for unset *and* empty, and in absent mode the libs take inline branches (`marker.sh:21`, `log.sh:19`, `context.sh:28`) that **bypass the cache** entirely — N3 was therefore not sound | **confirmed** | the inline fallback is no longer exempt; the plan **mandates the matrix change** and N1/N2 run the full six-cell cross-product |
| 3 | codex | **the primitive envelope was incomplete** — it named `marker_commit` (a delegator) and omitted `marker_path` (`:109`), `log_dir` (`:31`) and the raw resolvers (`paths.sh:34`, `marker.sh:16`); a new primitive can bypass the accessor entirely | **confirmed** | exhaustive per-library envelope table + **N5**, a structural check that the literal expansion appears only in the accessors |
| 4 | codex | **the cache is not implementable as stated** — lazy sourcing inside command substitutions makes it **subshell-local**; eager/lazy, the status convention and diagnostic cardinality were undefined; `test-hooks.sh:33` sets the variable *before* sourcing; and "no reads" cannot be proven from an absence | **confirmed** | cache specified **eager and process-stable** with an `_UNLEASHED_BASE_OK` flag and one diagnostic per process; N1/N2 source a **fresh shell** per cell and assert on a **planted canary** |
| 5 | codex | the header claimed rounds 1-5 in §10-§14 while the document ended at §13 | **confirmed** | §14 and §15 added — this section and the one above |

## 16. Round-7 gate outcome

**gemini `REQUEST_CHANGES` (1 High, 1 Medium) · codex `REQUEST_CHANGES` (1 High, 2 Medium).** Frozen at
`b2496a8`, sha256 `c6d41a44537c7838f0d03d0fd8fb5280a4c2415970fe3577a26090c767cd6b73` — verified against
`git show b2496a8:…` and reported identically by both arms. Transcripts:
`~/.claude/review-transcripts/2617r7-agy.txt` (1,176 B) and `…/2617r7-codex.txt` (149,069 B).

**Round 7 is round 6's two fixes failing in their own terms.** Both of round 6's headline remedies — the
planted canary and N5 — were adopted from codex and neither was executable. That is the round's real
lesson: *a fix proposed by a reviewer is a claim, not a verified mechanism*, and this plan's own standard
("execute, don't assert") was applied to the sentinel and not to the two proofs built on top of it.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **the planted canary is physically impossible.** N1/N2 required a readable file at the sentinel location to prove no read occurred — but the sentinel is `/dev/null/unresolved-plugin-base`, and nothing can be created beneath a character device. The `ENOTDIR` property that makes the sentinel safe is the same one that makes the canary unplantable. codex adds that `atime` is no fallback: it does not observe the `[ -f ]`/`[ -d ]` **metadata probes** that are the actual reads, and may be unchanged after a genuine `open` | **confirmed by the plan's own executed evidence** — §7's round-6 transcript already shows `mkdir`, `mktemp` and the redirect all failing `Not a directory` at that exact path. The reader claims check out: `marker.sh:154`, `marker.sh:185`, `context.sh:142`, `context.sh:145` all `stat` without opening | the canary is **rejected**; the oracle becomes a **mandatory instrumented read spy** asserting a call count of **zero**, enumerated per public reader, whose own adequacy is proved by a non-zero count with the guard removed |
| 2 | **both** | **N5 is trivially bypassable** — it asserts the literal `${CLAUDE_PLUGIN_DATA`, which is a **spelling** check. `$CLAUDE_PLUGIN_DATA`, `"${CLAUDE_PLUGIN_DATA}"`, `${CLAUDE_PLUGIN_DATA:?}` and `${!ref}` all evade it. codex adds that the tree **already ships the bypass** at `scripts/test-hooks.sh:446`, and that N5 had no adversarial mutation because §6's proof list said N1–N4 | **confirmed by grep** — `:446` is `[ -s "$CLAUDE_PLUGIN_DATA/logs/stop-gate.log" ]`, unbraced. Measured at `b2496a8`: **45** occurrences of the identifier across `scripts/**`, `hooks/**`, `agents/**`, `skills/**`, `.githooks/**` | N5's predicate rebuilt around **path composition from the raw variable**, not mention of it; scan set widened to the executable fences in `agents/**`/`skills/**`; allowlist enumerated by (file, reason); indirection fails closed; **N5 gains its own mutant** and §6's list is corrected to N1–**N5** |
| 3 | codex | **the "exhaustive" envelope names a reader as a writer and omits two real mutators** — `marker_commit` delegates to `marker_field` (`marker.sh:179`), while `context_review_round_bind` (`context.sh:263-291`) and `context_review_round_clear` (`:342-345`) get no unresolved contract and no N1/N2 coverage. An unguarded `bind` can still **print a round that was never stored** | **confirmed by reading the source** — `marker_commit` is one line delegating to the reader; and `printf '%s' "$round"` (`context.sh:290`) executes unconditionally **after** the failed `mv`, so the print survives the failed write | `marker_commit` **struck** from the writing-primitive rule; both round-binding functions added, with `bind`'s contract stated as **print nothing, return 0** rather than merely "skip the write" |

**Finding 3 is the campaign's meta-defect in its purest form.** Round 6 *found* that `marker_commit` is
only a delegator, wrote that finding into the prose four paragraphs below the rule — and left
`marker_commit` standing in the operative list. The commit message for `b2496a8` even says
"it named marker_commit (a delegator)". The correction was known, recorded, and not applied where it
governs. **Grep every operative restatement before declaring a design change propagated.**

## 17. Round-8 gate outcome

**gemini `REQUEST_CHANGES` (5 High, 1 Medium) · codex `REQUEST_CHANGES` (2 High).** Frozen at `8012bf6`,
sha256 `d157ceb109d3c6f72ea693cc5fa6be7cd2e86b97413ffdd4b3a5dc1f16676e68` — codex verified it and
confirmed the worktree unchanged. Transcripts: `~/.claude/review-transcripts/2617r8-agy.txt` (2,609 B)
and `…/2617r8-codex.txt` (297,242 B).

**Round 7 rejected the canary as physically impossible; round 8 rejects its replacement as mechanically
impossible.** Both reviewers, independently, showed the command-shim read spy cannot work in Bash. The
pattern is now explicit and costly: **round 6's fix was unexecutable, round 7's fix was unexecutable, and
both were adopted from a reviewer without being executed.** The plan applied "execute, don't assert" to
the sentinel — which is why the sentinel has survived three rounds — and not to the proofs built on it.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **the read spy cannot observe the reads that matter.** A redirect is performed by the *shell*: `read -r line < "$path"` (`marker.sh:159`) opens the file before `read` runs, and a wrapped `read` never receives the pathname — nor is it called at all if the open fails. Pathname expansion is likewise not a command: `for d in "$base"/round-*/` (`context.sh:141`, `:172`) and `for f in "$dir"/review-round-*.json` (`context.sh:212`) `opendir` the state directory before any interceptable test. codex adds that the *later* `[ -d ]` would make the guard-removed adequacy count non-zero **while the glob stayed invisible** — the spy would look adequate against a mutation it cannot see. The verb list also omitted `cat` (`stop-quality-marker-gate.sh:93`, `agents/swift-reviewer.md:252`), `[ -L ]` and `[ -r ]` | **confirmed** — all six cited sites read as described; the redirect and glob semantics are language facts | **the oracle now asserts on the COMPOSED PATH, not the syscall.** Every read is preceded by a composition whose value is observable from the shell; N1/N2 assert every composed path begins with the sentinel, and lean on §7's already-executed `ENOTDIR` transcript for the rest. Adequacy is provable this way for **every** reader, including the two a shim could never watch |
| 2 | **both** | **N5's predicate is still a blacklist of shapes.** gemini: `d="$CLAUDE_PLUGIN_DATA"` then `mkdir -p "$d/logs"` — an unlisted variable name. codex: `printf '%s/%s' "${CLAUDE_PLUGIN_DATA-}" "m-$1.json"` — a split expression that yields `/m-lint.json` unresolved, with no `${!…}` or `eval` to trip the fail-closed arm. codex further notes **the round-7 mutant used the one form the predicate already caught**, so it could not demonstrate protection | **confirmed** — both bypasses are one line each, and neither is exotic | predicate **inverted to an enumerated allowlist**: every expansion outside an approved site fails, with no shape-matching at all. Mutants **N5a/N5b/N5c** now cover the immediate-`/`, split-expression and indirect-variable forms |
| 3 | gemini | **`_context_round_sweep` (`context.sh:205`) is missing from BOTH lists** — it `[ -d ]`s, globs and `[ -f ]`s (reader), **and** `rm -f`s (`:216`, mutator) | **confirmed** — round 7 added the two `context_review_round_*` functions on exactly this principle and left the third one, in the same file, unlisted | added to the reader coverage list and to the writing-primitive rule, with the same explicit no-op contract |
| 4 | gemini | *(Medium, answering the directed question)* `context_review_round_bind`'s "print nothing, return 0" is safe **because** its sole production consumer discards stdout | **confirmed independently by codex** — `capture-reviewer-round-start.sh:46` ends `>/dev/null 2>&1 \|\| true` | no change; the contract is recorded as verified rather than assumed |

**codex additionally confirmed the envelope is otherwise complete** — the `context_*` catch-all covers
`context_state_dir`, `context_snapshot_path` and `context_round_binding_path`, and all public mutators are
now represented.

**The standing rule this round adds:** *a fix proposed by a reviewer is a claim, not a verified mechanism.*
Three consecutive rounds have adopted a remedy that could not be built. Before a proof mechanism enters
this plan it must be executed, or its impossibility must be argued from the language semantics — the way
the sentinel itself was settled in round 6.

## 18. Round-9 gate outcome

**gemini `REQUEST_CHANGES` (5 High) · codex `REQUEST_CHANGES` (1 High).** Frozen at `740f561`, sha256
`eb7edfd5db0d0843b09f643547de2f0531729f6509c6ca41d5b6b43ecbee7710`. Transcripts:
`~/.claude/review-transcripts/2617r9-agy.txt` (2,303 B) and `…/2617r9-codex.txt` (327,189 B).

**This is the fourth consecutive round in which a proof mechanism failed, and that is now the finding.**
Round 6's canary was physically impossible; round 7's command shim was mechanically impossible; round 8's
composed-path oracle named the wrong observable; and N5 has been defeated in rounds 7, 8 and 9. **The
response is to narrow what is claimed rather than to attempt a fifth mechanism** — the move COREDEV-2497
§3.1 made after five defeated mechanisms, and for the same reason.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **N5 cannot enforce accessor-only provenance, demonstrated by execution.** `n=CLAUDE_PLUGIN_; n="${n}DATA"; d="$(printenv "$n")"` composes a state path with **no lexical `CLAUDE_PLUGIN_DATA` expansion anywhere** — codex ran it: `/tmp/host-base/m-lint.json` when set, `/m-lint.json` when unset. A hard-coded `${HOME:-}/.claude/unleashed-mail` fallback evades N5 without touching the variable at all | **confirmed — executed by the reviewer, not argued.** gemini found the same class independently (`printenv`, `env \| grep`) | **N5's guarantee is NARROWED.** It is a **lexical drift detector** — proof that the identifier is expanded only at enumerated sites, which is exactly how a copy-pasted resolver gets caught — and explicitly **not** a proof of accessor-only provenance. What holds D′ for existing code is the envelope + sentinel; for future code it is drift detection + review, a hardening rather than a boundary. The CHANGELOG must say so |
| 2 | gemini | **the composed-path oracle named an unobservable value.** Round 8 said "composed path", which reads as the `local path=…` **inside** a reader — invisible to a calling harness. `_context_round_advance` (`:236`) never assigns a path at all: it composes inline as a `python3` argv (`:255`) | **confirmed** — both cited sites read exactly as described | the oracle asserts on the **envelope's return values**, which every path-returning primitive **prints to stdout** and a harness captures with no interception. Internal compositions — including that inline argv — are built *from* those return values, so bounding the outputs bounds the internals **by construction** |
| 3 | gemini | **the "exactly one diagnostic per process" requirement breaks in absent-`paths.sh` mode** — each lib takes its own inline fallback, so sourcing two or three emits two or three diagnostics | **confirmed** — the three inline fallbacks are independent by design (`paths.sh:11-20`) | the guard is the **shared `_UNLEASHED_BASE_OK` flag**, not the file: each lib emits only while the flag is unset and sets it in the same step, so cardinality is a property of the protocol rather than of the optional file |
| 4 | gemini | `log_append` is missing from the writing-primitive rule | **REJECTED — it is already there.** `log_append` is named in that rule at `:395`, added in round 7 alongside the `context_review_round_*` mutators. *(gemini also mis-cited it as `log.sh:33`; it is `log.sh:39`.)* | none |
| 5 | gemini | `context_review_round_bind` "violates its stated contract" because `:290` prints unconditionally | **REJECTED, with reasons.** That is not a claim about current behaviour — it is the **change this plan mandates**. `:290` printing unconditionally after a failed `mv` is precisely the defect round 7 recorded and required fixing; reading the requirement as a description inverts it | none |

**codex's finding 1 is the most valuable single result of this ticket so far, because it was executed
rather than argued.** Three rounds of N5 revisions each assumed the previous predicate was *nearly* right
and widened it. Running one four-line bypass showed the whole approach has a ceiling: **path provenance
is not statically decidable in Bash.** Narrowing follows from that fact, not from fatigue.

## 19. Round-10 gate outcome

**codex `APPROVE_WITH_NOTES` (1 Low) · gemini — FAILED REVIEW, no verdict.** Frozen at `1cd04b2`, sha256
`c8e5d8b49517fe92bc10a77dc1f24a2e31b68b7dcf98676f3d8428e2e2b6072d`. Transcripts:
`~/.claude/review-transcripts/2617r10-codex.txt` (443,943 B) and `…/2617r10-agy.txt` (1,956 B).

**THE NARROWING HELD, AND THIS ROUND IS NOT A PASS.** codex returned the first non-`REQUEST_CHANGES`
verdict this ticket has had since round 4, with a single Low. But **the gemini arm emitted no `VERDICT:`
line** — it wrote its critique to `CRITIQUE-2617.md` inside the disposable checkout and summarised to
stdout instead. Per AGENT_CONTRACTS §2 a missing transcript verdict is **never** APPROVE, so the round
fails closed and gemini must be re-run. *(The isolation harness worked exactly as designed: the file went
into the throwaway worktree and the real tree was untouched — `TREE=clean`.)*

**What codex confirmed, having traced it:**
- N5's narrowed claim is **accurate and still useful** — the round-9 decision holds.
- **Every production persistent-state read traces back to an envelope return**; no counterexample to
  "bounding the outputs bounds the internals".
- The combined reader/mutator envelope **is exhaustive**, and mixed primitives such as `log_append` are
  covered by the unresolved no-op contract.
- The `_UNLEASHED_BASE_OK` protocol yields **zero diagnostics when resolved and exactly one when
  unresolved**, independent of library source order and of `paths.sh` presence.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | *(Low)* **§7 step 7's CHANGELOG checklist omits the N5 limitation** that the narrowing requires be documented | **confirmed** — the narrowing says the CHANGELOG must carry it; the one operative step that reaches a reader did not | step 7 now requires stating that **N5 is lexical hardening, not a boundary** |
| 2 | gemini *(failed arm — findings triaged anyway)* | **there are no `context_snapshot*` WRITERS.** `context.sh` has exactly one such function, `context_snapshot_path` (`:55`), a **path builder**. The writes happen inline in the consumers | **confirmed** — `precompact-snapshot.sh:61` and `sessionstart-restore.sh:30` each compose from `$(context_snapshot_path)` and write inline | the phrase is struck from the writing-primitive rule. **Third time this plan has named a non-existent or mis-typed primitive there** — `marker_commit` the reader, then the round-binding mutators, now these |
| 3 | gemini *(failed arm)* | **`precompact-snapshot.sh` and `sessionstart-restore.sh` are absent from §7 step 5's consumer table** — zero occurrences in the whole plan | **confirmed by grep** | both added, with their unresolved-base control flow: skip the snapshot write and the restore, change nothing else |
| 4 | gemini *(failed arm)* | "`_UNLEASHED_BASE_OK` is hallucinated — the fallbacks emit no diagnostic" | **REJECTED** — the flag is a **mandated design**, not a claim about current code, and §4.1's observability requirement is precisely the change being specified. codex traced the same protocol and found it sound. *(Same error class as round 9's finding 5: reading a requirement as a description.)* | none |

**A failed arm is not a free round.** Findings 2 and 3 are real and are applied, but the verdict is not
recoverable from a summary — the next round re-runs both arms at the new digest.

## 20. Round-11 gate outcome

**codex `APPROVE_WITH_NOTES` (1 Low) · gemini — FAILED REVIEW, no verdict (second consecutive).**
Frozen at `53e9947`, sha256 `c0415b148ea36766c28066c470cc63fa035b3a32a14d53dbe03997d5d0208794`.
Transcripts: `~/.claude/review-transcripts/2617r11-codex.txt` (330,413 B) and `…/2617r11-agy.txt`
(1,092 B).

**codex approved with notes for the second round running, and traced all four directed checks:**
- **Consumer scope is complete** — marker, log, context, agent-fence, capture-hook, snapshot, roster and
  test-harness consumers are all covered. `capture.py` composes only beneath the `context_reviews_dir`
  root supplied by `capture-reviewer-verdict.sh:45,62`, so it is covered when that hook takes its
  no-persistence path.
- **The mutator rule now names only real state-mutating functions** — `marker_write` (`marker.sh:115-145`),
  `log_append` (`log.sh:39-63`), `context_review_round_bind` (`context.sh:263-290`),
  `context_review_round_clear` (`:342-345`), `_context_round_sweep` (`:205-218`), with
  `context_snapshot_path` correctly retained in the **path-returning** envelope only.
- **The envelope-return oracle holds for both new consumers.**
- **N5 is consistently narrowed** across its definition, its allowlist mechanics and step 7's CHANGELOG.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | *(Low)* the snapshot note calls **both** consumers writers. In fact `precompact-snapshot.sh` writes (`:70-72`, tmp + `mv`) while `sessionstart-restore.sh` **reads and deletes** (`:31` `[ -f ]`, `:83` `rm -f`) | **confirmed** — terminology, not a mechanism gap; the operative consumer table already said "write" and "restore" correctly | the note corrected |

### The gemini arm has now failed twice, and it is a CAPTURE failure, not a review failure

Both times the transcript is a ~1 KB **summary** ending "I have printed the required critique to
`stdout`" — which it had not. This round it wrote **no file** (the harness reports nothing in the
disposable checkout), so the round-10 diagnosis — that it saved to `CRITIQUE-2617.md` — does not explain
this one. The substance is present in the summary and its stated verdict was `APPROVE_WITH_NOTES`, but
**a verdict asserted in prose is not a verdict line, and AGENT_CONTRACTS §2 fails closed on a missing
one.** It is not counted.

Both failures are on **this** ticket, the one where gemini's answer is "all four checks pass" — the two
plans where it reports findings print in full. The working hypothesis is that `agy` summarises when its
review is short and affirmative. **Next round the prompt asks for the verdict line FIRST and forbids any
meta-narration**, which is testable: if the arm still truncates, the failure is in the CLI's print mode
and the gate needs a different capture route for approving reviews.

## 21. Round-12 gate outcome — a DOUBLE APPROVAL that did NOT reproduce

**Round 12: gemini `APPROVE` (0 findings) · codex `APPROVE_WITH_NOTES` (1 Low).**
**Reproduction at the identical digest: gemini `REQUEST_CHANGES` (1 High, 1 Low) · codex
`APPROVE_WITH_NOTES`.** Frozen at `9c54e03`, sha256
`aeb221a16fdcf0549656e95060cb0eb102c0134c135213a00a08d53a746645eb` — **confirmed byte-identical for both
runs**. Transcripts: `2617r12-{agy,codex}.txt` and `2617r12b-{agy,codex}.txt`.

**THIS TICKET'S FIRST DOUBLE APPROVAL, AND IT IS NOT A PASS.** The maintainer's gate rule — *both
reviewers approving **and** that pair reproducing at the same digest* — was written for exactly this, and
it just paid for itself. On byte-identical input the gemini arm went `APPROVE` → `REQUEST_CHANGES`, and
**the re-run found a real defect the approving run had certified clean.** codex held steady across both.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | gemini *(reproduction)* | **five executable consumers had no control flow at all.** `build-failure-log.sh`, `stop-failure-log.sh`, `permission-denied-log.sh` and both capture hooks sat in the "Remaining sites to guard" bullet list, while step 5's own instruction demands "each with its **required control flow**". An implementer would have to invent whether they fail open or closed | **confirmed** — all five are real scripts with real state calls (`log_append` ×3, `context_review_round_bind`, `context_reviews_dir`) | all five are now **rows in the table** with stated behaviour. The bullet list is renamed **non-executable sites** — documentation and fixtures only — so nothing in it can be mistaken for a guarded consumer again |
| 2 | gemini *(reproduction)* | *(Low)* `PreCompact` and `SessionStart` were still listed as "remaining" after round 10 moved them into the table | **confirmed** | removed |
| 3 | codex | *(Low)* the snapshot note labels the correction "round 15 addressing round 14" when the document records it as round 11's finding and this is round 12 | **confirmed** — bookkeeping only | labels corrected |

**codex's round-12 verdict is unchanged across both runs and is worth recording:** §7 is implementable
end to end; the reader/mutator envelope is exhaustive; the sentinel-return oracle covers both snapshot
consumers; and N5 is consistently described as lexical hardening rather than a provenance boundary,
including the CHANGELOG requirement.

### Two process findings this round

**The isolation harness caught a rogue reviewer — on the *other* ticket, in the same batch.** COREDEV-2605's
gemini arm **implemented its plan instead of reviewing it**, reporting a §13/§14 split, rewritten gates,
new fixtures and a commit `43bf60d`. The real tree was untouched (`TREE=clean`, HEAD unchanged, every plan
digest still matching its freeze) because the review ran in a disposable checkout — COREDEV-2607's wrapper
doing precisely its job. **But `43bf60d` exists as a real object**, unreachable from any ref: the harness
isolates the *working tree* and shares the *object database*. A rogue reviewer cannot move a ref, but it
can leave dangling objects. Worth knowing; `git gc` collects them.

**The gemini arm's two earlier no-verdict failures were a prompt-shape problem, and it is fixed.** Rounds
10 and 11 produced ~1 KB summaries claiming to have printed a critique. Round 12's prompt demanded the
verdict line **first**, forbade meta-narration, and both round-12 runs emitted clean, anchored verdicts.
