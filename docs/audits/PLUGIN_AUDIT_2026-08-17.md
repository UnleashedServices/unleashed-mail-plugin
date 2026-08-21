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

### Round 3 (`85d242e`) — 3×P1 + 2×P2, all reproduced

| # | finding | disposition |
|---|---|---|
| P1 | The prompt/target binding was a **substring** test and bypassable four ways: a `.bak` suffix, an `old-` path prefix, the path quoted in a sentence that then said "actual review: README.md", and a prompt naming two documents | Fixed — exactly ONE anchored declaration line whose whole value equals the operand; all four bypasses refused, three legitimate spellings accepted |
| P1 | **Git configuration injection**, missed by round 2's fix. `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` survived the hand-picked unset list and injected `core.hooksPath`, so `disposable_checkout`'s `git checkout` would fire an attacker `post-checkout` **inside the private tree before `TREE_BASELINE` was captured** — mutation the baseline then records as pristine | Fixed — the whole `GIT_*` namespace is enumerated and cleared (an indexed, unbounded family cannot be covered by a fixed list), and `disposable_checkout` additionally runs every command with `-c core.hooksPath=/dev/null` |
| P1 | A full stderr pipe **still** exited 120. Round 2's `print(..., flush=True)` left the failed non-blocking write buffered in `TextIOWrapper`; the interpreter's EOF flush retried it and died — the ping succeeded and the process still exited 120 | Fixed — diagnostics go through raw `os.write`, which has no buffer to leave anything in |
| P2 | Zero-width and default-ignorable Unicode (U+200B, U+FEFF, U+2060, U+180E) still bypassed matcher validation, because `str.isspace()` is false for them | Fixed — rejection is by Unicode CATEGORY (Cc/Cf/Co/Cs), not an enumerated blocklist the next codepoint outruns |
| P2 | **The round-2 regression test did not test what it claimed.** `_basis_of()` read the `BASIS plan = <path>` diagnostic rather than the `BASIS=<digest>` summary, so it reported equality even when the digests differed; and it poisoned toward this same repository, where the bytes are identical, so there was nothing to detect | Fixed — a genuinely separate repository with different plan bytes, the poison derived from the fixture's own env, both runs required to reach the clean summary, digests compared, plus a vacuity check that the decoy really does digest differently |

**The lesson this round records.** Round 2 claimed both new tests were "proven discriminating by
mutation" — and they were, in the sense that the mutant failed them. But one of them failed for a
reason unrelated to its oracle. *A mutation that turns a test red does not prove the test measures
the right thing.* The rewritten test's oracle is the digest itself, so the same mutation now fails it
for the reason the test exists.

### Cumulative

Three rounds, fourteen findings, every one reproduced. Round 2 contained two defects created by
round 1's repairs; round 3 contained one created by round 2's. Rounds continue until one returns
clean **and** that clean round reproduces on identical bytes — on this ticket family two double
approvals have already failed reproduction, and both re-runs found real defects the approving runs
had certified clean.

### Round 4 (`2343736`) — 2×P1 + 3×P2, all reproduced

| # | finding | disposition |
|---|---|---|
| P1 | The anchored binding scanned every line without tracking Markdown fences, so a declaration QUOTED as an example was operative while the real instruction redirected elsewhere; two identical declarations also passed (the check was `len(set)`, not `len`); and a `PLAN_REL` containing a backtick could not be represented at all | Fixed — fenced and indented regions blanked before scanning, `len(found) != 1` refused, and one wrapping quote pair stripped so any value is representable |
| P1 | The disposable checkout still consumed **executable** configuration. `-c core.hooksPath=/dev/null` disables hooks only; global/system config still defines `filter.*`, `core.attributesFile` and `insteadOf`, and a smudge filter runs a shell command over bytes entering the tree — reproduced, a filter EXECUTED with hooks already disabled | Fixed — `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` point at `/dev/null`, `init --template=` is empty, and `core.attributesFile` is pinned; the reproduction now shows zero filter executions |
| P2 | `_log()` set `O_NONBLOCK` on **inherited fd 2**, and `F_SETFL` mutates the open file DESCRIPTION, which is shared across fork/dup — so the server changed its launcher's stderr | Fixed — and note the obvious repair FAILED: duping the descriptor and setting the flag on the copy changes the same description, measured. Writability is now TESTED with `select` and no flag is changed at all |
| P2 | NFKC-equivalent matchers still validated cleanly: full-width `Ｅｄｉｔ` and `ＭｕｌｔｉＥｄｉｔ` are LETTERS, so the category guard did not touch them | Fixed — a non-canonical matcher whose NFKC form would satisfy the exact grammar is refused as a homoglyph |
| P2 | **The rewritten BASIS test still had an incomplete oracle.** `clean == poisoned` and `clean != decoy` are both satisfied by an implementation that consistently digests the WRONG file | Fixed — the test now asserts the digest EQUALS the reviewed plan's blob, computed independently; verified against a mutant that digests README.md, which the previous oracle passed |

