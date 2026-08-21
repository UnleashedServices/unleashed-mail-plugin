#!/usr/bin/env python3
"""`persist-verdict.sh`'s own refusals — the SHELL layer, which no test drove.

THE GAP. `persist-verdict.sh` is the gate's shell front door: it normalises each reviewer spec and
then `exec`s `review-verdict.py write`. Its stated core invariant lives at line 120 —

    # The gate's core invariant: an absent or empty transcript can never be counted as approval.

— and deleting it left the entire suite green. Seven test files mention the script by path (doc
gates, path contracts, inventories) but none EXECUTES it, so every refusal it owns was unobserved.

WHY THE DIAGNOSTIC IS ASSERTED, NOT JUST THE EXIT CODE. With the guard removed the run still fails,
because the downstream Python writer refuses a MISSING reviewer too. A cell asserting only
`returncode != 0` therefore passes against the mutant and proves nothing about this layer. The
distinguishing string `a missing transcript cannot produce approval` is emitted only here.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PERSIST = REPO / "scripts" / "review" / "persist-verdict.sh"
MISSING_DIAGNOSTIC = "a missing transcript cannot produce approval"


@unittest.skipUnless(PERSIST.is_file(), "persist-verdict.sh not present")
class AMissingTranscriptCannotProduceApproval(unittest.TestCase):
    def setUp(self):
        # A REAL git worktree with the plan at docs/planning/: the script refuses anything else
        # ("not inside a Git worktree" / "not an in-repo docs/planning file") long before the
        # invariant under test, so a bare tmpdir fixture would fail for the wrong reason.
        self.d = Path(tempfile.mkdtemp(prefix="persist-verdict-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))
        self.repo = self.d / "repo"
        plandir = self.repo / "docs" / "planning"
        plandir.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True,
                       capture_output=True, text=True)
        self.plan = plandir / "FEATURE_PLAN.md"
        self.plan.write_text("# Plan\nbytes\n", encoding="utf-8")
        self.real = self.d / "real-transcript.txt"
        self.real.write_text("reviewer output\nVERDICT: APPROVE\n", encoding="utf-8")
        self.empty = self.d / "empty-transcript.txt"
        self.empty.write_bytes(b"")

    def run_persist(self, verdict: str, gemini: str, codex: str):
        return subprocess.run(
            ["bash", str(PERSIST), "--plan", str(self.plan), "--verdict", verdict,
             "--reviewer", gemini, "--reviewer", codex,
             "--created-at", "2026-01-01T00:00:00Z"],
            cwd=self.repo, capture_output=True, text=True, check=False, input="",
        )

    def assert_refused_here(self, result, case: str):
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, f"{case}: approved anyway\n{output}")
        self.assertIn(MISSING_DIAGNOSTIC, output,
                      f"{case}: refused, but NOT by this layer — the downstream writer also "
                      f"refuses, so only this diagnostic discriminates\n{output}")

    def test_a_BARE_MISSING_gemini_cannot_approve(self):
        self.assert_refused_here(
            self.run_persist("APPROVE", "gemini=MISSING", f"codex=APPROVE:{self.real}"),
            "gemini=MISSING + APPROVE")

    def test_a_BARE_MISSING_codex_cannot_approve(self):
        """The second disjunct. One cell covers only one side of an `||`."""
        self.assert_refused_here(
            self.run_persist("APPROVE", f"gemini=APPROVE:{self.real}", "codex=MISSING"),
            "codex=MISSING + APPROVE")

    def test_a_MISSING_reviewer_cannot_produce_APPROVE_WITH_NOTES(self):
        """The `case` lists two approving verdicts; APPROVE alone leaves the other unasserted."""
        self.assert_refused_here(
            self.run_persist("APPROVE_WITH_NOTES", "gemini=MISSING", f"codex=APPROVE:{self.real}"),
            "gemini=MISSING + APPROVE_WITH_NOTES")

    def test_an_EMPTY_transcript_is_DERIVED_as_missing_and_cannot_approve(self):
        """The derived route: a status claiming APPROVE whose transcript is 0 bytes is normalised to
        `<name>=MISSING` by `persist_reviewer_spec`, then caught here. Today that combination is only
        ever asserted alongside `DISAGREEMENT`, so the approving pairing was untested."""
        self.assert_refused_here(
            self.run_persist("APPROVE", f"gemini=APPROVE:{self.empty}", f"codex=APPROVE:{self.real}"),
            "gemini empty transcript + APPROVE")

    def test_two_REAL_transcripts_are_NOT_refused_by_this_layer(self):
        """The positive control. Without it every cell above is satisfied by a guard that refuses
        everything. It asserts only that THIS layer let the call through — the downstream writer may
        still refuse for plan-binding reasons, which is not what these cells are about."""
        result = self.run_persist(
            "APPROVE", f"gemini=APPROVE:{self.real}", f"codex=APPROVE:{self.real}")
        self.assertNotIn(MISSING_DIAGNOSTIC, result.stdout + result.stderr,
                         "the shell layer refused two real transcripts")


if __name__ == "__main__":
    unittest.main()
