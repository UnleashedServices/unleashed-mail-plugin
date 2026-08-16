# COREDEV-2617 — Plugin state splits across two base directories

**Status:** Planning — **ROUND 34 OPEN: §4.2a is PROSPECTIVE CAPABILITY WORK, not a defect fix.**

> **CORRECTION RULE (round 50).** A correction edits the **clause**; the note may only explain why.
> Five times now a finding about a rule was answered by writing the fix into an explanatory
> parenthetical while the operative sentence kept the old contract — the Linux ACL grammar, the
> publisher's own-entry state, Invariant P's marker count, the bridge's empty-`$1` branch (twice). Each
> read as fixed to me and as unfixed to a reviewer, because the reviewer codes the clause. **If a fix
> cannot be expressed by changing the clause, it is not yet a fix.**
>
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
**per-publisher store whose entries are NAMED BY the base value they hold**, written by the side that knows the answer
and read by the side that cannot: it derives nothing, so it does not import the
registry/`CLAUDE_CONFIG_DIR`/cache ambiguity that killed the A+D hybrid in round 2 — a claim round 20
attacked directly and could not break — and it converges the non-hook shell on the **same** store the hooks use
rather than forking a second one. Re-measured: **three** bases exist on this machine, not two. Round 2's
rejection of the hybrid was correct about `pre-commit-checks.sh` and was **over-generalised to every
consumer**. **ROUND 20 GATED §4.2a: both arms `REQUEST_CHANGES`, and both answered the open question the
same way — DROP the `$HOME` fallback step.** That step is gone in round 21, which *simplifies* the
change: §4.3's mandate and §4.4's quarantine ordering now stand **unchanged**, the drift matrix keeps all
four rows, and the resolution enum needs three values, not four. D″ is now **three steps**: the variable,
else the single authenticated entry in the store, else D′'s sentinel byte for byte. `HOME` gates only publication
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
`sessionstart-restore.sh` row — each called out in place; §4.3 and the D′ envelope stand; **§4.4 was rewritten in round 32** — its round-23 block had a false premise and a destructive repair step. *(Round 34: this sentence went on saying "§4.4 … stand" after that rewrite, and the round-32 note quotes this very sentence as the defect it was diagnosing.)*** Previously — **round 18: SECOND FULL DOUBLE APPROVAL (gemini `APPROVE` + codex `APPROVE`) — AND THE SECOND TO FAIL REPRODUCTION.** The re-run at byte-identical bytes flipped to `REQUEST_CHANGES` and found a real **fail-open → fail-closed regression**: the agent fence has **no inline fallback**, so with `paths.sh` absent the round-17 helper never set `_UNLEASHED_BASE_OK` and round-17's "unset ⇒ unresolved" made the fence emit `NO CAPTURE` **on a valid base**. The helper now always establishes the flag and emits the single diagnostic; flag-branching is scoped to consumers whose control flow actually diverges. **Two double approvals, two reproduction failures, two sets of real defects.** See §27. Previously — **round 17 (both arms): the helper body I wrote in round 16 crashes in absent-file mode.** It sourced `paths.sh` **unconditionally** — Bash returns 1, zsh 127, the sentinel is never established, and an `errexit` caller terminates — contradicting §4.3's non-load-bearing contract that every shipped lib honours with a `[ -r … ] &&` guard four lines away in `marker.sh`. Also closed: **consumers now branch on `_UNLEASHED_BASE_OK`** to detect the unresolved state, which the plan had never specified while forbidding sentinel string comparison. See §26. Previously — **round 16: codex `APPROVE` (0 findings, SECOND consecutive) · gemini `REQUEST_CHANGES` ×1 — not a pass.** codex traced the corrected bridge end to end in **both shells**, including the empty-`$1` path. gemini's finding stands anyway: the helper's **body was never written down**, only derivable — so the four-line body is now in the plan, with the note that it needs **no conditional of its own** because `paths.sh`'s `:-` makes empty and unset the same branch. *codex asks whether a behaviour is derivable; gemini asks whether it is written. A specification needs the second.* See §25. Previously — **round 15 (codex `REQUEST_CHANGES` ×1; gemini arm did not run — quota): the bridge's self-location was Bash-only.** `${BASH_SOURCE[0]%/*}` fails in **zsh**, which is exactly the shell this repo documents for the agent-fence path. The fence now **passes the root as `$2`** and the helper does `. "$2/scripts/lib/paths.sh"` — cross-shell by construction. codex confirmed the substitution path and N5's allowlist sound. **Third round running in which my own response-to-a-finding mechanism was defective**, each time checkable against evidence already in this repo. See §24. Previously — **round 14 (both arms): the bridge helper I specified in round 13 COULD NOT WORK.** gemini: unbraced `$CLAUDE_PLUGIN_ROOT` is **unset** in a Bash-tool shell, so the `source` line would have crashed the fence. codex, deeper: **`${CLAUDE_PLUGIN_DATA}` inside a sourced `.sh` is not agent content**, gets no substitution, and the helper would export **empty** — re-creating this ticket's own defect. The fence now **passes the value in** (`source "${CLAUDE_PLUGIN_ROOT}/…/agent-env-bridge.sh" "${CLAUDE_PLUGIN_DATA}"`, both exact tokens in agent content), the helper takes `$1` and finds `paths.sh` via `${BASH_SOURCE[0]%/*}`, and **N5 retains the fence sites**. See §23. Previously — **round 13: codex `APPROVE` (0 findings, its first outright approve) · gemini `REQUEST_CHANGES` (2 High) — not a pass.** codex traced the whole plan clean. gemini found two **specification gaps** a mechanism trace cannot surface: the **bridge helper D′ requires was never specified** (now `scripts/lib/agent-env-bridge.sh`, with N5's allowlist gaining it and losing the two fence copies), and **§4.1's enum listed the state space of the REJECTED options** (`derived-registry`/`legacy-fallback` are unreachable under D′; it is now `host-env`/`unresolved`). See §22. Previously — **round 12: FIRST DOUBLE APPROVAL (gemini `APPROVE` + codex `APPROVE_WITH_NOTES`) — AND IT DID NOT REPRODUCE.** Re-run at the **byte-identical** digest: gemini flipped to `REQUEST_CHANGES` and **found a real defect the approving run had certified clean** — five executable consumers (three log hooks, both capture hooks) had **no unresolved-base control flow at all**, sitting in a bullet list while step 5 demands one per consumer. All five are now table rows; the bullet list is **non-executable sites** only. codex held `APPROVE_WITH_NOTES` across both runs. **The maintainer's reproduce-at-the-same-digest rule paid for itself.** See §21. Previously — **round 11 gated: codex `APPROVE_WITH_NOTES` (1 Low) for the SECOND round running; gemini FAILED to emit a verdict line for the second round running — NOT A PASS.** codex traced all four directed checks clean: consumer scope complete, the mutator rule naming only real mutators, the envelope oracle holding for both new consumers, and N5 narrowed consistently through step 7. The one Low was terminology — `sessionstart-restore.sh` reads and deletes the snapshot, it does not write it. **gemini's failure is a CAPTURE failure, not a review failure** (a ~1 KB summary claiming it printed a critique it did not); both failures are on this ticket, the one where its answer is affirmative. See §20. Previously — **round 10 gated: codex `APPROVE_WITH_NOTES` (1 Low), gemini FAILED (no verdict line) — NOT A PASS.** The round-9 narrowing **held**: codex traced every production read back to an envelope return, found the envelope exhaustive and the `_UNLEASHED_BASE_OK` protocol correct, and raised only the CHANGELOG omission. gemini's arm wrote its critique to a file instead of stdout, so it must be re-run; its findings were triaged anyway and two were real — **there are no `context_snapshot*` writers** (that phrase is struck) and **`precompact-snapshot.sh`/`sessionstart-restore.sh` were absent from the consumer table** (both added). See §19. Previously — **round 9 gated** (**gemini `REQUEST_CHANGES` 5 High · codex `REQUEST_CHANGES` 1 High**). **Fourth consecutive round with a failed proof mechanism, so the claim is NARROWED rather than patched a fifth time.** codex **executed** a bypass with no lexical expansion at all (`n=CLAUDE_PLUGIN_; n="${n}DATA"; printenv "$n"`), proving path provenance is **not statically decidable in Bash**: N5 is now stated as a **lexical drift detector**, explicitly not a proof of accessor-only provenance — the §3.1 move from COREDEV-2497. The oracle asserts on the envelope's **printed return values** (readers' locals are invisible; `_context_round_advance` composes inline as a `python3` argv), and the one-diagnostic-per-process rule is guarded by the shared `_UNLEASHED_BASE_OK` flag so it holds with `paths.sh` absent. Two gemini Highs **rejected with reasons**. See §18. Previously — **round 8 gated** (**gemini `REQUEST_CHANGES` 5 High + 1 Medium · codex `REQUEST_CHANGES` 2 High**). **Round 7 rejected the canary as physically impossible; round 8 rejects its replacement as mechanically impossible** — a Bash shim cannot observe `read < "$path"` (the shell opens before the command runs) or pathname globbing. The oracle now asserts on the **composed path**, which is observable, and leans on the sentinel's executed `ENOTDIR` physics for the rest. **N5 is inverted from a shape blacklist to an enumerated allowlist** — both reviewers bypassed the round-7 predicate in one line each, and round 7's mutant used the one form it already caught. `_context_round_sweep` was missing from **both** the reader and mutator lists. See §17. Previously — **round 7 gated** (**gemini `REQUEST_CHANGES` 1 High + 1 Medium · codex
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
**Ticket:** `COREDEV-2617` (Epic `COREDEV-2485`) · §4.1-§4.4 **High** (the pre-D′ split, now shipped-fixed) · **§4.2a is prospective capability work, not a live defect** — see the HEADER RULE below
**Last Updated:** 2026-08-10 (round 34 — the lock is deleted; per-publisher entries; see §4.2a)
**Measured against:** the branch `feat/COREDEV-2617-plugin-state-base`, worktree `.claude/worktrees/state-base`, plugin `2.7.1`. **No commit is pinned here.** A commit written into the document is stale the moment the next round commits, and it went stale three times while reading as provenance; the reviewing harness pins the commit and the digest in the PROMPT, where it is generated from the tree and asserted before launch, which is the only place that can be kept true. *(Round 34: this pinned `b2496a8` / a worktree that is not this one / plugin 2.6.4 — a **stale provenance pin naming content that is not here**, which is precisely the failure that voided round 33's gate when a prompt did the same thing.)*

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
> (`scripts/tests/test_shell_primitive_drift.py:146`, `:153`). The defect is **not** duplication. It is
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
> parser-safe (the reader selects named keys, `marker.sh:180`).
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
- **Unset or empty:** **no PLUGIN-STATE reads and no writes anywhere** — no legacy path, no
  root-derived path, nothing read from or written to a resolved base — the hook exits **fail-open**,
  and the diagnostic is **bounded and non-persistent** (stderr, not the log). **The store scan §4.2a
  adds is explicitly NOT one of those reads**: it opens `${HOME}/.claude/unleashed-mail/bases/`, which
  is the mechanism by which an unset shell learns the base, and forbidding it would forbid the
  capability this ticket exists to build. Stated because the blanket wording said both: N1's cells
  demanded no reads while §4.2a-S demanded exactly this one.
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
>   at most two lines from **each entry in one fixed directory** — bounded by the number of installed
>   plugin ids, not by anything an attacker controls — never repository or user content, and never
>   anything that
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
| **C** | Keep the env var authoritative; every non-hook entry point exports it | this is the **status quo workaround**, already copy-pasted into `agents/swift-reviewer.md:180-193` and `:255-263` (MAJ-6). Proven fragile: it requires every future call site to remember |
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
> **Acceptance criterion, so "done" is decidable rather than argued.** All three conjuncts, not any one
> of them:
>
> 1. **The capability works.** BUD-5 states this conjunct and governs; what follows is the round-44
>    wording, superseded by it — BUD-5 requires a live store whose COMPLETE `base.*` candidate set is one
>    authenticating entry PRODUCED BY RUNNING a publisher, with zero failing candidates. Historical text:
>    on a machine where **exactly one** authoritative install has published,
>    a shell with no `CLAUDE_PLUGIN_DATA` and no hook environment resolves **the same base that hook
>    resolves**. *(Round 44: the precondition said only "an authoritative hook has published". With TWO
>    installs publishing — the situation this machine is in, and the reason the conflict rules exist —
>    every reader correctly refuses, so conjunct 1 would report the capability broken exactly when the
>    design is working. The criterion has to name the case it is measuring.)*
> 2. **It fails closed everywhere else.** With nothing published, or with a store the reader cannot
>    authenticate, that shell reaches the sentinel with `OK=0` and one diagnostic.
> 3. **D′ is untouched when the variable is set** (row 19 is the standing guard).
>
> …with N6's mutant set green.
>
> *(**Round 32c — the round-29 wording was a DISJUNCTION, and its second arm is D′'s shipped behaviour**,
> so "done" was satisfiable by changing no code at all. A criterion written to make completion decidable
> that is satisfied by the status quo is worse than none: it reads as a bar while certifying whatever
> exists. Conjunction, and the first conjunct is the capability actually working.)*

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
> or a file-presence check (`scripts/ci-load-check.sh:98-101`). Since §1 (`:136-142`) establishes that
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
> | restore consumed it | no `work-context-snapshot-*` remains, per the `rm -f "$SNAP"` at `sessionstart-restore.sh:114` |
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
subprocesses but **not an ordinary shell** (`scripts/lib/paths.sh:22-25`, and §1 `:129`). Reproduced in a
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

   Round 2 (`:361-367`) rejected the A+D hybrid partly on this consumer's account, and that reasoning was
   sound **for the gate's purposes**; what it did not license was generalising "harmless here" to every
   consumer. *(Round 21: 19b paraphrased this as "already documented as unreachable no-ops". The bytes
   say "a harmless local no-op **for the gate**" — the writes were never unreachable, only invisible to
   the gate. The paraphrase is corrected here and the distinction matters, because under step 2 they
   become visible to the gate with no export at all.)*
2. ~~**Hand-run `scripts/*.sh` and CI shells**, which have no hook environment at all.~~
   **WITHDRAWN in round 23 (codex #6) — asserted, never traced.** Checked: CI runs the isolated harness
   (`.github/workflows/plugin-ci.yml:201-203`; the `:423-429` block cited alongside it reports the
   `sed`/`tr` implementation under test and is evidence about the ENGINE, not about harness isolation), which **exports its own temporary**
   `CLAUDE_PLUGIN_DATA` (`scripts/test-hooks.sh:31-35`), so CI is not affected; and the Bash-tool state
   reader already **bridges the authoritative value explicitly** (`agents/swift-reviewer.md:180-193`).
   Neither is a live harmed consumer. **A class with no traced member is not evidence**, and this is the
   third motivation defect on this section — the two before it were a wrong consumer and a nonexistent
   section, both of the same shape: a claim that reads as verified because it is specific. Withdrawn
   rather than patched.
3. **A model-written state path.** `docs/planning/DECISION_JOURNAL_PLAN.md:51` scopes the journal as
   *"written: at a checkpoint, by the model"* and `:64` puts *"the model-written write path"* in scope.
   **Stated honestly: on this branch that plan specifies no writer command, no invocation mechanism, and
   no writer exists in the tree** (`grep -rln journal scripts/` now matches only `scripts/validate-plan-citations.py`, which READS this plan and writes no journal — the conclusion holds, but the evidence originally offered for it, that the grep returned nothing, no longer reproduces). The concrete §4.5b
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

   **EXCEPTION — a non-authoritative shell resolves but never publishes.** A shell whose
   `CLAUDE_PLUGIN_DATA` was *substituted in* rather than *exported by the host* — the `agent-env-bridge`
   fence, whose `$1` comes from agent content — sets `_UNLEASHED_PUBLISH_OK=0` **before** sourcing
   `paths.sh`, and the publish side effect is skipped entirely, reporting
   `_UNLEASHED_POINTER_STATE=none`. *(Round 40, codex High #2: rounds 36 and 38 both asserted this
   exception was "lifted into the operative step-1 statement". **It was not — this is the third note in
   this document claiming an edit that was never made.** And the mechanism as described could not have
   worked anyway: the bridge exports the value and THEN sources `paths.sh`, so the shared resolver would
   publish before any inline branch could report `none`. The suppression must therefore be set before
   the source, which is why it is a variable and not a later decision — a non-authoritative Bash-tool
   shell writing a durable publisher entry is precisely what this exception exists to prevent.)*

   *Then, as a **side effect that cannot affect the line above**:* if `_UNLEASHED_HOME_OK`
   **and `_UNLEASHED_PUBLISH_OK` is not 0**, publish
   **this publisher's own entry** `${HOME}/.claude/unleashed-mail/bases/base.<key>`, where `<key>` is the
   injective encoding of that absolute path — written atomically (tmp + `mv` **in the same directory**),
   fully suppressed, `0600`, into a store created by a single `mkdir -m 700`. Publish **unless** the entry
   already authenticates under the shared predicate **and** its content equals the value — the complete
   reader predicate, not a weaker type-and-content test, so a `0644` REGULAR NON-SYMLINK entry is
   repaired rather
   than reported `current` and then refused by step 2. **(Superseded by PUB-9, which is exact: E0 and E1 compose nothing; E2 derives no key and opens
nothing UNDER THE STORE; E3 runs the `NAME_MAX` probe, which composes the store path; and E4 onward
may have created ancestors. "Every failed publish composes no `${HOME}` path" is true only of E0
and E1.)** If `_UNLEASHED_HOME_OK`
is false the publish takes E1 and **no `${HOME}` path is composed or opened at all**; a publish that
   fails for any OTHER reason composes what PUB-9's exit for that reason composes — E3 runs the
   `NAME_MAX` probe against the store path, and E4 onward may have created ancestors, which ST-2 and
   ST-3 then forbid removing. Either way `_UNLEASHED_POINTER_STATE=failed` and the resolution above
   still stands. *(Round 112, codex: this sentence claimed the E0/E1 property for EVERY failed publish
   while the note two lines above it already said otherwise — the rule-vs-note split, in the paragraph
   whose own note existed to correct it.)*

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
   would not authenticate — and the RESULTING STATE is whatever the ordered post-scan exits assign, not a
   value chosen here.** *(Round 50: round 48 wrote this correction into the note below and left the
   clause still saying "sets `failed`", so the overlap it was meant to remove survived in the operative
   text. Round 48, codex High #2: the clause said the publisher "sets `failed`" if its own
   entry would not authenticate, while the ordered post-scan exits map **any** failing entry — its own
   included — to `stale`. A `0644` own entry satisfied both, so rows 59/60 had no unique expected value.
   The ordered list is authoritative: this clause supplies the OBLIGATION to authenticate, not a second
   mapping.)* One predicate, used by both sides; a second predicate is a second source of
   truth. N6 row 80 mutates the skip test to the weaker form and requires `failed`. *(Round 34: this cited a mutant that does not exist — row 29 carried it and was retired in round 30 with no replacement, so the obligation shipped citing proof that had been deleted. The plan's own words: a citation to a deleted mutant is worse than none, because it reads as proof.)*
2. else, **and only if `_UNLEASHED_HOME_OK`**, **enumerate the store** `${HOME}/.claude/unleashed-mail/bases/`
   and apply the **ordered** reader rules below — a failing entry refuses as `stale`, two or more
   authenticating entries refuse as `conflict`, exactly one resolves (`OK=1`, source `pointer`), none
   falls to step 3. *(Round 32: this step still said "read that pointer", a single file at a fixed path,
   for two rounds after round 30 replaced it with per-publisher entries — the operative algorithm
   disagreeing with its own store.)*
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

**Consequences, all simplifications:** §4.3's round-6 mandate (`:2426`) and its matrix change (`:2432-2436`)
stand **exactly as written**; §4.4's quarantine premise and ordering (`:2459-2466`) stand as written;
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

> **What `mkdir -m 700` does NOT do, executed (round 34).** (a) **It does not create the parent.**
> `mkdir -m 700 /tmp/x/a/b` fails `No such file or directory`, so a clean machine with no
> `~/.claude/unleashed-mail` never publishes — the first publication on a new install, which is the case
> the mechanism exists for. The publisher therefore creates the ancestor first, `0700` when it creates
> it, accepting a pre-existing one under the general rule. (b) **With `-p` it silently succeeds on a
> pre-existing store without applying the mode:** `mkdir -m 700 -p` over an existing `0755` directory
> left it `0755` here. So `-p` may not be used to satisfy the exact-`0700` rule; a store that exists
> with the wrong mode is **refused**, per the rule above. N6 carries both.
Each publisher writes exactly one file:

```
${HOME}/.claude/unleashed-mail/bases/base.<key>      key = an injective encoding of the base value
${HOME}/.claude/unleashed-mail/bases/.pub.<pid>.<uniq>.<key>  transient; outside the base.* glob by construction
```

**Invariant P — the name is a pure function of the bytes. THIS IS THE ONE DEFINITION OF THE ENCODER;
every other mention in this document is a reference to it and adds nothing normative.** A **BYTE walk under `LC_ALL=C`** with **exactly four disjoint markers**:

```
_            -> _u
/            -> _s
upper C      -> _c<lower(C)>
byte >=0x80 or <0x20 -> _x<two lower-case hex digits>
```

*(Round 50, codex High #3: this read "four disjoint markers, **plus a fourth** for every byte outside
printable ASCII" — a leftover from when there were three, which made the RULE itself say four-or-five
while the explanation said four. The markers are now a table, so the count is not restated in prose and
cannot drift from it again.)* The output is
therefore **pure lower-case-safe ASCII**: a case-insensitive volume has nothing to fold, a
**normalization-insensitive volume has nothing to normalize**, and `${#_k}` counts bytes because every
character is one byte.

> **ROUND 34, codex High #1 — case was one member of the aliasing family, not the family.** Executed on
> this volume: `caf\xc3\xa9` (NFC) and `cafe\xcc\x81` (NFD) are distinct byte strings, and creating both
> as filenames yielded **one file**. Two bases that name genuinely different directories on a
> normalization-sensitive target volume would therefore share one entry here — last-writer-wins, the
> reader sees one authentic entry, and the conflict is never reported. The same fix closes the second
> half of that finding: `${#_k}` was a **character** count, so a short string of multi-byte characters
> could pass the `NAME_MAX` budget and still overflow it as a UTF-8 filename. With an ASCII-only output
> the two counts coincide. No fork: the lower-casing is a
`case` arm per letter, not `tr` and not bash-4's `${x,,}` (this repo's floor is bash 3.2.57).

*(**Round 33 — this normative statement carried the round-30 two-pass form for THREE rounds** after
round 31c proved it aliases. The 31c fix went into the note; the 32b fix that was meant to correct the
rule **was discarded by an aborted edit script and I committed a message saying otherwise**. Both
failures are the same one: the rule is the code block, not the paragraph under it.)*
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
> exists to prevent. The temp name is `.pub.<pid>.<uniq>.<key>`, where the suffix is
> derived without a fork; `<uniq>` IS `$RANDOM`, which both target shells provide (P-6) — the earlier
> "without `$RANDOM`" came from a POSIX `sh` framing this family does not target; a publisher that cannot obtain a
> unique temp name **does not publish** and reports `failed`. N6 carries a same-base concurrent-publish
> case and a mutant that reverts the temp name to `$$` alone.

**Conflict is a property of the directory, read at resolution time.** It is not a state one publisher
writes for another to find, so the `CONFLICTED` wire form, its stickiness rule, the
preserve-the-marker precondition, and operator-recovery-by-deletion all **go away**. A reader
enumerates `base.*`, authenticates each, and:

**The rules are ORDERED and the order is normative** — evaluate top to bottom, first match wins:

**Rule −1 comes first: authenticate the STORE, before any entry.** If `bases/` exists but is not a
directory, is a symlink, is not euid-owned, or is not exactly `0700` → refuse: sentinel, `OK=0`,
`SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic. If it does not exist at all → rule 4 (step 3
verbatim). *(Round 40, codex #4: rules 0-4 quantified only over ENTRIES, so a usable `HOME` with an
existing `bases/` at mode `0755` — which the store rule says must be refused — matched no rule at all.
An empty such store fell through to "none" and resolved as step 3 rather than refusing, and a populated
one resolved from entries inside a directory the design had already declared untrustworthy.)*

0. **an entry enumerated but gone when opened — and NOT a symlink** → **skip it; it is not an entry.**
   The test is `[ ! -L "$_f" ] && [ ! -e "$_f" ]`. *(Round 36, codex High #1: the rule tested `[ -e ]`
   alone, and **`[ -e ]` is FALSE for a dangling symlink** — executed in bash 3.2.57 and zsh 5.9, both
   report `-L=true -e=false`. So a store holding one authentic entry plus a dangling `base.*` symlink
   **skipped the malformed entry and resolved the good one**, when malformed-first exists precisely to
   refuse that store. A symlink is always an entry — a hostile one — never a vanished file. N6 row 2 is
   re-aimed to make its symlink fixture DANGLING, the case that discriminates.)* *(This rule lived
   only in prose below the list, so rule 1 matched the vanished entry first and an operator deleting a
   stale entry mid-scan flipped a healthy store to `stale`. A rule that qualifies an ordered list must
   live IN it.)*
1. **any remaining entry fails authentication** → refuse: sentinel, `OK=0`, `SOURCE=unresolved`,
   `POINTER_STATE=stale`, one diagnostic. *A malformed entry is never ignored in favour of a good one.*
2. **two or more authenticating entries** → refuse: sentinel, `OK=0`, `SOURCE=unresolved`,
   `POINTER_STATE=conflict`, one diagnostic naming **neither the targets nor the entry names, only how
   many entries disagree**, and telling the operator to list the store themselves. *(Round 32c: the
   round-31 rule said "naming the entries, never the raw targets" — but Invariant P makes the entry name
   a **lossless, trivially reversible** encoding of the absolute path (`_s` → `/`), so it leaks exactly
   what naming the target would. The redaction was cosmetic and row 64's oracle passed on it.)* §4.1 permits
   the raw path only inside the control file and states it is never emitted to stderr, so a conflict
   message quoting two absolute paths would leak the username and hand attacker-controlled text to a
   terminal (round 31, codex #8). N6 carries a redaction mutant;
3. **exactly one** → resolve to it, `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`;
4. **none** → step 3 verbatim — D′'s fail-closed protocol byte for byte, `POINTER_STATE=none`.

**Three further exits, each stated rather than left to an implementer** (round 31c, kimi). A reader whose
`HOME` is unusable never scans at all and takes step 3 with `POINTER_STATE=none` — the store was never
consulted, so there is nothing to report. **The publisher's post-scan exits are ORDERED, and the order is normative**: its own entry missing →
`failed`; else any entry failing authentication → `stale`; else two or more authenticating →
`conflict`; else `created`/`current` per the write decision. *(Round 36, codex High #4: `stale` and
`failed` both applied when a publisher's own entry had vanished AND another was malformed, with no
precedence — the same overlap the READER's rules were ordered to remove one section earlier, left
unfixed on the publisher side.)* A **publisher** whose post-publish scan finds a failing entry
reports `stale` (the bullet above is reader-framed "refuse"; a publisher has already resolved and does
not refuse, but it must still report what it saw). A publisher whose **own entry vanishes before its scan
observes it** reports `failed` — **whether or not this process wrote it** (round 34, codex #4: the rule
said "between its write and its scan", which does not cover the no-write `current` path, where an
operator removing the entry left rule 0 to skip it and no exit mapped at all) — it cannot assert `created` for a file that is no longer there,
and an operator deleting entries mid-publish is the one cause. *(§6 requires totality to be derived from
the exit paths; the round-30 note claiming the enum was "re-derived from D″-pf's exit paths" overstated
what was actually written down, which is exactly the class §6 exists to catch.)*

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
> `.github/workflows/plugin-ci.yml`'s macOS matrix leg runs on (no line in that file ASSERTS the
> case-insensitivity; the runner simply has it), so `/Data/A` and `/Data/a` alias to one
> entry: last write wins, the reader sees one authentic entry, and the loser diverges silently. The
> encoder therefore **case-folds nothing and escapes case**, with THREE DISJOINT MARKERS after the
> escape character:
>
> ```
> _  ->  _u          /  ->  _s          upper-case C  ->  _c<lower(C)>
> ```
>
> so the output contains **no upper-case character at all** and a case-insensitive volume has nothing to
> fold. Decoding is unambiguous: after `_` exactly one of `u`, `s`, `c` can appear, and `c` consumes one
> further character. The substitution is the walk **Invariant P defines** — see there, and nowhere else,
> for whether it is a byte or character walk — using parameter expansion, **no fork**,
> which is why it is a walk rather than the two `${v//…}` passes it replaces.
>
> **It is a BYTE walk, under `LC_ALL=C`, and both halves are load-bearing** (round 36, codex High #2).
> The rule said "per-character walk" while requiring two hex digits per non-ASCII **byte** and asserting
> every output character is one byte — false for its own input: measured here, `é` is ONE character of
> TWO bytes in both shells, so a character walk emits one unit where the rule demands two. And character
> semantics are locale-dependent, so a key that depends on the ambient locale is not a pure function of
> the bytes — Invariant P's premise. The resolver sets `LC_ALL=C` for the derivation and restores it
> immediately, so it cannot leak into a consumer's environment. N6 requires bash and zsh to produce
> **byte-identical keys for a non-ASCII path**. *(codex also reported that the two shells select
> different units — `c3` versus code point `e9`. That did NOT reproduce here; both returned `c3 a9`. The
> locale defect is real regardless of that particular divergence.)*
>
> **The round-31 wording said only "a two-character sequence" and did not say WHICH — and the obvious
> choice destroys Invariant P.** Executed: with upper-case `C` encoded as `_<lower(C)>`, the marker
> collides with the existing escapes, and `/a_b` and `/aUb` both encode to `_sa_ub` while `/a/b` and
> `/aSb` both encode to `_sa_sb`. **Two distinct bases sharing one entry name is last-writer-wins with no
> detection — this ticket's founding defect, reintroduced by the fix for it.** The three-marker form
> above was executed in `/bin/bash` and `/bin/zsh` on the collision set: identical output in both shells,
> six of six distinct, zero upper-case characters emitted. N6 carries the case-fold collision case, which
> row 44 — testing substitution order — does not cover.)* **So the count of distinct bases IS the count of authenticating entries** —
> no accumulator, no delimiter, no pattern matching, and no dependence on what characters a path
> contains. N6 mutates this back to string accumulation with a space-bearing and a glob-bearing base.

**"Authentication" means the WHOLE predicate — entry clauses AND chain clauses — everywhere the
ordered rules use the word.** *(Round 35: two disjoint clause lists were each presented as the
predicate — the file-level `_unleashed_auth_entry` list, and step 2's chain/target list — and neither
said it composed with the other, so an implementer coding rules 1-3 would apply only the narrow one and
follow a pointer whose ancestor chain was never checked. The composition is now named: an entry
authenticates iff it satisfies the entry clauses AND its target satisfies the chain clauses.)*

**It is ONE predicate, used by both sides.** `_unleashed_auth_entry` requires: a regular
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
local_options no_nomatch` — **guarded by `[ -n "${ZSH_VERSION:-}" ]`, because `setopt` is a zsh builtin
and bash reports `command not found`, which under the `set -euo pipefail` these libs are sourced with
aborts the sourcing shell in exactly the arm the guard protects** — inside the scanning function
suppresses it, and zsh restores the option at
function return — verified by execution, including that a later top-level glob still aborted, proving
the option did not leak. bash instead leaves the pattern literal, so a PRESENCE test is needed in both arms — the two-part
`[ ! -L "$_f" ] && [ ! -e "$_f" ]` form RD-4 mandates, never the one-part `[ -e ]` this passage
used to prescribe: `[ -e ]` is false for a dangling symlink, so the one-part form skips a hostile
entry that must be refused (RD-4 forbids it by name).
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

**Name length is pre-checked.** `getconf NAME_MAX /tmp` is 255 here — **the path argument is required; the bare command fails with `no such configuration parameter` (round 33b, kimi)** (measured: a 250-character suffix
creates, 260 fails `ENAMETOOLONG`). The publisher budgets the **longest** name it will create — the temporary `.pub.<pid>.<uniq>.<key>`, not the shorter final `base.<key>` — and checks that against `NAME_MAX` **before composing any
path**. *(Round 34: the check budgeted `${#_k} + 5`, the FINAL name, while the temp name is strictly longer and is created FIRST, so the guard passed in exactly the case it exists to catch. `<uniq>`'s width is part of the budget and must therefore be bounded.)*; over budget it writes nothing, reports `failed`, and emits one diagnostic naming the length.
Without the pre-check the failure surfaces as a generic write error and leaves a tmp file behind.

**Crash-orphaned temporaries are inert, and that is stated rather than assumed.** A publisher killed
between creating `.pub.<pid>.<uniq>.<key>` and renaming it leaves that file behind forever. It is
**outside the `base.*` glob by construction**, so no reader ever enumerates it and it can never be
mistaken for an entry — but it accumulates. It is not reaped automatically, for the same reason stale
entries are not: any age-based rule is the heuristic round 29 refuted, and being wrong here deletes a
live publisher's in-flight write. N6 asserts an orphaned temporary does not change any resolution.

**Stale entries need a human, and that is stated rather than automated.** An install that is removed
leaves its entry behind, and a reader then sees two entries and refuses. There is **no safe automatic
reaper**: a time threshold is the heuristic round 29 already refuted, and being wrong here deletes a
live install's entry. Recovery is `rm` of the obsolete entry, which the operator finds by listing the store themselves —
**ENC-10 and RD-6 forbid the diagnostic naming any entry or target**, because an entry name is path
material.


### Step 2's authentication — the whole chain, not just the file

Round 20 (codex #3, kimi #3) found the trust boundary enforced at the pointer and its parent and then
abandoned at the destination. `sessionstart-restore.sh` injects snapshot fields into the model's context
via `additionalContext` (§7 row `:2811`), so a pointer naming attacker-writable storage is a
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
  > safer. A blanket rule would refuse the maintainer's own home directory. **ACL-1..ACL-5 are the
  > rule and this paragraph states none of it.** What follows was a platform-independent SUMMARY
  > introduced with the words "the distinction is the rule" — the gloss cited AS the rule, which is
  > what ACL-1 forbids by name. Its own disclaimer ("the per-platform arms below are the definition")
  > does not save it: ACL-1 bans the RESTATEMENT, not merely its normativity, because an implementer
  > who codes the summary never reaches the arms. On Linux the summary is not merely different but
  > UNDEFINED — POSIX `getfacl` emits no `allow`/`deny` token at all, as this document says a few
  > lines below — so coding it finds zero `allow` ACEs and the ACL clause silently NO-OPS on the CI
  > platform. Where it is decidable it inverts ACL-3, which ACCEPTS `user:bob:rw-` under `mask::r--`.
  > The superseded summary read:
  >
  > **Refuse if any component of either chain carries an `allow` ACE that names a principal other than
  > the effective user AND grants a MUTATING right** — the per-platform arms below are the definition,
  > not an elaboration of a broader rule. *(Round 38, codex High #2: this general statement refused
  > **every** other-principal `allow` ACE while the Darwin arm refuses only mutating rights and
  > explicitly accepts read-only ones, and §5's risk row repeated the broad form. Three sites, two
  > verdicts, so a component carrying an inherited read-only ACE had to both accept and refuse — the
  > shared predicate was not decidable as specified. Round 35 narrowed the arm and left the general rule
  > and the risk row broad: half a family, in the fix for an overbreadth defect.)*
  >
  > *(superseded wording: refuse if any component of either chain carries an `allow` ACE naming a principal other than the
  > effective user. Ignore `deny` entries entirely** — they cannot grant the write this rule exists to
  > prevent. Enumeration is `ls -lde` on Darwin (ACE lines are ` <n>: <principal> <allow|deny> <perms>`,
  > so this is string matching, not ACL semantics).
  >
  > **The enumerator is selected by PLATFORM and invoked by ABSOLUTE PATH — never by tool discovery**
  > (round 31, codex High #7). Two defects in the round-30 wording: *"`getfacl` where present"* left the
  > non-Darwin grammar unspecified — **POSIX `getfacl` has no `allow`/`deny` tokens at all**, so a rule
  > written in Darwin's vocabulary is undefined there — and *"where present"* resolves through `PATH`,
  > which differs between a plugin hook and a git hook, so **one machine could reach two verdicts**,
  > breaking the same-predicate constraint this section states two paragraphs below by way of its own
  > enumerator.
  >
  > * **Darwin** (`uname -s` = `Darwin`): `/bin/ls -lde <path>`; refuse on an `allow` line whose
  >   principal is not the effective user **and whose permission set is not wholly READ-ONLY**.
  >
  >   **THE LIST IS AN ALLOWLIST OF READ-ONLY RIGHTS, AND THAT INVERSION IS THE POINT** (round 42).
  >   Refuse unless **every** right in the ACE is one of:
  >
  >   ```
  >   execute  list  read  readattr  readextattr  readsecurity  search
  >   ```
  >
  >   *(Rounds 40 and 41 each added a right to a mutating BLACKLIST — `writesecurity`, then a proposed
  >   `append` — which is the shape that re-opens every round: a right I fail to enumerate is a right
  >   that silently ACCEPTS. Inverted, a right I fail to enumerate REFUSES. The full vocabulary on this
  >   machine is 17 rights (`man chmod`); seven are read-only and the allowlist names exactly those, so
  >   the other ten and anything Apple adds later all refuse by construction.*
  >
  >   ***`append` was REFUTED by execution**, and the two arms disagreed about it: codex reported it
  >   missing from the list, kimi reported it never appears literally. Measured —
  >   `chmod +a "everyone allow append"` on a directory prints `allow add_subdirectory`, the composite
  >   never surfacing, while `writesecurity` DOES print literally. So codex's instance was wrong and its
  >   class was right, which is exactly why the fix is the inversion rather than another entry.)*
  >
  > * **Linux** (`uname -s` = `Linux`): `/usr/bin/getfacl -pc <path>`; the grammar is different and is
  >   specified rather than assumed — refuse **iff both** hold: (a) at least one
  >   **`user:<name>:`, `group:<name>:`, `default:user:<name>:` or `default:group:<name>:`** entry with
  >   `<name>` non-empty carries `w`, **and** (b) the corresponding `mask::` line — `mask::` for access
  >   entries, `default:mask::` for default entries — permits `w`.
  >
  >   **The `default:` prefixes are part of the RULE, not of the note below it** (round 50, codex High
  >   #1). Round 48 wrote the default-ACL correction into the explanatory parenthetical and left this
  >   clause naming only `user:`/`group:`, so an implementer coding the grammar still refused on access
  >   entries alone — the fix existed only in prose. **That is the fifth time a correction landed in a
  >   note while the rule kept the old contract, and it happened in the round whose commit message was
  >   about that very defect.** The discipline is therefore stated as a rule of this document: *a
  >   correction edits the clause; the note may only explain why.* *(Round 35: "and a `mask::` line permitting `w`" was ambiguous between a second independent
  >   trigger and a conjunct of the first. It is a conjunct — a named grant the mask filters out confers
  >   nothing, so refusing on it would be the same overbreadth as the Darwin arm above. `default:`
  >   entries are **CHECKED with the same rule as access entries** — and the round-35 reasoning that
  >   they "grant nothing on the directory itself" was wrong in a way that opened a live injection path
  >   (round 48, codex High #1). A POSIX default ACL determines the ACCESS ACL of newly created
  >   children, and this family CREATES children inside the target: `marker.sh:147` and
  >   `precompact-snapshot.sh:63` both `mkdir -p` under it. So a target carrying
  >   `default:user:attacker:rwx` with a permissive default mask authenticates cleanly, and the `.state`
  >   directory it then creates is attacker-writable — after which snapshot content reaches the model
  >   through `additionalContext`, which is exactly the prompt-injection path this section exists to
  >   close. **Refuse on a `default:` entry granting a mutating right, exactly as for an access entry.**)*
  > * **Any other platform, or the expected enumerator missing at its absolute path:** the condition is
  >   **unevaluable**, so the pointer path is refused — sentinel, `OK=0`, `POINTER_STATE=stale`, one
  >   diagnostic.
  >
  > **`uname` is itself invoked as `/usr/bin/uname`** — round 32: selecting the platform with a bare
  > `uname` would resolve through `PATH` and reintroduce, one level up, exactly the dependence codex
  > High #7 removed from the enumerator.
  >
  > **The publisher runs the ACL clauses too — the "hooks pay zero" claim was wrong and is withdrawn**
  > (round 40, codex High #1). The publisher must run the COMPLETE follower predicate, ACL clauses
  > included, or it can leave an entry the reader will refuse — the `0644` defect in a new costume. So a
  > hook pays the ACL cost as well, and row 92's "a hook resolution performs zero ACL forks" was a
  > direct contradiction of the shared-predicate rule: obeying one falsifies the other. Row 92 is
  > re-aimed at what is actually true — the ACL walk runs **once per resolution, not once per consumer**,
  > because the protocol variables are set once per process.
  >
  > **The cost is real and is stated rather than discovered.** One `uname` plus one `ls -lde` per
  > component of two chains is roughly a dozen forks **per resolution**, on the same source-time path
  > where the encoder is forbidden a single fork. That asymmetry is deliberate: the encoder runs on
  > **every load in five files**, whereas the ACL walk runs **once per process**, on **both** the
  > publisher and the reader paths — a publisher authenticates the entry it is about to leave, so a hook
  > pays it too. §6's budget is therefore stated for both paths, and is measured rather than asserted.
  >
  > *(Round 52, codex and gemini CONCORDANTLY: a third sentence in this paragraph still said "ACL
  > enumeration runs only on the **reader** path, which is taken only when `CLAUDE_PLUGIN_DATA` is
  > unset" — flatly contradicting the two sentences around it and licensing a publisher to skip ACL
  > validation entirely. **Fourth recurrence of this one family.** Rounds 40, 46 and 48 each edited the
  > sentences a reviewer cited and left the others in the same paragraph. The rule that follows from it
  > is now applied here: when a finding names a contradiction, reconcile EVERY sentence in the enclosing
  > block, not the two lines cited.)*
  >
  > Selecting on `uname -s` and invoking by absolute path makes the verdict a property of the **machine**
  > rather than of the invoking shell's environment, which is what "one predicate, both sides" requires.
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
  > **Where ACLs cannot be enumerated, the pointer path is REFUSED — not accepted on mode bits alone.**
  > *(Round 31: the round-30 text said the mode bits were authoritative there. That is the fail-OPEN
  > direction, in the one clause whose whole purpose is a trust boundary the mode bits cannot see.)*
  > **CI IS NOT EXEMPT, and the sentence that said it was would have turned CI red on the first
  > implementation commit** (round 54). It read: *"CI runs Linux, where the harness exports its own
  > `CLAUDE_PLUGIN_DATA` (`test-hooks.sh:31-35`) and never takes the pointer path, so refusing there
  > costs nothing measurable."* **Exporting the variable is exactly what makes the harness a
  > PUBLISHER** — step 1 publishes as a side effect — and a publisher runs the complete predicate,
  > ACL clauses included. So on a `getfacl`-less Linux runner every entry, including the one the
  > harness just wrote, fails authentication; N6 row 1's no-rewrite `mtime` oracle fails and the state
  > is `stale`. **Fifth turn of the hook/ACL-cost family**, found by a consolidation sweep rather than
  > by a reviewer, and the first turn with a consequence outside the document.
  >
  > **So the unenumerable-platform arm needs a CI-viable answer, not an exemption.** On a platform with
  > no ACL enumerator the publisher **skips the ACL clauses for its OWN entry** — it created that entry
  > this instant, at `0600`, in a store it authenticated — while the READER still refuses. That keeps
  > the reader fail-closed (the security property) and keeps a publisher able to publish on a runner
  > with no `getfacl` (the CI property), and it is stated here rather than left to be discovered when
  > the suite goes red. N6 carries a Linux-without-`getfacl` publish-then-verify case. **§5 carries the limit as a risk row rather than leaving it to be
  > rediscovered.** N6 carries a granting-ACE
  > REFUSE case, a deny-ACE ACCEPT case (without which the blanket rule regresses), and a case asserting
  > the probe creates no file.
* *(Round 31: a clause reading "it is not marked conflicted" stood here. The `CONFLICTED` wire form was deleted with the lock — conflict is now a property of the directory, derived at read time — so the clause had nothing to test.)*

> **Why the whole target chain, and not just the target** (round 23, codex #5). The round-21 text called
> this "the whole chain" while authenticating ancestors only from `${HOME}` down to the *pointer's*
> parent, and checking the destination as a single directory. A group- or world-writable **intermediate**
> ancestor of the target lets an attacker replace the validated directory *after* the check and redirect
> the later open — and `scripts/sessionstart-restore.sh:46-47,67-81` opens snapshot content from that
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

**The refuse-not-chmod rule applies to the STORE, `bases/` — not to its ancestors.** A pre-existing
`${HOME}/.claude/unleashed-mail/bases/` whose mode is not exactly `0700` is **refused, not chmod'ed**:
silently tightening a directory the user may have created is a surprise, and the fail-closed path is
already correct. Its **ancestors** — `${HOME}`, `~/.claude`, `~/.claude/unleashed-mail` — need only the
general not-group-or-world-writable rule, which `0755` satisfies.

> **ROUND 34 — this rule aimed at the wrong directory for FIVE rounds, and three sites disagreed about
> whether publication works on the maintainer's own machine.** It read *"a pre-existing
> `${HOME}/.claude/unleashed-mail` with loose permissions is refused"*, with a parenthetical pinning
> `drwxr-xr-x` here and concluding *"the refusal branch is the one that fires"*. Meanwhile the store rule
> says `0755` ancestors are accepted, §4.4 says the hazard *"cannot occur"*, and **N6 row 51 requires
> publication to SUCCEED on a `0755` `~/.claude` — this machine today.** Rule and mutant demanded
> opposite outcomes for the same fixture, and acceptance conjunct 1 failed on the only machine the plan
> measures. `git log -L` proves it: this rule was last touched in round 25, five rounds before the store
> moved to `bases/`. **Tenth half-a-family, and again the rule kept the old target while the paragraphs
> around it were updated.**

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
**no state is written to any base other than the one the resolution returns; the single exception is this
publisher's own entry in the store, which carries the base path and nothing else; and when resolution
fails, **no plugin-state payload is read or written anywhere** — the bounded read of the store's entries
being the one exception, since an invalid entry cannot be rejected without reading it.**
*(Round 32: §4.1's copy of this invariant was updated in round 31 and this one was not — one family, half
swept, found by the pre-gate sweep rather than by the gate.)*

§5's inert-gate mitigation (`:2525`) is amended **in place**, not by reference — see the round-21 note
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
`conflict`, `stale` or `failed`, and stays silent on `created`/`current`/`none`. **It does NOT fire "exactly when the non-hook path will fail"**: `none` is also an unresolved state — the store held no entry — and the notice is deliberately silent there, because a machine that has never published is the ordinary first-run case and not a fault to report. SS-1 states the predicate; this sentence restates its members and must not restate a rationale that contradicts it. *(Round 112, codex.)* This is a statement about
the *other* shells, which is the state the maintainer actually experiences and which no hook could
otherwise report.

The draft's justification was also false. *"`SessionStart` is the only hook that can address the model"*
is contradicted by the tree: `scripts/lib/hook-io.sh:266-269` defines `hook_emit_posttool_context()` and
`:275-278` `hook_emit_posttool_block()`. Both cited call sites in fact call the CONTEXT helper, not this one — `scripts/swift-build-verify.sh:71` is `hook_emit_posttool_context` — so "both in production use" was a claim about a function neither line calls. The true statement is narrower: **`PostCompact` cannot inject
context; `SessionStart` and `PostToolUse` can.** `SessionStart` is chosen over `PostToolUse(Bash)`
because the notice is a once-per-session fact, not a per-call one; **§8 Q8** (added by this round)
records the `PostToolUse(Bash)` alternative. *(Round 21 cited "§8 Q6", which is D′'s escape hatch —
another reference to a question that did not exist.)*

This **amends §7's consumer row** (`:2811`), which currently requires both snapshot scripts to leave
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
to kill, and §4.3's round-6 mandate (`:2426`) requires that `paths.sh`'s absence change *who computes* the
answer, never *what the answer is*. So the three-step logic lives in five files **by design**, and N6
must **prove the arms agree** rather than assume it — on `_UNLEASHED_BASE_RESOLVED`, `_UNLEASHED_BASE_OK`,
`_UNLEASHED_BASE_SOURCE` **and `_UNLEASHED_POINTER_STATE`**. *(Round 32: the fourth was omitted, and it is
the one round 31's ordered reader rules and the notice predicate both consume — so five copies could
disagree about what to report while agreeing about what they resolved, and nothing would catch it.)*

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
> Also re-check `N5LexicalDrift.ALLOWLIST` — in `scripts/tests/test_plugin_state_base.py`, where that
> class actually lives; it was cited against `test_shell_primitive_drift.py:158-170`, a file that
> exists, has never held the class, and whose `:158-170` implements the absent-`paths.sh` matrix, so
> the citation named real lines of the wrong file and read as verified. **No line number is given
> here**, because the allowlist is keyed by FILE and a line pin is what went stale — for the pointer
> path's expansion sites, keep
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
| 1 | publish always (drop the COMPLETE-PREDICATE skip) | mtime unchanged on a no-change second run |
| 2 | accept a symlink pointer — fixture must be a **DANGLING** symlink | a dangling `base.*` symlink yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic; it is NOT skipped as vanished |
| 3 | accept a relative path | an entry holding `foo/bar` yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic, and a conforming entry beside it does NOT win |
| 4 | accept a multi-line ENTRY (ENT-2, reader side) | a two-line entry yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic, and a conforming entry beside it does NOT win |
| 5 | accept a non-existent target | a DANGLING target path yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 6 | **accept a target that exists but is not a directory** | a target that is a regular file, not a directory, yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 7 | **drop the pointer-owner check** | an entry owned by another uid yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 8 | **accept any entry mode** | an entry at `0644` yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic, and a conforming entry beside it does NOT win |
| 9 | **drop the trailing-slash rejection** | an entry holding `/a/b/` (trailing slash) yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 10 | **drop the NUL rejection** | an entry holding an embedded NUL yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 11 | ~~accept a group-writable pointer parent~~ **RETIRED round 66 — equivalent to row 22**, which covers the whole ancestor chain including the parent. N6-9 ordered this retirement and the row kept printing, so N6-1 read it as live |
| 12 | accept a group-writable target | a `0775` target component yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic, and a conforming entry beside it does NOT win |
| 13 | **accept a group-writable target ANCESTOR** | a safe target beneath a `0775` ancestor yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 14 | **accept a symlinked target ancestor** | a symlinked ancestor yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 18 | compose a `${HOME}` path with `HOME=""` | no `${HOME}`-rooted open attempted |
| 19 | **let `HOME=""` suppress a valid `CLAUDE_PLUGIN_DATA`** | set variable still resolves, `OK=1` |
| 20 | stamp `host-env` for a pointer resolution | record carries `base_resolution=pointer` |
| 21 | **drop the owner check on a pointer-path ANCESTOR** | an ancestor owned by another uid yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 22 | **accept a writable ancestor anywhere in the entry chain** (this row covers the WHOLE chain, parent included; row 11 was retired into it) | a `0775` grandparent yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic |
| 23 | **drop the target's own owner check** | a target owned by another uid yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 24 | **drop the owner check on a target ANCESTOR** | a target ancestor owned by another uid yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 25 | **accept a SYMLINKED TARGET itself** (row 14 covers only an ancestor) | a symlinked target yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 26 | **accept a store at `0755`** | the store-level outcome, not the rule name: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, exactly one diagnostic — N6-6 requires the oracle to name what the RESOLUTION does, because "rule enforced" is satisfied by any refusal anywhere |
| 27 | **require euid ownership ABOVE the trust anchor** | a root-owned `/` and `/Users` above the trust anchor still RESOLVE — the store RESOLVES: `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`, and stderr is empty |
| 28 | **accept a group-writable system prefix** | a group- or world-writable `/` yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 33 | **accept an off-`${HOME}` target with a user-writable intermediate** | a target beneath a `0777` ancestor yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 34 | **require euid ownership of an all-root off-`${HOME}` target** | an all-root-owned system target above the trust anchor authenticates and the store RESOLVES to that target: `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`, empty stderr |
| 35 | **refuse a readable but UNWRITABLE target** | a readable but UNWRITABLE target still authenticates and the store RESOLVES to that target: `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`, empty stderr; its writes no-op and the sourcing shell survives |
| 42 | **accumulate distinct targets as a space-delimited string, tested for membership** | **two entries, both authenticating, whose base values are `<S>/b* <S>/c` and `<S>/c`** — the first an existing directory chain the harness creates with one `mkdir -p "<S>/b* <S>/c"`. Correct: two distinct base values, rule 2, `conflict`. Under the mutation the accumulator holds `<S>/b* <S>/c` when `<S>/c` is tested, `case " $acc " in *" <S>/c "*` MATCHES the trailing space-delimited run, the second entry is judged already present, the count is ONE, rule 3 fires and the reader RESOLVES with `OK=1`, `SOURCE=pointer`. Opposite reader rules. **The containing value must be SCANNED FIRST, and it is**: keys sort `_sa_sb* _sa_sc` before `_sa_sc`, verified with the encoder. **EXECUTED in bash 3.2.57 and zsh 5.9 against the membership form §4.2's round-30 note records: correct 2 / mutant 1 here; the round-104 fixture `/a b`, `/a`, `/b` gives 3 / 2 and the round-106 fixture gives 2 / 2 — both `>= 2`, both `conflict`, neither discriminating.** *(Round 108, codex, THIRD consecutive miss on this row. Rounds 104 and 106 each REASONED about the count — and each modelled a tokenising split, which is not what the mutation does. The rule this row now carries is that a fixture for a counting mutant is executed against the documented mutant form before it is written down.)* |
| 43 | **count entries without the name↔content check** | an entry whose name does not encode its content yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win, and is NOT counted toward the conflict tally |
| 44 | ~~swap the encoder's substitution order~~ **RETIRED round 34 — equivalent mutant.** Executed against the per-character walk in both shells: reordering the `case` arms produced byte-identical output for all seven collision-set values, so the row passed with the mutation applied. Injectivity is covered by rows 43, 63, 69 and 75 |
| 45 | **derive the key with command substitution** | the ENCODER forks zero times — scoped to the key derivation, not to the whole resolution, which forks for the ACL enumerator |
| 46 | **drop `no_nomatch` from the scan** — run in **each of the five family files** under zsh | an empty store does not terminate the sourcing shell, in all five arms |
| 47 | ~~drop bash's literal-glob `[ -e ]` guard~~ **RETIRED round 52 — equivalent mutant.** Round 36 gave rule 0 the test `[ ! -L ] && [ ! -e ]`, which skips the unmatched literal `base.*` whether or not the guard is present, so the mutation changes no observable. Rule 0 now carries the obligation |
| 48 | ~~treat an enumerated-then-vanished entry as malformed~~ **RETIRED round 104 — duplicate of row 77.** Both mutate the vanished-entry skip and both observe an operator deletion mid-scan; N6-4 forbids two live rows naming one mutation with one discriminating case | — |
| 49 | **scan before publishing** | the racing publisher REPORTS `conflict`, not `created` — the durable file set is identical under both orders, so only the reported state discriminates |
| 50 | **create the store `mkdir` then `chmod 700`** | no window exists in which another publisher observes `0755` |
| 51 | **put the entries directly in `~/.claude/unleashed-mail`** | the entries live in `~/.claude/unleashed-mail/bases/` and THAT directory is `0700`, asserted directly; `~/.claude/unleashed-mail` itself may be `0755` and ST-4 accepts it. Under the mutation the entries sit in a `0755` directory and the exact-0700 store rule is enforced on nothing. *(Round 104: "publication succeeds" is true of both implementations and discriminated nothing.)* |
| 52 | ~~drop the NAME_MAX pre-check~~ **SUPERSEDED by row 81** — the temp name is strictly longer and created first, so both halves of the old oracle held under the mutation |
| 53 | **let a publisher write an entry that is not its own key** | a publisher touches only `base.<key(its value)>` and its own tmp |
| 54 | **remove the harness `HOME` sandbox** | the developer's real store is byte-identical after `test-hooks.sh` |
| 55 | **ignore ACLs entirely** | a component that the PLATFORM ARM refuses — Darwin: an `allow` ACE for another principal naming any right outside ACL-2's seven-right allowlist; Linux: ACL-3's named grant AND mask conjunct — yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic, while a read-only `allow` RESOLVES (row 90) and a named grant the Linux mask filters out RESOLVES (row 91). The oracle names the ARMS because a mutating-right formulation is the gloss ACL-1 forbids, and on the Linux fixture it asserted the OPPOSITE of live row 91 for one machine state |
| 56 | **refuse on any ACE, `deny` included** | `$HOME`'s real `group:everyone deny delete` still RESOLVES — the store RESOLVES: `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`, and stderr is empty; `deny` entries are ignored entirely |
| 57 | **let the ACL probe write a test file** | the ACL probe creates nothing anywhere, and a PRE-CREATION refusal creates nothing (ACL-6). Ancestors created before a LATER failure are left in place — that is E4's behaviour, not a violation of this row |
| 58 | **admit a root conditional on `CLAUDE_CONFIG_DIR`** | publisher and reader reach the SAME verdict in different environments |
| 59 | **drop a declared value from the enum** | every publish exit still maps to a declared value |
| 60 | **assign a publish exit the wrong enum value** | each exit's value is the one §6's derivation gives |
| 61 | **reorder the reader rules so a good entry wins over a malformed one** | one valid PLUS one malformed entry yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — rule 1 outranks rule 2, so the good sibling does NOT win and the state is NOT `conflict` |
| 62 | **revert the temp name to `$$` alone** | two same-base publishers cannot open the same temp inode |
| 63 | **case-fold the encoding** | `/Data/A` and `/Data/a` produce distinct entries on a case-insensitive volume |
| 64 | **emit raw target paths in the conflict diagnostic** | no absolute path reaches stderr |
| 65 | **let `agent-env-bridge.sh` stay D′-only** | with empty `$1`, `paths.sh` absent and one valid entry, the fifth copy RESOLVES it and reports all four protocol variables — not `OK=0` |
| 66 | **omit parent creation for a missing `~/.claude/unleashed-mail`** | a clean install publishes, and reports `failed` only on a real error |
| 67 | **select the ACL enumerator with `command -v` instead of `uname -s` + absolute path** | publisher and reader agree under different `PATH`s |
| 68 | **fall back to mode bits where no enumerator exists** | an unevaluable ACL condition yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic; it does not accept on mode bits alone |
| 69 | **encode upper-case as `_<lower>` instead of `_c<lower>`** | `/a_b` vs `/aUb`, and `/a/b` vs `/aSb`, produce DISTINCT entries |
| 70 | **let an orphaned `.pub.*` temporary be enumerated** | a crash-orphaned temporary changes no resolution |
| 71 | **give the harness its own copy of the chain-walk predicate** | the fixture seam feeds the SAME accessor production uses |
| 72 | **let the quarantine remove and re-create `~/.claude/unleashed-mail`** | every entry under `bases/` survives the sweep byte-identical, and the entry SET is unchanged |
| 73 | **omit `_UNLEASHED_POINTER_STATE` from arm equivalence** | **this row mutates the HARNESS, not production, so its oracle is a META-TEST**: the arm-equivalence harness must itself fail when one copy is made to report a different `_UNLEASHED_POINTER_STATE` while the other three protocol variables agree. A row that removes an assertion changes no production outcome, so nothing but a deliberately divergent fixture can detect it |
| 74 | **drop the `ZSH_VERSION` guard around `setopt`** | a bash arm sources cleanly under `set -euo pipefail`, with no `command not found` |
| 75 | **use the two-pass `${v//…}` encoder** (the pre-31c normative form) | `/Data/A` and `/Data/a` produce distinct entries |
| 76 | **select the platform with a bare `uname`** | publisher and reader agree under different `PATH`s |
| 77 | **move the vanished-entry skip below rule 1** | an operator deleting an entry mid-scan does not flip a healthy store to `stale` |
| 78 | **satisfy the acceptance criterion with D′ unchanged** | conjunct 1 fails — a non-hook shell must resolve the SAME base a hook resolved |
| 79 | **name entry names in the conflict diagnostic** | no path material, reversible or otherwise, reaches stderr |
| 80 | **skip publication on the weaker type-and-content test** | a `0644` REGULAR entry with matching content is REPUBLISHED and reports `created`, never `current`; a SYMLINKED `base.<key>` is not republished at all — ST-7 refuses it and reports `failed`, so the two shapes carry different oracles |
| 81 | **budget `NAME_MAX` against the final name instead of the temp name** | a key that fits `base.<key>` but overflows `.pub.<pid>.<uniq>.<key>` reports `failed` and creates nothing |
| 82 | **use `mkdir -m 700 -p` instead of one-at-a-time creation** | **MEASURED: `mkdir -m 700 -p a/b/c` under `umask 022` leaves the INTERMEDIATES at `755` and applies `700` only to the final component; one-at-a-time `mkdir -m 700` gives all three `700`.** Fixture: `.claude` and `unleashed-mail` both absent. The oracle asserts their MODE directly after the run — correct: both `0700`; mutated: both `0755`. **The oracle must be the mode, NOT a refusal**: ST-4 holds ancestors only to not-group-or-world-writable, which `0755` satisfies, so E4's authentication accepts either and no resolution outcome differs. *(Rounds 100 and 102: the earlier ACL-inheritance fixture was UNREACHABLE — a parent carrying a refusing ACL is refused before any child is created — and my first replacement claimed authentication would refuse `0755`, which ST-4 contradicts. Both were caught by measuring rather than reasoning.)* |
| 83 | ~~omit ancestor creation on a clean install~~ **DELETED round 64 — duplicate of row 66** (one mutation, one fixture). N6-4 ordered this in an earlier round and the row kept printing, so N6-1 read it as live |
| 84 | ~~assert arm equivalence on three variables~~ **DELETED round 64 — duplicate of row 73.** Same as 83: ordered deleted, never struck |
| 85 | **leave non-ASCII bytes unescaped in the encoder** | NFC and NFD spellings of one path produce DISTINCT entries on a normalization-insensitive volume |
| 86 | ~~count characters rather than bytes in the NAME_MAX budget~~ **RETIRED round 52 — equivalent mutant.** Invariant P guarantees an ASCII-only key, so character and byte counts necessarily coincide and the mutation is a no-op. The property it aimed at is now structural (the encoder cannot emit a multi-byte character), not testable by mutation |
| 87 | **verify only N1–N5** | the pointer suite N6 is required, not optional |
| 88 | **scope the vanished-own-entry exit to the write path** | the no-write `current` path also reports `failed` when its entry is removed before the scan |
| 89 | **apply only the entry clauses in rules 1-3** | an entry whose TARGET chain fails yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a CONFORMING entry beside it does not win |
| 90 | **refuse on a read-only `allow` ACE (Darwin)** | an inherited read-only ACE, as MDM fleets carry, still RESOLVES — the store RESOLVES: `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`, and stderr is empty |
| 91 | **treat the `mask::` clause as an independent trigger (Linux)** | a named grant the mask filters out still RESOLVES — the store RESOLVES: `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`, and stderr is empty |
| 92 | **re-run the ACL walk per consumer instead of once per process** | **READER-path fixture** (`CLAUDE_PLUGIN_DATA` unset, one authenticating entry): five sourced libraries in one process perform ONE ACL walk between them. The fixture must be reader-only — a PUBLISHER walks each chain more than once by construction (BUD-1), so a publish cell would fail this row against a CORRECT implementation |
| 93 | **derive the key without pinning `LC_ALL=C`** | bash and zsh produce BYTE-IDENTICAL keys for a non-ASCII path |
| 94 | **let `LC_ALL=C` leak past the derivation** | a consumer's locale is unchanged after the resolver runs |
| 95 | **leave the publisher's post-scan exits unordered** | own-entry-missing plus another malformed entry reports `failed`, not `stale` |
| 96 | **enumerate publish exits only** | dropping `none` from the declaration FAILS, because reader rules 3-4 emit it |
| 97 | ~~let the bridge's prose branch return the sentinel for empty `$1`~~ **DELETED round 64 — duplicate of row 65** (one fixture, one oracle) |
| 98 | **add a right to the read-only allowlist that is not read-only** (e.g. `writesecurity`) | an `allow writesecurity` ACE for another principal yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — the allowlist admits exactly the seven read-only rights |
| 99 | **ignore `_UNLEASHED_PUBLISH_OK` in step 1** | the agent fence resolves without writing any entry |
| 100 | **set `_UNLEASHED_PUBLISH_OK` after sourcing `paths.sh`** | the fence still writes nothing — the flag must precede the source |
| 101 | **leave an existing `bases/` at `0755` unhandled by the reader rules** | a usable `HOME` with an unauthenticated STORE refuses as `stale`, not resolves |
| 102 | **treat the ACL rights list as a mutating BLACKLIST** | a right absent from the seven-right allowlist yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic |
| 103 | **omit `_UNLEASHED_PUBLISH_OK=0` from the bridge BODY** | the fence writes no entry even though step 1's rule alone would permit it |
| 104 | **ignore `default:` ACL entries (Linux)** | a target carrying `default:user:other:rwx` **with NO `default:mask::` line, or with one permitting `w`** — the conjunct ACL-3(a) requires, without which the same entry is ACCEPTED — yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — the `.state` it would create must not be attacker-writable |
| 105 | **let the own-entry clause assign a state directly AND RETURN, skipping the ordered post-scan exits** | **an AUTHENTICATING own entry beside a MALFORMED FOREIGN entry.** Correct: the own entry passes the complete skip predicate so nothing is rewritten, the post-scan meets the foreign entry, and the ordered exit P2 reports `stale`. Under the mutation the own-entry clause assigns `current` and RETURNS, so the foreign entry is never met and the publisher reports `current`. *(Round 108, codex: round 106's fixture used a `0644` own entry, which FAILS the skip predicate — so PUB-7 republishes it at `0600`, the scan reaches P4 and the specification reports `created`, not `stale`. The early return was the right shape and the oracle started from the wrong specification result, which no change to the mutation could repair. Round 106 fixed the mutation and left the fixture.)* |
| 106 | **apply the ACL clauses to the publisher's OWN entry where no enumerator exists** | TWO publishes in sequence on a runner with no enumerator: the first reports `created`, and **the second reports `current` without rewriting** (asserted by mtime). The second run is what discriminates the WRITE-OR-SKIP site — on a first clean publish there is no existing entry for that authentication to reach, so a mutation confined to it passes a single-publish oracle |
| 107 | **skip the ACL clauses for a FOREIGN entry where no enumerator exists** | exercised on the PUBLISHER's post-scan, not the reader: E4 gives the publisher the absent-enumerator carve-out for the STORE chain, so it proceeds to scan, and a FOREIGN entry it then meets must still refuse — the publisher reports `POINTER_STATE=stale`. A reader fixture cannot discriminate this: rule −1 applies the same unevaluable ACL condition to the store chain and returns `stale` before any entry is examined, with and without the mutation |
| 108 | **make a `failed` publish silent** | every publish exit reporting `failed` emits exactly ONE line — a store at a refusing mode is diagnosed on every invocation instead of failing in silence (PUB-11) |
| 109 | **derive the key before testing TGT-1** | an unpublishable value opens NOTHING under the store: no key, no ancestor creation, no temporary, no scan (PUB-9 E2) |
| 110 | **refuse the store because it holds a path the `base.*` glob does not match** | a junk file or subdirectory beside the entries does NOT deny the capability — the store still RESOLVES (the store RESOLVES: `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`, and stderr is empty) — while a DIRECTORY named `base.<k>` yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic |
| 111 | **accept a symlinked ancestor of the store** | a symlinked ancestor of the store yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic, under rule −1 and RD-10 clause (d) alike |
| 112 | **publish a base value containing a NEWLINE** | a base value containing a NEWLINE is UNPUBLISHABLE: the PUBLISHER reports `SOURCE=host-env`, `OK=1`, `POINTER_STATE=failed`, one diagnostic, and NO entry or transient exists afterwards |
| 113 | **repair a `base.<key>` that is a symlink or a directory** | THREE fixtures, because two of them are caught by a test the third is not: a symlink TO A DIRECTORY (the transient lands outside the store), a DIRECTORY (it lands inside it), and a **DANGLING symlink** — where `[ -e ]` is FALSE, so a one-part presence test does not fire at all and `mv -f` exits 0 having silently replaced the link (measured). All three must report `failed` with nothing written; an implementation using `[ -e ]` alone passes the first two and fails this one |
| 114 | **compare a mode with the low NINE bits** | a `chmod 1700` store yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic; a `chmod 4600` entry yields the same, and a conforming entry beside it does not win — the exact-mode clauses mean all twelve bits, and both P-2 arms reported `700`/`600` for those fixtures before round 66 |
| 115 | **skip P-4's post-create mode readback** | under a POSIX default ACL that grants beyond the umask, the transient is created at other than 0600 and the publisher REFUSES (`failed`, transient removal ATTEMPTED — best-effort per ST-7) instead of renaming it onto the entry. Linux-only fixture; runs once the CI probe has measured P-4 under `setfacl -d` |
| 116 | **open the TRANSIENT name before testing what is there** | the publisher does not HANG. Measured: `set -C; : > fifo` never returns in either shell (`rc=124` at a 5s timeout). The oracle is the absence of the hang, NOT a `failed` state: TMP-1 permits three TOTAL attempts with a fresh `$RANDOM`, so a correct implementation may skip a FIFO'd candidate and publish successfully on the next name — an oracle demanding `failed` would fail a correct implementation |
| 122 | **ignore UNNAMED default ACL entries on Linux** | THREE fixtures, all `0700` and euid-owned — `default:group::rwx` with NO mask, `default:group::rwx` under `default:mask::rwx`, and `default:other::rwx` under `default:mask::r-x` — each yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic. Linux-only; gated on the CI probe |
| 120 | **apply the ACL clauses at PUB-7's target-chain check on an enumerator-less platform** | a publisher on a box with no enumerator PUBLISHES and reports `created`; under the mutation it reports `failed` at E2. Row 106 covers only own-entry authentication and cannot discriminate this site |
| 121 | **apply the ACL clauses at PUB-9 E4's store-and-ancestor check on an enumerator-less platform** | same fixture, same oracle, different exit — under the mutation the publisher fails at E4 instead. AUTH-1(h) enumerates FOUR carve-out evaluations — the own-entry pair (i)/(ii), E4's store chain (iii) and PUB-7's target chain (iv) — and rows 106, 120 and 121 pin them, row 106 covering the own-entry pair with its two-publish oracle |
| 127 | **make a FOURTH attempt at a transient name** | with the first three candidate names occupied and the fourth FREE, the publisher takes E5 and reports `failed`, writing nothing — it does NOT publish on the fourth. Row 116 asserts only the absence of a hang, so a three-attempt and a four-attempt implementation both pass it; this row is the only one that pins TMP-1's TOTAL |
| 126 | **redirect the read-only probes' stdout to `/dev/null` along with the mutating commands** | resolution still WORKS: `uname`, `getconf`, `stat`, `ls -lde`, `getfacl` and `id -un` have their stdout CAPTURED because it is the answer, and the transient receives the base value as content. Under the mutation every primitive returns empty, the mode/uid/ACL decisions all read as unevaluable, and the store refuses on a healthy machine — a fail-CLOSED collapse that a test asserting only "no crash" would miss |
| 130 | **drop ENT-2's read-status clause, keeping only the byte count and the zsh NUL test** | the entry holds **an authenticating target — the harness's own `0700` euid-owned sandbox directory** — followed by a NUL and NO newline. The specification refuses it in both shells: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic. Under the mutation **bash AUTHENTICATES it and the reader RESOLVES** (`OK=1`, `SOURCE=pointer`) because the terminal NUL is counted as the required newline — `rc=1`, `size=len+1`, `${#line}+1=len+1` — while zsh still refuses, so a zsh-only cell cannot discriminate it and the oracle is the BASH arm. **The target may not be `/private/tmp`**: measured `drwxrwxrwt`, mode `1777`, so PCH-1 refuses that chain as world-writable with or without the mutation and both trees report `stale`. *(Round 106, codex: the round-104 row named `/private/tmp` because it is what the ENT-2 measurement used — a fixture inherited from a PRIMITIVE's demonstration, where no chain is walked, into a MUTANT, where one is.)* |
| 131 | **carve out the publisher when the identity probe fails while the ACL enumerator EXISTS** | the publisher REFUSES: `POINTER_STATE=failed`, one diagnostic, no entry written. Under the mutation it skips the ACL clauses and publishes into a store it could not evaluate — the fail-open AUTH-1(h) forbids for a present-but-failed probe. **Driven through the IDENTITY-PROBE SEAM of §7 step 3f(iii), not by breaking `/usr/bin/id`**: the probe is invoked by absolute path, so an unprivileged harness cannot make it fail while leaving `/bin/ls -lde` present and succeeding, and N6-10 requires every mutant to be runnable unprivileged. The seam is the SAME accessor production calls, per N6-10. Row 129 mutates an untyped PRINCIPAL, not a failed probe, and cannot discriminate this. *(Round 106, codex: the round-104 row prescribed a fixture no unprivileged harness can build, which is a row that cannot be RUN rather than one that cannot fail — N6-3 names both as equally worthless.)* |
| 132 | **walk a component chain a second time on the READER path** | BUD-1 gates the DERIVED INVOCATION COUNT: §6's harness counts, per resolution and on each of the `created`, `current`, `conflict`, `stale`, `failed` and `none` paths, EVERY EXTERNAL INVOCATION THE RESOLUTION MAKES — enumerated here so that nothing counted lives only in a primitive: `/usr/bin/uname -s`, `/bin/ls -lde`, `/usr/bin/getfacl -pc`, **`/usr/bin/stat`** (P-2's per-component accessor on the BASH arm), **`/usr/bin/id -un`** and **`/usr/bin/dsmemberutil getuuid -U`** (P-3a's principal name and UUID, once each per resolution), and on the publish path **`/usr/bin/getconf`** (NM-1) and the mutating **`/bin/mkdir`, `/bin/mv` and `/bin/rm`** (PUB-11). **The derived count is PER SHELL ARM and the two arms differ by construction**: `zstat` is a zsh builtin and forks nothing, so the zsh arm's count omits every `/usr/bin/stat` the bash arm makes, and a single expected number would fail one arm or the other. The harness fails if a count exceeds what the rules derive. A reader walks each chain ONCE — it authenticates each entry once and takes one exit — so a re-walk raises the counted invocations above the derivation and the harness fails, while every protocol variable is UNCHANGED. The oracle is therefore the COUNT and cannot be the resolution. *(Round 108, codex: this row previously mutated a wall-clock ceiling, and BUD-1 no longer states one — the cost is linear in components, nothing bounds a target's depth, and 100 component evaluations measured 520 ms in bash against a 400 ms ceiling, so the ceiling rejected conforming implementations exactly as 50 ms did.)* |
| 129 | **treat ANY UNTYPED (bare UUID) ACE principal as the effective user** | a component carrying an `allow` ACE whose principal is a bare UUID that is NOT the effective user's resolved UUID (P-3a's second probe) and whose rights fall outside ACL-2's seven-right allowlist yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic. Under the mutation it is read as ours and the component ACCEPTS — an identity the system could not resolve treated as proof of ownership. *(Refined with row 169: exactly ONE bare UUID is self.)* |
| 128 | **treat a failed cleanup `rm` as a failure of the publish** | with `bases/` made unwritable AFTER the transient is created, the `rm` fails: the publisher still reports `failed` with EXACTLY ONE diagnostic, and the leftover `.pub.*` transient is inert — no reader enumerates it (TMP-1's prefix is outside the `base.*` glob) and no resolution changes. Under the mutation the publisher emits a second diagnostic or aborts under `errexit` |
| 125 | **roll back ancestors created before a later failure** | with `.claude` creatable and `unleashed-mail` creation failing, the publisher reports `failed` and LEAVES `.claude` in place — ST-3/ST-4 forbid the plugin removing directories, so a rollback deletes paths it has no right to delete. Row 124 covers creation before validating an already-hostile prefix and cannot discriminate failure AFTER a first safe creation |
| 124 | **create a missing store ancestor before authenticating the existing prefix** | with `HOME` a SYMLINK to another tree and `.claude` absent, the publisher creates NOTHING and reports `failed`; under the mutation `mkdir` runs through the symlink and leaves a directory outside the store, which ACL-6 forbids for a PRE-CREATION refusal. Rows 111 and 121 test chain REFUSAL, not the write-before-validation ORDER, and cannot discriminate this |
| 123 | **read an entry with plain `read` instead of `IFS= read -r`** | an entry holding `/tmp/a\b ` (backslash, trailing space — both permitted by TGT-1) authenticates and the store RESOLVES to that target: `OK=1`, `SOURCE=pointer`, `POINTER_STATE=none`, empty stderr; under the mutation plain `read` yields `/tmp/ab`, ENT-3's name↔content check fails, and the store yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic. Measured: plain `read` transforms it in BOTH shells. Row 4 is the multi-line case and cannot discriminate this |
| 119 | **spell a concatenation `out="$out[$c]"` instead of `out="${out}${c}"`** | every family file sources cleanly under zsh; under the mutation zsh aborts with `bad math expression: operand expected at '/'` because `$out[` is an array subscript, while bash yields the literal `X[/]` and passes — so a bash-only cell cannot discriminate it and the oracle is the ZSH arm (FAM-5 clause 0) |
| 118 | **write before the TARGET CHAIN authenticates** | a base value naming an existing directory beneath a `0775` component publishes NOTHING and reports `failed`; under the mutation a durable entry appears that every reader refuses and ST-8 forbids deleting |
| 117 | **revert RD-12 to its symlink-only pre-read guard** | a FIFO named `base.<k>` in an otherwise healthy store yields `stale` with one diagnostic and the process EXITS; under the mutation the reader blocks forever (measured `rc=124`, both shells). This is the READER's obligation and row 116 cannot discriminate it — 116 mutates the publisher's open of the TRANSIENT, and ST-7 rejects an entry-named FIFO independently of what the reader does |
| 133 | **treat a failed `NAME_MAX` probe as an unlimited budget — compare against the raw value without checking `getconf`'s exit status or its numeric shape** | a publish whose `getconf` fails REFUSES: `POINTER_STATE=failed`, one diagnostic naming the length, nothing created — in BOTH shells. Under the mutation the arms DIVERGE: measured, `[ 42 -gt "" ]` is status 2 in bash 3.2.57 (so the `if` takes the ELSE branch and the publisher proceeds to create a name it never budgeted) and status 0 in zsh 5.9 (so it refuses), which is why a single-shell oracle cannot discriminate it and the row asserts BOTH arms. Driven through §4.2a-S's probe seam, since `getconf` is invoked by absolute path (N6-10); measured statuses are 64 bare and 71 on a missing path. PUB-9 E3 states this obligation and nothing mutated it |
| 134 | **invoke the STORE `mkdir` through `PATH` instead of by absolute path** | with a directory earlier in `PATH` supplying a `mkdir` that ignores `-m`, a publish creates `bases/` at the umask default; the oracle is the store-level outcome for the NEXT reader — sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — **and the SAME outcome on a second run**, which distinguishes a DURABLE poisoning from a transient failure, since ST-3 forbids repairing or removing a store in any other state. Unmutated the publisher calls `/bin/mkdir`, the shim is never consulted, the store is `0700` and the reader resolves. Measured: with `-m 700` not applied the components come out `755`, which ST-4 ACCEPTS for ancestors and ST-3 REFUSES for `bases/`. **This row covers ONE of PUB-11's four pinned call sites; rows 136-138 cover the others** |
| 135 | **locate the ACE verb by POSITION (the third field) instead of by token (Darwin)** | a component whose INHERITED `allow` ACE names another principal and carries **any right outside ACL-2's seven-right allowlist** — `chmod +a "group:staff allow add_file,delete,file_inherit,directory_inherit"` on the parent, as an MDM fleet propagates — yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic. Under the mutation the `inherited` token occupies the verb position, no ACE matches and the component is ACCEPTED: the fail-open ACL-2 describes in its own text. **Row 90 cannot discriminate this** — its fixture is a READ-ONLY inherited ACE, which the correct arm and the positional parser both accept. Measured against a positional-parser build: correct REFUSES, mutant ACCEPTS, both shells |
| 136 | **invoke the ANCESTOR `mkdir` through `PATH`** | same shim, but only `${HOME}/.claude` and `${HOME}/.claude/unleashed-mail` are created through it while `bases/` uses `/bin/mkdir`. ST-4 accepts `0755` ancestors, so the store-level outcome is NOT poisoned and the oracle is the ANCESTOR MODE read back: `0700` unmutated, the umask default under the mutation. Row 134 cannot discriminate this — it asserts the store's outcome, which is unchanged here |
| 137 | **invoke the entry `mv` through `PATH`** | a **SYNCHRONISED** shim `mv` — it removes or truncates the EXISTING destination, signals the harness, BLOCKS while the reader observes, then completes — satisfies the command name and breaks PUB-13's atomicity: a reader that has already seen the entry observes it ABSENT or TORN, which ST-7's absence guarantee forbids. **The synchronisation is part of the row, not an implementation detail**: a plain `cp src dest; rm src` replaces the destination's CONTENTS without necessarily removing its directory entry, and a one-line entry can finish before any observer runs, so an unsynchronised shim is reachable but not reliably discriminating. Rows 134 and 136 leave `mv` bare and cannot discriminate this. *(Round 110, codex.)* |
| 138 | **invoke the transient-cleanup `rm` through `PATH`** | a shim `rm` that exits non-zero without removing leaves the transient in the store; the oracle is that a `.pub.*` name is absent after a failed publish under E6, and that a FAILED removal still changes nothing a reader sees — TMP-2 keeps transients outside the `base.*` glob, so the store-level outcome is identical either way and the oracle must be the FILE's presence, not the resolution. **The fixture must keep the store WRITABLE**, so that the unmutated `/bin/rm` genuinely succeeds: ST-7 makes cleanup best-effort, so on a store where removal is impossible the specification leaves the same transient the mutation does, and the row cannot fail. *(Round 110, codex.)* |
| 139 | **find the ACE verb with word splitting — `for f in $ace_line` (Darwin)** | the same inherited or plain `allow` ACE as row 135, **carrying any right outside ACL-2's seven-right allowlist**. **zsh does not split unquoted parameter expansions** (SH_WORD_SPLIT is off by default), so the loop sees ONE field in zsh and every field in bash: MEASURED, bash REFUSES the component and **zsh ACCEPTS it** — a fail-open in the arm whose only job is to refuse, and a publisher and reader on one machine disagreeing by shell alone. The oracle must assert BOTH arms; a bash-only cell reads as a pass. Setting `IFS` does not fix it — zsh still does not split an unquoted expansion — and the portable technique is **P-13's two-layer token peel**, measured to give identical fields and rights in both shells. Same family as row 119's `out="$out[$c]"`, which is array subscripting in zsh |
| 140 | **resolve the ACL principal ONCE PER COMPONENT instead of once per resolution** | BUD-1 derives exactly ONE `/usr/bin/id -un` per resolution (P-3a). Under the mutation the count rises with the number of components while every protocol variable is UNCHANGED, so the oracle is the COUNT and can only be the count. **This row exists to prove the COUNTER IS WIRED to `id -un` specifically**: row 132's extra chain walk raises the `ls -lde` count too, so a harness that counts only the ACL enumerator passes row 132 while counting no `id` at all — which is exactly the defect round 110 fixed in BUD-1's enumeration and nothing proved |
| 141 | **probe `/usr/bin/uname -s` separately for P-2's arm selection and ACL-5's enumerator selection** | ACL-5 derives exactly ONE platform probe per resolution, shared. Under the mutation the count is two, with every protocol variable UNCHANGED. Proves the counter is wired to `uname` and that the shared-probe rule is enforced rather than merely stated |
| 142 | **probe `NAME_MAX` once per created component instead of once per publish** | NM-1 derives exactly ONE `/usr/bin/getconf` per publish. Under the mutation the count rises with the number of ancestors created, with the publish outcome UNCHANGED. Proves the counter is wired to `getconf`, which no other row exercises: rows 133 and 138 test a FAILED probe and command ROUTING, not counting |
| 143 | **name a scratch variable in P-2's BASH arm the same as the chain walk's loop variable** | the two ARMS return DIFFERENT verdicts on ONE identical chain — measured: bash REFUSES and zsh RESOLVES, with every per-component fact (mode, uid, ACL verdict) identical in both. A POSIX shell function has no locals, so the accessor overwrites the walk's state mid-loop; the zsh arm uses the `zstat` builtin, never touches that name, and is unaffected. **The oracle is AE-1's arm equivalence, and a single-shell cell cannot discriminate it** — which is what makes this class expensive: the defect is invisible on one arm and silent on the other |
| 144 | **drop the "exactly ONE field after the verb" check, keeping whichever field comes last** | a component whose enumerator line presents TWO FIELDS after the verb, NEITHER of them reserved (`group:staff allow write list`) yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — the line does not match ACL-2's grammar, so ACL-4 makes the condition unevaluable. Under the mutation the second field silently becomes the rights list, the ACE reads as read-only `list`, and the component is ACCEPTED. **The fixture may NOT use a second `allow` (`allow write allow list`): measured, that lands in the `<perms>` slot where row 148's RESERVED-TOKEN guard refuses it first, so specification and mutant both return 1 and this row CANNOT FAIL.** Found by running the rows as mutation tests rather than reading them — two rounds after the row was written, and by checking WHICH guard fired rather than trusting the summary |
| 145 | ~~restore the empty-element skip in the rights layer~~ **RETIRED round 124 — EQUIVALENT MUTANT.** P-13 rejects an empty, doubled, leading or trailing comma element BEFORE the rights loop is entered, so restoring a skip INSIDE that loop changes nothing: codex ran all four fixtures in both shells and the specification and the mutant both returned 1. N6-9 requires an equivalent mutant to be retired rather than left printing. **My own mutation harness reported this row as unable to fail one round earlier and I attributed it to a defect in the harness** — the harness was right | a component whose ACE carries an EMPTY `<perms>` field yields the store-level refusal above; under the mutation no right is ever tested and the foreign `allow` ACE passes VACUOUSLY. Row 144 cannot discriminate this — it mutates verb LOCATION, not element handling — and the two defects have now occurred in consecutive rounds in the same primitive |
| 146 | **accept an extra field between the principal and the verb** (anything, not only `inherited`) | a line `group:staff weird allow list` yields the store-level refusal; under the mutation the unknown field is ignored and the ACE is evaluated as though well-formed. Proves the grammar is enforced rather than merely stated, on the side ACL-4 governs |
| 147 | **accept more than one `inherited` token before the verb, or `inherited` as field 1** | through §7 step 3f's ENUMERATOR-OUTPUT seam, a component whose ACE line reads `group:staff inherited inherited allow list` yields the store-level outcome — sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — because the line does not match ACL-2's grammar and ACL-4 makes the condition unevaluable. Under the mutation the extra token is absorbed and the ACE is evaluated as well-formed. **That `/bin/ls -lde` does not emit this shape is NOT a reason to accept it**: ACL-4 makes any non-matching line unevaluable rather than ignorable, and an arm that predicts what a healthy enumerator emits is not enforcing a grammar |
| 148 | **accept a RESERVED token in the `<perms>` slot** | through the same seam, a line `group:staff deny allow` yields the store-level refusal above. Under the mutation it parses as verb `deny` with rights `allow`, and ACL-1's ignore-every-`deny` rule then DISCARDS the whole line — so a two-verb line is accepted by being thrown away. Row 144 mutates the SECOND-FIELD check and cannot discriminate this, because here there is only one field after the verb |
| 149 | **strip the ACE index by removing everything through the first `: ` without proving the prefix matched or is decimal** | through §7 step 3f's ENUMERATOR-OUTPUT seam, an answer containing ` 0:group:staff allow list` (no space after the colon) or ` x: group:staff allow list` (non-decimal index) yields the store-level outcome — sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — because ACL-4 classifies the line as MALFORMED and a malformed line poisons the whole answer. Under the mutation both parse as valid ACEs: measured, the first yields `principal=0:group:staff` and the second `principal=group:staff`, and each is then evaluated as though well-formed. **Rows 144-148 constrain only POST-PREFIX slots and none can discriminate this** — the prefix is stripped before they see anything |
| 150 | **skip ANY non-space line instead of only the first** | through the enumerator-output seam, an answer whose lines are the real stat line, one well-formed ACE, and then a third line that begins with no space (`garbage-after-stat`) yields the store-level outcome — sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — because ACL-4 permits a non-space line ONLY as line 1 and any later one is MALFORMED, which poisons the whole answer. Under the mutation the third line is skipped as though it were another stat line and the component is ACCEPTED with an answer that was never fully parsed. **Rows 144-149 all mutate WITHIN a line and every one of them stays green under this defect**; this is the only row that mutates the ANSWER-level classification. Measured, both shells: line 1 skip, line 2 ACE, line 3 MALFORMED |
| 151 | **accept an answer that never produced a stat line** | through the enumerator-output seam, an answer consisting SOLELY of one well-formed read-only ACE — no stat line — yields the store-level outcome: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic, because `STAT (BLANK | ACE)*` cannot accept until the mandatory initial stat line has been seen. Under the mutation the answer parses and an otherwise-valid single-entry store RESOLVES with `OK=1` — the strongest form of this fail-open, since the store is healthy and only the ACL evidence is missing. **Rows 144-150 all constrain lines; this row and 152 constrain the ANSWER**, and every one of 144-150 stays green under this defect. The same fixture with the empty answer and with a blank first line must also refuse |
| 152 | ~~accept a SECOND stat line~~ **RETIRED round 124 — SUBSUMED BY ROW 150.** Both change the same state-machine arc, `BODY x later-non-space`, from reject to skip-as-stat, and each mutant fails BOTH fixtures, so N6-4's one-mutation-one-row rule forbids keeping both. Row 151 (no initial stat line) mutates the INIT arc and remains independent | an answer of two non-space lines followed by a well-formed ACE yields the store-level refusal above; under the mutation the second stat line is skipped as though the machine were still in INIT and the answer parses. Row 150 mutates the line-level skip and row 151 the missing initial state; neither covers a REPEATED one |
| 153 | **write the value through a SECOND open of the transient's pathname — `set -C; : > "$tmp"` and then `printf … > "$tmp"`, instead of through the descriptor the exclusive create returned** | a fixture that substitutes a SYMLINK to a victim file at the transient's name the instant an EMPTY regular transient exists — a `DEBUG` trap on the publishing shell, armed with `set -T` in bash so functions and subshells inherit it; zsh's fires inside the create-and-write subshell — the publisher writes through descriptor 9, the victim is UNTOUCHED, and the P-4 mode readback of the substituted symlink refuses at E6 (`failed`, the symlink removed by the ST-7 cleanup, no entry). Under the mutation the second open FOLLOWS the symlink and the victim holds the base value. Measured, both shells. The oracle is the VICTIM's content, not the publish state — both builds report `failed`. Nothing in the fixture is platform-specific. *(PR #67, codex pass 6: the previous P-4 prescribed exactly the two-open shape, so no row could have caught it — the rule was the defect.)* |
| 154 | **treat a REFUSED exclusive create whose name now EXISTS as E6 instead of as a lost race** | a `DEBUG` trap on the publishing shell (`set -T` in bash) that PLANTS an empty `0600` regular file at `$_UNLEASHED_TRANSIENT` the instant the publisher is inside the write for that name and the name is still absent — keyed on `_wt_p` equalling `_UNLEASHED_TRANSIENT`, which is true only AFTER TMP-1's presence test has passed and BEFORE the `9>` open — so the open is refused and the name exists: the specification treats it as a lost race, consumes the attempt, and the trap plants again on the next name, so after TMP-1's three attempts the publisher takes **E5** — `failed`, the one diagnostic naming the transient-name exhaustion — with THREE planted files present. Under the mutation the first refusal is reported as **E6** — the diagnostic names the 0600 write — after ONE planted file. The oracle is the diagnostic's text and the planted-file count; both builds report `failed`. Measured, both shells. *(Adversarial verification of PR #67 pass 6: the refined mapping had no row that could fail on either of its two branches.)* |
| 155 | **treat a REFUSED exclusive create whose name is ABSENT as a lost race instead of as E6** | the same trap condition, but the trap makes the STORE unwritable (`/bin/chmod 500`) instead of planting a file, so the `9>` open is refused with `EACCES` and the name stays absent: the specification takes **E6** on the FIRST attempt — `failed`, the diagnostic naming the 0600 write, no transient anywhere. Under the mutation the refusal spends all three attempts and surfaces as **E5**, whose diagnostic names the wrong exit. The oracle is the diagnostic's text; the harness restores the store's mode afterwards. Measured, both shells. *(Same source as row 154; this is PUB-9 E6's "the temporary's creation … fails for any reason" clause, which E5 must not absorb.)* |
| 156 | **skip resolution on an inherited protocol variable instead of process identity** | `_UNLEASHED_BASE_OK=1` exported into a CHILD shell that sources a family file with `CLAUDE_PLUGIN_DATA` unset and no store: the specification resolves afresh (`_UNLEASHED_BASE_PID` ≠ `$$`) — `OK=0`, the sentinel, `marker_dir` beneath the sentinel, ONE diagnostic; under the mutation (`[ -z "${_UNLEASHED_BASE_OK:-}" ]` as the guard) resolution is skipped, `_UNLEASHED_BASE_RESOLVED` is unset, and `marker_dir` prints `/.state` — the ROOT path. All five resolver copies, both shells. *(PR #67, codex pass 7 — reproduced.)* |
| 157 | **honour an inherited machinery-loaded flag** | `_UNLEASHED_STATE_LOADED=1 _UNLEASHED_STATE_RC=0` exported into a child that sources `paths.sh` with the variable unset: the specification loads the four libraries (keyed on `command -v` of their entry functions) and resolves; under the mutation (a flag-keyed loader) the reader branch calls an undefined `_unleashed_read_store` — `command not found` on stderr and every protocol variable UNSET, so a `set -u` consumer aborts. Both shells. |
| 158 | **guard the `paths.sh` definition block on an inheritable flag** | `_UNLEASHED_PATHS_SH_LOADED=1` exported into a child that sources `paths.sh`: the specification (whose definitions are UNCONDITIONAL) defines its functions and resolves (`unleashed_plugin_base` prints the base or the sentinel); under the mutation — a flag guard wrapped around the definition block — the file defines NOTHING and `unleashed_plugin_base` is `command not found`. Both shells. *(Reshaped in pass 12: the mutation ADDS a guard where the specification has none.)* |
| 159 | **capture the transient write's status with a BARE call — `cmd; _pb_wrc=$?` — instead of an errexit-safe `cmd && … \|\| …=$?`** | the family sourced under `set -eu` with the store made unwritable after E4 (the create is refused, E6): the specification reports `failed` with its one diagnostic and the sourcing shell REACHES its next statement; under the mutation the shell EXITS at the bare call with the write's own non-zero status (`1` — E6 under `RLIMIT_FSIZE`; the fixture forces the write, not the create, to fail), before the diagnostic, leaving the transient orphaned. Both shells; the same fixture runs the create-and-write subshell's own `case` capture. The plan's "each file must source cleanly under `set -euo pipefail`" was stated at §4.3 and never had a row on the PUBLISH path. *(PR #67, codex pass 7 — reproduced: `set -e; . paths.sh` exited 2 with no diagnostic.)* |
| 160 | **read the entry through a SECOND open of its pathname — `read < "$p"` — instead of through the descriptor ENT-2b validated** | a `DEBUG` trap (`set -T` in bash) substitutes the entry the instant ENT-1 has validated it and before it is opened — a large regular file whose FIRST LINE is the valid target followed by 200 000 bytes (`0600`), a symlink to a foreign file, a vanished entry, and in zsh a FIFO: the specification refuses each as a failing entry (`stale`, one sanitised diagnostic, no path on stderr) and returns promptly, having read NOTHING of the large file (`${#_ae_line}` is 0); under the mutation the large file is READ and the resolver RESOLVES to it (`1 pointer none`) — a file ENT-1 never validated — and, in zsh, the FIFO BLOCKS the resolver. **The literal 200 000-byte file with no valid first line does NOT discriminate at the outcome level** (both builds end `stale`, the mutant after consuming it): the valid first line is what makes the row able to fail. bash's FIFO case is P-5's stated residual and is not run. Both shells for the other three. **Consequences for older rows, stated:** row 117's zsh half (the type guard keeps a FIFO from HANGING) is subsumed — under ENT-2b a FIFO cannot hang zsh with or without the guard, so its hang oracle runs in bash only; row 123's zsh half (`IFS= read -r` vs plain `read`) has no target — the zsh arm reads bytes with `sysread`, which has no IFS or backslash processing — so its discrimination is bash-only and zsh asserts the behaviour. |
| 161 | **omit `base_resolution` from log records** | `log_append` called with each of the four producers' record shapes plus `{}` and `{  }` under `host-env` and under `pointer` (variable unset, one authenticating entry): every persisted line parses as JSON and carries `"base_resolution"` naming the resolution that ran; a line that already carries the field is written unchanged; a non-object line is written unchanged. Under the mutation (the writer's stamp removed) the four producer shapes persist WITHOUT the field, so a `pointer` record is indistinguishable from a `host-env` one. Both shells. *(PR #67, codex pass 7.)* |
| 162 | **declare `path` or `status` as a local, or assign `path=`, in a family writer (zsh special parameters)** | under **zsh** with the variable set: `marker_write lint fail; marker_status lint` prints `fail`, `log_append` persists its line, `context_review_round_bind` prints a round and `context_review_round_lookup` reads it back, and `PATH` is intact afterwards (`command -v ls`); under the mutation — each writer's variables renamed back to `path`/`status` CONSISTENTLY throughout the function, so that bash still runs it correctly — zsh reports `read-only variable: status` and abandons the script for `marker_write`, `local path` empties `PATH` for `log_append` so `mkdir` is not found and NOTHING is written, and `context_review_round_bind`'s `path` leaves no binding to look up. bash is unaffected by the mutation, which is why every writer test until now passed. (Mutating only the `local` line is NOT the mutant: it leaves the renamed uses dangling and breaks bash too, contradicting this row's oracle.) *(Found while executing row 161's fixture under zsh: `log_append` had been a silent no-op in zsh since it was written; the same defect sat in `marker_write`, `marker_field`, `marker_mtime`, `context_review_round_bind`, `context_review_round_lookup`; and `marker_write`'s unquoted sentinel glob aborted under zsh's `nomatch` while `marker_field` read captures from `BASH_REMATCH`, which zsh does not fill.)* |
| 163 | **decide "the store does not exist" with `[ ! -e ] && [ ! -L ]` on the full path instead of RD-8's walk** | the store exists with one authenticating entry, and `${HOME}/.claude` is `chmod 600` (exists, not searchable): the specification takes rule −1 — `stale`, one diagnostic, `OK=0` — because the store is HIDDEN, not absent; under the mutation the reader reports `none` ("does not exist") and stays silent for SessionStart. A genuinely absent store (`unleashed-mail/` missing under a searchable `.claude`) reports `none` in BOTH builds. Both shells. *(PR #67, codex pass 8.)* |
| 164 | **test the existing `base.<key>` with `[ ! -f ]` alone, letting `-f` follow a symlink** | `base.<key>` is a SYMLINK to a regular `0600` file elsewhere holding the publisher's own base: the specification refuses at ST-7 — `failed`, one diagnostic, the symlink UNTOUCHED, no transient left; under the mutation the publisher `mv -f`s its transient over the link and reports `created`, and `base.<key>` is now a regular file. Both shells. *(PR #67, codex pass 8.)* |
| 165 | **evaluate the SessionStart notice only after the hook's source filter (`compact\|resume\|startup`)** | a store in `conflict` (two entries), the hook run with `{"source":"clear"}` and with `{"source":"weird"}` and with `UNLEASHED_COMPACT_RESTORE=off`: the specification emits the notice (`base store is conflict`) on every one; under the mutation (the source filter's branch back to a bare `exit 0`) `clear` and `weird` are silent. A `created` store stays silent on `clear` in both builds. *(PR #67, codex pass 9.)* |
| 166 | **skip resolution on pid + marker function alone, without the readonly-attribute instance check** | a wrapper shell under `set -a` sources a family file with `CLAUDE_PLUGIN_DATA=<a>`, then sets `<b>` and `exec`s a hook shell that sources the same file: the specification resolves afresh — the hook's base is `<b>` — in both shells (bash carries the functions too under `set -a`); under the mutation (the instance check removed) the hook keeps `<a>`. A subshell and a fork+exec child are unaffected in both builds. *(PR #67, codex pass 11 — reproduced.)* |
| 167 | **guard the `paths.sh` definition block on ONE function** | bash: `export -f unleashed_resolve_base` in a parent, then a child sources `paths.sh`: the specification (unconditional definitions) defines the whole API (`unleashed_plugin_base` prints the sentinel or the base, `unleashed_base_ok` is defined); under the mutation — a one-function guard wrapped around the block — it is skipped and `unleashed_plugin_base` is `command not found`. bash only (zsh cannot export functions). *(PR #67, codex pass 11; reshaped in pass 12 — the mutation ADDS the guard.)* |
| 168 | **validate type, uid and size on the opened entry but not its identity (inode)** | a `DEBUG` trap substitutes a `0644` COPY of the valid entry (same content, same size, same owner) between ENT-1's stat and the open: the specification refuses (`stale`) — the opened inode is not the validated one; under the mutation (the inode clause removed) the copy authenticates and the store RESOLVES to a world-readable entry. Both shells. Row 160's substitutions remain refused in both builds (their size or type differs). *(PR #67, codex pass 11.)* |
| 169 | **treat a bare-UUID ACE principal EQUAL to the effective user's resolved UUID as foreign** | the enumerator seam presents ` 0: <UUID> allow write` where `<UUID>` is `/usr/bin/dsmemberutil getuuid -U "$(/usr/bin/id -un)"` on the running host (a mutating right, so a FOREIGN reading refuses): the specification treats it as SELF and the component AUTHENTICATES; under the mutation (the UUID-self clause removed — every bare UUID foreign, the pre-audit behaviour) it REFUSES. A DIFFERENT UUID with the same right refuses in both builds (row 129). Both shells. *(External audit of PR #67, finding 1.)* |
| 170 | **guard the `paths.sh` definition block on the COMPLETE resolver API being present** | bash: a parent under `set -a` sources `paths.sh` and then REDEFINES `unleashed_resolve_base` and `unleashed_plugin_base` to answer `/attacker` (all six names now exported), then a child sources `paths.sh` (and, separately, `marker.sh`) with a genuine base in its environment: the specification prints the genuine base — the child's definitions are its own, the imported ones replaced; under the mutation (the six-function guard restored) the block is skipped, the eager call runs the INHERITED resolver, and the child prints `/attacker`. bash only. *(PR #67, codex pass 12 — reproduced.)* |
| 171 | **at E4 step (ii), treat a component that is present as already authenticated, without checking whether (i) walked it** | `.claude` absent at (i); a `DEBUG` trap plants it as a SYMLINK to an outside directory the instant (i) has completed and before (ii) reaches it: the specification refuses at E4 with NOTHING created outside the store; under the mutation the next component (`unleashed-mail`) is created THROUGH the link in the outside directory and only (iii) reports `failed`. A normal creation succeeds in both builds. Both shells. *(PR #67, codex pass 13 — reproduced.)* |
| 172 | **load the state machinery by "its four entry functions are present" first, sourcing the library files only when a name is missing** | bash: a parent under `set -a` sources `paths.sh`, redefines `_unleashed_read_store` to set `_UNLEASHED_BASE_RESOLVED=/attacker` and `_UNLEASHED_BASE_OK=1`, then `exec`s a child with `CLAUDE_PLUGIN_DATA` unset that sources `paths.sh` and calls `unleashed_plugin_base` (and, separately, `marker.sh` and `unleashed_base_ok`): the specification RE-SOURCES the four libraries from beside the resolver and the child prints the sentinel (or the store's base) with `unleashed_base_ok` false; under the mutation the exported names satisfy the presence check, all four libraries are skipped, the imported reader is trusted and the child prints `/attacker`. bash only. *(PR #67, codex pass 14 — reproduced.)* |
| 173 | **stamp the instance with a bare `readonly _UNLEASHED_BASE_INSTANCE=1` at every resolution** | (i) both shells: `set -e; . paths.sh` with base A, then `. agent-env-bridge.sh B <root>`, which re-resolves: the specification's sourcing shell survives holding base B; under the mutation bash treats the repeated readonly assignment as a fatal error and the shell EXITS. (ii) zsh: `typeset -p _UNLEASHED_BASE_INSTANCE` after `. paths.sh` alone: the specification shows `-r` — the stamp is GLOBAL (`typeset -g -r`); under the mutation the bare `readonly` inside `unleashed_resolve_base` declared a function-local that vanished at return: `no such variable`. (iii) bash: a `set -a` wrapper sources `paths.sh` and `exec`s a child that sources it again: the child sees `declare -x` (inherited value, no attribute) before and `declare -r` after its own resolution, in both builds. *(PR #67, codex pass 14 — reproduced.)* |
| 174 | **derive the library directory with `dirname`** | bash: a parent under `set -a` exports the four machinery names with a tampered `_unleashed_read_store`, then `exec`s a child with `PATH=/bin` (so `/usr/bin/dirname` is not found) that sources a resolver copy sitting beside its four libraries: the specification derives the directory by parameter expansion and builtin `cd`/`pwd`, RE-SOURCES the libraries and resolves the sentinel (or the store's base); under the mutation `dirname` is not found, the directory becomes the caller's cwd, the libraries are "not readable", the presence fallback trusts the import and the child prints `/attacker`. All five copies; a normal PATH resolves honestly in both builds. *(PR #67, codex sweep after pass 14 — reproduced.)* |
| 175 | **discard an inherited stamp with a bare `unset -f`** | zsh under `set -e` (and `setopt err_return`), with `_UNLEASHED_BASE_INSTANCE=1` carried in the environment and the marker function absent: the specification's `|| :` lets every copy source to completion and resolve; under the mutation `unset -f` returns 1 for the undefined function and the sourcing shell dies with nothing established. bash is unaffected (its `unset -f` returns 0) and must be shown so. *(PR #67, codex sweep after pass 14 — reproduced.)* |
| 176 | **test the readonly attribute against the WHOLE `declare -p` line** | `_UNLEASHED_BASE_INSTANCE='r _UNLEASHED_BASE_INSTANCE='` in the environment of a child that sources a resolver copy with a genuine `CLAUDE_PLUGIN_DATA`: the specification strips everything from the first ` _UNLEASHED_BASE_INSTANCE` and reads only the flag letters, finds no `r`, discards the inherited value and re-resolves; under the mutation the attacker-supplied VALUE furnishes both the `r` and the name, the line matches and the inherited resolution is trusted. The control — a genuine in-process stamp honoured across three copies in one shell, `-r` present in both shells — must hold in both builds. *(PR #67, codex sweep after pass 14 — reproduced.)* |
| 177 | **take the effective uid from `${EUID:-$(/usr/bin/id -u)}`** | bash 3.2 with `EUID=4242` in the environment (measured: bash IMPORTS it, zsh does not), a healthy euid-owned store and a publish: the specification probes `/usr/bin/id -u` through its own seam and publishes and reads normally; under the mutation every ownership clause compares against 4242 — the entry is `stale`, the publish `failed`, nothing is read or written. A failing seam must still refuse (fail-closed) in both builds. *(PR #67, codex sweep after pass 14 — reproduced.)* |

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
temporary root, so
the pair is runnable by an ordinary uid.

**Round 31c (kimi): "the same seam rows 27-28 already use" named a mechanism that does not exist.**
Grepped: zero hits for any injection seam anywhere in this plan. Rows 27-28 need none — the real `/` and
`/Users` are genuinely root-owned, so those cases run against the live filesystem — while rows 33-34 and
the new off-`${HOME}` cases DO need root-owned components an unprivileged test cannot create. **So the
seam is specified here rather than invoked:** the chain-walk predicate takes its per-component
ownership/mode facts from a single accessor, and the harness substitutes a fixture table for that
accessor. One accessor, used by production and by the harness, so a test cannot pass against a predicate
production does not run. *(An appeal to a mechanism that does not exist is the same class as the four
fabricated citations — specific enough to read as verified.)* An unrunnable mutant is a mutant that proves nothing, which is
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
value performs **no write** (asserted by mtime); a `0644` REGULAR entry with matching content **is**
republished as a conforming one; a second install id with a different base leaves **two entries**, which
every reader resolves as a conflict — no publisher marks anything for another to find; step 2 →
variable unset, exactly one authenticating entry → base is that entry's target,
`_UNLEASHED_BASE_SOURCE=pointer`, and **no second store is created** (this fails under D′, which resolves to the sentinel, and under the pre-D′
fallback, which resolves to `$HOME`); each authentication clause refused independently, including a
**conflicted** pointer; step 3 → `HOME=""` → sentinel, `OK=0`, **exactly one** diagnostic, **no
`${HOME}`-rooted open attempted at all**, and the D′ no-persistence envelope (`N2`, `N4`) holds in full;
persisted records carry `base_resolution` matching the resolution that actually ran — the markers, round bindings and PreCompact snapshot stamp it where they build the record, and LOG records are stamped by `log_append` itself, the one writer every producer goes through, so a producer that omits it cannot ship a record without it (PR #67, codex pass 7: four producers had, mutant row 161); and the SessionStart
notice fires on `conflict`/`stale`/`failed` and stays silent on `created`/`current`/`none` — the same partition as the declaration above, and derived from the same exit-path list rather than restated.

**Arm equivalence, across all five shell files** (round 20, kimi #8): the full pointer matrix
(absent / valid / malformed / unreadable / conflicted × publish / refuse) runs with `paths.sh` **present
and absent**, asserting identical `_UNLEASHED_BASE_RESOLVED`, `_UNLEASHED_BASE_OK`, `_UNLEASHED_BASE_SOURCE`
**and `_UNLEASHED_POINTER_STATE`** from every file. *(Round 34: the oracle listed three while the rule
and row 73 require four. `git log -L` dates this line to round 21 — untouched for eleven rounds, and
specifically NOT updated in round 32 when I recorded fixing exactly this family one section away. The
round-32 fix was itself half.)* Each file must also source cleanly under `set -euo pipefail`
in **both bash and zsh** in every cell.

**Stderr is asserted per cell, not globally** (round 20, kimi #7): `stderr == ""` is required only in
**resolved** cells **whose publish side effect also succeeded**. *(Round 35: a resolved cell CAN emit a
diagnostic — the `NAME_MAX` over-budget path resolves via the variable, reports `failed`, and emits one
line naming the length — so the unqualified form made the oracle unsatisfiable in exactly the case the
diagnostic exists for. Resolution and publication are separate outcomes and the oracle must say which
it constrains.)* Step 3 mandates **exactly one** diagnostic and step-1-conflict mandates **NONE** — a publisher that observes `conflict` has already resolved and is silent (PUB-11), while a READER that refuses on `conflict` emits one line, so the same word carries opposite oracles on the two paths (AE-2). A blanket empty-stderr
assertion would contradict them — the draft's N6 clause did exactly that.

### Consumers whose behaviour changes, stated rather than discovered

* **`scripts/pre-commit-checks.sh`** — under step 2 its marker writes become **visible to the gate** with
  no export, so the §7 row's unresolved-base conditional stops firing. Its `:14-18` MAJ-6 comment is
  falsified in both directions (it says marker.sh *"falls back to ~/.claude/unleashed-mail"*, which D′
  already made false, and *"To wire them up, export CLAUDE_PLUGIN_DATA in your git-hook env"*, which
  step 2 makes unnecessary). **Amend that comment in the same change** (round 20, kimi #11).
* **`scripts/sessionstart-restore.sh`** — gains the one-line notice above; §7's row `:2811` amended.

> **ROUND 56 — THIS SECTION IS THE FIX FOR THE PROPAGATION STALL, AND IT IS AUTHORITATIVE.**
> Twenty-five gate rounds failed on one pattern: a rule stated in three or four places, a fix landing in
> one, the siblings left asserting the old contract. Fourteen half-a-family instances, four of them in
> the round that fixed the previous one. **Where any other text in this document conflicts with §4.2a-S,
> §4.2a-S governs and the other text is explanatory.** A correction edits §4.2a-S first; prose elsewhere
> may only explain. That converts a contradiction from a defect into a resolved question of precedence.
>
> **Provenance.** Derived by extracting every rule of §4.2a with its restatement sites (94 rules over 957
> sites), then merging duplicates (102 rules, 91 merges, every drop justified), then verifying three ways:
> nothing lost, nothing contradictory, everything codeable. **The verification mattered** — the first
> extraction was NOT canonical (13 rules under multiple ids, three pairs with opposite verdicts, and one
> that would have REGRESSED the round-36 dangling-symlink fix while marking itself clean).
>
> **Five contradictions were resolved before writing, each on the side the plan settles:** the publisher's
> own-entry ACL exemption applies on EVERY authentication of that entry, not the write decision only (the
> narrow reading is CI-red); AUTH-1 carries that carve-out as clause (h), because AUTH-1 is where an
> implementer reads the clause list; rule −1 references ACL-1..ACL-5 rather than restating a
> platform-independent gloss that disagrees with ACL-3 on Linux; the bridge reports `none` on the
> RESOLVED path only, since arm equivalence requires identical states in every read cell; and the
> `SessionStart` notice keys on the enum, never on a hook's own `_UNLEASHED_BASE_OK`.

## 4.2a-S — THE NORMATIVE SPECIFICATION (authoritative)

This section is the authoritative statement of the §4.2a contract. Every rule below is stated here exactly once. Where any other text in this document — prose, a risk row, a summary, a code comment quoted into the document, a mutant oracle, or an implementation step — conflicts with a rule in this section, this section governs and the other text is explanatory only. A correction to the contract is made by editing THIS section; prose elsewhere may only explain what this section already says, and may never state a rule this section does not state, nor restate one in different terms.

### Store

**ST-1 — The store and its contents.** There is exactly one store: `${HOME}/.claude/unleashed-mail/bases/`. It is flat, and the plugin writes nothing into it but entries and transients: one durable entry per publisher, named `base.<key>`, where `<key>` is the key encoder's output over the bytes of the absolute base value that entry holds, plus a publisher's own transient, which that publisher creates and renames onto its own entry. There is no singleton pointer file. **That is a constraint on what the plugin WRITES, not an assumed property of the directory it finds.** A path in the store that the glob `base.*` does not match — a junk file, a subdirectory, another tool's leftover — is IGNORED: RD-9 never enumerates it, nothing authenticates it, and its presence is not a refusal. Refusing globally on it would let one stray file deny the capability, and the store is 0700 and euid-owned, so whatever is in it was put there by this uid. A path the glob DOES match is an entry and is authenticated like any other, so a directory or a symlink named `base.<anything>` is a FAILING entry and refuses under rule 1 — NOT rule 2, which is the CONFLICT exit and is reachable only when two or more entries AUTHENTICATE, so a failing entry can never arrive there; removing it is the operator `rm` of ST-8. No `${HOME}`-rooted store path is composed, read, or written unless `_UNLEASHED_HOME_OK` is true (`HOME` non-empty and beginning with `/`); `_UNLEASHED_HOME_OK` gates the store path only and has no bearing on whether `CLAUDE_PLUGIN_DATA` resolves — a shell with a non-empty `CLAUDE_PLUGIN_DATA` resolves it whatever `HOME` is.

**ST-2 — Creating the store.** The publisher creates the store with a single `mkdir -m 700 "${HOME}/.claude/unleashed-mail/bases"`. `-p` may not be used, and `mkdir` followed by `chmod` may not be used. `mkdir -m 700` does not create parents, so before that call the publisher creates each missing ancestor of the store, in order — `${HOME}/.claude`, then `${HOME}/.claude/unleashed-mail` — at mode 0700 when it is this publisher that creates it. An ancestor that already exists is used as it stands: it is never re-created, never chmod'ed, and is accepted whenever it satisfies the ancestor requirement of ST-4. **"Already exists" includes exists BY THE TIME THE `mkdir` RAN: a `mkdir` that fails because the component now exists is NOT a failure to create it**, and the publisher authenticates it exactly as it would a pre-existing one. Any other `mkdir` failure is PUB-9's E4. Measured: `mkdir -m 700 d` on an existing `d` exits 1 with `File exists` in both shells, and the exit status ALONE cannot tell the two cases apart — the re-test is what distinguishes them. *(Round 106: TMP-1 handles two publishers racing on the transient and PUB-13 handles two racing on the entry; nothing handled two racing on the ANCESTOR, which is the one creation that happens before either. Both readings conformed and they differ observably — one publishes, the other reports `failed` — and the race is likeliest on FIRST USE after install, when the components are missing and the resolver runs at source time in every shell that loads a family file.)*

**ST-3 — Accepting or refusing the store.** `bases/` is acceptable only if it is a directory, is not a symbolic link, is owned by the effective uid, is exactly mode 0700, and satisfies the ACL clauses that apply to every component of an authentication chain. A `bases/` in any other state is REFUSED: it is never chmod'ed, never repaired, never deleted, and no file is written into it. A reader evaluates this before it examines any entry, and evaluates it even when the store is empty; on refusal it sets `_UNLEASHED_BASE_RESOLVED=/dev/null/unresolved-plugin-base`, `_UNLEASHED_BASE_OK=0`, `_UNLEASHED_BASE_SOURCE=unresolved`, `_UNLEASHED_POINTER_STATE=stale`, and emits exactly one diagnostic on stderr. A `bases/` that does not exist at all is NOT a refusal: the reader treats the store as holding no entries and sets `_UNLEASHED_BASE_RESOLVED=/dev/null/unresolved-plugin-base`, `_UNLEASHED_BASE_OK=0`, `_UNLEASHED_BASE_SOURCE=unresolved`, `_UNLEASHED_POINTER_STATE=none`, with one diagnostic on stderr.

**ST-4 — The store's ancestors.** Every ancestor of the store — **every component of PCH-1's walk from `/` down to `bases/`, which includes `/`, `/Users` (or the platform equivalent), `${HOME}`, `${HOME}/.claude` and `${HOME}/.claude/unleashed-mail`** — must exist, be neither group- nor world-writable, not be a symbolic link, satisfy the ACL clauses, and be owned by the effective uid AT OR BELOW the trust anchor ANCHOR-1 defines (above it, system ownership is what ANCHOR-1 requires). **The list previously began at `${HOME}`**, which silently excluded every component above it from the ACL clauses while AUTH-1 and PCH-1 required them — see the correction note in PUB-9 E4 for the durable poison that produced. Exact mode 0700 is required of `bases/` alone and is never required of an ancestor: mode 0755 satisfies the ancestor requirement. Entries are never written directly into `${HOME}/.claude/unleashed-mail`; every entry lives in `bases/`, one level below it.

**ST-5 — The entry file on disk.** An entry is a regular file — never a symbolic link — named `base.<key>` in `bases/`, owned by the effective uid, at mode exactly 0600, whose entire content is the absolute base path it holds followed by exactly one `\n` and no other byte. The publisher creates the transient it will rename at mode 0600 in the SAME open through which it writes it (P-4); the rename preserves the transient's mode, so a transient created by a bare redirect under the prevailing `umask` would leave the entry at 0644 or 0664.

**ST-6 — What one publisher may write.** A publisher may write to AT MOST two paths in the store, and on the no-write `current` path it writes to neither — these are the only paths it MAY touch, not paths it always touches (PUB-4, PUB-7, and PUB-9's E0-E3, which write nothing at all): its own entry `base.<key>` for the base value this process holds, and its own transient. It never creates, modifies, renames, or deletes any other entry, any other publisher's transient, or any other file; nothing else is ever written into the store. A publisher records nothing on another publisher's behalf: conflict is derived by each reader from the store's contents at resolution time and is never written into the store.

**ST-7 — Atomic publication.** **Precondition, measured: if anything is PRESENT at `base.<key>` and it is not a regular non-symlink file, the publisher does not attempt repair — it removes its transient on a BEST-EFFORT basis, writes nothing, and reports `failed`. The symlink test is INDEPENDENT of the type test — `[ -L ]` first, then `[ -e ] && [ ! -f ]` — because `-f` FOLLOWS a link: a `base.<key>` symlink to a regular file passed a `[ ! -f ]`-only guard, and the publisher `mv -f`'d its transient over the link and reported `created`, the silent repair this precondition forbids *(PR #67, codex pass 8 — reproduced, both shells; mutant row 164)*. **The removal is not a guarantee and may not be specified as one:** if same-uid interference has removed write permission on `bases/` since the transient was created, the `rm` fails, and that changes nothing — the state is still `failed` with one diagnostic, and the leftover is INERT by construction, since TMP-1's `.pub.` prefix places it outside the `base.*` glob so no reader enumerates it and no resolution changes. ST-8 already says nothing in the store is reaped automatically. *(Round 98, codex: ST-7 and PUB-9 required removal while PUB-11 admitted the `rm` can fail and required silence afterwards — a guarantee no implementation could keep.)* PRESENCE is the two-part test `[ -L "$p" ] || [ -e "$p" ]`, never `[ -e ]` alone.** `[ -e ]` is FALSE for a DANGLING symlink, so the one-part form does not fire on one, and `mv -f` then silently REPLACES it — measured: exit 0, the link gone, a conforming entry in its place. That is the shape ST-7 exists to refuse, repaired by accident. RD-4 already forbids the one-part test **by name** on the reader side, for this exact reason; the publisher was left using it, so the two sides disagreed about whether a dangling symlink is even there. `mv -f` onto a DIRECTORY moves the transient *inside* it (executed: the transient appeared as `base.KEY/tmpfile`), and onto a symlink-to-directory Darwin `mv` can follow the link and write outside the store; Darwin `/bin/mv` has no GNU `-T` (executed: `illegal option -- T`). Such a shape arises only from same-uid interference or a crash, so refusal is correct and recovery is an operator `rm` — the same disposition as a stale entry. A publish writes the transient in the SAME directory as the entry and then renames it onto `base.<key>` with `mv -f`. The publish's MUTATING commands — the `mkdir`s and the `mv` — have both stdout and stderr redirected to `/dev/null`; their exit statuses are still examined, and the write decision is taken from them. **PUB-11 states the routing rule in full, including what is exempt from it; this clause does not restate it.** Two publishers holding the same base value converge on one entry name and require no serialisation: the bytes are identical and the rename is atomic, so either order leaves the same content, and no reader that has ALREADY SEEN the entry observes it torn or absent as a result of any publication. **The guarantee is scoped to reads after the first successful rename, and cannot be stronger:** before a first publication completes the store holds only `.pub.*` transients, which readers ignore by construction, so a reader legitimately counts zero entries and takes rule 4 (`none`). An atomic rename prevents torn content and preserves an existing destination while replacing it; it cannot make an entry that has never existed continuously present.

**ST-8 — Nothing is reaped automatically.** **One exception, stated first because ST-7 depends on it: a publisher may remove its OWN transient — the file it created in this same process and has not yet renamed.** That is not reaping: the file is this process's own uncommitted scratch and lies outside the `base.*` glob. **The removal is BEST-EFFORT, exactly as ST-7 states it** — this rule permits the attempt and does not guarantee its success, and an `rm` that fails leaves an inert transient no reader enumerates. Nothing ELSE in the store is ever deleted by the plugin: not an entry left behind by a removed install, not a transient orphaned by a killed publisher, and not on any age, mtime, count, or other heuristic. Removing an obsolete entry is a human `rm`, and the operator finds the entry by listing the store themselves, which is what the conflict diagnostic instructs them to do.

**ST-9 — Quarantine preserves the store.** The quarantine moves the orphaned FILES out of `${HOME}/.claude/unleashed-mail` into `${HOME}/.claude/unleashed-mail.orphaned-2617/`, preserving an inventory and checksums, and quarantines the one `-inline` residue separately with its own inventory. It runs after the resolver change lands. It must not move, remove, re-create, or change the mode of `${HOME}/.claude/unleashed-mail` or of `bases/`: after the sweep every entry under `bases/` is byte-identical to what it was before, and the set of entries is unchanged.

**TMP-1 — The transient's name.** A publisher's transient is named `.pub.<pid>.<uniq>.<key>` in `bases/`, where `<key>` is the same key as the entry it will become. `<uniq>` makes the name unique among all concurrent publishers, including two subshells of one process: `$$` alone is not sufficient, because concurrent subshells inherit the same `$$` in both bash and zsh. `<uniq>` is derived without forking a process and without `$RANDOM` in POSIX `sh` — but this family targets bash and zsh, **both of which provide `$RANDOM`** (measured, §4.2a-P P-6), so `<uniq>` IS `$RANDOM`: decimal, at most five digits, which is the fixed maximum width that makes the name-length budget of NM-1 computable. The transient is created by TESTING PRESENCE FIRST — `[ -L "$p" ] || [ -e "$p" ]` — and then creating under `set -C`, which fails if a file of that name already exists. **The two steps are both required and neither is sufficient**: `set -C` alone BLOCKS on a FIFO rather than failing (P-5, measured), and the presence test alone loses the race against a concurrent create. Their composition still leaves the window P-5 states — absent at the test, a FIFO before the redirect — which no POSIX shell redirect can close, and which is therefore an accepted limit of the same-uid model rather than a requirement this rule may state and not meet. **A publisher makes AT MOST THREE ATTEMPTS IN TOTAL to obtain an unused transient name — the initial attempt plus at most two retries with a fresh `<uniq>` — and then stops.** "Three attempts" is the whole budget, not three retries after an initial try: with the first three names occupied and the fourth free, the two readings publish and refuse respectively. A publisher that cannot obtain an unused name within those three attempts writes nothing and does not publish. *(Round 86, codex: the bound existed only in §4.2a-P's P-6, and §4.2a-S governs — so the authoritative specification permitted one attempt, four, or unbounded retries, all with different publication outcomes, while mutant 116 already depended on the bound. A behavioural rule cannot live in the primitives section.)*

**TMP-2 — Transients are invisible to readers.** The `.pub.` prefix places every transient outside the `base.*` pattern a reader enumerates, so no reader ever opens, counts, or authenticates one. A transient orphaned by a publisher killed between creating it and renaming it changes no resolution, no `_UNLEASHED_POINTER_STATE`, and no diagnostic.

**NM-1 — Name-length pre-check.** Before it composes the name of any file it will create in the store, the publisher computes the length of the LONGEST name it will create — the transient, `7 + len(<pid>) + len(<uniq>) + len(<key>)` bytes — and compares it against `NAME_MAX` for the filesystem holding the store. `NAME_MAX` is obtained from `/usr/bin/getconf NAME_MAX <dir>`, invoked by absolute path and never through `PATH`; the directory argument is mandatory (the bare command fails with `no such configuration parameter`), and `<dir>` is `bases/`, or the nearest existing ancestor of `bases/` when `bases/` does not exist yet. `len(<key>)` is a byte count and equals its character count. If the longest name exceeds `NAME_MAX`, the publisher creates nothing, sets `_UNLEASHED_POINTER_STATE=failed`, and emits exactly one diagnostic on stderr naming the length.

**HAR-1 — Harness HOME sandbox.** Every harness that exports `CLAUDE_PLUGIN_DATA` must set `HOME` to a temporary root of its own, resolved through `realpath`/`pwd -P` so that no component is a symbolic link, BEFORE it sources any family file. Those harnesses are `scripts/test-hooks.sh`, `scripts/tests/test_reviewer_roster.py`, and `scripts/tests/test_shell_primitive_drift.py` — the last sets `HOME=/probe` explicitly and still needs a temporary `HOME` so that a publish cannot create `/probe`. Each of those three harnesses must leave **the DEVELOPER's real store — the path captured from `HOME` BEFORE the sandbox replaces it, held in a separate variable for the postcondition** — byte-identical after it runs: every entry, and the set of entries. **It is NOT `${HOME}/.claude/unleashed-mail/bases/`, which after the reassignment denotes the SANDBOX — the very directory a successful publishing cell must create an entry in, so demanding that be unchanged is impossible for any cell that publishes.** Mutant row 54 already means the real store; the postcondition now names what it means.

**HAR-2 — test_plugin_state_base.py HOME regime.** In `scripts/tests/test_plugin_state_base.py` the `HOME` rule is file-wide, not per-cell. Every cell that must reach the unresolved state sets `HOME=""`; it must not `unset HOME`, because zsh repopulates `HOME` from passwd while bash leaves it unset. Every other cell gets its own temporary `HOME` resolved through `realpath`/`pwd -P`. Any cell that relies on a valid fixture asserts that the fixture authenticates before using it as a positive oracle. `/.claude` is in `test_nothing_is_created_at_root`'s watch set.

### Encoder

**ENC-1 — Entry-key encoder (Invariant P).** K is a pure function of a byte string. K(v) is computed by a SINGLE left-to-right walk over the bytes of v with `LC_ALL=C` in force, emitting for each input byte exactly one of four disjoint markers and otherwise that byte unchanged: `_` (0x5F) -> `_u`; `/` (0x2F) -> `_s`; an upper-case ASCII letter C (0x41-0x5A) -> `_c` followed by the lower-case form of C; a byte >= 0x80 or < 0x20 -> `_x` followed by exactly two lower-case hexadecimal digits giving that byte's value. There are exactly FOUR markers: no fifth marker, no case folding, no locale dependence and no other transformation. The four rows above are the whole table, so 0x7F (DEL) is emitted unchanged. Decoding is unambiguous — `_` is always followed by exactly one of `u`, `s`, `c`, `x`; `c` consumes one further output byte and `x` consumes two — therefore K is injective. The entry key for a base value is K applied to the absolute base path the publisher holds. No other statement of the encoder anywhere in the document is normative.

**ENC-2 — Fork-free single-pass derivation.** The derivation of K forks zero times and runs no external program: it is a plain assignment built from parameter expansion, with the lower-casing of an upper-case ASCII letter performed by a `case` arm per letter. Forbidden: command substitution (`k="$(...)"`), `tr`, `sed`, any other external command, bash-4's `${x,,}` (the shell floor is bash 3.2.57), the two-pass `${v//…}` substitution form, and any `%`-based escaping. The walk is a single pass — each input byte is consumed exactly once and its output appended, and output bytes are never re-examined or re-encoded. Consequently no substitution order exists: the `case` arms may appear in any order and there is no "escape the escape character first" obligation.

**ENC-3 — LC_ALL scope and restoration.** Before deriving K the resolver records whether `LC_ALL` is set in the caller's environment and, if set, its value. It sets `LC_ALL=C` for the duration of the derivation only and, immediately afterwards, restores exactly that state: re-assigning the saved value if `LC_ALL` was set on entry, and executing `unset LC_ALL` if it was unset on entry (an empty `LC_ALL` is not the same as an absent one). The restoration runs on every path by which the derivation ends, so a consumer's locale is unchanged after the resolver runs.

**ENC-4 — Key output alphabet.** Every byte K emits is a single byte in the range 0x20-0x7F and is never an upper-case ASCII letter. Three consequences are load-bearing and must not be weakened: on a case-insensitive volume there is nothing to fold, so `/Data/A` and `/Data/a` yield distinct entry names; on a normalization-insensitive volume there is nothing to normalize, so the NFC and NFD spellings of one path yield distinct entry names. **The cost of that is stated rather than discovered: two publishers naming the SAME physical directory in different spellings — NFC versus NFD, or two case variants on a case-folding volume — write TWO entries, and every reader then reports `conflict` and refuses.** The capability fails CLOSED, which is the correct direction, but it fails: an operator sees a conflict between two installs that are in fact pointing at one directory, and the recovery is the same `rm` any conflict needs. Normalising the value before encoding is REJECTED as the fix — it would make K non-injective over byte strings, so two genuinely different targets could collide on one entry name, trading a visible false conflict for a silent wrong resolution; and a key's length in characters equals its length in bytes, so `${#_k}` is an exact byte count for the name-length budget.

**ENC-5 — Injectivity and its consequences.** Distinct base values produce distinct keys and therefore distinct entry paths, so two publishers holding DIFFERENT base values never write the same file. There is no critical section in the publish path: no lock, lockfile, mutex or EXIT trap may be introduced to serialise it. Two publishers holding the SAME base value do converge on one entry name; that is permitted and must not be guarded against — they write identical bytes and the rename is atomic, so either order yields the same content. The count of authenticating entries in the store IS the count of distinct base values: a reader obtains that count by counting authenticating entries and never accumulates or compares target strings — no accumulator variable, no delimited list, no `case`-pattern match over a path, and no dependence on which characters a path contains.

**ENC-6 — Counting-mutant fixture bases.** The mutant that reverts entry counting to a space-delimited target-string accumulator is exercised against a store whose base values make the membership test MISCOUNT — one value whose space-delimited runs contain another value exactly, with the containing value scanned first. **MEASURED, and this corrects what this rule previously required:** a base containing a glob metacharacter does NOT miscount under the documented form `case " $acc " in *" $val "*`, because `$val` sits INSIDE the double quotes and its metacharacters are literal in both bash 3.2.57 and zsh 5.9 — a fixture of `<S>/g!` beside `<S>/g*` gives correct 2 and mutant 2, and discriminates nothing. A base containing a SPACE is the whole mechanism. Row 42's fixture keeps a glob metacharacter in its space-bearing value so the shape this rule names is still present, but the glob is not what discriminates and this rule no longer claims it is.

**ENC-7 — Same-base concurrent-publish case.** The mutant suite carries, in addition to the mutant that reverts the transient name to `$$` alone, an executable same-base concurrent-publish CASE: two publishers holding the same base value, racing on the single entry name that value encodes to, converge on byte-identical content with no torn read and no lost write.

**ENC-8 — Cross-shell key agreement.** For one base value the encoder produces BYTE-IDENTICAL keys in bash (floor 3.2.57) and in zsh (5.9), including for a base value containing non-ASCII bytes; this is asserted executably, not argued.

**ENC-9 — Name-length budget pre-check — see NM-1, which states it.** This rule adds only the ENCODER's stake in it: `len(key)` is a byte count that equals its character count (ENC-4), which is what makes the budget computable at all. The check itself, its trigger and its failure behaviour are NM-1's and are not restated here. *(Round 68: the pre-check was stated three times — NM-1, here and PUB-6 — with PUB-6's trigger strictly weaker than this one. They agreed on the day they were written, which is how every drift in this document began.)*

**ENC-10 — Entry names are path-material.** K is lossless and trivially reversible (`_u` -> `_`, `_s` -> `/`, `_c<c>` -> the upper-case letter, `_x<hh>` -> that byte), so an entry NAME carries exactly as much path material as the absolute path it encodes. No entry name and no target path is ever written to stderr, into a marker record, into a log record, or into the model's context. This includes the conflict diagnostic and every recovery instruction: they report how many entries disagree and never name an entry, a target, or the obsolete entry to delete — the operator is told to list the store themselves. Diagnostics carry counts and lengths only. The raw base path appears only inside the store's entry files, one per publisher, and nowhere else.

### Authentication

**AUTH-1 — The one authentication predicate.** "Authenticates" / "fails authentication", wherever either phrase is used of a store entry, denotes ONE predicate over a single entry, implemented by ONE shell function that both the publisher and the reader call. A second predicate, or a weaker variant of it at any call site, is forbidden. An entry authenticates IF AND ONLY IF ALL of the following hold: (a) ENT-1, the file clauses on the entry file itself; (b) ENT-2, the exactly-one-line clause; (c) ENT-3, the name-equals-encoded-content clause; (d) TGT-1, the content clauses on the single line the entry holds; (e) PCH-1's component walk over the entry's OWN chain — every component from `/` down to and including the entry's parent directory `bases/`; (f) PCH-1's component walk over the TARGET chain — every component from `/` down to and including the directory named by the line; (g) ANCHOR-1's ownership rule, applied to each of those two chains; (h) ACL-1..ACL-5, applied to every component of BOTH chains. Failure of any single clause makes the entry a failing entry; there is no clause an implementation may apply on one side and not the other. **Clause (h) — the one sanctioned carve-out.** On a platform where the ACL condition is unevaluable **because no enumerator EXISTS for it** — never because a present enumerator failed, which may be failing precisely because the component is hostile — a PUBLISHER omits the ACL clauses when authenticating **its own entry**, on EVERY such authentication — the write-or-skip decision AND the post-scan re-verification of that same entry. **The carve-out covers exactly these publisher call sites and no others: (i) the write-or-skip decision and (ii) the post-scan re-verification, both of the publisher's OWN ENTRY; (iii) the store-and-ancestor check of PUB-9 E4; and (iv) PUB-7's pre-write authentication of the TARGET CHAIN.** They are numbered rather than counted in prose: the previous wording said "three" and then listed four evaluations, because the own-entry pair reads as one site and behaves as two — which is exactly the ambiguity that let mutant 106 pass while covering only one of them. They are enumerated because "its own entry" does not by itself cover a directory or a chain, and two rounds running the exemption was granted at one site while another refused for want of it. No clause OTHER than the ACL clauses may be omitted at any call site, and a READER never omits the ACL clauses. Scoping this carve-out to the write decision alone makes the post-scan re-verification unevaluable and returns `stale` on every enumerator-less runner, which is the CI-red defect §4.2a records as the fifth turn of the hook/ACL-cost family.

**ENT-1 — Entry file clauses.** The entry file `<store>/base.<key>` must be a regular file, must NOT be a symbolic link, must be owned by the effective uid, and must be mode exactly `0600`. A `base.*` path that is a symbolic link — dangling or not — is a FAILING entry, never a vanished-entry skip. A `base.*` path that exists and is not a regular file (directory, FIFO, socket, device) is a failing entry.

**ENT-2 — Exactly one line, exactly its bytes, read from the object that was validated.** The entry authenticates only if ALL of these hold: **(1) the read RETURNS 0 and the content ends in exactly one newline** — a non-zero return means EOF with no delimiter, i.e. no trailing newline; **(2) its size in bytes equals the length of the line read plus one** (the single trailing newline); and **(3) — in zsh only — the line contains no NUL.** They are total over every malformed shape only TOGETHER, and each covers a case the others miss: (1) catches a TERMINAL NUL and an empty file in BOTH shells, (2) catches a mid-line or leading NUL in BASH (which truncates at the NUL, so the file is longer than the line), and (3) catches the same in ZSH (which keeps the NUL, so the byte count matches). **(2b) THE READ IS BOUND TO THE OBJECT ENT-1 VALIDATED.** ENT-1 stat'ed the PATHNAME; a plain `read < "$p"` then opened the pathname a SECOND time, and same-uid interference substituting the entry between the two — a FIFO, whose read-open BLOCKS every hook at source time; a large regular file the pre-read size bound never saw — was read in place of what was checked. So the entry is opened ONCE, and THE OPENED OBJECT IS BOUND TO THE OBJECT ENT-1 VALIDATED: its inode (P-2 now returns `_U_INO`) must equal the inode ENT-1 stat'ed — which binds every clause ENT-1 validated on the pathname, MODE INCLUDED, to the descriptor without a second copy of any of them (a second mode check on the descriptor masked ENT-1's own mutants, rows 8 and 114); type, size and owner are re-read on the descriptor as well, and the read is bounded to `len(key)+1`, the largest size a valid entry can have (ENT-3). A same-uid replacement of any kind — a `0644` copy with valid content included — is a different inode and is refused (PR #67, codex pass 11 — reproduced, both shells; row 168). The two arms differ only in what the shell can do, and the difference is stated: **zsh** opens with `sysopen -o nonblock` (never blocks on a FIFO), validates with `zstat -f` (INODE equal to ENT-1's, then TYPE, UID and SIZE of the OPEN object — the mode is bound through the inode, not re-checked: a second copy on the descriptor masked ENT-1's clause from its own mutants, rows 8 and 114) and reads once with `sysread -s len(key)+1`, taking the content up to the FIRST newline as the line exactly as `IFS= read -r` does, so clause (2) alone refuses a second line (row 4); **bash 3.2** has no non-blocking open, so a FIFO substituted in that window still blocks it — P-5's stated residual, mirrored here rather than claimed closed — and validates the open object through `/dev/fd/N`, which on Darwin (measured) reports its INODE, TYPE, SIZE and UID but its MODE as the open flags and its DEVICE as fdesc's, so the binding is by inode and mode stays validated on the pathname; its read is `read -r -n len(key)+1 -u N`, which stops at the newline or the bound. The descriptor is allocated, not fixed: zsh's `sysopen` needs an explicit number, taken from a free `{fd}` allocation and closed after; bash's `9<` on a group is saved and restored by the shell. Measured, both shells: a valid entry resolves with no stderr; a large regular file, a symlink, a vanished entry — and in zsh a FIFO — substituted between ENT-1's stat and the open are all refused as failing entries with the one sanitised diagnostic, never a path-bearing shell message (the group's `2>/dev/null` sits OUTSIDE the redirection that can fail). Mutant row 160. *(PR #67, codex pass 7. Round 104, codex: this rule declared the two-clause design complete and total while the round-102 correction added the third clause in a NOTE below — fix-the-rule-not-the-note, in the round that fixed a fail-open. Measured: `/private/tmp<NUL>` with no newline gives bash `rc=1`, `size=13`, `${#line}+1=13`, so clauses (2) and (3) alone PASS it and a correctly named entry targeting the real `/private/tmp` authenticates.)*

*Why it is written this way, all measured in bash 3.2.57 and zsh 5.9:*
* **The shells diverge on NUL.** Reading `/tmp\0junk\n`, bash yields `/tmp` (length 4) and zsh yields `/tmp\0junk` (length 9). Bash would otherwise authenticate a NUL-injected entry as the perfectly valid absolute path `/tmp`.
* **The byte-count check closes bash's half by construction** — the truncated read makes size (10) disagree with length+1 (5) — and it also closes `<path>\n\n` (4 vs 3), a missing trailing newline (11 vs 12) and a genuine second line (5 vs 3), in BOTH shells.
* **zsh needs the explicit NUL test** because it keeps the NUL, so size and length+1 agree (10 = 10) and the byte check passes.
* **bash must NOT run the NUL test.** `$(printf '\0')` is the EMPTY STRING in bash — command substitution strips NULs — so the pattern `*""*` matches everything and refuses every valid entry. Measured: the check written unguarded rejects a known-good entry in bash. It is guarded by `[ -n "${ZSH_VERSION:-}" ]`.
* **The first `IFS= read -r` must RETURN 0.** A non-zero return means EOF was reached with no delimiter — the file does not end in a newline — and a file whose final byte is a NUL is exactly that case. **Measured: `/private/tmp<NUL>` with no newline gives bash `line=/private/tmp`, `rc=1`, `size=13` and `${#line}+1=13`, so the byte-count clause PASSES and the NUL is mistaken for the required newline** — `/private/tmp` is an absolute non-symlink directory, so a correctly named entry then authenticates in bash while zsh refuses it. The three clauses cover DIFFERENT cases and all three are required: `rc=0` catches a terminal NUL and an empty file in BOTH shells; the byte count catches a mid-line or leading NUL in BASH (which truncates at the NUL); P-12's zsh-only pattern catches the same in ZSH (which keeps it, so the byte count matches). Verified over clean, terminal-NUL, mid-NUL, leading-NUL and NUL-only fixtures: every NUL-bearing file refuses in both shells, only the clean line accepts.
* **The line is read with `IFS= read -r` (§4.2a-P P-11), never plain `read`**, which would consume a backslash and strip a trailing space — both of which TGT-1 permits in a base value, and both of which would make this clause compare transformed bytes against the file's real size.
* The size comes from the same accessor call as the mode (§4.2a-P P-2), so it costs no extra fork —
  in BOTH arms, which P-2 previously satisfied in only one. The `${#line}` this size is compared
  against is a BYTE count taken with `LC_ALL=C` in force (§4.2a-P P-2a); taken under a UTF-8 locale
  it counts characters and this clause then rejects every valid non-ASCII entry.

**ENT-3 — Name equals encoded content.** The entry authenticates only if `<store>/base.<key(L)>` — where L is the single line the file holds and `key()` is the Invariant P encoder — is byte-equal to the entry's own path. Because `key()` is injective over values, two entries with different names necessarily hold different values; therefore the count of distinct bases IS the count of authenticating entries. Neither reader nor publisher may accumulate target strings, delimit them, or pattern-match them to count distinct bases.

**TGT-1 — Entry content clauses.** **A base value containing a NEWLINE is not publishable**, even though such a directory can exist on Unix: the entry format is one line, so publishing it creates a durable entry every reader then rejects as multi-line. It is excluded from the accepted domain at the same point as a relative path or an embedded NUL, and the publisher reports `failed` without deriving a key. The single line an entry holds must be an absolute path (its first byte is `/`), must not end in `/`, must contain no NUL byte, and must name a directory that exists. A relative value, a value with a trailing slash, a value containing NUL, a path that does not exist, and a path naming an existing non-directory are each a failing entry. These clauses are part of the one predicate and are applied identically by publisher and reader; a publisher holding a value that violates any of them publishes no entry for it.

**PCH-1 — Both chains, one walk.** One and the same component walk applies to BOTH chains: the entry's own chain (`/` down to and including the entry's parent directory `bases/`) and the target chain (`/` down to and including the target directory itself). Every component of the chain being walked must: exist; NOT be a symbolic link; NOT be group-writable; NOT be other-writable; and satisfy ANCHOR-1's ownership requirement. Intermediate ancestors are covered, not merely the final component. Neither chain carries a clause the other lacks, and no component of either chain is exempt. (The entry's parent `bases/` carries, in addition to these clauses, the store-authentication rule's exact-`0700` and euid-owned requirements.)

**ANCHOR-1 — Trust anchor ownership domain.** Ownership on a chain is required from the TRUST ANCHOR downward, by one rule covering both the through-`${HOME}` and off-`${HOME}` cases. Walk the chain from `/` downward and accept a leading run of SYSTEM PREFIX components, where a system prefix component is owned by uid 0, is not group- or other-writable, and is not a symbolic link. The TRUST ANCHOR is the first component that is not such a system prefix; every component from the anchor downward, inclusive, must be owned by the effective uid. **That is the WHOLE rule and it applies uniformly: a root-owned `${HOME}` that satisfies the system-prefix test REMAINS IN THE PREFIX, and the anchor falls on the first component below it that does not** — for a managed `/opt/managed-home` owned by root with an euid-owned `.claude` beneath it, the anchor is `.claude`. No clause may require every component from `${HOME}` downward to be euid-owned: that is a second, stricter rule, it rejects chains this one accepts, and it applies to the reader and to E4's publisher check alike. *(Round 90, codex: the rule and its own explanatory sentence gave opposite verdicts on exactly that state.)* For a chain passing through a euid-owned `${HOME}` this yields: the components above it are accepted as system prefixes and the anchor falls on `${HOME}` itself. For a chain through a ROOT-OWNED `${HOME}` that satisfies the system-prefix test, `${HOME}` stays in the prefix and the anchor falls below it. Requiring euid ownership of every component of a chain is forbidden, and so is requiring it of no component.

**WRIT-1 — No writability clause.** Authentication contains NO writability clause. It tests ownership, symbolic links, mode bits, the two chains and ACLs, and nothing else. A readable but UNWRITABLE target still authenticates and still resolves with `OK=1`; writes into it no-op silently and the sourcing shell survives. No `-w` test and no trial write may be added to the predicate at any level — not on the base, not on `.state`, `logs` or `reviews`.

**ACL-1 — ACL arms are the definition.** The ACL condition on a component is decided ONLY by the per-platform arms ACL-2 (Darwin), ACL-3 (Linux) and ACL-4 (any other platform, or a missing enumerator). There is no platform-independent ACL rule: the summary sentence "refuse if any component carries an `allow` ACE naming a principal other than the effective user and granting a mutating right" is a gloss, is NOT normative, and may not be implemented, cited as the rule, or restated in any risk row or summary section. On EVERY platform, `deny` entries are ignored entirely — a component is never refused on account of a `deny` entry.

**ACL-2 — Darwin ACL arm.** When `/usr/bin/uname -s` outputs `Darwin`, enumerate a component's ACL with `/bin/ls -lde <path>`. Each ACE line has the form ` <n>: <principal> [inherited] <allow|deny> <perms>`, where the `inherited` token is PRESENT ON EVERY INHERITED ACE and absent otherwise — measured: a directory under a parent carrying `+a "staff allow list,search,file_inherit,directory_inherit"` prints ` 0: group:staff inherited allow list,search,file_inherit,directory_inherit`, so a positional parser that expects `allow|deny` as the third field sees `inherited` there and matches nothing, FAILING OPEN on precisely the ACEs an MDM-managed fleet propagates. The arm must locate the `allow`/`deny` token rather than assume its position — **and it must enforce EVERY SLOT of the grammar, not merely find the verb.** An ACE line matches IF AND ONLY IF, reading its fields left to right after the ` <n>: ` index: field 1 is the PRINCIPAL and is not `allow`, `deny` or `inherited`; then AT MOST ONE `inherited`; then EXACTLY ONE `allow` or `deny`; then EXACTLY ONE `<perms>` field, which is likewise none of `allow`, `deny` or `inherited`. **Any other shape — a second verb, a second `inherited`, an unknown field before the verb, a reserved token in the `<perms>` slot, a missing or empty `<perms>` — does NOT match, so ACL-4 governs, the condition is UNEVALUABLE and the component is REFUSED.** P-13 gives the executed primitive; this rule is where the obligation lives. *(Round 116, codex: the stricter grammar existed only in P-13 while THIS rule said merely to "locate" the verb — and §4.2a-S governs, so the positional grammar was not authoritative. A behavioural rule cannot live in the primitives section, which is the same finding round 86 made about TMP-1's retry bound.)* `<perms>` is a COMMA-JOINED list that mixes rights with INHERITANCE FLAGS: `file_inherit`, `directory_inherit`, `limit_inherit` and `only_inherit` are flags, not rights, and are excluded from the allowlist test — without that exclusion the same inherited read-only ACE REFUSES, killing the capability on every Mac that inherits ACLs, which is the opposite failure and is what row 90 forbids. This arm is string matching over those lines, not ACL semantics. For each `allow` ACE whose principal is not the effective user, REFUSE the component unless EVERY right named in that ACE is one of exactly these seven: `execute`, `list`, `read`, `readattr`, `readextattr`, `readsecurity`, `search`. This is an ALLOWLIST — a right that is not in the list REFUSES. A blacklist of mutating rights is forbidden, in any form.

**ACL-3 — Linux ACL arm.** When `/usr/bin/uname -s` outputs `Linux`, enumerate a component's ACL with `/usr/bin/getfacl -pc <path>`. REFUSE the component if EITHER holds.
**(a) MASKED CLASS — refused when the mask does not stop it.** An entry of the form `user:<name>:`, `group:<name>:`, `default:user:<name>:` or `default:group:<name>:` with `<name>` non-empty, **or an unnamed owning-group entry `group::` / `default:group::`**, carries `w`, AND either the corresponding mask line (`mask::` for access entries, `default:mask::` for default entries) permits `w`, **or there is NO corresponding mask line at all** — a minimal ACL may omit the mask, and an absent mask masks nothing.
**(b) UNMASKED CLASS — refused unconditionally.** `other::` or `default:other::` carries `w`. **The mask does NOT apply to the other class**, so a mask conjunct here can never fire and must not be written.
`default:` entries are evaluated by exactly the same rule as access entries, and `deny` plays no part: POSIX ACLs have no deny token, which is why the platform-independent gloss ACL-1 forbids is not merely different here but UNDEFINED. **Why the unnamed classes are load-bearing:** Linux initialises a new object's access ACL from the parent's DEFAULT ACL and the creation mode, NOT from `umask`, so a `0700` euid-owned target carrying `default:group::rwx` would authenticate under a named-only rule while every `.state`, `logs` or `reviews` directory a consumer later creates beneath it inherits group-write — the fail-open P-4 guards for the publisher's transient and nothing guarded for consumer-created children. *(Round 84, agy and codex concordantly. This rule is REWRITTEN rather than amended: round 80 added the unnamed classes, round 82 split masked from unmasked, and each edit replaced the opening while leaving the previous clause standing further down — so the paragraph simultaneously refused and authenticated `default:group::rwx` with no mask. Splicing a rule I have already edited twice is what produced that; the whole statement is replaced here.)*

**ACL-4 — Unevaluable ACL platform.** On any platform that is neither Darwin nor Linux, when the selected platform's enumerator is absent from its absolute path, **or when that enumerator is present but does not produce a parseable answer — a non-zero exit, empty output, or an ACE LINE that does not match the arm's stated grammar**. "ACE line" is exact and load bearing: `/bin/ls -lde` prints a `drwxr-xr-x@ 2 nick wheel …` stat line FIRST and the numbered ACEs after it (measured), so a rule reading "any line that does not match" makes EVERY component unevaluable and the capability dies on Darwin. **The enumerator's answer is parsed by an ANSWER-LEVEL STATE MACHINE over the grammar `STAT (BLANK | ACE)*` — one mandatory initial stat line, then any number of blank and ACE lines in any order — and ACCEPTANCE IS IMPOSSIBLE UNTIL THAT STAT LINE HAS BEEN SEEN.** An answer that is empty, that begins with a blank line, that begins with an ACE, that carries a second non-space line, or that never reaches the body state at all is MALFORMED. **Line-level classification is NOT whole-answer parsing** and stating it that way was the defect: it made each line's kind decidable in isolation while leaving the ANSWER's shape unconstrained, so an answer consisting solely of a well-formed read-only ACE — no stat line — was accepted as parseable and an otherwise-valid single-entry store resolved with `OK=1` instead of refusing. *(Round 122, codex, asked directly whether the structure itself was wrong and answering that it was: "parsing the ACL output remains necessary, but independently classifying lines is not whole-answer parsing. It needs an answer-level state machine, not another slot-specific exception." This arm had failed the gate SIX consecutive rounds, each fix correct and each leaving a different gap; the state machine is the first formulation whose acceptance condition is a property of the WHOLE ANSWER.)* Within the body state the line kinds are, exhaustively and disjointly: the FIRST line is the stat line (it does not begin with a space); a BLANK line; an ACE line, which is ` <decimal index>: ` followed by a body matching this rule's slot grammar; and ANYTHING ELSE, which is MALFORMED. Blank lines are skipped and are not evidence of an unparseable answer, and the ONE initial stat line is required rather than merely tolerated; **a line that is neither of those and is not a well-formed ACE POISONS THE WHOLE ANSWER — the ACL condition is UNEVALUABLE and the component REFUSES.** There is deliberately no "skip what we do not recognise" arm: that arm is how a malformed prefix reached the field parser. **The index must be one or more DECIMAL digits and the delimiter exactly `: `** — measured, ` 0:group:staff allow list` (no space) and ` x: group:staff allow list` (non-decimal) both parsed as valid ACEs under the round-116 primitive, which stripped through the first `: ` without proving it had matched. *(Round 120, codex: round 118's block returned 2 for EVERY non-space line without tracking its POSITION, so `stat-line` followed by `garbage` was accepted as an ACL-free answer. **I had already found and fixed this exact drift in my own step-3b draft one round earlier and did not carry the fix back to the plan** — fixing one member of a family and leaving the other is the failure this document has recorded against me more than any other. Measured, both shells: line 1 stat -> skip, line 2 ACE -> parsed, line 3 `garbage-after-stat` -> MALFORMED.)* *(Round 118, codex — the FOURTH consecutive round in which this arm failed open, and the first three fixes each constrained the slot just exploited and left the next. The rule is now a whole-line match rather than a sequence of slot checks, which is the shape that cannot leave a gap.)* *(Round 124, agy and codex CONCORDANTLY: this sentence survived round 122 and contradicted both itself and the normative statement four lines above it — a stat-only answer could either authenticate or refuse. Round 122 edited a DIFFERENT sentence and left this one.)* The present-but-failing case is named explicitly because "missing binary" was the only stated trigger, leaving a tool that exits 1 with no verdict at all: an implementation could then treat its silence as "no ACEs found" and ACCEPT, which is the fail-open inversion this design has already produced four times. A READER refuses any component whose ACL condition is unevaluable — never accepts it on mode bits alone — and that refusal is an ordinary resolution outcome requiring no new enum value: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic. **A PUBLISHER omits the ACL clauses only at the call sites AUTH-1 clause (h) ENUMERATES, and only when the platform is unevaluable because no enumerator EXISTS for it. This rule states no scope of its own: AUTH-1(h) is the single statement of the carve-out and this sentence references it.** The exemption never extends to an enumerator that is present and merely failed — a tool that exits non-zero or prints an unparseable ACE line may be failing precisely because the component is hostile — and never to a READER, for any entry. *(Round 78, codex and kimi concordantly: this is the FIFTH consecutive round in which the carve-out was corrected at one site and left at another, so it is no longer stated twice. Rounds 70, 72, 74 and 76 each edited one of the two and each left the other saying something different; point-fixing a rule that lives in two places has now failed four times, and the structural fix — one statement, everything else a reference — is the same one that closed the ACL gloss and the exit enumerations.)* *(Round 70, codex #2: round 68 widened "unevaluable" to cover a failing tool without noticing that the exemption is scoped to the same word, which silently widened the exemption too.)* Every other authentication a publisher performs applies the ACL clauses and refuses on an unevaluable component. **Consequence, stated here because it is a LIMIT and not a defect: on an unevaluable platform the capability is UNAVAILABLE.** The publisher writes and re-verifies its own entry, so a runner without an enumerator stays green, but no reader can ever consume that entry — a reader refuses every entry — and resolution on such a platform is exactly D′: sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic. BUD-5 conjunct 1 is scoped accordingly. **The reader is not given the publisher's exemption, and no later round may grant it.** The publisher's exemption is sound only because it is re-verifying bytes it wrote itself in this same process; a reader has no independent knowledge of the value, and ENT-3's name↔content check is SELF-CONSISTENT — whoever writes an entry writes both halves — so a reader exempted from the ACL clauses would accept an entry whose non-ACL clauses passed but whose components were never checked for a grant to another principal — and those clauses are the only ones that detect a component another principal can replace. That is mutant row 107, and it fails open.

**ACL-5 — Enumerator selection and invocation.** The platform is selected by running `/usr/bin/uname -s` — by absolute path — and the enumerator for the selected platform is invoked by absolute path (`/bin/ls` on Darwin, `/usr/bin/getfacl` on Linux). **`/usr/bin/uname -s` RUNS AT MOST ONCE PER RESOLUTION, LAZILY, and its result is shared**: it is probed at the first point at which P-2's arm selection or this rule's enumerator selection needs it, both then read that same value, and it is NOT probed at all on a resolution that evaluates no component. **BUD-1's derived count is therefore exactly 0 or 1, and which one is DERIVED rather than chosen: 1 iff at least one component is evaluated, 0 otherwise** — so PUB-9's E0, a reader whose `HOME` is unusable, and a resolution that finds no store all derive 0. *(Round 114, codex: the round-112 wording said BOTH "exactly once per resolution" AND "computed at the first point either needs it", and those diverge precisely on the paths that touch no component — implementations probing zero or one produced identical protocol values and different counts, so the expected number was still not derivable end to end.)* *(Round 112, codex: P-2 selects the `stat` arm through `/usr/bin/uname` and this rule selects the enumerator through `/usr/bin/uname`, and NOTHING said the result was shared — so an implementation that probes once and one that probes twice both conformed, with different counts, and BUD-1's expected number could not be derived. The old prose said "one `uname` plus one `ls -lde` per component" and that frequency constraint was LOST when §4.2a-S became authoritative — the first rule found silently absent from S since it was written.)* **The RECOGNISED platform names are exactly `Darwin` and `Linux`.** If `/usr/bin/uname -s` is absent or exits non-zero, NO enumerator is selected, the ACL condition is UNEVALUABLE under ACL-4, the component is REFUSED, and the publisher carve-out of AUTH-1(h) DOES NOT apply — a probe that FAILED may be failing because the machine is hostile. **A probe that SUCCEEDS and prints any other name — `FreeBSD`, say — is a platform with NO ENUMERATOR, which is precisely the condition AUTH-1(h)'s carve-out is for, so the carve-out DOES apply there and the publisher publishes.** *(Round 124, codex: AUTH-1 and ACL-4 permitted the carve-out on any non-Darwin/Linux platform while this rule withheld it for an "unrecognised" name it never defined, so `FreeBSD` had two authoritative verdicts — one implementation reports `created` and another `failed`.)*, because that carve-out is for a platform where no enumerator EXISTS, and a failed or unrecognised probe is a platform whose enumerator is UNKNOWN. A probe that fails may be failing because the machine is hostile, which is the same reason clause (h) withholds itself from a present enumerator that failed. *(Round 112, codex: ACL-4 covered an absent or failing ENUMERATOR and nothing covered a failing SELECTOR, so an implementer had to invent both the outcome and whether the publisher exception applied.)* Neither `command -v` nor a bare `uname`, `ls` or `getfacl` may be used for selection or invocation: both resolve through `PATH`, which differs between a plugin hook and a git hook.

**ACL-6 — ACL probe writes nothing, and a PRE-CREATION refusal creates nothing.** ACL evaluation writes nothing: it creates no file and writes no byte anywhere, and in particular never inside the path being validated. Authentication may not be established by attempting a write. **A refusal reached BEFORE any creation — which includes every refusal of an already-existing component, and therefore the symlinked-`HOME` case E4 orders validated first — creates no file anywhere.** *(Round 92, codex: this rule previously said the refusal path as a whole creates nothing, which flatly contradicted E4's one-at-a-time creation: with `.claude` created and `unleashed-mail` then failing, E4 requires `.claude` to remain and this rule required it never to have existed. E4's leave-in-place is deliberate — ST-3/ST-4 forbid the plugin removing directories, and a rollback would be the plugin deleting paths it does not own the right to delete — so the scope corrected here is ACL-6's, not E4's.)* Ancestors already created when a LATER creation or authentication fails are left in place per E4; they are `0700` and euid-owned, the next run reuses them, and nothing else in the store is touched.

**ACL-7 — No environment-dependent verdict.** For a given absolute path, the predicate's verdict must be a property of the MACHINE. No branch of the predicate — ACL arm or any other clause — may be conditioned on an environment variable; in particular there is no conditional on `CLAUDE_CONFIG_DIR`. The publisher runs as a plugin hook and the reader typically as a git hook, and a predicate that reads their differing environments would accept for one and refuse for the other.

**SHARED-1 — Publisher runs the follower predicate.** Before leaving an entry in place — INCLUDING on the no-write `current` path — the publisher runs the COMPLETE follower predicate (AUTH-1 in full, ACL clauses included, subject only to ACL-4's own-entry exception) against that entry. The write-or-skip DECISION itself is PUB-7's and is not restated here. A weaker type-and-content test is forbidden, so an entry that is a REGULAR NON-SYMLINK FILE at `0644`, or one holding a relative path, is repaired by republication rather than skipped. **A `base.<key>` that is a symlink or a directory is NOT repaired**: ST-7's precondition refuses it, the publisher writes nothing and reports `failed`. The repair contract stops exactly where `mv -f` stops being safe — it moves the transient INSIDE a directory, and on a symlink it can follow the link out of the store. This clause imposes the OBLIGATION to authenticate only: it assigns no `_UNLEASHED_POINTER_STATE` value, and the publisher's reported state comes solely from the ordered post-scan exits.

**THREAT-1 — Same-uid trust model.** The trust model is stated explicitly rather than left implicit or forward-referenced: the predicate closes the TOCTOU window to the SAME-UID case, which is the trust assumption the plugin already makes everywhere else. Resolving and following an entry is a prompt-injection path, not merely a state-integrity one, because `sessionstart-restore.sh` injects content read through the resolved base into the model's context via `additionalContext`; accordingly every component of both chains is validated, and the ACL condition on each is decided **per ACL-1..ACL-5 — the whole and only statement of the ACL rules, which this sentence references and does not restate**. The platform-independent formulation that stood here — any ACL grant to another principal refuses — is the gloss ACL-1 forbids, and it disagrees with ACL-3 on Linux, where `user:bob:rw-` under `mask::r--` is ACCEPTED. This was the THIRD site of that gloss; rounds 56 and 61 each fixed the two I found by recall instead of deriving the family. Nothing outside the same-uid case is defended: a machine whose system prefixes are user-writable is out of scope (and is refused by ANCHOR-1 rather than accommodated).

### Reader

**RD-1 — Reader precondition and HOME gate.** The reader (step 2) runs if and only if `CLAUDE_PLUGIN_DATA` is empty or unset AND `_UNLEASHED_HOME_OK` is true. `_UNLEASHED_HOME_OK` is computed once per process: true iff `HOME` is non-empty and absolute, tested `case "${HOME:-}" in /*) ;; *) … esac`. It gates only whether a `${HOME}`-rooted path may be composed, read or written; a non-empty `CLAUDE_PLUGIN_DATA` resolves regardless of `HOME`. When `_UNLEASHED_HOME_OK` is false the reader composes, opens and enumerates NO `${HOME}`-rooted path at all — it does not test the store, does not glob, does not stat — and takes the unresolved exit directly: `_UNLEASHED_BASE_RESOLVED=/dev/null/unresolved-plugin-base`, `_UNLEASHED_BASE_OK=0`, `_UNLEASHED_BASE_SOURCE=unresolved`, `_UNLEASHED_POINTER_STATE=none`, exactly one diagnostic.

**RD-2 — Reader rules are ordered.** The reader has SIX rules, numbered −1, 0, 1, 2, 3 and 4. They are evaluated in that order, top to bottom, first match wins, and exactly one exit is taken per resolution. The numbering is normative, not descriptive: rule −1 precedes any per-entry test, and rule 1 precedes rules 2 and 3. Any statement anywhere that enumerates the reader's rules — another section, a code comment, an inline copy in a family file — names all six as "−1 through 4"; an enumeration reading "rules 0-4" is incomplete and is prohibited.

**RD-3 — Rule −1: store authentication.** Rule −1 authenticates the STORE before any entry is touched. The store is `${HOME}/.claude/unleashed-mail/bases/`. If it exists and any of the following holds — it is not a directory; it is a symlink (tested without following); it is not owned by the effective uid; its mode is not exactly 0700; **any component of PCH-1's walk over the store's own chain — `/` down to and including `bases/` — fails, under ST-4's clauses and ANCHOR-1's ownership rule, which this rule REFERENCES and does not restate. The walk starts at `/`, not at `${HOME}`: the earlier `${HOME}` bound dropped every component above it**; any component of PCH-1's walk — `/` down to and including `bases/`, NOT merely `${HOME}` downward — carries an ACL condition that fails **per ACL-1..ACL-5 — the whole and only statement of the ACL rules. This clause restates none of them: a platform-independent formulation disagrees with ACL-3 on Linux, where `user:bob:rw-` under `mask::r--` is ACCEPTED by ACL-3 and refused by the gloss** — then refuse: `_UNLEASHED_BASE_RESOLVED=/dev/null/unresolved-plugin-base`, `_UNLEASHED_BASE_OK=0`, `_UNLEASHED_BASE_SOURCE=unresolved`, `_UNLEASHED_POINTER_STATE=stale`, exactly one diagnostic. If the store does not exist at all, evaluation proceeds to rule 4. Otherwise evaluation proceeds to rule 0. A store whose mode is not 0700 is REFUSED, never `chmod`'ed. The exact-0700 requirement applies to `bases/` alone; its ancestors (`${HOME}`, `~/.claude`, `~/.claude/unleashed-mail`) are held only to the general not-group-or-world-writable requirement, which 0755 satisfies. This rule is where the exact-0700 requirement FIRES FIRST, so an EMPTY store at the wrong mode refuses here instead of falling through to rule 4. It is not the only place the requirement is EVALUATED: RD-10 clause (d) requires `bases/` to satisfy ST-3 on every per-entry authentication, so a store whose mode changes mid-scan is caught there too. Both defer to ST-3 and neither restates it, so the two cannot disagree — which is why this is a second evaluation site and not a second statement. For ACLs this rule **references ACL-1..ACL-5 and states nothing of its own**: a platform-independent ACL sentence is a gloss ACL-1 forbids implementing, and it disagrees with ACL-3 on Linux (`user:bob:rw-` under `mask::r--` is accepted by ACL-3 and refused by the gloss).

**RD-4 — Rule 0: vanished entry skip.** Rule 0: a candidate that is not a symlink AND does not exist when opened is SKIPPED — it is not an entry, and skipping it changes no protocol variable and produces no diagnostic. The test is exactly `[ ! -L "$_f" ] && [ ! -e "$_f" ]`, both parts required. A one-part `[ -e "$_f" ]` (or `[ -e "$_f" ] || continue`) test is prohibited anywhere in the reader: `[ -e ]` is false for a dangling symlink, so the one-part form skips a hostile entry that must be refused. A symlink is always an entry — a hostile one — is never skipped as vanished, and falls through to rule 1. Because the test is two-part it also disposes of bash's unmatched literal `base.*` pattern, so no separate existence guard exists anywhere else in the scan. Operator deletion of an entry during a scan therefore does not flip a healthy store to `stale` **when the deletion lands before the candidate is tested**. It is NOT unconditional, and the earlier "never" was: the test and the open are separate syscalls, so a deletion landing between them yields a failing authentication and `stale`. The window is inherent to a test-then-open sequence and is accepted; what is forbidden is claiming it away.

**RD-5 — Rule 1: failed entry refuses.** Rule 1: if any entry surviving rule 0 fails the complete authentication predicate, refuse: `_UNLEASHED_BASE_RESOLVED=/dev/null/unresolved-plugin-base`, `_UNLEASHED_BASE_OK=0`, `_UNLEASHED_BASE_SOURCE=unresolved`, `_UNLEASHED_POINTER_STATE=stale`, exactly one diagnostic. This fires however many entries authenticate beside the failing one: a malformed entry is never ignored in favour of a good one, and one valid plus one malformed entry refuses. A failing entry maps here and never to rule 4's `none`.

**RD-6 — Rule 2: conflicting entries refuse.** Rule 2: if two or more entries surviving rule 0 authenticate, refuse: `_UNLEASHED_BASE_RESOLVED=/dev/null/unresolved-plugin-base`, `_UNLEASHED_BASE_OK=0`, `_UNLEASHED_BASE_SOURCE=unresolved`, `_UNLEASHED_POINTER_STATE=conflict`, exactly one diagnostic. That diagnostic names neither the target paths nor the entry names — it reports only how many entries disagree and tells the operator to list the store themselves. No path material, reversible or otherwise, reaches stderr. Conflict is a property of the directory derived at read time: no publisher records it, there is no wire form for it, no stickiness rule, and nothing has to be recorded for it to survive — every later reader of the same directory derives it again.

**RD-7 — Rule 3: single entry resolves.** Rule 3: if exactly one entry surviving rule 0 authenticates, resolve to it — `_UNLEASHED_BASE_RESOLVED` is that entry's single line (the absolute path of the target directory), `_UNLEASHED_BASE_OK=1`, `_UNLEASHED_BASE_SOURCE=pointer`, `_UNLEASHED_POINTER_STATE=none`, and NO diagnostic is emitted. This is the only reader exit that resolves.

**RD-8 — Rule 4: nothing to resolve.** Rule 4: if zero entries survive rule 0, or the store directory does not exist at all, take the unresolved exit. **"Does not exist at all" is decided by a walk from `/` down the store's own path, not by `[ ! -e store ]`:** the store is absent iff every prefix that EXISTS is a searchable directory and the first missing component is simply missing. `-e` on the full path is also false when an ANCESTOR exists but cannot be searched (`${HOME}/.claude` at 0600), and that store is not absent, it is HIDDEN — a prefix that exists as a symlink, a non-directory or an unsearchable directory is rule −1's business, whose chain walk fails on it and refuses `stale`, so the SessionStart repair notice fires where rule 4's silent `none` would have hidden a broken store *(PR #67, codex pass 8 — reproduced, both shells; mutant row 163)* — `_UNLEASHED_BASE_RESOLVED=/dev/null/unresolved-plugin-base`, `_UNLEASHED_BASE_OK=0`, `_UNLEASHED_BASE_SOURCE=unresolved`, `_UNLEASHED_POINTER_STATE=none`, exactly one diagnostic.

**RD-9 — Store enumeration.** The reader enumerates exactly the glob `<store>/base.*`, from inside the scanning function. `.pub.<pid>.<uniq>.<key>` temporaries lie outside that glob by construction, are never enumerated, and a crash-orphaned temporary therefore changes no resolution. Under zsh the scanning function executes `setopt local_options no_nomatch`, guarded by `[ -n "${ZSH_VERSION:-}" ]`, because `setopt` is a zsh builtin and bash's `command not found` under the `set -euo pipefail` these libraries are sourced with aborts the sourcing shell in exactly the arm the guard protects; zsh restores the option at function return. Under bash the unmatched pattern remains literal and is disposed of by rule 0's test — the enumeration itself carries no existence guard. The empty-store case is asserted under zsh independently for each of the five family files; one passing arm is not evidence about the other four.

**RD-10 — What authenticates means.** In rules 0 through 4 an entry "authenticates" only if the WHOLE composed predicate holds — implemented as ONE function, the same one the publisher runs against the entry it is about to leave in place: (a) the entry is a regular file, not a symlink, owned by the effective uid, mode exactly 0600; (b) it holds exactly one line, and that line is an absolute path with no trailing slash and no embedded NUL naming an existing directory (a second line disqualifies the entry); (c) `<store>/base.<key(line)>` equals the entry's own path, where `key()` is the injective encoder — the name↔content check; (d) **PCH-1's walk over the entry's own chain — every component from `/` down to and including the entry's parent `bases/`** — with ANCHOR-1 governing which components must additionally be euid-owned, and `bases/` itself satisfying ST-3. This clause references PCH-1, ANCHOR-1, ST-3 and ST-4 and restates none of them. **It previously began the walk at `${HOME}`, which silently dropped every component above it**: a group-writable `/Users` passed the reader while AUTH-1(e) and PCH-1 said it must refuse, so the composed predicate and its own clause list disagreed about how far the chain reaches; this clause references those rules and restates neither, so a symlinked ancestor fails here exactly as it fails under rule −1; (e) every component of the TARGET path exists, is not group- or world-writable and is not a symlink, and every component at or below the trust anchor is owned by the effective uid; (f) the ACL clauses hold on every component of BOTH chains — refuse on an ACL condition that fails **per ACL-1..ACL-5**, ignore `deny` entries, and evaluate Linux `default:` entries exactly as access entries. Applying only clauses (a)-(c) is prohibited. Where the ACL condition cannot be evaluated — no enumerator for the platform, or the expected enumerator absent at its absolute path — the entry FAILS on the read path; the allowance that lets a publisher skip the ACL clauses for its OWN entry on such a platform never applies to a reader, for any entry. Rule −1's word "authenticate" is a different predicate with its own clause list and never imports these clauses.

**RD-11 — Count entries, never accumulate.** The count rules 2 and 3 test is the count of AUTHENTICATING ENTRIES, and that count is the count of distinct base values: directory entries are distinct by construction, and the injective encoder plus the name↔content check make two entries with different names necessarily hold different values. The reader never accumulates target strings — no space-delimited accumulator, and no `case " $_U_TARGETS " in *" $_L1 "*` membership test (an unquoted `case` pattern makes glob metacharacters in a path match as wildcards, and a base containing a space breaks the delimiting).

**RD-12 — Bounded read of entries, and NOTHING IS OPENED BEFORE ITS TYPE IS KNOWN.** **The entry's ENT-1 type clauses — regular file, not a symbolic link — are evaluated BEFORE any open, and a path that fails them is a failing entry that is never read.** `[ -L ]` alone is not sufficient and was the only guard this rule named: a FIFO is not a symlink, so it passed, and the redirect then BLOCKS FOREVER waiting for a writer — measured in bash 3.2.57 and zsh 5.9, `rc=124` at a 5-second timeout in both. Because the resolver runs at SOURCE TIME in every process that loads a family file, one FIFO named `base.*` in the store hangs every hook, permanently. ENT-1 already CLASSIFIES a FIFO as a failing entry; what was missing is the ORDER, and a classification that is applied after the open cannot prevent the hang. This is the reader-side twin of P-5's publisher hang: round 70 fixed the publisher and left the reader, so the same primitive defect survived in the other half of the family. The read itself is bounded: at most two lines from each `base.*` entry in the one store directory, the second read only to detect its presence. Nothing else is read — never repository content, never user content, never anything that reaches a consumer or the model's context. Every read target is pre-initialised before the read and every later expansion of it uses `:-`; the redirect is taken at GROUP level, because in zsh no redirect ordering on the inner command suppresses an open failure; and the entry is `[ -L ]`-tested before the read so a symlink is never opened. The read is performed inside the shared authentication function, never as top-level source-time code in a sourced library.

**RD-13 — Reader diagnostics: one, stderr.** Every REFUSING reader exit — the HOME-unusable exit, rule −1, rule 1, rule 2 and rule 4 — emits exactly one diagnostic; rule 3 emits none, so a reader that resolves leaves stderr empty. Each diagnostic is a single bounded line on stderr; it is never written to the plugin's own log and is never persisted. Cardinality is a property of the resolution protocol, not of `paths.sh`: each family file emits only while `_UNLEASHED_BASE_OK` is still unset and sets it in the same step, so sourcing two or three libraries with `paths.sh` absent still yields exactly one diagnostic per process. A blanket "stderr is empty" assertion over unresolved cells is prohibited — it contradicts the one-diagnostic obligation of every refusing exit.

**RD-14 — Reader exit totality.** The reader's exit paths are exactly six: the HOME-unusable exit, rule −1's refusal, rule 1's refusal, rule 2's refusal, rule 3's resolution, and rule 4's fall-through. Rule 0 is a skip, not an exit, and changes no protocol variable. Every one of the six sets all four protocol variables (`_UNLEASHED_BASE_RESOLVED`, `_UNLEASHED_BASE_OK`, `_UNLEASHED_BASE_SOURCE`, `_UNLEASHED_POINTER_STATE`) and is mapped to exactly one value of the declared list `created|current|conflict|stale|failed|none`; because the rules are ordered and first match wins, no exit is reachable by two rules. An exit with no value, or a value not in the declared list, fails verification. The reader emits only `stale`, `conflict` and `none`; `created`, `current` and `failed` are publisher-only and a reader never reports them. The mapping is verified against the declaration rather than asserted in prose.

**RD-15 — Sentinel and consumer detection.** On every reader exit with `_UNLEASHED_BASE_OK=0`, `_UNLEASHED_BASE_RESOLVED` is the literal poisoned sentinel `/dev/null/unresolved-plugin-base` — never empty, never a value beneath which a path composes successfully — so an unguarded caller that concatenates and writes fails `ENOTDIR` at one fixed, greppable path. `_UNLEASHED_BASE_OK` is binary and is the ONLY sanctioned resolved/unresolved test, read as `[ "${_UNLEASHED_BASE_OK:-0}" = 1 ]` with unset treated as unresolved. No consumer infers whether the base resolved from `_UNLEASHED_BASE_SOURCE`, from `_UNLEASHED_POINTER_STATE`, or by comparing `_UNLEASHED_BASE_RESOLVED` against the sentinel string; in particular `_UNLEASHED_POINTER_STATE=none` is emitted by rule 3 (resolved), rule 4 (unresolved) and the HOME-unusable exit (unresolved), so it does not distinguish the two.

**RD-16 — Five copies, read path.** All five family files — `scripts/lib/paths.sh` and the inline copies in `context.sh`, `marker.sh`, `log.sh` and `agent-env-bridge.sh` — implement the identical reader: same store predicate, same composed entry predicate, same rule order, same enum. No reduced inline reader is permitted; `paths.sh`'s absence changes who computes the answer, never what the answer is. For the READ path, in every cell of the store matrix **the cell set AE-1 states — this rule does not enumerate it**, because two enumerations of one matrix is how the empty-authenticated and one-valid-plus-one-malformed cells came to exist in only one of them. With `paths.sh` present AND absent, all five must report identical `_UNLEASHED_BASE_RESOLVED`, `_UNLEASHED_BASE_OK`, `_UNLEASHED_BASE_SOURCE` and `_UNLEASHED_POINTER_STATE`, and each must source cleanly under `set -euo pipefail` in both bash and zsh in every cell. Publish-side equivalence is asserted across the four PUBLISHING copies only: `agent-env-bridge.sh` never publishes and reports `_UNLEASHED_POINTER_STATE=none` on its resolved path, so a matrix requiring identical state from all five over publish cells is prohibited.

**RD-17 — Reader never writes.** A reader never writes, never repairs and never deletes anything, on any exit including the resolving one — no second store is created, no entry is rewritten, no wrong-moded store is `chmod`'ed, no stale entry is reaped on any age or other heuristic, and no crash-orphaned `.pub.*` temporary is reaped (it is inert but accumulates). Recovery from `conflict` or `stale` is a human `rm` of the obsolete entry, discovered by listing the store.

### Publisher

**PUB-1 — Publish trigger and non-interference.** The publish side effect is reachable from exactly one branch of the resolver: step 1, i.e. `CLAUDE_PLUGIN_DATA` non-empty. It runs at source time, in every process that sets that variable and sources any of the four PUBLISHING family files — `agent-env-bridge.sh` is the fifth copy and never publishes, because PUB-3 makes it set `_UNLEASHED_PUBLISH_OK=0` before it sources anything, and PUB-2 makes that flag a precondition of any publish. The exception is stated here rather than left to the reader to reconcile: "any of the five" and "that file never publishes" were flatly contradictory. The four are `scripts/lib/paths.sh` and the inline copies in `scripts/lib/context.sh`, `marker.sh` and `log.sh`, and it runs only AFTER step 1 has already set `_UNLEASHED_BASE_RESOLVED` to the variable's value, `_UNLEASHED_BASE_OK=1` and `_UNLEASHED_BASE_SOURCE=host-env`. Step 1 itself never consults `HOME` and never fails. Step 2 (enumerate the store) and step 3 (sentinel) never publish. No outcome of the publish — success, skip, refusal, or failure of any kind — may change `_UNLEASHED_BASE_RESOLVED`, `_UNLEASHED_BASE_OK` or `_UNLEASHED_BASE_SOURCE`. The only variable the publish may set is `_UNLEASHED_POINTER_STATE`.

**PUB-2 — Publish preconditions.** A publish is attempted if and only if `_UNLEASHED_HOME_OK` is true AND `_UNLEASHED_PUBLISH_OK` is not `0`. `_UNLEASHED_HOME_OK` is computed once per process and is true iff `HOME` is non-empty and absolute, tested as `case "${HOME:-}" in /*) ;; *) esac`; every expansion of `HOME` on this path uses the `${HOME:-}` form, never a bare `${HOME}`, because the libraries are sourced under `set -u`. `_UNLEASHED_PUBLISH_OK` is tested as "not 0" (`[ "${_UNLEASHED_PUBLISH_OK:-1}" != 0 ]`), so an unset flag means authoritative and publication proceeds. If either precondition fails, the publish routine composes and opens NO `${HOME}`-rooted path at all: no ancestor creation, no `mkdir`, no `NAME_MAX` probe, no temporary file, no rename, no scan. A fixture that forces the `HOME`-unusable case must set `HOME=""` rather than unsetting `HOME`, because zsh repopulates an unset `HOME` from passwd while bash leaves it unset.

**PUB-3 — Non-authoritative shells never publish.** A shell whose `CLAUDE_PLUGIN_DATA` was substituted in from agent content rather than exported by the host is non-authoritative and must never leave a durable entry. Such a shell sets `_UNLEASHED_PUBLISH_OK=0` as the FIRST statement of its body — before it exports `CLAUDE_PLUGIN_DATA`, before it sources `paths.sh`, and before any inline resolution of its own — because the resolver publishes at source time. The only such shell in the tree is `scripts/lib/agent-env-bridge.sh`. A suppressed shell still performs the same three-step resolution the other four copies perform and establishes all four protocol variables (`_UNLEASHED_BASE_RESOLVED`, `_UNLEASHED_BASE_OK`, `_UNLEASHED_BASE_SOURCE`, `_UNLEASHED_POINTER_STATE`); its publish side effect is skipped in its entirety — no ancestor creation, no store creation, no temporary, no entry, no scan — and it reports `_UNLEASHED_POINTER_STATE=none`. Arm equivalence across the five copies asserts all four protocol variables; for `agent-env-bridge.sh` it is asserted on the READ path only, which is the only path this copy has. It reports `_UNLEASHED_POINTER_STATE=none` **on the resolved path only**; on its read path it runs reader rules −1..4 and reports whatever they assign, because arm equivalence requires all five copies to report the identical state in every read cell.

**PUB-4 — What a publish may write.** A publish creates or replaces **AT MOST ONE** durable file, and on the no-write `current` path it creates none — PUB-7 and N6-8 require zero writes when the existing entry already authenticates, and row 1's mtime case proves it. When a publish does write, the one durable path it may touch is: `${HOME}/.claude/unleashed-mail/bases/base.<key>`, where `<key>` is K(v), the injective key the encoder rule (Invariant P) defines over the bytes of THIS process's own absolute base value v. Its content is that absolute path followed by exactly one `\n` and no other bytes, and its mode is exactly 0600. It is written by creating a temporary file in the SAME directory as the entry and then renaming that temporary onto the entry path with `mv`. The temporary is created with mode 0600 at creation time — a mode-setting creation, never a bare redirect under the ambient umask — because `mv` preserves the temporary's mode and an entry at 0644 or 0664 fails the publisher's own authentication check. The temporary's NAME, its `<uniq>`, and the prohibition on `$$` alone are TMP-1's and are not restated here. The `.pub.` prefix places every temporary outside the `base.*` glob by construction, so no reader ever enumerates one; a temporary orphaned by a killed publisher changes no resolution and no reported state, and is never reaped automatically. A publisher touches no path in the store other than its own `base.<key>` and its own temporary: it never creates, modifies, renames or deletes another publisher's entry, and never writes state on another publisher's behalf. Two publishers holding the SAME base value converge on one entry name; that is safe and must not be guarded against, because the bytes are identical and `mv` is atomic.

**PUB-5 — Store and ancestor creation — see ST-2, which states it.** The publisher's only addition is WHERE the creation sits in its order: **the `NAME_MAX` probe comes FIRST (PUB-9's E3, before anything is created), and the store and ancestor creation follows it (E4)** — which is why NM-1 measures against the nearest EXISTING ancestor, the store not existing yet at that point. Its failure is E4. *(Round 82, codex: round 80b's dedup of this rule asserted the opposite order — creation before the probe — which PUB-6 and PUB-9's E3-before-E4 both contradict, made E3's "nothing written" false once ancestors existed, and rendered NM-1's nearest-existing-ancestor branch dead. Reducing a rule to a reference is not free: the sentence that replaces it can still assert something new and wrong.)* The store path, the `mkdir -m 700` form, the prohibition on `-p` and on `mkdir`-then-`chmod`, the order of ancestor creation and the acceptance test for an ancestor that already exists are all ST-2's and ST-4's and are not restated here. *(Round 80: this rule and ST-2 stated the same obligation in different words, which is how PUB-5 came to accept an ancestor on three clauses where ST-4 requires five. A mechanical sweep for rules sharing rare phrasing found this pair and nine others; the arms had been finding them one per round.)*

**PUB-6 — Temp-name NAME_MAX pre-check — see NM-1, which states it.** The publisher's only addition is WHERE the check sits in its order: it is PUB-9's exit E3, evaluated before any name is composed and before any file is created. The trigger, the measurement and the failure behaviour are NM-1's and are not restated here — this rule's own trigger read "before creating any file", which is strictly WEAKER than NM-1's "before it composes or creates either entry name", so an implementer following it could compose a name NM-1 forbids composing.

**PUB-7 — Write-or-skip decision.** **Precondition, evaluated first: the publisher publishes NOTHING unless its own base value satisfies the target clauses **in full and exactly as TGT-1 states them**, **AND the TARGET CHAIN itself authenticates — every component of the path the value names, under PCH-1's walk, ANCHOR-1's ownership rule and the ACL clauses, the last SUBJECT TO THE SAME ABSENT-ENUMERATOR CARVE-OUT AUTH-1 clause (h) states.** Without that scoping this check refuses at E2 on an enumerator-less platform — one exit EARLIER than E4, where round 74 had just placed the exemption — so the round-74 fix would have moved the failure rather than removed it. *(Round 76, kimi H1 and codex concordantly.)* Those are precisely the clauses of AUTH-1 that are properties of the VALUE rather than of the entry file, so evaluating them here is the SAME predicate applied to the chain it already covers, not a second predicate and not a prospective-entry variant — both of which AUTH-1 forbids. *(Round 74, codex: without this, a value naming an existing directory beneath a GROUP-WRITABLE component passed TGT-1, the publisher wrote its entry, the post-scan then failed PCH-1 and reported `stale`, and ST-8 forbade removing what had just been written — a durable entry that every reader refuses forever and nothing may delete, created by a publisher obeying the rules. SHARED-1 requires the complete predicate BEFORE leaving an entry in place; that was unsatisfiable while the only pre-write check was TGT-1.)* This clause does not enumerate TGT-1's members, and no clause anywhere may: the enumeration it used to carry went stale the moment TGT-1 gained the newline exclusion, and an implementer following the stale list would have published a multi-line durable entry that every reader then refuses.** A value failing any of those is not publishable, no entry is written, no key is derived, and the state is `failed`. *(Round 58, codex #5: TGT-1 said such a publisher writes nothing while this rule said it writes whenever no authenticating matching entry exists — for a relative or NUL-bearing value both applied and they disagreed about whether a file appears on disk. The precedence is now explicit and TGT-1 is evaluated before the write-or-skip test, not alongside it.)* Given a publishable value, the publisher writes its entry UNLESS the file already at its own `base.<key>` both (a) satisfies the COMPLETE follower predicate — the entry clauses (regular non-symlink file, euid-owned, mode 0600, exactly one line, name↔content), the clauses on every component of the entry's own ancestor chain, the content clauses and the clauses on every component of the target's chain, and the platform ACL clauses — applied exactly as a reader applies them, and (b) holds a single line equal to this process's own base value. When both hold the publisher performs no write; otherwise it writes. That predicate is ONE shell function called by both the publisher and the reader, and the publisher runs it on BOTH paths, the no-write path included, against the entry it is about to leave in place. A weaker type-and-content test is forbidden: a REGULAR NON-SYMLINK entry at mode 0644, or one whose content is a relative path, is repaired by republication, never skipped. A `base.<key>` that is a symlink or a directory is refused by ST-7's precondition instead — nothing is written and the state is `failed` — because `mv -f` cannot safely repair those shapes. The predicate may not depend on any variable that differs between publisher and reader, so publisher and reader reach the same verdict in different environments. ONE EXCEPTION: on a platform where no ACL enumerator exists at its absolute path, the publisher skips the ACL clauses FOR ITS OWN ENTRY — both in this write-or-skip decision and in the post-scan re-verification of that same entry — while every foreign entry the publisher scans, and every reader, still refuses when the ACL condition is unevaluable. This clause imposes only the OBLIGATION to authenticate; it assigns no `_UNLEASHED_POINTER_STATE` value.

**PUB-8 — Publish-then-scan ordering.** The publisher completes its write-or-skip decision FIRST and only afterwards scans the store. Scanning before publishing is forbidden: publishing first puts every process's own entry into the set that process observes. One residual is accepted: under strict interleaving, publisher A may publish and scan before publisher B publishes at all, so A's process reports `created`; the conflict is nonetheless durable in the file set, so every later process of either install reports it. Nothing is recorded, marked, or handed to another process for a conflict to survive — conflict is a property of the store directory's contents, derived at resolution time. There is no `CONFLICTED` wire form, no stickiness rule, no preserve-the-marker precondition, and no operator-recovery-by-deletion protocol.

**PUB-9 — Ordered publish exit mapping.** Every exit of the publish routine maps to exactly one `_UNLEASHED_POINTER_STATE` value. The exits are evaluated in this order, first match wins: (E0) `_UNLEASHED_PUBLISH_OK` is `0` — the publish is skipped entirely, nothing is composed or opened, no scan → `none`; (E1) `_UNLEASHED_HOME_OK` is false — no `${HOME}`-rooted path is composed or opened at all, no scan → `failed`; (E2) this process's own base value is NOT PUBLISHABLE — it fails a clause of TGT-1, or its TARGET CHAIN fails to authenticate (PUB-7), neither of which this exit enumerates, for the reason PUB-7 gives one clause above — so no key is derived, nothing is composed or opened under the store, and no scan runs → `failed`; (E3) the `NAME_MAX` budget for `.pub.<pid>.<uniq>.<key>` cannot be satisfied — either it is exceeded, or `/usr/bin/getconf` is absent, exits nonzero, or emits anything that is not a decimal number, which FAILS CLOSED and is not treated as an unlimited budget — nothing written → `failed`; (E4) a missing ancestor cannot be created, or `bases/` or an ancestor of it fails ST-3 or ST-4 — whether it pre-existed or this publisher has just created it, since a freshly created store can inherit a default ACL that fails ST-3 → `failed`. **E4 evaluates the store chain in THIS ORDER, and no `mkdir` precedes the validation of what already exists.** (i) Authenticate every EXISTING component of PCH-1's walk from `/` downward — ACL clauses included — BEFORE creating anything; a failure here creates NOTHING, which is what ACL-6 already requires of every refusal path. (ii) Create each missing component in turn (ST-2), authenticating each immediately after creating it — **and authenticate, with the same no-follow chain predicate, any component that is PRESENT at this step but was ABSENT at (i)** (it appeared in between; `-d` follows a symlink, so without this a same-uid process that planted `.claude` as a symlink to an outside directory after (i) had the next component's `mkdir` run THROUGH the link — a directory created outside the store by the refusal path, before (iii) noticed; PR #67, codex pass 13 — reproduced, both shells; row 171). (iii) Authenticate the completed chain. **Validation of the existing prefix before the first `mkdir` is the load-bearing step**: with `HOME=/safe/home` a symlink to `/victim` and `.claude` absent, an implementation that creates first and validates afterwards runs `mkdir "$HOME/.claude"` THROUGH the symlink, leaves `/victim/.claude` behind, and only then reports `failed` — a write outside the store performed by the refusal path itself. *(Round 90, codex: E4 required the complete-chain verdict only before an ENTRY was written, and explicitly permitted created ancestors to remain, so the order above was permitted but not required and two conforming implementations differed on whether `/victim/.claude` appears.)* *(Round 88, codex: ST-4 and rule −1 bounded the store chain at `${HOME}` while AUTH-1 requires `/` downward, so a `/Users` carrying a foreign mutating `allow` ACE passed E2 and E4, the publisher wrote its entry, and the post-scan COMPLETE authentication then rejected that same ACE and reported `stale` — with ST-8 forbidding removal. A durable entry every reader refuses forever, created by a publisher obeying the rules: the identical shape round 74 fixed for the TARGET chain, surviving on the STORE chain because its lower bound was written in a different rule.)* **NO ENTRY and no transient is written; ancestors this publisher already created are LEFT IN PLACE.** ST-2 creates them one at a time, so a failure at `unleashed-mail` after `.claude` succeeded, or a store rejected after creation for an inherited default ACL, necessarily leaves the earlier directories — and ST-3/ST-4 forbid repairing or removing them. Those directories are `0700` and euid-owned, so leaving them is harmless and the next run reuses them; claiming "nothing written" was simply false, and no implementation could have satisfied it. *(Round 84, codex.)* **This check omits the ACL clauses under EXACTLY the condition AUTH-1 clause (h) states and no other: the platform has NO ENUMERATOR AT ALL.** A present enumerator that exits non-zero, prints nothing, or prints an unparseable ACE line REFUSES here, as everywhere else, because it may be failing precisely because the component is hostile. **And the carve-out extends to the STORE and its ancestors, not only to the publisher's own entry file** — stated because AUTH-1(h) is worded in terms of "its own entry" and this exit authenticates a directory: without the extension an enumerator-less runner fails at E4 and never reaches PUB-7, so the exemption both rules rely on would be dead code. *(Round 74, codex: rounds 70 and 72 narrowed the word in ACL-4 and then in AUTH-1(h) and left it wide HERE, so following E4 accepted a component that ACL-4 refuses — the third round in which this one exemption was fixed in some of its sites and not all.)* (E5) no unique temporary name can be obtained within TMP-1's three TOTAL attempts — a REFUSED exclusive create whose name is then PRESENT is a lost race and ONE consumed attempt, so three of them are this exit (mutant row 154) — nothing written → `failed`; (E6) the temporary's creation or write, or the `mv`, fails for any reason — INCLUDING a refused exclusive create whose name is ABSENT afterwards (`ENOSPC`, `EROFS`, `EACCES`: a CREATION failure, never a consumed attempt — mutant row 155; P-4 states how the primitive tells the two refusals apart), INCLUDING ST-7's refusal to repair a `base.<key>` that exists and is not a regular non-symlink file, **and including a transient that was CREATED SUCCESSFULLY but whose mode read back is not exactly 0600** (P-4: a POSIX default ACL supplies permissions `umask` does not mask, so this is reachable on a store ACL-3 accepts). In that case the publisher ATTEMPTS to remove its transient (best-effort, ST-7), writes no entry, and reports `failed` — a failed removal does not change the state, the diagnostic count, or anything a reader sees → `failed`. *(Round 84, codex: P-4 stated the readback obligation and no rule in §4.2a-S carried the resulting exit, so enum totality was not DERIVED — an implementer had to infer from §4.2a-P prose which exit it belonged to, which is precisely what §4.2a-S's completeness claim denies.)*; (E7) otherwise the write-or-skip has completed, and the publisher scans the store and applies the ORDERED post-scan exits below. E1 through E6 are stated in execution order and all map to `failed`, so their relative order does not affect the mapping; E0 outranks E1, and E7 is reachable only when no earlier exit matched. *(Round 61: E2 was missing. PUB-7 states the TGT-1 precondition and gives it the state `failed`, but this list — which calls itself exhaustive — did not carry it, so the one exit that writes nothing and derives no key was the one an implementer building from the list would not have.)* The post-scan exits are themselves ORDERED, first match wins: (P1) this process's own entry is missing → `failed`, whether or not this process wrote it; (P2) else any remaining entry, this process's own included, fails authentication → `stale`; (P3) else two or more entries authenticate → `conflict`; (P4) else `created` if this process wrote the entry, `current` if it skipped the write. The scan applies the same ordered reader rules the reader applies, including the vanished-entry skip: an entry enumerated but gone when opened and NOT a symlink is skipped and is not an entry, so it is never treated as malformed; a `base.*` symlink, dangling or not, is a failing entry. A publisher does not refuse — it has already resolved — it reports what it saw.

**PUB-10 — Pointer-state enum and totality.** `_UNLEASHED_POINTER_STATE` ∈ {`created`, `current`, `conflict`, `stale`, `failed`, `none`} and nothing else. It is set exactly once per process: by the publish routine on the step-1 path, and by the reader on the step-2/step-3 path. Totality is DERIVED, not asserted: every exit path of the publish routine AND of the reader is enumerated, each mapped to exactly one value, and the mapping checked against this declared list; an exit with no value, or a value not declared, fails verification. Consumers partition the enum as `conflict`/`stale`/`failed` versus `created`/`current`/`none`: the SessionStart notice emits one non-blocking `additionalContext` line, still exiting 0, when the value is `conflict`, `stale` or `failed`, and stays silent on `created`, `current` and `none`.

**PUB-11 — Publish-path output and diagnostics.** **The suppression covers INCIDENTAL output only, and three things are exempt from it by name.** The publish's MUTATING commands — the ancestor and store `mkdir`s and the `mv` — have both streams redirected to `/dev/null` and their outcome observed through their exit status, never their output. **They are ALSO invoked BY ABSOLUTE PATH — `/bin/mkdir`, `/bin/mv`, and ST-7's cleanup `/bin/rm` — never through `PATH`, exactly as every read probe already is.** *(Round 106: this one sentence named the read probes WITH their absolute paths and the mutating commands WITHOUT, and ACL-5, NM-1, ACL-7 and mutant row 67 exist precisely to keep `PATH` out of the predicate. The consequence of leaving it in for the writes is worse than for the reads and it is DURABLE: ST-3 requires `bases/` to be exactly `0700` and forbids ever repairing or deleting it, so a `mkdir` that did not apply `-m 700` creates a store EVERY READER REFUSES FOREVER, recoverable only by an operator `rm -rf` — the same durable-poison shape PUB-9 E4's round-88 note records. `mv` carries the second instance: PUB-13's no-torn-read guarantee rests on the rename being atomic, and a `PATH`-supplied `mv` that copies-then-unlinks satisfies the command name and breaks the guarantee.)* **The transient-cleanup `rm`** that ST-7 and E6 require is a MUTATING command and is suppressed with the others; its exit status is examined and a failed cleanup emits NOTHING, because the exit has already emitted the one diagnostic PUB-11 allows and a second line would break the one-line rule. EXEMPT: **(a) the captured stdout of the read-only probes**, because it IS the answer — `/usr/bin/uname -s`, `/usr/bin/getconf`, `/usr/bin/stat`, `/bin/ls -lde`, `/usr/bin/getfacl`, **`/usr/bin/id -un`** and **`/usr/bin/dsmemberutil getuuid -U`**, whose stdout P-3a needs to identify the ACL principal by name and by UUID — suppressing it empties the username, every `allow` ACE for the effective user then reads as foreign, and valid chains refuse; **(b) the transient's own content**, which P-4 writes THROUGH the descriptor its exclusive create returned — a redirect to the transient and not to `/dev/null`; the create-and-write subshell's OWN stdout and stderr ARE redirected to `/dev/null`, so a builtin's error-path flush (measured: bash's `printf` re-emits an unwritten value to the restored stdout after `EFBIG`) can never reach the caller's streams; and **(c) the one diagnostic a `failed` exit emits**, which the rest of this rule requires. *(Round 94, codex: taken literally the previous wording discarded the stdout every primitive exists to capture, forbade writing the entry's content, and contradicted this rule's own next sentence about the diagnostic — no implementation could obey it.)* **Every publish exit that reports `failed` emits exactly one bounded line on stderr naming which exit it was; every other publish outcome is silent.** So PUB-9's E1 through E6 AND the post-scan exit P1 — every exit that reports `failed`, pre-scan or post-scan alike — each emit one line — the `NAME_MAX` line additionally naming the length — while `created`, `current`, `conflict`, `stale` and `none` emit none and reach a human only through `_UNLEASHED_POINTER_STATE` and the SessionStart notice; in particular a publisher that observes `conflict` or `stale` emits no diagnostic, because the one-diagnostic-per-refusal rules are reader rules and a publisher has already resolved. The per-process cardinality is unchanged at one line, because the resolver runs once per process and a failing publish takes exactly one exit. *(Round 61: this rule said the `NAME_MAX` line was the ONLY diagnostic the publish path emits, while its own next sentence — `stderr == ""` may be asserted only where the publish ALSO succeeded — presumes every failure speaks, and AE-2 required one line from every `failed` cell. Under the narrow reading a publisher whose store is at the wrong mode fails on every invocation and says nothing anywhere, which is the silent no-op this ticket exists to remove.)* Consequently `stderr == ""` may be asserted only in resolved cells whose publish side effect ALSO succeeded, never globally. The exactly-one-diagnostic-per-process rule governs the unresolved-base diagnostic — guarded by the shared `_UNLEASHED_BASE_OK` flag so it holds with `paths.sh` absent — and is unaffected by any publish outcome.

**PUB-12 — Harness HOME sandbox.** Because step 1 makes every process that sets `CLAUDE_PLUGIN_DATA` a publisher, a harness that exports that variable while inheriting the developer's `HOME` writes a durable entry into the developer's real store. It does not overwrite the machine's own entry: it ADDS a second entry under a different key, naming (in the isolated-harness case) a temporary directory the harness itself deletes on exit, so that entry then fails authentication and every later reader refuses the WHOLE store as `stale`, permanently, until a human removes it. Each affected harness must therefore set `HOME` to its own temp root BEFORE sourcing any family file. The affected harnesses are exactly `scripts/test-hooks.sh`, `scripts/tests/test_reviewer_roster.py` and `scripts/tests/test_shell_primitive_drift.py`; the last sets `HOME=/probe` and so does not inherit the developer's home, but still needs a temp `HOME` so a publish cannot create `/probe`. Every temp `HOME` and every target must be canonical — resolved through `realpath` or `pwd -P` before use — because target authentication rejects symlinked components. The proof obligation is **HAR-1's, stated there and referenced here**: running the harness leaves the DEVELOPER's real store — the path captured before the sandbox replaced `HOME` — byte-identical, every entry and the set of entries. **This rule states no path of its own.** *(Round 80, agy and codex concordantly: round 78 corrected HAR-1 and left this sentence naming `${HOME}/…`, which after the reassignment is the SANDBOX a publishing cell must write into — so the two authoritative rules demanded opposite things. Two statements of one postcondition is what produced that, so there is now one.)* No `HOME` assignment exists in any of the three files today; this is implementation work, not a property that may be relied on.

**PUB-13 — Same-base concurrent publish case.** N6 carries an executable same-base CONCURRENT-PUBLISH case, in addition to the mutant that reverts the temporary name to `$$` alone: two publishers holding the same base value, racing on the one entry name that value produces, must converge on identical bytes — no torn read and no lost write, **with the absence guarantee exactly as ST-7 scopes it: no reader that has ALREADY SEEN the entry observes it absent.** A reader arriving before either publisher's first rename legitimately counts zero entries and takes rule 4 (`none`); requiring otherwise would demand that a never-created entry be continuously present. *(Round 84, codex: round 82 scoped ST-7 and left this rule absolute — the same half-family shape, in the round after the one that fixed it.)*

### Consumers and proof

**CON-1 — Consumer unresolved-base control flow.** A consumer whose control flow diverges when the base is unresolved branches on `[ "${_UNLEASHED_BASE_OK:-0}" = 1 ]` — `1` resolved, `0` unresolved, UNSET treated as unresolved so a consumer running without the libraries fails closed. No consumer inspects a path and none compares against the sentinel string. The consumers that branch, with their required behaviour on an unresolved base: `reviewer-roster.sh` — fail closed, classify reviewers `UNATTRIBUTED` and exit 3; `stop-quality-marker-gate.sh` — guard the whole script at entry; `capture-reviewer-verdict.sh` — skip the capture entirely and exit 0, attempting no write and not failing the reviewer's own run; `pre-commit-checks.sh`, `swift-lint-check.sh`, `swift-build-verify.sh` — skip persistence while keeping primary behaviour, output and exit code (`swift-lint-check.sh` still emits its model-visible block, `swift-build-verify.sh` still emits its advisory, `pre-commit-checks.sh` still honours its final exit code); `precompact-snapshot.sh` and `sessionstart-restore.sh` — skip the snapshot write and the restore; the `agents/swift-reviewer.md` fence — perform no filesystem read at all and emit `NO CAPTURE (unresolved)` for EACH reviewer. Consumers already correct from the writing primitives' no-op-and-return-0 contract take NO per-script guard: `build-failure-log.sh`, `stop-failure-log.sh`, `permission-denied-log.sh` and `capture-reviewer-round-start.sh`. Suppressing persistence never changes a consumer's primary behaviour or exit code; the single exception is `sessionstart-restore.sh`, whose output does change — it emits one non-blocking `additionalContext` line and still exits 0. The `SessionStart` notice is **not** part of this rule: its trigger is `_UNLEASHED_POINTER_STATE ∈ {conflict, stale, failed}` per SS-1, and is never a predicate on this hook's own `_UNLEASHED_BASE_OK`.

**CON-2 — Amend pre-commit MAJ-6 comment.** The same change amends the MAJ-6 comment at `scripts/pre-commit-checks.sh:14-18`. Under step 2 that git hook's marker writes become visible to the gate with no export, so its unresolved-base conditional stops firing, and both halves of the existing comment are false: `marker.sh` does not "fall back to ~/.claude/unleashed-mail", and exporting `CLAUDE_PLUGIN_DATA` in the git-hook environment is no longer needed to wire the writes up.

**FAM-1 — The five family files.** The D″ resolution is implemented in exactly five shell files, which change together: `scripts/lib/paths.sh`, `scripts/lib/context.sh`, `scripts/lib/marker.sh`, `scripts/lib/log.sh`, `scripts/lib/agent-env-bridge.sh`. Each of the five carries a resolver definition, so there are FIVE resolver definitions, not four. Test harnesses — `scripts/tests/test_plugin_state_base.py`, `scripts/tests/test_shell_primitive_drift.py`, `scripts/test-hooks.sh`, `scripts/tests/test_reviewer_roster.py` — are a separate list and are never family members; a Python file cannot be shell-sourced and no obligation quantified over family files applies to one. Any obligation asserted "per family file" is asserted five times, once per file, in both bash and zsh; a passing result in one file or one shell is not evidence about the other four.

**FAM-2 — Four protocol variables.** Every family file establishes, at source time in the sourcing shell and before any command substitution, all four protocol variables: `_UNLEASHED_BASE_RESOLVED` (the resolved absolute base, or the literal sentinel `/dev/null/unresolved-plugin-base`), `_UNLEASHED_BASE_OK` (`1` when resolved, `0` when the sentinel is in force), `_UNLEASHED_BASE_SOURCE` ∈ `host-env|pointer|unresolved`, and `_UNLEASHED_POINTER_STATE` ∈ `created|current|conflict|stale|failed|none`. They are plain shell variables in that shell, set once, never re-derived per call, and never first assigned inside a command substitution (a value assigned there lives in the subshell and is gone on return). Whichever family file is sourced first establishes them; every later file skips re-derivation because `_UNLEASHED_BASE_PID` equals `$$` — **the once-per-process key is PROCESS IDENTITY, never the presence of a protocol variable.** A protocol variable can be inherited from an environment while its functions and its meaning are not: measured, a child shell that inherited `_UNLEASHED_BASE_OK=1` alone skipped resolution and `marker_dir` returned `/.state`, the ROOT path D′ exists to prevent; an inherited `_UNLEASHED_STATE_LOADED=1` made the machinery loader report the four libraries present in a shell where `_unleashed_read_store` was undefined; an inherited `_UNLEASHED_PATHS_SH_LOADED=1` made `paths.sh` define nothing. So "resolved in this SHELL INSTANCE" is THREE things together: `_UNLEASHED_BASE_PID = $$`, the marker function `_unleashed_resolved_in_process` (defined at resolution, never at definition), and — checked once per SOURCING — the READONLY ATTRIBUTE on `_UNLEASHED_BASE_INSTANCE`, which no environment carries: `exec` keeps `$$`, an `allexport` wrapper carries every variable across it, and in bash `set -a` carries every FUNCTION too, so after such a wrapper an exec'd hook held a matching pid, the marker function and the wrapper's stale base (PR #67, codex pass 11 — reproduced); `declare -p`/`typeset -p` show `-r` only in the instance that set it (measured: `declare -rx` becomes `declare -x` across exec, `export -r` becomes `export`; a subshell keeps it), so a value present without the attribute is inherited and the inherited resolution is discarded before anything trusts it. **Only the FLAG LETTERS are read** — everything from the first ` _UNLEASHED_BASE_INSTANCE` onward is stripped before the test, because the VALUE is attacker-supplied and a whole-line glob let a value of `r _UNLEASHED_BASE_INSTANCE=` supply both the `r` and the name, so an inherited `declare -x` passed as READONLY (codex sweep after pass 14 — reproduced; row 176). **Discarding an inherited stamp is errexit-safe** (`|| :` on both unsets): zsh's `unset -f` returns 1 for a function that is not defined, and under `set -e` / `setopt err_return` that killed the sourcing of every copy the moment the stamp arrived through the environment (same sweep — reproduced; row 175). **The stamp is set once, only when the variable is absent, and globally** — `readonly _UNLEASHED_BASE_INSTANCE=1` guarded by `[ -z "${_UNLEASHED_BASE_INSTANCE+set}" ]`, and `typeset -g -r` under zsh: bash treats a repeated `readonly X=1` on a readonly `X` as a FATAL assignment error under `set -e`, even behind `|| :`, so the bridge's legitimate re-resolution of an already-stamped instance exited the sourcing shell (codex pass 14 — reproduced), and a bare `readonly` INSIDE a function is function-local in zsh, so the resolver's stamp vanished at return and the zsh arm never held the attribute (measured, same pass; row 173). "Absent" is the right test because the sourcing-time check has already discarded any inherited value. **The machinery is RE-SOURCED from the four library files beside the loader whenever they are readable** — the same replace-imports rule the definition block follows — and "the four entry functions are present" (`command -v` on `_unleashed_key`, `_unleashed_auth_chain`, `_unleashed_read_store`, `_unleashed_publish`) is consulted ONLY where those files are not readable (a copy of the resolver placed away from its libraries; an install always has them). Keyed on presence alone the loader trusted an imported namespace: bash `set -a` exports functions, so a parent exported a tampered `_unleashed_read_store` beside genuine names, the trusted resolver definitions were reloaded, the loader skipped all four libraries, and the import set `_UNLEASHED_BASE_RESOLVED=/attacker` (codex pass 14 — reproduced; row 172). **`paths.sh`'s definitions are UNCONDITIONAL — sourcing it always (re)defines every function it owns, and every family file sources it unconditionally when readable and defines its own fallback state test unconditionally.** **The DIRECTORY every copy sources from is derived with NO EXTERNAL COMMAND** — a parameter expansion (`${BASH_SOURCE[0]:-$0}`, `${x%/*}`) and the builtins `cd -P`/`pwd -P`: `dirname` is resolved through PATH, and the parent that exports a tampered function set chooses PATH too, so with `/usr/bin` off it the directory fell back to the caller's cwd, the four libraries "were not readable" although they sit beside the file, and the loader's presence fallback trusted the imported machinery — `_UNLEASHED_BASE_RESOLVED=/attacker` in all five copies (codex sweep after pass 14 — reproduced; row 174). Every guard tried in this position trusted something an environment can carry: a flag (pass 7), one function (`export -f`, pass 11), and "the complete API is present" — which bash `set -a` also satisfies, because it exports every function defined while it is active, so a child inherited all six names WITH AN ATTACKER'S `unleashed_resolve_base` and the guard skipped the definitions and the eager call ran the inherited code (codex pass 12 — reproduced: `_UNLEASHED_BASE_RESOLVED=/attacker`). A present namespace is never proof that this library populated it; redefinition is idempotent and cheap, and it replaces an imported copy with the file's own definition. The eager resolution runs after the definitions, fork-free when this instance has already resolved. **The bridge discards this instance's resolution when the value it establishes DIFFERS from the environment the current resolution was made under** (`_UNLEASHED_BASE_ENV`, recorded beside the pid stamp by every copy), because establishing the environment's base is its whole job: sourced after another resolver had run, it exported the fence's value while the guard kept the earlier base (codex pass 12 — reproduced). Only a differing value invalidates — an unconditional re-resolution doubled the ACL walk whenever the bridge was sourced beside another resolver with the same environment, and row 92 (BUD-1) caught it. The resolver RESETS `_UNLEASHED_BASE_DIAGNOSED` on entry: it caches only on state it sets itself. *(PR #67, codex passes 7, 11, 12 and 14 and its pre-push sweep; mutant rows 156–158, 166, 167, 170, 172–176.)* Consumers detect the unresolved state only as `[ "${_UNLEASHED_BASE_OK:-0}" = 1 ]`, treating unset as unresolved; no consumer branches on `_UNLEASHED_BASE_SOURCE`, and no consumer string-compares against the sentinel text.

**FAM-3 — Absent paths.sh changes nothing.** `paths.sh`'s absence may change WHO computes the answer, never WHAT the answer is. Each of the other four family files carries its own COMPLETE inline copy of the three-step resolution and establishes all four protocol variables with values identical to those `paths.sh` would have produced for the same environment and store. A reduced inline fallback is forbidden in every one of them, `agent-env-bridge.sh` included, and no file may abort, error or fail closed because `paths.sh` is missing — each guards the source with `[ -r … ] &&` and takes its own inline path instead.

**FAM-4 — The agent-env-bridge contract.** The agent fence sources the bridge as exactly `source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/agent-env-bridge.sh" "${CLAUDE_PLUGIN_DATA}" "${CLAUDE_PLUGIN_ROOT}"` — both exact braced tokens, both in agent content, which is the only place and the only form Claude Code substitutes. The bridge takes `$1` = the data value and `$2` = the plugin root, and its body runs in this order: (1) `_UNLEASHED_PUBLISH_OK=0`, before anything else and before sourcing `paths.sh`, because `paths.sh` publishes at source time; (2) `export CLAUDE_PLUGIN_DATA="${1-}"`, preserving an empty value rather than unsetting it; (3) source `"$2/scripts/lib/paths.sh"` only under `[ -z "${_UNLEASHED_PATHS_SH_LOADED:-}" ] && [ -r "$2/scripts/lib/paths.sh" ]`; (4) if `[ -z "${_UNLEASHED_BASE_RESOLVED:-}" ]`, run the complete three-step resolution inline — a non-empty `CLAUDE_PLUGIN_DATA` yields that value with `_UNLEASHED_BASE_OK=1` and `_UNLEASHED_BASE_SOURCE=host-env`; an empty or unset one enumerates the store and applies the ordered reader rules −1 through 4 (NOT 0 through 4, so the store-authentication rule is not skipped), reaching the sentinel with `OK=0`, `SOURCE=unresolved` and the single diagnostic only when that resolves nothing. Empty and unset `$1` take the same branch; that identity is the only conditional the bridge does not need. This copy never publishes and reports `_UNLEASHED_POINTER_STATE=none` **on its resolved path only**; on its read path it runs reader rules −1..4 and reports whatever they assign, because arm equivalence (AE-1) requires all five copies to report the identical state in every read cell. *(An unscoped "every path" makes the two-authenticating-entry cell demand both `conflict` and `none`, which no implementation can satisfy.)*

**FAM-5 — Source-time safety rules.** **(0a) EVERY HELPER'S SCRATCH VARIABLES CARRY THAT HELPER'S OWN PREFIX.** A POSIX shell function has no locals, the family files are SOURCED into a consumer's shell, and §4.2a-P states the primitives as fragments that §7 assembles — so every helper shares one namespace with every other helper AND with the consumer. **The two arms of a two-arm primitive must not differ in which names they touch**, because a collision only one arm has is a divergence no single-arm test can see: measured, naming P-2's bash-arm scratch the same as the chain walk's loop variable made bash REFUSE and zsh RESOLVE the identical real chain, with every per-component fact identical in both — the zsh arm uses the `zstat` builtin and never touches that name. Mutant row 143. **(0) EVERY STRING EXPANSION IN A CONCATENATION IS BRACED — `out="${out}${c}"`, never `"$out$c"` followed by a literal `[`.** In zsh `$var[` is ARRAY SUBSCRIPTING, so the obvious accumulator spelling `out="$out[$c]"` is `X[/]` in bash and a FATAL `bad math expression` in zsh (measured, §4.2a-P P-10). It is stated here, in §4.2a-S, because it binds every family file rather than one primitive, and a rule that lives only in §4.2a-P is not a rule this section governs. The remaining five are enforced in every family file, because every new command runs at source time in a shell that may be under `set -euo pipefail`: (1) no new command appears as a bare statement — each is inside an `if`/`&&` condition or terminated with `|| :`; (2) the entry read applies its `< "$_f"` redirect to a brace GROUP containing the reads, with `2>/dev/null` on the enclosing group, because in zsh no redirect ordering on the inner command suppresses an open failure; (3) every read target is pre-initialised and every expansion of it uses `:-`, because a failed redirect leaves the variables unset and an unguarded expansion kills the sourcing shell in both bash and zsh — rule (1) alone is not sufficient; (4) the store scan is wrapped in `setopt local_options no_nomatch` inside the scanning function, guarded by `[ -n "${ZSH_VERSION:-}" ]` because `setopt` is a zsh builtin and bash's `command not found` would abort the sourcing shell in exactly the arm the guard protects, and because bash instead leaves an unmatched `"$d"/base.*` pattern literal, each enumerated `$_f` is skipped as vanished only on `[ ! -L "$_f" ] && [ ! -e "$_f" ]` — the `-L` test decided before the `-e` test — in BOTH arms; a bare `[ -e "$_f" ] || continue` is forbidden, because `-e` is false for a dangling symlink and would skip a hostile entry that must instead refuse the store; (5) each file sources cleanly under `set -euo pipefail` in both bash and zsh in every matrix cell.

**FAM-6 — One stderr diagnostic per process.** Exactly ONE unresolved diagnostic per process, emitted at source time, on STDERR only — never into the plugin's own log, a marker, or any other persistent record, since a persisted diagnostic is itself the persistence an unresolved base forbids. When the base does not resolve, that single stderr line is the only output. Each family file emits it only while it is THE file resolving this process — `_UNLEASHED_BASE_PID` not yet `$$` (FAM-2) — and only once within that resolution (`_UNLEASHED_BASE_DIAGNOSED`, which the resolver resets on entry and sets when it emits), so the cardinality also holds in the absent-`paths.sh` mode, where two or three family files sourced into one process would otherwise each take their own inline fallback: the first resolves and stamps `$$`, the rest skip. The guard is process identity plus the in-resolution flag, not the presence of a file and not a bare inheritable flag: the cardinality is a property of the resolution protocol rather than of the optional file, and a child process — which has its own `$$` — gets its own one diagnostic rather than inheriting silence. *(PR #67, codex pass 7: rewritten from "the guard is the shared flag", which an environment could carry.)*

**FAM-7 — N5 expansion allowlist.** `N5LexicalDrift.ALLOWLIST`, in `scripts/tests/test_plugin_state_base.py`, allowlists every permitted expansion of `CLAUDE_PLUGIN_DATA` **BY FILE** — the shipped test is `if rel in self.ALLOWLIST: continue` — and N5 fails on any expansion in the scan set outside an allowlisted FILE. It is NOT file-and-line, so appending a suffix to a line in an allowlisted file does NOT fail N5; any obligation resting on line granularity must be built, not assumed. *(Round 72: round 70 corrected this in the NOTE below and left the RULE stating the old design, citing `test_shell_primitive_drift.py:158-170` — real lines of the wrong file, which is why the citation read as verified. Fixing the note and not the rule is the failure this document has recorded against itself four times, and it happened again in the round that was fixing citations.)* The allowlist must carry all five resolver definitions — the expansion in `paths.sh` and the inline fallbacks in `marker.sh`, `log.sh` and `context.sh`, plus every `CLAUDE_PLUGIN_DATA` expansion in `agent-env-bridge.sh`'s specified body. **No line numbers are given: the four that stood here named comments and `# shellcheck source=` directives, not the expansions** (which are at `paths.sh:69-70`, `marker.sh:33-34`, `log.sh:31-32`, `context.sh:40-41` in this checkout), and the allowlist is keyed by FILE in any case, so a line pin here is both wrong and inert — plus the two agent-fence substitution sites, which are the injection points and cannot be removed, plus the `export CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}"` propagation lines, which compose nothing. The scan set includes the executable fences under `agents/**` and `skills/**`. Test fixtures are allowlisted by (file, reason) enumerated in the test source, never by a `tests/` glob. N5 additionally fails on any `${!` or `eval` anywhere in the scan set that is not itself allowlisted, because indirection through a runtime-assembled name cannot be decided statically.

**AE-1 — Arm equivalence matrix — THE ONE STATEMENT OF THE CELL SET.** The full store matrix runs against each of the five family files: {store absent; store present but unauthenticated — a refusing mode, owner or type; **store present, authenticated and EMPTY**; exactly one authenticating entry; one malformed entry; one unreadable entry; **one authenticating entry PLUS one malformed**; two authenticating entries, i.e. a conflicted STORE; an entry enumerated then vanished mid-scan} × {`paths.sh` present, `paths.sh` absent} × {bash, zsh}. **No other rule states this set.** Two rules did, with different members: the empty-authenticated store and the one-valid-plus-one-malformed cell appeared in only one of them, and each is some row's DISCRIMINATING fixture — the second is row 61's, which proves rule 1 outranks rule 2, and a suite built from the other list would never run it. In every READ cell all five files must report identical `_UNLEASHED_BASE_RESOLVED`, `_UNLEASHED_BASE_OK`, `_UNLEASHED_BASE_SOURCE` and `_UNLEASHED_POINTER_STATE` — all four, not three. Publish-side outcomes are compared across the other four files only, because `agent-env-bridge.sh` never publishes and reports `_UNLEASHED_POINTER_STATE=none`; that carve-out is stated with the matrix itself, so the oracle is satisfiable by a correct implementation. Each file must also source cleanly under `set -euo pipefail` in both shells in every cell. "Conflicted" is a property of the store (two authenticating entries), never a state an individual entry carries.

**AE-2 — Stderr asserted per cell.** Stderr is asserted per cell, never globally. `stderr == ""` is required only in cells that RESOLVE and whose publish side effect also SUCCEEDED. A cell that resolves but reports `failed` must assert exactly one line, per PUB-11 — for example the over-budget `NAME_MAX` path, which resolves from the variable, reports `failed` and emits one line naming the length. A cell that resolves from the variable and reports `conflict`, `stale`, `created` or `current` asserts EMPTY stderr: those are publisher outcomes and PUB-11 makes them silent. A READER cell that refuses — `conflict` or `stale` from the ordered rules, or the sentinel — asserts exactly one line. `conflict` and `stale` therefore carry DIFFERENT stderr oracles on the two paths, so each cell's oracle must name which path it is on; a single “conflict cells emit one line” assertion is wrong on the publish path. A blanket empty-stderr assertion across all cells is forbidden: resolution and publication are separate outcomes and each cell's oracle must say which one it is asserting.

**SS-1 — SessionStart notice predicate.** `scripts/sessionstart-restore.sh` emits exactly ONE non-blocking `additionalContext` line and still exits 0 when `_UNLEASHED_POINTER_STATE` is `conflict`, `stale` or `failed`, and stays silent when it is `created`, `current` or `none`. That six-value partition is the whole predicate; no other characterisation of the trigger is normative, and in particular "whenever the non-hook path will fail" is not — it is also true of `none`. **The predicate has NO source restriction and is evaluated BEFORE the hook's own filters:** it fires on every SessionStart source — `compact`, `resume`, `startup`, `clear` and any other — and whether or not snapshot restoration is switched off (`UNLEASHED_COMPACT_RESTORE=off` disables restoration, not the notice). The hook's source filter and kill switch used to `exit 0` above the notice, so `conflict`/`stale`/`failed` were invisible on exactly the `clear` sessions the manifest also invokes this hook for *(PR #67, codex pass 9 — reproduced; mutant row 165)*. The predicate reads `_UNLEASHED_POINTER_STATE` only; it is never a predicate on this hook's own `_UNLEASHED_BASE_OK`. This is the single §7 step-5 consumer whose output changes: every other consumer skips its snapshot read or write on an unresolved base and leaves the hook's own output and exit code untouched.

**BUD-1 — Source-time budget: DERIVED and MEASURED, never asserted.** The resolution's cost is whatever PUB-7, PUB-9, SHARED-1 and the reader rules require, and **this rule states no numeric cap of its own — no invocation-count cap and, since round 108, no wall-clock ceiling either** (the wall-clock is RECORDED, below, and gates nothing). What it requires is that the number be DERIVED from those rules' decision points and then MEASURED: §6's harness counts, per resolution and on each of the `created`, `current`, `conflict`, `stale`, `failed` and `none` paths, EVERY EXTERNAL INVOCATION THE RESOLUTION MAKES — enumerated here so that nothing counted lives only in a primitive: `/usr/bin/uname -s`, `/bin/ls -lde`, `/usr/bin/getfacl -pc`, **`/usr/bin/stat`** (P-2's per-component accessor on the BASH arm), **`/usr/bin/id -un`** and **`/usr/bin/dsmemberutil getuuid -U`** (P-3a's principal name and UUID, once each per resolution), and on the publish path **`/usr/bin/getconf`** (NM-1) and the mutating **`/bin/mkdir`, `/bin/mv` and `/bin/rm`** (PUB-11). **The derived count is PER SHELL ARM and the two arms differ by construction**: `zstat` is a zsh builtin and forks nothing, so the zsh arm's count omits every `/usr/bin/stat` the bash arm makes, and a single expected number would fail one arm or the other. The harness records the counts and fails if one exceeds what the rules derive. **A worked derivation, so that "derivable" is shown rather than asserted** — the Darwin `current` path, with `S` the store-chain component count and `T` the target-chain count: bash performs one `uname`, one `id -un`, one `getconf`, `4S+3T` `/bin/ls -lde` calls and `4S+3T+2` `/usr/bin/stat` calls; zsh performs the same except that every `stat` fork is absent. *(Round 114: codex supplied this derivation while showing the PROBE count was not yet derivable; a rule that requires a number to be DERIVED should show one being derived. Round 110's edit also left both copies of this sentence ungrammatical — "would fail one arm or the other invocations per resolution" — spliced mid-sentence and read past by two arms for two rounds.)* — a discrepancy is a defect in the implementation or in the derivation, and the harness does not say which. *(Round 110, codex: this list named three tools while P-2 states the budget counts bash's per-component `stat` and P-3a states it counts `id -un`, so redundant `stat` and `id` calls passed the gate that round 108 had just made the WHOLE gate. Narrowing the budget was the alternative; enumerating it is the choice, because every one of these is a fork on the hot path.)*
Two facts about the shape of that cost, because they are properties of the RULES rather than budget targets: a READER walks each chain once, since it authenticates each entry once and takes one exit, **and a READER resolution's wall-clock time is RECORDED, not gated: the harness measures it, prints it, and fails nothing on it. The GATE is the DERIVED INVOCATION COUNT this rule already requires.** *(Rounds 106 AND 108, codex both times, independently re-measured here both times — this rule is titled DERIVED and MEASURED, never asserted, and BOTH ceilings it has carried were asserted. Round 106 replaced 50 ms with 400 ms; round 108 removed the ceiling altogether. The rules derive AT LEAST 22 component evaluations for rule −1 plus two complete entry authentications, and the Darwin arms cost one `/usr/bin/stat` plus one `/bin/ls -lde` per component in bash and one `zstat` builtin plus one `/bin/ls -lde` in zsh. Measured on the reference machine, component walk ALONE, excluding the scan, the entry reads, the encoder and all parsing: **bash 131 ms at 22 components and 152 ms at 28; zsh 77 ms and 88 ms.** So 50 ms rejected every conforming implementation on BOTH arms — the gate failed the specification rather than the code, which is the one direction a verification gate must never fail. **A wall-clock CEILING cannot be stated at all, and round 106's 400 ms was the second attempt to state one.** "A two-entry store" does not bound either target's component count, and the cost is linear in components: codex measured 100 component evaluations at 520 ms in bash and 260 ms in zsh on this machine, and a valid two-entry store can exceed 100 combined evaluations before the scan, the reads, the encoder and any parsing. So 400 ms rejects a CONFORMING implementation exactly as 50 ms did, one store shape further out — and any number chosen without bounding the component count fails the same way. Bounding it would mean the specification constraining how deep a consumer may put its base, which it has no business doing. The wall-clock is therefore RECORDED and not gated, and the derived invocation count — which is a property of the RULES and not of the runner — is the whole gate.)* The wall-clock gate is stated here because §4.2a-S is what an implementer builds from and §6 is not. A PUBLISHER walks a chain more than once by construction, and the repeats are NOT redundant — each pair is separated by its own write or by another process's possible write, so **a verdict cached from before it is not evidence about the state after it**. On the no-write `current` path the rules derive **three TARGET-CHAIN validations and two COMPLETE OWN-ENTRY authentications**, which are different operations and must not be conflated: PUB-7's pre-write check validates the target clauses and the target chain and does NOT authenticate the entry file (there may not be one yet); the write-or-skip predicate and PUB-9's post-scan re-verification are each a complete AUTH-1 authentication, and each of those walks the target chain again as part of itself. *(Round 86, codex: this rule previously called all three "authentications of the publisher's own entry", which is two different call graphs under one name — the harness would have had no unambiguous expected count and could have accepted a spurious own-chain walk or rejected the specified implementation.)*
*(Round 84, agy and codex concordantly. This budget has now been stated as a number FOUR times — once per component, then two walks, then three own-entry authentications, then "derived" with the two-walk cap still standing in the same paragraph — and every one was shown unachievable by a correct implementation within one round. The rule is REWRITTEN rather than amended, because each previous amendment replaced the opening and left the old bound further down. A bound the rules' own decision points contradict is not a budget; it is a fourth statement of the algorithm.)*

**BUD-2 — Verification commands and floors.** All seven verification commands must run green: `python3 scripts/validate-plugin-assembly.py --root . --strict`; `python3 scripts/validate-hooks.py --root . --strict --require-manifest`; `VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh`; `bash scripts/test-hooks.sh`; `python3 -m unittest discover -s mcp/review-synthesizer/tests`; `python3 -m unittest discover -s scripts/tests`; `shellcheck -s bash -S warning scripts/*.sh scripts/lib/*.sh scripts/review/*.sh .githooks/pre-commit`. The recorded numbers at `5a532b1` — `test-hooks.sh` 304, synthesizer 222, scripts 312, asset counts `21/21/0/1`, hook events 10 — are FLOORS, not equalities. Every measurement is re-derived rather than quoted, and prints `pwd` and `git rev-parse HEAD` beside its result.

**BUD-3 — Six mutation proofs required.** Verification requires mutation proofs N1, N2, N3, N4, N5 AND N6 — six, not five — each shown FAILING on the mutated tree and PASSING on the fixed one. None of the six is optional; the N6 store-publication suite is required, and any sentence declaring the envelope as N1–N5 is wrong.

**BUD-4 — Enum totality is derived.** Enum totality is DERIVED, not asserted: every exit path of the publish routine AND of the reader is enumerated, each mapped to exactly one `_UNLEASHED_POINTER_STATE` value, and the mapping checked against the declared list `created|current|conflict|stale|failed|none`. An exit with no value, or a value not on the declared list, fails verification. The no-scan exits are first-class members of that enumeration rather than exceptions to it. **This rule does not restate the exits: the publisher's are PUB-9's ordered E0..E7 and post-scan P1..P4, and the reader's are RD-14's six.** What BUD-4 requires of them is only this: every exit is enumerated, each maps to exactly one value, the mapping is checked against the declared list, and no clause anywhere assigns a state outside it. One consequence is stated here because it is an ORDERING and not a mapping: E0 is decided before E1, so a suppressed publisher in a shell with an unusable `HOME` reports `none`, not `failed`. *(Round 61: BUD-4 carried its own four-item list that reused the labels E0..E3 for DIFFERENT exits than PUB-9's — its E2 collapsed four of PUB-9's into one and its E3 named a READER exit — so two normative rules disagreed about what `E3` denotes. A second enumeration of a list is the defect this rule exists to prevent, and it had one.)*

**BUD-5 — Acceptance criterion.** §4.2a is complete only when all three conjuncts hold together AND N6's live mutant set is green; any one conjunct alone is insufficient. (1) The capability works: on a machine whose store's COMPLETE `base.*` candidate set is exactly ONE path, that path authenticates, and it was **PRODUCED BY RUNNING AN AUTHORITATIVE PUBLISHER** — one authenticating entry and ZERO failing ones. *(Round 80, codex: "exactly one authenticating entry" was satisfied by a store holding one authenticating entry PLUS a malformed candidate, which RD-5 and AE-1's own cell require to resolve `stale`; the criterion would then have demanded resolution of a store the design refuses.)* — the qualifying state is reached by executing a real publisher, never by seeding the entry, because a seeded store satisfies this conjunct while every real publisher reports `failed` — a live property of the store at resolution time, **not** the historical fact that one install once published, which stays true after that entry is chmod'ed to `0644` while conjunct 2 and RD-5 then require refusal — AND the ACL condition is evaluable — Darwin with `/bin/ls`, Linux with `/usr/bin/getfacl` — a shell with no `CLAUDE_PLUGIN_DATA` and no hook environment resolves the same base that a hook resolves. BOTH preconditions must be named, for the same reason: with two installs publishing every reader correctly refuses, and on a platform where the ACL condition is unevaluable every reader also correctly refuses (ACL-4), so without them conjunct 1 reports the capability broken exactly where the design is working. On an unevaluable platform the capability is unavailable by design and resolution degrades to D′; that is a PASS of this criterion, not a failure of it. (2) It fails closed everywhere else: with nothing published, or with a store the reader cannot authenticate, that shell reaches the sentinel with `OK=0` and exactly one diagnostic. (3) D′'s RESOLUTION and CONSUMER-PERSISTENCE behaviour is unchanged whenever `CLAUDE_PLUGIN_DATA` is set: the base resolves to the variable's value, `OK=1`, `SOURCE=host-env`, and every consumer reads and writes exactly where D′ put it. **It is not unchanged in the unqualified sense, and cannot be: PUB-4 deliberately adds one durable write under the store and PUB-11 may add one stderr line.** The unqualified wording was falsified by the feature it is meant to accept.

**BUD-6 — N1/N2 cell structure.** N1, N2 and N4 additionally gain the store × `HOME` dimensions; they are extended by this change rather than left as shipped. N1 and N2 run the full cross-product — `paths.sh` present and absent × `CLAUDE_PLUGIN_DATA` set, unset and empty: six cells, not two. Each cell starts a FRESH SHELL, sets the environment, and only then sources, because the cache is eager and process-stable and mutating the environment after sourcing tests the harness's ordering rather than the contract. Each cell exercises the marker, log AND context paths, not a single marker write. N1's set cell asserts the write lands only in the supplied host base and carries `base_resolution=host-env`; its unset and empty cells assert no PLUGIN-STATE reads and no writes anywhere — no legacy path, no root-derived path, nothing read from or written to a resolved base — a fail-open exit, and one bounded non-persistent stderr diagnostic. **The store scan is NOT one of those reads**, for the reason the unset/empty bullet of §4.1 now gives: it is the mechanism by which an unset shell learns the base, and forbidding it forbids the capability. *(Round 70: round 68b scoped the §4.1 bullet and left this one, so the rule still both required and prohibited the same read — the half-a-family shape, in the fix for a half-a-family defect.)*

**BUD-7 — N2 inert-gate fixture.** N2's defect-reproducing fixture must set NEITHER `CLAUDE_PLUGIN_DATA` NOR any entry in the store: an unset variable with a valid entry RESOLVES via step 2, so a fixture supplying either one proves nothing and the gate goes inert. The resolved-via-store path carries its own anti-inertness assertion instead — that resolving through an entry creates NO second store. This amendment is made in place in §5's inert-gate risk row, not by reference from another section.

**BUD-8 — N4 quarantine proof.** N4 must prove the quarantine move occurred safely, not merely that the old fallback is unreadable — the latter is satisfied the moment the resolver's guards land even if the quarantine never happens. N4 asserts: every source file ABSENT from the old location; each quarantine directory holding the EXACT inventory recorded before the move; every checksum matching; the one `-inline` residue quarantined separately with its own inventory, its provenance being unknown. N4 further asserts that every entry under `${HOME}/.claude/unleashed-mail/bases/` is byte-identical across the sweep and that the SET of entries is unchanged.

**N6-1 — Live mutant set membership.** A row is a member of N6's live mutant set if and only if it is PRINTED in the mutant table and is not marked struck/RETIRED in place. **The mutant table is part of the authoritative specification BY THIS REFERENCE**, notwithstanding that it is printed earlier in §4.2a rather than inside §4.2a-S rather than inside §4.2a-S: an implementer building steps 3a-3f needs its mutations, fixtures and oracles, so "§4.2a-S and §4.2a-P and nowhere else" includes the table N6-1 incorporates. *(Round 88, codex: S claimed self-containment while N6-1 made an external table operative, so an implementer had to open the older prose the self-containment claim told them they would not need.)* Rows deleted because they mutated mechanisms D″-pf removes — the singleton pointer, the `CONFLICTED` wire form, the publication lock — are absent from the table entirely (their numbers are simply missing); struck rows remain printed with their retirement reason recorded beside them and are NOT members. Membership is read from the table and from nowhere else. No section of this plan may cite a struck or deleted row as proof of an obligation: a citation to a retired mutant is worse than none, because it reads as proof while being enforced by nothing.

**N6-2 — Table derived, no counts.** The mutant table is DERIVED from the clause list and must be re-derived whenever a clause changes. No prose anywhere in this plan may state a mutant COUNT — not in §4.2a, not in §6, not in §7, not in a note. A count that is wrong and a count that has been corrected are the same defect: the number is deleted, never fixed, because the next change re-introduces the drift.

**N6-3 — Every obligation carries a mutant.** Every normative obligation in §4.2a carries at least one named, executable, discriminating mutant row, and every individual authentication clause carries exactly one mutant of its own. **This rule is an OBLIGATION ON §7, not a description of the table's current state, and the gap list below is the outstanding work — so a green mutant run does NOT mean the obligations in that list are proved.** N6 is satisfied only when the list is empty; until then "the live mutant set is green" is a statement about the rows that exist, and BUD-5's acceptance criterion may not be read as met while any obligation still has no row. A generic sentence such as "each authentication clause is refused independently" is not a mutant; an unnamed mutation is one nobody writes; a mutant that cannot fail reads exactly like a mutant that passes; and an unrunnable mutant proves nothing. Obligations that presently have no row and require one — **and this list is itself re-derived from the table each round, because it went stale twice while reading as authoritative**: the SessionStart notice predicate (its only mutant was deleted with no replacement); the per-cell stderr scoping; the no-bare-statement, group-level-redirect and nounset source-time rules; the exactly-one-unresolved-diagnostic-per-process cardinality across all five family files with `paths.sh` absent; and the per-family-file quantification of reader rules −1 and 0.

**N6-4 — No duplicate rows.** No two live rows may name the same mutation with the same discriminating case; a duplicate adds no evidence and inflates the table's apparent coverage. Applied: rows 73 and 84 are one mutation (arm equivalence must also assert `_UNLEASHED_POINTER_STATE`) — keep 73, delete 84, and repair every §7 step that cites 84. Rows 66 and 83 are one mutation with one fixture (omit ancestor creation on a clean install) — keep 66, delete 83, and repair the §7 step that cites 83. Rows 65 and 97 name one fixture and one oracle (empty `$1` + `paths.sh` absent + one valid entry ⇒ resolves `OK=1`), and 97 mutates the bridge's PROSE, which cannot be executed — keep 65, which mutates the body, and delete 97.

**N6-5 — One implementation step per row.** Every live row is assigned to exactly ONE implementation step, so the step that builds a clause also builds its proof; no row may appear under two steps (row 84 was listed under both 3d and 3e before it was struck as a duplicate of row 73) and no live row may be left unassigned. Assignment by category: encoder and injectivity rows, including the no-fork, `LC_ALL=C`-pin and `LC_ALL`-leak rows (45, 93, 94) → 3a; entry-clause, chain-clause and ACL rows, including the authentication block (**2**-14, 21-28, 33-35), 76 and 111 → 3b — **row 1 is excluded deliberately**: it mutates the publisher's write-or-skip decision, which step 3d builds, and the range that swept it in here assigned it to two steps at once, which the next sentence of this rule forbids; the scan and the ordered reader rules, including 74 and the store-refusal rows 101 and 110 → 3c; publisher, temp-name, `NAME_MAX`, publisher-diagnostic and enum-mapping rows, including 59, 60, 95, 96, 105, 108, 109, 113, 115, 116, 118 and **120 and 121** → 3d; five-copy and bridge rows, including 99, 100, 103 and **119** → 3e. **Where a row could be read into two categories the assignment above is decisive and the category is not:** rows 120 and 121 mutate ACL behaviour but are PUBLISHER CALL SITES and belong to 3d; row 92 is a reader-path budget row and belongs to 3c; row 122 is an ACL-arm row and belongs to 3b; **row 131 mutates an ACL carve-out but is a PUBLISHER CALL SITE and belongs to 3d, on the same ground as 120 and 121; row 132 is a reader-path budget row and belongs to 3c, on the same ground as 92; rows 133 and 134 are publisher rows — the `NAME_MAX` probe and the store `mkdir` — and belong to 3d; rows 135, 139 and 143 are chain-and-ACL rows and belong to 3b; rows 136, 137, 138 and 142 are publisher call-site and publisher-budget rows and belong to 3d; **rows 140 and 141 are COUNTER-WIRING rows — they prove BUD-1's harness counts a specific tool — and belong to 3b, with the chain authentication whose invocations they count. Rows 144, 146, 147, 148, 149, 150 and 151 are ACL-GRAMMAR rows — they mutate the enumerator's line or answer parser — and all belong to 3b, with the ACL arm they constrain; rows 145 and 152 are retired and are not members; rows 153, 154 and 155 are publisher-write rows — the transient's create-and-write primitive and its refused-open mapping — and belong to 3d; row 159 is a publisher-path row and belongs to 3d; row 160 is an entry-clause row and belongs to 3b; rows 156, 157, 158, 161 and 162 are five-copy and family-writer rows and belong to 3e; row 163 is a reader-rule row and belongs to 3c; row 164 is a publisher row and belongs to 3d; row 165 is a SessionStart-notice row and belongs to 3e; rows 166, 167 and 170 are five-copy rows and belong to 3e; rows 168 and 169 are entry-clause and ACL rows and belong to 3b; row 171 is a store-creation row and belongs to 3d.** *(Round 124, agy: this enumeration stopped at 143 while nine live rows had been added after it, which this rule's own "no live row may be left unassigned" forbids.)* *(Round 106, codex: rows 131 and 132 were added in round 104 without an assignment, so each was readable into two steps — the exact ambiguity this sentence was written to close for 120, 121 and 92, reopened by the round that added rows without extending it.)* *(Round 88, codex: category descriptions alone left 120, 121 and 92 assignable to two steps each, which this rule's own "exactly one implementation step" forbids.)* Rows proving harness obligations (54, 71) are assigned to **§7 step 3f**, and the quarantine row (72) to **§7 step 6**. Both steps must EXIST for that assignment to mean anything: before round 66 these rows pointed at "the steps that build the harness `HOME` sandbox", and §7 had no such step, so two live rows were owned by nobody while the sentence read as though they were assigned. Rows proving §6 obligations rather than implementation clauses — the acceptance criterion (78) and the N1–N6 envelope (87) — are assigned to §6, not to §7.

**N6-6 — Store-level discriminating outcomes.** An authentication-clause mutant's discriminating case must name the STORE-LEVEL outcome the ordered reader rules produce, never merely "refused" and never "skip the bad entry". For any entry that fails the complete predicate that outcome is: the whole store is refused — sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic — and a good entry sitting beside the failing one must NOT win. Every row still written for the singleton pointer (oracles of the form "`foo/bar` refused", "two-line pointer refused", "pointer at 0644 refused", "0775 target refused") must be re-aimed on the template of row 2, which states the complete tuple: "a dangling `base.*` symlink yields sentinel, `OK=0`, `SOURCE=unresolved`, `POINTER_STATE=stale`, one diagnostic; it is NOT skipped as vanished." **Row 2 did NOT state that tuple when this rule first named it as the template** — a template that does not itself comply teaches the shape the rule forbids, which is how eighteen rows stayed abbreviated across two sweeps.

**N6-7 — ACL rows state allowlist.** Every mutant row and every risk-register restatement of the Darwin ACL clause states it as an ALLOWLIST: a component is REFUSED when an `allow` ACE naming a principal other than the effective user carries ANY right outside the seven read-only rights `execute`, `list`, `read`, `readattr`, `readextattr`, `readsecurity`, `search`. The mutating-right BLACKLIST phrasing — "refused when an `allow` ACE grants another principal a mutating right" — is forbidden wherever it appears, including row 55's oracle and §5's ACL risk row, because a right nobody enumerated must REFUSE rather than accept.

**N6-8 — Complete-predicate publish skip.** The publisher skips its write only when its own entry already satisfies the COMPLETE follower predicate — the entry clauses, the entry-chain clauses, the target-chain clauses and the ACL clauses — AND its content equals the base value. The weaker type-and-content test is forbidden. Every row naming that skip must name the complete-predicate test: row 1's mutation is "drop the complete-predicate skip" with the oracle "mtime unchanged on a no-change second run", and row 80's is "skip publication on the weaker type-and-content test" with the oracle "a `0644` REGULAR NON-SYMLINK entry with matching content is REPUBLISHED, and reports `created`, never `current`; a SYMLINKED `base.<key>` is refused by ST-7 and reports `failed`". Two rows may not present two different skip tests.

**N6-9 — Equivalent mutants retired.** A row whose mutation produces no observable difference under the current clause set is RETIRED — struck in place with its reason recorded beside it — and is not a member of the live set. Any parenthetical in another row that cites a retired row must be re-pointed at a live one in the same edit. Applied: row 11 ("accept a group-writable pointer parent | 0775 parent refused") is an equivalent mutant, because the entry's parent is the store `bases/`, which must be exactly `0700` and which the store-authentication rule refuses at any other mode, so dropping the general not-group-or-world-writable test on that one component changes nothing observable; row 22's parenthetical "(row 11 covers only the parent)" must then cite row 26, and row 26 must state its store-level outcome rather than only "exact-0700 parent rule enforced".

**N6-10 — Mutants runnable unprivileged.** Every mutant must be runnable by an unprivileged uid; no row may prescribe a fixture that requires root, such as a real `/opt/claude/data`. Off-`${HOME}` chains are built by the harness under a temporary root, and no row names a fixed absolute path it cannot create. The mechanism is specified rather than appealed to: the chain-walk predicate takes its per-component ownership and mode facts from a SINGLE accessor, and the harness substitutes a fixture table for that accessor — one accessor used by production and by the harness, so a test cannot pass against a predicate production does not run. **The SAME single-accessor requirement covers the two PROBES and the ACL ENUMERATOR, and for the same reason: the IDENTITY probe (`/usr/bin/id -un`, P-3a), the `NAME_MAX` probe (`/usr/bin/getconf`, NM-1) and the ENUMERATOR OUTPUT (`/bin/ls -lde` on Darwin, ACL-2/ACL-5) are each reached through ONE accessor that production and the harness share, so a fixture can present a FAILED probe or a MALFORMED ACE LINE.** **The enumerator-output seam is what makes the grammar rows runnable at all**: `chmod +a` followed by the mandatory absolute `/bin/ls -lde` CANNOT emit a duplicate verb, a duplicated `inherited`, an empty `<perms>` or an unknown pre-verb field, so without this seam those obligations could be unit-tested as strings but never produce N6-6's store-level tuple through the production resolver — the only outcome N6-6 accepts. *(Round 116, codex: N6-10 and §7 step 3f seamed component facts, `id -un` and `getconf`, and rows 144-146 needed a fourth seam that did not exist.)* Both are invoked by absolute path, so no unprivileged harness can make either fail by manipulating `PATH`, and rows 131 and 133 would otherwise prescribe fixtures that cannot be built. *(Round 108, codex: this requirement existed only in §7 step 3f(iii), so two live rows depended on machinery §4.2a-S did not carry — and §4.2a-S claims an implementer needs nothing outside it.)*

**N6-11 — Required executable cases.** N6 carries executable CASES in addition to mutants, and each case must fail when the fix is reverted. Required cases: step 1 — the base is the variable's value and this publisher's entry holds it; a second run with the same value performs NO write, asserted by mtime; a `0644` REGULAR NON-SYMLINK entry with matching content IS republished as a conforming one, while a SYMLINKED `base.<key>` is NOT — ST-7 refuses it, nothing is written and the state is `failed`, a separate required case carrying the opposite oracle; a second install id with a different base leaves TWO entries, which every reader resolves as a conflict. Step 2 — variable unset with exactly one authenticating entry resolves to that entry's target with `_UNLEASHED_BASE_SOURCE=pointer` and NO second store created; each authentication clause refused independently, including a conflicted STORE (two authenticating entries; there is no per-entry conflicted state). Step 3 — `HOME=""` yields the sentinel, `OK=0`, exactly one diagnostic, no `${HOME}`-rooted open attempted at all, and the no-persistence envelope holding in full. Persisted records carry `base_resolution` matching the resolution that actually ran. The SessionStart notice fires on `conflict`/`stale`/`failed` and stays silent on `created`/`current`/`none`. Two publishers holding the SAME base racing on one entry name converge on identical bytes, with no torn read and no lost write. On a platform with no ACL enumerator, a publisher publishes and re-verifies its own entry successfully while a reader still REFUSES a foreign entry. The empty-store case is asserted under zsh for each of the five family files independently.

### How to use this section

An implementer codes from here and from nowhere else: if an obligation is not stated above, it is not required, and if it is stated above, no other passage may relax it. A reviewer checks the code against here, rule by rule, rather than against any narrative restatement. A correction — to fix a defect, close a gap, or settle a disagreement — edits here first; only after the rule above reads correctly may explanatory prose elsewhere be updated to match it, and prose that cannot be made to agree is deleted rather than reconciled.


### 4.2a-P — THE PRIMITIVES (how a POSIX shell actually learns each fact)

> **WHY THIS SECTION EXISTS.** A consolidation of §4.2a into 102 single-statement rules was checked for
> implementability, rule by rule, with one question: *could you write the shell from this statement
> alone?* **51 of 80 passed. The 29 failures shared one shape — the plan specifies PREDICATES
> completely and PRIMITIVES not at all.** Every clause said what must be true of a file; almost nothing
> said how a shell learns it. Three of the gaps blocked §7 steps 3a, 3b and 3d outright, which is why
> twenty-five gate rounds produced a document reviewers could argue about and nobody could build from.
>
> Each primitive below was **executed in `/bin/bash` 3.2.57 and `/bin/zsh` 5.9 on the reference
> machine**, and the measured output is recorded with it — **with ONE stated exception: the LINUX arms
> of P-2, ACL-3 and P-4 have NOT been executed**, because the reference machine is Darwin. They are
> named as unmeasured where they appear and §7 forbids building them until the CI probe's output is
> transcribed. *(Round 86, codex: this sentence said "each primitive" without qualification while P-2
> withheld the Linux format two hundred lines below — the section that exists to stop unexecuted claims,
> opening with one.)* A primitive that has not been run is not a
> primitive, it is a hope.

**P-1 — `[ -O <path> ]` is NOT the ownership accessor this design uses.** Measured: it works in **both** shells with **zero forks**, and it answers only one question — "is this owned by the EFFECTIVE uid?" It cannot identify any other owner: `[ -O / ]` is false for the root-owned `/` and equally false for a directory owned by uid 502, so ANCHOR-1's "owned by uid 0" is not decidable with it. **Every ownership question in this design — "owned by the effective uid" and "owned by uid 0" alike — is answered by comparing P-2's uid field against `${EUID}`**, which both shells define without a fork (measured; never `id -u`). That keeps P-2's one-lstat-call-per-component property true and lets §7 step 3f's fixture seam see every ownership decision; calling `[ -O ]` performs an ownership query OUTSIDE P-2 and bypasses both. It is recorded here only because it is the obvious spelling and a reader of this section will reach for it. *(Round 92: this rule is REWRITTEN WHOLE. Round 90 corrected it by prepending a new statement and left the old one below, producing a duplicated sentence and an unmatched `owner**` — in the primitives section implementers copy from. Second amendment, so the statement is replaced rather than spliced.)*

**P-2 — Mode, size AND owning uid, in ONE lstat call per component.** There is no single fork-free
answer, and the split is stated rather than papered over. Every clause of this design that asks a
question about a component — its mode, its byte size, who owns it — is answered by this ONE call,
and the three facts come back together:
* **zsh** — `zmodload zsh/stat; zstat -L -H h -- "$p"`, then `printf -v m "%04o" $(( ${h[mode]} &
  4095 ))`, `s=${h[size]}`, `u=${h[uid]}`. **Zero forks.**
* **bash** — no builtin exists, so **one fork**: `/usr/bin/stat -f '%p %z %u' -- "$p"` on Darwin,
  where the mode is the LAST FOUR octal digits of the first field. On Linux the same three facts
  must come from one `/usr/bin/stat -c` call in the same order; the exact format is NOT stated
  here because it has not been executed (see below). The platform is selected by `/usr/bin/uname
  -s` and the binary invoked by absolute path, for the reason ACL-5 gives.
* **`-L` ON THE ZSH ARM IS LOAD-BEARING: without it the two arms measure DIFFERENT FILES.**
  Measured on one symlink-to-a-0700-directory: the bash arm returned `755 9` — the LINK's own mode
  and the length of its target string — while `zstat` without `-L` returned mode `700`, size `64`,
  the TARGET's. On a DANGLING symlink the bash arm SUCCEEDS (`755 12`) and `zstat` without `-L`
  FAILS outright. `zstat -L` reproduces the bash answer exactly in both cases. `/usr/bin/stat` is
  lstat by default; `zstat` follows by default. Every clause here that says "not a symlink",
  "owned by", or "mode exactly" means the PATH ITSELF, so both arms must be lstat — and the
  dangling-symlink case is mutant row 2's own fixture, where the previous text would have made
  one shell refuse and the other abort.
* **THE MASK IS TWELVE BITS, NOT NINE, AND THE DARWIN FORMAT HAD TO CHANGE WITH IT.** An "exact
  mode" means all twelve bits. Measured: a `chmod 4600` file has `%p` = `104600`, yet the previous
  arms reported `600` (Darwin `%Lp`) and `600` (zsh masked with 511) — so a SETUID entry satisfied
  "mode exactly 0600" in both shells, and a `chmod 1700` store satisfied "exactly 0700" (`%p`
  `41700`, `%Lp` `700`). `%Lp` strips the high bits exactly as `& 511` does, which is why widening
  only the zsh mask would have CREATED a divergence rather than closing one. With `%p` last-four
  against `& 4095` printed `%04o`, both arms return `0700` / `1700` / `0600` / `4600` on those same
  fixtures — measured, agreeing on every one. Compare the four-digit octal STRING; never compare
  integers, and never write a bare `0NNN` inside `$(( ))` (P-3).
* **THE OWNING UID COMES FROM THIS CALL TOO, WHICH IS WHAT MAKES ANCHOR-1 CODEABLE AT ALL.** P-1's
  `[ -O ]` answers only "owned by the EFFECTIVE uid" and returns FALSE for a root-owned component
  and for a component owned by any other uid alike — measured, `[ -O / ]` is false — so ANCHOR-1's
  "owned by uid 0" test could not be written from the previous primitives at all. Both arms already
  had the fact and neither exposed it: `${h[uid]}` is populated (measured `0` for `/`) and
  `/usr/bin/stat -f '%u'` returns `0`. It costs no extra fork because it rides the same call.
* **The size comes from the SAME call in both arms**, which is what ENT-2 depends on.
* **The Linux arm has still not been executed** — this machine is Darwin, where `/usr/bin/stat -c`
  is `illegal option -- c` (executed). What §6 must verify on the CI runner is not a format string
  but a PROPERTY: one lstat call returning the twelve mode bits as four octal digits, the size in
  bytes, and the owning uid, agreeing digit-for-digit with the zsh arm on the fixtures above —
  including setuid, setgid and sticky. Until that runs, no Linux format is stated here, because a
  format written from documentation is what produced every defect this rule has had.
* The budget in §6 counts this fork. A bash reader pays one `stat` per component; a zsh reader pays none.

**P-2a — Byte length of a shell string: `LC_ALL=C` in force, or the count is characters.** Measured
on `/tmp/café`: `${#v}` is **9** under a UTF-8 locale and **10** under `LC_ALL=C`, in BOTH shells.
ENT-2 compares a file's SIZE (always bytes) against `${#line} + 1`, so a `${#line}` taken outside
`LC_ALL=C` compares bytes against characters and **rejects every otherwise-valid non-ASCII entry**.
Every length this design compares against a byte count is therefore taken with `LC_ALL=C` in force,
under ENC-3's save-and-restore discipline — which ENC-3 scopes to the key derivation alone, so the
scope is stated again here rather than assumed to carry.

**P-3a — The ACL principal: the NAME from `/usr/bin/id -un` and the effective user's UUID from `/usr/bin/dsmemberutil getuuid -U <name>`, one fork each, once per resolution.** **SCOPE: this primitive and its refusal apply ONLY on the DARWIN arm, and only when its enumerator is present.** The Linux arm does not compare principal NAMES at all, so it needs no principal and never runs this probe; "any arm whose enumerator is present" wrongly included Linux-with-`getfacl`, where a failing `id -un` would then refuse for want of a value nothing consumes. Where no enumerator exists the ACL clauses are not evaluated at all, so no principal is needed and the probe is not run; running it there would add a refusal AUTH-1 does not authorise, and the Linux arm does not compare Darwin principal names either. *(Round 106, codex: the operative sentence said any `id -un` failure refuses publisher and reader with no carve-out, which is correct WHERE THE PROBE IS NEEDED and a new fail-closed defect everywhere else — my round-104 fix for a fail-open, over-applied. The carve-out AUTH-1(h) grants and the scope THIS rule needs are different statements about the same platform, and round 104 conflated them.)* ACL-2 refuses an `allow` ACE "whose **Separately, and on EVERY arm: the effective UID NUMBER is a third probe of the same shape** — `/usr/bin/id -u` behind `_u_euid_probe`, resolved once per resolution and cached on a flag `_u_probes_reset` clears at the entry points — and **`$EUID` is never consulted**: bash 3.2, the `/bin/bash` a macOS hook runs, IMPORTS EUID from the environment as an ordinary exported variable (measured: `env EUID=4242 bash -c 'echo $EUID'` prints 4242; zsh sets its own and is unaffected), so the auth chain's ownership clause, the entry predicate and both ENT-2b arms answered to the parent — `env EUID=4242` turned a healthy store `stale` and a publish `failed`, reading and writing nothing (codex sweep after pass 14 — reproduced; row 177).
principal is not the effective user", which needs the euid's NAME as a string to match against the
enumerator's output; P-1's `[ -O ]` answers a different question and cannot supply it. Measured:
`/usr/bin/id -un` returns `nick` in both shells. **The ACE principal is NOT that bare name: measured, `/bin/ls -lde` prints ` 0: user:nick allow list`, so the field carries a `user:` or `group:` type prefix.** The arm compares the portion AFTER the first `:` of a `user:` principal against `id -un`, treats a `group:` principal as another principal regardless of name, and treats an UNTYPED principal — a bare UUID, which is how the enumerator renders an identity it cannot map to a name — as SELF iff it equals the effective user's UUID resolved by the second probe (exact 8-4-4-4-12 hex shape, one line; a failed or malformed probe leaves the UUID EMPTY, and an empty UUID means NO bare UUID is self — fail closed) and as foreign otherwise. **This is not a nicety: on some hosts — a mobile or directory account — the enumerator renders the effective user's OWN ACE as the bare UUID, and a parser that called every bare UUID foreign refused a legitimate self-ACE so that an authoritative publisher reported `failed`** *(external audit of PR #67, finding 1 — measured on the auditor's host; on the reference host the same ACE renders as `user:nick`, so it never showed here; rows 129 and 169)*. **A principal field with NO type prefix — a bare UUID, which `/bin/ls -lde` prints when it cannot resolve the ACE's identity, observed in a review checkout as `ABCDEFAB-CDEF-ABCD-EFAB-CDEF0000000C deny delete` — is NOT the effective user and is treated as another principal.** That is the fail-closed reading and the only safe one: an identity the system could not resolve cannot be shown to be ours. Comparing the raw field against the bare name never matches, which makes EVERY `allow` ACE look foreign and refuses every component that carries one — the capability dies on any Mac with an ACL, including the maintainer's own home directory, by absolute path, one fork, counted in BUD-1's
per-resolution budget. **`$USER` may not be used**: it is inherited from the environment, and
ACL-7 forbids a verdict that differs between a plugin hook and a git hook for the same machine
state. The name is resolved ONCE per resolution, not once per component. **If `/usr/bin/id -un` fails, exits non-zero, or prints anything but a single non-empty line, every component of this resolution REFUSES — publisher and reader alike, with NO carve-out. This governs WHERE THE PROBE IS RUN, which the SCOPE at the head of this rule fixes as the DARWIN arm with its enumerator present. On Linux, and on any platform with no enumerator, the probe is not run and there is no probe failure for this sentence to refuse.** *(Round 108, codex: round 106 scoped this to "the enumerator-present arm" in BOTH the preamble and here, and that phrase still includes Linux with `getfacl` — where the same sentence says principal names are not compared. Two readings, one refusing and one never running the probe. The third amendment to this rule's scope.)* AUTH-1 clause (h) grants the publisher's exemption only where NO enumerator exists, and explicitly withholds it from a present probe that failed; extending it here would let a publisher skip the ACL clauses whenever the identity probe fails while the enumerator is present and working — the fail-open AUTH-1 forbids by name. *(Round 104, codex: the round-102 wording said "the same publisher carve-out", which contradicted AUTH-1(h) and ACL-4 outright.)* Without that, a failed probe left the predicate undefined on the one input every ACE comparison depends on.

**P-3 — OCTAL LITERALS ARE NOT PORTABLE IN SHELL ARITHMETIC, and this would have corrupted every mode
comparison silently.** Measured: `$((0777))` is **511 in bash** and **777 in zsh** — zsh reads a leading
zero as decimal. `$((8#777))` is 511 in both, and plain `511` is 511 in both. **Every mask and every
mode constant in this design is written `8#NNN` or in decimal; a bare `0NNN` inside `$(( ))` is
forbidden.** The first `zstat` reading taken while writing this section returned **264** instead of `750`
for exactly this reason, and it looked like a `zstat` bug rather than an arithmetic one.

**P-4 — Creating the transient at mode 0600 without `touch`, `chmod` or `mktemp`, writing it, and telling
its three outcomes apart, is ONE open and ONE primitive:**
`( umask 077; set -C; trap '' XFSZ; _wt_opened=0; { _wt_opened=1; printf '%s\n' "$value" >&9 || exit 1; } 9>"$tmp" || { [ "$_wt_opened" = 0 ] && exit 2; exit 1; }; exit 0 ) >/dev/null 2>&1`
followed by `case $? in 0) ;; 2) [ -L "$tmp" ] || [ -e "$tmp" ] → LOST RACE, otherwise → E6 ;; *) → E6 ;; esac`,
and then VERIFY the mode. The redirection `9>"$tmp"` under `set -C` IS the exclusive create (P-5), and the
value is written THROUGH descriptor 9 — the transient's pathname is never opened a second time. Measured
on Darwin: yields `600` in **both** shells, and the value is in the file. **The umask is not sufficient
on its own.** A POSIX DEFAULT ACL on the containing directory supplies permissions that `umask` does not
mask, so on Linux a store carrying `default:group::r--` — which ACL-3 ACCEPTS, because the mask conjunct
is not satisfied — can yield a transient at other than 0600, and `mv` preserves that mode onto the entry.
The publisher therefore READS the transient's mode back through the single P-2 accessor immediately after
the create-and-write returns, and refuses (`failed`, transient removal ATTEMPTED — best-effort per ST-7)
if it is not exactly 0600. It does NOT `chmod`: ST-5 forbids the create-then-chmod window, and a mode
that arrives wrong is evidence about the directory, not something to paper over. This is UNMEASURED on
Linux — the CI probe of §6 must run it under a default ACL before the Linux arm is treated as proved. The
subshell scopes the `umask` change, `noclobber`, and the signal disposition, so none of them can leak to
a consumer, and there is no create-then-`chmod` window for a concurrent publisher to observe — the window
**ST-5 forbids**, which is the rule that requires the transient be created AT mode 0600 rather than
chmod'ed afterwards. *(Round 84, agy: this cited P-5, which is the exclusive-create primitive and says
nothing about a chmod window.)* **The three outcomes, and how the displayed shell tells them apart:**
`exit 2` is reachable ONLY on the branch where the `9>` redirection was REFUSED and the body never ran
(`_wt_opened` still 0); the caller then RE-TESTS PRESENCE with P-5's two-part test — if the name now
EXISTS it is a LOST RACE (PUB-9: one consumed TMP-1 attempt), and if the name is ABSENT (`ENOSPC`,
`EROFS`, `EACCES`, `EIO`) it is a CREATION FAILURE (PUB-9 E6), because a refusal that created nothing
must not spend the three attempts and surface as E5, whose diagnostic would name the wrong exit. EVERY
other non-zero status is a failure AFTER the create — the write failed, or the subshell died — and is E6
with the ST-7 cleanup, because a created-but-unwritten transient reported as a lost race would be
abandoned in the store; the ONE bounded exception is stated rather than hidden: with the descriptor
table exhausted the file is created and the `dup` onto 9 fails, the presence re-test then sees the name
and reports a lost race, and up to three empty transients remain — outside `base.*` (TMP-2), harmless
to every reader. **`SIGXFSZ` is ignored INSIDE the subshell** so a size limit surfaces as `EFBIG`
(`printf` rc 1 → E6) and not as a signal: measured, zsh does not carry the caller's ignored disposition
into a subshell, and when the subshell dies of the signal BASH reports the child's death ON THE CALLER'S
STDERR — a second, unbounded line beside PUB-11's one diagnostic, which the `2>&1` on the subshell cannot
cover because it is the PARENT that prints it. **zsh 5.9's `CLOBBER_EMPTY` is pinned off inside the
subshell** (`setopt no_clobber_empty`): a consumer's `setopt` would otherwise let `>` write through an
EXISTING EMPTY file under `noclobber`, turning the exclusive create into a write-through — measured,
refused (rc 2, file still empty) with the pin. The subshell's own stdout and stderr go to `/dev/null`:
measured, bash's `printf` builtin re-emits the value it failed to write to the RESTORED stdout after an
`EFBIG` error — a stray line on a hook's stdout — and zsh reports a refused `noclobber` redirection on the
shell's stderr even past a `2>/dev/null` placed on the compound command itself; only a redirection on
the enclosing subshell silences both, and PUB-11 permits nothing from this path on the caller's streams.
Mutant rows 153, 154 and 155 execute the three outcomes; row 138 caught a draft of this primitive
reporting the size-limit case as a lost race and leaving three empty transients behind. *(PR #67, codex
pass 6, and this rule is REWRITTEN rather than amended: its previous text prescribed
`(umask 077; : > "$tmp")` and a readback "before writing into it" — that is, a SECOND open of the
pathname to write the value — and that second open had none of the exclusive create's protection:
same-uid interference replacing the transient with a symlink between the two opens made the write
FOLLOW it and overwrite the target, reproduced in both shells, and a FIFO there would block every hook
at source time. No row could have caught it, because the rule WAS the defect. Adversarial verification
of the fix then found the first rewrite's displayed one-liner could not produce the `2` its own prose
described, its `SIGXFSZ` paragraph described a symptom the primitive now prevents, and its E5/E6
classification lived only here and not in §4.2a-S — PUB-9 now carries it.)*

**P-5 — Exclusive create (fail if the name exists): `set -C` (`noclobber`) plus a redirect — AFTER a
presence test, never before one.** Measured in both shells, on fresh names per shell: a new file is
**created**, and an existing regular file, an existing DIRECTORY, a symlink to a file and a DANGLING
symlink are each **refused** with a non-zero status. **A FIFO is not refused: the redirect BLOCKS.**
Measured with a 5-second timeout in both bash 3.2.57 and zsh 5.9, `set -C; : > thefifo` never
returned (`rc=124` in both) — opening a FIFO for writing waits for a reader. That is worse than a
wrong verdict: it HANGS the publisher, and the publish runs at SOURCE TIME in every process that sets
`CLAUDE_PLUGIN_DATA` and loads a family file, so a single FIFO left in the store stops every hook.
**Therefore the publisher tests presence with `[ -L "$p" ] || [ -e "$p" ]` and refuses any non-regular
shape BEFORE it opens anything** — the same two-part test ST-7 uses, for the same reason. `set -C`
remains as the race guard between that test and the create, which is all it can be: a check that
blocks on the hostile input cannot be the primary defence. **The residual is stated rather than
claimed closed: if the name is ABSENT at the presence test and same-uid interference creates a FIFO
there before the redirect runs, the open still blocks** — `set -C` refuses an existing file but cannot
make an open non-blocking. Closing that window needs an `O_NONBLOCK` open, which no POSIX shell
redirect offers, so it is an ACCEPTED LIMIT of the same-uid trust model THREAT-1 already states, not a
defect to be papered over. The transient's name carries `$RANDOM`, so the window is not predictable to
an attacker who cannot already read the process's memory; the DURABLE entry name is predictable, which
is why the reader's type-before-open rule (RD-12) is the load-bearing defence and this one is not. Same-uid interference is in-model here, per
ST-7's own rationale. *(Round 70, codex #3 asked whether this is exclusive-create for EVERY existing
pathname; measuring the answer found the FIFO hang, which no arm had named.)*
This is the primitive TMP-1 requires when it says the publisher creates the transient "under `set -C`,
which fails if a file of that name already exists". `set -C` is scoped to the subshell that performs the
creation, so it does not alter the sourcing shell's options.

**P-6 — `<uniq>`: `$RANDOM`, which BOTH shells provide.** Measured: bash 3.2.57 and zsh 5.9 each return
a value (`$RANDOM` is absent only from POSIX `sh`, which this family does not target — the plan's
earlier "no `$RANDOM`" constraint was inherited from a POSIX framing that does not apply). `<uniq>` is
therefore **`$RANDOM`, decimal, at most 5 digits**, which fixes the width the `NAME_MAX` budget needs:
`len(".pub.") + len(pid) + 1 + 5 + 1 + len(key)`. On collision — detected by P-5 — the publisher retries with a fresh `$RANDOM`; **the ATTEMPT BOUND is
TMP-1's, not this primitive's**, because it decides whether a publication happens and §4.2a-S governs
behaviour. `$$` alone is insufficient and
the plan already proves it: concurrent subshells inherit one `$$`.

**P-7 — Byte to two hex digits with no fork: `printf '%d' "'$c"`, masked, then `printf '%02x'`.**
Measured across `\303 \251 \001 \037 \177 \377`: bash **sign-extends** (`ffffffffffffffc3` for `\303`)
while zsh does not, so the mask is mandatory, not cosmetic:

```sh
printf -v n "%d" "'$c"; n=$(( n & 255 )); printf -v hh "%02x" "$n"
```

**`printf -v`, never `n=$(printf …)`** — and this correction is codex's, against my own first
version of this primitive (round 60). Command substitution creates a **subshell**, so the original
spelling contradicted the zero-fork requirement it was written to satisfy. I had verified the OUTPUT
was right and never checked it met the STATED CONSTRAINT, which is the same defect class as an oracle
that measures the wrong property. Measured: `printf -v` is supported in **both** bash 3.2.57 and zsh
5.9, assigns without a subshell, and yields `n=-61` in bash and `195` in zsh — masked with 255 both
give `195`, so the mask remains mandatory. *(`$(( #c ))` is a zsh-only ord and is not portable.)*

With the mask, **both shells produce identical output for every byte tested** (`c3 a9 01 1f 7f ff`).
`printf` is a builtin in both, and the arithmetic is builtin, so ENC-2's zero-fork requirement holds.

**P-8 — Walking every component of an absolute path, fork-free.** PCH-1 and ANCHOR-1 require a verdict
on EVERY component from `/` downwards, and no primitive said how to enumerate them. Measured identically
in bash 3.2.57 and zsh 5.9, zero forks, including a path containing a space:

```sh
acc=""; rest="$p"                                  # p is absolute
while :; do
    case "$rest" in //*) rest="/${rest#//}"; continue ;; esac   # collapse repeated separators
    printf '%s\n' "${acc:-/}"                      # THIS iteration's component; "" means /
    [ -n "$rest" ] || break
    rest="${rest#/}"                               # drop the leading separator
    [ -n "$rest" ] || break                        # a trailing slash ends the walk
    seg="${rest%%/*}"; acc="$acc/$seg"
    case "$rest" in *"/"*) rest="/${rest#*/}" ;; *) rest="" ;; esac
done
```

Measured by executing THIS TEXT, in both shells, with identical results:
`/` yields `/` alone; `/tmp` yields `/`, `/tmp`;
`/Users/nick/.claude/unleashed-mail/bases` yields `/`, `/Users`, `/Users/nick`, `/Users/nick/.claude`,
`/Users/nick/.claude/unleashed-mail`, `/Users/nick/.claude/unleashed-mail/bases`;
`/a b/c-d` yields `/`, `/a b`, `/a b/c-d` — no word splitting, because every expansion is quoted and
nothing is passed through `$( )`; `/a//b` yields `/`, `/a`, `/a/b`; `/a///b//c` yields `/`, `/a`,
`/a/b`, `/a/b/c`; and a trailing slash (`/a/b/c/`) ends the walk at `/a/b/c`.

*(Round 70, agy and codex CONCORDANTLY. The previous snippet **never emitted `/` at all** — it began
`rest="${p#/}"` and looped while `$rest` was non-empty, so for `p="/"` the loop body never ran and for
any other path the walk started at the FIRST named component. `ANCHOR-1` is the rule that most needs
the root tested, and this is the primitive an implementer copies. It also produced the invalid
component `/a/` for `/a//b`, which `TGT-1` does not forbid. **The cause is worth naming: the harness I
measured printed `/` before entering the loop, and the snippet transcribed into this section omitted
that line — so the recorded output was the harness's, not the snippet's.** Measuring one artefact and
publishing another is exactly the failure §4.2a-P exists to prevent, committed inside §4.2a-P. The text
above was therefore re-measured by executing the block verbatim, not a function wrapped around it.)*

**P-10 — Walking the BYTES of a string, and the `$var[` trap that breaks it in zsh.** The encoder walks
its input byte by byte, and no primitive stated how. Measured identically in bash 3.2.57 and zsh 5.9,
with `LC_ALL=C` in force (without it the count is CHARACTERS, per P-2a):

```sh
i=0; n=${#v}
while [ "$i" -lt "$n" ]; do
    c=${v:$i:1}
    i=$(( i + 1 ))
done
```

On `/a<c3><a9>b` both shells yield five single-byte elements and `n=5` — the two bytes of `é` are
separate elements, which is what makes ENC-1's `_x<hh>` rule reachable.

**The trap, found by executing this primitive rather than reading it: `"$out[$c]"` is ARRAY SUBSCRIPTING
in zsh.** Appending with `out="$out[$c]"` — the obvious spelling — is `X[/]` in bash and a FATAL ERROR
in zsh (`bad math expression: operand expected at '/'`), because zsh subscripts `$out` with `[$c]` and
tries to evaluate `/` as arithmetic. **Every string concatenation in these five files therefore braces
its expansions — `out="${out}${c}"` — never `"$out$c"` followed by a literal `[`.** Measured:
`"${o}[${c}]"` yields `X[/]` in both shells. This is a whole-family hazard, not one site: any
accumulator followed by a `[` is a zsh subscript.

**P-12 — Detecting an embedded NUL, and why the test is ZSH-ONLY.** ENT-2 refuses a line carrying a NUL, and no primitive said how to detect one. Measured in both shells on a file holding `/tmp/a\0b` and on a clean line:

```sh
case "$line" in *$'\0'*) : NUL present ;; *) : clean ;; esac
```

In **zsh** this is correct — the clean line reports clean, the NUL-bearing line reports NUL. In **bash** `$'\0'` collapses to the EMPTY string, the pattern becomes `**`, and **EVERY line matches**: the clean line reports NUL too. A bash implementation using this spelling therefore refuses every otherwise-valid entry. **So the pattern test runs only under zsh**, guarded by `[ -n "${ZSH_VERSION:-}" ]`, and bash relies on ENT-2's OTHER clause — the byte-count check, `size == ${#line} + 1` under `LC_ALL=C` (P-2a) — which detects a NUL because `IFS= read -r` stops at it and the file is longer than the line it yielded. Neither test alone covers both shells. **The pair is NOT sufficient either: ENT-2 requires a THIRD clause — the read's own return status — because a TERMINAL NUL makes the byte count match in bash. ENT-2 states the complete predicate; this primitive supplies only the zsh NUL test.** *(Round 100, codex, reproduced here: this is exactly the shell-divergent primitive §4.2a-P exists to pin, and ENT-2 named the zsh-only test without stating its spelling or why bash must not run it.)*

**P-11 — Reading a line EXACTLY: `IFS= read -r`, never plain `read`.** ENT-2 requires an entry's line to be its exact bytes, and no primitive said how to read it. Measured in BOTH shells on a file holding `/tmp/a\b ` (a backslash and a trailing space, both of which TGT-1 permits): plain `read` yields `/tmp/ab` — the backslash consumed as an escape, the trailing space stripped as `IFS` whitespace — while `IFS= read -r` yields `/tmp/a\b ` unchanged. The consequence is a durable poison: a publisher writes such a path, its own post-scan read sees different bytes, the name↔content check (ENT-3) fails, and the entry is `stale` forever with ST-8 forbidding its removal. **`IFS=` and `-r` are both required and neither is sufficient** — `-r` alone leaves the trailing space stripped, `IFS=` alone leaves the backslash consumed. Every read of an entry, on both the publisher and reader paths, uses this form.

**P-13 — Splitting a line into fields, and a field into rights, IN BOTH SHELLS.** ACL-2 requires
locating the `allow`/`deny` token in an ACE line and testing each right in a comma-joined list, and no
primitive said how. **The obvious spelling does not work: `for f in $line` splits in bash and NOT in
zsh, because zsh does not word-split unquoted parameter expansions (`SH_WORD_SPLIT` is off by default)
— and SETTING `IFS` DOES NOT CHANGE THAT.** Measured on the ACE body
`group:staff inherited allow list,add_file,file_inherit`, with `IFS=' '` explicitly set: **bash 3.2.57
yields 4 fields, zsh 5.9 yields 1.** In zsh the whole line is then one token, no field ever equals
`allow`, every ACE is skipped and the component is ACCEPTED — the fail-open mutant row 139 pins.

Both layers are peeled with parameter expansion instead, which behaves identically in both shells, and
**every SLOT of ACL-2's grammar is enforced — it is not enough to find the verb.** `<body>` is the line from the first `: ` onward. **THE CALLER SELECTS NOTHING: it passes EVERY line of the answer, in order, with its 1-based number, and this primitive classifies each one** — a caller that filtered would have to classify in order to filter, which is the same work in two places and the boundary along which they would drift. *(Round 120, codex: the prose said ACL-4 selected which lines reached P-13 while the block itself classified them, so the caller's responsibility was stated two contradictory ways.)* Field 1 is the principal; then at most ONE `inherited`; then
EXACTLY ONE verb; then EXACTLY ONE `<perms>`, which may not itself be `allow`, `deny` or `inherited`.
Repeated whitespace between fields is skipped. Every other shape REFUSES under ACL-4.

**The ANSWER-level machine, which is what decides parseability** — measured in both shells over eight
answer shapes:

```sh
_u13_answer_ok() {                              # stdin: the enumerator's answer
    _u13_st=INIT
    while IFS= read -r _u13_l || [ -n "$_u13_l" ]; do
        case "$_u13_st" in
            INIT) case "$_u13_l" in
                      # RECOGNISED POSITIVELY: `ls -l`'s mode field — a type character then nine
                      # permission characters. "any line not starting with a space" accepted
                      # `garbage` as a stat line, which is the seventh shape this arm has admitted.
                      [-dlbcps][-r][-w][-xSs][-r][-w][-xSs][-r][-w][-xTt]*) _u13_st=BODY ;;
                      *) return 1 ;;
                  esac ;;
            BODY) case "$_u13_l" in
                      '')   : ;;                # BLANK
                      ' '*) _u13_ace "$_u13_l" || return 1 ;;
                      *)    return 1 ;;         # a SECOND non-space line
                  esac ;;
        esac
    done
    [ "$_u13_st" = BODY ] || return 1           # an EMPTY answer never reached BODY
    return 0
}
```

| answer | result |
|---|---|
| stat + one ACE | parseable |
| stat only, no ACEs | parseable |
| stat + blank + ACE | parseable |
| **an ACE with NO stat line** | **MALFORMED** |
| blank first | **MALFORMED** |
| stat + ACE + a later non-space line | **MALFORMED** |
| the EMPTY answer | **MALFORMED** |
| two stat lines | **MALFORMED** |

**And the LINE parser it calls**, which decides only whether one ACE line is well formed:

```sh
# `_u13_ace` is STRICTLY an ACE-LINE parser: ONE argument, no line number, no classification.
# `_u13_answer_ok` above decides WHICH lines are ACE lines; this decides whether ONE of them is well
# formed. *(Round 124, agy and codex: the round-120 preamble survived here beside the answer machine,
# telling the caller to pass every line for THIS block to classify. Two measured consequences: an
# implementer following it reproduced the exact no-stat-line fail-open the answer machine removes,
# and composing the two PRINTED contracts REFUSED a valid stat+ACE answer in both shells, because the
# machine passes one argument while this block read `$_u13_line`.)*
_u13_line="$1"
_u13_idx="${_u13_line# }"; _u13_idx="${_u13_idx%%:*}"               # the claimed index, up to the FIRST colon
case "$_u13_idx" in ''|*[!0-9]*) return 1 ;; esac    # the index must be DECIMAL and non-empty
_u13_rest="${_u13_line# }"; _u13_rest="${_u13_rest#"$_u13_idx"}"
case "$_u13_rest" in ': '*) _u13_body="${_u13_rest#: }" ;; *) return 1 ;; esac   # delimiter is EXACTLY ": "

_u13_principal=""; _u13_verb=""; _u13_perms=""; _u13_inh=0; _u13_n=0
_u13_rest="$_u13_body"
while [ -n "$_u13_rest" ]; do
    _u13_tok="${_u13_rest%% *}"
    case "$_u13_rest" in *" "*) _u13_rest="${_u13_rest#* }" ;; *) _u13_rest="" ;; esac
    [ -n "$_u13_tok" ] || continue                   # a repeated space is not a field
    _u13_n=$(( _u13_n + 1 ))
    if [ -z "$_u13_verb" ]; then
        case "$_u13_tok" in
            allow|deny) _u13_verb="$_u13_tok" ;;
            inherited)  if [ "$_u13_n" = 1 ] || [ "$_u13_inh" = 1 ]; then return 1; fi
                        _u13_inh=1 ;;                # optional, singular, never field 1
            *)          if [ "$_u13_n" = 1 ]; then _u13_principal="$_u13_tok"
                        else return 1           # unknown field before the _u13_verb
                        fi ;;
        esac
    else
        [ -z "$_u13_perms" ] || return 1             # a SECOND field after the _u13_verb
        case "$_u13_tok" in
            allow|deny|inherited) return 1 ;;   # a reserved token cannot BE the rights field
        esac
        _u13_perms="$_u13_tok"
    fi
done
[ -n "$_u13_verb" ] || return 1
[ -n "$_u13_principal" ] || return 1
case "$_u13_perms" in
    ''|*,,*|,*|*,) return 1 ;;                  # empty, doubled, leading or trailing comma
esac

_u13_rest="$_u13_perms"                                   # layer 2: the comma-joined rights
while [ -n "$_u13_rest" ]; do
    _u13_tok="${_u13_rest%%,*}"
    case "$_u13_rest" in *,*) _u13_rest="${_u13_rest#*,}" ;; *) _u13_rest="" ;; esac
    # ... test $_u13_tok against ACL-2's seven-right allowlist ...
done
```
**Every name in this block carries the `_u13_` prefix, because FAM-5 requires it and a template must obey its own rule.** The family files are SOURCED into a consumer's shell and a POSIX function has no locals, so a block written with bare `n`, `rest` and `body` imports those names into whatever sources it — and mutant row 143 exists for exactly that collision. *(Round 120: the block used bare names, and the very harness extracting it to verify this round collided on `n` — its line counter against the block's field index — printing line numbers 1, 3, 4 for three lines.)*


**Return 2 means "not an ACE line, skip it"; return 1 means MALFORMED, which under ACL-4 poisons the
whole answer. They are different outcomes and collapsing them is the defect this primitive has now had
four times** — a residual "skip anything unrecognised" arm is exactly how a malformed prefix reached
the field parser.


Measured by executing THIS TEXT in both shells, identical results in each row — RAW lines, so the
`<n>:` strip is exercised too:

| raw line | result |
|---|---|
| ` 0: group:staff allow list,add_file` | ACE |
| ` 0: group:staff inherited allow list` | ACE |
| ` 12: group:staff allow list` | ACE — a multi-digit index |
| ` 0:` + 2 spaces + `group:staff allow list` | ACE — repeated whitespace after the delimiter is skipped |
| `drwxr-xr-x@ 2 nick wheel 64 … d` | STAT — skipped |
| (empty line) | BLANK — skipped |
| ` 0:group:staff allow list` | **MALFORMED** — the delimiter is not `: ` |
| ` x: group:staff allow list` | **MALFORMED** — the index is not decimal |
| ` : group:staff allow list` | **MALFORMED** — the index is empty |
| ` 0: group:staff deny allow` | **MALFORMED** — a reserved token in the `<perms>` slot |
| ` 0: group:staff inherited inherited allow list` | **MALFORMED** — `inherited` is singular |
| ` 0: group:staff allow write allow list` | **MALFORMED** — a second field after the verb |
| ` 0: group:staff weird list` | **MALFORMED** — unknown field before the verb |
| ` 0: group:staff allow ` | **MALFORMED** — empty `<perms>` |
| ` 0: group:staff allow list,,read` | **MALFORMED** — also `,list` and `list,` |

A principal CONTAINING a comma parses, then cannot match `id -un`, so it is treated as a foreign
principal — fail-closed by construction, and not forbidden here.

*(Round 116, codex, THIRD consecutive round of fail-opens in this one primitive. Round 114's block
constrained the verb and the rights field and left two slots free: unlimited pre-verb `inherited`
tokens, and a rights slot that accepted a RESERVED token — so ` 0: group:staff deny allow` parsed as
verb `deny`, perms `allow`, and ACL-1 then discarded the whole line. **agy saw the duplicate-`inherited`
case in round 115 and dismissed it as having "no operational impact" because `/bin/ls -lde` does not
emit it; that reasoning is wrong under ACL-4, which makes ANY non-matching line unevaluable rather than
ignorable** — the arm's job is not to predict what a healthy enumerator emits. Each round tightened the
slot that had just been exploited and left the next one; the grammar is now constrained at every slot
at once.)*

*(Round 114, agy and codex CONCORDANTLY, each having EXTRACTED AND RUN the round-112 block: it located
the verb by SCANNING, so a second `allow` reset `perms` and the earlier field was silently DISCARDED —
`group:staff allow add_file allow list` yielded verb `allow`, perms `list` in BOTH shells, and a
foreign ACE granting `add_file` was ACCEPTED as read-only. A space inside `<perms>` is the same shape.
Scanning cannot detect a duplicate verb; the grammar is now positional. **This is the SECOND fail-open
in this primitive in three rounds, and both came from writing a TOLERANT parser for a security
predicate** — tolerance is the defect, not the style.)*

*(Round 112, codex, who EXTRACTED AND RAN the round-110 block exactly as the prompt asked. Its rights
layer carried `[ -n "$tok" ] || continue`, which SILENTLY DISCARDED empty elements: an empty `<perms>`
yielded `[group:staff][allow]` and a foreign `allow` ACE then passed with no right ever tested —
vacuously. `list,,read` became `[list][read]`, `,list` and `list,` became `[list]`. **A fail-open in
the primitive added one round earlier to fix a fail-open**, and the skip that caused it was written to
be tolerant. ACL-4 already says an unparseable ACE line makes the condition unevaluable; this
primitive now obeys it instead of repairing the input.)*

**FAM-5's brace rule is load-bearing inside this primitive and I broke it while measuring it.** The
first harness accumulated with `out="$out[$tok]"` and zsh failed with `bad math expression: ':'
without '?'` — `$out[` is ARRAY SUBSCRIPTING there, exactly row 119's defect, committed in the script
measuring a different zsh divergence. Every concatenation here is braced.

**P-9 — The nearest EXISTING ancestor, fork-free.** NM-1 and ENC-9 need `getconf NAME_MAX <dir>` against
`bases/` *or its nearest existing ancestor while the store does not yet exist*, and no primitive said how
to find one. Measured identically in both shells:

```sh
d="$candidate"
while [ ! -d "$d" ]; do
    case "$d" in */*) d="${d%/*}"; [ -n "$d" ] || d=/ ;; *) d=/; break ;; esac
done
```

On this machine `/Users/nick/.claude/unleashed-mail/bases` yields `/Users/nick/.claude/unleashed-mail`,
`/nonexistent/a/b/c` yields `/`, and an existing `/tmp` yields itself. It terminates at `/` because `/`
always exists, so there is no unbounded loop on a pathological input.

> **What remains unmeasured — and the mechanism that will measure it.** P-2's Linux arm, ACL-3's
> `getfacl` grammar, and P-4's behaviour under a POSIX default ACL have never been executed: this
> machine is Darwin and has no `getfacl`. **They are not written from documentation, and they are
> not left as a promise either.** `scripts/review/linux-primitive-probe.sh` runs all three on a
> real Linux host and PRINTS what they return, and CI runs it on `ubuntu-latest`
> (`.github/workflows/plugin-ci.yml`, job `linux-primitive-probe`). It asserts nothing and gates
> nothing — its output is transcribed into this section by a human, which is why it cannot turn
> CI red. **§7 may not build the Linux arm of P-2, ACL-3 or P-4 until that transcription has
> happened**; the Darwin arms are executed and may be built now. Every defect P-2 has had came
> from a format written from documentation, so this is the one place where a promise is replaced
> by a runnable.

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
> **ROUND 32 — THIS BLOCK WAS WRITTEN FOR THE SINGLETON POINTER AND WAS NEVER REVISITED. Its premise is
> false, one of its three additions is now DESTRUCTIVE, and another cannot fail.** Proved mechanically:
> `git log -L1368,1383:<plan>` returns a **single** commit, `938a97c` (round 23) — byte-identical since,
> while round 30 deleted the singleton and round 31 propagated that to eight other sites. **Round 31
> swept by grepping the deleted NAMES; this section names the same things in different words** ("the
> pointer's parent", "that directory"), so grep passed over it — and `:48` went on asserting *"§4.3,
> §4.4 and the D′ envelope stand."* **A section certified without being read.** Sixth half-a-family, and
> the one that shows the propagation METHOD was inadequate, not just its coverage.
>
> * **The premise is false.** `~/.claude/unleashed-mail` is no longer the pointer's parent; the store is
>   `bases/` one level down, created `mkdir -m 700` by the publisher. The exact-`0700` rule applies only
>   to `bases/`, and `0755` ancestors satisfy the general rule — measured ACCEPT on this machine's real
>   modes, so the "emptied `0755` directory refuses every future publication, permanently" hazard this
>   block was written for **cannot occur**.
> * **Addition 2 is destructive and is DELETED.** *"After the move, remove and re-create the directory
>   `0700`"* means `rm -rf ~/.claude/unleashed-mail && mkdir -m 700 …`, which deletes `bases/` and every
>   published entry — **silently un-publishing the machine, verbatim the outcome addition 1 exists to
>   prevent**, and falsifying this plan's own live invariant that the quarantine *"never touches"*
>   `bases/`. No repair is needed at all now, so none is specified.
> * **Addition 3 could not fail and is RE-AIMED.** *"Loose `0755` parent → quarantine → a subsequent
>   publication succeeds"* passes identically before and after the quarantine, because publication
>   already succeeds at `0755` — N6 row 51 requires exactly that. Reachability, not discrimination. It
>   now asserts what the quarantine must actually preserve: **every entry under `bases/` is byte-identical
>   across the sweep, and the set of entries is unchanged.**
> * **Addition 1 survives, re-aimed.** It protected a file named `base`, which no longer exists. The
>   sweep moves *files* out of `~/.claude/unleashed-mail`; `bases/` is a directory and is out of its
>   reach structurally — but that is now stated as the reason rather than left to a clause that guards a
>   deleted filename.

**Proof — N4 (strengthened in round 3):** asserting only that the fallback is unreadable is satisfied
the moment D′'s guards land, **even if the quarantine never happens**. So N4 must also prove the move
occurred safely: every source file **absent** from the old location, each quarantine directory holding
the **exact inventory**, and **every checksum matching**. The `-inline` file is quarantined separately
with its own inventory.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| **ACLs cannot be enumerated on every platform** | **Low** | **Round 48 — the remaining limit is the unenumerable PLATFORM only. `default:` entries were a live injection path and are checked as of round 48.** Round 30 reversed round 29's blanket acceptance. Darwin refuses per ACL-2 — an `allow` ACE for another principal naming ANY right outside its seven-right read-only allowlist — which this row references and does not restate. The mutating-right formulation that stood here is the blacklist N6-7 forbids **by naming this very row**, and it fails open in a measured way: `chmod +a "everyone allow append"` prints `allow add_subdirectory` (executed), a token on nobody's list of mutating rights, so the component passes and another uid can create children in it (`deny` ignored, read-only `allow` accepted — measured, `$HOME` here carries `group:everyone deny delete`). Where no enumerator exists **the pointer path is refused**, not accepted on mode bits alone *(round 31, codex #7 — the round-30 text had this fail OPEN)*; CI stays green because ACL-4's absent-enumerator carve-out lets a publisher re-verify its own entry without an enumerator — **not** because "the harness exports its own `CLAUDE_PLUGIN_DATA` and never takes the pointer path", which round 54 refuted: exporting the variable makes the harness a PUBLISHER, so it takes the publish path rather than avoiding it. *(Superseded round-29 text follows.)* **Accepted limit, stated not hidden** (round 29, codex High #3). Authentication tests ownership, mode bits and symlinks; a macOS ACL can grant another uid write access to a root-owned `0755` ancestor and pass every clause. Defended: same-uid accident and mode-bit misconfiguration. **Not** defended: an attacker already holding an ACL grant on an ancestor of the data dir — who, on this platform, already has write access to the user's files by other routes. Enumerating ACLs needs a portable query the shell family does not have (`ls -le` is BSD-only and parsed nowhere here), and a half-implemented check would read as protection while providing none. Tracked as **COREDEV-2617a**; §4.2a states the limit in place |
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

**Source-time budget (round 44).** The resolver is sourced by five libraries in every hook, so its cost
is asserted, not assumed — and it is **derived from the predicate rule, not stated independently of
it**. A publisher runs the complete follower predicate, ACL clauses included (§4.2a), so a hook pays the
ACL cost too; the budget therefore bounds **how many times** that walk runs, not whether it runs: **at
most one ACL walk per PROCESS ON THE READ PATH**, because the protocol variables are set once and
the five sourced libraries share them. **A PUBLISHER walks more than once by construction and BUD-1
governs that count — this cap is the reader's and is not a bound on the publish path.** A **READER** resolution's wall-clock time is **RECORDED and gates nothing** — see BUD-1, which states why: the cost is linear in components, nothing bounds a target's depth, and every ceiling tried so far (50 ms, then 400 ms) rejected a CONFORMING implementation. **No figure is restated here**, because the 50 ms one stood in both places and a fix to one would have left the other governing. The GATE on this path is the derived invocation count.

> **ROUND 46 — the round-44 budget said "a HOOK resolution performs zero `ls -lde`/`getfacl`
> invocations", re-asserting in §6 the exact claim round 40 withdrew in §4.2a.** Third occurrence of
> this oscillation: round 35 asserted it, round 40 withdrew it, round 44 restored it one section away.
> A budget stated independently of the rule it prices will drift from it; this one is now written as a
> consequence of the rule. *(The superseded wording added "it takes step 1 and never authenticates a
> store" — false, because a publisher authenticates the entry it is about to leave. Round 44's own note
> stands: §4.2a had promised a §6 budget that §6 never set, the fourth such absent-edit claim.)*

Mutation proofs **N1–N6**, each shown failing before the fix and passing after. *(Round 34, codex #3: this operative line still said N1–N5 while the amendment below it says N1–N6, so **the entire pointer mutant suite could be omitted while satisfying the literal verification rule.** Rule versus note again — the eleventh instance, and in the section that exists to enforce the others.)* *(Round 7: this list
said N1–N4, so N5 — the one purely structural check in the set, with no behavioural counterpart —
carried no adversarial mutant and could have shipped unproven. Its mutant is specified in §7 step 5.)*

> **ENUM TOTALITY IS DERIVED, NOT ASSERTED** (round 29). `_UNLEASHED_POINTER_STATE` has now been
> incomplete **twice** — round 25 left lock contention with no value, and round 28's fix for that left
> the `CONFLICTED`-skip path with no value, one bullet away. Both times the prose said the enum was
> total. So totality is no longer a sentence: **every exit path of the publish routine **and of the reader**
> must be enumerated, each mapped to exactly one enum value, and the mapping checked against the declared value
> list.** An exit with no value, or a value not declared, fails verification. N6 rows 59, 60 and 96
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

   > **ROUND 35 — §7 HAD NO STEP FOR D″ AT ALL.** "The chosen resolution" was written for D′ in round 3
   > and never revisited, so a plan specifying a per-publisher store, an encoder, ordered reader rules,
   > a publish side effect, an ACL predicate and **a mutant table** carried an implementation order that
   > never mentioned any of them. Steps 3a-3e are that order. *(Twelfth instance of the same class: the
   > design moved and the section that tells someone how to build it did not.)*

   **3a. The store and the encoder.** `bases/` created `0700`, ancestor created if missing; the
   walk **exactly as Invariant P defines it** (byte walk, `LC_ALL=C`, four markers); the `NAME_MAX`
   budget against the
   **temp** name. Prove injectivity first, on the rows N6-5 assigns to this step, because every later
   step assumes it. **This step names no row numbers of its own.** The list it used to carry cited row
   86, which is struck — N6-1 prohibits citing a struck row — and omitted rows N6-5 assigns here. A
   second enumeration of an assignment drifts from it; there is now one assignment, in N6-5.

   **3b. The shared predicate.** `_unleashed_auth_entry` composed with the target-chain clauses, ONE
   function called by both publisher and reader, plus the ACL arm selected by `/usr/bin/uname -s`. The mutant rows are the ones N6-5 assigns to this step.

   **3c. The reader.** The scan (with the `ZSH_VERSION` guard) and the ordered rules **−1 through 4**
   (RD-2 prohibits a "rules 0-4" enumeration anywhere, because it silently drops the store-
   authentication rule). The mutant rows are the ones N6-5 assigns to this step; the list that stood
   here cited row 47, which is struck.

   **3d. The publisher.** Publish-then-scan, the temp-name uniqueness, and the enum mapping over every
   exit. The mutant rows are the ones N6-5 assigns to this step; the range that stood here swept in rows 83 and 84, both now struck.

   **3e. The five copies.** All four protocol variables established by each, `agent-env-bridge.sh`
   included, and arm equivalence asserted across them. The mutant rows are the ones N6-5 assigns to this step.
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
   (`scripts/tests/test_doc_gates.py:39-47`; `agents/swift-reviewer.md:180-193` documents the same rule
   for the current inline bridge). `agent-env-bridge.sh` takes the data value as **`$1`** and the plugin
   root as **`$2`**, exports the data value, then performs the shared source-time resolution.

   **The helper's body, stated rather than implied — round 16.** *(gemini: the signature and the
   `paths.sh` sourcing were specified and the body was not, so an implementer had to invent the
   empty-`$1` handling that keeps D′'s state space correct. codex traced the same path and found the
   behaviour **derivable** from the shared resolver contract — both are right, and the cheap fix is to
   write it down.)*

   ```bash
   # agent-env-bridge.sh — $1 = CLAUDE_PLUGIN_DATA value, $2 = CLAUDE_PLUGIN_ROOT
   # NON-AUTHORITATIVE: $1 is substituted from agent content, not exported by the host, so this
   # shell must never publish. The flag is set BEFORE the source because paths.sh publishes at
   # source time — after it, the entry is already written. (Round 42, codex High #1: the step-1
   # RULE said the fence sets this "before sourcing" and this BODY never set it at all.)
   _UNLEASHED_PUBLISH_OK=0
   export CLAUDE_PLUGIN_DATA="${1-}"          # empty is preserved, NOT unset: see below
   # GUARDED, exactly as marker.sh:27-30 guards it — paths.sh is an optimisation of
   # maintenance, NOT a load-bearing dependency (paths.sh:20), so an absent file must
   # take the same no-persistence path, never abort.
   if [ -z "${_UNLEASHED_PATHS_SH_LOADED:-}" ] && [ -r "$2/scripts/lib/paths.sh" ]; then
       . "$2/scripts/lib/paths.sh"
   fi
   # ALWAYS establish the protocol — the fence has no inline fallback of its own, so if the
   # helper returns without setting it, "unset => unresolved" would fail the fence CLOSED
   # on a perfectly valid base. Round 18.
   #
   # ROUND 34 (codex High #2): this branch used to consult only CLAUDE_PLUGIN_DATA and set
   # only _UNLEASHED_BASE_OK — i.e. it was D'-ONLY. With an empty $1, paths.sh absent and one
   # valid entry in the store, this fifth copy failed closed while the other four resolved
   # via the entry, which is the exact contradiction N6 row 65 claims to close. The inline
   # fallback must therefore run the SAME three-step resolution the other four carry, and
   # establish all FOUR protocol variables, not one.
   if [ -z "${_UNLEASHED_BASE_RESOLVED:-}" ]; then
       if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
           _UNLEASHED_BASE_RESOLVED="$CLAUDE_PLUGIN_DATA"
           _UNLEASHED_BASE_OK=1; _UNLEASHED_BASE_SOURCE=host-env
           _UNLEASHED_POINTER_STATE=none          # this copy never publishes; see below
       else
           # step 2: enumerate the store and apply the ORDERED reader rules −1 through 4, as
           # the other four copies do. Same predicate, same order, same enum.
           <the shared three-step resolution, inline>
       fi
   fi
   ```

   > **ROUND 36, codex High #3 — the paragraphs BELOW this body still described the D′-only behaviour
   > the body was changed to remove**: empty and unset yield the sentinel, no persistent read, no helper
   > conditional needed. An implementer following them reproduces exactly the failure row 65 exists to
   > catch. **Thirteenth rule-versus-note instance, and the first INVERTED one — I fixed the rule and
   > left the explanation.** Those sentences are struck; the body above is the rule. The publish
   > exception is lifted into the operative step-1 statement too, since step 1 mandates publication for
   > any non-empty value and this copy is an exception to it.

   **This copy resolves but does not PUBLISH**, and that asymmetry is deliberate and stated: the fence
   runs in a Bash-tool shell whose `$1` is substituted from agent content, so a publish here would write
   an entry on behalf of a shell that is not an authoritative hook. It therefore reports
   `_UNLEASHED_POINTER_STATE=none` on the resolved path. **Arm equivalence is asserted on the four
   protocol variables for the READ path only**, which is the only path this copy has. N6 row 65 is
   re-aimed at that, and it covers the fourth variable too — row 84, which used to be cited here, is
   struck as a duplicate of row 73.

   *(Round 17, BOTH arms: the round-16 body sourced `paths.sh` **unconditionally**. In the documented
   absent-file mode that emits a raw shell error — **Bash returns 1, zsh 127** (codex measured both) — the
   sentinel and `_UNLEASHED_BASE_OK` are never established, and an `errexit` caller **terminates**. It
   contradicted §4.3's non-load-bearing contract, which every shipped lib honours with exactly the
   `[ -r … ] && .` guard this now copies. I wrote a four-line body to close "the mechanism is unspecified"
   and omitted the one line that makes it safe.)*

   **When `paths.sh` is absent** the helper's resolver is not defined — so the helper performs the
   resolution **itself**, inline: a non-empty `$1` resolves to it (`host-env`); an empty or unset `$1`
   **runs step 2 against the store**, falling to the sentinel only if step 2 resolves nothing, and
   emitting the single diagnostic then. All four protocol variables are established either way.

   > **ROUND 48, codex High #3 — this paragraph still said the helper derives the flag "from the value
   > it was handed", i.e. D′-only.** Round 38 struck a DIFFERENT paragraph making the same claim and I
   > treated the family as closed; this is its fourth site. Stated as a standing rule: **the bridge's
   > inline fallback runs the same three-step resolution as the other four copies**, and any sentence
   > implying it derives only from its argument contradicts it.

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
   so an empty `CLAUDE_PLUGIN_DATA` takes the same branch as an absent one. **Under D″ that branch runs
   step 2** — enumerate the store, apply the ordered reader rules — and reaches the sentinel only when
   step 2 finds nothing to resolve. The helper still needs no conditional of its own: the conditional
   lives once, in the resolver, which is the entire point of the bridge.

   > **ROUND 38 — THE ROUND-36 NOTE SAID THESE SENTENCES WERE STRUCK. THEY WERE NOT.** They went on
   > saying the branch *"yields the poisoned sentinel … and no persistent read or write"*, which is D′,
   > for a full round after the body above was changed to run step 2 — so an implementer following the
   > prose returns `OK=0` for empty `$1` + absent `paths.sh` + one valid entry, violating acceptance
   > conjunct 1, arm equivalence, and row 65. **A note asserting an edit that never happened is worse
   > than the stale text alone, because it stops anyone looking.** This is the same failure as round
   > 32b's commit message describing work an aborted script had discarded — fourteenth instance, and the
   > second time I have *claimed* a fix rather than made one. Struck here, and verified by re-reading.

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
   (`scripts/lib/paths.sh:11-14`, `scripts/tests/test_shell_primitive_drift.py:153-157`). It would have
   expanded to `. "/paths.sh"`. It also fails under Bash for a basename-only invocation, where `%/*`
   leaves the filename untouched. **The fence already knows the root — `${CLAUDE_PLUGIN_ROOT}` is
   substituted there — so the helper should be told it, not made to rediscover it.** Passing it as `$2`
   is cross-shell by construction and removes the self-location problem rather than solving it.)*

   **Third consecutive round in which the mechanism I wrote in response to a finding was itself
   defective** — an unbraced variable, then a substitution that does not reach sourced files, now a
   Bash-only array in a zsh context. Each was checkable against evidence already in this repository. *(gemini, round 14: "share one code path" was stated without a mechanism, so an
   implementer had to choose between duplicating `paths.sh` — contradicting the claim — and inventing
   `BASH_SOURCE` resolution the plan never mentions.)*

   **3f. The harness seams.** The two seams every cell above depends on, which had mutant rows and no
   step. (i) The **`HOME` sandbox** PUB-12 and HAR-1 require: each cell runs in a fresh shell with
   `HOME` pointed at a scratch directory, so no cell reads or writes the developer's real
   `~/.claude/unleashed-mail/bases/`, and the `HOME`-unusable cell sets `HOME=""` rather than
   unsetting it, because zsh repopulates an unset `HOME` from passwd while bash leaves it unset.
   (ii) The **single-accessor fixture seam**: every mode, size and owner assertion goes through the
   ONE P-2 call, so a fixture cannot pass by consulting a different accessor than the implementation
   uses — the defect that let a nine-bit comparison read as an exact-mode test.
   (iii) The **probe seam**, on the same single-accessor principle and for the same reason: the
   IDENTITY probe (`/usr/bin/id -un`, P-3a), the `NAME_MAX` probe (`/usr/bin/getconf`, NM-1) **and the
   ACL ENUMERATOR'S OUTPUT** (`/bin/ls -lde`, ACL-2/ACL-5) are
   each reached through ONE accessor that production and the harness share, so a fixture can present
   a FAILED probe **or a MALFORMED ACE LINE or ANSWER, which rows 144-151 require and `chmod +a`
   cannot produce**. Both are invoked by absolute path, so no unprivileged harness can make either fail
   by manipulating `PATH` — and without this seam rows 131 and 133 prescribe fixtures that cannot be
   built, which N6-10 forbids. *(Round 106, codex: 3f seamed P-2's accessor only, while round 104
   added a row whose fixture needs the identity probe to fail.)* The mutant rows are
   the ones N6-5 assigns to this step. *(Round 66: N6-5 assigned rows 54 and 71 to "the steps that
   build the harness `HOME` sandbox", and §7 had no such step — two live rows owned by nobody, in a
   sentence that read as though they were assigned.)*

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
   | `stop-quality-marker-gate.sh` — **`:74`, `:129`, `:132`** | **the destructive ones.** `:74` composes `SENTINEL="$(marker_dir)/…"`; `:129` runs `mktemp "$(marker_dir)/.stopgate.XXXXXX"`; `:132` runs `mv -f "$_STMP" "$SENTINEL"`. On an unresolved base these **create and move files under `/.state/`**. Round 3 guarded only `:131-132`. Guard the whole script at entry |
   | `pre-commit-checks.sh` — **`:47` and `:72` too** | round 3 listed only the **fail** cases (`:44`, `:69`); the **pass** cases were unguarded, so a *successful* run wrote to a root path |
   | `swift-lint-check.sh` — **`:67` too** | the early syntax-error exit writes a marker before `:425` is reached |
   | *(historical — round 3 record, not control flow; the operative row is `reviewer-roster.sh` above)* | `reviewer-roster.sh:53` | `BASE="$(context_reviews_dir)/…"` composes `/reviews/…` and passes it to `context_latest_round_dir` (`:180`) — a root-directory **read** |
   | `agents/swift-reviewer.md:266-269` | **perform no filesystem read at all** and emit the existing `NO CAPTURE (unresolved)` result for **each** reviewer — the fence composes the path *and reads through it*, so "compose nothing" is not by itself a complete instruction. *(Rounds 3 and 4 both left this row restating that no control flow was supplied; round 5 supplies it.)* |
   | `build-failure-log.sh` (`:40`) · `stop-failure-log.sh` (`:36`) · `permission-denied-log.sh` (`:40`) | **round 12 — these three had no control flow at all.** Each calls `log_append` exactly once as its terminal action. On an unresolved base `log_append` is a **no-op returning 0** (§7's writing-primitive rule), so the hook's own behaviour is unchanged: it still exits 0 and still emits whatever the hook contract requires. **No per-script guard is needed or wanted** — adding one would duplicate the primitive's contract. Stated explicitly because "the primitive handles it" is a decision, not an omission |
   | `capture-reviewer-round-start.sh` (`:46`) | calls `context_review_round_bind`, whose unresolved contract is **print nothing, return 0**. The call site already discards stdout and forces success (`>/dev/null 2>&1 \|\| true`), so the hook is unaffected. **Fail-open**: a missing round binding degrades to inference, which is the documented fallback |
   | `capture-reviewer-verdict.sh` (`:49`) | composes `ROOT="$(context_reviews_dir)"` — a **sentinel** path when unresolved. **Skip the capture entirely and exit 0**; do **not** attempt the write, and do not fail the reviewer's own run. `capture.py` composes only beneath this `ROOT`, so it is covered transitively (codex, round 11) |
   | `precompact-snapshot.sh` (`:64`) · `sessionstart-restore.sh` (`:61`) | **round 10 — both were entirely absent from this table.** Each composes `SNAP="$(context_snapshot_path)"` and writes/reads the snapshot inline. On an unresolved base: **skip the snapshot write and the restore**, and leave every other behaviour (the hook's own output, its exit code) untouched. **Round 19b — §4.2a carves `sessionstart-restore.sh` out of "the hook's own output … untouched":** it is now the one consumer whose output *does* change, emitting a single non-blocking `additionalContext` line, still `exit 0`. Note the amended predicate — the line fires on `conflict`, `stale` or `failed` — **not** "when the non-hook path will fail", since `none` also leaves the non-hook path unresolved and is deliberately silent (SS-1) — **not** when this hook's own base is unresolved, which in a hook is unreachable |
   | `scripts/test-hooks.sh` — **`:624`, `:804`**, and **`:446`** | the harness itself calls `context_snapshot_path`. N1/N2 must run with the variable **unset**, so **the test that verifies D′ could compose root paths**. Guard before the fixtures run. *(Round 7 adds `:446` — `[ -s "$CLAUDE_PLUGIN_DATA/logs/stop-gate.log" ]` composes from the raw variable directly, not through a resolver, so it is a third site of a different kind and the one that proves N5's old predicate was blind.)* |
   | `swift-reviewer.md:266` and the roster's `:53` | both **append to the resolver result** — an empty result composes a root path |

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
   >   correct as a count: the canonical resolver in `paths.sh` plus the three **deliberate inline fallbacks**
   >   in `marker.sh`, `log.sh` and `context.sh`. **The line numbers that stood here named the
   >   `# shellcheck source=` directive above each fallback, not the fallback**, and §1's own round-30
   >   correction already gave different numbers for the same three sites — two pins for one fact,
   >   disagreeing. The allowlist is keyed by FILE in the shipped test, so no line number belongs here
   >   at all. Those three are load-bearing by design, not drift
   >   — `paths.sh:11-20` explains that these libs are sourced standalone and that making them abort would
   >   convert three fail-open paths into one shared point of failure. N5 must pin them, **not** delete
   >   them.
   > - **Scan set includes the executable fences in `agents/**` and `skills/**`.** An agent body that
   >   tells the model to compose the path is the same defect shipped as prose, and
   >   `agents/swift-reviewer.md:266-269` is already on §7's guard list for exactly that. The MAJ-6 bridge
   >   in `swift-reviewer.md`'s two MAJ-6 fences — which pass the value as a bridge ARGUMENT, not as the
   >   `export CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}"` line cited here, a spelling that exists
   >   nowhere in `agents/`, `skills/` or `scripts/` at HEAD
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
| 3 | gemini | `swift-lint-check.sh:67` (early syntax-error exit), `reviewer-roster.sh:53` (composes `/reviews/…` for a root **read**), `swift-reviewer.md:266` (no control-flow requirement) | **confirmed** | all three added |
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
| 1 | codex | **`${BASH_SOURCE[0]%/*}` is not portable to the runtime this bridge targets.** `BASH_SOURCE` is a **Bash-only** array; a sourced file's shebang cannot force the interpreter; and this repo explicitly identifies the agent-fence path as a **zsh** Bash-tool context (`scripts/lib/paths.sh:11-14`, `scripts/tests/test_shell_primitive_drift.py:153-157`). In zsh it expands to `. "/paths.sh"` and fails. It also fails under Bash for a basename-only invocation, where `%/*` leaves the filename unchanged | **confirmed** — both cited sources describe the zsh context directly | the helper no longer locates itself: **the fence passes the root as `$2`** and the helper does `. "$2/scripts/lib/paths.sh"`. Cross-shell by construction — the problem is removed rather than solved |

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
