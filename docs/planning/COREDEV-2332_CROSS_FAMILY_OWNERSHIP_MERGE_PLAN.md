# COREDEV-2332 — review-synthesizer: cross-family ownership-merge for ai-safety ↔ security/correctness overlaps

**Ticket:** COREDEV-2332 (parent COREDEV-2126 *GARI safety*) · **Type:** Task · follow-up from COREDEV-2329 (PR #18), codex PR-review P3 / gemini plan-review deferral.
**Repo:** `unleashed-mail-plugin` · **Branch:** `feat/COREDEV-2332-cross-family-ownership-merge` off `origin/main` (`f276673`).
**Change class:** synthesizer logic + tests only — **no asset count change, no plugin version bump** (release handled by the 2.4.0 run-through).

## 1. Problem

`mcp/review-synthesizer/synthesize.py` clusters two findings only when they share a category **family** or match a hard-coded cross-family **ownership pair** (`_candidate` → `_ownership_pair` over `_OWNERSHIP_MERGE_PAIRS`). The new `prompt-review` `ai-safety` family has **no** ownership pair, so when `prompt-review` flags an issue that overlaps another reviewer on the **same lines** using its AI taxonomy — e.g. `pii-log-leak` vs `security-reviewer`'s `privacy`, or `unsanitized-ingress` vs `webview` — they form **two separate clusters**. Consequences:
1. The consolidated report shows the overlapping defect **twice** (two rows) instead of once.
2. The `route_owner` ai-safety ownership branch (added COREDEV-2329, `synthesize.py:115-120`) **never fires on a real mixed cluster**, because the two findings never land in the same cluster to be routed.

This was deliberately deferred at PR #18 plan-review (`docs/planning/PROMPT_REVIEW_WIRING_PLAN.md` §10: "NOT adding an `ai-safety`↔`security` merge pair … safe and avoids cross-owner merge surprises; revisit if reports get noisy").

**Severity P3, safe by construction:** the synthesizer is conservative — it *clusters-not-collapses* and **never drops a fix**; today it just emits two rows. This ticket upgrades display/ownership accuracy without weakening that invariant.

## 2. Current state (already in place from COREDEV-2329 — do NOT re-add)

- `schema.py`: `ai-safety` family (10 categories) in `CATEGORY_FAMILY` + `DISPLAY_BUCKET["ai-safety"] = "AI Prompt Safety"`. ✅
- `synthesize.py`: `_AI_SAFETY_CATEGORIES` set + `route_owner` ai-safety branch (prompt-review authoritative, routes **before** security). ✅
- `tests/test_synthesize.py`: `route_owner` ai-safety ownership/tie tests — but they call `route_owner` **directly** on a hand-built cluster; they do **not** exercise `cluster_findings` clustering an ai-safety+security pair (which is impossible today). ❌ ← the gap.

## 3. Why not a family-level merge

A `family`-level `ai-safety`↔`security` pair would **over-cluster** (an unrelated `jailbreak-surface` row merging with a nearby `oauth` row). The correct fix is **category-pair-level**, exactly what `_OWNERSHIP_MERGE_PAIRS` already models (sets of *categories*, not families) — same mechanism as the existing `token-race`↔`{credential,oauth,keychain}` pair.

## 4. Design — add category-pair ownership merges

In `synthesize.py`, extend `_OWNERSHIP_MERGE_PAIRS` with the genuine same-defect overlaps (ai-safety category on the left, security category on the right; `_ownership_pair` is order-insensitive):

```python
_OWNERSHIP_MERGE_PAIRS = [
    ({"token-race"}, {"credential", "oauth", "keychain"}),            # security owns
    ({"perceived-perf"}, {"html-sanitization", "webview"}),          # security owns
    # ai-safety ↔ security (COREDEV-2332): prompt-review owns the merged cluster
    # (route_owner checks ai-safety BEFORE security).
    ({"pii-log-leak"}, {"privacy"}),                                 # same PII-in-logs defect
    ({"unsanitized-ingress"}, {"webview", "html-sanitization"}),     # same untrusted-content sink
    ({"unscoped-tool"}, {"privacy"}),                                # same cross-account-leak defect
]
```

**Pair rationale (same defect, same lines — NOT generic "sibling sink"):**
- `pii-log-leak`↔`privacy`: prompt-review and security-reviewer describing the same un-redacted PII log line.
- `unsanitized-ingress`↔`{webview, html-sanitization}`: justified **only** as *the same raw untrusted content (e.g. an email body) on the same lines feeding two sinks* — prompt-review flags it reaching an **LLM** with no `LLMInputSanitizer` (`unsanitized-ingress`), while security-reviewer flags that same raw content reaching a **WKWebView/HTML pipeline** unsanitized (`webview` / `html-sanitization`, `agents/security-reviewer.md:157-168`). This is narrow by construction: prompt-review deliberately does **not** itself emit WKWebView/security-general findings (`agents/prompt-review.md:89-92`), so the only way these two land on the same lines is a genuine shared-source defect. The ticket names `webview`; `html-sanitization` is its in-family sibling for the same sink and is retained on this same-source justification (codex asked to justify-or-narrow; justified). **A positive test for the `html-sanitization` pair is required (codex blocker).**
- `unscoped-tool`↔`privacy`: a tool touching user data without account scoping = a cross-account data leak.

**Explicitly NOT added:** `unsanitized-ingress`↔`network`. Per `agents/security-reviewer.md:89-106` the security `network` category is ATS/TLS/cert-validation/egress, **not** untrusted-content sanitization — a different defect. Adding it would over-cluster. A **negative** test guards this (below). (Gemini floated `network` for SSRF as optional; codex grounded it as out-of-scope — we follow codex and exclude it.)

**Ownership ordering (no code change needed, but assert it):** `route_owner` evaluates a11y → **ai-safety** → security. So a merged ai-safety+security cluster routes to `prompt-review` (the intended owner). Confirmed against `synthesize.py:107-125`.

**Invariants preserved:** clustering only groups + cross-links; `route_owner` only re-routes the lead/bucket. No finding is dropped — both fixes stay in the cluster and render via `_issue_and_fix`'s cross-link. Over-merge cost is bounded (one cross-linked row vs two), never a dropped fix; an optional `same_defect` adjudicator can still split.

## 5. Tests (add to `tests/test_synthesize.py`)

New class `TestAISafetyOwnershipMerge`:
1. **Overlap clusters + owned by prompt-review:** `pii-log-leak`(prompt-review) + `privacy`(security-reviewer) on overlapping lines, same file → `len(clusters)==1`; `cluster.primary.sourceAgent == "prompt-review"`; both findings present (no drop) → `len(cluster.findings)==2`.
2. **Each named pair clusters & routes to prompt-review** — one positive test per pair: `unsanitized-ingress`↔`webview`, **`unsanitized-ingress`↔`html-sanitization`** (codex blocker — must be explicit), and `unscoped-tool`↔`privacy`.
3. **No over-clustering (unrelated pair, overlapping lines, same file):** `jailbreak-surface`(prompt-review) + `oauth`(security) overlapping → `len(clusters)==2` (different families, not an ownership pair).
4. **Negative — `network` is NOT a pair:** `unsanitized-ingress`(prompt-review) + `network`(security-reviewer) on overlapping lines → `len(clusters)==2` (proves we did not over-reach into ATS/TLS).
5. **Non-overlapping lines stay separate** even for a valid pair: `pii-log-leak` lines 10-12 + `privacy` lines 40-42 → 2 clusters.
6. **Mixed-severity cluster — security blocker survives under prompt-review display ownership** (codex): `pii-log-leak`(prompt-review, **suggestion**) + `privacy`(security-reviewer, **blocker**) overlapping → 1 cluster; `cluster.primary.sourceAgent == "prompt-review"` (display owner) AND `cluster.severity == "blocker"` AND `cluster.lead_blocker.sourceAgent == "security-reviewer"`; via `decide_verdict(..., verify=lambda f: True)` the verdict is `REQUEST_CHANGES` and the rendered row leads with the security blocker's text — proving the merge never hides a security blocker (mirrors `test_blocker_text_surfaces_in_ownership_routed_row`).
7. **Fix never dropped** in the merged cluster: render the report, assert BOTH fixes appear (cross-linked), mirroring `test_cluster_keeps_all_fixes_cross_linked`.
8. Existing `test_category_set_equality_invariant` must stay green (we don't touch the category sets).

## 6. Validation

- `cd mcp/review-synthesizer && python3 -m unittest discover -s tests` → all green (existing + new).
- `python3 synthesize.py` demo (samples) still runs; eyeball that `prompt-review.json` + `security-reviewer.json` overlapping rows (if any) now consolidate.
- `validate-plugin-assembly.py --strict` + `version-sync` strict → unaffected (no asset/version change).
- Add `CHANGELOG.md` `[Unreleased] → Changed` entry (swept into 2.4.0).
- Append a one-line forward-pointer in `PROMPT_REVIEW_WIRING_PLAN.md` §10's `_OWNERSHIP_MERGE_PAIRS` bullet: "→ implemented in COREDEV-2332" (non-destructive; preserves the historical log).

## 7. Risks / mitigations

- **Over-clustering legitimately-distinct findings** that happen to share lines → low cost (cross-linked, never dropped) + category-pair scoping keeps it narrow; reviewers confirm the `html-sanitization` addition.
- **Ordering regression** (security accidentally owning an ai-safety cluster) → covered by test 1/2 asserting `prompt-review` ownership.
- **Touching the category-equality invariant** → we do NOT modify the category sets, only the merge-pair list; invariant test guards it.

## 8. Plan-review gate (mandatory) & Jira

- Dual gate (gemini + codex) on this plan BEFORE edits; iterate to APPROVE/APPROVE_WITH_NOTES; codex/gemini specifically confirm the `unsanitized-ingress`↔`html-sanitization` pair and the chosen owner ordering.
- Jira COREDEV-2332 → In Progress + dev notes; → Done-pending-merge at PR.
