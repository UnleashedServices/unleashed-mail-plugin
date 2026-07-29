# Decision Journal Plan

**Status:** ⏸️ **PAUSED — draft, NOT approved.** Round 1 of the dual gate ran: gemini
`APPROVE_WITH_NOTES`, codex `REQUEST_CHANGES`. The maintainer paused this ticket so `COREDEV-2583`
lands first. **Do not implement.** Round-1 findings are recorded in §10. **Both reviewers independently
recommended splitting the live redactor defects (§4.7) into a prerequisite ticket — done, as
`COREDEV-2597`, which is no longer in this plan's scope.**
**Created:** 2026-07-29
**Last Updated:** 2026-07-29
**Ticket:** `COREDEV-2585` — Decision journal: model-written checkpoints (append-only journal +
rewritten live-state)
**Epic:** `COREDEV-2582` — Opus 5 readiness and autonomous end-to-end mode
**Branch:** `feat/COREDEV-2585-decision-journal`
**Target version:** `2.7.0` → **`2.7.1`** (patch: no asset-count change). Epic release chain:
2.6.0 (`COREDEV-2583`) → 2.7.0 (`COREDEV-2584`) → **2.7.1 (this)**.
**Depends on:** `OPUS5_ALIGNMENT_PLAN.md` (`COREDEV-2583`) and then
`AUTONOMOUS_END_TO_END_PLAN.md` (`COREDEV-2584`). **This plan lands third** — the chain is
2583 → 2584 → 2585, not a free choice: §4.6's first checkpoint records rationale against the
brainstorm fork sidecar that 2584 introduces, so landing this first would leave that checkpoint
pointing at a store that does not exist yet.

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
(`scripts/lib/context.sh:100-112`) returns a `COREDEV-NNNN`/`vX.Y.Z` token, else a 12-hex hash, else the
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
the reviewer capture pipeline, the synthesizer, or the verdict contract. **Asset counts do not change**
— this ticket adds no skill and no agent, so `21/21/0/1` holds (or `21/22/0/1` if `COREDEV-2584` has
already landed; this plan must not assert either number, only that it does not move it).

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
- `round` is computed by an **inline** glob loop (`:41-52`) rather than the shared
  `context_highest_round` (`scripts/lib/context.sh:153-165`), so it lacks that helper's `10#$n` decimal
  normalization, its `??????*` >5-digit guard, and its zsh `NOMATCH` guard. Verified experimentally: with
  `round-3`, `round-09` and `round-abc` present, the snapshot recorded `"round":"09"` — a leading-zero
  **string** where the shared helper returns `9`.

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

**Proof.** A case asserting two consecutive checkpoints produce **two** `journal.jsonl` lines and **one**
`live-state.json`, with the live state reflecting the second.

### 4.3 — A corrupt or empty snapshot still injects a content-free hint (Medium)

**Root cause.** Restore never validates the JSON. Verified with a file containing `this is not json at
all`, and again with a zero-byte file: **both emitted the full hint with every slot `unknown`** —
`ticket=unknown, branch=unknown, plan=unknown, round=unknown` — and then deleted the file.

So the failure mode is not silence. It is content-free noise injected into the model's context, followed
by destruction of the evidence. `_snap_field` (`scripts/sessionstart-restore.sh:52-69`) returns the
literal `unknown` on any parse failure and the emitter never checks whether *all* slots degraded.

**Fix.** The journal's reader must **emit nothing** when the payload does not parse or when every field
is unknown, and must **not** delete an unparseable file — an unreadable record is evidence, and deleting
it destroys the only artifact that could explain the failure. Log the parse failure instead.

**Note for the reviewer.** This inverts the current delete-always behaviour deliberately, and it needs a
GC (§4.10) so an unparseable file cannot accumulate forever.

**Proof.** Cases: corrupt payload → zero bytes emitted, file retained, one log line; all-unknown payload
→ zero bytes emitted. Both fail against today's behaviour, which is the point.

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
(`${CLAUDE_PLUGIN_DATA:-${HOME:-}/.claude/unleashed-mail}`, `scripts/lib/context.sh:23-24`), namespaced
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

### 4.6 — Checkpoints are where reasoning is irrecoverable (Medium)

**Fix.** Write a checkpoint at exactly the points where a decision is made whose *justification* exists
nowhere on disk:

| Checkpoint | Why irrecoverable |
|---|---|
| `brainstorm` Step 4b fork | The chosen option is persisted **nowhere** today — `skills/brainstorm/SKILL.md:96-97` only tells the model to carry it forward as prose across five steps. `COREDEV-2584` §4.6 introduces the sidecar; this plan records the *reasoning*. |
| Plan Review Gate verdict | The verdict is recoverable (`.verdicts/`), but the **disagreements and the minority report** are not. |
| Per-round blocker adjudication | Which findings were confirmed vs `NEEDS DISCUSSION`, **and why** — the reviewer JSON records the finding, never the adjudication. |
| Abandoned implementation approaches | Nothing on disk records a path not taken. This is the single highest-value class. |

