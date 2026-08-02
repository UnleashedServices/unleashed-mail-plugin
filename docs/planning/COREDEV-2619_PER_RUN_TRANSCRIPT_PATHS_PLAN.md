# COREDEV-2619 — Per-run transcript paths

**Status:** Planning — **NOT GATED. Latest completed round: 53** — codex `REQUEST_CHANGES` (2 High +
1 Low), all applied; the other arm produced **no verdict token** and failed closed. Every codex finding for
three rounds has been a **previous round's fix left incomplete**, most often on one of two symmetric arms.
Blocks `COREDEV-2497`, whose §7 step 1 requires this to land
first.
**Ticket:** `COREDEV-2619` (Epic `COREDEV-2485`) · **High** — a live **gate bypass**, documented by the
2026-07-19 audit as MAJ-10 and reproduced twice on this campaign.
**Measured against:** HEAD `5187467` (v2.6.6), worktree `.claude/worktrees/opus5-review`.
**Last Updated:** 2026-08-01 (round 53 findings applied; **not gated**)

---

## 0. Prior art — this was already found, and the plan must not pretend otherwise

**`docs/audits/PLUGIN_AUDIT_2026-07-19.md` MAJ-10 identified this defect twelve days before this plan
was written**, with a sharper framing than the first draft had, and with a suggested fix this plan now
adopts. Round 1's first draft cited neither. The audit's material finding:

> *"The entire Plan Review Gate evidence chain runs through fixed, shared, never-pre-cleaned /tmp paths
> … so a stale transcript from a previous round, a different plan, or a concurrent session satisfies the
> dual-review gate as if it were this round's review."*

**That is the defect: a GATE BYPASS, not a measurement error.** §1 is rewritten around it.

## 1. The defect — a stale transcript satisfies the gate

Every review of every plan, in every project, on this machine writes to two fixed names:
`/tmp/agy-out.txt` and `/tmp/codex-out.txt`, plus their `.captureid` sidecars.

**The bypass, as the audit reconstructs it.** The documented flow is 2-6 review rounds per plan, each
overwriting the same two files. Revise the plan, re-snapshot, dispatch the reviews — and one CLI
invocation fails to *start* (auth expired, a Bash-tool-level kill before `pty-capture`'s finally-write,
a `command -v agy` short-circuit). **The previous round's non-empty transcript survives.**
`skills/review-synthesis/SKILL.md` maps only *missing, empty or unparseable* to `MISSING` — **stale is
none of those** — so the old `APPROVE` prose is read as this round's verdict, and
`review-verdict.py write --reviewer gemini=APPROVE:/tmp/agy-out.txt` passes every provenance check:
non-empty, real 64-hex digest, path and captureId distinct from codex's. **All of those checks are
intra-artifact.** The digest binding covers plan bytes, never transcript freshness.

**Two independent reproductions on this campaign:**

1. **Cross-project clobber.** A round-1 codex transcript measured at 769,988 bytes from
   `/tmp/codex-out.txt` held **another project's** plan review by the time it was read — 628 `lumawake`
   hits, **zero** `COREDEV-2497`. Another project's gate round had overwritten the shared path.
2. **Destructive loss.** macOS purged `/private/tmp` under disk pressure and destroyed **105**
   transcripts between two tool calls; two rounds' findings were lost unread.

**Everything else in this plugin is repo-hash namespaced** via `scripts/lib/context.sh`; these paths
are not.

## 2. Why now — 2497 changes the failure mode, and 2617 changed the options

Today a stale transcript passes the gate silently. After `COREDEV-2497` §4.1 lands, `verify` re-digests
every transcript in an approving artifact, so a *clobbered* transcript fails closed — correctly, but
diagnosed as "digest mismatch", pointing at the reviewer rather than the collision. **2619 removes the
collision while it is still fixable in one place.**

**`COREDEV-2617` (v2.6.5) also changed the design space**, which the first draft got wrong: it assumed
`${CLAUDE_PLUGIN_DATA}` was unusable because the variable is unset outside a hook. That conflates two
mechanisms — the **environment variable** is not exported to a Bash tool, but the **`${CLAUDE_PLUGIN_DATA}`
placeholder is substituted anywhere in plugin skill content and the directory is created on first
reference** (plugins reference; confirmed by codex round 1). So the plugin data dir *is* available to a
skill recipe.

## 3. Guiding principle, and the ceiling

**Principle: a capture's path must be unique to the RUN that produced it** — not to the ticket, not to
the round. Round 1's design was per ticket/round and failed on its own terms: a sequential retry of the
same round overwrites its predecessor, which is the defect.

**Ceiling — narrowed after round 1.** This ticket removes an **accidental collision** and makes a stale
capture impossible to mistake for a fresh one. It is **not** a security boundary, and the first draft
over-claimed on three counts, each corrected:

- Captures are **not world-readable** — `pty-capture.py` forces mode `0600`.
- A pre-created leaf symlink is **refused** by `O_NOFOLLOW`, not followed.
- A deterministic `<ticket>r<round>` name **is still predictable**, so "removing predictability" was
  never what this buys.

**And the freshness check (§4.5) is accidental-staleness detection, not operator provenance** — `cp` or
`touch` defeats an mtime comparison. *(Round 2.)*

**What it does buy, security-wise: very little, and the plan no longer claims otherwise — round 6.**
A `0700` parent and an atomically allocated name remove the *predictable shared filename*, which is a
real hygiene improvement. They do **not** close the squat window on a multi-user host: an attacker who
controls any ancestor of the state directory can rename or replace the subtree however private the leaf
is, and a rule that stopped that would need a per-component trust policy this ticket has no business
inventing. Detecting a *changed*
transcript is `COREDEV-2497`; cross-checking the verdict token inside it is `COREDEV-2618`.

## 4. Findings and fixes

### 4.1 — The path scheme: per-RUN, atomically allocated (High — round 1, codex)

**Round 1 rejected the round-1 scheme.** `~/.claude/review-transcripts/<ticket>r<round>-<reviewer>.txt`
fails three ways:

- **`.claude` is a PROTECTED path.** Writes there **prompt in default mode and are denied in
  `dontAsk`**, and ordinary allow rules do not pre-approve them. The drift checks M3/M4 could pass while
  the real workflow stalls.
- **Per ticket/round is not per run.** A sequential retry overwrites; concurrent runs need a lock the
  plan never specified. **M1 (refuse) and M2 (same name re-runs cleanly) encoded contradictory
  semantics.**
- **Reservation is defeated by the existing callers.** `pty-capture.py` truncates its target, and
  `scripts/review/isolated-agy-review.sh:89` **deletes the target before launch** — so any scheme that
  reserves *the target itself* is undone by the caller.

