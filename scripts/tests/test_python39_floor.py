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
import hashlib
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
    # `\r?` — a CRLF continuation is `\`, CR, LF, and the pattern expected `\` immediately
    # followed by LF, so it did not fold and the census kept only the FIRST fragment. That is
    # the fail-OPEN direction: a shorter command means a smaller derived file set (gemini,
    # PR #85 GitHub review). Widening the fold can only ever read MORE of the command.
    folded = re.sub(r"\\\r?\n\s*", " ", commands[0])
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
_WORKFLOW_DIR = REPO / ".github/workflows"

# ── WHY EVERY JOB IS FROZEN ────────────────────────────────────────────────────────────────────
#
# Five encodings of a "which jobs run the scripts suite" detector were defeated in five rounds, and
# the two designs that replaced detection were defeated in one round each. The pattern is the same
# every time: the check covered PART of what decides whether the suite runs, and reviewers found
# the rest.
#
#   `run:` text                  -> the path can live in `env:`, `working-directory:`, a matrix
#                                   value, a wrapper script, or a `uses:` step with no `run:`
#   a digest of `run:`           -> `shell: bash -c "bash {0}; exit 0"` swallows the exit code,
#                                   `env: {RUNNER_TEMP: /tmp/fake}` redirects the install, and
#                                   `working-directory:` moves it — none change a `run:` byte
#   a declaration, trusted       -> a declared job can later ACQUIRE a suite step; the declaration
#                                   records why it was true once and is never re-checked
#
# So the unit is the JOB, and the whole of it. `yaml.safe_dump(job, sort_keys=True)` covers the
# steps, their `env`, `shell`, `working-directory` and `if`, the job's own `if`, `defaults`,
# `container`, `strategy` and `continue-on-error` — every input that decides what runs. A job that
# is not in this table, or whose digest moved, is an offender.
#
# THE COST IS DELIBERATE. Editing any CI job now requires updating its digest here, and the failure
# message prints the new value so that is one paste. For the file that decides what CI runs, an
# explicit checkpoint on every change is the point rather than the price — it is the same trade
# COREDEV-2804 already made for `.trunk/trunk.yaml`.
#
# BOTH EXTENSIONS. GitHub accepts `.yml` and `.yaml`; globbing only `*.yml` left a `.yaml` workflow
# invisible, and the ">= 4 files" control still passed (PR #85 round 5).
_JOB_DIGESTS = {
    ("plugin-ci.yml", "validate"): (
        "873948c744de057ac974f4c6b5813b92c23a01e2f4c58545af4daa67ec9da8e3"
    ),
    ("plugin-ci.yml", "py39-smoke"): (
        "e87d60109f929643f84ee362d581e4306ab54bf98cf8c3e269e814163b3f7de7"
    ),
    ("plugin-ci.yml", "linux-primitive-probe"): (
        "9364cf91c8d53c02b357618450f37ecf61aa320657983615bd9361e96bb3e904"
    ),
    ("plugin-ci.yml", "load-check"): (
        "3ebd88459a7a56467cdb862f06f1b8f9a8b406f2ec78fadcb33714b50ee6abf9"
    ),
    ("plugin-ci.yml", "redactor-equivalence"): (
        "4fea961a111c1c7670a2a51f5c573076a907013e2491893576852134b3a67e72"
    ),
    ("plugin-ci.yml", "darwin-suite"): (
        "5b3353add742eda269f607672de3d7719cd659b0a6a8c0aa7b963f4f058e4581"
    ),
    ("plugin-ci.yml", "secret-scan"): (
        "054002e2d1f9657955831df0b242439e59ecae4d2b26146d800dd251a6eed1a0"
    ),
    ("trunk-check-push.yml", "trunk-check-push"): (
        "aaea34984148bfcf2e375e07fbd21a22a012e5e50ba22da2a365a7851ef374c5"
    ),
    # M3: the job-scoped `continue-on-error: true` advisory exemption was removed here, so this
    # digest moved. The freeze caught the change, which is the point — re-declaring it is the
    # deliberate act.
    ("trunk-check.yml", "trunk-check"): (
        "791ad3a0dd38cec342756a85e4c2e1bd85cbeeed7a989a50a743f395587cfcbc"
    ),
    ("trunk-parity-harness.yml", "parity"): (
        "ece6b83e5b9d8307d9115158a9818bce9da4e1288016a3a846795883ac505095"
    ),
}

