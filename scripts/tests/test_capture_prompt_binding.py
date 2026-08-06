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
: > "${M5_CAPTURE_RAN:?}"
sleep "${M5_CAPTURE_DELAY:-0}"
exit 0
"""

CAPTURE_STUB_PY = """#!/usr/bin/env python3
import os, sys, time
open(os.environ["M5_CAPTURE_RAN"], "w").close()
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
        binder = REPO / "scripts" / "review" / "bind-prompt.py"
        shutil.copy2(binder, self.review / binder.name)
        (self.review / binder.name).chmod(0o755)
        # The helpers bind each transcript to the plan it reviewed, and `bind-prompt.py` requires both
        # operands to be non-symlink regular files INSIDE the repository (deep review, P1).
        self.plan = self.root / "FIXTURE_PLAN.md"
        self.plan.write_text("# fixture plan\n", encoding="utf-8")
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
        self.capture_ran = self.root / f"capture-ran-{reviewer}-{round_value}"
        env.update({
            "M5_LEAF_DIR": str(self.leaves),
            "M5_CAPTURE_DELAY": delay,
            "M5_CAPTURE_RAN": str(self.capture_ran),
        })
        return subprocess.run(
            [
                "bash",
                str(self.review / HELPERS[reviewer].name),
                "COREDEV-2619",
                round_value,
                str(prompt),
                str(self.plan),
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
                    # `bind-prompt.py` records the REPO-RELATIVE path: it is what a human reads in the
                    # sidecar, and an absolute path from another machine would be noise.
                    self.assertEqual(prompts[round_value].name, named)

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

    def test_a_failed_prompt_binding_aborts_before_the_reviewer_launches(self):
        """`set -uo pipefail` has no `-e`, so an unchecked redirect ran the whole review unbound.

        Reachable for real: the allocator reserved headroom only for `.launch`/`.captureid`, so a
        basename near NAME_MAX allocated fine and then failed to write `.promptsha256` with
        ENAMETOOLONG — a round completing with exit 0 and no record of which prompt it read. The
        reservation is fixed in `pty-capture.py`; this proves the helper ALSO refuses rather than
        proceeding, because the two defences fail independently.
        """
        for reviewer in HELPERS:
            with self.subTest(reviewer=reviewer):
                prompt = self.root / f".{reviewer}-prompt-COREDEV-2619r9.md"
                prompt.write_text("a prompt\n", encoding="utf-8")
                # A leaf whose name leaves no room for the sidecar suffix.
                limit = os.pathconf(str(self.leaves), "PC_NAME_MAX")
                long_dir = self.root / f"long-{reviewer}"
                long_dir.mkdir()
                env = dict(os.environ)
                env.update({
                    "M5_LEAF_DIR": str(long_dir),
                    "M5_CAPTURE_DELAY": "0",
                    "M5_CAPTURE_RAN": str(self.root / f"ran-{reviewer}"),
                })
                # The stub names the leaf `<reviewer>-<round>.txt`; pad the round so the basename sits
                # at the limit and any suffix overflows.
                pad = limit - len(f"{reviewer}-.txt")
                result = subprocess.run(
                    ["bash", str(self.review / HELPERS[reviewer].name),
                     "COREDEV-2619", "9" * pad, str(prompt), str(self.plan), "60"],
                    cwd=str(self.root), env=env, capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(
                    0, result.returncode, "an unrecordable prompt binding must not run the review"
                )
                self.assertIn("binding could not be established", result.stderr)
                self.assertFalse(
                    (self.root / f"ran-{reviewer}").exists(),
                    "the reviewer launched despite an unrecordable prompt binding",
                )

    def test_an_out_of_repo_prompt_is_refused_before_the_reviewer_sees_it(self):
        """The exfiltration path: a pre-approved entrypoint reading anything the model names.

        `codex-review` is model-invocable and grants `capture-codex-review.sh *`, so the model chooses
        this operand. The old `-r`/`-s` pair accepted `../secret`, and `$(cat "$PROMPT")` then shipped
        those bytes to the reviewer CLI verbatim — reproduced by the deep review with a Codex stub.

        Asserted on the reviewer never launching, not merely on the exit code: a refusal that happens
        after the CLI has already received the bytes is not a refusal.
        """
        outside = self.root.parent / f"outside-secret-{self.root.name}.txt"
        outside.write_text("SECRET MATERIAL\n", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        link = self.root / ".codex-prompt-COREDEV-2619r9.md"
        link.symlink_to(outside)

        for reviewer, operand in (("codex", str(outside)), ("codex", str(link))):
            with self.subTest(operand=operand):
                ran = self.root / f"ran-{reviewer}-exfil"
                env = dict(os.environ)
                env.update({
                    "M5_LEAF_DIR": str(self.leaves), "M5_CAPTURE_DELAY": "0",
                    "M5_CAPTURE_RAN": str(ran),
                })
                result = subprocess.run(
                    ["bash", str(self.review / HELPERS[reviewer].name),
                     "COREDEV-2619", "9", operand, str(self.plan), "60"],
                    cwd=str(self.root), env=env, capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(0, result.returncode, result.stdout)
                self.assertFalse(ran.exists(), "the reviewer received an out-of-repo prompt")

    def test_a_prompt_inside_the_repo_is_still_accepted(self):
        """The positive control — containment must not be refusing everything."""
        prompt = self.root / ".codex-prompt-COREDEV-2619r11.md"
        prompt.write_text("a legitimate in-repo prompt\n", encoding="utf-8")
        result = self._run("codex", "11", prompt)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.leaves / "codex-11.txt.plan").is_file())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
