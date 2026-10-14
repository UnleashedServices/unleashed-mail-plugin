#!/usr/bin/env python3
"""Run one Gemini review through the `gemini` CLI and emit ONLY the reviewer's text (COREDEV-2887).

This is the reviewer COMMAND that `isolated-gemini-review.sh` (and `preflight-gemini.sh`) run under
`pty-capture.py`, so whatever it prints to stdout is the transcript. It exists for two reasons:

1. THE MODEL THAT ANSWERED IS ASSERTED. The `gemini` CLI can change model mid-session — automatic
   fallback (`activateFallbackMode`, session-only, never persisted) and plan-mode routing between Pro and
   Flash. A review the gate attributes to `gemini-3.1-pro-preview` must have been answered by it and by
   nothing else, so `-o json` is requested and `stats.models` must name exactly the requested model.
   Anything else — another model, an extra model, no stats, no JSON — exits 4 with the reason and prints
   NO review text, so no `VERDICT:` line can reach the transcript.
2. THE TRANSCRIPT STAYS THE REVIEWER'S TEXT. The JSON envelope is unwrapped and `response` is printed
   verbatim, so the harness's anchored `^VERDICT:` extraction, `review-verdict.py` and synthesis are
   unchanged.

The CLI is run with `--approval-mode plan` and the shipped deny policy, but NEITHER is the guarantee:
headless plan mode auto-approves `exit_plan_mode` and then switches to YOLO (plan §1 F4). Isolation —
the disposable checkout and the before/after fingerprints in the calling harness — is the guarantee.

3. NOTHING BUT VALIDATED RESPONSE TEXT REACHES THE TRANSCRIPT (codex, plan round 1, Q1). `pty-capture.py`
   records stdout AND stderr together, so forwarding the CLI's stderr let diagnostics — or anything the CLI
   printed there — supply an anchored `VERDICT:` line even when this adapter then refused the run. The CLI's
   stderr is written ONLY to `--diagnostics` (created exclusively, never followed through a symlink). This
   adapter's own failure lines are fixed text whose one embedded value is `repr()`-escaped, so no newline,
   and therefore no `^VERDICT:` line, can come from them.
4. A FAILURE THE CLI REPORTS INSIDE THE JSON IS A FAILURE (codex, plan round 1, Q1). gemini 0.64.0 can
   return normally with accumulated response text, model stats AND an `error` (e.g. INVALID_STREAM), so any
   non-empty `error` refuses the run before a byte of the response is printed.

NORMALIZATION, STATED: the transcript is `response` with a trailing newline ensured; `pty-capture.py` then
strips ANSI escape sequences and turns CRLF into LF. Nothing else is changed.

Usage: gemini-review-run.py --model M --policy FILE --diagnostics PATH -- <prompt text>
Exit:  the CLI's status when it fails · 4 the answering model could not be confirmed, or the output was
       not the expected JSON · 0 a confirmed review was printed
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404 — the reviewer CLI is run with a fixed argv list, never a shell
import sys

_REQUESTED = ""


def main() -> int:  # noqa: PLR0911 — one return per distinct, named failure reason
    """Run the review, assert the answering model, and print only the response text."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument(
        "--diagnostics",
        required=True,
        help="file for the CLI's stderr; created exclusively, never part of the transcript",
    )
    parser.add_argument("prompt", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    global _REQUESTED  # noqa: PLW0603 — every refusal names the model it was asked to confirm (codex, round 2)
    _REQUESTED = args.model
    prompt = " ".join(a for a in args.prompt if a != "--").strip()
    if not prompt:
        return _fail("no prompt was given")

    argv = [
        "gemini",
        "--skip-trust",  # the disposable checkout is untrusted; without this the CLI refuses (rc 55)
        "-m",
        args.model,
        "--approval-mode",
        "plan",
        "--policy",
        args.policy,
        # AN ALLOWLIST THAT ADMITS NOTHING: no configured MCP server — user, workspace or extension — is started.
        # The policy denies MCP tool CALLS; this stops the server PROCESS from being spawned at all, which a
        # policy cannot (gemini, plan round 2). The name cannot match a real server.
        "--allowed-mcp-server-names",
        "unleashed-mail-gate-review-no-mcp",
        "-o",
        "json",
        "-p",
        prompt,
    ]
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, check=False, env=_cli_env()
        )  # nosec B603 — fixed argv, no shell
    except FileNotFoundError:
        return _fail("the `gemini` CLI is not on PATH")
    if not _write_diagnostics(args.diagnostics, proc.stderr):
        return _fail(f"could not record the CLI's diagnostics at {args.diagnostics!r}")
    if proc.returncode != 0:
        return _fail(
            f"the gemini CLI exited {proc.returncode} (its stderr is in the diagnostics file)",
            proc.returncode,
        )

    try:
        data = json.loads(proc.stdout)
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
    # THE FULL IDENTITY IS COMPARED (codex, plan round 2, Q1): keys were truncated to 80 characters BEFORE the
    # comparison, so a requested 80-character id matched an answering `<id>-fallback`. Only the diagnostic
    # below is shortened.
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


def _cli_env() -> dict[str, str]:
    """The CLI's environment, with the session TRUSTED BEFORE settings load.

    gemini 0.64.0 loads settings before it parses arguments and excludes an untrusted workspace's settings, while
    `--skip-trust` only takes effect during argument parsing (codex, plan round 2). The staged routing-off workspace
    setting could therefore be ignored. `GEMINI_CLI_TRUST_WORKSPACE=true` — the CLI's own documented alternative —
    is read before settings, so the disposable checkout's `.gemini/settings.json` applies. The model assertion
    above remains the guarantee if it ever does not.
    """
    env = dict(os.environ)
    env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"
    return env


def _fail(reason: str, status: int = 4) -> int:
    """Report a refused run on ONE line of fixed text (no newline can enter it), and return its status."""
    print(
        f"GEMINI ARM FAILED [{_REQUESTED!r}] — "
        + reason.replace("\n", " ").replace("\r", " "),
        file=sys.stderr,
    )
    return status


def _write_diagnostics(path: str, text: str) -> bool:
    """Write the CLI's stderr to `path` through one exclusive, no-follow descriptor."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError:
        return False
    try:
        os.write(descriptor, (text or "").encode("utf-8", "replace"))
    except OSError:
        return False
    finally:
        os.close(descriptor)
    return True


if __name__ == "__main__":
    sys.exit(main())
