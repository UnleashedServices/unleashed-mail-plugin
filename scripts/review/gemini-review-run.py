#!/usr/bin/env python3
"""Run one Gemini review through the `gemini` CLI and emit ONLY the reviewer's text (COREDEV-2887).

This is the reviewer COMMAND that `isolated-gemini-review.sh` (and `preflight-gemini.sh`) run under
`pty-capture.py`, so whatever reaches the PTY is the transcript. The transcript is EXACTLY ONE OF TWO
THINGS: the validated, normalized response text, or NOTHING.

1. THE MODEL THAT ANSWERED IS ASSERTED. The `gemini` CLI can change model mid-session — automatic
   fallback (`activateFallbackMode`, session-only, never persisted) and plan-mode routing between Pro and
   Flash. A review the gate attributes to the requested model must have been answered by it and by
   nothing else, so `-o json` is requested and `stats.models` must name exactly the requested model,
   compared as complete strings (codex, plan round 2, Q1: a truncated comparison let `<id>-fallback`
   pass for an 80-character id).
2. A FAILURE THE CLI REPORTS INSIDE THE JSON IS A FAILURE (codex, plan round 1, Q1). gemini 0.64.0 can
   return normally with accumulated response text, model stats AND an `error` (e.g. INVALID_STREAM), so
   any non-empty `error` refuses the run before a byte of the response is printed.
3. NOTHING BUT THE VALIDATED RESPONSE REACHES THE PTY (codex, plan round 1, Q1; revision 4). `pty-capture.py`
   records stdout AND stderr together, so ANY stderr text — the CLI's diagnostics, this adapter's own
   refusals, even a Python traceback — would be transcript. The diagnostics file is therefore opened
   FIRST, through one exclusive, no-follow descriptor, and made this process's stderr before the CLI is
   launched. The CLI inherits it. A refused run therefore leaves the transcript EMPTY, which every layer
   downstream already treats as MISSING (`review-verdict.py write`: "EMPTY and therefore MISSING"), rather
   than a non-empty line that only the synthesizer's reading kept from counting.
4. A PRE-EXISTING DIAGNOSTICS ENTRY REFUSES THE RUN BEFORE THE CLI STARTS, so no review (and no quota) is
   spent on a round that cannot be recorded. Nothing is written anywhere in that case; the harness checks
   for the entry first and is the one that names it.
5. NO MCP SERVER IS STARTED, from any source (codex, plan round 3, Q1). `--allowed-mcp-server-names` is an
   exact-name allowlist, so a FIXED sentinel admitted any server configured under that very name (plan §1
   F13 E, observed). The name is generated per run from 128 random bits, after every configuration source is
   already fixed, so no configured server can carry it. An EMPTY allowlist is no fix: it means "unrestricted".
6. NO ENVIRONMENT FILE BUT THE OPERATOR'S IS LOADED (codex, plan round 3, Q1). The CLI walks up from its
   working directory and loads the first `.gemini/.env` or `.env` it finds, before falling back to the home
   directory's. A disposable checkout under a repository-local `TMPDIR` would let a committed ancestor file
   set the reviewer's environment (endpoint, credentials, flags). The same walk runs here, from this
   process's working directory — which IS the CLI's — and any file it reaches that is not in `$HOME` refuses
   the run before the CLI starts.

NORMALIZATION, STATED: CRLF and lone CR become LF, and a trailing newline is ensured; `pty-capture.py` then
strips ANSI escape sequences and removes the CR the PTY adds before each LF (codex, plan round 2).

Usage: gemini-review-run.py --model M --policy FILE --diagnostics PATH -- <prompt text>
Exit:  the CLI's status when it fails · 4 the diagnostics file could not be created, the answering model
       could not be confirmed, or the output was not the expected JSON · 0 a confirmed review was printed
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess  # nosec B404 — the reviewer CLI is run with a fixed argv list, never a shell
import sys
import threading
from pathlib import Path

_REQUESTED = ""
# The largest JSON envelope accepted from the CLI. A plan review's response is tens of kilobytes; 16 MiB is far
# above any real one and far below what would strain the host.
_STDOUT_CAP = 16 * 1024 * 1024
# The most the CLI may write to the diagnostics file. Its stderr is a few lines; this only stops a runaway.
_STDERR_CAP = 16 * 1024 * 1024


def main() -> int:  # noqa: PLR0911, PLR0912 — one per named refusal
    """Run the review, assert the answering model, and print only the response text."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument(
        "--diagnostics",
        required=True,
        help="file for every stderr byte; created exclusively, never part of the transcript",
    )
    parser.add_argument("prompt", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    global _REQUESTED  # noqa: PLW0603 — every refusal names the model it was asked to confirm (codex, round 2)
    _REQUESTED = args.model

    if not _redirect_stderr(args.diagnostics):
        return 4  # SILENT ON PURPOSE: any text here would reach the transcript (item 4 above)

    # Only a LEADING `--` is the separator; a later `--` belongs to the prompt (PR #124 review).
    prompt_args = args.prompt[1:] if args.prompt[:1] == ["--"] else args.prompt
    prompt = " ".join(prompt_args).strip()
    if not prompt:
        return _fail("no prompt was given")
    foreign = _foreign_env_file(Path.cwd())
    if foreign is not None:
        return _fail(
            f"the CLI would load the environment file {str(foreign)!r}, which is not the operator's; refusing to let it "
            "configure the reviewer"
        )

    cli = _resolve_cli(Path.cwd())
    if cli is None:
        return _fail(
            "no executable `gemini` CLI on PATH outside the reviewed checkout (relative PATH entries are skipped)"
        )
    argv = [
        cli,
        "--skip-trust",  # the disposable checkout is untrusted; without this the CLI refuses (rc 55)
        "-m",
        args.model,
        "--approval-mode",
        "plan",
        "--policy",
        args.policy,
        # AN ALLOWLIST THAT ADMITS NOTHING (item 5): no configured MCP server — user, workspace or extension —
        # is started. The policy denies MCP tool CALLS; this stops the server PROCESS from being spawned at all,
        # which a policy cannot (plan §1 F13: C against Cp). A per-run random name, because a fixed one is a name
        # a server can be configured under (F13 E).
        "--allowed-mcp-server-names",
        "unleashed-mail-no-mcp-" + secrets.token_hex(16),
        # NO EXTENSIONS (PR #124 review, P1). Without this option the CLI activates every installed extension, and
        # an extension's context and hooks run outside the deny policy's decision path. `none` is the CLI's own
        # spelling for "disable all"; verified on 0.64.0 (the ping still answers).
        "--extensions",
        "none",
        "-o",
        "json",
        "-p",
        prompt,
    ]
    try:
        # stderr is DRAINED into this process's stderr — the diagnostics file — under its own cap, so a runaway
        # CLI cannot fill the disk through it either (PR #124 review, P2).
        proc = subprocess.Popen(  # nosec B603 — fixed argv, no shell
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_cli_env()
        )
    except FileNotFoundError:
        return _fail("the `gemini` CLI is not on PATH")
    except (
        OSError
    ) as launch_error:  # e.g. a `gemini` on PATH that is not executable (PR #124 review)
        return _fail(f"could not run the `gemini` CLI: {launch_error}")
    stderr_capped = threading.Event()
    drain = threading.Thread(
        target=_drain_stderr, args=(proc, stderr_capped), daemon=True
    )
    drain.start()
    output, overflowed = _read_bounded(proc)
    drain.join()
    if stderr_capped.is_set():
        return _fail(
            f"the gemini CLI's diagnostics exceeded {_STDERR_CAP} bytes; it was stopped and nothing is a review"
        )
    if overflowed:
        return _fail(
            f"the gemini CLI's output exceeded {_STDOUT_CAP} bytes; it was stopped and nothing is a review"
        )
    if proc.returncode != 0:
        return _fail(
            f"the gemini CLI exited {proc.returncode} (its stderr is above, in this file)",
            proc.returncode,
        )

    try:
        data = json.loads(output.decode("utf-8", "replace"))
    except ValueError:
        return _fail("the CLI's output was not JSON; nothing is recorded as a review")
    if not isinstance(data, dict):
        return _fail("the CLI's JSON was not an object")
    error = data.get("error")
    if error:
        kind = error.get("type") if isinstance(error, dict) else type(error).__name__
        return _fail(
            f"the CLI reported an error inside its JSON ({str(kind)[:80]!r}); the response is not a review"
        )
    stats = data.get("stats")
    models = stats.get("models") if isinstance(stats, dict) else None
    # THE FULL IDENTITY IS COMPARED (codex, plan round 2, Q1). Only the diagnostic below is shortened.
    answered = sorted(str(m) for m in models) if isinstance(models, dict) else []
    if answered != [args.model]:
        return _fail(
            f"answered by {[m[:80] for m in answered]!r}, not {args.model!r}. A fallback or routed model is not "
            "the reviewer the gate records; the round is not a review."
        )
    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        return _fail("the CLI returned no response text")
    # LINE ENDINGS NORMALIZED HERE, not left to the PTY (codex, plan round 2): a PTY turns CRLF into CRCRLF and
    # `pty-capture.py` removes only one CR, so CRLF reached the transcript. CRLF and lone CR become LF.
    response = response.replace("\r\n", "\n").replace("\r", "\n")
    sys.stdout.write(response if response.endswith("\n") else response + "\n")
    return 0


def _resolve_cli(cwd: Path) -> str | None:
    """The `gemini` the review runs: an ABSOLUTE executable on PATH, outside the reviewed checkout.

    A bare name resolves through PATH, so a `.` (or any relative) entry, or an absolute entry inside the
    checkout, would run a branch-committed `gemini` that prints a valid envelope naming the requested model
    (PR #124 review, P1). Such entries are skipped, and the first executable found elsewhere is run by path.
    """
    here = cwd.resolve()
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or not Path(entry).is_absolute():
            continue
        directory = Path(entry).resolve()
        if directory == here or here in directory.parents:
            continue
        candidate = directory / "gemini"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _drain_stderr(proc: subprocess.Popen[bytes], capped: threading.Event) -> None:
    """Copy the CLI's stderr into the diagnostics file (fd 2), stopping and killing the CLI past `_STDERR_CAP`."""
    if proc.stderr is None:  # stderr=PIPE always provides one
        return
    written = 0
    while True:
        chunk = os.read(proc.stderr.fileno(), 1 << 16)
        if not chunk:
            break
        if written + len(chunk) > _STDERR_CAP:
            capped.set()
            proc.kill()
            break
        os.write(2, chunk)
        written += len(chunk)
    proc.stderr.close()


def _read_bounded(proc: subprocess.Popen[bytes]) -> tuple[bytes, bool]:
    """Read the CLI's stdout to EOF, keeping at most `_STDOUT_CAP` bytes; past it, kill the CLI.

    A runaway CLI or endpoint must not grow this process without bound (PR #124 review, P2): the outer
    `pty-capture.py` sees nothing until the adapter prints, so its own capture limit could never fire.
    """
    if (
        proc.stdout is None
    ):  # stdout=PIPE always provides one; checked, not asserted (asserts vanish under -O)
        raise RuntimeError  # unreachable with stdout=PIPE; refusing beats reading nothing
    chunks: list[bytes] = []
    total = 0
    overflowed = False
    while True:
        chunk = os.read(proc.stdout.fileno(), 1 << 16)
        if not chunk:
            break
        total += len(chunk)
        if total > _STDOUT_CAP:
            overflowed = True
            proc.kill()
            break
        chunks.append(chunk)
    proc.stdout.close()
    proc.wait()
    return b"".join(chunks), overflowed


def _foreign_env_file(start: Path) -> Path | None:
    """The environment file the CLI's loader would pick from `start`, when it is not the operator's own.

    Mirrors gemini 0.64.0's `findEnvFile` for a trusted session: from `start` up to `/`, the first
    `<dir>/.gemini/.env`, else `<dir>/.env`, wins; if none exists, the loader falls back to `$HOME`'s. A
    file found AT `$HOME` while walking is the operator's, and the loader stops there too. Existence is
    tested without following symlinks, so a dangling link is refused rather than skipped.
    """
    home = os.environ.get("HOME", "")
    homes = {Path(home), Path(home).resolve()} if home else set()
    # `absolute()`, not `resolve()`: the loader uses Node's `path.resolve`, which does not follow symlinks.
    current = start.absolute()
    while True:
        for candidate in (current / ".gemini" / ".env", current / ".env"):
            if candidate.is_symlink() or candidate.exists():
                return None if current in homes else candidate
        if current.parent == current:
            return None
        current = current.parent


def _redirect_stderr(path: str) -> bool:
    """Create `path` through ONE exclusive, no-follow descriptor and make it this process's stderr (fd 2).

    Opened before the CLI is launched, so a pre-existing entry — a file, a FIFO, a symlink to a victim —
    refuses the run before any review happens, and is never written through.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError:
        return False
    sys.stderr.flush()
    os.dup2(descriptor, 2)
    os.close(descriptor)
    return True


# NOT INHERITED (PR #124 review, P1). `GEMINI_SYSTEM_MD` replaces the CLI's whole system prompt, and a RELATIVE
# value resolves from the reviewer's working directory — the reviewed checkout — so a branch could supply it; the
# gate always runs the built-in prompt. `GEMINI_CLI_IDE_*` would add an IDE's workspace folders as readable roots.
_DROPPED_ENV = frozenset({"GEMINI_SYSTEM_MD", "GEMINI_WRITE_SYSTEM_MD"})


def _cli_env() -> dict[str, str]:
    """The CLI's environment, with the session TRUSTED BEFORE settings load.

    gemini 0.64.0 loads settings before it parses arguments and excludes an untrusted workspace's settings,
    while `--skip-trust` only takes effect during argument parsing (codex, plan round 2; confirmed live, plan
    §1 F13 D). `GEMINI_CLI_TRUST_WORKSPACE=true` is read before settings, so the disposable checkout's
    `.gemini/settings.json` applies (F13 A). The model assertion above remains the guarantee if it ever does not.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in _DROPPED_ENV and not key.startswith("GEMINI_CLI_IDE_")
    }
    env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"
    return env


def _fail(reason: str, status: int = 4) -> int:
    """Report a refused run on ONE line, to stderr — the diagnostics file — and return its status.

    One line of fixed text whose embedded values are `repr()`-escaped, so the harness and the preflight can
    find it (`^GEMINI ARM FAILED`) and print it for the operator.
    """
    print(
        f"GEMINI ARM FAILED [{_REQUESTED!r}] — "
        + reason.replace("\n", " ").replace("\r", " "),
        file=sys.stderr,
    )
    return status


if __name__ == "__main__":
    sys.exit(main())
