#!/usr/bin/env python3
"""Prove an operand is a non-symlink regular file inside this repository — one implementation.

WHY THIS IS SHARED AND NOT COPIED
Two model-invocable entrypoints feed caller-chosen operands to an external reviewer CLI, and each was
found separately: `capture-*-review.sh`'s prompt (deep review, P1 — closed by `bind-prompt.py`) and
`audit-codex.sh`'s file list (PR #63 recheck, P1 — `/etc/passwd` was accepted and sent verbatim, and
`$*` also flattened the operands into one string, so argument boundaries were lost too). The second was
written in the same batch as the fix for the first and did not inherit it. A containment rule that
lives in one script is a rule the next entrypoint will not have.

WHAT "CONTAINED" MEANS HERE
Non-symlink, regular, non-empty, no control characters in the operand, and resolving beneath the
PHYSICAL repository root. The root is `realpath` of the working directory, matching
`resolve-plan-gate.sh`'s anchor: a symlinked subdirectory must not be able to launder its own target,
which is the bypass that guard was fixed for four times.

This is not a sandbox. It bounds WHICH FILE an operand can name; it does not bound what the reviewer
does with the bytes. `-s read-only` likewise prevents writes, not disclosure to a third party.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys

TOOL = "containment"


def refuse(reason: str):
    print(f"{TOOL}: {reason}", file=sys.stderr)
    raise SystemExit(1)


def repository_root() -> str:
    """The physical directory every operand must live beneath."""
    return os.path.realpath(os.getcwd())


def _control_characters(value: str) -> bool:
    """True if the operand carries anything that would break a line-oriented handoff or a shell.

    Newlines matter concretely: the caller emits one repo-relative path per line, so a filename with an
    embedded newline would forge an extra operand. Rejecting the whole control range is cheaper than
    reasoning about which ones are survivable, and no legitimate path in this repo needs them.
    """
    return any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)


def contained_regular_file(path: str, label: str) -> str:
    """Return `path`'s realpath after proving it is a non-symlink regular file inside the repo."""
    if _control_characters(path):
        refuse(f"{label} contains control characters: {path!r}")
    if os.path.islink(path):
        refuse(f"{label} is a symbolic link, which could point anywhere: {path}")
    try:
        metadata = os.lstat(path)
    except OSError as error:
        refuse(f"{label} is unreadable: {path}: {error}")
    if not stat.S_ISREG(metadata.st_mode):
        refuse(f"{label} is not a regular file: {path}")
    if metadata.st_size == 0:
        refuse(f"{label} is EMPTY: {path}")

    root = repository_root()
    real = os.path.realpath(path)
    if real != root and not real.startswith(root + os.sep):
        refuse(
            f"{label} is outside the repository and will not be read: {path} "
            f"(resolved to {real}, which is not beneath {root})"
        )
    return real


def main(argv=None) -> int:
    """`containment.py --label L OPERAND...` -> one repo-relative path per line, or exit 1.

    Emitting repo-relative paths rather than echoing the operands is deliberate: the caller then builds
    its prompt from THIS output, so an operand that was accepted in one form cannot be sent in another.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="operand")
    parser.add_argument("--tool", default="containment")
    parser.add_argument("operands", nargs="+")
    arguments = parser.parse_args(argv)

    global TOOL
    TOOL = arguments.tool

    root = repository_root()
    for operand in arguments.operands:
        real = contained_regular_file(operand, arguments.label)
        print(os.path.relpath(real, root))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
