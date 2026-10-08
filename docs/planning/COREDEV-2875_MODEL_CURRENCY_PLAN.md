# COREDEV-2875 — Model currency: every caller in the plugin uses the newest model

**Status:** Planning, revision 1. Not yet reviewed.
**Ticket:** COREDEV-2875 (parent Epic COREDEV-2485). **Branch / worktree:**
`feat/COREDEV-2875-model-currency`, `.claude/worktrees/model-currency`. It is cut from PR #107's head
(`692576a`), which already carries PR #106, because both PRs edit the same files. The PR for this
branch opens against `main` once those two merge.
**Created:** 2026-10-08

## Review log

*(empty)*

## 0. The direction, and the two decisions behind it

The maintainer's direction (2026-10-08): **any caller must always use the newest model.** Two choices
inside that direction were put to the maintainer and decided:

* **The Gemini review arm selects its model at run time.** It picks the highest-versioned
  `gemini-*-flash-high` that `agy models` lists, unless `MODEL` overrides it. Only the flash-high family
  qualifies (§1, F3).
* **The `ai-engineer` app guidance defaults to `claude-opus-5-5`.** Cheap bulk routes use
  `claude-haiku-5-5`.

## 1. Verified facts (2026-10-08, on `692576a`)

* **F1 — agents and skills.** All 21 agents name an alias or `inherit` in `model:`. Today that is
  `opus` ×3, `sonnet` ×7 and `inherit` ×11. An alias resolves to the newest model of its family, so no
  agent is behind. No skill sets `model:`.
* **F2 — nothing keeps it that way.** `validate-plugin-assembly.py` accepts any concrete model id that
  matches `[a-z]+-[a-z0-9-]*\d[a-z0-9-]*` (`MODEL_ALIASES` plus that regex).
  `test_validate_plugin_assembly.test_valid_model_ids_pass` asserts that concrete ids pass. A future
  `model: claude-opus-4-8` would ship green.
* **F3 — the Gemini arm is two versions behind.** `scripts/review/isolated-agy-review.sh:71` reads
  `MODEL="${MODEL:-gemini-3.6-flash-high}"`, and `agy models` (agy 1.2.16, run today) lists
  `gemini-3.8-flash-high` and `gemini-3.7-flash-high` above it. The literal appears in four more
  places:
  * the gemini-review skill: its description (line 3), setup text (line 63) and checklist (line 273);
  * `CLAUDE.md:95`.

  `test_doc_gates` binds the skill to the wrapper's default in
  `test_gemini_skill_quotes_the_model_the_wrapper_actually_defaults_to` and
  `test_agy_arm_default_is_the_model_its_own_comment_names`.

  The wrapper's comment records why only flash-high qualifies: `gemini-3.1-pro-high` failed to emit a
  parseable verdict in 5 of 6 rounds. `agy` runs under the real home directory, with only the checkout
  disposable, so `agy models` has the same authentication as the review call.
* **F4 — a draft resolver, executed.** The draft is `~/.claude/handoffs/coredev-2875/draft-resolver.patch`,
  with its output saved beside it. Against the real `agy` it selects `gemini-3.8-flash-high`. Against
  stubs it does the following:
  * prefers `3.10` over `3.9`, a numeric comparison;
  * prefers `4` over `3.10`;
  * excludes `-preview` variants and `pro-high`;
  * fails closed (exit 1) when no flash-high model is listed.

  Applied to the branch, the draft breaks **41 tests**. **37** are stubbed-reviewer tests whose stub
  never answers `agy models`, so the wrapper fails closed before the review:
  * `test_gemini_reviews_the_bound_plan` 20;
  * `test_m5_path_contract` 10;
  * `test_transcript_path_threading` 5;
  * `test_isolated_harness_preconditions` 2.

  **2** are the F3 doc gates, and **2** are the callers-scan manifest.
* **F5 — the Codex arm already follows its config.** `capture-codex-review.sh` and `audit-codex.sh` pass
  no model, so Codex uses `~/.codex/config.toml`. An unpinned local `codex review --base origin/main`
  today recorded `model: gpt-6.1-sol` and `reasoning effort: ultra` in its transcript header.
  `gpt-6.1-sol` is the first entry in Codex's own model list. Only the skill names a model:
  `skills/codex-review/SKILL.md` pins `-c review_model=gpt-6.1-sol` in its command examples (lines
  142–144, 155, 159, 249 and 268) and names it in its setup text (lines 66 and 69). A pin in a command
  goes stale silently. The skill already records that a set `review_model` overrides `model` for
  `codex review`.
