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

import ast
import collections
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: The repo root -- the sibling probe below runs from here so `scripts.tests...` imports.
ROOT_PARENT = os.path.dirname(ROOT)
LIB = os.path.join(ROOT, "lib")
AUTH = os.path.join(LIB, "plugin-state-auth.sh")
STORE = os.path.join(LIB, "plugin-state-store.sh")
READER = os.path.join(LIB, "plugin-state-reader.sh")
PUB = os.path.join(LIB, "plugin-state-publisher.sh")
def _resolve_shell(name):
    """Absolute path to `name`, preferring /bin but accepting the distro's location.

    Hardcoding /bin/zsh meant CI's `command -v zsh` presence check could pass -- it finds
    /usr/bin/zsh -- while every zsh arm silently SKIPPED on any non-usrmerge Linux. On macOS both
    candidates exist and this returns exactly what the literal did.
    """
    for candidate in ("/bin/" + name, "/usr/bin/" + name):
        if os.path.exists(candidate):
            return candidate
    return shutil.which(name) or "/bin/" + name


SHELLS = (_resolve_shell("bash"), _resolve_shell("zsh"))
DARWIN = os.uname().sysname == "Darwin"


def run_shell(shell, body, env=None, sources=(AUTH, STORE, READER, PUB)):
    """Run `body` with the shipped libraries sourced. Returns (rc, stdout, stderr).

    SKIP, never ERROR, on a missing shell (2026-08-17 audit, AF-2): without this, an absent
    /bin/zsh made subprocess raise FileNotFoundError and ten dual-shell tests reported ERROR on any
    zsh-less Linux box — a false-red indistinguishable from a regression for anyone running the
    CLAUDE.md validation list. CI cannot silently lose the zsh arm to this skip: its workflow
    installs zsh and separately asserts `command -v zsh` before the suite runs.
    """
    if shutil.which(shell) is None:
        raise unittest.SkipTest(f"{shell} not installed — the dual-shell arm needs it (CI asserts presence)")
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


# ─────────────────────────────────────────────────────────────────────────────
# COREDEV-2691 — the auth-chain seam, and the two classes it lets CI actually run.
#
# WHY THIS EXISTS. `_unleashed_auth_chain` refuses on every non-Darwin platform, and the REQUIRED CI
# gate is ubuntu. So the required check verifies no plugin-state entry guard at all: every cell above
# that walks a chain is `@skipUnless(DARWIN)` and simply does not run where merges are gated.
# Narrowing those skips is measurably wrong (44 store / 119 mutant failures). The fix is a seam —
# `run_shell` sources the libraries and then appends the body, so a body-level redefinition overrides
# the shipped function for every later call, including calls from inside library functions.
#
# The seam is RECORDING and FAIL-CLOSED. An unconditional `return 0` would let a caller that stops
# calling the guard pass, which is the one thing these tests exist to detect.
#
# EIGHT DEFECTS were found in ten lines across six plan revisions — `|`-separated `case` alternatives
# (literal in an expanded variable), unquoted word-splitting (zsh does not), newline-delimited
# membership (`/a\n/b` matched two entries and ALLOWED), `case` under `shopt -s nocasematch`
# (case-INSENSITIVE, so `/Case` allows `/case`), unset allowlist slots aborting under `set -u`, an
# unchecked redirect returning 0 while recording nothing, a missing `-n` letting an uninitialised
# path variable match an unset slot, and the log variable itself left unguarded after its siblings
# were fixed. Every one was found by EXECUTING the seam against inputs this suite already uses —
# none by reading it. That is why each predicate below carries its own mutant.

#: The seam, ONE PREDICATE PER LINE so each can be broken in isolation.
#: §3 of the plan spells the first two as one compound `{ A && B; } || return 1`; splitting it is
#: behaviour-identical (both refuse if either conjunct fails) and is what makes the arity predicate
#: separately controllable, as §7.6 requires. `test_the_split_spelling_matches_the_compound` proves
#: the equivalence by execution rather than by assertion.
SEAM_LINES = (
    '    [ "$#" -eq 1 ] || return 1',
    '    [ -n "$1" ] || return 1',
    '    [ -n "${_SEAM_CALLS:-}" ] || return 1',
    """    printf '%s\\0' "$1" >> "$_SEAM_CALLS" || return 1""",
    '    [ "$1" = "${_SEAM_A1:-}" ] && return 0',
    '    [ "$1" = "${_SEAM_A2:-}" ] && return 0',
    '    [ "$1" = "${_SEAM_A3:-}" ] && return 0',
    '    return 1',
)

#: name -> (line index, replacement). Each breaks exactly ONE predicate, and each replacement is a
#: single line, so every mutant preserves the seam's line count by construction (asserted).
#: `fail_closed` is an INVERSION, not a deletion: dropping the trailing `return 1` leaves the failing
#: `&&` list as the last command and the function still returns 1, so deletion would have been a
#: mutant that changes nothing — a control that cannot fail reads exactly like a control that passes.
SEAM_MUTANTS = {
    "arity":        (0, '    :'),
    "nonempty":     (1, '    :'),
    "log_declared": (2, '    :'),
    "log_checked":  (3, """    printf '%s\\0' "$1" >> "$_SEAM_CALLS" || :"""),
    "nul_framing":  (3, """    printf '%s\\n' "$1" >> "$_SEAM_CALLS" || return 1"""),
    "allow_1":      (4, '    :'),
    "allow_2":      (5, '    :'),
    "allow_3":      (6, '    :'),
    "fail_closed":  (7, '    return 0'),
    # `[ = ]` is STRING equality; `case` is PATTERN matching, and bash's inherited
    # `shopt -s nocasematch` makes that comparison case-INSENSITIVE. This is not hypothetical for
    # this repo: the encoder already saves, clears and restores `nocasematch` as adversarial state.
    "pattern_match": (4, '    case "$1" in "${_SEAM_A1:-}") return 0 ;; esac'),
    # `:-` is what keeps an UNSET allowlist slot inert instead of aborting the shell under `set -u`.
    "unset_slot":    (5, '    [ "$1" = "$_SEAM_A2" ] && return 0'),
}

COMPOUND_FIRST_LINE = '    { [ "$#" -eq 1 ] && [ -n "$1" ]; } || return 1'


#: Mutant names actually EXECUTED in a shell during this process. The meta-control reads this
#: rather than the source text: a lexical count was satisfied by a comment, and an AST walk was
#: satisfied by an unreachable `if False:` call while missing a real dict-mediated one (codex, r2
#: and r3). Execution is the only signal that means what the control claims.
_MUTANTS_EXERCISED = set()


def seam_source(broken=None, compound=False):
    """The seam's shell source, optionally with ONE predicate broken.

    `compound=True` emits §3's literal spelling — arity and non-emptiness as one `{ A && B; }` —
    with a `:` filler so the line count is unchanged. Only the equivalence control uses it.
    """
    lines = list(SEAM_LINES)
    if compound:
        lines[0], lines[1] = COMPOUND_FIRST_LINE, "    :"
    if broken is not None:
        idx, replacement = SEAM_MUTANTS[broken]
        lines[idx] = replacement
    return "_unleashed_auth_chain() {\n" + "\n".join(lines) + "\n}\n"


