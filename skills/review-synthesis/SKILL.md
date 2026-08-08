---
name: review-synthesis
description: Synthesize the two plan-review transcripts (gemini + codex) into one auditable combined-verdict block. Source-preserving (never edits the plan or sources) but persists the digest-bound Combined verdict under .verdicts/; run AFTER both /gemini-review and /codex-review transcripts are captured, before implementation begins.
allowed-tools: Read, Grep, Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/persist-verdict.sh *)
---

# Plan-Review Synthesis

A **source-preserving** skill that combines the two plan-review transcripts into a single auditable
record — the proof that the `AGENT_CONTRACTS.md §2` "both reviewers must return APPROVE / APPROVE_WITH_NOTES"
gate passed, with any disagreement **surfaced** rather than averaged away. It runs nothing and gates
nothing automatically; it produces a Markdown block for the human running the gate.

> **Not read-only in the filesystem sense.** It never edits the plan, the gates, or any source, but it
> DOES write session state: it persists the plan-digest-bound Combined-verdict artifact under the plan's
> `.verdicts/` dir (step below). "Source-preserving, session-state-writing" is the accurate description;
> the earlier "read-only" label was wrong about the write (full review, #41).

Run it **after** both review transcripts are captured (see `/gemini-review` and
`/codex-review`). Supply the two allocated paths explicitly; there are no shared default paths:

```text
/unleashed-mail:review-synthesis \
  --reviewer "gemini=<STATUS>:<gemini-allocated-path>" \
  --reviewer "codex=<STATUS>:<codex-allocated-path>"
```

Each value after `--reviewer` is one opaque argument. Split it at the first `=` into name/remainder,
then at the first `:` into status/path. The complete remainder after that first `:` is the allocated
path: do not split it again, trim it, resolve it independently, or reconstruct it from ticket/round.

> **Scope — keep this distinct from the code-review synthesizer.** This is the **plan-review**
> synthesizer: **2 prose transcripts**, before implementation. It is deliberately separate from the
> code-review MCP synthesizer (`mcp/review-synthesizer/`, tool `synthesize_review`), which merges **5
> JSON findings arrays** after implementation and uses a different verdict vocabulary
> (`APPROVE_WITH_SUGGESTIONS` / `NEEDS_DISCUSSION`). **Do not unify the two enums.** This skill's verdict
> set is `APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES | DISAGREEMENT`.

## Inputs

1. Parse the two explicit `--reviewer` arguments using only their first structural `=` and `:`
   delimiters, then read those exact path remainders. Treat a **missing, empty, or 0-byte** allocated file
   as **"reviewer did not return" (`MISSING`)** — never as silent approval. Still confirm each transcript
   is **this round's** review (it names the current plan / matches the feedback you just sent); if you
   cannot confirm it is fresh, treat it as MISSING and re-run the review.
2. From each transcript, extract the reviewer's verdict token. Each review skill asks the reviewer to end
   with an explicit `VERDICT:` / `Verdict:` line — prefer that. If it is absent, infer the verdict from
   the prose **conservatively**: when ambiguous, pick the **more conservative** verdict and lower the
   confidence.

## Verdict normalization

Map each reviewer's raw verdict to one canonical token:

| Raw (any reviewer / CLI) | Canonical |
|---|---|
| `APPROVE`, "looks good", "ship it" | `APPROVE` |
| `APPROVE_WITH_NOTES`, `APPROVE_WITH_NITS`, "approve with a couple of nits/notes" | `APPROVE_WITH_NOTES` |
| `REQUEST_CHANGES`, `REQUEST CHANGES`, "needs changes", "blocking" | `REQUEST_CHANGES` |
| missing / empty / unparseable transcript | `MISSING` |

> The `agy`/gemini CLI emits `APPROVE_WITH_NITS`; the project's canonical gate term (CLAUDE.md,
> `AGENT_CONTRACTS.md`) is `APPROVE_WITH_NOTES`. **Normalize `NITS → NOTES`.**

## Combined-verdict rule (apply in priority order — first match wins)

