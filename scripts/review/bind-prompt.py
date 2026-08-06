#!/usr/bin/env python3
"""Validate a review prompt, and bind it and the plan to the allocated transcript.

Three jobs that must not be split, because each one's failure mode is the other's silent success:

1. **Contain the prompt.** The review skills are model-invocable and pre-approve
   `capture-*-review.sh *`, so the model chooses this operand. The capture helpers checked only
   `-r`/`-s`, which accepts `../secret` — and the helper then feeds those bytes to the reviewer CLI
   verbatim. Reproduced with an out-of-repo file and a Codex stub, which received the contents
   (deep review, P1). The prompt must be a NON-SYMLINK REGULAR FILE beneath the repository.

2. **Digest it.** Previously a `shasum`/`sha256sum` fork in shell, whose failure was unchecked.

3. **Write the sidecars with no-follow semantics.** The shell wrote `<transcript>.promptsha256` with a
   plain `>` redirect, so a same-account process that planted a symlink there first had the target
   truncated with the gate's privileges — in a file whose neighbours use `O_NOFOLLOW` for exactly that
   threat (deep review, P2).

The `.plan` sidecar is what makes the binding ENFORCEABLE rather than merely forensic:
`review-verdict.py write` refuses a per-run transcript whose recorded plan is not the plan being
gated. Without it, `.promptsha256` was written and never read by anything, and transcripts captured
for an unrelated ticket still produced `GATE OK — APPROVE` (deep review, P1).

Usage:
  bind-prompt.py --prompt PATH --transcript PATH --plan PATH

Exit: 0 bound · 1 refused, with a one-line reason on stderr. Nothing is written on refusal.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys


def _refuse(reason: str) -> "NoReturn":  # noqa: F821
    print("bind-prompt: " + reason, file=sys.stderr)
    raise SystemExit(1)


def repository_root() -> str:
    """The PHYSICAL directory the operands must live beneath.

    `realpath` of the working directory, matching `resolve-plan-gate.sh`'s containment anchor. The
    base is deliberately the resolved CWD rather than a resolved `docs/planning`-style subpath: a
    symlinked subdirectory must not be able to launder its own target, which is the bypass that
    guard was fixed for four times.
    """
    return os.path.realpath(os.getcwd())


def contained_regular_file(path: str, label: str) -> str:
    """Return `path`'s realpath after proving it is a non-symlink regular file inside the repo."""
    if os.path.islink(path):
        _refuse(f"{label} is a symbolic link, which could point anywhere: {path}")
    try:
        metadata = os.lstat(path)
    except OSError as error:
        _refuse(f"{label} is unreadable: {path}: {error}")
    if not stat.S_ISREG(metadata.st_mode):
        _refuse(f"{label} is not a regular file: {path}")
    if metadata.st_size == 0:
        _refuse(f"{label} is EMPTY: {path}")

    root = repository_root()
    real = os.path.realpath(path)
    if real != root and not real.startswith(root + os.sep):
        _refuse(
            f"{label} is outside the repository and will not be read: {path} "
            f"(resolved to {real}, which is not beneath {root})"
        )
    return real


def sha256_nofollow(path: str) -> str:
    """Digest via an O_NOFOLLOW descriptor, so the bytes hashed are the file that was validated."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    try:
        digest = hashlib.sha256()
        offset = 0
        while True:
            chunk = os.pread(descriptor, 65536, offset)
            if not chunk:
                return digest.hexdigest()
            offset += len(chunk)
            digest.update(chunk)
    finally:
        os.close(descriptor)


def write_sidecar(path: str, text: str) -> None:
    """Create `path` 0600, refusing to follow a symlink and refusing to overwrite.

    `O_EXCL` as well as `O_NOFOLLOW`: a sidecar that already exists belongs to another run, and
    silently overwriting it would destroy that run's binding.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        _refuse(f"binding sidecar already exists, refusing to overwrite: {path}")
    except OSError as error:
        _refuse(f"could not create binding sidecar: {path}: {error}")
    try:
        os.write(descriptor, text.encode("utf-8"))
    finally:
        os.close(descriptor)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--plan", required=True)
    arguments = parser.parse_args(argv)

    prompt = contained_regular_file(arguments.prompt, "prompt file")
    plan = contained_regular_file(arguments.plan, "plan file")

    root = repository_root()
    plan_relative = os.path.relpath(plan, root)
    write_sidecar(
        arguments.transcript + ".promptsha256",
        f"{sha256_nofollow(prompt)}  {os.path.relpath(prompt, root)}\n",
    )
    write_sidecar(
        arguments.transcript + ".plan",
        f"{sha256_nofollow(plan)}  {plan_relative}\n",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
