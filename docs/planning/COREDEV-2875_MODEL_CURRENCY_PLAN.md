# COREDEV-2875 — Model currency: every caller in the plugin uses the newest model

**Status:** Planning, revision 3. Gate round 2: agy `REQUEST_CHANGES` (1 blocking), codex `REQUEST_CHANGES` (3 blocking).
**Ticket:** COREDEV-2875 (parent Epic COREDEV-2485). **Branch / worktree:**
`feat/COREDEV-2875-model-currency`, `.claude/worktrees/model-currency`. It is cut from PR #107's head
(`692576a`), which already carries PR #106, because both PRs edit the same files. The PR for this
branch opens against `main` once those two merge.
**Created:** 2026-10-08

## Review log

> **r1** `2be0276` (revision 1): agy `APPROVE_WITH_NOTES`, codex `REQUEST_CHANGES` (3 blocking).
> 1. **The plan missed shipped Gemini callers** (P1).
>    * `preflight-agy.sh:71` runs a bare `agy -p "ping"`, so it uses agy's global setting, which can
>      be stale. The skill mandates that preflight.
>    * The skill's terminal examples (lines 229 and 236) and `pty-capture.py:30` bypass selection too.
>    * The Kimi arm (`isolated-kimi-review.sh:369`) passes no model, and its configuration boundary
>      was unstated.
> 2. **"Visible" did not reach the transcript** (P2). The banner and summary come from the parent, and
>    only the PTY child's output is captured.
> 3. **Skills got the agents' alias set** (P2). The premise was that `inherit` is sub-agent-only, per
>    the validator's own comment.
>
> Notes:
> * F1 should say that no agent PINS a generation, since `inherit` follows the session.
> * F2 missed the existing tier-table check.
> * The resolver's guarantee is the newest RECOGNIZED name in the listing. Unrecognized version forms
>   should be rejected, and the listing call should be bounded.
> * §2.4 would leave "forced tools are unavailable on 5.5" false for Haiku 5.5.
> * Each §4 cell needs a concrete control.
> * Two validator tests accept concrete ids, not one.
> * (agy) `CLAUDE.md:95` should be named explicitly.
>
> **Revision 2** takes all three blockers and every note, with one correction. The live docs
> (code.claude.com/docs/en/skills, re-read 2026-10-08) say a skill's `model` "accepts the same values as
> `/model`, or `inherit`". So `inherit` IS valid for skills, and the validator's comment was stale (F10).
> What stands from item 3 is that the two sets are checked separately, with `default` rejected for both.
> Revision 2 also adds §2.7, the CLI pin. The alias re-check that the validator requires at each pin bump
> had never been done for 2.1.289, and Haiku 5.5's alias needs Claude Code 2.1.293 or later.
>
> **r2** `8716979` (revision 2): agy `REQUEST_CHANGES` (1 blocking), codex `REQUEST_CHANGES` (3 blocking).
> 1. **(codex P1) More bare agy recipes.** The review recipe (`SKILL.md:62`), two pings (`:272`, `:314`)
>    and `implement/SKILL.md:107` still launch agy with no model.
> 2. **(codex P2) `agy --model "$(…)"` does not fail closed.** A failed command substitution does not
>    stop the outer command. Codex reproduced a launch with an empty model and exit 0.
> 3. **(codex P2) The banner could forge a verdict.** An override containing newlines puts
>    `VERDICT: APPROVE` on its own line. The anchored parser matches it, and the child's failure status
>    is not stored with the transcript.
> 4. **(agy) The banner argv was ambiguous.** `exec agy "$@"` with `…` that included `agy` would run
>    `agy agy …`.
>
> Notes:
> * (codex) `KNOWN_SKILL_KEYS` is a third set to re-derive at a pin bump.
> * (codex) Preflight cannot check an operand-six model.
> * (codex) Removing the timeout must fail in bounded time.
> * (codex) Codex-review's setup example `-c model=` (`:69`) must be covered.
> * (agy) Strip ANSI from `agy models`.
> * (agy) Give `CLAUDE.md:95`'s exact text.
>
> **Revision 3** takes all of them. The caller inventory is now DERIVED by grep, with each site classed
> as a recipe or not (§2.1). Agy's ANSI note was measured before it was taken. On a TTY agy fuses an
> escape to the FIRST entry, which is the newest model, so stripping would be an approximate fix. The
> resolver instead uses pipes only and fails closed on any control byte (F11).

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
  `opus` ×3, `sonnet` ×7 and `inherit` ×11. **No shipped agent pins a generation.** On the Anthropic API
  an alias resolves to the newest model of its family. `inherit` follows the session's model, which the
  operator controls (`AGENT_CONTRACTS.md:463`). No skill sets `model:`.
