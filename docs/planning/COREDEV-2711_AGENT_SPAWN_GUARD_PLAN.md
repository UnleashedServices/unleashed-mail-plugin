# COREDEV-2711 §2 — enforcing the spawn allowlist the runtime discards

**Status:** Planning, revision 6 · **Basis:** `2631845` (origin/main) · **Ticket:** COREDEV-2711
**Depends on:** COREDEV-2703 (done) · **Blocks on:** one unmeasured fact, §3a
**Found while writing this:** **COREDEV-2768** — stale user-scope agents shadow this plugin's
read-only reviewers with unrestricted copies, and real runs have used them.

> **r1** `2f6c5e5`: codex + agy `REQUEST_CHANGES`, kimi voided (false `__pycache__` positive).
> **r2** `710917d`: all three `REQUEST_CHANGES` — a privilege escalation revision 2 introduced.
> **r3** `1d9661a`: codex + kimi `REQUEST_CHANGES`, agy `APPROVE`.
> **r4** `9779436`: agy + kimi `APPROVE_WITH_NOTES`, codex `REQUEST_CHANGES` — three narrow findings,
> all verified against the tree and all fixed in revision 5. The findings have stopped being
> architectural.
> **r5** `9148a99`: agy `APPROVE`, kimi `APPROVE_WITH_NOTES`, codex `REQUEST_CHANGES` — two predicate
> gaps, both verified, both closed in revision 6. codex states the design is "otherwise sound" and
> that §3a is "honest, sufficient, and correctly blocking".
>
> **Revision 4 exists because r3 exposed that revision 3's central measurement was of the wrong
> thing.** §3 concluded "a plugin agent's identity is reported BARE". It was captured in a session
> where **the plugin's agents were not loaded at all**, so what it measured were the user-scope
> shadow files. That one sentence was the premise of rule 3, of §5.2, and of the entire
> collision-scan design — all of which revision 4 deletes.

---

## 1. The problem, and what this guard does not do

`Agent(type, …)` in a **sub-agent's** `tools:` grants the Agent tool but the runtime **discards the
type list** — enforcement is scoped to main-thread agents by design. `swift-reviewer` reads untrusted
PR content and can spawn agents it never declared.

**Three things this guard does not do, stated here rather than discovered later:**

* **It is not a write boundary.** `agents/swift-reviewer.md:13` grants bare `Bash`, and
  `AGENT_CONTRACTS.md` §9.1 records that shell as a **documented accepted decision**. A
  prompt-injected reviewer can already mutate the checkout. This closes one lateral-movement path.
* **It is INERT for any caller reaching the hook under a bare name** (§4 P2). That is the price of
  keying on an attested principal, and on the author's machine today — with fourteen user-scope
  shadows present (COREDEV-2768) — it is a large fraction of real invocations. Single-cell testable,
  and carried in §8 as a risk rather than buried.
* **It does not fix COREDEV-2768.** Those shadows are a separate, larger control failure. This guard
  would not have caught them and does not remove them.

## 2. What must NOT be done, and why

**Do not look for a frontmatter shape.** For a sub-agent the only levers are omitting `Agent` or
denying it — both all-or-nothing.

**Do not "deny writer agents".** Revision 1 argued this from a false example: `jira-manager` is not a
writer — `agents/jira-manager.md:19` denies Write, Edit, NotebookEdit, Bash *and* Agent. Recomputed
with `_live_tools`: **12 of 21 can write**, none among `swift-reviewer`'s declared callees. So a
blacklist would not break the workflow today and revision 1's stated reason was wrong.

It is still the wrong predicate, for a reason that survives (codex, r2): **a blacklist enforces a
capability class, while the declared policy is an exact caller→callee relation.** A blacklist would
also permit spawning any non-writing agent never declared. Drift is a secondary cost, not the case.

## 3. What was measured — and the correction that forced revision 4

