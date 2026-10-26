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
import sys
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
#: `<owner>.main()` ENDS the run only for a real test runner; `<owner>.exit()` only for the
#: modules that actually terminate the interpreter. Both were `any attribute with that name`
#: until `helper.main()` false-flagged a valid suite (codex, PR #78).
#: `unittest` ONLY. `pytest.main([__file__])` RE-IMPORTS the target as a module, so a
#: `def test_late()` written after the guard is defined during that import and collected
#: normally — nothing is dropped, and flagging it is a FALSE POSITIVE (codex, PR #78).
#: `unittest.main()` is different in exactly the way that matters: it collects from the
#: already-populated `__main__`, so whatever has not been defined yet never runs.
#: The two runners were treated alike because both are spelled `<mod>.main()`; the spelling is
#: the only thing they share.
_RUNNER_OWNERS = {"unittest"}
_EXIT_OWNERS = {"sys", "os"}


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
    # A GUARD THAT HANDS CONTROL TO PYTEST DROPS NOTHING, however it exits. `raise
    # SystemExit(pytest.main([__file__]))` does terminate — but pytest RE-IMPORTS the file first,
    # so every later definition exists and is collected. The exit is real and the drop is not, and
    # keying on the exit alone reported definitions that run (codex, PR #78).
    for n in _statements(node.body):
        f = getattr(n, "func", None)
        if (isinstance(n, ast.Call) and isinstance(f, ast.Attribute) and f.attr == "main"
                and isinstance(f.value, ast.Name) and f.value.id == "pytest"):
            return False
    for n in _statements(node.body):
        if isinstance(n, ast.Raise):
            exc = n.exc
            if isinstance(exc, ast.Call):
                exc = exc.func
            if isinstance(exc, ast.Name) and exc.id == "SystemExit":
                return True
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                owner = f.value.id if isinstance(f.value, ast.Name) else None
                # NOT every attribute named `main` (codex, PR #78). A module whose FIRST guard
                # calls `helper.main()` — a helper that returns — followed by its test classes and
                # a later real `unittest.main()` guard had those classes reported as dropped, which
                # reds CI on a valid file. `helper.main()` ends nothing.
                #
                # Narrow deliberately, and note which way the residual error runs: an unrecognised
                # runner now means we do NOT treat the guard as exiting, so later definitions go
                # unreported. That is the quieter failure, and it is bounded — every suite in this
                # tree uses `unittest.main()`. Being broad instead fails LOUD on correct code.
                if f.attr == "main" and owner in _RUNNER_OWNERS:
                    return True
                if f.attr in {"exit", "_exit"} and owner in _EXIT_OWNERS:
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
        # `ast.TryStar` (`except*`, 3.11+) is NOT a subclass of `ast.Try` — verified. Missing it
        # cut both ways: a guard inside `except*` made the file report "NO recognized entrypoint",
        # which is an OFFENCE now, redding the required validate job (which runs 3.12); and a class
        # after the guard inside one went unreported while the byte-near-identical plain `except`
        # fixture is already pinned. `getattr` keeps the 3.9 leg from raising.
        # A STATICALLY DEAD BRANCH EXECUTES NOTHING. `if False:` wrapping the entrypoint made
        # `analyse` report a working exiting guard, so a file that runs ZERO tests on direct
        # execution was approved while discovery ran its classes — the exact divergence this suite
        # exists to catch (codex, PR #78). Only a literal falsy CONSTANT is treated as dead;
        # anything evaluable at runtime is still walked, so a capability check like
        # `if shutil.which("zsh"):` keeps its current behaviour.
        # ...and `while False:` is dead by exactly the same argument. Special-casing `if` alone
        # was one spelling of a family (codex, PR #78) — the property is "a literal falsy test",
        # not "an If node". A `while`'s `orelse` runs when the loop ends normally, which for a
        # never-entered loop is immediately, so it is walked in both cases.
        # ...in BOTH polarities. Handling only a falsy test left `if True: … else: <guard>` —
        # where the ELSE is the dead half — walking both branches and counting the dead guard
        # (codex, PR #78). The live half is the body when the constant is truthy and the `orelse`
        # when it is falsy; for `while True:` the `orelse` is the unreachable one, which the same
        # expression gives.
        if isinstance(n, (ast.If, ast.While)) and isinstance(n.test, ast.Constant):
            live = list(n.body) if n.test.value else list(getattr(n, "orelse", []))
            yield from _module_level(live)
            continue
        if isinstance(n, (ast.If, ast.Try, getattr(ast, "TryStar", ()))):
            for sub in (list(getattr(n, "body", [])) + list(getattr(n, "orelse", []))
                        + list(getattr(n, "finalbody", []))
                        + [s for h in getattr(n, "handlers", []) for s in h.body]):
                yield from _module_level([sub])
        elif isinstance(n, (ast.With, ast.For, ast.While)):
            yield from _module_level(list(n.body) + list(getattr(n, "orelse", [])))


