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

The ANCESTOR DIRECTORIES of every tracked path are recorded by lstat — type and mode — before the leaves
(codex, PR #67 pass 13 — reproduced): `git status` says nothing about a directory's own metadata, so a
probe that hashed only the leaves certified a live tree whose `scripts/` had been `chmod 777`ed. The
control — the directory block removed, the leaf loop kept — must NOT move.

THE CHECKOUT ROOT IS ONE OF THOSE DIRECTORIES, EVERY RECORD CARRIES THE OBJECT'S IDENTITY, AND THE
EXCLUSION-METADATA FILES ARE RECORDED BY LSTAT (codex, PR #67 pass 14 — reproduced, three findings): the
ancestor walk stopped where `dirname` became empty, so `chmod 777 <checkout>` passed; mode+size+content
let a tracked file be swapped for a HARD LINK to an external byte-identical file (status clean, record
unchanged); and `.git/config` hashed THROUGH the name, so a symlink to an external byte-identical copy
digested identically while Git read its settings from outside the checkout. Records now carry
`dev:ino:nlink` (`D <mode> <ident> "rel"`, `F <mode> <size> <sha> <ident> "rel"`, …), the root is
recorded as `"."`, and `_u_hash_if_present` records type, mode, identity and (for a link) the target.
Each has a control — `dirs = set()`, the F record without `ident(st)`, the sha-only hasher — RUN and
compared EQUAL; and identity is stable across a clean round: two takes of an untouched tree are equal.

THE GIT METADATA IS RESOLVED THROUGH GIT, AND THE ACLs ARE RECORDED (codex sweep, PR #67 pass 14 — five
more findings, all reproduced, all in `GitMetadataAndAclsAreFingerprinted`). In a LINKED WORKTREE — which
is where this campaign's own reviews run — `.git` is a FILE and the real directories are elsewhere, so
`_u_hash_if_present "$1/.git/config"` recorded ABSENT and the whole metadata protection was inert:
`git -C <live> config core.hooksPath /tmp/evil` passed every gate. `_u_git_metadata_fingerprint` now
resolves `--absolute-git-dir` and `--git-common-dir` and records the `.git` entry, both directories,
`config`(+`.worktree`), `info/exclude`, `info/attributes`, `objects/info/alternates`, `HEAD` and every
entry of the hooks directories; `_u_acl_fingerprint` records the ACEs macOS keeps outside `st_mode`.
Controls: the two literal `$1/.git/…` calls restored, the `--dir <common>/hooks` argument dropped, the
`$_ugm_git/HEAD` argument dropped, and the ACL enumeration reduced to its marker — each RUN and compared
EQUAL. And STABILITY, which guards against a false void: two takes of an untouched linked worktree are
byte-identical.

THE STAGED BYTES, THE PATHS CONFIG POINTS AT, AND THE REPORT'S OWN GIT (codex, PR #67 pass 15 — four
more findings, all reproduced). `ls-files -z` records index MEMBERSHIP only, so a staged blob swapped
with `update-index --cacheinfo` left `status` reading the same `MM f.txt` and the fingerprint
byte-identical while `rev-parse :f.txt` moved — `ls-files --stage -z` is emitted as `INDEX` records now.
`git config --get` returns the UNEXPANDED text, so `core.hooksPath = ~/hooks` was fingerprinted as
`<root>/~/hooks` while git ran `$HOME/hooks/pre-commit`; every config-referenced path is read with
`--path`. `core.excludesFile` and `core.attributesFile`, and every `file:` origin `git config --list
--show-origin` names (which is how an `include.path`/`includeIf` file, and the global and system config,
get covered), are hashed — recording the config TEXT that named them did not record them. And
`tree_fingerprint_report`, which both isolation harnesses call the moment a mutation is detected, ran a
plain `git status`: a reviewer-planted `core.fsmonitor` executable would have been RUN by it, as us,
inside the tree being measured. Controls: the staged records dropped from the seed, `--path` dropped,
the excludes read dropped, the origins block dropped — each RUN and compared EQUAL; and for the report,
the plain `git status` restored, which EXECUTES the planted hook (the witness file appears).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HELPER = os.path.join(REPO, "scripts", "review", "tree-fingerprint.sh")
#: The identity field every tracked-content record carries (PR #67 pass 14): `st_dev:st_ino:st_nlink`.
IDENT = r"\d+:\d+:\d+"
#: `chmod +a` / `ls -lde` are macOS spellings; CI is Linux, where `_u_acl_fingerprint` says so and stops.
DARWIN = os.uname().sysname == "Darwin"


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


def tree_fingerprint(helper, root, ceiling, extra_env=None):
    """`tree_fingerprint <root>` through `helper`, as the harnesses call it. Returns (rc, stdout, stderr).

    GIT_CEILING_DIRECTORIES stops repository discovery at the scratch directory: with the fixture's own
    `.git` deleted, git would otherwise walk UP and answer for whatever repository encloses ~/.claude
    (a dotfiles checkout of $HOME is common), and a probe that succeeded THERE would read as clean.

    `extra_env` re-points HOME for the tilde-expansion case (PR #67 pass 15): `core.hooksPath = ~/hooks`
    is a form git supports, and the probe must resolve it the way git does — which means the fixture's
    HOME, never the developer's."""
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=ceiling, **(extra_env or {}))
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
    # (Every git call in the probe is built from the shared `GIT` prefix, which carries
    # `--no-optional-locks -c core.fsmonitor=false` since PR #67 pass 14: a probe must never write the
    # live index, and a reviewer-planted fsmonitor hook must not be EXECUTED by our own AFTER take.
    # `FsmonitorIsNeverExecutedByTheProbeOrTheReport` asserts that prefix behaviourally; the pin here
    # quotes the call as it is shipped, so a rewrite that dropped the prefix would strand this anchor.)
    LS_TREE_UNION = ('r2 = subprocess.run(GIT + ["ls-tree", "-r", "-z", "--name-only", "HEAD"], capture_output=True)\n'
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

    # ── the STAGED BYTES, not merely index membership (codex, PR #67 pass 15) ─────────────────────

    def _staged_blob_swap(self, helper):
        """`f.txt` committed, staged with one content and edited again in the working tree, so the checkout
        starts `MM f.txt`; B; `git update-index --cacheinfo` swaps the STAGED blob for other bytes; A.
        Returns (B, A, the staged oid before, the staged oid after). The premise is asserted on both
        sides: `git status --porcelain` is EXACTLY `MM f.txt` before and after, and `git rev-parse :f.txt`
        moved — the working tree, HEAD and the set of listed paths are all untouched."""
        self._fresh_repo()
        path = os.path.join(self.repo, "f.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("staged\n")
        self._git("add", "f.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("worktree\n")
        other = subprocess.run(["git", "-C", self.repo, "hash-object", "-w", "--stdin"],
                               input="planted\n", capture_output=True, text=True, check=True).stdout.strip()
        oid = lambda: subprocess.run(["git", "-C", self.repo, "rev-parse", ":f.txt"],
                                     capture_output=True, text=True, check=True).stdout.strip()
        status = lambda: subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                                        capture_output=True, text=True, check=True).stdout
        before_oid = oid()
        self.assertNotEqual(before_oid, other, "the planted blob already IS the staged one")
        self.assertEqual("MM f.txt\n", status(), f"the fixture must start `MM f.txt`: {status()!r}")
        before = self._fp(helper)
        self._git("update-index", "--cacheinfo", f"100644,{other},f.txt")
        self.assertEqual(other, oid(), "the cacheinfo swap did not move the staged object id")
        self.assertEqual("MM f.txt\n", status(),
                         f"status moved — the fixture is not the finding: {status()!r}")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual("worktree\n", fh.read(), "the swap touched the working tree — not the finding")
        after = self._fp(helper)
        return before, after, before_oid, other

    def test_the_staged_object_ids_are_recorded_not_only_index_membership(self):
        """codex, PR #67 pass 15 — `ls-files -z` records index MEMBERSHIP only. In a checkout that starts
        `MM f.txt` a reviewer can swap what is STAGED with `git update-index --cacheinfo` and leave the
        working tree alone: `git status --porcelain` prints the same two letters, every leaf digest is
        unchanged, and the fingerprint was BYTE-IDENTICAL while `git rev-parse :f.txt` returned different
        bytes — so the maintainer's next `git commit` writes a blob nobody reviewed. `ls-files --stage -z`
        is emitted as `INDEX <mode> <oid> <stage>\\t<path>` records at the head of the tracked block.
        Mutant: the staged records dropped from the seed (`out = []`) — the two takes compare EQUAL."""
        before, after, before_oid, other = self._staged_blob_swap(HELPER)
        self.assertNotEqual(before, after,
                            "the `update-index --cacheinfo` swap of the staged blob left the LIVE "
                            "fingerprint byte-identical — only index MEMBERSHIP was recorded")
        self.assertIn(f"\nINDEX 100644 {before_oid} 0\tf.txt\n", before,
                      f"no `INDEX <mode> <oid> <stage>\\t<path>` record before: {before!r}")
        self.assertIn(f"\nINDEX 100644 {other} 0\tf.txt\n", after,
                      f"the swapped object id is not recorded after: {after!r}")
        # ONLY the staged half moved: substituting the one oid in B reproduces A exactly.
        self.assertEqual(before.replace(before_oid, other), after,
                         "something other than the INDEX record differs — the fixture is not the finding")
        # The control: the seed without the staged records — the swap is invisible (measured).
        mutant = self._mutant(self.STAGED_SEED, "out = []\n", "tree-fingerprint-no-staged-oids.sh")
        b2, a2, _, _ = self._staged_blob_swap(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (no staged object ids) told the trees apart — the swap is visible to "
                         "something other than the INDEX records, so this test does not prove them")
        self.assertNotIn("\nINDEX ", b2, b2)

    # The directory block of the tracked-content probe — from the ancestor set through the `D` record;
    # the leaf loop that follows it (and the record-list seed it shares) stays in the control.
    # (`ident(st)` is defined ABOVE the block and stays in the control — the leaf loop uses it too.)
    DIR_BLOCK_HEAD = 'dirs = set(["."])\n'
    DIR_BLOCK_TAIL = '        out.append("D %s %s %s" % (mode, ident(st), json.dumps(rel)))\n'
    #: The record list's SEED — the staged `INDEX` records (PR #67 pass 15) the directory block is
    #: appended to. The directory-block control re-adds it verbatim, so the control differs from the
    #: shipped build in the directory block ALONE and not also in the staged-object-id half.
    STAGED_SEED = 'out = ["INDEX %s" % s for s in staged]\n'

    def _dir_block(self):
        """The CURRENT text of the directory block, sliced between two unique anchors of the shipped helper."""
        with open(HELPER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.DIR_BLOCK_HEAD), "the directory block's head is not unique")
        start = text.index(self.DIR_BLOCK_HEAD)
        self.assertIn(self.DIR_BLOCK_TAIL, text[start:], "the directory block's tail is not after its head")
        end = text.index(self.DIR_BLOCK_TAIL, start) + len(self.DIR_BLOCK_TAIL)
        block = text[start:end]
        self.assertEqual(1, text.count(block), "the sliced directory block is not unique")
        self.assertIn(self.STAGED_SEED, block,
                      "the block should carry the shared record-list seed — the control re-adds it")
        self.assertIn('out.append("MISSING-DIR %s"', block)
        self.assertIn('out.append("DL %s %s %s -> %s"', block)
        # The leaf loop is OUTSIDE the slice, so the control still hashes every tracked file.
        self.assertIn("for raw in sorted(names):\n", text[end:], "the leaf loop must follow the block")
        return block

    def _directory_mode_change(self, helper):
        """`scripts/f.sh` committed; B; `chmod 777 scripts`; A. Returns (B, A, pre-chmod mode as `%04o`).
        The premise is asserted: `status` is blind to the directory's mode before and after."""
        self._fresh_repo({"scripts/f.sh": "#!/bin/sh\n"})
        scripts = os.path.join(self.repo, "scripts")
        self.assertTrue(os.path.isdir(scripts) and not os.path.islink(scripts))
        pre = "%04o" % (os.lstat(scripts).st_mode & 0o7777)
        self.assertNotEqual("0777", pre, "the fixture's directory already carries the mode the change applies")
        before = self._fp(helper)
        os.chmod(scripts, 0o777)
        self.assertEqual("0777", "%04o" % (os.lstat(scripts).st_mode & 0o7777))
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, f"status sees the directory chmod — the fixture is not the finding: {st.stdout!r}")
        after = self._fp(helper)
        return before, after, pre

    def test_a_tracked_directorys_mode_change_moves_the_fingerprint(self):
        before, after, pre = self._directory_mode_change(HELPER)
        self.assertNotEqual(before, after,
                            "`chmod 777 scripts` left the LIVE fingerprint byte-identical — only the leaves were hashed")
        # The record shape (PR #67 pass 14): `D <mode> <dev:ino:nlink> "rel"` — an identity field between
        # the mode and the name, so the pins are regexes over the WHOLE line.
        self.assertRegex(before, rf'\nD {pre} {IDENT} "scripts"\n',
                         f"no `D {pre} <ident> \"scripts\"` record (the directory's actual pre-chmod mode) before: {before!r}")
        self.assertRegex(after, rf'\nD 0777 {IDENT} "scripts"\n', f"no `D 0777 <ident> \"scripts\"` record after: {after!r}")
        self.assertNotRegex(before, rf'\nD 0777 {IDENT} "scripts"\n')
        # The directory record precedes the leaves it encloses.
        self.assertLess(re.search(rf'D 0777 {IDENT} "scripts"', after).start(), after.index(' "scripts/f.sh"\n'), after)
        self.assertIn(' "scripts/f.sh"\n', before, before)                 # the leaf is still hashed
        # The control: the directory block removed, the leaf loop kept — compares EQUAL (measured).
        mutant = self._mutant(self._dir_block(), self.STAGED_SEED, "tree-fingerprint-no-dir-block.sh")
        b2, a2, _ = self._directory_mode_change(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (leaves only) told the trees apart — the chmod is visible to something "
                         "other than the directory record, so this test does not prove that record")
        self.assertNotIn(' "scripts"\n', b2, b2)                            # no directory record at all …
        self.assertIn(' "scripts/f.sh"\n', b2, b2)                          # … but the leaf loop survived

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

    # ── the checkout root, object identity, and the exclusion files by lstat (codex, PR #67 pass 14) ──

    def _root_mode_change(self, helper):
        """`scripts/f.sh` committed; B; `chmod 777 <checkout root>`; A. Returns (B, A, pre-chmod mode).
        The premise is asserted: `status` is blind to the root's mode after the change."""
        self._fresh_repo({"scripts/f.sh": "#!/bin/sh\n"})
        pre = "%04o" % (os.lstat(self.repo).st_mode & 0o7777)
        self.assertNotEqual("0777", pre, "the fixture's root already carries the mode the change applies")
        before = self._fp(helper)
        os.chmod(self.repo, 0o777)
        self.assertEqual("0777", "%04o" % (os.lstat(self.repo).st_mode & 0o7777))
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, f"status sees the root chmod — the fixture is not the finding: {st.stdout!r}")
        after = self._fp(helper)
        return before, after, pre

    def test_the_checkout_roots_mode_change_moves_the_fingerprint(self):
        """codex, PR #67 pass 14, finding 1 — the ancestor walk stopped where `dirname` became empty, so the
        checkout ROOT was never recorded and `chmod 777 <checkout>` passed every gate. The root is recorded
        as `D <mode> <ident> "."`, before every other directory. Mutant: `dirs = set(["."])` → `dirs = set()`
        (the root dropped from the ancestor set) — the two takes compare EQUAL (measured)."""
        before, after, pre = self._root_mode_change(HELPER)
        self.assertNotEqual(before, after,
                            "`chmod 777 <checkout>` left the LIVE fingerprint byte-identical — the root was not recorded")
        self.assertRegex(before, rf'\nD {pre} {IDENT} "\."\n', f"no `D {pre} <ident> \".\"` record before: {before!r}")
        self.assertRegex(after, rf'\nD 0777 {IDENT} "\."\n', f"no `D 0777 <ident> \".\"` record after: {after!r}")
        self.assertNotRegex(before, rf'\nD 0777 {IDENT} "\."\n')
        # The root record precedes every other directory and every leaf.
        self.assertLess(re.search(rf'\nD {pre} {IDENT} "\."\n', before).start(),
                        re.search(rf'\nD \d{{4}} {IDENT} "scripts"\n', before).start(), before)
        # The control: the root dropped from the ancestor set — `scripts` is still recorded, the root is
        # not, and the takes compare EQUAL (measured).
        mutant = self._mutant('dirs = set(["."])\n', "dirs = set()\n", "tree-fingerprint-no-root-dir.sh")
        b2, a2, _ = self._root_mode_change(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (root not in the ancestor set) told the trees apart — the chmod is visible "
                         "to something other than the root's own record, so this test does not prove that record")
        self.assertNotRegex(b2, rf'\nD \d{{4}} {IDENT} "\."\n', b2)          # no root record …
        self.assertRegex(b2, rf'\nD \d{{4}} {IDENT} "scripts"\n', b2)         # … but the other directories survived

    # The F record WITH the identity field (shipped) and the pre-fix record without it (the control).
    F_RECORD_IDENT = '        out.append("F %s %d %s %s %s" % (mode, st.st_size, h.hexdigest(), ident(st), json.dumps(rel)))\n'
    F_RECORD_OLD = '        out.append("F %s %d %s %s" % (mode, st.st_size, h.hexdigest(), json.dumps(rel)))\n'

    def _external_sibling(self):
        """A scratch directory BESIDE this test's own, under ~/.claude — the same filesystem as the fixture
        repository, which a hard link requires (a link across filesystems is EXDEV, not the finding)."""
        base = os.path.expanduser("~/.claude")
        ext = tempfile.mkdtemp(prefix="tree-fp-ext.", dir=base)
        self.addCleanup(shutil.rmtree, ext, ignore_errors=True)
        return ext

    def _hard_link_swap(self, helper):
        """`f.txt` committed; an EXTERNAL `f.txt` with identical bytes and mode in a sibling scratch; B;
        replace the tracked file by a hard link to the external one; A. Returns (B, A). The premise is
        asserted: same device, `status` blind to the swap, and the link count went to 2."""
        self._fresh_repo()
        tracked = os.path.join(self.repo, "f.txt")
        external = os.path.join(self._external_sibling(), "f.txt")
        with open(tracked, "rb") as fh:
            payload = fh.read()
        with open(external, "wb") as fh:
            fh.write(payload)
        os.chmod(external, os.lstat(tracked).st_mode & 0o7777)
        self.assertEqual(os.lstat(tracked).st_dev, os.lstat(external).st_dev,
                         "the external copy is on another filesystem — a hard link cannot be made (fixture, not the finding)")
        before = self._fp(helper)
        os.unlink(tracked)
        os.link(external, tracked)
        self.assertEqual(2, os.lstat(tracked).st_nlink, "the swap did not produce a hard link")
        self.assertEqual(os.lstat(external).st_ino, os.lstat(tracked).st_ino)
        with open(tracked, "rb") as fh:
            self.assertEqual(payload, fh.read(), "the swap changed the bytes — the fixture is not the finding")
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, f"status sees the hard-link swap — the fixture is not the finding: {st.stdout!r}")
        after = self._fp(helper)
        return before, after

    def test_a_tracked_file_replaced_by_a_hard_link_to_an_identical_external_file_moves_the_fingerprint(self):
        """codex, PR #67 pass 14, finding 2 — mode+size+content let a tracked file be REPLACED by a hard link
        to an external file with identical bytes and mode: status stayed clean and the record was unchanged,
        while a later write through either name silently changed the other. Every record now carries
        `dev:ino:nlink`. Mutant: the F record without `ident(st)` (the pre-fix shape) — the two takes compare
        EQUAL (measured)."""
        before, after = self._hard_link_swap(HELPER)
        self.assertNotEqual(before, after,
                            "the hard-link swap of a tracked file left the LIVE fingerprint byte-identical — "
                            "the record carried no object identity")
        self.assertRegex(before, r'\nF 0644 \d+ [0-9a-f]{64} \d+:\d+:1 "f\.txt"\n', before)
        self.assertRegex(after, r'\nF 0644 \d+ [0-9a-f]{64} \d+:\d+:2 "f\.txt"\n',
                         f"no F record with link count 2 after the swap: {after!r}")
        # Same mode, size and digest in both takes — ONLY the identity moved.
        rec = lambda text: re.search(r'\n(F 0644 \d+ [0-9a-f]{64}) \d+:\d+:\d+ "f\.txt"\n', text).group(1)
        self.assertEqual(rec(before), rec(after), "mode/size/digest changed — the fixture is not the finding")
        # The control: the pre-fix F record — no identity — compares EQUAL (measured).
        mutant = self._mutant(self.F_RECORD_IDENT, self.F_RECORD_OLD, "tree-fingerprint-no-ident.sh")
        b2, a2 = self._hard_link_swap(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (F record without identity) told the trees apart — the swap is visible to "
                         "something other than the identity field, so this test does not prove that field")
        self.assertRegex(b2, r'\nF 0644 \d+ [0-9a-f]{64} "f\.txt"\n', b2)     # the old four-field shape

    # `_u_hash_if_present`'s per-path record — `rec()`, from its `def` line through the `O` record it
    # ends with. The control replaces the whole lstat dispatch with a sha256 taken THROUGH the name,
    # which is what the helper did before pass 14: `open()` follows a symlink, so the link and its
    # target digested identically. `ABSENT` is kept for a path that does not exist, so the control
    # differs from the shipped build in exactly one respect — it never lstats.
    REC_HEAD = 'def rec(p):\n'
    REC_TAIL = '    return "O %s %s" % (mode, ident)\n'
    REC_OLD = ('def rec(p):\n'
               '    try:\n'
               '        return hashlib.sha256(open(p, "rb").read()).hexdigest()\n'
               '    except OSError:\n'
               '        return "ABSENT"\n')

    def _rec_block(self):
        """The CURRENT text of `_u_hash_if_present`'s `rec()`, sliced between two unique anchors."""
        with open(HELPER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.REC_HEAD), "the lstat record's head is not unique")
        start = text.index(self.REC_HEAD)
        self.assertIn(self.REC_TAIL, text[start:], "the lstat record's tail is not after its head")
        end = text.index(self.REC_TAIL, start) + len(self.REC_TAIL)
        block = text[start:end]
        self.assertEqual(1, text.count(block), "the sliced record block is not unique")
        self.assertIn("os.lstat(p)", block)
        self.assertIn("UNREADABLE-TARGET", block)
        return block

    def _config_symlink_swap(self, helper):
        """`.git/config` copied byte-for-byte to an EXTERNAL sibling scratch; B; replace `.git/config` by a
        symlink to that copy; A. Returns (B, A). The premise is asserted: git still reads its config
        through the link and `status` is clean and blind to the swap."""
        self._fresh_repo()
        cfg = os.path.join(self.repo, ".git", "config")
        external = os.path.join(self._external_sibling(), "config")
        shutil.copy2(cfg, external)
        with open(cfg, "rb") as a, open(external, "rb") as b:
            self.assertEqual(a.read(), b.read())
        before = self._fp(helper)
        os.unlink(cfg)
        os.symlink(external, cfg)
        self.assertTrue(os.path.islink(cfg) and os.path.isfile(cfg))
        st = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                            capture_output=True, text=True, check=False)
        self.assertEqual((0, ""), (st.returncode, st.stdout),
                         f"git does not read its config through the link, or status sees the swap — "
                         f"the fixture is not the finding: {st.returncode} {st.stdout!r} {st.stderr!r}")
        after = self._fp(helper)
        return before, after

    def test_git_config_replaced_by_a_symlink_to_an_identical_copy_moves_the_fingerprint(self):
        """codex, PR #67 pass 14, finding 3 — `_u_hash_if_present` hashed `.git/config` THROUGH the name, so a
        symlink to an external byte-identical copy digested identically while Git read its settings
        (`core.hooksPath` among them) from outside the checkout. The record is now taken by lstat — type,
        mode, identity, and a link's target. Mutant: `rec()`'s lstat dispatch replaced by the previous
        sha256-through-the-name — the two takes compare EQUAL (measured)."""
        before, after = self._config_symlink_swap(HELPER)
        self.assertNotEqual(before, after,
                            "`.git/config` swapped for a symlink to an identical copy left the LIVE fingerprint "
                            "byte-identical — the file was hashed through its name")
        cfg = os.path.join(self.repo, ".git", "config")
        self.assertRegex(before, rf'\n{re.escape(cfg)} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', before)
        self.assertRegex(after, rf'\n{re.escape(cfg)} L \d{{4}} {IDENT} -> "[^"\n]+" [0-9a-f]{{64}}\n',
                         f"no `L … -> <target> <digest>` record for the linked config after: {after!r}")
        # The digest of what the link resolves to is the SAME bytes — only the type/identity/target moved.
        digest = lambda text: re.search(rf'\n{re.escape(cfg)} \S.* ([0-9a-f]{{64}})\n', text).group(1)
        self.assertEqual(digest(before), digest(after), "the bytes differ — the fixture is not the finding")
        # The control: the sha-only record (a digest through the name) compares EQUAL (measured).
        mutant = self._mutant(self._rec_block(), self.REC_OLD, "tree-fingerprint-sha-only-hasher.sh")
        b2, a2 = self._config_symlink_swap(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (sha256 through the name) told the trees apart — the swap is visible to "
                         "something other than the lstat record, so this test does not prove that record")
        self.assertRegex(b2, rf'\n{re.escape(cfg)} [0-9a-f]{{64}}\n', b2)      # the old `<path> <sha>` shape

    def test_two_takes_of_an_untouched_tree_are_equal(self):
        """Identity is stable across a clean round: nothing the harness does re-creates a tracked object, so
        two takes of an untouched tree — files, directories, the root and `.git/config` all carrying
        `dev:ino:nlink` — are byte-identical. (The identity fields must not turn every honest round void.)"""
        self._fresh_repo({"scripts/f.sh": "#!/bin/sh\n", ".gitignore": "elsewhere/\n"})
        first = self._fp(HELPER)
        second = self._fp(HELPER)
        self.assertEqual(first, second, "two takes of an untouched tree differ — the fingerprint is not stable")
        self.assertRegex(first, rf'\nD \d{{4}} {IDENT} "\."\n', first)
        self.assertRegex(first, rf'\nF \d{{4}} \d+ [0-9a-f]{{64}} {IDENT} "f\.txt"\n', first)
        cfg = os.path.join(self.repo, ".git", "config")
        self.assertRegex(first, rf'\n{re.escape(cfg)} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', first)