**Revision 3's §3 measured the wrong agents.** Re-run while writing this: spawning
`unleashed-mail:tester` — a **plugin-only** agent with no user-scope copy — fails with *"Agent type
not found"*, and the runtime's available list contains **no `unleashed-mail:` names and none of the
seven plugin-only agents** (`tester`, `ai-engineer`, `code-simplifier`, `release-manager`,
`prompt-review`, `ci-engineer`, `docs-engineer`). The plugin is *enabled*
(`~/.claude/settings.json` → `unleashed-mail@npranson-unleashed-mail-plugin: true`) and installed at
2.8.2 with live `.in_use` markers, yet **its agents do not resolve in this session**.

So every revision-3 row about "a plugin agent" measured a **user-scope shadow**, and the committed
fixture encodes that error.

| row | claim | status |
|---|---|---|
| Bash from a sub-agent / main thread | `agent_type` present / absent | **stands** (built-ins) |
| `Agent` from a sub-agent | caller and callee both present | **stands** |
| "a plugin agent's identity is BARE" | — | **WITHDRAWN — measured a shadow** |
| "`unleashed-mail:…` is not a valid type" | — | **WITHDRAWN — plugin not loaded** |
| `swift-reviewer → security-reviewer` "production shape" | — | **WITHDRAWN — both shadows** |

### 3a. THE BLOCKING MEASUREMENT — not taken, and not takeable in this session

**All of §4 turns on one fact: the exact `agent_type` a PLUGIN sub-agent reports to PreToolUse.**
The indirect evidence says **scoped** (`unleashed-mail:<name>`):

* the runtime's persisted subagent metadata records `agentType` as `unleashed-mail:swift-reviewer`
  ×68 and `unleashed-mail:security-reviewer` ×36 — bare only for the mis-measured probes;
* plugin-only agents appear in the registry **scoped-only, never bare**;
* `scripts/capture-reviewer-round-start.sh` is a **live SubagentStart hook that strips
  `unleashed-mail:` from `agent_type`** and works; its own comment (COREDEV-2486 audit) states that
  plugin sub-agents surface scoped;
* `hooks/hooks.json` ships `(unleashed-mail:)?(…)` matchers for exactly this reason.

**None of that is the measurement.** Every item is one step removed, and the only *directly* observed
PreToolUse `agent_type` in this family is **bare** — the mis-measured probe. This plan has been wrong
twice by inferring runtime semantics; it will not be wrong a third time.

**Required before implementation:** in a session where the plugin is **proved loaded** (a
plugin-only name such as `unleashed-mail:tester` resolves), spawn the plugin's `swift-reviewer`, have
it make one `Agent` call, and record `agent_type` verbatim.

**Design the measurement as ONE complete positive-control event (codex, r4)**, not four separate
readings: prove a plugin-only name resolves, spawn the scoped `swift-reviewer`, have it invoke a
DECLARED scoped callee, and correlate its `PreToolUse` with a successful `PostToolUse` by
`tool_use_id`. That single event establishes the caller spelling, the prefix form, a non-empty
`agent_id`, and scoped-callee viability at once — and the correlation supplies the OUTCOME the
withdrawn fixture lacked.

**THE FORK, stated now.** If that string is **scoped**, §4 holds. If it is **bare**, the principal is
unattestable and this design is dead; the honest alternatives are then (a) remove `Agent` from
`swift-reviewer` and have the main thread fan the panel out, or (b) restructure so the reader of
untrusted content is not the spawner. **Do not implement §4 until this is measured.**

**Also unmeasured, and not to be hardcoded:** the prefix *form*. Observed data says two-part
`<plugin>:<agent>`; the hooks documentation gives **both** a two-part matcher example and a
three-part `plugin:<plugin>:<agent>` prose form on the same page. Derive the plugin name from
`$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`, pin the separator by measurement, and fail a cell
if the observed form changes.

