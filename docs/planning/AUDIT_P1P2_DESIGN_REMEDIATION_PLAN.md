# Plugin Audit — Design-Heavy Remediation Plan (P1b-design / P1a-2 / P1c / P2)

**Status:** DRAFT v5 — in plan-review gate. R1 gemini RC / codex MISSING; R2 gemini APPROVE / codex RC; R3 gemini APPROVE / codex RC; R4 gemini `APPROVE_WITH_NOTES` / codex `REQUEST_CHANGES` ("v4 resolves the round-3 findings; phase order sound" — remaining items are new, deeper rigor). v5 folds in R4. No code changes until both APPROVE / APPROVE_WITH_NOTES.
**Epic:** COREDEV-2485 · **Ticket:** COREDEV-2489 · **Date:** 2026-07-14
**Source of truth:** `docs/audits/2026-07-14-plugin-audit.md` + `-findings.md`

> **Document order = execution order** (P1b-design → P1a-2 → P1c → P2), **except P1b-5 (keychain), which is a parallel independent PR lane** gated on app evidence so it never stalls Items 6–8. Item IDs are stable across revisions.

## Context — already shipped (do not re-do)

| PR | Ticket | Scope |
|----|--------|-------|
| #24 | COREDEV-2486 | P0 — fleet-wide silent-failure fixes |
| #25 | COREDEV-2487 | P1a — model tiering, 5 skill preloads, agent memory + swift-reviewer memory hotfix `23ca4a1` |
| #26 | COREDEV-2488 | P1b/P2 mechanical |

**Baseline-sync prerequisite (codex r3):** implementation of THIS plan must branch from an integrated baseline that contains the merged PRs #24–#26 (including hotfix `23ca4a1`). Do NOT implement from an ancestor branch that predates the hotfix — assert `memory:` is absent from swift-reviewer and re-run the full gate suite on the *integrated* branch, not on independently-green ancestors. Locked decisions: owner = UnleashedServices; secrets = rotate + scan (no history rewrite).

## Guiding constraints & discovered principles

- **`memory:` auto-enables Read/Write/Edit** (sub-agents docs). **Never add `memory:` to a read-only agent.** CI invariant (item 0): reject `memory:` on any agent that also lists Write/Edit in `disallowedTools`, and treat the 6 review agents (swift-reviewer + the 5 reviewers) as a hardcoded read-only set that must not declare `memory:`.
- **Three distinct context layers — never conflate them (codex r3):**
  1. **Contributor context** = the plugin repo's own `CLAUDE.md` (rewritten in P1b-8). Loaded only for sessions working *in the plugin repo*; **NOT** loaded for installed agents (plugins-reference).
  2. **Consumer-project context** = the *app* repo's `CLAUDE.md`, loaded in a real install. The plugin cannot guarantee its contents.
  3. **Preloaded plugin content** = a `skills:` SKILL.md **body** injected at agent startup (NOT its `references/*.md`).
  A fact removed from an agent body (P1a-1) must be provably covered by **(3) a preloaded SKILL.md body**, kept **in the agent**, or proven present in **(2) the consumer app CLAUDE.md** — **never** by a pointer to **(1) the plugin CLAUDE.md**, which installed agents don't load. **`AGENT_CONTRACTS.md` is the same case (codex R4): it is NOT auto-injected** — a bare link to a §section does not make its content available to an installed agent. Any required contract rule must be retained in the agent, preloaded via a skill body, or read explicitly through `${CLAUDE_PLUGIN_ROOT}/AGENT_CONTRACTS.md`.
- **Never claim an architecture the app doesn't implement** (P1b-5): align a skill to an invariant only after reading the app's real code paths + lifecycle tests.
- **Sub-agent frontmatter is camelCase (`disallowedTools`); skills/commands use kebab `allowed-tools`, a pre-approval grant — skills can't deny tools.**
- **Full gate suite per PR:** `validate-plugin-assembly.py --strict`, `validate-hooks.py --strict --require-manifest`, `validate-version-sync.sh` (strict), `test-hooks.sh`, MCP unittest suite, shellcheck, **actionlint (add to CI — item 14; it is NOT currently run)**, gitleaks, and **`claude plugin validate . --strict`** (item 14).

---

## Item 0 — swift-reviewer memory (FIXED + guard)

