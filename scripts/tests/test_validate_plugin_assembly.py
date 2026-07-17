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
        p: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), {"model": model}, p)
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
        p: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), {"tools": tools}, p)
        return p

    def test_task_is_hard_rejected(self):
        # B4: `Task` is stale; the difflib guard finds no close match so it would slip through. An explicit
        # STALE_TOOLS reject is required (merely dropping it from KNOWN_TOOLS is a no-op).
        p = self._problems("Read, Task, Grep")
        self.assertTrue(any("stale" in x or "Agent" in x for x in p), f"`Task` must be rejected: {p}")

    def test_agent_is_accepted(self):
        self.assertEqual(self._problems("Read, Agent, Grep"), [], "`Agent` is the valid dispatcher tool")

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
        p: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), fm, p)
        self.assertTrue(any("stale" in x or "Agent" in x for x in p),
                        f"`Task` in a multi-line block list must be rejected: {p} (tools={fm.get('tools')!r})")

    def test_stale_task_with_inline_comment(self):
        # codex/gemini #53: a YAML inline comment on a block-list item must be stripped before the check
        md = "---\nname: x\ndescription: y\nmodel: inherit\ntools:\n  - Read\n  - Task # legacy\n---\nbody\n"
        fm = vpa.parse_frontmatter(md)
        p: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), fm, p)
        self.assertTrue(any("stale" in x or "Agent" in x for x in p),
                        f"`Task # legacy` must be rejected: {p} (tools={fm.get('tools')!r})")

    def test_multiline_block_list_clean_passes(self):
        md = "---\nname: x\ndescription: y\nmodel: inherit\ntools:\n  - Read\n  - Agent\n---\nbody\n"
        fm = vpa.parse_frontmatter(md)
        p: list[str] = []
        vpa.check_agent_fields(Path("agents/x.md"), fm, p)
        self.assertEqual(p, [], f"a clean multi-line block list must pass: {p}")


if __name__ == "__main__":
    unittest.main()
