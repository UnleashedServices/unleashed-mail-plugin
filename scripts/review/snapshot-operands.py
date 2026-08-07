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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", default="snapshot-operands")
    parser.add_argument("--dest", required=True, help="private directory to snapshot into")
    parser.add_argument("operands", nargs="+")
    arguments = parser.parse_args(argv)

    containment.TOOL = arguments.tool
    root = containment.repository_root()
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
