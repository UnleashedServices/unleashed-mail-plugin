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


def _valid_agents():
    """Read capture.VALID_AGENTS from the source of truth — never restate it here.

    Hardcoding the five names makes the disjointness gate INERT: the dangerous change is
    `swift-reviewer` joining the tuple while still named `in` in §13, and a hardcoded copy cannot
    see that happen.
    """
    src = _read("mcp/review-synthesizer/capture.py")
    m = re.search(r"VALID_AGENTS\s*=\s*\(([^)]*)\)", src, re.S)
    assert m, "VALID_AGENTS tuple not found in capture.py"
    return tuple(re.findall(r'"([a-z-]+)"', m.group(1)))


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
            # The two persistence skills reach `review-verdict.py` THROUGH `persist-verdict.sh` now,
            # so the bare-token reference to assert is the script they actually invoke. Asserting the
            # old one would pass on a stale prose mention while the executed path went unchecked.
            "skills/review-synthesis/SKILL.md": [
                "${CLAUDE_PLUGIN_ROOT}/scripts/review/persist-verdict.sh"
            ],
            "skills/brainstorm/SKILL.md": [
                "${CLAUDE_PLUGIN_ROOT}/scripts/review/persist-verdict.sh"
            ],
            "skills/implement/SKILL.md": [
                "${CLAUDE_PLUGIN_ROOT}/scripts/review/resolve-plan-gate.sh"
            ],
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

    def test_b_claude_md_documents_the_effort_floor(self):
        claude_md = _read("CLAUDE.md")
        self.assertIn("**`effort:` is a FLOOR, not a pin**", claude_md)
        self.assertIn("assets omit `effort:` and **inherit** the session level", claude_md)
        self.assertIn("CI rejects any pin below `xhigh`; `xhigh`/`max` are legal", claude_md)
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


