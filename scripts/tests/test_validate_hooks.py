"""MIN-20: validate-hooks.py must flag a misspelled/missing `matcher` key. A hook entry with no
`matcher` silently defaults to match-ALL, firing the hook on every tool call. Runs the validator as a
subprocess against a synthetic plugin root (the module name has a hyphen)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_VALIDATOR = os.path.join(os.path.dirname(__file__), "..", "validate-hooks.py")


def _run(root: Path):
    return subprocess.run([sys.executable, _VALIDATOR, "--root", str(root), "--strict"],
                          capture_output=True, text=True)


def _make_root(tmp: Path, hooks_obj: dict) -> Path:
    (tmp / "scripts").mkdir()
    (tmp / "scripts" / "x.sh").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    (tmp / "hooks").mkdir()
    (tmp / "hooks" / "hooks.json").write_text(json.dumps(hooks_obj), encoding="utf-8")
    return tmp


_GOOD_ENTRY = {"matcher": "Write|Edit",
               "hooks": [{"type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"}]}


class MatcherKeyTypoTest(unittest.TestCase):
    def test_clean_manifest_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = _make_root(Path(d), {"hooks": {"PostToolUse": [dict(_GOOD_ENTRY)]}})
            self.assertEqual(_run(root).returncode, 0)

    def test_matchers_typo_fails_strict(self):
        with tempfile.TemporaryDirectory() as d:
            bad = {"matchers": "Write|Edit",  # typo — would silently match ALL tools
                   "hooks": _GOOD_ENTRY["hooks"]}
            root = _make_root(Path(d), {"hooks": {"PostToolUse": [bad]}})
            res = _run(root)
            self.assertEqual(res.returncode, 1, res.stdout)
            self.assertIn("matcher", res.stdout)

    def test_unknown_hook_key_is_warned_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            entry = {"matcher": "Write",
                     "hooks": [{"type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/x.sh",
                                "timeut": 5}]}  # typo'd timeout — warned, not fatal
            root = _make_root(Path(d), {"hooks": {"PostToolUse": [entry]}})
            res = _run(root)
            self.assertEqual(res.returncode, 0, res.stdout)
            self.assertIn("timeut", res.stdout)


if __name__ == "__main__":
    unittest.main()