**Note for the reviewer.** The first row is a genuine cross-ticket dependency, not decoration: if
`COREDEV-2584` lands first, this plan records rationale next to a sidecar that already exists; if it
lands second, the checkpoint is the *only* record of the fork. Either order works, but the plans must
not both claim ownership of the sidecar. `COREDEV-2584` owns the sidecar; this plan owns the rationale.

### 4.7 — Free-text rationale is the main new risk, and the shipped redactor is the wrong tool (High)

**Root cause — and a correction the plan owes the reviewers.** The premise "today the pipeline only
persists derived tokens" is **false**, and an external reviewer would catch it.
`mcp/review-synthesizer/capture.py:159-161` already persists three **model-authored free-text** fields —
`finding`, `evidence`, `fix` — each `cap(redact_pii(...))` at 500 chars; `:372-377` persists free-text
status-trailer fields the same way. The accurate sentence is: *the **shell hook** logs persist only
derived tokens plus one capped classifier `reason`* (`scripts/permission-denied-log.sh:35`, the sole
free-text shell caller). A rationale journal is an **extension of an existing precedent**, and should be
argued that way rather than as a new category.

What is genuinely new is *volume* and *shape*. And here the shipped redactor fails in three distinct
ways, all verified by running it:

**(a) It does not redact PII.** `hook_redact_pii` (`scripts/lib/hook-io.sh:226-237`) is 8 `sed -E`
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

1. **Fix the two regex defects** (`sk-`/`pk_` word boundary; `~` path context) and the `tr` locale/stderr
   bug, in **both** implementations, with tests on both sides. These are live defects affecting shipped
   callers today — arguably they should be split into their own fix rather than ride this ticket (§8 Q1).
2. **Do not rely on redaction as the PII control.** It cannot detect names. The real control is §3:
   persist pointers, not prose, and bound what prose is written to the narrow irrecoverable set (§4.6).
3. **Instruct at write time.** The checkpoint prompt states explicitly that rationale must not name
   people, customers, or organizations, and must not paste credentials — the model is the only component
   in the system that can actually apply that rule.
4. **Name which redactor.** The two are **not interchangeable**: the Python mirror exempts `@2x` and
   `~Copyable` (`capture.py:51-62`); the shell one destroys both. Whitespace folding also diverges
   (`a\n\n\tb` → shell `a   b`, Python `a b`). A plan that says "reuse the existing redactor" without
   naming one is ambiguous in a way that silently mangles Swift rationale.

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

*(a) Permissions.* `log_append` (`scripts/lib/log.sh:37`) does a plain `>>` with no mode control;
verified, the resulting `denied-commands.jsonl` is `-rw-r--r--`. Rationale is more sensitive than a
denial enum. `capture.py:399` (`_open_private_tmp`, `O_CREAT|O_EXCL|O_NOFOLLOW`, `0o600`) is the
in-repo hardened precedent.

*(b) `.gitignore` reach.* Verified with `git check-ignore -v`: `.state/`, `logs/`, `*.jsonl`, `reviews/`
are covered (`.gitignore:26-29`), so **a `.jsonl` journal is git-ignored anywhere in the tree**. But
`docs/decisions/journal.md` and `docs/planning/DECISIONS.md` are **not** ignored — a markdown or `.json`
journal in-repo is committable.

**Fix.** `.jsonl` for the record and `.json` under `.state/` for the payload, both outside the repo under
`context_base()`, both written `0600` via the `capture.py` idiom. If a human-readable in-repo view is
ever wanted, it is a *generated* artifact and needs its own `.gitignore` entry — not the primary store.

**Note for the reviewer.** `log_append` is tempting and wrong for a second reason: it has **no repo and
no session namespacing** (`scripts/lib/log.sh:28-37` — the path is `$(log_dir)/$name`, caller-supplied
basename only), and its "rotation" is destructive truncation keeping the newest `max/2` lines
(`:42-51`, default 500). It is not an append-only audit trail and must not be described as one.

### 4.9 — Replace the flat 600 s TTL with run-scoped freshness (Medium)

**Root cause.** Freshness today is `now - file_mtime < 600` (`scripts/sessionstart-restore.sh:47-49`);
the snapshot's own `snapshot_time` field is **never read** by any consumer — verified, a repo-wide grep
finds only the producer, a test fixture, and a stale plan doc. It is write-only metadata.

A wall-clock window is wrong for this ticket's purpose. A long autonomous run legitimately idles longer
than 600 s (a `codex exec` review round alone runs to ~12 min under `model_reasoning_effort=xhigh`), and
a 610-second gap is not evidence the state is irrelevant.

