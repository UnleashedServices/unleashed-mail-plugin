"""Deterministic synthesis: dedup, ownership routing, scope, verdict, render."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import synthesize as S  # noqa: E402
from schema import parse_finding  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "synthesize.py")
_MUTANT_SEQ = [0]


def load_mutant(tc, old, new):
    """Import a COPY of synthesize.py with `old` -> `new`, asserting the mutation APPLIED: the anchor
    occurs exactly once and the replacement preserves the line count. A mutation that silently fails
    to apply otherwise reads as a passing control — the single most common way a mutation proof
    proves nothing. The copy lands in a fresh temp file under a fresh module name, which also
    sidesteps CPython's .pyc staleness trap (its cache key is (mtime SECONDS, size), so a
    same-length in-place mutate/run/restore inside one second silently reuses old bytecode)."""
    with open(SRC, encoding="utf-8") as fh:
        src = fh.read()
    tc.assertEqual(src.count(old), 1, f"mutant anchor must occur exactly once: {old!r}")
    mutated = src.replace(old, new)
    tc.assertNotEqual(src, mutated, "mutant replacement was a no-op")
    tc.assertEqual(src.count("\n"), mutated.count("\n"),
                   "mutant changed the line count — it must be line-for-line")
    d = tempfile.mkdtemp(prefix="synmutant")
    tc.addCleanup(shutil.rmtree, d, True)
    path = os.path.join(d, "synthesize_mutant.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(mutated)
    _MUTANT_SEQ[0] += 1
    name = f"_synthesize_mutant_{_MUTANT_SEQ[0]}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod               # @dataclass resolves cls.__module__ through sys.modules
    tc.addCleanup(sys.modules.pop, name, None)
    spec.loader.exec_module(mod)          # `from schema import ...` resolves via sys.path above
    return mod


class CliFixture(unittest.TestCase):
    """A real blocker in a real changeset — the CLI's documented CI-gating input."""

    BLOCKER = dict(severity="blocker", confidence="high", sourceAgent="security-reviewer",
                   category="credential", file="MyApp/Auth.swift", line=10, lineEnd=12,
                   finding="hardcoded API key", evidence="let k = 'sk-live'", fix="move to Keychain")

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="syncli")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.fj = self._findings("findings.json", [self.BLOCKER])
        self.clean = self._findings("clean.json", [])
        self.lowconf = self._findings("low.json", [dict(self.BLOCKER, confidence="low")])
        self.ch = os.path.join(self.d, "changed.txt")
        self._changed("MyApp/Auth.swift")

    def _findings(self, name, findings):
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"findings": findings}, fh)
        return p

    def _changed(self, *entries):
        with open(self.ch, "w", encoding="utf-8") as fh:
            fh.write("".join(e + "\n" for e in entries))

    def run_main(self, mod, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = mod.main(argv)
        return rc, out.getvalue(), err.getvalue()


def f(**over):
    d = dict(severity="warning", confidence="high", sourceAgent="x", category="logic",
             file="A.swift", line=10, lineEnd=12, finding="f", evidence="e", fix="x")
    d.update(over)
    return parse_finding(d)


class TestAuditPR53CLIHardening(unittest.TestCase):
    """Audit of #53 (A1): the standalone CLI is a GATING path too and must quarantine an absolute/`..`
    finding `file` + refuse an absolute/`..` changed entry, matching mcp_server.py (was permissive)."""

    _FINDING = dict(severity="warning", confidence="high", sourceAgent="codex", category="logic",
                    line=1, lineEnd=1, finding="secret", evidence="e", fix="x")

    def _write(self, d, obj):
        p = os.path.join(d, "f.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return p

    def test_load_quarantines_absolute_path_finding(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d, {"findings": [dict(self._FINDING, file="/private/project/AuthService.swift")]})
            findings, bad = S._load([p])
            self.assertEqual(findings, [], "an absolute-path finding must be quarantined, not loaded")
            self.assertTrue(bad, "the absolute-path finding must land in the quarantine list")

    def test_load_quarantines_traversal_finding(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d, {"findings": [dict(self._FINDING, file="../../../etc/passwd")]})
            findings, bad = S._load([p])
            self.assertEqual(findings, [])
            self.assertTrue(bad)

    def test_relative_path_finding_still_loads(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d, {"findings": [dict(self._FINDING, file="Sources/AuthService.swift")]})
            findings, bad = S._load([p])
            self.assertEqual(len(findings), 1, "a normal relative-path finding must still load")
            self.assertEqual(bad, [])

    def test_main_fails_closed_on_absolute_changed_entry(self):
        with tempfile.TemporaryDirectory() as d:
            fp = self._write(d, {"findings": []})
            ch = os.path.join(d, "changed.txt")
            with open(ch, "w", encoding="utf-8") as fh:
                fh.write("/abs/AuthService.swift\n")
            self.assertEqual(S.main([fp, "--changed", ch]), 2,
                             "an absolute changed entry must fail closed (exit 2)")

    def test_main_refuses_explicit_findings_without_changed(self):
        # MAJ-5: explicit findings + no --changed must NOT silently scope against the bundled demo
        # changeset (which demotes every out-of-sample blocker to pre-existing and exits 0 APPROVE — a
        # CI-gating fail-open). Fail closed (exit 2) instead.
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d, {"findings": [dict(self._FINDING, severity="blocker",
                                                  category="credential", file="MyApp/RealFile.swift")]})
            self.assertEqual(S.main([p]), 2,
                             "findings without --changed must fail closed, not APPROVE against the demo set")

    def test_main_refuses_unknown_flag(self):
        # MAJ-5: a typo'd/unknown --flag must exit 2, not be silently swallowed (which drops the
        # changeset value and APPROVEs).
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d, {"findings": []})
            ch = os.path.join(d, "changed.txt")
            with open(ch, "w", encoding="utf-8") as fh:
                fh.write("MyApp/RealFile.swift\n")
            self.assertEqual(S.main([p, "--chnged", ch]), 2, "an unknown --flag must fail closed (exit 2)")