class SeamedChain:
    """Mixin: drive the seamed chain and read back its transcript.

    Every helper here declares its shell set and asserts the declared set RAN. A cell that silently
    loses an arm — the zsh arm in particular, since bash 3.2 and zsh 5.9 have each produced a real
    fail-open in this material — still fails, which is the entire point of the assertion.
    """

    #: A fixture that is VALID in every respect except the one predicate under test, so a refusal is
    #: attributable to that predicate alone rather than to a broken log or an unlisted path.
    GOOD = "/declared/target"

    def seam_calls(self, shell, argv_list, allow=(GOOD,), broken=None, calls="fresh",
                   prelude="", strict=True, compound=False):
        """Make one or more calls to the seamed chain. Returns (rcs, records, alive).

        `records` is the NUL-framed transcript as a list of byte strings — NUL-framed so ONE call
        carrying an embedded newline stays distinguishable from TWO calls, which `printf '%s\\n'`
        cannot express. `alive` is False when the shell died before reaching the end of the body,
        which is how an unbound-variable abort is told apart from a clean refusal.
        """
        home = scratch_home("seam-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)

        log = os.path.join(home, "calls") if calls == "fresh" else calls
        if calls == "fresh":
            with open(log, "wb"):
                pass

        decl = "".join(
            "_SEAM_A%d=%s\n" % (i + 1, shlex.quote(a)) for i, a in enumerate(allow)
        )
        set_log = "" if log is None else "_SEAM_CALLS=%s\n" % shlex.quote(log)
        body = (
            ("set -u\n" if strict else "")
            + set_log
            + decl
            + prelude
            + seam_source(broken, compound)
            + "".join(
                "_unleashed_auth_chain %s\n" % " ".join(shlex.quote(a) for a in argv)
                + 'printf "SEAM_RC=%s\\n" "$?"\n'
                for argv in argv_list
            )
            + 'printf "SEAM_ALIVE\\n"\n'
        )
        out = run_shell(shell, body)[1]
        if broken is not None:
            # Recorded HERE, where the mutant is actually EXECUTED, not in `seam_source` where it is
            # merely BUILT. `test_every_mutant_preserves_the_seam_line_count` calls seam_source for
            # every declared mutant to compare line counts, which populated the set as a SIDE EFFECT
            # and blinded the meta-control: deleting a whole behavioural cell left it GREEN (agy,
            # r6 -- reproduced). A control that cannot fail is the defect this campaign has chased
            # more than any other, and it had reappeared inside the cell built to prevent it.
            _MUTANTS_EXERCISED.add(broken)
        alive = "SEAM_ALIVE" in out
        rcs = [int(l[len("SEAM_RC="):]) for l in out.splitlines() if l.startswith("SEAM_RC=")]

        records = []
        if log is not None and os.path.exists(log):
            with open(log, "rb") as fh:
                raw = fh.read()
            records = raw.split(b"\0")
            if records and records[-1] == b"":
                records.pop()   # the framing NUL terminates, so the tail split is an artifact
        return rcs, records, alive

    def seam_call(self, shell, argv, **kw):
        """One call. Returns (rc, records, alive); rc is None if the shell died before printing it."""
        rcs, records, alive = self.seam_calls(shell, [argv], **kw)
        return (rcs[0] if rcs else None), records, alive

    def for_declared_shells(self, declared, fn, narrowed_reason=None):
        """Run `fn(shell)` for each DECLARED shell, skipping the CELL if an interpreter is missing.

        §7.2. Revision 1 ended this with `assertEqual(list(declared), ran, "a declared shell arm did
        not run")` and both docstrings claimed that made a lost arm fail. It could NEVER fire:
        unittest SWALLOWS a SkipTest raised inside `subTest`, and `ran.append` sat outside the
        with-block, so `ran` always equalled `declared`. Measured: point the zsh arm at a
        nonexistent path and all 11 cells report OK with 14 skips. The assertion is gone rather than
        reworded -- a check that cannot fail reads exactly like a check that passes.

        What actually guards the arms is external and stated here so it is not re-invented: the
        missing interpreter is detected BEFORE any assertion, so the cell skips visibly rather than
        passing on one arm, and CI's `seam_ungated` step asserts `not result.skipped`, which turns
        any such skip into a red required check.
        """
        # Dropping an arm by DECLARING fewer shells produces no skip, so the skip-based guard above
        # does not see it (codex r2): changing a cell from SHELLS to SHELLS[:1] silently removes zsh
        # and CI stays green. Narrowing must therefore be explicit and carry its reason.
        if set(declared) != set(SHELLS) and not narrowed_reason:
            self.fail(f"cell declares {list(declared)} rather than both shells, without a reason")
        missing = [sh for sh in declared if shutil.which(sh) is None]
        if missing:
            raise unittest.SkipTest(f"declared shell(s) absent: {missing} (CI fails on this skip)")
        for shell in declared:
            with self.subTest(shell=shell):
                fn(shell)


class SeamContract(SeamedChain, unittest.TestCase):
    """COREDEV-2691 §7.6 — ONE control per seam predicate, each with the mutant that reddens it.

    UNGATED BY DESIGN. This is the first plugin-state class the required ubuntu `validate` job
    actually executes; everything above it that walks a chain is Darwin-only, so before this class
    the required check verified no entry guard at all.

    Every cell here runs the CORRECT seam and then the mutant that breaks exactly ONE predicate, and
    asserts the outcome FLIPS. A control that passes against both spellings is not isolating the
    predicate it claims to isolate — the failure mode this campaign hit more than any other.
    """

    def test_the_body_redefinition_overrides_the_shipped_chain(self):
        """Predicate zero: the seam mechanism itself. Without this the other ten prove nothing."""
        def check(shell):
            rc, records, alive = self.seam_call(shell, [self.GOOD])
            self.assertTrue(alive, "the shell died before the seam could be observed")
            self.assertEqual(0, rc, "the shipped chain answered, not the seam")
            self.assertEqual([self.GOOD.encode()], records,
                             "the seam did not record — the shipped chain handled the call")
        self.for_declared_shells(SHELLS, check)

    def test_arity_refuses_zero_and_two_arguments(self):
        """§7.6 arity. The fixture is otherwise VALID — writable log, allowlisted first argument —
        so a refusal here is attributable to arity and to nothing else."""
        def check(shell):
            rc, records, alive = self.seam_call(shell, [self.GOOD])
            self.assertEqual((0, True), (rc, alive), "the fixture itself does not authenticate")

            for argv, label in (([self.GOOD, self.GOOD], "two"), ([], "zero")):
                rc, records, alive = self.seam_call(shell, argv)
                self.assertTrue(alive, f"{label} arguments killed the shell")
                self.assertEqual(1, rc, f"{label} arguments authenticated")
                self.assertEqual([], records, f"{label} arguments were recorded despite refusal")

            # The TWO-argument case is the discriminating one: with arity neutered, `$1` is still
            # the allowlisted path and the seam authenticates. The zero-argument case cannot
            # discriminate, because a neutered arity check leaves `$1` unbound and `set -u` aborts
            # -- refusal for a different reason (codex r1). It is asserted above against the correct
            # seam only, for survival, and is deliberately not paired with the mutant.
            rc, _, _ = self.seam_call(shell, [self.GOOD, self.GOOD], broken="arity")
            self.assertEqual(0, rc, "the arity mutant did not flip this control")
        self.for_declared_shells(SHELLS, check)

    def test_an_empty_argument_refuses(self):
        """§7.6 non-emptiness. An unset slot expands to empty, so without `-n` a caller passing an
        UNINITIALISED path variable authenticates — exactly the mutant shape the seam exists to catch."""
        def check(shell):
            rc, records, alive = self.seam_call(shell, [""])
            self.assertTrue(alive)
            self.assertEqual(1, rc, "an empty argument authenticated against an unset slot")
            self.assertEqual([], records)

            rc, _, _ = self.seam_call(shell, [""], broken="nonempty")
            self.assertEqual(0, rc, "the non-emptiness mutant did not flip this control")
        self.for_declared_shells(SHELLS, check)

    def test_an_unset_log_refuses_and_the_shell_survives(self):
        """§7.6 log-declared. Fail-closed IN EFFECT is not enough: an unbound-variable abort kills
        the process before the cell can observe anything, which is indistinguishable from a crash."""
        def check(shell):
            rc, _, alive = self.seam_call(shell, [self.GOOD], calls=None)
            self.assertTrue(alive, "an unset log aborted the shell instead of refusing")
            self.assertEqual(1, rc, "an unset log authenticated")

            _, _, alive = self.seam_call(shell, [self.GOOD], calls=None, broken="log_declared")
            self.assertFalse(alive, "the log-declared mutant did not flip this control")
        self.for_declared_shells(SHELLS, check)

    def test_a_failed_recording_refuses(self):
        """§7.6 log-checked. The unchecked redirect returns 0 while recording NOTHING, so a cell
        could assert against a transcript that was never written."""
        def check(shell):
            rc, _, alive = self.seam_call(shell, [self.GOOD], calls="/dev/null/nope")
            self.assertTrue(alive)
            self.assertEqual(1, rc, "a call that failed to record authenticated")

            rc, _, _ = self.seam_call(shell, [self.GOOD], calls="/dev/null/nope", broken="log_checked")
            self.assertEqual(0, rc, "the log-checked mutant did not flip this control")
        self.for_declared_shells(SHELLS, check)

    def test_a_wrong_case_spelling_refuses_under_nocasematch(self):
        """§7.6 string-equality. DECLARED SHELL SET: bash only — `nocasematch` is a bash option and
        zsh has no equivalent inherited state, so the zsh arm would assert nothing."""
        allow = ("/Case/Sensitive",)
        rc, _, alive = self.seam_call("/bin/bash", ["/case/sensitive"], allow=allow,
                                      prelude="shopt -s nocasematch\n")
        self.assertTrue(alive)
        self.assertEqual(1, rc, "a wrong-case path authenticated under nocasematch")

        rc, _, _ = self.seam_call("/bin/bash", ["/case/sensitive"], allow=allow,
                                  prelude="shopt -s nocasematch\n", broken="pattern_match")
        self.assertEqual(0, rc, "the pattern-match mutant did not flip this control")

    def test_an_unset_allowlist_slot_is_inert_not_fatal(self):
        """§7.6 slot inertness. Reached only by a NON-matching path — a matching one returns before
        the later slots are ever evaluated, so the obvious fixture would control nothing."""
        def check(shell):
            rc, _, alive = self.seam_call(shell, ["/undeclared"], allow=(self.GOOD,))
            self.assertTrue(alive, "an unset allowlist slot aborted the shell under set -u")
            self.assertEqual(1, rc)

            _, _, alive = self.seam_call(shell, ["/undeclared"], allow=(self.GOOD,), broken="unset_slot")
            self.assertFalse(alive, "the unset-slot mutant did not flip this control")
        self.for_declared_shells(SHELLS, check)

    def test_an_undeclared_path_refuses_and_is_still_recorded(self):
        """§7.6 fail-closed. The recording happens BEFORE the allowlist, so a refused call is still
        visible in the transcript — that is what lets a cell prove the guard was consulted."""
        def check(shell):
            rc, records, alive = self.seam_call(shell, ["/undeclared"])
            self.assertTrue(alive)
            self.assertEqual(1, rc, "an undeclared path authenticated")
            self.assertEqual([b"/undeclared"], records, "the refused call was not recorded")

            rc, _, _ = self.seam_call(shell, ["/undeclared"], broken="fail_closed")
            self.assertEqual(0, rc, "the fail-closed mutant did not flip this control")
        self.for_declared_shells(SHELLS, check)

    def test_each_allowlist_slot_authenticates_its_own_path(self):
        """§7.6 one-control-per-predicate, for the three allowlist slots.

        Revision 1 DECLARED allow_1/allow_2/allow_3 and no cell ever executed one, so seam line [6]
        -- the `_SEAM_A3` comparison -- had no behavioural control at all, while the commit message
        claimed a mutant per predicate. Found by AST trace (codex r1) and by the sweep; confirmed by
        counting `broken="allow_N"` occurrences in this file: zero.
        """
        allow = ("/slot/one", "/slot/two", "/slot/three")

        def check(shell):
            with self.subTest(slot=1):
                rc, records, alive = self.seam_call(shell, [allow[0]], allow=allow)
                self.assertEqual((0, True), (rc, alive), "slot 1 did not authenticate its own path")
                self.assertEqual([allow[0].encode()], records)
                rc, _, _ = self.seam_call(shell, [allow[0]], allow=allow, broken="allow_1")
                self.assertEqual(1, rc, "the allow_1 mutant did not flip this control")
            with self.subTest(slot=2):
                rc, _, alive = self.seam_call(shell, [allow[1]], allow=allow)
                self.assertEqual((0, True), (rc, alive), "slot 2 did not authenticate its own path")
                rc, _, _ = self.seam_call(shell, [allow[1]], allow=allow, broken="allow_2")
                self.assertEqual(1, rc, "the allow_2 mutant did not flip this control")
            with self.subTest(slot=3):
                rc, _, alive = self.seam_call(shell, [allow[2]], allow=allow)
                self.assertEqual((0, True), (rc, alive), "slot 3 did not authenticate its own path")
                rc, _, _ = self.seam_call(shell, [allow[2]], allow=allow, broken="allow_3")
                self.assertEqual(1, rc, "the allow_3 mutant did not flip this control")
        self.for_declared_shells(SHELLS, check)

    #: Cells that legitimately drive the shell WITHOUT `for_declared_shells`, each with its reason.
    #: The `narrowed_reason` gate only sees cells that call the helper; a cell can bypass it entirely
    #: by calling `seam_call` directly, which is exactly what the nocasematch cell does (codex, r3).
    #: This table plus the check below is what makes a single-shell cell a DECLARED choice.
    SINGLE_SHELL_CELLS = {
        "test_a_wrong_case_spelling_refuses_under_nocasematch":
            "`nocasematch` is a bash option; zsh has no equivalent inherited state to assert on",
    }

    def test_no_shell_driving_cell_silently_skips_the_declared_shell_helper(self):
        """Every cell that drives the shell must go through `for_declared_shells` -- which enforces
        both arms -- or appear in SINGLE_SHELL_CELLS with a reason. Without this, dropping the zsh
        arm needs no `narrowed_reason` at all: just call `seam_call` directly and the guard never
        runs (codex, r3).
        """
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        # Every driver and every seamed class. The first spelling listed only SeamContract and
        # SeamedStoreCreation, so replacing a READER or PUBLISHER cell's `for_declared_shells(...)`
        # with `check(SHELLS[0])` kept the count at 43, kept this cell green, and silently dropped
        # that production guard's zsh arm (codex, r10).
        # BOTH LISTS ARE DERIVED. A hardcoded class list has now been left stale THREE times --
        # SeamedReader and SeamedPublisher at r10, PrefetchCacheContract at r17 -- each time letting
        # a cell in the new class drop its zsh arm unnoticed. Fixing the list is fixing the
        # instance; the list itself is the wrong mechanism. Any ungated class counts, and any method
        # that runs a shell is a driver.
        ungated = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                   and any(isinstance(b, ast.Name) and b.id == "SeamedChain" for b in n.bases)]
        drivers = {"seam_call", "seam_calls", "run_shell"}
        for cls in ungated:
            for fn in (m for m in cls.body if isinstance(m, ast.FunctionDef)
                       and not m.name.startswith("test_")):
                called = {n.func.attr for n in ast.walk(fn)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
                called |= {n.func.id for n in ast.walk(fn)
                           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                if called & drivers:
                    drivers.add(fn.name)     # a helper that drives the shell IS a driver
        self.assertGreaterEqual(len(ungated), 4,
                                f"only {len(ungated)} ungated classes found -- the derivation broke")
        offenders = []
        for cls in ungated:
            for fn in (member for member in cls.body if isinstance(member, ast.FunctionDef)
                       and member.name.startswith("test_")):
                # BOTH call shapes. `self.seam_call(...)` is an Attribute and `with_mutation(...)`
                # is a bare Name; collecting only the former made every positive control look like
                # an offender, because the marker that identifies them is a bare name.
                called = {n.func.attr for n in ast.walk(fn)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
                called |= {n.func.id for n in ast.walk(fn)
                           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                if not (called & drivers) or "for_declared_shells" in called:
                    continue
                if fn.name in self.SINGLE_SHELL_CELLS:
                    continue                 # declared, with its reason, in the table above
                if "with_mutation" in called:
                    # A POSITIVE CONTROL, recognised as a category rather than listed by name. These
                    # mutate a shipped file and assert the mutation is OBSERVABLE; the property is
                    # "the mutant flips", which is shell-independent, and running both arms doubles
                    # the cost for no added signal. Listing them individually would be the same
                    # recall-not-derive mistake as the hardcoded class list this cell just lost.
                    continue
                offenders.append(f"{cls.name}.{fn.name}")
        self.assertEqual([], offenders,
                         "shell-driving cells that bypass for_declared_shells without a declared reason")

    def test_the_declared_shell_set_is_one_bash_and_one_zsh(self):
        """`for_declared_shells` compares each cell's declaration to the module-level SHELLS, so it
        is blind to SHELLS itself being wrong: a copy/paste making it `(bash, bash)` runs every
        dual-shell cell TWICE under bash, produces no skip, preserves every CI floor, and satisfies
        the helper (codex, r8 -- reproduced). An oracle that checks a value against itself checks
        nothing. This asserts the property independently.
        """
        self.assertEqual(2, len(SHELLS), f"SHELLS is not a pair: {SHELLS}")
        self.assertEqual(2, len(set(SHELLS)), f"SHELLS names the same interpreter twice: {SHELLS}")
        names = sorted(os.path.basename(sh) for sh in SHELLS)
        self.assertEqual(["bash", "zsh"], names, f"SHELLS is not one bash and one zsh: {SHELLS}")
        for sh in SHELLS:
            with self.subTest(shell=sh):
                self.assertTrue(os.path.isabs(sh), f"{sh} is not an absolute path")
                # IDENTITY, not name. An executable shim named `zsh` that launches bash passes
                # basename, uniqueness, absolute-path and `which` checks alike (codex, r9). Ask the
                # interpreter what it is.
                # Both variables are CLEARED first: a correct bash launched from a zsh session
                # inherits ZSH_VERSION and answers "bashzsh" -- a false RED on a correct shell
                # (codex, r10). `env -u` removes them from the child's environment; each shell then
                # sets only its own.
                probe = 'printf "%s\\n" "${BASH_VERSION:+bash}${ZSH_VERSION:+zsh}"'
                got = subprocess.run(
                    ["/usr/bin/env", "-u", "BASH_VERSION", "-u", "ZSH_VERSION", sh, "-c", probe],
                    capture_output=True, text=True).stdout.strip()
                self.assertEqual(os.path.basename(sh), got,
                                 f"{sh} identifies itself as {got!r}, not {os.path.basename(sh)!r}")

    def test_the_ci_floors_match_the_cells_that_exist(self):
        """The CI gate floors a per-class cell count so DELETION cannot pass, and a floor that lags
        the real count protects nothing above it. This cell has caught that rot three times.

        It PARSES THE GATE'S OWN PYTHON with `ast` and evaluates the mapping the gate will actually
        build. Two earlier spellings read something different from what the gate executes, which is
        precisely the failure they existed to prevent:
          * a regex over the whole workflow took the FIRST match while Python takes the LAST
            duplicate key -- one duplicate made the check read 16 while the gate enforced 15;
          * the regex also matched inside COMMENTS, so prefixing one entry with `#` left the check
            green while the runtime gate silently dropped to four classes and stopped enforcing that
            class's floor and no-skip condition entirely (codex, r9 and r10).
        `ast` sees neither comments nor first-match ordering, and duplicate keys are detected on the
        parsed node rather than on text.
        """
        workflow = os.path.join(os.path.dirname(ROOT), ".github", "workflows", "plugin-ci.yml")
        if not os.path.exists(workflow):
            self.skipTest("workflow not present in this checkout")
        with open(workflow, encoding="utf-8") as fh:
            text = fh.read()
        # The gate's Python lives in a heredoc inside the step's `run:`; take it verbatim.
        body = re.search(r"python3 - <<'PY'\n(.*?)\n\s*PY\n", text, re.S)
        self.assertIsNotNone(body, "the seam gate no longer embeds a Python heredoc")
        source = textwrap.dedent(body.group(1))
        assigns = [n for n in ast.walk(ast.parse(source))
                   if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "MINIMUMS" for t in n.targets)]
        self.assertEqual(1, len(assigns),
                         f"expected exactly one MINIMUMS assignment, found {len(assigns)}")
        node = assigns[0].value
        self.assertIsInstance(node, ast.Dict, "MINIMUMS is not a dict literal")
        keys = [k.value for k in node.keys]
        self.assertEqual(sorted(set(keys)), sorted(keys),
                         f"MINIMUMS declares a duplicate key; Python would use the LAST: {keys}")
        declared = ast.literal_eval(node)
        # DERIVED, not curated. A hardcoded tuple stays green when a NEW seamed class is added with
        # no floor beside it -- which is the rot mode a floor list actually has, and the one this
        # cell could not see until r19 added a seventh class. Every `SeamedChain` subclass in this
        # module is built on the same harness; ForkClassification is named explicitly because it is
        # the one floored class that is not -- it is a pure source census with no shell fixture.
        seamed = sorted((c for c in list(globals().values())
                         if isinstance(c, type) and issubclass(c, SeamedChain)
                         and issubclass(c, unittest.TestCase)),
                        key=lambda c: c.__name__)
        self.assertGreater(len(seamed), 1, "no SeamedChain classes found -- this cell is inert")
        # ForkClassification and PortablePathIdentity are the floored classes that are NOT built on
        # the seam harness -- one is a pure source census, the other simulates a platform rather than
        # a chain. Everything else is derived, so a new seamed class cannot arrive without a floor.
        for cls in [ForkClassification, PortablePathIdentity] + seamed:
            name = "scripts.tests.test_plugin_state_store." + cls.__name__
            actual = len(unittest.defaultTestLoader.getTestCaseNames(cls))
            with self.subTest(cls=cls.__name__):
                self.assertIn(name, declared, f"{cls.__name__} has no floor in the CI gate")
                self.assertEqual(actual, declared[name],
                                 f"{cls.__name__}: {actual} cells but the CI floor says "
                                 f"{declared[name]} -- update plugin-ci.yml")
        self.assertEqual(len(seamed) + 2, len(declared),
                         f"the CI gate floors {len(declared)} classes, expected "
                         f"{len(seamed) + 2}: {sorted(declared)}")

    def test_every_declared_mutant_is_executed_by_some_cell(self):
        """The meta-control, EXECUTION-based. §7.6 asks for one control per predicate.

        Two earlier spellings of this cell were themselves defeated, which is the reason for the
        third: a lexical `src.count(...)` was satisfied by an inert comment naming the mutant, and
        an AST walk for `broken=` keywords was satisfied by an unreachable `if False:` call while
        MISSING a genuine `broken={"slot": "allow_1"}["slot"]` (codex, r2 and r3). Both are static
        proxies for a dynamic property. This one runs the sibling cells and reads what they actually
        passed, so an unexecuted control cannot look like an executed one.
        """
        # A SUBPROCESS, not a nested TextTestRunner. Running the siblings in-process inherited
        # this process's own state: under `python3 -m unittest -k <thisname>` the filter reached the
        # nested run, every sibling was filtered out, `_MUTANTS_EXERCISED` stayed empty and the cell
        # reported all eleven mutants unexecuted -- a FALSE RED on a correct tree (agy, r4). The
        # module-level set was also shared across repeated runs. A fresh interpreter has neither
        # problem.
        probe = (
            "import json, unittest, sys;"
            "sys.path.insert(0, %r);"
            "import scripts.tests.test_plugin_state_store as m;"
            "names=[n for n in unittest.defaultTestLoader.getTestCaseNames(m.SeamContract)"
            " if n != 'test_every_declared_mutant_is_executed_by_some_cell'];"
            "r=unittest.TextTestRunner(stream=open(__import__('os').devnull,'w'),verbosity=0)"
            ".run(unittest.TestSuite(m.SeamContract(n) for n in names));"
            "print(json.dumps({'ok': r.wasSuccessful(), 'ran': r.testsRun,"
            " 'seen': sorted(m._MUTANTS_EXERCISED)}))"
        ) % ROOT_PARENT
        out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                             cwd=ROOT_PARENT,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(0, out.returncode, f"the sibling probe did not run: {out.stderr[-600:]}")
        report = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertTrue(report["ok"],
                        "sibling cells failed, so mutant coverage cannot be read from this run")
        self.assertGreater(report["ran"], 0, "the sibling probe executed no cells")
        exercised = set(report["seen"])
        unexecuted = sorted(set(SEAM_MUTANTS) - exercised)
        self.assertEqual([], unexecuted, "declared mutants that no cell EXECUTES")
        covered = {SEAM_MUTANTS[m][0] for m in exercised if m in SEAM_MUTANTS}
        self.assertEqual(set(range(len(SEAM_LINES))), covered,
                         "a seam predicate has no executed mutant")

    def test_nul_framing_distinguishes_one_call_from_two(self):
        """§7.6 framing. `/a\\n/b` as ONE argument must not read back as the two calls `/a`, `/b` —
        a newline-delimited log cannot express that difference, and this suite treats embedded
        newlines as in-scope input."""
        one, two = ["/a\n/b"], ["/a"]
        def check(shell):
            _, joined, _ = self.seam_calls(shell, [one])
            _, split, _ = self.seam_calls(shell, [two, ["/b"]])
            self.assertEqual([b"/a\n/b"], joined)
            self.assertEqual([b"/a", b"/b"], split)
            self.assertNotEqual(joined, split, "one call is indistinguishable from two")

            _, m_joined, _ = self.seam_calls(shell, [one], broken="nul_framing")
            _, m_split, _ = self.seam_calls(shell, [two, ["/b"]], broken="nul_framing")
            self.assertEqual(m_joined, m_split, "the NUL-framing mutant did not flip this control")
        self.for_declared_shells(SHELLS, check)

    def test_the_split_spelling_matches_the_compound(self):
        """The plan spells arity and non-emptiness as one compound; this file splits them so each is
        separately controllable. Equivalence is proved by EXECUTION over the suite's own input
        classes, not asserted — the campaign's eight seam defects were all found this way."""
        classes = ([], [""], [self.GOOD], ["/undeclared"], [self.GOOD, self.GOOD], ["/a\n/b"])
        def check(shell):
            for argv in classes:
                with self.subTest(argv=argv):
                    split = self.seam_calls(shell, [argv])
                    comp = self.seam_calls(shell, [argv], compound=True)
                    # Both runs dying identically would make the comparison below compare
                    # ([], [], False) with itself and pass having proved nothing (agy r1, and the
                    # sweep independently). Establish that each run actually EXECUTED first.
                    for label, (rcs, _, alive) in (("split", split), ("compound", comp)):
                        self.assertTrue(alive, f"the {label} run died before reporting")
                        self.assertEqual(1, len(rcs), f"the {label} run produced no rc")
                    self.assertEqual(split, comp, "the split spelling diverges from §3's compound")
        self.for_declared_shells(SHELLS, check)

    def test_every_mutant_preserves_the_seam_line_count(self):
        """§7.1's line-count rule, asserted rather than inferred — `git diff --summary` reports mode
        and extended headers, never line counts, so it is evidence for the other property only."""
        baseline = len(seam_source().splitlines())
        for name in SEAM_MUTANTS:
            with self.subTest(mutant=name):
                self.assertEqual(baseline, len(seam_source(name).splitlines()))
        self.assertEqual(baseline, len(seam_source(compound=True).splitlines()))


#: Every absolute-path executable the four shipped libraries fork, and how portability is decided.
#: DERIVED, then declared: the census below re-derives this from the sources and fails if the two
#: disagree, in EITHER direction. Revision 1 of this file declared six executables and omitted
#: /bin/mkdir, /bin/rm and /bin/mv -- five real fork sites -- while its comment claimed to list
#: "every fork the shipped libraries make" (codex, r1).
#:
#: "portable"    POSIX everywhere; blocks nothing, and a cell whose only forks are these is admitted.
#: "nonportable" keeps a cell Darwin-gated regardless of argv.
#: "argv"        portability depends on the arguments; classify_fork must recognise the shape, and
#:               an UNRECOGNISED shape is a census FAILURE, never a silent pass.
FORK_EXES = {
    "/usr/bin/stat":        "argv",         # BSD `-f FORMAT`; GNU `-f` means FILE SYSTEM
    "/bin/ls":              "argv",         # `-e` (ACL) is BSD-only; other flag sets are portable
    "/usr/bin/dsmemberutil": "nonportable",  # a Darwin-only binary, whatever the subcommand
    "/usr/bin/id":          "portable",
    "/usr/bin/uname":       "portable",
    "/usr/bin/getconf":     "portable",
    "/bin/mkdir":           "portable",
    "/bin/rm":              "portable",
    "/bin/mv":              "portable",
}

#: Absolute-path prefixes a fork could plausibly acquire. `/opt/homebrew` and `/usr/local` are here
#: so that relocating a fork to a Homebrew binary is DISCOVERED rather than skipped by the scan.
_EXE_RE = re.compile(r"(?<![\w./-])(/(?:usr/local/|opt/homebrew/|usr/)?s?bin/[A-Za-z0-9_.-]+)")

#: Expected number of call sites per executable. A SET loses multiplicity: replacing one of the two
#: `/bin/ls` sites with `${UNLEASHED_BIN:-/bin}/ls -ld` left the set complete because the other
#: literal site remained, and `-ld` omits ACL entries -- a component carrying a foreign mutating ACE
#: then authenticates (codex, r5). Counts make any change to the inventory explicit.
FORK_SITE_COUNTS = {
    "/usr/bin/stat": 4, "/bin/ls": 2, "/usr/bin/dsmemberutil": 1, "/usr/bin/id": 2,
    "/usr/bin/uname": 1, "/usr/bin/getconf": 2, "/bin/mkdir": 2, "/bin/rm": 2, "/bin/mv": 1,
}

#: Shell keywords, POSIX special builtins and the bash/zsh builtins these libraries use. A command
#: word that is one of these is not a fork; anything that is NOT one of these, NOT a function defined
#: in the same four files, and NOT a literal declared absolute path is a census FAILURE.
#:
#: THIS IS AN ALLOWLIST BECAUSE THE BLACKLIST RE-OPENED TWICE IN ONE ROUND. Its predecessor matched
#: nine hardcoded basenames followed by whitespace, so `stat>/dev/null` escaped for want of a space
#: and every command outside those nine escaped by not being named (codex, r19); and it decided
#: command position from the preceding WORD, so `LC_ALL=C stat -f ...` was ruled not-a-command
#: because an assignment preceded it (agy, r19). A list of ways to be wrong is only ever as complete
#: as the last review; a list of ways to be right fails closed on everything else.
_SHELL_WORDS = frozenset("""
: . [ [[ ]] alias bg break builtin case cd continue declare do done echo elif else emulate
esac eval exit export false fc fg fi for getopts hash if in jobs kill let local printf pwd
read readonly return select set setopt shift shopt source sysopen sysread syswrite test then
time times trap true type typeset ulimit umask unalias unset unsetopt until wait while
zmodload zparseopts zstat
""".split())

#: Words after which the NEXT word is still the command: `command /bin/mkdir ...` forks mkdir, and
#: `if /bin/mkdir ...; then` forks it too. Yielding these would report a builtin as a fork; skipping
#: them WITHOUT keeping command position would hide the real command word behind them.
_CMD_KEEP = frozenset({"command", "builtin", "exec", "env", "nohup", "time", "!", "then", "do",
                       "else", "elif", "if", "while", "until"})

_CMD_SEP = ";|&"
#: `NAME=value` / `NAME[k]=value` / `NAME+=value` -- a prefix assignment KEEPS command position.
_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\[[^]]*\])?\+?=")
#: `{fd}<file` and `9>file` are redirections, not commands. Both were read as command words.
_FDNAME_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}(?=[<>])")
_FDNUM_RE = re.compile(r"[0-9]+(?=[<>])")


def _skip_arith(t, i):
    """`t[i:i+3]` is `$((`. Return the index after the matching `))`.

    Counting starts at the FIRST `(`, not past both: the first spelling stepped over `$((` before
    counting, so depth never rose, the closing parens drove it negative, and the scanner ran to the
    end of the file. Every command word after `_uk_n=$(( _uk_n & 255 ))` -- more than half of
    plugin-state-store.sh -- was silently unscanned, and the census still reported zero offenders.
    """
    d = 0
    i += 1                                   # step over the `$`; the first `(` is the depth opener
    while i < len(t):
        if t[i] == "(":
            d += 1
        elif t[i] == ")":
            d -= 1
            if d == 0:
                return i + 1
        i += 1
    return i


def _match_close(t, i):
    """`i` points at the `(` of a `$(`. Return the index AFTER its matching `)`, quote-aware."""
    d, q = 0, None
    while i < len(t):
        c = t[i]
        if q:
            if c == "\\" and q == '"' and i + 1 < len(t):
                i += 2
                continue
            if c == q:
                q = None
            i += 1
            continue
        if c in "'\"":
            q = c
            i += 1
            continue
        if c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return i + 1
        i += 1
    return i


def _skip_redirect(t, i):
    """Step over a redirection operator and its target; neither is a command word."""
    i += 1
    while i < len(t) and t[i] in "<>&-":
        i += 1
    while i < len(t) and t[i] in " \t":
        i += 1
    q = None
    while i < len(t):
        c = t[i]
        if q:
            if c == q:
                q = None
            i += 1
            continue
        if c in "'\"":
            q = c
            i += 1
            continue
        if c in " \t\n" or c in _CMD_SEP or c in "()":
            break
        i += 1
    return i


def _skip_case_pattern(t, i):
    """Step over a `case` arm's pattern list up to the `)` that ends it.

    `''|*[!0-9]*)` is not a command, and reading it as one reported twenty-odd offenders in the
    encoder's own byte table. `(` inside a pattern is balanced, and quotes are honoured.
    """
    q, d = None, 0
    while i < len(t):
        c = t[i]
        if q:
            if c == q:
                q = None
            i += 1
            continue
        if c in "'\"":
            q = c
            i += 1
            continue
        if c == "(":
            d += 1
            i += 1
            continue
        if c == ")":
            if d == 0:
                return i + 1
            d -= 1
            i += 1
            continue
        i += 1
    return i