**Fix.** Scope freshness to the **run**, not the clock: the payload carries a run identifier, and it is
valid while that run is the current one. Wall-clock becomes a generous backstop for abandoned state
rather than the primary test.

**Note for the reviewer.** Session id is a candidate run key and is **stable across compaction** —
proven on a live transcript with seven compactions and one `sessionId` across 16,908 records. But it
reaches shell state only via `hook_str session_id` on stdin (`scripts/lib/hook-io.sh:189-198`), which is
jq → python3 **structural only, with no grep fallback** — verified by shadowing both binaries: it returns
empty. So run-scoping degrades to unkeyed on a box with no JSON parser, and the plan must state that
fail-open behaviour rather than assume the key is always present. Also note `precompact-snapshot.sh`
does not read stdin **at all** today (§4.1), so adding `hook_io_read` to it is part of this fix — it does
not already have a session id.

### 4.10 — The journal needs its own GC (Medium)

**Root cause.** There is exactly **one** housekeeping routine in the entire state layer —
`_context_round_sweep` (`scripts/lib/context.sh:190-203`), which removes only `review-round-*.json` older
than the TTL, and is called only from `context_review_round_bind`. Markers, snapshots, sentinels,
`reviews/` and `logs/` are **never** swept. Confirmed live: 19 accumulated marker files across checkouts
and 5 leftover sentinels after a 5-session gate run.

A stale snapshot is specifically never deleted — `scripts/sessionstart-restore.sh:33-34` leaves it "for
the next PreCompact to overwrite". Verified: after a 700 s backdate the file survived.

**Fix.** Self-compaction rather than truncation. On checkpoint write, if the journal exceeds a bound,
fold the oldest entries into a summary line and rewrite — the record stays complete in *meaning* while
bounded in size. This is the one place the design tolerates rewriting the append-only file, and it must
be atomic (§4.11).

**Note for the reviewer.** Do **not** reuse `log_append`'s rotation for this: it keeps the newest
`max/2` lines and discards the rest with no summary (`scripts/lib/log.sh:42-51`). For a build log that is
fine; for a decision record it silently deletes the earliest — and usually most consequential —
decisions of a run.

### 4.11 — Atomic writes: name the idiom, keep the redirect order (Medium)

**Root cause.** **Four** atomic-write idioms ship, and "reuse the established pattern" is ambiguous:

| Idiom | Where | Notes |
|---|---|---|
| `.tmp.$$` + bare `mv`, no chmod | `scripts/lib/marker.sh:105-116` | predictable temp name; default umask |
| `$path.tmp.$$` + `mv -f`, explicit `rm` both branches, no trap | `scripts/lib/context.sh:269-274` | |
| self-disarming EXIT trap | `scripts/precompact-snapshot.sh:59-70` | the compaction-safe one |
| `mktemp` + `chmod 600` + `mv -f` + symlink pre-removal | `scripts/stop-quality-marker-gate.sh:117-128` | the hardened one |

**Fix.** Use the **EXIT-trap** idiom for the journal writes — a compaction landing mid-write must never
truncate the file, and the trap is what guarantees the partial temp is removed on any early exit — with
the `mktemp`+`chmod 600` hardening from the fourth idiom for the file mode (§4.8).

**Preserve the redirect order verbatim.** `scripts/precompact-snapshot.sh:64-68` places `2>/dev/null`
**before** `> "$TMP"`, and the comment explains why: bash applies redirects left-to-right, so a trailing
`2>/dev/null` would let the open error — **which echoes the full PII-bearing tmp path** — reach stderr.
Verified: with `.state` at `chmod 500` the hook exits 0 with completely empty stderr. "Tidying" this line
reintroduces a path leak.

**Note for the reviewer.** This code survived at least eight rounds of external PR review
(`scripts/precompact-snapshot.sh:2`, COREDEV-2325 Item 5). Nearly every odd-looking construct — the
redirect order, the feature-detected `stat` (`scripts/sessionstart-restore.sh:41-45`, which deliberately
rejects a `uname == Darwin` branch because not all BSDs report Darwin), the bash substring instead of
`cut` — is a fix for a reviewer-found bug. A plan that "simplifies" any of them will be challenged, and
should be.

### 4.12 — Documentation that goes stale (Low)

