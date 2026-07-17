# COREDEV-2504 — `${CLAUDE_PLUGIN_ROOT}` convention + reviewer-recipe timeout hardening

**Status:** 🔬 **v2 — awaiting re-review.** R1: gemini `APPROVE`; codex `REQUEST_CHANGES` (3 must-fix, all
verified real and folded in below → §2/§4/§6): (a) stale `:-.` prose/comments + CHANGELOG.md left false by
the edits; (b) the regression guard must enforce the EXACT `${CLAUDE_PLUGIN_ROOT}` token, not just reject
`:-` (evaded by `-.`/`:?`/`:=`/unbraced `$CLAUDE_PLUGIN_ROOT`); (c) state the version bump is conditional on
2.5.1 staying unpublished. Do not implement until both APPROVE / APPROVE_WITH_NOTES and `review-synthesis`
records the Combined verdict.
**Ticket:** COREDEV-2504 (Bug, High) · **Branch:** `fix/COREDEV-2504-plugin-root-convention` (off
`origin/alpha`, HEAD `8a803a2`) · **Targets:** `alpha` (then rides #52 → main on the user's word).
**Source:** A2Z audit (60 agents, adversarially verified), re-triaged against post-#53 alpha.

## 1. Context & root cause (doc-verified)

Claude Code substitutes the **bare `${CLAUDE_PLUGIN_ROOT}` token inline** in agent/skill markdown *bodies*
before the model reads them (code.claude.com/docs plugins-reference § Environment variables: "Skill and
agent content → placeholders resolve **anywhere they appear**"). The variable is **not** exported as an env
var to an agent's Bash-tool subprocess (only to hook / MCP / LSP processes) — confirmed empirically
(`echo "$CLAUDE_PLUGIN_ROOT"` is empty in a tool-call shell).

The bash default-value spelling **`${CLAUDE_PLUGIN_ROOT:-.}` is NOT recognized** by the substitution logic
(it is not the exact token). It therefore reaches the shell literally; with the env var unset it expands to
`.` — the **consumer app repo**, which ships none of the plugin scripts.

**Impact (HIGH):** in a consumer install the reviewer-roster fence exits 127 (every reviewer read as
"missing") and the fail-closed Plan Review Gate can never record a pass. CI never sees it — CI runs from the
plugin root, where `.` accidentally resolves. The #53 merge (COREDEV-2503) *added* the 8th site:
`swift-reviewer.md:389` previously used the working bare form (an F6 regression I introduced).

## 2. Scope

**In:**
- HIGH — replace `${CLAUDE_PLUGIN_ROOT:-.}` → bare `${CLAUDE_PLUGIN_ROOT}` at the 8 command sites (see §4).
- **Adjacent stale text made false by the edits (R1 codex must-fix a):** the three inline comments that
  justify `:-.` — `swift-reviewer.md:396`, `implement/SKILL.md:132`, `brainstorm/SKILL.md:187` — and the
  `test_doc_gates.py:16` class name/comment/failure-message + `CHANGELOG.md:36` (which advertises
  `(${…:-.} + exit "$BUILD_VERIFY")` as the COREDEV-2503 F6 fix). Repo policy requires recording every change,
  so CHANGELOG.md gets a corrective note under the unreleased 2.5.1 entry.
- Update the doc-gate test that currently *asserts* the broken `:-.` form → assert the bare form, and add a
  guard that enforces the EXACT token (R1 codex must-fix b — see §4).
- Medium (pty timeout) — `skills/codex-review/SKILL.md` two `--timeout 600` → `1200`, matching
  `gemini-review` (already 1200), WITH a brief inline comment stating the observed `xhigh` motivation
  (mirroring gemini-review's). Under the mandated `xhigh` effort, 600s SIGTERMs codex mid-run → exit 124 /
  partial transcript / MISSING-verdict retry loop. Keep the existing Monitor guidance (an outer runner
  timeout could otherwise kill the run before the wrapper's 1200s).

**Explicitly out (refuted):** the audit's paired "bare `${CLAUDE_PLUGIN_ROOT}` with no fallback misreports
the reviewer unavailable" medium. Per the docs, **bare is the correct form** for agent/skill bodies; that
reading came from running the command directly in a terminal (no substitution), not through an agent body.
Changing the already-correct bare sites (hooks.json, gemini-review, codex-review pty invocations) would be a
regression.

**Deferred (separate follow-ups, not gate-correctness):** the remaining audit mediums/lows (test-runner
`-resultBundlePath` cleanup, pre-commit PII scan ERE-under-BRE + `*.swift`-only filter, logic-engineer
unreachable skills, shared `/tmp/*-out.txt` clobber, `allowed-tools`/`disallowed-tools` grants, `model:`
pins vs CONTRACTS §11). The delivery-chain hitch (installed plugin at 2.3.1) is closed by **merging #52** +
a plugin update — an operational step, not this branch.

## 3. Guiding principle

Match the **existing working convention** (bare token, as hooks.json / gemini-review / codex-review already
use). Do NOT invent a new spelling, and do NOT add repo-relative fallbacks to the 7 gate-critical commands:
R1 codex is right that **failing closed is preferable to sourcing a coincidental consumer-repo script** —
adding `|| CTX="scripts/…"` everywhere risks executing an unrelated same-named file in the consumer tree.
Keep the ONE pre-existing existence-check at `swift-reviewer.md:229` (both reviewers accept it; the same
coincidental-source caveat applies but it predates this change and is out of scope). Manual users run the
repo-relative command explicitly, as the skill prose already documents.

## 4. The 8 sites (all `:-.` → bare `${CLAUDE_PLUGIN_ROOT}`)

| # | File:line | Command |
|---|---|---|
| 1 | agents/swift-reviewer.md:178 | `bash "…/scripts/review/reviewer-roster.sh"` |
| 2 | agents/swift-reviewer.md:229 | `CTX="…/scripts/lib/context.sh"; [ -f "$CTX" ] \|\| CTX="scripts/lib/context.sh"` (keep fallback) |
| 3 | agents/swift-reviewer.md:389 | `bash "…/scripts/review/build-verify.sh"` (the #53 F6 regression) |
| 4 | skills/create-feature-plan/SKILL.md:70 | `python3 "…/scripts/review-verdict.py" snapshot` |
| 5 | skills/review-synthesis/SKILL.md:121 | `python3 "…/scripts/review-verdict.py" write` |
| 6 | skills/brainstorm/SKILL.md:173 | `python3 "…/scripts/review-verdict.py" snapshot` |
| 7 | skills/brainstorm/SKILL.md:189 | `python3 "…/scripts/review-verdict.py" write` |
| 8 | skills/implement/SKILL.md:134 | `python3 "…/scripts/review-verdict.py" verify` |

**Stale `:-.` prose/comments to update (R1 codex must-fix a):**
- `agents/swift-reviewer.md:396` — comment "`${…:-.}` matches the siblings" → reword to the bare convention.
- `skills/implement/SKILL.md:132` — "`:-.` so the recipe DOES what the prose…" → reword.
- `skills/brainstorm/SKILL.md:187` — "`:-.` — unset would resolve to the absolute `/scripts/…`…" → reword.
- `CHANGELOG.md:36` — the 2.5.1 F6 line advertises `(${…:-.} + exit …)`; add a corrective note in the
  unreleased 2.5.1 section recording the `:-.`→bare fix (COREDEV-2504) and why (`:-.` is not substituted).

**Test (R1 codex must-fix b):** `scripts/tests/test_doc_gates.py` (the `F6_Step4FailClosed` class ~line 16-20)
currently asserts `${CLAUDE_PLUGIN_ROOT:-.}/scripts/review/build-verify.sh` and its comment says the `:-.`
fallback is *required*. Rename/reword the class + messages, assert the **bare** `${CLAUDE_PLUGIN_ROOT}/scripts/
review/build-verify.sh` form, AND add a guard that enforces the exact token: scan every `CLAUDE_PLUGIN_ROOT`
occurrence in `agents/` + `skills/` and fail if ANY is not the literal `${CLAUDE_PLUGIN_ROOT}` — i.e. reject
`${CLAUDE_PLUGIN_ROOT:-…}`, `${CLAUDE_PLUGIN_ROOT-…}`, `${CLAUDE_PLUGIN_ROOT:?…}`, `${CLAUDE_PLUGIN_ROOT:=…}`,
and unbraced `$CLAUDE_PLUGIN_ROOT` (a bare-`:-`-only reject is evadable). Implementation sketch: regex
`\$\{?CLAUDE_PLUGIN_ROOT\b[^}]*\}?` over the two trees, assert every match `== "${CLAUDE_PLUGIN_ROOT}"`.
(The `.py` test file's own `${…}`-in-string literals are not under `agents/`+`skills/`, so they don't trip
the guard.)

## 5. Verification

- `grep -rn 'CLAUDE_PLUGIN_ROOT:-' agents/ skills/` returns **zero** rows.
- Bare-token sites unchanged: hooks.json, gemini-review, codex-review pty invocations.
- `codex-review/SKILL.md` shows `--timeout 1200` (×2); no `--timeout 600` remains.
- All 7 CI gates green (assembly/hooks/version-sync 2.5.1, shellcheck, MCP suite, scripts suite incl. the
  updated `test_doc_gates`, hook harness).
- New regression test in `test_doc_gates.py` fails if `:-.` is reintroduced (mutation proof).

## 6. Risks

- **Low.** Pure doc-text substitution + a test + a timeout constant. No runtime script logic changes.
- The only behavioral change is that the substituted agent path now resolves to the plugin install dir in a
  consumer session (the intended behavior) instead of `.`.
- **Version (R1 codex must-fix c):** no bump is needed **only if** `2.5.1` remains unpublished until this fix
  is included. Current state: `origin/main`/marketplace = `2.4.2`, `origin/alpha` = `2.5.1`, and PR #52
  (alpha→main) is unmerged — so `2.5.1` has NOT reached installed users (they're on `2.3.1`); this fix lands
  in the *same* unreleased `2.5.1` that #52 will promote. **Conditional:** if any marketplace scope (e.g. an
  `alpha` channel) has already served `2.5.1` to a real install, bump to `2.5.2` — the manifest `version`
  controls whether installed users receive the update. **Open question for the user to confirm before
  promotion:** is `alpha` a served marketplace channel? If yes → `2.5.2`. `validate-version-sync` must stay
  green at whatever version is chosen (CHANGELOG heading + README H1 + counts in sync).

## 7. Implementation order

1. Edit the 8 command sites (`:-.` → bare); keep the `swift-reviewer.md:229` existence-check.
2. Reword the 3 stale `:-.` comments (swift-reviewer.md:396, implement:132, brainstorm:187) to the bare
   convention; add the CHANGELOG.md:36 corrective note under the unreleased 2.5.1 section.
3. `codex-review/SKILL.md` 600 → 1200 (×2) + xhigh-motivation comment; keep Monitor guidance.
4. Update `test_doc_gates.py` `F6_Step4FailClosed` (rename/reword; assert bare form) + add the exact-token
   guard test over `agents/`+`skills/`; mutation-prove BOTH directions (revert a site → fails; loosen the
   guard to `:-`-only → an injected `${…-.}`/unbraced form still fails).
5. Run the full CI gate set (assembly/hooks/version-sync/shellcheck/MCP/scripts/hook-harness); `grep`
   verification (§5): zero `:-` rows, bare sites intact, `--timeout 1200` ×2, no `--timeout 600`.
6. PR → alpha; drive codex/gemini bot review to convergence. Confirm the version question (§6) with the user
   before #52 promotes.
