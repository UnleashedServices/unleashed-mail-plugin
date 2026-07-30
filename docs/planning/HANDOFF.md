# Session handoff — unleashed-mail plugin, Opus-5 campaign

**Written:** 2026-07-30 · **Branch:** `claude/plugin-opus5-review-xs81o0` · **HEAD:** `48d60c2` ·
**Version:** `2.6.4` · **Tree:** clean · **2 commits ahead of `origin/main`**, both pushed.

Paste the **Prompt** section below into a new session. Everything after it is reference.

---

## Prompt

> Continue the unleashed-mail plugin campaign. Work in the existing worktree
> `/Users/nick/Developer/Mail/unleashed-mail-plugin/.claude/worktrees/opus5-review` (branch
> `claude/plugin-opus5-review-xs81o0`, HEAD `48d60c2`, v2.6.4) — **do not** flip the main checkout's
> branch and do not create a new worktree.
>
> Read `docs/planning/HANDOFF.md` first, then `~/.claude/projects/.../memory/opus5-campaign-state.md`
> and `memory/precompact-hook-does-not-fire.md`.
>
> **Immediate task:** a COREDEV-2497 round-3 dual gate was launched in the previous session and its
> transcripts land at `/tmp/rev/2497r3-codex.txt` and `/tmp/rev/2497r3-agy.txt` (the prompt is
> `.agy-prompt-2497r3.md`, gitignored). Check whether they completed:
>
> ```bash
> ls -la /tmp/rev/2497r3-*.txt
> grep -aE '^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$' /tmp/rev/2497r3-codex.txt | tail -1
> grep -aE '^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$' /tmp/rev/2497r3-agy.txt | tail -1
> ```
>
> If both are present, triage the findings **by execution** — verify every claim before acting on it;
> across three rounds roughly half of all reviewer findings needed correcting, in both directions. If a
> transcript is missing or under ~1 KB, that is a **failed run, not a review** — re-run that reviewer.
>
> Then, in order: re-run the **COREDEV-2605** gate (round 1 was killed mid-round), draft the
> **COREDEV-2617** plan, and implement 2497 once it gates. Never merge to `main` without me saying so.

---

## Where every ticket stands

