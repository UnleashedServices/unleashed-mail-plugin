#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-M5 wrapper and recipe proof pairs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple


REPO = Path(__file__).resolve().parents[2]
REVIEW = "review"
REVIEWER_FLAG = "--" + REVIEW + "er"
PLUGIN_DATA_KEY = "CLAUDE_PLUGIN_" + "DATA"
WRAPPER_PATH = REPO / "scripts" / REVIEW / "allocate-transcript.sh"
CONTEXT_PATH = REPO / "scripts" / "lib" / "context.sh"
PATHS_PATH = REPO / "scripts" / "lib" / "paths.sh"
CODEX_SKILL = REPO / "skills" / ("codex-" + REVIEW) / "SKILL.md"
GEMINI_SKILL = REPO / "skills" / ("gemini-" + REVIEW) / "SKILL.md"

CODEX_BEGIN = "# COREDEV2619_CODEX_CAPTURE_BEGIN"
CODEX_END = "# COREDEV2619_CODEX_CAPTURE_END"
GEMINI_BEGIN = "# COREDEV2619_GEMINI_CAPTURE_BEGIN"
GEMINI_END = "# COREDEV2619_GEMINI_CAPTURE_END"

CONTEXT_STUB = r'''context_repo_hash() {
    printf 'called\n' >> "${M5_CONTEXT_LOG:?}"
    if [ -n "${M5_CONTEXT_STDERR:-}" ]; then
        printf '%s' "$M5_CONTEXT_STDERR" >&2
    fi
    printf '%s' "${M5_CONTEXT_HASH:?}"
    return "${M5_CONTEXT_STATUS:-0}"
}
'''

ALLOCATOR_STUB = r'''#!/usr/bin/env python3
import json
import os
import pathlib
import sys

record = {
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "script": str(pathlib.Path(__file__).resolve()),
}
with open(os.environ["M5_ALLOCATOR_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\n")
sys.stdout.write(
    os.environ.get(
        "M5_ALLOCATOR_STDOUT",
        "UNLEASHED_TRANSCRIPT=/fixture/transcript.txt\n",
    )
)
sys.stderr.write(os.environ.get("M5_ALLOCATOR_STDERR", ""))
raise SystemExit(int(os.environ.get("M5_ALLOCATOR_STATUS", "0")))
'''

RECIPE_WRAPPER_STUB = r'''#!/usr/bin/env bash
printf '%s\0' "$@" > "${M5_RECIPE_LOG:?}"
exit 73
'''


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise AssertionError(
            "mutation anchor must occur exactly once: " + repr(old)
        )
    return source.replace(old, new, 1)


def _replace_nth(source: str, old: str, new: str, occurrence: int) -> str:
    if occurrence < 1 or source.count(old) < occurrence:
        raise AssertionError(
            "mutation occurrence is unavailable: " + repr((old, occurrence))
        )
    start = -1
    for _index in range(occurrence):
        start = source.index(old, start + 1)
    return source[:start] + new + source[start + len(old):]


def _extract_recipe(path: Path, begin: str, end: str) -> str:
    source = path.read_text(encoding="utf-8")
    if source.count(begin) != 1 or source.count(end) != 1:
        raise AssertionError(
            "expected one bounded recipe in " + str(path)
        )
    start = source.index(begin) + len(begin)
    finish = source.index(end, start)
    return source[start:finish].strip() + "\n"


