# COREDEV-2328 — Persist reviewer Output-Contract status in the SubagentStop capture path

**Ticket:** COREDEV-2328 (child of Epic **COREDEV-2321**, octo-adoption hardening)
**Status:** IMPLEMENTED in v2.4.0 (v8 — adversarial review + dual-gate rounds 1–6; gate passed and shipped)
**Branch:** `feat/COREDEV-2328-capture-reviewer-status` (worktree, off `origin/main@7111a28`, plugin v2.3.1)
**Relates to:** Item 6 (SubagentStop capture, COREDEV-2325) · Item 12 (Output-Contract enum, COREDEV-2327)
**Created:** 2026-06-26

---

## 1. Goal

Phase-3 Item 12 gave each specialist reviewer an Output-Contract `Status:` line
(`COMPLETE | BLOCKED | PARTIAL`) emitted **immediately before** its final ```json findings
fence, so `swift-reviewer` reads the status *first* and a `BLOCKED` reviewer that returns `[]`
cannot masquerade as a clean pass. That holds on the **live subagent** path; it does **not** hold
on the shipped **SubagentStop capture** path (`mcp/review-synthesizer/capture.py`), which persists
**only** the sanitized findings array (`<agent>.json`) and drops the `Status:` line. So a
pre-collected reviewer array from capture always arrives status-less, and the Phase-3 prose guard
in `swift-reviewer.md` Step 2 deliberately treats it at face value (no fail-closed) — pointing here.

**This ticket** extracts and persists the `Status:` (+ BLOCKED/PARTIAL detail fields) through
`capture.py` as a sibling `<agent>.status`, then tightens the `swift-reviewer.md` Step-2 guard —
with a **concrete, tested lookup** — so Item 12's guarantee holds on the capture path **whenever a
recognizable Status line was persisted**, degrading to today's fail-open behaviour (face value)
otherwise. The close is honestly **conditional on a recognizable status**; it introduces **no false
fail-closed from reviewer-output content** (the extractor honors only a *top-level* Output-Contract
trailer). The sole false-fail-closed residuals are the **best-effort cases documented in §3.5** (all
rare, infrastructure-level — not reviewer-content driven).

Out of scope (unchanged): the synthesizer (`synthesize.py`/`schema.py`) input shape, the
dedup/round-selection semantics, the SubagentStop hook script, any version/asset-count bump.

---

## 2. Ground truth (verified against the worktree, not memory)

- **Persisted shape today.** `capture.capture()` writes a **bare sanitized findings array** to
  `<root>/<slug>/round-N/<agent>.json` (tmp+`os.replace`), then a best-effort `<agent>.agentid`.
  Captures live **outside the repo** (`~/.claude/unleashed-mail/reviews/<repo_hash>/<slug>/round-N/`,
  `context_reviews_dir`) — a new sibling is never committed / never touches `.gitignore`.
- **`<agent>.json` consumers needing a bare `list`:** `is_final_capture()`; ~15 `test_capture.py`
  asserts; `synthesize._load()` (also accepts `{"findings":[…]}`, fed a list today). ⇒ Wrapping
  breaks `is_final_capture`+dedup tests; a **sibling `<agent>.status`** leaves all consumers
  untouched. **Decision: sibling file** (confirmed by adversarial review + both gate reviewers).
- **`Status:` grammar** — `## Output Contract` block is **byte-identical across all four
  reviewers**. `Status: <COMPLETE|BLOCKED|PARTIAL>` on its own line, **immediately before** the
  final ```json fence. **BLOCKED emits `[]`** + `Blocker Description:` + `What Was Attempted:`.
  **PARTIAL** adds `Completed:` + `Remaining:` + `Confidence: <0-100>`.
- **Only `swift-reviewer.md` Step 2 (~L147–156)** documents the gap + COREDEV-2328.
- **Validators unaffected** (no asset/count/version change ⇒ no version bump). `CHANGELOG.md` has a
  `[Unreleased]` section (repo convention: log every change there).
- **Baselines:** `unittest -s tests` = **121**; `py_compile` clean; `test-hooks.sh` = **98** (it
  already sources `scripts/lib/context.sh` — home for the round-lookup test).

## 2.5 Review findings incorporated

**Adversarial (internal, 5 lenses):** ReDoS in the status regex (A); stale sidecar on in-place
overwrite (B); decoupled status/findings selection + template-echo (C); no lookup path (D); regex
missed realistic drift (E). All folded into §4.

**Dual gate round 1** — gemini APPROVE_WITH_NOTES; codex REQUEST_CHANGES:
- codex C1: lookup `sort -t- -k2 -n` splits the hyphenated path → tested `context_latest_round_dir`.
- codex C2: lifecycle not fail-open → **clear-then-write**.
- codex S3: pin sidecar field names → fixed schema (+ `agent`). codex S4: lookup coverage → shell tests.
- gemini G1: `finditer` not `findall`. gemini G2: persist self-describing `agent` + label lookup output.

**Dual gate round 2** — gemini APPROVE_WITH_NOTES; codex REQUEST_CHANGES (converging 2c2s → 1c2s):
- **codex r2 CRITICAL: regex too permissive** — separator+whitespace both optional matched
  `StatusCOMPLETE`/`statusBlocked` → a status-less response could persist a false BLOCKED → false
  fail-closed. **Fix:** `_STATUS_LINE` now **requires a separator** (`:` `=` `–` `—` `-`), reject
  concatenation/bare-space; tests for concatenated words + copied bullets (§4a/§4b). *Verified
  empirically* — accepts `Status: COMPLETE`, `**Status:**`, `**Status**:`, `- Status:`,
  `Status — BLOCKED`, lowercase; rejects `StatusCOMPLETE`, `Status COMPLETE`, the `| …` template
  echo; ReDoS-safe (200K chars < 5 ms).
- codex r2 STRONG: lifecycle wording overstated if `_clear_status` itself fails → phrased
  **best-effort** (§3.5). codex r2 STRONG: helper huge-suffix `-gt` edge → digit-length guard (§4a-bis).
- codex r2 NOTE: state the `CLAUDE_PLUGIN_ROOT` assumption/fallback (§4c). codex r2 NOTE: add an
  Unreleased CHANGELOG touch since this *does* change Python under `mcp/review-synthesizer/` (§4d).
- **gemini r2 (both labelled critical):** marker drift `**Status**:` — fixed by marker-classes on
  **both** sides of the *required* separator (not gemini's adjacent-quantifier form, which would
  reintroduce the ReDoS); IndexError on no-fence → guard `… if fences else text`. gemini r2 STRONG:
  `_write_status` trailing `\n` (G3).

**Dual gate round 3** — gemini APPROVE_WITH_NOTES; codex REQUEST_CHANGES (converging 1c2s → 1c1s):
- **codex r3 CRITICAL: regex over-accepts copied contract examples** — the marker classes included
  **backticks**, and the reviewer contract presents its status examples in inline-code
  (`` `Status: BLOCKED` ``, `` - `Status: COMPLETE` ``). A status-less reviewer *quoting* the
  contract would persist a false BLOCKED → `[]` → NEEDS DISCUSSION (a false fail-closed). **Fix:**
  **drop the backtick from all marker classes**, so the contract's *actual* (backtick-wrapped)
  example shapes — and prose mentions — no longer match, while plain/bold/blockquote/dash real
  emissions still do. *Verified empirically* (rejects `` `Status: PARTIAL` ``, `` - `Status: COMPLETE` ``,
  prose mentions; accepts `Status: COMPLETE`, `**Status:**`, `**Status**:`, `- Status:`,
  `Status — BLOCKED`, lowercase, `Status: COMPLETE.`; ReDoS-safe 200K < 5 ms). Copied-example-only
  reject tests added (§4b). Residual: a reviewer wrapping its *real* status in inline-code is missed
  → degrades to face value (safe; never a false fail-closed).
- codex r3 STRONG: the Step-2 guard must **validate the sidecar** — honor `.status` only when it
  parses as JSON **and** `agent` equals the loop agent **and** `status` ∈ the three enums; else
  face value (§4c). Cheap protection against a misplaced/corrupt sidecar; preserves fail-open.
- **gemini r3 STRONG:** `_write_status`/`_clear_status` must swallow `OSError` **internally** so a
  status-side failure can't bubble into `capture()`'s try/except and flip a successful `"written"`
  to `"invalid"` — the status block is placed **after** the findings try/except, and the helpers
  never raise (§4a). gemini r3 STRONG: the recipe `cat`s `.status` **before** `.json` (status-first,
  §4c). gemini r3 nice-to-have: allow a trailing period (`Status: COMPLETE.`) — added to the regex.

**Dual gate round 4** — gemini APPROVE_WITH_NOTES ("airtight"); codex REQUEST_CHANGES (1c1s):
- **codex r4 CRITICAL: extraction not constrained to the real trailer** — even with backticks
  dropped, taking the *last* `Status:` line anywhere before the final fence still matches a
  `Status: BLOCKED` inside an **earlier non-json fenced/example block** (codex proved it with a
  ```` ```text ```` block) → false BLOCKED → false fail-closed. **Fix:** **final-trailer coupling** —
  `extract_status` walks **up from the final fence** over only blank + detail-field lines to the
  status; **any other content (prose, a code fence, an example) ends the trailer ⇒ no status** (§4a).
  *Verified*: kills the fenced-`text` repro and a prose-buried example, while real trailers extract
  correctly. Reject test added (§4b).
