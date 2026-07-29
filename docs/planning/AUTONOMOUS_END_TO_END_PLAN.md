# Autonomous End-to-End Mode Plan

**Status:** Planning — awaiting dual plan-review gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29
**Ticket:** `COREDEV-2584` — Autonomous end-to-end mode: user-invoked skill, PermissionRequest hook,
arm/disarm state
**Epic:** `COREDEV-2582` — Opus 5 readiness and autonomous end-to-end mode
**Branch:** `feat/COREDEV-2584-autonomous-mode`
**Target version:** `2.6.0` → **`2.7.0`** (minor: adds a skill, `21/21/0/1` → `21/22/0/1`). Epic release
chain: 2.6.0 (`COREDEV-2583`) → **2.7.0 (this)** → 2.7.1 (`COREDEV-2585`).
**Depends on:** `OPUS5_ALIGNMENT_PLAN.md` (`COREDEV-2583`) — **must land first**. Its §4.6 introduces
the *only* frontmatter validation skills have ever had, so a new skill carrying security-relevant
frontmatter should not land before it.
**Landing order:** this plan lands **second**, before `DECISION_JOURNAL_PLAN.md` (`COREDEV-2585`) —
that plan's §4.6 records rationale against the brainstorm fork sidecar this ticket introduces (§4.6
below), so 2584 → 2585 is the required chain, not a free choice.

> **Round-1 gate correction (carried from `COREDEV-2583`).** An earlier draft justified the 2583
> dependency by claiming a camelCase `disallowedTools:` in a skill "silently no-ops". **That is false.**
> The pinned 2.1.220 skill schema declares `disallowedTools` as a first-class *"Canonical (normalized)
> alias of `disallowed-tools`"*. The inert camelCase key is **`allowedTools`**, which does not appear in
> the schema at all. Both spellings of the *disallow* key work; this plan uses the kebab form for
> consistency with the other skills, not for correctness.

---

## 1. Context

The maintainer wants to launch a session, state a goal, and have the plugin drive
brainstorm → plan → review gate → implement → review → PR without stopping to answer permission
prompts. This plan designs that mode.

The finding that shapes everything below is that **a Claude Code plugin cannot grant itself no-prompt
operation.** Three levers a reader would reach for are all unavailable:

- `permissionMode` in sub-agent frontmatter is **ignored for plugin sub-agents** (security), along with
  `mcpServers` and `hooks`.
- Skill `allowed-tools:` is a per-turn **pre-approval grant** scoped to the skill's own active window;
  it does not reach a sub-agent's own tool calls.
- The plugin ships **no `settings.json` and no `.claude/` directory** — verified: `find . -name
  'settings*.json' -not -path './.git/*'` returns nothing. The plugin ships exactly
  `.claude-plugin/plugin.json`, `.mcp.json`, `hooks/hooks.json`, `agents/`, `skills/`, `scripts/`,
  `mcp/`.

That leaves exactly one plugin-native lever: a **`PermissionRequest` hook**. It is a real event —
`scripts/validate-hooks.py:49` lists it in `KNOWN_EVENTS` — and it is currently unused.

Two things make this ticket harder than "add a hook":

1. **Auto-approval is a decision this repo already made, and made the other way.**
   `scripts/lib/hook-io.sh:16-17` bans emitting `permissionDecision:"allow"` outright, and
   `docs/planning/OCTO_ADOPTION_PLAN.md:194,477` records it as codex-review Critical #1. This plan
   partially reverses a review-gated decision and must say so in those words rather than presenting
   auto-approval as neutral new work.
2. **Removing prompts is not the same as removing the human, and most of the human-dependencies are not
   permission prompts at all.** They are prose "wait for approval" instructions inside skills and agent
   bodies (§4.7), a Stop gate whose remedy the model cannot execute (§4.8), and a guard whose denial is
   reported to nobody when nobody is watching (§4.9).

**Maintainer decisions locked before this plan was written** (do not re-litigate in review):

| Decision | Value |
|---|---|
| Invocation | **Explicitly user-invoked** via slash command. Never model-triggered, never scheduled/cron. |
| Intended effort | Ultracode. Nothing below `xhigh`, ever. |
| Safety gates | Stay. "No approval prompts" must not silently become "no safety gates". |
| Asset counts | This is the ticket that takes skills **21 → 22** (`21/22/0/1`). |

## 2. Scope

**In:** one new invoke-only skill; a `PermissionRequest` hook and its armed/disarmed session state; the
arm preflight; a non-interactive path for `brainstorm` Step 4b including persistence of the chosen fork;
an unattended contract for the Stop gate and the sensitive-file guard, including making denials visible;
the `Workflow`-vs-orchestrator boundary in `AGENT_CONTRACTS.md`; a turn bound; the nine asset-count
sites; the launch-side snippet; version bump + CHANGELOG.

**Out:** the Opus 5 alignment work (`COREDEV-2583`) and the decision journal (`COREDEV-2585`). No change
to the five-reviewer roster, the synthesizer, or the review verdict contract. **The three fail-closed
STOPs in `skills/implement/SKILL.md:158,164,216` are explicitly out of scope and must not be "fixed"** —
they terminate the turn rather than block on input, so they already degrade correctly, and
`skills/implement/SKILL.md:219` forbids self-selection in terms this plan has no authority to relax.

**Explicitly out of scope after verification:** `skills/pr-review/SKILL.md`. It has **zero** human-wait
points — its four steps contain no `AskUserQuestion` and no approval instruction. It is the in-repo
exemplar of an unattended-safe workflow skill, not a thing to change.

