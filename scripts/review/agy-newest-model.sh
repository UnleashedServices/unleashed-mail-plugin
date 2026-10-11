#!/usr/bin/env bash
# Print the newest gemini flash-high model `agy models` lists, or fail closed (COREDEV-2875 §2.1).
#
# WHY RUN TIME, NOT A PIN. The gemini arm pinned a 3.6 flash-high model while `agy models` already listed
# 3.7 and 3.8 above it: a pin goes stale silently. So every agy launch the plugin ships resolves its model
# here, and an explicit MODEL (the capture wrapper's sixth operand) still wins over this.
#
# ONLY THE FLASH-HIGH FAMILY. `gemini-3.1-pro-high` failed to emit a parseable verdict in 5 of 6 rounds
# (isolated-agy-review.sh's rationale comment). "Newest" means the newest of the family whose verdicts have
# been reliable, so pro, `-preview` and other vendors' ids are well-formed listing lines but never candidates.
#
# THE GUARANTEE, EXACTLY: the newest RECOGNIZED `gemini-<major>[.<minor>]-flash-high` in the listing agy
# returns NOW. A stale listing is agy's own state (plan §6). On success exactly one id is printed on stdout;
# on ANY failure the exit is non-zero and stdout is empty. There is no remembered fallback name: a dead name
# in a fallback fails exactly when the fallback is needed.
#
# FAIL CLOSED, NEVER SKIP. Each refusal below exists because skipping the odd thing could pick an OLDER model
# silently:
#   * stream contract: agy's output depends on what its streams are attached to. On a PTY it draws a spinner
#     and fuses `\r\x1b[K` to the FIRST entry -- the newest model (measured, agy 1.2.16). So stdout and stderr
#     are separate pipes, only stdout is parsed, and any byte other than printable ASCII, TAB or newline
#     fails the resolution. Nothing is stripped: a tolerant parse of that output selects the second newest.
#   * declared line shape: every non-empty line must be exactly `<id>TAB<label>`. A trailing space after the
#     newest id would otherwise drop it out of the suffix test and let 3.9 win (codex r6).
#   * an id ending in `-flash-high` in an unrecognized version form (`gemini-3.10.1-flash-high`) fails:
#     "newest" cannot be decided.
#   * bounded: `agy models` runs under a 60 s timeout. AGY_MODELS_TIMEOUT_S may only LOWER it (clamped to
#     1-60) so a test can prove the bound in seconds; a value that is not a finite number fails, because
#     NaN survives a bare min/max clamp and subprocess accepts a NaN timeout (measured).
set -u

exec python3 - <<'PY'
import math
import os
import re
import subprocess
import sys

SHAPE = re.compile(r"([\x21-\x7e]+)\t(.*)")          # <id>: printable ASCII except space and TAB
FLASH_HIGH = re.compile(r"gemini-(\d+)(?:\.(\d+))?-flash-high")
CEILING_S = 60.0


def fail(message):
    print(f"agy-newest-model: {message}", file=sys.stderr)
    sys.exit(1)


raw = os.environ.get("AGY_MODELS_TIMEOUT_S", "")
timeout = CEILING_S
if raw != "":
    try:
        value = float(raw)
    except ValueError:
        fail(f"AGY_MODELS_TIMEOUT_S={raw!r} is not a number")
    if not math.isfinite(value):
        fail(f"AGY_MODELS_TIMEOUT_S={raw!r} is not a finite number")
    timeout = min(max(value, 1.0), CEILING_S)

try:
    listing = subprocess.run(["agy", "models"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=timeout, check=False)
except subprocess.TimeoutExpired:
    fail(f"`agy models` did not finish within {timeout:g}s")
except OSError as error:
    fail(f"could not run `agy models`: {error}")
if listing.returncode != 0:
    fail(f"`agy models` exited {listing.returncode}")

for offset, byte in enumerate(listing.stdout):
    if not (0x20 <= byte < 0x7F or byte in (0x09, 0x0A)):
        fail(f"`agy models` printed a forbidden byte 0x{byte:02x} at offset {offset}; its stdout is not "
             "the measured <id>TAB<label> listing (a PTY-attached agy fuses escapes to the newest entry)")

best = None
for number, line in enumerate(listing.stdout.decode("ascii").split("\n"), 1):
    if not line:
        continue
    shape = SHAPE.fullmatch(line)
    if shape is None:
        fail(f"`agy models` line {number} is not <id>TAB<label>: {line!r}")
    ident = shape.group(1)
    if not ident.endswith("-flash-high"):
        continue
    version = FLASH_HIGH.fullmatch(ident)
    if version is None:
        fail(f"`agy models` lists {ident!r}, a flash-high id in an unrecognized version form, so the "
             "newest cannot be decided")
    key = (int(version.group(1)), int(version.group(2) or 0))
    if best is None or key > best[0]:
        best = (key, ident)

if best is None:
    fail("`agy models` lists no gemini-<major>[.<minor>]-flash-high model; pass one explicitly")
print(best[1])
PY
