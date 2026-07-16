"""Unit tests for scripts/review/reviewer-roster.sh (COREDEV-2490).

Mirrors the shipped test_build_verify.py precedent: drives the real script with a fabricated capture
tree, no Xcode / no app / no network. The point of these tests is ONE property:

    No on-disk state may ever yield a clean pass. The script emits RATCHET only for a valid BLOCKED
    sidecar; EVERYTHING else is UNATTRIBUTED (-> the consumer re-dispatches that reviewer).

`TRUST` is never printed, by design — so a test asserting its absence is a real assertion, not a
tautology: it pins that no future edit can add a disk state that certifies.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_SCRIPT = os.path.join(_ROOT, "scripts", "review", "reviewer-roster.sh")
AGENT = "security-reviewer"
VALID = ("security-reviewer", "concurrency-reviewer", "ux-perf-reviewer",
         "accessibility-auditor", "prompt-review")


class _RosterFixture:
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.repo = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", self.repo], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # A deterministic branch so context_branch_slug is stable.
        subprocess.run(["git", "-C", self.repo, "checkout", "-q", "-b", "feat/COREDEV-2490-t"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def _env(self):
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_DATA"] = self.home  # context_base() honours this
        return env

    def _run_held(self, held):
        """Run the script with `held` (the reviewers the orchestrator asserts it HOLDS) on stdin."""
        p = subprocess.run(
            ["bash", _SCRIPT], input="\n".join(held), cwd=self.repo,
            env=self._env(), capture_output=True, text=True, timeout=30,
        )
        return p.returncode, p.stdout

    def _run(self, unresolved):
        """Classify `unresolved` by asserting the COMPLEMENT as held.

        The script's stdin is the HELD list, not the unresolved one — the polarity is inverted ON
        PURPOSE (COREDEV-2490 adversarial pass): with an unresolved-list stdin the DEFAULT was exit 0
        ("nothing to act on"), and an attacker reproduced a clean pass for a reviewer that never ran
        without touching the script — `printf '%s\n' "${UNRESOLVED[@]}"` on an unset array emits one
        blank line, which the loop skips. Silence must classify EVERYONE, so only a positive assertion
        of what you hold can shrink the roster. This helper keeps the tests written in terms of the
        thing under test (who is unresolved) while exercising the real interface."""
        held = [a for a in VALID if a not in unresolved]
        return self._run_held(held)

    @staticmethod
    def _directives(out):
        """Output minus the ROSTER-INPUT echo — the directive lines the consumer acts on."""
        return [ln for ln in out.strip().splitlines() if not ln.startswith("ROSTER-INPUT")]

    def _round_dir(self, n=1):
        """Resolve the real capture dir via the shipped context.sh, so the tests bind to production
        path logic rather than re-deriving it (a re-derivation would pass while prod broke)."""
        out = subprocess.run(
            ["bash", "-c", f'. "{_ROOT}/scripts/lib/context.sh"; '
                           f'printf "%s" "$(context_reviews_dir)/$(context_branch_slug "$(context_branch)")"'],
            cwd=self.repo, env=self._env(), capture_output=True, text=True,
        ).stdout.strip()
        d = os.path.join(out, "round-%d" % n)
        os.makedirs(d, exist_ok=True)
        return d

    def _capture(self, status=None, findings="[]", agent=AGENT, n=1, raw_status=None):
        d = self._round_dir(n)
        with open(os.path.join(d, agent + ".json"), "w") as fh:
            fh.write(findings)
        if raw_status is not None:
            with open(os.path.join(d, agent + ".status"), "w") as fh:
                fh.write(raw_status)
        elif status is not None:
            with open(os.path.join(d, agent + ".status"), "w") as fh:
                json.dump(status, fh)
        return d



class RosterTestCase(_RosterFixture, unittest.TestCase):
    # --- the normal path: this is the alert-fatigue defence -------------------------------------
    def test_all_five_held_is_zero_cost(self):
        """Path A: the orchestrator holds all five reports -> it names all five -> zero re-dispatch.
        If this ever fails, every clean review pays re-dispatches and the control gets ignored."""
        rc, out = self._run([])                      # nothing unresolved => all five asserted held
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "ROSTER-INPUT: held = " + " ".join(VALID))

    def test_empty_stdin_classifies_everyone_and_fails_closed(self):
        """THE REGRESSION THAT MOTIVATED THE INVERSION. Saying nothing must classify ALL FIVE, never
        exit 0. Under the old unresolved-list polarity this exact input exited 0 with no output, so the
        gate silently never fired — a reviewer that never ran read as a clean pass, with the script
        itself entirely correct. Silence is not evidence of holding anything."""
        rc, out = self._run_held([])
        self.assertEqual(rc, 3, f"empty stdin must fail CLOSED, got rc={rc}: {out!r}")
        for a in VALID:
            self.assertIn(f"UNATTRIBUTED {a} ", out)

    def test_a_hostile_or_typod_held_name_is_rejected_not_resolved(self):
        """The HELD list is the ONLY untrusted-name entry point (the roster is model-assembled), and
        every name in it is a POSITIVE claim that shrinks the classified set — so anything not exactly
        a known reviewer must be exit 4 (-> the caller's uncertainty branch), never a silent
        resolution of the reviewer it resembles.

        Covers the classes earlier rounds found by execution, now at the real boundary:
          * globs — `${_rest#* $agent }` once expanded $agent as a PATTERN, so `*` MATCHED (codex R6)
          * embedded CR — `${agent%%[$'\r']*}` cut at the first CR, so `x\rforged` became `x` (codex R8)
          * internal whitespace — `tr -d '[:space:]'` deleted it, so `se curity-reviewer` became real (R7)
          * traversal / case / trailing junk
        """
        for bad in ("security-reviewr", "SECURITY-REVIEWER", "security reviewer",
                    "se curity-reviewer", "*", "[a-z]*", "security-review*", "?",
                    "security-reviewer\rforged", "forged\rsecurity-reviewer",
                    "../../../etc/passwd", "security-reviewer.json"):
            with self.subTest(held=bad):
                rc, out = self._run_held([bad])
                self.assertEqual(rc, 4, f"{bad!r} was accepted as held: {out!r}")
                self.assertIn("ROSTER-INPUT-INVALID", out)
                self.assertNotIn("\r", out)          # a rejected name must not break the grammar
                self.assertEqual(len(out.strip().splitlines()), 1, f"grammar broken: {out!r}")
                # exit 4 must classify NOBODY: it is an input error, not a verdict
                self.assertNotIn("UNATTRIBUTED", out)
                self.assertNotIn("RATCHET", out)

    def test_surrounding_whitespace_in_a_held_name_is_normalised(self):
        """A trailing space or a CRLF `\r` is noise, not a different name: strip it, then exact-match.
        Rejecting these would break a legitimate roster written on a CRLF host."""
        for name in (f"{AGENT} ", f"  {AGENT}", f"{AGENT}\r"):
            with self.subTest(held=name):
                rc, out = self._run_held([name])
                self.assertNotEqual(rc, 4, f"{name!r} should normalise, not reject: {out!r}")
                self.assertIn(f"ROSTER-INPUT: held = {AGENT}", out)

    def test_a_duplicated_held_name_is_rejected(self):
        rc, out = self._run_held([AGENT, AGENT])
        self.assertEqual(rc, 4)
        self.assertIn("dup:", out)

    def test_roster_input_is_echoed_for_the_transcript(self):
        """What was asserted as held must be recorded, not inferred."""
        rc, out = self._run_held([AGENT])
        self.assertIn(f"ROSTER-INPUT: held = {AGENT}", out)

    # --- the ONLY trusted state ----------------------------------------------------------------
    def test_valid_blocked_ratchets(self):
        self._capture({"status": "BLOCKED", "agent": AGENT, "blockerDescription": "no repo access"})
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 2)
        self.assertIn(f"RATCHET {AGENT} BLOCKED no repo access", out)
        self.assertNotIn("UNATTRIBUTED", out)

    def test_blocked_without_description_still_ratchets(self):
        self._capture({"status": "BLOCKED", "agent": AGENT})
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 2)
        self.assertIn(f"RATCHET {AGENT} BLOCKED", out)

    # --- EVERYTHING else is UNATTRIBUTED. This table IS the fix. --------------------------------
    def test_complete_does_not_certify(self):
        """The heart of COREDEV-2490: a captured COMPLETE + [] used to read as a clean pass."""
        self._capture({"status": "COMPLETE", "agent": AGENT})
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn(f"UNATTRIBUTED {AGENT} complete-does-not-certify", out)

    def test_partial_does_not_certify_and_forwards_remaining(self):
        """R5-2: the roster is the ONLY sidecar reader, so it must forward `remaining` or nothing can
        preserve it — 'it cannot preserve safety metadata it never sees'.

        `remaining` is a CAPPED STRING as the producer actually persists it (capture.py:362,
        `cap(redact_pii(field[1]), STATUS_FIELD_CAP)`), NOT a list. My first version of this test used a
        list and therefore tested a contract that does not exist (codex, R7)."""
        self._capture({"status": "PARTIAL", "agent": AGENT,
                       "remaining": "A.swift B.swift"})
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn(f"UNATTRIBUTED {AGENT} partial-does-not-certify", out)
        self.assertIn(f"REMAINING {AGENT} A.swift B.swift", out)

    def test_remaining_of_a_wrong_type_is_not_coerced(self):
        """STRINGS ONLY. Every status field the producer persists goes through
        `cap(redact_pii(...))` (capture.py:362), so it is always a string. A list/dict/bool **or a
        number** is malformed input: forward nothing rather than invent a contract.
        (codex R8: my first fix rejected list/dict/bool but still str()-ed numerics — an int
        `remaining` is not a file list.)"""
        for bad in ([], ["A.swift"], {"a": 1}, True, 42, 3.14, 0):
            with self.subTest(remaining=bad):
                self._capture({"status": "PARTIAL", "agent": AGENT, "remaining": bad})
                rc, out = self._run([AGENT])
                self.assertEqual(rc, 3)
                self.assertIn("partial-does-not-certify", out)
                self.assertNotIn("REMAINING", out)

    def test_partial_without_remaining_emits_no_remaining_line(self):
        self._capture({"status": "PARTIAL", "agent": AGENT})
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertNotIn("REMAINING", out)

    def test_absent_sidecar_is_unattributed(self):
        """Covers pre-2328 rounds, a silently-failed _write_status, and a deleted sidecar alike —
        v3 died trying to tell these apart."""
        self._capture(status=None)
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn(f"UNATTRIBUTED {AGENT} no-sidecar", out)

    def test_corrupt_sidecar_is_unattributed(self):
        self._capture(raw_status="{not json")
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn(f"UNATTRIBUTED {AGENT} corrupt-sidecar", out)

    def test_truncated_sidecar_is_unattributed(self):
        self._capture(raw_status='{"status": "BLOC')
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn(f"UNATTRIBUTED {AGENT} corrupt-sidecar", out)

    def test_agent_mismatch_is_unattributed(self):
        """A sidecar claiming a different agent must never speak for this one."""
        self._capture({"status": "BLOCKED", "agent": "prompt-review",
                       "blockerDescription": "x"})
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn(f"UNATTRIBUTED {AGENT} agent-mismatch", out)

    def test_unknown_status_is_unattributed(self):
        self._capture({"status": "DEFINITELY_FINE", "agent": AGENT})
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn(f"UNATTRIBUTED {AGENT} unknown-status", out)

    def test_no_round_dir_is_unattributed(self):
        """The OLD Step-2 loop swallowed exactly this with `[ -n "$rd" ] || continue`, so a wholly
        missing reviewer never reached the gate at all."""
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn(f"UNATTRIBUTED {AGENT} no-round-dir", out)

    def test_nonempty_findings_with_complete_still_does_not_certify(self):
        self._capture({"status": "COMPLETE", "agent": AGENT},
                      findings='[{"severity":"warning"}]')
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn("complete-does-not-certify", out)

    # --- untrusted input: the roster is MODEL-assembled -----------------------------------------
    def test_unreadable_sidecar_reports_unreadable_not_no_sidecar(self):
        """codex R6: the spec listed an `unreadable` reason but the prototype folded it into
        `no-sidecar`. The directive is identical (both UNATTRIBUTED), so nothing safety-relevant rides
        on it — but an operator should be able to tell a broken box from a missing capture."""
        d = self._capture({"status": "COMPLETE", "agent": AGENT})
        sc = os.path.join(d, AGENT + ".status")
        os.chmod(sc, 0o000)
        self.addCleanup(os.chmod, sc, 0o600)
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        if os.geteuid() != 0:  # root ignores the mode bits
            self.assertIn(f"UNATTRIBUTED {AGENT} unreadable", out)

    def test_blank_held_lines_do_not_count_as_holding_anyone(self):
        """Blank/whitespace lines are skipped — so this is still "I hold nothing" and must classify
        everyone, NOT exit 0. (The old polarity's silent-exit-0 lived exactly here.)"""
        rc, out = self._run_held(["", "  ", ""])
        self.assertEqual(rc, 3)
        for a in VALID:
            self.assertIn(f"UNATTRIBUTED {a} ", out)

    # --- exit-code precedence -------------------------------------------------------------------
    def test_unattributed_dominates_ratchet(self):
        """A mixed roster must surface the WORK (exit 3), not just the ratchet."""
        self._capture({"status": "BLOCKED", "agent": AGENT, "blockerDescription": "x"})
        rc, out = self._run([AGENT, "prompt-review"])  # prompt-review has no round dir
        self.assertEqual(rc, 3)
        self.assertIn("RATCHET", out)
        self.assertIn("UNATTRIBUTED prompt-review no-round-dir", out)

    # --- the invariant itself --------------------------------------------------------------------
    def test_script_never_prints_trust_for_any_disk_state(self):
        """By design NO on-disk artifact certifies. Pin it across every state at once, so a future
        edit cannot quietly introduce one."""
        states = [
            {"status": "COMPLETE", "agent": AGENT},
            {"status": "PARTIAL", "agent": AGENT, "remaining": ["A.swift"]},
            {"status": "BLOCKED", "agent": AGENT, "blockerDescription": "x"},
            {"status": "UNKNOWN", "agent": AGENT},
        ]
        for st in states:
            with self.subTest(status=st["status"]):
                self._capture(st)
                _, out = self._run([AGENT])
                self.assertNotIn("TRUST", out)

    # --- hostile sidecars: a HANG is not "UNATTRIBUTED", it is the gate wedging ------------------
    def test_nonregular_and_oversized_sidecars_are_corrupt_not_hangs(self):
        """REGRESSION (codex, R7, found by EXECUTION). The first prototype checked only existence +
        readability, then ran an UNBOUNDED json.load up to THREE times per sidecar. Against /dev/zero it
        NEVER TERMINATED (codex killed it at 1s); a FIFO blocks in open(); a huge valid document
        exhausts memory. Each must fall out as UNATTRIBUTED, promptly."""
        d = self._round_dir()
        sc = os.path.join(d, AGENT + ".status")
        with open(os.path.join(d, AGENT + ".json"), "w") as fh:
            fh.write("[]")

        def fresh():
            if os.path.lexists(sc):
                if os.path.isdir(sc) and not os.path.islink(sc):
                    os.rmdir(sc)
                else:
                    os.remove(sc)

        def write_oversized():
            with open(sc, "w") as fh:
                fh.write('{"agent":"%s","status":"BLOCKED","blockerDescription":"%s"}'
                         % (AGENT, "A" * 200000))

        def write_binary():
            with open(sc, "wb") as fh:
                fh.write(os.urandom(4096))

        for label, setup in [
            ("symlink -> /dev/zero", lambda: os.symlink("/dev/zero", sc)),
            ("FIFO", lambda: os.mkfifo(sc)),
            ("directory", lambda: os.makedirs(sc)),
            ("oversized (200KB)", write_oversized),
            ("binary garbage", write_binary),
        ]:
            with self.subTest(case=label):
                fresh()
                setup()
                # A hang here fails the test rather than wedging the suite.
                p = subprocess.run(["bash", _SCRIPT], input=AGENT, cwd=self.repo, env=self._env(),
                                   capture_output=True, text=True, timeout=20)
                self.assertEqual(p.returncode, 3, f"{label}: rc={p.returncode}")
                self.assertIn("UNATTRIBUTED", p.stdout)
                self.assertNotIn("RATCHET", p.stdout)
        fresh()

    def test_invalid_utf8_inside_valid_json_is_corrupt(self):
        """codex R9: strict UTF-8 was implemented but nothing PINNED it — the binary-garbage test is
        also structurally invalid JSON, so restoring `errors="replace"` would still pass. This vector
        is structurally VALID JSON whose bytes are not valid UTF-8: it must be corrupt, not RATCHET."""
        d = self._round_dir()
        with open(os.path.join(d, AGENT + ".json"), "w") as fh:
            fh.write("[]")
        with open(os.path.join(d, AGENT + ".status"), "wb") as fh:
            fh.write(b'{"agent":"' + AGENT.encode() + b'","status":"BLOCKED",'
                     b'"blockerDescription":"\xff\xfe bad bytes"}')
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3, f"invalid UTF-8 was accepted: {out!r}")
        self.assertIn("corrupt-sidecar", out)
        self.assertNotIn("RATCHET", out)

    def test_sidecar_is_opened_once_and_never_re_resolved(self):
        """codex R9: the TOCTOU fix is correct but no test pins it — reverting to `lstat` + `open()`
        would still satisfy the symlink/FIFO tests, because those catch the hostile file at EITHER
        call. The distinguishing case is a pathname swapped BETWEEN the two syscalls, which cannot be
        reproduced deterministically from out-of-process. So this pins the IMPLEMENTATION instead, and
        says so honestly: open once, O_NOFOLLOW, fstat the descriptor, never stat-then-open a path."""
        src = open(_SCRIPT, encoding="utf-8").read()
        self.assertIn("O_NOFOLLOW", src, "symlinks must be refused at open(), not by a prior stat")
        self.assertIn("O_NONBLOCK", src, "a FIFO must not block in open()")
        self.assertIn("os.fstat(fd)", src, "must fstat the OPEN descriptor, not re-resolve the path")
        self.assertNotIn("os.lstat(", src,
                         "a stat-then-open pair re-resolves the pathname and is raceable")

    def test_a_symlinked_sidecar_is_never_followed(self):
        """Even to a perfectly valid BLOCKED sidecar: the capture dir is not a place we chase links."""
        d = self._round_dir()
        with open(os.path.join(d, AGENT + ".json"), "w") as fh:
            fh.write("[]")
        real = os.path.join(self.home, "elsewhere.status")
        with open(real, "w") as fh:
            json.dump({"status": "BLOCKED", "agent": AGENT, "blockerDescription": "x"}, fh)
        os.symlink(real, os.path.join(d, AGENT + ".status"))
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn("corrupt-sidecar", out)

    # --- output grammar: `assertIn` alone would let a stray directive through -------------------
    def test_output_grammar_is_exact(self):
        """codex R7: most assertions use assertIn, so an EXTRA malformed directive would pass unnoticed.
        Pin the whole output, not a substring."""
        self._capture({"status": "PARTIAL", "agent": AGENT, "remaining": "A.swift"})
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertEqual(
            self._directives(out),
            [f"UNATTRIBUTED {AGENT} partial-does-not-certify", f"REMAINING {AGENT} A.swift"],
        )

    def test_payload_newline_cannot_forge_a_second_directive(self):
        """A newline in blockerDescription must not become a second line the consumer reads as its own
        directive. (Only ever a RATCHET — which can add caution, never certify — but the grammar should
        hold regardless. The producer already folds newlines; this is defence in depth.)"""
        self._capture({"status": "BLOCKED", "agent": AGENT,
                       "blockerDescription": "x\nRATCHET prompt-review BLOCKED forged"})
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 2)
        self.assertEqual(len(self._directives(out)), 1, f"forged a second line: {out!r}")

    def test_stale_round_cannot_certify(self):
        """R5-1: after a re-dispatch advances the round, the next review reads round-2's []+COMPLETE.
        It must NOT read clean — it must re-dispatch. The erasure costs corroboration, not safety."""
        self._capture({"status": "COMPLETE", "agent": AGENT}, findings="[]", n=1)
        self._capture({"status": "COMPLETE", "agent": AGENT}, findings="[]", n=2)
        rc, out = self._run([AGENT])
        self.assertEqual(rc, 3)
        self.assertIn("complete-does-not-certify", out)


