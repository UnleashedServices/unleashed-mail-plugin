#!/usr/bin/env python3
"""Mechanical closure of the shell/Python redactor equivalence (COREDEV-2597 §4.5).

WHY THIS EXISTS
---------------
`redactor_fixture.py` is a list. Three of the nine divergence root causes found during the plan
review have UNBOUNDED generators, so a list is incomplete *by kind* — which is exactly why rounds 3
and 4 of the review each found more divergences than the previous round claimed existed (2 -> 5 ->
12). A static table cannot be the gate.

This module is the gate. It generates a large deterministic corpus, runs BOTH shipped
implementations over it, and asserts a single invariant:

    the ONLY inputs on which the two disagree are those the `_EMAIL` `@Nx` retina lookahead
    explains — everything else is byte-identical, and UNEXPLAINED == 0.

That converts *"did we find them all?"* into a checkable equivalence. It fails the moment either
implementation gains a behaviour the other does not have, which is precisely the statement "a new
root cause exists".

WHAT IT PROVES, AND WHAT IT DOES NOT
------------------------------------
It proves the equivalence holds *on this corpus, on this platform*. It is not a proof for all
strings. Two limits are deliberate and must stay documented rather than quietly assumed away:

  * PLATFORM. `sed`/`tr` behaviour differs between BSD (dev macOS) and GNU (CI Ubuntu), and one
    known root cause — `tr` aborting on invalid UTF-8 outside `LC_ALL=C` — *inverts* by platform.
    Run this on BOTH runners or the result is half a result.
  * INPUT DOMAIN. NUL bytes cannot cross `argv`, and the two sides have genuinely different input
    domains for invalid UTF-8 (bytes vs a decoded `str`). Those are out of scope here.

Usage:
    python3 redactor_model.py                # default corpus
    python3 redactor_model.py --count 40000  # the size the sweep used
    python3 redactor_model.py --seed 31337   # a different deterministic corpus
Exit 0 on equivalence, 1 on any UNEXPLAINED divergence.
"""
from __future__ import annotations

import argparse
import itertools
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import capture as C  # noqa: E402
import redactor_fixture as F  # noqa: E402

HOOK_IO = os.path.join(REPO, "scripts", "lib", "hook-io.sh")

# Tokens that trigger each shipped rule, plus near-misses that must NOT trigger it. The corpus is
# built by composing these, so every rule and every rule INTERACTION gets exercised — a per-rule
# corpus is what let the review miss cross-rule divergences for four rounds.
SEEDS = [
    # email + the retina exemption surface
    "nick@example.com", "a@b.co", "first.last+tag@sub.domain.org",
    "AppIcon@2x.png", "Icon@10x.PNG", "user@2x.png.example.com", "AppIcon@2X.png",
    "user@2xmail.com", "Icon@2x.heic", "Icon@3x.jpeg",
    # home paths
    "/Users/nick/x.swift", "/Users/nick", "/home/alice/y", "/Users/",
    "~alice/secrets", "~root/.ssh/id_rsa", "~alice", "~Copyable", "~Escapable",
    "~500ms", "~40/60", "~2x", "~_daemon/x", "~9lives/x", "~/Documents", "~a/~b/x",
    # secrets
    "sk-abcdefgh123", "pk_live_abcdefgh12345678", "sk-abcdefg", "sk-abcdefgh",
    "foo_sk-abcdefgh123", "orders_pk_customer_id_idx", "pk_abcdefgh-sk-ijklmnop",
    "OPENAI_KEY_sk-proj-abcdefgh12345678",
    # jwt / bearer / api key
    "eyJhbGciOiJIUzI1NiJ9", "eyJshort", "bearer " + "T" * 24, "Bearer " + "a" * 20,
    "bKarer " + "T" * 24, "api key: " + F.SECRET, "api_key=SECRETVALUE", "apikey:V" * 2,
    "API KEY : " + F.SECRET,
    # ordinary prose that the buggy rules used to corrupt
    "task-oriented", "risk-assessment", "disk-utilization", "desk-checking",
    "plain text", "", " ", "a", "café", "orders_pk_customer_id_idx",
]

# Perturbations. The whitespace set is the closed 23-codepoint difference between Python's `\s` and
# POSIX `[[:space:]]` under LC_ALL=C, plus ASCII separators, plus the three NOT-White_Space controls
# that must pass through untouched.
SEPARATORS = ["", " ", "\n", "\t", "\r", "\r\n", "  ", ":", "=", ",", "(", ")", '"', "-", "_", "/"]
PERTURB = F.UNICODE_WS + F.NOT_WS + [chr(0x212A), chr(0x0131), chr(0x017F), "é", "例"]


def shell_redact(value: str) -> str:
    return subprocess.run(
        ["bash", "-c", f'. "{HOOK_IO}"; hook_redact_pii "$1"', "_", value],
        capture_output=True, text=True,
    ).stdout


