#!/usr/bin/env python3
"""The gemini arm runs the NEWEST flash-high model `agy models` lists (COREDEV-2875 §2.1, §3).

Each case runs SHIPPED code -- `agy-newest-model.sh`, the capture entrypoint, the isolated wrapper, the
recipe text itself -- with a stub `agy` on PATH that records every argv it receives. The cells this file
carries (plan §4): M1 selection, M2 fail-closed, M3 override, M4 production path and the `.model` record,
M7's executed recipes, M8 the one-token id, M9 a silent reviewer stays MISSING, M11 exclusive creation.

The fail-closed cases each assert the REASON, not merely a non-zero exit: several guards overlap (the byte
guard and the candidate grammar both reject a PTY-fused entry), so "it failed" alone would stay green with
any one guard deleted.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REVIEW = REPO / "scripts" / "review"
RESOLVER = REVIEW / "agy-newest-model.sh"
CAPTURE = REVIEW / "capture-gemini-review.sh"
ISOLATED = REVIEW / "isolated-agy-review.sh"
PTY_CAPTURE = REPO / "scripts" / "pty-capture.py"
VERDICT = REPO / "scripts" / "review-verdict.py"

# A recording agy. `models` writes the listing given in hex (so a test controls every byte), after an
# optional sleep and a stderr line agy really prints; anything else is a review launch.
AGY_STUB = r"""#!/usr/bin/env python3
import os, sys, time
log = os.environ.get("AGY_STUB_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(" ".join(sys.argv[1:]) + "\n")
if sys.argv[1:2] == ["models"]:
    sys.stderr.write("Fetching available models...\n")
    time.sleep(float(os.environ.get("AGY_STUB_SLEEP", "0")))
    sys.stdout.buffer.write(bytes.fromhex(os.environ.get("AGY_STUB_LISTING_HEX", "")))
    sys.exit(int(os.environ.get("AGY_STUB_MODELS_RC", "0")))
sys.stdout.write(os.environ.get("AGY_STUB_REVIEW", "VERDICT: APPROVE\nthe stub reviewed the plan.\n"))
sys.exit(int(os.environ.get("AGY_STUB_REVIEW_RC", "0")))
"""

REAL_SHAPE = (
    "gemini-3.8-flash-high\tGemini 3.8 Flash (High)\n"
    "gemini-3.8-flash-medium\tGemini 3.8 Flash (Medium)\n"
    "gemini-3.7-flash-high\tGemini 3.7 Flash (High)\n"
    "gemini-3.1-pro-high\tGemini 3.1 Pro (High)\n"
    "claude-opus-5-5-high\tClaude Opus 5.5 (High)\n"
)

PROMPT_BODY = (
    "REVIEW TARGET: docs/planning/FEATURE_PLAN.md\n"
    + (
        "Review the attached plan for correctness, security and completeness.\n"
        "State your verdict on the FIRST line as `VERDICT: APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES`.\n"
    )
    * 12
)


def _normalized(raw: bytes) -> str:
    return raw.decode("utf-8").replace("\r\n", "\n")


class _StubAgy:
    """A temporary directory with the recording agy on PATH."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agy-model-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        stubs = self.tmp / ".stubs"
        stubs.mkdir()
        agy = stubs / "agy"
        agy.write_text(AGY_STUB, encoding="utf-8")
        agy.chmod(0o755)
        self.log = self.tmp / "agy-argv.log"
        self.env = dict(os.environ)
        self.env.pop(
            "MODEL", None
        )  # never let an inherited value hide the resolver path
        self.env.pop("AGY_MODELS_TIMEOUT_S", None)
        self.env["PATH"] = f"{stubs}{os.pathsep}{self.env['PATH']}"
        self.env["AGY_STUB_LOG"] = str(self.log)
        self.listing(REAL_SHAPE)

    def listing(self, text, encoding: str = "utf-8") -> None:
        raw = text if isinstance(text, bytes) else text.encode(encoding)
        self.env["AGY_STUB_LISTING_HEX"] = raw.hex()

    def calls(self) -> list[str]:
        return (
            self.log.read_text(encoding="utf-8").splitlines()
            if self.log.exists()
            else []
        )

    def resolve(self, timeout: float = 30):
        return subprocess.run(
            ["bash", str(RESOLVER)],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            input="",
        )


class ResolverSelection(_StubAgy, unittest.TestCase):
    """M1: the newest RECOGNIZED flash-high wins, compared numerically."""

    def assertSelects(self, expected: str) -> None:
        result = self.resolve()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected + "\n", result.stdout)

    def test_the_real_listing_shape_selects_the_newest_flash_high(self):
        self.assertSelects("gemini-3.8-flash-high")

    def test_3_10_beats_3_9_numerically_tested_alone(self):
        # No `4` in the list: a STRING comparison would pick 3.9 here and nowhere else.
        self.listing("gemini-3.9-flash-high\ta\ngemini-3.10-flash-high\tb\n")
        self.assertSelects("gemini-3.10-flash-high")

    def test_a_major_version_beats_a_larger_minor(self):
        self.listing("gemini-3.10-flash-high\ta\ngemini-4-flash-high\tb\n")
        self.assertSelects("gemini-4-flash-high")

    def test_a_newer_second_column_decoy_is_ignored(self):
        self.listing(
            "gemini-3.8-flash-high\tx\ngemini-3.1-pro-high\tgemini-9-flash-high\n"
        )
        self.assertSelects("gemini-3.8-flash-high")

    def test_a_newer_preview_and_pro_are_not_candidates(self):
        self.listing(
            "gemini-3.8-flash-high\tx\ngemini-9-flash-high-preview\tp\ngemini-9.9-pro-high\tq\n"
        )
        self.assertSelects("gemini-3.8-flash-high")

    def test_an_empty_line_between_valid_rows_is_ignored(self):
        self.listing("gemini-3.8-flash-high\tx\n\ngemini-3.9-flash-high\ty\n")
        self.assertSelects("gemini-3.9-flash-high")

    def test_fetching_on_stderr_is_ignored(self):
        # The stub always prints `Fetching available models...` to stderr, as agy does.
        result = self.resolve()
        self.assertEqual("gemini-3.8-flash-high\n", result.stdout)
        self.assertEqual(["models"], self.calls())


