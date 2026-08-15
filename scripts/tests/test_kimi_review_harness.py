#!/usr/bin/env python3
"""`isolated-kimi-review.sh` — the mutation gates, driven end to end with a stub `kimi`.

Every scenario runs the WORKTREE's harness against a PRIVATE clone of this repository, with a stub
`kimi` on PATH whose behaviour is chosen by `KIMI_STUB_MODE`. The stub prints the session-id line and
a verdict; the effort cannot be asserted from a stub, so a run whose mutation gates all pass ends
`EXIT=… TREE=clean … EFFORT=UNKNOWN` and exit 4 — that pair IS "the gates passed". Every mutation the
harness documents (COREDEV-2607 shapes in the disposable checkout, a commit in the live tree, an
edited prompt) must exit 3 with its own message; a git-config write inside the disposable checkout
must stay there.

Linux-safe: git, bash, python3 only. The transcript is written under ~/.claude — the harness refuses
/tmp, and CI's TMPDIR is /tmp.
"""

from __future__ import annotations

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
        self.env = dict(os.environ)
        self.env["PATH"] = bindir + os.pathsep + self.env.get("PATH", "")
        self.env["KIMI_STUB_CLONE"] = self.clone

    def _run(self, mode):
        out = os.path.join(self.scratch, f"out-{mode}.txt")
        env = dict(self.env, KIMI_STUB_MODE=mode)
        p = subprocess.run(["bash", HARNESS, ".review-prompt-x.md", out, "HEAD", "60"],
                           cwd=self.clone, env=env, capture_output=True, text=True, check=False, input="")
        return p, out

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


if __name__ == "__main__":
    unittest.main()
