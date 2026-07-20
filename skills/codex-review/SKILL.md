---
name: codex-review
description: Read-only Codex CLI review for plans, debug sessions, and post-implementation audits. Paired with /gemini-review.
# MIN-27: scope the Bash grant to exactly what the body runs (plugin scripts, CLI probe, `codex`) so the
# 2-6 gate rounds stop re-prompting for the same pty-capture pipelines. No unscoped Bash.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(command -v *), Bash(codex *), Bash(rm -f /tmp/codex-out.txt*)
---

# Codex CLI Review

All plans and debugging sessions must also be reviewed by Codex CLI — non-negotiable, runs alongside `/gemini-review` (not as a replacement). Post-implementation audits also run Codex.

> **Preflight:** `command -v codex && codex --version`. If `codex` is unavailable (fresh machine / CI), the gate is **fail-closed** — do NOT count it as APPROVE. **There is no scripted waiver**: stop and let the *user* choose the recovery (install/authenticate the CLI, capture the review elsewhere, or explicitly direct work outside `/implement` — a workflow exception, not a passed gate). Present the choices; never select, infer, or self-waive. See "Preflight & unavailable-reviewer recovery" in `AGENT_CONTRACTS.md` §2.

Docs: https://developers.openai.com/codex/cli/reference

| Trigger | When |
|---------|------|
| New plan or architecture decision | BEFORE any code is written |
| Bug investigation or debugging | BEFORE proposing fixes |
| Post-implementation audit | AFTER code is written — read-only scan for security, concurrency, UX/perf, accessibility |

## Setup

- **Tool:** `codex` CLI.
- **Working directory:** always run from the project root (top-level workspace directory containing `Unleashed Mail.xcodeproj/`). Codex resolves relative paths against `$PWD`.
- **Model:** `~/.codex/config.toml` sets `model = "gpt-5.6-sol"` (Codex 5.6 "Sol"; `codex-cli` 0.144.4, verified 2026-07-16). The model is inherited by every `codex exec` call — **do not pass `--model`** on this ChatGPT-auth'd install (`gpt-5-codex` silently fails with zero-byte output when backgrounded).
- **⚠️ Effort: ALWAYS pass `-c model_reasoning_effort=xhigh` on a review call — do not rely on the config default.** The config *should* carry `model_reasoning_effort = "xhigh"`, but that setting is fragile: the Codex 5.6 upgrade silently reset it to **`low`** once already. A plain `codex exec` inheriting a `low` default reviews at low and silently under-powers the gate, with no error to notice. So every review recipe below passes `-c model_reasoning_effort=xhigh` explicitly — it makes the gate resilient to a config reset and correct on any machine regardless of its default. There is no dedicated `--reasoning-effort` flag; the generic `-c key=value` (confirmed on `codex-cli` 0.144.4) is the mechanism.
- **Pinning a config value one-off (rarely needed):** `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=xhigh -s read-only "PROMPT"` — the `-c model=…` shows an explicit model pin. Normally let the config supply the model and only force effort; never `--model` (zero-byte failure on this install).

## ⚠️ Always capture output via the PTY wrapper (eliminates 0-byte / STDN failures)

`codex exec` only reliably emits its result to a **real terminal**. When stdout is piped, redirected (`> file`, `| tee`), or the process is backgrounded — Claude Code's Bash tool, `run_in_background`, CI — codex can finish successfully yet write **0 bytes**. That is the recurring failure: the run "worked" but nothing was captured. The `-o PATH` flag mitigates it but is easy to forget and does not cover every backgrounded case.

**Default to routing every `codex exec` through the shared PTY wrapper:** [`scripts/pty-capture.py`](../../scripts/pty-capture.py) (invoke as `${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py`). It runs codex inside a pseudo-terminal so output always renders, ANSI-strips it, and writes it to `<out-path>`. There is **no flag to forget**, so capture cannot silently fail. This is the same wrapper [`gemini-review`](../gemini-review/SKILL.md) uses for `agy` — one PTY wrapper, both review CLIs.

