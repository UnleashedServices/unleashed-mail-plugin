#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-THREAD proof cells."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple


REPO = Path(__file__).resolve().parents[2]
ALLOCATE = REPO / "scripts" / "review" / "allocate-transcript.sh"
ISOLATED_AGY = REPO / "scripts" / "review" / "isolated-agy-review.sh"
ISOLATED_CODEX = REPO / "scripts" / "review" / "isolated-codex-review.sh"
STAGE_BOUND_PLAN = REPO / "scripts" / "review" / "stage-bound-plan.py"
STAGE_PROMPT = REPO / "scripts" / "review" / "stage-prompt.py"
#: Every shipped file under `scripts/review/`, so the relocated-copy fixture cannot fall behind a new
#: shared sibling again.
REVIEW_DIR = REPO / "scripts" / "review"
PTY_CAPTURE = REPO / "scripts" / "pty-capture.py"
REVIEW_VERDICT = REPO / "scripts" / "review-verdict.py"

PERSIST_HELPER = REPO / "scripts" / "review" / "persist-verdict.sh"
CAPTURE_CODEX = REPO / "scripts" / "review" / "capture-codex-review.sh"
CAPTURE_GEMINI = REPO / "scripts" / "review" / "capture-gemini-review.sh"
PLAN_RELATIVE = "docs/planning/FEATURE_PLAN.md"
BIND_PROMPT = REPO / "scripts" / "review" / "bind-prompt.py"
CONTAINMENT = REPO / "scripts" / "review" / "containment.py"

