"""COREDEV-2503 F4/F12 unit tests for scripts/lib/bash-write-scan.py — the structured, quote/escape/
operator-aware write-target lexer that replaced the guard's O(n^2) parser + quote-blind greps. Each case is
a mutation proof: revert the corresponding lexer behavior and the assertion flips."""
import importlib.util
import os
import time
import unittest

_MOD = os.path.join(os.path.dirname(__file__), "..", "lib", "bash-write-scan.py")
_spec = importlib.util.spec_from_file_location("bash_write_scan", _MOD)
bws = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bws)


def targets(cmd):
    return [os.path.basename(t.rstrip("/")) for t in bws.write_targets(cmd)]


class QuoteAwareness(unittest.TestCase):
    # mutation-KILLS — WRONG in the pre-fix quote-blind parser:
    def test_midword_quote_is_dequoted(self):
        self.assertIn("Keychain.swift", targets('rm Key"chain".swift'))          # was a bypass

    def test_quoted_redirect_is_literal_not_a_write(self):
        self.assertNotIn("Keychain.swift", targets("echo '> Keychain.swift'"))    # was an over-ask

    def test_escaped_redirect_is_literal_not_a_write(self):
        self.assertNotIn("Keychain.swift", targets("echo \\> Keychain.swift"))    # was an over-ask


class WriteContext(unittest.TestCase):
    def test_active_redirect_writes(self):
        self.assertIn("Keychain.swift", targets("echo x > Keychain.swift"))

    def test_clobber_redirect_writes(self):
        self.assertIn("Keychain.swift", targets("echo x >| Keychain.swift"))

    def test_mv_removes_source(self):
        self.assertIn("Keychain.swift", targets("mv Keychain.swift /tmp/x"))

    def test_cp_source_is_not_written(self):
        self.assertNotIn("Keychain.swift", targets("cp Keychain.swift /tmp/x"))

    def test_cp_dest_is_written(self):
        self.assertIn("Keychain.swift", targets("cp template.swift Keychain.swift"))

    def test_read_only_grep_has_no_target(self):
        self.assertEqual(targets("grep foo Keychain.swift"), [])


class F12Arms(unittest.TestCase):
    def test_subshell_group_stripped(self):
        self.assertIn("Keychain.swift", targets("( rm Keychain.swift )"))

    def test_sed_inplace_suffix(self):
        self.assertIn("Info.plist", targets("sed --in-place=bak Info.plist"))

    def test_dd_of(self):
        self.assertIn("Keychain.swift", targets("dd of=Keychain.swift"))

    def test_find_delete(self):
        self.assertIn("Keychain.swift", targets("find . -name 'Keychain.swift' -delete"))

    def test_xargs_write_from_pipeline(self):
        self.assertIn("Keychain.swift", targets("printf 'Keychain.swift' | xargs rm"))

    def test_xargs_options_before_command(self):
        # codex review of #53: options BEFORE the child verb must be skipped, else the write bypasses.
        for cmd in ("printf 'Keychain.swift' | xargs -n 1 rm",
                    "printf 'Keychain.swift' | xargs -I{} rm {}",
                    "printf 'Keychain.swift' | xargs -0 -P4 rm",
                    "printf 'Keychain.swift' | xargs --max-args 1 rm"):
            self.assertIn("Keychain.swift", targets(cmd), cmd)

    def test_xargs_read_child_not_flagged(self):
        # a read-only child (grep) via xargs must NOT ask, even with options
        self.assertNotIn("Keychain.swift", targets("printf 'Keychain.swift' | xargs -n 1 grep foo"))


class Robustness(unittest.TestCase):
    def test_large_command_is_fast_and_linear(self):
        big = "echo " + ("a" * 80000)
        t0 = time.time()
        bws.write_targets(big)
        self.assertLess(time.time() - t0, 3.0, "80KB scan must be well under the hook timeout (O(n))")

    def test_large_obfuscated_write_still_caught(self):
        cmd = "echo " + ("a" * 40000) + " ; rm Key\"chain\".swift"
        self.assertIn("Keychain.swift", targets(cmd))


if __name__ == "__main__":
    unittest.main()
