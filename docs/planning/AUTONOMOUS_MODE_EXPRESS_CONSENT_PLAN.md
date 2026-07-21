# Autonomous Mode via Express Consent — Design Plan

**Status:** DRAFT (rev 6 — closes round-5 codex criticals: pre-existing tool grants, the `.verdicts`
deadlock, deny-matrix completeness, and every honesty-wording/schema fix. Final gate round per the plan's
own `AUTONOMY_MAX_ROUNDS=6`.)
**Ticket:** [COREDEV-2525](https://unleashedservices.atlassian.net/browse/COREDEV-2525)
**Prerequisites:** **COREDEV-2527** (audit/tighten existing skill `allowed-tools` grants) — hard pre-req.
**Deferred/optional:** COREDEV-2526 (external broker for tamper-evident artifacts) — NOT required by rev 6.
**Created:** 2026-07-19 · **Last Updated:** 2026-07-21
**Source material:** `docs/audits/PLUGIN_AUDIT_2026-07-19.md` + a live-docs survey (code.claude.com/docs).

## Foundational principle (rev 6, refined)

A plugin has no privileged layer its own session's Bash cannot reach. Rev 6 states the honest consequence
precisely (round-5 fix — the rev-5 wording was falsifiable against the shipped repo):

> **Autonomous mode defines NO new authority-expanding mechanism and gates nothing on plugin-computed
> state.** It does not *add* to the session's existing authority and does not *rely* on any plugin value
> to expand it. All enforcement is the operator's permission rules + OS sandbox, documented here as a deny
> matrix and never asserted, computed, or gated on in-plugin.

**Pre-existing tool grants are acknowledged, not denied (round-5 CRITICAL #1).** Eighteen model-invocable
skills already carry real `allowed-tools` grants — e.g. `Read, Write, Edit` on `gmail-api-integration:7`,
`grdb-patterns:7`, `macos-debugging:7`; `Write/Edit + Bash(...)` on `swift-tdd:7`, `spm-management:8`;
broad CLI families on `gemini-review:7`, `codex-review:6`. `allowed-tools` **is** a permission grant
(waives approval for the invoking turn — skills contract), so these predate and are independent of this
feature. Autonomous mode neither adds to nor depends on them. **They are audited/tightened under the hard
prerequisite COREDEV-2527**, and in an autonomous session they are constrained **only** by the operator's
deny rules + sandbox — by no plugin gate. Invariant 1 below is worded to match this reality.

## Consent & observation model

| Property | Design |
|---|---|
| Consent signal | `UNLEASHED_AUTONOMOUS=1` and/or `/unleashed-mail:autonomous on`; session-namespaced marker. **Cooperative only** — governs the plugin's own prose behavior; unlocks no security downgrade. |
| Preflight (telemetry) | `autonomy-preflight.sh` emits **channel-specific** advisory context (round-5 fix: a SessionStart *hook* probe cannot prove the Bash-tool sandbox or Edit/MCP boundaries — it only observes what a hook can see). Labels are per-channel (`fs-write-probe: RO`, `nested-claude-deny: present`, …), never a global `ENFORCED`. **Zero gates key off it.** Probes use a **non-clobbering canary path**, never opening the real `settings.json`. |
| Sensitive-guard | Not a plugin decision. Operator's `UNLEASHED_SENSITIVE_GUARD_MODE` only. **Round-5 fix:** the guard currently also honors `_MODE=off`/`UNLEASHED_SENSITIVE_GUARD=off` and treats any unrecognized mode as `warn` (`sensitive-file-guard.sh:92,138`) — a typo silently downgrades. Checklist item makes the enum **fail-closed** (unknown → `ask`) and documents every operator trust-root input. |
| Session-key | Verified key = **hook-stdin `session_id` only** (runtime-provided). `UNLEASHED_AUTONOMY_SESSION` (via `CLAUDE_ENV_FILE`) is an **untrusted session-scoping identifier** (a Bash caller can override it for one invocation) — usable for namespacing, never as a trust root. No verified key → **NO consent** (never adopt a sole marker). Because consent is cooperative-only, this is honesty/scoping, not a security bypass. |
| Storage/TTL/revoke | `$(marker_base)/sessions/<session_hash>/autonomy-consent`; TTL 8 h; `off`/expiry/SessionEnd. |
| Audit trail | `consent_log` (repo+session, controlled reasons, atomic/`fcntl.flock` append, PII-redacted, differentiated retention). Blocking is **per-event** — see the logging contract below. |

## Delegated-enforcement deny matrix (operator-side; documented — round-5 CRITICAL #2)

Native sandboxing covers **Bash subprocesses**; Edit/Write/MCP/hooks use **separate** permission
boundaries — enforcement needs permission rules **and** the sandbox. Required settings (previously missing):
`sandbox.failIfUnavailable: true`, `allowUnsandboxedCommands: false`, `disableBypassPermissionsMode: true`,
**managed-only** permission/domain/MCP policies, settings-source restriction, and MCP **server-load
(sideload)** control — not merely MCP tool-call rules.

| Channel | Operator control |
|---|---|
| Bash (+ PowerShell, `excludedCommands` widening) | OS sandbox + `deny` nested/`--resume` `claude`, renamed-binary paths; do not widen `excludedCommands` |
| Edit/Write (+ `NotebookEdit` via canonical `Edit(path)`) | `deny` on `.claude/**`, plugin dir, out-of-workspace. **NOT `.verdicts/**`** — see deadlock resolution |
| MCP (Atlassian/GitHub) + server loading | managed `disallowedTools` + deny MCP sideload; tool-name scoping can't constrain Jira params or GitHub HTTP methods → see PR/Jira |
| Network | managed domain rules + egress so external mutation flows only through a **defined** wrapper; block raw `curl`/`gh api` where auto-post isn't intended |
| WebSearch | **has no domain specifier** (tools-reference) → must be **denied** or checked by a PreToolUse hook validating `allowed_domains` (not a permission rule) |
| WebFetch | Context7-fallback allowlist only |
| Credentials/sockets/signing/release | sandbox denies unless the plan pre-authorizes and the operator opens them |

## `.verdicts` deadlock resolution (round-5 CRITICAL #2)

Denying `.verdicts/**` would block `review-verdict.py dispatch` itself (path-scoped `Edit` denies merge
into the Bash sandbox FS boundary). **Resolution: the verdict artifact stays cooperative and writable.**
The dispatcher writes it as an ordinary Bash subprocess; the plan makes **no tamper-protection claim** for
it (consistent with "the artifact is cooperative, not proof"). `.verdicts/**` is therefore **removed from
the Edit-deny matrix**. Tamper-evidence, if ever required, is the deferred external-broker item
(COREDEV-2526) — not part of rev 6, and not claimed.

## Layers (unchanged from rev 5 except the fixes below)

- **Layer 4 — review gate:** `dispatch` uses **absolute-path-pinned** executables, fixed argv, exit/timeout,
  and a **nonce-framed** verdict `<<<UNLEASHED_REVIEW_VERDICT nonce=<hex>: X>>>` (exactly one full-line
  frame; accepted vocabulary; a reviewed doc echoing the frame without the run nonce cannot match).
  **Round-5 fix:** the `write` path is incapable of producing an approving artifact **universally**
  (not "in autonomous mode" selected via forgeable consent) — only `dispatch` constructs an approval,
  period. Round counter: slug-keyed, **`fcntl.flock` from Python** (round-5: no `flock` binary on stock
  macOS), lockfiles under `${CLAUDE_PLUGIN_DATA}/locks/`; immutable `AUTONOMY_MAX_ROUNDS=6`.
- **Layer 3 — PR/Jira (round-5 CRITICAL #2):** no gated wrapper exists today, and tool-name scoping cannot
  constrain Jira parameters or GitHub HTTP methods. So autonomous PR-post and Jira-create are
  **artifact-only by default** — `pr-review` writes to `docs/planning/.pr-comments/`; `jira-manager`
  writes to the outbox. **Actual external mutation requires the operator to supply and permit a validating
  wrapper** (defined in the runbook: it re-reads its own launch env and validates the exact
  destination/method/params). Absent that wrapper, the plugin never mutates externally in autonomous mode.
- **Layer 5 — Jira outbox (round-5 STRONG):** required fields **per op** — `create` requires
  `project,type,summary`; `update|transition|comment|field` require `issue_key` (+ op-specific payload).
  A defined **dedup/reconciliation** algorithm handles remote-success/local-ack-lost (query-by-idempotency
  -key before re-create; label ops are read-modify-write per `jira-manager:187` → re-fetch prior state).
  Dead-letter on **`attempts >= max_attempts`** (round-5 off-by-one fix: `>=`, not `>`), precise increment
  timing. No silent expiry of pending records.

## Logging contract — per event (round-5 STRONG)

| Event | Log/lock failure behavior |
|---|---|
| PreToolUse | emit bounded diagnostic + **exit 2** before the 10 s timeout (mechanically blocks) |
| Stop | emit `{"continue":false,…}` exit 0 JSON-only (mechanically halts; never depends on the write) |
| SubagentStart | emit **no** consent context (fail-restrictive) |
| SessionStart | telemetry **fails silent/restrictive** (advisory only) |
| SessionEnd | if stdin `session_id` is **missing or mismatched → perform NO deletion** (never delete another/unknown session's marker); TTL remains the correctness backstop |
| Prose gate | **cooperative** halt only — the agent is instructed to stop on log failure; documented as not mechanically enforced |

## Safety invariants (rev 6)
1. **Autonomous mode adds no new authority and gates nothing on plugin-computed state.** Pre-existing skill
   `allowed-tools` grants are independent of this feature, audited under COREDEV-2527, and constrained in
   autonomous sessions only by operator deny rules + sandbox.
2. `hook-io.sh` never emits `permissionDecision:"allow"`.
3. Quality gates halt (never depending on a successful log/status write; hook primitive per the table).
4. Logging-failure blocking is **mechanical in decision hooks, restrictive in telemetry hooks, cooperative
   in prose gates** — no invariant claims prose-gate/telemetry logs are mechanically fail-closed.
5. An approving review artifact comes only from `dispatch`; `write` can never approve. The artifact is
   cooperative, trustworthy only under the operator's tamper-preventing config; consent is never the
   COREDEV-2493 waiver.
6. Consent expires; silence is never consent; unresolved/untrusted session key → no consent.

## Implementation checklist (delta from rev 5)
| # | Change | Files |
|---|---|---|
| 0a | **COREDEV-2527 (pre-req):** audit + tighten the 18 skills' `allowed-tools`; drop `Write/Edit` where unneeded | `skills/*/SKILL.md`, `scripts/validate-plugin-assembly.py` |
| 0b | `sensitive-file-guard.sh` enum **fail-closed** (unknown mode → `ask`; document `off`/`_MODE=off` inputs) | `scripts/sensitive-file-guard.sh` |
| 1 | Preflight: channel-specific telemetry + non-clobbering canary (no real `settings.json` open) | `scripts/autonomy-preflight.sh` |
| 2 | Deny matrix: add `failIfUnavailable`/`allowUnsandboxedCommands:false`/`disableBypassPermissionsMode`, managed-only + MCP sideload + PowerShell/NotebookEdit/WebSearch rows; **remove `.verdicts/**` from Edit-deny** | `README.md` (runbook) |
| 3 | Define the **PR + Jira validating wrappers**; default artifact-only when absent | `README.md`, `skills/pr-review/SKILL.md`, `agents/jira-manager.md` |
| 4 | `write` can **never** approve (universal); `dispatch`-only approval; `fcntl.flock` counter under `locks/` | `scripts/review-verdict.py` |
| 5 | Jira outbox: per-op required fields + dedup/reconciliation + `>=` dead-letter | `agents/jira-manager.md`, `scripts/` |
| 6 | Per-event logging contract incl. **SessionEnd no-delete on missing/mismatched session_id** | `scripts/lib/consent.sh`, `hooks/hooks.json` |
| 7 | `UNLEASHED_AUTONOMY_SESSION` documented **untrusted**; only hook-stdin `session_id` is a trust root | `scripts/lib/consent.sh`, `AGENT_CONTRACTS.md §13` |
| — | (rev-5 items 1–12 unchanged: namespaced markers, nonce frame, separate hooks w/ 5-reviewer roster intact, retention, Context7 allowlist, count 21/22/0/1 + 18/4 assertion, version 2.6.0) | — |

## Testing (delta — round-5 adversarial set)
Add: skill `allowed-tools` grant-escalation; invalid/`off` sensitive-guard modes (fail-closed); sandbox
unavailable + `dangerouslyDisableSandbox` + `excludedCommands` widening + PowerShell; hostile project/user
settings and MCP sideload; unrestricted WebSearch; direct `gh api`; arbitrary Jira params; the
`.verdicts` writable-not-denied path (dispatcher can write, artifact not claimed tamper-proof); Jira
remote-success/local-crash + duplicate-replay + concurrent-consumer + stale prior-state + dead-letter-move
failure; nonce test where the reviewed doc instructs the model to echo the supplied nonce (must stay
cooperative, not treated as proof); SessionEnd with missing/mismatched session_id performs no deletion;
`fcntl.flock` concurrent increments at the cap.

## Notes
- Round history: R1 RC → R2 DISAGREEMENT → R3 (signer) DISAGREEMENT → R4 (honest) DISAGREEMENT → R5
  (no-authority) DISAGREEMENT [gemini APPROVE / codex RC]. R5 codex found real residuals: shipped skills'
  `allowed-tools` grants contradicted an over-strong invariant, and the `.verdicts` deny deadlocked the
  dispatcher. Rev 6 rewords invariant 1 to match the repo (+ COREDEV-2527 to actually tighten the grants),
  resolves the deadlock (artifact stays cooperative/writable; `.verdicts` un-denied; no tamper claim),
  completes the deny matrix + PR/Jira wrapper story, and fixes every honesty-wording/schema/off-by-one
  item. This is round 6 = the plan's own `AUTONOMY_MAX_ROUNDS` cap; if the gate still diverges, the plan's
  own rule applies — persist the non-approving verdict and **escalate to a human** rather than iterate
  further.
- Recorded design decision (`AGENT_CONTRACTS.md §13`): the plugin is cooperative + observational only;
  autonomous enforcement is delegated to the operator's permission rules + OS sandbox (deny matrix);
  pre-existing tool grants are tightened under COREDEV-2527; tamper-evident artifacts are a deferred
  external-broker concern (COREDEV-2526), not claimed here.