def verdict_module():
    """The SHIPPED `review-verdict.py`, loaded as a module.

    Proof cells that hand-build evidence read the gate's own compiled grammars from here instead of
    respelling them, so a fixture fails on the rule it names rather than on a layout it restated.
    """
    spec = importlib.util.spec_from_file_location(
        "review_verdict_under_proof", str(REVIEW_VERDICT)
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not load " + str(REVIEW_VERDICT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The recipes name a PER-ROUND prompt file, so the fixture repo must carry the ones the
# fixture's TICKET/ROUND produce. A shared name was the cross-wiring hazard (deep review, P1).
FIXTURE_TICKET = "COREDEV-2619"
FIXTURE_ROUND = "85"

GEMINI_SKILL = REPO / "skills" / "gemini-review" / "SKILL.md"
CODEX_SKILL = REPO / "skills" / "codex-review" / "SKILL.md"
BRAINSTORM_SKILL = REPO / "skills" / "brainstorm" / "SKILL.md"
SYNTHESIS_SKILL = REPO / "skills" / "review-synthesis" / "SKILL.md"

GEMINI_BEGIN = "# COREDEV2619_GEMINI_CAPTURE_BEGIN"
GEMINI_END = "# COREDEV2619_GEMINI_CAPTURE_END"
CODEX_BEGIN = "# COREDEV2619_CODEX_CAPTURE_BEGIN"
CODEX_END = "# COREDEV2619_CODEX_CAPTURE_END"
BRAINSTORM_BEGIN = "# COREDEV2619_BRAINSTORM_PERSIST_BEGIN"
BRAINSTORM_END = "# COREDEV2619_BRAINSTORM_PERSIST_END"
SYNTHESIS_BEGIN = "# COREDEV2619_SYNTHESIS_PERSIST_BEGIN"
SYNTHESIS_END = "# COREDEV2619_SYNTHESIS_PERSIST_END"


WRITER_SHIM = r'''#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
if args and args[0] == "--allocate":
    os.execv(
        sys.executable,
        [sys.executable, os.environ["THREAD_REAL_ALLOCATOR"]] + args,
    )

record = {
    "argv": args,
    "cwd": os.getcwd(),
    "script": str(pathlib.Path(__file__).resolve()),
}
with open(os.environ["THREAD_CAPTURE_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\n")

separator = args.index("--")
pre = args[:separator]
allocated_index = pre.index("--allocated")
out_path = pre[allocated_index + 1]
reviewer = os.environ["THREAD_REVIEWER"]
payload = (reviewer + " review\nVERDICT: APPROVE\n").encode("utf-8")
pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "wb") as stream:
    stream.write(payload)
with open(out_path + ".captureid", "w", encoding="utf-8") as stream:
    stream.write("capture-" + reviewer + "\n")
'''


BASH_SHIM = r'''#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
# Both isolation harnesses are logged: the codex arm now runs `isolated-codex-review.sh` for the same
# reason the gemini arm runs `isolated-agy-review.sh` — review a disposable checkout with the bound
# plan staged, never the live file (PR #63 recheck, P1). Symmetric handling here keeps the helper-log
# assertions symmetric.
if args and pathlib.Path(args[0]).name in ("isolated-agy-review.sh", "isolated-codex-review.sh"):
    with open(os.environ["THREAD_HELPER_LOG"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps(args) + "\n")
    clean_env = dict(os.environ)
    clean_env.pop("CLAUDE_PLUGIN_ROOT", None)
    os.execve(os.environ["THREAD_REAL_BASH"], [os.environ["THREAD_REAL_BASH"]] + args, clean_env)
os.execv(os.environ["THREAD_REAL_BASH"], [os.environ["THREAD_REAL_BASH"]] + args)
'''


PYTHON_SHIM = r'''#!/bin/sh
if [ "${1-}" = "${THREAD_REVIEW_VERDICT-}" ] && [ "${2-}" = "write" ]; then
    : > "${THREAD_VERDICT_ARGV_LOG:?}"
    for argument in "$@"; do
        printf '%s\n' "$argument" >> "$THREAD_VERDICT_ARGV_LOG"
    done
fi
exec "${THREAD_REAL_PYTHON:?}" "$@"
'''


def extract_recipe(path: Path, begin: str, end: str) -> str:
    source = path.read_text(encoding="utf-8")
    if source.count(begin) != 1 or source.count(end) != 1:
        raise AssertionError(f"{path}: expected one {begin!r}/{end!r} recipe region")
    start = source.index(begin) + len(begin)
    finish = source.index(end, start)
    return source[start:finish].strip() + "\n"


def run_checked(argv: List[str], cwd: Path, env: Dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )



def write_prompt_binding(transcript) -> None:
    """Write the `.prompt` snapshot and `.promptsha256` that `bind-prompt.py` produces alongside `.plan`.

    `write` REQUIRES the prompt binding for a per-run transcript rather than skipping when it is
    absent — skipping meant deleting the sidecar turned the check off, the same "absent means
    unchecked" fail-open the plan binding exists to close (PR #63 recheck). All three sidecars are
    written together by the capture helper, so a fixture producing only `.plan` models a transcript no
    helper ever made.
    """
    payload = b"review prompt\n"
    Path(str(transcript) + ".prompt").write_bytes(payload)
    Path(str(transcript) + ".promptsha256").write_text(
        hashlib.sha256(payload).hexdigest() + "  prompt.md\n", encoding="utf-8"
    )


class TranscriptThreadingFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".thread-proof-", dir=str(REPO))
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)
        self.tmpdir = self.root / "tmp"
        self.tmpdir.mkdir(mode=0o700)
        self.reviewed = self.root / "reviewed app without plugin writer"
        self.plugin = self.root / "relocated plugin copy"
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.capture_log = self.root / "capture.jsonl"
        self.helper_log = self.root / "helper.jsonl"
        self.verdict_argv_log = self.root / "verdict-argv.txt"

        self.real_bash = shutil.which("bash")
        self.real_python = sys.executable
        if self.real_bash is None:
            self.skipTest("bash is required")

        self._make_reviewed_repo()
        self._make_relocated_plugin()
        self._write_executable(self.bin_dir / "bash", BASH_SHIM)
        self._write_executable(self.bin_dir / "python3", PYTHON_SHIM)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _write_executable(path: Path, payload: str) -> None:
        path.write_text(payload, encoding="utf-8")
        path.chmod(0o755)

    def _make_reviewed_repo(self) -> None:
        self.reviewed.mkdir()
        # The prompt must NAME the plan it reviews. `bind-prompt.py` refuses a prompt that names a
        # different `*_PLAN.md`, or none at all — a prompt saying `REVIEW TARGET: PLAN_B` bound cleanly
        # to `--plan PLAN_A` and produced an APPROVE artifact for the wrong plan (PR #63 recheck, P1).
        # A path-threading fixture still has to be a legitimate review request.
        prompt = (
            "# Review fixture\n\nREVIEW TARGET: FEATURE_PLAN.md\n\n"
            + ("read-only fixture material\n" * 80)
        )
        (self.reviewed / ".agy-prompt.md").write_text(prompt, encoding="utf-8")
        # The codex arm's prompt file was never created here. The old inline recipe passed
        # `$(cat .codex-prompt.md)`, which expands EMPTY on a missing file, so every codex capture
        # proof had been running against an empty prompt without failing — `capture-codex-review.sh`
        # checks the prompt is readable and non-empty, and that is what surfaced it.
        codex_prompt = f".codex-prompt-{FIXTURE_TICKET}r{FIXTURE_ROUND}.md"
        agy_prompt = f".agy-prompt-{FIXTURE_TICKET}r{FIXTURE_ROUND}.md"
        (self.reviewed / codex_prompt).write_text(prompt, encoding="utf-8")
        (self.reviewed / agy_prompt).write_text(prompt, encoding="utf-8")
        # UNDER docs/planning. The granted `snapshot-plan.sh` / `persist-verdict.sh` entrypoints now
        # require it there (PR #63 recheck, P1): both accepted a plan anywhere on disk, and even a
        # non-approving persist created a `.verdicts` directory beside it — reproduced against `/tmp`,
        # walking past the skill's apparent `Write(docs/planning/**)` boundary with no user gesture.
        # A fixture that keeps its plan at the repo root is modelling a layout the gate no longer allows.
        (self.reviewed / "docs" / "planning").mkdir(parents=True, exist_ok=True)
        (self.reviewed / PLAN_RELATIVE).write_text("# Plan\nThread paths.\n", encoding="utf-8")
        env = dict(os.environ)
        commands = (
            ["git", "init", "-q"],
            ["git", "config", "user.name", "Fixture"],
            ["git", "config", "user.email", "fixture@example.invalid"],
            ["git", "add", ".agy-prompt.md", codex_prompt, agy_prompt, PLAN_RELATIVE],
            ["git", "commit", "-q", "-m", "fixture"],
        )
        for command in commands:
            result = run_checked(list(command), self.reviewed, env)
            self.assertEqual(0, result.returncode, result.stderr)

    def _make_relocated_plugin(self) -> None:
        review_dir = self.plugin / "scripts" / "review"
        library_dir = self.plugin / "scripts" / "lib"
        review_dir.mkdir(parents=True)
        library_dir.mkdir()
        # THE WHOLE DIRECTORY, DERIVED — not a hand-kept list. This fixture had learned about a new
        # shared sibling THREE times, each with its own comment saying so, and the fourth was
        # `tree-fingerprint.sh`: the harnesses source it, the relocated copy did not have it, and the
        # only reason that had not already failed loudly is that the fingerprint swallowed its own
        # errors — the fail-closed fix landing in this same commit is what surfaced it. Enumeration is
        # not the class. Copying every file the review directory ships makes a new sibling automatic,
        # and the cost is a few kilobytes.
        for source in sorted(REVIEW_DIR.iterdir()):
            if source.is_file():
                shutil.copy2(source, review_dir / source.name)
        shutil.copy2(REPO / "scripts" / "lib" / "context.sh", library_dir / "context.sh")
        self._write_executable(self.plugin / "scripts" / "pty-capture.py", WRITER_SHIM)

    def install_capture_helper(self, source: str, reviewer: str = "codex") -> None:
        """Replace the staged `capture-codex-review.sh` with `source`.

        The codex capture rules moved out of the skill body into that script, so an M5 mutant now has
        to replace the script the recipe calls rather than edit the recipe text. The recipe under test
        stays the shipped one, which is the point.
        """
        name = CAPTURE_CODEX.name if reviewer == "codex" else CAPTURE_GEMINI.name
        self._write_executable(self.plugin / "scripts" / "review" / name, source)

    def environment(
        self,
        base: Path,
        reviewer: str,
        use_xdg: bool = True,
        home: Optional[Path] = None,
    ) -> Dict[str, str]:
        if use_xdg:
            base.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.pop("UNLEASHED_LIB_DIR", None)
        if use_xdg:
            env["XDG_STATE_HOME"] = str(base)
        else:
            env.pop("XDG_STATE_HOME", None)
        env.update(
            {
                "CLAUDE_PLUGIN_ROOT": str(self.plugin),
                "HOME": str(home or self.home),
                "TMPDIR": str(self.tmpdir),
                "TICKET": "COREDEV-2619",
                "ROUND": "85",
                # The capture helpers now bind the transcript to the plan it reviewed, so the recipe
                # needs the plan operand and `bind-prompt.py` contains it to this repo.
                "PLAN": PLAN_RELATIVE,
                "THREAD_CAPTURE_LOG": str(self.capture_log),
                "THREAD_HELPER_LOG": str(self.helper_log),
                "THREAD_REAL_ALLOCATOR": str(PTY_CAPTURE),
                "THREAD_REAL_BASH": str(self.real_bash),
                "THREAD_REAL_PYTHON": str(self.real_python),
                "THREAD_REVIEWER": reviewer,
                "PATH": str(self.bin_dir) + os.pathsep + env.get("PATH", ""),
            }
        )
        return env

    def run_capture_recipe(
        self,
        reviewer: str,
        base: Path,
        use_xdg: bool = True,
        home: Optional[Path] = None,
    ) -> Tuple[str, dict, List[List[str]]]:
        if reviewer == "gemini":
            recipe = extract_recipe(GEMINI_SKILL, GEMINI_BEGIN, GEMINI_END)
        elif reviewer == "codex":
            recipe = extract_recipe(CODEX_SKILL, CODEX_BEGIN, CODEX_END)
        else:
            raise AssertionError(f"unsupported reviewer fixture: {reviewer}")

        for log in (self.capture_log, self.helper_log):
            if log.exists():
                log.unlink()
        result = run_checked(
            [str(self.real_bash), "-c", recipe],
            self.reviewed,
            self.environment(base, reviewer, use_xdg=use_xdg, home=home),
        )
        self.assertEqual(0, result.returncode, result.stderr)

        marker_prefix = "UNLEASHED_TRANSCRIPT="
        markers = [line for line in result.stdout.splitlines() if line.startswith(marker_prefix)]
        self.assertEqual(1, len(markers), result.stdout)
        allocated = markers[0][len(marker_prefix):]
        records = [json.loads(line) for line in self.capture_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(1, len(records), records)
        helper_records = []
        if self.helper_log.exists():
            helper_records = [
                json.loads(line) for line in self.helper_log.read_text(encoding="utf-8").splitlines()
            ]
        return allocated, records[0], helper_records

    def allocate_empty(self, reviewer: str, base: Path) -> str:
        env = self.environment(base, reviewer)
        result = run_checked(
            [str(self.real_bash), str(ALLOCATE), "COREDEV-2619", "85", reviewer],
            self.reviewed,
            env,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        prefix = "UNLEASHED_TRANSCRIPT="
        self.assertTrue(result.stdout.startswith(prefix), result.stdout)
        return result.stdout[len(prefix):].rstrip("\n")

    def bind_transcript_to_plan(self, *transcripts: str) -> None:
        """Write the `.plan` sidecar the capture helper would have written.

        `write` refuses an APPROVING verdict whose per-run transcript is not bound to the plan being
        approved (deep review, P1) — transcripts allocated for an unrelated ticket used to satisfy
        this gate. Cells that hand-build a transcript rather than running the capture helper must
        therefore supply the binding themselves, or they witness that refusal instead of the property
        they are named for.
        """
        plan = self.reviewed / PLAN_RELATIVE
        digest = hashlib.sha256(plan.read_bytes()).hexdigest()
        # The REPO-RELATIVE identity, not the basename: `bind-prompt.py` records
        # `relpath(plan, root)`, and the verdict writer compares every recorded identity now that the
        # separator-free exemption is gone (PR #63 recheck). `plan.name` would drop `docs/planning/`
        # and make these cells fail on the binding rather than on the path threading they test.
        for transcript in transcripts:
            Path(str(transcript) + ".plan").write_text(
                f"{digest}  {PLAN_RELATIVE}\n", encoding="utf-8"
            )
            # `.planbytes` as well: `write` reads the snapshot and requires it to hash to the record,
            # because the snapshot is what the reviewer was actually fed and nothing downstream had
            # ever compared it (PR #63 recheck, P1).
            Path(str(transcript) + ".planbytes").write_bytes(plan.read_bytes())
            write_prompt_binding(transcript)

    def run_persistence_recipe(
        self,
        recipe: str,
        bindings: Dict[str, str],
        helper_source: Optional[str] = None,
    ) -> Tuple[dict, List[str]]:
        """Run a persistence recipe through the real `persist-verdict.sh`.

        `helper_source` stages a MUTATED copy of that helper under a private plugin root and points
        `CLAUDE_PLUGIN_ROOT` at it. The persistence rule used to be inline in each SKILL body, so the
        M5 mutants edited the extracted recipe string; now that it lives in one committed script, a
        mutant has to replace the script the recipe calls. The recipe under test is unchanged either
        way — that is the point, since the recipe is what the skill actually ships.
        """
        plan = self.reviewed / PLAN_RELATIVE

        snapshot = run_checked(
            [sys.executable, str(REVIEW_VERDICT), "snapshot", "--plan", str(plan)],
            self.reviewed,
            dict(os.environ),
        )
        self.assertEqual(0, snapshot.returncode, snapshot.stderr)

        plugin_root = REPO
        review_verdict = REVIEW_VERDICT
        if helper_source is not None:
            plugin_root = self.stage_plugin_root(helper_source)
            review_verdict = plugin_root / "scripts" / "review-verdict.py"

        env = dict(os.environ)
        env.update(
            {
                "CLAUDE_PLUGIN_ROOT": str(plugin_root),
                "PLAN_PATH": str(plan),
                "CREATED_AT": "2026-08-03T12:00:00Z",
                # The recipe now calls `bash …/persist-verdict.sh`, so it goes through the same bash
                # shim as the capture arms; without this the shim raises KeyError on its own env.
                "THREAD_REAL_BASH": str(self.real_bash),
                "THREAD_REAL_PYTHON": str(self.real_python),
                "THREAD_REVIEW_VERDICT": str(review_verdict),
                "THREAD_VERDICT_ARGV_LOG": str(self.verdict_argv_log),
                "PATH": str(self.bin_dir) + os.pathsep + env.get("PATH", ""),
            }
        )
        env.update(bindings)
        result = run_checked([str(self.real_bash), "-c", recipe], self.reviewed, env)
        self.assertEqual(0, result.returncode, result.stderr)

        artifact = (self.reviewed / "docs" / "planning" / ".verdicts"
                    / "FEATURE_PLAN.md.verdict.json")
        self.assertTrue(artifact.is_file(), result.stdout + result.stderr)
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        argv = self.verdict_argv_log.read_text(encoding="utf-8").splitlines()
        return payload, argv

    def stage_plugin_root(self, helper_source: str) -> Path:
        """A private plugin root whose `persist-verdict.sh` is `helper_source`.

        Only the helper is staged: the recipe reaches `review-verdict.py` THROUGH it, and the shims on
        PATH intercept `python3`, so nothing else in the tree has to be copied. The helper resolves the
        writer relative to its own location, which is exactly what makes this substitution possible.
        """
        self.staged_roots = getattr(self, "staged_roots", 0) + 1
        root = self.root / f"staged-plugin-root-{self.staged_roots}"
        review = root / "scripts" / "review"
        review.mkdir(parents=True)
        helper = review / "persist-verdict.sh"
        helper.write_text(helper_source, encoding="utf-8")
        helper.chmod(0o755)
        return root

    def run_synthesis(
        self,
        gemini_spec: str,
        codex_spec: str,
        combined_verdict: str,
        helper_source: Optional[str] = None,
    ) -> Tuple[dict, List[str]]:
        return self.run_persistence_recipe(
            extract_recipe(SYNTHESIS_SKILL, SYNTHESIS_BEGIN, SYNTHESIS_END),
            {
                "COMBINED_VERDICT": combined_verdict,
                "GEMINI_REVIEWER_SPEC": gemini_spec,
                "CODEX_REVIEWER_SPEC": codex_spec,
            },
            helper_source=helper_source,
        )

    def run_brainstorm_persistence(
        self,
        gemini_path: str,
        codex_path: str,
    ) -> Tuple[dict, List[str]]:
        return self.run_persistence_recipe(
            extract_recipe(BRAINSTORM_SKILL, BRAINSTORM_BEGIN, BRAINSTORM_END),
            {
                "COMBINED_VERDICT": "APPROVE",
                "GEMINI_STATUS": "APPROVE",
                "GEMINI_TRANSCRIPT": gemini_path,
                "CODEX_STATUS": "APPROVE",
                "CODEX_TRANSCRIPT": codex_path,
            },
        )

    def assert_artifact_paths(self, artifact: dict, gemini_path: str, codex_path: str) -> None:
        by_name = {reviewer["name"]: reviewer for reviewer in artifact["reviewers"]}
        self.assertEqual(gemini_path, by_name["gemini"]["transcriptPath"])
        self.assertEqual(codex_path, by_name["codex"]["transcriptPath"])

    @staticmethod
    def reviewer_values(argv: List[str]) -> List[str]:
        return [argv[index + 1] for index, value in enumerate(argv) if value == "--reviewer"]


class TranscriptPathPropagationTests(TranscriptThreadingFixture):
    def test_M5_1_M5_6_both_arms_and_consumers_preserve_one_opaque_argument(self) -> None:
        """Rejects unquoted/re-derived handoffs in capture, synthesis, brainstorm, or artifact."""
        hostile_base = self.root / "state space\tglob[*]?\\single' double\" colon: equals="

        gemini_path, gemini_capture, gemini_helpers = self.run_capture_recipe("gemini", hostile_base)
        codex_path, codex_capture, codex_helpers = self.run_capture_recipe("codex", hostile_base)

        expected_prefix = str(hostile_base.resolve()) + os.sep
        self.assertTrue(gemini_path.startswith(expected_prefix), gemini_path)
        self.assertTrue(codex_path.startswith(expected_prefix), codex_path)
        # BOTH arms now go through an isolation harness, so both leave exactly one helper record with
        # the five-operand contract (harness, prompt SNAPSHOT, transcript, timeout, plan). The codex arm
        # gained the gemini arm's isolation so a plan swap cannot reach the reviewer (PR #63 recheck, P1).
        self.assertEqual(1, len(gemini_helpers), gemini_helpers)
        self.assertEqual(1, len(codex_helpers), codex_helpers)
        self.assertEqual(
            [
                str(self.plugin / "scripts" / "review" / "isolated-codex-review.sh"),
                codex_path + ".prompt",
                codex_path,
            ],
            codex_helpers[0][:3],
        )
        self.assertEqual(5, len(codex_helpers[0]), codex_helpers[0])
        self.assertEqual(PLAN_RELATIVE, codex_helpers[0][4], "the bound plan is not handed to the codex harness")
        # The first three operands are a fixed contract. The timeout is NOT asserted as a literal --
        # see _assert_recipe_timeout_exceeds_print_timeout below for why.
        #
        # OPERAND 2 CHANGED, and the change is the point. It was the caller's prompt PATH; it is now
        # `<transcript>.prompt`, the O_EXCL snapshot `bind-prompt.py` took of the validated bytes.
        # Handing the path meant the wrapper reopened the NAME after the binder had blessed it, so a
        # swap in between changed what the reviewer read while both sidecars still described the old
        # bytes — and, because the prompt filename is only per-ROUND, two runs sharing a ticket and
        # round shared that file outright (PR #63 recheck, P1). Asserting the snapshot rather than the
        # name is what keeps the fix from being reverted silently.
        self.assertEqual(
            [
                str(self.plugin / "scripts" / "review" / "isolated-agy-review.sh"),
                gemini_path + ".prompt",
                gemini_path,
            ],
            gemini_helpers[0][:3],
        )
        # FIVE operands now: the PLAN travels as the fifth. The harness reviews a detached checkout of
        # HEAD, so without it `agy` reads the COMMITTED plan while `<transcript>.plan` describes the
        # working-tree one — and with uncommitted edits, the normal state during review iteration, the
        # transcript approved one version while the artifact recorded it as evidence for another
        # (PR #63 recheck, P1). Asserting the count keeps the operand from being quietly dropped.
        self.assertEqual(5, len(gemini_helpers[0]), gemini_helpers[0])
        self._assert_recipe_timeout_exceeds_print_timeout(gemini_helpers[0][3])
        self.assertEqual(PLAN_RELATIVE, gemini_helpers[0][4], "the bound plan is not handed to the harness")
        for expected, record in ((gemini_path, gemini_capture), (codex_path, codex_capture)):
            with self.subTest(expected=expected):
                argv = record["argv"]
                allocated_index = argv.index("--allocated")
                self.assertEqual(expected, argv[allocated_index + 1])
                self.assertEqual(1, argv.count(expected), argv)
                self.assertTrue(Path(expected).is_file())

        self.assertEqual(
            str((self.plugin / "scripts" / "pty-capture.py").resolve()),
            gemini_capture["script"],
        )
        self.assertFalse((self.reviewed / "scripts" / "pty-capture.py").exists())

        artifact, argv = self.run_synthesis(
            f"gemini=APPROVE:{gemini_path}",
            f"codex=APPROVE:{codex_path}",
            "APPROVE",
        )
        self.assert_artifact_paths(artifact, gemini_path, codex_path)
        self.assertEqual(
            [f"gemini=APPROVE:{gemini_path}", f"codex=APPROVE:{codex_path}"],
            self.reviewer_values(argv),
        )

        brainstorm_artifact, brainstorm_argv = self.run_brainstorm_persistence(
            gemini_path, codex_path
        )
        self.assert_artifact_paths(brainstorm_artifact, gemini_path, codex_path)
        self.assertEqual(
            [f"gemini=APPROVE:{gemini_path}", f"codex=APPROVE:{codex_path}"],
            self.reviewer_values(brainstorm_argv),
        )

    def test_M5_1_terminal_space_and_tab_bases_are_not_trimmed(self) -> None:
        """Rejects strip/read parsing that silently changes an otherwise valid selected base."""
        for suffix in ("terminal-space ", "terminal-tab\t"):
            with self.subTest(suffix=suffix):
                base = self.root / suffix
                gemini_path, gemini_capture, _helpers = self.run_capture_recipe("gemini", base)
                codex_path, codex_capture, _helpers = self.run_capture_recipe("codex", base)
                for allocated, record in (
                    (gemini_path, gemini_capture),
                    (codex_path, codex_capture),
                ):
                    self.assertTrue(allocated.startswith(str(base.resolve()) + os.sep), allocated)
                    index = record["argv"].index("--allocated")
                    self.assertEqual(allocated, record["argv"][index + 1])

                self.bind_transcript_to_plan(gemini_path, codex_path)
                artifact, _argv = self.run_synthesis(
                    f"gemini=APPROVE:{gemini_path}",
                    f"codex=APPROVE:{codex_path}",
                    "APPROVE",
                )
                self.assert_artifact_paths(artifact, gemini_path, codex_path)

    def test_M5_1_safe_symlink_bases_keep_the_emitted_canonical_spelling(self) -> None:
        """Rejects restoring a lexical base spelling after the allocator canonicalizes it."""
        xdg_target = self.root / "canonical XDG target:=one"
        xdg_target.mkdir()
        xdg_link = self.root / "lexical XDG link"
        xdg_link.symlink_to(xdg_target, target_is_directory=True)

        fallback_target = self.root / "canonical fallback home:=two"
        (fallback_target / ".local" / "state").mkdir(parents=True)
        fallback_link = self.root / "lexical fallback home"
        fallback_link.symlink_to(fallback_target, target_is_directory=True)

        cases = (
            ("xdg", xdg_link, True, self.home, xdg_target.resolve()),
            (
                "fallback",
                self.root / "unused XDG base",
                False,
                fallback_link,
                (fallback_target / ".local" / "state").resolve(),
            ),
        )
        for label, base, use_xdg, home, canonical_base in cases:
            with self.subTest(base_kind=label):
                gemini_path, _capture, _helpers = self.run_capture_recipe(
                    "gemini", base, use_xdg=use_xdg, home=home
                )
                codex_path, _capture, _helpers = self.run_capture_recipe(
                    "codex", base, use_xdg=use_xdg, home=home
                )
                canonical_prefix = str(canonical_base) + os.sep
                self.assertTrue(gemini_path.startswith(canonical_prefix), gemini_path)
                self.assertTrue(codex_path.startswith(canonical_prefix), codex_path)
                self.assertNotIn(str(xdg_link if use_xdg else fallback_link), gemini_path)
                self.assertNotIn(str(xdg_link if use_xdg else fallback_link), codex_path)

                self.bind_transcript_to_plan(gemini_path, codex_path)
                artifact, _argv = self.run_synthesis(
                    f"gemini=APPROVE:{gemini_path}",
                    f"codex=APPROVE:{codex_path}",
                    "APPROVE",
                )
                self.assert_artifact_paths(artifact, gemini_path, codex_path)

    def test_M5_10_reviewer_specs_split_only_the_first_equals_and_colon(self) -> None:
        """Rejects unrestricted split('=')/split(':') and loss of later path delimiters."""
        base = self.root / "delimiter:=base=more:still"
        gemini_path = self.allocate_empty("gemini", base)
        codex_path = self.allocate_empty("codex", base)
        Path(gemini_path).write_text("gemini review\nVERDICT: APPROVE\n", encoding="utf-8")
        Path(codex_path).write_text("codex review\nVERDICT: APPROVE\n", encoding="utf-8")

        self.bind_transcript_to_plan(gemini_path, codex_path)
        gemini_spec = f"gemini=APPROVE:{gemini_path}"
        codex_spec = f"codex=APPROVE:{codex_path}"
        artifact, argv = self.run_synthesis(gemini_spec, codex_spec, "APPROVE")

        self.assertEqual([gemini_spec, codex_spec], self.reviewer_values(argv))
        self.assert_artifact_paths(artifact, gemini_path, codex_path)

    def test_M5_17_allocated_but_empty_transcript_classifies_as_missing(self) -> None:
        """Rejects treating a reserved zero-byte leaf as an approving or returned review."""
        base = self.root / "empty synthesis:=base"
        gemini_path = self.allocate_empty("gemini", base)
        codex_path = self.allocate_empty("codex", base)
        self.assertEqual(0, Path(gemini_path).stat().st_size)
        Path(codex_path).write_text("codex review\nVERDICT: APPROVE\n", encoding="utf-8")

        artifact, argv = self.run_synthesis(
            f"gemini=APPROVE:{gemini_path}",
            f"codex=APPROVE:{codex_path}",
            "DISAGREEMENT",
        )

        by_name = {reviewer["name"]: reviewer for reviewer in artifact["reviewers"]}
        self.assertEqual("MISSING", by_name["gemini"]["status"])
        self.assertNotIn("transcriptPath", by_name["gemini"])
        self.assertEqual(
            ["gemini=MISSING", f"codex=APPROVE:{codex_path}"],
            self.reviewer_values(argv),
        )

    def _assert_recipe_timeout_exceeds_print_timeout(self, recipe_timeout: str) -> None:
        """Bind the recipe's timeout to the wrapper's `--print-timeout`, never to a literal.

        This previously asserted `"1500"`, which pinned a DEFECTIVE value as the expected one: the
        wrapper had moved to `--print-timeout 28m` (1680s), so 1500 SIGTERMs a live review at 25
        minutes. Applying the correct fix turned CI red while leaving it green on the bug (PR #63
        review, gap 12). Assert the INVARIANT that actually matters instead -- the wrapper's cap must
        exceed the print-timeout it is wrapping -- so either value may be retuned without editing a
        test, and no retuning can reintroduce the inversion.
        """
        wrapper = (self.plugin / "scripts" / "review" / "isolated-agy-review.sh").read_text()
        match = re.search(r"--print-timeout\s+(\d+)m", wrapper)
        self.assertIsNotNone(match, "wrapper must pass an explicit --print-timeout")
        print_timeout_seconds = int(match.group(1)) * 60
        self.assertGreater(
            int(recipe_timeout),
            print_timeout_seconds,
            "the recipe's wrapper timeout must EXCEED agy's --print-timeout "
            f"({print_timeout_seconds}s), or a live review is SIGTERMed before agy can "
            "report its own diagnosable timeout",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class NestedScratchWorktreeStillStages(unittest.TestCase):
    """`TMPDIR` inside the checkout made the rewrite guard reject its own substitution.

    THE FINDING (PR #63 recheck, P2). Both harnesses build their scratch worktree with `mktemp -d`,
    which honours `TMPDIR` — so pointing it inside the repository puts the tree at `<repo>/tmp.x/tree`
    and the REPLACEMENT VALUE then contains the repository path. `stage-prompt.py` scanned the
    rewritten payload for `repo` and found the bytes it had just inserted, aborting every otherwise
    valid review AFTER its transcript had been allocated. A false refusal, and an expensive one.

    The guard now inspects the RESIDUE — the payload with the inserted `tree` occurrences removed —
    which is exactly the set of references the substitution failed to reach.

    NO NEGATIVE CELL ACCOMPANIES THIS ONE, deliberately. `bytes.replace` is total, so with the inserted
    occurrences discounted the guard cannot fire for its stated cause: a reference the substitution
    missed is one spelled differently, and such a reference contains no literal `repo` for either form
    of the check to see. I wrote the negative cell first and it passed against the fixed code — which
    is the tell. The guard is kept as a cheap invariant against a future non-total rewrite; claiming a
    proof for it would be claiming a test that cannot fail.
    """

    def stage(self, repo: str, tree: str, body: str):
        root = Path(tempfile.mkdtemp(prefix="nested-stage-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        snapshot = root / "prompt.md"
        snapshot.write_text(body, encoding="utf-8")
        record = root / "prompt.sha256"
        record.write_text(
            hashlib.sha256(snapshot.read_bytes()).hexdigest() + "  prompt.md\n", encoding="utf-8")
        tree_root = Path(tree)
        tree_root.mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            [sys.executable, str(STAGE_PROMPT), "--snapshot", str(snapshot), "--record", str(record),
             "--tree", str(tree_root), "--rel", "prompt.md", "--repo", repo, "--min-bytes", "1"],
            capture_output=True, text=True, check=False,
        ), tree_root

    def test_a_SIBLING_sharing_the_repository_prefix_is_left_alone(self):
        """`Unleashed Mail` vs `Unleashed MailTests` — live in this project's own layout.

        The raw substring replace rewrote any path merely PREFIXED by the repository root, so a prompt
        naming `…/Unleashed MailTests/AuthTests.swift` became `<tree>Tests/AuthTests.swift`, a path
        that does not exist. The reviewer silently reads nothing while the residue and digest checks
        both pass and the round stays valid. `Unleashed Mail`, `Unleashed MailTests` and
        `Unleashed Mail.worktrees` are all real sibling directories in this developer's checkout, so
        this is the ordinary case rather than a contrived one.
        """
        repo = tempfile.mkdtemp(prefix="prefix-repo-")
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        sibling = repo + "Tests"           # shares the whole root as a prefix
        dotted = repo + ".worktrees"       # ditto, continued by `.`
        # A SPACE IS A LEGAL PATH CHARACTER, and this project's checkout name contains one. My first
        # boundary treated "any byte outside [A-Za-z0-9._-]" as a component end, so `<repo> Helper/…`
        # was rewritten to `<tree> Helper/…` — the same defect this cell exists for, one character
        # class over. Caught in review of the fix; the boundary is now `/` or end-of-input only.
        spaced = repo + " Helper"
        for path in (sibling, dotted, spaced):
            os.makedirs(path, exist_ok=True)
            self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        tree = os.path.join(tempfile.mkdtemp(prefix="prefix-tree-"), "tree")
        self.addCleanup(shutil.rmtree, os.path.dirname(tree), ignore_errors=True)

        body = ("Review carefully.\n" * 20
                + f"REVIEW TARGET: {repo}/docs/planning/X_PLAN.md\n"
                + f"Also read {sibling}/AuthTests.swift\n"
                + f"and the worktree {dotted}/feature/\n"
                + f"and the helper {spaced}/notes.md\n"
                # A SENTENCE-ENDING PERIOD closes the component; `.worktrees` above does not. Left
                # unrewritten, the prompt would still name the LIVE checkout and the residue check —
                # asking the same question — would not notice.
                + f"The checkout is {repo}. Then stop.\n"
                # The rest of the decidable class — punctuation followed by whitespace or end. The
                # review reported the PERIOD; measuring showed the others behaved identically, so they
                # are swept together rather than arriving one report at a time.
                + f"Compare {repo}, then {repo}; and finally ({repo}) or \"{repo}\" here.\n"
                # STACKED closing punctuation — ordinary Markdown produces it, and requiring the first
                # closing byte to be followed immediately by whitespace missed it.
                + f"See `{repo}`. And \"{repo}\".\n"
                # The root as a SUFFIX of a longer path. Without a LEFT boundary this became
                # `/Volumes/backup<tree>/…` — the same silent corruption, on the other side.
                + f"Backup at /Volumes/backup{repo}/docs/plan.md\n")
        result, tree_root = self.stage(repo, tree, body)

        self.assertEqual(0, result.returncode, result.stderr)
        staged = (tree_root / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(f"{tree}/docs/planning/X_PLAN.md", staged, "the plan reference was not rewritten")
        self.assertIn(f"{sibling}/AuthTests.swift", staged,
                      "a sibling sharing the repository prefix was rewritten into a path that does "
                      "not exist — the reviewer would silently read nothing")
        self.assertIn(f"{dotted}/feature/", staged)
        self.assertIn(f"{spaced}/notes.md", staged,
                      "a sibling whose name continues with a SPACE was rewritten — a space is a legal "
                      "path character, and this project's own checkout name contains one")
        self.assertNotIn(f"{tree}Tests", staged)
        self.assertNotIn(f"{tree} Helper", staged)
        self.assertIn(f"The checkout is {tree}. Then stop.", staged,
                      "a sentence-ending period left the root naming the LIVE checkout")
        self.assertIn(f"Compare {tree}, then {tree}; and finally ({tree}) or \"{tree}\" here.", staged,
                      "punctuation followed by whitespace is prose and must be rewritten")
        self.assertIn(f"See `{tree}`. And \"{tree}\".", staged,
                      "stacked closing punctuation left the root naming the LIVE checkout")
        self.assertIn(f"/Volumes/backup{repo}/docs/plan.md", staged,
                      "the root as a SUFFIX of a longer path was rewritten — a left boundary is "
                      "required, not only a right one")
        self.assertNotIn(f"/Volumes/backup{tree}", staged)
        self.assertNotIn(repo + ",", staged)
        self.assertNotIn("(" + repo, staged)

    def test_a_scratch_tree_whose_path_contains_a_BACKSLASH_stages_literally(self):
        """`Pattern.sub` treats the replacement as a TEMPLATE (review of this fix).

        A backslash is legal in a Unix path and reaches here through `TMPDIR`: `\1` raised
        `invalid group reference` and aborted staging outright, while `\t` silently inserted a TAB and
        produced a path that does not exist — the second is the dangerous one, because staging then
        SUCCEEDS and the reviewer reads nothing. Both verified against the template form. A callable
        replacement returns the bytes literally.
        """
        repo = tempfile.mkdtemp(prefix="backslash-repo-")
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        scratch = tempfile.mkdtemp(prefix="backslash-tmp-")
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        tree = os.path.join(scratch, "a\\1b", "tree")     # a literal backslash-one in the path

        result, tree_root = self.stage(repo, tree, f"Review {repo}/docs/planning/X_PLAN.md.\n" * 20)

        self.assertEqual(0, result.returncode, result.stderr)
        staged = (tree_root / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(f"{tree}/docs/planning/X_PLAN.md", staged,
                      "the backslash was expanded as a template escape instead of copied literally")

    def test_a_scratch_tree_BENEATH_the_repository_still_stages(self):
        repo = tempfile.mkdtemp(prefix="nested-repo-")
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        tree = os.path.join(repo, "tmp.scratch", "tree")      # TMPDIR inside the checkout
        result, tree_root = self.stage(repo, tree, f"Review {repo}/docs/planning/X_PLAN.md.\n" * 20)
        self.assertEqual(0, result.returncode, result.stderr)
        staged = (tree_root / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(f"{tree}/docs/planning/X_PLAN.md", staged)
