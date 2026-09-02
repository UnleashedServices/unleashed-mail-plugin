"""COREDEV-2503 doc-lint mutation proofs: F6 (swift-reviewer Step-4 fail-closed), F13 (CFR state-machine
contradictions), F9 (provider-parity gate drift), B7 (CFR protocol consistency across the 3 files). Each
assertion flips if the corresponding doc fix is reverted."""

import os
import re
import subprocess
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
        self.assertIn(
            "${CLAUDE_PLUGIN_ROOT}/scripts/review/build-verify.sh",
            src,
            "COREDEV-2504: Step-4 must use the bare ${CLAUDE_PLUGIN_ROOT} token (not the :-. form)",
        )
        self.assertNotIn(
            "${CLAUDE_PLUGIN_ROOT:-.}/scripts/review/build-verify.sh",
            src,
            "COREDEV-2504: the :-. fallback form must NOT reappear at Step-4",
        )
        self.assertIn(
            'exit "$BUILD_VERIFY"',
            src,
            "F6: Step-4 must exit the propagated code (fail closed on 127), not end on echo",
        )


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
    _ANY = re.compile(
        r"\$\{\s*CLAUDE_PLUGIN_ROOT[^}\n]*\}?|\$CLAUDE_PLUGIN_ROOT[a-zA-Z0-9_]*",
        re.IGNORECASE,
    )

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
        self.assertEqual(
            bad,
            [],
            f"COREDEV-2504: only the exact ${{CLAUDE_PLUGIN_ROOT}} token is allowed: {bad}",
        )

    def _verdict(self, s):
        # Guard verdict := FAIL iff any regex match != the exact token (i.e. a non-exact reference exists).
        matches = self._ANY.findall(s)
        return "FAIL" if any(m != "${CLAUDE_PLUGIN_ROOT}" for m in matches) else "PASS"

    def test_guard_regex_flags_adversarial_spellings(self):
        # COREDEV-2504 (gemini rounds 1-3 + completeness sweep): pin the guard's behaviour so a future
        # "cleanup" that reintroduces a `\b`-after-ROOT (silently drops suffix typos), loses `\s*` (spacing),
        # or drops re.IGNORECASE (case) is caught HERE — not by luck of a real file containing the typo.
        must_flag = [
            "${CLAUDE_PLUGIN_ROOT:-.}",  # the bug this whole ticket fixes
            "${CLAUDE_PLUGIN_ROOT_DIR}",  # round-1 hole: same-word suffix typo
            "${CLAUDE_PLUGIN_ROOTT}",  # round-1 hole
            "$CLAUDE_PLUGIN_ROOT",  # unbraced
            "echo $CLAUDE_PLUGIN_ROOT and more text",  # round-2: unbraced + trailing text
            "$CLAUDE_PLUGIN_ROOTX/scripts",  # unbraced suffix typo
            "${CLAUDE_PLUGIN_ROOT}/a ${CLAUDE_PLUGIN_ROOT_DIR}/b",  # a valid + a bad on one line
            "${CLAUDE_PLUGIN_ROOT:?err}",  # :? param form
            "${CLAUDE_PLUGIN_ROOT",  # unterminated brace
            "${ CLAUDE_PLUGIN_ROOT }",  # round-3: spaces inside braces
            "${ CLAUDE_PLUGIN_ROOT}",  # round-3: leading space only
            "${CLAUDE_PLUGIN_ROOT }",  # round-3: trailing space only
            "${claude_plugin_root}",  # sweep: all-lowercase (case)
            "${CLAUDE_PLUGIN_Root}",  # sweep: mixed case
            "$claude_plugin_root",  # sweep: unbraced lowercase
        ]
        must_pass = [
            "${CLAUDE_PLUGIN_ROOT}",
            "Run ${CLAUDE_PLUGIN_ROOT}/scripts/x.py and echo done",
            "See ${CLAUDE_PLUGIN_ROOT} then $HOME/x",
            "${CLAUDE_PLUGIN_ROOT}/a ${CLAUDE_PLUGIN_ROOT}/b",  # two valid on one line
            "prefix${CLAUDE_PLUGIN_ROOT}suffix",
            "the CLAUDE_PLUGIN_ROOT variable, in prose (no $) — not a substitution site",
            "no reference at all",
        ]
        for s in must_flag:
            self.assertEqual(
                self._verdict(s),
                "FAIL",
                f"COREDEV-2504: guard must FLAG {s!r} (findall={self._ANY.findall(s)})",
            )
        for s in must_pass:
            self.assertEqual(
                self._verdict(s),
                "PASS",
                f"COREDEV-2504: guard must PASS {s!r} (findall={self._ANY.findall(s)})",
            )

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
            "${CLADUE_PLUGIN_ROOT}",  # (a) transposition typo -> different name
            "${CLAUDE_PLGUIN_ROOT}",  # (a) transposition typo
            "${CLAUDEPLUGIN_ROOT}",  # (a) missing underscore
            "${​CLAUDE_PLUGIN_ROOT}",  # (b) zero-width space after brace
            "＄{CLAUDE_PLUGIN_ROOT}",  # (b) full-width dollar homoglyph
            "${CLAUDE_PLUGIN_ROOT}}",  # (c) exact token + stray trailing brace
            "$${CLAUDE_PLUGIN_ROOT}",  # (c) exact token + escaped leading dollar
        ]
        for s in out_of_contract:
            self.assertEqual(
                self._verdict(s),
                "PASS",
                f"COREDEV-2504: {s!r} is documented OUT of the guard's contract — if this now "
                f"FLAGs, update the contract comment + this test intentionally (findall={self._ANY.findall(s)})",
            )

    def test_gate_script_references_present_via_bare_token(self):
        # Defense-in-depth (codex R2): catch someone DELETING the token + replacing with a repo-relative
        # path — the syntax guard above would then pass. Assert each gate-critical script is still referenced
        # via the bare token.
        expect = {
            "agents/swift-reviewer.md": [
                "${CLAUDE_PLUGIN_ROOT}/scripts/review/reviewer-roster.sh",
                "${CLAUDE_PLUGIN_ROOT}/scripts/review/build-verify.sh",
                "${CLAUDE_PLUGIN_ROOT}/scripts/lib/context.sh",
            ],
            "skills/create-feature-plan/SKILL.md": [
                "${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py"
            ],
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
            "skills/codex-review/SKILL.md": [
                "${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py"
            ],
            "skills/gemini-review/SKILL.md": [
                "${CLAUDE_PLUGIN_ROOT}/scripts/pty-capture.py"
            ],
        }
        for rel, refs in expect.items():
            src = _read(rel)
            for ref in refs:
                self.assertIn(
                    ref,
                    src,
                    f"COREDEV-2504: {rel} lost the bare-token reference {ref!r}",
                )

    def test_codex_review_pty_timeout_is_1200(self):
        # COREDEV-2504 medium: every codex-review pty cap must be 1200s (xhigh survives), not 600.
        # One of the two caps moved into `capture-codex-review.sh` when the capture recipe was
        # extracted (COREDEV-2642), so counting occurrences in the SKILL alone would now pass while
        # the cap that actually governs a gate round went unchecked. Assert BOTH homes.
        src = _read("skills/codex-review/SKILL.md")
        helper = _read("scripts/review/capture-codex-review.sh")
        isolated = _read("scripts/review/isolated-codex-review.sh")
        audit = _read("scripts/review/audit-codex.sh")
        self.assertIn(
            "--timeout 1200",
            audit,
            "the audit wrapper must keep the 1200s cap",
        )
        self.assertIn(
            'capture-codex-review.sh" "$TICKET" "$ROUND" ".codex-prompt-${TICKET}r${ROUND}.md" "$PLAN" 1200',
            src,
            "the capture recipe must pass the 1200s cap to the helper",
        )
        self.assertRegex(
            helper,
            r'TIMEOUT="\$\{\d+-1200\}"',
            "the helper's default cap must be 1200s (the operand INDEX is not pinned — it moved when "
            "the plan operand was added, and pinning it made this cell fail for an unrelated reason)",
        )
        # The cap now threads capture-codex -> isolated-codex-review.sh -> pty-capture (COREDEV-2642, the
        # codex arm gained the gemini arm's isolation). Assert it is HANDED to the isolation harness and
        # that the harness PASSES it to pty-capture — the pty cap that governs a gate round lives there.
        self.assertIn(
            'isolated-codex-review.sh" \\\n    "${CODEX_TRANSCRIPT}.prompt" "$CODEX_TRANSCRIPT" "$TIMEOUT" "$PLAN"',
            helper,
            "the helper must hand its cap to the codex isolation harness",
        )
        self.assertRegex(
            isolated,
            r'TIMEOUT="\$\{\d+:-1200\}"',
            "the codex isolation harness must default the cap to 1200s",
        )
        self.assertIn(
            '--timeout "$TIMEOUT"',
            isolated,
            "the codex isolation harness must pass its cap through to pty-capture",
        )
        for label, text in (
            ("skill", src),
            ("helper", helper),
            ("isolation harness", isolated),
            ("audit wrapper", audit),
        ):
            self.assertNotIn(
                "--timeout 600",
                text,
                f"codex-review {label} must not keep the 600s cap that SIGTERMs xhigh",
            )
            self.assertNotIn(
                "{4-600}",
                text,
                f"codex-review {label} must not default to the 600s cap",
            )


