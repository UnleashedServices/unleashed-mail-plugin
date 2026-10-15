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
   the run before the CLI starts. The operator's own file may set only credentials (PR #124 review): it loads
   AFTER every check here, so anything else it set would be unchecked.
7. NOTHING THE CLI LOADS RESOLVES FROM THE CHECKOUT (PR #124 review): a relative configuration path refuses the run,
   `NODE_OPTIONS`/`NODE_PATH` are not inherited, and the `gemini` that runs is a real file outside every reviewed
   tree — the working directory and each `--reviewed-root` — however PATH and symlinks reach it.

NORMALIZATION, STATED: CRLF and lone CR become LF, and a trailing newline is ensured; `pty-capture.py` then
strips ANSI escape sequences and removes the CR the PTY adds before each LF (codex, plan round 2).

Usage: gemini-review-run.py --model M --policy FILE [--reviewed-root DIR ...] --diagnostics PATH -- <prompt text>
       Run it as `python3 -I -B`: the working directory is the reviewed checkout, and `-I` keeps it (and
       `PYTHONPATH`) off the import path, so a committed `secrets.py` cannot stand in for the standard library.
Exit:  the CLI's status when it fails · 4 the diagnostics file could not be created, the answering model
       could not be confirmed, or the output was not the expected JSON · 0 a confirmed review was printed
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
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


def main() -> int:  # noqa: PLR0911, PLR0912, PLR0915 — one per named refusal
    """Run the review, assert the answering model, and print only the response text."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument(
        "--diagnostics",
        required=True,
        help="file for every stderr byte; created exclusively, never part of the transcript",
    )
    parser.add_argument(
        "--reviewed-root",
        action="append",
        default=[],
        help="a tree the reviewed branch controls (the live checkout); the `gemini` run may not resolve into it",
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
    trees = _reviewed_trees(Path.cwd(), args.reviewed_root)
    # A CONFIGURATION PATH MUST BE THE OPERATOR'S (PR #124 review, P1, twice). Each variable names a file or directory the
    # CLI reads its configuration from: a relative value resolves from its working directory — the checkout — and an
    # absolute one may still point INTO a reviewed tree, where the branch supplies the file.
    for name in _PATH_VARIABLES:
        value = os.environ.get(name, "")
        if value and not Path(value).is_absolute():
            return _fail(
                f"{name} is a relative path, which the CLI would resolve inside the reviewed checkout"
            )
        if value and _inside(Path(os.path.realpath(value)), trees):
            return _fail(
                f"{name} names a path inside a reviewed tree, which the branch controls"
            )
    env_file, foreign = _env_file(Path.cwd())
    if foreign:
        return _fail(
            f"the CLI would load the environment file {str(env_file)!r}, which is not the operator's; refusing to let "
            "it configure the reviewer"
        )
    if env_file is not None:
        keys = _env_file_keys(env_file)
        if keys is None:
            return _fail(
                f"the environment file {str(env_file)!r} the CLI would load could not be read as plain ASCII text, "
                "so the keys it would set cannot be confirmed"
            )
        unexpected = sorted(keys - _ENV_FILE_KEYS)
        if unexpected:
            return _fail(
                f"the CLI would load {str(env_file)!r}, which sets {[key[:80] for key in unexpected]!r}; a review "
                f"accepts only {sorted(_ENV_FILE_KEYS)!r} from an environment file — set anything else in the "
                "shell, where this adapter checks it"
            )

    resolved = _resolve_cli(trees)
    if resolved is None:
        return _fail(
            "no executable `gemini` CLI on PATH outside the reviewed trees (relative PATH entries are skipped)"
        )
    invoked, cli = resolved
    argv = [
        invoked,
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
        # THE CHECKED FILE RUNS, under the name it was found by (local Codex review, P2): `executable` is the real
        # file `_resolve_cli` checked, and argv[0] stays the PATH entry's `gemini`, because a tool-manager shim
        # (mise) is a symlink to one binary that chooses the tool from argv[0].
        proc = subprocess.Popen(  # nosec B603 — fixed argv, no shell
            argv,
            executable=cli,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_cli_env(),
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


def _resolve_cli(trees: list[Path]) -> tuple[str, str] | None:
    """The `gemini` the review runs: an ABSOLUTE executable on PATH whose real file is outside every reviewed tree.

    A bare name resolves through PATH, so a `.` (or any relative) entry, or an absolute entry inside the
    checkout, would run a branch-committed `gemini` that prints a valid envelope naming the requested model
    (PR #124 review, P1). Relative entries are skipped. Every candidate is then RESOLVED to its real file and skipped if
    that file is inside a reviewed tree — which covers an entry inside one and a `gemini` SYMLINKED into one alike (PR
    #124 review, P2) — and the real file is what runs, so the file checked is the file executed. `trees` comes from
    `_reviewed_trees`. Returns the PATH entry's `gemini` (the name it is invoked by) and that real file.
    """
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or not Path(entry).is_absolute():
            continue
        candidate = Path(os.path.realpath(Path(entry) / "gemini"))
        if _inside(candidate, trees):
            continue
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(Path(entry) / "gemini"), str(candidate)
    return None


def _reviewed_trees(cwd: Path, reviewed_roots: list[str]) -> list[Path]:
    """The trees the reviewed branch controls: the working directory (the disposable checkout) and each root given."""
    return [cwd.resolve(), *(Path(root).resolve() for root in reviewed_roots)]


def _inside(path: Path, trees: list[Path]) -> bool:
    """Whether `path` is one of `trees` or lies beneath one."""
    return any(path == tree or tree in path.parents for tree in trees)


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
        try:
            os.write(2, chunk)
        except OSError:
            # An unwritable diagnostics file (a full disk) must not end the drain: the CLI would then block on a
            # full pipe until the outer timeout. Stopping it fails the run (PR #124 review, Gemini).
            proc.kill()
            break
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


def _env_file(start: Path) -> tuple[Path | None, bool]:
    """The environment file the CLI's loader would pick from `start`, and whether it is FOREIGN (not the operator's).

    Mirrors gemini 0.64.0's `findEnvFile` for a trusted session: from `start` up to `/`, the first
    `<dir>/.gemini/.env`, else `<dir>/.env`, wins; if none exists, the loader falls back to the CLI's home
    directory's (`$GEMINI_CLI_HOME`, else `$HOME`). A file found AT `$HOME` while walking is the operator's, and
    the loader stops there too. Existence is tested without following symlinks while walking, so a dangling link
    is refused rather than skipped.
    """
    home = os.environ.get("HOME", "")
    homes = {Path(home), Path(home).resolve()} if home else set()
    # `absolute()`, not `resolve()`: the loader uses Node's `path.resolve`, which does not follow symlinks.
    current = start.absolute()
    while True:
        for candidate in (current / ".gemini" / ".env", current / ".env"):
            if candidate.is_symlink() or candidate.exists():
                return candidate, current not in homes
        if current.parent == current:
            break
        current = current.parent
    cli_home = os.environ.get("GEMINI_CLI_HOME") or home
    if cli_home:
        for candidate in (Path(cli_home) / ".gemini" / ".env", Path(cli_home) / ".env"):
            if candidate.exists():  # the loader's `existsSync` follows links
                return candidate, False
    return None, False


def _env_file_keys(path: Path) -> set[str] | None:
    """Every key the CLI's loader would read from `path`, or None if it is unreadable or not plain ASCII text.

    The loader's own pattern is run as-is, which reproduces its key set only where Python's `re` and JavaScript agree
    on every class the pattern uses. They agree on printable ASCII, tab and line breaks; elsewhere they do not (a
    leading byte-order mark is whitespace to JavaScript and not to Python, so it hid `GEMINI_SYSTEM_MD` from this
    scan while the CLI loaded it — PR #124 local review, P2, reproduced). So any other byte refuses.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not set(raw) <= _ENV_FILE_BYTES:
        return None
    text = raw.decode("ascii")
    return {
        match.group(1) for match in _DOTENV_LINE.finditer(re.sub(r"\r\n?", "\n", text))
    }


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
# `NODE_OPTIONS` and `NODE_PATH` load code into the CLI, which is a Node program: a relative `--require`/`--import`
# or `NODE_PATH` entry resolves from the checkout too (PR #124 review, P1: the Python form of the same class).
_DROPPED_ENV = frozenset(
    {"GEMINI_SYSTEM_MD", "GEMINI_WRITE_SYSTEM_MD", "NODE_OPTIONS", "NODE_PATH"}
)

# CONFIGURATION PATHS the CLI reads (0.64.0): its home (user settings, the home `.env`, user context and skills), the
# system settings and defaults, the trusted-folders file and the experiments file. Absolute values only.
_PATH_VARIABLES = (
    "GEMINI_CLI_HOME",
    "GEMINI_CLI_SYSTEM_SETTINGS_PATH",
    "GEMINI_CLI_SYSTEM_DEFAULTS_PATH",
    "GEMINI_CLI_TRUSTED_FOLDERS_PATH",
    "GEMINI_EXP",
)

# AN ENVIRONMENT FILE MAY SUPPLY ONLY CREDENTIALS (PR #124 review, P1). The CLI loads the operator's `.env` AFTER this
# adapter has checked the environment, and a file key it loads is in force for the whole session: a relative
# `GEMINI_SYSTEM_MD` there brought the dropped variable back, from the checkout. Rather than a list of dangerous names,
# the file may set only the four keys the CLI itself accepts from an UNTRUSTED workspace's `.env`
# (`AUTH_ENV_VAR_WHITELIST`); anything else belongs in the shell, where the checks above see it.
_ENV_FILE_KEYS = frozenset(
    {
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
    }
)
# The loader's own line pattern (dotenv, as bundled in gemini 0.64.0), so the keys found are the keys it loads —
# on the bytes below, where Python and JavaScript read the pattern alike (`_env_file_keys`).
_ENV_FILE_BYTES = frozenset(b"\t\n\r" + bytes(range(0x20, 0x7F)))
_DOTENV_LINE = re.compile(
    r"""(?:^|^)\s*(?:export\s+)?([\w.-]+)(?:\s*=\s*?|:\s+?)(\s*'(?:\\'|[^'])*'|\s*"(?:\\"|[^"])*"|\s*`(?:\\`|[^`])*`|[^#\r\n]+)?\s*(?:#.*)?(?:$|$)""",
    re.MULTILINE,
)


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
    # An unwritable diagnostics file must not turn a refusal into a traceback: the status still refuses the run.
    with contextlib.suppress(OSError):
        print(
            f"GEMINI ARM FAILED [{_REQUESTED!r}] — "
            + reason.replace("\n", " ").replace("\r", " "),
            file=sys.stderr,
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
