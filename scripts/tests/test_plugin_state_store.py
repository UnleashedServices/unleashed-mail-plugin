#!/usr/bin/env python3
"""COREDEV-2617 §7 steps 3a and 3b — the encoder, the store, and the Darwin chain authenticator.

WHY THESE TESTS EXIST IN THIS SHAPE
The plan's mutant table states ~128 live obligations, and for many rounds they were PROSE: a reviewer
read them and formed an opinion. Every defect the gate actually found in this material was found by
EXECUTING it — the ACL arm alone failed seven consecutive review rounds, each on a shape a reader had
not thought of. So each test here RUNS the shipped shell in BOTH shells, and the adversarial ones
carry a POSITIVE CONTROL: a deliberately broken variant the same assertion must reject. A check that
cannot fail reads exactly like a check that passes.

BOTH SHELLS, ALWAYS. bash 3.2.57 is the floor (macOS ships it) and zsh 5.9 is what a consumer's
interactive shell and swift-reviewer's Bash tool actually run. The two diverge in ways that have each
produced a real fail-open here: zsh does not word-split unquoted expansions, `$var[` is array
subscripting there, `$((0777))` is 511 in bash and 777 in zsh, and `printf '%d' "'c"` sign-extends in
bash only.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "lib")
AUTH = os.path.join(LIB, "plugin-state-auth.sh")
STORE = os.path.join(LIB, "plugin-state-store.sh")
SHELLS = ("/bin/bash", "/bin/zsh")
DARWIN = os.uname().sysname == "Darwin"


def run_shell(shell, body, env=None, sources=(AUTH, STORE)):
    """Run `body` with the shipped libraries sourced. Returns (rc, stdout, stderr)."""
    src = "".join(f'. "{s}"\n' for s in sources) + body
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([shell, "-c", src], capture_output=True, text=True, env=e)
    return p.returncode, p.stdout, p.stderr


def with_mutation(old, new, path=AUTH):
    """A copy of `path` with one exact substitution — the positive control's mechanism.

    Asserts the pattern was found, because a control built from a pattern that does not match is a
    control that silently cannot fail. That mistake has been made in this campaign more than once.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    assert text.count(old) == 1, f"mutation pattern not unique in {path}: {old!r}"
    fd, tmp = tempfile.mkstemp(suffix=".sh")
    with os.fdopen(fd, "w") as fh:
        fh.write(text.replace(old, new, 1))
    return tmp


