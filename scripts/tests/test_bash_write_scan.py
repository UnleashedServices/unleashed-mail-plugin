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

    def test_heredoc_with_redirect_after_delimiter(self):
        # codex review of #53: a redirect AFTER the heredoc delimiter (`cat <<EOF > sensitive`) is a real
        # write and must be caught — the body is consumed at the newline, so the same-line redirect survives.
        self.assertIn("Keychain.swift", targets("cat <<EOF > Keychain.swift\ndata\nEOF"))
        self.assertIn("Keychain.swift", targets("cat <<EOF >> Keychain.swift\nx\nEOF"))
        # a heredoc redirected to a NON-sensitive file must not ask
        self.assertNotIn("Keychain.swift", targets("cat <<EOF > /tmp/safe.txt\ndata\nEOF"))
        # the interpreter-heredoc-as-code path still works
        self.assertIn("OAuthService.swift", targets("python3 <<PY\nopen(OAuthService.swift)\nPY"))

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

    def test_node_eval_equals_form_is_inline_code(self):
        # codex review of #53: node's documented `--eval=`/`--print=` equals form is inline code.
        self.assertIn("Keychain.swift", targets('node --eval=\'require("fs").unlinkSync("Keychain.swift")\''))
        self.assertIn("Keychain.swift", targets('node --print=\'require("fs").readFileSync("Keychain.swift")\''))
        self.assertIn("Keychain.swift", targets('node -e \'fs.unlinkSync("Keychain.swift")\''))  # short form still


