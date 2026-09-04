#!/usr/bin/env python3
"""COREDEV-2801 §3b cell 8 — the SessionStart surface of the drift detector.

THE CLAIM IS SPLIT HONESTLY. CI cannot invoke a real `SessionStart` hook: this repository does install
Claude Code later in `plugin-ci.yml`, but the Python suites run BEFORE that step. So this file asserts
the DECLARATION against the documented stdin contract, and exercises the detector's behaviour by
running the shipped script. A run of the WIRED COMMAND is recorded separately as committed evidence,
the same standing cells 10 and 12 have — and that artifact is explicit that it exercises the command
and not Claude Code's hook dispatcher, which nothing in this pipeline can invoke. Claiming a CI proof
this pipeline cannot produce would be a cell that cannot pass; so would leaving the docstring saying
"the one real session-start invocation" after the artifact itself retracted that (PR #85).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import pty
import select
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SETTINGS = REPO / ".claude/settings.json"
OBSERVATION = REPO / "docs/planning/evidence/COREDEV-2801-sessionstart-observation.json"
DETECTOR = REPO / "scripts/detect-plugin-version-drift.sh"
BUCKET_SECONDS = (
    604800  # seven days, asserted as an OPERAND, not merely "a constant exists"
)
EXPECTED_TIMEOUT = 5
EXPECTED_MATCHER = "startup|resume"


def _session_start_hook() -> dict:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    entries = settings["hooks"]["SessionStart"]
    assert len(entries) == 1, "exactly one SessionStart entry"
    entry = entries[0]
    assert isinstance(entry, dict), "the SessionStart entry must be a mapping"
    return entry


class TheDeclaration(unittest.TestCase):
    def test_matchers_are_startup_and_resume_only(self):
        """SessionStart also fires on `clear` and `compact`; a warning there is noise about a
        condition the human already saw at startup."""
        self.assertEqual(EXPECTED_MATCHER, _session_start_hook()["matcher"])

    def test_timeout_is_the_literal_five(self):
        """Asserting the KEY alone accepts the 600-second default this contract exists to override —
        covering the line without covering its operand."""
        hook = _session_start_hook()["hooks"][0]
        self.assertEqual(EXPECTED_TIMEOUT, hook["timeout"])
        self.assertNotEqual(600, hook["timeout"])

    def test_the_root_is_passed_as_an_operand_and_the_script_is_resolved_from_the_project(
        self,
    ):
        command = _session_start_hook()["hooks"][0]["command"]
        self.assertIn(
            "${CLAUDE_PROJECT_DIR}/scripts/detect-plugin-version-drift.sh", command
        )
        self.assertIn("--session-start", command)
        # The ROOT is an argument, not something the detector reads from the environment itself.
        self.assertGreaterEqual(command.count("${CLAUDE_PROJECT_DIR}"), 2)

    def test_the_detector_never_reads_the_ambient_variable_itself(self):
        """The whole point of the operand: git does not set CLAUDE_PROJECT_DIR for the OTHER caller,
        and a value inherited from a different project selects a foreign repository."""
        self.assertNotIn(
            "CLAUDE_PROJECT_DIR",
            DETECTOR.read_text(encoding="utf-8").split("# Usage:")[1],
        )


class _DetectorFixture(unittest.TestCase):
    """A repository whose `origin/main` serves `expected`, and a home whose record serves `installed`."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        (self.repo / ".claude-plugin").mkdir(parents=True)
        self._git("init", "-q", ".")
        self._git("config", "user.email", "t@t")
        self._git("config", "user.name", "t")
        self.home = self.root / "home"
        (self.home / ".claude/plugins").mkdir(parents=True)
        self.state = self.root / "state"
        self.set_expected("2.8.6")
        self.set_installed("2.8.5")

    def tearDown(self):
        self._tmp.cleanup()

    def _git(self, *args):
        subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True, capture_output=True
        )

    def set_expected(self, version: str):
        (self.repo / ".claude-plugin/plugin.json").write_text(
            json.dumps({"name": "unleashed-mail", "version": version}), encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-qm", version)
        self._git("update-ref", "refs/remotes/origin/main", "HEAD")

    def diverge_worktree(self, version: str):
        """Advance the WORKTREE, the INDEX and HEAD past `origin/main`, which stays where it was.

        `set_expected` points `origin/main` AT `HEAD`, so all four sources carry identical bytes
        and a detector reading the worktree, the index or HEAD behaves exactly like one reading
        `origin/main`. Every assertion in this file passes either way — the fixture making
        distinct sources equal, which is the defect class that already cost this repository three
        guard regressions (COREDEV-2811). After this call they disagree, and only an
        `origin/main` read produces the recorded answer.
        """
        (self.repo / ".claude-plugin/plugin.json").write_text(
            json.dumps({"name": "unleashed-mail", "version": version}), encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-qm", f"worktree ahead at {version}")

    def set_installed(self, version, scope="user", name="unleashed-mail"):
        """THE REAL RECORD SHAPE, read from a live machine rather than assumed:

            {"version": 2, "plugins": {"<name>@<marketplace>": [{"scope": …, "version": …}, …]}}

        The first draft of this fixture invented `{scope: {name: info}}`, which would have made the
        whole suite green against a detector that is SILENT FOREVER on every real install — the
        fixture defining the test's correctness rather than the contract doing it.
        """
        (self.home / ".claude/plugins/installed_plugins.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        f"{name}@npranson-unleashed-mail-plugin": [
                            {
                                "scope": scope,
                                "version": version,
                                "installPath": f"/tmp/{name}/{version}",
                            },
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )

    def run_detector(self, *args, payload=None, cwd=None, env_extra=None):
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.state),
        }
        env.update(env_extra or {})
        return subprocess.run(
            ["bash", str(DETECTOR), *args],
            check=False,
            input=payload if payload is not None else "",
            capture_output=True,
            text=True,
            cwd=str(cwd or self.root),
            env=env,
        )

    def session_start(self, session_id: str, **kwargs):
        return self.run_detector(
            str(self.repo),
            "--session-start",
            payload=json.dumps({"session_id": session_id}),
            **kwargs,
        )


