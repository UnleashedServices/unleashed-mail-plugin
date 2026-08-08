#!/usr/bin/env python3
"""The `agy` preflight must not point a mutation-capable agent at the reviewed checkout.

THE FINDING (PR #63 recheck, P2) — reproduced before it was fixed.
`preflight-agy.sh` ran `agy -p "ping"` in the CALLER'S working directory, which is the checkout under
review, while the same skill documents that `agy` has no read-only mode and has already once
implemented a plan instead of reviewing it (2.6.4, COREDEV-2607). A stub that touched a file in its
working directory left that file in the checkout and the script still printed `healthy`.

Two things were wrong, and they need separate fixes because they fail separately:

  * the ping ran WHERE the repository is — closed by giving it a fresh empty scratch directory, since
    a ping needs no repository at all; and
  * nothing checked afterwards — closed by fingerprinting `git status --porcelain` around the capture,
    the same assertion `isolated-agy-review.sh` already carried and this script did not.

Isolation alone would be the weaker fix: it makes the common case safe while a build that writes by
absolute path still goes unnoticed. The assertion is what turns "unlikely" into "detected".
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PREFLIGHT = REPO / "scripts" / "review" / "preflight-agy.sh"

HEALTHY = '#!/usr/bin/env bash\nprintf "Pong! How can I help?\\n"\n'
WRITES_IN_CWD = '#!/usr/bin/env bash\n: > "$PWD/AGY_WROTE_HERE.txt"\nprintf "Pong!\\n"\n'


class PreflightAgyIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="agy-preflight-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "tracked.txt").write_text("x\n", encoding="utf-8")
        for command in (["git", "init", "-q", "."],
                        ["git", "config", "user.email", "probe@test"],
                        ["git", "config", "user.name", "probe"],
                        ["git", "add", "-A"],
                        ["git", "commit", "-qm", "init"]):
            subprocess.run(command, cwd=self.root, check=True)

        self.stubs = self.root / ".stubs"
        self.stubs.mkdir()
        self.env = dict(os.environ)
        self.env["PATH"] = f"{self.stubs}{os.pathsep}{self.env['PATH']}"
        # The stub directory is untracked, so it is in the BEFORE fingerprint too — which is exactly
        # why the script compares before/after rather than asserting a clean tree.

    def install(self, body: str) -> None:
        stub = self.stubs / "agy"
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)

    def run_preflight(self):
        return subprocess.run(
            ["bash", str(PREFLIGHT)], cwd=self.root, env=self.env,
            capture_output=True, text=True, check=False, input="",
        )

    def test_a_healthy_agy_reports_healthy(self):
        """Positive control — isolation must not have broken the thing the preflight exists to do."""
        self.install(HEALTHY)
        result = self.run_preflight()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("healthy", result.stdout)

    def test_the_ping_does_not_run_in_the_checkout(self):
        """The stub writes to `$PWD`. If that is the checkout, the file lands in the tree."""
        self.install(WRITES_IN_CWD)
        result = self.run_preflight()
        self.assertFalse(
            (self.root / "AGY_WROTE_HERE.txt").exists(),
            "the ping ran in the reviewed checkout",
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_an_agy_that_writes_into_the_repo_anyway_is_caught(self):
        """The assertion, not the isolation — a build writing by ABSOLUTE path defeats isolation alone.

        Without this the preflight would report `healthy` while a file it created sat in the tree,
        which is the COREDEV-2607 failure mode arriving through the health check itself.
        """
        target = self.root / "SNEAKED_IN.txt"
        self.install(f'#!/usr/bin/env bash\n: > "{target}"\nprintf "Pong!\\n"\n')

        result = self.run_preflight()
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("MUTATED", result.stderr)
        self.assertIn("SNEAKED_IN.txt", result.stderr)

    def test_the_mutation_report_names_only_what_changed(self):
        """A diagnostic nobody can read is a diagnostic nobody uses.

        The stub directory is already untracked, so dumping the whole status buries the one new entry
        among pre-existing noise and leaves the operator diffing two blobs by eye.
        """
        target = self.root / "SNEAKED_IN.txt"
        self.install(f'#!/usr/bin/env bash\n: > "{target}"\nprintf "Pong!\\n"\n')

        result = self.run_preflight()
        reported = [line for line in result.stderr.splitlines() if line.startswith("??")]
        self.assertEqual(["?? SNEAKED_IN.txt"], reported, result.stderr)

    def test_a_content_edit_to_an_already_dirty_tracked_file_is_caught(self):
        """The status line alone could not see this (PR #63 recheck, P2).

        `git status --porcelain` emits ` M tracked.txt` whether the file was modified once or twice, so
        an agy build that edits an ALREADY-MODIFIED tracked file left the before/after status equal and
        the preflight reported `healthy`. Folding `git diff HEAD` into the fingerprint catches the
        content change; the report says a content edit occurred, since there is no new status line.
        """
        tracked = self.root / "tracked.txt"
        tracked.write_text("dirty edit\n", encoding="utf-8")  # already ` M` before the ping
        self.install(f'#!/usr/bin/env bash\nprintf "more dirt\\n" > "{tracked}"\nprintf "Pong!\\n"\n')

        result = self.run_preflight()
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("MUTATED", result.stderr)
        self.assertIn("content", result.stderr.lower())
        # No forged new status line — the whole point is that the status was unchanged.
        self.assertEqual([], [line for line in result.stderr.splitlines() if line.startswith("??")])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