class TestS1EmptyChangesetFailsClosed(unittest.TestCase):
    """S1: `--changed` present but EMPTY (or all-blank, or `.`-only) scoped every finding to
    pre-existing and exited 0 APPROVE — a CI-gating fail-open reachable from a real shell mistake
    (`git diff --name-only base..head > changed.txt` on an empty range writes a 0-byte file). The
    guard must refuse (exit 2) instead of certifying an unreviewed changeset clean."""

    # A finding that is VALID (sourceAgent + evidence present, relative path) so it LOADS rather than
    # being quarantined. An earlier reproduction of this bug was masked exactly there: a fixture
    # missing sourceAgent/evidence is quarantined, and quarantine forces NEEDS_DISCUSSION/rc=1 — a
    # plausible-looking refusal that hides the APPROVE. The control cell below pins that distinction.
    _BLOCKER = dict(severity="blocker", confidence="high", sourceAgent="security-reviewer",
                    category="credential", file="MyApp/RealFile.swift", line=1, lineEnd=1,
                    finding="hardcoded token", evidence="let t = \"AKIA...\"", fix="move to Keychain")

    def _run(self, changed_text):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "f.json")
            with open(fp, "w", encoding="utf-8") as fh:
                json.dump({"findings": [self._BLOCKER]}, fh)
            ch = os.path.join(d, "changed.txt")
            with open(ch, "w", encoding="utf-8") as fh:
                fh.write(changed_text)
            # Redirected so the suite's own output stays readable (gemini, PR #77) — the refusal
            # diagnostics and the rendered report otherwise interleave with the runner's dots and
            # bury the summary line. CliFixture.run_main already does this; this was the outlier.
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return S.main([fp, "--changed", ch])

    def test_zero_byte_changed_file_refuses(self):
        self.assertEqual(self._run(""), 2,
                         "a 0-byte --changed file must fail closed, not APPROVE every finding as pre-existing")

    def test_blank_lines_only_refuses(self):
        self.assertEqual(self._run("\n   \n\t\n\n"), 2,
                         "an all-whitespace --changed file must fail closed")

    def test_dot_only_refuses(self):
        # `.` canonicalises to the empty path, so it is an empty changeset wearing a plausible disguise.
        self.assertEqual(self._run(".\n"), 2, "a `.`-only --changed file must fail closed")

    def _run_findings(self, findings, changed_text):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "f.json")
            with open(fp, "w", encoding="utf-8") as fh:
                json.dump({"findings": findings}, fh)
            ch = os.path.join(d, "changed.txt")
            with open(ch, "w", encoding="utf-8") as fh:
                fh.write(changed_text)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = S.main([fp, "--changed", ch])
            return rc, out.getvalue(), err.getvalue()

    def test_no_findings_and_an_empty_changeset_still_APPROVES(self):
        # THE NARROWING HALF (codex, PR #77). The first cut of this guard tested whether a findings
        # PATH was supplied, not whether it held any rows — so a genuinely clean run (`findings.json`
        # holding `[]` beside an empty `git diff --name-only`, i.e. nothing changed and nothing found)
        # was REFUSED with exit 2. That is a false refusal, and it also diverged from the MCP twin at
        # mcp_server.py:185, which guards on the parsed `findings_in` list and accepted the same input.
        # Refusing an empty changeset is only correct when there is something that WOULD mis-scope.
        rc, out, err = self._run_findings([], "")
        self.assertIn("## Verdict (provisional): **APPROVE**", out)
        self.assertNotIn("refusing to synthesize", err)
        self.assertEqual(rc, 0, "nothing changed and nothing found is a clean review, not a refusal")

    def test_a_quarantined_row_still_counts_as_a_row(self):
        # `bad` counts as well as `findings`: a row that only quarantined is still a row that would
        # mis-scope, and the MCP twin's `findings_in` is likewise the raw list. Guarding on parsed
        # findings ALONE would reopen the fail-open for any input whose rows all fail schema.
        rc, _, err = self._run_findings([{"severity": "nonsense"}], "")
        self.assertIn("refusing to synthesize", err)
        self.assertEqual(rc, 2)

    def test_control_real_path_still_reviews(self):
        # CONTROL — without this the three cells above pass against a synthesizer that refuses
        # EVERYTHING, proving nothing. The same fixture and the same blocker must reach a real verdict
        # (REQUEST_CHANGES, rc=1) as soon as the changeset names the file the finding is in.
        self.assertEqual(self._run("MyApp/RealFile.swift\n"), 1,
                         "a real changed path must still produce REQUEST_CHANGES, not the refusal")


class TestExactDedup(unittest.TestCase):
    def test_byte_identical_duplicates_collapse(self):
        # MIN-14: the SAME finding ingested twice (a capture replay unioned with fresh arrays) must
        # collapse to one — else clusterSize inflates (presented as corroboration weight) and the verify
        # gate sees two identical blockersToVerify entries.
        dup = dict(severity="blocker", confidence="high", sourceAgent="security-reviewer",
                   category="credential", file="A.swift", line=10, lineEnd=10,
                   finding="same", evidence="same", fix="same")
        review = S.synthesize([parse_finding(dup), parse_finding(dict(dup))], {"A.swift"})
        self.assertEqual(len(review.clusters), 1)
        self.assertEqual(len(review.clusters[0].findings), 1, "an exact duplicate must collapse to one")

    def test_different_reviewer_same_defect_kept_as_corroboration(self):
        # Distinct sourceAgent => NOT byte-identical => real cross-reviewer corroboration => cluster the
        # two (never drop), so clusterSize legitimately reflects two reviewers.
        base = dict(severity="blocker", confidence="high", category="credential",
                    file="A.swift", line=10, lineEnd=10, finding="f", evidence="e", fix="x")
        review = S.synthesize([parse_finding(dict(base, sourceAgent="security-reviewer")),
                               parse_finding(dict(base, sourceAgent="concurrency-reviewer"))], {"A.swift"})
        self.assertEqual(len(review.clusters), 1)
        self.assertEqual(len(review.clusters[0].findings), 2, "two different reviewers => real corroboration")


