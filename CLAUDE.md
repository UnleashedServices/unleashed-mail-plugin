# unleashed-mail — Claude Code Plugin (developer instructions)

**This repo is a Claude Code _plugin_**, not the app. It ships the agents, skills, commands, hooks,
and a bundled MCP server used to develop **UnleashedMail** (a native macOS email client, in a
separate repo). You are working on the *plugin's own assets* here — treat them as software.

> **App-development knowledge lives in the shipped assets, not in this file.** Swift/SwiftUI/GRDB/
> MSAL/Gmail/Graph/Curator conventions are carried by the plugin's `agents/*.md` and `skills/*/SKILL.md`
> (and, at install time, by the consumer app repo's own `CLAUDE.md`). This plugin-root `CLAUDE.md` is
> loaded only for sessions working **in this plugin repo** — per the Claude Code plugins reference it is
> **not** injected into a consumer's session. Do not put app-domain rules here expecting installed agents
> to read them; put those in a skill body (preloaded via `skills:`) or the agent itself.

## What ships (auto-discovered by Claude Code)

```
agents/      21 subagents (*.md)                 skills/     21 skills (*/SKILL.md)
hooks/       hooks.json (10 events)              (incl. workflow skills brainstorm/implement/pr-review,
                                                  disable-model-invocation — commands merged into skills)
mcp/review-synthesizer/  1 bundled stdio MCP server (.mcp.json)
scripts/     hook scripts + validators + lib/    docs/       planning/, audits/, standards
AGENT_CONTRACTS.md   cross-agent boundaries (source of truth for disputes)
```

## Authoring rules (verified against code.claude.com/docs — the audit fixed real drift here)

**Sub-agent frontmatter** (`agents/*.md`) — keys are **camelCase**:
- `tools:` (allowlist; **omit to inherit ALL tools incl. MCP**), `disallowedTools:` (deny-list). **There is
  no `allowed-tools` for sub-agents** — that key is silently ignored (it's a skills/commands key). The CI
  validator now rejects it.
- If `tools:` is set, it is a strict allowlist: **MCP tools not listed are blocked**. To keep MCP access
  under install-defined server prefixes (Atlassian, Context7), **omit `tools:`** and scope with
  `disallowedTools:` (see jira-manager, modern-standards-planner).
- `model:` ∈ `inherit`(default) | `sonnet` | `opus` | `haiku` | `fable` | a model id. Prefer `inherit`/`sonnet`
  over hard-pinning `opus`.
- `skills:` (YAML list) preloads a skill's **SKILL.md body** (not its `references/`) at startup.
- **`memory:` (`user`/`project`/`local`) auto-enables Read/Write/Edit** — **never add it to a read-only agent**
  (it silently re-grants write access; this bit swift-reviewer once).

**Skills/commands** use kebab `allowed-tools:` — a **pre-approval grant, not a restriction** (skills cannot
deny tools). Don't grant unscoped `Bash, Write, Edit` on a pure-knowledge skill.

**Hooks** (`hooks/hooks.json` + `scripts/*.sh`): PostToolUse runs **after** the tool and cannot block —
feed the model via top-level `{"decision":"block","reason":…}` or `hookSpecificOutput.additionalContext`,
and **exit 0** (JSON is only read on exit 0). Plain stdout is invisible to the model on PostToolUse. The Stop
gate blocks with `{"decision":"block","reason":…}`. Use the helpers in `scripts/lib/hook-io.sh`.

## Validate before committing (all run in `.github/workflows/plugin-ci.yml`)

```bash
python3 scripts/validate-plugin-assembly.py --root . --strict     # frontmatter + manifests + agent keys
python3 scripts/validate-hooks.py --root . --strict --require-manifest
VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh  # plugin.json == README == counts (21/21/0/1)
bash scripts/test-hooks.sh                                         # hook stdin-contract harness
python3 -m unittest discover -s mcp/review-synthesizer/tests       # bundled MCP suite
shellcheck -s bash -S warning scripts/*.sh scripts/lib/*.sh .githooks/pre-commit
```

The pre-commit hook (`.githooks/pre-commit`; install with `git config core.hooksPath .githooks`) runs the
version-sync/assembly/hooks validators + a PII scan. It does **not** build/test the Swift app (this is a
Linux-friendly plugin repo — no Xcode).

## Mandatory processes

- **Planning + Plan Review Gate:** any feature/refactor/multi-step change gets a `docs/planning/*_PLAN.md`,
  reviewed by **both** `/gemini-review` (Antigravity `agy`, `gemini-3.1-pro`) and `/codex-review`
  (`codex exec -s read-only`) before implementation. Route non-TTY runs through `scripts/pty-capture.py`.
  Iterate until both APPROVE / APPROVE_WITH_NOTES.
- **Jira hygiene:** every change references a `COREDEV-XXXX` ticket (create one if none); update it with notes
  through implementation, not just at the end; associate with the parent Epic.
- **Context7 (mandatory)** for any library/framework/API/CLI lookup (Swift, SwiftUI, GRDB, MSAL, Gmail/Graph,
  Claude Code docs) — do not rely on training data.
- **Parallel tool calls** for independent work.

## Repository conventions

- **Branches:** `feat/COREDEV-XXXX-short-description` (use the Epic key when spanning children). Work in a
  dedicated `.claude/worktrees/<name>` worktree — never flip the main checkout's branch.
- **Commits:** `type(COREDEV-XXXX): description` — ticket is **mandatory**. Types: `feat`, `fix`, `chore`,
  `refactor`, `test`, `docs`.
- **Versioning:** `plugin.json` `version` (e.g. `2.4.2`) must stay in sync with the README H1 / What's-New
  heading and the asset counts — enforced by `validate-version-sync.sh`. Bump + CHANGELOG on release.
- **CI actions are SHA-pinned** (AGENT_CONTRACTS §6) — never `@vN` tags; Dependabot updates the pins.
- **Trunk:** `main` is the integration trunk; the canonical remote is `UnleashedServices/unleashed-mail-plugin`.

## The bundled MCP server

`mcp/review-synthesizer/` is a zero-dependency stdio JSON-RPC server (`synthesize_review` tool) that
deterministically merges the 5 reviewers' JSON findings for `swift-reviewer`'s Step-5. Pure compute, no repo
access; the verify gate stays in `swift-reviewer`. Tests: `python3 -m unittest discover -s mcp/review-synthesizer/tests`.

When two agents disagree about a boundary, **[`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md) is the source of truth.**