* **F2 — nothing keeps it that way.** `validate-plugin-assembly.py` accepts any concrete model id that
  matches `[a-z]+-[a-z0-9-]*\d[a-z0-9-]*` (`MODEL_ALIASES` plus that regex).
  `test_validate_plugin_assembly.test_valid_model_ids_pass` and `test_supported_aliases_and_ids_accepted`
  (line 227) both assert that concrete ids pass. The tier check (`validate-plugin-assembly.py:1143`)
  rejects an agent model that disagrees with §11's table. So a lone pin fails, but a COORDINATED pin and
  table edit ships green.
* **F3 — the Gemini arm is two versions behind.** `scripts/review/isolated-agy-review.sh:71` reads
  `MODEL="${MODEL:-gemini-3.6-flash-high}"`, and `agy models` (agy 1.2.16, run today) lists
  `gemini-3.8-flash-high` and `gemini-3.7-flash-high` above it. The literal appears in four more
  places:
  * the gemini-review skill: its description (line 3), setup text (line 63) and checklist (line 273);
  * `CLAUDE.md:95`.

  **More callers bypass it.** `preflight-agy.sh:71` runs `agy -p "ping"` with no `--model`, so it uses
  agy's global setting: `~/.gemini/settings.json`'s model, or agy's built-in default when that file
  names none, as on this machine. Neither is chosen by the gate. Six more recipes launch agy with no
  `--model`:
  * the review recipe (`SKILL.md:62`);
  * the terminal example (`:229`);
  * two pings (`:272`, `:314`);
  * a PTY-wrapped ping (`skills/implement/SKILL.md:107`);
  * the `pty-capture.py:30–32` docstring.

  §2.1 classifies every agy mention.

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
* **F9 — the Kimi arm also follows its config.** `isolated-kimi-review.sh:369` runs
  `kimi -p … --output-format text` with no model, so it uses the operator's Kimi configuration. That is
  the same boundary as Codex.
