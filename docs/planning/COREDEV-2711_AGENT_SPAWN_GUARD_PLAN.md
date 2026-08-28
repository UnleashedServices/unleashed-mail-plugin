# COREDEV-2711 §2 — enforcing the spawn allowlist the runtime discards

**Status:** Planning, revision 16 — **§3a MEASURED, FIXTURE COMPLETE** · **Basis:** `2631845` · **Ticket:** COREDEV-2711
**Depends on:** COREDEV-2703 (done), COREDEV-2769 (done — it was the blocker) · **Blocks on:** nothing measurable
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
> **r6** `5f60f75`: agy `APPROVE`, kimi `APPROVE_WITH_NOTES`, codex `REQUEST_CHANGES` — ONE finding,
> and codex and kimi found it independently in the same paragraph pair: the permission grammar closed
> over a bare `Agent` denial but not the scoped `Agent(x)` family, while the restored ONE PARSER
> requirement demanded the very `_live_tools` equivalence that rule requires departing from. Both
> verified against the tree; closed here. Every other r6 item is an amendment, not a redesign — codex
> calls the finding "not a new architectural objection", kimi "none of these are architectural".
> **r7** `2b64191`: agy `APPROVE` ("zero design findings remain"), kimi `APPROVE_WITH_NOTES` ("no
> design finding remains"), codex `REQUEST_CHANGES` — ONE finding, again found independently by two
> arms: revision 7's own §7.10 cell contradicted the shipped tree AND pressured a capability
> escalation. Closed here. Both arms ruled the denial closure, the parser rescoping and the
> reachability posture sound, and confirmed no third denial spelling exists.
> **Revision 8 was also swept adversarially BEFORE going to the arms** — five lenses (cross-section
> contradiction, capability escalation, citation accuracy, reproduced measurements, cell
> discrimination), each finding then handed to a refuter instructed to reject it. 25 raised, 15
> refuted, 10 survived, collapsing to four: the missing grant-axis cell (§7.9), the writer miscount
> (§2), the P2/P3 pair §4 promised and §7 never contained (§7.8), and a false attribution to §8 (§6).
> Every one is the same class the review rounds keep finding — a rule moved and the cell beside it
> did not — which is why the sweep now runs before the reviewers do.
> **r8** `370714c`: **only ONE of the three arms was admissible.** codex `REQUEST_CHANGES` — two
> DESIGN findings (revision 8's §7.13 required P0 to emit a diagnostic while §4's P0 row says
> `ALLOW, no state`, not both satisfiable; and §7.13 dropped the malformed/non-string `agent_type`
> that §4 covers) plus one NOTE (its claim that these outcomes shipped with "zero" cells was false
> for P0 — §7.3 was already one). All three are closed here. **The agy and kimi arms were both VOID**
> on the identical signature: each reviewer imported a repo module to REPRODUCE this plan's measured
> claims, CPython wrote `scripts/__pycache__/*.pyc`, and each harness's disposable-checkout
> fingerprint read that bytecode as reviewer tampering. That is COREDEV-2650 — the same false
> positive voided kimi at r1 — fixed in the same push by suppressing the artefact at source rather
> than by excluding a path from the fingerprint. The void kimi transcript had reached the P0 finding
> independently, which is corroboration but not evidence; the void agy transcript had certified the
> contradiction as *consistent*, which is why a voided arm is not quotable in either direction.
>
> **r9/r10** `d9f0d19`: unanimous `APPROVE` on all three admissible arms, r10 a reproduction on
> byte-identical input — six admissible approvals. **r11** `09f7719` (revision 10): agy + kimi
> `APPROVE`; **the codex arm was not run for that round.**
> **THEN §3a WAS MEASURED** (2026-08-27, revision 11). COREDEV-2769 turned out to be a *session*
> property, not a machine one: a Claude Code restart made the plugin's agents resolve, and the
> measurement took minutes. **`agent_type` for a plugin sub-agent at PreToolUse is SCOPED.** The fork
> is resolved in §4's favour. Eleven rounds of design review rested on a string nobody had read.
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
with `_live_tools` over `agents/*.md`: **13 of 21 can write** — the roster the validator computes
rather than a number anyone keeps — and none of the thirteen is among `swift-reviewer`'s declared
callees. So a blacklist would not break the workflow today and revision 1's stated reason was wrong.
(Revision 7 said **twelve**, and so does `validate-plugin-assembly.py:581` in prose beside the
computed roster. The single uncounted writer is **`swift-reviewer` itself**, which writes via its bare
`Bash` — §9.1's accepted residual — and so satisfies neither half of `:581`'s stated predicate,
"hold `Write`/`Edit` or inherit everything". `modern-standards-planner` is NOT a second cause:
it omits `tools:`, inherits everything, and is therefore already inside that twelve. Revision 9 named
both and made the arithmetic 12+2=14; the correction is 12+1=13. Neither changes the argument — this
is the plan citing a count it had not re-derived, twice.)

It is still the wrong predicate, for a reason that survives (codex, r2): **a blacklist enforces a
capability class, while the declared policy is an exact caller→callee relation.** A blacklist would
also permit spawning any non-writing agent never declared. Drift is a secondary cost, not the case.

## 3. What was measured — and the correction that forced revision 4

**Revision 3's §3 measured the wrong agents, and the reason is now understood.** When revision 4 was
written, spawning `unleashed-mail:tester` — a **plugin-only** agent with no user-scope copy — failed
with *"Agent type not found"*, and the runtime's available list contained **no `unleashed-mail:`
names**, though the plugin was enabled and installed at 2.8.2 with live `.in_use` markers. So every
revision-3 row about "a plugin agent" measured a **user-scope shadow**, and the committed fixture
encodes that error.

**That state was a SESSION property, not a machine one (COREDEV-2769, resolved 2026-08-27).** A
Claude Code restart made all 21 plugin-scoped names resolve, with no configuration change. This plan
said for six revisions that the measurement "cannot be taken on this machine"; that was wrong, and
the wording sent the reader after a hardware problem that never existed. **The hazard that remains is
the one worth carrying: the state is SILENT.** Nothing announces that a session lacks the plugin's
agents — bare names keep working by resolving to COREDEV-2768's shadows, so a probe returns
plausible data about the wrong asset. That is precisely how revision 3's central measurement was
invalidated. Hence §7's standing requirement to commit the registry listing from capture time.

| row | claim | status |
|---|---|---|
| Bash from a sub-agent / main thread | `agent_type` present / absent | **stands** (built-ins) |
| `Agent` from a sub-agent | caller and callee both present | **stands** |
| "a plugin agent's identity is BARE" | — | **WITHDRAWN — measured a shadow**, and now **DISPROVED**: it is scoped (§3a) |
| "`unleashed-mail:…` is not a valid type" | — | **WITHDRAWN — plugin not loaded**, and now **DISPROVED**: it resolves and spawns |
| `swift-reviewer → security-reviewer` "production shape" | — | **WITHDRAWN — both shadows**; re-measured for real in §3a |

### 3a. THE BLOCKING MEASUREMENT — **TAKEN, 2026-08-27. The fork resolved SCOPED.**

**All of §4 turns on one fact: the exact `agent_type` a PLUGIN sub-agent reports to PreToolUse.**
The indirect evidence says **scoped** (`unleashed-mail:<name>`):

* the runtime's persisted subagent metadata records `agentType` as `unleashed-mail:swift-reviewer`
  ×68 and `unleashed-mail:security-reviewer` ×36. The bare records in that store are NOT only the
  mis-measured probes — real review runs that resolved to COREDEV-2768's shadows wrote bare
  spellings too, which is what §1 and the header already say. The evidential force is unchanged and
  is in the correlation, not the absence: **spawns that resolved to the PLUGIN's assets are recorded
  scoped**, and bare records track shadow resolution;
* plugin-only agents appear in the registry **scoped-only, never bare**;
* `scripts/capture-reviewer-round-start.sh` is a **live SubagentStart hook that strips
  `unleashed-mail:` from `agent_type`** and works; its own comment (COREDEV-2486 audit) states that
  plugin sub-agents surface scoped;
* `hooks/hooks.json` ships `(unleashed-mail:)?(…)` matchers for exactly this reason.

**None of that was the measurement.** Every item was one step removed, and the only *directly*
observed PreToolUse `agent_type` in this family was **bare** — the mis-measured probe. The plan
refused to infer a third time. It no longer has to.

**THE RESULT.**

    a PLUGIN sub-agent's agent_type at PreToolUse  ->  "unleashed-mail:swift-reviewer"
                                                       SCOPED, 2-part <plugin>:<agent>

Captured 2026-08-27 against plugin 2.8.2, plan HEAD `09f7719`, in a session where
`unleashed-mail:tester` — the plugin-ONLY name with no user-scope shadow — resolved and returned
correctly. Raw payloads, committed: `docs/planning/evidence/COREDEV-2711-section3a-measurement.json`
(digest recorded once in §7's fixture table — deliberately NOT restated here, see below). All three
r12 arms found this line still naming the pre-commit
`~/.claude/handoffs/` copy — the very "uncommitted raw" §7's fixture rule rejects.

| field | measured | what it settles |
|---|---|---|
| caller `agent_type` (plugin sub-agent) | `unleashed-mail:swift-reviewer` | **the fork — §4 holds** |
| caller `agent_id` (plugin sub-agent) | `ad9622e20033905b5`, non-empty | `is_subagent` is decidable |
| caller `agent_id` (main thread, same capture) | **absent** | P0, confirmed from the other side |
| callee `tool_input.subagent_type` | `unleashed-mail:security-reviewer` | rule 6' compares a real value |
| Pre/Post correlation | both pairs matched on `tool_use_id`, outcome `completed` | the SUCCESS outcome path works |

**Method, stated so it can be repeated or attacked.** A temporary `PreToolUse`/`PostToolUse` hook on
`Agent` recorded payloads verbatim and exited 0 emitting nothing, so it could not influence what it
measured; it was verified to record both valid and malformed input *before* use; local settings were
restored byte-identically afterwards (`cmp` clean). The `agent_id` in the payload matches the id the
`Agent` tool returned for that sub-agent, which is an independent cross-check that the record belongs
to the spawn it claims to.

**WHAT THE EIGHT PAYLOADS DO NOT PROVE (codex, r12; recounted r15).** Two things in this section rest
on evidence of different weight, and the distinction is load-bearing. The count is eight — four per
event — and revision 14 left this paragraph, and §7's `cwd` row, still saying four:

* **Demonstrated by the committed artifact:** the caller and callee spellings, `agent_id` present /
  absent, the `tool_use_id` correlation, the `completed` outcomes, the 2-part form, and the
  `agent_id` ↔ `Agent`-tool-return cross-check. All independently re-derived by all three r12 arms.
* **Operational attestations, NOT demonstrated by the payloads:** that the hook exited silently, that
  it was verified against malformed input before use, and that settings were restored
  byte-identically. Those are claims about the METHOD; the artifact cannot corroborate them. They are
  reproducible — the method is stated above precisely enough to repeat — but a reader should know
  which half they are taking on trust.

**AND THE SCOPE IS NARROWER THAN "A PLUGIN SUB-AGENT" (codex, r12; recounted r16).** This is ONE
session, ONE install, ONE plugin version (2.8.2), ONE caller, and TWO callees — one declared, one
undeclared — across TWO **successful** outcomes. (Revision 15 left this saying "ONE declared callee,
ONE successful outcome"; it predated event 2 by two revisions.) `PostToolUseFailure` is not exercised
at all, so §7's fixture requirement naming it is met only on its success half. The generalisation the design actually needs is narrow — that the runtime
scopes `agent_type` for plugin sub-agents — and §7.7's probe, not this capture, is what keeps it true.

**One correction, recorded because this plan's history is made of exactly this.** The first analysis
script reported `agent_type` **ABSENT** and correlation **FAILED** — both artifacts of the script
reading `pre[0]` (the main-thread call) and pooling two distinct call-pairs. The data was right; the
checker was wrong, for the seventh time on this ticket. Had it been trusted, this plan would have
been declared dead by its own fork. It was caught only because "absent" contradicted a field visible
two lines above in the raw record.

**THE FIXTURE IS NOW COMPLETE (captured for revision 13, restated r15).** §7 requires two events and
both are captured. Event 2
— `swift-reviewer` spawning `unleashed-mail:ui-engineer`, **undeclared** and holding `Write`/`Edit`/
`Bash` — returned `completed` with no refusal, which evidences §2's central claim on a
real payload for the first time. Revision 11's first draft named this as the ONLY outstanding item
when the artifact was also uncommitted and carried no registry listing; all three are now closed. What
remains genuinely unexercised is narrower and still stated in §8: `PostToolUseFailure`, and every
generalisation beyond this one session, install and plugin version.

**Design the measurement as ONE complete positive-control event (codex, r4)**, not four separate
readings: prove a plugin-only name resolves, spawn the scoped `swift-reviewer`, have it invoke a
DECLARED scoped callee, and correlate its `PreToolUse` with a successful `PostToolUse` by
`tool_use_id`. That single event establishes the caller spelling, the prefix form, a non-empty
`agent_id`, and scoped-callee viability at once — and the correlation supplies the OUTCOME the
withdrawn fixture lacked.

**THE FORK, RESOLVED.** It said: if the string is **scoped**, §4 holds; if **bare**, the principal is
unattestable and this design is dead, with alternatives (a) remove `Agent` from `swift-reviewer` and
fan the panel out from the main thread, or (b) restructure so the reader of untrusted content is not
the spawner. **It measured scoped. §4 holds and the alternatives are not needed.** The fork is kept
here rather than deleted because it is the record of what this design was willing to lose, and
because a future runtime change that makes the string bare re-arms it — which is what §7.7's
compatibility probe exists to detect.

**The prefix form is now MEASURED as two-part — and is still not to be hardcoded.** The capture above
reads `unleashed-mail:swift-reviewer`: one separator, `<plugin>:<agent>`. That settles the observation
and changes nothing about the instruction, because a measurement pins what the runtime does *today*,
not what it will do. Prior reasoning, retained: observed data says two-part
`<plugin>:<agent>`, and every AGENT example in the documentation is two-part. A three-part
`plugin:<x>:<y>` spelling does appear on the same page, but revision 9 cited it as an agent-form
ambiguity without establishing that it applies to agents at all — it is used there for a different
field. **Treat the ambiguity as unestablished rather than as evidence in either direction**; the
instruction below is unchanged and is what actually protects the design, since it derives the form
instead of trusting any reading of the prose. Derive the plugin name from
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
    P3  "<us>:<name>", $CLAUDE_PLUGIN_ROOT/agents/<name>.md absent -> DENY + diagnostic.
    P4  "<us>:<name>", $CLAUDE_PLUGIN_ROOT/agents/<name>.md ships  -> ENFORCE:
          4'  no `Agent`/`Agent(...)` in the guard-adjusted effective set  -> DENY
          5'  a token exactly `Agent`                                      -> ALLOW
          6'  tokens matching `Agent(...)` -> ALLOW iff the callee matches a declared member
              VERBATIM **and** begins "<us>:", else DENY

**`agent_id`, not `agent_type`, decides main-thread (codex, r3).** Revision 3 said "`agent_type`
absent = main thread". The compiled 2.1.247 schema documents `agent_id` as *"Present only when the
hook fires from within a subagent… Absent for the main thread, **even in `--agent` sessions**"*,
while `agent_type` is present for a subagent **or** a `--agent` main thread. Revision 3 would
therefore have **denied the operator's own `claude --agent swift-reviewer` session** — violating its
own first rule.

**RULE 3 AND THE COLLISION SCAN ARE DELETED, not narrowed.** A scoped principal cannot be shadowed
**while this plugin is the active owner of its namespace**, because project, user, CLI and managed
agents register **bare**. Two qualifications on that premise, both from r6. codex: a same-name plugin
loaded via `--plugin-dir` REPLACES an installed plugin for the session, so `<us>:` can name someone
else's asset — that is an **attestor-liveness** case (§8), not a bare-name collision, and no
filesystem scan would catch it. kimi: the premise is **asserted, not measured**; it reduces to a
name-charset question, and §7.11 is the cell that settles it. The unenumerable-source problem —
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
ALLOWed it, which contradicted the fail-closed principle §7 carried at the time — revision 4's §7.8,
*"fail-closed only where the caller is identified and ours"*, which revision 9 replaced with the
P2/P3 pair now at §7.8 (whole-document pass, r10: the quotation outlived the sentence). P2 remains
the foreign-caller ALLOW, and §7.8 pairs the two so neither can drift into the other.

**And the asset path is pinned, not relative (kimi, r6).** `<name>` arrives inside `agent_type` and
crosses a trust boundary into a filesystem path, so the guard validates it against the agent-name
charset (`[A-Za-z0-9_-]+` — no `.`, no `/`) BEFORE joining, and resolves only
`$CLAUDE_PLUGIN_ROOT/agents/<name>.md`, never a `cwd`-relative `agents/<name>.md`. A traversing name
fails closed by accident today (no such file -> P3 DENY). Accident is not a control.

**The disposition, which revision 9 left unstated (whole-document pass, r10).** A `<name>` failing
the charset **DENIES**, with its OWN diagnostic — distinguishable by content from P3's "asset
missing", because they mean different things: P3 is version skew or corruption, this is a value that
should never have reached a path join. Stating it matters because the accident and the control are
observationally identical on today's tree: an implementation that simply omits the charset check
passes every cell in §7, which is why §7.15 pins it against a traversing name that resolves to an
asset that EXISTS.

**P1 is a judgment call, recorded as one.** A sub-agent with no `agent_type` should on a strict
reading fail closed. It ALLOWs because (i) the compiled schema makes it unreachable, so DENY buys
nothing today while adding a way to break every consumer on a schema change; (ii) the payload is
built by the runtime, not the model, so a prompt-injected sub-agent cannot suppress its own
`agent_type` — there is no attacker control to fail closed against; (iii) DENY would contradict P2,
whose premise is "cannot be shown to be ours → allow".

**ONE PARSER — OVER TOKENIZATION, NOT OVER EFFECTIVE TOOLS (kimi + codex, r6).** Revision 4 dropped
revision 3's single-parser requirement; revision 6 restored it and stated it too broadly. It said
enforcement "reproduces Python `_tool_tokens`/`_live_tools` semantics", and the permission grammar
below then requires the guard to **depart** from `_live_tools`. Both cannot be implemented as written, and
an equivalence gate over `_live_tools` would fail on exactly the divergence the departure exists to
create. This is the r3 failure class at note severity: fix one section, leave the adjacent
requirement contradicting it.

Scoped correctly: the shared parser — or the equivalence gate over a committed corpus — covers
**`_tool_tokens`**, the token split that keeps parentheses intact. The guard's effective-tool
semantics is then defined as **`_live_tools` PLUS the `Agent`-family removal below**, with the
divergence cases named IN that corpus, so the gate pins the adjustment instead of tripping over it.
Without one parser, CI and the runtime read the same declaration differently; without this scoping,
the requirement contradicts the rule it was written to protect.

**The corpus starts from RAW frontmatter as authored (codex, r7)** — plain scalar, flow sequence
(`[a, b]`), block sequence, and single- and double-quoted scalars. An equivalence gate fed an
already-normalised list on both sides proves the two normalisers agree about nothing.

**And `hook_str` fails open by design.** `scripts/lib/hook-io.sh:193` states it "return[s] empty
(fail-open) when neither exists" — so malformed JSON, or a box with neither `jq` nor `python3`, is
**indistinguishable from an absent field**. Under revision 4, P0 would then read a corrupt payload as
"main thread" and ALLOW. Therefore:

* **P0 means `agent_id` absent from a SUCCESSFULLY PARSED object** — never "the extractor returned
  empty";
* **parse failure is a distinct outcome**, and because the caller cannot be identified at all it
  ALLOWs like P2 but emits a diagnostic naming the parse failure — silence here would make the guard
  inert on a broken box with nothing to show for it.

**THE PERMISSION GRAMMAR, DEFINED (codex, r5).** Revision 5 said the plan "must also define" these
and then did not — a requirement stated as if it were a decision. Both cases are measured:

* **`Agent(*)` — and `(**)`, `(/**)`, `(/*)`, `(**/*)` — is FULL BREADTH, not a member named `*`.**
  Under a naive 6' it parses as a one-member list and **denies every real callee**, so a full-breadth
  scope takes **rule 5' (ALLOW)**, exactly as a bare `Agent` does.

  **The guard DEFINES this; it cannot inherit it (kimi, r7).** Revision 7 appealed to
  `validate-plugin-assembly.py:714-718` — "a full-breadth scope is the bare grant by another
  spelling" — but that line sits inside `check_model_reachable_grants` (`:692`), which audits a
  SKILL's `allowed-tools`. The AGENT path does not model it at all: run the shipped parser and
  `_agent_specifier_members("Agent(*)")` returns `['*']` (`:387-391`) — a member literally named
  `*`. The two paths genuinely disagree and the appeal was to the wrong one, so 5' is the guard's
  OWN rule, not a borrowed one. No shipped asset uses the form (verified tree-wide), so nothing
  depends on either reading today — which is precisely why it must be written down before something
  does.
* **ANY `Agent`-family denial — bare `Agent` OR scoped `Agent(x)` — removes the tool entirely, and
  takes rule 4' DENY (codex, r6).** Revision 6 closed only the bare spelling. `_live_tools` subtracts
  EXACT tokens (`validate-plugin-assembly.py:408`), and BOTH spellings escape that subtraction:

      tools: Read, Agent(a, b)   disallowedTools: Agent      ->  ['Agent(a, b)', 'Read']
      tools: Read, Agent(a, b)   disallowedTools: Agent(a)   ->  ['Agent(a, b)', 'Read']

  In the second case the denial names a member of the very token it fails to remove. Per the measured
  COREDEV-2703 contract a scoped entry in a DENY list strips the `Agent` tool **entirely** — that is
  what silently disabled the whole review panel — so taking `_live_tools` at face value would have
  the guard enforce rule 6' against a caller holding no `Agent` tool at all. **The guard therefore
  scans `disallowedTools` for ANY `Agent`-family token FIRST — bare or `Agent(...)`, quotes stripped
  as the validator does — and treats a hit as removing every `Agent`-family token, which lands the
  caller on rule 4'.** (`jira-manager` is the bare shape today.) The 4' diagnostic must distinguish
  the two ways it fires — *declares no `Agent` at all* versus *declared one and denied it away* —
  because the remedies differ, and COREDEV-2703 was a week of silence for want of that distinction.

  **The worst shape is INHERIT-ALL plus a scoped denial (kimi, r7), and it is why this rule keys on
  the DENIAL SET rather than the grant.** With `tools:` omitted `_live_tools` starts from every write
  vector AND a **bare** `Agent`; a `disallowedTools: Agent(a)` subtracts nothing from it, so the
  effective set holds bare `Agent` and a naive guard takes **5' (ALLOW) at full breadth**. That is
  permissive rather than merely mis-modelled — the dangerous direction, and the one shape neither r6
  finding named. Measured against the shipped parser:
  `_live_tools({"disallowedTools": "Agent(a)"})` -> `['Agent', 'Bash', 'Edit', 'NotebookEdit',
  'Write']`. Keying on the denial set catches it whatever the grant looks like.

  **Reachability, stated rather than assumed.** `validate-plugin-assembly.py:644-660` rejects the
  scoped-denial form **unconditionally**, so a validator-clean release cannot ship one. That is a CI
  gate, not a runtime invariant: the guard reads the INSTALLED asset and must not depend on the gate
  having run over it. Both cells ship regardless (§7.9, §7.10).
* **Unparseable frontmatter on an identified caller DENIES**, per §7.14. *(Revision 4 truncated the
  §7 cell that carried this and the attribution dangled for six revisions — ten review rounds did not
  catch it, because it was never in a diff. The outcome is load-bearing: an unparseable asset read
  naively is "no `tools:` key" -> inherit-all -> a BARE `Agent` -> rule 5' ALLOW at full breadth,
  the permissive direction §4 names as dangerous.)*

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
emitter today** — only `hook_emit_ask` (:166) and the `hook_emit_warn` no-op (:174) — so one must be
added.

### 5.2 Consumer blast radius — now trivial
Revision 3 needed three outcomes and a collision scan. With an attested principal there are two: the
caller is ours (scoped) or it is not (P2 → ALLOW, no state). Consumer agents register bare and are
never enforced. The contradiction r2 found is gone rather than papered over.

## 6. Scope

**In scope.** The PreToolUse matcher; `scripts/agent-spawn-guard.sh`; plugin-name derivation from
`CLAUDE_PLUGIN_ROOT`; the two-field predicate; token-shape-aware effective tools **including the
`Agent`-family denial removal**; the shared `_tool_tokens` parser or its equivalence gate; the `deny`
emitter in `hook-io.sh`; **the `UNLEASHED_SPAWN_GUARD=off` kill switch** — dropped from this list in
revision 4 while §5.1 kept relying on it (kimi, r6), and §7.12 now depends on it; the compatibility
probe; tests.

**The companion documentation edits are wider than revision 4 said (codex, r4), because shipped
source-of-truth text still asserts the WITHDRAWN result:**

* `agents/swift-reviewer.md:14-17` — "a probe sees its own `Agent` entry BARE, so nothing exists to
  enforce against". That was the mis-measurement (§3). It ships today.
* `AGENT_CONTRACTS.md:404` — "WHAT DOES NOT BOUND THE SPAWN SET … measured".
* `agents/swift-reviewer.md` **every dispatch path**, not just Step 2's labels — including the
  `jira-manager` call and any recovery path.
* `scripts/validate-plugin-assembly.py:581` — "the **twelve** that hold `Write`/`Edit` or inherit
  everything", in prose sitting directly beside the roster the same function COMPUTES. Recounted:
  thirteen. The computed roster is correct, so nothing behaves wrongly — but this is a shipped
  source-of-truth sentence that disagrees with the code beneath it, which is what this list is for,
  and it is where §2's own miscount came from.
* `scripts/tests/test_validate_plugin_assembly.py:914` — `assertIn(reviewer, scoped[0])` is a
  **substring test over the whole grant string**, so `"security-reviewer"` matches inside
  `"unleashed-mail:security-reviewer"`. When the bare spellings are dropped it will keep passing
  while asserting a property that no longer holds. It must compare PARSED members, not substrings.

**ORDERING, AND THE FAILURE MODE THE COMPANION EDIT CREATES (kimi, r6).** Dropping the bare
spellings converts today's SILENT failure into a LOUD one. Bare dispatch currently resolves to
COREDEV-2768's unrestricted user-scope shadows and reports success; scoped dispatch fails with
*"Agent type not found"* on any install where the plugin's agents do not resolve — **which was the
state of this machine until COREDEV-2769 was resolved on 2026-08-27, and which can silently recur**
(§3). Fail-loud is the posture this plan wants; it is not a posture to deploy
blind. So the ordering is explicit: **§3a's measurement first; the `swift-reviewer.md` dispatch edit
only after it proves scoped names resolve**, and COREDEV-2769 before either. **Both are now
satisfied** (2026-08-27): 2769 is resolved and §3a measured scoped, so the `swift-reviewer.md`
dispatch edit is unblocked — and its fail-loud posture is now the *safe* one, since scoped names
demonstrably resolve on a healthy session.

**Out of scope.** COREDEV-2768's shadows (separate, larger); `swift-reviewer`'s bare `Bash` (§9.1
accepted residual); transitivity — the five specialists resolve to `Read, Grep, Glob` and cannot
spawn, and rule 4' denies it in principle anyway.

## 7. Verification

1. **The hook fires** — feed recorded payloads to the script; assert `hooks/hooks.json` matches the
   literal `Agent`.
2. **Deny is attributable** — every deny cell pairs with an allow in the same run: a declared scoped
   callee ALLOWs where an undeclared one DENIEs.
3. **The main thread is never denied, and the cell is PAIRED (codex, r8)** — `agent_type` present
   with `agent_id` **absent** must ALLOW, including a `--agent` session, run in the same execution
   against the byte-identical payload with `agent_id` **present** and an undeclared callee, which
   must DENY. **The shared `agent_type` is a scoped `<us>:<name>` naming a shipped asset with a
   declared `Agent(...)` roster** (kimi, r9/r10) — §3a's replacement fixture pins exactly that, and
   the DENY arm needs it: against a BARE `agent_type` the second payload would stop at P2 and ALLOW,
   making the pair unsatisfiable rather than merely weak. **This is the cell that fails against
   revision 3**, and the pairing is what makes it fail against an always-ALLOW guard as well:
   `agent_id` is the entire predicate here, so a cell asserting only the ALLOW cannot tell a working
   guard from an absent one. This is where P0's falsifiability lives, which is why P0 is deliberately
   absent from §7.13.

   **ACCEPTED RESIDUAL, recorded so it is not "fixed" later (kimi, r10).** This cell falsifies P0's
   ALLOW/DENY *discrimination*, not the `no state` half of its disposition — after the §7.13
   retraction, P0's SILENCE is asserted by no cell at all. That is deliberate and must stay that way:
   any cell asserting "P0 emitted nothing" re-creates the pressure the retraction removed, since the
   cheapest way to make such an assertion pass is to change what the guard emits at runtime.
4. **Escalation** — `malicious-plugin:security-reviewer` DENIEs; the declared scoped spelling ALLOWs.
   Stated as an escalation test so no one reintroduces normalisation.
5. **Bare callees DENY** even for a declared member, paired against the scoped spelling ALLOWing.
6. **`swift-reviewer` is not denied by rule 4'** — the token-shape regression revision 3 would have
   failed.
7. **The compatibility probe asserts three things, and the third is the negative (kimi, r6)**: a
   known sub-agent event still CARRIES `agent_id`; a main-thread event — including `claude --agent X`
   — still LACKS it; and a plugin sub-agent's `agent_type` is still scoped in the measured form.
   Without that negative cell a runtime that begins emitting `agent_id` on main-thread events passes
   the probe while silently restoring revision 3's regression: enforcing against the operator's own
   session. A schema change must fail loudly rather than turn the guard silently inert.
8. **P2 and P3 are PAIRED — because §4 says they are.** `agent_type: "<us>:<name>"` with
   `$CLAUDE_PLUGIN_ROOT/agents/<name>.md` ABSENT must **DENY** (P3), run in the same execution as
   `agent_type: "other-plugin:<name>"`, which must **ALLOW with no state** (P2). The two payloads
   differ only in the prefix, which is the entire attestation, so a guard that collapses them passes
   either cell alone. Revision 7 left this cell as the bare principle *"fail-closed only where the
   caller is identified and ours"* — a sentence with no payload and no asserted outcome, which an
   always-ALLOW guard satisfies vacuously, while §4 claimed the pair already lived here. It did not.
9. **The `Agent`-family denial pairs, on BOTH axes.** *Denial-spelling axis (codex, r6):* an asset
   with `tools: Read, Agent(a, b)` and `disallowedTools: Agent(a)` DENIES via rule 4', paired in the
   same run against the identical asset WITHOUT the denial, where callee `a` ALLOWs via 6'; the
   bare-denial spelling gets the same pair. *Grant axis — the one revision 8 wrote the rule for and
   nearly failed to test:* an asset that **OMITS `tools:`** and carries `disallowedTools: Agent(a)`
   must DENY via 4', paired against the identical asset with no denial, where the callee ALLOWs via
   5' at full breadth.

   **The second pair is the only one that catches the PERMISSIVE failure.** With `tools:` omitted the
   effective set holds a **bare** `Agent`, so an implementation that reads §4's "removing every
   `Agent`-family token" as "remove the `Agent(...)`-shaped tokens" passes every explicit-grant cell
   above — and still ALLOWs this shape at full breadth. A cell asserting only the DENY would pass
   against a guard that denies everything; a cell set that varies only the denial spelling passes
   against a guard carrying exactly the hole §4 names as the dangerous direction.
10. **The shipped tree carries zero SCOPED `Agent(...)` denials — and the two BARE ones are asserted
    to REMAIN (codex + kimi, r7).** Asserted directly over `agents/*.md` by the guard's own suite
    rather than delegated to the CI validator, because the reachability argument must be checked
    where the guard reads the asset and not where CI does.

    Revision 7 wrote this as "zero `Agent`-family denials". §4 defines that family as bare **or**
    scoped, so the cell contradicted the shipped tree on day one — and worse, it pressured a
    **capability escalation**. `agents/jira-manager.md:19` and `agents/modern-standards-planner.md:23`
    each carry a bare `Agent` denial, and each **omits `tools:`**, so both inherit every tool.
    Measured against the shipped parser: strip that one denial and `Agent` returns to `_live_tools`
    for both. The denial is the only thing holding them out of the spawn set, so an implementer
    deleting it to make the cell pass would hand two agents exactly the capability this ticket exists
    to bound. The cell is therefore **two-sided**: zero scoped denials, AND those two bare denials
    still present. A one-sided cell here is worse than no cell.
11. **A colon-bearing agent name cannot be registered at project or user scope (kimi, r6)** — the
    cell that turns "a scoped principal cannot be shadowed" from an assertion into a measurement. If
    the runtime accepts one, the attestation is forgeable and §4's premise falls.
12. **The kill switch is PAIRED (codex, r7)** — with `UNLEASHED_SPAWN_GUARD=off` set, a cell that
    otherwise DENIEs must ALLOW, run against the same asset and callee that DENY with it unset. An
    unpaired kill-switch cell passes against a guard that never denies anything, which is the state
    this whole ticket is trying to leave.
13. **Every DIAGNOSTIC-EMITTING outcome carries a payload and an asserted result.** P1 (`agent_id`
    present, `agent_type` absent); schema-invalid — `agent_id` as `""`, `null` or a non-string, **and
    a malformed or non-string `agent_type`**, which §4 covers in the same breath and revision 8's
    cell dropped (codex, r8); and parse failure (malformed JSON). Each ALLOWs, and each must emit its
    OWN diagnostic asserted **by content**, so the three are distinguishable in a log. They all
    ALLOW, so an inert guard reproduces every outcome — only the distinct diagnostic separates
    "allowed for this stated reason" from "never ran". A rule with no cell is a comment.

    **P0 IS DELIBERATELY NOT IN THAT LIST, and revision 8 put it there (codex, r8; kimi reached it
    independently in a round its harness then voided).** §4's P0
    row reads `ALLOW, no state` — the same disposition as P2, written in explicit contrast to
    P1's `ALLOW + diagnostic`, and §4's parse-failure bullet ("ALLOWs like P2 **but** emits a
    diagnostic") is incoherent unless "no state" means silent. So the two sections could not both be
    implemented: build from §4 and the §7.13 suite fails; build from §7.13 and the guard logs on
    **every main-thread `Agent` call** — surface the P0 row itself declines to add, P0 being the only
    outcome the table marks `no state` on a path that fires for every main-thread spawn. (Revision 9
    first attributed that to §4's P1 rationale. It does not say it: P1's three reasons are
    unreachability, absence of attacker control, and consistency with P2 — and P1's own disposition
    is `ALLOW + diagnostic`, so it is the outcome that ADDS surface. Caught by the pre-review sweep.)
    Two retractions were available and §4's row is the one that survives, because amending P0 to
    `ALLOW + diagnostic` would let a verification cell dictate runtime behaviour: that is precisely
    the defect §7.10 was rewritten to remove, one revision earlier. P0's falsifiability is carried by
    **§7.3**, which is where it already was — revision 8's claim that these outcomes shipped with
    "zero" cells was false for P0 (codex, r8).

14. **Unparseable frontmatter on an identified caller DENIES (whole-document pass, r10)** — an
    `agent_type` of `<us>:<name>` whose `$CLAUDE_PLUGIN_ROOT/agents/<name>.md` SHIPS but whose
    frontmatter does not parse must DENY, paired in the same run against the same asset with
    parseable frontmatter, where a declared scoped callee ALLOWs. §4 asserted this outcome and cited
    a §7 cell that revision 4 had removed; without the cell, the naive implementation ALLOWs at full
    breadth, so this is the permissive direction and needs the pair, not a lone DENY.
15. **The agent-name charset check is asserted, against a name that RESOLVES** — a `<name>`
    containing `/` or `.` must DENY on the charset rule with its own diagnostic, and the cell must
    use a traversing name whose target asset EXISTS. A cell whose traversing name resolves to
    nothing proves only that P3 fires, which is the accident §4 says must stop being one: an
    implementation omitting the charset check entirely passes it.
16. **Rule 4' fires two ways and says which** — an identified caller whose asset declares NO
    `Agent` token at all must DENY, paired against one that declared an `Agent(...)` and had it
    removed by an `Agent`-family denial, in the same run, with the two diagnostics distinguishable
    **by content**. §4 makes the two-way diagnostic mandatory and motivates it with COREDEV-2703's
    week of silence; §7.9's payloads are all the denial-driven variant, so nothing exercised the
    other arm.

17. **The plan's cited artifact digest matches the artifact.** Recompute the sha256 of
    `docs/planning/evidence/COREDEV-2711-section3a-measurement.json` and assert it equals the value in
    §7's fixture table — and assert that value appears EXACTLY ONCE in the plan.

    **This cell exists because the failure it catches happened three times.** The digest drifted when
    event 2 was merged (r13), again when the artifact's `significance` was corrected (r15), and the
    stale value survived a whole-document sweep both times. The mechanism was duplication: the digest
    was stated in two places, so every artifact edit needed two updates and got at most one. Revision
    16 removes the duplication and this cell enforces it. A derived value restated in prose is a stale
    value waiting to happen; §7's own doctrine — a rule with no cell is a comment — applies to the
    plan's own bookkeeping.

**The fixture must be rebuilt (§3); the r3 one is not evidence. IT NOW EXISTS IN FULL.** Capture it
with the plugin **proved loaded**, commit the registry listing from capture time as that proof, retain
`cwd` (structural), hash **the committed artifact** rather than an uncommitted raw, and record
**outcomes** by registering `PostToolUse`/`PostToolUseFailure` on `Agent` and correlating by
`tool_use_id`. Each requirement, with its true status — revision 11 first claimed only ONE was outstanding, which
was itself an overclaim (measurement audit, r11):

| requirement | status |
|---|---|
| captured with the plugin **proved loaded** | **met** — `unleashed-mail:tester`, plugin-only with no shadow, resolved |
| the registry listing committed as that proof | **met** — `registry_listing_at_capture` in the artifact below |
| `cwd` retained (structural) | **met** — present in all **eight** payloads (verified) |
| the **committed** artifact hashed, not an uncommitted raw | **met** — `docs/planning/evidence/COREDEV-2711-section3a-measurement.json`, sha256 `3eef3d1176ebd11a` — **this is the ONLY place the digest is stated** |
| outcomes recorded via `PostToolUse` correlated by `tool_use_id` | **met** — both pairs matched, outcome `completed` |
| event 1: a plugin sub-agent spawning a **declared** scoped callee | **met** — §3a |
| event 2: one spawning an **UNDECLARED** callee | **met** — captured 2026-08-27 |

**Event 2 does more than complete the fixture — it demonstrates the premise.** `swift-reviewer`
spawned `unleashed-mail:ui-engineer`, a type absent from its own declared `Agent(...)` roster which
holds `Write`, `Edit` and `Bash`, and the runtime returned `completed` — **the roster was not
enforced.** (Revision 13 also said "no prompt". Withdrawn as unprovable from this evidence, kimi r14 —
and revision 14 withdrew it HERE while leaving it asserted in §3a, so for one revision the document
contradicted itself about its own withdrawal. codex r15 caught that. It is the FIFTH instance in a
single day of a fix landing in one section while an adjacent one keeps the old claim, which is why
§7's own discipline — a rule with no cell is a comment — applies to prose as much as to cells:
the payload records `permission_mode: "auto"`, under which no prompt would be expected anyway, and a
payload cannot demonstrate a UI negative. The claim that carries the design — roster not enforced,
`completed`, no refusal — is fully demonstrated and is what remains.)
The declared list is not a runtime control. §2 and `validate-plugin-assembly.py:615-626` have said so
since COREDEV-2703; this is the first time it is evidenced by a payload rather than asserted.

**Exactly ONE real caller/callee pair now exists — not one per cell (kimi, r14).** Revision 13 said
"every DENY cell in §7 now has a real pair to run against", which overreached. This pair grounds the
undeclared-callee denial specifically. Cells that vary the caller PREFIX (§7.4, §7.8), the asset
SHAPE (§7.9, §7.14) or the name CHARSET (§7.15) still construct their payloads synthetically, and
that is legitimate — but it is not what "a real payload" means, and the distinction is the difference
between a suite grounded in one observation and a suite grounded in seven.

## 8. Risks

* **Inert for bare-name callers** (§1). Honest, testable, and strictly better than revision 3 — which
  was a no-op in production *and* would have denied both the operator's `--agent` session and
  `swift-reviewer`'s own panel.
* **§3a — DISCHARGED 2026-08-27.** It read scoped; §4 holds. What replaces it as a risk is narrower
  and permanent: the measurement pins TODAY's runtime. §7.7's probe is what turns a future change
  from a silent inversion into a loud failure, and it is now the only thing standing between this
  design and a runtime that starts reporting bare.
* **The fixture is complete (§7) — but `PostToolUseFailure` is not exercised.** Both required events
  are captured, including the undeclared-callee spawn that the runtime permitted with no refusal. The
  residual gap is narrow: every captured outcome is `completed`, so no cell has ever seen the failure
  path its own fixture rule names.
* **The prefix form is measured, not guaranteed.** Derive it, pin it by measurement, fail loudly on
  change — unchanged by having measured it once.
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
