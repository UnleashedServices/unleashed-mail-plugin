# Agent Workflow Contracts

This document defines the **contracts between agents** — the boundaries, handoffs, and shared
conventions that must stay aligned across every agent in this plugin. Individual agents reference
this file in their bodies; conflicts between agents and this document are bugs.

> **Why this exists:** without a shared contract, release-manager / docs-engineer / ci-engineer
> independently invent versioning, branching, and changelog conventions. Without fleet-wide rule
> adoption, code from logic-engineer hands off to ui-engineer using patterns that ui-engineer
> doesn't know about — fragmenting architectural rules at every boundary.

## 1. Release & Versioning Contract

**Owner:** `release-manager` · **Consumers:** `ci-engineer`, `docs-engineer`, `jira-manager`, `swift-reviewer`

### Version format: `MAJOR.MINORRELEASE.YYMMBB`

Authoritative source: `<consumer-root>/docs/VERSIONING.md` and `Config/Base.xcconfig`.

- `MAJOR` = breaking redesigns (e.g., `1`)
- `MINOR` = new features, backwards compatible (e.g., `0`)
- `RELEASE` ∈ {`0`=Pre-alpha, `1`=Alpha, `2`=Beta, `3`=RC, `4`=Release} — concatenated to MINOR (e.g., `02` = Minor 0, Beta)
- `YYMMBB` = year + month (UTC) + build counter within the month (e.g., `260501`)

Two xcconfig fields:
- `MARKETING_VERSION` = `MAJOR.MINORRELEASE` (manual, e.g., `1.02`)
- `CURRENT_PROJECT_VERSION` = full `MARKETING_VERSION.YYMMBB` (e.g., `1.02.260501`)

