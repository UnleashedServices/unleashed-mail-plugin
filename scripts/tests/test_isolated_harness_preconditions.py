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

        for command in (["git", "init", "-q", "."],
                        ["git", "config", "user.email", "probe@test"],
                        ["git", "config", "user.name", "probe"],
                        ["git", "add", "-A"],
                        ["git", "commit", "-qm", "init"]):
            subprocess.run(command, cwd=self.repo, check=True, capture_output=True)

        self.witness = self.root / "REVIEWER_RAN.txt"
        stubs = self.root / "stubs"
        stubs.mkdir()
        for harness in REVIEW.glob("isolated-*-review.sh"):
            stub = stubs / reviewer_binary(harness)
            stub.write_text(REVIEWER_STUB, encoding="utf-8")
            stub.chmod(0o755)

        self.env = dict(os.environ)
        self.env["PATH"] = f"{stubs}{os.pathsep}{self.env['PATH']}"
        self.env["HOME"] = str(self.home)
        self.env["XDG_STATE_HOME"] = str(self.root / "state")
        self.env["UM_HARNESS_WITNESS"] = str(self.witness)

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