**Fix — allocate, do not name.** `pty-capture.py` gains an allocate mode — **one command shape, used everywhere** — and it carries `--repo-hash`, because §4.1 forbids the Python allocator from reimplementing the Bash-only `context_repo_hash` *(round 7, gemini: the round-6 shape omitted it, so the allocator could not build the path it is specified to build)*:
`pty-capture.py --allocate --repo-hash <H> --ticket <T> --round <R> --reviewer <name>` *(round 6, codex: `:104` declared `--allocate <dir>` while §4.1's interface paragraph omitted `<dir>` entirely, so the wrapper and the Python parser could implement different contracts)* *(round 14, BOTH ARMS: `--base` is **removed** — the allocator owns base selection, validation, fallback and the diagnostic, and a caller-supplied base made that ownership ambiguous. A test that needs a different base sets `XDG_STATE_HOME`/`HOME`, which is what M2 already does)*. It creates the parent
`0700`, then allocates a fresh path with `O_CREAT|O_EXCL` in a retry loop, and **prints the allocated
path on stdout** so the caller propagates it rather than re-deriving it:

```
${XDG_STATE_HOME:-$HOME/.local/state}/unleashed-mail/review-transcripts/<repo-hash>/<ticket>r<round>-<reviewer>-<runid>.txt
```

**The wrapper sources `${UNLEASHED_LIB_DIR:-<script-dir>/../lib}`, resolved from its own location** —
stated here in operative text *(round 24, codex: round 23's tag move put §4.1's only occurrence of this
token **inside** `M5.3`'s cell span, so the prescribed stripping reduced it to zero and §6.0 was really
10/11, not the 11/11 I reported. **My checker had an order-of-operations bug**: it stripped round-notes
before cell spans, and removing a note creates a spurious paragraph break that truncates the span early,
letting a token inside a cell survive. Cell spans are now computed on the original text, before notes are
removed — fixing a defect I introduced in round 23 while fixing round 22's.)*.

**The three creation contracts, stated operatively here** *(round 22, codex: §4.1's only occurrences of
these were inside the proof cells `M1.13`, `M1.10` and `M1.14`, so deleting the production requirement
would have left §6.0's tokens present and the check green — masking by proof cell, the same defect as
round 18's masking by round-note, in a form the round-18 fix did not cover)*:
- the allocated path is `<base>/unleashed-mail/review-transcripts/<repo-hash>/<ticket>r<round>-<reviewer>-<runid>.txt`;
- the allocator creates the leaf with `O_CREAT|O_EXCL` and mode `0o600`;
- and it creates the `.launch` record `O_CREAT|O_EXCL` on that same call, never truncating an existing one.

The retry loop is **bounded at 8 attempts**; and `<reviewer>` is a **hard-coded literal in each skill's own
recipe**, never derived. *(Round 22: applying the proof-cell stripping rule caught these two as well —
codex named three masked tokens and the sharper check found **five**. A check that only finds what a
reviewer already told you about is not doing independent work.)*

- **Outside `.claude` entirely — round 2, and this is the SECOND directory this plan has got wrong.**
  Round 1 chose `~/.claude/review-transcripts/`; round 2's "fix" chose `${CLAUDE_PLUGIN_DATA}`, which
  **resolves to `~/.claude/plugins/data/{id}`** — *the same protected tree*. Verified on this machine:
  `/Users/nick/.claude/plugins/data/unleashed-mail-npranson-unleashed-mail-plugin`. Claude Code protects
  `.claude` except `.claude/worktrees`, so writes there prompt in default mode and are **denied** in
  `dontAsk`; "created on first reference" establishes provisioning, not write permission from a skill's
  Bash recipe. **`$HOME/.local/state` is confirmed absent from Claude Code's protected-path list** (round 3), so the
  **default** is correct. But **a set `XDG_STATE_HOME` is not guaranteed safe** — it can be relative,
  point inside `.claude`, or be unwritable. **The protected-root set, enumerated so it need not be
  invented:** `.claude` and everything beneath it **except `.claude/worktrees`** — which includes
  `.claude/plugins/data/…`, the location `COREDEV-2617` established. The implementation reads that set from
  **one place**, and `M2.2` exercises `.claude`, a `.claude/plugins/data/…` path, a canonical/symlink alias,
  **and `.claude/worktrees` as a POSITIVE (it must be accepted)** *(round 19, codex: row 1 certified
  validation against "all protected roots" while `M2.2` exercised only `.claude`, so an implementation
  treating `.claude` as the entire set passed — and a §7-only implementer had to invent the set)*.
  The allocator therefore **validates it: absolute, a DIRECTORY, outside every protected root,
  writable AND searchable (`W_OK|X_OK`)** — otherwise it falls back to `$HOME/.local/state`, **which is validated
  by the same rules**, and says so. **If the fallback also fails validation the allocator allocates
  NOTHING and exits non-zero with a diagnostic** — it never invents a third location.
  **"Writable" is defined for the FIRST-RUN case, which is the common one:** a base is valid if it exists,
  **is a DIRECTORY, is writable AND searchable (`W_OK|X_OK`)**, **or does not exist and its nearest existing
  ancestor satisfies those same three predicates** *(round 49, codex: the rule said only "exists and is
  writable", so an `exists()` + `os.access(W_OK)` validator accepts a **writable regular file** or a
  **mode-`0200` directory** — writable but not searchable — passes every stated M2 case, and then fails when
  it tries to create the transcript subtree **instead of falling back**. A base you cannot descend into is
  not a usable base)* — the allocator then
  creates it `0700`. *(Round 25, codex, High: neither operative section said whether an absent
  `$XDG_STATE_HOME` or `$HOME/.local/state` is valid, and `M2.4`'s positive fixture was not required to be
  initially absent — so an `exists()`-plus-`os.access` validator passed every stated case and then failed
  on a fresh host whose state directory has not been created yet. "Not protected" and "is writable" are
  independent predicates, and §8 had conflated them.)*
  **`M2.4`'s positive fixture is initially ABSENT**, so first-run creation is proved rather than assumed.
  **No caller passes --base, and the allocator REJECTS it if given**: selection, validation, fallback and diagnostic are the
allocator's alone. **Two distinct diagnostics, both required:** on **falling back** (XDG rejected, fallback
valid) it says so, naming the rejected value and the reason; on **terminal failure** (neither validates) it
names the rejected value and the reason and allocates nothing.
*(Round 19, codex: the contract disagreed in **both** directions — `S-ALLOC` specified a diagnostic only
when both bases fail, while §4.1 and `M2.2` require one on fallback; and `M2.18` required the terminal
message to name value and reason while §4.1, `S-ALLOC` and row 3b asked only for "a diagnostic". A
§7-conforming implementation could fail both M2 cells.)* *(Round 9, codex:
  "validated by the same rules" named no consequence, so an implementation could validate the fallback and
  then use it regardless. No allocation means no capture, which is the fail-closed direction: a review that
  cannot be recorded must not appear to have run.)* *(Round 6: the round-5 wording validated `XDG_STATE_HOME` and then fell back
  **unconditionally**, so the fallback was never checked at all. Round 7 removes the group-writable
  rationale that came with it — the narrowed rules deliberately do **not** reject a group-writable
  `$HOME`, because §3 no longer claims squat resistance.)* **The multi-user claim is NARROWED, not defended by an ancestry check — round 6.** *(codex: trusted
  ancestry is "neither sufficient nor implementable as written" — checking only the canonical base
  accepts a user-owned `0700` directory beneath an attacker-writable parent, while requiring user
  ownership of **every** ancestor rejects ordinary root-owned ones. A correct rule needs an explicit
  trust boundary and per-component policy, which is a security mechanism this ticket has no business
  inventing.)* **So §3 drops the squat-resistance claim.** A shared host on which an attacker controls an
  ancestor of the state directory is **out of scope**; detecting a transcript that was changed is
  `COREDEV-2497`'s job, not this ticket's. The unqualified
  "outside every protected tree" claim of round 2 was too strong.
- **`<repo-hash>`** — reuse `context.sh`'s existing repo-hash slug, so two checkouts cannot collide.
  Everything else in the plugin is already namespaced this way.
- **`<runid>`** — the atomically allocated component. `O_EXCL` is what makes concurrency safe; refusal
  is **not** the right behaviour, because two legitimate concurrent captures must be able to coexist.
- **Ticket/round stay in the name** for human legibility, not for uniqueness.

**The allocator takes the metadata — round 2.** `--allocate <dir>` alone cannot own a
`<ticket>r<round>-<reviewer>-<runid>` name it is never told the parts of. The repo hash comes from **one shared helper**: `context.sh`'s slug is Bash and the allocator is Python, so it is exposed once
(`context_repo_hash`, called by the wrapper) rather than reimplemented — otherwise callers rebuild parts
of the path independently, which is the drift this design exists to remove.

**The path must reach synthesis.** `skills/review-synthesis/SKILL.md` currently has **no ticket/round
input contract** — it reads two fixed names. The allocated path is therefore threaded explicitly:
`--reviewer gemini=<STATUS>:<allocated-path>`, and the skill takes the two paths as inputs.

**Proof — M5 (new, round 3): the INTEGRATION mutation M1 cannot give.** `[M5.1 propagation]` `[M5.2 re-derivation]` `[M5.15 artifact-transcriptpath]` A correct allocator whose
callers ignore its stdout and derive a fixed basename **passes M1**. So M5 drives both real paths — the
codex recipe and `isolated-agy-review.sh` — and asserts the **emitted** allocation is the capture
target, the synthesis input, **and** the artifact's `transcriptPath`. Mutate a caller to re-derive the
name: M5 must fail.

`[M5.4 two-checkout]` **Plus, round 11 (codex): M5 did not carry `S-WRAPPER`'s single-helper requirement.** M5 asserted only
that *whatever* path was emitted propagates consistently — so a wrapper using a **constant** namespace,
or one **reimplementing** the repo hash instead of calling `context_repo_hash`, passed M1–M5 while
violating both the single-helper rule and the per-checkout namespace that makes concurrent worktrees
safe. M5 therefore adds a **two-checkout** mutation: allocate from two distinct checkouts of the same
repo and assert the `<repo-hash>` segments **differ**.

**That two-checkout case does NOT prove provenance, and the round-11 reasoning behind it was wrong —
round 12, codex (High).** `context_repo_hash` is a pure function of `context_repo_root`
(`scripts/lib/context.sh:69`), so a wrapper that **copies the algorithm** yields different values for two
checkouts *and* matches the real helper in each — passing the case while violating `S-WRAPPER`'s
single-helper rule. Round 11 chose this form *over* a hard-coded expected hash on the grounds that a
reimplementation "happens to agree on the fixture"; **a reimplementation agrees on every fixture**, which
makes two-checkout strictly weaker, not stronger. The error was proving a *property of the value* when
the requirement is a *fact about the call*.
`[M5.3 stubbed-helper]` **M5 therefore STUBS the helper — through a seam, because the obvious form is unimplementable.**
*(Round 13, gemini: `S-WRAPPER` has the wrapper **source** `context.sh`, and sourcing unconditionally
redefines the function, so a stub installed by the test is clobbered the moment the wrapper runs. The
only ways left would be editing `context.sh` on disk — mutating the repo and breaking concurrent runs —
or nothing at all. The round-12 fix named the right observation and gave it no mechanism.)*
The wrapper sources **`${UNLEASHED_LIB_DIR:-<script-dir>/../lib}`**, resolved from its own location
(`S-WRAPPER`) *(round 15, BOTH ARMS: this paragraph still prescribed the `${CLAUDE_PLUGIN_ROOT}` fallback
that round 14 removed from `S-WRAPPER` — the fix landed in §7 and its counterpart in §4.1 kept asserting
the broken form. That is the third time in this plan a correction has reached one section and not the
other, which is why §6 now runs a cross-section consistency check)*. M5
points `UNLEASHED_LIB_DIR` at a temporary directory holding a stub `context.sh` whose `context_repo_hash`
prints a non-derivable sentinel, and asserts **the sentinel appears in the allocated path**. That observes
**invocation** without touching the repo, and it fails against a wrapper that reimplements or hard-codes
the hash. *(A seam that exists only for testing is a cost; the alternative is an unprovable requirement,
and this campaign has now twice shipped a "fix" that could not be run.)*
`[M5.6 brainstorm-synthesis-consumption]` **M5 also drives `brainstorm` and `review-synthesis`** and
asserts each consumes the **emitted** allocation *(round 14, BOTH ARMS: M5 drove only the codex recipe and
`isolated-agy-review.sh`, and §6.1 row 14b claimed M3 covered the other two. It does not — M3 scans for the
absence of the two old `/tmp` literals, so replacing them with `/var/tmp/codex-out.txt`, another fixed
name, or no handoff at all passes it. Absence of the old name is not presence of the new one.)*
`[M5.10 synthesis-cli-shape]` **Synthesis is invoked with the exact shape `S-THREAD` mandates** —
`--reviewer <name>=<STATUS>:<allocated-path>` — asserted against the real invocation *(round 18, gemini:
`M5.6` proved the allocation is *consumed* and nothing pinned the interface)*.
`[M5.11 wrapper-cli-signature]` **The wrapper's positional signature is exactly
`allocate-transcript.sh <ticket> <round> <reviewer>`** — a fourth argument, **an OMITTED third argument and an EMPTY third argument** are each rejected, **and the
wrapper's internal positional mapping is mutated to assert each supplied component lands in its specified
field**. **An explicitly EMPTY `<ticket>` or `<round>` — `'' B codex`, `A '' codex` — is rejected too**
*(round 38, codex: round 37 made this operative in `S-WRAPPER` and added no cell, while row 12c claimed
`M5.11` rejects "extra/omitted/empty"; `M5.11` covered an empty **third** argument and `M5.7` covered
invocations **without** ticket/round, so a wrapper using `${1:-default}` passed every defined cell and
allocated anyway. The fix reached the contract and not the proof — the mirror of round 34's defect)*.
**Every rejection case also asserts that NOTHING WAS ALLOCATED** — no leaf, no `.launch`
*(round 36, codex: the cases said only "rejected", so a wrapper that allocates from its first three
arguments and *then* exits non-zero on a fourth passed the cell while violating §7's "allocates nothing")* *(round 35, codex, High: "reject a reordering" is **not implementable** — `ticket` and `round` share
one grammar and `M1.8` requires every in-class family accepted in **all three** positions, so
`allocate-transcript.sh A B codex` is indistinguishable from a legitimate call whose ticket is `A` and round
is `B`. The wrapper has no information from which to infer caller intent, and rejecting it would demand
position-specific formats that contradict the positive grammar cases. What is checkable is that position 1
becomes the ticket, 2 the round and 3 the reviewer — so that is what the cell asserts)* *(round 32, codex: rejecting only a fourth argument
and a reordering is passed by `reviewer=${3:-codex}`, which silently defaults the reviewer and satisfies
`M5.7`, the caller scan and every normal recipe call while violating the stated interface — "exactly three"
is a claim about **too few** as much as too many)*
*(round 18, gemini)*.
`[M5.12 allocator-cli-shape]` **And the ALLOCATOR's own command line is asserted at runtime via the same RECORDING SHIM** — every
option in §4.1's shape present and spelled as specified *(round 37, gemini: "asserted at runtime" across a
Bash→Python boundary is unrunnable as interposition; the shim records `argv` and the assertion reads it)* *(round 18, codex: §6.0 compares two plan
sections and does not test the implementation, so renaming an option or dropping `--repo-hash` passed
every functional cell as long as wrapper and allocator agreed with each other)*.
`[M5.13 callers-scan]` **A repo-wide SCAN finds every review-skill reference and requires each to carry
`--ticket` and `--round`, or to sit on a committed exemption list — and the scan additionally FAILS on any
invocation whose command is assembled dynamically** (a variable-expanded or concatenated skill name), since
a text scan cannot prove such a call passes the flags *(round 45, gemini: a static scan enforcing a runtime
property is only sound if the call sites are statically visible; making dynamic construction itself a
failure keeps that assumption true rather than assuming it)* *(round 20, codex: enumerations were
claimed exhaustive twice and were wrong both times — two callers in round 18, four in round 19, six files
by scan. The cell now supplies the **discovery mechanism** a list cannot.)*
`[M5.15b full-invocation-shape]` **And the COMPLETE command shape is asserted at every non-exempt site** —
namespace (`/unleashed-mail:<gemini|codex>-review`), both flags, **and the `<plan>` operand** *(round 48,
codex: `M5.13` checked literal references plus the two flags and `M5.14` only the flag names, so a site
could keep its bare form, gain `--ticket`/`--round`, and **omit the plan operand entirely** — passing both
cells while violating `S-CALLERS`)*.
`[M5.14 invocation-syntax]` **And the flags are asserted BY NAME** — `--ticket <T> --round <N>` — not merely
that the values reach the skill *(round 20, codex: `S-CALLERS` made the syntax operative while `M5.13` and
row 32 asserted only that ticket and round are passed, so a positional or differently-named-flag
implementation passed every cell)*.
`[M5.7 missing-input-fails-closed]` **And the wrapper invoked without a ticket or round must FAIL CLOSED**,
allocating nothing and exiting non-zero — **and, at the SKILL level, a recipe that derives ticket or round
from context instead of receiving them is rejected — asserted for BOTH `gemini-review` and `codex-review`,
independently** *(round 30, codex: the cell said only "a recipe", so one skill could silently make the
inputs optional or inferred while the other complied; the caller scan supplies valid flags and so cannot
catch it)* *(round 16, codex: the wrapper-level case is passed by
a skill that silently **infers** both values and always calls with non-empty arguments, which is exactly
what §4.1's "never inferred" forbids)* *(round 14, gemini: round 13 recorded this as an accepted hole;
"an honest hole is better than false coverage, but a hole that need not exist is still a gap", and this
one is a two-line test)*.
`[M5.16 allocator-own-location]` **The relocated copy's `pty-capture.py` emits a distinct allocator marker,
and the emitted marker line must carry it** — so invoking the original checkout's allocator fails the cell
*(round 37, both arms: `S-WRAPPER` required this and no row covered it)*.
`[M5.8 production-fallback]` **And the PRODUCTION path is exercised separately**: run the wrapper with
**both `UNLEASHED_LIB_DIR` and `CLAUDE_PLUGIN_ROOT` unset**, **from a working directory outside the repo**
(`cd /`), **and from a COPY of the tree at a different absolute path whose `context.sh` returns a DISTINCT sentinel
AND whose `pty-capture.py` emits a DISTINCT allocator marker**, requiring the allocated path to carry the
copy's sentinel **and the emitted marker line to carry the copy's allocator marker** — proving both the
library **and the executable** came from the copy
*(round 37, BOTH ARMS: round 36 made only the *library* distinguishable, so a wrapper could source the
copy's sentinel `context.sh` and still invoke a **hard-coded allocator from the original checkout** — the
original allocator receives that sentinel through `--repo-hash` and produces an identical path, passing
`M5.3`, `M5.8` and `M5.12`. **Two executables are resolved and both must be distinguishable**; making one of
them so is exactly the outcome-vs-mechanism trap, on its fourth visit to this cell family)* *(round 32, codex, High: merely relocating and succeeding is still not the mechanism.
The original library remains at the hard-coded absolute path, so the very implementation this cell targets
can source **the original** and allocate successfully from the copy — `M5.3` is bypassed by its own seam and
`M5.4` still passes because the original `context_repo_hash` hashes the invocation CWD. **Third attempt at
this cell**: round 24 asserted success with the vars unset, round 31 added relocation, and both observed an
outcome two mechanisms share. Making the relocated library *distinguishable* is what finally separates
them)* *(round 31, codex, High: `cd /` alone proves only that resolution
*succeeds*, not that it is `$0`-based — a wrapper hardcoding
`LIB="${UNLEASHED_LIB_DIR:-/absolute/current-checkout/scripts/lib}"` passes `M5.3`, `M5.4` **and** `M5.8`
on this checkout and breaks the moment the plugin is installed or relocated. **Relocation is the only
observation that separates `$0` from a literal.** This is the plan's own mechanism-vs-outcome rule applied
to a cell I wrote after stating it)* *(round 16, codex: unsetting the
two variables is not enough — a `$PWD/scripts/lib` fallback passes under the natural test CWD while
violating the `$0` requirement. Only running from elsewhere discriminates the two.)* *(round 15, BOTH ARMS: M5.3 sets `UNLEASHED_LIB_DIR`, so it **bypasses the fallback
entirely** — an implementation that kept the broken `${CLAUDE_PLUGIN_ROOT}` form passed it, and §6.1 row 30
claimed the opposite. A seam-based test cannot prove the behaviour of the path the seam replaces.)*
`[M5.9 reviewer-is-a-recipe-literal]` **And `<reviewer>` is asserted to be a hard-coded literal in each
skill's own recipe** — `gemini` in `skills/gemini-review`, `codex` in `skills/codex-review` — matching
that skill's identity, never a value the skill infers or receives. The cell greps each recipe for the
literal third argument and asserts a recipe passing a *computed* reviewer is rejected.
*(Round 16, codex, High: round 15 said "the skill passes ticket and round only, and a skill that also
supplies a reviewer is rejected", which **contradicted `S-WRAPPER`'s own interface**
`allocate-transcript.sh <ticket> <round> <reviewer>` — a wrapper cannot require a third argument and
reject every caller that supplies one. I had conflated "not a skill INPUT" with "not passed by the
caller". The reviewer is passed; what it must not be is derived.)*
That is what `S-WRAPPER` requires; the two-checkout case is retained only as a secondary check that the namespace
is per-checkout at all. *(Campaign rule, earned again: **a reviewer's fix is a claim** — and so is mine.
Round 11's fix was mine, it was wrong, and it was wrong in the specific way of testing an artefact of the
mechanism instead of the mechanism.)*

**The handoff must be specified before it can be tested**, and round 3 found three gaps: where each
skill obtains ticket/round; how the **codex** recipe reaches the Bash-only `context_repo_hash` when its
grant contains no shell-helper invocation; and how the allocated path is emitted beyond the allocating
invocation. **Answered here rather than deferred — round 4, both arms.** *(Round 3 deferred them to "§8 Q2", and
Q2 is about pre-cleaning: the gaps were in no open question at all, so they were simply lost.)*

- **Ticket and round** are **required inputs** to both review skills, passed by the wrapper, not
  inferred. A skill that cannot determine them fails closed rather than guessing.
- **The codex recipe reaches `context_repo_hash` through a shared Bash wrapper**, not directly: the
  recipe invokes Python (`skills/codex-review/SKILL.md:49`; `:48` is the pre-clean §7 `S-PRECLEAN` deletes) while the helper is Bash-only
  (`scripts/lib/context.sh:79`). One wrapper sources `context.sh`, allocates, and prints — and **that
  wrapper is what the codex skill is granted**, so no recipe re-implements the hash.
- **The allocated path is emitted on stdout behind a stable marker** the wrapper captures verbatim and
  threads into the capture target, the synthesis input and the artifact's `transcriptPath`. A marker
  rather than bare stdout, so a diagnostic line cannot be mistaken for the path.

**Proof — M1, rewritten in round 2 because the first version proved nothing.** `[M1.16 runid-freshness-unstubbed]` **The production run-ID source yields a FRESH candidate on every
attempt and every run**, asserted **without stubbing it**: two allocations with identical
ticket/round/reviewer must both succeed and return different paths, **and the generator is observed
PER ATTEMPT during a forced collision — every candidate within one allocation must differ** *(round 53,
codex: observing only two top-level allocations is passed by a coarse-clock or counter generator that
differs across calls seconds apart yet **repeats within a rapid retry loop**, which is exactly when
freshness matters)*. `[M1.17 runid-entropy-source]` **And the SOURCE is asserted mechanically** — the run
ID is drawn from `secrets`/`os.urandom` and is ≥128 bits, observed by interposing on that call rather than
inferred from output *(round 53, codex: `S-ALLOC`'s ≥128-bit requirement had no discriminating cell at all;
two differing samples cannot establish entropy)* *(round 52, codex: §4.1 requires
concurrent captures to coexist, yet `M1.1`'s different-candidate case **stubs the run-ID source** and
`M1.11` proves only the eight-attempt boundary — so a production generator returning a constant, or a
coarse timestamp, passes every stubbed proof and every single-allocation integration case while repeatedly
retrying one occupied pathname and rejecting the second same-metadata capture. **The generator is what makes
allocation per-RUN**, and nothing specified or exercised it.)*
`[M1.1 sentinel-collision]` Two random basenames are
distinct anyway, and "neither truncated" observes nothing when both files start empty — the assertion
could not fail. Instead: **pre-create a sentinel at the exact candidate the allocator will try first**
(seeded by stubbing the run-ID source), containing known bytes. The allocator must retry on `EEXIST`,
return a *different* path, and **leave the sentinel's bytes untouched**. `[M1.2 parent-0700]` **And a
SEPARATE case with the transcript parent ABSENT asserts the allocator CREATES it `0700`**
*(round 40, codex: this tag sat on the sentinel-collision fixture, and pre-creating the candidate necessarily
pre-creates its parent — so asserting the parent's final mode proved nothing about creation. An allocator
that creates new parents with the default `0755`, while correctly rejecting pre-existing mis-moded ones,
passed both `M1.2` and `M1.3`. `M2.4`/`M2.22` cover the **base** directory, not this nested
`<repo-hash>/` parent, so the class was not swept either)*. *(Round 6: an
attacker-owned-ancestor mutation was specified in round 5 and is **withdrawn** with the claim it
defended — see §3.)*
Must FAIL against ordinary `create/truncate` and against a name derived from ticket/round.
**Plus, round 3:** `ticket`/`round`/`reviewer` become **filename components**, so a rejection grammar is
required: **`[A-Za-z0-9._-]+`, and the component must not be exactly `.` or `..`.**
*(Round 10, codex: the bare grammar **accepts both `.` and `..`** — verified by execution — so §7's prose
demanded a rejection its own grammar permitted, leaving §7 and M1 with contradictory acceptance criteria.
**And the stated rationale was overstated, which the fix must not preserve:** the leaf is a single
basename, `<ticket>r<round>-<reviewer>-<runid>.txt`, so a `..` component yields `..r9-gemini-x.txt` — an
ordinary filename that escapes nothing. The vector that **does** escape is the **separator** `/` (and
NUL), which the grammar already rejects. `.` and `..` are excluded because they are meaningless as
components and because the plan must not depend on the concatenation format never changing — not because
they traverse. A future round must not "restore" the traversal claim.)* And
`[M1.3 mis-moded-parent]` `makedirs(mode=0o700, exist_ok=True)` **leaves an existing `0755` parent unchanged**, so M1 must include
a mutation with a **pre-existing mis-moded parent** and assert the allocator fails closed rather than
writing into it. `[M1.12 leaf-mode-0600]` **The allocated leaf is created mode `0600`, asserted by
`stat` on the returned path** *(round 14, gemini: the tag sat on the atomicity paragraph, which asserts
nothing about mode — a tag on a heading is not a cell)*. `[M1.13 full-layout]` **And the returned path is
asserted in FULL** — `<base>/unleashed-mail/review-transcripts/<repo-hash>/<ticket>r<round>-<reviewer>-<runid>.txt`
— not just its basename *(round 14, codex: M1.9 proved the basename and M2.1 proved the dispatch lands somewhere
permitted, so a layout like `<base>/transcripts/<repo-hash>/…` passed both)*.
`[M1.15 exhaustion-diagnostic]` **The exhaustion diagnostic NAMES the exhausted parent** — asserted on
stderr, not merely a non-zero exit *(round 18, both arms: `M1.11` and row 8c required failure and said
nothing about the message, so a generic "allocation failed" satisfied the cell while violating `S-ALLOC`)*.
**The retry loop is bounded at 8 attempts**, after which the allocator exits non-zero with a diagnostic
naming the exhausted parent *(round 14, codex: `S-ALLOC` required a "bounded" loop and never said what the bound
was, so M1.11's "every candidate up to the bound" was unimplementable)*.
`[M1.4 wrong-owner-parent]` **Plus, round 9 (codex): a pre-existing WRONG-OWNER parent is a second, separate mutation.** §7 `S-ALLOC`
requires failing closed on a parent that exists "with a different mode **or owner**", but M1 proved only
the mode arm — so a mode-only implementation passed every listed M1 case while violating §7. The two
checks fail independently and each needs its own mutation. *(Where the test cannot create a
foreign-owned directory unprivileged, stub the `stat` result rather than skipping: a skipped mutation
proves nothing, and this one is unrunnable as-written in most CI.)*

`[M1.5 invalid-component]` **Plus, round 11 (gemini, High): the rejection grammar itself had NO mutation.** Every M1 case above
concerns collision, parent mode/owner and leaf mode; an allocator that **omitted component validation
entirely** passed all of them. M1 therefore includes an **invalid-component** case per rejected class —
for **each of `ticket`, `round` and `reviewer`**: a component containing `/`, an **empty** component,
and the exact values `.` and `..`
*(NUL is **not** among them — see `M1.8`: it cannot reach this argv surface, and round 16 removed it there
while leaving it here, so the two halves of the same proof disagreed — round 17, codex)* — each asserting the allocator **fails closed and allocates nothing**. *(A rejection that still
allocates is the fail-open direction and would not be caught by asserting the return code alone.)*

`[M1.6 launch-collision]` `[M1.7 launch-payload]` **Plus, round 11 (BOTH arms, concordant): the `.launch` record's CREATION had no producer-side proof.**
`S-ALLOC` requires the allocator to create `<path>.launch` with `O_EXCL`, in the same call, containing
the run ID. M1 pre-creates the *transcript* candidate but never the *launch* record, and M4 mutates the
record only **after** allocation to test `review-verdict.py` — **the consumer**. So an allocator that
used correct `O_EXCL` semantics for the transcript and a plain truncating `open(…, "w")` for `.launch`
passed every stated case in the plan. M1 therefore adds a **launch-only collision** mutation:
pre-create `<candidate>.launch` with known bytes, and require the allocator to **leave those bytes
untouched, not return the collided path, and fail closed or retry** — never truncate. M1 also asserts
the emitted record's **payload matches the §4.5 grammar** (one line, lowercase hex, no trailing content)
and **equals the run ID embedded in the returned filename**. *(This is the producer half of the anchor;
M4 remains the consumer half. Both arms found this independently, which is why it is stated here in the
proof rather than only in the round log.)*

`[M1.8 grammar-class-sweep]` **Plus, round 13 (codex): the invalid-component cases do not prove the GRAMMAR, only five values.**
M1 rejected `/`, NUL, empty, `.` and `..`, so a validator that blacklists exactly those — and accepts a
space, `@`, `:` or any other out-of-class byte — passed every case while violating `[A-Za-z0-9._-]+`.
**A blacklist of the tested values always passes a test set of those values** — and round 13's fix, which
added five more characters, is beaten by the same argument with `+`, `=`, comma or tab *(round 14, codex:
"a blacklist of those ten still accepts numerous other characters outside the class")*. **Enumeration
cannot establish a class; only the complement can.** M1 therefore sweeps the **complement
programmatically**, **anchored to the FULL string, at every POSITION, and beyond ASCII**
*(round 31, codex, High, verified by execution: the cell varied the invalid byte and the input field but
never its **position** and never required **full-string** matching — so an unanchored
`re.match(r"[A-Za-z0-9._-]+", value)` plus the named empty/`.`/`..` checks passes every specimen while
**accepting `A/../../escape`**, which is a real path escape. And a `0x01–0xFF` byte sweep misses higher
code points that reach `argv` unchanged. So: each invalid character is placed **leading, medial and
trailing**; a **valid-prefix/invalid-remainder** specimen such as `A/../../escape` must be **rejected**,
which only full-string anchoring achieves; and the sweep is **quantified over the entire argv-representable complement**, not a sample of it: for
**every** code point that can traverse `argv` and is outside `[A-Za-z0-9._-]`, a component containing it is
rejected — implemented as a property/range sweep rather than an enumeration *(round 32, codex: the round-31
wording said the sweep "includes" higher code points, which is an example, not a quantification — a
validator could reject the chosen specimens and accept some other non-ASCII character while row 4 claimed
the complete complement. "Includes" is not "for all")*)*,
**parameterized across all three inputs — `ticket`, `round` AND `reviewer`**
*(round 21, codex: the cells mutated only "a component", so an implementation validating just the exercised
position passed while accepting invalid values in the other two — the requirement is stated for three
inputs and was proved for one)*: for **every code point representable in `argv`** and not in `[A-Za-z0-9._-]` — the whole complement, not
the `0x01–0xFF` prefix of it — **swept IN-PROCESS against the validator function** (import it and call it),
with a handful of CLI specimens for the end-to-end path
*(round 35, gemini, High, measured: driving the allocator as a **subprocess** once per code point is
1,114,112 invocations at ~2.3 ms ≈ **42 minutes** — physically unrunnable in a suite that must return in
seconds. The same exhaustive sweep in-process takes **0.15 s**. This is the fourth time in this campaign a
requirement was given a mechanism that cannot run; exhaustiveness and runnability are both required, and
here they are only compatible below the process boundary)*
*(round 33, codex: round 32's quantification was written **inside a round-note**, and §6.0 classifies notes
as history rather than contract — so the operative case still swept only `0x01–0xFF`, and a validator
enforcing the grammar through `U+00FF` while accepting `U+0100` passed it. **A fix placed in a note is not
a fix**, by this plan's own rule about where contracts live)* — a component
containing it **must be rejected** — the test iterates the range rather than listing members — plus empty, `.` and
`..` as named cases.
**NUL is excluded, because it is not reachable through this surface** *(round 16, gemini, High: the sweep
required rejecting a NUL byte, but `execve` truncates `argv` at NUL and Python's `subprocess` raises
`ValueError: embedded null byte` before the call is made — verified by execution. The driver cannot
construct the invocation, so the case could never run, and the mutation was unimplementable as written.
Asserting a rejection the OS makes unreachable proves nothing about the allocator.)* And the **VALID class is swept exhaustively too** — every one of the **65** characters in `[A-Za-z0-9._-]` is
accepted — 52 letters, 10 digits, and `.`, `_`, `-`, the count **derived by the generator rather than
written as a literal** *(round 41, codex, High: round 40 said **64**, which is simply wrong — and a
64-character sweep omits one valid character, which is exactly how the over-strict validator round 40
existed to catch would have slipped through. Rejecting the exact components `.` and `..` does not remove
`.` from ordinary components like `A.B`, so it is not excluded from the class)*, in leading, medial and trailing position, **parameterized across all three inputs exactly as the
complement sweep is** *(round 40, codex, High: one acceptance case **per family** does not prove the positive
half — a range typo that rejects an unchosen valid letter or digit passes every negative complement case and
every chosen representative, while row 4 claimed full grammar coverage. **The complement was swept and the
class was sampled**; both halves of a grammar need the same treatment, and in-process both are trivially
cheap)* *(round 22, codex:
the sweep was parameterized in round 21 and its positive half still said only "a valid component", so a
validator accepting `.`/`_`/`-` in the exercised position while rejecting them in another passed every
stated case — a fix applied to one half of a proof is the same defect as one applied to one section)*. *(The acceptance half matters as much: an
over-strict validator that rejects `COREDEV-2619` fails no negative case.)*

`[M1.9 component-echo]` **Plus, round 12 (codex): the supplied COMPONENTS must appear in the returned path.** No proof asserted
it, so a wrapper that **hard-codes** ticket/round/reviewer — or an allocator that validates them and then
ignores them — passed M1–M5 while producing paths that collide across tickets. M1 asserts the returned
basename contains the exact `<ticket>`, `<round>` and `<reviewer>` it was given. **And M5 asserts the
marker discipline** `[M5.5 marker-line-discipline]`: a caller receiving **bare stdout with no
`UNLEASHED_TRANSCRIPT=` prefix must fail**, **and so must a marker line carrying anything else on it** —
leading text, a trailing comment, or a second path *(round 15, codex: the cell rejected only completely
bare stdout while row 11 claims "alone on its line", so an emitter appending commentary to the marker line
passed)*. **And the POSITIVE: a correctly formed marker line is ACCEPTED** *(round 17, codex: the cell
defined only negatives, so a caller that rejected **every** output satisfied all of them — the same
rejection-only gap this campaign has hit before)*.

**Plus, round 12 (codex, High): the sentinel cases prove NON-TRUNCATION, not ATOMICITY.** Every M1 case
above observes an *outcome* — bytes intact, a different path returned — and a **check-then-create**
implementation (`if os.path.exists(c): next_candidate()` followed by a plain `open`) produces **exactly
those outcomes** in a single-threaded test while leaving the TOCTOU race wide open. Outcome observation
cannot distinguish it; only **flag observation** can. M1 therefore **interposes on `os.open`** and asserts **`O_CREAT` and `O_EXCL` are present on the SAME
call** — `[M1.10 leaf-open-flags]` asserts the **leaf with `O_CREAT|O_EXCL` and mode `0o600`**, and
`[M1.14 launch-open-flags]` asserts the **`.launch` record `O_CREAT|O_EXCL` on that same call, never
truncating an existing one**
*(round 15, both arms: one cell cited by two rows is not two proofs; the flags are two separate opens and
each needs its own)* *(round 14, codex: asserting `O_EXCL` alone is passed
by a check-then-`touch` followed by `os.open(…, O_EXCL)` — two calls, no atomic creation. The property is
a single creating open, so both flags must be observed together)*. Likewise **one successful retry does not distinguish a bounded loop from an unbounded
one**: `[M1.11 exhausted-collision]` M1 adds an **exhausted-collision** case that pins the bound **exactly**: pre-create **7** candidates and
require the allocator to **succeed on the 8th**; pre-create **8** and require it to **fail closed** with
the diagnostic *(round 15, codex: "pre-create every candidate up to the bound" passed a two-attempt
implementation, because M1.1 proves one retry and a bare exhaustion case proves only eventual failure.
A bound is an equality, and only a pair of cases either side of it can establish one)*. *(This is the same lesson as the campaign's
"reachability ≠ discrimination": a test that the correct implementation passes is worthless unless the
wrong one fails it, and here the wrong implementation is the *plausible* one — `exists()`-then-create is
what most people write.)*

### 4.2 — The `rm -f` grants and the pre-clean commands (High — round 1, revised in rounds 2 and 6)

*(The round-1 heading read "the grants are ALREADY broken". They are not — see the reversal below. The heading contradicted its own section for four rounds.)*

Round 1 established something worse than the first draft claimed. `${HOME}` and `${CLAUDE_PLUGIN_DATA}` are **not** substituted in `allowed-tools`; `${CLAUDE_PLUGIN_ROOT}`
**is** (fixed in Claude Code 2.1.0; this plugin pins 2.1.220).

**ROUND 2 REVERSED THIS — the grants are NOT inert, and the round-1 finding was wrong.**
`${CLAUDE_PLUGIN_ROOT}` substitution in plugin `allowed-tools` was **fixed in Claude Code 2.1.0**, and
this plugin pins **2.1.220** (verified: `claude --version` → `2.1.220`). So the shipped grants *do*
expand, the round-1 "pre-existing defect" does not exist, and the validator proposed in round 1 **would
have rejected a supported placeholder and forced the removal of working grants.**

*(Recorded rather than quietly dropped: codex found this defect in round 1 and refuted it in round 2,
having checked the changelog against the pinned version the second time. A reviewer's finding is a
claim — including when the reviewer is the reliable arm, and including when I have already acted on it.)*

**What remains true** is only that the `rm -f` grants name a literal `/tmp` path this ticket removes.
**`${CLAUDE_PLUGIN_ROOT}` grants are CORRECT and stay** — the validator idea from round 1 is withdrawn
entirely, not narrowed. *(Round 3: the reversal reached §4.2's opening and **three other sites still
asserted the opposite** — the "does not expand" line below, M2's validator, and §7 `S-RELEASE`'s CHANGELOG
instruction. Applying a correction in one place and leaving its consequences standing is the exact
defect this campaign has hit in every plan; here I did it to a **reversal of a finding I had already
acted on**.)*

| skill | grant | disposition |
|---|---|---|
| `skills/codex-review/SKILL.md:7` | `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)` | **KEEP — expands correctly** (2.1.0+) |
| `skills/codex-review/SKILL.md:7` | `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)` | **ADD — round 5.** §4.1 routes codex through a shared **Bash** wrapper (it is the only way to reach the Bash-only `context_repo_hash`), and a `python3`-only grant **cannot execute it**. Without this the handoff fails authorization. gemini caught the mismatch between §4.1's design and §4.2's own table |
| `skills/codex-review/SKILL.md:7` | `Bash(rm -f /tmp/codex-out.txt*)` | **DELETE** — allocation removes the need to pre-clean |
| `skills/gemini-review/SKILL.md:8` | `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)` | **KEEP — expands correctly** |
| `skills/gemini-review/SKILL.md:8` | `Bash(rm -f /tmp/agy-out.txt*)` | **DELETE** |

*(Round 1 called this a pre-existing defect. **It is not** — see the reversal above. The `rm -f` grants
are removed because allocation makes pre-cleaning unnecessary, not because they were broken.)*

**Fix.** The pre-clean stops being a *grant* problem:

- **Allocation replaces cleaning.** With `O_EXCL` allocation there is nothing to pre-clean — a fresh
  path cannot hold a stale transcript. The `rm -f` grants are **deleted**, not rewritten.
- **The outer pre-clean is DELETED, not relocated — round 2.** Round 1 kept it, and codex showed that
  the retained `rm -f` **removes the very file `--allocate` just created with `O_EXCL`**, before
  `pty-capture.py` opens it: the atomic handoff does not survive its own caller. It is also unnecessary.
  **An allocated empty file already fails closed** — synthesis treats empty as `MISSING` — so the
  "wrapper never starts" case the audit reconstructs is covered by allocation itself, not by cleaning.
  A pre-clean only ever existed to compensate for a *shared* name.

**Proof — M2, rewritten twice.** `[M2.1 dontAsk-runtime]` `[M2.2 xdg-invalid-classes]` A **runtime** check under a pinned **`dontAsk`** permission mode
(round 3: the round-2 form never named a mode, so a direct-shell check could pass while the shipped
workflow was denied): dispatch a real skill invocation and assert the capture lands. **And exercise the XDG
validation itself** *(round 4, codex: an implementation that blindly trusts a set `XDG_STATE_HOME`
passes M2 whenever the test leaves it unset)*: run with `XDG_STATE_HOME` **relative**, **inside
`.claude`** — including a canonical/symlink alias — **inside `.claude/plugins/data/…`**, **unwritable**, **a writable REGULAR FILE**, and **a mode-`0200`
directory (writable, not searchable)**, and require the fallback **plus its diagnostic** in each
*(round 49, codex: the last two are the cases an `exists()`+`W_OK` validator passes while being unusable)*;
**and an ABSENT base whose nearest existing ancestor fails ANY of the predicates must fall back** — not
only an unwritable ancestor, but an ancestor that is **a regular file** or a **mode-`0200` directory**
*(round 52, codex: the regular-file and unsearchable-directory discriminators were added for the case where
the base **exists**, so an implementation applying the full predicate only then, and checking merely `W_OK`
on an absent base's ancestor, passed every named case and both positives while accepting
`<writable-file>/child` or `<0200-directory>/child` — failing during creation instead of falling back.
The quantifier rule on a new axis: **exists versus absent**, each needing the whole predicate set)* *(round 49,
gemini: the XDG arm had a positive for absent-but-creatable and no negative for absent-but-NOT-creatable)*.
**Plus a MUST-PASS SAFE SYMLINK, on both arms** — an `XDG_STATE_HOME` (and a `$HOME`-derived fallback)
that is a **symlink resolving to a permitted, writable location** must be **ACCEPTED**
*(round 39, codex, High: every symlink case in this cell aliases *into* a protected root, and the positive
fixture is initially absent and so is not a symlink at all — so a validator that simply **rejects every
symlink** rather than resolving it passes every stated case while breaking a perfectly ordinary setup.
Canonical resolution is "follow, then judge"; only a safe symlink that must be accepted distinguishes it
from "refuse")*.
**Plus the SIBLING-PREFIX pair, which separates component containment from a string prefix**
*(round 27, codex; verified by execution): a validator that rejects paths starting with `$HOME/.claude`
except those starting with `$HOME/.claude/worktrees` passes **every** case above, yet **accepts
`$HOME/.claude/worktrees-evil`** — which is not the exception, it merely starts like it — and **rejects a
perfectly valid `$HOME/.claude-cache`*. So: `$HOME/.claude/worktrees-evil` must be **REJECTED**, and
`$HOME/.claude-cache` must be **ACCEPTED**. Containment is by path COMPONENT, never by string prefix.* **And `.claude/worktrees` is a
POSITIVE — it must be ACCEPTED**, being the documented exception *(round 20, codex: row 1 claimed the cell
exercised `plugins/data`, an alias and the `worktrees` positive; the cell specified none of them, so an
allocator rejecting **all** of `.claude` passed. **I had edited the row and not the cell** — the same
one-side fix, in its newest form.)* Assert also that no `/tmp/` literal survives in any `allowed-tools` line.
**Plus, round 9 (codex): every case above is an INVALID value that falls back, so M2 as written was
passed by two wrong implementations** — one that ignores `XDG_STATE_HOME` entirely and always uses the
fallback, and one that validates `XDG_STATE_HOME` but then trusts the fallback blindly. Two more cases,
and they are of the two kinds this campaign keeps needing:
- `[M2.4 xdg-valid-positive]` **Positive (must PASS), with the fixture INITIALLY ABSENT:** a **valid**
  `XDG_STATE_HOME` that **does not yet exist** is **created `0700` and used** — allocation lands beneath it and
  **no** fallback diagnostic is emitted. This is the metamorphic case that kills "always fall back".
- `[M2.22 absent-fallback-positive]` **And an ABSENT `$HOME/.local/state` is created `0700` and used** when
  `XDG_STATE_HOME` is unset — **the mode is asserted** *(round 27, codex: the cell required creation and use
  but not the mode, so a fallback-specific path creating it `0755` passed, and `M2.4` checks only the XDG
  branch)* *(round 26, codex: `M2.4` covers the XDG arm and `M2.5` only invalid fallbacks,
  so an implementation accepting an absent XDG base while rejecting an absent fallback passed every stated
  cell — and the fallback is the path a fresh host actually takes)*.
- `[M2.19 fallback-diagnostic]` **On FALLING BACK, the diagnostic is asserted in every invalid class** —
  naming the rejected value and the reason, and distinct from the terminal message *(round 19, codex: the
  fallback diagnostic was required by §4.1 and by `M2.2`, absent from `S-ALLOC`, and carried by no row)*.
- `[M2.18 base-failure-diagnostic]` **And when neither base validates, the DIAGNOSTIC is asserted** —
  naming the rejected value and the reason *(round 18, gemini: `M2.5` asserted non-allocation and a
  non-zero exit but never the message `S-ALLOC` requires)*.
- `[M2.5 fallback-invalid-classes]` **Negative (must FAIL closed):** the **fallback itself** is invalid — run with `HOME` pointing at an
  unwritable directory *and* `XDG_STATE_HOME` unset, and require the allocator to **refuse to allocate**
  with a diagnostic, not to invent a path. §4.1 says the fallback "is validated by the same rules" but
  never said what a failed validation *does*; it does this.
  **The fallback arm runs the SAME case set as the XDG arm, item for item** — relative, inside a protected
  root, canonical/symlink alias, the sibling-prefix pair, a writable **regular file**, a **mode-`0200`
  directory**, and each of those again as an **absent base whose nearest existing ancestor** carries the
  defect *(round 53: written as one set applied to both arms after the fourth one-arm miss; a mechanical
  parity check now compares the two case lists and caught the `0200` case missing here)*.
  **Round 53 (codex): the fallback arm also lacks the ABSENT-ANCESTOR cases.** `M2.5` tests the fallback as
  an *existing* regular file or unsearchable directory, but never an **absent** `$HOME/.local/state` whose
  nearest existing ancestor has either defect — so a fallback-specific validator applying the full predicate
  only when the fallback exists, and merely `W_OK` when absent, passed `M2.5` and the positive `M2.22`.
  Both absent-ancestor defects now run on the fallback arm. *(**Fourth** time a fix has landed on the XDG
  arm alone. The cases are now stated as a single set applied to both arms rather than written twice.)*
  **Round 50 (codex): the fallback arm also lacks the DIRECTORY and SEARCHABILITY discriminators.** The
  writable-regular-file and writable-but-unsearchable-directory cases were added to the XDG arm only, so a
  fallback-specific `exists()`+`W_OK` validator passes every stated fallback case, accepts both invalid
  bases, and fails later during subtree creation. Both cases now run on the fallback arm too. *(Third time
  "validated by the same rules" has been instantiated on one arm — the quantifier rule exists for exactly
  this, and I applied a fix to one arm again.)*
  **Round 32 (gemini): the fallback arm still omitted the ABSOLUTE class.** `M2.5` pointed `HOME` at an
  unwritable directory and ran the component-sensitive cases, but never exercised a **relative** `HOME` — so
  an implementation accepting a relative fallback passed while violating the first of the three classes.
  The fallback arm now runs **all three**: relative, protected-root, unwritable. *(The quantifier rule found
  by the arm that has otherwise been the weaker reviewer — worth recording, because it is the reason both
  arms are kept.)*
  **Round 29 reproduction (codex): "the same rules" also means the COMPONENT-SENSITIVE cases, not just the
  three broad classes.** `M2.2`'s canonical/symlink alias, its `.claude/worktrees` acceptance and its
  sibling-prefix pair were applied to the **XDG arm only**, so a *fallback-specific* string-prefix validator
  passed `M2.5` while accepting `.claude/worktrees-evil` or rejecting `.claude-cache` — reachable through a
  symlinked `$HOME/.local`. The fallback arm therefore carries **the same case set as the XDG arm**: the
  alias, the `worktrees` positive, and the sibling-prefix pair. *(Second time this exact quantifier has bitten:
  round 19 extended "the same rules" to the three broad classes and round 27's component cases were then
  added to one arm only. **When a rule says "the same", the proof set must be copied, not sampled.**)*
  **Round 12 (codex): "the same rules" means ALL THREE classes, and this case covered only one.** The XDG
  arm is exercised against *relative*, *inside a protected root* and *unwritable*; the fallback arm tested
  **unwritable alone**, so an allocator that validated `XDG_STATE_HOME` completely and then accepted a
  **relative** or **protected-root** `$HOME`-derived fallback passed every named cell. The fallback arm
  therefore carries **one mutation per validation class**, the same three. *(A phrase like "validated by
  the same rules" is a *quantifier*; a proof set that instantiates it once has not tested it.)*
**No substitution validator** — round 1's would have rejected `${CLAUDE_PLUGIN_ROOT}`, which is
supported and correct.

`[M2.6 wrapper-grant-present]` `[M2.7 plugin-root-grants-retained]` **Plus, round 11 — two PRESENCE assertions, found while building §6.1's coverage table.** Writing that
table exposed two rows whose proof column I had filled in from memory and which **did not exist**:
- `[M2.3 no-tmp-literal]` M2 asserts **no `/tmp/` literal survives** in any `allowed-tools` line. That is an absence
  check, and **absence of a `/tmp` literal is not presence of the wrapper grant**. M2 now also asserts
  `skills/codex-review/SKILL.md` **contains** the grant `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)`
  — without it `S-WRAPPER`'s entry point is ungranted and the codex arm silently cannot allocate.
- "No substitution validator" was a **stated decision with no cell that would fail if one were added**.
  M2 now asserts the `${CLAUDE_PLUGIN_ROOT}` grants are **still present and unrewritten** in both review
  skills — the positive form of the round-2 reversal, which four prior rounds kept re-breaking.
  *(Round 12, codex: that presence assertion **still does not prove the requirement** — a substitution
  validator that is added but happens to **accept** `${CLAUDE_PLUGIN_ROOT}` passes it. The requirement is
  the **absence of the validator**, so M2 asserts no substitution-validation step exists in the skill
  pipeline; see §6.1 row 16.)* `[M2.10 validator-absence]` **The scan is bounded and the cell carries a
  mutation** *(round 20, gemini: this tag had sat on the pre-clean cluster three paragraphs away — a tag
  must sit on the text that defines it, or the bidirectional check passes while the cell is unfindable)* *(round 16, codex:
  "no validator exists" named no scan surface, so nothing would fail when a differently-named one was
  added)*: it scans repo-wide for **the withdrawn validator specifically** — a step that validates or rewrites
  `${CLAUDE_PLUGIN_ROOT}` **inside `allowed-tools` lines** — and **adds one under a different name as a
  mutation**, requiring the cell to fail.
  *(Round 18, codex, High: round 17 broadened this to "no substitution-validation step exists" repo-wide,
  which **fails against the existing repository**. `scripts/tests/test_doc_gates.py:43-83`
  (`COREDEV2504_PluginRootConvention`) is exactly such a validator — it scans agent/skill bodies, accepts
  the exact `${CLAUDE_PLUGIN_ROOT}` token and rejects non-substituted spellings — and it lives inside the
  stated scan surface. The cell could not pass without deleting an unrelated, working defence. Fixing a
  too-narrow scope by making it unbounded is not a fix; the requirement was always about the
  **`allowed-tools` validator round 1 proposed and round 2 withdrew**, not about substitution validation
  in general.)* *(Round 17, codex: the scan had been restricted to
  `skills/*/SKILL.md` and `scripts/review/*`, so adding the validator at the **natural** place —
  `scripts/validate-plugin-assembly.py`, which is where every other plugin validator lives — would not have
  failed the cell. An absence assertion is only as strong as the surface it scans, and a scope that excludes
  the most likely location is not a scan.)*

`[M2.8 preclean-command-absence]` `[M2.9 preclean-reinstate-must-fail]` **Plus, round 12 (codex, High): the pre-clean COMMANDS are invisible to an `allowed-tools` literal scan.**
The gemini pre-clean is `rm -f "$OUT" "$OUT.captureid"` (`scripts/review/isolated-agy-review.sh:89`) —
it **contains no `/tmp` literal**, so §6.1 row 15 cited a proof that could never fail on it. Worse, the
failure is **silent end-to-end**: `pty-capture.py` opens the transcript with `O_CREAT|O_TRUNC`
(`scripts/pty-capture.py:76`), so a retained pre-clean **deletes the reserved leaf and pty-capture
recreates it** — the capture lands, M5's propagation assertions pass, and the `O_EXCL` reservation this
entire ticket exists to establish is gone with nothing observing its loss.
M2 therefore adds: **(a)** a source assertion that **both** identified pre-clean commands are **absent from the files** — i.e.
  **deleted**, not merely invisible to an `allowed-tools` literal scan *(round 35, gemini: row 15 claimed
  deletion while the cell proved only invisibility to a literal scan, and those are different facts)* —
`isolated-agy-review.sh:89` and `skills/codex-review/SKILL.md:48`, matched as commands, not as `/tmp`
strings; and **(b)** a runtime mutation — **reinstate the pre-clean against an allocated path and require
the gate to FAIL, with EVERY target open observed IN-PROCESS (importing the writer) and asserted to
include no creating retry** — **not** by interposing across the skill dispatch, which spans Bash→Python and
cannot be patched from the test process *(round 37, applying gemini's own finding to the fourth cell it
also hits: rounds 35 and 37 removed this impossibility from `M2.23`/`M2.24` and then `M2.20`/`M5.12`/`M2.15`,
and `M2.9` still carried it. **Fixing a class means sweeping every instance in the same edit** — the defect
this campaign has repeated more than any other, here caught by re-reading rather than by a reviewer)*
*(round 30, codex, High: requiring only "the gate fails" is passed by a writer that catches `ENOENT`,
**retries with a creating open**, and then returns non-zero for its own reasons — `M2.11` passes on the
normal existing-leaf path and `M2.9` sees the failure it expected. The requirement is that the missing leaf
is **not recreated**, so that is what the cell observes)*. *(Absence assertions
must name what they scan for. "No `/tmp` literal" and "no `rm -f` of the allocated path" are different
claims, and only the second is the requirement.)*

#### The reservation must be HONOURED BY THE WRITER — round 13, BOTH ARMS, High

**That runtime mutation could not fail, and the reason is a hole in the design, not in the test.**
`pty-capture.py` writes its capture through `_write_private` (`:321`), whose flags are
`O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW` (`:76`). **Nothing in this plan ever required that to change.** So
on the mutation: `rm -f` deletes the reserved leaf → `pty-capture.py` **recreates it** → `.launch` is
still valid and the new transcript is *newer* than the record → freshness passes, M5's propagation passes,
**the gate PASSES**. gemini put it as "the test fails on a correct implementation"; codex put it as "the
mutation proves nothing unless capture is required to open an existing reserved leaf". **Both are the same
defect and both are right:** the plan allocated a leaf atomically and then let the writer create its own.

**An `O_EXCL` reservation that the writer does not honour is decorative.** Twelve rounds specified the
allocator in increasing detail and never once said the *capture* must land in the file the allocator
reserved. The fix is a new operative step, `S-CAPTURE`: when writing to an **allocated** path,
`pty-capture.py` opens it **without `O_CREAT` and without `O_TRUNC`** — the file must already exist, and
its absence is a **hard error**, not a creation. `O_NOFOLLOW` and the `0600` fchmod are retained.
*(The reserved leaf is created `0600` and empty, so opening it `O_WRONLY` and writing loses nothing;
the pre-existing non-allocated call sites keep the old create-if-absent behaviour, so this is gated on
the allocated-path mode rather than applied unconditionally — see `S-CAPTURE`.)*
With that invariant, the reinstate-and-must-fail mutation fails **for the reason the plan claims**: the
leaf is gone, the open fails, the capture aborts.

`[M2.11 capture-requires-existing-leaf]` **The cell, stated as a mutation rather than as a consequence**
*(round 14, gemini: the tag sat on this heading and defined nothing — the text only claimed `S-CAPTURE`
makes M2.9 pass, which is not a proof)*: **interpose on `os.open` in ALLOCATED mode — IN-PROCESS, importing the writer directly**
*(round 35, gemini, High: `M2.1` dispatches a **real skill invocation**, which spawns Bash which spawns
`pty-capture.py` — you cannot interpose `os.open`/`os.fstat`/`os.fchmod` across two process boundaries
without `LD_PRELOAD`-class measures. The **integration** assertion stays with `M2.1`; the **mechanism**
assertions run against the writer in the test process. Separating them is what makes both runnable)* and assert the flags
contain **neither `O_CREAT` nor `O_TRUNC`**, and **do** contain `O_NOFOLLOW` **and `O_NONBLOCK`**
*(round 25, codex)*. **And the other two protections are observed by their own mutations, not inferred from
the flags** *(round 27, codex: interposing on `os.open` proves the flag set and nothing else — an
implementation with exactly the right flags that dropped the `fstat` check and the `fchmod` passed
`M2.11`, `M2.9` and the non-allocated regression alike)*:
`[M2.23 allocated-nonregular-target]` **a pre-created FIFO at the allocated path is REJECTED — with a
READER HELD OPEN on it, and `os.fstat` is INTERPOSED and asserted to be called ON THE OPENED FD**, so the
rejection is attributed to the fd-based check and not to something earlier
*(round 29 reproduction, codex: observing only "the FIFO is rejected" is passed by an implementation that
replaces the required fd-based `fstat` with a **pre-open `lstat`** — it never opens the target, never calls
`fstat`, and still rejects. That substitution is exactly the TOCTOU-vulnerable form `S-CAPTURE` forbids:
a path checked before opening can change before the open. The **mechanism** is the requirement, so the
mechanism is what the cell observes)*
*(round 28, codex, High, verified by execution: with `O_WRONLY|O_NONBLOCK` and **no** reader, the open
fails `ENXIO` **before** any `fstat` runs — which is what the existing fixture at
`scripts/tests/test_pty_capture.py:48` does. An allocated-mode implementation that **deleted** the
`fstat` check therefore still rejected that FIFO and passed the cell. **My round-27 fix for a
non-discriminating cell was itself non-discriminating** — the same "reachability is not discrimination"
error, one round later. Holding a reader open makes the open succeed, so the regular-file check is the
only thing left that can fail)*, and
`[M2.24 allocated-mode-tightening]` **a leaf whose mode has been loosened to `0644` is re-tightened to
`0600` — with `os.fchmod` INTERPOSED and asserted to be called on the opened FD**
*(round 29 reproduction, codex: asserting only the final mode is passed by a **path-based `chmod`**, which
races a swapped path in a way `fchmod` on the held descriptor cannot. Same lesson as `M2.23`, same round:
an outcome assertion cannot distinguish two mechanisms that produce the same outcome)*. *(Round 14, codex: dropping only `O_CREAT` already makes a missing leaf fail, so an
implementation that kept `O_TRUNC` passed while still truncating a leaf someone else reserved — the
mutation discriminated one flag and the requirement names two.)*
`[M2.21 protected-roots-single-source]` **The protected-root set is read from ONE place** — asserted by
mutating that single definition and requiring **both** the XDG and fallback validation paths to change
behaviour together *(round 22, codex: `M2.2` proves only behaviour, so two separate-but-identical lists
passed it)*.
`[M2.20 allocated-flag-name]` **The capture interface is the flag `--allocated`, asserted by name** in
both the recipes and the writer — **and asserted to be FORWARDED to the actual `pty-capture.py` invocation
on BOTH production paths**, `scripts/review/isolated-agy-review.sh` and the codex recipe, **observed by TWO DIFFERENT mechanisms, because the two paths are not alike**
*(round 39, codex, High: `scripts/review/isolated-agy-review.sh` creates **its own detached worktree** from
the reviewed commit and invokes `$TREE/scripts/pty-capture.py` inside it — verified at `:53-56,90` — so a
shim placed in `M5.8`'s relocated copy sits in a different directory entirely and can never intercept it.
One mechanism cannot cover both, and asserting otherwise is how the class stayed unswept)*:
- **the wrapper/codex path** — replace `pty-capture.py` **at the resolved location** in `M5.8`'s relocated
  copy, whose `scripts/` directory is exactly what `$0`-relative resolution targets, with a stub that
  appends its `argv` to a file; the recorded `argv` must contain `--allocated`;
- **the nested gemini path** — first, `S-CAPTURE` requires the helper to invoke **the PLUGIN's own writer,
  resolved `$0`-relative from the helper's location**, instead of `$TREE/scripts/pty-capture.py`
  *(round 42, codex, High, verified: `$TREE` is a detached checkout of the **reviewed** commit
  (`isolated-agy-review.sh:53-56`), so the writer it runs is **the reviewed repository's**, not the
  plugin's. In this repo those coincide and everything appears to work; **in a consumer install the
  reviewed repo is the app, which has no `scripts/pty-capture.py` at all** — and against any pre-change
  commit it exposes the legacy CLI with no `--allocated`. So `M2.20` could pass against the plugin's own
  HEAD while row 15e claimed both production paths. This is a **latent bug in the existing helper**, not
  only a proof gap)* — then a **source assertion** that it passes `--allocated` on that invocation,
  **plus a runtime consequence**: with the leaf pre-allocated and the
  pre-clean removed, the capture must land in **that exact leaf**, and must **fail** when the leaf is
  absent — an end-to-end observation that only holds if the flag was genuinely honoured, and one that needs
  no interception at all; **and, decisively, the whole path is exercised against a REVIEWED TREE THAT DOES
  NOT CONTAIN `scripts/pty-capture.py`, with an assertion that the executable actually run is the one under
  the HELPER's own directory** *(round 43, codex, High: without this, a patch that keeps
  `$TREE/scripts/pty-capture.py` and merely adds `--allocated` passes against **this** repository's HEAD —
  where the plugin's writer and the reviewed tree's coincide — and fails in a consumer repo, which is the
  exact wrong implementation round 42 identified. **Round 42 promised this fixture and it never reached the
  document**: the edit's anchor did not match and my script printed success unconditionally, so the claim
  was made without the text existing. Present this round by grep, not by a script's say-so)*
*(round 38, codex, High, verified by execution: the round-37 wording put the shim **on `PATH`**, but
`S-WRAPPER` requires invoking the allocator by an **explicit self-relative path**, and an explicit path
**bypasses `PATH` lookup entirely** — measured, the real executable ran and the shim never fired. The two
fixes I added a round apart were mutually incompatible. Replacing the file the wrapper actually resolves to
is both runnable and consistent with self-relative resolution)*
*(round 37, gemini, High: the round-33 wording said "interposing on the invocation", which is the same
cross-process impossibility round 35 already removed from `M2.23`/`M2.24` — Bash spawning Python cannot be
patched from the test process without `LD_PRELOAD`-class measures. A shim on `PATH` observes the same fact
and actually runs. **Fixing this class in one cell and leaving it in three others is the propagation defect
this campaign keeps repeating.**)* *(round 33, codex, High: naming the flag proves only that the string
appears. `isolated-agy-review.sh` could **accept the flag and never pass it on**, fall back to the legacy
`O_CREAT|O_TRUNC` path, and still pass `M2.20`, `M2.11` — which tests the writer directly — and M5, which
proves only path propagation. `M2.9` was not quantified over both paths either, so the reservation was
unproved **end-to-end on the gemini arm**, which is the arm this ticket's own gate runs on)* *(round 20, codex: `S-CAPTURE` made the flag operative while `M2.11` proved
only the resulting `os.open` flags, so renaming it consistently on both sides passed the whole proof set)*.
`[M2.12 nonallocated-mode-positive]` **And the POSITIVE for the other mode**: a non-allocated call still
**creates its target if absent**, so the change is a mode and not a global regression — the requirement
`S-CAPTURE` states and nothing tested.

*(Recorded because the mechanism matters: **a coverage table built from memory certifies coverage that
does not exist.** Every row of §6.1 was re-derived from the proof text, not from recollection — the same
rule that caught an earlier consistency checker in this campaign comparing two derived sites against each
other instead of against the source.)*

### 4.3 — The site inventory, measured properly this time (Medium — round 1, codex)

**31 matched lines across 13 files**, at `78e28f2`, counting only the two output literals.

| file | lines | rewrite | quote-keep | note |
|---|---|---|---|---|
| `skills/review-synthesis/SKILL.md` | 5 | 5 | 0 | takes the two **allocated paths** as explicit inputs — not a ticket/round contract (§4.1, §7 `S-THREAD`) |
| `skills/gemini-review/SKILL.md` | 5 | 5 | 0 | its `:24` is `/tmp/agy-ping.txt`, a **different** path, and is NOT among these 5 |
| `skills/codex-review/SKILL.md` | 5 | 5 | 0 | includes the `rm -f` grant, which is **deleted** not rewritten (§4.2) |
| `docs/audits/PLUGIN_AUDIT_2026-07-19.md` | 4 | 0 | 4 | MAJ-10 — the audit finding that named this defect |
| `scripts/pty-capture.py` | 3 | 3 | 0 | `:315-320` is **live implementation commentary** ("the recipes use predictable /tmp paths"), not a historical quote — leaving it after the recipes move would ship false current-state documentation *(round 2)* |
| `skills/brainstorm/SKILL.md` | 2 | 2 | 0 | `--reviewer` examples |
| `README.md` | 1 | 1 | 0 | feature blurb |
| `scripts/review-verdict.py` | 1 | 0 | 1 | `:129`, quotes the duplicate-transcript defect |
| `scripts/tests/test_review_verdict.py` | 1 | 0 | 1 | `:146`, same |
| `CHANGELOG.md` | 1 | 0 | 1 | a shipped release note |
| `docs/planning/OCTO_ADOPTION_PLAN.md` | 1 | 0 | 1 | historical |
| `docs/planning/HANDOFF.md` | 1 | 0 | 1 | historical |
| `docs/planning/COREDEV-2497_VERIFY_TRANSCRIPTS_PLAN.md` | 1 | 0 | 1 | historical |
| **TOTAL** | **31** | **21** | **10** | 13 files |

**Totals: 31 lines, 13 files — 21 rewrites, 10 quote-keeps.**

**`/tmp/agy-ping.txt` is a separate decision.** It is the preflight ping, not an evidence artifact; it is
also a fixed shared path. **Out of scope here, recorded so it is a decision and not an oversight.**

> *(This table has now been wrong **four times**. Round 2 found `pty-capture.py:315-320` misclassified
> as a historical quote when it is **live commentary describing the current recipes** — retaining it
> after the move would ship documentation that contradicts the code. Split: **21/10**. The risk register
> independently said "12 quote-keeps" while the table said 11, so two figures in one document disagreed
> and neither matched the rows. **The lesson has stopped being about arithmetic: a hand-maintained
> inventory in prose cannot be kept true across edits, which is why M3 pins it and why the split is now
> per-file.** Earlier history: the third version was the sharpest — with the line counts
> finally correct at 31/13, the rewrite/quote-keep split still read "19 rewrites, 12 quote-keeps" while
> the rows summed to **20/11**. Draft 1 said 23/7 from a partial grep; the "correction" still said 23/7
> because it **counted `/tmp/agy-ping.txt`** — a different path — and omitted `README.md`,
> `CHANGELOG.md`, the audit and three planning docs. **Every version was internally consistent**, which
> is exactly how a wrong inventory survives review. The per-file split above is now stated so the totals
> can be summed mechanically rather than asserted, and M3 checks them.*
>
> *(Original note:)* *This table has now been wrong twice. Draft 1 said 23/7 from a partial grep; the "correction" still
> said 23/7 because it **counted `/tmp/agy-ping.txt` toward the output-literal total** — a different
> path — and omitted `README.md`, `CHANGELOG.md`, the audit and three planning docs. Both times the
> total was internally consistent, which is how a wrong inventory survives. The figures above are
> `git ls-files | xargs grep -n` over the two literals only.)*

`[M2.16 grants-deleted-not-rewritten]` **The two `rm -f` grants are DELETED, not rewritten** — the cell asserts neither skill's `allowed-tools` contains an `rm -f` grant at **any** path *(round 17, codex: row 15 covers the pre-clean COMMANDS and row 26 checks only that `/tmp` is absent, so rewriting a grant to a non-`/tmp` path passed both — `S-PRECLEAN` says delete)*.
`[M2.15 no-base-argument]` **The allocator refuses a caller-supplied base argument** — asserted by invoking it with `--base` directly
— **and no caller emits one**, asserted by the **recording shim's recorded `argv`** (the shim placed at the
resolved location, per `M2.20`) and by a **source scan of the wrapper**
*(round 38, codex: the round-37 text still said it would inspect "the wrapper's emitted command line" in the
very sentence that acknowledged the wrapper emits only its marker line. The phrase is removed rather than
re-explained — there is no such output to read)* *(deliberately paraphrased: restating §6.0's token verbatim here would mask a deletion of the operative
clause — round 22, gemini)* —
asserted against the **recording shim's recorded `argv`** and by invoking the allocator with `--base` and
requiring a non-zero unknown-argument exit *(round 38: this was a SECOND live occurrence of the
"emitted command line" phrasing, in a different sentence from the one codex cited. Removing only the cited
instance would have been the very class-not-swept defect the round-37 prompt asks reviewers to call out —
found here by grepping the phrase rather than the line number)* *(round 15, codex: the round-14 single-owner decision was
operative in §4.1 and `S-WRAPPER` but had **no discriminating cell** — a wrapper that still derived and
passed `--base` to an allocator that accepted it produced identical M2/M5 outcomes)*.
`[M2.13 captureid-freshness]` **Two successive captures produce DISTINCT `.captureid` sidecars — in BOTH
the allocated and non-allocated modes** *(round 31, codex: the cell said only "two successive captures",
so an implementation generating fresh sidecars in the exercised mode and reusing them in the other passed
while violating row 23's "per run" — the quantifier rule, applied to the two modes `S-CAPTURE` creates)*,
asserted directly *(round 14, codex: §6.1 rows 22–23 cited `pty-capture.py:322-328` — the **implementation that
generates** the ID — as though it were a proof, and `scripts/tests/test_pty_capture.py` contains **no**
case running two captures and requiring fresh sidecars. Citing production code as its own test is the
purest form of false coverage, and this can silently regress during the `S-CAPTURE` writer change.)*
`[M2.25 home-fixtures-cleared]` **`~/.local/state/unleashed-mail/review-transcripts/` contains none of the
39 synthetic fixtures** the two runaway review runs left there — asserted as a release postcondition
*(round 37, codex: `S-RELEASE` made the cleanup operative and no cell failed if it was skipped)*.
`[M2.14 version-bump]` **The release check is IN-TREE and PINS THE PRE-CHANGE VERSION**: the plan records
the version this work starts from — **`2.6.6`** — and the cell asserts `plugin.json` is **not** `2.6.6`
**and** that the CHANGELOG's newest entry equals `plugin.json`
*(round 26, codex, High: the round-25 predicate — newest entry matches `plugin.json` and differs from the
one below — **is already satisfied by the unchanged tree**: `plugin.json` is `2.6.6`, `CHANGELOG.md:16` is
`2.6.6`, `CHANGELOG.md:69` is `2.6.5`. An implementation could leave the version alone, append the ceiling
text to the existing `2.6.6` entry, and pass. **I replaced an unrunnable check with a non-discriminating
one** — the second successive failure on this same cell, and the reason a pinned literal is now used
instead of a relationship between fields that already holds.)*
*(round 25, codex, High: the round-14 form compared against "the pre-change version from the merge base",
which **cannot run in the shipped workflow** — `.github/workflows/plugin-ci.yml` checks out with the
default `fetch-depth: 1`, so on a PR the merge base is absent and on a push "merge base" does not identify
the pre-change commit. Skipping when unavailable lets an unchanged version pass; failing closed rejects a
correct bump. **A proof that cannot run in the environment that ships it is not a proof** — the third fix
in this campaign that named the right observation and gave it an unrunnable mechanism.)* *(round 14, codex:
`scripts/validate-version-sync.sh:40-56,119-120` checks current-field consistency and a matching CHANGELOG
heading, so adding the ceiling text **without bumping anything** satisfies it. Row 20 was right that no
existing cell proves a bump; the answer is to add one, not to keep the hole.)* **And the cell also asserts
the CHANGELOG entry contains the §3 ceiling text.** `[M2.17 no-inert-claim]` **A separate cell asserts the
CHANGELOG does NOT claim the `${CLAUDE_PLUGIN_ROOT}` grants were inert** *(round 16, codex: `S-RELEASE` prohibits that claim and no
cell checked it, so a CHANGELOG carrying both the ceiling and the prohibited falsehood passed)* *(round 15, codex: row 20 claimed both the bump and the
ceiling text while the cell asserted only the version comparison — omitting the ceiling still passed)*.

**Proof — M3 (was M5):** `[M3.1 inventory-drift]` a drift check asserting no output literal survives outside the enumerated
`quote-keep` set, and that the set is exactly the one above.

### 4.4 — Two existing defences must keep working (Medium)

- **`review-verdict.py`'s distinct-evidence check** — recording the same transcript for both reviewers
  once produced a **GATE OK in which one review backed both approvals**.
- **`.captureid`** — a per-run random ID, already written fresh on every capture.

**Round 1 correction: neither of these is a pre-fix failure.** `test_review_verdict.py:143-155` already
covers the first, and `pty-capture.py:322-328` already writes a fresh ID every run. They are **regression
tests**, and this plan no longer describes them as proofs that fail before the fix.

### 4.5 — Freshness, which paths alone do not give (Medium — from the audit)

Per-run paths stop a stale transcript being *reused*; they do not prove the transcript is *newer than
the gate launch*. The audit's second suggestion covers that gap: **`review-verdict.py` records and checks each transcript's mtime against **its own launch record**
(§4.5's schema below) — **not** against the snapshot sidecar. *(Round 5: this sentence still named the
sidecar while the paragraphs below replaced it, giving two incompatible operative instructions. The
sidecar is additionally wrong under concurrency: a later snapshot updates the shared mtime and would
reject a valid concurrent run.)*

**Adopted as in scope, with two round-2 corrections.**

- **It is accidental-staleness detection, not operator provenance.** A determined operator can `cp` or
  `touch` an old transcript. The first draft claimed the stronger property; §3's ceiling now covers this.
- **The explicit `--reviewed-sha256` path has no freshness anchor at all.** That path deliberately
  permits an approving write *without* a snapshot sidecar (`scripts/review-verdict.py:469-493`,
  `skills/review-synthesis/SKILL.md:143-147`), while the proposed check compares only against the
  sidecar's mtime — so M4 could pass for the sidecar case while an implementation skips freshness
  entirely whenever the explicit digest is supplied. **Resolved in round 3, by codex:** a **per-allocation LAUNCH RECORD**, created with `O_EXCL` *before*
  dispatch and bound to the returned run ID, is the anchor. **The rule: a transcript strictly OLDER than
  its `.launch` record is REJECTED; equal-or-newer is accepted** — compared by `st_mtime_ns` on **both** digest
  paths.

  **Its schema, creator and lookup — round 5, gemini.** The record is
  **`<transcript-path>.launch`**: the allocated transcript path with a `.launch` suffix, in the same
  directory, so lookup is a pure function of the `transcriptPath` already recorded in the artifact and
  `review-verdict.py` needs no index. **The allocator creates it**, in the same `--allocate` call that
  creates the leaf and before it prints the path — so "created before dispatch" is structural rather
  than a caller's obligation. **Payload and comparison — round 6, codex.** The record contains **exactly the run ID**, as a single
  line of lowercase hex, no trailing content. The expected ID is the one embedded in the transcript's
  own filename (`…-<runid>.txt`), so the check is self-contained: **`review-verdict.py` reads the record,
  requires a syntactically valid ID, and requires it to EQUAL the ID in the filename.** It **fails
  closed** when the record is absent, empty, malformed, or mismatched. *(The round-5 wording said only
  "contains the run ID", so an implementation that wrote the wrong ID and never read the payload still
  passed M4's timing assertions.)* **M4 gains a mismatched-record mutation.** *(Round 5: the plan named the mechanism and never its path, extension or creator, so nothing
  could look it up deterministically.)* The snapshot sidecar is a poor anchor independently of this, because under concurrency a later
  snapshot overwrites its mtime. **A timestamp first written when the post-review artifact is created is
  not a launch anchor at all.**

**Proof — M4, both polarities.** `[M4.1 timing-negative]` `[M4.2 timing-positive]` *Negative:* a transcript whose mtime predates its launch record is
rejected. *Positive (round 4, codex):* a transcript captured **after** an already-existing record is
**accepted**, and `[M4.10 record-precedes-dispatch]` **the record is asserted to have existed BEFORE dispatch and not to
have been replaced** — the temporal rule, distinct from the mtime comparison *(round 42, codex: `M4.2`
exercised the ordering but no row carried the requirement, so deleting it from §4.5 and `S-FRESH` left the
tag map and all eleven §6.0 tokens green)*.
Without the positive case, M4 passes against the explicitly rejected implementation that creates its
"launch" record while writing the artifact — an older transcript still predates that late record. Run
both polarities through **both digest paths**, with **nanosecond-separated** mtimes.
`[M4.9 transcript-position]` **And every mutation runs at BOTH transcript positions** — first and second reviewer — so an implementation anchoring only the first is caught *(round 30, codex)*.
`[M4.8 mtime-equality]` **And an EXACT-EQUALITY positive**: a transcript whose `st_mtime_ns` matches its
record's exactly is accepted *(round 14, codex: every stated case used separated mtimes, so an implementation
comparing `transcript <= launch` — rejecting equality — passed both polarities while violating
"equal-or-newer". The boundary is the case the two stated cells cannot see)*.
`[M4.3 absent]` **Plus the ABSENT-RECORD mutation (round 8 reproduction, codex):** delete the `.launch` entirely — the
gate must **fail**. Without it, every listed M4 case *requires a record to exist*, so an implementation
that validates only when `.launch` is present passes them all while violating §7's explicit
absent-record rejection. **codex wrote that §7 requirement itself in round 7 and then approved a proof
set that never tested it** — which is precisely why the reproduction run exists.
`[M4.4 mismatched]` `[M4.5 empty]` `[M4.6 malformed]` **Plus the MISMATCHED-RECORD mutation (round 7, gemini):** write a `.launch` whose payload is a
syntactically valid but *different* run ID from the one in the transcript's filename — the gate must
**fail**. Also cover **empty** and **malformed** payloads — **including a payload that is malformed in the SAME way
as the filename's ID, so the two still match** *(round 39, codex: the contract requires *both* a
syntactically valid lowercase-hex ID *and* equality with the filename's, but the cell said only "malformed",
so a verifier that skipped syntax validation and merely compared the two values rejected every ordinary
malformed, empty and mismatched fixture and passed the whole matrix. Equality cannot stand in for
validity)*. *(§4.5's prose announced "M4 gains a
mismatched-record mutation" and the Proof defined only the timing cases, so an implementation that never
read the payload passed. The arms disagreed here — codex reported the mutation present; it was not.)*

`[M4.7 both-digest-paths]` **EVERY mutation above runs through BOTH digest paths — round 10, codex (High).** The "both digest
paths" requirement was attached only to the **timing** polarities; the absent, mismatched, empty and
malformed mutations inherited nothing. So an implementation that validated the launch record on the
snapshot-sidecar path and **skipped validation entirely on the `--reviewed-sha256` path** passed the
whole stated suite — while violating `S-FRESH`, which keys freshness to each transcript's own record
**independently of which digest path is used**. This is the same shape as round 9's `0600` and
wrong-owner findings: **§7 stated the requirement and the proof set did not carry it.** The matrix is
therefore *(timing-negative, timing-positive, **mtime-equality**, absent, mismatched, empty, malformed)*
× *(sidecar, `--reviewed-sha256`)* × **transcript position — FIRST and SECOND reviewer**
*(round 30, codex, High: `S-FRESH` requires the record to be looked up **per transcript**, and the matrix
varied timing state and digest path only. An implementation validating just the **first** reviewer's
transcript passed every named case, because every mutation targeted that position — while accepting an
entirely unanchored second transcript, which is the two-reviewer gate this ticket exists to protect)*
— **twenty-eight** cells, none optional *(round 15, codex: the equality
positive was defined but left out of the cross-product, so an implementation using `<` on one digest
branch and `<=` on the other passed the stated matrix)*.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The chosen directory is protected or unwritable in some permission mode | **High** | §4.1 moved off `.claude`; M2 is a **runtime** check, not a string check |
| The withdrawn substitution validator is re-introduced and rejects the supported `${CLAUDE_PLUGIN_ROOT}` | **High** | §4.2 — the validator is withdrawn in §4.2, M2, §5 and §7 `S-PRECLEAN`; the `rm -f` grants are deleted, the `${CLAUDE_PLUGIN_ROOT}` grants **kept** |
| A historical quote is rewritten and the record of a real finding is corrupted | **High** | §4.3's **10** quote-keeps, pinned by M3 *(round 2: this cell said 12 while the table said 11 — the two were never reconciled, and both were wrong)* |
| Allocation is added but callers still derive the name | **High** | `--allocate` **prints** the path behind a stable marker; **M5** (integration, both real paths) fails a derived name — **M1 cannot**, since it exercises only the allocator |
| Per-run paths are read as making the gate tamper-proof | Medium | §3's ceiling, in the CHANGELOG |
| Transcripts accumulate without bound | Low | out of scope, stated |

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

Baselines at `78e28f2`: `test-hooks.sh` **304**, synthesizer **227**, scripts **324**, counts
`21/21/0/1`, hook events **10**. Floors, not equalities.

**Mutation proofs M1–M5, each shown failing before the fix and passing after.** *(Round 1: the original
M1-M6 could not meet that bar — M2 and M6 already passed, M3/M4 tested strings rather than runtime
behaviour, and M5 was unsatisfiable against a wrong inventory. The set is rebuilt.)*

### 6.0 — Cross-section consistency (added round 15, **rebuilt round 16**)

**Round 15 added this check and round 16 found it failed five of its own seven comparisons** (both arms,
independently). The defect was in the check, not only in the text: it demanded that contracts "appear
identically" while the two sections legitimately phrase things differently — `` `O_CREAT` and `O_EXCL` ``
in prose against `` `O_CREAT|O_EXCL` `` in a command description — and **no normalization was ever
defined**, so the rule was unrunnable. *(Worse: the round-15 turn reported this check "OK" after testing
**four** of the seven with loose substring matching. A check that is claimed to pass and was never run in
the form claimed is the same defect as a coverage row citing a cell that does not exist — and it is the
third time in this plan that a verification has been asserted more strongly than it was performed.)*

**The rule is now a CANONICAL TOKEN, not prose identity.** Each contract has exactly one normative token
below. **Markdown escaping is undone before comparison** — the table writes `\|` for a literal `|`
because a bare pipe would break the row *(round 22, gemini: taken literally, the escaped tokens matched
**zero** times; my checker had silently used the unescaped form, so the table and the check disagreed)*.
Every section that states the contract must contain that token **verbatim after whitespace normalization** — runs of spaces and newlines collapsed to a single space, so a line wrap is not a
divergence — and prose may say whatever else it likes around it. **The normalization is part of the rule**:
round 15's version defined none, which is why it was unrunnable as written. This is mechanically checkable, and the check is run and its result
reported before every freeze.

| contract | canonical token | must appear in |
|---|---|---|
| allocator command shape | `--allocate --repo-hash <H> --ticket <T> --round <R> --reviewer <name>` | §4.1 · `S-ALLOC` |
| lib-dir resolution | `${UNLEASHED_LIB_DIR:-<script-dir>/../lib}` | §4.1 · `S-WRAPPER` |
| leaf open flags | `leaf with `O_CREAT\|O_EXCL` and mode `0o600`` | §4.1 · `S-ALLOC` |
| `.launch` open flags | `` `.launch` record `O_CREAT\|O_EXCL` on that same call, never truncating an existing one`` | §4.1 · `S-ALLOC` |
| reviewer provenance | `hard-coded literal in each skill's own recipe` | §4.1 · `S-CALLERS` |
| retry bound | `bounded at 8 attempts` | §4.1 · `S-ALLOC` |
| path layout | `<base>/unleashed-mail/review-transcripts/<repo-hash>/<ticket>r<round>-<reviewer>-<runid>.txt` | §4.1 · `S-ALLOC` |
| base ownership | `No caller passes --base, and the allocator REJECTS it if given` | §4.1 · `S-ALLOC` · `S-WRAPPER` |
| freshness comparison | `a transcript strictly OLDER than its `.launch` record is REJECTED; equal-or-newer is accepted` | §4.5 · `S-FRESH` |
| base validation rules | `absolute, a DIRECTORY, outside every protected root, writable AND searchable (`W_OK\|X_OK`)` | §4.1 · `S-ALLOC` |
| protected-root set | `` `.claude` and everything beneath it **except `.claude/worktrees`** `` | §4.1 · `S-ALLOC` |

**The check is EXACTLY-ONCE, over text with round-notes stripped — round 18, both arms.** Presence is not
deletion sensitivity. `No caller passes --base` occurred **twice** inside `S-ALLOC`: once as the operative
requirement and once inside a round-17 note **quoting the wording it replaced** — so deleting the operative
line would have left the token present and the check green. **My own commentary about a fix masked the
fix.** Two rules follow, and both are mechanical:
1. **Cell spans are stripped FIRST, on the original text; round-notes second.** *(Round 24: the reverse
   order silently truncates a cell span — removing a note can create a paragraph break inside it — so a
   token sitting in a cell survives and the check passes when it should fail. The rule had not fixed an
   order, so two defensible implementations disagreed; this one is normative.)*
   **Round-notes (`*( … )*`) AND tagged proof-cell spans are stripped before checking.** A cell span runs
   from its `[M<n>.<k> name]` tag to the end of that paragraph. Notes are history; cells are *evidence*.
   **Neither is the contract**, and either can restate a token and hide that the contract itself is gone —
   round 18 caught the note form, round 22 caught the cell form *(all three of the path-layout and
   open-flags tokens existed in §4.1 **only** inside `M1.13`/`M1.10`/`M1.14`)*.
2. **Each token must then occur EXACTLY ONCE in each named section** — zero means the requirement is gone,
   two means something else is restating it and the check can no longer see a deletion.
Tokens are therefore **full requirement clauses**, long enough that a proof cell or a note does not restate
them verbatim. *(A shorter token is easier to satisfy accidentally, which is the failure mode above.)*

**Each token must be SITE-SPECIFIC, and that is a rule the round-16 version broke.** A single
`O_CREAT|O_EXCL` token stood for both the leaf open and the `.launch` open, and it occurs six times in this
document including historical commentary — so **deleting the `.launch` requirement entirely still left the
check reporting success** *(round 17, codex)*. A presence check whose token appears for more than one
reason cannot detect the removal of any one of them: **it can certify the exact divergence it exists to
find.** Tokens are therefore phrased to occur only at the site they govern.

**A divergence is a defect even when both wordings are individually defensible**, because §7 is the
buildable-alone section and §4.x is the reasoned one: an implementer follows §7 and then fails a proof
written against §4.x.

### 6.1 — Requirement → proof coverage (added round 11)

**Why this table exists.** Rounds 9, 10 and 11 each found the *same class* of defect — an operative
requirement stated in §7 that **no proof carried** — nine instances in three rounds: the `0600` leaf, the
wrong-owner parent, M2's fallback cases, M4's validity mutations on the second digest path, the component
grammar, the `.launch` producer semantics, the payload grammar, and M5's repo-hash provenance. Each was
found by reading, one at a time, which is why three consecutive rounds each found more. **The table turns
that reading into an enumeration.**

**The obligation is bidirectional and it is part of the plan, not a courtesy:** every operative
requirement has a row naming the proof cell that would fail if an implementation omitted it, and **adding
a requirement without adding its row is itself the defect.**

**The table's own first version was substantially wrong — round 12, codex.** Six of its rows named a
proof that did not carry the requirement, and it omitted three requirements entirely:

| row | what it claimed | why that was false |
|---|---|---|
| 11 | the stable marker is proved by M5's propagation | propagation passes with **no marker at all**; the marker had never even been *defined* |
| 15 | pre-clean deletion is proved by M2's `/tmp`-literal scan | the command is `rm -f "$OUT"` — **no `/tmp` literal**, so the cell could never fail on it |
| 16 | validator-absence is proved by "grants survive" | a validator that **accepts** `${CLAUDE_PLUGIN_ROOT}` passes that check |
| 20 | release hygiene is "not machine-checkable" | **false** — version sync and a CHANGELOG string are both checkable; the rationale excused the only unproved row |
| 8, 12 | `O_EXCL` and helper provenance are proved by outcome observation | a check-then-create and a copied hash produce **identical outcomes** (see M1, M5) |
| — | 1, 3 prove "the fallback is validated by the same rules" | only **one** of the three validation classes was instantiated |

**Two lessons, both already campaign rules, both re-earned here.** *A row whose proof column reads "none"
must say why — and "not machine-checkable" is a claim that must itself be checked; row 20's was simply
untrue.* And **an absence assertion must name what it scans for**: "no `/tmp` literal" and "no `rm -f` of
the allocated path" are different claims, and only the second was ever the requirement.

**The isolation harness does NOT contain writes outside the repo — corrected round 36.** Twice in this
campaign the gemini arm *implemented* the plan instead of reviewing it (rounds 25 and 36). Both times the
harness kept the **repository** pristine — tree clean, digest identical, none of the claimed edits present —
and both times I reported "zero damage" on that basis. **That verification was incomplete.** Both runs also
created `~/.local/state/unleashed-mail/review-transcripts/` and 39 synthetic fixtures there
(`COREDEV-9999`, `testhash`, `abc`, `h1`), at `00:15` and `03:53`. The harness diffs the git worktree; it
does not sandbox `$HOME`. The artifacts are inert — nothing reads that path until this ticket ships — but
they sit in **exactly the directory this plan allocates into**, so `S-RELEASE` must clear them before the
allocator goes live, and the harness's containment claim must be stated as *repo-only*.

**The reproduction rule has now paid for itself FOUR times — round 29.** Round 29 was this plan's **first
double approval**: gemini `APPROVE_WITH_NOTES`, codex `APPROVE` with the words *"No findings."* The
mandatory re-run at the **byte-identical digest** returned codex `REQUEST_CHANGES` with **two High
findings**, both real, both since fixed — over-certified fallback coverage, and two cells that observed an
outcome where the contract names a mechanism. **An approving round is evidence about that run, not about
the document.** Nothing here was gated on it.

**Mechanism-vs-outcome rule (round 29 reproduction, codex): when a contract names a MECHANISM, the cell
must observe the mechanism.** `M2.23` asserted "the FIFO is rejected" — passed by a pre-open `lstat` that
never opens the target; `M2.24` asserted "the mode ends up `0600`" — passed by a path-based `chmod`. Both
substitutes are the TOCTOU-vulnerable forms the contract exists to exclude, and **an outcome assertion
cannot separate two mechanisms that produce the same outcome.**

**Quantifier rule (round 30 — the generalisation of the property-count rule, after three consecutive
rounds of the same failure).** When a requirement quantifies over a set — *both* skills, *every* transcript,
*all three* inputs, *each* digest path, *the same* rules — **the cell must be parameterized over that set,
not instantiated at one member.** Rounds 27, 29-reproduction and 30 each found cells that were correct for
one member and silent about the rest: three inputs proved for one, the fallback arm sampled instead of
copied, `M4` varied timing and digest path but never transcript position, `M5.7` said "a recipe" and meant
two. **A universally quantified requirement with a single-instance proof is an unproved requirement.**

**Property-count rule (round 27, codex): if a requirement enumerates N properties, its cell must OBSERVE
N.** Three findings in one round were this shape — `S-CAPTURE` named four retained protections and `M2.11`
observed only the flag set; the fallback had to be *created `0700`* and `M2.22` asserted only creation; the
protected-root set is a **component** containment and `M2.2` exercised only cases a string-prefix check also
satisfies. **A cell that observes a subset of a conjunction proves the subset**, and the row that cites it
silently claims the whole. When a requirement gains a clause, its cell needs a matching assertion in the
same edit.

**Name-consistency rule (round 21, codex): one tag ID carries exactly ONE name, everywhere.** `M5.13` was
renamed `existing-callers-updated` → `callers-scan` in the proof and the table while §7 kept the old name,
so the document held **59 tag occurrences for 58 cells**. My verification counted definitions only in the
text *before* §6.1, so a §7 citation under a stale name was invisible to it — **the checker could not see
the class of error it was written to catch.** It now groups occurrences by ID and asserts a single name.
*(Seventh instance of a rename reaching some sites and not others; the first one a mechanical check
missed.)*

**Round 44, gemini — REJECTED on both counts; THIRD false masking claim.** It reported (a) the lib token
occurring twice in §4.1 with "neither occurrence inside a note or a proof-cell span", and (b) two tokens
claiming `S-WRAPPER` membership they lack. Both are checkable and both are wrong:
- **(a)** the raw count is indeed 2, but one occurrence sits **inside `M5.3`'s cell span** and is stripped,
  so the counted total is 1. The property that matters is deletion sensitivity, and it holds: deleting the
  **operative** statement drops §4.1's count to **0** and fails the check, while deleting the cell-internal
  one correctly changes nothing — evidence is not contract. *(Run the deletion test, not the raw grep.)*
- **(b)** §6.0's table names **`§4.1 · S-ALLOC`** for both tokens, not `S-WRAPPER`. The claim misread the
  table it was auditing.
codex, independently and in the same round, reported all eleven tokens exactly-once with every governing
occurrence deletion-sensitive and no third carrier — which the deletion test confirms.

**Round 33, gemini High — REJECTED, and this is the SECOND time the same claim failed the same check.**
It reported the `bounded at 8 attempts` token occurring twice in §4.1 "outside of proof cells and round
notes", masking a deletion. The second occurrence is **inside the M1 proof paragraph** and is stripped as a
cell span; the deletion test drops the §4.1 count to **0**, so the check is deletion-sensitive exactly as
designed. The identical claim was raised and disproved in round 29. *(Recorded rather than re-argued each
round: a reviewer repeating a refuted claim is not new evidence, and re-verifying it — which I did — is
cheap enough to keep doing.)*

**Round 24, gemini High #1 — REJECTED, and checked both ways.** It reported the base-ownership token
"completely absent from §4.1". Raw `grep` agrees: **zero** literal matches, because the sentence is
line-wrapped there. But §6.0's rule mandates whitespace normalization *before* comparison, and under the
rule the token occurs **exactly once**. The finding applied the check without the normalization step the
check specifies. *(Recorded because the opposite error — my own — happened in the same round: codex's High
was correct and my checker was buggy. An arm being wrong once is not evidence about the next finding.)*

**A reviewer's cited constraint is itself a claim — round 23.** gemini returned a High finding rejecting
`M1.10`'s `os.open` interposition as violating an instruction *"Does the plan propose mocking time, wrapping
os.open … If so, REJECT"*. **No prompt in this campaign has ever contained that sentence** — verified by
grep across every round's prompt, zero matches — and round 23's prompt in fact asks the reviewer to
*validate* the interposition. The finding was **not** applied. Interposition stays: it is the only
mechanism that distinguishes a single atomic create from check-then-create, which is precisely what
`S-ALLOC` requires. *(Recorded because the campaign rule cuts both ways — a fix of mine is a claim, and so
is a constraint a reviewer attributes to its own instructions.)*

**Rewrite rule (round 48): an edit that REPLACES a clause must state what it keeps.** Two operative rules
were lost this way — row 4's `.`/`..` rejection (round 40) and `S-ALLOC`'s component containment (round 35)
— each time because a new clause was written *over* the old one instead of beside it. After round 48 every
§6.1 row's claim was swept against its named step's **note-stripped** operative text; the three further
candidates were inspected and are phrasing differences, not losses. *(The same sweep also showed my
round-41 check had passed this clause only because it did not strip notes — a checker reading history as
contract, which is the error this campaign most often corrects in reviewers.)*

**Placement rule (round 20, gemini): a tag sits on the text that DEFINES its cell.** `M2.10`'s tag had
drifted onto the pre-clean cluster three paragraphs from its own mutation — the bidirectional check still
passed, because it verifies that a tag exists and is cited, not that it labels the right sentence. *(Five
`M2.x` cells added in rounds 17–19 also sit at the end of §4.3 rather than beside the mechanisms they
prove. That is a **readability** defect, not a correctness one — each is defined exactly once and cited
exactly once — and it is recorded here rather than fixed by moving text mid-campaign: an attempt to
relocate them consumed two section headings and duplicated four cells, which is a worse failure than the
one being fixed. It is a cleanup for the implementation commit, tracked in `S-RELEASE`.)*

**Convention (round 13, corrected round 14): every row cites either a TAGGED CELL** — of the form
`[M<n>.<k> short-name]`, placed verbatim in the proof text — **or a NAMED EXISTING TEST** with `file:line`, for
requirements that are pre-existing regressions rather than new proofs. **Row 22 is the only instance of the
second form** and its citation was re-read at round 14
(`scripts/tests/test_review_verdict.py:143` — `test_one_transcript_cannot_back_TWO_approvals`).
*(Round 14, codex, Low: the round-13 wording claimed "every row cites a TAGGED CELL" while four rows cited
none, and it miscounted the tags. A convention stated more strongly than it is followed is the same defect
as a coverage row stated more strongly than its proof.)* Round 12's "quote a phrase" convention was applied to **four** rows and
violated by the other **25** (gemini, round 13), which is the same one-place-fix defect the plan keeps
hitting. Tags are exact tokens, so the mapping is checked by string match in both directions: **every row
cites a tag that exists, and every tag is cited by a row.** A requirement with no tag is an uncovered
requirement, and that is now visible rather than arguable.

| # | requirement (source) | proof cell |
|---|---|---|
| 1 | base validated: absolute, **a DIRECTORY**, **canonically resolved (follow, then judge)**, outside the protected-root set by path COMPONENT, **writable AND searchable (`W_OK\|X_OK`)** (`S-ALLOC`, §4.1) | `[M2.2 xdg-invalid-classes]` — incl. the **sibling-prefix pair** `.claude/worktrees-evil` (reject) and `.claude-cache` (accept), which a string-prefix check fails (round 27, codex) |
| 2 | a **valid** `XDG_STATE_HOME` is **used**, including when **absent-but-creatable** — ancestor satisfying the **complete** predicate set, discriminated on both arms (§4.1) | `[M2.4 xdg-valid-positive]` — fixture initially absent (round 25, codex) |
| 2b | an **absent** `$HOME/.local/state` fallback is created **`0700`** and used (§4.1) | `[M2.22 absent-fallback-positive]` (round 27 — the cell had not asserted the mode) |
| 3 | fallback validated by the **same complete predicate set, existing AND absent-ancestor** — absolute, directory, outside protected roots by component, `W_OK\|X_OK` — incl. the regular-file and unsearchable-directory discriminators; neither valid ⇒ allocate nothing, exit non-zero (§4.1) | `[M2.5 fallback-invalid-classes]` |
| 4 | component grammar `[A-Za-z0-9._-]+` full-string anchored, **both halves swept** — complement rejected, all **65** valid chars accepted, **and the exact values `.` and `..` rejected** (`S-ALLOC`, §4.1) | `[M1.5 invalid-component]` + `[M1.8 grammar-class-sweep]` — a programmatic sweep of the **complement**, since no enumeration establishes a class (round 14) |
| 5 | the **nested transcript parent** is CREATED `0700` when absent (`S-ALLOC`) | `[M1.2 parent-0700]` — absent-parent case, not the pre-created sentinel's parent (round 40, codex) |
| 6 | fail closed on pre-existing **mis-moded** parent (`S-ALLOC`) | `[M1.3 mis-moded-parent]` |
| 7 | fail closed on pre-existing **wrong-owner** parent (`S-ALLOC`) | `[M1.4 wrong-owner-parent]` |
| 8 | leaf created `O_CREAT\|O_EXCL` — **both flags, one call** (`S-ALLOC`) | `[M1.1 sentinel-collision]` + `[M1.10 leaf-open-flags]` (round 14 — `O_EXCL` alone is passed by check-then-`touch`) |
| 8e | the run-ID source yields a fresh candidate **per attempt and per run** (`S-ALLOC`, §4.1) | `[M1.16 runid-freshness-unstubbed]` — two same-metadata allocations **plus per-attempt observation during a forced collision**, source not stubbed (round 53, codex) |
| 8f | the run ID is drawn from a CSPRNG with **≥128 bits** (`S-ALLOC`) | `[M1.17 runid-entropy-source]` — the source call is interposed, not inferred from output (round 53, codex) |
| 8b | leaf mode `0o600` (`S-ALLOC`) | `[M1.12 leaf-mode-0600]` |
| 8c | retry is bounded at **8 attempts**, then exits non-zero (`S-ALLOC`) | `[M1.11 exhausted-collision]` (round 14 — "bounded" with no stated bound was unimplementable) |
| 9 | `<path>.launch` created `O_CREAT\|O_EXCL`, same call, **never truncating** (`S-ALLOC`, now operative — round 17) | `[M1.6 launch-collision]` + `[M1.14 launch-open-flags]` |
| 10 | payload = one line lowercase hex, **equal to the run ID in the filename** (`S-ALLOC`, §4.5) | `[M1.7 launch-payload]` |
| 11 | path printed behind `UNLEASHED_TRANSCRIPT=`, **alone on its line** (`S-ALLOC`) | `[M5.5 marker-line-discipline]` (round 15 — the cell rejected only bare stdout, not a marker line with extra content) |
| 11b | supplied ticket/round/reviewer appear in the returned path (`S-ALLOC`) | `[M1.9 component-echo]` |
| 12 | wrapper obtains the namespace **by calling** `context_repo_hash` (`S-WRAPPER`) | `[M5.3 stubbed-helper]` (via the `UNLEASHED_LIB_DIR` seam — round 13) |
| 12b | the namespace is per-checkout (`S-WRAPPER`, §4.1) | `[M5.4 two-checkout]` (secondary) |
| 13 | wrapper is the granted codex entry point (`S-WRAPPER`, §4.2) | `[M2.6 wrapper-grant-present]` |
| 14 | allocated path threaded to **`isolated-agy-review.sh` and the codex recipe** (`S-THREAD`) | `[M5.1 propagation]` + `[M5.2 re-derivation]` |
| 14d | the emitted allocation becomes the artifact's `transcriptPath` (`S-M5`) | `[M5.15 artifact-transcriptpath]` (round 21, codex — `S-M5` requires it, `M5` asserts it, and no row carried it) |
| 14b | …and to `brainstorm` + `review-synthesis` (`S-THREAD`) | `[M5.6 brainstorm-synthesis-consumption]` (round 14, both arms — the round-13 claim that M3 covered these was **false**: M3 proves absence of the old literal, never presence of the new path) |
| 15 | the pre-clean **COMMANDS** deleted from both sites (`S-PRECLEAN`) | `[M2.8 preclean-command-absence]` — absence from the files, not from an `allowed-tools` scan (round 35, gemini) (round 23, codex — `M2.9` was mapped here but proves something else; see row 15f) |
| 15f | a **missing reserved leaf is a hard error, not a creation** — no creating retry (`S-CAPTURE`) | `[M2.9 preclean-reinstate-must-fail]` — every target open observed **in-process** (round 37) (round 23, codex — this is what `M2.9` actually discriminates, and it is the only cell that catches an implementation which catches `ENOENT` and recreates on a second open; row 15b covers only the first open's flags) |
| 1c | the protected-root set is read from **one place** (§4.1, `S-ALLOC`) | `[M2.21 protected-roots-single-source]` (round 22, codex — behaviour proofs pass two identical lists) |
| 15g | allocated mode keeps the **fd-based** `fstat`/`S_ISREG` defence (`S-CAPTURE`) | `[M2.23 allocated-nonregular-target]` — reader-held FIFO **plus in-process `os.fstat` observation on the opened fd**, so a pre-open `lstat` fails the cell (round 37) |
| 15h | allocated mode keeps the **fd-based** `0600` `fchmod` (`S-CAPTURE`) | `[M2.24 allocated-mode-tightening]` — mode assertion **plus in-process `os.fchmod` observation**, so a path-based `chmod` fails the cell (round 37) |
| 15e | `--allocated` is named **and FORWARDED** on **both** paths, the gemini helper using the **plugin's** `$0`-relative writer (`S-CAPTURE`) | `[M2.20 allocated-flag-name]` — relocated-copy shim for the wrapper path; **source assertion + runtime consequence** for the nested gemini worktree (round 39, both arms — the row still said "on `PATH`", the mechanism round 38 proved cannot work) |
| 15b | capture in allocated mode: **no `O_CREAT`, no `O_TRUNC`**; `O_NOFOLLOW` + `O_NONBLOCK` (`S-CAPTURE`) | `[M2.11 capture-requires-existing-leaf]` (round 14 — now a flag-interposition mutation on **both** flags, not a claimed consequence) |
| 16 | **no validator of `${CLAUDE_PLUGIN_ROOT}` inside `allowed-tools` exists** (`S-PRECLEAN`, §4.2) | `[M2.10 validator-absence]` (round 19, both arms — the row and `S-PRECLEAN` still said "no substitution validator" unscoped, which the repo's own `COREDEV2504_PluginRootConvention` contradicts) |
| 16b | the `${CLAUDE_PLUGIN_ROOT}` grants are retained unrewritten (§4.2) | `[M2.7 plugin-root-grants-retained]` |
| 17 | freshness fails closed on absent / mismatched / empty / malformed (`S-FRESH`) | `[M4.3 absent]` `[M4.4 mismatched]` `[M4.5 empty]` `[M4.6 malformed]` |
| 18 | …on **both** digest paths (`S-FRESH`) | `[M4.7 both-digest-paths]` |
| 21b | the `.launch` record **exists BEFORE dispatch** (`S-FRESH`, §4.5) | `[M4.10 record-precedes-dispatch]` (round 42, codex — row 21 described only the comparison, so deleting the temporal rule left every check green) |
| 18b | the record is looked up **per transcript**, not once per run (`S-FRESH`) | `[M4.9 transcript-position]` (round 30, codex — every mutation had targeted the first reviewer's transcript) |
| 19 | 31 sites inventoried and classified (`S-INVENTORY`) | `[M3.1 inventory-drift]` |
| 20 | version **bump** off the pinned pre-change `2.6.6` + CHANGELOG ceiling text (`S-RELEASE`) | `[M2.14 version-bump]` (round 26, codex — the round-25 in-tree predicate was satisfied by the **unchanged** tree) |
| 21 | mtime comparison: older ⇒ reject; **equal**-or-newer ⇒ accept, **on both digest paths and both transcript positions** (`S-FRESH`, §4.5) | `[M4.1 timing-negative]` + `[M4.2 timing-positive]` + `[M4.8 mtime-equality]`, all in the **28-cell** cross-product (round 34, codex — the row still said 14 after §4.5 grew the transcript-position axis) |
| 22 | `review-verdict.py`'s distinct-evidence check keeps working (§4.4) | `test_review_verdict.py:143-155` — **existing regression** (verified present), not a pre-fix proof |
| 23 | `.captureid` stays freshly generated per run, in **both** capture modes (§4.4) | `[M2.13 captureid-freshness]` (round 14 — the old cell cited `pty-capture.py:322-328`, the code that **generates** the ID; `test_pty_capture.py` has no such case, so this was production code cited as its own test) |
| 24 | the fixed directory/basename layout (§4.1, `S-ALLOC`) | `[M1.13 full-layout]` (round 14 — basename + "lands somewhere permitted" is passed by `<base>/transcripts/<repo-hash>/…`) |
| 25 | the dispatch works under a pinned `dontAsk` permission mode (§4.1) | `[M2.1 dontAsk-runtime]` |
| 26 | no `/tmp` literal survives in any `allowed-tools` line (`S-PRECLEAN`) | `[M2.3 no-tmp-literal]` |
| 31 | no caller passes `--base`; the allocator **rejects** it (§4.1, `S-ALLOC`, `S-WRAPPER` — rejection made operative round 17) | `[M2.15 no-base-argument]` |
| 20b | the CHANGELOG does **not** claim the `${CLAUDE_PLUGIN_ROOT}` grants were inert (`S-RELEASE`) | `[M2.17 no-inert-claim]` (round 17, codex — `M2.14` tested it but no row listed it, violating §6.1's bidirectional rule) |
| 15c | the two `rm -f` grants are **deleted, not rewritten** (`S-PRECLEAN`) | `[M2.16 grants-deleted-not-rewritten]` (round 17, codex — rewriting a grant to a non-`/tmp` path passed rows 15 and 26) |
| 8d | the exhaustion diagnostic **names the exhausted parent** (`S-ALLOC`) | `[M1.15 exhaustion-diagnostic]` (round 18, both arms — a generic "allocation failed" passed row 8c) |
| 3b | when neither base validates, the diagnostic **names the rejected value and the reason** (`S-ALLOC`, §4.1) | `[M2.18 base-failure-diagnostic]` (round 19 — the row and operative text had asked only for "a diagnostic" while the cell required value+reason) |
| 3c | on **falling back**, a diagnostic names the rejected value and the reason (`S-ALLOC`, §4.1) | `[M2.19 fallback-diagnostic]` (round 19, codex — `S-ALLOC` had specified a diagnostic only when **both** bases fail) |
| 14c | synthesis is invoked as `--reviewer <name>=<STATUS>:<allocated-path>` (`S-THREAD`) | `[M5.10 synthesis-cli-shape]` (round 18, gemini) |
| 12c | the wrapper's signature is **exactly three** positional args, each landing in its field (`S-WRAPPER`) | `[M5.11 wrapper-cli-signature]` — extra arg, omitted/empty **reviewer**, empty **ticket/round**, each allocating nothing, + **positional-mapping mutation** (round 38, codex) |
| 1b | the allocator's command line matches §4.1's shape **in the implementation** (`S-ALLOC`) | `[M5.12 allocator-cli-shape]` (round 18, codex — §6.0 compares plan sections, not code) |
| 32 | **every** review-skill invocation site passes ticket and round and is written as a **literal command** (`S-CALLERS`) | `[M5.13 callers-scan]` (round 20, codex — two successive enumerations were claimed exhaustive and both were wrong) |
| 32b | the invocation syntax is exactly `--ticket <T> --round <N>` (`S-CALLERS`) | `[M5.14 invocation-syntax]` (round 20, codex) |
| 32c | the **complete** command shape — namespace, both flags and the `<plan>` operand — at every non-exempt site (`S-CALLERS`) | `[M5.15b full-invocation-shape]` (round 48, codex — flags alone let a site omit the plan operand) |
| 28 | non-allocated call sites keep create-if-absent — a mode, not a global change (`S-CAPTURE`) | `[M2.12 nonallocated-mode-positive]` (round 14, gemini) |
| 29 | `<reviewer>` is a **hard-coded literal in each skill recipe**, never derived (`S-CALLERS`, §4.1 — retargeted round 24) | `[M5.9 reviewer-is-a-recipe-literal]` (round 17, both arms — §7 still carried the superseded "supplied by the wrapper" wording) |
| 30b | the wrapper invokes `pty-capture.py` from its **own location** too (`S-WRAPPER`) | `[M5.16 allocator-own-location]` (round 37, both arms — round 36 made only the library distinguishable) |
| 20c | the 39 synthetic `$HOME` fixtures are cleared (`S-RELEASE`) | `[M2.25 home-fixtures-cleared]` (round 37, codex — the cleanup was operative with nothing failing if skipped) |
| 30 | the wrapper resolves its lib dir from its **own location** — survives RELOCATION (`S-WRAPPER`) | `[M5.8 production-fallback]` — run from `cd /` **and from a relocated copy**, which a hardcoded absolute path fails (round 31, codex) (round 15, both arms — `M5.3` **sets** `UNLEASHED_LIB_DIR` and so bypasses the fallback entirely; it could not fail on the broken form) |
| 27 | ticket/round are required inputs of **both** review skills; missing ⇒ fail closed (§4.1, `S-WRAPPER`) | `[M5.7 missing-input-fails-closed]` — parameterized over both recipes (round 30, codex) (round 14, gemini — declared an accepted hole in round 13; it is a two-line test, and a hole that need not exist is still a gap) |

## 7. Implementation order

*(**Steps carry stable labels.** Round 9, both arms: inserting the wrapper step shifted every later
number and left **seven** cross-references pointing at the wrong step — the third time this plan has
broken that way. Numbers are reading order; **labels are the referent**, and an inserted step cannot
invalidate one. Cite `S-PRECLEAN`, never "step 5".)*

1. **`S-INVENTORY`** — **Inventory and classify all 31 sites** and commit the classification; M3 asserts it.
2. **`S-ALLOC`** — **Add `pty-capture.py --allocate`**: validate the base (§4.1); **reject any `ticket`/`round`/
   `reviewer` component that is not `[A-Za-z0-9._-]+` **matched against the FULL string (anchored at both
   ends)**, **and reject the exact values `.` and `..`** *(round 41, gemini: §7 named the character class but
   not the anchoring, so an unanchored match accepts `A/../../escape` — the escape `M1.8` exists to reject)*
   (the grammar alone accepts both) — the separator `/` is the vector that would escape the intended
   parent, and it is what the character class excludes; `.`/`..` are rejected as meaningless components,
   not as traversal (§4.1, round 10); create the `0700` parent and **fail closed if it already exists with a different
   mode or owner** (`makedirs(exist_ok=True)` silently accepts a `0755` directory); allocate
   the leaf with `O_CREAT|O_EXCL` and mode `0o600`, **each attempt drawing a FRESH run ID from a source
   with at least 128 bits of entropy — never a constant, a counter, or a coarse clock** *(round 52, codex:
   the generator is what makes allocation per-RUN and §7 never specified it)*, in a retry loop
   **bounded at 8 attempts**, after which it
   exits non-zero with a diagnostic naming the exhausted parent *(round 15, codex: `S-ALLOC` still said
   only "bounded" while §4.1 and row 8c specify 8 — a §7-only implementer had to invent the bound)*
   *(round 9, codex: this step said only
   `O_CREAT|O_EXCL`, so an implementer using the conventional `0o666` creation mode yields `0644` and
   **fails M1's `0600` assertion** — §7 was not sufficient on its own)*; **create the `<path>.launch` record
   **`.launch` record `O_CREAT|O_EXCL` on that same call, never truncating an existing one**
   *(round 17, gemini: "never truncating" was in row 9 and `M1.6` but absent from the operative step, so the
   table certified a §7 requirement that did not exist)* *(round 15, codex: `S-ALLOC` said only `O_EXCL` while M1.14 and
   row 9 require both, so a check-then-create implementation could follow §7 and fail its mandated proof)*,
   containing exactly the run ID as a single line of lowercase hex with no
   trailing content** *(round 11, codex: `S-ALLOC` said only "containing the run ID" and `S-FRESH` required
   rejecting "malformed" without defining it — the grammar existed only in §4.5, so an implementer working
   from §7 alone had to invent the payload format that the consumer then validates against)*; then print
   **The path layout is fixed and stated here, not only in §4.1** *(round 13, both arms: `S-ALLOC` never
   reproduced it, so an implementer working from §7 alone had to invent the directory structure)*:
   `<base>/unleashed-mail/review-transcripts/<repo-hash>/<ticket>r<round>-<reviewer>-<runid>.txt`, with
   `<base>` **selected by the allocator itself** — `$XDG_STATE_HOME` when it is
   **absolute, a DIRECTORY, outside every protected root, writable AND searchable (`W_OK|X_OK`)** — where a
   base that **does not exist is valid if its nearest existing ancestor satisfies those same predicates**, and the allocator then creates it `0700`
   *(round 26, codex: §4.1 declared absent-but-creatable bases valid and `S-ALLOC` still demanded plain
   writability, so a §7-only implementer would reject **every** absent base — including the default on a
   fresh host)* — else `$HOME/.local/state` judged by those
   same three rules. **The protected-root set, enumerated here so §7 stands alone:** `.claude` and
   everything beneath it **except `.claude/worktrees`** — including `.claude/plugins/data/…`.
   **The candidate is CANONICALLY RESOLVED (symlinks followed) and then containment is judged BY PATH
   COMPONENT, never by string prefix** — so `$HOME/.claude-cache` is accepted and
   `$HOME/.claude/worktrees-evil` rejected *(round 48, gemini: the round-35 edit **replaced** the
   component-containment clause with canonical resolution instead of adding to it, so §7 described only
   "outside the protected roots" and an implementer would reasonably write `str.startswith()` and fail
   `M2.2`'s mandatory sibling-prefix pair. Second instance of a **rewrite dropping a clause the prior
   wording carried** — and my round-41 check reported the clause "present" only because it did not strip
   notes, which is the very error this campaign keeps correcting in reviewers)*
   *(round 35, codex: `M2.2` mandates rejecting a canonical/symlink alias into `.claude`, while `S-ALLOC`
   described only component containment — a purely lexical implementation follows §7, passes the
   sibling-prefix and `worktrees` cases, and fails the mandatory alias case. Another proof stricter than its
   requirement)*. **That set is read from ONE place**, shared by the XDG and fallback validation paths
   *(round 22, codex: §4.1 required single-sourcing and §7 never mentioned it, so a §7-only implementer
   would write two lists — identical today, divergent later, which is the exact defect `scripts/lib/paths.sh`
   exists to prevent)*
   *(round 20, codex: `S-ALLOC` said "every protected root" while the enumeration lived only in §4.1 — the
   sixth time a contract has been stated in §4.x and left as a bare cross-reference in §7)*.
   **On falling back** (XDG rejected, fallback valid) it emits a diagnostic naming the
   rejected value and the reason; **if neither validates** it allocates nothing and exits non-zero with a
   diagnostic naming the rejected value and the reason *(round 19, codex: `S-ALLOC` specified a diagnostic
   only for the terminal case while §4.1 and `M2.2` require one on fallback, and asked only for "a
   diagnostic" where `M2.18` requires value and reason — the contract disagreed in both directions)*.
   **No caller passes --base, and the allocator REJECTS it if given** with a non-zero unknown-argument
   exit *(round 17, gemini: §4.1 and `S-WRAPPER` had stated only the caller half of this rule while `M2.15`
   tests **rejection** — an implementer would omit the argument at the call sites and leave the parser
   accepting it, failing the proof. This note deliberately **paraphrases** rather than quoting the token,
   per §6.0's exactly-once rule — round 18.)* *(round 16, both arms: `S-ALLOC` said only "validate the base (§4.1)", so a
   §7-only implementer had to look up the three rules elsewhere — the buildable-alone requirement is not
   satisfied by a cross-reference)*.
   Print the path **on stdout, alone on its line, prefixed by the literal marker `UNLEASHED_TRANSCRIPT=`** —
   the *stable marker*, defined here because §7 referred to it four rounds running without ever saying
   what it was *(round 12, codex)*. Callers match that prefix and take the remainder verbatim; **bare
   stdout with no marker is a failure**, not a fallback.
   **Command shape**, so the handoff is buildable from §7 alone:
   `pty-capture.py --allocate --repo-hash <H> --ticket <T> --round <R> --reviewer <name>` —
   **the identical shape §4.1 specifies** *(a §7 restatement that added or dropped an argument would be
   the very drift these two sections exist to keep aligned; `--base` was removed from BOTH in round 14)*.
   **ticket and round are required inputs of both review skills**, passed by the wrapper, **never
   inferred** — a skill that cannot determine them **fails closed** (§4.1). **`<reviewer>` is supplied by the caller, never derived by the allocator** — see `S-CALLERS`, which owns
   that contract *(round 23, gemini: this rule governs the **skill recipes**, not `pty-capture.py`, and the
   allocator cannot enforce it; a step scoped to one module should not carry another module's rule)*
   *(round 17, BOTH ARMS: §7 still said "supplied by the wrapper, not a skill input", the round-16 wording
   this replaced, so a §7-only implementation could **derive** the reviewer and pass it through the
   three-argument interface — satisfying §7 and failing M5.9. Fourth time a correction has reached §4.x and
   not §7, which is what §6.0 exists to catch; the reviewer contract is now one of its tokens.)*
   *(An earlier edit also left the fragment "Ticket, round and" dangling here — removed.)*
   *(Round 13, codex: §7 listed reviewer among the skill inputs and §4.1 listed only ticket and round —
   two different input contracts for the same two skills.)* Add M1.
   *(Round 8 reproduction, gemini: this step omitted the grammar and the mis-moded-parent rule, both
   mandated by §4.1 and both required by M1 — so an implementer working from §7 alone would build an
   allocator vulnerable to path escape and M1 would fail on it.)*
   *(Round 6, gemini: this step omitted the launch record entirely, so an implementer following §7 would
   build the allocator without it and `S-FRESH`'s freshness check would fail closed forever.)*
3. **`S-WRAPPER`** — **Create the shared Bash wrapper** — `scripts/review/allocate-transcript.sh`. It sources
   `context.sh` for `context_repo_hash`, calls the full `--allocate` shape above with that hash, and
   echoes the marker line verbatim. **Interface:** `allocate-transcript.sh <ticket> <round> <reviewer>`;
   **No caller passes --base, and the allocator REJECTS it if given** — base selection, validation,
   fallback and the diagnostic are owned by the allocator alone (§4.1). *(Round 14, BOTH ARMS, High: round 13 had the wrapper derive
   `--base` by the §4.1 rule while §4.1 and M2 required the **allocator** to do it. Two owners is not a
   division of labour: if Bash passes the fallback the allocator cannot know XDG was rejected, and if
   Bash passes an invalid XDG for Python to reject then the wrapper has not "derived the base" at all.
   One owner, and it is the side M2 already tests.)*
   **The wrapper takes EXACTLY three positional arguments.** A fourth argument and a
   **missing or empty `<reviewer>`** are each rejected — **not "a reordering", which is undetectable**
   *(round 36, codex: round 35 removed that rule from the cell and the row and left it standing here, so §7
   retained an impossible, uncovered requirement that its own §4.1 text explains cannot be implemented)*; **missing or empty `<ticket>` or `<round>` is a hard
   error** — and `M5.11` covers the **explicitly empty** cases, not only the omitted ones
   *(round 37, codex: `M5.11` covered an empty *reviewer* and `M5.7` an invocation *without* ticket/round,
   so a wrapper defaulting only empty `$1`/`$2` to valid values passed every named cell and allocated
   anyway)* too. In every case the wrapper allocates nothing and exits
   non-zero *(round 34, codex: `S-WRAPPER` presented the interface **shape** and rejected only missing
   ticket/round, while the stricter arity and nonempty-reviewer rules lived **only inside `M5.11`** — which
   §6.0 classifies as evidence, not contract. So a §7-conforming wrapper could accept a fourth argument or
   default `$3`, satisfy every production recipe that passes its literal reviewer, and then **fail a
   mandatory proof**. This is the inverse of the usual defect — the proof stricter than the requirement —
   and it is the same principle: **a rule that lives only in a cell is not a rule.**)* *(round 19, gemini: row 27 cited `S-WRAPPER` for this and `S-WRAPPER` did not state it, so a
   §7-only implementer would not build the check `M5.7` tests)*.
   **It invokes `pty-capture.py` by a path resolved from its OWN location too** — not a literal — and
   `M5.8`'s relocated copy makes that allocator distinguishable as well *(round 36, codex: the
   self-relative contract covered only `context.sh`, so a wrapper could source the relocated copy's
   sentinel library while invoking a **hard-coded allocator from the original checkout** — passing `M5.3`,
   `M5.8` and `M5.12`, then breaking on installation or once that checkout is removed. Two executables are
   resolved here and only one had the contract)*.
   **The lib directory it sources is `${UNLEASHED_LIB_DIR:-<script-dir>/../lib}`, resolved from the
   script's OWN location** — `LIB="${UNLEASHED_LIB_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/../lib" && pwd)}"`.
   *(Round 14, gemini, High: round 13 wrote the fallback as `${CLAUDE_PLUGIN_ROOT}/scripts/lib`, but
   **`CLAUDE_PLUGIN_ROOT` is unset in an ordinary Bash-tool shell** — §2, and `scripts/lib/agent-env-bridge.sh:19`
   exists for exactly that reason. The fallback expanded to the nonexistent absolute path
   `/scripts/lib/context.sh`, so the wrapper **failed unconditionally in production** while the
   `UNLEASHED_LIB_DIR` seam masked it in M5. A test seam that hides a production break is worse than no
   seam. The placeholder IS substituted in the skill's **invocation line**, which is why the wrapper can
   be reached at all — but nothing exports it into the shell the script then runs in.)* **This is the entry point the codex skill is granted** (§4.2's added
   `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)`), because the codex recipe runs Python and the
   hash helper is Bash-only. *(Round 8 reproduction, gemini: §4.1 required this wrapper and §7 never
   said to create it — an implementer could not build the handoff from §7 alone without inventing it.)*
4. **`S-CALLERS`** — **Thread ticket and round through EVERY invocation site, discovered by SCAN.**
   The syntax is **`/unleashed-mail:<gemini|codex>-review --ticket <T> --round <N> <plan>`**, and **every
   non-exempt invocation site must use that COMPLETE shape — namespace, both flags and the `<plan>`
   operand** *(round 49, gemini: this defined the syntax and then required only the two flags per site, so
   `M5.15b`'s plan-operand assertion was a rule living in a cell)*. **`<reviewer>` is a hard-coded literal in each skill's own recipe** —
   `gemini` in `skills/gemini-review`, `codex` in `skills/codex-review` — passed as the wrapper's third
   argument, **never derived** *(moved here from `S-ALLOC` in round 23, gemini: it is a caller contract)*. **The site set is discovered, not enumerated:** `M5.13` greps the repo for
   review-skill references and requires each either to carry both flags or to sit on an explicit committed
   exemption list (the skills' own definitions; prose that describes rather than invokes). A caller added
   later fails the cell; an exemption is a visible diff.
   **A review-skill invocation must be written as a LITERAL command — assembling the skill name or its
   flags dynamically (variable expansion, concatenation, `eval`) is itself a failure**, because a static
   scan can only bind a runtime property while the call sites are statically visible
   *(round 46, codex: round 45 put this rule in `M5.13` alone, so a §7-conforming implementation could scan
   literal references, permit a dynamically assembled invocation carrying both flags, and still fail a
   mandatory cell. **A rule that lives only in a proof cell is not a rule** — my own lens item, committed
   while fixing the finding that prompted it)*.
   *(Round 20, codex: round 19's "all four known callers" was **still not exhaustive** —
   `skills/implement/SKILL.md:161` and `:172` also instruct running both skills, and a scan finds
   references across **six** files. **Twice an enumeration was claimed complete and was wrong**, which is
   the whole argument for a discovery mechanism: a list is a snapshot, and this one has been wrong every
   time it was written.)*
   Known sites when written: `create-feature-plan/SKILL.md:81`, `AGENT_CONTRACTS.md:99-100`,
   `brainstorm/SKILL.md:178`, `modern-standards-planner.md:42-43`, `implement/SKILL.md:161`, `:172`.
   *(Round 18, codex, High: `M5.7` makes a skill that cannot determine ticket/round **fail closed**, so
   applying that contract without updating these two callers **breaks the canonical documented workflow** —
   and `M5.1`/`M5.6` never exercise them, so nothing would have caught it. A fail-closed rule is a
   compatibility change to every existing caller, not only a property of the new code.)*
   Add `M5.13` and `M5.14`. *(Plain IDs, as every other step writes "Add M1" — round 24, gemini: the
   bracketed `[id name]` form here was a THIRD occurrence of each tag, beyond its definition and its table
   row.)*
5. **`S-CAPTURE`** — **Make `pty-capture.py` HONOUR the reservation** (round 13, both arms). When the
   caller supplies an **allocated** path (`--allocated`, set by the review recipes), open the target
   — **and both production paths, `scripts/review/isolated-agy-review.sh` and the codex recipe, must
   FORWARD `--allocated` to their actual `pty-capture.py` invocation — where `isolated-agy-review.sh`
   invokes the PLUGIN's writer resolved `$0`-relative from its own location, NOT
   `$TREE/scripts/pty-capture.py`, which is the reviewed repository's copy and need not exist at all
   in a consumer install** *(round 42, codex)* *(round 35, gemini: `M2.20` asserts
   that forwarding while `S-CAPTURE` described only the callee's behaviour, so row 15e cited an operative
   rule that did not exist in the step)* —
   **without `O_CREAT` and without `O_TRUNC`**: the reserved leaf must already exist and its absence is a
   **hard error**, not a creation. **Retain `O_NOFOLLOW`, `O_NONBLOCK`, the `fstat`/`S_ISREG` regular-file
   check AND the `0600` fchmod** *(round 25, codex: this step had listed only `O_NOFOLLOW` and the fchmod,
   so an allocated-mode branch implementing exactly what was written would **drop the FIFO/device defence**
   that `scripts/pty-capture.py:66,76,81` relies on and `scripts/tests/test_pty_capture.py:48` covers for
   the existing mode — a new mode silently narrower than the one it sits beside)*. Non-allocated call sites
   keep today's create-if-absent behaviour, so this is a mode, not a global change. **`.captureid` stays
   freshly generated per run in BOTH modes** *(round 41, gemini: `M2.13` and row 23 require it and §7 never
   said so, though this step is the one that introduces the second mode)*.
   *(Without this, `_write_private`'s `O_CREAT|O_TRUNC` (`scripts/pty-capture.py:76`, `:321`) silently
   **recreates** a leaf that a retained pre-clean deleted — the `O_EXCL` reservation becomes decorative
   and §4.2's reinstate-and-must-fail mutation cannot fail. Twelve rounds specified the allocator and
   never said the capture must land in the file it reserved.)* Add M2's pre-clean runtime mutation.
6. **`S-THREAD`** — **Thread the allocated path** through `isolated-agy-review.sh`, both review skills,
   `brainstorm` and `review-synthesis`. Synthesis takes **the two allocated paths as explicit inputs**
   (`--reviewer <name>=<STATUS>:<allocated-path>`) — **not** a ticket/round contract from which it
   re-derives a name. *(Round 9, gemini: this step and §4.3's inventory note both demanded "a ticket/round
   input contract for synthesis", contradicting §4.1, which threads paths explicitly **precisely because**
   synthesis has no such contract. Deriving the path in a second place is the drift this design removes —
   a re-derived name that disagrees with the allocation reads an absent file and fails closed forever.)*
7. **`S-PRECLEAN`** — **Delete the two `rm -f` grants AND the pre-clean COMMANDS themselves** — `skills/codex-review/SKILL.md:48`
   and `scripts/review/isolated-agy-review.sh:89`. **And no `/tmp` literal remains in ANY `allowed-tools`
   line** *(round 43, gemini: `M2.3` asserts that absence repo-wide and `S-PRECLEAN` named only the two
   specific sites, so an implementer following §7 exactly could leave an unrelated `/tmp` literal standing,
   satisfy the step and fail the mandatory cell — row 26 was certifying a requirement §7 did not make)*. *(Round 5, codex: this step named only the grants, so
   as frozen the plan still permitted retaining a pre-clean that **destroys the allocated `O_EXCL`
   leaf** — the precise defect §4.2 exists to remove.)* **Delete the pre-clean in the Bash helper too** — `scripts/review/isolated-agy-review.sh:89`, not only
   `skills/codex-review/SKILL.md:48` *(round 35, gemini: §7 named one of the two sites §4.2 identifies)*.
   **Add codex's grant, exactly `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)`** *(round 35, codex:
   "add codex's bash grant (§4.2)" let an implementer add a narrower grant for `allocate-transcript.sh`,
   satisfy §7, authorize production, and then fail `M2.6` — the exact string is the contract)*. **No validator of `${CLAUDE_PLUGIN_ROOT}` inside `allowed-tools`** — round 1 proposed one, round 2 reversed the finding behind it, and it would reject the supported token. *(Scoped in round 19, both arms: the unqualified "no substitution validator" contradicted `scripts/tests/test_doc_gates.py`'s existing `COREDEV2504_PluginRootConvention`, which this ticket preserves.)* Add M2.
8. **`S-M5`** — **Add M5**, the integration proof: drive the codex recipe and `isolated-agy-review.sh` and assert the
   **emitted** allocation becomes the capture target, the synthesis input and the artifact's
   `transcriptPath`; mutate a caller to re-derive the name and it must fail.
9. **`S-FRESH`** — **Add the LAUNCH-RECORD freshness check** to `review-verdict.py`: the record is created `O_EXCL`
   **before dispatch**, bound to the run ID, looked up per transcript, and **fails closed when the record is absent, empty, malformed, or its run ID
   does not equal the one in the transcript's filename**. **`malformed` means: not exactly one line of
   lowercase hex with no trailing content** — the same grammar `S-ALLOC` writes (§4.5) *(round 11, codex:
   this step required rejecting "malformed" and never said what that was)* *(round 7, gemini: this step said only "when
   absent", dropping the ID equality that makes the record an anchor rather than a touch-file)*.
   **The operative comparison is `st_mtime_ns`: a transcript strictly OLDER than its `.launch` record is
   REJECTED; equal-or-newer is accepted** *(round 13, codex: `S-FRESH` never stated the comparison it
   exists to perform, so §7 could not be implemented without reading §4.5)*.
   Freshness is keyed to each transcript's own record, **independently of which digest path is used**.
   Add M4. *(Round 4: this step said only "add the mtime freshness check", so §7 did not require the
   record's creation, binding, lookup or fail-closed handling — the parts that make it an anchor.)*
10. **`S-RELEASE`** — **Clear `~/.local/state/unleashed-mail/review-transcripts/` of the 39 synthetic
   fixtures two runaway review runs left there** (`COREDEV-9999`, `testhash`, `abc`, `h1`; rounds 25 and 36)
   *(round 36: the isolation harness sandboxes the git worktree, **not `$HOME`**, so those runs escaped into
   precisely the directory this plan allocates into. Inert today because nothing reads the path until this
   ticket ships — which is exactly why it must be cleared before it does)*. Then version bump **off the pinned pre-change version `2.6.6`** *(round 41, gemini: §7 said "version bump"
   without the baseline `M2.14` pins, so an implementer had no way to know what it must differ from)* +
   CHANGELOG — state the **ceiling** (§3). **Do not claim the `${CLAUDE_PLUGIN_ROOT}`
   grants were inert**: that was a round-1 finding, reversed in round 2 and verified against the pinned
   2.1.220 in round 3.

## 8. Open questions — NONE REMAIN

*(Round 5, both arms: this section had become the plan's main source of contradictions — it reopened
four decisions that are settled operatively elsewhere. **A question that the plan has answered is not an
open question; it is a contradiction with a question mark.** Q1, Q2, Q3 and Q5 are struck and their
resolutions cited.)*

- ~~Q1 — is the XDG default writable?~~ **SETTLED, §4.1** — but the old wording answered a *different*
  question. `$HOME/.local/state` being absent from the protected-path list settles **"is it permitted?"**,
  not **"is it writable?"**; those are independent predicates *(round 25, codex)*. Both are now settled:
  a base is valid if it exists, **is a DIRECTORY and is writable AND searchable (`W_OK|X_OK`)**, **or is
  absent and its nearest existing ancestor satisfies those same predicates**, in which case the allocator
  creates it `0700` *(round 50, codex: this settled answer still said "writable" alone and so re-authorised
  the two implementations round 49 rejected — a stale settled answer, not a reopened question)*. A *set* `XDG_STATE_HOME` is validated by the
  same rules or falls back.
- ~~Q2 / Q5 — does deleting the outer pre-clean cover "the wrapper never starts"?~~ **SETTLED, §4.2:**
  yes — an allocated empty file maps to `MISSING` in synthesis and is rejected by
  `review-verdict.py:364` (codex, round 3, with citations). The pre-clean is **deleted**, including the
  commands (§7 `S-PRECLEAN`).
- ~~Q3 — is `/tmp/agy-ping.txt` in scope?~~ **SETTLED, §4.3:** out of scope, recorded as a decision.
- ~~Q4 — what anchors freshness on the `--reviewed-sha256` path?~~ **SETTLED, §4.5 and §7 `S-FRESH`**
  *(round 5 pointed at "step 5", which was M5; round 9's renumbering broke the corrected number too, which
  is why §7 now carries stable labels)*: the per-allocation
  launch record, `<transcript-path>.launch`, created by the allocator before it prints the path.

**Genuinely open:**

- ~~Q1 — is trusted-ownership validation of the XDG base sufficient and portable?~~ **SETTLED by the
  round-6 narrowing (§3):** the ancestry check is **withdrawn with the claim it defended**. A shared host
  where an attacker controls an ancestor is out of scope. *(Round 7, both arms: this question still
  asserted that "§4.1 now requires the canonical base to be owned by the user and not group/world
  writable" — which round 6 removed — so the allocator had two incompatible base-validation contracts.)*
- ~~Q2 — does anything read the two fixed literals at runtime?~~ **SETTLED, §4.3:** the inventory is
  exhaustive and classified per site, and M3 pins it *(round 7, codex)*.

**No open questions remain.** Every question this section has posed is answered in §3, §4.1, §4.2, §4.3
or §4.5, and each is struck above with its resolution cited rather than deleted — because a question
silently removed is indistinguishable from one nobody answered.
