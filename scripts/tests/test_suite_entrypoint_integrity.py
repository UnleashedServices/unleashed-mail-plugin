#!/usr/bin/env python3
"""No test class may be defined AFTER `unittest.main()` (COREDEV-2691, codex on PR #78).

`unittest.main()` discovers the classes defined SO FAR and then exits. A class declared below that
call is silently omitted when the file is run directly — and the run still prints **OK**. A passing
result that quietly omits tests is the worst shape a suite can have: it is indistinguishable from a
passing result that ran them.

Codex found ONE instance (`test_plugin_state_base.py`, where two new D-prime hook cells were being
dropped). Deriving the family found TWELVE files, and every one measured before the fix diverged:

    test_callers_scan.py            direct 33   discovery 36
    test_capture_prompt_binding.py  direct 18   discovery 26
    test_doc_gates.py               direct 43   discovery 57
    test_freshness.py               direct 35   discovery 42

CI runs discovery, so those tests were never actually skipped in CI. The hazard is developer-facing
and real all the same: iterating on one file directly is an ordinary thing to do, and it silently
under-reports. This file makes the invariant enforceable instead of remembered.

LEXICAL, deliberately. The honest check is "direct count == discovery count", but that means
executing every suite twice — minutes of subprocesses, including suites that shell out. The lexical
rule is what actually causes the divergence, it is cheap, and it cannot itself be flaky.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUARD = 'if __name__ == "__main__":'


def _test_files() -> "list[Path]":
    """DERIVED from git, never enumerated — the lesson this whole PR is about."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "scripts/tests/test_*.py",
         "mcp/review-synthesizer/tests/test_*.py"],
        capture_output=True, text=True, check=True).stdout.split()
    return [REPO / rel for rel in out]


class NoTestClassIsDefinedAfterUnittestMain(unittest.TestCase):
    def test_every_suite_declares_its_classes_before_the_entrypoint(self):
        offenders = []
        for path in _test_files():
            lines = path.read_text(encoding="utf-8").splitlines()
            guards = [i for i, line in enumerate(lines) if line.startswith(GUARD)]
            if not guards:
                continue
            after = [f"{i + 1}: {lines[i].strip()}"
                     for i in range(guards[0] + 1, len(lines))
                     if lines[i].startswith("class ")]
            if after:
                rel = path.relative_to(REPO).as_posix()
                offenders.append(f"{rel}: {len(after)} class(es) after {GUARD} — " + "; ".join(after))
        self.assertEqual([], offenders,
                         "these classes are silently dropped when the file is run directly, and the "
                         "run still prints OK:\n  " + "\n  ".join(offenders))

    def test_the_derivation_reaches_the_whole_suite(self):
        """The derivation's own control. An empty or truncated file list makes the cell above pass
        vacuously — which is the exact failure this PR is about, one level up."""
        found = {p.relative_to(REPO).as_posix() for p in _test_files()}
        self.assertGreater(len(found), 20, f"suspiciously few test files: {sorted(found)}")
        for required in ("scripts/tests/test_plugin_state_base.py",
                         "scripts/tests/test_doc_gates.py",
                         "mcp/review-synthesizer/tests/test_capture.py"):
            self.assertIn(required, found)

    def test_the_rule_matches_the_shape_it_claims_to_reject(self):
        """The pattern's own control — it must flag a class below the guard and not one above it."""
        below = [GUARD, "    unittest.main()", "", "class Late(unittest.TestCase):", "    pass"]
        above = ["class Early(unittest.TestCase):", "    pass", "", GUARD, "    unittest.main()"]
        for lines, want in ((below, True), (above, False)):
            g = next(i for i, line in enumerate(lines) if line.startswith(GUARD))
            hit = any(lines[i].startswith("class ") for i in range(g + 1, len(lines)))
            self.assertEqual(want, hit)


if __name__ == "__main__":
    unittest.main()