class F13_CFRStateMachine(unittest.TestCase):
    def test_no_unlabelled_conflation(self):
        src = _read("agents/jira-manager.md")
        self.assertNotIn(
            "leave the issue UNLABELLED",
            src,
            "F13(a): a cfr-needs-human issue is not UNLABELLED — say 'without the counted label'",
        )
        self.assertIn("without the counted `change-failure` label", src)

    def test_reattribution_vs_resolution_distinguished(self):
        src = _read("agents/jira-manager.md")
        # the swap-back (re-attribution) must be distinguished from the terminal 'resolution' clear
        self.assertIn(
            "re-attribution",
            src,
            "F13(b): re-attribution swap must be a named, non-terminal move",
        )
        self.assertIn(
            "resolution",
            src,
            "F13(b): the terminal-only rule governs *resolution*, not the swap",
        )


class F9_ParityGateModel(unittest.TestCase):
    def test_reviewer_references_capability_model(self):
        src = _read("agents/swift-reviewer.md")
        self.assertIn(
            "ServiceCapabilities",
            src,
            "F9: parity gate must reference the ServiceCapabilities model",
        )
        self.assertIn(
            "ProviderParityError",
            src,
            "F9: a sanctioned gap is a ProviderParityError throw",
        )
        self.assertIn(
            'is NOT "an implementation in both"',
            src,
            "F9: a throwing stub must not be accepted as an implementation",
        )

    def test_contract_source_of_truth_updated(self):
        src = _read("AGENT_CONTRACTS.md")
        self.assertIn("ServiceCapabilities", src)
        self.assertIn("ProviderParityError", src)