- codex r4 STRONG: the `.status`/`.json` pair is **not transactional** under concurrent same-agent
  same-round captures → documented as a best-effort residual (§3.5/§6).
- codex r4 confirmed (NOTE): the regex is ReDoS-safe (its own 200K probes stayed linear); the
  sibling shape is right; and the SubagentStop hook fields used by the existing hook (`agent_type`,
  `agent_id`, `agent_transcript_path`, `last_assistant_message`) **match the official Hooks
  reference** (codex web-checked the docs).

**Dual gate round 5** — gemini **APPROVE** ("airtight; clear to implement"); codex REQUEST_CHANGES (1c1s):
- **codex r5 CRITICAL: an *unterminated* earlier fence** wrapping the status immediately before the
  json fence (` ```text ` → `Status: BLOCKED` → ` ```json ` with no closing ` ``` `) still slipped
  past plain trailer-coupling. **Fix:** make extraction **fence-state-aware** — track ```` ``` ````/
  `~~~` toggles top-down; a `Status:` inside *any* open fence (terminated or not) is ignored (§4a).
  *Verified* against both the terminated (r4) and unterminated (r5) repros + well-formed code-fence
  reports. Reject test added (§4b).
- codex r5 STRONG: the "never false fail-closed" wording overclaimed vs. the concurrent stale-pairing
  residual (which passes `agent`+enum validation) → scoped to "no false fail-closed **from
  reviewer-output content**", with the two best-effort residuals called out (§1/§3.5/§4c).
- codex r5 re-confirmed the hook field names against the live Hooks reference.

**Dual gate round 6** — gemini **APPROVE**; codex REQUEST_CHANGES (1c2s):
- **codex r6 CRITICAL: fence tracking wasn't marker-family-aware** — a naive toggle let a `~~~`
  *inside* an open ```` ``` ```` block falsely "close" it (` ```text ` / `~~~` / `Status: BLOCKED` /
  ` ```json `). **Fix:** **CommonMark family + length-aware** fence state (`_FENCE_MARK`; a fence
  closes only on a same-family run ≥ the opener with no info string) — §4a. *Verified* against the
  mixed-marker repro + all prior fence repros + a `~~~`-as-content case.
- codex r6 STRONG: `confidence` "verbatim" wording was ambiguous → clarified that **every** field
  incl. `confidence` is `redact_pii`+`cap`'d ("verbatim" = not numeric-coerced only); PII-in-
  `Confidence` test added (§4a/§4b).
- codex r6 STRONG: a third best-effort residual — a process kill / reader interleave **between** the
  findings replace and the status clear — added to §3.5/§4c.
- gemini r6 nice-to-haves: `2>/dev/null` on the recipe `cat`s (§4c); the multi-line detail-field
  wrap is the accepted fail-open tradeoff (documented telemetry limitation).

---

## 3. Design constraints

1. **Observe-only / fail-open.** A missing/failed status write never blocks; best-effort telemetry.
2. **No PII.** Detail fields → `redact_pii` + `cap`; the status keyword and the `agent` field are
   enum/allowlist literals, never transcript text.
3. **Linear / no ReDoS.** Status regexes run **per line**; a *required* separator literal sits
   between marker-classes (no adjacent unbounded quantifiers); `[ \t]` not `\s`. (Verified.)
4. **Portable, stdlib-only** (Python) / **no GNU-only tools** (shell helper).
5. **`.status` tracks its `.json` (best-effort).** After the findings `os.replace` succeeds, the
   sidecar is **cleared, then (re)written** — so on a *write* failure or a status-less overwrite it
   ends up **absent** (face value), never carrying a prior occupant's status. Best-effort residuals
   (not hard guarantees): (a) a `_clear_status` (`os.remove`) failure (extremely unlikely in the
   just-written dir); (b) the `.json`+`.status` **pair is not transactional** under *concurrent
   same-agent same-round* captures (one process could replace findings while another clears/writes
   status); and (c) a process kill / reader interleave **between** the findings replace and the
   status clear can momentarily expose fresh findings beside a stale status (codex r4/r6 STRONG). The
   SubagentStop flow makes all three rare (subagent stops are delivered sequentially; `agent_id`
   dedup skips true reruns; the clear→write window is two fast syscalls), and the Step-2 guard
   re-validates the sidecar's `agent`+`status` before trusting it. Torn *individual* writes are
   impossible (tmp+`os.replace`, tmp removed on failure).

---

## 4. Implementation

### 4a. `mcp/review-synthesizer/capture.py`

- **Constants:** `STATUS_VALUES = ("COMPLETE","BLOCKED","PARTIAL")`; `STATUS_FIELD_CAP = EVIDENCE_CAP` (500).
- **`_STATUS_LINE`** — one status line; **requires a separator** (rejects concatenation/bare-space —
  codex r2 CRITICAL); marker-tolerant on both sides **but excludes backtick** (handles `**Status:**`
  / `**Status**:` / `- Status:`, while the contract's inline-code examples `` `Status: X` `` and
  `` - `Status: COMPLETE` `` do **not** match — codex r3 CRITICAL); end-anchored (rejects the `| …`
  template echo); a trailing period is allowed (`Status: COMPLETE.` — gemini r3); ReDoS-safe (verified):
  `re.compile(r"^[ \t>*_#-]*status[ \t>*_#]*[:=–—-][ \t>*_#-]*(COMPLETE|BLOCKED|PARTIAL)[ \t>*_#.-]*$", re.IGNORECASE)`
- **`_FIELD_RES`** — per label (`Blocker Description`/`What Was Attempted`/`Completed`/`Remaining`/
  `Confidence`); **backtick excluded** too; required `[:=]` between marker-classes, capture to end-of-line:
  `^[ \t>*_#-]*<words>[ \t>*_#]*[:=][ \t>*_#-]*(.+)$` (`<words>` joined by `[ \t]+`), case-insensitive.
- **`_match_field(line) -> (key, value) | None`** — match one detail-field line via `_FIELD_RES`.
- **`_FENCE_MARK = re.compile(r"^[ \t>]*(`{3,}|~{3,})[ \t]*(.*)$")`** — a code-fence marker line:
  group 1 = the marker run (≥3 backticks **or** tildes), group 2 = the info string / trailing text.
- **`extract_status(text) -> dict | None`** — **CommonMark-fence-aware final-trailer coupling**
  (codex r4/r5/r6 CRITICAL: the status must be the report's *actual* top-level pre-fence
  Output-Contract trailer — never a `Status:` line inside an earlier code fence of any marker family,
  terminated or not, nor behind any prose):
  1. `fences = list(_FENCE.finditer(text))` (**`finditer`**); `region = text[: fences[-1].start()]
     if fences else text` (no IndexError when fence-less — gemini).
  2. `lines = region.splitlines()`; compute `in_code[i]` **top-down with marker-family + length
     awareness** (codex r6): track the open fence's `(char, len)`; a marker line **opens** a fence
     when none is open; while one is open, only a **same-family** run of **length ≥** the opener
     **with no info string** closes it — any other marker line (e.g. `~~~` inside a ```` ``` ````
     block) is content. Every in-fence line (incl. an unterminated tail) is flagged `in_code`.
  3. **Walk UP from the end**: an `in_code[i]` line (fence delimiter / in-fence) **ends the trailer**;
     otherwise skip blank + `_match_field` lines until a top-level `_STATUS_LINE` match (→ `status`,
     `.upper()`, remember index) **or any other content ⇒ return `None`**. So a `Status:` separated
     from the final fence by *any* non-trailer line — or inside *any* code fence — is ignored.
  4. From `lines[status_i+1:]` (the trailer's field lines), first-match per label →
     `cap(redact_pii(val), 500)` — **every** field, **including `confidence`**, is redacted+capped
     ("verbatim" means only *not numeric-coerced*, never un-redacted — codex r6 STRONG). Return
     `{"status": status, …present fields}` (`agent` injected at write time). *Verified*: kills codex's
     terminated / unterminated / **mixed-marker** fence repros + the prose-buried example; still
     extracts real COMPLETE/BLOCKED/PARTIAL trailers (incl. reports with a well-formed code fence in
     their findings).
- **`_status_path` / `_write_status` / `_clear_status`:** `_write_status` writes
  `{"agent": agent, **status}` via tmp+`os.replace`, **trailing `\n`** (gemini G3), tmp removed on
  `(OSError, TypeError)`. `_clear_status` = best-effort `os.remove`, ignore `OSError`. **Both fully
  swallow their own `OSError`/`TypeError` — they never raise** (gemini r3 STRONG).
- **`capture()`** — the status block runs **after** the findings `try/except` succeeds (so a
  status-side issue can never be caught there and flip a real `"written"` into `"invalid"` — gemini
  r3 STRONG). **Clear then write:**
  ```python
  # (reached only after the findings os.replace + _add_agentid succeeded; OUTSIDE that try/except)
  # Keep the sidecar consistent with THIS findings file. Clear any prior status FIRST, then write
  # the freshly-extracted one (if any). A write failure OR a status-less overwrite ⇒ absent (face
  # value), never a stale BLOCKED/PARTIAL beside fresh findings. Helpers never raise. COREDEV-2328.
  _clear_status(dest_dir, agent)
  status = extract_status(message)
  if status:
      _write_status(dest_dir, agent, status)
  return "written"
  ```
- **Pinned sidecar schema** (codex S3 + gemini G2):
  ```jsonc
  { "agent": "security-reviewer",  // always — allowlisted VALID_AGENTS name
    "status": "BLOCKED",           // always — COMPLETE | BLOCKED | PARTIAL
    "blockerDescription": "…", "whatWasAttempted": "…",   // BLOCKED only
    "completed": "…", "remaining": "…", "confidence": "…" } // PARTIAL only — ALL fields redact_pii+cap'd; "confidence" kept as a (redacted) string, just not int-coerced
  ```
- **Docstring:** note the sanitized, observe-only sibling `<agent>.status` (self-id `agent`) and why
  it sits beside (not inside) the findings array.

### 4a-bis. `scripts/lib/context.sh` — portable, tested round-lookup helper (codex C1/S4)

```bash
# Highest round-<N> dir under $1 holding $2's findings, by NUMERIC round. Portable (no GNU sort).
# Prints the dir or nothing. $1=<reviews_dir>/<slug>, $2=agent.
context_latest_round_dir() {
    local base="${1:-}" agent="${2:-}" best="" best_n=-1 d n
    [ -n "$base" ] && [ -n "$agent" ] || return 0
    for d in "$base"/round-*/; do
        [ -d "$d" ] || continue                          # literal glob when no match -> skipped
        d="${d%/}"; n="${d##*/round-}"
        case "$n" in ''|*[!0-9]*|??????*) continue ;; esac  # numeric, <=5 digits (codex r2: no huge-suffix -gt error)
        [ -f "$d/$agent.json" ] || continue
        [ "$n" -gt "$best_n" ] && { best_n="$n"; best="$d"; }
    done
    [ -n "$best" ] && printf '%s' "$best"
}
```
`round-10` beats `round-2` (numeric); hyphens in `base` irrelevant (N from the basename).

### 4b. Tests

**`tests/test_capture.py`** (121 → ~145):
- `TestExtractStatus`: COMPLETE/BLOCKED/PARTIAL; detail-field capture + **PII redaction** + cap
  (incl. **PII in a malformed `Confidence:` value** → redacted, codex r6); markers `**Status:**` /
  `**Status**:` / `- Status:` / `> Status:`; **em/en-dash** separators; **trailing period**
  `Status: COMPLETE.` → COMPLETE (gemini r3); **reject** `StatusCOMPLETE` / `statusBlocked` /
  `Status COMPLETE` (codex r2); **reject the contract's inline-code example shapes**
  `` `Status: BLOCKED` `` / `` - `Status: COMPLETE` `` and an in-prose mention (→ `None`, codex r3);
  **template echo → `None`**; **CommonMark-fence-aware final-trailer coupling** (codex r4/r5/r6): an
  earlier fenced block containing `Status: BLOCKED` before the real json fence → `None` for
  **terminated**, **unterminated**, **and mixed-marker** forms (` ```text ` / `~~~` / `Status` →
  `None`; a `~~~` inside a ```` ``` ```` block is content, with a real top-level status after the
  close → that status); a well-formed code fence in the findings + a real status trailer → real
  status; a status-less report ending in prose **or** a code block → `None`; a prose-buried example
  **earlier** + the real status in the trailer → real wins; **no fence + no status → `None`**
  (IndexError guard); **ReDoS** (65K whitespace < ~50 ms).
- `TestStatusSidecar` (through `capture()`): BLOCKED `[]` → `<agent>.json==[]` **and** `.status`
  with `agent`+`status`+detail keys + **trailing newline**; COMPLETE writes both; **no-status ⇒ no
  `.status`**; **stale cleared on overwrite** (BLOCKED `[]` id1 → status-less real-findings id2
  reuse ⇒ findings present, `.status` gone); invisible to `synthesize._load`; **no PII**; no `.tmp.` leftover.

**`scripts/test-hooks.sh`** (98 → ~104) — `context_latest_round_dir`: highest numeric (`round-10`
not `round-2`); ignores a round lacking the agent's `.json`; empty when none; hyphenated base.

### 4c. `agents/swift-reviewer.md` Step 2 — concrete lookup + tightened guard

Rewrite the Step-2 capture-path paragraph (~L147–156): capture now persists the status; read it
via the tested helper; tighten the guard honestly.

- **Lookup recipe** (bash; same root/slug/round as capture; labels per agent; states the
  `CLAUDE_PLUGIN_ROOT` assumption with a repo-relative fallback — codex r2 NOTE):
  ```bash
  # Read pre-collected reviewer captures' persisted status (COREDEV-2328). CLAUDE_PLUGIN_ROOT is
  # set in the plugin runtime; fall back to the repo-relative path if unset (as the review skills do).
  CTX="${CLAUDE_PLUGIN_ROOT:-.}/scripts/lib/context.sh"; [ -f "$CTX" ] || CTX="scripts/lib/context.sh"
  . "$CTX"
  BASE="$(context_reviews_dir)/$(context_branch_slug "$(context_branch)")"
  for agent in security-reviewer concurrency-reviewer ux-perf-reviewer accessibility-auditor; do
      rd="$(context_latest_round_dir "$BASE" "$agent")"   # highest round holding this agent's findings
      [ -n "$rd" ] || continue
      echo "=== $agent ==="
      [ -f "$rd/$agent.status" ] && cat "$rd/$agent.status" 2>/dev/null   # status FIRST (read status first)
      cat "$rd/$agent.json" 2>/dev/null                                   # then the findings array (same round)
  done
  ```
  Findings + status from the **same** highest round per agent; status printed **before** findings
  (gemini r3 — matches the live-path "read status first" order); the `.status` is self-describing.
- **Guard:** trust a `.status` **only when** it parses as JSON **and** its `agent` equals the loop
  agent **and** its `status` ∈ `{COMPLETE, BLOCKED, PARTIAL}` (codex r3 STRONG — reject a misplaced/
  corrupt sidecar); then apply Step 5 (`BLOCKED` → Needs-Confirmation quoting `blockerDescription` →
  **NEEDS DISCUSSION**; `PARTIAL` → keep findings + non-gating `verification` warning naming
  `remaining`; `COMPLETE` → array authoritative ≡ face value). A `.status` that is absent,
  unparseable, mismatched, or out-of-enum → **pre-Item-12 face value**, fail-open — never worse.
- **Honest guarantee:** holds **whenever a recognizable top-level `Status:` trailer was persisted**
  (parser covers the colon form + bold/dash drift, requiring a real separator, never a `Status:`
  inside a code fence or behind prose); status-less/unrecognizable degrades to face value. **No
  false fail-closed from reviewer-output content**; the only such residuals are the **best-effort
  cases documented in §3.5** (rare, infrastructure-level). No claim of full live-path parity.
- **Consumed fields:** `agent`, `status`, `blockerDescription`, `remaining`;
  `whatWasAttempted`/`completed`/`confidence` are telemetry, intentionally unconsumed.

### 4d. Doc consistency (accuracy-only)

- `capture.py` docstring (4a). `AGENT_CONTRACTS.md §5` — one clause: the capture path persists the
  status as a self-describing sibling `<agent>.status`. **`CHANGELOG.md [Unreleased]`** — a
  *Changed/Fixed* entry: capture now persists the reviewer Output-Contract status (sibling
  `.status`) so the pre-collected-array path honours BLOCKED/PARTIAL (codex r2 NOTE — this is a
  Python change under `mcp/review-synthesizer/`, distinct from the Item-12 "no Python change" note).
  **No** change to `synthesize.py`/`schema.py`/`mcp_server.py`, the hook script, `hooks.json`, the
  README file-list, `agent-orchestration/SKILL.md`, or version/asset counts.

---

## 5. Files changed

| File | Change |
|---|---|
| `mcp/review-synthesizer/capture.py` | status extract / write / clear + docstring |
| `scripts/lib/context.sh` | `context_latest_round_dir` helper |
| `mcp/review-synthesizer/tests/test_capture.py` | `TestExtractStatus` + `TestStatusSidecar` |
| `scripts/test-hooks.sh` | `context_latest_round_dir` cases |
| `agents/swift-reviewer.md` | Step-2 lookup recipe + tightened guard |
| `AGENT_CONTRACTS.md` | §5 one-clause note |
| `CHANGELOG.md` | `[Unreleased]` entry |

**NOT changing:** `synthesize.py`/`schema.py` input shape; `is_final_capture`/`select_round`/dedup;
version/asset counts; the SubagentStop hook script / `hooks.json`.

---

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| ReDoS hangs the sync hook | Per-line scan; required-separator literal between marker-classes; `[ \t]`. Verified 200K < 5 ms. |
| Stale `.status` after overwrite / write failure | **Clear-then-write**; best-effort (residual: `os.remove` failure, ~nil). Regression test. |
| False status from earlier `Status:` content (concatenation, copied examples, fenced blocks — terminated or unterminated) → false fail-closed | **Fence-aware final-trailer coupling** (status must be a top-level line in the contiguous pre-fence trailer; any in-fence `Status:` ignored) + **require separator** + **exclude backtick** + end-anchor; reject tests (codex r2/r3/r4/r5). |
| Misplaced / corrupt sidecar honored | Guard validates the `.status` (JSON parses, `agent` matches, `status` ∈ enum) before trusting it; else face value (codex r3). |
| Status/findings mismatch | Region-before-last-fence; last-status-before-fence; tests. |
| Lookup picks wrong/older round | Tested `context_latest_round_dir` (numeric, no path-sort; digit-length guard). |
| False fail-CLOSED from a merely-absent sidecar | Guard: absent/unparseable ⇒ face value; only a present BLOCKED/PARTIAL gates/warns. |
| PII / anonymous sidecar | `redact_pii`+`cap`; pinned schema with self-describing `agent`; no-PII test. |

---

## 7. Verification (local CI mirror)

1. `py_compile mcp/review-synthesizer/*.py` · 2. `unittest -s mcp/review-synthesizer/tests` → **~145**
(was 121) · 3. `synthesize.py samples/*.json --changed …` unchanged · 4. `shellcheck -S warning
scripts/*.sh scripts/lib/*.sh` clean · 5. `VERSION_SYNC_ENFORCE=strict validate-version-sync.sh`
green · 6. `validate-plugin-assembly.py --root . --strict` green · 7. `test-hooks.sh` → **~104**
(was 98) · 8. targeted: BLOCKED `[]` → `.json==[]` + `.status` w/ `agent`+`BLOCKED`+redacted+`\n`;
status-less rerun clears sidecar; 65K-whitespace status < ~50 ms; `context_latest_round_dir`
picks `round-10`.

---

## 8. Process gates

- **Pre-implementation (mandatory):** codex + gemini (pty-capture), **codex-weighted**. gemini
  AWN×4 → **APPROVE** (r5, r6); codex RC, each round a deeper real edge in `extract_status`
  (concatenation → backtick examples → terminated fence → unterminated fence → mixed-marker fence).
  v8 makes fence-handling **CommonMark-correct** (family+length aware), which closes the class.
  **Re-gate both on v8** → require APPROVE / APPROVE_WITH_NOTES before code edits.
- **Post-implementation (mandatory):** re-run both on the diff; iterate to convergence.
- **Jira/commit:** In Progress; notes throughout; `fix(COREDEV-2328): …` + the
  `Co-Authored-By: Claude Opus 4.8 (1M context)` trailer; commit/PR only when asked.

---

## 9. Sequencing

1–3. ✅ Ground-truth → plan v1 + baselines → adversarial review → v2.
4. ✅ r1 → v3. 5. ✅ r2 → v4. 6. ✅ r3 → v5. 7. ✅ r4 → v6. 8. ✅ r5 → v7. 9. ✅ r6 → v8 (this doc).
10. Re-gate both on v8 → converge to APPROVE / APPROVE_WITH_NOTES.
11. Implement 4a → 4a-bis → 4b → 4c → 4d. 12. Local CI mirror (§7).
13. Post-implementation dual gate → converge. 14. Report; commit/push/PR on request.
