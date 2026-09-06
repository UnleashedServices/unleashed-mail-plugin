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
_WORKFLOW_DIR = REPO / ".github/workflows"

# ── WHY THIS IS A DECLARATION AND NOT A CHECK ──────────────────────────────────────────────────
#
# Four encodings of a "which jobs run the scripts suite" detector were defeated in a row:
#
#   literal substring   -> a line continuation, padded whitespace
#   tokens on a line    -> quoting, a flag between the words, no `discover` at all
#   shlex argv          -> a quoted `;`, `2>&1`, `-s=`, `./`, wrappers, pytest, coverage
#   a substring mention -> `env:` holding the path, `working-directory:`, `${{ matrix.* }}`,
#                          a `uses:` step with no `run:` at all, a wrapper script
#
# The last row is the one that ends the argument. A step can run the suite while its `run:` text
# names nothing — the path lives in `env:` three lines above, which is this repository's own house
# style for shared values and is what zizmor's template-injection remediation tells contributors to
# do. No amount of reading `run:` finds it.
#
# The failure direction is what decides the design: a detector fails OPEN — every spelling it does
# not model is a job that escapes silently — while a declaration fails CLOSED. So there is no
# detector. Every job in every workflow either installs the pinned mypy, or is named below with a
# reason. A job that is neither is an offender, so ADDING a job forces an explicit decision rather
# than inheriting a silent exemption.
#
# ALL WORKFLOW FILES, not one. The previous guards were keyed by `(filename, job)` while only ever
# being handed `plugin-ci.yml`, so three of the four workflows were governed by nothing at all.
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

# ── THE FROZEN BODIES, AND WHY A FREEZE ────────────────────────────────────────────────────────
#
# Everything above removes parsing from the QUESTION of which jobs are governed. These two step
# bodies are where the remaining hazard lives, and they were the source of every other evasion:
# `>` instead of `>>`, `tee -a`, `printf`, `echo -n`, a second append chained onto the same line,
# a comment carrying `/bin/python`, `|| true` swallowing the suite's exit code. Each was a new way
# to spell the same step, and each defeated a checker that read the step's text.
#
# So the text is FROZEN. Any edit to either step — including every evasion above — breaks the
# digest and forces the author to re-state the declaration, which is exactly the review checkpoint
# a step that manipulates `$PATH` should have. This is the pattern COREDEV-2804 already uses for
# `.trunk/trunk.yaml`, applied to the other thing that can silently change what CI runs.
#
# AND IT MAKES THE PARSING BELOW SAFE. The cells that read these bodies parse bytes that cannot
# change without this digest failing first, so "the parser missed a spelling" stops being a way to
# get past them.
_PINNED_MYPY_STEP_DIGEST = (
    "52a0c0147dbb58a74984e8c7ecdbbb8f5071a1f29307b1e46353d4adfaf5e8e9"
)
_SUITE_STEP_DIGEST = "78a778068483d7d379ee76e2e894110b56cf84f6b1e55786e8e9b11fcad17270"
_PUBLISHED_DIRECTORY = "${RUNNER_TEMP}/pinned-mypy-bin"

