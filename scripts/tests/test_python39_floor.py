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
import shlex
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
_MYPY_VERSION = re.compile(r"\bmypy\s+(\d+(?:\.\d+)*[0-9A-Za-z.+-]*)")


def _logical_lines(step: dict) -> list[str]:
    """`step`'s run script as logical commands: continuations folded, whitespace collapsed."""
    folded = re.sub(r"\\\n\s*", " ", step.get("run") or "")
    return [re.sub(r"\s+", " ", line).strip() for line in folded.splitlines()]


_SHELL_SEPARATORS = re.compile(r"(?:\|\||&&|[;|&])")


def _commands(step: dict) -> list[list[str]]:
    """Each logical line split into shell commands and tokenised the way a shell would.

    Unbalanced quotes fall back to a whitespace split rather than raising: this is a census over
    other people's YAML, and refusing to parse a step is a silent exemption.
    """
    out = []
    for line in _logical_lines(step):
        for raw in _SHELL_SEPARATORS.split(line):
            segment = raw.strip()
            if not segment:
                continue
            try:
                out.append(shlex.split(segment))
            except ValueError:
                out.append(segment.split())
    return out


def _runs_scripts_suite(step: dict) -> bool:
    """Whether `step` runs the scripts suite — asked of the ARGV, not of the raw text.

    Three rounds of this check have now been evaded, each time because it matched a longer
    spelling than the property needed:

      * `"unittest discover -s scripts/tests" in run` — beaten by a line continuation or one
        extra space (codex, PR #85).
      * the same tokens anywhere on one logical line — beaten by `unittest 'discover'` and by
        `scripts/"tests"`, whose argv is IDENTICAL to the canonical command, and it false-positived
        on `echo 'unittest discover'; ls scripts/tests` (codex, PR #85 round 2). Also beaten by a
        flag between the two words, and by dropping `discover` entirely — `python3 -m unittest
        scripts/tests/test_x.py` runs the suite perfectly well (agy, PR #85 round 2).

    So the question asked here is the one that survives quoting and word order: does a single
    command invoke `unittest` AND name something under `scripts/tests`? `discover` is deliberately
    NOT required — it is one spelling of running the suite, not the property.

    DECLARED LIMIT: this cannot follow shell variables. `DIR=scripts/tests` on one line and
    `-s "$DIR"` on the next evades it, and no static string match over YAML can close that. Stated
    rather than papered over, because a predicate that looks total and is not is worse than one
    whose edge is known.
    """
    for tokens in _commands(step):
        if _SUITE_COMMAND not in tokens:
            continue
        if any(
            token == _SUITE_DIRECTORY or token.startswith(_SUITE_DIRECTORY + "/")
            for token in tokens
        ):
            return True
    return False


def _jobs_missing_the_pin(workflow: dict) -> list[str]:
    """Jobs that run the scripts suite without installing the pinned mypy before it.

    Separated from disk so the predicate can be exercised against a workflow that ACTUALLY HAS
    the defect. Reading the real file only ever proves the current shape passes, which is the
    reachability-is-not-discrimination failure this module has been repaired for once already.
    """
    offenders = []
    for name, job in (workflow.get("jobs") or {}).items():
        steps = job.get("steps") or []
        suite_at = next(
            (index for index, step in enumerate(steps) if _runs_scripts_suite(step)),
            None,
        )
        if suite_at is None:
            continue
        installs = [
            index
            for index, step in enumerate(steps)
            if any("mypy==" in line for line in _logical_lines(step))
        ]
        if not installs:
            offenders.append(f"{name}: runs the suite, never installs the pinned mypy")
        elif installs[0] > suite_at:
            offenders.append(f"{name}: installs the pin AFTER running the suite")
    return offenders


def _installs_pep668_refuses(workflow: dict) -> list[str]:
    """Steps installing the pinned mypy in the one form an externally-managed interpreter rejects.

    The install COMMAND must itself carry one of the two forms known to survive PEP 668: it runs
    out of a venv created in the same step, or it says `--break-system-packages`. Checking the
    step for `-m venv` ANYWHERE passed this, which creates a venv and then installs with the
    original interpreter — the exact call PEP 668 refuses (codex, PR #85 round 2):

        python3 -m venv v
        python3 -m pip install mypy==2.3.1

    This does not execute pip against an externally-managed interpreter — none is guaranteed on
    the machine running this suite — so it is a narrower claim than "the install works", stated
    that way on purpose. What it discriminates is the shape that was actually wrong here.
    """
    offenders = []
    for name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            lines = _logical_lines(step)
            install = next((line for line in lines if "mypy==" in line), None)
            if install is None:
                continue
            # THE VENV MUST BE THE THING THAT INSTALLS. Accepting `-m venv` anywhere in the step
            # passed a step that created a venv and then installed with the ORIGINAL interpreter,
            # which is precisely the refused call (codex, PR #85 round 2). Bind the two: the
            # install command itself must run out of a venv created here, or say the flag.
            targets = [
                shlex.split(match)[0] if match else ""
                for match in re.findall(r"-m venv\s+(\S+)", " ".join(lines))
            ]
            survives = "--break-system-packages" in install or any(
                target and f"{target}/bin/" in install for target in targets
            )
            if not survives:
                offenders.append(
                    f"{name}: installs the pin through a possibly externally-managed interpreter"
                )
    return offenders