**Three consecutive rounds found a defect in the test written to prove the previous round's fix.**
Round 2's test read the wrong line; round 3's compared the right line but only for inequality;
round 4's finally asserts the positive fact. The through-line is that each oracle was chosen to
detect the defect I had just fixed, rather than to state what must be TRUE — and "not wrong in the
way I was wrong last time" is a weaker claim than it sounds.

### Round 5 (`326f4cc`) — 2×P1 + 2×P2, all reproduced

| # | finding | disposition |
|---|---|---|
| P1 | The fence stripper ignored opening-fence length and trailing text, and tested the marker before indentation — so a four-space-indented ``` opened a fence, a shorter nested fence closed an outer one, and ``` followed by text counted as a close. Three prompts with a quoted declaration and an operative redirect were accepted | Fixed — real fence rules: character, opening run length, indentation < 4, and a close requiring an equal-or-longer run with nothing after it. An unclosed fence swallows the remainder, which fails safe |
| P1 | **`disposable_checkout` was still exposed in the agy and codex harnesses.** `GIT_CONFIG_GLOBAL`/`SYSTEM=/dev/null` do not remove `GIT_CONFIG_COUNT`, whose indexed pairs arrive as command-line config and outrank both — and with `url.<ext::cmd>.insteadOf` plus `protocol.ext.allow` that is **code execution through the fetch transport**, reproduced. Only the kimi harness cleared the namespace, while all three call the shared helper | Fixed at the shared boundary — `_tf_sanitize_git_env` clears the whole `GIT_*` namespace inside `disposable_checkout`, so every caller is covered and the next one cannot forget |
| P2 | VARIATION SELECTOR-16 and COMBINING GRAPHEME JOINER are category `Mn` and NFKC preserves them, so they passed both guards and produced matchers that match nothing | Fixed — default-ignorable codepoints are rejected by RANGE (the Unicode property is not exposed by `unicodedata`, and a name list is outrun by the next codepoint). `Mn` is not rejected wholesale: `café.*` still validates |
| P2 | **The BASIS oracle still did not prove the digest follows the operand.** Every positive assertion used `DEFAULT_PLAN`, and the only alternate operand was refused before the digest — so an implementation that always hashes the default passed | Fixed — an accepted committed ALTERNATE plan with distinct bytes, its own declaring prompt, and its independently computed digest asserted. Verified against the always-default mutant, which the previous oracle passed |

**No logging finding this round** — `/dev/null`, a full 64 KiB stderr pipe and a closed stderr all
returned rc 0 with the ping and `-32700` replies intact. That surface is now settled after three
rounds of defects.

### Cumulative after five rounds

Twenty-three findings, every one reproduced. Four of the five rounds found at least one defect
created by the previous round's repair, and rounds 2-5 each found a defect in the TEST written to
prove the previous round's fix. The tests now assert positive facts — that the digest equals the
reviewed plan's blob, and that it CHANGES when the operand changes — rather than only that the
previous defect is absent.

### Round 6 (`6fe87f2`) — 2×P1 + 2×P2, all reproduced

