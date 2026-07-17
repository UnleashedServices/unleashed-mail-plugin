"""COREDEV-2503 doc-lint mutation proofs: F6 (swift-reviewer Step-4 fail-closed), F13 (CFR state-machine
contradictions), F9 (provider-parity gate drift), B7 (CFR protocol consistency across the 3 files). Each
assertion flips if the corresponding doc fix is reverted."""
import os
import re
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(rel):
    with open(os.path.join(_ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


class F6_Step4FailClosed(unittest.TestCase):
    def test_step4_uses_bare_root_token_and_propagates_exit(self):
        # COREDEV-2504: Step-4 must reference the plugin script via the BARE ${CLAUDE_PLUGIN_ROOT} token
        # (Claude Code substitutes it inline in agent bodies; the `:-.` form is NOT substituted → resolves
        # to `.` = the consumer repo). Both strings are unique to the Step-4 build-verify fence.
        src = _read("agents/swift-reviewer.md")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/review/build-verify.sh", src,
                      "COREDEV-2504: Step-4 must use the bare ${CLAUDE_PLUGIN_ROOT} token (not the :-. form)")
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT:-.}/scripts/review/build-verify.sh", src,
                         "COREDEV-2504: the :-. fallback form must NOT reappear at Step-4")
        self.assertIn('exit "$BUILD_VERIFY"', src,
                      "F6: Step-4 must exit the propagated code (fail closed on 127), not end on echo")


class COREDEV2504_PluginRootConvention(unittest.TestCase):
    """COREDEV-2504: agent/skill BODIES must reference the plugin root ONLY via the exact, inline-substituted
    `${CLAUDE_PLUGIN_ROOT}` token. Claude Code does not substitute the bash-fallback `${…:-.}` (nor `-.`,
    `:?`, `:=`, unbraced `$CLAUDE_PLUGIN_ROOT`), so those reach the shell literally → unset var → `.` (the
    consumer repo). This guard fails if ANY non-exact spelling is (re)introduced."""

    _TREES = ("agents", "skills")
    # NOTE: `[a-zA-Z0-9_]*` BEFORE the word boundary is load-bearing (gemini COREDEV-2504 review):
    # a bare `\b` right after ROOT does NOT match a same-word suffix typo like `${CLAUDE_PLUGIN_ROOT_DIR}`
    # or `${CLAUDE_PLUGIN_ROOTT}` (T→_ / T→T is not a boundary) → the typo yields NO match and silently
    # passes the exact-token assertion. Consuming trailing word chars makes the whole mis-spelled token
    # match, so it is compared against — and flagged as — a non-exact spelling.
    _ANY = re.compile(r"\$\{?CLAUDE_PLUGIN_ROOT[a-zA-Z0-9_]*\b[^}\n]*\}?")

    def _md_files(self):
        for tree in self._TREES:
            base = os.path.join(_ROOT, tree)
            for dirpath, _dirs, files in os.walk(base):
                for fn in files:
                    if fn.endswith(".md"):
                        yield os.path.relpath(os.path.join(dirpath, fn), _ROOT)

    def test_every_occurrence_is_the_exact_bare_token(self):
        bad = []
        for rel in self._md_files():
            for m in self._ANY.findall(_read(rel)):
                if m != "${CLAUDE_PLUGIN_ROOT}":
                    bad.append(f"{rel}: {m!r}")
        self.assertEqual(bad, [], f"COREDEV-2504: only the exact ${{CLAUDE_PLUGIN_ROOT}} token is allowed: {bad}")

    def test_gate_script_references_present_via_bare_token(self):
        # Defense-in-depth (codex R2): catch someone DELETING the token + replacing with a repo-relative
        # path — the syntax guard above would then pass. Assert each gate-critical script is still referenced
        # via the bare token.
        expect = {
            "agents/swift-reviewer.md": ["${CLAUDE_PLUGIN_ROOT}/scripts/review/reviewer-roster.sh",
                                         "${CLAUDE_PLUGIN_ROOT}/scripts/review/build-verify.sh",
                                         "${CLAUDE_PLUGIN_ROOT}/scripts/lib/context.sh"],
            "skills/create-feature-plan/SKILL.md": ["${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py"],
            "skills/review-synthesis/SKILL.md": ["${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py"],
            "skills/brainstorm/SKILL.md": ["${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py"],
            "skills/implement/SKILL.md": ["${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py"],
            "skills/codex-review/SKILL.md": ["${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py"],
            "skills/gemini-review/SKILL.md": ["${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py"],
        }
        for rel, refs in expect.items():
            src = _read(rel)
            for ref in refs:
                self.assertIn(ref, src, f"COREDEV-2504: {rel} lost the bare-token reference {ref!r}")

    def test_codex_review_pty_timeout_is_1200(self):
        # COREDEV-2504 medium: the two codex-review pty caps must be 1200s (xhigh survives), not 600.
        src = _read("skills/codex-review/SKILL.md")
        self.assertEqual(src.count("--timeout 1200"), 2, "codex-review must use --timeout 1200 (x2)")
        self.assertNotIn("--timeout 600", src, "codex-review must not keep the 600s cap that SIGTERMs xhigh")