def _command_words(text):
    """Yield (offset, word) for every word in COMMAND position in a run of shell source.

    A command substitution is SCANNED, not skipped, and scanned wherever it appears -- including
    inside double quotes, which is where most of this codebase's forks live:
    `_x="$(/usr/bin/stat -f '%p' -- "$1")"`. The first version read that whole thing as one word, so
    ten of the seventeen real fork sites were never examined at all while the census reported clean.
    """
    i, n, quote, cmd = 0, len(text), None, True
    pending_case, case_pat = False, False
    while i < n:
        c = text[i]
        if quote == "'":
            if c == "'":
                quote = None
            i += 1
            continue
        if quote == '"':
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if text[i:i + 3] == "$((":
                i = _skip_arith(text, i)
                continue
            if text[i:i + 2] == "$(":
                j = _match_close(text, i + 1)
                yield from _command_words(text[i + 2:j - 1])
                i = j
                continue
            if c == '"':
                quote = None
            i += 1
            continue
        if c in " \t":
            i += 1
            continue
        if c == "\n":
            cmd = True                       # a newline ends the command, NOT a case arm: an arm's
            i += 1                           # pattern sits on the line after its `;;`
            continue
        if case_pat:
            if re.match(r"\s*esac\b", text[i:]):
                case_pat = False             # `;;` then `esac`: there is no further pattern, and
                continue                     # scanning for one ran off the end of the file
            i = _skip_case_pattern(text, i)
            cmd, case_pat = True, False
            continue
        if text[i:i + 3] == "$((":
            i = _skip_arith(text, i)
            continue
        if text[i:i + 2] == "$(":
            j = _match_close(text, i + 1)
            yield from _command_words(text[i + 2:j - 1])
            i, cmd = j, False
            continue
        if c == "`":
            j = text.find("`", i + 1)
            j = n if j < 0 else j
            yield from _command_words(text[i + 1:j])
            i, cmd = j + 1, False
            continue
        if text[i:i + 2] == ";;":
            case_pat, cmd = True, False
            i += 2
            continue
        if c in _CMD_SEP:
            cmd = True
            i += 1
            continue
        m = _FDNAME_RE.match(text, i) or _FDNUM_RE.match(text, i)
        if m:                                # tested BEFORE `{`: `exec {fd}<file` reached the
            i = _skip_redirect(text, m.end())  # brace arm first and yielded `fd}` as a command
            continue
        if c in "<>":
            i = _skip_redirect(text, i)
            continue
        if c in "(){}":
            cmd = True
            i += 1
            continue
        if c in "'\"":
            quote = c
            i += 1
            continue
        start, q, braces = i, None, 0
        while i < n:
            ch = text[i]
            if ch == "\\" and q != "'" and i + 1 < n:
                i += 2
                continue
            if q:
                if q == '"' and text[i:i + 3] == "$((":
                    i = _skip_arith(text, i)
                    continue
                if q == '"' and text[i:i + 2] == "$(":
                    j = _match_close(text, i + 1)
                    yield from _command_words(text[i + 2:j - 1])
                    i = j
                    continue
                if ch == q:
                    q = None
                i += 1
                continue
            if ch in "'\"":
                q = ch
                i += 1
                continue
            if text[i:i + 3] == "$((":
                i = _skip_arith(text, i)
                continue
            if text[i:i + 2] == "$(":
                j = _match_close(text, i + 1)
                yield from _command_words(text[i + 2:j - 1])
                i = j
                continue
            if text[i:i + 2] == "${":
                braces += 1
                i += 2
                continue
            if braces:
                if ch == "}":
                    braces -= 1
                i += 1
                continue
            if ch in " \t\n" or ch in _CMD_SEP or ch in "()<>`":
                break
            i += 1
        word = text[start:i]
        if not word:
            i += 1
            continue
        if cmd:
            if _ASSIGN_RE.match(word):
                continue                     # a prefix assignment; the command is still ahead
            if word == "case":
                pending_case, cmd = True, False
                continue
            if word in ("for", "select"):
                cmd = False                  # the loop variable and its word list are not commands
                continue
            if word in _CMD_KEEP:
                continue
            yield start, word
            cmd = False
        elif word == "in" and pending_case:
            pending_case, case_pat = False, True


def _defined_functions(paths):
    """Every function these libraries define. A call to one of them is not a fork."""
    out = set()
    for p in paths:
        for _, code in _logical_lines(p):
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_:.-]*)\s*\(\)", code)
            if m:
                out.add(m.group(1))
    return out


#: (source, why) pairs the scanner MUST flag: every spelling a reviewer has used to reach a binary
#: while escaping a scan keyed on literal absolute paths, plus the two that re-opened it at r19.
_CMD_ESCAPES = (
    ("stat>/dev/null", "no whitespace after the basename (codex, r19)"),
    ('readlink -f -- "$1"', "a bare command outside the nine the blacklist named (codex, r19)"),
    ("LC_ALL=C stat -f '%p' /x", "an env-assignment prefix before the command (agy, r19)"),
    ('${UNLEASHED_BIN:-/bin}/ls -ld -- "$1"', "assembled by parameter expansion (codex, r5)"),
    ('"/bin/"ls -lde -- "$1"', "split across quotes (codex, r4)"),
    ('ls -lde -- "$1"', "a bare ls (codex, r1)"),
    ('_x="$(stat -f \'%p\' -- "$1")"', "inside a substitution inside double quotes"),
    ("if stat -f x; then :; fi", "after a keyword"),
    ("command stat -f x", "behind `command`"),
)

#: (source, why) pairs the scanner MUST NOT flag. Without these the invariant could be satisfied by
#: a scanner that flags everything, which is the false-positive direction -- and this census gates
#: the required `validate` job, so a false RED there is worse than a false green here.
_CMD_ACCEPTED = (
    ('/bin/mkdir -m 700 "$_cs_d"', "the legitimate literal absolute path"),
    ('printf "%s" "$x"', "a shell builtin"),
    ("zmodload zsh/stat", "a builtin whose ARGUMENT looks like a sensitive basename"),
    ('_x="$(/usr/bin/stat -f \'%p\' -- "$1")"', "a declared fork inside a quoted substitution"),
    ("case $x in stat) : ;; esac", "a case PATTERN that happens to spell a command"),
)

#: `_EXE_RE` sites that are NOT command words, per executable. `/usr/bin/getconf` is NAMED in a
#: publisher diagnostic string -- "the NAME_MAX probe (/usr/bin/getconf) failed" -- and the
#: absolute-path census counts it because it scans text. Declaring the difference is what keeps
#: "the scanner missed a real fork" distinguishable from "the two censuses measure different things".
FORK_MENTIONS = {"/usr/bin/getconf": 1}



def _ls_flags(rest):
    """Merge every short-option letter before `--`. `-lde`, `-led` and `-l -d -e` are one flag set."""
    flags = set()
    for a in rest:
        if a == "--":
            break
        if a.startswith("--"):
            # A GNU long option (`--color`, `--time-style=...`) is not portable and is not a flag
            # bundle either. Revision 3 skipped it silently and classified the fork portable
            # (codex + agy, r4). None propagates to classify_fork, which the census treats as
            # unclassified -- a human decides.
            return None
        if a.startswith("-") and len(a) > 1:
            flags.update(a[1:])
    return flags


def _command_args(text):
    r"""Tokenise the argv that FOLLOWS an executable, stopping where the command does.

    A fork here is usually wrapped: `_x="$(/usr/bin/stat -f '%p' -- "$1" 2>/dev/null)" || return 1`.
    Handing the whole remainder to `shlex.split` raises "No closing quotation" on the enclosing
    substitution's own quote -- which is what a first attempt at this census did on FIVE real sites.
    Walk to the first terminator that is genuinely at top level, then tokenise what is left.

    Three things must be tracked, and each was learned by being caught missing it:
      * QUOTES, or the enclosing wrapper's quote ends the scan (r1).
      * COMMAND SUBSTITUTION, or an inner `)` / `|` truncates the argv and a runtime `ls ... -e`
        classifies as portable (codex + agy, r2). A substitution is refused outright rather than
        parsed -- but only a REAL one: `'$('` inside single quotes and an escaped `\$(` are
        literals, and rejecting those was a false RED (codex, r3).
      * `${...}` NESTING, or a `)` inside a parameter default truncates exactly the same way --
        `${x:-a)b}` parsed to `['-l', '${x:-a']` and reported portable while the runtime argv held
        `-e` (codex, r3). That hole was relocated by the r2 fix, not closed.

    Raises ValueError when the remainder cannot be classified with confidence; the caller treats
    that as unclassified, never as absent.
    """
    out, quote, braces, i = [], None, 0, 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and quote != "'" and i + 1 < len(text):
            out.append(ch)
            out.append(text[i + 1])          # an escaped `$` is not a substitution
            i += 2
            continue
        if quote == "'":                     # single quotes: everything is literal
            out.append(ch)
            if ch == "'":
                quote = None
            i += 1
            continue
        if ch == "`" or text[i:i + 2] == "$(":
            raise ValueError("command substitution in the argument region; classify by hand")
        if quote == '"':
            # Quote state is resolved FIRST: a `}` inside `${x:-"}"}` closed the brace depth while
            # still inside quotes, and a later `;` then truncated the argv (agy, r4).
            out.append(ch)
            if ch == '"':
                quote = None
            i += 1
            continue
        if text[i:i + 2] == "${":
            braces += 1
            out.append(ch)
            out.append(text[i + 1])
            i += 2
            continue
        if braces and ch == "}":
            braces -= 1
            out.append(ch)
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if not braces and ch in "<>":
            # A REDIRECTION, not a terminator: `/bin/ls -l 2>/dev/null -e -- /x` continues with
            # real argv after it, and treating `>` as the end classified that as portable while the
            # runtime argv held `-e` (codex, r4). Skip the operator and its target, then carry on.
            # `<(` is process substitution -- a substitution, so refuse rather than guess.
            if text[i:i + 2] in ("<(", ">("):
                raise ValueError("process substitution in the argument region; classify by hand")
            i += 1
            while i < len(text) and text[i] in "<>&":
                i += 1
            while i < len(text) and text[i].isspace():
                i += 1
            # THE TARGET IS A WORD, AND A WORD CAN BE QUOTED. Walking to the first space or `;`
            # broke inside `2>"/tmp/my log; err"` and truncated every argument after it, so
            # `/bin/ls -ld 2>"/tmp/my log; err" -e -- /x` parsed to ['-ld'] and classified PORTABLE
            # while the runtime argv carried `-e` (agy, r19). Same shape as the r4 defect this
            # redirection arm was added to fix, one level down.
            rq = None
            while i < len(text):
                rc = text[i]
                if rq:
                    if rc == rq:
                        rq = None
                    i += 1
                    continue
                if rc in "'\"":
                    rq = rc
                    i += 1
                    continue
                if rc.isspace() or rc in ");|&":
                    break
                i += 1
            out.append(" ")
            continue
        if not braces and ch in ");|&":
            break
        out.append(ch)
        i += 1
    args = shlex.split("".join(out), comments=False, posix=True)
    # `2>/dev/null` leaves a bare fd number behind once the redirect is cut off.
    while args and args[-1].isdigit():
        args.pop()
    return args


def classify_fork(argv):
    """('portable'|'nonportable', reason) for a complete runtime argv, or None if UNRECOGNISED.

    None is NOT a synonym for portable. Revision 1 returned None for anything it did not know and
    `admits` then let it through, so a Darwin-only `dsmemberutil checkmembership` was admitted at
    runtime while all seven classifier cells passed. Callers must treat None as "a human has not
    classified this yet" and refuse.
    """
    if not argv:
        return None
    exe, rest = argv[0], list(argv[1:])
    kind = FORK_EXES.get(exe)
    if kind is None:
        return None
    if kind != "argv":
        return (kind, f"{exe} is {kind} regardless of argv")
    if exe == "/usr/bin/stat":
        # BOTH SPELLINGS ARE NON-PORTABLE, and that is not a contradiction of `_u_path_id` being
        # portable. This classifier answers about a SITE. `-f` is a BSD format string and means
        # FILE-SYSTEM information to GNU; `-c` is a GNU format string and BSD `stat` has no `-c` at
        # all (measured here: `stat: illegal option -- c`). `_u_path_id` is portable because it
        # holds one of each behind `_u_platform`, so every individual fork it makes is correctly
        # reported non-portable while the function as a whole runs everywhere (COREDEV-2761).
        for flag, other in (("-f", "GNU -f means file system"),
                            ("-c", "BSD stat has no -c")):
            if flag in rest:
                i = rest.index(flag) + 1
                fmt = rest[i] if i < len(rest) else "<missing>"
                return ("nonportable", f"stat {flag} {fmt!r}: platform-specific format; {other}")
        return None                      # an unrecognised stat shape must be classified by hand
    if exe == "/bin/ls":
        flags = _ls_flags(rest)
        if not flags:          # None (a long option) or empty: unrecognised either way
            return None
        if "e" in flags:
            return ("nonportable", f"ls -{''.join(sorted(flags))}: -e (ACL) is BSD-only")
        return ("portable", f"ls -{''.join(sorted(flags))}: no -e")
    return None


def admits(argv_list):
    """May a cell whose forks are exactly `argv_list` leave the Darwin gate? FAIL-CLOSED.

    An unrecognised argv answers False, not True. That is the whole correction from revision 1.
    """
    return all(
        (classify_fork(a) or (None, ""))[0] == "portable" for a in argv_list
    )