class M5WrapperFixture(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(
            prefix=".m5-wrapper-proof-",
            dir=str(REPO),
        )
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)
        self.wrapper_source = WRAPPER_PATH.read_text(encoding="utf-8")
        self.real_bash = shutil.which("bash")
        if self.real_bash is None:
            self.skipTest("bash is required")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_wrapper_tree(
        self,
        label: str,
        wrapper_source: Optional[str] = None,
        context_source: str = CONTEXT_STUB,
    ) -> Tuple[Path, Path, Path]:
        scripts = self.root / label / "scripts"
        review_dir = scripts / REVIEW
        library_dir = scripts / "lib"
        review_dir.mkdir(parents=True)
        library_dir.mkdir()

        wrapper = review_dir / WRAPPER_PATH.name
        wrapper.write_text(
            self.wrapper_source if wrapper_source is None else wrapper_source,
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        (library_dir / "context.sh").write_text(context_source, encoding="utf-8")
        allocator = scripts / "pty-capture.py"
        allocator.write_text(ALLOCATOR_STUB, encoding="utf-8")
        allocator.chmod(0o755)
        return wrapper, allocator, library_dir

    def environment(
        self,
        label: str,
    ) -> Tuple[Dict[str, str], Path, Path]:
        context_log = self.root / (label + "-context.log")
        allocator_log = self.root / (label + "-allocator.jsonl")
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        env.pop("UNLEASHED_LIB_DIR", None)
        env.update(
            {
                "HOME": str(self.home),
                "TMPDIR": str(self.root),
                "XDG_STATE_HOME": str(self.root / (label + "-state")),
                PLUGIN_DATA_KEY: str(self.root / (label + "-data")),
                "M5_CONTEXT_HASH": "Namespace-Exact_09",
                "M5_CONTEXT_LOG": str(context_log),
                "M5_CONTEXT_STATUS": "0",
                "M5_ALLOCATOR_LOG": str(allocator_log),
                "M5_ALLOCATOR_STATUS": "0",
            }
        )
        env.pop("M5_CONTEXT_STDERR", None)
        env.pop("M5_ALLOCATOR_STDERR", None)
        env.pop("M5_ALLOCATOR_STDOUT", None)
        return env, context_log, allocator_log

    def invoke(
        self,
        wrapper: Path,
        args: List[str],
        env: Dict[str, str],
        cwd: str = "/",
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(self.real_bash), str(wrapper)] + args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def records(path: Path) -> List[dict]:
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]

    def expected_allocator_argv(
        self,
        ticket: str,
        round_value: str,
        reviewer: str,
        repo_hash: str = "Namespace-Exact_09",
    ) -> List[str]:
        return [
            "--allocate",
            "--repo-hash",
            repo_hash,
            "--ticket",
            ticket,
            "--round",
            round_value,
            REVIEWER_FLAG,
            reviewer,
        ]

    def assert_hash_contract(self, source: str, label: str) -> None:
        local_context = CONTEXT_STUB.replace("M5_CONTEXT_", "M5_LOCAL_CONTEXT_")
        wrapper, _allocator, _library = self.make_wrapper_tree(
            label,
            wrapper_source=source,
            context_source=local_context,
        )
        seam = self.root / (label + "-seam")
        seam.mkdir()
        (seam / "context.sh").write_text(CONTEXT_STUB, encoding="utf-8")

        env, context_log, allocator_log = self.environment(label)
        local_log = self.root / (label + "-local-context.log")
        env.update(
            {
                "UNLEASHED_LIB_DIR": str(seam),
                "M5_LOCAL_CONTEXT_HASH": "Wrong-Local-Hash",
                "M5_LOCAL_CONTEXT_LOG": str(local_log),
                "M5_LOCAL_CONTEXT_STATUS": "0",
            }
        )

        first = self.invoke(wrapper, ["TicketA", "RoundA", "ReviewerA"], env)
        second = self.invoke(wrapper, ["TicketB", "RoundB", "ReviewerB"], env)
        self.assertEqual(
            [0, 0],
            [first.returncode, second.returncode],
            [first.stderr, second.stderr],
        )
        self.assertTrue(context_log.is_file(), "context_repo_hash was not called")
        self.assertEqual(
            ["called", "called"],
            context_log.read_text(encoding="utf-8").splitlines(),
        )
        self.assertFalse(local_log.exists(), "the explicit seam was ignored")

        records = self.records(allocator_log)
        self.assertEqual(2, len(records))
        expected_hash = env["M5_CONTEXT_HASH"]
        self.assertEqual(
            [
                self.expected_allocator_argv(
                    "TicketA", "RoundA", "ReviewerA", expected_hash
                ),
                self.expected_allocator_argv(
                    "TicketB", "RoundB", "ReviewerB", expected_hash
                ),
            ],
            [record["argv"] for record in records],
        )
        first_hash = records[0]["argv"][2]
        second_hash = records[1]["argv"][2]
        self.assertEqual(expected_hash, first_hash)
        self.assertEqual(first_hash, second_hash)

    def assert_signature_contract(self, source: str, label: str) -> None:
        wrapper, _allocator, _library = self.make_wrapper_tree(
            label,
            wrapper_source=source,
        )
        env, _context_log, allocator_log = self.environment(label)

        valid = self.invoke(wrapper, ["TicketField", "RoundField", "ReviewerField"], env)
        self.assertEqual(0, valid.returncode, valid.stderr)

        invalid_argv = (
            [],
            ["TicketField"],
            ["TicketField", "RoundField"],
            ["TicketField", "RoundField", "ReviewerField", "extra"],
            ["", "RoundField", "ReviewerField"],
            ["TicketField", "", "ReviewerField"],
            ["TicketField", "RoundField", ""],
        )
        for argv in invalid_argv:
            result = self.invoke(wrapper, list(argv), env)
            self.assertNotEqual(0, result.returncode, argv)
            self.assertEqual("", result.stdout, argv)
            self.assertNotEqual("", result.stderr, argv)

        records = self.records(allocator_log)
        self.assertEqual(1, len(records))
        self.assertEqual(
            self.expected_allocator_argv(
                "TicketField", "RoundField", "ReviewerField"
            ),
            records[0]["argv"],
        )

    def assert_allocator_shape(self, source: str, label: str) -> None:
        wrapper, _allocator, _library = self.make_wrapper_tree(
            label,
            wrapper_source=source,
        )
        env, _context_log, allocator_log = self.environment(label)
        result = self.invoke(wrapper, ["TicketShape", "RoundShape", "ReviewerShape"], env)
        self.assertEqual(0, result.returncode, result.stderr)
        records = self.records(allocator_log)
        self.assertEqual(1, len(records))
        self.assertEqual(
            self.expected_allocator_argv(
                "TicketShape", "RoundShape", "ReviewerShape"
            ),
            records[0]["argv"],
        )

    def assert_location_contract(self, source: str, label: str) -> None:
        wrapper, allocator, _library = self.make_wrapper_tree(
            label,
            wrapper_source=source,
        )
        env, context_log, allocator_log = self.environment(label)
        self.assertNotIn("CLAUDE_PLUGIN_ROOT", env)
        self.assertNotIn("UNLEASHED_LIB_DIR", env)
        self.assertNotEqual(WRAPPER_PATH.resolve(), wrapper.resolve())

        result = self.invoke(wrapper, ["TicketLoc", "RoundLoc", "ReviewerLoc"], env, cwd="/")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        self.assertEqual(
            "UNLEASHED_TRANSCRIPT=/fixture/transcript.txt\n",
            result.stdout,
        )
        self.assertTrue(context_log.is_file(), "the relocated context helper was not called")
        self.assertEqual("called\n", context_log.read_text(encoding="utf-8"))
        records = self.records(allocator_log)
        self.assertEqual(1, len(records))
        self.assertEqual(str(allocator.resolve()), records[0]["script"])
        self.assertEqual("/", records[0]["cwd"])

    def assert_marker_contract(self, source: str, label: str) -> None:
        wrapper, _allocator, _library = self.make_wrapper_tree(
            label,
            wrapper_source=source,
        )
        env, _context_log, _allocator_log = self.environment(label)
        correct = "UNLEASHED_TRANSCRIPT=/correct path/with:=[] value.txt\n"
        env["M5_ALLOCATOR_STDOUT"] = correct
        accepted = self.invoke(wrapper, ["TicketMarker", "RoundMarker", "Marker"], env)
        self.assertEqual(0, accepted.returncode, accepted.stderr)
        self.assertEqual(correct, accepted.stdout)
        self.assertEqual("", accepted.stderr)

        malformed = (
            "/bare/path.txt\n",
            "UNLEASHED_TRANSCRIPT=/path.txt\nunexpected output\n",
            "diagnostic output\nUNLEASHED_TRANSCRIPT=/path.txt\n",
            "UNLEASHED_TRANSCRIPT=\n",
        )
        for stream in malformed:
            env["M5_ALLOCATOR_STDOUT"] = stream
            rejected = self.invoke(
                wrapper,
                ["TicketMarker", "RoundMarker", "Marker"],
                env,
            )
            self.assertNotEqual(0, rejected.returncode, stream)
            self.assertEqual("", rejected.stdout, stream)
            self.assertIn("invalid marker stream", rejected.stderr, stream)

    def assert_exit_polarity_contract(self, source: str, label: str) -> None:
        wrapper, _allocator, _library = self.make_wrapper_tree(
            label,
            wrapper_source=source,
        )
        env, _context_log, allocator_log = self.environment(label)
        marker = "UNLEASHED_TRANSCRIPT=/success/path.txt\n"
        env["M5_ALLOCATOR_STDOUT"] = marker
        success = self.invoke(wrapper, ["TicketExit", "RoundExit", "ReviewerExit"], env)
        self.assertEqual(0, success.returncode, success.stderr)
        self.assertEqual(marker, success.stdout)

        env.update(
            {
                "M5_ALLOCATOR_STATUS": "23",
                "M5_ALLOCATOR_STDOUT": "UNLEASHED_TRANSCRIPT=/must-not-leak.txt\n",
                "M5_ALLOCATOR_STDERR": "allocator failed safely\n",
            }
        )
        allocator_failure = self.invoke(
            wrapper,
            ["TicketExit", "RoundExit", "ReviewerExit"],
            env,
        )
        self.assertEqual(23, allocator_failure.returncode)
        self.assertEqual("", allocator_failure.stdout)
        self.assertEqual("allocator failed safely\n", allocator_failure.stderr)

        before_context_failure = len(self.records(allocator_log))
        env.update(
            {
                "M5_CONTEXT_STATUS": "17",
                "M5_CONTEXT_HASH": "context-output-must-not-leak",
                "M5_CONTEXT_STDERR": "context failed safely\n",
                "M5_ALLOCATOR_STATUS": "0",
                "M5_ALLOCATOR_STDOUT": marker,
            }
        )
        env.pop("M5_ALLOCATOR_STDERR", None)
        context_failure = self.invoke(
            wrapper,
            ["TicketExit", "RoundExit", "ReviewerExit"],
            env,
        )
        self.assertEqual(17, context_failure.returncode)
        self.assertEqual("", context_failure.stdout)
        self.assertEqual("context failed safely\n", context_failure.stderr)
        self.assertEqual(before_context_failure, len(self.records(allocator_log)))


