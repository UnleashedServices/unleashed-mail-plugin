---
name: review-synthesis
description: Synthesize the two plan-review transcripts (gemini + codex) into one auditable combined-verdict block. Read-only; run AFTER both /gemini-review and /codex-review transcripts are captured, before implementation begins.
allowed-tools: Read, Grep, Bash
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
`/codex-review`):

- gemini → `/tmp/agy-out.txt`  (Antigravity `agy`, free-form plaintext)
- codex  → `/tmp/codex-out.txt` (`codex exec`, free-form plaintext)

Those are the default paths the two review skills write. If the caller specifies custom paths in the
prompt (e.g. "synthesize `/tmp/a.txt` and `/tmp/b.txt`"), read those instead.

> **Scope — keep this distinct from the code-review synthesizer.** This is the **plan-review**
> synthesizer: **2 prose transcripts**, before implementation. It is deliberately separate from the
> code-review MCP synthesizer (`mcp/review-synthesizer/`, tool `synthesize_review`), which merges **5
> JSON findings arrays** after implementation and uses a different verdict vocabulary
> (`APPROVE_WITH_SUGGESTIONS` / `NEEDS_DISCUSSION`). **Do not unify the two enums.** This skill's verdict
> set is `APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES | DISAGREEMENT`.

## Inputs

1. Read `/tmp/agy-out.txt` (gemini) and `/tmp/codex-out.txt` (codex). Treat a **missing, empty, or
   0-byte** file as **"reviewer did not return"** — never as silent approval.
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

After emitting the block, **persist the Combined verdict as a plan-digest-bound artifact** so
`implement`'s Design Gate can verify it deterministically (and detect an approve-then-edit). Pass the
plan that was reviewed plus each reviewer's status + transcript:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/review-verdict.py" write \
    --plan docs/planning/FEATURE_NAME_PLAN.md \
    --verdict <COMBINED_VERDICT> \
    --reviewer gemini=<GEMINI_STATUS>:/tmp/agy-out.txt \
    --reviewer codex=<CODEX_STATUS>:/tmp/codex-out.txt \
    --reviewed-sha256 "$REVIEWED_PLAN_SHA256" \
    --created-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

> **Bind the approval to the bytes that were REVIEWED, not the bytes at write time.** The digest is
> computed at `write`, which runs AFTER the reviews — so a plan edited between review and write would
> record an approval for content the reviewers never saw ("review v1, edit to v2, write approves v2").
> **Snapshot the plan's digest BEFORE dispatching the reviews** and pass it as `--reviewed-sha256`:
> ```bash
> # at the START of the gate, before /gemini-review + /codex-review run:
> REVIEWED_PLAN_SHA256="$(shasum -a 256 docs/planning/FEATURE_NAME_PLAN.md | cut -d' ' -f1)"
> ```
> `write` aborts if the plan has changed since. It's optional (backward-compatible), but omitting it
> reopens the review→write window that `verify`'s post-write digest check cannot see (#44 review §4).

For a reviewer that did not return, record `<reviewer>=MISSING` **without** a `:transcript` path
(the artifact fails closed — `implement`'s verify blocks on a non-approving verdict), e.g. `--reviewer codex=MISSING`.

This records the plan's **raw-byte SHA-256** (+ the two transcript digests) in a private `.verdicts/`
dir beside the plan (git-ignored session state). It writes the artifact for ANY combined verdict —
`implement` is what refuses to proceed on a non-approving one, so the audit trail is complete either
way. If `${CLAUDE_PLUGIN_ROOT}` is unset, use the repo-relative `scripts/review-verdict.py`.

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
