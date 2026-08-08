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
import sys
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


class StateWritesArePinnedToTheContainedDirectory(unittest.TestCase):
    """A pathname handed across an exec is not a pin (PR #63 recheck, P1 — reproduced).

    The granted wrappers validate the plan with `containment.py` and pass `review-verdict.py` the
    resolved path. Resolution then happens AGAIN, in a second process, so a same-account swap of
    `docs/planning` for a symlink in that window sent every state write through the new ancestor:
    `snapshot-plan.sh` returned 0 having created `.verdicts/` and the digest sidecar in an outside
    directory. Passing the realpath — the earlier fix — removed the "validated one string, opened
    another" half and could not remove this half, because a string cannot pin an inode across an exec.

    State is now created and written through a descriptor walk from the repository root, so a symlinked
    component fails whenever it was planted. The post-swap STATE is built directly, for the reason it
    always is here: a race cannot be staged deterministically, and the attacker's leftovers are what
    the guard has to refuse.
    """

    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="state-pin-")).resolve()
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.repo = self.base / "repo"
        self.outside = self.base / "outside"
        (self.repo / "docs" / "planning").mkdir(parents=True)
        self.outside.mkdir()
        subprocess.run(["git", "init", "-q", "."], cwd=self.repo, check=True)
        self.plan = self.repo / "docs" / "planning" / "FEATURE_PLAN.md"
        self.plan.write_text("# Plan\nbody\n", encoding="utf-8")

    def snapshot(self, operand: str):
        return subprocess.run(
            [sys.executable, str(REPO / "scripts" / "review-verdict.py"),
             "snapshot", "--plan", operand],
            cwd=str(self.repo), capture_output=True, text=True, check=False,
        )

    def test_a_planning_directory_SWAPPED_for_a_symlink_creates_no_outside_state(self):
        resolved = str(self.plan.resolve())          # what containment.py --absolute emits
        shutil.move(str(self.repo / "docs" / "planning"), str(self.outside / "planning"))
        (self.repo / "docs" / "planning").symlink_to(self.outside / "planning")

        result = self.snapshot(resolved)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("symlinked path component", result.stderr)
        self.assertFalse((self.outside / "planning" / ".verdicts").exists(),
                         "state was created outside the repository through the swapped ancestor")

    def gate(self, rel: str) -> None:
        """Run an honest gate for `rel` in the fixture repo, leaving a valid approving artifact."""
        import hashlib

        state = self.repo / "state" / "unleashed-mail" / "review-transcripts" / "H"
        state.mkdir(parents=True, exist_ok=True)
        for path in (self.repo / "state", state.parent.parent, state.parent, state):
            path.chmod(0o700)
        payload = (self.repo / rel).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        specs = []
        for reviewer, run in (("gemini", "a" * 32), ("codex", "b" * 32)):
            leaf = state / f"COREDEV-1r1-{reviewer}-{run}.txt"
            leaf.write_text(f"{reviewer}\nVERDICT: APPROVE\n", encoding="utf-8")
            Path(str(leaf) + ".launch").write_text(f"{run} {reviewer}\n", encoding="utf-8")
            stamp = leaf.stat().st_mtime_ns
            os.utime(str(leaf) + ".launch", ns=(stamp - 10**6, stamp - 10**6))
            Path(str(leaf) + ".plan").write_text(f"{digest}  {rel}\n", encoding="utf-8")
            Path(str(leaf) + ".planbytes").write_bytes(payload)
            prompt = b"prompt\n"
            Path(str(leaf) + ".prompt").write_bytes(prompt)
            Path(str(leaf) + ".promptsha256").write_text(
                hashlib.sha256(prompt).hexdigest() + "  prompt.md\n", encoding="utf-8")
            specs += ["--reviewer", f"{reviewer}=APPROVE:{leaf}"]
        verdict = str(REPO / "scripts" / "review-verdict.py")
        for argv in (["snapshot", "--plan", rel],
                     ["write", "--plan", rel, "--verdict", "APPROVE"] + specs):
            done = subprocess.run([sys.executable, verdict] + argv, cwd=str(self.repo),
                                  capture_output=True, text=True, check=False)
            self.assertEqual(0, done.returncode, done.stderr)

    def test_a_SWAPPED_ancestor_cannot_make_verify_read_another_plans_artifact(self):
        """The READ path was not covered by the write fix (PR #63 recheck, P1).

        `verify` reopened the artifact by pathname after its `islink` pre-checks, so the same ancestor
        swap sent verification at a different directory: `GATE OK` against another plan and ITS
        matching artifact, with the ancestor restored afterwards leaving `implement` proceeding on a
        plan nothing had verified. The decoy here is genuinely gated, so nothing but the pinning can
        refuse it.
        """
        rel = "docs/planning/FEATURE_PLAN.md"
        (self.repo / "decoydocs" / "planning").mkdir(parents=True)
        (self.repo / "decoydocs" / "planning" / "FEATURE_PLAN.md").write_text(
            "# Plan\nDECOY\n", encoding="utf-8")
        self.gate("decoydocs/planning/FEATURE_PLAN.md")
        shutil.move(str(self.repo / "decoydocs" / "planning"), str(self.outside / "planning"))

        shutil.rmtree(self.repo / "docs" / "planning")
        (self.repo / "docs" / "planning").symlink_to(self.outside / "planning")

        result = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "review-verdict.py"), "verify", "--plan", rel],
            cwd=str(self.repo), capture_output=True, text=True, check=False)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertNotIn("GATE OK", result.stdout + result.stderr)
        self.assertIn("symlinked path component", result.stdout + result.stderr)

    def test_an_ordinary_plan_still_gets_its_private_state(self):
        """Positive control: the walk must refuse a substituted ancestor, not every write."""
        result = self.snapshot("docs/planning/FEATURE_PLAN.md")
        self.assertEqual(0, result.returncode, result.stderr)
        verdicts = self.repo / "docs" / "planning" / ".verdicts"
        self.assertEqual(0o700, verdicts.stat().st_mode & 0o777)
        self.assertEqual({".gitignore", "FEATURE_PLAN.md.reviewed-sha256"},
                         {entry.name for entry in verdicts.iterdir()})
        self.assertEqual("*\n", (verdicts / ".gitignore").read_text(encoding="utf-8"))


