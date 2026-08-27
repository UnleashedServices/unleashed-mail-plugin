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
                                                  model-invocable — commands merged into skills)
mcp/review-synthesizer/  1 bundled stdio MCP server (.mcp.json)
scripts/     hook scripts + validators + lib/    docs/       planning/ (+ audits/ on later branches)
.claude-plugin/  plugin.json + marketplace.json
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
- `model:` ∈ the runtime alias table — `sonnet` | `opus` | `haiku` | `fable` | `best` | `opusplan` |
  the long-context forms `sonnet[1m]` / `opus[1m]` / `fable[1m]` — plus `inherit` (default) or a full
  model id. There is **no** `default` alias, and only sonnet/opus/fable take `[1m]`.
  `opus` is an **alias** that tracks the current Opus generation; `claude-opus-5` is a hard version
  pin. Prefer the alias. (The old "prefer `inherit`/`sonnet` over hard-pinning `opus`" guidance
  conflated the two and is superseded by AGENT_CONTRACTS §11's consequence-based tiering.)
- **`effort:` is a FLOOR, not a pin** — assets omit `effort:` and **inherit** the session level, so a
  `max` session is not silently pulled down. CI rejects any pin below `xhigh`; `xhigh`/`max` are legal.
  Frontmatter effort is an override in BOTH directions (it pulls a `max` session down), and
  `CLAUDE_CODE_EFFORT_LEVEL` outranks it, so the floor is not enforceable from inside the plugin.
- `skills:` (YAML list) preloads a skill's **SKILL.md body** (not its `references/`) at startup.
- **`memory:` (`user`/`project`/`local`) auto-enables Read/Write/Edit** — **never add it to a read-only agent**
  (it silently re-grants write access; this bit swift-reviewer once).

**Skills/commands** use kebab `allowed-tools:` — a **pre-approval grant, not a restriction** (`allowed-tools`
itself never denies; to *remove* tools for a skill's active window use the separate `disallowed-tools:`
key, cleared on the next user message). Don't grant unscoped `Bash, Write, Edit` on a pure-knowledge skill.

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
python3 -m unittest discover -s scripts/tests                      # scripts suite (review-verdict gate)
shellcheck -s bash -S warning scripts/*.sh scripts/lib/*.sh scripts/review/*.sh .githooks/pre-commit
python3 scripts/validate-plan-citations.py --selftest docs/planning/COREDEV-2617_PLUGIN_STATE_BASE_DIR_PLAN.md
python3 scripts/validate-plan-citations.py docs/planning/COREDEV-2617_PLUGIN_STATE_BASE_DIR_PLAN.md   # line-pinned citations rot when files shift
git diff --check "$(git merge-base origin/main HEAD)" HEAD                                              # whitespace, as CI checks it
python3 scripts/review/generate-callers-exemptions.py && git diff --exit-code -- scripts/review/callers-scan-exemptions.tsv
```

**Run the whole list, not the first six** — CI's `validate` job was red on PR #67 for two review passes
because the plan-citation linter (added there in the same PR) was never part of the local gate, and
the local suite kept passing while a shifted line pin failed the linter's own self-test.

The pre-commit hook (`.githooks/pre-commit`; install with `git config core.hooksPath .githooks`) runs the
version-sync/assembly/hooks validators + an **advisory** secret/PII pattern scan over all staged text files
(enforced by `gitleaks --staged` when installed, and by the history-aware gitleaks job in CI). It does
**not** build/test the Swift app (this is a
Linux-friendly plugin repo — no Xcode).

## Mandatory processes

- **Planning + Plan Review Gate:** any feature/refactor/multi-step change gets a `docs/planning/*_PLAN.md`,
  reviewed by **both** `/unleashed-mail:gemini-review` (Antigravity `agy`, `gemini-3.6-flash-high`) and `/unleashed-mail:codex-review`
  (`codex exec -c model_reasoning_effort=xhigh -s read-only`) before implementation (the plugin registers its skills namespaced; a bare `/gemini-review` resolves only where the consumer workspace ships local copies). **Drive each arm through its capture wrapper, not the CLI and not `pty-capture.py` directly:**
  `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/capture-codex-review.sh" <ticket> <round> <prompt> <plan> [timeout]`
  (`capture-gemini-review.sh` takes the same operands plus a trailing `[model]` — that SIXTH operand
  is the only way to fall back a model, because the wrapper always passes `--model` and therefore
  overrides `~/.gemini/settings.json`). Each one allocates the transcript, binds BOTH the prompt
  digest and the plan to it via `bind-prompt.py`, then runs `isolated-<arm>-review.sh`. Skipping the
  bind is fail-closed, not silent — the arm refuses with `GATE FAILED — no bound plan snapshot`.
  `pty-capture.py` sits underneath these; it is not the entry point. **Kimi K3 is available as a third
  arm** via `scripts/review/isolated-kimi-review.sh <prompt> <transcript> <commit> [timeout] [plan]` —
  it has no `capture-` wrapper, so allocate and bind first, and PASS YOUR PLAN (its plan operand
  defaults to the COREDEV-2617 plan).
  Iterate until both APPROVE / APPROVE_WITH_NOTES, then run `/unleashed-mail:review-synthesis` to combine
  the two transcripts into a single auditable Combined verdict.
  **Create the feature worktree FIRST**, then create the plan, snapshot, review, synthesize and
  implement **all inside that same worktree**. The Combined-verdict artifact is per-directory session
  state under `docs/planning/.verdicts/` — it is git-ignored twice over and does **not** follow a later
  `git worktree add`, so gating in one checkout and implementing in another fails the gate on a genuine
  approval (hit on COREDEV-2583 with byte-identical plan content). Two mandatory conventions in this
  file used to contradict each other on exactly this point; this ordering is the resolution.
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
