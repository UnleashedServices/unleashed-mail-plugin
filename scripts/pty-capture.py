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
    python3 pty-capture.py --allocated "$CODEX_TRANSCRIPT" -- \
        codex exec -c model_reasoning_effort=xhigh -s read-only "$(cat .codex-prompt-$TICKET-r$ROUND.md)"

    # Antigravity (agy) review.
    python3 pty-capture.py --allocated "$GEMINI_TRANSCRIPT" -- \
        agy --add-dir "$(pwd)" -p "Read and follow .agy-prompt-$TICKET-r$ROUND.md"

Exit codes: the wrapped command's exit code propagates (0 = success; non-zero
= failure). Captured output is written to <out-path>, which is REQUIRED — there
is no shared default, because a fixed path lets a run that died before writing
leave stale bytes for the next reader to trust.
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
# THE CAPTURE BUFFER IS BOUNDED (PR #63 recheck, P2). `--timeout` bounds wall-clock and nothing bounded
# BYTES: a reviewer stuck in an output loop accumulated everything it printed in memory for the whole
# 28-minute budget, which is tens of gigabytes at PTY speeds and takes the machine down rather than the
# round. 64 MiB is ~1000x the largest real transcript (a few tens of KiB) and ~500x the codex argv cap,
# so nothing legitimate approaches it. Hitting it is treated like the timeout: terminate the child
# through the same ladder, persist what was captured, and exit non-zero — a runaway must fail the round
# loudly, never be silently truncated into a transcript someone then greps for a verdict.
MAX_CAPTURE_BYTES = 64 * 1024 * 1024

# The allocator's run identity, and the two grammars that must agree with `review-verdict.py`.
# `_RUN_ID_HEX_LENGTH` is 16 random bytes rendered as hex; `_LAUNCH_RECORD_RE` mirrors that file's
# `_LAUNCH_RECORD` and `_ALLOCATED_LEAF_RE` mirrors its `_ALLOCATOR_BASENAME`. They are duplicated
# rather than imported because this module runs on the blocking hook path and imports nothing local —
# `test_doc_gates` asserts the pairs are identical so the copies cannot drift.
_RUN_ID_HEX_LENGTH = 16 * 2
_LAUNCH_RECORD_RE = re.compile(
    rb"\A([0-9a-f]{" + str(_RUN_ID_HEX_LENGTH).encode("ascii")
    + rb"}) ([A-Za-z0-9][A-Za-z0-9-]*)\n\Z"
)
_ALLOCATED_LEAF_RE = re.compile(
    r"\A[A-Za-z0-9][A-Za-z0-9._-]*r[0-9]+-(?P<reviewer>[A-Za-z0-9][A-Za-z0-9-]*)-"
    r"(?P<run_id>[0-9a-f]{" + str(_RUN_ID_HEX_LENGTH) + r"})\.txt\Z"
)
# THE ROUND IS NUMERIC, and that is not merely a convention (PR #63 recheck, P2). The generic component
# grammar below accepts `[A-Za-z0-9._-]+`, so a round of `round-1` allocated a leaf named `…rround-1-…`,
# the capture spent a full 12-28 minute review, and `review-verdict.py` then refused the transcript
# because its `_ALLOCATOR_BASENAME` requires `r[0-9]+`. Validating here — the one allocation path both
# arms funnel through — makes malformed input fail in milliseconds instead of after the review.
_ROUND_COMPONENT_RE = re.compile(r"[0-9]+")
#: Both readers of the launch record read this many bytes and then `fullmatch` the result, so a record
#: longer than this can never validate. The allocator therefore has to REFUSE a reviewer that would
#: produce one, rather than reserving a leaf no capture or verdict can ever use (PR #63 recheck, P2 —
#: reproduced: a 100-character reviewer allocated cleanly, wrote a 134-byte record, and `--allocated`
#: immediately refused it). The bound is derived from the grammar, not restated: run id, one space, the
#: reviewer, one newline.
_LAUNCH_RECORD_READ_BYTES = 128
_MAX_REVIEWER_LENGTH = _LAUNCH_RECORD_READ_BYTES - _RUN_ID_HEX_LENGTH - len(" ") - len("\n")