class COREDEV2605_Section13Narrowing(unittest.TestCase):
    """§13 Agent Output Style, narrowed to client-facing surfaces (COREDEV-2605).

    §13 now carries a four-column SCOPE TABLE that binds each surface to its producer and to a
    repository ANCHOR. The anchor's PATH is pinned by equality to a canonical map; only its LINE is
    resolution-driven. That split is deliberate: pinning the whole anchor would make the resolution
    logic untestable, and pinning nothing lets a decoy file satisfy every check while the surface is
    silently redirected off its canonical producer.
    """

    #: (surface_id, producer_id, scope, canonical path, fingerprint the anchored section must contain).
    #: The fingerprints are TEST-ONLY metadata — they never ship inside AGENT_CONTRACTS.md — and each
    #: is UNIQUE to its surface, because four `out` rows once shared a generic `## Output Format` and a
    #: security<->concurrency swap was therefore accepted by the gate.
    SURFACES = (
        ("verdict-report", "swift-reviewer", "in", "agents/swift-reviewer.md", "### Verdict:"),
        ("brainstorm-summary", "brainstorm", "in", "skills/brainstorm/SKILL.md", "## Step 8: Summary for Approval"),
        ("implement-wrapup", "implement", "in", "skills/implement/SKILL.md", "## Phase 6: Wrap Up"),
        ("pr-review-report", "pr-review", "in", "skills/pr-review/SKILL.md", "## Step 4: Compile the Final Report"),
        ("security-findings", "security-reviewer", "out", "agents/security-reviewer.md", "## Security Review"),
        ("concurrency-findings", "concurrency-reviewer", "out", "agents/concurrency-reviewer.md", "## Correctness & Concurrency Review"),
        ("ux-perf-findings", "ux-perf-reviewer", "out", "agents/ux-perf-reviewer.md", "## Performance & UX Review"),
        ("accessibility-findings", "accessibility-auditor", "out", "agents/accessibility-auditor.md", "## Accessibility Audit"),
        ("prompt-safety-findings", "prompt-review", "out", "agents/prompt-review.md", "## Structured Findings (orchestrator handoff)"),
    )

    CLASSIFIERS = ("**Adapted**", "**Adopted**", "**Restated positively**")

    # --- extraction helpers: read the artifact, never restate expectations ------------------

    def _doc(self):
        return _read("AGENT_CONTRACTS.md")

    def _section13(self):
        t = self._doc()
        start = t.index("## 13. Agent Output Style")
        return t[start:t.index("## 14.", start)]

    def _section14(self):
        t = self._doc()
        start = t.index("## 14. Blocked Subagent Handoff Contract")
        return t[start:t.index("## Cross-references", start)]

    @staticmethod
    def _fence_state(lines):
        """Yield (line, inside_fence) with CommonMark-ish fence tracking.

        A delimiter is a LINE whose first non-whitespace run is >= 3 backticks or tildes, indented at
        most three spaces; a closer must use the same character. Inline triple-backticks in prose are
        NOT delimiters — `agents/swift-reviewer.md` contains several, well before its real fence, and a
        substring-based scanner inverts the state and rejects the clean document.
        """
        fence = None
        for ln in lines:
            stripped = ln.lstrip(" ")
            indent = len(ln) - len(stripped)
            m = re.match(r"^(`{3,}|~{3,})", stripped) if indent <= 3 else None
            if m:
                ch = m.group(1)[0]
                if fence is None:
                    fence = ch
                    yield ln, True          # the opener itself is inside
                    continue
                if ch == fence:
                    fence = None
                    yield ln, True
                    continue
            yield ln, fence is not None

    def _scope_rows(self):
        """FAIL-CLOSED parser for the four-column scope table.

        Raises on a malformed or unrecognised row rather than skipping it — `_rows` below matches
        numbered rule rows only and, given a scope table, silently returned the rules instead.
        """
        rows = []
        seen_header = False
        for line, inside in self._fence_state(self._section13().split("\n")):
            s = line.strip()
            if inside:
                continue
            if not s.startswith("|"):
                if seen_header and rows:
                    break          # the scope table ended; the rules table is NOT ours to parse
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not seen_header:
                if cells[:1] == ["`surface_id`"]:
                    seen_header = True
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            if len(cells) != 4:
                raise ValueError(f"scope row must have exactly 4 cells, got {len(cells)}: {s}")
            sid, pid, scope, anchor = (c.strip("`") for c in cells)
            if scope not in ("in", "out"):
                raise ValueError(f"scope must be in/out, got {scope!r}")
            if ":" not in anchor:
                raise ValueError(f"anchor must be path:line, got {anchor!r}")
            rows.append((sid, pid, scope, anchor))
        if not rows:
            raise ValueError("no scope rows parsed — the table is missing or malformed")
        return rows

    def _rows(self):
        """rule number -> its single disposition row."""
        out = {}
        for line in self._section13().split("\n"):
            m = re.match(r"^\|\s*(\d+)\s*\|", line)
            if m:
                out[int(m.group(1))] = line
        return out

    # --- the scope table --------------------------------------------------------------------

    def test_scope_table_is_the_exact_nine_triples(self):
        got = {(s, p, sc) for s, p, sc, _ in self._scope_rows()}
        want = {(s, p, sc) for s, p, sc, _, _ in self.SURFACES}
        self.assertEqual(want, got, "the scope table must carry exactly the nine approved triples")

    def test_scope_rows_are_duplicate_free(self):
        ids = [s for s, _, _, _ in self._scope_rows()]
        self.assertEqual(len(ids), len(set(ids)), "duplicate surface_id in the scope table")

    def test_in_set_is_exact_and_DISJOINT_from_valid_agents(self):
        """Positive allowlist + empty intersection — NOT equality with the tuple (§4.1, round 1).

        Equality was considered and rejected: it couples §13 to every future captured specialist, so
        adding a harmless one would force prose churn even though the positive `in` allowlist already
        puts it out of scope. Disjointness catches the change that actually matters — `swift-reviewer`
        joining VALID_AGENTS while still named `in` — without that coupling.

        This distinction is not academic: the first version of this gate asserted equality, and the
        M1p positive case (add an unrelated captured specialist; the gate must still PASS) failed.
        """
        rows = self._scope_rows()
        ins = {p for _, p, sc, _ in rows if sc == "in"}
        outs = {p for _, p, sc, _ in rows if sc == "out"}
        valid = set(_valid_agents())
        self.assertEqual({"swift-reviewer", "brainstorm", "implement", "pr-review"}, ins,
                         "the `in` set is an exact positive allowlist of four surfaces")
        self.assertEqual(set(), ins & valid,
                         "an `in` producer is also a captured reviewer — the dangerous change")
        self.assertLessEqual(outs, valid,
                            "every `out` producer must be a real captured reviewer")

    def test_anchor_paths_are_pinned_to_their_canonical_producer(self):
        """Step 0. Without this a decoy file carrying one heading and one fingerprint passes every
        other check while the surface is redirected off its canonical producer."""
        canonical = {s: path for s, _, _, path, _ in self.SURFACES}
        for sid, _, _, anchor in self._scope_rows():
            with self.subTest(surface=sid):
                self.assertEqual(canonical[sid], anchor.rsplit(":", 1)[0])

    def test_anchor_resolves_to_the_nearest_enclosing_real_heading_of_its_fingerprint(self):
        """Steps 1-5, in order, for every row.

        The anchor must BE the nearest enclosing real heading of the fingerprint — not merely some
        heading whose section happens to contain it. A file's sole H1 encloses everything to EOF and
        would otherwise pass.
        """
        fp = {s: f for s, _, _, _, f in self.SURFACES}
        for sid, _, _, anchor in self._scope_rows():
            with self.subTest(surface=sid):
                path, line = anchor.rsplit(":", 1)
                lines = _read(path).split("\n")
                marked = list(self._fence_state(lines))
                idx = int(line) - 1
                self.assertTrue(marked[idx][0].startswith("#"), f"{anchor} is not a heading")
                self.assertFalse(marked[idx][1], f"{anchor} is inside a fence")
                # step 3: content search of the CURRENT file, exactly one occurrence
                hits = [i for i, (ln, _) in enumerate(marked) if fp[sid] in ln]
                self.assertEqual(1, len(hits), f"{fp[sid]!r} must occur exactly once in {path}")
                # step 4: walk UP from the fingerprint to the first real heading
                nearest = None
                for i in range(hits[0], -1, -1):
                    ln, inside = marked[i]
                    if ln.startswith("#") and not inside:
                        nearest = i
                        break
                self.assertEqual(idx, nearest,
                                 f"{anchor} is not the nearest enclosing real heading of {fp[sid]!r}")

    # --- the rules --------------------------------------------------------------------------

    def test_exactly_ten_dispositions_one_row_each(self):
        self.assertEqual(list(range(1, 11)), sorted(self._rows()))

    def test_each_rule_carries_exactly_one_classifier(self):
        """M3's differential depends on this: membership, never a fixed token per rule.

        Pinning rule N to a particular classifier breaks the moment the narrowing legitimately changes
        it — which §4.4 expressly permits for rules 1, 2, 3 and 5.
        """
        for n, row in self._rows().items():
            with self.subTest(rule=n):
                found = [c for c in self.CLASSIFIERS if c in row]
                self.assertEqual(1, len(found), f"rule {n} must carry exactly one classifier, got {found}")

    def test_rules_4_and_9_still_protect_the_consolidated_table(self):
        """The narrowing removes the PARSER justification, not the CONTRACT one (codex, round 1)."""
        rows = self._rows()
        for n in (4, 9):
            with self.subTest(rule=n):
                self.assertIn("All Issues (Consolidated)", rows[n])

    # --- relocation -------------------------------------------------------------------------

    def test_payload_region_invariant_moved_to_section_5_verbatim(self):
        t = self._doc()
        s5 = t[t.index("## 5. Code Review Pipeline"):t.index("## 6. CI / GitHub Actions Pinning")]
        self.assertIn("The payload region is the span from the `Status:` line to the final fenced JSON block.", s5)
        self.assertIn("Within it, nothing but detail fields and blank lines.", s5)
        self.assertNotIn("The payload region is the span", self._section13(),
                         "the invariant must MOVE, not be copied")

    def test_section_14_exists_and_owns_the_blocked_prefix(self):
        s14 = self._section14()
        self.assertIn("BLOCKED — <reason>", s14)
        self.assertNotIn("BLOCKED — <reason>", self._section13())

    def test_section_13_keeps_only_a_precedence_pointer(self):
        s13 = self._section13()
        self.assertIn("§5", s13)
        self.assertIn("§14", s13)
        self.assertNotIn("Blocker Description", s13,
                         "the six-contract enumeration belongs to §5, not §13")

