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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
