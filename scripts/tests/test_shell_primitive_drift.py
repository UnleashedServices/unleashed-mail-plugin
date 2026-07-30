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
import shutil
import subprocess
import tempfile
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

    #: (env, expected). The FOURTH row is the only one that rejects `${CLAUDE_PLUGIN_DATA-…}`
    #: (single dash): that form passes rows 1-3 identically to the correct `:-` form and returns
    #: EMPTY only when the variable is set-but-empty, which would relocate every marker, log and
    #: snapshot to a relative path.
    MATRIX = (
        ({"__unset__": ["HOME", "CLAUDE_PLUGIN_DATA"]}, "/.claude/unleashed-mail"),
        ({"HOME": "/probe", "__unset__": ["CLAUDE_PLUGIN_DATA"]}, "/probe/.claude/unleashed-mail"),
        ({"HOME": "/probe", "CLAUDE_PLUGIN_DATA": "/custom/d"}, "/custom/d"),
        ({"HOME": "/probe", "CLAUDE_PLUGIN_DATA": ""}, "/probe/.claude/unleashed-mail"),
    )
    LIBS = (("marker.sh", "marker_base"), ("log.sh", "log_base"), ("context.sh", "context_base"))

    def _run(self, libdir, lib, fn, envspec):
        env = {k: v for k, v in os.environ.items()}
        for k in envspec.get("__unset__", []):
            env.pop(k, None)
        for k, v in envspec.items():
            if k != "__unset__":
                env[k] = v
        return subprocess.run(
            ["bash", "-c", f"set -euo pipefail; . '{libdir}/{lib}'; {fn}"],
            capture_output=True, text=True, env=env,
        ).stdout

    def test_every_copy_is_the_same_expression(self):
        missing = [
            n for n in ("marker.sh", "log.sh", "context.sh")
            if self.EXPECTED not in open(os.path.join(SCRIPTS, "lib", n), encoding="utf-8").read()
        ]
        self.assertEqual(
            [], missing,
            "base-path fallback expansion diverged (or dropped the `:-` / `${HOME:-}` guard) in: "
            + ", ".join(missing),
        )

    def test_matrix_with_paths_sh_present(self):
        libdir = os.path.join(SCRIPTS, "lib")
        for lib, fn in self.LIBS:
            for envspec, expected in self.MATRIX:
                with self.subTest(lib=lib, env=str(envspec)):
                    self.assertEqual(expected, self._run(libdir, lib, fn, envspec))

    def test_matrix_with_paths_sh_ABSENT(self):
        """The inline fallback is the whole reason `paths.sh` is safe to add.

        These libs are sourced standalone (swift-reviewer sources context.sh alone into a zsh
        Bash tool; test-hooks.sh sources marker.sh/context.sh without hook-io.sh). If a missing
        paths.sh aborted them, the dedup would convert three independent fail-open paths into one
        shared point of failure — worse than the triplication it replaced. So the fallback must
        produce IDENTICAL results across the whole matrix, not merely 'not crash'.
        """
        with tempfile.TemporaryDirectory() as tmp:
            for f in os.listdir(os.path.join(SCRIPTS, "lib")):
                if f.endswith(".sh") and f != "paths.sh":
                    shutil.copy(os.path.join(SCRIPTS, "lib", f), tmp)
            self.assertFalse(os.path.exists(os.path.join(tmp, "paths.sh")))
            for lib, fn in self.LIBS:
                for envspec, expected in self.MATRIX:
                    with self.subTest(lib=lib, env=str(envspec)):
                        self.assertEqual(expected, self._run(tmp, lib, fn, envspec))

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


class WorkflowPinDrift(unittest.TestCase):
    """CI pins must not drift between jobs (COREDEV-2598).

    Both defects below were real, in the first draft of the load-check job:
      * a FABRICATED `actions/setup-node` commit SHA. A pin that does not exist fails at run time,
        and a pin that exists but differs from the repo's other jobs silently tests a different
        toolchain. AGENT_CONTRACTS §6 requires SHA pins; nothing checked they AGREE.
      * `${{ env.CLAUDE_CODE_VERSION }}` referenced from a second job, where it expands to EMPTY —
        the other job scopes it to a single STEP. `npm install -g pkg@` installs `latest`, so the
        load check would silently run on a DIFFERENT CLI than the schema validation it exists to
        complement.
    """

    WORKFLOW = os.path.join(REPO, ".github", "workflows", "plugin-ci.yml")

    @classmethod
    def setUpClass(cls):
        with open(cls.WORKFLOW, encoding="utf-8") as fh:
            cls.src = fh.read()

    def test_every_action_pin_of_the_same_action_uses_the_same_sha(self):
        pins = {}
        for m in re.finditer(r"uses:\s*([\w.-]+/[\w.-]+)@([0-9a-f]{40})", self.src):
            pins.setdefault(m.group(1), set()).add(m.group(2))
        drifted = {a: sorted(s) for a, s in pins.items() if len(s) > 1}
        self.assertEqual({}, drifted, f"the same action pinned to different SHAs: {drifted}")

    def test_no_action_is_pinned_to_a_mutable_tag(self):
        """AGENT_CONTRACTS §6: SHA pins, never @vN."""
        tagged = re.findall(r"uses:\s*([\w.-]+/[\w.-]+@v[\d.]+)\s*$", self.src, re.M)
        self.assertEqual([], tagged, f"mutable tag pins found: {tagged}")

    def test_all_claude_code_version_pins_agree(self):
        versions = set(re.findall(r"CLAUDE_CODE_VERSION:\s*([0-9.]+)", self.src))
        self.assertEqual(
            1, len(versions),
            f"CLAUDE_CODE_VERSION differs across jobs: {sorted(versions)} — the load check must run "
            "on the SAME CLI as the schema validation",
        )

    def test_no_job_installs_an_unpinned_claude_cli(self):
        """`npm install -g @anthropic-ai/claude-code@` with an empty expansion installs `latest`."""
        self.assertNotIn("claude-code@${{ env.", self.src,
                         "cross-job env reference — CLAUDE_CODE_VERSION is step-scoped and expands empty")
        bare = re.findall(r"claude-code@\s*$", self.src, re.M)
        self.assertEqual([], bare, "unpinned claude-code install")