# Jobs whose advisory posture is deliberate. `continue-on-error` on a job that runs the suite would
# make a green check meaningless, so the ones that legitimately carry it are named.
_JOBS_ALLOWED_TO_CONTINUE_ON_ERROR = {
    ("plugin-ci.yml", "linux-primitive-probe"),
    ("trunk-check-push.yml", "trunk-check-push"),
    ("trunk-check.yml", "trunk-check"),
    ("trunk-parity-harness.yml", "parity"),
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _workflows() -> list[tuple[str, dict]]:
    """Every workflow file in the repository, parsed."""
    return [
        (path.name, yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        for path in sorted(_WORKFLOW_DIR.glob("*.yml"))
    ]


def _installs_the_pin(job: dict) -> bool:
    """Whether the job installs the pinned mypy, keyed on the FROZEN step body.

    `"mypy==" in step` was satisfied by an `echo`, by a comment, and by any version at all — it
    checked a mention, not the pin (PR #85 audit).
    """
    return any(
        _digest(step.get("run") or "") == _PINNED_MYPY_STEP_DIGEST
        for step in (job.get("steps") or [])
    )


def _unclassified_jobs() -> list[str]:
    """Jobs that neither install the pin nor are declared as not running the suite."""
    offenders = []
    for filename, document in _workflows():
        for name, job in (document.get("jobs") or {}).items():
            if (filename, name) in _JOBS_THAT_DO_NOT_RUN_THE_SCRIPTS_SUITE:
                continue
            if not _installs_the_pin(job):
                offenders.append(
                    f"{filename}::{name}: neither installs the pinned mypy nor is declared as "
                    "a job that does not run the scripts suite"
                )
    return offenders


def _stale_declarations() -> list[str]:
    """Declared names that no longer exist, and declarations that contradict themselves.

    THE VACUITY CONTROL. `_unclassified_jobs()` returning `[]` is satisfied by a workflow nobody
    matches, and by a declaration that exempts everything — so the empty result is only evidence
    while the declaration still describes reality (PR #85 audit).
    """
    live = {
        (filename, name)
        for filename, document in _workflows()
        for name in (document.get("jobs") or {})
    }
    offenders = [
        f"{filename}::{name}: declared, but no such job exists"
        for (filename, name) in sorted(_JOBS_THAT_DO_NOT_RUN_THE_SCRIPTS_SUITE)
        if (filename, name) not in live
    ]
    offenders += [
        f"{filename}::{name}: declared as not running the suite, yet installs the pin"
        for filename, document in _workflows()
        for name, job in (document.get("jobs") or {}).items()
        if (filename, name) in _JOBS_THAT_DO_NOT_RUN_THE_SCRIPTS_SUITE
        and _installs_the_pin(job)
    ]
    return offenders


def _github_path_steps() -> list[tuple[str, str, dict]]:
    """Every step in every workflow that mentions `$GITHUB_PATH` ANYWHERE in its YAML.

    Not just in `run:` — a `uses:` step, a `with:` value or an `env:` entry can put a directory on
    `$PATH` for the rest of the job just as effectively, and reading `run:` alone made those
    invisible (PR #85 audit).
    """
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


class EveryJobIsClassified(unittest.TestCase):
    """No detection, so nothing to evade — and controls proving the emptiness means something."""

    def test_every_job_installs_the_pin_or_is_declared(self):
        self.assertEqual(
            [],
            _unclassified_jobs(),
            "a job that runs the scripts suite without the pinned mypy fails the 3.9-floor cell "
            "on CI; adding a job must be an explicit decision, not a silent exemption",
        )

    def test_the_declaration_still_describes_reality(self):
        self.assertEqual([], _stale_declarations())

    def test_the_jobs_that_install_the_pin_are_the_ones_that_run_the_suite(self):
        """VACUITY CONTROL. `_unclassified_jobs() == []` is satisfied by a workflow nobody
        matches and by a declaration that exempts everything, so the count is asserted too.
        """
        installers = {
            f"{filename}::{name}"
            for filename, document in _workflows()
            for name, job in (document.get("jobs") or {}).items()
            if _installs_the_pin(job)
        }
        self.assertEqual(
            {"plugin-ci.yml::validate", "plugin-ci.yml::darwin-suite"}, installers
        )

    def test_every_workflow_file_is_actually_read(self):
        """The previous guards were keyed by filename while being handed ONE file, so three of the
        four workflows were governed by nothing. This asserts the breadth, not just the verdict.
        """
        names = {filename for filename, _ in _workflows()}
        self.assertIn("plugin-ci.yml", names)
        self.assertGreaterEqual(
            len(names), 4, f"only {len(names)} workflow(s) read: {names}"
        )

    def test_a_new_undeclared_job_is_an_offender(self):
        """The discriminating case, since every real job passes: prove the census can fail."""
        live = {
            (filename, name)
            for filename, document in _workflows()
            for name in (document.get("jobs") or {})
        }
        self.assertNotIn(
            ("plugin-ci.yml", "a-job-nobody-declared"),
            live,
            "fixture name collided with a real job",
        )
        # The predicate is exercised through its own helpers on a synthetic document rather than
        # by writing a file, because writing one would void any review round in flight.
        synthetic = {"jobs": {"a-job-nobody-declared": {"steps": [{"run": "echo hi"}]}}}
        offenders = [
            f"x.yml::{name}"
            for name, job in synthetic["jobs"].items()
            if ("x.yml", name) not in _JOBS_THAT_DO_NOT_RUN_THE_SCRIPTS_SUITE
            and not _installs_the_pin(job)
        ]
        self.assertEqual(["x.yml::a-job-nobody-declared"], offenders)


class TheStepsThatChangePathAreFrozen(unittest.TestCase):
    """`$GITHUB_PATH` PREPENDS: publishing a venv's `bin` replaces `python3` for every later step
    in the job, which is how the scripts suite lost PyYAML. Every evasion of the previous checks
    was a different way to spell this step, so the step is frozen instead of parsed.
    """

    def test_every_github_path_step_in_the_repository_is_frozen(self):
        offenders = []
        for filename, name, step in _github_path_steps():
            if _digest(step.get("run") or "") != _PINNED_MYPY_STEP_DIGEST:
                offenders.append(
                    f"{filename}::{name}: touches $GITHUB_PATH with an unfrozen body"
                )
        self.assertEqual([], offenders)

    def test_the_freeze_covers_exactly_the_two_known_steps(self):
        """VACUITY CONTROL — the cell above passes trivially if nothing touches $GITHUB_PATH."""
        self.assertEqual(
            [("plugin-ci.yml", "validate"), ("plugin-ci.yml", "darwin-suite")],
            [(f, n) for f, n, _ in _github_path_steps()],
        )

    def test_the_frozen_body_publishes_the_declared_directory_and_nothing_else(self):
        """Parsing is safe HERE because the bytes are frozen: they cannot change without the
        digest cell failing first. Every append in the body is checked, not just the first —
        `split(">>", 1)` read only one, so a second append chained onto the same line was invisible.
        """
        for filename, name, step in _github_path_steps():
            body = step.get("run") or ""
            published = [
                segment.rsplit(">>", 1)[-1]
                for segment in body.split("\n")
                if "GITHUB_PATH" in segment and ">>" in segment
            ]
            with self.subTest(job=f"{filename}::{name}"):
                self.assertEqual(1, len(published), "exactly one append is expected")
                self.assertIn(_PUBLISHED_DIRECTORY, body)

    def test_the_published_directory_is_not_inside_a_venv_created_by_that_step(self):
        """THE PROPERTY THE P1 VIOLATED, stated over the frozen text."""
        for filename, name, step in _github_path_steps():
            body = step.get("run") or ""
            targets = re.findall(r"-m venv\s+(\S+)", body)
            with self.subTest(job=f"{filename}::{name}"):
                self.assertTrue(targets, "the step is expected to create a venv")
                for target in targets:
                    clean = target.strip("\"'").rstrip("/")
                    self.assertFalse(
                        _PUBLISHED_DIRECTORY.startswith(clean + "/"),
                        f"{_PUBLISHED_DIRECTORY} is inside the venv {clean}",
                    )


class TheSuiteStepCannotSwallowItsResult(unittest.TestCase):
    """A job can install the pin, run the suite, and stay green while the suite fails — `|| true`,
    a step-level `continue-on-error`, or an `if:` that never fires all do it (PR #85 audit).
    """

    def _suite_steps(self):
        for filename, document in _workflows():
            for name, job in (document.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    if _digest(step.get("run") or "") == _SUITE_STEP_DIGEST:
                        yield filename, name, step

    def test_both_suite_steps_are_frozen(self):
        found = [(f, n) for f, n, _ in self._suite_steps()]
        self.assertEqual(
            [("plugin-ci.yml", "validate"), ("plugin-ci.yml", "darwin-suite")], found
        )

    def test_no_suite_step_is_conditional_or_advisory(self):
        for filename, name, step in self._suite_steps():
            with self.subTest(job=f"{filename}::{name}"):
                self.assertNotIn(
                    "if", step, "a suite step that can skip proves nothing"
                )
                self.assertIsNone(step.get("continue-on-error"))

    def test_no_pin_installing_job_is_advisory(self):
        offenders = []
        for filename, document in _workflows():
            for name, job in (document.get("jobs") or {}).items():
                if not _installs_the_pin(job):
                    continue
                if job.get("continue-on-error"):
                    offenders.append(
                        f"{filename}::{name}: runs the suite but is advisory"
                    )
        self.assertEqual([], offenders)

    def test_advisory_jobs_are_declared(self):
        offenders = []
        for filename, document in _workflows():
            for name, job in (document.get("jobs") or {}).items():
                if (
                    job.get("continue-on-error")
                    and (
                        filename,
                        name,
                    )
                    not in _JOBS_ALLOWED_TO_CONTINUE_ON_ERROR
                ):
                    offenders.append(
                        f"{filename}::{name}: undeclared continue-on-error"
                    )
        self.assertEqual([], offenders)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