## 4. The mechanism — two fields, and an attested principal

    us          := plugin name from $CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json  (never hardcoded)
    is_subagent := agent_id present and non-empty        # NOT agent_type
    principal   := agent_type                            # meaningful only when is_subagent
    callee      := tool_input.subagent_type              # compared VERBATIM, never normalised

    P0  agent_id absent               -> ALLOW, no state.  MAIN THREAD — INCLUDING `claude --agent X`
                                         and settings.json {"agent": X}, which set agent_type with
                                         NO agent_id.
    P1  is_subagent, agent_type absent -> ALLOW + diagnostic.   (judgment call — see below)
    P2  agent_type lacks the exact prefix "<us>:" -> ALLOW, no state.  NOT OUR PRINCIPAL.
    P3  "<us>:<name>", agents/<name>.md absent    -> DENY + diagnostic.
    P4  "<us>:<name>", agents/<name>.md ships     -> ENFORCE:
          4'  no `Agent` and no `Agent(...)` token in _live_tools(<name>)  -> DENY
          5'  a token exactly `Agent`                                      -> ALLOW
          6'  tokens matching `Agent(...)` -> ALLOW iff the callee matches a declared member
              VERBATIM **and** begins "<us>:", else DENY

**`agent_id`, not `agent_type`, decides main-thread (codex, r3).** Revision 3 said "`agent_type`
absent = main thread". The compiled 2.1.247 schema documents `agent_id` as *"Present only when the
hook fires from within a subagent… Absent for the main thread, **even in `--agent` sessions**"*,
while `agent_type` is present for a subagent **or** a `--agent` main thread. Revision 3 would
therefore have **denied the operator's own `claude --agent swift-reviewer` session** — violating its
own first rule.

**RULE 3 AND THE COLLISION SCAN ARE DELETED, not narrowed.** A scoped principal cannot be shadowed,
because project, user, CLI and managed agents register **bare**. The unenumerable-source problem —
`--agents` inline JSON invisible to any filesystem scan, managed settings, undocumented
same-directory tie-breaks, `cwd`-relative nested roots — never arises. Revision 3's "maintained root
list" goes with it, along with a §7 cell that compared a constant to a copy of itself.

**Rule 6' accepts ONLY the scoped callee spelling, and this reverses revision 3's §6.**
`agents/swift-reviewer.md:13` declares both spellings and its Step 2 dispatches **bare** names —
which, per COREDEV-2768, resolve to unrestricted user-scope copies. The companion edit is therefore
mandatory: **drop the bare spellings from line 13 and make Step 2 spawn scoped names.** Revision 3's
"do not edit `swift-reviewer.md`, it is pinned at 688 lines" is withdrawn — codex was right that a
citation pin is bookkeeping, not a boundary.

**P3 DENIES, and revision 4 had the polarity wrong (codex, r4).** An exact `<us>:` prefix IS the
attestation that the caller is ours. If the matching asset is then missing, that is corruption,
version skew, or an identifier this build does not understand — **not** a foreign caller. Revision 4
ALLOWed it, which contradicted §7's own "fail-closed where the caller is identified and ours". P2
remains the foreign-caller ALLOW, and the two are paired in §7 so neither can drift into the other.

**P1 is a judgment call, recorded as one.** A sub-agent with no `agent_type` should on a strict
reading fail closed. It ALLOWs because (i) the compiled schema makes it unreachable, so DENY buys
nothing today while adding a way to break every consumer on a schema change; (ii) the payload is
built by the runtime, not the model, so a prompt-injected sub-agent cannot suppress its own
`agent_type` — there is no attacker control to fail closed against; (iii) DENY would contradict P2,
whose premise is "cannot be shown to be ours → allow".

**ONE PARSER, AND PARSE FAILURE IS ITS OWN STATE (codex, r4).** Revision 4 dropped revision 3's
single-parser requirement during the rewrite — an accidental deletion, restored here. Enforcement
reproduces Python `_tool_tokens`/`_live_tools` semantics inside a shell hook, so the two must either
share one parser or be pinned by an equivalence gate over a committed corpus; otherwise CI and the
runtime can read the same declaration differently.

**And `hook_str` fails open by design.** `scripts/lib/hook-io.sh:189` states it "return[s] empty
(fail-open) when neither exists" — so malformed JSON, or a box with neither `jq` nor `python3`, is
**indistinguishable from an absent field**. Under revision 4, P0 would then read a corrupt payload as
"main thread" and ALLOW. Therefore:

