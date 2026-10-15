#!/usr/bin/env python3
"""A stand-in `gemini` CLI for the harness tests (COREDEV-2887): a test-supplied BASH body is the reviewer.

The plan gate's Gemini arm runs the `gemini` CLI with `-o json` through `scripts/review/gemini-review-run.py`, which
accepts only a JSON envelope whose `stats.models` names exactly the requested model. The fixtures written for the
retired `agy` arm are bash bodies that print the review as plain text. This shim lets each of them keep its body:
copy it onto PATH as `gemini`, and point `GEMINI_SHIM_BODY` at the body.

- The body runs with `tree` (the CLI's working directory, which the harness makes the disposable checkout) and
  `prompt` (the path after "Read and follow ") in its environment — the two things the `agy` bodies parsed from
  `--add-dir` and `-p`.
- Its stdout becomes `response`, and `stats.models` names exactly the `-m` model, so the adapter's assertion
  passes and the transcript is the body's text.
- Its stderr is inherited: the adapter's diagnostics file, never the transcript.
- A non-zero body status is the CLI's status, with no JSON, as a failing CLI behaves.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 — a test fixture running a test-supplied body
import sys
from pathlib import Path

_PREFIX = "Read and follow "


def main() -> int:
    """Run the body as the reviewer and wrap its stdout as the CLI's JSON output."""
    argv = sys.argv[1:]
    model = argv[argv.index("-m") + 1] if "-m" in argv else ""
    prompt = argv[argv.index("-p") + 1] if "-p" in argv else ""
    env = dict(os.environ)
    env["tree"] = str(Path.cwd())
    env["prompt"] = prompt.removeprefix(_PREFIX)
    proc = subprocess.run(  # nosec B603 B607 — the fixture's own body, run by bash
        ["bash", os.environ["GEMINI_SHIM_BODY"]],
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return proc.returncode
    sys.stdout.write(
        json.dumps({"response": proc.stdout, "stats": {"models": {model: {}}}})
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