class TestDedup(unittest.TestCase):
    def test_same_family_overlap_clusters(self):
        cs = S.cluster_findings([f(category="logic", line=10, lineEnd=20),
                                 f(category="error-handling", line=15, lineEnd=18)])
        self.assertEqual(len(cs), 1)
        self.assertEqual(len(cs[0].findings), 2)

    def test_non_overlapping_lines_separate(self):
        cs = S.cluster_findings([f(line=10, lineEnd=12), f(line=30, lineEnd=32)])
        self.assertEqual(len(cs), 2)

    def test_different_family_separate(self):
        cs = S.cluster_findings([f(category="logic"),
                                 f(category="rendering", sourceAgent="ux-perf-reviewer")])
        self.assertEqual(len(cs), 2)

    def test_line0_only_clusters_with_line0(self):
        cs = S.cluster_findings([f(category="logic", line=0, lineEnd=0),
                                 f(category="error-handling", line=5, lineEnd=6)])
        self.assertEqual(len(cs), 2)

    def test_cross_family_ownership_pair_clusters(self):
        cs = S.cluster_findings([
            f(category="keychain", sourceAgent="security-reviewer", line=40, lineEnd=52),
            f(category="token-race", sourceAgent="concurrency-reviewer", line=44, lineEnd=48)])
        self.assertEqual(len(cs), 1)

    def test_cluster_keeps_all_fixes_cross_linked(self):
        cs = S.cluster_findings([f(category="logic", fix="FIX_A"),
                                 f(category="error-handling", fix="FIX_B")])
        review = S.Review(cs, S.decide_verdict(cs, lambda x: True), [], [])
        report = S.render_report(review)
        self.assertIn("FIX_A", report)
        self.assertIn("FIX_B", report)   # second fix is never silently dropped

    def test_related_categories_are_deduped(self):
        cs = S.cluster_findings([f(category="logic", line=10, lineEnd=20, fix="A"),
                                 f(category="error-handling", line=11, lineEnd=19, fix="B"),
                                 f(category="error-handling", line=12, lineEnd=18, fix="C")])
        self.assertEqual(len(cs), 1)
        finding, _ = S._issue_and_fix(cs[0])
        self.assertIn("related:", finding)
        self.assertEqual(finding.count("error-handling"), 1)   # not "error-handling, error-handling"

    def test_extra_fix_identical_to_primary_is_not_repeated(self):
        cs = S.cluster_findings([f(category="logic", line=10, lineEnd=20, fix="SAME"),
                                 f(category="error-handling", line=11, lineEnd=19, fix="SAME")])
        self.assertEqual(len(cs), 1)
        _, fix = S._issue_and_fix(cs[0])
        self.assertEqual(fix.count("SAME"), 1)        # primary's fix once; identical extra skipped
        self.assertNotIn("·also· SAME", fix)


class TestAISafetyOwnershipMerge(unittest.TestCase):
    """COREDEV-2332: ai-safety↔security category pairs cluster on the SAME lines and
    route to prompt-review, without over-clustering or hiding a security blocker."""

    def _overlap(self, ai_cat, sec_cat):
        # same file (default A.swift), overlapping lines (10-20 vs 12-18)
        return S.cluster_findings([
            f(category=ai_cat, sourceAgent="prompt-review", line=10, lineEnd=20, finding="ai"),
            f(category=sec_cat, sourceAgent="security-reviewer", line=12, lineEnd=18, finding="sec")])

    def test_pii_log_leak_privacy_clusters_owned_by_prompt_review(self):
        cs = self._overlap("pii-log-leak", "privacy")
        self.assertEqual(len(cs), 1)
        self.assertEqual(len(cs[0].findings), 2)                 # nothing dropped
        self.assertEqual(cs[0].primary.sourceAgent, "prompt-review")

    def test_unsanitized_ingress_webview_clusters_owned_by_prompt_review(self):
        cs = self._overlap("unsanitized-ingress", "webview")
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0].primary.sourceAgent, "prompt-review")

    def test_unsanitized_ingress_html_sanitization_clusters_owned_by_prompt_review(self):
        # the html-sanitization sibling sink (codex r1 blocker — must be covered)
        cs = self._overlap("unsanitized-ingress", "html-sanitization")
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0].primary.sourceAgent, "prompt-review")

    def test_unscoped_tool_privacy_clusters_owned_by_prompt_review(self):
        cs = self._overlap("unscoped-tool", "privacy")
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0].primary.sourceAgent, "prompt-review")

    def test_unrelated_ai_security_pair_does_not_cluster(self):
        # jailbreak-surface (ai-safety) + oauth (security) overlapping -> NOT a pair ->
        # two clusters. Proves we did a category-pair, not a family-level, merge.
        cs = self._overlap("jailbreak-surface", "oauth")
        self.assertEqual(len(cs), 2)

    def test_network_is_not_an_ingress_pair(self):
        # `network` is ATS/TLS/cert, not untrusted-content sanitization -> must NOT merge.
        cs = self._overlap("unsanitized-ingress", "network")
        self.assertEqual(len(cs), 2)

    def test_valid_pair_on_non_overlapping_lines_stays_separate(self):
        cs = S.cluster_findings([
            f(category="pii-log-leak", sourceAgent="prompt-review", line=10, lineEnd=12),
            f(category="privacy", sourceAgent="security-reviewer", line=40, lineEnd=42)])
        self.assertEqual(len(cs), 2)

    def test_mixed_severity_security_blocker_survives_under_prompt_review_ownership(self):
        # prompt-review owns DISPLAY routing, but a security BLOCKER in the merged cluster
        # must still lead the row text and still gate the verdict — the merge can never
        # hide a security blocker behind ai-safety display ownership.
        r = S.synthesize([
            f(category="pii-log-leak", sourceAgent="prompt-review", severity="suggestion",
              line=10, lineEnd=20, finding="ai pii note", fix="redact"),
            f(category="privacy", sourceAgent="security-reviewer", severity="blocker",
              line=12, lineEnd=18, finding="SEC BLOCKER leak", fix="scope it")],
            {"A.swift"}, verify=lambda x: True)
        self.assertEqual(len(r.clusters), 1)
        c = r.clusters[0]
        self.assertEqual(c.primary.sourceAgent, "prompt-review")     # display owner (ai-safety)
        self.assertEqual(c.primary.bucket, "AI Prompt Safety")
        self.assertEqual(c.severity, "blocker")                      # cluster severity = the blocker
        self.assertEqual(c.lead_blocker.sourceAgent, "security-reviewer")
        self.assertEqual(r.verdict.decision, "REQUEST_CHANGES")      # the security blocker still gates
        report = S.render_report(r)
        self.assertIn("SEC BLOCKER leak", report)                    # blocker text leads the row
        self.assertIn("AI Prompt Safety", report)                    # prompt-review's display bucket