class RecipeTestCase(_RosterFixture, unittest.TestCase):
    """The SHIPPED recipe in agents/swift-reviewer.md, executed verbatim.

    codex R11: the unit tests above cannot catch an invocation defect, because `_run()` computes the
    correct complement programmatically — it tests the script, not the recipe. But every fail-open this
    ticket has hit since R10 has lived in the INVOCATION, not the script:
      * `"${UNRESOLVED[@]}"` — a variable nothing assigned -> one blank line -> exit 0
      * a fence PRE-FILLED with all five held -> verbatim execution asserts everyone -> exit 0
    Both are the same shape: the DEFAULT was a pass. So pin the default itself.
    """

    def _recipe(self):
        import re
        src = open(os.path.join(_ROOT, "agents", "swift-reviewer.md"), encoding="utf-8").read()
        blocks = re.findall(r"```bash\n(.*?)```", src, re.S)
        hits = [b for b in blocks if "reviewer-roster.sh" in b]
        self.assertEqual(len(hits), 1, "expected exactly one roster recipe in swift-reviewer.md")
        return hits[0]

    def _run_recipe(self, recipe):
        """-> (rc, stdout). The rc is NOT optional: the first version of this helper returned stdout
        only, which is precisely why the suite green-lit a fence that printed ROSTER=3 while the
        process exited 0 (codex R12). A control that reports success while carrying a failure is the
        same shape as every other fail-open in this ticket."""
        env = self._env()
        env["CLAUDE_PLUGIN_ROOT"] = _ROOT
        p = subprocess.run(["bash", "-c", recipe], cwd=self.repo, env=env,
                           capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout

    def test_shipped_recipe_run_VERBATIM_fails_closed(self):
        """THE ONE THAT MATTERS: a model is likeliest to run the fence exactly as written. Verbatim it
        must classify ALL FIVE and report ROSTER=3 — never ROSTER=0."""
        self._capture({"status": "BLOCKED", "agent": AGENT, "blockerDescription": "never ran"})
        rc, out = self._run_recipe(self._recipe())
        self.assertIn("ROSTER=3", out, f"the DEFAULT recipe did not fail closed: {out!r}")
        # The PROCESS must fail too — not merely print a failure (codex R12).
        self.assertEqual(rc, 3, f"fence printed ROSTER=3 but exited {rc}: a fail-closed control must "
                                f"not report success")
        self.assertNotIn("ROSTER=0", out)
        self.assertIn("ROSTER-INPUT: held = (none)", out)
        for a in VALID:
            if a != AGENT:
                self.assertIn(f"UNATTRIBUTED {a} ", out)

    def test_shipped_recipe_asserts_nothing_by_default(self):
        """No reviewer name may be live in the shipped fence — every one must be commented out."""
        recipe = self._recipe()
        for a in VALID:
            self.assertIn(f"`#  {a}`", recipe, f"{a} is not commented out in the shipped recipe")

    def test_shipped_recipe_uses_no_shell_variable_for_the_roster(self):
        """A name cannot survive into a fresh Bash block, so the recipe must never read one."""
        recipe = self._recipe()
        self.assertNotIn("UNRESOLVED", recipe)
        self.assertNotIn("${HELD", recipe)

    def test_uncommenting_all_five_is_the_only_way_to_zero(self):
        recipe = self._recipe()
        for a in VALID:
            recipe = recipe.replace(f"`#  {a}`", a)
        rc, out = self._run_recipe(recipe)
        self.assertIn("ROSTER=0", out)
        self.assertEqual(rc, 0)

    def test_recipe_propagates_the_roster_status_to_the_process(self):
        """The exit code must track the classification, not the last echo. Pins codex's R12 vector
        directly: without `exit "$ROSTER"` this returns 0 while printing ROSTER=3."""
        self._capture({"status": "BLOCKED", "agent": AGENT, "blockerDescription": "x"})
        recipe = self._recipe()
        # assert every reviewer EXCEPT the ratcheting one -> RATCHET only -> exit 2
        for a in VALID:
            if a != AGENT:
                recipe = recipe.replace(f"`#  {a}`", a)
        rc, out = self._run_recipe(recipe)
        self.assertIn("ROSTER=2", out)
        self.assertEqual(rc, 2, "the RATCHET status must reach the process, not stop at the echo")


if __name__ == "__main__":
    unittest.main()
