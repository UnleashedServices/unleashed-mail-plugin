# COREDEV-2503 — Quality/Review-Gate Fail-Open Remediation

**Status:** ✅ **APPROVED (v9) — dual plan-review gate satisfied at Round 9: gemini `APPROVE`, codex
`APPROVE_WITH_NOTES` (no must-fix items).** Ready for implementation. Run `review-synthesis` to record the
Combined verdict, then implement per §7 (each fix mutation-proved).
Convergence history (blocking items/round): R1 codex `RC`(9)/gemini `AWN`→v2; R2 both `RC`(2)→v3; R3 gemini
`APPROVE`/codex `RC`(3)→v4; R4 both `RC`(F4 >8KB, F5 test)→v5; R5 codex `RC`/gemini misframe→v6; R6 both
`RC`(precise-parser quote-blindness + exit-2 contract)→v7; R7 gemini `APPROVE`/codex `RC`(2 fixture nits)→v8;
R8 gemini `APPROVE`/codex `RC`(1 dd-label nit)→v9; **R9 gemini `APPROVE` + codex `APPROVE_WITH_NOTES`**.
All non-F4 findings sound since R2; F5 since R5; F4 design since R7. The F4 saga (a security-critical
shell-command parser) drove most rounds and converged on ONE structured quote/escape/operator-aware O(n)
lexer replacing the ad-hoc greps.
**Ticket:** COREDEV-2503 · **Branch:** `feat/COREDEV-2503-gate-hardening` (off `origin/alpha`, HEAD `aade3e1`)
**Blocks:** PR #52 (`alpha → main`, v2.4.2 → v2.5.0) is **parked** until this lands on `alpha`.
**Round-1 reviews:** `docs/planning/reviews/COREDEV-2503_{codex,gemini}_plan_review_r1.txt`.

## 1. Context

An external audit of v2.5.0 found fail-open defects in the review/quality gates that are the release's
marquee features. The repo's validators (`validate-plugin-assembly --strict`, `validate-version-sync`)
pass — these are **logic/gate defects the validators don't cover**. Every finding below was **reproduced
against the real `origin/alpha` code** before planning. Excluded after verification: **F7** (SIGPIPE) —
refuted, writer is a `printf` builtin. **F9** — reclassified (see §4): not a fail-open, but round-1 codex
showed it *is* live gate-policy drift, not mere prose cleanup.

**Process note (F14):** the CFR + verdict-gate code shipped without the mandated plan doc + dual review.
This document is that correction; round-1 already caught 9 real gaps in my first draft — evidence the gate
matters.

## 2. Scope

In: 14 confirmed findings (F1–F6, F8, F10–F13, B1, B2, B4) + regression tests; below-cut B6/B7; F9 gate-drift
fix. **B3 is re-scoped** (round-1: the original inventory was wrong — see §4). Deferred to a follow-up:
**B5** (CI perf) and **B8** (commit-type convention) — not gate-correctness.

## 3. Guiding principle (narrowed after round-1)

Codex correctly flagged that a blanket "everything fails closed" invariant conflicts with **deliberate**
existing fail-opens (`scripts/lib/hook-io.sh:19-20`, `scripts/stop-quality-marker-gate.sh:41-49,86-94`,
`scripts/lib/marker.sh:10-11` intentionally fail open when payload parsing, clock, repo context, or sentinel
persistence fails — so a non-security quality *nudge* never wedges the user). The narrowed invariant:

> **Security/correctness gates fail closed.** The traversal guards (F2/F3), the captureId/quorum floor
> (F1/B2), and the sensitive-file write guard (F4/F12) must *block / ask / quarantine* on any undecidable
> input — never silently pass. The **Stop quality-gate's** environmental fail-opens (missing repo/clock/
> parse) are a deliberate UX choice and are **retained**; F5 must not *add* a new fail-open and must clean
> up its own sentinel. Where this remediation touches a security/correctness gate, "can't decide" ⇒ ask/
> quarantine; where it touches the quality nudge, we preserve the existing non-wedging behavior.

Other principles unchanged: **mutation proof** (revert → the new test fails; and where an *existing* test
asserts the old behavior, it is inverted/replaced, not left contradictory); **match the real hardened
opener** (not an imagined one — see F11); **minimal local edits**.

---

## 4. Findings, fixes, and proofs (revised)

