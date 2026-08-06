#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-PRECLEAN source-proof cells."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REVIEW = "review"
CODEX_SKILL = "skills/" + "codex-" + REVIEW + "/SKILL.md"
GEMINI_SKILL = "skills/" + "gemini-" + REVIEW + "/SKILL.md"
ISOLATED_HELPER = "scripts/review/" + "isolated-agy-" + REVIEW + ".sh"

ALLOWED_TOOLS = "allowed" + "-tools"
PLUGIN_ROOT_NAME = "CLAUDE_PLUGIN_" + "ROOT"
PLUGIN_ROOT_TOKEN = "${" + PLUGIN_ROOT_NAME + "}"
TMP_ROOT = "/" + "tmp"

CODEX_PRECLEAN = (
    "rm -f "
    + TMP_ROOT
    + "/codex-out.txt "
    + TMP_ROOT
    + "/codex-out.txt.captureid"
)
GEMINI_PRECLEAN = 'rm -f "$OUT" "$OUT.captureid"'
PRECLEAN_COMMANDS = {
    CODEX_SKILL: CODEX_PRECLEAN,
    ISOLATED_HELPER: GEMINI_PRECLEAN,
}

# M2.6/M2.7's property is that each review skill GRANTS the plugin-root scripts it invokes, so the
# pre-clean removal cannot leave a capture ungranted. It was pinned to the DIRECTORY WILDCARDS
# (`/scripts/*`, `/scripts/review/*`), which satisfied that property by covering everything — including
# the destructive cleanup tool with `--apply` and `pty-capture.py <any path> -- <any command>`
# (deep review, P1). The wildcards are gone; the property is now pinned to the exact entrypoints, which
# is what it always meant.
CAPTURE_CODEX_GRANT = "Bash(bash " + PLUGIN_ROOT_TOKEN + "/scripts/review/capture-codex-review.sh *)"
AUDIT_CODEX_GRANT = "Bash(bash " + PLUGIN_ROOT_TOKEN + "/scripts/review/audit-codex.sh *)"
CAPTURE_GEMINI_GRANT = "Bash(bash " + PLUGIN_ROOT_TOKEN + "/scripts/review/capture-gemini-review.sh *)"
PREFLIGHT_AGY_GRANT = "Bash(bash " + PLUGIN_ROOT_TOKEN + "/scripts/review/preflight-agy.sh)"
REQUIRED_GRANTS = {
    CODEX_SKILL: (CAPTURE_CODEX_GRANT, AUDIT_CODEX_GRANT),
    GEMINI_SKILL: (CAPTURE_GEMINI_GRANT, PREFLIGHT_AGY_GRANT),
}

RM_GRANT = re.compile(r"Bash\([ \t]*rm[ \t]+-f(?:[ \t]+|(?=\)))")
VALIDATOR_SOURCE_SUFFIXES = {".py", ".sh"}


