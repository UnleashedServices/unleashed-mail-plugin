#!/usr/bin/env python3
"""Stage the bound plan into a disposable review checkout, and print the digest of what was staged.

WHY THIS IS SHARED AND NOT COPIED
Both review arms run their reviewer against a `git worktree add --detach` checkout so a plan edited
after binding cannot reach the reviewer through the live, mutable file. The gemini arm got that
staging first; the codex arm ran in the LIVE tree and never inherited it, so an A->B->A swap let codex
review substituted bytes while the artifact attested the original (PR #63 recheck, P1). That is the
exact "a rule that lives in one script is a rule the next entrypoint will not have" failure this repo
keeps hitting — so the staging lives HERE, called identically by `isolated-agy-review.sh` and
`isolated-codex-review.sh`. A cross-arm test drives the same attack through both.

WHAT IT GUARANTEES
  * AUTHENTICATION: with `--snapshot`/`--record`, the bound `.planbytes` are read once through an
    O_NOFOLLOW descriptor and refused unless they hash to the digest the `.plan` record attests to — so
    a same-account process rewriting `.planbytes` between binding and staging cannot substitute bytes.
    With `--live`, the working-tree plan is staged (weaker provenance, used only when no snapshot
    exists) but through the identical no-follow write.
  * NO SYMLINK TRAVERSAL: `git worktree add --detach` recreates committed tree entries, so the plan
    path — or any parent — may materialize as a symlink pointing outside the checkout. Every directory
    component is opened O_DIRECTORY|O_NOFOLLOW (a symlinked parent fails ELOOP) and the leaf is
    unlinked-without-following then created O_CREAT|O_EXCL|O_NOFOLLOW, so a materialized symlink is
    removed as a link and never written through (PR #63 recheck, P1).

Prints the hex sha256 of the staged bytes on stdout — the caller anchors its post-run basis check to it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys


def _read_nofollow(path: str, label: str) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        sys.exit(f"stage-bound-plan: cannot read the {label}: {path}: {error}")
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            sys.exit(f"stage-bound-plan: the {label} is not a regular file: {path}")
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


def _stage_no_follow(tree_root: str, rel: str, payload: bytes) -> None:
    components = [c for c in rel.split("/") if c and c != "."]
    if not components or ".." in components:
        sys.exit(f"stage-bound-plan: refusing an unsafe staging path: {rel}")
    dir_fd = os.open(tree_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for comp in components[:-1]:
            try:
                os.mkdir(comp, 0o755, dir_fd=dir_fd)
            except FileExistsError:
                pass
            next_fd = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = next_fd
        leaf = components[-1]
        try:
            os.unlink(leaf, dir_fd=dir_fd)   # never follows; removes a materialized symlink as a link
        except FileNotFoundError:
            pass
        fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
        try:
            written = 0
            while written < len(payload):
                written += os.write(fd, payload[written:])
        finally:
            os.close(fd)
    finally:
        os.close(dir_fd)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", required=True, help="the disposable detached checkout root")
    parser.add_argument("--rel", required=True, help="repo-relative plan path to stage into the tree")
    parser.add_argument("--snapshot", help="the bound <transcript>.planbytes to authenticate and stage")
    parser.add_argument("--record", help="the <transcript>.plan digest record to authenticate against")
    parser.add_argument("--live", help="fall back to staging this working-tree plan (weaker provenance)")
    arguments = parser.parse_args(argv)

    if arguments.snapshot:
        if not arguments.record:
            sys.exit("stage-bound-plan: --snapshot requires --record")
        payload = _read_nofollow(arguments.snapshot, "bound plan snapshot")
        fields = _read_nofollow(arguments.record, "plan binding record").decode("utf-8", "replace").split()
        if not fields:
            sys.exit(f"stage-bound-plan: the plan binding record is empty: {arguments.record}")
        expected = fields[0]
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            sys.exit(
                "stage-bound-plan: the bound plan snapshot does not match its recorded digest — "
                f"refusing to stage substituted bytes: {arguments.snapshot} hashes {actual[:12]}…, "
                f"{arguments.record} records {expected[:12]}…"
            )
    elif arguments.live:
        payload = _read_nofollow(arguments.live, "working-tree plan")
        actual = hashlib.sha256(payload).hexdigest()
    else:
        sys.exit("stage-bound-plan: pass either --snapshot/--record or --live")

    _stage_no_follow(arguments.tree, arguments.rel, payload)
    print(actual)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
