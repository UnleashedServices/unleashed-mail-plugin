#!/usr/bin/env python3
"""Snapshot audit operands into a private tree so the reviewer reads immutable copies, not live paths.

THE DEFECT (PR #63 recheck, P1). `audit-codex.sh` validated each operand with `containment.py`
(non-symlink, regular, in-repo) and then handed the repo-relative PATH to codex, which opened it later.
Between the validation and codex's open, a same-account process replaced an accepted file with a symlink
to an outside secret; `codex exec -s read-only` followed it and disclosed the outside file. `-s
read-only` stops writes, not a validate-then-open race. Reproduced end to end.

THE FIX. Validation and the read are now ONE operation per operand: `containment.py` proves the operand
is a non-symlink regular file inside the repository, and this program IMMEDIATELY opens that path with
`O_NOFOLLOW` and copies the bytes into a private snapshot directory. codex is pointed at the snapshot
copies, which no later swap can change. `O_NOFOLLOW` on the read means that even a swap landing between
the containment check and this open is refused (a symlink fails ELOOP) rather than followed.

Prints one snapshot absolute path per line, in the operand order, for the caller to name in the prompt.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import containment  # noqa: E402


def _read_nofollow(path: str) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        containment.refuse(f"operand could not be read without following a link: {path}: {error}")
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            containment.refuse(f"operand is not a regular file at read time: {path}")
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


# A prompt is an argv string, so an unbounded embed would blow past the reviewer CLI's limits with a
# confusing failure. Refuse loudly instead, and say what to do about it.
_MAX_EMBED_BYTES = 256 * 1024


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", default="snapshot-operands")
    parser.add_argument("--dest", help="private directory to snapshot into (path-transport mode)")
    parser.add_argument(
        "--embed",
        action="store_true",
        help="emit the retained BYTES inline instead of snapshot paths (no later pathname lookup)",
    )
    parser.add_argument("operands", nargs="+")
    arguments = parser.parse_args(argv)

    containment.TOOL = arguments.tool
    root = containment.repository_root()

    # EMBED: TRANSPORT THE BYTES, NOT A PATHNAME (PR #63 recheck, P2). Snapshotting to a private
    # directory closed the validate-then-open race against the LIVE tree, but it left a second window:
    # the reviewer still opened the snapshot by NAME, and a same-account process watching for
    # `codex-audit-src.*` could overwrite a copy — or replace its leaf with a symlink — between this
    # helper exiting and that open. A private mode excludes other users, not another process under the
    # same UID, so "immutable copies" overstated what a directory could promise.
    #
    # There is no filesystem defence against a same-UID writer once a pathname is involved, so the
    # pathname is removed: the authenticated bytes are placed directly in the prompt the reviewer
    # receives as an argument. Nothing is opened after validation, so there is no window at all.
    if arguments.embed:
        sections = []
        total = 0
        for operand in arguments.operands:
            real = containment.contained_regular_file(operand, "audit operand")
            payload = _read_nofollow(real)
            relative = os.path.relpath(real, root)
            total += len(payload)
            if total > _MAX_EMBED_BYTES:
                containment.refuse(
                    f"the operands exceed {_MAX_EMBED_BYTES} bytes once inlined, which would overflow "
                    "the reviewer's argument. Audit fewer files per run."
                )
            # A delimiter that cannot be forged from inside a source file: the operand list was already
            # contained (no control characters), and the fence carries the repo-relative identity.
            text = payload.decode("utf-8", "replace")
            sections.append(f"===== BEGIN {relative} =====\n{text}\n===== END {relative} =====")
        print("\n".join(sections))
        return 0

    if not arguments.dest:
        containment.refuse("pass --dest for path transport, or --embed to inline the bytes")
    dest = os.path.realpath(arguments.dest)

    snapshots = []
    for index, operand in enumerate(arguments.operands):
        # Validate (non-symlink, regular, in-repo) THEN read through O_NOFOLLOW in the same breath.
        real = containment.contained_regular_file(operand, "audit operand")
        payload = _read_nofollow(real)
        relative = os.path.relpath(real, root)
        # Preserve the repo-relative structure under the private dest so the reviewer sees familiar
        # paths, but numbered by operand order so two files with the same basename cannot collide.
        target_dir = os.path.join(dest, str(index), os.path.dirname(relative))
        os.makedirs(target_dir, mode=0o700, exist_ok=True)
        target = os.path.join(dest, str(index), relative)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            written = 0
            while written < len(payload):
                written += os.write(fd, payload[written:])
        finally:
            os.close(fd)
        snapshots.append(target)

    for path in snapshots:
        print(path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