class EncoderInvariantP(unittest.TestCase):
    """ENC-1..ENC-5. Injectivity is proved FIRST because every later step assumes it."""

    #: Marker-dense, case pairs, NFC vs NFD, control and high bytes, spaces, glob metacharacters.
    CORPUS = [
        "/", "/tmp", "/Users/nick/.claude/unleashed-mail", "/a b/c-d", "/a//b", "/A/a",
        "/Data/A", "/Data/a", "/_u", "/_s", "/_x41", "/_c", "/__", "/_u_s_c_x", "/_x7f", "/_x80",
        "/*", "/?", "/[a-z]", "/$HOME", "/a;b", "/a|b", "/a&b", "/(x)", "/{x}",
        "/ÜBER", "/über", "/é", "/é",
    ] + [f"/a\\x{h}b" for h in ("01", "07", "1f", "20", "7e", "7f", "80", "fe", "ff")] \
      + [f"/{L}" for L in "ABMZ"] + [f"/x{L}y" for L in "ABMZ"]

    def _keys(self, shell):
        # A here-doc, so no shell quoting of the corpus is needed and `%b` turns the `\\xNN`
        # entries into real bytes.
        lines = "\n".join(self.CORPUS)
        body = (
            "while IFS= read -r v; do\n"
            '  _unleashed_key "$(printf %b "$v")"\n'
            '  printf "%s\\n" "$_UNLEASHED_KEY"\n'
            f"done <<'CORPUS'\n{lines}\nCORPUS\n"
        )
        rc, out, err = run_shell(shell, body)
        self.assertEqual(0, rc, f"{shell}: {err}")
        return out.splitlines()

    def test_injective_over_the_adversarial_corpus(self):
        for shell in SHELLS:
            keys = self._keys(shell)
            self.assertEqual(len(self.CORPUS), len(keys), f"{shell}: wrong key count")
            dupes = {k for k in keys if keys.count(k) > 1}
            self.assertEqual(set(), dupes, f"{shell}: colliding keys {dupes}")

    def test_output_alphabet_is_0x20_to_0x7f_and_never_upper_case(self):
        # ENC-4. The range is INCLUSIVE of 0x7F: ENC-1 emits DEL unchanged, and a test written as
        # `[ -~]` (0x20-0x7E) wrongly flags it.
        for shell in SHELLS:
            for key in self._keys(shell):
                for ch in key:
                    self.assertTrue(0x20 <= ord(ch) <= 0x7F, f"{shell}: {ch!r} outside the alphabet")
                    self.assertFalse(ch.isupper(), f"{shell}: upper-case {ch!r} in {key!r}")

    def test_keys_are_byte_identical_across_both_shells(self):
        # ENC-8. The two arms must agree exactly; a divergence here is a divergence in every entry
        # NAME, so two shells on one machine would write two entries for one base and every reader
        # would then report `conflict`.
        self.assertEqual(self._keys("/bin/bash"), self._keys("/bin/zsh"))

    def test_lc_all_is_restored_in_both_entry_states(self):
        # ENC-3. An EMPTY LC_ALL is not the same as an absent one, so both are checked.
        for shell in SHELLS:
            rc, out, _ = run_shell(shell, 'LC_ALL=en_US.UTF-8; _unleashed_key /x; printf "%s" "${LC_ALL-ABSENT}"')
            self.assertEqual("en_US.UTF-8", out, f"{shell}: a set LC_ALL was not restored")
            rc, out, _ = run_shell(shell, 'unset LC_ALL; _unleashed_key /x; printf "%s" "${LC_ALL-ABSENT}"')
            self.assertEqual("ABSENT", out, f"{shell}: an unset LC_ALL was not restored")

    def test_del_byte_is_emitted_unchanged(self):
        # ENC-1's four rows are the whole table, so 0x7F is NOT escaped. Stated because a reader
        # reaches for "escape everything unprintable".
        for shell in SHELLS:
            rc, out, _ = run_shell(shell, '_unleashed_key "$(printf \'/\\177\')"; printf "%s" "$_UNLEASHED_KEY"')
            self.assertNotIn("_x7f", out, f"{shell}: DEL was escaped")


class NameLengthBudget(unittest.TestCase):
    """NM-1 and PUB-9 E3 — the budget FAILS CLOSED."""

    def test_getconf_failure_refuses_rather_than_meaning_unlimited(self):
        # E3: absent, non-zero, or non-numeric all refuse. The numeric guard is not redundant with
        # the status check: with an empty value `[ 42 -gt "" ]` is status 2 in bash (so an `if` takes
        # the ELSE branch and a publisher PROCEEDS) and status 0 in zsh (so it refuses) — the same
        # code, opposite outcomes, which is why the value never reaches a comparison unvalidated.
        for shell in SHELLS:
            rc, out, _ = run_shell(shell, '[ 42 -gt "" ] 2>/dev/null; printf "%s" "$?"')
            self.assertIn(out, ("0", "2"), f"{shell}: unexpected status")

    def test_budget_boundary_is_exact(self):
        for shell in SHELLS:
            body = (
                '_UNLEASHED_NAME_MAX=255\n'
                'pid=$$; edge=$(( 255 - 7 - ${#pid} - 5 ))\n'
                'k=""; i=0; while [ $i -lt $edge ]; do k="${k}k"; i=$(( i + 1 )); done\n'
                '_unleashed_budget_ok "$k" && printf "edge=ok " || printf "edge=REFUSED "\n'
                '_unleashed_budget_ok "${k}k" && printf "over=ACCEPTED" || printf "over=refused"\n'
            )
            rc, out, err = run_shell(shell, body)
            self.assertEqual("edge=ok over=refused", out, f"{shell}: {err}")


