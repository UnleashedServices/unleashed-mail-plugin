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
    python3 pty-capture.py [--timeout SECONDS] <out-path> -- <command> [args...]

`--timeout` bounds the wall-clock run: on expiry the child is terminated (bounded ladder),
the partial transcript is still written, and the wrapper exits 124 (the timeout(1) convention).

Examples
--------
    # Codex review — capture is guaranteed, no -o flag needed.
    python3 pty-capture.py /tmp/codex-out.txt -- \
        codex exec -s read-only "$(cat .codex-prompt.md)"

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

import fcntl
import os
import pty
import re
import select
import signal
import struct
import sys
import termios
import time

ANSI_RE = re.compile(rb'\x1b\[[0-9;?]*[a-zA-Z]')
SIGTERM_GRACE_SEC = 5.0   # bounded grace period before SIGKILL
POLL_INTERVAL_SEC = 0.1
SIGKILL_REAP_SEC = 2.0    # bounded wait for the SIGKILL'd child to be reaped


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


def main(out_path: str, cmd: list[str], timeout: float | None = None) -> int:
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
            with open(out_path, 'wb') as f:
                f.write(cleaned)
            # PROVENANCE: leave a per-run capture ID beside the transcript. review-verdict.py auto-reads
            # `<out>.captureid` and uses distinct capture IDs as authoritative, content-independent proof
            # that two reviewers were two separate wrapper runs — so two byte-identical transcripts from
            # distinct runs are no longer falsely rejected (full review, #41). Best-effort: a failure
            # here must not fail the capture, so it never touches `capture_error`. Unique per run without
            # `uuid`: os.urandom is available on macOS stock 3.9.6 and needs no import beyond `os`.
            try:
                with open(out_path + '.captureid', 'w', encoding='utf-8') as cf:
                    cf.write(os.urandom(16).hex() + '\n')
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


if __name__ == "__main__":
    # argv shape: pty-capture.py <out-path> -- <command> [args...]
    argv = sys.argv[1:]
    if "--" not in argv:
        raise SystemExit(
            "usage: pty-capture.py <out-path> -- <command> [args...]"
        )
    sep = argv.index("--")
    pre = argv[:sep]          # tokens before `--` (optional out-path + --timeout N)
    command = argv[sep + 1:]  # the command to run in the PTY
    # Parse an optional `--timeout SECONDS` and at most one out-path token. Rejecting
    # extras avoids silently dropping a misplaced flag — or worse, treating it as the out-path.
    timeout = None
    positional = []
    i = 0
    while i < len(pre):
        if pre[i] == "--timeout":
            if i + 1 >= len(pre):
                raise SystemExit("usage: pty-capture.py [--timeout SECONDS] [out-path] -- <cmd>\n"
                                 "error: --timeout requires a value")
            try:
                timeout = float(pre[i + 1])
            except ValueError:
                raise SystemExit(f"error: --timeout: invalid number '{pre[i + 1]}'")
            if not (0 < timeout < float("inf")):
                # rejects <=0 AND non-finite (nan/inf): `nan <= 0` is False, and with nan the
                # deadline check `elapsed >= timeout` is always False -> the timeout silently no-ops.
                raise SystemExit("error: --timeout must be a positive, finite number of seconds")
            i += 2
        else:
            positional.append(pre[i])
            i += 1
    if len(positional) > 1:
        raise SystemExit(
            "usage: pty-capture.py [--timeout SECONDS] [out-path] -- <command> [args...]\n"
            f"error: too many arguments before '--': {positional}"
        )
    out = positional[0] if positional else "/tmp/pty-out.txt"
    sys.exit(main(out, command, timeout))
