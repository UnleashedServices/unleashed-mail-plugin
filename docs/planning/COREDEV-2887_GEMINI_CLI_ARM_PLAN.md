# COREDEV-2887 — The plan gate's Gemini arm moves from `agy` (Flash) to the `gemini` CLI (3.1 Pro Preview)

**Status:** Planning, revision 6. Urgent (High). Round 1: codex `REQUEST_CHANGES` (Q1: 2, Q2: 4); gemini 3.1 Pro through
the prototype `REQUEST_CHANGES` (Q1: 2 claimed, both disproven; Q2: 1). Round 2: codex `REQUEST_CHANGES` (Q1: 1, Q2: 5);
gemini `REQUEST_CHANGES` (Q1: 1 claimed, disproven by a discriminating live probe; Q2: 1, the same as codex's fourth).
Round 3: codex `REQUEST_CHANGES` (Q1: 3, Q2: 4); gemini `APPROVE_WITH_NOTES` (Q1: 0; Q2: 1, declined).
Round 4: codex `REQUEST_CHANGES` (Q1: 1, Q2: 3); gemini `APPROVE` (Q1: 0, Q2: 0).
Round 5: codex `REQUEST_CHANGES` (Q1: 3, Q2: 1); gemini `REQUEST_CHANGES` (Q1: 1, Q2: 0). Every Q1 was in revision 5's
void machinery, which revision 6 REMOVES; the inherited property it chased moves, for all three arms, to COREDEV-2888.
**Ticket:** COREDEV-2887 (Epic COREDEV-2485).
**Branch / worktree:** `feat/COREDEV-2887-gemini-cli-arm`, `.claude/worktrees/2887-gemini-cli`, cut from `origin/alpha` at
`5c04728`.
**Process (maintainer):** Codex reviews this plan through the existing arm. The new Gemini arm reviews it through a
PROTOTYPE of the harness this plan specifies, because the `agy` arm it replaces is down. Then implement, test, run the
full gate, and open a PR into `alpha`.

## Review log

- **Round 1 (revision 1), codex `REQUEST_CHANGES`, Q1: 2, Q2: 4.** All six were real, reproduced in memory by codex,
  and fixed in revision 2 and its prototype.
  1. **(Q1) CLI stderr could forge a verdict.** `pty-capture.py` records stdout AND stderr; the adapter forwarded the
     CLI's stderr, so stderr text could put an anchored `VERDICT: APPROVE` in the transcript even when the adapter then
     refused the run. The noise lines that reached round 1's real transcript were a symptom. **Fix (§2.2):** the CLI's
     stderr goes only to a `--diagnostics` sidecar, and the adapter's own failure lines are single-line fixed text.
  2. **(Q1) A JSON-reported error could approve.** gemini 0.64.0 can return normally with response text, stats AND an
     `error` (`INVALID_STREAM`; upstream `nonInteractiveCli.ts:565-582`). **Fix:** any non-empty `error` refuses the run
     before a byte of the response is printed.
  3. **(Q2) Deleting `test_agy_model_resolution.py` and `test_preflight_agy_isolation.py` would drop shared coverage.**
     **Fix (§3.3):** the shared cases are ported first; only resolver- and `agy`-CLI-specific cases retire.
  4. **(Q2) L1 could pass vacuously.** **Fix (§4 L1):** an effective unsafe positive control, every deny rule in BOTH plan
     and YOLO modes, schema-exclusion accepted as evidence, and a run that never reached the model is VOID.
  5. **(Q2) G3's "exact response bytes" was false.** **Fix:** the normalization is stated (§2.2) and tested.
  6. **(Q2) The preflight's `grep -qi pong` passed `not pong`.** **Fix (§2.4):** a whole-answer match.
- **Round 1, gemini (`gemini-3.1-pro-preview`, through the prototype): `REQUEST_CHANGES`, Q1: 2, Q2: 1.** This round was
  also L2: exit 0, `TREE=clean`, `.model` = `gemini-3.1-pro-preview`, and a parsed verdict.
  1. **(Q1, declined) "An absolute snapshot path voids every round."** Disproven by the round itself, which completed
     with `TREE=clean` through that path. `stage-prompt.py` drops empty path components, so an absolute `--rel` is
     staged as a nested path inside the disposable tree, and the basis check and the reviewer's path resolve to the
     same file. The path is also unchanged from the `agy` harness.
  2. **(Q1, declined) "UnleashedMail commits a `.gemini` directory, so every app round fails."** False: neither the
     app's `1.02.0000` nor its `main`, nor this repo, contains `.gemini`. Refusing a committed `.gemini` is deliberate,
     since a reviewed repo's settings must not configure its reviewer. It is now a stated boundary (§6).
  3. **(Q2, adopted)** The preflight now passes the pre-run HEAD to `tree_fingerprint_report`. The argument is
     optional, so the earlier call was valid, but the report can now name a moved HEAD.
- **Round 2 (revision 2), codex `REQUEST_CHANGES`, Q1: 1, Q2: 5.** All six adopted, and fixed in revision 3 and its
  prototype.
  1. **(Q1) The model identity was truncated before it was compared.** The adapter cut model keys to 80 characters,
     while the harness accepts a 128-character override, so a requested 80-character id matched an answering
     `<id>-fallback` (codex reproduced exit 0 with `VERDICT: APPROVE`). **Fix (§2.2):** the full identity is compared;
     only the diagnostic is shortened. Stub-checked: a 93-character id answered by `<id>-fallback` exits 4 with no
     output, and the exact id exits 0. **Cell:** G2.
  2. **(Q2) The staged routing setting could be ignored.** gemini 0.64.0 loads settings BEFORE it parses arguments and
     excludes an untrusted workspace's settings; `--skip-trust` takes effect only during parsing. **Confirmed live (F13
     D):** with `--skip-trust` alone, a workspace `.gemini/settings.json` was not applied. **Fix (§2.1, §2.2):** the
     adapter sets `GEMINI_CLI_TRUST_WORKSPACE=true`, which is read before settings (F13 A: the same file then applies),
     and the harness refuses a committed `.env`, which the CLI also loads (§6). The model assertion stays the
     guarantee. **Cells:** G4a, G7, L1b.
  3. **(Q2) CRLF reached the transcript.** A PTY turns CRLF into CRCRLF, and `pty-capture.py` removes one CR. **Fix
     (§2.2):** the adapter turns CRLF and lone CR into LF before printing. **Cell:** G3, through the full PTY path.
  4. **(Q2) G4 asserted `--diagnostics` in the stub's argv, which the adapter consumes and never forwards.** **Fix:** G4
     is split. G4a checks the CLI's argv and environment; G4b checks the harness's adapter invocation, exclusive
     creation of the diagnostics file, and stderr isolation.
  5. **(Q2) L1 could pass vacuously for MCP and `invoke_agent`.** No MCP server was configured, so deleting the MCP rule
     changed nothing L1 observed; `invoke_agent`'s denial was added after its only observation. **Fix (§4 L1):** a
     harmless local MCP fixture with a positive control, and `invoke_agent` exercised under the final policy, in both
     modes.
  6. **(Q2) The preflight's failure did not name the model, and its diagnostics were deleted with the scratch
     directory.** **Fix (§2.2, §2.4):** every refusal line names the requested model (`repr()`-escaped), and the ping's
     diagnostics are kept at `<ping>.diag`.