### F1 — captureId waives the digest-distinctness floor (High) · `scripts/review-verdict.py`
**Root cause (confirmed).** `_quorum_problem` (~L168–179) early-`return None`s when captureIds are present +
distinct, skipping the content-digest floor (~L183–186). captureId has no authenticity binding; two forged
distinct captureIds behind one identical transcript → `GATE OK — APPROVE`, exit 0 (reproduced end-to-end).
**Fix.** Delete the captureId short-circuit so the digest floor runs on **every** approving path. captureId
may supplement, never replace, content-distinctness.
**Mutation proof + test-inversion (round-1).** The **existing** test `scripts/tests/test_review_verdict.py:
157-175` asserts the *old* (bypass) behavior — it must be **inverted/replaced**, not merely added to. New
assertion: two reviewers, same `transcriptSha256`, distinct paths + distinct captureIds → `_quorum_problem`
returns non-None. Revert → fails.

### F2 + F3 — traversal fail-opens, unified helper (High / Med) · `mcp/review-synthesizer/{mcp_server,schema}.py`
**Root cause (confirmed).** `_abs_or_traversal` (mcp_server.py ~L61) inspects the raw path (backslash
literal) while `canonical_path` (schema.py ~L150) folds `\`→`/` — so `\Sources\Auth.swift` (→ `/Sources/…`)
and `..\..\x` (→ `../../x`) bypass the changed_files guard (F2). `parse_finding` (schema.py ~L191) has **no**
traversal/abs reject at all (F3); a `..`/absolute finding path demotes to pre-existing → provisional APPROVE.
Round-1 codex: the F3 fix as first drafted **still missed Windows drive-absolute** (`C:/repo/X.swift`).
**Fix (one schema-owned helper).** Add `_is_abs_or_traversal(path) -> bool` in **`schema.py`** (schema.py
must not import mcp_server — circular; mcp_server imports schema). It **normalizes separators** then rejects:
POSIX-absolute (`/…`), UNC (`\\…` → `//…`), **drive-absolute (`^[A-Za-z]:[\\/]`)**, and any `..` segment.
Use it in **both** `parse_finding` (quarantine → schema failure) and mcp_server's `changed_files` guard.
Quarantine is correct: `mcp_server.py:182-191` collects schema failures and `synthesize.py:256-264` turns an
otherwise-approving verdict into **NEEDS_DISCUSSION** (confirmed).
**Mutation proof + test updates.** New: helper rejects `\S\A`, `..\..\x`, `/abs`, `C:/x`, `C:\x`; a `..`
finding path → quarantined + `synthesize` not APPROVE. **Update** `mcp/review-synthesizer/tests/test_mcp_
server.py:156-164` (which currently asserts a literal-backslash POSIX path is *valid*) and **document the
policy**: rare POSIX filenames containing a literal backslash are now rejected (deliberate). Normal
git-relative forward-slash paths remain valid (positive test).

### F4 — O(n²) parser + obfuscation + temp-file fail-opens (High) · `scripts/sensitive-file-guard.sh`
**Root cause (confirmed, and broader than v1).** (a) `_split_segments` (L81–145) is O(n²) — measured
crosses the 10s PreToolUse timeout at ~23KB; a SIGTERM-killed hook exits non-zero → JSON discarded → **no
decision → fail-open**. Round-1 codex added three real gaps the v1 fix missed: (b) the >16KB `grep`
fallback still passes when a **quoted/obfuscated** basename (`rm Key"chain".swift`) evades the raw regex;
(c) `${#cmd}` counts **locale chars, not bytes**, so multibyte input exceeds the intended bound; (d)
independent fail-open — `read -ra … <<<` (L162, L261) and the heredoc (L382) require **temp-file
creation**; in a temp-constrained env even `rm Keychain.swift` errors → no JSON → exit 0.
**Fix (fail-closed) — ONE structured, whole-pipeline O(n), quote/escape/operator-aware parser (rounds 1–6).**
Rounds 1–5 chased a separate >8KB fallback; round 6 (codex + gemini, **reproduced**) showed the *precise
path itself* is not quote-aware: redirect extraction scans raw segments so a **quoted** `echo '> Keychain.swift'`
falsely asks (`:255–260`), and the basename grep doesn't reconstruct a mid-word-quoted word so
`rm Key"chain".swift` **bypasses** (`:365–369`); `cp`/`mv` strip only *surrounding* quotes (`:375`). (The
`mv`-all-operands / `cp`-dest-only *logic* is otherwise correct.) So the fix is a single structured lexer
used at all sizes:
1. **Replace the ad-hoc greps with a structured O(n) lexer** (one `python3` pass; python3 is already a hook
   dependency via `scripts/lib/hook-io.sh`). It tokenizes the whole pipeline once — **reconstructing
   quoted/escaped word fragments** into de-quoted words (`Key"chain".swift` → `Keychain.swift`) and
   **classifying each operator as active / quoted / backslash-escaped** (`>` active; `'>'` and `\>` literal).
   The write-context decision (verbs, active-redirect targets, `cp`/`install`/`ln` dest, `mv`/`rename`
   all-operands, F12 forms) runs over this token stream, **replacing** the quote-blind redirect grep
   (`:255–260`), the basename grep (`:365–369`), and the surrounding-only strip (`:375`). This is
   **whole-pipeline O(n)** — the downstream `cand="${cand}\n…"` growing-string accumulation (also quadratic)
   is replaced too, **not** just `_split_segments`; keeping the NUL-segment contract alone is insufficient
   (round-6 codex).
