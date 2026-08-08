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
import re
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
        # A real worktree, because the gate now anchors at `git rev-parse --show-toplevel` and FAILS
        # CLOSED outside one (PR #63 recheck, P2) — a fixture that models a repository must be one.
        # No commit is needed; --show-toplevel answers in an empty repository.
        subprocess.run(["git", "init", "-q", "."], cwd=self.repo, check=True)
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
        # the RAW spelling — but since the caller-anchor fix (PR #63 recheck, P2), `resolve_in_repo`
        # collapses the `..` physically FIRST, so the guard classifies the file's true identity
        # (`evil/OUTSIDE_PLAN.md`) and refuses it as what it is: not a tracked plan. The prefix cannot
        # be worn at all any more; the refusal family changed from "uncontained" to "not tracked", and
        # both fail closed with the verdict tool never invoked.
        evil = self.repo / "evil"
        evil.mkdir()
        (evil / "OUTSIDE_PLAN.md").write_text("# not tracked\n", encoding="utf-8")
        self.assert_refused(
            "docs/planning/../../evil/OUTSIDE_PLAN.md", "is not a tracked plan"
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
            self.gate_source, '    _contained "$REL" || _refuse_uncontained "$ARG"\n', ""
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

        # TWO mechanisms now refuse a symlinked planning root: `resolve_in_repo` physicalizes the
        # PARENT before containment (the PR #63 recheck caller-anchor fix), and `_contained` keeps its
        # base unresolved. A single mutant no longer discriminates — each mechanism alone still
        # refuses — so defence in depth is asserted on the singles and the PAIR is proved by the
        # double mutant admitting. (The earlier single-mutant version of this proof stopped failing
        # the moment the second mechanism landed; two independent mechanisms defeat single mutants.)
        base_mutant = _replace_once(
            self.gate_source,
            'base = os.path.join(root, "docs", "planning")   # deliberately NOT realpath\'d',
            'base = os.path.realpath(os.path.join(root, "docs", "planning"))',
        )
        result = self.run_gate("docs/planning/OUTSIDE_PLAN.md", base_mutant)
        self.assertNotEqual(
            0, result.returncode,
            "with the base realpath'd, resolve_in_repo alone no longer refuses the symlinked root",
        )
        self.assertFalse(self.verdict_argv.exists(), "the single mutant reached the verdict tool")

        resolver_mutant = _replace_once(
            self.gate_source,
            '        *) return 1 ;;\n',
            '        *) printf \'%s\\n\' "$1" ;;\n',
        )
        result = self.run_gate("docs/planning/OUTSIDE_PLAN.md", resolver_mutant)
        self.assertNotEqual(
            0, result.returncode,
            "with resolve_in_repo bypassed, the unresolved base alone no longer refuses",
        )
        self.assertFalse(self.verdict_argv.exists(), "the single mutant reached the verdict tool")

        double_mutant = _replace_once(
            base_mutant,
            '        *) return 1 ;;\n',
            '        *) printf \'%s\\n\' "$1" ;;\n',
        )
        result = self.run_gate("docs/planning/OUTSIDE_PLAN.md", double_mutant)
        self.assertEqual(
            0, result.returncode,
            "disabling BOTH mechanisms was expected to admit the symlinked planning root — "
            "if it still refuses, a third mechanism exists and this proof understates the design",
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


class ArgumentIsNeverInShellSyntax(unittest.TestCase):
    """The `implement` recipe must not substitute the user's argument into shell syntax at all.

    THE FINDING (PR #63 recheck, P1). The fence bound the argument through a quoted heredoc, which kept
    metacharacters literal — but the placeholder is substituted TEXTUALLY across the whole fence before
    the shell runs, so an argument containing a line equal to the heredoc DELIMITER closed the body
    early and every following line was parsed as a shell command. With the skill model-invocable that
    needed no user gesture. A quoted delimiter stops expansion inside the body; it does not stop the
    body from ending, and no quoting can, because the fault is one level above the quoting.
    """

    SKILL = Path(__file__).resolve().parents[2] / "skills" / "implement" / "SKILL.md"

    def shell_fences(self):
        return re.findall(r"```(?:bash|sh|shell)\n(.*?)```", self.SKILL.read_text(encoding="utf-8"), re.S)

    def test_no_shell_fence_contains_the_argument_placeholder(self):
        """Asserted on FENCES, not on the file. The placeholder is legitimate in prose and in the

        title — what must never happen is it landing where a shell parses it.
        """
        offenders = [f for f in self.shell_fences() if "ARGUMENTS" in f]
        self.assertEqual([], offenders, "the argument is back in shell syntax")

    def test_the_skill_carries_no_heredoc_at_all(self):
        """The delimiter cannot be injected if there is no delimiter.

        Deliberately broader than the one delimiter that was exploitable: any `<<` in this recipe
        re-creates the shape, and a differently-named delimiter would be just as matchable.
        """
        for fence in self.shell_fences():
            self.assertNotIn("<<", fence, "a heredoc reappeared in the implement recipe")

    def test_the_gate_accepts_the_documented_operand_form(self):
        """Positive control: removing the heredoc is only a fix if the documented call still works."""
        fences = [f for f in self.shell_fences() if "resolve-plan-gate.sh" in f]
        self.assertEqual(1, len(fences), "expected exactly one gate invocation fence")
        self.assertIn("resolve-plan-gate.sh\" docs/planning/", fences[0])


class CallerAnchorProofs(ResolvePlanGateFixture):
    """The gate anchors at the worktree root and honors the CALLER'S spelling (PR #63 recheck, P2).

    Everything used to be evaluated against the caller's working directory: from a repository
    subdirectory the documented root-relative operand existed nowhere, fell through to name
    resolution, and the glob — evaluated in the same wrong place — matched nothing, so a valid, gated
    plan was reported as "No plan matches". The absolute in-repo spelling was likewise refused as
    "not a tracked plan" purely for how it was spelled. Both are false refusals, and a guard that
    refuses correct work is one an operator switches off.
    """

    def run_gate_operand(self, argument: str, cwd) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.bash, str(self.repo / "scripts" / "review" / "resolve-plan-gate.sh"), argument],
            cwd=str(cwd), input="", capture_output=True, text=True, check=False,
        )

    def assert_resolves(self, result) -> None:
        self.assertIn("Plan: docs/planning/DARK_MODE_PLAN.md", result.stdout,
                      result.stdout + result.stderr)
        self.assertEqual(
            "verify\n--plan\ndocs/planning/DARK_MODE_PLAN.md",
            self.verdict_argv.read_text(encoding="utf-8"),
            "the verdict tool must receive the repo-relative identity",
        )

    def test_root_relative_operand_resolves_from_a_subdirectory(self):
        self.write_plan("DARK_MODE_PLAN.md")
        sub = self.repo / "sub"
        sub.mkdir()
        self.assert_resolves(self.run_gate_operand("docs/planning/DARK_MODE_PLAN.md", sub))

    def test_caller_relative_operand_resolves_from_a_subdirectory(self):
        self.write_plan("DARK_MODE_PLAN.md")
        sub = self.repo / "sub"
        sub.mkdir()
        self.assert_resolves(self.run_gate_operand("../docs/planning/DARK_MODE_PLAN.md", sub))

    def test_a_feature_name_resolves_from_a_subdirectory(self):
        """The name branch's glob is the exact place the original defect fell through."""
        self.write_plan("DARK_MODE_PLAN.md")
        sub = self.repo / "sub"
        sub.mkdir()
        self.assert_resolves(self.run_gate_operand("dark mode", sub))

    def test_absolute_in_repo_operand_resolves(self):
        """The old prefix test refused this spelling outright — same file, wrong refusal."""
        self.write_plan("DARK_MODE_PLAN.md")
        absolute = str(self.repo / "docs" / "planning" / "DARK_MODE_PLAN.md")
        self.assert_resolves(self.run_gate_operand(absolute, self.repo))

    def test_an_operand_meaning_two_files_is_refused_as_ambiguous(self):
        """Branch order must not silently decide which of two real files the gate verifies."""
        self.write_plan("DARK_MODE_PLAN.md")
        sub = self.repo / "sub"
        (sub / "docs" / "planning").mkdir(parents=True)
        (sub / "docs" / "planning" / "DARK_MODE_PLAN.md").write_text("# impostor\n",
                                                                     encoding="utf-8")
        result = self.run_gate_operand("docs/planning/DARK_MODE_PLAN.md", sub)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("AMBIGUOUS", result.stderr)
        self.assertFalse(self.verdict_argv.exists(), "ambiguity must not reach the verdict tool")

    def test_outside_a_worktree_the_gate_fails_closed(self):
        """No repository -> no docs/planning to contain plans to. Falling back to the working
        directory would restore the exact bug the anchor fixes."""
        result = self.run_gate_operand("docs/planning/DARK_MODE_PLAN.md", self.root)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("not inside a Git worktree", result.stderr)

    def test_removing_the_root_anchor_breaks_subdirectory_resolution(self):
        """The revert-proof: without the `cd`, a feature NAME from a subdirectory finds nothing.

        A PATH operand survives this mutant — `resolve_in_repo` carries its own bases, so the direct
        branch is cwd-independent by construction — which is itself worth knowing: the first version
        of this proof probed a path and concluded the anchor was decorative. The discriminating probe
        is the NAME branch, whose glob runs wherever the process stands, and which is also the branch
        the original defect fell through to.
        """
        self.write_plan("DARK_MODE_PLAN.md")
        sub = self.repo / "sub"
        sub.mkdir()
        mutant = _replace_once(self.gate_source, 'cd "$TOP" || exit 1\n', "")
        self.install_gate(mutant)
        try:
            result = self.run_gate_operand("dark mode", sub)
        finally:
            self.install_gate(self.gate_source)
        self.assertNotEqual(0, result.returncode,
                            "without the root anchor the name branch was expected to find nothing")
        self.assertIn("No plan matches", result.stderr)
        self.assertFalse(self.verdict_argv.exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
