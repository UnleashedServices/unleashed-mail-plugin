"""Deterministic review synthesizer — the coded half of the hybrid.

Input:  validated Finding objects (from the markdown reviewers' JSON, or from
        API tool calls — see reviewers.py).
Output: a consolidated review (clustered, ownership-routed) and a verdict —
        computed in plain Python, not by an LLM parsing a markdown table.

Why "cluster", not "collapse": code CANNOT decide on its own whether two findings
are the *same defect*. Family + line-overlap is necessary but not sufficient
(Gemini's blocker: two `data-race`s on different fields share a family but not a
defect). So this synthesizer NEVER silently drops a fix — it groups merge-
candidates into a cluster and keeps every fix, cross-linked. An optional
`same_defect` adjudicator (an LLM call, or a human) may collapse a cluster
further; the default keeps both. Ownership rules only RE-ROUTE (owner + display
bucket); they never discard.

Run it:  python3 synthesize.py            # uses ./sample_findings + ./changed_files.txt
         python3 synthesize.py a.json b.json --changed changed_files.txt
"""
from __future__ import annotations

import glob
import itertools
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

from schema import Finding, SEVERITY_EMOJI, SEVERITY_RANK, parse_finding

# --------------------------------------------------------------------------- #
# scope filter
# --------------------------------------------------------------------------- #

def in_gating_scope(f: Finding, changed_files: set[str]) -> bool:
    # structural-pipeline findings gate even outside the diff (the reviewer traced
    # them); everything else must be in the changeset.
    return f.scope == "structural-pipeline" or f.file in changed_files


# --------------------------------------------------------------------------- #
# merge-candidate detection
# --------------------------------------------------------------------------- #

def _overlap(a: Finding, b: Finding) -> bool:
    # file-level (line 0) findings overlap only with other file-level findings —
    # a file-level finding never silently absorbs a line-range one.
    if a.line == 0 or b.line == 0:
        return a.line == 0 and b.line == 0
    return a.line <= b.lineEnd and b.line <= a.lineEnd

# Deliberate CROSS-family merges (the Step-5 ownership rules). These are the only
# places a different-family pair is allowed to cluster.
_OWNERSHIP_MERGE_PAIRS = [
    ({"token-race"}, {"credential", "oauth", "keychain"}),          # security owns
    ({"perceived-perf"}, {"html-sanitization", "webview"}),         # security owns
]

def _ownership_pair(a: Finding, b: Finding) -> bool:
    for left, right in _OWNERSHIP_MERGE_PAIRS:
        if (a.category in left and b.category in right) or \
           (b.category in left and a.category in right):
            return True
    return False

def _candidate(a: Finding, b: Finding) -> bool:
    if a.file != b.file or not _overlap(a, b):
        return False
    return a.family == b.family or _ownership_pair(a, b)


# --------------------------------------------------------------------------- #
# clustering (union-find over merge-candidates)
# --------------------------------------------------------------------------- #

_A11Y_CATEGORIES = {
    "a11y", "curator-tokens", "color-contrast", "dynamic-type", "voiceover",
    "keyboard-nav", "webview-a11y", "dual-impl-parity", "notifications",
    "macos-specific",
}

def _highest(fs: list[Finding]) -> Finding:
    return max(fs, key=lambda f: SEVERITY_RANK[f.severity])

def route_owner(findings: list[Finding]) -> Finding:
    """Pick the authoritative representative of a cluster (Step-5 ownership rules).
    Re-routing only changes which finding leads + its display bucket — no fix is
    discarded (all stay in the cluster)."""
    a11y = [f for f in findings
            if f.category in _A11Y_CATEGORIES or f.sourceAgent == "accessibility-auditor"]
    if a11y:                                   # accessibility-auditor is authoritative
        return _highest(a11y)
    sec = [f for f in findings if f.family == "security"]
    if sec and (any(f.category == "token-race" for f in findings)
                or any(f.category in ("html-sanitization", "webview") for f in sec)):
        return _highest(sec)                   # security owns credential-race / sanitize-render
    return _highest(findings)


