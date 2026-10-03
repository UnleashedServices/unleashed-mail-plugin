# COREDEV-2873 — Guidance refresh: Claude 5.5 request shapes, Apple toolchain, Foundation Models, stale examples

**Ticket:** COREDEV-2873 · **Epic:** COREDEV-2485 · **Branch:** `feat/COREDEV-2873-guidance-refresh` · **Base:** `main` (`dd84d82`)
**Status:** Planning, revision 2
**Origin:** item (c) of the 2026-10-03 external audit. The maintainer agreed the order: COREDEV-2872 (item b),
then this, then COREDEV-2869 part 1 and M4.

## Review log

> **r1** `d114502` (revision 1): agy `APPROVE`, codex `REQUEST_CHANGES` (2 blocking).
> 1. §3.4 listed only some of the stale toolchain text. I had built it from a truncated search, and a complete
>    scan finds more sites than codex named, including `tester.md` and `spm-management`.
> 2. §3.2 put a correctness check into `prompt-review`, whose own scope excludes correctness
>    (`agents/prompt-review.md:21`, `:89-93`) and whose closed category taxonomy has no slot for it.
>
> **Revision 2** makes these changes:
> - Enumerates every toolchain site from a complete scan, with explicit exceptions.
> - Drops §3.2. The 5.5 request rules live where the code is written, `ai-engineer`, and a review-time
>   owner is recorded as out of scope.
> - Sources §3.1's replacement strategies and labels §3.3's fallback as a recommendation.
> - Writes the brainstorm and Graph replacements out in full, and sources the Graph lifetime (F10).
> - Adds the validator-comment update and a probe for each of the three events.
> - Adds explicit acceptance checks.
> - Removes the unsourced F7.

## 0. Scope rule

**Guidance corrections only.** This plan changes what the plugin's agents and skills TELL an app developer,
plus one validator list and one CI pin, which are themselves stale facts. It adds **no new test machinery**.
Every change corrects a stated fact or adds a missing warning. Each fact in §1 was re-read from a primary source
on 2026-10-03. Where the audit was wrong, §2 states the correction rather than silently dropping it, because the
audit's wording is what a reader of this plan will have seen first.

## 1. Verified facts (source, date)

| # | Fact | Source (2026-10-03) |
|---|------|---------------------|
| F1 | The current API IDs are `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-fable-5-1` and `claude-haiku-4-5-20251001`. `claude-sonnet-5` is a **legacy** model and is still available. | platform.claude.com, *Models overview* |
| F2 | The API's default effort is `medium` on Opus 5.5 and `high` on Sonnet 5.5. Effort is set with `output_config.effort`. | *Models overview*; *Migrating to Claude Opus 5.5* |
| F3 | Opus 5.5 and Sonnet 5.5 each return **400** for five settings: a thinking budget (`thinking: {"type":"enabled","budget_tokens":N}`), `thinking: {"type":"disabled"}`, non-default `temperature`/`top_p`/`top_k`, an assistant prefill, and a forced `tool_choice` (`any` or `tool`). The guides' own replacements are: adaptive thinking plus the effort parameter for budgets; "use prompting to guide the model's behavior" for sampling; "structured outputs or system prompt instructions" for prefill; "`auto` plus strict tool use or structured outputs" for forced tool choice. On 5.5 a specific tool call can no longer be FORCED. | *Migrating to Claude Opus 5.5*; *Migrating to Claude Sonnet 5.5* ("five settings that return a 400 error") |
| F4 | On Sonnet 5.5 only, `thinking: {"type":"between_tools"}` is the lowest thinking setting. It is accepted at `low`, `medium` and `high` effort and returns a 400 at `xhigh` or `max`. With it set, changing the effort on a single message is a 400. Opus 5.5's thinking is always on. | *Migrating to Claude Sonnet 5.5* |
| F5 | The app (`UnleashedServices/UnleashedMail`, `main` `d9bdfc5d3`) uses Foundation Models in `Sources/Services/AI/Providers/AppleIntelligenceProvider.swift`. The provider is `@available(macOS 26.0, *)`. Under `#if canImport(FoundationModels)` it maps `SystemLanguageModel.default.availability` onto its own `AppleIntelligenceAvailability`: `deviceNotEligible`, `appleIntelligenceNotEnabled`→`notEnabled`, `modelNotReady`, and anything else (including `@unknown default`) → `unknown`. Without the framework it reports `unsupportedOS`. | the app repo, via the GitHub API |
| F6 | The app's CI runs on `macos-26` runners and selects the NEWEST installed Xcode (`ls -d /Applications/Xcode*.app \| sort -V \| tail -1`). The project has `MACOSX_DEPLOYMENT_TARGET = 15.0` and `SWIFT_VERSION = 6.0` (the language mode). | the app's `.github/workflows/ci.yml`, `memory-budget.yml` and `project.pbxproj` |
| F8 | Apple's April 28, 2026 upload rule reads: "built with Xcode 26 or later using an SDK for iOS 26, iPadOS 26, tvOS 26, visionOS 26, or watchOS 26". **macOS is not in it.** | developer.apple.com, *Upcoming requirements* |
| F9 | The Claude Code hooks reference lists 33 events. `scripts/validate-hooks.py` knows all of them except `DirectoryAdded`, `PreModelSwitch` and `PostModelSwitch`, and its comment still says "complete documented set (30)". npm's `latest` for `@anthropic-ai/claude-code` is 2.1.289. | code.claude.com/docs/en/hooks; `npm view`; a diff against the validator |
| F10 | Graph subscription lifetime for Outlook `message`/`event`/`contact` is "10,080 minutes (under seven days)", and "for subscriptions with resource data ... 1440 minutes (under one day)". Any `expirationDateTime` under 45 minutes after the request is raised to 45 minutes. | learn.microsoft.com, *subscription resource type* (v1.0) |

