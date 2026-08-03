#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-WRAPPER proof cells."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "scripts" / "review" / "allocate-transcript.sh"

CONTEXT_STUB = """\
context_repo_hash() {
    printf '%s\\n' called >> "${WRAPPER_CONTEXT_LOG:?}"
    printf '%s' "${WRAPPER_CONTEXT_HASH:?}"
}
"""

ALLOCATOR_STUB = """\
#!/usr/bin/env python3
import json
import os
import pathlib
import sys

record = {
    "argv": sys.argv[1:],
    "script": str(pathlib.Path(__file__).resolve()),
}
with open(os.environ["WRAPPER_ALLOCATOR_RECORD"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\\n")
sys.stdout.write(
    os.environ.get(
        "WRAPPER_ALLOCATOR_STDOUT",
        "UNLEASHED_TRANSCRIPT=/fixture/transcript.txt\\n",
    )
)
sys.stderr.write(os.environ.get("WRAPPER_ALLOCATOR_STDERR", ""))
raise SystemExit(int(os.environ.get("WRAPPER_ALLOCATOR_STATUS", "0")))
"""


class WrapperFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".wrapper-proof-", dir=REPO)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)
        self.context_log = self.root / "context-calls.log"
        self.allocator_record = self.root / "allocator-records.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def make_relocated_tree(self, name: str = "relocated-plugin") -> tuple[Path, Path]:
        scripts = self.root / name / "scripts"
        review = scripts / "review"
        library = scripts / "lib"
        review.mkdir(parents=True)
        library.mkdir()

        relocated_wrapper = review / WRAPPER.name
        shutil.copyfile(WRAPPER, relocated_wrapper)
        (library / "context.sh").write_text(CONTEXT_STUB, encoding="utf-8")
        allocator = scripts / "pty-capture.py"
        allocator.write_text(ALLOCATOR_STUB, encoding="utf-8")
        return relocated_wrapper, allocator

    def environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        env.pop("UNLEASHED_LIB_DIR", None)
        env.update(
            {
                "HOME": str(self.home),
                "XDG_STATE_HOME": str(self.root / "state"),
                "WRAPPER_CONTEXT_HASH": "Context.Hash-Mixed_09",
                "WRAPPER_CONTEXT_LOG": str(self.context_log),
                "WRAPPER_ALLOCATOR_RECORD": str(self.allocator_record),
            }
        )
        return env

    @staticmethod
    def invoke(wrapper: Path, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(wrapper), *args],
            cwd="/",
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def allocator_records(self) -> list[dict[str, object]]:
        if not self.allocator_record.exists():
            return []
        return [json.loads(line) for line in self.allocator_record.read_text(encoding="utf-8").splitlines()]


class WrapperLocationTests(WrapperFixture):
    def test_M5_8_production_fallback_runs_from_root_with_plugin_root_and_seam_unset(self):
        """Rejects a production fallback based on cwd or CLAUDE_PLUGIN_ROOT."""
        env = self.environment()

        result = self.invoke(WRAPPER, ["COREDEV-2619", "85", "codex"], env)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("plugin state will not be read or written", result.stderr)
        self.assertTrue(result.stdout.endswith("\n"))
        self.assertEqual(1, len(result.stdout.splitlines()))
        marker = "UNLEASHED_TRANSCRIPT="
        self.assertTrue(result.stdout.startswith(marker), result.stdout)
        allocated = Path(result.stdout.removeprefix(marker).rstrip("\n"))
        self.assertTrue(allocated.is_file())
        self.assertTrue(Path(str(allocated) + ".launch").is_file())

    def test_M5_8_and_M5_16_relocated_wrapper_resolves_both_dependencies_from_own_location(self):
        """Rejects hard-coded original paths for either context.sh or pty-capture.py."""
        relocated_wrapper, relocated_allocator = self.make_relocated_tree()
        env = self.environment()
        marker = "UNLEASHED_TRANSCRIPT=/relocated path/with=equals.txt\n"
        env["WRAPPER_ALLOCATOR_STDOUT"] = marker

        result = self.invoke(relocated_wrapper, ["TicketA", "RoundB", "ReviewerC"], env)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(marker, result.stdout)
        self.assertEqual("", result.stderr)
        self.assertEqual("called\n", self.context_log.read_text(encoding="utf-8"))
        records = self.allocator_records()
        self.assertEqual(1, len(records))
        self.assertEqual(str(relocated_allocator.resolve()), records[0]["script"])


