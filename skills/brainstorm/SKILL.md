---
name: brainstorm
description: Brainstorm and design a feature — research modern approaches, then pressure-test with enterprise and SMB stakeholder personas before planning
argument-hint: [feature description]
# Edit(docs/planning/**), NOT Write(...): since Claude Code 2.1.210 file-permission rules are consulted
# for `Edit(path)`/`Read(path)` only — a `Write(path)` rule is accepted but never consulted, so the
# previous Write-form grant was dead and plan writes re-prompted (2026-08-17 audit, AF-27).
# disallowed-tools carves the gate's verdict state out of that grant: gitignore `**` matches
# dot-directories, so an effective Edit(docs/planning/**) would otherwise pre-approve direct writes to
# docs/planning/.verdicts/ — the artifact `resolve-plan-gate.sh verify` trusts. Verdict artifacts are
# written ONLY through the granted persist-verdict.sh entrypoint (a Bash subprocess, which file rules
# do not govern); Claude editing them directly must prompt (2026-08-17 audit, AF-8).
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch, AskUserQuestion, Edit(docs/planning/**), Agent(enterprise-stakeholder), Agent(unleashed-mail:enterprise-stakeholder), Agent(smb-entrepreneur), Agent(unleashed-mail:smb-entrepreneur), Agent(jira-manager), Agent(unleashed-mail:jira-manager), Agent(modern-standards-planner), Agent(unleashed-mail:modern-standards-planner), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/snapshot-plan.sh *), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/persist-verdict.sh *)
disallowed-tools: Edit(docs/planning/.verdicts/**)
---

# Feature Brainstorm: $ARGUMENTS

You are starting the design phase for a new feature in UnleashedMail.

**Do NOT write any code yet.** This is design + research only.

## Step 1: Jira Ticket Setup

Launch the **`jira-manager`** agent in parallel with Step 2:
> Check if a Jira ticket exists for this feature. If not, create one (Task type).
> Associate with parent Epic if one exists. Log that brainstorming has begun.

## Step 2: Understand the Request

Restate the feature request in your own words. Ask clarifying questions if ambiguous. Identify:

- **Who** benefits from this feature (end user, developer, both)?
- **What** does it do at a high level?
- **Where** in the app does it live (which views, which layer)?
- **Why** is it needed (user pain point, missing capability)?
- **Which providers** does it affect (Gmail, Graph, both)?

## Step 3: Explore the Codebase

Use Read, Grep, and Glob to understand the current state:

- What existing code is related to this feature?
- What patterns are already established?
- Are there similar features we can model this after?
- What's the current state of provider parity in the affected area?

## Step 4: Design Proposal

Present a concise design covering:

1. **Data model changes** — new GRDB records, migrations, or modifications
2. **Service layer** — new protocols/implementations needed (both providers)
3. **ViewModel** — new or modified ViewModels
4. **View** — UI changes (SwiftUI views, WKWebView changes)
5. **Provider parity** — what both Gmail and Graph need, and any known asymmetries

## Step 4b: Decision-Support Options (for forks)

**Only when the design has a genuine architectural fork** — a point where two or more materially
different approaches are viable and the choice shapes the rest of the plan (sync strategy, storage
shape, provider mechanism, migration timing). Skip this step entirely for a linear design with one
obvious approach; do **not** manufacture a fork.

Present **2–4 options** in a comparison table, then call **`AskUserQuestion`** to record the chosen
fork **before** the Step 9 plan document is written — so the plan commits to a decided approach, not an
open question. No emoji; use the project's vocabulary (`**Pros**` / `**Cons**` / `**(Recommended)**`).

**Comparison table** — one column per option, at least these rows:

| Dimension | Option A | Option B |
|---|---|---|
| **Summary** | one line | one line |
| **Pros** | … | … |
| **Cons** | … | … |
| **Parity-Impact** | what Gmail needs · what Graph needs · any asymmetry | … |
| **Effort** | S / M / L | S / M / L |
| **Reversibility** | easy / moderate / hard to undo later | … |
| **Best for** | when this option wins | … |

Then a recommendation line — **`Option X (Recommended)`** — one sentence on why, honest about the
trade-off being accepted.

**Parity-Impact is mandatory — never drop that row.** Every sync / compose / push / storage fork has a
provider-parity dimension (CLAUDE.md). Gmail and Graph share one **Parity-Impact** cell per option (not
separate columns), so a "Gmail-only quick win" must still show its Graph cost (e.g. a tracked
`// TODO: PARITY` stub) **inside that cell**, rather than omitting the other provider's analysis.

**Worked examples (real unleashed forks):**

- **Incremental sync:** Gmail `historyId`-incremental vs full resync. Parity-Impact: Graph's counterpart
  is `deltaLink` delta queries — the choice must land for **both** providers.
- **Push vs poll:** Gmail Pub/Sub push vs Graph webhook subscription / delta-poll — different
  freshness/cost trade-offs per provider.
- **Compose editor:** `NativeRichTextEditor` (macOS 26+) vs `HTMLWebViewEditor` (≤25). **This is
  OS-gated, not a peer choice** — present it as a hard precondition (the native editor only exists on
  macOS 26+; the WebKit editor is the floor on ≤25), never as two interchangeable alternatives on
  macOS 25.
- **Migration timing:** CRITICAL (runs at startup, blocks UI) vs DEFERRABLE (background after UI loads).
  **Default to DEFERRABLE** (CLAUDE.md "defer unless proven critical"); starring CRITICAL requires
  explicit justification that the data is needed before first paint.

**Record the decision:** call `AskUserQuestion` with the option labels — lead with the recommended one,
suffixed `(Recommended)`. Carry the chosen option, **and** the rejected alternatives as "considered and
why not," into the Step 8 summary and the Step 9 plan document.

## Step 5: Research Modern Standards

Launch the **`modern-standards-planner`** agent to research current best practices for every technology area this feature touches. The planner will:

- Use Context7 to look up latest GRDB, MSAL, SwiftUI docs
- Web search for latest Gmail API and Graph API recommendations
- Check for deprecated APIs in the proposed approach
- Identify modernization opportunities

Wait for the planner's research summary before finalizing.

## Step 6: Stakeholder Review

Launch both persona agents **in parallel** to pressure-test the design:

**Agent: `enterprise-stakeholder`**
> Review this feature proposal from an enterprise deployment perspective.
> Evaluate for: compliance (HIPAA, SOC 2, PIPEDA), admin control, scale
> (50k emails, 200 labels, shared mailboxes), SSO/MDM, integration risks,
> and security. Here is the proposed design: [summary from Steps 2-4]

**Agent: `smb-entrepreneur`**
> Review this feature proposal from a small business power-user perspective.
> Evaluate for: daily workflow impact (150 emails/day, 3 accounts), speed,
> keyboard-first UX, client communication edge cases, multi-device sync,
> cost justification, and competitive comparison. Here is the proposed design:
> [summary from Steps 2-4]

Collect both assessments and incorporate their findings:
- Enterprise BLOCK or SHIP WITH CONDITIONS items become hard requirements
- SMB DEAL BREAKER items become hard requirements
- Enterprise NEEDS WORK and SMB NICE TO HAVE items become backlog candidates
- Missing requirements from both personas get added to the spec

## Step 7: Edge Cases & Risks (Consolidated)

Merge technical risks with stakeholder findings:

- What could go wrong technically? (offline, API quotas, provider limitations)
- What could go wrong for enterprise? (compliance gaps, admin blind spots, scale failures)
- What could go wrong for SMB? (workflow disruption, speed regression, missing integrations)
- Security considerations from both perspectives

## Step 8: Summary for Approval

Present the design as a short spec incorporating:

- Design decisions with rationale
- Modern standards findings (from planner)
- Enterprise impact assessment verdict and key conditions
- SMB reality check verdict and key expectations
- Provider parity plan
- Estimated task breakdown (S/M/L per task)
- Dual implementation impacts (native + WebKit compose, etc.)
- Requirements added from stakeholder review

## Step 9: Create Planning Document (Mandatory)

Per project CLAUDE.md, create `docs/planning/FEATURE_NAME_PLAN.md` using the template
from the `modern-standards-planner` agent. This is non-negotiable — no implementation
without a tracked plan.

Update the Jira ticket with a link to the plan document.

## Step 10: Plan Review Gate (Mandatory — do this BEFORE `/implement`)

`/unleashed-mail:implement` runs a **deterministic** Design Gate: it calls
`scripts/review-verdict.py verify` and refuses to write code unless an **approving, plan-digest-bound
Combined-verdict artifact** exists. Going straight from here to `/implement` therefore fails with
`GATE FAILED — no Combined-verdict artifact`. Walk the gate first:

1. **Snapshot the reviewed digest BEFORE dispatching the reviews** — this binds the eventual approval to
   the bytes the reviewers saw, and an **APPROVING** `write` now REQUIRES it (fails closed otherwise):
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/snapshot-plan.sh" docs/planning/FEATURE_NAME_PLAN.md
   ```
2. **Review the plan with BOTH reviewers** (AGENT_CONTRACTS §2 — neither is optional):
   - /unleashed-mail:gemini-review --ticket <T> --round <N> <plan>
   - /unleashed-mail:codex-review --ticket <T> --round <N> <plan>
   Route non-TTY runs through `scripts/pty-capture.py` (see those skills).
3. **Iterate to convergence** — revise and re-run until **both** return `APPROVE` /
   `APPROVE_WITH_NOTES` (typically 2–6 rounds). After a revision, re-run `snapshot` (step 1) and both reviews on the exact new bytes.
4. **Synthesize:** run `/unleashed-mail:review-synthesis` to combine the two transcripts into one
   auditable Combined verdict — it also **persists** the artifact (`write` auto-reads the snapshot from
   step 1, so no `--reviewed-sha256` is needed). Bind the exact allocated paths returned by the two
   review recipes; do not reconstruct them:

   ```bash
   # The bare `${CLAUDE_PLUGIN_ROOT}` token is substituted inline in the skill body -> the plugin install
   # path; the `:-.` form is NOT substituted (it would resolve to `.`) and would fail to persist the
   # artifact, so /implement would report "no artifact" (COREDEV-2504). Matches implement.
   # COREDEV2619_BRAINSTORM_PERSIST_BEGIN
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/persist-verdict.sh" \
       --plan "$PLAN_PATH" \
       --verdict "$COMBINED_VERDICT" \
       --reviewer "gemini=${GEMINI_STATUS}:${GEMINI_TRANSCRIPT}" \
       --reviewer "codex=${CODEX_STATUS}:${CODEX_TRANSCRIPT}"
   # COREDEV2619_BRAINSTORM_PERSIST_END
   ```
5. **Then** hand off: `/unleashed-mail:implement FEATURE_NAME`.

> The artifact is bound to the plan's **raw bytes** — editing the plan after approval invalidates it
> (approve-then-edit is blocked), so re-run the gate on any post-approval change.