1. **Either or both transcripts `MISSING`** → you **cannot** claim `APPROVE`:
   - **Both** missing → `REQUEST_CHANGES` (the gate did not run at all).
   - One missing, the other `REQUEST_CHANGES` → `REQUEST_CHANGES`.
   - One missing, the other approves (`APPROVE`/`APPROVE_WITH_NOTES`) → `DISAGREEMENT` (a lone approval can't carry the gate).
   Always **low** confidence, with an explicit note naming the reviewer(s) that did not return.
2. **One side approves (`APPROVE`/`APPROVE_WITH_NOTES`) and the other is `REQUEST_CHANGES`** →
   `DISAGREEMENT`. Surface both positions; **do not average** to a middle verdict.
3. **Both `REQUEST_CHANGES`** → `REQUEST_CHANGES`.
4. **Both approve** (`APPROVE`/`APPROVE_WITH_NOTES`) → `APPROVE_WITH_NOTES` **if either reviewer had
   notes**; otherwise `APPROVE`.

## Output (emit exactly this shape; plain Markdown, no emoji)

```markdown
## Plan-Review Synthesis

**Combined verdict:** APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES | DISAGREEMENT

### Agreement
- [points BOTH reviewers raised or endorsed]

### Disagreement
- [points where the reviewers diverge — name which reviewer took which side; leave empty only if they fully agree]

### Minority report
- [a concern raised by ONLY one reviewer that you are NOT folding into the combined verdict but the human should see]

### Risk register

| Risk | Raised by | Likelihood | Mitigation |
|---|---|---|---|
| … | gemini / codex / both | low/med/high | … |

### Conditions that would change the recommendation
- [what evidence or change would flip the verdict — e.g. "codex blocker X addressed", "missing transcript recaptured"]

### Confidence
- **[high | medium | low]** — [one line; low whenever a transcript was MISSING or a verdict was inferred from ambiguous prose]
```

## Persist the verdict (bind it to the plan)

> **The artifact is written beside the plan in the CURRENT checkout, and it does not travel.**
> `<plan-dir>/.verdicts/` is git-ignored at the repo root and self-ignored by a `*` `.gitignore`
> that `_ensure_secure_dir` writes inside it on purpose, so it is never committed and a fresh
> clone or `git worktree add` will not have it. Synthesize in the same worktree you intend to
> implement in (`AGENT_CONTRACTS.md` §2 step 00). CI and a second developer cannot verify an
> approval at all — that is by design, not a gap to work around.

After emitting the block, **persist the Combined verdict as a plan-digest-bound artifact** so
`implement`'s Design Gate can verify it deterministically (and detect an approve-then-edit).

**Prerequisite — the reviewed digest was snapshotted at gate LAUNCH.** `create-feature-plan` runs
`review-verdict.py snapshot --plan …` *before* dispatching `/gemini-review` + `/codex-review`, writing
a git-ignored `.reviewed-sha256` sidecar beside the plan. That snapshot binds the approval to the bytes
the reviewers actually saw. It CANNOT be a shell variable — each skill step is a separate tool
invocation, so a `REVIEWED_PLAN_SHA256=…` shell-local would be empty here (#44 review §4; COREDEV-2499).
If no valid pre-review snapshot exists — none was taken, or the plan was edited AFTER the reviews ran —
do **NOT** snapshot the current bytes here and continue: that would bind the approval to bytes the
reviewers never saw. Instead **re-run `/gemini-review` + `/codex-review` on the current plan** (with a
fresh `snapshot` taken before dispatch), then synthesize those transcripts. An approval is only valid for
the exact plan the reviewers actually reviewed.

Then persist — bind `PLAN_PATH`, `COMBINED_VERDICT`, `GEMINI_REVIEWER_SPEC`, and
`CODEX_REVIEWER_SPEC` to the current synthesis inputs in one Bash invocation. Each reviewer spec must
carry the CANONICAL status and the exact transcript-path remainder supplied to this skill — that is,
rebuild it as `<name>=<canonical status>:<the original path, unchanged>`.

> **`APPROVE_WITH_NITS` must be canonicalized in the spec too, not only in the synthesis** (PR #63
> recheck). `agy` emits `NITS`, the normalization table above converts it for the combined verdict, and
> passing the reviewer argument through byte-for-byte then handed `persist-verdict.sh` a token it does
> not accept — `invalid reviewer status`, aborting an otherwise valid dual approval at the last step.
> The path remainder is still passed unchanged, because it is the thing the gate binds to. `scripts/review/persist-verdict.sh` parses only the
first delimiters, classifies an absent or empty allocated leaf as `MISSING`, and otherwise passes the
spec through unchanged — it accepts `APPROVE`, `APPROVE_WITH_NOTES`, `REQUEST_CHANGES` and `MISSING`
only, which is why the canonicalization above has to happen before it is called. `write` auto-reads the snapshot sidecar and aborts if the plan changed since, so
no `--reviewed-sha256` argument is needed in the normal flow.

This used to be the same logic pasted inline here, in `brainstorm`, and (in capture form) in the two
review skills. Each copy defined functions and branched, so it matched none of those skills'
`allowed-tools` Bash shapes — the one block every gate round must run prompted for permission every time,
which is the reprompting problem `MIN-27` records as fixed and the pressure toward blanket `Bash` grants
(PR #63 review, gaps 7-9 and bot thread 7). As one committed script it is covered by the
`Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)` grant above, and the rule lives in one place rather
than in copies that drift — the inline copy had already drifted, rejecting the bare `<reviewer>=MISSING`
form this same file documents below as the unavailable-reviewer recovery path.

```bash
# COREDEV2619_SYNTHESIS_PERSIST_BEGIN
bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/persist-verdict.sh" \
    --plan "$PLAN_PATH" \
    --verdict "$COMBINED_VERDICT" \
    --reviewer "$GEMINI_REVIEWER_SPEC" \
    --reviewer "$CODEX_REVIEWER_SPEC"
# COREDEV2619_SYNTHESIS_PERSIST_END
```

`write` aborts if the plan changed since the snapshot. An **APPROVING** verdict REQUIRES a reviewed-digest
binding: if no snapshot sidecar exists (and no `--reviewed-sha256` is passed) `write` FAILS CLOSED rather
than record an approval bound to unreviewed bytes — so the snapshot in `create-feature-plan` is
mandatory, not optional, for an approval. You may still pass `--reviewed-sha256 <digest>` explicitly to
override the sidecar (e.g. a caller that tracks the digest itself); a passed-but-EMPTY
`--reviewed-sha256 ""` fails loudly rather than silently skipping the binding.

For a reviewer that did not return, record `<reviewer>=MISSING` **without** a `:transcript` path
(the artifact fails closed — `implement`'s verify blocks on a non-approving verdict), e.g. `--reviewer codex=MISSING`.

This records the plan's **raw-byte SHA-256** (+ the two transcript digests) in a private `.verdicts/`
dir beside the plan (git-ignored session state). It writes the artifact for ANY combined verdict —
`implement` is what refuses to proceed on a non-approving one, so the audit trail is complete either
way. If `${CLAUDE_PLUGIN_ROOT}` is unset, use the repo-relative
`scripts/review/persist-verdict.sh` — **not** `review-verdict.py write` directly. Calling the writer
skips the MISSING classification that makes an absent or empty transcript fail closed, which is the
whole reason this step goes through the helper (deep review, P2).

## Guardrails

- **No PII.** Plan transcripts may quote email addresses, subjects, or message bodies. Reference findings
  by **location/topic** (file, area, concern) — never echo an address, subject, or body into the block.
- **Partial capture is the known failure mode.** A short or 0-byte transcript means the reviewer did not
  return; treat it as `MISSING` (rule 1), never as a silent `APPROVE`.
- **Surface, don't average.** `DISAGREEMENT` is a real verdict — keep both reviewers' positions visible
  rather than collapsing a one-approve / one-reject split into either extreme.
- **Never edits the plan or gates.** This skill reads the two transcripts, emits one block, and persists
  the verdict artifact beside the plan (the `.verdicts/` handoff). It never edits the plan itself,
  re-runs a reviewer, or decides to proceed — `implement`'s Design Gate is the only consumer that gates.
