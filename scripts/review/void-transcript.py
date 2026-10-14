#!/usr/bin/env python3
"""Invalidate a VOIDED round's transcript: keep its bytes for forensics, then leave the leaf EMPTY (COREDEV-2887).

A harness that detects a reviewer mutation, a rewritten basis or an unreadable checkout exits 3 — but the capture
had already written the reviewer's text into the reserved leaf, so an approving `VERDICT:` stayed in a file that
`persist-verdict.sh` and `review-verdict.py write` accept (they refuse only an EMPTY transcript and never consume
the harness's outcome). Codex reproduced a rewritten staged plan plus `VERDICT: APPROVE` being accepted
(plan round 4, Q1). After this runs, the leaf is EMPTY — MISSING at both layers — and the reviewer's text is in
`<leaf>.void`, which nothing downstream reads.

Order: the forensic copy FIRST, best-effort; the truncation SECOND, mandatory. A copy that fails (an entry already
at `<leaf>.void`, a full disk) never prevents the invalidation. The leaf is opened without O_CREAT, so the
allocator's reservation is neither recreated nor replaced, and with O_NOFOLLOW, so a symlink planted at the leaf is
refused rather than followed.

Usage: void-transcript.py <leaf>
Exit:  0 the leaf is empty (or was already) · 1 it could not be emptied — the caller must say so loudly
"""

from __future__ import annotations

import os
import sys

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def _read_all(path: str) -> bytes:
    """Every byte of `path`, read without following a symlink."""
    descriptor = os.open(path, os.O_RDONLY | _NOFOLLOW)
    try:
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1 << 16)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


def _write_exclusive(path: str, data: bytes) -> None:
    """Create `path` exclusively, without following a symlink, and write all of `data`."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError  # a zero-byte write would otherwise loop forever
            view = view[written:]
    finally:
        os.close(descriptor)


def main() -> int:
    """Copy the leaf to `<leaf>.void` (best-effort), then empty it (mandatory)."""
    operands = sys.argv[1:]
    if len(operands) != 1:
        print("usage: void-transcript.py <leaf>", file=sys.stderr)
        return 1
    leaf = operands[0]
    try:
        data = _read_all(leaf)
    except OSError:
        data = b""
    if data:
        try:
            _write_exclusive(leaf + ".void", data)
        except OSError as error:
            print(
                f"void-transcript: the forensic copy {leaf + '.void'!r} was not written ({error}); "
                "invalidating anyway",
                file=sys.stderr,
            )
    try:
        descriptor = os.open(leaf, os.O_WRONLY | os.O_TRUNC | _NOFOLLOW)
        os.close(descriptor)
    except OSError as error:
        print(f"void-transcript: could not empty {leaf!r}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
