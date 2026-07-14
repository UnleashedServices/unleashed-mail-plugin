# UnleashedMail Plugin — Full Audit (2026-07-14)

**Scope:** entire plugin repo at v2.4.2 — 21 agents, 18 skills, 3 commands, hooks + 20 scripts, bundled `review-synthesizer` MCP server, CI/validators, and all cross-cutting docs — graded against Claude Code's *current* (July 2026) documented plugin/agent standards.

**Method:** 11 parallel dimension auditors + independent adversarial verification of every critical/high finding (each verified against the repo **and** the live official docs at code.claude.com/docs, not from memory) + a completeness critic. 54 agents total. Result: **42 confirmed critical/high findings** (0 refuted), **122 medium/low findings**, **5 coverage findings** from the critic. Full detail per finding: [`2026-07-14-plugin-audit-findings.md`](2026-07-14-plugin-audit-findings.md).

---

## Verdict

The plugin's *architecture* is ahead of the curve — a docs-legal nested subagent fan-out (supported since v2.1.172), a deterministic MCP synthesizer with an LLM verify gate, a fail-closed reviewer status contract, drift-free category vocabularies, and a hooks validator whose 30-event allowlist exactly matches the official docs. The *mechanics underneath it* have one fleet-wide defect and several silent-failure paths that mean much of the designed behavior does not actually happen in a real install:

1. **Every tool restriction in all 21 agents is inert** — the frontmatter key is wrong.
2. **The headline SwiftLint hook has been dead on any modern SwiftLint** — removed CLI flag.
3. **Hook feedback never reaches the model** — wrong exit-code/stdout contract on the PostToolUse hooks.
4. **The reviewer-capture pipeline likely never fires for plugin-installed agents** — bare-name matching vs plugin-scoped agent identifiers.
5. **Leaked secrets are still retrievable from git history** despite the "remove sensitive data" commit.

None of these produce an error anywhere — they are all silent. That is the central theme of this audit: the plugin is heavy on *instructional* enforcement (prose promises) and light on *mechanical* enforcement, and where it did build mechanical enforcement, key wiring is broken in ways CI doesn't catch.

---

## P0 — Broken now, silently (fix before anything else)

### 1. `allowed-tools:` is not a valid agent frontmatter key — all 21 agents inherit ALL tools
**Files:** every file in `agents/` (e.g. `agents/swift-reviewer.md:13`, `agents/jira-manager.md:12`)
Per the sub-agents doc and plugins reference (verified 2026-07-14), agent frontmatter supports `tools` and `disallowedTools`; `allowed-tools` is the **skill/command** key. When `tools` is omitted, a subagent "inherits all tools." Consequences:
- The five "read-only" reviewers (incl. `prompt-review`, which promises "never edits code") can Write/Edit and call every connected MCP server (Gmail, Slack, GitHub, Jira…).
- jira-manager's 27-entry Atlassian whitelist, the personas' read-only posture, and every least-privilege boundary in `AGENT_CONTRACTS.md` §9/§10 are prompt-text only.
- Irony: swift-reviewer's 5-way fan-out currently *works only because* of this bug (full inheritance includes `Agent`); after the rename its list already includes `Agent`, so orchestration keeps working.

**Fix:** rename `allowed-tools:` → `tools:` in all 21 agents; add `disallowedTools: Write, Edit` to the five specialist reviewers as belt-and-braces; drop `Bash` from `prompt-review` (needs only Read/Grep/Glob); drop `Agent` from jira-manager/ci-engineer/release-manager (no documented fan-out). Then add an unknown-key check to `validate-plugin-assembly.py` so this class of failure can't recur.

### 2. SwiftLint hook is dead: `--path` was removed in SwiftLint 0.56
**File:** `scripts/swift-lint-check.sh:43`
`swiftlint lint --path "$FILE_PATH"` — `--path` was deprecated in 0.48 and **removed** in 0.56 (current is 0.65), so the entire lint stage errors out and, because of finding #3, nobody ever sees it. **Fix:** positional form `swiftlint lint --quiet --force-exclude "$FILE_PATH"`, plus a guard that a non-zero swiftlint exit with zero parsed findings is itself logged as a hook failure.

