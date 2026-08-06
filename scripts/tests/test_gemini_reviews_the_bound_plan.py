#!/usr/bin/env python3
"""The Gemini arm must review the bytes its `.plan` sidecar attests to.

THE FINDING (PR #63 recheck, P1). `isolated-agy-review.sh` builds its review tree with
`git worktree add --detach "$SCR/tree" "$(git rev-parse HEAD)"`, so `agy` reads the **committed** plan.
`bind-prompt.py` hashes the **working-tree** plan into `<transcript>.plan`. When the plan has
uncommitted edits — the normal state during the documented review iteration — the transcript approves
the committed version while the artifact records it as evidence for the edited one. Two correct
digests describing different bytes, which is the same pairing failure as the prompt/plan binding, one
layer further down.

WHY COPY RATHER THAN REFUSE
Refusing an uncommitted plan would break the iterate-then-review loop the process depends on. Copying
the bound bytes into the checkout makes the binding TRUE instead of merely checkable: the reviewer
reads exactly what the sidecar attests to.

The stub reads the plan through the `--add-dir` the harness hands it, not through its own working
directory — an earlier version of this probe reported nothing because a relative read landed
somewhere else entirely, which looked like the fix failing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAPTURE = REPO / "scripts" / "review" / "capture-gemini-review.sh"

COMMITTED = "COMMITTED VERSION"
EDITED = "EDITED VERSION - not committed"

# The harness refuses an assembled prompt below a size floor, so a two-line probe never reaches `agy`
# at all — the guard is real and this fixture has to clear it rather than trip it.
PROMPT_BODY = "Review the plan for correctness, security and completeness.\n" * 40

AGY_STUB = """#!/usr/bin/env bash
tree=""
while [ "$#" -gt 0 ]; do
  case "$1" in --add-dir) tree="$2"; shift 2 ;; *) shift ;; esac
done
tail -1 "$tree/docs/planning/FEATURE_PLAN.md" > "$UM_PROBE_OUT" 2>/dev/null || echo "<absent>" > "$UM_PROBE_OUT"
printf 'VERDICT: APPROVE\\n'
"""


class GeminiReviewsTheBoundPlan(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="agy-bound-plan-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "docs" / "planning").mkdir(parents=True)
        self.plan = self.root / "docs" / "planning" / "FEATURE_PLAN.md"

        self.plan.write_text(f"# Plan\n{COMMITTED}\n", encoding="utf-8")
        prompt = self.root / ".agy-prompt-COREDEV-9999r1.md"
        prompt.write_text(PROMPT_BODY + "REVIEW TARGET: docs/planning/FEATURE_PLAN.md\n",
                          encoding="utf-8")
        for command in (["git", "init", "-q", "."],
                        ["git", "config", "user.email", "probe@test"],
                        ["git", "config", "user.name", "probe"],
                        ["git", "add", "-A"],
                        ["git", "commit", "-qm", "init"]):
            subprocess.run(command, cwd=self.root, check=True)

        # The uncommitted edit. This is the whole scenario.
        self.plan.write_text(f"# Plan\n{EDITED}\n", encoding="utf-8")

        stubs = self.root / ".stubs"
        stubs.mkdir()
        stub = stubs / "agy"
        stub.write_text(AGY_STUB, encoding="utf-8")
        stub.chmod(0o755)

        self.probe = self.root / "PLAN_AS_REVIEWED.txt"
        self.env = dict(os.environ)
        self.env["PATH"] = f"{stubs}{os.pathsep}{self.env['PATH']}"
        self.env["XDG_STATE_HOME"] = str(self.root / "state")
        self.env["UM_PROBE_OUT"] = str(self.probe)

    def capture(self, round_value: str):
        return subprocess.run(
            ["bash", str(CAPTURE), "COREDEV-9999", round_value,
             ".agy-prompt-COREDEV-9999r1.md", "docs/planning/FEATURE_PLAN.md", "90"],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=False, input="",
        )

    def test_the_reviewer_reads_the_uncommitted_bytes_the_binding_names(self):
        result = self.capture("1")
        self.assertTrue(self.probe.is_file(),
                        f"the stub never ran — the harness refused first: {result.stdout}{result.stderr}")
        seen = self.probe.read_text(encoding="utf-8").strip()
        self.assertEqual(EDITED, seen,
                         "the reviewer read the COMMITTED plan while the sidecar bound the edited one")

    def test_the_sidecar_and_the_reviewed_bytes_agree(self):
        """Stated as the property, not as two separate facts.

        The defect was never "the wrong file was read" on its own — it was that the recorded binding
        and the reviewed bytes could disagree while both looked correct in isolation.
        """
        import hashlib

        result = self.capture("2")
        marker = [line for line in (result.stdout + result.stderr).splitlines()
                  if line.startswith("UNLEASHED_TRANSCRIPT=")]
        self.assertEqual(1, len(marker), result.stderr)
        transcript = Path(marker[0].split("=", 1)[1])

        bound = Path(str(transcript) + ".plan").read_text(encoding="utf-8").split()[0]
        self.assertEqual(hashlib.sha256(self.plan.read_bytes()).hexdigest(), bound)
        self.assertEqual(EDITED, self.probe.read_text(encoding="utf-8").strip())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