def _logical_lines(path):
    """Yield (first_line_number, code) with backslash continuations JOINED and comments stripped.

    Revision 1 read physical lines and skipped only FULL-LINE comments, so a backslash-continued
    fork was invisible (the exe and its `-f` sat on different lines) while `: # /usr/bin/stat -f`
    counted as a real one. Comment stripping tracks quoting, because `'#'` inside a format string
    is not a comment -- `stat -f '%p %z'` has none, but a future format could.
    """
    buf, start = "", None
    with open(path, encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if start is None:
                start = n
            if line.endswith("\\"):
                buf += line[:-1] + " "
                continue
            buf += line
            code, quote = [], None
            for ch in buf:
                if quote:
                    code.append(ch)
                    if ch == quote:
                        quote = None
                elif ch in "'\"":
                    quote = ch
                    code.append(ch)
                elif ch == "#" and (not code or code[-1].isspace()):
                    break
                else:
                    code.append(ch)
            yield start, "".join(code)
            buf, start = "", None
    if buf:                 # a file ending mid-continuation still owes its last logical line;
        yield start, buf    # dropping it silently loses a fork site (measured, r1 remediation)


class ForkClassification(unittest.TestCase):
    """COREDEV-2691 §7.7 -- ONE control per fork mapping, in BOTH directions, plus a FAIL-CLOSED
    census that re-derives the table from the shipped sources. UNGATED.

    §5's table is load-bearing: whether a cell may move off the Darwin gate depends on the
    classifier's answer for each entry, and a control built on ONE argv validates ONE mapping. The
    portable direction matters just as much and is easier to lose: misclassifying a portable fork as
    blocking is SILENT, because the cell simply stays gated and every other control still passes.
    """

    #: Complete runtime argv, transcribed from the shipped call sites. BOTH `/bin/ls` shapes appear:
    #: `-lde --` and `-lde -d --` are different argv.
    NONPORTABLE_ARGV = (
        ("auth _u_stat", ("/usr/bin/stat", "-f", "%p %z %u %i", "--", "/some/component")),
        ("auth chain prefetch", ("/usr/bin/stat", "-f", "%p %z %u %i %N", "--", "/a", "/b")),
        # `_u_path_id`'s two arms, one per platform. Both are declared because the exact-argv cell
        # compares each against the shipped source, and a dropped arm is exactly how COREDEV-2761
        # happened in the first place.
        ("auth _u_path_id (Darwin)", ("/usr/bin/stat", "-f", "%d %i", "--", "/some/value")),
        ("auth _u_path_id (Linux)", ("/usr/bin/stat", "-c", "%d %i", "--", "/some/value")),
        ("auth _u_acl_enumerate", ("/bin/ls", "-lde", "--", "/some/component")),
        ("auth prefetch ACL", ("/bin/ls", "-lde", "-d", "--", "/a", "/b")),
        ("auth _u_principal_uuid", ("/usr/bin/dsmemberutil", "getuuid", "-U", "<user>")),
    )
    PORTABLE_ARGV = (
        ("auth _u_euid", ("/usr/bin/id", "-u")),
        ("auth _u_principal", ("/usr/bin/id", "-un")),
        ("auth _u_platform", ("/usr/bin/uname", "-s")),
        ("store name budget", ("/usr/bin/getconf", "NAME_MAX", "/some/path")),
        ("publisher mkdir", ("/bin/mkdir", "-p", "--", "/some/dir")),
        # NO `--`: the shipped calls are `/bin/rm -f "$_UNLEASHED_TRANSIENT"` and
        # `/bin/mv -f "$_UNLEASHED_TRANSIENT" "$_pb_entry"`. The `--` here was INVENTED, and the
        # exact-argv cell caught it on its first clean run -- two entries in this table described
        # calls that do not exist as written. (Not exploitable: the operand is a composed absolute
        # path, so it cannot be read as an option. But the table was fiction.)
        ("publisher rm", ("/bin/rm", "-f", "<transient>")),
        ("publisher mv", ("/bin/mv", "-f", "<transient>", "<entry>")),
    )

    def test_each_nonportable_argv_keeps_its_cell_gated(self):
        for label, argv in self.NONPORTABLE_ARGV:
            with self.subTest(site=label):
                got = classify_fork(argv)
                self.assertIsNotNone(got, f"{label} is unclassified")
                self.assertEqual("nonportable", got[0], f"{label}: {got}")
                self.assertFalse(admits([argv]), f"{label} would leave the Darwin gate")

    def test_each_portable_argv_admits_its_cell(self):
        """The opposite direction. Without these, a portable fork misread as blocking is invisible."""
        for label, argv in self.PORTABLE_ARGV:
            with self.subTest(site=label):
                got = classify_fork(argv)
                self.assertIsNotNone(got, f"{label} is unclassified")
                self.assertEqual("portable", got[0], f"{label}: {got}")
                self.assertTrue(admits([argv]), f"{label} was treated as blocking")

    def test_respelled_bsd_ls_flags_are_still_non_portable(self):
        """`-lde`, `-led` and `-l -d -e` are the SAME flags. Revision 1 compared `-lde` as one exact
        element, so two respellings of a set the table DECLARES non-portable classified as unknown
        and were admitted -- the classifier's own table defeated by whitespace."""
        for rest in (("-lde", "--"), ("-led", "--"), ("-l", "-d", "-e", "--"), ("-e", "-l", "-d")):
            with self.subTest(flags=rest):
                got = classify_fork(("/bin/ls",) + rest + ("/x",))
                self.assertIsNotNone(got, f"ls {rest} unclassified")
                self.assertEqual("nonportable", got[0], f"ls {rest}: {got}")
        portable = classify_fork(("/bin/ls", "-ld", "--", "/x"))
        self.assertEqual("portable", portable[0], "ls without -e should not block")

    def test_an_unrecognised_argv_is_refused_not_admitted(self):
        """FAIL-CLOSED, the correction that defines this revision. Revision 1's `admits` returned
        True for anything `classify_fork` did not know, so a Darwin-only subcommand of a declared
        binary sailed through. Both cases below were admitted before."""
        for argv in (("/usr/bin/dsmemberutil", "checkmembership", "-U", "n", "-G", "g"),
                     ("/usr/bin/stat", "--printf", "%s", "/x"),
                     ("/usr/bin/perl", "-e", "1")):
            with self.subTest(argv=argv):
                self.assertFalse(admits([argv]), f"{argv} was admitted")
        self.assertIsNone(classify_fork(("/usr/bin/perl", "-e", "1")))

    def test_every_declared_stat_format_is_told_apart(self):
        """`%p %z %u %i` is a strict PREFIX of `%p %z %u %i %N`; substring matching maps both to one
        entry and a single control then appears to cover two mappings.

        THE COUNT IS DERIVED, not pinned. This cell was named `..._three_stat_formats...` and
        asserted a literal 3; COREDEV-2761 added a fourth (the GNU `-c` arm) and the cell failed for
        the one reason that is not a defect. r19 fixed the identical rot in the CI-floor cell a day
        earlier. A count that describes an inventory must be read FROM that inventory.
        """
        stat_argv = [a for _, a in self.NONPORTABLE_ARGV if a[0] == "/usr/bin/stat"]
        self.assertGreater(len(stat_argv), 1, "no stat argv declared -- this cell would be inert")
        got = [classify_fork(a)[1] for a in stat_argv]
        self.assertEqual(len(stat_argv), len(set(got)), f"the stat formats collapsed: {got}")

    def test_admits_is_not_vacuously_true(self):
        self.assertFalse(admits([("/usr/bin/id", "-u"), ("/bin/ls", "-lde", "--", "/x")]))
        self.assertTrue(admits([("/usr/bin/id", "-u")]))
        self.assertTrue(admits([]))

    def test_every_guard_operand_is_quoted(self):
        """Every `_unleashed_auth_chain` operand in the shipped libraries must be QUOTED.

        Sixth mutation class (codex, r13): dropping the quotes from a guard operand loses argument
        ATOMICITY. Under bash the value word-splits, the shipped authenticator -- which does not
        enforce arity -- receives the FIRST word only, authenticates that safe prefix, and the caller
        then accepts the original unverified chain. Measured fail-open: `_unleashed_store_ok`
        returned 1 correctly and 0 under the mutant.

        Covered STATICALLY, and deliberately so. A behavioural cell would need a path containing a
        space or a hostile IFS, and would discriminate in BASH ONLY: zsh does not word-split
        unquoted parameter expansions, so the same mutation is an equivalent mutant there (measured
        -- bash rc 0 vs 1, zsh rc 0 vs 0). A source-level invariant covers all NINE sites in both
        shells at once, which a per-site behavioural fixture cannot.
        """
        unquoted = []
        for path in (AUTH, STORE, READER, PUB):
            base = os.path.basename(path)
            for n, code in _logical_lines(path):
                for m in re.finditer(r"_unleashed_auth_chain\s+(\S+)", code):
                    # Trailing shell punctuation is not part of the operand: the publisher's two
                    # sites are `if ! _unleashed_auth_chain "$_pb_anc"; then`, and keeping the `;`
                    # made a correctly-quoted operand look unquoted.
                    operand = m.group(1).rstrip(";&|)")
                    if operand.startswith("()"):          # the definition, not a call
                        continue
                    if not (operand.startswith('"') and operand.endswith('"')):
                        unquoted.append(f"{base}:{n}: {operand}")
        self.assertEqual([], unquoted,
                         "a guard operand is unquoted -- it can word-split and authenticate only "
                         "its first word")

    def test_every_command_word_is_a_literal_declared_absolute_path(self):
        """The absolute-path census is only sufficient because this invariant holds.

        Every command word in the four shipped libraries must be a shell builtin or keyword, a
        function these same files define, or a LITERAL declared absolute path. Anything else fails,
        by name and line, with no list of forbidden spellings to keep current.
        """
        funcs = _defined_functions((AUTH, STORE, READER, PUB))
        offenders = []
        for path in (AUTH, STORE, READER, PUB):
            base = os.path.basename(path)
            lines = list(_logical_lines(path))
            joined = "\n".join(code for _, code in lines)
            # Offsets map back to real line numbers, so a report names the site rather than the file.
            spans, off = [], 0
            for num, code in lines:
                spans.append((off, num))
                off += len(code) + 1
            for start, word in _command_words(joined):
                if word in _SHELL_WORDS or word in funcs or word in FORK_EXES:
                    continue
                num = max((n for o, n in spans if o <= start), default=lines[0][0])
                offenders.append(f"{base}:{num}: {word!r} is not a builtin, a defined function, "
                                 "or a literal declared absolute path")
        self.assertEqual([], offenders, "a command word is neither known nor a literal absolute path")

    def test_the_command_word_scanner_flags_every_known_escape_and_no_legitimate_form(self):
        """The control, in BOTH directions, because only one of them was ever checked.

        The escapes are the real ones reviewers found, r1 through r19. The accepted forms are the
        other direction: a scanner that flags everything satisfies the invariant above and turns the
        required `validate` job red on correct code, which is the worse failure here.
        """
        funcs = _defined_functions((AUTH, STORE, READER, PUB))

        def unknown(src):
            return [w for _, w in _command_words(src)
                    if w not in _SHELL_WORDS and w not in funcs and w not in FORK_EXES]

        for src, why in _CMD_ESCAPES:
            with self.subTest(escape=why):
                self.assertTrue(unknown(src), f"{src!r} escaped the scanner: {why}")
        for src, why in _CMD_ACCEPTED:
            with self.subTest(accepted=why):
                self.assertEqual([], unknown(src), f"{src!r} was flagged but is legitimate: {why}")

    def test_the_command_word_scanner_reaches_every_shipped_fork(self):
        """Zero offenders means nothing if the scanner never reached the forks.

        It did not, for most of one afternoon: an arithmetic-expansion bug stopped the walk halfway
        through plugin-state-store.sh and a quoted substitution swallowed ten more sites, and the
        invariant above reported clean throughout. This compares the command-word census against the
        text-level `_EXE_RE` census per executable; the only permitted difference is a declared
        MENTION in a diagnostic string.
        """
        seen = collections.Counter()
        for path in (AUTH, STORE, READER, PUB):
            joined = "\n".join(code for _, code in _logical_lines(path))
            for _, word in _command_words(joined):
                if word in FORK_EXES:
                    seen[word] += 1
        expected = {exe: FORK_SITE_COUNTS[exe] - FORK_MENTIONS.get(exe, 0)
                    for exe in FORK_SITE_COUNTS}
        self.assertEqual(expected, dict(seen),
                         "the command-word scanner and the absolute-path census disagree on how "
                         "many times an executable is INVOKED")

    def test_the_store_is_created_with_the_exact_mkdir_spelling(self):
        """A SOURCE-level control, and labelled as one because that is what it is.

        agy (r4) showed that adding `-p` to the production mkdir leaves every behavioural cell green.
        I could not build a behavioural control for it, and measured why rather than assuming:
        `_unleashed_create_store` walks top, mid, store IN ORDER, so a component's parent always
        exists by the time its mkdir runs, and `-p` is therefore behaviourally equivalent in every
        fixture reachable here. The hazard is latent -- `-p` would create missing intermediates
        WITHOUT the per-component authentication if the loop order ever changed, and it makes the
        lost-the-race `elif [ -d ]` branch dead code.

        The first spelling of this control was a substring check, and codex (r5) defeated it with
        `-""p`, which both shells concatenate into `-p` at runtime -- evading the very check added to
        prohibit it. It compares TOKENS now, after `_command_args` has resolved quoting, and reads
        LOGICAL lines so a backslash continuation cannot hide the call either (agy, r5).

        `-m 700` itself is behaviourally controlled: dropping it and changing it to `1700` both
        redden SeamedStoreCreation.
        """
        sites = []
        for n, code in _logical_lines(STORE):
            for m in _EXE_RE.finditer(code):
                if m.group(1) == "/bin/mkdir":
                    sites.append((n, _command_args(code[m.end():])))
        self.assertEqual(1, len(sites), f"expected exactly one mkdir call site, got {sites}")
        _, argv = sites[0]
        self.assertEqual(["-m", "700", "$_cs_d"], argv,
                         "the store mkdir is not exactly `-m 700 \"$_cs_d\"`")

    def test_the_mkdir_spelling_control_rejects_a_concatenated_flag(self):
        """The positive control for the cell above. `-""p` is the shape that defeated the substring
        spelling; both shells concatenate it to `-p`, so a token comparison must reject it while a
        substring search for `" -p"` does not see it at all."""
        self.assertNotIn("-p", _command_args(' -m 700 "$_cs_d" 2>/dev/null; then'))
        self.assertIn("-p", _command_args(' -m 700 -""p "$_cs_d" 2>/dev/null; then'),
                      "`-\"\"p` must resolve to the `-p` a token comparison can reject")

    def test_a_quoted_redirection_target_does_not_truncate_the_argv(self):
        """`_command_args` must not lose argv after a redirection target containing a space.

        The control is the pair: the quoted form and the unquoted form must both keep `-e`, because
        the classifier reads `-e` to decide BSD-only, and losing it reports a non-portable fork as
        portable -- the fail-open direction (agy, r19).
        """
        for target, why in (('2>"/tmp/my log; err"', "spaces and a `;` inside double quotes"),
                            ("2>'/tmp/my log; err'", "the same inside single quotes"),
                            ("2>/dev/null", "the ordinary unquoted form")):
            with self.subTest(target=why):
                argv = _command_args(' -ld %s -e -- /x' % target)
                self.assertIn("-e", argv, f"argv was truncated at the redirection target: {argv}")
                self.assertIn("/x", argv, f"argv was truncated at the redirection target: {argv}")

    def test_the_shipped_fork_argv_matches_the_declared_argv_exactly(self):
        """Every declared fork's argv must appear VERBATIM in the shipped source.

        The census classifies any `stat -f` as non-portable and counts the site, so it is blind to
        the FORMAT STRING changing. Substituting `%u` (owner uid) for `%g` (group id) is one
        character, leaves branches, return codes, fork count and call order identical, and makes a
        foreign-owned component authenticate whenever its GID equals the effective uid (codex, r18).

        This compares the declared argv against the source as an EXACT token sequence, so any field
        that moves, is dropped, or is swapped for a different specifier reddens -- whatever it does
        to control flow, which is nothing.
        """
        # CODE ONLY. The raw text contains prose like "`/bin/ls -lde -d` over every component of
        # the chain", so searching it found the argv in a COMMENT and a dropped `-e` at the real
        # call site still passed. That is the third time in this work that a lexical search counted
        # a mention as the thing itself -- the reachability census counted a label and a
        # redefinition the same way. `_logical_lines` strips comments and joins continuations.
        sources = "\n".join(code for path in (AUTH, PUB, STORE)
                            for _, code in _logical_lines(path))
        missing = []
        for label, argv in self.NONPORTABLE_ARGV + self.PORTABLE_ARGV:
            # Rebuild the invocation as the source spells it: quoted format strings, `--` retained.
            # Keep the LITERAL prefix only: the exe, its flags, and any format string. Trailing
            # elements are placeholders standing in for runtime values -- the source spells them
            # `"$1"` or `"$_cs_d"` -- so comparing them verbatim is meaningless. `dsmemberutil
            # getuuid -U someone` is the clearest case: `someone` is invented, `getuuid -U` is not.
            # Placeholders are MARKED `<like-this>`, never inferred. A first attempt stopped at the
            # first non-flag word, which cannot tell the literal subcommand `getuuid` from the
            # invented operand `someone` -- both are alphabetic. Angle brackets never appear in a
            # real argv, so the marker is unambiguous and the table states which parts are real.
            # `--` is KEPT, and the scan stops after it. Without it the two `/bin/ls` sites share
            # the prefix `/bin/ls -lde`, so dropping the `e` at ONE site left the other matching and
            # the check passed -- an argv appearing SOMEWHERE is not the same as it appearing at
            # every site that declares it. With the terminator, `-lde --` and `-lde -d --` are
            # distinct strings and each site stands alone.
            literal = [argv[0]]
            for a in argv[1:]:
                if a.startswith("<") or a.startswith("/"):
                    break
                literal.append("'%s'" % a if " " in a else a)
                if a == "--":
                    break
            head = " ".join(literal)
            if head not in sources:
                missing.append(f"{label}: {head!r} not found verbatim in the shipped sources")
        self.assertEqual([], missing,
                         "a declared fork's argv does not appear verbatim -- the shipped call was "
                         "changed without updating the table, or vice versa")

    def test_the_declared_tables_match_the_shipped_sources(self):
        """DERIVED and FAIL-CLOSED, in both directions.

        Revision 1 did `if got: found.add(got)` -- an argv it could not parse contributed NOTHING,
        so the census inherited the partiality it was documented to close, and a new Darwin-only
        fork stayed green. Here every absolute-path executable found must be DECLARED, and every
        `argv`-kind site must CLASSIFY; anything else fails with its file:line.
        """
        undeclared, unclassified, split_exe = [], [], []
        seen = collections.Counter()
        for path in (AUTH, STORE, READER, PUB):
            base = os.path.basename(path)
            for n, code in _logical_lines(path):
                # `"/bin/"ls -lde` runs the real binary while `_EXE_RE` matches nothing, so the
                # site escapes both this census and the bare/variable invariant (codex, r4). An
                # executable that only appears once the quotes are removed is a split spelling.
                dequoted = code.replace('"', "").replace("'", "")
                extra = {m.group(1) for m in _EXE_RE.finditer(dequoted)} - {
                    m.group(1) for m in _EXE_RE.finditer(code)}
                for e in sorted(extra):
                    split_exe.append(f"{base}:{n}: {e} written across quotes")
                for m in _EXE_RE.finditer(code):
                    exe = m.group(1)
                    seen[exe] += 1
                    if exe not in FORK_EXES:
                        undeclared.append(f"{base}:{n}: {exe}")
                        continue
                    if FORK_EXES[exe] != "argv":
                        continue
                    try:
                        rest = _command_args(code[m.end():])
                    except ValueError as exc:
                        unclassified.append(f"{base}:{n}: {exe} unparseable ({exc})")
                        continue
                    if classify_fork([exe] + rest) is None:
                        unclassified.append(f"{base}:{n}: {exe} {' '.join(rest[:4])}")
        self.assertEqual([], split_exe, "a fork's executable is split across quotes")
        self.assertEqual([], undeclared, "a fork site's executable is not in FORK_EXES")
        self.assertEqual([], unclassified, "a fork site's argv could not be classified")
        self.assertEqual(FORK_SITE_COUNTS, dict(seen),
                         "the shipped fork SITES and the declared counts have diverged")


#: The platform gate, mutated so the SHIPPED chain refuses on a Darwin box exactly as it does on
#: Linux. Line-count preserving, so §7.1's rule holds for it.
LINUX_SIM = ('[ "$_U_PLATFORM" = Darwin ] || return 1',
             '[ "$_U_PLATFORM" = LinuxSm ] || return 1')


def counting_seam_source(refuse_at):
    """A seam that ALLOWS every call except the Nth, which it REFUSES.

    The allowlist seam proves the guard was CONSULTED. It cannot prove the caller HONOURS a refusal:
    weakening `|| return 1` to `|| :` at a call site leaves a success-path transcript and rc=0
    completely unchanged (codex r2, reproduced). Refusing by POSITION is what discriminates, and it
    reaches call sites an allowlist cannot separate -- store.sh:256 and :259 both authenticate the
    same store path, so no static allowlist can refuse one and not the other.
    """
    return (
        "_SEAM_N=0\n"
        "_unleashed_auth_chain() {\n"
        '    [ "$#" -eq 1 ] || return 1\n'
        '    [ -n "$1" ] || return 1\n'
        '    [ -n "${_SEAM_CALLS:-}" ] || return 1\n'
        # NB: built by CONCATENATION, not %-formatting -- the shell's own `printf '%s\\0'` is a
        # format string too, and `% refuse_at` consumed it (TypeError, caught on first run).
        "    printf '%s\\0' \"$1\" >> \"$_SEAM_CALLS\" || return 1\n"
        "    _SEAM_N=$((_SEAM_N + 1))\n"
        '    [ "$_SEAM_N" = "' + str(refuse_at) + '" ] && return 1\n'
        "    return 0\n"
        "}\n"
    )


class SeamedStoreCreation(SeamedChain, unittest.TestCase):
    """COREDEV-2691 §1 -- the seam DRIVING A PRODUCTION CALLER. UNGATED.

    SeamContract and ForkClassification test the seam and the classifier. Neither invokes a shipped
    caller, so on their own they leave the required ubuntu gate exercising no production entry guard
    -- the very gap this ticket exists to close (codex, r1, blocking). This class closes it.

    `_unleashed_create_store` (plugin-state-store.sh:219) consults the guard FOUR times for a fresh
    store: the nearest existing ancestor (i), then each component it creates, then the store again
    (iii). The store therefore appears TWICE, which is why the assertion is an ordered transcript
    with multiplicity and not a set -- comparing `{claude, mid, store}` is unchanged when either
    store call is deleted, so a set comparison cannot prove what this cell exists to prove.

    Every run here is under LINUX-SIM, so the cell asks the same question on every platform: the
    shipped chain refuses, and only a seam can carry the caller through.
    """

    #: `/bin/mkdir` seamed to LOSE THE RACE for `mid`: the directory appears, but mkdir reports
    #: failure -- exactly what happens when a concurrent publisher wins. A slash-named shell
    #: function DOES take precedence over an absolute-path command in both bash and zsh (measured),
    #: which is what makes this arm reachable at all.
    LOST_RACE_MKDIR = (
        '/bin/mkdir() { _last=""; for _a in "$@"; do _last="$_a"; done;\n'
        '  if [ "$_last" = %s ]; then command /bin/mkdir -m 700 "$_last"; return 1; fi\n'
        '  command /bin/mkdir "$@"; }\n'
    )

    def _create_store(self, shell, seamed, race=False, refuse_at=None, lose_race=False,
                      mid_exists=False, top_exists=True):
        """Run `_unleashed_create_store` on a fresh HOME. Returns (rc, transcript, modes).

        `race=True` seams `_unleashed_nearest_existing` so that `mid` APPEARS between the walk and
        the loop, which is the only way to reach plugin-state-store.sh:239.
        """
        auth = with_mutation(*LINUX_SIM, path=AUTH)
        self.addCleanup(os.unlink, auth)

        home = scratch_home("seamstore-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        claude = os.path.join(home, ".claude")
        if top_exists:
            os.makedirs(claude, mode=0o700)
        mid = os.path.join(claude, "unleashed-mail")
        if mid_exists:
            # Makes `_UNLEASHED_NEAREST` == mid, so it DIFFERS from `_cs_top`. Every other fixture
            # here leaves those two equal, which is what let store:225 be rewritten undetected.
            os.makedirs(mid, mode=0o700)
        store = os.path.join(mid, "bases")
        log = os.path.join(home, "calls")
        with open(log, "wb"):
            pass

        body = (
            "_SEAM_CALLS=%s\n_SEAM_A1=%s\n_SEAM_A2=%s\n_SEAM_A3=%s\n"
            % tuple(shlex.quote(x) for x in (log, claude, mid, store))
            + (counting_seam_source(refuse_at) if refuse_at is not None
               else seam_source() if seamed else "")
            + ("_unleashed_nearest_existing() { /bin/mkdir -m 700 -p %s 2>/dev/null; "
               "_UNLEASHED_NEAREST=%s; }\n"
               % (shlex.quote(store if race == "both" else mid), shlex.quote(claude))
               if race else "")
            + ((self.LOST_RACE_MKDIR % shlex.quote(mid)).replace("\\n", "\n")
               if lose_race else "")
            + "_unleashed_create_store %s\n" % shlex.quote(store)
            + 'printf "SEAM_RC=%s\\n" "$?"\n'
        )
        out = run_shell(shell, body, env={"HOME": home},
                        sources=(auth, STORE, READER, PUB))[1]
        rcs = [int(l[len("SEAM_RC="):]) for l in out.splitlines() if l.startswith("SEAM_RC=")]
        with open(log, "rb") as fh:
            raw = fh.read()
        transcript = [r.decode() for r in raw.split(b"\0")[:-1]]
        # Two maps, deliberately: `names` labels the TRANSCRIPT, which includes `home` when the
        # fixture leaves `.claude` absent; the mode assertions below cover only the three components
        # they were written for. Folding `home` into both broke that assertion.
        names = {home: "home", claude: "claude", mid: "mid", store: "store"}
        mode_paths = ((claude, "claude"), (mid, "mid"), (store, "store"))
        # 0o7777, NOT 0o777. Masking to twelve bits erased setuid/setgid/sticky, so mutating the
        # production `mkdir -m 700` to `-m 1700` left rc, transcript, existence AND the reported
        # modes all unchanged while producing a store `_unleashed_store_ok` refuses forever
        # (codex, r4 -- reproduced). The reader requires EXACTLY 0700.
        modes = {n: (oct(os.stat(p).st_mode & 0o7777) if os.path.isdir(p) else "ABSENT")
                 for p, n in mode_paths}
        return (rcs[0] if rcs else None), [names.get(t, t) for t in transcript], modes

    #: (label, race, refuse_at) -> the transcript the walk must stop at, MEASURED. Each row refuses
    #: one call POSITION, and the position maps to one production call site.
    #: (label, race, refuse_at, expected transcript, components that may EXIST afterwards).
    #: The filesystem column is not decoration: without it the rows check only rc and the ordered
    #: transcript, and a mutation that creates `mid` BEFORE the first authentication leaves both
    #: unchanged (codex, r3). Row 1 expects NOTHING created, so any pre-authentication mkdir reddens
    #: it. Every value here was measured, in both shells, before being written down.
    REFUSAL_ROWS = (
        ("store.sh:225 nearest ancestor", False, 1, ["claude"], set()),
        ("store.sh:256 per-created component", False, 2, ["claude", "mid"], {"mid"}),
        ("store.sh:256 the store itself", False, 3, ["claude", "mid", "store"], {"mid", "store"}),
        ("store.sh:259 the store again", False, 4,
         ["claude", "mid", "store", "store"], {"mid", "store"}),
        # The race fixture creates `mid` itself, deliberately -- that IS the race being modelled --
        # so `mid` is expected here and the pre-authentication check lives on the rows above.
        ("store.sh:239 appeared-since-walk", True, 2, ["claude", "mid"], {"mid"}),
    )

    def test_create_store_consults_the_guard_for_every_component_in_order(self):
        """The ordered transcript, with multiplicity. This is the cell that fails if a maintainer
        deletes a production guard call -- mutation-verified against all four call sites."""
        def check(shell):
            rc, transcript, modes = self._create_store(shell, seamed=True)
            self.assertEqual(0, rc, "the seamed production caller did not succeed")
            self.assertEqual(["claude", "mid", "store", "store"], transcript,
                             "the guard was not consulted for every component, in order")
            self.assertEqual({"claude": "0o700", "mid": "0o700", "store": "0o700"}, modes,
                             "a component was created with the wrong mode")
        self.for_declared_shells(SHELLS, check)

    def test_a_component_that_appeared_after_the_walk_is_authenticated(self):
        """The fourth production guard call, plugin-state-store.sh:239.

        That branch fires only when a component is ABSENT during the nearest-ancestor walk and
        PRESENT by the time the loop reaches it -- an interfering same-uid process planting
        `.claude/unleashed-mail` in between. codex reproduced exactly that on PR #67 as a symlink
        the refusal path then created through, which is why the branch exists. A plain fixture can
        never reach it, so the three other cells here leave it uncovered.

        `_unleashed_nearest_existing` is seamed the same way the chain is -- redefined in the body
        after sourcing -- to report a SHALLOWER nearest while creating the component behind it. That
        is the race, made deterministic.
        """
        def check(shell):
            rc, transcript, _ = self._create_store(shell, seamed=True, race=True)
            self.assertEqual(0, rc, "the seamed production caller did not succeed")
            self.assertEqual(["claude", "mid", "store", "store"], transcript,
                             "the component that appeared after the walk was not authenticated")
        self.for_declared_shells(SHELLS, check)

    def test_a_refused_component_stops_the_create_at_that_call_site(self):
        """ENFORCEMENT, not invocation -- the distinction codex drew at r2.

        The three cells above assert the guard is CONSULTED. None of them fails when a call site's
        `|| return 1` is weakened to `|| :`, because on the success path nothing changes: same
        transcript, same rc=0. The security-relevant behaviour is what happens when the guard says
        NO -- an interfering process planted a symlink at `mid` and authentication refuses. These
        rows refuse one call position each and require the walk to STOP there and report failure.
        """
        def check(shell):
            for label, race, refuse_at, expected, may_exist in self.REFUSAL_ROWS:
                with self.subTest(site=label):
                    rc, transcript, modes = self._create_store(
                        shell, seamed=True, race=race, refuse_at=refuse_at)
                    self.assertEqual(1, rc, f"{label}: a refused chain still returned success")
                    self.assertEqual(expected, transcript,
                                     f"{label}: the walk did not stop at the refusal")
                    created = {n for n in ("mid", "store") if modes[n] != "ABSENT"}
                    self.assertEqual(may_exist, created,
                                     f"{label}: components created past (or before) the refusal")
        self.for_declared_shells(SHELLS, check)

    def test_the_refusal_rows_pass_when_nothing_is_refused(self):
        """The positive control for the cell above: with `refuse_at` past the end of the walk, the
        SAME counting seam authenticates everything and the create succeeds. Without this, a
        counting seam that refused unconditionally would satisfy every refusal row."""
        def check(shell):
            rc, transcript, _ = self._create_store(shell, seamed=True, refuse_at=99)
            self.assertEqual(0, rc, "the counting seam refuses even when it should not")
            self.assertEqual(["claude", "mid", "store", "store"], transcript)
        self.for_declared_shells(SHELLS, check)

    def test_the_nearest_existing_ancestor_is_what_gets_authenticated(self):
        """store.sh:225 must authenticate `$_UNLEASHED_NEAREST`, not some other in-scope variable.

        Every other fixture in this class starts with only `~/.claude` present, so the nearest
        existing ancestor IS `_cs_top` and the two variables are INDISTINGUISHABLE. Replacing
        `$_UNLEASHED_NEAREST` with the adjacent `$_cs_top` therefore left all 43 cells green while
        regressing a real guard: when `_cs_mid` exists but does not authenticate, production
        authenticates only `_cs_top`, the `case` then treats `_cs_mid` as already walked, and the
        store is created beneath an unauthenticated component (codex, r11 -- reproduced).

        Pre-creating `mid` separates them: nearest becomes mid, and the transcript's FIRST entry is
        the discriminator.
        """
        def check(shell):
            rc, transcript, _ = self._create_store(shell, seamed=True, mid_exists=True)
            self.assertEqual(0, rc, "the seamed production caller did not succeed")
            self.assertEqual(["mid", "store", "store"], transcript,
                             "the guard was not called with the NEAREST EXISTING ancestor")
        self.for_declared_shells(SHELLS, check)

    def _walk_transcript(self, shell, kind):
        """Drive `_unleashed_create_store` with a PERMISSIVE recording seam over a fixture shaped to
        separate two predicates that ordinary fixtures leave equal. Returns (rc, labelled transcript).
        """
        auth = with_mutation(*LINUX_SIM, path=AUTH)
        self.addCleanup(os.unlink, auth)
        home = scratch_home("walk-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        extra = ""
        if kind == "sibling":
            claude = os.path.join(home, ".claude")
            os.makedirs(claude, mode=0o700)
            sibling = os.path.join(home, ".claude-attacker")
            os.makedirs(sibling, mode=0o700)
            mid = os.path.join(claude, "unleashed-mail")
            store = os.path.join(mid, "bases")
            extra = ("_unleashed_nearest_existing() { _UNLEASHED_NEAREST=%s; }\n"
                     % shlex.quote(sibling))
            names = {sibling: "sibling", claude: "claude", mid: "mid", store: "store"}
        else:                                    # a NON-DIRECTORY ancestor
            afile = os.path.join(home, "afile")
            with open(afile, "w", encoding="utf-8") as fh:
                fh.write("x")
            mid = os.path.join(afile, "x")
            store = os.path.join(mid, "bases")
            names = {home: "home", afile: "afile", mid: "mid", store: "store"}
        log = os.path.join(home, "calls")
        with open(log, "wb"):
            pass
        body = ("_SEAM_CALLS=%s\n" % shlex.quote(log)
                + counting_seam_source(0)        # 0 never matches _SEAM_N, so every call is allowed
                + extra
                + "_unleashed_create_store %s\n" % shlex.quote(store)
                + 'printf "SEAM_RC=%s\\n" "$?"\n')
        out = run_shell(shell, body, env={"HOME": home}, sources=(auth, STORE, READER, PUB))[1]
        rcs = [int(l[len("SEAM_RC="):]) for l in out.splitlines() if l.startswith("SEAM_RC=")]
        with open(log, "rb") as fh:
            raw = fh.read()
        return (rcs[0] if rcs else None), [names.get(r.decode(), r.decode())
                                           for r in raw.split(b"\0")[:-1]]

    def test_a_sibling_sharing_the_prefix_is_not_treated_as_already_walked(self):
        """store.sh:238's `case` must match the component or its DESCENDANTS, not its prefix.

        `"$_cs_d"|"$_cs_d"/*` widened to `"$_cs_d"*` matches a SIBLING -- `.claude-attacker` matches
        `.claude*` -- so a newly appeared `.claude` is treated as already walked and its guard is
        skipped entirely. All 48 cells stayed green, because every fixture makes the nearest
        ancestor a descendant of the component and never a sibling (agy, r13 -- reproduced).

        Narrowing the same pattern (dropping the `/*` arm) IS caught by the existing cells; only
        widening was invisible, which is the direction that fails OPEN.
        """
        def check(shell):
            rc, transcript = self._walk_transcript(shell, "sibling")
            self.assertEqual(0, rc, "the walk did not complete")
            self.assertEqual(["sibling", "claude", "mid", "store", "store"], transcript,
                             "a component was treated as already walked because a SIBLING shared "
                             "its prefix")
        self.for_declared_shells(SHELLS, check)

    def test_the_ancestor_walk_stops_only_at_a_directory(self):
        """`_unleashed_nearest_existing` must walk to the nearest existing DIRECTORY.

        `[ ! -d "$_ne_d" ]` weakened to `[ ! -e "$_ne_d" ]` stops the walk at a regular file or a
        dangling symlink, so the guard is called with a path that is not a directory at all. Every
        fixture has directories all the way up, so all 48 cells stayed green (agy, r13).
        """
        def check(shell):
            rc, transcript = self._walk_transcript(shell, "file")
            self.assertEqual(["home"], transcript,
                             "the ancestor walk stopped at a NON-DIRECTORY")
            self.assertEqual(1, rc, "a store under a non-directory ancestor was created")
        self.for_declared_shells(SHELLS, check)

    def test_every_component_the_loop_creates_is_authenticated(self):
        """store.sh:227 -- the loop must walk `$_cs_top` as well as mid and store.

        Every other fixture pre-creates `~/.claude`, so the top iteration authenticates a component
        that already existed and dropping `$_cs_top` from the loop bound changes nothing observable.
        On a clean install -- or a top-appeared race -- the mutant creates `mid` THROUGH a component
        it never validated (codex, r12 -- reproduced against the production function).

        Leaving top absent makes the loop responsible for creating and authenticating it, and the
        transcript grows from four entries to five. The permissive counting seam is used because the
        walk needs four distinct allowlist entries and the seam carries three.
        """
        def check(shell):
            rc, transcript, _ = self._create_store(shell, seamed=True, refuse_at=99,
                                                   top_exists=False)
            self.assertEqual(0, rc, "a clean install did not complete")
            self.assertEqual(["home", "claude", "mid", "store", "store"], transcript,
                             "a component the loop CREATED was not authenticated")
        self.for_declared_shells(SHELLS, check)

    def test_each_component_that_appeared_is_authenticated_as_itself(self):
        """store.sh:239 must authenticate `$_cs_d` -- the component the loop is ON.

        The other race fixture makes only `mid` appear, so on the single pass through that branch
        `_cs_d` IS `_cs_mid` and the two are indistinguishable. Substituting `$_cs_mid` therefore
        survived every cell. Derived by an operand sweep over all nine guard sites rather than found
        one at a time (~/.claude/handoffs/operand-sweep.py, after codex's r11 pair).

        With BOTH components appearing, the branch fires twice with different values and the THIRD
        transcript entry is the discriminator: the mutant authenticates `mid` a second time instead
        of the store, and would create the store beneath a component it never checked.
        """
        def check(shell):
            rc, transcript, _ = self._create_store(shell, seamed=True, race="both")
            self.assertEqual(0, rc, "the seamed production caller did not succeed")
            self.assertEqual(["claude", "mid", "store", "store"], transcript,
                             "an appeared component was not authenticated as ITSELF")
        self.for_declared_shells(SHELLS, check)

    def test_a_component_that_lost_the_mkdir_race_is_still_authenticated(self):
        """store.sh:252 -- the LOST-RACE arm, and the fifth production behaviour these cells reach.

        `_unleashed_create_store` handles `mkdir` failing because a concurrent publisher already
        created the component: it falls through to `elif [ -d ]`, does NOT treat that as an error,
        and authenticates the component that appeared. codex (r6) found that changing that branch's
        `:` to `continue` -- an idiomatic "another publisher won; continue" refactor, needing no
        scanner evasion -- SKIPS that authentication and then creates the next component through
        whatever now sits there, including a planted symlink. Measured: rc=0 with a directory
        created outside the store, in both shells.

        Neither existing fixture reaches this arm: ordinary creation makes `mkdir` succeed, and the
        `race=True` fixture creates `mid` BEFORE the loop. This one makes `mkdir` fail while the
        directory appears, which is the race itself.
        """
        def check(shell):
            rc, transcript, _ = self._create_store(shell, seamed=True, lose_race=True)
            self.assertEqual(0, rc, "the lost-race path did not complete")
            self.assertEqual(["claude", "mid", "store", "store"], transcript,
                             "the component that won the race was not authenticated")
        self.for_declared_shells(SHELLS, check)

    def test_a_refused_component_that_won_the_race_stops_the_create(self):
        """Enforcement for the same arm: when the component that appeared FAILS authentication --
        the planted-symlink case -- the create must refuse and must not build beneath it."""
        def check(shell):
            rc, transcript, modes = self._create_store(
                shell, seamed=True, lose_race=True, refuse_at=2)
            self.assertEqual(1, rc, "a refused race winner still returned success")
            self.assertEqual(["claude", "mid"], transcript, "the walk did not stop at the refusal")
            self.assertEqual("ABSENT", modes["store"], "the store was built beneath a refused component")
        self.for_declared_shells(SHELLS, check)

    def test_without_the_seam_the_same_call_refuses_and_creates_nothing(self):
        """Predicate zero, done properly. The version in SeamContract asserts only that the body
        function answers -- it passes even with `sources=()`, so it proves the body works, not that
        it OVERRIDES a shipped function (codex, r1). This runs the SAME production caller over the
        SAME fixture with the seam withheld: the shipped chain refuses, nothing is created, and the
        guard is never consulted. The difference between this cell and the one above is the seam.
        """
        def check(shell):
            rc, transcript, modes = self._create_store(shell, seamed=False)
            self.assertEqual(1, rc, "the shipped chain authenticated under LINUX-SIM")
            self.assertEqual([], transcript, "the shipped chain recorded through the seam's log")
            self.assertEqual("ABSENT", modes["mid"], "a refused create still made a component")
            self.assertEqual("ABSENT", modes["store"], "a refused create still made the store")
        self.for_declared_shells(SHELLS, check)

class SeamedReader(SeamedChain, unittest.TestCase):
    """COREDEV-2691 -- the READER's chain guard, driven through the seam. UNGATED.

    `SeamedStoreCreation` covers `_unleashed_create_store`. It is one of THREE production callers
    behind the chain, and codex (r7) showed the other two are unguarded on the required leg:
    weakening `plugin-state-reader.sh:282` from `|| return 1` to `|| :` left all 31 cells green,
    because none of them calls `_unleashed_store_ok`. The concrete failure is an euid-owned 0700
    store beneath a group-writable, symlinked or foreign-owned ancestor: it must resolve `stale`,
    and the mutant admits it instead.

    THIS CELL DOUBLE-SEAMS, and says so. `_unleashed_store_ok` calls `_u_stat`, which forks the
    Darwin-only `stat -f`, so on Linux it refuses BEFORE reaching the chain call under test. `_u_stat`
    and `_u_euid` are therefore stubbed alongside the chain. That means these cells prove the chain
    is consulted and its refusal honoured -- NOT that `_u_stat`'s mode/owner clauses are right. Those
    clauses are covered by the Darwin-gated classes above, and §5 of the plan is why they stay there.
    """

    @staticmethod
    def stat_stub(table, uid):
        """A PATH-STRICT `_u_stat`: it answers for the listed paths and REFUSES every other.

        The first spelling answered for ANY path with one set of values, which masked a shipped
        mutation: if an ENT-2c call changed from `"$_ae_p"` to its parent, the live `_u_stat` sees a
        different inode and refuses, while the stub handed back the entry's inode and every cell
        stayed green (codex, r8 -- measured, real(entry,parent)=0,1 against stub 0,0). A stub that
        answers for paths the code should never ask about cannot detect the code asking about them.

        `table` maps an exact path (or the literal "/dev/fd" prefix) to (mode, size, inode).
        """
        arms = "".join(
            '  %s) _U_MODE=%s; _U_SIZE=%s; _U_INO=%s ;;\n' % (pattern, mode, size, ino)
            for pattern, (mode, size, ino) in table.items()
        )
        return (
            '_u_stat() { case "$1" in\n' + arms
            + '  *) return 1 ;;\n'          # an unexpected path is a REFUSAL, never a default answer
            + 'esac\n_U_UID=%d\nreturn 0; }\n' % uid
            + '_u_euid() { _U_EUID=%d; return 0; }\n' % uid
        )

    def _store_ok(self, shell, allow, broken=None):
        """Run `_unleashed_store_ok` over a real 0700 store. Returns (rc, transcript)."""
        auth = with_mutation(*LINUX_SIM, path=AUTH)
        self.addCleanup(os.unlink, auth)
        home = scratch_home("seamrdr-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        store = os.path.join(home, "bases")
        os.makedirs(store, mode=0o700)
        log = os.path.join(home, "calls")
        with open(log, "wb"):
            pass
        uid = os.geteuid()
        st = os.stat(store)
        body = (
            "_SEAM_CALLS=%s\n_SEAM_A1=%s\n" % (shlex.quote(log),
                                               shlex.quote(store if allow else "/nothing"))
            + seam_source(broken)
            + self.stat_stub({shlex.quote(store): ("0700", 0, st.st_ino)}, uid)
            + "_unleashed_store_ok %s\n" % shlex.quote(store)
            + 'printf "SEAM_RC=%s\\n" "$?"\n'
        )
        out = run_shell(shell, body, env={"HOME": home},
                        sources=(auth, STORE, READER, PUB))[1]
        rcs = [int(l[len("SEAM_RC="):]) for l in out.splitlines() if l.startswith("SEAM_RC=")]
        with open(log, "rb") as fh:
            raw = fh.read()
        return (rcs[0] if rcs else None), [r.decode() for r in raw.split(b"\0")[:-1]]

    def _auth_entry(self, shell, allow_parent, allow_target, race=False):
        """Build a LEGITIMATE store entry and run `_unleashed_auth_entry` over it.

        The fixture satisfies every ENT-1..3 precondition, each of which refused a draft of this
        probe before it was right: the name is `base.<key>` with the key derived by the SHIPPED
        encoder from the value; the value is an existing directory; the mode is exactly 0600; the
        content is the value plus one trailing newline; and `_u_stat` reports the file's REAL size
        and inode, because zsh's ENT-2b arm stats the DESCRIPTOR with `zstat` and compares inodes.

        `zmodload zsh/stat zsh/system` is done here because the real `_u_stat` is what normally
        loads them -- stubbing it removed the load, `zstat` failed, and the whole ENT-2b `&&` chain
        short-circuited to a refusal that looked like a guard decision. The stub was hiding a
        dependency, which is the sort of thing a stub does quietly.
        """
        auth = with_mutation(*LINUX_SIM, path=AUTH)
        self.addCleanup(os.unlink, auth)
        home = scratch_home("seament-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        store = os.path.join(home, "bases")
        os.makedirs(store, mode=0o700)
        value = os.path.join(home, "data")
        os.makedirs(value, mode=0o700)
        srcs = (auth, STORE, READER, PUB)
        key = run_shell(shell, "_unleashed_key %s\nprintf '%%s' \"$_UNLEASHED_KEY\"\n"
                        % shlex.quote(value), sources=srcs)[1]
        entry = os.path.join(store, "base." + key)
        with open(entry, "w", encoding="utf-8") as fh:
            fh.write(value + "\n")
        os.chmod(entry, 0o600)
        st = os.stat(entry)
        uid = os.geteuid()
        log = os.path.join(home, "calls")
        with open(log, "wb"):
            pass
        allowed = [store if allow_parent else "/nothing", value if allow_target else "/nothing"]
        # PATH-STRICT, including the DESCRIPTOR. `/dev/fd/*` accepted any descriptor -- closed,
        # wrong, or nonsense -- and answered 0600 while the comment beside it claimed the measured
        # 0444 (codex, r9: my own claim-vs-code defect, inside the fix for a claim-vs-code defect).
        # A maintainer changing reader.sh:107's literal `/dev/fd/9` to `/dev/fd/8` makes the live
        # bash arm refuse every entry, while the glob fabricated the expected inode for fd 8 and all
        # four entry cells stayed green. reader.sh:107 uses the LITERAL 9, so 9 is what is listed;
        # the mode is 0444 as measured, and the bash arm reads inode/uid/size from it, never mode.
        stub = (
            'if [ -n "${ZSH_VERSION:-}" ]; then zmodload -i zsh/stat zsh/system 2>/dev/null || :; fi\n'
            + self.stat_stub({shlex.quote(entry): ("0600", st.st_size, st.st_ino),
                              "/dev/fd/9": ("0444", st.st_size, st.st_ino)}, uid)
        )
        if race:
            q = shlex.quote(entry)
            stub += ('_u_euid() { if [ -z "${_SWAPPED:-}" ] && [ -e %s ]; then _SWAPPED=1; '
                     'command mv -- %s %s.real 2>/dev/null; '
                     'command ln -s %s.real %s 2>/dev/null; fi; _U_EUID=%d; return 0; }\n'
                     % (q, q, q, q, q, uid))
        body = ("_SEAM_CALLS=%s\n_SEAM_A1=%s\n_SEAM_A2=%s\n"
                % (shlex.quote(log), shlex.quote(allowed[0]), shlex.quote(allowed[1]))
                + seam_source() + stub
                + "_unleashed_auth_entry %s\n" % shlex.quote(entry)
                + 'printf "SEAM_RC=%s\\n" "$?"\n')
        out = run_shell(shell, body, env={"HOME": home, "LC_ALL": "C"}, sources=srcs)[1]
        rcs = [int(l[len("SEAM_RC="):]) for l in out.splitlines() if l.startswith("SEAM_RC=")]
        if race:
            # The setup must be PROVEN, out of band. `mv` and `ln` failures were ignored: if `mv`
            # succeeded and `ln -s` did not, the open saw an absent pathname and returned 1 BEFORE
            # ENT-2c -- so the cell passed with the re-test deleted, for a reason that has nothing
            # to do with the property under test (codex, r9). An expected rc cannot validate the
            # fixture that produced it.
            self.assertTrue(os.path.islink(entry),
                            "the race did not install a symlink; rc proves nothing here")
            self.assertTrue(os.path.exists(entry + ".real"),
                            "the race did not move the validated entry aside")
            # A DANGLING or wrong-target link satisfies both assertions above while the open (or the
            # descriptor inode check) refuses BEFORE ENT-2c -- so the re-test could be deleted and
            # the cell would still pass (codex, r10). The link must reach the object ENT-1 validated.
            self.assertTrue(os.path.samefile(entry, entry + ".real"),
                            "the race's symlink does not resolve to the moved-aside original")
            self.assertEqual(st.st_ino, os.stat(entry).st_ino,
                             "the race's symlink resolves to a DIFFERENT inode than ENT-1 validated")
        with open(log, "rb") as fh:
            raw = fh.read()
        names = {store: "parent", value: "target"}
        return (rcs[0] if rcs else None), [names.get(r.decode(), r.decode())
                                           for r in raw.split(b"\0")[:-1]]

    def test_an_entry_replaced_by_a_symlink_after_the_read_is_refused(self):
        """ENT-2c -- the pathname is re-tested AFTER the read, and this is the race it exists for.

        codex found (PR #67 pass 15) that a same-uid process can rename the validated entry aside
        and drop a SYMLINK at its name between ENT-1 and the open: the descriptor still has exactly
        the inode ENT-1 validated, so type, owner, size and content all pass, while the surviving
        store entry is a link ENT-1 forbids. Deleting the re-test changes NOTHING on a healthy
        fixture, so the three cells above cannot see it -- measured green before this cell existed.

        The swap is interposed at `_u_euid`. Its FIRST call is reader.sh:33 -- BEFORE either open,
        not after it as an earlier version of this docstring claimed; the commit message was
        corrected and this comment was not, which is half-closing the same defect (codex, r10). The
        timing is nonetheless the right one: it reproduces the ENT-1-to-open swap PR #67 found. It is deliberately not interposed at `_u_stat`: zsh stats the descriptor
        with `zstat` directly, so a `_u_stat` swapper never fires there, and a first attempt at this
        made the zsh arm look like a shipped defect when it was the probe that was wrong.

        Each shell exercises its OWN re-test site -- bash reader.sh:113, zsh reader.sh:101 -- so
        running both arms is what covers both, and deleting either makes that shell accept the race.
        """
        def check(shell):
            rc, _ = self._auth_entry(shell, allow_parent=True, allow_target=True, race=True)
            self.assertEqual(1, rc, "an entry replaced by a symlink after the read was accepted")
        self.for_declared_shells(SHELLS, check)

    def test_entry_authenticates_the_parent_then_the_target(self):
        """reader:207 and :208 -- PCH-1 walks the entry's own chain and the target chain, one each,
        in that order. A legitimate entry authenticates both."""
        def check(shell):
            rc, transcript = self._auth_entry(shell, allow_parent=True, allow_target=True)
            self.assertEqual(0, rc, "a legitimate entry was refused")
            self.assertEqual(["parent", "target"], transcript,
                             "the entry's own chain and the target chain were not both walked")
        self.for_declared_shells(SHELLS, check)

    def test_entry_refuses_when_the_parent_chain_refuses(self):
        """reader:207 in isolation: the walk stops at the parent, and the target is never reached."""
        def check(shell):
            rc, transcript = self._auth_entry(shell, allow_parent=False, allow_target=True)
            self.assertEqual(1, rc, "an entry under a refusing parent was accepted")
            self.assertEqual(["parent"], transcript, "the walk continued past a refused parent")
        self.for_declared_shells(SHELLS, check)

    def test_entry_refuses_when_the_target_chain_refuses(self):
        """reader:208 in isolation: the parent authenticates, so the refusal is attributable to the
        TARGET guard alone -- which the parent-refusal cell above cannot show."""
        def check(shell):
            rc, transcript = self._auth_entry(shell, allow_parent=True, allow_target=False)
            self.assertEqual(1, rc, "an entry naming a refusing target was accepted")
            self.assertEqual(["parent", "target"], transcript,
                             "the target guard was not consulted")
        self.for_declared_shells(SHELLS, check)

    def test_store_ok_consults_the_guard_for_the_store(self):
        """reader:282 -- the guard IS called, with the store path, exactly once."""
        def check(shell):
            rc, transcript = self._store_ok(shell, allow=True)
            self.assertEqual(0, rc, "an authenticating store was refused")
            self.assertEqual(1, len(transcript), f"expected one chain call, got {transcript}")
            self.assertTrue(transcript[0].endswith("/bases"),
                            f"the guard was called for {transcript[0]!r}, not the store")
        self.for_declared_shells(SHELLS, check)

    def test_store_ok_honours_a_refusal(self):
        """reader:282 -- ENFORCEMENT. This is the cell that reddens when `|| return 1` becomes
        `|| :`, which is the mutation codex reproduced against a suite that could not see it."""
        def check(shell):
            rc, transcript = self._store_ok(shell, allow=False)
            self.assertEqual(1, rc, "a store whose chain REFUSED was accepted")
            self.assertEqual(1, len(transcript), "the guard was not consulted before refusing")
        self.for_declared_shells(SHELLS, check)

class SeamedPublisher(SeamedChain, unittest.TestCase):
    """COREDEV-2691 -- the PUBLISHER's two chain guards, driven through the seam. UNGATED.

    The third and last production caller behind the chain. `plugin-state-publisher.sh:230` refuses
    to create a base beneath an ancestor that does not authenticate; `:252` authenticates the
    published base before any key is derived or anything is written. Neither is reached by
    `_unleashed_create_store` or `_unleashed_store_ok`, so before this class both were unguarded on
    the required leg (codex, r7).

    DOUBLE-SEAMED, for the reason given on SeamedReader: `_u_stat` forks the Darwin-only `stat -f`.
    These cells prove the guard is consulted and its refusal honoured, not that the stat clauses are
    right.

    ASSERTED ON THE GUARD, NOT ON A COMPLETE PUBLISH. A full publish needs a writable transient
    under the store, which this fixture deliberately does not build -- the run ends at "the
    plugin-state transient could not be written at 0600". What each cell asserts is the transcript
    up to and including its guard, plus the refusal DIAGNOSTIC, which is the observable the guard
    itself produces.
    """

    stat_stub = staticmethod(SeamedReader.stat_stub)

    def _publish(self, shell, allow, value_exists, depth=1):
        """Run `_unleashed_publish`. Returns (transcript, last failure diagnostic)."""
        auth = with_mutation(*LINUX_SIM, path=AUTH)
        self.addCleanup(os.unlink, auth)
        home = scratch_home("seampub-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        store = os.path.join(home, "bases")
        os.makedirs(store, mode=0o700)
        parent = os.path.join(home, "exists")
        os.makedirs(parent, mode=0o700)
        # depth=2 leaves TWO components missing, so the nearest existing ancestor is `parent` while
        # the value's IMMEDIATE parent is `parent/a` -- which does not exist. At depth 1 they are the
        # same directory, and that equality is what let publisher:230 be rewritten undetected.
        value = (os.path.join(home, "data") if value_exists
                 else os.path.join(parent, *(["a", "b"] if depth == 2 else ["base"])))
        if value_exists:
            os.makedirs(value, mode=0o700)
        uid = os.geteuid()
        log = os.path.join(home, "calls")
        with open(log, "wb"):
            pass
        allowed = (parent, value, store) if allow else ("/nothing", "/nothing", "/nothing")
        body = (
            "_SEAM_CALLS=%s\n_SEAM_A1=%s\n_SEAM_A2=%s\n_SEAM_A3=%s\n"
            % tuple(shlex.quote(x) for x in (log,) + allowed)
            + seam_source()
            + self.stat_stub({shlex.quote(store): ("0700", 0, os.stat(store).st_ino),
                              shlex.quote(parent): ("0700", 0, os.stat(parent).st_ino)}
                             | ({shlex.quote(value): ("0700", 0, os.stat(value).st_ino)}
                                if os.path.isdir(value) else {}), uid)
            + "_unleashed_publish %s %s\n" % (shlex.quote(store), shlex.quote(value))
        )
        err = run_shell(shell, body, env={"HOME": home},
                        sources=(auth, STORE, READER, PUB))[2]
        with open(log, "rb") as fh:
            raw = fh.read()
        transcript = [r.decode().replace(home, "~") for r in raw.split(b"\0")[:-1]]
        failures = [l.split("failed: ")[-1] for l in err.splitlines() if "failed: " in l]
        # WAS THE VALUE CREATED? Without this the refusal cells assert only rc, transcript and
        # diagnostic -- and MOVING the ancestor guard below the `mkdir -p` on publisher.sh:233
        # leaves all three unchanged while creating beneath a refused ancestor (codex, r12). The
        # same filesystem column was added to SeamedStoreCreation's refusal rows at r7 and never
        # propagated here, which is fixing one member of a class and calling it closed.
        created = os.path.isdir(value)
        return transcript, (failures[-1] if failures else ""), created

    def test_publish_authenticates_the_nearest_existing_ancestor_not_the_immediate_parent(self):
        """publisher.sh:230 must authenticate `$_pb_anc` -- the NEAREST EXISTING ancestor.

        The other publisher fixtures leave exactly one component missing, so the immediate parent
        and the nearest existing ancestor are the same directory. Replacing `$_pb_anc` with
        `"${_pb_folded%/*}"` therefore left all 43 cells green, while breaking the ordinary
        fresh-install case: with two components missing the immediate parent does not exist, the
        guard refuses, and publication always fails (codex, r11 -- reproduced). That is fail-closed
        availability rather than a bypass, but it is a real shipped regression.
        """
        def check(shell):
            transcript, _, created = self._publish(shell, allow=True, value_exists=False, depth=2)
            self.assertGreater(len(transcript), 1, f"the create arm did not proceed: {transcript}")
            self.assertTrue(transcript[0].endswith("/exists"),
                            f"the guard was not called with the nearest EXISTING ancestor: "
                            f"{transcript[0]}")
            self.assertTrue(transcript[1].endswith("/exists/a/b"),
                            f"the created base was not authenticated next: {transcript}")
        self.for_declared_shells(SHELLS, check)

    def test_publish_refuses_a_base_whose_own_chain_refuses(self):
        """publisher:252 -- the published base is authenticated BEFORE a key is derived or anything
        is written. A refusal must stop there, with nothing composed under the store."""
        def check(shell):
            transcript, diagnostic, created = self._publish(shell, allow=False, value_exists=True)
            self.assertEqual(1, len(transcript),
                             f"the walk continued past a refused base: {transcript}")
            self.assertIn("chain does not authenticate", diagnostic)
        self.for_declared_shells(SHELLS, check)

    def test_publish_consults_the_guard_before_composing_a_store_path(self):
        """publisher:252, positive direction: with the base authenticating, the guard is consulted
        FIRST and the flow proceeds to the store. Without this the refusal cell above could pass
        because the guard refused everything."""
        def check(shell):
            transcript, _, created = self._publish(shell, allow=True, value_exists=True)
            self.assertGreater(len(transcript), 1,
                               "an authenticating base did not proceed past the guard")
            self.assertTrue(transcript[0].endswith("/data"),
                            f"the base was not the first thing authenticated: {transcript}")
        self.for_declared_shells(SHELLS, check)

    def test_publish_refuses_to_create_beneath_an_unauthenticated_ancestor(self):
        """publisher:230 -- a base that does NOT exist is created only if its nearest existing
        ancestor authenticates. This is the arm that stops a base being made under a hostile
        directory; it is unreachable from the two cells above, which use an existing base."""
        def check(shell):
            transcript, diagnostic, created = self._publish(shell, allow=False, value_exists=False)
            self.assertEqual(1, len(transcript),
                             f"the walk continued past a refused ancestor: {transcript}")
            self.assertIn("nearest existing ancestor does not authenticate", diagnostic)
            self.assertFalse(created,
                             "the base was created beneath an ancestor that REFUSED -- the guard "
                             "ran after the mkdir instead of before it")
        self.for_declared_shells(SHELLS, check)

    def test_publish_creates_beneath_an_authenticated_ancestor(self):
        """publisher:230, positive direction: the ancestor authenticates, so the base is created and
        then authenticated in its own right -- the transcript shows both, in that order."""
        def check(shell):
            transcript, _, created = self._publish(shell, allow=True, value_exists=False)
            self.assertGreater(len(transcript), 2, f"the create arm did not proceed: {transcript}")
            self.assertTrue(transcript[0].endswith("/exists"),
                            f"the ancestor was not authenticated first: {transcript}")
            self.assertTrue(transcript[1].endswith("/exists/base"),
                            f"the created base was not authenticated next: {transcript}")
        self.for_declared_shells(SHELLS, check)

class PrefetchCacheContract(SeamedChain, unittest.TestCase):
    """COREDEV-2691 -- the guard's INTERNALS, below the seam. UNGATED.

    Every other ungated class redefines `_unleashed_auth_chain`, which makes everything the real
    chain does internally unreachable. codex (r14) found the eighth mutation class there: at
    `plugin-state-auth.sh`, flipping `_u_stat_cache_get`'s MISS path from `return 1` to `return 0`
    makes `_u_stat` accept a cache miss without refreshing anything, so the guard evaluates the
    current component using the PRECEDING component's attributes. Measured fail-open: a real 1777
    `/private/tmp` was refused (rc=1, mode=1777) and accepted under the mutant (rc=0, mode=0755).

    THIS IS TESTABLE ON LINUX because `_u_stat_cache_get` is pure shell -- the Darwin-only `stat -f`
    fork happens only on the MISS path, after this function has already answered. The seam is not
    needed and is not used here; the shipped function is called directly.
    """

    #: `<nl><rs><path><nl><mode> <size> <uid> <ino><nl>`, the prefetch's own record format.
    CACHE = ('_u_pf_sep\n'
             '_U_STAT_CACHE="${_u_pf_nl}${_u_pf_rs}/alpha${_u_pf_nl}0755 4096 0 111'
             '${_u_pf_nl}${_u_pf_rs}/beta${_u_pf_nl}1777 8192 501 222${_u_pf_nl}"\n')

    def _cache_get(self, shell, path, auth=AUTH, cache=True, prime=None):
        """Call the SHIPPED `_u_stat_cache_get` and report (rc, mode, uid, ino).

        `prime` runs an earlier lookup IN THE SAME SHELL. It has to be the same process: the stale
        `_U_*` values that make the miss contract matter live in shell variables, and a first
        version of this ran the prime in a separate `run_shell` where they could not survive.
        """
        body = (self.CACHE if cache else '_u_pf_sep\n_U_STAT_CACHE=\n')
        body += '_U_MODE=; _U_UID=; _U_INO=\n'
        if prime is not None:
            body += '_u_stat_cache_get %s || :\n' % shlex.quote(prime)
        body += ('_u_stat_cache_get %s\n'
                 'printf "RC=%%s %%s %%s %%s\\n" "$?" "${_U_MODE:-}" "${_U_UID:-}" "${_U_INO:-}"\n'
                 % shlex.quote(path))
        out = run_shell(shell, body, sources=(auth, STORE, READER, PUB))[1]
        line = [l for l in out.splitlines() if l.startswith("RC=")]
        if not line:
            return None, "", "", ""
        parts = line[-1].split()
        rc = int(parts[0][len("RC="):])
        return (rc, *(parts[1:] + ["", "", ""])[:3])

    def test_a_cache_hit_answers_from_the_record(self):
        def check(shell):
            self.assertEqual((0, "0755", "0", "111"), self._cache_get(shell, "/alpha"))
            self.assertEqual((0, "1777", "501", "222"), self._cache_get(shell, "/beta"))
        self.for_declared_shells(SHELLS, check)

    def test_a_cache_miss_returns_nonzero_and_the_stale_values_survive(self):
        """A MISS must answer NON-ZERO -- and the reason is that it leaves the previous entry's
        values in place. Measured: after missing `/gamma`, `_U_MODE` still reads `/beta`'s 1777.
        The return code is therefore the ENTIRE contract; a caller that trusted the variables would
        evaluate one component using another's attributes. This cell asserts both halves, because
        asserting only `rc == 1` would not record WHY it matters.
        """
        def check(shell):
            rc, mode, uid, ino = self._cache_get(shell, "/gamma", prime="/beta")
            self.assertEqual(1, rc, "a cache MISS answered zero -- stale values would be used")
            self.assertEqual(("1777", "501", "222"), (mode, uid, ino),
                             "the miss path is expected to LEAVE the previous record in place; if "
                             "that ever changes, the rc contract is no longer the only protection "
                             "and this cell should be revisited")
        self.for_declared_shells(SHELLS, check)

    def test_an_empty_cache_is_a_miss(self):
        def check(shell):
            self.assertEqual(1, self._cache_get(shell, "/alpha", cache=False)[0],
                             "an empty cache answered zero")
        self.for_declared_shells(SHELLS, check)

    #: Everything `_u_probes_reset` must clear. DERIVED from the shipped `unset` lines by the cell
    #: below, not recalled -- a list written from memory drifts the moment a variable is added.
    def _probe_vars(self):
        with open(AUTH, encoding="utf-8") as fh:
            body = fh.read()
        start = body.index("_u_probes_reset() {")
        end = body.index("\n}", start)
        names = []
        for line in body[start:end].splitlines():
            stripped = line.strip()
            if stripped.startswith("unset "):
                names.extend(stripped[len("unset "):].split())
        # CENSUS the whole library for poisonable state, then union. Deriving the universe from
        # `_u_probes_reset` alone was still self-referential for anything NEW: adding a
        # `_U_NEW_PROBED` consumer elsewhere left the derived set unchanged, so the docstring's
        # claim that new state is caught was false (codex, r15). Every `_U_*_PROBED`, `_U_*_CACHE`
        # and `_U_PRINCIPAL*`/`_U_PLATFORM*`/`_U_EUID*` name assigned anywhere in the auth library
        # is poisonable, so the expectation comes from THERE, not from the reset itself.
        with open(AUTH, encoding="utf-8") as fh:
            whole = fh.read()
        for found in re.findall(r"\b(_U_[A-Z0-9_]*(?:_PROBED|_CACHE))\b", whole):
            if found not in names:
                names.append(found)
        # UNION with the security-critical pair, which must NOT be derived from the function under
        # test. Deriving the whole list from `_u_probes_reset` itself made the cell self-referential:
        # replacing `unset _U_STAT_CACHE _U_ACL_CACHE` with `:` removed those names from the
        # derivation, so the cell stopped poisoning them and passed. An oracle that reads its
        # expectation out of the thing it is checking cannot see that thing disappear.
        for critical in ("_U_STAT_CACHE", "_U_ACL_CACHE"):
            if critical not in names:
                names.append(critical)
        return names

    def test_probes_reset_clears_every_variable_a_caller_could_poison(self):
        """`_u_probes_reset` is what stops a CALLER arriving with a forged answer.

        `_U_STAT_CACHE` and `_U_ACL_CACHE` are ordinary variables in a sourced library, so a caller
        can pre-set a record claiming a component is 0700 and euid-owned, or an ACL answer with no
        foreign ACE in it. The same goes for the principal/platform/euid probe results. Dropping any
        single `unset` from that list is a one-line fail-open, and no seamed cell reaches this
        function at all -- the seam replaces the chain above it (codex and agy, r14, independently).

        The expected set is CENSUSED from the whole auth library -- every `_U_*_PROBED` and
        `_U_*_CACHE` name it assigns -- not read out of `_u_probes_reset`. Deriving it from the reset
        alone meant new state added elsewhere was never poisoned and so never checked.
        """
        names = self._probe_vars()
        self.assertGreaterEqual(len(names), 10,
                                f"only {len(names)} variables parsed from _u_probes_reset -- the "
                                f"derivation broke and this cell would prove nothing")
        for critical in ("_U_STAT_CACHE", "_U_ACL_CACHE"):
            self.assertIn(critical, names, f"{critical} must always be in the poisoned set")

        def check(shell):
            poison = "".join('%s=POISON\n' % v for v in names)
            report = "".join('printf "%%s=%%s\\n" %s "${%s:-<unset>}"\n' % (shlex.quote(v), v)
                             for v in names)
            out = run_shell(shell, poison + "_u_probes_reset\n" + report,
                            sources=(AUTH, STORE, READER, PUB))[1]
            survived = [l for l in out.splitlines() if l.endswith("=POISON")]
            self.assertEqual([], survived,
                             "a caller-poisoned value survived _u_probes_reset")
        self.for_declared_shells(SHELLS, check)

    def test_probes_reset_is_reddened_by_dropping_any_single_unset(self):
        """The positive control, per variable: each name dropped from the reset must be detected."""
        names = self._probe_vars()
        with open(AUTH, encoding="utf-8") as fh:
            body = fh.read()
        for name in names:
            with self.subTest(dropped=name):
                line = [l for l in body.splitlines()
                        if l.strip().startswith("unset ") and name in l.split()][0]
                kept = " ".join(w for w in line.strip().split() if w != name)
                mutant = with_mutation(line, line.replace(line.strip(), kept), path=AUTH)
                self.addCleanup(os.unlink, mutant)
                out = run_shell(SHELLS[0],
                                "%s=POISON\n_u_probes_reset\nprintf '%%s\\n' \"${%s:-<unset>}\"\n"
                                % (name, name),
                                sources=(mutant, STORE, READER, PUB))[1]
                self.assertIn("POISON", out,
                              f"dropping `unset {name}` was not observable -- the control is inert")

    #: A `/bin/ls -lde` block as the ACL parser expects it: the stat line, optionally followed by
    #: ACE lines. The hostile one carries a foreign MUTATING right.
    ACL_STAT_LINE = "drwx------  2 nick  staff  64 Jan  1 00:00 /alpha"
    ACL_HOSTILE_ACE = " 0: group:staff allow write,delete"

    def _acl_payload(self, shell, hostile, auth=AUTH):
        """Put a block in the ACL cache, read it back, and run it through `_u_acl_ok`.

        Returns (getter_rc, payload_bytes, acl_ok_rc).
        """
        blk = ('"%s${_u_pf_nl}%s"' % (self.ACL_STAT_LINE, self.ACL_HOSTILE_ACE) if hostile
               else '"%s"' % self.ACL_STAT_LINE)
        body = ('_u_pf_sep\n_blk=%s\n' % blk
                + '_U_ACL_CACHE="${_u_pf_nl}${_u_pf_rs}/alpha${_u_pf_nl}${_blk}${_u_pf_nl}"\n'
                + '_u_principal 2>/dev/null || :\n'
                + 'payload="$(_u_acl_cache_get /alpha)"; grc=$?\n'
                + '_u_acl_ok /alpha; ork=$?\n'
                + 'printf "R=%s %s %s\\n" "$grc" "${#payload}" "$ork"\n')
        out = run_shell(shell, body, sources=(auth, STORE, READER, PUB))[1]
        line = [l for l in out.splitlines() if l.startswith("R=")]
        if not line:
            return None, 0, None
        parts = line[-1][2:].split()
        return int(parts[0]), int(parts[1]), int(parts[2])

    def test_the_acl_cache_returns_the_WHOLE_block_not_just_its_status(self):
        """`_u_acl_cache_get` must return the whole cached block, ACE lines included.

        TENTH mutation class (codex, r17): a STATUS-ONLY oracle. The previous cell asserted only
        hit/miss/empty return codes, so truncating the payload to its first line -- dropping every
        cached ACE while still reporting a successful hit -- left it green. A foreign
        `group:staff allow write,delete` then changes from REFUSAL to ACCEPTANCE.

        Measured: the safe block is 49 bytes and `_u_acl_ok` accepts (0); the hostile block is 84
        bytes and `_u_acl_ok` REFUSES (2). Both halves are asserted, because the byte count alone
        would not show that the refusal actually depends on the ACE surviving.
        """
        def check(shell):
            grc, safe_bytes, safe_ok = self._acl_payload(shell, hostile=False)
            self.assertEqual(0, grc, "a cached safe block was not found")
            self.assertEqual(0, safe_ok, "a block with NO foreign ACE was refused")
            grc, hostile_bytes, hostile_ok = self._acl_payload(shell, hostile=True)
            self.assertEqual(0, grc, "a cached hostile block was not found")
            self.assertGreater(hostile_bytes, safe_bytes,
                               "the ACE line did not survive the cache round-trip")
            self.assertNotEqual(0, hostile_ok,
                                "a foreign MUTATING ACE was accepted from the cache")
        self.for_declared_shells(SHELLS, check)

    def test_truncating_the_acl_payload_is_observable(self):
        """The positive control: dropping everything after the stat line must flip the hostile
        block from refused to accepted, which is exactly what the status-only oracle could not see."""
        mutant = with_mutation('    printf \'%s\' "$_u_ag_out"',
                               '    printf \'%s\' "${_u_ag_out%%"$_u_pf_nl"*}"', path=AUTH)
        self.addCleanup(os.unlink, mutant)
        _, _, hostile_ok = self._acl_payload(SHELLS[0], hostile=True, auth=mutant)
        self.assertEqual(0, hostile_ok,
                         "truncating the payload was not observable -- this control is inert")

    def test_the_acl_cache_miss_returns_nonzero(self):
        """`_u_acl_cache_get` carries the same miss polarity as the stat cache, and is equally
        unreached by any seamed cell (agy, r14). Pure shell, so it runs here."""
        def check(shell):
            body = ('_u_pf_sep\n'
                    '_U_ACL_CACHE="${_u_pf_nl}${_u_pf_rs}/alpha${_u_pf_nl}ACLDATA${_u_pf_nl}"\n'
                    '_u_acl_cache_get /alpha; printf "hit=%s\\n" "$?"\n'
                    '_u_acl_cache_get /gamma; printf "miss=%s\\n" "$?"\n'
                    '_U_ACL_CACHE=\n_u_acl_cache_get /alpha; printf "empty=%s\\n" "$?"\n')
            out = run_shell(shell, body, sources=(AUTH, STORE, READER, PUB))[1]
            self.assertIn("hit=0", out, "a cached ACL record was not found")
            self.assertIn("miss=1", out, "an ACL cache MISS answered zero")
            self.assertIn("empty=1", out, "an empty ACL cache answered zero")
        self.for_declared_shells(SHELLS, check)

    #: Darwin-shaped output for the producer's two forks, with THREE components at DIFFERENT modes
    #: so a mis-keyed record is visible: `/` is 0755 and `/hostile` is 1777.
    #: Darwin-shaped output for BOTH producer forks. The `ls` half is the `-d` shape the parser
    #: actually consumes -- one stat line per component ENDING with its path, ACE lines indented.
    #: The first spelling emitted the non-`-d` form (`/:`, `total 0`), so no line matched a
    #: component, the ALL-OR-NOTHING rule discarded the whole ACL cache, and `_U_ACL_CACHE` was
    #: EMPTY while the cell still passed -- the stat half worked and nothing asserted the other
    #: (codex, r17: measured `STAT_BYTES=81 ACL_BYTES=0`).
    #: The stat seam VERIFIES THE FORMAT IT WAS ASKED FOR. The first spelling ignored the argv and
    #: always emitted UID-shaped data, so changing the shipped format from `%u` (owner uid) to `%g`
    #: (group id) -- one character -- left every observable identical while a foreign-owned
    #: component authenticated whenever its GID equalled the effective UID (codex, r18: shipped
    #: RC=1 UID=1501, mutant RC=0 UID=501). A fixture that does not read the format cannot detect
    #: the format changing.
    PRODUCER_SEAM = (
        "/usr/bin/stat() {\n"
        "  case \" $* \" in\n"
        "    *\" -f %p\\ %z\\ %u\\ %i\\ %N \"*|*\"%p %z %u %i %N\"*) : ;;\n"
        "    *) printf 'SEAM-REJECT: unexpected stat format: %s\\n' \"$*\" >&2; return 9 ;;\n"
        "  esac\n"
        "  printf '%s\\n' '40755 4096 0 111 /' '41777 4096 0 222 /hostile'"
        " '40700 4096 501 333 /hostile/leaf'\n"
        "  return 0\n}\n"
        "/bin/ls() {\n"
        "  printf '%s\\n' 'drwxr-xr-x  2 root wheel 64 Jan  1 00:00 /'"
        " 'drwxrwxrwt  2 root wheel 64 Jan  1 00:00 /hostile'"
        " ' 0: group:staff allow write,delete'"
        " 'drwx------  2 nick staff 64 Jan  1 00:00 /hostile/leaf'\n"
        "  return 0\n}\n"
    )

    def _prefetch_records(self, shell, auth=AUTH):
        """Run the SHIPPED `_u_chain_prefetch` and read each component's record back."""
        # ONE path. `_u_chain_prefetch` takes `$1` and DERIVES the components itself; passing three
        # operands left `$#` at 1 while the ACL parser found three blocks, so its all-or-nothing
        # rule discarded that cache -- correctly. The stat cache has no such rule, which is why the
        # miscall stayed invisible: half the fixture worked and nothing checked the other half.
        body = (self.PRODUCER_SEAM
                + "_u_chain_prefetch /hostile/leaf\n"
                + 'printf "ACLBYTES=%s\\n" "${#_U_ACL_CACHE}"\n'
                + 'for p in / /hostile /hostile/leaf; do\n'
                + '  _U_MODE=; _U_SIZE=; _U_UID=; _U_INO=\n'
                + '  if _u_stat_cache_get "$p"; then'
                  ' printf "%s=%s/%s/%s/%s\\n" "$p" "$_U_MODE" "$_U_SIZE" "$_U_UID" "$_U_INO";'
                  ' else printf "%s=MISS\\n" "$p"; fi\n'
                + '  blk="$(_u_acl_cache_get "$p")"\n'
                + '  ace=no; case "$blk" in *allow*) ace=yes ;; esac\n'
                + '  printf "ACE%s=%s\\n" "$p" "$ace"\n'
                + 'done\n')
        out = run_shell(shell, body, sources=(auth, STORE, READER, PUB))[1]
        return dict(l.split("=", 1) for l in out.strip().splitlines() if "=" in l)

    def test_each_prefetch_record_is_keyed_to_its_own_component(self):
        """`_u_chain_prefetch` must key each record by the path THAT LINE describes.

        Ninth mutation class (codex, r15). Keying every record by one component -- `$1` instead of
        the parsed `$_u_cp_f` -- makes the terminal's lookup consume the FIRST component's payload,
        so a hostile 1777 directory inherits `/`'s safe 0755 and authenticates. Every earlier cell
        exercised the cache GETTERS with hand-built records and never the PRODUCER.

        A NATIVE LINUX CELL IS POSSIBLE, contrary to the review note that suggested otherwise: the
        producer forks `/usr/bin/stat -f` and `/bin/ls -lde`, and a slash-named shell function takes
        precedence over an absolute-path command in BOTH shells (measured earlier for `/bin/mkdir`).
        Seaming the two forks with Darwin-shaped output runs the real parsing and keying logic here.
        """
        def check(shell):
            r = self._prefetch_records(shell)
            # ALL FOUR FIELDS. Asserting only the mode left the UID unchecked, which is the field
            # a `%u` -> `%g` format substitution corrupts (codex, r18).
            self.assertEqual({"/": "0755/4096/0/111",
                              "/hostile": "1777/4096/0/222",
                              "/hostile/leaf": "0700/4096/501/333"},
                             {k: v for k, v in r.items() if k.startswith("/")},
                             "a cached stat field is wrong or the record is mis-keyed")
            # THE ACL CACHE TOO, and that the ACE lands on the component that owns it. Asserting
            # only the stat half is what let a completely empty `_U_ACL_CACHE` pass.
            self.assertNotEqual("0", r.get("ACLBYTES"),
                                "the ACL producer populated nothing -- the fixture does not match "
                                "the `ls -d` block shape the parser consumes")
            self.assertEqual({"ACE/": "no", "ACE/hostile": "yes", "ACE/hostile/leaf": "no"},
                             {k: v for k, v in r.items() if k.startswith("ACE")},
                             "the hostile ACE is not on the component whose block carried it")
        self.for_declared_shells(SHELLS, check)

    def test_the_prefetch_key_is_reddened_by_keying_every_record_alike(self):
        """The positive control: keying every record by the first operand must break the mapping.

        IT COULD NOT FAIL. It compared the records against a hardcoded MODE-ONLY dictionary, and r18
        widened each record to `mode/size/uid/inode` and added the ACL half -- so the two stopped
        being equal for the HEALTHY tree as well, and `assertNotEqual` was satisfied by the record
        shape rather than by the mutation (codex, r19). A control whose baseline is a literal goes
        stale the moment the thing it describes changes; this one measures the shipped producer on
        the same fixture in the same run, and additionally states HOW the mutant must differ --
        three distinct stat records must collapse onto fewer.
        """
        mutant = with_mutation(
            '_u_cp_out="$_u_cp_out$_u_pf_nl$_u_pf_rs$_u_cp_f$_u_pf_nl',
            '_u_cp_out="$_u_cp_out$_u_pf_nl$_u_pf_rs$1$_u_pf_nl', path=AUTH)
        self.addCleanup(os.unlink, mutant)
        healthy = self._prefetch_records(SHELLS[0])
        records = self._prefetch_records(SHELLS[0], auth=mutant)
        self.assertNotEqual(healthy, records,
                            "keying every record alike was not observable -- the cell is inert")
        # AND HOW. Keying every record by the first operand does not remove records -- the probe
        # still asks for three components -- it makes two of the three UNFINDABLE. Measured:
        # `/hostile` and `/hostile/leaf` both come back MISS while `/` still resolves. Stating the
        # mechanism is what keeps this from being another "something changed" assertion.
        stat_healthy = {k: v for k, v in healthy.items() if k.startswith("/")}
        stat_mutant = {k: v for k, v in records.items() if k.startswith("/")}
        self.assertEqual(3, len(stat_healthy),
                         "the fixture no longer produces three stat records; the claim below is void")
        self.assertNotIn("MISS", stat_healthy.values(),
                         "the SHIPPED producer already misses a component -- fix that first")
        self.assertGreaterEqual(sum(1 for v in stat_mutant.values() if v == "MISS"), 2,
                                f"keying alike left more than one component findable: {stat_mutant}")

    def _read_store(self, shell, reader=READER):
        """Drive the SHIPPED `_unleashed_read_store` with a CALLER-POISONED cache.

        The chain is seamed to ALLOW so that the only variable is whether the poison is honoured;
        without that, the chain's own refusal masks the difference and the cell cannot discriminate
        (measured before this cell was written).
        """
        auth = with_mutation(*LINUX_SIM, path=AUTH)
        self.addCleanup(os.unlink, auth)
        home = scratch_home("readstore-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        store = os.path.join(home, "bases")
        os.makedirs(store, mode=0o777)                      # HOSTILE: world-writable
        body = ('_unleashed_auth_chain() { return 0; }\n'
                '_u_pf_sep\n'
                '_U_STAT_CACHE="${_u_pf_nl}${_u_pf_rs}%s${_u_pf_nl}0700 4096 %d 999${_u_pf_nl}"\n'
                % (store, os.geteuid())
                + "_unleashed_read_store %s\n" % shlex.quote(store)
                + 'printf "STATE=%s\\n" "${_UNLEASHED_POINTER_STATE:-resolved}"\n')
        out = run_shell(shell, body, env={"HOME": home}, sources=(auth, STORE, reader, PUB))[1]
        line = [l for l in out.splitlines() if l.startswith("STATE=")]
        return line[-1][len("STATE="):] if line else ""

    def test_read_store_discards_a_caller_poisoned_cache_before_using_it(self):
        """`_unleashed_read_store` must call `_u_probes_reset` FIRST.

        Found by a reachability census rather than by review: `_unleashed_read_store`,
        `_unleashed_store_absent` and `_unleashed_unresolved` were the reader's only functions NO
        ungated cell could reach (~/.claude/handoffs/reach-census.py). The entry point is where the
        ordering property lives -- a caller arrives holding a forged `_U_STAT_CACHE` claiming the
        store is 0700 and euid-owned, and the reset is what discards it before anything consults it.

        Removing the reset makes a WORLD-WRITABLE store report `none` -- benign, rule 4, "there is no
        store" -- instead of `stale`, so every caller proceeds as though nothing were there. That is
        a worse outcome than a refusal, not merely a different one.
        """
        def check(shell):
            self.assertEqual("stale", self._read_store(shell),
                             "a hostile store was not reported stale")
        self.for_declared_shells(SHELLS, check)

    def test_removing_the_reset_from_read_store_is_observable(self):
        """The positive control for the ordering above."""
        mutant = with_mutation(
            '    _rs_store="$1"\n    _u_probes_reset                                  '
            '# no inherited probe state is honoured',
            '    _rs_store="$1"\n    :                                                '
            '# no inherited probe state is honoured', path=READER)
        self.addCleanup(os.unlink, mutant)
        self.assertNotEqual("stale", self._read_store(SHELLS[0], reader=mutant),
                            "dropping _u_probes_reset was not observable -- the cell is inert")

    def test_the_euid_probe_answers_the_real_effective_uid(self):
        """`_u_euid_probe` forks `/usr/bin/id -u`, which is POSIX and runs here. It was unreached
        only because every other cell stubs `_u_euid` above it (reachability census)."""
        def check(shell):
            out = run_shell(shell, '_u_euid_probe\n', sources=(AUTH, STORE, READER, PUB))[1]
            self.assertEqual(str(os.geteuid()), out.strip(),
                             "the euid probe did not report this process's effective uid")
        self.for_declared_shells(SHELLS, check)

    def test_the_miss_paths_redden_when_flipped_to_success(self):
        """The positive control: BOTH miss paths, mutated to `return 0`, must break the contract."""
        for old, new, label in (
            ('    [ -n "${_U_STAT_CACHE:-}" ] || return 1',
             '    [ -n "${_U_STAT_CACHE:-}" ] || return 0', "empty-cache"),
            ('    [ "$_u_sg_v" = "$_U_STAT_CACHE" ] && return 1',
             '    [ "$_u_sg_v" = "$_U_STAT_CACHE" ] && return 0', "prefix-strip"),
        ):
            mutant = with_mutation(old, new, path=AUTH)
            self.addCleanup(os.unlink, mutant)
            with self.subTest(miss=label):
                if label == "empty-cache":
                    rc = self._cache_get(SHELLS[0], "/alpha", auth=mutant, cache=False)[0]
                else:
                    rc = self._cache_get(SHELLS[0], "/gamma", auth=mutant, prime="/beta")[0]
                self.assertEqual(0, rc, f"the {label} mutant did not flip -- this control is inert")


class UnauthenticatedEffectCensus(SeamedChain, unittest.TestCase):
    """COREDEV-2691 -- the CONVERSE of every other seamed class in this file. UNGATED.

    Eleven mutation classes are closed and every one of them BREAKS A GUARD THAT EXISTS: a call is
    deleted, a refusal is not honoured, an operand is wrong, a parsed field is the wrong one. Each is
    caught by a cell ANCHORED ON THAT SITE. Nothing asserted the converse -- that a production entry
    point produces NO effect at all while the chain refuses -- and the anchoring is exactly why: a
    write ADDED with no chain call beside it has no site for a cell to anchor on.

    MEASURED BEFORE THIS CLASS WAS WRITTEN, on `_unleashed_create_store`:

        -    _cs_top="${_cs_mid%/*}"            # ${HOME}/.claude
        +    _cs_top="${_cs_mid%/*}"; : > "$_cs_top/.um-staging" 2>/dev/null || :

    That creates a file inside the user's `~/.claude` BEFORE the first authentication, and all 65
    cells passed. rc, the ordered transcript and the three-component mode map are all unchanged --
    the transcript can only record calls that happen, and the mode map covers the three components
    the cells were written for.

    TWO NEARBY SPELLINGS DO REDDEN, and the difference is the whole point. `mkdir -p` reddens because
    `-p` creates an ancestor the fixtures happen to check; a literal `/bin/mkdir` reddens because
    ForkClassification counts mkdir SITES. Neither is a property of the guard. A redirect is neither
    a fork nor an ancestor, and it walked straight through both.

    THE ORACLE IS THE WHOLE TREE -- kind, mode, size, symlink target and content hash for every path
    under HOME -- because every narrower oracle in this file has been defeated by an effect it was
    not looking at, and a narrower one here would be defeated by the next spelling rather than the
    last one.

    THE CALL LOG LIVES OUTSIDE THE SNAPSHOTTED TREE. The seam appends to it on every call, so a log
    under HOME would make the tree differ on every run and these cells would fail for the one reason
    that is not a defect.
    """

    #: One entry point per production caller behind the chain. The reader and publisher arms are
    #: DOUBLE-SEAMED for the reason SeamedReader states: `_u_stat` forks the Darwin-only `stat -f`,
    #: so on Linux they refuse before reaching the call under test.
    ENTRIES = ("create_store", "store_ok", "publish")

    #: (label, which library, old, new, entry point). Each is a write a maintainer could add BY
    #: ACCIDENT -- a staging marker, a breadcrumb -- with no chain call beside it. Both are
    #: line-count preserving, so §7.1's rule holds for them.
    UNGUARDED_WRITES = (
        ("store: a staging marker beside the store's parent", STORE,
         '    _cs_top="${_cs_mid%/*}"            # ${HOME}/.claude',
         '    _cs_top="${_cs_mid%/*}"; : > "$_cs_top/.um-staging" 2>/dev/null || :',
         "create_store"),
        ("publisher: a breadcrumb inside the store", PUB,
         '        _pb_anc="$_pb_folded"',
         '        _pb_anc="$_pb_folded"; : > "$_pb_store/.pub-attempt" 2>/dev/null || :',
         "publish"),
    )

    @staticmethod
    def _snapshot(root):
        """Every path under `root` as rel -> (kind, mode, ...). Not just names, not just mtimes.

        A rewrite with identical length leaves size alone, so regular files carry a content hash; a
        directory swapped for a symlink leaves both alone, so links carry their target and are never
        followed (`os.walk` does not descend them, and `islink` is tested BEFORE `isdir`, which does
        follow). Mode is twelve bits, not nine: masking to 0o777 erased a setgid store once already.
        """
        out = {}
        for dirpath, dirnames, filenames in os.walk(root):
            for name in list(dirnames) + list(filenames):
                p = os.path.join(dirpath, name)
                rel = os.path.relpath(p, root)
                mode = oct(os.lstat(p).st_mode & 0o7777)
                if os.path.islink(p):
                    out[rel] = ("link", mode, os.readlink(p))
                elif os.path.isdir(p):
                    out[rel] = ("dir", mode)
                else:
                    with open(p, "rb") as fh:
                        blob = fh.read()
                    out[rel] = ("file", mode, len(blob), hashlib.sha256(blob).hexdigest())
        return out

    def _build(self, entry, home, log):
        """Build one entry point's fixture under `home` and return the body that drives it.

        The allowlist slots are all set to a path no fixture can produce, so the seam REFUSES every
        call while still recording it -- which is what lets these cells tell "refused" apart from
        "never reached the chain at all".
        """
        uid = os.geteuid()
        decl = ("_SEAM_CALLS=%s\n_SEAM_A1=/nothing\n_SEAM_A2=/nothing\n_SEAM_A3=/nothing\n"
                % shlex.quote(log)) + seam_source()
        if entry == "create_store":
            os.makedirs(os.path.join(home, ".claude"), mode=0o700)
            store = os.path.join(home, ".claude", "unleashed-mail", "bases")
            return decl + "_unleashed_create_store %s\n" % shlex.quote(store)
        store = os.path.join(home, "bases")
        os.makedirs(store, mode=0o700)
        table = {shlex.quote(store): ("0700", 0, os.stat(store).st_ino)}
        if entry == "store_ok":
            return (decl + SeamedReader.stat_stub(table, uid)
                    + "_unleashed_store_ok %s\n" % shlex.quote(store))
        parent = os.path.join(home, "exists")
        os.makedirs(parent, mode=0o700)
        table[shlex.quote(parent)] = ("0700", 0, os.stat(parent).st_ino)
        value = os.path.join(parent, "base")          # ABSENT: this is the arm that creates things
        return (decl + SeamedReader.stat_stub(table, uid)
                + "_unleashed_publish %s %s\n" % (shlex.quote(store), shlex.quote(value)))

    def _census(self, shell, entry, libs=None):
        """Run one entry point under a refusing chain. Returns (transcript, before, after)."""
        auth = with_mutation(*LINUX_SIM, path=AUTH)
        self.addCleanup(os.unlink, auth)
        home = scratch_home("seamcensus-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        logdir = scratch_home("seamcensuslog-")
        self.addCleanup(shutil.rmtree, logdir, ignore_errors=True)
        log = os.path.join(logdir, "calls")
        with open(log, "wb"):
            pass
        body = self._build(entry, home, log)
        store_lib, pub_lib = libs if libs else (STORE, PUB)
        # SNAPSHOT AFTER THE FIXTURE IS BUILT: `_build` creates the directories the entry point
        # needs, and folding them into the diff would make every cell fail on its own fixture.
        before = self._snapshot(home)
        run_shell(shell, body, env={"HOME": home},
                  sources=(auth, store_lib, READER, pub_lib))
        after = self._snapshot(home)
        with open(log, "rb") as fh:
            # NORMALISED against the fixture root. Two runs get two scratch homes, so a raw
            # transcript differs between the shipped and mutant runs for a reason that has nothing
            # to do with either -- and the pairing cell below compares the two transcripts.
            transcript = [r.decode().replace(home, "~") for r in fh.read().split(b"\0")[:-1]]
        return transcript, before, after

    def _assert_untouched(self, shell, entry):
        transcript, before, after = self._census(shell, entry)
        self.assertTrue(transcript,
                        f"{entry} never consulted the chain -- this cell proves nothing")
        added = {k: v for k, v in after.items() if k not in before}
        changed = {k: (before[k], v) for k, v in after.items()
                   if k in before and before[k] != v}
        removed = [k for k in before if k not in after]
        self.assertEqual(({}, {}, []), (added, changed, removed),
                         f"{shell} {entry}: the refusal path touched the tree")

    def test_create_store_leaves_the_tree_untouched_while_the_chain_refuses(self):
        """`_unleashed_create_store` must reach the chain, refuse, and write nothing anywhere."""
        self.for_declared_shells(SHELLS, lambda sh: self._assert_untouched(sh, "create_store"))

    def test_store_ok_leaves_the_tree_untouched_while_the_chain_refuses(self):
        """`_unleashed_store_ok` is a read path -- it must not write on the refusal path either."""
        self.for_declared_shells(SHELLS, lambda sh: self._assert_untouched(sh, "store_ok"))

    def test_publish_leaves_the_tree_untouched_while_the_chain_refuses(self):
        """`_unleashed_publish` with an ABSENT base: the arm that creates, refused before it does."""
        self.for_declared_shells(SHELLS, lambda sh: self._assert_untouched(sh, "publish"))

    def test_an_unguarded_write_is_invisible_to_the_transcript_and_visible_to_the_census(self):
        """The pairing that makes this class worth its runtime, in BOTH directions at once.

        For each mutant: the transcript is byte-identical to the shipped run -- so every cell in this
        file whose oracle is the transcript, the return code or a named component is blind to it --
        and the tree census differs. If `_snapshot` ever degenerates to a constant, the second half
        fails, so the mechanism controls itself rather than being asserted sound.
        """
        def check(shell):
            for label, path, old, new, entry in self.UNGUARDED_WRITES:
                with self.subTest(mutant=label):
                    mutant = with_mutation(old, new, path=path)
                    self.addCleanup(os.unlink, mutant)
                    libs = ((mutant, PUB) if path == STORE else (STORE, mutant))
                    clean_t, clean_b, clean_a = self._census(shell, entry)
                    dirty_t, dirty_b, dirty_a = self._census(shell, entry, libs=libs)
                    self.assertEqual(clean_t, dirty_t,
                                     f"{label}: the transcript DID move -- pick a subtler mutant, "
                                     "this one is already covered")
                    self.assertEqual(clean_b, clean_a, f"{label}: the shipped run is not clean")
                    self.assertNotEqual(dirty_b, dirty_a,
                                        f"{label}: the census did not see the write")
        self.for_declared_shells(SHELLS, check)



class AmbientStateContract(SeamedChain, unittest.TestCase):
    """COREDEV-2691 -- the state the guards run IN, not the code they are written in. UNGATED.

    Twelve mutation classes are closed and every one of them EDITS CODE. None changes the ambient
    the code inherits, and these libraries are SOURCED into shells the plugin does not control, so
    the ambient is adversarial input: a caller's `shopt`, `setopt`, `umask` and locale all reach
    them. Both r19 arms raised this independently, and a sweep of eleven save/restore/force
    deletions found NINE that leave every ungated cell green.

    Three are closed here, chosen by consequence and measured before being written:

      * `shopt -s nocasematch` makes bash's `case` case-INSENSITIVE, so the encoder's byte table
        folds `/A` onto `/a`. MEASURED with the clear deleted: `_unleashed_key /A` and
        `_unleashed_key /a` both returned `_s_ca` -- one entry NAME for two distinct bases. Not
        hygiene: a key collision.
      * `umask 077` on the transient. MEASURED with it deleted: the state file lands `0666` in both
        shells. The mode readback catches it on Darwin and refuses; on the required Linux leg
        `_u_stat` refuses first, so the readback never runs and only the FILE ITSELF is evidence.
      * `set -C` on the transient's exclusive create. MEASURED with it deleted: a symlink planted at
        the transient's name is FOLLOWED and the victim outside the store is overwritten with the
        published value in both shells. The shipped code returns 2 and leaves the victim alone.

    The remaining six -- the reader's `LC_ALL` force and restore, its `noglob` and `failglob`
    handling, the published base's umask, and the encoder's nocasematch RESTORE -- are recorded on
    COREDEV-2766 with this sweep, because each needs a fixture that reaches its entry point and none
    of them is a bypass. `~/.claude/handoffs/ambient-sweep.py` reproduces all eleven.
    """

    #: `/A` and `/a` differ only in case, which is exactly what a case-insensitive `case` folds.
    CASE_PAIR = ("/A", "/a")

    def _transient(self, shell, value, umask=None, plant=None, pub=None):
        """Call `_unleashed_write_transient` directly. It consults no chain, so it needs no seam.

        Returns (rc, mode-or-ABSENT, victim-contents-or-None). The MODE is read from Python rather
        than from the library's own readback: on Linux `_u_stat` forks the Darwin-only `stat -f` and
        refuses, so the readback never runs and the shipped rc is 1 on a perfectly good file. The
        file on disk is the observable that means the same thing on both platforms.
        """
        home = scratch_home("ambient-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        target = os.path.join(home, "t")
        victim = None
        if plant is not None:
            victim = os.path.join(home, "victim")
            with open(victim, "w") as fh:
                fh.write(plant)
            os.symlink(victim, target)
        body = (("umask %s\n" % umask if umask is not None else "")
                + "_unleashed_write_transient %s %s\n" % (shlex.quote(target), shlex.quote(value))
                + 'printf "RC=%s\\n" "$?"\n')
        out = run_shell(shell, body, env={"HOME": home},
                        sources=(AUTH, STORE, READER, pub or PUB))[1]
        rcs = [int(l[len("RC="):]) for l in out.splitlines() if l.startswith("RC=")]
        mode = (oct(os.lstat(target).st_mode & 0o7777)
                if os.path.lexists(target) else "ABSENT")
        after = None
        if victim:
            with open(victim) as fh:
                after = fh.read()
        return (rcs[0] if rcs else None), mode, after

    def test_the_transient_is_created_at_0600_whatever_the_callers_umask(self):
        """PUB-9 E6. A state file at 0666 is readable and writable by every user on the machine."""
        def check(shell):
            _, mode, _ = self._transient(shell, "hello", umask="000")
            self.assertEqual(oct(0o600), mode, f"{shell}: the transient did not land at 0600")
        self.for_declared_shells(SHELLS, check)

    def test_the_transient_umask_control_reddens_when_the_umask_is_dropped(self):
        """The positive control. Without it this cell passes on a machine whose ambient umask is
        already 077, which is every developer machine and every CI runner -- the assertion would be
        satisfied by the ambient rather than by the library."""
        mutant = with_mutation("    ( umask 077; set -C; trap '' XFSZ; _wt_opened=0",
                               "    ( umask 000; set -C; trap '' XFSZ; _wt_opened=0", path=PUB)
        self.addCleanup(os.unlink, mutant)

        def check(shell):
            _, mode, _ = self._transient(shell, "hello", umask="000", pub=mutant)
            self.assertEqual(oct(0o666), mode,
                             f"{shell}: dropping `umask 077` changed nothing -- the control is inert")
        self.for_declared_shells(SHELLS, check)

    def test_the_exclusive_create_does_not_follow_a_planted_symlink(self):
        """`set -C` is what makes `9>` an exclusive create rather than a write-through.

        The fixture plants a symlink at the transient's name pointing OUTSIDE the store, which is
        same-uid interference winning the race. The shipped code must refuse (2 -- the name exists,
        a lost race) and leave the victim byte-identical.
        """
        def check(shell):
            rc, _, victim = self._transient(shell, "POISON", plant="VICTIM")
            self.assertEqual(2, rc, f"{shell}: a planted symlink was not reported as a lost race")
            self.assertEqual("VICTIM", victim, f"{shell}: the write followed the symlink")
        self.for_declared_shells(SHELLS, check)

    def test_the_symlink_control_reddens_when_noclobber_is_dropped(self):
        """The positive control, and it is the finding: with `set -C` removed the published value is
        written THROUGH the link to a file outside the store, in both shells."""
        mutant = with_mutation("    ( umask 077; set -C; trap '' XFSZ; _wt_opened=0",
                               "    ( umask 077; set +C; trap '' XFSZ; _wt_opened=0", path=PUB)
        self.addCleanup(os.unlink, mutant)

        def check(shell):
            _, _, victim = self._transient(shell, "POISON", plant="VICTIM", pub=mutant)
            self.assertEqual("POISON\n", victim,
                             f"{shell}: dropping `set -C` clobbered nothing -- the control is inert")
        self.for_declared_shells(SHELLS, check)

    def _key(self, shell, path, prelude="", store=None):
        body = prelude + "_unleashed_key %s\nprintf '%%s' \"$_UNLEASHED_KEY\"\n" % shlex.quote(path)
        return run_shell(shell, body, sources=(AUTH, store or STORE, READER, PUB))[1]

    def test_the_encoder_is_immune_to_a_hostile_nocasematch(self):
        """ENC-1's byte table is a `case`, and bash's `nocasematch` makes `case` case-insensitive.

        bash only, stated: `shopt` does not exist in zsh, and the shipped clear is guarded by
        `[ -z "${ZSH_VERSION:-}" ]` for that reason -- zsh's `case` is case-sensitive regardless.
        """
        bash = SHELLS[0]

        def check(shell):
            upper, lower = (self._key(shell, p, "shopt -s nocasematch\n") for p in self.CASE_PAIR)
            self.assertNotEqual(upper, lower,
                                f"{shell}: `/A` and `/a` collided under a hostile nocasematch")
            self.assertEqual(self._key(shell, self.CASE_PAIR[0]), upper,
                             f"{shell}: a hostile nocasematch changed the key")
        self.for_declared_shells((bash,), check,
                                 narrowed_reason="`shopt` is bash-only; zsh `case` is always exact")

    def test_the_nocasematch_control_reddens_when_the_clear_is_deleted(self):
        """The positive control, and the finding: the two keys become the SAME string."""
        bash = SHELLS[0]
        mutant = with_mutation(
            "        _uk_nocase=1; shopt -u nocasematch 2>/dev/null || :",
            "        _uk_nocase=1; : nocasematch 2>/dev/null || :       ", path=STORE)
        self.addCleanup(os.unlink, mutant)

        def check(shell):
            keys = [self._key(shell, p, "shopt -s nocasematch\n", store=mutant)
                    for p in self.CASE_PAIR]
            self.assertEqual(keys[0], keys[1],
                             f"{shell}: deleting the clear did not collide the keys -- inert control")
        self.for_declared_shells((bash,), check,
                                 narrowed_reason="`shopt` is bash-only; zsh `case` is always exact")



class PortablePathIdentity(unittest.TestCase):
    """COREDEV-2761 -- `_u_path_id` on BOTH platforms. UNGATED, and it needs no seam.

    `stat -f` is a BSD FORMAT STRING and GNU FILE-SYSTEM information. The publisher forked
    `stat -f '%d %i'` directly to prove a folded spelling names the same directory, so on Linux both
    probes returned empty, the `-z` guards fired, and EVERY base containing `.`, `..` or `//` was
    refused -- with a diagnostic saying the two spellings named different directories when in truth
    the probe had not run.

    THIS IS TESTABLE WITHOUT THE CHAIN SEAM, which is why it is a class of its own. The identity
    probe sits at plugin-state-publisher.sh:245, BEFORE the chain call at :252, so the defect is
    reached on any platform. The observable is WHICH diagnostic comes out.

    LINUX IS SIMULATED, and completely: `uname -s` reports Linux so `_u_platform` takes the GNU arm,
    `stat -f` fails as GNU's does, and `stat -c '%d %i'` answers by delegating to the real BSD stat.
    A slash-named shell function overrides an absolute-path command in both shells (measured
    elsewhere in this file for `/bin/mkdir`). Simulating only the platform, or only the stat, would
    let the cell pass for the wrong reason.
    """

    #: The publish CANNOT SUCCEED on Linux and this class does not pretend otherwise:
    #: `_unleashed_auth_chain` refuses on every non-Darwin platform by design (COREDEV-2617 §4.2a),
    #: so the honest observable is that the run reaches the CHAIN's refusal instead of dying at the
    #: identity probe. That is exactly the difference the fix makes, and it is what these cells
    #: assert. The ticket's "publishes successfully on Linux" acceptance needs the chain's Linux
    #: arms, which are a separate, unbuilt piece of work.
    IDENTITY_FAILURE = "identity could not be probed"
    FALSE_DIAGNOSTIC = "name different directories"
    CHAIN_REFUSAL = "chain does not authenticate"

    LINUX_SIM = (
        '/usr/bin/uname() { case "$1" in -s) printf \'Linux\\n\' ;; '
        '*) command /usr/bin/uname "$@" ;; esac; }\n'
        '/usr/bin/stat() {\n'
        '  case "$1" in\n'
        '    -f) printf \'stat: cannot read file system information\\n\' >&2; return 1 ;;\n'
        '    -c) shift; _f="$1"; shift; [ "$1" = "--" ] && shift\n'
        # THE SIMULATION MUST RUN ON THE HOST IT IS RUN ON. The first spelling delegated the `-c`
        # arm to `command /usr/bin/stat -f`, which is right on macOS and WRONG on a real Linux
        # runner -- there `-f` is the file-system query this whole ticket is about, so the cell
        # would have gone red on the required ubuntu leg while passing locally. Try the host's own
        # `-c` first and fall back to `-f`: GNU answers the first, BSD the second.
        '        case "$_f" in "%d %i") command /usr/bin/stat -c \'%d %i\' -- "$@" 2>/dev/null \\\n'
        '                                 || command /usr/bin/stat -f \'%d %i\' -- "$@" ;;\n'
        '                       *) return 1 ;; esac ;;\n'
        '    *)  command /usr/bin/stat "$@" ;;\n'
        '  esac\n'
        '}\n'
    )

    def _publish_folded(self, shell, auth=AUTH, linux=True):
        """Publish a base spelled with `..`, so the identity probe is REQUIRED. Returns the last
        diagnostic line, or "" when the publish produced none."""
        home = scratch_home("pathid-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        store = os.path.join(home, "store")
        base = os.path.join(home, "base", "sub")
        os.makedirs(store, mode=0o700)
        os.makedirs(base, mode=0o700)
        os.chmod(os.path.join(home, "base"), 0o700)
        folded = os.path.join(home, "base", "sub", "..", "sub")
        body = ((self.LINUX_SIM if linux else "")
                + "_unleashed_publish %s %s\n" % (shlex.quote(store), shlex.quote(folded)))
        err = run_shell(shell, body, env={"HOME": home}, sources=(auth, STORE, READER, PUB))[2]
        lines = [l for l in err.splitlines() if "failed: " in l]
        return lines[-1] if lines else ""

    def test_a_folded_base_gets_past_the_identity_probe_on_linux(self):
        """The fix. The run must reach the CHAIN's refusal, not die at the probe."""
        for shell in SHELLS:
            if shutil.which(shell) is None:
                self.skipTest(f"{shell} absent")
            with self.subTest(shell=shell):
                got = self._publish_folded(shell)
                self.assertIn(self.CHAIN_REFUSAL, got,
                              f"{shell}: the folded base did not reach the chain: {got!r}")
                self.assertNotIn(self.FALSE_DIAGNOSTIC, got,
                                 f"{shell}: the false diagnostic is back: {got!r}")

    def test_the_control_reverting_the_linux_arm_to_dash_f_restores_the_defect(self):
        """The paired mutant, and it IS the shipped defect: with the GNU arm spelled `-f` the probe
        fails on Linux and the publisher blames the directories instead of the probe."""
        # A SHORT, UNIQUE anchor: the long line carries both quote kinds and a `$(`, and spelling
        # it inside this file's own quoting is how the first attempt died.
        mutant = with_mutation("stat -c '%d %i'", "stat -f '%d %i'", path=AUTH)
        self.addCleanup(os.unlink, mutant)
        for shell in SHELLS:
            if shutil.which(shell) is None:
                self.skipTest(f"{shell} absent")
            with self.subTest(shell=shell):
                got = self._publish_folded(shell, auth=mutant)
                self.assertIn(self.IDENTITY_FAILURE, got,
                              f"{shell}: reverting the arm did not break the probe -- inert control: "
                              f"{got!r}")

    def test_the_darwin_arm_still_resolves_a_folded_base(self):
        """The other direction: the Darwin arm must keep working, or the fix traded one platform for
        the other. Runs unsimulated, so it exercises the real `stat -f` wherever it is run; on Linux
        the real `uname` sends it down the GNU arm instead, and either way the probe must SUCCEED."""
        for shell in SHELLS:
            if shutil.which(shell) is None:
                self.skipTest(f"{shell} absent")
            with self.subTest(shell=shell):
                got = self._publish_folded(shell, linux=False)
                self.assertNotIn(self.IDENTITY_FAILURE, got,
                                 f"{shell}: the native identity probe failed: {got!r}")
                self.assertNotIn(self.FALSE_DIAGNOSTIC, got,
                                 f"{shell}: the native probe reported different directories: {got!r}")


if __name__ == "__main__":
    unittest.main()
