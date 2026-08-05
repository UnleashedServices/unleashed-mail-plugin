#!/usr/bin/env python3
"""Runnable proofs for `scripts/review/resolve-plan-gate.sh` (COREDEV-2642, PR #63 review).

This logic was ~135 lines of shell inlined in `skills/implement/SKILL.md`, where it could not be
executed by a test — so the four containment bypasses it defends against, the `tr` dash-range defect
and the empty-key fail-open were recorded ONLY as comments next to the code that fixed them. Extracting
the fence to a script to make it grantable also makes it testable, and these are those tests.

Every guard below is proved as a PAIR: the real script refuses, and a mutant with that one guard
removed or reverted accepts. A refusal test alone would pass against a script that refuses everything.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Optional


REPO = Path(__file__).resolve().parents[2]
GATE = REPO / "scripts" / "review" / "resolve-plan-gate.sh"

VERDICT_STUB = """#!/usr/bin/env python3
import sys
with open(__file__ + ".argv", "w", encoding="utf-8") as stream:
    stream.write("\\n".join(sys.argv[1:]))
sys.exit(0)
"""


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise AssertionError("mutation anchor must occur exactly once: " + repr(old))
    return source.replace(old, new, 1)


class ResolvePlanGateFixture(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.bash = shutil.which("bash")
        if self.bash is None:
            self.skipTest("bash is required")
        self.temporary = tempfile.TemporaryDirectory(prefix=".plan-gate-proof-")
        self.root = Path(self.temporary.name)
        # `outside` is a sibling of the repo, never under it — the destination every bypass wants.
        self.outside = self.root / "outside"
        self.outside.mkdir()
        self.repo = self.root / "repo"
        (self.repo / "docs" / "planning").mkdir(parents=True)
        (self.repo / "scripts" / "review").mkdir(parents=True)
        self.gate_source = GATE.read_text(encoding="utf-8")
        self.install_gate(self.gate_source)

        stub = self.repo / "scripts" / "review-verdict.py"
        stub.write_text(VERDICT_STUB, encoding="utf-8")
        stub.chmod(0o755)
        self.verdict_argv = Path(str(stub) + ".argv")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def install_gate(self, source: str) -> None:
        path = self.repo / "scripts" / "review" / "resolve-plan-gate.sh"
        path.write_text(source, encoding="utf-8")
        path.chmod(0o755)

    def write_plan(self, name: str) -> Path:
        path = self.repo / "docs" / "planning" / name
        path.write_text("# plan\n", encoding="utf-8")
        return path

    def run_gate(self, argument: str, source: Optional[str] = None) -> subprocess.CompletedProcess:
        if source is not None:
            self.install_gate(source)
        try:
            return subprocess.run(
                [self.bash, "scripts/review/resolve-plan-gate.sh"],
                cwd=str(self.repo),
                input=argument,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            if source is not None:
                self.install_gate(self.gate_source)

    def assert_refused(self, argument: str, needle: str, source: Optional[str] = None) -> None:
        result = self.run_gate(argument, source)
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(needle, result.stderr)
        self.assertFalse(
            self.verdict_argv.exists(),
            "the gate ran `verify` on a plan it should have refused to resolve",
        )

    def assert_verified(self, argument: str, expected_plan: str) -> None:
        result = self.run_gate(argument)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Plan: " + expected_plan, result.stdout)
        self.assertTrue(self.verdict_argv.is_file(), "verify never ran")
        self.assertEqual(
            ["verify", "--plan", expected_plan],
            self.verdict_argv.read_text(encoding="utf-8").splitlines(),
        )


class PhysicalContainmentProofs(ResolvePlanGateFixture):
    """The four ways this guard was bypassed, each of which reached `GATE OK` in its day."""

    def test_absolute_path_outside_the_repo_is_refused(self) -> None:
        outside = self.outside / "OUTSIDE_PLAN.md"
        outside.write_text("# not tracked\n", encoding="utf-8")
        self.assert_refused(str(outside), "is not a tracked plan")

    def test_dotdot_escape_wearing_the_prefix_is_refused(self) -> None:
        # `docs/planning/../../evil/` resolves to `<repo>/evil` — outside docs/planning, which is what
        # the guard is about. `case` globs match `/`, so the `docs/planning/*PLAN*.md` pattern accepts
        # this spelling and the containment check is the only thing that refuses it.
        evil = self.repo / "evil"
        evil.mkdir()
        (evil / "OUTSIDE_PLAN.md").write_text("# not tracked\n", encoding="utf-8")
        self.assert_refused(
            "docs/planning/../../evil/OUTSIDE_PLAN.md", "does not live under"
        )

    def test_symlinked_plan_wearing_the_prefix_is_refused(self) -> None:
        target = self.outside / "OUTSIDE_PLAN.md"
        target.write_text("# not tracked\n", encoding="utf-8")
        link = self.repo / "docs" / "planning" / "EVIL_PLAN.md"
        link.symlink_to(target)
        self.assert_refused("docs/planning/EVIL_PLAN.md", "does not live under")

    def test_symlinked_planning_root_is_refused(self) -> None:
        """The subtlest one: realpath'ing the BASE too would resolve both sides through one link."""
        shutil.rmtree(self.repo / "docs" / "planning")
        target = self.outside / "planning"
        target.mkdir()
        (target / "OUTSIDE_PLAN.md").write_text("# not tracked\n", encoding="utf-8")
        (self.repo / "docs" / "planning").symlink_to(target, target_is_directory=True)
        self.assert_refused("docs/planning/OUTSIDE_PLAN.md", "does not live under")

    def test_symlinked_plan_is_refused_through_the_GLOB_branch_too(self) -> None:
        """The direct branch refused this symlink while the glob branch happily took it."""
        target = self.outside / "OUTSIDE_PLAN.md"
        target.write_text("# not tracked\n", encoding="utf-8")
        (self.repo / "docs" / "planning" / "EVIL_PLAN.md").symlink_to(target)
        self.assert_refused("evil", "No plan matches")

    def test_removing_either_containment_call_admits_the_symlink(self) -> None:
        target = self.outside / "OUTSIDE_PLAN.md"
        target.write_text("# not tracked\n", encoding="utf-8")
        (self.repo / "docs" / "planning" / "EVIL_PLAN.md").symlink_to(target)

        direct_mutant = _replace_once(
            self.gate_source, '    _contained "$_p" || _refuse_uncontained "$ARG"\n', ""
        )
        result = self.run_gate("docs/planning/EVIL_PLAN.md", direct_mutant)
        self.assertEqual(
            0, result.returncode, "the direct-branch containment call is not load-bearing"
        )

        self.verdict_argv.unlink()
        glob_mutant = _replace_once(
            self.gate_source, '            _contained "$p" || continue\n', ""
        )
        result = self.run_gate("evil", glob_mutant)
        self.assertEqual(
            0, result.returncode, "the glob-branch containment call is not load-bearing"
        )

    def test_realpathing_the_base_reopens_the_symlinked_root(self) -> None:
        shutil.rmtree(self.repo / "docs" / "planning")
        target = self.outside / "planning"
        target.mkdir()
        (target / "OUTSIDE_PLAN.md").write_text("# not tracked\n", encoding="utf-8")
        (self.repo / "docs" / "planning").symlink_to(target, target_is_directory=True)

        mutant = _replace_once(
            self.gate_source,
            'base = os.path.join(root, "docs", "planning")   # deliberately NOT realpath\'d',
            'base = os.path.realpath(os.path.join(root, "docs", "planning"))',
        )
        result = self.run_gate("docs/planning/OUTSIDE_PLAN.md", mutant)
        self.assertEqual(
            0,
            result.returncode,
            "leaving the base unresolved is not what refuses a symlinked planning root",
        )


