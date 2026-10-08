# COREDEV-2875 — Model currency: every caller in the plugin uses the newest model

**Status:** Planning, revision 8. Gate round 7: agy `APPROVE`, codex `REQUEST_CHANGES` (1 blocking, 4 notes).
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
>
> **r3** `b2a73e7` (revision 3): agy `APPROVE`, codex `REQUEST_CHANGES`.
> 1. **(P1) A new-session caller was exempted.** `agy -i "…"` (`SKILL.md:236`) runs an INITIAL prompt
>    in a new session. Revision 3 had filed it under "interactive keeps the session's choice", but the
>    flag table says a session without `--model` starts on `settings.json`.
> 2. **(P2) §3 missed broken fixtures:**
>    * `test_preflight_agy_isolation`'s pong-only stubs;
>    * `test_end_to_end_gate`'s verdict-only stubs, plus its first-line `VERDICT: APPROVE` assertion
>      (`:156`);
>    * `test_validate_plugin_assembly`'s every-key fixture, which sets `model: v`.
> 3. **(P2) M2's byte-guard control cannot go red.** The fused `\x1b[Kgemini-3.8-flash-high` still ends
>    in `-flash-high`, so the candidate grammar rejects it whether or not the byte guard exists.
> 4. **F2 was false.** `_TIER_ROW` parses tier names as `` `[a-z]+` ``, so a coordinated concrete-id
>    edit leaves the agent unparsed and the build red. agy's r3 review "verified" F2 as written.
>
> **Revision 4** takes all four.
> * **Item 1** is widened rather than patched. agy's own help says `--model` is the "Model for the current
>   CLI session", and `-c`/`--conversation` resume a conversation in a new CLI session. So EVERY launch
>   mode resolves (`-p`, `-i`, `-c`, `--conversation`). Slash commands inside a running session are the
>   only interactive surface left with the session's choice.
> * **Item 2** is answered by MEASUREMENT rather than by adding codex's three names. A throwaway draft of
>   the whole design was applied and the full suite run. It fails 56 tests in 9 modules, and §3 now
>   accounts for every one (F4).
>
> **r4** `c46e167` (revision 4): agy `APPROVE`, codex `REQUEST_CHANGES`. Neither finding is caught by the
> draft's failure count or by any M cell.
> 1. **(P2) The banner defeated the empty-review safeguard.** `review-verdict.py:1142` refuses a
>    transcript only when it has ZERO bytes. A silent reviewer behind the banner leaves a banner-only
>    transcript, and codex confirmed that such evidence accepts `gemini=APPROVE`.
> 2. **(P2) The flag order made a safety test vacuous.** `test_doc_gates.py:915` finds raw checkout
>    launches by the exact substring `agy --add-dir "$(pwd)"`. With `--model` placed first, it matches
>    nothing and passes without reading the `SKILL.md:229` example.
> 3. **(fact) F4 named the wrong cause for the callers-scan failures.** They reject lines of THIS PLAN
>    (`draft-full-suite.txt:86–88`), not the new script.
>
> **Revision 5 takes the banner out of the transcript** rather than teaching the verdict writer to
> discount it. Codex proposed the second. But that would give the shared writer a second definition of
> "empty", coupled to one wrapper's output format. With the model in a `.model` sidecar beside the
> transcript, the transcript stays the reviewer's bytes alone. The empty safeguard, the byte-size
> failure signatures and `test_end_to_end_gate.py:156`'s first-line assertion then all hold unchanged,
> and none of them needs new code. The banner was revision 2's answer to r1's "visible did not reach
> the transcript". The sidecar answers that too: it persists with the transcript's own leaf name.
>
> **r5** `3475faf` (revision 5): agy `APPROVE`, codex `REQUEST_CHANGES`.
> 1. **(P2) `set -C` is not exclusive creation.** bash's noclobber refuses only an existing REGULAR file
>    (bash(1): "exists and is a regular file"). It opens a planted FIFO and hangs before the PTY
>    timeout starts. The repository already records the same hang (`test_plugin_state_mutants.py:637`,
>    row 116).
>
> Notes:
> * F3's inventory omitted the `agy -i` launch at `SKILL.md:236`, which §2.1 already fixes.
> * "A refused round leaves none" overstated the guarantee. `pty-capture.py` validates the reservation
>   and `.launch` AFTER the wrapper's write.
> * The draft's `line.split()` discards an empty first field, so `\tgemini-9-flash-high` promotes a label
>   to a candidate. Measured: `"\tgemini-9-flash-high\tlabel".split()[0]` is `gemini-9-flash-high`.
> * Resolver-path fixtures must REMOVE an inherited `MODEL`, not merely leave it unset.
>
> **Revision 6** takes all five. The sidecar is written through one `os.open(O_WRONLY | O_CREAT | O_EXCL
> | O_NOFOLLOW)`, the primitive `bind-prompt.py`'s `write_sidecar_bytes` (`:242`) already uses. M11's
> controls were measured with `~/.claude/handoffs/coredev-2875/oexcl-probe.py` before they were written.
> Revision 6's first draft of M11 was wrong: it claimed that dropping `O_EXCL` lets a symlink be written
> through, but `O_NOFOLLOW` still refuses it.
>
> **r6** `febe27f` (revision 6): agy `APPROVE`, codex `REQUEST_CHANGES`.
> 1. **(P2) A malformed newest entry was SKIPPED, selecting an older model.** Candidates were found by
>    suffix BEFORE the grammar check. So `gemini-4-flash-high<SP><TAB>…` beside `gemini-3.9-flash-high`
>    failed the suffix test, dropped out silently, and 3.9 won. That contradicted "surrounding spaces
>    fail the resolution".
> 2. **(P2) The silent-reviewer test asserted an unreachable message.** `persist-verdict.sh:109–123`
>    turns an empty transcript into `gemini=MISSING` and dies with "a missing transcript cannot produce
>    approval" BEFORE the writer runs.
>
> Note: M11 merged two mutations. Measured on bash 3.2 (`noclobber-probe.sh`), a `set -C` writer refuses
> a regular file and both symlinks, and hangs only on the FIFO.
>
> **Revision 7** declares the stdout LINE SHAPE and fails on any line that breaks it, so no line is ever
> skipped. It also asserts each layer's real diagnostic, and states each M11 outcome on its own.
>
> The shape rule was EXECUTED before it was written into the plan:
> `~/.claude/handoffs/coredev-2875/shape-spec-check.py` runs §2.1 as written, and the M1 and M2 mutants,
> over §3's cases.
> * Codex's counterexample and all four malformations fail with the shape message.
> * The real listing's shape resolves to `gemini-3.8-flash-high`.
> * The skip-malformed mutant selects the older model in every malformed case, so M2's control
>   discriminates.
> * The whitespace-split mutant agrees with the spec in every case, as M1 states.
>
> **r7** `82dae7e` (revision 7): agy `APPROVE`, codex `REQUEST_CHANGES`.
> 1. **(P2) The gates' launch definition required a QUOTED prompt.** A future `agy -p ping` or
>    `agy -i $PROMPT` would escape both the recipe gate and M10's raw-launch matcher. No shipped caller
>    is missed today.
>
> Notes:
> * Pair the unrecognized-version case with a valid older candidate. Otherwise a skip still fails as
>   "no candidate", and the M2 mutant hides.
> * Spell the persist argument `gemini=APPROVE:<transcript>`. A bare `gemini=APPROVE` dies at
>   `persist-verdict.sh:99` first.
> * A `NaN` timeout survives `min(max(…))`. Measured: the clamp yields `nan`, and `subprocess.run`
>   accepts it.
> * Keep M8's no-leaf-consumed assertion. Without it, isolated's later check masks a capture mutant.
>
> **Revision 8** recognizes a launch with ANY argument, in COMMAND positions only. Executed with
> `~/.claude/handoffs/coredev-2875/launch-scan.py`:
> * it returns exactly the 14 known lines (10 launch sites and 4 historical demonstrations);
> * it recognizes the unquoted probes;
> * it excludes the fenced shell comment at `SKILL.md:226`, which the line-wide form matched.

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
* **F2 — only an accident keeps it that way, and only for agents.** `validate-plugin-assembly.py:806`
  accepts any concrete model id that matches `[a-z]+-[a-z0-9-]*\d[a-z0-9-]*`.
  `test_validate_plugin_assembly.test_valid_model_ids_pass` and `test_supported_aliases_and_ids_accepted`
  (line 227) both assert that concrete ids pass.
  * **Agents** with a concrete id still fail today, but only through §11's tier check. Its row parser
    (`_TIER_ROW`, `:1064`) reads a tier name as `` `[a-z]+` ``, so a concrete id cannot be filed. A lone
    pin disagrees with its row, and a coordinated pin-and-table edit leaves the agent "missing from the
    tiering table" (`:1143–1149`). Neither message says why the id is wrong. (Revision 3 said the
    coordinated edit ships green; codex r3 showed it does not.)
  * **Skills** have no tier table, so nothing stops a concrete id there.