def _report_overflow() -> bool:
    """Announce the capture cap and return True, so every drain path sets `overflowed` identically.

    THE CAP MUST HOLD ON EVERY PATH THAT APPENDS (PR #63 recheck, P2). It was applied in the main read
    loop only, and the two drain sweeps that follow — the post-reap sweep and the `finally` sweep —
    called `raw.extend()` without rechecking. A child that emitted just under the limit, spawned a
    descendant holding the PTY and exited, drove the wrapper past it: the reviewer measured 70,561,968
    bytes captured and an exit status of 0, so the oversized transcript was treated as a completed
    review. One helper, called from all three, so a fourth append site cannot quietly opt out.
    """
    try:
        sys.stderr.write(
            f"pty-capture: child produced more than {MAX_CAPTURE_BYTES} bytes; terminating child\n"
        )
        sys.stderr.flush()
    except OSError:
        pass
    return True


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

    Allocated writes MUST still truncate to the payload length (PR #63 review, High). Omitting O_TRUNC
    protects the reservation — the leaf must already exist — but it does not bound the file, so a
    re-write that is SHORTER than a previous one leaves the earlier tail in place. That was reproduced
    end-to-end: a 19-byte failed round left a 55-byte file whose surviving tail read `VERDICT: APPROVE`,
    and the wrapper's `grep … | tail -1` then reported a failed review as an approval. ftruncate is the
    right instrument because, unlike O_TRUNC, it can never CREATE the file, so the reservation invariant
    is preserved exactly.
    """
    # NO O_TRUNC ON THE NON-ALLOCATED PATH (PR #63 recheck, P2). O_TRUNC empties a pre-existing file AT
    # open(), before any fstat can look — so a hard link planted at the predictable fresh/`.captureid`
    # path was already truncated to zero by the time the `nlink` guard (itself wrongly gated on
    # `allocated`) would have fired. The victim's bytes were destroyed on the way in; reproduced with a
    # hard-linked `PRECIOUS OUTSIDE DATA` becoming the capture. Dropping O_TRUNC means a pre-existing
    # file is OPENED but not emptied: the unconditional `nlink != 1` check below then refuses a
    # hard-linked victim before a single byte is written, and the `ftruncate` after the write (which
    # was already there for the allocated path) bounds an honest single-linked overwrite to this run's
    # length. This preserves the legitimate "overwrite a stale non-allocated capture" behaviour while
    # closing the victim-rewrite hole — strictly better than O_EXCL, which would have refused the honest
    # overwrite too.
    create_flags = 0 if allocated else os.O_CREAT
    flags = os.O_WRONLY | create_flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)

    def _opener(p, _flags):
        fd = os.open(p, flags, 0o600)   # our flags (incl. O_NOFOLLOW/O_NONBLOCK), not open()'s default
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise NonRegularCaptureTargetError(errno.ENOTSUP, "refusing a non-regular capture target", p)
            # A HARD LINK IS A REGULAR FILE, so `O_NOFOLLOW` and `S_ISREG` both accept one. A
            # same-account process that replaces the reserved leaf with a link to any other file it
            # owns turns the `fchmod`/write/`ftruncate` below into a rewrite of THAT file — reproduced
            # by linking an 18-byte file at the reserved path and watching it become the capture, mode
            # 0600 (PR #63 recheck, P2). The allocator creates its leaf with exactly one link, so a
            # second one is never legitimate here. UNCONDITIONAL, not `allocated`-gated: this is the guard
            # that now stands in for O_TRUNC's removed truncation on the fresh path — it must run there,
            # and it never fires falsely because an honestly fresh or honestly stale single-linked file
            # has exactly one link. It executes BEFORE the write below, so a hard-linked victim is
            # refused with its bytes intact.
            if info.st_nlink != 1:
                raise NonRegularCaptureTargetError(
                    errno.EMLINK,
                    f"refusing a hard-linked capture target ({info.st_nlink} links) — writing it would "
                    "rewrite whatever else shares the inode",
                    p,
                )
            os.fchmod(fd, 0o600)        # tighten an already-existing 0644 file (O_CREAT mode is create-only)
        except BaseException:
            os.close(fd)                # open() hasn't taken ownership yet, so we must close it here
            raise
        return fd

    with open(path, "wb", opener=_opener) as fh:
        fh.write(data)
        # Bound the file to what THIS run produced. Load-bearing for BOTH paths now: the allocated path
        # never truncates (reservation), and the non-allocated path no longer uses O_TRUNC (so an
        # overwrite of a longer stale file would otherwise leave a tail). A shorter re-write must not
        # resurrect the previous content's tail.
        fh.flush()
        os.ftruncate(fh.fileno(), len(data))


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
    # PREFLIGHT the reservation BEFORE spawning anything. In allocated mode the reservation was
    # previously enforced only by the final write, i.e. AFTER the wrapped command had already run —
    # so a stale allocated path, or a leaf someone deleted, burned an entire review (up to 28
    # minutes of `agy`) and only then failed on a missing file. The round is lost either way, but
    # failing in milliseconds costs nothing and tells the caller to re-allocate immediately.
    #
    # This is a fail-FAST check, not a substitute for the write-time defences: the leaf can still be
    # swapped while the command runs, so `_write_private` keeps O_NOFOLLOW, the S_ISREG check and
    # the no-O_CREAT open. Checked with lstat, so a symlink planted at the reserved path is rejected
    # here rather than silently resolving to its target.
    if allocated:
        # Reports and RETURNS like the write-failure path rather than raising: `main()`'s contract is
        # "returns an exit code", and an existing test pins that for the unreserved case.
        try:
            reserved = os.lstat(out_path)
        except OSError as error:
            print(
                f"pty-capture: allocated transcript is not reserved, refusing to run the command: "
                f"{out_path}: {error}",
                file=sys.stderr,
            )
            return 1
        if not stat.S_ISREG(reserved.st_mode):
            print(
                f"pty-capture: allocated transcript is not a regular file, refusing to run the "
                f"command: {out_path}",
                file=sys.stderr,
            )
            return 1
        if reserved.st_nlink != 1:
            print(
                f"pty-capture: allocated transcript is hard-linked ({reserved.st_nlink} links), "
                f"refusing to run the command: {out_path}",
                file=sys.stderr,
            )
            return 1
        # THE LAUNCH RECORD, BEFORE THE REVIEWER RUNS. `review-verdict.py` rejects a transcript whose
        # `.launch` sibling is absent or malformed — but only at WRITE time, so a deleted or corrupted
        # record meant a 20-30 minute review completed, exited 0, and was then thrown away. Checking
        # the same precondition here costs a read and turns a wasted round into an immediate refusal.
        #
        # A SHAPE CHECK WAS NOT ENOUGH (PR #63 recheck, P2). "Regular and nonempty" accepted a
        # `not-a-run-id` record, ran the wrapped command to completion and returned 0 — the verdict
        # writer then rejected the transcript, so the expensive round was still lost. Reproduced. The
        # canonical grammar is checked here instead, AND the recorded run id must equal the one the
        # allocator embedded in the filename: a record that belongs to a different run is exactly as
        # unusable as a malformed one, and both are free to detect before spawning.
        #
        # `_LAUNCH_RECORD_RE` / `_ALLOCATED_LEAF_RE` mirror `review-verdict.py`'s `_LAUNCH_RECORD` and
        # `_ALLOCATOR_BASENAME`. That duplication is deliberate — this file is the blocking hook path
        # and imports nothing local — so `test_doc_gates` asserts the two grammars agree, which is what
        # keeps a copy from drifting into a second, softer authority.
        #
        # ONE OPEN, O_NOFOLLOW|O_NONBLOCK, AND THE CHECKS ARE MADE ON THE DESCRIPTOR (PR #63 recheck,
        # P2). This was `lstat` followed by a plain `open()` of the same NAME, which is both a
        # check-then-use and a hang: a same-account process replacing the record with a FIFO — or a
        # symlink to one — in that window made the blocking `open()` wait for a writer that never
        # comes. It happens BEFORE the fork and before the timeout clock starts, so `--timeout` cannot
        # recover the capture and the round hangs indefinitely. `O_NONBLOCK` makes the open of a
        # reader-less FIFO return immediately, `O_NOFOLLOW` refuses the symlink, and `fstat` on the
        # resulting descriptor describes the object actually opened rather than one a second lookup
        # found.
        launch_path = out_path + ".launch"
        launch_fd = -1
        try:
            launch_fd = os.open(
                launch_path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            )
        except OSError as error:
            print(
                f"pty-capture: allocated transcript has no usable launch record, refusing to run the "
                f"command: {launch_path}: {error}",
                file=sys.stderr,
            )
            return 1
        try:
            launch_info = os.fstat(launch_fd)
            if not stat.S_ISREG(launch_info.st_mode) or launch_info.st_size == 0:
                print(
                    f"pty-capture: allocated transcript's launch record is unusable, refusing to run "
                    f"the command: {launch_path}",
                    file=sys.stderr,
                )
                return 1
            # Run id + a space + the reviewer name + newline; 128 is ample and bounds a planted file.
            launch_bytes = os.read(launch_fd, _LAUNCH_RECORD_READ_BYTES)
        except OSError as error:
            print(
                f"pty-capture: allocated transcript's launch record is unreadable, refusing to run "
                f"the command: {launch_path}: {error}",
                file=sys.stderr,
            )
            return 1
        finally:
            if launch_fd >= 0:
                try:
                    os.close(launch_fd)
                except OSError:
                    pass
        launch_match = _LAUNCH_RECORD_RE.fullmatch(launch_bytes)
        if launch_match is None:
            print(
                f"pty-capture: allocated transcript's launch record is malformed, refusing to run the "
                f"command (expected {_RUN_ID_HEX_LENGTH} hex digits, a space and the reviewer): "
                f"{launch_path}",
                file=sys.stderr,
            )
            return 1
        leaf_match = _ALLOCATED_LEAF_RE.fullmatch(os.path.basename(out_path))
        if leaf_match is not None:
            if leaf_match.group("run_id") != launch_match.group(1).decode("ascii"):
                print(
                    f"pty-capture: allocated transcript's launch record names a DIFFERENT run than its "
                    f"filename, refusing to run the command: {launch_path}",
                    file=sys.stderr,
                )
                return 1
            # A renamed leaf is caught here too: the record is the allocator's attestation, the
            # filename is the caller's spelling, and a mismatch means one of them was rewritten.
            if leaf_match.group("reviewer").casefold() != launch_match.group(2).decode("ascii").casefold():
                print(
                    f"pty-capture: allocated transcript's launch record names reviewer "
                    f"{launch_match.group(2).decode('ascii')!r} but its filename says "
                    f"{leaf_match.group('reviewer')!r}, refusing to run the command: {launch_path}",
                    file=sys.stderr,
                )
                return 1
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
    overflowed = False  # set if the child printed more than MAX_CAPTURE_BYTES
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
                    if len(raw) > MAX_CAPTURE_BYTES:
                        overflowed = _report_overflow()
                        break
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
                        if len(raw) > MAX_CAPTURE_BYTES:
                            overflowed = _report_overflow()
                            break
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
                if len(raw) > MAX_CAPTURE_BYTES:
                    overflowed = _report_overflow()
                    break
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
            # ONLY the non-allocated path may create its parents. In allocated mode the ALLOCATOR owns
            # the directory chain and builds it at 0700; this call used the process umask, so it would
            # rebuild the private state tree at 0755. That is not merely untidy — the allocator VALIDATES
            # the mode, so every later `--allocate` for that repo hash then fails with
            # "has mode 0o0755, expected 0o0700", permanently, until someone chmods it by hand. The
            # trigger is real: remove ~/.local/state mid-capture (a manual reset during an up-to-28-minute
            # review) and the finishing capture recreates the ancestors at 0755, fails ENOENT on the leaf
            # it never reserved, and bricks allocation for that repo — a self-inflicted fail-closed denial
            # whose error blames the wrong thing (PR #63 review, gap 3).
            if out_dir and not allocated:
                os.makedirs(out_dir, exist_ok=True)
            # PTYs translate \n -> \r\n (ONLCR); normalize to Unix newlines.
            cleaned = ANSI_RE.sub(b'', bytes(raw)).replace(b'\r\n', b'\n')
            # SESSION-SAFE write (#44 review §4). Review transcripts can quote message bodies / tokens,
            # and the recipes use predictable /tmp paths, so a pre-created symlink or a 0644 file is a
            # local hazard: another user could replace the reserved `<out-path>` with a symlink to redirect the
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
    if overflowed:
        # Distinct from 124 so a runaway is not read as a slow reviewer. The transcript on disk holds
        # the first MAX_CAPTURE_BYTES, which is evidence of what happened, not a reviewable capture.
        exit_status = 125
    elif timed_out:
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
            "usage: pty-capture.py [--timeout SECONDS] [--allocated] <out-path> -- <command> [args...]\n"
            f"error: too many arguments before '--': {positional}"
        )
    if not positional:
        # The out-path is REQUIRED. This used to default to a fixed `/tmp` file, which is the MAJ-10
        # staleness hazard this whole ticket exists to remove: a run that dies before writing leaves the
        # PREVIOUS run's bytes at the shared path, and the next reader takes a stale transcript for a
        # fresh one. Two concurrent captures also silently overwrote each other. Every caller in the tree
        # already passes a path, so the default only ever served the caller who FORGOT one — which is
        # exactly the caller who must not silently get a shared file (deep review, P2).
        raise SystemExit(
            "usage: pty-capture.py [--timeout SECONDS] [--allocated] <out-path> -- <command> [args...]\n"
            "error: an explicit out-path is required — there is no shared default, because a fixed "
            "path lets a dead run leave stale bytes for the next reader to trust"
        )
    return timeout, positional[0], allocated


ALLOCATION_MARKER = "UNLEASHED_TRANSCRIPT="
ALLOCATION_ATTEMPTS = 8
RUN_ID_BYTES = 16
# Every suffix a caller may append to the allocated leaf. `_basename_limit` reserves headroom for the
# LONGEST of these, so a name that fits the leaf also fits all of its siblings. `.promptsha256` (13
# chars) was added by the capture helpers and is longer than `.captureid` (10) — until it was listed
# here, a ticket producing a basename near NAME_MAX allocated fine and then failed to record its
# prompt binding with ENAMETOOLONG (deep review, codex inline). Anything appended to the leaf belongs
# in this tuple; that is the whole contract.
DERIVED_SIBLING_SUFFIXES = (".launch", ".captureid", ".promptsha256")
_COMPONENT_RE = re.compile(r"[A-Za-z0-9._-]+")
_ALLOCATE_OPTIONS = ("--repo-hash", "--ticket", "--round", "--reviewer")


class AllocationError(RuntimeError):
    """A fail-closed transcript allocation error suitable for a stderr diagnostic."""


def is_valid_transcript_component(value: str) -> bool:
    """Return whether a caller-supplied path component has the S-ALLOC grammar."""
    return value not in ("", ".", "..") and _COMPONENT_RE.fullmatch(value) is not None


def is_valid_reviewer_component(value: str) -> bool:
    """The generic component rule, PLUS the length the launch record can carry.

    The record is `<run id> <reviewer>\n` and both readers read `_LAUNCH_RECORD_READ_BYTES` and then
    `fullmatch`, so a longer reviewer produces a record that can never validate. Without this the
    allocator reserved a leaf, wrote the oversized record and returned 0 — and the very next step,
    `--allocated`, refused it as malformed. A reservation no capture or verdict can use is worse than
    a refusal, because it consumes the round (PR #63 recheck, P2 — reproduced with 100 characters).
    """
    return is_valid_transcript_component(value) and len(value) <= _MAX_REVIEWER_LENGTH


def is_valid_round_component(value: str) -> bool:
    """Return whether the ROUND additionally satisfies the numeric grammar synthesis requires.

    A SHARED, NAMED VALIDATOR rather than an inline check in `allocate_transcript` — M1.5/M1.8 bind the
    allocator's decision to the validators precisely so production logic cannot diverge from them, and
    an inline rule would be exactly that divergence. The round needs its own because the generic
    component grammar accepts `[A-Za-z0-9._-]+`, so `round-1` allocated a leaf named `…rround-1-…`, a
    full 12-28 minute review ran, and `review-verdict.py` then refused the transcript because its
    `_ALLOCATOR_BASENAME` requires `r[0-9]+` (PR #63 recheck, P2).
    """
    return is_valid_transcript_component(value) and _ROUND_COMPONENT_RE.fullmatch(value) is not None


def _identity(path: str):
    """(st_dev, st_ino) for an existing path, else None. Case- and spelling-independent by construction."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    return (info.st_dev, info.st_ino)


def _path_is_within(path: str, root: str) -> bool:
    """Is `path` inside `root`? Answered by INODE where both exist, lexically otherwise.

    `commonpath` is case-SENSITIVE, and this runs on default case-insensitive APFS: `$HOME/.CLAUDE/x`
    opens the same directory as `$HOME/.claude/x` while comparing unequal, so a case-mangled
    `XDG_STATE_HOME` was accepted as outside the protected root. `realpath` does not help — it resolves
    symlinks but preserves the caller's component spelling (PR #63 recheck, P2).

    Walking the ancestry by inode is the spelling-independent answer: it cannot be defeated by case,
    by `.`/`..`, or by a symlinked ancestor. The lexical comparison stays as the fallback for paths
    that do not exist yet, where there is no inode to compare — and it is casefolded there, since a
    not-yet-created `.CLAUDE` directory would still be created inside the protected root.
    """
    root_identity = _identity(root)
    if root_identity is not None:
        probe = os.path.abspath(path)
        seen = set()
        while probe not in seen:
            seen.add(probe)
            probe_identity = _identity(probe)
            if probe_identity is not None and probe_identity == root_identity:
                return True
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent

    try:
        common = os.path.commonpath((path, root))
    except ValueError:
        return False
    if common == root:
        return True
    try:
        return os.path.commonpath((path.casefold(), root.casefold())) == root.casefold()
    except ValueError:
        return False


def _unsafe_ancestor_reason(path: str, info) -> "str | None":
    """Why `path` may not stand above the allocator's private subtree, or None if it may.

    TWO PROPERTIES, ONE RULE, ONE IMPLEMENTATION.

      * OWNERSHIP. `os.access` says the mode bits permit us; it says nothing about WHO OWNS the
        directory. An attacker-created mode-0777 directory under `/tmp` passes an access check, and the
        allocator then puts its 0700 subtree beneath a parent whose owner can rename or replace that
        subtree between allocation and capture. Root is accepted because a root-owned ancestor like
        `/tmp` or `/` is the normal case and is not attacker-controlled.
      * RENAME PERMISSION COMES FROM THE PARENT. A self-owned but group/world-writable ancestor lets any
        local user rename or replace the allocator's mode-0700 child, and every private mode validated
        below it then protects a subtree that is no longer the one we created. The sticky bit is the
        exception that makes `/tmp` usable: with `S_ISVTX`, only the owner of an entry may rename or
        delete it, which is exactly the property being demanded.

    Both were enforced on the base candidate's NEAREST EXISTING ancestor and nowhere else, so the
    components `_mkdir_private_chain` creates between that ancestor and the base were exempt — and its
    `FileExistsError` branch, which exists precisely because another process can win that race, adopted
    whatever it found as long as it was a directory. Under a sticky world-writable anchor another user
    may create entries, so they could pre-create the base as their own 0777 directory in that window and
    the allocator would build inside it (PR #63 recheck, P2). The rule lives here so the probe and the
    race branch cannot answer differently.
    """
    if not stat.S_ISDIR(info.st_mode):
        return f"{path!r} is not a directory (a symlink or other object occupies it)"
    owner = info.st_uid
    if owner not in (os.getuid(), 0):
        return (
            f"{path!r} is owned by uid {owner}, not by this user — its owner could replace the "
            "allocated subtree between allocation and capture"
        )
    mode = info.st_mode
    if (mode & (stat.S_IWGRP | stat.S_IWOTH)) and not (mode & stat.S_ISVTX):
        return (
            f"{path!r} is writable by others (mode {stat.S_IMODE(mode):04o}) without the sticky bit — "
            "another local user could rename or replace the allocated subtree, and rename permission "
            "comes from the parent, not from the 0700 child"
        )
    return None


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
    try:
        probe_info = os.stat(probe)
    except OSError as error:
        return None, f"nearest existing directory {probe!r} is unreadable: {error}"
    unsafe = _unsafe_ancestor_reason(probe, probe_info)
    if unsafe is not None:
        return None, "nearest existing directory " + unsafe
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
    # `lexists` + `lstat`, NEVER `exists`/`isdir` (PR #63 recheck, P2). Both of the following followed
    # symlinks, and each is separately exploitable:
    #   * `os.path.exists(cursor)` is TRUE for a symlink, so a pre-planted link stops the walk and
    #     becomes the "existing ancestor"; `os.path.isdir(cursor)` then follows it to a real directory
    #     and accepts it. Reproduced: with `<base>/unleashed-mail -> <attacker-dir>`, the whole private
    #     transcript hierarchy was created INSIDE the attacker's directory.
    #   * the same follow in the `FileExistsError` branch below adopts a link raced in mid-loop.
    # `lexists` sees the link itself so the walk stops there, and `lstat` reports S_IFLNK so it fails
    # S_ISDIR — the allocation refuses instead of building through an ancestor someone else can
    # retarget or rename afterwards.
    missing = []
    cursor = path
    while not os.path.lexists(cursor):
        missing.append(cursor)
        parent = os.path.dirname(cursor)
        if parent == cursor:
            raise AllocationError(f"cannot find an existing ancestor for {path!r}")
        cursor = parent
    try:
        anchor = os.lstat(cursor)
    except OSError as error:
        raise AllocationError(f"existing ancestor {cursor!r} is unreadable: {error}")
    unsafe = _unsafe_ancestor_reason(cursor, anchor)
    if unsafe is not None:
        raise AllocationError("existing ancestor " + unsafe)

    for directory in reversed(missing):
        try:
            os.mkdir(directory, 0o700)
        except FileExistsError:
            # `lstat`, NOT `os.path.isdir` (PR #63 recheck, P2). Another process can win the race by
            # creating a SYMLINK at a component this loop is about to make; `os.path.isdir` follows it
            # and accepts the target, so the supposedly private transcript hierarchy gets built through
            # an attacker-controlled ancestor that can be retargeted or renamed afterwards. `lstat`
            # reports S_IFLNK for the link itself, so a raced symlink fails S_ISDIR and the allocation
            # refuses instead of adopting it.
            try:
                raced = os.lstat(directory)
            except OSError as error:
                raise AllocationError(
                    f"concurrent path {directory!r} vanished during allocation: {error}"
                )
            # THE SAME RULE AS THE ANCHOR, not merely "is it a directory" (PR #63 recheck, P2). This
            # branch exists because another process can win the race; requiring only S_ISDIR meant a
            # racer under a sticky world-writable anchor could pre-create this component as their own
            # 0777 directory and have the whole private subtree built inside it. `_unsafe_ancestor_reason`
            # answers here exactly as it answers for the base probe.
            unsafe = _unsafe_ancestor_reason(directory, raced)
            if unsafe is not None:
                raise AllocationError(
                    "concurrent path " + unsafe + " (created there mid-allocation)"
                )


def _validate_existing_private_directory(path: str, metadata=None) -> None:
    """Require an existing allocator-owned shared directory to be ours, exactly 0700, and NOT a symlink.

    lstat, not stat. `os.stat()` follows the link, so a pre-existing component such as
    `$XDG_STATE_HOME/unleashed-mail` that is a SYMLINK to a 0700 directory owned by the same user
    satisfied every check here while the bytes lived somewhere else entirely (PR #63 second-round
    review). That defeats what the 0700 requirement is for: the mode of the link's TARGET says
    nothing about who can replace the LINK, and whoever can retargets every future allocation.

    A symlink now fails the S_ISDIR test — `lstat` reports S_IFLNK — so it is rejected by the check
    that already exists rather than needing a new branch.
    """
    info = metadata if metadata is not None else os.lstat(path)
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


def _create_launch_record(path: str, run_id: str, reviewer: str) -> bool:
    """Create and owner-reopen a launch record; return False on an exclusive-name collision.

    RECORD FORMAT: `<32 hex run id> <reviewer>\\n`. The reviewer field was added because the identity
    the gate checks must come from the allocator, not from a filename the caller can rewrite
    (PR #63 recheck, P1). `review-verdict.py`'s `_LAUNCH_RECORD` parses the same two fields, and
    `test_doc_gates` pins the two grammars to each other.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        return False

    try:
        try:
            os.fchmod(fd, 0o600)
            _write_all(fd, (run_id + " " + reviewer + "\n").encode("ascii"))
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

        # THE REVIEWER GOES IN THE RECORD, not only in the filename (PR #63 recheck, P1). The reviewer
        # identity was parsed out of the basename and nothing else carried it, so a rename defeated the
        # two-arm quorum in BOTH directions: a name outside the allocator grammar made the identity
        # check `continue` (it was the only reader), and a canonical name with the reviewer field
        # swapped was satisfied by a `.launch` that bound the run id alone. The allocator already knows
        # the reviewer here — recording it makes the identity allocator-ATTESTED instead of
        # caller-spelled, and a rename can no longer change the answer.
        #
        # The record is created BEFORE the allocation marker is written, and the two statements are
        # kept adjacent: `test_freshness`'s marker-before-record mutant anchors on exactly this
        # `try:`/create pair to prove the ordering is what rejects a dispatched-then-recorded run.
        try:
            launch_created = _create_launch_record(path + ".launch", run_id, reviewer)
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
        # The round is validated by its own shared validator, which subsumes the generic one.
        checker = {
            "round": is_valid_round_component,
            "reviewer": is_valid_reviewer_component,
        }.get(label, is_valid_transcript_component)
        if not checker(value):
            reason = ""
            if label == "round":
                reason = (" — the round must be digits only, because review-verdict.py's allocator "
                          "grammar requires `r<digits>` and would reject the transcript AFTER the "
                          "review had run")
            elif label == "reviewer" and len(value) > _MAX_REVIEWER_LENGTH:
                reason = (f" — at most {_MAX_REVIEWER_LENGTH} characters, because the launch record "
                          f"`<run id> <reviewer>` must fit the {_LAUNCH_RECORD_READ_BYTES} bytes both "
                          "readers read; a longer one allocates a leaf that `--allocated` then refuses")
            raise AllocationError(f"invalid {label} component: {value!r}" + reason)

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
