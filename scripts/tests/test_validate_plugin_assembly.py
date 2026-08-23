"""COREDEV-2503 F10 (model-id regex end anchor) + B4 (stale-tool hard reject) for
`scripts/validate-plugin-assembly.py::check_agent_fields`. The module has a hyphen in its name, so it is
loaded via importlib rather than imported."""
import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_MOD_PATH = os.path.join(os.path.dirname(__file__), "..", "validate-plugin-assembly.py")
_spec = importlib.util.spec_from_file_location("validate_plugin_assembly", _MOD_PATH)
vpa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vpa)


class ModelRegexAnchorTest(unittest.TestCase):
    def _problems(self, model):
        p: list[str] = []; w: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), {"model": model}, p, w)
        return p

    def test_valid_model_ids_pass(self):
        for m in ("claude-opus-4-8", "claude-3-5-sonnet-20241022", "claude-haiku-4-5"):
            self.assertEqual(self._problems(m), [], f"{m!r} is a valid model id")

    def test_trailing_content_rejected(self):
        # F10: re.fullmatch anchors BOTH ends; a valid PREFIX plus trailing content (incl. a newline, which
        # `$` would have allowed) must NOT pass — the prior start-only re.match accepted these.
        for m in ("claude-opus-4-8 rm -rf", "claude-opus-4-8; evil", "claude-opus-4-8\nmalicious"):
            self.assertTrue(self._problems(m), f"{m!r} (valid prefix + trailing) must be flagged")


class StaleToolRejectTest(unittest.TestCase):
    def _problems(self, tools):
        p: list[str] = []; w: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), {"tools": tools}, p, w)
        return p

    def test_kebab_allowed_tools_on_an_AGENT_is_a_hard_problem_with_the_reason(self):
        """`allowed-tools` is a skills/commands key. On a SUB-AGENT the runtime ignores it, so every
        restriction it expresses evaporates and the agent inherits ALL tools.

        The check exists to stop that recurring (audit pm-diagnostic.1 / orchestration.1) and had no
        test: adding `allowed-tools` to KNOWN_AGENT_KEYS, or neutering the hint branch, left the whole
        suite green while an agent carrying it validated clean.

        The hint text is asserted, not just the rejection. `allowed-tools` would otherwise fall
        through to the generic "unknown agent frontmatter key" message, which is also a hard problem —
        so a cell asserting only that SOME problem was raised passes with the specific branch gone,
        and the author never learns why their restriction did nothing.
        """
        problems: list[str] = []
        warnings: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), {"name": "x", "allowed-tools": "Read, Grep"},
                               problems, warnings)
        self.assertTrue(problems, "`allowed-tools` on an agent must be a hard problem")
        joined = " ".join(problems)
        self.assertIn("allowed-tools", joined)
        self.assertIn("inherits ALL tools", joined,
                      f"rejected, but without the reason — the author cannot tell that the "
                      f"restriction is silently ignored:\n{problems}")

    def test_a_legitimate_agent_key_is_not_rejected(self):
        """The control: `disallowedTools` IS a legal sub-agent key, and only the 'allowed' side is
        inert. Without this, a check that rejected every key would satisfy the cell above."""
        problems: list[str] = []
        warnings: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"),
                               {"name": "x", "disallowedTools": "Bash"}, problems, warnings)
        self.assertEqual([], problems, f"a legal sub-agent key was rejected: {problems}")

    def test_task_is_hard_rejected(self):
        # B4: `Task` is stale; the difflib guard finds no close match so it would slip through. An explicit
        # STALE_TOOLS reject is required (merely dropping it from KNOWN_TOOLS is a no-op).
        p = self._problems("Read, Task, Grep")
        self.assertTrue(any("stale" in x or "Agent" in x for x in p), f"`Task` must be rejected: {p}")

    def test_agent_is_accepted(self):
        self.assertEqual(self._problems("Read, Agent, Grep"), [], "`Agent` is the valid dispatcher tool")

    def test_block_scalar_description_not_comma_corrupted(self):
        # gemini review of #53: the block-list accumulation must NOT comma-join a `description: |` block
        # scalar (that corrupts prose). Space-join scalars; comma-join only real block-list items.
        md = "---\nname: x\ndescription: |\n  Line one.\n  Line two.\nmodel: inherit\n---\nbody\n"
        fm = vpa.parse_frontmatter(md)
        self.assertEqual(fm["description"], "Line one. Line two.")
        self.assertNotIn(",", fm["description"])
        # tools block list is unaffected (still comma-joined + Task caught)
        md2 = "---\nname: x\ndescription: y\nmodel: inherit\ntools:\n  - Read\n  - Task\n---\nb\n"
        fm2 = vpa.parse_frontmatter(md2); p: list[str] = []; w: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), fm2, p, w)
        self.assertTrue(any("stale" in x for x in p))

    def test_stale_task_case_insensitive(self):
        # gemini review of #53: a mixed-case stale dispatcher must still be rejected
        for tools in ("task", "TASK", "tAsK", "Read, task", "[TASK]", "- task"):
            p = self._problems(tools)
            self.assertTrue(any("stale" in x or "Agent" in x for x in p),
                            f"mixed-case stale tool {tools!r} must be rejected: {p}")

    def test_stale_task_in_yaml_list_forms(self):
        # audit of #53: `val.split(",")` alone missed the YAML flow-list and block-list forms
        for tools in ("[Task]", "[Task, Read]", "[Read, Task]", "- Task"):
            p = self._problems(tools)
            self.assertTrue(any("stale" in x or "Agent" in x for x in p),
                            f"`Task` in list form {tools!r} must be rejected: {p}")

    def test_valid_list_form_is_accepted(self):
        self.assertEqual(self._problems("[Read, Agent]"), [], "a valid flow-list must pass")

    def test_stale_task_in_multiline_block_list(self):
        # gemini review of #53: parse_frontmatter recorded only the FIRST block-list item, so a stale tool
        # past line 1 escaped. It must now accumulate ALL items.
        md = "---\nname: x\ndescription: y\nmodel: inherit\ntools:\n  - Read\n  - Task\n  - Grep\n---\nbody\n"
        fm = vpa.parse_frontmatter(md)
        p: list[str] = []; w: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), fm, p, w)
        self.assertTrue(any("stale" in x or "Agent" in x for x in p),
                        f"`Task` in a multi-line block list must be rejected: {p} (tools={fm.get('tools')!r})")

    def test_stale_task_with_inline_comment(self):
        # codex/gemini #53: a YAML inline comment on a block-list item must be stripped before the check
        md = "---\nname: x\ndescription: y\nmodel: inherit\ntools:\n  - Read\n  - Task # legacy\n---\nbody\n"
        fm = vpa.parse_frontmatter(md)
        p: list[str] = []; w: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), fm, p, w)
        self.assertTrue(any("stale" in x or "Agent" in x for x in p),
                        f"`Task # legacy` must be rejected: {p} (tools={fm.get('tools')!r})")

    def test_multiline_block_list_clean_passes(self):
        md = "---\nname: x\ndescription: y\nmodel: inherit\ntools:\n  - Read\n  - Agent\n---\nbody\n"
        fm = vpa.parse_frontmatter(md)
        p: list[str] = []; w: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), fm, p, w)
        self.assertEqual(p, [], f"a clean multi-line block list must pass: {p}")