class GitMetadataAndAclsAreFingerprinted(unittest.TestCase):
    """The fixture is a LINKED WORKTREE — `git init main`, one commit, `git worktree add wt` — and every
    scenario fingerprints THE WORKTREE, which is how this campaign's own reviews actually run.

    codex sweep, PR #67 pass 14, five findings; each has a control that is RUN and compared EQUAL:
      * in a linked worktree `.git` is a FILE and the real directories are elsewhere, so the two literal
        `_u_hash_if_present "$1/.git/…"` calls recorded ABSENT and the metadata protection was entirely
        inert — `git -C <live> config core.hooksPath <evil>` passed every gate;
      * a `pre-commit` planted in the COMMON hooks directory needs no config change and fires on the
        maintainer's next commit;
      * `HEAD` retargeted to another branch at the SAME sha moves no other record;
      * macOS keeps ACLs outside `st_mode`, so `chmod +a` on a tracked file, a tracked directory or the
        checkout root left every record byte-identical (Darwin only — `find -acl`/`ls -lde`/`chmod +a`);
      * and the new records must be STABLE, or they void every honest round instead of the tampered ones.
    """

    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="tree-fp-wt.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.main = os.path.join(self.scratch, "main")
        self.wt = os.path.join(self.scratch, "wt")
        subprocess.run(["git", "init", "-q", self.main], check=True, capture_output=True)
        self._git("config", "user.email", "fixture@test")
        self._git("config", "user.name", "fixture")
        os.makedirs(os.path.join(self.main, "scripts"))
        for rel, text in (("f.txt", "one\n"), ("scripts/f.sh", "#!/bin/sh\n")):
            with open(os.path.join(self.main, rel), "w", encoding="utf-8") as fh:
                fh.write(text)
        self._git("add", "-A")
        self._git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        self._git("branch", "other")                         # a second branch for the HEAD retarget
        self._git("worktree", "add", "--quiet", "-b", "feat", self.wt)
        # THE FIXTURE IS THE FINDING: `.git` in the worktree is a FILE, not a directory.
        self.assertTrue(os.path.isfile(os.path.join(self.wt, ".git")),
                        "the fixture's `.git` is not a regular file — this is not a linked worktree")
        self.common = os.path.join(self.main, ".git")        # the common dir, where config and hooks live
        self.gitdir = os.path.join(self.common, "worktrees", "wt")   # this worktree's own gitdir
        self.assertTrue(os.path.isdir(self.gitdir), self.gitdir)
        self._assert_clean("the worktree fixture must start clean")

    def _git(self, *args, repo=None):
        subprocess.run(["git", "-C", repo or self.main, *args], check=True, capture_output=True)

    def _status(self):
        return subprocess.run(["git", "-C", self.wt, "status", "--porcelain"],
                              capture_output=True, text=True, check=True).stdout

    def _head(self):
        return subprocess.run(["git", "-C", self.wt, "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()

    def _assert_clean(self, why):
        self.assertEqual("", self._status(), f"{why}: {self._status()!r}")

    def _fp(self, helper, env=None):
        rc, out, err = tree_fingerprint(helper, self.wt, self.scratch, extra_env=env)
        self.assertEqual(0, rc, f"tree_fingerprint failed on the linked worktree: {err!r}")
        return out

    def _ext(self, name):
        """A directory beside the worktree but OUTSIDE it — where the config-referenced files live."""
        path = os.path.join(self.scratch, name)
        os.makedirs(path, exist_ok=True)
        return path

    def _config(self, *args, env=None):
        """`git -C <worktree> config <args>`, returning the trimmed stdout (empty when unset)."""
        p = subprocess.run(["git", "-C", self.wt, "config", *args], capture_output=True, text=True,
                           check=False, env=dict(os.environ, **(env or {})))
        return p.stdout.strip()

    def _mutant(self, old, new, name):
        """A copy of the shipped helper with ONE anchor replaced; the anchor must be unique."""
        with open(HELPER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(old), "mutation anchor is not unique — the control is not the control")
        path = os.path.join(self.scratch, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new, 1))
        return path

    def _round(self, helper, mutate):
        """B on the untouched worktree, `mutate()`, A. Returns (B, A). The premise is asserted on both
        sides: `git status` stays clean, so nothing here is visible to the index-based views."""
        self._assert_clean("the round must start clean")
        before = self._fp(helper)
        mutate()
        self._assert_clean("the mutation is visible to `status` — the fixture is not the finding")
        return before, self._fp(helper)

    # ── the metadata is resolved THROUGH GIT, not by assuming `$1/.git` is a directory ────────────

    #: The shipped probe; the control puts the two literal `$1/.git/…` paths back — the shape that was
    #: recorded ABSENT in a linked worktree, which is where the campaign's reviews run.
    METADATA_CALL = '    _u_git_metadata_fingerprint "$1" || return 1\n'
    METADATA_OLD = ('    _u_hash_if_present "$1/.git/info/exclude" || return 1\n'
                    '    _u_hash_if_present "$1/.git/config" || return 1\n')

    def test_core_hookspath_set_in_a_linked_worktree_moves_the_fingerprint(self):
        """codex sweep, PR #67 pass 14, finding T1 — in a linked worktree `.git` is a FILE, so
        `_u_hash_if_present "$1/.git/config"` recorded ABSENT and `git -C <live> config core.hooksPath
        <evil>` passed every gate. Mutant: the two literal `$1/.git/…` calls restored in place of
        `_u_git_metadata_fingerprint` — the two takes compare EQUAL (measured)."""
        evil = os.path.join(self.scratch, "evil-hooks")      # never created: only lstat-ed
        mutate = lambda: self._git("config", "core.hooksPath", evil, repo=self.wt)
        before, after = self._round(HELPER, mutate)
        self.assertNotEqual(before, after,
                            "`git config core.hooksPath` in a linked worktree left the LIVE fingerprint "
                            "byte-identical — the metadata was looked for at `<worktree>/.git/config`")
        # The `.git` entry is recorded as the FILE it is, and the config that governs the worktree is the
        # COMMON one — the proof that the resolution went through git rather than through `$1/.git/`.
        dot_git = os.path.join(self.wt, ".git")
        self.assertRegex(before, rf'\n{re.escape(dot_git)} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', before)
        cfg = os.path.join(self.common, "config")
        self.assertRegex(before, rf'\n{re.escape(cfg)} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', before)
        self.assertIn(f"\n{evil} ABSENT\n", after,
                      f"the configured hooks directory is not recorded after the change: {after!r}")
        self.assertNotIn(f"\n{evil} ABSENT\n", before)
        # The control: the pre-fix literal paths — ABSENT in a linked worktree — compare EQUAL (measured).
        mutant = self._mutant(self.METADATA_CALL, self.METADATA_OLD, "tree-fingerprint-literal-gitdir.sh")
        self._git("config", "--unset", "core.hooksPath", repo=self.wt)
        b2, a2 = self._round(mutant, mutate)
        self.assertEqual(b2, a2,
                         "the CONTROL (the literal `$1/.git/…` paths) told the trees apart — the hooksPath "
                         "write is visible to something other than the git-resolved metadata, so this test "
                         "does not prove that resolution")
        # …and the inertness itself, asserted rather than inferred: BOTH literal paths read ABSENT.
        for leaf in ("info/exclude", "config"):
            self.assertIn(f"\n{os.path.join(self.wt, '.git', leaf)} ABSENT\n", b2,
                          f"the CONTROL did not record `<worktree>/.git/{leaf}` as ABSENT: {b2!r}")

    # ── the hooks that will actually run, and the branch HEAD points at ───────────────────────────

    #: The `--dir <common>/hooks` argument (T2) and the per-worktree `HEAD` argument (T3). The first
    #: anchor contains the second, so both are unique; each control drops exactly one argument.
    HOOKS_DIR_ARG = ('           "$_ugm_common/objects/info/alternates" "$_ugm_git/HEAD" \\\n'
                     '           --dir "$_ugm_common/hooks"\n')
    HOOKS_DIR_GONE = '           "$_ugm_common/objects/info/alternates" "$_ugm_git/HEAD"\n'
    HEAD_ARG = '           "$_ugm_common/objects/info/alternates" "$_ugm_git/HEAD" \\\n'
    HEAD_GONE = '           "$_ugm_common/objects/info/alternates" \\\n'

    def test_a_pre_commit_hook_planted_in_the_common_dir_moves_the_fingerprint(self):
        """codex sweep, PR #67 pass 14, finding T2 — a `pre-commit` planted in the COMMON hooks directory
        needs no config change at all and fires on the maintainer's next commit, so the hooks directories
        are recorded entry by entry. Mutant: the `--dir "$_ugm_common/hooks"` argument dropped — the two
        takes compare EQUAL (measured)."""
        hook = os.path.join(self.common, "hooks", "pre-commit")
        os.makedirs(os.path.dirname(hook), exist_ok=True)    # an empty init template ships no hooks dir

        def plant():
            with open(hook, "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\nexfiltrate\n")
            os.chmod(hook, 0o755)

        before, after = self._round(HELPER, plant)
        self.assertNotEqual(before, after,
                            "a `pre-commit` planted in the common hooks directory left the LIVE fingerprint "
                            "byte-identical — the hooks directory was not recorded")
        self.assertRegex(after, rf'\n{re.escape(hook)} F 0755 {IDENT} \d+ [0-9a-f]{{64}}\n', after)
        self.assertNotIn(f"\n{hook} ", before)
        # The control: without the hooks directory the planted hook is invisible (measured).
        mutant = self._mutant(self.HOOKS_DIR_ARG, self.HOOKS_DIR_GONE, "tree-fingerprint-no-hooks-dir.sh")
        os.unlink(hook)
        b2, a2 = self._round(mutant, plant)
        self.assertEqual(b2, a2,
                         "the CONTROL (no hooks directory) told the trees apart — the planted hook is "
                         "visible to something other than the `--dir` expansion, so this test does not "
                         "prove that expansion")
        self.assertNotIn(f"\n{hook} ", a2, a2)

    def test_a_head_retarget_at_the_same_sha_moves_the_fingerprint(self):
        """codex sweep, PR #67 pass 14, finding T3 — `git symbolic-ref HEAD refs/heads/other` leaves the
        resolved commit and every other record untouched, so the worktree's own `HEAD` file is recorded.
        Mutant: the `"$_ugm_git/HEAD"` argument dropped — the two takes compare EQUAL (measured)."""
        head_file = os.path.join(self.gitdir, "HEAD")
        sha = self._head()
        retarget = lambda: self._git("symbolic-ref", "HEAD", "refs/heads/other", repo=self.wt)
        before, after = self._round(HELPER, retarget)
        # The premise: the resolved commit did NOT move, so the first line of the record is unchanged.
        self.assertEqual(sha, self._head(), "the retarget moved HEAD's commit — the fixture is not the finding")
        self.assertEqual(before.splitlines()[0], after.splitlines()[0],
                         "the `rev-parse HEAD` line moved — the fixture is not the finding")
        self.assertNotEqual(before, after,
                            "`symbolic-ref HEAD refs/heads/other` left the LIVE fingerprint byte-identical "
                            "— the worktree's own HEAD was not recorded")
        self.assertRegex(before, rf'\n{re.escape(head_file)} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', before)
        # The control: without the HEAD argument the retarget is invisible (measured).
        mutant = self._mutant(self.HEAD_ARG, self.HEAD_GONE, "tree-fingerprint-no-head.sh")
        self._git("symbolic-ref", "HEAD", "refs/heads/feat", repo=self.wt)
        b2, a2 = self._round(mutant, retarget)
        self.assertEqual(b2, a2,
                         "the CONTROL (no HEAD record) told the trees apart — the retarget is visible to "
                         "something other than that record, so this test does not prove it")
        self.assertNotIn(f"\n{head_file} ", b2, b2)

    # ── the paths CONFIG POINTS AT, read the way GIT reads them (codex, PR #67 pass 15) ───────────

    #: `core.hooksPath` read with git's own path semantics; the control drops `--path`, which is the
    #: shape that fingerprinted the supported tilde form as the literal `<root>/~/hooks`.
    HOOKS_PATH_READ = 'config --path --get core.hooksPath'
    HOOKS_PATH_OLD = 'config --get core.hooksPath'

    def _home(self):
        """A HOME for the fixture — inside the scratch, outside the worktree. `~` must never expand to
        the developer's own home in a test that then edits `~/hooks/pre-commit`."""
        return self._ext("home")

    def _tilde_hooks_edit(self, helper):
        """`core.hooksPath = ~/hooks` (the literal tilde, as git stores it) with `~/hooks/pre-commit`
        already present; B; the hook's CONTENT is rewritten in place — nothing created anywhere; A.
        Returns (B, A, the hook path). The premises are asserted: `--get` returns the raw tilde,
        `--path --get` returns the expanded path, and `git status` is blind throughout."""
        home = self._home()
        hooks = os.path.join(home, "hooks")
        os.makedirs(hooks, exist_ok=True)
        hook = os.path.join(hooks, "pre-commit")
        with open(hook, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexit 0\n")
        os.chmod(hook, 0o755)
        self._git("config", "core.hooksPath", "~/hooks", repo=self.wt)
        self.assertEqual("~/hooks", self._config("--get", "core.hooksPath"),
                         "git did not store the tilde form verbatim — the fixture is not the finding")
        self.assertEqual(hooks, self._config("--path", "--get", "core.hooksPath", env={"HOME": home}),
                         "git does not expand `~` for this key — the fixture is not the finding")
        self._assert_clean("the tilde-hooks round must start clean")
        before = self._fp(helper, env={"HOME": home})
        with open(hook, "w", encoding="utf-8") as fh:                     # in place: same inode, new bytes
            fh.write("#!/bin/sh\nexfiltrate\n")
        self._assert_clean("the hook edit is visible to `status` — the fixture is not the finding")
        after = self._fp(helper, env={"HOME": home})
        return before, after, hook

    def test_core_hookspath_in_its_tilde_form_is_resolved_the_way_git_resolves_it(self):
        """codex, PR #67 pass 15 — `git config --get` returns the UNEXPANDED text, so the supported
        `core.hooksPath = ~/hooks` was fingerprinted as `<root>/~/hooks`, a directory that does not
        exist, while git executed `$HOME/hooks/pre-commit`: editing that hook left the two takes
        byte-identical. The value is read with `--path`, which is how git itself reads it (a relative
        value is still resolved against the checkout root). Mutant: `--path` dropped — the two takes
        compare EQUAL, and the recorded directory is the literal `<worktree>/~/hooks` ABSENT."""
        before, after, hook = self._tilde_hooks_edit(HELPER)
        self.assertNotEqual(before, after,
                            "an edit to the hook `core.hooksPath = ~/hooks` actually names left the LIVE "
                            "fingerprint byte-identical — the tilde was never expanded")
        self.assertRegex(before, rf'\n{re.escape(hook)} F 0755 {IDENT} \d+ [0-9a-f]{{64}}\n', before)
        self.assertRegex(after, rf'\n{re.escape(hook)} F 0755 {IDENT} \d+ [0-9a-f]{{64}}\n', after)
        digest = lambda t: re.search(rf'\n{re.escape(hook)} F 0755 {IDENT} \d+ ([0-9a-f]{{64}})\n', t).group(1)
        self.assertNotEqual(digest(before), digest(after), "the hook's digest did not move")
        # The control: without `--path` the recorded path is the literal tilde under the checkout root,
        # which does not exist — both takes record it ABSENT and compare EQUAL (measured).
        mutant = self._mutant(self.HOOKS_PATH_READ, self.HOOKS_PATH_OLD,
                              "tree-fingerprint-hookspath-unexpanded.sh")
        b2, a2, _ = self._tilde_hooks_edit(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (no `--path`) told the trees apart — the hook edit is visible to "
                         "something other than the expanded hooks path, so this test does not prove it")
        self.assertIn(f"\n{os.path.join(self.wt, '~', 'hooks')} ABSENT\n", b2,
                      f"the CONTROL did not record the unexpanded `<root>/~/hooks`: {b2!r}")
        self.assertNotIn(f"\n{hook} ", b2, b2)

    #: `core.excludesFile` read as a path and hashed; the control drops the argument entirely, which is
    #: the shape that recorded the config TEXT naming the file but never the file.
    EXCLUDES_READ = ('    _ugm_excl="$(_u_git -C "$_ugm_root" config --path --get core.excludesFile '
                     '2>/dev/null)" || _ugm_excl=""\n')
    EXCLUDES_GONE = '    _ugm_excl=""\n'

    def _external_excludes_edit(self, helper):
        """An EXTERNAL `core.excludesFile` that hides an untracked file from `status`; the hidden file is
        created BEFORE the round, so the window contains ONLY a content change to the excludes file; B;
        one rule appended to it; A. Returns (B, A, the excludes path). The premises are asserted: the
        file IS hidden, and it is that external file doing the hiding.

        (Nothing is CREATED between the takes on purpose: on APFS a directory's `st_nlink` tracks its
        entry count, so a new file moves the enclosing directory's own record and the round would pass
        for a reason that has nothing to do with the excludes file.)"""
        excl = os.path.join(self._ext("ext-excludes"), "excludes")
        with open(excl, "w", encoding="utf-8") as fh:
            fh.write("hidden.txt\n")
        self._git("config", "core.excludesFile", excl, repo=self.wt)
        hidden = os.path.join(self.wt, "hidden.txt")
        if not os.path.exists(hidden):
            with open(hidden, "w", encoding="utf-8") as fh:
                fh.write("planted\n")
        self.assertEqual("", self._status(),
                         "the external excludes file does not hide the untracked file — not the finding")
        bare = subprocess.run(["git", "-C", self.wt, "-c", "core.excludesFile=/dev/null",
                               "status", "--porcelain"], capture_output=True, text=True, check=True)
        self.assertEqual("?? hidden.txt\n", bare.stdout,
                         f"without that excludes file the path is NOT untracked-visible — the fixture "
                         f"does not show the file doing the hiding: {bare.stdout!r}")
        before = self._fp(helper)
        with open(excl, "a", encoding="utf-8") as fh:                     # one more rule; nothing created
            fh.write("second-rule\n")
        self._assert_clean("the excludes edit is visible to `status` — the fixture is not the finding")
        after = self._fp(helper)
        return before, after, excl

    def test_the_external_excludes_file_is_hashed_not_only_the_config_that_names_it(self):
        """codex, PR #67 pass 15 — `core.excludesFile` hides an untracked file from `status`, so a reviewer
        who adds a rule to an external excludes file changes what the whole status half can see while the
        repository's own config text stands still: recording the config that NAMES the file did not
        record the file. Mutant: the `--path --get core.excludesFile` read dropped — the two takes
        compare EQUAL."""
        before, after, excl = self._external_excludes_edit(HELPER)
        self.assertNotEqual(before, after,
                            "a rule appended to the external `core.excludesFile` left the LIVE fingerprint "
                            "byte-identical — only the config text that names it was recorded")
        self.assertRegex(before, rf'\n{re.escape(excl)} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', before)
        # The control: the excludes read dropped — the file is not recorded at all and the takes are EQUAL.
        mutant = self._mutant(self.EXCLUDES_READ, self.EXCLUDES_GONE, "tree-fingerprint-no-excludes.sh")
        b2, a2, _ = self._external_excludes_edit(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (no excludes-file record) told the trees apart — the appended rule is "
                         "visible to something other than that record, so this test does not prove it")
        self.assertNotIn(f"\n{excl} ", b2, b2)

    def _origins_block(self):
        """The CURRENT text of the `--show-origin` block, sliced between two unique anchors."""
        with open(HELPER, encoding="utf-8") as fh:
            text = fh.read()
        head = '    _ugm_origins="$(_u_git -C "$_ugm_root" config --list --show-origin'
        self.assertEqual(1, text.count(head), "the origins block's head is not unique")
        start = text.index(head)
        end = text.index("\n    fi\n", start) + len("\n    fi\n")
        block = text[start:end]
        self.assertEqual(1, text.count(block), "the sliced origins block is not unique")
        self.assertIn("sed -n 's/^file://p'", block)
        # The block feeds the origins through a `while read` so a RELATIVE origin can be resolved
        # against the checkout root: `--show-origin` prints the repository's own files relative
        # (`.git/config`, and `.git/../inc.cfg` for a relative include), and fed verbatim they
        # resolved against the recorder's cwd and recorded `.git/config ABSENT`.
        self.assertIn('while IFS= read -r _ugm_o', block)
        self.assertIn('case "$_ugm_o" in /*) : ;; *) _ugm_o="$_ugm_root/$_ugm_o" ;; esac', block)
        self.assertIn('set -- "$@" "$_ugm_o"', block)
        return block

    def _included_config_edit(self, helper):
        """An EXTERNAL config pulled in by `include.path`, which sets `core.hooksPath` for this checkout;
        B; that file's CONTENT changes (a `user.email` line — `core.hooksPath` is left byte-identical, so
        no other record can move); A. Returns (B, A, the included path). The premises are asserted: the
        included file is what supplies `core.hooksPath`, the repository's own config never names it, and
        the value does not move across the window."""
        inc = os.path.join(self._ext("ext-include"), "included.cfg")
        inc_hooks = self._ext("ext-include-hooks")
        with open(os.path.join(inc_hooks, "pre-commit"), "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexit 0\n")

        def write_inc(email):
            with open(inc, "w", encoding="utf-8") as fh:
                fh.write(f"[core]\n\thooksPath = {inc_hooks}\n[user]\n\temail = {email}\n")

        write_inc("a@a")
        self._git("config", "include.path", inc, repo=self.wt)
        self.assertEqual(inc_hooks, self._config("--get", "core.hooksPath"),
                         "the included file does not supply `core.hooksPath` — the fixture is not the finding")
        with open(os.path.join(self.common, "config"), encoding="utf-8") as fh:
            self.assertNotIn("hooksPath", fh.read(),
                             "the repository's own config names the hooks path — the fixture does not show "
                             "the INCLUDED file governing the checkout")
        self._assert_clean("the include round must start clean")
        before = self._fp(helper)
        write_inc("b@b")                                  # content moves; `core.hooksPath` does not
        self.assertEqual(inc_hooks, self._config("--get", "core.hooksPath"),
                         "the rewrite moved `core.hooksPath` — another record could account for the change")
        self._assert_clean("the include edit is visible to `status` — the fixture is not the finding")
        after = self._fp(helper)
        return before, after, inc

    def test_every_file_that_contributes_config_is_hashed_including_an_included_one(self):
        """codex, PR #67 pass 15 — `include.path` / `includeIf` pull settings from a file the repository's
        own `config` only NAMES, and the global and system files can set `core.hooksPath` for this
        checkout too; none of them was recorded. `git config --list --show-origin --name-only` names
        every file that contributed, and each is hashed. Mutant: the origins block dropped — the two
        takes compare EQUAL.

        RESIDUAL, MEASURED (not closed by the shipped block, reported rather than asserted here):
        `--show-origin` renders the repository's own config as the RELATIVE `.git/config`, and a
        RELATIVELY-included file as `.git/../<name>`; those strings are passed to the recorder verbatim
        and resolve against the RECORDER's cwd, so they read `ABSENT` (or, worse, name another
        repository's file) whenever the caller's cwd is not the checkout root. An ABSOLUTE include —
        the case this fixture drives — is recorded correctly."""
        before, after, inc = self._included_config_edit(HELPER)
        self.assertNotEqual(before, after,
                            "an edit to the config file `include.path` pulls in left the LIVE fingerprint "
                            "byte-identical — only the file that NAMES it was recorded")
        self.assertRegex(before, rf'\n{re.escape(inc)} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', before)
        digest = lambda t: re.search(rf'\n{re.escape(inc)} F \d{{4}} {IDENT} \d+ ([0-9a-f]{{64}})\n', t).group(1)
        self.assertNotEqual(digest(before), digest(after), "the included file's digest did not move")
        # The control: the origins block dropped — the included file is not recorded and the takes are EQUAL.
        mutant = self._mutant(self._origins_block(), '    _ugm_origins=""\n',
                              "tree-fingerprint-no-config-origins.sh")
        b2, a2, _ = self._included_config_edit(mutant)
        self.assertEqual(b2, a2,
                         "the CONTROL (no config origins) told the trees apart — the included file's edit is "
                         "visible to something other than the origins block, so this test does not prove it")
        self.assertNotIn(f"\n{inc} ", b2, b2)

    # ── the ACLs macOS keeps outside st_mode ──────────────────────────────────────────────────────

    #: The enumeration `_u_acl_fingerprint` performs; the control keeps only its `ACL-PROBE done` marker,
    #: so the probe still RUNS and still prints a line — it just never names an ACE (the pre-fix state,
    #: where mode bits were the whole of the write-access answer).
    ACL_ENUM = ('    { /usr/bin/find "$1" -acl -print 2>/dev/null || :; } | LC_ALL=C sort | while IFS= read -r _uacl_p; do\n'
                "        printf 'ACL %s\\n' \"$_uacl_p\"\n"
                "        /bin/ls -lde -- \"$_uacl_p\" 2>/dev/null | sed -n 's/^[[:space:]]*\\([0-9][0-9]*: .*\\)$/ACE \\1/p'\n"
                '    done\n')

    def _acl_case(self, helper, target):
        add = lambda: subprocess.run(["chmod", "+a", "everyone allow write,delete", target],
                                     check=True, capture_output=True)
        try:
            return self._round(helper, add)
        finally:
            subprocess.run(["chmod", "-N", target], check=False, capture_output=True)

    @unittest.skipUnless(DARWIN, "`chmod +a`, `ls -lde` and `find -acl` are macOS spellings")
    def test_an_acl_on_a_tracked_path_the_root_or_a_directory_moves_the_fingerprint(self):
        """codex sweep, PR #67 pass 14, finding T4 — macOS keeps ACLs OUTSIDE `st_mode`, so `chmod +a
        'everyone allow write,delete'` on a tracked file, on a tracked DIRECTORY, or on the checkout ROOT
        left every record byte-identical, re-opening for ACEs the write-access class pass 13 closed for
        mode bits. Mutant: `_u_acl_fingerprint` reduced to its `ACL-PROBE done` marker — all three cases
        compare EQUAL (measured)."""
        targets = {"tracked file": os.path.join(self.wt, "f.txt"),
                   "tracked directory": os.path.join(self.wt, "scripts"),
                   "checkout root": self.wt}
        for what, target in targets.items():
            before, after = self._acl_case(HELPER, target)
            self.assertNotEqual(before, after,
                                f"`chmod +a` on the {what} left the LIVE fingerprint byte-identical — "
                                f"the ACL is outside st_mode and nothing recorded it")
            self.assertIn(f"\nACL {target}\n", after, f"{what}: no `ACL {target}` line after: {after!r}")
            self.assertNotIn(f"\nACL {target}\n", before, f"{what}: {before!r}")
            self.assertRegex(after, r"\nACE\s+0: .*everyone", f"{what}: the ACE itself is not rendered: {after!r}")
            self.assertIn("\nACL-PROBE done\n", before, before)
            # The control: the enumeration removed, the marker kept — EQUAL (measured). Built HERE, after
            # the discriminating assertion, so a HELPER that already carries the defect fails on the
            # comparison above rather than on the anchor that no longer matches.
            mutant = self._mutant(self.ACL_ENUM, "    :\n", "tree-fingerprint-no-acl.sh")
            b2, a2 = self._acl_case(mutant, target)
            self.assertEqual(b2, a2,
                             f"the CONTROL (no ACL enumeration) told the trees apart on the {what} — the "
                             f"ACE is visible to something other than the ACL probe, so this test does not "
                             f"prove that probe")
            self.assertNotIn("\nACL ", b2, b2)
            self.assertIn("\nACL-PROBE done\n", b2, b2)      # the probe still ran, and still said so

    # ── stability: the new records must not void an honest round ─────────────────────────────────

    def test_two_takes_of_an_untouched_linked_worktree_are_equal(self):
        """codex sweep, PR #67 pass 14, finding T5 — a fingerprint that moves on its own turns every honest
        round VOID, which is how a probe gets switched off. Two consecutive takes of an untouched LINKED
        worktree are byte-identical, and the take is not vacuous: it carries the worktree's `.git` file, the
        common dir's `config`, the per-worktree `HEAD`, the hooks directory and the ACL probe's own marker.
        (No mutant: this asserts the ABSENCE of movement, so the discriminating build is the shipped one —
        any record that were unstable would fail it. Its positive controls are T1-T4, which prove the same
        records DO move when the corresponding metadata changes.)"""
        first = self._fp(HELPER)
        second = self._fp(HELPER)
        self.assertEqual(first, second,
                         "two takes of an untouched linked worktree differ — the metadata/ACL records are "
                         "not stable, and every honest round is now void")
        self.assertRegex(first, rf'\n{re.escape(os.path.join(self.wt, ".git"))} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', first)
        self.assertRegex(first, rf'\n{re.escape(os.path.join(self.common, "config"))} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', first)
        self.assertRegex(first, rf'\n{re.escape(os.path.join(self.gitdir, "HEAD"))} F \d{{4}} {IDENT} \d+ [0-9a-f]{{64}}\n', first)
        hooks = os.path.join(self.common, "hooks")
        self.assertRegex(first, rf'\n{re.escape(hooks)} O \d{{4}} {IDENT}\n', first)
        if os.listdir(hooks):                                # an empty init template ships no samples
            self.assertRegex(first, rf'\n{re.escape(hooks)}/\S+ F ', first)
        self.assertIn("\nACL-PROBE %s\n" % ("done" if DARWIN else "unsupported"), first, first)
        self.assertRegex(first, rf'\nF \d{{4}} \d+ [0-9a-f]{{64}} {IDENT} "f\.txt"\n', first)


class FsmonitorIsNeverExecutedByTheProbeOrTheReport(unittest.TestCase):
    """`core.fsmonitor` names an EXECUTABLE that git runs on index refresh, so it is a way for a
    reviewer who can write the live checkout's config to have OUR OWN post-run probe run THEIR code,
    as us, in the tree we are measuring. `tree_fingerprint` has gone through `_u_git`
    (`--no-optional-locks -c core.fsmonitor=false`) since PR #67 pass 14 — but
    `tree_fingerprint_report`, which BOTH isolation harnesses call the moment a mutation is detected,
    still ran a plain `git status` / `git rev-parse` (codex, PR #67 pass 15 — reproduced). All three
    call sites use `_u_git` now.

    Measured on git 2.54.0 (Apple Git-157): a plain `git status --porcelain` EXECUTES the hook (the
    witness file appears); `git status` under `-c core.fsmonitor=false` does not; and `git rev-parse
    HEAD` does not execute it either way — so the two `rev-parse` call sites cannot be shown
    behaviourally and are covered by the text assertion below, which is stated as being that."""

    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="tree-fp-fsm.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.repo = os.path.join(self.scratch, "repo")
        subprocess.run(["git", "init", "-q", self.repo], check=True, capture_output=True)
        self._git("config", "user.email", "fixture@test")
        self._git("config", "user.name", "fixture")
        with open(os.path.join(self.repo, "f.txt"), "w", encoding="utf-8") as fh:
            fh.write("one\n")
        self._git("add", "-A")
        self._git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        # THE PLANTED HOOK AND ITS WITNESS LIVE OUTSIDE THE CHECKOUT, so neither is a tracked or
        # untracked path the fingerprint would notice — the only thing the witness records is that
        # the hook RAN.
        self.witness = os.path.join(self.scratch, "witness")
        self.hook = os.path.join(self.scratch, "fsmonitor-hook.sh")
        with open(self.hook, "w", encoding="utf-8") as fh:
            fh.write(f'#!/bin/sh\nprintf "FIRED %s\\n" "$*" >> {self.witness}\nexit 1\n')
        os.chmod(self.hook, 0o755)
        self._git("config", "core.fsmonitor", self.hook)

    def _git(self, *args):
        subprocess.run(["git", "-C", self.repo, *args], check=True, capture_output=True)

    def _fired(self):
        return os.path.exists(self.witness)

    def _clear(self):
        if os.path.exists(self.witness):
            os.unlink(self.witness)

    def _run(self, helper, script):
        env = dict(os.environ, GIT_CEILING_DIRECTORIES=self.scratch)
        return subprocess.run(["bash", "-c", script, "_", helper, self.repo],
                              capture_output=True, text=True, check=False, env=env)

    #: The report's status probe as shipped, and the plain `git` the control restores.
    REPORT_STATUS = '    _tf_after_status="$(_u_git -C "$1" status --porcelain 2>/dev/null)"\n'
    REPORT_STATUS_OLD = '    _tf_after_status="$(git -C "$1" status --porcelain 2>/dev/null)"\n'
    #: `tree_fingerprint <root> >/dev/null; tree_fingerprint_report <root> "" <a sha that is not HEAD>` —
    #: the empty before-status forces the report down its `rev-parse` branch as well.
    PROBE = '. "$1"; tree_fingerprint "$2" >/dev/null'
    REPORT = PROBE + '; tree_fingerprint_report "$2" "" 0000000000000000000000000000000000000000'

    def test_a_planted_fsmonitor_hook_is_not_executed_by_the_probe_or_by_the_report(self):
        """codex, PR #67 pass 15 — the report ran plain `git`, so a reviewer-planted `core.fsmonitor`
        executable was RUN by the very code path that reports the mutation it planted. Mutant: the
        report's `_u_git` status restored to a plain `git` — the hook FIRES."""
        # The premise, measured rather than assumed: an ordinary `git status` DOES execute the hook.
        subprocess.run(["git", "-C", self.repo, "status", "--porcelain"], check=True, capture_output=True)
        self.assertTrue(self._fired(),
                        "a plain `git status` did not execute the planted fsmonitor hook — this git does "
                        "not run it, so the fixture cannot show anything")
        self._clear()
        # The shipped build: neither the probe nor the report executes it.
        p = self._run(HELPER, self.PROBE)
        self.assertEqual(0, p.returncode, f"tree_fingerprint failed: {p.stderr!r}")
        self.assertFalse(self._fired(), "`tree_fingerprint` executed the planted fsmonitor hook")
        p = self._run(HELPER, self.REPORT)
        self.assertEqual(0, p.returncode, f"the report failed: {p.stderr!r}")
        self.assertIn("no new status line", p.stderr, f"the report did not run its branch: {p.stderr!r}")
        self.assertFalse(self._fired(),
                         "`tree_fingerprint_report` EXECUTED the reviewer-planted fsmonitor hook — the "
                         "report runs after a mutation is detected, as us, inside the measured tree")
        # The control: the report's plain `git status` restored — the hook fires (measured).
        with open(HELPER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.REPORT_STATUS), "the report's status probe is not unique")
        mutant = os.path.join(self.scratch, "tree-fingerprint-plain-git-report.sh")
        with open(mutant, "w", encoding="utf-8") as fh:
            fh.write(text.replace(self.REPORT_STATUS, self.REPORT_STATUS_OLD, 1))
        self._clear()
        p = self._run(mutant, self.PROBE)                 # the PROBE half of the control is still clean …
        self.assertEqual(0, p.returncode, f"the control's probe failed: {p.stderr!r}")
        self.assertFalse(self._fired(),
                         "the CONTROL fired on `tree_fingerprint` alone — the mutation is not what runs "
                         "the hook, so this test does not prove the report's own call")
        p = self._run(mutant, self.REPORT)                # … and only the REPORT executes the hook
        self.assertEqual(0, p.returncode, f"the control's report failed: {p.stderr!r}")
        self.assertTrue(self._fired(),
                        "the CONTROL (plain `git status` in the report) did NOT execute the hook — the "
                        "fixture is not the finding")
        with open(self.witness, encoding="utf-8") as fh:
            self.assertIn("FIRED", fh.read())

    def test_every_git_invocation_in_the_report_goes_through_the_safe_wrapper(self):
        """The two `rev-parse HEAD` call sites cannot be shown behaviourally — measured: `git rev-parse
        HEAD` does not execute an fsmonitor hook with or without `core.fsmonitor=false` — so they are
        asserted at the TEXT level, which is stated here rather than dressed up as a behavioural proof.
        Every `git` token in `tree_fingerprint_report`'s body is `_u_git`."""
        with open(HELPER, encoding="utf-8") as fh:
            text = fh.read()
        head = "tree_fingerprint_report() {\n"
        self.assertEqual(1, text.count(head), "the report's definition is not unique")
        start = text.index(head)
        end = text.index("\n}\n", start)
        body = text[start + len(head):end]
        self.assertIn("rev-parse HEAD", body, "the report no longer probes HEAD — re-derive this pin")
        # WHOLE-LINE COMMENTS ARE SKIPPED and nothing else is: a line that is entirely a comment cannot
        # invoke anything, while an inline comment sits on a line that can, so those stay scanned.
        bare = [ln for ln in body.splitlines()
                if not ln.lstrip().startswith("#")
                and re.search(r'(?<![\w-])git\b', ln) and not re.search(r'(?<![\w-])_u_git\b', ln)]
        self.assertEqual([], bare,
                         f"a plain `git` invocation survives in `tree_fingerprint_report` — a "
                         f"reviewer-planted `core.fsmonitor` would be executed by it: {bare}")
        self.assertEqual(3, len(re.findall(r'(?<![\w-])_u_git\b', body)),
                         f"the report's three git call sites are not all `_u_git`: {body!r}")
        # …and the premise for the pair above: `rev-parse` really is the call that cannot be shown.
        subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"], check=True, capture_output=True)
        self.assertFalse(self._fired(),
                         "a plain `git rev-parse HEAD` DOES execute the fsmonitor hook on this git — the "
                         "rev-parse call sites can be asserted behaviourally, and this text-level "
                         "assertion is weaker than what is available")


if __name__ == "__main__":
    unittest.main()
