#!/usr/bin/env python3
"""The Plan Review Gate driven end to end, through the real scripts, in a real git repository.

WHY THIS FILE EXISTS
Every other suite here tests one script. Nothing spanned the chain — snapshot, allocate, bind, capture,
write, verify, resolve — and the chain is where the gate's guarantees actually live.

Running it end to end on 2026-08-06 independently reproduced `COREDEV-2497` §4.1: `verify` re-reads the
plan and nothing else, so a transcript can be rewritten after approval and the gate still prints
`GATE OK`. That defect was already known and planned — this suite did not discover it, and the claim
that it did was corrected. What the run DID establish is that the defect is reachable through the real
chain with no hand-built fixture, which a per-script suite cannot show because each script is
individually correct. It is pinned by
`test_the_gate_still_accepts_altered_evidence_COREDEV_2497` until that plan passes its gate.

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
# The prompt NAMES its plan: `bind-prompt.py` refuses a prompt that names a different `*_PLAN.md`, or
# none at all, because a prompt saying `REVIEW TARGET: PLAN_B` bound cleanly to `--plan PLAN_A` and
# produced an APPROVE artifact for the wrong plan (PR #63 recheck, P1).
PROMPT_BODY = (
    "REVIEW TARGET: docs/planning/FEATURE_PLAN.md\n"
) + (
    "Review the attached plan for correctness, security and completeness.\n"
    "State your verdict on the FIRST line as "
    "`VERDICT: APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES`.\n"
) * 12

# Drops a run-marker when `UM_REVIEWER_RAN` is set, so a test can prove the reviewer did NOT run rather
# than only that the wrapper exited non-zero — a refusal that happens AFTER the bytes reach the reviewer
# is not a refusal (PR #63 recheck, P3: the never-reaches test asserted only the exit code).
REVIEWER_STUB = (
    "#!/usr/bin/env bash\n"
    "[ -n \"${UM_REVIEWER_RAN:-}\" ] && : > \"$UM_REVIEWER_RAN\"\n"
    "printf 'VERDICT: APPROVE\\n%s reviewed the plan.\\n' \"$0\"\n"
)


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

    def test_two_runs_at_the_SAME_ticket_and_round_get_their_own_snapshot(self):
        """Per-ROUND naming is not per-RUN — proved against the REAL allocator (PR #63 recheck, P1).

        Both invocations name one prompt file, `.codex-prompt-COREDEV-9999r5.md`, because the prompt
        name is derived from ticket and round only. The concurrency test in
        `test_capture_prompt_binding.py` compares round 7 against round 8, so it structurally cannot
        see this case. Each run must still end up bound to a snapshot of its own, which holds because
        the snapshot is keyed by the transcript's unique run identity rather than by the prompt's name.
        """
        transcripts = []
        for _attempt in range(2):
            transcripts.append(Path(self.capture("codex", 5)))

        self.assertNotEqual(transcripts[0], transcripts[1], "the allocator reused a leaf")
        for transcript in transcripts:
            snapshot = transcript.with_name(transcript.name + ".prompt")
            self.assertTrue(snapshot.is_file(), f"{transcript.name} has no snapshot of its own")

    # ---- refusals: the capture arms ------------------------------------------------------------

    def test_a_prompt_outside_the_repository_never_reaches_the_reviewer(self):
        """The capture helpers are reached from model-invocable skills, so the MODEL picks this operand."""
        outside = self.root.parent / f"outside-{self.root.name}.txt"
        outside.write_text("SECRET MATERIAL\n", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        link = self.root / ".codex-prompt-COREDEV-9999r7.md"
        link.symlink_to(outside)

        marker = self.root.parent / f"reviewer-ran-{self.root.name}"
        self.addCleanup(lambda: marker.unlink(missing_ok=True))
        self.env["UM_REVIEWER_RAN"] = str(marker)
        for operand in (str(outside), link.name):
            with self.subTest(operand=operand):
                marker.unlink(missing_ok=True)
                result = self.run_script(
                    "bash", REVIEW / "capture-codex-review.sh", "COREDEV-9999", "7",
                    operand, "docs/planning/FEATURE_PLAN.md", "60",
                )
                self.assertNotEqual(0, result.returncode, result.stdout)
                # The point of the finding: the reviewer must never have been reached. A non-zero exit
                # that happened AFTER the secret was disclosed would still pass the exit-code check.
                self.assertFalse(marker.exists(),
                                 f"the reviewer RAN on operand {operand!r} before the refusal")

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

    def test_the_gate_still_accepts_altered_evidence_COREDEV_2497(self):
        """PINS A KNOWN, OPEN DEFECT — this test passing is the bug, not the fix.

        `verify` re-reads the plan and nothing else. Every transcript check — freshness, layout, the
        O_NOFOLLOW descriptor digest, the plan binding — runs at WRITE and is never re-run, so
        `transcriptSha256` is recorded in the artifact and no code path compares it back. Overwriting an
        approved transcript with `REQUEST_CHANGES` still yields `GATE OK — APPROVE`.

        This is `docs/planning/COREDEV-2497_VERIFY_TRANSCRIPTS_PLAN.md` §4.1 (High), whose plan has NOT
        passed its gate — the last recorded round is `Both arms REQUEST_CHANGES`. That plan specifies
        behaviour this test deliberately does not anticipate: a missing transcript must FAIL with a
        distinct `MISSING` cause, the recorded path must be resolved exactly once (no `os.path.exists`
        before the open, on any branch), and the work must land behind the named `_open_regular_fd` /
        `_digest_transcript_fd` seams. An ad-hoc fix was written here on 2026-08-06 and reverted for
        exactly that reason: it tolerated absence and pre-checked the path with `lexists`.

        Asserting the defect rather than omitting it means this file records what the gate ACTUALLY
        does. When COREDEV-2497 lands, this test fails — and that failure is the signal to delete it.
        """
        codex, _gemini, _artifact = self.passing_gate()
        self.assertEqual(0, self.verdict("verify", "--plan", self.plan).returncode, "control")

        codex.write_text("VERDICT: REQUEST_CHANGES\nthis is not what was approved\n", encoding="utf-8")
        self.assertEqual(
            0,
            self.verdict("verify", "--plan", self.plan).returncode,
            "COREDEV-2497 §4.1 has landed — the gate now catches altered evidence. Delete this test.",
        )

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