### 3. PostToolUse hooks use the wrong feedback contract — findings never reach Claude
**Files:** `scripts/swift-lint-check.sh:127`, `scripts/swift-build-verify.sh:38`
The scripts print advisories/violations to **stdout** and exit **1** ("BLOCKED"). Per the hooks docs: exit 1 is a *non-blocking* error, blocking requires **exit 2 + stderr** (or JSON `{"decision":"block","reason":…}`), and PostToolUse stdout is *never* fed to the model — advisory context must go through `hookSpecificOutput.additionalContext`. So the `try!`/`as!` blocker, the token-logging guard, and every build/test reminder are invisible to the agent they address. **Fix:** emit the documented JSON shapes (add a `hook_emit_posttool_context` helper to `scripts/lib/hook-io.sh`); reuse the existing marker machinery for the fail-closed cases.

### 4. Reviewer capture (COREDEV-2326/2328) likely never fires when installed as a plugin
**Files:** `scripts/capture-reviewer-round-start.sh:32`, `scripts/capture-reviewer-verdict.sh:33`
Both SubagentStart/SubagentStop hooks match bare names (`security-reviewer|…`), but per the docs plugin-shipped agents surface with plugin-scoped identifiers (`unleashed-mail:security-reviewer`). The entire round-binding + status-sidecar pipeline then silently no-ops. **Fix:** normalize (`AGENT="${AGENT##*:}"`) before matching, log the received `agent_type` once in debug mode, and add a scoped-name case to `test-hooks.sh`.

### 5. Secrets remain in git history
**Critic finding.** Commit `edc27bf` (2026-03-10) committed `firebase-debug.log`; `1f18944` ("remove sensitive data from public repo") deleted it **from HEAD only** — the blob and the real GCP project ID are fully retrievable from history. **Fix:** add a history-aware secret scan (gitleaks/trufflehog) to CI; explicitly decide rewrite-history (git-filter-repo/BFG + coordinated force-push) vs. formally accepting the exposure (rotate/retire the identifiers).

### 6. Distribution identity is split across two GitHub owners
**Files:** `.claude-plugin/plugin.json:9`, `.claude-plugin/marketplace.json`, `README.md:98,109`
The actual origin is `UnleashedServices/unleashed-mail-plugin`; every distribution pointer (plugin.json `repository`, marketplace `owner`/`source.repo`/`homepage`, README `claude plugin marketplace add npranson/…` commands) targets `npranson/…`. Users following the README install from a different repo than the one being developed. **Fix:** pick the canonical home and update all six pointers + the marketplace `name`.

---

## P1 — Agent utilization & execution: capability left on the table

These are the direct answer to "today's standards in agent utilization" — the plugin was written against an older feature surface and doesn't use most of what agents/skills/hooks now offer.

### Subagent interaction model
- **Ask-before checkpoints can't execute** (`release-manager`, `xcode-build-fixer`, `graph-api-debugger`, `jira-manager`, AGENT_CONTRACTS §2/§7): subagents cannot use `AskUserQuestion` or pause for conversational input (docs-confirmed). Every "ask the user and wait" instruction silently no-ops or stalls. Rewrite as fail-closed handoffs: *"do NOT edit; return `APPROVAL REQUIRED:` + proposed diff; the invoking session asks the user and re-invokes."* Back the contract with the PreToolUse sensitive-file guard in `ask` mode (see below).
- **jira-manager's "print a banner and wait for acknowledgement" fallback** has no channel from inside a subagent — same rewrite applies.