class B7_CFRProtocolConsistency(unittest.TestCase):
    FILES = (
        "agents/jira-manager.md",
        "agents/release-manager.md",
        "AGENT_CONTRACTS.md",
    )

    def test_label_names_consistent(self):
        for rel in self.FILES:
            src = _read(rel)
            for label in ("change-failure", "cfr-triage-pending", "cfr-needs-human"):
                self.assertIn(
                    label, src, f"B7: {rel} must mention the CFR label `{label}`"
                )

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
            self.assertIn(
                "pre-existing",
                low,
                f"B7: {rel} must name the proven-pre-existing terminal",
            )
            self.assertIn(
                "dismiss", low, f"B7: {rel} must name the human-dismissal terminal"
            )


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
        self.assertNotRegex(
            readme,
            r"all five review agents.{0,20}`opus`",
            "README must not re-assert the uniform-opus claim in any casing",
        )

    def test_a_readme_states_the_actual_tiering(self):
        readme = _read("README.md")
        for agent in ("security-reviewer", "prompt-review", "concurrency-reviewer"):
            self.assertIn(
                agent, readme, f"README must name {agent} as an `opus` reviewer"
            )

    # (b) the alias list must be complete against the pinned runtime table.
    def test_b_claude_md_alias_list_is_complete(self):
        claude_md = _read("CLAUDE.md")
        for alias in (
            "`best`",
            "`opusplan`",
            "`sonnet[1m]`",
            "`opus[1m]`",
            "`fable[1m]`",
        ):
            self.assertIn(alias, claude_md, f"CLAUDE.md model alias list omits {alias}")

    def test_b_claude_md_denies_the_nonexistent_default_alias(self):
        # `default` is NOT in the runtime table; an earlier draft of this plan proposed adding it.
        self.assertIn("no** `default` alias", _read("CLAUDE.md"))

    def test_b_claude_md_documents_the_effort_floor(self):
        claude_md = _read("CLAUDE.md")
        self.assertIn("**`effort:` is a FLOOR, not a pin**", claude_md)
        self.assertIn(
            "assets omit `effort:` and **inherit** the session level", claude_md
        )
        self.assertIn(
            "CI rejects any pin below `xhigh`; `xhigh`/`max` are legal", claude_md
        )
        self.assertIn(
            "CLAUDE_CODE_EFFORT_LEVEL",
            claude_md,
            "the honest limit (the env var outranks frontmatter) must be stated",
        )

    # (c) alias vs version pin — the old guidance argued against something the alias does not do.
    def test_c_alias_versus_version_pin_is_distinguished(self):
        for rel in ("CLAUDE.md", "AGENT_CONTRACTS.md"):
            with self.subTest(rel=rel):
                text = _read(rel)
                self.assertNotIn(
                    "Prefer `inherit`/`sonnet` over hard-pinning `opus`",
                    text,
                    f"{rel} still carries the superseded alias/pin conflation",
                )
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
        self.assertEqual(
            offenders, [], "agent bodies must not teach from a superseded model id"
        )


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
        (
            "verdict-report",
            "swift-reviewer",
            "in",
            "agents/swift-reviewer.md",
            "### Verdict:",
        ),
        (
            "brainstorm-summary",
            "brainstorm",
            "in",
            "skills/brainstorm/SKILL.md",
            "## Step 8: Summary for Approval",
        ),
        (
            "implement-wrapup",
            "implement",
            "in",
            "skills/implement/SKILL.md",
            "## Phase 6: Wrap Up",
        ),
        (
            "pr-review-report",
            "pr-review",
            "in",
            "skills/pr-review/SKILL.md",
            "## Step 4: Compile the Final Report",
        ),
        (
            "security-findings",
            "security-reviewer",
            "out",
            "agents/security-reviewer.md",
            "## Security Review",
        ),
        (
            "concurrency-findings",
            "concurrency-reviewer",
            "out",
            "agents/concurrency-reviewer.md",
            "## Correctness & Concurrency Review",
        ),
        (
            "ux-perf-findings",
            "ux-perf-reviewer",
            "out",
            "agents/ux-perf-reviewer.md",
            "## Performance & UX Review",
        ),
        (
            "accessibility-findings",
            "accessibility-auditor",
            "out",
            "agents/accessibility-auditor.md",
            "## Accessibility Audit",
        ),
        (
            "prompt-safety-findings",
            "prompt-review",
            "out",
            "agents/prompt-review.md",
            "## Structured Findings (orchestrator handoff)",
        ),
    )

    CLASSIFIERS = ("**Adapted**", "**Adopted**", "**Restated positively**")

    # --- extraction helpers: read the artifact, never restate expectations ------------------

    def _doc(self):
        return _read("AGENT_CONTRACTS.md")

    def _section13(self):
        t = self._doc()
        start = t.index("## 13. Agent Output Style")
        return t[start : t.index("## 14.", start)]

    def _section14(self):
        t = self._doc()
        start = t.index("## 14. Blocked Subagent Handoff Contract")
        return t[start : t.index("## Cross-references", start)]

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
                    yield ln, True  # the opener itself is inside
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
                    break  # the scope table ended; the rules table is NOT ours to parse
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not seen_header:
                if cells[:1] == ["`surface_id`"]:
                    seen_header = True
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            if len(cells) != 4:
                raise ValueError(
                    f"scope row must have exactly 4 cells, got {len(cells)}: {s}"
                )
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
        self.assertEqual(
            want, got, "the scope table must carry exactly the nine approved triples"
        )

    def test_scope_rows_are_duplicate_free(self):
        ids = [s for s, _, _, _ in self._scope_rows()]
        self.assertEqual(
            len(ids), len(set(ids)), "duplicate surface_id in the scope table"
        )

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
        self.assertEqual(
            {"swift-reviewer", "brainstorm", "implement", "pr-review"},
            ins,
            "the `in` set is an exact positive allowlist of four surfaces",
        )
        self.assertEqual(
            set(),
            ins & valid,
            "an `in` producer is also a captured reviewer — the dangerous change",
        )
        self.assertLessEqual(
            outs, valid, "every `out` producer must be a real captured reviewer"
        )

    def test_anchor_paths_are_pinned_to_their_canonical_producer(self):
        """Step 0. Without this a decoy file carrying one heading and one fingerprint passes every
        other check while the surface is redirected off its canonical producer."""
        canonical = {s: path for s, _, _, path, _ in self.SURFACES}
        for sid, _, _, anchor in self._scope_rows():
            with self.subTest(surface=sid):
                self.assertEqual(canonical[sid], anchor.rsplit(":", 1)[0])

    def test_anchor_resolves_to_the_nearest_enclosing_real_heading_of_its_fingerprint(
        self,
    ):
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
                self.assertTrue(
                    marked[idx][0].startswith("#"), f"{anchor} is not a heading"
                )
                self.assertFalse(marked[idx][1], f"{anchor} is inside a fence")
                # step 3: content search of the CURRENT file, exactly one occurrence
                hits = [i for i, (ln, _) in enumerate(marked) if fp[sid] in ln]
                self.assertEqual(
                    1, len(hits), f"{fp[sid]!r} must occur exactly once in {path}"
                )
                # step 4: walk UP from the fingerprint to the first real heading
                nearest = None
                for i in range(hits[0], -1, -1):
                    ln, inside = marked[i]
                    if ln.startswith("#") and not inside:
                        nearest = i
                        break
                self.assertEqual(
                    idx,
                    nearest,
                    f"{anchor} is not the nearest enclosing real heading of {fp[sid]!r}",
                )

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
                self.assertEqual(
                    1,
                    len(found),
                    f"rule {n} must carry exactly one classifier, got {found}",
                )

    def test_rules_4_and_9_still_protect_the_consolidated_table(self):
        """The narrowing removes the PARSER justification, not the CONTRACT one (codex, round 1)."""
        rows = self._rows()
        for n in (4, 9):
            with self.subTest(rule=n):
                self.assertIn("All Issues (Consolidated)", rows[n])

    # --- relocation -------------------------------------------------------------------------

    def test_payload_region_invariant_moved_to_section_5_verbatim(self):
        t = self._doc()
        s5 = t[
            t.index("## 5. Code Review Pipeline") : t.index(
                "## 6. CI / GitHub Actions Pinning"
            )
        ]
        self.assertIn(
            "The payload region is the span from the `Status:` line to the final fenced JSON block.",
            s5,
        )
        self.assertIn("Within it, nothing but detail fields and blank lines.", s5)
        self.assertNotIn(
            "The payload region is the span",
            self._section13(),
            "the invariant must MOVE, not be copied",
        )

    def test_section_14_exists_and_owns_the_blocked_prefix(self):
        s14 = self._section14()
        self.assertIn("BLOCKED — <reason>", s14)
        self.assertNotIn("BLOCKED — <reason>", self._section13())

    def test_section_13_keeps_only_a_precedence_pointer(self):
        s13 = self._section13()
        self.assertIn("§5", s13)
        self.assertIn("§14", s13)
        self.assertNotIn(
            "Blocker Description",
            s13,
            "the six-contract enumeration belongs to §5, not §13",
        )


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
                self.assertIn(
                    "worktree",
                    src,
                    f"{rel} must carry the worktree ordering — it is an entry point",
                )

    def test_contracts_carries_it_as_a_numbered_clause(self):
        """§2's ordered gate steps are what implementation agents follow; prose elsewhere is not
        a substitute for a step in that list."""
        src = self.FILES["AGENT_CONTRACTS.md"]
        self.assertIn("00.", src, "§2 needs a step 00 preceding the digest snapshot")
        i = src.index("00.")
        clause = src[i : i + 1400]
        self.assertIn("worktree", clause)
        self.assertIn(".verdicts", clause)

    def test_the_reason_is_stated_not_just_the_rule(self):
        """A bare 'create the worktree first' gets optimised away by the next reader. The WHY —
        that the artifact is git-ignored and does not follow a later `git worktree add` — is what
        makes it stick."""
        for rel in (
            "AGENT_CONTRACTS.md",
            "skills/implement/SKILL.md",
            "skills/review-synthesis/SKILL.md",
        ):
            with self.subTest(file=rel):
                src = self.FILES[rel]
                self.assertIn(".verdicts", src)
                self.assertTrue(
                    "git-ignored" in src
                    or "not carried by git" in src
                    or "does not travel" in src,
                    f"{rel} must say WHY the artifact does not move, not just that it must not be moved",
                )

    def test_the_plan_freeze_rule_is_recorded(self):
        """A reviewer refused a round because the target changed mid-review. The rule now applies to
        the author too, and it belongs in the ordered gate steps."""
        src = self.FILES["AGENT_CONTRACTS.md"]
        self.assertIn(
            "moving target",
            src,
            "record that a review cannot approve a plan edited mid-round",
        )

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
        self.assertTrue(
            os.path.exists(self.WRAPPER), "isolated-agy-review.sh must ship"
        )
        self.assertTrue(os.access(self.WRAPPER, os.X_OK), "wrapper must be executable")

    def test_the_skill_recommends_the_wrapper(self):
        self.assertIn("isolated-agy-review.sh", self.skill)

    def test_the_skill_warns_that_agy_can_write(self):
        self.assertIn(
            "NOT READ-ONLY",
            self.skill,
            "the skill must lead with the fact that agy can write to the tree",
        )

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
            window = "\n".join(lines[max(0, i - 12) : i])
            with self.subTest(line=i + 1):
                self.assertTrue(
                    any(
                        k in window
                        for k in (
                            "SUPERSEDED",
                            "can write",
                            "NOT READ-ONLY",
                            "isolated wrapper",
                            "COREDEV-2607",
                        )
                    ),
                    f"unwarned raw agy invocation at line {i + 1} — it points at the working tree",
                )

    def test_the_wrapper_asserts_the_tree_is_unchanged(self):
        with open(self.WRAPPER, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('tree_fingerprint "$REPO"', src, "must fingerprint the live tree")
        self.assertIn(
            "exit 3",
            src,
            "a tree mutation must VOID the round with a distinct exit code",
        )
        # A PRIVATE clone, never `git worktree add` — a linked worktree's `.git` points into the
        # maintainer's real repository, and the reviewer's git operations landed there (PR #67 pass 6).
        self.assertIn(
            'disposable_checkout "$REPO" "$SHA"',
            src,
            "must review a private disposable checkout",
        )
        self.assertNotIn(
            "worktree add", src, "a linked worktree hands the reviewer the real .git"
        )
        self.assertIn(
            'disposable_fingerprint "$TREE"',
            src,
            "the disposable checkout must be compared by CONTENT, not by git status",
        )

    def test_the_wrapper_guards_against_a_truncated_prompt(self):
        """A guard-only prompt wasted two review rounds; the reviewer's reply read like a wording
        problem rather than the read-after-truncate bug it was.

        Both halves moved into the SHARED `stage-prompt.py` when the two arms stopped duplicating a
        `sed` pipeline and an inline guard-prepend (PR #63 recheck). The wrapper now passes the floor
        and the helper enforces it, so this asserts the rule at whichever layer owns it — naming the
        layer explicitly rather than letting the check silently pass on a file that no longer decides.
        """
        with open(self.WRAPPER, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn(
            "--min-bytes 1000",
            src,
            "the wrapper must still demand the 1000-byte floor from the staging helper",
        )
        helper = _read("scripts/review/stage-prompt.py")
        self.assertIn(
            "assembled prompt is only",
            helper,
            "the staging helper must refuse a truncated assembled prompt",
        )
        self.assertIn(
            "refusing to write a guard-only prompt",
            helper,
            "the staging helper must refuse a guard-only prompt (read before write)",
        )


class DeepReviewP2Fixes(unittest.TestCase):
    """Two findings from the exact-head deep review, each executed rather than eyeballed."""

    def test_codex_audit_allocator_is_portable_and_substitutes_its_template(self):
        """`mktemp -t codex-audit` exits 1 on GNU: "too few X's in template".

        The Linux CI job never executes this documentation recipe, so it stayed green while the recipe
        could not run on the platform CI uses. `-t name.XXXXXX` satisfies GNU but BSD leaves the X's
        LITERAL and appends its own suffix, so the assertion below is on the produced NAME, not just on
        the template: a form that only half-works produces a path still containing `XXXXXX`.
        """
        # The allocator moved into `audit-codex.sh` when the audit recipe became one granted command
        # (deep review, P1) — read it where it now lives, not where it used to.
        line = [
            item
            for item in _read("scripts/review/audit-codex.sh").splitlines()
            if item.startswith("AUDIT_OUT=")
        ]
        self.assertEqual(1, len(line), "expected exactly one audit allocator line")
        allocator = line[0]
        self.assertNotIn(
            " -t ",
            allocator,
            "the BSD `-t` shorthand without a template is rejected by GNU mktemp",
        )
        self.assertRegex(
            allocator, r"X{6,}", "GNU mktemp requires at least six trailing X's"
        )

        result = subprocess.run(
            ["bash", "-c", allocator + '\nprintf "%s" "$AUDIT_OUT"'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        produced = result.stdout.strip()
        try:
            self.assertTrue(
                os.path.isfile(produced), f"allocator produced no file: {produced!r}"
            )
            self.assertNotIn(
                "XXXXXX",
                os.path.basename(produced),
                "the template was not substituted — this is the BSD `-t name.XXXXXX` half-fix",
            )
        finally:
            if os.path.isfile(produced):
                os.remove(produced)

    def test_agy_arm_default_is_the_model_its_own_comment_names(self):
        """The comment described a switch the code never made, for every round this branch ran.

        Binding the two to each other is the point: either can be edited, but they cannot disagree.
        """
        source = _read("scripts/review/isolated-agy-review.sh")
        match = re.search(r'^MODEL="\$\{MODEL:-([^}]+)\}"$', source, re.M)
        self.assertIsNotNone(match, "isolated-agy-review.sh has no MODEL default line")
        default = match.group(1)
        self.assertIn(
            "Switched from gemini-3.1-pro to " + default,
            source,
            f"the default is {default!r} but the rationale above it names a different model",
        )
        self.assertNotEqual(
            "gemini-3.1-pro-high",
            default,
            "this is the model the comment says failed to emit a parseable verdict in 5 of 6 rounds",
        )

    def test_agy_preflight_ping_is_allocated_per_run(self):
        """A shared `/tmp/agy-ping.txt` lets a dead CLI read as healthy.

        The preflight decides whether the mandatory gate can run at all. With one shared path, a
        preflight that dies before writing leaves the PREVIOUS run's `pong` in place and the next
        reader calls the CLI available; two concurrent preflights also overwrite each other
        (deep review, P2). Both surfaces that document it must allocate per run AND re-read the path
        they allocated, never a re-derived name.
        """
        for rel in ("skills/gemini-review/SKILL.md", "AGENT_CONTRACTS.md"):
            with self.subTest(file=rel):
                source = _read(rel)
                self.assertNotIn(
                    "/tmp/agy-ping.txt",
                    source,
                    f"{rel} still documents a fixed shared preflight path",
                )
                if (
                    rel.startswith("skills/")
                    or "scripts/review/preflight-agy.sh" in source
                ):
                    # The caller routes through the wrapper, which allocates and re-reads the path
                    # itself. AGENT_CONTRACTS.md §2 joined the skills here (2026-08-17 remediation):
                    # it had gone on teaching the INLINE recipe the wrapper was extracted to replace,
                    # whose reproduced defects are cwd pollution — which can now VOID a round under
                    # AF-5's freeze rule — and no exit-status check. The property this gate protects
                    # (a ping path allocated per run) is asserted on the wrapper below either way.
                    self.assertIn(
                        "scripts/review/preflight-agy.sh",
                        source,
                        f"{rel} must route the preflight through the granted wrapper",
                    )
                else:
                    self.assertRegex(
                        source,
                        r'PING="\$\(mktemp "\$\{TMPDIR:-/tmp\}/agy-ping\.X{6,}"\)"',
                        f"{rel} must allocate the ping path per run with a portable template",
                    )
                    self.assertIn(
                        '"$PING"',
                        source,
                        f"{rel} must pass and re-read the allocated path, not a re-derived name",
                    )
        # And the wrapper itself must do the allocating it now owns.
        wrapper = _read("scripts/review/preflight-agy.sh")
        self.assertRegex(
            wrapper, r'PING="\$\(mktemp "\$\{TMPDIR:-/tmp\}/agy-ping\.X{6,}"\)"'
        )
        self.assertIn('grep -qi pong "$PING"', wrapper)

    def test_gemini_skill_quotes_the_model_the_wrapper_actually_defaults_to(self):
        """The skill QUOTES the wrapper's default line, so the two can drift silently.

        They did: the script moved to `gemini-3.6-flash-high` while the skill still quoted
        `gemini-3.1-pro-high` and told operators to fall back by editing `settings.json` — a route the
        wrapper makes inert, because it always passes `--model` (deep review, codex inline). Bind the
        quotation to the source rather than pinning either to a literal.
        """
        script = _read("scripts/review/isolated-agy-review.sh")
        skill = _read("skills/gemini-review/SKILL.md")
        match = re.search(r'^MODEL="\$\{MODEL:-([^}]+)\}"$', script, re.M)
        self.assertIsNotNone(match)
        default = match.group(1)

        self.assertIn(
            'MODEL="${MODEL:-' + default + '}"',
            skill,
            "the skill quotes a different wrapper default than the wrapper has",
        )
        self.assertIn(
            "(binary `agy`, model `" + default + "`)",
            skill,
            "the skill's frontmatter description names a different model than the wrapper runs",
        )
        self.assertNotIn(
            "temporarily edit settings.json and restore after",
            skill,
            "settings.json cannot affect a wrapper round — the wrapper always passes --model",
        )


class DuplicatedGrammarsAgree(unittest.TestCase):
    """`pty-capture.py` copies two grammars from `review-verdict.py`; the copies must not drift.

    The copy is deliberate: `pty-capture.py` runs on the blocking hook path and imports nothing local,
    so it cannot share a module with the verdict writer. But a copy that drifts becomes a SECOND,
    softer authority — the preflight would accept a transcript the writer later rejects, which is
    exactly the wasted-round defect the preflight exists to prevent (PR #63 recheck, P2). Asserting the
    pattern text is identical is what keeps "duplicated" from meaning "diverged".
    """

    def test_the_launch_record_and_leaf_grammars_are_identical(self):
        capture = _read("scripts/pty-capture.py")
        verdict = _read("scripts/review-verdict.py")

        # Both must derive the run-id length from the same value.
        for source, label in ((capture, "pty-capture"), (verdict, "review-verdict")):
            self.assertIn(
                "_RUN_ID_HEX_LENGTH = 16 * 2",
                source,
                f"{label} changed the run-id length; the other file must change with it",
            )

        # The launch-record grammar: 32 hex digits, a space, the reviewer, a newline. The reviewer
        # field is what makes the gate's identity check read ALLOCATOR-ATTESTED evidence instead of a
        # filename the caller supplies — a rename defeated the two-arm quorum in both directions
        # without it (PR #63 recheck, P1). Both files must parse the same two fields.
        for source, name in (
            (capture, "_LAUNCH_RECORD_RE"),
            (verdict, "_LAUNCH_RECORD"),
        ):
            self.assertIn(
                r'rb"}) ([A-Za-z0-9][A-Za-z0-9-]*)\n\Z"',
                source,
                f"{name} no longer records/parses the reviewer field",
            )
            self.assertIn(
                r'rb"\A([0-9a-f]{"', source, f"{name} no longer anchors the run id"
            )

    def test_the_allocator_writes_the_reviewer_into_the_launch_record(self):
        """The record is the evidence the identity check reads, so it must actually contain it."""
        capture = _read("scripts/pty-capture.py")
        self.assertIn(
            '_write_all(fd, (run_id + " " + reviewer + "\\n").encode("ascii"))',
            capture,
            "the allocator no longer records the reviewer beside the run id",
        )
        verdict = _read("scripts/review-verdict.py")
        self.assertIn(
            '_run_id, attested, _info, problem = _read_launch_record(transcript + ".launch")',
            verdict,
            "the identity check no longer reads the allocator's record",
        )
        # ONE parser for the record, not one per field. The freshness check reads the run id and the
        # identity check reads the reviewer, and they briefly had a copy each — so the grammar had to
        # be tightened twice, which is the divergence-between-arms defect the shared staging helpers
        # exist to prevent, in the file that adjudicates them.
        self.assertEqual(
            1,
            verdict.count("_LAUNCH_RECORD.fullmatch("),
            "review-verdict.py must parse the launch record in exactly one place",
        )
        self.assertNotIn(
            "match = _ALLOCATOR_BASENAME.match(os.path.basename(transcript))\n        if match is None:\n            continue",
            verdict,
            "the identity check still skips a transcript whose FILENAME is not allocator-shaped — "
            "that is the rename bypass",
        )

        # The allocator leaf grammar: the round is `r[0-9]+` in BOTH, which is the precondition the
        # allocator's numeric-round check exists to guarantee.
        for source, label in ((capture, "pty-capture"), (verdict, "review-verdict")):
            self.assertIn(
                r"r[0-9]+-(?P<reviewer>[A-Za-z0-9][A-Za-z0-9-]*)-",
                source,
                f"{label}'s allocator-leaf grammar drifted from the other's",
            )

    def test_the_allocator_enforces_the_round_shape_the_leaf_grammar_requires(self):
        """The two must agree in DIRECTION too: a round the allocator accepts must be one the leaf
        grammar can match, or the review is spent on a transcript that can never validate.
        """
        capture = _read("scripts/pty-capture.py")
        self.assertIn(
            '_ROUND_COMPONENT_RE = re.compile(r"[0-9]+")',
            capture,
            "the allocator no longer constrains the round to digits",
        )
        # The rule lives in a NAMED shared validator, not inline in `allocate_transcript` — M1.5/M1.8
        # bind the allocator's decision to the validators so production logic cannot diverge from them.
        self.assertIn(
            "def is_valid_round_component(",
            capture,
            "the numeric-round rule must be a named shared validator, not inline logic",
        )
        self.assertIn(
            '"round": is_valid_round_component,',
            capture,
            "the round validator is defined but the allocator never applies it",
        )


class ContainedOperandsAreTheOnesUsed(unittest.TestCase):
    """Every entrypoint that validates an operand must pass ON what the validator returned.

    THE FINDING (PR #63 recheck, P1). `containment.py` emits the resolved path precisely so the caller
    builds from THAT — its own docstring says so, and `audit-codex.sh` follows it ("from the SNAPSHOT
    output rather than from the caller's argv"). The two plan-state wrappers instead sent the output to
    `/dev/null` and passed the caller's original operand to `review-verdict.py`, which resolves and
    OPENS it: the string that was proved contained and the string that was opened were two different
    things, so an alternate spelling — or a `docs/planning` swapped for a symlink after the check —
    reached an object containment never saw.

    Asserted structurally because the divergence has no single-process observable: with the `--under`
    base left physical, every accepted alternate spelling resolves to the same file, and what remains is
    a post-validation swap, which cannot be staged deterministically. The reproducible half of this
    finding — a symlinked ANCESTOR between validation and the read — is proven end-to-end in
    `test_plan_operand_containment.ContainedReadWalksEveryComponent`.
    """

    WRAPPERS = (
        ("scripts/review/snapshot-plan.sh", "PLAN_CONTAINED", "$PLAN"),
        ("scripts/review/persist-verdict.sh", "PLAN_PATH", "$PLAN_PATH"),
    )

    def test_neither_plan_wrapper_discards_the_containment_result(self):
        for path, captured, _raw in self.WRAPPERS:
            source = _read(path)
            self.assertIn(
                "--absolute",
                source,
                f"{path} no longer asks containment for the resolved path",
            )
            self.assertNotIn(
                '-- "$PLAN" >/dev/null',
                source,
                f"{path} discards the containment result again",
            )
            self.assertNotIn(
                '-- "$PLAN_PATH" >/dev/null',
                source,
                f"{path} discards the containment result again",
            )
            self.assertIn(
                f'{captured}="$(python3',
                source,
                f"{path} does not capture the validated path",
            )

    def test_the_captured_path_is_what_reaches_review_verdict(self):
        snapshot = _read("scripts/review/snapshot-plan.sh")
        self.assertIn(
            'review-verdict.py" snapshot --plan "$PLAN_CONTAINED"',
            snapshot,
            "snapshot-plan.sh passes an operand other than the validated one",
        )
        # `persist-verdict.sh` REPLACES `PLAN_PATH` rather than capturing into a new name, so there is
        # no unvalidated spelling left in scope for a later line to reach for. Assert the absence, which
        # is the property — a second variable would let both survive.
        persist = _read("scripts/review/persist-verdict.sh")
        self.assertNotIn(
            "PLAN_CONTAINED",
            persist,
            "persist-verdict.sh kept a second name, so the raw operand is still in scope",
        )

    def test_the_shared_reader_is_the_only_descriptor_walk(self):
        """The walk lived in `snapshot-operands.py` alone while `bind-prompt.py` kept a leaf-only read.

        One implementation, in `containment.py` beside the validator — the same "a rule that lives in
        one script is a rule the next entrypoint will not have" failure this module keeps recording.
        """
        self.assertIn(
            "def read_contained(",
            _read("scripts/review/containment.py"),
            "the shared descriptor walk is gone from containment.py",
        )
        for path in (
            "scripts/review/snapshot-operands.py",
            "scripts/review/bind-prompt.py",
        ):
            source = _read(path)
            self.assertNotIn(
                "O_DIRECTORY", source, f"{path} grew its own descriptor walk again"
            )
            self.assertIn(
                "read_contained(",
                source,
                f"{path} no longer reads through the shared walk",
            )


class EveryShippedPythonIsByteCompiledOn39(unittest.TestCase):
    """The 3.9 compile job protects an ENUMERATED list, so a new script joins it only if remembered.

    `stage-prompt.py` did not (PR #63 recheck, P3), and the two py_compile invocations had drifted from
    each other as well — the 3.9 job covered `cleanup_coredev_2619_leaks.py` and the default-Python job
    did not. macOS ships 3.9.6 as `/usr/bin/python3` and the review CLIs run these scripts under it, so
    an unlisted script is one whose 3.9 syntax nothing checks.

    Enumeration is not the class. This derives the class — every tracked non-test `.py` under `scripts/`
    — and requires both invocations to name all of it.
    """

    def _compile_lines(self) -> "list[str]":
        lines = [
            line.strip()
            for line in _read(".github/workflows/plugin-ci.yml").splitlines()
            if line.strip().startswith("run: python3 -m py_compile")
        ]
        self.assertEqual(
            2, len(lines), "the two py_compile invocations moved or multiplied"
        )
        return lines

    def test_both_invocations_cover_every_shipped_script(self):
        import subprocess

        tracked = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        shipped = sorted(
            path
            for path in tracked
            if path.startswith("scripts/") and "/tests/" not in path
        )
        self.assertTrue(
            shipped, "the tracked-script query found nothing — the derivation is broken"
        )
        for line in self._compile_lines():
            for path in shipped:
                self.assertIn(
                    path, line, f"{path} is not byte-compiled by: {line[:80]}…"
                )

    def test_the_two_invocations_are_identical(self):
        first, second = self._compile_lines()
        self.assertEqual(
            first,
            second,
            "the default-Python and 3.9 compile jobs check different sets of files",
        )


class TheTwoStagingHelpersParseTheSameBindingGrammar(unittest.TestCase):
    """`.plan` and `.promptsha256` have one producer, one consumer and one grammar.

    Both are written by `bind-prompt.py` as `<64 hex>  <identity>\\n` and both are re-parsed by
    `review-verdict.py` with `_PLAN_BINDING`. Their staging helpers each validated the record before
    launching a 12-28 minute reviewer, and each originally took `fields[0]` — accepting a record
    truncated to its digest and spending the round on evidence the verdict writer would reject.

    The `.plan` case was reported and fixed first; the `.promptsha256` sibling was NOT swept and had to
    be reported separately. This gate is the sweep: the three spellings must stay identical.
    """

    PATTERN = r'rb"\A([0-9a-f]{64})  (.+)\n\Z"'

    def test_all_three_spell_the_binding_the_same_way(self):
        for rel, name in (
            ("scripts/review-verdict.py", "_PLAN_BINDING"),
            ("scripts/review/stage-bound-plan.py", "_PLAN_BINDING"),
            ("scripts/review/stage-prompt.py", "_PROMPT_BINDING"),
        ):
            source = _read(rel)
            self.assertIn(
                f"{name} = re.compile({self.PATTERN})",
                source,
                f"{rel}'s binding grammar drifted from the other two",
            )

    def test_neither_staging_helper_takes_only_the_first_field(self):
        """The defect itself: `fields[0]` accepts a record with no identity at all.

        Asserted against the ASSIGNMENT, not the bare token — both files explain the defect in a
        comment that names `fields[0]`, and a token search matched the explanation rather than the
        code. Grepping prose for a code property is the mistake this suite exists to catch elsewhere.
        """
        for rel in (
            "scripts/review/stage-bound-plan.py",
            "scripts/review/stage-prompt.py",
        ):
            source = _read(rel)
            self.assertNotIn(
                "expected = fields[0]", source, f"{rel} parses only the digest again"
            )
            self.assertIn(
                "fullmatch(record_bytes)",
                source,
                f"{rel} no longer validates the complete record",
            )


class COREDEV2780_TheEnforcedShellcheckGateMatchesTheDocumentedOne(unittest.TestCase):
    """CLAUDE.md publishes the gate a developer is told to run before committing; `plugin-ci.yml`
    runs the one that actually blocks. They drifted: the documented list named `scripts/ci/*.sh`
    and the enforced list did not, so the shared range resolver — the file the required check's
    guard pins by digest and then executes — was never shellchecked by CI.

    Both lists are DERIVED here rather than restated. A restated copy is a third thing to forget.
    """

    @staticmethod
    def _globs(command: str) -> set:
        return set(re.findall(r"\S+\*\.sh|\.githooks/pre-commit", command))

    def _documented(self) -> set:
        line = next(
            l
            for l in _read("CLAUDE.md").splitlines()
            if l.strip().startswith("shellcheck ")
        )
        return self._globs(line)

    def _enforced(self) -> set:
        workflow = _read(".github/workflows/plugin-ci.yml")
        line = next(
            l
            for l in workflow.splitlines()
            if "run:" in l and "shellcheck -s bash" in l
        )
        return self._globs(line)

    def test_the_enforced_gate_covers_everything_the_documentation_promises(self):
        missing = self._documented() - self._enforced()
        self.assertEqual(
            set(),
            missing,
            f"CLAUDE.md promises these are shellchecked and CI does not check them: {sorted(missing)}",
        )

    def test_the_documentation_promises_everything_the_gate_enforces(self):
        """Two-sided. A gate that checks MORE than the documentation says is also a drift — the next
        person to edit the docs will 'tidy' the extra path back out."""
        undocumented = self._enforced() - self._documented()
        self.assertEqual(
            set(),
            undocumented,
            f"CI shellchecks these and CLAUDE.md does not mention them: {sorted(undocumented)}",
        )

    def test_scripts_ci_is_in_both(self):
        """The specific omission this class was written for, named so a regression is legible."""
        self.assertIn("scripts/ci/*.sh", self._documented())
        self.assertIn("scripts/ci/*.sh", self._enforced())


if __name__ == "__main__":
    unittest.main()
