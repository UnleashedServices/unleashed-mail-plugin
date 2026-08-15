#!/usr/bin/env python3
"""Mechanical checks for planning documents, targeting the defect classes that keep recurring.

WHY THIS LIVES IN THE REPO
An earlier version of this tool ran for a whole campaign out of a session scratchpad under /tmp, and
the scratchpad was cleared mid-session — taking ~600 lines, 39 assertions and six adequacy seeds with
it, uncommitted. This repo already carries the lesson for review transcripts ("never /tmp"); the tool
that checks the plans is at least as load-bearing as the transcripts, so it is version-controlled here
and runs in CI alongside the other validators.

THE CLASSES IT CATCHES, each found repeatedly on COREDEV-2617:

  * STALE INTRA-PLAN CITATION. `:N` references drift every time text is inserted above them. Verified
    against the CONTENT at the target line, never against the number.
  * STALE CROSS-FILE CITATION. `path/file.sh:83` correct in one worktree and wrong in another. Round 28
    cited `sessionstart-restore.sh:83`, exact on `main`, wrong by two lines on the feature branch. This
    resolves against the tree it is given and nothing else.
  * UNVERIFIABLE EXTERNAL REFERENCE. A confident `§4.5b of the journal plan` naming a section that
    exists only on an unmerged branch. Four such citations shipped before this check existed.
  * ENUM DRIFT. A state value used that the declaration never lists, so an outcome silently folds onto
    another. Twice on one enum.
  * HALF-A-FAMILY. A normative sentence living in several places; one copy edited, the siblings left
    asserting the old contract. Fourteen instances, and the reason the CORRECTION RULE exists.

ADEQUACY IS PART OF THE TOOL. `--selftest` seeds each defect into a scratch copy and requires the
corresponding check to FAIL. A check that cannot fail is indistinguishable from a check that passes,
and this campaign shipped three harnesses that reported success while proving nothing.

Usage:
    validate-plan-citations.py <plan.md> [--repo ROOT]   # lint; exit 1 on any problem
    validate-plan-citations.py <plan.md> --selftest      # prove each check discriminates
    validate-plan-citations.py <plan.md> --fix-citations # repair intra-plan line numbers, then lint
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile

# --------------------------------------------------------------------------------------------------
# Check 1 — intra-plan `:N` citations must point at the content they claim.
# Each rule is (label, regex over the plan capturing the line number, regex the target line must match).
# The expected pattern MUST identify exactly one line; --fix-citations refuses to repair otherwise, and
# --selftest enforces the property so it cannot rot. An earlier repair pass that picked the first of
# five matches silently re-pointed three real citations at a history paragraph.
# --------------------------------------------------------------------------------------------------
INTERNAL_RULES = [
    ("§1 env evidence",      r"§1 \(`:(\d+)(?:-\d+)?`\) establishes", r"exported only to hook and MCP invocations"),
    ("§4.3 round-6 mandate", r"§4\.3's round-6 mandate \(`:(\d+)`\)", r"inline branch must implement"),
    ("§4.3 matrix change",   r"its matrix change \(`:(\d+)-\d+`\)", r"mandates a test change"),
    ("§4.4 quarantine",      r"§4\.4's quarantine premise and ordering \(`:(\d+)-\d+`\)", r"DECIDED IN ROUND 1 — QUARANTINE"),
    ("§5 inert-gate row",    r"§5's inert-gate mitigation \(`:(\d+)`\)", r"^\| The gate goes inert"),
    ("§7 consumer row",      r"§7 row `:(\d+)`", r"^\s*\| `precompact-snapshot\.sh`"),
    ("§7 consumer row (2)",  r"§7's consumer row\*{0,2} \(`:(\d+)`\)", r"^\s*\| `precompact-snapshot\.sh`"),
    ("§7 consumer row (3)",  r"§7's row `:(\d+)` amended", r"^\s*\| `precompact-snapshot\.sh`"),
    ("round-2 rejection",    r"Round 2 \(`:(\d+)-\d+`\) rejected the A\+D hybrid", r"DECIDED IN ROUND 2"),
]

# --------------------------------------------------------------------------------------------------
# Check 2 — cross-document section references must resolve IN THIS TREE.
# A section on an unmerged branch is a promise, not a citation.
# --------------------------------------------------------------------------------------------------
EXTERNAL_RULES = [
    (r"§(\d+\.\d+[a-z]?) of the journal plan", "docs/planning/DECISION_JOURNAL_PLAN.md", "journal plan"),
    (r"`COREDEV-2585` §(\d+\.\d+[a-z]?)", "docs/planning/DECISION_JOURNAL_PLAN.md", "journal plan"),
]

SELF_QUESTION_RE = re.compile(r"§8 Q(\d+)")

# --------------------------------------------------------------------------------------------------
# Check 3 — cross-FILE citations must name the content they claim, in the worktree the plan lives in.
# A range citation is satisfied by the content appearing anywhere in the range: demanding it on the
# opening line measures formatting, not truth.
# --------------------------------------------------------------------------------------------------
CROSS_FILE_RULES = [
    ("snapshot delete",  r"`rm -f \"\$SNAP\"` at `sessionstart-restore\.sh:(\d+)`",
     "scripts/sessionstart-restore.sh", r'rm -f "\$SNAP"'),
    ("precompact SNAP",  r"`precompact-snapshot\.sh` \(`:(\d+)`\)",
     "scripts/precompact-snapshot.sh", r'SNAP="\$\(context_snapshot_path\)"'),
    ("restore SNAP",     r"`sessionstart-restore\.sh` \(`:(\d+)`\)",
     "scripts/sessionstart-restore.sh", r'SNAP="\$\(context_snapshot_path\)"'),
    # One file, three claims, three ranges. A single rule applying one expectation to all of them
    # reported the two correct citations as wrong — scope must match expectation.
    ("reviewer fence",   r"`agents/swift-reviewer\.md:(\d+)-(269)`",
     "agents/swift-reviewer.md", r"context_reviews_dir|NO CAPTURE \(unresolved\)"),
    ("reviewer bridge",  r"`agents/swift-reviewer\.md:(\d+)-(193)`",
     "agents/swift-reviewer.md", r"MAJ-6: bridge CLAUDE_PLUGIN_DATA"),
    ("reviewer attribution", r"`agents/swift-reviewer\.md:(\d+)-(176)`",
     "agents/swift-reviewer.md", r"Positive attribution|Name the reviewers you HOLD"),
]

# --------------------------------------------------------------------------------------------------
# Check 4 — every enum value used must be declared.
# --------------------------------------------------------------------------------------------------
ENUMS = [
    ("_UNLEASHED_POINTER_STATE", r"_UNLEASHED_POINTER_STATE`? ∈ ([^\n.]+)"),
    ("_UNLEASHED_BASE_SOURCE", r"vocabulary becomes\s+([^\n]+)"),
]

# --------------------------------------------------------------------------------------------------
# Check 5 — a normative phrase stated in several places must be stated identically.
# This does not know which copy is right; it reports that a FAMILY EXISTS, so a rule cannot be edited
# in one place under the belief that it lives in one place. Each entry below is a family that actually
# split during this campaign.
# --------------------------------------------------------------------------------------------------
FAMILY_PHRASES = [
    ("encoder form",
     r"(?:four disjoint markers|three disjoint markers|_k=\$\{_v//_/_u\})",
     "four disjoint markers"),
    ("temp name shape",
     r"\.pub\.<pid>\.(?:<uniq>\.|<monotonic-unique-suffix>\.|<suffix>\.)?<key>",
     ".pub.<pid>.<uniq>.<key>"),
    ("hook ACL cost",
     r"(?:A hook pays zero|hook pays the ACL cost)",
     "hook pays the ACL cost"),
    ("no-persistence invariant",
     r"(?:nothing|no plugin-state payload) is read or written anywhere",
     "no plugin-state payload is read or written anywhere"),
]


def _join_wraps(text: str) -> str:
    """Join wrapped lines but KEEP markup.

    Split from `_flatten` because the enum parser reads values out of backticked tokens and flattening
    strips exactly those, which silently disarmed it.
    """
    out = re.sub(r"\n[ \t]*>[ \t]*", " ", text)
    out = re.sub(r"\n[ \t]+", " ", out)
    return re.sub(r"[ \t]+", " ", out)


def _flatten(text: str) -> str:
    """Join wraps AND strip emphasis, for prose scans.

    Scanning raw text let a fabricated `§4.5c of the journal plan` through because the reference wrapped
    between "journal" and "plan".
    """
    return re.sub(r"[ \t]+", " ", re.sub(r"\*\*|\*|`", "", _join_wraps(text)))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\*\*|\*|`|_", "", s)).strip().lower()


def check_internal(lines, body, start, end, problems):
    checked = 0
    for label, pat, expect in INTERNAL_RULES:
        for m in re.finditer(pat, "\n".join(lines)):
            checked += 1
            n = int(m.group(1))
            if not 1 <= n <= len(lines):
                problems.append(f"[cite-internal] {label}: cites :{n}, outside the file")
                continue
            if not re.search(expect, lines[n - 1]):
                problems.append(f"[cite-internal] {label}: cites :{n}, but that line is "
                                f"{lines[n - 1].strip()[:60]!r} (expected /{expect}/)")
            if start < n <= end:
                problems.append(f"[cite-internal] self-citation `:{n}` lands inside the section ({start+1}..{end})")
    return checked


_SENTENCE_END = re.compile(r"[.!?](?=\s)|\n\s*\n|\|")


def _sentence_around(flat, start, end, other_spans=()):
    """The text a negation may sit in to correct the citation at [start, end) — ASYMMETRIC, as grammar
    is: a POST-position negation ("does not exist", "unmerged", …) belongs to the citation it FOLLOWS,
    from the citation's end to the next citation or the sentence's end; a PRE-position form ("no §",
    "there is no") must sit in the 40 characters immediately BEFORE the citation, after any previous
    citation. A whole-sentence window let one negation exempt two references in one sentence, and a
    symmetric clause split still handed the text BETWEEN two citations to both of them
    (`§9.9z … does not exist, but this rule relies on §9.8z …`; codex, PR #67 passes 7 and 13)."""
    lo = 0
    for m in _SENTENCE_END.finditer(flat, 0, start):
        lo = m.end()
    m = _SENTENCE_END.search(flat, end)
    hi = m.start() if m else len(flat)
    for s, e in other_spans:
        if e <= start and e > lo:
            lo = e
        if s >= end and s < hi:
            hi = s
    post = flat[end:hi]
    pre = flat[max(lo, start - 40):start]
    return post, pre


_POST_NEGATION = re.compile(r"does not exist|does NOT exist|lives only on|unmerged|zero hits|not exist in this tree|prospective")
_PRE_NEGATION = re.compile(r"no §|there is\s+no|there was\s+no")


def check_external(text, repo, problems, flat):
    checked = 0
    all_spans = sorted(mm.span() for pat, _r, _l in EXTERNAL_RULES for mm in re.finditer(pat, flat))
    for pat, relpath, label in EXTERNAL_RULES:
        for m in re.finditer(pat, flat):
            sec = m.group(1)
            checked += 1
            full = os.path.join(repo, relpath)
            if not os.path.exists(full):
                problems.append(f"[cite-external] {label}: {relpath} does not exist in this tree")
                continue
            doc = open(full, encoding="utf-8", errors="replace").read()
            if re.search(rf"^#{{2,4}} {re.escape(sec)}[ .—-]", doc, re.M):
                continue
            # A CORRECTION is not a claim. The plan deliberately records that §4.5b does NOT exist here;
            # flagging that sentence forever is how a noisy gate becomes a disabled one. The exemption is
            # scoped to THE SENTENCE THAT CONTAINS THE CITATION — a 260-character window let a negation in
            # a NEIGHBOURING sentence launder an unrelated fabricated reference (`This old section does not
            # exist. A separate rule relies on §9.9z …` passed; codex, PR #67 pass 7). A sentence ends at
            # `.`/`!`/`?` followed by whitespace, at a blank line, or at a table-cell bar.
            post, pre = _sentence_around(flat, m.start(), m.end(), [sp for sp in all_spans if sp != m.span()])
            if _POST_NEGATION.search(post) or _PRE_NEGATION.search(pre):
                continue
            problems.append(f"[cite-external] §{sec} of the {label} does NOT exist in this tree ({relpath})")
    declared = {m.group(1) for m in re.finditer(r"^(\d+)\. ", text, re.M)}
    for m in SELF_QUESTION_RE.finditer(flat):
        checked += 1
        if m.group(1) not in declared:
            problems.append(f"[cite-external] §8 Q{m.group(1)} is referenced but no such question exists")
    return checked


def check_cross_file(repo, problems, joined):
    checked = 0
    for label, cite_pat, relpath, expect in CROSS_FILE_RULES:
        full = os.path.join(repo, relpath)
        if not os.path.exists(full):
            problems.append(f"[cite-file] {label}: {relpath} does not exist in this tree")
            continue
        lines = open(full, encoding="utf-8", errors="replace").read().split("\n")
        for m in re.finditer(cite_pat, joined):
            checked += 1
            n = int(m.group(1))
            end = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else n
            if not 1 <= n <= len(lines):
                problems.append(f"[cite-file] {label}: cites {relpath}:{n}, file has {len(lines)} lines")
                continue
            window = lines[n - 1: max(n, min(end, len(lines)))]
            if not any(re.search(expect, l) for l in window):
                real = [i + 1 for i, l in enumerate(lines) if re.search(expect, l)]
                problems.append(f"[cite-file] {label}: cites {relpath}:{n}"
                                f"{f'-{end}' if end != n else ''} — content is at {real or 'nowhere'}")
    return checked


def check_enums(problems, joined):
    checked = 0
    for var, decl_re in ENUMS:
        m = re.search(decl_re, joined)
        if not m:
            problems.append(f"[enum] {var}: no declaration found — cannot verify its values")
            continue
        declared = set(re.findall(r"`([a-z][a-z-]*)`", m.group(1)))
        if not declared:
            problems.append(f"[enum] {var}: declaration parsed but lists no values: {m.group(1)[:60]!r}")
            continue
        checked += 1
        used = set()
        for um in re.finditer(rf"{re.escape(var)}.{{0,80}}?=\s*`?([a-z][a-z-]*)`?", joined):
            used.add(um.group(1))
        stray = used - declared
        if stray:
            problems.append(f"[enum] {var}: value(s) {sorted(stray)} used but NOT declared "
                            f"(declared: {sorted(declared)})")
    return checked


def check_family(problems, flat):
    checked = 0
    for label, pat, _canonical in FAMILY_PHRASES:
        hits = []
        for m in re.finditer(pat, flat):
            # A QUOTATION of superseded wording is not a stale sibling — correction notes deliberately
            # quote the old sentence. Only skip text literally in quote marks at the match boundary; an
            # earlier proximity filter blinded the check exactly where it was most needed, because the
            # stale sibling usually sits beside the note correcting it.
            before, after = flat[max(0, m.start() - 2): m.start()], flat[m.end(): m.end() + 2]
            if ('"' in before and '"' in after) or ("'" in before and "'" in after):
                continue
            hits.append(m.group(0))
        if not hits:
            continue
        checked += 1
        variants = {_norm(h) for h in hits}
        if len(variants) > 1:
            problems.append(f"[family] {label}: {len(hits)} occurrences in {len(variants)} DIFFERENT "
                            f"wordings — one copy was edited and the others were not. "
                            f"Variants: {sorted(variants)[:3]}")
    return checked


def fix_citations(plan):
    """Repair intra-plan line numbers from the CONTENT they claim. Refuses on an ambiguous anchor."""
    text = open(plan, encoding="utf-8").read()
    lines = text.split("\n")
    changed, unresolved = [], []
    for label, cite_pat, expect in INTERNAL_RULES:
        hits = [i + 1 for i, l in enumerate(lines) if re.search(expect, l, re.M)]
        if len(hits) != 1:
            unresolved.append(f"{label}: expected pattern matches {len(hits)} lines {hits[:5]} — need "
                              f"exactly 1; nothing rewritten")
            continue
        target = hits[0]

        def _sub(m, _t=target, _l=label):
            span = m.group(0)

            def _num(mm):
                start, end = int(mm.group(1)), mm.group(2)
                if end is None:
                    return f"`:{_t}`"
                return f"`:{_t}-{_t + max(0, int(end) - start)}`"

            new = re.sub(r"`:(\d+)(?:-(\d+))?`", _num, span, count=1)
            if new != span:
                changed.append(f"{_l}: {span.strip()} -> {new.strip()}")
            return new

        text = re.sub(cite_pat, _sub, text)
    open(plan, "w", encoding="utf-8").write(text)
    return changed, unresolved


def lint(plan, repo, section_head="### 4.2a — ", section_end="### 4.3 — "):
    text = open(plan, encoding="utf-8").read()
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith(section_head)), 0)
    end = next((i for i, l in enumerate(lines) if l.startswith(section_end)), len(lines))
    body = "\n".join(lines[start:end])
    joined, flat = _join_wraps(text), _flatten(text)
    problems: list[str] = []
    n = 0
    n += check_internal(lines, body, start, end, problems)
    n += check_external(text, repo, problems, flat)
    n += check_cross_file(repo, problems, joined)
    n += check_enums(problems, joined)
    n += check_family(problems, flat)
    return problems, n


