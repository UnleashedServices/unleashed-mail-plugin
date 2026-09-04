#!/usr/bin/env python3
"""COREDEV-2810 — the Python 3.9 floor, enforced where it actually bites.

`.trunk/configs/.mypy.ini` carried `python_version = 3.9` and a comment claiming that this made
mypy "reject 3.10+ constructs at lint time". It did neither. The pinned mypy 2.3.1 REFUSES 3.9:
on the command line that is a hard error, and from a config file it emits a note and continues at
its own default. Measured before the fix — with the floor set, a PEP-604 annotation type-checked
as "Success: no issues found". An unenforced floor advertised as enforced is worse than an
unstated one, because it stops anyone looking for the real check.

The real check is here, and it is not a restatement of the byte-compile job. `int | None` is
VALID 3.9 SYNTAX, so `py_compile` accepts it; it fails only when Python EVALUATES the annotation,
which happens at function-definition time unless the module opts into postponed evaluation. That
is precisely the gap between what CI's py39 job can see and what breaks on a stock macOS runtime.
"""

from __future__ import annotations

import ast
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
CI = REPO / ".github/workflows/plugin-ci.yml"
MYPY_INI = REPO / ".trunk/configs/.mypy.ini"


def _py39_compiled_files() -> list[pathlib.Path]:
    """DERIVED FROM CI, never hand-listed. A hand-listed set is narrowed by the same edit that
    adds a file to the job, so the file most likely to be missing is the one just added.
    """
    match = re.search(r"python3 -m py_compile ([^\n]+)", CI.read_text(encoding="utf-8"))
    assert (
        match is not None
    ), "the py39 byte-compile step is gone; this check has no file set"
    found: list[pathlib.Path] = []
    for token in match.group(1).split():
        if token.startswith("-"):
            continue
        if "*" in token:
            found.extend(sorted(REPO.glob(token)))
        else:
            found.append(REPO / token)
    return [p for p in found if p.is_file()]


def _runtime_evaluated_unions(source: str) -> list[int]:
    """Lines where a PEP-604 union sits in an annotation Python evaluates at runtime.

    Scoped to ANNOTATIONS deliberately. A bare `a | b` elsewhere is ordinary bitwise or, and a
    checker that cannot tell them apart would be turned off the first time it cried wolf.
    """
    if "from __future__ import annotations" in source:
        # Postponed evaluation: every annotation is a string at runtime, so 3.9 never evaluates it.
        return []
    tree = ast.parse(source)
    lines: list[int] = []

    def scan(node: ast.AST) -> None:
        lines.extend(
            inner.lineno
            for inner in ast.walk(node)
            if isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.BitOr)
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                if arg.annotation is not None:
                    scan(arg.annotation)
            for maybe in (args.vararg, args.kwarg):
                if maybe is not None and maybe.annotation is not None:
                    scan(maybe.annotation)
            if node.returns is not None:
                scan(node.returns)
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            scan(node.annotation)
    return sorted(set(lines))


class TheRuntimeFloorHoldsOnEveryFileCICompilesOnThreeNine(unittest.TestCase):
    def test_no_runtime_evaluated_pep604_union_in_a_load_bearing_script(self):
        offenders = []
        for path in _py39_compiled_files():
            hits = _runtime_evaluated_unions(path.read_text(encoding="utf-8"))
            if hits:
                offenders.append(f"{path.relative_to(REPO)}:{','.join(map(str, hits))}")
        self.assertEqual(
            [],
            offenders,
            "PEP-604 in an annotation Python evaluates at runtime is a TypeError on 3.9, and "
            "byte-compiling cannot see it. Add `from __future__ import annotations`, or use "
            "typing.Optional/Union",
        )

    def test_the_checker_detects_what_it_claims_to(self):
        """A checker whose positive case is never exercised is a checker nobody has run."""
        # DISTINCT LINES PER POSITION, so this proves the ARGUMENT and the RETURN are both
        # scanned. Put on one line they collapse to a single entry and either scan alone passes.
        breaks = (
            "MODULE_ALIAS: int | None = None\n"
            "\n\n"
            "def f(\n"
            "    x: int | None,\n"
            ") -> str | None:\n"
            "    return None\n"
        )
        self.assertEqual([1, 5, 6], _runtime_evaluated_unions(breaks))
        postponed = "from __future__ import annotations\n" + breaks
        self.assertEqual([], _runtime_evaluated_unions(postponed))
        bitwise = "FLAGS = 1 | 2\n\n\ndef g(x: int) -> int:\n    return x | 4\n"
        self.assertEqual(
            [], _runtime_evaluated_unions(bitwise), "ordinary bitwise or is not a union"
        )

    def test_the_file_set_is_derived_and_not_empty(self):
        files = _py39_compiled_files()
        self.assertGreater(len(files), 10, "the derivation lost CI's file list")


class TheConfiguredTargetIsOneThePinnedMypyAccepts(unittest.TestCase):
    """The defect's own shape: a config naming a version mypy refuses is a NOTE, not an error, so
    it survives every green run. This asserts the acceptance rather than the spelling, so the next
    mypy bump that narrows the supported range fails here instead of silently un-targeting.
    """

    @staticmethod
    def _mypy() -> str | None:
        found = shutil.which("mypy")
        if found:
            return found
        candidates = sorted(
            pathlib.Path.home().glob(".cache/trunk/tools/mypy/*/bin/mypy")
        )
        return str(candidates[-1]) if candidates else None

    def test_the_pinned_mypy_does_not_refuse_the_configured_version(self):
        mypy = self._mypy()
        if mypy is None:
            self.skipTest(
                "no materialised mypy to interrogate; trunk-check covers this in CI"
            )
        # `addCleanup`, not `enterContext`: the latter is 3.11+, and this suite has to stay
        # runnable on the oldest interpreter anyone points at it.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        probe = pathlib.Path(tmp.name)
        target = probe / "probe.py"
        target.write_text("x: int = 1\n", encoding="utf-8")
        completed = subprocess.run(
            [mypy, "--config-file", str(MYPY_INI), str(target)],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertNotIn(
            "is not supported",
            completed.stdout + completed.stderr,
            "the configured python_version is one this mypy refuses, so it is silently ignored "
            "and the target is whatever mypy defaults to",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
