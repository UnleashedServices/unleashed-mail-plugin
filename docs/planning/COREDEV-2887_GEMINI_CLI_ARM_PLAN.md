# COREDEV-2887 — The plan gate's Gemini arm moves from `agy` (Flash) to the `gemini` CLI (3.1 Pro Preview)

**Status:** Planning, revision 1. Urgent (High).
**Ticket:** COREDEV-2887 (Epic COREDEV-2485).
**Branch / worktree:** `feat/COREDEV-2887-gemini-cli-arm`, `.claude/worktrees/2887-gemini-cli`, cut from `origin/alpha` at
`5c04728`.
**Process (maintainer):** Codex reviews this plan through the existing arm. The new Gemini arm reviews it through a
PROTOTYPE of the harness this plan specifies, because the `agy` arm it replaces is down. Then implement, test, run the
full gate, and open a PR into `alpha`.

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

## 2. Design

**The isolation harness is unchanged. Only the command inside it changes, and two layers are added.**

1. **`scripts/review/isolated-gemini-review.sh`**, derived from `isolated-agy-review.sh` with the same staging, the same
   fingerprints, the same exit-3 rules and the same anchored verdict. It differs in four places:
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
2. **`scripts/review/gemini-review-run.py`, the adapter and the reviewer command.**
   - It runs `gemini --skip-trust -m MODEL --approval-mode plan --policy <shipped policy> -o json -p "Read and follow
     <prompt>"`.
   - It parses the JSON. Unless `stats.models` names exactly `{MODEL}`, it prints `GEMINI ARM FAILED — answered by
     <models>, not <MODEL>` and exits 4.
   - Otherwise it prints `response` verbatim to stdout, which is the transcript, and exits with the CLI's status.
   - Malformed or missing JSON exits 4 with a reason, never a traceback.
   - The transcript therefore stays the reviewer's text, so the anchored `^VERDICT:` extraction works unchanged.
3. **`scripts/review/gemini-review-policy.toml`, the deny policy.** Priority-999 `deny` rules, for all modes, on
   `exit_plan_mode`, `write_file`, `replace` and `run_shell_command`. Each carries a `denyMessage` explaining that this
   is a read-only review. This closes F4's YOLO path at the policy layer. Isolation still guarantees the outcome if the
   policy ever fails to load or match.
4. **`scripts/review/preflight-gemini.sh`**, replacing `preflight-agy.sh` in the skill. It pings through the same
   adapter, so the model assertion applies, from a scratch directory with the same before-and-after checkout
   fingerprint. It is healthy only on rc 0, `pong` (case-insensitive) and the asserted model.
5. **`scripts/review/capture-gemini-review.sh`** `exec`s `isolated-gemini-review.sh` instead of the `agy` harness.
   Its interface is unchanged.

**Retiring `agy`.** `isolated-agy-review.sh`, `preflight-agy.sh` and `agy-newest-model.sh`, and the tests that exercise
only them, are removed in the same PR. The maintainer chose replace, not fallback. A dead harness kept in-tree is a
second authority that drifts. Tests that exercise shared machinery (binding, staging, the plan-binding chain) are
re-pointed at the new harness, not deleted.

## 3. Changes

1. New: `scripts/review/isolated-gemini-review.sh`, `gemini-review-run.py`, `gemini-review-policy.toml` and
   `preflight-gemini.sh`.
2. `scripts/review/capture-gemini-review.sh`: `exec` the new harness, and update the comments describing the model and
   timeout.
3. Removed: `isolated-agy-review.sh`, `preflight-agy.sh`, `agy-newest-model.sh`, and the tests that exist only for
   them (`test_agy_model_resolution.py`, `test_preflight_agy_isolation.py`).
4. `skills/gemini-review/SKILL.md`, rewritten around the new CLI:
   - setup, model, trust, preflight, plan mode, the policy, why isolation is still required (F4), and the fallback
     assertion;
   - the `allowed-tools` grants name the new scripts (`preflight-gemini.sh`, `capture-gemini-review.sh`) and drop
     `agy models`;
   - the one-shot preamble is kept;
   - the arm is still invoked as `/unleashed-mail:gemini-review`.
5. Re-point or update the tests that read the recipe, the harness or the skill (`test_agy_recipe_gate.py`,
   `test_doc_gates.py`, `test_gemini_reviews_the_bound_plan.py`, `test_transcript_path_*`, `test_end_to_end_gate.py`
   and others). Each keeps its property and changes only the binary or script it names. The full list is in the PR.
