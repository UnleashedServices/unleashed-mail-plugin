---
name: gemini-review
description: Plan and debug review via the `gemini` CLI, run isolated (binary `gemini`, model: the `DEFAULT_MODEL` that `isolated-gemini-review.sh` declares, asserted from the CLI's own JSON stats). Use before implementing any plan or fix.
# MIN-27: this user-invoked workflow is nothing BUT capture pipelines, yet granted no tools — so every one of
# the documented 2-6 gate rounds re-prompted for the same commands. Scope the grant to exactly what the body
# runs (the plugin's capture and preflight scripts); do not grant unscoped Bash, and do NOT grant
# `Bash(gemini *)`: a raw launch bypasses the adapter's model assertion, the deny policy and the isolation
# harness, and headless plan mode is NOT read-only (COREDEV-2887).
# The prompt file this body REQUIRES writing is granted narrowly. Without it the mandatory first
# step prompted for permission (or was denied) before the newly narrowed capture grant could run —
# so tightening the capture command had made the flow LESS usable, not more. The glob is the exact
# per-round filename shape the recipe derives, not a general repo write (PR #63 recheck, P2).
# Edit(...), NOT Write(...): since Claude Code 2.1.210 file-permission rules are consulted for
# `Edit(path)`/`Read(path)` only — a `Write(path)` rule is accepted but NEVER consulted (docs:
# "Use Edit(docs/**) in place of Write(docs/**)"), so the previous Write-form grant was dead on the
# CLI this plugin targets (>= 2.1.219) and every round re-prompted anyway (2026-08-17 audit, AF-27).
# An Edit(path) allow rule covers all built-in file-editing tools on that path, the Write tool included.
allowed-tools: Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/capture-gemini-review.sh *), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/preflight-gemini.sh), Edit(.agy-prompt-*.md), Read
---

# Gemini Review (the `gemini` CLI, isolated)

All plans and debugging sessions must be reviewed by the Gemini arm before implementation. Non-negotiable — paired with `/codex-review`. **The canonical invocation is the namespaced `/unleashed-mail:gemini-review`** — the plugin registers its skills namespaced, so that form always resolves; the bare `/gemini-review` resolves only where the consumer workspace ships its own local copy (AGENT_CONTRACTS Cross-references; 2026-08-17 audit, AF-6).

**History.** Until COREDEV-2887 (2026-10-14) this arm ran the Antigravity CLI (`agy`). Gemini 3.1 Pro was retired there, and `agy`'s Flash arm stopped answering, so the arm now runs Google's `gemini` CLI with the 3.1 Pro preview, inside the same isolation harness. The per-round prompt keeps its historical `.agy-prompt-<T>r<N>.md` name: the `.gitignore` glob, this skill's `Edit` grant and every existing gate document use it.

| Trigger                           | When                       |
| --------------------------------- | -------------------------- |
| New plan or architecture decision | BEFORE any code is written |
| Bug investigation or debugging    | BEFORE proposing fixes     |

## Scope and round hygiene (read before dispatching)

- **The granted capture wrapper is PLAN-ONLY.** `capture-gemini-review.sh` requires a `<plan>` operand
  and `bind-prompt.py` binds only `docs/planning/*_PLAN.md` documents — a prompt naming no plan (or a
  non-plan target like `docs/planning/ISSUE-42.md`) is refused with "the prompt never names a plan"
  **before the reviewer launches**. This is by design: the digest-bound, gate-bearing artifact chain
  exists for plans. **Debug/bug-investigation reviews are ADVISORY** — they produce no verdict artifact
  and never satisfy the `/unleashed-mail:implement` gate. Run them by writing the investigation up as a
  `*_PLAN.md` (a diagnosis plan is a plan — this makes the round gate-bearing and isolated). Do not run
  the `gemini` CLI against the working tree for one: it is not read-only (below). Do not fight the "never
  names a plan" refusal by renaming arbitrary files to `*_PLAN.md`. (2026-08-17 audit, AF-3; a scripted
  non-plan `--target` binding is tracked in COREDEV-2654.)
