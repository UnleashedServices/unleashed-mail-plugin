#!/usr/bin/env python3
"""Operand refusals in the review shell entry points — none of which any test executed.

`resolve-plan-gate.sh` and `snapshot-plan.sh` are invoked from skills with operands the model
composes, so their arity and stdin refusals are the last thing standing between a malformed
invocation and a silent hang or a wrong plan. Deleting each of them left the whole suite green.

Each cell asserts the DIAGNOSTIC, not merely a non-zero exit: the mutants below still fail further
on (containment, missing operand), so a cell checking only `returncode != 0` passes against them and
proves nothing.
"""

from __future__ import annotations

import contextlib
import os
import pty
import signal
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESOLVE = REPO / "scripts" / "review" / "resolve-plan-gate.sh"
SNAPSHOT = REPO / "scripts" / "review" / "snapshot-plan.sh"


class TheReviewShellsRefuseMalformedOperands(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="shell-operands-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.repo = self.d / "repo"
        (self.repo / "docs" / "planning").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True,
                       capture_output=True, text=True)
        self.plan = self.repo / "docs" / "planning" / "FEATURE_PLAN.md"
        self.plan.write_text("# Plan\nbytes\n", encoding="utf-8")

    def run_script(self, script: Path, *operands, stdin=""):
        return subprocess.run(
            ["bash", str(script), *operands],
            cwd=self.repo, capture_output=True, text=True, check=False, input=stdin,
        )

    @unittest.skipUnless(RESOLVE.is_file(), "resolve-plan-gate.sh not present")
    def test_resolve_plan_gate_refuses_TWO_operands(self):
        """`resolve-plan-gate.sh:50`. Asserting the message matters: with the arity check deleted the
        second operand is simply ignored and the run continues on the first, so a cell checking only
        the exit status would not distinguish the mutant."""
        result = self.run_script(RESOLVE, "docs/planning/FEATURE_PLAN.md", "EXTRA")
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("takes at most one operand", output)

    @unittest.skipUnless(RESOLVE.is_file(), "resolve-plan-gate.sh not present")
    def test_resolve_plan_gate_refuses_NO_operand_when_stdin_is_a_REAL_TTY(self):
        """`resolve-plan-gate.sh:59`. The guard exists so an interactive caller is not left sitting
        at a silent `cat` waiting for an EOF it does not know to send (2026-08-17 audit, AF-13).

        A pty is REQUIRED: `[ -t 0 ]` is false for a pipe, so the ordinary subprocess stdin every
        other cell uses takes the piped branch and never reaches this line. That is precisely why the
        guard had no test. The cell also bounds the wait — with the guard deleted the script blocks
        on `cat` forever, so a hang IS the failure being detected.
        """
        primary, secondary = pty.openpty()
        proc = subprocess.Popen(
            ["bash", str(RESOLVE)], cwd=self.repo, stdin=secondary,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True,     # its own process group, so the whole tree can be reaped
        )
        os.close(secondary)
        hung = False
        try:
            try:
                _, err = proc.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                hung = True
                # REAP THE WHOLE GROUP, and give the pty EOF first. Killing only `proc` leaves the
                # `cat` grandchild alive holding the stdout/stderr pipes, so a second `communicate()`
                # blocks forever — the cell would then hang CI for the full job timeout instead of
                # failing fast, which is worse than not detecting the mutation at all.
                os.close(primary)
                primary = None
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.communicate(timeout=10)
        finally:
            if primary is not None:
                os.close(primary)
        if hung:
            self.fail("no operand with a TTY on stdin HUNG — the refusal at :59 is gone and the "
                      "script is sitting at a silent `cat`")
        self.assertNotEqual(0, proc.returncode, err)
        self.assertIn("stdin is a terminal", err)

    @unittest.skipUnless(SNAPSHOT.is_file(), "snapshot-plan.sh not present")
    def test_snapshot_plan_refuses_MORE_than_one_operand(self):
        """`snapshot-plan.sh:37`. The extra operand must come after a VALID plan: with an invalid
        first operand the earlier emptiness check fires instead and the arity guard is never reached,
        which would make the cell pass against the mutant."""
        result = self.run_script(SNAPSHOT, "docs/planning/FEATURE_PLAN.md", "EXTRA")
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("takes exactly one operand", output)


@unittest.skipUnless((REPO / "scripts" / "review" / "persist-verdict.sh").is_file(),
                     "persist-verdict.sh not present")
class ThePersistRoutingIsWhatMakesTheNameCheckUnREACHABLE(unittest.TestCase):
    """Why `persist-verdict.sh:101`'s name check has no direct test — and the guard that replaces one.

    A sweep flagged `[ "$name" = "$expected_name" ] || die "invalid reviewer specification"` as
    untested. It is untested because it is UNREACHABLE through the CLI: `--reviewer` routes on the
    `gemini=*` / `codex=*` prefixes, so `GEMINI_SPEC` can only ever hold a `gemini=` spec and is only
    ever checked against `gemini`. Measured: `GEMINI=…` and `gemini2=…` are both rejected earlier
    with "unknown reviewer in specification".

    Testing the inner check directly would mean sourcing the script, which executes it — there is no
    main-guard. So rather than contort a test, this asserts the ROUTING property that makes the check
    unreachable. If anyone widens that routing, this cell fails and the inner guard becomes live and
    testable — which is the outcome that actually matters.
    """

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="persist-routing-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.repo = self.d / "repo"
        (self.repo / "docs" / "planning").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True,
                       capture_output=True, text=True)
        (self.repo / "docs" / "planning" / "P_PLAN.md").write_text("# Plan\n", encoding="utf-8")
        self.tx = self.d / "tx"
        self.tx.write_text("x\nVERDICT: APPROVE\n", encoding="utf-8")

    def test_only_the_two_exact_reviewer_prefixes_are_routed(self):
        script = REPO / "scripts" / "review" / "persist-verdict.sh"
        for spec in ("GEMINI=APPROVE:{}", "gemini2=APPROVE:{}", "Gemini=APPROVE:{}",
                     " gemini=APPROVE:{}"):
            with self.subTest(spec=spec):
                result = subprocess.run(
                    ["bash", str(script), "--plan", "docs/planning/P_PLAN.md",
                     "--verdict", "APPROVE", "--reviewer", spec.format(self.tx),
                     "--reviewer", f"codex=APPROVE:{self.tx}"],
                    cwd=self.repo, capture_output=True, text=True, check=False, input="",
                )
                output = result.stdout + result.stderr
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn("unknown reviewer in specification", output,
                              "the routing widened — persist-verdict.sh:101's name check is now "
                              "reachable and needs a direct test")


if __name__ == "__main__":
    unittest.main()
