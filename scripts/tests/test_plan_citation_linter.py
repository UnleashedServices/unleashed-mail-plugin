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

ONE NEGATION EXEMPTS ONE REFERENCE (codex, PR #67 pass 13 — reproduced). The correction exemption
(`… does not exist`) was scoped to the sentence, and a symmetric clause split still handed the text
BETWEEN two citations to both of them: `§9.9z of the journal plan does not exist, but this rule relies
on §9.8z of the journal plan.` exempted §9.8z on §9.9z's negation. The window is asymmetric now — a
POST-position negation belongs to the citation it follows, a PRE-position form to the 40 characters
before — so §9.8z is reported and §9.9z is not. The control (the POST regex applied to the pre-window
as well) is RUN on the same fixture and reports neither. The plain lint is used, not `--fix-citations`:
the inserted lines shift the copy's internal line pins, so the run fails on those too and only the two
named `[cite-external]` lines are asserted.
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


class OneNegationExemptsOneReference(unittest.TestCase):
    """The pass-13 laundering shape: one negation, TWO external references in one sentence."""

    SENTENCE = "§9.9z of the journal plan does not exist, but this rule relies on §9.8z of the journal plan.\n\n"
    HEADING = "## 5. Risk register"
    REPORTED_98 = "§9.8z of the journal plan does NOT exist"
    REPORTED_99 = "§9.9z of the journal plan does NOT exist"
    # The shipped exemption test, and the control's: the POST-position regex run over the PRE window too,
    # which hands `does not exist` — sitting between the two citations — to §9.8z as well.
    EXEMPTION_OLD = "            if _POST_NEGATION.search(post) or _PRE_NEGATION.search(pre):\n"
    EXEMPTION_NEW = "            if _POST_NEGATION.search(pre + post) or _PRE_NEGATION.search(pre):\n"

    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="plan-lint.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.copy = os.path.join(self.scratch, "plan.md")
        with open(PLAN, encoding="utf-8") as fh:
            src = fh.read()
        self.assertEqual(1, src.count(self.HEADING), "the fixture plan must carry the §5 heading exactly once")
        self.assertNotIn("§9.9z", src)
        self.assertNotIn("§9.8z", src)
        with open(self.copy, "w", encoding="utf-8") as fh:
            fh.write(src.replace(self.HEADING, self.SENTENCE + self.HEADING, 1))

    def _lint(self, linter=LINTER):
        """The plain lint of the copy — cwd is the repository root, so `--repo .` resolves the journal plan."""
        p = subprocess.run(["python3", linter, self.copy], cwd=REPO, capture_output=True, text=True, check=False)
        return p.returncode, p.stdout + p.stderr

    def _control_linter(self):
        with open(LINTER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.EXEMPTION_OLD), "the exemption line is not unique — the control is not the control")
        control = os.path.join(self.scratch, "validate-plan-citations-symmetric.py")
        with open(control, "w", encoding="utf-8") as fh:
            fh.write(text.replace(self.EXEMPTION_OLD, self.EXEMPTION_NEW, 1))
        return control

    def test_one_negation_does_not_exempt_two_references_in_a_sentence(self):
        rc, out = self._lint()
        self.assertNotEqual(0, rc, f"the fabricated §9.8z passed the lint:\n{out}")
        self.assertIn(self.REPORTED_98, out, f"§9.8z was exempted by §9.9z's negation:\n{out}")
        self.assertNotIn(self.REPORTED_99, out, f"§9.9z's own correction was reported as a claim:\n{out}")
        # The control: the negation between the citations exempts BOTH — neither is reported (measured), and
        # the run still exits non-zero on the shifted internal pins, so the status alone is not the oracle.
        rc2, out2 = self._lint(self._control_linter())
        self.assertNotEqual(0, rc2, out2)
        self.assertNotIn(self.REPORTED_98, out2,
                         f"the CONTROL (symmetric window) still reported §9.8z — the fixture is not the finding:\n{out2}")
        self.assertNotIn(self.REPORTED_99, out2, out2)


if __name__ == "__main__":
    unittest.main()