* **F6 — the app guidance, against the current API reference.** The source is the Claude API reference
  bundled with Claude Code 2.1.293, model table cached 2026-10-06. `agents/ai-engineer.md:78` sets
  `defaultModel = "claude-sonnet-5-5"`. The reference states:
  * **The default model is `claude-opus-5-5`.** The newest model in each family is `claude-fable-5-1`,
    `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5`.
  * **Opus 5.5:** effort defaults to `medium`. Code should branch on `stop_reason: "refusal"` before
    reading `content`, and should opt into server-side fallbacks (`fallbacks: "default"` with beta
    `server-side-fallback-2026-07-01`, Claude API only).
  * **`claude-haiku-5-5`:** supports effort (default `medium`) and has **no server-side fallback**
    (`fallbacks` must not be sent). It returns a 400 on `budget_tokens`, on non-default
    `temperature`/`top_p`/`top_k`, and on assistant prefill. It ACCEPTS `thinking: {"type": "disabled"}`
    at `low`/`medium`/`high`, and it ACCEPTS a forced `tool_choice`.
  * **Claude Haiku 4.5 does not support effort.**

  The guidance cites Haiku 4.5 twice (lines 115 and 152) and never names `claude-haiku-5-5`.
* **F7 — the effort note names an old model.** `AGENT_CONTRACTS.md` §11 (line 502) and the README's
  2.8.28 entry list "Opus 4.7 to `xhigh`" beside the current models. It reads as if something defaults
  to Opus 4.7. Nothing does.
* **F8 — the reviewer's request-shape item covers Opus and Sonnet 5.5 only.**
  `agents/concurrency-reviewer.md:273` covers those two, plus effort sent to a model without effort
  support. It does not name Haiku 5.5's three 400s. Its `## Output Format` heading is pinned as
  `agents/concurrency-reviewer.md:286` in `AGENT_CONTRACTS.md` §13.

## 2. Design

### 2.1 The Gemini arm selects the newest flash-high model at run time

`isolated-agy-review.sh` replaces its default line with a resolver:

* **The candidate set** is every name in the FIRST column of `agy models` that fully matches
  `gemini-<major>[.<minor>]-flash-high`. Other models, suffixed variants such as `-preview`, and any
  other column are excluded.
* **Selection** takes the highest `(major, minor)`, compared numerically, with a missing minor read as 0.
* **Precedence:** a non-empty `MODEL` wins, and `agy models` is then not invoked. That is the capture
  wrapper's sixth operand, which stays the one-run override.
* **Fail closed:** if `agy models` exits non-zero, or lists no candidate, the round fails with
  `GATE FAILED — agy models lists no gemini-*-flash-high model …` and exit 1. It never falls back to a
  remembered name.
* **Visible:** the wrapper prints `gemini arm model: <id> (<source>)` to stderr, and its summary line
  gains `MODEL=<id>`. A transcript then records which model reviewed it.

The flash-high-only rule is the boundary this change deliberately keeps. "Newest" means the newest of
the family whose verdicts have been reliable, not the newest model of any family.

### 2.2 The Codex arm: no model is named anywhere in the plugin

* **The skill stops pinning models.** The `-c review_model=gpt-6.1-sol` pins come out of
  `codex-review/SKILL.md`'s commands, and the setup text describes the rule instead: Codex uses
  `review_model` if the config sets it, otherwise `model`. Leave `review_model` unset so reviews follow
  `model`, and keep `model` current.
* **No script change.** The scripts already pass no model (F5).

Which Codex model is newest is the operator's Codex configuration. It is outside what the plugin
ships, and §6 records that boundary.

### 2.3 CI rejects concrete model ids in shipped frontmatter

`validate-plugin-assembly.py` accepts only `MODEL_ALIASES`, which includes `inherit`, in `model:`. A
concrete id fails with a message naming the alias that tracks the newest model. This applies to:
* **agents:** the existing check, tightened;
* **skills:** newly checked; today no skill sets `model:`.

`test_valid_model_ids_pass` becomes the opposite assertion. `CLAUDE.md`'s authoring rule ("…or a full
model id") and `AGENT_CONTRACTS.md`'s alias-versus-pin note say concrete ids are rejected.

### 2.4 The app guidance moves to the current models

