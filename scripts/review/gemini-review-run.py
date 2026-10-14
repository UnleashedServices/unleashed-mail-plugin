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
        "-o",
        "json",
        "-p",
        prompt,
    ]
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, check=False
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
    answered = sorted(str(m)[:80] for m in models) if isinstance(models, dict) else []
    if answered != [args.model]:
        return _fail(
            f"answered by {answered!r}, not {args.model!r}. A fallback or routed model is not the reviewer the "
            "gate records; the round is not a review."
        )
    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        return _fail("the CLI returned no response text")
    sys.stdout.write(response if response.endswith("\n") else response + "\n")
    return 0


def _fail(reason: str, status: int = 4) -> int:
    """Report a refused run on ONE line of fixed text (no newline can enter it), and return its status."""
    print(
        "GEMINI ARM FAILED — " + reason.replace("\n", " ").replace("\r", " "),
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
