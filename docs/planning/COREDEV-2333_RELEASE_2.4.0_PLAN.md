# Release 2.4.0 — finalize the `prompt-review` agent (version bump + changelog + docs)

**Why:** `prompt-review` (COREDEV-2329 wiring + COREDEV-2330 agent) shipped in PR #18 under **2.3.1 with no version bump** — it still sits in CHANGELOG `[Unreleased]`. This release cuts **2.4.0** (minor) to properly release it, **bundled** with the two finalization fixes COREDEV-2331 (doc drift) and COREDEV-2332 (synthesizer cross-family merge). One coherent release: *"2.4.0 = prompt-review fully finalized."*
**Repo:** `unleashed-mail-plugin` · **Branch:** `feat/<RELEASE-TICKET>-release-2.4.0` off `origin/main` — created **after** the 2331 + 2332 PRs merge, so it sweeps their `[Unreleased]` entries into `[2.4.0]`.
**Jira:** new release Task (to be created) linked to COREDEV-2329/2330/2331/2332; parent epic COREDEV-2126.

## 1. Sequencing (hard dependency)

1. COREDEV-2331 PR merges (adds its `[Unreleased]` Fixed entry).
2. COREDEV-2332 PR merges (adds its `[Unreleased]` Changed entry).
3. **Then** branch this release off the updated `main` and sweep the whole `[Unreleased]` (prompt-review block already there + 2331 + 2332) → dated `[2.4.0]`.

If the user prefers, 2.4.0 can instead be cut immediately for prompt-review alone — but the chosen structure is *bundle all into 2.4.0*, which requires 1+2 first.

## 2. Version-sync anchors (from `scripts/validate-version-sync.sh`) — ALL must move together

| Anchor | From | To |
|---|---|---|
| `.claude-plugin/plugin.json` `"version"` | `2.3.1` | `2.4.0` |
| `README.md` H1 (`… Plugin vX.Y.Z`) | `Plugin v2.3.1` | `Plugin v2.4.0` |
| `README.md` newest `### vX.Y.Z` (What's New) | `### v2.3.1` | add `### v2.4.0` block **above** it (validator reads the FIRST `### v`) |
| `README.md` bold counts `**N agents · …**` | `21/18/3/1` | **unchanged** (no asset change in 2331/2332; prompt-review already counted) |
| `CHANGELOG.md` | `[Unreleased]` holds prompt-review + (post-merge) 2331 + 2332 | move all → `## [2.4.0] - 2026-06-27`; start fresh empty `[Unreleased]` |

`plugin.json` `description` already says "21 specialized agents" — **no change** (counts unchanged).

## 3. README `### v2.4.0` What's-New block (content)

Summarize the bundle in the established voice:
- **`prompt-review` — 5th specialist reviewer, fully released.** (the prompt-review/ai-safety pipeline summary currently in `[Unreleased]`.)
- **`ai-engineer` doc-drift fix (COREDEV-2331).** Removed the non-existent `HTTPBasedAIProvider`/`AIToolDefinition` symbols from agent docs/CLAUDE.md/contracts; grounded examples on real `BaseAIProvider`+`AIProviderProtocol` / `AITool`+`ToolHandlerProtocol`; `HTTPBasedAIProvider` relabeled PLANNED (COREDEV-1837) like `AISafetyPipeline`.
- **review-synthesizer cross-family ownership merge (COREDEV-2332).** Overlapping `ai-safety`↔`security` findings on the same lines now consolidate into one `prompt-review`-owned row instead of two.

## 4. CHANGELOG [2.4.0] structure

```
## [2.4.0] - 2026-06-27

### Added
- prompt-review … (existing [Unreleased] Added block, verbatim)
- COREDEV-2326 round-binding block (already in [Unreleased])

### Changed
- (existing [Unreleased] COREDEV-2328 Changed entries, CHANGELOG.md:58-85)
- review-synthesizer cross-family ai-safety↔security ownership merge (COREDEV-2332) …

### Fixed
- (existing [Unreleased] COREDEV-2328 Fixed entries, if any)
- ai-engineer doc drift (COREDEV-2331) …

## [Unreleased]
```

> **Sweep EVERYTHING currently under `[Unreleased]`** — not only prompt-review/2326/2331/2332. Codex confirmed the `[Unreleased]` block also holds **COREDEV-2328** Changed/Fixed entries (`CHANGELOG.md:58-85`) and the **COREDEV-2326** round-binding block (`CHANGELOG.md:33-56`); all are unreleased and belong in 2.4.0. After the move, `git grep -n "Unreleased"` must show only the fresh empty section — nothing stranded. (Exact line ranges re-verified at implementation time, post-merge.)

## 5. Validation

- `VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh` → OK at 2.4.0.
- `python3 scripts/validate-plugin-assembly.py --strict` → OK (21/18/3/1).
- `bash scripts/test-hooks.sh` + `python3 -m unittest discover -s mcp/review-synthesizer/tests` → green (regression safety).
- `shellcheck -S warning scripts/*.sh` → clean.
- `git grep -n "Unreleased"` → only the fresh empty section remains; no stranded entries.

## 6. Risks

- **CHANGELOG merge ordering** — must branch off post-2331/2332 `main`; if cut early, `[Unreleased]` won't contain their entries. Mitigated by §1 sequencing.
- **Minor vs patch** — user chose **2.4.0 (minor)**; diverges from the 2329 plan's stated 2.3.2 (intentional, per user).
- **Stranded `[Unreleased]` items** — audit before moving so nothing unreleased is missed (§4 note re COREDEV-2326).

## 7. Gate & Jira

- Reviewed in the same dual gate as 2331/2332 (mechanical, but version-sync is the real enforcement).
- Create the release Jira Task; link 2329/2330/2331/2332; → Done at merge.
