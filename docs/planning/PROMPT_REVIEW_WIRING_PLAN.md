# COREDEV-2329 — Full-pipeline wiring for the `prompt-review` reviewer agent

**Status:** DRAFT — pending plan-review gate (codex + gemini)   **Created:** 2026-06-27
**Lands on:** PR #18 (branch `feat/COREDEV-2330-prompt-review-agent`, off `main` @ `ed6f5f9`)
**Tickets:** COREDEV-2329 (wiring) + COREDEV-2330 (the agent, authored by the owner) — one PR.
**Parent epic:** COREDEV-2126 (GARI safety / audit AI-01..06).

---

## 1. Context

The user authored `agents/prompt-review.md` — a read-only static reviewer of AI prompts / provider
call sites (taxonomy: `jailbreak-surface`, `missing-refusal-path`, `format-leak`,
`context-overflow-risk`, `ambiguous-instruction`, `evaluation-gap`, `unsanitized-ingress`,
`inline-prompt-leak`, `unscoped-tool`, `pii-log-leak`). It currently ships **standalone** and emits
**prose tables only**. Full-pipeline integration = make it a **5th specialist reviewer** that
`swift-reviewer` spawns and whose findings flow through the SubagentStop capture →
`review-synthesizer` pipeline exactly like the existing four (`security-reviewer`,
`concurrency-reviewer`, `ux-perf-reviewer`, `accessibility-auditor`).

Two gaps make that work:
1. **The agent has no machine-readable output** — the capture extracts the *last* ` ```json ` fence;
   the agent must additionally emit a schema-conformant findings array + a `Status:` line.
2. **Its taxonomy isn't in the synthesizer schema** — `schema.py:parse_finding` quarantines any
   `category` not in `CATEGORY_FAMILY`, and none of the 10 kinds exist there yet (the silent-drop trap).

## 2. Resolved design decision (the fork)

A pre-gate design pass surfaced two mutually-exclusive options and an adversarial critic flagged the
contradiction (**NOT-READY**). Decision:

- ✅ **Design A — first-class `ai-safety` family.** Add the 10 kinds to `CATEGORY_FAMILY` as a new
  `ai-safety` family; the agent emits its kinds **verbatim as `category`** (1:1). AI-safety findings
  get their own display bucket ("AI Prompt Safety") and `prompt-review` is their authoritative owner.
- ❌ **Design B — remap to existing categories** (`webview`/`logic`/`privacy`): rejected — it
  mislabels AI-safety findings under Security/Concurrency&Correctness and yields no dedicated section.

**Hard invariant (the trap):** the set of `category` values the agent emits MUST equal the set added
to `CATEGORY_FAMILY`, exactly (same kebab-case). Pinned by a test.

## 3. Agent output contract — `agents/prompt-review.md` (append)

Keep the human prose tables; **append** a "Structured Findings (orchestrator handoff)" section whose
**final** fenced block is a bare ` ```json ` array (capture takes the last `json` fence — examples
elsewhere must use `jsonc`/no-fence), preceded by a real top-level `Status:` line. Per finding (all
required; `scope` optional): `severity` (`blocker|warning|suggestion`, lowercase), `confidence`
(`high|medium|low`), `sourceAgent` (`"prompt-review"`), `category` (one of the **10 kinds**, verbatim),
`file` (repo-relative), `line`/`lineEnd` (ints; `0` = file-level, `lineEnd ≥ line`), `finding`,
`evidence`, `fix`. `Status: COMPLETE|BLOCKED|PARTIAL` (a literal value, never the template) with the
COREDEV-2328 detail fields for BLOCKED/PARTIAL — emitted **before** the final JSON fence, mirroring
the four reviewers' handoff + Output-Contract sections.

## 4. Synthesizer — `mcp/review-synthesizer/` (Design A, edits validated against source)

