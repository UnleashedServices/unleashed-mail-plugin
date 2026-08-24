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

import ast
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _entrypoint_lineno(tree: "ast.Module") -> "int | None":
    """Line of the module-level `if __name__ == "__main__":`, or None if the file has none.

    STRUCTURAL, not lexical (codex, PR #78). The first version matched the literal string
    `if __name__ == "__main__":`, so `if __name__ == '__main__':`, or a space around `==`, produced
    no match at all — and a no-match SKIPPED the file, leaving a class appended after its entrypoint
    silently dropped while this guard reported OK. A guard against a narrowing defect that was
    itself narrowed; measured on a planted offender, canonical spelling -> FAILED, single-quoted
    spelling -> OK.

    Deliberately does NOT require a `unittest.main()` call inside the block: measured, that
    tightening skips `if __name__ == "__main__": sys.exit(main())`, which is a real hazard the
    lexical rule caught. A freebie that loses coverage is a regression.
    """
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        t = node.test
        if not isinstance(t, ast.Compare) or len(t.ops) != 1 or not isinstance(t.ops[0], ast.Eq):
            continue
        left, right = t.left, t.comparators[0]
        for a, b in ((left, right), (right, left)):
            if (isinstance(a, ast.Name) and a.id == "__name__"
                    and isinstance(b, ast.Constant) and b.value == "__main__"):
                return node.lineno
    return None


def _test_files() -> "list[Path]":
    """DERIVED from git, never enumerated — the lesson this whole PR is about.

    TRACKED, deliberately, and not `Path.glob` (gemini proposed the swap, PR #78). The rule is
    about files that SHIP, and tracked is exactly that set: a developer's untracked scratch
    `test_probe.py` is not shipped and should not red their suite. The boundary is real and worth
    naming — a new test file is invisible to this guard until it is `git add`-ed, which is the same
    staging rule the callers manifest already follows. The git dependency is not new: this suite
    shells out to git in several other modules and CI always runs in a checkout.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "scripts/tests/test_*.py",
         "mcp/review-synthesizer/tests/test_*.py"],
        capture_output=True, text=True, check=True).stdout.split()
    return [REPO / rel for rel in out]


class NoTestClassIsDefinedAfterUnittestMain(unittest.TestCase):
    def _offenders(self, paths):
        """Shared by the sweep and its own control, so the control tests the REAL predicate.

        The first version of the control re-implemented this inline; proven byte-identical and
        still green under both the old and new rules, so it certified nothing.
        """
        out = []
        for path in paths:
            try:                                          # scratch fixtures live outside REPO
                rel = path.relative_to(REPO).as_posix()
            except ValueError:
                rel = path.name
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:                       # a bare traceback names nothing useful
                raise AssertionError(f"{rel}: cannot parse: {exc}") from exc
            line = _entrypoint_lineno(tree)
            if line is None:
                out.append(f"{rel}: NO recognized `if __name__ == \"__main__\":` entrypoint — a "
                           f"class appended later would be dropped and this guard would not see it")
                continue
            after = [f"{n.lineno}: class {n.name}" for n in tree.body
                     if isinstance(n, ast.ClassDef) and n.lineno > line]
            if after:
                out.append(f"{rel}: {len(after)} class(es) after the entrypoint at :{line} — "
                           + "; ".join(after))
        return out

    def test_every_suite_declares_its_classes_before_the_entrypoint(self):
        offenders = self._offenders(_test_files())
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
        """The rule's own control — and it calls `_offenders`, the SAME predicate the sweep uses.

        An earlier version re-implemented the check inline. That version was byte-identical to the
        lexical rule and stayed green under BOTH the old and the new one, so it certified nothing —
        the exact defect this suite exists to catch, one level up.

        Every spelling below is a REAL hazard: each drops the trailing class on direct execution.
        """
        import shutil, tempfile
        scratch = Path(tempfile.mkdtemp(prefix="entrypoint-control."))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)

        def write(name, body):
            p = scratch / name
            p.write_text(body, encoding="utf-8")
            return p

        must_flag = {
            "dq.py": 'if __name__ == "__main__":\n    unittest.main()\n\n\nclass L: pass\n',
            # THE ONE THE LEXICAL RULE MISSED — single quotes.
            "sq.py": "if __name__ == '__main__':\n    unittest.main()\n\n\nclass L: pass\n",
            "spaced.py": 'if __name__  ==  "__main__":\n    unittest.main()\n\n\nclass L: pass\n',
            "reversed.py": 'if "__main__" == __name__:\n    unittest.main()\n\n\nclass L: pass\n',
            # A guard block that is not unittest.main() is STILL an entrypoint, and a class after it
            # is still dropped. Requiring a `main()` call here would skip this — measured.
            "sysexit.py": 'if __name__ == "__main__":\n    raise SystemExit(0)\n\n\nclass L: pass\n',
            # No entrypoint at all is now an OFFENCE, not a skip: a skip is what let the
            # single-quoted spelling through.
            "none.py": "class OnlyThis: pass\n",
        }
        for name, body in must_flag.items():
            with self.subTest(spelling=name):
                self.assertNotEqual([], self._offenders([write(name, body)]),
                                    f"{name} must be flagged")

        must_not_flag = {
            "ok.py": 'class E: pass\n\n\nif __name__ == "__main__":\n    unittest.main()\n',
            # A CLASS NESTED inside a function after the entrypoint is not module-level, and the
            # lexical rule's `startswith("class ")` could not tell the difference.
            "nested.py": ('class E: pass\n\n\nif __name__ == "__main__":\n    unittest.main()\n'
                          '\n\ndef f():\n    class Inner: pass\n    return Inner\n'),
        }
        for name, body in must_not_flag.items():
            with self.subTest(spelling=name):
                self.assertEqual([], self._offenders([write(name, body)]),
                                 f"{name} must NOT be flagged")

    def test_an_unparseable_file_fails_by_name(self):
        """`ast.parse` raises where the lexical read could not. Fail with the path, not a traceback."""
        import shutil, tempfile
        scratch = Path(tempfile.mkdtemp(prefix="entrypoint-broken."))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        bad = scratch / "broken.py"
        bad.write_text("def f(:\n", encoding="utf-8")
        with self.assertRaises(AssertionError) as caught:
            self._offenders([bad])
        self.assertIn("broken.py", str(caught.exception))
        self.assertIn("cannot parse", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
