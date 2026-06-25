# Hybrid review synthesizer — prototype

A standalone sketch of the **hybrid** review architecture we discussed:

> keep the four reviewer agents as portable **markdown** (Claude Code subagents),
> but move the **synthesis — dedup, ownership routing, verify gate, verdict — into
> deterministic code**.

This is the piece the prompt-only system can't make airtight: an LLM orchestrator
doing row-by-row JSON dedup can silently drop a real finding or gate on an
unverified one (the two blockers Gemini caught in the cross-reference rules). Here
that logic is plain Python — auditable, testable, and incapable of "forgetting" a
finding.

It is **not wired into the plugin**. Nothing under `agents/` or `skills/` changed.
Delete this directory and the plugin is exactly as it was.

```
schema.py        canonical Finding schema  → strict report_finding tool
                                            → structured-output format
                                            → ingest validator (stdlib only)
synthesize.py    deterministic dedup + ownership routing + verify gate + verdict + render + CLI
reviewers.py     PATH A: ingest the markdown reviewers' JSON   (no deps, no key)
                 PATH B: drive a reviewer via the API with a guaranteed-valid schema
sample_findings/ four reviewers' + the orchestrator's findings (a realistic PR)
changed_files.txt the changeset (drives the scope filter)
```

## Run it

```bash
cd prototypes/hybrid-review-synthesizer
python3 synthesize.py          # zero installs — uses sample_findings/ + changed_files.txt
echo $?                        # 1 on a gating verdict → drops straight into CI
```

## Where the determinism comes from

Two layers, and you can adopt either independently:

1. **Schema-valid findings at the source.** On the API the model is *forced* to
   emit valid findings — `strict: true` on the `report_finding` tool guarantees
   `tool_use.input` validates, or `output_config.format` guarantees a valid
   `{"findings": [...]}`. No markdown table to mangle, no pipe-escaping, no
   "ask it to re-emit". (`reviewers.py` PATH B.) If you keep the markdown
   reviewers, the same schema validates their JSON on ingest and **quarantines**
   anything malformed instead of dropping it. (PATH A.)

2. **Deterministic synthesis.** Dedup, ownership routing, the verdict — all in
   `synthesize.py`, mechanically:
   - **Cluster, don't collapse.** Code can't know if two findings are the *same
     defect*; `file + overlapping line-range + same category-family` is the
     candidate test (necessary, not sufficient). Candidates are **clustered and
     cross-linked** — every fix is kept. An optional `same_defect(a, b)`
     adjudicator (an LLM or a human) can collapse a cluster further; the default
     keeps both. This is why the demo's `logic` + `error-handling` rows merge into
     one row that carries *both* fixes rather than dropping one.
   - **Ownership rules re-route, never drop.** The deliberate cross-family merges
     (a credential-site `token-race` → owned by **security**; sanitize/render
     `perceived-perf` → **security**; any a11y-tagged row → **accessibility**) only
     change which finding leads and which display bucket it lands in.
   - **Verify gate is a seam.** `default_verify()` trusts high-confidence blockers
     and routes the rest to *Needs Confirmation* → `NEEDS_DISCUSSION`. Swap in a
     real verifier (`grep file:line`, or a cheap LLM call) with the same signature.
   - **Scope filter.** In-changeset findings gate; `scope: "structural-pipeline"`
     findings gate even outside the diff; everything else is *Pre-existing*
     (surfaced, non-gating).

## How it maps to the markdown today

| `swift-reviewer.md` Step 5 rule | Where it lives here |
|---|---|
| JSON findings schema | `schema.FINDING_JSON_SCHEMA` (+ strict tool / structured output) |
| `file` + overlapping `line..lineEnd` + same family | `synthesize._candidate` |
| cross-family ownership merges | `synthesize._OWNERSHIP_MERGE_PAIRS` + `route_owner` |
| a11y owned by accessibility-auditor | `synthesize.route_owner` |
| keep-both / cross-link, never drop | `cluster_findings` + `_row` |
| verify gate → confirmed gates, else NEEDS DISCUSSION | `default_verify` + `decide_verdict` |
| scope filter + structural carve-out | `in_gating_scope` |
| category → display bucket | `schema.DISPLAY_BUCKET` |
| consolidated table + verdict | `render_markdown` |

The markdown reviewers stay the source of the *findings*; the orchestrator's
Step 5 prose is replaced by `synthesize.py`.

## Trade-offs (so the choice is honest)

| | Prompt-only (today) | This hybrid | Full coded harness |
|---|---|---|---|
| Dedup / verdict correctness | model judgment | **deterministic** | deterministic |
| Reviewers | markdown | **markdown (unchanged)** | code (API calls) |
| Infra / deps | none | Python (stdlib for core) | Python + API key + a runner |
| Portability (drop into any Claude Code install) | **full** | reviewers yes; synth is a script | none |
| Human-editable review logic | prompt prose | Python | Python |

The hybrid is the middle: you keep the portable, editable markdown reviewers and
get guaranteed-correct merging exactly where silent drops would hurt. Go full-coded
only if this becomes a constantly-run gate where you want bit-exact reproducibility
end to end.

## Obvious next steps if you pursue it

- Replace `default_verify` with a real verifier (open `file:line`, confirm the
  pattern, or a one-shot LLM "is this real?" with a `strict` verdict tool).
- Wire `synthesize.py` behind an MCP tool or a Claude Code hook so `swift-reviewer`
  calls it instead of doing Step 5 in prose — markdown reviewers unchanged.
- Add a `same_defect` adjudicator for same-family clusters (cheap LLM call) to
  collapse true duplicates while keeping the safe default.