def shell_redact_batch(values: list[str]) -> list[str]:
    """One bash process for many inputs — spawning one per input is ~1000x slower and makes a
    40k-input corpus impractical, which is how a gate ends up "too slow to run" and gets skipped.

    NUL-separated on stdin, NUL-separated on stdout, so any input byte except NUL round-trips.
    """
    script = f'. "{HOOK_IO}"\nwhile IFS= read -r -d "" v; do printf "%s\\0" "$(hook_redact_pii "$v")"; done'
    payload = "".join(v + "\0" for v in values)
    out = subprocess.run(["bash", "-c", script], input=payload, capture_output=True, text=True).stdout
    parts = out.split("\0")[:-1]
    if len(parts) != len(values):  # pragma: no cover - defensive
        raise RuntimeError(f"batch desync: sent {len(values)}, got {len(parts)}")
    return parts


import re as _re

#: `_EMAIL` with the `@Nx` retina lookahead REMOVED and nothing else changed.
_EMAIL_NO_EXEMPTION = _re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _email_lookahead_explains(value: str, sh: str, py: str) -> bool:
    """True when the divergence is the ONE permanent exemption and nothing else.

    Classified by CONSTRUCTION: temporarily swap `capture._EMAIL` for the same pattern WITHOUT the
    retina lookahead, then call THE REAL `capture.redact_pii`. If it now matches the shell, the
    exemption is the whole explanation.

    THIS MUST CALL THE SHIPPED FUNCTION. An earlier version of this file re-implemented the
    pipeline inline, and that made the gate PARTIALLY INERT: mutating `redact_pii`'s body (reverting
    the sequential secret passes, or deleting the whitespace canonicalisation) changed the real
    output but not the re-implemented classifier, which then absorbed the divergence as "explained".
    Two of four deliberate regressions went undetected. Verified by re-running all four mutants
    after this change. Never reconstruct the pipeline here.
    """
    original = C._EMAIL
    try:
        C._EMAIL = _EMAIL_NO_EXEMPTION
        return C.redact_pii(value) == sh
    finally:
        C._EMAIL = original


def build_corpus(count: int, seed: int) -> list[str]:
    """Deterministic for a given (count, seed). Never uses an unseeded RNG — a gate whose corpus
    changes run to run cannot be bisected when it goes red."""
    rng = random.Random(seed)
    corpus: list[str] = []
    # every fixture vector, always
    corpus.extend(v for v, _, _ in F.VECTORS)
    corpus.extend(F.retina_generator())
    # exhaustive 2-token compositions of the seeds across the separator set, sampled
    pairs = list(itertools.product(SEEDS, SEPARATORS, SEEDS))
    rng.shuffle(pairs)
    for a, sep, b in pairs:
        if len(corpus) >= count:
            break
        corpus.append(f"{a}{sep}{b}")
    # random perturbation injection at every position of a random seed token
    while len(corpus) < count:
        base = rng.choice(SEEDS)
        if not base:
            continue
        pos = rng.randrange(len(base) + 1)
        corpus.append(base[:pos] + rng.choice(PERTURB) + base[pos:])
    return corpus[:count]


def run(count: int, seed: int, verbose: bool) -> int:
    if not os.path.exists(HOOK_IO):
        print(f"FATAL: {HOOK_IO} not found", file=sys.stderr)
        return 1
    corpus = build_corpus(count, seed)
    # NUL cannot cross argv/stdin framing; drop it rather than silently mangling the batch
    corpus = [v for v in corpus if "\0" not in v]
    print(f"corpus: {len(corpus)} inputs (seed={seed})")

    shells: list[str] = []
    BATCH = 500
    for i in range(0, len(corpus), BATCH):
        shells.extend(shell_redact_batch(corpus[i:i + BATCH]))

    exempt = 0
    unexplained: list[tuple[str, str, str]] = []
    for value, sh in zip(corpus, shells):
        py = C.redact_pii(value)
        if sh == py:
            continue
        if _email_lookahead_explains(value, sh, py):
            exempt += 1
        else:
            unexplained.append((value, sh, py))

    print(f"  agree               : {len(corpus) - exempt - len(unexplained)}")
    print(f"  exempt (@Nx lookahead): {exempt}")
    print(f"  UNEXPLAINED         : {len(unexplained)}")
    if unexplained:
        print("\nUNEXPLAINED divergences — a NEW root cause exists:", file=sys.stderr)
        for value, sh, py in unexplained[: (len(unexplained) if verbose else 25)]:
            print(f"  in     {value!r}\n    shell  {sh!r}\n    python {py!r}", file=sys.stderr)
        if not verbose and len(unexplained) > 25:
            print(f"  … and {len(unexplained) - 25} more (--verbose for all)", file=sys.stderr)
        return 1
    print("\nEQUIVALENCE HOLDS — the retina lookahead is the only divergence.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--count", type=int, default=8000, help="corpus size (default 8000)")
    ap.add_argument("--seed", type=int, default=20260729, help="RNG seed — keep it FIXED in CI")
    ap.add_argument("--verbose", action="store_true", help="print every unexplained divergence")
    a = ap.parse_args(argv)
    return run(a.count, a.seed, a.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