class ResolverFailsClosed(_StubAgy, unittest.TestCase):
    """M2: every refusal is asserted by its REASON, and stdout stays empty."""

    def assertRefused(self, reason: str, timeout: float = 30) -> None:
        result = self.resolve(timeout=timeout)
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertEqual("", result.stdout, "a refusal must print nothing on stdout")
        self.assertIn(reason, result.stderr)

    def test_a_non_zero_listing_fails_even_when_it_printed_a_valid_candidate(self):
        self.env["AGY_STUB_MODELS_RC"] = "1"  # so ONLY the status check can catch it
        self.assertRefused("`agy models` exited 1")

    def test_an_empty_listing_fails(self):
        self.listing("")
        self.assertRefused("lists no gemini-<major>[.<minor>]-flash-high model")

    def test_each_malformed_line_fails_beside_a_valid_older_candidate(self):
        # Paired with a valid OLDER candidate on purpose: alone, a malformed line would fail as "no
        # candidate" whether or not the shape rule existed. A skip selects 3.9; the rule refuses.
        older = "gemini-3.9-flash-high\tolder\n"
        for name, row in (
            ("leading whitespace", " gemini-4-flash-high\tnewest\n"),
            ("trailing whitespace", "gemini-4-flash-high \tnewest\n"),
            ("a TAB-led row", "\tgemini-9-flash-high\tlabel\n"),
            ("a row with no TAB", "gemini-4-flash-high newest\n"),
        ):
            with self.subTest(malformation=name):
                self.listing(older + row)
                self.assertRefused("line 2 is not <id>TAB<label>")

    def test_a_pty_fused_newest_entry_fails_on_the_byte_guard(self):
        # The measured PTY form: the escape is fused to the FIRST entry, which is the newest.
        self.listing(b"\r\x1b[Kgemini-3.8-flash-high\tx\ngemini-3.7-flash-high\ty\n")
        self.assertRefused("forbidden byte 0x0d")

    def test_a_forbidden_byte_in_a_label_fails_on_the_byte_guard(self):
        # Only the byte guard can catch this: every id is well-formed.
        self.listing(
            b"gemini-3.8-flash-high\tGemini \x1b[1m3.8\x1b[0m\ngemini-3.7-flash-high\ty\n"
        )
        self.assertRefused("forbidden byte 0x1b")

    def test_an_unrecognized_newer_form_fails_beside_a_valid_older_candidate(self):
        self.listing("gemini-3.9-flash-high\tolder\ngemini-3.10.1-flash-high\tnewer?\n")
        self.assertRefused("unrecognized version form")

    def test_a_non_finite_or_non_numeric_timeout_fails_before_listing(self):
        for value, reason in (
            ("nan", "is not a finite number"),
            ("inf", "is not a finite number"),
            ("abc", "is not a number"),
        ):
            with self.subTest(value=value):
                self.env["AGY_MODELS_TIMEOUT_S"] = value
                self.assertRefused(f"AGY_MODELS_TIMEOUT_S={value!r} {reason}")
                self.assertEqual(
                    [], self.calls(), "the listing ran despite an invalid timeout"
                )

    def test_a_slow_listing_fails_in_bounded_time(self):
        # FINITE (5 s) so a removed timeout makes this case SUCCEED, not hang.
        self.env["AGY_STUB_SLEEP"] = "5"
        self.env["AGY_MODELS_TIMEOUT_S"] = "1"
        self.assertRefused("did not finish within 1s", timeout=20)


