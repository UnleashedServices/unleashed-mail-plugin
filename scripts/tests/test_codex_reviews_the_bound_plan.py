#!/usr/bin/env python3
"""The codex arm must review the authenticated bound plan, not the live, swappable file.

THE FINDING (PR #63 recheck, P1). `capture-codex-review.sh` ran `codex exec … -s read-only` in the LIVE
working tree, so the plan file codex opened was the mutable one. An A->B->A swap during codex's read
window let it review substituted bytes while `.plan` and the live plan both still hashed A, and
`review-verdict` authenticates only the live plan — so the artifact attested a plan the reviewer never
read. The gemini arm already isolated its review into a detached checkout with the authenticated
`.planbytes` staged; the codex arm never inherited it. It now runs `isolated-codex-review.sh`, which
uses the SHARED `stage-bound-plan.py` — so the fix cannot diverge between the two arms again.

The codex stub reads the plan from its cwd, exactly as `codex exec` does, and records what it saw.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAPTURE = REPO / "scripts" / "review" / "capture-codex-review.sh"

COMMITTED = "COMMITTED VERSION"
EDITED = "EDITED VERSION - not committed"
PROMPT_BODY = "Review the plan for correctness, security and completeness.\n" * 40

# codex exec is invoked by pty-capture as `codex exec -c … -s read-only "<prompt>"`, run from the
# disposable checkout. The stub records BOTH the plan bytes it sees AND its working directory — the
# directory is the deterministic discriminator: under isolation codex runs in a throwaway detached
# worktree, never the repo root, so the live plan it would otherwise open is out of reach.
CODEX_STUB = """#!/usr/bin/env bash
{ pwd; tail -1 docs/planning/FEATURE_PLAN.md 2>/dev/null || echo "<absent>"; } > "$UM_CODEX_SAW"
printf 'VERDICT: APPROVE\\n'
"""


class CodexReviewsTheBoundPlan(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="codex-bound-plan-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "docs" / "planning").mkdir(parents=True)
        self.plan = self.root / "docs" / "planning" / "FEATURE_PLAN.md"
        self.plan.write_text(f"# Plan\n{COMMITTED}\n", encoding="utf-8")
        prompt = self.root / ".codex-prompt-COREDEV-9999r1.md"
        prompt.write_text(PROMPT_BODY + "REVIEW TARGET: docs/planning/FEATURE_PLAN.md\n",
                          encoding="utf-8")
        for command in (["git", "init", "-q", "."],
                        ["git", "config", "user.email", "probe@test"],
                        ["git", "config", "user.name", "probe"],
                        ["git", "add", "-A"],
                        ["git", "commit", "-qm", "init"]):
            subprocess.run(command, cwd=self.root, check=True)
        # The uncommitted edit — the normal state during review iteration.
        self.plan.write_text(f"# Plan\n{EDITED}\n", encoding="utf-8")

        stubs = self.root / ".stubs"
        stubs.mkdir()
        (stubs / "codex").write_text(CODEX_STUB, encoding="utf-8")
        (stubs / "codex").chmod(0o755)

        self.saw = Path(tempfile.mkdtemp(prefix="codex-saw-")) / "SEEN.txt"
        self.addCleanup(shutil.rmtree, self.saw.parent, ignore_errors=True)
        self.env = dict(os.environ)
        self.env["PATH"] = f"{stubs}{os.pathsep}{self.env['PATH']}"
        self.env["XDG_STATE_HOME"] = str(self.root / "state")
        self.env["UM_CODEX_SAW"] = str(self.saw)

    def capture(self, round_value: str):
        return subprocess.run(
            ["bash", str(CAPTURE), "COREDEV-9999", round_value,
             ".codex-prompt-COREDEV-9999r1.md", "docs/planning/FEATURE_PLAN.md", "30"],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=False, input="",
        )

    def test_codex_reviews_an_isolated_checkout_not_the_live_repo(self):
        """The deterministic isolation property (PR #63 recheck, P1).

        Under isolation codex runs in a disposable detached worktree, so the plan it opens is the
        authenticated staged copy — a swap of the LIVE plan cannot reach it. The stub records its cwd:
        if codex ran in the repo root (`self.root`), it was reading the live, swappable file, which is
        the defect. The reverted, pre-isolation arm runs codex in the live tree and fails here.
        """
        result = self.capture("1")
        self.assertTrue(self.saw.is_file(),
                        f"the stub never ran — the harness refused first: {result.stdout}{result.stderr}")
        cwd_line, plan_line = self.saw.read_text(encoding="utf-8").splitlines()[:2]
        self.assertNotEqual(
            os.path.realpath(cwd_line), os.path.realpath(self.root),
            "codex ran in the live repo root, not an isolated checkout — the live plan was reachable",
        )
        # And what it read there is the authenticated bound plan (the uncommitted EDITED bytes).
        self.assertEqual(EDITED, plan_line.strip(),
                         "codex did not read the authenticated bound plan in its checkout")

    def test_a_live_plan_diverging_from_the_staged_bytes_does_not_reach_codex(self):
        """The A->B->A property, made DETERMINISTIC (PR #63 recheck, P1).

        A concurrent swap is timing-flaky — a test that can pass against the broken code proves nothing
        (the reviewer's own "weak tests" finding). Instead the divergence is arranged statically: after
        the binding captures the authenticated `.planbytes` (EDITED), the LIVE plan is overwritten with
        B and left that way for the whole capture. Under isolation codex reads the staged EDITED bytes
        from its checkout; the reverted live-tree arm reads B. The `.plan`/`.planbytes` the binder wrote
        still attest EDITED either way, which is exactly what makes the live-tree read a wrong-verdict
        hole. We assert codex never sees B.

        To arrange staged=EDITED while live=B, the binding must run against EDITED first. The capture
        binds against whatever the live plan is at call time, so a fixture cannot both bind EDITED and
        present B before the call. Instead this drives `isolated-codex-review.sh` directly with a
        pre-built transcript whose `.planbytes` are EDITED, then points the live plan at B.
        """
        import hashlib

        allocated = Path(tempfile.mkdtemp(prefix="codex-alloc-"))
        self.addCleanup(shutil.rmtree, allocated, ignore_errors=True)
        out = allocated / "COREDEV-9999-r2-codex.txt"
        out.touch()
        # A CANONICAL launch record: 32 hex digits and a newline. `pty-capture` validates the record's
        # grammar before spawning, because "regular and nonempty" let a `not-a-run-id` record burn a
        # full review the verdict writer then discarded (PR #63 recheck, P2).
        (allocated / (out.name + ".launch")).write_text("a" * 32 + "\n", encoding="utf-8")
        edited = f"# Plan\n{EDITED}\n".encode("utf-8")
        (allocated / (out.name + ".plan")).write_text(
            f"{hashlib.sha256(edited).hexdigest()}  docs/planning/FEATURE_PLAN.md\n", encoding="utf-8")
        (allocated / (out.name + ".planbytes")).write_bytes(edited)
        prompt = allocated / "prompt.md"
        prompt.write_text(PROMPT_BODY + "REVIEW TARGET: docs/planning/FEATURE_PLAN.md\n",
                          encoding="utf-8")
        (allocated / (out.name + ".prompt")).write_bytes(prompt.read_bytes())

        # The live plan now diverges to B; the authenticated staged bytes are EDITED.
        self.plan.write_text("# Plan\nVERSION B (SUBSTITUTED)\n", encoding="utf-8")

        harness = REPO / "scripts" / "review" / "isolated-codex-review.sh"
        result = subprocess.run(
            ["bash", str(harness), str(allocated / (out.name + ".prompt")), str(out), "30",
             "docs/planning/FEATURE_PLAN.md"],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=False, input="",
        )
        self.assertTrue(self.saw.is_file(), result.stdout + result.stderr)
        seen = self.saw.read_text(encoding="utf-8")
        self.assertNotIn("SUBSTITUTED", seen,
                         "codex read the diverged LIVE plan B, not the authenticated staged EDITED bytes")
        self.assertIn(EDITED, seen)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