def _defines_test_class(node) -> bool:
    if isinstance(node, ast.ClassDef):
        return True
    # A pytest-style module-level `def test_late(): ...` is dropped by direct execution exactly as
    # a class is, and `_body_can_exit` already recognises `pytest.main()` as a runner — so
    # accepting that runner while ignoring the definitions it collects was an inconsistency, not a
    # scope decision (codex, PR #78).
    # ...and `load_tests`, the standard unittest discovery hook. Direct execution runs the runner
    # before the hook exists while discovery imports the module and then calls it, so a late
    # `load_tests` is exactly the direct/discovery divergence this suite is about — it simply is
    # not spelled `test*` (codex, PR #78).
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name.startswith("test") or node.name == "load_tests"):
        return True
    # `Late = type("Late", (unittest.TestCase,), {})` is an Assign, not a ClassDef.
    # `Late: type = type(...)` is an AnnAssign, not an Assign (codex, local round) — the broad
    # "type()-assigned classes" claim has to cover the annotated spelling too.
    #
    # ANY call, not just the `type` builtin. `Late = make_test_case()` is a factory-generated case
    # (codex, PR #78) and no static rule can tell what a call returns — recognizing only `type(...)`
    # let the identical hazard through under a different spelling, which is the blacklist shape this
    # whole suite is about.
    #
    # This is a deliberate OVER-APPROXIMATION of the hazard, not a proof. It reports any
    # call-assigned name past the entrypoint, including one that builds no test case at all — such
    # a name is dead on direct execution and worth naming, but the report says "definition" about
    # something that may not be one. The trade is paid for by measurement, not by argument: no
    # shipped test file has ANY statement after its entrypoint, so nothing in the tree is admitted
    # today, and the sweep is green. An earlier draft of this comment called the widening "SOUND"
    # and "never a false alarm" — it is neither, and it false-flagged in-guard assignments until
    # `analyse` was fixed to skip the guard's own body.
    #
    # STILL ESCAPING, ticketed on COREDEV-2760 rather than chased with more spellings:
    # `Late = SomeBase` (an alias binds no new class), `Late = type(...) if c else Other`, and
    # `for n, c in make_cases(): globals()[n] = c`. `globals()["Late"] = make_test_case()` IS
    # caught, because its right-hand side is directly a call.
    if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Call):
        return True
    return False


