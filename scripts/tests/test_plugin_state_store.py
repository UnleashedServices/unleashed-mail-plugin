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
READER = os.path.join(LIB, "plugin-state-reader.sh")
PUB = os.path.join(LIB, "plugin-state-publisher.sh")
SHELLS = ("/bin/bash", "/bin/zsh")
DARWIN = os.uname().sysname == "Darwin"


def run_shell(shell, body, env=None, sources=(AUTH, STORE, READER, PUB)):
    """Run `body` with the shipped libraries sourced. Returns (rc, stdout, stderr)."""
    src = "".join(f'. "{s}"\n' for s in sources) + body
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([shell, "-c", src], capture_output=True, text=True, env=e)
    return p.returncode, p.stdout, p.stderr



def scratch_home(prefix):
    """A fresh scratch HOME for one test, under a chain that AUTHENTICATES.

    The fixture must sit under `~/.claude` rather than `/tmp`: on Darwin `/tmp` is a symlink to a
    1777 directory, so any store rooted there is refused by PCH-1's world-writable clause and every
    chain-walk assertion would fail for the wrong reason. `~/.claude` may not exist yet on a clean
    CI runner or a new developer machine — `tempfile.mkdtemp(dir=...)` then raises FileNotFoundError
    before a single assertion runs (gemini, PR #67) — so it is created here, at 0700, which is what
    the chain walk requires of a euid-owned ancestor anyway.
    """
    claude_dir = os.path.expanduser("~/.claude")
    os.makedirs(claude_dir, mode=0o700, exist_ok=True)
    home = tempfile.mkdtemp(prefix=prefix, dir=claude_dir)
    os.chmod(home, 0o700)
    return home

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
                # FAIL LOUDLY, and PROVE the ACE landed: with `check=False` a failed `chmod +a` left the
                # fixture unarmed and every assertion on it vacuous (external audit of PR #67, finding 1).
                subprocess.run(["/bin/chmod", "+a", a, p], check=True)
                shown = subprocess.run(["/bin/ls", "-lde", p], capture_output=True, text=True, check=True).stdout
                who, verb = a.split(" ")[0], a.split(" ")[1]          # `group:staff deny …` / `user:x allow …`
                assert f"{who} {verb} " in shown, f"ACE not installed on {p}: {shown!r}"
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
        # `deny_w` carries a `deny delete` ACE, so a plain rmtree cannot unlink it and, with
        # ignore_errors, said nothing: measured, EVERY run left one `acl2617.*/deny_w` behind in
        # $TMPDIR (77 of them on one machine). Strip every ACL top-down and restore 0700 first,
        # then remove LOUDLY — a leftover is a harness defect, not something to hide.
        subprocess.run(["/bin/chmod", "-N", cls.tmp], check=False, capture_output=True)
        for root, dirs, files in os.walk(cls.tmp):
            for name in dirs + files:
                p = os.path.join(root, name)
                subprocess.run(["/bin/chmod", "-N", p], check=False, capture_output=True)
                try:
                    os.chmod(p, 0o700)
                except OSError:
                    pass
        shutil.rmtree(cls.tmp)

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
        self.home = scratch_home("store2617.")
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


