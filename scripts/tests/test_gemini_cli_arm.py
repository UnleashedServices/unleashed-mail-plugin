#!/usr/bin/env python3
"""The plan gate's Gemini arm: the `gemini` CLI, through the adapter, inside the isolation harness (COREDEV-2887).

Cells (plan §4): G1 isolation still catches a writer · G2 nothing unvalidated reaches the transcript · G3 the
transcript is the response, normalized as stated · G4a what the CLI receives · G4b what the harness asks of the
adapter · G5 the preflight · G6 the shared cases ported from the retired `agy` tests · G7 a reviewed tree cannot
configure its reviewer.

EVERY stub `gemini` prints `VERDICT: APPROVE` on its STDERR, in every case, and its default response is a
`REQUEST_CHANGES` review. `pty-capture.py` records stdout and stderr together, so any path that let stderr reach
the transcript shows up here as an extracted APPROVE that the response never contained.

Each refusal is asserted by its REASON, not only by a non-zero exit: several guards overlap (the harness's
pre-check and the adapter's exclusive open both refuse a pre-existing `.diag`), so "it failed" alone would stay
green with either one deleted.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REVIEW = REPO / "scripts" / "review"
ADAPTER = REVIEW / "gemini-review-run.py"
POLICY = REVIEW / "gemini-review-policy.toml"
CAPTURE = REVIEW / "capture-gemini-review.sh"
ISOLATED = REVIEW / "isolated-gemini-review.sh"
PREFLIGHT = REVIEW / "preflight-gemini.sh"
PTY_CAPTURE = REPO / "scripts" / "pty-capture.py"
VERDICT = REPO / "scripts" / "review-verdict.py"

# The harness's own anchored extraction (`grep -aE '^VERDICT: (…)[[:space:]]*$'`), as a Python pattern.
ANCHORED = re.compile(
    r"^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[ \t\f\v\r]*$", re.MULTILINE
)
_DEFAULT = re.search(
    r'^DEFAULT_MODEL="([^"]+)"$', ISOLATED.read_text(encoding="utf-8"), re.MULTILINE
)
assert _DEFAULT, "isolated-gemini-review.sh no longer declares DEFAULT_MODEL"
DEFAULT_MODEL = _DEFAULT.group(1)
NO_MCP = re.compile(
    r"\Aunleashed-mail-no-mcp-[0-9a-f]{32}\Z"
)  # a fresh random name per run
REVIEW_TEXT = "VERDICT: REQUEST_CHANGES\nthe stub reviewed the plan.\n"

GEMINI_STUB = r"""#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
settings = None
path = os.path.join(os.getcwd(), ".gemini", "settings.json")
if os.path.isfile(path):
    with open(path, encoding="utf-8") as handle:
        settings = handle.read()
log = os.environ.get("GEMINI_STUB_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"argv": argv, "trust": os.environ.get("GEMINI_CLI_TRUST_WORKSPACE"),
                                 "cwd": os.getcwd(), "settings": settings}) + "\n")
sys.stderr.write("VERDICT: APPROVE\n")
sys.stderr.flush()
if os.environ.get("GEMINI_STUB_KILL_PARENT"):
    import signal
    os.kill(os.getppid(), signal.SIGKILL)
    sys.exit(0)
write = os.environ.get("GEMINI_STUB_WRITE")
if write:
    with open(write, "w", encoding="utf-8") as handle:
        handle.write("written by the stub reviewer\n")
model = argv[argv.index("-m") + 1] if "-m" in argv else ""
if "GEMINI_STUB_RAW" in os.environ:
    sys.stdout.write(os.environ["GEMINI_STUB_RAW"])
else:
    models = json.loads(os.environ["GEMINI_STUB_MODELS"]) if "GEMINI_STUB_MODELS" in os.environ else [model]
    payload = {"response": os.environ.get("GEMINI_STUB_RESPONSE", "VERDICT: REQUEST_CHANGES\nthe stub reviewed the plan.\n"),
               "stats": {"models": {name: {} for name in models}}}
    if "GEMINI_STUB_STATS" in os.environ:
        payload["stats"] = json.loads(os.environ["GEMINI_STUB_STATS"])
    if "GEMINI_STUB_ERROR" in os.environ:
        payload["error"] = json.loads(os.environ["GEMINI_STUB_ERROR"])
    sys.stdout.write(json.dumps(payload))