class ArgumentBindingProofs(ResolvePlanGateFixture):
    """MAJ-9: the argument is data on stdin, never shell syntax."""

    def test_multiline_argument_is_refused(self) -> None:
        self.write_plan("DARK_MODE_PLAN.md")
        self.assert_refused("dark mode\nsecond line\n", "multi-line argument")

    def test_shell_metacharacters_in_a_feature_name_are_inert(self) -> None:
        self.write_plan("DARK_MODE_PLAN.md")
        for hostile in (
            '"; touch pwned; #',
            "$(touch pwned)",
            "`touch pwned`",
            "dark mode' && touch pwned && echo '",
        ):
            with self.subTest(argument=hostile):
                self.run_gate(hostile)
                self.assertFalse(
                    (self.repo / "pwned").exists(),
                    f"{hostile!r} executed instead of being treated as a name",
                )

    def test_a_quoted_feature_name_still_resolves(self) -> None:
        """Inertness must not come from refusing everything with punctuation in it."""
        self.write_plan("DARK_MODE_PLAN.md")
        self.assert_verified("dark mode", "docs/planning/DARK_MODE_PLAN.md")


class ResolutionProofs(ResolvePlanGateFixture):
    def test_exact_full_desc_and_ticket_stems_each_resolve(self) -> None:
        self.write_plan("COREDEV_2328_REVIEWER_STATUS_CAPTURE_PLAN.md")
        expected = "docs/planning/COREDEV_2328_REVIEWER_STATUS_CAPTURE_PLAN.md"
        for argument in (
            "coredev 2328 reviewer status capture",
            "reviewer status capture",
            "coredev 2328",
        ):
            with self.subTest(argument=argument):
                if self.verdict_argv.exists():
                    self.verdict_argv.unlink()
                self.assert_verified(argument, expected)

    def test_a_pure_substring_is_not_identity(self) -> None:
        self.write_plan("DARK_MODE_PLAN.md")
        result = self.run_gate("mode")
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("No plan is named exactly", result.stderr)
        self.assertFalse(self.verdict_argv.exists())

    def test_two_exact_matches_are_ambiguous(self) -> None:
        self.write_plan("COREDEV_1_DARK_MODE_PLAN.md")
        self.write_plan("COREDEV_2_DARK_MODE_PLAN.md")
        result = self.run_gate("dark mode")
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("AMBIGUOUS", result.stderr)
        self.assertFalse(self.verdict_argv.exists())

    def test_whitespace_only_argument_does_not_resolve_to_the_first_plan(self) -> None:
        """`tr` maps a space to `_`, so a `-n "$KEY"` guard would call this a match."""
        self.write_plan("DARK_MODE_PLAN.md")
        self.assert_refused(" ", "No plan matches")

    def test_content_guard_relaxation_makes_whitespace_name_a_plan(self) -> None:
        """`-n "$KEY"` is not enough: `tr` has already turned the space into `_`, and `*_*` matches
        most plan filenames.

        The observable is a CANDIDATE, not a silent resolution: the substring rule added later
        (`full review, #41`) turns what used to be auto-resolution into an exit-2 suggestion list. So
        the guard's effect today is the difference between "names nothing" and "names something",
        which is the distinction that matters — and asserting exit 0 here would be asserting a
        fail-open that a second, independent guard already closed.
        """
        self.write_plan("DARK_MODE_PLAN.md")
        clean = self.run_gate(" ")
        self.assertEqual(1, clean.returncode)
        self.assertIn("No plan matches", clean.stderr)

        mutant = _replace_once(
            self.gate_source, 'if [[ "$KEY" == *[!_]* ]]; then', 'if [ -n "$KEY" ]; then'
        )
        result = self.run_gate(" ", mutant)
        self.assertEqual(
            2,
            result.returncode,
            "the *[!_]* content guard is not what stops whitespace from naming a plan",
        )
        self.assertIn("No plan is named exactly", result.stderr)

    def test_tr_set_keeps_the_dash_last(self) -> None:
        """` -.` is a RANGE covering 32..46, so `c+dark` matched C-DARK_PLAN.md."""
        self.write_plan("C-DARK_PLAN.md")
        result = self.run_gate("c+dark")
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(self.verdict_argv.exists())

    def test_dash_range_mutation_matches_a_plan_nobody_named(self) -> None:
        self.write_plan("C-DARK_PLAN.md")
        mutant = _replace_once(
            self.gate_source,
            "    KEY=$(printf '%s' \"$ARG\" | tr '[:upper:] .-' '[:lower:]___')",
            "    KEY=$(printf '%s' \"$ARG\" | tr '[:upper:] -.' '[:lower:]___')",
        )
        result = self.run_gate("c+dark", mutant)
        self.assertEqual(
            0, result.returncode, "the trailing dash is not what keeps `c+dark` from matching"
        )

    def test_no_plan_at_all_fails_closed(self) -> None:
        self.assert_refused("dark mode", "No plan matches")

    def test_a_failing_verify_is_propagated(self) -> None:
        self.write_plan("DARK_MODE_PLAN.md")
        stub = self.repo / "scripts" / "review-verdict.py"
        stub.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n", encoding="utf-8")
        result = self.run_gate("dark mode")
        self.assertEqual(1, result.returncode, "a rejecting verdict must not report success")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