SEEDS = [
    ("cite-internal", lambda s: s.replace("§5's inert-gate mitigation (`:", "§5's inert-gate mitigation (`:9", 1)),
    ("cite-external", lambda s: s.replace("## 5. Risk register",
                                          "See §4.9z of the journal plan.\n\n## 5. Risk register", 1)),
    # The seed that was missing when a real fabricated citation slipped through: it WRAPPED across a
    # line, and the check scanned raw text. A seed that does not reproduce the real shape proves nothing.
    ("cite-external", lambda s: s.replace("## 5. Risk register",
                                          "* a lock, the same primitive §4.9z of the journal\n"
                                          "  plan settled on, is taken.\n\n## 5. Risk register", 1)),
    # The laundering shape (codex, PR #67 pass 7): a negation in the NEIGHBOURING sentence.
    ("cite-external", lambda s: s.replace("## 5. Risk register",
                                          "This old section does not exist. A separate rule relies on "
                                          "§9.9z of the journal plan.\n\n## 5. Risk register", 1)),
    # The second laundering shape (codex, PR #67 pass 13): one negation, TWO references in one sentence —
    # the negation belongs to §9.9z, and §9.8z must still be detected.
    ("cite-external", lambda s: s.replace("## 5. Risk register",
                                          "§9.9z of the journal plan does not exist, but this rule relies "
                                          "on §9.8z of the journal plan.\n\n## 5. Risk register", 1)),
    # CONTENT-RELATIVE, not a hard-coded line: the seed anchored on `:85` for as long as that was the pin,
    # and when the pin was relocated to follow the script the seed silently found nothing — CI red on
    # PR #67 for two passes with "ANCHOR NOT FOUND", which is this self-test doing its job one level up.
    # And it must land on a line the checker REJECTS: an offset that happened to hit a second copy of the
    # expected content would report "NOT DETECTED — check is decorative" and blame the checker for a
    # coincidence in the seed. Line 0 is outside every file, so the checker rejects it unconditionally.
    ("cite-file", lambda s: re.sub(r"(at `sessionstart-restore\.sh:)(\d+)`",
                                   lambda m: f"{m.group(1)}0`", s, count=1)),
    # The seed value must be one the plan does NOT declare. It was `contended` until that value was
    # declared for real, at which point the seed went quiet and the check looked healthy while proving
    # nothing — a seed sharing vocabulary with the document under test has an expiry date.
    ("enum", lambda s: s.replace("## 5. Risk register",
                                "The publisher sets `_UNLEASHED_POINTER_STATE=deferred` and returns."
                                "\n\n## 5. Risk register", 1)),
    ("family", lambda s: s.replace("**exactly four disjoint markers**", "**three disjoint markers**", 1)),
]