def _publishes_a_venv_interpreter(workflow: dict) -> list[str]:
    """Steps that put a venv's own `bin` on `$GITHUB_PATH`.

    `$GITHUB_PATH` PREPENDS, so publishing a venv's `bin` silently replaces `python3` for every
    later step in the job. The venv here holds mypy and nothing else, while every module in the
    scripts suite opens with `import yaml` — so the suite died with ModuleNotFoundError in both
    jobs, and the local gate could not see it because `$GITHUB_PATH` does not exist locally
    (codex, PR #85 round 2; reproduced). Publish a directory holding the binary, not the
    interpreter.
    """
    offenders: list[str] = []
    for name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            lines = _logical_lines(step)
            joined = " ".join(lines)
            targets = {
                match.strip("\"'") for match in re.findall(r"-m venv\s+(\S+)", joined)
            }
            if not targets:
                continue
            published = {
                match.strip("\"'")
                for match in re.findall(
                    r"echo\s+(\S+)\s*>>\s*[\"']?\$\{?GITHUB_PATH", joined
                )
            }
            offenders.extend(
                f"{name}: publishes the venv interpreter at {target}/bin to $GITHUB_PATH"
                for target in targets
                if f"{target}/bin" in published
            )
    return offenders


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

    def test_no_job_publishes_a_venv_interpreter_to_github_path(self):
        workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
        self.assertEqual(
            [],
            _publishes_a_venv_interpreter(workflow),
            "$GITHUB_PATH prepends, so publishing a venv's bin replaces python3 for every later "
            "step — and this venv has mypy but not PyYAML, which every suite module imports",
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


class TheCensusSeesJobsThatDoNotSpellItTheOneWay(unittest.TestCase):
    """Mutation proof for the evasion codex found in the census (PR #85).

    The old predicate asked whether the literal `unittest discover -s scripts/tests` appeared in a
    step. Every case below runs the suite and installs nothing, so every case MUST be reported —
    under the old spelling test each of the first two was silently skipped, and the invariant went
    green while covering neither job.
    """

    @staticmethod
    def _one_job(run: str) -> dict:
        return {"jobs": {"target": {"steps": [{"run": run}]}}}

    def test_a_continuation_between_discover_and_its_flag_is_still_the_suite(self):
        self.assertEqual(
            ["target: runs the suite, never installs the pinned mypy"],
            _jobs_missing_the_pin(
                self._one_job("python3 -m unittest discover \\\n  -s scripts/tests -v")
            ),
        )

    def test_padded_whitespace_is_still_the_suite(self):
        self.assertEqual(
            ["target: runs the suite, never installs the pinned mypy"],
            _jobs_missing_the_pin(
                self._one_job("python3 -m unittest  discover -s  scripts/tests")
            ),
        )

    def test_the_two_tokens_must_share_one_COMMAND_not_merely_one_line(self):
        # The complement: a census that cries wolf gets its assertion relaxed, so the false
        # positives matter as much as the evasions. Both of these mention the tokens without
        # running anything; the second is codex's, and it registered as a suite run when the
        # predicate asked about a LINE rather than a COMMAND (PR #85 round 2).
        for run in (
            "echo 'unittest discover'\nls scripts/tests",
            "echo 'unittest discover'; ls scripts/tests",
        ):
            with self.subTest(run=run):
                self.assertEqual([], _jobs_missing_the_pin(self._one_job(run)))

    def test_quoting_that_leaves_argv_identical_is_still_the_suite(self):
        # Both have argv identical to the canonical command, and both evaded the substring
        # predicate (codex, PR #85 round 2).
        for run in (
            "python3 -m unittest 'discover' -s scripts/tests",
            'python3 -m unittest discover -s scripts/"tests"',
        ):
            with self.subTest(run=run):
                self.assertEqual(
                    ["target: runs the suite, never installs the pinned mypy"],
                    _jobs_missing_the_pin(self._one_job(run)),
                )

    def test_a_flag_between_the_two_words_is_still_the_suite(self):
        # `discover` is one spelling of running the suite, not the property (agy, PR #85 round 2).
        self.assertEqual(
            ["target: runs the suite, never installs the pinned mypy"],
            _jobs_missing_the_pin(
                self._one_job("python3 -m unittest -v discover -s scripts/tests")
            ),
        )

    def test_naming_the_modules_directly_is_still_the_suite(self):
        # No `discover` at all — this runs the suite perfectly well (agy, PR #85 round 2).
        self.assertEqual(
            ["target: runs the suite, never installs the pinned mypy"],
            _jobs_missing_the_pin(
                self._one_job(
                    "python3 -m unittest scripts/tests/test_python39_floor.py"
                )
            ),
        )

    def test_the_declared_limit_is_real_and_stays_declared(self):
        """Shell-variable indirection across lines is NOT caught, and the docstring says so.

        Recorded as an executable statement of the boundary rather than left implicit: if a later
        change closes it, this cell fails and the docstring's disclaimer gets removed with it.
        """
        self.assertEqual(
            [],
            _jobs_missing_the_pin(
                self._one_job(
                    'DIR="scripts/tests"\npython3 -m unittest discover -s "$DIR"'
                )
            ),
            "a static census cannot follow shell variables; the limit is declared, not hidden",
        )

    def test_installing_the_pin_after_the_suite_is_still_an_offence(self):
        workflow = {
            "jobs": {
                "late": {
                    "steps": [
                        {"run": "python3 -m unittest discover -s scripts/tests"},
                        {"run": "python3 -m pip install mypy==2.3.1"},
                    ]
                }
            }
        }
        self.assertEqual(
            ["late: installs the pin AFTER running the suite"],
            _jobs_missing_the_pin(workflow),
        )

    def test_a_job_that_installs_first_is_clean(self):
        workflow = {
            "jobs": {
                "good": {
                    "steps": [
                        {"run": "python3 -m venv v && v/bin/pip install mypy==2.3.1"},
                        {"run": "python3 -m unittest discover -s scripts/tests"},
                    ]
                }
            }
        }
        self.assertEqual([], _jobs_missing_the_pin(workflow))


class TheBareInstallFormIsRefused(unittest.TestCase):
    """Mutation proof for the PEP 668 finding (codex, PR #85): the bare form must be reported."""

    @staticmethod
    def _one_step(run: str) -> dict:
        return {"jobs": {"target": {"steps": [{"run": run}]}}}

    def test_a_bare_pip_install_is_an_offender(self):
        self.assertEqual(
            [
                "target: installs the pin through a possibly externally-managed interpreter"
            ],
            _installs_pep668_refuses(
                self._one_step('python3 -m pip install "mypy==2.3.1"')
            ),
        )

    def test_a_venv_install_is_accepted(self):
        self.assertEqual(
            [],
            _installs_pep668_refuses(
                self._one_step(
                    'python3 -m venv "${RUNNER_TEMP}/v"\n'
                    '"${RUNNER_TEMP}/v/bin/python" -m pip install "mypy==2.3.1"'
                )
            ),
        )

    def test_a_venv_created_but_NOT_USED_to_install_is_an_offender(self):
        # The step creates a venv and then installs with the ORIGINAL interpreter — the exact
        # call PEP 668 refuses. Accepting `-m venv` anywhere in the step passed this
        # (codex, PR #85 round 2).
        self.assertEqual(
            [
                "target: installs the pin through a possibly externally-managed interpreter"
            ],
            _installs_pep668_refuses(
                self._one_step("python3 -m venv v\npython3 -m pip install mypy==2.3.1")
            ),
        )

    def test_an_explicit_break_system_packages_is_accepted(self):
        self.assertEqual(
            [],
            _installs_pep668_refuses(
                self._one_step(
                    "python3 -m pip install --break-system-packages mypy==2.3.1"
                )
            ),
        )


class ThePinIsPublishedWithoutReplacingTheInterpreter(unittest.TestCase):
    """Mutation proof for the P1 codex reproduced (PR #85 round 2).

    `$GITHUB_PATH` PREPENDS. Publishing the venv's own `bin` therefore makes `python3` the venv's
    python for every later step in the job — and that venv holds mypy and nothing else, while
    every module in the scripts suite opens with `import yaml`. Both jobs would have gone red, and
    the local gate could not see it because `$GITHUB_PATH` does not exist locally.
    """

    @staticmethod
    def _one_step(run: str) -> dict:
        return {"jobs": {"target": {"steps": [{"run": run}]}}}

    def test_publishing_the_venv_bin_is_an_offender(self):
        self.assertEqual(
            [
                "target: publishes the venv interpreter at ${RUNNER_TEMP}/v/bin to $GITHUB_PATH"
            ],
            _publishes_a_venv_interpreter(
                self._one_step(
                    'python3 -m venv "${RUNNER_TEMP}/v"\n'
                    'echo "${RUNNER_TEMP}/v/bin" >> "${GITHUB_PATH}"'
                )
            ),
        )

    def test_publishing_a_directory_of_symlinks_is_accepted(self):
        self.assertEqual(
            [],
            _publishes_a_venv_interpreter(
                self._one_step(
                    'python3 -m venv "${RUNNER_TEMP}/v"\n'
                    'ln -sf "${RUNNER_TEMP}/v/bin/mypy" "${RUNNER_TEMP}/vbin/mypy"\n'
                    'echo "${RUNNER_TEMP}/vbin" >> "${GITHUB_PATH}"'
                )
            ),
            "a directory holding only the binary leaves python3 alone",
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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
