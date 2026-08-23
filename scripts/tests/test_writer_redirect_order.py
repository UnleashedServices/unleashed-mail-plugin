#!/usr/bin/env python3
"""The state writers must suppress stderr BEFORE opening their temp file.

`scripts/precompact-snapshot.sh:70-72` states the rule normatively:

    `2>/dev/null` BEFORE `> "$TMP"` so an open failure (state dir unwritable) is suppressed too
    (bash applies redirects left-to-right; a trailing `2>/dev/null` would let the open error —
    which echoes the full PII-bearing tmp path — reach stderr).

Three of the five writers shipped with the order INVERTED — `marker.sh`, `context.sh` and
`stop-quality-marker-gate.sh` — and nothing anywhere observed it. Reproduced before fixing, with a
DIRECTORY planted at the exact temp name so the open fails EISDIR:

    SHIPPED : marker.sh: line 274: /Users/<name>/…/quality-marker-lint-<hash>.json.tmp.<pid>: Is a directory
    FIXED   : (stderr empty)

The leaked path carries the operator's home directory, and hooks write to the user's terminal.

Two cells, deliberately: a BEHAVIOURAL one that drives a real writer into a real open failure, and a
LEXICAL sweep over the whole family. The behavioural cell is the evidence; the sweep is what stops a
sixth writer being added tomorrow with the order flipped, which is how three of these five got here.

The EISDIR fixture is uid-independent — no `chmod`, so no root skip. A permissions-based fixture
would silently stop testing anything for uid 0.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: Every writer that composes a temp file and suppresses stderr around the write.
WRITERS = (
    Path("scripts/lib/marker.sh"),
    Path("scripts/lib/context.sh"),
    Path("scripts/lib/log.sh"),
    Path("scripts/precompact-snapshot.sh"),
    Path("scripts/stop-quality-marker-gate.sh"),
)

#: A redirect into a temp target followed LATER on the same line by `2>/dev/null` — the inverted
#: order. The open error escapes to the real stderr before the suppression takes effect.
INVERTED = re.compile(r'>\s*"\$[^"]*(?:tmp|TMP|STMP)[^"]*"\s+2>/dev/null')


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class TheWritersSuppressStderrBeforeOpening(unittest.TestCase):
    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = Path(tempfile.mkdtemp(prefix="redirect-order.", dir=base))
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        (self.scratch / "home").mkdir()
        (self.scratch / "data").mkdir()
        # `XDG_CONFIG_HOME` goes too: redirecting HOME alone is NOT hermetic, because git also reads
        # `$XDG_CONFIG_HOME/git/config` and it wins (measured — gemini raised this on the sibling file
        # in PR #73; this file had the same hole).
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("GIT_") and k != "XDG_CONFIG_HOME"}
        self.env.update(HOME=str(self.scratch / "home"),
                        CLAUDE_PLUGIN_DATA=str(self.scratch / "data"),
                        LC_ALL="C", LANG="C",
                        # PUBLICATION OFF. These cells assert that stderr is EMPTY, and sourcing a
                        # family lib with the variable set publishes into the store — which emits
                        # `unleashed-mail: plugin-state publication failed: …` whenever the chain does
                        # not authenticate. On Linux it NEVER authenticates: `plugin-state-auth.sh`
                        # refuses on every non-Darwin platform by design, so the diagnostic is
                        # unconditional there and the empty-stderr assertion cannot hold. Reproduced
                        # locally by forcing that gate to refuse — the failure is byte-identical to
                        # the one CI produced (codex, PR #74). `test_plugin_state_base.py`'s own
                        # `run()` helper sets this for the same reason.
                        _UNLEASHED_PUBLISH_OK="0")

    def _marker_write_onto_a_directory(self, library: Path):
        """Drive `marker_write` with a DIRECTORY planted at the exact temp name it will open.

        `$$` is the sourcing shell's pid, so the collision has to be created by that same shell —
        hence the whole fixture is one script rather than a setup step plus a call.
        """
        script = self.scratch / "drive.sh"
        script.write_text(
            '#!/usr/bin/env bash\n'
            '. "$1"\n'
            'p="$(marker_path lint)"\n'
            'mkdir -p "$(dirname "$p")"\n'
            'mkdir -p "${p}.tmp.$$"\n'
            'marker_write lint fail\n',
            encoding="utf-8")
        return subprocess.run(["bash", str(script), str(library)],
                              capture_output=True, text=True, env=self.env, check=False)

    def test_an_unopenable_temp_file_does_not_leak_its_path_to_stderr(self):
        result = self._marker_write_onto_a_directory(REPO / "scripts" / "lib" / "marker.sh")
        self.assertEqual("", result.stderr,
                         f"the open failure leaked the temp path to stderr:\n{result.stderr}")

    def test_the_INVERTED_order_leaks_the_path(self):
        """The mutant control. Without it this cell could not distinguish a correct redirect order
        from a writer that never opens anything — and it is what proves the fixture actually
        provokes an open failure rather than quietly succeeding."""
        library = REPO / "scripts" / "lib" / "marker.sh"
        text = library.read_text(encoding="utf-8")
        good = '"${_UNLEASHED_BASE_SOURCE:-unresolved}" 2>/dev/null > "$tmp"'
        bad = '"${_UNLEASHED_BASE_SOURCE:-unresolved}" > "$tmp" 2>/dev/null'
        self.assertEqual(1, text.count(good), "mutation anchor is not unique")
        mutant = self.scratch / "marker-inverted.sh"
        mutated = text.replace(good, bad, 1)
        self.assertEqual(text.count("\n"), mutated.count("\n"), "the mutation changed the line count")
        mutant.write_text(mutated, encoding="utf-8")
        result = self._marker_write_onto_a_directory(mutant)
        self.assertIn("Is a directory", result.stderr,
                      f"CONTROL FAILED — the inverted order did not leak, so the fixture is not "
                      f"provoking an open failure and the cell above proves nothing:\n{result.stderr!r}")
        self.assertIn(".tmp.", result.stderr,
                      f"CONTROL FAILED — the leak did not name the temp path:\n{result.stderr!r}")

    def test_NO_writer_in_the_family_carries_the_inverted_order(self):
        """The family sweep. Three of these five shipped inverted while the rule sat in a comment in
        the fourth; a rule that lives only in prose is not enforced. This is what a sixth writer
        added tomorrow has to pass."""
        offenders = []
        for rel in WRITERS:
            path = REPO / rel
            if not path.is_file():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if INVERTED.search(line):
                    offenders.append(f"{rel}:{number}: {line.strip()}")
        self.assertEqual([], offenders,
                         "these writers redirect into a temp file BEFORE suppressing stderr, so an "
                         "open failure prints the full path:\n  " + "\n  ".join(offenders))

    def test_the_sweep_would_catch_an_inverted_writer(self):
        """The sweep's own control: it must actually match the shape it claims to reject."""
        self.assertRegex('printf x > "$tmp" 2>/dev/null', INVERTED)
        self.assertRegex('printf x > "$_rb_path.tmp.$$" 2>/dev/null', INVERTED)
        self.assertRegex("if [ -n \"$_STMP\" ] && printf '%s' \"$C\" > \"$_STMP\" 2>/dev/null; then", INVERTED)
        self.assertNotRegex('printf x 2>/dev/null > "$tmp"', INVERTED)
        self.assertNotRegex('tail -n 5 "$p" 2>/dev/null > "$tmp"', INVERTED)


if __name__ == "__main__":
    unittest.main()
