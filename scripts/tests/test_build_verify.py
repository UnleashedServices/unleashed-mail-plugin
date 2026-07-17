"""Tests for scripts/review/build-verify.sh — logic verified with mocked xcodebuild/swiftlint,
so the extracted Step-4 gate is checkable in CI without an Xcode toolchain."""
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "review", "build-verify.sh"))

XCODEBUILD_MOCK = textwrap.dedent("""\
    #!/usr/bin/env bash
    # $1 is the subcommand. B6 (COREDEV-2503): the script compiles ONCE via `build-for-testing`, then runs
    # `test-without-building` (reuse) — NOT the plain `build`+`test` pair that recompiled twice.
    [ -n "${MOCK_LOG:-}" ] && printf '%s\\n' "$1" >> "$MOCK_LOG"
    if [ "$1" = "build-for-testing" ]; then echo "mock build output"; exit "${MOCK_BUILD_RC:-0}"; fi
    if [ "$1" = "test-without-building" ]; then echo "mock test output"; exit "${MOCK_TEST_RC:-0}"; fi
    exit 0
""")
SWIFTLINT_MOCK = textwrap.dedent("""\
    #!/usr/bin/env bash
    # `swiftlint lint --baseline ...` = whole-repo baseline arm; anything else = changed-files arm
    if [ "$1" = "lint" ]; then exit "${MOCK_BASELINE_RC:-0}"; fi
    exit "${MOCK_CHANGED_RC:-0}"
""")


class BuildVerifyTest(unittest.TestCase):
    def setUp(self):
        self.mock = tempfile.mkdtemp()
        for name, body in (("xcodebuild", XCODEBUILD_MOCK), ("swiftlint", SWIFTLINT_MOCK)):
            p = os.path.join(self.mock, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            os.chmod(p, 0o755)
        self.repo = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.repo, "Unleashed Mail", "Sources"))
        open(os.path.join(self.repo, "swiftlint-baseline.json"), "w").close()

    def tearDown(self):
        for d in (self.mock, self.repo):
            shutil.rmtree(d, ignore_errors=True)

    def run_bv(self, changed="README.md\n", **env):
        e = dict(os.environ)
        e["PATH"] = self.mock + os.pathsep + e["PATH"]
        e.update({k: str(v) for k, v in env.items()})
        return subprocess.run(["bash", SCRIPT], input=changed, capture_output=True,
                              text=True, cwd=self.repo, env=e)

    def _touch_source(self, name):
        p = os.path.join(self.repo, "Unleashed Mail", "Sources", name)
        open(p, "w").close()
        return f"Unleashed Mail/Sources/{name}\n"

    # --- hard gates ------------------------------------------------------------------
    def test_all_pass(self):
        r = self.run_bv()
        self.assertEqual(r.returncode, 0, r.stdout)
        for gate in ("✅ build", "✅ lint", "✅ tests"):
            self.assertIn(gate, r.stdout)

    def test_b6_compiles_once_via_build_for_testing(self):
        # COREDEV-2503 B6: the plain `build`+`test` pair recompiled everything twice. The script must use
        # `build-for-testing` (compile app+tests once) then `test-without-building` (reuse) — and each
        # failure must still propagate (the RC mocks below prove they are the invoked subcommands).
        log = os.path.join(self.mock, "xcodebuild.log")
        r = self.run_bv(MOCK_LOG=log)
        self.assertEqual(r.returncode, 0, r.stdout)
        invoked = [ln for ln in open(log, encoding="utf-8").read().splitlines() if ln]
        self.assertIn("build-for-testing", invoked)
        self.assertIn("test-without-building", invoked)
        self.assertNotIn("build", invoked, "no bare recompiling `build` subcommand")
        self.assertNotIn("test", invoked, "no bare recompiling `test` subcommand")

    def test_build_fail_exits_nonzero(self):
        r = self.run_bv(MOCK_BUILD_RC=65)
        self.assertEqual(r.returncode, 1)
        self.assertIn("❌ build", r.stdout)

    def test_test_fail_exits_nonzero(self):
        r = self.run_bv(MOCK_TEST_RC=1)
        self.assertEqual(r.returncode, 1)
        self.assertIn("❌ tests", r.stdout)

    def test_baseline_lint_fail_exits_nonzero(self):
        r = self.run_bv(MOCK_BASELINE_RC=2)
        self.assertEqual(r.returncode, 1)
        self.assertIn("❌ lint", r.stdout)

    def test_changed_swift_lint_fail_exits_nonzero(self):
        changed = self._touch_source("Foo.swift")
        r = self.run_bv(changed=changed, MOCK_CHANGED_RC=2)
        self.assertEqual(r.returncode, 1)
        self.assertIn("❌ lint", r.stdout)

    # --- subtle behaviors preserved from the inline block ----------------------------
    def test_deleted_changed_swift_is_not_linted(self):
        # a changed .swift that no longer exists must be filtered out of the changed arm, so its
        # (would-be) failure can't fail the gate — the empty-set guard keeps xargs from running.
        r = self.run_bv(changed="Unleashed Mail/Sources/Gone.swift\n", MOCK_CHANGED_RC=2)
        self.assertEqual(r.returncode, 0)
        self.assertIn("✅ lint", r.stdout)

    def test_non_swift_change_skips_changed_arm(self):
        r = self.run_bv(changed="docs/README.md\n", MOCK_CHANGED_RC=2)
        self.assertEqual(r.returncode, 0)  # non-.swift -> changed arm skipped -> lint OK

    def test_missing_test_file_is_a_warning_not_a_gate(self):
        changed = self._touch_source("Bar.swift")  # no BarTests.swift
        r = self.run_bv(changed=changed)
        self.assertEqual(r.returncode, 0)  # advisory only
        self.assertIn("Missing test file", r.stdout)
        self.assertIn("BarTests.swift", r.stdout)

    def test_present_test_file_no_warning(self):
        changed = self._touch_source("Baz.swift")
        os.makedirs(os.path.join(self.repo, "Unleashed MailTests"), exist_ok=True)
        open(os.path.join(self.repo, "Unleashed MailTests", "BazTests.swift"), "w").close()
        r = self.run_bv(changed=changed)
        self.assertNotIn("Missing test file", r.stdout)


if __name__ == "__main__":
    unittest.main()
