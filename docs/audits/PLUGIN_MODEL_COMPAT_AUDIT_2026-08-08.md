# Plugin Model-Compatibility Audit — Opus 5 + Fable 5

**Date:** 2026-08-08 · **Ticket:** COREDEV-2642 (follow-up to the PR #63 Opus 5 review) ·
**Branch:** `claude/plugin-compatibility-audit-i9yovn` · **Baseline:** `3b62071` (merge of PR #63)

**Question audited:** does every shipped asset — 21 agents, 21 skills, hooks (10 events / 12
invocations), the bundled review-synthesizer MCP server, scripts, CI, and the governing docs —
work correctly when the session model is **Claude Opus 5** (`claude-opus-5`) or **Claude Fable 5**
(`claude-fable-5`)?

**Verdict: compatible.** No blocking gap. The PR #63 alignment (COREDEV-2583/2642) holds; this
audit re-verified it against the *current* runtime and extended the check to Fable 5. Two
documentation gaps were found and fixed in this changeset; three residuals are documented below
with no change required.

## Method

- Full-tree grep inventory of model ids, aliases, effort keys, and API-shape fossils
  (`budget_tokens`, `temperature`/`top_p`, `output_format`, prefills, "think step by step",
  forced-progress scaffolding, severity filters) across `agents/`, `skills/`, `hooks/`,
  `scripts/`, `mcp/`, and the governing docs.
- `MODEL_ALIASES` in `scripts/validate-plugin-assembly.py` diffed against the **live Claude Code
  2.1.226 binary** (`/opt/claude-code/bin/claude`, this session's runtime), extracted via
  `grep -aoE '.{0,160}fable\[1m\].{0,160}'`.
- Frontmatter semantics (`model`, `effort`, `memory`, `disallowedTools`) cross-checked against the
  current sub-agents reference via Context7 (`/websites/code_claude`).
- Every validator and test suite run before and after the doc edits: plugin assembly, hooks
  manifest, version-sync, hook stdin-contract harness (302), MCP suite (228), scripts suite (765).
  All green.

## Verified current — no action

| # | Claim | Evidence |
|---|---|---|
| V1 | The validator's alias table is **byte-identical** to the current runtime's. The 2.1.226 binary carries `["sonnet","opus","haiku","fable","best","sonnet[1m]","opus[1m]","fable[1m]","opusplan"]` — exactly the `MODEL_ALIASES` transcription from the CI-pinned 2.1.220. No drift across six runtime releases; `fable` / `fable[1m]` validate. | `scripts/validate-plugin-assembly.py:48-63`; binary extract above |
| V2 | The concrete-id fallback accepts the 5-family ids (`claude-opus-5`, `claude-fable-5`, `claude-mythos-5`) and stays injection-anchored (`re.fullmatch`, no trailing-garbage acceptance). | `scripts/validate-plugin-assembly.py:685-692`; `scripts/tests/test_validate_plugin_assembly.py:195-215` |
| V3 | All 21 agents use **aliases only** (3 `opus`, 7 `sonnet`, 11 `inherit`), machine-checked against the §11 tiering table; no agent or skill pins `effort` (CI floor: `absent \| xhigh \| max`), so a `max`-effort Fable session runs subagents at `max`. | `agents/*.md` frontmatter; `validate-plugin-assembly.py:944-1035` (§11 parse), `:962-991` (effort policy) |
| V4 | **No pre-5 API scaffolding anywhere** in shipped prompt surfaces: zero hits for `budget_tokens`, `temperature`/`top_p`, `output_format`, prefills, `<scratchpad>`, "think step by step", or forced progress-update cadences across `agents/`, `skills/`, `hooks/`. | grep sweep (patterns above) |
| V5 | The review pipeline already matches the 5-family review-harness guidance: reviewers are **coverage-first** (no "only report high-severity" / "be conservative" filters anywhere), filtering/dedup happens downstream in the deterministic synthesizer, and the one verify gate is a deliberate pipeline stage — with an explicit **"do NOT re-verify"** guard on confirmed-by-construction gates, which is aligned with Opus 5's over-verification note. | grep sweep; `agents/swift-reviewer.md:577`; `mcp/review-synthesizer/` |
| V6 | CI's pinned Claude Code **2.1.220 ≥ the Opus 5 floor (2.1.219)** and its alias table already carried `fable`, so consumers on the CI-verified version get both session models. Hooks and scripts are model-agnostic — no `ANTHROPIC_MODEL`/`CLAUDE_MODEL` conditionals, no model-dependent branches. | `.github/workflows/plugin-ci.yml:105-112`; grep sweep of `scripts/`, `hooks/` |
| V7 | Teaching content is current: `ai-engineer`'s illustrative provider uses `claude-sonnet-5` and a clean minimal request body; the doc gate hard-fails any agent body citing a superseded `claude-{sonnet,opus,haiku}-4-x` id. | `agents/ai-engineer.md:78`; `scripts/tests/test_doc_gates.py:336-339` |

## Session-model behavior matrix

With the §11 tiers and omit-to-inherit effort, the fleet resolves as:

| Session model | `inherit` tier (11 agents) | `opus` tier (3 deep reviewers) | `sonnet` tier (7) |
|---|---|---|---|
| Opus 5 | Opus 5, session effort | Opus 5 | Sonnet (current) |
| **Fable 5** | **Fable 5, session effort** | Opus 5 *(deliberate — see G1)* | Sonnet (current) |
| Sonnet | Sonnet, session effort | Opus 5 (floor holds) | Sonnet |

`opus`/`sonnet` are runtime aliases tracking the current generation, so an Opus 5.x → next-gen
transition is again a zero-edit event for the fleet (AGENT_CONTRACTS §11).

## Gaps found

### G1 — §11 was silent on Fable 5 sessions *(fixed in this changeset)*

On a Fable 5 session the deep-review tier runs `opus` — i.e. *below* the session model. That
asymmetry is a defensible consequence of §11's design (the `opus` pin exists to hold a **floor** on
cheap sessions, not to chase the session ceiling), but it was nowhere stated, and §11 is the
designated source of truth for exactly this kind of dispute. **Fix:** a session-model compatibility
paragraph appended to §11 stating the behavior, the deliberate asymmetry, the one-edit escalation
path (move the three agents to the `inherit` row), and the status of the unused legal aliases.

### G2 — README had no current-state compatibility statement *(fixed in this changeset)*

Every model statement in the README lives in historical What's-New sections (v2.6.0's "Opus 5
alignment", v2.3.0's tiering note). A reader asking "does this plugin work on my Opus 5 / Fable 5
session?" had to reconstruct the answer from release archaeology. **Fix:** one current-state
sentence in the intro, pointing at §11 and this audit.

## Residuals — documented, no change

- **R1 — bracketed concrete ids.** The runtime's Fable matcher tolerates
  `claude-fable-5[1m]`-style dated/bracketed spellings; the validator's model-id regex rejects any
  bracketed *concrete id* (its character class deliberately excludes `[`/`]` for F10
  injection-anchoring). Not a live gap: the sanctioned spelling for long-context Fable is the
  `fable[1m]` **alias**, which validates, and §11 policy prefers aliases over pins throughout.
  Revisit only if a maintainer ever needs a *version-pinned* long-context model.
- **R2 — `best` / `opusplan` are legal but unused.** Both validate (V1) but no asset uses them, and
  the runtime groups both as "other" for tier display; their resolution semantics are
  runtime-defined and undocumented in the pinned reference. Do **not** move a §11 tier onto `best`
  (e.g. hoping it means "Fable when entitled") without first verifying what the pinned CLI actually
  resolves it to.
- **R3 — alias-table re-check contract.** `MODEL_ALIASES` must be re-verified on every CI pin bump;
  that standing instruction already exists at `validate-plugin-assembly.py:50` and this audit
  discharges it for 2.1.226. No mechanism change needed — the check is cheap (one grep against the
  installed binary) and the comment says exactly when to run it.

## Out of scope

Consumer-app (UnleashedMail) source is a separate repo; its `AnthropicProvider` request shapes are
reviewed there by `prompt-review`/`ai-engineer` at development time. The external review CLIs
(`codex`, `agy`/Gemini) pin non-Claude models and are unaffected by Claude-family changes.
