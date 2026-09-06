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
import os
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


# CapWords, and it must CONTAIN A LOWERCASE LETTER. `\A[A-Z][A-Za-z0-9]*\Z` alone also matches
# ALL-CAPS, which are constants by the same convention — `APPROVING | {"..."}` is a set union
# valid on 3.9, and `Flags.RED | Flags.BLUE` is enum arithmetic. The first spelling flagged both.
_CAPWORDS = re.compile(r"\A[A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*\Z")


def _names_a_type(node: ast.AST) -> bool:
    """Whether this operand reads as a TYPE rather than as an integer.

    `_TYPE_NAMES` alone covered builtins and typing aliases, so `Alias = Foo | Bar` and
    `isinstance(v, Foo | Bar)` — both runtime-evaluated, both TypeError on 3.9 — were reported as
    clean, which is the commonest spelling of the very incompatibility this gate advertises
    (codex, PR #85). CapWords is the discriminator Python's own conventions supply: `Foo` is a
    class, `FLAG_A` is a constant, and `Flags.RED | Flags.BLUE` keeps its ALL-CAPS attribute so it
    stays out. A convention is not a proof, and the alternative — resolving names — is not
    available to a static scan, so the rule is stated here rather than implied.
    """
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in _TYPE_NAMES or bool(_CAPWORDS.match(node.id))
    if isinstance(node, ast.Attribute):
        return node.attr in _TYPE_NAMES or bool(_CAPWORDS.match(node.attr))
    if isinstance(node, ast.Subscript):
        return _names_a_type(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _names_a_type(node.left) or _names_a_type(node.right)
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

    # A `|` inside the second argument of isinstance/issubclass is a TYPE union by construction,
    # whatever the operands are called — no naming convention needed to know that.
    isinstance_args: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"isinstance", "issubclass"}
            and len(node.args) >= 2
        ):
            isinstance_args.update(map(id, ast.walk(node.args[1])))

    lines: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)):
            continue
        in_annotation = id(node) in annotation_nodes
        if in_annotation:
            if not postponed:
                lines.append(node.lineno)
        elif id(node) in isinstance_args or _names_a_type(node):
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
            (
                "from __future__ import annotations\nAlias = Foo | Bar\n",
                [2],
                "USER-DEFINED types count: _TYPE_NAMES alone missed the commonest spelling",
            ),
            (
                (
                    "from __future__ import annotations\ndef f(v):\n"
                    "    return isinstance(v, Foo | Bar)\n"
                ),
                [3],
                "an isinstance second argument is a type union whatever the operands are called",
            ),
            (
                "APPROVING = {'A'}\nBOTH = APPROVING | {'B'}\n",
                [],
                "ALL-CAPS is a constant by the same convention: this set union is valid on 3.9",
            ),
            (
                "mask = Flags.RED | Flags.BLUE\n",
                [],
                "and enum arithmetic stays out for the same reason",
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


_SUITE_COMMAND = "unittest"
_SUITE_DIRECTORY = "scripts/tests"

# THE TRIGGER IS A MENTION, NOT A PARSE — and that is a deliberate reversal.
#
# Three review rounds drove a tokeniser through quoting, redirection, process wrappers, alternate
# runners and venv operand grammar. Each round modelled more shell and each round produced more
# shell left unmodelled; round 3's prescription was, literally, "parse complete shell constructs".
# A unit test is the wrong place for a shell interpreter, and the failure direction is what
# settles it: an approximate parser fails OPEN. Every spelling it does not model is a job that
# escapes silently, which is exactly the defect this cell exists to prevent.
#
# So the question is inverted. ANY step whose text mentions `scripts/tests` puts its job under the
# requirement, however that text is spelled. Every evasion found across three rounds —
# `unittest 'discover'`, `scripts/"tests"`, `-s=scripts/tests`, `./scripts/tests`, a line
# continuation, `2>&1`, `-p 'test_[a-z;]*.py'`, `timeout 300 python3 …`, `pytest`, `coverage run`,
# `unittest.main`, a bare module path — contains that substring. None can hide from it.
#
# The cost is false positives: a job may mention the path without running the suite. That is not a
# defect to be parsed away, it is DECLARED below with a reason, and a declaration is reviewable in
# a way a parser's silence is not.
_JOBS_THAT_MENTION_THE_SUITE_WITHOUT_RUNNING_IT: dict[str, str] = {}

# Steps permitted to write `$GITHUB_PATH`, and the exact directory each publishes.
#
# `$GITHUB_PATH` PREPENDS, so a published venv `bin` silently replaces `python3` for every later
# step in the job — the P1 that broke this branch, invisible to any local run because the variable
# does not exist locally. There are exactly two such writes in this repository's workflows and both
# are here. The guard's job is to refuse an UNDECLARED write, which no spelling can evade, because
# the trigger is again a mention.
_GITHUB_PATH_WRITES = {
    ("plugin-ci.yml", "validate"): "${RUNNER_TEMP}/pinned-mypy-bin",
    ("plugin-ci.yml", "darwin-suite"): "${RUNNER_TEMP}/pinned-mypy-bin",
}


def _step_text(step: dict) -> str:
    """The step's script with quote characters removed.

    ONE normalisation, and it is needed: `-s scripts/"tests"` names the suite directory and does
    NOT contain the substring, because a quote sits inside the path (codex, PR #85 round 1).
    Dropping `"` and `'` before the search is the whole of it — no tokenising, no command
    splitting, nothing that failed across three rounds. Two adjacent quoted words could in
    principle be joined into a spurious match; that costs a false positive, which is declarable,
    rather than a false negative, which is silent.
    """
    return (step.get("run") or "").replace('"', "").replace("'", "")


def _jobs_missing_the_pin(workflow: dict) -> list[str]:
    """Jobs mentioning the suite directory without installing the pinned mypy before it.

    Separated from disk so it can be exercised against a workflow that ACTUALLY HAS the defect —
    reading the real file only ever proves the current shape passes.
    """
    offenders = []
    for name, job in (workflow.get("jobs") or {}).items():
        if name in _JOBS_THAT_MENTION_THE_SUITE_WITHOUT_RUNNING_IT:
            continue
        steps = job.get("steps") or []
        mention_at = next(
            (
                index
                for index, step in enumerate(steps)
                if _SUITE_DIRECTORY in _step_text(step)
            ),
            None,
        )
        if mention_at is None:
            continue
        installs = [
            index for index, step in enumerate(steps) if "mypy==" in _step_text(step)
        ]
        if not installs:
            offenders.append(
                f"{name}: mentions {_SUITE_DIRECTORY}, never installs the pinned mypy"
            )
        elif installs[0] > mention_at:
            offenders.append(f"{name}: installs the pin AFTER running the suite")
    return offenders


def _undeclared_github_path_writes(workflow: dict, filename: str) -> list[str]:
    """`$GITHUB_PATH` writes the allowlist above does not account for."""
    offenders = []
    for name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            text = _step_text(step)
            # A WRITE, not a mention. `>>` is required and `#` lines are skipped, because this
            # module's own explanatory comments say "$GITHUB_PATH" and were read as publications.
            writes = [
                line
                for line in text.splitlines()
                if "GITHUB_PATH" in line
                and ">>" in line
                and not line.strip().startswith("#")
            ]
            if not writes:
                continue
            declared = _GITHUB_PATH_WRITES.get((filename, name))
            if declared is None:
                offenders.append(
                    f"{name}: writes $GITHUB_PATH, which is not declared in this module"
                )
                continue
            # THE OPERAND OF THE APPEND, NOT THE STEP'S TEXT. Asking whether the declared path
            # appeared anywhere in the step made this cell UNABLE TO FAIL for its own defect:
            # the shipped step names `pinned-mypy-bin` on its `ln -sf` and `--version` lines, so
            # switching the published directory back to the venv's `bin` — the exact P1 — left
            # the declared string present and the cell green. Caught by mutating the real
            # workflow and watching nothing go red.
            for line in writes:
                published = line.split(">>", 1)[0].strip()
                for command in ("echo", "printf"):
                    if published.startswith(command):
                        published = published[len(command) :].strip()
                if published != declared:
                    offenders.append(
                        f"{name}: publishes {published!r} to $GITHUB_PATH, not the declared "
                        f"{declared!r}"
                    )
    return offenders


def _installs_pep668_refuses(workflow: dict) -> list[str]:
    """Steps installing the pin in the one form an externally-managed interpreter rejects.

    `darwin-suite` has no setup-python step, so its `python3` is the runner's system interpreter,
    which REFUSES a plain `pip install`. Two forms survive: an install run through a venv's own
    interpreter, or an explicit `--break-system-packages`.

    DECLARED BOUNDARY: this asserts the shape of a step, not arbitrary shell. Round 2 showed a
    text-scoped version accepting `v/bin/python -m pip --version && python3 -m pip install …`,
    where the venv interpreter runs something else entirely. Requiring the venv's `bin/python` to
    appear on the SAME line as `mypy==` closes the case that was found; a step contrived to defeat
    even that is out of scope here, and `_GITHUB_PATH_WRITES` above is what actually bounds the
    blast radius of a wrong install.
    """
    offenders = []
    for name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            install = next(
                (
                    line
                    for line in _step_text(step).splitlines()
                    if "mypy==" in line and "pip install" in line
                ),
                None,
            )
            if install is None:
                continue
            if "--break-system-packages" in install:
                continue
            if "/bin/python" in install and "-m venv" in _step_text(step):
                continue
            offenders.append(
                f"{name}: installs the pin through a possibly externally-managed interpreter"
            )
    return offenders


_MYPY_VERSION = re.compile(r"\bmypy\s+(\d+(?:\.\d+)*[0-9A-Za-z.+-]*)")


def _reported_mypy_version(binary: str) -> str | None:
    """The version token `binary` REPORTS, parsed out rather than substring-matched.

    `pinned in reported` is TRUE of a mypy reporting 2.3.10 when the pin is 2.3.1 — and of 12.3.1
    as well — so the ambient-binary guard accepted precisely the releases it exists to reject
    (codex, PR #85). Compare the token, never the sentence that contains it.
    """
    try:
        completed = subprocess.run(
            [binary, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError:
        return None
    match = _MYPY_VERSION.search(completed.stdout)
    return match.group(1) if match else None


class EveryJobRunningTheSuiteCanSatisfyItsOwnGate(unittest.TestCase):
    """The cell below FAILS rather than skips when CI is set, so every CI job that runs this suite
    must be able to reach the pinned mypy. That coupling lives across two files and a local run
    cannot see it: locally `CI` is unset, so the guard skips and the mismatch is invisible.

    It was invisible exactly once. The install step was added to `validate` only; `darwin-suite`
    runs the same suite and went red on a machine that had no pin to find. This asserts the
    invariant where it can be checked before pushing.
    """

    def test_every_job_that_runs_the_suite_installs_the_pinned_mypy(self):
        workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
        self.assertEqual(
            [],
            _jobs_missing_the_pin(workflow),
            "the 3.9-floor cell fails rather than skips on CI, so a job that runs the suite "
            "without the pin cannot satisfy it",
        )

    def test_every_github_path_write_in_this_workflow_is_declared(self):
        workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
        self.assertEqual(
            [],
            _undeclared_github_path_writes(workflow, CI.name),
            "$GITHUB_PATH PREPENDS, so an undeclared write can silently replace python3 for every "
            "later step in its job — which is exactly how the suite lost PyYAML",
        )

    def test_no_declared_path_is_a_venv_bin(self):
        """The declaration is only worth having if something checks WHAT is declared.

        The P1 was publishing a venv's own `bin`; a declaration naming one would reintroduce it
        with review cover. A venv publishes `<target>/bin` — that suffix is the property.
        """
        for (filename, job), path in sorted(_GITHUB_PATH_WRITES.items()):
            with self.subTest(job=f"{filename}::{job}"):
                self.assertFalse(
                    path.endswith("/bin"),
                    f"{job} declares {path}, which is the shape of a venv interpreter directory",
                )

    def test_no_job_installs_the_pin_in_the_form_pep668_refuses(self):
        workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
        self.assertEqual(
            [],
            _installs_pep668_refuses(workflow),
            "`darwin-suite` has no setup-python step, so a bare `pip install` there is refused "
            "by an externally-managed interpreter and the job cannot reach the pin at all",
        )


class TheConfiguredTargetIsOneThePinnedMypyAccepts(unittest.TestCase):
    """The defect's own shape: a config naming a version mypy refuses is a NOTE, not an error, so
    it survives every green run. This asserts the acceptance rather than the spelling, so the next
    mypy bump that narrows the supported range fails here instead of silently un-targeting.
    """

    @staticmethod
    def _pinned_version() -> str:
        """The version `.trunk/trunk.yaml` pins, because that is the release under test."""
        config = yaml.safe_load(
            (REPO / ".trunk/trunk.yaml").read_text(encoding="utf-8")
        )
        for entry in config["lint"]["enabled"]:
            name, _, version = str(entry).partition("@")
            if name == "mypy":
                return version
        raise AssertionError("mypy is not pinned in .trunk/trunk.yaml")

    @classmethod
    def _mypy(cls) -> str | None:
        """The PINNED release, wherever it lives — never whatever happens to be on PATH.

        Resolving `shutil.which("mypy")` first meant any ambient binary was tested instead, and the
        property here is precisely WHICH targets a PARTICULAR release accepts, so an older mypy
        passes where the pinned one refuses (codex, PR #85). Two lookups, both version-checked:

          * trunk's tool cache, honouring TRUNK_CACHE — CI pipelines relocate that cache to persist
            it across runs, and hardcoding ~/.cache/trunk made this skip there (gemini, PR #85);
          * a mypy on PATH, accepted ONLY if it reports the pinned version, so CI can install the
            pin directly without this becoming the ambient-binary bug again.
        """
        pinned = cls._pinned_version()
        cache = os.environ.get("TRUNK_CACHE")
        base = pathlib.Path(cache) if cache else pathlib.Path.home() / ".cache/trunk"
        cached = sorted(base.glob(f"tools/mypy/{pinned}-*/bin/mypy"))
        if cached:
            return str(cached[-1])
        ambient = shutil.which("mypy")
        # THE TOKEN, NOT A SUBSTRING OF THE LINE. `pinned in reported` accepted a mypy reporting
        # 2.3.10 against a 2.3.1 pin, and 12.3.1 against it too — so the guard whose entire
        # purpose is refusing an ambient binary admitted exactly the neighbouring releases whose
        # behaviour differs (codex, PR #85).
        if ambient and _reported_mypy_version(ambient) == pinned:
            return ambient
        return None

    def test_it_interrogates_the_PINNED_release_not_an_ambient_one(self):
        """The property under test is which Python targets a PARTICULAR mypy accepts, so resolving
        `shutil.which("mypy")` first meant a developer or runner with any ambient mypy tested that
        one instead — and an older binary passes where the pinned release refuses, defeating the
        protection entirely (codex, PR #85). The pin is read from `.trunk/trunk.yaml`, so a bump
        there moves this too.
        """
        pinned = self._pinned_version()
        self.assertRegex(
            pinned, r"\A\d+\.\d+\.\d+\Z", "the pin must be a concrete version"
        )
        resolved = self._mypy()
        if resolved is None:
            # A SKIP ON CI IS THE DEFECT, NOT A COURTESY. This cell is the only guard on the
            # mypy half of the 3.9 floor, and it skipped on every CI run — so a future pin that
            # refuses the configured target would pass exactly where it gates (codex, PR #85).
            # Contributors without the pin still skip; CI does not get that option.
            if os.environ.get("CI"):
                self.fail(
                    f"the pinned mypy {self._pinned_version()} is not available on CI — "
                    "this cell cannot gate what it claims to"
                )
            self.skipTest("the pinned mypy is not materialised on this machine")
        # THE VERSION IT REPORTS, not the path it sits at. This asserted the resolved path
        # contained "/mypy/<pinned>-", which is the shape of TRUNK'S CACHE — so the moment CI
        # satisfied the pin by installing it with pip, the correct binary at
        # /opt/hostedtoolcache/.../bin/mypy failed an assertion about pinning. The property is
        # which release this is, and `--version` is what answers that.
        # assertEqual on the PARSED TOKEN, not assertIn on the banner: `assertIn("2.3.1", ...)`
        # is satisfied by "mypy 2.3.10" and by "mypy 12.3.1", which is the same substring defect
        # the resolver above carried (codex, PR #85).
        reported = _reported_mypy_version(resolved)
        self.assertEqual(
            pinned,
            reported,
            f"resolved a mypy reporting {reported!r}, not the pinned {pinned}",
        )

    def test_the_pinned_mypy_does_not_refuse_the_configured_version(self):
        mypy = self._mypy()
        if mypy is None:
            # A SKIP ON CI IS THE DEFECT. This is the only guard on the mypy half of the 3.9
            # floor, and it skipped on every CI run — so a pin that refuses the configured
            # target would pass exactly where it gates (codex, PR #85).
            if os.environ.get("CI"):
                self.fail(
                    f"the pinned mypy {self._pinned_version()} is not available on CI — "
                    "this cell cannot gate what it claims to"
                )
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


class TheVersionGuardComparesTokensNotSubstrings(unittest.TestCase):
    """`pinned in reported` was true of 2.3.10 for a 2.3.1 pin, and of 12.3.1 (codex, PR #85).

    These run a real binary rather than stubbing the call, because the property is what the
    resolver does with what a binary PRINTS, and a stub asserting my own parse would be testing
    the mechanism I chose instead of the behaviour it exists to produce.
    """

    def _fake_mypy(self, banner: str) -> str:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        binary = pathlib.Path(tmp.name) / "mypy"
        binary.write_text(f"#!/bin/sh\necho '{banner}'\n", encoding="utf-8")
        binary.chmod(0o755)
        return str(binary)

    def test_a_longer_patch_is_not_the_pin(self):
        self.assertEqual(
            "2.3.10",
            _reported_mypy_version(self._fake_mypy("mypy 2.3.10 (compiled: yes)")),
        )

    def test_a_longer_major_is_not_the_pin(self):
        self.assertEqual(
            "12.3.1",
            _reported_mypy_version(self._fake_mypy("mypy 12.3.1 (compiled: yes)")),
        )

    def test_the_pin_itself_is_recognised(self):
        self.assertEqual(
            "2.3.1",
            _reported_mypy_version(self._fake_mypy("mypy 2.3.1 (compiled: yes)")),
        )

    def test_a_binary_that_cannot_be_executed_reports_nothing(self):
        self.assertIsNone(_reported_mypy_version("/nonexistent/mypy"))

    def test_a_banner_without_a_version_reports_nothing(self):
        self.assertIsNone(_reported_mypy_version(self._fake_mypy("mypy (unknown)")))


class TheMentionTriggerCatchesEverySpelling(unittest.TestCase):
    """Every evasion found across three review rounds, against one check.

    This class is the argument for the reversal. Each row below defeated some encoding of a
    tokenising census — several defeated two, and each fix that closed one opened another. All of
    them mention `scripts/tests`, so all of them are caught by asking that question instead, and
    no future spelling can be added to this list.
    """

    EVASIONS = {
        # round 1 — the literal-substring census
        "continuation": "python3 -m unittest discover \\\n  -s scripts/tests",
        "padded whitespace": "python3 -m unittest  discover -s  scripts/tests",
        # round 2 — the line-scoped token census
        "quoted subcommand": "python3 -m unittest 'discover' -s scripts/tests",
        "quoted path segment": 'python3 -m unittest discover -s scripts/"tests"',
        "flag between words": "python3 -m unittest -v discover -s scripts/tests",
        "no discover": "python3 -m unittest scripts/tests/test_x.py",
        "quoted separator": "python3 -m unittest discover -p 'test_[a-z;]*.py' -s scripts/tests",
        "redirection": "python3 -m unittest discover 2>&1 -s scripts/tests",
        # round 3 — the shlex census
        "option-assignment": "python3 -m unittest discover -s=scripts/tests",
        "explicit relative": "python3 -m unittest discover -s ./scripts/tests",
        "module entrypoint": "python3 -m unittest.main scripts/tests",
        "direct script": "python3 scripts/tests/test_x.py",
        "timeout wrapper": "timeout 300 python3 -m unittest discover -s scripts/tests",
        "exec wrapper": "exec python3 scripts/tests/test_x.py",
        "sudo wrapper": "sudo python3 -m unittest discover -s scripts/tests",
        "env -u wrapper": "env -u PYTHONPATH python3 -m unittest discover -s scripts/tests",
        "pytest": "pytest scripts/tests",
        "coverage": "coverage run -m unittest discover -s scripts/tests",
        "pypy": "pypy3 -m unittest discover -s scripts/tests",
        "unclosed quote": 'python3 -m unittest discover -s scripts/tests; echo "unclosed',
        "separator-only argument": "printf '%s\\n' ';' python3 -m unittest discover -s scripts/tests",
        # the shell-variable case round 1 declared unclosable, closed by the reversal because the
        # ASSIGNMENT still spells the path
        "variable indirection": 'DIR="scripts/tests"\npython3 -m unittest discover -s "$DIR"',
    }

    def test_every_known_evasion_is_caught(self):
        for label, run in sorted(self.EVASIONS.items()):
            with self.subTest(evasion=label):
                self.assertEqual(
                    ["target: mentions scripts/tests, never installs the pinned mypy"],
                    _jobs_missing_the_pin(
                        {"jobs": {"target": {"steps": [{"run": run}]}}}
                    ),
                )

    def test_a_job_that_never_mentions_the_suite_is_not_flagged(self):
        self.assertEqual(
            [],
            _jobs_missing_the_pin(
                {
                    "jobs": {
                        "target": {
                            "steps": [{"run": "python3 -m unittest discover -s mcp"}]
                        }
                    }
                }
            ),
        )

    def test_installing_the_pin_after_the_suite_is_still_an_offence(self):
        self.assertEqual(
            ["late: installs the pin AFTER running the suite"],
            _jobs_missing_the_pin(
                {
                    "jobs": {
                        "late": {
                            "steps": [
                                {
                                    "run": "python3 -m unittest discover -s scripts/tests"
                                },
                                {"run": "python3 -m pip install mypy==2.3.1"},
                            ]
                        }
                    }
                }
            ),
        )

    def test_a_declared_exemption_is_honoured_and_is_currently_empty(self):
        """The escape hatch works — and nothing uses it, which is the fact worth asserting.

        An empty declaration means both mentioning jobs really do run the suite. If a future job
        mentions the path without running it, this dict is where that gets said out loud.
        """
        self.assertEqual({}, _JOBS_THAT_MENTION_THE_SUITE_WITHOUT_RUNNING_IT)
        # THE DICT ITSELF, not `patch.dict` by module path. Under `discover -s scripts/tests` this
        # module is imported as `test_python39_floor`, so patching
        # "scripts.tests.test_python39_floor.<name>" reached a DIFFERENT module object: the cell
        # passed when run as `-m unittest scripts.tests.test_python39_floor` and failed in the
        # suite CI actually runs.
        self.addCleanup(_JOBS_THAT_MENTION_THE_SUITE_WITHOUT_RUNNING_IT.clear)
        _JOBS_THAT_MENTION_THE_SUITE_WITHOUT_RUNNING_IT["target"] = (
            "a hypothetical mention that runs nothing"
        )
        self.assertEqual(
            [],
            _jobs_missing_the_pin(
                {"jobs": {"target": {"steps": [{"run": "ls scripts/tests"}]}}}
            ),
        )


class TheGithubPathAllowlistRefusesUndeclaredWrites(unittest.TestCase):
    """`$GITHUB_PATH` PREPENDS — an undeclared write can replace `python3` for a whole job."""

    def test_an_undeclared_write_is_an_offender(self):
        self.assertEqual(
            ["mystery: writes $GITHUB_PATH, which is not declared in this module"],
            _undeclared_github_path_writes(
                {"jobs": {"mystery": {"steps": [{"run": 'echo x >> "$GITHUB_PATH"'}]}}},
                "plugin-ci.yml",
            ),
        )

    def test_reading_github_path_is_not_writing_it(self):
        """A read must not be reported as a publication (codex, PR #85 round 3).

        This also covers the `>>` requirement itself: without it the comment filter alone still
        happens to give the right answer on the real workflow, so nothing would fail if the
        append test were deleted — an operand covered by no cell.
        """
        self.assertEqual(
            [],
            _undeclared_github_path_writes(
                {
                    "jobs": {
                        "reader": {"steps": [{"run": 'grep -F v/bin "$GITHUB_PATH"'}]}
                    }
                },
                "plugin-ci.yml",
            ),
        )

    def test_a_declared_job_publishing_something_else_is_an_offender(self):
        self.assertEqual(
            [
                (
                    "validate: publishes '${RUNNER_TEMP}/pinned-mypy/bin' to $GITHUB_PATH, "
                    "not the declared '${RUNNER_TEMP}/pinned-mypy-bin'"
                )
            ],
            _undeclared_github_path_writes(
                {
                    "jobs": {
                        "validate": {
                            "steps": [
                                {
                                    "run": 'echo "${RUNNER_TEMP}/pinned-mypy/bin" >> "$GITHUB_PATH"'
                                }
                            ]
                        }
                    }
                },
                "plugin-ci.yml",
            ),
            "the venv's own bin is the P1 shape, and a declaration must not launder it",
        )


class ThePinIsInstalledInAFormPEP668Accepts(unittest.TestCase):
    """`darwin-suite` has no setup-python, so its `python3` refuses a plain `pip install`."""

    @staticmethod
    def _one(run: str) -> dict:
        return {"jobs": {"target": {"steps": [{"run": run}]}}}

    def test_a_bare_install_is_an_offender(self):
        self.assertEqual(
            [
                "target: installs the pin through a possibly externally-managed interpreter"
            ],
            _installs_pep668_refuses(self._one('python3 -m pip install "mypy==2.3.1"')),
        )

    def test_a_venv_that_does_not_perform_the_install_is_an_offender(self):
        # Round 2's evasion: the venv interpreter runs `--version`, not the install.
        self.assertEqual(
            [
                "target: installs the pin through a possibly externally-managed interpreter"
            ],
            _installs_pep668_refuses(
                self._one(
                    "python3 -m venv v\n"
                    "v/bin/python -m pip --version\n"
                    "python3 -m pip install mypy==2.3.1"
                )
            ),
        )

    def test_the_shipped_shape_and_the_explicit_flag_are_accepted(self):
        for run in (
            'python3 -m venv "${R}/v"\n"${R}/v/bin/python" -m pip install "mypy==2.3.1"',
            "python3 -m pip install --break-system-packages mypy==2.3.1",
        ):
            with self.subTest(run=run):
                self.assertEqual([], _installs_pep668_refuses(self._one(run)))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