class Column0BlockListTest(unittest.TestCase):
    def test_column0_block_list_parses_and_catches_stale(self):
        # MIN-21: a COLUMN-0 block list under `tools:` is legal YAML that Claude Code reads as a list,
        # but the old parser dropped it (leaving tools=''), so a stale `Task` in that form escaped.
        md = "---\nname: x\ndescription: y\ntools:\n- Read\n- Task\n---\nbody\n"
        fm = vpa.parse_frontmatter(md)
        self.assertIn("Read", fm.get("tools", ""))
        self.assertIn("Task", fm.get("tools", ""))
        p: list[str] = []; w: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), fm, p, w)
        self.assertTrue(any("stale" in x for x in p), f"stale Task in a column-0 list must be caught: {p}")

    def test_column0_clean_block_list_passes(self):
        md = "---\nname: x\ndescription: y\ntools:\n- Read\n- Agent\n---\nbody\n"
        fm = vpa.parse_frontmatter(md)
        p: list[str] = []; w: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), fm, p, w)
        self.assertEqual(p, [], f"a clean column-0 block list must pass: {p}")


class SkillPreloadListTest(unittest.TestCase):
    def test_forms_and_prefix(self):
        self.assertEqual(vpa.skill_preload_list({"skills": "[a, b]"}), ["a", "b"])
        self.assertEqual(vpa.skill_preload_list({"skills": "- a, - b"}), ["a", "b"])
        self.assertEqual(vpa.skill_preload_list({"skills": "unleashed-mail:swift-tdd"}), ["swift-tdd"])
        self.assertEqual(vpa.skill_preload_list({}), [])


