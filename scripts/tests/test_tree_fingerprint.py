#!/usr/bin/env python3
"""`disposable_fingerprint` (scripts/review/tree-fingerprint.sh) serialises paths INJECTIVELY.

THE FINDING (codex, PR #67 pass 9 — reproduced). The record was line-oriented and carried the path
RAW: a reviewer that deleted `b` and renamed `a` to `a<newline><b's whole record>` produced output
byte-identical to the untouched tree's, and the before/after gate in all three harnesses accepted the
altered checkout. Paths (and link targets) are JSON-encoded now — pure ASCII, quoted, escaped — so
one entry is one line and a newline in a name cannot forge a second record.

Both builds are RUN: the shipped helper must tell the two trees apart; a copy with the encoding removed
(`q = rel`) must NOT — a control that cannot collide would prove the fixture, not the fix.
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


if __name__ == "__main__":
    unittest.main()