# WHY each job needs no pinned mypy, or does. Documentation the digest cannot carry — and it is
# asserted against the digest table, so the two cannot drift apart.
_JOBS_THAT_DO_NOT_RUN_THE_SCRIPTS_SUITE = {
    (
        "plugin-ci.yml",
        "py39-smoke",
    ): "byte-compiles a derived file list on 3.9; runs no tests",
    (
        "plugin-ci.yml",
        "linux-primitive-probe",
    ): "probes Linux ACL and primitive behaviour",
    (
        "plugin-ci.yml",
        "load-check",
    ): "loads the pinned Claude Code CLI against the assets",
    (
        "plugin-ci.yml",
        "redactor-equivalence",
    ): "runs the redactor equivalence matrix only",
    ("plugin-ci.yml", "secret-scan"): "runs gitleaks over history",
    ("trunk-check-push.yml", "trunk-check-push"): "the non-required push canary",
    ("trunk-check.yml", "trunk-check"): "the diff-scoped lint job",
    ("trunk-parity-harness.yml", "parity"): "the parity sensor, on fixture refs",
}

_PINNED_MYPY_STEP_DIGEST = (
    "52a0c0147dbb58a74984e8c7ecdbbb8f5071a1f29307b1e46353d4adfaf5e8e9"
)
_PUBLISHED_DIRECTORY = "${RUNNER_TEMP}/pinned-mypy-bin"

_JOBS_ALLOWED_TO_CONTINUE_ON_ERROR = {
    ("plugin-ci.yml", "linux-primitive-probe"),
    # `trunk-check-push` is the CANARY and stays advisory permanently — it can never block because
    # its context is not required, which is the whole design.
    ("trunk-check-push.yml", "trunk-check-push"),
    # ("trunk-check.yml", "trunk-check") — REMOVED AT M3. The required-to-be job is strict now, and
    # leaving it declared here would have been a stale declaration that outlived its subject: the
    # very shape `_stale_declarations()` was added to catch, which is exactly how this was found.
    ("trunk-parity-harness.yml", "parity"),
}