class ModelTieringTest(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[2]

    def test_real_repo_tiers_match_frontmatter(self):
        # Guard rail: the shipped §11 table must equal the shipped model frontmatter (MAJ-1). Build the
        # model map the same way the validator does, from agents/*.md, then assert zero tier problems.
        models = {}
        for ap in sorted((self.ROOT / "agents").glob("*.md")):
            fm = vpa.parse_frontmatter(ap.read_text(encoding="utf-8-sig")) or {}
            models[ap.stem] = fm.get("model", "").strip() or "inherit"
        p: list[str] = []; w: list[str] = []
        vpa.check_model_tiering(self.ROOT, models, p)
        self.assertEqual(p, [], f"§11 must equal the shipped frontmatter: {p}")

    def test_mismatched_model_is_flagged(self):
        p: list[str] = []; w: list[str] = []
        vpa.check_model_tiering(self.ROOT, {"jira-manager": "opus"}, p)
        self.assertTrue(any("jira-manager" in x and "opus" in x for x in p), p)


class ReviewerRosterTest(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[2]

    def test_real_repo_roster_agrees(self):
        agents = {p.stem for p in (self.ROOT / "agents").glob("*.md")}
        p: list[str] = []; w: list[str] = []
        vpa.check_reviewer_roster(self.ROOT, agents, p)
        self.assertEqual(p, [], f"the six roster copies must agree and all exist as agents: {p}")

    def test_missing_reviewer_agent_is_flagged(self):
        # If agents/<name>.md is gone but the roster still lists it, that must be flagged.
        p: list[str] = []; w: list[str] = []
        vpa.check_reviewer_roster(self.ROOT, {"security-reviewer"}, p)
        self.assertTrue(any("does not exist" in x for x in p), p)


class McpServerPathTest(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[2]

    def test_real_repo_mcp_paths_resolve(self):
        p: list[str] = []; w: list[str] = []
        vpa.check_mcp_server_paths(self.ROOT, p)
        self.assertEqual(p, [], f".mcp.json server targets must resolve on disk: {p}")




class COREDEV2583_ModelAliasTable(unittest.TestCase):
    """§4.4 — MODEL_ALIASES is the pinned runtime's table verbatim, not a synthesised one.

    Mutation proof: revert MODEL_ALIASES to the old five-alias set and the accept cases fail;
    replace exact membership with 'strip [1m] then re-validate' and the over-accept cases fail.
    """

    def _problems(self, model):
        p, w = [], []
        vpa.check_agent_fields(Path("agents/x.md"), {"model": model}, p, w)
        return p

    def test_supported_aliases_and_ids_accepted(self):
        for model in ("sonnet", "opus", "haiku", "fable", "best", "opusplan", "inherit",
                      "sonnet[1m]", "opus[1m]", "fable[1m]", "claude-opus-5", "claude-sonnet-4-5"):
            with self.subTest(model=model):
                self.assertEqual(self._problems(model), [], f"{model} should be accepted")

    def test_unsupported_alias_suffix_combinations_rejected(self):
        # The runtime table has ONLY sonnet/opus/fable with [1m]. A strip-then-revalidate rule
        # would wrongly accept every one of these.
        for model in ("haiku[1m]", "best[1m]", "opusplan[1m]", "inherit[1m]"):
            with self.subTest(model=model):
                self.assertTrue(self._problems(model), f"{model} is not in the runtime table")

    def test_default_is_not_an_alias(self):
        # An earlier draft of COREDEV-2583 proposed adding `default`; it is absent from `h1e`.
        self.assertTrue(self._problems("default"))

    def test_f10_injection_negatives_still_rejected(self):
        for model in ("claude-opus-5 rm -rf", "claude-opus-5; evil", "claude-opus-5\nmalicious",
                      "opus[1m;evil]", "opus[1m\nmalicious]", "opus[rm-rf]",
                      "opus[1m][1m]", "opus[1m]x", "opus[1m", "opus[]"):
            with self.subTest(model=model):
                self.assertTrue(self._problems(model), f"{model!r} must stay rejected (F10)")


class COREDEV2583_ToolSets(unittest.TestCase):
    """§4.5 — refreshed KNOWN_TOOLS; MultiEdit hard-rejected; typo guard demoted to advisory."""

    def _run(self, tools):
        p, w = [], []
        vpa.check_agent_fields(Path("agents/x.md"), {"tools": tools}, p, w)
        return p, w

    def test_previously_false_rejected_tools_are_clean(self):
        # Both were rejected as difflib near-misses (TaskOutput~BashOutput, EnterPlanMode~ExitPlanMode).
        for tool in ("TaskOutput", "EnterPlanMode", "ToolSearch", "Monitor", "Workflow"):
            with self.subTest(tool=tool):
                p, w = self._run(tool)
                self.assertEqual(p, [], f"{tool} is a real tool and must not be a problem")
                self.assertEqual(w, [], f"{tool} is known and must not even warn")

    def test_multiedit_is_hard_rejected_not_merely_unknown(self):
        # Dropping it from KNOWN_TOOLS alone is a no-op: unknown tools are accepted.
        p, w = self._run("MultiEdit")
        self.assertTrue(p, "MultiEdit must be a hard problem, not an accepted unknown")
        self.assertIn("Edit", p[0])

    def test_stale_tool_reasons_are_tool_specific(self):
        # A shared message would be false for one of them.
        p_task, _ = self._run("Task")
        p_multi, _ = self._run("MultiEdit")
        self.assertIn("dispatcher is `Agent`", p_task[0])
        self.assertNotIn("dispatcher is `Agent`", p_multi[0])

    def test_typo_guard_is_advisory_not_blocking(self):
        p, w = self._run("Raed")            # near-miss of Read
        self.assertEqual(p, [], "a near-miss must not fail the build (§4.5)")
        self.assertTrue(w, "a near-miss must still be surfaced as a warning")


class COREDEV2583_SkillKeys(unittest.TestCase):
    """§4.6 — skill frontmatter validation, derived from the pinned runtime schema."""

    def _run(self, fm):
        p, w = [], []
        vpa.check_skill_fields(Path("skills/x/SKILL.md"), fm, p, w)
        return p, w

    def test_disallowedTools_is_a_LEGAL_alias(self):
        # THE round-1 regression guard: an earlier draft would have rejected this legal field.
        # Assert NEITHER a problem NOR a warning: if the key were merely dropped from
        # KNOWN_SKILL_KEYS it would fall through to the advisory branch, and a problems-only
        # assertion would still pass — i.e. the mutation test would not fail.
        p, w = self._run({"name": "x", "description": "y", "disallowedTools": "AskUserQuestion"})
        self.assertEqual(p, [], "`disallowedTools` is the runtime's canonical alias — must pass")
        self.assertEqual(w, [], "`disallowedTools` is KNOWN — it must not even warn")

    def test_allowedTools_is_a_targeted_error(self):
        p, w = self._run({"name": "x", "description": "y", "allowedTools": "Read"})
        self.assertTrue(p)
        self.assertIn("allowed-tools", p[0], "the error must name the kebab form")

    def test_every_derived_key_validates_clean(self):
        p, w = self._run({k: "v" for k in vpa.KNOWN_SKILL_KEYS})
        self.assertEqual(p, [])
        self.assertEqual(w, [])

    def test_unknown_key_warns_but_does_not_fail(self):
        # The schema moves between releases; a hard reject would block a legitimate new key.
        p, w = self._run({"name": "x", "description": "y", "some-future-key": "v"})
        self.assertEqual(p, [])
        self.assertTrue(w)


class COREDEV2583_WarningsChannel(unittest.TestCase):
    """§4.7 — keys Claude Code ignores for plugin sub-agents warn, and never fail strict."""

    def test_plugin_ignored_keys_warn(self):
        for key in ("permissionMode", "mcpServers", "hooks"):
            with self.subTest(key=key):
                p, w = [], []
                vpa.check_agent_fields(Path("agents/x.md"),
                                       {"name": "x", "description": "y", key: "v"}, p, w)
                self.assertEqual(p, [], f"`{key}` is a legal key — must not be a problem")
                self.assertTrue(w, f"`{key}` must warn: it is silently ignored for plugin sub-agents")
                self.assertIn("IGNORED", w[0])


class COREDEV2583_EffortPolicy(unittest.TestCase):
    """§4.3 — the effort floor is asserted on BOTH axes and in the §11 policy text.

    The first cut of `check_effort_policy` was called before the skills loop had run, so it
    silently checked only agents and a missing SKILL pin passed. These cases pin both axes.
    """

    def _problems(self, efforts, policy_line=True):
        p = []
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            body = ("## 11. Model Tiering Policy\n\n"
                    + ("**Effort policy: assets INHERIT the session effort — no agent or skill pins an effort below `xhigh`.**"
                       if policy_line else "**Effort policy: pick something sensible.**\n"))
            (root / "AGENT_CONTRACTS.md").write_text(body, encoding="utf-8")
            vpa.check_effort_policy(root, efforts, p)
        return p

    def test_all_pinned_is_clean(self):
        self.assertEqual(
            self._problems({"agents/a.md": "xhigh", "skills/s/SKILL.md": "xhigh"}), [])

    def test_absent_pin_is_legal_because_it_INHERITS(self):
        # The policy is a FLOOR, not a pin. Omitting `effort:` means the asset inherits the
        # session level, so a `max` session reaches its subagents instead of being silently
        # capped at xhigh — frontmatter effort overrides the session in BOTH directions.
        self.assertEqual(
            self._problems({"agents/a.md": "", "skills/s/SKILL.md": ""}), [],
            "omitting `effort:` is inheritance, not drift, and must not fail")

    def test_downward_pin_fails_on_both_axes(self):
        # A skill must be checked as well as an agent — the ordering-bug regression guard.
        for level in ("high", "medium", "low"):
            for rel in ("agents/a.md", "skills/s/SKILL.md"):
                with self.subTest(level=level, asset=rel):
                    p = self._problems({rel: level})
                    self.assertTrue(p, f"`effort: {level}` is below the floor and must fail")
                    self.assertIn(rel, p[0])

    def test_pins_at_or_above_the_floor_are_legal(self):
        for level in ("xhigh", "max"):
            with self.subTest(level=level):
                self.assertEqual(
                    self._problems({"agents/a.md": level, "skills/s/SKILL.md": level}), [],
                    f"`effort: {level}` is at or above the floor and must be accepted")

    def test_policy_sentence_must_state_the_floor(self):
        p = self._problems({"agents/a.md": "xhigh"}, policy_line=False)
        self.assertTrue(p)
        self.assertIn("effort policy line", p[0])


class COREDEV2583_EffortPolicyWiring(unittest.TestCase):
    """The check must run AFTER every asset walk, or it is inert for skills (ordering bug)."""

    def test_effort_check_is_called_after_the_skills_loop(self):
        src = Path(_MOD_PATH).read_text(encoding="utf-8")
        call = src.index("check_effort_policy(root, asset_efforts, problems)",
                         src.index("def main("))
        skills_loop = src.index("for p in skills:", src.index("def main("))
        self.assertGreater(call, skills_loop,
                           "check_effort_policy must run after the skills loop populates "
                           "asset_efforts — otherwise a missing SKILL pin passes silently")


if __name__ == "__main__":
    unittest.main()


# The count `validate-version-sync.sh` enforces against `plugin.json` and the README. Pinned here so
# a tree walk that silently visits nothing cannot pass for a clean one.
SHIPPED_SKILL_COUNT = 21


class ModelReachableGrantPolicy(unittest.TestCase):
    """Deep review P1: a model-invocable skill pre-approves every tool it lists, with no user gesture.

    The reviewer named three skills; the check found the same class in eight. Each case below is a
    PAIR — the broad form is rejected and a scoped form of the SAME tool is accepted — because a check
    that rejected the tool outright would just push authors to `disable-model-invocation`.
    """

    def _check(self, granted, extra=None):
        problems, warnings = [], []
        frontmatter = {"allowed-tools": granted}
        frontmatter.update(extra or {})
        vpa.check_model_reachable_grants(
            Path("skills/x/SKILL.md"), frontmatter, problems, warnings
        )
        return problems, warnings

    def test_bare_write_edit_and_agent_are_rejected(self):
        for granted in ("Read, Write", "Read, Edit", "Read, Agent", "Read, Bash", "Read, NotebookEdit"):
            with self.subTest(granted=granted):
                problems, _ = self._check(granted)
                self.assertTrue(problems, f"{granted!r} must be rejected on a model-invocable skill")

    def test_scoped_forms_of_the_same_tools_are_accepted(self):
        for granted in (
            "Read, Write(docs/planning/**)",
            "Read, Edit(src/**)",
            "Read, Agent(db-engineer), Agent(unleashed-mail:db-engineer)",
            "Read, Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/persist-verdict.sh *)",
        ):
            with self.subTest(granted=granted):
                problems, _ = self._check(granted)
                self.assertEqual([], problems, f"{granted!r} is scoped and must be accepted")

    def test_vcs_and_reviewer_cli_wildcards_are_rejected(self):
        for granted in ("Bash(git *)", "Bash(gh *)", "Bash(codex *)", "Bash(agy *)", "Bash(rm *)"):
            with self.subTest(granted=granted):
                problems, _ = self._check(granted)
                self.assertTrue(problems, f"{granted!r} is an unbounded CLI wildcard")

    def test_a_wildcard_in_the_script_path_is_rejected(self):
        """`Bash(python3 …/scripts/*)` pre-approves EVERY script in the directory.

        That is the form that pre-approved the destructive cleanup tool with `--apply` and
        `pty-capture.py <any path> -- <any command>` — arbitrary child execution.
        """
        problems, _ = self._check("Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)")
        self.assertTrue(problems)
        self.assertIn("SCRIPT PATH", problems[0])

        problems, _ = self._check("Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/*)")
        self.assertTrue(problems, "a directory wildcard is unbounded for `bash` too")

    def test_disable_model_invocation_opts_out(self):
        """A user must type the name of a non-model-invocable skill, which is the missing gesture."""
        problems, _ = self._check("Read, Write, Bash(git *)")
        self.assertTrue(problems)
        problems, _ = self._check(
            "Read, Write, Bash(git *)", extra={"disable-model-invocation": "true"}
        )
        self.assertEqual([], problems)

    def test_shell_operators_after_an_allowlisted_wrapper_are_rejected(self):
        """Reaching an allowlisted target was treated as the whole answer (PR #63 recheck, P2).

        Everything after the wrapper went unexamined, so `&& rm *`, `; rm -rf *`, `$(rm *)`, a
        redirection and a pipe all passed while CI called the tree clean. The policy claims one exact
        reviewed entrypoint, and that claim is only true if nothing can be appended to it.
        """
        wrapper = "${CLAUDE_PLUGIN_ROOT}/scripts/review/audit-codex.sh"
        for tail in ("&& rm *", "; rm -rf *", "$(rm *)", "> /etc/x *", "| tee *", "`rm *`"):
            with self.subTest(tail=tail):
                problems, _warnings = self._check(f"Read, Bash(bash {wrapper} {tail})")
                self.assertTrue(problems, f"`{tail}` after the wrapper must be refused")

    def test_the_plain_wrapper_grant_is_still_accepted(self):
        """Control. The trailing-token rule must reject OPERATORS, not operands."""
        for granted in (
            "Read, Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/audit-codex.sh *)",
            "Read, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py snapshot *)",
        ):
            with self.subTest(granted=granted):
                problems, _warnings = self._check(granted)
                self.assertEqual([], problems, granted)

    def test_a_wildcard_free_COMPOUND_grant_is_now_refused(self):
        """PR #63 recheck, P2: the no-wildcard exemption was a fail-open, and is now closed.

        This test previously ASSERTED that `Bash(bash …/x.sh && rm -rf /tmp/x)` passed, documenting the
        `*`-only analysis scope as a deliberate boundary. The recheck showed it for what it was — a
        `*`-free two-command program that pre-approves `rm -rf`. The operator scan now runs for every
        specifier, so the `&&` (and `;`, `|`, backtick, redirection, `$(`) is refused whether or not a
        wildcard is present.
        """
        for granted in (
            "Read, Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/audit-codex.sh && rm -rf /tmp/x)",
            "Read, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/x.py;rm -rf /)",
            "Read, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/x.py|tee /etc/passwd)",
            "Read, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/x.py > /etc/x)",
        ):
            with self.subTest(granted=granted):
                problems, _warnings = self._check(granted)
                self.assertTrue(problems, f"{granted} is a compound program and must be refused")

    def test_a_genuinely_bounded_single_command_stays_exempt(self):
        """The boundary that REMAINS: one command, no operators, no wildcard.

        Whether a bounded-but-dangerous exact command belongs on a model-invocable skill is a different
        policy this check deliberately does not claim. A single command with no shell operators — the
        shape of the two shipped preflight probes — must still pass, or the operator scan has
        over-reached into refusing legitimate exact grants.
        """
        for granted in ("Read, Bash(command -v codex)", "Read, Bash(codex --version)",
                        "Read, Bash(git reset --hard)"):
            with self.subTest(granted=granted):
                problems, _warnings = self._check(granted)
                self.assertEqual([], problems, f"{granted} is one bounded command and must stay exempt")

    def test_a_full_breadth_write_or_agent_scope_is_refused(self):
        """`Write(**)`/`Agent(*)` pre-approve the same surface as the bare grant (PR #63 recheck, P2).

        The bare-name exemption was exact-string, so the scoped spellings slipped past it.
        """
        for granted in ("Write(**)", "Write(/**)", "Edit(**)", "NotebookEdit(**)", "Agent(*)"):
            with self.subTest(granted=granted):
                problems, _warnings = self._check("Read, " + granted)
                self.assertTrue(problems, f"{granted} is full-breadth and must be refused")
        # ...but a real scope must still pass.
        self.assertEqual([], self._check("Write(docs/planning/**), Agent(db-engineer)")[0])

    def test_nested_parens_do_not_truncate_the_specifier(self):
        """`re.findall(r'Bash\\(([^)]*)\\)')` stopped at the first `)` and dropped the trailing `*`.

        `Bash(python3 …/x.py $(rm) *)` then looked wildcard-free and skipped analysis. Balanced
        extraction keeps the whole specifier so the `$(` and `*` are both seen and refused.
        """
        problems, _warnings = self._check(
            "Read, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/x.py $(rm) *)")
        self.assertTrue(problems, "a nested-paren specifier truncated its wildcard and passed")

    def test_wildcard_bash_is_default_deny(self):
        """The measured fail-open, inverted (PR #63 recheck, P2).

        The old rule deny-listed a fixed set of command NAMES and passed everything else. Each probe
        below produced zero problems and zero warnings under it — including `python3 -c *`, which is
        arbitrary code execution that slipped through the interpreter branch because `-c` is not a
        script path and so never met the "wildcard in the path" test.

        Trampolines moved from advisory to refused in the same change: the advisory tier existed for
        knowledge skills whose grants have since been removed, so nothing shipped depends on it.
        """
        for granted in (
            "Bash(python3 -c *)", "Bash(sh -c *)", "Bash(cp *)", "Bash(mv *)", "Bash(tee *)",
            "Bash(find *)", "Bash(curl *)", "Bash(chmod *)", "Bash(node -e *)",
            "Bash(python3 -m http.server *)", "Bash(swiftlint *)", "Bash(xcodebuild *)",
            "Bash(xcrun *)", "Bash(swift *)", "Bash(bash /tmp/evil.sh *)", "Bash(*)",
        ):
            with self.subTest(granted=granted):
                problems, _warnings = self._check("Read, " + granted)
                self.assertTrue(problems, f"{granted} must be refused under default-deny")

    def test_the_allowlisted_shapes_still_pass(self):
        """Default-deny is worthless if it also refuses the wrappers the plugin actually ships.

        An exact script beneath `${CLAUDE_PLUGIN_ROOT}` may carry a trailing wildcard because the
        script bounds its own operands — that is the property being relied on, not the location alone.
        """
        for granted in (
            "Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/review/audit-codex.sh *)",
            "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py snapshot *)",
            "Bash(command -v codex)",
            "Bash(codex --version)",
        ):
            with self.subTest(granted=granted):
                problems, _warnings = self._check("Read, " + granted)
                self.assertEqual([], problems, granted)

    def test_every_shipped_skill_satisfies_the_policy(self):
        """The tree itself, so the policy cannot pass on fixtures while the shipped assets violate it."""
        root = Path(_MOD_PATH).resolve().parents[1]
        offenders = []
        for skill in sorted((root / "skills").glob("*/SKILL.md")):
            frontmatter = vpa.parse_frontmatter(skill.read_text(encoding="utf-8"))
            if not frontmatter:
                continue
            problems: list[str] = []
            vpa.check_model_reachable_grants(
                Path(skill.relative_to(root).as_posix()), frontmatter, problems, []
            )
            offenders.extend(problems)
        self.assertEqual([], offenders)

    def test_no_shipped_skill_carries_a_trampoline_grant_either(self):
        """The advisory tier is a tripwire for NEW grants, not a standing exception list.

        Seven of these warnings sat on `macos-debugging`, `spm-management` and `swift-tdd` and were
        measured before being removed rather than after: three were dead (the command never appeared
        in the body — `spm-management` granted `Bash(swift *)` while its own prose says the swift CLI
        does not apply to this project), and every live one was inside a COMPOUND block
        (`set -o pipefail` … `| tail`), which Claude Code decomposes per-subcommand — so the grant
        never pre-approved the block it existed for. They cost a standing toolchain pre-approval on
        model-reachable skills and bought nothing measurable, so they are gone.

        This asserts the *warning* channel, which the problem-level test above discards. Without it
        the tree can drift back to seven warnings while every hard check still reports green.
        """
        root = Path(_MOD_PATH).resolve().parents[1]
        advisories = []
        examined = 0
        for skill in sorted((root / "skills").glob("*/SKILL.md")):
            frontmatter = vpa.parse_frontmatter(skill.read_text(encoding="utf-8"))
            if not frontmatter:
                continue
            examined += 1
            warnings: list[str] = []
            vpa.check_model_reachable_grants(
                Path(skill.relative_to(root).as_posix()), frontmatter, [], warnings
            )
            advisories.extend(warnings)
        # Counted, not assumed. `skills/*/SKILL.md` is a glob and `parse_frontmatter` can return
        # nothing: either would walk zero skills and certify a tree this never looked at, and an
        # empty loop's `assertEqual([], advisories)` is indistinguishable from a clean one. A fixture
        # asserting the checker warns on `Bash(xcodebuild *)` does NOT cover this — it exercises a
        # different mechanism than the loop it is supposed to guard.
        self.assertEqual(SHIPPED_SKILL_COUNT, examined, "the shipped-skill walk found the wrong number")
        self.assertEqual([], advisories)


class SpawnerDeniesEveryWriter(unittest.TestCase):
    """A bare `Agent` grant reaches every agent, so the writers must be denied by name — and STAY denied.

    `swift-reviewer` is spawned from `pr-review` while it processes untrusted PR content. Its `tools:`
    lists bare `Agent` because a sub-agent tool list takes bare names — `Agent(type)` is ignored there —
    so it could reach all twelve file-writing agents, and a prompt-injected finding could have steered it
    into `ui-engineer` or `db-engineer` with no user gesture (PR #63 recheck, P1).

    The only lever is `disallowedTools`, which makes it a deny-list. The check below recomputes the
    writer set from the agents on disk, so the list cannot silently fall behind — that is the property
    under test, not the current contents.
    """

    def _run(self, root):
        problems: list[str] = []
        vpa.check_spawner_denies_every_writer(root, problems)
        return problems

    def test_the_shipped_tree_denies_every_writer(self):
        self.assertEqual([], self._run(Path(_MOD_PATH).resolve().parents[1]))

    def test_a_newly_added_writer_agent_is_UNREACHABLE_under_a_scoped_grant(self):
        """COREDEV-2703 changed what protects this, so this cell changed with it.

        It used to assert that a new writer agent was CAUGHT by the deny-list — the way a deny-list
        re-opens. `swift-reviewer` no longer carries one: its `Agent` grant is now a scoped ALLOWLIST,
        so a thirteenth writer is unreachable by construction and there is correctly nothing to
        report. Asserting the old expectation here would demand a deny-list that must not come back —
        the 26 `Agent(x)` entries are exactly what removed the agent's `Agent` tool.

        The structural guarantee is asserted directly: the new writer must not appear in the
        allowlist. The check's teeth for BARE-`Agent` agents are preserved by the sibling cell below.
        """
        import shutil
        import tempfile

        root = Path(tempfile.mkdtemp(prefix="spawner-drift-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "agents").mkdir()
        shipped = Path(_MOD_PATH).resolve().parents[1] / "agents" / "swift-reviewer.md"
        shutil.copy2(shipped, root / "agents" / "swift-reviewer.md")
        (root / "agents" / "rogue-writer.md").write_text(
            "---\nname: rogue-writer\ndescription: x\ntools: Read, Write, Edit, Bash\n---\nbody\n",
            encoding="utf-8",
        )
        self.assertEqual([], self._run(root),
                         "a scoped grant needs no writer denials — demanding them is what put the "
                         "`Agent(x)` entries in the deny-list and removed the `Agent` tool")
        granted = vpa._tool_tokens(
            vpa.parse_frontmatter(shipped.read_text(encoding="utf-8")).get("tools", ""))
        scoped = next(t for t in granted if t.startswith("Agent("))
        self.assertNotIn("rogue-writer", scoped,
                         "the new writer is reachable — the allowlist is not doing its job")

    def test_a_BARE_Agent_spawner_still_must_deny_every_writer(self):
        """The teeth, preserved. The check must still catch an agent that grants bare `Agent` — which
        reaches every type — and omits a writer denial. Without this the change above would have
        removed the rule rather than relocated it."""
        import shutil
        import tempfile

        root = Path(tempfile.mkdtemp(prefix="spawner-bare-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "agents").mkdir()
        (root / "agents" / "bare-spawner.md").write_text(
            "---\nname: bare-spawner\ndescription: x\ntools: Read, Agent\n"
            "disallowedTools: Write, Edit, NotebookEdit\n---\nbody\n", encoding="utf-8")
        (root / "agents" / "rogue-writer.md").write_text(
            "---\nname: rogue-writer\ndescription: x\ntools: Read, Write, Edit, Bash\n---\nbody\n",
            encoding="utf-8")
        problems = self._run(root)
        self.assertTrue(problems, "a BARE `Agent` spawner that omits a writer denial must be caught")
        self.assertIn("rogue-writer", problems[0])

    def test_a_read_only_agent_does_not_have_to_be_denied(self):
        """The rule must not demand denying agents that cannot write — that would be noise, and noise
        is how a real finding gets skimmed past."""
        import shutil
        import tempfile

        root = Path(tempfile.mkdtemp(prefix="spawner-readonly-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "agents").mkdir()
        shutil.copy2(Path(_MOD_PATH).resolve().parents[1] / "agents" / "swift-reviewer.md",
                     root / "agents" / "swift-reviewer.md")
        (root / "agents" / "harmless-reader.md").write_text(
            "---\nname: harmless-reader\ndescription: x\ntools: Read, Grep, Glob\n---\nbody\n",
            encoding="utf-8",
        )
        self.assertEqual([], self._run(root))


class BashlessAgentsRunNoShell(unittest.TestCase):
    """Removing `Bash` is only safe if the body stopped needing it.

    Four reviewers had `Bash` removed; two bodies still called `cat`, `find` and `plutil`. `Grep`
    cannot execute any of those, so those audit sections would have produced NOTHING while the agent
    reported a complete review — and the note added beside the change asserted the opposite, because it
    was checked against the dominant pattern rather than the whole set (PR #63 recheck).

    A missing capability that announces itself is a bug. One that silently drops a section is a false
    clean bill of health, which is strictly worse.
    """

    def _run(self, root):
        problems: list[str] = []
        vpa.check_bashless_agents_run_no_shell(root, problems)
        return problems

    def test_the_shipped_agents_are_consistent(self):
        self.assertEqual([], self._run(Path(_MOD_PATH).resolve().parents[1]))

    def test_a_shell_only_command_in_a_bashless_agent_is_caught(self):
        import shutil
        import tempfile

        root = Path(tempfile.mkdtemp(prefix="bashless-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "agents").mkdir()
        (root / "agents" / "reader.md").write_text(
            "---\nname: reader\ndescription: x\ntools: Read, Grep, Glob\n---\n"
            "```bash\ncat *.entitlements\n```\n",
            encoding="utf-8",
        )
        problems = self._run(root)
        self.assertTrue(problems)
        self.assertIn("cat", problems[0])

    def test_grep_is_exempt_because_the_Grep_tool_does_it(self):
        """The exemption is the entire basis for removing Bash — if grep were flagged too, the rule
        would demand giving Bash back, which is the opposite of the fix."""
        import shutil
        import tempfile

        root = Path(tempfile.mkdtemp(prefix="bashless-grep-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "agents").mkdir()
        (root / "agents" / "reader.md").write_text(
            "---\nname: reader\ndescription: x\ntools: Read, Grep, Glob\n---\n"
            '```bash\ngrep -rn "pattern" Sources/\n```\n',
            encoding="utf-8",
        )
        self.assertEqual([], self._run(root))

    def test_an_agent_that_still_holds_Bash_is_out_of_scope(self):
        """`swift-reviewer` genuinely needs Bash; the rule must not push it to drop working recipes."""
        import shutil
        import tempfile

        root = Path(tempfile.mkdtemp(prefix="bashful-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "agents").mkdir()
        (root / "agents" / "runner.md").write_text(
            "---\nname: runner\ndescription: x\ntools: Read, Bash, Grep\n---\n"
            "```bash\ncat *.entitlements\n```\n",
            encoding="utf-8",
        )
        self.assertEqual([], self._run(root))


class ScopedAgentGrantsParseAsOneToken(unittest.TestCase):
    """COREDEV-2703. `_tool_tokens` split on EVERY comma, so the documented multi-type grant
    `Agent(worker, researcher)` became `Agent(worker` + `researcher)` — two tokens matching nothing.

    That mis-parse is why no gate caught the bug: the validator could not represent the form the
    runtime documents, so a frontmatter that removed `swift-reviewer`'s own `Agent` tool validated
    clean. Measured on Claude Code 2.1.241 / plugin 2.8.0 — the shipped agent received only `Read`,
    `Bash` and the synthesizer MCP tool, and reported `AGENT: NO_SUCH_TOOL`.
    """

    def test_a_multi_type_scoped_grant_is_ONE_token(self):
        tokens = vpa._tool_tokens("Read, Agent(worker, researcher), Bash")
        self.assertEqual({"Read", "Agent(worker, researcher)", "Bash"}, tokens,
                         "commas inside parentheses are TYPE separators, not token separators")

    def test_top_level_commas_still_separate(self):
        """The control: the paren-awareness must not stop ordinary lists splitting, which is the
        property the substring-membership fix of PR #63 depends on."""
        self.assertEqual({"Write", "Edit", "NotebookEdit"},
                         vpa._tool_tokens("Write, Edit, NotebookEdit"))
        self.assertEqual({"Write", "Agent(ui-engineer)"},
                         vpa._tool_tokens("Write, Agent(ui-engineer)"))

    def test_a_scoped_grant_is_NOT_the_bare_Agent_tool(self):
        """The distinction the spawner check rests on: a scoped grant is an allowlist, so writers are
        excluded by construction and no deny-list entry is required. A bare `Agent` reaches every
        agent and still needs them."""
        self.assertNotIn("Agent", vpa._tool_tokens("Read, Agent(security-reviewer)"))
        self.assertIn("Agent", vpa._tool_tokens("Read, Agent"))

    def test_the_shipped_swift_reviewer_grants_a_SCOPED_Agent(self):
        """The regression pin. If this file ever goes back to a bare `Agent` plus `Agent(x)` denials,
        the panel loses its spawn tool again and every review runs with no specialists."""
        root = Path(_MOD_PATH).resolve().parents[1]
        fm = vpa.parse_frontmatter((root / "agents" / "swift-reviewer.md").read_text(encoding="utf-8"))
        granted = vpa._tool_tokens(fm.get("tools", ""))
        scoped = [t for t in granted if t.startswith("Agent(")]
        self.assertEqual(1, len(scoped),
                         f"swift-reviewer must grant exactly one SCOPED Agent entry, got {sorted(granted)}")
        self.assertNotIn("Agent", granted,
                         "a bare `Agent` alongside the scoped grant re-opens every agent type")
        for reviewer in ("security-reviewer", "concurrency-reviewer", "ux-perf-reviewer",
                         "accessibility-auditor", "prompt-review"):
            self.assertIn(reviewer, scoped[0],
                          f"the panel cannot spawn {reviewer} — it is not in the allowlist")
            self.assertIn(f"unleashed-mail:{reviewer}", scoped[0],
                          f"{reviewer} is granted only in its bare spelling; a consumer install "
                          f"resolves the namespaced one")
        denied = vpa._tool_tokens(fm.get("disallowedTools", ""))
        self.assertEqual(set(), {d for d in denied if d.startswith("Agent(")},
                         "an `Agent(x)` DENY entry is what removed the tool — the allowlist is the "
                         "only lever now")


class WriterPredicateAndSpawnerDetection(unittest.TestCase):
    """PR #63 recheck, P1: writer means "can modify the checkout", and inherit-all agents spawn too.

    The first predicate tested only `Write`/`Edit` — by SUBSTRING — so three distinct agents escaped:
    an inherit-all agent denying the two file editors while keeping unrestricted `Bash` (the
    jira-manager shape), an agent whose `NotebookEdit` deny satisfied the `Edit` probe with `Edit`
    still live, and a `memory:` agent whose auto-enabled Write never appeared in its `tools:` list.
    Spawner detection had the matching blind spot: `tools:` omitted inherits `Agent` exactly as it
    inherits `Bash`, and the explicit-list-only detection skipped every such agent.
    """

    def _root(self, agents: "dict[str, str]") -> Path:
        base = Path(tempfile.mkdtemp(prefix="vpa-writers-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        (base / "agents").mkdir()
        for name, frontmatter_tail in agents.items():
            (base / "agents" / f"{name}.md").write_text(
                f"---\nname: {name}\ndescription: x\n{frontmatter_tail}---\nbody\n",
                encoding="utf-8",
            )
        return base

    def _spawner_problems(self, agents: "dict[str, str]") -> "list[str]":
        problems: "list[str]" = []
        vpa.check_spawner_denies_every_writer(self._root(agents), problems)
        return problems

    SPAWNER = "tools: Read, Agent\n"

    def test_unrestricted_bash_makes_an_inherit_all_agent_a_writer(self):
        problems = self._spawner_problems({
            "shelly": "disallowedTools: Write, Edit, NotebookEdit, Agent\n",
            "spawny": self.SPAWNER,
        })
        self.assertTrue(any("spawny" in p and "shelly" in p for p in problems),
                        f"a live-Bash inherit-all agent must be a writer: {problems}")

    def test_denying_every_write_vector_clears_it(self):
        problems = self._spawner_problems({
            "shelly": "disallowedTools: Write, Edit, NotebookEdit, Bash, Agent\n",
            "spawny": self.SPAWNER,
        })
        self.assertEqual([], problems,
                         "an agent with every write vector denied must be freely spawnable")

    def test_edit_denial_is_not_satisfied_by_a_NotebookEdit_substring(self):
        """`"Edit" in "Write, NotebookEdit, …"` is True — the substring hole, now closed by tokens."""
        problems = self._spawner_problems({
            "eddy": "disallowedTools: Write, NotebookEdit, Bash, Agent\n",
            "spawny": self.SPAWNER,
        })
        self.assertTrue(any("eddy" in p for p in problems),
                        f"`Edit` is live on eddy and must classify it a writer: {problems}")

    def test_an_inherit_all_agent_holds_Agent_and_is_a_spawner(self):
        problems = self._spawner_problems({
            "planner": "\n",
            "wrx": "tools: Read, Write\n",
        })
        self.assertTrue(any("planner.md" in p and "wrx" in p for p in problems),
                        f"an inherit-all agent holds bare Agent and must be checked: {problems}")
        self.assertEqual([], self._spawner_problems({
            "planner": "disallowedTools: Agent\n",
            # wrx alone: a writer with no spawner in sight is not a finding.
            "wrx": "tools: Read, Write\n",
        }))

    def test_memory_auto_enables_write_capability(self):
        problems = self._spawner_problems({
            "memo": "tools: Read, Grep, Glob\nmemory: project\n",
            "spawny": self.SPAWNER,
        })
        self.assertTrue(any("memo" in p for p in problems),
                        f"`memory:` re-grants Write/Edit and must classify a writer: {problems}")

    def test_bashless_by_denial_bodies_are_swept_for_shell(self):
        """`jira-manager` becomes bashless BY DENY — its recipes must be checked like any other."""
        base = Path(tempfile.mkdtemp(prefix="vpa-bashless-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        (base / "agents").mkdir()
        (base / "agents" / "quiet.md").write_text(
            "---\nname: quiet\ndescription: x\ndisallowedTools: Bash\n---\n"
            "```bash\nplutil -p Info.plist\n```\n",
            encoding="utf-8",
        )
        problems: "list[str]" = []
        vpa.check_bashless_agents_run_no_shell(base, problems)
        self.assertTrue(any("quiet" in p and "plutil" in p for p in problems),
                        f"a deny-based bashless agent's shell recipe must be flagged: {problems}")

        (base / "agents" / "quiet.md").write_text(
            "---\nname: quiet\ndescription: x\ndisallowedTools: Bash\n---\n"
            "```bash\ngrep -rn pattern Sources/\n```\n",
            encoding="utf-8",
        )
        problems = []
        vpa.check_bashless_agents_run_no_shell(base, problems)
        self.assertEqual([], problems, "grep alone is native to Grep and stays exempt")


if __name__ == "__main__":
    unittest.main()


class EveryYamlListSpellingReachesTheSameVerdict(unittest.TestCase):
    """One list, thirteen spellings, one answer (PR #63 recheck, P1).

    Every consumer of a list-valued frontmatter key compares EXACT TOKENS —
    `check_model_reachable_grants` tests `entry in BROAD_MODEL_REACHABLE_GRANTS`, `_tool_tokens` builds
    a set — so any spelling the parser failed to normalize produced tokens that matched nothing, and the
    grant sailed through. Three families were live at once:

      * `[Bash]` kept its brackets, so the tokens were `[Bash` (or `[Read` and `Bash]`).
      * `- Bash` kept its marker, so the token was `- Bash`.
      * `["Bash"]` / `- "Bash"` kept their quotes, so the token was `"Bash"`.

    All are the same YAML value. The first two were fixed one at a time as each was found; this cell
    exists because fixing them individually is what let the third survive — the property is that the
    SPELLING cannot change the verdict, so it is asserted over the whole matrix rather than per form.
    """

    #: Every legal way to write the one-item list `[Bash]` and the two-item list `[Read, Bash]`.
    ONE = (
        "allowed-tools: Bash",
        "allowed-tools: [Bash]",
        'allowed-tools: ["Bash"]',
        "allowed-tools: ['Bash']",
        "allowed-tools:\n  - Bash",
        "allowed-tools:\n- Bash",
        'allowed-tools:\n  - "Bash"',
        "allowed-tools:\n  - 'Bash'",
        "allowed-tools: [Bash] # inline note",
    )
    #: A YAML COMMENT IS NOT THE COLLECTION (PR #63 recheck, P1). The multi-line fold decided the list
    #: was complete with a raw `"]" in line` search, so a `]` inside a comment on the OPENING line
    #: ended it early: `parse_frontmatter` recorded `[ Bash`, the bare-grant deny-list matched nothing,
    #: and Claude's own parser granted unrestricted shell. Stripping the comment only after joining is
    #: not enough either — that discards every item past the first comment and loses the grant entirely,
    #: which is the same bypass one step along. Each folded line is stripped as it is folded.
    COMMENTED = (
        "allowed-tools: [ # tool list ]\n  Bash\n]",
        "allowed-tools: [\n  Bash # keep ] this\n]",
        "allowed-tools: [\n  # just a note\n  Bash,\n]",
    )
    TWO = (
        "allowed-tools: Read, Bash",
        "allowed-tools: [Read, Bash]",
        'allowed-tools: [Read, "Bash"]',
        "allowed-tools: [\n  Read,\n  Bash,\n]",
        "allowed-tools: [Read,\n  Bash]",
        "allowed-tools:\n  - Read\n  - Bash",
        "allowed-tools:\n- Read\n- Bash",
    )

    @staticmethod
    def _grant_problems(spelling: str) -> "list[str]":
        text = f"---\nname: probe\ndescription: a probe skill\n{spelling}\n---\nbody\n"
        fm = vpa.parse_frontmatter(text)
        if fm is None:
            return [f"frontmatter did not parse: {spelling!r}"]
        problems: list[str] = []
        vpa.check_model_reachable_grants(Path("skills/probe/SKILL.md"), fm, problems, [])
        return problems

    def test_bare_Bash_is_refused_in_every_spelling(self):
        for spelling in self.ONE + self.TWO + self.COMMENTED:
            with self.subTest(spelling=spelling):
                problems = self._grant_problems(spelling)
                self.assertTrue(problems,
                                f"a model-invocable skill granting bare Bash passed as {spelling!r}")
                self.assertTrue(any("`Bash`" in problem for problem in problems),
                                f"the refusal names something other than Bash: {problems}")

    def test_a_hash_inside_quotes_is_not_a_comment(self):
        """Discrimination: the comment rule must not eat a `#` that belongs to the value."""
        fm = vpa.parse_frontmatter(
            '---\nname: p\ndescription: d\nallowed-tools: ["Bash(printf a#b)"]\n---\nb\n')
        self.assertEqual("Bash(printf a#b)", fm["allowed-tools"])
        problems: list[str] = []
        vpa.check_model_reachable_grants(Path("skills/p/SKILL.md"), fm, problems, [])
        self.assertEqual([], problems, "a scoped grant containing `#` was refused")

    def test_the_tokens_are_identical_in_every_spelling(self):
        """The verdict is downstream of the tokens; assert the tokens themselves so a future consumer
        inherits the normalization instead of re-deriving it."""
        for spelling in self.ONE + self.COMMENTED:
            with self.subTest(spelling=spelling):
                fm = vpa.parse_frontmatter(
                    f"---\nname: probe\ndescription: d\n{spelling}\n---\nbody\n")
                self.assertEqual({"Bash"}, vpa._tool_tokens(fm["allowed-tools"]))
        for spelling in self.TWO:
            with self.subTest(spelling=spelling):
                fm = vpa.parse_frontmatter(
                    f"---\nname: probe\ndescription: d\n{spelling}\n---\nbody\n")
                self.assertEqual({"Read", "Bash"}, vpa._tool_tokens(fm["allowed-tools"]))

    def test_a_SCOPED_grant_is_accepted_in_every_spelling(self):
        """Discrimination: normalization must not turn every spelling into a refusal.

        `Write(docs/planning/**)` is bounded and is what the shipped `brainstorm` skill actually grants.
        It also proves the flow-list split respects parentheses: splitting
        `[Write(docs/planning/**), Read]` naively on commas is fine here, but the ENTRY-level split the
        checker uses must keep a parenthesised argument containing a comma whole, so the scoped
        `Agent(...)` form below is included as the case that would break under a naive split.
        """
        for spelling in (
            "allowed-tools: Write(docs/planning/**), Read",
            "allowed-tools: [Write(docs/planning/**), Read]",
            "allowed-tools:\n  - Write(docs/planning/**)\n  - Read",
            "allowed-tools:\n- 'Write(docs/planning/**)'\n- Read",
            "allowed-tools: [Agent(unleashed-mail:jira-manager), Read]",
            "allowed-tools:\n  - Agent(unleashed-mail:jira-manager)\n  - Read",
        ):
            with self.subTest(spelling=spelling):
                self.assertEqual([], self._grant_problems(spelling),
                                 f"a scoped Bash grant was refused as {spelling!r}")

    def test_a_bracket_inside_a_QUOTED_scalar_is_not_treated_as_a_list(self):
        """The multi-line fold triggers on a value that OPENS with `[`; a quoted one does not.

        Without this a description like `"see [1] for details"` would start a fold and swallow the
        frontmatter terminator — turning a valid asset into `missing or unterminated frontmatter`.
        """
        fm = vpa.parse_frontmatter(
            '---\nname: probe\ndescription: "see [1] for details"\nallowed-tools: Read\n---\nbody\n')
        self.assertIsNotNone(fm)
        self.assertEqual("see [1] for details", fm["description"])
        self.assertEqual("Read", fm["allowed-tools"])

    def test_an_UNTERMINATED_flow_list_fails_closed(self):
        """A list that never closes is malformed YAML, and Claude Code would not read it as a list
        either. Reporting no usable frontmatter is the fail-closed answer; silently recording
        `[Read, Bash` would hand every consumer two tokens that match nothing — the bug itself."""
        self.assertIsNone(vpa.parse_frontmatter(
            "---\nname: probe\ndescription: d\nallowed-tools: [Read,\n  Bash\n---\nbody\n"))


class GrepPipelinesAreNotNativeGrep(unittest.TestCase):
    """The bashless-agent exemption keyed on the FIRST WORD (PR #63 recheck, P2).

    `grep … | grep -v …`, `grep … | wc -l` and `grep … || echo …` all start with `grep`, so the check
    that exists to catch "documents a command only a shell could run" waved them through. The `Grep`
    tool takes a path, not stdin, and has no `||` — so those audit sections produced NOTHING while the
    reviewer reported a complete review, which is the exact failure the check was written for,
    surviving inside its own exemption. Four shipped agents carried fifteen such recipes.

    Quoting is what makes this checkable rather than a blanket ban: `grep -rn "A\\|B" path` contains a
    `|`, but inside a quoted regex it is ALTERNATION, which `Grep` does natively. A substring scan
    would have rejected dozens of legitimate recipes and the check would have been switched off.
    """

    def test_an_unquoted_operator_is_found_and_a_quoted_one_is_not(self):
        cases = {
            'grep -rn "A" path | grep -v "B"': ["|"],
            'grep -rn "A" path | wc -l': ["|"],
            'grep -A5 "A" f 2>/dev/null || echo "none"': ["||"],
            'grep -rn "A" path && echo done': ["&&"],
            'grep -rn "A" path; echo done': [";"],
            'grep -rn "$(cat p)" path': ["$("],
            'grep -rn "`cat p`" path': ["`", "`"],  # double quotes do NOT disable substitution
            'grep -rn "Button\\|Toggle" path': [],  # alternation inside a quoted regex
            "grep -rn 'A\\|B' --include='*.swift' path": [],
            'grep -rn "A" path 2>/dev/null': [],    # a redirect is not an operator Grep must express
            # A TRAILING COMMENT ENDS THE LINE. Found by cross-checking this function against `shlex`
            # over the 398 fenced command lines this repo ships: every disagreement that was MINE had
            # an operator sitting inside a comment. Flagging those refuses a recipe for what its
            # comment says, which is a false refusal.
            'grep -rn "A" path   # then filter | by hand': [],
            'set -o pipefail   # without it, `| tail` returns 0': [],
            'grep -rn "A" path | grep -v B   # a real pipeline, commented': ["|"],
            'grep -rn "A#B" path': [],              # `#` inside quotes is not a comment
            'grep -rn "A" path#notacomment': [],    # nor is one without preceding whitespace
            # Process substitution is NOT a redirect: nothing but a shell can produce it.
            'grep -rn "A" < <(cat p)': ["<("],
        }
        for line, expected in cases.items():
            with self.subTest(line=line):
                self.assertEqual(expected, vpa._unquoted_shell_operators(line))

    def test_the_shipped_bashless_agents_document_no_pipelines(self):
        """The tree itself, not a fixture: every recipe in a bashless agent must be runnable."""
        problems: list[str] = []
        vpa.check_bashless_agents_run_no_shell(Path(_ROOT), problems)
        self.assertEqual([], problems)