If this ticket adds a hook event, nothing in CI will notice — `grep -n 'hook' scripts/validate-version-sync.sh`
returns **zero** matches — but two documented counts become false: `README.md:340` ("The plugin registers
hooks on 10 Claude Code events") and `CLAUDE.md:18` ("`hooks.json` (10 events)"). Both must be edited by
hand, together with a new row in the `README.md:342-355` hook table naming the new `UNLEASHED_*` kill
switch (every shipped hook has one; it is convention, not enforcement).

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Model-written rationale names a person, customer, or employer | **High** | The redactor provably cannot catch it (§4.7a). Controls are §3 (pointers not prose), a bounded checkpoint set (§4.6), and a write-time instruction. Stated as a residual risk, not a solved one. |
| Redaction corrupts the rationale it is meant to protect | **High** (today) | §4.7 fix 1 repairs the `sk-`/`~`/`tr` defects in both implementations before any rationale flows through them. This is a prerequisite, not a nicety. |
| A credential is pasted into rationale and survives | Medium | Only 4 credential shapes are covered; `ghp_`, `AKIA…`, `password=` are not. Nothing downstream scans a git-ignored file. Write-time instruction is the only control — say so. |
| Journal grows unbounded over a long autonomous run | Medium | §4.10 self-compaction. Explicitly not `log_append`'s truncation. |
| Restore injects noise instead of context after a corrupt write | Medium | §4.3 — emit nothing rather than an all-`unknown` hint, and retain the file as evidence. |
| Run-scoping degrades to unkeyed with no JSON parser | Low | Documented fail-open (§4.9); matches the shipped precedent at `scripts/lib/context.sh:305-308`, where session id is a soft discriminator and never the primary key. |
| A worktree and its parent checkout keep separate journals | Medium | Correct for isolation, surprising for continuity. Stated in §4.5 rather than discovered later. |
| Token budget overruns the ~1.5–2 k target | Medium | O(1) by construction (§4.5): the payload is fixed-shape. Add an explicit cap on the payload and assert it in a test. |
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

Asset counts must be **unchanged** by this ticket. The `scripts/test-hooks.sh` baseline on this branch is
**302 passed**; any behavioural change to the restore path must update the contradicting assertions in
cases 28–32 (`:623-671`) rather than leave them inconsistent.

**Mutation proof is required for every new assertion** (§4.1–§4.5, §4.7–§4.11): revert the fix, and the
new test must fail.

## 7. Implementation order

1. §4.7 fix 1 — repair the `sk-`/`pk_` boundary, the `~` context, and the `tr` locale/stderr bug in both
   redactors, with tests on both sides. **Nothing that writes rationale may land before this.**
2. §4.5 — the two-file schema and the path helpers, with the `0600` write idiom from §4.8/§4.11.
3. §4.1 — add `hook_io_read` to the PreCompact producer; split mechanical vs model-written records.
4. §4.9 — run-scoped freshness replacing the flat TTL.
5. §4.3 + §4.4 — restore-path correctness: no all-`unknown` hint, retain unparseable evidence,
   source-aware wording and consumption.
6. §4.2 — the append-only record proving two compactions lose nothing.
7. §4.6 — wire the four checkpoints.
8. §4.10 — self-compaction and GC.
9. §4.12 — documentation and the hook-table row, last.

## 8. Open questions for the reviewers

1. **Should the redactor fixes be their own ticket?** §4.7's three defects (`task-oriented` →
   `ta[redacted-secret]`, `~500ms` → `~[redacted]`, silent UTF-8 truncation) are **live bugs affecting
   shipped callers today** — `capture.py` already runs model-written findings through the same patterns,
   so reviewer evidence is being corrupted right now. Splitting them out gets a fix in sooner and keeps
   this plan's diff honest; keeping them here guarantees they land before any rationale is written. This
   plan currently keeps them (§7 step 1) but the argument for splitting is strong.
2. **How much free text is worth the residual risk?** §3 says pointers, not prose — but "why this fork
   was rejected" is irreducibly prose. Is there a tighter formulation (a bounded enum of rejection
   reasons plus a short free-text field, capped at 200 chars like
   `scripts/permission-denied-log.sh:36`) that keeps most of the value with far less exposure?
3. **Should a corrupt payload really be retained?** §4.3 proposes retaining it as evidence and logging,
   inverting today's delete-always. That trades a self-cleaning failure mode for one that needs the §4.10
   GC to be correct. Is the forensic value worth the coupling?

## 9. Notes

- Every file:line in this plan was verified against the worktree at `a230b49`, and every behavioural
  claim was **executed** — the redactor was run against constructed inputs, the hooks were run in an
  isolated `CLAUDE_PLUGIN_DATA`, the corrupt/empty/backdated snapshot cases were reproduced, and the
  pre-commit scan was run against a scratch repo with a staged email and JWT.
- One premise in the ticket brief was found **false** and is corrected in §4.7: the pipeline does **not**
  persist only derived tokens today — `mcp/review-synthesizer/capture.py:159-161` already persists
  model-authored `finding`/`evidence`/`fix` prose through the same redaction patterns.
- `scripts/review/reviewer-roster.sh:110` cites `capture.py:362` for the status redaction call; the real
  line is `:376` (`:362` is `m = _STATUS_LINE.match(ln)`). Do not copy that number — reviewers open
  citations.
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
