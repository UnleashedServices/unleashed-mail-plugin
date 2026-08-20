---
name: gemini-review
description: Plan and debug review via the Antigravity CLI (binary `agy`, model `gemini-3.6-flash-high`). Use before implementing any plan or fix.
# MIN-27: this user-invoked workflow is nothing BUT pty-capture Bash pipelines, yet granted no tools — so
# every one of the documented 2-6 gate rounds re-prompted for the same commands. Scope the grant to exactly
# what the body runs (the plugin's scripts, the CLI probe, and `agy`); do not grant unscoped Bash.
# The prompt file this body REQUIRES writing is granted narrowly. Without it the mandatory first
# step prompted for permission (or was denied) before the newly narrowed capture grant could run —
# so tightening the capture command had made the flow LESS usable, not more. The glob is the exact
# per-round filename shape the recipe derives, not a general repo write (PR #63 recheck, P2).
# Edit(...), NOT Write(...): since Claude Code 2.1.210 file-permission rules are consulted for
# `Edit(path)`/`Read(path)` only — a `Write(path)` rule is accepted but NEVER consulted (docs:
# "Use Edit(docs/**) in place of Write(docs/**)"), so the previous Write-form grant was dead on the
# CLI this plugin targets (>= 2.1.219) and every round re-prompted anyway (2026-08-17 audit, AF-27).
# An Edit(path) allow rule covers all built-in file-editing tools on that path, the Write tool included.
allowed-tools: Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/capture-gemini-review.sh *), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/preflight-agy.sh), Bash(command -v agy), Edit(.agy-prompt-*.md), Read
---

# Antigravity (`agy`) Review

All plans and debugging sessions must be reviewed by the `agy` CLI before implementation. Non-negotiable — paired with `/codex-review`. **The canonical invocation is the namespaced `/unleashed-mail:gemini-review`** — the plugin registers its skills namespaced, so that form always resolves; the bare `/gemini-review` resolves only where the consumer workspace ships its own local copy (AGENT_CONTRACTS Cross-references; 2026-08-17 audit, AF-6). The `gemini` name is kept for muscle memory while the underlying CLI is Antigravity (Google retired the older `gemini` CLI in May 2026).

| Trigger | When |
|---------|------|
| New plan or architecture decision | BEFORE any code is written |
| Bug investigation or debugging | BEFORE proposing fixes |

## Scope and round hygiene (read before dispatching)

- **The granted capture wrapper is PLAN-ONLY.** `capture-gemini-review.sh` requires a `<plan>` operand
  and `bind-prompt.py` binds only `docs/planning/*_PLAN.md` documents — a prompt naming no plan (or a
  non-plan target like `docs/planning/ISSUE-42.md`) is refused with "the prompt never names a plan"
  **before the reviewer launches**. This is by design: the digest-bound, gate-bearing artifact chain
  exists for plans. **Debug/bug-investigation reviews are ADVISORY** — they produce no verdict artifact
  and never satisfy the `/unleashed-mail:implement` gate. Run them either by (a) writing the
  investigation up as a `*_PLAN.md` (a diagnosis plan is a plan — this makes the round gate-bearing), or
  (b) invoking `agy` through `pty-capture.py` directly with the debug system prompt below — that
  invocation is outside this skill's grants, so expect a permission prompt; that is intentional for a
  non-gate round. Do not fight the "never names a plan" refusal by renaming arbitrary files to
  `*_PLAN.md`. (2026-08-17 audit, AF-3; a scripted non-plan `--target` binding is tracked in
  COREDEV-2654.)
- **Write BOTH per-round prompt files BEFORE launching either arm, then freeze the tree.** The
  isolation harnesses fingerprint the live checkout before and after each round and **void the round on
  ANY difference — a new untracked file included** (exit 3). Writing `.codex-prompt-*.md` while the
  ~28-minute gemini round is still running voids that round at the finish line in any repo that does
  not git-ignore these files; so does unrelated untracked churn (build logs, editor droppings). Order:
  write `.agy-prompt-<T>r<N>.md` AND `.codex-prompt-<T>r<N>.md`, then dispatch both captures, and make
  no working-tree changes until both rounds land. **Consumer repos must add the ignore globs**
  `.agy-*.md`, `.codex-*.md`, `.kimi-*.md`, `.gate-*-prompt.md` (see README → Installation).
  (2026-08-17 audit, AF-5.)
