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

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
PY39_JOB = "py39-smoke"
CI = REPO / ".github/workflows/plugin-ci.yml"
MYPY_INI = REPO / ".trunk/configs/.mypy.ini"


def _py_compile_tokens(workflow: dict, job_name: str) -> list[str]:
    """The file tokens of `job_name`'s single py_compile step. Separated from disk so the scoping
    can be tested on a workflow whose two lists DIFFER — on the real one they are identical, which
    is exactly why an unscoped search passed while reading the wrong job.
    """
    job = (workflow.get("jobs") or {}).get(job_name)
    assert job is not None, f"the `{job_name}` job is gone; this check has no file set"
    commands = [
        step["run"]
        for step in job.get("steps", [])
        if isinstance(step.get("run"), str) and "py_compile" in step["run"]
    ]
    assert len(commands) == 1, (
        f"expected exactly one py_compile step in `{job_name}`, found {len(commands)} — "
        "a census that picks one of several is back to guessing"
    )
    # CONTINUATIONS FOLDED FIRST. `[^\n]+` stops at the first newline, so the moment the py39
    # command is wrapped with a trailing backslash — the natural thing to do to a 500-character
    # line — the census silently keeps the first fragment and drops the rest, while the suite
    # stays green. That is the same "derivation reading less than it claims" defect this
    # function was just repaired for, one level down (PR #85 adversarial pass).
    folded = re.sub(r"\\\n\s*", " ", commands[0])
    match = re.search(r"python3 -m py_compile ([^\n]+)", folded)
    assert match is not None, "the py39 byte-compile command changed shape"
    return [t for t in match.group(1).split() if not t.startswith("-")]


def _py39_compiled_files() -> list[pathlib.Path]:
    """DERIVED FROM THE py39-smoke JOB — never hand-listed, and never "the first match in the file".

    A hand-listed set is narrowed by the very edit that adds a file to the job, so the file most
    likely to be missing is the one just added. The first version of this derivation had the same
    disease in a subtler form: an unscoped `re.search` over the whole workflow takes the EARLIEST
    `py_compile` command, which belongs to the Python 3.12 `validate` step, not `py39-smoke`. The
    two lists are identical today, so it passed — and if the 3.9 list were ever updated on its own,
    which is precisely the drift this census exists to catch, the new file would go unchecked
    (codex, PR #85).
    """
    workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
    found: list[pathlib.Path] = []
    for token in _py_compile_tokens(workflow, PY39_JOB):
        if "*" in token:
            found.extend(sorted(REPO.glob(token)))
        else:
            found.append(REPO / token)
    return [p for p in found if p.is_file()]


# Names whose presence makes a `|` a TYPE union rather than arithmetic. `None` is the strongest
# signal of all — `x | None` is never a bitwise or, because NoneType implements no `__or__`.
_TYPE_NAMES = frozenset(
    {
        "Any",
        "Callable",
        "Dict",
        "FrozenSet",
        "Iterable",
        "Iterator",
        "List",
        "Mapping",
        "Optional",
        "Sequence",
        "Set",
        "Tuple",
        "Union",
        "bool",
        "bytearray",
        "bytes",
        "complex",
        "dict",
        "float",
        "frozenset",
        "int",
        "list",
        "object",
        "set",
        "str",
        "tuple",
        "type",
    }
)