* **F10 — what the runtime and the docs accept** (re-read 2026-10-08).
  * The 2.1.294 binary's alias table is `["sonnet","opus","haiku","fable","best","sonnet[1m]",
    "opus[1m]","fable[1m]","opusplan"]`. It equals `MODEL_ALIASES` minus `inherit`, so the validator's
    set is still exactly right. Its comment says to re-check at every CLI pin bump, and 2.1.289 was
    never re-checked; this measurement covers it.
  * Skills accept "the same values as `/model`, or `inherit`" (code.claude.com/docs/en/skills).
  * `default` is "not itself a model alias". It reverts to the account's runtime default, which is
    not necessarily the newest model.
  * On the Anthropic API, `opus` resolves to Opus 5.5 and `haiku` to Haiku 5.5. Some other providers
    resolve them to earlier versions (model-config).
  * The same binary's hook-event array has 33 entries, and they equal `validate-hooks.py`'s
    `KNOWN_EVENTS` exactly. That set's comment records a re-check at 2.1.289 only.
  * The same binary's skill frontmatter schema (zod, `name` … `improved_by`) has 22 keys. They equal
    `KNOWN_SKILL_KEYS` minus `license` and `metadata`, which the validator adds on purpose ("accepted in
    the wild and harmless"). The set's comment records a derivation from 2.1.220 and says "Re-derive on
    every CLI pin bump" (`validate-plugin-assembly.py:97–99`).
  * Haiku 5.5 needs Claude Code 2.1.293 or later. CI pins 2.1.289 TWICE: in the `validate` job
    (`plugin-ci.yml:260`) and the `load-check` job (`:534`). `test_shell_primitive_drift` asserts that
    the two agree. npm's `latest` and `next` are 2.1.294; `stable` is 2.1.286.
* **F11 — `agy models` output depends on what its streams are attached to** (agy 1.2.16, measured
  2026-10-08).
  * **Separate pipes:** stdout holds 18 lines of `<id>\t<label>\n`, with no escape byte. The
    `Fetching available models...` line is on stderr.
  * **Under a PTY:** a braille spinner, then `\r\x1b[K` FUSED to the first entry, so the line reads
    `\r\x1b[Kgemini-3.8-flash-high`. That entry is the newest model.
  * **stdout on `/dev/null`:** the spinner and `\x1b[K` go to stderr.

  So the format is not a stable contract. A parse that tolerated or stripped such bytes would, on the
  PTY form, either skip the newest entry or depend on exactly which bytes it strips.

## 2. Design

### 2.1 The Gemini arm selects the newest flash-high model, everywhere it runs agy

**One resolver, `scripts/review/agy-newest-model.sh`.** On success it prints exactly one model id on
stdout. On any failure it exits non-zero and prints nothing on stdout.
* **Stream contract (F11).** It runs `agy models` with stdin from `/dev/null` and with stdout and stderr
  on SEPARATE pipes, never a TTY. It parses stdout only. A stdout byte that is not printable ASCII, tab
  or newline FAILS the resolution, and nothing is stripped.
* **Bounded.** `agy models` runs under a 60-second timeout (a `python3` subprocess timeout).
  `AGY_MODELS_TIMEOUT_S` may LOWER the bound, clamped to 1–60, so a test can prove it in seconds. It can
  never raise it. The PTY timeout starts only after resolution.
* **Candidates** are every FIRST-column token ending in `-flash-high`. Each one must FULLY match
  `gemini-<major>[.<minor>]-flash-high`.
  * A token that ends in `-flash-high` but does not match, such as `gemini-3.10.1-flash-high`, FAILS the
    resolution rather than being skipped. An unrecognized version form means "newest" cannot be
    decided, and skipping it could pick an older model silently.
  * Tokens that do not end in `-flash-high` (pro, `-preview` variants, other vendors) are not
    candidates.
* **Selection** takes the highest `(major, minor)`, compared numerically, with a missing minor read as 0.
* **Fail closed** on a timeout, a non-zero `agy models`, a forbidden byte, no candidate, or an
  unrecognized candidate. It never falls back to a remembered name.
* **The guarantee, stated exactly:** the newest RECOGNIZED flash-high model in the listing `agy`
  returns now. A stale listing is agy's own state, and the boundary is recorded in §6.

**Every model id is checked before it reaches a command line or the transcript.** The id may come from
the resolver, the environment `MODEL`, or capture operand six. Whatever its source, it must fully match
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`, or the round fails before launch. That rules out whitespace,
newlines and control bytes.
* `capture-gemini-review.sh` checks operand six BEFORE allocation, so a round that cannot run consumes
  no leaf.
* `isolated-agy-review.sh` checks the final value before the PTY child starts.

Without this check, an override containing newlines could write `VERDICT: APPROVE` into the transcript
through the banner (codex r2).

**Every agy mention in shipped text, classified.** The inventory is derived with this command, run
over `skills`, `agents`, `scripts`, `hooks`, `CLAUDE.md` and `AGENT_CONTRACTS.md`, excluding tests:

```text
git grep -nIE '(^|[`"( ]|-- )agy( +-[-a-z]|  *models)'
```

On `8716979` it returns 44 lines. A narrower scan, for an `agy` command with a quoted `-p` prompt,
returns exactly the eight launch sites in the table below plus the four historical demonstrations
(`SKILL.md:163–165`, `:168`).

| Site | Today | After |
|---|---|---|
| `isolated-agy-review.sh:71`, `:263` | the default literal | a non-empty `MODEL` wins, and the resolver is not called; otherwise the resolver's output |
| `preflight-agy.sh:71` | a bare ping | resolve, then `--model "$MODEL"`; a resolution failure is a preflight failure |
| `skills/gemini-review/SKILL.md:62` (review recipe) | bare | the checked form below |
| `SKILL.md:229` (terminal example) | bare | the checked form below |
| `SKILL.md:272` (smoke test), `:314` (troubleshooting) | a bare ping | `bash …/preflight-agy.sh` |
| `skills/implement/SKILL.md:107` | a PTY-wrapped bare ping | `bash …/preflight-agy.sh` |
| `scripts/pty-capture.py:30–32` (docstring) | bare | the checked form below |

**The checked form** is `MODEL="$(bash …/agy-newest-model.sh)" && agy --model "$MODEL" …`. A failed
command substitution does not stop the command it is embedded in: codex reproduced `agy --model "$(…)"`
launching with an empty model. So resolution is its own command, and `&&` gates the launch.

**The other 36 lines start no non-interactive review:**
* **Interactive sessions keep the session's choice, and the examples say so:** `agy -i` and `agy -c`
  (`SKILL.md:236`, `:239–248`, `:276`, and the interactive-only notes at `:344`, `:403` and `:459`).
* **Historical demonstrations** of failed invocations: `SKILL.md:86–88`, `:163–168`, and
  `isolated-agy-review.sh:16–18`.
* **Prose about agy's behaviour or flags, or calls that start no model:**
  * `AGENT_CONTRACTS.md:125`, `:128`;
  * `SKILL.md:16` (the grant), `:59`, `:61` (which already routes to preflight), `:63`, `:65`, `:69`,
    `:226` (the comment heading `:229`'s example), `:250` (the flags heading), `:311`, `:313`
    (`agy --version`) and `:319–323`;
  * the timeout comments at `capture-gemini-review.sh:37` and `isolated-agy-review.sh:57`, and the
    `agy models` note at `isolated-agy-review.sh:62`.

**Preflight checks the gate's default.** `preflight-agy.sh` takes no caller input by design (`:10–11`,
deep review P1), so it pings the resolved default. A round run with operand six is not preflighted. Its
failure shows as a tiny transcript, never a verdict.

**The transcript records the model.** The PTY child, spelled out in full:

```text
python3 pty-capture.py … -- sh -c 'printf "gemini arm model: %s (%s)\n" "$1" "$2"; shift 2; exec agy "$@"' \
    sh "$MODEL" "$MODEL_SOURCE" --add-dir "$TREE" --model "$MODEL" --print-timeout 28m -p "…"
```

* **The binary name is fixed inside the `sh -c` string.** Everything after the two banner operands is
  agy's ARGUMENTS, and the word `agy` is not among them, so agy's first argument is `--add-dir`.
* **`$MODEL_SOURCE` is a literal the wrapper sets:** `override` or `newest flash-high listed by agy
  models`. It is never caller text.
* **The banner is the FIRST line** of the captured transcript, inside the allocated artifact. The
  wrapper's summary line also gains `MODEL=<id>`.
* **Verdict parsing is unaffected.** `isolated-agy-review.sh:332` matches an anchored
  `^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)` line. Under the id grammar above, the banner
  is exactly one line, and it begins `gemini arm model:`. The reviewer identity comes from the
  allocation's launch record, not the child's argv, so the `sh` wrapper does not change it.
* **Byte sizes shift.** Every transcript grows by the banner's length. The skill's "~36-byte transcript"
  for a timeout (`SKILL.md:62`) becomes "the banner line plus ~36 bytes". Failure signatures are then
  read from what follows the banner.

**The wrapper, the skill and `CLAUDE.md` describe the rule, not a model.**
* The wrapper's rationale comment (`isolated-agy-review.sh:59–70`) keeps its record of why only
  flash-high qualifies (the 5-of-6 failure of `gemini-3.1-pro`). It names the family, "the flash-high
  family (then 3.6)", rather than a versioned id. `test_agy_arm_default_is_the_model_its_own_comment_names`
  becomes a check that the family the comment names is the family the resolver selects from.
* The skill's description (line 3), setup text (line 63) and checklist (line 273) drop
  `gemini-3.6-flash-high`.
* Line 63's fallback becomes "a currently listed `gemini-*-flash-high` other than the one the transcript
  banner names".
* Line 273 tells the operator to read the banner.
* `CLAUDE.md:95`'s parenthesis becomes "(Antigravity `agy`, the newest `gemini-*-flash-high` that
  `agy models` lists)".

The flash-high-only rule is the boundary this change keeps on purpose. "Newest" means the newest of
the family whose verdicts have been reliable.

### 2.2 The Codex arm: no model is named anywhere in the plugin

* **The skill stops pinning models.** The `-c review_model=gpt-6.1-sol` pins come out of
  `codex-review/SKILL.md`'s commands, and the setup text describes the rule instead: Codex uses
  `review_model` if the config sets it, otherwise `model`. Leave `review_model` unset so reviews follow
  `model`, and keep `model` current.
* **No script change.** The scripts already pass no model (F5).

Which Codex model is newest is the operator's Codex configuration. It is outside what the plugin
ships, and §6 records that boundary. The Kimi arm (F9) is the same: the plugin names no Kimi model, and
`codex-review`'s Kimi stand-in text says so.

### 2.3 CI rejects concrete model ids in shipped frontmatter

`validate-plugin-assembly.py` accepts in `model:` only the runtime aliases (F10) plus `inherit`. The
two sets are held separately, so a future divergence is a one-line change:
* **agents:** aliases and `inherit`; the existing check, tightened;
* **skills:** aliases and `inherit`, per the skills reference; newly checked, though today no skill
  sets `model:`.

Both reject a concrete model name, with a message naming the alias that tracks the newest model. Both
also reject `default`, which reverts to the account default, not the newest model. The regex that
admitted concrete ids is removed. Its injection and end-anchor negatives (COREDEV-2503 F10) still hold,
because only exact set membership passes.

`test_valid_model_ids_pass` and `test_supported_aliases_and_ids_accepted` (line 227) become rejections
for concrete ids. Their independently enumerated alias cases and the invalid-suffix and injection
negatives are kept. `CLAUDE.md`'s authoring rule ("…or a full
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
* **Haiku 5.5's differences are stated where the guidance generalizes over 5.5.** "A specific tool call
  can no longer be FORCED on 5.5" becomes "on Opus 5.5 and Sonnet 5.5". Haiku 5.5 ACCEPTS a forced
  `tool_choice`, though the response then skips thinking, and it accepts `thinking: disabled` at
  `low`/`medium`/`high` (F6). Each such sentence names the models it covers.

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

### 2.7 The CLI pin moves to the newest release, and the alias table is re-checked against it

* **Both pins move together.** `CLAUDE_CODE_VERSION` goes from 2.1.289 to **2.1.294** (npm's `latest`
  on 2026-10-08) in the `validate` job and the `load-check` job. `test_shell_primitive_drift` already
  fails if they disagree. That release clears Haiku 5.5's 2.1.293 floor (F10), and the `validate` job's
  comment states why.
* **All three transcribed sets record the re-check.** `MODEL_ALIASES` and `KNOWN_SKILL_KEYS`
  (`validate-plugin-assembly.py`) and `KNOWN_EVENTS` (`validate-hooks.py`) each say "re-verified
  against the 2.1.294 binary, 2026-10-08". All three are unchanged (F10). The family was derived by
  grepping for "pin bump", "re-derive" and "transcribed from". The trunk entries that grep also returns
  are pin obligations for a different tool.
* **The stale mentions move with them.** That is `test_python39_floor.py:373`'s comment, plus a new
  2.8.31 README entry stating the CI version. The 2.8.29 entry's "CI validates with Claude Code
  2.1.289" (`README.md:25`) is history and stays.
* **`test_python39_floor`:** the `validate` and `load-check` job digests are re-pinned through
  `_job_digest`, as COREDEV-2873 did.

## 3. Tests

* **New `scripts/tests/test_agy_model_resolution.py`.** Each case runs the shipped
  `agy-newest-model.sh` with a stub `agy` on `PATH`:
  * the newest wins, compared numerically (`3.10` beats `3.9`, `4` beats `3.10`);
  * `-preview`, `pro-high` and second-column text are excluded;
  * an empty list fails closed, with the message;
  * `agy models` exiting non-zero fails closed;
  * a listing with `\r\x1b[K` fused to the NEWEST entry fails, rather than selecting the second newest;
  * `Fetching available models...` on stderr is ignored;
  * a set `MODEL` wins, and the stub records that `models` was never called;
  * an unrecognized candidate (`gemini-3.10.1-flash-high`) fails;
  * a FINITE slow stub (5 s) with `AGY_MODELS_TIMEOUT_S=1` fails, so a removed timeout fails in bounded
    time;
  * an id with a newline, a space or a control byte is refused before launch. Via operand six, no leaf
    is consumed; via `MODEL`, the stub agy's call log stays empty;
  * end to end through `capture-gemini-review.sh`, with operand six absent and `MODEL` explicitly
    REMOVED from the environment:
    * the review invocation receives `--model <newest listed>`;
    * agy's first argument is `--add-dir`;
    * the stored transcript's first line is the model banner;
  * `preflight-agy.sh`'s ping receives `--model <newest listed>`;
  * a resolver failure in the checked form launches nothing. The test EXECUTES the skill's and the
    docstring's recipe text with a failing resolver stub and a recording agy stub.
* **The 37 stubbed-reviewer tests** set `MODEL` explicitly in the environment they build. They test
  binding, isolation and status propagation, not selection, and selection is covered above. The
  production path, `MODEL` unset, is the end-to-end case.
* **The two doc gates** bind the skill's description of the RULE to the resolver's pattern. They also
  assert that no versioned flash-high literal (`gemini-<major>[.<minor>]-flash-high`) appears anywhere
  in the wrapper, the resolver, the gemini-review skill or `CLAUDE.md`. Other names stay legal, such as
  the skill's warning against `gemini-3.1-pro-high`. The existing `settings.json` regression assertion
  (`test_doc_gates.py:1135`) is kept.
* **The validator test** asserts that every alias passes and that concrete ids fail, for agents and for
  skills.
* **A codex-review doc gate** asserts that nothing in the skill assigns a value to `model` or
  `review_model`, in commands or in setup text (line 69's `-c model=` included). Prose that names the
  keys without a value passes.
* **A recipe gate** scans shipped markdown and script docstrings for an `agy` command with a quoted
  `-p` prompt. Each one must use the checked form, or appear in a closed exemption list of historical
  demonstrations. That list holds `SKILL.md:163–165` and `:168`, keyed by exact line text with a
  reason, and its count is pinned.
* The callers-scan manifest is regenerated. Any transcript-path inventory site whose bytes move is
  re-pinned through the suite's own derivation.

## 4. Verification cells (each must be seen red)

| # | property | must go red when |
|---|---|---|
| M1 | the resolver selects the newest flash-high | string comparison: `3.10` vs `3.9` is tested ALONE (no `4` in the list); the `$1` filter is dropped: a NEWER second-column decoy wins; `-preview` is admitted: a NEWER `-flash-high-preview` wins |
| M2 | it fails closed | the non-zero listing stub PRINTS A VALID candidate and exits 1 (so only the status check can catch it); an unrecognized newer form is skipped instead of failing; the control-byte check is removed (the `\x1b[K`-fused newest entry then yields the second newest); the timeout is removed (a 5 s stub with a 1 s bound then succeeds) |
| M3 | the override wins without a listing | the selected model is not the override, OR the stub's call log shows `models` was called. This is checked for the environment `MODEL` and for capture operand six |
| M4 | production runs the resolved model | `MODEL` is unset by the test (not merely operand six omitted), and the real capture entrypoint stops passing `--model <newest>`, stops writing the banner as the transcript's first line, or passes `agy` as agy's first argument |
| M5 | no concrete id ships in frontmatter | direct field tests: a concrete id or `default` is rejected WITH the model-specific message, for an agent and for a skill; an integration fixture keeps a consistent tier table, so the failure is this guard's |
| M6 | the review skills name no pinned model | a `-c review_model=…` command or the `-c model=…` setup example returns to codex-review; a versioned flash-high literal returns to the wrapper, the resolver, any line of the gemini-review skill, or `CLAUDE.md`; the `settings.json` assertion still holds |
| M7 | every agy caller resolves, and a failed resolution launches nothing | `preflight-agy.sh` stops passing `--model`; any row of §2.1's table reverts to a bare launch; a NEW bare `agy -p "…"` recipe is added to a skill; the checked form's `&&` becomes `;` (the executed recipe then launches agy after a failed resolution) |
| M8 | no model id can add a line to the transcript | the id grammar check is removed: a newline override then writes an anchored `VERDICT:` line. The cell asserts the REASON — the round fails with the grammar message and the transcript holds no anchored `VERDICT:` line — not merely a failure |

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
* **The operator's configurations** are not shipped by the plugin: `~/.codex/config.toml`, Kimi's
  config, and agy's own global setting for bare manual runs. §2.2 documents the rule.
* **`inherit` and providers.** `inherit` follows the session's model, the operator's choice. On Bedrock,
  Google Cloud and Foundry some aliases resolve to earlier versions (F10). Both are outside what an
  alias in shipped frontmatter can control.
* **The listing itself.** The resolver trusts the listing `agy models` returns. If agy's catalog lags
  Google's, so does the selected model.
* **Passing `agy --effort`** remains a separate decision (COREDEV-2872 note).
* **A Fable 5.1 default for the app** was offered and declined in favour of Opus 5.5 (§0).