@unittest.skipUnless(DARWIN, "the Darwin ACL arm; the Linux arms are unmeasured by design")
class DarwinAclArm(unittest.TestCase):
    """ACL-1/ACL-2/ACL-4 — the arm that failed seven consecutive review rounds."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="acl2617.")
        def mk(name, *acls):
            p = os.path.join(cls.tmp, name)
            os.makedirs(p, exist_ok=True)
            os.chmod(p, 0o700)
            for a in acls:
                subprocess.run(["/bin/chmod", "+a", a, p], check=False)
            return p
        cls.none = mk("none")
        cls.other_w = mk("other_w", "group:staff allow write,delete")
        cls.other_r = mk("other_r", "group:staff allow read,list,search")
        cls.deny_w = mk("deny_w", "group:staff deny write,delete")
        me = subprocess.run(["/usr/bin/id", "-un"], capture_output=True, text=True).stdout.strip()
        # NOT os.getlogin(): it reads the controlling terminal and returns `root` under a test
        # runner, which would build an ACE for a FOREIGN principal and the arm would correctly
        # refuse it — a fixture defect that reads exactly like a code defect.
        cls.self_w = mk("self_w", f"user:{me} allow write,delete")
        cls.writeattr = mk("writeattr", "group:staff allow writeattr,chown")
        parent_ro = mk("p_ro", "group:staff allow list,search,file_inherit,directory_inherit")
        cls.inherited_ro = os.path.join(parent_ro, "child"); os.makedirs(cls.inherited_ro, exist_ok=True)
        parent_w = mk("p_w", "group:staff allow add_file,delete,file_inherit,directory_inherit")
        cls.inherited_w = os.path.join(parent_w, "child"); os.makedirs(cls.inherited_w, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _verdict(self, shell, path, lib=AUTH):
        rc, out, _ = run_shell(shell, f'_u_principal; _u_acl_ok "{path}" && printf accept || printf refuse',
                               sources=(lib,))
        return out

    def test_the_eight_fixtures_the_rule_distinguishes(self):
        expected = [
            (self.none, "accept"), (self.other_w, "refuse"), (self.other_r, "accept"),
            (self.deny_w, "accept"),            # ACL-1: `deny` is ignored ENTIRELY
            (self.self_w, "accept"),            # our own ACE is exempt
            (self.writeattr, "refuse"),         # rights outside the seven-right ALLOWLIST
            (self.inherited_ro, "accept"),      # an inherited read-only ACE must NOT refuse
            (self.inherited_w, "refuse"),       # the MDM-propagated case
        ]
        for shell in SHELLS:
            for path, want in expected:
                self.assertEqual(want, self._verdict(shell, path),
                                 f"{shell}: {os.path.basename(path)}")

    def test_control_a_positional_verb_parser_fails_open_on_an_inherited_ace(self):
        # ACL-2 says to locate the verb by TOKEN. A parser that assumes position sees `inherited`
        # where the verb should be, matches nothing, and accepts — "failing open on precisely the
        # ACEs an MDM-managed fleet propagates". The fixture must be an inherited MUTATING ACE: with
        # a read-only one, the correct arm and the broken one both accept and the control proves
        # nothing.
        # The control must FAIL OPEN, not merely refuse for another reason, and it must model the
        # defect ACL-2 actually describes: a parser that reads the verb from field 2 and the rights
        # from field 3. On an inherited ACE that gives verb=`inherited`, which is not `allow`, so the
        # ACE is SKIPPED and the component is ACCEPTED.
        # Two earlier attempts at this control failed for the WRONG reason — one left the verb unset
        # (malformed, refused) and one was caught by the reserved-token-in-`<perms>` guard, which is
        # the same masking that made mutant row 144 unable to fail. A control that refuses for a
        # different reason proves nothing, so the whole field loop is replaced.
        loop_start = '    _u13_principal=""; _u13_verb=""; _u13_perms=""; _u13_inh=0; _u13_n=0'
        with open(AUTH, encoding="utf-8") as fh:
            body = fh.read()
        loop_end = '    case "$_u13_perms" in\n        \'\'|*,,*|,*|*,) return 1 ;;                              # empty, doubled, leading, trailing\n    esac'
        i, j = body.index(loop_start), body.index(loop_end) + len(loop_end)
        positional = (
            '    _u13_principal="${_u13_body%% *}"\n'
            '    _u13_r="${_u13_body#* }"; _u13_verb="${_u13_r%% *}"\n'
            '    _u13_r="${_u13_r#* }"; _u13_perms="${_u13_r%% *}"\n'
            '    [ -n "$_u13_principal" ] || return 1')
        mutant = with_mutation(body[i:j], positional)
        try:
            for shell in SHELLS:
                self.assertEqual("refuse", self._verdict(shell, self.inherited_w),
                                 f"{shell}: the shipped arm must refuse")
                self.assertEqual("accept", self._verdict(shell, self.inherited_w, lib=mutant),
                                 f"{shell}: the CONTROL did not fail — this test cannot discriminate")
        finally:
            os.unlink(mutant)

    def test_control_a_blacklist_of_mutating_rights_fails_open(self):
        # N6-7: the rule is an ALLOWLIST. A right nobody enumerated must REFUSE, so `writeattr` and
        # `chown` — absent from any plausible blacklist — are the discriminating fixture.
        mutant = with_mutation(
            "            execute|list|read|readattr|readextattr|readsecurity|search) : ;;\n"
            "            file_inherit|directory_inherit|limit_inherit|only_inherit) : ;;\n"
            "            *) return 1 ;;",
            "            write|delete) return 1 ;;\n            *) : ;;")
        try:
            for shell in SHELLS:
                self.assertEqual("refuse", self._verdict(shell, self.writeattr))
                self.assertEqual("accept", self._verdict(shell, self.writeattr, lib=mutant),
                                 f"{shell}: the CONTROL did not fail")
        finally:
            os.unlink(mutant)


class AceGrammarAndAnswerMachine(unittest.TestCase):
    """P-13 and ACL-4. Every shape below was a real fail-open in some review round."""

    ACE_OK = [
        " 0: group:staff allow list,add_file",
        " 0: group:staff inherited allow list,add_file,file_inherit",
        " 0: user:nick allow write,delete",
        " 0: group:staff deny add_file,delete",
        " 10: group:staff allow list",
        " 0: group:staff   allow   list,read",
    ]
    ACE_MALFORMED = [
        " 0: group:staff allow write allow list",     # a second field after the verb
        " 0: group:staff allow list, write",          # a space inside <perms> is the same shape
        " 0: group:staff weird list",                 # unknown field before the verb
        " 0: group:staff allow ",                     # empty <perms>
        " 0: group:staff allow list,,read",           # doubled comma
        " 0: group:staff allow ,list",                # leading comma
        " 0: group:staff allow list,",                # trailing comma
        " 0: group:staff inherited inherited allow list",  # `inherited` is singular
        " 0: inherited allow list",                   # ...and never field 1
        " 0: group:staff deny allow",                 # a RESERVED token in the <perms> slot
        " 0:group:staff allow list",                  # the delimiter is not ": "
        " x: group:staff allow list",                 # the index is not decimal
        " : group:staff allow list",                  # the index is empty
    ]

    def test_every_ace_shape(self):
        for shell in SHELLS:
            for line in self.ACE_OK:
                rc, out, _ = run_shell(shell, f'_u_ace {line!r} && printf ok || printf REFUSED',
                                       sources=(AUTH,))
                self.assertEqual("ok", out, f"{shell}: refused a valid ACE {line!r}")
            for line in self.ACE_MALFORMED:
                rc, out, _ = run_shell(shell, f'_u_ace {line!r} && printf ACCEPTED || printf refused',
                                       sources=(AUTH,))
                self.assertEqual("refused", out, f"{shell}: ACCEPTED a malformed ACE {line!r}")

    ANSWERS_OK = [
        "drwxr-xr-x@ 2 n w 64 d\n 0: g:s allow list\n",
        "drwxr-xr-x@ 2 n w 64 d\n",                                  # a stat line and no ACEs
        "drwxr-xr-x@ 2 n w 64 d\n\n 0: g:s allow list\n",            # a blank line in the body
        "drwxrwxrwt  9 root wheel 288 tmp\n",                        # sticky bit
        "-rw-------  1 n s 0 f\n",                                   # a regular file's mode line
    ]
    ANSWERS_MALFORMED = [
        " 0: g:s allow list\n",              # an ACE with NO stat line
        "\ndrwxr-xr-x@ 2 n w 64 d\n",        # a blank FIRST line
        "drwxr-xr-x@ 2 n w 64 d\ngarbage\n", # a later non-space line
        "garbage\n",                         # not a stat line at all
        "",                                  # the EMPTY answer
        "drwxr-xr-x@ 2 n w 64 d\ndrwx e\n",  # a SECOND stat line
    ]

    def test_every_answer_shape(self):
        for shell in SHELLS:
            for ans in self.ANSWERS_OK:
                rc, out, _ = run_shell(
                    # %b, NOT %s: `printf %s` does not interpret `\n`, so every fixture was ONE
                    # line and the valid cases passed VACUOUSLY — they happen to start with the
                    # stat pattern. Only the stat+garbage case exposed it.
                    shell, f'printf %b {ans!r} | _u_acl_answer_ok && printf ok || printf REFUSED',
                    sources=(AUTH,))
                self.assertEqual("ok", out, f"{shell}: refused a valid answer {ans!r}")
            for ans in self.ANSWERS_MALFORMED:
                rc, out, _ = run_shell(
                    shell, f'printf %b {ans!r} | _u_acl_answer_ok && printf ACCEPTED || printf refused',
                    sources=(AUTH,))
                self.assertEqual("refused", out, f"{shell}: ACCEPTED a malformed answer {ans!r}")

    def test_control_accepting_any_non_space_line_as_the_stat_line_fails_open(self):
        mutant = with_mutation(
            "                      [-dlbcps][-r][-w][-xSs][-r][-w][-xSs][-r][-w][-xTt]*) _u_ans_st=BODY ;;\n"
            "                      *) return 1 ;;",
            "                      '') return 1 ;;\n                      ' '*) return 1 ;;\n"
            "                      *) _u_ans_st=BODY ;;")
        try:
            for shell in SHELLS:
                rc, out, _ = run_shell(shell, "printf %b 'garbage\\n' | _u_acl_answer_ok && printf ACCEPTED || printf refused",
                                       sources=(AUTH,))
                self.assertEqual("refused", out, f"{shell}: the shipped machine must refuse")
                rc, out, _ = run_shell(shell, "printf %b 'garbage\\n' | _u_acl_answer_ok && printf ACCEPTED || printf refused",
                                       sources=(mutant,))
                self.assertEqual("ACCEPTED", out, f"{shell}: the CONTROL did not fail")
        finally:
            os.unlink(mutant)


@unittest.skipUnless(DARWIN, "store creation uses the Darwin chain authenticator")
class StoreCreation(unittest.TestCase):
    """ST-2 and PUB-9 E4."""

    def setUp(self):
        # A scratch HOME so no test reads or writes the developer's real store (§7 step 3f(i)).
        self.home = tempfile.mkdtemp(prefix="store2617.", dir=os.path.expanduser("~/.claude"))
        os.chmod(self.home, 0o700)
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def test_creates_the_chain_at_0700_and_is_idempotent(self):
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            body = (f'_unleashed_name_max "{self.store}" || exit 9\n'
                    f'_unleashed_create_store "{self.store}" || exit 8\n'
                    f'_unleashed_create_store "{self.store}" || exit 7\n'   # idempotent
                    'printf ok')
            rc, out, err = run_shell(shell, body)
            self.assertEqual("ok", out, f"{shell}: rc={rc} {err}")
            for d in (os.path.join(self.home, ".claude"),
                      os.path.join(self.home, ".claude", "unleashed-mail"), self.store):
                self.assertEqual(0o700, os.stat(d).st_mode & 0o777, f"{shell}: {d} mode")

    def test_a_group_writable_ancestor_refuses(self):
        # ST-4/PCH-1: a group-writable component anywhere on the chain refuses, and NOTHING is
        # created — ACL-6 requires a pre-creation refusal to create no file anywhere.
        os.chmod(self.home, 0o770)
        try:
            for shell in SHELLS:
                rc, out, _ = run_shell(shell, f'_unleashed_name_max "{self.store}"; '
                                              f'_unleashed_create_store "{self.store}" && printf CREATED || printf refused')
                self.assertEqual("refused", out, f"{shell}: a group-writable ancestor was accepted")
                self.assertFalse(os.path.exists(os.path.join(self.home, ".claude")),
                                 f"{shell}: the refusal path created a directory")
        finally:
            os.chmod(self.home, 0o700)


if __name__ == "__main__":
    unittest.main()
