#!/usr/bin/env python3
"""Pre-run refusals carried by MORE THAN ONE isolated review harness, gated as a family.

`isolated-codex-review.sh` and `isolated-agy-review.sh` carry byte-identical copies of two refusals
that run before the reviewer is launched:

  * the AMBIGUOUS PLAN OPERAND check — a relative operand that names one file from the caller's
    directory and a different one from the repository root is refused rather than resolved by the
    caller-first precedence in `PLAN_REL="${FROM_CALLER:-$FROM_ROOT}"`. Otherwise the plan
    `review-verdict` later authenticates (resolved from the root) is not the plan the reviewer read.
  * the NON-EMPTY RESERVED LEAF check — a leaf that already holds another round's transcript is
    refused rather than overwritten. Measured with the check removed: the harness reuses the leaf,
    truncates 117 bytes of an earlier transcript to 17, and reports `VERDICT: APPROVE`.

Neither copy had a cell in either direction. Fixing one member of a pair like this and leaving the
other is exactly how these two harnesses drifted apart before, so this module DERIVES the family by
searching the shipped sources for each guard's message instead of naming the files: a harness that
grows one of these guards is covered here automatically, and one that renames the message empties
the family, which `test_the_families_are_not_empty` refuses to let pass silently.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REVIEW = REPO / "scripts" / "review"

LEAF_MARKER = "refusing to reuse a non-empty reserved leaf"
AMBIGUOUS_MARKER = "ambiguous plan operand"

PROMPT_BODY = "Review the plan for correctness, security and completeness.\n" * 40
PLAN_TEXT = "# Plan\nCOMMITTED VERSION\n"
STALE_TRANSCRIPT = "STALE TRANSCRIPT FROM AN EARLIER ROUND\n" * 3

#: Every stubbed reviewer records that it ran and then APPROVES — so a cell that expects a refusal
#: fails loudly if the guard let the round through, rather than passing on an unrelated error.
REVIEWER_STUB = """#!/usr/bin/env bash
printf 'ran\\n' >> "$UM_HARNESS_WITNESS"
printf 'VERDICT: APPROVE\\n'
"""


def harnesses_with(marker: str) -> list[Path]:
    """Every shipped isolated harness whose source carries `marker`."""
    return sorted(p for p in REVIEW.glob("isolated-*-review.sh")
                  if marker in p.read_text(encoding="utf-8"))


def reviewer_binary(harness: Path) -> str:
    """`isolated-codex-review.sh` -> `codex`. The binary the harness puts on the wire."""
    match = re.fullmatch(r"isolated-(.+)-review\.sh", harness.name)
    assert match, harness.name
    return match.group(1)


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "needs git and bash")
class IsolatedHarnessPreconditions(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="harness-precond-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

        # HOME and XDG_STATE_HOME are redirected into the fixture: these harnesses write plugin state,
        # and a test must never reach the developer's real one.
        self.home = self.root / "home"
        self.home.mkdir()

        self.repo = self.root / "repo"
        (self.repo / "docs" / "planning").mkdir(parents=True)
        self.plan_rel = "docs/planning/FEATURE_PLAN.md"
        (self.repo / self.plan_rel).write_text(PLAN_TEXT, encoding="utf-8")
        # The SHADOW plan: the same relative operand, resolvable from `repo/sub` as well. Its presence
        # is the whole ambiguity scenario, and it is committed so the harness can stage either one.
        self.shadow_dir = self.repo / "sub"
        (self.shadow_dir / "docs" / "planning").mkdir(parents=True)
        (self.shadow_dir / self.plan_rel).write_text("# Plan\nSHADOW VERSION\n", encoding="utf-8")

        self.witness = self.root / "REVIEWER_RAN.txt"
        stubs = self.root / "stubs"
        stubs.mkdir()
        for harness in REVIEW.glob("isolated-*-review.sh"):
            stub = stubs / reviewer_binary(harness)
            stub.write_text(REVIEWER_STUB, encoding="utf-8")
            stub.chmod(0o755)

        # THE ENVIRONMENT IS BUILT BEFORE THE FIXTURE'S OWN GIT CALLS, AND SANITISED.
        # An inherited `GIT_DIR`/`GIT_WORK_TREE` silently redirects which repository git operates on —
        # the very thing `_tf_sanitize_git_env` exists to stop in the code under test, reproduced here
        # in the fixture that tests it (codex, PR #73). Measured before fixing: with `GIT_DIR` naming a
        # bare repository, this loop wrote `user.email=probe@test` and `user.name=probe` INTO THAT
        # REPOSITORY and then errored at `git add` with status 128 — mutating unrelated state and
        # failing before a single guard ran.
        self.env = self.sanitized(os.environ)
        # `os.defpath`, not `""`: `shutil.which` in the class decorator falls back to it when PATH is
        # unset, so the child gets the same search path the skip decision was made against. Falling
        # back to an EMPTY string would hand the child a PATH containing only the stub directory and
        # fail later with the wrong cause — see `test_changeset.py`'s scratch-allocation cell.
        self.env["PATH"] = f"{stubs}{os.pathsep}{self.env.get('PATH', os.defpath)}"
        self.env["HOME"] = str(self.home)
        self.env["XDG_STATE_HOME"] = str(self.root / "state")
        self.env["UM_HARNESS_WITNESS"] = str(self.witness)

        self.build_repo(self.repo)

    #: The fixture's own git invocations, factored out so a cell can run them against a chosen
    #: directory and prove they are not steerable by the caller's environment.
    FIXTURE_GIT = (["git", "init", "-q", "."],
                   ["git", "config", "user.email", "probe@test"],
                   ["git", "config", "user.name", "probe"],
                   ["git", "add", "-A"],
                   ["git", "commit", "-qm", "init"])

    @staticmethod
    def sanitized(env):
        """`env` without any `GIT_*`, which is what makes the fixture's git calls unsteerable."""
        return {k: v for k, v in env.items() if not k.startswith("GIT_")}

    def build_repo(self, path, env=None):
        for command in self.FIXTURE_GIT:
            subprocess.run(command, cwd=str(path), check=True, capture_output=True,
                           env=env if env is not None else self.env)

    # ── fixtures ──────────────────────────────────────────────────────────────────────────────────

    def reserved_leaf(self, harness: Path, *, contents: str = ""):
        """A reserved leaf carrying the sidecars the harness authenticates before it reads the leaf.

        The plan and prompt bindings are MANDATORY and are checked FIRST, so a leaf without them is
        refused for the wrong reason and a cell built on it would prove nothing about the guard under
        test. `contents` is what the leaf itself already holds.
        """
        base = Path(tempfile.mkdtemp(prefix="leaf-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        out = base / "COREDEV-9999-r1-probe.txt"
        out.write_text(contents, encoding="utf-8")

        prompt = base / "prompt.md"
        prompt.write_text(PROMPT_BODY + f"REVIEW TARGET: {self.plan_rel}\n", encoding="utf-8")

        plan_bytes = (self.repo / self.plan_rel).read_bytes()
        Path(f"{out}.plan").write_text(
            f"{hashlib.sha256(plan_bytes).hexdigest()}  {self.plan_rel}\n", encoding="utf-8")
        Path(f"{out}.planbytes").write_bytes(plan_bytes)
        Path(f"{out}.promptsha256").write_text(
            hashlib.sha256(prompt.read_bytes()).hexdigest() + "  prompt.md\n", encoding="utf-8")
        # A canonical launch record. Neither harness reads it before the guards under test — only
        # `pty-capture --allocated` does, downstream — but a fixture should still look like something
        # the allocator could have written.
        token = "gemini" if reviewer_binary(harness) == "agy" else reviewer_binary(harness)
        Path(f"{out}.launch").write_text("a" * 32 + f" {token}\n", encoding="utf-8")
        return out, prompt

    def run_harness(self, harness: Path, prompt: Path, out: Path, *, cwd: Path | None = None,
                    plan_operand: str | None = None):
        result = subprocess.run(
            ["bash", str(harness), str(prompt), str(out), "30",
             plan_operand if plan_operand is not None else self.plan_rel],
            cwd=str(cwd if cwd is not None else self.repo), env=self.env,
            capture_output=True, text=True, check=False, input="",
        )
        return result, result.stdout + result.stderr

    def assertReviewerNeverRan(self, output: str):
        self.assertFalse(self.witness.exists(),
                         f"the reviewer was launched despite the refusal: {output}")

    # ── the family itself ─────────────────────────────────────────────────────────────────────────

    def test_the_FIXTURE_ITSELF_is_not_steerable_by_an_inherited_GIT_DIR(self):
        """codex, PR #73 — reproduced before fixing, and pinned here.

        The fixture's git calls inherited `os.environ`, so an exported `GIT_DIR` pointed them at an
        EXTERNAL repository. Measured: with `GIT_DIR` naming a bare repo, the run wrote
        `user.email=probe@test` and `user.name=probe` into it and then errored at `git add` with
        status 128 — mutating unrelated state AND failing before any guard executed.

        `test_changeset.py` already filtered `GIT_*` and this twin did not: the same
        fix-one-member-of-a-family defect this module exists to prevent, in the module itself.

        The cell is discriminating: neuter `sanitized()` to return its argument unchanged and the
        victim's config picks up `probe@test`, which the last assertion catches.
        """
        victim = self.root / "victim.git"
        subprocess.run(["git", "init", "-q", "--bare", str(victim)],
                       check=True, capture_output=True, env=self.env)
        fresh = self.root / "fresh"
        (fresh / "docs" / "planning").mkdir(parents=True)
        (fresh / self.plan_rel).write_text(PLAN_TEXT, encoding="utf-8")

        poisoned = dict(os.environ, GIT_DIR=str(victim), GIT_WORK_TREE=str(victim))
        self.build_repo(fresh, env=self.sanitized(poisoned))

        self.assertTrue((fresh / ".git").is_dir(),
                        "the fixture repo was not built in place — the git calls went elsewhere")
        config = subprocess.run(["git", "--git-dir", str(victim), "config", "--list", "--local"],
                                capture_output=True, text=True, env=self.env)
        self.assertNotIn("probe@test", config.stdout,
                         f"the fixture's git calls wrote into the repository GIT_DIR named:\n"
                         f"{config.stdout}")

    def test_the_families_are_not_empty(self):
        """Every other cell loops over a family derived by searching for a message. If a message is
        reworded the family goes empty and those loops pass VACUOUSLY, reporting green while testing
        nothing. This cell is what makes that impossible."""
        for marker in (LEAF_MARKER, AMBIGUOUS_MARKER):
            with self.subTest(marker=marker):
                family = harnesses_with(marker)
                self.assertGreaterEqual(
                    len(family), 2,
                    f"expected this guard in at least two harnesses, found {[p.name for p in family]}"
                    f" — if it was deliberately reworded, update the marker here in the same commit")

    # ── the ambiguous plan operand ────────────────────────────────────────────────────────────────

    def test_an_AMBIGUOUS_plan_operand_is_refused_before_the_review(self):
        for harness in harnesses_with(AMBIGUOUS_MARKER):
            with self.subTest(harness=harness.name):
                self.witness.unlink(missing_ok=True)
                out, prompt = self.reserved_leaf(harness)
                result, output = self.run_harness(harness, prompt, out, cwd=self.shadow_dir)
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn(AMBIGUOUS_MARKER, output,
                              f"refused, but not as ambiguous: {output}")
                self.assertReviewerNeverRan(output)

    def test_an_UNAMBIGUOUS_operand_is_not_refused_as_ambiguous(self):
        """The discrimination control. Without it the cell above would also pass against a harness
        that refused every operand — the same relative path, run from the repository root where it
        resolves exactly one way, must get past this guard."""
        for harness in harnesses_with(AMBIGUOUS_MARKER):
            with self.subTest(harness=harness.name):
                self.witness.unlink(missing_ok=True)
                out, prompt = self.reserved_leaf(harness)
                _, output = self.run_harness(harness, prompt, out, cwd=self.repo)
                self.assertNotIn(AMBIGUOUS_MARKER, output,
                                 f"an unambiguous operand was refused as ambiguous: {output}")

    # ── the reserved leaf ─────────────────────────────────────────────────────────────────────────

    def test_a_NON_EMPTY_reserved_leaf_is_refused_before_the_review_runs(self):
        for harness in harnesses_with(LEAF_MARKER):
            with self.subTest(harness=harness.name):
                self.witness.unlink(missing_ok=True)
                out, prompt = self.reserved_leaf(harness, contents=STALE_TRANSCRIPT)
                result, output = self.run_harness(harness, prompt, out)
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn(LEAF_MARKER, output, f"refused, but not for the leaf: {output}")
                self.assertReviewerNeverRan(output)
                # The bytes of the earlier round are still there: the refusal happened BEFORE the
                # overwrite, which is the property that matters and not merely that it exited 1.
                self.assertEqual(STALE_TRANSCRIPT, out.read_text(encoding="utf-8"),
                                 "the earlier round's transcript was modified despite the refusal")

    def test_an_EMPTY_reserved_leaf_is_not_refused_as_non_empty(self):
        """The discrimination control: the guard is about the leaf's CONTENT, so an empty leaf — the
        state the allocator actually leaves behind — must get past it."""
        for harness in harnesses_with(LEAF_MARKER):
            with self.subTest(harness=harness.name):
                self.witness.unlink(missing_ok=True)
                out, prompt = self.reserved_leaf(harness)
                _, output = self.run_harness(harness, prompt, out)
                self.assertNotIn(LEAF_MARKER, output,
                                 f"an EMPTY reserved leaf was refused as non-empty: {output}")


if __name__ == "__main__":
    unittest.main()
