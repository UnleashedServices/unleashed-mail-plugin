# COREDEV-2873 — Guidance refresh: Claude 5.5 request shapes, Apple toolchain, Foundation Models, stale examples

**Ticket:** COREDEV-2873 · **Epic:** COREDEV-2485 · **Branch:** `feat/COREDEV-2873-guidance-refresh` · **Base:** `main` (`dd84d82`)
**Status:** Planning, revision 1
**Origin:** item (c) of the 2026-10-03 external audit. The maintainer agreed the order: COREDEV-2872 (item b),
then this, then COREDEV-2869 part 1 and M4.

## 0. Scope rule

**Guidance corrections only.** This plan changes what the plugin's agents and skills TELL an app developer,
plus one validator list and one CI pin that are themselves stale facts. It adds **no new test machinery**.
Every change is a correction to a stated fact or a missing warning, and each fact below was re-read from a
primary source on 2026-10-03. Where the audit was wrong, the correction is stated rather than silently
dropped (§2), because the audit's wording is what a reader of this plan will have seen first.

## 1. Verified facts (source, date)

| # | Fact | Source (2026-10-03) |
|---|------|---------------------|
| F1 | Current API IDs: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-fable-5-1`, `claude-haiku-4-5-20251001`. `claude-sonnet-5` is a **legacy** model, still available. | platform.claude.com, *Models overview* |
| F2 | API default effort: Opus 5.5 `medium`, Sonnet 5.5 `high`. Effort is set with `output_config.effort`. | *Models overview*; *Migrating to Claude Opus 5.5* |
| F3 | Opus 5.5 and Sonnet 5.5 each return **400** for: a thinking budget (`thinking: {"type":"enabled","budget_tokens":N}`), `thinking: {"type":"disabled"}`, non-default `temperature`/`top_p`/`top_k`, an assistant prefill, and a forced `tool_choice` (`any` or `tool`). | *Migrating to Claude Opus 5.5*; *Migrating to Claude Sonnet 5.5* ("five settings that return a 400 error") |
| F4 | Sonnet 5.5 only: `thinking: {"type":"between_tools"}` is its lowest thinking setting, accepted at `low`/`medium`/`high` effort and a 400 at `xhigh`/`max`; with it, a per-message effort change is a 400. Opus 5.5's thinking is always on. | *Migrating to Claude Sonnet 5.5* |
| F5 | The app (`UnleashedServices/UnleashedMail`, `main` `d9bdfc5d3`) USES Foundation Models: `Sources/Services/AI/Providers/AppleIntelligenceProvider.swift` is `@available(macOS 26.0, *)` and switches on `SystemLanguageModel.default.availability`. The model runs only on Apple Intelligence-capable hardware in supported regions. | the app repo (GitHub API); developer.apple.com, *Meet the Foundation Models framework* |
| F6 | The app's CI runs on `macos-26` runners and selects the NEWEST installed Xcode (`ls -d /Applications/Xcode*.app \| sort -V \| tail -1`); `MACOSX_DEPLOYMENT_TARGET = 15.0`; `SWIFT_VERSION = 6.0` (language mode). | the app's `.github/workflows/ci.yml`, `memory-budget.yml`, `project.pbxproj` |
| F7 | Xcode 27 (Swift 6.4) shipped 2026-09-14. | release coverage of Xcode 27 |
| F8 | Apple's April 28, 2026 upload rule: "built with Xcode 26 or later using an SDK for iOS 26, iPadOS 26, tvOS 26, visionOS 26, or watchOS 26". **macOS is not in it.** | developer.apple.com, *Upcoming requirements* |
| F9 | The Claude Code hooks reference lists 33 events (npm `latest` is 2.1.289); `scripts/validate-hooks.py` knows all but `DirectoryAdded`, `PreModelSwitch`, `PostModelSwitch`. | code.claude.com/docs/en/hooks; diff against the validator |

## 2. Corrections to the audit

* **Item 6 overstated:** "App Store uploads have required Xcode 26+ since April" does not apply to this macOS
  app (F8). The agents' toolchain text is still stale and self-contradictory, so it is corrected (§3.4) — as
  consistency, not as an App Store blocker.
* **Item 5 overstated:** `claude-sonnet-5` is legacy, not invalid (F1). The defect is that the guidance does
  not recommend the current model and does not warn about the request shapes that fail on 5.5 (F3).
* **Item 9 is an addition, not a correction:** no agent or skill mentions Foundation Models today, but the app
  uses it (F5), so the guidance should describe the app's EXISTING gating pattern for new code to follow.

## 3. Changes

### 3.1 `agents/ai-engineer.md` — Claude API guidance (priority 1)
* The provider example's `defaultModel` (`:78`, `"claude-sonnet-5"`) becomes `"claude-sonnet-5-5"` (F1),
  and the example request gains `output_config: {effort: ...}` (F2).
* A short **"Claude 5.5 request rules"** subsection lists F3's five 400s with what to do instead (adaptive
  thinking + effort; prompt instead of sampling; structured outputs instead of prefill; `tool_choice: auto`
  plus strict tools), and F4's Sonnet-only `between_tools` note. Stated as API facts with the source named,
  not as style advice.

### 3.2 `agents/prompt-review.md` — rubric (priority 1)
* A rubric item: at an AI call site targeting a 5.5 model, flag each F3 request shape as a finding (a request
  that will be rejected), citing the rule. Read-only reviewer; no tool or permission change.

### 3.3 `agents/ai-engineer.md` — Foundation Models (priority 1)
* Describe the app's existing pattern (F5): `@available(macOS 26.0, *)` on the provider, a switch over
  `SystemLanguageModel.default.availability` before use, and a fallback provider when unavailable (device not
  eligible, Apple Intelligence off, model not ready). New Foundation Models code must follow it.

### 3.4 Toolchain text — consistency (priority 2)
* `agents/ci-engineer.md` (`:17`, and the six `runs-on: macos-15` examples), `agents/xcode-build-fixer.md:60`
  ("Verify CI uses correct Xcode (16.3+)"), `agents/docs-engineer.md` (`:58`, `:258`): state F6 — `macos-26` runners, newest installed Xcode, deployment
  target macOS 15.0, Swift 6 language mode — instead of "Xcode 16.3+ / macos-15". Where a minimum Xcode must be
  named, say "the Xcode the app's CI selects", not a number that goes stale.
* `agents/concurrency-reviewer.md:140` ("macOS 15 SDK / Swift 6.3") is a DATED record of the COREDEV-1578
  audit's environment and stays as is.
* `agents/release-manager.md:73` ("Xcode 16.1.1, 2026-04-29") is likewise a dated empirical note and stays.

### 3.5 Stale examples (priority 2)
* `skills/brainstorm/SKILL.md:98`: "macOS 25" (never existed; 15 → 26) → the correct version for the sentence.
* `skills/microsoft-graph-integration/SKILL.md:222`: the subscription example's fixed `expirationDateTime`
  (`2025-04-01T00:00:00Z`, already past) → a value computed from now within Graph's maximum lifetime, with a
  comment, so the example never goes stale again.

### 3.6 Tooling facts (priority 2)
* `scripts/validate-hooks.py`: add `DirectoryAdded`, `PreModelSwitch`, `PostModelSwitch` to the known events
  (F9). A plugin using them today is rejected by the strict validator.
* `.github/workflows/plugin-ci.yml`: the Claude Code CLI pin (`CLAUDE_CODE_VERSION: 2.1.220`, at `:260` and
  `:530`) moves to the current `latest` dist-tag (2.1.289 on 2026-10-03, re-read with
  `npm view @anthropic-ai/claude-code version` at implementation time). The pin's own comment explains why it
  tracks `latest` rather than `stable`, and that reasoning is kept. No tarball checksum is pinned today; that
  is an existing follow-up and stays out of scope. This changes two job
  digests in `test_python39_floor.py`; they are re-pinned. If the newer CLI's authoritative `plugin validate`
  rejects anything, that is reported and fixed or the pin is held, never silenced.

## 4. Out of scope (separate decisions)

These change how the review gate itself behaves, so they are NOT folded in here:
* the reviewer models (Gemini 3.8 Flash as primary; a pinned Codex model) and agy's `--effort` flag;
* the bundled MCP server's protocol version (2025-11-25 → 2026-07-28).

## 5. Verification

* Each changed claim is re-read against its §1 source at implementation time.
* Existing gates: `validate-plugin-assembly.py --strict`, `validate-hooks.py --strict`, version sync, the doc
  gates and the full local gate list in CLAUDE.md, then CI.
* The validator change is shown to matter: a hooks manifest using `PostModelSwitch` is rejected before the
  change and accepted after (run once, by hand, recorded in the PR; no new test).
* Formatting: any file prettier would renumber or re-indent in a meaning-bearing way gets a scoped
  `prettier-ignore`, as COREDEV-2872 did, and every non-cosmetic formatter change is reviewed.

## 6. Rollout

One PR, version **2.8.29** (all sync points + CHANGELOG), Jira notes through implementation, merged on the
maintainer's word.
