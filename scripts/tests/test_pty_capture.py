"""Tests for scripts/pty-capture.py's session-safe transcript writer.

Covers the allocated/non-allocated write modes, their descriptor-based security discipline, and the
round-1 double-close fix: once open() owns the fd, the except path must not close it again (a second close
can clobber a concurrently reused fd number)."""
import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_PTY = os.path.normpath(os.path.join(_HERE, "..", "pty-capture.py"))


def _load():
    spec = importlib.util.spec_from_file_location("pty_capture_under_test", _PTY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WritePrivateTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load()
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_nonallocated_mode_creates_absent_target_at_0600(self):
        path = os.path.join(self.d, "t.txt")
        self.mod._write_private(path, b"hello")
        self.assertEqual(Path(path).read_bytes(), b"hello")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_nonallocated_mode_truncates_a_longer_world_readable_file(self):
        path = os.path.join(self.d, "t.txt")
        with open(path, "wb") as fh:
            fh.write(b"old-with-a-stale-suffix")
        os.chmod(path, 0o644)
        self.mod._write_private(path, b"new")
        self.assertEqual(Path(path).read_bytes(), b"new")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_allocated_mode_omits_create_and_truncate_but_retains_open_defences(self):
        path = os.path.join(self.d, "reserved.txt")
        Path(path).touch()
        real_open = os.open
        target_flags = []

        def _open_spy(open_path, flags, mode=0o777, *args, **kwargs):
            if os.fspath(open_path) == path:
                target_flags.append(flags)
            return real_open(open_path, flags, mode, *args, **kwargs)

        os.open = _open_spy
        try:
            self.mod._write_private(path, b"captured", allocated=True)
        finally:
            os.open = real_open

        self.assertEqual(len(target_flags), 1, "the reserved leaf should be opened exactly once")
        flags = target_flags[0]
        self.assertFalse(flags & os.O_CREAT, "allocated mode must not create the reserved leaf")
        self.assertFalse(flags & os.O_TRUNC, "allocated mode must not truncate the reserved leaf")
        self.assertTrue(flags & os.O_NOFOLLOW, "allocated mode must retain O_NOFOLLOW")
        self.assertTrue(flags & os.O_NONBLOCK, "allocated mode must retain O_NONBLOCK")
        self.assertEqual(Path(path).read_bytes(), b"captured")

    def test_allocated_mode_missing_leaf_is_a_hard_error_without_creating_retry(self):
        path = os.path.join(self.d, "missing.txt")
        real_open = os.open
        target_flags = []

        def _open_spy(open_path, flags, mode=0o777, *args, **kwargs):
            if os.fspath(open_path) == path:
                target_flags.append(flags)
            return real_open(open_path, flags, mode, *args, **kwargs)

        os.open = _open_spy
        try:
            with self.assertRaises(OSError):
                self.mod._write_private(path, b"must-not-land", allocated=True)
        finally:
            os.open = real_open

        self.assertFalse(os.path.lexists(path), "a missing reservation must not be recreated")
        self.assertTrue(target_flags, "the writer must attempt to open the reserved leaf")
        for flags in target_flags:
            self.assertFalse(flags & os.O_CREAT, "no retry may create the missing reservation")
            self.assertFalse(flags & os.O_TRUNC, "no retry may truncate a replacement target")

    def test_allocated_mode_consumes_reader_held_fifo_fstat_with_a_distinct_error(self):
        path = os.path.join(self.d, "reserved.fifo")
        os.mkfifo(path)
        reader_fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        real_open, real_fstat = os.open, os.fstat
        opened_fds = []
        fstat_fds = []

        def _open_spy(open_path, flags, mode=0o777, *args, **kwargs):
            fd = real_open(open_path, flags, mode, *args, **kwargs)
            if os.fspath(open_path) == path:
                opened_fds.append(fd)
            return fd

        def _fstat_spy(fd):
            fstat_fds.append(fd)
            return real_fstat(fd)

        os.open, os.fstat = _open_spy, _fstat_spy
        try:
            with self.assertRaises(self.mod.NonRegularCaptureTargetError):
                self.mod._write_private(path, b"must-not-land", allocated=True)
        finally:
            os.open, os.fstat = real_open, real_fstat
            os.close(reader_fd)

        self.assertTrue(opened_fds, "the FIFO must be opened before its file type is decided")
        self.assertEqual(fstat_fds, opened_fds, "fstat must consume the descriptor returned by os.open")

    def test_regular_fstat_result_does_not_mask_an_independent_rejection(self):
        path = os.path.join(self.d, "reserved.fifo")
        os.mkfifo(path)
        reader_fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        real_fstat, real_fchmod = os.fstat, os.fchmod

        class IndependentDefenceError(OSError):
            pass

        def _regular_fstat(fd):
            values = list(real_fstat(fd))
            values[0] = stat.S_IFREG | 0o600
            return os.stat_result(values)

        def _independent_rejection(_fd, _mode):
            raise IndependentDefenceError("independent defence")

        os.fstat, os.fchmod = _regular_fstat, _independent_rejection
        try:
            with self.assertRaises(IndependentDefenceError) as raised:
                self.mod._write_private(path, b"must-not-land", allocated=True)
        finally:
            os.fstat, os.fchmod = real_fstat, real_fchmod
            os.close(reader_fd)
        self.assertNotIsInstance(raised.exception, self.mod.NonRegularCaptureTargetError)

    def test_allocated_mode_fchmods_open_fd_before_writing_without_path_chmod(self):
        path = os.path.join(self.d, "reserved.txt")
        Path(path).touch()
        os.chmod(path, 0o644)
        real_chmod, real_fchmod, real_fstat = os.chmod, os.fchmod, os.fstat
        fchmod_observations = []

        def _fchmod_spy(fd, mode):
            fchmod_observations.append((mode, real_fstat(fd).st_size))
            return real_fchmod(fd, mode)

        def _path_chmod_forbidden(*_args, **_kwargs):
            raise AssertionError("the capture target must not be tightened through its path")

        os.fchmod, os.chmod = _fchmod_spy, _path_chmod_forbidden
        try:
            self.mod._write_private(path, b"payload", allocated=True)
        finally:
            os.fchmod, os.chmod = real_fchmod, real_chmod

        self.assertEqual(fchmod_observations, [(0o600, 0)], "fchmod must precede every payload byte")
        self.assertEqual(Path(path).read_bytes(), b"payload")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_allocated_mode_fchmod_failure_writes_nothing(self):
        path = os.path.join(self.d, "reserved.txt")
        Path(path).touch()
        real_fchmod, real_fstat = os.fchmod, os.fstat
        fchmod_observations = []

        def _fchmod_boom(fd, mode):
            fchmod_observations.append((mode, real_fstat(fd).st_size))
            raise PermissionError("forced allocated-mode fchmod failure")

        os.fchmod = _fchmod_boom
        try:
            with self.assertRaises(PermissionError):
                self.mod._write_private(path, b"must-not-land", allocated=True)
        finally:
            os.fchmod = real_fchmod

        self.assertEqual(fchmod_observations, [(0o600, 0)], "fchmod must run before payload persistence")
        self.assertEqual(Path(path).read_bytes(), b"", "fchmod failure must leave the reservation empty")

    def test_main_applies_allocated_mode_only_to_the_reserved_transcript(self):
        path = os.path.join(self.d, "reserved.txt")
        writes = []
        real_write_private = self.mod._write_private

        def _write_spy(write_path, data, allocated=False):
            writes.append((write_path, data, allocated))

        self.mod._write_private = _write_spy
        try:
            status = self.mod.main(path, [sys.executable, "-c", "pass"], allocated=True)
        finally:
            self.mod._write_private = real_write_private

        self.assertEqual(status, 0)
        self.assertEqual(writes[0], (path, b"", True))
        self.assertEqual(writes[1][0], path + ".captureid")
        self.assertFalse(writes[1][2], "the unreserved capture-id sidecar keeps create/truncate mode")

    def test_refuses_to_write_to_a_fifo(self):
        """O_NOFOLLOW alone permits a pre-created FIFO at the predictable capture path — with no reader
        the write blocks forever, with an attacker-held reader it leaks the transcript. O_NONBLOCK + an
        fstat S_ISREG check must refuse it (round 5: codex)."""
        fifo = os.path.join(self.d, "out.fifo")
        os.mkfifo(fifo)
        with self.assertRaises(OSError):
            self.mod._write_private(fifo, b"x")

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "O_NOFOLLOW required")
    def test_refuses_to_write_through_a_symlink(self):
        target = os.path.join(self.d, "secret")
        link = os.path.join(self.d, "link")
        os.symlink(target, link)
        with self.assertRaises(OSError):
            self.mod._write_private(link, b"x")
        self.assertFalse(os.path.exists(target), "must not create the symlink target")

    def test_opener_closes_the_fd_if_fchmod_fails(self):
        """The `opener` holds a raw fd BEFORE open() takes ownership, so if os.fchmod raises there it must
        close that fd (not leak it) and propagate. Force fchmod to fail and assert the error propagates
        and the fd we handed out was closed (round 4: gemini — uncovered error path)."""
        path = os.path.join(self.d, "t.txt")
        real_open, real_fchmod, real_close = os.open, os.fchmod, os.close
        opened, closed = [], []

        def _open_spy(*a, **k):
            fd = real_open(*a, **k)
            opened.append(fd)
            return fd

        def _fchmod_boom(fd, mode):
            raise PermissionError("forced")

        os.open, os.fchmod, os.close = _open_spy, _fchmod_boom, lambda fd: (closed.append(fd), real_close(fd))[1]
        try:
            with self.assertRaises(PermissionError):
                self.mod._write_private(path, b"x")
        finally:
            os.open, os.fchmod, os.close = real_open, real_fchmod, real_close
        self.assertTrue(opened, "opener should have os.open'd an fd")
        self.assertIn(opened[-1], closed, "the fd must be closed when fchmod fails in the opener")

    def test_no_manual_close_once_open_owns_the_fd(self):
        """Double-close guard: the fd is created via open()'s `opener`, so the file object owns it and
        closes it exactly once (C-level, not via os.close) — even when the write fails. Passing a str
        makes fh.write raise TypeError after open() returned, so any os.close observed here would be an
        erroneous manual close on an fd another thread could have since reopened."""
        path = os.path.join(self.d, "wf.txt")
        real_close = os.close
        closed = []

        def _spy(fd):
            closed.append(fd)
            return real_close(fd)

        os.close = _spy
        try:
            with self.assertRaises(TypeError):
                self.mod._write_private(path, "not-bytes")  # type: ignore[arg-type]
        finally:
            os.close = real_close
        self.assertEqual(closed, [], "os.fdopen owns fd; the except path must not os.close it again")