class TestOwnershipRouting(unittest.TestCase):
    def test_a11y_authoritative(self):
        fs = [f(category="curator-tokens", sourceAgent="accessibility-auditor", severity="warning"),
              f(category="curator-tokens", sourceAgent="accessibility-auditor", severity="blocker")]
        self.assertEqual(S.route_owner(fs).severity, "blocker")

    def test_security_owns_credential_race(self):
        fs = [f(category="keychain", sourceAgent="security-reviewer", line=40, lineEnd=52),
              f(category="token-race", sourceAgent="concurrency-reviewer", line=44, lineEnd=48)]
        self.assertEqual(S.route_owner(fs).family, "security")

    def test_a11y_tie_prefers_accessibility_auditor_over_input_order(self):
        # ux-perf row tagged a11y listed BEFORE the auditor row, same severity:
        # the auditor must still own it (documented authority), not input order.
        fs = [f(category="color-contrast", sourceAgent="ux-perf-reviewer", severity="warning", finding="ux"),
              f(category="color-contrast", sourceAgent="accessibility-auditor", severity="warning", finding="audit")]
        self.assertEqual(S.route_owner(fs).sourceAgent, "accessibility-auditor")

    def test_ai_safety_owned_by_prompt_review(self):
        # an ai-safety row clustered with a security row -> prompt-review owns (COREDEV-2329).
        fs = [f(category="privacy", sourceAgent="security-reviewer", severity="warning", finding="sec"),
              f(category="pii-log-leak", sourceAgent="prompt-review", severity="warning", finding="ai")]
        self.assertEqual(S.route_owner(fs).sourceAgent, "prompt-review")

    def test_ai_safety_tie_prefers_prompt_review_over_input_order(self):
        fs = [f(category="unsanitized-ingress", sourceAgent="security-reviewer", severity="blocker", finding="sec"),
              f(category="unsanitized-ingress", sourceAgent="prompt-review", severity="blocker", finding="ai")]
        self.assertEqual(S.route_owner(fs).sourceAgent, "prompt-review")


class TestAISafetyFamily(unittest.TestCase):
    # The 10 prompt-review taxonomy kinds, canonical. The agent emits these verbatim as `category`.
    EXPECTED = {
        "jailbreak-surface", "missing-refusal-path", "format-leak", "context-overflow-risk",
        "ambiguous-instruction", "evaluation-gap", "unsanitized-ingress", "inline-prompt-leak",
        "unscoped-tool", "pii-log-leak",
    }

    def test_category_set_equality_invariant(self):
        # The silent-drop trap (COREDEV-2329): the agent-emitted set MUST equal the schema family
        # set MUST equal synthesize's ownership set — exact, all kebab-case. Any drift quarantines.
        import schema
        schema_set = {c for c, fam in schema.CATEGORY_FAMILY.items() if fam == "ai-safety"}
        self.assertEqual(schema_set, self.EXPECTED)
        self.assertEqual(S._AI_SAFETY_CATEGORIES, self.EXPECTED)
        for c in self.EXPECTED:
            self.assertRegex(c, r"^[a-z]+(?:-[a-z]+)*$")

    def test_agent_md_documents_every_category(self):
        # the shipped agents/prompt-review.md must name each category (so its output can't drift
        # from the schema undetected).
        here = os.path.dirname(os.path.abspath(__file__))
        agent_md = os.path.join(here, "..", "..", "..", "agents", "prompt-review.md")
        with open(agent_md, encoding="utf-8") as fh:
            text = fh.read()
        for c in self.EXPECTED:
            self.assertIn(c, text, f"prompt-review.md does not document category {c!r}")

    def test_ai_safety_finding_validates_and_buckets(self):
        fnd = f(category="jailbreak-surface", sourceAgent="prompt-review")
        self.assertEqual(fnd.family, "ai-safety")
        self.assertEqual(fnd.bucket, "AI Prompt Safety")


class TestScope(unittest.TestCase):
    CHANGED = {"A.swift"}

    def test_changeset_finding_gates(self):
        r = S.synthesize([f(file="A.swift")], self.CHANGED)
        self.assertEqual((len(r.clusters), len(r.pre_existing)), (1, 0))

    def test_structural_pipeline_gates_outside_diff(self):
        r = S.synthesize([f(file="Z.swift", scope="structural-pipeline")], self.CHANGED)
        self.assertEqual(len(r.clusters), 1)

    def test_out_of_scope_is_pre_existing(self):
        r = S.synthesize([f(file="Z.swift")], self.CHANGED)
        self.assertEqual((len(r.clusters), len(r.pre_existing)), (0, 1))

    def test_path_normalization_matches_scope_on_both_sides(self):
        # finding uses a ./ prefix, $CHANGED is clean -> still gates
        r = S.synthesize([f(category="logic", severity="blocker", file="./A.swift")],
                         self.CHANGED, verify=lambda x: True)
        self.assertEqual((len(r.clusters), len(r.pre_existing)), (1, 0))
        # clean finding, $CHANGED carries the ./ -> still gates
        r2 = S.synthesize([f(category="logic", severity="blocker", file="A.swift")],
                          {"./A.swift"}, verify=lambda x: True)
        self.assertEqual((len(r2.clusters), len(r2.pre_existing)), (1, 0))

    def test_verification_blocker_gates_even_outside_diff(self):
        # a red build is emitted with file = scheme/target, not a changed path —
        # it must gate, not be scoped out to pre-existing.
        r = S.synthesize([f(category="verification", sourceAgent="swift-reviewer",
                            severity="blocker", file="Unleashed Mail (scheme)",
                            finding="xcodebuild build FAILED")],
                         self.CHANGED, verify=lambda x: True)
        self.assertEqual((len(r.clusters), len(r.pre_existing)), (1, 0))
        self.assertEqual(r.verdict.decision, "REQUEST_CHANGES")

    def test_parity_and_coverage_gate_outside_diff(self):
        for cat in ("parity", "test-coverage"):
            r = S.synthesize([f(category=cat, severity="blocker", file="(global)",
                               finding="gate")], self.CHANGED, verify=lambda x: True)
            self.assertEqual(len(r.pre_existing), 0, cat)
            self.assertEqual(r.verdict.decision, "REQUEST_CHANGES", cat)


