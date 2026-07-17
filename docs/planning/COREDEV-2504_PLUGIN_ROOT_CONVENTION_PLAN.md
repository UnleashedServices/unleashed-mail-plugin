# COREDEV-2504 — `${CLAUDE_PLUGIN_ROOT}` convention + reviewer-recipe timeout hardening

**Status:** 🔬 **DRAFT (v1) — awaiting dual plan-review gate (codex `xhigh` + gemini).** Do not implement
until both APPROVE / APPROVE_WITH_NOTES and `review-synthesis` records the Combined verdict.
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
- HIGH — replace `${CLAUDE_PLUGIN_ROOT:-.}` → bare `${CLAUDE_PLUGIN_ROOT}` at 8 sites (see §4).
- Update the doc-gate test that currently *asserts* the broken `:-.` form.
- Medium (pty timeout) — `skills/codex-review/SKILL.md` two `--timeout 600` → `1200`, matching
  `gemini-review` (already 1200). Under the mandated `xhigh` effort, 600s → exit 124 / partial transcript /
  MISSING-verdict retry loop.

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
use). Do NOT invent a new spelling. Where a body already carries a repo-relative existence-check fallback
(`swift-reviewer.md:229`, and the prose notes in review-synthesis/implement/codex-review), **keep it** — it
is a harmless belt-and-suspenders for a human copy-pasting the command directly inside the plugin repo (where
`.`/repo-relative resolves); it never fires in the substituted agent path.

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

Test: `scripts/tests/test_doc_gates.py:20` asserts `${CLAUDE_PLUGIN_ROOT:-.}/scripts/review/build-verify.sh`
is present in `swift-reviewer.md` → update to assert the bare `${CLAUDE_PLUGIN_ROOT}/scripts/review/
build-verify.sh` form (and add an assertion that **no** `${CLAUDE_PLUGIN_ROOT:-` spelling remains anywhere in
`agents/` + `skills/`, so a future edit can't reintroduce it).

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
- Version: no plugin-version bump required (doc/skill/agent body edits + test; asset counts unchanged) —
  confirm `validate-version-sync` still passes at 2.5.1.

## 7. Implementation order

1. `sed`/Edit the 8 sites (`:-.` → bare); keep the `swift-reviewer.md:229` existence-check.
2. `codex-review/SKILL.md` 600 → 1200 (×2).
3. Update `test_doc_gates.py` (assert bare form + no-`:-.`-anywhere guard); mutation-prove.
4. Run the full CI gate set; `grep` verification (§5).
5. PR → alpha; drive codex/gemini bot review to convergence.