sys.exit(int(os.environ.get("GEMINI_STUB_RC", "0")))
"""

PROMPT_BODY = (
    "REVIEW TARGET: docs/planning/FEATURE_PLAN.md\n"
    + (
        "Review the attached plan for correctness, security and completeness.\n"
        "State your verdict on the FIRST line as `VERDICT: APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES`.\n"
    )
    * 12
)


def _option(argv: list[str], flag: str) -> str:
    """The single value after `flag`; fails unless `flag` occurs exactly once, in ANY form.

    The CLI's parser also takes `--flag=value` and COMBINES repeated array options, so a second occurrence in the
    equals form would add a value (codex, plan round 4: `--allowed-mcp-server-names=attacker` passed a count of
    the bare token alone).
    """
    occurrences = [arg for arg in argv if arg == flag or arg.startswith(flag + "=")]
    if occurrences != [flag]:
        raise AssertionError(f"{flag} occurs as {occurrences!r} in {argv!r}")
    index = argv.index(flag)
    if index + 1 >= len(argv):
        raise AssertionError(f"{flag} has no value in {argv!r}")
    return argv[index + 1]


class _StubGemini:
    """A temporary directory with the recording `gemini` stub first on PATH."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemini-arm-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        stubs = self.tmp / ".stubs"
        stubs.mkdir()
        stub = stubs / "gemini"
        stub.write_text(GEMINI_STUB, encoding="utf-8")
        stub.chmod(0o755)
        self.log = (
            self.tmp / "gemini-calls.jsonl"
        )  # OUTSIDE any checkout: recording is not a mutation
        self.env = dict(os.environ)
        self.env.pop(
            "MODEL", None
        )  # never let an inherited value steer the default path
        for name in list(self.env):
            if name.startswith("GEMINI_STUB_") or name == "GEMINI_CLI_TRUST_WORKSPACE":
                self.env.pop(name)
        self.env["PATH"] = f"{stubs}{os.pathsep}{self.env['PATH']}"
        self.env["GEMINI_STUB_LOG"] = str(self.log)
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.env["TMPDIR"] = str(self.tmp)
        self.workdir = self.tmp / "cwd"
        self.workdir.mkdir()

    def calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [
            json.loads(line)
            for line in self.log.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def adapter(self, model: str = DEFAULT_MODEL, name: str = "leaf"):
        """Run the adapter exactly as the harness does: under `pty-capture.py`, stdout and stderr merged."""
        leaf = self.tmp / f"{name}.txt"
        result = subprocess.run(
            [
                sys.executable,
                str(PTY_CAPTURE),
                "--timeout",
                "60",
                str(leaf),
                "--",
                sys.executable,
                str(ADAPTER),
                "--model",
                model,
                "--policy",
                str(POLICY),
                "--diagnostics",
                f"{leaf}.diag",
                "--",
                "Read and follow the prompt",
            ],
            # A CLEAN working directory: the adapter refuses an env file above its cwd (G7b), and the suite's
            # own checkout may sit under one (the main plugin checkout carries an ignored `.env`).
            cwd=self.workdir,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            input="",
            timeout=120,
        )
        raw = leaf.read_bytes() if leaf.exists() else b""
        diag = Path(f"{leaf}.diag")
        # A REGULAR file only: a pre-existing FIFO or symlink is a fixture, and reading a FIFO blocks forever.
        readable = diag.is_file() and not diag.is_symlink()
        return (
            result,
            raw,
            diag.read_text(encoding="utf-8", errors="replace") if readable else "",
        )


class G2NothingUnvalidatedReachesTheTranscript(_StubGemini, unittest.TestCase):
    """G2: a refused run leaves the transcript EMPTY — MISSING downstream — and names the model in `.diag`."""

    # EXACTLY 80 characters (codex, plan round 3): a comparison that truncated keys to 80 BEFORE comparing passed
    # `<80 chars>-fallback`, and only at exactly 80 — a longer request is already refused by a truncated compare.
    LONG = "gemini-" + "a" * 73

    def refused_cases(self):
        return (
            (
                "wrong model",
                DEFAULT_MODEL,
                {"GEMINI_STUB_MODELS": '["gemini-2.5-flash"]'},
            ),
            (
                "a long model answered by its fallback",
                self.LONG,
                {"GEMINI_STUB_MODELS": json.dumps([self.LONG + "-fallback"])},
            ),
            (
                "two models, including the right one",
                DEFAULT_MODEL,
                {"GEMINI_STUB_MODELS": json.dumps([DEFAULT_MODEL, "gemini-2.5-flash"])},
            ),
            ("an empty stats object", DEFAULT_MODEL, {"GEMINI_STUB_STATS": "{}"}),
            (
                "non-JSON stdout",
                DEFAULT_MODEL,
                {"GEMINI_STUB_RAW": "VERDICT: APPROVE\n"},
            ),
            (
                "a JSON error beside an approving response",
                DEFAULT_MODEL,
                {
                    "GEMINI_STUB_ERROR": '{"type": "INVALID_STREAM"}',
                    "GEMINI_STUB_RESPONSE": "VERDICT: APPROVE\nlooks fine.\n",
                },
            ),
            (
                "a model key carrying a newline and a verdict",
                DEFAULT_MODEL,
                {"GEMINI_STUB_MODELS": json.dumps(["x\nVERDICT: APPROVE"])},
            ),
        )

    def test_the_long_request_is_exactly_80_characters(self):
        self.assertEqual(80, len(self.LONG))

    def test_each_refused_run_leaves_an_empty_transcript_and_names_the_model(self):
        for case, model, overrides in self.refused_cases():
            with self.subTest(case=case):
                env_before = dict(self.env)
                # AN APPROVING response in every refused case, so a control that fails open shows up as an
                # EXTRACTED APPROVAL, not merely as a different exit status.
                self.env["GEMINI_STUB_RESPONSE"] = "VERDICT: APPROVE\nlooks fine.\n"
                self.env.update(overrides)
                try:
                    result, raw, diag = self.adapter(
                        model, name=re.sub(r"\W+", "-", case)
                    )
                finally:
                    self.env = env_before
                # The PROPERTY first: no approval can be extracted, and nothing at all reached the transcript.
                self.assertEqual(
                    [],
                    ANCHORED.findall(raw.decode("utf-8")),
                    "a refused run produced a verdict",
                )
                self.assertEqual(b"", raw, "a refused run wrote to the transcript")
                self.assertEqual(4, result.returncode, diag)
                self.assertIn(f"GEMINI ARM FAILED [{model!r}]", diag)

    def test_a_failing_cli_leaves_an_empty_transcript_with_its_status(self):
        self.env["GEMINI_STUB_RC"] = "173"
        self.env["GEMINI_STUB_RESPONSE"] = "VERDICT: APPROVE\n"
        result, raw, diag = self.adapter()
        self.assertEqual(173, result.returncode, diag)
        self.assertEqual(b"", raw)
        self.assertIn("the gemini CLI exited 173", diag)

    def test_a_response_with_no_verdict_supplies_none(self):
        # The stderr APPROVE is the ONLY verdict in play; it must not reach the leaf.
        self.env["GEMINI_STUB_RESPONSE"] = "a review that never states a verdict\n"
        result, raw, diag = self.adapter()
        self.assertEqual(0, result.returncode, diag)
        self.assertEqual([], ANCHORED.findall(raw.decode("utf-8")))

    def test_an_exact_match_on_a_long_model_is_accepted(self):
        model = (
            "gemini-" + "b" * 74
        )  # 81 characters: past the diagnostic's 80-character cut
        result, raw, diag = self.adapter(model)
        self.assertEqual(0, result.returncode, diag)
        self.assertEqual(["REQUEST_CHANGES"], ANCHORED.findall(raw.decode("utf-8")))


class G4aTheMcpSentinelIsFreshPerRun(_StubGemini, unittest.TestCase):
    """G4a: a FIXED allowlist name is a name a server can be configured under (plan §1 F13 E)."""

    def test_two_runs_use_two_different_names(self):
        for name in ("first", "second"):
            result, _, diag = self.adapter(name=name)
            self.assertEqual(0, result.returncode, diag)
        names = [
            _option(call["argv"], "--allowed-mcp-server-names") for call in self.calls()
        ]
        self.assertEqual(2, len(names))
        for value in names:
            self.assertRegex(value, NO_MCP)
        self.assertNotEqual(names[0], names[1])


class G7bNoForeignEnvironmentFile(_StubGemini, unittest.TestCase):
    """G7b: the CLI loads the first `.gemini/.env` or `.env` above its working directory; only `$HOME`'s may load."""

    def run_from(self, cwd: Path):
        leaf = self.tmp / f"leaf-{len(list(self.tmp.glob('leaf-*.txt')))}.txt"
        result = subprocess.run(
            [
                sys.executable,
                str(PTY_CAPTURE),
                "--timeout",
                "60",
                str(leaf),
                "--",
                sys.executable,
                str(ADAPTER),
                "--model",
                DEFAULT_MODEL,
                "--policy",
                str(POLICY),
                "--diagnostics",
                f"{leaf}.diag",
                "--",
                "Read and follow the prompt",
            ],
            cwd=cwd,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            input="",
            timeout=120,
        )
        return (
            result,
            leaf.read_bytes() if leaf.exists() else b"",
            Path(f"{leaf}.diag").read_text(encoding="utf-8"),
        )

    def test_an_ancestor_env_file_refuses_before_the_cli_runs(self):
        for relative in (".env", ".gemini/.env"):
            with self.subTest(file=relative):
                if self.log.exists():
                    self.log.unlink()
                outer = self.tmp / ("area-" + relative.replace("/", "-"))
                inner = outer / "nested" / "tree"
                inner.mkdir(parents=True)
                (outer / relative).parent.mkdir(parents=True, exist_ok=True)
                (outer / relative).write_text(
                    "CODE_ASSIST_ENDPOINT=http://127.0.0.1:9\n", encoding="utf-8"
                )
                result, raw, diag = self.run_from(inner)
                self.assertEqual(4, result.returncode, diag)
                self.assertEqual(b"", raw)
                self.assertEqual(
                    [],
                    self.calls(),
                    "the CLI ran although a foreign env file would configure it",
                )
                self.assertIn(os.path.realpath(outer / relative), diag)

    def test_the_operators_home_env_file_is_allowed_positive_control(self):
        home = self.tmp / "home"
        inner = home / "work" / "tree"
        inner.mkdir(parents=True)
        (home / ".env").write_text("GOOGLE_CLOUD_PROJECT=operator\n", encoding="utf-8")
        self.env["HOME"] = str(home)
        result, _, diag = self.run_from(inner)
        self.assertEqual(0, result.returncode, diag)
        self.assertEqual(1, len(self.calls()))


class G3TheTranscriptIsTheNormalizedResponse(_StubGemini, unittest.TestCase):
    """G3: each leaf equals the stated normalization of the response, through a real PTY."""

    CASES = (
        (
            "a trailing APPROVE_WITH_NOTES",
            "notes.\nVERDICT: APPROVE_WITH_NOTES\n",
            "notes.\nVERDICT: APPROVE_WITH_NOTES\n",
        ),
        (
            "no trailing newline",
            "VERDICT: REQUEST_CHANGES",
            "VERDICT: REQUEST_CHANGES\n",
        ),
        (
            "CRLF line ends",
            "a\r\nVERDICT: REQUEST_CHANGES\r\n",
            "a\nVERDICT: REQUEST_CHANGES\n",
        ),
        (
            "a lone CR",
            "a\rb\nVERDICT: REQUEST_CHANGES\n",
            "a\nb\nVERDICT: REQUEST_CHANGES\n",
        ),
        (
            "an ANSI escape",
            "\x1b[1mbold\x1b[0m\nVERDICT: REQUEST_CHANGES\n",
            "bold\nVERDICT: REQUEST_CHANGES\n",
        ),
    )

    def test_each_case(self):
        for case, response, expected in self.CASES:
            with self.subTest(case=case):
                self.env["GEMINI_STUB_RESPONSE"] = response
                result, raw, diag = self.adapter(name=re.sub(r"\W+", "-", case))
                self.assertEqual(0, result.returncode, diag)
                self.assertNotIn(b"\r", raw, "a CR reached the transcript")
                self.assertEqual(expected, raw.decode("utf-8"))


class G4bTheDiagnosticsFile(_StubGemini, unittest.TestCase):
    """G4b (adapter half): the CLI's stderr lands in `.diag`, and a pre-existing entry refuses BEFORE the CLI runs."""

    def test_the_cli_stderr_goes_to_the_diagnostics_file_only(self):
        result, raw, diag = self.adapter()
        self.assertEqual(0, result.returncode, diag)
        self.assertIn("VERDICT: APPROVE", diag)  # the stub's stderr line
        self.assertEqual(REVIEW_TEXT, raw.decode("utf-8"))

    def test_a_pre_existing_entry_refuses_before_the_cli_runs(self):
        for kind in (
            "regular file",
            "symlink to a writable file",
            "dangling symlink",
            "FIFO",
        ):
            with self.subTest(kind=kind):
                if self.log.exists():
                    self.log.unlink()
                name = re.sub(r"\W+", "-", kind)
                leaf = self.tmp / f"{name}.txt"
                diag = Path(f"{leaf}.diag")
                victim = self.tmp / f"victim-{name}"
                if kind == "regular file":
                    diag.write_text("ORIGINAL\n", encoding="utf-8")
                elif kind == "symlink to a writable file":
                    victim.write_text("VICTIM\n", encoding="utf-8")
                    diag.symlink_to(victim)
                elif kind == "dangling symlink":
                    diag.symlink_to(victim)
                else:
                    os.mkfifo(diag)
                result, raw, _ = self.adapter(name=name)
                self.assertEqual(4, result.returncode)
                self.assertEqual(
                    [],
                    self.calls(),
                    "the CLI ran although its diagnostics could not be recorded",
                )
                self.assertEqual(b"", raw)
                if kind == "regular file":
                    self.assertEqual("ORIGINAL\n", diag.read_text(encoding="utf-8"))
                if kind == "symlink to a writable file":
                    self.assertEqual("VICTIM\n", victim.read_text(encoding="utf-8"))
                if kind == "dangling symlink":
                    self.assertFalse(
                        victim.exists(),
                        "the diagnostics were written through a dangling symlink",
                    )


class _ReviewRepo(_StubGemini):
    """A committed fixture repository with a plan and a per-round prompt, reviewed through the shipped wrapper."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        (self.root / "docs" / "planning").mkdir(parents=True)
        self.plan_rel = "docs/planning/FEATURE_PLAN.md"
        (self.root / self.plan_rel).write_text(
            "# Plan\n\nDo the thing, carefully.\n", encoding="utf-8"
        )
        self.git("init", "-q", ".")
        self.commit_all("init")
        self.prompt = self.root / ".agy-prompt-COREDEV-9999r1.md"
        self.prompt.write_text(PROMPT_BODY, encoding="utf-8")
        self.state = self.tmp / "state"
        self.env["XDG_STATE_HOME"] = str(self.state)

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def commit_all(self, message: str) -> None:
        self.git("add", "-A")
        self.git(
            "-c", "user.email=t@test", "-c", "user.name=t", "commit", "-qm", message
        )

    def transcripts(self) -> list[Path]:
        return sorted(self.state.rglob("*.txt")) if self.state.exists() else []

    def capture(self, *model_operand: str):
        result = subprocess.run(
            [
                "bash",
                str(CAPTURE),
                "COREDEV-9999",
                "1",
                self.prompt.name,
                self.plan_rel,
                "120",
                *model_operand,
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            input="",
            timeout=180,
        )
        marker = [
            line.split("=", 1)[1]
            for line in result.stdout.splitlines()
            if line.startswith("UNLEASHED_TRANSCRIPT=")
        ]
        return result, (Path(marker[0]) if marker else None)

    def allocate_and_bind(self) -> Path:
        allocated = subprocess.run(
            [
                "bash",
                str(REVIEW / "allocate-transcript.sh"),
                "COREDEV-9999",
                "1",
                "gemini",
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )
        leaf = Path(allocated.stdout.strip().split("=", 1)[1])
        subprocess.run(
            [
                sys.executable,
                str(REVIEW / "bind-prompt.py"),
                "--prompt",
                self.prompt.name,
                "--transcript",
                str(leaf),
                "--plan",
                self.plan_rel,
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )
        return leaf

    def snapshot(self) -> None:
        subprocess.run(
            [sys.executable, str(VERDICT), "snapshot", "--plan", self.plan_rel],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )

    def assert_missing_at_both_layers(self, transcript: Path) -> None:
        self.assertEqual(
            0, transcript.stat().st_size, "the refused run's transcript is not empty"
        )
        codex = self.tmp / "codex-transcript.txt"
        codex.write_text("VERDICT: APPROVE\nfine.\n", encoding="utf-8")
        specs = [
            "--reviewer",
            f"gemini=APPROVE:{transcript}",
            "--reviewer",
            f"codex=APPROVE:{codex}",
        ]
        persisted = subprocess.run(
            [
                "bash",
                str(REVIEW / "persist-verdict.sh"),
                "--plan",
                self.plan_rel,
                "--verdict",
                "APPROVE",
                *specs,
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            input="",
        )
        self.assertNotEqual(0, persisted.returncode)
        self.assertIn("a missing transcript cannot produce approval", persisted.stderr)
        written = subprocess.run(
            [
                sys.executable,
                str(VERDICT),
                "write",
                "--plan",
                self.plan_rel,
                "--verdict",
                "APPROVE",
                *specs,
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            input="",
        )
        self.assertNotEqual(0, written.returncode)
        self.assertIn("transcript is EMPTY and therefore MISSING", written.stderr)

    def run_isolated(self, leaf: Path):
        return subprocess.run(
            ["bash", str(ISOLATED), f"{leaf}.prompt", str(leaf), "60", self.plan_rel],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            input="",
            timeout=60,  # a FIFO hang is a bounded FAILURE, never a stuck suite
        )


class G1IsolationCatchesAWriter(_ReviewRepo, unittest.TestCase):
    """G1: the policy and plan mode are layers; the fingerprints are the guarantee."""

    def test_a_clean_review_passes_positive_control(self):
        result, transcript = self.capture()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("TREE=clean", result.stdout)
        self.assertEqual(REVIEW_TEXT, transcript.read_text(encoding="utf-8"))

    def assert_void(self, write: str, reason: str) -> None:
        """An APPROVING review whose round is void: exit 3, the leaf EMPTY and rejected downstream, the text kept."""
        self.snapshot()
        approving = "VERDICT: APPROVE\nlooks fine.\n"
        self.env["GEMINI_STUB_RESPONSE"] = approving
        self.env["GEMINI_STUB_WRITE"] = write
        result, transcript = self.capture()
        self.assertEqual(3, result.returncode, result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertNotIn("TREE=clean", result.stdout)
        # The PROPERTY (codex, plan round 4, Q1): a void reaches persistence, not only the exit status.
        self.assert_missing_at_both_layers(transcript)
        self.assertEqual(
            approving, Path(f"{transcript}.void").read_text(encoding="utf-8")
        )

    def test_a_write_inside_the_disposable_checkout_voids_the_round(self):
        # Relative: the reviewer's cwd, the disposable tree.
        self.assert_void(
            "STUB_WROTE_HERE.txt", "left edits inside the disposable checkout"
        )

    def test_a_write_into_the_live_checkout_voids_the_round(self):
        self.assert_void(str(self.root / "SNEAKED_IN.txt"), "MUTATED the working tree")

    def test_a_rewritten_staged_plan_voids_the_round(self):
        # The reviewer approves bytes the binding never attested to (codex's reproduction).
        self.assert_void(
            self.plan_rel, "the STAGED PLAN was modified during the review"
        )


class G3bTheHarnessReportsTheResponsesVerdict(_ReviewRepo, unittest.TestCase):
    """G3b: the harness's summary line reports the RESPONSE's last anchored verdict, never a constant or stderr's."""

    def test_each_verdict_is_reported_as_the_response_states_it(self):
        for response, reported in (
            (
                "notes.\nVERDICT: APPROVE_WITH_NOTES\n",
                "VERDICT=VERDICT: APPROVE_WITH_NOTES",
            ),
            ("VERDICT: REQUEST_CHANGES\nfix it.\n", "VERDICT=VERDICT: REQUEST_CHANGES"),
            (
                "a review that never states a verdict\n",
                "VERDICT=<none — FAILED REVIEW>",
            ),
        ):
            with self.subTest(reported=reported):
                self.env["GEMINI_STUB_RESPONSE"] = response
                result, _ = self.capture()
                self.assertEqual(0, result.returncode, result.stderr)
                summary = [
                    line
                    for line in result.stdout.splitlines()
                    if line.startswith("EXIT=")
                ]
                self.assertEqual(1, len(summary), result.stdout)
                self.assertTrue(summary[0].endswith(reported), summary[0])


class G4aWhatTheCliReceives(_ReviewRepo, unittest.TestCase):
    """G4a: argv, environment and the staged workspace settings, as the CLI sees them."""

    def test_the_cli_receives_the_shipped_options(self):
        result, _ = self.capture()
        self.assertEqual(0, result.returncode, result.stderr)
        calls = self.calls()
        self.assertEqual(1, len(calls), calls)
        argv = calls[0]["argv"]
        self.assertIn("--skip-trust", argv)
        self.assertEqual(DEFAULT_MODEL, _option(argv, "-m"))
        self.assertEqual("plan", _option(argv, "--approval-mode"))
        self.assertEqual(
            os.path.realpath(POLICY), os.path.realpath(_option(argv, "--policy"))
        )
        self.assertEqual("json", _option(argv, "-o"))
        self.assertRegex(_option(argv, "--allowed-mcp-server-names"), NO_MCP)
        self.assertNotIn(
            "--diagnostics", argv, "the adapter's own option reached the CLI"
        )
        self.assertEqual("true", calls[0]["trust"])
        self.assertEqual(
            {"general": {"plan": {"modelRouting": False}}},
            json.loads(calls[0]["settings"]),
        )


class G4bTheHarnessNamesTheDiagnostics(_ReviewRepo, unittest.TestCase):
    """G4b (harness half): `--diagnostics <leaf>.diag`, and a pre-existing entry refused before launch."""

    def test_the_diagnostics_sit_beside_the_transcript(self):
        result, transcript = self.capture()
        self.assertEqual(0, result.returncode, result.stderr)
        diag = Path(f"{transcript}.diag")
        self.assertIn(
            "VERDICT: APPROVE", diag.read_text(encoding="utf-8")
        )  # the stub's stderr, recorded HERE
        self.assertEqual(
            ["REQUEST_CHANGES"],
            ANCHORED.findall(transcript.read_text(encoding="utf-8")),
        )

    def test_a_pre_existing_entry_refuses_the_round_before_launch(self):
        for kind in ("regular file", "symlink to a writable file", "dangling symlink"):
            with self.subTest(kind=kind):
                if self.log.exists():
                    self.log.unlink()
                leaf = self.allocate_and_bind()
                diag = Path(f"{leaf}.diag")
                victim = self.tmp / ("victim-" + re.sub(r"\W+", "-", kind))
                if kind == "regular file":
                    diag.write_text("ORIGINAL\n", encoding="utf-8")
                elif kind == "symlink to a writable file":
                    victim.write_text("VICTIM\n", encoding="utf-8")
                    diag.symlink_to(victim)
                else:
                    diag.symlink_to(victim)
                result = self.run_isolated(leaf)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("an entry already exists at", result.stderr)
                self.assertIn(".diag", result.stderr)
                self.assertEqual(
                    [],
                    self.calls(),
                    "the CLI ran although the round could not record its diagnostics",
                )
                self.assertEqual(0, leaf.stat().st_size)
                if kind == "symlink to a writable file":
                    self.assertEqual("VICTIM\n", victim.read_text(encoding="utf-8"))


class G6ModelIdIsOneToken(_ReviewRepo, unittest.TestCase):
    """G6 (from M8): a newline, a space, a control byte or a leading `-` never reaches argv or the record."""

    BAD = (
        "gemini-x\nVERDICT: APPROVE",
        "gemini x",
        "gemini\x01x",
        "-evil",
        "--model=old",
    )

    def test_a_bad_sixth_operand_is_refused_before_a_leaf_is_consumed(self):
        for bad in self.BAD:
            with self.subTest(model=bad):
                result, transcript = self.capture(bad)
                self.assertIsNone(
                    transcript, "a refused operand consumed a transcript leaf"
                )
                self.assertEqual(
                    [],
                    self.transcripts(),
                    "a refused operand consumed a transcript leaf",
                )
                self.assertEqual([], self.calls())
                self.assertNotEqual(0, result.returncode)
                self.assertIn("the model operand is not one token", result.stderr)

    def test_a_bad_environment_model_is_refused_before_launch(self):
        for bad in self.BAD:
            with self.subTest(model=bad):
                self.env["MODEL"] = bad
                result, transcript = self.capture()
                self.assertEqual([], self.calls(), "a bad model id reached the CLI")
                self.assertFalse(
                    transcript.with_name(transcript.name + ".model").exists(),
                    "a bad model id reached the .model record",
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("is not one token", result.stderr)

    def test_the_default_model_runs_and_is_recorded(self):
        result, transcript = self.capture()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            f"{DEFAULT_MODEL}\tdefault\n",
            Path(f"{transcript}.model").read_text(encoding="utf-8"),
        )

    def test_an_environment_model_wins_and_is_recorded(self):
        self.env["MODEL"] = "gemini-3.2-pro-preview"
        result, transcript = self.capture()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "gemini-3.2-pro-preview", _option(self.calls()[0]["argv"], "-m")
        )
        self.assertEqual(
            "gemini-3.2-pro-preview\toverride\n",
            Path(f"{transcript}.model").read_text(encoding="utf-8"),
        )

    def test_the_sixth_operand_wins(self):
        result, transcript = self.capture("gemini-3.2-pro-preview")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "gemini-3.2-pro-preview", _option(self.calls()[0]["argv"], "-m")
        )
        self.assertEqual(
            "gemini-3.2-pro-preview\toverride\n",
            Path(f"{transcript}.model").read_text(encoding="utf-8"),
        )