@unittest.skipUnless(DARWIN, "the reader walks chains through the Darwin ACL arm")
class ReaderOrderedRules(unittest.TestCase):
    """RD-3..RD-9 — rules −1 through 4, IN ORDER.

    Numbered from −1, not 0: RD-2 prohibits a "rules 0-4" enumeration because it silently drops the
    store-authentication rule, and a reader that skips it examines entries inside a store it never
    checked.
    """

    def setUp(self):
        self.home = scratch_home("rd2617.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.target = os.path.join(self.home, "target")
        os.makedirs(self.target); os.chmod(self.target, 0o700)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _resolve(self, shell, setup=""):
        body = (f'_unleashed_name_max "{self.store}" >/dev/null\n'
                f'_unleashed_create_store "{self.store}" || exit 9\n'
                f'{setup}\n'
                f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"')
        rc, out, err = run_shell(shell, body)
        self.assertNotEqual(9, rc, f"{shell}: the store could not be created: {err}")
        return out

    #: `key` writes a well-formed entry: the target's encoded name, its single line, mode 0600.
    ENTRY = ('_unleashed_key "{t}"; printf "%s\\n" "{t}" > "{s}/base.$_UNLEASHED_KEY"; '
             'chmod 600 "{s}/base.$_UNLEASHED_KEY"')

    def test_rule_4_empty_store_and_absent_store_both_yield_none(self):
        for shell in SHELLS:
            self.assertEqual("0 unresolved none", self._resolve(shell), f"{shell}: empty store")
            self.assertEqual("0 unresolved none",
                             self._resolve(shell, f'rm -rf "{self.home}/.claude"'),
                             f"{shell}: absent store")

    def test_rule_3_exactly_one_entry_resolves_silently(self):
        for shell in SHELLS:
            setup = self.ENTRY.format(t=self.target, s=self.store)
            self.assertEqual("1 pointer none", self._resolve(shell, setup), f"{shell}")

    def test_rule_2_two_authenticating_entries_conflict(self):
        for shell in SHELLS:
            t2 = os.path.join(self.home, "t2")
            setup = (f'mkdir -p "{t2}"; chmod 700 "{t2}"\n'
                     + self.ENTRY.format(t=self.target, s=self.store) + "\n"
                     + self.ENTRY.format(t=t2, s=self.store))
            self.assertEqual("0 unresolved conflict", self._resolve(shell, setup), f"{shell}")

    def test_rule_1_one_failing_entry_refuses_the_whole_store(self):
        # Fires HOWEVER MANY entries authenticate: a good entry beside a failing one must NOT win.
        for shell in SHELLS:
            setup = (self.ENTRY.format(t=self.target, s=self.store) + "\n"
                     + f'chmod 644 "{self.store}"/base.*')
            self.assertEqual("0 unresolved stale", self._resolve(shell, setup), f"{shell}: 0644 entry")

    def test_rule_1_a_dangling_symlink_is_a_failing_entry_not_a_vanished_one(self):
        # Rule 0's test is EXACTLY `[ ! -L ] && [ ! -e ]`. A one-part `[ -e ]` is FALSE for a dangling
        # symlink, so it would SKIP a hostile entry that must be refused — which is why the one-part
        # form is prohibited anywhere in the reader.
        for shell in SHELLS:
            setup = f'ln -s /nonexistent "{self.store}/base.dangling"'
            self.assertEqual("0 unresolved stale", self._resolve(shell, setup), f"{shell}")

    def test_rule_minus_1_a_non_conforming_store_refuses_before_any_entry(self):
        for shell in SHELLS:
            setup = (self.ENTRY.format(t=self.target, s=self.store) + "\n"
                     + f'chmod 755 "{self.store}"')
            self.assertEqual("0 unresolved stale", self._resolve(shell, setup),
                             f"{shell}: a 0755 store must refuse even holding a valid entry")

    def test_control_skipping_rule_minus_1_would_resolve_from_a_bad_store(self):
        # The positive control for the rule whose omission RD-2 warns about: with rule −1 removed, a
        # store at 0755 holding one valid entry RESOLVES, which is the whole point of numbering the
        # rules from −1.
        mutant = with_mutation(
            '    if ! _unleashed_store_ok "$_rs_store"; then',
            '    if false; then', path=READER)
        try:
            for shell in SHELLS:
                setup = (self.ENTRY.format(t=self.target, s=self.store) + "\n"
                         + f'chmod 755 "{self.store}"')
                self.assertEqual("0 unresolved stale", self._resolve(shell, setup))
                body = (f'_unleashed_name_max "{self.store}" >/dev/null\n'
                        f'_unleashed_create_store "{self.store}" || exit 9\n{setup}\n'
                        f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                        'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"')
                rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, mutant))
                self.assertEqual("1 pointer none", out,
                                 f"{shell}: the CONTROL did not fail — rule −1 is not load-bearing here")
        finally:
            os.unlink(mutant)