class TheAnchoredLookup(_DetectorFixture):
    def test_it_resolves_the_project_repository_from_an_unrelated_working_directory(
        self,
    ):
        """A bare `git show origin/main:…` works from the repository root and silently takes Table A
        row 1 when SessionStart fires from somewhere else — reporting nothing, forever, on exactly the
        machines it exists to warn."""
        with tempfile.TemporaryDirectory() as elsewhere:
            completed = self.session_start("cwd-check", cwd=elsewhere)
        self.assertIn("systemMessage", completed.stdout)

    def test_dropping_the_root_operand_makes_it_silent(self):
        """The mutation. Without this the cell proves the script was LOCATED, not that it looked in
        the right place."""
        with tempfile.TemporaryDirectory() as elsewhere:
            completed = self.run_detector(
                elsewhere,
                "--session-start",
                payload='{"session_id":"x"}',
                cwd=elsewhere,
            )
        self.assertEqual("", completed.stdout.strip())

    def test_a_foreign_root_is_a_wrong_comparison_not_an_error(self):
        """This is why the operand exists rather than an ambient variable: pointing at another
        project's repository does not fail, it MISCLASSIFIES."""
        foreign = self.root / "foreign"
        (foreign / ".claude-plugin").mkdir(parents=True)
        subprocess.run(
            ["git", "-C", str(foreign), "init", "-q", "."],
            check=True,
            capture_output=True,
        )
        for key, value in (("user.email", "t@t"), ("user.name", "t")):
            subprocess.run(
                ["git", "-C", str(foreign), "config", key, value],
                check=True,
                capture_output=True,
            )
        (foreign / ".claude-plugin/plugin.json").write_text(
            json.dumps({"name": "unleashed-mail", "version": "1.0.0"}), encoding="utf-8"
        )
        for args in (
            ("add", "-A"),
            ("commit", "-qm", "f"),
            ("update-ref", "refs/remotes/origin/main", "HEAD"),
        ):
            subprocess.run(
                ["git", "-C", str(foreign), *args], check=True, capture_output=True
            )
        # installed 2.8.5 is BEHIND the project (2.8.6) and AHEAD of the foreign repo (1.0.0), so the
        # foreign root turns a row-7 warning into a row-8 silence.
        self.assertIn("systemMessage", self.session_start("real").stdout)
        foreign_run = self.run_detector(
            str(foreign), "--session-start", payload='{"session_id":"foreign"}'
        )
        self.assertEqual("", foreign_run.stdout.strip())