```bash
# Put the prompt in a workspace file, then run codex through the wrapper.
# Wrapper timeout is 1200s: mandated `model_reasoning_effort=xhigh` runs to ~12 min; the previous 600s cap
# SIGTERM'd codex mid-run -> masked exit 124 / partial transcript / MISSING-verdict retry loop
# (COREDEV-2504). Matches gemini-review. Keep the Monitor pattern below — an outer runner timeout could
# otherwise kill the run before the wrapper's cap fires.
# MAJ-10: pre-clean the fixed transcript path FIRST so a wrapper that never starts (codex absent / auth
# expired / a Bash-tool kill before pty-capture's finally-write) leaves this file ABSENT — never a STALE
# previous-round transcript that review-synthesis would read as THIS round's verdict. Absent maps to
# MISSING -> the gate fails closed. Re-run this before every round; it also clears the captureid.
rm -f /tmp/codex-out.txt /tmp/codex-out.txt.captureid
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py" --timeout 1200 /tmp/codex-out.txt -- \
    codex exec -c model_reasoning_effort=xhigh -s read-only "$(cat .codex-prompt.md)"
# Captured output is in /tmp/codex-out.txt; the wrapper's exit code matches codex's.

# Skill-based audit through the wrapper:
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py" --timeout 1200 /tmp/security.txt -- \
    codex exec -c model_reasoning_effort=xhigh -s read-only "/security-reviewer [FILES]"
```

Interface: `pty-capture.py [--timeout SECONDS] <out-path> -- <command> [args...]`. Read `<out-path>` back into context after the run. If `${CLAUDE_PLUGIN_ROOT}` is unset (skill running outside the plugin), use the repo-relative `scripts/pty-capture.py`.

## Monitor, not Bash background (user-confirmed preference)

> **Source:** user auto-memory `feedback_codex_monitor_pattern.md` — this is a project-specific operational preference the user has confirmed, not a rule from the original `.claude/prompts/codex-review.md` (workspace-only artifact).

For non-trivial `codex exec` runs, route the process through the `Monitor` tool. Reason on this project: `Bash run_in_background` has produced 0-byte outputs on long Codex runs, while `Monitor` has been reliable. **Combine the two:** run the PTY wrapper above *under* `Monitor` (`pty-capture.py /tmp/out.txt -- codex exec …`) so a long run is both reliably scheduled and reliably captured — the wrapper guarantees the bytes land in the file, `Monitor` guarantees you don't block on it.

## Invocation patterns