@unittest.skipUnless(DARWIN, "the publisher walks chains through the Darwin ACL arm")
class PublisherAndEndToEnd(unittest.TestCase):
    """PUB-4, PUB-7, PUB-9, ST-7, TMP-1, P-4 — and the capability itself.

    The end-to-end test is the ticket: a shell that never receives the plugin-data variable
    discovers the base anyway, from what a publisher recorded.
    """

    def setUp(self):
        self.home = scratch_home("pb2617.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.base = os.path.join(self.home, "base")
        os.makedirs(self.base); os.chmod(self.base, 0o700)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _publish(self, shell, value=None, extra=""):
        v = value if value is not None else self.base
        body = (f'{extra}\n_unleashed_publish "{self.store}" "{v}" 2>/dev/null\n'
                'printf "%s" "$_UNLEASHED_POINTER_STATE"')
        rc, out, err = run_shell(shell, body)
        return out

    def test_first_publish_creates_one_entry_at_0600_named_for_its_content(self):
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            self.assertEqual("created", self._publish(shell), f"{shell}")
            entries = [f for f in os.listdir(self.store) if f.startswith("base.")]
            self.assertEqual(1, len(entries), f"{shell}: PUB-4 allows AT MOST ONE durable file")
            path = os.path.join(self.store, entries[0])
            self.assertEqual(0o600, os.stat(path).st_mode & 0o777, f"{shell}")
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(self.base + "\n", fh.read(), f"{shell}")
            self.assertEqual([], [f for f in os.listdir(self.store) if f.startswith(".pub.")],
                             f"{shell}: a transient was left behind")

    def test_second_publish_writes_nothing_and_reports_current(self):
        # PUB-4 and row 1: on the no-write path a publish creates NO durable file. Proved by mtime,
        # because "reports current" is satisfiable by a publisher that rewrites an identical file.
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            self._publish(shell)
            entry = os.path.join(self.store, [f for f in os.listdir(self.store)
                                              if f.startswith("base.")][0])
            before = os.stat(entry).st_mtime_ns
            self.assertEqual("current", self._publish(shell), f"{shell}")
            self.assertEqual(before, os.stat(entry).st_mtime_ns, f"{shell}: the entry was rewritten")

    def test_a_second_base_value_yields_conflict(self):
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            other = os.path.join(self.home, "other")
            os.makedirs(other, exist_ok=True); os.chmod(other, 0o700)
            self._publish(shell)
            self.assertEqual("conflict", self._publish(shell, other), f"{shell}")

    def test_e2_an_unpublishable_value_writes_nothing_at_all(self):
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            self.assertEqual("failed", self._publish(shell, "relative/path"), f"{shell}")
            self.assertFalse(os.path.exists(self.store),
                             f"{shell}: E2 must compose and open NOTHING under the store")

    def test_a_newline_bearing_value_is_refused_and_an_ordinary_one_is_not(self):
        # Both halves matter. The first version of this check spelled the newline
        # `*"$(printf '\n')"*`, and command substitution STRIPS trailing newlines — so the pattern
        # was the EMPTY STRING, matched everything, and refused every ordinary path. A test for the
        # refusal alone would have passed against that defect.
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            self.assertEqual("created", self._publish(shell), f"{shell}: an ordinary base must publish")
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            body = ('v="$(printf %b "/tmp/a\\nb")"\n'
                    f'_unleashed_publish "{self.store}" "$v" 2>/dev/null\n'
                    'printf "%s" "$_UNLEASHED_POINTER_STATE"')
            rc, out, _ = run_shell(shell, body)
            self.assertEqual("failed", out, f"{shell}: a newline-bearing base must refuse")

    def test_end_to_end_a_reader_with_no_variable_resolves_the_publishers_base(self):
        """THE CAPABILITY. This is what COREDEV-2617 is for."""
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                    'unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE\n'
                    'unset _UNLEASHED_BASE_DIAGNOSED\n'
                    f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                    'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_BASE_RESOLVED"')
            rc, out, err = run_shell(shell, body)
            self.assertEqual(f"1 pointer {self.base}", out, f"{shell}: {err}")