* **P0 means `agent_id` absent from a SUCCESSFULLY PARSED object** — never "the extractor returned
  empty";
* **parse failure is a distinct outcome**, and because the caller cannot be identified at all it
  ALLOWs like P2 but emits a diagnostic naming the parse failure — silence here would make the guard
  inert on a broken box with nothing to show for it;
**THE PERMISSION GRAMMAR, DEFINED (codex, r5).** Revision 5 said the plan "must also define" these
and then did not — a requirement stated as if it were a decision. Both cases are measured:

* **`Agent(*)` — and `(**)`, `(/**)`, `(/*)`, `(**/*)` — is FULL BREADTH, not a member named `*`.**
  `validate-plugin-assembly.py:714-718` already models it that way in as many words: "a full-breadth
  scope is the bare grant by another spelling". Under a naive 6' it would parse as a one-member list
  and **deny every real callee**. So a full-breadth scope takes **rule 5' (ALLOW)**, exactly as a
  bare `Agent` does, and the guard must not invent a stricter reading than the validator's.
* **A bare `Agent` in `disallowedTools` removes the tool entirely -> rule 4' DENY.** `_live_tools`
  subtracts EXACT tokens, so measured: `tools: Agent(a, b)` with `disallowedTools: Agent` yields
  `['Agent(a, b)', 'Read']` — **the scoped token survives the denial**. Taking `_live_tools`'s output
  at face value would enforce an agent that has no `Agent` tool at all. The guard therefore checks
  the denial set for a bare `Agent` FIRST, and treats it as removing every `Agent`-family token.
  (`jira-manager` is exactly this shape today.)
* **Unparseable frontmatter on an identified caller DENIES**, per §7.

**SCHEMA-INVALID IS NOT ABSENT (codex, r5).** `is_subagent` requires a present, non-empty `agent_id`,
but revision 5's P0 covered only *absence* — so a successfully parsed object carrying
`agent_id: ""`, `null`, or a non-string matched **no rule at all**. Same for a malformed
`agent_type`. This is distinct from malformed JSON. Such a payload **ALLOWs with a diagnostic**,
consistent with P1/P2: the field is present but unusable, so attribution is impossible, and denying
on a shape the runtime is not documented to emit would turn a schema change into a global outage.

**Effective tools, token-shape-aware.** `_tool_tokens` keeps parentheses intact, so
`_live_tools(swift-reviewer)` contains `Agent(security-reviewer, …)` and **not** a bare `Agent` —
`validate-plugin-assembly.py:625` documents this trap. Revision 3's rule 4 taken literally would have
**denied `swift-reviewer` itself**. Hence 4'/5'/6' test token *shape*, not plain membership.

## 5. Decisions

### 5.1 `deny`, against a precedent of never denying
`scripts/sensitive-file-guard.sh:9-10` records the convention: never `deny`. This is the plugin's
first denying hook. All three arms ruled for `deny` — an out-of-roster spawn is a policy violation,
not something a possibly-compromised sub-agent should escalate for approval. P0 keeps the operator
unblocked; `UNLEASHED_SPAWN_GUARD=off` is the kill switch. **`scripts/lib/hook-io.sh` has no `deny`
emitter today** — only `ask` (:169) and a warn no-op (:172) — so one must be added.

### 5.2 Consumer blast radius — now trivial
Revision 3 needed three outcomes and a collision scan. With an attested principal there are two: the
caller is ours (scoped) or it is not (P2 → ALLOW, no state). Consumer agents register bare and are
never enforced. The contradiction r2 found is gone rather than papered over.

## 6. Scope

**In scope.** The PreToolUse matcher; `scripts/agent-spawn-guard.sh`; plugin-name derivation from
`CLAUDE_PLUGIN_ROOT`; the two-field predicate; token-shape-aware effective tools; the shared parser or
equivalence gate; the `deny` emitter in `hook-io.sh`; the compatibility probe; tests.

**The companion documentation edits are wider than revision 4 said (codex, r4), because shipped
source-of-truth text still asserts the WITHDRAWN result:**