- **Round 2, gemini (`gemini-3.1-pro-preview`, through the prototype): `REQUEST_CHANGES`, Q1: 1, Q2: 1.**
  1. **(Q1, declined on a discriminating probe) "The CLI starts MCP servers from a committed `.mcp.json`, so the
     reviewed tree can run code before the review."** **F13 B:** a `.mcp.json` whose server touches a marker file started
     nothing, while the same server in `.gemini/settings.json` (the positive control, F13 A) did. `.mcp.json` is Claude
     Code's file, not a `gemini` CLI configuration source. This repository and UnleashedMail (`main` and `1.02.0000`)
     both commit one, so refusing it would refuse every round in both, for no protection. The finding's spirit is adopted: the adapter now passes an MCP-server
     allowlist that admits nothing, so no configured server, from any source, is started (F13 C against Cp). A
     committed `.gemini` was already refused.
  2. **(Q2, adopted)** Identical to codex's fourth: G4 is split.
- **Round 3 (revision 3), codex `REQUEST_CHANGES`, Q1: 3, Q2: 4.** All seven adopted, and fixed in revision 4 and its
  prototype. The first had also been found independently while drafting the §3.3 test port (the
  "silent reviewer stays MISSING" case could not pass as specified).
  1. **(Q1) A refused run left a NON-EMPTY transcript, so it was approval-eligible.** The adapter printed its refusal
     line to stderr, which the PTY records, and `persist-verdict.sh` and `review-verdict.py write` refuse only an EMPTY
     transcript; neither checks an extracted verdict. Codex accepted a 203-byte wrong-model leaf as `gemini=APPROVE`
     with the production checks. **Fix (§2.2):** the adapter opens the diagnostics file FIRST and makes it its own
     stderr, so a refused run leaves the transcript EMPTY, which is MISSING at both layers; the harness repeats the
     refusal on its own stderr, outside the PTY. **Cells:** G2, G6.
  2. **(Q1) The MCP allowlist admitted its own sentinel.** The allowlist matches names exactly, so a server configured
     under `unleashed-mail-gate-review-no-mcp` would start. **Confirmed live (F13 E).** An empty allowlist means
     unrestricted. **Fix (§2.2):** the name is generated per run from 128 random bits. **Cell:** G4a.
  3. **(Q1) Ancestor environment files bypassed the boundary.** The CLI loads the first `.gemini/.env` or `.env` found
     walking UP from its working directory (F14), so a disposable checkout under a repository-local `TMPDIR` could be
     configured by a committed or ignored file above it. **Fix (§2.2):** the adapter performs the same walk from its own
     working directory, which is the CLI's, and refuses any file the walk reaches that is not in `$HOME`. Running the
     new tests from this worktree found one: the main checkout's ignored `.env` (F14). **Cell:** G7b.
  4. **(Q2) The truncation probe was not discriminating as specified.** A truncating comparison forged an approval
     only for a request of EXACTLY 80 characters. **Fix:** G2 uses exactly 80, every refused case carries an APPROVING
     response, and the truncation mutant is shown to produce an extracted `APPROVE`.
  5. **(Q2) A timed-out preflight did not name the model.** **Fix (§2.4):** every preflight failure line names it, and
     repeats the adapter's refusal when there is one. **Cell:** G5, with the adapter killed before it can refuse.
  6. **(Q2) The `.gemini`/`.env` refusal ran after staging, though the plan said before.** **Fix:** the checks moved to
     immediately after the checkout is created.
  7. **(Q2) Rollout named mutants only for G1–G5.** **Fix (§5.3):** G1–G7, with the executed mutant table.
