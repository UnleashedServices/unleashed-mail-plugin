# COREDEV-2619 — Per-run transcript paths

**Status:** Planning — **round 7 gated (codex `REQUEST_CHANGES` 3 High + 2 Medium + 1 Low; the gemini
arm timed out at 36 bytes — the harness's `--print-timeout` is raised from 18m to 28m).** Blocks `COREDEV-2497`, whose §7 step 1 requires this to land
first.
**Ticket:** `COREDEV-2619` (Epic `COREDEV-2485`) · **High** — a live **gate bypass**, documented by the
2026-07-19 audit as MAJ-10 and reproduced twice on this campaign.
**Measured against:** HEAD `5187467` (v2.6.6), worktree `.claude/worktrees/opus5-review`.
**Last Updated:** 2026-07-31 (round 7, post-gate revision)

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
`pty-capture.py --allocate --base <dir> --repo-hash <H> --ticket <T> --round <R> --reviewer <name>` *(round 6, codex: `:104` declared `--allocate <dir>` while §4.1's interface paragraph omitted `<dir>` entirely, so the wrapper and the Python parser could implement different contracts)*. It creates the parent
`0700`, then allocates a fresh path with `O_CREAT|O_EXCL` in a retry loop, and **prints the allocated
path on stdout** so the caller propagates it rather than re-deriving it:

```
${XDG_STATE_HOME:-$HOME/.local/state}/unleashed-mail/review-transcripts/<repo-hash>/<ticket>r<round>-<reviewer>-<runid>.txt
```

- **Outside `.claude` entirely — round 2, and this is the SECOND directory this plan has got wrong.**
  Round 1 chose `~/.claude/review-transcripts/`; round 2's "fix" chose `${CLAUDE_PLUGIN_DATA}`, which
  **resolves to `~/.claude/plugins/data/{id}`** — *the same protected tree*. Verified on this machine:
  `/Users/nick/.claude/plugins/data/unleashed-mail-npranson-unleashed-mail-plugin`. Claude Code protects
  `.claude` except `.claude/worktrees`, so writes there prompt in default mode and are **denied** in
  `dontAsk`; "created on first reference" establishes provisioning, not write permission from a skill's
  Bash recipe. **`$HOME/.local/state` is confirmed absent from Claude Code's protected-path list** (round 3), so the
  **default** is correct. But **a set `XDG_STATE_HOME` is not guaranteed safe** — it can be relative,
  point inside `.claude`, or be unwritable. The allocator therefore **validates it: absolute, outside every
  protected root, and writable** — otherwise it falls back to `$HOME/.local/state`, **which is validated
  by the same rules**, and says so. **If the fallback also fails validation the allocator allocates
  NOTHING and exits non-zero with a diagnostic** — it never invents a third location. *(Round 9, codex:
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

**Proof — M5 (new, round 3): the INTEGRATION mutation M1 cannot give.** A correct allocator whose
callers ignore its stdout and derive a fixed basename **passes M1**. So M5 drives both real paths — the
codex recipe and `isolated-agy-review.sh` — and asserts the **emitted** allocation is the capture
target, the synthesis input, **and** the artifact's `transcriptPath`. Mutate a caller to re-derive the
name: M5 must fail.

**Plus, round 11 (codex): M5 did not carry `S-WRAPPER`'s single-helper requirement.** M5 asserted only
that *whatever* path was emitted propagates consistently — so a wrapper using a **constant** namespace,
or one **reimplementing** the repo hash instead of calling `context_repo_hash`, passed M1–M5 while
violating both the single-helper rule and the per-checkout namespace that makes concurrent worktrees
safe. M5 therefore adds a **two-checkout** mutation: allocate from two distinct checkouts of the same
repo and assert the `<repo-hash>` segments **differ**, and that each equals `context_repo_hash` evaluated
in that checkout. *(The two-checkout form is preferred over asserting one expected literal, because a
hard-coded expected hash passes against a reimplementation that happens to agree on the fixture and
fails to detect the drift this design exists to remove.)*

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

**Proof — M1, rewritten in round 2 because the first version proved nothing.** Two random basenames are
distinct anyway, and "neither truncated" observes nothing when both files start empty — the assertion
could not fail. Instead: **pre-create a sentinel at the exact candidate the allocator will try first**
(seeded by stubbing the run-ID source), containing known bytes. The allocator must retry on `EEXIST`,
return a *different* path, and **leave the sentinel's bytes untouched**. Assert the parent is `0700`. *(Round 6: an
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
`makedirs(mode=0o700, exist_ok=True)` **leaves an existing `0755` parent unchanged**, so M1 must include
a mutation with a **pre-existing mis-moded parent** and assert the allocator fails closed rather than
writing into it. Leaf creation is `0600`; retry is bounded.
**Plus, round 9 (codex): a pre-existing WRONG-OWNER parent is a second, separate mutation.** §7 `S-ALLOC`
requires failing closed on a parent that exists "with a different mode **or owner**", but M1 proved only
the mode arm — so a mode-only implementation passed every listed M1 case while violating §7. The two
checks fail independently and each needs its own mutation. *(Where the test cannot create a
foreign-owned directory unprivileged, stub the `stat` result rather than skipping: a skipped mutation
proves nothing, and this one is unrunnable as-written in most CI.)*

**Plus, round 11 (gemini, High): the rejection grammar itself had NO mutation.** Every M1 case above
concerns collision, parent mode/owner and leaf mode; an allocator that **omitted component validation
entirely** passed all of them. M1 therefore includes an **invalid-component** case per rejected class —
a component containing `/`, one containing NUL, an **empty** component, and the exact values `.` and
`..` — each asserting the allocator **fails closed and allocates nothing**. *(A rejection that still
allocates is the fail-open direction and would not be caught by asserting the return code alone.)*

**Plus, round 11 (BOTH arms, concordant): the `.launch` record's CREATION had no producer-side proof.**
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

**Proof — M2, rewritten twice.** A **runtime** check under a pinned **`dontAsk`** permission mode
(round 3: the round-2 form never named a mode, so a direct-shell check could pass while the shipped
workflow was denied): dispatch a real skill invocation and assert the capture lands. **And exercise the XDG
validation itself** *(round 4, codex: an implementation that blindly trusts a set `XDG_STATE_HOME`
passes M2 whenever the test leaves it unset)*: run with `XDG_STATE_HOME` **relative**, **inside
`.claude`** — including a canonical/symlink alias — and **unwritable**, and require the fallback **plus
its diagnostic** in each. Assert also that no `/tmp/` literal survives in any `allowed-tools` line.
**Plus, round 9 (codex): every case above is an INVALID value that falls back, so M2 as written was
passed by two wrong implementations** — one that ignores `XDG_STATE_HOME` entirely and always uses the
fallback, and one that validates `XDG_STATE_HOME` but then trusts the fallback blindly. Two more cases,
and they are of the two kinds this campaign keeps needing:
- **Positive (must PASS):** a **valid** `XDG_STATE_HOME` is **used** — allocation lands beneath it and
  **no** fallback diagnostic is emitted. This is the metamorphic case that kills "always fall back".
- **Negative (must FAIL closed):** the **fallback itself** is invalid — run with `HOME` pointing at an
  unwritable directory *and* `XDG_STATE_HOME` unset, and require the allocator to **refuse to allocate**
  with a diagnostic, not to invent a path. §4.1 says the fallback "is validated by the same rules" but
  never said what a failed validation *does*; it does this.
**No substitution validator** — round 1's would have rejected `${CLAUDE_PLUGIN_ROOT}`, which is
supported and correct.

**Plus, round 11 — two PRESENCE assertions, found while building §6.1's coverage table.** Writing that
table exposed two rows whose proof column I had filled in from memory and which **did not exist**:
- M2 asserted only that **no `/tmp/` literal survives** in any `allowed-tools` line. That is an absence
  check, and **absence of a `/tmp` literal is not presence of the wrapper grant**. M2 now also asserts
  `skills/codex-review/SKILL.md` **contains** the grant `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)`
  — without it `S-WRAPPER`'s entry point is ungranted and the codex arm silently cannot allocate.
- "No substitution validator" was a **stated decision with no cell that would fail if one were added**.
  M2 now asserts the `${CLAUDE_PLUGIN_ROOT}` grants are **still present and unrewritten** in both review
  skills — the positive form of the round-2 reversal, which four prior rounds kept re-breaking.

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

**Proof — M3 (was M5):** a drift check asserting no output literal survives outside the enumerated
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
  dispatch and bound to the returned run ID, is the anchor — compared by `st_mtime_ns` on **both** digest
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

**Proof — M4, both polarities.** *Negative:* a transcript whose mtime predates its launch record is
rejected. *Positive (round 4, codex):* a transcript captured **after** an already-existing record is
**accepted**, and the record is asserted to have existed **before dispatch** and not been replaced.
Without the positive case, M4 passes against the explicitly rejected implementation that creates its
"launch" record while writing the artifact — an older transcript still predates that late record. Run
both polarities through **both digest paths**, with **nanosecond-separated** mtimes.
**Plus the ABSENT-RECORD mutation (round 8 reproduction, codex):** delete the `.launch` entirely — the
gate must **fail**. Without it, every listed M4 case *requires a record to exist*, so an implementation
that validates only when `.launch` is present passes them all while violating §7's explicit
absent-record rejection. **codex wrote that §7 requirement itself in round 7 and then approved a proof
set that never tested it** — which is precisely why the reproduction run exists.
**Plus the MISMATCHED-RECORD mutation (round 7, gemini):** write a `.launch` whose payload is a
syntactically valid but *different* run ID from the one in the transcript's filename — the gate must
**fail**. Also cover **empty** and **malformed** payloads. *(§4.5's prose announced "M4 gains a
mismatched-record mutation" and the Proof defined only the timing cases, so an implementation that never
read the payload passed. The arms disagreed here — codex reported the mutation present; it was not.)*

**EVERY mutation above runs through BOTH digest paths — round 10, codex (High).** The "both digest
paths" requirement was attached only to the **timing** polarities; the absent, mismatched, empty and
malformed mutations inherited nothing. So an implementation that validated the launch record on the
snapshot-sidecar path and **skipped validation entirely on the `--reviewed-sha256` path** passed the
whole stated suite — while violating `S-FRESH`, which keys freshness to each transcript's own record
**independently of which digest path is used**. This is the same shape as round 9's `0600` and
wrong-owner findings: **§7 stated the requirement and the proof set did not carry it.** The matrix is
therefore *(timing-negative, timing-positive, absent, mismatched, empty, malformed)* × *(sidecar,
`--reviewed-sha256`)* — twelve cells, none optional.

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

### 6.1 — Requirement → proof coverage (added round 11)

**Why this table exists.** Rounds 9, 10 and 11 each found the *same class* of defect — an operative
requirement stated in §7 that **no proof carried** — nine instances in three rounds: the `0600` leaf, the
wrong-owner parent, M2's fallback cases, M4's validity mutations on the second digest path, the component
grammar, the `.launch` producer semantics, the payload grammar, and M5's repo-hash provenance. Each was
found by reading, one at a time, which is why three consecutive rounds each found more. **The table turns
that reading into an enumeration.**

**The obligation is bidirectional and it is part of the plan, not a courtesy:** every operative
requirement has a row naming the proof cell that would fail if an implementation omitted it, and **adding
a requirement without adding its row is itself the defect.** A row whose proof column reads *none* must
say why in the same line — an unproved requirement is allowed only when it is not machine-checkable, and
saying so out loud is what stops it from hiding.

| # | requirement (source) | proof cell that fails without it |
|---|---|---|
| 1 | base validated: absolute, outside protected roots, writable (`S-ALLOC`, §4.1) | M2 invalid-XDG cases |
| 2 | a **valid** `XDG_STATE_HOME` is **used** (§4.1) | M2 **positive** case |
| 3 | invalid fallback ⇒ allocate nothing, exit non-zero (§4.1) | M2 invalid-fallback case |
| 4 | component grammar `[A-Za-z0-9._-]+`, and not `.`/`..` (`S-ALLOC`, §4.1) | M1 **invalid-component** cases |
| 5 | parent created `0700` (`S-ALLOC`) | M1 parent-mode assertion |
| 6 | fail closed on pre-existing **mis-moded** parent (`S-ALLOC`) | M1 mis-moded-parent mutation |
| 7 | fail closed on pre-existing **wrong-owner** parent (`S-ALLOC`) | M1 wrong-owner mutation |
| 8 | leaf `O_CREAT\|O_EXCL`, mode `0o600`, bounded retry (`S-ALLOC`) | M1 sentinel-collision + mode assertion |
| 9 | `<path>.launch` created `O_EXCL`, same call, **never truncating** (`S-ALLOC`) | M1 **launch-only collision** mutation |
| 10 | payload = one line lowercase hex, no trailing content (`S-ALLOC`, §4.5) | M1 payload assertion; M4 malformed cells |
| 11 | path printed behind the stable marker (`S-ALLOC`) | M5 propagation assertions |
| 12 | wrapper obtains the namespace from `context_repo_hash` (`S-WRAPPER`) | M5 **two-checkout** mutation |
| 13 | wrapper is the granted codex entry point (`S-WRAPPER`, §4.2) | M2 **grant-presence** assertion (added round 11) |
| 14 | allocated path threaded to every consumer; synthesis takes **paths** (`S-THREAD`) | M5 re-derivation mutation |
| 15 | both `rm -f` grants **and** the pre-clean commands deleted (`S-PRECLEAN`) | M2 no-`/tmp`-literal assertion |
| 16 | no substitution validator (`S-PRECLEAN`, §4.2) | M2 **`${CLAUDE_PLUGIN_ROOT}`-grants-survive** assertion (added round 11) |
| 17 | freshness fails closed on absent / empty / malformed / mismatched (`S-FRESH`) | M4 cells 3–6 |
| 18 | …on **both** digest paths (`S-FRESH`) | M4 `× {sidecar, --reviewed-sha256}` |
| 19 | 31 sites inventoried and classified (`S-INVENTORY`) | M3 drift check |
| 20 | version bump + CHANGELOG states the ceiling (`S-RELEASE`) | **none — release hygiene, not machine-checkable.** Stated so it is not mistaken for an oversight |

## 7. Implementation order

*(**Steps carry stable labels.** Round 9, both arms: inserting the wrapper step shifted every later
number and left **seven** cross-references pointing at the wrong step — the third time this plan has
broken that way. Numbers are reading order; **labels are the referent**, and an inserted step cannot
invalidate one. Cite `S-PRECLEAN`, never "step 5".)*

1. **`S-INVENTORY`** — **Inventory and classify all 31 sites** and commit the classification; M3 asserts it.
2. **`S-ALLOC`** — **Add `pty-capture.py --allocate`**: validate the base (§4.1); **reject any `ticket`/`round`/
   `reviewer` component that is not `[A-Za-z0-9._-]+`, **and reject the exact values `.` and `..`**
   (the grammar alone accepts both) — the separator `/` is the vector that would escape the intended
   parent, and it is what the character class excludes; `.`/`..` are rejected as meaningless components,
   not as traversal (§4.1, round 10); create the `0700` parent and **fail closed if it already exists with a different
   mode or owner** (`makedirs(exist_ok=True)` silently accepts a `0755` directory); allocate the leaf
   with `O_CREAT|O_EXCL` **and mode `0o600`** in a bounded retry loop *(round 9, codex: this step said only
   `O_CREAT|O_EXCL`, so an implementer using the conventional `0o666` creation mode yields `0644` and
   **fails M1's `0600` assertion** — §7 was not sufficient on its own)*; **create the `<path>.launch` record
   `O_EXCL` in the SAME call, containing exactly the run ID as a single line of lowercase hex with no
   trailing content** *(round 11, codex: `S-ALLOC` said only "containing the run ID" and `S-FRESH` required
   rejecting "malformed" without defining it — the grammar existed only in §4.5, so an implementer working
   from §7 alone had to invent the payload format that the consumer then validates against)*; then print
   the path behind the stable marker. Add M1.
   *(Round 8 reproduction, gemini: this step omitted the grammar and the mis-moded-parent rule, both
   mandated by §4.1 and both required by M1 — so an implementer working from §7 alone would build an
   allocator vulnerable to path escape and M1 would fail on it.)*
   *(Round 6, gemini: this step omitted the launch record entirely, so an implementer following §7 would
   build the allocator without it and `S-FRESH`'s freshness check would fail closed forever.)*
3. **`S-WRAPPER`** — **Create the shared Bash wrapper** — `scripts/review/allocate-transcript.sh`. It sources
   `context.sh` for `context_repo_hash`, calls `pty-capture.py --allocate …` with that hash, and echoes
   the marker line. **This is the entry point the codex skill is granted** (§4.2's added
   `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)`), because the codex recipe runs Python and the
   hash helper is Bash-only. *(Round 8 reproduction, gemini: §4.1 required this wrapper and §7 never
   said to create it — an implementer could not build the handoff from §7 alone without inventing it.)*
4. **`S-THREAD`** — **Thread the allocated path** through `isolated-agy-review.sh`, both review skills,
   `brainstorm` and `review-synthesis`. Synthesis takes **the two allocated paths as explicit inputs**
   (`--reviewer <name>=<STATUS>:<allocated-path>`) — **not** a ticket/round contract from which it
   re-derives a name. *(Round 9, gemini: this step and §4.3's inventory note both demanded "a ticket/round
   input contract for synthesis", contradicting §4.1, which threads paths explicitly **precisely because**
   synthesis has no such contract. Deriving the path in a second place is the drift this design removes —
   a re-derived name that disagrees with the allocation reads an absent file and fails closed forever.)*
5. **`S-PRECLEAN`** — **Delete the two `rm -f` grants AND the pre-clean COMMANDS themselves** — `skills/codex-review/SKILL.md:48`
   and `scripts/review/isolated-agy-review.sh:89`. *(Round 5, codex: this step named only the grants, so
   as frozen the plan still permitted retaining a pre-clean that **destroys the allocated `O_EXCL`
   leaf** — the precise defect §4.2 exists to remove.)* **Add** codex's `bash` grant (§4.2). **No substitution validator** — round 1 proposed one, round 2 reversed the finding behind it, and it would reject the supported `${CLAUDE_PLUGIN_ROOT}`. Add M2.
6. **`S-M5`** — **Add M5**, the integration proof: drive the codex recipe and `isolated-agy-review.sh` and assert the
   **emitted** allocation becomes the capture target, the synthesis input and the artifact's
   `transcriptPath`; mutate a caller to re-derive the name and it must fail.
7. **`S-FRESH`** — **Add the LAUNCH-RECORD freshness check** to `review-verdict.py`: the record is created `O_EXCL`
   **before dispatch**, bound to the run ID, looked up per transcript, and **fails closed when the record is absent, empty, malformed, or its run ID
   does not equal the one in the transcript's filename**. **`malformed` means: not exactly one line of
   lowercase hex with no trailing content** — the same grammar `S-ALLOC` writes (§4.5) *(round 11, codex:
   this step required rejecting "malformed" and never said what that was)* *(round 7, gemini: this step said only "when
   absent", dropping the ID equality that makes the record an anchor rather than a touch-file)*.
   Freshness is keyed to each transcript's own record, **independently of which digest path is used**.
   Add M4. *(Round 4: this step said only "add the mtime freshness check", so §7 did not require the
   record's creation, binding, lookup or fail-closed handling — the parts that make it an anchor.)*
8. **`S-RELEASE`** — Version bump + CHANGELOG — state the **ceiling** (§3). **Do not claim the `${CLAUDE_PLUGIN_ROOT}`
   grants were inert**: that was a round-1 finding, reversed in round 2 and verified against the pinned
   2.1.220 in round 3.

## 8. Open questions — NONE REMAIN

*(Round 5, both arms: this section had become the plan's main source of contradictions — it reopened
four decisions that are settled operatively elsewhere. **A question that the plan has answered is not an
open question; it is a contradiction with a question mark.** Q1, Q2, Q3 and Q5 are struck and their
resolutions cited.)*

- ~~Q1 — is the XDG default writable?~~ **SETTLED, §4.1:** `$HOME/.local/state` is absent from the
  protected-path list (codex, round 3); a *set* `XDG_STATE_HOME` is validated or falls back.
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