2. **DoS backstop.** A pre-parse `LC_ALL=C` **256KB** byte cap → unconditional **exit-0 `ask`** (fail-closed
   safety net far above any real command).
3. **Correct failure contract (round-6 codex).** Claude Code **ignores stdout JSON on exit 2**, so an `ask`
   MUST be **exit 0** with the structured JSON (a normal sensitive-write → exit-0 `ask`). A genuine
   tokenizer failure (unparseable input / lexer crash) → fail-closed **exit-2 denial** with a stderr reason
   (a hard block on a command the guard cannot parse). Removing the `<<<`/heredoc constructs means an invalid
   `$TMPDIR` is **no longer a failure** — such a sensitive write just yields the normal exit-0 `ask`.
4. Do **not** raise the hooks.json timeout.
**Residual (documented, §8).** Base64/variable-indirection still evades any textual heuristic (best-effort
vs *accidental* writes). Guaranteed: quote/escape/operator-aware write-context decision at all sizes; no
exit-0-without-decision; read-only and quoted/escaped-operator commands never ask.
**Mutation proof.**
- **Perf (whole-pipeline O(n)):** a 40–80KB command **and** an adversarial **many-operands** command that
  produces candidates — e.g. a long `mv a b c … Keychain.swift` or `tee … Keychain.swift` (round-7 codex: the
  fixture must hit a candidate-producing arm to exercise the downstream accumulation, not just
  `_split_segments`) — each return within `timeout 8`; revert the linear lexer *or* the linear candidate
  accumulation → O(n²) times out.
- **Mutation-kills (WRONG in the current parser; the fix makes them right — revert → wrong again):**
  `rm Key"chain".swift` → ask (currently **bypasses**); quoted `echo '> Keychain.swift'` → **no** ask
  (currently **over-asks**); escaped `echo \> Keychain.swift` → **no** ask (currently over-asks).
- **Preservation regressions (already correct in the current parser; the change must NOT break them — these
  guard against a lexer regression, they are not revert-kills of a new fix):** active `echo x > Keychain.swift`
  → ask; `mv Keychain.swift /tmp/x` → ask; source-only `cp Keychain.swift /tmp/x` → **no** ask;
  `grep …Keychain.swift` → **no** ask. (`dd of=Keychain.swift` is **not** handled by the current parser — it
  is an **F12 mutation-kill**, not a preservation test — round-8 codex.)
- **Failure contract:** invalid `TMPDIR` on a sensitive write → normal **ask / exit-0** (proves temp-file
  dependence removed); a **separately injected** tokenizer failure → **exit-2 denial** (fail-closed).