Hotfix `23ca4a1` (PR #25) removed `memory:` from swift-reviewer (memory auto-enabled Write/Edit on the read-only orchestrator; codex round-2). **Prerequisite:** implement from a baseline that contains it (see baseline-sync). **Guard:** add the CI invariant above so a read-only agent can never regain write via memory.

## Phase P1b-design — Content-truth (fix first)

4. **grdb-patterns → snake_case SQL columns** + add the deferred `db-engineer → grdb-patterns` preload. *Acceptance:* validate SQL identifiers are snake_case AND `CodingKeys` map camelCase Swift props ↔ snake_case columns (Swift properties stay camelCase — don't grep for "no camelCase"). *Files:* `skills/grdb-patterns/SKILL.md`, `agents/db-engineer.md`. *Risk:* LOW.

5. **keychain-security → align to the invariant.** ⚠️ EVIDENCE GATE · **parallel independent PR lane.** Read the app's real credential paths (Gmail access/refresh tokens; MSAL cache + platform backing; account add/refresh/sign-out/deletion/migration; SQLCipher master key handled *separately* from OAuth creds; test-only in-memory sub). If app uses Keychain → rewrite skill to Keychain, remove the "master key encrypts a credential file" rationale, revalidate accessibility class/access-group/rotation/sign-out/dev-keychain. If any production path uses file/SQLite storage → real **app** security bug; the app migration must land **before** the plugin claims Keychain (not "concurrently"); interim = **remove the unsafe credential-store recipe** and make the skill stop with an app-migration handoff (a warning alone is NOT a fail-closed safe state — codex R4); never preload/publish guidance that normalizes the known violation. Evidence must come from production code paths + lifecycle tests, not docs. OAuth creds stay distinct from the SQLCipher master key. *Risk:* HIGH.

6. **MailProviderError — one canonical shape.** ⚠️ EVIDENCE GATE. **Sources include `skills/error-handling/SKILL.md` (a 4th competing enum, codex r3)**, plus logic-engineer, code-simplifier, tester. Do a **repo-wide `MailProviderError` inventory**, adopt the app's real enum (app source + compiler/tests are authoritative; Context7 can't establish a private enum), and align every site so the tester sample compiles. *Files:* `skills/error-handling/SKILL.md`, `agents/{logic-engineer,code-simplifier,tester}.md`. *Risk:* MEDIUM.

7. **swiftui-mvvm + accessibility-patterns → Curator + correct layout** + add the deferred `ui-engineer → swiftui-mvvm` preload. Confirm the exact Curator token APIs against the app first. *Risk:* LOW-MEDIUM.

8. **Rewrite plugin-repo `CLAUDE.md` → plugin-development instructions** (replacement, not deletion). Contributor-only context (installed agents don't load it). App-dev facts move to preloaded skills / stay in agents (see 3-layer principle). *Risk:* HIGH.

---

## Phase P1a-2 — Context economy (after content is correct)

1. **Strip duplicated content from agent bodies.** Per-agent diff + a **3-column coverage matrix** proving each removed line is covered by (a) a preloaded SKILL.md **body**, (b) retained in the agent, or (c) the **consumer app** CLAUDE.md — **not** the plugin CLAUDE.md. Keep role/workflow/deltas/negative-knowledge guardrails verbatim. **Re-run the matrix after P2-13** (progressive disclosure must not relocate a relied-upon fact out of a preloaded body). *Files:* `agents/*.md`. *Risk:* MEDIUM.

2. **swift-reviewer: inline shell → shipped `scripts/` invocations** (~4-5k tokens/spawn). Verify Step-1/Step-5 resolve; harness + dry-run green. *Risk:* MEDIUM.

3. **Explicit per-agent `maxTurns` on the 2 personas** (documented value + a truncation test using a **deterministic fixture/harness that asserts completion markers**, not a model reproducing an exact checklist — codex R4). Drop the vague `effort: low` from committed scope. *Risk:* LOW-MEDIUM.

---

## Phase P1c — Pipeline wiring

9. **Make the Plan Review Gate executable.** `implement` fail-closed checks for an approved-plan Combined verdict before edits; remove the impossible `/brainstorm` self-invocation (`disable-model-invocation: true` excludes it from the **Skill tool** — current term; commands & skills now share invocation semantics). Fix via user-prerequisite handoff or migrate brainstorm to a model-invocable skill (P2-16, decided here). **Honest enforcement (codex R4):** a skill/command cannot itself be a tool-access boundary — `disable-model-invocation` only controls invocation and `allowed-tools` only pre-approves. So `implement`'s gate is **workflow-level fail-closed** (it declines to proceed); if edits must be *mechanically* impossible pre-approval, add a **PreToolUse hook keyed to the validated approval token**. **Land Item 11 (the approval producer/artifact) BEFORE or ATOMICALLY WITH Item 9** — otherwise `implement` could consume an unbound/stale verdict. *Files:* `commands/implement.md`, `commands/brainstorm.md`, `skills/agent-orchestration/`, (opt.) a PreToolUse guard. *Risk:* MEDIUM.

10. **code-simplifier pre-pass + full registry coverage.** Add all missing agents to the registry (13→21: code-simplifier, ai-engineer, tester, ci-engineer, docs-engineer, release-manager, enterprise-stakeholder, smb-entrepreneur) as a **machine-readable/narrowly-parsed table** (so the set-equality CI check can't miscount prose examples); add the `agents/*.md == registry` set-equality CI check. The **mutating** pre-pass runs only in the implementation/cleanup workflow (never read-only `/pr-review`) or via explicit opt-in. *Files:* `skills/agent-orchestration/SKILL.md`, commands, CI.

11. **Review-gate data plane hardening + approval binding.** The persisted **Combined-verdict artifact** carries: a **versioned schema**, the canonical plan path, a **raw-byte plan digest**, exact reviewer identities + per-reviewer status, transcript digests, and the session/round binding; `implement` validates ALL of these against the *current* plan before any mutation (prevents approve-then-edit). Add **SubagentStop reviewer-schema enforcement** (block/annotate on schema failure) rather than the current observe-only capture. Secure the handoff dir: a private `0700` dir created safely, regular-file/no-symlink checks, restrictive `umask`, atomic writes, cleanup — session-scoping alone doesn't fix the symlink/tamper concern. Add a wall-clock `--timeout` (exit 124) to `pty-capture.py` (this gate hit the 600s wall twice); ship one-shot gemini/codex prompt variants with an explicit `VERDICT:` line (this gate's prompt is the template); add an external-CLI **preflight**; the **waiver is a ⚠️ USER DECISION, not an impl detail (codex R4)** — it changes the mandatory dual-review invariant, so default stays fail-closed and any waiver must be user-authorized, reasoned, time/session-scoped, digest-bound to the plan, and recorded in the approval artifact. *Files:* `skills/{gemini-review,codex-review}/`, `scripts/pty-capture.py`, `AGENT_CONTRACTS.md`. *Risk:* MEDIUM.

12. **Enforcement posture.** ⚠️ USER DECISION.
    - `sensitive-file-guard.sh`: promote `ask` to default. **Execution-mode matrix (required):** interactive/default, `plan`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, and `-p` as a SEPARATE interactive/non-interactive axis — document that `dontAsk`/non-interactive contexts **deny** an operation that would prompt (headless failure mode) + the kill switch.
    - Stop gate: the **only** model-visible Stop mechanism is top-level `{"decision":"block","reason":"…"}` (the `reason` becomes Claude's next instruction when stopping is blocked) — **not** `additionalContext`, which is a PostToolUse/context-injection contract (codex r3). So "make warn model-visible" = promote to `enforce` (block+reason); there is no non-blocking model-visible Stop path. Requires loop guards, continuation cap, `stop_hook_active` coverage, token-cost tests, CHANGELOG. Gate on user confirmation.

---

## Phase P2 — Hardening & progressive disclosure (last)

13. **Skills progressive disclosure** (5 largest skills → short SKILL.md + `references/*.md`). **Constraint:** any fact a P1a-1 deletion relies on stays in the *preloaded SKILL.md body*, not a reference. Re-run the P1a coverage matrix after this.
14. **CI coverage gaps + official/actionlint validation.** Add **`claude plugin validate . --strict`** pinned to **min Claude Code `>=2.1.172`** (nested subagent fan-out was introduced there; schema validation alone can't prove runtime fan-out, so also add an **installed-plugin nested-dispatch smoke test**) — official manifest/skill/command/agent/hook schema check the local validator only partially covers AND a **pinned `actionlint` step** (currently absent from `plugin-ci.yml`). Plus: `py_compile`/smoke for `pty-capture.py`; expected-hooks inventory; reviewer-allowlist cross-check (3 code sites + frontmatter); cross-artifact link checker; **version-sync that parses only the newest CHANGELOG release heading + an explicit current-version marker in AGENT_CONTRACTS** (not every CHANGELOG version); fix the job-summary `job.status`-per-row bug.
15. **`allowed-tools` in skills/commands.** Remove where over-broad; scope where needed. `review-synthesis` already correct (`Read, Grep`) — no change.
16. **Commands → skills migration.** Invocation policy decided in P1c-9; file relocation here. *Acceptance:* new `name` frontmatter; **final asset counts `21 agents / 21 skills / 0 commands / 1 MCP server`** reflected in version-sync + README; cross-ref updates; plugin version + CHANGELOG entry; **all three `/unleashed-mail:*` namespaced invocations resolve unchanged.**
17. **Docs/supply-chain + MCP.** Placeholders-only `.env.example` (gitleaks-covered) + document the `.env` key gmail-api-integration needs; date-stamp modern-standards-planner baked-in knowledge; MCP `finalize_review` + `outputSchema`/annotations **with unit tests** (malformed/stale inputs, outputSchema conformance, annotations); **fix the MCP/reviewer fail-open findings + acceptance tests (codex R4 / audit mcp-server):** nonempty findings with `changed_files: []` must fail closed (currently accepted → non-gating); a `Status: BLOCKED`/`PARTIAL` message with no JSON fence must still persist its `.status` sidecar (COREDEV-2328); remove or actually wire the dead `REPORT_FINDING_TOOL`/`reviewers.py` layer. CODEOWNERS optional.

---

## Remaining audit findings — add or defer-with-ticket (do not claim full coverage)

Not yet folded into a numbered item above; each is either added to the phase noted or explicitly deferred with its own COREDEV ticket (codex R4 / gemini R4):
- **`/pr-review` + `swift-reviewer` run the full `xcodebuild` test suite twice** — dedupe (P1c/Item 16).
- **PostToolUse hook hardening:** the two per-edit hooks have no `timeout` (inherit 600s); `swift-build-verify.sh` is wired to Write|Edit where it's a guaranteed no-op; PreToolUse matches `MultiEdit` but PostToolUse doesn't (asymmetry) — (P2/Item 14).
- **Pre-commit `.githooks/pre-commit` hardening (critic.2 + ci-validators):** BRE-mode email/PII regex is inert; the PII scan filters to `*.swift` (scans nothing in this non-Swift repo); fails open when the checks script is missing; the required `git config core.hooksPath .githooks` install step is documented nowhere user-facing — (P2/Item 14).
- **modern-standards-planner baked-in-knowledge staleness** + README `.env.example`/`.env` key — (Item 17).

## Open decisions for the user

- **P1c-12 (enforcement default):** promote guard `ask` to default? (behaviour change; needs the mode matrix + CHANGELOG) — the one true preference decision.
- **Evidence gates (P1b-5/6/7):** resolved by reading the *app* repo — please confirm I can access it / point me at it.
- **P1b-8:** confirmed → replace the plugin CLAUDE.md.
- **P2-16:** invocation settled in P1c; do the file migration now (recommended) or later.
- **External-review waiver (P1c-11):** may the dual-review gate be waived on a machine/CI without `agy`/`codex`? Default fail-closed; any waiver is user-authorized + recorded.

## Sequencing & PR strategy

**P1b-design → P1a-2 → P1c → P2**, with **P1b-5 as a parallel evidence-gated lane**. Within P1c, **land Item 11 before/atomically with Item 9** (approval producer before consumer). Implement from an integrated baseline containing #24–#26. Each PR green on the full gate suite (incl. `claude plugin validate . --strict` + actionlint) run on the *integrated* branch.

## Plan-review gate log

- **R1** — gemini `REQUEST_CHANGES` (7) → v2; codex `MISSING` (capacity).
- **R2** — gemini `APPROVE`; codex `REQUEST_CHANGES` (8, incl. the swift-reviewer memory regression → fixed as item 0) → v3.
- **R3** — gemini `APPROVE` (semantics/security/sequencing all pass); codex `REQUEST_CHANGES` ("most round-2 concerns resolved") — 6 findings: baseline-sync/memory-still-in-branch, CLAUDE.md context layers, Stop-hook contract (block+reason not additionalContext), 4th MailProviderError source (error-handling skill), approval-digest binding + secure temp dir, actionlint-not-in-CI; + nits (Skill-tool term, P1b-5 lane, 21/21/0/1 counts, machine-readable registry). **All addressed in v4.**
- **R4** — gemini `APPROVE_WITH_NOTES` (notes were mostly already-shipped-#26 false-positives + real completeness gaps: pre-commit hardening, pr-review double-test, MCP cleanup); codex `REQUEST_CHANGES` ("v4 resolves round-3; phase order sound") — new deeper findings: 9/11 producer-before-consumer ordering, honest skill-enforcement, AGENT_CONTRACTS not auto-injected, MCP fail-open + SubagentStop schema, item-5 quarantine-must-remove, min CC >=2.1.172, waiver-is-a-decision, remaining-findings catalog. **All folded into v5.**
- **R5** — _pending — re-gate both on v5._