@unittest.skipUnless(DARWIN, "drives the Darwin ACL arm through step 3f's seams")
class MutantRowsThroughTheProductionResolver(unittest.TestCase):
    """§7 step 3f — the seams, and the rows they make runnable.

    N6-6 requires a mutant's discriminating case to name the STORE-LEVEL outcome the ordered reader
    rules produce, never merely "refused". A malformed ACE line cannot be produced with `chmod +a`
    and `/bin/ls -lde`, so before the enumerator-output seam existed these obligations could be
    unit-tested as strings but never driven through the production resolver. They can now.

    The seam is a FUNCTION the harness redefines, not an environment variable: ACL-7 requires a
    component's verdict to be a property of the MACHINE, and an `if [ -n "$SOMEVAR" ]` inside the
    predicate would be exactly the environment dependence it forbids.
    """

    def setUp(self):
        self.home = scratch_home("seam2617.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.base = os.path.join(self.home, "base")
        os.makedirs(self.base); os.chmod(self.base, 0o700)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _resolve_with_answer(self, shell, answer):
        """Publish a valid entry, then make every component's ACL answer `answer`, then READ."""
        override = ('_u_acl_enumerate() { printf %b ' + repr(answer).replace("'", '"') + '; }\n')
        body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                'unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE\n'
                'unset _UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL _U_PRINCIPAL_PROBED\n'
                + override +
                f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"')
        rc, out, err = run_shell(shell, body)
        return out

    #: A healthy answer for a euid-owned component with no ACEs.
    HEALTHY = "drwx------@ 2 nick staff 64 Aug 14 d\n"

    def test_the_seam_itself_does_not_change_a_healthy_resolution(self):
        # The control for the seam: with a WELL-FORMED substituted answer the store still resolves.
        # Without this, every row below would "pass" against a seam that broke resolution outright.
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            self.assertEqual("1 pointer none", self._resolve_with_answer(shell, self.HEALTHY),
                             f"{shell}: the seam broke a healthy resolution")

    def test_malformed_answers_yield_the_store_level_refusal(self):
        # Each of these is a mutant row's fixture, and each now produces N6-6's store-level tuple
        # through the PRODUCTION resolver rather than being asserted against the parser in isolation.
        cases = {
            "a duplicate verb":            "drwx------@ 2 n s 64 d\n 0: group:staff allow write list\n",
            "an empty rights field":       "drwx------@ 2 n s 64 d\n 0: group:staff allow \n",
            "a reserved token as rights":  "drwx------@ 2 n s 64 d\n 0: group:staff deny allow\n",
            "a duplicated `inherited`":    "drwx------@ 2 n s 64 d\n 0: group:staff inherited inherited allow list\n",
            "a non-decimal index":         "drwx------@ 2 n s 64 d\n x: group:staff allow list\n",
            "no delimiter after the index":"drwx------@ 2 n s 64 d\n 0:group:staff allow list\n",
            "a later non-space line":      "drwx------@ 2 n s 64 d\n 0: group:staff allow list\ngarbage\n",
            "no stat line at all":         " 0: group:staff allow list\n",
            "an empty answer":             "",
        }
        for shell in SHELLS:
            for name, answer in cases.items():
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                self.assertEqual("0 unresolved stale", self._resolve_with_answer(shell, answer),
                                 f"{shell}: {name} must poison the answer and refuse the store")

    def test_a_failed_identity_probe_refuses(self):
        # The identity-probe seam. P-3a: a FAILED probe refuses publisher and reader alike, with no
        # carve-out — that carve-out is for a platform where no enumerator EXISTS, and a probe that
        # failed may be failing because the machine is hostile.
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                    'unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE\n'
                    'unset _UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL _U_PRINCIPAL_PROBED\n'
                    '_u_identity_probe() { return 1; }\n'
                    f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                    'printf "%s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_POINTER_STATE"')
            rc, out, _ = run_shell(shell, body)
            self.assertEqual("0 stale", out, f"{shell}: a failed identity probe must refuse")

    def test_a_failed_name_max_probe_refuses_the_publish(self):
        # The NAME_MAX-probe seam, and PUB-9 E3's fail-closed obligation, which had no mutant at all
        # until the seam existed. Both a FAILING probe and a NON-NUMERIC one must refuse: the numeric
        # guard is not redundant, because `[ 42 -gt "" ]` is status 2 in bash (whose `if` then takes
        # the ELSE branch and PROCEEDS) and status 0 in zsh.
        for probe, label in (("return 1", "a failing probe"), ("printf notanumber", "a non-numeric probe")):
            for shell in SHELLS:
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                body = (f'_u_name_max_probe() {{ {probe}; }}\n'
                        f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                        'printf "%s" "$_UNLEASHED_POINTER_STATE"')
                rc, out, _ = run_shell(shell, body)
                self.assertEqual("failed", out, f"{shell}: {label} must fail closed")
                self.assertFalse(os.path.exists(self.store),
                                 f"{shell}: {label} must create nothing")