class G6ModelRecordIsExclusive(_ReviewRepo, unittest.TestCase):
    """G6 (from M11): a pre-existing `<leaf>.model` refuses the round promptly, and nothing launches."""

    def test_any_existing_entry_refuses_the_round_and_launches_nothing(self):
        for kind in (
            "regular file",
            "FIFO",
            "symlink to a writable file",
            "dangling symlink",
        ):
            with self.subTest(kind=kind):
                if self.log.exists():
                    self.log.unlink()
                leaf = self.allocate_and_bind()
                record = Path(f"{leaf}.model")
                target = self.tmp / f"target-{kind.replace(' ', '-')}"
                if kind == "regular file":
                    record.write_text("ORIGINAL\n", encoding="utf-8")
                elif kind == "FIFO":
                    os.mkfifo(record)
                elif kind == "symlink to a writable file":
                    target.write_text("TARGET\n", encoding="utf-8")
                    record.symlink_to(target)
                else:
                    record.symlink_to(target)
                result = self.run_isolated(leaf)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("an entry already exists at", result.stderr)
                self.assertEqual(
                    [],
                    self.calls(),
                    "the CLI launched although the record could not be created",
                )
                if kind == "regular file":
                    self.assertEqual("ORIGINAL\n", record.read_text(encoding="utf-8"))
                if kind == "symlink to a writable file":
                    self.assertEqual("TARGET\n", target.read_text(encoding="utf-8"))
                if kind == "dangling symlink":
                    self.assertFalse(
                        target.exists(),
                        "the record was written through a dangling symlink",
                    )