* `agents/swift-reviewer.md:14-17` — "a probe sees its own `Agent` entry BARE, so nothing exists to
  enforce against". That was the mis-measurement (§3). It ships today.
* `AGENT_CONTRACTS.md:404` — "WHAT DOES NOT BOUND THE SPAWN SET … measured".
* `agents/swift-reviewer.md` **every dispatch path**, not just Step 2's labels — including the
  `jira-manager` call and any recovery path.
* `scripts/tests/test_validate_plugin_assembly.py:912` — `assertIn(reviewer, scoped[0])` is a
  **substring test over the whole grant string**, so `"security-reviewer"` matches inside
  `"unleashed-mail:security-reviewer"`. When the bare spellings are dropped it will keep passing
  while asserting a property that no longer holds. It must compare PARSED members, not substrings.

**Out of scope.** COREDEV-2768's shadows (separate, larger); `swift-reviewer`'s bare `Bash` (§9.1
accepted residual); transitivity — the five specialists resolve to `Read, Grep, Glob` and cannot
spawn, and rule 4' denies it in principle anyway.

## 7. Verification

1. **The hook fires** — feed recorded payloads to the script; assert `hooks/hooks.json` matches the
   literal `Agent`.
2. **Deny is attributable** — every deny cell pairs with an allow in the same run: a declared scoped
   callee ALLOWs where an undeclared one DENIEs.
3. **The main thread is never denied**, including a `--agent` session — `agent_type` present,
   `agent_id` absent, must ALLOW. **This is the cell that fails against revision 3.**
4. **Escalation** — `malicious-plugin:security-reviewer` DENIEs; the declared scoped spelling ALLOWs.
   Stated as an escalation test so no one reintroduces normalisation.
5. **Bare callees DENY** even for a declared member, paired against the scoped spelling ALLOWing.
6. **`swift-reviewer` is not denied by rule 4'** — the token-shape regression revision 3 would have
   failed.
7. **The compatibility probe asserts two things**: a known sub-agent event still carries `agent_id`,
   and a plugin sub-agent's `agent_type` is still scoped in the measured form. A schema change fails
   loudly rather than turning the guard silently inert.
8. **Fail-closed only where the caller is identified and ours.**

**The fixture must be rebuilt (§3); the r3 one is not evidence.** Capture it with the plugin **proved
loaded**, commit the registry listing from capture time as that proof, retain `cwd` (structural),
hash **the committed artifact** rather than an uncommitted raw, and record **outcomes** by registering
`PostToolUse`/`PostToolUseFailure` on `Agent` and correlating by `tool_use_id`. It must contain the
two events this ticket exists for and currently lacks: a plugin sub-agent spawning a **declared**
scoped callee, and one spawning an **undeclared** callee.

## 8. Risks

* **Inert for bare-name callers** (§1). Honest, testable, and strictly better than revision 3 — which
  was a no-op in production *and* would have denied both the operator's `--agent` session and
  `swift-reviewer`'s own panel.
* **§3a is unmeasured and blocking.** If `agent_type` is bare for plugin sub-agents this design is
  dead, and §3a names the two alternatives.
* **The prefix form is documented two ways.** Derive it, pin it by measurement, fail loudly on change.
* **Not a boundary** (§1). If it is ever described as one, that is the defect COREDEV-2711 §1 already
  fixed once in the frontmatter.
* **ATTESTOR LIVENESS — the next blind-spot class (codex, r4).** If the plugin or its hook is not
  loaded, an in-plugin compatibility probe **cannot announce its own absence**. That is precisely the
  family that invalidated revision 3: the evidence looked fine because the thing that would have
  contradicted it was not running. §7's probe must therefore be executed INDEPENDENTLY of the plugin
  — a release check or smoke test that proves registry presence, hook registration, hook firing, and
  a successful scoped outcome. A self-check that cannot observe its own non-existence is not a check.
* **Governance.** Q1 = surviving mutants of shipped code, Q2 = scaffolding defects; continue on Q1
  only; ticket Q2; stop after two consecutive zero-Q1 rounds.