| # | finding | disposition |
|---|---|---|
| P1 | **Sanitisation ran too late.** `_tf_sanitize_git_env` was called from `disposable_checkout`, but every harness runs `git rev-parse --show-toplevel`, `git status --porcelain` and `tree_fingerprint` first — and inherited config executes there: `core.fsmonitor=/bin/echo` spawned a child on a plain `git status` in **both shells**, and selection poisoning made `--show-toplevel` answer a different repository, so the round fingerprinted and reviewed a checkout nobody asked for | Fixed — the sanitiser now runs **at source time**. All four consumers source this file before their first git call, so every one is covered and the next harness cannot forget. Verified in bash and zsh: zero child processes, correct repository |
| P1 | The hand-written Markdown classifier accepted three more mismatches — a fenced block inside a list container, an HTML comment, and space-then-tab indentation — and the list case was the **refuse→accept regression** I had asked to be hunted: blanking merged two raw declarations into one acceptable one | Fixed by **deleting the parser**. The declaration is now the first line, byte-exactly `Plan under review: <path>`; nothing else in the prompt is inspected. Four rounds of hardening a prose scanner lost every time, because deciding which prose is "operative" means reimplementing CommonMark, and a partial CommonMark is a bypass generator |
| P2 | Default-ignorable rejection was gated on category `Mn`, which was itself a bypass: U+2065 and U+FFF0 are `Cn`, U+3164 HANGUL FILLER is `Lo`, and all three are invisible and match nothing | Fixed — the property is checked regardless of category, and the range table widened. Eight codepoints across four categories refused; `café.*` and `naïve|Edit` still accepted |
| P2 | The BASIS oracle still permitted a legacy-prefix implementation: **both** accepted operands lived under `docs/planning/`, so hard-coding that prefix and using only the basename passed — and would have failed on the real `docs/audits/` operand this branch is reviewed with | Fixed — the alternate plan moved to `docs/audits/`, so the two accepted operands differ in directory. Verified against both the legacy-prefix and always-default mutants |

**A scope statement, because the rigid format changes what is guaranteed.** The binding now
guarantees that the DECLARATION and the BASIS cannot disagree, and that the declaration cannot be
forged by formatting. It does **not** police the body: a prompt whose first line declares A and
whose prose then discusses B is ACCEPTED, because the BASIS honestly certifies A. Two cases the old
scanner refused are therefore accepted now. That is the correct answer under this property rather
than a regression — what the reviewer chooses to read has never been knowable from the harness,
which is what the BASIS line's own header comment has said since round 1. Policing prose is the
thing that kept failing.

### Round 7 (`3be042e`) — 2×P1 + 2×P2, all reproduced

| # | finding | disposition |
|---|---|---|
| P1 | **`changeset.sh` reviewed a different checkout** under inherited selection variables — a git-invoking script that never sourced the boundary at all | Fixed as a CLASS: `changeset.sh`, `persist-verdict.sh`, `resolve-plan-gate.sh` and `snapshot-plan.sh` all source the boundary before their first git. Codex named one; the same exposure existed in four |
| P1 | **"Byte-exact" was not true.** `.decode("utf-8","replace")` maps any invalid byte to U+FFFD, so `\xff` aliased a real U+FFFD filename and was accepted as the same declaration; `.rstrip()` accepted extra trailing spaces while making a filename that ENDS in a space impossible to declare | Fixed — the comparison is raw bytes against `os.fsencode(want)`, with only the intentional CRLF handling. Trailing spaces now refused, a space-terminated filename representable, `\xff` no longer aliases |
| P2 | **The source-time sanitiser failed OPEN.** It read `$(env)` through a here-document, which needs a temp file; where that was denied the shell printed an error, the loop never ran, every `GIT_*` survived — and the source still returned 0. My claim that all four consumers source before their first git was also **false**: Kimi ran git at line 95 and sourced at line 210 | Fixed — the sanitiser is allocation-free (shell name expansion, no temp file, no subshell), VERIFIES afterwards and exits non-zero if anything survives, and Kimi now sources the boundary before its first git |
| P2 | A basename-only BASIS implementation still passed: the two accepted operands had **different basenames**, so resolving the leaf against any directory worked | Fixed — the alternate plan now shares the default's basename in a different directory, forcing the digest to depend on the full path. Verified against all three wrong implementations proposed in rounds 4-7 |