@dataclass
class Cluster:
    findings: list[Finding]

    @property
    def severity(self) -> str:
        return _highest(self.findings).severity

    @property
    def agents(self) -> list[str]:
        return sorted({f.sourceAgent for f in self.findings})

    @property
    def primary(self) -> Finding:
        return route_owner(self.findings)


def cluster_findings(
    findings: list[Finding],
    same_defect: Optional[Callable[[Finding, Finding], bool]] = None,
) -> list[Cluster]:
    """Group merge-candidates. `same_defect(a, b)` (optional) is the semantic
    adjudicator that confirms whether a candidate pair is truly one defect; the
    default treats every candidate as one cluster (conservative cross-link)."""
    decide = same_defect or (lambda a, b: True)
    parent = list(range(len(findings)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in itertools.combinations(range(len(findings)), 2):
        if _candidate(findings[i], findings[j]) and decide(findings[i], findings[j]):
            parent[find(i)] = find(j)

    groups: dict[int, list[Finding]] = {}
    for i, f in enumerate(findings):
        groups.setdefault(find(i), []).append(f)
    return [Cluster(g) for g in groups.values()]


# --------------------------------------------------------------------------- #
# verify gate (pluggable seam)
# --------------------------------------------------------------------------- #

def default_verify(f: Finding) -> bool:
    """Return True if a blocker is CONFIRMED. Default trusts high-confidence
    blockers and quarantines the rest, so the prototype runs with no API/grep.
    Swap in an LLM or `grep file:line` verifier for real use — same signature."""
    return f.confidence == "high"


# --------------------------------------------------------------------------- #
# verdict
# --------------------------------------------------------------------------- #

@dataclass
class Verdict:
    decision: str
    confirmed_blockers: list[Cluster] = field(default_factory=list)
    needs_confirmation: list[Cluster] = field(default_factory=list)


def decide_verdict(clusters: list[Cluster], verify: Callable[[Finding], bool]) -> Verdict:
    confirmed, unconfirmed = [], []
    for c in clusters:
        if c.severity == "blocker":
            (confirmed if verify(c.primary) else unconfirmed).append(c)
    if confirmed:
        return Verdict("REQUEST_CHANGES", confirmed, unconfirmed)
    if unconfirmed:
        return Verdict("NEEDS_DISCUSSION", confirmed, unconfirmed)
    if any(c.severity in ("warning", "suggestion") for c in clusters):
        return Verdict("APPROVE_WITH_SUGGESTIONS")
    return Verdict("APPROVE")


# --------------------------------------------------------------------------- #
# top-level synthesize
# --------------------------------------------------------------------------- #

@dataclass
class Review:
    clusters: list[Cluster]
    verdict: Verdict
    pre_existing: list[Finding]
    quarantined: list[tuple[dict, str]]


def synthesize(
    findings: list[Finding],
    changed_files: set[str],
    *,
    same_defect: Optional[Callable[[Finding, Finding], bool]] = None,
    verify: Callable[[Finding], bool] = default_verify,
    quarantined: Optional[list[tuple[dict, str]]] = None,
) -> Review:
    gating = [f for f in findings if in_gating_scope(f, changed_files)]
    pre = [f for f in findings if not in_gating_scope(f, changed_files)]
    clusters = cluster_findings(gating, same_defect=same_defect)
    verdict = decide_verdict(clusters, verify)
    return Review(clusters, verdict, pre, quarantined or [])


# --------------------------------------------------------------------------- #
# rendering (mirrors swift-reviewer.md ## Output Format)
# --------------------------------------------------------------------------- #

_BUCKET_ORDER = [
    "Security", "Concurrency & Correctness", "Performance & UX",
    "Accessibility", "Provider Parity", "Test Coverage", "Build / Lint / Tests",
]

def _row(c: Cluster) -> str:
    p = c.primary
    finding = p.finding
    fix = p.fix
    extra = [f for f in c.findings if f is not p]
    if extra:  # cross-link the other fixes in the cluster — nothing is dropped
        finding += f"  _(+{len(extra)} related: {', '.join(f.category for f in extra)})_"
        fix += "".join(f"  ·also· {f.fix}" for f in extra)
    agents = "+".join(a.replace("-reviewer", "").replace("-auditor", "") for a in c.agents)
    return f"| {SEVERITY_EMOJI[c.severity]} | `{p.loc}` | {finding} | {agents} | {fix} |"

def render_markdown(review: Review) -> str:
    out: list[str] = ["# Code Review — synthesized in code\n"]

    by_bucket: dict[str, list[Cluster]] = {}
    for c in review.clusters:
        by_bucket.setdefault(c.primary.bucket, []).append(c)

    out.append("## Consolidated findings (in-scope, gating)\n")
    any_rows = False
    for bucket in _BUCKET_ORDER:
        rows = by_bucket.get(bucket)
        if not rows:
            continue
        any_rows = True
        out.append(f"### {bucket}")
        out.append("| sev | location | finding | from | fix |")
        out.append("|-----|----------|---------|------|-----|")
        for c in sorted(rows, key=lambda c: -SEVERITY_RANK[c.severity]):
            out.append(_row(c))
        out.append("")
    if not any_rows:
        out.append("_none_\n")

    if review.verdict.needs_confirmation:
        out.append("## Needs Confirmation (non-gating)")
        out.append("_Blockers the verify gate could not confirm — route to NEEDS DISCUSSION, never auto-REQUEST-CHANGES._")
        for c in review.verdict.needs_confirmation:
            p = c.primary
            out.append(f"- 🔴 `{p.loc}` — {p.finding}  _(confidence: {p.confidence})_")
        out.append("")

    if review.pre_existing:
        out.append("## Pre-existing (non-gating)")
        out.append("_Outside `$CHANGED` and not tagged `structural-pipeline` — surfaced for awareness, never gates._")
        for f in review.pre_existing:
            out.append(f"- {SEVERITY_EMOJI[f.severity]} `{f.loc}` — {f.finding}")
        out.append("")

    if review.quarantined:
        out.append("## Quarantined (schema-invalid)")
        out.append("_Findings that failed schema validation on ingest — fixed reviewers, not dropped silently._")
        for raw, err in review.quarantined:
            out.append(f"- {err}  ·  `{json.dumps(raw)[:90]}…`")
        out.append("")

    v = review.verdict
    out.append("---")
    out.append(f"## Verdict: **{v.decision}**")
    if v.confirmed_blockers:
        out.append(f"- {len(v.confirmed_blockers)} confirmed blocker(s) → REQUEST CHANGES")
    if v.needs_confirmation:
        out.append(f"- {len(v.needs_confirmation)} unconfirmed blocker(s) → flagged for discussion")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _load(paths: list[str]) -> tuple[list[Finding], list[tuple[dict, str]]]:
    findings, bad = [], []
    for path in paths:
        raw = json.load(open(path))
        items = raw["findings"] if isinstance(raw, dict) else raw
        for d in items:
            try:
                findings.append(parse_finding(d))
            except Exception as exc:  # noqa: BLE001 - quarantine, don't crash
                bad.append((d, str(exc)))
    return findings, bad


def main(argv: list[str]) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    changed_path = os.path.join(here, "changed_files.txt")
    paths = [a for a in argv if not a.startswith("--")]
    if "--changed" in argv:
        changed_path = argv[argv.index("--changed") + 1]
    if not paths:  # default demo
        paths = sorted(glob.glob(os.path.join(here, "sample_findings", "*.json")))

    changed = {ln.strip() for ln in open(changed_path) if ln.strip()} if os.path.exists(changed_path) else set()
    findings, bad = _load(paths)
    review = synthesize(findings, changed, quarantined=bad)
    print(render_markdown(review))
    # exit non-zero on a gating verdict, so this can drop into CI
    return 0 if review.verdict.decision.startswith("APPROVE") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
