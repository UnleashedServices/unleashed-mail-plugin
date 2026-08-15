#!/usr/bin/env python3
"""`isolated-kimi-review.sh` — the mutation gates, driven end to end with a stub `kimi`.

Every scenario runs the WORKTREE's harness against a PRIVATE clone of this repository, with a stub
`kimi` on PATH whose behaviour is chosen by `KIMI_STUB_MODE`. The stub prints the session-id line and
a verdict; the effort cannot be asserted from a stub, so a run whose mutation gates all pass ends
`EXIT=… TREE=clean … EFFORT=UNKNOWN` and exit 4 — that pair IS "the gates passed". Every mutation the
harness documents (COREDEV-2607 shapes in the disposable checkout, a commit in the live tree, an
edited prompt) must exit 3 with its own message; a git-config write inside the disposable checkout
must stay there. PROMPT= on the summary line is the digest of the ARGUMENT the reviewer received (the
snapshot's bytes with trailing newlines stripped by command substitution), not of the prompt file; a
transcript operand that only PHYSICALLY resolves under /tmp — `..` traversal in an absolute path, or a
symlinked parent — is refused; and a live tracked file hidden with `update-index --assume-unchanged`
before it is edited still voids the round.

THE EFFORT EVIDENCE IS BOUND TO THE ONE SESSION THE RUN CREATED (codex, PR #67 pass 11): the set
difference of `$HOME/.kimi-code/sessions/*/session_*` before and after the run — never a session id read
out of the transcript, which is reviewer-controlled text. Exactly one new session with a `max` wire log
asserts `max` (exit 0); an older session's id QUOTED in the transcript, with no session created, is not
evidence (`EFFORT=UNKNOWN`, exit 4) — the previous grep-based selection would have returned that older
session's `max`, and a control carrying that selection is RUN and does; two new sessions fail closed.
Every run here has `HOME` re-pointed at a scratch directory, so the sessions the stub creates, and the
sessions the harness lists, are never the developer's real `~/.kimi-code`.

Linux-safe: git, bash, python3 only. The transcript is written under ~/.claude — the harness refuses
/tmp, and CI's TMPDIR is /tmp.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HARNESS = os.path.join(REPO, "scripts", "review", "isolated-kimi-review.sh")
SOURCE_PROMPT = os.path.join(REPO, ".review-prompt-2617r123.md")
SESSION = "session_00000000-0000-4000-8000-000000000001"
#: A session that exists BEFORE the run (the test creates it), and the one/two the stub creates DURING it.
OLD_SESSION = "session_11111111-1111-4111-8111-111111111111"
NEW_SESSION = "session_22222222-2222-4222-8222-222222222222"
NEW_SESSION_2 = "session_33333333-3333-4333-8333-333333333333"

KIMI_STUB = f"""#!/usr/bin/env bash
# cwd = the harness's DISPOSABLE checkout; $KIMI_STUB_CLONE = the live fixture repository.
case "${{KIMI_STUB_MODE:-clean}}" in
  clean) ;;
  gitkill)       rm -rf .git; echo x > IMPLEMENTED.sh ;;
  commit-hide)   echo x >> README.md
                 git -c user.email=r@r -c user.name=r -c commit.gpgsign=false commit -qam hide ;;
  nested-ignore) mkdir impl; printf '*\\n' > impl/.gitignore; echo x > impl/x.sh ;;
  live-commit)   git -C "$KIMI_STUB_CLONE" -c commit.gpgsign=false commit -q --allow-empty -m mid ;;
  prompt-edit)   printf '\\nEDITED\\n' >> "$KIMI_STUB_CLONE/.review-prompt-x.md" ;;
  hookspath)     git config core.hooksPath /evil/hooks
                 printf 'HOOKSPATH=%s\\n' "$(git config --get core.hooksPath)" ;;
  record-arg)    printf '%s' "$2" > "$KIMI_STUB_SCRATCH/received.bin" ;;   # $1=-p, $2=the prompt text
  assume-unchanged-live)
                 git -C "$KIMI_STUB_CLONE" update-index --assume-unchanged README.md
                 echo x >> "$KIMI_STUB_CLONE/README.md" ;;
  # The session-binding modes write under $HOME — the harness's HOME, re-pointed at the scratch by the test.
  new-max)       mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  quote-old)     printf 'As in {OLD_SESSION} earlier\\n' ;;      # creates NOTHING; quotes a pre-existing session
  two-new)       for s in {NEW_SESSION} {NEW_SESSION_2}; do
                   mkdir -p "$HOME/.kimi-code/sessions/wd_new/$s/agents/main"
                   printf '{{"thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/$s/agents/main/wire.jsonl"
                 done ;;