Current state: `1.02.260601` (Beta) — `Config/Base.xcconfig` is authoritative (the BB byte auto-bumps, so don't trust this literal once it ages).

> **BB byte is automated.** `<consumer-root>/scripts/bump-build-number.sh`
> runs from a **Run Script Build Phase on the app target** (install/Archive builds only, gated by
> `runOnlyForDeploymentPostprocessing = 1`) and increments BB — **not** a Scheme Pre-Action. Pre-Actions
> run before "Process Info.plist," so a Pre-Action bump lands one archive too late (confirmed empirically,
> Xcode 16.1.1, 2026-04-29); see `<consumer-root>/docs/VERSIONING.md`. A successful
> bump drops the gitignored `.bump-build-number.pending` sentinel that blocks the next archive until the bump
> is committed; the Scheme Post-Action `<consumer-root>/scripts/post-archive-commit-bump.sh`
> commits and pushes it. `release-manager` MUST NOT manually edit BB — racing the script corrupts the sentinel.

### Branch convention

- **Feature branches**: `1.0X/feature-name` off the matching version branch (`1.0X.0000`)
  where `X` is the RELEASE stage digit (e.g., `1.02/coredev-1899-foo` for Beta features)
- **Hotfix branches**: off the version branch, merged to BOTH the version branch AND `main`
- **Trunk**: `main` is the integration trunk

> ❌ Never use `feature/desc`, `fix/desc`, or `claude/desc-sessionId` patterns. Those don't carry
> the version-stage signal needed for release routing.

### Commit format

Conventional commits with a **mandatory** COREDEV ticket key: `feat(COREDEV-1234): ...`, `fix(COREDEV-1234): ...`, `docs(COREDEV-1234): ...`, `test(COREDEV-1234): ...`, `refactor(COREDEV-1234): ...`, `chore(COREDEV-1234): ...`. The ticket key is required, not optional — it makes the PR searchable and drives Jira's GitHub dev-panel integration. Use the Epic key when a commit spans multiple child tickets.

### Changelog ownership

`docs-engineer` writes/maintains `CHANGELOG.md`. `release-manager` triggers updates at version-bump
time; `jira-manager` provides ticket summaries.

### Mandatory release gates

A PR cannot merge to `main` (or to the version branch) without:
1. Build green (xcodebuild)
2. SwiftLint green — changed files via `swiftlint --strict <changed files>`; whole repo via `swiftlint lint --strict --baseline swiftlint-baseline.json` (the committed baseline suppresses the pre-existing NSRegularExpression backlog so only NEW violations fail — COREDEV-2290)
3. Tests green (xcodebuild test)
4. `swift-reviewer` verdict: APPROVE
5. Provider parity audit: PASS, or a **declared** gap — a `ServiceCapabilities` flag set `false` + a
   `ProviderParityError.unsupportedForProvider` throw at the call site (per `skills/provider-parity`;
   COREDEV-2503 F9). A bare `// TODO: PARITY` comment or a throwing stub without that declaration is not a
   sanctioned gap.

## 2. Plan → Implement Contract

**Owner:** `modern-standards-planner` · **Consumers:** all implementation agents

### Plan creation

Every feature, refactor, or multi-step development requires `docs/planning/FEATURE_NAME_PLAN.md`.
Use `/unleashed-mail:create-feature-plan` to scaffold (a bare `/create-feature-plan` resolves only where the consumer workspace ships its own local copy — see Cross-references).

### Plan review gate (mandatory)

Before any implementation begins:

00. **Create the feature worktree FIRST**, and do everything below inside it — plan creation, snapshot,
    both reviews, synthesis and implementation. The Combined-verdict artifact is per-directory session
    state under `<plan-dir>/.verdicts/`; it is git-ignored at the repo root **and** self-ignored by a
    `*` `.gitignore` that `review-verdict.py::_ensure_secure_dir` writes inside the directory on
    purpose. It therefore does **not** follow a later `git worktree add`, and a fresh clone or worktree
    contains only the plan. Gating in one checkout and implementing in another fails the gate on a
    genuine approval — hit on COREDEV-2583 with byte-identical plan content and a five-round approval.
    CI and a second developer cannot verify an approval at all, by design; do not expect them to.
0. Plan author **snapshots the plan digest BEFORE dispatching the reviews**: `review-verdict.py snapshot
   --plan <PLAN>`. This binds the eventual approval to the reviewed bytes; an APPROVING `write` (3a) now
   fails closed without it. Re-run it on any plan revision.
0b. **Freeze the plan for the duration of a review round.** No edits between dispatching a review and
    recording its verdict. A reviewer that re-reads the target mid-run will refuse — *"a mandatory
    digest-bound review cannot approve a moving target"* — and the round is void. This applies to the
    author exactly as §2's read-only expectation applies to the reviewer.
1. /unleashed-mail:gemini-review --ticket <T> --round <N> <plan>
2. /unleashed-mail:codex-review --ticket <T> --round <N> <plan>
3. **Both must produce APPROVE / APPROVE_WITH_NOTES** before implementation starts
   - **(3a)** Once both transcripts are captured, run `/unleashed-mail:review-synthesis` to combine them into a single auditable **Combined verdict** block (`APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES | DISAGREEMENT`) — the record that this gate passed, with any divergence surfaced as `DISAGREEMENT` (never averaged) and a missing/empty transcript never counted as approval. This is the **plan-review** synthesizer (2 prose transcripts); keep it distinct from the code-review `synthesize_review` MCP tool (5 JSON findings arrays, `APPROVE_WITH_SUGGESTIONS` / `NEEDS_DISCUSSION`) used in §5.
4. Iterate (typically 2–6 rounds) until both converge

### Preflight & unavailable-reviewer recovery

The gate depends on the `agy` (gemini) and `codex` CLIs being installed and authenticated. On a fresh
machine or in CI they may be absent — the gate must NOT silently pass, and must NOT hard-wedge the dev
loop with no escape.

- **Preflight (run first):** route the `agy` smoke test through the PTY wrapper so a healthy install
  isn't misread as unavailable, and allocate the ping path PER RUN — a shared one lets a preflight that
  died before writing leave the previous `pong` for the next reader, so a dead CLI reads as healthy —
  `command -v agy && PING="$(mktemp "${TMPDIR:-/tmp}/agy-ping.XXXXXX")" && python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py"
  --timeout 60 "$PING" -- agy -p "ping"`, then check that same `"$PING"` for `pong` with `grep -qi` — NOT the literal `Pong!`, which agy returns
  only ~2 runs in 3 (it also answers a bare lowercase `pong`), so an exact check reports a healthy CLI as
  unavailable and sends you down the recovery path for no reason (bare
  `agy -p` writes 0 bytes from a non-TTY context like Claude's Bash tool / CI even when it succeeds). For
  codex, `command -v codex && codex --version` (note: this only proves the binary is on PATH, not that it
  is authenticated). If either is missing/unauthenticated, do NOT proceed as if the gate passed.
  A **healthy ping but a failed review is an invocation problem, not an unavailable CLI** — `agy -p`
  defaults to `--print-timeout 5m0s` and a long plan review needs `--print-timeout 28m`; a tiny transcript
  (e.g. `Error: timeout waiting for response`) is a *failure*, never a verdict. Fix the invocation and
  re-run; that is not a reviewer-unavailable situation.
- **Default is fail-closed:** with a reviewer unavailable, the Combined verdict is `DISAGREEMENT` /
  `REQUEST_CHANGES` — a missing/empty transcript is never `APPROVE` (see 3a); implementation does not start.
- **Recovery — the user chooses; there is no scripted waiver (COREDEV-2493).** If either reviewer is
  unavailable or unauthenticated, **stop**: a missing or empty transcript never counts as approval, and
  **no scripted waiver is recognized**. The **user** chooses the recovery — install/authenticate the CLI,
  obtain and capture the review on another machine, or explicitly direct work outside `/implement`. That
  last choice is a **workflow exception, not a passed Plan Review Gate**: record it as such in the plan's
  progress log and do **not** emit an approving Combined verdict. An agent may present these choices but
  must **never select or infer the exception**, and must never self-waive.

  > **Why there is no `WAIVED:` marker.** §2 previously promised a "user-authorized, scoped, recorded"
  > waiver. Nothing implemented it, so the gate hard-wedged — the very outcome the promise forbade. It was
  > removed rather than built because **"only the user may waive" is not enforceable here**: the agent is
  > the process that would run the script, so any flag or marker it could be asked to supply, it can also
  > supply unprompted (a TTY proves terminal attachment, not human presence — this repo's own
  > `pty-capture.py` creates one). A mechanical control documented as user-authorized but forgeable would
  > misdescribe the system. Note this does **not** make the rest of the gate cryptographically
  > trustworthy — it is a cooperative attestation too — but it declines to add a *sanctioned* bypass to
  > it. The audit record and the bypass are separable: record the exception in the plan
  > **without** claiming the gate passed. (This used to cite `docs/planning/OCTO_ADOPTION_PLAN.md` as the
  > exemplar. It is the opposite: that plan excluded gemini and then declared **"GATE SATISFIED"** on
  > codex alone — a reviewer exclusion *plus* a gate-passed claim, i.e. precisely what COREDEV-2493
  > forbids. An agent copying the cited precedent would do the wrong thing and believe the contract
  > endorsed it. No exemplar is cited now because none exists.) A genuinely
  > unforgeable waiver would need new trust infrastructure (an external signer holding a key outside the
  > agent's authority, releasing a plan-digest-bound token on user presence) — disproportionate for a
  > single-developer, non-CI workflow. Gated + decided at COREDEV-2493 (gemini `APPROVE`, codex
  > `APPROVE_WITH_NOTES`).

### Diagnostic agent scope (`xcode-build-fixer`, `graph-api-debugger`)

Diagnostic agents do have `Write` and `Edit` tools — they apply **mechanical, low-risk fixes**
(e.g., correcting a typo'd import, adjusting a Bash invocation, generating a missing log
helper). They do NOT auto-fix changes that cross the project's "Ask before" boundaries:

| Edit | Diagnostic auto-applies | Diagnostic must Ask first |
|------|-------------------------|---------------------------|
| Local Bash command tweak | ✅ | — |
| Adding/changing Swift Package dependency | — | ✅ (xcode-build-fixer) |
| Editing `.entitlements` file | — | ✅ (graph-api-debugger, xcode-build-fixer) |
| Editing `Info.plist` / xcconfig | — | ✅ (xcode-build-fixer) |
| Editing auth/token-handling code | — | ✅ (graph-api-debugger) |
| Editing menus, toolbar, keyboard shortcuts | — | ✅ (any) |
| Disabling sandbox or weakening security | ❌ NEVER | ❌ NEVER |
| Generating a debug logger or diagnostic script | ✅ | — |

When in doubt, propose and wait. The user is always in the loop for diagnostic work — if the
fix is non-trivial, surface it.

### Implementation handoff

Implementation agents read the plan, work milestone-by-milestone, and update the plan's progress
log as they go. `jira-manager` mirrors plan state to Jira ticket status.

## 3. Data → Logic → UI Handoff Contract

**Owners:** `db-engineer` → `logic-engineer` → `ui-engineer`

### Database layer (db-engineer)

- All tables include `account_email` column (snake_case in SQL, `accountEmail` in Swift Record types)
- Every query filters by `account_email`
- Migrations categorized CRITICAL (rare) or DEFERRABLE (default)

### Service / ViewModel layer (logic-engineer)

- Services obtain providers via `AccountScopedServiceProvider.activeService()`. **Never** reference
  `gmailService` or `microsoftGraphService` concretes in new service code.
- `serviceProvider.gmailServiceGuarded()` for Gmail-only ops; `validateSupported(.operation)` as
  guard at top of provider-specific methods
- ViewModels: `@Observable @MainActor final class`, dependencies injected via `init`
- Concurrency caps: respect `APIRequestCoordinator.shared.maxConcurrentRequests = 4` —
  TaskGroup fan-out must not exceed this
- Provider-specific error types **never** leak across the ViewModel boundary

### View layer (ui-engineer)

- Resolve services via `@State` + `.task` + `.onChange` — **never** a computed property that
  calls `serviceProvider.activeService()` (TOCTOU race during account switches)
- Use Curator design system: `CuratorTheme.*`, `Color.curator*`, `CuratorDivider`,
  `.curatorSheetBackground()`. Never hardcode fonts/colors/spacing/radii.
- `.foregroundStyle()` (not deprecated `.foregroundColor()`)
- File-split access control: when extracting `+Feature.swift`, `private` becomes `internal` for
  members read across the split

## 4. AI Pipeline Ownership

**Owner:** `ai-engineer` · **Consumer:** `logic-engineer`

### Provider abstraction

- **Today** — cloud providers inherit `BaseAIProvider` and conform to `AIProviderProtocol`
  (`complete(_:)` / `stream(_:)` / `completeStructured(_:)`); each owns its `URLSession` and a
  per-provider `buildRequestBody(...)`.
- **On-device providers (Apple Intelligence) conform to `AIProviderProtocol` directly** (no
  `BaseAIProvider`) — they don't have HTTP semantics. This is an explicit project-sanctioned exception.
- **PLANNED (COREDEV-1837, not yet built)** — a unified `HTTPBasedAIProvider` base will absorb the
  per-provider URLSession/SSE boilerplate. Do not write code that inherits it today (same status as
  `AISafetyPipeline` below).

### Tool dispatch

- `ToolRegistry` is the **only** authorized tool execution path
- New tools implement `ToolHandlerProtocol`, registered with `ToolRegistry`
- No legacy `switch` blocks in `ExecutionService`

### Prompts

- All prompts live in `PromptRegistry`, versioned for A/B testing
- No inline prompt strings in services or ViewModels

### Safety pipeline

- **`AISafetyPipeline` is PLANNED — not yet implemented** (see project rule
  `.claude/rules/ai-architecture.md`). Until it ships, safety checks are applied **inline** via
  `PIIRedactor` and `LLMInputSanitizer`. New safety checks co-locate with existing inline
  validators and are documented for future migration.
- When `AISafetyPipeline` ships, all validation MUST flow through it (COREDEV-833 audit finding SEC-4)

### Routing

- All AI operations route through `AIAgentPipeline`
- `AIService` is deprecated — do **not** add new methods to `AIService.swift`

## 5. Code Review Pipeline

**Owner:** `swift-reviewer` · **Sub-reviewers:** `security-reviewer`, `concurrency-reviewer`, `ux-perf-reviewer`, `accessibility-auditor`, `prompt-review`

### Order of operations

1. `code-simplifier` runs first (clean before review)
2. `swift-reviewer` orchestrates: spawns 5 sub-reviewers in parallel + `jira-manager`. Each sub-reviewer returns a structured **JSON findings array** (not prose) **plus an Output Contract status** — `COMPLETE | BLOCKED | PARTIAL` — read **before** the findings (a `BLOCKED` reviewer returning `[]` means "could not review," not "clean"). On the **pre-collected (SubagentStop capture) path**, that status is persisted as a self-describing sibling `<agent>.status` JSON beside the findings (`mcp/review-synthesizer/capture.py`, COREDEV-2328). **A persisted capture may only RATCHET a review toward caution — it can NEVER certify completion (COREDEV-2490 roster redesign).** So on that path: a *valid* `BLOCKED` sidecar is the only on-disk state honored (→ Needs Confirmation → **NEEDS DISCUSSION**); a `COMPLETE`, `PARTIAL`, absent, corrupt, or unrecognized sidecar is **UNATTRIBUTED** and forces an in-session **re-dispatch** of that reviewer — a captured `COMPLETE` never reads as a clean pass, and there is no on-disk artifact that certifies "reviewer ran clean." (The earlier "degrades to face value / never a false fail-closed" wording described the pre-2490 fail-OPEN and is wrong.) The normative procedure is `scripts/review/reviewer-roster.sh` (which "NEVER prints TRUST") and `swift-reviewer` Step 2
3. `swift-reviewer` runs provider parity audit itself
4. `swift-reviewer` calls the **`synthesize_review` MCP tool** (bundled `review-synthesizer` server) to dedup / scope-filter / ownership-merge the collected JSON findings in code — pure compute, no repo access
5. `swift-reviewer` owns the **verify gate**: it opens each `blockersToVerify` `file:line`, confirms the blocker against the code, and only then decides the final verdict (unconfirmed blockers → NEEDS DISCUSSION, not REQUEST CHANGES). A sub-reviewer that returned **BLOCKED** is the explicit form of a did-not-run uncertainty → a Needs-Confirmation item → **NEEDS DISCUSSION** (**not** a `verification` blocker, which is confirmed-by-construction and gates REQUEST CHANGES); a **PARTIAL** reviewer's findings are kept for its completed scope plus a non-gating `verification` warning naming the files it did not reach. If the tool is unavailable it applies the documented rules in `mcp/review-synthesizer/README.md` manually
6. `jira-manager` logs verdict to Jira

**Runtime dependency — subagent spawn depth (COREDEV-2583 §4.9).** The panel is a two-level dispatch:
`swift-reviewer` sits at depth 1 and the five reviewers at depth 2. Claude Code's default spawn depth
has moved three times — 5 (fixed) up to 2.1.216, **1** in 2.1.217–2.1.218, and 3 from 2.1.219 (tunable
via `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`). **At the limit Claude Code withholds the `Agent` tool**, so
the panel cannot spawn. This plugin therefore requires **Claude Code ≥ 2.1.219**, which the CI pin
(`.github/workflows/plugin-ci.yml`) tracks.

It fails **closed**, not silently: with no reviewer reports held, `scripts/review/reviewer-roster.sh`
classifies all five as `UNATTRIBUTED` and exits 3 (mutation-proved by
`scripts/tests/test_reviewer_roster.py::test_empty_stdin_classifies_everyone_and_fails_closed`). No
additional detection is warranted — and specifically **not** a "zero captures ⇒ NEEDS DISCUSSION" rule:
zero captures does **not** imply the panel did not run, because five readable in-session handoffs are
intentionally sufficient even when the capture hooks fail (`test_all_five_held_is_zero_cost`).

### Base branch detection

`swift-reviewer` must detect the correct base — feature PRs target the matching `1.0X.0000` version
branch, not `main`. Default to `git merge-base $(git rev-parse --abbrev-ref HEAD) origin/main` only
as fallback.

### Path safety

All `xargs grep`, `find`, etc. must handle paths with spaces (`Unleashed Mail/...`). Use
null-delimited (`-print0` / `-0`) or quoted paths.

### Required checks

`swift-reviewer` must verify:
- Build green (`xcodebuild build`)
- SwiftLint green — `swiftlint --strict <changed files>` on touched files plus whole-repo `swiftlint lint --strict --baseline swiftlint-baseline.json` (the committed baseline suppresses the existing backlog — COREDEV-2290)
- Tests green (`xcodebuild test`)
- All sub-reviewer JSON findings collected, run through the `synthesize_review` MCP tool (or the documented fallback rules), and every gating blocker confirmed via the verify gate before REQUEST CHANGES

### The payload-region invariant

> **The payload region is the span from the `Status:` line to the final fenced JSON block.**
> **Within it, nothing but detail fields and blank lines.**

Not prose, not a numbered step, not a next action, not a state restatement, and **not another machine
payload** — a stray `VERDICT:` line there breaks the parse exactly as prose does. Everything else an
agent emits goes **before** `Status:`.

This is not a style preference; it is `mcp/review-synthesizer/capture.py::extract_status`'s actual
behaviour, verified by execution. Violating it returns `None` → no `.status` sidecar → `UNATTRIBUTED` →
a re-dispatch, or `NEEDS DISCUSSION` when the reviewer's single retry is already spent. The regression
that owns this evidence is `mcp/review-synthesizer/tests/test_capture.py`.

Where a rule of §13 would conflict with a machine-readable contract — the completeness of a JSON
findings array, the `Status:` line that precedes it, the Output Contract detail trailer that follows it
(`Blocker Description`, `What Was Attempted`, `Completed`, `Remaining`, `Confidence`), the `VERDICT:`
line that must end a review transcript, the final fenced JSON block, or a `BLOCKED — …` result prefix —
**the contract wins and the rule yields.** Completeness and position of a machine-consumed payload are
never traded for brevity. In particular `Remaining:` is **safety information, never a list to shorten**.

## 6. CI / GitHub Actions Pinning

**Owners:** `ci-engineer`, `release-manager`, `security-reviewer`

### Single stance

Pin GitHub Actions to **commit SHAs**, not version tags. `security-reviewer` flags `@vN`-pinned
actions as 🟡 WARNING. `ci-engineer` and `release-manager` MUST use SHAs in workflow examples.

> A previous version of this plugin had `security-reviewer` flagging `@v*` while `ci-engineer`
> and `release-manager` used `@v*` in examples — and `security-reviewer`'s grep filter
> `grep -v "@v\|@main\|@sha"` actually excluded the violation. All three now align: SHAs only.

## 7. Mandatory Project Gates

The project's CLAUDE.md defines "Ask before" checkpoints. Agents that touch these areas must surface
the change for user approval, not auto-edit:

- Xcode project structure, entitlements, Info.plist
- App lifecycle, menus, toolbar, keyboard shortcuts
- Authentication flows or token handling
- Adding frameworks, libraries, or SwiftPM dependencies

Affected agents: `release-manager` (Info.plist, entitlements), `xcode-build-fixer` (dependencies),
`graph-api-debugger` (auth/token), `ui-engineer` (toolbar/keyboard).

## 8. Path-Scoped Rule System (`.claude/rules/`)

The project uses path-scoped rule files in `.claude/rules/*.md`. They auto-load based on file path
match. Agents that edit Swift files should be aware:

> Rule paths in `.claude/rules/*.md` use the project-rooted form `"Unleashed Mail/Sources/..."`.
> Globs match relative to the project root.

| Rule | Trigger paths (summary, relative to project root) |
|------|------------------------|
| `ai-architecture.md` | `Unleashed Mail/Sources/Services/AI/**`, `AIAgent*`, `ServiceContainer+Wiring*` |
| `api-endpoints.md` | `APIEndpoints*`, `*Service*`, `RateLimiter*`, `RetryPolicy*` |
| `code-style.md` | `**/*.swift` (always loaded) |
| `database.md` | `Unleashed Mail/Sources/Services/Database/**`, `*Migration*`, `*Repository*` |
| `provider-isolation.md` | `Gmail*`, `MicrosoftGraph*`, `AccountScoped*`, sync workers |
| `swift-regex-sendable.md` | `*Regex*`, `*Pattern*`, `PIIRedactor*` |
| `swiftui-views.md` | `Unleashed Mail/Sources/Views/**`, `Unleashed Mail/Sources/ViewModels/**`, `Unleashed Mail/Sources/Components/**` |
| `webview-editor.md` | `*WebView*`, `*EmailWeb*`, `HTML*` |

**Naming convention matters:** rule auto-load matches by filename, not content. When `code-simplifier`
extracts a `+Feature.swift` extension, it must preserve the parent type's naming convention so the
correct rules continue to load.

## 9. Tool Capability Floor

Each agent type has minimum tool requirements:

| Agent kind | Required tools |
|------------|---------------|
| Reviewers (read-only) | Read, Bash, Grep, Glob — **exception:** `prompt-review` is `Read, Grep, Glob` (Bash deliberately dropped; it inspects AI call sites, not shell state) |
| Implementation | Read, Write, Edit, Bash, Grep, Glob |
| Orchestrator (swift-reviewer) | + Agent (subagent dispatch) |
| Diagnostic | + WebFetch (look up vendor docs mid-debug) |
| Planner (modern-standards-planner) | Context7 MCP + WebFetch/WebSearch/Write/Edit/Agent + Bash — **inherited by omitting `tools:`** (an allowlist would block the install-specific MCP prefix); scoped with `disallowedTools: mcp__github`, which denies repo mutation from an agent that fetches UNTRUSTED web/Context7 content. Bash is deliberately retained (the preloaded `create-feature-plan` skill runs `review-verdict.py snapshot` as part of the gate) |
| Personas (read+search) | Read, Grep, Glob |
| Project (jira-manager) | Atlassian MCP **inherited by omitting `tools:`** (portable across install prefixes); `disallowedTools: Write, Edit, NotebookEdit, Bash, Agent, mcp__github` blocks every checkout-write vector — file editors, shell, subagent dispatch — and the github MCP write surface. `Bash` is denied (PR #63 recheck, P1): `swift-reviewer` spawns this agent while processing untrusted review content, and a sub-agent `Bash` cannot be scoped to one command — so the caller passes the PR URL instead of the agent running `gh pr view`. It mutates JIRA via the Atlassian MCP by design, and nothing else. (This row previously listed a `MultiEdit` deny the agent file never carried — Claude Code removed that tool, and the stale-name rule rejects denying it.) |

> The Claude Code subagent dispatcher tool is named `Agent`, **not** `Task`. `Task` is not a
> valid tool name in current Claude Code; older docs that say `Task` are stale.

### 9.1 Accepted residual — `swift-reviewer`'s shell is reachable from model-invoked `pr-review`

**This is a documented decision, not an oversight** (PR #63, raised four times; decided 2026-08-07).

`pr-review` is model-invocable and grants `Agent(swift-reviewer)`. `swift-reviewer` holds bare `Bash`,
so a prompt-injected finding in untrusted PR content could in principle steer it into an arbitrary
shell command with no user gesture.

**Why it is not simply removed.** A sub-agent's `tools:` list takes BARE NAMES — `Bash(...)` scoping is
silently ignored there — so a sub-agent either has arbitrary shell or none. `swift-reviewer` needs it
for `changeset.sh` (scope detection) and `build-verify.sh` (Step 4). Dropping `Bash` would not make
those steps safe; it would make them silently produce nothing, which is precisely the worse failure
mode the `check_bashless_agents_run_no_shell` validator exists to catch — it is what happened to
`security-reviewer`, `concurrency-reviewer` and `ux-perf-reviewer` when their `Bash` was removed while
their bodies still ran `cat`/`find`/`plutil`.

**What bounds it instead** (each verified, each with a regression test):
- the five spawned reviewers are `Read, Grep, Glob` — **no `Bash` on any of them**;
- `swift-reviewer`'s `disallowedTools` denies **every** checkout-writing agent by name, in both the
  bare and `unleashed-mail:`-namespaced spellings, and that set is **recomputed from disk** by
  `validate-plugin-assembly.py` rather than hand-maintained, so a newly added writer cannot be missed;
- `swift-reviewer` denies spawning itself, so there is no recursive amplification;
- `jira-manager` — the one agent it spawns that is not a reviewer — **denies `Bash`** outright;
- the skill boundary itself grants only `changeset.sh`, never bare `git`.

**The alternative, if this residual is ever judged unacceptable:** set
`disable-model-invocation: true` on `skills/pr-review/SKILL.md`. That closes the path completely and
costs only the model's ability to *enter* the workflow autonomously — a user typing `/pr-review` is
unaffected. It was not taken because autonomous review is the workflow's purpose.

## 10. MCP Tool Prefixes

MCP tool names are install-specific (the prefix depends on how the MCP server was installed).
An agent that sets a `tools:` allowlist would have to enumerate every possible prefix and would
still break on an unlisted one — so **agents that need MCP tools OMIT `tools:` entirely** (inheriting
all tools, including whatever MCP prefix is installed) and restrict with `disallowedTools:` instead.
The prefixes below are the ones a given server surfaces under, for reference (e.g. when reading a
tool name in a transcript), **not** a whitelist to hardcode:

- Atlassian (jira-manager):
  - `mcp__claude_ai_Atlassian__*` (VSCode-shipped MCP)
  - `mcp__atlassian__*` (standalone MCP server)
  - `mcp__plugin_atlassian_atlassian__*` (Anthropic-marketplace plugin)
- Context7 (modern-standards-planner):
  - `mcp__claude_ai_Context7__*` (VSCode-shipped)
  - `mcp__context7__*` (standalone)
  - `mcp__plugin_context7_context7__*` (Anthropic-marketplace plugin)

If none of the prefixes resolve, agents must degrade gracefully (log to stdout for the user, do
not block implementation).

## 11. Model Tiering Policy

Agent `model:` is set by role so future model generations are a one-line policy update, not a
fleet-wide edit:

Agent names below are listed in full (no `/` shorthand) so this table stays machine-checkable:
`validate-plugin-assembly.py` parses these rows and asserts every agent's frontmatter `model:`
(defaulting to `inherit` when the key is omitted) equals its tier here, and that every `agents/*.md`
appears in exactly one row — so this policy can no longer silently drift from the shipped frontmatter.

| Tier | `model:` | Agents |
|------|----------|--------|
| Deep-review specialists | `opus` | security-reviewer, prompt-review, concurrency-reviewer |
| Orchestrator + implementation/diagnostic engineers | `inherit` (follows the session model) | swift-reviewer, ai-engineer, ci-engineer, code-simplifier, db-engineer, graph-api-debugger, logic-engineer, modern-standards-planner, tester, ui-engineer, xcode-build-fixer |
| First-pass reviewers, planning personas, + fixed-scope managers | `sonnet` | accessibility-auditor, docs-engineer, enterprise-stakeholder, jira-manager, release-manager, smb-entrepreneur, ux-perf-reviewer |

Rationale (rewritten for COREDEV-2583; the previous version argued from **cost**, which is no longer a
constraint the maintainer accepts): the tier is now set by **consequence of being wrong**.

- **`opus` — deep-review specialists.** `security-reviewer` (credentials, OAuth, injection, CI),
  `prompt-review` (AI prompt/call-site safety, injection, PII-in-logs) and `concurrency-reviewer` — the
  declared **correctness owner**, which absorbs the logic and error-handling findings the other reviewers
  explicitly punt. A miss by any of these ships a defect the rest of the pipeline is not looking for.
- **`inherit` — orchestrator + implementation/diagnostic engineers.** They match whatever the user is
  running and scale up on demanding work.
- **`sonnet` — first-pass reviewers, planning personas, fixed-scope managers.** Breadth and
  bounded-scope bookkeeping (doc edits, the CFR label state machine, release/ticket hygiene), where a
  finding that is missed is caught by the deep-review tier or is low-consequence.

A maintainer who wants any agent to scale with the session flips its frontmatter and moves it between
rows **in the same edit** — the validator keeps the two in sync and fails otherwise.

**Effort policy: assets INHERIT the session effort. The "floor" constrains permitted PINS, not runtime
effort.** Omit `effort:` so a `max` session runs its subagents at `max`. Frontmatter effort overrides the
session in **both** directions, so a hard `effort: xhigh` pin silently *capped* a `max` session — which is
why the policy is omit-to-inherit rather than pin-everywhere. CI accepts exactly `absent | xhigh | max`;
any lower pin fails, so **no agent or skill pins an effort below `xhigh`**.

**What this does NOT do — state it plainly, because the previous wording claimed the opposite in
consecutive sentences.** There is **no in-plugin mechanism that raises a low session.** With `effort:`
omitted, a `low` session runs its subagents at `low`; nothing pulls it up. `CLAUDE_CODE_EFFORT_LEVEL`
outranks frontmatter regardless. So the floor is a **CI rule about what may be written into an asset**,
not a runtime guarantee — it prevents the repo from shipping a cap, and that is all it can do. The
earlier text asserted "the floor is unconditional" and then, three lines later, that it "cannot be
guaranteed from inside the plugin"; §11 is the designated source of truth for disputes, so the
contradiction is resolved here in favour of the mechanism that actually exists (PR #63 review, gap 20).

Consequence for tier selection: it is a *capability* decision, made on the assumption that the session
is run at an appropriate effort. If a maintainer needs a guaranteed minimum, it must be set on the
session (or via `CLAUDE_CODE_EFFORT_LEVEL`), not requested from the plugin.

Note on `opus` vs a version pin: `opus` is an **alias** that tracks the current Opus generation and
updates with the CLI; `claude-opus-5` would be a hard version pin. Prefer the alias — the guidance this
replaces ("prefer `inherit`/`sonnet` over hard-pinning `opus`") conflated the two.

---

## 12. Change-Failure Rate (CFR) Labeling

**Owner (causation):** `release-manager` · **Owner (label mechanics):** `jira-manager`

GitKraken Insights computes **Change Failure Rate** for `unleashedservices.atlassian.net` by counting
Jira issues tagged with the literal label **`change-failure`** (lowercase, hyphenated; a standard label,
not a custom field or issue type), divided by deployments over the window. Under-labeling **understates**
CFR — each missed failure lowers the numerator, reading a false 0% only in a window where nothing was
labeled; the metric is only as good as the labeling discipline.

- **`release-manager` determines deploy-causation (analysis only, no Jira access)** — it returns one of
  **three** verdicts for a production-impacting Bug: **confirmed** regression (corroborated evidence — bisect
  to a shipped commit, worked-in-prior-release, or crash-first-seen-in-release), **proven pre-existing**
  (positive evidence it predates the release), or **unconfirmed** (neither can be established). Absence of
  evidence is never downgraded to pre-existing. A reporter's bare "broke after release X" is temporal
  correlation, not proof — corroborate before attributing; severity alone never implies a change failure.
  `release-manager`'s `tools:` allowlist grants no Atlassian MCP, so it never queries or edits Jira — it
  receives a named candidate and returns the verdict.
- **`jira-manager` owns all Jira mechanics** — adds `change-failure` (**additive** to type / priority /
  component) at creation only when causation is confirmed at intake; otherwise it runs a **two-label queue**,
  *both* uncounted (only `change-failure` counts): **`cfr-triage-pending`** (fresh, awaiting attribution)
  and **`cfr-needs-human`** (escalated, awaiting human), at most one per issue. It **enumerates each queue**
  by JQL — `project in (COREDEV, FT) AND labels = cfr-triage-pending` (no status filter) and the parallel
  `… labels = cfr-needs-human` — and surfaces candidates so the invoking session dispatches `release-manager`
  for the *dispatch* queue only. Every label change is `editJiraIssue` read-modify-write (the `labels` field
  replaces the whole array). On `release-manager`'s verdict: **confirmed** → add `change-failure`, clear the
  marker; **proven pre-existing** → clear the marker, withhold; **unconfirmed** (neither corroboration nor
  pre-existence evidence) → **swap `cfr-triage-pending` → `cfr-needs-human`**, leaving the issue UNLABELLED
  on the human-review queue. Absence of evidence is never treated as pre-existing, no agent drops a marker on
  a guess, and because an escalated candidate no longer carries `cfr-triage-pending` it is not re-dispatched
  to `release-manager` absent new evidence (no churn). `cfr-needs-human` clears only on a terminal outcome —
  `change-failure` (confirmed), proven pre-existing, or an explicit human dismissal (a recorded decision).
- **Scope:** GitKraken defect detection covers projects **`COREDEV` and `FT` only** (LW / UV excluded).
  Labeling an out-of-scope issue does not affect CFR; widening scope is a GitKraken Insights config change,
  not an agent action.

Do NOT apply `change-failure` to: pre-existing bugs, feature requests, or any issue whose root cause is not
attributable to a recent deploy. See `jira-manager` (Change-Failure Labeling) and `release-manager`
(Change-failure attribution) for the operational detail.

---

## 13. Agent Output Style

Rules adapted from [`ayghri/i-have-adhd`](https://github.com/ayghri/i-have-adhd) (MIT), pinned at commit
`07684c4ab625dd7d1ea6e99e065f60bc0ac6a1ba`. **Adapted, not adopted** — see
`docs/planning/AGENT_OUTPUT_STYLE_PLAN.md` (COREDEV-2602) for the derivation and the evidence, and
`docs/planning/COREDEV-2605_SECTION13_NARROWING_PLAN.md` for this narrowing.

### Scope

This is a **narrowing, not a relaxation.** The five capture-roster reviewers are *out* of scope here
because their output is machine-consumed and governed by their own contracts — those contracts are
unchanged and still mandatory.

| `surface_id` | `producer_id` | `scope` | `anchor` |
|---|---|---|---|
| `verdict-report` | `swift-reviewer` | `in` | `agents/swift-reviewer.md:613` |
| `brainstorm-summary` | `brainstorm` | `in` | `skills/brainstorm/SKILL.md:141` |
| `implement-wrapup` | `implement` | `in` | `skills/implement/SKILL.md:237` |
| `pr-review-report` | `pr-review` | `in` | `skills/pr-review/SKILL.md:68` |
| `security-findings` | `security-reviewer` | `out` | `agents/security-reviewer.md:207` |
| `concurrency-findings` | `concurrency-reviewer` | `out` | `agents/concurrency-reviewer.md:265` |
| `ux-perf-findings` | `ux-perf-reviewer` | `out` | `agents/ux-perf-reviewer.md:199` |
| `accessibility-findings` | `accessibility-auditor` | `out` | `agents/accessibility-auditor.md:210` |
| `prompt-safety-findings` | `prompt-review` | `out` | `agents/prompt-review.md:95` |

This table is the **only** scope statement and it is **exclusive and normative**. Every row is exactly
one of `in`/`out`; rows are duplicate-free; every `surface_id`, `producer_id` and `scope` is drawn from a
finite allowlist, and any unknown key, catch-all, alias or semantically overlapping row is a **failure**,
not a skip. The four `in` `producer_id`s are an exact positive allowlist and are **disjoint** from
`capture.VALID_AGENTS`; each `out` `producer_id` is one of that roster. The binding is disjointness, not
equality — a future captured specialist is already out of scope by virtue of the positive allowlist and
must not force churn here. Prose descriptions are not row content; the `anchor` identifies
the surface in the repository and is validated by resolution, not by prose.

It does **not** govern skill-body documentation (that is injected context, not output).

### The rules

| # | Rule | Disposition |
|---|------|-------------|
| 1 | Lead with the next action | **Adapted** — lead the prose with the actionable point; never reorder a mandated payload to do it. |
| 2 | Number multi-step tasks | **Adapted** — number human-facing prose only. |
| 3 | End with one concrete next action | **Adapted** — end the prose with the next action. |
| 4 | Suppress tangents | **Adapted** — suppress out-of-scope tangents; **never** defer an in-scope finding out of the current array, and never drop a row from `swift-reviewer`'s **All Issues (Consolidated)** table. |
| 5 | Restate state every turn | **Adapted** — restate state in prose, never before a mandated result prefix. |
| 6 | Give specific time estimates | **Adapted** — estimates address whoever runs the steps; these agents advise, they rarely execute. |
| 7 | Make completed work visible | **Adopted** — state what now works, concretely. |
| 8 | Matter-of-fact tone for errors | **Adopted** — state cause and fix. No "Uh oh." |
| 9 | Cap lists at 5 items | **Restated positively** — rank prose for readability; **never** cap, split, omit or defer a machine-consumed finding, and never shorten the **All Issues (Consolidated)** table. Prose only. |
| 10 | No preamble, no recap, no closing pleasantries | **Adapted** — `Status:` and `BLOCKED — …` are **payload, not preamble**; the cure for an unwanted opener is to delete it, never to move it below `Status:`. |

Each disposition carries **exactly one** classifier from `{Adapted, Adopted, Restated positively}`.

### Precedence

Surfaces outside the four-item `in` allowlist above remain governed by their existing contracts, which
take precedence over every rule in this section — see §5 for the payload-region invariant and §14 for the
blocked-handoff prefix.

---

## 14. Blocked Subagent Handoff Contract

A subagent that cannot proceed hands control back with a **`BLOCKED — <reason>`** prefix as the first
line of its reply. This is **payload, not preamble**: §13 rule 10's carve-out exists so it is never moved
below `Status:` or deleted as an opener.

The handoff states, in this order: the **diagnosis**, what was **attempted**, the **user action
required**, and what remains. It is used for diagnostic confirmation
(`agents/graph-api-debugger.md`) and for Jira-tool failure (`agents/jira-manager.md`) — a subagent
pausing to hand control back for external action, which is why it belongs here and not in §2's
Plan → Implement contract.

---

## Cross-references

> Cross-references below describe the **consumer project layout** (what UnleashedMail
> looks like when this plugin is loaded against it). Paths are repo-relative within the
> consumer's checkout — they are NOT clickable links from this plugin repo, since the
> plugin can be installed anywhere. Each agent reads these locations from inside the
> consumer's working tree at runtime.

- Project root CLAUDE.md: `<consumer-root>/CLAUDE.md` (top-level project rules)
- Project rules: `<consumer-root>/.claude/rules/*.md` (8 path-scoped rules — auto-load by file path)
- Nested CLAUDE.md (under `<consumer-root>/`):
  `Unleashed Mail/Sources/Services/CLAUDE.md`, `Unleashed Mail/Sources/Views/CLAUDE.md`,
  `Unleashed Mail/Sources/Models/CLAUDE.md`, `Unleashed Mail/Sources/Utilities/CLAUDE.md`,
  `Unleashed Mail/Sources/Components/CLAUDE.md`, `Unleashed Mail/Sources/ViewModels/CLAUDE.md`
- Review skills (shipped with the plugin): the plugin registers them **namespaced** —
  `/unleashed-mail:gemini-review` / `/unleashed-mail:codex-review` / `/unleashed-mail:create-feature-plan`
  — and that is the invocation that **always resolves** (per the plugins-reference, a plugin's skills
  register exclusively under the `plugin-name:` namespace). The **bare** `/gemini-review` /
  `/codex-review` / `/create-feature-plan` aliases resolve **only** where the consumer workspace ships its
  own local copies under `.claude/skills/` (the host app does, and prefers them over the plugin's generic
  ones); in a fresh consumer checkout — or in this plugin repo itself — use the namespaced form. Skill
  sources at `skills/gemini-review/SKILL.md`, `skills/codex-review/SKILL.md`. The earlier workspace-only
  `.claude/prompts/*.md` files were retired when the skills moved into the plugin.
