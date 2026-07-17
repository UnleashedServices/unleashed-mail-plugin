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
    # CONTRACT (COREDEV-2504, gemini review rounds 1-3 + a 6-lens adversarial completeness sweep):
    # among strings that are RECOGNISABLE references to this variable — a `$` + the correctly-spelled ASCII
    # name CLAUDE_PLUGIN_ROOT (any case) — every one must be the exact `${CLAUDE_PLUGIN_ROOT}` token, because
    # Claude Code substitutes ONLY that literal inline; anything else (fallback `:-.`, suffix typo, unbraced,
    # or spaces inside the braces) reaches the shell verbatim and resolves to `.` in a consumer install.
    # Two branches, NO `\b` immediately after ROOT (that boundary silently drops same-word suffix typos —
    # the round-1 hole, which gemini's own round-2/3 replacement suggestions each reintroduced):
    #   1. braced   `\$\{\s*CLAUDE_PLUGIN_ROOT[^}\n]*\}?` — `\s*` tolerates `${ CLAUDE_PLUGIN_ROOT }`;
    #      `[^}\n]*` swallows any suffix/operator (`_DIR`, `:-.`, `:?`, `#…`) up to the brace, so it matches
    #      as ONE non-exact token → flagged. Also catches an unterminated `${CLAUDE_PLUGIN_ROOT`.
    #   2. unbraced `\$CLAUDE_PLUGIN_ROOT[a-zA-Z0-9_]*` — matches `$CLAUDE_PLUGIN_ROOT[suffix]` precisely,
    #      WITHOUT greedily eating the rest of the line (the round-2 imprecision).
    # re.IGNORECASE folds in case variants (`${claude_plugin_root}`) — the one high-plausibility miss.
    # DELIBERATELY OUT OF CONTRACT (pinned in test_out_of_contract_spellings_are_deliberately_not_flagged):
    # identifier MISSPELLINGS (`${CLADUE_…}`), invisible/unicode homoglyphs (ZWSP, BOM, full-width `＄`), and
    # the-exact-token-plus-a-stray-char (`${CLAUDE_PLUGIN_ROOT}}`). Those are unbounded generic-typo /
    # unicode-hygiene concerns a token regex cannot own without false positives — a separate check's job.
    _ANY = re.compile(r"\$\{\s*CLAUDE_PLUGIN_ROOT[^}\n]*\}?|\$CLAUDE_PLUGIN_ROOT[a-zA-Z0-9_]*", re.IGNORECASE)

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

    def _verdict(self, s):
        # Guard verdict := FAIL iff any regex match != the exact token (i.e. a non-exact reference exists).
        matches = self._ANY.findall(s)
        return "FAIL" if any(m != "${CLAUDE_PLUGIN_ROOT}" for m in matches) else "PASS"

    def test_guard_regex_flags_adversarial_spellings(self):
        # COREDEV-2504 (gemini rounds 1-3 + completeness sweep): pin the guard's behaviour so a future
        # "cleanup" that reintroduces a `\b`-after-ROOT (silently drops suffix typos), loses `\s*` (spacing),
        # or drops re.IGNORECASE (case) is caught HERE — not by luck of a real file containing the typo.
        must_flag = [
            "${CLAUDE_PLUGIN_ROOT:-.}",                             # the bug this whole ticket fixes
            "${CLAUDE_PLUGIN_ROOT_DIR}",                            # round-1 hole: same-word suffix typo
            "${CLAUDE_PLUGIN_ROOTT}",                               # round-1 hole
            "$CLAUDE_PLUGIN_ROOT",                                  # unbraced
            "echo $CLAUDE_PLUGIN_ROOT and more text",              # round-2: unbraced + trailing text
            "$CLAUDE_PLUGIN_ROOTX/scripts",                        # unbraced suffix typo
            "${CLAUDE_PLUGIN_ROOT}/a ${CLAUDE_PLUGIN_ROOT_DIR}/b",  # a valid + a bad on one line
            "${CLAUDE_PLUGIN_ROOT:?err}",                          # :? param form
            "${CLAUDE_PLUGIN_ROOT",                                 # unterminated brace
            "${ CLAUDE_PLUGIN_ROOT }",                             # round-3: spaces inside braces
            "${ CLAUDE_PLUGIN_ROOT}",                             # round-3: leading space only
            "${CLAUDE_PLUGIN_ROOT }",                             # round-3: trailing space only
            "${claude_plugin_root}",                               # sweep: all-lowercase (case)
            "${CLAUDE_PLUGIN_Root}",                               # sweep: mixed case
            "$claude_plugin_root",                                 # sweep: unbraced lowercase
        ]
        must_pass = [
            "${CLAUDE_PLUGIN_ROOT}",
            "Run ${CLAUDE_PLUGIN_ROOT}/scripts/x.py and echo done",
            "See ${CLAUDE_PLUGIN_ROOT} then $HOME/x",
            "${CLAUDE_PLUGIN_ROOT}/a ${CLAUDE_PLUGIN_ROOT}/b",     # two valid on one line
            "prefix${CLAUDE_PLUGIN_ROOT}suffix",
            "the CLAUDE_PLUGIN_ROOT variable, in prose (no $) — not a substitution site",
            "no reference at all",
        ]
        for s in must_flag:
            self.assertEqual(self._verdict(s), "FAIL", f"COREDEV-2504: guard must FLAG {s!r} (findall={self._ANY.findall(s)})")
        for s in must_pass:
            self.assertEqual(self._verdict(s), "PASS", f"COREDEV-2504: guard must PASS {s!r} (findall={self._ANY.findall(s)})")

    def test_out_of_contract_spellings_are_deliberately_not_flagged(self):
        # COREDEV-2504 scope boundary — pinned so it is an INTENTIONAL design decision, not an oversight,
        # and so bot review round N+1 has a documented answer. A 6-lens adversarial sweep enumerated ~60
        # non-exact spellings; these three classes are deliberately OUT of this token guard's contract:
        #   (a) identifier MISSPELLINGS — a reference to a *different* (non-existent) variable name; catching
        #       every transposition/missing-underscore is unbounded fuzzy matching a regex cannot own;
        #   (b) invisible/unicode homoglyphs — a non-ASCII/hidden-char hygiene concern for a separate linter,
        #       not a `${…}`-token spelling check (chasing it in this regex risks false positives on prose);
        #   (c) the EXACT token plus a stray adjacent char (`${CLAUDE_PLUGIN_ROOT}}`, `$${…}`) — the token
        #       itself IS spelled correctly and Claude Code substitutes it; the stray brace/dollar is a
        #       different lexical bug, and flagging it cannot be distinguished from a legit `${…}/path` suffix
        #       without over-matching.
        # If the team later wants any of these caught, that is a NEW ticket that consciously flips a line here.
        out_of_contract = [
            "${CLADUE_PLUGIN_ROOT}",          # (a) transposition typo -> different name
            "${CLAUDE_PLGUIN_ROOT}",          # (a) transposition typo
            "${CLAUDEPLUGIN_ROOT}",           # (a) missing underscore
            "${​CLAUDE_PLUGIN_ROOT}",    # (b) zero-width space after brace
            "＄{CLAUDE_PLUGIN_ROOT}",     # (b) full-width dollar homoglyph
            "${CLAUDE_PLUGIN_ROOT}}",         # (c) exact token + stray trailing brace
            "$${CLAUDE_PLUGIN_ROOT}",         # (c) exact token + escaped leading dollar
        ]
        for s in out_of_contract:
            self.assertEqual(self._verdict(s), "PASS",
                             f"COREDEV-2504: {s!r} is documented OUT of the guard's contract — if this now "
                             f"FLAGs, update the contract comment + this test intentionally (findall={self._ANY.findall(s)})")

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