esac
printf '{SESSION}\\nVERDICT: APPROVE\\n'
"""


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "needs git and bash")
class KimiHarnessMutationGates(unittest.TestCase):
    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="kimi-harness.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.clone = os.path.join(self.scratch, "repo")
        subprocess.run(["git", "clone", "-q", REPO, self.clone], check=True, capture_output=True)
        git = ["git", "-C", self.clone]
        subprocess.run(git + ["config", "user.email", "fixture@test"], check=True)
        subprocess.run(git + ["config", "user.name", "fixture"], check=True)
        # A shallow SOURCE (CI's default depth-1 checkout) makes the harness's `disposable_checkout`
        # fetch fail — "shallow roots are not allowed to be updated" (measured, git 2.54) — even for a
        # commit made on top of it. An orphan root carries the same tree with a complete history.
        subprocess.run(git + ["checkout", "-q", "--orphan", "fixture"], check=True)
        prompt = os.path.join(self.clone, ".review-prompt-x.md")
        if os.path.isfile(SOURCE_PROMPT) and os.path.getsize(SOURCE_PROMPT) >= 1000:
            shutil.copy(SOURCE_PROMPT, prompt)
        else:
            with open(prompt, "w", encoding="utf-8") as fh:
                fh.write("Review the plan for correctness, security and completeness.\n" * 40)
        with open(os.path.join(self.clone, ".gitignore"), "a", encoding="utf-8") as fh:
            fh.write(".review-prompt-x.md\n")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], check=True)
        status = subprocess.run(git + ["status", "--porcelain"], capture_output=True, text=True, check=True)
        self.assertEqual("", status.stdout, "the fixture clone must start clean (the prompt is ignored)")
        bindir = os.path.join(self.scratch, "bin")
        os.mkdir(bindir)
        stub = os.path.join(bindir, "kimi")
        with open(stub, "w", encoding="utf-8") as fh:
            fh.write(KIMI_STUB)
        os.chmod(stub, 0o755)
        # HOME IS THE SCRATCH for every run: the harness lists `$HOME/.kimi-code/sessions/*/session_*`
        # before and after the reviewer, and the stub's session-binding modes create sessions there.
        # A real `~/.kimi-code` (dozens of sessions on a developer machine) must never be listed,
        # written, or — through a concurrent real session — mistaken for this run's evidence. Git
        # identity comes from the clone's own config, so no HOME-level gitconfig is needed.
        self.home = os.path.join(self.scratch, "home")
        os.mkdir(self.home)
        self.env = dict(os.environ)
        self.env["HOME"] = self.home
        self.env["PATH"] = bindir + os.pathsep + self.env.get("PATH", "")
        self.env["KIMI_STUB_CLONE"] = self.clone
        self.env["KIMI_STUB_SCRATCH"] = self.scratch
        self.prompt = prompt

    def _run(self, mode, out=None, harness=HARNESS):
        out = out or os.path.join(self.scratch, f"out-{mode}.txt")
        env = dict(self.env, KIMI_STUB_MODE=mode)
        p = subprocess.run(["bash", harness, ".review-prompt-x.md", out, "HEAD", "60"],
                           cwd=self.clone, env=env, capture_output=True, text=True, check=False, input="")
        return p, out

    def _wire(self, wd, session):
        """The wire-log path of `session` under `wd` in the SCRATCH home."""
        return os.path.join(self.home, ".kimi-code", "sessions", wd, session, "agents", "main", "wire.jsonl")

    def _seed_session(self, wd, session, effort="max"):
        path = self._wire(wd, session)
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"thinkingEffort":"%s"}\n' % effort)
        return path

    def _assert_void(self, mode, message):
        p, _ = self._run(mode)
        self.assertEqual(3, p.returncode, f"{mode}: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn(message, p.stderr, f"{mode}: {p.stderr!r}")
        self.assertNotIn("TREE=clean", p.stdout, f"{mode}: a void round printed the clean summary")
        return p

    def test_clean_run_passes_every_gate_and_stops_only_at_the_effort_assertion(self):
        p, out = self._run("clean")
        self.assertEqual(4, p.returncode, f"clean: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r"^EXIT=0 BYTES=\d+ TREE=clean BASIS=[0-9a-f]{12} PROMPT=[0-9a-f]{12} EFFORT=UNKNOWN$")
        self.assertIn("EFFORT NOT ASSERTED", p.stderr)
        with open(out, encoding="utf-8") as fh:
            transcript = fh.read()
        self.assertIn(SESSION, transcript)
        self.assertIn("VERDICT: APPROVE", transcript)

    def test_deleting_dot_git_and_creating_a_file_in_the_disposable_checkout_voids(self):
        p = self._assert_void("gitkill", "left edits inside the disposable checkout")
        self.assertIn('"IMPLEMENTED.sh"', p.stderr, "the diff must name the created file")

    def test_committing_an_edit_inside_the_disposable_checkout_voids(self):
        p = self._assert_void("commit-hide", "left edits inside the disposable checkout")
        self.assertIn('"README.md"', p.stderr, "the diff must name the edited file")

    def test_a_nested_self_ignoring_gitignore_voids(self):
        p = self._assert_void("nested-ignore", "left edits inside the disposable checkout")
        self.assertIn('"impl/x.sh"', p.stderr, "the diff must name the file the nested .gitignore hid")

    def test_a_commit_in_the_live_repository_voids(self):
        self._assert_void("live-commit", "real worktree was mutated")

    def test_editing_the_prompt_file_during_the_review_voids(self):
        self._assert_void("prompt-edit", "prompt file changed")

    def test_a_hooksPath_write_stays_inside_the_private_disposable_checkout(self):
        p, out = self._run("hookspath")
        self.assertEqual(4, p.returncode, f"hookspath: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn("TREE=clean", p.stdout)
        with open(out, encoding="utf-8") as fh:
            self.assertIn("HOOKSPATH=/evil/hooks", fh.read(), "the stub's write never happened")
        live = subprocess.run(["git", "-C", self.clone, "config", "--get", "core.hooksPath"],
                              capture_output=True, text=True, check=False)
        self.assertEqual("", live.stdout.strip(), "the reviewer's git-config write reached the LIVE repository")
        self.assertNotEqual(0, live.returncode)

    def test_prompt_digest_is_of_the_argument_the_reviewer_received_not_the_file(self):
        """The stub records `$2` (the `-p` argument) byte-for-byte; PROMPT= must be ITS sha256 — and,
        because the file ends in newlines that command substitution strips, NOT the file's digest.
        The prompt is git-ignored in the fixture, so appending to it does not dirty the tree."""
        with open(self.prompt, "ab") as fh:
            fh.write(b"\n\n")
        with open(self.prompt, "rb") as fh:
            file_bytes = fh.read()
        self.assertTrue(file_bytes.endswith(b"\n"))
        p, _ = self._run("record-arg")
        self.assertEqual(4, p.returncode, f"record-arg: rc {p.returncode}\n{p.stdout}{p.stderr}")
        m = re.search(r"\bPROMPT=([0-9a-f]{12})\b", p.stdout)
        self.assertIsNotNone(m, p.stdout)
        with open(os.path.join(self.scratch, "received.bin"), "rb") as fh:
            received = fh.read()
        self.assertEqual(file_bytes.rstrip(b"\n"), received,
                         "the reviewer did not receive the snapshot's bytes (minus trailing newlines)")
        self.assertEqual(hashlib.sha256(received).hexdigest()[:12], m.group(1),
                         "PROMPT= is not the digest of the argument the reviewer received")
        self.assertNotEqual(hashlib.sha256(file_bytes).hexdigest()[:12], m.group(1),
                            "PROMPT= equals the FILE's digest — but the reviewer never received the file's "
                            "trailing newlines, so that digest describes bytes it did not review")

    def _assert_tmp_refused(self, out, leaf):
        for physical in ("/tmp", "/private/tmp"):
            self.assertFalse(os.path.lexists(os.path.join(physical, leaf)), f"stale {leaf} under {physical}")
        p, _ = self._run("clean", out=out)
        self.assertEqual(1, p.returncode, f"rc {p.returncode} for {out}\n{p.stdout}{p.stderr}")
        self.assertIn("refusing to write the transcript under /tmp", p.stderr, p.stderr)
        self.assertNotIn("TREE=clean", p.stdout)
        for physical in ("/tmp", "/private/tmp"):
            self.assertFalse(os.path.lexists(os.path.join(physical, leaf)),
                             f"the refused transcript was written anyway: {physical}/{leaf}")

    def test_an_absolute_transcript_path_traversing_into_tmp_is_refused(self):
        """An ABSOLUTE operand whose `..` segments physically resolve under /tmp (`/…/scratch/../../tmp/x`)
        matched neither `/tmp/*` nor `/private/tmp/*` before the parent was resolved with `cd -P`."""
        leaf = f"kimi-x-{os.path.basename(self.scratch)}.txt"
        physical_scratch = os.path.realpath(self.scratch)
        out = os.path.join(physical_scratch, os.path.relpath("/tmp", physical_scratch), leaf)
        self.assertTrue(out.startswith("/") and "/../" in out and not out.startswith("/tmp/"), out)
        self.assertEqual(os.path.realpath("/tmp"), os.path.dirname(os.path.realpath(out)))
        self._assert_tmp_refused(out, leaf)

    def test_a_transcript_path_through_a_symlinked_parent_into_tmp_is_refused(self):
        """`<scratch>/link -> /tmp`; `<scratch>/link/x` is lexically under ~/.claude and physically under /tmp."""
        leaf = f"kimi-y-{os.path.basename(self.scratch)}.txt"
        link = os.path.join(self.scratch, "link")
        os.symlink("/tmp", link)
        out = os.path.join(link, leaf)
        self.assertFalse(out.startswith("/tmp/") or out.startswith("/private/tmp/"), out)
        self.assertEqual(os.path.realpath("/tmp"), os.path.dirname(os.path.realpath(out)))
        self._assert_tmp_refused(out, leaf)

    def test_a_live_tracked_file_hidden_by_assume_unchanged_then_edited_voids(self):
        """The reviewer flags a LIVE tracked file `--assume-unchanged` (status and `diff HEAD` go blind)
        and then edits it: the content-hashing live probe still sees the edit and voids the round."""
        self._assert_void("assume-unchanged-live", "real worktree was mutated")
        # The premise: the index-based views were indeed blind to the edit that voided the round.
        st = subprocess.run(["git", "-C", self.clone, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertNotIn("README.md", st.stdout, "status still saw the edit — the fixture is not the finding")
        with open(os.path.join(self.clone, "README.md"), "rb") as fh:
            self.assertTrue(fh.read().endswith(b"x\n"), "the stub's edit did not land in the live README.md")

    # ── the effort assertion is bound to the ONE session this run created ─────────────────────

    def test_exactly_one_new_session_with_a_max_wire_log_asserts_max(self):
        """The stub creates ONE session under the scratch HOME during the run, with `thinkingEffort:max`
        in its wire log: EFFORT=max, and the harness exits with the reviewer's own status (0)."""
        self.assertFalse(os.path.exists(os.path.join(self.home, ".kimi-code")), "no session before the run")
        p, _ = self._run("new-max")
        self.assertEqual(0, p.returncode, f"new-max: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r"^EXIT=0 BYTES=\d+ TREE=clean BASIS=[0-9a-f]{12} PROMPT=[0-9a-f]{12} EFFORT=max,$")
        self.assertNotIn("EFFORT NOT ASSERTED", p.stderr)
        self.assertTrue(os.path.isfile(self._wire("wd_new", NEW_SESSION)), "the stub's session did not land under the scratch HOME")

    def _quote_old(self, harness):
        """A `max` session exists BEFORE the run; the stub QUOTES its id and creates no session. Returns
        the completed process, after asserting the premise: the transcript carries the quoted id."""
        self._seed_session("wd_old", OLD_SESSION)
        p, out = self._run("quote-old", harness=harness)
        with open(out, encoding="utf-8") as fh:
            self.assertIn(OLD_SESSION, fh.read(), "the fixture is not the finding: the transcript does not quote the old id")
        self.assertFalse(os.path.exists(os.path.join(self.home, ".kimi-code", "sessions", "wd_new")),
                         "quote-old must create no session")
        return p

    def test_an_older_sessions_id_quoted_in_the_transcript_is_not_evidence(self):
        """No session was created during the run, so there is no evidence — whatever the transcript says.
        The pre-existing session's `max` log is NOT consulted: EFFORT=UNKNOWN and exit 4."""
        p = self._quote_old(HARNESS)
        self.assertEqual(4, p.returncode, f"quote-old: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r"^EXIT=0 BYTES=\d+ TREE=clean BASIS=[0-9a-f]{12} PROMPT=[0-9a-f]{12} EFFORT=UNKNOWN$")
        self.assertIn("EFFORT NOT ASSERTED", p.stderr)

    # The set-difference selection, as shipped — replaced by the control with the PREVIOUS selection: the
    # first `session_<uuid>` grep'd out of the transcript, then that session's wire log.
    SET_DIFFERENCE_HEAD = 'SESSIONS_AFTER="$(ls -d "$HOME"/.kimi-code/sessions/*/session_* 2>/dev/null | LC_ALL=C sort)"\n'
    SET_DIFFERENCE_TAIL = '    [ -r "$_w" ] && WIRE="$_w"\nfi\n'
    TRANSCRIPT_GREP = ('SESSION_ID="$(grep -m1 -oE \'session_[0-9a-f-]{36}\' "$OUT" 2>/dev/null || true)"\n'
                       'WIRE=""\n'
                       'if [ -n "$SESSION_ID" ]; then\n'
                       '    for _w in "$HOME"/.kimi-code/sessions/*/"$SESSION_ID"/agents/main/wire.jsonl; do\n'
                       '        [ -r "$_w" ] && { WIRE="$_w"; break; }\n'
                       '    done\n'
                       'fi\n')

    def _control_harness(self):
        """A copy of the harness with the transcript-grep selection in place of the set difference, laid
        out as `<scratch>/scripts/review/isolated-kimi-review.sh` beside `tree-fingerprint.sh` and under
        `<scratch>/scripts/pty-capture.py` — the harness resolves both from its OWN directory."""
        with open(HARNESS, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.SET_DIFFERENCE_HEAD), "the set-difference head is not unique")
        start = text.index(self.SET_DIFFERENCE_HEAD)
        self.assertIn(self.SET_DIFFERENCE_TAIL, text[start:], "the set-difference tail was not found after its head")
        end = text.index(self.SET_DIFFERENCE_TAIL, start) + len(self.SET_DIFFERENCE_TAIL)
        block = text[start:end]
        self.assertEqual(1, text.count(block), "the set-difference block is not unique")
        self.assertIn("NEW_SESSIONS", block)
        review_dir = os.path.join(self.scratch, "scripts", "review")
        os.makedirs(review_dir)
        shutil.copy(os.path.join(REPO, "scripts", "review", "tree-fingerprint.sh"), review_dir)
        shutil.copy(os.path.join(REPO, "scripts", "pty-capture.py"), os.path.join(self.scratch, "scripts"))
        control = os.path.join(review_dir, "isolated-kimi-review.sh")
        with open(control, "w", encoding="utf-8") as fh:
            fh.write(text.replace(block, self.TRANSCRIPT_GREP, 1))
        return control

    def test_the_control_with_the_transcript_grep_selection_certifies_the_quoted_session(self):
        """The CONTROL — the previous, transcript-grep selection — on the SAME quote-old fixture returns the
        older session's `max` and exits 0: it certifies this run on another run's evidence (measured).
        That is the defect; the shipped set difference above does not do it."""
        p = self._quote_old(self._control_harness())
        self.assertEqual(0, p.returncode,
                         f"the CONTROL did not certify the quoted session — the fixture is not the finding: "
                         f"rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r" EFFORT=max,$")

    def test_two_new_sessions_are_not_evidence(self):
        """Two sessions created during the run (a concurrent run's shape), both `max`: no single session is
        this run's, so EFFORT=UNKNOWN and exit 4 — never `max` on the strength of either."""
        p, _ = self._run("two-new")
        self.assertEqual(4, p.returncode, f"two-new: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r" EFFORT=UNKNOWN$")
        self.assertIn("EFFORT NOT ASSERTED", p.stderr)
        for s in (NEW_SESSION, NEW_SESSION_2):
            self.assertTrue(os.path.isfile(self._wire("wd_new", s)), f"the stub did not create {s}")


if __name__ == "__main__":
    unittest.main()
