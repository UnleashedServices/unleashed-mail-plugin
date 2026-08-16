# UnleashedMail — Claude Code Plugin v2.8.0

A multi-agent development plugin for **UnleashedMail**, a native macOS 15+ email client supporting Gmail and Microsoft Graph, built with Swift 6, SwiftUI, AppKit, WKWebView, GRDB.swift (SQLCipher), and MVVM architecture.

**21 agents · 21 skills · 0 commands · 1 MCP server**

> v2.2.0 introduces [`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md) — the source of truth for cross-agent boundaries (release contract, plan-implement gate, data→logic→ui handoff, AI pipeline ownership, code review pipeline, CI pinning, MCP tool prefixes, mandatory project gates). When two agents disagree about a boundary, the contracts doc wins.

## What's New

### v2.8.0

- **The plugin-state base store (`COREDEV-2617`)** — a shell that never receives `CLAUDE_PLUGIN_DATA`
  (a git hook, an ordinary terminal, a zsh Bash tool) now discovers the plugin-data base from a store
  each publisher records under `~/.claude/unleashed-mail/bases/`. Entry names are an injective
  encoding of the base value, so different bases never collide and a disagreement surfaces as a
  visible `conflict` rather than a silent second state directory. All five resolver copies
  (`paths.sh`, `marker.sh`, `log.sh`, `context.sh`, `agent-env-bridge.sh`) consult it; the bridge
  reads and never publishes. Darwin arms only — the Linux arms wait on the CI primitive probe.
  Proved by **a mutant suite that RUNS the plan's obligation table**: 125 rows executed as
  spec-vs-mutant tests in both bash 3.2.57 and zsh 5.9, on top of the 32 behavioural tests that
  demonstrate the capability end to end. Also fixed en route: a pre-existing zsh path-derivation
  defect in `context.sh` reachable from the swift-reviewer fence.

### v2.7.1

- **Seven review passes over the 2.7.0 permission and transcript surface (`COREDEV-2642`)** — 40+ findings
  remediated, each with a proof that fails when the fix is reverted. The ones that changed observable
  behaviour: a prompt naming a path that merely *shares the checkout's prefix* (`…/Unleashed Mail` vs
  `…/Unleashed MailTests/…`) was silently rewritten to a path that does not exist, so the reviewer read
  nothing while the round still validated; a plan over 64 KiB could never be persisted, because the
  bound-snapshot digest was taken through a cap meant for small sidecars; and `pr-review` could approve
  a PR having inspected **nothing**, because a stale local base branch made the changeset empty.
  Reviewer identity is now allocator-attested rather than parsed from the filename, the plan and prompt
  bindings are mandatory rather than skippable, and gate state is written and read through a
  descriptor walk so a swapped path component cannot redirect it.
  **Expect new refusals, not failures:** a stale/advanced base branch, a transcript missing
  `.planbytes`/`.promptsha256`, or a symlinked path component now stop a round instead of quietly
  degrading it.

### v2.7.0

- **Model-invocable skill grants narrowed from wildcards to exact entrypoints (`COREDEV-2642`)** — remediation of four independent reviews over the permission surface v2.6.7 shipped. `Bash(python3 …/scripts/*)`, `Bash(codex *)`, `Bash(agy *)` and `Bash(git *)` are gone from every model-invocable skill, replaced by exact wrapper scripts (`audit-codex.sh`, `preflight-agy.sh`, `changeset.sh`, plus five extracted capture/persistence helpers); bare `Write`/`Agent` are now `Write(docs/planning/**)` and enumerated `Agent(<type>)`. `validate-plugin-assembly.py` now rejects broad write/VCS/agent grants on any model-reachable skill — it found 17 further instances across 8 knowledge skills. Several fail-open gaps in the transcript-freshness and cleanup gates were also closed.
  **Breaking for direct callers:** `pty-capture.py` now requires an out-path (no more shared `/tmp/pty-out.txt` default); both review recipes require a per-round prompt file (`.codex-prompt-${TICKET}r${ROUND}.md` / `.agy-prompt-${TICKET}r${ROUND}.md`) instead of a shared `.codex-prompt.md` / `.agy-prompt.md`; the gemini arm's default model is now `gemini-3.6-flash-high`. See the CHANGELOG for the full breakdown, including which of the underlying tickets did and did not clear the mandatory plan-review gate.

### v2.6.7

- **Per-run transcript paths and freshness (`COREDEV-2619`)** — reviewer captures are atomically allocated, threaded unchanged through review and synthesis, and bound to per-capture launch records so stale output cannot satisfy a later run; a one-shot release tool cleans only the closed 39-file leak manifest and its nine empty parents.

### v2.6.6

- **`AGENT_CONTRACTS.md` §13 narrowed to client-facing output** (`COREDEV-2605`) — a **scope narrowing, not a relaxation.** §13's scope is now a parseable four-column table binding each surface to its producer and to a repository **anchor**; the five capture-roster reviewers are `out` because their output is machine-consumed and governed by their own contracts, which are unchanged and still mandatory.
  The payload-region invariant moves verbatim to **§5**, and the blocked-handoff prefix gets its own **§14**.

### v2.6.5

- **Plugin state no longer splits across two directories** (`COREDEV-2617`) — `CLAUDE_PLUGIN_DATA` is
  exported to hooks and MCP subprocesses but **not** to an ordinary shell, so anything written outside a
  hook landed in a *second* store (`~/.claude/unleashed-mail`) that the hooks' store never saw. An
  unresolved base now **persists nothing**: path primitives return a poisoned, non-root sentinel
  (`/dev/null/unresolved-plugin-base` — every path beneath a character device is `ENOTDIR`, so an
  unguarded caller fails harmlessly instead of composing `/logs`), writers become no-ops, and one
  diagnostic per process says so. **State written before this fix may still live in the second
  directory** — see the CHANGELOG for how to find it.

### v2.6.4

- **Reviewer isolation** (`COREDEV-2607`) — a plan review once *implemented* the plan it was reviewing,
  modifying 6 shipped scripts. [`scripts/review/isolated-agy-review.sh`](scripts/review/isolated-agy-review.sh)
  now runs the `agy` reviewer against a disposable detached checkout and **fails the round** if the real
  working tree changed. `agy` has no read-only flag — four candidates were tested and all four wrote
  files — so the fix isolates rather than constrains.
- **Secret redaction closes the Unicode fold residual** (`COREDEV-2609`) — U+0130 / U+0131 / U+017F /
  U+212A now ride in the secret *payload* class in both redactors. The *anchor* is deliberately left
  narrow: widening an unanchored prefix is what corrupted prose before.

### v2.6.3

- **CI now proves the plugin LOADS, not just that it validates (COREDEV-2598).** A new
  `load-check` job installs the checkout's **own bytes** into a scratch config and asserts the plugin
  reaches an enabled state, that the bundled MCP server completes an `initialize`/`tools/list`
  handshake **driven from its own installed `.mcp.json` declaration**, and that the hook manifest is
  loadable. Reproduced first: the obvious recipe git-clones `main` and reports success — a green check
  over the wrong bytes — so byte identity is proved by a per-run sentinel rather than a version number.
- **Two live shell-primitive bugs fixed (COREDEV-2600).** The PreCompact hook leaked
  `integer expression expected` to stderr on an oversized round directory, breaking the fail-open
  invariant; and `marker_mtime` branched on `uname == Darwin`, so on FreeBSD it returned its failure
  sentinel and the stop-quality gate **skipped entirely**. Both reproduced before fixing. The
  plugin-data base path is now single-sourced in `scripts/lib/paths.sh`, with every caller keeping an
  inline fallback so a missing file can never abort a hook.
- **A plan approval now survives the worktree move the docs mandate (COREDEV-2603).** The verdict
  artifact bound approval to an absolute path, so gating in one worktree and implementing in another
  failed the gate on a genuine approval with byte-identical plan content. Identity is now
  repo-relative (`schemaVersion` 3), and the required ordering — create the worktree **first** — is
  documented on all five surfaces an operator can enter through.

### v2.6.2

- **Redactor defects fixed, and the two implementations are now gated as equivalent
  (COREDEV-2597).** `hook_redact_pii` no longer corrupts ordinary prose — `task-oriented`,
  `~500ms`, `~40/60 split` and Swift's `~Copyable` all survive intact — and **five leak classes are
  closed**: Unicode whitespace in the api-key/bearer slots, newline-spanning secrets (`sed` is
  line-oriented and the fold ran after the rules), the compound form where `/Users/…` over-consumed
  and ate the `api` anchor, a *routable* address preserved entirely by the email exemption, and a real
  username leaked by the tilde exemption. The `sk-`/`pk_` boundary is now asymmetric so
  `OPENAI_KEY_sk-proj-…` redacts while `orders_pk_customer_id_idx` survives. Equivalence between the
  shell and Python redactors is enforced by a new CI job on **both** `ubuntu-latest` and
  `macos-latest`, because one root cause inverts between GNU and BSD `tr`.

### v2.6.1

- **Agent output style (COREDEV-2602).** New `AGENT_CONTRACTS.md` §13 adapts ten output rules from
  `ayghri/i-have-adhd` (MIT, pinned). Four are adapted with carve-outs and one restated, because this
  plugin's output is mostly consumed by software — a rule that shortens a findings array or moves a
  `Status:` line is a correctness regression, not concision.
- Adds the **payload-region invariant**: between `Status:` and the final fenced JSON block, nothing but
  detail fields and blank lines. This is the review parser's actual behaviour, verified by execution.

### v2.6.0

- **Opus 5 alignment (COREDEV-2583).** Requires **Claude Code ≥ 2.1.219** (Opus 5's floor); CI now pins
  2.1.220.
- **`effort: xhigh` is pinned on every agent and every skill** (42 assets) and enforced by CI. Previously
  *nothing* set `effort`, so every asset ran at whatever the session carried — including `low`. Note the
  pin is an override in both directions, and `CLAUDE_CODE_EFFORT_LEVEL` still outranks it.
- **Model tiering is now three tiers, set by consequence rather than cost.** `security-reviewer`,
  `prompt-review` and `concurrency-reviewer` move to `opus`; the orchestrator and implementation agents
  stay `inherit`; first-pass reviewers, personas and fixed-scope managers stay `sonnet`.
- **Validator fixes.** `model: opus[1m]` and the other long-context aliases now validate (they were
  rejected, blocking long context). `MultiEdit` is hard-rejected as a removed tool; `TaskOutput` and
  `EnterPlanMode` are no longer false-rejected as typos. Skills get frontmatter key validation for the
  first time, derived from the pinned runtime schema. A new warnings channel reports keys Claude Code
  ignores for plugin sub-agents without failing the build.
- **Docs.** The subagent spawn-depth dependency is declared in AGENT_CONTRACTS §5, and four verified
  documentation defects are corrected and gated by tests.

### v2.5.3

Correctness-audit remediation (COREDEV-2525) — 49 findings across the plugin's own assets, none of which
the shipped validators caught. Highlights: the review-synthesizer MCP now rejects tilde/home paths and
refuses to scope real findings against the demo changeset (closing two gate fail-opens); the `/implement`
Design Gate binds `$ARGUMENTS` through a quoted heredoc (no shell injection); the plan-review skills
pre-clean their fixed `/tmp` transcript paths so a stale previous-round APPROVE can't satisfy the gate;
eight auto-triggering knowledge skills no longer pre-approve unscoped `Bash`; `swift-reviewer` bridges
`CLAUDE_PLUGIN_DATA` so its capture pipeline resolves the same dir the hooks write to; and the validators
gained real coverage (model-tier alignment, the six-copy reviewer roster, hook `matcher`-key typos, agent
`skills:`/`.mcp.json` path resolution, manifest-description + CHANGELOG counts). No agents/skills added
(counts stay 21 · 21 · 0 · 1).

### v2.5.2

Consumer-install fix for the Plan Review Gate (COREDEV-2504). The plan-gate script references in agent/skill
bodies used the shell-fallback spelling `${CLAUDE_PLUGIN_ROOT:-.}`, which Claude Code does **not** substitute
(only the exact `${CLAUDE_PLUGIN_ROOT}` token is substituted inline) — so it reached the shell literally and
resolved to `.` (the consumer app repo, which ships none of these scripts), making every reviewer read as
"missing" and the fail-closed gate un-passable in any consumer install. All 8 sites are back to the bare
token (correcting a v2.5.1 F6 regression), `codex-review`'s pty timeout is raised 600→1200 s to survive
`xhigh` runs, and a mutation-proved doc-gate test now enforces the exact-token convention going forward.

### v2.5.1

Quality/review-gate fail-open remediation (COREDEV-2503). A v2.5.0 audit found fail-opens in the very gates
this plugin ships; all 14 are closed and mutation-proved: the `review-verdict` captureId dual-review bypass,
the review-synthesizer backslash/`..` traversal fail-opens, the sensitive-file guard's O(n²) parser and
quote-blindness (replaced by one structured linear lexer with a corrected exit-code contract), the Stop-gate
sentinel now keyed per-session, and secure-IO / validator / doc-consistency fixes. Every fix ships with a
regression test that fails when reverted.

### v2.5.0

The Plan Review Gate hardening release — the gate is now usable end-to-end and cannot be talked out of
its own guarantees.

- **Plan Review Gate, usable and hardened (COREDEV-2492).** `/implement <feature|path>` resolves to *the*
  tracked plan (exact-stem match; a bare substring must be named), refuses any plan outside
  `docs/planning/` (realpath containment closes the `" "`/`.`/`..`/symlink/symlinked-root/same-basename
  bypasses that let a stray argument or an out-of-tree file satisfy the gate), and verifies a
  plan-digest-bound Combined-verdict artifact before code is written. That artifact demands a non-empty,
  real-SHA-256, **distinct** transcript per reviewer — by capture path or wrapper capture-id, so two
  genuine reviews with identical text aren't rejected and one review can't stand in for two — a validated
  combined verdict, and the mandatory gemini+codex identities, enforced identically at write and verify.
- **The `WAIVED` promise dropped, not faked (COREDEV-2493).** `AGENT_CONTRACTS.md` §2 had promised a
  user-authorized scripted waiver that nothing implemented and nothing could; it now documents the
  recovery that actually exists. `agy` review timeouts raised so a real multi-file plan review stops
  dying at the 5-minute default.
- **Correctness + CI hardening (COREDEV-2494).** `swift-lint-check.sh` now honours every `swiftlint:disable`
  form (region / `:next` / `:this` / `:previous` / `all`), ignores prose and typo'd directives, and no
  longer flags IUO types (`Registry!`, `Canvas!`) as force operations — 15/15 sampled real app files were
  false positives before. `pty-capture.py` runs on macOS system Python 3.9 again (a new py3.9 CI job
  guards it), the gitleaks exemption is commit-scoped (no permanent blind spot), and `alpha` is now
  gated by CI + history-aware secret scanning.
- **Review tooling on Codex `gpt-5.6-sol` @ `xhigh` (COREDEV-2495).** Every codex review call forces
  `-c model_reasoning_effort=xhigh`, resilient to the config reset the 5.6 upgrade introduced.
- Built on the v2.4.x plugin-audit remediation (Epic COREDEV-2485, 17 PRs) already integrated on `alpha`.

### v2.4.2

- **Hook-manifest integrity gate (COREDEV-2338)** — new [`scripts/validate-hooks.py`](scripts/validate-hooks.py) statically validates `hooks/hooks.json` so a declared hook can't silently fail to fire. It checks every event name against the supported Claude Code set (hard-fail on an unknown/typo'd event), requires simple `Tool|Tool` matchers to reference real tools (catches `Bsh` / `Write|Edti`) while compile-checking grouped regexes like `^(Read|Write)$` (not falsely rejected), requires every `command` to resolve to an existing non-empty `scripts/<file>`, and `bash -n`-parses each referenced script. Wired into `plugin-ci.yml` (`--strict --require-manifest`, before the existing behavioral harness) and `pre-commit-checks.sh` (warn mode). Reviewed with Codex (converged over three rounds). No agents/skills/commands added (counts stay 21 · 18 · 3 · 1).

### v2.4.1

- **Host-app documentation sync (COREDEV-2335)** — corrected seven stale/contradictory spots where the plugin's docs/agents had drifted from the host app (`Unleashed Mail`); each was independently verified against both repos and adversarially cross-checked. Plugin-only scope (no app-repo edits); no agents/skills/commands added (counts stay 21 · 18 · 3 · 1).
  - **SwiftLint gate** now documented as the app's two-pronged form — changed-file `swiftlint --strict <files>` **plus** whole-repo `swiftlint lint --strict --baseline swiftlint-baseline.json` (the committed baseline suppresses the pre-existing `NSRegularExpression` backlog — COREDEV-2290) — replacing the bare `swiftlint --strict` that would have promoted the whole baselined backlog to errors.
  - **Build-number automation** reworded to a **Run Script Build Phase on the app target** (install/Archive builds only), **not** a Scheme Pre-Action (a Pre-Action bumps one archive too late — see `docs/VERSIONING.md`); current build corrected to `1.02.260601`, with `Config/Base.xcconfig` flagged authoritative.
  - **Email-detail dual-implementation** guidance dropped — `SimpleEmailWebView` is the sole renderer (`EmailWebView` was removed).
  - **Commit policy** made mandatory — every commit carries a `COREDEV-XXXX` ticket key (was documented as "optional").
  - **Review commands** — bare workspace names (`/gemini-review`, `/codex-review`, `/create-feature-plan`) documented as canonical, with the plugin's `/unleashed-mail:*` forms as the bundled alias; stale `v2.2.2` self-references corrected.
  - **`set -o pipefail`** added to piped `xcodebuild` blocks (`implement` / `pr-review` + four skill/agent examples) so a failing build/test can't be masked by `| tail`.
  - **Synthesizer test count** corrected `78` → `159`.
  - (An eighth audit finding — the reviewer Output-Contract capture claim — was already resolved by COREDEV-2328 in 2.4.0 and needed no change.)

### v2.4.0

- **`prompt-review` — a 5th specialist reviewer (GARI prompt / call-site safety).** A read-only static reviewer of AI prompts and provider call sites (jailbreak/injection surface, missing refusal paths, format/context leaks, unsanitized ingress of untrusted email/web content, inline prompts outside `PromptRegistry`, unscoped tools, PII-in-logs), fully wired into the `swift-reviewer` panel and the deterministic `review-synthesizer` pipeline (new **`ai-safety`** category family + `prompt-review` ownership). **Agent count: 21** (was 20). (COREDEV-2329 / COREDEV-2330)
- **Cross-family AI-safety ↔ security consolidation** — overlapping `prompt-review` and security/correctness findings on the *same lines* now merge into one `prompt-review`-owned row (category-level `_OWNERSHIP_MERGE_PAIRS`), never dropping a fix and never hiding a co-located security blocker. (COREDEV-2332)
- **Reviewer-capture round binding** — a `SubagentStart` producer hook freezes each reviewer's round at spawn (keyed by `agent_id`) so captures land in their *originating* cycle under interleaved timing; observe-only and fail-open. (COREDEV-2326)
- **Reviewer Output-Contract status persisted through capture** — each reviewer's `COMPLETE | BLOCKED | PARTIAL` status is written to a sibling `<agent>.status` JSON, so a captured `BLOCKED` reviewer can't read as a clean `[]` pass. (COREDEV-2328)
- **`ai-engineer` doc-drift fix** — removed the non-existent `HTTPBasedAIProvider` / `AIToolDefinition` symbols from the agent docs, `CLAUDE.md`, and contracts; examples now use the real `BaseAIProvider` + `AIProviderProtocol` / `AITool` + `ToolHandlerProtocol` model, with `HTTPBasedAIProvider` relabelled **PLANNED** (COREDEV-1837). (COREDEV-2331)

### v2.3.1

- **Plan-review synthesis skill** — new [`/unleashed-mail:review-synthesis`](skills/review-synthesis/SKILL.md) reads the two captured plan-review transcripts and emits one auditable **Combined verdict** block (`APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES | DISAGREEMENT`) with Agreement / Disagreement / Minority report / Risk register / Confidence. Each transcript path is carried as one opaque `--reviewer "<name>=<STATUS>:<path>"` argument (**at this version the two paths were fixed; per-run allocated paths arrived in v2.6.7** — this historical entry had been rewritten to describe the later behaviour, so the file contradicted itself about when per-run paths existed); a one-approve / one-reject split is surfaced as `DISAGREEMENT` rather than averaged, and a missing/empty transcript can never claim `APPROVE`. Kept **distinct** from the code-review `synthesize_review` MCP tool (5 JSON arrays, `APPROVE_WITH_SUGGESTIONS`). Wired into [`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md) §2 as plan-review step 3a.
- **Reviewer Output-Contract status enum** — the four specialist reviewers now end with a `## Output Contract` status (`COMPLETE | BLOCKED | PARTIAL`) that is **orthogonal** to their findings, so a reviewer that *couldn't run* returns `BLOCKED` + `[]` instead of an empty `[]` that reads as a clean pass. `swift-reviewer` Step 5 reads status **first**: `BLOCKED` → NEEDS DISCUSSION (the explicit form of a did-not-run uncertainty — **not** a `verification` blocker); `PARTIAL` → keep completed-scope findings + a non-gating `verification` warning naming the un-reviewed files. No synthesizer (Python) change.
- **Decision-support option tables in `/unleashed-mail:brainstorm`** — a new design-phase **Step 4b** presents 2–4 options for a genuine architectural fork in a comparison table (with an unleashed-specific **Parity-Impact** column, S/M/L effort, a `**(Recommended)**` row, no emoji), then calls `AskUserQuestion` to record the chosen fork before the plan document is written. `AskUserQuestion` is added to the command's `allowed-tools` (a command-interface change).
- **Skill count: 18** (was 17) — adds `review-synthesis`.

### v2.3.0

- **Deterministic review-synthesizer MCP server** — the plugin now bundles a local, zero-dependency stdio MCP server ([`mcp/review-synthesizer/`](mcp/review-synthesizer/), declared in [`.mcp.json`](.mcp.json)) that performs the review orchestrator's Step-5 synthesis **in code** instead of LLM prose. It validates the sub-reviewers' JSON findings, scope-filters (changeset + `structural-pipeline`), and dedups via category-family + line-overlap with cross-family ownership routing — **cluster-and-cross-link, never silently dropping a fix** — then returns a provisional verdict plus `blockersToVerify`. `swift-reviewer` calls it via `mcp__plugin_unleashed-mail_review-synthesizer__synthesize_review`, then owns the verify gate. The server has **no repo access, no network, no secrets** — pure compute. See [MCP Servers](#mcp-servers-1).
- **Review-agent overhaul** — the four sub-reviewers now emit a structured **JSON findings array** (`severity · confidence · sourceAgent · category · file · line · lineEnd · scope · finding · evidence · fix`) instead of a prose table, so `swift-reviewer` cross-references and deduplicates on `file:line`, not paraphrase. `concurrency-reviewer` broadened to the **correctness owner** (logic/error-handling); provider-parity, test-coverage, and build/lint/test emit gating `verification` rows; a **verify gate** confirms each blocker against the code before REQUEST CHANGES (unconfirmable → NEEDS DISCUSSION); and **structural-pipeline** review widens scope to the whole pipeline (not just the diff) when key subsystems — API calls, AI flows, syncs — change. Review agents are tiered by consequence (AGENT_CONTRACTS §11): `security-reviewer`, `prompt-review` and `concurrency-reviewer` pin `opus`; `accessibility-auditor` and `ux-perf-reviewer` pin `sonnet`.
- **The full stdlib-only unit suite** for the synthesizer ([`mcp/review-synthesizer/tests/`](mcp/review-synthesizer/tests/), stdlib `unittest`, no deps), discovered — not a hardcoded count — covering schema validation/quarantine, dedup/ownership/scope/verdict, render, and the full JSON-RPC protocol via subprocess. Run: `python3 -m unittest discover -s mcp/review-synthesizer/tests`.
- **Reviewed to convergence** by Codex (`gpt-5.5`) and Gemini (`gemini-3.1-pro`) over four rounds until both approved. A new [`CHANGELOG.md`](CHANGELOG.md) tracks releases going forward.

### v2.2.4

- **One shared PTY wrapper for both review CLIs** — new committed script [`scripts/pty-capture.py`](scripts/pty-capture.py) runs any command inside a pseudo-terminal, ANSI-strips its output, writes it to `<out-path>`, and propagates the child's exit code. It generalizes the agy-only `pty.openpty()` recipe that previously lived inline in `gemini-review`. Interface: `pty-capture.py <out-path> -- <command> [args...]`.
- **`codex-review` now routes through the wrapper** — `codex exec` emits **0 bytes** when piped, redirected, or backgrounded (the recurring "STDN"/nothing-captured failure). Running every invocation as `pty-capture.py <out> -- codex exec …` guarantees capture with **no `-o` flag to forget**; pairs with the existing `Monitor` guidance.
- **`gemini-review` points at the same committed script** — its agy invocations now call `${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py`; the inline reference recipe is removed so there is one canonical, command-agnostic script both skills invoke.
- **Wrapper hardened per PR review (gemini + codex)** — uses `pty.fork()` so the child acquires a real **controlling terminal** (`/dev/tty` works instead of `ENXIO`-ing terminal-oriented CLIs), converts a wrapper-level **`SIGTERM` into `SystemExit`** so the child is reaped rather than orphaned, and **normalizes PTY `\r\n` → `\n`** in the captured output.

### v2.2.3

- **SwiftLint "fix-when-touched" rule disambiguated** — the rule "fix violations in files you modify" (`CLAUDE.md`, `code-simplifier` Pass 4) read as a conflict with `jira-manager`'s "ticket out-of-scope violations" guidance. "Out-of-scope" now explicitly means **files the change does not modify**; any violation in a modified file is fixed as part of the change and never deferred to a ticket — consistent with the `swiftlint --strict` merge gate.
- **Legacy-regex migration exception** — the one carve-out from fix-when-touched: legacy `NSRegularExpression` ("old regex") is **not** migrated inline. It's owned by the dedicated Swift `Regex`/`RegexBuilder` migration (`.claude/rules/swift-regex-sendable.md`); piecemeal conversion risks Sendable-conformance regressions. If a lint rule flags a site in a touched file, it's suppressed with `// swiftlint:disable:next no_legacy_nsregex - <ticket>` (the ` - ` rationale delimiter keeps `--strict` green; a trailing `//` does not) and tracked under the migration epic. Documented in `CLAUDE.md`, `code-simplifier`, and `jira-manager`.
- **`swiftlint-config` skill gains `no_legacy_nsregex`** — a sample custom rule flagging `NSRegularExpression`, with guidance to introduce it alongside a SwiftLint **baseline** (`swiftlint lint --strict --baseline swiftlint-baseline.json`; baselines are native to SwiftLint ≥ 0.55) so the existing backlog (hundreds of sites) doesn't break the strict gate while the migration burns it down.

### v2.2.2

- **Review skills promoted into the plugin** — `gemini-review`, `codex-review`, and `create-feature-plan` were previously workspace-only skills referenced by the plugin's docs but not bundled. They now ship with the plugin under their namespaced slash commands: `/unleashed-mail:gemini-review`, `/unleashed-mail:codex-review`, `/unleashed-mail:create-feature-plan`.
- **gemini-review rewritten for Antigravity (`agy`)** — replaces the retired `gemini-cli` binary, removes obsolete `-m`/`-o` flags, documents the TTY-only "text drip" print mode and the **Python `pty.openpty()` wrapper recipe** required to capture agy's output from non-TTY contexts (Bash automation, CI scripts).
- **codex-review portability fix** — removed user-specific absolute path from the "working directory" note; references the workspace root abstractly so the skill is portable across installs.
- **All plugin docs renamed slash-command refs** — `CLAUDE.md`, `README.md`, `AGENT_CONTRACTS.md`, `agents/modern-standards-planner.md` now reference the namespaced commands.
- **Skill count: 17** (was 14) — adds `gemini-review`, `codex-review`, `create-feature-plan`.

### v2.2.1

- **Antigravity CLI migration** — Google retired Gemini CLI in May 2026; the dual-review gate now invokes Antigravity CLI (binary `agy`, model `gemini-3.1-pro`). Agent docs (`modern-standards-planner`, `release-manager`), `AGENT_CONTRACTS.md`, and `CLAUDE.md` updated.
- **Model name updated** — `gemini-3.1-pro` graduated out of preview. References to `gemini-3.1-pro-preview` removed.

### v2.2.0

- **New file: [`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md)** — formalizes cross-agent boundaries. Source of truth when agents disagree on workflow contracts.
- **20 agents (up from 15)** — adds `tester`, `code-simplifier`, `docs-engineer`, `ci-engineer`, `release-manager`.
- **14 skills (up from 10)** — adds `error-handling`, `accessibility-patterns`, `swiftlint-config`, `spm-management`.
- **Subagent dispatcher fix** — uses `Agent` (Claude Code's correct tool name), not `Task`. Fixed in 5 agent + 4 command/skill frontmatters.
- **MCP portability** — Atlassian and Context7 whitelist all three install prefixes (standalone, VSCode-shipped, plugin-namespaced) so the plugin works regardless of MCP install.
- **Project rule alignment** with the consumer project's `.claude/rules/*.md` system: `AccountScopedServiceProvider` for service resolution, `@State` (not computed property) for views, Curator design tokens, COREDEV-1578 Sendable matrix, image budget tiers, two-layer HTML pipeline (`HTMLSanitizer` + `HTMLRenderPipeline`), inline AI safety (`AISafetyPipeline` is PLANNED, not shipped), `BaseAIProvider` for Apple Intelligence, snake_case SQL columns, append-only migrations.
- **Project knowledge corrected fleet-wide** — quoted scheme name (`"Unleashed Mail"`), `xcodebuild test` everywhere (this is `.xcodeproj`, not SwiftPM), version scheme `MAJOR.MINORRELEASE.YYMMBB` per `docs/VERSIONING.md`, branch convention `1.0X/feature-name`, version-bump automation acknowledged.
- **Dangerous recommendations removed** — cert pinning for Google/Microsoft OAuth (they rotate certs), sandbox-disable workaround for Keychain prompts, append-only migrations no longer paired with rollback scripts.
- **Cross-agent inconsistencies resolved** — GitHub Actions SHA-pinned everywhere, `jira-manager` ticket-before-code rule with manual fallback, diagnostic agents have explicit Ask-before checkpoints for entitlements/auth/dependencies/toolbar/keyboard.
- **Hooks/scripts portability** — `test-runner.sh` removed from Bash hook (was running full test suite after every Bash command), null-delimited PII scan, no `xargs -a` (BSD-incompatible), no `<<<` here-strings (require writable `/tmp`), explicit refspec for `git fetch` so CI works on fresh clones.
- **`jira-manager` knows the Atlassian site** — embedded `https://unleashedservices.atlassian.net/` and project key `COREDEV` so it stops using placeholder URLs.
- **`smb-entrepreneur` and `enterprise-stakeholder`** — gain Grep+Glob so they can search project docs while stress-testing proposals.

15 rounds of Codex review iteration before merge. See PR #2 for the audit detail.

## Installation

This repo is both the plugin **and** its own marketplace (the repo ships [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)).

```bash
# 1. Add the marketplace (one-time)
claude plugin marketplace add UnleashedServices/unleashed-mail-plugin

# 2. Install the plugin
claude plugin install unleashed-mail

# 3. Restart Claude Code so the new agents/skills/commands load
```

To pull a newer version after upstream changes:

```bash
claude plugin marketplace update unleashedservices-unleashed-mail-plugin
claude plugin update unleashed-mail
# Restart Claude Code
```

> **Migrating from the old `npranson-unleashed-mail-plugin` marketplace?** The marketplace was
> renamed to `UnleashedServices/unleashed-mail-plugin`, and Claude Code's plugin-rename migration
> does not cover marketplace-name changes — an install keyed as
> `unleashed-mail@npranson-unleashed-mail-plugin` will stop resolving. Re-point it once:
>
> ```bash
> claude plugin marketplace remove npranson-unleashed-mail-plugin
> claude plugin marketplace add UnleashedServices/unleashed-mail-plugin
> claude plugin install unleashed-mail   # reinstall under the new marketplace
> # Restart Claude Code
> ```

For local development against an unpushed clone:

```bash
claude --plugin-dir /path/to/unleashed-mail-plugin   # session-scoped, no marketplace required
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          SLASH COMMANDS                                      │
│    /unleashed-mail:brainstorm → /unleashed-mail:implement → /unleashed-mail:pr-review │
└────────┬────────────────────┬───────────────────────────┬────────────────────┘
         │                    │                           │
         ▼                    ▼                           ▼
 ┌────────────────┐  ┌────────────────┐  ┌──────────────────────────────────────┐
│  PLANNING +    │  │ IMPLEMENTATION │  │      REVIEW ORCHESTRATOR             │
 │  PERSONAS      │  │  AGENTS        │  │      (swift-reviewer)                │
 │                │  │                │  │                                      │
 │ modern-        │  │ db-engineer    │  │  ┌─ security-reviewer                │
 │ standards-     │  │ logic-engineer │  │  ├─ concurrency-reviewer             │
 │ planner        │  │ ui-engineer    │  │  ├─ ux-perf-reviewer                 │
 │ smb-           │  │ ai-engineer    │  │  ├─ accessibility-auditor            │
 │ entrepreneur   │  │ tester         │  │  ├─ prompt-review                    │
│ enterprise-    │  │code-simplifier │  │   └─ provider parity audit            │
 │ stakeholder    │  │                │  │                                      │
 └────────────────┘  └────────────────┘  └──────────────────────────────────────┘
         │                    │                           │
         ▼                    ▼                           ▼
 ┌────────────────────────────────┐  ┌──────────────────────────────────────────┐
 │  PROJECT MANAGEMENT            │  │  DIAGNOSTIC (on-demand, Ask-before)      │
 │  jira-manager (parallel)       │  │  xcode-build-fixer                       │
 │  docs-engineer                 │  │  graph-api-debugger                      │
 │  ci-engineer                   │  │                                          │
 │  release-manager               │  │                                          │
 └────────────────────────────────┘  └──────────────────────────────────────────┘
         │                    │                           │
         ▼                    ▼                           ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │                     AUTO-TRIGGERING SKILLS (18)                              │
 │  swift-tdd · swiftui-mvvm · grdb-patterns · macos-debugging ·                │
 │  webview-composer · keychain-security · gmail-api · graph-api ·              │
 │  provider-parity · agent-orchestration · error-handling ·                    │
 │  accessibility-patterns · swiftlint-config · spm-management ·                │
 │  gemini-review · codex-review · create-feature-plan · review-synthesis       │
 └──────────────────────────────────────────────────────────────────────────────┘
```

> After the five reviewers return their JSON findings, `swift-reviewer` calls the bundled **`review-synthesizer`** MCP server (`synthesize_review`) for deterministic dedup / scope / ownership-merge — cluster-and-cross-link, never silently dropping a fix — then runs its **verify gate** (confirm each blocker against the code) before issuing the verdict. See [MCP Servers](#mcp-servers-1).

## Agents (21)

### Review Agents (run in parallel via orchestrator)

| Agent | Specialization |
|---|---|
| `swift-reviewer` | **Orchestrator** — spawns all 5 reviewers, runs parity audit, calls the deterministic `synthesize_review` MCP tool to dedup/merge their JSON findings, then owns the **verify gate** + unified verdict |
| `security-reviewer` | Credential exposure, OAuth/MSAL flaws, WKWebView injection (HTMLSanitizer + HTMLRenderPipeline), CI pipeline, entitlements, SQLCipher |
| `concurrency-reviewer` | Data races, actor isolation, async/await, GRDB threading, COREDEV-1578 Sendable matrix, deprecated APIs (Swift 6 enforced) |
| `ux-perf-reviewer` | Main-thread responsiveness, SwiftUI rendering, query perf, image budget tiers, perceived speed, error UX |
| `accessibility-auditor` | VoiceOver, keyboard nav, Dynamic Type, color contrast, focus management, Curator design system, dual-impl a11y parity |
| `prompt-review` | AI prompt/call-site safety (static, read-only): jailbreak/injection surface, missing refusal paths, format/context leaks, unsanitized ingress, inline prompts outside PromptRegistry, unscoped tools, PII-in-logs |

### Coding & Implementation Agents

| Agent | Domain |
|---|---|
| `db-engineer` | GRDB 7+ schema (snake_case columns), SQLCipher, migrations (CRITICAL/DEFERRABLE), Record types, async observation, append-only |
| `logic-engineer` | Service protocols, Gmail + Graph impls via `AccountScopedServiceProvider`, ViewModels, AI pipeline routing, sync, mocks |
| `ui-engineer` | SwiftUI views (macOS 15+), AppKit bridging, WKWebView composer, Curator design tokens, `@State`-resolved services, a11y, dual-impl updates |
| `ai-engineer` | GARI AI pipeline — cloud providers (`BaseAIProvider` + `AIProviderProtocol`) + Apple Intelligence, ToolRegistry, PromptRegistry, inline safety (PIIRedactor + LLMInputSanitizer), AIAgentPipeline (unified `HTTPBasedAIProvider` base PLANNED, COREDEV-1837) |
| `tester` | Test strategy, MockServices.swift extension, `KeychainManager.resetInMemoryStore()` discipline, account-isolation invariants |
| `code-simplifier` | 16-pass conservative simplification with deletion guardrails (selectors, IBActions, reflection-loaded code preserved) |

### Stakeholder Persona Agents (used during brainstorming)

| Agent | Perspective |
|---|---|
| `smb-entrepreneur` | SMB founder (15-person firm, 150 emails/day) — evaluates speed, workflow, cost, keyboard-first UX |
| `enterprise-stakeholder` | IT director (500-5000 person org) — evaluates compliance, admin control, scale, SSO/MDM, security |

### Planning, Tracking & Diagnostic Agents

| Agent | Purpose |
|---|---|
| `modern-standards-planner` | Researches current best practices via Context7 + web search; cites `.claude/rules/` as standards source; gates plans on dual review |
| `jira-manager` | Ticket lifecycle — creation, Epic linking, milestone updates against `https://unleashedservices.atlassian.net/` (project key `COREDEV`) |
| `docs-engineer` | README, API docs (DocC via xcodebuild), user guides, planning docs, architecture, roadmap |
| `xcode-build-fixer` | Diagnoses and proposes fixes for Xcode build / package resolution failures (Ask-before for dependency changes) |
| `graph-api-debugger` | Microsoft Graph / MSAL auth troubleshooting (Ask-before for auth/entitlements edits) |
| `ci-engineer` | GitHub Actions workflows (SHA-pinned), Xcode Cloud, build automation, coordination with the `bump-build-number.sh` Run Script Build Phase + `post-archive-commit-bump.sh` Post-Action |
| `release-manager` | `MAJOR.MINORRELEASE.YYMMBB` versioning, App Store / TestFlight submission, defers BB-byte to automation |

## Skills (18) — Auto-activate based on context

| Skill | Triggers When |
|---|---|
| `swift-tdd` | Implementing features, writing tests, refactoring (uses `xcodebuild test`) |
| `swiftui-mvvm` | Building views, view models, navigation, state management |
| `grdb-patterns` | Database models, migrations, queries, observation |
| `macos-debugging` | Crashes, memory leaks, performance issues, build failures |
| `webview-composer` | Email composition UI, contenteditable, JS bridge code |
| `keychain-security` | OAuth tokens, credential storage, encryption |
| `gmail-api-integration` | Gmail email fetching, sending, labels, Pub/Sub, OAuth flows |
| `microsoft-graph-integration` | Outlook/M365 email, MSAL auth (added via Xcode UI), Graph webhooks, delta queries |
| `provider-parity` | Any code touching provider-specific implementations or protocols |
| `agent-orchestration` | Coordinating multi-agent workflows, determining parallel execution strategy |
| `error-handling` | Error patterns, do-catch, Result types, error propagation |
| `accessibility-patterns` | Accessibility implementation patterns for macOS/SwiftUI |
| `swiftlint-config` | SwiftLint rule configuration, violation remediation |
| `spm-management` | Xcode-managed package dependencies (NOT root SwiftPM), version pinning, security audit |
| `gemini-review` | Plan/debug review via Antigravity CLI (`agy`); routes through the shared [`scripts/pty-capture.py`](scripts/pty-capture.py) PTY wrapper for guaranteed non-TTY output capture |
| `codex-review` | Read-only Codex CLI review for plans, debug, and post-implementation audits; routes through the same shared [`scripts/pty-capture.py`](scripts/pty-capture.py) wrapper so output is never lost when piped/backgrounded |
| `create-feature-plan` | Scaffolds a `FEATURE_NAME_PLAN.md` under `docs/planning/` using the project template |
| `review-synthesis` | Combines the two captured plan-review transcripts (gemini + codex) into one auditable **Combined verdict** block; read-only, run after both reviews and before implementation |

## Workflow skills (3)

These three orchestration workflows ship as **skills** (custom commands have merged into skills) — you
invoke them exactly as before, and Claude can now also trigger them itself when the task calls for one:

| Skill | Usage |
|---|---|
| `/unleashed-mail:brainstorm` | Design feature → Context7 research → spec → plan document → Jira ticket |
| `/unleashed-mail:implement` | Plan → db → logic → ui (layered agents) → multi-agent review → Jira updates |
| `/unleashed-mail:pr-review` | All 5 reviewers (incl. prompt-review) + parity in parallel → unified verdict → Jira logged |

## Parallel Execution

Agents are designed for **flexible parallel execution** in any combination. The `agent-orchestration` skill defines dependency rules:

- **Always parallel**: All review agents run simultaneously. `jira-manager` runs alongside everything.
- **Layered coding**: `db-engineer` → `logic-engineer` → `ui-engineer` (chained by dependency, but each can parallelize with `jira-manager`)
- **Any subset**: Request any combination — "just run security and accessibility reviewers", "only the db-engineer", etc.
- **Reactive agents**: `xcode-build-fixer` and `graph-api-debugger` fire on demand, not as part of standard pipeline.

## Mandatory Processes (from project CLAUDE.md)

The plugin enforces these non-negotiable processes:

1. **Planning document** — `docs/planning/FEATURE_NAME_PLAN.md` for every feature (no exceptions)
2. **Plan review gate** — Every plan or debug session must be reviewed by **both** `/gemini-review` (Antigravity CLI `agy`) and `/codex-review` before implementation. Both must produce APPROVE / APPROVE_WITH_NOTES; iterate (typically 2–6 rounds) until both converge. (Bare workspace names are canonical; the plugin also bundles them as `/unleashed-mail:gemini-review` / `/unleashed-mail:codex-review`.)
3. **Context7 usage** — Mandatory for code generation, setup, config, API docs lookup
4. **Jira ticket hygiene** — Every change tracked at `https://unleashedservices.atlassian.net/` (project key `COREDEV`), updated throughout, with Epic association
5. **Provider parity** — Gmail ↔ Graph implementations stay in sync; views/ViewModels obtain providers via `AccountScopedServiceProvider`, never concrete types
6. **Accessibility** — Every UI element gets a11y support (mandatory per CLAUDE.md); use Curator design tokens
7. **Security invariants** — SQLCipher encryption, Keychain-only tokens, `account_email` filtering, PIIRedactor, two-layer HTML sanitization (`HTMLSanitizer` + `HTMLRenderPipeline`)
8. **SwiftLint compliance** — Fix violations in any file you modify (functions ≤50 lines, files ≤600 lines); violations in *unmodified* files are ticketed, not fixed in-flight. Lone exception: legacy `NSRegularExpression` is left for the Swift `Regex`/`RegexBuilder` migration (suppressed + ticketed, not converted inline)
9. **Dual implementations** — Changes applied to both variants (native + WebKit compose, docked + floating AI). *Email detail is no longer dual — `SimpleEmailWebView` is the sole renderer.*
10. **Ask-before checkpoints** — Don't auto-edit Xcode project structure, entitlements, Info.plist, app lifecycle, menus, toolbar, keyboard shortcuts, auth/token handling, or framework/SwiftPM dependencies. Surface for user approval first.

See [`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md) for the cross-agent boundaries that operationalize these processes.

## Hooks

The plugin registers hooks on 10 Claude Code events (see [`hooks/hooks.json`](hooks/hooks.json)). All are **fail-open** — a hook error never blocks your work — and every telemetry/enforcement hook has an environment kill switch — including `swift-lint-check.sh`, which emits `decision:block` and arms the Stop gate, so it is the one that most needs an escape (`UNLEASHED_LINT_CHECK=off`). State (markers, logs, snapshots) lives under the plugin data dir (`~/.claude/unleashed-mail/`), never in your repo.

| Event | Script | Behavior | Default | Kill switch |
|---|---|---|---|---|
| PreToolUse (Write/Edit/Bash) | `sensitive-file-guard.sh` | Flags edits to sensitive files (Keychain/OAuth/entitlements/DB/WebView). `ask` = permission prompt (non-interactive / `dontAsk` / `-p` contexts **deny** the operation); `warn` = advisory only | `ask` | `UNLEASHED_SENSITIVE_GUARD_MODE` = `ask`/`warn`/`off` |
| PostToolUse (Write/Edit) | `swift-lint-check.sh` | Swift syntax + SwiftLint + `try!`/`as!`/token-log checks. Feeds findings back to the model via the PostToolUse JSON contract (`decision:block` reason / `additionalContext`) | on | `UNLEASHED_LINT_CHECK=off` |
| PostToolUse (Write/Edit, Bash) | `swift-build-verify.sh` | Build/test-command advisories via `additionalContext` | on | `UNLEASHED_FAILURE_LOG=off` (telemetry only) |
| Stop | `stop-quality-marker-gate.sh` | Blocks the turn once (via `decision:block`+`reason`) if a lint-fail marker is set — fail-open, TTL/commit-guarded. `enforce` = block; `warn` = silent log | `enforce` | `UNLEASHED_STOP_GATE_MODE` = `enforce`/`warn`/`off` |
| StopFailure | `stop-failure-log.sh` | Observe-only failure telemetry (class only, no PII) | on | `UNLEASHED_FAILURE_LOG=off` |
| PermissionDenied | `permission-denied-log.sh` | Observe-only denial telemetry | on | `UNLEASHED_DENY_LOG=off` |
| PostToolUseFailure (Bash) | `build-failure-log.sh` | Observe-only build-failure telemetry | on | `UNLEASHED_FAILURE_LOG=off` |
| PreCompact | `precompact-snapshot.sh` | Snapshots work context before compaction | on | `UNLEASHED_COMPACT_SNAPSHOT=off` |
| SessionStart | `sessionstart-restore.sh` | Restores the pre-compaction context as `additionalContext` | on | `UNLEASHED_COMPACT_RESTORE=off` |
| SubagentStart | `capture-reviewer-round-start.sh` | Binds a review round to each spawned reviewer | on | `UNLEASHED_CAPTURE_REVIEWERS=off`, `UNLEASHED_REVIEW_ROUND_SIGNAL=off` |
| SubagentStop | `capture-reviewer-verdict.sh` | Captures each reviewer's findings for the synthesizer | on | `UNLEASHED_CAPTURE_REVIEWERS=off` |

> **PostToolUse hooks run *after* the tool call**, so they cannot undo a write — they feed findings back to the model (a top-level `{"decision":"block","reason":…}` or `additionalContext`). The Stop gate in `enforce` mode is the only hook that blocks a turn.

## MCP Servers (1)

The plugin bundles one local, zero-dependency **stdio MCP server**, declared in [`.mcp.json`](.mcp.json) and launched by Claude Code as a subprocess:

| Server | Tool | Purpose |
|---|---|---|
| `review-synthesizer` | `synthesize_review` | Deterministic Step-5 synthesis for the [code-review pipeline](AGENT_CONTRACTS.md). Validates the sub-reviewers' JSON findings, filters to changed + `structural-pipeline` scope, dedups via category-family + line-overlap with cross-family ownership routing (**cluster-and-cross-link — never silently drops a fix**), and returns a provisional verdict + `blockersToVerify`. `swift-reviewer` then confirms each blocker against the code (the verify gate) and issues the final verdict. |

- **Pure compute** — no repo access, no network, no secrets. The repo-reading half (the verify gate) stays in `swift-reviewer`, which is the only side that can open `file:line`.
- **Agent tool name:** `mcp__plugin_unleashed-mail_review-synthesizer__synthesize_review` (inherited by `swift-reviewer`, whose `tools:` list includes it). The orchestrator falls back to the documented rules in [`mcp/review-synthesizer/README.md`](mcp/review-synthesizer/README.md) if the server is unavailable.
- **Source + tests:** [`mcp/review-synthesizer/`](mcp/review-synthesizer/) — run `python3 -m unittest discover -s mcp/review-synthesizer/tests` (the full stdlib-only suite, discovered by `unittest`).

## Baked-In Knowledge

Agents come pre-loaded with Context7 research for the stack:

- **GRDB 7+**: Async read/write, `ValueObservation.trackingConstantRegion`, Swift 6 concurrency safety, `for try await` observation
- **SwiftUI macOS 15+**: `@Observable` + `@Environment`, `NavigationSplitView`, `ContentUnavailableView`, `@AccessibilityFocusState`, modern toolbar API
- **MSAL**: Public client desktop flow, silent/interactive acquisition, keychain access groups
- **Context7 library IDs**: Pre-resolved (`/groue/grdb.swift`, `/azuread/microsoft-authentication-library-for-objc`, `/websites/developer_apple_swiftui`, `/avdlee/swiftui-agent-skill`) — agents skip the resolve step

## License

MIT
