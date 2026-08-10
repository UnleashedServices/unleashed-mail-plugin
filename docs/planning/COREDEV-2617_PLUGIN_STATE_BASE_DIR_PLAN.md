# COREDEV-2617 — Plugin state splits across two base directories

**Status:** Planning — **ROUND 30 OPEN: §4.2a is PROSPECTIVE CAPABILITY WORK, not a defect fix.**

> **HEADER RULE (round 30).** This header may not assert a motivation, a consumer count, or a severity
> that the section it summarises does not itself carry. It broke that rule twice: it said *"the
> specification is what is wrong"* (defect framing) and *"the anchor is now three consumer classes"*
> (a count §4.2a had already reduced to one live, one withdrawn, one prospective) for a full round
> after §4.2a was reframed. **A reframing applied to a section and not to the header that governs it is
> half a family**, and it is the fourth instance of that class on this ticket.

D′ shipped in **2.6.5** (`CHANGELOG.md:1045-1049`), not 2.7.0, ships in 2.7.1 today, and **behaves
exactly as specified — §1's split is history, closed by `f4ad405` and asserted by a green test.** What
§4.2a adds is a *capability*: making the base resolvable from shells that never receive
`CLAUDE_PLUGIN_DATA`. **It is not a fix for an observed failure** — the maintainer's "0s" report remains
undiagnosed, and three of the four motivations this plan once carried have been withdrawn (the
compaction snapshot, refuted by executing a compaction; the hand-run/CI class, never traced; and
`COREDEV-2585` §4.5b, absent from this tree). With `CLAUDE_PLUGIN_DATA` unset every writer
returns early **in silence**, and the variable does not reach an ordinary shell — so any consumer
outside a hook or MCP subprocess can neither read nor write plugin state. **One such consumer is traced
to bytes** — git hooks, where `scripts/pre-commit-checks.sh:14-18` documents the condition in its own
comment. The Bash-tool/CI/hand-run classes this summary previously named were **withdrawn in round 23**
as asserted-not-traced (CI exports its own temporary value; the Bash-tool reader bridges it explicitly),
and a model-written path remains **prospective**. §4.2a replaces the binary with a
**three-step resolution whose new element is a pointer file** published by the side that knows the answer
and read by the side that cannot: it derives nothing, so it does not import the
registry/`CLAUDE_CONFIG_DIR`/cache ambiguity that killed the A+D hybrid in round 2 — a claim round 20
attacked directly and could not break — and it converges the non-hook shell on the **same** store the hooks use
rather than forking a second one. Re-measured: **three** bases exist on this machine, not two. Round 2's
rejection of the hybrid was correct about `pre-commit-checks.sh` and was **over-generalised to every
consumer**. **ROUND 20 GATED §4.2a: both arms `REQUEST_CHANGES`, and both answered the open question the
same way — DROP the `$HOME` fallback step.** That step is gone in round 21, which *simplifies* the
change: §4.3's mandate and §4.4's quarantine ordering now stand **unchanged**, the drift matrix keeps all
four rows, and the resolution enum needs three values, not four. D″ is now **three steps**: the variable,
else an authenticated pointer, else D′'s sentinel byte for byte. `HOME` gates only pointer publication
and reading — **a non-empty `CLAUDE_PLUGIN_DATA` resolves regardless of `HOME`**; saying otherwise is
the fail-closed inversion round 23 removed. Two
motivations were corrected along the way and both are recorded rather than quietly replaced — **19b:**
the *compaction snapshot* argument was wrong (`precompact-snapshot.sh` runs only as the `PreCompact`
hook, `hooks/hooks.json:101`, where the variable **is** set, so the snapshot is written), so the
maintainer's *"I don't want 0s"* report is **not yet diagnosed** and this plan no longer claims to fix
it; **21:** the replacement anchor was *also* wrong — it cited `COREDEV-2585` §4.5b, which **does not
exist in this tree** (that plan is 567 lines here, `### 4.5` at `:195`, zero hits for `4.5b` or `Bash`;
§4.5b lives only on the unmerged, ungated 2585 branch). **The anchor is ONE live consumer class** — git
hooks, observed emitting D′'s diagnostic during a real `pre-commit` run — **plus one withdrawn and one
prospective.** *(Round 30: this said "three consumer classes" for a full round after §4.2a had reduced
the count, which is the half-a-family the HEADER RULE above now forbids.)* **§4.2a amends §4.1's enum, N1/N2, §5's inert-gate row and §7's
`sessionstart-restore.sh` row — each called out in place; §4.3, §4.4 and the D′ envelope stand.** Previously — **round 18: SECOND FULL DOUBLE APPROVAL (gemini `APPROVE` + codex `APPROVE`) — AND THE SECOND TO FAIL REPRODUCTION.** The re-run at byte-identical bytes flipped to `REQUEST_CHANGES` and found a real **fail-open → fail-closed regression**: the agent fence has **no inline fallback**, so with `paths.sh` absent the round-17 helper never set `_UNLEASHED_BASE_OK` and round-17's "unset ⇒ unresolved" made the fence emit `NO CAPTURE` **on a valid base**. The helper now always establishes the flag and emits the single diagnostic; flag-branching is scoped to consumers whose control flow actually diverges. **Two double approvals, two reproduction failures, two sets of real defects.** See §27. Previously — **round 17 (both arms): the helper body I wrote in round 16 crashes in absent-file mode.** It sourced `paths.sh` **unconditionally** — Bash returns 1, zsh 127, the sentinel is never established, and an `errexit` caller terminates — contradicting §4.3's non-load-bearing contract that every shipped lib honours with a `[ -r … ] &&` guard four lines away in `marker.sh`. Also closed: **consumers now branch on `_UNLEASHED_BASE_OK`** to detect the unresolved state, which the plan had never specified while forbidding sentinel string comparison. See §26. Previously — **round 16: codex `APPROVE` (0 findings, SECOND consecutive) · gemini `REQUEST_CHANGES` ×1 — not a pass.** codex traced the corrected bridge end to end in **both shells**, including the empty-`$1` path. gemini's finding stands anyway: the helper's **body was never written down**, only derivable — so the four-line body is now in the plan, with the note that it needs **no conditional of its own** because `paths.sh`'s `:-` makes empty and unset the same branch. *codex asks whether a behaviour is derivable; gemini asks whether it is written. A specification needs the second.* See §25. Previously — **round 15 (codex `REQUEST_CHANGES` ×1; gemini arm did not run — quota): the bridge's self-location was Bash-only.** `${BASH_SOURCE[0]%/*}` fails in **zsh**, which is exactly the shell this repo documents for the agent-fence path. The fence now **passes the root as `$2`** and the helper does `. "$2/scripts/lib/paths.sh"` — cross-shell by construction. codex confirmed the substitution path and N5's allowlist sound. **Third round running in which my own response-to-a-finding mechanism was defective**, each time checkable against evidence already in this repo. See §24. Previously — **round 14 (both arms): the bridge helper I specified in round 13 COULD NOT WORK.** gemini: unbraced `$CLAUDE_PLUGIN_ROOT` is **unset** in a Bash-tool shell, so the `source` line would have crashed the fence. codex, deeper: **`${CLAUDE_PLUGIN_DATA}` inside a sourced `.sh` is not agent content**, gets no substitution, and the helper would export **empty** — re-creating this ticket's own defect. The fence now **passes the value in** (`source "${CLAUDE_PLUGIN_ROOT}/…/agent-env-bridge.sh" "${CLAUDE_PLUGIN_DATA}"`, both exact tokens in agent content), the helper takes `$1` and finds `paths.sh` via `${BASH_SOURCE[0]%/*}`, and **N5 retains the fence sites**. See §23. Previously — **round 13: codex `APPROVE` (0 findings, its first outright approve) · gemini `REQUEST_CHANGES` (2 High) — not a pass.** codex traced the whole plan clean. gemini found two **specification gaps** a mechanism trace cannot surface: the **bridge helper D′ requires was never specified** (now `scripts/lib/agent-env-bridge.sh`, with N5's allowlist gaining it and losing the two fence copies), and **§4.1's enum listed the state space of the REJECTED options** (`derived-registry`/`legacy-fallback` are unreachable under D′; it is now `host-env`/`unresolved`). See §22. Previously — **round 12: FIRST DOUBLE APPROVAL (gemini `APPROVE` + codex `APPROVE_WITH_NOTES`) — AND IT DID NOT REPRODUCE.** Re-run at the **byte-identical** digest: gemini flipped to `REQUEST_CHANGES` and **found a real defect the approving run had certified clean** — five executable consumers (three log hooks, both capture hooks) had **no unresolved-base control flow at all**, sitting in a bullet list while step 5 demands one per consumer. All five are now table rows; the bullet list is **non-executable sites** only. codex held `APPROVE_WITH_NOTES` across both runs. **The maintainer's reproduce-at-the-same-digest rule paid for itself.** See §21. Previously — **round 11 gated: codex `APPROVE_WITH_NOTES` (1 Low) for the SECOND round running; gemini FAILED to emit a verdict line for the second round running — NOT A PASS.** codex traced all four directed checks clean: consumer scope complete, the mutator rule naming only real mutators, the envelope oracle holding for both new consumers, and N5 narrowed consistently through step 7. The one Low was terminology — `sessionstart-restore.sh` reads and deletes the snapshot, it does not write it. **gemini's failure is a CAPTURE failure, not a review failure** (a ~1 KB summary claiming it printed a critique it did not); both failures are on this ticket, the one where its answer is affirmative. See §20. Previously — **round 10 gated: codex `APPROVE_WITH_NOTES` (1 Low), gemini FAILED (no verdict line) — NOT A PASS.** The round-9 narrowing **held**: codex traced every production read back to an envelope return, found the envelope exhaustive and the `_UNLEASHED_BASE_OK` protocol correct, and raised only the CHANGELOG omission. gemini's arm wrote its critique to a file instead of stdout, so it must be re-run; its findings were triaged anyway and two were real — **there are no `context_snapshot*` writers** (that phrase is struck) and **`precompact-snapshot.sh`/`sessionstart-restore.sh` were absent from the consumer table** (both added). See §19. Previously — **round 9 gated** (**gemini `REQUEST_CHANGES` 5 High · codex `REQUEST_CHANGES` 1 High**). **Fourth consecutive round with a failed proof mechanism, so the claim is NARROWED rather than patched a fifth time.** codex **executed** a bypass with no lexical expansion at all (`n=CLAUDE_PLUGIN_; n="${n}DATA"; printenv "$n"`), proving path provenance is **not statically decidable in Bash**: N5 is now stated as a **lexical drift detector**, explicitly not a proof of accessor-only provenance — the §3.1 move from COREDEV-2497. The oracle asserts on the envelope's **printed return values** (readers' locals are invisible; `_context_round_advance` composes inline as a `python3` argv), and the one-diagnostic-per-process rule is guarded by the shared `_UNLEASHED_BASE_OK` flag so it holds with `paths.sh` absent. Two gemini Highs **rejected with reasons**. See §18. Previously — **round 8 gated** (**gemini `REQUEST_CHANGES` 5 High + 1 Medium · codex `REQUEST_CHANGES` 2 High**). **Round 7 rejected the canary as physically impossible; round 8 rejects its replacement as mechanically impossible** — a Bash shim cannot observe `read < "$path"` (the shell opens before the command runs) or pathname globbing. The oracle now asserts on the **composed path**, which is observable, and leans on the sentinel's executed `ENOTDIR` physics for the rest. **N5 is inverted from a shape blacklist to an enumerated allowlist** — both reviewers bypassed the round-7 predicate in one line each, and round 7's mutant used the one form it already caught. `_context_round_sweep` was missing from **both** the reader and mutator lists. See §17. Previously — **round 7 gated** (**gemini `REQUEST_CHANGES` 1 High + 1 Medium · codex
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
root; the consumer enumeration is now in the implementation order. Rounds 1-18 are in §10-§27.
**Ticket:** `COREDEV-2617` (Epic `COREDEV-2485`) · **High** — a live defect, reproduced on this machine
**Last Updated:** 2026-07-31 (round 18, post-gate revision — helper always sets the flag; branching scoped)
**Measured against:** HEAD `b2496a8` (v2.6.4), worktree `.claude/worktrees/opus5-review`, plugin `2.6.4`

---

## 1. The defect, reproduced — **as it stood BEFORE D′ shipped**

> **ROUND 30 — THIS SECTION WAS WRITTEN IN THE PRESENT TENSE ABOUT CODE THAT NO LONGER EXISTS, AND IT
> IS THE EVIDENCE BASE THE WHOLE PLAN RESTS ON.** It said the expansion "appears in four shell
> libraries" and cited four live line numbers. **D′ shipped in 2.6.5 and removed three of them**
> (`f4ad405`, *"implement D′ — an unresolved plugin-data base persists nothing"*).
>
> **The citations were not fabricated — they were exact, at the wrong commit.** Measured against
> `f4ad405^` (= `8881b6a`): `marker.sh:29`, `log.sh:27` and `context.sh:36` each hold the expansion
> verbatim. Measured at HEAD: those lines hold shellcheck directives and comments, and the string does
> not occur in those three files at all. This is a *fourth* distinct citation failure mode on this
> ticket — not a wrong number, not a nonexistent section, but **a correct citation to a superseded
> tree**, which is the same shape as the round-28 wrong-worktree error one axis over.
>
> **A green test already asserts the correction.** `scripts/tests/test_shell_primitive_drift.py:118`,
> `test_legacy_expansion_survives_only_in_paths_sh`, passes at HEAD (`Ran 11 tests … OK`). So §1 as
> written asserted the negation of a currently-passing gate in its own suite, and neither review arm
> caught it across ten rounds — because reviewers check whether a claim is *supported*, not whether it
> is *still true*. Grep the target file's history before trusting a present-tense claim about it.

**Before D′** (at `f4ad405^`), every persistent artefact the plugin writes — quality markers, logs,
reviewer captures, Stop-gate state — resolved its base directory through one expansion, carried
independently by **four** shell libraries:

```sh
printf '%s' "${CLAUDE_PLUGIN_DATA:-${HOME:-}/.claude/unleashed-mail}"
```

`scripts/lib/paths.sh` · `scripts/lib/marker.sh:29` · `scripts/lib/log.sh:27` ·
`scripts/lib/context.sh:36` — **all at `f4ad405^`, not at HEAD.**

**At HEAD it survives in exactly one place**, `scripts/lib/paths.sh:62-64`, inside
`unleashed_plugin_legacy_base()`, whose own comment reads *"The pre-2617 expansion. Kept **ONLY** so the
drift matrix can assert the legacy behaviour it documents; **no primitive calls it**."* That is D′
working as specified. **The split this section describes is therefore history, not a live defect** —
which is exactly why §4.2a is capability work rather than a fix.

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
> reason). An absolute base path contains the username and home directory. Record an **enum** — never the
> path.
>
> **Round 13 — the enum's vocabulary is `host-env` / `unresolved`, and ONLY those.** *(gemini: this
> listed `host-env` / `derived-registry` / `legacy-fallback`, which were the states of the **rejected**
> options A and B. Under the adopted **D′** the base resolves **only** when `CLAUDE_PLUGIN_DATA` is set,
> so `derived-registry` and `legacy-fallback` are unreachable — and an implementer told to write an enum
> for them could reasonably conclude the rejected options are still live. The enum must describe D′'s
> actual state space: resolved from the host environment, or unresolved.)* The `unresolved` value is
> written **only** where a record is written at all — which under D′ is nowhere, so in practice the enum
> is always `host-env` in a persisted record and `unresolved` exists solely for the source-time
> diagnostic. Extra marker fields are
> parser-safe (the reader selects named keys, `marker.sh:150`).
>
> **Round 19b, narrowed in round 21 — AMENDED BY §4.2a: the vocabulary is now THREE values.** Round 13's
> reasoning was sound *for D′*, where the base resolves only when the variable is set. **D″ makes one
> further resolution reachable — a published pointer — and it sets `OK=1`, so it persists records.** Left
> at two values, such a record would be stamped `host-env`: a record that **lies about its provenance**,
> which is worse than the silence this section was written to fix, and is this ticket's founding defect
> (§2) with the label now vouching for the wrong half. The vocabulary is therefore
> `host-env` / `pointer` / `unresolved`, carried by a fourth protocol variable `_UNLEASHED_BASE_SOURCE`
> set beside `_UNLEASHED_BASE_OK` in each of the five shell family files. `_UNLEASHED_BASE_OK` stays
> **binary** and stays the only sanctioned resolved/unresolved test — consumers branch on it, never on
> the source enum.
>
> *(19b proposed a fourth value, `home-fallback`, for a `$HOME` fallback step. The round-20 gate dropped
> that step on both arms, so the value is not needed. N6 carries a `stamp host-env for a pointer
> resolution` mutant — round 20 found the provenance stamping had no adversarial case at all, though it
> is this amendment's entire rationale.)*
>
> **Round 25 — §4.2a's pointer file is an EXPLICIT, BOUNDED EXCEPTION to "never the path" (codex #11).**
> The rule above forbids recording the base directory because it contains the username. D″'s pointer
> stores exactly that absolute path, so the two must be reconciled rather than left to collide:
> * **What the rule protects is the RECORD** — markers, logs, snapshots. Those are read back, aggregated,
>   and can travel. They keep the enum and never the path; D″ does not change that.
> * **The pointer is a control file, not a record.** It is `0600`, in a `0700` directory the same user
>   owns, never read into a marker or log, never emitted to stderr, and never injected into the model's
>   context. It carries the path and nothing else.
> * The username is already present in that pathname's own location, so the pointer discloses nothing to
>   anyone who can read it that they did not already have.
>
> **This exception is deliberate and is bounded to that one file.** Any future control file wanting the
> same latitude needs its own amendment here.
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

> **Round 19b — AMENDED BY §4.2a, in both directions.** As written, N1 is falsified by D″ twice, and the
> first draft of §4.2a patched the *tests* to keep passing while leaving this text untouched — moving the
> oracle to fit the code. Stated honestly:
>
> *(Rewritten in round 23. The round-19b version of this note described a `$HOME` fallback step and a
> "step 4", both of which the round-20 gate removed — it was left standing when §4.1's sibling enum note
> was updated, so §4.1 carried **two** normative N1/N2 definitions at once. codex found it. That is the
> same half-a-family mistake this campaign keeps recording: the fix is to derive the amendment sites by
> grep, not by memory of which one I just edited.)*
>
> * **Set:** the resolution is **unchanged** — the host base, exactly as D′. Step 1 additionally writes
>   **one** file outside it: its own entry `${HOME}/.claude/unleashed-mail/bases/base.<key>`, containing
>   the base path and nothing else, and only when `HOME` is usable. *"only in the supplied host base"* is no longer
>   literally true of the process's total writes, and is restated below.
> * **Unset or empty:** step 2 performs one bounded, authenticated **read** of that pointer. If it
>   authenticates, the base resolves to the value the authority published — **the same directory the
>   hooks use**, not a second store. If it does not, step 3 is D′'s sentinel and **no plugin-state
>   payload is read or written anywhere**. There is no legacy-path branch.
>
>   *(Round 25, codex #2: the round-23 wording said "nothing is read or written anywhere", which is
>   **impossible** — an invalid pointer cannot be rejected without reading it, so the invariant
>   contradicted step 2 in the same section. The bounded pointer read is the **one explicit exception**:
>   at most two lines from one fixed path, never repository or user content, and never anything that
>   reaches a consumer. Everything D′ meant by "no persistence" is preserved; the sentence was simply
>   stronger than the truth. N1/N2/N6 oracles assert the narrowed form.)*
> * So the no-persistence trigger is no longer *"variable unset"* alone but **"variable unset **and** no
>   authenticated pointer"**. §5's inert-gate mitigation is amended in place for this: a fixture that
>   sets **either** the variable or a pointer no longer reproduces the defect.
>
> **The invariant that survives, and which N1/N2 now assert:** no state is written to any base other than
> the one the resolution returns; the single exception is this publisher's own entry in the store; and when resolution fails,
> **no plugin-state payload is read or written anywhere** — the bounded pointer read being the one
> exception, since an invalid pointer cannot be rejected without reading it.

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

### 4.2a — D″: a pointer so non-hook shells can resolve the base — **PROSPECTIVE CAPABILITY, not a defect fix**

> **WHAT THIS SECTION IS, stated before anything else** (round 29, codex #7; maintainer approved).
> Through round 28 this section was headed *"the unresolved case is silent, and silence was not the
> goal (High)"* and read as the remedy for an observed failure. **It is not, and the evidence no longer
> supports that framing.** Of the four motivations it has carried, three are withdrawn — the compaction
> snapshot (refuted by code-reading in 19b and **by executing a compaction** in round 28), the
> hand-run/CI shell class (withdrawn round 23, never traced), and a dependency on a section of another
> plan that **does not exist in this tree**. The maintainer's "0s" report **remains undiagnosed**, and
> nothing here claims to fix it. What survives is one live consumer class (git hooks, observed below)
> whose writes the gate already treats as harmless, and one prospective consumer with no code yet.
>
> **So D″ is capability work: it makes the plugin's state base resolvable from shells that never
> receive `CLAUDE_PLUGIN_DATA`.** That is a real and growing gap, and the maintainer has decided to
> build it. Framing it honestly costs nothing and prevents the severity from doing argumentative work
> the evidence cannot.
>
> **Acceptance criterion, so "done" is decidable rather than argued:** a shell with no
> `CLAUDE_PLUGIN_DATA` and no hook environment resolves the *same* base a hook resolves, or fails
> closed with one diagnostic and `OK=0` — with N6's mutant set green, and with **no change to D′'s
> behaviour when the variable is set** (row 19 is the standing guard on that). Anything short of this
> is not a partial success; it is the ambiguous second store this ticket exists to remove.

**Round 28 gated this section; both arms returned `REQUEST_CHANGES` and their findings are applied
below as round 29.** Round 20's findings were applied as round 21, and its open question is CLOSED —
see "Step 3 is dropped".

**Maintainer report, 2026-08-08:** *"please fix the compaction fall back safety, I don't want 0s."*
D′ shipped in **2.6.5** (`CHANGELOG.md:1045-1049`) and remains in 2.7.x; it works exactly as
specified. The specification is what needs amending. *(Round 25: this said "2.7.0", a different
release — `CHANGELOG.md:238`.)*

> **ROUND 19b — THE MOTIVATION THIS SECTION OPENED WITH WAS WRONG, AND IS REPLACED.** The first draft
> argued from the compaction snapshot: *"the compaction snapshot … is therefore not written at all in any
> non-hook-provisioned shell."* **That inference does not hold.** `precompact-snapshot.sh` has exactly one
> executable invoker — `hooks/hooks.json:101`, the `PreCompact` hook — and `sessionstart-restore.sh`
> exactly one, `hooks.json:113` under `SessionStart`. Every other occurrence is prose (`README.md:463`)
> or a file-presence check (`scripts/ci-load-check.sh:98-101`). Since §1 (`:129-135`) establishes that
> `CLAUDE_PLUGIN_DATA` **is** exported to hook invocations, `unleashed_base_ok` at
> `precompact-snapshot.sh:53` is true whenever that script runs, and **the snapshot is written**. Both
> round-20 arms independently re-verified this.
>
> **The maintainer's report is therefore NOT yet diagnosed, and this section does not claim to fix it.**
> Two candidate causes were left open: (a) `PreCompact` is not firing in the affected repository; or (b)
> a consumer other than the two snapshot scripts is being observed.

> **ROUND 28 — candidate (a) is REFUTED, by execution. The compaction chain works end to end.**
> Round 20 recorded that *"the `unleashed-mail` install is **project**-scoped and bound to the app repo,
> so no plugin hook fires in this repo or its worktrees"*, attributed to kimi's read of
> `installed_plugins.json`. **That read saw one of two entries.** Re-measured 2026-08-09 against the same
> file: `plugins["unleashed-mail@npranson-unleashed-mail-plugin"]` is an **array of two** installations —
> a `"scope": "user"` entry with **no `projectPath`** (`installPath` …/`2.7.0`, `lastUpdated`
> `2026-08-09T05:34:46.154Z`) *and* the `"scope": "project"` entry bound to the app repo. A user-scope
> install is unbound, so **plugin hooks do fire here.**
>
> Then the chain was executed rather than argued about, by compacting a live session in this repo on
> 2026-08-09 and recording the before-state first (**zero** snapshots had ever been written; newest
> `.state` write `Jul 29 23:57`; repo hash `e7d5478ad109`):
>
> | link | observed |
> |---|---|
> | `PreCompact` ran | `PreCompact [bash "${CLAUDE_PLUGIN_ROOT}/scripts/precompact-snapshot.sh"] completed successfully` |
> | it wrote the snapshot | `.state` directory `mtime` advanced to `22:34:04` — a create+unlink in that directory |
> | `SessionStart` restored it | the `additionalContext` hint was delivered verbatim into the model's context |
> | restore consumed it | no `work-context-snapshot-*` remains, per the `rm -f "$SNAP"` at `sessionstart-restore.sh:85` |
>
> **This also confirms, by execution, the premise D′ rests on:** the snapshot landed **inside the plugin
> data dir**, so `unleashed_base_ok` was true, so the hook really does receive `CLAUDE_PLUGIN_DATA`.
> §1's claim is no longer only a reading of the code.
>
> **What it means for this section.** The compaction motivation is now dead twice over — by code-reading
> in 19b and by experiment here — and candidate (a) cannot be the explanation for the maintainer's
> report. The honest position is that **the "0s" report remains undiagnosed**, and D″ is not justified by
> it. What the run *did* expose is unrelated to D′: the restored hint named `ticket=unknown`,
> `branch=b28b7af69320`, `plan=docs/planning/REVIEW_GATE_WAIVER_DECISION_PLAN.md` — every field correct
> for the code (`context_branch_slug("main")` reproduces that hash exactly) and useless in fact, because
> the session cwd was the main checkout while the work was in a worktree, and "newest `*_PLAN.md` by
> mtime" ties across a fresh checkout. **That is a snapshot-payload defect, not a base-resolution one,
> and it belongs in its own ticket.**

> **ROUND 21 — the round-19b re-anchoring was ALSO wrong, and both arms caught it.** 19b replaced the
> compaction argument with *"`COREDEV-2585` §4.5b is blocked on exactly this"*. **In this tree there is
> no §4.5b.** `docs/planning/DECISION_JOURNAL_PLAN.md` here is 567 lines, its sections are `### 4.1`–
> `### 4.12` with no lettered subsections, `### 4.5` is at `:195`, and fixed-string greps for `4.5b` and
> for `Bash` return **zero** hits. §4.5b exists only on the unmerged branch
> `feat/COREDEV-2585-decision-journal`, which is **itself ungated**.
>
> **That is the draft's own defect committed one layer down** — anchoring to a consumer the reader cannot
> verify — and it is the reason this note exists rather than a quiet edit. The corrected anchor is below,
> and it cites only bytes present in this tree.

**What D″ is actually for — anchored in this tree.** `CLAUDE_PLUGIN_DATA` reaches hooks and MCP
subprocesses but **not an ordinary shell** (`scripts/lib/paths.sh:22-25`, and §1 `:77`). Reproduced in a
live Bash-tool call at `dbb1fb8`:

```
CLAUDE_PLUGIN_DATA = [UNSET]
base=/dev/null/unresolved-plugin-base   ok=0
```

**One traced live consumer class, plus one prospective** — and neither is the compaction snapshot.
*(Round 21 claimed three. Round 23 withdrew the middle one but wrote "two live … plus one prospective",
which was still wrong — codex #9 counted the list. The honest count is one live, one withdrawn, one
prospective. **If no second live member can be traced from actual bytes, that is itself the most
important fact about this section**, and it is stated here rather than absorbed into a count.)*

1. **Git hooks.** `scripts/pre-commit-checks.sh:14-18` states the condition in its own comment: a git
   hook does not inherit the variable, so *"the writes are a **harmless local no-op for the gate**"*.

   > **OBSERVED, not merely read (round 28).** The commit carrying this round printed, from the
   > `.githooks/pre-commit` shell and before any validator output:
   >
   > ```
   > unleashed-mail: CLAUDE_PLUGIN_DATA is unset; plugin state will not be read or written this run
   > ```
   >
   > That is D′'s single diagnostic firing in a real git-hook invocation on this machine. **This is the
   > one live consumer class this section rests on, and it is now evidenced by execution rather than by
   > reading a comment** — which matters precisely because the three motivations beside it were all
   > retracted for being asserted rather than traced.

   Round 2 (`:347-353`) rejected the A+D hybrid partly on this consumer's account, and that reasoning was
   sound **for the gate's purposes**; what it did not license was generalising "harmless here" to every
   consumer. *(Round 21: 19b paraphrased this as "already documented as unreachable no-ops". The bytes
   say "a harmless local no-op **for the gate**" — the writes were never unreachable, only invisible to
   the gate. The paraphrase is corrected here and the distinction matters, because under step 2 they
   become visible to the gate with no export at all.)*
2. ~~**Hand-run `scripts/*.sh` and CI shells**, which have no hook environment at all.~~
   **WITHDRAWN in round 23 (codex #6) — asserted, never traced.** Checked: CI runs the isolated harness
   (`.github/workflows/plugin-ci.yml:201-203,423-429`), which **exports its own temporary**
   `CLAUDE_PLUGIN_DATA` (`scripts/test-hooks.sh:31-35`), so CI is not affected; and the Bash-tool state
   reader already **bridges the authoritative value explicitly** (`agents/swift-reviewer.md:180-193`).
   Neither is a live harmed consumer. **A class with no traced member is not evidence**, and this is the
   third motivation defect on this section — the two before it were a wrong consumer and a nonexistent
   section, both of the same shape: a claim that reads as verified because it is specific. Withdrawn
   rather than patched.
3. **A model-written state path.** `docs/planning/DECISION_JOURNAL_PLAN.md:51` scopes the journal as
   *"written: at a checkpoint, by the model"* and `:64` puts *"the model-written write path"* in scope.
   **Stated honestly: on this branch that plan specifies no writer command, no invocation mechanism, and
   no writer exists in the tree** (`grep -rln journal scripts/` returns nothing). The concrete §4.5b
   mechanism — a script the model invokes through the ordinary `Bash` tool — lives only on the unmerged,
   ungated 2585 branch. **So this is a prospective consumer, not a live blocker**, and D″ must not be
   justified by it. It is recorded because it shows the class is real and growing, not as evidence.

**The load-bearing claim, and round 20's attempt on it.** kimi attacked the "derives nothing"
distinction directly and **could not break it** for steps 1-2: the pointer imports the variable's value
verbatim, so no registry / `CLAUDE_CONFIG_DIR` / cache-root / `--plugin-dir` ambiguity attaches to
*reading* it, and a relocated config still converges because the pointer's **content**, not its location,
carries the data dir. The distinction holds. Ambiguity re-enters only through the **publish policy** under
multiple install ids — a policy hole, closed below, not a derivation.

**Do NOT simply restore the fallback.** Re-measured 2026-08-08 — there are **three** bases on this
machine, not two:

| base | files | last write |
|---|---|---|
| `~/.claude/unleashed-mail` (whole tree; `.state` holds 20 of these) | 21 | **Jul 17 15:58** |
| `~/.claude/plugins/data/unleashed-mail-npranson-unleashed-mail-plugin` | 76 | live |
| `~/.claude/plugins/data/unleashed-mail-inline` | 1 | stray — a hook once ran under this id |

> Row 1 previously labelled `.state` while counting the whole tree. `.state` holds **20** files; the
> 21st is `logs/build-log.jsonl`. The "frozen Jul 17" reading stands (newest write `15:58`).

That third directory is also why **option B (globbing) stays rejected**: two entries still match
`unleashed-mail-*`, exactly as round 1 found — and it is why the publish policy below is fail-closed.

## The amendment — D″, a three-step resolution (`HOME` gates only the pointer)

> **Step 0 — `HOME` gates the POINTER PATH, never the resolution.**
> `_UNLEASHED_HOME_OK` is set once: true iff `HOME` is non-empty and absolute
> (`case "${HOME:-}" in /*) ;; *) … esac`). It decides only whether a `${HOME}`-rooted path may be
> **composed, read or written**. It has **no** bearing on whether `CLAUDE_PLUGIN_DATA` resolves.
>
> **ROUND 23 — the round-21 wording of this guard was a fail-open → fail-closed inversion, and codex
> caught it.** It read *"validate `HOME` FIRST … `*) → step 3`"*, which sent a shell with a **valid,
> authoritative `CLAUDE_PLUGIN_DATA`** but an empty or relative `HOME` to the sentinel — discarding the
> one value §4.2 calls *"the only authoritative identity"* because of an unrelated variable.
> `scripts/lib/paths.sh:68-74` resolves every non-empty value without consulting `HOME` today, so that
> would have silently invalidated D′ and N1's set-variable arm. **This is the third fail-open →
> fail-closed inversion on this ticket** (round 17's unconditional source, round 18's agent fence), and
> the first two were both caught by a reproduction rather than by review. The rule that prevents a
> fourth: *the guard on a side effect must never be able to change the primary result.*
>
> The hazard it was written for is still real and is still closed: with `HOME=""` — *the value the TEST
> TRAP itself prescribes* — the round-19b draft composed and read `/.claude/…`, and its publish would
> have attempted to **create `/.claude`**, which succeeds in a root-writable CI container. Under the
> corrected guard that publish is simply skipped. It also preserves the `${HOME:-}` form `paths.sh:51`
> documents as load-bearing: a bare `${HOME}` under the `set -u` every hook uses aborts the hook.
>
> **zsh asymmetry, verified by execution (round 20, kimi #10):** `env -u HOME zsh -c …` **repopulates**
> `HOME` from passwd, while bash leaves it unset. `HOME=""` and relative values fall through in both
> shells. So `HOME=""` is the only portable spelling of "force the unresolved case" — a future zsh cell
> that *unsets* `HOME` would silently test the passwd home instead of the guard.

1. `CLAUDE_PLUGIN_DATA` non-empty → **use it, `OK=1`, source `host-env`. Unconditionally — this branch
   never consults `HOME` and never fails.** D′'s set-variable behaviour is untouched.

   *Then, as a **side effect that cannot affect the line above**:* if `_UNLEASHED_HOME_OK`, publish
   **this publisher's own entry** `${HOME}/.claude/unleashed-mail/bases/base.<key>`, where `<key>` is the
   injective encoding of that absolute path — written atomically (tmp + `mv` **in the same directory**),
   fully suppressed, `0600`, into a store created by a single `mkdir -m 700`. Publish **unless** the entry
   already authenticates under the shared predicate **and** its content equals the value — the complete
   reader predicate, not a weaker type-and-content test, so a `0644` or symlinked entry is repaired rather
   than reported `current` and then refused by step 2. If `_UNLEASHED_HOME_OK` is false, or the publish
   fails for any reason, **no `${HOME}` path is composed or opened at all**,
   `_UNLEASHED_POINTER_STATE=failed`, and the resolution above still stands.

   *(**Round 31 — this step still described the SINGLETON pointer for a full round after round 30
   replaced it**, so the operative algorithm and its own store disagreed. codex High #2. It is the fifth
   half-a-family on this ticket and the largest: a redesign applied to one section and not propagated.
   Every site naming the old single `base` file is corrected in the same commit, derived by grep rather
   than recalled.)*

   **`created` and `current` must mean the FOLLOWER can use it** (round 25, codex #5). The skip test and
   the follower's test were different, so a pointer at mode `0644` — a regular non-symlink file with
   matching content — made the publisher report `current` while step 2 rejected it, and SessionStart
   stayed silent because it only speaks on `conflict`/`stale`/`failed`. Worse, `paths.sh:69-71` accepts any
   non-empty `CLAUDE_PLUGIN_DATA` without proving it absolute, so a relative value could be published and
   then refused by every reader. **So the publisher runs the COMPLETE follower authentication against the
   pointer it is about to leave in place — the no-write `current` path included — and sets `failed` if it
   would not authenticate.** One predicate, used by both sides; a second predicate is a second source of
   truth. N6 mutates the skip test to the weaker form and requires `failed`.
2. else, **and only if `_UNLEASHED_HOME_OK`**, read that pointer. Accept only if it passes **full
   authentication** (below) → use it, `OK=1`, source `pointer`.
3. else sentinel, `OK=0`, source `unresolved`, one diagnostic. **D′'s fail-closed protocol byte for
   byte.**

### Step 3 is DROPPED — the round-20 gate closed the open question

Rounds 19/19b carried a fourth step: *"else `${HOME}/.claude/unleashed-mail` when `HOME` is absolute"*,
deliberately left open. **Both round-20 arms independently answered DROP, with different reasoning, and
that concordance is the decision.** Recorded because the reasoning constrains future rounds:

* **codex** — step 3 recreates the pre-D′ split before first publication and reactivates the quarantined
  legacy store, and is unnecessary once any authoritative hook has published. *"A project-scope
  installation under which no hooks run is a registration defect, not justification for restoring an
  ambiguous store globally."*
* **kimi** — took the re-anchored motivation on its own terms and found step 3 **fails it**: a
  model-written checkpoint made before the first hook run would land in `${HOME}/.claude/unleashed-mail`
  and every one after it in the plugin data dir via step 2, so the store **splits by time** and neither
  side can ever see the early half. Step 3 does not give a blocked consumer a degraded store — it gives
  it *"a store that is guaranteed to become invisible to its own reader the moment the mechanism works."*
  A diagnosed no-op is strictly more recoverable than a durable write into a store on a countdown to
  orphanhood.

**Consequences, all simplifications:** §4.3's round-6 mandate (`:1242`) and its matrix change (`:1248-1252`)
stand **exactly as written**; §4.4's quarantine premise and ordering (`:1275-1282`) stand as written;
`test_shell_primitive_drift.py`'s `MATRIX` keeps all four rows unchanged, so the 12 subtests rounds
19b/20 costed **do not flip**; and the resolution enum needs no `home-fallback` value.

**If the never-run-a-hook window must be covered**, both arms named the honest mechanism: an **explicit
publish** — the installer or a first-run step writes the pointer deliberately — not a silent read-time
fallback. That is out of scope here and is recorded as **§8 Q7** (added by this round) rather than decided
silently. *(Round 21 cited "§8 Q5", which is N2 — the question did not exist. Round 23 adds it.)*

### Publish policy under multiple install ids — **the lock is DELETED; names carry the values**

> **ROUND 30 — THE LOCK IS REMOVED, NOT REPAIRED. Two rounds tried to make it correct and both were
> wrong in kind.** Round 28 treated `mtime` age as evidence of abandonment. Round 29 replaced that with
> a fence token plus a rename and called it compare-and-swap; codex showed `rename()` is keyed on a
> **path** and has no predicate on the renamed directory's contents, so a breaker can rename away a lock
> created *after* its own read and discover the mismatch only afterwards — with release also by path,
> the stolen holder's release then removes the next holder's lock and the violation cascades.
>
> **The deeper reason no third attempt was made.** Executed on this machine: a `trap` set inside a
> shell function fires at **function return in zsh** and at **process exit in bash**; and a shell has
> **one `EXIT` trap slot**, which the caller usually already owns — `scripts/test-hooks.sh` installs
> `trap cleanup EXIT` (`rm -rf "$TMPROOT"`) *before* sourcing `marker.sh` and `context.sh`. All five
> family files are sourced libraries. **A lock that cannot be reliably released is not a lock**, and
> nothing in POSIX shell offers an atomic conditional *delete* to reclaim one safely. So the design
> stops needing mutual exclusion instead of pretending to achieve it.

**The mechanism: one entry per distinct base value, named by that value.** The store is
`${HOME}/.claude/unleashed-mail/bases/`, created `mkdir -m 700` — one call, so there is no
create-then-`chmod` window in which a second publisher stats a `0755` directory and spuriously refuses.
Each publisher writes exactly one file:

```
${HOME}/.claude/unleashed-mail/bases/base.<key>      key = an injective encoding of the base value
${HOME}/.claude/unleashed-mail/bases/.pub.<pid>.<key>  transient; outside the base.* glob by construction
```

**Invariant P — the name is a pure function of the bytes.** `_k=${_v//_/_u}` then `_k=${_k//\//_s}`.
Escape the escape character **first**: measured, the swapped order maps both `/a/b` and `/a_sb` to
`_usa_usb`, and a collision is two bases sharing one entry — last-writer-wins with no detection, the
exact defect this design exists to remove. Two portability traps, both measured, both silent:
`${v//%/%25}` is **not portable** (bash 3.2.57 yields `/a%25b/c_d/e`; zsh 5.9 yields `/a%b/c_d/e%25`),
and quoting the delimiter as `${v//"/"/"%2F"}` is a **no-op in both shells**. The `_`-escape form above
was executed in both and produced identical output. Derivation is a plain assignment, never
`k="$(...)"` — command substitution forks, and this runs at source time in every hook.

**Why this removes the lock rather than hiding it.** Different base values produce different keys,
therefore different paths, therefore **no two publishers holding DIFFERENT bases ever write the same
file** — and it is only *different* bases that a lock was ever needed to arbitrate. There is no critical
section, so there is nothing to serialise, nothing to release, and no trap.

> **Two publishers holding the SAME base do target the same entry, and that is safe — but the round-30
> wording claimed more than it could** (round 31, codex High #3). It said *"no two publishers ever write
> the same file"*, without the qualifier; same-base publishers necessarily converge on one name. That is
> harmless because the bytes are identical and `mv` is atomic, so either order yields the same content —
> **but it must be stated, not hidden by an over-strong claim.**
>
> **The temporary name must not use `$$` alone.** Measured: concurrent subshells inherit the **same
> `$$`** in both bash and zsh, so two same-base publishers could open the same temp inode and one could
> rename it away while the other was still writing — reintroducing the torn read the tmp+`mv` idiom
> exists to prevent. The temp name is `.pub.<pid>.<monotonic-unique-suffix>.<key>`, where the suffix is
> derived without a fork and without `$RANDOM` (absent in POSIX `sh`); a publisher that cannot obtain a
> unique temp name **does not publish** and reports `failed`. N6 carries a same-base concurrent-publish
> case and a mutant that reverts the temp name to `$$` alone.

**Conflict is a property of the directory, read at resolution time.** It is not a state one publisher
writes for another to find, so the `CONFLICTED` wire form, its stickiness rule, the
preserve-the-marker precondition, and operator-recovery-by-deletion all **go away**. A reader
enumerates `base.*`, authenticates each, and:

**The rules are ORDERED and the order is normative** — evaluate top to bottom, first match wins:

1. **any entry fails authentication** → refuse: sentinel, `OK=0`, `SOURCE=unresolved`,
   `POINTER_STATE=stale`, one diagnostic. *A malformed entry is never ignored in favour of a good one.*
2. **two or more authenticating entries** → refuse: sentinel, `OK=0`, `SOURCE=unresolved`,
   `POINTER_STATE=conflict`, one diagnostic **naming the entries, never the raw targets** — §4.1 permits
   the raw path only inside the control file and states it is never emitted to stderr, so a conflict
   message quoting two absolute paths would leak the username and hand attacker-controlled text to a
   terminal (round 31, codex #8). N6 carries a redaction mutant;
3. **exactly one** → resolve to it, `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`;
4. **none** → step 3 verbatim — D′'s fail-closed protocol byte for byte, `POINTER_STATE=none`.

> **ROUND 31 — THE RULES WERE UNORDERED AND TWO OF THEM OVERLAPPED** (codex High #5 and gemini #2,
> concordant). One valid entry beside one malformed entry matched *both* "exactly one" and "any entry
> fails authentication"; two valid plus one malformed matched both `conflict` and `stale`. **Branch order
> therefore decided the resolution**, and it could differ between the five family copies — five
> implementations of one rule, disagreeing, which is precisely the drift §4.3 exists to prevent.
> Malformed-first is the fail-closed order: a store containing anything the reader cannot authenticate is
> not a store it should resolve from, however many good entries sit beside the bad one. N6 mutates the
> order and requires the one-valid-one-malformed case to refuse.

> **COUNT ENTRIES, NEVER ACCUMULATE TARGET STRINGS** (round 30, correctness judge). The candidate
> design counted distinct targets with a space-delimited accumulator tested by
> `case " $_U_TARGETS " in *" $_L1 "*`. That is broken twice: an unquoted `case` **pattern** makes glob
> metacharacters in a path match as wildcards, and a base containing a space breaks the delimiting —
> so two different bases could be counted as one, **reproducing this ticket's founding defect inside
> the mechanism built to remove it.** It is also unnecessary. Invariant P plus the name↔content check
> means two entries with **different names necessarily hold different values**, and directory entries
> are distinct by definition. *(Round 31, codex High #1: "distinct by definition" is true of the
> DIRECTORY, and the encoding is byte-injective — but **macOS is case-insensitive by default**, which
> `.github/workflows/plugin-ci.yml:419` already recognises, so `/Data/A` and `/Data/a` alias to one
> entry: last write wins, the reader sees one authentic entry, and the loser diverges silently. The
> encoder therefore **case-folds nothing and escapes case**: an upper-case character is encoded as a
> two-character sequence so that distinct bases remain distinct **as pathnames**, not merely as byte
> strings. N6 carries a case-fold collision case, which row 44 — testing substitution order — does not
> cover.)* **So the count of distinct bases IS the count of authenticating entries** —
> no accumulator, no delimiter, no pattern matching, and no dependence on what characters a path
> contains. N6 mutates this back to string accumulation with a space-bearing and a glob-bearing base.

**Authentication is ONE predicate, used by both sides.** `_unleashed_auth_entry` requires: a regular
non-symlink file, euid-owned, mode `0600`; exactly one line; and **`<dir>/base.<key(line)>` equal to the
file's own path** — the name↔content check. That last clause is what makes Invariant P *verifiable*
rather than asserted, and it is the only thing that turns encoder drift between the five family copies
into a loud refusal instead of a second store. The publisher runs the complete reader predicate against
the entry it is about to leave in place, **including on the no-write `current` path** (round 25,
codex #5) — one predicate, both sides; a second predicate is a second source of truth.

**Publish, then scan — in that order.** A publisher that scanned first could, racing another's first
publication, see only itself and report no conflict. Publishing first puts every process's own entry in
the set it observes. One residual is accepted and stated: under strict interleaving A may publish and
scan before B publishes at all, so A's *process* reports `created`; the conflict is nonetheless durable
in the file set, so every later process of either install reports it. **Nothing has to be recorded for
the conflict to survive** — which is precisely why the sticky marker could be deleted.

**Enumeration is safe at source time in both shells — and this is the one construct that can kill the
sourcing shell.** Measured: an unmatched `for _f in "$d"/base.*` under zsh 5.9 prints `no matches found`
and **terminates the script**, which is every machine before its first publication. `setopt
local_options no_nomatch` inside the scanning function suppresses it and zsh restores the option at
function return — verified by execution, including that a later top-level glob still aborted, proving
the option did not leak. bash instead leaves the pattern literal, so `[ -e "$_f" ] || continue` is
required in **both** arms. **This ships in five copies, so N6 asserts the empty-store case under zsh for
each of the five family files independently** — one passing arm is not evidence about the other four.

**Enumerated-then-vanished is a SKIP, not a refusal.** Measured under an adversarial race — 8 concurrent
publishers across bash and zsh with an operator deleting entries in a tight loop, ~480 observations —
there were **0 torn reads** and a handful of vanished observations. `rename()` never makes a destination
absent, so the only cause is an unlink, i.e. operator recovery; re-testing `[ -e "$_f" ]` distinguishes
it. Treating it as malformed would flip a healthy store to `stale` while someone is cleaning up.

**The store lives one level down, and that is load-bearing.** Measured on this machine: `$HOME`,
`~/.claude` and `~/.claude/unleashed-mail` are all `0755`. The plan's *"the pointer's parent must be
exactly `0700`"* rule would therefore **refuse publication on the maintainer's own machine** until §4.4
repaired it. Putting the entries in `bases/` makes the exact-`0700` rule apply only to a directory the
publisher creates and owns, while the ancestors need only the general not-group-or-world-writable rule,
which `0755` satisfies. §4.4's quarantine sweep also stops colliding with live state: it moves *files*
out of `~/.claude/unleashed-mail`, and `bases/` is a directory it never touches.

**Name length is pre-checked.** `getconf NAME_MAX` is 255 here (measured: a 250-character suffix
creates, 260 fails `ENAMETOOLONG`). The publisher checks `${#_k} + 5 <= 240` **before composing any
path**; over budget it writes nothing, reports `failed`, and emits one diagnostic naming the length.
Without the pre-check the failure surfaces as a generic write error and leaves a tmp file behind.

**Stale entries need a human, and that is stated rather than automated.** An install that is removed
leaves its entry behind, and a reader then sees two entries and refuses. There is **no safe automatic
reaper**: a time threshold is the heuristic round 29 already refuted, and being wrong here deletes a
live install's entry. Recovery is `rm` of the obsolete entry, named in the conflict diagnostic.


### Step 2's authentication — the whole chain, not just the file

Round 20 (codex #3, kimi #3) found the trust boundary enforced at the pointer and its parent and then
abandoned at the destination. `sessionstart-restore.sh` injects snapshot fields into the model's context
via `additionalContext` (§7 row `:1501`), so a pointer naming attacker-writable storage is a
**prompt-injection path**, not merely a state-integrity one. Step 2 accepts the pointer only if **all**
hold, and falls through to step 3 otherwise:

* every component from `${HOME}` down to the pointer's parent exists, is owned by the effective uid, and
  is **not** group- or world-writable;
* the pointer itself is a **regular file**, not a symlink, owned by the effective uid, mode `0600`;
* it holds exactly one line: an absolute path, no trailing slash, no embedded NUL, naming an **existing
  directory**;
* **every component of the TARGET path** — not merely the target directory itself — exists, is not
  group- or world-writable, and is **not a symlink**; and every component **at or below the trust
  anchor** is owned by the effective uid.

  > **The trust anchor, and why "every component euid-owned" was unsatisfiable** (round 25, codex #4).
  > Round 23 required *every* component to be owned by the effective uid. Executed here: `/` and
  > `/Users` are `uid=0` while the effective uid is `501`, so that rule **rejects every real path**,
  > including the documented target under `~/.claude/plugins/data/`. It was written while over-correcting
  > a genuine round-22 finding, and it would have made D″ resolve nothing at all.
  >
  > **Anchor:** the first component at or below `${HOME}`. System prefixes above it (`/`, `/Users`, and
  > the equivalents on other platforms) are accepted when they are **root-owned, not group- or
  > world-writable, and not symlinks** — a machine whose `/` is user-writable has already lost, and this
  > plugin's threat model is same-uid, stated in the clause below. Everything from `${HOME}` down must be
  > euid-owned. N6 carries both a root-owned-prefix ACCEPT case and a writable-system-prefix REFUSE
  > case, so neither half can regress unnoticed.
  >
  > **ROUND 28 — that anchor is defined only for paths that pass through `${HOME}`, and the TARGET need
  > not.** The pointer's own chain is under `${HOME}` by construction, so the rule is total there. The
  > target chain is the value `CLAUDE_PLUGIN_DATA` held, and this plan already records
  > (`CLAUDE_CONFIG_DIR`, cache-root and `--plugin-dir` in the load-bearing-claim paragraph above) that
  > the data dir is relocatable. For a target such as `/opt/claude/data`, **no component is at or below
  > `${HOME}`** — so "everything from `${HOME}` down must be euid-owned" quantifies over the empty set,
  > every component falls into the "system prefix" arm, and the euid-ownership requirement silently
  > disappears from the target chain altogether. The rule is not wrong there; it is **absent**, and an
  > implementer would have to invent it. That is the same shape as the round-25 defect it is written
  > underneath — a rule stated for the case in front of me and left undefined for the neighbouring one.
  >
  > **Completed:** the anchor is *the first component at or below `${HOME}` if the path passes through
  > `${HOME}`; otherwise the first component that is **not** euid-owned-safe as a system prefix* — i.e.
  > walk the target chain from `/` downward, accept a leading run of components that are root-owned, not
  > group- or world-writable and not symlinks, and require **every component from the first non-system one
  > onward** to be euid-owned. Under `${HOME}` this reduces to exactly the rule above, so the two cases
  > share one predicate rather than two. N6 gains an off-`${HOME}` target ACCEPT case and an
  > off-`${HOME}` target with a **user-writable intermediate** REFUSE case; without the second, the
  > empty-set reading would pass unnoticed.
  >
  > **WRITABILITY IS NOT AUTHENTICATION — round 29's requirement is WITHDRAWN** (round 30, codex High #3
  > accepted, gemini #1 refuted by measurement). Round 29 required the target to be writable by the
  > effective uid, else fail closed, on gemini's reasoning that otherwise *"`marker_write`, `log_append`
  > and the snapshot writers attempt writes that fail with unhandled errors"*. **Measured at `6911ec1`:
  > they do not.** Every writer is already fail-open on write failure —
  > `marker.sh:147` `mkdir -p "$dir" 2>/dev/null || return 0`, `:156` `printf … > "$tmp" … || { rm -f;
  > return 0; }`, `:157` `mv … || { rm -f; return 0; }`, and `log.sh` the same on `mkdir`, the append and
  > the rotate. An unwritable base therefore produces **silent no-ops**, not errors, not a crash, and not
  > an aborted hook — the behaviour `paths.sh:17-20` mandates.
  >
  > codex's High #3 is nonetheless right, and sharper than the fix it prompted: writability was checked
  > **at the wrong level** (writes land in `.state`, `logs` and `reviews`, per `marker_dir()`,
  > `log_dir()` and `context_state_dir()`), and a base-level test is *"neither necessary nor sufficient"*
  > — a `0555` base with good state directories is usable and would have been refused, while a writable
  > base with an unwritable `.state` would have passed and still persisted nothing. **The correct
  > conclusion is not a better usability predicate; it is that usability does not belong in
  > authentication at all.** Authentication answers *may I trust this path* — ownership, symlinks, modes,
  > the chain. Usability is answered correctly at each write site already, and any point-in-time `-w`
  > check is a TOCTOU that proves nothing about the write that follows it.
  >
  > Two attempts to specify the usability predicate were built and both were broken by execution: one
  > **refused the very case codex said must be accepted**, because `reviews` is created lazily by
  > `scripts/capture-reviewer-verdict.sh` and is absent on any install that has never run a reviewer
  > subagent; and under `umask 002` every creator in the write-set yields `0775`, so **the family
  > bootstraps into a base its own rule then permanently refuses.** Two failed attempts at a predicate
  > nothing needed is the signal that the requirement was wrong, not the predicate.
  >
  > **So: no writability clause.** N6 row 35 is re-aimed — an unwritable target **still resolves**, and
  > its writes no-op silently rather than aborting the sourcing shell.

  > **macOS ACLs — REFUSE ON A GRANTING ACE. Round 29's out-of-scoping is reversed** (round 30, codex
  > High #4). Round 29 accepted ACLs as an unexamined limit, arguing an attacker holding a write-capable
  > ACE on an ancestor *"already has access to the user's files by other routes"*. **That is false in
  > general** — an ACE can be scoped to exactly one directory — and this plan itself calls
  > pointer-following a prompt-injection path, so knowingly following a path another uid may replace
  > contradicts its own threat model. Accepting was the wrong call.
  >
  > **But "any ACE ⇒ refuse" is also wrong, and measured so.** On this machine `ls -lde "$HOME"` shows
  > `0: group:everyone deny delete` — a **deny** entry, which *restricts* access and makes the path
  > safer. A blanket rule would refuse the maintainer's own home directory. The distinction is the rule:
  >
  > **Refuse if any component of either chain carries an `allow` ACE naming a principal other than the
  > effective user. Ignore `deny` entries entirely** — they cannot grant the write this rule exists to
  > prevent. Enumeration is `ls -lde` on Darwin (ACE lines are ` <n>: <principal> <allow|deny> <perms>`,
  > so this is string matching, not ACL semantics); on other platforms `getfacl` where present.
  >
  > **Three constraints the previous attempt violated, each now binding.** (a) **The probe writes
  > nothing.** The earlier spec probed by *writing into the attacker-chosen path*, contradicting N1/N2's
  > *"when resolution fails, no plugin-state payload is read or written anywhere"*. (b) **The rule may
  > not depend on any variable that differs between publisher and reader.** The earlier spec admitted a
  > root conditional on `CLAUDE_CONFIG_DIR`; the publisher is a hook and the reader is a git hook, so it
  > was measured to ACCEPT for the publisher and REFUSE for the reader — a pointer published silently
  > that no reader can authenticate, which is verbatim the `0644` defect this plan already fixed by
  > requiring **one predicate used by both sides**. (c) **Refusal is a resolution outcome, not a special
  > case:** it falls to step 3 — sentinel, `OK=0`, `POINTER_STATE=stale`, one diagnostic — so it needs no
  > new enum value and cannot collide with the conflict rule.
  >
  > **Where ACLs cannot be enumerated at all, the mode bits are authoritative and the plan says so.**
  > `getfacl` is absent on this machine and CI runs Linux, where the harness exports its own
  > `CLAUDE_PLUGIN_DATA` (`test-hooks.sh:31-35`) and never takes the pointer path — so failing closed
  > there would cost nothing real but would also prove nothing. Stating the limit is the honest option,
  > and **§5 carries it as a risk row rather than leaving it to be rediscovered.** N6 carries a granting-ACE
  > REFUSE case, a deny-ACE ACCEPT case (without which the blanket rule regresses), and a case asserting
  > the probe creates no file.
* *(Round 31: a clause reading "it is not marked conflicted" stood here. The `CONFLICTED` wire form was deleted with the lock — conflict is now a property of the directory, derived at read time — so the clause had nothing to test.)*

> **Why the whole target chain, and not just the target** (round 23, codex #5). The round-21 text called
> this "the whole chain" while authenticating ancestors only from `${HOME}` down to the *pointer's*
> parent, and checking the destination as a single directory. A group- or world-writable **intermediate**
> ancestor of the target lets an attacker replace the validated directory *after* the check and redirect
> the later open — and `scripts/sessionstart-restore.sh:32-33,53-67` opens snapshot content from that
> pathname and feeds it to the model via `additionalContext`. So the residual is not state corruption, it
> is **prompt injection with a TOCTOU window**. Validating every component closes the window to the
> same-uid case, which is the trust assumption this plugin already makes everywhere else — **state that
> assumption rather than leave it implicit**, and carry writable- and symlinked-target-ancestor mutants
> in N6.

**The pointer's parent must be exactly `0700`.** This is stricter than the not-group-or-world-writable
test applied to every other component, and is stated separately because it is **not implied** by it.
*(Round 25, codex #6: `0755` carries no group or other WRITE bit, so it satisfies the general rule — and
§4.4's claim that a `0755` parent permanently refuses publication therefore contradicted this section
until the exact-mode requirement was written down. N6 carries a `0755`-parent refusal mutant.)*

A **pre-existing** `${HOME}/.claude/unleashed-mail` with loose permissions is **refused, not chmod'ed** —
silently tightening a directory the user may have created is a surprise, and the fail-closed path is
already correct. *(Measured 2026-08-08: `~/.claude/plugins` is `drwx------` but `~/.claude/unleashed-mail`
is `drwxr-xr-x`, so on this machine the refusal branch is the one that fires until it is fixed — state
that plainly rather than let an implementer discover it.)*

### Source-time safety in five shell files

Every new command runs at **source** time. The libs are sourced under `set -euo pipefail` by an
already-gated test (`test_shell_primitive_drift.py:114`), and `paths.sh:17-20` forbids converting
fail-open paths into a shared point of failure. Probed: a bare `read -r _P < "$PTR"` **aborts an errexit
sourcing shell** when the pointer lacks a trailing newline; the discriminating run with a trailing
newline reached the marker, so the silence is a genuine abort.

**Rules — all three are load-bearing:**

1. No new command may appear as a bare statement; each is inside an `if`/`&&` condition or terminated
   with `|| :`.
2. The read takes its **group-level** redirect, because in zsh no redirect ordering on the inner command
   suppresses an open failure.
3. **`nounset` discipline — round 20, kimi #7.** When the redirect fails, `read` never executes, so the
   variables stay **unset**, and a following unguarded `"${_L1}"` kills a `set -euo pipefail` shell in
   *both* shells (`_L1: unbound variable` / `_L1: parameter not set`). Every read target is
   pre-initialised and every expansion uses `:-`. Rule 1 alone is **not** sufficient; this is the half an
   implementer following only the written rule would miss.

```sh
_L1=''; _L2=''
{ [ -L "$PTR" ] || { IFS= read -r _L1; IFS= read -r _L2; } < "$PTR"; } 2>/dev/null || :
[ -n "${_L2:-}" ] && return 1   # a second line means it is not a single-line pointer
```

### Observability — §4.1's enum no longer describes the state space

§4.1's round-13 note pins the vocabulary to `host-env` / `unresolved` *"and ONLY those"*, reasoning that
under D′ everything else is unreachable. **D″ makes one further resolution reachable — a published
pointer — and it sets `OK=1`, so it persists records.** Left unamended, such a record would be stamped
`host-env`: a record that **lies about its provenance**, which is worse than the silence §4.1 was written
to fix, and is this ticket's founding defect with the label vouching for the wrong half.

**This section therefore amends §4.1:** the vocabulary becomes `host-env` / `pointer` / `unresolved`
(no `home-fallback` — step 3 is dropped), carried by a fourth protocol variable
`_UNLEASHED_BASE_SOURCE` set beside `_UNLEASHED_BASE_OK` in all five shell family files.
`_UNLEASHED_BASE_OK` stays **binary** and stays the only sanctioned resolved/unresolved test — consumers
branch on it, never on the source enum.

### N1 and N2 are amended, not silently narrowed

N1 says a set variable writes *"only in the supplied host base"*; step 1 writes the pointer outside it.
The draft patched the *tests* to keep passing while leaving the normative text untouched — moving the
oracle to fit the code. With step 3 dropped, the unset-case half of N1/N2 is **restored intact**: an
unset variable with no valid pointer reads nothing and writes nothing. The invariant N1/N2 now assert:
**no state is written to any base other than the one the resolution returns; the single exception is the
pointer file, which carries the base path and nothing else; and when resolution fails, **no plugin-state
payload is read or written anywhere** — the bounded pointer read being the one exception, since an
invalid pointer cannot be rejected without reading it.**

§5's inert-gate mitigation (`:1329`) is amended **in place**, not by reference — see the round-21 note
there. Its *"N2 must run the unset case, which is the only case that reproduces the defect"* is still
true for the no-pointer case and is now joined by step 2's *"no second store is created"*.

### Make the silence audible — with a predicate that can fire

The draft required `sessionstart-restore.sh` to emit `additionalContext` when `unleashed_base_ok` is
false. **That predicate is unreachable in that hook:** it runs as a hook, so step 1 always resolves.
Round 20 (codex #6) added that `sessionstart-restore.sh:16-18` sources `context.sh` before any consumer
logic, so a source-time step 1 publishes there anyway — the hook cannot observe its own failure.

**Decided, rather than left open:** the resolver exposes a source-time publish result
`_UNLEASHED_POINTER_STATE` ∈ `created` | `current` | `conflict` | `stale` | `failed` | `none`.

*(**Round 30 — re-derived from D″-pf's exit paths, not edited.** `contended` is **deleted** with the
lock that produced it; `stale` is new and means an entry failed authentication; `none` is new and is the
honest value for "nothing to report" — a clean resolve and a clean empty store both reach it, and round
28's and round 29's totality failures were both an exit path with **no** value, so the enum now carries
one rather than leaving an implementer to pick.)*

`SessionStart` emits **one** non-blocking `additionalContext` line, still `exit 0`, when that value is
`conflict`, `stale` or `failed` — i.e. exactly when the **non-hook path will fail** — and stays silent
on `created`/`current`/`none`. This is a statement about
the *other* shells, which is the state the maintainer actually experiences and which no hook could
otherwise report.

The draft's justification was also false. *"`SessionStart` is the only hook that can address the model"*
is contradicted by the tree: `scripts/lib/hook-io.sh:266-269` defines `hook_emit_posttool_context()` and
`:275-278` `hook_emit_posttool_block()`, both in production use (`scripts/swift-build-verify.sh:71`,
`scripts/swift-lint-check.sh:433`). The true statement is narrower: **`PostCompact` cannot inject
context; `SessionStart` and `PostToolUse` can.** `SessionStart` is chosen over `PostToolUse(Bash)`
because the notice is a once-per-session fact, not a per-call one; **§8 Q8** (added by this round)
records the `PostToolUse(Bash)` alternative. *(Round 21 cited "§8 Q6", which is D′'s escape hatch —
another reference to a question that did not exist.)*

This **amends §7's consumer row** (`:1501`), which currently requires both snapshot scripts to leave
*"the hook's own output"* untouched on an unresolved base.

### The implementing family is FIVE shell files — and the harnesses are a separate list

*(Round 21, codex #5: 19b said "six", folding in `scripts/tests/test_plugin_state_base.py` because it
matched the resolver grep. It is **Python**; it cannot be shell-sourced, so the obligation "each of the
six family files sources cleanly under `set -euo pipefail`" was literally unsatisfiable. Deriving the
family by grep was right; the conclusion drawn from it was not.)*

**Implementing family (all five change together):** `scripts/lib/paths.sh` and the inline copies in
`context.sh`, `marker.sh`, `log.sh`, `agent-env-bridge.sh`.

**Affected test harnesses (a different list, derived by `grep -rln 'CLAUDE_PLUGIN_DATA' scripts/` —
setters, not just resolvers):** `scripts/tests/test_plugin_state_base.py`,
`scripts/tests/test_shell_primitive_drift.py`, `scripts/test-hooks.sh`,
`scripts/tests/test_reviewer_roster.py`.

**The duplication is priced in, and must be stated rather than left implicit** (round 20, kimi #8). No
reduced inline fallback is coherent: a reduced copy makes resolution depend on whether `paths.sh` was
found, which is the drift defect `test_with_paths_sh_absent` (`test_plugin_state_base.py:54-60`) exists
to kill, and §4.3's round-6 mandate (`:1242`) requires that `paths.sh`'s absence change *who computes* the
answer, never *what the answer is*. So the three-step logic lives in five files **by design**, and N6
must **prove the arms agree** rather than assume it.

> **TEST TRAP — read this before editing a single test.** Three hazards.
>
> **(a) Tests that would write into the developer's real `$HOME`.** `test_plugin_state_base.py` reaches
> the unresolved state by **simply not setting `CLAUDE_PLUGIN_DATA`** while inheriting the real `HOME`
> (`run()` strips only `CLAUDE_PLUGIN_DATA`/`CLAUDE_PLUGIN_ROOT`, `:28`). Under D″ those cells resolve
> via step 2 to `OK=1` whenever a pointer exists. **The rule is file-wide, not per-cell:** force every
> unresolved case with `HOME=""`, and give every other case a `tempfile.TemporaryDirectory()` `HOME`.
> **The temp `HOME` must be CANONICAL** (round 25, codex #8). Target authentication rejects every
> symlinked component, and on macOS `tempfile.TemporaryDirectory()` returns a path under
> `/var/folders/…` where `/var` is a symlink to `private/var` — so the prescribed remedy would make every
> intended-VALID pointer cell fail authentication, and the suite would "pass" by rejecting fixtures it
> was meant to accept. Resolve every temp `HOME` and target through `realpath`/`pwd -P` before use, and
> **assert the valid fixture authenticates** before relying on it as a positive oracle. A positive
> control that is silently negative proves nothing — the same class as a mutation script that no-ops.
>
> Stated once so no enumeration can be incomplete — round 20 (kimi #9) showed the 19b enumeration had
> missed `test_zsh_agrees_with_bash` (`:62-68`), `test_exactly_one_diagnostic_per_process` (`:70-80`),
> `test_writes_really_happen_when_resolved` (`:117-122`) and `test_no_diagnostic_when_resolved`
> (`:82-85`).
>
> **(b) The PUBLISH side.** Any process that sets `CLAUDE_PLUGIN_DATA` and inherits the real `HOME`
> **clobbers the machine's live pointer** under step 1. `scripts/test-hooks.sh` does exactly that: `:6`
> promises *"All hook state is isolated in a temp CLAUDE_PLUGIN_DATA so the real ~/.claude is never
> touched"*, `:33` exports the temp value, `:34-35` `rm -rf`s it on exit, and `HOME` is never set in the
> file. Executed against a sandboxed HOME, a prototype left the pointer naming a **deleted** directory.
> `test_reviewer_roster.py:41` has the same shape. `test_shell_primitive_drift.py:98-102` is a
> **different** case — it sets `HOME=/probe` explicitly, so it does not inherit the developer's home, but
> it still needs a temp `HOME` so a publish cannot create `/probe`. *(codex #8 — round 21 lumped them.)* **Sandbox
> `HOME` in all three** — that is the three files listed above, not "two more harnesses" — and prove it:
> *running the harness leaves `$HOME/.claude/unleashed-mail/bases/` byte-identical — every entry, and the set of entries.*
>
> **(c) The drift test — the draft named the wrong symbol, and with step 3 dropped the answer changes.**
> `EXPECTED` (`test_shell_primitive_drift.py:92`) is the *legacy expansion string*, used only by
> `test_legacy_expansion_survives_only_in_paths_sh` (`:118-144`), and **D″ does not change it**. 19b
> asserted that `MATRIX` rows `:100`/`:102` would flip; **with step 3 dropped they do not** — all four
> rows stand, in both arms, and the 12 subtests do not change. What *does* need attention is that
> `test_legacy_expansion_survives_only_in_paths_sh` states its premise in **two** places (round 20,
> kimi #12): the docstring (`:119-129`) *and* the `assertEqual` failure message (`:134-138`). Under D″
> with step 3 dropped that premise remains **true**, so both stand — but any future round that revives a
> `$HOME` fallback must change both sites, not one.
>
> Also re-check `N5LexicalDrift.ALLOWLIST` (`:158-170`) for the pointer path's expansion sites, keep
> `test_indirection_fails_closed` satisfied (no `${!` in a state library, `:201-211`), and add `/.claude`
> to `test_nothing_is_created_at_root`'s watch set (`:111,114`).

### Proof — N6, with the mutants round 20 found missing

§6 declares the envelope as N1–N5, each with an adversarial mutant. **N6 — pointer publication,
authentication and refusal semantics** is added, because every obligation above is new and *"an
obligation with no adversarial mutant can ship unproven"* is this plan's own round-7 lesson.

**Mutant set — ONE MUTANT PER AUTHENTICATION CLAUSE, enumerated.** Round 22 (codex #7) found the
round-21 set covered only some clauses while the text claimed *"each authentication clause refused
independently"* — a generic sentence is not a mutant, and an unnamed mutation is one nobody writes.

| # | mutation | discriminating case it must break |
|---|---|---|
| 1 | publish always (drop the type-and-content skip) | mtime unchanged on a no-change second run |
| 2 | accept a symlink pointer | symlink pointer refused |
| 3 | accept a relative path | `foo/bar` refused |
| 4 | accept a multi-line file | two-line pointer refused |
| 5 | accept a non-existent target | dangling path refused |
| 6 | **accept a target that exists but is not a directory** | regular-file target refused |
| 7 | **drop the pointer-owner check** | pointer owned by another uid refused |
| 8 | **accept any pointer mode** | pointer at `0644` refused |
| 9 | **drop the trailing-slash rejection** | `/a/b/` refused |
| 10 | **drop the NUL rejection** | embedded-NUL pointer refused |
| 11 | accept a group-writable pointer parent | `0775` parent refused |
| 12 | accept a group-writable target | `0775` target refused |
| 13 | **accept a group-writable target ANCESTOR** | safe target under a `0775` ancestor refused |
| 14 | **accept a symlinked target ancestor** | symlinked ancestor refused |
| 18 | compose a `${HOME}` path with `HOME=""` | no `${HOME}`-rooted open attempted |
| 19 | **let `HOME=""` suppress a valid `CLAUDE_PLUGIN_DATA`** | set variable still resolves, `OK=1` |
| 20 | stamp `host-env` for a pointer resolution | record carries `base_resolution=pointer` |
| 21 | **drop the owner check on a pointer-path ANCESTOR** | ancestor owned by another uid refused |
| 22 | **accept a writable INTERMEDIATE pointer ancestor** (row 11 covers only the parent) | `0775` grandparent refused |
| 23 | **drop the target's own owner check** | target owned by another uid refused |
| 24 | **drop the owner check on a target ANCESTOR** | target ancestor owned by another uid refused |
| 25 | **accept a SYMLINKED TARGET itself** (row 14 covers only an ancestor) | symlinked target refused |
| 26 | **accept a pointer parent at `0755`** | exact-`0700` parent rule enforced |
| 27 | **require euid ownership ABOVE the trust anchor** | root-owned `/`, `/Users` still ACCEPT |
| 28 | **accept a group-writable system prefix** | writable `/` refused |
| 33 | **accept an off-`${HOME}` target with a user-writable intermediate** | target under a `0777` ancestor refused |
| 34 | **require euid ownership of an all-root off-`${HOME}` target** | an all-root-owned system target authenticates |
| 35 | **refuse a readable but UNWRITABLE target** | unwritable target still resolves, `OK=1`; its writes no-op and the sourcing shell survives |
| 42 | **accumulate distinct targets as a space-delimited string** | a base containing a space, and one containing a glob char, each counted as ONE distinct base |
| 43 | **count entries without the name↔content check** | an entry whose name does not encode its content is refused, not counted |
| 44 | **swap the encoder's substitution order** | `/a/b` and `/a_sb` produce DIFFERENT entry names |
| 45 | **derive the key with command substitution** | no fork occurs at source time |
| 46 | **drop `no_nomatch` from the scan** — run in **each of the five family files** under zsh | an empty store does not terminate the sourcing shell, in all five arms |
| 47 | **drop bash's literal-glob `[ -e ]` guard** | an empty store yields zero entries, not one named `base.*` |
| 48 | **treat an enumerated-then-vanished entry as malformed** | operator deletion during a scan does not report `stale` |
| 49 | **scan before publishing** | two publishers racing a first publication still leave a durable conflict |
| 50 | **create the store `mkdir` then `chmod 700`** | no window exists in which another publisher observes `0755` |
| 51 | **put the entries directly in `~/.claude/unleashed-mail`** | publication succeeds on a `0755` `~/.claude` (this machine today) |
| 52 | **drop the NAME_MAX pre-check** | an over-long base reports `failed` and leaves no tmp file |
| 53 | **let a publisher write an entry that is not its own key** | a publisher touches only `base.<key(its value)>` and its own tmp |
| 54 | **remove the harness `HOME` sandbox** | the developer's real store is byte-identical after `test-hooks.sh` |
| 55 | **ignore ACLs entirely** | a component carrying an `allow` ACE for another principal is REFUSED |
| 56 | **refuse on any ACE, `deny` included** | `$HOME`'s real `group:everyone deny delete` still ACCEPTS |
| 57 | **let the ACL probe write a test file** | refusal path creates nothing anywhere |
| 58 | **admit a root conditional on `CLAUDE_CONFIG_DIR`** | publisher and reader reach the SAME verdict in different environments |
| 59 | **drop a declared value from the enum** | every publish exit still maps to a declared value |
| 60 | **assign a publish exit the wrong enum value** | each exit's value is the one §6's derivation gives |
| 61 | **reorder the reader rules so a good entry wins over a malformed one** | one valid + one malformed entry REFUSES |
| 62 | **revert the temp name to `$$` alone** | two same-base publishers cannot open the same temp inode |
| 63 | **case-fold the encoding** | `/Data/A` and `/Data/a` produce distinct entries on a case-insensitive volume |
| 64 | **emit raw target paths in the conflict diagnostic** | no absolute path reaches stderr |
| 65 | **let `agent-env-bridge.sh` stay D′-only** | the fifth copy resolves an authenticated entry like the other four |
| 66 | **omit parent creation for a missing `~/.claude/unleashed-mail`** | a clean install publishes, and reports `failed` only on a real error |

*(Rows 59-66 are round-31 additions. 59-60 replace the totality proof §6 was citing from **retired** rows
31-32/40-41 — both arms found that independently, and a citation to a deleted mutant is worse than none
because it reads as proof. 61 is the concordant precedence defect. 62-64 are codex's `$$`, case-fold and
PII findings. 65 closes the fifth-copy contradiction: §7 makes `agent-env-bridge.sh` choose only the
supplied value or the sentinel, which contradicts the five-copy mandate and the arm-equivalence
requirement — with an authenticated entry, empty `$1` and `paths.sh` absent, that copy fails closed while
the other four resolve. 66 restores the clean-install obligation that retired row 36 was carrying, since
`mkdir -m 700 bases` does not create a missing parent.)*

> **ROUND 30 — THIRTEEN ROWS WERE RETIRED, AND WHY MATTERS AS MUCH AS WHICH.** Rows **15, 16, 17, 29,
> 30, 31, 32, 36, 37, 38, 39, 40, 41** are gone. Every one of them mutated a mechanism D″-pf **deletes**:
> the single shared pointer and its `CONFLICTED` wire form (15-17), the single-pointer skip test (29),
> the publication lock and everything built on it (30-32, 36-41). A mutant against a mechanism that no
> longer exists cannot fail, and **a row that cannot fail reads exactly like a row that passes** — which
> is how row 31 spent a round asserting the opposite of the live notice rule while the table looked
> complete. They are removed rather than rewritten because rewriting would have preserved the numbering
> and hidden the scale of the change.
>
> **Rows 42-54 replace them, one per obligation D″-pf actually creates**, derived from its exit paths
> and its stated invariants rather than counted to a target. Note 46 in particular: the `no_nomatch`
> guard ships in **five copies**, so it is asserted **per family file** — one passing arm is not
> evidence about the other four, which is the lesson row 19 already carries for the `HOME` guard.

*(Rows 35-41 are round-29 additions. 35 is gemini's authenticated-but-unusable target; 36 its ENOENT
clean-install case; 37-39 codex's fencing and convergence Highs; 40 the concordant untotal-enum finding;
41 the notice half of it. **Rows 33-34 were also NOT EXECUTABLE as round 28 wrote them** (codex #5): they
prescribed `/opt/claude/data` fixtures, which need root to create, while the verification runs
unprivileged. They now name no fixed absolute path — the harness builds the off-`${HOME}` chain under a
temporary root and injects the ownership/mode metadata through the same seam rows 27-28 already use, so
the pair is runnable by an ordinary uid. An unrunnable mutant is a mutant that proves nothing, which is
this plan's own round-8 lesson about the physically-impossible canary.)*

*(Rows 33-34 are round-28 additions pinning the two halves of the trust anchor where the target does
not pass through `${HOME}`. Rows 33 and 34 are a matched pair for the same reason as 27/28:
row 34 alone would be satisfied by an anchor that never requires euid ownership off-`${HOME}`, which is
precisely the empty-set reading being closed.)*

*(Rows 6-10, 13-14, 16 and 19 are round-23 additions; rows 21-30 are round-25 additions after codex #7
showed the "one mutant per clause" claim was still false — four clauses had no row, and the asserted
count of 20 was doing the work a per-clause derivation should. **The count is no longer asserted; the
table is derived from the clause list and must be re-derived whenever a clause changes.** Row 19 remains
the most important: it is the fail-open → fail-closed inversion codex found in round 22's step-0 wording.
Row 27 is its mirror — it proves the round-25 trust anchor did not over-correct into rejecting every real
path, which is exactly what the round-23 rule did.)*

**Cases** — each must fail when the fix is reverted:

step 1 → base is the variable's value **and** this publisher's entry holds it; a second run with the same
value performs **no write** (asserted by mtime); a symlinked or `0644` entry with matching content **is**
republished as a conforming one; a second install id with a different base leaves **two entries**, which
every reader resolves as a conflict — no publisher marks anything for another to find; step 2 →
variable unset, exactly one authenticating entry → base is that entry's target,
`_UNLEASHED_BASE_SOURCE=pointer`, and **no second store is created** (this fails under D′, which resolves to the sentinel, and under the pre-D′
fallback, which resolves to `$HOME`); each authentication clause refused independently, including a
**conflicted** pointer; step 3 → `HOME=""` → sentinel, `OK=0`, **exactly one** diagnostic, **no
`${HOME}`-rooted open attempted at all**, and the D′ no-persistence envelope (`N2`, `N4`) holds in full;
persisted records carry `base_resolution` matching the resolution that actually ran; and the SessionStart
notice fires on `conflict`/`stale`/`failed` and stays silent on `created`/`current`/`none` — the same partition as the declaration above, and derived from the same exit-path list rather than restated.

**Arm equivalence, across all five shell files** (round 20, kimi #8): the full pointer matrix
(absent / valid / malformed / unreadable / conflicted × publish / refuse) runs with `paths.sh` **present
and absent**, asserting identical `_UNLEASHED_BASE_RESOLVED`, `_UNLEASHED_BASE_OK` and
`_UNLEASHED_BASE_SOURCE` from every file. Each file must also source cleanly under `set -euo pipefail`
in **both bash and zsh** in every cell.

**Stderr is asserted per cell, not globally** (round 20, kimi #7): `stderr == ""` is required only in
**resolved** cells. Steps 1-conflict and 3 mandate **exactly one** diagnostic, so a blanket empty-stderr
assertion would contradict them — the draft's N6 clause did exactly that.

### Consumers whose behaviour changes, stated rather than discovered

* **`scripts/pre-commit-checks.sh`** — under step 2 its marker writes become **visible to the gate** with
  no export, so the §7 row's unresolved-base conditional stops firing. Its `:14-18` MAJ-6 comment is
  falsified in both directions (it says marker.sh *"falls back to ~/.claude/unleashed-mail"*, which D′
  already made false, and *"To wire them up, export CLAUDE_PLUGIN_DATA in your git-hook env"*, which
  step 2 makes unnecessary). **Amend that comment in the same change** (round 20, kimi #11).
* **`scripts/sessionstart-restore.sh`** — gains the one-line notice above; §7's row `:1501` amended.

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
>
> **Round 21 — this section is UNCHANGED, and that is now a settled outcome rather than an open risk.**
> Rounds 19/19b carried a fourth resolution step (`${HOME}/.claude/unleashed-mail` when `HOME` is
> absolute) that would have reversed both statements above: it yields exactly the legacy base this
> mandate forbids, and it requires the **opposite** expectation for two `MATRIX` rows. **The round-20
> gate dropped that step — both arms independently — so nothing here changes.**
>
> Recorded because the cost was the evidence that settled it: the affected rows are `MATRIX` `:100`
> (`HOME=/probe`, variable unset) and `:102` (`HOME=/probe`, variable empty) — **not** `EXPECTED`
> (`:92`), which is the legacy expansion string and is untouched by D″. Each row runs in both arms across
> three libs, so reviving a `$HOME` fallback in any future round costs **12 subtests** plus a rewrite of
> this mandate. Under D″ as gated, all four rows stand.

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

> **Round 21 — this section is UNCHANGED, premise and ordering both.** Rounds 19/19b carried a fourth
> resolution step that would have made the fallback path resolve again, invalidating this section's
> premise (*"Leaving them in place conflicts with N4 **while the fallback path still resolves**"*) and
> **inverting its ordering** — the quarantine would have had to land *before* the resolver rather than
> after, because it would otherwise be moving state a live resolver can reach. The two orderings are
> mutually exclusive, so this could not be deferred.
>
> **The round-20 gate dropped that step**, on both arms. Under D″ as gated, an unresolved base yields the
> sentinel, this directory stays inert, and the quarantine keeps its original *after-the-resolver*
> ordering. kimi's round-20 note that the directory is **not empty** (21 files, including the divergent
> marker that is §2's load-bearing evidence) is why the inverted ordering would have been mandatory had
> the step survived — recorded so a future revival does not miss it.
>
> **ROUND 23 — the ORDERING is unchanged, but this section's SCOPE is not (codex #3).** D″ makes
> `~/.claude/unleashed-mail` the **pointer's parent**, and §4.2a refuses to publish into a directory that
> is group- or world-writable. Measured on this machine it is `drwxr-xr-x` (`0755`). So moving the 21
> files out and stopping — which is all this section currently does — leaves an **emptied `0755`
> directory that refuses every future publication**, permanently. The quarantine would complete, report
> success, and leave D″ inert.
>
> Three additions, in this section rather than §4.2a because they are quarantine mechanics:
> 1. **Move exactly the legacy inventory.** If an authenticated `base` pointer already exists in that
>    directory it is **preserved in place**, never swept into the quarantine — the current "move the 21
>    files" wording would carry it off and silently un-publish the machine.
> 2. **Repair the parent**: after the move, remove and re-create the directory `0700`, or `chmod` it, as
>    an explicit documented step. Not a side effect of the move.
> 3. **Prove it end to end**: loose `0755` parent → quarantine → a subsequent publication **succeeds**.
>    Asserting only that the files moved is the "recorded but never compared" defect this campaign has
>    now hit four times.

**Proof — N4 (strengthened in round 3):** asserting only that the fallback is unreadable is satisfied
the moment D′'s guards land, **even if the quarantine never happens**. So N4 must also prove the move
occurred safely: every source file **absent** from the old location, each quarantine directory holding
the **exact inventory**, and **every checksum matching**. The `-inline` file is quarantined separately
with its own inventory.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| **ACLs cannot be enumerated on every platform** | **Low** | **Round 30 — round 29's blanket acceptance is REVERSED; only the unenumerable case remains a limit.** Darwin refuses any component carrying an `allow` ACE for another principal (`deny` ignored — measured, `$HOME` here carries `group:everyone deny delete`). Where no enumerator exists the mode bits are authoritative and that is stated rather than hidden; CI is unaffected because the harness exports its own `CLAUDE_PLUGIN_DATA` and never takes the pointer path. *(Superseded round-29 text follows.)* **Accepted limit, stated not hidden** (round 29, codex High #3). Authentication tests ownership, mode bits and symlinks; a macOS ACL can grant another uid write access to a root-owned `0755` ancestor and pass every clause. Defended: same-uid accident and mode-bit misconfiguration. **Not** defended: an attacker already holding an ACL grant on an ancestor of the data dir — who, on this platform, already has write access to the user's files by other routes. Enumerating ACLs needs a portable query the shell family does not have (`ls -le` is BSD-only and parsed nowhere here), and a half-implemented check would read as protection while providing none. Tracked as **COREDEV-2617a**; §4.2a states the limit in place |
| The fix breaks the fail-open property of hooks | **High** | §4.3 keeps the absent-`paths.sh` fallback; A is rejected for the hook path |
| A derivation picks the wrong id where two exist | **High** | §2 measured two on this machine; B is called out as ambiguous rather than assumed safe |
| The change looks correct because all four libs still agree | **High** | §3 — agreement is what hid this. N3 compares to `unleashed_plugin_base()`, not to peers |
| Auto-migration overwrites the newer of two divergent markers | Medium | §4.4 forbids auto-merge by default |
| The gate goes inert: a test that sets `CLAUDE_PLUGIN_DATA` in its fixture proves nothing | **High** | **N2 must run the unset case**, which is the only case that reproduces the defect. `scripts/test-hooks.sh:33` exports it for isolation — a test inheriting that harness cannot see this bug. **Round 21 (§4.2a):** under D″ "unset" is no longer sufficient on its own — an unset variable with a valid pointer *resolves*, via step 2. The unset case must therefore be run **with no pointer** to reproduce the defect, and it is now joined by step 2's own assertion, *"no second store is created"*, which carries the anti-inertness burden for the resolved-via-pointer path. A fixture that sets **either** the variable or a pointer proves nothing |
| A harness that sets `CLAUDE_PLUGIN_DATA` clobbers the developer's real pointer | **High** | **Round 21 (§4.2a), new.** Step 1 makes every setter a publisher. `scripts/test-hooks.sh` promises isolation at `:6` but never sets `HOME`, so it would publish into the developer's real `${HOME}` naming a temp directory its own EXIT trap then deletes. **ROUND 30 — the mitigation was written as an accomplished fact and is not one.** It read *"`HOME` is sandboxed in all three affected harnesses"*, present tense. Measured at `6911ec1`: `grep -rn 'HOME=' scripts .github .githooks` returns **no assignment anywhere in the repo** — the only hits are `pty-capture.py`'s `XDG_STATE_HOME` diagnostics. **So sandboxing `HOME` is work the implementation must do, not a property the tree has**, and until it is done every harness that exports `CLAUDE_PLUGIN_DATA` writes into the real `${HOME}`. Stated as a requirement: each affected harness must set `HOME` to its own temp root **before** sourcing any family file, N6 asserts the real store is byte-identical after a run, and a mutant removes the sandbox and requires the assertion to fail |

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

> **ENUM TOTALITY IS DERIVED, NOT ASSERTED** (round 29). `_UNLEASHED_POINTER_STATE` has now been
> incomplete **twice** — round 25 left lock contention with no value, and round 28's fix for that left
> the `CONFLICTED`-skip path with no value, one bullet away. Both times the prose said the enum was
> total. So totality is no longer a sentence: **every exit path of the publish routine must be
> enumerated, each mapped to exactly one enum value, and the mapping checked against the declared value
> list.** An exit with no value, or a value not declared, fails verification. N6 rows 43, 59 and 60
> mutate the mapping in both directions — a value dropped from the declaration, and an exit assigned the
> wrong value. *(Round 31, both arms concordantly: this cited rows 31-32 and 40-41, all four **retired**
> with the lock in round 30, so the totality mandate was enforced by nothing. A citation to a deleted
> mutant is worse than none — it reads as proof.)* *(This is the same move as round 25's "the count is no longer asserted; the table is
> derived from the clause list" — applied to the state space instead of the mutant set, for the same
> reason: a claim of completeness that nobody can check is a claim that fails silently.)*

> **Round 19b — the envelope becomes N1–N6.** §4.2a's first draft asserted only that *"the D′
> no-persistence envelope (`N2`, `N4`) still holds in full"* and left every genuinely **new** obligation
> without an N-number: the pointer's publication, its no-rewrite-when-unchanged property, its six refusal
> cases, the directory's ownership and mode requirement, source-time errexit/stderr safety across both
> shells, and the SessionStart notice. That is exactly the round-7 failure this list already records — an
> obligation with no adversarial mutant can ship unproven. **N6 — pointer publication and refusal
> semantics** is named in §4.2a with its mutant set; N1, N2 and N4 additionally gain the
> pointer × `HOME` dimensions.

## 7. Implementation order

1. **D′ is settled** (rounds 2-3, both reviewers; §8 Q1). Do **not** re-open it during implementation.
2. Make the fallback observable (§4.1) and add N1.
3. Implement the chosen resolution; add N2 with the **unset** case.
   **Including the ONE explicit bridge D′ requires — round 13.** *(gemini: §4.2's option D and D′'s
   restatement both require "one documented bridge helper instead of per-agent copy-paste", and this step
   said only "implement the chosen resolution" — the bridge was never specified anywhere, while §7's N5
   discussion simultaneously deferred it to "a future extraction". An implementer had to invent it or
   leave D′ incomplete.)*

   **Specified — and round 14 corrected the round-13 form, which could not work.** The fence must
   **pass the substituted value in**; it cannot delegate the substitution to a sourced file.

   ```bash
   source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/agent-env-bridge.sh" \
          "${CLAUDE_PLUGIN_DATA}" "${CLAUDE_PLUGIN_ROOT}"
   ```

   Both placeholders are the **exact braced tokens**, which is the only form Claude Code substitutes, and
   both are in **agent content**, which is the only place it substitutes them
   (`scripts/tests/test_doc_gates.py:39-47`; `agents/swift-reviewer.md:168-176` documents the same rule
   for the current inline bridge). `agent-env-bridge.sh` takes the data value as **`$1`** and the plugin
   root as **`$2`**, exports the data value, then performs the shared source-time resolution.

   **The helper's body, stated rather than implied — round 16.** *(gemini: the signature and the
   `paths.sh` sourcing were specified and the body was not, so an implementer had to invent the
   empty-`$1` handling that keeps D′'s state space correct. codex traced the same path and found the
   behaviour **derivable** from the shared resolver contract — both are right, and the cheap fix is to
   write it down.)*

   ```bash
   # agent-env-bridge.sh — $1 = CLAUDE_PLUGIN_DATA value, $2 = CLAUDE_PLUGIN_ROOT
   export CLAUDE_PLUGIN_DATA="${1-}"          # empty is preserved, NOT unset: see below
   # GUARDED, exactly as marker.sh:21-24 guards it — paths.sh is an optimisation of
   # maintenance, NOT a load-bearing dependency (paths.sh:20), so an absent file must
   # take the same no-persistence path, never abort.
   if [ -z "${_UNLEASHED_PATHS_SH_LOADED:-}" ] && [ -r "$2/scripts/lib/paths.sh" ]; then
       . "$2/scripts/lib/paths.sh"
   fi
   # ALWAYS establish the flag — the fence has no inline fallback of its own, so if the
   # helper returns without setting it, "unset => unresolved" would fail the fence CLOSED
   # on a perfectly valid base. Round 18.
   if [ -z "${_UNLEASHED_BASE_OK:-}" ]; then
       if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
           _UNLEASHED_BASE_OK=1
       else
           _UNLEASHED_BASE_OK=0
           printf 'unleashed-mail: plugin data dir unresolved; no state will persist\n' >&2
       fi
   fi
   ```

   *(Round 17, BOTH arms: the round-16 body sourced `paths.sh` **unconditionally**. In the documented
   absent-file mode that emits a raw shell error — **Bash returns 1, zsh 127** (codex measured both) — the
   sentinel and `_UNLEASHED_BASE_OK` are never established, and an `errexit` caller **terminates**. It
   contradicted §4.3's non-load-bearing contract, which every shipped lib honours with exactly the
   `[ -r … ] && .` guard this now copies. I wrote a four-line body to close "the mechanism is unspecified"
   and omitted the one line that makes it safe.)*

   **When `paths.sh` is absent** the helper's resolver is not defined — so the helper establishes the flag
   **itself**, from the value it was handed, and emits the single diagnostic if unresolved.

   *(Round 18, from the REPRODUCTION run: this is the defect that made a double approval fail to
   reproduce, and it is a genuine regression I introduced. The three state libs each carry an **inline
   fallback**, so they always set the flag; **the agent fence does not** — it sources only the bridge
   (`agents/swift-reviewer.md:266-269`). With `paths.sh` absent the round-17 helper exported the value and
   returned **without setting `_UNLEASHED_BASE_OK`**, so the round-17 rule "unset ⇒ unresolved" made the
   fence emit `NO CAPTURE` **even when `$1` was set and the base was perfectly valid** — breaking the
   fail-open fallback §4.3 exists to protect. In the two empty-`$1` absent-file cells it also emitted **no
   diagnostic at all**, violating the exactly-one-per-process mandate. Two round-17 fixes, each correct
   alone, combined into a fail-closed regression on the one consumer without a fallback.)*

   **Empty and unset are treated identically**, which is what makes this correct: `paths.sh` uses `:-`,
   so an empty `CLAUDE_PLUGIN_DATA` takes the same branch as an absent one, and under D′ that branch
   yields the **poisoned sentinel**, `_UNLEASHED_BASE_OK=0`, **one** bounded stderr diagnostic, and no
   persistent read or write. The helper therefore needs no conditional of its own — the conditional
   lives once, in the resolver, which is the entire point of the bridge.

   *(Round 14, BOTH arms. gemini: the round-13 form used **unbraced** `$CLAUDE_PLUGIN_ROOT`, and §1 of
   this plan says that variable is **unset** in an ordinary Bash-tool shell — so it would have expanded
   to `source "/scripts/lib/agent-env-bridge.sh"` and crashed the fence. codex went further and found the
   deeper error: even spelled correctly, **`${CLAUDE_PLUGIN_DATA}` inside a sourced `.sh` file is not
   agent content**, so it receives no substitution and the helper would export an empty value — leaving
   the roster and capture readers unresolved, which is the exact defect this ticket exists to fix. The
   round-13 design would have replaced a working inline bridge with a broken indirect one.)*

   **Consequently N5's allowlist RETAINS the two fence sites** — they are the substitution injection
   points and cannot move — **and gains the helper.** *(Round 13 claimed the fences could be removed;
   they cannot. The duplication that goes away is the resolution logic, not the injection.)*

   **How the helper shares one code path with the libraries:** it sources `paths.sh` via the root the
   fence handed it — **`. "$2/scripts/lib/paths.sh"`** — so it never has to locate itself.

   *(Round 15, codex: the round-14 form used `. "${BASH_SOURCE[0]%/*}/paths.sh"`, which **fails in zsh**
   — `BASH_SOURCE` is a Bash-only array, a sourced file's shebang cannot force the interpreter, and this
   repo explicitly identifies the agent-fence path as a **zsh** Bash-tool context
   (`scripts/lib/paths.sh:11-14`, `scripts/tests/test_shell_primitive_drift.py:129-136`). It would have
   expanded to `. "/paths.sh"`. It also fails under Bash for a basename-only invocation, where `%/*`
   leaves the filename untouched. **The fence already knows the root — `${CLAUDE_PLUGIN_ROOT}` is
   substituted there — so the helper should be told it, not made to rediscover it.** Passing it as `$2`
   is cross-shell by construction and removes the self-location problem rather than solving it.)*

   **Third consecutive round in which the mechanism I wrote in response to a finding was itself
   defective** — an unbraced variable, then a substitution that does not reach sourced files, now a
   Bash-only array in a zsh context. Each was checkable against evidence already in this repository. *(gemini, round 14: "share one code path" was stated without a mechanism, so an
   implementer had to choose between duplicating `paths.sh` — contradicting the claim — and inventing
   `BASH_SOURCE` resolution the plan never mentions.)*
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
   | *(historical — round 3 record, not control flow; the operative row is `reviewer-roster.sh` above)* | `reviewer-roster.sh:53` | `BASE="$(context_reviews_dir)/…"` composes `/reviews/…` and passes it to `context_latest_round_dir` (`:180`) — a root-directory **read** |
   | `agents/swift-reviewer.md:266-269` | **perform no filesystem read at all** and emit the existing `NO CAPTURE (unresolved)` result for **each** reviewer — the fence composes the path *and reads through it*, so "compose nothing" is not by itself a complete instruction. *(Rounds 3 and 4 both left this row restating that no control flow was supplied; round 5 supplies it.)* |
   | `build-failure-log.sh` (`:40`) · `stop-failure-log.sh` (`:36`) · `permission-denied-log.sh` (`:40`) | **round 12 — these three had no control flow at all.** Each calls `log_append` exactly once as its terminal action. On an unresolved base `log_append` is a **no-op returning 0** (§7's writing-primitive rule), so the hook's own behaviour is unchanged: it still exits 0 and still emits whatever the hook contract requires. **No per-script guard is needed or wanted** — adding one would duplicate the primitive's contract. Stated explicitly because "the primitive handles it" is a decision, not an omission |
   | `capture-reviewer-round-start.sh` (`:46`) | calls `context_review_round_bind`, whose unresolved contract is **print nothing, return 0**. The call site already discards stdout and forces success (`>/dev/null 2>&1 \|\| true`), so the hook is unaffected. **Fail-open**: a missing round binding degrades to inference, which is the documented fallback |
   | `capture-reviewer-verdict.sh` (`:45`, `:62`) | composes `ROOT="$(context_reviews_dir)"` — a **sentinel** path when unresolved. **Skip the capture entirely and exit 0**; do **not** attempt the write, and do not fail the reviewer's own run. `capture.py` composes only beneath this `ROOT`, so it is covered transitively (codex, round 11) |
   | `precompact-snapshot.sh` (`:64`) · `sessionstart-restore.sh` (`:32`) | **round 10 — both were entirely absent from this table.** Each composes `SNAP="$(context_snapshot_path)"` and writes/reads the snapshot inline. On an unresolved base: **skip the snapshot write and the restore**, and leave every other behaviour (the hook's own output, its exit code) untouched. **Round 19b — §4.2a carves `sessionstart-restore.sh` out of "the hook's own output … untouched":** it is now the one consumer whose output *does* change, emitting a single non-blocking `additionalContext` line, still `exit 0`. Note the amended predicate — the line fires when the **non-hook path** will fail — `conflict`, `stale` or `failed` — **not** when this hook's own base is unresolved, which in a hook is unreachable |
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
   >   `agents/swift-reviewer.md:266-269` is already on §7's guard list for exactly that. The MAJ-6 bridge
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

   > **HOW A CONSUMER DETECTS THE UNRESOLVED STATE — round 17, gemini.** Every control flow in the table
   > above is conditioned on "an unresolved base", and the plan **forbids string-comparing against the
   > sentinel** (§7's cache rules: a caller must not be able to fake resolution by exporting the sentinel
   > text). It never said what to branch on instead, so each consumer's guard was an invented mechanism.
   >
   > **This applies ONLY to consumers whose control flow actually differs when unresolved** — round 18.
   > The three log hooks and `capture-reviewer-round-start.sh` are explicitly recorded above as needing
   > **no per-script guard**, because the primitive's no-op return already gives them the right behaviour;
   > forcing them to branch would duplicate the contract and contradict their own rows. The consumers that
   > **do** branch are the ones with a divergent path: `reviewer-roster.sh` (fail closed, exit 3),
   > `stop-quality-marker-gate.sh` (guard at entry), `capture-reviewer-verdict.sh` (skip the capture),
   > `pre-commit-checks.sh` / `swift-lint-check.sh` / `swift-build-verify.sh` (skip persistence, keep
   > primary behaviour), the snapshot pair, and the `swift-reviewer.md` fence.
   > *(From the reproduction run: the round-17 wording said "consumers branch on `_UNLEASHED_BASE_OK`"
   > without qualification, directly contradicting four rows of the table two screens above it.)*
   >
   > **Those consumers branch on `_UNLEASHED_BASE_OK`** — `1` resolved, `0` unresolved — the same flag the
   > eager source-time resolution sets, read as `[ "${_UNLEASHED_BASE_OK:-0}" = 1 ]`. It is a plain shell
   > variable in the sourcing shell, so it is available to every consumer that sources any state lib, and
   > **unset is treated as unresolved** so a consumer that somehow runs without the libs fails closed.
   > No consumer inspects a path, and none compares against `/dev/null/unresolved-plugin-base`.

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

7. **Should the never-run-a-hook window be covered by an EXPLICIT publish?** — **OPEN, added round 23.**
   Round 20 dropped the `$HOME` fallback, which leaves one uncovered case: a machine on which no plugin
   hook has ever run has no pointer, so every non-hook shell fails closed. Both round-20 arms said that
   if this must be covered, the honest mechanism is an **explicit publish** — the installer or a
   first-run step writes the pointer deliberately — not a silent read-time fallback. Out of scope for
   §4.2a; recorded here so it is not re-invented as a fallback. *(Round 21 cited this as "§8 Q5"; that
   question is N2 and this one did not exist. The reference is the defect, not the idea.)*

8. **Should the unavailable-state notice live on `SessionStart` or `PostToolUse(Bash)`?** — added round
   23; **ANSWERED in round 25 — `SessionStart`.** §4.2a chooses it because the notice is a
   once-per-session fact, and the predicate is exactly `conflict | stale | failed` *(round 30: this row said `conflict | failed` for two rounds after the predicate changed — it is the fifth site of that family and the one both prior rounds missed)*. Recorded as answered rather
   than left `OPEN`, because §4.2a said "Decided, rather than left open" while this row said `OPEN` and
   §8 closed with "No open questions remain" — three statements, no two agreeing (codex #10).
   `PostToolUse(Bash)` runs immediately after every Bash tool call — i.e. exactly where the unresolved
   state is experienced — and can also address the model (`scripts/lib/hook-io.sh:266-269`). The
   trade-off is timeliness against repetition. *(Round 21 cited this as "§8 Q6"; that question is D′'s
   escape hatch. Same defect as Q7 above: a specific-looking reference to something that was never
   written.)*

**One open question remains: Q7** (explicit publish for the never-run-a-hook window), which §4.2a
places out of scope by design. Q8 was answered in round 25. *(This line previously read "No open
questions remain" while Q7 and Q8 were both marked `OPEN` immediately above it — codex #10.)*
Historically: Round 4 returned `APPROVE_WITH_NOTES` from codex with no High or Medium
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
| 2 | codex | the `swift-reviewer.md` fence's row **restated that no control flow was supplied** rather than supplying it; the fence composes *and reads through* the path | **confirmed** — `agents/swift-reviewer.md:266-269` | the row now mandates no filesystem read and `NO CAPTURE (unresolved)` per reviewer |
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

## 22. Round-13 gate outcome

**codex `APPROVE` (0 findings — no High, Medium or Low) · gemini `REQUEST_CHANGES` (2 High, 1 Low).**
Frozen at `dacd56b`, sha256 `98796d90a53c7c710cf794d90563d9a731963b92df9f52bd50c11cedec8f5471`.
Transcripts: `~/.claude/review-transcripts/2617r13-codex.txt` (347,390 B) and `…/2617r13-agy.txt`
(2,333 B).

**codex's first outright APPROVE on this ticket**, confirming by trace: the consumer table is complete
across marker/log/context/roster/agent-fence/capture/snapshot/test-harness paths; `capture.py` composes
only beneath the root supplied by `capture-reviewer-verdict.sh:45`, so the hook's explicit skip covers it
transitively; the three log-hook rows are correct because `log_append`'s unresolved contract returns
success **before** reaching its `log_dir` composition; and the two capture-hook controls are right — the
round-start call already discards output and forces success, while the verdict hook genuinely needs its
explicit skip because it passes the composed root into Python.

**gemini agreed on every directed check and then found two things codex did not.**

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | gemini | **the bridge helper D′ requires is never specified.** §4.2's option D demands "one documented bridge helper instead of per-agent copy-paste" and D′ restates it as "one explicit bridge", but no path, name or content appears anywhere — while §7's N5 discussion simultaneously defers it to "a future extraction". Step 3 says only "implement the chosen resolution" | **confirmed by grep** — every "bridge" hit is either the option statement, the restatement, or the MAJ-6 fence lines it is meant to replace | **specified**: `scripts/lib/agent-env-bridge.sh`, carrying the export plus the shared source-time resolution and its single diagnostic. `swift-reviewer.md:176`/`:244` become a `source` line; **N5's allowlist gains the file and loses the two fence copies** — one site instead of two, so the copy-paste this ticket exists to kill cannot recur silently |
| 2 | gemini | **§4.1's enum contradicts D′.** It mandates recording `host-env` / `derived-registry` / `legacy-fallback`, but under D′ the base resolves **only** when the variable is set, so the latter two are unreachable — an implementer told to write them could conclude the rejected options A/B are still live | **confirmed** — those are the state spaces of the *rejected* options | the vocabulary is now `host-env` / `unresolved`, D′'s actual state space |
| 3 | gemini | *(Low)* `reviewer-roster.sh:53` appears three times in the consumer table; two rows restate the defect rather than giving control flow | **confirmed** | noted; the duplicate rows are historical round-3/5 records and are marked as such rather than deleted, since they carry why the site was missed |

**The two arms have now inverted their usual roles on this ticket.** codex traced mechanisms and approved;
gemini found two *specification* gaps — an unspecified helper and an enum describing rejected options —
that a mechanism trace would not surface, because both are omissions rather than errors. Neither arm alone
would have reached this state.

## 23. Round-14 gate outcome

**Both arms `REQUEST_CHANGES` — gemini 2 High + 1 Low, codex 1 High.** Frozen at `4e6162f`, sha256
`f852d3eb5c5d1f4212f55f46ad38299815532c60d1b313b0510143ba76a81464`. Transcripts:
`~/.claude/review-transcripts/2617r14-agy.txt` (1,873 B) and `…/2617r14-codex.txt` (300,578 B).

**codex's round-13 `APPROVE` did not survive contact with the fix it approved around.** Round 13's only
substantive change was the bridge helper I specified in response to gemini — and both arms now show that
specification could not work. This is the clearest case yet of the campaign's standing rule: *a fix is a
claim until it is executed or argued from the semantics.*

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **the specified bridge cannot work.** gemini: the round-13 form used **unbraced** `$CLAUDE_PLUGIN_ROOT`, which §1 of this plan says is **unset** in an ordinary Bash-tool shell — it would expand to `source "/scripts/lib/agent-env-bridge.sh"` and crash the fence. codex found the deeper error: even spelled correctly, **`${CLAUDE_PLUGIN_DATA}` inside a sourced `.sh` file is not agent content**, so it receives no substitution and the helper exports an **empty** value — leaving the roster and capture readers unresolved, i.e. re-creating the exact defect this ticket exists to fix | **confirmed** — `scripts/tests/test_doc_gates.py:39-47` documents that only the exact `${CLAUDE_PLUGIN_ROOT}` token is substituted, and `agents/swift-reviewer.md:168-176` documents that substitution happens **in agent content** | the fence **passes the substituted value in**: `source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/agent-env-bridge.sh" "${CLAUDE_PLUGIN_DATA}"` — both exact braced tokens, both in agent content — and the helper takes it as `$1`. **N5's allowlist RETAINS the two fence sites** (they are the injection points and cannot move) and gains the helper; round 13's claim that the fences could be deleted is withdrawn |
| 2 | gemini | **"the bridge and the libraries share one code path" had no mechanism.** An implementer had to choose between duplicating `paths.sh` — contradicting the claim — and inventing `BASH_SOURCE` resolution the plan never mentions | **confirmed** | specified: the helper locates `paths.sh` relative to **itself**, `. "${BASH_SOURCE[0]%/*}/paths.sh"`, never via `CLAUDE_PLUGIN_ROOT`, which is unset in the shells it runs in |
| 3 | gemini | *(Low)* §22 claimed the duplicate `reviewer-roster.sh:53` rows were "marked as historical"; they were not | **confirmed** — I wrote the claim and not the marking | marked |

**What round 13 got right and round 14 does not disturb:** the consumer table's coverage, the log-hook
contract, both capture-hook controls, `capture.py`'s transitive coverage, and the enum correction to D′'s
actual state space. The defect was confined to the one mechanism introduced *in* round 13.

**And the lesson lands on me twice over.** gemini raised the bridge gap in round 13; I specified a bridge
without executing it against the substitution rules **this plan's own §1 documents**, and codex approved
the round that contained it. A specification written in response to a finding deserves the same scrutiny
as the finding — arguably more, because no reviewer has seen it yet.

## 24. Round-15 gate outcome

**codex `REQUEST_CHANGES` (1 High) · gemini — arm did not run (quota).** Frozen at `6ad0559`, sha256
`a4ec574b110f92856179e0c591b7768b7302e0d3da07328e5e6554e47f4e9386`. Transcript:
`~/.claude/review-transcripts/2617r15-codex.txt` (220,978 B).

**codex confirmed the corrected bridge's substitution path and then found its self-location broken.**

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | codex | **`${BASH_SOURCE[0]%/*}` is not portable to the runtime this bridge targets.** `BASH_SOURCE` is a **Bash-only** array; a sourced file's shebang cannot force the interpreter; and this repo explicitly identifies the agent-fence path as a **zsh** Bash-tool context (`scripts/lib/paths.sh:11-14`, `scripts/tests/test_shell_primitive_drift.py:129-136`). In zsh it expands to `. "/paths.sh"` and fails. It also fails under Bash for a basename-only invocation, where `%/*` leaves the filename unchanged | **confirmed** — both cited sources describe the zsh context directly | the helper no longer locates itself: **the fence passes the root as `$2`** and the helper does `. "$2/scripts/lib/paths.sh"`. Cross-shell by construction — the problem is removed rather than solved |

**What codex confirmed sound:** the exact agent tokens resolve, the second `source` argument reaches the
helper as `$1`, and **N5's exact-site allowlist correctly retains both fence injection sites**, adds the
helper, and still rejects a new direct lexical expansion within its narrowed guarantee.

**Third consecutive round in which the mechanism I wrote in response to a finding was itself defective.**
Round 13: an unbraced `$CLAUDE_PLUGIN_ROOT` that §1 of this plan says is unset. Round 14: a substitution
that does not reach sourced files. Round 15: a Bash-only array in a zsh context. **Every one was
checkable against evidence already in this repository** — the plan's own §1, a shipped test's comments,
and `paths.sh`'s header. The corrective is not more care in the abstract: it is to **execute or cite the
specific file that governs a mechanism before writing the mechanism down.**

## 25. Round-16 gate outcome

**codex `APPROVE` (0 findings, second consecutive) · gemini `REQUEST_CHANGES` (2 High, one finding).**
Frozen at `174ba61`, sha256 `d99c8df423657ef2190457319519370e8ac785bc6cac25cb81d8b9bf28d1d6ab`.
Transcripts: `~/.claude/review-transcripts/2617r16-codex.txt` (161,488 B) and `…/2617r16-agy.txt` (900 B).

**codex traced the corrected bridge end to end and approved it:**
- Both exact placeholders are substituted in agent content and passed as **quoted positional
  arguments**; Bash *and* zsh preserve an empty first argument and expose `$1`/`$2`.
- `. "$2/scripts/lib/paths.sh"` is valid in both shells and avoids self-location entirely, matching the
  documented zsh consumer context (`scripts/lib/paths.sh:11-14`).
- With `$1` empty the helper exports an empty value and calls the shared resolver, which treats empty and
  unset identically — poisoned sentinel, `_UNLEASHED_BASE_OK=0`, one bounded diagnostic, no persistent
  read or write.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | gemini | **the helper's body is unspecified.** The signature and the `paths.sh` sourcing are given; the internal logic — in particular what happens when `$1` is empty because the variable is unset upstream — is not, so an implementer must invent the conditional that keeps D′'s state space correct | **both arms are right.** codex showed the behaviour is *derivable* from the shared resolver contract; gemini is right that a plan is not implementable because a behaviour can be derived by a sufficiently careful reader | the four-line body is written out, with the reason it needs **no conditional of its own**: `paths.sh` uses `:-`, so empty takes the same branch as unset, and that branch is D′'s. The conditional lives once, in the resolver — which is the point of having a bridge |

**The two arms disagreed and both were correct**, which is the useful part. codex asks *is this
derivable?*; gemini asks *is this written down?* A specification needs the second, and this plan has now
twice shipped a mechanism that satisfied the first and not the second — the enum, and now the helper body.

## 26. Round-17 gate outcome

**Both arms `REQUEST_CHANGES` — gemini 3 High (two distinct), codex 1 High.** Frozen at `1d9e3ea`, sha256
`c3fb4fbd17046e19aecfa2935a3726514bf54f1e798ea377ad736d4e1db265a9`. Transcripts:
`~/.claude/review-transcripts/2617r17-agy.txt` (2,014 B) and `…/2617r17-codex.txt` (293,087 B).

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | **both** | **the round-16 helper body sources `paths.sh` unconditionally**, breaking the documented absent-file mode. codex measured the failure: **Bash returns 1, zsh returns 127**, the sentinel and `_UNLEASHED_BASE_OK` are never established, and an `errexit` caller **terminates** — contradicting §4.3's non-load-bearing contract | **confirmed** — every shipped lib guards it exactly as `marker.sh:21-24` does, with `[ -r … ] && .` plus an inline fallback | the guard is copied verbatim into the helper. **I wrote a four-line body to close "the mechanism is unspecified" and left out the one line that makes it safe** |
| 2 | gemini | **consumers have no specified way to DETECT the unresolved state.** Every control flow in §7 step 5 is conditioned on "an unresolved base"; the plan **forbids string-comparing the sentinel** and never said what to branch on instead, so each consumer's guard was an invented mechanism | **confirmed** — a genuine gap, and the last one of its kind in this plan | consumers branch on **`_UNLEASHED_BASE_OK`**, read as `[ "${_UNLEASHED_BASE_OK:-0}" = 1 ]`, with **unset treated as unresolved** so a consumer running without the libs fails closed. No consumer inspects a path |

**gemini also confirmed N5's allowlist is correct with the helper's `export` line in it** — N5 flags any
appearance of the identifier unless allowlisted, so listing the helper is both correct and necessary.

**Finding 1 is the fourth round running in which my response to a finding was itself defective**, and the
sharpest instance: the round-16 body existed *only* because gemini asked for the mechanism to be written
down, and I wrote a version that crashes in a mode this plan spends a section defending. The guard was
four lines away in `marker.sh`.

## 27. Round-18 gate outcome — a SECOND double approval that did not reproduce

**Round 18: gemini `APPROVE` + codex `APPROVE` — this ticket's first FULL double approval (both
outright, neither with notes).**
**Reproduction at the identical digest: gemini `REQUEST_CHANGES` (3 High) · codex `APPROVE`.**
Frozen at `63354a9`, sha256 `a501f1b290956fcdc311005f1ab6dde9fb18c64dca017c5d4f606c01675cfbeb` —
**verified byte-identical for both runs**. Transcripts: `2617r18-{agy,codex}.txt` and
`2617r18b-{agy,codex}.txt`.

**THE SECOND DOUBLE APPROVAL ON THIS TICKET, AND THE SECOND TO FAIL REPRODUCTION.** Round 12's flipped
too. Both times the re-run found **real defects the approving run had certified clean** — and this time
codex had approved *twice*, having tabulated all eight shell × value × file-presence cells.

| # | from | finding | verified | fix |
|---|---|---|---|---|
| 1 | gemini *(reproduction)* | **the agent fence FAILS CLOSED on a valid base in absent-`paths.sh` mode.** The three state libs each carry an **inline fallback**, so they always set `_UNLEASHED_BASE_OK`. **The fence does not** — it sources only the bridge (`agents/swift-reviewer.md:266-269`). With `paths.sh` absent the round-17 helper exported the value and returned **without setting the flag**, so round 17's "unset ⇒ unresolved" made the fence emit `NO CAPTURE` **even when `$1` was set and the base was valid** | **confirmed** — a genuine fail-open→fail-closed regression, breaking exactly what §4.3 exists to protect | the helper now **always establishes the flag**, from the value it was handed, whether or not `paths.sh` loaded |
| 2 | gemini *(reproduction)* | **"consumers branch on the flag" contradicts four rows of the consumer table**, which state the three log hooks and `capture-reviewer-round-start.sh` need **no per-script guard** because the primitive's no-op already suffices | **confirmed** — the round-17 sentence was unqualified | branching is scoped to the consumers whose control flow actually **diverges**; the no-guard rows are named as such |
| 3 | gemini *(reproduction)* | **diagnostic cardinality breaks in absent-file mode** — in the two empty-`$1` absent-`paths.sh` cells **no diagnostic is emitted at all**, violating exactly-one-per-process | **confirmed** — same root cause as finding 1 | the helper emits the single diagnostic itself when it resolves unresolved |

**Root cause: two round-17 fixes, each correct in isolation, combined into a regression.** Guarding the
`paths.sh` source (correct — it stopped a crash) and "unset ⇒ unresolved" (correct — it fails closed for
a consumer running without the libs) interact badly on **the one consumer that has no inline fallback of
its own.** Neither reviewer caught it in the approving round; the same reviewer caught it on a re-read of
identical bytes.

**The gate rule has now paid for itself twice on this ticket alone.** Two double approvals, two
reproduction failures, two sets of real defects. *An approving pair is a hypothesis; the reproduction is
the test.*