- **Write BOTH per-round prompt files BEFORE launching either arm, then freeze the tree.** The
  isolation harnesses fingerprint the live checkout before and after each round and **void the round on
  ANY surviving difference — a new untracked file included** (exit 3). Writing `.codex-prompt-*.md`
  while the gemini round is still running voids that round at the finish line in any repo that does not
  git-ignore these files; so does unrelated untracked churn (build logs, editor droppings). Order:
  write `.agy-prompt-<T>r<N>.md` AND `.codex-prompt-<T>r<N>.md`, then dispatch both captures, and make
  no working-tree changes until both rounds land. **Consumer repos must add the ignore globs**
  `.agy-*.md`, `.codex-*.md`, `.kimi-*.md`, `.gate-*-prompt.md` (see README → Installation).
  (2026-08-17 audit, AF-5.)
- **The assembled prompt has a 1000-byte floor.** The wrapper passes `--min-bytes 1000` to
  `stage-prompt.py`; the read-only guard it prepends is ~381 bytes, so your prompt file itself must
  carry a real review specification (roughly 620+ bytes — the schematic example under "Invocation
  patterns" is illustrative, not sufficient). A refusal naming the floor means the prompt was too
  thin or truncated, not that the CLI failed. (2026-08-17 audit, AF-9.)
- **A NON-ZERO CAPTURE IS `MISSING`, whatever its transcript says.** Exit 3 is a VOID (the reviewer
  changed the tree or the staged basis), 4 is a REFUSED run (another model answered, the CLI reported an
  error, its output was not the expected JSON, or an environment file would configure the reviewer), and
  any other status is the CLI's own (173 is a capacity error). A voided round's transcript can still hold
  the reviewer's `VERDICT:` line, and nothing downstream reads the capture status — neither
  `/unleashed-mail:review-synthesis` nor `persist-verdict.sh` — so **never pass a non-zero capture's
  transcript to synthesis**: record that reviewer as `MISSING` for the round. (Making persistence require
  proof of a clean round is COREDEV-2888.)

## Setup

- **Tool:** the `gemini` CLI (verified 0.64.0, 2026-10-14; typical install `/opt/homebrew/bin/gemini`), resolved via `$PATH`. Call it only through this skill's two scripts — never directly, and never through an MCP wrapper.
- **Auth:** OAuth-personal through the CLI's own login (run `gemini` interactively once, in a scratch directory, to sign in). The CLI loads the operator's home environment file (`~/.gemini/.env`, else `~/.env`) as before; **any OTHER `.env` or `.gemini/.env` the CLI would reach above the reviewer's working directory refuses the run** (exit 4), because a repository-controlled one could set the reviewer's endpoint or credentials (COREDEV-2887 F14).
- **Smoke test / preflight:** `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/preflight-gemini.sh"` — ONE granted command. It allocates its own per-run ping path (a shared path lets a preflight that dies before writing leave the PREVIOUS run's `pong` in place, so a dead CLI reads as healthy — deep review, P2), pings through the SAME adapter a review runs through, from a scratch directory, with the checkout fingerprinted before and after, and keeps the CLI's diagnostics at `<ping>.diag`. It is healthy only when the asserted model answered `pong` as its WHOLE answer (case-insensitive, optionally ending in `.` or `!`), and every failure line names the model. **If the Gemini arm is unavailable (fresh machine / CI / capacity), the gate is fail-closed** — do NOT count it as APPROVE. **There is no scripted waiver**: stop and let the _user_ choose the recovery (install/authenticate the CLI, retry later as a new round, capture the review elsewhere, or explicitly direct work outside `/implement` — a workflow exception, not a passed gate). Present the choices; never select, infer, or self-waive. See "Preflight & unavailable-reviewer recovery" in `AGENT_CONTRACTS.md` §2.
- **Model:** the harness runs its `DEFAULT_MODEL` (read it with `grep DEFAULT_MODEL scripts/review/isolated-gemini-review.sh`; the preflight reads the same literal, so the two cannot disagree). The `gemini` CLI has no model-listing command, so there is nothing to resolve from: a retired model fails the preflight and the round CLOSED, naming itself. **The answering model is ASSERTED** — the adapter requests `-o json` and refuses the round unless the CLI's `stats.models` names exactly the requested model, so an automatic fallback or a plan-mode route to Flash can never be recorded as this arm's review. The model a round ran is recorded beside its transcript, in `<transcript>.model`. To run one round on another model, pass it as the SIXTH OPERAND — not as a `MODEL=` prefix, which is a different command shape and does not match this skill's capture grant: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/capture-gemini-review.sh" <ticket> <round> <prompt> <plan> 1800 <model>`. Moving the default is a one-line, reviewed change to `DEFAULT_MODEL`. For debug review: NO fallback — fail the review rather than degrade.
- **Trust and settings:** the reviewer runs in a disposable checkout the CLI has never seen, so the adapter passes `--skip-trust` and sets `GEMINI_CLI_TRUST_WORKSPACE=true` (the CLI loads workspace settings BEFORE `--skip-trust` takes effect). The harness stages that checkout's own `.gemini/settings.json` with plan-mode model routing OFF and the CLI's `.gitignore`/`.geminiignore` file filtering OFF (the staged prompt can sit under a path the reviewed repo ignores, and a committed `.geminiignore` must not hide the plan); it never touches your global settings. A reviewed repository that COMMITS a `.gemini` or `.env` entry is refused (exit 1) before anything is staged. A committed `.mcp.json` is fine: the CLI does not read it.
- **No MCP server is started.** The adapter passes `--allowed-mcp-server-names` with a name generated per run from 128 random bits, so no server configured anywhere can match it (a fixed name was matched by a server configured under it; an EMPTY allowlist means unrestricted).

> ## ⚠️ The `gemini` CLI IS NOT READ-ONLY HEADLESS — NEVER POINT IT AT THE WORKING TREE
>
> **Plan mode is not a boundary in headless use.** In non-interactive runs the CLI's policy engine
> auto-approves `exit_plan_mode`, and leaving plan mode switches to YOLO, which auto-approves every tool.
> Observed 2026-10-14 in a scratch directory: asked to leave plan mode and write, 3.1 Pro did — it created
> a file, ran a shell command and overwrote another (COREDEV-2887 F4).
>
> | invocation (headless, no deny policy) | wrote the file?                            |
> | ------------------------------------- | ------------------------------------------ |
> | `--approval-mode plan`                | **yes** (via `exit_plan_mode`, then YOLO)  |
> | `--approval-mode yolo`                | **yes**                                    |
> | either, with the shipped `--policy`   | no — the tools are withheld from the model |
>
> The arm therefore has THREE layers, and only the last is the guarantee: plan mode; a per-run deny
> policy (`scripts/review/gemini-review-policy.toml`: `exit_plan_mode`, `write_file`, `replace`,
> `run_shell_command`, `invoke_agent` and every MCP tool, priority 999, in every mode); and the isolation
> harness — a disposable checkout, fingerprinted before and after, the round VOID (exit 3) on any
> surviving change. **Isolate instead of constraining.** The origin is COREDEV-2607: on 2026-07-29 an
> `agy` plan review **implemented the plan instead of reviewing it** — 6 shipped scripts modified, 5
> files created — and emitted no `VERDICT:` line, so the gate failed closed but the edits persisted.
> That is the asymmetry with [`codex-review`](../codex-review/SKILL.md), which runs `-s read-only`.

Interface: `capture-gemini-review.sh <ticket> <round> <prompt-file> <plan> [timeout] [model]`.

**`isolated-gemini-review.sh` is the harness that entrypoint calls, not a command to run directly.** This
skill's `allowed-tools` grants the capture wrapper and not the harness, so invoking the harness yourself
prompts or is denied; and the plan is its _fourth_ operand, so a hand-written three-argument call skips
plan staging entirely and the reviewer reads the COMMITTED plan instead of the uncommitted edits that are
the normal state during review iteration (PR #63 recheck, P2). Use the complete recipe under "Required
invocation inputs" below; never derive or normalize the allocated path.

```bash
# capture-gemini-review.sh allocates the per-run leaf, binds the prompt AND the plan to it, and hands
# off to scripts/review/isolated-gemini-review.sh, which creates a disposable DETACHED checkout of the
# reviewed commit, refuses a committed .gemini/.env, stages the bound plan snapshot into it —
# authenticated against the `.plan` digest, so bytes substituted after binding are refused rather than
# reviewed — rewrites the prompt's absolute paths to point there, prepends a read-only guard, and runs
# scripts/review/gemini-review-run.py (the adapter) against THAT copy under pty-capture.py. The adapter
# runs the CLI with the deny policy, asserts the answering model, and prints ONLY the validated response:
# the CLI's stderr and every refusal go to `<leaf>.diag`, so a refused run leaves the transcript EMPTY.
# The harness then asserts the real working tree and the disposable copy are unchanged. A mutation exits
# 3 and VOIDS the round rather than being cleaned up silently.
#
# Staleness protection comes from the PER-RUN ALLOCATED PATH — the wrapper no longer pre-cleans, and
# must not (an ABSENT transcript maps to MISSING -> the gate fails closed; a STALE one would be read as
# this round's verdict). Each round gets its own leaf, so absence is guaranteed without deleting
# anything. The wrapper additionally REFUSES a non-empty reserved leaf, so a retry is forced to
# re-allocate rather than overwrite a previous round's bytes. It extracts the verdict with an ANCHORED
# grep — a loose `grep VERDICT:` matches the prompt's own echoed template in a timed-out transcript.
bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/capture-gemini-review.sh" \
    "$TICKET" "$ROUND" ".agy-prompt-${TICKET}r${ROUND}.md" "$PLAN" 1800
# -> UNLEASHED_TRANSCRIPT=<the allocated leaf>  (printed BEFORE the capture starts, so a timeout keeps it)
#    EXIT=0 BYTES=… TREE=clean MODEL=<the model> VERDICT=VERDICT: APPROVE_WITH_NOTES
# Exit 3 = a VOID (the reviewer changed the tree or the staged basis). Exit 4 = the adapter REFUSED the
# run; the harness prints its reason, `gemini arm (<model>): GEMINI ARM FAILED [...] — <reason>`. Exit 1 =
# setup/prompt failure (e.g. a truncated prompt, which the wrapper refuses to launch on rather than
# burning a review). ANY non-zero exit is MISSING (see "Scope and round hygiene").
```

**One timeout, the whole review's wall clock.** The fifth operand (default **1800 s**) bounds the
review; the `gemini` CLI has no print-timeout of its own, so there is nothing to keep it above. (The
retired `agy` arm had to keep its wrapper cap ABOVE `agy --print-timeout`; that coupling, and the flag,
are gone — passing `--print-timeout` to the `gemini` CLI is an unknown-argument error.) A capacity error
(`429 … No capacity available`, the CLI exiting 173) is a failed round: retry later as a NEW round.

The capture runs under the committed, command-agnostic [`scripts/pty-capture.py`](../../scripts/pty-capture.py) (invoke as `${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py`) — the same wrapper [`codex-review`](../codex-review/SKILL.md) uses. The `gemini` CLI itself needs no TTY with `-o json`; the wrapper is there for the allocated-leaf protocol, the capture provenance (`<leaf>.captureid`) and the bounded teardown. Its hardening contract (verified across four Codex + Gemini review rounds):

- **Command passed after `--`** — wraps any command (the Gemini adapter, `codex exec`, …); the program is resolved on `$PATH`, callable from any directory.
- **Controlling TTY via `pty.fork()`** — the child gets a real controlling terminal (`setsid()` + `TIOCSCTTY` handled by the stdlib), so CLIs that open `/dev/tty` render instead of failing with `ENXIO`. A plain `openpty()` + `dup2()` does not acquire one.
- **Sane PTY window size** — a fresh PTY in a non-TTY context reports `0x0`; the wrapper sets `TIOCSWINSZ` (inherits `COLUMNS`/`LINES`, else 80×24) so width-aware CLIs don't wrap to nothing or emit empty/garbled transcripts.
- **Capture preserved on `SIGTERM`/`SIGHUP`** — a wrapper-level SIGTERM or SIGHUP (CI timeout, process manager, terminal close / SSH disconnect) is turned into a `SystemExit` whose unwinding still runs `finally`, which reaps the child **and writes the partial transcript** before exiting. Output is never lost; the child is never orphaned.
- **Teardown reaches helpers, never hangs** — the leader is killed directly with `os.kill(pid, …)` (reliable: it's our own child); the child's process group is signalled best-effort for any helpers (`os.killpg`, tolerant of macOS's spurious `ESRCH`), and closing the PTY hangs up the session as a final backstop. The SIGKILL reap is **bounded** — a denied/failed signal can never block the wrapper forever (the prior unbounded `waitpid(pid, 0)` could deadlock against a `SIGTERM`-trapping child whose group `killpg` had ESRCH'd).
- **Signal-safe cleanup** — the SIGTERM/SIGHUP handler disarms itself (`SIG_DFL`) before raising, and `finally` also resets the handlers, so a second signal — arriving while unwinding into cleanup, or during normal-path cleanup — can't re-enter the handler and abort the reap or the write.
- **`try / finally` block** — guarantees `master_fd` close + child reaping + output write even on `KeyboardInterrupt`, SIGTERM/SIGHUP, or exception.
- **Capture failure is never silent** — if persisting the transcript fails (bad dir, permissions, full disk) the wrapper writes a diagnostic to its own stderr and forces a non-zero exit, rather than reporting the child's (often `0`) status with no output.
- **Exit-code fidelity** — `os.waitstatus_to_exitcode` propagates the child's code; a signal death (negative status) is normalized to the Unix `128 + signum` convention rather than a masked 8-bit value.
- **`execvp` failure is diagnosable** — the child writes `pty-capture: failed to execute …` to its PTY stderr (captured in the output file) and `os._exit(127)`, instead of leaving an empty file.
- **Output dir auto-created** — `os.makedirs(exist_ok=True)` on the out-path parent, so a missing directory doesn't raise `FileNotFoundError`.
- **Unix newlines** — the PTY's `\r\n` (ONLCR) is normalized to `\n` in the captured file. (The Gemini adapter normalizes the response's own CRLF and lone CR to LF first, because the PTY would double a CR.)
- **`InterruptedError` → `continue`** (not `break`) — signals during `select`/`read` (e.g., SIGWINCH from terminal resize, SIGCHLD when child exits) retry the loop instead of terminating a healthy child.
- **Bounded termination ladder** — finally requests SIGTERM, waits up to `SIGTERM_GRACE_SEC` (5 s) polling with `WNOHANG`, then escalates to SIGKILL with a further bounded (`SIGKILL_REAP_SEC`, 2 s) `WNOHANG` reap — never an unbounded blocking wait. Worst case for a CLI that fully ignores SIGTERM is ~grace + reap, then exit.
- **Drain before close on every path** — the read loop drains on natural exit, and the cancellation (`SIGTERM`/`SIGHUP`) path drains the PTY again after reaping and before closing, so final diagnostics the CLI emits while handling the signal (and bytes buffered when `select` was interrupted) still reach `<out-path>`. Both drains are bounded (≤ 0.5 s).

**Why not just `gemini -p "…" > review.txt`?** A raw run has none of the arm's guarantees: no model
assertion (a fallback answer would be recorded as 3.1 Pro's), no deny policy (headless plan mode can reach
YOLO and write), no isolation (it runs in, and can change, the tree under review), and no binding of the
transcript to the plan it reviewed. This skill grants no `Bash(gemini *)` for exactly that reason.

## Invocation patterns

### Slim-argv + workspace prompt file (the only gate path)

Put the full review/task spec in a PER-ROUND workspace markdown file — `.agy-prompt-${TICKET}r${ROUND}.md`, never a shared `.agy-prompt.md`, because two concurrent rounds sharing one prompt cross-wire prompt and transcript (deep review, P1). The harness stages it and hands the reviewer a short `Read and follow <path>` prompt. Keeps argv small AND makes the prompt editable/version-controllable.

```bash
# 1. WRITE the prompt to the per-round workspace file with the **Write tool**, not a shell heredoc.
#    This skill grants `Edit(.agy-prompt-*.md)` (the Edit-form rule pre-approves all built-in
#    file-editing tools on that path, Write included; a Write-form rule is never consulted on
#    CLI >= 2.1.210); a `cat > … <<EOF` is a Bash redirect matching no Bash
#    grant, so it PROMPTS on every gate round — the exact reprompt the granted flow exists to avoid
#    (PR #63 recheck, P2). Same shape as codex-review's `Edit(.codex-prompt-*.md)` step. Give the file
#    an absolute plan reference — the harness rewrites the checkout root to the disposable copy, e.g.:
#
#        Write(.agy-prompt-${TICKET}r${ROUND}.md):
#          # Review task
#          Read $(pwd)/docs/planning/FEATURE_PLAN.md
#          and provide architectural assessment.
#          Verdict: APPROVE / APPROVE_WITH_NOTES / REQUEST_CHANGES.

# 2. Capture it through the GRANTED wrapper. It allocates the per-run leaf (MAJ-10: staleness protection
# comes from that PER-RUN ALLOCATED PATH, so a wrapper that never starts leaves the leaf ABSENT — never a
# STALE previous-round transcript — and absent maps to MISSING), binds the prompt and plan to it, runs the
# adapter against a disposable detached checkout, and asserts the real tree is unchanged afterwards.
# DO NOT `rm -f` THE RESERVED LEAF. The allocator creates it 0-byte and pty-capture.py --allocated opens
# it WITHOUT O_CREAT; deleting it makes the final write fail on a missing file after the whole review has
# already run, losing the round (PR #63 review, gaps 13-14). Retries must RE-ALLOCATE, which the wrapper
# enforces by refusing a non-empty reserved leaf.
bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/capture-gemini-review.sh" \
    "$TICKET" "$ROUND" ".agy-prompt-${TICKET}r${ROUND}.md" "$PLAN" 1800
# -> the same UNLEASHED_TRANSCRIPT= marker; the capture lands in that allocated leaf and nowhere else.
```

### From an interactive terminal

Running `gemini` interactively in a real terminal is fine for exploration, and you can watch what it does — but it is **not** a gate round, and it **can write to the workspace** (COREDEV-2607, and F4 above). Run it from a scratch directory, never the reviewed checkout, and check `git status` afterwards either way. A gate-bearing review always goes through the capture wrapper.

## Flags the adapter passes (`gemini --help`)

| Flag                                   | Why                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------ |
| `--skip-trust`                         | The disposable checkout is untrusted; without it the CLI refuses (rc 55) |
| `-m <model>`                           | The harness's `DEFAULT_MODEL`, or the sixth operand                      |
| `--approval-mode plan`                 | A layer, not the boundary (see the warning above)                        |
| `--policy <gemini-review-policy.toml>` | Withholds every write, shell, delegation and MCP tool, in every mode     |
| `--allowed-mcp-server-names <random>`  | Starts no MCP server: a per-run name nothing is configured under         |
| `-o json`                              | `stats.models` names the model that answered; the adapter asserts it     |
| `-p "Read and follow <prompt>"`        | One headless turn                                                        |

## Workflow

<!-- prettier-ignore -->
1. **Smoke-test:** `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/preflight-gemini.sh"` → it pings the model the gate will run and prints `gemini preflight: healthy` when that model answered `pong`. If it reports unavailable, its line names the model and the reason; re-login interactively (in a scratch directory) if it is an auth failure.
2. **Check the model the GATE will use:** the harness's `DEFAULT_MODEL` (or your sixth-operand override); the round records it in `<transcript>.model` and on its `MODEL=` summary line — read either.
3. **Write the task** to a PER-ROUND workspace prompt file (`.agy-prompt-${TICKET}r${ROUND}.md`) with all context including absolute paths to any files the reviewer must read.
4. **Invoke** the capture wrapper (the recipe under "Required invocation inputs").
5. **Read the capture's exit and summary line.** Non-zero is `MISSING` for the round — do not read a verdict out of that transcript (see "Scope and round hygiene").
6. **Capture output** — the isolated helper writes to the exact path in `GEMINI_TRANSCRIPT`. Read that
   allocated file back into context; do not reconstruct its name.
7. **Incorporate** the feedback into the plan; iterate until APPROVE or APPROVE_WITH_NOTES. Each round is
   a NEW capture (a new leaf); there is no conversation to continue.
8. **Synthesize both reviews** — once the paired `/unleashed-mail:codex-review` transcript is also captured, invoke
   `/unleashed-mail:review-synthesis` with each allocated path as one quoted `--reviewer
   "<name>=<STATUS>:<allocated-path>"` argument. Make sure each review prompt asks the reviewer to finish
   with an explicit `VERDICT:` line (e.g. `APPROVE / APPROVE_WITH_NOTES / REQUEST_CHANGES`) so the
   synthesis can read it deterministically.

Do not skip to save time. Do not treat as a rubber stamp.

## Required invocation inputs

/unleashed-mail:gemini-review --ticket <T> --round <N> <plan>

Ticket and round are required operands received from that invocation; never infer either from the plan,
branch, or prior transcript. If either is absent, stop before allocation. Bind the received operands to
`TICKET`, `ROUND` and `PLAN` in the same Bash invocation, then run this complete recipe. The marker remainder
is copied with shell prefix removal only; every later expansion is quoted so the path remains one opaque
argument.

```bash
# Write this round's prompt to a PER-ROUND file first — `.agy-prompt-${TICKET}r${ROUND}.md`, never a
# shared `.agy-prompt.md`. A shared prompt is the same MAJ-10 hazard as a shared transcript: two
# concurrent rounds each get a unique leaf, but the second overwrites the prompt before the first
# wrapper reads it, so the first round records a fresh, valid transcript OF THE OTHER PLAN under its
# own ticket and round. The helper records the prompt's digest beside the transcript.
# COREDEV2619_GEMINI_CAPTURE_BEGIN
bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/capture-gemini-review.sh" "$TICKET" "$ROUND" ".agy-prompt-${TICKET}r${ROUND}.md" "$PLAN" 1800
# COREDEV2619_GEMINI_CAPTURE_END
```

## Diagnostics

If a round fails, check in order:

1. **The harness's stderr.** A refused run prints `gemini arm (<model>): GEMINI ARM FAILED [...] — <reason>`; a void prints `GATE FAILED — …` and the change it saw.
2. **`<transcript>.diag`** — the CLI's own stderr for that round, and the adapter's refusal line. A `429 … No capacity available` there is Google's capacity (retry later as a new round), not your quota or your prompt.
3. `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/preflight-gemini.sh"` — should print `gemini preflight: healthy`; every failure line names the model.
4. `gemini --version` — verified 0.64.0. A much newer CLI may have changed a flag the adapter passes; the preflight goes through the same adapter, so it catches that too.

## One-shot preamble (REQUIRED for the automated path)

The two system prompts below are written for an **interactive** session: they invite clarifying questions
and end with "Start by asking me…". The automated gate gives the reviewer exactly ONE headless turn — a
reviewer following them verbatim replies with a _counter-question_, producing a transcript
`/unleashed-mail:review-synthesis` cannot parse, which burns a gate round.

**So when building the per-round prompt file for the one-shot path, prepend this preamble** (it overrides the
ask-first/opener instructions below) and append the target path:

```markdown
ONE-SHOT MODE — you have exactly ONE response; there is no follow-up turn.

- Do NOT ask clarifying questions and do NOT ask what to review. Review the artifact at the absolute
  path given below, right now, using only what you can read from disk.
- If something is genuinely unresolvable from the files, state the assumption you made and continue —
  never end your turn with a question.
- Ignore any instruction below to "start by asking" or to request files interactively; read them yourself.
- End your response with EXACTLY one final line:
  VERDICT: APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES

REVIEW TARGET: <absolute path to the plan / the issue description>
```

The `VERDICT:` line is what makes synthesis deterministic (Workflow step 8) — without it the verdict must
be inferred from prose and confidence drops. The interactive prompts below are unchanged for interactive use.

## Plan review — system prompt

> You are a senior software architect and development consultant acting as my conversational review partner. Your role is to thoroughly review and discuss development plans, architecture decisions, and implementation strategies BEFORE any code is written. You are NOT to write, modify, or suggest specific code changes — that work will be handled separately by Claude Code. Your job is purely analytical and advisory.
>
> When I share a development plan, feature spec, architecture document, or technical approach, review and discuss the following aspects conversationally:
>
> **Architecture & Design**
>
> - Overall system architecture and component relationships
> - Design pattern selection and appropriateness
> - Separation of concerns and modularity
> - Scalability considerations and potential bottlenecks
> - Data flow and state management approach
>
> **Framework & Technology Choices**
>
> - Framework suitability for the stated requirements
> - Dependency evaluation (maturity, maintenance status, licensing)
> - Compatibility between chosen technologies
> - Performance implications of the tech stack
>
> **Planning & Requirements**
>
> - Completeness of requirements and acceptance criteria
> - Edge cases, error scenarios, and failure modes not accounted for
> - Dependency mapping and sequencing of work
> - Risk identification and mitigation strategies
> - Scope clarity — anything ambiguous or underspecified
>
> **Code Quality & Standards**
>
> - Adherence to modern best practices as documented in current official documentation (always reference Context7 for the latest documentation on any frameworks, libraries, or tools being discussed)
> - API design and contract clarity
> - Security considerations and potential vulnerabilities
> - Testing strategy and coverage approach
> - Accessibility and compliance requirements where applicable
>
> **Developer Experience & Maintainability**
>
> - Naming conventions and organizational structure
> - Documentation needs
> - CI/CD and deployment considerations
> - Logging, monitoring, and observability planning
>
> Important guidelines:
>
> - Always consult and reference Context7 for the most current documentation, best practices, and API references for any technology being discussed. Do not rely on potentially outdated training data when current docs are available.
> - Be conversational — ask clarifying questions, challenge assumptions, and propose alternatives through discussion rather than code.
> - Flag risks and concerns with clear reasoning, not just warnings.
> - When you identify a gap or concern, explain WHY it matters and what the consequences could be.
> - Prioritize your feedback — distinguish between critical issues, strong recommendations, and nice-to-haves.
> - If you need more context about any aspect of the plan, ask before making assumptions.
>
> **File Access:** You have complete read access to any file in this project. If you need to see source code, configuration, tests, documentation, or any other file to inform your review, ask and it will be provided immediately. Do not hesitate to request specific files — thorough review requires full context.
>
> Start by asking me what I'd like to review today.

> **Interactive sessions only.** On the automated one-shot path this opener does NOT apply — the
> One-shot preamble above overrides it (review the given path immediately; end with `VERDICT:`).

## Debug review — system prompt

> You are a senior debugging specialist and codebase investigator acting as my conversational partner for diagnosing issues and bugs. Your role is to help me READ, UNDERSTAND, and REASON about code to identify root causes and formulate fix strategies. You are NOT to write, modify, or suggest specific code patches — all code changes will be handled separately by Claude Code. Your job is to help me think through the problem and arrive at a clear diagnosis and action plan.
>
> When I share a bug report, error log, unexpected behavior, or code snippet for investigation, work through the following conversationally:
>
> **Issue Characterization**
>
> - Clarify the expected vs. actual behavior
> - Identify whether the issue is deterministic or intermittent
> - Establish the scope — is this isolated or potentially systemic
> - Determine when the issue was introduced if possible (recent change, always existed, environmental)
>
> **Codebase Analysis**
>
> - Trace the execution path related to the issue
> - Identify relevant components, modules, and their interactions
> - Examine data flow, state transitions, and side effects along the path
> - Review error handling and boundary conditions in the affected area
>
> **Root Cause Investigation**
>
> - Develop and evaluate hypotheses for the root cause
> - Identify the most likely cause and explain the reasoning
> - Consider secondary or contributing factors
> - Check for related issues that may share the same root cause
>
> **Context & Best Practices Validation**
>
> - Always reference Context7 for the latest documentation on any frameworks, libraries, or APIs involved in the issue. Verify that current usage aligns with documented behavior and best practices — do not rely on potentially outdated training data.
> - Identify if the issue stems from deprecated patterns, misused APIs, or deviation from documented conventions.
> - Note if the relevant library or framework version has known issues or breaking changes.
>
> **Fix Strategy & Prevention**
>
> - Describe the conceptual approach to fixing the issue (without writing the fix)
> - Identify what areas of the codebase would need to change
> - Suggest what tests should be added or updated to cover this case
> - Recommend any preventive measures to avoid similar issues (architectural, process, or tooling)
>
> Important guidelines:
>
> - Always consult and reference Context7 for current documentation and known issues related to any technology involved. This is critical for ensuring any diagnosis accounts for the actual documented behavior of dependencies.
> - Be conversational — walk through the investigation like a pair debugging session. Ask me questions about behavior, environment, and reproduction steps.
> - Think out loud — share your reasoning as you narrow down hypotheses so I can follow and contribute.
> - When you need to see more code, specific logs, or configuration, ask for exactly what you need and explain why.
> - Distinguish between what you're confident about and what you're still hypothesizing.
> - Summarize your findings clearly at the end: root cause, affected areas, recommended fix approach, and prevention steps — all as discussion points for implementation by Claude Code.
>
> **File Access:** You have complete read access to any file in this project. If you need to see source code, stack traces, logs, configuration, tests, or any other file to inform your investigation, ask and it will be provided immediately. Do not hesitate to request specific files — thorough debugging requires full context.
>
> Start by asking me to describe the issue I'm investigating.

> **Interactive sessions only.** On the automated one-shot path this opener does NOT apply — the
> One-shot preamble above overrides it (investigate the given issue immediately; end with `VERDICT:`).