class TestVerdict(unittest.TestCase):
    def _mixed(self):
        # keychain WARNING (routes as display primary) + token-race BLOCKER
        return S.cluster_findings([
            f(category="keychain", sourceAgent="security-reviewer", severity="warning",
              line=40, lineEnd=52, finding="kc"),
            f(category="token-race", sourceAgent="concurrency-reviewer", severity="blocker",
              line=44, lineEnd=48, finding="tr")])

    def test_lead_blocker_is_the_blocker_not_the_routed_primary(self):
        c = self._mixed()[0]
        self.assertEqual(c.severity, "blocker")
        self.assertEqual(c.primary.finding, "kc")        # ownership-routed display owner (warning)
        self.assertEqual(c.lead_blocker.finding, "tr")    # actual blocker — what the verify gate uses

    def test_verify_gate_targets_the_blocker(self):
        seen = {}
        S.decide_verdict(self._mixed(), lambda x: seen.setdefault("v", x.finding) or True)
        self.assertEqual(seen["v"], "tr")

    def test_verify_all_true_gates(self):
        r = S.synthesize([f(severity="blocker", confidence="low")], {"A.swift"}, verify=lambda x: True)
        self.assertEqual(r.verdict.decision, "REQUEST_CHANGES")

    def test_unconfirmable_blocker_needs_discussion(self):
        r = S.synthesize([f(severity="blocker", confidence="low")], {"A.swift"}, verify=lambda x: False)
        self.assertEqual(r.verdict.decision, "NEEDS_DISCUSSION")

    def test_warnings_only_approve_with_suggestions(self):
        r = S.synthesize([f(severity="warning")], {"A.swift"})
        self.assertEqual(r.verdict.decision, "APPROVE_WITH_SUGGESTIONS")

    def test_clean_approve(self):
        self.assertEqual(S.synthesize([], set()).verdict.decision, "APPROVE")

    def test_quarantined_findings_force_needs_discussion(self):
        # a malformed row could have hidden a blocker -> never a clean APPROVE
        bad = [({"bad": 1}, "schema error")]
        self.assertEqual(S.synthesize([f(severity="warning")], {"A.swift"},
                                      quarantined=bad).verdict.decision, "NEEDS_DISCUSSION")
        self.assertEqual(S.synthesize([], {"A.swift"},
                                      quarantined=bad).verdict.decision, "NEEDS_DISCUSSION")

    def test_cluster_gates_if_any_blocker_verifies_not_just_lead(self):
        # two blockers cluster (same family, overlapping lines); the lead fails
        # verification but the other passes -> the cluster must still gate.
        cs = S.cluster_findings([
            f(category="data-race", sourceAgent="concurrency-reviewer", severity="blocker",
              line=10, lineEnd=20, finding="race A"),
            f(category="data-race", sourceAgent="concurrency-reviewer", severity="blocker",
              line=12, lineEnd=18, finding="race B")])
        self.assertEqual(len(cs), 1)
        self.assertEqual(sum(1 for x in cs[0].findings if x.severity == "blocker"), 2)
        v = S.decide_verdict(cs, lambda b: b.finding == "race B")  # only the non-lead one
        self.assertEqual(v.decision, "REQUEST_CHANGES")


class TestRender(unittest.TestCase):
    def test_render_report_omits_verdict_sections(self):
        r = S.synthesize([f(severity="blocker")], {"A.swift"}, verify=lambda x: True)
        report = S.render_report(r)
        self.assertTrue(report.lstrip().startswith("### All Issues (Consolidated)"))
        self.assertNotIn("## Verdict", report)
        self.assertNotIn("## Needs Confirmation", report)

    def test_render_report_pre_existing_and_quarantine(self):
        r = S.Review([], S.Verdict("APPROVE"), [f(file="Z.swift")], [({"x": 1}, "bad row")])
        report = S.render_report(r)
        self.assertIn("Pre-existing", report)
        self.assertIn("Quarantined", report)

    def test_blocker_text_surfaces_in_ownership_routed_row(self):
        # a security keychain WARNING owns a token-race BLOCKER (ownership pair) — the
        # 🔴 row must lead with the blocker's text, not the routed warning's.
        r = S.synthesize([
            f(category="keychain", sourceAgent="security-reviewer", severity="warning",
              line=40, lineEnd=52, finding="keychain warning here", fix="rotate"),
            f(category="token-race", sourceAgent="concurrency-reviewer", severity="blocker",
              line=44, lineEnd=48, finding="TOKEN RACE blocker here", fix="add actor")],
            {"A.swift"}, verify=lambda x: True)
        report = S.render_report(r)
        self.assertIn("TOKEN RACE blocker here", report)
        self.assertIn("keychain", report)   # the routed warning is still cross-linked

    def test_table_cells_escape_pipes_and_newlines(self):
        # a literal `|` would add a table column; a newline would add a row
        r = S.synthesize([f(severity="warning", finding="has | pipe", fix="line1\nline2")], {"A.swift"})
        report = S.render_report(r)
        self.assertIn("has \\| pipe", report)
        self.assertIn("line1<br>line2", report)
        self.assertNotIn("line1\nline2", report)   # raw newline must not survive into the row


_VALID_RAW = dict(severity="warning", confidence="high", sourceAgent="x", category="logic",
                  file="A.swift", line=10, lineEnd=12, finding="f", evidence="e", fix="x")


