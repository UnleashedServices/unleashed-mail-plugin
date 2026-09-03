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
import re
import shutil
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


class TheBoundedRun(unittest.TestCase):
    """COREDEV-2780 M5a / PR #84. `run_with_timeout` has three branches — `timeout`, `gtimeout`, and a
    hand-rolled watchdog — and EVERY case here runs against ALL OF THEM.

    The first version of this class did not. It sanitised `PATH` so only the no-coreutils fallback
    could ever be reached, and said so in its docstring as though that were the point. But the
    fallback is the branch that runs when neither tool is installed: not this repo's CI, which is
    `ubuntu-latest`, and not a Mac with homebrew coreutils. Every guarantee below was therefore
    proven for the branch that does not run, while the branch that does had no escalation at all and
    overran its deadline thirtyfold — measured at 60s against a 2s deadline. A reviewer found it.
    That is the same defect as the code it was testing: closing the member, not the family.

    So the branch is a PARAMETER. `bare` builds a PATH with no coreutils; `coreutils` puts the real
    tools on it and skips when the machine genuinely has none. The function is sliced out of
    `.githooks/pre-commit` and sourced, so these are the shipped bytes, not a copy.
    """

    NEEDED = ("sleep", "rm", "echo", "sh", "bash", "date", "cat")
    IGNORES_TERM = "trap '' TERM\nsleep 60\nexit 0\n"
    LEAKS_A_TERM_IGNORING_GRANDCHILD = (
        "bash -c 'trap \"\" TERM; sleep 40' &\necho started\nsleep 40\n"
    )

    @staticmethod
    def _coreutils_timeout():
        for name in ("timeout", "gtimeout"):
            found = shutil.which(name)
            if found:
                return found
        return None

    def _harness(self, script: str, seconds: int, *, branch: str):
        hook = HOOK.read_text(encoding="utf-8")
        head = hook.index("run_with_timeout() {")
        body = hook[head : hook.index("\n}\n", head) + 3]

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        (root / "bin").mkdir()
        for tool in self.NEEDED:
            for prefix in ("/bin", "/usr/bin"):
                if (pathlib.Path(prefix) / tool).exists():
                    (root / "bin" / tool).symlink_to(pathlib.Path(prefix) / tool)
                    break

        if branch == "coreutils":
            real = self._coreutils_timeout()
            if real is None:
                self.skipTest(
                    "no coreutils timeout on this machine to exercise that branch"
                )
            (root / "bin/timeout").symlink_to(real)
        else:
            self.assertIsNone(
                shutil.which("timeout", path=str(root / "bin")),
                "the bare branch must not offer coreutils, or it tests the wrong branch",
            )

        (root / "target.sh").write_text(script, encoding="utf-8")
        (root / "probe.sh").write_text(
            f"PATH={root / 'bin'}\nexport TMPDIR={root}\n{body}\n"
            f'run_with_timeout {seconds} bash "{root / "target.sh"}"\n'
            'echo "RC=$?"\n',
            encoding="utf-8",
        )
        started = time.monotonic()
        completed = subprocess.run(
            ["bash", str(root / "probe.sh")],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        elapsed = time.monotonic() - started
        rc = int(completed.stdout.rsplit("RC=", 1)[1].strip())
        return rc, elapsed, list(root.glob("rwt.*.deadline")), completed

    def _both_branches(self):
        return ("bare", "coreutils")

    def test_a_command_that_finishes_in_time_keeps_its_own_exit_status(self):
        """Pass-through must be EXACT on every branch: a lint finding is 1, and trunk's own
        could-not-run 2 must arrive at the caller as 2 so the caller can tell them apart.
        """
        for branch in self._both_branches():
            for expected in (0, 1, 2, 7):
                with self.subTest(branch=branch, exit=expected):
                    rc, elapsed, litter, _ = self._harness(
                        f"exit {expected}\n", seconds=10, branch=branch
                    )
                    self.assertEqual(expected, rc)
                    self.assertLess(
                        elapsed, 8, "a fast command must not wait for the deadline"
                    )
                    self.assertEqual(
                        [], litter, "no deadline marker may be left behind"
                    )

    def test_a_command_that_IGNORES_SIGTERM_and_then_exits_zero_is_reported_as_a_timeout(
        self,
    ):
        """The false CLEAN, on every branch. A TERM-only bound waits indefinitely on a process that
        traps the signal, and if that process later exits 0 the hook reports `no new findings` for a
        check that never finished — a green lint gate on an unlinted diff.

        Two separate properties: the status must be 124 and not the child's 0 (no amount of
        signalling fixes that, because a fast success and a killed-then-late process are
        indistinguishable by exit status), and the wait must be BOUNDED, which needs the escalation.
        On the coreutils branch this measured 60s before `-k 5` was passed.
        """
        for branch in self._both_branches():
            with self.subTest(branch=branch):
                rc, elapsed, litter, _ = self._harness(
                    self.IGNORES_TERM, seconds=2, branch=branch
                )
                self.assertEqual(
                    124,
                    rc,
                    "a run that blew the deadline must not report the child's 0",
                )
                self.assertLess(
                    elapsed,
                    30,
                    "SIGTERM alone never lands; the escalation must bound it",
                )
                self.assertEqual([], litter)

    def test_a_fast_run_leaves_no_ORPHANED_SLEEPER_behind(self):
        """The watchdog is a subshell BLOCKED IN `sleep`. Signalling the subshell alone orphans that
        `sleep` to PPID 1, where it runs out the full deadline — so every fast commit on a stock Mac
        left a `sleep 180` behind, and they accumulate (codex, PR #84).

        Counted as PROCESSES rather than read off the source: the property is that nothing outlives
        the run, not that a particular kill was written.
        """
        # THE DEADLINE ITSELF IS THE MARKER. A first draft put a marker in a `sleep` SHIM — but the
        # shim `exec`s, so the marker never reached the running process's argv and `pgrep` matched
        # nothing whether the fix was present or not. The mutation caught it: reverting the fix left
        # the test green. An unusual duration appears verbatim in the sleeper's own command line.
        deadline = 9173

        def alive() -> int:
            return len(
                subprocess.run(
                    ["pgrep", "-f", f"sleep {deadline}"],
                    check=False,
                    capture_output=True,
                    text=True,
                ).stdout.split()
            )

        before = alive()
        self.assertEqual(
            0, before, "the fixture duration must be unique on this machine"
        )
        rc, elapsed, _litter, _ = self._harness(
            "exit 0\n", seconds=deadline, branch="bare"
        )
        self.assertEqual(0, rc)
        self.assertLess(
            elapsed, 10, "the command itself must have returned immediately"
        )
        time.sleep(1.0)
        self.assertLessEqual(
            alive(), before, "the watchdog's sleeper outlived the run it was bounding"
        )

    def test_a_TERM_IGNORING_grandchild_does_not_hold_the_caller_open(self):
        """The direct child dies on TERM, so the wait returns and the pending SIGKILL is cancelled —
        and a grandchild that ignores TERM then outlives the deadline still holding the caller's
        stdout. Measured at 45s against a 2s deadline, on BOTH branches: `timeout -k` does not help,
        because its own child exited normally and the escalation never fired.

        This is why the teardown kill happens after the wait rather than being left to the watchdog.
        """
        for branch in self._both_branches():
            with self.subTest(branch=branch):
                rc, elapsed, _, _ = self._harness(
                    self.LEAKS_A_TERM_IGNORING_GRANDCHILD, seconds=2, branch=branch
                )
                self.assertEqual(124, rc)
                self.assertLess(
                    elapsed, 25, "a TERM-ignoring grandchild must not hold the caller"
                )

    def test_a_SIGTERM_that_beat_the_deadline_is_NOT_reported_as_a_timeout(self):
        """The same discriminator as 137, for the status `timeout` passes through untouched. A child
        that TERMs itself long before the deadline keeps its own 143 — calling that a timeout is the
        fail-open the caller's arm used to carry."""
        for branch in self._both_branches():
            with self.subTest(branch=branch):
                rc, elapsed, _, _ = self._harness(
                    "kill -TERM $$\nsleep 30\n", seconds=45, branch=branch
                )
                self.assertNotEqual(
                    124, rc, "a TERM before the deadline is not a timeout"
                )
                self.assertLess(
                    elapsed, 15, "it died immediately; nothing should have waited"
                )

    def test_a_SIGKILL_that_beat_the_deadline_is_NOT_reported_as_a_timeout(self):
        """The discriminator that makes the 137 normalisation safe. `timeout -k` reports 137 when its
        own SIGKILL lands — but an OOM-killed linter reports 137 too, with no deadline passed.
        Normalising unconditionally would turn a crashed tool into `not blocking`: a fail-open.

        Measured counterexample, so this is a real case and not a hypothetical one.
        """
        for branch in self._both_branches():
            with self.subTest(branch=branch):
                rc, elapsed, _, _ = self._harness(
                    "kill -9 $$\n", seconds=30, branch=branch
                )
                self.assertNotEqual(
                    124, rc, "a crash before the deadline is not a timeout"
                )
                self.assertLess(
                    elapsed, 10, "it died immediately; nothing should have waited"
                )

    def test_every_process_group_signal_is_paired_with_a_pid_retry(self):
        """STRUCTURAL, and it says so — because the runtime path cannot be forced.

        `kill -- -PID` reaches a process GROUP, which only exists if `set -m` gave the child one. When
        job control is unavailable the child stays in the parent's group, `kill -- -PID` fails with
        ESRCH and kills NOTHING — measured: the child survives. Every group signal therefore needs a
        pid retry, and three of the four had one; the teardown kill did not, so it was silently inert
        on exactly the shells that could not grant a group (gemini, PR #84).

        A behavioural test would need `set -m` to fail, and in bash it does not — `set` is a special
        builtin and cannot be shadowed. So this asserts the property over a DERIVED site set: every
        `kill -SIG "-$var"` in the file is found by pattern and each must be followed by its retry.
        Deriving the sites rather than listing them is the point; a listed set is one a fifth signal
        can be added outside of.
        """
        hook = HOOK.read_text(encoding="utf-8")
        group_signals = re.findall(
            r'kill -(\w+) "-\$\{(\w+)\}" 2>/dev/null( \|\| kill -\w+ "\$\{\w+\}" 2>/dev/null)?',
            hook,
        )
        self.assertGreaterEqual(
            len(group_signals),
            3,
            f"expected the known group signals, found {group_signals}",
        )
        unpaired = [
            f"kill -{signal} on ${{{variable}}}"
            for signal, variable, retry in group_signals
            if not retry
        ]
        self.assertEqual(
            [],
            unpaired,
            "a group signal with no pid retry kills nothing when job control is unavailable",
        )

    def test_the_escalation_is_asserted_as_BEHAVIOUR_not_as_a_spelling(self):
        """`test_the_timeout_is_macos_portable` used to assert that the strings `command -v timeout`
        and `kill -TERM` appear in the hook — a check keyed on a spelling, which stays green when the
        escalation is deleted. The behavioural cases above are the real check; this one only pins the
        portability claim that stock macOS ships neither tool, which is why a fallback must exist.
        """
        hook = HOOK.read_text(encoding="utf-8")
        self.assertIn("command -v timeout", hook)
        self.assertIn("command -v gtimeout", hook)

        # SCOPED TO THE CODE, NOT THE FILE. The first draft asserted `--kill-after` was absent from
        # the whole text and failed on the comment that explains why the long form is avoided —
        # keying on a spelling, in the very test that exists to stop keying on spellings. Comments
        # are free to name the thing they are warning about; the executable lines are not.
        code = "\n".join(
            line for line in hook.split("\n") if not line.lstrip().startswith("#")
        )
        self.assertIn(
            "-k 5", code, "the coreutils branches must pass a bounded kill-after"
        )
        self.assertNotIn(
            "--kill-after",
            code,
            "the long form is rejected by busybox (exit 1) and toybox (exit 125); use `-k 5`",
        )


class TheCallerClassifiesWhatItWasTold(unittest.TestCase):
    """The gate's exit-code arms, driven with the SHIPPED block. Every arm must name a cause it
    actually tested — `trunk could not run` and `trunk was killed` are not `new findings in the
    staged diff`, and reporting them that way sends a developer to fix a diff that is fine.

    `exit 2` is not hypothetical: reproduced on trunk 1.25.0 with a `--filter` naming a linter this
    config does not enable, which is exactly the one literal this gate passes.
    """

    def _classify(self, rc: int):
        hook = HOOK.read_text(encoding="utf-8")
        block = hook[hook.index("if command -v trunk") :]
        block = block[: block.index("\nfi\n") + 4]
        harness = (
            "TRUNK_TIMEOUT_SECONDS=180\noverall=0\n"
            'command() { [ "$1" = "-v" ] && [ "$2" = "trunk" ] && return 0; return 1; }\n'
            'run_with_timeout() { shift; return "${FAKE_RC}"; }\n'
            + block
            + '\necho "overall=${overall}"\n'
        )
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = pathlib.Path(tmp.name) / "caller.sh"
        path.write_text(harness, encoding="utf-8")
        completed = subprocess.run(
            ["bash", str(path)],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "FAKE_RC": str(rc)},
            timeout=60,
        )
        blocks = "overall=1" in completed.stdout
        return blocks, completed.stdout

    def test_a_clean_run_allows_and_a_finding_blocks(self):
        self.assertFalse(self._classify(0)[0], "a clean run must not block")
        blocks, out = self._classify(1)
        self.assertTrue(blocks)
        self.assertIn("new findings in the staged diff", out)

    def test_only_124_is_treated_as_a_timeout(self):
        """`run_with_timeout` owns the question "did the deadline elapse" and answers it with 124 on
        every branch, so anything else arriving here did NOT time out.

        This used to accept 143 as well. `timeout` passes a pre-deadline TERM straight through, so a
        lint killed after two seconds reported "exceeded 180s" and let the commit through — while the
        identical death by SIGKILL blocked it. An external TERM says nothing about whether the
        deadline was reached (codex, PR #84).
        """
        blocks, out = self._classify(124)
        self.assertFalse(blocks, "an infrastructure timeout must not block the commit")
        self.assertIn("not blocking on a timeout", out)

        blocks_143, out_143 = self._classify(143)
        self.assertTrue(
            blocks_143, "a pre-deadline TERM is not a timeout and must block"
        )
        self.assertNotIn("not blocking on a timeout", out_143)

    def test_trunk_exit_2_blocks_but_is_NOT_called_a_lint_finding(self):
        """The live misclassification. `trunk check` exits 2 when the invocation itself is unusable —
        measured on the real binary for a `--filter` naming an unsupported linter. Reported as
        findings, it sends the developer to fix a diff that no edit will clear."""
        blocks, out = self._classify(2)
        self.assertTrue(blocks, "a gate that could not run must not report a pass")
        self.assertIn("could not run", out)
        self.assertNotIn("new findings in the staged diff", out)

    def test_a_signal_death_blocks_but_is_NOT_blamed_on_the_diff(self):
        """128+N reaching the caller means the run died for a reason this hook did not cause — the
        deadline cases were already normalised to 124 upstream."""
        for rc, signal in ((137, 9), (139, 11), (143, 15)):
            with self.subTest(rc=rc):
                blocks, out = self._classify(rc)
                self.assertTrue(blocks)
                self.assertIn(f"killed (signal {signal})", out)
                self.assertNotIn("new findings in the staged diff", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