def _anchor_uniqueness(plan):
    lines = open(plan, encoding="utf-8").read().split("\n")
    bad = []
    for label, _cite, expect in INTERNAL_RULES:
        hits = [i + 1 for i, l in enumerate(lines) if re.search(expect, l, re.M)]
        if len(hits) != 1:
            bad.append(f"  ANCHOR {label}: matches {len(hits)} lines {hits[:5]}, need exactly 1")
    return bad


def selftest(plan, repo):
    base, checked = lint(plan, repo)
    print(f"baseline: {len(base)} problem(s), {checked} assertions")
    for p in base:
        print(f"    {p}")
    ok = True
    for msg in _anchor_uniqueness(plan):
        print(msg)
        ok = False
    tmp = tempfile.mkdtemp()
    try:
        for name, mutate in SEEDS:
            probe = os.path.join(tmp, "probe.md")
            src = open(plan, encoding="utf-8").read()
            mutated = mutate(src)
            if mutated == src:
                print(f"  SEED {name}: ANCHOR NOT FOUND — the seed mutated nothing, so it proves nothing")
                ok = False
                continue
            open(probe, "w", encoding="utf-8").write(mutated)
            probs, _ = lint(probe, repo)
            new = [p for p in probs if p not in base and p.startswith(f"[{name}]")]
            if new:
                print(f"  SEED {name}: detected — {new[0][:96]}")
            else:
                print(f"  SEED {name}: NOT DETECTED — check is decorative")
                ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--fix-citations", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest(a.plan, a.repo) else 1)
    if a.fix_citations:
        changed, unresolved = fix_citations(a.plan)
        for c in changed:
            print(f"  fixed  {c}")
        for u in unresolved:
            print(f"  STALE RULE  {u}")
        if not changed and not unresolved:
            print("  no citation changes needed")
        # Fall through to a normal lint — the repair is VERIFIED, not announced. But an UNRESOLVED anchor
        # (zero or several matches) is a repair that did NOT happen: the citation may still point at
        # one line that matches, so the lint below passes and a caller reads "fixed" off exit 0 (codex,
        # PR #67 pass 9). Lint first for the report, then fail regardless.
        if unresolved:
            problems, checked = lint(a.plan, a.repo)
            for p in problems:
                print(f"  - {p}")
            print(f"PLAN CITATION REPAIR FAILED — {len(unresolved)} anchor(s) unresolved; nothing rewritten "
                  f"for them ({checked} assertions linted)")
            sys.exit(1)
    problems, checked = lint(a.plan, a.repo)
    if problems:
        print(f"PLAN LINT FAILED — {len(problems)} problem(s), {checked} assertions\n")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"plan lint OK — {checked} assertions")


if __name__ == "__main__":
    main()