class _ReviewRepo(_StubAgy):
    """A real repository with a committed plan and a prompt, as the capture entrypoint needs."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        (self.root / "docs" / "planning").mkdir(parents=True)
        self.plan_rel = "docs/planning/FEATURE_PLAN.md"
        (self.root / self.plan_rel).write_text(
            "# Plan\n\nDo the thing, carefully.\n", encoding="utf-8"
        )
        for command in (
            ["git", "init", "-q", "."],
            ["git", "add", "-A"],
            [
                "git",
                "-c",
                "user.email=t@test",
                "-c",
                "user.name=t",
                "commit",
                "-qm",
                "init",
            ],
        ):
            subprocess.run(command, cwd=self.root, check=True)
        self.prompt = self.root / ".agy-prompt-COREDEV-9999r1.md"
        self.prompt.write_text(PROMPT_BODY, encoding="utf-8")
        self.state = self.tmp / "state"
        self.env["XDG_STATE_HOME"] = str(self.state)

    def transcripts(self) -> list[Path]:
        return (
            sorted(p for p in self.state.rglob("*.txt")) if self.state.exists() else []
        )

    def capture(self, *model_operand: str):
        argv = [
            "bash",
            str(CAPTURE),
            "COREDEV-9999",
            "1",
            self.prompt.name,
            self.plan_rel,
            "120",
            *model_operand,
        ]
        result = subprocess.run(
            argv,
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            input="",
            timeout=120,
        )
        marker = [
            line.split("=", 1)[1]
            for line in result.stdout.splitlines()
            if line.startswith("UNLEASHED_TRANSCRIPT=")
        ]
        return result, (Path(marker[0]) if marker else None)

    def review_calls(self) -> list[str]:
        return [call for call in self.calls() if call != "models"]


class ProductionPath(_ReviewRepo, unittest.TestCase):
    """M4 and M3: the real capture entrypoint runs the resolved model and records it beside the transcript."""

    def test_with_no_override_the_review_runs_the_newest_listed_model(self):
        self.assertNotIn("MODEL", self.env)
        result, transcript = self.capture()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "models", self.calls()[0], "the wrapper did not resolve its model"
        )
        reviews = self.review_calls()
        self.assertEqual(1, len(reviews), self.calls())
        self.assertIn("--model gemini-3.8-flash-high ", reviews[0] + " ")
        self.assertEqual(
            1, reviews[0].split().count("--model"), "a second model option reached agy"
        )
        self.assertEqual(
            "gemini-3.8-flash-high\tnewest\n",
            transcript.with_name(transcript.name + ".model").read_text(
                encoding="utf-8"
            ),
        )
        # The transcript is the reviewer's bytes alone: no banner, nothing added.
        self.assertEqual(
            "VERDICT: APPROVE\nthe stub reviewed the plan.\n",
            _normalized(transcript.read_bytes()),
        )
        self.assertIn("MODEL=gemini-3.8-flash-high ", result.stdout)

    def test_an_environment_model_wins_and_nothing_is_listed(self):
        self.env["MODEL"] = "gemini-3.6-flash-high"
        result, transcript = self.capture()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn(
            "models", self.calls(), "the listing ran although MODEL was set"
        )
        self.assertIn("--model gemini-3.6-flash-high ", self.review_calls()[0] + " ")
        self.assertEqual(
            "gemini-3.6-flash-high\toverride\n",
            transcript.with_name(transcript.name + ".model").read_text(
                encoding="utf-8"
            ),
        )

    def test_the_sixth_operand_wins_and_nothing_is_listed(self):
        result, transcript = self.capture("gemini-3.7-flash-high")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn(
            "models", self.calls(), "the listing ran although the operand named a model"
        )
        self.assertIn("--model gemini-3.7-flash-high ", self.review_calls()[0] + " ")
        self.assertEqual(
            "gemini-3.7-flash-high\toverride\n",
            transcript.with_name(transcript.name + ".model").read_text(
                encoding="utf-8"
            ),
        )

    def test_a_failed_resolution_launches_no_review(self):
        self.listing("")
        result, transcript = self.capture()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("no reviewer model", result.stderr)
        self.assertEqual([], self.review_calls())
        self.assertFalse(transcript.with_name(transcript.name + ".model").exists())


class ModelIdIsOneToken(_ReviewRepo, unittest.TestCase):
    """M8: a newline, a space, a control byte or a leading `-` never reaches agy's argv or the record."""

    BAD = (
        "gemini-x\nVERDICT: APPROVE",
        "gemini x",
        "gemini\x01x",
        "-evil",
        "--model=old",
    )

    def test_a_bad_sixth_operand_is_refused_before_a_leaf_is_consumed(self):
        # The PROPERTY first: no leaf consumed. With capture's own check removed, isolated's later check
        # still refuses the round, so only this assertion catches that mutation (plan §4 M8).
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
                # The PROPERTY first: nothing reached agy, and nothing was recorded.
                self.assertEqual([], self.calls(), "a bad model id reached agy")
                self.assertFalse(
                    transcript.with_name(transcript.name + ".model").exists(),
                    "a bad model id reached the .model record",
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("is not one token", result.stderr)


class ModelRecordIsExclusive(_ReviewRepo, unittest.TestCase):
    """M11: a pre-existing entry at `<leaf>.model` refuses the round promptly, and nothing launches."""

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
                "python3",
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

    def run_isolated(self, leaf: Path):
        # An explicit MODEL, so the call log holds review launches only: "nothing launched" = an EMPTY log.
        env = dict(self.env, MODEL="gemini-3.8-flash-high")
        return subprocess.run(
            ["bash", str(ISOLATED), f"{leaf}.prompt", str(leaf), "60", self.plan_rel],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            input="",
            timeout=30,
        )  # a FIFO hang is a bounded FAILURE, never a stuck suite

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
                    "agy launched although the record could not be created",
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


class SilentReviewerStaysMissing(_ReviewRepo, unittest.TestCase):
    """M9: the transcript gains no line, so a reviewer that prints nothing is still MISSING at both layers."""

    def test_both_layers_refuse_an_approval_backed_by_a_silent_reviewer(self):
        self.env["AGY_STUB_REVIEW"] = ""
        self.env["AGY_STUB_REVIEW_RC"] = "1"
        subprocess.run(
            ["python3", str(VERDICT), "snapshot", "--plan", self.plan_rel],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )
        _, transcript = self.capture()
        self.assertEqual(
            0,
            transcript.stat().st_size,
            "the silent reviewer's transcript is not empty",
        )
        codex = self.tmp / "codex-transcript.txt"
        codex.write_text("VERDICT: APPROVE\nfine.\n", encoding="utf-8")
        persisted = subprocess.run(
            [
                "bash",
                str(REVIEW / "persist-verdict.sh"),
                "--plan",
                self.plan_rel,
                "--verdict",
                "APPROVE",
                "--reviewer",
                f"gemini=APPROVE:{transcript}",
                "--reviewer",
                f"codex=APPROVE:{codex}",
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
                "python3",
                str(VERDICT),
                "write",
                "--plan",
                self.plan_rel,
                "--verdict",
                "APPROVE",
                "--reviewer",
                f"gemini=APPROVE:{transcript}",
                "--reviewer",
                f"codex=APPROVE:{codex}",
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


class ShippedRecipesExecute(_StubAgy, unittest.TestCase):
    """M7: the recipe TEXT the plugin ships resolves first, and a failed resolution launches nothing."""

    def setUp(self) -> None:
        super().setUp()
        self.plugin = self.tmp / "plugin"
        (self.plugin / "scripts" / "review").mkdir(parents=True)
        self.cwd = self.tmp / "cwd"
        (self.cwd / "review").mkdir(parents=True)
        (self.cwd / "pty-capture.py").symlink_to(PTY_CAPTURE)
        self.env["CLAUDE_PLUGIN_ROOT"] = str(self.plugin)
        self.env["TICKET"], self.env["ROUND"] = "COREDEV-9999", "1"

    def stub_resolver(self, body: str) -> None:
        for path in (
            self.plugin / "scripts" / "review" / "agy-newest-model.sh",
            self.cwd / "review" / "agy-newest-model.sh",
        ):
            path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
            path.chmod(0o755)

    def shipped_recipes(self) -> list[str]:
        """Every recipe that RESOLVES, found by the resolver call alone -- never by the `&&` that follows it.

        Keyed on `&&`, a recipe whose `&&` became `;` silently dropped out of execution, and only a
        `>= 3` count noticed (red-control battery). The count is EXACT: the review recipe (inline), the
        terminal example and the interactive example.
        """
        skill = (REPO / "skills" / "gemini-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        resolve = (
            'MODEL="$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/agy-newest-model.sh")"'
        )
        recipes = [
            line.strip()
            for line in skill.splitlines()
            if line.strip().startswith(resolve)
        ]
        recipes += [
            span for span in re.findall(r"`([^`]+)`", skill) if span.startswith(resolve)
        ]
        self.assertEqual(
            3, len(recipes), "the skill's resolving recipes changed in number"
        )
        return recipes

    def docstring_recipe(self) -> str:
        source = PTY_CAPTURE.read_text(encoding="utf-8")
        found = [
            line.strip()
            for line in source.splitlines()
            if "agy-newest-model.sh" in line and "pty-capture.py" in line
        ]
        self.assertEqual(
            1, len(found), "the pty-capture.py docstring's agy recipe was not found"
        )
        return found[0]

    def run_recipe(self, recipe: str):
        return subprocess.run(
            ["bash", "-c", recipe],
            cwd=self.cwd,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            input="",
            timeout=60,
        )

    def allocate(self) -> Path:
        self.env["XDG_STATE_HOME"] = str(self.tmp / "state")
        out = subprocess.run(
            [
                "python3",
                str(PTY_CAPTURE),
                "--allocate",
                "--repo-hash",
                "0123456789ab",
                "--ticket",
                "COREDEV-9999",
                "--round",
                "1",
                "--reviewer",
                "gemini",
            ],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return Path(out.split("=", 1)[1])

    def test_a_failed_resolution_launches_nothing_from_any_shipped_recipe(self):
        self.stub_resolver("exit 1")
        self.env["GEMINI_TRANSCRIPT"] = str(self.allocate())
        for recipe in [*self.shipped_recipes(), self.docstring_recipe()]:
            with self.subTest(recipe=recipe[:80]):
                self.run_recipe(recipe)
                self.assertEqual(
                    [], self.calls(), "agy launched after a failed resolution"
                )

    def test_the_docstring_pty_recipe_succeeds_with_the_resolved_model(self):
        self.stub_resolver('printf "gemini-9.9-flash-high\\n"')
        leaf = self.allocate()
        self.env["GEMINI_TRANSCRIPT"] = str(leaf)
        self.env["AGY_STUB_REVIEW"] = "STUB-REVIEW-BYTES\n"
        result = self.run_recipe(self.docstring_recipe())
        self.assertEqual(0, result.returncode, result.stderr)
        calls = self.calls()
        self.assertEqual(1, len(calls), calls)
        self.assertTrue(calls[0].startswith("--model gemini-9.9-flash-high "), calls[0])
        self.assertEqual(
            1, calls[0].split().count("--model"), "a second model option reached agy"
        )
        self.assertEqual("STUB-REVIEW-BYTES\n", _normalized(leaf.read_bytes()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