`agents/ai-engineer.md` changes as follows:
* **`defaultModel = "claude-opus-5-5"`**, with a comment that names it as the default and the newest
  Opus.
* **The refusal requirement** for Opus 5.5 (F6): branch on `stop_reason` before reading `content`, and
  opt into `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) on the Claude API.
* **Cheap and bulk routes use `claude-haiku-5-5`**, with its rules (F6): no `fallbacks`, so handle the
  refusal in the client; the three 400s; and effort supported, with a default of `medium`.
* **Haiku 4.5 is kept only as the example** of an older model without effort support, in the
  `supportsEffort` comment. It is never named as a choice.

The 5.5 rules table gains a Haiku 5.5 column, or a note, for where it differs.

### 2.5 The reviewer item names Haiku 5.5's rejections

`concurrency-reviewer`'s request-shape item adds `claude-haiku-5-5`'s 400s: `budget_tokens`,
non-default sampling and prefill. If the item grows past its current lines, `AGENT_CONTRACTS.md` §13's
`concurrency-findings` anchor moves with the `## Output Format` heading. That is a position-only
change, as in COREDEV-2873.

### 2.6 The effort note covers current models only

§11 and the README entry say: with nothing set, Opus 5.5, Sonnet 5.5 and Haiku 5.5 default to
`medium`, so set a level explicitly for review and gate sessions. The old-model detail goes, and the
note links to the model-config page for any other model.

## 3. Tests

* **New `scripts/tests/test_agy_model_resolution.py`.** Each case runs the shipped wrapper's resolver
  with a stub `agy` on `PATH`:
  * the newest wins, compared numerically (`3.10` beats `3.9`, `4` beats `3.10`);
  * `-preview`, `pro-high` and second-column text are excluded;
  * an empty list fails closed, with the message;
  * `agy models` exiting non-zero fails closed;
  * a set `MODEL` wins, and the stub records that `models` was never called;
  * end to end through `capture-gemini-review.sh` with no override, the review invocation receives
    `--model <newest listed>`.
* **The 37 stubbed-reviewer tests** set `MODEL` explicitly in the environment they build. They test
  binding, isolation and status propagation, not selection, and selection is covered above. The
  production path, `MODEL` unset, is the end-to-end case.
* **The two doc gates** bind the skill's description of the RULE to the wrapper's resolver pattern.
  They also assert that no `gemini-<digits>` literal sits in the wrapper's default or the skill's
  description.
* **The validator test** asserts that every alias passes and that concrete ids fail, for agents and for
  skills.
* **A codex-review doc gate** asserts that no command line in the skill pins `model=` or `review_model=`.
* The callers-scan manifest is regenerated. Any transcript-path inventory site whose bytes move is
  re-pinned through the suite's own derivation.

## 4. Verification cells (each must be seen red)

| # | property | must go red when |
|---|---|---|
| M1 | the resolver selects the newest flash-high | selection compares as strings; the `$1` column filter is dropped; `-preview` is admitted |
| M2 | it fails closed | an empty list falls back to a literal name; a non-zero `agy models` is ignored |
| M3 | the override wins without a listing | `MODEL` is ignored, or `agy models` is called anyway |
| M4 | production runs the resolved model | the end-to-end case stops receiving `--model <newest>` |
| M5 | no concrete id ships in frontmatter | a `model: claude-opus-4-8` agent or skill is added |
| M6 | the review skills name no pinned model | a `-c review_model=…` line returns to codex-review; a `gemini-3.x-flash-high` literal returns to the wrapper default |

## 5. Rollout

1. Run the plan gate in this worktree: agy and codex, reproduced on byte-identical bytes, then the
   review synthesis.
2. Implement, run the red controls, and run the local `codex review --base` diff review until it is
   clean. Then run the full local gate.
3. Ship as version 2.8.31, with the CHANGELOG and README updated. The PR opens against `main` after #106
   and #107 merge. Merging needs the maintainer's word.
4. Add Jira notes on COREDEV-2875 at each step.

## 6. Out of scope

* **The UnleashedMail app's provider code** is a separate repository. This plan changes the guidance
  the app's engineers follow, not the app.
* **The operator's `~/.codex/config.toml`** is not shipped by the plugin. §2.2 documents the rule.
* **Passing `agy --effort`** remains a separate decision (COREDEV-2872 note).
* **A Fable 5.1 default for the app** was offered and declined in favour of Opus 5.5 (§0).
