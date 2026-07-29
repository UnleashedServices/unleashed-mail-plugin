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


class COREDEV2583_DocDefects(unittest.TestCase):
    """§4.10 — all FOUR verified documentation defects, each independently mutation-proved.

    Round 1 of this plan's gate promised assertions for only two of the four, which contradicted
    its own §3 ("CI must be able to tell") and §6's blanket mutation requirement.
    """

    # (a) README claimed "All five review agents now run on `opus`" — false then (all five pinned
    #     `sonnet`) and still false after §4.2 (3 of 5), which is worse because it reads plausible.
    def test_a_readme_does_not_claim_all_five_reviewers_are_opus(self):
        readme = _read("README.md")
        self.assertNotIn("All five review agents now run on `opus`", readme)
        self.assertNotRegex(readme, r"all five review agents.{0,20}`opus`",
                            "README must not re-assert the uniform-opus claim in any casing")

    def test_a_readme_states_the_actual_tiering(self):
        readme = _read("README.md")
        for agent in ("security-reviewer", "prompt-review", "concurrency-reviewer"):
            self.assertIn(agent, readme, f"README must name {agent} as an `opus` reviewer")

    # (b) the alias list must be complete against the pinned runtime table.
    def test_b_claude_md_alias_list_is_complete(self):
        claude_md = _read("CLAUDE.md")
        for alias in ("`best`", "`opusplan`", "`sonnet[1m]`", "`opus[1m]`", "`fable[1m]`"):
            self.assertIn(alias, claude_md, f"CLAUDE.md model alias list omits {alias}")

    def test_b_claude_md_denies_the_nonexistent_default_alias(self):
        # `default` is NOT in the runtime table; an earlier draft of this plan proposed adding it.
        self.assertIn("no** `default` alias", _read("CLAUDE.md"))

    def test_b_claude_md_documents_the_mandatory_effort_pin(self):
        claude_md = _read("CLAUDE.md")
        self.assertIn("`effort: xhigh`", claude_md)
        self.assertIn("CLAUDE_CODE_EFFORT_LEVEL", claude_md,
                      "the honest limit (the env var outranks frontmatter) must be stated")

    # (c) alias vs version pin — the old guidance argued against something the alias does not do.
    def test_c_alias_versus_version_pin_is_distinguished(self):
        for rel in ("CLAUDE.md", "AGENT_CONTRACTS.md"):
            with self.subTest(rel=rel):
                text = _read(rel)
                self.assertNotIn("Prefer `inherit`/`sonnet` over hard-pinning `opus`", text,
                                 f"{rel} still carries the superseded alias/pin conflation")
                self.assertIn("alias", text)

    # (d) no agent body may teach from a superseded model id.
    def test_d_no_agent_body_cites_a_superseded_model_id(self):
        stale = re.compile(r"claude-(?:sonnet|opus|haiku)-4-\d")
        offenders = []
        agents_dir = os.path.join(_ROOT, "agents")
        for name in sorted(os.listdir(agents_dir)):
            if not name.endswith(".md"):
                continue
            for m in stale.finditer(_read(os.path.join("agents", name))):
                offenders.append(f"{name}: {m.group(0)}")
        self.assertEqual(offenders, [],
                         "agent bodies must not teach from a superseded model id")


