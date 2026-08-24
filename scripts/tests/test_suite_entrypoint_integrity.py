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

#: `git ls-files` lists what SHIPS, which is the right set for this rule (an untracked scratch test
#: is not shipped). But where git is absent — a source tarball, a minimal container — the right
#: behaviour is a VISIBLE SKIP, not a `FileNotFoundError` and not a silent change of which files the
#: rule covers (gemini). I said as much when declining the `Path.glob` swap; this is that fix.
try:
    subprocess.run(["git", "-C", str(REPO), "rev-parse", "--is-inside-work-tree"],
                   capture_output=True, check=True)
    HAS_GIT = True
except (subprocess.CalledProcessError, FileNotFoundError, OSError):
    HAS_GIT = False


_EXIT_NAMES = {"exit", "quit"}


def _statements(body):
    """Every node that EXECUTES when this block runs — NOT the bodies of nested `def`/`class`/
    `lambda` (agy) — as one BFS with no duplicate yields (gemini).

    `ast.walk` ignores scope, so a guard containing `def fail_fast(): sys.exit(1)` beside a
    harmless `configure()` read as EXITING and every later class was falsely reported dropped.
    Defining a function is not calling it.
    """
    todo = list(body)
    while todo:
        n = todo.pop(0)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield n
        todo.extend(ast.iter_child_nodes(n))


def _body_can_exit(node) -> bool:
    """True if this `if __name__ == '__main__':` block can terminate the interpreter.

    A guard that merely calls `configure()` does NOT end module execution, so classes defined
    after it are perfectly reachable — flagging them is a false positive (codex, local round).
    A guard that calls `unittest.main()`, `sys.exit(...)`, `exit(...)` or raises `SystemExit`
    does end it, and anything defined afterwards is silently dropped on direct execution.
    """
    for n in _statements(node.body):
        if isinstance(n, ast.Raise):
            exc = n.exc
            if isinstance(exc, ast.Call):
                exc = exc.func
            if isinstance(exc, ast.Name) and exc.id == "SystemExit":
                return True
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in {"main", "exit", "_exit"}:
                return True
            if isinstance(f, ast.Name) and f.id in _EXIT_NAMES:
                return True
    return False


def _is_main_guard(node) -> bool:
    if not isinstance(node, ast.If):
        return False
    t = node.test
    if not isinstance(t, ast.Compare) or len(t.ops) != 1 or not isinstance(t.ops[0], ast.Eq):
        return False
    for a, b in ((t.left, t.comparators[0]), (t.comparators[0], t.left)):
        if (isinstance(a, ast.Name) and a.id == "__name__"
                and isinstance(b, ast.Constant) and b.value == "__main__"):
            return True
    return False


def _module_level(body):
    """Statements that EXECUTE at module level, recursing into control flow but NOT into
    function or class bodies — a class nested in `if shutil.which("zsh"):` is defined at import,
    a class nested in `def f():` is not (kimi/agy/codex, local round)."""
    for n in body:
        yield n
        if isinstance(n, (ast.If, ast.Try)):
            for sub in (list(getattr(n, "body", [])) + list(getattr(n, "orelse", []))
                        + list(getattr(n, "finalbody", []))
                        + [s for h in getattr(n, "handlers", []) for s in h.body]):
                yield from _module_level([sub])
        elif isinstance(n, (ast.With, ast.For, ast.While)):
            yield from _module_level(list(n.body) + list(getattr(n, "orelse", [])))


def _defines_test_class(node) -> bool:
    if isinstance(node, ast.ClassDef):
        return True
    # `Late = type("Late", (unittest.TestCase,), {})` is an Assign, not a ClassDef.
    # `Late: type = type(...)` is an AnnAssign, not an Assign (codex, local round) — the broad
    # "type()-assigned classes" claim has to cover the annotated spelling too.
    if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Call):
        f = node.value.func
        if isinstance(f, ast.Name) and f.id == "type" and len(node.value.args) == 3:
            return True
    return False


