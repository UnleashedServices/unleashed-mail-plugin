#!/usr/bin/env python3
"""`validate-plan-citations.py --fix-citations` FAILS when an anchor cannot be repaired.

THE FINDING (codex, PR #67 pass 9). An anchor that matched zero or several lines was reported as
`STALE RULE` and then fell through to the ordinary lint — which can pass, because the citation may
still point at ONE line that matches — so a caller read "fixed" off exit 0 while nothing had been
rewritten. The repair now exits 1 with `PLAN CITATION REPAIR FAILED` in that case; a clean plan
still repairs-and-lints to exit 0.

The fixture is a COPY of the real plan (the linter's cross-file rules resolve against `--repo .`,
so the run's cwd is the repository root); the duplicate is the §5 inert-gate anchor appended at EOF,
which is exactly "one anchor, two matches".
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINTER = os.path.join(REPO, "scripts", "validate-plan-citations.py")
PLAN = os.path.join(REPO, "docs", "planning", "COREDEV-2617_PLUGIN_STATE_BASE_DIR_PLAN.md")
ANCHOR = "| The gate goes inert"


class FixCitationsExitCode(unittest.TestCase):
    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="plan-lint.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.copy = os.path.join(self.scratch, "plan.md")
        shutil.copy(PLAN, self.copy)

    def _run(self):
        return subprocess.run(["python3", LINTER, self.copy, "--fix-citations"],
                              cwd=REPO, capture_output=True, text=True, check=False)

    def test_an_ambiguous_anchor_fails_the_repair(self):
        with open(self.copy, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        hits = [l for l in lines if l.startswith(ANCHOR)]
        self.assertEqual(1, len(hits), f"the fixture plan must carry the anchor exactly once: {len(hits)}")
        with open(self.copy, "a", encoding="utf-8") as fh:
            fh.write(hits[0] + "\n")                        # now two lines match the §5 rule
        p = self._run()
        self.assertNotEqual(0, p.returncode, f"an unrepaired anchor exited 0:\n{p.stdout}{p.stderr}")
        self.assertIn("PLAN CITATION REPAIR FAILED", p.stdout, p.stdout + p.stderr)
        self.assertIn("§5 inert-gate row", p.stdout, "the failure does not name the ambiguous rule")

    def test_a_clean_plan_repairs_and_lints_to_exit_0(self):
        p = self._run()
        self.assertEqual(0, p.returncode, f"the untouched plan copy did not pass:\n{p.stdout}{p.stderr}")
        self.assertNotIn("PLAN CITATION REPAIR FAILED", p.stdout)
        self.assertIn("plan lint OK", p.stdout, p.stdout)


if __name__ == "__main__":
    unittest.main()