class WrapperInterfaceTests(WrapperFixture):
    def test_M5_3_hash_is_helper_derived_unchanged_and_stable_across_tickets(self):
        """Rejects a copied, hard-coded, normalized, or ticket-mixed repo hash."""
        relocated_wrapper, _allocator = self.make_relocated_tree()
        seam = self.root / "seam-lib"
        seam.mkdir()
        (seam / "context.sh").write_text(CONTEXT_STUB, encoding="utf-8")
        env = self.environment()
        env["UNLEASHED_LIB_DIR"] = str(seam)

        first = self.invoke(relocated_wrapper, ["TicketA", "RoundA", "ReviewerA"], env)
        second = self.invoke(relocated_wrapper, ["TicketB", "RoundB", "ReviewerB"], env)

        self.assertEqual([0, 0], [first.returncode, second.returncode], [first.stderr, second.stderr])
        self.assertEqual("called\ncalled\n", self.context_log.read_text(encoding="utf-8"))
        records = self.allocator_records()
        self.assertEqual(2, len(records))
        expected_hash = env["WRAPPER_CONTEXT_HASH"]
        self.assertEqual(
            [
                [
                    "--allocate",
                    "--repo-hash",
                    expected_hash,
                    "--ticket",
                    "TicketA",
                    "--round",
                    "RoundA",
                    "--reviewer",
                    "ReviewerA",
                ],
                [
                    "--allocate",
                    "--repo-hash",
                    expected_hash,
                    "--ticket",
                    "TicketB",
                    "--round",
                    "RoundB",
                    "--reviewer",
                    "ReviewerB",
                ],
            ],
            [record["argv"] for record in records],
        )
        self.assertNotIn("--base", records[0]["argv"])

    def test_M5_11_rejects_every_nonexact_or_empty_signature_without_allocating(self):
        """Rejects optional defaults, ignored extras, and validation of only some fields."""
        relocated_wrapper, _allocator = self.make_relocated_tree()
        env = self.environment()
        invalid_argv = (
            [],
            ["TicketA"],
            ["TicketA", "RoundA"],
            ["TicketA", "RoundA", "ReviewerA", "extra"],
            ["", "RoundA", "ReviewerA"],
            ["TicketA", "", "ReviewerA"],
            ["TicketA", "RoundA", ""],
        )

        for argv in invalid_argv:
            with self.subTest(argv=argv):
                result = self.invoke(relocated_wrapper, list(argv), env)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertNotEqual("", result.stderr)
        self.assertEqual([], self.allocator_records())

    def test_M5_18_nonzero_allocator_status_wins_before_marker_output_is_consumed(self):
        """Rejects exec-through or marker parsing that leaks stdout from a failed allocator."""
        relocated_wrapper, _allocator = self.make_relocated_tree()
        env = self.environment()
        env.update(
            {
                "WRAPPER_ALLOCATOR_STATUS": "23",
                "WRAPPER_ALLOCATOR_STDOUT": "UNLEASHED_TRANSCRIPT=/stale/review.txt\n",
                "WRAPPER_ALLOCATOR_STDERR": "forced allocator failure\n",
            }
        )

        result = self.invoke(relocated_wrapper, ["TicketA", "RoundA", "ReviewerA"], env)

        self.assertEqual(23, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertEqual("forced allocator failure\n", result.stderr)
        self.assertEqual(1, len(self.allocator_records()))

    def test_M5_5_malformed_success_streams_fail_closed_without_stdout(self):
        """Rejects accepting bare, empty, prefixed, or duplicate marker streams."""
        relocated_wrapper, _allocator = self.make_relocated_tree()
        env = self.environment()
        malformed_streams = (
            "/bare/transcript.txt\n",
            "UNLEASHED_TRANSCRIPT=\n",
            "diagnostic\nUNLEASHED_TRANSCRIPT=/fixture/transcript.txt\n",
            "UNLEASHED_TRANSCRIPT=/first.txt\nUNLEASHED_TRANSCRIPT=/second.txt\n",
        )

        for stream in malformed_streams:
            with self.subTest(stream=stream):
                env["WRAPPER_ALLOCATOR_STDOUT"] = stream
                result = self.invoke(relocated_wrapper, ["TicketA", "RoundA", "ReviewerA"], env)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn("invalid marker stream", result.stderr)
        self.assertEqual(len(malformed_streams), len(self.allocator_records()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