* **F3 — the Gemini arm is two versions behind.** `scripts/review/isolated-agy-review.sh:71` reads
  `MODEL="${MODEL:-gemini-3.6-flash-high}"`, and `agy models` (agy 1.2.16, run today) lists
  `gemini-3.8-flash-high` and `gemini-3.7-flash-high` above it. The literal appears in five more
  places:
  * the wrapper's rationale comment (`:59`);
  * the gemini-review skill: its description (line 3), setup text (line 63) and checklist (line 273);
  * `CLAUDE.md:95`.

  **More callers bypass it.** `preflight-agy.sh:71` runs `agy -p "ping"` with no `--model`, so it uses
  agy's global setting: `~/.gemini/settings.json`'s model, or agy's built-in default when that file
  names none, as on this machine. Neither is chosen by the gate. Eight more launches start agy with no
  `--model`:
  * the review recipe (`SKILL.md:62`);
  * the terminal example (`:229`);
  * the `agy -i "…"` launch in the same block (`:236`), a NEW session with an initial prompt;
  * the "continue with `agy -c` or `agy -i`" step (`:276`);
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

  **A second draft covers the whole design** (`draft-full.patch` and `draft-agy-newest-model.sh` beside
  the first). It contains the resolver, the wrapper's resolution, id grammar and revision 4's banner, operand six's
  grammar check, the preflight resolution, and the validator's alias-only check for agents and skills.
  Against the real `agy` the resolver printed `gemini-3.8-flash-high`. The full scripts suite then FAILED
  56 of 1519 (`draft-full-suite.txt`):

  | Module | Failures | Cause |
  |---|---|---|
  | `test_gemini_reviews_the_bound_plan` | 20 | stub never answers `agy models`, `MODEL` unset |
  | `test_m5_path_contract` | 10 | the same |
  | `test_transcript_path_threading` | 5 | the same |
  | `test_isolated_harness_preconditions` | 2 | the same |
  | `test_end_to_end_gate` | 9 | verdict-only stub, `MODEL` unset: the wrapper fails closed and the gemini transcript is empty |
  | `test_preflight_agy_isolation` | 2 | pong-only stubs: resolution fails, so no ping runs |
  | `test_validate_plugin_assembly` | 4 | two concrete-id acceptance cases, `test_valid_model_ids_pass`, and the every-key fixture's `model: v` |
  | `test_doc_gates` | 2 | the F3 literal bindings |
  | `test_callers_scan` | 2 | lines of THIS PLAN quote transcript-path text and are not yet in the shipped exemption manifest (`draft-full-suite.txt:86–88`). The branch is red here until §3 regenerates it, draft or not |

  The draft was then reverted, and the tree verified clean at `b2a73e7`.
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
  * Unset or empty means 60.
  * Any other value must parse as a FINITE number, or the resolution fails with a message naming the
    variable.
  * Measured: `NaN` survives a bare `min(max(value, 1), 60)`, and `subprocess.run` accepts a `NaN`
    timeout.