class M58AndM516LocationProofs(M5WrapperFixture):
    def test_M5_8_assertion_unset_shell_uses_relocated_wrapper_library(self) -> None:
        self.assert_location_contract(self.wrapper_source, "location-positive")

    def test_M5_8_plugin_root_cwd_and_original_library_mutations_are_rejected(self) -> None:
        fallback = (
            'LIB="${UNLEASHED_LIB_DIR:-$(CDPATH=\'\' cd -- '
            '"${SCRIPT_DIR}/../lib" && pwd)}"'
        )
        original_library = str((REPO / "scripts" / "lib").resolve())
        mutations = {
            "plugin-root-fallback": _replace_once(
                self.wrapper_source,
                fallback,
                'LIB="${UNLEASHED_LIB_DIR:-${CLAUDE_PLUGIN_ROOT}/scripts/lib}"',
            ),
            "cwd-fallback": _replace_once(
                self.wrapper_source,
                fallback,
                'LIB="${UNLEASHED_LIB_DIR:-$PWD/scripts/lib}"',
            ),
            "original-library": _replace_once(
                self.wrapper_source,
                fallback,
                'LIB="${UNLEASHED_LIB_DIR:-' + original_library + '}"',
            ),
        }
        for label, source in mutations.items():
            with self.subTest(mutation=label):
                with self.assertRaises(AssertionError):
                    self.assert_location_contract(source, "location-" + label)

    def test_M5_16_assertion_allocator_is_from_the_relocated_wrapper_tree(self) -> None:
        self.assert_location_contract(self.wrapper_source, "allocator-location-positive")

    def test_M5_16_cwd_allocator_mutation_is_rejected(self) -> None:
        mutant = _replace_once(
            self.wrapper_source,
            '    python3 "${SCRIPT_DIR}/../pty-capture.py" \\\n',
            '    python3 "$PWD/scripts/pty-capture.py" \\\n',
        )
        with self.assertRaises(AssertionError):
            self.assert_location_contract(mutant, "allocator-location-cwd")