class TestCliLoad(unittest.TestCase):
    """`_load` (standalone CLI path) must quarantine bad files, never crash."""

    def _write(self, d, name, content):
        path = os.path.join(d, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def test_malformed_json_file_is_quarantined_not_raised(self):
        with tempfile.TemporaryDirectory() as d:
            bad = self._write(d, "bad.json", "{ not valid json ")
            good = self._write(d, "good.json", json.dumps([_VALID_RAW]))
            findings, quarantined = S._load([bad, good])   # must not raise
            self.assertEqual(len(findings), 1)
            self.assertEqual(len(quarantined), 1)

    def test_wrong_top_level_shape_is_quarantined(self):
        with tempfile.TemporaryDirectory() as d:
            wrong = self._write(d, "w.json", json.dumps({"notFindings": 1}))
            findings, quarantined = S._load([wrong])
            self.assertEqual((len(findings), len(quarantined)), (0, 1))

    def test_object_with_findings_array_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            obj = self._write(d, "o.json", json.dumps({"findings": [_VALID_RAW]}))
            findings, quarantined = S._load([obj])
            self.assertEqual((len(findings), len(quarantined)), (1, 0))

    def test_help_flag_prints_usage_and_exits_zero(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = S.main(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("usage:", buf.getvalue())

    def test_explicit_missing_changed_file_fails_closed(self):
        # a typo'd --changed must NOT silently scope everything out and exit 0 APPROVE
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            rc = S.main(["--changed", "/no/such/changed_file_xyz.txt"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()


class TestS2CliGatingExitCode(CliFixture):
    """S2: `synthesize.py` main()'s gating exit code was unexecuted in BOTH directions. Proven by
    tripwire: replacing main()'s first success-path line with `raise` left the suite 231/231 OK, so
    no test reached the success path at all — the CLI is advertised as CI-droppable and nothing
    exercised it end to end (_load -> synthesize -> render -> gating exit)."""

    ANCHOR = '    return 0 if review.verdict.decision.startswith("APPROVE") else 1'

    def test_cli_exit_code_tracks_the_verdict(self):
        # Assert the VERDICT TEXT as well as the code. Exit 1 alone cannot discriminate: a gating
        # REQUEST_CHANGES and a non-gating NEEDS_DISCUSSION both exit 1, and exit 2 is emitted by
        # five different guards. The text is the only observable that separates them.
        rc, out, _ = self.run_main(S, [self.fj, "--changed", self.ch])
        self.assertIn("## Verdict (provisional): **REQUEST_CHANGES**", out)
        self.assertIn("hardcoded API key", out, "the finding itself must reach the report")
        self.assertEqual(rc, 1, "a gating verdict must exit non-zero for CI")

        rc0, out0, _ = self.run_main(S, [self.clean, "--changed", self.ch])
        self.assertIn("## Verdict (provisional): **APPROVE**", out0)
        self.assertEqual(rc0, 0, "a clean review must exit 0")

        # Third invocation, required by the above: a LOW-confidence blocker is NOT confirmed by the
        # default verify gate, so it lands in Needs Confirmation and does not gate. Same exit code
        # as REQUEST_CHANGES, different verdict — this is the pair rc cannot tell apart.
        rc1, out1, _ = self.run_main(S, [self.lowconf, "--changed", self.ch])
        self.assertIn("## Verdict (provisional): **NEEDS_DISCUSSION**", out1)
        self.assertEqual(rc1, 1)
        self.assertNotEqual(out1, out, "NEEDS_DISCUSSION must not render as REQUEST_CHANGES")

    def test_mutant_control_always_zero_would_green_a_ci_job(self):
        m = load_mutant(self, self.ANCHOR,
                        '    return 0  # MUTANT                                                  ')
        rc, out, _ = self.run_main(m, [self.fj, "--changed", self.ch])
        self.assertIn("REQUEST_CHANGES", out)
        self.assertEqual(rc, 0, "control must exhibit the fail-open: green CI with a blocker on screen")

    def test_mutant_control_always_one_would_red_every_job(self):
        m = load_mutant(self, self.ANCHOR,
                        '    return 1  # MUTANT                                                  ')
        rc, out, _ = self.run_main(m, [self.clean, "--changed", self.ch])
        self.assertIn("APPROVE", out)
        self.assertEqual(rc, 1, "control must exhibit the opposite failure: red CI on a clean review")


class TestS2DefaultVerifyGate(unittest.TestCase):
    """S2 cont. — `synthesize.py`'s default verify gate (:199), the predicate that decides whether a
    blocker is CONFIRMED (gating) or merely NEEDS CONFIRMATION (non-gating). Unpinned in both
    directions before this."""

    ANCHOR = '    return f.confidence == "high"'

    def test_default_verify_confirms_only_high_confidence(self):
        self.assertTrue(S.default_verify(f(severity="blocker", confidence="high")))
        for c in ("medium", "low"):
            self.assertFalse(S.default_verify(f(severity="blocker", confidence=c)), c)

    def test_verdict_through_the_default_gate(self):
        hi = S.synthesize([f(severity="blocker", confidence="high")], {"A.swift"})
        self.assertEqual(hi.verdict.decision, "REQUEST_CHANGES")
        self.assertEqual((len(hi.verdict.confirmed_blockers), len(hi.verdict.needs_confirmation)), (1, 0))
        lo = S.synthesize([f(severity="blocker", confidence="low")], {"A.swift"})
        self.assertEqual(lo.verdict.decision, "NEEDS_DISCUSSION")
        self.assertEqual((len(lo.verdict.confirmed_blockers), len(lo.verdict.needs_confirmation)), (0, 1))
        self.assertIn("### Needs Confirmation (non-gating)", S.render_markdown(lo))

    def test_mutant_control_confirm_everything(self):
        m = load_mutant(self, self.ANCHOR, "    return True  # MUTANT      ")
        self.assertEqual(m.synthesize([f(severity="blocker", confidence="low")],
                                      {"A.swift"}).verdict.decision, "REQUEST_CHANGES")

    def test_mutant_control_confirm_nothing(self):
        m = load_mutant(self, self.ANCHOR, "    return False  # MUTANT     ")
        self.assertEqual(m.synthesize([f(severity="blocker", confidence="high")],
                                      {"A.swift"}).verdict.decision, "NEEDS_DISCUSSION")


class TestS4ChangedGuardAdmitsAndRejects(CliFixture):
    """S4: the NARROWING half of the CLI's abs/traversal changed-path guard (:454). One member of a
    five-member `is_abs_or_traversal` family; the other four were pinned individually, this one was
    not. Both halves are needed and for different reasons — `_bad_changed = sorted(changed)` (reject
    EVERYTHING) passed the suite, and so did a POSIX-only narrowing that lets `../`, `~/` and `C:\\`
    through to a mis-scoped bogus APPROVE."""

    ANCHOR = "    _bad_changed = sorted({c for c in changed if is_abs_or_traversal(c)})"

    def test_a_normal_changeset_is_admitted(self):
        rc, out, err = self.run_main(S, [self.fj, "--changed", self.ch])
        self.assertNotIn("absolute/traversal", err)
        self.assertIn("REQUEST_CHANGES", out)
        self.assertEqual(rc, 1)

    def test_every_abs_or_traversal_form_is_rejected_by_name(self):
        # Assert WHICH diagnostic, not merely the code: several guards share exit 2, so an exit-code
        # assertion cannot tell this rejection from an unrelated one firing first.
        for entry in ("/abs/Auth.swift", "../MyApp/Auth.swift", "~/MyApp/Auth.swift",
                      "C:\\MyApp\\Auth.swift", "\\\\server\\share\\Auth.swift", "~user/Auth.swift"):
            with self.subTest(entry=entry):
                self._changed(entry)
                rc, out, err = self.run_main(S, [self.fj, "--changed", self.ch])
                self.assertIn("--changed contains absolute/traversal paths", err)
                self.assertIn(entry, err, "the diagnostic must name the offending entry")
                self.assertEqual(rc, 2)
                self.assertNotIn("Verdict", out, "a rejected changeset must not print a verdict")

    def test_mutant_control_posix_only_narrowing_fails_open_to_approve(self):
        m = load_mutant(self, self.ANCHOR,
                        '    _bad_changed = sorted({c for c in changed if c.startswith("/")})     ')
        for entry in ("../MyApp/Auth.swift", "~/MyApp/Auth.swift", "C:\\MyApp\\Auth.swift"):
            with self.subTest(entry=entry):
                self._changed(entry)
                rc, out, _ = self.run_main(m, [self.fj, "--changed", self.ch])
                self.assertIn("**APPROVE**", out, "control must exhibit the mis-scoped bogus APPROVE")
                self.assertEqual(rc, 0)

    def test_mutant_control_reject_everything_bricks_the_cli(self):
        m = load_mutant(self, self.ANCHOR,
                        "    _bad_changed = sorted(changed)                                       ")
        rc, _, err = self.run_main(m, [self.fj, "--changed", self.ch])
        self.assertIn("MyApp/Auth.swift", err)
        self.assertEqual(rc, 2, "control must exhibit the opposite failure: every changeset rejected")


class TestS4ChangedFlagWithoutValue(CliFixture):
    """T6-adjacent, landed with S4 because it shares the fixture: `--changed` as the LAST argv token
    leaves `changed_path` None, and without the explicit None arm `os.path.exists(None)` raises
    TypeError — a traceback where a diagnostic belongs."""

    def test_trailing_changed_flag_gets_a_diagnostic_not_a_traceback(self):
        rc, _, err = self.run_main(S, [self.fj, "--changed"])
        self.assertIn("error: --changed file not found: None", err)
        self.assertEqual(rc, 2)

    def test_mutant_control_without_the_none_arm_raises_typeerror(self):
        m = load_mutant(
            self,
            "    if changed_explicit and (changed_path is None or not os.path.exists(changed_path)):",
            "    if changed_explicit and (not os.path.exists(changed_path)):" + " " * 26)
        with self.assertRaises(TypeError):
            self.run_main(m, [self.fj, "--changed"])


class TestS5ClusterNeverCollapsesALineDimension(unittest.TestCase):
    """S5, LINE dimension (`synthesize.py:61`). A file-level finding is `line == 0` but MAY still
    carry a non-zero `lineEnd`. Without the guard, `a.line <= b.lineEnd and b.line <= a.lineEnd`
    reads 0 <= 4 and 3 <= 120 — the file-level finding absorbs the line-range one, whose row and
    `loc` vanish from the consolidated table while clusterSize doubles. clusterSize is rendered as
    corroboration weight, so the same mutation simultaneously DROPS a finding and INFLATES the
    apparent confidence of the one that swallowed it."""

    ANCHOR = "    if a.line == 0 or b.line == 0:"

    def _pair(self):
        return (f(category="logic", line=0, lineEnd=120, finding="FILE-LEVEL", fix="FIX_FILE"),
                f(category="error-handling", line=3, lineEnd=4, finding="LINE-RANGE", fix="FIX_LINE"))

    def test_file_level_finding_with_a_line_end_never_absorbs_a_line_range_one(self):
        a, b = self._pair()
        self.assertEqual((a.line, a.lineEnd), (0, 120),
                         "premise: a file-level finding CAN carry a non-zero lineEnd")
        self.assertFalse(S._overlap(a, b))
        r = S.synthesize([a, b], {"A.swift"})
        self.assertEqual(sorted(len(c.findings) for c in r.clusters), [1, 1],
                         "clusterSize is corroboration weight — it must not be inflated by absorption")
        report = S.render_report(r)
        self.assertIn("A.swift (file-level)", report)
        self.assertIn("A.swift:3-4", report, "the line-range finding keeps its own row and loc")

    def test_both_file_level_still_cluster(self):
        # The narrowing half: two genuine file-level findings SHOULD still cluster, so the guard
        # cannot simply be `return False` for anything touching line 0.
        cs = S.cluster_findings([f(category="logic", line=0, lineEnd=0),
                                 f(category="error-handling", line=0, lineEnd=0)])
        self.assertEqual(len(cs), 1)

    def test_mutant_control_without_the_guard_the_file_level_row_absorbs_it(self):
        m = load_mutant(self, self.ANCHOR, "    if False:  # MUTANT               ")
        a, b = self._pair()
        self.assertTrue(m._overlap(a, b))
        r = m.synthesize([a, b], {"A.swift"})
        self.assertEqual([len(c.findings) for c in r.clusters], [2])
        self.assertNotIn("A.swift:3-4", m.render_report(r), "control: the line-range loc disappears")


class TestS5ClusterNeverCollapsesBFileDimension(unittest.TestCase):
    """S5, FILE dimension (`synthesize.py:92`) — found by the critic, absent from the sweep. The same
    class of defect one axis over: drop the `a.file != b.file` half and two findings in DIFFERENT
    files cluster whenever their line ranges happen to overlap. Line numbers collide constantly
    across files, so this is not an exotic input — it is the common case."""

    ANCHOR = "    if a.file != b.file or not _overlap(a, b):"

    def _pair(self):
        return (f(category="logic", file="A.swift", line=10, lineEnd=20, finding="IN-A", fix="FIX_A"),
                f(category="logic", file="B.swift", line=12, lineEnd=18, finding="IN-B", fix="FIX_B"))

    def test_findings_in_different_files_never_cluster(self):
        a, b = self._pair()
        self.assertTrue(S._overlap(a, b), "premise: the LINE ranges do overlap — only the file differs")
        self.assertFalse(S._candidate(a, b))
        r = S.synthesize([a, b], {"A.swift", "B.swift"})
        self.assertEqual(sorted(len(c.findings) for c in r.clusters), [1, 1])
        report = S.render_report(r)
        self.assertIn("A.swift:10-20", report)
        self.assertIn("B.swift:12-18", report, "the finding in the other file keeps its own row")
        self.assertIn("IN-A", report)
        self.assertIn("IN-B", report)

    def test_same_file_overlapping_still_clusters(self):
        # Narrowing half: the file check must not become `return False` for everything.
        a, b = self._pair()
        b_same = f(category="logic", file="A.swift", line=12, lineEnd=18, finding="IN-B", fix="FIX_B")
        self.assertTrue(S._candidate(a, b_same))
        self.assertEqual(len(S.cluster_findings([a, b_same])), 1)

    def test_mutant_control_without_the_file_check_a_finding_vanishes(self):
        m = load_mutant(self, self.ANCHOR,
                        "    if not _overlap(a, b):  # MUTANT: file check dropped")
        a, b = self._pair()
        self.assertTrue(m._candidate(a, b), "control premise: the mutant treats them as one defect")
        r = m.synthesize([a, b], {"A.swift", "B.swift"})
        self.assertEqual([len(c.findings) for c in r.clusters], [2],
                         "control: clusterSize doubles — rendered as corroboration weight")
        report = m.render_report(r)
        self.assertNotIn("B.swift:12-18", report, "control: the other file's loc disappears")


class TestS1EmptyChangesetCauseClauseIsSharedAndTrue(unittest.TestCase):
    """The empty-changeset refusal exists on TWO entry points that must stay identical — the CLI and
    `mcp_server._call_synthesize`. This module has now been bitten THREE times by those twins drifting
    (S1 itself; the `findings_explicit` vs `findings_in` predicate; and this wording), so the cause
    clause lives in ONE constant that both import, and this cell pins that.

    It also pins the clause's TRUTH. It used to read "every finding would mis-scope to pre-existing",
    which is a FALSE UNIVERSAL (codex, PR #77): `in_gating_scope` keeps a finding gating regardless of
    `changed_files` when its family is in `_ALWAYS_GATING_FAMILIES` or its scope is
    "structural-pipeline", so those rows would not mis-scope at all."""

    _ROW = dict(severity="blocker", confidence="high", sourceAgent="security-reviewer",
                category="credential", file="A.swift", line=1, lineEnd=1, finding="k",
                evidence="e", fix="x")

    def test_both_arms_emit_the_same_cause_clause(self):
        # Assert the EMITTED message on BOTH arms, not merely that a shared constant exists. An
        # earlier version asserted `assertIs` on the constant alone — and a mutant that hardcoded a
        # different literal at the MCP raise site SURVIVED it, because the constant was still shared,
        # just unused. Importing a constant is a mechanism; emitting it is the outcome.
        import mcp_server as MS
        self.assertIs(MS._EMPTY_CHANGESET_CAUSE, S._EMPTY_CHANGESET_CAUSE,
                      "the twins must share ONE constant, not two equal literals that can drift")

        with self.assertRaises(Exception) as caught:
            MS._call_synthesize({"findings": [self._ROW], "changed_files": []})
        self.assertIn(S._EMPTY_CHANGESET_CAUSE, str(caught.exception),
                      "the MCP arm must EMIT the shared cause clause, not merely import it")

        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "f.json")
            with open(fp, "w", encoding="utf-8") as fh:
                json.dump({"findings": [dict(severity="blocker", confidence="high",
                                             sourceAgent="security-reviewer", category="credential",
                                             file="A.swift", line=1, lineEnd=1, finding="k",
                                             evidence="e", fix="x")]}, fh)
            ch = os.path.join(d, "changed.txt")
            open(ch, "w").close()
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc = S.main([fp, "--changed", ch])
            self.assertEqual(rc, 2)
            cli_err = err.getvalue()
        self.assertIn(S._EMPTY_CHANGESET_CAUSE, cli_err,
                      "the CLI must state the shared cause clause verbatim")

    def test_the_cause_clause_does_not_claim_EVERY_finding_mis_scopes(self):
        # The false universal this replaced. Proven false below by the sibling cell.
        self.assertNotIn("every finding", S._EMPTY_CHANGESET_CAUSE.lower())

    def test_a_globally_gating_finding_really_would_not_mis_scope(self):
        # PROOF that the old wording was false, and the reason the new wording is narrowed. Bypass the
        # guard by calling the library entry point directly with an empty changeset: a structural-
        # pipeline finding does NOT land in pre_existing — it gates.
        # BOTH global-gating mechanisms, because `in_gating_scope` has two independent ones and an
        # earlier version of this cell exercised only `scope`: mutating the `_ALWAYS_GATING_FAMILIES`
        # branch left it green, so the cell did not cover what its own docstring claimed.
        globals_ = [
            ("scope", f(severity="blocker", confidence="high", category="logic",
                        file="A.swift", scope="structural-pipeline")),
            ("family:verification", f(severity="blocker", confidence="high", category="verification",
                                      file="A.swift")),
            ("family:parity", f(severity="blocker", confidence="high", category="parity",
                                file="A.swift")),
            ("family:test-coverage", f(severity="blocker", confidence="high", category="test-coverage",
                                       file="A.swift")),
        ]
        for mechanism, glob_blocker in globals_:
            with self.subTest(mechanism=mechanism):
                r = S.synthesize([glob_blocker], set())
                self.assertEqual(r.pre_existing, [],
                                 f"a globally-gating finding ({mechanism}) must not mis-scope")
                self.assertEqual(r.verdict.decision, "REQUEST_CHANGES")

        # ...and the contrast that makes the refusal correct for everything else.
        dep_blocker = f(severity="blocker", confidence="high", category="credential", file="A.swift")
        r2 = S.synthesize([dep_blocker], set())
        self.assertEqual(len(r2.pre_existing), 1, "a changed-file-dependent finding DOES mis-scope")
        self.assertTrue(r2.verdict.decision.startswith("APPROVE"),
                        "which is exactly the bogus APPROVE the guard exists to refuse")

    def test_the_refusal_is_per_input_not_per_row(self):
        # Deliberate, and documented: a globally-gating finding is refused ALONGSIDE the rest rather
        # than split out. Splitting it would make the CLI answer where the MCP twin refuses — the
        # exact drift this class exists to prevent. Recorded as behaviour so a future change is a
        # deliberate one on BOTH arms, not an accident on one.
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "f.json")
            with open(fp, "w", encoding="utf-8") as fh:
                json.dump({"findings": [dict(severity="blocker", confidence="high",
                                             sourceAgent="security-reviewer", category="logic",
                                             file="A.swift", line=1, lineEnd=1, finding="k",
                                             evidence="e", fix="x", scope="structural-pipeline")]}, fh)
            ch = os.path.join(d, "changed.txt")
            open(ch, "w").close()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(S.main([fp, "--changed", ch]), 2)