def _tracked_text_tree() -> dict[str, str]:
    completed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    tree = {}
    for raw_path in completed.stdout.rstrip(b"\0").split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        path = REPO / relative
        if not path.is_file():
            continue
        try:
            tree[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return tree


def _allowed_tool_lines(tree: dict[str, str]) -> list[tuple[str, int, str]]:
    prefix = ALLOWED_TOOLS + ":"
    return [
        (path, line_number, line)
        for path, text in tree.items()
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.lstrip().startswith(prefix)
    ]


def _allowed_tool_entries(line: str) -> set[str]:
    _key, value = line.split(":", 1)
    return {entry.strip() for entry in value.split(",")}


def _replace_line(
    tree: dict[str, str],
    path: str,
    line_number: int,
    replacement: str,
) -> dict[str, str]:
    mutated = dict(tree)
    lines = mutated[path].splitlines()
    lines[line_number - 1] = replacement
    mutated[path] = "\n".join(lines) + "\n"
    return mutated


def _tmp_allowed_tool_hits(tree: dict[str, str]) -> list[tuple[str, int]]:
    return [
        (path, line_number)
        for path, line_number, line in _allowed_tool_lines(tree)
        if TMP_ROOT in line
    ]


def _rm_grant_hits(tree: dict[str, str]) -> list[tuple[str, int]]:
    targets = {CODEX_SKILL, GEMINI_SKILL}
    return [
        (path, line_number)
        for path, line_number, line in _allowed_tool_lines(tree)
        if path in targets and RM_GRANT.search(line)
    ]


def _missing_required_grants(tree: dict[str, str]) -> list[tuple[str, str]]:
    allowed_by_path = {}
    for path, _line_number, line in _allowed_tool_lines(tree):
        if path in REQUIRED_GRANTS:
            allowed_by_path.setdefault(path, set()).update(_allowed_tool_entries(line))
    return [
        (path, grant)
        for path, grants in REQUIRED_GRANTS.items()
        for grant in grants
        if grant not in allowed_by_path.get(path, set())
    ]


def _preclean_command_hits(tree: dict[str, str]) -> list[tuple[str, int]]:
    hits = []
    for path, command in PRECLEAN_COMMANDS.items():
        for line_number, line in enumerate(tree.get(path, "").splitlines(), start=1):
            if line.strip() == command:
                hits.append((path, line_number))
    return hits


def _direct_validator_lexeme_hits(tree: dict[str, str]) -> list[tuple[str, int]]:
    """Find only direct same-line validator spellings; semantic absence remains manual."""
    hits = []
    for path, text in tree.items():
        source_path = Path(path)
        if not path.startswith("scripts/") or source_path.suffix not in VALIDATOR_SOURCE_SUFFIXES:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if ALLOWED_TOOLS in line and PLUGIN_ROOT_TOKEN in line:
                hits.append((path, line_number))
    return hits


class SPrecleanProofs(unittest.TestCase):
    """Source assertions plus mutations that exercise each assertion's boundary."""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = _tracked_text_tree()
        test_path = Path(__file__).resolve()
        cls.tree[str(test_path.relative_to(REPO))] = test_path.read_text(encoding="utf-8")

    def test_M2_3_no_tmp_literal_survives_in_any_allowed_tools_line(self) -> None:
        self.assertEqual([], _tmp_allowed_tool_hits(self.tree))

    def test_M2_3_every_allowed_tools_line_rejects_a_tmp_mutation(self) -> None:
        allowed_lines = _allowed_tool_lines(self.tree)
        self.assertGreater(len(allowed_lines), 0)
        tmp_grant = ", Bash(command " + TMP_ROOT + "/preclean-proof)"

        for path, line_number, line in allowed_lines:
            with self.subTest(path=path, line=line_number):
                mutated = _replace_line(self.tree, path, line_number, line + tmp_grant)
                self.assertIn((path, line_number), _tmp_allowed_tool_hits(mutated))

    def test_M2_16_rm_grants_are_deleted_at_both_review_skills(self) -> None:
        self.assertEqual([], _rm_grant_hits(self.tree))

    def test_M2_16_non_tmp_rm_grant_rewrites_are_rejected_independently(self) -> None:
        allowed_by_path = {
            path: (line_number, line)
            for path, line_number, line in _allowed_tool_lines(self.tree)
            if path in (CODEX_SKILL, GEMINI_SKILL)
        }
        self.assertEqual({CODEX_SKILL, GEMINI_SKILL}, set(allowed_by_path))

        rewritten_grant = ", Bash(rm -f /var/state/unleashed-transcript*)"
        for path, (line_number, line) in allowed_by_path.items():
            with self.subTest(path=path):
                mutated = _replace_line(self.tree, path, line_number, line + rewritten_grant)
                self.assertEqual([], _tmp_allowed_tool_hits(mutated))
                self.assertIn((path, line_number), _rm_grant_hits(mutated))

    def test_M2_8_preclean_commands_are_absent_from_the_source_files(self) -> None:
        self.assertEqual([], _preclean_command_hits(self.tree))

    def test_M2_8_each_preclean_command_reintroduction_is_detected_in_its_file(self) -> None:
        for path, command in PRECLEAN_COMMANDS.items():
            with self.subTest(path=path):
                mutated = dict(self.tree)
                mutated[path] = mutated[path].rstrip("\n") + "\n" + command + "\n"
                hits = _preclean_command_hits(mutated)
                self.assertIn((path, len(mutated[path].splitlines())), hits)

    def test_M2_6_and_M2_7_required_plugin_root_grants_remain_exact(self) -> None:
        self.assertEqual([], _missing_required_grants(self.tree))

    def test_M2_6_and_M2_7_each_required_grant_rewrite_is_rejected(self) -> None:
        allowed_by_path = {
            path: (line_number, line)
            for path, line_number, line in _allowed_tool_lines(self.tree)
            if path in REQUIRED_GRANTS
        }
        for path, grants in REQUIRED_GRANTS.items():
            line_number, line = allowed_by_path[path]
            for grant in grants:
                with self.subTest(path=path, grant=grant):
                    rewritten = grant.replace(PLUGIN_ROOT_TOKEN, "/opt/plugin")
                    mutated = _replace_line(
                        self.tree,
                        path,
                        line_number,
                        line.replace(grant, rewritten, 1),
                    )
                    self.assertIn((path, grant), _missing_required_grants(mutated))

    def test_bounded_direct_validator_lexeme_scan_is_clean(self) -> None:
        """This cell intentionally makes no semantic no-validator claim."""
        self.assertEqual([], _direct_validator_lexeme_hits(self.tree))

    def test_bounded_direct_validator_lexeme_scan_rejects_its_named_form(self) -> None:
        """A multiline, generic, or computed validator remains a manual inspection gap."""
        path = "scripts/validate-plugin-assembly.py"
        direct_validator = (
            '\nif key == "'
            + ALLOWED_TOOLS
            + '" and "'
            + PLUGIN_ROOT_TOKEN
            + '" in value:\n    problems.append("unsupported placeholder")\n'
        )
        mutated = dict(self.tree)
        mutated[path] += direct_validator

        self.assertIn(
            (path, len(mutated[path].splitlines()) - 1),
            _direct_validator_lexeme_hits(mutated),
        )


if __name__ == "__main__":
    unittest.main()