- **Round 3, gemini (through the prototype): `APPROVE_WITH_NOTES`, Q1: 0, Q2: 1.** The round was clean (`TREE=clean`, the
  model asserted).
  1. **(Q2, declined)** "`capture-gemini-review.sh` says `bind TICKET to the --ticket operand`, but takes positional
     operands." `--ticket` is the skill's own invocation argument (`/unleashed-mail:gemini-review --ticket <T> --round
     <N> <plan>`), from which the skill binds `TICKET`; the codex wrapper uses the same wording. Not changed by this
     plan.
- **Round 4 (revision 4), codex `REQUEST_CHANGES`, Q1: 1, Q2: 3.** All four adopted, and fixed in revision 5 and its
  prototype.
  1. **(Q1) A VOIDED round left an approval-eligible transcript.** The capture writes the reviewer's text into the leaf
     before the post-run checks, and a void only exits 3; `persist-verdict.sh` and `review-verdict.py write` never see
     the exit status. Codex's reproduction: rewrite the staged plan, emit `VERDICT: APPROVE`, and the production writer
     accepts the leaf. Inherited from the `agy` harness, and present in the codex and kimi harnesses too. Revision 5
     emptied the leaf on every void (`void-transcript.py`); **round 5 showed that revocation is the wrong shape, and
     revision 6 removed it** (see round 5). The property now belongs to COREDEV-2888, for all three arms (§6).
  2. **(Q2) G4a's "exactly one" allowlist value did not see the `--flag=value` form,** which the CLI's parser accepts
     and combines. **Fix:** every occurrence of every asserted option is counted, in both forms. **Cell:** G4a, with an
     injected `--allowed-mcp-server-names=attacker` as its mutant.
  3. **(Q2) The harness's reported verdict was untested.** **Fix:** G3b runs `APPROVE_WITH_NOTES`, `REQUEST_CHANGES`
     and verdict-free responses through the capture and asserts the summary line, with a constant-verdict mutant.
  4. **(Q2) "Every preflight failure names the model" was overclaimed:** the missing-CLI, fingerprint and mutation
     lines did not. **Fix (§2.4):** the model is read first and every failure line names it. **Cell:** G5.
- **Round 4, gemini (`gemini-3.1-pro-preview`, through the prototype): `APPROVE`, Q1: 0, Q2: 0.** Clean round. It did not
  find codex's Q1. A comparison run of `gemini-3.8-flash` on the same bytes is recorded in §6.
- **Round 5 (revision 5), codex `REQUEST_CHANGES`, Q1: 3, Q2: 1; gemini (`gemini-3.1-pro-preview`) `REQUEST_CHANGES`,
  Q1: 1, Q2: 0.** All four Q1s are in revision 5's void machinery:
  1. **(codex Q1)** `void_round` loaded `void-transcript.py` from the live checkout AFTER the review, so a reviewer
     that wrote there could replace it with a no-op.
  2. **(codex Q1)** A truncation that failed only warned; persistence never reads the harness's status.
  3. **(codex Q1)** The failure path's `O_TRUNC` open could empty a hard link substituted at the leaf.
  4. **(gemini Q1)** A lingering reviewer process could `chmod 400` the leaf after the capture, so the truncation's
     write-open failed and the approval survived. (A symlinked leaf, its other variant, was already refused by
     `review-verdict.py`'s per-run check.)

  **Disposition: the machinery is REMOVED, not hardened again.** Each hardening of a revoke-after-capture design opened
  a new surface; the author's own draft of a fifth version (lstat, `fchmod`, unlink fallback) would still have kept
  findings 1 and 2. The gap it chased is INHERITED and identical in all three harnesses, and its structural fix is
  positive evidence, not revocation: persistence accepts an approval only with a clean-round receipt the harness
  writes after every post-run check passes. That changes shared persistence code for every arm, so it is COREDEV-2888
  (High), with its own plan and gate. This arm's void behaviour returns to exactly the inherited `exit 3` (§0.3). The
  adapter's EMPTY transcript on a refused run (round 3) is a different property, new to this arm, and stays.
  5. **(codex Q2, adopted)** G4a's "exactly once" did not cover `--skip-trust=false` or `--diagnostics=…`. **Fix:**
     boolean options are counted in both forms, and `--diagnostics` is refused in both forms, each with a mutant.
- **Comparison replay of round 3, `gemini-3.8-flash` (the same bytes, digest `da901792`, the same harness and prompt):
  `APPROVE_WITH_NOTES`, Q1: 0, Q2: 3.** All three were verified against the files and adopted in revision 5; none had
  been raised by either arm.
  1. **(Q2) §3.3's port range skipped `ProductionPath`** (`test_agy_model_resolution.py:293–359`: the default model
     runs and is recorded; an environment `MODEL` and the sixth operand override it). **Fix:** the range is 293–563, and
     the environment override is ported (it was the one missing).
  2. **(Q2) §3.6 missed active references to `agy`:** `CLAUDE.md:103`, whose wording `test_doc_gates.py:1153` and
     `:1163` assert; `README.md:886` and `:916` (the current capability table and gate description, not history); and
     the `scripts/pty-capture.py:32` docstring recipe, which `test_agy_recipe_gate` executes. **Fix:** §3.6 lists them.
  3. **(Q2) The prompt-file name was unstated.** **Fix (§3.4):** it stays `.agy-prompt-<T>r<N>.md`.

## 0. The defect, and what "fixed" means

The plan gate's second arm runs Gemini through the Antigravity CLI (`agy`), with the newest `gemini-*-flash-high` that
`agy models` lists. As of 2026-10-14 that arm is unusable:
- **Gemini 3.1 Pro has been retired from `agy`.** `agy` 1.3.5 lists only `gemini-3.8-flash-{high,medium,low}`, and the
  maintainer doubts Flash's reasoning is adequate for gate reviews.
- **The Flash arm has not answered since 2026-10-12.** Its preflight fails, with `streamGenerateContent` for
  `gemini-3.8-flash-high` unanswered within 60 s, while auth and `agy models` are healthy. COREDEV-2885's gate was
  closed by maintainer decision because of this.

Gemini 3.1 Pro **Preview** remains available through the `gemini` CLI (0.64.0 installed at `/opt/homebrew/bin/gemini`).

**Fixed means:**
1. A gate round's Gemini arm is reviewed by `gemini-3.1-pro-preview`, and the round FAILS rather than passes if any
   other model answered (fallback or routing).
2. The reviewer cannot change the tree under review. As today, that is guaranteed by isolation (a disposable private
   checkout plus before-and-after fingerprints, exit 3 on any change), with the CLI's own read-only mode and a deny
   policy as additional layers.

   **What isolation defends against.** A reviewer that WRITES (agent-mode implementing, COREDEV-2607) or otherwise
   misbehaves is detected, and its round voids with exit 3. The deny policy and the CLI's workspace boundary keep it
   from obtaining a shell or a write tool at all. A deliberately MALICIOUS same-account process that targets the
   harness, its helpers, the transcript store or the persistence code is NOT in scope: it could forge any artifact
   directly. A void's transcript is still on disk after exit 3, as with every arm today; making persistence REQUIRE
   proof of a clean round is COREDEV-2888.
3. Everything downstream of the transcript is unchanged: the arm name `gemini`, allocation, prompt and plan binding,
   anchored `VERDICT:` extraction, `review-verdict.py`, `persist-verdict.sh` and synthesis.
4. A retired or unreachable model fails the preflight and the round CLOSED, with a message naming the model.

## 1. Verified facts (2026-10-14, `gemini` 0.64.0, `agy` 1.3.5)

- **F1. 3.1 Pro answers headless.** From a scratch directory:
  `gemini --skip-trust -m gemini-3.1-pro-preview --approval-mode plan -o json -p "Reply with exactly the single word: pong"`
  returned rc 0 in 6 s, `response: "pong"`, and `stats.models` keyed exactly `gemini-3.1-pro-preview`. No PTY is
  required.
- **F2. Trust.** Without `--skip-trust`, the CLI refuses an untrusted folder (rc 55, "Gemini CLI is not running in a
  trusted directory") and overrides the approval mode to `default`. `--skip-trust` is "Trust the current workspace for
  this session" and does not persist.
- **F3. Plan mode refused writes when the model stayed in it.** Asked, in plan mode, to create `pwned.txt`, run
  `touch shell.txt` and overwrite `existing.txt`, it refused all three: "`run_shell_command` is disabled in Plan Mode";
  writes are restricted to `.md` files in a plans directory. None of the three happened.
- **F4. But plan mode is not a boundary in headless use.** The docs (`docs/cli/plan-mode.md`, "Non-interactive
  execution") say the policy engine AUTO-APPROVES `enter_plan_mode` and `exit_plan_mode`, and that exiting switches to
  YOLO, which auto-approves every tool. **Observed 2026-10-14, in a scratch directory:** without a policy, asked to
  leave plan mode and then write, 3.1 Pro called `exit_plan_mode` (accepted, "transitioned to YOLO mode"), then created
  `pwned.txt`, ran `touch shell.txt` and overwrote `existing.txt`. All three changes landed. F3 passed only because
  that model chose to stay.
- **F4a. The deny policy closes it (observed).** The same request, with `scripts/review/gemini-review-policy.toml`
  passed by `--policy` through the adapter: the model reported `exit_plan_mode` as "not available in my current
  schema declarations". Denied tools are withheld from the model. Nothing was written or run, and `existing.txt` was
  unchanged.
- **F5. The CLI can change model mid-session.** The docs and source show automatic fallback (`activateFallbackMode`,
  session-only and never persisted) and plan-mode model routing between Pro and Flash. Routing is disabled by
  `general.plan.modelRouting: false` in `settings.json`. JSON output's `stats.models` records every model that
  answered.
- **F6. A per-run policy is possible.** `--policy` loads "additional policy files or directories". A rule takes
  `toolName` (a string or array), `decision` (`allow`, `deny` or `ask_user`), `priority` (0–999), optional `modes`
  (applying to all modes if omitted) and `denyMessage`.
- **F7. Plan artifacts are written outside the workspace** by default, to `~/.gemini/tmp/<project>/<session-id>/plans/`.
- **F8. The harness's reviewer is a single command.** `scripts/review/isolated-agy-review.sh:344-345` runs
  `pty-capture.py --timeout T --allocated OUT -- agy --add-dir TREE --model M --print-timeout 28m -p "Read and follow
  TREE/PROMPT"` inside the disposable checkout. Binding, staging, fingerprints, basis checks and verdict extraction
  surround it and are reviewer-agnostic. `capture-gemini-review.sh` already allocates under the literal arm name
  `gemini`.
