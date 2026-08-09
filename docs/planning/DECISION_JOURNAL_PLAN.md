# Decision Journal Plan

**Status:** **Planning — round 2, revised and UNPAUSED.** Round 1 ran gemini `APPROVE_WITH_NOTES` /
codex `REQUEST_CHANGES`; those findings are recorded verbatim in §10 and each is answered in §11.
**Still not approved — do not implement until round 2 returns two approving verdicts that reproduce
at the same digest.** Both reviewers independently recommended splitting the live redactor defects
(§4.7) into a prerequisite ticket — done, as `COREDEV-2597`, which is no longer in this plan's scope
and which **has since landed** (§7 step 1).
**Created:** 2026-07-29
**Last Updated:** 2026-08-08 (round 2 — decoupled from `COREDEV-2584`; schema, locking, run identity,
quarantine and proofs specified; version re-targeted)
**Ticket:** `COREDEV-2585` — Decision journal: model-written checkpoints (append-only journal +
rewritten live-state)
**Epic:** `COREDEV-2582` — Opus 5 readiness and autonomous end-to-end mode
**Branch:** `feat/COREDEV-2585-decision-journal`
**Target version:** **`2.7.2`** (patch: no asset-count change — see §2 for the exact baseline).

> **The Epic's original release chain is VOID, and pretending otherwise is how this plan acquired a
> false dependency.** It read `2.6.0 (COREDEV-2583) → 2.7.0 (COREDEV-2584) → 2.7.1 (this)`. Every one
> of those numbers has since been consumed by *other* tickets while 2583 and 2584 stayed unlanded:
> 2.6.2 (`COREDEV-2597`), 2.6.3 (`COREDEV-2598`), 2.7.0 and 2.7.1 (`COREDEV-2642`, merged
> 2026-08-09 as PR #66). A version chain is not a dependency graph. This plan therefore targets the
> next free patch, **2.7.2**, and asserts **no** version for its siblings — they take whatever is free
> when they land.

**Depends on:** `COREDEV-2597` (redactor defects) — **LANDED as v2.6.2**, commit `929c160`. §7 **step 0**
is a verification step, not outstanding work, and §7 records the gaps that verification found.

> ### ⛔ A REAL dependency, found in round 2 — and it is the one nobody was looking for
>
> **`COREDEV-2617` §4.2a (D″) must land before this ticket does anything useful.** §4.5b specifies that
> the model writes a checkpoint by invoking `scripts/journal-checkpoint.sh` **through the ordinary
> `Bash` tool**. Under D′ that path cannot write, because `CLAUDE_PLUGIN_DATA` is exported to hooks and
> MCP subprocesses **but not to the Bash tool**. Executed in a live Bash tool call at `dbb1fb8`:
>
> ```
> CLAUDE_PLUGIN_DATA = [UNSET]
> base=/dev/null/unresolved-plugin-base   ok=0
> ```
>
> So **every model-written checkpoint — the entire point of this ticket — would be a silent no-op**,
> while the hook-written half kept working. The journal would ship, pass its own hook-side tests, and
> record nothing the model ever decided.
>
> **D″'s step 2 is exactly the mechanism that fixes it:** the hooks, which do have the variable, publish
> a pointer file; the Bash-tool shell, which cannot know the base, reads it and converges on the **same**
> store. Without step 2 this ticket needs its own private answer to a question `COREDEV-2617` is already
> answering — and two answers to that question is precisely the split-brain both tickets exist to prevent.
>
> **The irony is recorded rather than hidden.** This round's headline change was *removing* a dependency
> on `COREDEV-2584` that proved to be a plan-ordering preference. The verification sweep then found a
> dependency on `COREDEV-2617` that **nobody had stated** and that is load-bearing. A declared dependency
> was false; an undeclared one was real. Round 1 reviewed the declared one twice and neither arm caught
> the real one, because the two plans were read separately and the coupling exists only where they meet.

**Ordering: this plan is INDEPENDENT of `COREDEV-2583` and `COREDEV-2584`.** Round 1 asserted a hard
`2583 → 2584 → 2585` chain. That was never a technical dependency — codex round-1 finding 5 caught the
plan contradicting itself, because §4.6's own reviewer note already said "either order works". The
entire coupling was one row of one table: the `brainstorm` fork checkpoint recorded rationale *next to*
a sidecar `COREDEV-2584` introduces. §4.6 now records that rationale in a store **this plan owns**, so
the coupling is gone in the only direction that mattered — the journal never reads, writes or requires
2584's sidecar. What remains is a one-way *enhancement*: if 2584 has landed, its sidecar and this
journal describe the same fork from two sides, and §4.6 says how they are correlated without either
depending on the other. **Maintainer decision, 2026-08-08: decouple.**

---

## 1. Context

Compaction destroys the reasoning behind decisions, not the decisions themselves. The plugin already has
a pipeline that tries to soften this, and it works exactly as designed — the problem is what it is
structurally capable of.

**What ships today.** `scripts/precompact-snapshot.sh` (PreCompact, `hooks/hooks.json:95-105`, timeout
10) writes a single-line JSON object with exactly five keys — `ticket`, `branch_slug`, `plan`, `round`,
`snapshot_time` (`:67-68`). `scripts/sessionstart-restore.sh` (SessionStart, empty matcher) reads four of
them, emits **one** line of `additionalContext` from a fixed template, caps it at 400 chars (`:76-78`),
deletes the snapshot so it restores exactly once (`:82-84`), and drops anything whose file mtime is
600 s or older (`:47-49`).

It is PII-safe by construction, and that claim survives scrutiny: `context_branch_slug`
(`scripts/lib/context.sh:143`) returns a `COREDEV-NNNN`/`vX.Y.Z` token, else a 12-hex hash, else the
literal `unknown` — there is no code path that returns raw branch text. Verified by running it:
`fix/john.doe@corp.com-x` → `a4d667655d5a`.

**The structural problem.** `scripts/precompact-snapshot.sh` is a **bash hook with no model access**. It
never calls `hook_io_read` and never touches `HOOK_STDIN` (grep for `hook_io_read|hook_str|HOOK_STDIN|
trigger` in that file returns nothing). All it can do is scrape the filesystem: the newest plan file by
mtime, the highest round directory, a branch-derived slug. **It cannot summarize the conversation —
which is precisely what compaction destroys.**

So the fix is not a bigger snapshot. Doubling the field count would still capture only filesystem facts,
all of which the model can re-read for itself. **The fix is changing *when* the information is
written:** at a checkpoint, by the model, while it still has the context to know what mattered.

**Maintainer decisions locked before this plan was written** (do not re-litigate in review):

| Decision | Value |
|---|---|
| Design | **A+C hybrid** — append-only `journal.jsonl` (the record) **plus** rewritten `live-state.json` (the payload) |
| Restore cost | **O(1)** regardless of run length; budget ~1.5–2 k tokens |
| Location | Under `context_base()`, per-checkout namespaced by `context_repo_hash()` |
| `PostCompact` | **Not on the table.** See §2. |

## 2. Scope

**In:** the two-file journal design and its schema; the checkpoint set; the model-written write path and
the hook-written mechanical path; PII handling for free-text rationale; run-scoped freshness replacing
the flat 600 s TTL; journal self-compaction; the correctness defects in the existing restore path that a
journal inherits if it reuses the same shape (§4.2–§4.4).

**Out:** the Opus 5 alignment work (`COREDEV-2583`) and autonomous mode (`COREDEV-2584`). No change to
the reviewer capture pipeline, the synthesizer, or the verdict contract.

**The baseline, stated unambiguously — codex round-1 finding 5.** Round 1 hedged: "`21/21/0/1` holds
(or `21/22/0/1` if `COREDEV-2584` has already landed; this plan must not assert either number)". A plan
that cannot say what it starts from cannot say what it changes. Decoupling (§4.6) removes the
conditional, and the baseline is now a measurement rather than a prediction — taken on this branch's
merge-base, `dbb1fb8` (v2.7.1):

| quantity | value | measured by |
|---|---|---|
| agents / skills / commands / MCP | **21 / 21 / 0 / 1** | `validate-plugin-assembly.py --strict`, `validate-version-sync.sh` |
| hook **events** | **10** (12 invocations, 11 scripts) | `validate-hooks.py --strict --require-manifest` |
| plugin version | `2.7.1` → this ticket targets **2.7.2** | `.claude-plugin/plugin.json` |

**This ticket moves none of them, and that is a design constraint rather than an observation.** It adds
exactly one script (`scripts/journal-checkpoint.sh`, §4.5b) and modifies two existing hook scripts. A
script under `scripts/` is not a counted asset; **no new agent, no new skill, no new command, no new MCP
server, and — settled below — no new hook event.** If an implementer finds themselves adding one, the
design has drifted and this plan is the thing that is wrong.

**No new hook event, so no new kill switch is named — because naming one would be fiction.** Codex
finding 5 observed that §4.12 hedged with "if this ticket adds a hook event" and then named no event and
no switch. The hedge is resolved in the only honest direction: the model-written path is a **script the
model invokes** (§4.5b), not a hook, and the two hook-side changes land in `precompact-snapshot.sh` and
`sessionstart-restore.sh`, which are **already registered** on `PreCompact` and `SessionStart` and
already carry their own kill switches. The event count stays **10** and §4.12's documentation edits
reduce to the hook-table row for behaviour that changed, not for an event that did not appear.

**Out — done elsewhere:** the three `hook_redact_pii` defects (`sk-`/`pk_` boundary, `~` path
context, `tr` locale/stderr) and their tests. Split out as `COREDEV-2597` on both reviewers'
independent recommendation and implemented there. This plan DEPENDS on that work; it does not
contain it.

**Explicitly out of scope, with the reason recorded so a future reader does not re-investigate:**
`PostCompact`. `scripts/sessionstart-restore.sh:4-8` already documents why, and it is correct:

> The documented post-compaction context-delivery point: PostCompact CANNOT inject context
> (decision-control "None"), so restore lives on SessionStart with source=="compact" (and,
> as a freshness-windowed bonus, resume/startup).

Corroborated at `docs/planning/OCTO_ADOPTION_PLAN.md:252` (a round-2 codex-review correction verified
against the live hooks reference) and flagged again at `OPUS5_ALIGNMENT_PLAN.md:394-395` as "correct and
already correctly resolved". Restore stays on `SessionStart`.

## 3. Guiding principle

> **Never carry anything the model can re-read.** Recoverable state — plans in `docs/planning/`, verdicts
> in `.verdicts/`, reviewer findings in `reviews/`, Jira — gets a **pointer**. Only *irrecoverable
> reasoning* gets spent tokens.

This is what bounds the token budget and it is also the design's main defence: the smaller the set of
things worth persisting, the less free text there is to leak (§4.7).

The second principle follows from the first and is the whole point of the `live-state.json` half:
**summarization happens at WRITE time, when full context exists — not at read time, when it doesn't.**
Because `live-state.json` is *rewritten* at each checkpoint rather than appended to, the model is forced
to decide what is *still true* every time. A file that only grows can only be summarized by a reader who
has already lost the context needed to do it well.

---

## 4. Findings, fixes, and proofs

### 4.1 — The producer is a bash hook and cannot summarize anything (High)

**Root cause.** Established in §1: `scripts/precompact-snapshot.sh` never reads stdin, so it has no
conversation, no `trigger` field, and no `custom_instructions`. Every one of its five fields is a
filesystem derivation. Two of them are not even reliable derivations:

- `plan` is `ls -t "$_root"/docs/planning/*_PLAN.md | head -1` (`:29-37`) — the **newest plan by mtime**,
  not the plan being worked on. A `git checkout` or an unrelated `touch` re-orders it.
- ~~`round` is computed by an **inline** glob loop~~ — **STRUCK IN ROUND 2. This claim was false, and it
  was false in a way worth recording.** Round 1 read `scripts/precompact-snapshot.sh:41-49` as the
  implementation. It is a **comment describing the removal** of that inline loop by `COREDEV-2600`
  (`cf2c44b`) — the comment even quotes the old defect (`round-09` recorded `"09"`), which is what round 1
  then reported as current behaviour. The live computation is `:50-58` and calls the shared
  `context_highest_round` at **`:56`** (`scripts/lib/context.sh:196`). Re-run with round 1's own fixture
  (`round-3`, `round-09`, `round-abc`): the snapshot recorded **`"round":"9"`**, stderr empty, rc 0.
  So the `10#` normalisation, the `??????*` digit cap and the zsh `NOMATCH` guard are all **already in
  effect**, and there is nothing here for this ticket to fix. A plan that "verified experimentally" a
  behaviour the tree had already fixed did not run the experiment it reported.

**Fix.** Keep the mechanical hook for mechanical facts, and add a **model-written** path for reasoning.
The division is the design:

| Written by | What | When |
|---|---|---|
| Hooks (bash) | mechanical facts — ticket, slug, plan pointer, round, timestamps | already happens; `SubagentStop` capture is the working precedent |
| Model | rationale — why a fork was taken, what was rejected and why, what was tried and abandoned | at checkpoints (§4.6) |

**Note for the reviewer.** The hook half is not speculative: `SubagentStop` →
`scripts/capture-reviewer-verdict.sh` → `mcp/review-synthesizer/capture.py` already persists structured
per-reviewer records with a passing 302-case harness. This plan extends an existing, review-hardened
pattern rather than introducing a new one.

**Proof.** Cases in `scripts/test-hooks.sh` (the existing stdin-contract harness) asserting the mechanical
record is written and that the model-written record is *absent* when no checkpoint fired — the two paths
must be independently observable.

### 4.2 — Two compactions silently lose the first snapshot (Medium)

**Root cause.** The second PreCompact **overwrites** the first. There is no history, no append, no
versioning. Verified by running the hook twice: the file is replaced (`snapshot_time` 1785296889 →
1785296891) and zero `.tmp` files remain.

"Fire-once" is therefore fire-once-**per-snapshot-file**, not per-compaction-event: two compactions
followed by one SessionStart restore exactly one hint — the newest — and whatever the first captured is
gone.

**Fix.** This is exactly what the append-only half of the design solves. `journal.jsonl` receives one
line per checkpoint and is never overwritten; only `live-state.json` is rewritten. A second compaction
costs nothing because the record is not the payload.

**Proof — and round 1 got this proof wrong.** It proposed "two consecutive **checkpoints** produce two
journal lines". Codex finding 6 caught that this **cannot fail while the defect is present**: the defect
is that a second *compaction* overwrites the first snapshot, and two checkpoints exercise the journal
writer without ever invoking the PreCompact path. The test would pass on a build where the legacy
overwrite is fully intact.

The proof must therefore drive **two PreCompact events**, not two checkpoint calls: run the PreCompact
hook, checkpoint, run the PreCompact hook again, and assert that the record of the **first** compaction
is still present and readable afterwards. That case fails today and fails again if the append-only
property is ever lost. The two-checkpoint case is kept as well, but demoted to what it actually proves —
that `live-state` is rewritten rather than appended, reflecting the second checkpoint and not a merge of
both — and it is no longer offered as the proof for this finding.

### 4.3 — A corrupt or empty snapshot still injects a content-free hint (Medium)

**Root cause.** Restore never validates the JSON. Verified with a file containing `this is not json at
all`, and again with a zero-byte file: **both emitted the full hint with every slot `unknown`** —
`ticket=unknown, branch=unknown, plan=unknown, round=unknown` — and then deleted the file.

So the failure mode is not silence. It is content-free noise injected into the model's context, followed
by destruction of the evidence. `_snap_field` (`scripts/sessionstart-restore.sh:54-71`) returns the
literal `unknown` on any parse failure and the emitter never checks whether *all* slots degraded.

**Fix.** The journal's reader must **emit nothing** when the payload does not parse, when `v` is
unrecognised, or when every field is unknown. Emitting an all-`unknown` hint is worse than silence: it
spends tokens to tell the model nothing and looks like state.

**The corrupt payload is QUARANTINED, not retained in place — and this overrides round 1.** Round 1
proposed leaving the unparseable file at the active path as evidence, and gemini's §8 answer agreed.
**Codex finding 4 refuted that, and codex is right on all three counts:** the §4.10 GC as drafted
compacts only an oversized *journal* and would never collect a corrupt *live-state*; a file left at the
active path re-triggers the parse failure and its log line on **every** subsequent restore; and the
very next checkpoint rewrites that path, destroying the evidence the retention existed to preserve. The
proposal was self-defeating.

So: on a parse failure the reader **atomically renames** the payload to

```
<state>/quarantine/live-state-<repohash>-<t>-<seq>.json     # 0600, same filesystem, so rename is atomic
```

and leaves **no** file at the active path. Consequences: the failure is logged exactly once; the next
checkpoint writes a clean payload rather than colliding with a corrupt one; and the evidence survives
at a path nothing else writes. Quarantine is bounded by **both** a count (keep the newest 10) and a TTL
(14 days), swept by the same GC pass as §4.10 — a bound on only one of the two is how an "evidence"
directory becomes an unbounded leak.

**Proof.** Cases, each failing against today's behaviour and against the round-1 design: a corrupt
payload → zero bytes emitted, **nothing at the active path**, exactly one file under `quarantine/`,
exactly one log line; a second restore over the same corruption → **no second log line and no second
quarantine file**, because there is nothing left at the active path to re-read (this is the case that
fails under the round-1 retain-in-place design, and is why it is listed); an all-`unknown` but
well-formed payload → zero bytes emitted and **no** quarantine (it parsed; it is empty, not corrupt —
the two must not share a failure path); an unrecognised `v` → zero bytes, quarantined; and 11 corrupt
payloads → exactly 10 files retained, oldest evicted.

### 4.4 — `startup` and `resume` consume the snapshot and claim a compaction happened (Medium)

**Root cause.** `scripts/sessionstart-restore.sh:24-28` accepts `compact|resume|startup` and emits the
**same** text — "Context restored after compaction — resume prior work: …" (`:76`) — for all three.
Verified live with `{"source":"startup"}`.

Two consequences. A plain new session started within the 600 s window is told a compaction restore
happened when it did not; and it **burns the snapshot** the genuinely-compacted session would have used.
Only `clear` is excluded.

**Fix.** The journal reader distinguishes sources: `compact` gets the post-compaction payload and
consumes it; `resume`/`startup` may *read* the live state but must not consume it, and must not claim a
compaction occurred. The wording follows the source.

**Proof.** Cases asserting `source=startup` leaves the payload in place and emits source-appropriate
text; `source=compact` consumes. Today's harness (`scripts/test-hooks.sh:623-671`, cases 28–32) already
covers `clear` and staleness — extend rather than duplicate.

### 4.5 — The design: append-only record, rewritten payload (High)

**Fix.** Two files, both under `context_base()`
(`${CLAUDE_PLUGIN_DATA:-${HOME:-}/.claude/unleashed-mail}`, `scripts/lib/context.sh:61`), namespaced
per checkout by `context_repo_hash()`:

**`journal-<repohash>.jsonl` — the RECORD.** Append-only, one JSON line per checkpoint. Never read
wholesale by the restore path. Its readers are humans, audits, and the self-compactor (§4.10).

**`live-state-<repohash>.json` — the PAYLOAD.** Rewritten in full at every checkpoint. The **only** thing
the restore path reads. Fields carry *pointers* wherever the underlying artifact is re-readable
(§3): the plan path rather than the plan, the round directory rather than the findings, the ticket key
rather than the ticket body. Free text appears only where nothing on disk can reconstruct it.

Restore cost is O(1) in run length because the payload is a fixed-shape object, not a growing list.

**Note for the reviewer — the `branch` vs `branch_slug` trap.** The old design sketch at
`docs/planning/OCTO_ADOPTION_PLAN.md:258-262` shows a schema with a raw `"branch":
"feat/v2.2.4-shared-pty-wrapper"` field and asserts "all PII-free — a branch name is not PII". That is
**directly contradicted by the shipped code** (`scripts/lib/context.sh:8-13`: "A git branch name is
USER-CONTROLLED FREE TEXT … so it is NEVER persisted") and by the shipped snapshot, whose field is
`branch_slug`. The same doc gives the state path as `.state/work-context-snapshot.json` and calls it
"global (shared across checkouts)"; the shipped path is `…-<repohash>.json` and is explicitly per-checkout.
`docs/planning/` is a historical record — do not copy its schema.

**Note on keying.** `context_repo_hash()` hashes `git rev-parse --show-toplevel`, so **a worktree and its
parent checkout get separate journals** (verified live: main checkout `19c639948f86`, this worktree
`5e2ba3a91fbd`). That is correct for isolation and wrong for anyone expecting continuity across a
worktree switch. State it; do not silently inherit it.

**Proof.** Round-trip cases: checkpoint → both files written; restore reads only `live-state`; N
checkpoints produce N journal lines and one live-state whose content matches checkpoint N.

### 4.5a — The schema, exactly (High)

**Root cause.** Codex round-1 finding 1: the plan promised a schema and never defined one — no keys,
types, version, caps, identity, ordering or deduplication. "Two files under `context_base()`" is a
filesystem layout, not a contract, and an implementer would have invented the rest.

**Fix.** Both files carry `"v": 1` as their **first** key. A reader that does not recognise `v` emits
nothing and logs once; it never guesses. Bumping `v` is a deliberate, documented act.

**`journal-<repohash>.jsonl` — the RECORD.** One line, one JSON object, `\n`-terminated:

| key | type | cap / domain | notes |
|---|---|---|---|
| `v` | int | `1` | schema version; first key |
| `id` | string | `<run>-<seq>` | **checkpoint identity.** Unique per journal. A duplicate `id` is a no-op, not a second line — this is the deduplication rule |
| `seq` | int | ≥ 1, monotonic | **ordering.** Assigned under the §4.5c lock as `last seq + 1`; never derived from a clock, which can go backwards |
| `run` | string | 64 chars, `[A-Za-z0-9_-]` | the run identity of §4.5b. **Never empty** — a writer with no run id does not write |
| `t` | int | unix seconds | for humans and GC only; never an ordering key |
| `kind` | string | **closed enum**: `fork` \| `gate` \| `adjudication` \| `abandoned` | §4.6. An unrecognised value is rejected and nothing is written |
| `ticket` | string | 32 chars, `[A-Z]+-[0-9]+` or `unknown` | pointer (§3) |
| `slug` | string | 32 chars | from `context_branch_slug` — already PII-safe by construction (§1) |
| `plan` | string | 200 chars, repo-relative | **pointer**, never plan content |
| `round` | int | ≥ 0 | from the shared `context_highest_round` (`scripts/lib/context.sh:196`), which `precompact-snapshot.sh:56` already calls — §4.1's "inline scanner" is struck |
| `reason` | string | **closed enum** (below) | the bounded half of the "enum + short free text" both reviewers asked for |
| `note` | string | **200 chars**, redacted | the only free text. Cap matches the shipped precedent `scripts/permission-denied-log.sh:36` (verified: `REASON="${REASON:0:200}"`) |

`reason` enum — nine values, closed: `perf`, `complexity`, `platform-limit`, `security`, `scope`,
`dependency`, `maintainer-directive`, `superseded`, `other`. `other` exists so the enum never silently
forces a wrong code; a run where most records are `other` is a signal the enum needs extending, and
that is visible precisely because the field is closed.

**Whole-line cap: 1024 bytes serialized, asserted before the write.** Over-cap is a *failure*, not a
truncation — a silently truncated JSON line is an unparseable record, which is the §4.3 defect
manufactured on purpose.

**`live-state-<repohash>.json` — the PAYLOAD.** Same `v`, `run`, `t`, `ticket`, `slug`, `plan`, `round`,
plus `seq` (the seq of the checkpoint that last rewrote it) and two bounded lists:

- `open`: ≤ **5** objects `{kind, note}` — what is still true and still undecided.
- `rejected`: ≤ **5** objects `{reason, note}` — paths closed, so they are not re-proposed after a
  compaction. This is the single highest-value field and the reason the file is rewritten rather than
  appended (§3).

**Whole-payload cap: 2048 bytes serialized, asserted.** Codex finding 6 is right that a fixed *shape*
does not bound tokens — only a byte cap does. 2048 bytes is ≈ 512 tokens, comfortably inside the
1.5–2 k budget of §1 with the restore preamble on top. When a list is full the **oldest** entry is
dropped, and the drop is recorded as a `journal.jsonl` line so the record still has it.

**Proof.** Per-field cap cases (a 201-char `note` is rejected, not truncated); an unknown `kind` and an
unknown `reason` each write nothing; a duplicate `id` produces no second line; `seq` strictly increases
across 20 appends; and two explicit serialization-cap assertions, one per file, that fail if the cap
constant is removed. Codex finding 6's "assert an explicit serialized cap" is these last two.

### 4.5b — How a checkpoint is invoked, and where the run id comes from (High)

**Root cause.** The other half of codex finding 1: the plan never said how a model checkpoint *invokes*
the writer or obtains the run id — and codex finding 3 showed the two are the same problem, because a
model-written checkpoint has **no hook stdin** to read a session id from.

**Fix — the writer is a script the model calls, not a hook.**

```
scripts/journal-checkpoint.sh --kind <enum> --reason <enum> --note <text> [--open <text>]
```

It is invoked through the ordinary `Bash` tool at the four §4.6 points. This choice is load-bearing for
codex finding 5's baseline question: a script under `scripts/` is **not** an agent, a skill, a command,
an MCP server or a hook event, so it moves **no** counted asset. The baseline is stated in §2 and the
validators are the arbiter, not this sentence.

**Run identity — fail-closed, and sourced from the one place that has it.** `SessionStart` already
receives `session_id` on stdin, and it is **stable across compaction** (§4.9's note: one `sessionId`
across 16,908 records and seven compactions). So `sessionstart-restore.sh` writes it once per session to

```
<context_state_dir>/run-<repohash>.id     # 0600, atomic, single line, [A-Za-z0-9_-]{1,64}
```

and `journal-checkpoint.sh` reads that file. Three consequences, all deliberate:

1. **No run id file, or an empty/malformed one → the checkpoint writes NOTHING** and says so on stderr.
   Codex finding 3 required a non-empty exact match; this is that rule at the write end, where it is
   cheaper to enforce than at the read end.
2. **Restore requires an exact, non-empty match** between the payload's `run` and the current session
   id. Mismatch or empty → emit nothing. §4.9 is amended accordingly: the earlier "degrades to unkeyed"
   wording is **withdrawn**, because a payload with no run key is exactly the cross-run replay codex
   named.
3. **On a box with no `jq` and no `python3`, `hook_str` returns empty**, so no run id is written and the
   journal is inert. That is the correct failure: silent and safe, not silent and wrong.

   **But this ticket must not claim the dependency is free, because for `PreCompact` it is not.** An
   earlier draft argued the point was "largely theoretical, since `python3` is already a hard dependency
   of the capture pipeline". That is true of the *capture* pipeline and **false of the hook this ticket
   modifies.** Verified by execution at `dbb1fb8`: with `jq`, `python3` **and** `python` all shadowed to
   `exit 127`, `scripts/precompact-snapshot.sh` still exits 0, writes its snapshot
   (`.state/work-context-snapshot-<repohash>.json`) and leaves stderr empty — because it never reads
   stdin (§4.1) and derives every field from the filesystem.

   So §4.1's "add `hook_io_read` to the PreCompact producer" **introduces a JSON-engine dependency that
   hook does not have today**, converting a parser-free hook into one that degrades to inert without a
   parser. That is an acceptable trade — the journal is worthless without a run key — but it is a real
   regression in that hook's robustness envelope and it is stated as one rather than waved away.
   §4.5b's writer (`scripts/journal-checkpoint.sh`) is `python3` by design anyway (§4.5c), so the
   dependency is genuinely new only for `PreCompact`.

**Normalisation must be identical on both sides, and the shipped idiom gets this wrong.** §4.5a
constrains `run` to `[A-Za-z0-9_-]{1,64}`, so the raw session id is normalised before it is stored. An
exact-match rule is then only meaningful if the **same** normalisation is applied before comparing.
The existing round-binding code is the cautionary example: `scripts/lib/context.sh:312` stores
`sid` through `tr -cd 'A-Za-z0-9._-' | cut -c1-128`, while `:353-356` compares the **raw** environment
value against that stored form. A session id containing any character outside the charset — or longer
than 128 — is therefore written in one form and looked up in another, and never matches itself.
Demonstrated: a binding stored from `sess:with/odd chars` is unfindable by that same id. There it is
survivable because the check is soft and other keys carry the match; here it would silently disable
every restore while looking like a working exact match. **Normalise once, in one function, called by
both the writer and the reader** — and prove it with a case using an id that normalisation changes.

**Note for the reviewer — why not reuse `context_review_round_bind`'s treatment of session id.**
Codex finding 3 said that precedent is not equivalent, and it is right. There (`scripts/lib/context.sh`
~`:291-360`) session id is a **soft** discriminator layered on agent id, slug and a TTL, so an empty id
degrades to a still-tightly-keyed match. Here there is no such surrounding key material, so the same
degradation would be a genuine replay. The precedent is cited in round 1's §4.9 as justification for
failing open; that citation is withdrawn, not reinterpreted.

**Proof.** Cases: absent run-id file → no journal line, non-zero exit, one stderr line; empty file →
same; 65-char or non-charset content → same; payload `run` ≠ current session id → restore emits zero
bytes; payload `run` == current → restore emits the hint. Each fails if the guard is removed.

### 4.5c — Concurrency: the append is atomic, the rewrite needs a lock (High)

**Root cause.** Codex round-1 finding 2: tmp+rename prevents a *torn* file but not a concurrent
**read-modify-write**. Two checkpoint writers, or a writer racing self-compaction (§4.10), can both
read version N and each replace it with a different N+1. The plan had no single-writer protocol, no
lost-update risk row, and no concurrency tests.

**Fix: ONE mutex, held across the whole checkpoint. Every write path takes it — including the append.**

```
mkdir "<state>/journal-<repohash>.lock"      # atomic create-or-fail, POSIX, no flock dependency
```

`mkdir` is the primitive because **`flock(1)` does not exist on macOS** and the repo has no locking
primitive to reuse (verified: no `flock`, and no **process mutex** anywhere under `scripts/` — the ~8 `O_EXCL` uses
there are single-file tmp/symlink safety, e.g. `scripts/pty-capture.py:1022`, `scripts/review-verdict.py:520`, not mutual exclusion).
The holder writes its PID inside. **The numbers are literals, not adjectives** — an earlier draft said
"bounded backoff to a short deadline" and "a stale TTL", which cannot be implemented from, and cannot be
tested against:

| constant | value | why |
|---|---|---|
| retry schedule | 10 attempts at **50 ms** | ~0.5 s total; a checkpoint is human-paced, so this is invisible in the normal case |
| acquisition deadline | **500 ms** | after which the checkpoint fails non-zero rather than writing unlocked |
| stale-lock TTL | **120 s** on the lock directory's mtime | far above any real checkpoint (which is milliseconds) and far below a session, so a `SIGKILL`ed holder self-heals within one interaction |
| break behaviour | broken **once** per process, logged | a second break in the same process means the protocol is wrong, not that the lock is stale again |

> **An earlier draft of this section exempted the append from the lock, and that was wrong twice
> over.** It is recorded here rather than quietly deleted, because both errors are instructive and a
> reviewer who has seen the earlier draft deserves the reasoning.
>
> **(1) It was internally contradictory.** Every record carries `seq`, and `id` is `<run>-<seq>`
> (§4.5a). Allocating `seq` means reading the current last value — a read-modify-write. So an
> "unlocked" append still had to take the lock to number itself. The exemption described a code path
> that cannot exist.
>
> **(2) It made this section's own proof unsatisfiable.** The draft promised "an appender racing
> self-compaction loses no record" while specifying that only compaction takes the mutex. Compaction
> *rewrites the file*; an appender holding the old descriptor, or writing between compaction's read and
> its rename, writes into a file that is about to be replaced. Reproduced under measurement:
> **489 records lost** with a held descriptor and **160 lost** with the realistic open-per-record
> pattern. The proof obligation was correct and the design contradicted it.
>
> **`O_APPEND` atomicity is real but was the wrong load-bearing claim.** A single `write()` to an
> `O_APPEND` regular-file descriptor *is* atomic — measured clean from 64 B to 128 KiB with 16
> concurrent writers, zero torn records — so it remains a genuine second line of defence against
> interleaving. It simply never addressed lost updates, which is what codex finding 2 was about.
> Interleaving and losing are different failures and only one of them was being answered.
>
> **Do not reintroduce `PIPE_BUF` reasoning either.** It bounds atomic writes to **pipes and FIFOs**,
> not regular files, and on this box it is **512**, not the 4096 the folklore assumes
> (`getconf PIPE_BUF /` and `os.pathconf('/','PC_PIPE_BUF')` both return 512; `syslimits.h:104` agrees).
> Both the constant and its applicability were wrong.

**So the protocol is one lock, and it is simple on purpose:** acquire → read `seq` → build the record in
memory → single `write()` to `O_APPEND` → rewrite `live-state` → compact if needed → release.

**Lock-acquisition failure is a VISIBLE FAILURE, not a silent skip.** The earlier draft let the append
proceed unlocked when the lock was unavailable, which is precisely how a lost update happens under
contention. A checkpoint that cannot take the lock exits non-zero and says so. Losing a decision record
silently is the worst outcome available here; a noisy failure the model can retry is strictly better.

**The writer is `python3`, not `bash`, and that is a correctness requirement.** Measured on macOS:
`printf '%s\n' "$line" >> file` is atomic only up to **1024 bytes** — at 1025 bytes it tears (**994 of 1600
records torn**, against a clean control at 1024), identically in `sh`, `bash` and `zsh`, because the shell's stdio buffer is `BUFSIZ`.
The §4.5a line cap is **also** 1024 bytes, so the two coincide *numerically* while being unrelated in
kind — exactly the coincidence that invites someone to raise the cap and silently lose atomicity. The
record is therefore written with a single `os.write()` from `python3`, which has no such bound, and
§4.5a's cap stays what it is: a **token-budget** bound with no atomicity meaning whatsoever.

**Risk accepted and stated:** a `mkdir` mutex is not robust against a `SIGKILL`ed holder within the
stale TTL — during that window checkpoints fail loudly rather than corrupting. Liveness probing is
rejected as over-engineering for a single-user CLI, and surfaced as §8 Q4 rather than decided silently.

**Proof.** Concurrency cases, each failing if the protocol is removed: 20 concurrent checkpoints produce
20 well-formed lines with 20 **distinct** `seq` values and no interleaved bytes; an appender racing
self-compaction loses **no** record (the case the earlier draft could not have passed — 489 lost);
two concurrent `live-state` writers leave a payload matching exactly one of them, never a merge; a
held lock makes a checkpoint **fail non-zero** rather than write unlocked; a lock backdated past the
stale TTL is broken exactly once; and a 1025-byte record is **rejected by the cap** rather than written.

> **Method warning, carried from the measurement that produced these numbers.** The first harness used
> to test append atomicity silently wrote **zero bytes** at sizes ≥ 4096 and duly reported `TORN=0` — a
> false pass that reads exactly like proof of atomicity. Every concurrency case above must assert
> **completeness** (expected line count *and* byte count) before it asserts integrity, or it can pass by
> doing nothing. This is the same class as the mutation script that no-ops silently (§6).

### 4.6 — Checkpoints are where reasoning is irrecoverable (Medium)

**Fix.** Write a checkpoint at exactly the points where a decision is made whose *justification* exists
nowhere on disk. Four, and the `kind` value is the wire enum from §4.5a — not prose:

| `kind` | Checkpoint | Why irrecoverable |
|---|---|---|
| `fork` | `brainstorm` Step 4b fork (`skills/brainstorm/SKILL.md:49`) | The chosen option is persisted **nowhere** today. `:94-96` tells the model to carry the choice *and* the rejected alternatives forward **as prose** from Step 4b to the Step 8 summary and Step 9 plan — roughly 100 lines and five steps of context later. Nothing on disk survives a compaction in between. |
| `gate` | Plan Review Gate verdict | The verdict is recoverable (`.verdicts/`), but the **disagreements and the minority report** are not. |
| `adjudication` | Per-round blocker adjudication | Which findings were confirmed vs `NEEDS DISCUSSION`, **and why** — the reviewer JSON records the finding, never the adjudication. |
| `abandoned` | Abandoned implementation approaches | Nothing on disk records a path not taken. This is the single highest-value class. |

**The `fork` checkpoint records into the journal's own store, and depends on nothing else.**
Round 1 declared this row a cross-ticket dependency on `COREDEV-2584`'s brainstorm sidecar and made it
the sole justification for a hard `2583 → 2584 → 2585` chain. Codex round-1 finding 5 caught the
contradiction: the very same note also said "either order works". Both cannot be true, and the
"either order works" half was the accurate one.

So the dependency is removed at the source. A `fork` checkpoint is a `journal.jsonl` line like any
other — same writer (§4.5b), same store, same schema — carrying the chosen option's identity and the
rejected alternatives' bounded `reason` codes plus their capped `note`. It reads nothing that
`COREDEV-2584` produces and writes nothing that `COREDEV-2584` consumes. **If `COREDEV-2584` never
lands, the `fork` checkpoint is complete on its own.** That is the whole of the decoupling.

**What is left is a one-way correlation, and it is optional.** If `COREDEV-2584` *has* landed, its
sidecar records the *selected option* as structured data while this journal records the *reasoning*.
They describe one fork from two sides, correlated after the fact by `(slug, round)` — which both
already carry — and **not** by either reading the other's file. The ownership split round 1 asserted
still stands and is now the only thing it asserts: **2584 owns the sidecar; 2585 owns the rationale.**
Neither plan may claim the other's artifact, and neither may fail because the other is absent.

> **Citation correction, because this plan nearly repeated the error it warns about (§9).** The fork
> sidecar **does not exist yet** — `COREDEV-2584` proposes it, modelled on the existing gate-digest
> sidecar. `AUTONOMOUS_END_TO_END_PLAN.md:306` cites `scripts/review-verdict.py:272-280` for that
> pattern; at `dbb1fb8` those lines are `_read_regular_file`, and the sidecar writer is
> `_reviewed_sha_sidecar` at **`scripts/review-verdict.py:565`**. An earlier draft of this section
> copied the stale number forward. Verify a citation before inheriting it, including from a sibling
> plan — that is the whole point of §9's third bullet.

**Cross-document action, deliberately NOT taken here.** `AUTONOMOUS_END_TO_END_PLAN.md:18-20` still
states the reverse — "so 2584 → 2585 is the required chain, not a free choice". That sentence is now
wrong, and two plans disagreeing about their own coupling is precisely the class codex finding 5
raised. It is **not** edited by this round: that document carries its own gate state, and rewriting a
sibling plan's ordering claim outside its own revision round is the drive-by edit this project has
already been burned by. It is filed in §11 as a required follow-up, to be made in 2584's next round.

**Proof.** Codex round-1 finding 6 correctly noted that §4.6 was excluded from the blanket
mutation-proof requirement. It no longer is. **One case per `kind`** (four), each asserting that
invoking the checkpoint writer with that `kind` appends exactly one `journal.jsonl` line whose `kind`
field matches and whose `id` is unique; plus one case asserting an **unknown `kind` is rejected** and
writes nothing — the enum must be closed, or "bounded" is decorative. Each fails if that `kind`'s
wiring is removed. Additionally, one case runs the `fork` checkpoint with **no `COREDEV-2584` sidecar
present anywhere on disk** and asserts it still writes a complete record — this is the decoupling
itself, and it is the case that fails if a future edit reintroduces the dependency.

### 4.7 — Free-text rationale is the main new risk, and the shipped redactor is the wrong tool (High)

**Root cause — and a correction the plan owes the reviewers.** The premise "today the pipeline only
persists derived tokens" is **false**, and an external reviewer would catch it.
`mcp/review-synthesizer/capture.py:232-234` already persists three **model-authored free-text** fields —
`finding`, `evidence`, `fix` — each `cap(redact_pii(...))` at 500 chars; `:372-377` persists free-text
status-trailer fields the same way. The accurate sentence is: *the **shell hook** logs persist only
derived tokens plus one capped classifier `reason`* (`scripts/permission-denied-log.sh:35`, the sole
free-text shell caller). A rationale journal is an **extension of an existing precedent**, and should be
argued that way rather than as a new category.

What is genuinely new is *volume* and *shape*. And here the shipped redactor fails in three distinct
ways, all verified by running it:

**(a) It does not redact PII.** `hook_redact_pii` (`scripts/lib/hook-io.sh:236-250`) is 8 `sed -E`
substitutions and a `tr` fold — a **secret-shape scrubber, not a PII scrubber**. Verified: the input
`Customer Robert Nakamura at Nakamura Holdings reported the crash; his account id is 5512-9987.` returns
**byte-identical**. Also untouched: phone numbers, SSNs, postal addresses, DOBs, credit-card numbers,
tenant GUIDs, `ghp_…` GitHub PATs, `AKIA…` AWS keys, `password=…`. Emails, `/Users|/home|~user`,
`Bearer <20+>`, `eyJ…`, `sk-|pk_ <8+>` and `api key: <v>` are the entire coverage.

**(b) It corrupts ordinary English.** The `sk-` rule has no leading word boundary. Verified:
`task-oriented` → `ta[redacted-secret]`, `risk-assessment` → `ri[redacted-secret]`, `disk-utilization` →
`di[redacted-secret]`. The `~` rule has no path context: `~500ms` → `~[redacted]`, `~40 percent` →
`~[redacted] percent`. **It deletes exactly the quantitative justification a decision journal exists to
preserve.** Both bugs exist in the shell and Python implementations.

**(c) It silently truncates on invalid UTF-8.** `LC_ALL=C` is applied to `sed` but not to `tr`, and the
`2>/dev/null` binds only to `sed`. Verified under `LANG=C.UTF-8`: input `name \xff\xfe
jane.doe@corp.com end` produced stdout `name ` — everything from the bad byte dropped — plus
`tr: Illegal byte sequence` escaping to stderr, contradicting the repo's own stderr-clean invariant.
`scripts/stop-failure-log.sh:33` gets this right for its own `tr`; the helper does not.

One end-to-end run through the real `PermissionDenied` hook captures all of it at once:

```
"reason":"denied because customer Jane Doe at Acme wrote [redacted-email] and we chose a ta[redacted-secret] fix"
```

The customer **name** and employer persisted verbatim; the email died; `task-oriented` was mangled.

**Fix.** Four parts, in priority order:

1. ~~**Fix the two regex defects** and the `tr` locale/stderr bug in both implementations.~~
   **SUPERSEDED — DONE in `COREDEV-2597`.** Split out on both reviewers' independent recommendation
   and implemented there, which also closed five leak classes this plan never identified (Unicode
   whitespace in the api-key/bearer slots, the line-oriented `sed` case, the compound
   `/Users/…`-eats-the-anchor form, a routable address preserved by the email lookahead, and a real
   username leaked by the tilde lookahead). Treat the redactor as FIXED and GATED — the equivalence is
   enforced by `mcp/review-synthesizer/redactor_model.py` on both `sed` engines. **Do not re-do this
   work; verify the dependency landed instead.**
2. **Do not rely on redaction as the PII control.** It cannot detect names. The real control is §3:
   persist pointers, not prose, and bound what prose is written to the narrow irrecoverable set (§4.6).
3. **Instruct at write time.** The checkpoint prompt states explicitly that rationale must not name
   people, customers, or organizations, and must not paste credentials — the model is the only component
   in the system that can actually apply that rule.
4. ~~**Name which redactor.**~~ **SUPERSEDED by `COREDEV-2597`.** The two are now equivalent by
   construction: exactly ONE documented divergence remains (Python's `@Nx` retina-filename exemption,
   which POSIX ERE cannot express), and that equivalence is gated in CI on both `sed` engines. The
   `~Copyable` exemption and the whitespace-folding divergence this bullet warned about are both gone —
   the tilde rule now requires a path separator, and whitespace is canonicalised identically on both
   sides before any rule runs. "Reuse the existing redactor" is no longer ambiguous.

**Note for the reviewer — what will NOT catch a leak.** All three verified:

- The pre-commit pattern scan is **advisory by design** — `scripts/pre-commit-checks.sh:126-156` sets
  `FOUND_PII` but never `EXIT_CODE`. Ran against a staged file with an email and a JWT: two warnings,
  then `🎉 All pre-commit checks passed!`, **exit 0**.
- `gitleaks` is **not installed** on this machine, and even when present only exit code exactly `1`
  enforces — any other non-zero fails open (`:171-179`).
- CI's `gitleaks` scans **committed git objects** (`.github/workflows/plugin-ci.yml:219-221`). A
  git-ignored `*.jsonl` journal is never committed and therefore **never scanned by anything, ever**.
  And gitleaks detects credentials, not customer names.

**Proof.** Redactor tests on both sides for: a personal name (documents that it survives — an honest
negative assertion, not a pretence), `task-oriented` surviving intact after the boundary fix, `~500ms`
surviving, and an invalid UTF-8 byte no longer truncating. Each must fail if the regex fix is reverted.

### 4.8 — Where the journal lives, and its file mode (Medium)

**Root cause.** Two details a journal gets wrong by inheriting the nearest primitive.

*(a) Permissions.* `log_append` (`scripts/lib/log.sh:77`) does a plain `>>` with no mode control;
verified, the resulting `denied-commands.jsonl` is `-rw-r--r--`. Rationale is more sensitive than a
denial enum. `capture.py:457` (`_open_private_tmp`, `O_CREAT|O_EXCL|O_NOFOLLOW`, `0o600`) is the
in-repo hardened precedent.

*(b) `.gitignore` reach.* Verified with `git check-ignore -v`: `.state/`, `logs/`, `*.jsonl`, `reviews/`
are covered (`.gitignore:26-29`), so **a `.jsonl` journal is git-ignored anywhere in the tree**. But
`docs/decisions/journal.md` and `docs/planning/DECISIONS.md` are **not** ignored — a markdown or `.json`
journal in-repo is committable.

**Fix.** `.jsonl` for the record and `.json` under `.state/` for the payload, both outside the repo under
`context_base()`, both written `0600` via the `capture.py` idiom. If a human-readable in-repo view is
ever wanted, it is a *generated* artifact and needs its own `.gitignore` entry — not the primary store.

**Note for the reviewer.** `log_append` is tempting and wrong for a second reason: it has **no repo and
no session namespacing** (`scripts/lib/log.sh:59-73` — the path is `$(log_dir)/$name`, caller-supplied
basename only), and its "rotation" is destructive truncation keeping the newest `max/2` lines
(`:42-51`, default 500). It is not an append-only audit trail and must not be described as one.

### 4.9 — Replace the flat 600 s TTL with run-scoped freshness (Medium)

**Root cause.** Freshness today is `now - file_mtime < 600` (`scripts/sessionstart-restore.sh:51`);
the snapshot's own `snapshot_time` field is **never read** by any consumer — verified, a repo-wide grep
finds only the producer, a test fixture, and a stale plan doc. It is write-only metadata.

A wall-clock window is wrong for this ticket's purpose. A long autonomous run legitimately idles longer
than 600 s (a `codex exec` review round alone runs to ~12 min under `model_reasoning_effort=xhigh`), and
a 610-second gap is not evidence the state is irrelevant.

**Fix.** Scope freshness to the **run**, not the clock. The payload carries the `run` identifier of
§4.5b, and it is valid **only** while that run is the current one, matched exactly and non-empty.
Wall-clock survives solely as a generous backstop that collects abandoned state (§4.10), never as the
primary test and never as a substitute for the run match.

**The round-1 fail-open is WITHDRAWN.** Round 1 wrote that run-scoping "degrades to unkeyed on a box
with no JSON parser, and the plan must state that fail-open behaviour". Codex finding 3 rejected this
and the rejection is accepted in full: an unkeyed payload is restorable into **any** session, so the
moment parser availability changes — a `jq` install, a PATH change — previously-inert state becomes
cross-run replay. Worse, it degrades **silently**, in the direction of injecting one run's reasoning
into another's context. The rule is now: **no run id, no restore.** §4.5b specifies the same rule at
the write end, so an unkeyed payload is never created in the first place; this is the second gate on
the read side, and both are required — the write guard alone would not protect a payload written by an
older build.

**Note for the reviewer — the precedent this plan cited for failing open does not support it.**
Round 1 cited `scripts/lib/context.sh:353-356`, where session id is a soft discriminator. Codex finding
3 pointed out the precedent is not equivalent because that code also keys on agent id, slug and a TTL.
That is correct, and the citation is **withdrawn rather than reinterpreted** (see §4.5b).

**Note for the reviewer — session id is stable across compaction**, which is what makes it usable at
all: proven on a live transcript with seven compactions and one `sessionId` across 16,908 records. It
reaches shell state only via `hook_str session_id` (`scripts/lib/hook-io.sh:194-213` — round 1 cited
`:189-198`, which stops before the `python3` fallback its own sentence describes), which is
jq → python3 **structural only, with no grep fallback** — verified by shadowing both binaries: it
returns empty. Under §4.5b that emptiness now disables the journal instead of unkeying it.

**Note for the reviewer — `precompact-snapshot.sh` does not read stdin at all today** (§4.1), so adding
`hook_io_read` to it is part of this fix; it does not already have a session id. The run id itself is
written by `SessionStart` (§4.5b), which is the only hook guaranteed to fire before any checkpoint.

**`snapshot_time` is dropped.** It is write-only dead metadata (§9) and the run key plus `t` supersede
it. Dropping a field that no consumer reads is not a compatibility break.

**Proof.** Cases: payload `run` matches current → hint emitted; differs by one character → zero bytes;
payload has no `run` key at all (an older-build payload) → zero bytes; payload `run` empty string →
zero bytes. The third and fourth fail under the round-1 design, which is the point of listing them.

### 4.10 — The journal needs its own GC (Medium)

**Root cause.** There is exactly **one** housekeeping routine in the entire state layer —
`_context_round_sweep` (`scripts/lib/context.sh:233`), which removes only `review-round-*.json` older
than the TTL, and is called only from `context_review_round_bind`. Markers, snapshots, sentinels,
`reviews/` and `logs/` are **never** swept. Confirmed live: 19 accumulated marker files across checkouts
and 5 leftover sentinels after a 5-session gate run.

A stale snapshot is specifically never deleted — `scripts/sessionstart-restore.sh:33-34` leaves it "for
the next PreCompact to overwrite". Verified: after a 700 s backdate the file survived.

**Fix.** Self-compaction rather than truncation, plus a sweep that actually covers everything this
ticket creates. On checkpoint write, if the journal exceeds a bound, fold the oldest entries into a
summary line and rewrite — the record stays complete in *meaning* while bounded in size. This is the one
place the design tolerates rewriting the append-only file; it is atomic (§4.11) and it **takes the
§4.5c mutex**, because a rewrite concurrent with an append is the lost-update codex finding 2 named.

**The GC's scope is three things, not one.** Round 1 drafted a compactor for the journal alone, which is
why codex finding 4 could observe that a corrupt `live-state` would never be collected. The sweep covers:

| target | bound | why both bounds |
|---|---|---|
| `journal-<repohash>.jsonl` | fold oldest when > 256 records | size, with meaning preserved |
| `quarantine/` (§4.3) | newest **10** AND ≤ **14 days** | a count alone leaks under a slow drip; a TTL alone leaks under a fast one |
| `run-<repohash>.id` (§4.5b) | removed when its run is neither current nor < 14 days old | otherwise every session leaves one behind forever |

**Note for the reviewer.** This ticket must not pretend to fix the *general* housekeeping gap it
documents. Markers, snapshots, sentinels, `reviews/` and `logs/` remain unswept — 19 accumulated marker
files and 5 leftover sentinels were confirmed live. This GC sweeps **only what this ticket creates**.
Widening it to the pre-existing state layer is a separate ticket, and claiming otherwise would be the
overstated-scope defect this project keeps catching in its own commit messages.

**Note for the reviewer.** Do **not** reuse `log_append`'s rotation: it keeps the newest `max/2` lines
and discards the rest with no summary (`scripts/lib/log.sh:82-91`). For a build log that is fine; for a
decision record it silently deletes the earliest — and usually most consequential — decisions of a run.

**Proof.** Cases: 257 records → folded to a summary plus the newest tail, with the **earliest** decision
still recoverable from the summary line (this is the case `log_append`'s rotation fails); 11 quarantine
files → 10 retained; a 15-day-old quarantine file → removed even when the count is under 10, and a
15-day-old file when the count is over 10 → removed once, not twice; a stale `run-*.id` → removed while
the **current** run's id survives the same sweep; and compaction racing an append → no record lost.

**Note for the reviewer.** Do **not** reuse `log_append`'s rotation for this: it keeps the newest
`max/2` lines and discards the rest with no summary (`scripts/lib/log.sh:82-91`). For a build log that is
fine; for a decision record it silently deletes the earliest — and usually most consequential —
decisions of a run.

### 4.11 — Atomic writes: name the idiom, keep the redirect order (Medium)

**Root cause.** **Four** atomic-write idioms ship, and "reuse the established pattern" is ambiguous:

| Idiom | Where | Notes |
|---|---|---|
| `.tmp.$$` + bare `mv`, no chmod | `scripts/lib/marker.sh:149-156` | predictable temp name; default umask |
| `$path.tmp.$$` + `mv -f`, explicit `rm` both branches, no trap | `scripts/lib/context.sh:318-321` | |
| self-disarming EXIT trap | `scripts/precompact-snapshot.sh:65-76` | the compaction-safe one |
| `mktemp` + `chmod 600` + `mv -f` + symlink pre-removal | `scripts/stop-quality-marker-gate.sh:126-132` | the hardened one |

**Fix.** Use the **EXIT-trap** idiom for the journal writes — a compaction landing mid-write must never
truncate the file, and the trap is what guarantees the partial temp is removed on any early exit — with
the `mktemp`+`chmod 600` hardening from the fourth idiom for the file mode (§4.8).

**Preserve the redirect order verbatim.** `scripts/precompact-snapshot.sh:70-74` places `2>/dev/null`
**before** `> "$TMP"`, and the comment explains why: bash applies redirects left-to-right, so a trailing
`2>/dev/null` would let the open error — **which echoes the full PII-bearing tmp path** — reach stderr.
Verified: with `.state` at `chmod 500` the hook exits 0 with completely empty stderr. "Tidying" this line
reintroduces a path leak.

**Note for the reviewer.** This code survived at least eight rounds of external PR review
(`scripts/precompact-snapshot.sh:2`, COREDEV-2325 Item 5). Nearly every odd-looking construct — the
redirect order, the feature-detected `stat` (`scripts/sessionstart-restore.sh:43-47`, which deliberately
rejects a `uname == Darwin` branch because not all BSDs report Darwin), the bash substring instead of
`cut` — is a fix for a reviewer-found bug. A plan that "simplifies" any of them will be challenged, and
should be.

### 4.12 — Documentation that goes stale (Low)

**The conditional is resolved: this ticket adds no hook event** (§2), so the two documented counts stay
true and neither needs editing. That is worth stating rather than leaving implicit, because nothing in
CI would have caught it either way — `grep -n 'hook' scripts/validate-version-sync.sh` returns **zero**
matches, so the counts are load-bearing prose with no enforcement behind them.

**Two citation corrections this round owes the reviewers.** Round 1 cited `README.md:340` for the
hook-event count and `README.md:342-355` for the hook table. The real line is **`README.md:452`**;
`CLAUDE.md:18` is still correct. Reviewers open citations, and a plan that misdirects them burns the
credibility it needs for the claims that matter.

**A genuine doc defect found while checking those lines, and deliberately NOT fixed here.**
`README.md:452` ends: *"State (markers, logs, snapshots) lives under the plugin data dir
(`~/.claude/unleashed-mail/`), never in your repo."* That path is **no longer what the code does.**
`COREDEV-2617`'s D′ removed the `${HOME}/.claude/unleashed-mail` fallback entirely: the base is
`CLAUDE_PLUGIN_DATA`, and when it is unset the base does not resolve and nothing is read or written
(`scripts/lib/paths.sh`). The README documents a path the shipped resolver will never produce. It is
out of scope here — it belongs to the `COREDEV-2617` surface, is being handled in that plan's own
revision round, and fixing it from this ticket would be the cross-plan drive-by edit §4.6 declines to
make. Recorded so the next reader does not re-discover it.

**A third doc site round 1 did not name.** Beyond the two counts, the README carries a **hook table** at
`README.md:454-466` — 11 rows for 10 events, because `PostToolUse` has two. Any event change would make
that stale too, and it was unmentioned. It is the only doc site this ticket actually touches.

**What this ticket edits in the docs:** the `README.md` hook-table rows for `precompact-snapshot.sh`
(`:463`) and `sessionstart-restore.sh` (`:464`), whose *Behavior* column changes (§4.3, §4.4, §4.9), and
nothing else. No new row, no new kill switch, no count edits. Both hooks already have kill switches —
`UNLEASHED_COMPACT_SNAPSHOT` (`scripts/precompact-snapshot.sh:19`) and `UNLEASHED_COMPACT_RESTORE`
(`scripts/sessionstart-restore.sh:20`) — so the table's existing entries stay correct.

> **Correction to a claim round 1 made in passing.** It described the kill switch as universal: "every
> shipped hook has one; it is convention, not enforcement". The convention half is right; the
> **universality is false**. `scripts/swift-build-verify.sh` gates only its `log_append` behind
> `UNLEASHED_FAILURE_LOG` (`:65-67`); the `additionalContext` advisory at `:70-72` fires regardless, so
> that hook's user-visible output has **no** kill switch. Nothing in this ticket depends on the claim,
> which is exactly why it would have shipped unchallenged — an unchecked aside is still an assertion,
> and this plan is asking two reviewers to trust its assertions.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Model-written rationale names a person, customer, or employer | **High** | The redactor provably cannot catch it (§4.7a — **there is no §4.7a; the reference is stale round-1 residue and the subsection meant is §4.7(a)**). Controls are §3 (pointers not prose), a bounded checkpoint set (§4.6), and a write-time instruction. Stated as a residual risk, not a solved one. |
| Redaction corrupts the rationale it is meant to protect | **Low — RESOLVED upstream** | Was High. `COREDEV-2597` repaired the `sk-`/`~`/`tr` defects in both implementations, closed five further leak classes, and gated the shell/Python equivalence in CI on both engines. Verify the dependency landed; do not re-do it. |
| A credential is pasted into rationale and survives | Medium | Only 4 credential shapes are covered; `ghp_`, `AKIA…`, `password=` are not. Nothing downstream scans a git-ignored file. Write-time instruction is the only control — say so. |
| Journal grows unbounded over a long autonomous run | Medium | §4.10 self-compaction. Explicitly not `log_append`'s truncation. |
| Restore injects noise instead of context after a corrupt write | Medium | §4.3 — emit nothing rather than an all-`unknown` hint, and **QUARANTINE** the payload (bounded by count AND TTL) while clearing the active path. **Round 1's "retain the file as evidence" is reversed**, on codex finding 4: retention at the active path re-logs on every restore and the next checkpoint destroys the evidence anyway. |
| No JSON parser, so no run id, so the journal is inert | Low | **Fail-CLOSED.** Round 1's "degrades to unkeyed" fail-open is **withdrawn** (§4.9), and the `context.sh:353-356` precedent cited to justify it is **withdrawn with it** — codex finding 3 is right that a soft discriminator layered on agent/slug/round/TTL is not a precedent for a bare unkeyed key. No run id → no write and no restore. |
| A worktree and its parent checkout keep separate journals | Medium | Correct for isolation, surprising for continuity. Stated in §4.5 rather than discovered later. |
| Token budget overruns the ~1.5–2 k target | **Low — CLOSED** | Was Medium. Codex finding 6: a fixed *shape* does not bound tokens. §4.5a now sets an explicit **2048-byte serialized cap**, asserted by a test that fails if the constant is removed. O(1) in run length remains true by construction. |
| **Lost update: concurrent writers each replace version N** | **Medium** | Codex finding 2. §4.5c holds **one** `mkdir` mutex across the whole checkpoint — `seq` allocation, append, `live-state` rewrite and self-compaction alike. An earlier draft exempted the append and was measurably wrong (489 records lost racing compaction); that draft and its refutation are kept in §4.5c so the exemption is not reinvented. Proved by concurrent-append, append-vs-compaction and two-writer cases. |
| A `SIGKILL`ed mutex holder blocks writes until the stale TTL | Low | Accepted and stated (§4.5c). Because the lock now covers the append too, the consequence is a checkpoint that **fails loudly** during the stale window rather than one that writes unlocked — the failure the model can see and retry, chosen deliberately over the silent lost update. Liveness probing rejected as over-engineering for a single-user CLI — surfaced as §8 Q4 rather than decided silently. |
| Adding `hook_io_read` gives `PreCompact` a JSON-engine dependency it does not have today | Low | Verified, not assumed: with `jq`/`python3`/`python` all shadowed, `precompact-snapshot.sh` still exits 0 and writes its snapshot. §4.5b states the regression rather than reusing the "python3 is already required" argument, which is true of the capture pipeline and false of this hook. |
| Normalisation drift between the run-id writer and reader | Medium | The shipped round-binding code already has this bug (`context.sh:312` sanitizes, `:353-356` compares raw). §4.5b requires one shared normalise function called by both sides, proved with an id that normalisation changes. |
| `SessionStart` never fires, so no run id exists and the journal is inert | **Medium** | §4.5b fails closed by design. **This is not hypothetical** — a stale plugin registry was observed writing no plugin state for an entire session. Fail-closed is right, but the silence is the risk, not the inertness; §8 Q5 asks whether it needs a visible signal. |
| Quarantine becomes an unbounded leak | Low | §4.10 bounds it by count **and** TTL. Either bound alone leaks — a count under a slow drip, a TTL under a fast one — which is why both are specified and both are proved. |
| The `note` caps and the payload cap are jointly unsatisfiable at their maxima | Low | Deliberate: 10 × 200 chars exceeds 2048, so eviction (oldest first, recorded to the journal) makes the payload lossy rather than making a write fail. Stated in §8 Q6 rather than left for an implementer to discover. |
| "Simplifying" a review-hardened construct | Medium | §4.11 note. Cite the eight review rounds when a reviewer asks why the code looks odd. |

## 6. Verification

Every gate below must pass before the change is proposed for merge:

```bash
python3 scripts/validate-plugin-assembly.py --root . --strict
python3 scripts/validate-hooks.py --root . --strict --require-manifest
VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh
bash scripts/test-hooks.sh
python3 -m unittest discover -s mcp/review-synthesizer/tests
python3 -m unittest discover -s scripts/tests
shellcheck -s bash -S warning scripts/*.sh scripts/lib/*.sh scripts/review/*.sh .githooks/pre-commit
```

Plus, on the pinned CLI (`npm install -g @anthropic-ai/claude-code@2.1.220`):

```bash
claude plugin validate --strict .
claude plugin validate .claude-plugin/plugin.json
```

Asset counts must be **unchanged** by this ticket, at the §2 baseline `21/21/0/1` and **10 hook events**.

**The `scripts/test-hooks.sh` baseline is 304 passed, 0 failed** — measured on this branch's merge-base
`dbb1fb8`, 2026-08-08, not carried forward. Round 1 said 302; that number was true at `a230b49` and
drifted when 2.7.0 and 2.7.1 landed. Any behavioural change to the restore path must **update** the
contradicting assertions around cases 28–32 (`scripts/test-hooks.sh:630-671`, verified: case 28 at
`:630`, the stale-snapshot assertions at `:659-660`) rather than leave them inconsistent — in
particular `"stale -> file left for next precompact"` at `:660`, which asserts today's retain-forever
behaviour and directly contradicts §4.3's quarantine and §4.10's sweep. An implementer who adds new
cases without reconciling that one leaves the suite self-contradicting and green.

**Mutation proof is required for every new assertion** — §4.1, §4.2, §4.3, §4.4, §4.5, **§4.5a, §4.5b,
§4.5c**, §4.6, §4.8, §4.9, §4.10, §4.11. §4.7 is superseded by `COREDEV-2597` **except** for the
invalid-UTF-8 gap recorded in §7 step 0, which is a prerequisite rather than part of this ticket.
Revert the fix, and the new test must fail.

**Every mutation script must assert it changed something** — `assert s.count(old) == 1` before
replacing. A silent `str.replace` no-op is indistinguishable from a surviving mutant, and that
confusion has already cost this project a round.

**Explicitly required by codex round-1 finding 6, so listed rather than implied:** concurrency cases
(§4.5c), an explicit serialized-cap assertion per file (§4.5a), per-`kind` checkpoint wiring cases
(§4.6), and positive controls on the redactor — established by **mutation, not by reading test names**
(§7 step 0): (b) and (c-order) are genuinely proved, (a) is proved by an absolute assertion rather than
by the prose class round 1 cited, and (c-tr) is **unguarded**.

**Assert absolute expected output, never agreement.** The redactor's parity suite is a **differential**
gate: it compares the shell and Python implementations to each other, so a revert applied to **both**
keeps them equal and passes. Every proof this ticket adds — redactor-adjacent or not — must assert the
value it expects, not that two components agree. A test that can only see disagreement cannot see a
shared mistake, and the shared mistake is the one a single canonical implementation makes.

**Assert completeness before integrity in any concurrency case.** Carried from the measurement in
§4.5c: the first harness built there capped its payload and silently wrote **zero bytes** at larger
sizes, then reported `TORN=0` — a false pass indistinguishable from proof. Assert the expected line
count **and** byte count first; only then believe a tearing or ordering number.

## 7. Implementation order

0. **The `COREDEV-2597` dependency check — RUN, 2026-08-08, and it is not clean.**
   2597 **landed as v2.6.2** (commit `929c160`). All three of its fixes are present in shipped code:
   the `sk-`/`pk_` word boundary (`scripts/lib/hook-io.sh:247-248`), the tilde rule requiring a
   following `/` (`:244`), and the `LC_ALL=C tr … 2>/dev/null` at `:238` with the Unicode-whitespace
   fold running **first** among the `sed` rules at `:240` (all line numbers re-checked at `dbb1fb8`).
   Behaviour was **executed, not read**: input `name \xff\xfe jane.doe@corp.com end` returns
   `name <2 replacement chars> [redacted-email] end` on **both** implementations, byte-identical, with
   **empty stderr**. The `redactor-equivalence` CI job is green.

   **But the proof coverage is uneven, and establishing that required mutation rather than reading.**
   Each fix was reverted in a `/tmp` copy and the suite re-run:

   | fix | reverted → suite | verdict |
   |---|---|---|
   | (b) tilde requires `/` | `FAILED (failures=9)` — `~500ms`, `~2x faster`, `~40 percent`, `~L147` (`tests/test_redactor_parity.py:126`) | **genuinely proved** |
   | (c-order) fold-before-rules | `FAILED (failures=25)` — all 23 codepoints of `test_canonicalisation_closes_unicode_ws` (`:145`) | **genuinely proved** |
   | (a) `sk-`/`pk_` boundary | `FAILED` ×2 — `test_asymmetric_boundary_policy` (`:94`, `orders_pk_customer_id_idx`) and `test_sequential_secret_passes` (`:102`) | **proved, but not by the class the plan cited** |
   | (c-tr) `LC_ALL=C` on `tr` | suite stays **GREEN** | **UNGUARDED** |

   **Two things round 1 got wrong here, and the second is structural.**

   *First:* there is **no vector with an invalid UTF-8 byte** anywhere — exhaustive search across the
   fixture, `test_redactor_parity.py` and `redactor_model.py` returns zero hits. The fix is load-bearing
   at runtime (with `\xff` input under `LC_ALL=en_US.UTF-8`, dropping `LC_ALL=C` **silently truncates**;
   the `2>/dev/null` only suppresses `tr: Illegal byte sequence`) — yet reverting it leaves the suite
   green.

   *Second, and this generalises past one fix:* **the parity suite is a DIFFERENTIAL gate and is blind
   to any symmetric revert.** `task-oriented` exists only as a parity *vector*
   (`redactor_fixture.py:59`, `redactor_model.py:77`) — there is no `assertEqual("task-oriented", …)`
   anywhere. Under a both-sides revert it becomes `ta[redacted-secret]` on **both** engines, the two
   still agree, and every parity assertion passes. (a) survives only because
   `test_asymmetric_boundary_policy` asserts an **absolute expected output**. So §4.7's proof obligation
   — "`task-oriented` surviving intact … must fail if the regex fix is reverted" — is **not satisfiable
   by a parity vector at all**, and any new redactor proof this ticket relies on must assert an absolute
   expected output, not agreement between two implementations that can be wrong together.

   This is exactly the sub-case codex round-1 finding 6 asked for ("the invalid-byte case as a
   shell-ingress test and a separate Python-ingress test proving replacement without truncation"), and
   it is **not** closed by 2597. It is a **test-only gap in a landed ticket**, so it is not this
   ticket's work to smuggle in: filed in §11 as a follow-up against the 2597 surface. **Nothing that
   writes rationale may land before that gap is closed**, because §4.7's entire PII argument rests on
   the redactor behaving as documented on hostile bytes, and an unproven fix is one refactor away from
   silently regressing.
1. §4.5a + §4.5b — the schema, the run-id file, and `scripts/journal-checkpoint.sh`, with the `0600`
   write idiom from §4.8/§4.11. Schema before writers: everything downstream cites it.
2. §4.5c — the `O_APPEND` single-`write()` appender and the `mkdir` mutex, with the concurrency cases.
   Before any second writer exists, so the protocol is never retrofitted.
3. §4.1 — add `hook_io_read` to the PreCompact producer; split mechanical vs model-written records.
4. §4.9 — run-scoped freshness replacing the flat TTL, fail-closed on both ends.
5. §4.3 + §4.4 — restore-path correctness: no all-`unknown` hint, **quarantine** the unparseable
   payload, source-aware wording and consumption.
6. §4.2 — the append-only record, proved by two **compactions** rather than two checkpoints.
7. §4.6 — wire the four checkpoints, including the no-sidecar-present case.
8. §4.10 — self-compaction and the three-target GC.
9. §4.12 — documentation and the two hook-table rows, last.

## 8. Open questions for the reviewers

1. ~~**Should the redactor fixes be their own ticket?**~~ **ANSWERED AND DONE.** Both reviewers said
   yes, independently; they became `COREDEV-2597` and are implemented. Five further leak classes were
   found there that this plan had not identified. §7 step 1 is now a dependency CHECK, not the work.
2. ~~**How much free text is worth the residual risk?**~~ **ANSWERED — both reviewers converged, and it
   is implemented in §4.5a.** Gemini and codex independently proposed the bounded enum plus a short
   capped free-text field; codex added that "pointers, not prose" is valuable minimisation but **not
   sufficient** as the primary PII control, because the remaining prose is exactly where names leak.
   Adopted verbatim: a closed nine-value `reason` enum, one `note` capped at 200 chars against the
   shipped `permission-denied-log.sh:36` precedent, per-field and whole-payload byte caps, and the
   residual risk left standing in §5 rather than declared solved.
3. ~~**Should a corrupt payload really be retained?**~~ **ANSWERED — codex's answer overrides gemini's,
   and §4.3 is rewritten.** Gemini said retain it, provided the GC sweeps it. Codex refuted that on
   three specific grounds (the drafted GC covers only the journal; the active path re-logs on every
   restore; the next checkpoint destroys the evidence anyway). Codex is correct on all three, so the
   payload is **quarantined** to a private, doubly-bounded directory and the active path is cleared.

**New for round 2** — the questions this revision could not settle from inside itself:

4. **Is the `mkdir` mutex's `SIGKILL` window acceptable?** §4.5c bounds the damage to a skipped
   `live-state` rewrite (never a lost record) and declines liveness probing as over-engineering for a
   single-user CLI. That is a judgement call about an availability/complexity trade, and it is the kind
   this project has been wrong about before.
5. **Is the run-id file the right coupling?** §4.5b makes the whole journal inert when `SessionStart`
   does not fire — which is a real operational state, not a hypothetical: a stale plugin registry was
   observed writing no plugin state at all for an entire session. Fail-closed is the right default, but
   it means an unnoticed hook-registration failure silently disables journaling. Is a visible
   "journal inert" signal needed, and is `SessionStart`'s own `additionalContext` the place for it?
6. **Does the 2048-byte payload cap survive contact with four checkpoint kinds?** Five `open` plus five
   `rejected` entries at 200 chars each is 2000 bytes of `note` alone before keys and pointers. The
   caps are therefore *jointly* unsatisfiable at their maxima — deliberately, since the eviction rule
   makes the payload lossy by design rather than rejecting a write. Confirm that is the right choice
   and not a latent surprise.

## 9. Notes

- Every file:line in this plan was verified against the worktree at `a230b49`, and every behavioural
  claim was **executed** — the redactor was run against constructed inputs, the hooks were run in an
  isolated `CLAUDE_PLUGIN_DATA`, the corrupt/empty/backdated snapshot cases were reproduced, and the
  pre-commit scan was run against a scratch repo with a staged email and JWT.
- One premise in the ticket brief was found **false** and is corrected in §4.7: the pipeline does **not**
  persist only derived tokens today — `mcp/review-synthesizer/capture.py:232-234` already persists
  model-authored `finding`/`evidence`/`fix` prose through the same redaction patterns.
- `scripts/review/reviewer-roster.sh:110` cites `capture.py:362` for the status redaction call, and that
  citation is wrong. **So was this bullet's correction of it.** Round 1 said "the real line is `:376`";
  at `dbb1fb8`, `:362` is the `_STATUS_LINE` regex body and `:376` is a bare `)`. The real call is
  **`capture.py:449`** — `out[field[0]] = cap(redact_pii(field[1]), STATUS_FIELD_CAP)`.
  A bullet whose entire point is "do not copy that number — reviewers open citations" shipped a number
  that was itself uncheckable. Every file:line in this plan was **re-resolved against `dbb1fb8`** in
  round 2 for exactly this reason (§11), and the lesson generalises past this one line: a correction is
  a claim, and claims in this repo get verified or they do not get made.
- `snapshot_time` is write-only dead metadata (§4.9). A new schema can drop it; keeping it needs a
  reason.

---

## 10. Round-1 gate outcome (recorded; this plan is paused)

Both reviewers independently **confirmed every empirical claim in §4.7 by execution** — the redactor
leaves personal names untouched, corrupts `task-oriented` / `risk-assessment` / `disk-utilization` /
`~500ms` / `~40 percent`, and truncates on invalid UTF-8 while leaking `tr: Illegal byte sequence` to
stderr; `capture.py:159` already persists model-authored `finding`/`evidence`/`fix`; and
`precompact-snapshot.sh` never reads stdin. The §4.2–§4.4 restore-path reproductions were confirmed
too. The diagnosis is sound; the **implementation contract** is what needs work.

**gemini `APPROVE_WITH_NOTES`.** §8 answers: (1) split the redactor fixes into a separate ticket — they
are live bugs corrupting shipped reviewer evidence today; (2) adopt the bounded enum + short capped
free-text field; (3) retain the corrupt payload for forensic value, provided §4.10's GC sweeps it.

**codex `REQUEST_CHANGES`** — six findings:

1. **The plan promises a schema but never defines one.** §4.5 gives filenames and concepts but no exact
   keys, types, schema version, per-field/total caps, checkpoint identity, ordering, deduplication, or
   writer command — and never says how a model checkpoint *invokes* the writer or obtains the run id.
2. **The atomic-write design can lose journal entries.** tmp+rename prevents torn files but **not
   concurrent read-modify-write races**: two checkpoint writers, or a writer racing self-compaction, can
   both read version N and replace it with different N+1 versions. Needs a single-writer or locking
   protocol, tests for concurrent appends and append-versus-compaction, and a lost-update risk row.
3. **Run scoping is not sound as written.** §4.9 calls session id a "candidate", but model-written
   checkpoints have **no hook stdin** to obtain it from. Allowing empty ids to degrade to unkeyed
   restore creates cross-run replay once parser availability changes. The review-round precedent is not
   equivalent — it also discriminates on agent id, slug and TTL. Require a **non-empty exact run match**;
   missing or mismatched identity emits nothing.
4. **Corrupt-payload retention is not closed by the proposed GC.** §4.10 compacts only an oversized
   journal; it never collects corrupt `live-state` files. Retaining corruption at the *active* path also
   repeats logging and lets the next checkpoint destroy the evidence. Atomically **quarantine** it under
   a private bounded TTL/count policy and clear the active path. (This overrides gemini's §8 Q3 answer.)
5. **Scope and ordering contradict themselves.** "No change to the reviewer capture pipeline" (§2)
   conflicts with modifying `capture.py`'s redactor — resolved by the `COREDEV-2597` split. The header
   requires 2583 → 2584 → 2585 while §4.6 said either order works. And because 2584 lands first, this
   ticket's baseline is unambiguously **21 agents / 22 skills / 0 commands / 1 MCP and 11 hook events** —
   the conditional "if this ticket adds a hook event" language must be resolved, and no new event or
   kill switch is actually named.
6. **The mutation-proof suite is incomplete.** §4.2 tests two checkpoints rather than two *compactions*,
   so it can pass while the legacy overwrite remains; §§4.8–4.11 lack concrete proofs; §4.6 checkpoint
   wiring is excluded from the blanket requirement; the redactor preservation tests would pass if
   secret/home redaction were disabled entirely (needs positive controls for real `sk-…`, `pk_…`,
   `~alice/…`, email and bearer inputs on both paths, with the invalid-byte case as a shell-ingress test
   and a separate Python-ingress test proving replacement without truncation); and a fixed shape does
   not prove the token budget — assert an explicit serialized cap.

Its §8 answers: (1) split the redactor defects into a prerequisite ticket landing **before** this one;
(2) bounded rejection-reason enum + optional short rationale with exact per-field and whole-payload
caps — "pointers, not prose" is valuable minimisation but **not sufficient** as the primary PII control,
because the remaining prose is exactly where names leak; (3) do **not** retain corruption at the active
path — quarantine privately with bounded retention.

**Maintainer decision (2026-07-29):** paused; `COREDEV-2583` lands first. The redactor split is
actioned as `COREDEV-2597`.

---

## 11. Round-2 revision — how each round-1 finding is answered

**Maintainer decision (2026-08-08): unpause and decouple.** `COREDEV-2597` has landed, `COREDEV-2583`
and `COREDEV-2584` have not, and the chain that justified waiting for them was a plan-ordering choice
resting on a single checkpoint (§4.6). This section exists so a reviewer can check closure directly
instead of re-deriving it, and so a finding answered by *refusing* the round-1 proposal is visible as
such rather than buried.

| # | Round-1 codex finding | Where answered | How |
|---|---|---|---|
| 1 | Promises a schema, never defines one; no writer invocation, no run-id source | **§4.5a, §4.5b** | Full field table for both files — types, closed enums, per-field and whole-file byte caps, `v`, `id`, `seq`, ordering and dedup rules. Writer is `scripts/journal-checkpoint.sh` called via `Bash`; run id comes from a `SessionStart`-written `run-<repohash>.id`. |
| 2 | Atomic write can still lose entries (concurrent read-modify-write) | **§4.5c** | **One mutex across the whole checkpoint, the append included** (`flock` is absent on macOS, so `mkdir`). A mid-round draft exempted the append; it was reproduced as lossy (**489** records with a held fd, **160** with open-per-record) and is recorded in §4.5c so it is not reinvented. Lost-update **risk row added** (§5), concurrency cases specified. Also corrects a `PIPE_BUF` error and a shell-`>>` tearing bound the draft would have shipped. |
| 3 | Run scoping unsound; empty ids must not degrade to unkeyed | **§4.9, §4.5b** | Fail-open **withdrawn**, not softened. Non-empty exact match required at *both* ends; no run id → no write and no restore. The `context.sh` precedent cited to justify failing open is withdrawn, because codex is right that it is not equivalent. |
| 4 | Corrupt-payload retention not closed by the GC | **§4.3, §4.10** | Round-1 design **reversed**: quarantine to a private directory bounded by count *and* TTL, active path cleared. Codex's answer explicitly **overrides gemini's** §8 Q3 answer, and the case that would fail under the round-1 design is listed. |
| 5 | Scope and ordering contradict themselves; baseline ambiguous; no event or kill switch named | **Header, §2, §4.6, §4.12** | The contradiction is resolved by **decoupling** — §4.6's "either order works" was the true half. Baseline measured, not predicted: `21/21/0/1`, 10 events, at `dbb1fb8`. **No new hook event**, so no kill switch is invented to satisfy a checklist. |
| 6 | Mutation-proof suite incomplete | **§4.2, §4.5a, §4.5c, §4.6, §6, §7 step 0** | §4.2 now drives two **compactions**, not two checkpoints — round 1's proof could not fail while the defect stood. §§4.8–4.11 and §4.6 have concrete per-case proofs. Explicit serialized-cap assertions added. Redactor controls established by **mutation**: (b) and (c-order) proved, (a) proved by an absolute assertion rather than the class round 1 cited, **(c-tr) unguarded**. §6 now also requires absolute-output assertions over parity ones, and completeness-before-integrity in concurrency cases. |

**Gemini round-1 notes.** (1) split the redactor fixes — done, `COREDEV-2597`, landed. (2) bounded enum
plus short capped free text — adopted in §4.5a. (3) retain the corrupt payload — **not adopted**;
codex's contrary answer is better argued and §4.3 follows codex. Where the two reviewers disagreed, the
disagreement is recorded rather than averaged.

### Follow-ups this round deliberately did NOT perform

Each is real, each is out of scope, and each is recorded so it is not re-discovered:

1. **`COREDEV-2597`'s invalid-UTF-8 fix has no regression proof** (§7 step 0). Established by mutation:
   revert `LC_ALL=C` on the `tr` and the suite stays **green**, while the runtime behaviour silently
   truncates on `\xff` under a UTF-8 locale. Needs a shell-ingress case and a separate Python-ingress
   case, both asserting **absolute** output. Test-only work against a landed ticket. **Prerequisite for
   anything in this plan that writes rationale.**
   *Second, larger follow-up from the same investigation:* the redactor's parity suite is a
   **differential** gate blind to symmetric reverts, so several vectors that look like positive controls
   (`task-oriented`, `risk-assessment`, `disk-utilization`, `desk-checking` at `redactor_fixture.py:59`)
   prove nothing on their own. Auditing which of 2597's vectors are absolute assertions and which are
   parity-only is a `COREDEV-2597`-surface task, not this ticket's — but until it is done, "the redactor
   is gated" means less than it sounds.
2. **`AUTONOMOUS_END_TO_END_PLAN.md:18-20` still asserts the `2584 → 2585` chain** as "required, not a
   free choice". Now false. Must be corrected in **2584's own revision round** — that plan carries gate
   state, and editing a sibling's ordering claim outside its round is the drive-by edit this project
   has been burned by.
3. **`README.md:452` documents `~/.claude/unleashed-mail/` as the state directory**, which
   `COREDEV-2617`'s D′ removed (§4.12). Belongs to the 2617 surface and is being handled in that plan's
   revision round.
4. **`scripts/test-hooks.sh:660` asserts the retain-forever behaviour** this plan replaces (§6). Not a
   defect today; it becomes a contradiction the moment §4.3 lands, and the implementer must reconcile
   it in the same change rather than adding cases beside it.

### Gate status

Round 1: gemini `APPROVE_WITH_NOTES`, codex `REQUEST_CHANGES`. **Round 2 has not yet run.**
The gate arms for round 2 are **Kimi K3** (replacing the gemini arm per `KIMI_REVIEW_ARM_PLAN.md`) and
**codex**. A pass is **both arms approving AND that pair reproducing at the same digest** — one
approving round is not a pass, which this campaign has now demonstrated twice on byte-identical input.