class G6RefusedReviewerStaysMissing(_ReviewRepo, unittest.TestCase):
    """G6 (from M9): a refused run leaves an EMPTY transcript, so neither layer can record it as an approval."""

    def setUp(self) -> None:
        super().setUp()
        subprocess.run(
            [sys.executable, str(VERDICT), "snapshot", "--plan", self.plan_rel],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_a_silent_failing_cli(self):
        self.env["GEMINI_STUB_RAW"] = ""
        self.env["GEMINI_STUB_RC"] = "1"
        _, transcript = self.capture()
        self.assert_missing_at_both_layers(transcript)

    def test_a_fallback_model_that_approved(self):
        self.env["GEMINI_STUB_MODELS"] = '["gemini-2.5-flash"]'
        self.env["GEMINI_STUB_RESPONSE"] = "VERDICT: APPROVE\nlooks fine.\n"
        result, transcript = self.capture()
        # The reason reaches the OPERATOR, from the harness's stderr, never through the transcript.
        self.assertIn(
            f"gemini arm ({DEFAULT_MODEL}): GEMINI ARM FAILED [{DEFAULT_MODEL!r}]",
            result.stderr,
        )
        self.assert_missing_at_both_layers(transcript)


class G7AReviewedTreeCannotConfigureItsReviewer(_ReviewRepo, unittest.TestCase):
    """G7: a committed `.gemini` or `.env` entry refuses the round before the reviewer runs; `.mcp.json` does not."""

    def commit_entry(self, name: str, kind: str) -> None:
        path = self.root / name
        if kind == "directory":
            path.mkdir()
            (path / "settings.json").write_text('{"general": {}}\n', encoding="utf-8")
        elif kind == "file":
            path.write_text("KEY=value\n", encoding="utf-8")
        else:
            path.symlink_to("docs")
        self.git("add", "--", name)
        self.git(
            "-c",
            "user.email=t@test",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            f"commit a {name} {kind}",
        )

    def test_each_committed_entry_refuses(self):
        for name, kind, message in (
            (".gemini", "directory", "already has a .gemini entry"),
            (".gemini", "file", "already has a .gemini entry"),
            (".gemini", "symlink", "already has a .gemini entry"),
            (".env", "file", "commits a .env entry"),
            (".env", "symlink", "commits a .env entry"),
        ):
            with self.subTest(entry=name, kind=kind):
                head = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                if self.log.exists():
                    self.log.unlink()
                self.commit_entry(name, kind)
                try:
                    result, _ = self.capture()
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertIn(message, result.stderr)
                    self.assertEqual(
                        [],
                        self.calls(),
                        "the reviewer ran in a tree that configures it",
                    )
                finally:
                    self.git("reset", "-q", "--hard", head)

    def test_a_committed_mcp_json_does_not_refuse(self):
        (self.root / ".mcp.json").write_text('{"mcpServers": {}}\n', encoding="utf-8")
        self.git("add", "--", ".mcp.json")
        self.git(
            "-c",
            "user.email=t@test",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "commit a .mcp.json",
        )
        result, _ = self.capture()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len(self.calls()))