**Codex judged the round-6 scope trade sound**, unprompted by me beyond asking: *"accepting a
declaration for A whose body discusses B is appropriate because this gate binds the declaration to
BASIS, not prose semantics."* It also independently confirmed the default-ignorable range table
matches Node's `Default_Ignorable_Code_Point` property exactly — missing 0, extra 0.

### Round 8 (`911069d`) — 1×P1 + 2×P2, all reproduced

| # | finding | disposition |
|---|---|---|
| P1 | **`containment.py` inherited `GIT_DIR`/`GIT_WORK_TREE`**, and since `--show-toplevel` IS the containment boundary, `/etc/hosts` resolved as "inside the repository" and would have been handed to the reviewer — defeating `audit-codex.sh`'s disclosure boundary. It is reached directly from Python and never passed through the shell boundary | Fixed — the `git` call runs with a `GIT_*`-stripped environment. Poisoned and control runs both refuse; legitimate operands still resolve |
| P2 | **The fail-closed verifier could be disabled by its own scratch variable.** A caller pre-declaring `readonly _tf_left=""` blocked every assignment; the verifier read empty, concluded "nothing survived" and returned 0 with a readonly `GIT_DIR` still set. Readonly `GIT_*` alone already failed closed — it was the NAME COLLISION that opened it | Fixed — and my first repair kept a scratch name and the bypass **survived it**, measured. The check now uses no variable name at all: positional parameters inside a subshell, which cannot be made readonly and cannot disturb the caller's `$@` |
| P2 | The BASIS fixture still did not force the full path: the two operands shared a basename but differed in the immediate parent, so an implementation using the last TWO components passed | Fixed — the alternate now shares basename AND immediate parent, differing only in a higher ancestor. Verified against all four wrong implementations proposed in rounds 4-8 |

**The verifier fix is the campaign's clearest example of measuring the outcome rather than the
mechanism.** My first repair looked right, parsed, and passed shellcheck — and the reproduction
showed the bypass still open, because the harness I first wrote measured `env | grep -c '^GIT_'`
inside a shell that `exit` had already killed, and `readonly` without `export` never appears in
`env` at all. Only after rewriting the probe to capture the shell's exit status **from outside**
did the real behaviour appear.

### Round 9 (`1dd5dd1`) — 1×P1 + 2×P2; two fixed, one RECORDED AS A RESIDUAL

| # | finding | disposition |
|---|---|---|
| P1 | **`callers_scan.py` trusted caller-controlled git selection.** `git -C <root>` selects a DIRECTORY; it does not neutralise the environment, and `GIT_INDEX_FILE` pointing at another worktree's index made `ls-files` report a different file set — so the scan PASSED against a manifest it should have rejected, which is the scanner's entire purpose | Fixed — the call runs with a `GIT_*`-stripped environment, matching `containment.py`. Poisoned and control now agree (both reject the filtered manifest), and the unfiltered manifest still passes |
| P2 | The BASIS fixture still did not force the full path: with only two fixed operands, a mutant branching on the first path component satisfied both | Fixed by defeating the CLASS rather than adding a third sample. Any finite operand set can be special-cased, so the test now uses a third plan whose path is derived from the per-run scratch name — **unguessable at authoring time**. Verified against all five wrong implementations from rounds 4-9, including codex's own first-component branch |
| P2 | The verifier is fail-open through a **shadowed `eval`/`exit`** | **NOT FIXED — recorded as a residual (C3).** See below |