* **Every stdout line has a DECLARED shape (F11), and a line that breaks it fails the resolution.**
  * A non-empty line must FULLY match `<id>\t<label>`. `<id>` is one or more printable ASCII bytes
    other than space and TAB, and exactly one TAB follows it. The label may contain spaces.
  * Empty lines are ignored.
  * ANY other line fails the resolution, and the message names its line number. That includes
    whitespace before or after the id, a TAB-led row, and a row with no TAB.
  * A malformed line is never skipped, because a skipped line can be the newest model (codex r6:
    `gemini-4-flash-high<SP><TAB>…` beside 3.9).
* **Candidates** are the ids ending in `-flash-high`. Each one must FULLY match
  `gemini-<major>[.<minor>]-flash-high`. Ids that do not end in `-flash-high` (pro, `-preview` variants,
  other vendors) are well-formed lines, but not candidates.
  * A token that ends in `-flash-high` but does not match, such as `gemini-3.10.1-flash-high`, FAILS the
    resolution rather than being skipped. An unrecognized version form means "newest" cannot be
    decided, and skipping it could pick an older model silently.
* **Selection** takes the highest `(major, minor)`, compared numerically, with a missing minor read as 0.
* **Fail closed** on a timeout, a non-zero `agy models`, a forbidden byte, a malformed line, no
  candidate, or an unrecognized candidate. It never falls back to a remembered name.