- **`schema.py` `CATEGORY_FAMILY`**: add the 10 kinds → `"ai-safety"` (before the
  orchestrator-owned singletons block). This also extends `FINDING_JSON_SCHEMA["category"]`
  (built from `sorted(CATEGORY_FAMILY)`), so the strict tool path accepts them too.
- **`schema.py` `DISPLAY_BUCKET`**: add `"ai-safety": "AI Prompt Safety"` — **mandatory**
  (`Finding.bucket` does `DISPLAY_BUCKET[family]` with no fallback → `KeyError` in `render_report`
  otherwise; also keeps `test_schema.py`'s "every family has a bucket" green).
- **`synthesize.py`**: add `_AI_SAFETY_CATEGORIES` (the 10 kinds) and an ownership branch in
  `route_owner` mirroring the `accessibility-auditor` pattern — `prompt-review` (or the `ai-safety`
  family) is authoritative, placed after the a11y branch, before the security branch. The report is a
  single flat consolidated table keyed on `c.primary.bucket`, so the family **auto-renders** once
  `DISPLAY_BUCKET` has the entry — no `render_report` change. `ai-safety` is a normal changeset-scoped
  family (NOT added to `_ALWAYS_GATING_FAMILIES`).

## 5. Capture + round-binding (allowlists — 3 sites)

- `mcp/review-synthesizer/capture.py` — add `"prompt-review"` to `VALID_AGENTS`.
- `scripts/capture-reviewer-verdict.sh` — add `prompt-review` to the agent_type `case` allowlist.
- `scripts/capture-reviewer-round-start.sh` — add `prompt-review` to the same allowlist (the
  COREDEV-2326 SubagentStart producer).

## 6. Orchestration

- `agents/swift-reviewer.md`: (a) Step 2 panel — spawn `prompt-review` (Agent N) with a review prompt
  scoped to AI prompts / provider call sites; (b) structural-routing table — make `prompt-review` the
  owner of `ai-flow` and add it to the "all four/all reviewers" rows; (c) the COREDEV-2328 status-read
  loop (`for agent in security-reviewer …`) — add `prompt-review`; (d) Output Format — add an "AI
  Prompt Safety Findings" section + the `**Reviewers**:` line.
- `commands/pr-review.md` + `commands/implement.md` — add `prompt-review` to the reviewer
  enumeration + the per-reviewer status table.
- `skills/agent-orchestration/SKILL.md` — add to the parallel-reviewer set + dependency rules.
- `AGENT_CONTRACTS.md` — the code-review reviewer panel.

## 7. Docs / counts (critique-surfaced gaps)

- `README.md`: architecture diagram (~L109-113 — add `prompt-review` to the swift-reviewer box); the
  "four reviewers" prose (L138 → "five reviewers"); the Review Agents table (~L144-150 — add a
  `prompt-review` row); the stale `## Agents (20)` heading (L140 → **21**). **No version bump:** the
  H1 counts line (L5) already reads "21 agents" and matches disk (the agent landed earlier in this PR),
  so `validate-version-sync.sh` passes; the `(20)` heading is not validator-checked but is fixed here.
- `skills/codex-review/SKILL.md`: the Codex mirror of the 4-reviewer set (L99/101/102, L127/128, L143)
  — add a `/prompt-review` row + example, parallel to the plugin reviewers.
- `CHANGELOG.md`: `[Unreleased] / Added` entry (agent + full wiring).

## 8. Tests

- `mcp/review-synthesizer/tests/test_capture.py` — `VALID_AGENTS` now 5; a `prompt-review` capture
  round-trip (a finding with an `ai-safety` category persists + is consumable).
- `mcp/review-synthesizer/tests/test_synthesize.py` — an `ai-safety` finding validates, routes to
  `prompt-review` ownership, and renders under the "AI Prompt Safety" bucket; **category-consistency
  pin** — every `ai-safety` category has a `DISPLAY_BUCKET` (guards the silent-drop trap).
- `scripts/test-hooks.sh` — both capture allowlists accept `prompt-review`; round-binding works for it.
- `mcp/review-synthesizer/samples/prompt-review.json` — a sample findings file (per-agent convention).
- Gates: `python3 -m unittest discover -s mcp/review-synthesizer/tests`, `bash scripts/test-hooks.sh`,
  `validate-plugin-assembly.py --strict`, `VERSION_SYNC_ENFORCE=strict validate-version-sync.sh`,
  `shellcheck -S warning scripts/*.sh`, PR CI.

## 9. Risks / edge cases

- **Category consistency** (agent-emitted ⊆/= schema set) is the single highest-risk item — pinned by
  a test that asserts the agent's documented categories all exist in `CATEGORY_FAMILY` under `ai-safety`.
- Must not break the existing 4 reviewers: the `route_owner` branch is additive (after a11y, before
  security); the capture/round-binding allowlists are additive.
- The agent stays read-only (`allowed-tools: Read, Bash, Grep, Glob`) — no pipeline change needed.

## 10. Plan-review log

- **Design workflow (pre-gate) → critic NOT-READY:** caught a fatal A/B self-contradiction (output
  spec mapped to existing categories while the wiring added an `ai-safety` family) and missed sites
  (README diagram/prose/table/heading, `skills/codex-review/SKILL.md`). **Resolved →** Design A with
  exact category↔schema parity; missed sites folded into §6/§7. Confirmed no version bump needed.
- **codex `APPROVE_WITH_NOTES` + gemini `APPROVE_WITH_NITS`** — both affirm Design A; 0 Critical.
  Notes folded in:
  - **More "four→five" live surfaces** (both): `agents/swift-reviewer.md` L4/L144/L185/L357/L444,
    `README.md` L211, `commands/pr-review.md` L2 — sweep ALL live reviewer-count prose/frontmatter
    (`grep -rn '\bfour\b.*review\|all 4\|four reviewers'` over live docs; exclude CHANGELOG/planning).
  - **`mcp/review-synthesizer/README.md`** (codex) — the authoritative manual-fallback category map
    swift-reviewer points to: add the 10 `ai-safety` categories + `prompt-review` ownership. **(§4/§7.)**
  - **Stale agent description** (gemini): flip `prompt-review.md`'s "Runs standalone today; integration
    … not yet wired" to reflect it's now wired into the swift-reviewer panel. **(§3.)**
  - **Exact category-equality test** (codex): assert `{documented agent categories}` ==
    `{cat for cat,fam in CATEGORY_FAMILY if fam=="ai-safety"}` == `_AI_SAFETY_CATEGORIES`, all
    kebab-case — guards the silent-drop/quarantine drift directly. **(§8.)**
  - **Output-contract wording** (codex nit): the `Status:` trailer sits **immediately before** the
    final bare ` ```json ` fence, with only blank/detail-field lines between (matches
    `capture.extract_status()`). **(§3.)**
  - **`_OWNERSHIP_MERGE_PAIRS`** (gemini, nice-to-have): NOT adding an `ai-safety`↔`security` merge
    pair — the synthesizer conservatively emits two rows for an overlapping `pii-log-leak`/`privacy`
    finding, which is safe and avoids cross-owner merge surprises; revisit if reports get noisy.
    **→ Followed up in COREDEV-2332**: added the genuine same-defect *category*-pairs
    (`pii-log-leak`↔`privacy`, `unsanitized-ingress`↔`{webview, html-sanitization}`,
    `unscoped-tool`↔`privacy`) — category-level, not family-level, so unrelated rows (e.g.
    `jailbreak-surface`↔`oauth`, `unsanitized-ingress`↔`network`) still stay separate.
- **Gate satisfied** — proceeding to implementation on PR #18.

## 11. Plan-review gate (mandatory before edits)

`/unleashed-mail:codex-review` + `/unleashed-mail:gemini-review` — both APPROVE / APPROVE_WITH_NOTES.
This touches the synthesizer schema + the capture hook allowlists; codex is primary for the
capture/CC-contract surface, gemini reliable for the prose/schema/orchestration edits.