def _looks_like_a_type(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in _TYPE_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _TYPE_NAMES
    if isinstance(node, ast.Subscript):
        return _looks_like_a_type(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _looks_like_a_type(node.left) or _looks_like_a_type(node.right)
    return False


def _runtime_evaluated_unions(source: str) -> list[int]:
    """Lines where a PEP-604 union is EVALUATED at runtime, and so fails on Python 3.9.

    THE FUTURE IMPORT IS NOT A BLANKET EXEMPTION, and treating it as one made this check inert.
    The first version returned `[]` for any module importing postponed annotations — and every
    file in the census imports it, so the checker inspected 0 of 20 files while reporting success
    (codex, PR #85). Postponed evaluation covers ANNOTATIONS only. `Alias = int | None` at module
    level, or `isinstance(v, int | str)`, is evaluated exactly as before and raises TypeError on
    3.9 while `py_compile` accepts it, which is the whole gap this check exists to close.

    So the exemption is scoped to the nodes it actually covers, and every other position is scanned
    regardless. Outside annotations a bare `a | b` is ordinary arithmetic, so those sites are
    reported only when an operand is recognisably a TYPE — a checker that cannot tell the two apart
    gets switched off the first time it cries wolf.
    """
    tree = ast.parse(source)
    postponed = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
        for node in ast.walk(tree)
    )
    annotation_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in [
                *args.posonlyargs,
                *args.args,
                *args.kwonlyargs,
                args.vararg,
                args.kwarg,
            ]:
                if arg is not None and arg.annotation is not None:
                    annotation_nodes.update(map(id, ast.walk(arg.annotation)))
            if node.returns is not None:
                annotation_nodes.update(map(id, ast.walk(node.returns)))
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            annotation_nodes.update(map(id, ast.walk(node.annotation)))

    lines: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)):
            continue
        in_annotation = id(node) in annotation_nodes
        if in_annotation:
            if not postponed:
                lines.append(node.lineno)
        elif _looks_like_a_type(node):
            lines.append(node.lineno)
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
        """A checker whose positive case is never exercised is a checker nobody has run — and this
        one was worse than unexercised: it returned [] for any module importing postponed
        annotations, which is EVERY file in the census, so it inspected 0 of 20 while reporting
        success (codex, PR #85). Each row below is a distinct claim, not a variation.
        """
        for source, expected, label in (
            (
                "from __future__ import annotations\nAlias = int | None\n",
                [2],
                "a module-level alias is evaluated despite postponed annotations",
            ),
            (
                (
                    "from __future__ import annotations\ndef f(v):\n"
                    "    return isinstance(v, int | str)\n"
                ),
                [3],
                "so is a union built inside a call",
            ),
            (
                (
                    "from __future__ import annotations\n"
                    "def f(x: int | None) -> str | None:\n    return None\n"
                ),
                [],
                "annotations, and only annotations, are postponed",
            ),
            (
                "def f(x: int | None) -> str | None:\n    return None\n",
                [1],
                "without the future import the annotation is evaluated again",
            ),
            (
                "FLAGS = 1 | 2\n\n\ndef g(x: int) -> int:\n    return x | 4\n",
                [],
                "ordinary bitwise or is not a union",
            ),
            (
                "from __future__ import annotations\nmask = FLAG_A | FLAG_B\n",
                [],
                "nor is a union of names that are not types",
            ),
        ):
            with self.subTest(label):
                self.assertEqual(expected, _runtime_evaluated_unions(source), label)

    def test_the_census_reads_the_py39_job_and_not_the_first_match(self):
        """On the real workflow both jobs list the same files, so reading the wrong one is
        invisible — which is why the original unscoped search passed. This drives a workflow where
        the two lists DIFFER, so picking the earlier job is a visible, failing answer.
        """
        synthetic = {
            "jobs": {
                "validate": {"steps": [{"run": "python3 -m py_compile wrong_job.py"}]},
                PY39_JOB: {"steps": [{"run": "python3 -m py_compile right_job.py"}]},
            }
        }
        self.assertEqual(["right_job.py"], _py_compile_tokens(synthetic, PY39_JOB))

    def test_a_job_with_two_py_compile_steps_is_an_error_not_a_guess(self):
        two = {
            "jobs": {
                PY39_JOB: {
                    "steps": [
                        {"run": "python3 -m py_compile a.py"},
                        {"run": "python3 -m py_compile b.py"},
                    ]
                }
            }
        }
        with self.assertRaises(AssertionError):
            _py_compile_tokens(two, PY39_JOB)

    def test_the_real_workflow_still_carries_that_job(self):
        workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
        self.assertIn(PY39_JOB, workflow["jobs"], "the job this census is derived from")

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
