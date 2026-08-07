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
HARNESS = REPO / "scripts" / "review" / "isolated-agy-review.sh"

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

        # OUTSIDE the repository. The stub writing inside it is a reviewer mutating the checkout, which
        # `isolated-agy-review.sh` detects and exits 3 for — correctly. That went unnoticed until the
        # capture status began propagating: before that the harness returned 0 regardless, so the
        # detector fired into a void. The fixture's own instrumentation must not look like the defect
        # the harness exists to catch.
        self.probe = Path(tempfile.mkdtemp(prefix="agy-probe-")) / "PLAN_AS_REVIEWED.txt"
        self.addCleanup(shutil.rmtree, self.probe.parent, ignore_errors=True)
        self.env = dict(os.environ)
        self.env["PATH"] = f"{stubs}{os.pathsep}{self.env['PATH']}"
        self.env["XDG_STATE_HOME"] = str(self.root / "state")
        self.env["UM_PROBE_OUT"] = str(self.probe)

    def allocated_transcript(self, name: str, plan_bytes: bytes, recorded: bytes):
        """A reserved leaf with the sidecars `isolated-agy-review.sh` reads, built by hand.

        `plan_bytes` is what `.planbytes` holds; `recorded` is what `.plan`'s digest attests to. Passing
        two different values is the substitution scenario; passing the same value is the control.

        The `.launch` record is written for BOTH, even though only the honest run reaches `pty-capture`.
        Without it the refusal in the tampering test could be the launch-record preflight rather than
        the digest check, and the test would pass while proving nothing — which is how it first failed.
        """
        import hashlib

        base = Path(tempfile.mkdtemp(prefix="agy-alloc-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        out = base / name
        out.touch()
        # A CANONICAL launch record: 32 hex digits and a newline. `pty-capture` now validates the record's
        # grammar (and its equality to the run id in the filename) BEFORE spawning, because "regular and
        # nonempty" let a `not-a-run-id` record burn a full review that the verdict writer then discarded
        # (PR #63 recheck, P2). A fixture record has to be one a real allocator could have written.
        Path(str(out) + ".launch").write_text("a" * 32 + " gemini\n", encoding="utf-8")
        Path(str(out) + ".plan").write_text(
            f"{hashlib.sha256(recorded).hexdigest()}  docs/planning/FEATURE_PLAN.md\n",
            encoding="utf-8")
        Path(str(out) + ".planbytes").write_bytes(plan_bytes)
        prompt = base / "prompt.md"
        prompt.write_text(PROMPT_BODY + "REVIEW TARGET: docs/planning/FEATURE_PLAN.md\n",
                          encoding="utf-8")
        # The prompt binding is MANDATORY for the same reason the plan snapshot is: staging an
        # unauthenticated snapshot when the sidecar was absent was "absent means unchecked", reachable
        # by one `rm` (PR #63 recheck, P1). A hand-built capture must carry what the binder writes.
        Path(str(out) + ".promptsha256").write_text(
            hashlib.sha256(prompt.read_bytes()).hexdigest() + "  prompt.md\n", encoding="utf-8")
        return out, prompt

    def run_harness(self, out, prompt):
        return subprocess.run(
            ["bash", str(HARNESS), str(prompt), str(out), "90", "docs/planning/FEATURE_PLAN.md"],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=False, input="",
        )

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

    def test_an_ABSOLUTE_plan_operand_still_reaches_the_reviewer(self):
        """The copy fix survived for the relative spelling only (PR #63 recheck).

        `bind-prompt.py` accepts an absolute in-repository plan path — the Gemini skill's own generated
        prompt uses one — and pasting it into `"$TREE/$PLAN_REL"` built a nested destination like
        `$TREE/Users/…/docs/planning/X.md`, while the rewritten prompt still pointed `agy` at
        `$TREE/docs/planning/X.md`. The copy landed where the reviewer never looks, so it read the
        COMMITTED plan again: the exact defect the copy was added to fix, alive for one spelling of
        the same operand.
        """
        result = subprocess.run(
            ["bash", str(CAPTURE), "COREDEV-9999", "3",
             ".agy-prompt-COREDEV-9999r1.md", str(self.plan), "90"],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=False, input="",
        )
        self.assertTrue(
            self.probe.is_file(),
            f"the stub never ran — the harness refused an absolute operand: {result.stdout}{result.stderr}",
        )
        self.assertEqual(
            EDITED, self.probe.read_text(encoding="utf-8").strip(),
            "an absolute plan operand still leaves the reviewer reading the COMMITTED plan",
        )

    def test_a_failing_reviewer_propagates_its_status(self):
        """`isolated-agy-review.sh` captured the status in `RC` and then discarded it.

        The script ended with a successful diagnostic `echo`, so a stub exiting 23 printed
        `EXIT=23 … FAILED REVIEW` while the helper reported success — leaving the caller unable to tell
        a completed review from an auth, model or timeout failure, which is the distinction the gate
        depends on (PR #63 recheck, P2).
        """
        stub = self.root / ".stubs" / "agy"
        stub.write_text('#!/usr/bin/env bash\nprintf "output\\n"\nexit 23\n', encoding="utf-8")
        stub.chmod(0o755)
        result = self.capture("7")
        self.assertEqual(23, result.returncode, result.stdout + result.stderr)

    def test_a_tampered_plan_snapshot_is_refused_BEFORE_the_reviewer_runs(self):
        """`cp` then `cmp` compared the snapshot only against its own copy (PR #63 recheck, P1).

        A same-account process rewriting `<transcript>.planbytes` between `bind-prompt.py` returning and
        the staging copy was read by BOTH operations, so they agreed and `agy` reviewed substituted
        bytes. Nothing downstream caught it: `review-verdict.py` validates the `.plan` RECORD against the
        live plan and never hashes `.planbytes`, so the resulting transcript could approve the ORIGINAL
        plan while the reviewer had read something else.

        The record held the honest digest the entire time and nothing read it — the fifth
        "recorded and never compared" on this branch.

        The assertion that matters is the LAST one. Exiting non-zero after the reviewer has already
        consumed the substituted bytes would be a report, not a refusal.
        """
        out, prompt = self.allocated_transcript(
            "COREDEV-9999-r9-gemini.txt",
            plan_bytes=b"# Plan\nSUBSTITUTED BYTES\n",
            recorded=self.plan.read_bytes(),
        )
        result = self.run_harness(out, prompt)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("does not match its recorded digest", result.stderr)
        self.assertFalse(
            self.probe.is_file(),
            "the reviewer RAN on substituted bytes — the refusal came after the damage",
        )

    def test_DELETING_the_bound_snapshot_from_an_allocated_capture_is_refused(self):
        """Absence downgraded the arm to the live, mutable plan (PR #63 recheck, P1).

        The staging guard authenticates `.planbytes` against `.plan` — but only when `.planbytes`
        EXISTS. Removing it took the `else` branch, which re-read the working-tree plan, so the cheapest
        attack on the strongest binding in the chain was `rm` rather than any substitution: bind plan A,
        delete the snapshot, point the live plan at B, and the reviewer read B while `review-verdict`
        (which requires `.plan` and never reads `.planbytes`) approved A.

        This is "absent means unchecked" — the same fail-open shape as a missing `.launch`, a missing
        prompt binding and a missing plan binding, all closed on this branch. The binder writes
        `.planbytes` and `.plan` together, so for an allocator-shaped capture absence is tampering.
        """
        honest = self.plan.read_bytes()
        out, prompt = self.allocated_transcript(
            "COREDEV-9999-r14-gemini.txt", plan_bytes=honest, recorded=honest)
        Path(str(out) + ".planbytes").unlink()
        # The live plan diverges to B — what the fallback would have staged.
        self.plan.write_text("# Plan\nVERSION B (LIVE, UNBOUND)\n", encoding="utf-8")

        result = self.run_harness(out, prompt)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("no bound plan snapshot", result.stderr)
        self.assertFalse(
            self.probe.is_file(),
            "the reviewer RAN on the live plan — deleting the snapshot still downgrades the arm",
        )

    def test_the_snapshot_requirement_is_UNCONDITIONAL_not_scoped_to_a_launch_record(self):
        """The first fix scoped the requirement to captures carrying a `.launch`, and that was dead.

        The theory was that a direct or legacy call had no binder run and so no snapshot to lose. But
        this harness only ever invokes `pty-capture --allocated`, which refuses a leaf whose `.launch`
        is absent — so the scoped condition held in every run that could complete, and the live-plan
        fallback behind it was unreachable. A weaker path nobody can take is one an edit re-exposes, so
        it was deleted rather than left as a guarded branch. Removing the record must not resurrect it.
        """
        honest = self.plan.read_bytes()
        out, prompt = self.allocated_transcript(
            "COREDEV-9999-r15-gemini.txt", plan_bytes=honest, recorded=honest)
        Path(str(out) + ".planbytes").unlink()
        Path(str(out) + ".launch").unlink()
        self.plan.write_text("# Plan\nVERSION B (LIVE, UNBOUND)\n", encoding="utf-8")

        result = self.run_harness(out, prompt)

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertFalse(
            self.probe.is_file(),
            "dropping the launch record re-opened the live-plan fallback",
        )

    def test_an_honest_snapshot_still_stages(self):
        """Positive control for the digest check — it must refuse tampering, not refuse everything.

        Without this, deleting the `with open(destination…)` write would leave the tampering test green
        while every real round silently lost its staged plan.
        """
        honest = self.plan.read_bytes()
        out, prompt = self.allocated_transcript(
            "COREDEV-9999-r10-gemini.txt", plan_bytes=honest, recorded=honest)
        result = self.run_harness(out, prompt)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(EDITED, self.probe.read_text(encoding="utf-8").strip(),
                         "an authentic snapshot did not reach the reviewer")

    def test_a_plan_relative_to_the_CALLERS_directory_reaches_the_reviewer(self):
        """The harness `cd`'d to the repository root and re-read the operand there (PR #63 recheck, P2).

        `bind-prompt.py` accepts the plan relative to the CALLER'S directory, so
        `../docs/planning/FEATURE_PLAN.md` from a subdirectory bound successfully and then died here as
        `plan not readable` — a round refused for a spelling the binder had just accepted, before the
        reviewer ever launched. That is the fifth false refusal this recheck surfaced, and they matter
        as much as fail-opens: a guard that rejects correct work is one an operator switches off.
        """
        sub = self.root / "sub"
        sub.mkdir()
        result = subprocess.run(
            ["bash", str(CAPTURE), "COREDEV-9999", "4",
             "../.agy-prompt-COREDEV-9999r1.md", "../docs/planning/FEATURE_PLAN.md", "90"],
            cwd=sub, env=self.env, capture_output=True, text=True, check=False, input="",
        )
        self.assertTrue(
            self.probe.is_file(),
            f"a caller-relative plan was refused: {result.stdout}{result.stderr}",
        )
        self.assertEqual(EDITED, self.probe.read_text(encoding="utf-8").strip())

    def test_the_harness_own_staging_is_not_reported_as_a_reviewer_mutation(self):
        """The plan copy deliberately dirties the checkout — that IS the detached-HEAD fix.

        Comparing the final tree to `HEAD` therefore reported the harness's own staged input as a
        reviewer write, with the plan listed. A detector that cries wolf on its own inputs is one
        nobody reads, and this is the COREDEV-2607 detector — doubly load-bearing now that a reviewer
        write VOIDS the round (PR #63 recheck, P1) instead of printing a note: a false positive here
        would fail every clean round, which is how a gate gets switched off.
        """
        result = self.capture("8")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("GATE FAILED", result.stdout + result.stderr)

    MUTATING_STUB = """#!/usr/bin/env bash
tree=""; prompt=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --add-dir) tree="$2"; shift 2 ;;
    -p) prompt="${2#Read and follow }"; shift 2 ;;
    *) shift ;;
  esac
done
%s
printf 'VERDICT: APPROVE\\n'
"""

    def install_stub(self, body: str) -> None:
        stub = self.root / ".stubs" / "agy"
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)

    def test_staging_never_writes_through_a_symlink_leaf_from_committed_HEAD(self):
        """PR #63 recheck, P1 — reproduced: an outside victim was overwritten.

        `git worktree add --detach` materializes committed tree entries, so if HEAD records the plan
        path as a SYMLINK to a file outside the tree, the disposable checkout recreates that link and
        the old `open(destination, "wb")` staging wrote THROUGH it. Here HEAD carries the symlink, the
        live worktree replaces it with a real uncommitted plan (the normal review state), and staging
        must refuse to traverse the recreated link.
        """
        victim = Path(tempfile.mkdtemp(prefix="agy-victim-")) / "PRECIOUS.txt"
        self.addCleanup(shutil.rmtree, victim.parent, ignore_errors=True)
        victim.write_text("PRECIOUS OUTSIDE DATA\n", encoding="utf-8")

        # Commit the plan path AS A SYMLINK to the outside victim.
        self.plan.unlink()
        self.plan.symlink_to(victim)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "plan-as-symlink"], cwd=self.root, check=True)
        # Live worktree: a real, uncommitted plan at that path (what the reviewer should read).
        self.plan.unlink()
        self.plan.write_text(f"# Plan\n{EDITED}\n", encoding="utf-8")

        result = self.capture("9")
        self.assertEqual("PRECIOUS OUTSIDE DATA\n", victim.read_text(encoding="utf-8"),
                         "staging wrote through the materialized symlink leaf to the outside victim")

    def test_a_reviewer_that_rewrites_the_staged_plan_voids_the_round(self):
        """PR #63 recheck, P1 — reproduced: rc was 0 with NO note at all.

        The status diff is STATUS-line based and the staged plan is already `M` in the baseline, so
        re-modifying its content changed nothing the diff compared: the reviewer substituted the plan,
        approved, and the capture succeeded while synthesis validated only the untouched live plan.
        The basis is now verified by CONTENT against the digest the `.plan` record attests to.
        """
        self.install_stub(self.MUTATING_STUB
                     % 'printf "# Plan\\nSUBSTITUTED\\n" > "$tree/docs/planning/FEATURE_PLAN.md"')
        result = self.capture("11")
        self.assertEqual(3, result.returncode, result.stdout + result.stderr)
        self.assertIn("STAGED PLAN was modified", result.stdout + result.stderr)

    def test_a_reviewer_that_writes_scratch_inside_the_checkout_voids_the_round(self):
        """Writing files is the COREDEV-2607 signature — agent mode, implementing instead of
        reviewing. A review produced that way is untrustworthy whether or not the copy is discarded,
        so the round is VOID, not annotated."""
        self.install_stub(self.MUTATING_STUB % ': > "$tree/IMPLEMENTATION_NOTES.txt"')
        result = self.capture("12")
        self.assertEqual(3, result.returncode, result.stdout + result.stderr)
        combined = result.stdout + result.stderr
        self.assertIn("WROTE inside the disposable checkout", combined)
        self.assertIn("IMPLEMENTATION_NOTES.txt", combined)

    def test_a_reviewer_editing_an_ALREADY_DIRTY_tracked_file_voids_the_round(self):
        """The live-tree detector was STATUS-CATEGORY-only (PR #63 recheck, P1).

        `git status --porcelain` emits one line per path — ` M docs/…` — so a reviewer that rewrote a
        file ALREADY modified in the working tree left that line byte-identical, and `BEFORE != AFTER`
        compared equal. The detector is the COREDEV-2607 gate whose failure VOIDS the round, and it saw
        nothing. The same defect had already been found and fixed in `preflight-agy.sh`; the fix did not
        reach either harness, which is why the rule now lives in one sourced file.

        The fixture arranges the exact blind spot: a tracked file is committed, then modified (so it is
        ` M` before the run), and the stub modifies it AGAIN by absolute path. No status line moves.
        """
        tracked = self.root / "NOTES.md"
        tracked.write_text("committed\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "notes"], cwd=self.root, check=True)
        tracked.write_text("uncommitted edit\n", encoding="utf-8")   # ` M` before the run

        def status_line_for(name: str) -> str:
            lines = subprocess.run(["git", "status", "--porcelain"], cwd=self.root,
                                   capture_output=True, text=True, check=True).stdout.splitlines()
            return next(line for line in lines if line.endswith(name))

        before_line = status_line_for("NOTES.md")
        self.install_stub(self.MUTATING_STUB
                          % f'printf "REVIEWER WROTE HERE\\n" > {tracked}')
        result = self.capture("14")

        # The blind spot is real: the file was rewritten and its status line did not move.
        self.assertEqual("REVIEWER WROTE HERE\n", tracked.read_text(encoding="utf-8"))
        self.assertEqual(before_line, status_line_for("NOTES.md"),
                         "the fixture no longer reproduces the blind spot — the status line moved")
        self.assertEqual(3, result.returncode, result.stdout + result.stderr)
        self.assertIn("MUTATED the working tree", result.stdout + result.stderr)
        # Emitted only when the new-status-lines diff is EMPTY, which is the harness's own evidence
        # that a status-only comparison had nothing to report. That is the deletion test for the fix.
        self.assertIn("no new status line", result.stdout + result.stderr)

    def test_a_reviewer_that_tampers_with_its_prompt_voids_the_round(self):
        """The old diff EXCLUDED the prompt's basename, so prompt tampering was invisible by
        construction. The prompt is basis exactly like the plan; content-verified the same way."""
        self.install_stub(self.MUTATING_STUB % 'printf "sneaky addendum\\n" >> "$prompt"')
        result = self.capture("13")
        self.assertEqual(3, result.returncode, result.stdout + result.stderr)
        self.assertIn("PROMPT was modified", result.stdout + result.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