> **Capture:** the forms below show the codex *command shape*. From any non-TTY context (Claude Code's Bash tool, CI, backgrounded runs) wrap each with `pty-capture.py <out> -- …` per the PTY-wrapper section above so output is never lost. The `-o PATH` forms are the in-terminal fallback.

```bash
# Plan / debug review (non-interactive, read-only)
codex exec -c model_reasoning_effort=xhigh -s read-only "PROMPT_HERE"

# Targeted agent-role audit (post-implementation) — see skill list below
codex exec -c model_reasoning_effort=xhigh -s read-only "/security-reviewer [FILES]"

# Full diff review — built-in `codex review` (outputs to STDOUT; no -o — capture via the PTY wrapper)
codex -c review_model=gpt-5.6-sol -c model_reasoning_effort=xhigh review --uncommitted
codex -c review_model=gpt-5.6-sol -c model_reasoning_effort=xhigh review --base main
codex -c review_model=gpt-5.6-sol -c model_reasoning_effort=xhigh review --commit <SHA>

# Save agent output to file
codex exec -c model_reasoning_effort=xhigh -s read-only -o /tmp/output.md "PROMPT_HERE"
```

> **The built-in `codex review` path pins EFFORT, not the MODEL.** `-c model_reasoning_effort=xhigh`
> only overrides effort; the built-in review resolves its model from config — and if `~/.codex/config.toml`
> sets `review_model` (a recognized key, verified on 0.144.4), `codex review` uses THAT, not the session
> `model`. So a machine left with a stale `review_model` can run the diff audit on an old model despite the
> v2.5.0 "review tooling is on `gpt-5.6-sol`" guidance. For the built-in path, either verify `review_model`
> is unset/`gpt-5.6-sol` or pin it inline with a `-c review_model=gpt-5.6-sol` override alongside the effort
> override. The `codex exec "/skill …"` audits are unaffected — they inherit the session `model`.
>
> ```bash
> codex -c review_model=gpt-5.6-sol -c model_reasoning_effort=xhigh review --uncommitted
> ```

## `codex exec` flags (non-interactive)

| Flag | Purpose |
|------|---------|
| `exec` | Non-interactive scripted execution (no TUI) |
| `-s read-only` / `--sandbox read-only` | Prevents file modifications — safe for audits |
| `-s workspace-write` | Allows writes within project directory |
| `-m MODEL` / `--model MODEL` | Override model selection (do not use on this install) |
| `-o PATH` / `--output-last-message PATH` | Write final response to file |
| `--ephemeral` | Run without persisting session files |

## `codex review` flags (built-in review mode)

| Flag | Purpose |
|------|---------|
| `--uncommitted` | Review staged, unstaged, and untracked changes |
| `--base BRANCH` | Review changes against the given base branch |
| `--commit SHA` | Review changes introduced by a specific commit |
| `--title TITLE` | Commit title for the review summary — **requires `--commit`** (`codex review --title …` alone errors: `Usage: codex review --commit <SHA> --title <TITLE>`) |
| `[PROMPT]` | Custom review instructions (`-` reads from stdin) — a **review target of its own**, mutually exclusive with `--uncommitted`/`--base`/`--commit` |

`codex review` takes exactly **one** review target: `--uncommitted`, `--base`, `--commit`, **or** a
custom `[PROMPT]` — they **conflict** and cannot be combined. Verified on `codex-cli` 0.144.4:
`codex review --uncommitted "focus on X"` exits non-zero with the argument-conflict error
(`--uncommitted` cannot be used with `[PROMPT]`). So `[PROMPT]` steers a review INSTEAD of a diff
target, not on top of one. It writes to
**stdout only — there is no `-o`/`--output-last-message`** on `codex review` (that flag is
`codex exec`-only), so capture it via the mandated PTY wrapper. For a steerable review of specific
changes, keep the instructions on `codex exec -c model_reasoning_effort=xhigh -s read-only "/skill ..."`,
which carries the skill rubric and takes both a prompt and file targets.

## Codex skills — mirror of the Unleashed Mail plugin

Codex has first-class skills that mirror every Unleashed Mail plugin agent, command, and skill. Invoke the skill by name inside `codex exec` — skills carry their own rubric and output contract.

General form: `codex exec -c model_reasoning_effort=xhigh -s read-only "/<skill-name> [ARGS or FILES]"`

**Review** (run the first five in parallel, then synthesize with `/swift-reviewer`):
- `/security-reviewer` — credential exposure, injection, insecure storage, entitlement misuse, OAuth flaws, supply-chain risks
- `/concurrency-reviewer` — race conditions, data races, actor isolation, unsafe threading, deprecated Swift/Apple APIs
- `/ux-perf-reviewer` — UI responsiveness, animation, memory, DB query perf, network optimization
- `/accessibility-auditor` — VoiceOver, keyboard nav, Dynamic Type, color contrast, a11y labels/hints/traits
- `/prompt-review` — AI prompt/call-site safety: jailbreak/injection surface, refusal paths, unsanitized ingress, tool scoping, PII-in-logs
- `/swift-reviewer` — orchestrator + provider-parity audit + synthesizer

**Implementation:** `/logic-engineer`, `/ui-engineer`, `/db-engineer`, `/ai-engineer`, `/tester`, `/code-simplifier`

**Planning & personas:** `/modern-standards-planner`, `/smb-entrepreneur`, `/enterprise-stakeholder`, `/unleashed-mail:brainstorm`, `/unleashed-mail:implement`, `/unleashed-mail:pr-review`

**Diagnostics:** `/xcode-build-fixer`, `/graph-api-debugger`, `/macos-debugging`

**CI / release / project:** `/ci-engineer`, `/release-manager`, `/jira-manager`, `/docs-engineer`

**Domain skills:** `/swiftui-mvvm`, `/microsoft-graph-integration`, `/gmail-api-integration`, `/keychain-security`, `/grdb-patterns`, `/webview-composer`, `/provider-parity`, `/swift-tdd`, `/error-handling`, `/accessibility-patterns`, `/swiftlint-config`, `/spm-management`

**Infrastructure:** `/agent-orchestration`

**Review tooling (v2.4.1):** `/gemini-review`, `/codex-review`, `/create-feature-plan` (canonical bare workspace names; the plugin also bundles them namespaced as `/unleashed-mail:gemini-review` etc.)

If a skill is missing from a given install, list `~/.codex/skills/` before falling back to a free-form prompt.

## Example invocations

```bash
# Parallel audit — one codex exec per skill, run concurrently via Monitor
codex exec -c model_reasoning_effort=xhigh -s read-only "/security-reviewer [FILES]"
codex exec -c model_reasoning_effort=xhigh -s read-only "/concurrency-reviewer [FILES]"
codex exec -c model_reasoning_effort=xhigh -s read-only "/ux-perf-reviewer [FILES]"
codex exec -c model_reasoning_effort=xhigh -s read-only "/accessibility-auditor [FILES]"
codex exec -c model_reasoning_effort=xhigh -s read-only "/prompt-review [FILES]"

# Synthesize after the five complete
codex exec -c model_reasoning_effort=xhigh -s read-only "/swift-reviewer [PRIOR_OUTPUTS or FILES]"

# Implementation consult
codex exec -c model_reasoning_effort=xhigh -s read-only "/grdb-patterns How should I add a ValueObservation for [TABLE]?"

# Plan / debug (unstructured — when no skill is a good fit)
codex exec -c model_reasoning_effort=xhigh -s read-only "PLAN_OR_DEBUG_CONTENT"
```

## Full workflow (plan or debug → implementation → post-impl audit)

1. **Plan review:** `codex exec -c model_reasoning_effort=xhigh -s read-only "PLAN_CONTENT"` — **end the prompt asking Codex to finish with an explicit `VERDICT: APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES` line** so the synthesis step can parse it deterministically. Once gemini's paired transcript is also captured, run `/unleashed-mail:review-synthesis` to combine `/tmp/codex-out.txt` + `/tmp/agy-out.txt` into one auditable **Combined verdict** block before implementation.
2. **Post-implementation audit:** run the five Codex audit skills in parallel (`/security-reviewer`, `/concurrency-reviewer`, `/ux-perf-reviewer`, `/accessibility-auditor`, `/prompt-review`) with `-s read-only`
3. **Full diff review:** optionally also run `codex -c review_model=gpt-5.6-sol -c model_reasoning_effort=xhigh review --uncommitted`
4. **Synthesize:** run `/swift-reviewer` last, feeding it the five audit outputs
5. Incorporate feedback from both Gemini and Codex before considering work complete

## Safety rules

- **Always `-s read-only` for audits** — never `--full-auto`, `danger-full-access`, or `--dangerously-bypass-approvals-and-sandbox`
- `--dangerously-bypass-approvals-and-sandbox` is reserved for externally sandboxed CI environments only
- `codex exec -c model_reasoning_effort=xhigh -s read-only` with skill prompts is the preferred pattern for targeted reviews
- `codex -c review_model=gpt-5.6-sol -c model_reasoning_effort=xhigh review` is the built-in general diff review; its target is **exactly one** of `--uncommitted` / `--base` / `--commit` / a custom `[PROMPT]` — these **conflict**, so a `[PROMPT]` replaces a diff target rather than refining one (`codex review --uncommitted "…"` errors). It outputs to stdout (capture via the PTY wrapper — no `-o`). The `review_model` pin is needed because the built-in review path resolves its model from `review_model`, not the session `model` (see the callout above)

Both Gemini and Codex must review plans before implementation begins. Neither review is optional.