**Why the shadowed-builtin finding is recorded rather than fixed.** It reproduces exactly as
reported. But its premise is a parent that can `export -f eval` into our shell, and that parent
already has arbitrary code execution by a cheaper route — measured here: `BASH_ENV=<file>` ran code
*before any line of the script*, printing "ARBITRARY CODE RAN BEFORE ANY LINE OF THE SCRIPT" and
then letting the script proceed. So the finding demonstrates **no capability change over what its
own premise already grants**, which is precisely the disposition rule §4.2a-T TM-5 states and §28.1
records ("an exported function, a `PATH` executable, a crafted `declare -p` value and an imported
`BASH_SOURCE` are four carriers of one premise, and the premise is what was recorded").

Hardening it would also repeat a mistake this campaign already made: TM-2's first normative
consequence forbids adding an in-process guard against a same-uid parent on "raises the bar"
grounds, *because this ticket spent four separate rounds re-fixing one such guard as each round's
carrier was replaced by the next*. `builtin eval` is shadowable by a function named `builtin`; there
is no fixed point. **If the reviewer disagrees that the review harness inherits this threat model,
that is the argument to make — the disposition, not the reproduction, is what is in dispute.**

### Round 10 (`3450354`) — 2×P2, **no P1**

| # | finding | disposition |
|---|---|---|
| P2 | **My "last Python git consumer" claim was false**, and the caller-scan REFERENCE helper was poisonable: under a sibling worktree's index `load_final_tree()` silently inventoried 13 fewer files, while the "final tree matches an independent reference" proof stayed **green in both states** — so the reference it compared against was the poisoned one. Worse, the round-9 sanitisation could be **deleted with no focused regression failing** | Fixed — the helper strips `GIT_*` too, and a poison/control regression now covers **both** the helper and the production CLI. Verified load-bearing: deleting either sanitisation fails the test |
| P2 | The randomised BASIS operand still did not force full-path handling — an implementation stripping a leading component satisfied all three operands | Fixed — the random operand's **strict suffix is now another tracked plan with different bytes**, so any generic prefix-strip resolves the wrong file, while the prefix stays unguessable. Verified against six wrong implementations from rounds 4-10 |

**A claim withdrawn.** Earlier entries said the unguessable operand "defeats the class". It does not,
and codex is right to push back: no finite fixture can prove a property of an arbitrary
implementation, only sample it. What these operands do is defeat every *concrete* wrong
implementation proposed across seven rounds — basename-only, last-two-components, legacy-prefix,
always-default, first-component-branch and prefix-strip. That is a stronger sample, not a proof, and
the audit should not have said otherwise.

**The residual disposition is settled.** Codex, unprompted beyond being asked: *"Residual
disposition: agreed. I would not re-file the shadowed `eval`/`exit` carrier… A parent capable of
importing the shadow already controls code executed before the harness body."* It reproduced
`BASH_ENV` itself to check. It noted correctly that §4.2a-T is formally scoped to the store rather
than automatically governing the review harness — the reasoning transfers, the section's authority
does not, and that distinction is worth keeping.

### Round 11 (`fa27847`) — 1×P2, no P1

| # | finding | disposition |
|---|---|---|
| P2 | **The "load-bearing" poison regression could pass without exercising the sanitisers.** It depended on a sibling worktree index existing — and CI checks out with `fetch-depth: 0` and creates no worktrees, so on CI the test **skipped silently** ("OK (skipped=1)"), absent exactly where it matters most. Its oracle was also `len(control) == len(poisoned)` rather than inventory equality, so equal-sized but different file sets passed | Fixed — the test now **builds its own decoy repository and index**, so there is nothing to skip on (verified with every sibling index hidden: still runs), compares inventories **exactly**, and carries two vacuity checks that the decoy is actually distinguishable. Both sanitisations re-verified load-bearing |
| — | *Note, not filed as a finding:* all three positive BASIS operands shared one basename, so a resolver keyed on that basename could use the full path for it and strip otherwise | Closed anyway — a fourth operand with a **differing** basename. All seven concrete wrong implementations from rounds 4-11 now fail |

**The finding I had flagged myself.** I asked codex in the round-11 prompt whether the `skipTest`
was a hole. It was, and worse than I guessed: not merely *could* it skip, it skips on CI
specifically. That is the same shape as the campaign's recurring defect — a check that examines
nothing reads as coverage — and the fix is the same one that worked for the BASIS oracle: stop
depending on the environment to supply the adversarial condition, and construct it.

**Negative evidence codex recorded this round**, which is the first substantial body of it:
`helper control=197 poisoned=197 exact=True`; `production clean_rc=0 poisoned_rc=0`; the
production-tree Python git-consumer scan found only `containment.py` and `callers_scan.py`, both
stripping `GIT_*`; the binder compares raw bytes against `os.fsencode` and removes only a terminal
CR; and the audit's withdrawal paragraph correctly corrects the earlier "defeats the class"
language. Those are four claims of mine it checked rather than accepted.

### Round 12 (`385c1f3`) — APPROVE, **and the approval reproduced**

Round 12 returned `VERDICT: APPROVE` with no findings. On this ticket family that is a hypothesis,
not a result: two double approvals have previously failed reproduction on byte-identical input, and
both re-runs found real defects the approving runs had certified clean. So round 12 was **re-run at
the same commit with the same prompt bytes** (head `385c1f3`, prompt sha256 `3bfbb386…`, worktree
clean before and after).

**Both runs approved.** This is the first reproduction on this ticket that has held.

What the two rounds exercised, between them:

- **Decoy construction cannot fail silently** — the failure mode I asked to be attacked, one layer
  below the `skipTest` hole of round 11. A sandbox-denied `TemporaryDirectory`, a missing `git`, and
  a failing `git init` each produce `errors=1`; none skips and none passes. `check=True` on both git
  commands and an explicit assertion on the index file.
- **Both sanitisations remain load-bearing**, shown against a real sibling index:
  `unsanitized git inventory control=197 poisoned=184 exact=False`, while
  `helper control=197 poisoned=197 keys_exact=True contents_exact=True` and
  `production clean_rc=0 poisoned_rc=0`.
- **An eighth mutation boundary was raised and deliberately not filed**: a "keep the last four
  components" resolver survives all four operands but mishandles a five-component path. It is not a
  finding because the audit no longer claims a finite fixture proves anything about arbitrary
  implementations — the withdrawal from round 10 doing its job.
- Read-only validation: callers manifest up to date (412 records), both changed test files parse,
  assembly 21/21/0/1, hooks manifest 10 events / 12 invocations / 11 scripts, version-sync OK.

**Stated limits of this evidence.** Neither run could reach GitHub (`gh pr view` failed to connect
from the sandbox), so live PR/CI state is asserted from this machine, not by the reviewer. Neither
could run the write-heavy 1008-cell suite in a read-only sandbox; that is run here instead. A nested
independent reviewer could not initialise. None of that is evidence of anything either way, and it
is recorded so the approval is not read as broader than it is.

## Campaign summary

**Twelve rounds. Forty-one findings, every one reproduced before it was fixed.
(Counted from the per-round headings, which include round 2's audit-record P2. Earlier
paragraphs said 40; codex round 14 caught the discrepancy — the headings sum to 41.)** Trend:
4, 6, 5, 5, 4, 4, 4, 3, 3, 2, 1, 0.

Four of the twelve rounds found a defect created by the previous round's repair. Rounds 2-5 each
found a defect in the test written to prove the previous round's fix. The recurring shape was never
a missing check — it was **a check that could not fail**: an oracle comparing the wrong line, a
mutation that turned a test red for an unrelated reason, a regression that skipped on CI, a verifier
its own scratch name disabled, and a security boundary that failed open when a temp file could not
be allocated.

One finding was **declined and settled**: the shadowed-`eval`/`exit` carrier is recorded as a
residual, and the reviewer agreed after reproducing `BASH_ENV` itself. One claim was **withdrawn**:
no finite fixture "defeats the class".

### Round 13 (`385c1f3`, effort=**max**) — 1×P2. **The dual approval was a ceiling artifact.**

Rounds 12 and 12b both approved at `model_reasoning_effort=xhigh`. Round 13 re-ran the **same prompt
bytes** (sha256 `3bfbb386…`) against the **same tree** (`221d9ee6…`, worktree clean, verified before
and after) changing exactly one variable — effort `xhigh` → `max` — and returned `REQUEST_CHANGES`.

| # | finding | disposition |
|---|---|---|
| P2 | **The BASIS oracle never varied the COMMIT operand.** Every harness invocation passed the literal `HEAD`, and every expected digest was computed from `HEAD:` too — so an implementation that ignores `$SHA` and hard-codes `HEAD` satisfied all four path operands | Fixed — the fixture now makes a **second commit that changes the default plan's bytes**, and a cell runs the harness at the EARLIER sha and requires that commit's blob, with a vacuity check that the two commits' bytes actually differ. Verified: a `HEAD:`-hardcoding mutant now fails |

**What this says about the campaign's own method.** Eleven rounds of `xhigh` sampled the *path*
operand exhaustively — eight concrete wrong resolvers, culminating in an unguessable path whose
suffix is another tracked plan. Not one of them varied the *commit* operand. The blind spot was not
in the code under review; it was in the axis the fixture explored, and two clean rounds at the same
depth could not see it because they were the same search.

That is the campaign's recurring defect, one level up: **a check cannot find what it is not looking
for**, and repeating the same check does not change what it looks for. Two approvals at one depth
are evidence about that depth. The reproduction rule (run it again on identical bytes) tests
*stability*; it does not test *reach*.

**Method note for future gates on this repo:** a dual approval at one effort tier is not a clean
gate. Vary the tier before believing it — the cost here was one 20-minute round, and it found a real
sampling gap that twelve rounds had certified clean.

### Round 14 (`532ae12`, effort=max) — 3×P2 + 1×P3

Asked directly "**name any other axis the fixtures never vary**", the reviewer named two more and a
third fell out of them. That question was worth more than another operand mutant.

| # | finding | disposition |
|---|---|---|
| P2 | **The commit test bound the BASIS blob but not the checkout the reviewer sees.** A mutant computing the BASIS from the right commit while checking out `HEAD` passed the round-13 cell: `basis_oracle=PASS reviewer_bytes=WRONG` | Fixed — a `record-checkout` stub mode records `git rev-parse HEAD` and the plan digest **from inside the reviewer's own working directory**, and both must correspond to the requested commit |
| P2 | **Axis three: reviewer-process behaviour.** Every stub mode ended with an approving `printf`; no non-zero reviewer exit was ever sampled. **Axis four: the timeout**, hard-coded to 60 in every cell | Fixed — `fail-nonzero` and `slow` stub modes, `_run(timeout=…)` parameterised, and cells asserting `EXIT=7` and `EXIT=124` survive into the summary |
| P2 | **Axis five: prompt encoding.** The binder accepted a NUL, but bash command substitution silently DELETES it, so the reviewer receives different bytes than `PROMPT_SHA` digests (documented length 91, argv length 90, `bytes_equal=False`). `bind-prompt.py` already refused this for the plan skills; the kimi harness did not | Fixed — refused at the source, detected in python3 with a control proving ordinary prompts still pass |
| P3 | **The campaign totals in this document were arithmetically wrong** — the per-round headings sum to 41 through round 12 while the prose said 40 | Fixed, with the counting convention stated |

**Two mistakes of mine inside this round, both caught by running things.** First, the NUL guard was
written as `grep -qU $'\000'` — and bash cannot hold a NUL in a variable, so that compiles to an
EMPTY pattern matching every file: a guard that refuses everything and detects nothing. The control
caught it inverted (NUL file "ACCEPT", ordinary file "REFUSE"). Second, my first assertions for the
new exit-status and timeout cells demanded the absence of `TREE=clean` — but that token reports the
FINGERPRINT, not the round's success, and the harness was already behaving correctly. I would have
"fixed" working code to satisfy a wrong oracle.

And a third: the NUL guard shipped with **no test**, so a mutation check reported `TEST NOT FOUND`.
That is exactly the gap round 10 raised — a sanitiser that can be deleted with nothing failing —
repeated four rounds later. All four new cells are now mutation-verified.