## 2. Corrections to the audit

* **Item 6 is overstated.** "App Store uploads have required Xcode 26+ since April" does not apply to this
  macOS app (F8). The agents' toolchain text is still stale and contradicts itself, so §3.4 corrects it, as a
  consistency fix rather than an App Store blocker.
* **Item 5 is overstated.** `claude-sonnet-5` is legacy, not invalid (F1). The real defect is that the guidance
  does not recommend the current model and does not warn about the request shapes that fail on 5.5 (F3).
* **Item 9 is an addition, not a correction.** No agent or skill mentions Foundation Models today, but the app
  uses it (F5), so the guidance should describe the app's EXISTING gating pattern for new code to follow.

## 3. Changes

### 3.1 `agents/ai-engineer.md`: Claude API guidance (priority 1)
* In the provider example, `defaultModel` (`:78`, `"claude-sonnet-5"`) becomes `"claude-sonnet-5-5"` (F1), and
  the example request gains `output_config: {effort: ...}` (F2).
* A **"Claude 5.5 request rules"** subsection lists F3's five 400s, each next to the replacement the migration
  guides themselves give (F3). It states plainly that a specific tool call can no longer be forced, so code
  that relied on forcing one must validate the model's choice. It adds F4's Sonnet-only `between_tools` note
  and names the source.

### 3.2 (dropped in revision 2)
`agents/prompt-review.md` is out of scope for these checks. That reviewer excludes correctness by its own
contract (`:21`, `:89-93`), and a request that is guaranteed to get a 400 is a correctness defect. The rules
belong in `ai-engineer`, where the code is written (§3.1). A review-time owner is listed in §4.

### 3.3 `agents/ai-engineer.md`: Foundation Models (priority 1)
* **Verified pattern (F5), stated as the app's current practice:**
  - `@available(macOS 26.0, *)` on the provider;
  - the `#if canImport(FoundationModels)` guard;
  - a mapping of `SystemLanguageModel.default.availability` to the app's own reasons, before any use.

  New Foundation Models code must follow this pattern.
* **Recommendation, labelled as such:** when the model is unavailable, route to another provider rather than
  failing. F5 does not show where that routing happens, so the guidance does not claim the app already does it.

### 3.4 Toolchain text: every site from a complete scan (priority 2)
The scan covered `agents/`, `skills/`, `README.md`, `CLAUDE.md` and `AGENT_CONTRACTS.md`, using the pattern
`Xcode[ _]1[0-9]|Swift 6\.[0-9]|macos-1[0-9]|macOS 25|≤ ?25`.