## 3. Guiding principle

> **Remove the prompt, never the check.** Every gate that exists today still runs in autonomous mode and
> still reaches the same verdict. What changes is only *who answers the prompt* — and when nothing can
> answer, the run **stops and reports**, it does not proceed.

Corollary, and the reason several items below are larger than they look: **a guarantee the plugin cannot
deliver must be documented as such, not implied.** The effort preflight (§4.5) cannot distinguish
ultracode from plain `xhigh`; the arm state cannot be read by a hook if a skill wrote it to the wrong
directory (§4.4); `CLAUDE_CODE_EFFORT_LEVEL` outranks every frontmatter pin. Each is stated plainly
rather than papered over.

Second corollary, inverting the repo's default: the state layer is **fail-open by contract**
(`scripts/lib/marker.sh:7-11`). For an *armed* flag that polarity is a hazard — fail-open on a
disarm-read leaves autonomous mode armed when the file is unreadable. §4.4 names the polarity
explicitly and departs from the convention.

---

## 4. Findings, fixes, and proofs

### 4.1 — `PermissionRequest` is the only lever, and the repo defines no contract for it (High)

**Root cause.** `PermissionRequest` appears in exactly **three** places repo-wide, all inside one file:
`scripts/validate-hooks.py:49` (a `KNOWN_EVENTS` member), `:64` (a `TOOL_MATCHER_EVENTS` member), and
`:130` (a parenthetical in a comment). There is no hook script, no test case, no README row, no
CHANGELOG entry, no audit note, and no planning paragraph. `scripts/test-hooks.sh` contains zero
`PermissionRequest` assertions.

So the plugin's own tree establishes only two facts: the event name is valid, and its `matcher` is
validated against tool names like `PreToolUse`'s.

**Fix.** Source the I/O contract from the live hooks reference and cite it as **external**, never as
"per the repo". The two load-bearing external facts, both from `code.claude.com/docs/en/hooks.md`:

- In sessions that cannot show a prompt — background subagents, non-interactive mode — Claude Code
  **still runs `PermissionRequest` hooks, and denies the tool call if no hook returns a decision.**
  This is the documented mechanism by which an unanswerable `ask` becomes a deny, and it is precisely
  the seam this ticket occupies.
- `permissionDecisionReason` visibility differs per decision: for `allow` and `ask` it is shown to the
  **user and not to Claude**; for `deny` it is shown to **Claude**. §4.9 depends on this.

Add the new event to `hooks/hooks.json` mirroring the shipped entry shape verbatim
(`hooks/hooks.json:3-13`) — `bash "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.sh"`, the path double-quoted
inside the JSON string, **no `:-.` fallback** (that form was a HIGH finding fixed in COREDEV-2504 and
is not substituted at all).

**Note for the reviewer.** Do **not** reach for `hook_emit_ask` in the new script.
`scripts/lib/hook-io.sh:169` hard-codes `"hookEventName":"PreToolUse"` in its `printf`; calling it from
a `PermissionRequest` hook emits a mislabelled envelope. Every emitter in the library has its event
baked in — there is no generic one. A new emitter is required.

**Proof.** A synthetic manifest containing only a `PermissionRequest` entry was run through
`python3 scripts/validate-hooks.py --root . --strict --require-manifest`: it printed
`✅ OK — hooks manifest (1 events, 1 invocations, 1 scripts, 1 parse-checked)` and exited 0. **No
`KNOWN_EVENTS` edit is required.** Revert the manifest entry and the new hook is simply absent — there
is no gate that would notice, which is itself §4.3's problem.

### 4.2 — Adding a hook has acceptance criteria that are easy to half-satisfy (Medium)

**Root cause.** `scripts/validate-hooks.py:227-323` imposes eleven conditions on a new entry. The ones
that actually bite:

- The referenced script **must exist and be non-empty** (`:316`, `:318`) and resolve **inside**
  `scripts/` (`:312`) — so manifest and script must ship in the **same commit**.
- The command must contain at least one `scripts/<file>` reference (`:294-296`); `"echo '{}'"` fails.
- If it is a shell script, `bash -n` must parse it (`:333-342`).
- A new `scripts/*.sh` is picked up automatically by CI's `shellcheck -s bash -S warning` glob
  (`.github/workflows/plugin-ci.yml:104`) — a real and frequently forgotten gate.

**Fix.** Ship script + manifest entry + shellcheck-clean source together, and add explicit cases to
`scripts/test-hooks.sh`.

**Note for the reviewer.** Three properties of the validator make "CI will catch it" false, and the
plan must not lean on any of them:

1. `scripts/test-hooks.sh` **does not read `hooks/hooks.json` at all** — its own header (`:9-15`) says
   so. A new hook can ship with zero coverage and CI stays green. Coverage is a deliverable, not a
   consequence.
2. An entry with **no `matcher` key at all** is fully valid and silently matches every tool. Only a key
   that difflib-matches `matcher` (e.g. `matchers`) is caught.
3. `--require-manifest` does **not** tighten per-entry validation — it only turns a *missing*
   `hooks/hooks.json` into a problem (`:194-209`). It is a deletion tripwire, nothing more.

**Proof.** New `scripts/test-hooks.sh` cases driving the hook with simulated stdin, following the
harness's existing `printf '{...}' | bash "$SCRIPT"` idiom. Each must fail when the fix is reverted.

### 4.3 — Auto-allow reverses a documented, review-gated decision (High)

