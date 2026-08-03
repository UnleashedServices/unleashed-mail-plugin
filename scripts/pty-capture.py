#!/usr/bin/env python3
"""Run any command inside a PTY so TTY-only output renders, then ANSI-strip and capture it.

Why this exists
---------------
Some CLIs (Antigravity `agy`, OpenAI `codex exec`) only emit their output to a
real terminal. When stdout is piped, redirected (`> file`, `| tee`), or the
process is backgrounded — i.e. Claude Code's Bash tool, CI scripts, any
non-TTY context — they produce **0 bytes** even though the command itself
completed successfully. The fix is to give the child a pseudo-terminal (PTY)
so it believes it is attached to a terminal, then capture and ANSI-strip what
it writes. Routing every automated review through this wrapper means output is
ALWAYS written to `<out-path>` — there is no `-o`/`--output` flag to forget,
so the recurring "0-byte / nothing captured" failure cannot happen.

Usage
-----
    python3 pty-capture.py [--timeout SECONDS] [--allocated] <out-path> -- <command> [args...]

`--timeout` bounds the wall-clock run: on expiry the child is terminated (bounded ladder),
the partial transcript is still written, and the wrapper exits 124 (the timeout(1) convention).

Examples
--------
    # Codex review — capture is guaranteed, no -o flag needed. Always force xhigh effort
    # (the config default is fragile — see skills/codex-review/SKILL.md).
    python3 pty-capture.py /tmp/codex-out.txt -- \
        codex exec -c model_reasoning_effort=xhigh -s read-only "$(cat .codex-prompt.md)"

    # Antigravity (agy) review.
    python3 pty-capture.py /tmp/agy-out.txt -- \
        agy --add-dir "$(pwd)" -p "Read and follow .agy-prompt.md"

Exit codes: the wrapped command's exit code propagates (0 = success; non-zero
= failure). Captured output is written to <out-path> (default /tmp/pty-out.txt).
"""
# REQUIRED for macOS's stock /usr/bin/python3 (3.9.6): `main()`'s `timeout: float | None` is a PEP-604
# union evaluated AT IMPORT in a module-level def, so 3.9 raises `TypeError: unsupported operand type(s)
# for |: 'type' and 'NoneType'` before anything runs — which would take BOTH mandatory review gates down
# on a stock Mac (this plugin's likeliest host). Matches the 7 other shipped .py files. (COREDEV-2494)
from __future__ import annotations

import errno
import fcntl
import os
import pty
import re
import select
import signal
import stat
import struct
import sys
import termios
import time

ANSI_RE = re.compile(rb'\x1b\[[0-9;?]*[a-zA-Z]')
SIGTERM_GRACE_SEC = 5.0   # bounded grace period before SIGKILL
POLL_INTERVAL_SEC = 0.1
SIGKILL_REAP_SEC = 2.0    # bounded wait for the SIGKILL'd child to be reaped


def _write_private(path: str, data: bytes, allocated: bool = False) -> None:
    """Write bytes to `path` at mode 0600, refusing to follow a pre-existing symlink (#44 review §4).

    O_NOFOLLOW: if `path` is already a symlink, open() raises (ELOOP) instead of writing THROUGH it to
    an attacker-chosen target. O_NONBLOCK plus fd-based fstat/S_ISREG rejects a FIFO or device at the
    predictable path; without that check, a FIFO blocks with no reader or leaks to an attacker-held reader
    (round 5: codex). Non-allocated writes use O_CREAT|O_TRUNC; allocated writes use neither and require the
    reserved leaf. fd-based fchmod tightens mode before any payload is written.

    The open() opener gives its file object fd ownership, avoiding manual bookkeeping and double-close
    (round 2: gemini). Only the opener still holds a raw fd; if a check fails, it closes before raising
    because open() never received it.
    """
    create_flags = 0 if allocated else os.O_CREAT | os.O_TRUNC
    flags = os.O_WRONLY | create_flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)

    def _opener(p, _flags):
        fd = os.open(p, flags, 0o600)   # our flags (incl. O_NOFOLLOW/O_NONBLOCK), not open()'s default
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise NonRegularCaptureTargetError(errno.ENOTSUP, "refusing a non-regular capture target", p)
            os.fchmod(fd, 0o600)        # tighten an already-existing 0644 file (O_CREAT mode is create-only)
        except BaseException:
            os.close(fd)                # open() hasn't taken ownership yet, so we must close it here
            raise
        return fd

    with open(path, "wb", opener=_opener) as fh:
        fh.write(data)


