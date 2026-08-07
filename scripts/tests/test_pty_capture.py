"""Tests for scripts/pty-capture.py's session-safe transcript writer.

Covers the allocated/non-allocated write modes, their descriptor-based security discipline, and the
round-1 double-close fix: once open() owns the fd, the except path must not close it again (a second close
can clobber a concurrently reused fd number)."""
import importlib.util
import errno
import shutil
import os
import stat
import sys
import pathlib
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

    def test_nonallocated_mode_refuses_a_hardlinked_victim_without_touching_it(self):
        """PR #63 recheck, P2 — reproduced: the victim was rewritten.

        The non-allocated path used `O_CREAT|O_TRUNC`, which empties a pre-existing file AT open(),
        before any fstat — so a hard link planted at the predictable capture/`.captureid` path was
        truncated to zero on the way in, and the `nlink != 1` guard that would have caught it was
        skipped entirely on this path (`if allocated and …`). Now the path opens without O_TRUNC and the
        guard is unconditional, so the victim is refused with its bytes intact.
        """
        victim = os.path.join(self.d, "PRECIOUS")
        Path(victim).write_bytes(b"PRECIOUS OUTSIDE DATA\n")
        target = os.path.join(self.d, "capture.txt")
        os.link(victim, target)  # a hard link IS a regular file — O_NOFOLLOW/S_ISREG both accept it

        with self.assertRaises(OSError) as caught:
            self.mod._write_private(target, b"attacker capture bytes\n")  # non-allocated (default)
        self.assertEqual(caught.exception.errno, errno.EMLINK)
        self.assertEqual(Path(victim).read_bytes(), b"PRECIOUS OUTSIDE DATA\n",
                         "the hard-linked victim was modified — the refusal came too late")

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

    def test_allocated_rewrite_shorter_than_the_previous_run_leaves_no_stale_tail(self):
        """A shorter second write must not resurrect the first run's VERDICT (PR #63 review, High).

        `--allocated` omits O_TRUNC to protect the reservation, which also left the file unbounded:
        a failed round that wrote fewer bytes than a previous successful one left that round's tail
        in place, and the wrapper's `grep … | tail -1` reported the OLD approval for the NEW failed
        review. The existing allocated-mode coverage all writes into a 0-byte leaf, so none of it
        could observe this. Assert on the surviving bytes, not on the flags — the fix is ftruncate,
        and a flags-only assertion would pass with the bug still present.
        """
        path = os.path.join(self.d, "reserved.txt")
        Path(path).touch()

        first = b"round 1 transcript, long and complete\nVERDICT: APPROVE\n"
        self.mod._write_private(path, first, allocated=True)
        self.assertEqual(Path(path).read_bytes(), first)

        shorter = b"round 2 died early\n"
        self.mod._write_private(path, shorter, allocated=True)

        got = Path(path).read_bytes()
        self.assertEqual(got, shorter, "the leaf must hold exactly what THIS run wrote")
        self.assertNotIn(b"VERDICT:", got, "the previous run's verdict must not survive the rewrite")

    def test_allocated_rewrite_still_refuses_to_create_an_unreserved_leaf(self):
        """The truncation fix must not weaken the reservation invariant it sits next to.

        ftruncate is used precisely because it cannot create a file; O_TRUNC would have. This is the
        deletion test for that choice: if someone later "simplifies" the fix back to O_TRUNC, the
        allocated write starts creating leaves it never reserved and this fails.
        """
        path = os.path.join(self.d, "never-reserved.txt")
        with self.assertRaises(OSError):
            self.mod._write_private(path, b"must-not-land", allocated=True)
        self.assertFalse(os.path.exists(path), "allocated mode must never create the leaf")

    def test_allocated_mode_never_recreates_the_private_parent_chain(self):
        """The allocator owns the directory chain at 0700; the capture must not rebuild it at umask.

        `main()` created `dirname(out_path)` unconditionally, using the process umask. In allocated mode
        that rebuilt the private state tree at 0755 — and the allocator VALIDATES the mode, so every
        later `--allocate` for that repo hash failed "has mode 0o0755, expected 0o0700" permanently
        (PR #63 review, gap 3). Assert on the filesystem, not on the flags: the parent must still be
        absent afterwards, and the run must fail rather than silently write somewhere new.
        """
        parent = os.path.join(self.d, "state-root", "review-transcripts", "abcdef")
        target = os.path.join(parent, "leaf.txt")
        self.assertFalse(os.path.exists(parent))

        code = self.mod.main(target, ["/bin/echo", "hi"], timeout=20, allocated=True)

        self.assertNotEqual(0, code, "an allocated write into a missing chain must fail")
        self.assertFalse(
            os.path.isdir(parent), "allocated mode must never recreate the allocator's parent chain"
        )

    def test_nonallocated_mode_still_creates_its_parent_chain(self):
        """The deletion test for the guard: it must be conditional, not a blanket removal."""
        parent = os.path.join(self.d, "ordinary", "nested")
        target = os.path.join(parent, "out.txt")

        code = self.mod.main(target, ["/bin/echo", "hi"], timeout=20, allocated=False)

        self.assertEqual(0, code)
        self.assertTrue(os.path.isdir(parent), "non-allocated mode must still create its parents")

    def test_allocated_mode_refuses_before_running_the_command(self):
        """A stale/deleted reservation must fail FAST, not after the review has already run.

        The reservation used to be enforced only by the final write — i.e. after the wrapped command
        finished — so a stale allocated path burned an entire review (up to 28 minutes of `agy`) and
        only then failed on a missing file. The round is lost either way; the cost was the wasted
        wall-clock (PR #63 second-round review).

        Asserts the command's SIDE EFFECT is absent rather than timing the failure: a timing
        assertion would pass on a fast machine even if the command did run.
        """
        marker = os.path.join(self.d, "the-command-ran")
        missing = os.path.join(self.d, "never-reserved.txt")

        self.assertNotEqual(
            0, self.mod.main(missing, ["/usr/bin/touch", marker], timeout=30, allocated=True)
        )

        self.assertFalse(
            os.path.exists(marker), "the wrapped command must NOT run when the leaf is unreserved"
        )
        self.assertFalse(os.path.exists(missing), "and the leaf must still not be created")

    def test_allocated_mode_refuses_a_symlink_at_the_reserved_path_before_running(self):
        """A symlink planted at the reserved path is rejected at preflight, via lstat."""
        marker = os.path.join(self.d, "symlink-command-ran")
        target = os.path.join(self.d, "elsewhere.txt")
        open(target, "w").close()
        link = os.path.join(self.d, "reserved-link.txt")
        os.symlink(target, link)

        self.assertNotEqual(
            0, self.mod.main(link, ["/usr/bin/touch", marker], timeout=30, allocated=True)
        )

        self.assertFalse(os.path.exists(marker), "a symlinked reservation must not run the command")

    def test_allocated_mode_still_runs_for_a_properly_reserved_leaf(self):
        """The deletion test: preflight must be conditional, not refuse every allocated run."""
        leaf = os.path.join(self.d, "properly-reserved.txt")
        os.close(os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        # …and its `.launch` record. The allocator writes both, and the preflight now refuses an
        # allocation without one — a deleted or corrupted record used to let a 20-30 minute review
        # run to completion and exit 0, only for the verdict writer to discard it (PR #63 recheck).
        # A fixture reserving a leaf alone models an allocation the allocator never produces.
        with open(leaf + ".launch", "w", encoding="utf-8") as fh:
            fh.write("a" * 32 + "\n")

        self.assertEqual(0, self.mod.main(leaf, ["/bin/echo", "ok"], timeout=30, allocated=True))
        self.assertIn(b"ok", Path(leaf).read_bytes())

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
        # Actually reserve the leaf. This test stubs `_write_private`, so it previously passed with no
        # reservation at all — nothing checked. `main()` now preflights the reservation before spawning
        # the command, which is the state a real allocated run is always in.
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        with open(path + ".launch", "w", encoding="utf-8") as fh:
            fh.write("a" * 32 + "\n")
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

    def test_missing_out_path_is_refused_rather_than_defaulted(self):
        """The out-path used to default to a fixed `/tmp/pty-out.txt` (deep review, P2).

        That is MAJ-10 in miniature: a run that dies before writing leaves the PREVIOUS run's bytes at
        the shared path for the next reader to trust, and two concurrent captures overwrite each other.
        The caller who forgets a path is exactly the caller who must not silently get a shared file.
        """
        with self.assertRaises(SystemExit) as raised:
            self.mod.parse_pre_args(["--timeout=5"])
        self.assertIn("out-path is required", str(raised.exception))

        source = pathlib.Path(_PTY).read_text(encoding="utf-8")
        self.assertNotIn(
            '"/tmp/pty-out.txt"',
            source,
            "a fixed default out-path is back in the parser",
        )

    def test_restoring_the_default_out_path_is_what_the_guard_prevents(self):
        """Mutation: put the default back and the same call succeeds, handing back the shared path."""
        mutant_source = pathlib.Path(_PTY).read_text(encoding="utf-8").replace(
            "    if not positional:", "    if False:", 1
        )
        self.assertNotIn("    if not positional:", mutant_source)
        mutant_source = mutant_source.replace(
            "    return timeout, positional[0], allocated",
            '    return timeout, (positional[0] if positional else "/tmp/pty-out.txt"), allocated',
            1,
        )
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "pty_capture_mutant.py"
            path.write_text(mutant_source, encoding="utf-8")
            spec = importlib.util.spec_from_file_location("_pty_default_mutant", path)
            mutant = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mutant
            try:
                spec.loader.exec_module(mutant)
                _timeout, out, _allocated = mutant.parse_pre_args(["--timeout=5"])
                self.assertEqual("/tmp/pty-out.txt", out)
            finally:
                sys.modules.pop(spec.name, None)

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


class AllocatedTargetHardening(unittest.TestCase):
    """Four allocated-capture defects the recheck reproduced (PR #63 recheck, P2)."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        spec = importlib.util.spec_from_file_location("ptycap_h", _PTY)
        self.mod = importlib.util.module_from_spec(spec)
        sys.modules["ptycap_h"] = self.mod
        spec.loader.exec_module(self.mod)

    def _reserve(self, name="leaf.txt", launch=True):
        leaf = os.path.join(self.d, name)
        os.close(os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        if launch:
            with open(leaf + ".launch", "w", encoding="utf-8") as fh:
                fh.write("a" * 32 + "\n")
        return leaf

    def test_a_hard_linked_target_is_refused_before_it_is_rewritten(self):
        """A hard link IS a regular file, so `O_NOFOLLOW` and `S_ISREG` both accept one.

        Reproduced: linking an 18-byte file at the reserved path made `_write_private` rewrite that
        file's contents and set it 0600 — corrupting an arbitrary same-user file. Asserted on the
        victim's bytes, not on the exception: an exception raised after the write would be no defence.
        """
        victim = os.path.join(self.d, "victim.txt")
        with open(victim, "w", encoding="utf-8") as fh:
            fh.write("PRECIOUS DATA\n")
        leaf = os.path.join(self.d, "linked.txt")
        os.link(victim, leaf)

        with self.assertRaises(Exception):
            self.mod._write_private(leaf, b"REVIEW OUTPUT\n", allocated=True)
        with open(victim, encoding="utf-8") as fh:
            self.assertEqual("PRECIOUS DATA\n", fh.read())

    def test_an_unlinked_reservation_is_still_accepted(self):
        """The positive control: the guard must reject SHARING, not every allocated write."""
        leaf = self._reserve()
        self.mod._write_private(leaf, b"REVIEW OUTPUT\n", allocated=True)
        with open(leaf, encoding="utf-8") as fh:
            self.assertEqual("REVIEW OUTPUT\n", fh.read())

    def test_a_missing_launch_record_refuses_BEFORE_running_the_command(self):
        """Asserted on the child never running, which is the whole point of moving the check earlier.

        `review-verdict.py` already rejected such a transcript — but only at WRITE time, so a 20-30
        minute review completed and exited 0 before being discarded. A refusal after the cost is paid
        is a report, not a preflight.
        """
        leaf = self._reserve("no-record.txt", launch=False)
        marker = os.path.join(self.d, "child-ran")
        code = self.mod.main(leaf, ["/bin/sh", "-c", f"touch {marker}"], timeout=30, allocated=True)
        self.assertEqual(1, code)
        self.assertFalse(os.path.exists(marker), "the reviewer ran despite an unusable allocation")

    def test_an_empty_launch_record_is_also_refused(self):
        """Present-but-useless is the same outcome as absent, and was equally invisible until now."""
        leaf = self._reserve("empty-record.txt", launch=False)
        open(leaf + ".launch", "w").close()
        marker = os.path.join(self.d, "child-ran-2")
        code = self.mod.main(leaf, ["/bin/sh", "-c", f"touch {marker}"], timeout=30, allocated=True)
        self.assertEqual(1, code)
        self.assertFalse(os.path.exists(marker))

    def test_a_case_mangled_protected_root_is_rejected(self):
        """`commonpath` is case-SENSITIVE; APFS is not, by default.

        `$HOME/.CLAUDE/x` opens the same directory as `$HOME/.claude/x` while comparing unequal, so a
        case-mangled `XDG_STATE_HOME` was accepted as outside the protected root. `realpath` does not
        help: it resolves symlinks but preserves the caller's spelling.

        MUTATION NOTE — the containment has TWO independent mechanisms, the inode walk and the
        casefolded lexical fallback, and either alone rejects this. So disabling one changes nothing
        and a single-mutant run reports no failures; only disabling BOTH reopens the hole, which this
        test then catches. Recorded because "the mutant passed" would otherwise read as "the guard is
        inert" — it means the redundancy is real, not that the check is decorative.
        """
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        os.makedirs(os.path.join(home, ".claude", "review-state"))
        for spelling in (".claude", ".CLAUDE", ".Claude"):
            with self.subTest(spelling=spelling):
                candidate = os.path.join(home, spelling, "review-state")
                canonical, reason = self.mod._validate_base_candidate(candidate, home)
                self.assertIsNone(canonical, f"{spelling} was accepted: {reason}")

    def test_a_base_outside_the_protected_root_is_still_accepted(self):
        """Control — the containment must not have become "reject everything"."""
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        elsewhere = os.path.join(home, "elsewhere")
        os.makedirs(elsewhere)
        canonical, reason = self.mod._validate_base_candidate(elsewhere, home)
        self.assertIsNotNone(canonical, reason)
    def test_a_base_owned_by_another_user_is_rejected(self):
        """`os.access` answers "may I write here", never "is this mine".

        An attacker-created mode-0777 directory under `/tmp` passed, and the allocator then placed its
        0700 subtree beneath a parent whose owner can rename or replace that subtree between allocation
        and capture (PR #63 recheck, P2). The uid is stubbed because creating a foreign-owned directory
        needs root — the check under test is the comparison, not the kernel's bookkeeping.
        """
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        foreign = os.path.join(home, "attacker")
        os.makedirs(foreign, mode=0o777)

        real_stat = os.stat

        class _Foreign:
            def __init__(self, base): self._base = base
            def __getattr__(self, name): return getattr(self._base, name)
            @property
            def st_uid(self): return 4242      # neither this user nor root

        def stub(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            same = os.path.realpath(str(path)) == os.path.realpath(foreign)
            return _Foreign(info) if same else info

        self.mod.os.stat = stub
        self.addCleanup(setattr, self.mod.os, "stat", real_stat)
        canonical, reason = self.mod._validate_base_candidate(foreign, home)
        self.assertIsNone(canonical, "a foreign-owned base was accepted")
        self.assertIn("owned by uid", reason)

    def test_a_root_owned_ancestor_is_still_accepted(self):
        """Control, and the reason the check is not simply "must be mine".

        `/tmp` and `/` are root-owned and are the normal case; rejecting them would refuse every
        default configuration, which is a false positive nobody would tolerate for long.
        """
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        canonical, reason = self.mod._validate_base_candidate(
            os.path.join(tempfile.gettempdir(), "um-ownership-probe"), home
        )
        self.assertIsNotNone(canonical, reason)


if __name__ == "__main__":
    unittest.main()
