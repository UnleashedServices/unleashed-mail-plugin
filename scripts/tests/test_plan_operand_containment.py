#!/usr/bin/env python3
"""The gate's two plan-state entrypoints must not write outside this repository's planning tree.

THE FINDING (PR #63 recheck, P1) — reproduced before it was fixed.
`brainstorm` is model-invocable and pre-approves both the snapshot and the persistence command, so the
MODEL chooses `--plan`. Neither enforced containment: any existing file on disk was accepted, the
snapshot sidecar was written beside it, and even a NON-approving persist created and chmod'd a
`.verdicts` directory there — walking straight past the skill's apparent `Write(docs/planning/**)`
boundary with no user gesture.

The containment lives in the granted entrypoints, not in `review-verdict.py`: that tool has a designed,
tested behaviour for a plan outside any git repo and is also the maintainer's own CLI. What has to be
bounded is the pre-approved path the model can enter.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO / "scripts" / "review" / "snapshot-plan.sh"
PERSIST = REPO / "scripts" / "review" / "persist-verdict.sh"


class PlanOperandContainment(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="plan-containment-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "."], cwd=self.root, check=True)
        # A dedicated out-of-repo directory, NOT the shared system temp root. Placing it there meant a
        # run that legitimately wrote outside the repo left `.verdicts` in a directory every later run
        # also inspects — so a mutation run poisoned the next clean run's assertion. The isolation is
        # the fixture's job; a probe that contaminates its own environment proves nothing twice.
        self.outside_dir = self.root.parent / (self.root.name + "-outside")
        self.outside_dir.mkdir()
        self.addCleanup(shutil.rmtree, self.outside_dir, ignore_errors=True)
        (self.root / "docs" / "planning").mkdir(parents=True)
        self.inside = self.root / "docs" / "planning" / "FEATURE_PLAN.md"
        self.inside.write_text("# Plan\nbody\n", encoding="utf-8")
        self.elsewhere = self.root / "NOT_A_PLAN.md"
        self.elsewhere.write_text("# Not in the planning tree\n", encoding="utf-8")

    def test_a_symlinked_planning_subtree_cannot_launder_its_target(self):
        """The `--under` boundary was `realpath`'d, which MOVED it (PR #63 recheck, P1).

        With `docs/planning -> ../src`, resolving the subtree made the base `<root>/src`, so a regular
        file reached through the link satisfied the containment check and was accepted as a plan — the
        model-invocable snapshot and persistence wrappers would then create `.verdicts` state under
        `src` while promising to operate only under `docs/planning`. Reproduced.

        The operand is still fully resolved; only the BASE is left physical, so a symlinked subtree
        resolves out from under the boundary instead of being laundered through it. Same asymmetry
        `resolve-plan-gate.sh` uses, and it was fixed there four times before it landed here.
        """
        linked = Path(tempfile.mkdtemp(prefix="linked-repo-"))
        self.addCleanup(shutil.rmtree, linked, ignore_errors=True)
        (linked / "src").mkdir()
        (linked / "src" / "EVIL_PLAN.md").write_text("# not a tracked plan\n", encoding="utf-8")
        (linked / "docs").mkdir()
        (linked / "docs" / "planning").symlink_to("../src")
        subprocess.run(["git", "init", "-q", "."], cwd=linked, check=True)

        result = subprocess.run(
            ["python3", str(REPO / "scripts" / "review" / "containment.py"),
             "--tool", "probe", "--label", "plan", "--under", "docs/planning",
             "--", "docs/planning/EVIL_PLAN.md"],
            cwd=linked, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertNotIn("src/EVIL_PLAN.md", result.stdout,
                         "the symlinked subtree laundered a file outside docs/planning")

    def test_a_checkout_whose_path_ends_in_a_space_still_works(self):
        """`strip()` on `git rev-parse` output ate a legal path character (PR #63 recheck).

        A space is valid in a path, so a checkout ending in one had that byte removed from the computed
        root — which then named a DIFFERENT directory, so every operand resolved outside it and was
        refused. That breaks the capture, audit, snapshot and persistence wrappers at once, since they
        all share this helper. Git terminates the path with exactly one newline; only that is stripped.
        """
        spaced = Path(tempfile.mkdtemp()) / "trailing space "
        spaced.mkdir()
        self.addCleanup(shutil.rmtree, spaced.parent, ignore_errors=True)
        (spaced / "docs" / "planning").mkdir(parents=True)
        (spaced / "docs" / "planning" / "X_PLAN.md").write_text("# plan\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", "."], cwd=spaced, check=True)

        result = subprocess.run(
            ["python3", str(REPO / "scripts" / "review" / "containment.py"),
             "--tool", "probe", "--label", "plan", "--under", "docs/planning",
             "--", "docs/planning/X_PLAN.md"],
            cwd=spaced, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("docs/planning/X_PLAN.md", result.stdout.strip())

    def test_a_real_planning_subtree_is_still_accepted(self):
        """Positive control — the boundary must refuse a symlinked subtree, not every subtree."""
        result = subprocess.run(
            ["python3", str(REPO / "scripts" / "review" / "containment.py"),
             "--tool", "probe", "--label", "plan", "--under", "docs/planning",
             "--", "docs/planning/FEATURE_PLAN.md"],
            cwd=self.root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("docs/planning/FEATURE_PLAN.md", result.stdout.strip())

    def run_entrypoint(self, script, *operands):
        return subprocess.run(
            ["bash", str(script), *operands], cwd=self.root,
            capture_output=True, text=True, check=False, input="",
        )

    def assert_nothing_written(self, near: Path) -> None:
        """A refusal that still created state is not a refusal — this is the half the finding names."""
        self.assertFalse((near.parent / ".verdicts").exists(),
                         f"a refused call created {near.parent / '.verdicts'}")
        self.assertFalse(list(near.parent.glob("*.sha256")), "a refused call left a snapshot sidecar")

    # ---- snapshot ------------------------------------------------------------------------------

    def test_snapshot_refuses_a_plan_outside_the_repository(self):
        outside = self.outside_dir / "OUTSIDE_PLAN.md"
        outside.write_text("# outside\n", encoding="utf-8")
        result = self.run_entrypoint(SNAPSHOT, str(outside))
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assert_nothing_written(outside)

    def test_snapshot_refuses_an_in_repo_plan_outside_docs_planning(self):
        result = self.run_entrypoint(SNAPSHOT, "NOT_A_PLAN.md")
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assert_nothing_written(self.elsewhere)

    def test_snapshot_refuses_a_symlink_into_the_planning_tree(self):
        """Realpath, not the lexical prefix — a symlink must not launder its own target."""
        link = self.root / "docs" / "planning" / "LINKED_PLAN.md"
        link.symlink_to(self.elsewhere)
        result = self.run_entrypoint(SNAPSHOT, "docs/planning/LINKED_PLAN.md")
        self.assertNotEqual(0, result.returncode, result.stdout)

    def test_snapshot_accepts_a_real_plan(self):
        """The positive control: containment must not be refusing everything."""
        result = self.run_entrypoint(SNAPSHOT, "docs/planning/FEATURE_PLAN.md")
        self.assertEqual(0, result.returncode, result.stderr)

    # ---- persistence ---------------------------------------------------------------------------

    def test_persist_refuses_a_plan_outside_docs_planning_even_when_non_approving(self):
        """The reproduction used MISSING/MISSING — a non-approving call still created `.verdicts`.

        Asserting on a non-approving verdict matters: it is the case a reader would assume is inert,
        and it was the one that wrote outside the repository.
        """
        result = self.run_entrypoint(
            PERSIST, "--plan", "NOT_A_PLAN.md", "--verdict", "REQUEST_CHANGES",
            "--reviewer", "gemini=MISSING", "--reviewer", "codex=MISSING",
        )
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assert_nothing_written(self.elsewhere)

    def test_persist_refuses_a_plan_outside_the_repository(self):
        outside = self.outside_dir / "OUTSIDE_PERSIST_PLAN.md"
        outside.write_text("# outside\n", encoding="utf-8")
        result = self.run_entrypoint(
            PERSIST, "--plan", str(outside), "--verdict", "REQUEST_CHANGES",
            "--reviewer", "gemini=MISSING", "--reviewer", "codex=MISSING",
        )
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assert_nothing_written(outside)

    def test_persist_accepts_a_real_plan(self):
        result = self.run_entrypoint(
            PERSIST, "--plan", "docs/planning/FEATURE_PLAN.md", "--verdict", "REQUEST_CHANGES",
            "--reviewer", "gemini=MISSING", "--reviewer", "codex=MISSING",
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_wrapper_run_from_a_subdirectory_still_accepts_in_repo_plans(self):
        """`repository_root()` was `realpath(getcwd())`, which made the CWD the repository.

        Launched from `scripts/`, every plan in the tree became "outside the repository" — the capture,
        audit, snapshot and persistence wrappers all share this helper, so all four broke at once
        (PR #63 recheck). Reproduced by running the snapshot entrypoint from a subdirectory with a
        `../`-relative plan. It resolves the Git top level now.

        This is the fourth false refusal this recheck surfaced, and the same shape each time: a guard
        right about the danger and wrong about the boundary.
        """
        subdirectory = self.root / "scripts"
        subdirectory.mkdir()
        result = subprocess.run(
            ["bash", str(SNAPSHOT), "../docs/planning/FEATURE_PLAN.md"],
            cwd=str(subdirectory), capture_output=True, text=True, check=False, input="",
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_outside_the_repo_is_still_refused_from_a_subdirectory(self):
        """Resolving the top level must widen the boundary to the repo, not remove it."""
        subdirectory = self.root / "scripts2"
        subdirectory.mkdir()
        outside = self.outside_dir / "OUTSIDE_PLAN.md"
        outside.write_text("# outside\n", encoding="utf-8")
        result = subprocess.run(
            ["bash", str(SNAPSHOT), str(outside)],
            cwd=str(subdirectory), capture_output=True, text=True, check=False, input="",
        )
        self.assertNotEqual(0, result.returncode, result.stdout)

    def test_outside_a_git_worktree_it_fails_closed(self):
        """No repository means no containment boundary — refusing is the only safe answer.

        Falling back to the working directory here would restore the exact bug above.
        """
        loose = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, loose, ignore_errors=True)
        (loose / "docs" / "planning").mkdir(parents=True)
        plan = loose / "docs" / "planning" / "FEATURE_PLAN.md"
        plan.write_text("# Plan\n", encoding="utf-8")
        result = subprocess.run(
            ["bash", str(SNAPSHOT), "docs/planning/FEATURE_PLAN.md"],
            cwd=str(loose), capture_output=True, text=True, check=False, input="",
        )
        self.assertNotEqual(0, result.returncode, result.stdout)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