def _signal_child(pid: int, sig: int) -> None:
    """Deliver `sig` to the wrapped child, and best-effort to its process group.

    `os.kill(pid, …)` is the reliable path — `pid` is our own child and a
    session/group leader via `pty.fork()`. The process-group signal additionally
    reaches helpers the child spawned, but macOS can spuriously raise `ESRCH`
    from `killpg` even for a live group, so it is best-effort only and must never
    prevent the direct kill of the leader.
    """
    try:
        os.killpg(pid, sig)   # reach helpers (works on Linux; advisory on macOS)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        os.kill(pid, sig)     # reliable: terminate the leader itself
    except (ProcessLookupError, PermissionError):
        pass


def main(out_path: str, cmd: list[str], timeout: float | None = None, allocated: bool = False) -> int:
    if not cmd:
        raise SystemExit("no command given after `--`")
    # If the wrapper itself is asked to terminate — CI timeout, process manager,
    # or terminal hangup / SSH disconnect — turn the signal into a SystemExit so
    # the `finally` block still runs: it reaps the child and persists whatever we
    # captured instead of orphaning agy/codex.
    _term_signals = [s for s in (signal.SIGTERM, getattr(signal, "SIGHUP", None))
                     if s is not None]

    def _on_term_signal(signum, frame):
        # Disarm both handlers immediately so a second signal arriving while we
        # unwind into cleanup can't re-enter this handler and abort the reap or
        # the output write — it takes the default action (terminate) instead.
        for s in _term_signals:
            try:
                signal.signal(s, signal.SIG_DFL)
            except (ValueError, OSError):
                pass
        sys.exit(128 + signum)

    for _sig in _term_signals:
        signal.signal(_sig, _on_term_signal)
    # pty.fork() forks with the child attached to a NEW controlling terminal: it
    # performs setsid(), the TIOCSCTTY ioctl, and wires the slave to
    # stdin/stdout/stderr. That controlling TTY is what lets terminal-oriented
    # CLIs that open /dev/tty (agy's text-drip, codex) actually render — a plain
    # openpty()+dup2() leaves the child with no controlling terminal (ENXIO).
    pid, master_fd = pty.fork()
    if pid == 0:
        # Child: become the wrapped command. os.execvp resolves it on $PATH.
        try:
            os.execvp(cmd[0], cmd)
        except OSError as e:
            # stderr is wired to the PTY slave, so this diagnostic lands in the
            # captured output. Raw os.write avoids post-fork stdio buffering.
            os.write(2, f"pty-capture: failed to execute '{cmd[0]}': {e}\n".encode())
        # If exec fails the child must not return to caller's code:
        os._exit(127)
    # Parent.
    # A PTY opened with no terminal to inherit (Claude/CI/non-TTY) reports a 0x0
    # window size; width-aware CLIs (agy's text-drip, codex) then wrap to nothing
    # or emit empty/garbled output. Give it a sane size — inherit COLUMNS/LINES
    # if present, else 80x24 — so the capture path stays reliable.
    try:
        cols = int(os.environ.get("COLUMNS") or 80)
        rows = int(os.environ.get("LINES") or 24)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", rows, cols, 0, 0))
    except (OSError, ValueError, AttributeError):
        pass
    raw = bytearray()
    status = None  # raw wait-status; only assigned when we actually reap the child
    capture_error = None  # set if persisting the transcript fails (surfaced below)
    timed_out = False  # set if the wall-clock --timeout elapses before the child exits
    start = time.monotonic()
    try:
        while True:
            # Wall-clock timeout: agy's print-timeout (5 min) exceeds Claude's default Bash
            # timeout, and a wedged CLI would otherwise run until an external SIGTERM. On
            # timeout, break so `finally` reaps the child (bounded ladder) and persists the
            # partial transcript; the exit code becomes 124 (the timeout(1) convention).
            if timeout is not None and time.monotonic() - start >= timeout:
                timed_out = True
                try:
                    sys.stderr.write(f"pty-capture: timed out after {timeout:g}s; terminating child\n")
                    sys.stderr.flush()
                except OSError:
                    pass
                break
            try:
                r, _, _ = select.select([master_fd], [], [], 0.5)
            except InterruptedError:
                # Signal during select (e.g., SIGWINCH, SIGCHLD when the PTY
                # child exits) — the call was interrupted, not failed.
                # Retry without tearing down the (healthy) main child.
                continue
            except OSError:
                # Real PTY error — break and let finally clean up.
                break
            if master_fd in r:
                try:
                    chunk = os.read(master_fd, 65536)
                    if not chunk:
                        break  # EOF on PTY; child likely exited — finally reaps
                    raw.extend(chunk)
                except InterruptedError:
                    continue
                except OSError:
                    break
            try:
                done_pid, st = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                done_pid, st = pid, 0
            if done_pid == pid:
                status = st
                # Drain remaining buffered output (one short sweep, bounded).
                deadline = time.monotonic() + 0.5
                while time.monotonic() < deadline:
                    try:
                        r, _, _ = select.select([master_fd], [], [], 0.05)
                    except (InterruptedError, OSError):
                        break
                    if master_fd not in r:
                        break
                    try:
                        chunk = os.read(master_fd, 65536)
                        if not chunk:
                            break
                        raw.extend(chunk)
                    except (InterruptedError, OSError):
                        break
                break
    finally:
        # Restore default disposition first so a SIGTERM/SIGHUP arriving DURING
        # cleanup can't re-enter the handler and abort reaping or the output
        # write midway. The bounded ladder below still cannot hang.
        for _sig in (signal.SIGTERM, getattr(signal, "SIGHUP", None)):
            if _sig is not None:
                try:
                    signal.signal(_sig, signal.SIG_DFL)
                except (ValueError, OSError):
                    pass
        # Ensure the child is reaped on all paths with a bounded grace period
        # so the wrapper cannot hang forever if the child ignores SIGTERM.
        if status is None:
            try:
                done_pid, st = os.waitpid(pid, os.WNOHANG)
            except (ChildProcessError, ProcessLookupError):
                done_pid, st = pid, 0
            if done_pid == pid:
                status = st
            else:
                # Child still alive — ask it (and any helpers in its group) to
                # terminate. Direct kill of the leader is reliable; the group
                # signal is best-effort for descendants (see _signal_child).
                _signal_child(pid, signal.SIGTERM)
                grace_deadline = time.monotonic() + SIGTERM_GRACE_SEC
                while time.monotonic() < grace_deadline:
                    try:
                        done_pid, st = os.waitpid(pid, os.WNOHANG)
                    except (ChildProcessError, ProcessLookupError):
                        done_pid, st = pid, 0
                        break
                    if done_pid == pid:
                        break
                    time.sleep(POLL_INTERVAL_SEC)
                if done_pid == pid:
                    status = st
                else:
                    # Grace period expired — force-kill (uncatchable) and reap,
                    # BOUNDED: a failed/denied signal must never block the wrapper
                    # forever on a child that won't die. Closing the PTY below
                    # hangs up the session as a final backstop.
                    _signal_child(pid, signal.SIGKILL)
                    kill_deadline = time.monotonic() + SIGKILL_REAP_SEC
                    while time.monotonic() < kill_deadline:
                        try:
                            done_pid, st = os.waitpid(pid, os.WNOHANG)
                        except (ChildProcessError, ProcessLookupError):
                            done_pid, st = pid, 0
                        if done_pid == pid:
                            status = st
                            break
                        time.sleep(POLL_INTERVAL_SEC)
                    if status is None:
                        status = 0  # gave up reaping — do not hang
        # Drain anything still buffered in the PTY before closing — bytes left
        # unread when `select` was interrupted by a cancellation, plus any final
        # diagnostics the child wrote while handling the signal. The normal-exit
        # path drains in the read loop; this covers the SIGTERM/SIGHUP path so a
        # cancellation doesn't lose the tail of the transcript. Bounded so
        # cleanup can't hang.
        drain_deadline = time.monotonic() + 0.5
        while time.monotonic() < drain_deadline:
            try:
                r, _, _ = select.select([master_fd], [], [], 0.05)
            except (InterruptedError, OSError):
                break
            if master_fd not in r:
                break
            try:
                chunk = os.read(master_fd, 65536)
                if not chunk:
                    break
                raw.extend(chunk)
            except (InterruptedError, OSError):
                break
        try:
            os.close(master_fd)
        except OSError:
            pass
        # Always persist what we captured — even when unwinding from a
        # SIGTERM-driven SystemExit — so the output file exists and holds the
        # partial transcript. A write failure must not mask the original
        # exit/exception, but it must not pass silently either: capturing IS the
        # job, so record it and surface a non-zero exit below.
        try:
            out_dir = os.path.dirname(out_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            # PTYs translate \n -> \r\n (ONLCR); normalize to Unix newlines.
            cleaned = ANSI_RE.sub(b'', bytes(raw)).replace(b'\r\n', b'\n')
            # SESSION-SAFE write (#44 review §4). Review transcripts can quote message bodies / tokens,
            # and the recipes use predictable /tmp paths, so a pre-created symlink or a 0644 file is a
            # local hazard: another user could pre-seed `/tmp/agy-out.txt` as a symlink to redirect the
            # capture, or read a world-readable transcript. Create with O_NOFOLLOW (a pre-existing symlink
            # at out_path makes open() fail rather than being followed) and force mode 0600 (fchmod, since
            # O_CREAT only sets the mode when the file did not already exist).
            _write_private(out_path, cleaned, allocated=allocated)
            # PROVENANCE: leave a per-run capture ID beside the transcript. review-verdict.py auto-reads
            # `<out>.captureid` and uses distinct capture IDs as authoritative, content-independent proof
            # that two reviewers were two separate wrapper runs (full review, #41). Best-effort — a
            # failure here must not fail the capture, so it never touches `capture_error`. Same 0600 /
            # O_NOFOLLOW discipline as the transcript.
            try:
                _write_private(out_path + '.captureid', (os.urandom(16).hex() + '\n').encode())
            except OSError:
                # A pre-existing SYMLINK at the sidecar makes _write_private (O_NOFOLLOW) fail. Leaving it
                # would let a pre-seeded `.captureid` (attacker-chosen value) survive and be trusted by
                # review-verdict as authoritative provenance — two copied transcripts could then look like
                # distinct wrapper runs. Remove it (os.unlink never follows the link) so no stale/foreign
                # value is read; a capture with NO sidecar is safe — review-verdict treats a missing
                # captureId as "no proof", not as authoritative (round 3: codex).
                try:
                    os.unlink(out_path + '.captureid')
                except OSError:
                    pass
        except OSError as e:
            capture_error = e
            try:
                sys.stderr.write(
                    f"pty-capture: failed to write capture to '{out_path}': {e}\n"
                )
                sys.stderr.flush()
            except OSError:
                pass
    # status is always assigned (0 if reap raced). Normalize signal deaths
    # (negative waitstatus exit codes) to the Unix 128+signum convention.
    exit_status = os.waitstatus_to_exitcode(status) if status is not None else 1
    if exit_status < 0:
        exit_status = 128 - exit_status
    # Capturing is the contract: if persisting the transcript failed, never
    # report success — that would silently reintroduce the missing-output bug.
    if capture_error is not None and exit_status == 0:
        exit_status = 1
    if timed_out:
        exit_status = 124  # conventional timeout exit code; partial transcript already written
    return exit_status


class NonRegularCaptureTargetError(OSError):
    """The opened capture target failed the fd-based regular-file check."""


def _parse_timeout_value(val: str) -> float:
    try:
        t = float(val)
    except ValueError:
        raise SystemExit(f"error: --timeout: invalid number '{val}'")
    if not (0 < t < float("inf")):
        # rejects <=0 AND non-finite (nan/inf): `nan <= 0` is False, and with nan the deadline check
        # `elapsed >= timeout` is always False -> the timeout silently no-ops.
        raise SystemExit("error: --timeout must be a positive, finite number of seconds")
    return t


def parse_pre_args(pre: list[str]) -> "tuple[float | None, str, bool]":
    """Parse the tokens BEFORE `--`: an optional timeout in either `--timeout SECONDS` (space) or
    `--timeout=SECONDS` (equals) form, an optional `--allocated`, and at most one out-path. Returns
    (timeout, out_path, allocated).

    B1 (COREDEV-2503): the equals form was previously unrecognized and fell into `positional` as the
    out-path — so a caller passing `--timeout=600` got an UNBOUNDED run (and its real out-path became a
    'too many arguments' error, or was silently replaced). Both forms now share `_parse_timeout_value`.
    """
    timeout = None
    allocated = False
    positional: list[str] = []
    i = 0
    while i < len(pre):
        if pre[i] == "--timeout":
            if i + 1 >= len(pre):
                raise SystemExit("usage: pty-capture.py [--timeout SECONDS] [--allocated] [out-path] -- <cmd>\n"
                                 "error: --timeout requires a value")
            timeout = _parse_timeout_value(pre[i + 1])
            i += 2
        elif pre[i].startswith("--timeout="):
            timeout = _parse_timeout_value(pre[i][len("--timeout="):])
            i += 1
        elif pre[i] == "--allocated":
            allocated = True
            i += 1
        else:
            positional.append(pre[i])
            i += 1
    if len(positional) > 1:
        raise SystemExit(
            "usage: pty-capture.py [--timeout SECONDS] [--allocated] [out-path] -- <command> [args...]\n"
            f"error: too many arguments before '--': {positional}"
        )
    return timeout, (positional[0] if positional else "/tmp/pty-out.txt"), allocated


ALLOCATION_MARKER = "UNLEASHED_TRANSCRIPT="
ALLOCATION_ATTEMPTS = 8
RUN_ID_BYTES = 16
DERIVED_SIBLING_SUFFIXES = (".launch", ".captureid")
_COMPONENT_RE = re.compile(r"[A-Za-z0-9._-]+")
_ALLOCATE_OPTIONS = ("--repo-hash", "--ticket", "--round", "--reviewer")


class AllocationError(RuntimeError):
    """A fail-closed transcript allocation error suitable for a stderr diagnostic."""


def is_valid_transcript_component(value: str) -> bool:
    """Return whether a caller-supplied path component has the S-ALLOC grammar."""
    return value not in ("", ".", "..") and _COMPONENT_RE.fullmatch(value) is not None


def _path_is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath((path, root)) == root
    except ValueError:
        return False


def _validate_base_candidate(candidate: str, home: str) -> "tuple[str | None, str | None]":
    """Return (canonical candidate, None), or (None, rejection reason)."""
    if not candidate:
        return None, "value is empty"
    if "\n" in candidate or "\r" in candidate:
        return None, "value contains a line terminator"
    if not os.path.isabs(candidate):
        return None, "value is not an absolute path"
    if not home or not os.path.isabs(home):
        return None, "HOME is unavailable or not absolute, so protected roots cannot be validated"

    canonical = os.path.realpath(candidate)
    if "\n" in canonical or "\r" in canonical:
        return None, "canonical path contains a line terminator"
    protected_root = os.path.realpath(os.path.join(home, ".claude"))
    worktree_exception = os.path.realpath(os.path.join(home, ".claude", "worktrees"))
    if _path_is_within(canonical, protected_root) and not _path_is_within(canonical, worktree_exception):
        return None, "canonical path is inside the protected .claude root"

    probe = canonical
    while not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    if not os.path.isdir(probe):
        return None, f"nearest existing path {probe!r} is not a directory"
    if not os.access(probe, os.W_OK | os.X_OK):
        return None, f"nearest existing directory {probe!r} is not writable and searchable"
    if os.path.exists(canonical) and not os.path.isdir(canonical):
        return None, "value is not a directory"
    return canonical, None


def _select_allocation_base(environ: "dict[str, str]", diagnostic_stream) -> str:
    home = environ.get("HOME", "")
    xdg = environ.get("XDG_STATE_HOME")
    xdg_reason = None
    if xdg:
        canonical, xdg_reason = _validate_base_candidate(xdg, home)
        if canonical is not None:
            return canonical

    fallback = os.path.join(home, ".local", "state") if home else ""
    canonical, fallback_reason = _validate_base_candidate(fallback, home)
    if canonical is None:
        parts = []
        if xdg:
            parts.append(f"XDG_STATE_HOME={xdg!r} rejected: {xdg_reason}")
        parts.append(f"fallback={fallback!r} rejected: {fallback_reason}")
        raise AllocationError("no valid transcript state base: " + "; ".join(parts))

    if xdg and xdg_reason is not None:
        diagnostic_stream.write(
            f"pty-capture: XDG_STATE_HOME={xdg!r} rejected: {xdg_reason}; "
            f"falling back to {fallback!r}\n"
        )
        diagnostic_stream.flush()
    return canonical


def _mkdir_private_chain(path: str) -> None:
    """Create every absent component at its achieved, publication-time mode 0700."""
    missing = []
    cursor = path
    while not os.path.exists(cursor):
        missing.append(cursor)
        parent = os.path.dirname(cursor)
        if parent == cursor:
            raise AllocationError(f"cannot find an existing ancestor for {path!r}")
        cursor = parent
    if not os.path.isdir(cursor):
        raise AllocationError(f"existing ancestor {cursor!r} is not a directory")

    for directory in reversed(missing):
        try:
            os.mkdir(directory, 0o700)
        except FileExistsError:
            if not os.path.isdir(directory):
                raise AllocationError(f"concurrent path {directory!r} is not a directory")


def _validate_existing_private_directory(path: str, metadata=None) -> None:
    """Require an existing allocator-owned shared directory to be ours and exactly 0700."""
    info = metadata if metadata is not None else os.stat(path)
    if not stat.S_ISDIR(info.st_mode):
        raise AllocationError(f"nested transcript parent {path!r} is not a directory")
    mode = stat.S_IMODE(info.st_mode)
    if mode != 0o700:
        raise AllocationError(f"nested transcript parent {path!r} has mode {mode:#06o}, expected 0o0700")
    if info.st_uid != os.geteuid():
        raise AllocationError(
            f"nested transcript parent {path!r} has owner {info.st_uid}, expected {os.geteuid()}"
        )


def _ensure_private_directory(path: str) -> None:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    _validate_existing_private_directory(path)


def _ensure_allocation_parent(base: str, repo_hash: str) -> str:
    _mkdir_private_chain(base)
    parent = base
    for component in ("unleashed-mail", "review-transcripts", repo_hash):
        parent = os.path.join(parent, component)
        _ensure_private_directory(parent)
    return parent


def _generate_run_id() -> str:
    """Encode one direct 128-bit CSPRNG draw; do not transform it beyond lowercase hex."""
    return os.urandom(RUN_ID_BYTES).hex()


def _allocation_basename(ticket: str, round_value: str, reviewer: str, run_id: str) -> str:
    return f"{ticket}r{round_value}-{reviewer}-{run_id}.txt"


def _basename_limit(parent: str) -> int:
    name_max = os.pathconf(parent, "PC_NAME_MAX")
    return name_max - max(len(suffix) for suffix in DERIVED_SIBLING_SUFFIXES)


def _unlink_reservation(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError(errno.EIO, "short write while creating launch record")
        view = view[written:]


def _create_launch_record(path: str, run_id: str) -> bool:
    """Create and owner-reopen a launch record; return False on an exclusive-name collision."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        return False

    try:
        try:
            os.fchmod(fd, 0o600)
            _write_all(fd, (run_id + "\n").encode("ascii"))
        finally:
            os.close(fd)
    except BaseException:
        _unlink_reservation(path)
        raise

    try:
        verify_fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        os.close(verify_fd)
    except BaseException:
        _unlink_reservation(path)
        raise
    return True


def _validate_basename_length(parent: str, ticket: str, round_value: str, reviewer: str) -> None:
    limit = _basename_limit(parent)
    expected_name = _allocation_basename(
        ticket,
        round_value,
        reviewer,
        "0" * (RUN_ID_BYTES * 2),
    )
    if len(expected_name) > limit:
        raise AllocationError(
            f"assembled transcript basename length {len(expected_name)} exceeds limit {limit} "
            f"for parent {parent!r}"
        )


def _reserve_transcript(parent: str, ticket: str, round_value: str, reviewer: str) -> str:
    leaf_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    for _attempt in range(ALLOCATION_ATTEMPTS):
        run_id = _generate_run_id()
        path = os.path.join(parent, _allocation_basename(ticket, round_value, reviewer, run_id))
        try:
            leaf_fd = os.open(path, leaf_flags, 0o600)
        except FileExistsError:
            continue

        try:
            try:
                os.fchmod(leaf_fd, 0o600)
            finally:
                os.close(leaf_fd)
        except BaseException:
            _unlink_reservation(path)
            raise

        try:
            launch_created = _create_launch_record(path + ".launch", run_id)
        except BaseException:
            _unlink_reservation(path)
            raise
        if not launch_created:
            _unlink_reservation(path)
            continue
        return path

    raise AllocationError(
        f"exhausted {ALLOCATION_ATTEMPTS} transcript allocation attempts in parent {parent!r}"
    )


def allocate_transcript(
    repo_hash: str,
    ticket: str,
    round_value: str,
    reviewer: str,
    environ: "dict[str, str] | None" = None,
    diagnostic_stream=None,
) -> str:
    """Atomically reserve one private transcript leaf and its launch record."""
    values = {
        "repo-hash": repo_hash,
        "ticket": ticket,
        "round": round_value,
        "reviewer": reviewer,
    }
    for label, value in values.items():
        if not is_valid_transcript_component(value):
            raise AllocationError(f"invalid {label} component: {value!r}")

    env = dict(os.environ if environ is None else environ)
    diagnostics = sys.stderr if diagnostic_stream is None else diagnostic_stream
    entry_umask = os.umask(0)
    try:
        try:
            base = _select_allocation_base(env, diagnostics)
            parent = _ensure_allocation_parent(base, repo_hash)
            _validate_basename_length(parent, ticket, round_value, reviewer)
            return _reserve_transcript(parent, ticket, round_value, reviewer)
        except AllocationError:
            raise
        except OSError as exc:
            raise AllocationError(f"transcript allocation failed: {exc}") from exc
    finally:
        os.umask(entry_umask)


def _parse_allocate_args(args: list[str]) -> "tuple[str, str, str, str]":
    values = {}
    index = 0
    while index < len(args):
        option = args[index]
        if option not in _ALLOCATE_OPTIONS:
            raise AllocationError(f"unknown allocation argument: {option!r}")
        if option in values:
            raise AllocationError(f"duplicate allocation argument: {option}")
        if index + 1 >= len(args):
            raise AllocationError(f"allocation argument {option} requires a value")
        values[option] = args[index + 1]
        index += 2
    missing = [option for option in _ALLOCATE_OPTIONS if option not in values]
    if missing:
        raise AllocationError("missing allocation arguments: " + ", ".join(missing))
    return tuple(values[option] for option in _ALLOCATE_OPTIONS)


def cli_main(argv: "list[str] | None" = None, environ: "dict[str, str] | None" = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--allocate":
        try:
            repo_hash, ticket, round_value, reviewer = _parse_allocate_args(args[1:])
            path = allocate_transcript(repo_hash, ticket, round_value, reviewer, environ=environ)
        except AllocationError as exc:
            sys.stderr.write(f"pty-capture: {exc}\n")
            sys.stderr.flush()
            return 1
        sys.stdout.write(ALLOCATION_MARKER + path + "\n")
        sys.stdout.flush()
        return 0

    if "--" not in args:
        raise SystemExit("usage: pty-capture.py [--timeout SECONDS] [--allocated] <out-path> -- <command> [args...]")
    separator = args.index("--")
    timeout, out_path, allocated = parse_pre_args(args[:separator])
    return main(out_path, args[separator + 1:], timeout, allocated=allocated)


if __name__ == "__main__":
    sys.exit(cli_main())
