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

Usage: gemini-review-run.py --model M --policy FILE -- <prompt text>
Exit:  the CLI's status when it fails · 4 the answering model could not be confirmed, or the output was
       not the expected JSON · 0 a confirmed review was printed
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404 — the reviewer CLI is run with a fixed argv list, never a shell
import sys


def main() -> int:  # noqa: PLR0911 — one return per distinct, named failure reason
    """Run the review, assert the answering model, and print only the response text."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("prompt", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    prompt = " ".join(a for a in args.prompt if a != "--").strip()
    if not prompt:
        print("GEMINI ARM FAILED — no prompt was given", file=sys.stderr)
        return 4

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
        print("GEMINI ARM FAILED — the `gemini` CLI is not on PATH", file=sys.stderr)
        return 4
    # The CLI's own diagnostics stay visible to the operator, never in the transcript.
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print(
            f"GEMINI ARM FAILED — the gemini CLI exited {proc.returncode}",
            file=sys.stderr,
        )
        return proc.returncode

    try:
        data = json.loads(proc.stdout)
    except ValueError:
        print(
            "GEMINI ARM FAILED — the CLI's output was not JSON; nothing is recorded as a review",
            file=sys.stderr,
        )
        return 4
    if not isinstance(data, dict):
        print("GEMINI ARM FAILED — the CLI's JSON was not an object", file=sys.stderr)
        return 4
    stats = data.get("stats")
    models = stats.get("models") if isinstance(stats, dict) else None
    answered = sorted(models) if isinstance(models, dict) else []
    if answered != [args.model]:
        print(
            f"GEMINI ARM FAILED — answered by {answered or 'no recorded model'}, not {args.model!r}. "
            "A fallback or routed model is not the reviewer the gate records; the round is not a review.",
            file=sys.stderr,
        )
        return 4
    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        print("GEMINI ARM FAILED — the CLI returned no response text", file=sys.stderr)
        return 4
    sys.stdout.write(response if response.endswith("\n") else response + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
