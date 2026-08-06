"""COREDEV-2503 F10 (model-id regex end anchor) + B4 (stale-tool hard reject) for
`scripts/validate-plugin-assembly.py::check_agent_fields`. The module has a hyphen in its name, so it is
loaded via importlib rather than imported."""
import importlib.util
import os
import unittest
from pathlib import Path

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

    def test_a_newly_added_writer_agent_is_caught(self):
        """The discrimination that matters: this is how a deny-list normally re-opens.

        Asserting only on the current contents would pass forever while the tree grew a thirteenth
        writer nobody added to the list.
        """
        import shutil
        import tempfile

        root = Path(tempfile.mkdtemp(prefix="spawner-drift-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "agents").mkdir()
        shutil.copy2(Path(_MOD_PATH).resolve().parents[1] / "agents" / "swift-reviewer.md",
                     root / "agents" / "swift-reviewer.md")
        (root / "agents" / "rogue-writer.md").write_text(
            "---\nname: rogue-writer\ndescription: x\ntools: Read, Write, Edit, Bash\n---\nbody\n",
            encoding="utf-8",
        )
        problems = self._run(root)
        self.assertTrue(problems, "a new writer agent must be caught")
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


if __name__ == "__main__":
    unittest.main()