- **The assembled prompt has a 1000-byte floor.** The wrapper passes `--min-bytes 1000` to
  `stage-prompt.py`; the read-only guard it prepends is ~381 bytes, so your prompt file itself must
  carry a real review specification (roughly 620+ bytes — the schematic example under "Invocation
  patterns" is illustrative, not sufficient). A refusal naming the floor means the prompt was too
  thin or truncated, not that the CLI failed. (2026-08-17 audit, AF-9.)

## Setup

- **Tool:** Antigravity CLI binary `agy` — resolve via `$PATH` (typical install: `~/.local/bin/agy`). Current verified version: 1.0.1 (2026-05-23). Call it directly via Bash — do NOT use an MCP wrapper.
- **Auth:** OAuth-personal handled by the CLI's own login. Creds cached at `~/.gemini/oauth_creds.json` (the `~/.gemini/` dir is reused by Antigravity for backward compatibility). DO NOT set `GEMINI_API_KEY` or `GOOGLE_CLOUD_PROJECT` (user rejected Vertex 2026-04-20).
- **Smoke test / preflight:** route through the PTY wrapper (bare `agy -p` writes 0 bytes from Claude's Bash tool / CI even on success). Allocate a PER-RUN ping path — a shared `/tmp` file lets a preflight that dies before writing leave the PREVIOUS run's `pong` in place, so a dead CLI reads as healthy, and two concurrent preflights overwrite each other (deep review, P2): `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/preflight-agy.sh"` — ONE granted command that allocates its own per-run ping path, hard-codes `-p "ping"`, and checks the path it allocated. It replaces `Bash(agy *)`, which let `agy` run OUTSIDE `isolated-agy-review.sh` even though this skill documents that agy has no read-only mode (deep review, P1). It greps `-qi pong` (**case-insensitive, and do not require the `!`** — across 3 measured runs agy answered `Pong! How can I help you today?`, a bare lowercase `pong`, and `Pong! Let me know how I can help you today.`; a `Pong!`-exact check calls a healthy CLI unavailable ~1 run in 3). Any of those from a real terminal is valid. If empty/errors, run `agy` interactively once to re-login. **If `agy` is unavailable (fresh machine / CI), the gate is fail-closed** — do NOT count it as APPROVE. **There is no scripted waiver**: stop and let the *user* choose the recovery (install/authenticate the CLI, capture the review elsewhere, or explicitly direct work outside `/implement` — a workflow exception, not a passed gate). Present the choices; never select, infer, or self-waive. See "Preflight & unavailable-reviewer recovery" in `AGENT_CONTRACTS.md` §2.
- **`--print-timeout` is REQUIRED for a real review.** `agy -p` defaults to `--print-timeout 5m0s`; a plan review that reads several files routinely exceeds it and dies with `Error: timeout waiting for response` (a ~36-byte transcript, exit 1). Always pass `agy --print-timeout 28m -p "Read and follow <the per-round prompt file>"` — the slim-argv form recommended below, NOT `-p "$(cat …)"`, which inlines the whole prompt into argv. **A healthy ping (`grep -qi pong`) plus a failed review means the invocation is wrong, NOT that the CLI is unavailable** — fix the flag and re-run; do not treat it as a reviewer-unavailable case. A tiny transcript is a *failure*, never a verdict, and never an APPROVE.
- **Model selection — `--model` EXISTS; the short `-m` does not.** `agy --help` lists `--model  Model for the current CLI session`, and `agy models` lists the valid names. A session flag OVERRIDES the global default in `~/.gemini/settings.json` (`"model": { "name": "gemini-3.1-pro" }`), which governs only invocations that pass no flag. **The wrapper passes `--model` explicitly** (`MODEL="${MODEL:-gemini-3.6-flash-high}"` in `scripts/review/isolated-agy-review.sh`, overridable via the `MODEL` environment variable), so wrapper rounds run that model and NOT the settings.json one. This documentation previously claimed the flag was removed while the wrapper was passing it — one of the two had to be wrong, and it was this text (PR #63 review, gap 6). **A fallback must therefore go through `MODEL`, not settings.json** — editing the global setting cannot affect a wrapper round, because the wrapper always supplies `--model`. To fall back for one plan review, pass the model as the SIXTH OPERAND — not as a `MODEL=` prefix, which is a different command shape and does not match this skill's capture grant: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/capture-gemini-review.sh" <ticket> <round> <prompt> <plan> 1800 gemini-2.5-pro`, and check `agy models` for the current valid names. Verify what a bare `agy` would use with `cat ~/.gemini/settings.json | grep model`, but do not mistake that for what the gate ran. For debug review: NO fallback — fail the review rather than degrade.
- **NO `-o` flag.** Output is plaintext only.
- **Workspace access — NOT persistent.** Each `agy -p` invocation is a fresh session. Either pass `--add-dir /absolute/path/to/workspace` on every invocation, OR use absolute paths in the prompt. The interactive `/add-dir` slash command (inside `agy -i` sessions) updates persistent state but doesn't affect `-p` runs.

## ⚠️ Critical: non-TTY invocation requires a Python PTY wrapper

`agy -p` uses a TTY-only "text drip" typewriter-style streaming UI. When stdout is piped or redirected (`> file`, `| tee`, Claude's Bash tool environment), the drip has nowhere to render → **0 bytes captured**, even though agy itself completed the task successfully. The conversation file in `~/.gemini/antigravity-cli/conversations/*.pb` is encrypted/opaque and cannot be extracted from.

**The only proven recipe for non-TTY contexts** (Claude's Bash tool, CI scripts, automation): run `agy` inside a pseudo-terminal via the committed, command-agnostic wrapper [`scripts/pty-capture.py`](../../scripts/pty-capture.py) (invoke as `${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py`). It runs the command under a controlling PTY via `pty.fork()` so the text-drip renders, ANSI-strips the output, writes it to `<out-path>`, and propagates the child's exit code. The **same wrapper** captures `codex exec` for [`codex-review`](../codex-review/SKILL.md) — one PTY wrapper, both review CLIs.

> ## ⚠️ `agy` IS NOT READ-ONLY — NEVER POINT IT AT THE WORKING TREE
>
> On 2026-07-29 a plan review **implemented the plan instead of reviewing it**: 6 shipped scripts
> modified, 5 files created, including a stray `marketplace.json` at the repo root (COREDEV-2607). It
> emitted no `VERDICT:` line so the gate failed closed — the *fortunate* failure mode — but the edits
> persisted. The concurrent `codex` review only stayed trustworthy because it independently
> re-anchored its citations to committed `HEAD`; nothing in the gate required that.
>
> **These flags were TESTED and none of them prevents writes. Do not re-try them:**
>
> | invocation | wrote the file? |
> |---|---|
> | `agy` (no flags) | **yes** |
> | `agy --mode plan` | **yes** |
> | `agy --sandbox` | **yes** |
> | `agy --sandbox --mode plan` | **yes** |
>
> All four exited 0. `--mode` is "agent execution mode (accept-edits, plan)" and `--sandbox` is
> "terminal restrictions"; neither restricts file writes in print mode. This is the asymmetry with
> [`codex-review`](../codex-review/SKILL.md), which already runs `-s read-only`. **Isolate instead of
> constraining** — that is what the wrapper below does.

Interface: `capture-gemini-review.sh <ticket> <round> <prompt-file> <plan> [timeout] [model]`.

**`isolated-agy-review.sh` is the harness that entrypoint calls, not a command to run directly.** This
skill's `allowed-tools` grants the capture wrapper and not the harness, so invoking the harness yourself
prompts or is denied; and the plan is its *fourth* operand, so a hand-written three-argument call skips
plan staging entirely and `agy` reviews the COMMITTED plan instead of the uncommitted edits that are the
normal state during review iteration (PR #63 recheck, P2). Two recipes here documented that stale
three-argument shape. Use the complete recipe under "Required invocation inputs" below; never derive or
normalize the allocated path.

```bash
# capture-gemini-review.sh allocates the per-run leaf, binds the prompt AND the plan to it, and hands
# off to scripts/review/isolated-agy-review.sh, which creates a disposable DETACHED worktree at the
# reviewed commit, stages the bound plan snapshot into it — authenticated against the `.plan` digest, so
# bytes substituted after binding are refused rather than reviewed — rewrites the prompt's absolute
# paths to point there, prepends a read-only guard, runs agy against THAT copy, then asserts the real
# working tree is byte-identical before/after. A tree mutation exits 3 and VOIDS the round rather than
# being cleaned up silently.
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
#    EXIT=0 BYTES=… TREE=clean VERDICT=VERDICT: APPROVE_WITH_NOTES
# Exit 3 = the reviewer mutated the tree. Exit 1 = setup/prompt failure (e.g. a truncated prompt,
# which the wrapper refuses to launch on rather than burning 20 minutes).
```

**Timeouts are load-bearing, and the INVARIANT matters more than either number:**

> the pty wrapper's timeout must **exceed** `agy`'s `--print-timeout`.

`--print-timeout 28m` (1680s) is passed by the wrapper because `agy`'s own default is 5m and a real
plan review blows past it. The pty wrapper's timeout (default **1800s**) sits deliberately above it,
because a lower wrapper cap SIGTERMs `agy` before its own print-timeout can fire, giving a masked
exit 124 instead of `agy`'s diagnosable `Error: timeout waiting for response`.

**Do not "correct" a recipe back to a smaller number.** This prose previously still described the
retired 18m/1500s pair while the wrapper had already moved to 28m/1800s, so following it produced a
wrapper cap *below* the print-timeout — killing live reviews at 25 minutes, the exact failure the
invariant exists to prevent (PR #63 review, gaps 10-12 and bot thread 4). If you change one value,
re-check the other and the contract test that binds them.

Do not paste or re-derive the recipe inline — invoke the committed [`scripts/pty-capture.py`](../../scripts/pty-capture.py). Its hardening contract (verified across four Codex + Gemini review rounds):
- **Command passed after `--`** — wraps any command (`agy`, `codex exec`, …); the program is resolved on `$PATH`, callable from any directory.
- **Controlling TTY via `pty.fork()`** — the child gets a real controlling terminal (`setsid()` + `TIOCSCTTY` handled by the stdlib), so CLIs that open `/dev/tty` (agy's text-drip, codex) render instead of failing with `ENXIO`. A plain `openpty()` + `dup2()` does not acquire one.
- **Sane PTY window size** — a fresh PTY in a non-TTY context reports `0x0`; the wrapper sets `TIOCSWINSZ` (inherits `COLUMNS`/`LINES`, else 80×24) so width-aware CLIs don't wrap to nothing or emit empty/garbled transcripts.
- **Capture preserved on `SIGTERM`/`SIGHUP`** — a wrapper-level SIGTERM or SIGHUP (CI timeout, process manager, terminal close / SSH disconnect) is turned into a `SystemExit` whose unwinding still runs `finally`, which reaps the child **and writes the partial transcript** before exiting. Output is never lost; the child is never orphaned.
- **Teardown reaches helpers, never hangs** — the leader is killed directly with `os.kill(pid, …)` (reliable: it's our own child); the child's process group is signalled best-effort for any helpers (`os.killpg`, tolerant of macOS's spurious `ESRCH`), and closing the PTY hangs up the session as a final backstop. The SIGKILL reap is **bounded** — a denied/failed signal can never block the wrapper forever (the prior unbounded `waitpid(pid, 0)` could deadlock against a `SIGTERM`-trapping child whose group `killpg` had ESRCH'd).
- **Signal-safe cleanup** — the SIGTERM/SIGHUP handler disarms itself (`SIG_DFL`) before raising, and `finally` also resets the handlers, so a second signal — arriving while unwinding into cleanup, or during normal-path cleanup — can't re-enter the handler and abort the reap or the write.
- **`try / finally` block** — guarantees `master_fd` close + child reaping + output write even on `KeyboardInterrupt`, SIGTERM/SIGHUP, or exception.
- **Capture failure is never silent** — if persisting the transcript fails (bad dir, permissions, full disk) the wrapper writes a diagnostic to its own stderr and forces a non-zero exit, rather than reporting the child's (often `0`) status with no output.
- **Exit-code fidelity** — `os.waitstatus_to_exitcode` propagates the child's code; a signal death (negative status) is normalized to the Unix `128 + signum` convention rather than a masked 8-bit value.
- **`execvp` failure is diagnosable** — the child writes `pty-capture: failed to execute …` to its PTY stderr (captured in the output file) and `os._exit(127)`, instead of leaving an empty file.
- **Output dir auto-created** — `os.makedirs(exist_ok=True)` on the out-path parent, so a missing directory doesn't raise `FileNotFoundError`.
- **Unix newlines** — the PTY's `\r\n` (ONLCR) is normalized to `\n` in the captured file.
- **`InterruptedError` → `continue`** (not `break`) — signals during `select`/`read` (e.g., SIGWINCH from terminal resize, SIGCHLD when child exits) retry the loop instead of terminating a healthy child.
- **Bounded termination ladder** — finally requests SIGTERM, waits up to `SIGTERM_GRACE_SEC` (5 s) polling with `WNOHANG`, then escalates to SIGKILL with a further bounded (`SIGKILL_REAP_SEC`, 2 s) `WNOHANG` reap — never an unbounded blocking wait. Worst case for a CLI that fully ignores SIGTERM is ~grace + reap, then exit.
- **Drain before close on every path** — the read loop drains on natural exit, and the cancellation (`SIGTERM`/`SIGHUP`) path drains the PTY again after reaping and before closing, so final diagnostics the CLI emits while handling the signal (and bytes buffered when `select` was interrupted) still reach `<out-path>`. Both drains are bounded (≤ 0.5 s).

**Things that do NOT work from non-TTY context:**
- `agy -p "..." > /tmp/out.txt` — 0 bytes
- `agy -p "..." | tee /tmp/out.txt` — same
- `script -q out.txt agy -p "..."` — errors `tcgetattr/ioctl: Operation not supported on socket`
- Bash `&` + watcher loop with `kill` at timeout — kills agy mid-drip

**It does work** in a true terminal (interactive shell) without the wrapper — that's why a human running `agy -p "..."` from Terminal.app sees output, while a script doesn't.

## Invocation patterns

### Slim-argv + workspace prompt file (recommended)

Put the full review/task spec in a PER-ROUND workspace markdown file — `.agy-prompt-${TICKET}r${ROUND}.md`, never a shared `.agy-prompt.md`, because two concurrent rounds sharing one prompt cross-wire prompt and transcript (deep review, P1) — then pass a short `-p` that points to it. Keeps argv small AND makes the prompt editable/version-controllable.

# 1. WRITE the prompt to the per-round workspace file with the **Write tool**, not a shell heredoc.
#    This skill grants `Edit(.agy-prompt-*.md)` (the Edit-form rule pre-approves all built-in
#    file-editing tools on that path, Write included; a Write-form rule is never consulted on
#    CLI >= 2.1.210); a `cat > … <<EOF` is a Bash redirect matching no Bash
#    grant, so it PROMPTS on every gate round — the exact reprompt the granted flow exists to avoid
#    (PR #63 recheck, P2). Same shape as codex-review's `Edit(.codex-prompt-*.md)` step. Give the file
#    an absolute plan reference so agy resolves it regardless of how it was launched, e.g.:
#
#        Write(.agy-prompt-${TICKET}r${ROUND}.md):
#          # Review task
#          Read $(pwd)/docs/planning/FEATURE_PLAN.md
#          and provide architectural assessment.
#          Verdict: APPROVE / APPROVE_WITH_NOTES / REQUEST_CHANGES.

```bash
# 2. Invoke agy through the shared PTY wrapper:
#    pty-capture.py <out-path> -- <command> [args...]
# --print-timeout 28m: agy's own default is 5m and a real plan review blows past it (see above).
# Wrapper 1800s (30m) > agy's 28m (1680s) ON PURPOSE. A wrapper cap BELOW the print-timeout SIGTERMs
# agy before its own timeout can fire, giving a masked exit 124 instead of agy's diagnosable
# `Error: timeout waiting for response`. Keep the wrapper ABOVE the print-timeout.
# MAJ-10 — staleness protection now comes from the PER-RUN ALLOCATED PATH, not from deleting a fixed
# one. Each round allocates its own transcript leaf, so a wrapper that never starts (agy absent / auth
# expired / a Bash-tool kill before pty-capture's finally-write) leaves that leaf ABSENT — never a STALE
# previous-round transcript that review-synthesis would read as THIS round's APPROVE. Absent (not stale)
# maps to MISSING -> the gate fails closed.
# DO NOT `rm -f` THE RESERVED LEAF. The allocator creates it 0-byte and pty-capture.py --allocated opens
# it WITHOUT O_CREAT; deleting it makes the final write fail on a missing file after the full ~25-minute
# review has already run, losing the round (PR #63 review, gaps 13-14). Retries must RE-ALLOCATE, which
# the wrapper now enforces by refusing a non-empty reserved leaf.
# SUPERSEDED — this raw form points agy at the WORKING TREE, which it can write to (COREDEV-2607).
# Use the GRANTED capture wrapper instead. It wraps exactly this pipeline, but binds the prompt and plan
# to the leaf, runs against a disposable detached checkout, and asserts the real tree is unchanged
# afterwards. Calling scripts/review/isolated-agy-review.sh directly — as this line used to — is neither
# granted by this skill nor complete: its plan operand is the fourth, and omitting it makes agy review
# the COMMITTED plan rather than the working-tree edits under review (PR #63 recheck, P2).
bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/capture-gemini-review.sh" \
    "$TICKET" "$ROUND" ".agy-prompt-${TICKET}r${ROUND}.md" "$PLAN" 1800
# -> the same UNLEASHED_TRANSCRIPT= marker; the capture lands in that allocated leaf and nowhere else.
```

### From an interactive terminal (no wrapper needed)

The drip animation renders to a real TTY directly. Read the output in your terminal; do NOT pipe to a file (the drip cannot capture through a pipe — that's the whole reason the PTY wrapper exists for non-TTY contexts).

> **Even here, `agy` can write to the workspace** (COREDEV-2607). Interactively that is at least
> *visible* — you are watching it — but for anything gate-bearing prefer the isolated wrapper, and
> check `git status` afterwards either way.

```bash
# Plan review — agy -p with workspace flag in same invocation.
# Run from the project root so "$(pwd)" resolves to the workspace.
# NOTE: this points agy at the real tree. For a gate round use the isolated wrapper above.
agy --add-dir "$(pwd)" --print-timeout 28m -p "Read and follow .agy-prompt-${TICKET}r${ROUND}.md"

# For record-keeping: use the PTY wrapper above instead of `> file`.
# A redirect like `agy ... > /tmp/review.md` will produce 0 bytes because
# the text-drip print mode cannot render to a non-TTY stream.

# Interactive follow-up
agy -i "Review the v3 plan and continue the discussion"
```

### Interactive slash commands (require `agy -i` real TTY)

Inside an `agy -i` session you can use:
- `/goal` — long-running task; tells the agent to be extra thorough and not stop until the goal is achieved.
- `/schedule` — recurring/timed instruction or one-time wake-up timer.
- `/grill-me` — interactive interview where agy asks YOU questions to clarify design.
- `/add-dir <path>` — register a workspace dir for the current session (persists differently than `--add-dir` CLI flag).

Slash commands are NOT available via `-p`; you must be inside an interactive `agy -i` session in a real terminal.

## Key flags (`agy --help`)

| Flag | Purpose |
|------|---------|
| `-p` / `--print` / `--prompt` | Non-interactive single prompt |
| `-i` / `--prompt-interactive` | Run initial prompt and stay interactive |
| `-c` / `--continue` | Resume the most recent conversation |
| `--conversation <ID>` | Resume specific conversation by ID |
| `--add-dir <path>` | Add workspace directory (repeatable, per-invocation) |
| `--print-timeout` | Print-mode wait timeout (default 5m) |
| `--sandbox` | Run with terminal restrictions enabled |
| `--dangerously-skip-permissions` | Auto-approve all tool permission requests |

**Removed/changed since the old gemini-cli:**
- `--model` → supported (session override; `-m` short form is NOT). `~/.gemini/settings.json` is the default when the flag is absent
- `-o / --output-format` → removed (always plaintext)
- `--include-directories` → renamed `--add-dir`

## Workflow

1. **Smoke-test:** `agy -p "ping"` → expect a `pong` (case-insensitive; the `!` is not guaranteed). If empty, re-login interactively.
2. **Check the model the GATE will use:** the wrapper passes `--model` explicitly, so read `MODEL=` in `scripts/review/isolated-agy-review.sh` (or your `MODEL` override) — currently `gemini-3.6-flash-high`. `~/.gemini/settings.json` governs only a bare `agy` invocation.
3. **Write the task** to a PER-ROUND workspace prompt file (`.agy-prompt-${TICKET}r${ROUND}.md`) with all context including absolute paths to any files agy must read.
4. **Invoke** via PTY wrapper from non-TTY contexts, or directly from a real terminal.
5. **Continue the conversation** with `agy -c` or `agy -i` for follow-up questions. Do not treat the first response as final.
6. **Capture output** — the isolated helper writes to the exact path in `GEMINI_TRANSCRIPT`. Read that
   allocated file back into context; do not reconstruct its name.
7. **Incorporate** the feedback into the plan; iterate until APPROVE or APPROVE_WITH_NOTES.
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

If `agy -p` is failing, check in order:

1. `agy --version` — should be ≥ 1.0.1 (2026-05-23). If older, `agy update`.
2. `agy -p "ping"` — should return a `pong` (case varies) in < 2 s in a real terminal.
3. `tail ~/.gemini/antigravity-cli/cli.log` — most-recent log entries; non-zero size = startup succeeded.
4. `ls -lt ~/.gemini/antigravity-cli/log/cli-*.log | head -3` — 0-byte logs = agy died at launch (often non-TTY drip issue, OR macOS sandbox/TCC permission denial).
5. `ls -lt ~/.gemini/antigravity-cli/conversations/ | head -3` — most-recent conversation file growing = agy IS doing work even if your stdout shows 0 bytes (TTY-drip issue, use PTY wrapper).

## One-shot preamble (REQUIRED for the automated `agy -p` path)

The two system prompts below are written for an **interactive** session (`agy -i`): they invite
clarifying questions and end with "Start by asking me…". The automated gate feeds them to a **one-shot**
`agy -p` through `pty-capture.py` — a reviewer following them verbatim replies with a *counter-question*,
producing a transcript `/unleashed-mail:review-synthesis` cannot parse, which burns a gate round.

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
be inferred from prose and confidence drops. The interactive prompts below are unchanged for `agy -i` use.

## Plan review — system prompt

> You are a senior software architect and development consultant acting as my conversational review partner. Your role is to thoroughly review and discuss development plans, architecture decisions, and implementation strategies BEFORE any code is written. You are NOT to write, modify, or suggest specific code changes — that work will be handled separately by Claude Code. Your job is purely analytical and advisory.
>
> When I share a development plan, feature spec, architecture document, or technical approach, review and discuss the following aspects conversationally:
>
> **Architecture & Design**
> - Overall system architecture and component relationships
> - Design pattern selection and appropriateness
> - Separation of concerns and modularity
> - Scalability considerations and potential bottlenecks
> - Data flow and state management approach
>
> **Framework & Technology Choices**
> - Framework suitability for the stated requirements
> - Dependency evaluation (maturity, maintenance status, licensing)
> - Compatibility between chosen technologies
> - Performance implications of the tech stack
>
> **Planning & Requirements**
> - Completeness of requirements and acceptance criteria
> - Edge cases, error scenarios, and failure modes not accounted for
> - Dependency mapping and sequencing of work
> - Risk identification and mitigation strategies
> - Scope clarity — anything ambiguous or underspecified
>
> **Code Quality & Standards**
> - Adherence to modern best practices as documented in current official documentation (always reference Context7 for the latest documentation on any frameworks, libraries, or tools being discussed)
> - API design and contract clarity
> - Security considerations and potential vulnerabilities
> - Testing strategy and coverage approach
> - Accessibility and compliance requirements where applicable
>
> **Developer Experience & Maintainability**
> - Naming conventions and organizational structure
> - Documentation needs
> - CI/CD and deployment considerations
> - Logging, monitoring, and observability planning
>
> Important guidelines:
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

> **Interactive (`agy -i`) only.** On the automated one-shot `agy -p` path this opener does NOT apply —
> the One-shot preamble above overrides it (review the given path immediately; end with `VERDICT:`).

## Debug review — system prompt

> You are a senior debugging specialist and codebase investigator acting as my conversational partner for diagnosing issues and bugs. Your role is to help me READ, UNDERSTAND, and REASON about code to identify root causes and formulate fix strategies. You are NOT to write, modify, or suggest specific code patches — all code changes will be handled separately by Claude Code. Your job is to help me think through the problem and arrive at a clear diagnosis and action plan.
>
> When I share a bug report, error log, unexpected behavior, or code snippet for investigation, work through the following conversationally:
>
> **Issue Characterization**
> - Clarify the expected vs. actual behavior
> - Identify whether the issue is deterministic or intermittent
> - Establish the scope — is this isolated or potentially systemic
> - Determine when the issue was introduced if possible (recent change, always existed, environmental)
>
> **Codebase Analysis**
> - Trace the execution path related to the issue
> - Identify relevant components, modules, and their interactions
> - Examine data flow, state transitions, and side effects along the path
> - Review error handling and boundary conditions in the affected area
>
> **Root Cause Investigation**
> - Develop and evaluate hypotheses for the root cause
> - Identify the most likely cause and explain the reasoning
> - Consider secondary or contributing factors
> - Check for related issues that may share the same root cause
>
> **Context & Best Practices Validation**
> - Always reference Context7 for the latest documentation on any frameworks, libraries, or APIs involved in the issue. Verify that current usage aligns with documented behavior and best practices — do not rely on potentially outdated training data.
> - Identify if the issue stems from deprecated patterns, misused APIs, or deviation from documented conventions.
> - Note if the relevant library or framework version has known issues or breaking changes.
>
> **Fix Strategy & Prevention**
> - Describe the conceptual approach to fixing the issue (without writing the fix)
> - Identify what areas of the codebase would need to change
> - Suggest what tests should be added or updated to cover this case
> - Recommend any preventive measures to avoid similar issues (architectural, process, or tooling)
>
> Important guidelines:
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

> **Interactive (`agy -i`) only.** On the automated one-shot `agy -p` path this opener does NOT apply —
> the One-shot preamble above overrides it (investigate the given issue immediately; end with `VERDICT:`).
