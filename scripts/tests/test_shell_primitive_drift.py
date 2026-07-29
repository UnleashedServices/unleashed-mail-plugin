#!/usr/bin/env python3
"""Drift guards for duplicated shell primitives (COREDEV-2600).

Some duplication in `scripts/lib/` is legitimate — the libs are sourced standalone by different
callers and cannot all depend on each other. What is NOT acceptable is silent DIVERGENCE, which had
already happened three times when this ticket was written:

  * the PreCompact round scanner had an inline copy missing two guards `context_highest_round` has,
    and one of them leaked to stderr (fixed; asserted in `scripts/test-hooks.sh`);
  * `marker_mtime` branched on `uname == Darwin` while two other sites feature-detected, so on
    FreeBSD it returned its `0` sentinel — which makes `stop-quality-marker-gate.sh` compute
    AGE=999999 and SKIP THE GATE ENTIRELY;
  * `scripts/test-hooks.sh` carried its OWN diverged copy of the same `uname` shape, so the harness
    that would have to prove the fix was itself carrying the defect.

These assert on SHAPE, deliberately, because that third case is why the scope is all of `scripts/`
and not just `scripts/lib/`.
"""
from __future__ import annotations

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO, "scripts")

#: The `[ "$(uname …)" = "Darwin" ]` TEST shape. Deliberately not a bare `uname.*Darwin` search:
#: the source now carries several COMMENTS explaining why this shape is wrong, and a loose pattern
#: would match the explanation and fail on a correct tree — an own-goal this project has hit before
#: (a doc gate whose marker also appeared in prose).
#: Single-quoted raw string on purpose — the pattern ENDS in a double quote, so a `"""…"""` form
#: is a syntax error. And no `re.X`: verbose mode strips whitespace from the pattern, which would
#: silently delete the `\s` classes and leave a regex that matches almost nothing.
UNAME_DARWIN_TEST = re.compile(r'\[\s*"\$\(uname[^)]*\)"\s*=\s*"Darwin"')


def _shell_files():
    for root, _dirs, files in os.walk(SCRIPTS):
        if os.path.basename(root) == "tests":
            continue
        for f in files:
            if f.endswith(".sh"):
                yield os.path.join(root, f)


class MtimeShape(unittest.TestCase):
    def test_no_uname_darwin_branch_survives_anywhere_under_scripts(self):
        offenders = []
        for path in _shell_files():
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if UNAME_DARWIN_TEST.search(line):
                        offenders.append(f"{os.path.relpath(path, REPO)}:{n}: {line.strip()}")
        self.assertEqual(
            [], offenders,
            "`uname == Darwin` mtime branch found — feature-detect instead (BSD `stat -f %m` then "
            "GNU `stat -c %Y`). It returns the failure sentinel on FreeBSD:\n  " + "\n  ".join(offenders),
        )

    def test_the_guard_regex_actually_matches_the_defect(self):
        """A shape gate that matches nothing is decoration. Prove it fires on the real form."""
        defect = 'if [ "$(uname 2>/dev/null)" = "Darwin" ]; then m="$(stat -f %m "$1")"; fi'
        self.assertTrue(UNAME_DARWIN_TEST.search(defect), "guard regex does not match the defect")

    def test_the_guard_regex_does_not_match_prose_about_the_defect(self):
        """The source explains why this shape is wrong; the gate must not fail on the explanation."""
        for prose in (
            "# FEATURE-DETECT, do not branch on `uname` (COREDEV-2600 item 3). The old",
            "# `uname == Darwin` form assumed only Darwin has BSD `stat`, so on FreeBSD it took",
            "# Feature-detect the mtime flavor rather than branching on `uname == Darwin`: BSD stat",
        ):
            with self.subTest(prose=prose[:48]):
                self.assertIsNone(UNAME_DARWIN_TEST.search(prose))


class BasePathExpansion(unittest.TestCase):
    #: Every plugin-data base expansion must keep the `${HOME:-}` inner guard AND use `:-` (not `-`).
    #: `${CLAUDE_PLUGIN_DATA-…}` passes a three-environment matrix identically to the correct form and
    #: fails only when the variable is set-but-EMPTY, where it returns "" and silently relocates every
    #: marker, log and snapshot to a relative path.
    EXPECTED = "${CLAUDE_PLUGIN_DATA:-${HOME:-}/.claude/unleashed-mail}"

    def test_every_copy_is_the_same_expression(self):
        found = {}
        for name in ("marker.sh", "log.sh", "context.sh"):
            path = os.path.join(SCRIPTS, "lib", name)
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            found[name] = self.EXPECTED in src
        missing = [k for k, v in found.items() if not v]
        self.assertEqual(
            [], missing,
            "base-path expansion diverged (or dropped the `:-` / `${HOME:-}` guard) in: "
            + ", ".join(missing),
        )

    def test_no_single_dash_default_anywhere(self):
        """`${CLAUDE_PLUGIN_DATA-` (single dash) is the plausible-wrong form: it treats an
        explicitly-empty value as 'set' and returns empty."""
        offenders = []
        for path in _shell_files():
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if "${CLAUDE_PLUGIN_DATA-" in line:
                        offenders.append(f"{os.path.relpath(path, REPO)}:{n}")
        self.assertEqual([], offenders, "single-dash default found: " + ", ".join(offenders))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
