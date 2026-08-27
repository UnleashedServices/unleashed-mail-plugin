# COREDEV-2711 §2 — enforcing the spawn allowlist the runtime discards

**Status:** Planning, revision 2 · **Basis:** `2631845` (origin/main) · **Ticket:** COREDEV-2711
**Depends on:** COREDEV-2703 (done — restored `swift-reviewer`'s ability to spawn at all)

> **r1 (frozen `2f6c5e5`): codex and agy both `REQUEST_CHANGES`; kimi `APPROVE_WITH_NOTES` on a round
> the harness VOIDED for a false positive (it ran a Python script and left `__pycache__`, which the
> COREDEV-2607 check reads as a reviewer editing the tree — filed on COREDEV-2650).**
> Three findings were concordant and all three were verified against the tree before acting:
> §2's central example was factually wrong, Rule 2 contradicted §5.2, and §3 never measured the one
> event the design depends on. Revision 2 also corrects two things in the **opposite** direction —
> §1 claimed a protection that does not exist, and §6 recorded an open gap that is already closed.

---

## 1. The problem, stated as a consequence

`swift-reviewer` reads untrusted content — PR diffs, issue text, third-party code. `Agent(type, …)`
in a **sub-agent's** `tools:` grants the Agent tool but the runtime **discards the type list**;
enforcement is scoped to main-thread agents by design. Measured three times across two sessions with
no permission prompt: `swift-reviewer` spawned `ui-engineer`, a writer absent from its own declared
list. So the posture equals an unrestricted bare `Agent` grant, and the PR #63 P1 this was meant to
provide is not in force.

**What this does NOT protect, corrected from revision 1 (codex, r1).** Revision 1 implied
`disallowedTools: Write, Edit, NotebookEdit` stops `swift-reviewer` writing directly. **It does not.**
`agents/swift-reviewer.md:13` grants bare `Bash`, and `AGENT_CONTRACTS.md` §9.1 records
"`swift-reviewer`'s shell is reachable from model-invoked `pr-review`" as a **documented accepted
decision**, raised four times and settled on 2026-08-07. A prompt-injected reviewer can already
mutate the checkout through the shell.

This guard therefore closes **one lateral-movement path** — spawning a second agent that writes — and
is **defense in depth, not a boundary**. Saying otherwise is the same overstatement COREDEV-2711 §1
existed to correct in the frontmatter, and it must not reappear in the plan that replaces it.

## 2. What must NOT be done, and why

**Do not look for a frontmatter shape.** The ticket is explicit and the docs agree: for a sub-agent
the only levers are omitting `Agent` or denying it, both all-or-nothing.

**Do not "deny writer agents".** Revision 1 argued this from an example that was **wrong**: it claimed
`jira-manager` is a writer inside `swift-reviewer`'s allowlist. `agents/jira-manager.md:19` is
`disallowedTools: Write, Edit, NotebookEdit, Bash, Agent, mcp__github` — it is not a writer, and it
cannot spawn either. Revision 1's derivation counted `tools:` and `memory:` and **never subtracted
`disallowedTools`**. Both arms caught it independently. Recomputed with the validator's own
`_live_tools` (granted minus denied): **12 of 21 agents can write** via `Write`/`Edit`/`NotebookEdit`,
and **none of `swift-reviewer`'s six declared callees is among them**.

So the honest position: a writer-blacklist would **not** break the flagship workflow today, and
revision 1's stated reason for rejecting it was false. It is still the wrong predicate, for reasons
that survive:

* **It rots.** "Writer" is a derived property of another agent's frontmatter. Add `Write` to a
  declared callee and the rule silently changes meaning; the declaration does not.
* **It answers the wrong question.** The frontmatter already states who may spawn whom. The defect is
  that nothing enforces it — not that we lack a policy.
* **Counting is contested.** By `Write`/`Edit` the roster is 12; counting `swift-reviewer` itself,
  which writes through bare `Bash` (§1), it is 13. A predicate whose population depends on where you
  draw "writes" is a poor gate.

## 3. What was measured

Three payload facts, all captured with a temporary project-scoped recording hook and a positive
control, then torn down. Artifact: `~/.claude/handoffs/COREDEV-2711-hook-payload-evidence.json`.

| event | `agent_type` (CALLER) | `tool_input.subagent_type` (CALLEE) |
|---|---|---|
| Bash from a sub-agent | `'general-purpose'` (+ `agent_id`) | — |
| Bash from the main thread | absent | — |
| `Agent` from the main thread | absent | `'general-purpose'` |
| **`Agent` from a SUB-AGENT** | **`'general-purpose'`, `agent_id` set** | **`'Explore'`** |
| `Read` from a plugin sub-agent | **`'security-reviewer'` — BARE** | — |

**Row 4 is new in revision 2 and both arms required it.** Revision 1 measured a sub-agent's *Bash*
call and a main-thread *Agent* call, and inferred the combination. That inference is now a
measurement: the exact event the guard reads carries **caller and callee together**.

**Row 5 is new and it constrains the design (codex, r1).** A plugin agent's own identity is reported
**bare**. There is no namespaced runtime form: `subagent_type: 'unleashed-mail:security-reviewer'`
fails with *"Agent type not found"*, and the valid list is flat — plugin agents and project agents
from `.claude/agents/` share one unprefixed namespace. Two consequences:

* the **caller** (`agent_type`) is always bare, so it cannot prove provenance;
* the **callee** is whatever the caller asked for — namespaced or bare, valid or not, because
  PreToolUse fires **before** the type is validated. Both spellings must be normalised.

## 4. The mechanism — enforce what the frontmatter already declares

    caller = agent_type            (absent -> MAIN THREAD)
    callee = tool_input.subagent_type
    both prefix-normalised: strip a leading "<anything>:" before comparing

    1. caller absent                        -> ALLOW   (never block the operator)
    2. caller names no agent this plugin
       defines                              -> ALLOW   (see §5.2 — provenance, not indifference)
    3. caller is a plugin agent whose
       effective tools contain NO Agent      -> DENY    (see below)
    4. caller declares a BARE Agent grant    -> ALLOW   (declares reach over everything)
    5. caller declares Agent(a, b, …)        -> ALLOW iff callee is a member, else DENY

**Rule 3 is inverted from revision 1, and agy is right about why.** Revision 1 said "declares no
Agent grant -> ALLOW (nothing was declared to enforce)". That makes **zero declared authority more
permissive than scoped authority** — an agent granted no spawn capability at all would be unrestricted
if it ever reached the hook. Denying costs nothing: an agent with no `Agent` in its effective tools
should never be issuing an `Agent` call, so the rule is unreachable in a healthy tree and correct in
an unhealthy one.

**Effective tools, not declared `tools:`** — granted minus `disallowedTools`, the same computation
`_live_tools` performs. Revision 1's failure to subtract denials is exactly what produced its wrong
writer roster (§2), and the same mistake here would let a `disallowedTools: Agent` agent pass rule 4.

## 5. The decisions this plan is asking reviewers to rule on

### 5.1 `deny`, against a shipped precedent of never denying

`scripts/sensitive-file-guard.sh:9-10` records the convention: never `deny`, because "the user is
always in the loop". This would be the plugin's first denying hook.

**Both arms ruled for `deny`, and codex corrected the argument.** Revision 1 claimed an `ask` nobody
sees is "a delay before the same outcome". That is wrong — `ask` forces a prompt even in auto mode.
The correct argument is different: **an out-of-roster spawn is a policy violation, not an operation a
possibly-compromised sub-agent should be able to escalate for approval.** Rule 1 keeps the operator
unblocked and `UNLEASHED_SPAWN_GUARD=off` is the kill switch.

### 5.2 Consumer blast radius — the contradiction, resolved

Revision 1 said both "foreign callers are allowed" (rule 2) and "a consumer agent with a scoped grant
would newly be enforced" (§5.2). Both arms caught it; they cannot both be true.

**Resolved in favour of rule 2: only agents this plugin defines are enforced.** The reason is
provenance, measured in §3 row 5 — `agent_type` is bare, so a project agent named `security-reviewer`
is indistinguishable from the plugin's. Enforcing on a bare name would let a consumer's unrelated
agent inherit this plugin's policy, and would let a project agent shadow a plugin one. The plugin can
only speak for frontmatter it ships.

Consequences stated rather than buried: a consumer agent with a scoped grant is **not** enforced;
"record it" in rule 2 must be a **no-op**, because writing state would make foreign calls
non-inert; and an opt-in for consumer enforcement is out of scope here and needs its own ticket.

## 6. Scope

**In scope.** The PreToolUse matcher and `scripts/agent-spawn-guard.sh`; effective-tools computation;
prefix normalisation on both ends; the kill switch; fail-closed on a malformed payload where the
caller is identified; tests with paired mutants.

**Out of scope, corrected from revision 1.**

* **Transitivity is NOT an open gap — revision 1 was wrong.** It recorded `swift-reviewer` →
  `security-reviewer` → a writer as an unclosed path. agy called that an absolute blocker; codex said
  it is already closed; **codex is right and it is verified**: all five specialists resolve to
  `Read, Grep, Glob` and `jira-manager` denies `Agent`, so no declared callee can spawn at all. The
  second hop is stopped by the runtime before any hook runs. Rule 3 now also denies it in principle.
  What remains genuinely open is only that a FUTURE callee granted `Agent` would need its own
  declaration — which rules 3-5 handle by construction.
* **Non-plugin callers** (rule 2), for the provenance reason in §5.2.
* **`swift-reviewer`'s bare `Bash`** (§1) — an accepted residual under AGENT_CONTRACTS §9.1. This
  guard does not close it and does not claim to.
* **`agents/swift-reviewer.md` is not edited.** It is 688 lines and plan citations pin lines in it.
  codex is right that this is bookkeeping rather than a boundary; if implementation shows the file
  must change, the citations move and the pin is not a reason to refuse.

## 7. Verification — and what would make it vacuous

1. **The hook must actually fire.** Feed the recorded §3 payloads to the script directly, AND assert
   `hooks/hooks.json` carries a matcher matching the literal `Agent`.
2. **A deny must be attributable.** A guard that denies everything also passes an "it denied" cell.
   Each case asserts its verdict AND its paired opposite in the same run: `swift-reviewer` →
   `jira-manager` ALLOWED where `swift-reviewer` → `ui-engineer` is DENIED.
3. **The main thread is never denied** — `agent_type` absent must allow a callee that a sub-agent
   would be denied.
4. **Both spellings normalise** — `security-reviewer` and `unleashed-mail:security-reviewer` reach
   the same verdict, in both the caller and callee positions.
5. **Fail-closed only where the caller is identified.** No `agent_type` is the main thread (allow);
   an identified caller with unparseable frontmatter is a refusal.

**Trap 4's claim is withdrawn (codex, r1).** Revision 1 said a runtime that stopped sending
`agent_type` would "fail loudly". It would not: production would read the event as main-thread and
**ALLOW**. Static fixtures cannot detect that. This is a **fail-open on schema change**, stated
plainly, and mitigated only by a startup/CI compatibility probe that asserts a known sub-agent event
still carries `agent_type` — not by any assertion over fixtures.

**One parser, not two (codex, r1).** Revision 1 said the guard "shares `_tool_tokens`". That is not a
design: `_tool_tokens` is Python and the guard is shell, so CI and runtime could read the same
declaration differently. The implementation must either invoke one shared parser from both, or pin a
fixture that both parse and compare — decided at implementation, and named here as a requirement.

## 8. Risks

* **A false deny breaks the flagship workflow** and ships to consumers. Rule 5 enforces a declaration
  rather than a heuristic precisely to bound this.
* **Fail-open on a runtime schema change** (§7). Named, not mitigated by fixtures.
* **The guard is not a boundary** (§1). If it is ever described as one, that is the defect this
  ticket's §1 already fixed once.
* **This plan could become another 29-round gate.** COREDEV-2691 ran nineteen implementation rounds
  and changed zero shipped lines. Governance: score **Q1 = surviving mutants of shipped code**
  separately from **Q2 = defects in the test scaffolding**; continue on Q1 only; ticket Q2; **stop
  after two consecutive rounds with zero Q1 findings.**
