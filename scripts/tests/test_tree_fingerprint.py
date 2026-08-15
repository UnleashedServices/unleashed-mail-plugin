#!/usr/bin/env python3
"""`disposable_fingerprint` (scripts/review/tree-fingerprint.sh) serialises paths INJECTIVELY.

THE FINDING (codex, PR #67 pass 9 — reproduced). The record was line-oriented and carried the path
RAW: a reviewer that deleted `b` and renamed `a` to `a<newline><b's whole record>` produced output
byte-identical to the untouched tree's, and the before/after gate in all three harnesses accepted the
altered checkout. Paths (and link targets) are JSON-encoded now — pure ASCII, quoted, escaped — so
one entry is one line and a newline in a name cannot forge a second record.

Both builds are RUN: the shipped helper must tell the two trees apart; a copy with the encoding removed
(`q = rel`) must NOT — a control that cannot collide would prove the fixture, not the fix.

`tree_fingerprint` (the LIVE-checkout probe) does not TRUST THE INDEX (codex, PR #67 pass 10 —
reproduced). `git status` and `git diff HEAD` both consult the live index, so `update-index
--assume-unchanged` / `--skip-worktree` on a tracked file followed by an edit left both empty and the
fingerprint byte-identical; the probe now hashes every `git ls-files` path's working-tree bytes. The
`.verdicts` root is recorded by its OWN lstat, so a directory swapped for a symlink to an identical copy
moves the fingerprint even when the ignore rule hides the swap from `status`. And a listing that FAILS
fails the probe — never an empty tree. Each has a control: the pre-fix probe (`git diff HEAD`) and a
copy without the root lstat are RUN and must NOT tell the trees apart.

The tracked set is the UNION of the index and HEAD's tree (codex, PR #67 pass 11 — reproduced):
`ls-files` derives membership from the mutable index, so a committed-and-ignored path staged for
deletion (`git rm --cached`) vanished from the listing while `status` stayed `D  path` before and after
its working-tree file was rewritten. The control — the union's `ls-tree` half removed — must NOT move.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HELPER = os.path.join(REPO, "scripts", "review", "tree-fingerprint.sh")


def fingerprint(helper, root):
    """`disposable_fingerprint <root>` through `helper`, as the harnesses call it. Returns the text."""
    p = subprocess.run(["bash", "-c", '. "$1"; disposable_fingerprint "$2"', "_", helper, root],
                       capture_output=True, text=True, check=False)
    assert p.returncode == 0, f"disposable_fingerprint failed: {p.stderr!r}"
    return p.stdout


class DisposableFingerprintIsInjective(unittest.TestCase):
    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="tree-fp.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.tree = os.path.join(self.scratch, "tree")

    def _fresh_tree(self):
        shutil.rmtree(self.tree, ignore_errors=True)
        os.makedirs(self.tree)
        with open(os.path.join(self.tree, "a"), "w", encoding="utf-8") as fh:
            fh.write("X")
        with open(os.path.join(self.tree, "b"), "w", encoding="utf-8") as fh:
            fh.write("Y")

    def _forge(self, helper):
        """B = fingerprint of {a:X, b:Y}; then delete `b` and rename `a` to `a<newline><b's record as THIS
        build prints it>`; A = fingerprint afterwards. Returns (B, A, the forged name)."""
        self._fresh_tree()
        before = fingerprint(helper, self.tree)
        lines = before.splitlines()
        self.assertEqual(2, len(lines), f"two entries expected before the forgery: {before!r}")
        record_b = lines[-1]                                    # sorted: `a` then `b`
        self.assertTrue(record_b.endswith("b") or record_b.endswith('"b"'), record_b)
        forged = "a\n" + record_b
        os.unlink(os.path.join(self.tree, "b"))
        os.rename(os.path.join(self.tree, "a"), os.path.join(self.tree, forged))
        self.assertEqual([forged], os.listdir(self.tree))
        after = fingerprint(helper, self.tree)
        return before, after, forged

    def test_a_newline_in_a_name_cannot_forge_a_second_record(self):
        before, after, forged = self._forge(HELPER)
        self.assertNotEqual(before, after,
                            "the deleted-b / renamed-a tree fingerprinted IDENTICALLY to the untouched one")
        # The path token is JSON: `"a"` appears verbatim, and the forged name round-trips through json.loads.
        self.assertIn(' "a"\n', before, before)
        self.assertIn(' "b"\n', before, before)
        lines = after.splitlines()
        self.assertEqual(1, len(lines), f"one entry must be ONE line: {after!r}")
        token = lines[0].split(" ", 4)[4]                        # F <mode> <size> <sha256> <json-path>
        self.assertEqual(forged, json.loads(token), "the JSON path token does not decode to the real name")
        self.assertNotIn("\n", token)

    def test_the_control_without_json_encoding_collides(self):
        """The mutant — `q = rel` — is the pre-fix serialisation, and under it A == B (measured)."""
        with open(HELPER, encoding="utf-8") as fh:
            text = fh.read()
        old = "        q = json.dumps(rel)   "
        self.assertEqual(1, text.count(old), "mutation anchor is not unique — the control is not the control")
        mutant = os.path.join(self.scratch, "tree-fingerprint-mutant.sh")
        with open(mutant, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, "        q = rel   ", 1))
        before, after, _ = self._forge(mutant)
        self.assertEqual(before, after,
                         "the CONTROL did not collide — the raw-path serialisation told the trees apart, so "
                         "the fixture is not the forgery the finding describes")
        # And the shipped build, on the SAME forgery shape, does not collide.
        b2, a2, _ = self._forge(HELPER)
        self.assertNotEqual(b2, a2)


def tree_fingerprint(helper, root, ceiling):
    """`tree_fingerprint <root>` through `helper`, as the harnesses call it. Returns (rc, stdout, stderr).

    GIT_CEILING_DIRECTORIES stops repository discovery at the scratch directory: with the fixture's own
    `.git` deleted, git would otherwise walk UP and answer for whatever repository encloses ~/.claude
    (a dotfiles checkout of $HOME is common), and a probe that succeeded THERE would read as clean."""
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=ceiling)
    p = subprocess.run(["bash", "-c", '. "$1"; tree_fingerprint "$2"', "_", helper, root],
                       capture_output=True, text=True, check=False, env=env)
    return p.returncode, p.stdout, p.stderr


class LiveFingerprintDoesNotTrustTheIndex(unittest.TestCase):
    """A scratch repository with ONE committed tracked file, `f.txt`; each scenario takes B, mutates,
    takes A. The shipped helper must move; the named control must not."""

    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="tree-fp-live.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.repo = os.path.join(self.scratch, "repo")

    def _git(self, *args):
        subprocess.run(["git", "-C", self.repo, "-c", "commit.gpgsign=false", *args],
                       check=True, capture_output=True)

    def _fresh_repo(self, extra=None):
        """`git init` + `f.txt` (+ `extra`: {relpath: text}) committed; the tree starts clean."""
        shutil.rmtree(self.repo, ignore_errors=True)
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True, capture_output=True)
        self._git("config", "user.email", "fixture@test")
        self._git("config", "user.name", "fixture")
        files = {"f.txt": "one\n"}
        files.update(extra or {})
        for rel, text in files.items():
            full = os.path.join(self.repo, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(text)
        self._git("add", "-A")
        self._git("commit", "-qm", "fixture")
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, "the fixture must start clean")

    def _fp(self, helper):
        rc, out, err = tree_fingerprint(helper, self.repo, self.scratch)
        self.assertEqual(0, rc, f"tree_fingerprint failed: {err!r}")
        return out

    def _mutant(self, old, new, name):
        """A copy of the shipped helper with ONE line replaced (or deleted); the anchor must be unique."""
        with open(HELPER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(old), "mutation anchor is not unique — the control is not the control")
        path = os.path.join(self.scratch, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new, 1))
        return path

    # The pre-fix probe: `git diff HEAD` where the shipped build hashes every tracked file's bytes.
    DIFF_HEAD_OLD = '    _tracked_content_fingerprint "$1" || return 1\n'
    DIFF_HEAD_NEW = '    git -C "$1" diff HEAD 2>/dev/null || return 1\n'

    def _hidden_edit(self, helper, flag):
        """B on a clean repo; `git update-index <flag> f.txt`; append to f.txt; A. Returns (B, A)."""
        self._fresh_repo()
        before = self._fp(helper)
        self._git("update-index", flag, "f.txt")
        with open(os.path.join(self.repo, "f.txt"), "a", encoding="utf-8") as fh:
            fh.write("two\n")
        # The premise of the finding, asserted rather than assumed: the INDEX-based views are empty.
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        df = subprocess.run(["git", "-C", self.repo, "diff", "HEAD"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, f"{flag}: status still sees the edit — the fixture is not the finding")
        self.assertEqual("", df.stdout, f"{flag}: diff HEAD still sees the edit — the fixture is not the finding")
        after = self._fp(helper)
        return before, after

    def _assert_hidden_edit_moves_only_the_shipped_build(self, flag):
        before, after = self._hidden_edit(HELPER, flag)
        self.assertNotEqual(before, after,
                            f"{flag} + edit left the LIVE fingerprint byte-identical — the index was trusted")
        self.assertIn(' "f.txt"\n', before, before)
        # The control: the previous probe (`git diff HEAD`) on the SAME mutation compares EQUAL (measured).
        mutant = self._mutant(self.DIFF_HEAD_OLD, self.DIFF_HEAD_NEW, "tree-fingerprint-diff-head.sh")
        b2, a2 = self._hidden_edit(mutant, flag)
        self.assertEqual(b2, a2,
                         f"{flag}: the CONTROL (`git diff HEAD`) told the trees apart — the fixture is not "
                         "the hidden edit the finding describes")

    def test_assume_unchanged_plus_edit_moves_the_fingerprint(self):
        self._assert_hidden_edit_moves_only_the_shipped_build("--assume-unchanged")

    def test_skip_worktree_plus_edit_moves_the_fingerprint(self):
        self._assert_hidden_edit_moves_only_the_shipped_build("--skip-worktree")

    def test_a_failed_listing_fails_closed(self):
        """With `.git` deleted, `tree_fingerprint` returns non-zero — not an empty (clean-looking) record —
        and so does the tracked-content probe on its own, which runs the listing itself."""
        self._fresh_repo()
        self.assertEqual(0, tree_fingerprint(HELPER, self.repo, self.scratch)[0])
        shutil.rmtree(os.path.join(self.repo, ".git"))
        rc, out, _ = tree_fingerprint(HELPER, self.repo, self.scratch)
        self.assertNotEqual(0, rc, f"tree_fingerprint returned 0 on a checkout without .git: {out!r}")
        env = dict(os.environ, GIT_CEILING_DIRECTORIES=self.scratch)
        p = subprocess.run(["bash", "-c", '. "$1"; ! _tracked_content_fingerprint "$2"', "_", HELPER, self.repo],
                           capture_output=True, text=True, check=False, env=env)
        self.assertEqual(0, p.returncode, "`! _tracked_content_fingerprint` — the probe SUCCEEDED without a listing")
        self.assertEqual("", p.stdout, "a failed listing must not print a (empty) tracked-file record")

    # The `.verdicts` root's own lstat line, and nothing else, sees a directory swapped for a symlink.
    ROOT_LSTAT_LINE = '        _u_lstat_record "$1/docs/planning/.verdicts" || return 1\n'

    def _verdicts_swap(self, helper):
        """`docs/planning/.verdicts/x.json` and an identical `elsewhere/x.json`, both ignored (`.verdicts`
        WITHOUT a trailing slash, so the symlink that replaces the directory is ignored too and `status`
        cannot see the swap); B; replace the directory by a symlink to `elsewhere`; A."""
        self._fresh_repo({".gitignore": ".verdicts\nelsewhere/\n"})
        verdict = '{"verdict": "APPROVE"}\n'
        for rel in ("docs/planning/.verdicts/x.json", "elsewhere/x.json"):
            full = os.path.join(self.repo, rel)
            os.makedirs(os.path.dirname(full))
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(verdict)
        os.chmod(os.path.join(self.repo, "docs/planning/.verdicts/x.json"), 0o644)
        os.chmod(os.path.join(self.repo, "elsewhere/x.json"), 0o644)
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, "both copies must be ignored before the swap")
        before = self._fp(helper)
        verdicts = os.path.join(self.repo, "docs/planning/.verdicts")
        shutil.rmtree(verdicts)
        os.symlink(os.path.join("..", "..", "elsewhere"), verdicts)
        self.assertTrue(os.path.islink(verdicts) and os.path.isdir(verdicts))
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, "the swap must be invisible to `status` — the fixture is not the finding")
        after = self._fp(helper)
        return before, after

    # The HEAD-tree half of the tracked-path union — the `ls-tree` call and the lines that fold it in.
    LS_TREE_UNION = ('r2 = subprocess.run(["git", "-C", root, "ls-tree", "-r", "-z", "--name-only", "HEAD"], '
                     'capture_output=True)\n'
                     'if r2.returncode == 0:                      # an unborn HEAD has no tree; that is not a failure\n'
                     '    names.update(x for x in r2.stdout.split(b"\\0") if x)\n')

    def _staged_deletion_of_an_ignored_path(self, helper):
        """`f.txt` committed AND ignored (`.gitignore` lists it; it was added with `-f`); `git rm --cached
        f.txt`; B; rewrite f.txt; A. Returns (B, A). The premise is asserted: `ls-files` no longer lists
        the path and `status` reads `D  f.txt` — and only that — both before and after the rewrite."""
        self._fresh_repo({".gitignore": "f.txt\n"})          # `add -A` skipped the ignored f.txt …
        self._git("add", "-f", "f.txt")                       # … so it is forced in and committed
        self._git("commit", "-qm", "track the ignored file")
        listed = subprocess.run(["git", "-C", self.repo, "ls-files"], capture_output=True, text=True, check=True)
        self.assertIn("f.txt", listed.stdout.split(), "the fixture must start with f.txt TRACKED")
        self._git("rm", "--cached", "-q", "f.txt")
        listed = subprocess.run(["git", "-C", self.repo, "ls-files"], capture_output=True, text=True, check=True)
        self.assertNotIn("f.txt", listed.stdout.split(), "`rm --cached` must drop f.txt from the index listing")
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("D  f.txt\n", st.stdout, f"the fixture is not the finding: {st.stdout!r}")
        before = self._fp(helper)
        with open(os.path.join(self.repo, "f.txt"), "w", encoding="utf-8") as fh:
            fh.write("REWRITTEN\n")
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("D  f.txt\n", st.stdout,
                         f"status must be blind to the rewrite (ignored + staged deletion): {st.stdout!r}")
        after = self._fp(helper)
        return before, after

    def test_a_staged_deletion_of_an_ignored_path_is_still_hashed(self):
        before, after = self._staged_deletion_of_an_ignored_path(HELPER)
        self.assertNotEqual(before, after,
                            "the rewrite of a committed-and-ignored file staged for deletion left the LIVE "
                            "fingerprint byte-identical — membership came from the index alone")
        self.assertIn(' "f.txt"\n', before, before)           # HEAD's tree still names it, so it is hashed
        # The control: the union WITHOUT its `ls-tree` half — index membership only — compares EQUAL (measured).
        mutant = self._mutant(self.LS_TREE_UNION, "", "tree-fingerprint-no-ls-tree.sh")
        b2, a2 = self._staged_deletion_of_an_ignored_path(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (index-only membership) told the trees apart — the rewrite is visible "
                         "to something other than the HEAD-tree half, so this test does not prove that half")
        self.assertNotIn(' "f.txt"\n', b2, b2)

    def test_verdicts_root_type_is_recorded(self):
        before, after = self._verdicts_swap(HELPER)
        self.assertNotEqual(before, after,
                            "the directory→symlink swap of .verdicts left the LIVE fingerprint byte-identical")
        self.assertTrue(any(line.startswith("ROOT D ") for line in before.splitlines()), before)
        self.assertTrue(any(line.startswith("ROOT L ") for line in after.splitlines()),
                        f"no `ROOT L` line after the swap: {after!r}")
        # The control: without the root's own lstat, the walk THROUGH the symlink is identical (measured).
        mutant = self._mutant(self.ROOT_LSTAT_LINE, "", "tree-fingerprint-no-root-lstat.sh")
        b2, a2 = self._verdicts_swap(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (no root lstat) told the trees apart — the swap is visible to something "
                         "other than the root record, so this test does not prove that record")


if __name__ == "__main__":
    unittest.main()