class COREDEV2603_WorktreeOrdering(unittest.TestCase):
    """The worktree-BEFORE-plan ordering must stay documented (COREDEV-2603 item C1).

    Two mandatory `CLAUDE.md` conventions used to contradict each other: work in a dedicated
    `.claude/worktrees/<name>` worktree, AND pass `implement`'s verify step. The Combined-verdict
    artifact is per-directory session state that git never carries, so gating in one checkout and
    implementing in another failed the gate on a genuine five-round approval (COREDEV-2583, with
    byte-identical plan content).

    Before C1 the resolution existed NOWHERE an operator would look: `grep -rn worktree skills/
    AGENT_CONTRACTS.md` returned ZERO hits, and the convention appeared only at `CLAUDE.md:91`.
    These assertions exist because a docs-only fix is exactly the kind that gets silently reverted.
    """

    FILES = {
        "CLAUDE.md": None,
        "AGENT_CONTRACTS.md": None,
        "skills/create-feature-plan/SKILL.md": None,
        "skills/implement/SKILL.md": None,
        "skills/review-synthesis/SKILL.md": None,
    }

    @classmethod
    def setUpClass(cls):
        for rel in cls.FILES:
            with open(os.path.join(_ROOT, rel), encoding="utf-8") as fh:
                cls.FILES[rel] = fh.read()

    def test_every_surface_mentions_the_worktree_constraint(self):
        """All five, because an operator can enter the flow at any one of them."""
        for rel, src in self.FILES.items():
            with self.subTest(file=rel):
                self.assertIn("worktree", src,
                              f"{rel} must carry the worktree ordering — it is an entry point")

    def test_contracts_carries_it_as_a_numbered_clause(self):
        """§2's ordered gate steps are what implementation agents follow; prose elsewhere is not
        a substitute for a step in that list."""
        src = self.FILES["AGENT_CONTRACTS.md"]
        self.assertIn("00.", src, "§2 needs a step 00 preceding the digest snapshot")
        i = src.index("00.")
        clause = src[i:i + 1400]
        self.assertIn("worktree", clause)
        self.assertIn(".verdicts", clause)

    def test_the_reason_is_stated_not_just_the_rule(self):
        """A bare 'create the worktree first' gets optimised away by the next reader. The WHY —
        that the artifact is git-ignored and does not follow a later `git worktree add` — is what
        makes it stick."""
        for rel in ("AGENT_CONTRACTS.md", "skills/implement/SKILL.md",
                    "skills/review-synthesis/SKILL.md"):
            with self.subTest(file=rel):
                src = self.FILES[rel]
                self.assertIn(".verdicts", src)
                self.assertTrue(
                    "git-ignored" in src or "not carried by git" in src or "does not travel" in src,
                    f"{rel} must say WHY the artifact does not move, not just that it must not be moved",
                )

    def test_the_plan_freeze_rule_is_recorded(self):
        """A reviewer refused a round because the target changed mid-review. The rule now applies to
        the author too, and it belongs in the ordered gate steps."""
        src = self.FILES["AGENT_CONTRACTS.md"]
        self.assertIn("moving target", src,
                      "record that a review cannot approve a plan edited mid-round")

    def test_no_surface_promises_CI_can_verify(self):
        """CI and a second developer cannot verify an approval — the artifact is doubly git-ignored
        BY DESIGN. Round 1 of the CI plan claimed repo-relative paths would fix that; they do not,
        and a doc that implies otherwise sends someone chasing an impossible bug."""
        for rel in ("AGENT_CONTRACTS.md", "skills/review-synthesis/SKILL.md"):
            with self.subTest(file=rel):
                self.assertNotIn("CI can verify", self.FILES[rel])