class COREDEV2602_AgentOutputStyle(unittest.TestCase):
    """§13 Agent Output Style — per-rule assertions are ROW-scoped; per-contract are SECTION-scoped.

    The two are NOT interchangeable. A section-scoped per-rule assertion false-passes, because a
    rule's marker phrase also occurs in the precedence clause and elsewhere in §13 — that was the
    round-7 defect. Row scoping is what makes a deleted disposition detectable.
    """

    # --- extraction helpers: read the artifact, never restate expectations ------------------
    def _section13(self):
        text = _read("AGENT_CONTRACTS.md")
        start = text.index("## 13. Agent Output Style")
        end = text.index("## Cross-references", start)
        return text[start:end]

    def _rows(self):
        """rule number -> its single disposition row.

        §13's table is `| # | Rule | Disposition |` — three columns, four pipes. Derive the shape
        from the header rather than hardcoding a count, so a future column cannot silently make
        every row invisible and turn this whole class into a no-op.
        """
        lines = self._section13().split("\n")
        header = next(l for l in lines if l.startswith("| # |"))
        ncols = header.count("|")
        rows = {}
        for line in lines:
            m = re.match(r"^\| (\d+) \|", line)
            if m and line.count("|") == ncols:
                self.assertNotIn(int(m.group(1)), rows,
                                 f"rule {m.group(1)} has more than one disposition row")
                rows[int(m.group(1))] = line
        return rows

    # --- the section exists and is complete -------------------------------------------------
    def test_section_13_exists_before_cross_references(self):
        text = _read("AGENT_CONTRACTS.md")
        self.assertIn("## 13. Agent Output Style", text)
        self.assertLess(text.index("## 13. Agent Output Style"),
                        text.index("## Cross-references"))

    def test_exactly_ten_dispositions_one_row_each(self):
        self.assertEqual(sorted(self._rows()), list(range(1, 11)))

    def test_every_rule_declares_an_explicit_disposition(self):
        # A blanked or flipped Disposition cell must fail — asserting titles + markers alone
        # would not catch it (round-8 finding).
        expected = {1: "Adapted", 2: "Adapted", 3: "Adapted", 4: "Adapted", 5: "Adapted",
                    6: "Adapted", 7: "Adopted", 8: "Adopted", 9: "Restated positively",
                    10: "Adapted"}
        rows = self._rows()
        for n, disposition in expected.items():
            with self.subTest(rule=n):
                self.assertIn(f"**{disposition}**", rows[n],
                              f"rule {n} must declare `{disposition}` explicitly")

    # --- per-rule markers: ROW-scoped ---------------------------------------------------------
    def test_each_adapted_rule_carries_its_marker_in_its_own_row(self):
        markers = {
            1: "never reorder a mandated payload",
            2: "keep their mandated single-line/schema shape",
            3: "per the payload-region invariant",
            4: "defer an in-scope finding out of the current array",
            5: "never before a mandated result prefix",
            6: "whoever runs the steps",
            9: "cap, split, omit, or defer",
            10: "payload, not preamble",
        }
        rows = self._rows()
        for n, marker in markers.items():
            with self.subTest(rule=n):
                self.assertIn(marker, rows[n],
                              f"rule {n}'s marker must be literal IN ITS OWN ROW (row-scoped)")

    def test_parser_touching_rules_reference_the_invariant_by_name(self):
        rows = self._rows()
        # The approved plan requires 1, 2, 3, 5 AND 10 to reference it by name.
        for n in (1, 2, 3, 5, 10):
            with self.subTest(rule=n):
                self.assertIn("payload-region invariant", rows[n])

    # --- the invariant: SECTION-scoped --------------------------------------------------------
    def test_payload_region_invariant_is_present_on_one_physical_line(self):
        # One physical line by construction: a Markdown line break inside the marker made exact
        # matching fail against a CORRECT document in round 10.
        marker = "Within it, nothing but detail fields and blank lines."
        lines = [l for l in self._section13().split("\n") if marker in l]
        self.assertTrue(lines, "the invariant marker must appear literally on a single line")

    def test_invariant_covers_non_prose_payloads_too(self):
        # It breaks on ANY non-detail content, not only prose — a stray VERDICT: included.
        self.assertIn("VERDICT:", self._section13())

    # --- the precedence clause: SECTION-scoped, all six contracts ------------------------------
    def test_precedence_clause_names_all_six_contracts(self):
        section = self._section13()
        for contract in ("JSON findings array", "`Status:`", "Remaining", "`VERDICT:`",
                         "final fenced JSON block", "BLOCKED"):
            with self.subTest(contract=contract):
                self.assertIn(contract, section)

    def test_precedence_clause_states_the_contract_wins(self):
        self.assertIn("the contract wins and the rule yields", self._section13())

    def test_remaining_is_marked_safety_information(self):
        self.assertIn("never a list to shorten", self._section13())

    # --- attribution -------------------------------------------------------------------------
    def test_attribution_names_the_source_licence_and_pinned_commit(self):
        section = self._section13()
        self.assertIn("i-have-adhd", section)
        self.assertIn("MIT", section)
        self.assertIn("07684c4ab625dd7d1ea6e99e065f60bc0ac6a1ba", section,
                      "pin the upstream commit so the adaptation stays auditable")
