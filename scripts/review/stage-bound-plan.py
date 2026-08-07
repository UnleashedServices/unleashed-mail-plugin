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
  * AUTHENTICATION: the bound `.planbytes` are read once through an O_NOFOLLOW descriptor and refused
    unless they hash to the digest the `.plan` record attests to — so a same-account process rewriting
    `.planbytes` between binding and staging cannot substitute bytes. There is NO live-plan fallback:
    a `--live` mode existed for "an older capture or a direct call", but both harnesses invoke
    `pty-capture --allocated`, which refuses a leaf without a valid `.launch` record, so no run that
    could complete ever reached it. Deleting `.planbytes` therefore used to downgrade the arm to the
    mutable plan; now both arms refuse (PR #63 recheck, P1).
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
import re
import stat
import sys

#: `<64 hex digits><two spaces><plan identity><newline>` — the record `bind-prompt.py` writes and
#: `review-verdict.py` re-parses. Duplicated here rather than imported (this runs as a standalone
#: script from shell); `test_doc_gates` pins the two spellings together.
_PLAN_BINDING = re.compile(rb"\A([0-9a-f]{64})  (.+)\n\Z")


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
    # BOTH REQUIRED. They were optional so a `--live` fallback could stand in; with that mode gone,
    # optional would mean an omitted `--record` staged unauthenticated bytes — the same fail-open,
    # re-created by an argument default rather than a branch.
    parser.add_argument("--snapshot", required=True,
                        help="the bound <transcript>.planbytes to authenticate and stage")
    parser.add_argument("--record", required=True,
                        help="the <transcript>.plan digest record to authenticate against")
    arguments = parser.parse_args(argv)

    payload = _read_nofollow(arguments.snapshot, "bound plan snapshot")
    # THE COMPLETE GRAMMAR, not just the first field (PR #63 recheck, P2). Taking `fields[0]` accepted a
    # record truncated to its digest alone, so both harnesses staged the snapshot and spent a full
    # 12-28 minute review — and `review-verdict.py`, which requires the canonical
    # `<digest>  <plan identity>\n`, then rejected the same record. A round guaranteed to be unusable
    # must fail here, in milliseconds, not after the reviewer has run. The pattern is the one
    # `review-verdict._PLAN_BINDING` enforces.
    record_bytes = _read_nofollow(arguments.record, "plan binding record")
    match = _PLAN_BINDING.fullmatch(record_bytes)
    if match is None:
        sys.exit(
            "stage-bound-plan: the plan binding record is malformed — expected "
            f"'<64 hex digits>  <plan path>' and a newline: {arguments.record}"
        )
    expected = match.group(1).decode("ascii")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        sys.exit(
            "stage-bound-plan: the bound plan snapshot does not match its recorded digest — "
            f"refusing to stage substituted bytes: {arguments.snapshot} hashes {actual[:12]}…, "
            f"{arguments.record} records {expected[:12]}…"
        )

    _stage_no_follow(arguments.tree, arguments.rel, payload)
    print(actual)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
