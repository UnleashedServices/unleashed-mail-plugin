#!/usr/bin/env python3
"""The Plan Review Gate driven end to end, through the real scripts, in a real git repository.

WHY THIS FILE EXISTS
Every other suite here tests one script. Nothing spanned the chain — snapshot, allocate, bind, capture,
write, verify, resolve — and the chain is where the gate's guarantees actually live. Running it by hand
on 2026-08-06 found a defect no unit test could see: `verify` re-read the plan and nothing else, so a
transcript could be rewritten after approval and the gate still printed `GATE OK`. That is the
class of bug a per-script suite is structurally blind to, because each script was individually correct.

WHAT IS REAL AND WHAT IS STUBBED
Real: the git repository, `allocate-transcript.sh` (and through it `pty-capture.py --allocate`),
`bind-prompt.py`, `pty-capture.py`, `review-verdict.py` in all three modes, `resolve-plan-gate.sh`.
Stubbed: `codex` and `agy` ONLY — the two things that leave the machine. They are stubbed by putting a
shell script earlier on `PATH`, not by patching the helpers, so the helpers run their real argv.

The state root is redirected with `XDG_STATE_HOME` into the test's own temporary directory, so a run
never reads or writes the developer's real transcripts.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REVIEW = REPO / "scripts" / "review"
VERDICT = REPO / "scripts" / "review-verdict.py"

# The gemini arm's isolation harness refuses a prompt below a size floor, which a two-line probe trips.
# A realistic prompt is part of the fixture, not an incidental detail.
PROMPT_BODY = (
    "Review the attached plan for correctness, security and completeness.\n"
    "State your verdict on the FIRST line as "
    "`VERDICT: APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES`.\n"
) * 12

REVIEWER_STUB = "#!/usr/bin/env bash\nprintf 'VERDICT: APPROVE\\n%s reviewed the plan.\\n' \"$0\"\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EndToEndGate(unittest.TestCase):
    """One real repository per test, so no test can inherit another's tampering.

    That is not defensive boilerplate. The hand run that produced this file reported a FALSE failure
    because a transcript tampered with in one scenario was still tampered with when the next scenario
    took its "clean" baseline — the control failed and the fix looked broken. Isolation is the fixture's
    job, not the scenario's.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="e2e-gate-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "docs" / "planning").mkdir(parents=True)
        self.plan = self.root / "docs" / "planning" / "FEATURE_PLAN.md"
        self.plan.write_text("# Plan\n\nDo the thing, carefully.\n", encoding="utf-8")

        subprocess.run(["git", "init", "-q", "."], cwd=self.root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "-c", "user.email=e2e@test", "-c", "user.name=e2e", "commit", "-qm", "init"],
            cwd=self.root, check=True,
        )

        stubs = self.root / ".stubs"
        stubs.mkdir()
        for reviewer in ("codex", "agy"):
            stub = stubs / reviewer
            stub.write_text(REVIEWER_STUB, encoding="utf-8")
            stub.chmod(0o755)

        self.env = dict(os.environ)
        self.env["XDG_STATE_HOME"] = str(self.root / "state")
        self.env["PATH"] = f"{stubs}{os.pathsep}{self.env['PATH']}"

    # ---- the chain -----------------------------------------------------------------------------

    def run_script(self, *argv, stdin: str | None = None):
        return subprocess.run(
            [str(a) for a in argv], cwd=self.root, env=self.env, text=True,
            capture_output=True, check=False, input=stdin if stdin is not None else "",
        )

    def verdict(self, *argv):
        return self.run_script("python3", VERDICT, *argv)

    def capture(self, reviewer: str, round_value: int) -> str:
        """Run one arm for real and return the transcript path the allocator handed it."""
        prefix = {"codex": ".codex-prompt", "gemini": ".agy-prompt"}[reviewer]
        prompt = self.root / f"{prefix}-COREDEV-9999r{round_value}.md"
        prompt.write_text(PROMPT_BODY, encoding="utf-8")
        helper = REVIEW / f"capture-{reviewer}-review.sh"
        result = self.run_script(
            "bash", helper, "COREDEV-9999", str(round_value), prompt.name,
            "docs/planning/FEATURE_PLAN.md", "120",
        )
        marker = [
            line for line in (result.stdout + result.stderr).splitlines()
            if line.startswith("UNLEASHED_TRANSCRIPT=")
        ]
        self.assertEqual(1, len(marker), f"{reviewer} arm emitted no transcript marker: {result.stderr}")
        return marker[0].split("=", 1)[1]

    def passing_gate(self, round_value: int = 1):
        """snapshot -> both arms -> write. Returns (codex transcript, gemini transcript, artifact)."""
        self.assertEqual(0, self.verdict("snapshot", "--plan", self.plan).returncode)
        codex = self.capture("codex", round_value)
        gemini = self.capture("gemini", round_value)
        written = self.verdict(
            "write", "--plan", self.plan, "--verdict", "APPROVE", "--round", str(round_value),
            "--reviewer", f"codex=APPROVE:{codex}", "--reviewer", f"gemini=APPROVE:{gemini}",
        )
        self.assertEqual(0, written.returncode, written.stderr)
        artifacts = sorted((self.root / "docs" / "planning" / ".verdicts").glob("*.json"))
        self.assertEqual(1, len(artifacts), "one gate run must leave exactly one artifact")
        return Path(codex), Path(gemini), artifacts[0]

    def edit_artifact(self, artifact: Path, mutate) -> None:
        data = json.loads(artifact.read_text(encoding="utf-8"))
        mutate(data)
        artifact.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # ---- the happy path ------------------------------------------------------------------------

    def test_the_whole_chain_produces_a_passing_gate(self):
        codex, gemini, artifact = self.passing_gate()

        for transcript in (codex, gemini):
            self.assertTrue(transcript.is_file(), transcript)
            self.assertEqual("VERDICT: APPROVE", transcript.read_text(encoding="utf-8").splitlines()[0])
            # The binding sidecars are what make the transcript evidence rather than just output.
            for suffix in (".plan", ".promptsha256"):
                self.assertTrue(
                    transcript.with_name(transcript.name + suffix).is_file(),
                    f"{transcript.name}{suffix} was not written",
                )

        self.assertEqual(0, self.verdict("verify", "--plan", self.plan).returncode)
        gate = self.run_script("bash", REVIEW / "resolve-plan-gate.sh",
                               stdin="docs/planning/FEATURE_PLAN.md\n")
        self.assertEqual(0, gate.returncode, gate.stderr)
        self.assertIn("GATE OK", gate.stdout + gate.stderr)

    def test_each_arm_binds_its_transcript_to_the_plan_it_reviewed(self):
        codex, gemini, _artifact = self.passing_gate()
        expected = f"{_sha256(self.plan)}  docs/planning/FEATURE_PLAN.md\n"
        for transcript in (codex, gemini):
            self.assertEqual(
                expected,
                transcript.with_name(transcript.name + ".plan").read_text(encoding="utf-8"),
            )

    # ---- refusals: the capture arms ------------------------------------------------------------

    def test_a_prompt_outside_the_repository_never_reaches_the_reviewer(self):
        """The capture helpers are reached from model-invocable skills, so the MODEL picks this operand."""
        outside = self.root.parent / f"outside-{self.root.name}.txt"
        outside.write_text("SECRET MATERIAL\n", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        link = self.root / ".codex-prompt-COREDEV-9999r7.md"
        link.symlink_to(outside)

        for operand in (str(outside), link.name):
            with self.subTest(operand=operand):
                result = self.run_script(
                    "bash", REVIEW / "capture-codex-review.sh", "COREDEV-9999", "7",
                    operand, "docs/planning/FEATURE_PLAN.md", "60",
                )
                self.assertNotEqual(0, result.returncode, result.stdout)

    def test_a_transcript_bound_to_another_plan_cannot_back_this_one(self):
        codex, gemini, _artifact = self.passing_gate()
        other = self.root / "docs" / "planning" / "OTHER_PLAN.md"
        other.write_text("# A different plan\n", encoding="utf-8")
        self.assertEqual(0, self.verdict("snapshot", "--plan", other).returncode)

        written = self.verdict(
            "write", "--plan", other, "--verdict", "APPROVE", "--round", "1",
            "--reviewer", f"codex=APPROVE:{codex}", "--reviewer", f"gemini=APPROVE:{gemini}",
        )
        self.assertNotEqual(0, written.returncode, "a transcript bound elsewhere must not gate this plan")

    # ---- refusals: writing the verdict ---------------------------------------------------------

    def test_the_write_path_refuses_an_unbacked_approval(self):
        codex, gemini, _artifact = self.passing_gate()
        for label, reviewers in (
            ("one reviewer", [f"codex=APPROVE:{codex}"]),
            ("one arm rejects", [f"codex=REQUEST_CHANGES:{codex}", f"gemini=APPROVE:{gemini}"]),
            ("missing transcript", ["codex=APPROVE:/nonexistent/transcript.txt",
                                    f"gemini=APPROVE:{gemini}"]),
        ):
            with self.subTest(case=label):
                argv = ["write", "--plan", self.plan, "--verdict", "APPROVE", "--round", "2"]
                for reviewer in reviewers:
                    argv += ["--reviewer", reviewer]
                self.assertNotEqual(0, self.verdict(*argv).returncode)

    # ---- refusals: verifying afterwards --------------------------------------------------------

    def test_editing_the_plan_after_approval_fails_the_gate(self):
        self.passing_gate()
        self.plan.write_text(self.plan.read_text(encoding="utf-8") + "\nsnuck in later\n",
                             encoding="utf-8")

        self.assertNotEqual(0, self.verdict("verify", "--plan", self.plan).returncode)
        gate = self.run_script("bash", REVIEW / "resolve-plan-gate.sh",
                               stdin="docs/planning/FEATURE_PLAN.md\n")
        self.assertNotEqual(0, gate.returncode, "the gate skill must refuse what verify refuses")

    def test_rewriting_a_transcript_after_approval_fails_the_gate(self):
        """The defect this whole file was written to catch.

        Every transcript check — freshness, layout, the O_NOFOLLOW digest, the plan binding — ran at
        WRITE and was never re-run, so `transcriptSha256` was recorded and nothing compared it back.
        Overwriting an approved transcript with `REQUEST_CHANGES` still produced `GATE OK — APPROVE`.
        The exposed window is write->verify, which is the entire implementation phase.
        """
        codex, _gemini, _artifact = self.passing_gate()
        self.assertEqual(0, self.verdict("verify", "--plan", self.plan).returncode, "control")

        original = codex.read_bytes()
        codex.write_text("VERDICT: REQUEST_CHANGES\nthis is not what was approved\n", encoding="utf-8")
        failed = self.verdict("verify", "--plan", self.plan)
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("evidence", failed.stdout + failed.stderr)

        codex.write_bytes(original)
        self.assertEqual(0, self.verdict("verify", "--plan", self.plan).returncode,
                         "restoring the exact bytes must restore the gate — the check is on content")

    def test_altering_the_recorded_digest_fails_the_gate(self):
        """The other direction: same transcript, artifact re-stamped. Both sides must be load-bearing."""
        _codex, _gemini, artifact = self.passing_gate()
        self.edit_artifact(artifact, lambda d: d["reviewers"][0].update(transcriptSha256="0" * 64))
        self.assertNotEqual(0, self.verdict("verify", "--plan", self.plan).returncode)

    def test_a_purged_transcript_is_tolerated(self):
        """Deliberate, and the reason the check is not simply "present and matching".

        Transcripts live in an XDG state directory that is legitimately purgeable — macOS has already
        destroyed 105 of this project's transcripts in one sweep under disk pressure. Failing a real
        approval because its evidence aged out is a false GATE FAILED, which is its own outage.
        """
        codex, _gemini, _artifact = self.passing_gate()
        codex.unlink()
        self.assertEqual(0, self.verdict("verify", "--plan", self.plan).returncode)

    def test_a_transcript_replaced_by_a_symlink_is_not_treated_as_purged(self):
        """Absence is forgiven; a different KIND of object standing in its place is not."""
        codex, _gemini, _artifact = self.passing_gate()
        elsewhere = self.root / "decoy-transcript.txt"
        elsewhere.write_bytes(codex.read_bytes())
        codex.unlink()
        codex.symlink_to(elsewhere)
        self.assertNotEqual(0, self.verdict("verify", "--plan", self.plan).returncode)

    def test_a_hand_edited_reviewer_status_fails_the_gate(self):
        _codex, _gemini, artifact = self.passing_gate()
        self.edit_artifact(artifact, lambda d: d["reviewers"][0].update(status="REQUEST_CHANGES"))
        self.assertNotEqual(0, self.verdict("verify", "--plan", self.plan).returncode)

    def test_deleting_a_reviewer_from_the_artifact_fails_the_gate(self):
        _codex, _gemini, artifact = self.passing_gate()
        self.edit_artifact(artifact, lambda d: d.update(reviewers=d["reviewers"][:1]))
        self.assertNotEqual(0, self.verdict("verify", "--plan", self.plan).returncode)

    # ---- refusals: the gate skill's own operand ------------------------------------------------

    def test_the_gate_refuses_a_plan_outside_the_planning_tree(self):
        self.passing_gate()
        outside = self.root.parent / f"outside-plan-{self.root.name}.md"
        outside.write_text("# not a plan in this tree\n", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))

        for operand in (str(outside), "docs/planning/../../etc/passwd"):
            with self.subTest(operand=operand):
                gate = self.run_script("bash", REVIEW / "resolve-plan-gate.sh", stdin=operand + "\n")
                self.assertNotEqual(0, gate.returncode)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