class F13_CFRStateMachine(unittest.TestCase):
    def test_no_unlabelled_conflation(self):
        src = _read("agents/jira-manager.md")
        self.assertNotIn("leave the issue UNLABELLED", src,
                         "F13(a): a cfr-needs-human issue is not UNLABELLED — say 'without the counted label'")
        self.assertIn("without the counted `change-failure` label", src)

    def test_reattribution_vs_resolution_distinguished(self):
        src = _read("agents/jira-manager.md")
        # the swap-back (re-attribution) must be distinguished from the terminal 'resolution' clear
        self.assertIn("re-attribution", src, "F13(b): re-attribution swap must be a named, non-terminal move")
        self.assertIn("resolution", src, "F13(b): the terminal-only rule governs *resolution*, not the swap")


class F9_ParityGateModel(unittest.TestCase):
    def test_reviewer_references_capability_model(self):
        src = _read("agents/swift-reviewer.md")
        self.assertIn("ServiceCapabilities", src, "F9: parity gate must reference the ServiceCapabilities model")
        self.assertIn("ProviderParityError", src, "F9: a sanctioned gap is a ProviderParityError throw")
        self.assertIn('is NOT "an implementation in both"', src,
                      "F9: a throwing stub must not be accepted as an implementation")

    def test_contract_source_of_truth_updated(self):
        src = _read("AGENT_CONTRACTS.md")
        self.assertIn("ServiceCapabilities", src)
        self.assertIn("ProviderParityError", src)


class B7_CFRProtocolConsistency(unittest.TestCase):
    FILES = ("agents/jira-manager.md", "agents/release-manager.md", "AGENT_CONTRACTS.md")

    def test_label_names_consistent(self):
        for rel in self.FILES:
            src = _read(rel)
            for label in ("change-failure", "cfr-triage-pending", "cfr-needs-human"):
                self.assertIn(label, src, f"B7: {rel} must mention the CFR label `{label}`")

    def test_verdict_vocab_consistent_across_all_three(self):
        # every CFR file must agree on the causation trichotomy (no drift)
        for rel in self.FILES:
            low = _read(rel).lower()
            for term in ("confirmed", "pre-existing", "unconfirmed"):
                self.assertIn(term, low, f"B7: {rel} must name the `{term}` verdict")

    def test_resolution_outcomes_in_resolution_owners(self):
        # the RESOLUTION owners (jira-manager mechanics + the §12 contract) name all three terminal
        # outcomes incl. human dismissal; release-manager owns the verdict, not the resolution, so it is
        # deliberately excluded here.
        for rel in ("agents/jira-manager.md", "AGENT_CONTRACTS.md"):
            low = _read(rel).lower()
            self.assertIn("change-failure", low)
            self.assertIn("pre-existing", low, f"B7: {rel} must name the proven-pre-existing terminal")
            self.assertIn("dismiss", low, f"B7: {rel} must name the human-dismissal terminal")


if __name__ == "__main__":
    unittest.main()