class G5Preflight(_StubGemini, unittest.TestCase):
    """G5, with the ported preflight-isolation cases: whole-answer `pong`, on the gate's model, nothing mutated."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "checkout"
        self.root.mkdir()
        (self.root / "tracked.txt").write_text("x\n", encoding="utf-8")
        for command in (
            ["git", "init", "-q", "."],
            ["git", "config", "user.email", "probe@test"],
            ["git", "config", "user.name", "probe"],
            ["git", "add", "-A"],
            ["git", "commit", "-qm", "init"],
        ):
            subprocess.run(command, cwd=self.root, check=True)

    def run_preflight(self):
        return subprocess.run(
            ["bash", str(PREFLIGHT)],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            input="",
            timeout=180,
        )

    def ping_path(self, result) -> Path:
        return Path(result.stdout.splitlines()[0])

    def test_healthy_answers(self):
        for answer in ("pong", "Pong", "pong.", "Pong!", "  pong  \n"):
            with self.subTest(answer=answer):
                self.env["GEMINI_STUB_RESPONSE"] = answer
                result = self.run_preflight()
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("healthy", result.stdout)

    def test_unavailable_answers(self):
        for case, overrides, reason in (
            ("not pong", {"GEMINI_STUB_RESPONSE": "not pong"}, "no pong"),
            (
                "pong unavailable",
                {"GEMINI_STUB_RESPONSE": "pong unavailable"},
                "no pong",
            ),
            (
                "the wrong model",
                {
                    "GEMINI_STUB_RESPONSE": "pong",
                    "GEMINI_STUB_MODELS": '["gemini-2.5-flash"]',
                },
                f"GEMINI ARM FAILED [{DEFAULT_MODEL!r}]",
            ),
            (
                "a JSON error",
                {"GEMINI_STUB_RESPONSE": "pong", "GEMINI_STUB_ERROR": '{"type": "X"}'},
                f"GEMINI ARM FAILED [{DEFAULT_MODEL!r}]",
            ),
            (
                "rc 1",
                {"GEMINI_STUB_RESPONSE": "pong", "GEMINI_STUB_RC": "1"},
                "exited 1",
            ),
        ):
            with self.subTest(case=case):
                env_before = dict(self.env)
                self.env.update(overrides)
                try:
                    result = self.run_preflight()
                finally:
                    self.env = env_before
                self.assertNotEqual(0, result.returncode, result.stdout)
                self.assertNotIn("healthy", result.stdout)
                self.assertIn(reason, result.stderr)

    def test_a_ping_killed_before_the_adapter_refused_still_names_the_model(self):
        # The stand-in for a timeout: the CLI kills its parent, the adapter, so no refusal is ever written.
        self.env["GEMINI_STUB_RESPONSE"] = "pong"
        self.env["GEMINI_STUB_KILL_PARENT"] = "1"
        result = self.run_preflight()
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn(f"gemini preflight ({DEFAULT_MODEL})", result.stderr)
        self.assertIn("no adapter refusal was recorded", result.stderr)

    def test_a_missing_cli_names_the_model(self):
        tools = self.tmp / "no-gemini"
        tools.mkdir()
        for name in ("python3", "git"):
            found = shutil.which(name, path=os.environ["PATH"])
            if found is None:
                self.fail(f"{name} is not on the suite's PATH")
            (tools / name).symlink_to(found)
        self.env["PATH"] = f"{tools}{os.pathsep}/usr/bin{os.pathsep}/bin"
        self.assertIsNone(
            shutil.which("gemini", path=self.env["PATH"]),
            "a gemini is still on the PATH",
        )
        result = self.run_preflight()
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(
            f"gemini preflight ({DEFAULT_MODEL}): the gemini CLI is not on PATH",
            result.stderr,
        )

    def test_a_checkout_left_unreadable_names_the_model(self):
        self.env["GEMINI_STUB_RESPONSE"] = "pong"
        self.env["GEMINI_STUB_WRITE"] = str(
            self.root / ".git" / "HEAD"
        )  # garbage HEAD: git cannot read the repo
        result = self.run_preflight()
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn(
            f"gemini preflight ({DEFAULT_MODEL}): FAILED — the gemini CLI left the checkout unreadable",
            result.stderr,
        )

    def test_the_ping_runs_on_the_gates_model_with_the_policy(self):
        self.env["GEMINI_STUB_RESPONSE"] = "pong"
        result = self.run_preflight()
        self.assertEqual(0, result.returncode, result.stderr)
        argv = self.calls()[0]["argv"]
        self.assertEqual(DEFAULT_MODEL, _option(argv, "-m"))
        self.assertEqual(
            os.path.realpath(POLICY), os.path.realpath(_option(argv, "--policy"))
        )
        self.assertRegex(_option(argv, "--allowed-mcp-server-names"), NO_MCP)

    def test_the_diagnostics_survive_the_scratch_cleanup(self):
        self.env["GEMINI_STUB_RESPONSE"] = "pong"
        result = self.run_preflight()
        diag = Path(f"{self.ping_path(result)}.diag")
        self.assertIn(
            "VERDICT: APPROVE", diag.read_text(encoding="utf-8")
        )  # the stub's stderr

    def test_the_ping_does_not_run_in_the_checkout(self):
        self.env["GEMINI_STUB_RESPONSE"] = "pong"
        self.env["GEMINI_STUB_WRITE"] = (
            "WROTE_IN_CWD.txt"  # relative: wherever the ping runs
        )
        result = self.run_preflight()
        self.assertFalse(
            (self.root / "WROTE_IN_CWD.txt").exists(),
            "the ping ran in the reviewed checkout",
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_write_into_the_checkout_is_caught_and_reports_only_it(self):
        self.env["GEMINI_STUB_RESPONSE"] = "pong"
        self.env["GEMINI_STUB_WRITE"] = str(self.root / "SNEAKED_IN.txt")
        result = self.run_preflight()
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn(
            f"gemini preflight ({DEFAULT_MODEL}): FAILED — the gemini CLI MUTATED",
            result.stderr,
        )
        self.assertIn("COREDEV-2607", result.stderr)
        reported = [
            line for line in result.stderr.splitlines() if line.startswith("??")
        ]
        self.assertEqual(["?? SNEAKED_IN.txt"], reported, result.stderr)

    def test_a_content_edit_to_an_already_dirty_tracked_file_is_caught(self):
        tracked = self.root / "tracked.txt"
        tracked.write_text(
            "dirty edit\n", encoding="utf-8"
        )  # already ` M` before the ping
        self.env["GEMINI_STUB_RESPONSE"] = "pong"
        self.env["GEMINI_STUB_WRITE"] = str(tracked)
        result = self.run_preflight()
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("MUTATED", result.stderr)
        self.assertIn("content", result.stderr.lower())
        self.assertEqual(
            [], [line for line in result.stderr.splitlines() if line.startswith("??")]
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