- **DoS backstop:** an **otherwise-benign** >256KB command → ask; revert the cap → **no** ask (so the cap is
  what's proven).
All existing `test-hooks.sh` assertions (read-only 106/129, `sed -i` write) are preserved.

### F5 — Stop-gate sentinel keying + reset (Med) · `scripts/stop-quality-marker-gate.sh`, `scripts/lib/marker.sh`
**Root cause (confirmed).** Sentinel keyed only by repo (filename hash, ~L52) + commit (~L75); no session
component, and this PR flips default `warn`→`enforce` (~L27), so a commit that blocked once passes in every
later session; 0644 sentinel is plantable (same-user). Round-1 codex added: (a) a stable identifier is
required (a per-invocation nonce would defeat same-session dedup and could wedge — gemini concurred); (b)
the **success path resets only** `stop-last-blocked-${hash}` (`marker.sh:96-110`), so a session-suffixed
sentinel would **survive** and a later same-session regression would wrongly pass.
**Fix.** (1) Derive a **hashed session key** from the Stop payload's `session_id` (available on Claude Code
2.1.211; `hook_str session_id`), falling back to a **stable** hash of `transcript_path` (a session-stable
value) — **never a random nonce**. Fold it (hashed, filename-safe) into the sentinel filename (~L52) and the
compared/written token (~L75/L90). (2) Extend the **success reset** to clear **all repo-matching session
sentinels** — round-3 codex: `marker_write` (`marker.sh:96-110`) carries **no session payload**, so it
cannot target one session's sentinel; the success path must glob-clear `stop-last-blocked-${repohash}-*`
(every session's sentinel for this repo/commit). (3) `chmod 600`. (4) Keep the enforce default —
`stop_hook_active` remains loop-guard #1 (`stop-quality-marker-gate.sh:37-38`), so session keying does
**not** weaken anti-runaway.
**Mutation proof (must distinguish a stable key from a nonce — round-2/3 codex).** **Precondition (round-3
codex #3):** every harness Stop payload sets **`stop_hook_active: false`** so execution reaches loop-guard #2
(the sentinel); with `true`, guard #1 short-circuits and a *nonce* impl would also pass, defeating the
discriminator. Cases: (a) **same-session dedup:** two Stops with the **same** `session_id` on a failing
marker — first blocks, second **passes** (budget spent). A nonce mints a fresh key on the 2nd → re-blocks →
wedge, so **(a) FAILS under a nonce** (the discriminator). (b) **cross-session re-block:** a fresh
`session_id`, same commit+marker → blocks again (revert keying → session-2 wrongly passes). (c) **success
reset (all-session, round-4 codex):** **seed two** session sentinels (session-1 + session-2, same
repo/commit), then a successful marker write → assert **both** repo-matching sentinels are removed **and**
both sessions subsequently re-block; revert the glob-clear to a single-session reset → the other session's
sentinel survives and wrongly passes. (a) needs `stop_hook_active:false` to mean anything; (a)+(b) pin
stable-within-session + fresh-across-session.

### F6 — swift-reviewer Step-4 silent skip (High) · `agents/swift-reviewer.md`
**Root cause (confirmed).** Step-4 fence (~L386–394) uses bare `${CLAUDE_PLUGIN_ROOT}` (L389, siblings use
`:-.`) and ends on `echo` (L393) → exits 0 even on a 127 (`build-verify.sh` not found) → build/lint/test
silently skipped.
**Fix.** `${CLAUDE_PLUGIN_ROOT:-.}` (L389) + append `exit "$BUILD_VERIFY"` (fail-closed, propagate code).
**Mutation proof (doc-lint).** New check isolates the unique `build-verify.sh` fence and asserts it contains
`:-.` and a **trailing** `exit "$BUILD_VERIFY"`. Revert → fails.

### F8 — secure-IO size cap with a bounded read (Low) · `scripts/review-verdict.py`
**Root cause (confirmed partial).** `_read_regular_file` (~L198–213) rejects FIFO/device via `S_ISREG` but
has no size cap. Round-1 codex: `fstat().st_size` alone has a **grow-after-check race**.
**Fix.** After `S_ISREG`, do a **bounded read of cap+1 bytes** (cap = 65536) and reject on overflow — not a
size-only check. Fail-closed.
**Mutation proof.** A >64KB (and a grow-after-stat) regular file is refused. Revert → accepted (fails).

### F10 — model-id regex anchoring (Low) · `scripts/validate-plugin-assembly.py`
**Root cause (confirmed).** L76 `re.match(r"^[a-z]+-[a-z0-9-]*\d", …)` — start-anchored only.
**Fix.** Use `re.fullmatch(r"[a-z]+-[a-z0-9-]*\d[a-z0-9-]*")` (or `\Z`, **not** `$` — terminal-newline
semantics). Accepts `claude-opus-4-8`; rejects `claude-opus-4-8 rm -rf` and trailing-newline injection.
**Mutation proof.** New cases pass/fail accordingly. Revert → the malformed case passes (fails).

### F11 — capture.py symlink-followable writes (Med) · `mcp/review-synthesizer/capture.py`
**Root cause (confirmed).** Three writers (~L380, L438, L462) use plain `open(tmp,"w")` on a predictable
`dest+".tmp."+pid` — no `O_NOFOLLOW`, default 0644; a planted symlink is followed (clobber). Round-1 codex
corrections: (a) the twins (`review-verdict.py:231-242`, `pty-capture.py:62-90`) use `O_NOFOLLOW` but
**not `O_EXCL`** — so **do not claim "matches the twins"**; (b) `capture()` **catches** write errors and
returns `"invalid"`/`"no-fence"` (~L435–479) — it does **not raise**, so a "capture raises" test is wrong.
**Fix.** Route all three writes through a shared opener using `O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW`, 0600
(matching the twins), **plus `O_EXCL`** as an added improvement (documented as *stronger* than the twins,
closing the predictable-name race). Keep the `os.replace` atomic swap.
**Mutation proof.** Plant a symlink at the computed tmp path for **each** of the three call sites (status,
status-only-`[]`, findings) → the victim file is **untouched** and capture returns a non-written status;
revert any one site → that victim is truncated (fails). (Assert on the victim, not on an exception.)

### F12 — guard-bypass cluster, corrected fixtures (Med) · `scripts/sensitive-file-guard.sh`
**Root cause (confirmed).** Verb/target extraction misses `( rm … )` (subshell), `sed --in-place` long-form,
`>|` clobber, and `xargs rm`/`dd of=`. Round-1 codex corrections: (a) `*.p12` is **not** in the sensitive set
(`L23–43`), so a `find … -name '*.p12' -delete` fixture is **out of policy** — and expanding the set to
`*.p12` would wrongly `ask` on the legit signing recipe at `agents/ci-engineer.md:300`; **drop that fixture**
and test an in-policy target (e.g. `Keychain.swift`); (b) sed handling must cover **option ordering,
`--in-place=SUFFIX`, short-option clusters, and multiple targets** — current logic inspects only the last
token (`L303–307`).
**Fix.** Arms for: subshell-group stripping before verb resolution; broadened sed matcher (ordering / `=SUFFIX`
/ clusters / multi-target); `>|` as a write redirect; **`find … -delete`**; `xargs rm` and `dd of=` target
detection. All emit `ask`.
**Mutation proof (in-policy fixtures only — round-7 codex: `Secrets.swift` is NOT in the guard's sensitive
set at `:23`).** `( rm Keychain.swift )`, `sed --in-place=bak … Info.plist`, `echo x >| Keychain.swift`,
`find . -name 'Keychain.swift' -delete`, `printf 'Keychain.swift' | xargs rm`, `dd of=Keychain.swift` each
`ask`. Revert each arm → its case yields no decision (fails).

### F13 — CFR contradictions, `(c)` dropped (Med) · `agents/jira-manager.md`  *(introduced by me in #51)*
**Root cause (confirmed a/b; c refuted by round-1).** (a) L165 adds `cfr-needs-human` yet calls the issue
"UNLABELLED" (conflation); (b) swap-back-vs-terminal deadlock (new evidence swaps back to
`cfr-triage-pending`, but the terminal rule says `cfr-needs-human` clears *only* on a terminal outcome).
Round-1 codex: **(c) is not real** — `jira-manager.md:173-175` **already** names all three human-adjudication
outcomes (change-failure / proven pre-existing / dismissal). **Drop F13(c).**
**Fix.** (a) L165 → "leave the issue **without the counted `change-failure` label** (uncounted)"; (b) reword
the terminal rule to distinguish *re-attribution* (swap back to `cfr-triage-pending` on new evidence) from
*resolved* (cleared) — the terminal-only clear governs *resolved*, not the re-attribution swap. Keep parity
with `release-manager.md` and the canonical `AGENT_CONTRACTS §12` (see B7).
**Mutation proof (doc-lint).** Assert the CFR section does not call a `cfr-needs-human` issue "UNLABELLED"
and that re-attribution and resolved-clear are distinct. Revert → fails. (Coordinated with B7 — see below.)

### B1 — pty `--timeout=N` ignored (Low) · `scripts/pty-capture.py`
**Root cause (confirmed).** Pre-`--` parser (~L363–401) matches only exact `--timeout`; `--timeout=N` →
positional → unbounded run.
**Fix.** Add `elif tok.startswith("--timeout="):` with the same `float()` + `0 < t < inf` validation.
**Mutation proof (round-1).** No callable `parse()` exists today — **extract the inline parser into a
callable** (or drive via subprocess). Test: `--timeout=5` sets 5.0; revert → lands in positional (fails).

### B2 — verify path accepts stray reviewers (Low) · `scripts/review-verdict.py`
**Root cause (confirmed).** `_quorum_problem` checks only missing-required, never strays; `_reviewer_
identity_problem` (write only) checks strays — asymmetry.
**Fix.** Add the mirror stray check in `_quorum_problem` (shared enforcer → closes write + verify).
**Mutation proof.** `{gemini, codex, mallory}` → non-None. Revert → passes (fails).

### B4 — stale-tool rejection, not removal (Low) · `scripts/validate-plugin-assembly.py`
**Root cause (confirmed no-op in v1).** Removing `"Task"` from `KNOWN_TOOLS` (L54) does **nothing** — unknown
tools are accepted unless `difflib` finds a close match (L80–89), and `"Task"` has none.
**Fix.** Add explicit `STALE_TOOLS = {"Task"}` checked **before** the difflib pass → hard reject with a
message pointing at `AGENT_CONTRACTS §9` (`Agent`, not `Task`).
**Mutation proof.** A frontmatter `tools: [Task]` fails assembly. Revert → passes (fails).

### F9 — provider-parity gate-policy drift (Low, but a gate fix — reclassified) · agents/skills docs
**Root cause (round-1 codex).** Not mere prose. `agents/swift-reviewer.md:352,365-367` is **live gate
policy** — it still accepts a tracked `// TODO: PARITY` stub, and the L352 parenthetical ("or an
implementation in both") would accept a **throwing `ProviderParityError` stub** as "implemented", while
`skills/provider-parity/SKILL.md:185-203` now requires **declared `ServiceCapabilities`**. That is gate
drift. Stale phrasing also lingers in `skills/implement/SKILL.md:286`, `AGENT_CONTRACTS.md:66`,
`agents/code-simplifier.md:310`, `agents/jira-manager.md:109`, `skills/brainstorm/SKILL.md:79`.
**Fix.** Update the swift-reviewer parity policy to the `ServiceCapabilities`/`ProviderParityError` model
(a throwing stub is **not** "implemented"); refresh the stale references to the new convention.
**Mutation proof (doc-lint).** Assert swift-reviewer's parity section references `ServiceCapabilities`/
`ProviderParityError` and does not treat a throwing stub as an implementation. Revert → fails.

---

## 5. Below-the-cut (revised)

### B3 — reviewer-allowlist parity: re-inventory or drop
Round-1 codex: the v1 inventory was **wrong** — `sensitive-file-guard.sh`, `mcp_server.py` etc. contain
`gemini`/`codex` in **review-attribution comments**, not executable copies of `REQUIRED_REVIEWERS`; a
string-scan parity test would be noise. **Action:** re-inventory the *actual* gate consumers that
programmatically encode the reviewer set (`review-verdict.py:66` canonical; check `review-synthesis`,
`skills/implement`, `AGENT_CONTRACTS`). If `review-verdict.py` is the **sole** executable definition, **drop
B3** (no real duplication to guard). If others restate it programmatically, add a targeted parity test over
*those* sites only. Decision recorded during implementation.

### B6 — build-verify.sh double compile
`xcodebuild build` (L28) then `xcodebuild test` (L50) compiles twice. **Fix:** `build-for-testing` +
`test-without-building` (compile once), both gates preserved. **Mutation proof (round-1):** update
`scripts/tests/test_build_verify.py` to assert **both** subcommands are invoked and each failure propagates.
Revert → fails. (Plugin repo has no Xcode — script + test change only.)

### B7 — CFR protocol de-duplication (coordinated with F13)
CFR protocol is triplicated across `jira-manager.md`, `release-manager.md`, `AGENT_CONTRACTS §12` (F13 is a
symptom). Round-1 codex: a test requiring all three to restate all outcomes **conflicts** with trimming the
agent files. **Order:** (1) fix the **canonical** statement in `AGENT_CONTRACTS §12` (the corrected F13
outcomes) first; (2) trim the two agent files to **role-specific mechanics + a pointer to §12**; (3) test
**pointer integrity** (each agent file references §12) **+ canonical content** (§12 names the three
outcomes correctly) — **not** triplicate restatement. This supersedes the F13 doc-lint's "all three files"
wording.

## 6. Deferred (follow-up ticket)
- **F7** refuted (no SIGPIPE). **B5** (CI perf: full-history gitleaks, uncached install, no
  `paths-ignore`/concurrency). **B8** (`ci`/`style` + ticketless Dependabot commit types vs CLAUDE.md).

## 7. Implementation order & tests
1. **Synthesizer** (F2+F3 shared helper, then F1, B2, F8, F10, B4) — Python units in
   `mcp/review-synthesizer/tests/` + `scripts/tests/test_review_verdict.py` (**invert the F1 test**;
   **update the F2 backslash test**).
2. **capture.py** (F11) — shared secure opener + per-call-site symlink tests.
3. **Shell gates** (F4, F5, F12) — harness tests with hard time bounds + temp-constrained + session cases.
4. **Agent/doc** (F6, F13, F9, B7) — doc-lint assertions; §12 canonical first, then agent-file trims.
5. **B1** (extract parser), **B6** (build-verify + test), **B3** (re-inventory → test or drop).
6. Full suite: assembly/hooks/version-sync validators, `test-hooks.sh`, `python3 -m unittest` (mcp +
   scripts), `shellcheck -S warning`.
Every code fix mutation-proved; every **pre-existing** test that asserted old behavior is inverted/replaced.

## 8. Risks
- **F4 (one structured linear lexer)** — a single quote/escape/operator-aware O(n) lexer runs at all sizes,
  so read-only + quoted/escaped-operator commands never ask and `mv`/`cp`/redirect semantics match the tests.
  **Failure contract:** `ask` is exit-0 structured JSON (Claude Code ignores stdout JSON on exit 2, so `ask`
  can never be exit-2); a genuine parser failure is an **exit-2 denial** (stderr). Only accepted extreme: a
  **>256KB** command asks unconditionally (DoS backstop). Base64/indirection out of scope. python3 dependency
  already present (`scripts/lib/hook-io.sh`); a linear-bash lexer is the fallback if a python3-free hot path
  is later required.
- **F5 `session_id`** — present on CC 2.1.211; stable `transcript_path`-hash fallback (never a nonce);
  success-path reset must cover the session sentinel.
- **F2/F3 over-rejection** — only rare literal-backslash POSIX names; documented; positive test for normal
  paths.
- **F11** — `O_EXCL` is stronger than the twins (documented), not a parity claim.
- **B6** — unverifiable locally (no Xcode); rely on dual review + app CI.

## 9. Rollout
PR `feat/COREDEV-2503-gate-hardening` → `alpha`; dual bot review to convergence; **only then** unpark #52.
Version bump 2.5.0 → **2.5.1** (fixes); README/What's-New + CHANGELOG per `validate-version-sync`.

## 10. Round-1 review response (traceability)
**codex `REQUEST_CHANGES` — all 9 blocking items addressed:** F4 fail-closed for oversized/obfuscated/
malformed/temp-constrained inputs (§4 F4). B4 explicit `STALE_TOOLS` reject, not removal (§4 B4). F5 stable
hashed session fallback + sentinel reset + same-session tests (§4 F5). One schema-owned traversal helper
covering POSIX/UNC/drive-absolute/`..` (§4 F2+F3). F11/F12 tests corrected — all call sites / all arms, no
out-of-policy fixtures, assert-on-victim not on raise (§4 F11, F12). F13(c) dropped; F13 reconciled with B7
consolidation (§4 F13, §5 B7). B3 re-inventoried or dropped (§5 B3). F9 treated as live gate logic with a
regression assertion (§4 F9). Blanket invariant narrowed to security/correctness gates; intentional Stop-gate
fail-opens retained (§3). **Qualifications:** F1 existing test inverted; F2 backslash test updated + policy
documented; F8 bounded cap+1 read (race); F10 `fullmatch`/`\Z`; B1 parser extracted; B6 test asserts both
subcommands.
**gemini `APPROVE_WITH_NOTES`:** F5 nonce → **stable session id** (§4 F5, aligns with codex); F2/F3 helper in
`schema.py` (§4); F4 over-rejection documented as expected fail-closed behavior (§8).

**Round-2 (v3) — both `REQUEST_CHANGES`, converged to 2 items, both fixed:**
- **F4 (codex + gemini):** the de-obfuscation/substring-`ask` was wrongly gated behind the >8KB path, so a
  *small* obfuscated command (`rm Key"chain".swift`) still fell through the precise regex to exit 0. Now the
  conservative de-obfuscated substring-`ask` is the **primary check at ALL sizes**; the O(n²) precise parser
  is byte-bounded to <8KB and only refines the message (§4 F4). Residual (base64/indirection) documented.
- **F5 (codex):** the v2 mutation-proof (session-2 also blocks) would pass under a nonce too. Added the
  **same-session dedup** case — a second same-session Stop must *pass*; a nonce would re-block/wedge and fail
  it — the discriminator that pins the key as session-stable, not fresh (§4 F5).
Codex explicitly affirmed the rest sound: F1, F2/F3, F6, F8–F10, F13/B7, B1–B3, B6 "match the live control
flow"; the schema helper's import direction, quarantine → NEEDS_DISCUSSION, and F9 policy-drift are correct.

**Round-3 (v4) — gemini `APPROVE`; codex `REQUEST_CHANGES` on 3 refinements, all fixed:**
- **F4 write-context (codex #1):** v3's blanket all-sizes "any basename ⇒ ask" would have blocked read-only
  `grep`/`cat`/source-`cp` on a sensitive path, contradicting `test-hooks.sh:106`. Fixed: de-obfuscation is
  folded **inside** the write-verb parser; reads never ask; the >8KB fallback requires a write verb too
  (§4 F4, §8).
- **F4 test masking (codex #2):** the primary scan could mask the byte-cap and temp-file sub-fixes. Fixed:
  independent per-sub-fix tests, incl. a >8KB *basename-free* command to isolate the byte-cap and a
  `TMPDIR=/nonexistent` case to isolate the temp-file path (§4 F4).
- **F5 test precondition + reset (codex #3):** the same-session cases must set `stop_hook_active:false` or
  guard #1 short-circuits and a nonce also passes; and the success reset must **glob-clear all** session
  sentinels since `marker_write` has no session payload. Both fixed (§4 F5).
Gemini `APPROVE` (v3): confirmed F4 all-sizes + F5 discriminator sound, no new fail-opens — the v4 edits only
*narrow* F4 (fewer asks) and *strengthen* F5 tests, so they don't regress gemini's approval.

**Round-4 (v5) — both `REQUEST_CHANGES`, converged to the F4 >8KB fallback + one F5 test, both fixed:**
- **F4 >8KB fallback (codex + gemini):** v4 folded de-obfuscation only into the <8KB precise path, so the
  >8KB fallback scanned the raw string (obfuscated writes bypass — gemini) and was verb-only (false-asked on
  source-only `cp`, missed redirect-writes `echo … > Keychain.swift` — codex). Fixed: the >8KB fallback now
  linearly **de-obfuscates** and applies **write-context + target-awareness** (redirects `>`/`>|`, write
  verbs, `cp`/`mv` dest-not-source, F12 forms) before asking; tests for large quoted `rm`, large
  redirect-write (→ ask), and large source-only `cp` (→ no ask) (§4 F4).
- **F5 reset test (codex):** v4's reset test seeded one sentinel — insufficient to prove the *all-session*
  glob-clear. Now seeds **two** session sentinels, does the success write, asserts **both** are removed and
  both re-block (§4 F5). Gemini confirmed F5 "completely sound" at v4.

**Round-5 (v6):**
- **F4 `mv`/quoted-`>` (codex):** the v5 >8KB fallback still had two edges — it treated `mv` as dest-only
  (but `mv`/`rename` remove the *source*, so a source-side `mv Keychain.swift /tmp/x` must ask), and blind
  `tr` de-obfuscation turned a *quoted* `echo '> Keychain.swift'` into an apparent redirect (over-ask).
  Root realization: a separate simplified fallback keeps missing what the precise, quote-aware parser already
  gets right. **v6 eliminates the fallback** — the precise parser is made O(n) and used at all sizes, so
  `mv`-source, quoted-vs-active `>`, redirect-without-verb, and obfuscation are all handled by the one
  already-correct parser (§4 F4). This ends the round-over-round F4 edge discovery by construction.
- **gemini `REQUEST_CHANGES` (misframe, not actioned):** gemini reported the fixes "missing" from the *code*
  (`sensitive-file-guard.sh` lacks the cap; `stop-quality-marker-gate.sh` still session-blind). True but
  expected — this is a **pre-implementation** plan review; the code is unchanged by design. No plan defect;
  the round-6 gemini prompt states the code-unchanged framing explicitly.

**Round-6 (v7) — both `REQUEST_CHANGES`, converging on F4's parser correctness (design agreed):**
- **Quote-blindness in the *precise* parser (codex + gemini, reproduced):** v6 wrongly assumed the precise
  path is quote-aware. It isn't — quoted `echo '> Keychain.swift'` **over-asks** (`:255-260`) and
  `rm Key"chain".swift` **bypasses** (`:365-369`); `cp`/`mv` strip only surrounding quotes (`:375`). v7's
  lexer emits **de-quoted words + classified operators**, replacing those greps, so these are fixed at all
  sizes (§4 F4).
- **Whole-pipeline O(n) (codex):** replacing only `_split_segments` leaves the quadratic `cand="…"`
  accumulation; v7 makes the whole candidate path linear (§4 F4).
- **Exit-code contract (codex):** `ask` + exit-2 is impossible (Claude Code ignores stdout JSON on exit 2).
  v7: `ask` = exit-0 JSON; a genuine tokenizer failure = exit-2 denial; invalid `TMPDIR` is no longer a
  failure after temp removal (§4 F4). Matches the repo's own CLAUDE.md ("JSON is only read on exit 0").
- **gemini redeemed the R5 misframe:** with the corrected code-unchanged prompt it produced the sharpest
  design catch of the round (the quote-blindness), independently corroborated by codex. F5 affirmed sound by
  both at R6.

**Round-7 (v8) — gemini `APPROVE`; codex `REQUEST_CHANGES` on test-fixture precision only (F4 design sound
by both):**
- **F12 fixtures (codex):** `Secrets.swift` is not in the guard's sensitive set (`:23`), so the `>|` fixture
  couldn't ask without an unplanned policy expansion; and the fix list omitted the `find … -delete` arm its
  proof used. Fixed: in-policy basenames throughout (`Keychain.swift`/`Info.plist`), `find -delete` added to
  the arm list, `xargs` fixture names a sensitive input (§4 F12).
- **F4 test taxonomy (codex):** "each reverts to a wrong decision" was inaccurate — active-redirect/`mv`/
  source-`cp`/`grep` are *already correct*, so they are **preservation** regressions, not mutation-kills.
  Split the F4 proof into mutation-kills (the quote-blind cases) vs preservation regressions, and made the
  many-operands perf fixture use a candidate-producing arm (`mv`/`tee`) to exercise the downstream
  accumulation (§4 F4). No design change — F4 confirmed sound by both reviewers at R7.