class CaptureArgumentParsingTests(unittest.TestCase):
    """COREDEV-2503 B1: `--timeout=N` (equals form) was unrecognized and fell into the out-path, so a caller
    using `=N` got an UNBOUNDED run. Both forms now parse to the same timeout via parse_pre_args."""

    def setUp(self):
        self.mod = _load()

    def test_equals_form_sets_timeout(self):
        t, out, allocated = self.mod.parse_pre_args(["--timeout=5", "/tmp/o.txt"])
        self.assertEqual(t, 5.0)
        self.assertEqual(out, "/tmp/o.txt")
        self.assertFalse(allocated)

    def test_space_form_still_works(self):
        t, _, allocated = self.mod.parse_pre_args(["--timeout", "5", "/tmp/o.txt"])
        self.assertEqual(t, 5.0)
        self.assertFalse(allocated)

    def test_equals_form_validates_like_space_form(self):
        for bad in ("--timeout=abc", "--timeout=0", "--timeout=-1", "--timeout=inf", "--timeout=nan"):
            with self.assertRaises(SystemExit):
                self.mod.parse_pre_args([bad, "/tmp/o.txt"])

    def test_equals_form_does_not_leak_into_outpath(self):
        # before B1 `--timeout=600` became the out-path (unbounded run + a 'too many arguments' error)
        t, out, allocated = self.mod.parse_pre_args(["--timeout=600", "/real/out.txt"])
        self.assertEqual((t, out, allocated), (600.0, "/real/out.txt", False))

    def test_allocated_flag_is_forwarded_to_main(self):
        observed = []
        real_main = self.mod.main

        def _main_spy(out_path, command, timeout=None, allocated=False):
            observed.append((out_path, command, timeout, allocated))
            return 23

        self.mod.main = _main_spy
        try:
            status = self.mod.cli_main([
                "--timeout=5",
                "--allocated",
                "/reserved/transcript.txt",
                "--",
                "reviewer",
                "--arg",
            ])
        finally:
            self.mod.main = real_main

        self.assertEqual(status, 23)
        self.assertEqual(
            observed,
            [("/reserved/transcript.txt", ["reviewer", "--arg"], 5.0, True)],
        )


if __name__ == "__main__":
    unittest.main()
