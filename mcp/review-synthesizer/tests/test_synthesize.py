"""Deterministic synthesis: dedup, ownership routing, scope, verdict, render."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import synthesize as S  # noqa: E402
from schema import parse_finding  # noqa: E402


def f(**over):
    d = dict(severity="warning", confidence="high", sourceAgent="x", category="logic",
             file="A.swift", line=10, lineEnd=12, finding="f", evidence="e", fix="x")
    d.update(over)
    return parse_finding(d)


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


class TestOwnershipRouting(unittest.TestCase):
    def test_a11y_authoritative(self):
        fs = [f(category="curator-tokens", sourceAgent="accessibility-auditor", severity="warning"),
              f(category="curator-tokens", sourceAgent="accessibility-auditor", severity="blocker")]
        self.assertEqual(S.route_owner(fs).severity, "blocker")

    def test_security_owns_credential_race(self):
        fs = [f(category="keychain", sourceAgent="security-reviewer", line=40, lineEnd=52),
              f(category="token-race", sourceAgent="concurrency-reviewer", line=44, lineEnd=48)]
        self.assertEqual(S.route_owner(fs).family, "security")


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


if __name__ == "__main__":
    unittest.main()
