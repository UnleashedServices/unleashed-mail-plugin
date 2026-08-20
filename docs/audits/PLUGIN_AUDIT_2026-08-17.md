# Plugin Soundness Audit — 2026-08-17

**Ticket:** COREDEV-2654 (parent Epic COREDEV-2485; prior audit COREDEV-2525).
**Baseline:** v2.8.0, commit `4cf4835` (merge of PR #68), branch `claude/unleashed-mail-audit-tnfcq4`.
**Scope:** full plugin — manifests, `hooks/` + all 11 hook scripts + `scripts/lib/`, the plan-review
pipeline (`scripts/review/`, capture hooks, verdict gate), all 21 `agents/` + 21 `skills/`,
`mcp/review-synthesizer/`, validators, CI, repo hygiene, and **remediation verification of every major
finding from the 2026-07-19 audit**.
**Method:** the complete CLAUDE.md validation suite executed on Linux; every contract claim re-verified
against the live Claude Code docs (fetched 2026-08-17); three parallel deep reviews (review pipeline,
assets, MCP server); the pipeline exercised **end-to-end with stub CLIs and then attacked** (7 forgery /
staleness / identity attacks, all refused); the MCP server driven through a **35-check live JSON-RPC
handshake**; CI history checked via the GitHub API, including the macOS post-merge canary.
**Question asked of every subsystem:** would this fail, wedge, produce a wrong verdict, or severely
hinder flow when the plugin is the primary harness for UnleashedMail development?

---

## Executive verdict

**The plugin is sound and runs as intended.** Every shipped validator and test suite passes (302 hook
tests, 228 MCP tests, 1006 scripts tests, shellcheck, both `claude plugin validate` modes on CLI
2.1.234); all 10 registered hook events are real documented events; the mandatory plan-review gate
refused every attack thrown at it (approve-then-edit, transcript reuse, reviewer-identity swap, foreign
artifact, stale approval, mid-round tree mutation); the bundled MCP server is protocol-correct and
byte-deterministic; and **all 10 major findings from the 2026-07-19 audit are verified remediated**,
several now machine-enforced. CI on `main` is green through `cdbaf32`, including the macOS
redactor-equivalence canary.

**Nothing found produces a wrong verdict or a corrupted gate.** The defects that remain live at the
edges: contract documentation that contradicts the (correct) shipped assets, a debug-review flavor that
is advertised but unreachable, an undocumented operational rule whose violation burns a 28-minute review
round, and a test suite that reports false-red on machines without zsh. These are flow hazards, not
mechanism defects — each has a small, local fix, itemized below.

---

## 1. Verified all-clears (positive assurance)

### 1.1 Validation baseline (this audit's run)

| Gate | Result |
|---|---|
| `validate-plugin-assembly.py --strict` | ✅ 21 agents, 21 skills, 0 commands, 4/4 manifests |
| `validate-hooks.py --strict --require-manifest` | ✅ 10 events, 12 invocations, 11 scripts parse-checked |
| `validate-version-sync.sh` (strict) | ✅ plugin 2.8.0 == README; counts 21/21/0/1 |
| `test-hooks.sh` | ✅ 302 passed, 0 failed |
| MCP suite (`mcp/review-synthesizer/tests`) | ✅ 228 tests OK |
| scripts suite (`scripts/tests`) | ✅ 1006 tests OK (165 Darwin/CLI-gated skips) **with zsh**; ⚠️ errors=10 **without zsh** → AF-2 |
| `shellcheck -s bash -S warning` (all scripts + pre-commit) | ✅ clean (0.11.0) |
| plan-citation linter (`--selftest` + plan) | ✅ 38 assertions |
| `git diff --check` (merge-base..HEAD) | ✅ clean |
| `generate-callers-exemptions.py` + diff | ✅ unchanged (388 records) |
| `claude plugin validate --strict .` (CLI 2.1.234 > pinned 2.1.220) | ✅ passed |
| `claude plugin validate .claude-plugin/plugin.json` (deep) | ✅ passed with only the documented root-CLAUDE.md warning |
| `bash -n` (29 review-pipeline scripts) / `py_compile` (10 Python files) | ✅ clean |
| CI history (GitHub API) | ✅ plugin-ci green on `main` pushes incl. macOS canary through `cdbaf32` |

### 1.2 Contract claims vs live Claude Code docs (fetched 2026-08-17)

- **All 10 hook events in `hooks/hooks.json` are real, documented events** — `PreToolUse`,
  `PostToolUse`, `Stop`, `StopFailure`, `PermissionDenied`, `PostToolUseFailure`, `PreCompact`,
  `SessionStart`, `SubagentStart`, `SubagentStop`. No dead registrations.
- Agent frontmatter camelCase keys (`tools`/`disallowedTools`/`model`/`effort`/`skills`/`memory`),
  the absence of `allowed-tools` on agents, kebab-case `allowed-tools`/`disallowed-tools` on skills,
  commands-merged-into-skills, `${CLAUDE_PLUGIN_ROOT}` in hooks/.mcp.json, and the
  SessionStart/PostToolUse JSON output contracts used by `scripts/lib/hook-io.sh` — **all confirmed**.
- Method note: a first docs fetch returned a truncated page that "refuted" `PreCompact`/`SubagentStop`;
  a direct re-fetch of the full hooks reference disproved that. The habit of re-verifying surprising
  doc claims against the primary source remains load-bearing.

### 1.3 The 2026-07-19 audit's 10 major findings — all remediated

| Prior finding | Status | Evidence |
|---|---|---|
| MAJ-1 §11 model-tier drift | ✅ fixed, **machine-enforced** | §11 table == all 21 frontmatters; `validate-plugin-assembly.py` parses the table and asserts equality |
| MAJ-2 §5 stale capture semantics | ✅ fixed | §5 now ratchet semantics: "a captured COMPLETE never certifies", UNATTRIBUTED → re-dispatch |
| MAJ-3 logic-engineer skill access | ✅ fixed | skills referenced as Read targets via `${CLAUDE_PLUGIN_ROOT}/skills/...` (logic-engineer.md:36-41, 89, 233) |
| MAJ-4 schema.py tilde fail-open | ✅ fixed | schema.py:202 rejects `~`, `~/`, `~user/` |
| MAJ-5 synthesize.py silent samples default | ✅ fixed | unrecognized flags exit 2 (synthesize.py:420-423); samples fallback confined to demo mode |
| MAJ-6 CLAUDE_PLUGIN_DATA two-directory split | ✅ fixed by design (2.8.0) | COREDEV-2617 base store + SessionStart conflict notice; git-hook caveat documented (pre-commit-checks.sh:13-18) |
| MAJ-7 pre-commit PII scan no-op | ✅ fixed | all staged text files, correct ERE, enforcing `gitleaks --staged` pass |
| MAJ-8 unscoped Bash on 8 knowledge skills | ✅ fixed | every knowledge skill is `Read, Grep, Glob`; workflow skills use scoped `Bash(...)`/`Agent(...)`/`Write(...)` grants |
| MAJ-9 `$ARGUMENTS` shell injection (implement) | ✅ fixed | no `$ARGUMENTS` in shell syntax; the heredoc-delimiter attack that defeated the first fix is documented as the design rationale |
| MAJ-10 fixed `/tmp` capture paths | ✅ fixed | COREDEV-2619 per-run transcript allocation (O_EXCL leafs, `.launch` attestation); the old fixed `/tmp` capture-path spelling survives only in historical doc comments (described, not written — the COREDEV-2619 scanner flags the literal, and correctly flagged this report's first draft for spelling it) |

### 1.4 Plan-review pipeline (mandatory gate) — exercised and attacked

Full gate ran green end-to-end on Linux with stub CLIs: `snapshot-plan.sh` →
`capture-gemini-review.sh` → `capture-codex-review.sh` → `persist-verdict.sh` →
`resolve-plan-gate.sh` = `GATE OK`. Then attacked; **every attack refused**:

- approve-then-edit → refused (digest);
- `codex=MISSING` + APPROVE → refused;
- one transcript reused for both reviewers → refused (content-digest floor);
- two genuine gemini runs labelled gemini+codex → refused (`.launch` attestation);
- artifact copied to a byte-identical second plan → refused (plan identity);
- absent `agy` → clean exit 127 with a captured diagnosis (preflight exits 1 with a clear message);
- mid-round live-tree write → round void, exit 3.

Also verified: no unbounded external invocation anywhere (every reviewer call goes through
`pty-capture.py` with an explicit `--timeout`); missing CLIs fail closed in milliseconds; per-run
O_EXCL leafs, atomic verdict writes and TTL-swept consume-once round bindings make two concurrent
sessions unable to cross-satisfy each other's gates; BSD/GNU portability clean on the critical path.

### 1.5 MCP server — live protocol verification

35-check driver against the real subprocess: initialize (version negotiation incl. unknown-version
fallback to 2025-11-25), notification silence, `tools/list`, `tools/call` on the shipped samples
(verdict=REQUEST_CHANGES with the two demo rows correctly quarantined/pre-existing), `ping`,
`-32601`/`-32602`, malformed-line survival, clean EOF exit 0, stdout purity, and **byte-identical
output across 3 processes × 3 hash seeds**. Zero-dependency and Python-3.8-parse floors hold. The tool
name and argument contract match `agents/swift-reviewer.md` Step-5 and README byte-for-byte
(`mcp__plugin_unleashed-mail_review-synthesizer__synthesize_review`).

### 1.6 Assets, CI, hygiene

- All 42 frontmatters parse; no `allowed-tools` on agents; no `effort:` pins anywhere; `memory:` only
  on the two writer agents; model aliases valid (sonnet ×7, opus ×3, inherit ×11); every asset has a
  non-empty `description:`; no name collisions; all `skills:` preloads and all
  `${CLAUDE_PLUGIN_ROOT}/scripts/...` references resolve; hook matchers name the five real reviewer
  agents with the optional namespace prefix; swift-reviewer's writer deny-list is complete in bare and
  namespaced spellings; all 9 README-documented `UNLEASHED_*` kill switches are read by the named scripts.
- Read-only reviewer body↔frontmatter coherence holds for all five reviewers + two personas.
- CI: SHA-pinned actions; pinned + checksum-verified actionlint/gitleaks/Claude CLI; zsh presence
  asserted so the dual-shell tests cannot silently skip; event-dependent whitespace base; py3.9 smoke
  with real invocations; a plugin **load check** (scratch marketplace + MCP handshake); history-aware
  gitleaks with a commit-scoped allowlist that matches SECURITY.md's guarantee.
- `hook-io.sh` emit shapes match the documented hook JSON contracts; the redactor's `\xNN` sed escapes
  are **empirically proven equivalent on BSD sed** by the macOS canary (60k seeded vectors + 196
  fixtures incl. NBSP/U+2028/U+3000, UNEXPLAINED == 0) — an initial audit suspicion, refuted by the
  repo's own gate.
- `.gitignore` covers the twice-burned transient-file classes by tool prefix, the 7 fixture-tree
  prefixes, and `__pycache__`; working tree stays clean through a full audit run.

---

## 2. Findings needing remediation

Severity reflects consequence for a team relying on this plugin as its primary harness.
No CRITICALs were found.

### AF-1 · HIGH · `AGENT_CONTRACTS.md:371` — §9 capability-floor row contradicts §9.1 and the shipped reviewers

§9's floor table says reviewers get `Read, Bash, Grep, Glob` with prompt-review as the no-Bash
exception. Reality: **all five reviewers ship `tools: Read, Grep, Glob`**, and §9.1 (line 399) says
exactly that — "no `Bash` on any of them" — with the regression-tested PR #63 P1 rationale (reviewers
are reachable from the model-invocable `pr-review` skill). AGENT_CONTRACTS is the declared source of
truth for boundary disputes, so a maintainer "fixing" reviewers up to the §9 floor would re-grant
shell to four read-only reviewers and reintroduce the exact P1 the repo documents removing.
**Fix:** rewrite the §9 reviewer row to `Read, Grep, Glob` (delete the now-inverted prompt-review
exception) and restate the orchestrator row's `+`-base explicitly. Consider extending the §11-style
table parser in `validate-plugin-assembly.py` to §9 so floor rows can never drift from frontmatter again.

### AF-2 · MEDIUM · `scripts/tests/test_plugin_state_store.py:31` — 10 tests ERROR (not SKIP) when zsh is absent

`SHELLS = ("/bin/bash", "/bin/zsh")` is iterated with no existence guard; on a zsh-less machine
`run_shell()`'s `subprocess.run` raises `FileNotFoundError` → unittest **ERROR** in the three
non-Darwin-gated classes (EncoderInvariantP, AceGrammarAndAnswerMachine, NameLengthBudget).
Reproduced: `FAILED (errors=10, skipped=167)` without zsh; `OK` after installing zsh 5.9. CI is
unaffected (it installs zsh and separately asserts its presence), but CLAUDE.md's mandatory local list
("run the whole list") reports a false-red on any Linux box without zsh — **including fresh Claude Code
web containers for this very repo** — indistinguishable from a real regression. That trains agents and
maintainers to ignore red suites, the exact failure mode this repo's own history warns about.
**Fix:** guard the zsh arm the way sibling `test_plugin_state_base.py` does
(`@unittest.skipUnless(shutil.which("zsh") ...)` or a per-shell skip inside the loop), resolving the
binary via `shutil.which` with `/bin/zsh` fallback rather than hardcoding. CI's explicit
"Assert zsh is present" step already prevents silent skip-loss there. Optionally add a SessionStart
setup note (or repo setup script) installing zsh for remote/web sessions.

### AF-3 · MEDIUM · `skills/gemini-review/SKILL.md` + `scripts/review/bind-prompt.py:84,178-180` — advertised debug reviews cannot pass the mandatory wrappers

The skill advertises "Bug investigation or debugging" through the same granted capture wrapper and
mandates "for debug review: NO fallback — fail the review rather than degrade". But
`capture-gemini-review.sh:51` requires a `<plan>` operand and `bind-prompt.py` recognizes only
`*_PLAN.md` tokens, refusing any prompt that names no plan ("the prompt never names a plan") **before
the reviewer launches**. Verified empirically with `docs/planning/ISSUE-42.md`. A gate-bearing debug
round on anything not named `*_PLAN.md` is impossible through the only pre-approved entry points, and
the skill never says so — an agent following it hits a dead end with a misleading refusal.
**Fix:** either scope the wrapper contract explicitly to plans in both review skills and document the
alternate path for debug reviews, or teach `bind-prompt.py` an explicit `--target` mode that binds a
non-plan review target by path + digest.

### AF-4 · MEDIUM · `skills/create-feature-plan/SKILL.md:75` — documents the raw, uncontained snapshot call

Step 2 instructs `python3 .../review-verdict.py snapshot --plan ...` directly, and the skill has **no
`allowed-tools` at all**. `scripts/review/snapshot-plan.sh` exists precisely to contain this call (its
header records that the direct grant once let the model snapshot `/tmp` files; `brainstorm` was
migrated to the wrapper at SKILL.md:172). Consequences: the mandatory gate-launch step re-prompts for
permission every time (the MIN-27 re-prompting problem this release claims fixed), and the documented
command bypasses the `docs/planning` containment.
**Fix:** change step 2 to `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/snapshot-plan.sh"
docs/planning/FEATURE_NAME_PLAN.md` and grant exactly that in `allowed-tools`.

### AF-5 · MEDIUM · `scripts/review/isolated-{agy,codex}-review.sh` (fingerprint compare) — the freeze-the-tree rule is enforced but nowhere stated; parallel dispatch can self-void a 28-minute round

Both harnesses compare `tree_fingerprint` before/after and exit 3 "round void" on any difference — a
new untracked file counts (verified live). In this repo the `.agy-*.md`/`.codex-*.md` prompt files are
gitignored so the natural parallel flow is safe *here*; in a **consumer repo without those ignore
entries**, "write agy prompt → launch 28-min gemini capture → write codex prompt" voids the gemini
round at minute 28, as does any unrelated untracked churn (build logs, editor droppings). Neither
review skill states the ordering rule; only the unreferenced kimi harness carries the lesson.
**Fix:** add to both review skills: "write BOTH per-round prompt files before launching either arm,
and freeze the tree until both rounds land"; ship the prompt-glob gitignore entries in the consumer-repo
setup instructions (README Installation).

### AF-6 · MEDIUM · `skills/gemini-review/SKILL.md:16`, `skills/codex-review/SKILL.md:180`, `README.md:452` — "bare names are canonical" contradicts the namespacing correction

AGENT_CONTRACTS Cross-references (:621-627) and CLAUDE.md state the plugin registers skills
**namespaced** ("the invocation that always resolves"); bare `/gemini-review` resolves only where the
consumer workspace ships local copies. The three cited sites still teach bare-is-canonical, so an agent
following the skill body in a fresh consumer checkout invokes a command that does not resolve.
**Fix:** flip the three sites to namespaced-canonical phrasing (`README.md:207` is a historical v2.4.1
record and can stay).

### AF-7 · MEDIUM · `CLAUDE.md:87` — stale gemini reviewer model

Says the gate runs `gemini-3.1-pro`; the shipped skill (gemini-review/SKILL.md:3,29,232) and
`isolated-agy-review.sh:58` use `gemini-3.6-flash-high` — a v2.7.0 breaking change per README:44.
Every plugin-repo session loads CLAUDE.md, so this actively misinforms.
**Fix:** update CLAUDE.md:87.

### AF-8 · MEDIUM (documented residual + one verification task) · `scripts/review-verdict.py:1417-1620` — `verify` trusts the artifact; check whether `Write(docs/planning/**)` covers `.verdicts/`

All transcript checks run only in `write`; `verify` validates artifact self-consistency + plan digest
but never re-opens a transcript, so a hand-written artifact with fabricated distinct 64-hex digests
passes the gate. This bound is **openly documented** (review-verdict.py:109-112, deferred to
COREDEV-2497) and is accepted design. The new observation: `brainstorm`'s `Write(docs/planning/**)`
grant plausibly covers `docs/planning/.verdicts/<plan>.verdict.json`, which would make direct artifact
fabrication permission-prompt-free.
**Fix:** verify whether Claude Code's permission glob matches dot-directories; if it does, carve
`.verdicts` out of the grant or move the verdict state directory out of `docs/planning`.

### Minor findings (LOW)

| # | Location | Finding → fix |
|---|---|---|
| AF-9 | `isolated-agy-review.sh:207`, `stage-prompt.py:253-254` | Undocumented 1000-byte assembled-prompt floor; the skill's own minimal example (gemini SKILL.md:146-150) is below it, and the refusal says "truncated" after consuming a transcript leaf. Document the floor in both review skills; reword the message ("below the N-byte floor"). |
| AF-10 | `isolated-agy-review.sh:234-235`, `isolated-codex-review.sh:153-154` | Harnesses wrap pty-capture in `>/dev/null 2>&1`, discarding its stderr diagnostics (timeout notice, leaf/launch refusal reasons). Redirect stdout only, or tee stderr through. |
| AF-11 | `isolated-codex-review.sh:154` | Prompt passed positionally with no `--`; a prompt starting with `-` (e.g. a Markdown bullet) parses as a flag and fails the round after allocation. Insert `--` (and in the skill's example forms). |
| AF-12 | `isolated-kimi-review.sh:44` | Hardcodes `PLAN_REL=...COREDEV-2617...`; against any other plan it basis-checks the wrong document. Unreferenced campaign tool, so the mandatory gate is unaffected — parameterize before reuse. |
| AF-13 | `resolve-plan-gate.sh:48`, `reviewer-roster.sh:141` | Bare interactive invocation blocks on `cat` stdin until EOF (Claude Code's Bash tool yields immediate EOF, so only a human at a TTY sits at a silent read). Add a `[ -t 0 ]` usage hint. |
| AF-14 | `AGENT_CONTRACTS.md:392` | §9.1 cites `changeset.sh` for swift-reviewer's Bash need; actually the inline git Step 1 + `reviewer-roster.sh` + `build-verify.sh` (`changeset.sh` belongs to pr-review). Correct the citation. |
| AF-15 | `README.md:472` | Hook table lists `swift-build-verify.sh` under "Write/Edit, Bash"; it registers under Bash only (hooks.json:36-45). Fix the cell. |
| AF-16 | `hooks/hooks.json:5,27` | Stale `MultiEdit` in the PreToolUse/PostToolUse matchers (tool removed from Claude Code; harmless in a regex, but violates the repo's own stale-name hygiene per jira-manager.md:17-18). Drop it. |
| AF-17 | `CHANGELOG.md` | History starts at `[2.2.4]` while the preamble claims all notable changes and README documents 2.2.0–2.2.3. Add a one-line "history starts here" provenance note. |
| AF-18 | `README.md:470,473` | The working `UNLEASHED_SENSITIVE_GUARD=off` and `UNLEASHED_STOP_GATE=off` kill switches are undocumented (only `_MODE` forms listed). Add them. |
| AF-19 | `mcp_server.py:232,282` | BrokenPipeError traceback + rc 1 when the client closes stdout mid-write (teardown race; the only untested protocol path). Catch BrokenPipeError around `_send`/main loop and return 0. |
| AF-20 | `mcp_server.py:258-261` | Malformed JSON line silently dropped (stderr note) instead of JSON-RPC `-32700` with `id:null`. Matches common SDK practice; optional strict-conformance fix. |
| AF-21 | `mcp_server.py:218-219,281` | A *request* (with id) to `notifications/initialized` gets no response — a buggy client would hang. Reply `{}` or `-32600` when `has_id` on `notifications/*`. |
| AF-22 | `mcp_server.py:25` | Unused `import re`. Delete. |
| AF-23 | `mcp/review-synthesizer/README.md:35-42` | Omits the shipped `content[1]` verify-data block; `content[0]` description slightly off (All Issues table, not per-domain sections). One-sentence doc fix. |

### Info / accepted residuals

| # | Note |
|---|---|
| AF-24 | MCP server: no readline length cap (multi-GB line would OOM) and O(n²) clustering — input is the local trusted orchestrator's, acceptable as shipped; defensive caps optional. |
| AF-25 | The plugin-state store is **Darwin-only by design**; on Linux publishers print one "chain does not authenticate" stderr line per process and state features stay off fail-closed (`unleashed_base_ok`), never blocking the pipeline. `linux-primitive-probe.sh` + the probe CI job exist to build the Linux arms; until then this is by-design, documented in CHANGELOG 2.8.0. |
| AF-26 | The §9/§11-style machine-checking of AGENT_CONTRACTS covers §11 and §13 only; §9's floor table is prose-checked by nobody (see AF-1's fix suggestion). |

---

## 3. Flow-hindrance analysis (the specific "severely hindered" risks)

Ranked by expected time lost for a team using this plugin as the primary harness:

1. **False-red local suite without zsh (AF-2).** Every fresh Linux/remote session that follows
   CLAUDE.md's mandatory list hits `FAILED (errors=10)`. Cost: either a wasted investigation per
   session or, worse, learned disregard for red gates. One-file fix.
2. **Self-voiding review rounds in consumer repos (AF-5).** The natural parallel dispatch voids the
   28-minute gemini round at its end; nothing tells the operator the rule the harness enforces. Cost:
   ~30 min per occurrence plus reviewer-CLI quota. Doc + gitignore fix.
3. **Debug-review dead end (AF-3).** The gemini skill's advertised debug flavor is refused before
   launch with a misleading message; an agent has no documented way forward. Cost: a stalled
   debugging session per attempt.
4. **Non-resolving bare commands in fresh checkouts (AF-6).** `/gemini-review` per the skill body vs
   the namespaced reality — first-run friction exactly at the mandatory gate.
5. **Per-round permission re-prompting in plan scaffolding (AF-4).** Undermines the frictionless-gate
   work this release shipped; also a containment bypass.
6. **Gate refusals that under-explain (AF-9, AF-10, AF-11, AF-13).** Each costs minutes-to-an-hour of
   head-scratching when hit; all are one-line fixes to messages/redirects.

Explicitly **not** flow risks: the Stop gate (TTL + commit + per-session sentinel + two loop guards,
fail-open on every degraded path — it cannot wedge a session); the sensitive-file guard (fail-open on
missing python3, 256 KiB DoS backstop, fail-closed only on a genuine parse failure); hook timeouts
(5–60 s, all observe-only paths exit 0); the MCP server (deterministic, survives malformed input);
missing reviewer CLIs (millisecond fail-closed with clear diagnostics, no hangs anywhere).

---

## 4. Suggested remediation order

1. **AF-1** (source-of-truth contradiction — the one finding that can cause a *security regression* if
   obeyed) and **AF-7** (one-line CLAUDE.md model fix). Both are documentation edits.
2. **AF-2** (zsh skip guard) — one test-file edit; unblocks trustworthy local validation everywhere.
3. **AF-3, AF-4, AF-5, AF-6** as one "review-gate operator contract" pass over the three review skills
   + README Installation (they touch the same files).
4. **AF-8**'s verification task (dot-directory glob semantics), then decide carve-out vs relocation.
5. The LOW batch (AF-9…AF-23) — mostly one-liners; AF-19 is the only behavioral code fix among them.
6. Consider extending the assembly validator to machine-check §9 like §11/§13 (closes AF-1's class).

---

*Method notes: subagent docs-fetches were re-verified against primary sources before use; one
hallucinated hook-event refutation was caught and discarded this way. All attack claims above were
reproduced live, not inferred. No repo file was modified during evidence collection; the working tree
remained clean throughout.*

---

## Addendum — remediation record (same day, same branch, COREDEV-2654)

Remediation was applied on `claude/unleashed-mail-audit-tnfcq4` immediately after the report landed.
Per-finding status:

| Finding | Status | Where |
|---|---|---|
| AF-1 HIGH §9 floor row | **Fixed** | AGENT_CONTRACTS §9 reviewer row now `Read, Grep, Glob` with the inversion's history recorded; Orchestrator/Diagnostic rows restated in full (no `+`-inheritance) |
| AF-2 zsh ERROR-not-SKIP | **Fixed** | `run_shell()` raises `unittest.SkipTest` on a missing shell; CI's zsh-presence assert still prevents silent skip-loss there |
| AF-3 debug reviews unreachable | **Fixed (documented)** | Both review skills now state the wrappers are plan-only and give the two debug paths (plan-ify the investigation, or advisory run outside the grants). The scripted `--target` binding stays deferred to COREDEV-2654 — a functional gate change that must go through the plan gate itself |
| AF-4 uncontained snapshot call | **Fixed** | create-feature-plan documents `snapshot-plan.sh` and gained `allowed-tools` granting exactly it (+ `Edit(docs/planning/**)` scaffold grant with the AF-8 carve-out) |
| AF-5 freeze-the-tree unstated | **Fixed** | "Scope and round hygiene" section in gemini-review (mirrored in codex-review); consumer gitignore globs added to README Installation |
| AF-6 bare-canonical drift | **Fixed** | gemini-review:16, codex-review review-tooling line, README process item 2 flipped to namespaced-canonical |
| AF-7 stale gemini model | **Fixed** | CLAUDE.md now `gemini-3.6-flash-high` |
| AF-8 `.verdicts` grant question | **Verified + carved out** | Docs confirm gitignore semantics (dot-dirs matched). brainstorm + create-feature-plan carry `disallowed-tools: Edit(docs/planning/.verdicts/**)`; sanctioned writes stay Bash-subprocess-only via `persist-verdict.sh`. Relocating the state dir stays deferred (gate change) |
| AF-9 undocumented prompt floor | **Fixed** | Floor documented in the hygiene section; `stage-prompt.py` refusal now names the floor and the likely causes (test-pinned prefix retained) |
| AF-10 discarded pty stderr | **Fixed** | Both harness capture invocations silence stdout only |
| AF-11 codex leading-dash prompt | **Fixed** | `--` before the positional in the harness and the skill's free-content example |
| AF-12 kimi hardcoded plan | **Fixed** | Plan is now the optional 5th operand (default preserved for existing invocations/tests); the basis-checked plan is printed loudly per round |
| AF-13 TTY stdin hangs | **Fixed** | `[ -t 0 ]` refusals with usage in resolve-plan-gate (exit 1) and reviewer-roster (exit 4, its uncertainty code); piped/CI paths unchanged |
| AF-14 §9.1 wrong citation | **Fixed** | Cites the inline Step-1 git program, reviewer-roster.sh, build-verify.sh |
| AF-15 README hook-table cell | **Fixed** | swift-build-verify listed under PostToolUse (Bash) |
| AF-16 stale MultiEdit matcher | **Fixed** | Both matchers now `Write|Edit` (hook harness re-run green) |
| AF-17 CHANGELOG provenance | **Fixed** | "History starts here" note under [2.2.4] |
| AF-18 undocumented kill switches | **Fixed** | `UNLEASHED_SENSITIVE_GUARD=off` / `UNLEASHED_STOP_GATE=off` added to the README table |
| AF-19 BrokenPipe traceback | **Fixed + tested** | Clean exit 0 with devnull re-point; regression test drives a real broken pipe |
| AF-20 silent malformed-JSON drop | **Fixed + tested** | `-32700` with `id: null`; pre-existing silent-drop test updated to the spec-correct contract |
| AF-21 notification-with-id hang | **Fixed + tested** | `notifications/initialized` returns `{}`; notification silence (no id) unchanged and still tested |
| AF-22 unused import | **Fixed** | `import re` removed |
| AF-23 MCP README content blocks | **Fixed** | `content[0]` corrected; `content[1]` documented |
| AF-24/25/26 INFO | **Accepted as documented** | Resource caps optional; Darwin-only store by design; §9 machine-check deferred to COREDEV-2654 |

**New finding fixed during remediation — AF-27 (MEDIUM): dead `Write(path)` grants.** While verifying
AF-8 against the permissions reference: since Claude Code 2.1.210, file-permission rules are consulted
for `Edit(path)`/`Read(path)` **only** — a `Write(path)` rule "is accepted but never consulted" (the
docs' own migration line: "Use `Edit(docs/**)` in place of `Write(docs/**)`"). Three shipped grants were
therefore dead on the CLI this plugin targets (≥ 2.1.219), quietly reintroducing the MIN-27 per-round
re-prompting they were built to fix: `Write(docs/planning/**)` (brainstorm), `Write(.agy-prompt-*.md)`
(gemini-review), `Write(.codex-prompt-*.md)` (codex-review). All three are now Edit-form, with the AF-8
carve-out attached where the grant covers `docs/planning/`.

**Operational note (user-directed, 2026-08-17):** codex has hit a weekly quota; reviews route through
the kimi harness for now. AF-12's fix makes that workable (`isolated-kimi-review.sh <prompt> <out>
<commit> [timeout] <plan>` — always pass the plan). The scripted quorum still records `codex=MISSING`
and the gate still refuses — by design, per the no-scripted-waiver contract; the kimi transcript is the
captured evidence for the user-directed workflow exception. The codex-review skill documents this flow.

**Deferred to COREDEV-2654 (functional gate changes needing the plan gate itself):** `bind-prompt.py
`--target` mode for gate-bearing non-plan reviews (AF-3b); relocating `.verdicts/` out of
`docs/planning/` (AF-8b); machine-checking §9 like §11 (AF-26); MCP resource caps (AF-24).

Validation after remediation: plugin-assembly ✅ · hooks-manifest ✅ · version-sync ✅ · hook harness
304/304 ✅ · MCP suite 231/231 ✅ (3 new regression tests) · scripts suite 1006 ✅ · shellcheck ✅ ·
`claude plugin validate` both modes ✅ (CLI 2.1.234) · callers-scan ✅ (exemptions manifest regenerated —
line-pinned records shifted with the edits) · `git diff --check` ✅. Two frozen manifests were
re-frozen for legitimate drift, payload-verified: the COREDEV-2619 transcript-path inventory
(line pins relocated by matching each frozen payload's bytes; the two AF-27 grant lines adopted their
amended bytes) and the §13 `brainstorm-summary` anchor (heading moved by the frontmatter comment).
The first run of the suite over the remediated tree was RED (16 failures) — every one a frozen-pin
drift check doing its job — and was fixed before anything was committed.

## Addendum 2 — two Codex review rounds against the remediation itself (PR #69)

The remediation above was reviewed by Codex twice. **Both rounds returned `REQUEST_CHANGES`, and
every finding was against the remediation's own code rather than the original audit's subject.** The
record is kept here because an audit whose remediation was itself defective is only accurate if it
says so.

### Round 1 (`bed8551`) — 3×P1 + 1×P2, all reproduced

| # | finding | disposition |
|---|---|---|
| P1 | The AF-19 broken-pipe fix did not survive a real teardown. Measured rc **120**, not 1 — CPython's exit-time flush. Wrapping `_log` in `try/except OSError` was **also** insufficient: the failed write leaves the text buffered for that flush | Fixed — log, and neutralise stderr only on failure |
| P1 | The Kimi plan operand was uncontained: `..`/absolute/empty spellings made the printed BASIS certify bytes outside the reviewed commit | Fixed — see round 2, which found the first repair still incomplete |
| P1 | The new `Bash(… isolated-kimi-review.sh *)` grant enabled **arbitrary out-of-tree overwrite**: that harness alone uses non-allocated `pty-capture`, which creates and truncates any single-linked path | Fixed at the permission layer — grant removed |
| P2 | The two validators still disagreed on stale tool names, and `Task` was told to become `Edit` rather than `Agent` | Fixed — mirrors assembly's folded set and per-tool reasons |

**A repair that was reverted.** The first attempt at the grant P1 changed `isolated-kimi-review.sh`
to require an allocated leaf. It broke **19 of that harness's own tests**, whose whole contract is
that it owns its output path. That was the wrong layer; Codex had already said to grant a wrapper
instead. Reverted, and the grant removed instead. `capture-kimi-review.sh` remains the follow-up
that would make a safe grant possible.

### Round 2 (`f21c902`) — 3×P1 + 2×P2 + 1×P3, all reproduced

| # | finding | disposition |
|---|---|---|
| P1 | The plan operand accepted **any tracked blob**, so the prompt and the certified target could disagree — `README.md` passed every mode/blob gate while the prompt named the audit | Fixed — the prompt must name the operand's repo-relative path |
| P1 | `git -C "$REPO"` does **not** anchor the repository: with `GIT_DIR`/`GIT_WORK_TREE` inherited, `--show-toplevel` still answered this checkout while every object lookup resolved in another repository. **Introduced by round 1's own fix**, which moved the digest to git objects | Fixed — selection variables cleared before the first `git`, and the resolved gitdir proved to belong to the checkout |
| P1 | A **full** stderr pipe still blocked the protocol. `_log` handled a failed write, but a blocking pipe never raises — the server stalled before a queued `ping`; draining stderr released it | Fixed — logging is non-blocking and lossy under back-pressure; diagnostics are droppable, the protocol is not |
| P2 | Whitespace bypassed stale-tool validation entirely: `\tTask\t`, `Task `, `Edit\n` validated with **neither problem nor warning**, because the padding breaks the exact-matcher grammar and the token is then classified as a regex — matching nothing at runtime | Fixed — control characters and non-space whitespace refused **before** classification; `KNOWN_TOOLS` also synced (it was 13 entries behind assembly) |
| P2 | This audit record was not updated for round 1 | Fixed by this addendum |
| P3 | The claim "every remaining grant is exercised by its body" was **not literal** — `Bash(command -v agy)` sat in gemini-review's frontmatter with zero body occurrences | Fixed — grant removed; the body's real preflight is `preflight-agy.sh`, which does the check internally |

### What both rounds confirmed

Nothing found in either round produces a wrong verdict or a corrupted gate. Round 2 also confirmed
the grant removal was **sufficient**: the remaining non-allocated `pty-capture` callers
(`audit-codex.sh`, `preflight-agy.sh`) allocate their own leaves and are not caller-controlled.

### Still open

`agents/modern-standards-planner.md:44` continues to show the raw, uncontained
`review-verdict.py snapshot` call. It sits inside a digest-frozen callers-scan migration region;
editing it broke eight tests, so it was deferred. **Codex's judgment, stated in both rounds, is that
deferring it is the wrong release boundary** — the live instruction stays unsafe, and the region
should be re-anchored deliberately with its tests. That decision is the maintainer's.