def analyse(src, filename="<s>"):
    """(has_any_guard, exiting_guard_lineno_or_None, [(lineno, label), ...]).

    TWO SEPARATE QUESTIONS, because conflating them produced a false positive both ways:
      * has_any_guard closes the FAIL-OPEN — an unrecognized entrypoint used to make the file be
        skipped silently, which is how the single-quoted spelling slipped through.
      * exiting_guard is the boundary that actually DROPS later definitions. A guard that only
        calls `configure()` ends nothing, so definitions after it are reachable and flagging them
        is wrong (codex, local round).
    """
    tree = ast.parse(src, filename=filename)
    any_guard, guard_line = False, None
    for n in _module_level(tree.body):
        if _is_main_guard(n):
            any_guard = True
            if _body_can_exit(n):
                guard_line = n.lineno
                break
    if guard_line is None:
        return any_guard, None, []
    dropped = [(n.lineno, getattr(n, "name", None) or "type()-assigned class")
               for n in _module_level(tree.body)
               if _defines_test_class(n) and n.lineno > guard_line]
    return any_guard, guard_line, dropped


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


@unittest.skipUnless(HAS_GIT, "needs a git checkout — the census lists TRACKED files")
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
            text = path.read_text(encoding="utf-8")
            try:
                ast.parse(text, filename=str(path))
            except SyntaxError as exc:                       # a bare traceback names nothing useful
                raise AssertionError(f"{rel}: cannot parse: {exc}") from exc
            any_guard, line, dropped = analyse(text, rel)
            if not any_guard:
                out.append(f"{rel}: NO recognized `if __name__ == \"__main__\":` entrypoint — a "
                           f"class appended later would be dropped and this guard would not see it")
                continue
            if dropped:
                out.append(f"{rel}: {len(dropped)} definition(s) after the EXITING entrypoint at "
                           f":{line} — " + "; ".join(f"{ln}: {name}" for ln, name in dropped))
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
        must_flag.update({
            "in_if.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                         'if True:\n    class B(unittest.TestCase): pass\n'),
            "in_try.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                          'try:\n    class B(unittest.TestCase): pass\n'
                          'except Exception:\n    pass\n'),
            # `type()` builds a class without a ClassDef node.
            "type_assign.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                               'L = type("L", (unittest.TestCase,), {})\n'),
        })
        for name, body in must_flag.items():
            with self.subTest(spelling=name):
                self.assertNotEqual([], self._offenders([write(name, body)]),
                                    f"{name} must be flagged")

        # ── SHAPES FOUND BY THE LOCAL REVIEW ROUND (codex / agy / kimi, all three arms) ──
        # A class NESTED in a module-level `if`/`try` after the entrypoint is still defined at
        # import and still DROPPED on direct execution — and this repo already uses that shape for
        # capability skips (`if shutil.which("zsh"):`). The old walk read only `tree.body`.

        must_not_flag = {
            # A working entrypoint WRAPPED in `try:` is found by recursing — the old top-level-only
            # walk reported "NO recognized entrypoint" and, with missing-entrypoint now an offence,
            # would have RED a file where nothing is dropped.
            "wrapped.py": ('class E(unittest.TestCase): pass\ntry:\n'
                           '    if __name__ == "__main__":\n        unittest.main()\n'
                           'except SystemExit:\n    pass\n'),
            # A nested `def` containing `sys.exit` is a DEFINITION, not a call — the guard runs
            # `configure()` and returns, so the class after it is reachable. `ast.walk` ignores
            # scope and flagged this, redding CI on legitimate code (agy, local round).
            "nested_def.py": ('if __name__ == "__main__":\n    def fail_fast():\n'
                              '        sys.exit(1)\n    configure()\n'
                              'class Valid(unittest.TestCase): pass\n'),
            # An INNOCUOUS first guard ends nothing, so classes after it are reachable. Treating the
            # first guard as the boundary regardless of whether it exits false-flags this.
            "innocuous_first.py": ('if __name__ == "__main__":\n    configure()\n'
                                   'class Included(unittest.TestCase): pass\n'
                                   'if __name__ == "__main__":\n    unittest.main()\n'),
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
