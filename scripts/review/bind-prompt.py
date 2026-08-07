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


def _plan_references(prompt_bytes: bytes, root: str) -> "list[bytes]":
    """Every plan reference in the prompt, with root-anchored absolute paths matched WHOLE.

    THE TOKEN REGEX ALONE TRUNCATED AN ABSOLUTE PATH AT ANY CHARACTER OUTSIDE ITS ALLOWLIST — most
    plainly a SPACE in the repository's own path (`/Users/me/My Projects/repo/…`). The match began
    after the space, `prompt_disagreement` compared `Projects/repo/docs/…` against `docs/…`, and the
    documented capture flow was refused before either reviewer launched (PR #63 recheck, P1). The
    absolute normalization downstream never received a complete path to normalize — it works only on
    what this extraction hands it.

    So absolute references under THIS repository are matched first, anchored on the known root — the
    one string that makes an embedded space unambiguous — and masked out before the conservative token
    regex sweeps the remainder for relative and prose references. Masked with a SPACE rather than
    deleted, so the neighbouring bytes cannot fuse into a token nobody wrote.

    Residual, accepted: a reference that both spells the root DIFFERENTLY (e.g. through a symlink) and
    contains a space matches neither pattern. Space-free alternate spellings keep working exactly as
    before, via `realpath` in the caller.
    """
    anchored = re.compile(re.escape(os.fsencode(root)) + rb"/[^\n]*?_PLAN\.md")
    references = anchored.findall(prompt_bytes)
    references += _PLAN_REFERENCE.findall(anchored.sub(b" ", prompt_bytes))
    return references


def _plan_candidates(root: str, basename: str) -> "list[str]":
    """Every `*_PLAN.md` in the repo with this basename, repo-relative and sorted."""
    found = []
    for directory, _subdirs, files in os.walk(root):
        if ".git" in directory.split(os.sep):
            continue
        if basename in files:
            found.append(os.path.relpath(os.path.join(directory, basename), root))
    return sorted(found)


def prompt_disagreement(prompt_bytes: bytes, plan_relative: str, root: str) -> "str | None":
    """Refuse a prompt that asks for a review of a plan OTHER than the one being bound.

    THE FIRST DEFECT (PR #63 recheck, P1). The prompt and the plan were hashed INDEPENDENTLY, so a
    prompt whose text said `REVIEW TARGET: PLAN_B.md` bound cleanly to `--plan PLAN_A.md` and produced
    an APPROVE artifact for Plan A off a review of Plan B.

    THE SECOND (PR #63 recheck, same file). The first fix compared BASENAMES, so two plans sharing a
    name in different directories collided: a prompt explicitly targeting `docs/planning/b/SAME_PLAN.md`
    was accepted while `--plan` named `docs/planning/a/SAME_PLAN.md`. Reproduced. Comparing basenames
    is the same shortcut the artifact's own plan identity was fixed for in PR #41 — a name is not an
    identity, and this repo already had a plan-pair proving it.

    So references are compared as FULL normalized repo-relative paths. A bare basename carries no
    directory, so it is accepted only when exactly one plan in the repo answers to it AND that plan is
    the one being bound; otherwise it is ambiguous and refused rather than guessed.
    """
    # ABSOLUTE IN-REPO REFERENCES NORMALIZE TO THE SAME IDENTITY. `skills/gemini-review/SKILL.md`
    # requires the generated prompt to name the plan by its ABSOLUTE path, and an absolute string can
    # never equal the repo-relative `plan_normalized` — so this check refused the repository's own plan
    # while accepting its relative spelling, aborting the documented capture flow before the reviewer
    # ever launched (PR #63 recheck). A false refusal is not the safe direction here: it breaks the
    # gate for correct input, which is how guards get switched off.
    referenced = set()
    for match in _plan_references(prompt_bytes, root):
        reference = os.path.normpath(match.decode("utf-8", "replace"))
        if os.path.isabs(reference):
            resolved = os.path.realpath(reference)
            if resolved == root or resolved.startswith(root + os.sep):
                reference = os.path.relpath(resolved, root)
        referenced.add(reference)
    if not referenced:
        return (f"the prompt never names a plan, so nothing ties it to {plan_relative}. A review "
                "prompt must state the plan path it is reviewing.")

    plan_normalized = os.path.normpath(plan_relative)
    bare = {r for r in referenced if os.sep not in r}
    qualified = referenced - bare

    wrong = sorted(r for r in qualified if r != plan_normalized)
    if wrong:
        return (f"the prompt names {wrong}, not {plan_normalized} — refusing to bind a review of one "
                "plan to another")

    for basename in sorted(bare):
        candidates = _plan_candidates(root, basename)
        if len(candidates) > 1:
            return (f"the prompt refers to {basename!r} by name only, and this repository has "
                    f"{len(candidates)} plans with that basename ({candidates}). A basename is not an "
                    "identity — state the full repo-relative path.")
        if candidates and candidates[0] != plan_normalized:
            return (f"the prompt refers to {basename!r}, which resolves to {candidates[0]}, not to "
                    f"{plan_normalized}")
        if not candidates and basename != os.path.basename(plan_normalized):
            return f"the prompt refers to {basename!r}, which is not {plan_normalized}"

    if plan_normalized not in qualified and os.path.basename(plan_normalized) not in bare:
        return (f"the prompt names {sorted(referenced)}, not {plan_normalized} — refusing to bind a "
                "review of one plan to another")
    return None


