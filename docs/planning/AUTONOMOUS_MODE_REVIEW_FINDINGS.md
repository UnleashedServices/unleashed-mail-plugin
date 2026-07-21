# Autonomous-Mode Plan — Plan-Review Gate Findings (COREDEV-2525)

**Artifact:** `docs/planning/AUTONOMOUS_MODE_EXPRESS_CONSENT_PLAN.md` (rev 6)
**Gate:** `/unleashed-mail:gemini-review` (agy, `gemini-3.1-pro-high`) + `/unleashed-mail:codex-review`
(`codex exec`, `gpt-5.6-sol`, effort xhigh, read-only) + `/unleashed-mail:review-synthesis`.
**Outcome:** **NOT PASSED — terminal at the plan's own `AUTONOMY_MAX_ROUNDS=6` cap.** Escalated to human
per the plan's own rule. Digest-bound verdicts persisted under `docs/planning/.verdicts/`.

## Round history

| Round | Plan rev | gemini | codex | Combined |
|---|---|---|---|---|
| 1 | rev 1 | REQUEST_CHANGES | REQUEST_CHANGES | REQUEST_CHANGES |
| 2 | rev 2 — env-signal Tier-A/Tier-B | APPROVE_WITH_NOTES | REQUEST_CHANGES | DISAGREEMENT |
| 3 | rev 3 — external Ed25519 signer | APPROVE_WITH_NOTES | REQUEST_CHANGES | DISAGREEMENT |
| 4 | rev 4 — honest cooperative + OS sandbox | APPROVE_WITH_NOTES | REQUEST_CHANGES | DISAGREEMENT |
| 5 | rev 5 — no plugin authority-expansion | APPROVE | REQUEST_CHANGES | DISAGREEMENT |
| 6 | rev 6 — repo-consistent invariant | APPROVE_WITH_NOTES | REQUEST_CHANGES | DISAGREEMENT |

## The converging conclusion

Across six rounds codex established — with live-docs + repo citations, and gemini did not dispute the
underlying facts — that **a Claude Code plugin cannot enforce autonomous-mode consent against its own
session's Bash.** There is no plugin-held privileged layer: `disable-model-invocation` only blocks the
Skill tool; on-disk markers, env vars, and even signed tokens are all reachable/replayable by same-user
Bash (nested/`--resume` Claude, `.claude` settings writes, `PATH` poisoning, replacing the verifier/pubkey);
`PreToolUse` command matchers fall to `gh api`/`curl`/renamed binaries; and plugin `settings.json` cannot
ship permission rules. **The only honest design delegates enforcement to the operator's OS sandbox +
managed permission rules, which the plugin can document but never provide.** rev 6 is a strong statement of
that ceiling; the gate correctly refuses to mark the residual wiring gaps below as a pass.

## Open residuals (codex round 6 — the hand-off list)

1. **`review-verdict.py dispatch` lands behind existing preapproval wildcards** (`review-verdict.py *` in
   `skills/brainstorm`; `scripts/*` in `skills/codex-review`, `gemini-review`, `review-synthesis`) —
   verified present. "Adds no new authority" is not established unless the prerequisite **COREDEV-2527**
   narrows those wildcard grants *before* `dispatch` ships.
2. **`/unleashed-mail:autonomous on` state transition is undefined and contradicts no-key→no-consent** — a
   `consent.sh` Bash call receives no hook-stdin `session_id`, so interactive grant cannot turn on without
   trusting the (untrusted) environment. Needs a hook-mediated transition (e.g. UserPromptSubmit/PreToolUse).
3. **Writable-artifact wording is internally contradictory** — with `.verdicts` writable (to fix the
   dispatcher deadlock), "only `dispatch` constructs an approval / trustworthy under operator config" is
   false. Narrow to: "`write` exposes no approving code path; `dispatch` is the only *intended* path; the
   artifact remains forgeable cooperative evidence." Drop tamper-prevention implications.
4. **PR/Jira validating wrappers are not a real trust boundary** — "re-reads its own launch env" is not
   operator-authenticated (Bash controls per-process env). Needs immutable operator-owned policy + exact
   destination/operation allowlists + credentials inaccessible to arbitrary session commands, or external
   mutation stays out of scope (artifact-only).
5. **Managed-settings exact forms** — `permissions.disableBypassPermissionsMode: "disable"` (string, not
   boolean); concrete `permissions.deny` rules (not "managed `disallowedTools`"); `allowManagedPermission
   RulesOnly`, `sandbox.network.allowManagedDomainsOnly`, `allowManagedMcpServersOnly` + authoritative
   `allowedMcpServers` by URL/command, `disableSideloadFlags`; if `allowManagedHooksOnly`, force-enable the
   plugin ID in managed `enabledPlugins` or its hooks are suppressed.
6. **Grant-inventory correction** — repo has 21 skills / 18 model-invocable / 20 with `allowed-tools` / 17
   both; `create-feature-plan` is model-invocable with no grant; `brainstorm`/`implement`/`pr-review` also
   carry grants. COREDEV-2527 must audit all 20 grants + inherited surfaces, not "the 18 skills'."
7. **Jira outbox reconciliation still underspecified** — per-op required fields; remote idempotency-key
   storage/query; atomic claim/lease for concurrent consumers; reconciliation for comments/transitions/
   updates, not just create + label RMW.
8. **`CLAUDE_PLUGIN_DATA` hook/non-hook split** — the variable is exported to hook processes but only
   substituted inline in skill content; non-hook scripts must be passed the substituted value explicitly or
   consent producer/consumer use different directories (audit MAJ-6).

## gemini round-6 non-blocking notes

- WebSearch `PreToolUse` hooks see only `tool_input.query`, not the resolved destination — for strict
  egress, deny WebSearch via `disallowedTools` and constrain WebFetch to the Context7 allowlist.
- SessionEnd refuses deletion on missing/mismatched `session_id`; add a passive stale-marker GC sweep
  (mtime > TTL) at session init so crashed sessions don't leak markers.
- Wire the COREDEV-2527 CI assertion in `validate-plugin-assembly.py` (reject unscoped `Bash`/`Write`/`Edit`
  grants outside an explicit allowlist manifest).
- Clean up preflight canary probe files in an EXIT trap.

## Suggested next decision (for the plan owner)

Either (a) accept the plan as **design-complete at the honest ceiling** and convert the residuals above into
concrete implementation conditions, with **COREDEV-2527 (narrow the wildcard/`Write`/`Edit` grants) as a
hard pre-merge prerequisite**; or (b) **descope external mutation** (PR-post / Jira-create auto-acts)
entirely, since a trustworthy in-plugin wrapper cannot be provided — which removes the largest surface codex
keeps flagging and likely lets a subsequent round converge.