6. `AGENT_CONTRACTS.md` §2 and the other skills that name `agy` as the Gemini arm (`codex-review`, `implement`,
   `review-synthesis`): wording only.
7. New tests, the cells in §4, using a stub `gemini` on `PATH` where the behaviour is the harness's own.
8. Version bump to the next free patch at merge time: 2.8.36 after #122's 2.8.35, five sync points plus the CHANGELOG.
   `README` What's New covers this; its history is left alone.

## 4. Verification cells (each must be seen red, for the stated reason)

**Stub-driven (deterministic, in the suite):**
- **G1, isolation still catches a writer.** A stub `gemini` that writes a file into its working directory and prints a
  valid approving JSON response. The harness must exit 3, "left edits inside the disposable checkout". Mutant: delete the
  post-run fingerprint comparison, and G1 goes green. That proves the stub reaches it.
- **G2, the fallback assertion.** A stub whose JSON `stats.models` names `gemini-2.5-flash`, with a response containing
  `VERDICT: APPROVE`. The adapter must exit 4, the transcript must carry no anchored `VERDICT:`, and the harness must
  exit non-zero. Variants: two models including the right one; an empty `stats`; a non-JSON stdout. Mutant: drop the
  assertion, and G2 approves.
- **G3, the transcript is the response text.** A stub with the right model and a multi-line response ending
  `VERDICT: APPROVE_WITH_NOTES`. The harness prints `VERDICT=VERDICT: APPROVE_WITH_NOTES`, and the leaf holds exactly
  the response bytes.
- **G4, the policy and settings are staged and passed.** The stub records its argv and its working directory's
  `.gemini/settings.json`. Assert `--policy <the shipped toml>`, `--approval-mode plan`, `--skip-trust`, `-o json` and
  `-m <model>`, and that `modelRouting` is false. Mutant: drop each, and G4 reds naming it.
- **G5, the preflight.** A stub answering `pong` with the right model is healthy. Wrong model, a non-`pong` answer, or
  rc ≠ 0 are each unavailable. A stub that writes into the checkout makes the preflight FAIL with the COREDEV-2607
  message.

**Live (recorded in the PR, not in the suite):**
- **L1, the policy denies under the real CLI.** In a scratch dir, with the shipped policy, ask 3.1 Pro to exit plan mode
  and then write a file and run a shell command. Assert no file appears and nothing ran, and record the denial in the
  JSON tool stats. Run it once WITHOUT `--policy` as the contrast, and record whether the model attempts
  `exit_plan_mode` at all.
- **L2, a full gate round on this plan** through `capture-gemini-review.sh`, with a parseable `VERDICT:`, `TREE=clean`
  and `.model` = `gemini-3.1-pro-preview`.
- **L3, the preflight** passes live.

## 5. Rollout

1. Build the prototype: item 1 of §3 plus the `capture-gemini-review.sh` switch. Run L3, L1, then L2 on this plan. That
   is the new arm's review. Run the Codex arm on the same plan bytes in parallel.
2. Iterate on the findings. Codex's findings follow the Q1/Q2 stopping rule. The new arm's findings count as review
   evidence, not as a gate pass, until the plan is synthesized.
3. Implement the rest of §3, then run G1–G5 with their mutants, the full local gate, and `codex review --base
   origin/alpha`.
4. Open a PR into `alpha`, trigger the bot reviews, and triage them. **Merge needs the maintainer's word.**
5. After merge, run one real gate round with the shipped skill (any open plan) as the end-to-end check.

## 6. Out of scope, and boundaries stated rather than covered

- **Preview-model retirement.** `gemini-3.1-pro-preview` will be retired eventually. The preflight and the adapter fail
  closed with the model's name, and the sixth operand allows a one-round override. Moving the default is a one-line,
  reviewed change. There is no listing command to resolve from automatically.
- **Quota.** 3.1 Pro has lower quotas than Flash. A quota failure is a failed round (adapter or CLI non-zero), never an
  approval. If quota limits gate cadence, that is a follow-up.
- **The Kimi stand-in and the Codex arm** are untouched.
- **`README` history** that names `agy` or 3.1 Pro on `agy` describes past releases and stays.