* **Change to F6** (CI on `macos-26` runners, the newest installed Xcode selected the way the app selects it,
  deployment target macOS 15.0, Swift 6 language mode):
  - `agents/ci-engineer.md:17`, the platform line ("Build: Xcode 16.3+");
  - `agents/ci-engineer.md:53, 85, 106, 174, 193, 250`, six `runs-on: macos-15`;
  - `agents/ci-engineer.md:57`, `xcode-select -s /Applications/Xcode_16.3.app`, replaced by the app's own
    newest-installed selection (F6);
  - `agents/xcode-build-fixer.md:60` ("Verify CI uses correct Xcode (16.3+)"), `:107` ("Xcode 16.3+ for Swift
    6.1 toolchain") and `:108` ("Use `macos-15`");
  - `agents/docs-engineer.md:58` and `:258` ("Xcode 16.3+");
  - `agents/release-manager.md:251`, `agents/tester.md:358` and `skills/spm-management/SKILL.md:121`, each a
    `runs-on: macos-15` example.

  Where a minimum Xcode must be named, the text says "the Xcode the app's CI selects" rather than a number that
  goes stale.
* **Stay, because they are correct:** "macOS 15+"/"macOS 15.0+" and "Swift 6.0+" are the deployment target and
  language mode (F6). These are `agents/code-simplifier.md:16`, `agents/xcode-build-fixer.md:18`,
  `agents/docs-engineer.md:59` and `:259`, and the deployment-target part of `ci-engineer.md:17`.
* **Stay, because they are dated records of a specific measurement:**
  - `agents/concurrency-reviewer.md:140` ("the COREDEV-1578 audit established this matrix on macOS 15 SDK /
    Swift 6.3");
  - `agents/release-manager.md:73` and `AGENT_CONTRACTS.md:35` ("Xcode 16.1.1, 2026-04-29").

### 3.5 Stale examples (priority 2)
* `skills/brainstorm/SKILL.md:95-98`. macOS went from 15 to 26, so "≤25" means "below 26", which for this app
  is macOS 15 (the deployment floor, F6). The replacements are:
  - `HTMLWebViewEditor` (≤25) → `HTMLWebViewEditor` (macOS 15);
  - "the WebKit editor is the floor on ≤25" → "the WebKit editor is the floor on macOS 15";
  - "never as two interchangeable alternatives on macOS 25" → "never as two interchangeable alternatives on the
    same OS version".
* `skills/microsoft-graph-integration/SKILL.md:222`. The fixed `"expirationDateTime": "2025-04-01T00:00:00Z"`,
  which is already past, becomes a placeholder that cannot go stale:
  `"<ISO 8601 UTC, at most 10,080 minutes from now — 1,440 with includeResourceData>"` (F10).
* The lifecycle bullet at `:229` keeps the 10,080-minute mail maximum (now sourced to F10) and adds F10's
  1,440-minute limit with resource data and the 45-minute floor.

### 3.6 Tooling facts (priority 2)
* `scripts/validate-hooks.py`: add `DirectoryAdded`, `PreModelSwitch` and `PostModelSwitch` to the known
  events, and update the comment at `:41` to "(33)" with the re-verification date (F9).
* `.github/workflows/plugin-ci.yml`: the Claude Code CLI pin (`CLAUDE_CODE_VERSION: 2.1.220`, at `:260` and
  `:530`, in the `validate` and `load-check` jobs) moves to the current `latest` dist-tag. That was 2.1.289 on
  2026-10-03, and it is re-read at implementation time. The pin's own comment, which says why it tracks
  `latest` rather than `stable`, is kept. The two changed job digests in `test_python39_floor.py` are
  re-pinned. If the newer CLI's `claude plugin validate --strict` rejects anything, that is reported, and then
  either fixed or the pin is held — never silenced. No tarball checksum is pinned today; that is an existing
  follow-up and stays out of scope.

## 4. Out of scope (separate decisions)

* A **review-time** check for 5.5 request shapes. No reviewer in the panel owns AI-request correctness:
  `prompt-review` excludes correctness, and the other four reviewers are domain-specific. Assigning one is a
  roster decision, not a guidance correction. Ticket it if wanted.
* Changes to how the review gate itself behaves:
  - the reviewer models (Gemini 3.8 Flash as primary, a pinned Codex model) and agy's `--effort`;
  - the bundled MCP server's protocol version (2025-11-25 → 2026-07-28).

## 5. Verification

* **Sources:** each changed claim is re-read against its §1 source at implementation time.
* **Acceptance checks**, recorded with their output in the PR:
  1. **Stale-toolchain scan.** The §3.4 pattern over the same paths returns ONLY the sites §3.4 keeps:
     - the three dated records (`concurrency-reviewer.md:140`, `release-manager.md:73`, `AGENT_CONTRACTS.md:35`);
     - any deployment-target or language-mode line the pattern happens to match.

     Every listed change site must be gone.
  2. `ai-engineer.md` names `claude-sonnet-5-5` in the example, and mentions `claude-sonnet-5` only as legacy
     (or not at all). The 5.5 subsection names all five F3 settings.
  3. `brainstorm/SKILL.md` contains neither "macOS 25" nor "≤25".
  4. `microsoft-graph-integration/SKILL.md` contains no fixed past `expirationDateTime`, and states both F10
     limits.
  5. **Validator probe, one per added event:** a hooks manifest using `DirectoryAdded`, then `PreModelSwitch`,
     then `PostModelSwitch` is rejected by `validate-hooks.py --strict` before the change and accepted after.
     This is done by hand, three runs each way, and recorded; no new test is added.
* **Existing gates:**
  - `validate-plugin-assembly.py --strict`;
  - `validate-hooks.py --strict`;
  - version sync;
  - the doc gates (the transcript-path inventory pins exact lines in some skills; a moved payload is updated
    by position only, as in COREDEV-2872);
  - the full local gate list in CLAUDE.md, then CI.
* **Formatting:** any file that prettier would renumber or re-indent in a way that changes meaning gets a
  scoped `prettier-ignore`, and every non-cosmetic formatter change is reviewed.

## 6. Rollout

* **One PR.** Its version is the patch after whatever `main` carries when it is opened: **2.8.29** if
  COREDEV-2872 (2.8.28) has merged first, otherwise the next free patch. All sync points and the CHANGELOG are
  updated together.
* **Process:** Jira notes are kept through implementation, and the PR is merged on the maintainer's word.