@unittest.skipUnless(DARWIN, "the publish and read cells walk chains through the Darwin arm; on Linux every cell is `failed`/`stale` by design (CI, PR #67 pass 7 — the class shipped without this skip and the validate job went red)")
class SourcedUnderErrexit(unittest.TestCase):
    """The family sourced under `set -eu` reaches its next statement in every publish/read cell.

    Plan §4.3: "each file must also source cleanly under `set -euo pipefail` in both bash and zsh in
    every cell" — stated, and never executed on the PUBLISH path. Codex (PR #67 pass 7) found two bare
    status captures in the publisher that aborted a `set -e` sourcer before the E5/E6 classification;
    this is the sweep that would have caught them and that now guards the whole matrix. The positive
    control is row 159's mutant: with the capture made a bare call, the E6 cell aborts.
    """

    def setUp(self):
        self.home = scratch_home("eu.2617.")
        self.libdir = os.path.join(self.home, "lib")
        shutil.copytree(LIB, self.libdir)
        self.store = os.path.join(self.home, "h", ".claude", "unleashed-mail", "bases")
        for d in ("t", "t2"):
            os.makedirs(os.path.join(self.home, d))
            os.chmod(os.path.join(self.home, d), 0o700)
        os.makedirs(os.path.join(self.home, "h"))
        os.chmod(os.path.join(self.home, "h"), 0o700)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _fresh(self):
        shutil.rmtree(os.path.join(self.home, "h", ".claude"), ignore_errors=True)

    def _store(self, mode=0o700):
        os.makedirs(self.store, exist_ok=True)
        for d in (os.path.join(self.home, "h", ".claude"), os.path.dirname(self.store)):
            os.chmod(d, 0o700)
        os.chmod(self.store, mode)

    def _entry(self, target, mode=0o600):
        r = subprocess.run(["/bin/bash", "-c",
                            f'. "{AUTH}"; . "{STORE}"; _unleashed_key "{target}"; printf %s "$_UNLEASHED_KEY"'],
                           capture_output=True, text=True)
        path = os.path.join(self.store, "base." + r.stdout)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(target + "\n")
        os.chmod(path, mode)

    def _run(self, shell, env_line, prefix, lib):
        body = (f'set -eu; {env_line}; {prefix}; . "{self.libdir}/{lib}"; '
                'echo "END OK=${_UNLEASHED_BASE_OK:-unset} ST=${_UNLEASHED_POINTER_STATE:-unset}"')
        p = subprocess.run([shell, "-c", body], capture_output=True, text=True,
                           env={k: v for k, v in os.environ.items()
                                if not k.startswith("_UNLEASHED_") and k not in ("CLAUDE_PLUGIN_DATA",)})
        return p.returncode, p.stdout, p.stderr

    def _cells(self):
        h, t, t2 = os.path.join(self.home, "h"), os.path.join(self.home, "t"), os.path.join(self.home, "t2")
        set_env = f'export HOME="{h}" CLAUDE_PLUGIN_DATA="{t}"'
        unset_env = f'export HOME="{h}"; unset CLAUDE_PLUGIN_DATA'
        yield "set: created", (lambda: self._fresh()), set_env, ":", "paths.sh", "created"
        yield "set: current", (lambda: (self._fresh(), self._store(), self._entry(t))), set_env, ":", "paths.sh", "current"
        yield "set: conflict", (lambda: (self._fresh(), self._store(), self._entry(t2))), set_env, ":", "paths.sh", "conflict"
        yield "set: E4 store mode", (lambda: (self._fresh(), self._store(0o500))), set_env, ":", "paths.sh", "failed"
        yield "set: E6 fsize0", (lambda: (self._fresh(), self._store())), set_env, 'trap "" XFSZ; ulimit -f 0', "paths.sh", "failed"
        yield "set: E1 HOME empty", (lambda: self._fresh()), f'export HOME="" CLAUDE_PLUGIN_DATA="{t}"', ":", "paths.sh", "failed"
        yield "set: E0 disabled", (lambda: self._fresh()), set_env + " _UNLEASHED_PUBLISH_OK=0", ":", "paths.sh", "none"
        yield "unset: D' envelope", (lambda: self._fresh()), unset_env, ":", "paths.sh", "none"
        yield "unset: resolves", (lambda: (self._fresh(), self._store(), self._entry(t))), unset_env, ":", "paths.sh", "none"
        yield "unset: conflict", (lambda: (self._fresh(), self._store(), self._entry(t), self._entry(t2))), unset_env, ":", "paths.sh", "conflict"
        yield "unset: failing entry", (lambda: (self._fresh(), self._store(), self._entry(t, 0o644))), unset_env, ":", "paths.sh", "stale"
        yield "unset: rule -1 store", (lambda: (self._fresh(), self._store(0o755))), unset_env, ":", "paths.sh", "stale"
        for lib in ("marker.sh", "log.sh", "context.sh"):
            yield f"unset: {lib}", (lambda: self._fresh()), unset_env, ":", lib, "none"
            yield f"unset+entry: {lib}", (lambda: (self._fresh(), self._store(), self._entry(t))), unset_env, ":", lib, "none"
            yield f"set: {lib}", (lambda: self._fresh()), set_env, ":", lib, "created"

    def test_every_cell_reaches_its_next_statement_in_both_shells(self):
        for shell in SHELLS:
            for label, setup, env_line, prefix, lib, want_state in self._cells():
                with self.subTest(shell=shell, cell=label):
                    setup()
                    rc, out, err = self._run(shell, env_line, prefix, lib)
                    self.assertIn("END ", out, f"{label}: the sourcer did not reach its next statement "
                                               f"(rc={rc}, stderr={err!r})")
                    self.assertIn(f"ST={want_state}", out, f"{label}: {out!r} {err!r}")
                    if os.path.exists(self.store):
                        os.chmod(self.store, 0o700)

    def test_positive_control_a_bare_status_capture_aborts_the_e6_cell(self):
        """Row 159's mutant: the sourcer dies at the bare call, before the diagnostic (both shells)."""
        mutant = with_mutation(
            '            _unleashed_write_transient "$_UNLEASHED_TRANSIENT" "$_pb_value" && _pb_wrc=0 || _pb_wrc=$?\n',
            '            _unleashed_write_transient "$_UNLEASHED_TRANSIENT" "$_pb_value"; _pb_wrc=$?\n',
            path=PUB)
        try:
            shutil.copyfile(mutant, os.path.join(self.libdir, "plugin-state-publisher.sh"))
            h, t = os.path.join(self.home, "h"), os.path.join(self.home, "t")
            for shell in SHELLS:
                with self.subTest(shell=shell):
                    self._fresh(); self._store()
                    rc, out, err = self._run(shell, f'export HOME="{h}" CLAUDE_PLUGIN_DATA="{t}"',
                                             'trap "" XFSZ; ulimit -f 0', "paths.sh")
                    self.assertNotEqual(0, rc, f"{shell}: the CONTROL did not fail — the bare capture "
                                               f"survived errexit: {out!r} {err!r}")
                    self.assertNotIn("END ", out)
        finally:
            os.unlink(mutant)