class SweepRound4(unittest.TestCase):
    """codex review of #53 (round 4) + the adversarial completeness sweep. Each asserts a write CLASS the
    lexer must catch (fail-open proof) or a benign read it must NOT (over-ask proof)."""

    # >& file-redirect (both streams to a file) vs fd dup/close
    def test_amp_redirect_writes_file(self):
        for cmd, want in (("echo hi >& Keychain.swift", "Keychain.swift"),
                          ("echo hi >&Keychain.swift", "Keychain.swift"),
                          ('printf x >& OAuthService.swift', "OAuthService.swift"),
                          ('echo hi >& "Keychain.swift"', "Keychain.swift")):
            self.assertIn(want, targets(cmd), cmd)

    def test_amp_redirect_fd_ref_is_not_a_write(self):
        for cmd in ("echo err >&2", "echo x >&-", "echo x 2>&1"):
            self.assertEqual(targets(cmd), [], cmd)

    # command substitution / expansion embedded in a target word
    def test_command_substitution_in_operand(self):
        for cmd in ('rm "$(printf Keychain.swift)"', 'rm $(printf Keychain.swift)',
                    'rm `echo Keychain.swift`', 'mv "$(echo Keychain.swift)" /tmp',
                    'cp x.swift "$(echo Keychain.swift)"', 'tee "$(echo Keychain.swift)"',
                    'echo x > "$(echo Keychain.swift)"', 'echo x > `echo Keychain.swift`',
                    'dd of="$(echo Keychain.swift)"', 'rm "$(basename /p/Keychain.swift)"'):
            self.assertIn("Keychain.swift", targets(cmd), cmd)

    def test_brace_suffix_expansion(self):
        self.assertIn("Keychain.swift", targets("rm Keychain.swift{,.bak}"))

    # -- end of options
    def test_dashdash_end_of_options(self):
        for cmd in ("rm -- -Keychain.swift", "rm -f -- -Keychain.swift", "mv -- -Keychain.swift /tmp",
                    "tee -- -Keychain.swift", "sed -i -- -Keychain.swift", "touch -- -Keychain.swift",
                    "cp x.swift -- -Keychain.swift", 'rm -- "-Keychain.swift"'):
            self.assertIn("-Keychain.swift", targets(cmd), cmd)

    # command wrappers
    def test_wrapper_prefixes(self):
        for cmd, want in (("timeout 5 rm Keychain.swift", "Keychain.swift"),
                          ("timeout 30s rm -f OAuthService.swift", "OAuthService.swift"),
                          ("timeout --signal=TERM 5 rm Keychain.swift", "Keychain.swift"),
                          ("timeout -k 10 5 rm Keychain.swift", "Keychain.swift"),
                          ("nohup rm Keychain.swift", "Keychain.swift"),
                          ("sudo timeout 5 rm Keychain.swift", "Keychain.swift"),
                          ("doas rm Keychain.swift", "Keychain.swift"),
                          ("doas -u root -- rm Keychain.swift", "Keychain.swift"),
                          ("taskset -c 0 rm Keychain.swift", "Keychain.swift"),
                          ("taskset 0x1 rm Keychain.swift", "Keychain.swift"),
                          ("chrt 1 rm Keychain.swift", "Keychain.swift"),
                          ("arch -arm64 rm Keychain.swift", "Keychain.swift"),
                          ("xcrun rm Keychain.swift", "Keychain.swift")):
            self.assertIn(want, targets(cmd), cmd)

    def test_taskset_cpu_opt_does_not_eat_verb(self):
        # -c consumes the cpu spec, so there is NO mask positional to eat the child verb
        self.assertIn("Keychain.swift", targets("taskset -c 0 rm Keychain.swift"))
        self.assertEqual(targets("taskset -c 0 grep x data.txt"), [])

    def test_xcrun_find_is_a_probe(self):
        self.assertEqual(targets("xcrun -f rm Keychain.swift"), [])  # -f prints a path, runs nothing

    # interpreters
    def test_ruby_e_is_code_but_E_is_encoding(self):
        self.assertIn("Keychain.swift", targets('ruby -e \'File.delete("Keychain.swift")\''))
        self.assertEqual(targets("ruby -E UTF-8 OAuthService.swift"), [])  # -E is encoding, arg is a read

    def test_awk_program_redirect_writes(self):
        self.assertIn("Keychain.swift", targets('awk \'BEGIN{print "x" > "Keychain.swift"}\''))
        self.assertIn("Info.plist", targets('gawk \'{printf "x" >> "Info.plist"}\''))
        self.assertEqual(targets("awk '{print}' data.swift"), [])       # reads data.swift, no `>` -> no ask

    def test_osascript_dash_e_is_code(self):
        self.assertIn("Keychain.swift", targets('osascript -e \'do shell script "rm Keychain.swift"\''))

    # brace group + subshell that hide the verb / glue a trailing )
    def test_brace_group_command_position(self):
        for cmd in ("{ rm Keychain.swift; }", "{ mv Keychain.swift /tmp; }", "{ rm -f AuthService.swift; }"):
            self.assertTrue(any("Keychain.swift" in t or "AuthService.swift" in t for t in targets(cmd)), cmd)

    def test_brace_arg_position_stays_one_word(self):
        # `{a,b}` in ARGUMENT position is brace expansion, not a group — must not split cp's source/dest
        self.assertEqual(targets("cp {a,b}.swift dest/"), ["dest"])

    def test_subshell_trailing_paren_deglued(self):
        for cmd in ("(rm Keychain.swift)", "(cd Sources && rm Keychain.swift)",
                    "(cp Keychain.swift.tmp Keychain.swift)"):
            self.assertIn("Keychain.swift", targets(cmd), cmd)

    # new write verbs
    def test_new_write_verbs(self):
        self.assertIn("Keychain.swift", targets("git rm Keychain.swift"))
        self.assertIn("Keychain.swift", targets("git checkout -- Keychain.swift"))
        self.assertIn("Keychain.swift", targets("git restore Keychain.swift"))
        self.assertIn("Keychain.swift", targets("git mv old.swift Keychain.swift"))
        self.assertIn("Keychain.swift", targets("truncate -s 0 Keychain.swift"))
        self.assertIn("Info.plist", targets("ditto src Info.plist"))
        self.assertIn("Migration001.swift", targets("rsync rs.txt Migration001.swift"))
        self.assertIn("AuthService.swift", targets("patch AuthService.swift < p.diff"))

    def test_git_branch_switch_is_not_a_write(self):
        for cmd in ("git checkout main", "git checkout -b Keychain.swift", "git status",
                    "git log Keychain.swift", "git diff Keychain.swift"):
            self.assertEqual(targets(cmd), [], cmd)

    # input-redirect read source must NOT be emitted as a write target
    def test_input_redirect_source_not_written(self):
        self.assertNotIn("Keychain.swift", targets("tee out.log < Keychain.swift"))
        self.assertNotIn("Keychain.swift", targets("rm out.txt < Keychain.swift"))
        self.assertIn("out.log", targets("tee out.log < Keychain.swift"))  # the real write target survives


