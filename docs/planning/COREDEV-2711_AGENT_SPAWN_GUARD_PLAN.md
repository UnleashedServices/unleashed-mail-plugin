# COREDEV-2711 §2 — enforcing the spawn allowlist the runtime discards

**Status:** Planning, revision 1 · **Basis:** `2631845` (origin/main) · **Ticket:** COREDEV-2711
**Depends on:** COREDEV-2703 (done — restored `swift-reviewer`'s ability to spawn at all)

> COREDEV-2711 §1 (the honesty fix) is done: `agents/swift-reviewer.md` and
> `scripts/validate-plugin-assembly.py:565` now state plainly that the scoped `Agent(...)` grant is a
> declaration of intent, not an enforced control. This plan is §2 — picking a mechanism and building
> it. The ticket recommends a PreToolUse hook and forbids hunting for a frontmatter shape; §3 records
> the measurement that makes the hook viable, which the ticket did not have.

---

## 1. The problem, stated as a consequence

`swift-reviewer` reads untrusted content — PR diffs, issue text, third-party code. Its
`disallowedTools: Write, Edit, NotebookEdit` stops it writing **directly**. Nothing stops it
**spawning something that writes**.

Measured on 2.8.1 and recorded on the ticket, three times across two sessions with no permission
prompt in any case: `swift-reviewer` spawned `unleashed-mail:ui-engineer` — a writer, absent from
its own declared `Agent(...)` list — and a bare probe agent spawned a type outside its allowlist.
The runtime grants the `Agent` tool from the specifier and **discards the type list for a sub-agent**;
the sub-agents reference scopes that enforcement to a *main-thread* agent.

So the posture today equals an unrestricted bare `Agent` grant. The PR #63 P1 this was meant to
provide — stopping a prompt-injected finding from steering the reviewer into a writing agent — **is
not in force**.

## 2. What must NOT be done, and why

**Do not look for a frontmatter shape.** The ticket is explicit and the docs agree: for a sub-agent
the only levers are omitting `Agent` or denying it, both all-or-nothing. `agents/swift-reviewer.md:13`
already carries the corrected comment. Any revision of this plan that proposes a `tools:` or
`disallowedTools:` spelling has misread §1.

**Do not "deny writer agents".** This is the obvious rule and it is wrong. Derived from the shipped
tree, **13 of 21 agents can write** — via `Write`/`Edit` in `tools:`, via `memory:` (which
auto-enables Read/Write/Edit), or by omitting `tools:` entirely and inheriting everything. One of
them is **`jira-manager`**, which omits `tools:` — and `jira-manager` is *inside* `swift-reviewer`'s
declared allowlist, because logging the review is its job. A writer-blocking rule breaks the
flagship workflow on its first run.

That is not a detail to patch around. It is the signal that **"writer" is the wrong predicate**.

## 3. The measurement that makes a hook viable

The ticket recommends a PreToolUse hook but does not establish that a hook can tell **who** is
spawning. Without that, a guard either blocks the operator's own direct spawns or enforces nothing.

The sub-agents reference documents `agent_id`/`agent_type` as base hook fields "when firing in
subagents", but the CLI hooks page shows them only for `SubagentStart`. So it was measured, with a
temporary project-scoped recording hook and a positive control. Evidence retained at
`~/.claude/handoffs/COREDEV-2711-hook-payload-evidence.json`:

| call | `agent_type` (the CALLER) | `tool_input.subagent_type` (the CALLEE) |
|---|---|---|
| Bash from inside a sub-agent | `'general-purpose'`, `agent_id 'a608928f342802ae0'` | — |
| Bash from the main thread | absent | — |
| `Agent` call from the main thread | absent | `'general-purpose'` |

**A PreToolUse hook on `Agent` can therefore read both ends of the spawn.** `agent_type` absent means
the main thread, which must never be blocked.

> A first reading of this data said `agent_type` was absent everywhere. That was a substring match
> over `tool_input` picking up the probe's own commands; only an exact match on the sub-agent's
> command isolated the real record. The corrected reading is the one tabulated above, and the
> verification in §7 re-derives it rather than citing this table.

## 4. The mechanism — enforce what the frontmatter already declares

A PreToolUse hook on `Agent` that enforces **the caller's own declared `Agent(...)` membership**.
Not a writer blacklist; not a hardcoded roster. The frontmatter already says what each agent may
spawn — the runtime simply refuses to enforce it, and this restores that.

    caller = agent_type, prefix-stripped        (absent -> MAIN THREAD)
    callee = tool_input.subagent_type, prefix-stripped

    1. caller absent                       -> ALLOW    (never block the operator)
    2. caller is not a plugin agent        -> ALLOW    (not ours to police; record it)
    3. caller declares no Agent grant      -> ALLOW    (nothing was declared to enforce)
    4. caller declares a BARE Agent grant  -> ALLOW    (declares reach over everything)
    5. caller declares Agent(a, b, …)      -> ALLOW iff callee is a member, else DENY

Rule 5 is the whole control. `jira-manager` passes because `swift-reviewer` **declares** it;
`ui-engineer` is denied because it does not. The rule needs no knowledge of who writes, so it cannot
rot when an agent's tools change — and the existing advisory check at
`scripts/validate-plugin-assembly.py:565` already keeps a *writer* out of any declared list, so the
two compose: the validator keeps the declaration honest, the hook makes it real.

Both spellings of every name must be accepted — `security-reviewer` and
`unleashed-mail:security-reviewer` — because the declared list contains both and `agent_type` may
arrive either way. `SubagentStart`'s existing matcher in `hooks/hooks.json` already handles that
with `(unleashed-mail:)?`, which is the precedent to follow.

## 5. The two decisions this plan is asking reviewers to rule on

### 5.1 `deny`, against a shipped precedent of never denying

`scripts/sensitive-file-guard.sh:9-10` states the convention: it "NEVER emits
permissionDecision:\"allow\" … and never \"deny\" — the user is always in the loop." This guard would
be the plugin's **first denying hook**, and that deserves an explicit ruling rather than a quiet
precedent break.

The argument for `deny` over `ask`: **the threat model is an unattended sub-agent.** `swift-reviewer`
runs a five-specialist panel over untrusted content, and the injection this exists to stop happens
while nobody is watching the sub-agent's prompts. An `ask` that nobody sees is not a control — it is
a delay before the same outcome. The precedent's own justification ("the user is always in the loop")
is exactly the premise that does not hold here.

Mitigations that keep the operator sovereign: rule 1 never touches the main thread, and a kill
switch (`UNLEASHED_SPAWN_GUARD=off`) mirrors `sensitive-file-guard`'s.

### 5.2 The hook ships to every consumer

`hooks/hooks.json` is a plugin asset. This hook will fire in the UnleashedMail app repo and in any
other install — not only here. Rules 2-4 mean it is inert for every agent that does not declare a
scoped grant, and **`swift-reviewer` is the only agent in the plugin that does**. So the blast radius
is intended to be exactly one agent. Reviewers should check that claim rather than accept it: a
consumer defining its own agent with a scoped grant would newly be enforced, which is arguably
correct but is a behaviour change they did not ask for.

## 6. Scope

**In scope.** The PreToolUse matcher and `scripts/agent-spawn-guard.sh`; the frontmatter parse
(shared with the validator's existing `_tool_tokens` model, which is already parenthesis-aware after
COREDEV-2703); both name spellings; the kill switch; fail-closed behaviour on a malformed payload;
tests with paired mutants.

**Out of scope, stated so it is not mistaken for an oversight.**

* **Transitivity.** `swift-reviewer` -> `security-reviewer` -> a writer is not stopped: the second
  hop's caller is `security-reviewer`, which declares no `Agent` grant, so rule 3 allows it. Closing
  it means denying `Agent` to every specialist, which is a separate decision with its own blast
  radius. **Recorded, not fixed** — and the plan must not claim depth it does not have.
* **Non-plugin callers** (rule 2). A `general-purpose` agent can spawn anything. The plugin cannot
  police agents it does not define.
* **`agents/swift-reviewer.md` is not edited.** The ticket pins it at **688 lines** — plan citations
  and the §13 scope anchor reference lines in that file. Verified: it is 688 today.

## 7. Verification — and what would make it vacuous

Every cell pairs with a mutant that reddens it. The specific traps this material invites:

1. **The hook must actually fire.** A matcher typo yields a guard that never runs and a suite that
   passes. The harness feeds the recorded payloads from §3 to the script directly *and* asserts the
   `hooks/hooks.json` matcher matches the literal string `Agent`.
2. **A deny must be attributable.** Asserting "denied" is not enough — a guard that denies
   *everything* also passes. Each cell asserts the decision AND that the paired allow-case is
   allowed: `swift-reviewer` -> `jira-manager` must be ALLOWED in the same run where
   `swift-reviewer` -> `ui-engineer` is DENIED.
3. **The main thread must never be denied.** A payload with `agent_type` absent must allow, for a
   callee that would be denied from a sub-agent. This is the cell that fails if rule 1 is dropped.
4. **Re-derive §3 rather than cite it.** A cell asserts the field names the guard depends on
   (`agent_type`, `tool_input.subagent_type`) are the ones the recorded payloads actually carry, so
   a runtime rename fails here rather than silently disabling the guard.
5. **Fail-closed on malformed input**, but only where the caller is identified: no `agent_type` is
   the main thread (allow), whereas an `agent_type` present with an unparseable frontmatter is a
   refusal.

Plus the standing local gate (CLAUDE.md's thirteen commands), and `bash -n`/`zsh -n` and shellcheck
on the new script.

## 8. Risks

* **A false deny breaks the flagship workflow**, and it ships to consumers. This is the dominant
  risk and it is why rule 5 enforces a declaration rather than a heuristic.
* **The guard is a plugin-level control over a runtime behaviour that may change.** If a future
  release enforces the specifier itself, this becomes redundant but not harmful. If a release stops
  sending `agent_type`, trap 4 fails loudly rather than the guard going quietly inert.
* **`deny` is a precedent break** (§5.1) and may be overruled. If it is, `ask` plus a
  `PermissionDenied`-logged record is the fallback, and the plan should say so rather than pretend
  the control is equivalent.
* **This plan could become another 29-round gate.** COREDEV-2691 ran nineteen implementation rounds
  and changed zero shipped lines. Governance, adopted here: score **Q1 = surviving mutants of
  shipped code** separately from **Q2 = defects in the test scaffolding**; continue on Q1 only;
  ticket Q2 rather than fixing it in flight; **stop after two consecutive rounds with zero Q1
  findings.** Applied retroactively to COREDEV-2691 that rule fires at round 10.
