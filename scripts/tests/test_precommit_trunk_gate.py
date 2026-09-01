#!/usr/bin/env python3
"""COREDEV-2780 cell 13 and COREDEV-2801 cell 8's pre-commit half.

Cell 13's `--index`/`--no-fix`/timeout/aggregation controls arrive with M5a, which wires the trunk
check itself. What is asserted here now is the surface M6 shipped: the drift detector's OTHER caller,
and the exit-code aggregation that a later advisory command must not be able to mask.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / ".githooks/pre-commit"
DETECTOR = REPO / "scripts/detect-plugin-version-drift.sh"


class TheHookAggregatesItsExitCode(unittest.TestCase):
    """Appending any passing command after the checks would otherwise mask a nonzero result. A hook
    that swallows a prior failure is worse than no hook."""

    def _run_with_checks(self, script: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / ".githooks").mkdir()
            (root / ".githooks/pre-commit").write_bytes(HOOK.read_bytes())
            (root / ".githooks/pre-commit").chmod(0o755)
            (root / "scripts/pre-commit-checks.sh").write_text(script, encoding="utf-8")
            (root / "scripts/detect-plugin-version-drift.sh").write_bytes(DETECTOR.read_bytes())
            (root / "scripts/detect-plugin-version-drift.sh").chmod(0o755)
            subprocess.run(["git", "-C", str(root), "init", "-q", "."], check=True, capture_output=True)
            return subprocess.run(["bash", str(root / ".githooks/pre-commit")],
                                  cwd=str(root), capture_output=True, text=True,
                                  env={"PATH": os.environ["PATH"], "HOME": tmp})

    def test_an_earlier_failure_survives_the_later_advisory_command(self):
        completed = self._run_with_checks('#!/bin/bash\necho "checks failed"\nexit 3\n')
        self.assertEqual(3, completed.returncode)

    def test_a_clean_run_still_exits_zero(self):
        completed = self._run_with_checks('#!/bin/bash\nexit 0\n')
        self.assertEqual(0, completed.returncode)

    def test_the_detector_cannot_block_a_commit(self):
        """ADVISORY. A stale install is a thing to know about, not a reason to refuse a commit — and a
        detector that can block is one people disable."""
        completed = self._run_with_checks('#!/bin/bash\nexit 0\n')
        self.assertEqual(0, completed.returncode)
        self.assertNotIn("detect-plugin-version-drift", completed.stderr)


class TheDetectorsSecondCaller(unittest.TestCase):
    def setUp(self):
        self.hook = HOOK.read_text(encoding="utf-8")

    def test_the_root_is_derived_from_the_worktree_not_inherited(self):
        """git runs the hook FROM the worktree, so `--show-toplevel` is correct — while
        CLAUDE_PROJECT_DIR may be unset, empty, or left over from a DIFFERENT project."""
        self.assertIn("--show-toplevel", self.hook)
        # Assert the PROPERTY (the variable is never USED), not the spelling (the string never
        # appears) — it appears in the comment that explains why it is not used, and a check keyed on
        # a spelling is not a check on the property.
        executable = [line for line in self.hook.splitlines()
                      if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual([], [line for line in executable if "CLAUDE_PROJECT_DIR" in line])

    def test_the_detector_is_invoked_without_the_session_start_protocol(self):
        """The marker/dedup dance belongs to SessionStart; a commit is not a session."""
        call = [line for line in self.hook.splitlines() if "detect-plugin-version-drift.sh" in line
                and line.strip().startswith("bash")]
        self.assertEqual(1, len(call))
        self.assertNotIn("--session-start", call[0])

    def test_it_is_guarded_on_the_script_being_executable(self):
        """A checkout without the script — an older branch — must not break every commit."""
        self.assertIn("-x \"$SCRIPT_DIR/detect-plugin-version-drift.sh\"", self.hook)


class TheDetectorHandlesTheHostileRootCases(unittest.TestCase):
    """The three cases that made `git -C \"${CLAUDE_PROJECT_DIR}\"` wrong for this surface."""

    def _run(self, root_arg, home):
        return subprocess.run(["bash", str(DETECTOR), root_arg], capture_output=True, text=True,
                              env={"PATH": os.environ["PATH"], "HOME": home})

    def test_unset_empty_and_foreign_roots_are_all_silent_rather_than_wrong(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / ".claude/plugins").mkdir(parents=True)
            (Path(home) / ".claude/plugins/installed_plugins.json").write_text(
                json.dumps({"user": {"unleashed-mail": {"version": "0.0.1"}}}), encoding="utf-8")
            for label, root_arg in (("empty", ""), ("non-repository", "/"),
                                    ("missing directory", "/nonexistent-xyz")):
                with self.subTest(root=label):
                    completed = self._run(root_arg, home)
                    self.assertEqual(0, completed.returncode)
                    self.assertEqual("", completed.stdout.strip())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