def _exclusive_of(tree, guard):
    """Line spans of branches that CANNOT execute in the same run as `guard`'s branch.

    A platform-gated module puts a Windows class and runner in an `if`'s body and the Unix pair
    in its `orelse`. `_module_level` flattens both, so the first branch's runner appeared to
    precede the OTHER branch's class and a valid suite was reported as dropping it (codex,
    PR #78). Only `If` is modelled: a `try` handler is not mutually exclusive with its body in
    the way that matters here, since the body runs first either way.
    """
    parent = {}
    for p in ast.walk(tree):
        for child in ast.iter_child_nodes(p):
            parent[child] = p
    spans, node = [], guard
    while node in parent:
        p = parent[node]
        if isinstance(p, ast.If):
            other = p.orelse if any(node is st for st in p.body) else (
                p.body if any(node is st for st in p.orelse) else [])
            spans += [(st.lineno, getattr(st, "end_lineno", st.lineno)) for st in other]
        node = p
    return spans


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
    any_guard, guard_line, guard_end, guard_node = False, None, None, None
    for n in _module_level(tree.body):
        if _is_main_guard(n):
            any_guard = True
            if _body_can_exit(n):
                guard_line, guard_end, guard_node = (
                    n.lineno, getattr(n, "end_lineno", n.lineno), n)
                break
    if guard_line is None:
        return any_guard, None, []
    excluded = _exclusive_of(tree, guard_node)
    # PAST THE GUARD'S OWN BODY, not merely past its first line. The guard block runs, so what
    # is INSIDE it is reachable — `if __name__ == "__main__": argv = prepare_argv();
    # unittest.main(argv=argv)` had `argv` reported as dropped, which would red CI on ordinary
    # code (codex, PR #78). The narrow `type(...)` predicate hid this scope bug; widening the
    # predicate exposed it rather than causing it.
    dropped = [(n.lineno, getattr(n, "name", None) or "call-assigned definition")
               for n in _module_level(tree.body)
               if _defines_test_class(n) and n.lineno > guard_end
               and not any(lo <= n.lineno <= hi for lo, hi in excluded)]
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
    # DERIVED FROM THE TREE, not from two hard-coded directories. A `test_*.py` added under a
    # second MCP package — or any new `*/tests/` directory — was invisible here while the breadth
    # control still passed on the existing count and its three required paths (codex, PR #78).
    # That is the same enumerate-instead-of-derive narrowing this suite exists to catch, in the
    # census of the suite itself.
    # NUL-DELIMITED. `.split()` on newline-delimited output breaks any tracked path containing a
    # space into fragments, and `_offenders` then fails reading paths that do not exist — the gate
    # crashes instead of checking the suite (codex, PR #78).
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", "*/tests/test_*.py", "tests/test_*.py"],
        capture_output=True, text=True, check=True).stdout.split("\0")
    return [REPO / rel for rel in out if rel]


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
        # THE DERIVATION MUST REACH EVERY `*/tests/` DIRECTORY, not the two it was written
        # against. A named-directory census stayed green on its count and its three required
        # paths while a new package's suite went unswept (codex, PR #78) — so assert the census
        # equals what the tree actually holds, which is the only form that cannot drift.
        every = {p for p in subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z", "*test_*.py"],
            capture_output=True, text=True, check=True).stdout.split("\0")
            if p and ("/tests/" in p or p.startswith("tests/"))}
        self.assertEqual(every, found,
                         "the census and the tree disagree: "
                         f"missing={sorted(every - found)} extra={sorted(found - every)}")

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
            # The narrowing must not lose the shapes that DO terminate. `sys.exit(main())` is the
            # one measured earlier to be skipped by a naive "requires `*.main()`" rule.
            "sys_exit_main.py": ('if __name__ == "__main__":\n    sys.exit(main())\n'
                                 'class L(unittest.TestCase): pass\n'),
            "os_exit.py": ('if __name__ == "__main__":\n    os._exit(0)\n'
                           'class L(unittest.TestCase): pass\n'),
            # No entrypoint at all is now an OFFENCE, not a skip: a skip is what let the
            # single-quoted spelling through.
            "none.py": "class OnlyThis: pass\n",
            # A guard inside a STATICALLY DEAD branch is not an entrypoint: direct execution skips
            # it and runs zero tests while discovery runs the class. Reporting a working entrypoint
            # there approved the exact divergence this suite exists to catch.
            "dead_branch.py": ('class T(unittest.TestCase): pass\nif False:\n'
                               '    if __name__ == "__main__":\n        unittest.main()\n'),
            "dead_zero.py": ('class T(unittest.TestCase): pass\nif 0:\n'
                             '    if __name__ == "__main__":\n        unittest.main()\n'),
            # `while False:` is dead by the same argument — the property is a literal falsy TEST,
            # not an `If` node, and special-casing `if` alone was one spelling of a family.
            "dead_while.py": ('class T(unittest.TestCase): pass\nwhile False:\n'
                              '    if __name__ == "__main__":\n        unittest.main()\n'),
            # ...and the dead half of a constant-TRUE test is the `else`, which the falsy-only
            # rule walked and counted.
            "dead_else.py": ('class T(unittest.TestCase): pass\nif True:\n    pass\nelse:\n'
                             '    if __name__ == "__main__":\n        unittest.main()\n'),
        }
        must_flag.update({
            "in_if.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                         'if True:\n    class B(unittest.TestCase): pass\n'),
            "in_try.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                          'try:\n    class B(unittest.TestCase): pass\n'
                          'except Exception:\n    pass\n'),
            # ...but a class in the SAME branch, after that branch's runner, is still dropped —
            # the branch fix must not become a blanket pass for anything inside an `if`.
            "same_branch.py": ('import sys\nif sys.platform == "win32":\n'
                               '    if __name__ == "__main__":\n        unittest.main()\n'
                               '    class Late(unittest.TestCase): pass\n'
                               'else:\n    pass\n'),
            # `load_tests` is the standard unittest discovery hook - dropped exactly as a class
            # is, and not spelled test*.
            "load_tests.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                              'def load_tests(loader, tests, pattern):\n    return tests\n'),
            # A test FUNCTION after a UNITTEST runner is dropped exactly as a class is.
            "async_func.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                              'async def test_late():\n    assert True\n'),
            "sync_func.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                             'def test_late():\n    assert True\n'),
            # `type()` builds a class without a ClassDef node.
            "type_assign.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                               'L = type("L", (unittest.TestCase,), {})\n'),
            # A FACTORY call returns one just the same, and nothing static can tell that it does
            # (codex, PR #78). Recognizing only the `type` builtin left this identical hazard open.
            "factory.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                           'Late = make_test_case()\n'),
            "factory_annotated.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                                     'Late: type = mod.make_test_case("Late")\n'),
        })
        # `except*` PARSES ONLY ON 3.11+. The fixture is a STRING parsed at runtime, so the module
        # itself imports anywhere; but on macOS stock 3.9 `ast.parse` would raise and red this cell
        # on a valid tree. CI's validate job runs 3.12, where both spellings parse and both are
        # exercised. Gate the fixture, not the fix: `getattr(ast, "TryStar", ())` in the walk is
        # already 3.9-safe.
        if sys.version_info >= (3, 11):
            must_flag["in_trystar.py"] = ('if __name__ == "__main__":\n    unittest.main()\n'
                                          'try:\n    class B(unittest.TestCase): pass\n'
                                          'except* Exception:\n    pass\n')
            must_not_flag_star = ('class E(unittest.TestCase): pass\ntry:\n'
                                  '    if __name__ == "__main__":\n        unittest.main()\n'
                                  'except* SystemExit:\n    pass\n')
        for name, body in must_flag.items():
            with self.subTest(spelling=name):
                self.assertNotEqual([], self._offenders([write(name, body)]),
                                    f"{name} must be flagged")
        if sys.version_info >= (3, 11):
            with self.subTest(spelling="wrapped_star.py"):
                self.assertEqual([], self._offenders([write("wrapped_star.py",
                                                            must_not_flag_star)]),
                                 "a guard inside `except*` must be RECOGNIZED, not reported as a "
                                 "missing entrypoint")

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
            # PYTEST IS NOT UNITTEST. `pytest.main([__file__])` re-imports the file, so definitions
            # after the guard ARE collected — nothing is dropped and reporting them reds valid
            # code. These two were in the must-FLAG set for two rounds on the strength of the
            # shared `.main()` spelling.
            "pytest_main.py": ('if __name__ == "__main__":\n'
                               '    raise SystemExit(pytest.main([__file__]))\n'
                               'class L(unittest.TestCase): pass\n'),
            "pytest_func.py": ('if __name__ == "__main__":\n    pytest.main([__file__])\n'
                               'def test_late():\n    assert True\n'),
            # ...but a RUNTIME-evaluable condition is not dead, and this tree uses that shape for
            # capability skips. Only a literal falsy constant counts, or the fix would blind the
            # walk to every conditional block.
            "live_cond.py": ('import shutil\nif shutil.which("zsh"):\n'
                             '    class Z(unittest.TestCase): pass\n'
                             'if __name__ == "__main__":\n    unittest.main()\n'),
            # ...and a runtime-evaluable `while` is not dead either.
            "live_while.py": ('import shutil\nwhile shutil.which("zsh"):\n    break\n'
                              'if __name__ == "__main__":\n    unittest.main()\n'),
            # ...and the LIVE half of a constant-true test is the body, which must still be walked
            # or the fix trades one blind spot for another.
            "live_true_body.py": ('class T(unittest.TestCase): pass\nif True:\n'
                                  '    if __name__ == "__main__":\n        unittest.main()\n'),
            # A non-test helper defined after the guard is dead, but it is not a dropped TEST and
            # the sweep's message would be wrong about it. Only `test`-named functions count.
            "helper_after.py": ('if __name__ == "__main__":\n    unittest.main()\n'
                                'def _summarize():\n    return 1\n'),
            # INSIDE the guard's own body. The block RUNS, so these are reachable — reporting them
            # would red CI on ordinary code, and it did until `analyse` stopped comparing against
            # the guard's FIRST line (codex, PR #78). Both spellings occur in real suites: setting
            # up argv before the runner, and doing work after `unittest.main(exit=False)`.
            "in_guard_before.py": ('if __name__ == "__main__":\n    argv = prepare_argv()\n'
                                   '    unittest.main(argv=argv)\n'),
            "in_guard_after.py": ('if __name__ == "__main__":\n    unittest.main(exit=False)\n'
                                  '    report = summarize()\n'),
            # A first guard calling a HELPER named `main` ends nothing, so the classes after it are
            # reachable — and the real runner comes later (codex, PR #78). Treating every `.main`
            # attribute as terminating reported `Real` as dropped and would red CI.
            "helper_main_first.py": ('if __name__ == "__main__":\n    helper.main()\n'
                                     'class Real(unittest.TestCase): pass\n'
                                     'if __name__ == "__main__":\n    unittest.main()\n'),
            # A CLASS NESTED inside a function after the entrypoint is not module-level, and the
            # lexical rule's `startswith("class ")` could not tell the difference.
            "nested.py": ('class E: pass\n\n\nif __name__ == "__main__":\n    unittest.main()\n'
                          '\n\ndef f():\n    class Inner: pass\n    return Inner\n'),
            # MUTUALLY EXCLUSIVE BRANCHES. A platform-gated module defines one class + runner per
            # branch; on either platform the direct and discovery behaviour agree, so nothing is
            # dropped. Flattening the branches made the first runner appear to precede the other
            # branch's class and reported a valid suite as broken (codex, PR #78).
            "platform_split.py": ('import sys\nif sys.platform == "win32":\n'
                                  '    class WinT(unittest.TestCase): pass\n'
                                  '    if __name__ == "__main__":\n        unittest.main()\n'
                                  'else:\n'
                                  '    class NixT(unittest.TestCase): pass\n'
                                  '    if __name__ == "__main__":\n        unittest.main()\n'),
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
