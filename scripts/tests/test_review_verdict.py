"""Tests for scripts/review-verdict.py — the plan-digest-bound Combined-verdict artifact."""
import hashlib
import errno
import importlib.util
import shutil
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "review-verdict.py")


def run(*args, cwd=None):
    """`cwd` matters for plan IDENTITY: `_plan_identity` is repo-relative inside a git repo and
    absolute outside one, so a case about two same-named plans has to run from that repo's root."""
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True, cwd=cwd)


def allocated_transcript(directory, plan, reviewer, body, salt=""):
    """Build one transcript the way the allocator does: run-ID name, `.launch`, and a `.plan` binding.

    Module-level so every class shares ONE definition of "what an allocated transcript is". An
    approving write now REFUSES anything else (PR #63 recheck, P1): `_is_per_run_transcript` decides
    whether freshness AND the plan binding run at all, so a legacy-shaped path was exempt from both,
    and two stale shared-`/tmp` reviewer outputs could carry an APPROVE for a plan nobody reviewed.
    Every fixture in this file used bare names — which is precisely why no test caught the hole.
    """
    run_id = hashlib.sha256((reviewer + str(directory) + salt).encode()).hexdigest()[:32]
    path = os.path.join(str(directory), "COREDEV-2619r9-" + reviewer + "-" + run_id + ".txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    launch = path + ".launch"
    with open(launch, "w", encoding="utf-8") as fh:
        # `<run id> <reviewer>` — the allocator records the reviewer so the gate reads the
        # identity from evidence the caller did not write (PR #63 recheck, P1).
        fh.write(run_id + " " + reviewer + "\n")
    stamp = os.stat(path).st_mtime_ns
    # BEFORE the transcript: a record written after it is the stale-dispatch shape freshness rejects.
    os.utime(launch, ns=(stamp - 1_000_000, stamp - 1_000_000))
    with open(plan, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    # The identity is DERIVED from the module under test, not restated as a basename. A bare basename
    # was accepted only while the binding comparison exempted separator-free records — the exemption
    # that also let a transcript bound to one root-level plan approve another with identical bytes
    # (PR #63 recheck). Restating it here would make unrelated cells fail on the binding.
    fh_spec = importlib.util.spec_from_file_location("rv_identity", SCRIPT)
    _rv_identity = importlib.util.module_from_spec(fh_spec)
    fh_spec.loader.exec_module(_rv_identity)
    _identity, _kind = _rv_identity._plan_identity(str(plan))
    with open(path + ".plan", "w", encoding="utf-8") as fh:
        fh.write(digest + "  " + _identity + "\n")
    # `.planbytes` — the bytes the binder hashed and the harnesses stage. `write` now READS it and
    # requires it to match the record: it was written and never read, so a snapshot rewritten after
    # binding fed the reviewer substituted bytes and still produced a validating artifact.
    with open(plan, "rb") as fh:
        _plan_bytes = fh.read()
    with open(path + ".planbytes", "wb") as fh:
        fh.write(_plan_bytes)
        # `.promptsha256` and `.prompt` too. `bind-prompt.py` writes all three together, so a per-run
    # transcript carrying only `.plan` was never produced by the capture helper — and `write` now
    # REQUIRES the prompt binding rather than skipping when it is absent, which was the same
    # "absent means unchecked" fail-open the plan binding exists to close (PR #63 recheck).
    prompt_bytes = ("review prompt for " + os.path.basename(str(plan)) + "\n").encode("utf-8")
    with open(path + ".prompt", "wb") as fh:
        fh.write(prompt_bytes)
    with open(path + ".promptsha256", "w", encoding="utf-8") as fh:
        fh.write(hashlib.sha256(prompt_bytes).hexdigest() + "  prompt.md\n")
    return path


def _load_verdict_module(name):
    """The SHIPPED `review-verdict.py`, loaded as a module."""
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ReviewVerdictTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.plan = os.path.join(self.d, "FEATURE_NAME_PLAN.md")
        with open(self.plan, "w", encoding="utf-8") as fh:
            fh.write("# Plan\nDo the thing.\n")
        # A non-empty transcript. An APPROVING artifact now requires one per reviewer (COREDEV-2492
        # PR review): `--reviewer gemini=APPROVE` with no `:TRANSCRIPT` used to produce a GATE OK on
        # the caller's bare assertion, and a 0-byte file passed because only `isfile` was checked.
        # ALLOCATOR-SHAPED, with a launch record. An approving write now REFUSES any transcript that
        # is not (PR #63 recheck, P1): `_is_per_run_transcript` is the switch deciding whether freshness
        # AND the plan binding run at all, so a legacy-shaped path was exempt from both, and two stale
        # shared-`/tmp` reviewer outputs could carry an APPROVE for a plan nobody reviewed. This fixture
        # used bare `transcript.txt` names — i.e. it only ever exercised the exempt path.
        self.tx = allocated_transcript(self.d, self.plan, "gemini",
                                       "reviewer said things\nVERDICT: APPROVE\n")
        # A SECOND, distinct transcript. An approving artifact requires a DISTINCT transcript per
        # reviewer (codex, #41 review), and until that rule existed this fixture handed the SAME file to
        # both reviewers — so every test wrote the exact artifact shape that rule now forbids, which is
        # precisely why no test caught the hole. `_write` gives each reviewer its own by default.
        self.tx2 = allocated_transcript(self.d, self.plan, "codex",
                                        "the OTHER reviewer said other things\nVERDICT: APPROVE\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def _write(self, verdict="APPROVE_WITH_NOTES",
               reviewers=("gemini=APPROVE", "codex=APPROVE_WITH_NOTES"), reviewed_sha256=None,
               snapshot=True):
        # An APPROVING write now REQUIRES a reviewed-digest binding (round 6): snapshot the plan first by
        # default, unless the test drives the digest itself (reviewed_sha256) or exercises the no-binding
        # path (snapshot=False).
        if snapshot and reviewed_sha256 is None:
            run("snapshot", "--plan", self.plan)
        args = ["write", "--plan", self.plan, "--verdict", verdict]
        for i, r in enumerate(reviewers):
            # Attach a DISTINCT fixture transcript per reviewer unless the case supplied its own path
            # (or deliberately omits one to exercise the missing-transcript rule).
            if ":" not in r:
                r = f"{r}:{self.tx if i == 0 else self.tx2}"
            args += ["--reviewer", r]
        if reviewed_sha256 is not None:
            args += ["--reviewed-sha256", reviewed_sha256]
        return run(*args)

    def test_approving_artifact_requires_a_transcript_per_reviewer(self):
        """An APPROVING verdict must EVIDENCE its approvals: `gemini=APPROVE` with no `:TRANSCRIPT`
        used to write a GATE OK on the caller's bare assertion alone (codex, #41 review)."""
        run("snapshot", "--plan", self.plan)
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
        # approve a_plan — with evidence bound to a_plan, not to the fixture's default plan. The
        # binding compares DIGESTS, and these two plans deliberately share bytes, so this fixture also
        # keeps the test honest: what distinguishes them is the recorded plan identity, not the digest.
        a_tx = allocated_transcript(a_dir, a_plan, "gemini", "a\nVERDICT: APPROVE\n")
        a_tx2 = allocated_transcript(a_dir, a_plan, "codex", "b\nVERDICT: APPROVE\n")
        run("snapshot", "--plan", a_plan)
        r = run("write", "--plan", a_plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{a_tx}", "--reviewer", f"codex=APPROVE:{a_tx2}")
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

    def test_a_NON_DICT_reviewer_entry_cannot_pad_an_approving_quorum(self):
        """`_quorum_problem` (review-verdict.py:86) — the length comparison.

        `names` is built with an `isinstance(r, dict)` filter, so a non-dict entry makes it SHORTER
        than `reviewers`; comparing the two lengths is the only thing that notices. Delete it and the
        malformed entry is silently dropped: the two required names are still present, there are no
        duplicates, and the stray check never sees the non-dict — so a tampered artifact verifies.
        """
        import glob                            # local, matching every sibling cell in this class
        self.assertEqual(self._write().returncode, 0)
        art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
        with open(art, encoding="utf-8") as fh:
            d = json.load(fh)
        d["verdict"] = "APPROVE"
        for r in d["reviewers"]:
            r["status"] = "APPROVE"
        d["reviewers"].append("mallory")          # a bare string where a dict is required
        with open(art, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        v = run("verify", "--plan", self.plan)
        output = v.stdout + v.stderr
        self.assertNotEqual(v.returncode, 0,
                            "a non-dict reviewer entry padded an approving quorum")
        self.assertIn("malformed reviewer entries", output)

    def test_uppercase_and_padded_digests_are_normalized_not_rejected(self):
        """The hex check must not be over-strict: hex is case-insensitive, and the digest is stripped
        before matching, so `A...A` and ` a...a ` are REAL digests in a different skin. A check that
        rejected them would fail a legitimate artifact — a false GATE FAILED is its own outage.

        Re-skinned on the REAL fixture digests when `verify` began re-reading each transcript and
        comparing it to `transcriptSha256`. The old vehicle wrote invented digests (`A`*64, `b`*64)
        while the transcripts on disk kept their true ones, so the evidence check refused — correctly.
        Using the true digest in a different skin is a strictly better test of the same property, and
        it now also proves normalization is applied on BOTH sides of the new comparison: an artifact
        holding a legitimately uppercase digest must still verify.
        """
        import glob

        def _skins(path):
            true = hashlib.sha256(open(path, "rb").read()).hexdigest()
            return (true.upper(), " " + true + " ")

        for skin in (0, 1):
            with self.subTest(skin=("uppercase", "padded")[skin]):
                self.assertEqual(self._write().returncode, 0)
                art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                with open(art, encoding="utf-8") as fh:
                    d = json.load(fh)
                d["verdict"] = "APPROVE"
                for i, r in enumerate(d["reviewers"]):
                    r["status"] = "APPROVE"
                    r["transcriptSha256"] = _skins(self.tx if i == 0 else self.tx2)[skin]
                with open(art, "w", encoding="utf-8") as fh:
                    json.dump(d, fh)
                v = run("verify", "--plan", self.plan)
                self.assertEqual(v.returncode, 0, f"skin {skin} is a real digest: {v.stderr}")

    def test_one_transcript_cannot_back_TWO_approvals(self):
        """Distinct NAMES are not distinct EVIDENCE.

        `--reviewer gemini=APPROVE:/tmp/agy-out.txt --reviewer codex=APPROVE:/tmp/agy-out.txt` — one
        copy-paste slip in the documented two-file flow — recorded identical transcript digests for both
        reviewers and produced `GATE OK — [gemini=APPROVE, codex=APPROVE]`. Every existing check passed
        because they all inspect the LABEL: the duplicate-name rule says "one reviewer cannot stand in
        for the other" while only ever comparing names (codex, #41 review)."""
        run("snapshot", "--plan", self.plan)
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", f"codex=APPROVE:{self.tx}")
        self.assertNotEqual(r.returncode, 0, "one transcript must not back two approvals")
        self.assertIn("DISTINCT transcript", r.stdout + r.stderr)

    def test_identical_content_behind_distinct_capture_ids_is_REJECTED(self):
        """COREDEV-2503 F1 (INVERTS the pre-fix test that wrongly ACCEPTED this). captureId has no
        authenticity binding — `_provenance` only checks it is a non-empty string, and it is read verbatim
        from a `.captureid` sidecar or hand-written into the artifact. So two DISTINCT (possibly FORGED)
        capture IDs behind ONE identical transcript must NOT waive the content-digest floor; otherwise a
        single review (or zero) manufactures a passing gemini+codex approval (GATE OK / exit 0). The floor
        now runs unconditionally: identical bytes are rejected regardless of captureId."""
        id1 = allocated_transcript(self.d, self.plan, "gemini", "one\nVERDICT: APPROVE\n", salt="id1")
        id2 = allocated_transcript(self.d, self.plan, "codex", "two\nVERDICT: APPROVE\n", salt="id2")
        for pth in (id1, id2):
            with open(pth, "w", encoding="utf-8") as fh:
                fh.write("byte-identical review body\nVERDICT: APPROVE\n")   # SAME bytes -> same digest
        with open(id1 + ".captureid", "w", encoding="utf-8") as fh:
            fh.write("forged-A\n")
        with open(id2 + ".captureid", "w", encoding="utf-8") as fh:
            fh.write("forged-B\n")
        run("snapshot", "--plan", self.plan)
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{id1}", "--reviewer", f"codex=APPROVE:{id2}")
        self.assertNotEqual(r.returncode, 0, "distinct captureIds must NOT waive the content-digest floor (F1)")
        self.assertIn("DISTINCT transcript", r.stdout + r.stderr)

    def test_stray_reviewer_is_rejected_on_verify(self):
        """COREDEV-2503 B2: `_quorum_problem` (shared by write AND verify) checked only for MISSING required
        reviewers; the write-path `_reviewer_identity_problem` rejected strays but verify did not — so a
        `{gemini, codex, mallory}` set could pass verification. A stray now fails BOTH paths."""
        import glob
        self.assertEqual(self._write().returncode, 0)
        art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
        with open(art, encoding="utf-8") as fh:
            a = json.load(fh)
        a["verdict"] = "APPROVE"
        a["reviewers"] = [
            {"name": "gemini", "status": "APPROVE", "transcriptSha256": "a" * 64, "transcriptPath": "/x/g"},
            {"name": "codex", "status": "APPROVE", "transcriptSha256": "b" * 64, "transcriptPath": "/x/c"},
            {"name": "mallory", "status": "APPROVE", "transcriptSha256": "d" * 64, "transcriptPath": "/x/m"},
        ]
        with open(art, "w", encoding="utf-8") as fh:
            json.dump(a, fh)
        v = run("verify", "--plan", self.plan)
        self.assertNotEqual(v.returncode, 0, "a stray reviewer must not pass verify")
        self.assertIn("not part of the gate", v.stdout + v.stderr)

    def test_a_symlinked_captureid_sidecar_is_ignored_not_trusted(self):
        """A `.captureid` SYMLINK (a pre-seeded, attacker-chosen value) must NOT be read as authoritative
        provenance — otherwise two copied transcripts could be dressed up as distinct wrapper runs. A
        genuine sidecar is a real regular file (pty-capture writes it O_NOFOLLOW) (round 3: codex)."""
        tx = allocated_transcript(self.d, self.plan, "gemini",
                                  "review body\nVERDICT: APPROVE\n", salt=self._testMethodName)
        real_value = os.path.join(self.d, "planted-value")
        with open(real_value, "w", encoding="utf-8") as fh:
            fh.write("PLANTED-CID\n")
        os.symlink(real_value, tx + ".captureid")   # sidecar is a SYMLINK, not a real file
        run("snapshot", "--plan", self.plan)
        run("write", "--plan", self.plan, "--verdict", "APPROVE_WITH_NOTES",
            "--reviewer", f"gemini=APPROVE:{tx}", "--reviewer", f"codex=APPROVE:{self.tx2}")
        art = json.load(open(os.path.join(self.d, ".verdicts", "FEATURE_NAME_PLAN.md.verdict.json")))
        gem = next(r for r in art["reviewers"] if r["name"] == "gemini")
        self.assertNotIn("captureId", gem, "a symlinked sidecar must not be trusted as a captureId")

    def test_an_oversized_captureid_sidecar_is_refused_not_trusted(self):
        """COREDEV-2503 F8: `_read_regular_file` bounds the read (cap+1, refuse on overflow) — a size-only
        fstat check races a grow-after-check, and a huge regular sidecar is not a genuine provenance token.
        A >64 KiB `.captureid` must be refused (treated as absent), never read wholesale."""
        tx = allocated_transcript(self.d, self.plan, "gemini",
                                  "review body\nVERDICT: APPROVE\n", salt=self._testMethodName)
        with open(tx + ".captureid", "w", encoding="utf-8") as fh:
            fh.write("A" * (65536 + 10) + "\n")   # > 64 KiB regular file
        run("snapshot", "--plan", self.plan)
        run("write", "--plan", self.plan, "--verdict", "APPROVE_WITH_NOTES",
            "--reviewer", f"gemini=APPROVE:{tx}", "--reviewer", f"codex=APPROVE:{self.tx2}")
        art = json.load(open(os.path.join(self.d, ".verdicts", "FEATURE_NAME_PLAN.md.verdict.json")))
        gem = next(r for r in art["reviewers"] if r["name"] == "gemini")
        self.assertNotIn("captureId", gem, "an oversized sidecar must be refused, not trusted (F8)")

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
        run("snapshot", "--plan", self.plan)
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{id1}", "--reviewer", f"codex=APPROVE:{id2}")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DISTINCT capture", r.stdout + r.stderr)

    def test_same_file_for_both_is_rejected_by_path(self):
        """The real accidental mistake: one transcript FILE for both reviewers."""
        run("snapshot", "--plan", self.plan)
        r = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", f"codex=APPROVE:{self.tx}")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("same transcript FILE", r.stdout + r.stderr)

    def test_two_distinct_transcripts_still_pass(self):
        """The fix must not break the legitimate case it guards."""
        tx2 = allocated_transcript(self.d, self.plan, "codex",
                                   "codex said other things\nVERDICT: APPROVE\n")
        _legacy_codex = os.path.join(self.d, "codex.txt")
        with open(tx2, "w", encoding="utf-8") as fh:
            fh.write("codex said other things\nVERDICT: APPROVE\n")
        run("snapshot", "--plan", self.plan)
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
        run("snapshot", "--plan", self.plan)
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
                # `verdict` is a COMBINED verdict; a reviewer STATUS cannot be DISAGREEMENT, so drive
                # the reviewers with a real rejecting status while the combined verdict varies.
                r = run("write", "--plan", self.plan, "--verdict", verdict,
                        "--reviewer", f"gemini=REQUEST_CHANGES:{empty}",
                        "--reviewer", f"codex=REQUEST_CHANGES:{self.tx}")
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

    def test_a_null_status_is_reported_as_corrupt_not_invented_as_a_rejection(self):
        """`.get("status", "")` returns None (not "") for an explicit null, and `str(None)` == "None" —
        so a null-status reviewer was reported as `gemini=NONE (ran, wants plan changes)`, fabricating a
        verdict for a reviewer whose status is unusable (gemini, #42 review). Same `.get`-default trap
        already annotated on transcriptSha256."""
        import glob
        # "INVALID_STATUS" per gemini's suggestion: an unrecognized STRING status is corrupt too — it
        # used to be classified as a considered rejection ("ran, wants plan changes").
        for junk in (None, 123, [], {}, "INVALID_STATUS"):
            with self.subTest(status=junk):
                r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                        "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", "codex=MISSING")
                self.assertEqual(r.returncode, 0, r.stderr)
                art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                with open(art, encoding="utf-8") as fh:
                    a = json.load(fh)
                a["reviewers"] = [{"name": "gemini", "status": junk},
                                  {"name": "codex", "status": "MISSING"}]
                with open(art, "w", encoding="utf-8") as fh:
                    json.dump(a, fh)
                v = run("verify", "--plan", self.plan)
                out = v.stdout + v.stderr
                self.assertNotEqual(v.returncode, 0)
                self.assertNotIn("NONE", out)                  # never invent a status
                self.assertNotIn("wants plan changes", out)    # never invent a rejection
                self.assertIn("CORRUPT", out)

    def test_a_null_reviewer_NAME_is_corrupt_not_rendered_as_the_string_None(self):
        """FOURTH instance of the `.get`-default trap in this file (gemini, #42 review).

        `str(r.get("name"))` renders `"name": null` as the STRING "None", so the hint reported
        "None recorded MISSING (never ran)" — naming a reviewer that does not exist. An unreadable NAME
        is as corrupt as an unreadable STATUS; the invariant is the same."""
        import glob
        for junk in (None, 123, "", "   "):
            with self.subTest(name=junk):
                r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                        "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", "codex=MISSING")
                self.assertEqual(r.returncode, 0, r.stderr)
                art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                with open(art, encoding="utf-8") as fh:
                    a_ = json.load(fh)
                a_["reviewers"] = [{"name": "gemini", "status": "APPROVE",
                                    "transcriptSha256": "a" * 64},
                                   {"name": junk, "status": "MISSING"}]
                with open(art, "w", encoding="utf-8") as fh:
                    json.dump(a_, fh)
                v = run("verify", "--plan", self.plan)
                out = v.stdout + v.stderr
                self.assertNotEqual(v.returncode, 0)
                self.assertNotIn("None recorded MISSING", out)
                self.assertIn("no readable name", out)

    def test_a_non_list_reviewers_field_is_reported_as_corrupt_not_silently_coerced(self):
        """Coercing `reviewers: 5` to [] stopped the TypeError but MASKED the corruption: every count
        went to zero, so the hint fell through and reported a plain non-approving verdict (gemini, #42
        review). Fixing a crash by making it quiet is not fixing it."""
        import glob
        for junk in (5, True, "str", {"a": 1}):
            with self.subTest(reviewers=junk):
                r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                        "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", "codex=MISSING")
                self.assertEqual(r.returncode, 0, r.stderr)
                art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                with open(art, encoding="utf-8") as fh:
                    d = json.load(fh)
                d["reviewers"] = junk
                with open(art, "w", encoding="utf-8") as fh:
                    json.dump(d, fh)
                v = run("verify", "--plan", self.plan)
                out = v.stdout + v.stderr
                self.assertNotEqual(v.returncode, 0)
                self.assertNotIn("Traceback", out)
                self.assertIn("CORRUPT", out)

    def test_an_unrecognized_status_is_corrupt_not_a_rejection(self):
        """`rejecting` was a CATCH-ALL for "not approving and not MISSING", so any status outside the
        VERDICTS vocabulary — defined at the top of this very file and never consulted — was reported as
        a considered rejection. Found independently by BOTH bots (#42 review).

        `WAIVED` is the live case, not a hypothetical: this PR REMOVES that status, so any artifact
        written before it carries a status this code no longer recognizes."""
        import glob
        for st in ("INVALID_STATUS", "WAIVED", "lgtm", "APPROVE_WITH_NITS"):
            with self.subTest(status=st):
                self.assertEqual(self._write(verdict="DISAGREEMENT").returncode, 0)
                art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                with open(art, encoding="utf-8") as fh:
                    d = json.load(fh)
                d["reviewers"] = [{"name": "gemini", "status": st, "transcriptSha256": "a" * 64},
                                  {"name": "codex", "status": "MISSING"}]
                with open(art, "w", encoding="utf-8") as fh:
                    json.dump(d, fh)
                v = run("verify", "--plan", self.plan)
                out = v.stdout + v.stderr
                self.assertNotEqual(v.returncode, 0)
                self.assertIn("CORRUPT", out)
                self.assertIn("not a recognized status", out)
                self.assertNotIn("wants plan changes", out)

    def test_write_enforces_reviewer_identity_for_ALL_verdicts(self):
        """Write rejects duplicate/stray/missing-mandatory reviewers regardless of verdict — the
        symmetry the review asked for, so an artifact verify would call corrupt can never be created
        (full review, #42). Verify's handling of hand-tampered artifacts is covered separately."""
        cases = [
            (("gemini=MISSING", f"gemini=REQUEST_CHANGES:{self.tx}", f"codex=APPROVE:{self.tx2}"),
             "duplicate reviewer"),
            ((f"gemini=APPROVE:{self.tx}", f"codex=APPROVE:{self.tx2}", "octo=MISSING"),
             "not part of the gate"),
            (("gemni=MISSING", f"codex=APPROVE:{self.tx}"), "not part of the gate"),
        ]
        for reviewers, needle in cases:
            with self.subTest(reviewers=reviewers):
                r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                        *[a for rv in reviewers for a in ("--reviewer", rv)])
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(needle, r.stderr)

    def test_a_non_string_or_unknown_top_level_verdict_is_corrupt_not_a_crash(self):
        """`[1,2] not in APPROVING` raises TypeError (unhashable) — verify crashed instead of failing
        cleanly. And a verdict outside the COMBINED vocabulary (stale WAIVED, a bare reviewer status
        like MISSING) is corrupt, not recoverable (codex, #42 review). One controlled result for all."""
        import glob
        for bad in ([1, 2], {"a": 1}, 5, None, "WAIVED", "MISSING", "lgtm"):
            with self.subTest(verdict=bad):
                self.assertEqual(self._write(verdict="DISAGREEMENT").returncode, 0)
                art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
                with open(art, encoding="utf-8") as fh:
                    d = json.load(fh)
                d["verdict"] = bad
                with open(art, "w", encoding="utf-8") as fh:
                    json.dump(d, fh)
                v = run("verify", "--plan", self.plan)
                out = v.stdout + v.stderr
                self.assertNotEqual(v.returncode, 0)
                self.assertNotIn("Traceback", out)
                self.assertIn("not a recognized combined verdict", out)

    def test_a_duplicate_reviewer_is_corrupt_not_contradictory_advice(self):
        """`_quorum_problem` rejects duplicates for APPROVING verdicts only, so a non-approving artifact
        with `gemini=MISSING` AND `gemini=REQUEST_CHANGES` produced advice saying gemini both ran and did
        not run — from one artifact (codex, #42 review)."""
        # WRITE now refuses to create the contradictory artifact at all (write/verify symmetry, full
        # review); verify's handling of a hand-tampered one is covered separately.
        r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                "--reviewer", "gemini=MISSING",
                "--reviewer", f"gemini=REQUEST_CHANGES:{self.tx}",
                "--reviewer", f"codex=APPROVE:{self.tx2}")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("duplicate reviewer", r.stderr)

    def test_a_stray_reviewer_is_corrupt_not_recovery_advice(self):
        """`write` accepts extra reviewers for non-approving verdicts, so `octo=MISSING` alongside the
        required pair produced "octo recorded MISSING ... see 'Unavailable reviewer'" — recovery advice
        for a reviewer that is not part of the gate at all (codex, #42 review)."""
        # WRITE now refuses the stray (write/verify symmetry, full review).
        r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                "--reviewer", f"gemini=APPROVE:{self.tx}",
                "--reviewer", f"codex=REQUEST_CHANGES:{self.tx2}",
                "--reviewer", "octo=MISSING")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not part of the gate", r.stderr)

    def test_a_typod_reviewer_name_is_corrupt_not_recovery_advice(self):
        """`_quorum_problem` enforces the mandatory pair for APPROVING verdicts only, so
        `--reviewer gemni=MISSING` was accepted and verify emitted "gemni recorded MISSING (never ran)"
        — recovery advice about a reviewer that does not exist (codex, #42 review)."""
        # WRITE now refuses the typo (a misspelled name is a stray + the real one is missing).
        r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                "--reviewer", "gemni=MISSING", "--reviewer", f"codex=APPROVE:{self.tx}")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not part of the gate", r.stderr)   # gemni is a stray

    def test_the_MISSING_hint_does_not_assert_never_ran(self):
        """MISSING is overloaded: `review-synthesis` maps BOTH "never returned" AND "empty/unparseable
        transcript" to it (SKILL.md:48). Asserting "never ran" states one of two possible facts as
        certain, and they need different recoveries (codex, #42 review). What IS common to both — no
        plan edit clears either — must survive."""
        r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", "codex=MISSING")
        self.assertEqual(r.returncode, 0, r.stderr)
        v = run("verify", "--plan", self.plan)
        out = v.stdout + v.stderr
        self.assertIn("codex", out)
        self.assertIn("no usable verdict", out)
        self.assertIn("unparseable", out)
        self.assertIn("NOT a plan problem", out)      # the load-bearing half must remain
        self.assertNotIn("(never ran):", out)         # ...but not as a bare assertion of fact

    def test_a_non_object_reviewer_entry_is_reported_as_corrupt(self):
        """An unreadable ENTRY is as corrupt as an unreadable STATUS — the invariant is "never guess".

        `_dicts = [r for r in _revs if isinstance(r, dict)]` filtered non-objects out SILENTLY, so
        `reviewers: ["gemini-approved-trust-me", {...}]` skipped the CORRUPT branch and produced a
        confident "codex recorded MISSING ... NOT a plan problem" derived from a garbage artifact
        (pre-merge audit)."""
        import glob
        r = run("write", "--plan", self.plan, "--verdict", "DISAGREEMENT",
                "--reviewer", f"gemini=APPROVE:{self.tx}", "--reviewer", "codex=MISSING")
        self.assertEqual(r.returncode, 0, r.stderr)
        art = glob.glob(os.path.join(self.d, ".verdicts", "*.json"))[0]
        with open(art, encoding="utf-8") as fh:
            a = json.load(fh)
        a["reviewers"] = ["gemini-approved-trust-me", {"name": "codex", "status": "MISSING"}]
        with open(art, "w", encoding="utf-8") as fh:
            json.dump(a, fh)
        v = run("verify", "--plan", self.plan)
        out = v.stdout + v.stderr
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("CORRUPT", out)
        self.assertIn("not an object", out)
        self.assertNotIn("NOT a plan problem", out)   # must not draw conclusions from garbage

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
        # ATTRIBUTION, not presence. Asserting only that both NAMES appear left the ONE axis this PR
        # exists to protect unpinned: transposing the two f-string interpolations inverts the message to
        # "codex (ran, wants plan changes) AND gemini=REQUEST_CHANGES recorded MISSING" — telling the
        # implementer to address the plan feedback of a reviewer that never ran, and to install the CLI
        # of one that ran fine and rejected the plan — and the whole 54-test suite stayed GREEN
        # (pre-merge audit). Pin each name TO ITS ROLE, not to the output.
        self.assertIn("gemini=REQUEST_CHANGES (ran", out)   # the rejector, named as the rejector
        self.assertIn("codex recorded MISSING", out)        # the absentee, named as the absentee
        self.assertNotIn("NOT a plan problem", out)         # ...and we do NOT claim there is nothing to fix

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
    def test_reviewed_sha256_aborts_when_the_plan_changed_since_review(self):
        """DIGEST-BEFORE-DISPATCH (#44 review §4): the digest is bound at write (after review), so an
        edit between review and write would approve bytes the reviewers never saw. --reviewed-sha256
        (the digest snapshotted BEFORE dispatch) makes write refuse if the plan changed since."""
        import hashlib as _h
        reviewed = _h.sha256(open(self.plan, "rb").read()).hexdigest()
        # edit the plan AFTER "review"
        with open(self.plan, "a", encoding="utf-8") as fh:
            fh.write("\nan edit the reviewers never saw\n")
        r = self._write(reviewed_sha256=reviewed)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CHANGED between review and write", r.stdout + r.stderr)

    def test_reviewed_sha256_matching_current_plan_writes(self):
        import hashlib as _h
        reviewed = _h.sha256(open(self.plan, "rb").read()).hexdigest()
        r = self._write(reviewed_sha256=reviewed)   # no edit -> matches -> writes
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_empty_reviewed_sha256_is_rejected_not_silently_skipped(self):
        """PASSING --reviewed-sha256 EMPTY (e.g. an unset `$REVIEWED_PLAN_SHA256`) must FAIL loudly,
        never falsy-skip the binding. A truthiness check let `""` silently disable the digest guard and
        record an approval bound to no reviewed bytes; omitting the flag stays the backward-compatible
        skip (round 1: gemini + codex)."""
        r = self._write(reviewed_sha256="")
        self.assertNotEqual(r.returncode, 0, "empty --reviewed-sha256 must not silently write")
        self.assertIn("64 hex chars", r.stdout + r.stderr)

    def test_snapshot_then_write_auto_binds_without_the_flag(self):
        """The `snapshot` subcommand persists the pre-review digest to a sidecar so a LATER `write` (a
        separate tool invocation) can bind the approval WITHOUT `--reviewed-sha256` — a shell variable
        could not survive across invocations (round 4: codex). Write auto-reads the sidecar."""
        self.assertEqual(run("snapshot", "--plan", self.plan).returncode, 0)
        r = self._write()   # no reviewed_sha256 flag -> must auto-read the sidecar and bind
        self.assertEqual(r.returncode, 0, r.stderr)
        import hashlib as _h
        art = json.load(open(os.path.join(self.d, ".verdicts", "FEATURE_NAME_PLAN.md.verdict.json")))
        self.assertEqual(art["planSha256"], _h.sha256(open(self.plan, "rb").read()).hexdigest())

    def test_snapshot_then_plan_edit_aborts_the_auto_bound_write(self):
        """A plan edited AFTER the snapshot must abort write (approve-then-edit blocked) even via the
        sidecar path, not just the explicit flag. `snapshot=False` keeps the ORIGINAL snapshot (a re-snap
        would bind the edited bytes)."""
        self.assertEqual(run("snapshot", "--plan", self.plan).returncode, 0)
        with open(self.plan, "a", encoding="utf-8") as fh:
            fh.write("\nan edit the reviewers never saw\n")
        r = self._write(snapshot=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CHANGED between review and write", r.stdout + r.stderr)

    def test_symlinked_snapshot_sidecar_is_ignored(self):
        """A pre-seeded SYMLINK snapshot sidecar (attacker-chosen digest) must NOT bind the approval — a
        genuine snapshot is a real regular file, so the symlink yields NO binding. An APPROVING write with
        no binding then FAILS CLOSED (round 6), so the planted digest can neither bind nor slip through."""
        run("snapshot", "--plan", self.plan)
        side = os.path.join(self.d, ".verdicts", "FEATURE_NAME_PLAN.md.reviewed-sha256")
        os.remove(side)
        planted = os.path.join(self.d, "planted")
        with open(planted, "w", encoding="utf-8") as fh:
            fh.write("0" * 64 + "\n")
        os.symlink(planted, side)
        r = self._write(snapshot=False)
        self.assertNotEqual(r.returncode, 0, "symlinked sidecar -> no binding -> approving must fail closed")
        self.assertIn("requires a reviewed-plan digest", r.stdout + r.stderr)
        self.assertNotIn("0" * 12, r.stdout + r.stderr)      # the planted digest never bound

    def test_fifo_snapshot_sidecar_is_ignored(self):
        """A pre-created FIFO snapshot sidecar (a non-regular file planted at the predictable path) must
        NOT be read as a digest — O_NONBLOCK + fstat reject it, yielding NO binding; an APPROVING write
        then fails closed rather than blocking or trusting it (round 5 + round 6: codex)."""
        run("snapshot", "--plan", self.plan)
        side = os.path.join(self.d, ".verdicts", "FEATURE_NAME_PLAN.md.reviewed-sha256")
        os.remove(side)
        os.mkfifo(side)
        r = self._write(snapshot=False)
        self.assertNotEqual(r.returncode, 0, "FIFO sidecar -> no binding -> approving must fail closed")
        self.assertIn("requires a reviewed-plan digest", r.stdout + r.stderr)

    def test_approving_write_without_any_binding_fails_closed(self):
        """No snapshot sidecar and no --reviewed-sha256 leaves the review->write window unguarded: a
        caller could review v1, edit to v2, and write an APPROVE bound only to v2. An APPROVING verdict
        must therefore REQUIRE a reviewed-digest binding (round 6: codex)."""
        r = self._write(snapshot=False)   # no sidecar, no flag
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("requires a reviewed-plan digest", r.stdout + r.stderr)

    def test_non_approving_write_needs_no_binding(self):
        """A non-approving verdict blocks `implement` regardless, so it does not need the binding."""
        r = self._write(verdict="REQUEST_CHANGES",
                        reviewers=("gemini=REQUEST_CHANGES:%s" % self.tx, "codex=APPROVE:%s" % self.tx2),
                        snapshot=False)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_non_approving_verdict_not_blocked_by_stale_snapshot(self):
        """A non-approving verdict needs NO binding, so a STALE snapshot (plan edited after snapshot) must
        not abort it — the digest-mismatch check is gated on APPROVING (round 7: codex)."""
        run("snapshot", "--plan", self.plan)
        with open(self.plan, "a", encoding="utf-8") as fh:
            fh.write("\nedited after snapshot\n")
        r = self._write(verdict="REQUEST_CHANGES",
                        reviewers=("gemini=REQUEST_CHANGES:%s" % self.tx, "codex=APPROVE:%s" % self.tx2),
                        snapshot=False)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_invalid_utf8_snapshot_sidecar_does_not_traceback(self):
        """A sidecar with invalid UTF-8 bytes must be treated as no-binding (controlled), not raise an
        uncaught UnicodeDecodeError traceback (round 7: codex). With an approving verdict that means the
        fail-closed 'requires a digest' message, not a stack trace."""
        os.makedirs(os.path.join(self.d, ".verdicts"), exist_ok=True)
        side = os.path.join(self.d, ".verdicts", "FEATURE_NAME_PLAN.md.reviewed-sha256")
        with open(side, "wb") as fh:
            fh.write(b"\xff\xfe not utf-8\n")
        r = self._write(snapshot=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("requires a reviewed-plan digest", r.stdout + r.stderr)

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
        self.assertIn("not part of the gate", r.stderr)   # foo/bar are strays

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
        import hashlib as _h
        elsewhere = os.path.join(self.d, "attacker")
        os.makedirs(elsewhere)
        os.symlink(elsewhere, os.path.join(self.d, ".verdicts"))
        # Pass an explicit valid binding so the write clears the reviewed-digest check and REACHES the
        # dir-symlink refusal (a symlinked `.verdicts` blocks `snapshot` from writing a sidecar).
        reviewed = _h.sha256(open(self.plan, "rb").read()).hexdigest()
        r = self._write(reviewed_sha256=reviewed)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("symlink", r.stderr.lower())

    # --- transcript digests ----------------------------------------------------------
    def test_legacy_transcripts_cannot_back_an_APPROVING_verdict(self):
        """The reproduction: two stale legacy files + a fresh snapshot = a gate-passing artifact.

        `_is_per_run_transcript` decides whether freshness AND the plan binding run at all, so a
        legacy-shaped path was exempt from BOTH — and the shapes it exempts are the fixed
        the fixed shared-`/tmp` reviewer outputs an older plugin version left behind. Nothing
        connected them to this plan and nothing checked how old they were, yet they satisfied an
        APPROVE (PR #63 recheck, P1).
        """
        # DISTINCT bodies. Identical ones trip the "same content for two reviewers" rule first, so the
        # test would refuse for a reason that has nothing to do with the finding — a refusal is only
        # evidence if it is the refusal you are claiming.
        legacy = []
        # Neutral names on purpose. The historical filenames are frozen literals the M3.1 inventory
        # forbids reappearing in the tree, and they are not load-bearing here: what reproduces the
        # finding is any shape the allocator would not produce, not those particular names.
        for name, body in (("stale-gemini-output.txt", "stale gemini bytes\nVERDICT: APPROVE\n"),
                           ("stale-codex-output.txt", "stale codex bytes\nVERDICT: APPROVE\n")):
            path = os.path.join(self.d, name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
            legacy.append(path)

        run("snapshot", "--plan", self.plan)
        approving = run("write", "--plan", self.plan, "--verdict", "APPROVE",
                        "--reviewer", f"gemini=APPROVE:{legacy[0]}",
                        "--reviewer", f"codex=APPROVE:{legacy[1]}")
        self.assertNotEqual(0, approving.returncode, approving.stdout)
        self.assertIn("ALLOCATED evidence", approving.stderr)
        self.assertFalse(
            os.path.exists(self._verdict_file()),
            "a refused approving write must leave no artifact behind",
        )

    def test_legacy_transcripts_are_still_accepted_for_a_NON_approving_record(self):
        """Deliberately asymmetric, and the asymmetry is the design.

        A REQUEST_CHANGES record blocks `implement` regardless of its evidence, so refusing legacy
        paths there would discard a legitimate rejection captured before the migration — a false
        refusal with no security benefit. It is only the APPROVING direction that must insist.
        """
        legacy = os.path.join(self.d, "stale-gemini-output.txt")
        with open(legacy, "w", encoding="utf-8") as fh:
            fh.write("older run\nVERDICT: REQUEST_CHANGES\n")
        result = run("write", "--plan", self.plan, "--verdict", "REQUEST_CHANGES",
                     "--reviewer", f"gemini=REQUEST_CHANGES:{legacy}",
                     "--reviewer", f"codex=APPROVE:{self.tx2}")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_transcript_digest_recorded(self):
        # Was a shared-`/tmp` reviewer output — the exact legacy shape an approving verdict may no
        # longer rest on.
        # The property under test (a digest IS recorded) is unchanged; the evidence has to be real.
        t = allocated_transcript(self.d, self.plan, "gemini", "VERDICT: APPROVE\n", salt="digest")
        self._write(reviewers=(f"gemini=APPROVE:{t}", f"codex=APPROVE:{self.tx2}"))
        with open(self._verdict_file(), encoding="utf-8") as fh:
            art = json.load(fh)
        g = next(r for r in art["reviewers"] if r["name"] == "gemini")
        self.assertIn("transcriptSha256", g)
        self.assertEqual(len(g["transcriptSha256"]), 64)




class WriteTextNofollowTest(unittest.TestCase):
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("rv_wtn", SCRIPT)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m

    def test_refuses_a_symlinked_tmp(self):
        """The `.tmp.<pid>` staging file is predictable; a pre-planted symlink there must be refused
        (O_NOFOLLOW), not written THROUGH to the link target (round 8: codex)."""
        m = self._mod()
        d = tempfile.mkdtemp()
        try:
            target = os.path.join(d, "target"); tmp = os.path.join(d, "x.tmp")
            os.symlink(target, tmp)
            with self.assertRaises(OSError):
                m._write_text_nofollow(tmp, "digest")
            self.assertFalse(os.path.exists(target), "must not write through the symlink")
        finally:
            import shutil; shutil.rmtree(d, ignore_errors=True)


class TheRepoBranchStateWriterRefusesPlantedOccupants(unittest.TestCase):
    """`_write_state_file`'s REPO branch — the half most fixtures never reach.

    `_plan_directory_fd` returns a descriptor only inside a git repo; without one the function takes
    the path-based fallback. `ReviewVerdictTest` roots its fixture in `tempfile.mkdtemp()`, so its
    ~70 cells exercise the fallback exclusively — which is why the repo branch's own refusals had no
    coverage and deleting them left the suite green.

    Two guards live here and each needs BOTH of its cells:

      * `.verdicts` OCCUPANT (`follow_symlinks=False`, must be a directory). A symlink and a plain
        file are different halves: `follow_symlinks=True` alone still catches the plain file.
      * `.gitignore` CREATION (`O_CREAT|O_EXCL|O_NOFOLLOW`). `O_EXCL` and `O_NOFOLLOW` are redundant
        on the symlink axis but NOT on the hard-link axis — a hard link is a regular file, so
        `O_NOFOLLOW` is indifferent to it and only `O_EXCL` refuses. A symlink cell alone leaves the
        `O_EXCL`-only drop alive.

    MEASURED, including what these cells CANNOT catch:

        mutant              symlink cell   hard-link cell
        drop O_EXCL             pass           FAIL
        drop O_NOFOLLOW         pass           pass
        drop BOTH               FAIL           FAIL

    Dropping `O_NOFOLLOW` ALONE is undetectable here, and that is correct rather than a gap: on an
    `O_CREAT` open, `O_EXCL` already refuses any existing entry — symlink or not — so the flag is
    subsumed and its removal changes no behaviour. Recorded so a later reader does not add a cell
    chasing a mutant that cannot be killed.
    """

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.repo = os.path.join(self.base, "repo")
        self.plandir = os.path.join(self.repo, "docs", "planning")
        os.makedirs(self.plandir)
        subprocess.run(["git", "init", "-q", self.repo], check=True,
                       capture_output=True, text=True)
        self.plan = os.path.join(self.plandir, "FEATURE_PLAN.md")
        with open(self.plan, "w", encoding="utf-8") as fh:
            fh.write("# Plan\nbytes\n")
        self.verdicts = os.path.join(self.plandir, ".verdicts")
        self.module = _load_verdict_module("rv_repo_branch")

    def _write(self):
        return self.module._write_state_file(
            self.plan, "FEATURE_PLAN.md.reviewed-sha256", "deadbeef\n")

    def test_an_ordinary_repo_branch_write_succeeds(self):
        """The positive control. Without it every refusal below is satisfied by refusing everything."""
        dest = self._write()
        self.assertTrue(os.path.isfile(dest), dest)
        with open(os.path.join(self.verdicts, ".gitignore"), encoding="utf-8") as fh:
            self.assertEqual("*\n", fh.read())

    def test_a_DANGLING_SYMLINKED_gitignore_is_not_written_through(self):
        """`os.path.exists` is FALSE for a dangling symlink, so a "not there, create it" branch
        would follow it. `O_CREAT|O_EXCL|O_NOFOLLOW` refuses instead — and the write continues."""
        victim = os.path.join(self.base, "VICTIM_IGNORE")
        os.mkdir(self.verdicts, 0o700)
        os.symlink(victim, os.path.join(self.verdicts, ".gitignore"))
        dest = self._write()
        self.assertFalse(os.path.exists(victim),
                         "wrote through a dangling symlinked .gitignore")
        self.assertTrue(os.path.isfile(dest),
                        "the refusal swallowed the state write as well")

    def test_a_HARD_LINKED_gitignore_is_not_written_through(self):
        """The half a symlink cell cannot reach. A hard link is a regular file, so `O_NOFOLLOW` is
        indifferent to it; only `O_EXCL` refuses. Dropping `O_EXCL` alone appends to the victim."""
        victim = os.path.join(self.base, "VICTIM_LINK")
        with open(victim, "w", encoding="utf-8") as fh:
            fh.write("PRECIOUS OUTSIDE DATA\n")
        os.mkdir(self.verdicts, 0o700)
        os.link(victim, os.path.join(self.verdicts, ".gitignore"))
        dest = self._write()
        with open(victim, encoding="utf-8") as fh:
            self.assertEqual("PRECIOUS OUTSIDE DATA\n", fh.read(),
                             "wrote through a hard-linked .gitignore")
        self.assertTrue(os.path.isfile(dest))

    def test_a_SYMLINKED_verdicts_dir_is_refused_CLEANLY(self):
        """Asserting the message, not just a non-zero exit: with the occupant check deleted the run
        still fails, but with an ENOTDIR traceback saying "Not a directory" — a cell asserting only
        failure would pass against the mutant."""
        outside = os.path.join(self.base, "outside")
        os.mkdir(outside)
        os.symlink(outside, self.verdicts)
        with self.assertRaises(SystemExit) as caught:
            self._write()
        self.assertIn("refusing a symlinked or non-directory verdict dir", str(caught.exception))
        self.assertEqual([], os.listdir(outside), "wrote into the symlink target")

    def test_a_REGULAR_FILE_verdicts_occupant_is_refused_CLEANLY(self):
        """The half `follow_symlinks=True` would still catch — kept so the guard's two axes are
        asserted separately rather than one standing in for both."""
        with open(self.verdicts, "w", encoding="utf-8") as fh:
            fh.write("not a directory\n")
        with self.assertRaises(SystemExit) as caught:
            self._write()
        self.assertIn("refusing a symlinked or non-directory verdict dir", str(caught.exception))


class COREDEV2603_RepoRelativePlanIdentity(unittest.TestCase):
    """Repo-relative plan identity (COREDEV-2603 item C2).

    THE EXISTING SUITE CANNOT COVER THIS, AND THAT IS THE POINT. `ReviewVerdictTest` roots its
    fixture in `tempfile.mkdtemp()`, which is not a git repo — so every one of its 70 tests
    exercises only the ABSOLUTE fallback branch. An implementer who added the repo-relative code and
    watched the suite stay green would have tested nothing about the new path. Verified: the same
    plan yields `absolute` under mkdtemp and `repo-relative` under a real `git init`.

    So every case below is rooted in a REAL git repo.
    """

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.repo = os.path.join(self.base, "repo")
        self.plandir = os.path.join(self.repo, "docs", "planning")
        os.makedirs(self.plandir)
        subprocess.run(["git", "init", "-q", self.repo], check=True,
                       capture_output=True, text=True)
        self.plan = os.path.join(self.plandir, "FEATURE_NAME_PLAN.md")
        with open(self.plan, "w", encoding="utf-8") as fh:
            fh.write("# Plan\nDo the thing.\n")
        self.tx = allocated_transcript(self.base, self.plan, "gemini", "t1\nVERDICT: APPROVE\n")
        _unused_t1 = os.path.join(self.base, "t1.txt")
        self.tx2 = allocated_transcript(self.base, self.plan, "codex", "t2\nVERDICT: APPROVE\n")
        _unused_t2 = os.path.join(self.base, "t2.txt")
        for f, body in ((self.tx, "gemini said things\n"), (self.tx2, "codex said other things\n")):
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(body)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.base, ignore_errors=True)

    def _gate(self, plan=None):
        """Gate `plan` with evidence bound to THAT plan.

        It reused `self.tx`/`self.tx2` unconditionally, which were bound to the default plan — fine
        while the binding was skipped for legacy-shaped transcripts, wrong now that an approving write
        requires allocated evidence and therefore reaches the binding for every reviewer. Each call
        allocates its own pair, salted by the plan path so two gates never collide.
        """
        plan = plan or self.plan
        directory = os.path.dirname(plan)
        gemini = allocated_transcript(directory, plan, "gemini", "g\nVERDICT: APPROVE\n", salt=plan)
        codex = allocated_transcript(directory, plan, "codex", "c\nVERDICT: APPROVE\n", salt=plan)
        run("snapshot", "--plan", plan)
        return run("write", "--plan", plan, "--verdict", "APPROVE",
                   "--reviewer", f"gemini=APPROVE:{gemini}",
                   "--reviewer", f"codex=APPROVE:{codex}")

    def _artifact(self, plan=None):
        plan = plan or self.plan
        path = os.path.join(os.path.dirname(plan), ".verdicts",
                            os.path.basename(plan) + ".verdict.json")
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), path

    # --- assertion 6: planPathKind is present, correct, and enforced -------------------------
    def test_identity_is_repo_relative_and_kind_records_it(self):
        self.assertEqual(0, self._gate().returncode)
        art, _ = self._artifact()
        self.assertEqual("docs/planning/FEATURE_NAME_PLAN.md", art["planPath"])
        self.assertEqual("repo-relative", art["planPathKind"])
        self.assertEqual(3, art["schemaVersion"], "a new required field needs a schema bump")

    def test_verify_rejects_a_missing_planPathKind(self):
        """A field nothing checks is a comment. Rounds 3-4 required it and asserted it nowhere."""
        self.assertEqual(0, self._gate().returncode)
        art, path = self._artifact()
        del art["planPathKind"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(art, fh)
        r = run("verify", "--plan", self.plan)
        self.assertNotEqual(0, r.returncode)
        self.assertIn("planPathKind", r.stdout + r.stderr)

    def test_verify_rejects_an_unknown_planPathKind(self):
        self.assertEqual(0, self._gate().returncode)
        art, path = self._artifact()
        art["planPathKind"] = "sort-of-relative"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(art, fh)
        self.assertNotEqual(0, run("verify", "--plan", self.plan).returncode)

    def test_verify_rejects_a_kind_inconsistent_with_this_plan(self):
        """The shape a compatibility branch would have had to allow: comparing a relative string
        against an absolute one, passing or failing by accident. Hence schemaVersion 2 -> 3."""
        self.assertEqual(0, self._gate().returncode)
        art, path = self._artifact()
        art["planPathKind"] = "absolute"          # plan still resolves repo-relative
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(art, fh)
        r = run("verify", "--plan", self.plan)
        self.assertNotEqual(0, r.returncode)
        self.assertIn("absolute", r.stdout + r.stderr)

    # --- assertion 3: the regression this item exists to fix ---------------------------------
    def test_an_approval_survives_a_real_worktree_move(self):
        """THE POINT OF THE TICKET. Gating in one worktree and implementing in another failed the
        gate on a genuine five-round approval with byte-identical plan content (COREDEV-2583).
        No test covered it before this one."""
        subprocess.run(["git", "-C", self.repo, "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "plan"], check=True, capture_output=True)
        self.assertEqual(0, self._gate().returncode)
        wt = os.path.join(self.base, "wt")
        subprocess.run(["git", "-C", self.repo, "worktree", "add", "-q", "--detach", wt],
                       check=True, capture_output=True)
        # carry the artifact across, exactly as an operator would
        import shutil
        shutil.copytree(os.path.join(self.plandir, ".verdicts"),
                        os.path.join(wt, "docs", "planning", ".verdicts"))
        moved = os.path.join(wt, "docs", "planning", "FEATURE_NAME_PLAN.md")
        r = run("verify", "--plan", moved)
        self.assertEqual(0, r.returncode,
                         f"a genuine approval must survive the mandated worktree move:\n{r.stdout}{r.stderr}")

    def test_git_dir_as_a_FILE_is_accepted(self):
        """A worktree's `.git` is a FILE, not a directory. A dir-only check resolves a nested
        worktree to the PARENT checkout, making every worktree share one identity."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("rv", SCRIPT)
        rv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rv)
        fake = os.path.join(self.base, "wtlike")
        os.makedirs(os.path.join(fake, "docs", "planning"))
        with open(os.path.join(fake, ".git"), "w", encoding="utf-8") as fh:
            fh.write("gitdir: /elsewhere/.git/worktrees/x\n")
        p = os.path.join(fake, "docs", "planning", "X_PLAN.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("x")
        self.assertEqual(("docs/planning/X_PLAN.md", "repo-relative"), rv._plan_identity(p))

    # --- the property PR #41 added, which must NOT regress ----------------------------------
    def test_same_basename_in_a_different_dir_still_cannot_reuse_the_artifact(self):
        """Repo-relative must still distinguish `docs/planning/a/X` from `docs/planning/b/X`."""
        import shutil
        a = os.path.join(self.plandir, "a"); b = os.path.join(self.plandir, "b")
        os.makedirs(a); os.makedirs(b)
        pa = os.path.join(a, "SAME_PLAN.md"); pb = os.path.join(b, "SAME_PLAN.md")
        for p in (pa, pb):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("identical bytes\n")
        self.assertEqual(0, self._gate(pa).returncode)
        shutil.copytree(os.path.join(a, ".verdicts"), os.path.join(b, ".verdicts"))
        self.assertNotEqual(0, run("verify", "--plan", pb).returncode,
                            "an artifact copied between same-basename plans must NOT verify")

    # --- assertions 4 and 5: the absolute fallback -------------------------------------------
    def test_a_plan_outside_every_git_repo_records_absolute(self):
        outside = os.path.join(self.base, "outside")
        os.makedirs(outside)
        p = os.path.join(outside, "OUT_PLAN.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("x\n")
        self.assertEqual(0, self._gate(p).returncode)
        art, _ = self._artifact(p)
        self.assertEqual("absolute", art["planPathKind"])
        self.assertTrue(os.path.isabs(art["planPath"]))
        self.assertEqual(0, run("verify", "--plan", p).returncode, "the fallback must round-trip")

    def test_no_recorded_identity_ever_begins_with_dotdot(self):
        """Defence-in-depth, and labelled as such: given `_repo_root` returns an ANCESTOR, `relpath`
        cannot escape, so removing the guard is unobservable (executed both ways). Asserted on the
        stored string anyway, because emitting a `../` identity would be far worse than two
        comparisons."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("rv", SCRIPT)
        rv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rv)
        for p in (self.plan, os.path.join(self.base, "OUT_PLAN.md")):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("x")
            ident, _kind = rv._plan_identity(p)
            with self.subTest(plan=p):
                self.assertFalse(ident.startswith(".."), f"identity escaped the root: {ident!r}")


class PlanIdentityAndOversizedSnapshot(unittest.TestCase):
    """Two write-path defects the recheck found in the binding (PR #63 recheck).

    Both are the same shape as defects already fixed one layer away, which is why they are worth
    pinning: the digest-only comparison repeats PR #41's basename shortcut, and the capped read repeats
    the "a guard that refuses valid work" failure the absolute-path fix corrected.
    """

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "."], cwd=self.d, check=True)
        for sub in ("a", "b"):
            os.makedirs(os.path.join(self.d, "docs", "planning", sub))
            with open(os.path.join(self.d, "docs", "planning", sub, "SAME_PLAN.md"), "w") as fh:
                fh.write("# Identical bytes\n")

    def _allocated(self, reviewer, bound_relative):
        run_id = hashlib.sha256((reviewer + bound_relative).encode()).hexdigest()[:32]
        path = os.path.join(self.d, f"COREDEV-2619r9-{reviewer}-{run_id}.txt")
        with open(path, "w") as fh:
            fh.write(reviewer + "\nVERDICT: APPROVE\n")
        with open(path + ".launch", "w") as fh:
            fh.write(run_id + " " + reviewer + "\n")
        stamp = os.stat(path).st_mtime_ns
        os.utime(path + ".launch", ns=(stamp - 1_000_000, stamp - 1_000_000))
        with open(os.path.join(self.d, bound_relative), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        with open(path + ".plan", "w") as fh:
            fh.write(f"{digest}  {bound_relative}\n")
        with open(os.path.join(self.d, bound_relative), "rb") as fh:
            bound_bytes = fh.read()
        with open(path + ".planbytes", "wb") as fh:
            fh.write(bound_bytes)
        return path

    def _bind_prompt(self, path, payload=b"review prompt\n"):
        with open(path + ".prompt", "wb") as fh:
            fh.write(payload)
        with open(path + ".promptsha256", "w") as fh:
            fh.write(hashlib.sha256(payload).hexdigest() + "  prompt.md\n")

    def _write(self, plan_relative, transcripts):
        run("snapshot", "--plan", plan_relative, cwd=self.d)
        return run("write", "--plan", plan_relative, "--verdict", "APPROVE",
                   "--reviewer", f"gemini=APPROVE:{transcripts[0]}",
                   "--reviewer", f"codex=APPROVE:{transcripts[1]}", cwd=self.d)

    def test_identical_bytes_in_two_plans_cannot_be_crossed(self):
        """The digest cannot discriminate here, so the recorded identity has to."""
        a = "docs/planning/a/SAME_PLAN.md"
        transcripts = [self._allocated("gemini", a), self._allocated("codex", a)]
        for path in transcripts:
            self._bind_prompt(path)

        crossed = self._write("docs/planning/b/SAME_PLAN.md", transcripts)
        self.assertNotEqual(0, crossed.returncode, crossed.stdout)
        self.assertIn("bound to a different plan", crossed.stderr)

        matched = self._write(a, transcripts)
        self.assertEqual(0, matched.returncode, matched.stderr)

    def test_a_BLANK_recorded_identity_is_refused_not_treated_as_absent(self):
        """`.strip()` made a whitespace-only field indistinguishable from no field (PR #63 recheck, P2).

        The identity comparison exists because two distinct plans with identical bytes share a digest.
        Writing spaces into the record's path field made `bound_identity` empty, which took the "nothing
        recorded" branch — so the comparison could be switched OFF by a blank, and the byte-identical
        crossing it was added to stop worked again. Same "absent means unchecked" shape as a deleted
        sidecar, spelled with a space.

        The plan under test is one half of the identical-bytes pair above, so the digest cannot
        discriminate and only the identity can — if the blank were tolerated, this write would succeed.
        """
        a = "docs/planning/a/SAME_PLAN.md"
        transcripts = [self._allocated("gemini", a), self._allocated("codex", a)]
        for path in transcripts:
            self._bind_prompt(path)
            with open(os.path.join(self.d, a), "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            with open(path + ".plan", "w") as fh:
                fh.write(f"{digest}   \n")          # present, non-empty by the grammar, and blank

        blanked = self._write("docs/planning/b/SAME_PLAN.md", transcripts)
        self.assertNotEqual(0, blanked.returncode, blanked.stdout)
        self.assertIn("BLANK plan identity", blanked.stderr)

    def test_a_SUBSTITUTED_plan_snapshot_is_refused_at_write_time(self):
        """`.planbytes` was written by the binder and read by NOTHING (PR #63 recheck, P1).

        Both harnesses stage those bytes — they are what the reviewer actually read — and until now no
        check downstream ever compared them to the record again. So a snapshot rewritten after binding
        fed the reviewer substituted bytes and still produced an artifact that validated: the record
        and the live plan agreed with each other and neither described what was reviewed.

        HONEST SCOPE. This closes the uncoordinated family — a snapshot substituted and left, or
        restored while the record was not. A same-account process that replaces BOTH sidecars
        coherently and restores BOTH before the verdict is written is not defended against, and cannot
        be by any file-based binding: every anchor this program could read is a file that attacker can
        rewrite, including the transcript whose digest the artifact records.
        """
        a = "docs/planning/a/SAME_PLAN.md"
        transcripts = [self._allocated("gemini", a), self._allocated("codex", a)]
        for path in transcripts:
            self._bind_prompt(path)
        with open(transcripts[0] + ".planbytes", "wb") as fh:
            fh.write(b"# Plan\nSUBSTITUTED BYTES THE REVIEWER ACTUALLY READ\n")

        result = self._write(a, transcripts)
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("does not match its own record", result.stderr)

    def test_a_DELETED_plan_snapshot_is_refused_rather_than_skipped(self):
        """Absent means unchecked — the shape this whole family of bindings exists to close."""
        a = "docs/planning/a/SAME_PLAN.md"
        transcripts = [self._allocated("gemini", a), self._allocated("codex", a)]
        for path in transcripts:
            self._bind_prompt(path)
        os.unlink(transcripts[1] + ".planbytes")

        result = self._write(a, transcripts)
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("no bound plan snapshot", result.stderr)

    def test_a_PLAN_larger_than_the_trusted_read_cap_still_persists(self):
        """My own regression, in the file that carries the warning about it (PR #63 recheck, P1).

        `_read_regular_file_bytes` caps at `_MAX_TRUSTED_READ_BYTES + 1` to bound UNTRUSTED PARSING of
        small sidecars. Hashing the bound plan snapshot through it truncated every plan over 64 KiB to
        its prefix, so the digest could never match its own record and EVERY approving persist for such
        a plan was rejected as a modified snapshot. Five plans in this checkout are over the cap — the
        largest is 204 KB — so this was not hypothetical. The prompt-snapshot check one field over had
        already been fixed for exactly this and carries the comment saying so; I copied the wrong
        sibling. A digest reads every byte and holds none, which is why the cap does not apply to it.
        """
        a = "docs/planning/a/SAME_PLAN.md"
        oversized = ("# Plan\n" + ("x" * 100 + "\n") * 1000).encode()   # ~100 KB, over the cap
        with open(os.path.join(self.d, a), "wb") as fh:
            fh.write(oversized)
        transcripts = [self._allocated("gemini", a), self._allocated("codex", a)]
        for path in transcripts:
            self._bind_prompt(path)

        result = self._write(a, transcripts)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_prompt_larger_than_the_trusted_read_cap_still_persists(self):
        """A guard that refuses valid work is a guard someone switches off.

        `_read_regular_file_bytes` caps at `_MAX_TRUSTED_READ_BYTES + 1`, so a legitimate prompt above
        that hashed only its prefix and the write reported the snapshot as modified — an otherwise
        valid approving review could never be recorded. The cap bounds untrusted PARSING; a digest
        reads every byte and keeps none, so it is not what the cap protects.
        """
        a = "docs/planning/a/SAME_PLAN.md"
        oversized = b"x" * (65537 + 4096)
        transcripts = [self._allocated("gemini", a), self._allocated("codex", a)]
        for path in transcripts:
            self._bind_prompt(path, oversized)

        result = self._write(a, transcripts)
        self.assertEqual(0, result.returncode, result.stderr)


class TheVerdictWritersRefuseAPlantedTarget(unittest.TestCase):
    """Both writers under `.verdicts/` could be aimed at an outside file (PR #63 recheck, P2).

    The same two mistakes that were found and fixed in `pty-capture.py`'s non-allocated write survived
    here, in the tool that writes the gate's own artifact:

      * THE ARTIFACT. `<dest>.tmp.<pid>` is a predictable staging name, and a HARD LINK is a regular
        file — so `O_NOFOLLOW` accepted one, and `O_TRUNC` emptied the victim AT open(), before any
        check could look. The refusal, if it came, came after the damage.
      * THE SELF-IGNORING `.gitignore`. `os.path.exists` is FALSE for a DANGLING symlink, so a planted
        `.verdicts/.gitignore -> <victim>` took the "not there, create it" branch and `open(…, "w")`
        wrote through the link.
    """

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.module = _load_verdict_module("rv_planted_targets")

    def test_a_hard_linked_staging_path_is_refused_with_the_victim_INTACT(self):
        victim = os.path.join(self.d, "PRECIOUS")
        with open(victim, "w", encoding="utf-8") as fh:
            fh.write("PRECIOUS OUTSIDE DATA\n")
        target = os.path.join(self.d, "artifact.json.tmp.999")
        os.link(victim, target)

        with self.assertRaises(OSError) as caught:
            self.module._write_text_nofollow(target, "attacker artifact")
        self.assertEqual(errno.EMLINK, caught.exception.errno)
        with open(victim, encoding="utf-8") as fh:
            self.assertEqual("PRECIOUS OUTSIDE DATA\n", fh.read(),
                             "the victim was emptied — the refusal came after O_TRUNC")

    def test_a_hard_linked_DESCRIPTOR_RELATIVE_target_is_refused_with_the_victim_INTACT(self):
        """The same guard, in the OTHER writer of the family.

        `_write_text_nofollow` (path-relative) is covered by the cell above. `_write_text_at`
        (descriptor-relative) carries the IDENTICAL `st_nlink != 1` refusal and had no test —
        deleting it left the whole suite green. One member of a two-member family tested is the
        shape this campaign keeps finding, so the family is asserted together here.

        The second assertion is what makes it discriminating: with the guard deleted the victim is
        emptied by `ftruncate` and rewritten, so checking the bytes proves the refusal came BEFORE
        the damage rather than merely that an error was raised.
        """
        victim = os.path.join(self.d, "PRECIOUS_AT")
        with open(victim, "w", encoding="utf-8") as fh:
            fh.write("PRECIOUS OUTSIDE DATA\n")
        state = os.path.join(self.d, "state_at")
        os.mkdir(state)
        name = "artifact.json.tmp.999"
        os.link(victim, os.path.join(state, name))

        state_fd = os.open(state, os.O_RDONLY)
        try:
            with self.assertRaises(OSError) as caught:
                self.module._write_text_at(state_fd, name, "attacker artifact")
        finally:
            os.close(state_fd)
        self.assertEqual(errno.EMLINK, caught.exception.errno)
        with open(victim, encoding="utf-8") as fh:
            self.assertEqual("PRECIOUS OUTSIDE DATA\n", fh.read(),
                             "the victim was emptied — the refusal came after ftruncate")

    def test_an_ordinary_rewrite_still_works_and_leaves_no_stale_tail(self):
        """Discrimination, and the deletion test for dropping O_TRUNC.

        Removing O_TRUNC is what lets the link check run before any damage; the explicit `ftruncate`
        is what still bounds an honest overwrite. Without it a shorter second artifact would carry the
        first one's tail — the same defect this repo already fixed once in the transcript writer.
        """
        path = os.path.join(self.d, "artifact.json")
        self.module._write_text_nofollow(path, "x" * 400)
        self.module._write_text_nofollow(path, "short")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual("short", fh.read())

    def test_a_DANGLING_gitignore_symlink_is_not_written_through(self):
        verdicts = os.path.join(self.d, ".verdicts")
        os.mkdir(verdicts, 0o700)
        victim = os.path.join(self.d, "OUTSIDE.txt")
        os.symlink(victim, os.path.join(verdicts, ".gitignore"))
        self.assertFalse(os.path.exists(victim))

        self.module._ensure_secure_dir(verdicts)

        self.assertFalse(os.path.exists(victim),
                         "the self-ignoring write followed a dangling symlink out of .verdicts")

    def test_a_missing_gitignore_is_still_created(self):
        """Positive control: the refusal must be about the link, not about writing at all."""
        verdicts = os.path.join(self.d, ".verdicts")
        self.module._ensure_secure_dir(verdicts)
        with open(os.path.join(verdicts, ".gitignore"), encoding="utf-8") as fh:
            self.assertEqual("*\n", fh.read())


class LegacyNamesAreNotMistakenForAllocations(unittest.TestCase):
    """Classification must key on the WHOLE allocator basename, not just its hex suffix.

    `_TRANSCRIPT_RUN_ID` matches any name ending `-<32 hex>.txt`, and the classifier's own docstring
    names the realistic collision: a digest-suffixed file like `review-<md5>.txt`, MD5 hex being exactly
    32 characters. Such a file was then treated as per-run, REQUIRED to carry a `.launch`, and rejected
    without one — so a legitimate custom or historical transcript became unusable (PR #63 recheck, P2).

    The narrowing keeps the property the docstring refuses to give up: the basename travels with the
    file, so an allocated transcript that was copied or moved still classifies as per-run. Conditioning
    on the DIRECTORY would have lost exactly that, which is the fail-open the docstring rejects — and
    this is why the fix is on the name, not the location.
    """

    def _module(self):
        spec = importlib.util.spec_from_file_location("rv_names", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules["rv_names"] = module
        spec.loader.exec_module(module)
        return module

    def test_the_allocator_shape_classifies_as_per_run(self):
        module = self._module()
        for name in ("COREDEV-2619r9-codex-" + "a" * 32 + ".txt",
                     "COREDEV-2619r12-gemini-" + "b" * 32 + ".txt"):
            with self.subTest(name=name):
                self.assertTrue(module._is_per_run_transcript("/anywhere/" + name),
                                "a real allocated name must stay per-run wherever it lives")

    def test_a_digest_suffixed_legacy_name_does_not(self):
        """The named collision. Before the narrowing this demanded a `.launch` and failed without one."""
        module = self._module()
        for name in ("review-" + "c" * 32 + ".txt", "backup-" + "d" * 32 + ".txt"):
            with self.subTest(name=name):
                self.assertFalse(module._is_per_run_transcript("/anywhere/" + name),
                                 "a digest-suffixed legacy file was classified as an allocation")

    def test_a_launch_record_still_forces_the_per_run_branch(self):
        """The narrowing must not weaken the third branch: a sibling record is proof of provenance,
        and planting one only makes the gate STRICTER, never laxer."""
        module = self._module()
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        odd = os.path.join(directory, "review-" + "c" * 32 + ".txt")
        open(odd, "w").close()
        open(odd + ".launch", "w").close()
        self.assertTrue(module._is_per_run_transcript(odd))


class OneArmCannotSatisfyTheDualGate(unittest.TestCase):
    """Two separately allocated GEMINI runs satisfied the mandatory gemini+codex quorum.

    Every distinctness rule asks whether the two entries DIFFER — distinct paths, digests, capture IDs —
    and two real gemini runs do differ. None asked what either transcript actually WAS, so one arm
    satisfied the single thing the gate exists to require (PR #63 recheck, P1 — reproduced).

    The allocator encodes the reviewer in the filename it reserves, so the evidence already carried the
    answer; it simply was not read. Same "recorded and never compared" shape as the prompt digest and
    the bound plan identity, both closed earlier in this release.
    """

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "."], cwd=self.d, check=True)
        os.makedirs(os.path.join(self.d, "docs", "planning"))
        self.plan_relative = "docs/planning/FEATURE_PLAN.md"
        with open(os.path.join(self.d, self.plan_relative), "w") as fh:
            fh.write("# Plan\n")

    def _allocated(self, reviewer, salt):
        run_id = hashlib.sha256((reviewer + salt).encode()).hexdigest()[:32]
        path = os.path.join(self.d, f"COREDEV-9999r1-{reviewer}-{run_id}.txt")
        with open(path, "w") as fh:
            fh.write(f"{reviewer} {salt}\nVERDICT: APPROVE\n")
        with open(path + ".launch", "w") as fh:
            fh.write(run_id + " " + reviewer + "\n")
        stamp = os.stat(path).st_mtime_ns
        os.utime(path + ".launch", ns=(stamp - 1_000_000, stamp - 1_000_000))
        with open(os.path.join(self.d, self.plan_relative), "rb") as fh:
            plan_bytes = fh.read()
        digest = hashlib.sha256(plan_bytes).hexdigest()
        with open(path + ".plan", "w") as fh:
            fh.write(f"{digest}  {self.plan_relative}\n")
        with open(path + ".planbytes", "wb") as fh:
            fh.write(plan_bytes)
        payload = f"prompt {salt}\n".encode()
        with open(path + ".prompt", "wb") as fh:
            fh.write(payload)
        with open(path + ".promptsha256", "w") as fh:
            fh.write(hashlib.sha256(payload).hexdigest() + "  prompt.md\n")
        return path

    def _write(self, gemini, codex, verdict="APPROVE"):
        run("snapshot", "--plan", self.plan_relative, cwd=self.d)
        return run("write", "--plan", self.plan_relative, "--verdict", verdict,
                   "--reviewer", f"gemini=APPROVE:{gemini}",
                   "--reviewer", f"codex=APPROVE:{codex}", cwd=self.d)

    def test_two_gemini_runs_cannot_pass_as_gemini_and_codex(self):
        result = self._write(self._allocated("gemini", "one"), self._allocated("gemini", "two"))
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("mislabelled", result.stderr)

    def test_a_RENAMED_leaf_whose_FILENAME_disagrees_with_its_allocator_record_is_refused(self):
        """`_reviewer_identity_mismatch`'s SECOND arm (review-verdict.py:1076) — the rename itself.

        The first arm compares ATTESTED against DECLARED. This one compares the FILENAME against the
        attested record, and only fires when the other two agree: rename the leaf and `.launch` still
        attests `gemini`, the caller still declares `gemini`, so every other check passes while the
        evidence's own name says something else. Deleting this arm left the suite green.

        The comment above it calls that "the rename attack itself" — and it had no test.
        """
        gemini = self._allocated("gemini", "g")
        renamed = gemini.replace("-gemini-", "-codex-")
        for suffix in ("", ".launch", ".plan", ".planbytes", ".prompt", ".promptsha256"):
            os.rename(gemini + suffix, renamed + suffix)
        result = self._write(renamed, self._allocated("codex", "c"))
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("the leaf was renamed", result.stderr)

    def test_a_genuine_pair_still_passes(self):
        """Control: the rule must reject MISLABELLING, not the dual review itself."""
        result = self._write(self._allocated("gemini", "g"), self._allocated("codex", "c"))
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_non_approving_record_is_not_subject_to_it(self):
        """Deliberate asymmetry, matching the allocated-evidence rule.

        The bypass is "one arm satisfies the mandatory TWO-arm gate", which is a property of an
        APPROVAL. A non-approving record blocks `implement` whatever its labels say, so refusing one
        would discard a legitimate REQUEST_CHANGES for no gain.
        """
        result = run("write", "--plan", self.plan_relative, "--verdict", "REQUEST_CHANGES",
                     "--reviewer", f"gemini=REQUEST_CHANGES:{self._allocated('gemini', 'x')}",
                     "--reviewer", f"codex=APPROVE:{self._allocated('gemini', 'y')}", cwd=self.d)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