# ── AND THE KEYS OUTSIDE `jobs:` ───────────────────────────────────────────────────────────────
#
# The job digests cover everything INSIDE a job. They cover nothing outside one, and round 6 showed
# that is not a detail: prepending
#
#     defaults:
#       run:
#         shell: bash -c "bash {0}; exit 0"
#
# to `plugin-ci.yml` leaves ALL TEN job digests byte-identical, because `defaults:` is a
# workflow-level key. Both suite steps inherit that shell, and a measured probe — `python3` stubbed
# to exit 17 — returned **17 normally and 0 under the mutant shell**. The suite's failure would be
# reported as success while every cell passed (codex, PR #85 round 6).
#
# So the workflow-level keys are frozen too: `on:`, `env:`, `defaults:`, `permissions:`,
# `concurrency:` and anything else a future edit adds beside them.
#
# NOTE THE `on:` KEY. YAML 1.1 reads a bare `on` as the BOOLEAN True, so it arrives as `True` and
# not as the string "on" — which is why the keys are stringified before sorting. Sorting them
# unstringified raises `TypeError: '<' not supported between instances of 'bool' and 'str'`, which
# is how this was found.
_WORKFLOW_LEVEL_DIGESTS = {
    "plugin-ci.yml": "e64c6c46d7d605d58605839716ed012ee7ae65f1206816b14925a089ea361a19",
    "trunk-check-push.yml": (
        "649aca568e734004f031e7a8c8dd06d7916364a7be656f75b42d93f246ffa125"
    ),
    "trunk-check.yml": "950aea6ecb808d9d8d0b7b5f4ee57d323bd43c7bd95b10f45bbe3772535e5a17",
    "trunk-parity-harness.yml": (
        "ae1e606b59e5ae9277c23f8e0b5fd7b66ac6f11645a37cce64c3cb93b7fb3272"
    ),
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _job_digest(job: dict) -> str:
    return _digest(yaml.safe_dump(job, sort_keys=True))


def _workflow_level_digest(document: dict) -> str:
    """Everything OUTSIDE `jobs:`. Keys are stringified because `on:` arrives as boolean True."""
    top = {str(key): value for key, value in document.items() if str(key) != "jobs"}
    return _digest(yaml.safe_dump(top, sort_keys=True))


def _workflows_off_their_frozen_level() -> list[str]:
    """Workflow files whose keys outside `jobs:` are unfrozen or have moved."""
    offenders = []
    for filename, document in _workflows():
        expected = _WORKFLOW_LEVEL_DIGESTS.get(filename)
        actual = _workflow_level_digest(document)
        if expected is None:
            offenders.append(
                f"{filename}: workflow-level keys are not frozen — add them with digest {actual}"
            )
        elif expected != actual:
            offenders.append(
                f"{filename}: workflow-level keys changed; digest is now {actual}"
            )
    return offenders


def _workflow_files(directory: pathlib.Path | None = None) -> list[pathlib.Path]:
    """Every workflow file, BOTH extensions — GitHub accepts `.yml` and `.yaml`.

    Takes a directory so the globbing can be EXERCISED on the extension that escaped it, rather
    than asserted about: the first version of that cell checked this docstring for the string
    "*.yaml", which is a check on a spelling and not on the behaviour.
    """
    root = _WORKFLOW_DIR if directory is None else directory
    return sorted(
        [*root.glob("*.yml"), *root.glob("*.yaml")], key=lambda path: path.name
    )


def _workflows() -> list[tuple[str, dict]]:
    return [
        (path.name, yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        for path in _workflow_files()
    ]


def _installs_the_pin(job: dict) -> bool:
    """Keyed on the frozen STEP body — `"mypy==" in text` was satisfied by an echo, by a comment,
    and by any version at all.
    """
    return any(
        _digest(step.get("run") or "") == _PINNED_MYPY_STEP_DIGEST
        for step in (job.get("steps") or [])
    )


def _jobs_off_their_frozen_definition() -> list[str]:
    """Jobs absent from the freeze table, or whose whole definition has moved."""
    offenders = []
    for filename, document in _workflows():
        for name, job in (document.get("jobs") or {}).items():
            expected = _JOB_DIGESTS.get((filename, name))
            actual = _job_digest(job)
            if expected is None:
                offenders.append(
                    f"{filename}::{name}: not in the freeze table — add it with digest {actual}"
                )
            elif expected != actual:
                offenders.append(
                    f"{filename}::{name}: definition changed; digest is now {actual}"
                )
    return offenders


def _stale_declarations() -> list[str]:
    """Every declaration checked against reality — the freeze table, the reason table, and the
    advisory table. A declaration that outlives its subject is how an exemption becomes silent.
    """
    live = {
        (filename, name)
        for filename, document in _workflows()
        for name in (document.get("jobs") or {})
    }
    offenders = [
        f"{filename}::{name}: frozen, but no such job exists"
        for (filename, name) in sorted(_JOB_DIGESTS)
        if (filename, name) not in live
    ]
    offenders += [
        f"{filename}::{name}: declared as not running the suite, but no such job exists"
        for (filename, name) in sorted(_JOBS_THAT_DO_NOT_RUN_THE_SCRIPTS_SUITE)
        if (filename, name) not in live
    ]
    offenders += [
        f"{filename}::{name}: declared advisory, but no such job exists"
        for (filename, name) in sorted(_JOBS_ALLOWED_TO_CONTINUE_ON_ERROR)
        if (filename, name) not in live
    ]
    # An advisory declaration that no longer describes an advisory job is equally stale.
    for filename, document in _workflows():
        for name, job in (document.get("jobs") or {}).items():
            declared_advisory = (filename, name) in _JOBS_ALLOWED_TO_CONTINUE_ON_ERROR
            if declared_advisory and not job.get("continue-on-error"):
                offenders.append(
                    f"{filename}::{name}: declared advisory, but carries no continue-on-error"
                )
            if (
                filename,
                name,
            ) in _JOBS_THAT_DO_NOT_RUN_THE_SCRIPTS_SUITE and _installs_the_pin(job):
                offenders.append(
                    f"{filename}::{name}: declared as not running the suite, yet installs the pin"
                )
    return offenders


def _github_path_steps() -> list[tuple[str, str, dict]]:
    """Every step mentioning `$GITHUB_PATH` anywhere in its YAML — not only in `run:`."""
    found: list[tuple[str, str, dict]] = []
    for filename, document in _workflows():
        for name, job in (document.get("jobs") or {}).items():
            found.extend(
                (filename, name, step)
                for step in job.get("steps") or []
                if "GITHUB_PATH" in yaml.safe_dump(step)
            )
    return found


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
        output = completed.stdout + completed.stderr
        # NO CONFIG DIAGNOSTIC AT ALL, not merely the absence of one phrase.
        #
        # Asserting `"is not supported" not in output` is a requirement phrased as an absence, and
        # any OTHER config failure satisfies it — a future pin refusing the target with different
        # wording, or an unrelated broken option (codex, PR #85 GitHub review). The finding is
        # right; its proposed remedy is not, and the difference was measured:
        #
        #   config              rc   "Success: no issues found"   ": [mypy]:" line
        #   healthy (3.10)      0    yes                          no
        #   python_version=3.9  0    yes                          YES
        #   unknown option      0    yes                          YES
        #
        # mypy exits 0 while REFUSING the configured version, so "assert a successful exit" adds
        # nothing, and "Success: no issues found" is printed in all three. What discriminates is
        # that mypy reports config problems as `<file>: [mypy]: …`. Assert none is present, which
        # covers the wording this cell was written for AND every other config failure.
        config_diagnostics = [
            line for line in output.splitlines() if ": [mypy]: " in line
        ]
        self.assertEqual(
            [],
            config_diagnostics,
            "the pinned mypy reported a problem with the configured file, so the target it "
            "actually used is not the one the config names",
        )
        self.assertIn(
            "Success: no issues found",
            output,
            "the probe must actually have been checked",
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


class EveryJobIsFrozenAndClassified(unittest.TestCase):
    """The unit is the whole job, so every input that decides what runs is covered at once."""

    def test_every_job_matches_its_frozen_definition(self):
        self.assertEqual(
            [],
            _jobs_off_their_frozen_definition(),
            "a job's steps, its env, shell, working-directory, if, defaults, container and "
            "continue-on-error all decide whether the scripts suite runs and whether its result "
            "is believed — so the whole job is frozen, and changing CI is a deliberate act",
        )

    def test_every_workflow_level_key_matches_its_freeze(self):
        """`defaults.run.shell` sits OUTSIDE `jobs:` and is inherited by every step in the file.

        A wrapper shell there turns the suite's failure into success while every job digest stays
        byte-identical — measured at 17 -> 0 (codex, PR #85 round 6).
        """
        self.assertEqual(
            [],
            _workflows_off_their_frozen_level(),
            "on:, env:, defaults:, permissions: and concurrency: all change what runs without "
            "touching a single job",
        )

    def test_every_declaration_still_describes_reality(self):
        self.assertEqual([], _stale_declarations())

    def test_the_freeze_table_and_the_reason_table_partition_the_same_jobs(self):
        """The digest cannot say WHY a job needs no pin; the reason table can, and the two must
        not drift. Every frozen job is either declared as not running the suite, or installs it.
        """
        offenders = []
        for filename, document in _workflows():
            for name, job in (document.get("jobs") or {}).items():
                declared = (filename, name) in _JOBS_THAT_DO_NOT_RUN_THE_SCRIPTS_SUITE
                if declared == _installs_the_pin(job):
                    offenders.append(
                        f"{filename}::{name}: declared={declared}, installs_pin="
                        f"{_installs_the_pin(job)} — exactly one must hold"
                    )
        self.assertEqual([], offenders)

    def test_every_workflow_file_on_disk_is_read(self):
        """VACUITY CONTROL, and it replaces a broken one. The previous control asserted ">= 4
        files read", which a `.yaml` workflow satisfied while being invisible: `glob("*.yml")`
        never saw it. This compares what is READ against what is THERE.
        """
        on_disk = {
            path.name
            for path in _WORKFLOW_DIR.iterdir()
            if path.is_file() and path.suffix in {".yml", ".yaml"}
        }
        self.assertEqual(on_disk, {name for name, _ in _workflows()})
        self.assertGreaterEqual(
            len(on_disk), 4, "the workflow directory has been emptied"
        )

    def test_at_least_one_believed_job_runs_the_suite_with_the_pin(self):
        """THE PROPERTY, STATED POSITIVELY — and it is what bounds the finding below.

        A declared job invokes a repository script (`linux-primitive-probe.sh`), and that script is
        outside the workflow YAML, so editing it to run the suite leaves every digest intact
        (codex, PR #85 round 6). The freeze covers the workflow; it does not cover the transitive
        closure of everything a workflow invokes, and chasing that is unbounded — a script calls a
        script.

        What bounds the impact is this cell. The suite's BELIEVED verdict comes from jobs that
        install the pin and are neither advisory nor conditional, and removing the suite from those
        jobs, making one advisory, or putting one behind an `if:` all move a frozen digest. An
        extra unpinned run inside an advisory job is then noise: it cannot make a required check
        report green having tested nothing, which is the hazard this campaign exists for.

        The residue — an advisory job doing something misleading — is COREDEV-2823.
        """
        believed = {
            f"{filename}::{name}"
            for filename, document in _workflows()
            for name, job in (document.get("jobs") or {}).items()
            if _installs_the_pin(job)
            and not job.get("continue-on-error")
            and "if" not in job
        }
        self.assertEqual(
            {"plugin-ci.yml::validate", "plugin-ci.yml::darwin-suite"},
            believed,
            "the suite's verdict must come from at least one job that installs the pin and whose "
            "failure actually fails the run",
        )

    def test_the_jobs_that_install_the_pin_are_named(self):
        installers = {
            f"{filename}::{name}"
            for filename, document in _workflows()
            for name, job in (document.get("jobs") or {}).items()
            if _installs_the_pin(job)
        }
        self.assertEqual(
            {"plugin-ci.yml::validate", "plugin-ci.yml::darwin-suite"}, installers
        )

    def test_a_yaml_extension_workflow_is_actually_read(self):
        """EXERCISED, not asserted about. `glob("*.yml")` left a `.yaml` workflow invisible while
        the old ">= 4 files" control still passed (codex, PR #85 round 5).
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        scratch = pathlib.Path(tmp.name)
        (scratch / "a.yml").write_text("jobs: {}\n", encoding="utf-8")
        (scratch / "b.yaml").write_text("jobs: {}\n", encoding="utf-8")
        (scratch / "notes.md").write_text("ignored\n", encoding="utf-8")
        self.assertEqual(
            ["a.yml", "b.yaml"], [path.name for path in _workflow_files(scratch)]
        )


class TheStepsThatChangePathAreFrozen(unittest.TestCase):
    """`$GITHUB_PATH` PREPENDS: publishing a venv's `bin` replaces `python3` for every later step,
    which is how the scripts suite lost PyYAML. The step body is frozen; the job around it is too.
    """

    def test_every_github_path_step_is_frozen(self):
        offenders = [
            f"{filename}::{name}: touches $GITHUB_PATH with an unfrozen body"
            for filename, name, step in _github_path_steps()
            if _digest(step.get("run") or "") != _PINNED_MYPY_STEP_DIGEST
        ]
        self.assertEqual([], offenders)

    def test_the_freeze_covers_exactly_the_two_known_steps(self):
        self.assertEqual(
            [("plugin-ci.yml", "validate"), ("plugin-ci.yml", "darwin-suite")],
            [(f, n) for f, n, _ in _github_path_steps()],
        )

    def test_the_published_directory_is_not_inside_a_venv_created_by_that_step(self):
        """THE PROPERTY THE P1 VIOLATED, stated over bytes that cannot move silently."""
        for filename, name, step in _github_path_steps():
            body = step.get("run") or ""
            targets = re.findall(r"-m venv\s+(\S+)", body)
            with self.subTest(job=f"{filename}::{name}"):
                self.assertTrue(targets, "the step is expected to create a venv")
                self.assertIn(_PUBLISHED_DIRECTORY, body)
                for target in targets:
                    clean = target.strip("\"'").rstrip("/")
                    self.assertFalse(
                        _PUBLISHED_DIRECTORY.startswith(clean + "/"),
                        f"{_PUBLISHED_DIRECTORY} is inside the venv {clean}",
                    )

    def test_no_pin_installing_job_is_advisory_or_conditional(self):
        offenders = []
        for filename, document in _workflows():
            for name, job in (document.get("jobs") or {}).items():
                if not _installs_the_pin(job):
                    continue
                if job.get("continue-on-error"):
                    offenders.append(
                        f"{filename}::{name}: runs the suite but is advisory"
                    )
                if "if" in job:
                    offenders.append(
                        f"{filename}::{name}: runs the suite behind a job-level if:"
                    )
        self.assertEqual([], offenders)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