**Root cause.** The ban is stated three times and enforced nowhere:
`scripts/lib/hook-io.sh:16-17` ("NEVER emit `permissionDecision:"allow"` … `allow` BYPASSES the
permission prompt (auto-approves)"), `scripts/sensitive-file-guard.sh:9-11` ("never emits … `allow` …
and never `deny` — the user is always in the loop"), and `docs/planning/OCTO_ADOPTION_PLAN.md:194,477`
recording it as codex-review Critical #1.

There is no allow-emitting helper in the library, by design.

**Fix.** Introduce the allow path **only** behind the armed state, and amend the three sites so the
codebase stops asserting an invariant it no longer holds. Specifically:

- `scripts/lib/hook-io.sh:16-17` becomes "never emit `allow` **except** from the armed autonomous-mode
  `PermissionRequest` hook, which is the one place the user has explicitly opted in", with a pointer to
  this ticket.
- `README.md:340` asserts "All are **fail-open** — a hook error never blocks your work". An
  allow-emitting hook inverts the failure direction: a bug **grants** access rather than losing a
  prompt. This sentence must be amended, not silently preserved.

**Note for the reviewer.** This is the item most likely to draw a `REQUEST_CHANGES`, and it should. The
honest framing is: the original decision was correct for a *model-triggered* auto-allow; this ticket
introduces a *user-triggered, session-scoped, explicitly-armed* one. If the reviewers judge the
distinction insufficient, the fallback is §8 Q1 — a mode that never allows, only converts unanswerable
asks into reported denies, which delivers visibility without ever bypassing a prompt.

**Proof.** A `scripts/test-hooks.sh` case asserting the hook emits **no decision** when the armed state
is absent, and only emits `allow` when it is present and valid. Delete the arm file, the case must fail.

### 4.4 — There is no session-keyed state helper, and the data dir splits between writer and reader (High)

**Root cause — two independent defects.**

*(a) No session-scoped path helper exists.* Every path helper in `scripts/lib/marker.sh` and
`scripts/lib/context.sh` keys on the **repo hash** (plus a kind, or an agent-id hash). The only
session-keyed file in the whole repo is the Stop-gate sentinel, and its name is composed **inline** at
`scripts/stop-quality-marker-gate.sh:66`, not by any library function. A plan that said "reuse
`context.sh`'s session-keyed path helper" would be describing something that does not exist.

The inline pattern to copy is `scripts/stop-quality-marker-gate.sh:57-69`: read `hook_str session_id`,
fall back to `hook_str transcript_path`, hash with `marker_hash_str` (`scripts/lib/marker.sh:79-95`),
compose `<marker_dir>/<prefix>-<repohash>-<sessionhash>`. Note its deliberate empty-key branch — with
neither field present it uses **no** sentinel rather than collapsing every anonymous session into one
shared file.

*(b) `CLAUDE_PLUGIN_DATA` is exported to hook processes and MCP/LSP subprocesses **only** — not to the
Bash tool* (`docs/audits/PLUGIN_AUDIT_2026-07-19.md:57`, MAJ-6). Under a marketplace install, a **skill**
that arms the mode via the Bash tool writes to `~/.claude/unleashed-mail`, while the **hook** that reads
it looks in `~/.claude/plugins/data/{id}/`. **The arm would be invisible.** This is the single largest
trap in the ticket.

The only shipped bridge is `export CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_ROOT}"`-style substitution added
to `agents/swift-reviewer.md:175,243` in 2.5.3 — and **no skill carries it**.
`scripts/pre-commit-checks.sh:14-18` documents its own marker writes as a no-op for exactly this reason.

**Fix.**

1. Add the `CLAUDE_PLUGIN_DATA` bridge line to the new skill's Bash fence. It is not inherited.
2. Compose the arm path inline from `marker_repo_hash` + `marker_hash_str(session_id)`, with a **prefix
   that is not `stop-last-blocked-`** — `scripts/lib/marker.sh:134` glob-deletes
   `stop-last-blocked-<repohash>-*` on any unrelated lint `pass` write, across every session.
3. Write it with the **hardened** idiom, not the plain one. Four atomic-write idioms ship; only
   `scripts/stop-quality-marker-gate.sh:117-128` (symlink pre-removal → `mktemp` → `chmod 600` →
   `mv -f`) is safe for a security-relevant flag. `marker.sh:105-116` uses a predictable `.tmp.$$` and
   no `chmod`, leaving the file world-readable and same-user plantable. Mirror the read-side trust check
   at `:92-95` (regular file, not a symlink) too.
4. **Fail closed on the disarm read.** Departing from `scripts/lib/marker.sh:7-11`: if the arm file
   cannot be read or does not parse, treat the session as **disarmed**, not armed.
5. Give it a GC. `scripts/lib/context.sh:190-203` (`_context_round_sweep`) is the **only** housekeeping
   routine in the entire state layer and it touches only `review-round-*.json`. Markers, snapshots and
   sentinels are never swept — confirmed live by 19 accumulated marker files and 5 leftover sentinels.

**Note for the reviewer.** Session id is **stable across compaction** — proven on a live transcript with
seven compactions and one `sessionId` across 16,908 records. The hazard is the opposite of the intuitive
one: **a session-scoped armed state survives the compaction that erases the reasoning which justified
arming it.** §4.5's preflight is therefore not sufficient on its own; the arm needs an expiry as well as
a session key.

**Proof.** `scripts/test-hooks.sh` cases for: arm→read round-trip; unreadable file → disarmed; symlink
at the arm path → rejected; a `marker_write lint pass` does **not** delete the arm file. The last one
fails today if the prefix is chosen carelessly, which is the point.

### 4.5 — The effort preflight guards the only thing frontmatter cannot (Medium)

**Root cause.** `CLAUDE_CODE_EFFORT_LEVEL` outranks frontmatter. Every `effort: xhigh` pin
`COREDEV-2583` §4.1 adds to the 21 agents and 3 workflow skills is silently defeated by that one env
var, and nothing inside the plugin can detect it after the fact.

**Fix.** Refuse to arm unless `${CLAUDE_EFFORT}` reports `xhigh`. This is a **runtime** check at the one
moment the plugin has an opportunity to look — the arm step — and it is the only guard that exists.

**Note for the reviewer, stated because the plan must not imply a guarantee it cannot deliver.**
`${CLAUDE_EFFORT}` reports ultracode as `xhigh`. **A skill cannot distinguish ultracode from plain
`xhigh`.** Ultracode is a Claude Code *setting*, not an effort level; it cannot be set via
`effortLevel`, `CLAUDE_CODE_EFFORT_LEVEL`, or any frontmatter — only `/effort ultracode`,
`--effort ultracode`, or the SDK. So the preflight can enforce "not below `xhigh`" and **cannot**
enforce "ultracode is on". The launch snippet in §4.13 is the only thing that gets the user there, and
it is documentation, not enforcement.

**Proof.** A case asserting the arm refuses with a readable reason when `CLAUDE_EFFORT` is unset or
below `xhigh`, and succeeds at `xhigh`.

### 4.6 — `brainstorm` Step 4b blocks on `AskUserQuestion`, and the fork it decides is never persisted (High)

**Root cause.** `AskUserQuestion` appears in exactly **three** places across all shipped assets:
`skills/brainstorm/SKILL.md:5` (frontmatter), `:57`, and `:95`. **Lines 57 and 95 are one logical call
described twice** inside Step 4b (header `:50`, next header `## Step 5` at `:99`) — `:57` is the
instruction, `:95` is the same call's argument shape. No agent calls it; the two agent hits
(`agents/graph-api-debugger.md:21`, `agents/jira-manager.md:252`) document its **absence**.

The deeper problem is not the call. It is that **the chosen fork is persisted nowhere.**
`skills/brainstorm/SKILL.md:96-97` only tells the model to "Carry the chosen option, **and** the
rejected alternatives … into the Step 8 summary and the Step 9 plan document" — voluntary prose carried
across five intervening steps before the Step 9 `Write` at `:155`. `skills/brainstorm/` contains exactly
one file. There is no sidecar, no state dir, nothing downstream can inspect to detect that the fork was
never decided.

**Fix.** Three parts:

1. `disallowed-tools: AskUserQuestion` on the new autonomous skill, so the call is removed for the
   skill's active window rather than merely unanswered.
2. A documented non-interactive fallback: **auto-select the `(Recommended)` option.** The convention
   already exists and is already load-bearing in three places — `skills/brainstorm/SKILL.md:59` (as
   vocabulary), `:73` (the recommendation line format), `:96` (the label suffix) — so the fallback keys
   off a marker the skill itself defines. Any rewording must update all three.
3. **Persist the chosen fork at decision time**, following house precedent rather than inventing one:
   `skills/create-feature-plan/SKILL.md:57-61` records that the review gate hit this exact
   "state must survive between skill steps" problem (COREDEV-2499) and solved it with a git-ignored
   sidecar written by a small `python3` script — `scripts/review-verdict.py:272-280` writes
   `<plan-dir>/.verdicts/<plan-basename>.reviewed-sha256`, and `.verdicts/` is git-ignored at
   `.gitignore:7`.

**Note for the reviewer.** Step 4b is **conditional** — `skills/brainstorm/SKILL.md:52-55` says "Skip
this step entirely for a linear design with one obvious approach; do **not** manufacture a fork." So
only fork-bearing features break, and a plan claiming "every brainstorm run hits `AskUserQuestion`" is
wrong. Separately, if the fork is to be persisted **into the plan document**, the plan template has no
slot for it — `skills/create-feature-plan/SKILL.md:19-51` has Overview/Approach/Milestones/Progress
Log/Files Changed/Testing/Notes and no Decision or Alternatives section. Adding the section is part of
the fix or the persistence location is undefined.

**Proof.** A unit case asserting the sidecar is written with the selected option and the rejected
alternatives, and that a later step reads it back. The `disallowed-tools` half is **unprovable by CI
until `COREDEV-2583` §4.6 lands** — skills have no key validation today
(`scripts/validate-plugin-assembly.py:82-84`: "Skills/commands are intentionally exempt"), so a
camelCase `disallowedTools:` would pass every gate and do nothing. That dependency is the reason this
ticket is ordered second.

### 4.7 — Removing `AskUserQuestion` does not make the workflow unattended (High)

**Root cause.** The `AskUserQuestion` call is one of several human dependencies, and not the widest one.
Verified sites:

| Site | Kind | Consequence unattended |
|---|---|---|
| `skills/brainstorm/SKILL.md:57,95` | `AskUserQuestion` | §4.6 |
| `skills/implement/SKILL.md:256` | bare prose "Present the plan and wait for approval" | **names no tool** — a plan scoped to `AskUserQuestion` misses it entirely |
| `agents/modern-standards-planner.md:263` | "Wait for approval before moving to implementation" | invoked **by** brainstorm Step 5 (`skills/brainstorm/SKILL.md:101`), inside a subagent with no user channel at all |
| `agents/code-simplifier.md:88`, `ui-engineer.md:25-27`, `release-manager.md:98,347`, `docs-engineer.md:37,107,263`, `jira-manager.md:51`, `xcode-build-fixer.md:60,76` | prose confirmation waits | same class |
| `skills/implement/SKILL.md:339` | "Offer to create a PR" | soft — an offer with no recipient |

So a brainstorm run has **two independent human-wait dependencies in sequence**: Step 4b's
`AskUserQuestion`, then the planner subagent's own wait. Fixing only the first leaves the run stalled at
the second.

**Fix.** Adopt the pattern the repo has already blessed for exactly this, rather than inventing one.
`agents/graph-api-debugger.md:20-22` states it: a subagent has no user channel, so instead of "waiting
for confirmation" it **returns a result beginning `BLOCKED — …`** with the diagnosis and the proposed
edit, and lets the invoking session surface it. `agents/jira-manager.md:252` states it identically for
MCP unavailability.

Convert the prose waits in the table above to the `BLOCKED — …` return shape. In autonomous mode a
`BLOCKED` return is reported and the run stops; it is never self-approved.

**Note for the reviewer.** `skills/implement/SKILL.md:158,164,216` are **not** in this table and must
not be touched — see §2.

**Proof.** Doc-level; assert via `scripts/tests/test_doc_gates.py` that no agent body contains a bare
"wait for" confirmation instruction without an accompanying `BLOCKED` clause. Revert any one conversion
and the assertion fails.

### 4.8 — The Stop gate's unattended risk is real but narrower than "hang" (Medium)

**Root cause — and a correction the plan owes the reviewers.** The framing "a blocking Stop gate with no
human to break the loop is a hang risk" overstates it. There are **five** independent terminators today:

1. `stop_hook_active` → exit 0 (`scripts/stop-quality-marker-gate.sh:37-38`).
2. The sentinel: the gate exits 0 if it already blocked at this `(repo, session, HEAD-commit)`
   (`:90-95`).
3. Claude Code itself **ends the turn after 8 consecutive stop-hook blocks** (live hooks reference).
4. The marker TTL — default 600 s (`:29`).
5. A HEAD change breaks the commit match (`:88`).

Further, the gate blocks **only after** durably writing the sentinel (`:111-129`): if the state dir is
unwritable it silently does not block. Verified with `chmod 500`: rc=0, empty stdout, one `would-block`
line in `logs/stop-gate.log`. And an **anonymous** Stop payload (no `session_id`, no `transcript_path`)
**never blocks** — `SENTINEL` is set to `""` at `:64-69` and the enforce branch requires it non-empty.

The genuine defect is different and worse: **the block reason instructs a remedy the model cannot
perform.** It says to run `swiftlint --quiet` / `xcodebuild build`, but `scripts/swift-lint-check.sh:421-425`
is explicitly forbidden from writing `lint=pass` ("one clean file can't prove the repo lints"), and the
**only** `pass` writers are `scripts/pre-commit-checks.sh:47,72`. In an unattended run the model is
handed an instruction it literally cannot satisfy; the only escapes are the 600 s TTL, a HEAD change, or
a passing `git commit` through `.githooks/pre-commit`.

**Fix.** Two parts:

1. Amend the block reason to name a remedy that actually clears the marker (a passing pre-commit run),
   so the instruction is executable in both attended and unattended runs.
2. Define unattended behaviour explicitly rather than inheriting it: in armed mode the gate keeps
   blocking (the check stays — §3) but its reason is additionally written to the run's visible report,
   because warn mode reaches nobody (see the note).

**Note for the reviewer.** Two things a plan would get wrong by reading `README.md:347`. First, "Blocks
the turn once" is imprecise — the dedup compares the sentinel's **content** to HEAD, so it is once per
`(session, commit)`; a session that commits N times with a fresh fail marker blocks N times. Verified by
rewriting the sentinel to a different sha: the same session blocked again. Second, `warn` mode is **not**
an unattended-visibility answer — it writes one line to `~/.claude/unleashed-mail/logs/stop-gate.log` and
emits nothing to stdout. Nothing reaches the model or the user.

**Proof.** Cases asserting the amended reason names a `pass`-writing command, and that armed mode still
blocks. The existing 302-case harness already covers the terminators; any behavioural change must update
contradicting assertions rather than leaving them inconsistent.

### 4.9 — The sensitive-file guard does not hard-deny, and its denial is reported to nobody (High)

**Root cause — the plan's starting premise was false and is corrected here.** The guard **never emits
`deny`**. On a sensitive-basename match it emits `permissionDecision:"ask"` (mode `ask`, the default) or
a `systemMessage` advisory (mode `warn`), and exits 0 — `scripts/sensitive-file-guard.sh:136-146`, with
the file header at `:9-11` stating it never emits `allow` **and never `deny`**. Verified live: an `Edit`
of `KeychainManager.swift` returns rc=0 with `permissionDecision:"ask"`.

The denial in a headless run is the **platform** refusing an unanswerable prompt, not the hook deciding.
So "keep it hard-denying" is not a preservation request — it is a request to **change `ask` → `deny`**,
and must be argued as a change.

The one true `exit 2` hard deny is unrelated to sensitive paths: a Bash **lexer parse failure**
(`:119-126`). It is path-agnostic — forced on the benign command `ls` it returns rc=2 — and it fires
even in `warn` mode. Describing it as "denies writes to protected files" is wrong on both counts.

**And visibility is exactly inverted between the two paths:**

| Path | Reason goes to | Consequence unattended |
|---|---|---|
| `ask` → platform deny | `permissionDecisionReason` is shown to the **user, not Claude** | reported to **nobody**, explained to **nothing** |
| `exit 2` | stderr is fed to **Claude, not the user** | model sees it; the operator never does |
| `warn` → `systemMessage` | **user only** | same as the first |

There is also **no existing record of a guard denial anywhere.**
`scripts/permission-denied-log.sh:4-5` explicitly scopes itself to auto-mode classifier denials and
excludes the guard's `ask` prompts. So "denials are already logged, we just need to surface them" would
be false.

**Fix.** Keep the guard's policy exactly as-is — same patterns, same `ask` default, no weakening — and
add the **reporting** the mode needs, in the `PermissionRequest` hook rather than in the guard:

1. When armed and a permission request would be denied for want of an answer, **log it** (a new
   JSONL under the existing `logs/` tier) and **surface it** in the run's final report.
2. Do **not** auto-allow anything the sensitive-file guard flagged. The armed allow path (§4.3) must
   exclude the guard's match set, or "no approval prompts" does silently become "no safety gates".

**Note for the reviewer.** `scripts/lib/bash-write-scan.py:955-958` ships a live env-var seam,
`_BWS_FORCE_FAIL`, in **production** code, which forces the `exit 2` hard-deny path. If it leaks into an
unattended environment every Bash call is denied with a message only the model sees. Worth an explicit
guard or a rename as part of hardening the deny path.

**Proof.** Cases asserting: a guard-flagged path is never auto-allowed while armed; a denied request
produces a log line; the exclusions at `:29-49` still hold (`*.md`, `*tests.swift`, `*test.swift` remain
not-sensitive — verified live: `keychain.md` and `KeychainManagerTests.swift` produce no output).

### 4.10 — Ultracode's dynamic `Workflow` orchestration is a second, ungoverned orchestrator (High)

**Root cause.** The one-orchestrator invariant lives in **exactly one file**, and it is not the contract:

> **One orchestrator, one entry point.** … Either way there is exactly one orchestrator and one verdict.
> — `skills/agent-orchestration/SKILL.md:45-50`

`AGENT_CONTRACTS.md` — the repo's declared source of truth for boundary disputes — contains **none** of
that language. That is itself the most citable defect here: the invariant is delivered as advisory prose
inside an auto-triggering skill which, at `skills/agent-orchestration/SKILL.md:8`, simultaneously hands
the model the `Agent` dispatch tool. There is zero mechanical coupling between the grant and the rule.

`Workflow` is ungoverned in a provable sense: repo-wide greps for `ultracode`, `ultrathink`, and
`dynamic orchestrat` return **zero** hits; `Workflow` the tool appears **twice**, both in planning docs
(`OPUS5_ALIGNMENT_PLAN.md:203`; `COREDEV-2490_EXTRACT_STATUS_DETECTION_PLAN.md:469`) — and the 2490 one
already **prescribes** Workflow for adversarial verification sweeps. The practice exists and is
undocumented; this ticket governs it rather than introducing it.

Four concrete collisions, each verified:

1. **CI would not notice.** Appending `, Workflow` to an agent's `tools:` passes
   `validate-plugin-assembly.py --root . --strict` with exit 0 and no warning — the difflib guard
   (`:119`, cutoff 0.7) finds no near match and `:112` accepts unknown non-MCP entries.
2. **The roster gate structurally rejects dynamic composition.**
   `scripts/review/reviewer-roster.sh:51` hardcodes a five-name `_VALID` allowlist. Run live, an unknown
   name yields `ROSTER-INPUT-INVALID` and **exit 4**, which `agents/swift-reviewer.md:191` defines as
   "an INPUT error — treat as uncertainty, never as a pass".
3. **Captures go silently missing.** The `SubagentStart`/`SubagentStop` hooks match a hardcoded
   five-name regex (`hooks/hooks.json:121,133`) and `scripts/capture-reviewer-verdict.sh:39-42` exits 0
   on any other `agent_type`. A Workflow-dispatched agent outside those five produces no capture and no
   signal.
4. **The spawn bound becomes unenforceable.** The only bound in the plugin is prose at
   `agents/swift-reviewer.md:485-489` — "at most ONE spawn per reviewer per review" — tracked in the
   orchestrator's own working memory with explicitly no on-disk ledger. Two concurrent orchestrators are
   two independent ledgers, so the bound cannot hold by construction. Combined with
   `AGENT_CONTRACTS.md:242` ("a persisted capture may only RATCHET a review toward caution — it can
   NEVER certify completion"), each orchestrator sees the other's output as unattributed on-disk state
   and re-dispatches everything.

**Fix.** Write the boundary into `AGENT_CONTRACTS.md`. Two correct homes, both existing:

- **§9 Tool Capability Floor** (`AGENT_CONTRACTS.md:316`), adjacent to the dispatcher-identity
  blockquote at `:330-331` which already reasons about *which tool performs subagent dispatch*. A
  `Workflow` rule is the same shape of claim.
- **§5 Code Review Pipeline** (`:235`, ownership at `:237`, spawn assignment at `:242`) for *who owns
  the verdict*.

The rule: `Workflow` may fan out **research, verification and implementation** work; it may **never**
dispatch the five reviewers, compose a roster, or produce a review verdict. Those remain
`swift-reviewer`'s, per the narrow exception at `skills/agent-orchestration/SKILL.md:48-49` — an external
caller may substitute for the **spawn** step and hand JSON to `swift-reviewer` for synthesis, but never
for the **verdict** step.

**Note for the reviewer — two claims that are false and must not appear in this plan.** First,
"`swift-reviewer` is the only agent that can spawn subagents" is **wrong**: it is the only agent with
`Agent` in a `tools:` **allowlist** (`agents/swift-reviewer.md:13`), but `modern-standards-planner`
omits `tools:` entirely and denies only `mcp__github` (`:20`), so it **inherits** `Agent` —
and `AGENT_CONTRACTS.md:326` confirms this is deliberate. Second, there is **no** §-numbered subagent
budget to cite: `grep budget AGENT_CONTRACTS.md` returns zero hits. There is also no §13 — the contract
ends at §12 (`:379`) followed by an unnumbered `## Cross-references` (`:421`), so any new section must
be inserted before `:421`.

**Proof.** Add `Workflow` to `KNOWN_TOOLS` in `scripts/validate-plugin-assembly.py` so it is
legal-but-tracked, plus an assertion that no agent under `agents/` lists it. Add `Workflow` to any
agent's `tools:` and strict validation must fail — today it passes.

### 4.11 — `maxTurns` is unset on every agent (Medium)

**Root cause.** No agent declares a turn bound. Attended, the human is the bound. Unattended at `xhigh`
with ultracode's fan-out, there is none.

**Fix.** Declare an explicit bound for the autonomous path and document what happens at it — the run
stops and reports, consistent with §3, rather than silently truncating mid-implementation.

**Note for the reviewer.** This interacts with §4.4's expiry and with spawn depth: `COREDEV-2583` §4.9
documents that the reviewers sit at depth 2 and that the Claude Code default moved 5 → 1 → 3. **A
Workflow layer pushes them to depth 3 — exactly the ≥2.1.219 default**, where the `Agent` tool is
withheld. (`COREDEV-2583` §4.9 originally claimed the panel would then "emit a normal-looking verdict";
that was **overstated and is corrected there** — `scripts/review/reviewer-roster.sh` already classifies
an empty held-report set as five `UNATTRIBUTED` and exits 3, mutation-proved at
`scripts/tests/test_reviewer_roster.py:105`. The panel fails **closed**, not silently.) §4.10's rule is what
prevents that; the two findings must be read together.

### 4.12 — The count change touches nine sites; only three are gated (Medium)

**Root cause.** Adding one invoke-only skill moves `21/21/0/1` → `21/22/0/1`. Three sites satisfy CI:

- `README.md:5` — the bold counts line (**not** line 60; `scripts/validate-version-sync.sh:60` is the
  *grep that finds it*, and the repo's own audit uses the same wording, which is where the confusion
  originates)
- `.claude-plugin/plugin.json:4` and `.claude-plugin/marketplace.json:11` — the `N skills` token inside
  each `description`, asserted by `check_desc_counts` (`scripts/validate-version-sync.sh:106-115`;
  the greps are at `:109-112`, the two calls at `:114-115`)
- plus a `## [X.Y.Z]` CHANGELOG heading matching `plugin.json`'s version (`:117-123`)

**Six more go stale silently**, because nothing reads them: `README.md:301` (`## Workflow skills (3)` →
4), `README.md:303` ("These three orchestration workflows" → four), a new table row after `README.md:310`,
the `(18 auto-triggering + 3 invoke-only)` parenthetical inside **both** manifest descriptions,
`CLAUDE.md:17`, and `CLAUDE.md:55` (`21/21/0/1` → `21/22/0/1`).

**Fix.** Ship the full nine-site checklist, and state in the plan that only three are gated so reviewers
see the gap is known rather than overlooked.

**Note for the reviewer.** Because the new skill is **invoke-only**, `README.md:224` (`AUTO-TRIGGERING
SKILLS (18)`) and `README.md:278` (`## Skills (18)`) **stay at 18**. An auto-triggering skill would
change those instead and leave `:301`/`:303` alone. A single unconditional checklist is wrong for one of
the two cases.

**Proof, executed against a fixture.** Copying the tree and adding a 22nd `skills/*/SKILL.md`, editing
**only** the three gated sites turned strict green — `✅ version-sync OK — … counts 21/22/0/1 match
disk`, exit 0 — while `README.md:224/278/301` still said 18/18/3. That is the drift this checklist
exists to prevent. Two further fixture results worth stating: `VERSION_SYNC_ENFORCE=strict` changes
**only** the trailer line and the exit code (warn and strict print byte-identical `❌ count drift:`
lines), and `check_desc_counts` **fails open** on rewording — changing the description to
`Ships 21 specialized agents, skills: 22` makes the grep miss, `s` is empty, and `:110`/`:112` treat
empty as PASS. Never reword those two phrases.

### 4.13 — Launch-side settings the plugin cannot set for itself (Low)

**Root cause.** Ultracode and the session permission mode are set at launch, by the user. No frontmatter,
env var, hook or skill in the plugin can set either.

**Fix.** Ship a copy-pasteable snippet in `README.md` next to the new skill's row, stating plainly which
parts are the user's responsibility and that the plugin verifies only what §4.5 can verify.

### 4.14 — Version bump and CHANGELOG (Low)

Bump `.claude-plugin/plugin.json` `version`, the `README.md:1` H1 (`Plugin vX.Y.Z`), and the newest
`### vX.Y.Z` What's-New heading together — `scripts/validate-version-sync.sh:53-56` asserts all three —
plus a `## [X.Y.Z]` CHANGELOG heading. `## [Unreleased]` does **not** satisfy the gate.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The armed allow path is reached without the user having armed it | Low | Fails closed by construction (§4.4): absent/unreadable/unparseable arm state ⇒ disarmed. The hook emits no decision when not armed, and no decision means Claude Code denies. |
| A skill arms the mode but the hook cannot see it (`CLAUDE_PLUGIN_DATA` split) | **High** | §4.4 fix 1 — the bridge line. This is the most likely way the feature silently does nothing. A test must export **different** values for producer and consumer, because `scripts/test-hooks.sh:33` exports one for both and would prove nothing. |
| Reviewers reject reversing the auto-allow ban (§4.3) | Medium | Accepted as the likeliest `REQUEST_CHANGES`. Fallback is §8 Q1: report-only mode, no allow path at all. |
| Armed state survives a compaction that erased the justifying context | Medium | Proven behaviour, not speculation (§4.4). Mitigated by an arm expiry in addition to the session key; a plain session key is insufficient. |
| "No prompts" is read as "no gates" by a future maintainer | Medium | §3 is stated as the guiding principle, and §4.9 excludes guard-flagged paths from the allow set. |
| A Workflow layer pushes reviewers to spawn depth 3 and kills the panel silently | Medium | §4.10's boundary rule forbids Workflow-dispatched reviewers outright; coordinate with `COREDEV-2583` §4.9, which owns the detection. |
| `_BWS_FORCE_FAIL` leaks into an unattended environment | Low | Denies 100% of Bash calls with a model-only message (§4.9 note). Cheap to guard; flagged so it is not discovered at runtime. |
| Six ungated doc sites drift after the count change | **High** (over time) | Unavoidable with the current gate. §4.12 ships the full checklist and says plainly that only three are enforced. |
| Merged before `COREDEV-2583` | Medium | Stated in the header. 2583 §4.6 introduces the only frontmatter validation skills have ever had; a new skill with security-relevant frontmatter should not land unvalidated. (The earlier "camelCase `disallowedTools` no-ops" justification was false — see the header note.) |

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

Expected count after this ticket: **21 agents / 22 skills / 0 commands / 1 MCP server**, and
**11 hook events**.

**Mutation proof is required for every new assertion** (§4.1–§4.4, §4.6, §4.7, §4.9, §4.10, §4.12):
revert the fix, and the new test must fail. Where an existing test asserts the old behaviour it is
inverted or replaced — never left contradictory.

## 7. Implementation order

1. §4.4 — the arm/disarm state primitive, its hardened write, its fail-closed read, and its GC. Nothing
   else works without it.
2. §4.1 + §4.2 — the `PermissionRequest` script and manifest entry, shipped together, plus the new
   event emitter.
3. §4.3 — the armed allow path and the three amended ban sites.
4. §4.5 — the arm preflight.
5. §4.9 — denial logging and reporting; exclude guard-flagged paths from the allow set.
6. §4.6 + §4.7 — the new skill, the Step 4b fallback and fork sidecar, the `BLOCKED — …` conversions.
7. §4.8 — the Stop-gate reason fix and unattended contract.
8. §4.10 — `AGENT_CONTRACTS.md` §9/§5 boundary, plus the `KNOWN_TOOLS` assertion.
9. §4.11 — the turn bound.
10. §4.12 + §4.13 + §4.14 — the nine count sites, the launch snippet, version bump and CHANGELOG, last.

## 8. Open questions for the reviewers

1. **Report-only, or allow?** §4.3 reverses a codex-Critical decision. The narrower alternative is a
   mode that **never** emits `allow` and only converts unanswerable asks into *reported* denies —
   delivering the visibility this repo lacks (§4.9) without bypassing a single prompt. It does not
   deliver uninterrupted operation. Is the visibility half worth shipping on its own first, with the
   allow path as a follow-up ticket once the reporting has been exercised?
2. **Where should the armed state expire?** §4.4 shows a session key is not enough, because the session
   outlives the compaction that erased its justification. Options: a wall-clock expiry (600 s matches
   `scripts/sessionstart-restore.sh:49` and the Stop-gate TTL), a turn-count expiry tied to §4.11, or
   re-arming after every compaction. The third is the safest and the most annoying.
3. **Should `Workflow` be added to `KNOWN_TOOLS`, or to a deny set?** §4.10's proof adds it as
   legal-but-tracked plus an assertion that no agent declares it. The stricter alternative is a
   `STALE_TOOLS`-style hard reject, which would also block a future legitimate use. Which polarity does
   the contract want?

## 9. Notes

- Every file:line in this plan was verified against the worktree at `a230b49` before it was written, and
  the behavioural claims (the validator runs, the fixture count edits, the guard's live outputs, the
  Stop-gate sentinel experiments) were **executed**, not inferred.
- Three premises in the ticket brief were found **false** during verification and are corrected in
  place rather than carried forward: the sensitive-file guard does not hard-deny (§4.9); the README
  counts line is `README.md:5`, not `:60` (§4.12); `skills/brainstorm/SKILL.md:57` and `:95` are one
  `AskUserQuestion` call, not two (§4.6).
- `docs/planning/` is a historical record, not current state. `OCTO_ADOPTION_PLAN.md:393` targets
  `commands/brainstorm.md` and asserts `AskUserQuestion` is unused — both true when written, both false
  now. `README.md:98` likewise still calls `brainstorm` a command. There are zero commands on disk.
- `scripts/lib/marker.sh:48-51`'s `_MARKER_REPO_HASH_CACHE` is a no-op in every shipped call path (every
  caller uses `$(marker_repo_hash)`, a subshell). It forks `shasum` on every call. Not this ticket's
  problem, but do not describe the hash as computed once per invocation.
