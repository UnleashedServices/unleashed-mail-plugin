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

Containment itself lives in `containment.py`, shared with `audit-codex.sh` — the recheck found the
same defect on that sibling entrypoint because this file's copy could not reach it.

Usage:
  bind-prompt.py --prompt PATH --transcript PATH --plan PATH

Exit: 0 bound · 1 refused, with a one-line reason on stderr. Nothing is written on refusal.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


import containment  # noqa: E402
from containment import contained_regular_file, refuse as _refuse, repository_root  # noqa: E402

# Own the diagnostic prefix: the shared module defaults to its own name, and a refusal that says
# `containment:` sends the reader to the wrong file.
containment.TOOL = "bind-prompt"


def read_nofollow(path: str) -> bytes:
    """Read the whole file through ONE O_NOFOLLOW descriptor and return the bytes.

    Returning the BYTES rather than a digest is the point. The caller then checks, snapshots and hashes
    the same in-memory copy, so there is no second open between the check and the use — which is
    exactly the window the recheck found downstream, where the helper re-`cat`ed the prompt by name
    after this program had already blessed it.
    """
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    try:
        chunks = []
        offset = 0
        while True:
            chunk = os.pread(descriptor, 65536, offset)
            if not chunk:
                return b"".join(chunks)
            offset += len(chunk)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


_PLAN_REFERENCE = re.compile(rb"[A-Za-z0-9_./-]*_PLAN\.md")


def prompt_disagreement(prompt_bytes: bytes, plan_relative: str) -> "str | None":
    """Refuse a prompt that asks for a review of a plan OTHER than the one being bound.

    THE DEFECT (PR #63 recheck, P1). The prompt and the plan were hashed INDEPENDENTLY. Nothing tied
    the prompt's content to the `--plan` operand, so a prompt whose text said `REVIEW TARGET: PLAN_B.md`
    bound cleanly to `--plan PLAN_A.md`, and `review-verdict.py write` produced an APPROVE artifact for
    Plan A off a review of Plan B. Both digests were correct; they were digests of the wrong pairing.

    The rule is symmetric on purpose: the prompt must name the plan it is bound to, AND must not name a
    different `*_PLAN.md`. Requiring only the first would accept a prompt that mentions both and asks
    about the other one.
    """
    referenced = {match.decode("utf-8", "replace") for match in _PLAN_REFERENCE.findall(prompt_bytes)}
    if not referenced:
        return (f"the prompt never names a plan, so nothing ties it to {plan_relative}. A review "
                "prompt must state the plan path it is reviewing.")
    plan_name = os.path.basename(plan_relative)
    if not any(reference == plan_relative or os.path.basename(reference) == plan_name
               for reference in referenced):
        return (f"the prompt asks about {sorted(referenced)}, not about {plan_relative} — refusing to "
                "bind a review of one plan to another")
    others = sorted(reference for reference in referenced
                    if os.path.basename(reference) != plan_name)
    if others:
        return (f"the prompt names other plans as well as {plan_relative}: {others}. A round reviews "
                "exactly one plan; the binding cannot say which one this transcript is evidence for.")
    return None


def write_sidecar_bytes(path: str, payload: bytes) -> None:
    """`write_sidecar` for raw bytes — the prompt snapshot must not be decoded and re-encoded."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        _refuse(f"binding sidecar already exists, refusing to overwrite: {path}")
    except OSError as error:
        _refuse(f"could not create binding sidecar: {path}: {error}")
    try:
        os.write(descriptor, payload)
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

    # ONE read. Everything below uses these bytes: the agreement check, the snapshot the reviewer will
    # actually be fed, and the digest recorded for it.
    prompt_bytes = read_nofollow(prompt)
    disagreement = prompt_disagreement(prompt_bytes, plan_relative)
    if disagreement is not None:
        _refuse(disagreement)

    # THE SNAPSHOT is what closes the other two halves of this finding. It is created O_EXCL beside the
    # transcript, so it inherits the transcript's UNIQUE RUN identity — where the prompt FILENAME is
    # only per-round, and two invocations sharing a ticket and round shared one file. And the capture
    # helper now feeds these held bytes instead of re-`cat`ing the caller's path, so replacing the
    # prompt after this program returns changes nothing the reviewer sees.
    write_sidecar_bytes(arguments.transcript + ".prompt", prompt_bytes)
    write_sidecar(
        arguments.transcript + ".promptsha256",
        f"{hashlib.sha256(prompt_bytes).hexdigest()}  {os.path.relpath(prompt, root)}\n",
    )
    write_sidecar(
        arguments.transcript + ".plan",
        f"{hashlib.sha256(read_nofollow(plan)).hexdigest()}  {plan_relative}\n",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
