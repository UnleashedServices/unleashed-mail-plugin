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


class TheManifestStructuralRejectionsAreExercised(unittest.TestCase):
    """The hooks-manifest rejections that decide whether a hook can fire at all.

    Each of these describes a manifest that PARSES but produces a hook Claude Code will never run —
    an event name it does not dispatch, a hook type it does not support, or a script reference that
    resolves nowhere or outside `scripts/`. None had a test: replacing each rejection with
    `if False:` left the whole suite green while the validator accepted the manifest.

    Every cell asserts the DIAGNOSTIC as well as the exit code. These guards sit in one loop over the
    same manifest, so a malformed entry usually trips a LATER one too — asserting only `returncode
    == 1` is satisfied by the mutant and proves nothing about the guard named in the docstring.
    """

    def _validate(self, hooks_obj, extra=None):
        with tempfile.TemporaryDirectory() as d:
            root = _make_root(Path(d), hooks_obj)
            if extra:
                extra(root)
            return _run(root)

    def test_an_unknown_EVENT_name_is_fatal(self):
        """An event key outside KNOWN_EVENTS is a hook that silently never fires."""
        res = self._validate({"hooks": {"PostToolUsage": [dict(_GOOD_ENTRY)]}})
        self.assertEqual(1, res.returncode, res.stdout)
        self.assertIn("unknown hook event", res.stdout)

    def test_an_unsupported_hook_TYPE_is_fatal(self):
        """Only `command` is dispatched; any other type is an entry that never runs."""
        entry = {"matcher": "Write",
                 "hooks": [{"type": "shell",
                            "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"}]}
        res = self._validate({"hooks": {"PostToolUse": [entry]}})
        self.assertEqual(1, res.returncode, res.stdout)
        self.assertIn("unsupported hook type", res.stdout)

    def test_a_script_ref_that_ESCAPES_scripts_is_fatal(self):
        """Containment: `scripts/../README.md` resolves to a real file, so an existence check alone
        would accept it. The guard is about WHERE it resolves, not whether it exists."""
        entry = {"matcher": "Write",
                 "hooks": [{"type": "command",
                            "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/../hooks/hooks.json"}]}
        res = self._validate({"hooks": {"PostToolUse": [entry]}})
        self.assertEqual(1, res.returncode, res.stdout)
        self.assertIn("escapes the scripts/ directory", res.stdout)

    def test_a_DANGLING_script_ref_is_fatal(self):
        """A reference under `scripts/` that names no file — the hook would fail at dispatch time,
        long after the manifest validated."""
        entry = {"matcher": "Write",
                 "hooks": [{"type": "command",
                            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gone.py"}]}
        res = self._validate({"hooks": {"PostToolUse": [entry]}})
        self.assertEqual(1, res.returncode, res.stdout)
        self.assertIn("scripts/gone.py", res.stdout)

    def test_a_WELL_FORMED_manifest_still_passes(self):
        """The positive control for all four: without it, a validator that rejected every manifest
        would satisfy each cell above."""
        res = self._validate({"hooks": {"PostToolUse": [dict(_GOOD_ENTRY)]}})
        self.assertEqual(0, res.returncode, res.stdout)


class TheMatcherRejectionVocabularyIsExercised(unittest.TestCase):
    """`validate_matcher`'s rejection vocabulary — every branch of it, and its limits.

    A matcher carrying a control character, an invisible codepoint, or a full-width homoglyph fails
    the exact-matcher grammar, is then treated as a REGEX, skips the known/stale checks, and matches
    NO tool at runtime. The hook silently never fires. Each branch below was added for a specific
    bypass found in review, and none of them had a test: replacing the rejections with `if False:`
    left the whole suite green while the validator accepted every case here.

    The negative cells are not decoration. Two of the branches are deliberately narrow — a plain
    space is legal, and ordinary combining marks are legal — so a guard that simply refused
    non-ASCII would pass every positive cell above while breaking legitimate matchers. Asserting
    both directions is what pins the carve-outs.
    """

    def _matcher(self, matcher: str):
        with tempfile.TemporaryDirectory() as d:
            entry = {"matcher": matcher, "hooks": _GOOD_ENTRY["hooks"]}
            root = _make_root(Path(d), {"hooks": {"PostToolUse": [entry]}})
            return _run(root)

    def test_every_rejected_class_is_refused(self):
        cases = {
            "control (ord<32)":            "\tTask",
            "delete (ord==127)":           "Task\x7f",
            "Cf zero-width space":         "Task\u200b",
            "Cf BOM":                      "Task\ufeff",
            "Cn default-ignorable":        "Task\u2065",
            "Lo HANGUL FILLER":            "\u3164Edit",
            "Co private use":              "Task\ue000",
            "non-space whitespace":        "Task\u00a0",
            "NFKC full-width homoglyph":   "\uff25\uff44\uff49\uff54",
        }
        for label, matcher in cases.items():
            with self.subTest(case=label, matcher=matcher):
                result = self._matcher(matcher)
                self.assertEqual(1, result.returncode,
                                 f"{label}: accepted a matcher that matches NO tool at runtime\n"
                                 f"{result.stdout}")
                self.assertIn("matcher", result.stdout)

    def test_the_carve_outs_still_pass(self):
        """The guard must not be over-broad. `c != " "` keeps a plain space legal, and the
        default-ignorable check is by PROPERTY, not "non-ASCII" — `café.*` carries ordinary
        combining marks and must still validate."""
        for label, matcher in {"plain space in a list": "Write, Edit",
                               "ordinary accented regex": "caf\u00e9.*"}.items():
            with self.subTest(case=label, matcher=matcher):
                result = self._matcher(matcher)
                self.assertEqual(0, result.returncode,
                                 f"{label}: a legitimate matcher was rejected\n{result.stdout}")


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