### Model strategy (18 of 21 agents pin `model: opus`)
`opus` is a valid alias, but with the Claude 5 (Fable) family current, a Fable main session *downgrades* every spawned agent to Opus 4.8 — including personas producing qualitative commentary. Adopt tiering:
- `inherit` for swift-reviewer + the implementation engineers (tracks the session's frontier model);
- `sonnet` for the five first-pass reviewers (their findings are re-verified by the deterministic synthesizer + verify gate anyway — that structure *already exists*, it's just not exploited for cost);
- `haiku`/`sonnet` for personas and jira-manager;
- consider `effort:` and `maxTurns:` (both documented plugin-agent fields, both unused fleet-wide).

### Unused current frontmatter capabilities (fleet-wide: zero usage)
- **`skills:` preload** — agents *tell themselves in prose* to consult bundled skills (`db-engineer.md:32` "check the grdb-patterns skill", logic-engineer, ui-engineer, tester) but never preload them. Wire 1:1 pairings: db-engineer→grdb-patterns, ui-engineer→swiftui-mvvm, tester→swift-tdd, graph-api-debugger→microsoft-graph-integration, xcode-build-fixer→macos-debugging.
- **`memory:`** — the two diagnostic agents and swift-reviewer would gain the most from persistent memory of past diagnoses/reviews.
- **`disallowedTools`, `maxTurns`, `effort`, `background`, `isolation`** — all documented, all unused.

### Context economy (a real per-spawn cost)
- **Duplication of CLAUDE.md in agent bodies:** custom subagents already load CLAUDE.md; agents restate it wholesale (swift-reviewer's conventions block, db-engineer's GRDB corpus, ai-engineer's provider rules). This pays the token cost twice per dispatch and has *already produced drift* (see contradictions below). Strip agent bodies to role/workflow/deltas; let CLAUDE.md + skills carry shared facts.
- **swift-reviewer is a 34KB (~8.5k-token) system prompt** embedding shell libraries the plugin already ships in `scripts/`. Replace inline `detect_base`/`classify_subsystem`/status-read blocks with one-line script invocations (~4–5k tokens saved per spawn).
- **Zero progressive disclosure in skills:** all 18 skills are monolithic SKILL.md files (2,886 lines across the 13 technical ones); none uses `references/`, `scripts/`, or `assets/`. Restructure the five largest (microsoft-graph-integration, swiftlint-config, accessibility-patterns, provider-parity, error-handling) as rules + navigation with corpora in `references/*.md`.
- **docs-engineer (487 lines) / ci-engineer (375 lines)** are dominated by literal boilerplate templates injected on every invocation — move templates to skill reference files.

### `allowed-tools` in skills/commands means *pre-approval*, not restriction
All 13 technical skills carry `allowed-tools: Read, Write, Edit, Bash, Grep, Glob` under the apparent belief it declares capabilities. Per the skills doc, it **grants permission without prompting** and "does not restrict which tools are available" — so any auto-fired knowledge skill silently pre-approves unscoped Bash/Write/Edit for the turn. Same for `commands/implement.md` and `pr-review.md` (bare `Bash` pre-approves *every* shell command for the whole orchestration turn). **Fix:** remove `allowed-tools` from pure-knowledge skills; scope grants where genuinely needed (`Bash(xcodebuild *)`, `Bash(git *)`…); add `disallowed-tools: Write, Edit, Bash` to review-synthesis to make its read-only claim mechanical.

### Orchestration gaps (designed but not wired)
- **The mandatory Plan Review Gate is absent from the command pipeline**: `brainstorm` ends without invoking gemini/codex/review-synthesis; `implement` never checks for a Combined verdict. The plugin's own #1 mandatory process is enforced nowhere executable.
- **AGENT_CONTRACTS §5's code-simplifier pre-pass** ("runs first, clean before review") is wired into no command and missing from agent-orchestration's registry.
- **agent-orchestration skill covers 13 of 21 agents** while claiming to define strategy for "all agent combinations" — ai-engineer, tester, code-simplifier have no pipeline placement.
- **implement.md Phase 1 tells the model to run `/unleashed-mail:brainstorm`**, which has `disable-model-invocation: true` — impossible; fail closed through the user instead.
- **pr-review runs the full xcodebuild test suite twice** (command + swift-reviewer), only the second gating.
- **Commands are now legacy**: commands and skills have merged; repackaging the three commands as skills removes the duplicated 24-line `detect_base()` (→ `skills/pr-review/scripts/detect-base.sh`) and keeps the same `/unleashed-mail:*` invocations.

### The review-gate data plane
- **Fixed shared `/tmp` handoffs** (`/tmp/agy-out.txt`, `/tmp/codex-out.txt`) — cross-session clobbering, stale-transcript acceptance, predictable-path symlink exposure. Session-scope them (`/tmp/claude-reviews/${CLAUDE_SESSION_ID}/…`) and stamp transcripts with plan path + timestamp.
- **gemini-review's embedded prompts are interactive multi-turn prompts** ("Start by asking me what I'd like to review today") fed to a one-shot `agy -p` pipeline — a one-shot run returns no review. Ship a one-shot variant with an explicit VERDICT: instruction.
- **The smoke test contradicts the skill's own premise** (bare `agy -p` returns 0 bytes from Bash even on success) — route it through pty-capture.
- **pty-capture.py has no wall-clock timeout** while agy's print timeout (5 min) exceeds Bash's default 120s — add `--timeout` with exit 124, and Monitor/raised-timeout guidance.
- **Dual external-review gate is a hard SPOF**: on a fresh machine or CI (no `agy`/`codex` OAuth), the entire dev loop is blocked with no documented waiver/degradation path. Add a preflight + documented fallback in AGENT_CONTRACTS §2.

### Enforcement posture: warn-by-default is invisible
`sensitive-file-guard.sh` and `stop-quality-marker-gate.sh` both default to warn mode, and warn output (`systemMessage`) goes to the **user**, not the model — so the "Ask Before Modifying" gate and the Stop quality gate do nothing in a real install. Promote the guard's `ask` mode to default (the allowlist is already curated); make the Stop gate's warn mode at least emit model-visible context. Also: the reviewer JSON contract is emission-by-hope — the existing SubagentStop hook could *enforce* schema validity (block/annotate on schema.py failure) instead of only observing.

---

## P1 — Content contradictions that will mislead agents

These directly cause wrong code, because skills and agents disagree about the project's own invariants:

| Where | Contradiction |
|---|---|
| `skills/grdb-patterns` vs `agents/db-engineer` + CLAUDE.md | Skill teaches **camelCase SQL columns** throughout (`accountEmail`); db-engineer and CLAUDE.md mandate **snake_case + CodingKeys**. db-engineer tells itself to consult the very skill that contradicts it. |
| `skills/keychain-security` vs CLAUDE.md security table | Skill's architecture moves OAuth tokens **out of Keychain into an encrypted SQLite/file store** — precisely what the non-negotiable table bans ("Never: UserDefaults, files"). |
| `skills/error-handling:228` | Cache-fallback sample runs `MailMessage.fetchAll(db)` with **no `account_email` scoping** — teaches the exact cross-account leak the project's top invariant bans. |
| `skills/swiftlint-config:126` | `pii_logging_check` regex is doubly inert (escaped alternation + `${…}` instead of Swift's `\(…)`) — can never match Swift code. |
| `agents/logic-engineer` vs `code-simplifier` vs `tester` | Three different shapes of `MailProviderError`; tester's assertion doesn't compile against logic-engineer's definition. |
| `agents/ui-engineer` | Canonical macOS pattern uses `.toolbarVisibility(.hidden, for: .navigationBar)` — unavailable on macOS (needs `.windowToolbar`). |
| `skills/webview-composer` | Omits CLAUDE.md's bolded `isUserTyping` rule and demonstrates fire-and-forget `evaluateJavaScript`. |
| `skills/accessibility-patterns` / `swiftui-mvvm` | Endorse raw semantic colors/fonts and a file layout that contradict the Curator mandate and CLAUDE.md's source layout. |

Also: **this repo's CLAUDE.md is a copy of the app's** ("You are working on UnleashedMail, a native macOS email client") with no signposting — it misdirects every session in the *plugin* repo (wrong test commands, wrong branch/versioning conventions) and, per docs, is never loaded into consumer sessions anyway. Replace with plugin-repo instructions.

### MCP tool whitelists won't survive contact with real installs
jira-manager / modern-standards-planner enumerate per-tool names under three hardcoded prefixes (`mcp__claude_ai_Atlassian__*`, `mcp__atlassian__*`, `mcp__plugin_atlassian_atlassian__*`). Prefixes derive from the user's configured server name and are case-sensitive — in this very audit environment the live tools are `mcp__Atlassian_Rovo__*` and `mcp__Context7__*`, matching none of the three. Once the `tools` key is fixed (P0-1), these agents would *lose* their core capability on common installs. Prefer server-level patterns or omit MCP entries from `tools` entirely (inherit + permissions).

---

## P2 — CI, validation, and docs hardening

- **CI blind spots:** `pty-capture.py` (load-bearing for the mandatory gate) has zero coverage — not even `py_compile`; no expected-hooks inventory (deleting a safety hook from hooks.json passes CI); the reviewer allowlist is duplicated in 3 code sites + frontmatter with no cross-check; `validate-plugin-assembly.py` doesn't validate `model:`/`tools:` values, duplicate agent names, or that `.mcp.json`'s command target exists; marketplace.json is only JSON-parsed; version-sync skips CHANGELOG and AGENT_CONTRACTS (which is *again* stale at "v2.4.1" — the exact bug class 2.4.1 claimed to fix); no link/reference checker for cross-artifact paths; CI job-summary table prints the same `job.status` in every row.
- **Pre-commit:** the email-PII regex is dead code (BRE-mode grep makes `+`/`{2,}` literal — verified empirically); the PII scan filters to `*.swift` so in this repo it scans nothing; `.githooks/pre-commit` fails open when the checks script is missing; the required `git config core.hooksPath .githooks` install step is documented nowhere user-facing.
- **hooks.json details:** `swift-build-verify.sh` registered on Write|Edit where it's a guaranteed no-op process spawn per edit; the two per-edit hooks have no timeout (inherit 600s — a hung swiftc stalls every edit up to 10 min); PreToolUse matches `MultiEdit` but PostToolUse doesn't.
- **Docs:** README documents 2 of 11 hook commands and describes blocking behavior the hooks don't have; README's `.env.example` has never existed in the repo (while gmail-api-integration depends on an undocumented `.env` key); MIT claimed with no LICENSE file committed; CHANGELOG per-file test counts are actually suite totals; broken `../../Unleashed%20Mail/...` links in three agents + AGENT_CONTRACTS resolve nowhere post-install; 4 of 7 `docs/planning/` plans still show pre-implementation status for shipped work.
- **Supply chain:** SHA-pinned actions have no update mechanism (no Dependabot/Renovate `github-actions` ecosystem entry); no SECURITY.md; shellcheck unpinned from the runner image; no actionlint.
- **MCP server (minor — this component is in the best shape):** pins protocol `2025-06-18` (current finalized: `2025-11-25` — support both); explicitly-empty `changed_files` + real findings silently yields provisional APPROVE (fail-open inconsistency); a `finalize_review` tool would close the verdict loop that `decide_verdict` already implements; unused `REPORT_FINDING_TOOL` layer references a nonexistent `reviewers.py`; a Status-only reviewer message without a JSON fence never persists its `.status` sidecar — the exact degraded state COREDEV-2328 targets.

---

## What's genuinely strong (keep and build on)

- **The nested fan-out is legal and correctly reasoned** — subagent→subagent spawning verified supported (v2.1.172+, depth ≤5), `Agent` tool naming correct, and swift-reviewer even reasons correctly about spawn-freshness.
- **The bundled MCP server is excellent**: protocol-correct stdio JSON-RPC, 159/159 tests passing as a real subprocess, zero-dependency and determinism claims verified, `.mcp.json` matches the documented plugin mechanism, and `mcp__plugin_unleashed-mail_review-synthesizer__synthesize_review` is exactly the documented namespacing.
- **Category vocabulary is drift-free end-to-end** across six agents and `schema.py`.
- **The reviewer Output-Contract** (status orthogonal to findings; BLOCKED+[] can't read as clean) and the **verify gate** (deterministic merge in code, LLM only confirms blockers) match current best practice.
- **validate-hooks.py's 30-event allowlist exactly matches the official docs** — the validator itself was right; the semantic layer above it was where things broke.
- **Negative-knowledge guardrails** ("do NOT recommend cert pinning", "AISafetyPipeline does not exist yet") prevent classic plausible-but-wrong agent advice.
- **pty-capture.py** is well-engineered (controlling TTY via `pty.fork()`, SIGTERM→reap, CRLF normalization) — it just needs a timeout and CI coverage.

---

## Recommended remediation order

| Phase | Items | Effort |
|---|---|---|
| **P0 (this week)** | `allowed-tools`→`tools` fleet-wide + unknown-key CI check · SwiftLint positional args · PostToolUse JSON feedback contract · scoped-name matching in capture hooks · secrets-in-history decision + gitleaks CI · distribution identity | ~1–2 days |
| **P1a (agent modernization)** | Model tiering (`inherit`/`sonnet`/`haiku`) · `skills:` preloads · `disallowedTools`/`maxTurns`/`effort` · strip duplicated CLAUDE.md content from agent bodies · swift-reviewer prompt→scripts | ~2–3 days |
| **P1b (content truth)** | Fix the 8 contradictions table (grdb-patterns snake_case, keychain-security, error-handling scoping, pii regex, MailProviderError, toolbar API, isUserTyping, Curator) · rewrite plugin-repo CLAUDE.md | ~1–2 days |
| **P1c (pipeline wiring)** | Plan Review Gate into brainstorm/implement · code-simplifier stage · orchestration registry to 21 agents · session-scoped review transcripts · one-shot gemini prompts + pty timeout · external-CLI preflight/waiver · guard `ask`-mode default | ~2–3 days |
| **P2 (hardening)** | CI gaps (pty-capture coverage, hooks inventory, allowlist cross-check, model/tools validation, link checker, version-sync scope) · README hooks table + `.env.example` + LICENSE · skills progressive disclosure · commands→skills migration · MCP protocol bump · Dependabot/SECURITY.md | ongoing |

---

*Generated by a 54-agent audit (11 dimension auditors, 42 adversarial verifiers, 1 completeness critic); every critical/high finding independently verified against the repository and the live Claude Code documentation on 2026-07-14.*
