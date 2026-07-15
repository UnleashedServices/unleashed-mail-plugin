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
        # A non-empty transcript. An APPROVING artifact now requires one per reviewer (COREDEV-2492
        # PR review): `--reviewer gemini=APPROVE` with no `:TRANSCRIPT` used to produce a GATE OK on
        # the caller's bare assertion, and a 0-byte file passed because only `isfile` was checked.
        self.tx = os.path.join(self.d, "transcript.txt")
        with open(self.tx, "w", encoding="utf-8") as fh:
            fh.write("reviewer said things\nVERDICT: APPROVE\n")
        # A SECOND, distinct transcript. An approving artifact requires a DISTINCT transcript per
        # reviewer (codex, #41 review), and until that rule existed this fixture handed the SAME file to
        # both reviewers — so every test wrote the exact artifact shape that rule now forbids, which is
        # precisely why no test caught the hole. `_write` gives each reviewer its own by default.
        self.tx2 = os.path.join(self.d, "transcript2.txt")
        with open(self.tx2, "w", encoding="utf-8") as fh:
            fh.write("the OTHER reviewer said other things\nVERDICT: APPROVE\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def _write(self, verdict="APPROVE_WITH_NOTES",
               reviewers=("gemini=APPROVE", "codex=APPROVE_WITH_NOTES")):
        args = ["write", "--plan", self.plan, "--verdict", verdict]
        for i, r in enumerate(reviewers):
            # Attach a DISTINCT fixture transcript per reviewer unless the case supplied its own path
            # (or deliberately omits one to exercise the missing-transcript rule).
            if ":" not in r:
                r = f"{r}:{self.tx if i == 0 else self.tx2}"
            args += ["--reviewer", r]
        return run(*args)

    def test_approving_artifact_requires_a_transcript_per_reviewer(self):
        """An APPROVING verdict must EVIDENCE its approvals: `gemini=APPROVE` with no `:TRANSCRIPT`
        used to write a GATE OK on the caller's bare assertion alone (codex, #41 review)."""
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", "gemini=APPROVE", "--reviewer", "codex=APPROVE")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("requires a transcript per reviewer", r.stdout + r.stderr)

    def test_a_same_basename_plan_in_a_different_dir_cannot_reuse_the_artifact(self):
        """The plan binding compared BASENAMES only, so an approving artifact copied between two
        same-named plans with identical bytes verified the wrong one — the digest matched (identical
        bytes) and the basename matched (same filename). Now bound to the full realpath (full review,
        #41; reproduced)."""
        import shutil
        a_dir = os.path.join(self.d, "a")
        b_dir = os.path.join(self.d, "b")
        os.makedirs(a_dir); os.makedirs(b_dir)
        a_plan = os.path.join(a_dir, "SAME_PLAN.md")
        b_plan = os.path.join(b_dir, "SAME_PLAN.md")
        for pth in (a_plan, b_plan):
            with open(pth, "w", encoding="utf-8") as fh:
                fh.write("# Same plan\nidentical bytes\n")
        # approve a_plan
        r = run("write", "--plan", a_plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", f"codex=APPROVE:{self.tx2}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(run("verify", "--plan", a_plan).returncode, 0)  # legit
        # copy a's artifact next to b's identically-named plan
        b_verdicts = os.path.join(b_dir, ".verdicts")
        os.makedirs(b_verdicts)
        shutil.copy(os.path.join(a_dir, ".verdicts", "SAME_PLAN.md.verdict.json"), b_verdicts)
        v = run("verify", "--plan", b_plan)
        self.assertNotEqual(v.returncode, 0, "a's approval must NOT verify b's plan")
        self.assertIn("written for a different plan", v.stdout + v.stderr)

    def test_a_malformed_transcript_digest_cannot_pass(self):
        """A digest must LOOK like a digest.

        non-empty + distinct + not-the-empty-hash admitted `transcriptSha256: "x"` / `"y"` and produced
        GATE OK on a hand-edited artifact (codex, #41 review). Hand-tampering is this check's stated
        threat model, so "any non-empty string is evidence" was never good enough."""
        import glob
        # NOTE "A"*64 and " "+"a"*64 are deliberately NOT here: hex is case-insensitive and the digest
        # is stripped+lowercased before matching, so both normalize to a REAL digest and must PASS.
        # Rejecting them would be over-strict and could fail a legitimate artifact — asserted below.
        for bad in ("x", "y" * 63, "z" * 64, "a" * 65, "g" * 64, "0x" + "a" * 62):
            with self.subTest(digest=bad):
                self.assertEqual(self._write().returncode, 0)
                art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                with open(art, encoding="utf-8") as fh:
                    d = json.load(fh)
                d["verdict"] = "APPROVE"
                for i, r in enumerate(d["reviewers"]):
                    r["status"] = "APPROVE"
                    r["transcriptSha256"] = bad if i == 0 else "b" * 64
                with open(art, "w", encoding="utf-8") as fh:
                    json.dump(d, fh)
                v = run("verify", "--plan", self.plan)
                self.assertNotEqual(v.returncode, 0, f"{bad!r} is not a sha256 and must not pass")

    def test_uppercase_and_padded_digests_are_normalized_not_rejected(self):
        """The hex check must not be over-strict: hex is case-insensitive, and the digest is stripped
        before matching, so `A...A` and ` a...a ` are REAL digests in a different skin. A check that
        rejected them would fail a legitimate artifact — a false GATE FAILED is its own outage."""
        import glob
        for good in ("A" * 64, " " + "a" * 64 + " "):
            with self.subTest(digest=good):
                self.assertEqual(self._write().returncode, 0)
                art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                with open(art, encoding="utf-8") as fh:
                    d = json.load(fh)
                d["verdict"] = "APPROVE"
                for i, r in enumerate(d["reviewers"]):
                    r["status"] = "APPROVE"
                    r["transcriptSha256"] = good if i == 0 else "b" * 64
                with open(art, "w", encoding="utf-8") as fh:
                    json.dump(d, fh)
                v = run("verify", "--plan", self.plan)
                self.assertEqual(v.returncode, 0, f"{good!r} normalizes to a real digest: {v.stderr}")

    def test_one_transcript_cannot_back_TWO_approvals(self):
        """Distinct NAMES are not distinct EVIDENCE.

        `--reviewer gemini=APPROVE:/tmp/agy-out.txt --reviewer codex=APPROVE:/tmp/agy-out.txt` — one
        copy-paste slip in the documented two-file flow — recorded identical transcript digests for both
        reviewers and produced `GATE OK — [gemini=APPROVE, codex=APPROVE]`. Every existing check passed
        because they all inspect the LABEL: the duplicate-name rule says "one reviewer cannot stand in
        for the other" while only ever comparing names (codex, #41 review)."""
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", f"codex=APPROVE:{self.tx}")
        self.assertNotEqual(r.returncode, 0, "one transcript must not back two approvals")
        self.assertIn("DISTINCT transcript", r.stdout + r.stderr)

    def test_identical_content_with_distinct_capture_ids_passes(self):
        """Content-inequality alone cannot tell two genuinely-separate reviews that happen to be
        byte-identical from one file reused for both. A wrapper capture ID (a per-run token) is
        authoritative provenance: two DIFFERENT files with IDENTICAL bytes but DISTINCT capture IDs are
        two real reviews and must pass (full review, #41)."""
        id1 = os.path.join(self.d, "r1.txt")
        id2 = os.path.join(self.d, "r2.txt")
        for pth in (id1, id2):
            with open(pth, "w", encoding="utf-8") as fh:
                fh.write("byte-identical review body\nVERDICT: APPROVE\n")
        with open(id1 + ".captureid", "w", encoding="utf-8") as fh:
            fh.write("cap-A\n")
        with open(id2 + ".captureid", "w", encoding="utf-8") as fh:
            fh.write("cap-B\n")
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{id1}", "--reviewer", f"codex=APPROVE:{id2}")
        self.assertEqual(r.returncode, 0, r.stderr)   # digest floor would have WRONGLY rejected this
        self.assertEqual(run("verify", "--plan", self.plan).returncode, 0)

    def test_a_non_string_provenance_field_fails_closed_not_with_a_crash(self):
        """A hand-tampered non-string transcriptPath/captureId (a list/dict) would make `set(...)` raise
        TypeError: unhashable type — a crash, not a controlled failure — and dropping it silently would
        let a tamperer null a field to skip distinctness (gemini, #41 review). Present non-string ->
        CORRUPT, no crash."""
        import glob
        for field in ("transcriptPath", "captureId"):
            for bad in ([1, 2], {"a": 1}, 5):
                with self.subTest(field=field, value=bad):
                    self.assertEqual(self._write().returncode, 0)
                    art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                    with open(art, encoding="utf-8") as fh:
                        a = json.load(fh)
                    a["verdict"] = "APPROVE"
                    a["reviewers"] = [
                        {"name": "gemini", "status": "APPROVE", "transcriptSha256": "a" * 64, field: bad},
                        {"name": "codex", "status": "APPROVE", "transcriptSha256": "b" * 64, field: "ok"},
                    ]
                    with open(art, "w", encoding="utf-8") as fh:
                        json.dump(a, fh)
                    v = run("verify", "--plan", self.plan)
                    out = v.stdout + v.stderr
                    self.assertNotEqual(v.returncode, 0)
                    self.assertNotIn("Traceback", out)

    def test_duplicate_provenance_among_present_fields_is_not_bypassed_by_a_fieldless_entry(self):
        """The distinctness checks must catch duplicates among the fields that ARE present, not require
        every reviewer to have the field. An all-or-nothing guard let a tampered artifact with one
        path-less / capture-id-less entry skip the check even with duplicates among the rest (gemini,
        #41 review)."""
        import glob
        self.assertEqual(self._write().returncode, 0)
        art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
        # (a) two reviewers share a capture ID; a third entry has none.
        with open(art, encoding="utf-8") as fh:
            a = json.load(fh)
        a["verdict"] = "APPROVE"
        a["reviewers"] = [
            {"name": "gemini", "status": "APPROVE", "transcriptSha256": "a" * 64,
             "transcriptPath": "/x/g", "captureId": "DUP"},
            {"name": "codex", "status": "APPROVE", "transcriptSha256": "b" * 64,
             "transcriptPath": "/x/c", "captureId": "DUP"},
            {"name": "octo", "status": "APPROVE", "transcriptSha256": "d" * 64, "transcriptPath": "/x/o"},
        ]
        with open(art, "w", encoding="utf-8") as fh:
            json.dump(a, fh)
        self.assertNotEqual(run("verify", "--plan", self.plan).returncode, 0)
        # (b) two reviewers share a PATH; a third entry has none.
        a["reviewers"] = [
            {"name": "gemini", "status": "APPROVE", "transcriptSha256": "a" * 64, "transcriptPath": "/x/SAME"},
            {"name": "codex", "status": "APPROVE", "transcriptSha256": "b" * 64, "transcriptPath": "/x/SAME"},
            {"name": "octo", "status": "APPROVE", "transcriptSha256": "d" * 64},
        ]
        with open(art, "w", encoding="utf-8") as fh:
            json.dump(a, fh)
        self.assertNotEqual(run("verify", "--plan", self.plan).returncode, 0)

    def test_identical_capture_ids_are_rejected(self):
        """The same capture ID for both = one wrapper run standing in for two."""
        id1 = os.path.join(self.d, "s1.txt")
        id2 = os.path.join(self.d, "s2.txt")
        with open(id1, "w", encoding="utf-8") as fh:
            fh.write("gemini body\nVERDICT: APPROVE\n")
        with open(id2, "w", encoding="utf-8") as fh:
            fh.write("codex body DIFFERENT\nVERDICT: APPROVE\n")
        for pth in (id1, id2):
            with open(pth + ".captureid", "w", encoding="utf-8") as fh:
                fh.write("cap-SAME\n")
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{id1}", "--reviewer", f"codex=APPROVE:{id2}")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DISTINCT capture", r.stdout + r.stderr)

    def test_same_file_for_both_is_rejected_by_path(self):
        """The real accidental mistake: one transcript FILE for both reviewers."""
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", f"codex=APPROVE:{self.tx}")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("same transcript FILE", r.stdout + r.stderr)

    def test_two_distinct_transcripts_still_pass(self):
        """The fix must not break the legitimate case it guards."""
        tx2 = os.path.join(self.d, "codex.txt")
        with open(tx2, "w", encoding="utf-8") as fh:
            fh.write("codex said other things\nVERDICT: APPROVE\n")
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", f"codex=APPROVE:{tx2}")
        self.assertEqual(r.returncode, 0, r.stderr)
        v = run("verify", "--plan", self.plan)
        self.assertEqual(v.returncode, 0, v.stderr)

    def test_empty_transcript_is_rejected(self):
        """`agy` writes exactly 0 bytes from a non-TTY on failure, and only `isfile` was checked — so
        a failed review recorded e3b0c442...855 (the empty-string digest) and passed."""
        empty = os.path.join(self.d, "empty.txt")
        open(empty, "w").close()
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{empty}", "--reviewer", f"codex=APPROVE:{self.tx}")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("EMPTY", r.stdout + r.stderr)

    def test_the_parse_time_empty_guard_covers_NON_approving_verdicts_too(self):
        """Pins the parse-time `getsize == 0` guard, which nothing else did.

        `test_empty_transcript_is_rejected` names that guard but does not pin it: it writes an APPROVING
        verdict, which `_quorum_problem`'s `empty_t` check rejects independently — so deleting the
        parse-time guard entirely left the WHOLE suite green (pre-merge audit). `_quorum_problem`
        early-returns for non-approving verdicts, so those paths are covered by the parse-time guard
        ALONE. Verified: with the guard deleted, APPROVE is still caught but REQUEST_CHANGES and
        DISAGREEMENT both write an artifact recording a 0-byte transcript — an audit trail asserting a
        review that never happened. Distinct from `test_non_approving_verdict_may_omit_a_transcript`:
        OMITTING a transcript (a MISSING reviewer) is legitimate; SUPPLYING an empty one is a failure.
        """
        empty = os.path.join(self.d, "empty2.txt")
        open(empty, "w").close()
        for verdict in ("REQUEST_CHANGES", "DISAGREEMENT"):
            with self.subTest(verdict=verdict):
                r = run("write", "--plan", self.plan, "--verdict", verdict,
                        "--reviewer", f"gemini={verdict}:{empty}",
                        "--reviewer", f"codex={verdict}:{self.tx}")
                self.assertNotEqual(r.returncode, 0,
                                    "a 0-byte transcript is a FAILED review — it must never be recorded "
                                    "as a real one, approving or not")
                self.assertIn("EMPTY", r.stdout + r.stderr)

    def test_non_approving_verdict_may_omit_a_transcript(self):
        """Deliberate asymmetry: a MISSING reviewer legitimately HAS no transcript, and recording
        that failure is the whole point of the artifact."""
        r = run("write", "--plan", self.plan, "--verdict", "REQUEST_CHANGES",
                "--reviewer", "gemini=MISSING", "--reviewer", f"codex=REQUEST_CHANGES:{self.tx}")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_verify_NAMES_a_MISSING_reviewer(self):
        """An unavailable reviewer and a genuine disagreement must not read identically.

        `/review-synthesis` records an absent reviewer as `<name>=MISSING` and writes a NON-APPROVING
        artifact, so both land on verify's 'not an approving verdict' branch. Byte-identical messages
        left an implementer unable to tell which `implement` recovery branch applied — so they follow
        the first one that fits, 'iterate the plan + gate', which can never clear a reviewer that never
        ran. That is the exact wedge COREDEV-2493 removes (codex, #42 review).
        """
        r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", "codex=MISSING")
        self.assertEqual(r.returncode, 0, r.stderr)
        v = run("verify", "--plan", self.plan)
        out = v.stdout + v.stderr
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("MISSING", out)
        self.assertIn("codex", out)
        self.assertIn("NOT a plan problem", out)

    def test_a_tampered_non_list_reviewers_field_fails_cleanly_not_with_a_traceback(self):
        """`art.get("reviewers") or []` rescues only FALSY junk — `5`/`true` are truthy and
        non-iterable, so the MISSING-hint loop raised TypeError (gemini, #42 review). Fails closed
        either way, but a GATE FAILED must be diagnosable, not a stack trace."""
        for junk in (5, True, "str", {"a": 1}, None):
            with self.subTest(reviewers=junk):
                r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                        "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", "codex=MISSING")
                self.assertEqual(r.returncode, 0, r.stderr)
                import glob
                art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                with open(art, encoding="utf-8") as fh:
                    a = json.load(fh)
                a["reviewers"] = junk
                with open(art, "w", encoding="utf-8") as fh:
                    json.dump(a, fh)
                v = run("verify", "--plan", self.plan)
                out = v.stdout + v.stderr
                self.assertNotEqual(v.returncode, 0)
                self.assertNotIn("Traceback", out)
                self.assertIn("GATE FAILED", out)

    def test_mixed_MISSING_plus_rejection_does_not_mask_the_rejection(self):
        """One reviewer MISSING + one REQUEST_CHANGES is TWO problems, not one.

        The unconditional MISSING hint said "this is NOT a plan problem" even when the reviewer that
        DID run wanted plan changes — telling the implementer to ignore real, actionable feedback and
        go chase the unavailable CLI (codex, #42 review)."""
        r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                "--reviewer", f"gemini=REQUEST_CHANGES:{self.tx}", "--reviewer", "codex=MISSING")
        self.assertEqual(r.returncode, 0, r.stderr)
        v = run("verify", "--plan", self.plan)
        out = v.stdout + v.stderr
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("codex", out)                    # the missing one is still named
        self.assertIn("gemini=REQUEST_CHANGES", out)   # ...and the rejection is NOT masked
        self.assertNotIn("NOT a plan problem", out)    # ...and we do NOT claim there is nothing to fix

    def test_verify_does_NOT_name_MISSING_on_a_genuine_disagreement(self):
        """Both reviewers ran and disagreed — 'iterate the plan + gate' IS the right advice, and the
        MISSING hint would be actively misleading. The hint must be earned, not unconditional."""
        r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                "--reviewer", f"gemini=APPROVE:{self.tx}",
                "--reviewer", f"codex=REQUEST_CHANGES:{self.tx}")
        self.assertEqual(r.returncode, 0, r.stderr)
        v = run("verify", "--plan", self.plan)
        out = v.stdout + v.stderr
        self.assertNotEqual(v.returncode, 0)
        self.assertNotIn("MISSING", out)
        self.assertNotIn("NOT a plan problem", out)

    def test_a_tampered_transcript_field_cannot_pass(self):
        """gemini (#41 review): `.get(k, "")` returns the default only when the key is ABSENT, so an
        explicit `"transcriptSha256": null` yielded None -> str(None) == "None" -> truthy -> PASSED.
        A hand-tampered artifact is precisely this check's threat model, so the one shape an attacker
        would hand-write must not be the one that slips through. Verify at BOTH write and verify."""
        import json as _json
        for bad in (None, "", "   ", 123, ["x"], {"a": 1}, True):
            with self.subTest(transcriptSha256=bad):
                self.assertEqual(self._write().returncode, 0)     # a legitimate artifact first
                vf = self._verdict_file()
                with open(vf) as fh:
                    art = _json.load(fh)
                art["verdict"] = "APPROVE"
                for r in art["reviewers"]:
                    r["status"] = "APPROVE"
                    r["transcriptSha256"] = bad
                with open(vf, "w") as fh:
                    _json.dump(art, fh)
                v = run("verify", "--plan", self.plan)
                self.assertNotEqual(v.returncode, 0,
                                    f"tampered transcriptSha256={bad!r} passed verify")

    def test_the_empty_file_digest_is_rejected_at_verify(self):
        """codex (#41 review): the 0-byte check at parse time guards only the WRITE path. An artifact
        written before that check existed — or hand-edited after a zero-byte capture — carried
        e3b0c442...855 (SHA-256 of nothing) and passed verify. `agy` writes EXACTLY 0 bytes from a
        non-TTY when a review fails, so that digest is the signature of a FAILED review."""
        import hashlib as _h, json as _json
        self.assertEqual(self._write().returncode, 0)
        vf = self._verdict_file()
        with open(vf) as fh:
            art = _json.load(fh)
        art["verdict"] = "APPROVE"
        for r in art["reviewers"]:
            r["status"] = "APPROVE"
            r["transcriptSha256"] = _h.sha256(b"").hexdigest()
        with open(vf, "w") as fh:
            _json.dump(art, fh)
        v = run("verify", "--plan", self.plan)
        self.assertNotEqual(v.returncode, 0, "the empty-file digest passed verify")
        self.assertIn("NON-EMPTY transcript", v.stdout + v.stderr)

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
