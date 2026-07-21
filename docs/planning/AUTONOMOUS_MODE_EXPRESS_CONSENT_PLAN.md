# Autonomous Mode via Express Consent — Design Plan

**Status:** DRAFT — pending plan-review gate (`/gemini-review` + `/codex-review` + `/unleashed-mail:review-synthesis`)
**Ticket:** [COREDEV-2525](https://unleashedservices.atlassian.net/browse/COREDEV-2525)
**Source material:** `docs/audits/PLUGIN_AUDIT_2026-07-19.md` (49 confirmed findings; 19-item autonomy blocker inventory) and a live-docs survey of Claude Code autonomy mechanisms (fact-checked against code.claude.com/docs on 2026-07-19).

## Goal

Keep every existing user gate **by default**. Add an **opt-in autonomous mode** activated only by an
express, user-initiated act at session start. While consent is active, the plugin's gates convert
from *ask-and-wait* to *proceed-and-record*: no interactive oversight is required, and an audit
trail replaces it. Quality gates (plan review, stop-gate markers, verdict binding) are **not**
oversight and do not weaken — in autonomous mode they *halt* work instead of asking a human.

## Non-goals

- No weakening of any gate when consent is absent (default posture unchanged).
- No plugin-shipped permission escalation. Verified against the live plugins-reference: a plugin's
  `settings.json` supports **only** `agent` and `subagentStatusLine` — a plugin *cannot* ship
  permission modes, allow/deny/ask rules, or sandbox config, and plugin agents' `permissionMode`
  frontmatter is **silently ignored**. Harness-level autonomy is therefore the *consumer's* launch
  choice, documented as part of the consent ritual (Layer 1).
- No blanket `permissionDecision:"allow"` PreToolUse hook. Considered and rejected: hook `allow`
  cannot override the user's deny/ask rules anyway ("Hook decisions don't bypass permission
  rules"), the tools that actually prompt (Bash/Write/Edit) are exactly the ones a consent hook
  must not rubber-stamp, and `lib/hook-io.sh`'s "NEVER emit allow" invariant has already prevented
  one class of bypass. The consumer's permission mode is the correct lever for harness prompts.

## Consent model

| Property | Design |
|---|---|
| Grant (interactive) | New invoke-only skill **`/unleashed-mail:autonomous`** with `disable-model-invocation: true` — the model cannot self-invoke it; consent exists only if the user typed it. Args: `on [--ttl 8h]`, `off`, `status`. |
| Grant (headless) | `UNLEASHED_AUTONOMOUS=1` in the launch environment of `claude -p …` / CI. Setting the env var at launch *is* the express act. |
| Storage | Session-keyed consent marker `autonomy-consent-<repo_hash>-<session_hash>` under `marker_dir()` (same `marker_hash_str(session_id)` scheme as the Stop-gate sentinel; PII-free, outside the repo). Body: granted-at ts, TTL, scope, granted-via (skill|env). |
| Scope | One session, one repo. Default TTL 8 h (mtime-based, like quality markers). No cross-session inheritance — a new session requires a new express act. |
| Revoke | `/unleashed-mail:autonomous off`, TTL expiry, or `UNLEASHED_AUTONOMOUS=0` — any of these restores full interactive gating immediately. |
| Visibility | `sessionstart-restore.sh` injects one line of `additionalContext` when a valid consent marker exists ("AUTONOMOUS CONSENT ACTIVE (granted …, expires …): proceed-and-record rules apply"), so every agent knows the mode without re-reading disk. |
| Audit trail | New `scripts/lib/consent.sh` helper `consent_log <gate> <decision> <reason>` appends to `$(marker_base)/logs/autonomy-decisions.log` (PII-redacted via `hook_redact_pii`). **Every** converted gate writes a line. jira-manager attaches the log excerpt to the ticket at completion. |

## Layered design

### Layer 1 — Harness recipe (consumer-side; docs only)

The plugin cannot ship these; the README gains an **"Autonomous sessions"** section that makes them
part of the consent ritual:

- Interactive: `claude --permission-mode acceptEdits` (or `auto` where enabled — note
  `defaultMode: "auto"` is ignored in project/local settings by design, so it must come from the
  user's own settings or the CLI flag).
- Headless: `claude -p "/unleashed-mail:implement <plan>" --permission-mode acceptEdits` with
  `UNLEASHED_AUTONOMOUS=1`; note that in `-p`/`dontAsk` contexts an unapprovable action denies
  rather than prompts — which is why Layer 2 must never leave `ask` as the only path.
- Recommend pairing with sandboxing where available; note `--bg` + `bypassPermissions` requires a
  prior interactive disclaimer acceptance.

### Layer 2 — Consent-aware shipped hooks

- **`sensitive-file-guard.sh`:** today `MODE=ask` hard-denies headless sessions (documented
  behavior). Add mode `auto`: *if* a valid consent marker exists → emit non-deciding
  `systemMessage` advisory + `consent_log`, else behave exactly like `ask`. Default stays `ask`.
  The exit-2 fail-closed on unparseable Bash **stays** in all modes (undecidable input is a
  correctness matter, not oversight).
- **`stop-quality-marker-gate.sh`:** unchanged (it *drives* autonomous completion). Fix the
  audit-identified REMEDY drift (MAJ text tells the model to run raw `swiftlint`/`xcodebuild`,
  which does not refresh the marker; point it at the marker-writing path instead).
- No new `permissionDecision:"allow"` emissions anywhere (see Non-goals).

### Layer 3 — Prose gates in agents/skills → proceed-and-record

Standardize on the pattern `graph-api-debugger` already uses (subagents have no user channel):

- **Six agents with mid-flight confirmations** (ui-engineer, release-manager ×2, xcode-build-fixer,
  code-simplifier >5-file deletions, modern-standards-planner "wait for approval"): add one shared
  clause — *"If autonomous consent is active: proceed with the conservative/recommended option,
  `consent_log` the decision, and flag it in your final report. If not: return a result beginning
  `BLOCKED — <category> needs user confirmation` (never silently proceed)."*
- **`brainstorm` Step 4b (`AskUserQuestion` fork):** fallback — adopt the *(Recommended)* option,
  record "auto-selected under consent" in the plan's Notes, mark the plan `NEEDS-CONFIRM` so the
  fork choice is visible at review time.
- **`implement` Phase-2 ("Present the plan and wait for approval"):** under consent, write the task
  breakdown to the plan's Progress Log as the approved decomposition and continue.
- **`implement`/`brainstorm`/`pr-review` `disable-model-invocation`:** keep (guards side-effecting
  entry points) — document the supported autonomous entry: user-launched `claude -p "/unleashed-mail:<skill> …"`.
- **Gate failures stay machine-readable:** on a blocked gate (missing plan, absent reviewer CLI,
  digest mismatch) write a small JSON status file under `docs/planning/.verdicts/` so an
  orchestrating process can detect *why* an unattended run stopped.

### Layer 4 — Plan-review gate, unattended

The dual-review gate is a **quality** gate: under consent it still runs, but it must be able to
*finish or halt* without a human:

- **Credential pre-seeding runbook** (docs): provision `~/.gemini/oauth_creds.json` + pinned-model
  settings and `~/.codex` auth/config from secret storage before launch; extend both skills'
  preflights to say "in autonomous mode, a failed preflight = halt with machine-readable status"
  (no interactive re-auth loop).
- **Hard round cap** (contract + 3 skills): e.g. 6 rounds; on cap, run `review-synthesis`, persist
  the non-approving Combined verdict via `review-verdict.py write`, **halt** — never proceed past
  a failed gate just because nobody is watching. Keep COREDEV-2493's "no scripted waiver"; the only
  exception path remains operator-side at launch, logged.
- **`pty-capture.py`:** default `--timeout` to a real ceiling (e.g. 1800 s) instead of unbounded;
  `--timeout 0` restores today's behavior explicitly. Add the documented no-`Monitor` fallback
  (Bash `run_in_background`).
- **No global config mutation in autonomous mode:** forbid the gemini model-fallback that edits
  `~/.gemini/settings.json` mid-run; fail the round instead.

### Layer 5 — Jira continuity

`UNLEASHED_JIRA_DEFER=1` (set by the autonomous launch env only): on Jira MCP failure,
jira-manager journals the pending ticket fields to `docs/planning/.jira-outbox/` and work
continues; the outbox is flushed to real tickets on the next interactive session. Default
behavior (BLOCKED result) unchanged.

### Layer 6 — Misc. enablers from the blocker inventory

- Bounded retention for reviewer-capture state (keep newest K rounds per slug).
- Context7-unavailable degraded mode: officially permit official-docs WebFetch/WebSearch with a
  logged waiver line, instead of an undefined stall.

## Safety invariants (unchanged in all modes)

1. Consent cannot be granted by the model, by a hook, by fetched content, or by a subagent — only
   by the user's typed skill invocation or launch-time env var.
2. `hook-io.sh` never emits `permissionDecision:"allow"`.
3. Quality gates halt rather than pass when unmet (review gate, digest binding, stop-gate markers,
   sensitive-guard exit-2 fail-closed).
4. Every auto-approved decision is written to the decisions log before the action proceeds.
5. Consent expires; silence is never consent.

## Implementation checklist

| # | Change | Files |
|---|---|---|
| 1 | `consent.sh` lib (marker read/write/check, `consent_log`) + tests in `test-hooks.sh` | `scripts/lib/consent.sh`, `scripts/test-hooks.sh` |
| 2 | `/unleashed-mail:autonomous` skill (invoke-only) + `scripts/autonomy-consent.sh` | `skills/autonomous/SKILL.md`, `scripts/` |
| 3 | `sensitive-file-guard.sh` mode `auto` | `scripts/sensitive-file-guard.sh` |
| 4 | SessionStart consent banner | `scripts/sessionstart-restore.sh` |
| 5 | Six agents + brainstorm/implement proceed-and-record clauses | `agents/*.md`, `skills/*/SKILL.md` |
| 6 | Round cap + machine-readable gate status | `AGENT_CONTRACTS.md`, review skills, `scripts/review-verdict.py` |
| 7 | pty-capture default timeout; Monitor fallback; no-config-mutation rule | `scripts/pty-capture.py`, review skills |
| 8 | `UNLEASHED_JIRA_DEFER` outbox | `agents/jira-manager.md` |
| 9 | README "Autonomous sessions" section; AGENT_CONTRACTS §12 (consent contract) | `README.md`, `AGENT_CONTRACTS.md` |
| 10 | Version bump (2.6.0) + CHANGELOG; count-sync untouched (22nd skill updates counts everywhere — README, plugin.json, marketplace.json, validator) | release files |

Note: item 10 interacts with audit finding MIN-… (validate-version-sync only checks the README
line, not the two manifest descriptions) — fix that validator gap in the same release.