class ContainedReadWalksEveryComponent(unittest.TestCase):
    """`contained_regular_file()` validates a NAME; the read must open the object it approved.

    THE FINDING (PR #63 recheck, P1). Every consumer validated with `contained_regular_file()` and then
    re-opened that pathname with a leaf-only `O_NOFOLLOW`. That flag protects the LEAF and says nothing
    about ancestors, so a same-account process could rename an accepted operand's parent and put a
    symlink in its place between the two calls — and the substituted parent was traversed happily. In
    `bind-prompt.py` the operand in question is the PLAN, the most load-bearing input in the gate.

    The walk that closes it existed in `snapshot-operands.py` only; it now lives in `containment.py`
    beside the validator. A race cannot be staged deterministically, so the post-swap STATE is built
    directly — a symlinked parent component is what the attacker leaves behind, and the read must refuse
    it whether it appeared a microsecond ago or was always there.
    """

    def setUp(self) -> None:
        # RESOLVED: `repository_root()` realpaths the worktree, and on macOS the system temp root is
        # itself a symlink (`/var` -> `/private/var`). An unresolved fixture root makes every operand
        # look like it is outside the repository, which would refuse these cells for a reason that has
        # nothing to do with the walk. Consumers pass the realpath `contained_regular_file()` returns,
        # so this also matches how the function is really called.
        self.root = Path(tempfile.mkdtemp(prefix="contained-read-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "."], cwd=self.root, check=True)
        (self.root / "real" / "planning").mkdir(parents=True)
        self.plan = self.root / "real" / "planning" / "FEATURE_PLAN.md"
        self.plan.write_text("# Plan\nreal bytes\n", encoding="utf-8")
        # The swapped parent: an in-repo symlink, so `realpath` still lands INSIDE the repository and
        # `contained_regular_file()` accepts the name. An out-of-repo target would be caught by the
        # existing containment check, and the cell would prove nothing about the walk.
        (self.root / "sneaky").mkdir()
        (self.root / "sneaky" / "planning").symlink_to(self.root / "real" / "planning")
        self.through_link = self.root / "sneaky" / "planning" / "FEATURE_PLAN.md"

    def read(self, path: Path, source: str):
        """Run `source` against `path` in the fixture repo, returning the completed process."""
        program = (
            "import sys; sys.path.insert(0, %r)\n" % str(REPO / "scripts" / "review")
            + "import containment\n"
            + source
        )
        return subprocess.run(
            [sys.executable, "-c", program, str(path)],
            cwd=str(self.root), capture_output=True, text=True, check=False,
        )

    WALK = "sys.stdout.write(containment.read_contained(sys.argv[1], 'plan file').decode())\n"
    # The reverted implementation: ONE `O_NOFOLLOW` open of the same pathname.
    LEAF_ONLY = (
        "import os\n"
        "fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW)\n"
        "sys.stdout.write(containment.read_leaf(fd, 'plan file').decode())\n"
    )

    def test_the_name_containment_accepts_is_still_refused_when_a_PARENT_is_a_link(self):
        from importlib import util

        spec = util.spec_from_file_location(
            "containment_under_proof", str(REPO / "scripts" / "review" / "containment.py"))
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            # Containment accepts the linked spelling: the leaf is a real file and resolves in-repo.
            accepted = module.contained_regular_file(str(self.through_link), "plan file")
        finally:
            os.chdir(cwd)
        self.assertEqual(os.path.realpath(str(self.plan)), accepted)

        refused = self.read(self.through_link, self.WALK)
        self.assertNotEqual(0, refused.returncode, refused.stdout)
        self.assertIn("could not be traversed without following a link", refused.stderr)

    def test_the_reverted_leaf_only_read_ACCEPTS_that_same_path(self):
        """Discrimination. Without this the refusal above could come from any unrelated strictness."""
        accepted = self.read(self.through_link, self.LEAF_ONLY)
        self.assertEqual(0, accepted.returncode, accepted.stderr)
        self.assertEqual("# Plan\nreal bytes\n", accepted.stdout)

    def test_the_physical_path_still_reads(self):
        """Positive control: the walk must refuse a substituted ancestor, not every operand.

        The consumers pass the `realpath` `contained_regular_file()` returns, so in a run with no
        interference every component is physical and this is the path actually taken.
        """
        result = self.read(self.plan, self.WALK)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("# Plan\nreal bytes\n", result.stdout)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
