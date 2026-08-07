#!/usr/bin/env python3
"""Authenticate the bound prompt snapshot and stage it into a disposable review checkout.

WHY THIS IS SHARED AND NOT INLINE IN EACH HARNESS
Both isolation harnesses did this with `sed "s#$REPO#$TREE#g"` plus an inline python guard-prepend.
Two independent defects came out of that (PR #63 recheck):

  * NO AUTHENTICATION. `bind-prompt.py` writes `<transcript>.prompt` (the O_EXCL snapshot) and
    `<transcript>.promptsha256` (its digest), but the staging path re-read the snapshot NAME and never
    compared it to the recorded digest. A same-account process that rewrote `.prompt` after the binder
    returned and restored it before synthesis had the reviewer read substituted instructions while
    `review-verdict` later hashed the restored bytes and accepted them. The post-run `PROMPT_TREE_SHA`
    check does not close this: it anchors the already-substituted copy inside the tree.
  * THE `sed` EXPRESSION WAS ASSEMBLED FROM A PATH. A checkout whose path contains the `#` delimiter
    made the expression invalid — `sed: bad flag in substitute command` — and every capture aborted
    with an empty prompt. Reproduced from a checkout named `repo#x`. Regex metacharacters and
    backslashes in the path could likewise change the match rather than break it loudly.

Doing it in one place means the codex and gemini arms cannot drift apart again, which is the failure
mode that left the codex arm reading the live plan for a whole release.

WHAT IT GUARANTEES
  1. The snapshot is read ONCE through an `O_NOFOLLOW` descriptor and refused unless it hashes to the
     digest `<transcript>.promptsha256` records.
  2. The repository path is replaced by the tree path as a LITERAL BYTE substring — no regex, no
     delimiter, no escaping to get wrong — and the result is refused if any reference survives.
  3. The optional read-only guard is prepended to the authenticated body (read before write, so a
     truncating open cannot yield a guard-only prompt).
  4. The result is written through a no-follow descriptor walk, so a symlink materialized in the
     detached checkout is removed as a link rather than written through.

Prints the sha256 of the staged bytes, which the caller uses as its post-run basis anchor.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys

READ_ONLY_GUARD = (
    "READ-ONLY REVIEW — CONSTRAINT, NOT A TASK. You have READ access only: do NOT create, modify, "
    "delete or move any file, and do NOT implement any part of the plan. Producing the written "
    "review demanded by the instructions that follow is your ONLY deliverable. If you find "
    "yourself editing a file, stop — that is a failed review.\n"
    "The full task follows immediately below; read on.\n\n"
)


def _refuse(message: str):
    print(f"stage-prompt: {message}", file=sys.stderr)
    raise SystemExit(1)


def _read_nofollow(path: str, label: str) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        _refuse(f"cannot read the {label}: {path}: {error}")
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            _refuse(f"the {label} is not a regular file: {path}")
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
    """Write `payload` to tree_root/rel without traversing ANY symlink component."""
    components = [c for c in rel.split("/") if c and c != "."]
    if not components or ".." in components:
        _refuse(f"refusing an unsafe staging path: {rel}")
    dir_fd = os.open(tree_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in components[:-1]:
            try:
                os.mkdir(component, 0o755, dir_fd=dir_fd)
            except FileExistsError:
                pass
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = next_fd
        leaf = components[-1]
        try:
            os.unlink(leaf, dir_fd=dir_fd)
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
    parser.add_argument("--snapshot", required=True, help="the bound <transcript>.prompt snapshot")
    # REQUIRED. The comment below claimed a missing record was refused; the code merely skipped the
    # check, so the caller could authenticate or not by omitting a flag — and both harnesses did
    # exactly that when the sidecar was absent (PR #63 recheck, P1).
    parser.add_argument("--record", required=True,
                        help="<transcript>.promptsha256 to authenticate the snapshot against")
    parser.add_argument("--tree", required=True, help="the disposable checkout root")
    parser.add_argument("--rel", required=True, help="path under the tree to stage the prompt at")
    parser.add_argument("--repo", required=True, help="repository path to replace (literal bytes)")
    parser.add_argument("--guard", action="store_true", help="prepend the read-only guard")
    parser.add_argument("--min-bytes", type=int, default=0, help="refuse an assembled prompt below this")
    parser.add_argument("--max-bytes", type=int, default=0,
                        help="refuse an assembled prompt above this (the codex arm's argv cap)")
    arguments = parser.parse_args(argv)

    payload = _read_nofollow(arguments.snapshot, "bound prompt snapshot")

    # AUTHENTICATE BEFORE TRANSFORMING. The digest names the bytes the binder validated; everything
    # below operates on those bytes or refuses. A missing record is refused rather than skipped —
    # "absent means unchecked" is the fail-open this whole family of bindings exists to close.
    fields = _read_nofollow(arguments.record, "prompt binding record").decode("utf-8", "replace").split()
    if not fields:
        _refuse(f"the prompt binding record is empty: {arguments.record}")
    expected = fields[0]
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        _refuse(
            "the bound prompt snapshot does not match its recorded digest — refusing to review "
            f"substituted instructions: {arguments.snapshot} hashes {actual[:12]}…, "
            f"{arguments.record} records {expected[:12]}…"
        )

    # LITERAL BYTES, NOT A `sed` EXPRESSION. `bytes.replace` has no delimiter to collide with and no
    # metacharacters to escape, so a repository path containing `#`, a backslash or a regex character
    # is substituted correctly instead of breaking or mis-matching.
    repo = os.fsencode(arguments.repo)
    tree = os.fsencode(arguments.tree)
    if repo:
        payload = payload.replace(repo, tree)
        # THE CHECK LOOKS AT THE RESIDUE, NOT THE WHOLE PAYLOAD (PR #63 recheck, P2). When `TMPDIR`
        # points inside the checkout — which both harnesses honour, so it is a configuration, not an
        # exotic state — the scratch worktree lands beneath the repository and the REPLACEMENT value
        # itself contains the repository path (`<repo>/tmp.x/tree`). Scanning the rewritten payload for
        # `repo` then found the bytes this substitution had just INSERTED and aborted every otherwise
        # valid review, after its transcript had already been allocated. Reproduced.
        #
        # Removing the inserted `tree` occurrences leaves exactly the references the substitution did
        # not reach; `repo` surviving THERE is the failure this guard names.
        #
        # HONEST ABOUT REACHABILITY: `bytes.replace` is TOTAL, so with the inserted occurrences
        # discounted this can no longer fire for its stated cause — a reference the substitution missed
        # is one spelled differently (through a symlink, `..`, a trailing slash), and such a reference
        # does not contain `repo` literally, so neither form of the check ever saw it. The whole-payload
        # version could therefore only ever fire on its own substitution, which is exactly the false
        # refusal that was reported. It is kept as a cheap invariant against a future non-total
        # rewrite, NOT presented as an active defence, and no test claims to exercise it — a test that
        # cannot fail is not evidence.
        if repo in payload.replace(tree, b""):
            _refuse("the prompt still references the real worktree after rewriting")

    if arguments.guard:
        # Read-then-write: the body is already in memory, so there is no truncating open to evaluate
        # before the read — the bug that once produced a guard-only prompt and wasted two rounds.
        if not payload.strip():
            _refuse(f"refusing to write a guard-only prompt: {arguments.snapshot} is empty")
        payload = READ_ONLY_GUARD.encode("utf-8") + payload

    if arguments.min_bytes and len(payload) < arguments.min_bytes:
        _refuse(f"assembled prompt is only {len(payload)} bytes — truncated")
    # The codex arm hands the assembled prompt to `codex exec` as ONE argv element, and Linux caps a
    # single argument at `MAX_ARG_STRLEN` (128 KiB) whatever `ARG_MAX` says. Without this the `execvp`
    # fails with E2BIG after a leaf has been reserved and a worktree built (PR #63 recheck).
    if arguments.max_bytes and len(payload) > arguments.max_bytes:
        _refuse(
            f"assembled prompt is {len(payload)} bytes, over the {arguments.max_bytes}-byte limit — "
            "the reviewer receives it as a single argument, which Linux caps at 128 KiB. Shorten the "
            "prompt or reference files instead of inlining them."
        )

    _stage_no_follow(arguments.tree, arguments.rel, payload)
    print(hashlib.sha256(payload).hexdigest())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
