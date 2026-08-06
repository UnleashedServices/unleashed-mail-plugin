#!/usr/bin/env python3
"""Two concurrent rounds must not cross-wire prompt and transcript (deep review, P1).

COREDEV-2619 names `.agy-prompt.md` / `.codex-prompt.md` as the same-checkout collision, but the
shipped recipes kept using those fixed files. Two concurrent rounds each received a UNIQUE transcript
leaf while the second overwrote the shared prompt before the first wrapper read it — so the first run
recorded a fresh, valid transcript for the OTHER plan under its own ticket and round, defeating the
evidence association the per-run work exists to establish.

Two properties, proved separately because they fail separately:

  * the RECIPES derive the prompt name from TICKET and ROUND, so two rounds cannot name one file; and
  * the HELPERS bind the prompt they were handed to the transcript they allocated, so a cross-wire is
    detectable even if one is somehow contrived.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
HELPERS = {
    "codex": REPO / "scripts" / "review" / "capture-codex-review.sh",
    "gemini": REPO / "scripts" / "review" / "capture-gemini-review.sh",
}
RECIPES = {
    "codex": (
        REPO / "skills" / "codex-review" / "SKILL.md",
        "# COREDEV2619_CODEX_CAPTURE_BEGIN",
        "# COREDEV2619_CODEX_CAPTURE_END",
    ),
    "gemini": (
        REPO / "skills" / "gemini-review" / "SKILL.md",
        "# COREDEV2619_GEMINI_CAPTURE_BEGIN",
        "# COREDEV2619_GEMINI_CAPTURE_END",
    ),
}

ALLOCATOR_STUB = """#!/usr/bin/env bash
# ticket=$1 round=$2 reviewer=$3 — one reserved leaf per (reviewer, round), like the real allocator.
leaf="${M5_LEAF_DIR:?}/${3}-${2}.txt"
: > "$leaf"
printf 'UNLEASHED_TRANSCRIPT=%s\\n' "$leaf"
"""

# The two arms hand off to different backends, so each needs a stub in its own language: codex execs
# `python3 pty-capture.py`, gemini execs `bash isolated-agy-review.sh`.
CAPTURE_STUB_SH = """#!/usr/bin/env bash
sleep "${M5_CAPTURE_DELAY:-0}"
exit 0
"""

CAPTURE_STUB_PY = """#!/usr/bin/env python3
import os, sys, time
time.sleep(float(os.environ.get("M5_CAPTURE_DELAY", "0")))
sys.exit(0)
"""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CapturePromptBindingTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        if shutil.which("bash") is None:
            self.skipTest("bash is required")
        self.temporary = tempfile.TemporaryDirectory(prefix=".prompt-binding-")
        self.root = Path(self.temporary.name)
        self.review = self.root / "scripts" / "review"
        self.review.mkdir(parents=True)
        self.leaves = self.root / "leaves"
        self.leaves.mkdir()

        for path in HELPERS.values():
            shutil.copy2(path, self.review / path.name)
            (self.review / path.name).chmod(0o755)
        for name, payload in (
            ("allocate-transcript.sh", ALLOCATOR_STUB),
            ("isolated-agy-review.sh", CAPTURE_STUB_SH),
        ):
            (self.review / name).write_text(payload, encoding="utf-8")
            (self.review / name).chmod(0o755)
        capture = self.root / "scripts" / "pty-capture.py"
        capture.write_text(CAPTURE_STUB_PY, encoding="utf-8")
        capture.chmod(0o755)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, reviewer: str, round_value: str, prompt: Path, delay: str = "0"):
        env = dict(os.environ)
        env.update({"M5_LEAF_DIR": str(self.leaves), "M5_CAPTURE_DELAY": delay})
        return subprocess.run(
            [
                "bash",
                str(self.review / HELPERS[reviewer].name),
                "COREDEV-2619",
                round_value,
                str(prompt),
                "60",
            ],
            cwd=str(self.root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_concurrent_rounds_each_bind_their_own_prompt(self):
        """The interleaving the finding describes, run for real.

        Round 7 is delayed inside its capture so round 8 completes entirely while round 7 is still in
        flight — the window in which a shared prompt would have been overwritten. Each round must end
        up bound to the prompt IT was given.
        """
        for reviewer in HELPERS:
            with self.subTest(reviewer=reviewer):
                prompts = {}
                for round_value, body in (("7", "round seven prompt\n"), ("8", "round eight prompt\n")):
                    prompt = self.root / f".{reviewer}-prompt-COREDEV-2619r{round_value}.md"
                    prompt.write_text(body, encoding="utf-8")
                    prompts[round_value] = prompt
                self.assertNotEqual(
                    _sha256(prompts["7"]),
                    _sha256(prompts["8"]),
                    "the two prompts must differ, or binding proves nothing",
                )

                results = {}

                def run(round_value, delay):
                    results[round_value] = self._run(
                        reviewer, round_value, prompts[round_value], delay
                    )

                slow = threading.Thread(target=run, args=("7", "1"))
                slow.start()
                run("8", "0")
                slow.join()

                for round_value in ("7", "8"):
                    self.assertEqual(0, results[round_value].returncode, results[round_value].stderr)
                    leaf = self.leaves / f"{reviewer}-{round_value}.txt"
                    record = Path(str(leaf) + ".promptsha256")
                    self.assertTrue(record.is_file(), f"no prompt binding for round {round_value}")
                    digest, _, named = record.read_text(encoding="utf-8").strip().partition("  ")
                    self.assertEqual(
                        _sha256(prompts[round_value]),
                        digest,
                        f"round {round_value} recorded another round's prompt",
                    )
                    self.assertEqual(str(prompts[round_value]), named)

    def test_each_recipe_names_its_prompt_from_ticket_and_round(self):
        """Structural half: two rounds cannot name one prompt file.

        Asserted by EXPANDING the recipe's prompt operand for two different rounds and requiring the
        results to differ — a shared literal passes any "does it mention a prompt" check, but cannot
        pass this one.
        """
        for reviewer, (path, begin, end) in RECIPES.items():
            with self.subTest(reviewer=reviewer):
                source = path.read_text(encoding="utf-8")
                start = source.index(begin) + len(begin)
                recipe = source[start : source.index(end, start)].strip()
                match = re.search(r'"(\.[a-z]+-prompt[^"]*\.md)"', recipe)
                self.assertIsNotNone(
                    match, f"{path.name}: the recipe names no quoted prompt operand: {recipe!r}"
                )
                template = match.group(1)

                def expand(round_value):
                    return subprocess.run(
                        ["bash", "-c", f'TICKET=COREDEV-2619 ROUND={round_value}; printf "%s" "{template}"'],
                        capture_output=True,
                        text=True,
                        check=True,
                    ).stdout

                first, second = expand("7"), expand("8")
                self.assertNotEqual(
                    first,
                    second,
                    f"{path.name}: rounds 7 and 8 name the SAME prompt file ({first!r}) — this is the "
                    "shared-prompt cross-wire",
                )
                for produced in (first, second):
                    self.assertNotIn("${", produced, "the operand did not expand")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
