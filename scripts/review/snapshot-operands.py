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
import hashlib
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import containment  # noqa: E402


def _read_leaf_nofollow(fd: int) -> bytes:
    """Drain an already-opened descriptor, refusing anything that is not a regular file."""
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            containment.refuse("target is not a regular file at read time")
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


def _read_snapshot(path: str) -> bytes:
    """Read one of OUR OWN snapshot copies (they live in a private dir, not in the repository)."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        containment.refuse(f"snapshot could not be read without following a link: {path}: {error}")
    return _read_leaf_nofollow(fd)


def _read_nofollow(path: str) -> bytes:
    """Read `path` with no symlink traversal at ANY component, walking down from the repository root.

    `O_NOFOLLOW` PROTECTS ONLY THE LEAF (PR #63 recheck). `containment.contained_regular_file()`
    validates by pathname and this function then re-opened that pathname, so a same-account process
    could rename an accepted operand's parent and put a symlink in its place between the two: the leaf
    flag says nothing about ancestors, and the substituted parent was traversed happily — inlining or
    snapshotting an outside file. Descending component by component with `O_DIRECTORY|O_NOFOLLOW`,
    rooted at the validated repository, makes the ancestors part of the same no-follow guarantee, so
    the object opened is the one containment approved.
    """
    root = containment.repository_root()
    relative = os.path.relpath(path, root)
    components = [c for c in relative.split(os.sep) if c and c != "."]
    if not components or ".." in components:
        containment.refuse(f"operand is not inside the repository: {path}")

    dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in components[:-1]:
            try:
                next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
            except OSError as error:
                containment.refuse(
                    f"operand's parent {component!r} could not be traversed without following a link: "
                    f"{path}: {error}"
                )
            os.close(dir_fd)
            dir_fd = next_fd
        try:
            fd = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
        except OSError as error:
            containment.refuse(f"operand could not be read without following a link: {path}: {error}")
    finally:
        os.close(dir_fd)

    return _read_leaf_nofollow(fd)


#: Written beside the snapshots so the caller can re-verify the exact bytes just before launching.
DIGEST_MANIFEST = "digests.tsv"


def _verify(dest: str) -> int:
    """Re-check every snapshot against the digest recorded when it was taken.

    WHY NOT INLINE THE BYTES INSTEAD (the first attempt, reverted). Embedding the operand contents in
    the prompt removes the pathname entirely and so closes the same-UID window completely — but a
    prompt is an argv string, and Linux caps a SINGLE argument at `MAX_ARG_STRLEN` (32 x PAGE_SIZE =
    128 KiB) regardless of the much larger total `ARG_MAX`. macOS has no such per-argument cap, so the
    local suite passed while CI failed with exit 126 on an ordinary two-file audit (README.md +
    CHANGELOG.md = 175 KB). Embedding therefore caps audits at roughly one medium file — a capability
    regression worse than the narrow race it closed.

    SO THE HONEST SCOPE IS STATED RATHER THAN OVERCLAIMED. Path transport is kept, the window between
    validation and the reviewer's open is narrowed to the microseconds between this check and `exec`,
    and the residual is documented: a same-UID writer that wins that race is NOT defended against here,
    and cannot be — the same attacker can rewrite this script. What this does defend is everything the
    original finding was about: a stale, swapped or symlinked operand from BEFORE the run.
    """
    manifest = os.path.join(dest, DIGEST_MANIFEST)
    try:
        with open(manifest, "r", encoding="utf-8") as stream:
            records = [line.rstrip("\n").split("\t") for line in stream if line.strip()]
    except OSError as error:
        containment.refuse(f"snapshot digest manifest is unreadable: {manifest}: {error}")
    for expected, path in records:
        payload = _read_snapshot(path)
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            containment.refuse(
                f"a snapshot changed after it was taken, refusing to launch the reviewer: {path} "
                f"hashes {actual[:12]}…, recorded {expected[:12]}…"
            )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", default="snapshot-operands")
    parser.add_argument("--dest", required=True, help="private directory to snapshot into")
    parser.add_argument("--verify", action="store_true",
                        help="re-check existing snapshots in --dest against their recorded digests")
    parser.add_argument("operands", nargs="*")
    arguments = parser.parse_args(argv)

    containment.TOOL = arguments.tool
    if arguments.verify:
        return _verify(os.path.realpath(arguments.dest))
    if not arguments.operands:
        containment.refuse("name at least one operand to snapshot")

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
        snapshots.append((target, hashlib.sha256(payload).hexdigest()))

    # The digests the caller re-verifies immediately before launching the reviewer, narrowing the
    # window between "these are the bytes we validated" and "the reviewer opens them".
    manifest = os.path.join(dest, DIGEST_MANIFEST)
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        for target, digest in snapshots:
            stream.write(f"{digest}\t{target}\n")

    for target, _digest in snapshots:
        print(target)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