@unittest.skipUnless(DARWIN, "walks chains through the Darwin arm; on Linux every cell is `failed`/`stale` by design")
class TwoProcessAcceptance(unittest.TestCase):
    """The Jira acceptance flows the external audit of PR #67 (finding 5) said were unproved:

    (a) the SAME real `marker_write` reached through a hook-shaped process (the variable set) and then
        through a fresh STANDALONE process (no variable, a different pid) lands in ONE file at ONE path;
    (b) a value published in the SET process is recovered identically by a fresh UNSET process, through
        `paths.sh` and through each family file's own fallback with `paths.sh` absent, in both shells.

    Every earlier test either published and read inside ONE shell, or exercised the resolver copies with
    a pre-built store; none crossed a process boundary through the writers' real entry points.
    """

    def setUp(self):
        self.home = scratch_home("twop.2617.")
        self.base = os.path.join(self.home, "plugin-data")
        os.makedirs(self.base); os.chmod(self.base, 0o700)
        os.makedirs(os.path.join(self.home, "h")); os.chmod(os.path.join(self.home, "h"), 0o700)
        self.absent = os.path.join(self.home, "lib-no-paths")
        shutil.copytree(LIB, self.absent); os.remove(os.path.join(self.absent, "paths.sh"))

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _proc(self, shell, libdir, lib, body, set_var):
        env = {k: v for k, v in os.environ.items() if not k.startswith("_UNLEASHED_") and k != "CLAUDE_PLUGIN_DATA"}
        env["HOME"] = os.path.join(self.home, "h")
        if set_var:
            env["CLAUDE_PLUGIN_DATA"] = self.base
        p = subprocess.run([shell, "-c", f'. "{libdir}/{lib}"; {body}'], capture_output=True, text=True, env=env)
        return p.returncode, p.stdout, p.stderr

    def test_hook_shaped_then_standalone_marker_write_land_in_one_file(self):
        for shell in SHELLS:
            for libdir, label in ((LIB, "paths.sh present"), (self.absent, "paths.sh absent")):
                with self.subTest(shell=shell, resolver=label):
                    shutil.rmtree(os.path.join(self.home, "h", ".claude"), ignore_errors=True)
                    shutil.rmtree(os.path.join(self.base, ".state"), ignore_errors=True)
                    # Process 1: hook-shaped — the variable is set; this publishes the base to the store.
                    rc, out, err = self._proc(shell, libdir, "marker.sh",
                                              'marker_write lint pass; printf "%s|%s" "$(marker_path lint)" "$_UNLEASHED_POINTER_STATE"', True)
                    p1_path, p1_state = out.split("|")
                    self.assertEqual("created", p1_state, f"{shell}/{label}: hook-shaped process did not publish: {err!r}")
                    # Process 2: standalone — no variable, a fresh pid; the SAME entry points.
                    rc, out, err = self._proc(shell, libdir, "marker.sh",
                                              'printf "%s|%s|%s" "$(marker_path lint)" "$(marker_status lint)" "$_UNLEASHED_BASE_SOURCE"; marker_write build fail', False)
                    p2_path, p2_status, p2_source = out.split("|")
                    self.assertEqual(p1_path, p2_path, f"{shell}/{label}: two processes composed different marker paths")
                    self.assertEqual("pass", p2_status, f"{shell}/{label}: the standalone process did not read the hook's marker: {err!r}")
                    self.assertEqual("pointer", p2_source)
                    state_dirs = [d for d in (os.path.join(self.base, ".state"),) if os.path.isdir(d)]
                    self.assertEqual(1, len(state_dirs), "exactly one .state directory, under the published base")
                    names = sorted(os.listdir(state_dirs[0]))
                    self.assertTrue(any(n.startswith("quality-marker-lint-") for n in names) and
                                    any(n.startswith("quality-marker-build-") for n in names),
                                    f"{shell}/{label}: both writers must land in the one directory: {names}")
                    self.assertFalse(os.path.exists(os.path.join(self.home, "h", ".claude", "unleashed-mail", ".state")),
                                     "no second store under HOME")

    def test_set_publisher_then_unset_reader_agree_through_every_resolver_copy(self):
        for shell in SHELLS:
            shutil.rmtree(os.path.join(self.home, "h", ".claude"), ignore_errors=True)
            rc, out, err = self._proc(shell, LIB, "paths.sh", 'printf "%s|%s" "$_UNLEASHED_BASE_RESOLVED" "$_UNLEASHED_POINTER_STATE"', True)
            resolved, state = out.split("|")
            self.assertEqual((self.base, "created"), (resolved, state), f"{shell}: {err!r}")
            for libdir, label in ((LIB, "paths.sh"), (self.absent, "fallback")):
                for lib in ("paths.sh", "marker.sh", "log.sh", "context.sh"):
                    if label == "fallback" and lib == "paths.sh":
                        continue
                    with self.subTest(shell=shell, resolver=label, lib=lib):
                        rc, out, err = self._proc(shell, libdir, lib, 'printf "%s|%s|%s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_BASE_RESOLVED"', False)
                        self.assertEqual(f"1|pointer|{self.base}", out, f"{shell}/{label}/{lib}: {err!r}")


if __name__ == "__main__":
    unittest.main()