class SweepRound5(unittest.TestCase):
    """codex review of #53 (round 5) — further lexer classes."""

    def test_patch_output_and_reject_files(self):
        for cmd in ("patch --output=Keychain.swift < p.diff", "patch -o Keychain.swift orig.c < p.diff",
                    "patch --reject-file Keychain.swift < p.diff", "patch --reject-file=Keychain.swift < p.diff",
                    "patch -r Keychain.swift < p.diff", "patch AuthService.swift < p.diff"):
            self.assertTrue(any(b in t for t in targets(cmd) for b in ("Keychain.swift", "AuthService.swift")), cmd)

    def test_find_exec_subcommand(self):
        self.assertIn("Keychain.swift", targets("find . -exec rm Keychain.swift ;"))
        self.assertIn("Keychain.swift", targets("find . -name x -exec mv Keychain.swift /t ;"))
        self.assertEqual(targets("find . -type f -exec grep foo Keychain.swift ;"), [])  # exec grep = read

    def test_versioned_interpreters(self):
        self.assertIn("Keychain.swift", targets('python3.12 -c \'open("Keychain.swift","w")\''))
        self.assertIn("Keychain.swift", targets('ruby3.3 -e \'File.delete("Keychain.swift")\''))
        self.assertIn("Keychain.swift", targets('node20 -e \'require("fs").unlinkSync("Keychain.swift")\''))
        self.assertIn("Keychain.swift", targets('perl5.38 -e \'unlink "Keychain.swift"\''))

    def test_versioned_stem_guard_no_false_normalize(self):
        # `sha256` must NOT normalize to the `sha` interpreter (there is none) — it is not an interpreter arm
        self.assertEqual(targets('sha256 Keychain.swift'), [])

    def test_shell_keyword_prefixes(self):
        for cmd in ("! rm Keychain.swift", "if rm Keychain.swift; then :; fi",
                    "while rm Keychain.swift; do break; done", "until rm Keychain.swift; do :; done"):
            self.assertIn("Keychain.swift", targets(cmd), cmd)

    def test_git_broad_pathspec_documented_boundary(self):
        # broad `.`/tree pathspec emits only the literal `.` (basename never matches the sensitive policy) —
        # out of scope like `rm -rf <dir>`; NAMED pathspecs ARE caught.
        self.assertEqual(targets("git restore ."), ["."])
        self.assertIn("Keychain.swift", targets("git restore Keychain.swift"))
        self.assertIn("OAuthService.swift", targets("git checkout -- OAuthService.swift"))

    def test_git_checkout_named_file_without_dashdash(self):
        # gemini review of #53: `git checkout <file>` (no `--`) discards local edits -> a write. Distinguish
        # a file pathspec from a branch name by the file-shaped heuristic.
        self.assertIn("Keychain.swift", targets("git checkout Keychain.swift"))
        self.assertIn("OAuthService.swift", targets("git checkout HEAD OAuthService.swift"))
        self.assertIn("Info.plist", targets("git checkout Info.plist"))
        # branch switches / branch creation must NOT be treated as file writes
        self.assertEqual(targets("git checkout main"), [])
        self.assertEqual(targets("git checkout -b Keychain.swift"), [])   # creating a branch, not a file
        self.assertEqual(targets("git checkout feature/foo"), [])

    def test_patch_attached_output_only_via_equals_branch(self):
        # the ATTACHED `--output=FILE` form has no positional to fall back on — proves the `=` branch
        self.assertEqual(targets("patch --output=Keychain.swift < p.diff"), ["Keychain.swift"])


class SweepRound6(unittest.TestCase):
    """codex review of #53 (round 6)."""

    def test_patch_attached_short_output_reject(self):
        self.assertEqual(targets("patch -oKeychain.swift < change.diff"), ["Keychain.swift"])
        self.assertEqual(targets("patch -rKeychain.swift < change.diff"), ["Keychain.swift"])

    def test_xargs_sed_inplace_child(self):
        for cmd in ("printf 'Keychain.swift' | xargs sed -i 's/a/b/'",
                    "printf 'Keychain.swift' | xargs sed -i.bak 's/a/b/'",
                    "printf 'Keychain.swift' | xargs -n1 sed -i 's/a/b/'",
                    "printf 'Keychain.swift' | xargs truncate -s 0"):
            self.assertIn("Keychain.swift", targets(cmd), cmd)

    def test_xargs_read_child_still_not_flagged(self):
        # sed WITHOUT -i streams to stdout (read); grep/cat read — must NOT ask
        for cmd in ("printf 'Keychain.swift' | xargs sed 's/a/b/'",
                    "printf 'Keychain.swift' | xargs grep foo",
                    "printf 'Keychain.swift' | xargs cat"):
            self.assertNotIn("Keychain.swift", targets(cmd), cmd)

    def test_find_start_path_deleted(self):
        # codex review of #53: a sensitive file as a find STARTING POINT (not behind -name) is deleted by a
        # writing action (-delete, or an -exec that writes) -> emit it.
        for cmd, want in (("find Keychain.swift -delete", "Keychain.swift"),
                          ("find OAuthService.swift -maxdepth 0 -delete", "OAuthService.swift"),
                          ("find . Keychain.swift -delete", "Keychain.swift"),
                          ("find src Keychain.swift -type f -delete", "Keychain.swift"),
                          ("find Keychain.swift -exec rm {} ;", "Keychain.swift"),
                          ("find -L Keychain.swift -delete", "Keychain.swift"),
                          ("find . -name Keychain.swift -delete", "Keychain.swift")):
            self.assertIn(want, targets(cmd), cmd)

    def test_find_non_destructive_or_read_exec_is_not_a_write(self):
        # a start path with NO writing action is a search/list (read) — must NOT be a target
        for cmd in ("find Keychain.swift -type f", "find Keychain.swift",
                    "find . -type f -exec grep foo Keychain.swift ;",   # exec grep = read
                    "find Keychain.swift -exec grep foo {} ;"):          # reads the matched start path
            self.assertNotIn("Keychain.swift", targets(cmd), cmd)


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