class COREDEV2607_ReviewerIsolation(unittest.TestCase):
    """The gemini reviewer must not be pointed at the working tree (COREDEV-2607).

    `agy` is not read-only and no flag makes it so. A plan review implemented the plan instead of
    reviewing it — 6 shipped scripts modified, 5 files created — and the skill at the time documented
    `agy --add-dir "$(pwd)"` as THE recipe with no warning at all.
    """

    SKILL = os.path.join(_ROOT, "skills", "gemini-review", "SKILL.md")
    WRAPPER = os.path.join(_ROOT, "scripts", "review", "isolated-agy-review.sh")

    @classmethod
    def setUpClass(cls):
        with open(cls.SKILL, encoding="utf-8") as fh:
            cls.skill = fh.read()

    def test_the_isolation_wrapper_ships(self):
        self.assertTrue(os.path.exists(self.WRAPPER), "isolated-agy-review.sh must ship")
        self.assertTrue(os.access(self.WRAPPER, os.X_OK), "wrapper must be executable")

    def test_the_skill_recommends_the_wrapper(self):
        self.assertIn("isolated-agy-review.sh", self.skill)

    def test_the_skill_warns_that_agy_can_write(self):
        self.assertIn("NOT READ-ONLY", self.skill,
                      "the skill must lead with the fact that agy can write to the tree")

    def test_the_tested_ineffective_flags_are_recorded(self):
        """So nobody 'fixes' this by adding --mode plan. All four were tested; all four wrote."""
        for flag in ("--mode plan", "--sandbox"):
            with self.subTest(flag=flag):
                self.assertIn(flag, self.skill)

    def test_every_raw_agy_invocation_is_warned_or_superseded(self):
        """A raw `agy --add-dir "$(pwd)"` may appear only where the surrounding text flags the risk."""
        lines = self.skill.split("\n")
        for i, line in enumerate(lines):
            if 'agy --add-dir "$(pwd)"' not in line:
                continue
            window = "\n".join(lines[max(0, i - 12):i])
            with self.subTest(line=i + 1):
                self.assertTrue(
                    any(k in window for k in ("SUPERSEDED", "can write", "NOT READ-ONLY",
                                              "isolated wrapper", "COREDEV-2607")),
                    f"unwarned raw agy invocation at line {i + 1} — it points at the working tree",
                )

    def test_the_wrapper_asserts_the_tree_is_unchanged(self):
        with open(self.WRAPPER, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("git status --porcelain", src, "must fingerprint the tree")
        self.assertIn("exit 3", src, "a tree mutation must VOID the round with a distinct exit code")
        self.assertIn("worktree add --detach", src, "must review a disposable detached checkout")

    def test_the_wrapper_guards_against_a_truncated_prompt(self):
        """A guard-only prompt wasted two review rounds; the reviewer's reply read like a wording
        problem rather than the read-after-truncate bug it was."""
        with open(self.WRAPPER, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("1000", src, "must refuse to launch on a truncated prompt")
        self.assertIn("read back empty", src, "must assert the prompt body was read before writing")


if __name__ == "__main__":
    unittest.main()
