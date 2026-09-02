#!/usr/bin/env python3
"""COREDEV-2780 cell 13 and COREDEV-2801 cell 8's pre-commit half.

Cell 13's `--index`/`--no-fix`/timeout/aggregation controls arrive with M5a, which wires the trunk
check itself. What is asserted here now is the surface M6 shipped: the drift detector's OTHER caller,
and the exit-code aggregation that a later advisory command must not be able to mask.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
import time
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
            (root / "scripts/detect-plugin-version-drift.sh").write_bytes(
                DETECTOR.read_bytes()
            )
            (root / "scripts/detect-plugin-version-drift.sh").chmod(0o755)
            subprocess.run(
                ["git", "-C", str(root), "init", "-q", "."],
                check=True,
                capture_output=True,
            )
            # PATH DELIBERATELY EXCLUDES a real `trunk`. These cases are about the hook's exit-code
            # aggregation, and letting the ambient PATH supply a real trunk would make them depend on
            # this repository's live lint state rather than on the property under test.
            return subprocess.run(
                ["bash", str(root / ".githooks/pre-commit")],
                check=False,
                cwd=str(root),
                capture_output=True,
                text=True,
                env={"PATH": "/usr/bin:/bin", "HOME": tmp},
            )

    def test_an_earlier_failure_survives_the_later_advisory_command(self):
        completed = self._run_with_checks('#!/bin/bash\necho "checks failed"\nexit 3\n')
        self.assertEqual(3, completed.returncode)

    def test_a_clean_run_still_exits_zero(self):
        completed = self._run_with_checks("#!/bin/bash\nexit 0\n")
        self.assertEqual(0, completed.returncode)

    def test_the_detector_cannot_block_a_commit(self):
        """ADVISORY. A stale install is a thing to know about, not a reason to refuse a commit — and a
        detector that can block is one people disable."""
        completed = self._run_with_checks("#!/bin/bash\nexit 0\n")
        self.assertEqual(0, completed.returncode)
        self.assertNotIn("detect-plugin-version-drift", completed.stderr)


class TheDetectorsSecondCaller(unittest.TestCase):
    def setUp(self):
        self.hook = HOOK.read_text(encoding="utf-8")

    def test_the_root_is_derived_from_the_worktree_not_inherited(self):
        """git runs the hook FROM the worktree, so `--show-toplevel` is correct — while
        CLAUDE_PROJECT_DIR may be unset, empty, or left over from a DIFFERENT project.
        """
        self.assertIn("--show-toplevel", self.hook)
        # Assert the PROPERTY (the variable is never USED), not the spelling (the string never
        # appears) — it appears in the comment that explains why it is not used, and a check keyed on
        # a spelling is not a check on the property.
        executable = [
            line
            for line in self.hook.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            [], [line for line in executable if "CLAUDE_PROJECT_DIR" in line]
        )

    def test_the_detector_is_invoked_without_the_session_start_protocol(self):
        """The marker/dedup dance belongs to SessionStart; a commit is not a session."""
        call = [
            line
            for line in self.hook.splitlines()
            if "detect-plugin-version-drift.sh" in line
            and line.strip().startswith("bash")
        ]
        self.assertEqual(1, len(call))
        self.assertNotIn("--session-start", call[0])

    def test_it_is_guarded_on_the_script_being_executable(self):
        """A checkout without the script — an older branch — must not break every commit."""
        # Asserted as a PROPERTY, not a byte spelling: `trunk fmt` rewrites `$VAR` to `${VAR}` and
        # retabs the file, so an exact-bytes anchor silently stops matching after any reformat — the
        # documented way this repository's shell assertions go quietly dead.
        guard = [
            line
            for line in self.hook.splitlines()
            if "detect-plugin-version-drift.sh" in line
            and line.lstrip().startswith("if")
        ]
        self.assertEqual(1, len(guard), "exactly one guard around the detector call")
        self.assertIn(
            "-x", guard[0], "the guard must test EXECUTABILITY, not mere existence"
        )


class TheDetectorHandlesTheHostileRootCases(unittest.TestCase):
    """The three cases that made `git -C \"${CLAUDE_PROJECT_DIR}\"` wrong for this surface."""

    def _run(self, root_arg, home):
        return subprocess.run(
            ["bash", str(DETECTOR), root_arg],
            check=False,
            capture_output=True,
            text=True,
            env={"PATH": os.environ["PATH"], "HOME": home},
        )

    def test_unset_empty_and_foreign_roots_are_all_silent_rather_than_wrong(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / ".claude/plugins").mkdir(parents=True)
            (Path(home) / ".claude/plugins/installed_plugins.json").write_text(
                json.dumps({"user": {"unleashed-mail": {"version": "0.0.1"}}}),
                encoding="utf-8",
            )
            for label, root_arg in (
                ("empty", ""),
                ("non-repository", "/"),
                ("missing directory", "/nonexistent-xyz"),
            ):
                with self.subTest(root=label):
                    completed = self._run(root_arg, home)
                    self.assertEqual(0, completed.returncode)
                    self.assertEqual("", completed.stdout.strip())


MEASUREMENT = REPO / "docs/planning/evidence/COREDEV-2780-m5a-timeout-measurement.json"


class Cell13_TheLocalTrunkGate(unittest.TestCase):
    """COREDEV-2780 M5a. Exercised against a FAKE `trunk` on PATH, because the controls are about what
    the hook DOES with the tool — the arguments it passes, whether it blocks, whether it is bounded —
    and a real 30-second cold bootstrap would make the suite measure the network instead.
    """

    # `exec` matters: a real hanging `trunk` IS the direct child the watchdog kills. A fake that
    # spawns `sleep` as a GRANDCHILD leaves it orphaned after the kill, still holding the captured
    # stdout pipe — so the harness measures the orphan rather than the hook, and the watchdog looks
    # broken when it worked.
    FAKE = (
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$TRUNK_ARGV_LOG"\n'
        '[ -n "$TRUNK_SLEEP" ] && exec sleep "$TRUNK_SLEEP"\n'
        'exit "${TRUNK_EXIT:-0}"\n'
    )

    def _run(self, *, trunk_exit=0, trunk_sleep=None, checks_exit=0, with_trunk=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        (root / "scripts").mkdir()
        (root / ".githooks").mkdir()
        (root / "bin").mkdir()
        (root / ".githooks/pre-commit").write_bytes(HOOK.read_bytes())
        (root / ".githooks/pre-commit").chmod(0o755)
        (root / "scripts/pre-commit-checks.sh").write_text(
            f"#!/bin/bash\nexit {checks_exit}\n", encoding="utf-8"
        )
        (root / "scripts/detect-plugin-version-drift.sh").write_bytes(
            DETECTOR.read_bytes()
        )
        (root / "scripts/detect-plugin-version-drift.sh").chmod(0o755)
        argv_log = root / "argv.log"
        argv_log.write_text("", encoding="utf-8")
        if with_trunk:
            fake = root / "bin/trunk"
            fake.write_text(self.FAKE, encoding="utf-8")
            fake.chmod(0o755)
        subprocess.run(
            ["git", "-C", str(root), "init", "-q", "."], check=True, capture_output=True
        )
        env = {
            "PATH": f"{root / 'bin'}:/usr/bin:/bin",
            "HOME": str(root),
            "TRUNK_ARGV_LOG": str(argv_log),
            "TRUNK_EXIT": str(trunk_exit),
        }
        if trunk_sleep is not None:
            env["TRUNK_SLEEP"] = str(trunk_sleep)
        completed = subprocess.run(
            ["bash", str(root / ".githooks/pre-commit")],
            check=False,
            cwd=str(root),
            capture_output=True,
            text=True,
            env=env,
        )
        return completed, argv_log.read_text(encoding="utf-8")

    # ---- what it passes -------------------------------------------------------------------------
    def test_it_checks_the_index_and_never_the_whole_tree(self):
        """The commit is made from the INDEX. Checking the worktree lets a finding that is clean in
        the index but dirty in the worktree fail the commit, and vice versa."""
        _, argv = self._run()
        self.assertIn("--index", argv)
        self.assertNotIn("--all", argv)

    def test_it_passes_no_fix_so_the_hook_never_rewrites_files(self):
        _, argv = self._run()
        self.assertIn("--no-fix", argv)

    def test_it_passes_the_declared_exclusion_literal(self):
        """§6.4's literal is required on BOTH surfaces. A literal required in two places and checked
        in one is a declaration, not a control."""
        _, argv = self._run()
        self.assertIn("--filter=-markdown-link-check", argv)

    # ---- whether it blocks ----------------------------------------------------------------------
    def test_a_finding_in_the_staged_diff_blocks_the_commit(self):
        completed, _ = self._run(trunk_exit=1)
        self.assertEqual(1, completed.returncode)
        self.assertIn("new findings", completed.stdout)

    def test_a_clean_staged_diff_commits_with_the_backlog_present(self):
        """The 9027-issue backlog must not block every commit — that is the `--all` trap."""
        completed, _ = self._run(trunk_exit=0)
        self.assertEqual(0, completed.returncode)

    def test_a_missing_trunk_binary_does_not_block(self):
        """A developer without trunk installed still gets every other check."""
        completed, _ = self._run(with_trunk=False)
        self.assertEqual(0, completed.returncode)

    # ---- whether it is bounded -------------------------------------------------------------------
    def test_the_timeout_constant_is_the_recorded_measured_literal(self):
        """Asserted as an OPERAND against the measurement that justifies it — revision 23's 120 was
        not a wrong number, it was an unjustified one."""
        measurement = json.loads(MEASUREMENT.read_text(encoding="utf-8"))
        constant = measurement["constantSeconds"]
        self.assertIn(
            f"TRUNK_TIMEOUT_SECONDS={constant}", HOOK.read_text(encoding="utf-8")
        )
        self.assertGreater(
            constant,
            measurement["envelopeSeconds"],
            "the constant must exceed the measured envelope",
        )
        self.assertGreaterEqual(
            constant / measurement["envelopeSeconds"],
            3,
            "headroom for slower hardware is not optional",
        )

    def test_a_hanging_trunk_is_bounded_and_does_not_block(self):
        """Exercised against a SLEEPING fake trunk. A timeout is infrastructure, not a finding —
        blocking on someone's slow network teaches people to pass --no-verify, which disables every
        other check too."""
        hook = HOOK.read_text(encoding="utf-8").replace(
            "TRUNK_TIMEOUT_SECONDS=180", "TRUNK_TIMEOUT_SECONDS=2"
        )
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        for sub in ("scripts", ".githooks", "bin"):
            (root / sub).mkdir()
        (root / ".githooks/pre-commit").write_text(hook, encoding="utf-8")
        (root / ".githooks/pre-commit").chmod(0o755)
        (root / "scripts/pre-commit-checks.sh").write_text(
            "#!/bin/bash\nexit 0\n", encoding="utf-8"
        )
        fake = root / "bin/trunk"
        fake.write_text(self.FAKE, encoding="utf-8")
        fake.chmod(0o755)
        subprocess.run(
            ["git", "-C", str(root), "init", "-q", "."], check=True, capture_output=True
        )
        started = time.time()
        completed = subprocess.run(
            ["bash", str(root / ".githooks/pre-commit")],
            check=False,
            cwd=str(root),
            capture_output=True,
            text=True,
            env={
                "PATH": f"{root / 'bin'}:/usr/bin:/bin",
                "HOME": str(root),
                "TRUNK_ARGV_LOG": str(root / "argv.log"),
                "TRUNK_SLEEP": "30",
            },
        )
        elapsed = time.time() - started
        self.assertLess(elapsed, 20, "the watchdog must actually fire")
        self.assertEqual(0, completed.returncode, "a timeout must not block the commit")
        self.assertIn("exceeded", completed.stdout)

    def test_the_clean_slow_path_completes_without_tripping_the_timeout(self):
        """Cell 13's discriminating pair for the constant: a run comfortably inside the envelope must
        NOT be killed. A constant fitted tightly to one machine fails this on a slower one.
        """
        completed, _ = self._run(trunk_exit=0, trunk_sleep=1)
        self.assertEqual(0, completed.returncode)
        self.assertNotIn("exceeded", completed.stdout)

    def test_the_timeout_is_macos_portable(self):
        """Stock macOS ships NEITHER `timeout` NOR `gtimeout`; they arrive with homebrew coreutils. A
        hook that assumes them is broken on a clean Mac, which is most of the machines it runs on.
        """
        hook = HOOK.read_text(encoding="utf-8")
        self.assertIn("command -v timeout", hook)
        self.assertIn("command -v gtimeout", hook)
        self.assertIn("kill -TERM", hook, "there must be a fallback that needs neither")

    # ---- aggregation, with the trunk check in the chain -------------------------------------------
    def test_an_earlier_failure_is_not_masked_by_a_passing_trunk_check(self):
        """The specific shape cell 13 names: append a passing command after a failing one and the
        nonzero result disappears."""
        completed, _ = self._run(checks_exit=3, trunk_exit=0)
        self.assertEqual(3, completed.returncode)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