class TableA(_DetectorFixture):
    """Every row, and only row 7 speaks. SILENT MEANS SILENT: no output, and nothing recorded."""

    def _plain(self):
        return self.run_detector(str(self.repo)).stdout.strip()

    def test_row_7_installed_below_expected_warns(self):
        self.assertIn("is behind origin/main", self._plain())

    def test_the_expected_version_is_read_from_ORIGIN_and_not_the_checkout(self):
        """COREDEV-2811. The whole point of this detector is "what does origin/main SERVE", not
        "what is in my tree" — on a feature branch those differ by construction, and reading the
        checkout would compare the install against unreleased work and warn about nothing.
        """
        self.diverge_worktree("9.9.9")
        out = self._plain()
        self.assertIn("is behind origin/main 2.8.6", out)
        self.assertNotIn(
            "9.9.9", out, "the worktree's version must not reach the comparison at all"
        )

    def test_a_worktree_ahead_of_origin_does_not_MANUFACTURE_a_warning(self):
        """The silent direction, and it has to be built so the two reads DISAGREE.

        My first attempt here set the worktree BEHIND origin and asserted silence — and a
        worktree-reading detector produces silence too, by the locally-newer row. It passed
        against the mutant, proving nothing. Setting the worktree AHEAD makes the wrong read
        warn about an unreleased version while the right read stays silent.
        """
        self.set_installed("2.8.6")  # equal to origin/main -> silent
        self.diverge_worktree("9.9.9")  # a worktree read would call this "behind 9.9.9"
        self.assertEqual(
            "",
            self._plain(),
            "unreleased work in the tree is not a released version to lag",
        )

    def test_row_6_equal_is_silent(self):
        self.set_installed("2.8.6")
        self.assertEqual("", self._plain())

    def test_row_8_locally_newer_is_silent(self):
        """Warning here fires on every development clone."""
        self.set_installed("2.9.0")
        self.assertEqual("", self._plain())

    def test_row_5_equal_precedence_but_different_identity_is_silent(self):
        """SemVer ignores build metadata, so this pair is neither `<` nor `>` nor the same string."""
        self.set_installed("2.8.6+local")
        self.assertEqual("", self._plain())

    def test_row_4_not_comparable_is_silent(self):
        self.set_installed("not-a-semver")
        self.assertEqual("", self._plain())

    def test_row_3_entry_absent_is_silent(self):
        self.set_installed("2.0.0", name="some-other-plugin")
        self.assertEqual("", self._plain())

    def test_row_2_unreadable_record_is_silent(self):
        (self.home / ".claude/plugins/installed_plugins.json").write_text(
            "{not json", encoding="utf-8"
        )
        self.assertEqual("", self._plain())

    def test_row_2_unrecognised_schema_is_silent(self):
        """A record without the `plugins` mapping — a future or foreign shape."""
        (self.home / ".claude/plugins/installed_plugins.json").write_text(
            json.dumps({"version": 99, "somethingElse": {}}), encoding="utf-8"
        )
        self.assertEqual("", self._plain())

    def test_the_detector_parses_under_the_bash_that_actually_runs_it(self):
        """macOS ships bash 3.2, and BOTH callers run on developer machines. bash 3.2 cannot parse a
        quoted heredoc inside a command substitution when the body contains an apostrophe — CI runs
        bash 5 and would never have noticed."""
        for shell in ("/bin/bash", "bash"):
            with self.subTest(shell=shell):
                completed = subprocess.run(
                    [shell, "-n", str(DETECTOR)], check=False, capture_output=True
                )
                self.assertEqual(0, completed.returncode, completed.stderr.decode())

    def test_row_1_malformed_expected_manifest_is_silent(self):
        (self.repo / ".claude-plugin/plugin.json").write_text(
            '{"name":', encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-qm", "bad")
        self._git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.assertEqual("", self._plain())

    def test_silent_rows_record_nothing(self):
        """Not merely 'no warning' — a silent row must leave no marker behind either."""
        self.set_installed("2.8.6")
        self.session_start("quiet")
        self.assertFalse(
            (self.state / "unleashed-mail/drift-warned").exists()
            and any((self.state / "unleashed-mail/drift-warned").iterdir())
        )

    def test_an_unset_HOME_keeps_the_ALWAYS_ZERO_contract(self):
        """The file's header promises "Exit: ALWAYS 0. This is a diagnostic, not a gate." It runs
        under `set -u`, where a bare `${HOME}` ABORTS with "unbound variable" — exit 1 plus a message
        on stderr, from the one script that must never produce either (gemini, PR #84).

        The environment is built explicitly rather than copied-and-unset, so HOME cannot leak in.
        """
        completed = subprocess.run(
            ["bash", str(DETECTOR), str(self.repo)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(self.root),
            env={"PATH": os.environ["PATH"]},  # deliberately NO HOME
        )
        self.assertNotIn("unbound variable", completed.stderr)
        self.assertEqual(0, completed.returncode, completed.stderr[-300:])
        self.assertEqual(
            "", completed.stdout.strip(), "a silent row emits nothing at all"
        )

    def test_it_never_blocks(self):
        for version in ("2.8.5", "2.8.6", "2.9.0", "nonsense"):
            with self.subTest(installed=version):
                self.set_installed(version)
                self.assertEqual(0, self.run_detector(str(self.repo)).returncode)


class TheOutputProtocolAndDedup(_DetectorFixture):
    def _markers(self):
        directory = self.state / "unleashed-mail/drift-warned"
        return sorted(p.name for p in directory.iterdir()) if directory.exists() else []

    def test_the_warning_is_a_systemMessage_not_bare_stdout(self):
        """A SessionStart hook's plain stdout is injected into the AGENT'S CONTEXT; only
        `systemMessage` is shown to the human as a notice."""
        payload = json.loads(self.session_start("shape").stdout)
        self.assertEqual(["systemMessage"], list(payload))
        self.assertIn("is behind origin/main", payload["systemMessage"])

    def test_one_warning_per_session_per_window(self):
        self.assertIn("systemMessage", self.session_start("same").stdout)
        self.assertEqual("", self.session_start("same").stdout.strip())

    def test_distinct_sessions_each_warn(self):
        """The dedup must be PER SESSION. A bug that made it global would look correct from a single
        session and silence every other one on the machine for a week."""
        self.assertIn("systemMessage", self.session_start("one").stdout)
        self.assertIn("systemMessage", self.session_start("two").stdout)
        self.assertEqual(2, len(self._markers()))

    def test_the_marker_name_is_the_hashed_session_id(self):
        self.session_start("hash-me")
        digest = hashlib.sha256(b"hash-me").hexdigest()
        window = int(time.time()) // BUCKET_SECONDS
        self.assertIn(f"{digest}.{window}", self._markers())

    def test_filename_hostile_session_ids_still_warn(self):
        """`session_id` is documented as OPAQUE with no filename-safety contract. Raw, these make
        marker creation fail — and a detector that fails open warns on every single session start.
        """
        for session_id in ("a/b/c", "../../escape", "x" * 400, ""):
            with self.subTest(session_id=session_id[:16]):
                # A fresh fixture per id, torn down properly — re-running setUp() alone leaks the
                # previous TemporaryDirectory and the suite reports ResourceWarnings.
                self.tearDown()
                self.setUp()
                self.assertIn("systemMessage", self.session_start(session_id).stdout)

    def test_removing_the_hash_would_break_those_ids(self):
        """The mutation, shown rather than asserted: the raw id is not a usable path component."""
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(OSError):
            (Path(tmp) / "a/b/c.1").open("x").close()

    def test_a_prior_window_marker_is_swept_and_the_session_warns_again(self):
        """Aged-marker resumption: the promise is per WINDOW, not per session forever."""
        self.session_start("aged")
        directory = self.state / "unleashed-mail/drift-warned"
        digest = hashlib.sha256(b"aged").hexdigest()
        current = next(p for p in directory.iterdir() if p.name.startswith(digest))
        current.rename(directory / f"{digest}.1")
        self.assertIn("systemMessage", self.session_start("aged").stdout)
        self.assertNotIn(
            f"{digest}.1", self._markers(), "the prior-window marker must be swept"
        )

    def test_cleanup_removes_any_prior_window_not_just_seven_day_old_ones(self):
        """Not the same statement: just after a boundary, a marker SECONDS old belongs to a prior
        bucket and goes."""
        directory = self.state / "unleashed-mail/drift-warned"
        directory.mkdir(parents=True)
        digest = hashlib.sha256(b"fresh-but-prior").hexdigest()
        window = int(time.time()) // BUCKET_SECONDS
        (directory / f"{digest}.{window - 1}").write_text("", encoding="utf-8")
        self.session_start("fresh-but-prior")
        self.assertNotIn(f"{digest}.{window - 1}", self._markers())

    def test_the_bucket_constant_is_604800_as_an_operand(self):
        """A different constant puts the marker in a different bucket — which is what makes this a
        test of the operand and not merely of the line."""
        self.session_start("operand")
        digest = hashlib.sha256(b"operand").hexdigest()
        now = int(time.time())
        self.assertIn(f"{digest}.{now // BUCKET_SECONDS}", self._markers())
        self.assertNotIn(f"{digest}.{now // 86400}", self._markers())

    def test_concurrent_invocations_of_one_session_warn_exactly_once(self):
        """The O_EXCL create happens BEFORE the warning, so the loser goes silent rather than warning
        twice."""
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(lambda _: self.session_start("race").stdout, range(8))
            )
        self.assertEqual(1, sum("systemMessage" in r for r in results))


class TheRetentionPromiseIsKept(_DetectorFixture):
    """COREDEV-2801, PR #84 (codex). The sweep was scoped to the CURRENT SESSION'S digest, so it only
    ever tidied a session that came back in a later window. Every session that never resumed left an
    inode behind forever — on precisely the machines where a persistently stale install keeps the
    warning path hot. The promise was stated in the comment and not kept by the code.

    The two hazards a wider glob introduces are guarded here as well: it must not touch a marker that
    is still LIVE (any session's, not just this one's), and it must not unlink files it did not write.
    """

    def _dir(self):
        directory = self.state / "unleashed-mail/drift-warned"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _markers(self):
        directory = self.state / "unleashed-mail/drift-warned"
        return sorted(p.name for p in directory.iterdir()) if directory.exists() else []

    @staticmethod
    def _window():
        return int(time.time()) // BUCKET_SECONDS

    def test_it_sweeps_prior_window_markers_left_by_OTHER_sessions(self):
        """The regression this fix exists for. Under the old digest-scoped glob these survive the
        run, and nothing else in the suite would notice."""
        directory, window = self._dir(), self._window()
        abandoned = [hashlib.sha256(f"gone-{n}".encode()).hexdigest() for n in range(5)]
        for digest in abandoned:
            (directory / f"{digest}.{window - 1}").write_text("", encoding="utf-8")
        self.assertIn("systemMessage", self.session_start("the-sweeper").stdout)
        survivors = [n for n in self._markers() if n.split(".")[0] in abandoned]
        self.assertEqual(
            [], survivors, "another session's expired markers must be swept"
        )

    def test_it_does_not_touch_another_session_s_LIVE_marker(self):
        """The over-sweep hazard, and the reason the window is in the NAME rather than inferred from
        mtime: a concurrent session's current-window marker is indistinguishable from litter by age
        alone. Removing it would let that session warn a second time in the same window.
        """
        directory, window = self._dir(), self._window()
        live = hashlib.sha256(b"still-running").hexdigest()
        (directory / f"{live}.{window}").write_text("", encoding="utf-8")
        self.session_start("the-sweeper")
        self.assertIn(f"{live}.{window}", self._markers())

    def test_it_leaves_files_it_did_not_write(self):
        """The shape guard. Scoped to one digest the name was its own filter; unscoped, this loop
        runs in a directory it no longer wholly owns, and `notes.3` is not ours to delete.
        """
        directory, window = self._dir(), self._window()
        foreign = ["notes.3", "README.txt", f"{'g' * 64}.{window - 1}", "short.1"]
        for name in foreign:
            (directory / name).write_text("keep me", encoding="utf-8")
        self.session_start("the-sweeper")
        for name in foreign:
            self.assertIn(
                name, self._markers(), f"{name} is not this script's to unlink"
            )

    def test_a_marker_shaped_DIRECTORY_does_not_cost_the_session_its_warning(self):
        """The warning is decided and emitted BEFORE the sweep, and the sweep is best-effort. An
        entry that cannot be unlinked is litter, not a reason to swallow the notice the hook was run
        to produce — and the hook is declared with `timeout: 5`, so cleanup must never be on the
        critical path to the output."""
        directory, window = self._dir(), self._window()
        (directory / f"{'a' * 64}.{window - 1}").mkdir()
        self.assertIn("systemMessage", self.session_start("undeletable").stdout)


class AManualRunDoesNotHangAndDoesNotBurnAMarker(_DetectorFixture):
    """`hook_payload="$(cat)"` blocks forever when stdin is a terminal, so running the detector by
    hand with `--session-start` — to debug it, or to see what it would say — hangs until interrupted
    (gemini, PR #84). Reproduced under a real pty before the fix: it never exited.

    The obvious repair is to substitute an empty payload, and it is WRONG in a way this file already
    documents: `session_id` would be the empty string, every marker would be named for sha256("")
    and the per-session dedup would silently become global — one session per machine per week warns
    and the rest stay quiet. So the TTY case degrades to the plain-text path, and the assertion below
    is two-sided: it must emit the warning AND leave the marker directory untouched.
    """

    def _under_a_pty(self, timeout=15):
        pid, fd = pty.fork()
        if pid == 0:  # pragma: no cover - child process
            os.environ["HOME"] = str(self.home)
            os.environ["XDG_STATE_HOME"] = str(self.state)
            os.chdir(str(self.root))
            os.execv(
                "/bin/bash",
                ["/bin/bash", str(DETECTOR), str(self.repo), "--session-start"],
            )
        # EVERY READ IS GUARDED BY `select`. A pty fd is blocking, so a bare `os.read` on a child
        # that produces no output and never exits waits forever — which is precisely the regression
        # this class exists to catch, so the FIRST draft of this harness hung indefinitely instead of
        # failing at its own deadline. A test that can hang is worse than the bug it looks for: it
        # takes CI down rather than reporting. The deadline is now enforced on every iteration.
        output, deadline, status = b"", time.monotonic() + timeout, None
        while time.monotonic() < deadline:
            done, raw = os.waitpid(pid, os.WNOHANG)
            if done:
                status = raw
                while select.select([fd], [], [], 0.2)[0]:
                    try:
                        chunk = os.read(fd, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output += chunk
                break
            if select.select([fd], [], [], 0.1)[0]:
                with contextlib.suppress(OSError):
                    output += os.read(fd, 4096)
        else:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            os.close(fd)
            self.fail("the detector hung on a TTY stdin instead of returning")
        os.close(fd)
        return status, output.decode("utf-8", "replace")

    def test_it_returns_instead_of_blocking_on_cat(self):
        status, output = self._under_a_pty()
        self.assertEqual(0, status, "a manual run must exit cleanly")
        self.assertIn(
            "is behind origin/main", output, "it must still say what it found"
        )

    def test_it_does_not_consume_a_real_session_s_warning(self):
        """The two-sided half. A TTY run that wrote a marker would silence the next genuine
        SessionStart for the rest of the window — the detector eating its own notice."""
        self._under_a_pty()
        directory = self.state / "unleashed-mail/drift-warned"
        written = (
            sorted(p.name for p in directory.iterdir()) if directory.exists() else []
        )
        self.assertEqual([], written, "a manual run must not write a dedup marker")

    def test_it_emits_PLAIN_TEXT_not_the_hook_protocol(self):
        """`{"systemMessage": …}` is for a hook harness that is not there. A human at a terminal
        should see the sentence, not the envelope."""
        _, output = self._under_a_pty()
        self.assertNotIn("systemMessage", output)


class TheVersionGrammarIsSemVerNotACharacterClass(_DetectorFixture):
    """Row 4 says a version that is not comparable produces SILENCE. "Comparable" means valid SemVer,
    and the first grammar was a permissive character class — `[0-9A-Za-z.-]+` for the prerelease —
    which accepts strings the specification forbids (codex, PR #84).

    It matters because `precedence()` calls `int()` on any all-digit identifier: `2.8.0-01` compared
    as `2.8.0-1` and produced a stale-install WARNING about malformed registry data, where the
    contract calls for silence. Driven end to end through the real detector, not against the regex.
    """

    VALID = ("2.8.0", "2.8.0-alpha.1", "2.8.0-1", "2.8.0-0alpha", "2.8.0+build.1")
    INVALID = (
        "2.8.0-01",
        "2.8.0-alpha..1",
        "2.8.0-",
        "2.8.0-+x",
        "2.8..0",
        "v2.8.0",
        # NON-ASCII DIGITS. Python's `\d` is Unicode-aware, so these MATCHED the "official" grammar
        # — and `str.isdigit()`/`int()` accept them too, so they compared as numbers and warned where
        # row 4 requires silence. SemVer's numeric identifiers are [0-9] only (codex, PR #84).
        "1\u0662.0.0",
        "2.8.0-1\u0662",
        # WHITESPACE-WRAPPED. `.strip()` used to trim these into validity, so malformed registry
        # data warned where row 4 requires silence. The trailing-newline form is separate: Python's
        # `$` matches just before one, so dropping `.strip()` alone left it accepted — the anchor is
        # `\Z` (codex, PR #84).
        " 2.8.5 ",
        "2.8.5 ",
        "\t2.8.5",
        "2.8.5\n",
    )

    def test_an_invalid_prerelease_takes_the_row_4_SILENT_path(self):
        for version in self.INVALID:
            with self.subTest(installed=version):
                self.tearDown()
                self.setUp()
                self.set_installed(version)
                completed = self.run_detector(str(self.repo))
                self.assertEqual(0, completed.returncode)
                self.assertEqual(
                    "",
                    completed.stdout.strip(),
                    f"{version} is not valid SemVer, so it is not comparable and must be silent",
                )

    def test_a_VALID_prerelease_is_still_compared(self):
        """The two-sided half. A grammar tightened until it rejects everything would pass the test
        above and make the detector silent forever — the failure this file has already had once.
        """
        for version in self.VALID:
            with self.subTest(installed=version):
                self.tearDown()
                self.setUp()
                self.set_installed(version)
                completed = self.run_detector(str(self.repo))
                self.assertIn(
                    "is behind origin/main",
                    completed.stdout,
                    f"{version} is valid SemVer below the expected version and must warn",
                )


class TheRevertedRecordIsDistinguishedFromANeverUpdatedOne(_DetectorFixture):
    """COREDEV-2801, post-gate addition (2026-09-02). NOT part of the reviewed Table A — it changes
    no row's verdict and only extends the text of an existing row-7 warning.

    A record that is behind has two causes with one symptom: nobody updated, or an update was
    UNDONE. On 2026-09-02 the second happened here — the record selected 2.7.0 while a complete
    `.../2.8.3/` sat in the install cache, written the same second as the record. Those call for
    different responses, so the detector now says which it is: the install cache is the evidence,
    read from the sibling directories of the entry's own `installPath`.
    """

    def _stage(self, *versions, selected="2.7.0"):
        """Build a real cache tree and point the record's installPath into it."""
        cache = self.home / ".claude/plugins/cache/mkt/unleashed-mail"
        for version in versions:
            (cache / version).mkdir(parents=True, exist_ok=True)
        (self.home / ".claude/plugins/installed_plugins.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "unleashed-mail@mkt": [
                            {
                                "scope": "user",
                                "version": selected,
                                "installPath": str(cache / selected),
                            }
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_a_newer_version_already_in_the_cache_is_reported_as_a_REVERSION(self):
        self._stage("2.7.0", "2.8.3", selected="2.7.0")
        out = self.run_detector(str(self.repo)).stdout
        self.assertIn("is behind origin/main", out)
        self.assertIn("2.8.3 is present in the install cache", out)
        self.assertIn("already downloaded locally", out)
        self.assertNotIn(
            "revert",
            out,
            "the message must not claim a history it did not observe",
        )

    def test_with_NOTHING_newer_staged_the_warning_carries_no_such_claim(self):
        """The two-sided half. A note that always appears says nothing; it must be absent when the
        install genuinely was never updated, or it would misdiagnose every stale machine.
        """
        self._stage("2.7.0", selected="2.7.0")
        out = self.run_detector(str(self.repo)).stdout
        self.assertIn("is behind origin/main", out)
        self.assertNotIn("present in the install cache", out)

    def test_it_reports_the_HIGHEST_staged_version_not_merely_a_newer_one(self):
        self._stage("2.7.0", "2.8.0", "2.8.2", "2.8.3", selected="2.7.0")
        out = self.run_detector(str(self.repo)).stdout
        self.assertIn("2.8.3 is present in the install cache", out)
        self.assertNotIn("2.8.0 is present", out)

    def test_a_SILENT_row_stays_silent_even_with_a_newer_version_staged(self):
        """THE CONTRACT TEST. Table A's silent rows are the plan's binding promise, and this addition
        must not create a warning where the reviewed table says nothing. An install already AT
        origin/main is row 6 — silent — regardless of what else sits in the cache."""
        # 2.8.6 is what the fixture's origin/main declares — row 6, exact identity, silent. Picking
        # 2.8.3 here the first time made this fail for a FIXTURE reason (2.8.3 really is behind
        # 2.8.6), which would have read as the contract breaking when it was the test that was wrong.
        self._stage("2.8.6", "2.9.9", selected="2.8.6")
        completed = self.run_detector(str(self.repo))
        self.assertEqual(0, completed.returncode)
        self.assertEqual("", completed.stdout.strip())

    def test_row_8_a_LOCALLY_NEWER_install_stays_silent_with_more_staged(self):
        """THE CONTRACT TEST THAT ACTUALLY DISCRIMINATES.

        The first one I wrote used an install EQUAL to origin/main — row 6 — which `continue`s out of
        the loop before the new code is ever reached, so it could not have caught a leak. A mutation
        that emitted the note for every row passed it. Row 8 (installed AHEAD of origin/main, silent
        because every development clone looks like that) is the row that reaches the new code and
        must still say nothing.
        """
        self._stage("2.9.0", "2.9.9", selected="2.9.0")
        completed = self.run_detector(str(self.repo))
        self.assertEqual(0, completed.returncode)
        self.assertEqual(
            "",
            completed.stdout.strip(),
            "row 8 is silent; a locally newer install must not be warned about",
        )

    def test_an_unreadable_cache_directory_does_not_break_the_warning(self):
        """The note is best-effort: losing it must not cost the warning it decorates."""
        cache = self.home / ".claude/plugins/cache/mkt/unleashed-mail"
        (cache / "2.7.0").mkdir(parents=True)
        (self.home / ".claude/plugins/installed_plugins.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "unleashed-mail@mkt": [
                            {"scope": "user", "version": "2.7.0", "installPath": None}
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        out = self.run_detector(str(self.repo)).stdout
        self.assertIn("is behind origin/main", out)
        self.assertNotIn("present in the install cache", out)


class TheRecordedObservationIsCommittedAndBounded(unittest.TestCase):
    """COREDEV-2808. This module's own docstring defers to "one real session-start invocation
    recorded separately as committed evidence" — and that file did not exist. An observation nobody
    committed is indistinguishable from one nobody made, and the promise was worse than silence:
    it made the absence read as a deliberate split of the claim rather than as a gap in it.
    """

    def setUp(self):
        self.assertTrue(
            OBSERVATION.is_file(),
            f"{OBSERVATION.name} is the evidence this module explicitly defers to",
        )
        self.observation = json.loads(OBSERVATION.read_text(encoding="utf-8"))

    def test_the_observation_is_bound_to_the_LIVE_wiring(self):
        """A recorded command that no longer matches settings.json is evidence about a hook that is
        no longer wired. Binding the two here is what stops the file decaying into a souvenir —
        the failure mode this repo has already hit three times with digests written and never read.
        """
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        live = [
            hook["command"]
            for group in settings["hooks"]["SessionStart"]
            for hook in group["hooks"]
            if "detect-plugin-version-drift" in hook["command"]
        ]
        self.assertEqual(
            1, len(live), "exactly one SessionStart drift invocation is wired"
        )
        self.assertEqual(
            live[0],
            self.observation["entryPoint"]["command"],
            "the observation records a command the repository no longer wires",
        )

    def test_it_states_what_it_does_NOT_establish(self):
        """The artifact first called itself an observation through the real entry point, while the
        recorded run pipes a payload straight into the script — exercising the script and the
        argument vector, not Claude Code's hook dispatcher. An evidence file that overstates its own
        reach is worse than a missing one, because the gap stops being visible (codex, PR #85).

        The wiring is evidenced separately, and independently: a live SessionStart writes a dedup
        marker into the state directory, and this observation ran with XDG_STATE_HOME isolated, so
        it cannot have written the markers it cites.
        """
        # THE PROPERTY, NOT THREE SPELLINGS. The first version of this asserted that certain words
        # appeared in certain fields, which any rewording defeats and no rewording of the CLAIM
        # would trip. What actually has to hold is that the artifact records a command DIFFERENT
        # from the one settings.json wires — that gap is the limitation being disclosed — and that
        # it does not present itself as having exercised the wiring.
        scope = self.observation["whatThisDoesAndDoesNotShow"]
        self.assertNotEqual(
            self.observation["entryPoint"]["command"],
            self.observation["command"],
            "if these were the same, there would be no limitation to disclose",
        )
        self.assertTrue(
            scope.get("doesNotShow", "").strip(),
            "an artifact that cannot say what it fails to show is back to overclaiming",
        )
        # SCOPED TO THE FIELDS THAT MAKE CLAIMS. A blanket ban on the phrase fails against the
        # RETRACTION, which has to name what it is retracting — the first version of this assertion
        # did exactly that. What must not survive is the artifact still ASSERTING it.
        asserting = " ".join(
            str(self.observation.get(field, ""))
            for field in ("experiment", "why", "outcome", "note")
        ).lower()
        self.assertNotIn("real entry point", asserting)

    def test_it_records_the_warning_AND_the_dedup(self):
        """One run only proves the hook fires. The dedup is a claim about the SECOND call, and no
        reading of the source establishes it — that is precisely why an observation was owed.
        """
        observed = self.observation["observed"]
        self.assertEqual(0, observed["run1"]["commandExitCode"])
        self.assertIn(
            "systemMessage",
            observed["run1"]["stdout"],
            "SessionStart's protocol is the systemMessage envelope, not a bare line",
        )
        self.assertEqual(
            0,
            observed["run2"]["stdoutBytes"],
            "the repeat in one session must be suppressed",
        )


class TheDetectorSaysWhenItCouldNotRun(unittest.TestCase):
    """COREDEV-2808's second half. Every comparison in the detector happens inside
    `python3 <<'PY' 2>/dev/null`, so with no interpreter the heredoc fails, its diagnostic is
    discarded, and the empty-warning guard takes the same silent exit 0 a healthy up-to-date
    install takes. "Could not check" must never look like "checked, and found nothing".
    """

    def test_an_absent_python3_is_stated_rather_than_read_as_no_drift(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fake = Path(tmp.name) / "bin"
        fake.mkdir()
        # EVERY OTHER TOOL STAYS. Dropping whole PATH directories also drops `git` and `mktemp`,
        # and the detector then exits early for an unrelated reason — a probe that reproduces
        # silence without reproducing its cause proves nothing.
        for directory in ("/usr/bin", "/bin"):
            source = Path(directory)
            if not source.is_dir():
                continue
            for entry in source.iterdir():
                if entry.name.startswith("python"):
                    continue
                target = fake / entry.name
                if not target.exists():
                    with contextlib.suppress(OSError):
                        target.symlink_to(entry)
        if (fake / "git").exists() is False:
            self.skipTest("no git available to build a python3-free PATH")
        completed = subprocess.run(
            ["bash", str(REPO / "scripts/detect-plugin-version-drift.sh"), str(REPO)],
            check=False,
            capture_output=True,
            text=True,
            env={"PATH": str(fake), "HOME": tmp.name},
            timeout=120,
        )
        self.assertEqual(0, completed.returncode, "advisory: it must never block")
        self.assertIn(
            "did NOT run",
            completed.stdout + completed.stderr,
            "silence here is indistinguishable from a clean, up-to-date install",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
