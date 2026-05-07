# UnleashedMail — Claude Code Plugin v2.2.0

A multi-agent development plugin for **UnleashedMail**, a native macOS 15+ email client supporting Gmail and Microsoft Graph, built with Swift 6, SwiftUI, AppKit, WKWebView, GRDB.swift (SQLCipher), and MVVM architecture.

**20 agents · 14 skills · 3 commands**

> v2.2.0 introduces [`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md) — the source of truth for cross-agent boundaries (release contract, plan-implement gate, data→logic→ui handoff, AI pipeline ownership, code review pipeline, CI pinning, MCP tool prefixes, mandatory project gates). When two agents disagree about a boundary, the contracts doc wins.

## What's New

### v2.2.0

- **New file: [`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md)** — formalizes cross-agent boundaries. Source of truth when agents disagree on workflow contracts.
- **20 agents (up from 15)** — adds `tester`, `code-simplifier`, `docs-engineer`, `ci-engineer`, `release-manager`.
- **14 skills (up from 10)** — adds `error-handling`, `accessibility-patterns`, `swiftlint-config`, `spm-management`.
- **Subagent dispatcher fix** — uses `Agent` (Claude Code's correct tool name), not `Task`. Fixed in 5 agent + 4 command/skill frontmatters.
- **MCP portability** — Atlassian and Context7 whitelist all three install prefixes (standalone, VSCode-shipped, plugin-namespaced) so the plugin works regardless of MCP install.
- **Project rule alignment** with the consumer project's `.claude/rules/*.md` system: `AccountScopedServiceProvider` for service resolution, `@State` (not computed property) for views, Curator design tokens, COREDEV-1578 Sendable matrix, image budget tiers, two-layer HTML pipeline (`HTMLSanitizer` + `HTMLRenderPipeline`), inline AI safety (`AISafetyPipeline` is PLANNED, not shipped), `BaseAIProvider` for Apple Intelligence, snake_case SQL columns, append-only migrations.
- **Project knowledge corrected fleet-wide** — quoted scheme name (`"Unleashed Mail"`), `xcodebuild test` everywhere (this is `.xcodeproj`, not SwiftPM), version scheme `MAJOR.MINORRELEASE.YYMMBB` per `docs/VERSIONING.md`, branch convention `1.0X/feature-name`, version-bump automation acknowledged.
- **Dangerous recommendations removed** — cert pinning for Google/Microsoft OAuth (they rotate certs), sandbox-disable workaround for Keychain prompts, append-only migrations no longer paired with rollback scripts.
- **Cross-agent inconsistencies resolved** — GitHub Actions SHA-pinned everywhere, `jira-manager` ticket-before-code rule with manual fallback, diagnostic agents have explicit Ask-before checkpoints for entitlements/auth/dependencies/toolbar/keyboard.
- **Hooks/scripts portability** — `test-runner.sh` removed from Bash hook (was running full test suite after every Bash command), null-delimited PII scan, no `xargs -a` (BSD-incompatible), no `<<<` here-strings (require writable `/tmp`), explicit refspec for `git fetch` so CI works on fresh clones.
- **`jira-manager` knows the Atlassian site** — embedded `https://unleashedservices.atlassian.net/` and project key `COREDEV` so it stops using placeholder URLs.
- **`smb-entrepreneur` and `enterprise-stakeholder`** — gain Grep+Glob so they can search project docs while stress-testing proposals.

15 rounds of Codex review iteration before merge. See PR #2 for the audit detail.

## Installation

This repo is both the plugin **and** its own marketplace (the repo ships [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)).

```bash
# 1. Add the marketplace (one-time)
claude plugin marketplace add npranson/unleashed-mail-plugin

# 2. Install the plugin
claude plugin install unleashed-mail

# 3. Restart Claude Code so the new agents/skills/commands load
```

To pull a newer version after upstream changes:

```bash
claude plugin marketplace update npranson/unleashed-mail-plugin
claude plugin update unleashed-mail
# Restart Claude Code
```

For local development against an unpushed clone:

```bash
claude --plugin-dir /path/to/unleashed-mail-plugin   # session-scoped, no marketplace required
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          SLASH COMMANDS                                      │
│    /brainstorm → /implement → /pr-review                                     │
└────────┬────────────────────┬───────────────────────────┬────────────────────┘
         │                    │                           │
         ▼                    ▼                           ▼
 ┌────────────────┐  ┌────────────────┐  ┌──────────────────────────────────────┐
│  PLANNING +    │  │ IMPLEMENTATION │  │      REVIEW ORCHESTRATOR             │
 │  PERSONAS      │  │  AGENTS        │  │      (swift-reviewer)                │
 │                │  │                │  │                                      │
 │ modern-        │  │ db-engineer    │  │  ┌─ security-reviewer                │
 │ standards-     │  │ logic-engineer │  │  ├─ concurrency-reviewer             │
 │ planner        │  │ ui-engineer    │  │  ├─ ux-perf-reviewer                 │
 │ smb-           │  │ ai-engineer    │  │  ├─ accessibility-auditor            │
 │ entrepreneur   │  │ tester         │  │  └─ provider parity audit            │
 │ enterprise-    │  │ code-simplifier│  │                                      │
 │ stakeholder    │  │                │  │                                      │
 └────────────────┘  └────────────────┘  └──────────────────────────────────────┘
         │                    │                           │
         ▼                    ▼                           ▼
 ┌────────────────────────────────┐  ┌──────────────────────────────────────────┐
 │  PROJECT MANAGEMENT            │  │  DIAGNOSTIC (on-demand, Ask-before)      │
 │  jira-manager (parallel)       │  │  xcode-build-fixer                       │
 │  docs-engineer                 │  │  graph-api-debugger                      │
 │  ci-engineer                   │  │                                          │
 │  release-manager               │  │                                          │
 └────────────────────────────────┘  └──────────────────────────────────────────┘
         │                    │                           │
         ▼                    ▼                           ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │                     AUTO-TRIGGERING SKILLS (14)                              │
 │  swift-tdd · swiftui-mvvm · grdb-patterns · macos-debugging ·               │
 │  webview-composer · keychain-security · gmail-api · graph-api ·             │
 │  provider-parity · agent-orchestration · error-handling ·                   │
 │  accessibility-patterns · swiftlint-config · spm-management                 │
 └──────────────────────────────────────────────────────────────────────────────┘
```

## Agents (20)

### Review Agents (run in parallel via orchestrator)

| Agent | Specialization |
|---|---|
| `swift-reviewer` | **Orchestrator** — spawns all 4 reviewers, runs parity audit, synthesizes unified verdict |
| `security-reviewer` | Credential exposure, OAuth/MSAL flaws, WKWebView injection (HTMLSanitizer + HTMLRenderPipeline), CI pipeline, entitlements, SQLCipher |
| `concurrency-reviewer` | Data races, actor isolation, async/await, GRDB threading, COREDEV-1578 Sendable matrix, deprecated APIs (Swift 6 enforced) |
| `ux-perf-reviewer` | Main-thread responsiveness, SwiftUI rendering, query perf, image budget tiers, perceived speed, error UX |
| `accessibility-auditor` | VoiceOver, keyboard nav, Dynamic Type, color contrast, focus management, Curator design system, dual-impl a11y parity |

### Coding & Implementation Agents

| Agent | Domain |
|---|---|
| `db-engineer` | GRDB 7+ schema (snake_case columns), SQLCipher, migrations (CRITICAL/DEFERRABLE), Record types, async observation, append-only |
| `logic-engineer` | Service protocols, Gmail + Graph impls via `AccountScopedServiceProvider`, ViewModels, AI pipeline routing, sync, mocks |
| `ui-engineer` | SwiftUI views (macOS 15+), AppKit bridging, WKWebView composer, Curator design tokens, `@State`-resolved services, a11y, dual-impl updates |
| `ai-engineer` | GARI AI pipeline — HTTPBasedAIProvider (cloud) + BaseAIProvider (Apple Intelligence), ToolRegistry, PromptRegistry, inline safety (PIIRedactor + LLMInputSanitizer), AIAgentPipeline |
| `tester` | Test strategy, MockServices.swift extension, `KeychainManager.resetInMemoryStore()` discipline, account-isolation invariants |
| `code-simplifier` | 16-pass conservative simplification with deletion guardrails (selectors, IBActions, reflection-loaded code preserved) |

### Stakeholder Persona Agents (used during brainstorming)

| Agent | Perspective |
|---|---|
| `smb-entrepreneur` | SMB founder (15-person firm, 150 emails/day) — evaluates speed, workflow, cost, keyboard-first UX |
| `enterprise-stakeholder` | IT director (500-5000 person org) — evaluates compliance, admin control, scale, SSO/MDM, security |

### Planning, Tracking & Diagnostic Agents

| Agent | Purpose |
|---|---|
| `modern-standards-planner` | Researches current best practices via Context7 + web search; cites `.claude/rules/` as standards source; gates plans on dual review |
| `jira-manager` | Ticket lifecycle — creation, Epic linking, milestone updates against `https://unleashedservices.atlassian.net/` (project key `COREDEV`) |
| `docs-engineer` | README, API docs (DocC via xcodebuild), user guides, planning docs, architecture, roadmap |
| `xcode-build-fixer` | Diagnoses and proposes fixes for Xcode build / package resolution failures (Ask-before for dependency changes) |
| `graph-api-debugger` | Microsoft Graph / MSAL auth troubleshooting (Ask-before for auth/entitlements edits) |
| `ci-engineer` | GitHub Actions workflows (SHA-pinned), Xcode Cloud, build automation, coordination with `bump-build-number.sh` Pre/Post-Action scripts |
| `release-manager` | `MAJOR.MINORRELEASE.YYMMBB` versioning, App Store / TestFlight submission, defers BB-byte to automation |

## Skills (14) — Auto-activate based on context

| Skill | Triggers When |
|---|---|
| `swift-tdd` | Implementing features, writing tests, refactoring (uses `xcodebuild test`) |
| `swiftui-mvvm` | Building views, view models, navigation, state management |
| `grdb-patterns` | Database models, migrations, queries, observation |
| `macos-debugging` | Crashes, memory leaks, performance issues, build failures |
| `webview-composer` | Email composition UI, contenteditable, JS bridge code |
| `keychain-security` | OAuth tokens, credential storage, encryption |
| `gmail-api-integration` | Gmail email fetching, sending, labels, Pub/Sub, OAuth flows |
| `microsoft-graph-integration` | Outlook/M365 email, MSAL auth (added via Xcode UI), Graph webhooks, delta queries |
| `provider-parity` | Any code touching provider-specific implementations or protocols |
| `agent-orchestration` | Coordinating multi-agent workflows, determining parallel execution strategy |
| `error-handling` | Error patterns, do-catch, Result types, error propagation |
| `accessibility-patterns` | Accessibility implementation patterns for macOS/SwiftUI |
| `swiftlint-config` | SwiftLint rule configuration, violation remediation |
| `spm-management` | Xcode-managed package dependencies (NOT root SwiftPM), version pinning, security audit |

## Commands (3)

| Command | Usage |
|---|---|
| `/unleashed-mail:brainstorm` | Design feature → Context7 research → spec → plan document → Jira ticket |
| `/unleashed-mail:implement` | Plan → db → logic → ui (layered agents) → multi-agent review → Jira updates |
| `/unleashed-mail:pr-review` | All 4 reviewers + a11y + parity in parallel → unified verdict → Jira logged |

## Parallel Execution

Agents are designed for **flexible parallel execution** in any combination. The `agent-orchestration` skill defines dependency rules:

- **Always parallel**: All review agents run simultaneously. `jira-manager` runs alongside everything.
- **Layered coding**: `db-engineer` → `logic-engineer` → `ui-engineer` (chained by dependency, but each can parallelize with `jira-manager`)
- **Any subset**: Request any combination — "just run security and accessibility reviewers", "only the db-engineer", etc.
- **Reactive agents**: `xcode-build-fixer` and `graph-api-debugger` fire on demand, not as part of standard pipeline.

## Mandatory Processes (from project CLAUDE.md)

The plugin enforces these non-negotiable processes:

1. **Planning document** — `docs/planning/FEATURE_NAME_PLAN.md` for every feature (no exceptions)
2. **Plan review gate** — Every plan or debug session must be reviewed by **both** `/gemini-review` and `/codex-review` before implementation. Both must produce APPROVE / APPROVE_WITH_NOTES; iterate (typically 2–6 rounds) until both converge.
3. **Context7 usage** — Mandatory for code generation, setup, config, API docs lookup
4. **Jira ticket hygiene** — Every change tracked at `https://unleashedservices.atlassian.net/` (project key `COREDEV`), updated throughout, with Epic association
5. **Provider parity** — Gmail ↔ Graph implementations stay in sync; views/ViewModels obtain providers via `AccountScopedServiceProvider`, never concrete types
6. **Accessibility** — Every UI element gets a11y support (mandatory per CLAUDE.md); use Curator design tokens
7. **Security invariants** — SQLCipher encryption, Keychain-only tokens, `account_email` filtering, PIIRedactor, two-layer HTML sanitization (`HTMLSanitizer` + `HTMLRenderPipeline`)
8. **SwiftLint compliance** — Fix violations when touching files (functions ≤50 lines, files ≤600 lines)
9. **Dual implementations** — Changes applied to both variants (native + WebKit compose, simple + full email detail, docked + floating AI)
10. **Ask-before checkpoints** — Don't auto-edit Xcode project structure, entitlements, Info.plist, app lifecycle, menus, toolbar, keyboard shortcuts, auth/token handling, or framework/SwiftPM dependencies. Surface for user approval first.

See [`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md) for the cross-agent boundaries that operationalize these processes.

## Environment Setup

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

The `.env` file is gitignored and will not be distributed with the plugin.

## Hooks

The plugin includes PostToolUse hooks that run automatically:

| Hook | Trigger | Behavior |
|---|---|---|
| `swift-lint-check.sh` | After Write/Edit | Syntax check, SwiftLint, `try!`/`as!` detection, token logging — **blocks on critical violations** |
| `swift-build-verify.sh` | After Bash | Detects build/test commands and reminds to verify results |

## Baked-In Knowledge

Agents come pre-loaded with Context7 research for the stack:

- **GRDB 7+**: Async read/write, `ValueObservation.trackingConstantRegion`, Swift 6 concurrency safety, `for try await` observation
- **SwiftUI macOS 15+**: `@Observable` + `@Environment`, `NavigationSplitView`, `ContentUnavailableView`, `@AccessibilityFocusState`, modern toolbar API
- **MSAL**: Public client desktop flow, silent/interactive acquisition, keychain access groups
- **Context7 library IDs**: Pre-resolved (`/groue/grdb.swift`, `/azuread/microsoft-authentication-library-for-objc`, `/websites/developer_apple_swiftui`, `/avdlee/swiftui-agent-skill`) — agents skip the resolve step

## License

MIT