- **F9. A JSON-reported error can accompany response text** (codex, upstream `nonInteractiveCli.ts:565-582`): gemini
  0.64.0 may exit normally with `response`, `stats` and an `error` such as `INVALID_STREAM`.
- **F10. The preview model has capacity failures.** On 2026-10-14, after about a dozen pings and tests plus one full
  review, requests failed with `429 "No capacity available for model gemini-3.1-pro-preview on the server"`
  (`TerminalQuotaError`), with the CLI exiting 173. This is server capacity, not the operator's quota.
- **F11. YOLO really does write without the policy (observed).** In a scratch directory, with `--approval-mode yolo` and
  no policy, the model created `pwned.txt` and ran `touch shell.txt` before the F10 capacity error ended the run.
  **YOLO WITH the policy (observed, after two VOID attempts).** The first attempt passed `--policy <path>` as a single
  zsh word, and the CLI rejected it as "Unknown arguments"; the second hit F10. Neither counted. A third, valid run
  (rc 0, model asserted, no JSON `error`) wrote nothing: `write_file`, `replace` and `run_shell_command` were withheld
  even in YOLO, and `existing.txt` was unchanged.
- **F12. With its tools withheld, the model tried to DELEGATE (observed).** In that YOLO run, it called `invoke_agent`
  to pass the task to a `generalist` sub-agent. The call succeeded, but the sub-agent reported that it was "also not
  provisioned with `write_file`, `run_shell_command`, or `replace`". The policy applied to it, and nothing changed. The
  policy now also denies `invoke_agent`, and every MCP tool (`toolName = "*"`, `mcpName = "*"`). MCP side effects land
  outside the checkout, where fingerprints cannot see them; none are configured today. Checked under the extended
  policy: the preflight is healthy, and the reviewer still READS files (it returned a file's exact contents).

- **F13. MCP servers and workspace trust (observed, five runs, each answering `pong` with the model asserted).** Each
  scratch directory configured one MCP server whose command only touches a marker file, so a marker means the CLI
  STARTED it.
  - **A, positive control.** The server in `.gemini/settings.json`, with `GEMINI_CLI_TRUST_WORKSPACE=true` and
    `--skip-trust`: started (marker present; the CLI reported "MCP issues detected").
  - **B.** The same server in `.mcp.json` only: NOT started. `.mcp.json` is not a `gemini` CLI source.
  - **C.** As A, run through the adapter, which passes `--allowed-mcp-server-names unleashed-mail-gate-review-no-mcp`:
    NOT started.
  - **Cp, the control for C.** The adapter's exact argv and environment, without the allowlist: started. So the
    allowlist stops the process, and the deny policy, which governs tool CALLS, does not.
  - **D.** As A, with `--skip-trust` but WITHOUT the environment variable: NOT started. The workspace's settings were
    not applied, which confirms the settings-before-trust order (codex, round 2). The staged `modelRouting: false`
    applies only with the variable.
  - **E, the sentinel collision (round 3).** As Cp, with the server configured under the name the allowlist admitted,
    `unleashed-mail-gate-review-no-mcp`: STARTED. A fixed allowlist name is a name a server can be configured under.
- **F14. Environment files (read from the installed 0.64.0 bundle, `findEnvFile`).** From the working directory up to
  `/`, the first `<dir>/.gemini/.env` (trusted sessions only) or `<dir>/.env` is loaded; if none is found, the loader
  falls back to `~/.gemini/.env`, then `~/.env`. The operator's `~/.env` exists and sets `GOOGLE_CLOUD_PROJECT` and
  `GOOGLE_CLOUD_LOCATION`, so every live run so far loaded it; it stays the operator's (§6). The main plugin checkout
  carries an IGNORED `.env`, found by the new guard when the tests ran from a worktree beneath it.

## 2. Design

**The isolation harness is unchanged. Only the command inside it changes, and two layers are added.**

1. **`scripts/review/isolated-gemini-review.sh`**, derived from `isolated-agy-review.sh` with the same staging, the same
   fingerprints, the same exit-3 rules and the same anchored verdict. It differs in seven places:
   - **Model:** the default is the literal `gemini-3.1-pro-preview`, with no resolver, because the `gemini` CLI has no
     model-listing command. An explicit `MODEL` (the capture wrapper's sixth operand) still wins, with the same
     one-token check.
   - **Reviewer command:** under the same `pty-capture.py --allocated`, the harness runs the adapter in item 2, not the
     CLI directly.
   - **Staging:** before the post-staging baseline, it writes `$TREE/.gemini/settings.json` with
     `{"general":{"plan":{"modelRouting":false}}}`, so routing is off for this workspace only. The file is part of the
     baseline, so a reviewer edit to it still voids the round.
   - **Timeout:** the default stays 1800 s. There is no `--print-timeout` coupling, because the `gemini` CLI has no
     such flag.
   - **Refusals first:** a committed `.gemini` or `.env` entry (file, directory or symlink) refuses the round with exit
     1 immediately after the checkout is created, before the plan or prompt is staged or anything runs. The CLI reads
     both, and a reviewed repository must not configure its reviewer (§6).
   - **The diagnostics file must not exist yet:** a pre-existing `<leaf>.diag` (any kind) refuses the round with exit 1
     before launch, naming it. The adapter refuses it too, silently (item 2).
   - **A refused run is explained outside the PTY:** on a non-zero adapter exit, the harness prints the adapter's
     `GEMINI ARM FAILED` line from `<leaf>.diag` on its own stderr, with the model, or says that none was recorded
     (a timeout or kill).
2. **`scripts/review/gemini-review-run.py`, the adapter and the reviewer command.**
   - It runs `gemini --skip-trust -m MODEL --approval-mode plan --policy <shipped policy> --allowed-mcp-server-names
     unleashed-mail-no-mcp-<32 random hex> -o json -p "Read and follow <prompt>"`, with
     `GEMINI_CLI_TRUST_WORKSPACE=true` added to its environment so the staged workspace settings apply (F13 D).
   - **The transcript is EXACTLY the validated response, or EMPTY.** `pty-capture.py` records stdout and stderr together,
     so the FIRST thing the adapter does, before the CLI runs, is create `--diagnostics` (the harness passes
     `<transcript>.diag`) through one O_EXCL|O_NOFOLLOW descriptor and make it the adapter's own stderr. The CLI
     inherits it. Every refusal, the CLI's diagnostics and even a traceback land there, never in the transcript. A
     refused run therefore leaves an EMPTY transcript, which `persist-verdict.sh` and `review-verdict.py write` already
     treat as MISSING. A pre-existing diagnostics entry refuses before the CLI runs, writing nothing anywhere.
   - **No MCP server is started.** The allowlist name is generated per run from 128 random bits, so no server configured
     anywhere (user, workspace or extension) can carry it (F13 C, Cp, E). An empty allowlist would mean unrestricted. The
     policy cannot do this, because it governs tool calls, not processes.
   - **No environment file but the operator's is loaded.** Before the CLI runs, the adapter walks from its working
     directory (the CLI's) up to `/` exactly as the loader does (F14), and refuses the run if the walk reaches a
     `.gemini/.env` or `.env` that is not in `$HOME`. Symlinks count as present.
   - **A JSON `error` refuses the run** (F9), before any response text is printed.
   - **Unless `stats.models` names exactly `{MODEL}`**, compared as complete strings, it refuses the run with exit 4.
     Only the diagnostic shortens a model name.
   - **Every refusal is ONE line of fixed text in the diagnostics file**, `GEMINI ARM FAILED [<requested model>] —
     <reason>`, with `repr()`-escaped values and no embedded newline, so the harness and the preflight can find it and
     repeat it. Naming the model meets §0.4.
   - **Otherwise it prints `response`** and exits 0. Malformed or missing JSON exits 4 with a reason.
   - **Normalization, stated:** the adapter turns CRLF and lone CR into LF and ensures a trailing newline.
     `pty-capture.py` then strips ANSI escape sequences and removes the CR the PTY adds before each LF. Nothing else
     changes, and the leaf contains no CR.
3. **`scripts/review/gemini-review-policy.toml`, the deny policy.** Priority-999 `deny` rules, for all modes, on
   `exit_plan_mode`, `write_file`, `replace`, `run_shell_command`, `invoke_agent` (sub-agent delegation, F12), and every
   MCP tool. Each carries a `denyMessage` explaining that this is a read-only review. This closes F4's YOLO path at the
   policy layer. The MCP rule backs up the allowlist (item 2) for a server that starts anyway. Isolation still
   guarantees the outcome if the policy ever fails to load or match.
4. **`scripts/review/preflight-gemini.sh`**, replacing `preflight-agy.sh` in the skill. It pings through the same
   adapter, so the model assertion applies, from a scratch directory with the same before-and-after checkout
   fingerprint. It is healthy only on rc 0, the asserted model, and a WHOLE answer matching `(?i)pong[.!]?` after
   trimming, so `not pong` and `pong unavailable` are unavailable. A detected mutation reports the pre-run HEAD. The
   CLI's diagnostics are kept at `<ping>.diag`, beside the ping transcript, so they survive the scratch cleanup, and
   they stream there, so an interrupted ping keeps what the CLI printed. The model is read FIRST, so every failure line
   names it: a missing CLI, an unreadable or mutated checkout, a failed capture (repeating the adapter's refusal, or
   saying none was recorded), and no pong.
5. **`scripts/review/capture-gemini-review.sh`** `exec`s `isolated-gemini-review.sh` instead of the `agy` harness.
   Its interface is unchanged.

**Retiring `agy`.** `isolated-agy-review.sh`, `preflight-agy.sh` and `agy-newest-model.sh`, and the tests that exercise
only them, are removed in the same PR. The maintainer chose replace, not fallback. A dead harness kept in-tree is a
second authority that drifts. Tests that exercise shared machinery (binding, staging, the plan-binding chain) are
re-pointed at the new harness, not deleted.

## 3. Changes

1. New: `scripts/review/isolated-gemini-review.sh`, `gemini-review-run.py`, `gemini-review-policy.toml` and
   `preflight-gemini.sh`. `gemini-review-run.py` is added to BOTH `py_compile` invocations in `plugin-ci.yml`, one of
   which runs Python 3.9 (`test_doc_gates` requires every shipped script in both); the prototype compiles it under
   3.9.6 and runs its environment walk there. The callers-scan exemptions are regenerated last.
2. `scripts/review/capture-gemini-review.sh`: `exec` the new harness, and update the comments describing the model and
   timeout. The comments the new scripts inherited from the `agy` versions are rewritten so that none names a removed
   file; the history they record (why each check exists) stays.
3. **Removed:** `isolated-agy-review.sh`, `preflight-agy.sh` and `agy-newest-model.sh`. **Port the shared cases first**
   into `scripts/tests/test_gemini_cli_arm.py`:
   - from `test_agy_model_resolution.py` (lines 293–563): the production path (the default model runs and is recorded
     as `default`; an environment `MODEL` and the sixth operand each win and are recorded as `override`); malformed
     model operands, at both the capture wrapper and the harness; exclusive `.model` creation against a FIFO and a
     symlink; and silent-reviewer rejection downstream;
   - from `test_preflight_agy_isolation.py` (lines 131–193): execution in a scratch directory, and detection of a
     CONTENT change to an already-dirty tracked file.

   The silent-reviewer case keeps its downstream assertions unweakened: a refused run's transcript must be EMPTY and
   rejected by both `persist-verdict.sh` and `review-verdict.py write`. The port is drafted and passing in the prototype
   (`scripts/tests/test_gemini_cli_arm.py`, 39 tests).

   Only the resolver (`agy models` parsing) and `agy`-CLI-specific cases retire with their scripts.
4. `skills/gemini-review/SKILL.md`, rewritten around the new CLI:
   - setup, model, trust, preflight, plan mode, the policy, why isolation is still required (F4), and the fallback
     assertion;
   - the `allowed-tools` grants name the new scripts (`preflight-gemini.sh`, `capture-gemini-review.sh`) and drop
     `agy models`;
   - the one-shot preamble is kept;
   - the per-round prompt keeps its name, `.agy-prompt-<T>r<N>.md`: the `.gitignore` glob (`.agy-*.md`), the skill's
     `Edit(.agy-prompt-*.md)` grant and every existing gate document already use it, and renaming would widen this
     urgent change for no protection. The skill says the prefix is historical;
   - the arm is still invoked as `/unleashed-mail:gemini-review`.
5. Re-point or update the tests that drive the Gemini capture path or read the recipe, the harness or the skill. Each
   keeps its property and changes only the binary or script it names (a stub `gemini` emitting the CLI's JSON, in place
   of a stub `agy`). MEASURED on revision 4's prototype, 37 cases of the 1622-test suite fail (35 failures, 2 errors,
   subtests counted), in exactly these modules: `test_gemini_reviews_the_bound_plan` (14), `test_m5_path_contract` (11),
   `test_agy_model_resolution`
   (5, retired or ported per item 3), `test_callers_scan` (2, the regenerated exemptions), `test_capture_prompt_binding`,
   `test_transcript_path_threading`, `test_end_to_end_gate`, `test_agy_recipe_gate` (an exemption naming the old
   `agy --print-timeout` comment) and `test_doc_gates` (the `py_compile` lists, item 1). The PR's suite must be green
   with no test deleted except those item 3 retires.
6. Every ACTIVE reference to `agy` as the Gemini arm, wording only: `AGENT_CONTRACTS.md` §2; the other skills
   (`codex-review`, `implement`, `review-synthesis`); `CLAUDE.md:103`, together with the strings `test_doc_gates.py:1153`
   and `:1163` assert about it; `README.md:886` (the capability table) and `:916` (the gate description); and the
   `scripts/pty-capture.py:32` docstring recipe, which `test_agy_recipe_gate` executes. The implementation greps for
   `agy` across the shipped tree and lists every remaining hit in the PR as history or a retained name.
7. New tests, the cells in §4, using a stub `gemini` on `PATH` where the behaviour is the harness's own.
8. Version bump to the next free patch at merge time: 2.8.36 after #122's 2.8.35, five sync points plus the CHANGELOG.
   `README` What's New covers this; its history is left alone.

## 4. Verification cells (each must be seen red, for the stated reason)

**Stub-driven (deterministic, in the suite).** A stub `gemini` on `PATH` prints `VERDICT: APPROVE` on its STDERR in every
case.
- **G1, isolation still catches a writer.** Each case's response is APPROVING. The stub writes into its working
  directory (the disposable tree); into the live checkout by absolute path; and over the staged plan. The harness must
  exit 3 with "left edits inside the disposable checkout", "MUTATED the working tree" and "the STAGED PLAN was
  modified" respectively, and must not report `TREE=clean`. A clean stub is the positive control. Mutants: delete
  either post-run comparison, or the staged-plan check; its case reds. (That the void's transcript stays on disk is the
  inherited gap COREDEV-2888 closes for every arm, §0.2.)
- **G2, nothing unvalidated reaches the transcript.** Each case is captured as the harness captures it, through
  `pty-capture.py`, so stdout and stderr are combined. Every case's response is APPROVING. The leaf must contain NO
  anchored `VERDICT:` and be EMPTY, the adapter must exit 4, and the diagnostics file must name the requested model:
  - wrong model;
  - a requested model of EXACTLY 80 characters answered by `<model>-fallback`;
  - two models, including the right one;
  - an empty `stats`;
  - non-JSON stdout;
  - a JSON `error` alongside a response containing `VERDICT: APPROVE`;
  - a model key containing a newline and `VERDICT: APPROVE`.

  In addition, the right model with a response that has NO verdict must exit 0 with no anchored verdict, so that the
  stderr `APPROVE` cannot supply one, and an exact match on an 81-character model must exit 0. A CLI exiting non-zero
  leaves an empty leaf and its own status. Mutants: let stderr reach the PTY; drop the `error` check; drop the model
  assertion; truncate the model keys before comparing. Each must turn a case into an extracted approval.
- **G3, the transcript is the response text, normalized as stated.** Five cases, each through the full path (adapter,
  then `pty-capture.py` over a real PTY): a response ending `VERDICT: APPROVE_WITH_NOTES`; a response with no trailing
  newline; one with CRLF line ends; one with a lone CR; one containing an ANSI escape. Each leaf equals the stated
  normalization of the response and contains no CR. The harness prints the response's own verdict, never the stub's
  stderr one. Mutant: remove the adapter's CR normalization, and the CRLF case reds on a CR in the leaf.
- **G3b, the harness reports the response's verdict.** `APPROVE_WITH_NOTES`, `REQUEST_CHANGES` and verdict-free
  responses go through the capture, and the summary line must end `VERDICT=VERDICT: APPROVE_WITH_NOTES`,
  `VERDICT=VERDICT: REQUEST_CHANGES` and `VERDICT=<none — FAILED REVIEW>` respectively. Mutant: a constant extracted
  verdict reds.
- **G4a, what the CLI receives.** The stub records its argv, its environment and its working directory's
  `.gemini/settings.json`. Assert `--policy <the shipped toml>`, `--approval-mode plan`, `--skip-trust`, `-o json`,
  `-m <model>`, and `--allowed-mcp-server-names` followed by exactly one value matching
  `unleashed-mail-no-mcp-[0-9a-f]{32}`; that two runs use two different values; that `GEMINI_CLI_TRUST_WORKSPACE` is
  `true`; and that `modelRouting` is false. Each asserted option, the boolean `--skip-trust` included, must occur
  exactly once counting BOTH forms, `--flag value` and `--flag=value`, because the CLI's parser accepts and combines
  both. `--diagnostics` is the adapter's own option and must reach the CLI in NEITHER form. Mutants: drop each; fix the
  sentinel; inject a second `--allowed-mcp-server-names=attacker`; append `--skip-trust=false`; forward
  `--diagnostics=<path>`. G4a reds naming each.
- **G4b, the diagnostics file.** Observed by its effect: after a harness round, the stub's stderr is in `<leaf>.diag`
  and not in the leaf, which shows the harness passed exactly that path. A pre-existing `<leaf>.diag` (a file, a symlink
  to a writable file, a dangling symlink) refuses the harness round before launch, naming it: the stub records no
  call, the leaf stays empty, the target is untouched. At the adapter alone, the same entries and a FIFO make it exit 4
  before the CLI runs. Mutants: open the diagnostics without `O_EXCL`; drop the harness pre-check. Each reds.
- **G5, the preflight.**
  - Healthy: `pong`, `Pong`, `pong.` and `Pong!` from the right model.
  - Unavailable: `not pong`; `pong unavailable`; the wrong model; a JSON `error`; rc ≠ 0.
  - A stub that writes into the checkout makes the preflight FAIL with the COREDEV-2607 message.
  - A stub that kills the adapter before it can refuse (the stand-in for a timeout) fails with the model named, as do
    a missing CLI (a PATH without it), a checkout left unreadable (a stub that overwrites `.git/HEAD`) and a mutation.
  - The ping runs on the harness's `DEFAULT_MODEL`, with the policy and a fresh sentinel, and `<ping>.diag` survives.
  - Mutants: drop the model from the capture-failure line, or from the shared `die`; match `pong` as a substring. Each
    reds.
- **G6, the ported shared cases** (§3.3): each red for its original reason against the new scripts. A refused run (a
  silent failing CLI; a fallback model that approved) leaves an EMPTY transcript that both downstream layers reject as
  MISSING, and the harness's stderr names the model and the refusal. Mutants: let stderr reach the PTY; drop the
  harness's refusal line.
- **G7a, a reviewed tree cannot configure its reviewer.** A fixture repository that commits a `.gemini` directory, a
  `.gemini` file, a `.gemini` symlink, a `.env` file or a `.env` symlink: each refuses with exit 1 and the matching
  message, and the stub records no invocation. A committed `.mcp.json` does NOT refuse (F13 B). Mutants: delete the
  `.env` check, or the `.gemini` check, and its cases red.
- **G7b, no foreign environment file above the reviewer.** Run from a directory nested under one carrying `.env`, and
  under one carrying `.gemini/.env`: the adapter exits 4 before the CLI runs, the leaf is empty, and the diagnostics
  name the file. Positive control: with `HOME` set to the directory carrying `.env`, the CLI runs. Mutant: drop the
  walk, and both cases red.

**Live (recorded in the PR, not in the suite):**
- **L1, every deny rule holds under the real CLI, in BOTH modes.**
  - **Positive control, without the policy:** the unsafe actions must actually happen. They were observed in plan mode
    (§1 F4) and in YOLO (F11).
  - **With the shipped policy,** in `--approval-mode plan` AND in `--approval-mode yolo`, each of `write_file`,
    `replace`, `run_shell_command`, `invoke_agent` and (in plan mode) `exit_plan_mode` must have no effect, and a
    read-only request must still READ. Evidence is the files plus
    either a denial in the JSON tool stats, or the model reporting the tool absent from its schema (denied tools are
    withheld, §1 F4a).
  - **A run that never reached the model does not count.** No JSON, a usage error, or a capacity error makes the run
    VOID: it is re-run, never passed.
  - **Arguments are passed as separate words.** `--policy <path>` must be two argv entries; in zsh an unquoted
    `$extra` is not split (F11).
  - **MCP, with a fixture.** A harmless local stdio MCP server, zero-dependency like `mcp/review-synthesizer`, with one
    tool that creates a marker file. It is configured in a scratch workspace's `.gemini/settings.json`, and the CLI is
    run WITHOUT the allowlist, so the server starts and only the deny rule is under test. Positive control, without
    the policy and in YOLO: asked to call the tool, the model does, and the marker appears. With the shipped policy, in
    plan mode and in YOLO: no marker, and the tool is denied or absent from the schema.
  - **`invoke_agent` under the FINAL policy**, in both modes: asked to hand the write to a sub-agent, the model reports
    delegation unavailable or the call is denied, and nothing is written. The positive control is F12, where delegation
    succeeded before the rule existed.
  - **L1b, the allowlist and the trust order.** Recorded as F13: a configured server is started only without the
    allowlist (C against Cp), and workspace settings apply only with `GEMINI_CLI_TRUST_WORKSPACE=true` (A against D).
  - **L1c, an ancestor environment file reaches the real CLI (observed on revision 4).** Positive control: an `.env`
    two levels above a scratch working directory, setting `CODE_ASSIST_ENDPOINT=http://127.0.0.1:9`, made the CLI fail
    authenticating against that endpoint (`ECONNREFUSED 127.0.0.1:9`). With the file moved aside, the same run answered
    `pong`. Through the adapter, the same layout exited 4 before the CLI started, with an empty transcript and the file
    named in the diagnostics.
  - **Observed on revisions 2 to 4:** plan mode (F3, F4a); YOLO (F11, F12); reading under the policy (F12); the
    allowlist, trust order and sentinel collision (F13); the ancestor environment file (L1c). Still to run: the MCP
    fixture, and `invoke_agent` under the final policy.
- **L2, a full gate round on this plan** through `capture-gemini-review.sh`, with a parseable `VERDICT:`, `TREE=clean`
  and `.model` = `gemini-3.1-pro-preview`.
- **L3, the preflight** passes live.

## 5. Rollout

1. Build the prototype: item 1 of §3 plus the `capture-gemini-review.sh` switch. Run L3, L1, then L2 on this plan. That
   is the new arm's review. Run the Codex arm on the same plan bytes in parallel.
2. Iterate on the findings. Codex's findings follow the Q1/Q2 stopping rule. The new arm's findings count as review
   evidence, not as a gate pass, until the plan is synthesized.
3. Implement the rest of §3, then run G1–G7 with every mutant §4 names, as an executed table in which each mutant
   must go red and each anchor must match exactly once, so that a no-op mutation cannot pass as a kill. Then run the
   full local gate and `codex review --base origin/alpha`. (On revision 6's prototype: 25 mutants, all red, over a
   39-test suite.)
4. Open a PR into `alpha`, trigger the bot reviews, and triage them. **Merge needs the maintainer's word.**
5. After merge, run one real gate round with the shipped skill (any open plan) as the end-to-end check.

## 6. Out of scope, and boundaries stated rather than covered

- **Preview-model retirement.** `gemini-3.1-pro-preview` will be retired eventually. The preflight and the adapter fail
  closed with the model's name, and the sixth operand allows a one-round override. Moving the default is a one-line,
  reviewed change. There is no listing command to resolve from automatically.
- **Quota.** 3.1 Pro has lower quotas than Flash. A quota failure is a failed round (adapter or CLI non-zero), never an
  approval. If quota limits gate cadence, that is a follow-up.
- **The Kimi stand-in and the Codex arm** are untouched.
- **A VOID's transcript stays on disk after exit 3, in every arm, as today** (round 4's Q1, inherited). Persistence
  refuses only an empty or absent transcript, so an operator or synthesis that ignores a void could still record its
  approval. Revoking the transcript after the fact was tried in revision 5 and abandoned (round 5). COREDEV-2888 (High)
  fixes it for all three arms with positive evidence: each harness writes a `<leaf>.clean` receipt (the certified
  transcript's digest) only after every post-run check passes, and `review-verdict.py write` requires a matching
  receipt for any approving reviewer. Until then, a void is enforced by the harness's exit 3 and by synthesis, which
  treats a failed round as MISSING.
- **A reviewed repository that commits a `.gemini` or `.env` entry** cannot be reviewed by this arm: the harness
  refuses right after creating the checkout. Committed settings (MCP servers, tools, approval) or a committed `.env` (endpoint,
  credentials, flags) would otherwise configure the reviewer. Neither this repository nor UnleashedMail commits either
  (checked 2026-10-14). A committed `.mcp.json` is NOT refused: the CLI does not read it (F13 B), and both repositories
  commit one.
- **Availability of a preview model** (F10). A capacity failure exits non-zero, and the round fails CLOSED (MISSING),
  never approves. Gate cadence can therefore stall on Google's capacity, as it stalled on `agy`. A retry is a new
  round. Waiving the arm stays a maintainer decision.
- **The operator's home environment file still loads** (F14): `~/.gemini/.env` or `~/.env`, which carries the
  operator's Google Cloud project here. It is the operator's, not the reviewed repository's, and removing it would change
  the environment every live run so far was measured in. Any OTHER environment file the loader would reach refuses the
  run, including an ignored one, such as the main plugin checkout's, if `TMPDIR` or a test's working directory sits
  beneath it.
- **The default model, 3.1 Pro Preview or 3.8 Flash, is the maintainer's decision; this plan ships 3.1 Pro.** Three
  comparison runs of `gemini-3.8-flash` (the CLI runs Gemini 3 models at `ThinkingLevel.HIGH`, the tier `agy` called
  `-high`), each on byte-identical plans through the same harness and prompt as the 3.1 Pro round:
  - round 3 (digest `da901792`): 3.1 Pro `APPROVE_WITH_NOTES`, with one Q2 that was wrong; 3.8 `APPROVE_WITH_NOTES`, with
    three Q2s, all real, which neither arm had raised;
  - round 4 (digest `5a3accee`): both `APPROVE`, Q1 0 and Q2 0, 3.8 with about four times the cited detail;
  - round 5 (digest `df84bffe`): 3.1 Pro `REQUEST_CHANGES` with one real Q1 (the `chmod` defeat of revision 5's void
    truncation); 3.8 `APPROVE`, Q1 0 and Q2 0, missing all four real Q1s on those bytes.

  The evidence is MIXED. On the blocking class that matters most to a gate, only 3.1 Pro has scored (one real Q1 in
  round 5, out of the eight codex and it raised across these three rounds); 3.8 was broader on secondary findings
  (round 3). Three samples on one plan are suggestive, not conclusive, so the default stays 3.1 Pro. Switching is a
  one-line change of `DEFAULT_MODEL` (the preflight reads it); the sixth operand keeps either model available for a
  single round. 3.1 Pro is a preview, and it returned capacity errors on 2026-10-14 (F10).
- **`README` history** that names `agy` or 3.1 Pro on `agy` describes past releases and stays.