class M55MarkerProofs(M5WrapperFixture):
    @staticmethod
    def marker_condition(source: str) -> str:
        matches = [
            line
            for line in source.splitlines()
            if line.startswith('if [[ "$allocator_output"')
        ]
        if len(matches) != 1:
            raise AssertionError("expected one marker-condition line")
        return matches[0]

    def test_M5_5_assertion_correct_marker_accepts_bare_and_extra_reject(self) -> None:
        self.assert_marker_contract(self.wrapper_source, "marker-positive")

    def test_M5_5_prefix_multiline_and_valid_rejection_mutations_are_rejected(self) -> None:
        condition = self.marker_condition(self.wrapper_source)
        mutations = {
            "bare-accepted": _replace_once(
                self.wrapper_source,
                condition,
                "if [[ \"$allocator_output\" == *$'\\n'* ]]; then",
            ),
            "extra-output-accepted": _replace_once(
                self.wrapper_source,
                condition,
                'if [[ "$allocator_output" != UNLEASHED_TRANSCRIPT=?* ]]; then',
            ),
            "valid-marker-rejected": _replace_once(
                self.wrapper_source,
                condition,
                'if [[ "$allocator_output" == UNLEASHED_TRANSCRIPT=?* ]]; then',
            ),
        }
        for label, source in mutations.items():
            with self.subTest(mutation=label):
                with self.assertRaises(AssertionError):
                    self.assert_marker_contract(source, "marker-" + label)


class M518ExitPolarityProofs(M5WrapperFixture):
    def test_M5_18_assertion_success_and_failure_streams_are_closed(self) -> None:
        self.assert_exit_polarity_contract(self.wrapper_source, "exit-positive")

    def test_M5_18_status_flattening_and_failed_output_leaks_are_rejected(self) -> None:
        exit_line = '    exit "$status"\n'
        mutations = {
            "allocator-output-leak": _replace_nth(
                self.wrapper_source,
                exit_line,
                '    printf \'%s\\n\' "$allocator_output"\n' + exit_line,
                2,
            ),
            "allocator-status-flattened": _replace_nth(
                self.wrapper_source,
                exit_line,
                "    exit 1\n",
                2,
            ),
            "context-output-leak": _replace_nth(
                self.wrapper_source,
                exit_line,
                '    printf \'%s\\n\' "$repo_hash"\n' + exit_line,
                1,
            ),
        }
        for label, source in mutations.items():
            with self.subTest(mutation=label):
                with self.assertRaises(AssertionError):
                    self.assert_exit_polarity_contract(source, "exit-" + label)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