| ticket | state | next action |
|---|---|---|
| **2583 / 2602 / 2597 / 2598 / 2600 / 2603 / 2607 / 2609** | **DONE — merged to `main` as `ff83f02` (PR #62), v2.6.0→v2.6.4** | none |
| **2606** — PreCompact snapshot inert | root-caused and install fixed; **hook dispatch still unproven** | see *Open questions* |
| **2497** — forgeable verdict artifact | plan **rescoped** to §4.1+§4.2 at `48d60c2`; **round-3 gate running** | triage the round-3 transcripts |
| **2605** — narrow AGENT_CONTRACTS §13 | plan drafted; **round 1 killed mid-round.** gemini already returned `REQUEST_CHANGES` (preserved: `/tmp/rev/agy-2605r1.txt`, 2,798 B); codex never finished | re-freeze, re-run both. Prompt: `/tmp/rev/.agy-prompt-2605r1.md` |
| **2617** — plugin state splits across two base dirs | **filed, High, no plan yet** | draft the plan |
| **2618** — verdict-token cross-check | filed (split from 2497), no plan | after 2497 |
| **2619** — per-run transcript paths | filed (split from 2497), no plan | **before** 2497 implements |
| **2604** | blocked on 2605 landing | wait |
| **2599** evals · **2584/2585** | open / paused by decision | — |

## Locked maintainer decisions — do not re-litigate, do not re-ask

`effort: xhigh` everywhere (all 21 agents + 21 skills; cost accepted) · three model tiers
(`opus`/`inherit`/`sonnet`) · direct Anthropic API only · `opus[1m]` must stay legal in the validator ·
CLI pin **2.1.220** · autonomous mode is user-invoked only and **PAUSED** · compaction design is the
A+C hybrid (`journal.jsonl` + `live-state.json`), paused · **2497 is split three ways** (2026-07-30).

**Merging to `main` requires an explicit instruction from the maintainer.** Drive a PR to ready, then ask.

## Process that is mandatory here

- Every feature/refactor gets a `docs/planning/*_PLAN.md` reviewed by **both** `/unleashed-mail:gemini-review`
  (`agy`, gemini-3.1-pro) and `/unleashed-mail:codex-review` (`codex exec -c model_reasoning_effort=xhigh
  -s read-only`), then `/unleashed-mail:review-synthesis`. Route non-TTY runs through
  `scripts/pty-capture.py`.
- **Freeze the plan during a round** (`AGENT_CONTRACTS.md` §2 step 0b). A reviewer once refused a round
  because the author edited the plan mid-review.
- Run `agy` through **`scripts/review/isolated-agy-review.sh`** — it is not read-only and once
  *implemented* a plan it was reviewing (6 shipped scripts modified). The wrapper uses a disposable
  detached checkout and fails the round on any real-tree mutation.
- Every commit references a `COREDEV-XXXX` key. Validate before committing — the seven commands are in
  `CLAUDE.md`; the pre-commit hook runs a subset.
- Context7 is mandatory for any library/framework/CLI lookup.

## Invocation details that cost real rounds to learn

- `agy -p` defaults to `--print-timeout 5m` and **dies** on long plan reviews → pass `--print-timeout 18m`
  (the wrapper does).
- `codex` needs `-c model_reasoning_effort=xhigh` explicitly; it runs ~12 min, so give `pty-capture.py`
  `--timeout 900`+. Exit 124 means the *wrapper* timed out — **not** a reason to downgrade to `high`.
- **A tiny transcript is a failure, not a review.** Byte-count first.
- **Never grep `VERDICT:` loosely** — it matches the prompt's own echoed template in a timed-out
  transcript and reads as a real verdict. Always anchor:
  `grep -aE '^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$' … | tail -1`
- Concurrency is fine; **timeout is the real variable**. Give overlapping runs distinct out-paths.
- **Write transcripts to `/tmp/rev/<ticket>r<round>-<reviewer>.txt`, never the shared fixed paths.** See
  the next section for why.

## The two hardest-won lessons

**1. Verify which file you are measuring.** Round 2 of the 2497 plan reported its headline number from
`/tmp/codex-out.txt`, which by then held a **LumaWake** plan review — 638 matches for `lumawake`, zero for
`COREDEV-2497` — because another project's gate round overwrote the shared fixed path. The real transcript
is `/tmp/rev/2497r1-codex.txt` at **512,723 bytes**. I then "corrected" 512,723 → 769,988, inverting the
truth, and **both reviewers assessed the plan without catching it.** Grep evidence for the ticket key
before building an argument on it. This is COREDEV-2619's justification, produced by accident.

**2. A green test suite says nothing about whether the host runs the code.** `bash scripts/test-hooks.sh`
passed 304 tests throughout the ~2 weeks the plugin's hooks were **entirely inert** in this repo, because
the harness drives the scripts directly via stdin. "The scripts are correct" and "the host invokes them"
are separate claims.

## Method that keeps paying

- **Execute, don't assert** — and check *attribution* separately from *mechanism*. Reviewers reproduce
  defects correctly while getting ownership, line numbers and counts wrong. codex was wrong twice on the
  same upstream line number in opposite directions; gemini invented a proof case the plan never contained.
- **Seven wrong citations across three drafts**, all the same shape: a number taken from a `grep -n`/`sed`
  offset instead of from the file. **Print the line you are citing, from the file, before writing it down.**
- **Inert gates are the recurring failure** — this campaign shipped or nearly shipped seven. The newest: a
  16-case proof set that a validate-then-reopen implementation passes while keeping the exact race the plan
  forbids in four places. Closing it needed a *named seam* (`_open_regular_fd`); round 2 described the
  split but never named it, so nothing could pin it.
- **A mutation that does not apply is indistinguishable from a test that does not work.** Verify the edit
  landed before believing green.
- **Escalating round counts mean stop iterating and sweep the class.** 2497 went 4 → 8 → 37 findings.
  Same signal as 2597, where rounds 3 and 4 each found more redactor divergences than the previous round
  claimed were possible.

## Open questions I could not settle

1. **Do the plugin's hooks now fire in this repo?** The install is correct (`scope=user`, `version=2.6.4`,
   confirmed in `~/.claude/plugins/installed_plugins.json`) and the plugin's agents/skills/MCP tools load.
   But `stop_hook_summary.hookInfos` still lists only Bartender and GitKraken, and the session I checked
   had **resumed** rather than started fresh, so it was carrying pre-install hook config. **Test in a
   genuinely new session**, then look for fresh files under
   `~/.claude/plugins/data/unleashed-mail-npranson-unleashed-mail-plugin/` — **not**
   `~/.claude/unleashed-mail/`, which is the fallback base and is what misled me for several turns.
2. **PreCompact has never produced a snapshot anywhere, ever** — including in the app repo where hooks
   demonstrably do fire. Confounded by COREDEV-2617. A real compaction in a plugin-loaded session settles
   it; needs no action.
3. **Most hooks write only conditionally** (Swift edits, builds, blocks, denials) — none of which occur in
   this repo — so **their silence proves nothing**. Only PreCompact writes unconditionally. Do not infer
   "hooks are dead" from a quiet state dir.

## Repo facts worth not rediscovering

- `origin` is `UnleashedServices/unleashed-mail-plugin`. The marketplace source `npranson/unleashed-mail-plugin`
  is a **transfer redirect** to it, so merging to `origin/main` does reach the install.
- Counts are `21/21/0/1` (agents/skills/commands/MCP) and `validate-version-sync.sh` enforces
  `plugin.json` == README H1 == newest What's-New == counts.
- Test baselines at `48d60c2`: `test-hooks.sh` **304**, synthesizer **222**, scripts **312**, hook events
  **10**. Floors, not equalities.
- `~/.claude/plugins/data/unleashed-mail-*/` is the real plugin data dir. `${CLAUDE_PLUGIN_DATA:-$HOME/.claude/unleashed-mail}`
  is the expansion — and the env var is set **only for hook invocations**, which is COREDEV-2617.