def _write_all(descriptor: int, payload: bytes, path: str) -> None:
    """Write EVERY byte, or refuse.

    `os.write` may return a short count without raising — a filesystem quota or an `RLIMIT_FSIZE` is
    enough. The previous code ignored the count and reported a successful binding, so a 5,023-byte
    prompt produced a 2,048-byte `.prompt` snapshot under a 2 KiB limit and `bind-prompt.py` exited 0
    (PR #63 recheck, reproduced). That truncated snapshot still clears the Gemini arm's 1,000-byte
    floor, so a reviewer consumes a cut-off prompt and only the digest check downstream notices —
    after a full review round has been spent. `allocate-transcript.sh` already loops for its launch
    records; this is the same discipline, applied where it was missing.
    """
    written = 0
    try:
        while written < len(payload):
            count = os.write(descriptor, payload[written:])
            if count <= 0:
                raise OSError(f"wrote {count} bytes")
            written += count
    except OSError as error:
        # BOTH shapes, because the platforms differ and the outcome must not. A quota can surface as a
        # SHORT COUNT (the reviewer's reproduction) or as `EFBIG` (macOS, reproduced here under a 2 KiB
        # `RLIMIT_FSIZE`). Either way a partial sidecar is left on disk, and a truncated `.prompt` still
        # clears the Gemini arm's 1,000-byte floor — so a reviewer would consume a cut-off prompt and
        # only the digest check would notice, a full round later. Remove it: a binding that names bytes
        # nobody stored is worse than no binding, which fails closed.
        try:
            os.unlink(path)
        except OSError:
            pass
        _refuse(f"could not write {path} in full ({written} of {len(payload)} bytes: {error}) — the "
                "partial sidecar was removed rather than left to describe bytes that were never stored")


def write_sidecar_bytes(path: str, payload: bytes) -> None:
    """Create `path` 0600 with raw bytes, refusing to follow a symlink and refusing to overwrite.

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
        _write_all(descriptor, payload, path)
    finally:
        os.close(descriptor)


def write_sidecar(path: str, text: str) -> None:
    """`write_sidecar_bytes` for text — one encoding, one writer, one short-write guard."""
    write_sidecar_bytes(path, text.encode("utf-8"))


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
    # NO NUL BYTES. The capture helpers hand the snapshot to the reviewer through `$(cat …)`, and Bash
    # command substitution SILENTLY DELETES NULs — so the bytes validated here and the bytes the
    # reviewer receives are different strings. Reproduced: a prompt naming `A_PLAN.md` normally while
    # spelling its instruction as `B_PL\0AN.md` bound cleanly against A, because the agreement check
    # below sees a token that is not a plan name at all, and Codex then received the joined
    # `B_PLAN.md` — a review of B supporting A's approval (PR #63 recheck, P1).
    #
    # Refused at the SOURCE rather than escaped at each call site: a review prompt containing a NUL is
    # never legitimate, and every transport added later would otherwise need its own defence.
    if b"\x00" in prompt_bytes:
        _refuse(
            f"prompt contains a NUL byte, which shell command substitution deletes — the reviewer "
            f"would receive different bytes than are being bound: {arguments.prompt}"
        )
    disagreement = prompt_disagreement(prompt_bytes, plan_relative, root)
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
    # ONE read of the plan, and the bytes are KEPT. Hashing it and letting the harness re-open the path
    # left a window: another process could edit the plan after this digest and restore it before
    # synthesis, so the reviewer saw transient bytes while the sidecar and the final plan digest both
    # described the restored ones. The harness's `cmp` did not close it — it re-opened the same mutable
    # source, confirming only that the copy matched at copy time (PR #63 recheck, P1).
    #
    # `<transcript>.planbytes` is the plan exactly as hashed. The harness stages THAT, so the bytes the
    # reviewer reads and the bytes the binding attests to are the same object, not two reads of a name.
    plan_bytes = read_nofollow(plan)
    write_sidecar_bytes(arguments.transcript + ".planbytes", plan_bytes)
    write_sidecar(
        arguments.transcript + ".plan",
        f"{hashlib.sha256(plan_bytes).hexdigest()}  {plan_relative}\n",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
