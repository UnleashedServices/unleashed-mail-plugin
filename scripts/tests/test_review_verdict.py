"""Tests for scripts/review-verdict.py — the plan-digest-bound Combined-verdict artifact."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "review-verdict.py")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


class ReviewVerdictTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.plan = os.path.join(self.d, "FEATURE_NAME_PLAN.md")
        with open(self.plan, "w", encoding="utf-8") as fh:
            fh.write("# Plan\nDo the thing.\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def _write(self, verdict="APPROVE_WITH_NOTES",
               reviewers=("gemini=APPROVE", "codex=APPROVE_WITH_NOTES")):
        args = ["write", "--plan", self.plan, "--verdict", verdict]
        for r in reviewers:
            args += ["--reviewer", r]
        return run(*args)

    def _verdict_file(self):
        return os.path.join(self.d, ".verdicts", "FEATURE_NAME_PLAN.md.verdict.json")

    # --- happy path -----------------------------------------------------------------
    def test_write_then_verify_approves(self):
        self.assertEqual(self._write().returncode, 0)
        v = run("verify", "--plan", self.plan)
        self.assertEqual(v.returncode, 0, v.stderr)
        self.assertIn("GATE OK", v.stdout)

    def test_plain_approve_also_verifies(self):
        self._write(verdict="APPROVE", reviewers=("gemini=APPROVE", "codex=APPROVE"))
        self.assertEqual(run("verify", "--plan", self.plan).returncode, 0)

    # --- the core protection: approve-then-edit -------------------------------------
    def test_edited_plan_fails_verify(self):
        self._write()
        with open(self.plan, "a", encoding="utf-8") as fh:
            fh.write("sneaky extra line\n")
        v = run("verify", "--plan", self.plan)
        self.assertEqual(v.returncode, 1)
        self.assertIn("CHANGED since approval", v.stderr)

    def test_whitespace_only_edit_still_fails(self):
        # raw-byte digest — even a trailing space must invalidate the approval
        self._write()
        with open(self.plan, "a", encoding="utf-8") as fh:
            fh.write(" ")
        self.assertEqual(run("verify", "--plan", self.plan).returncode, 1)

    # --- non-approving verdicts fail closed -----------------------------------------
    def test_request_changes_fails_verify(self):
        self._write(verdict="REQUEST_CHANGES", reviewers=("gemini=APPROVE", "codex=REQUEST_CHANGES"))
        v = run("verify", "--plan", self.plan)
        self.assertEqual(v.returncode, 1)
        self.assertIn("not an approving verdict", v.stderr)

    def test_disagreement_fails_verify(self):
        self._write(verdict="DISAGREEMENT", reviewers=("gemini=APPROVE", "codex=REQUEST_CHANGES"))
        self.assertEqual(run("verify", "--plan", self.plan).returncode, 1)

    # --- absence / malformed fail closed --------------------------------------------
    def test_no_artifact_fails_verify(self):
        v = run("verify", "--plan", self.plan)
        self.assertEqual(v.returncode, 1)
        self.assertIn("no Combined-verdict artifact", v.stderr)

    def test_missing_plan_fails_verify(self):
        self.assertEqual(run("verify", "--plan", self.plan + ".nope").returncode, 1)

    def test_corrupt_artifact_fails_verify(self):
        self._write()
        with open(self._verdict_file(), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        v = run("verify", "--plan", self.plan)
        self.assertEqual(v.returncode, 1)
        self.assertIn("corrupt", v.stderr)

    def test_stale_schema_version_fails_verify(self):
        self._write()
        with open(self._verdict_file(), encoding="utf-8") as fh:
            art = json.load(fh)
        art["schemaVersion"] = 999
        with open(self._verdict_file(), "w", encoding="utf-8") as fh:
            json.dump(art, fh)
        self.assertEqual(run("verify", "--plan", self.plan).returncode, 1)

    def test_tampered_verdict_field_fails_when_plan_untouched(self):
        # flipping verdict to APPROVE without a re-review still needs the digest to match — it does
        # here (plan untouched), so this asserts the verdict field itself is honored, not bypassed.
        self._write(verdict="REQUEST_CHANGES", reviewers=("gemini=REQUEST_CHANGES", "codex=REQUEST_CHANGES"))
        self.assertEqual(run("verify", "--plan", self.plan).returncode, 1)

    # --- write-side validation ------------------------------------------------------
    def test_single_reviewer_rejected(self):
        r = self._write(reviewers=("gemini=APPROVE",))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("at least two reviewers", r.stderr)

    def test_invalid_verdict_rejected(self):
        r = self._write(verdict="LGTM")
        self.assertNotEqual(r.returncode, 0)

    def test_invalid_reviewer_status_rejected(self):
        r = self._write(reviewers=("gemini=MAYBE", "codex=APPROVE"))
        self.assertNotEqual(r.returncode, 0)

    def test_missing_plan_on_write_rejected(self):
        r = run("write", "--plan", self.plan + ".nope", "--verdict", "APPROVE",
                "--reviewer", "gemini=APPROVE", "--reviewer", "codex=APPROVE")
        self.assertNotEqual(r.returncode, 0)

    # --- reviewer quorum: genuine gemini+codex dual approval (adversarial verify) -----
    def test_duplicate_reviewer_rejected_at_write(self):
        # gemini listed twice, codex absent — must NOT pass the dual-review requirement
        r = self._write(reviewers=("gemini=APPROVE", "gemini=APPROVE"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("duplicate reviewer", r.stderr)

    def test_unknown_reviewers_rejected_at_write(self):
        r = self._write(reviewers=("foo=APPROVE", "bar=APPROVE"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("missing required reviewer", r.stderr)

    def test_approve_verdict_with_rejecting_statuses_rejected_at_write(self):
        # combined --verdict APPROVE but both reviewers said REQUEST_CHANGES -> refuse to record
        r = self._write(verdict="APPROVE",
                        reviewers=("gemini=REQUEST_CHANGES", "codex=REQUEST_CHANGES"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("EVERY reviewer to approve", r.stderr)

    def test_verify_rejects_tampered_reviewer_statuses(self):
        # write a genuine approval, then hand-tamper the artifact so both statuses reject while the
        # top-level verdict stays APPROVE -> verify must fail (defense-in-depth beyond write).
        self._write()
        art_path = self._verdict_file()
        with open(art_path, encoding="utf-8") as fh:
            art = json.load(fh)
        for rvw in art["reviewers"]:
            rvw["status"] = "REQUEST_CHANGES"
        with open(art_path, "w", encoding="utf-8") as fh:
            json.dump(art, fh)
        v = run("verify", "--plan", self.plan)
        self.assertEqual(v.returncode, 1)
        self.assertIn("genuine dual review", v.stderr)

    def test_verify_rejects_tampered_duplicate_reviewer(self):
        self._write()
        art_path = self._verdict_file()
        with open(art_path, encoding="utf-8") as fh:
            art = json.load(fh)
        art["reviewers"] = [{"name": "gemini", "status": "APPROVE"},
                            {"name": "gemini", "status": "APPROVE"}]
        with open(art_path, "w", encoding="utf-8") as fh:
            json.dump(art, fh)
        self.assertEqual(run("verify", "--plan", self.plan).returncode, 1)

    # --- security: perms + symlink refusal ------------------------------------------
    def test_dir_0700_file_0600(self):
        self._write()
        dmode = stat.S_IMODE(os.stat(os.path.join(self.d, ".verdicts")).st_mode)
        fmode = stat.S_IMODE(os.stat(self._verdict_file()).st_mode)
        self.assertEqual(dmode, 0o700)
        self.assertEqual(fmode, 0o600)

    def test_verify_refuses_symlinked_artifact(self):
        self._write()
        real = self._verdict_file()
        os.rename(real, real + ".real")
        os.symlink(real + ".real", real)
        self.assertEqual(run("verify", "--plan", self.plan).returncode, 1)

    def test_write_refuses_symlinked_verdict_dir(self):
        elsewhere = os.path.join(self.d, "attacker")
        os.makedirs(elsewhere)
        os.symlink(elsewhere, os.path.join(self.d, ".verdicts"))
        r = self._write()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("symlink", r.stderr.lower())

    # --- transcript digests ----------------------------------------------------------
    def test_transcript_digest_recorded(self):
        t = os.path.join(self.d, "agy-out.txt")
        with open(t, "w", encoding="utf-8") as fh:
            fh.write("VERDICT: APPROVE\n")
        self._write(reviewers=(f"gemini=APPROVE:{t}", "codex=APPROVE"))
        with open(self._verdict_file(), encoding="utf-8") as fh:
            art = json.load(fh)
        g = next(r for r in art["reviewers"] if r["name"] == "gemini")
        self.assertIn("transcriptSha256", g)
        self.assertEqual(len(g["transcriptSha256"]), 64)


if __name__ == "__main__":
    unittest.main()
