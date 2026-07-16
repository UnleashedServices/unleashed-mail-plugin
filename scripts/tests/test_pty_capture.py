"""Tests for scripts/pty-capture.py's _write_private — the session-safe transcript writer.

Covers the write's security discipline (0600 mode, O_NOFOLLOW symlink refusal) and, specifically, the
round-1 double-close fix: once os.fdopen() owns the fd, the except path must NOT close it again (a second
close can clobber a concurrently-reused fd number)."""
import importlib.util
import os
import stat
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

    def test_writes_content_at_0600(self):
        path = os.path.join(self.d, "t.txt")
        self.mod._write_private(path, b"hello")
        self.assertEqual(Path(path).read_bytes(), b"hello")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_tightens_a_preexisting_world_readable_file(self):
        path = os.path.join(self.d, "t.txt")
        with open(path, "wb") as fh:
            fh.write(b"old")
        os.chmod(path, 0o644)
        self.mod._write_private(path, b"new")
        self.assertEqual(Path(path).read_bytes(), b"new")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "O_NOFOLLOW required")
    def test_refuses_to_write_through_a_symlink(self):
        target = os.path.join(self.d, "secret")
        link = os.path.join(self.d, "link")
        os.symlink(target, link)
        with self.assertRaises(OSError):
            self.mod._write_private(link, b"x")
        self.assertFalse(os.path.exists(target), "must not create the symlink target")

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


if __name__ == "__main__":
    unittest.main()