* **The guarantee, stated exactly:** the newest RECOGNIZED flash-high model in the listing `agy`
  returns now. A stale listing is agy's own state, and the boundary is recorded in §6.

**Every model id is checked before it reaches a command line or a record.** The id may come from
the resolver, the environment `MODEL`, or capture operand six. Whatever its source, it must fully match
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`, or the round fails before launch. That rules out whitespace,
newlines and control bytes.
* `capture-gemini-review.sh` checks operand six BEFORE allocation, so a round that cannot run consumes
  no leaf.
* `isolated-agy-review.sh` checks the final value before the PTY child starts.

The id reaches agy's argv and the `.model` sidecar below. A newline, a leading `-` or a control byte
must never reach either.

**Every agy mention in shipped text, classified.** The inventory is derived with this command, run
over `skills`, `agents`, `scripts`, `hooks`, `CLAUDE.md` and `AGENT_CONTRACTS.md`, excluding tests:

```text
git grep -nIE '(^|[`"( ]|-- )agy( +-[-a-z]|  *models)'
```

On `8716979` it returns 44 lines. A narrower scan, for an agy LAUNCH in any mode, returns exactly the
ten launch sites in the table below plus the four historical demonstrations (`SKILL.md:163–165`,
`:168`). A launch is `agy` with `-p`/`--print`/`--prompt` or `-i`/`--prompt-interactive` and a quoted
prompt, or with `-c`/`--continue`/`--conversation`.

**The gates' launch definition is broader than that scan.**
* **Flags:** `agy`, optional flags, then `-p`/`--print`/`--prompt` or `-i`/`--prompt-interactive`, followed
  by ANY argument, quoted or not. Or `agy` with `-c`/`--continue`/`--conversation`.
* **Positions:** it is recognized only in COMMAND positions:
  * in markdown, inline-code contents and the non-comment lines of fenced blocks;
  * in other files, non-comment lines.
* **Executed** (`launch-scan.py`) on the shipped tree: the same 14 lines. It recognizes
  `agy -p ping`, `agy -i $PROMPT` and `agy --add-dir "$(pwd)" -p ping`. It excludes the fenced comment at
  `SKILL.md:226` ("agy -p with workspace flag…"), which a line-wide match reads as a launch.

| Site | Today | After |
|---|---|---|
| `isolated-agy-review.sh:71`, `:263` | the default literal | a non-empty `MODEL` wins, and the resolver is not called; otherwise the resolver's output |
| `preflight-agy.sh:71` | a bare ping | resolve, then `--model "$MODEL"`; a resolution failure is a preflight failure |
| `skills/gemini-review/SKILL.md:62` (review recipe) | bare | the checked form below |
| `SKILL.md:229` (terminal example) | bare | the checked form below |
| `SKILL.md:236` (`agy -i "…"`, a NEW session with an initial prompt) | bare | the checked form below |
| `SKILL.md:276` ("continue with `agy -c` or `agy -i`") | bare | refers to the example's checked form, without spelling a bare launch |
| `SKILL.md:272` (smoke test), `:314` (troubleshooting) | a bare ping | `bash …/preflight-agy.sh` |
| `skills/implement/SKILL.md:107` | a PTY-wrapped bare ping | `bash …/preflight-agy.sh` |
| `scripts/pty-capture.py:30–32` (docstring) | bare | the checked form below |

**The checked form** is `MODEL="$(bash …/agy-newest-model.sh)" && agy --model "$MODEL" …`. A failed
command substitution does not stop the command it is embedded in: codex reproduced `agy --model "$(…)"`
launching with an empty model. So resolution is its own command, and `&&` gates the launch.

**Every launch mode uses it.** agy's help says `--model` is the "Model for the current CLI session".
`-i` runs an initial prompt in a new session, and `-c`/`--conversation` resume a conversation in a new
CLI session. Without `--model`, each of them starts on agy's global setting.

**The other 34 lines launch nothing:**
* **Inside a running session.** Slash commands keep that session's choice: the section at
  `SKILL.md:239–248`, and the interactive-only notes at `:344`, `:403` and `:459`.
* **Historical demonstrations** of failed invocations: `SKILL.md:86–88`, `:163–168`, and
  `isolated-agy-review.sh:16–18`.
* **Prose about agy's behaviour or flags, or calls that start no model:**
  * `AGENT_CONTRACTS.md:125`, `:128`;
  * `SKILL.md:16` (the grant), `:59`, `:61` (which already routes to preflight), `:63`, `:65`, `:69`,
    `:226` (the comment that heads the terminal example), `:250` (the flags heading), `:311`, `:313`
    (`agy --version`) and `:319–323`;
  * the timeout comments at `capture-gemini-review.sh:37` and `isolated-agy-review.sh:57`, and the
    `agy models` note at `isolated-agy-review.sh:62`.

**Preflight checks the gate's default.** `preflight-agy.sh` takes no caller input by design (`:10–11`,
deep review P1), so it pings the resolved default. A round run with operand six is not preflighted. Its
failure shows as a tiny transcript, never a verdict.

**The model is recorded BESIDE the transcript, never in it.**
* **The record.** `isolated-agy-review.sh` writes `${OUT}.model` after its own preconditions and
  immediately before it hands off to `pty-capture.py`. It holds one line, `<id>\t<source>\n`.
  * **One `os.open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600)`, then a full write through
    that descriptor.** This is the primitive of `bind-prompt.py`'s `write_sidecar_bytes` (`:242`).
    `set -C` is NOT used: bash's noclobber refuses only an existing regular file, and opens a FIFO.
  * **ANY existing entry at that name refuses the round promptly,** before agy launches. That covers a
    regular file, a FIFO, a symlink and a dangling symlink, because `O_CREAT | O_EXCL` fails on every
    existing name and never follows a symlink. A short write removes the partial file and refuses.
  * **`<source>` is a literal the wrapper sets,** `override` or `newest`, and never caller text.
* **What it records, exactly:** the model selected for an ATTEMPTED launch. `pty-capture.py` validates
  the reservation and the `.launch` record AFTER this write (`:227–344`). A launch it refuses therefore
  leaves a `.model` beside an EMPTY transcript. That transcript is MISSING to the verdict writer, as
  today, and the record is not evidence (below).
* **The sidecar contract.** `.model` joins `DERIVED_SIBLING_SUFFIXES` (`pty-capture.py:690`), whose
  comment states the contract: "Anything appended to the leaf belongs in this tuple". The
  basename limit is unchanged, because it reserves room for the longest suffix (`.promptsha256`,
  13 characters).
* **The transcript is the reviewer's bytes alone, as today.** That keeps four things unchanged:
  * the verdict writer's EMPTY-is-MISSING refusal (`review-verdict.py:1142`);
  * the byte-size failure signatures the skill documents (`SKILL.md:62`'s "~36-byte transcript");
  * the anchored verdict parse (`isolated-agy-review.sh:332`);
  * `test_end_to_end_gate.py:156`'s first-line `VERDICT: APPROVE` assertion.
* **The PTY child stays exactly `agy --add-dir "$TREE" --model "$MODEL" …`**, as at `:263` today.
* **The wrapper's summary line gains `MODEL=<id>`.**
* **The record is not gate evidence.** The verdict artifact binds the transcript, prompt and plan, as
  today, and not `.model`. The sidecar answers "which model ran this round" for the operator. A
  `.model` that is missing or wrong does not change any verdict.

**The wrapper, the skill and `CLAUDE.md` describe the rule, not a model.**
* The wrapper's rationale comment (`isolated-agy-review.sh:59–70`) keeps its record of why only
  flash-high qualifies (the 5-of-6 failure of `gemini-3.1-pro`). It names the family, "the flash-high
  family (then 3.6)", rather than a versioned id. `test_agy_arm_default_is_the_model_its_own_comment_names`
  becomes a check that the family the comment names is the family the resolver selects from.
* The skill's description (line 3), setup text (line 63) and checklist (line 273) drop
  `gemini-3.6-flash-high`.
* Line 63's fallback becomes "a currently listed `gemini-*-flash-high` other than the one the round's
  `.model` sidecar names".
* Line 273 tells the operator to read the `.model` sidecar or the wrapper's `MODEL=` summary.
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
  * **a malformed line beside a VALID OLDER candidate fails the resolution, with the shape message
    naming its line.** Pairing it with a valid candidate is deliberate: a listing with no other
    candidate would fail for "no candidate" whether or not the shape rule existed. The case runs once
    for each malformation:
    * the NEWEST id with leading whitespace only;
    * the newest id with trailing whitespace only;
    * a TAB-led row (`\tgemini-9-flash-high\tlabel`);
    * a row with no TAB;
  * an empty line between valid rows is ignored;
  * an empty list fails closed, with the message;
  * `agy models` exiting non-zero fails closed;
  * a listing with `\r\x1b[K` fused to the NEWEST entry fails WITH the forbidden-byte message. It is a
    regression case, and the candidate grammar would also reject it;
  * a forbidden byte in a SECOND-column label, beside valid candidates, fails with the forbidden-byte
    message. Only the byte guard can catch this case;
  * `Fetching available models...` on stderr is ignored;
  * a set `MODEL` wins, and the stub records that `models` was never called;
  * an unrecognized candidate (`gemini-3.10.1-flash-high`) BESIDE A VALID OLDER candidate fails with
    the unrecognized-form message (a skip would select the older one);
  * `AGY_MODELS_TIMEOUT_S` set to `nan`, `inf` or `abc` fails with the variable's message, and
    nothing is listed;
  * a FINITE slow stub (5 s) with `AGY_MODELS_TIMEOUT_S=1` fails, so a removed timeout fails in bounded
    time;
  * an id with a newline, a space or a control byte is refused before launch. Via operand six, no leaf
    is consumed; via `MODEL`, the stub agy's call log stays empty;
  * end to end through `capture-gemini-review.sh`, with operand six absent and `MODEL` explicitly
    REMOVED from the environment:
    * the review invocation receives `--model <newest listed>`;
    * the `.model` sidecar holds exactly `<newest listed>\tnewest\n`, and the transcript holds only the
      stub reviewer's bytes;
  * `preflight-agy.sh`'s ping receives `--model <newest listed>`;
  * a resolver failure in the checked form launches nothing. The test EXECUTES the skill's and the
    docstring's recipe text with a failing resolver stub and a recording agy stub;
  * **a pre-existing `${OUT}.model` refuses the round promptly, and nothing launches.** The case runs
    once each with a regular file, a FIFO and a symlink (dangling, and pointing at a writable file). Each
    run sits under a subprocess timeout, so a hang is a bounded FAILURE. Each asserts the refusal
    message, an empty stub-agy call log, and an unchanged symlink target;
  * **a SILENT reviewer stays MISSING, at BOTH layers, each with its own diagnostic.** A stub agy that
    prints nothing and exits 1 runs through the real capture entrypoint, with a successful `models`
    answer and otherwise valid evidence. Then:
    * `persist-verdict.sh` with `--reviewer gemini=APPROVE:<transcript>` must die with "a missing
      transcript cannot produce approval" (`:109–123`), as it does today. The path is part of the
      spec: a bare `gemini=APPROVE` dies earlier, at `:99`;
    * `review-verdict.py write` called directly with `gemini=APPROVE:<transcript>` must refuse with
      "transcript is EMPTY and therefore MISSING" (`:1142`).
* **Every one of the draft's 56 failures (F4) is answered:**
  * **The 37 stubbed-reviewer tests** set `MODEL` explicitly in the environment they build. They test
    binding, isolation and status propagation, not selection, and selection is covered above.
  * **`test_end_to_end_gate` (9)** keeps exercising the production path. Its stub agy gains a
    side-effect-free `models` answer listing one flash-high model. Its environment REMOVES `MODEL`
    (`env.pop`), so an inherited value cannot hide the resolver path. The
    whole-chain assertion at `:156` is UNCHANGED, because the transcript gains no line. One assertion
    is added: the gemini transcript's `.model` sidecar names the stub's model.
  * **`test_preflight_agy_isolation` (2):** its stubs gain the same `models` answer and keep their ping
    behaviour. Its environment removes `MODEL` too. A new case asserts that a failed resolution reports unavailable and runs no ping.
  * **`test_validate_plugin_assembly` (4):**
    * the two concrete-id cases and `test_valid_model_ids_pass` become rejections (§2.3);
    * the every-key fixture (`:309`) keeps EVERY key, with a legal value for `model` (`inherit`).
  * **`test_doc_gates` (2) and `test_callers_scan` (2):** below.
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
* **The raw-checkout warning gate stops depending on flag order.**
  `test_every_raw_agy_invocation_is_warned_or_superseded` (`test_doc_gates.py:915`) finds raw launches by
  the exact substring `agy --add-dir "$(pwd)"`. The checked form puts `--model` first, so that substring
  would match nothing, and the test would pass without reading `SKILL.md:229` (codex r4).
  * It instead recognizes an agy launch (§2.1's definition) whose arguments include `--add-dir "$(pwd)"`
    in ANY position.
  * It asserts that it found at least one such launch, so it can never pass vacuously.
* **A recipe gate** scans shipped markdown and script docstrings for an agy LAUNCH in any mode (§2.1's
  definition). Each one must use the checked form, or appear in a closed exemption list of historical
  demonstrations. That list holds `SKILL.md:163–165` and `:168`, keyed by exact line text with a
  reason, and its count is pinned.
* The callers-scan manifest is regenerated. Any transcript-path inventory site whose bytes move is
  re-pinned through the suite's own derivation.

## 4. Verification cells (each must be seen red)

| # | property | must go red when |
|---|---|---|
| M1 | the resolver selects the newest flash-high | string comparison: `3.10` vs `3.9` is tested ALONE (no `4` in the list); the id is taken from the wrong field: a NEWER second-column decoy wins; `-preview` is admitted: a NEWER `-flash-high-preview` wins. Splitting the id on whitespace instead of the first TAB is an EQUIVALENT mutant once the shape rule holds, because a well-formed `<id>` contains no whitespace; it has no separate control |
| M2 | it fails closed | the non-zero listing stub PRINTS A VALID candidate and exits 1 (so only the status check can catch it); the shape rule SKIPS a malformed line instead of failing: the leading-only and trailing-only whitespace cases then select the valid OLDER candidate (each case asserts the shape message, so a failure for any other reason does not count); an unrecognized newer form is skipped instead of failing (paired with a valid older candidate, so the skip SELECTS it; the case asserts the unrecognized-form message); the finite check on `AGY_MODELS_TIMEOUT_S` is removed (`nan` then passes the clamp and the listing runs); the control-byte check is removed (the second-column-label case then SUCCEEDS, and the fused-entry case fails with the grammar message instead of the byte message); the timeout is removed (a 5 s stub with a 1 s bound then succeeds) |
| M3 | the override wins without a listing | the selected model is not the override, OR the stub's call log shows `models` was called. This is checked for the environment `MODEL` and for capture operand six |
| M4 | production runs the resolved model, and records it beside the transcript | `MODEL` is unset by the test (not merely operand six omitted), and the real capture entrypoint stops passing `--model <newest>`, or stops writing the `.model` sidecar |
| M5 | no concrete id ships in frontmatter | direct field tests: a concrete id or `default` is rejected WITH the model-specific message, for an agent and for a skill. Any integration test asserts that model-specific message, never merely a non-zero exit, because §11's tier parser already rejects a concrete agent id incidentally (F2) |
| M6 | the review skills name no pinned model | a `-c review_model=…` command or the `-c model=…` setup example returns to codex-review; a versioned flash-high literal returns to the wrapper, the resolver, any line of the gemini-review skill, or `CLAUDE.md`; the `settings.json` assertion still holds |
| M7 | every agy caller resolves, and a failed resolution launches nothing | `preflight-agy.sh` stops passing `--model`; any row of §2.1's table reverts to a bare launch; a NEW bare launch is added to a skill, once each as `agy -p "…"`, `agy -p ping` (unquoted), `agy -i $PROMPT` (unquoted) and `agy -c`; the checked form's `&&` becomes `;` (the executed recipe then launches agy after a failed resolution) |
| M8 | every model id is one token before launch | TWO mutations, one per check. **Capture's early operand-six check removed:** isolated's later check still refuses the round, so only the NO-LEAF-CONSUMED assertion catches it — the bad operand now allocates a transcript leaf. **Isolated's check removed** (the environment `MODEL` path, which capture never sees): a newline override and a `-`-led override then reach the stub agy's argv (its call log is non-empty) and write a multi-line `.model`. Each asserts the REASON — the grammar message, no leaf, an empty call log, and no `.model` — not merely a failure |
| M9 | a silent reviewer is still MISSING | the model is written INTO the transcript (for example, revision 4's banner is restored). With the rest of the evidence valid, `persist-verdict.sh` then ACCEPTS `gemini=APPROVE` instead of dying with its missing-transcript message, and the direct `review-verdict.py write` accepts it instead of refusing it as EMPTY |
| M10 | the raw-checkout warning gate reads every raw launch | the warning above `SKILL.md:229` is removed with the checked form's flag order in place (the test must fail); an UNWARNED `agy --add-dir "$(pwd)" -p ping` (unquoted) is added (the test must fail); the test's matcher reverts to the exact substring (its found-at-least-one assertion must fail) |
| M11 | the `.model` record is created exclusively, never through an existing entry | each mutation has its own measured outcome (macOS, 2026-10-08; `oexcl-probe.py`, `noclobber-probe.sh`). **A `set -C` redirect writer** (bash 3.2) refuses the regular file and both symlinks, and HANGS on the FIFO, so only the FIFO case catches it; the test's timeout makes the hang a failure. bash(1) documents the rule for every version: noclobber refuses only an existing REGULAR file. **`O_EXCL` dropped**, `O_NOFOLLOW` kept: the regular file is written over, the FIFO case hangs, and both symlink cases stay refused (ELOOP). **Both flags dropped:** the symlink also writes through to its target, and the dangling one creates it. **`O_NOFOLLOW` dropped alone** is an EQUIVALENT mutant (all four still refused with EEXIST). It is kept for parity with `bind-prompt.py`, and it has no separate control |

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
