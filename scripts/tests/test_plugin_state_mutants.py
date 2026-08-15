#!/usr/bin/env python3
"""COREDEV-2617 — the mutant table, EXECUTED.

Each test builds one row's mutation against the SHIPPED shell (by exact substring, or through a
step-3f seam), runs the row's fixture against the shipped build and the mutant build in BOTH
bash 3.2.57 and zsh 5.9, and asserts the outcomes DIFFER. A row whose two builds agree cannot fail
and proves nothing — four such rows were found while writing these and are recorded in the plan
campaign's findings file rather than faked here.

Assembled from six parallel drafting agents; every row carries the run evidence its drafter measured,
and THIS suite's own run is the gate — the evidence informed assembly, it is not the verification.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from test_plugin_state_store import (run_shell, with_mutation, AUTH, STORE, READER, PUB,
                                     SHELLS, DARWIN, scratch_home)

# ==================================================================================================
# Chunk 1
# ==================================================================================================
# COREDEV-2617 mutant-table rows, chunk 1 — EXECUTED mutation tests.
#
# Every covered-new row here was RUN: the shipped build and a with_mutation/seam build, in BOTH
# /bin/bash and /bin/zsh, and the outcomes differ. Fixtures follow test_plugin_state_store.py's
# conventions (scratch HOME under ~/.claude so the chain authenticates; %b for multi-line answers;
# every expansion quoted).

import os
import shutil
import stat as statmod
import subprocess
import tempfile
import unittest


#: Same shape as ReaderOrderedRules.ENTRY — a well-formed entry: encoded name, one line, 0600.
ENTRY = ('_unleashed_key "{t}"; printf "%s\\n" "{t}" > "{s}/base.$_UNLEASHED_KEY"; '
         'chmod 600 "{s}/base.$_UNLEASHED_KEY"')

#: The reset the briefing requires between publisher/reader calls in one body.
RESET_C1 = ('unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE '
         '_UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL\n')

#: Print the store-level tuple N6-6 requires the oracle to name.
TUPLE_C1 = 'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"'


def seam(answer):
    """The enumerator-output seam, spelled exactly as the existing suite spells it."""
    return '_u_acl_enumerate() { printf %b ' + repr(answer).replace("'", '"') + '; }\n'


@unittest.skipUnless(DARWIN, "every row here drives the Darwin chain/ACL arm or the Darwin store")
class RowsChunk1(unittest.TestCase):
    """Rows 1, 7, 14, 23, 33, 46, 55, 61, 67, 79, 88, 95, 102, 109, 116, 123, 129, 141, 148."""

    def setUp(self):
        # A scratch HOME under ~/.claude so every chain authenticates (§7 step 3f(i)).
        self.home = scratch_home("rows1.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.base = os.path.join(self.home, "base")
        os.makedirs(self.base)
        os.chmod(self.base, 0o700)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    # ── shared machinery ──────────────────────────────────────────────────────────────────────────

    def _mkstore(self):
        """Create the store chain at 0700 from Python, as ST-2 would leave it."""
        for d in (os.path.join(self.home, ".claude"),
                  os.path.join(self.home, ".claude", "unleashed-mail"), self.store):
            os.makedirs(d, exist_ok=True)
            os.chmod(d, 0o700)

    def _fresh(self):
        shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
        self._mkstore()

    def _sources(self, mutant, mutated):
        """The canonical source list with exactly one file replaced by its mutant."""
        return tuple(mutant if s is mutated else s for s in (AUTH, STORE, READER, PUB))

    def _other_target(self, name="t2"):
        t2 = os.path.join(self.home, name)
        os.makedirs(t2, exist_ok=True)
        os.chmod(t2, 0o700)
        return t2

    # ── row 1 ─────────────────────────────────────────────────────────────────────────────────────

    def test_row_001_publish_always_rewrites_on_the_current_path(self):
        """mtime unchanged on a no-change second run — dropping PUB-7's complete-predicate skip rewrites it."""
        # The mutant drops the write-or-skip decision entirely: every publish takes the write path.
        # PUB-4/row 1: the `current` path performs ZERO writes, proved by mtime_ns, because
        # "reports current" alone is satisfiable by a publisher that rewrites an identical file.
        mutant = with_mutation(
            '    if _unleashed_auth_entry "$_pb_entry"; then\n        _pb_wrote=0\n    else',
            '    if false; then\n        _pb_wrote=0\n    else', path=PUB)
        try:
            for shell in SHELLS:
                for arm, srcs, want_state, want_same in (
                        ("shipped", (AUTH, STORE, READER, PUB), "current", True),
                        ("mutant", self._sources(mutant, PUB), "created", False)):
                    shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                    # The second publish runs in a FRESH process, as a real hook would.
                    rc, out, err = run_shell(
                        shell, f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null', sources=srcs)
                    entries = [f for f in os.listdir(self.store) if f.startswith("base.")]
                    self.assertEqual(1, len(entries), f"{shell}: first publish must leave one entry")
                    entry = os.path.join(self.store, entries[0])
                    before = os.stat(entry).st_mtime_ns
                    rc, out, err = run_shell(
                        shell,
                        f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                        'printf "%s" "$_UNLEASHED_POINTER_STATE"', sources=srcs)
                    self.assertEqual(want_state, out, f"{shell} {arm}: {err}")
                    same = before == os.stat(entry).st_mtime_ns
                    self.assertEqual(want_same, same,
                                     f"{shell} {arm}: mtime same={same}, want same={want_same}")
        finally:
            os.unlink(mutant)

    # ── rows 7 / 23 — foreign-uid fixtures through a delegating stat wrapper ──────────────────────
    #
    # An unprivileged test cannot chown a file to another uid, so the fixture presents the foreign
    # owner through P-2's probe result: the wrapper DELEGATES to the shipped _u_stat (copied under a
    # new name, not paraphrased) and overrides _U_UID for exactly one path. The MUTATION under test
    # is always a with_mutation on the shipped file; both arms run the identical fixture, and the
    # mutant arm authenticating both entries through the same wrapper is the proof the wrapper
    # itself does not refuse anything.

    WRAP = ('if [ -n "${{ZSH_VERSION:-}}" ]; then functions -c _u_stat _u_stat_real; '
            'else eval "$(declare -f _u_stat | /usr/bin/sed \'1s/_u_stat/_u_stat_real/\')"; fi\n'
            '_u_stat() {{ _u_stat_real "$@" || return 1; '
            '[ "$1" = "{p}" ] && _U_UID=0; return 0; }}\n')

    def test_row_007_pointer_owner_check_is_load_bearing(self):
        """An entry owned by another uid ⇒ stale + one diagnostic, and a conforming sibling does not win."""
        mutant = with_mutation(
            '    [ "$_U_MODE" = 0600 ] || return 1                # TWELVE bits: `chmod 4600` must not pass as 0600\n'
            '    [ "$_U_UID" = "${EUID:-$(/usr/bin/id -u)}" ] || return 1\n',
            '    [ "$_U_MODE" = 0600 ] || return 1                # TWELVE bits: `chmod 4600` must not pass as 0600\n',
            path=READER)
        try:
            t2 = self._other_target()
            for shell in SHELLS:
                for srcs, want, want_diag in (((AUTH, STORE, READER, PUB), "0 unresolved stale", 1),
                                              (self._sources(mutant, READER), "0 unresolved conflict", 1)):
                    self._fresh()
                    body = (ENTRY.format(t=self.base, s=self.store) + '\n'
                            f'_row7_foreign="{self.store}/base.$_UNLEASHED_KEY"\n'
                            + ENTRY.format(t=t2, s=self.store) + '\n'
                            + self.WRAP.format(p='$_row7_foreign')
                            + RESET_C1
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(want_diag, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    def test_row_023_target_owner_check_is_load_bearing(self):
        """A target owned by another uid ⇒ stale + one diagnostic, and a conforming sibling does not win."""
        mutant = with_mutation(
            '            [ "$_U_UID" = "${EUID:-$(/usr/bin/id -u)}" ] || return 1\n',
            '            :\n', path=AUTH)
        try:
            t1 = os.path.join(self.home, "foreign_t")
            os.makedirs(t1)
            os.chmod(t1, 0o700)
            t2 = self._other_target()
            for shell in SHELLS:
                for srcs, want in (((AUTH, STORE, READER, PUB), "0 unresolved stale"),
                                   (self._sources(mutant, AUTH), "0 unresolved conflict")):
                    self._fresh()
                    body = (ENTRY.format(t=t1, s=self.store) + '\n'
                            + ENTRY.format(t=t2, s=self.store) + '\n'
                            + self.WRAP.format(p=t1)
                            + RESET_C1
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(1, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 14 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_014_symlinked_target_ancestor_refuses(self):
        """A symlinked target ancestor ⇒ stale + one diagnostic, and a conforming sibling does not win."""
        # PCH-1: every component of the target chain must not be a symbolic link. The mutant accepts
        # one; lstat's own mode/owner clauses do NOT catch it (a macOS symlink is 0755 and ours), so
        # without this clause the entry authenticates and the store resolves through the link.
        mutant = with_mutation(
            '        [ -L "$_u_ac_c" ] && return 1                   # never a symbolic link\n',
            '        :\n', path=AUTH)
        try:
            real = os.path.join(self.home, "real")
            tgt = os.path.join(real, "tgt")
            os.makedirs(tgt)
            os.chmod(real, 0o700)
            os.chmod(tgt, 0o700)
            link = os.path.join(self.home, "link")
            os.symlink(real, link)
            linked_tgt = os.path.join(link, "tgt")     # the entry's value: an ancestor is a symlink
            t2 = self._other_target()
            for shell in SHELLS:
                for srcs, want in (((AUTH, STORE, READER, PUB), "0 unresolved stale"),
                                   (self._sources(mutant, AUTH), "0 unresolved conflict")):
                    self._fresh()
                    body = (ENTRY.format(t=linked_tgt, s=self.store) + '\n'
                            + ENTRY.format(t=t2, s=self.store) + '\n'
                            + RESET_C1
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(1, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 33 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_033_off_home_target_beneath_0777_ancestor_refuses(self):
        """An off-${HOME} target beneath a 0777 ancestor ⇒ stale + one diagnostic; sibling does not win."""
        # What refuses an off-HOME target is the CHAIN CONDITION, not a HOME-membership test:
        # /private/tmp is 1777, so the group/other-writable clauses refuse it. The mutant drops both
        # clauses and the chain then authenticates straight through the world-writable intermediate.
        mutant = with_mutation(
            '        case "$_U_MODE" in *[2367]?) return 1 ;; esac   # group-writable\n'
            '        case "$_U_MODE" in *[2367])  return 1 ;; esac   # other-writable\n',
            '        :\n', path=AUTH)
        t_off = tempfile.mkdtemp(prefix="row33.", dir="/private/tmp")
        os.chmod(t_off, 0o700)
        self.addCleanup(shutil.rmtree, t_off, True)
        try:
            t2 = self._other_target()
            for shell in SHELLS:
                for srcs, want in (((AUTH, STORE, READER, PUB), "0 unresolved stale"),
                                   (self._sources(mutant, AUTH), "0 unresolved conflict")):
                    self._fresh()
                    body = (ENTRY.format(t=t_off, s=self.store) + '\n'
                            + ENTRY.format(t=t2, s=self.store) + '\n'
                            + RESET_C1
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(1, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 46 ────────────────────────────────────────────────────────────────────────────────────

    FAMILY = ("paths.sh", "context.sh", "log.sh", "marker.sh", "agent-env-bridge.sh")

    def test_row_046_no_nomatch_guards_the_scan_in_all_five_family_files(self):
        """An empty store does not abort the sourcing shell mid-file, in all five family arms (zsh)."""
        # The guard lives once, in the reader every family file loads — but the OBLIGATION is on the
        # five sourcing arms, so each is sourced against a shadow lib dir holding byte-identical
        # copies (mutant arm: the reader with `setopt local_options no_nomatch` dropped). Measured:
        # a zsh glob failure aborts execution up to the source boundary, so the family file's later
        # protocol assignments never run — the discriminator is the UNSET tuple, bash unaffected.
        mutant = with_mutation('        setopt local_options no_nomatch\n', '        :\n',
                               path=READER)
        lib = os.path.dirname(READER)
        try:
            shadows = {}
            for arm, reader in (("shipped", READER), ("mutant", mutant)):
                root = os.path.join(self.home, "shadow-" + arm)
                sl = os.path.join(root, "scripts", "lib")
                os.makedirs(sl)
                for f in ("plugin-state-auth.sh", "plugin-state-store.sh",
                          "plugin-state-publisher.sh") + self.FAMILY:
                    shutil.copy(os.path.join(lib, f), os.path.join(sl, f))
                shutil.copy(reader, os.path.join(sl, "plugin-state-reader.sh"))
                shadows[arm] = root
            self._mkstore()                                 # the EMPTY store fixture
            for shell in SHELLS:
                for arm, root in shadows.items():
                    for fam in self.FAMILY:
                        f = os.path.join(root, "scripts", "lib", fam)
                        src = (f'. "{f}" "" "{root}"' if fam == "agent-env-bridge.sh"
                               else f'. "{f}"')
                        body = ('unset CLAUDE_PLUGIN_DATA\n'
                                + src + '\n'
                                'printf "%s %s" "${_UNLEASHED_BASE_OK-UNSET}" '
                                '"${_UNLEASHED_POINTER_STATE-UNSET}"')
                        rc, out, err = run_shell(shell, body, env={"HOME": self.home},
                                                 sources=())
                        if arm == "mutant" and shell == "/bin/zsh":
                            self.assertEqual("UNSET UNSET", out,
                                             f"{shell} {fam}: the CONTROL did not fail")
                            self.assertIn("no matches found", err, f"{shell} {fam}: {err!r}")
                        else:
                            self.assertEqual("0 none", out, f"{shell} {arm} {fam}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 55 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_055_ignoring_acls_resolves_what_the_arm_refuses(self):
        """A refused ACE (another principal, rights outside ACL-2's seven) ⇒ stale; read-only allow resolves."""
        mutant = with_mutation('        _u_acl_ok "$_u_ac_c" || return 1\n', '        :\n',
                               path=AUTH)
        hostile = "drwx------@ 2 n s 64 d\n 0: group:staff allow add_file,delete\n"
        readonly = "drwx------@ 2 n s 64 d\n 0: group:staff allow read,list,search\n"
        try:
            for shell in SHELLS:
                # The row's own control (its "row 90" clause): a read-only allow RESOLVES on the
                # SHIPPED arm, so the refusal below is the ACE's rights, not the seam.
                self._fresh()
                body = (ENTRY.format(t=self.base, s=self.store) + '\n' + RESET_C1
                        + seam(readonly)
                        + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + TUPLE_C1)
                rc, out, err = run_shell(shell, body)
                self.assertEqual("1 pointer none", out, f"{shell}: read-only allow must resolve")
                for srcs, want, want_diag in (((AUTH, STORE, READER, PUB), "0 unresolved stale", 1),
                                              (self._sources(mutant, AUTH), "1 pointer none", 0)):
                    self._fresh()
                    body = (ENTRY.format(t=self.base, s=self.store) + '\n' + RESET_C1
                            + seam(hostile)
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(want_diag, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 61 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_061_rule_1_outranks_rule_3_good_beside_malformed(self):
        """One valid PLUS one malformed entry ⇒ stale (not a resolution, not conflict) + one diagnostic."""
        # The mutant makes rule 1 fire only when NOTHING authenticates — i.e. a good entry wins over
        # a malformed sibling, which RD-3's order forbids: one bad entry refuses the whole store.
        mutant = with_mutation(
            '    if [ "$_UNLEASHED_FAILED" -gt 0 ]; then                                    # rule 1\n',
            '    if [ "$_UNLEASHED_FAILED" -gt 0 ] && [ "$_UNLEASHED_AUTHED" = 0 ]; then    # rule 1\n',
            path=READER)
        try:
            for shell in SHELLS:
                for srcs, want, want_diag in (((AUTH, STORE, READER, PUB), "0 unresolved stale", 1),
                                              (self._sources(mutant, READER), "1 pointer none", 0)):
                    self._fresh()
                    body = (ENTRY.format(t=self.base, s=self.store) + '\n'
                            f'printf "%s\\n" garbage > "{self.store}/base.bad"; '
                            f'chmod 600 "{self.store}/base.bad"\n'
                            + RESET_C1
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(want_diag, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 67 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_067_enumerator_is_absolute_not_path_selected(self):
        """Publisher and reader agree under different PATHs; a command -v-selected enumerator diverges."""
        # ACL-5/PUB-11: the enumerator is chosen by `uname -s` and invoked by ABSOLUTE PATH. The
        # mutant selects it through `command -v`, so a PATH entry decides which tool answers — a
        # publisher and a reader running under different PATHs then disagree about one machine.
        mutant = with_mutation(
            '_u_acl_enumerate() {\n    /bin/ls -lde -- "$1" 2>/dev/null\n}\n',
            '_u_acl_enumerate() {\n'
            '    if command -v getfacl >/dev/null 2>&1; then getfacl -- "$1" 2>/dev/null; '
            'else /bin/ls -lde -- "$1" 2>/dev/null; fi\n}\n',
            path=AUTH)
        fakebin = os.path.join(self.home, "fakebin")
        os.makedirs(fakebin)
        fake = os.path.join(fakebin, "getfacl")
        with open(fake, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nprintf 'garbage\\n'\n")
        os.chmod(fake, 0o755)
        try:
            for shell in SHELLS:
                for srcs, want in (((AUTH, STORE, READER, PUB), "created / 1 pointer none"),
                                   (self._sources(mutant, AUTH), "created / 0 unresolved stale")):
                    shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                    body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                            '_row67_pub="$_UNLEASHED_POINTER_STATE"\n'
                            + RESET_C1
                            + f'PATH="{fakebin}:$PATH"\n'
                            f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                            'printf "%s / %s %s %s" "$_row67_pub" "$_UNLEASHED_BASE_OK" '
                            '"$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"')
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
        finally:
            os.unlink(mutant)

    # ── row 79 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_079_conflict_diagnostic_carries_no_path_material(self):
        """The conflict diagnostic names neither targets nor entry names — an entry name decodes to a path."""
        mutant = with_mutation(
            '        _unleashed_unresolved conflict "two or more plugin-state entries disagree"\n',
            '        _unleashed_unresolved conflict "two or more plugin-state entries disagree: '
            '$(printf \'%s \' "$_rs_store"/base.*)"\n',
            path=READER)
        try:
            t2 = self._other_target()
            expected = ("unleashed-mail: two or more plugin-state entries disagree; "
                        "plugin state will not be read or written this run")
            for shell in SHELLS:
                for srcs, leaks in (((AUTH, STORE, READER, PUB), False),
                                    (self._sources(mutant, READER), True)):
                    self._fresh()
                    body = (ENTRY.format(t=self.base, s=self.store) + '\n'
                            '_row79_k1="$_UNLEASHED_KEY"\n'
                            + ENTRY.format(t=t2, s=self.store) + '\n'
                            '_row79_k2="$_UNLEASHED_KEY"\n'
                            + RESET_C1
                            + f'_unleashed_read_store "{self.store}"\n'
                            'printf "%s %s %s|%s|%s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" '
                            '"$_UNLEASHED_POINTER_STATE" "$_row79_k1" "$_row79_k2"')
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    tup, k1, k2 = out.split("|")
                    self.assertEqual("0 unresolved conflict", tup, f"{shell}: {err}")
                    self.assertEqual(1, len(err.splitlines()), f"{shell}: {err!r}")
                    if leaks:
                        self.assertIn(k1, err, f"{shell}: the CONTROL did not leak")
                    else:
                        # ENC-10/RD-6: no path material, REVERSIBLE OR OTHERWISE — the raw targets
                        # and both entry keys (lossless encodings of them) must all be absent.
                        self.assertEqual(expected, err.splitlines()[0], f"{shell}: {err!r}")
                        for secret in (self.base, t2, k1, k2):
                            self.assertNotIn(secret, err, f"{shell}: {secret!r} leaked")
        finally:
            os.unlink(mutant)

    # ── rows 88 / 95 — the vanished-own-entry fixture ─────────────────────────────────────────────
    #
    # "Removed before the scan" needs a deterministic hook between PUB-7's decision and E7's scan.
    # The enumerator seam provides one: during one publish the TARGET path is enumerated exactly
    # twice — once by E2's target-chain walk and once by PUB-7's auth of the existing entry, whose
    # target chain is the LAST walk before the scan. The seam counts visits through a file (it runs
    # in a command-substitution subshell, so a shell variable would not persist) and deletes the own
    # entry on the second visit; every answer it gives is healthy, so nothing else changes.

    def _vanish_body(self, extra_setup=""):
        cnt = os.path.join(self.home, "row-visits")
        return (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                + extra_setup
                + RESET_C1
                + f': > "{cnt}"\n'
                f'_unleashed_key "{self.base}"\n'
                f'_row_entry="{self.store}/base.$_UNLEASHED_KEY"\n'
                '_u_acl_enumerate() {\n'
                f'    if [ "$1" = "{self.base}" ]; then\n'
                f'        printf x >> "{cnt}"\n'
                f'        if [ "$(/usr/bin/wc -c < "{cnt}")" -ge 2 ]; then '
                '/bin/rm -f -- "$_row_entry"; fi\n'
                '    fi\n'
                "    printf %b 'drwx------@ 2 n s 64 d\\n'\n"
                '}\n'
                f'_unleashed_publish "{self.store}" "{self.base}"\n'
                'printf "%s" "$_UNLEASHED_POINTER_STATE"')

    def test_row_088_vanished_own_entry_fails_on_the_no_write_path_too(self):
        """PUB-9 P1 fires whether or not this process wrote: a no-write `current` publish reports `failed`."""
        mutant = with_mutation(
            '    if ! _unleashed_auth_entry "$_pb_entry"; then\n',
            '    if [ "$_pb_wrote" = 1 ] && ! _unleashed_auth_entry "$_pb_entry"; then\n',
            path=PUB)
        try:
            for shell in SHELLS:
                for srcs, want, want_diag in (((AUTH, STORE, READER, PUB), "failed", 1),
                                              (self._sources(mutant, PUB), "current", 0)):
                    shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                    rc, out, err = run_shell(shell, self._vanish_body(), sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(want_diag, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    def test_row_095_post_scan_exits_are_ordered_p1_before_p2(self):
        """Own-entry-missing PLUS another malformed entry reports `failed` (P1), never `stale` (P2)."""
        mutant = with_mutation(
            '    if ! _unleashed_auth_entry "$_pb_entry"; then\n'
            '        _unleashed_pub_failed "this process\'s own plugin-state entry is missing or unusable"   # P1\n'
            '    elif [ "$_UNLEASHED_FAILED" -gt 0 ]; then\n'
            '        _unleashed_pub_state stale                                                             # P2\n',
            '    if [ "$_UNLEASHED_FAILED" -gt 0 ]; then\n'
            '        _unleashed_pub_state stale                                                             # P2\n'
            '    elif ! _unleashed_auth_entry "$_pb_entry"; then\n'
            '        _unleashed_pub_failed "this process\'s own plugin-state entry is missing or unusable"   # P1\n',
            path=PUB)
        sibling = (f'printf "%s\\n" garbage > "{self.store}/base.bad"; '
                   f'chmod 600 "{self.store}/base.bad"\n')
        try:
            for shell in SHELLS:
                for srcs, want, want_diag in (((AUTH, STORE, READER, PUB), "failed", 1),
                                              (self._sources(mutant, PUB), "stale", 0)):
                    shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                    rc, out, err = run_shell(shell, self._vanish_body(sibling), sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(want_diag, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 102 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_102_blacklist_mutant_at_the_store_level(self):
        """A right outside the seven-right allowlist ⇒ the store-level stale tuple + one diagnostic."""
        # DarwinAclArm.test_control_a_blacklist_of_mutating_rights_fails_open kills this same mutant
        # at the COMPONENT level; N6-6 requires the STORE-LEVEL tuple through the production
        # resolver, which the enumerator seam makes runnable. `writeattr,chown` is absent from any
        # plausible blacklist, so the mutant accepts what the allowlist refuses.
        mutant = with_mutation(
            "            execute|list|read|readattr|readextattr|readsecurity|search) : ;;\n"
            "            file_inherit|directory_inherit|limit_inherit|only_inherit) : ;;\n"
            "            *) return 1 ;;",
            "            write|delete) return 1 ;;\n            *) : ;;",
            path=AUTH)
        answer = "drwx------@ 2 n s 64 d\n 0: group:staff allow writeattr,chown\n"
        try:
            for shell in SHELLS:
                for srcs, want, want_diag in (((AUTH, STORE, READER, PUB), "0 unresolved stale", 1),
                                              (self._sources(mutant, AUTH), "1 pointer none", 0)):
                    self._fresh()
                    body = (ENTRY.format(t=self.base, s=self.store) + '\n' + RESET_C1
                            + seam(answer)
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(want_diag, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 109 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_109_e2_derives_no_key(self):
        """An unpublishable value opens NOTHING under the store — and derives NO KEY (PUB-9 E2)."""
        # The FS half ("no ancestor, no temporary, no scan") is held by the existing
        # test_e2_an_unpublishable_value_writes_nothing_at_all; the mutant here satisfies that half
        # too, so the discriminator is E2's "no key is derived": _UNLEASHED_KEY, pre-set to a
        # marker, must still hold the marker after the refusal.
        mutant = with_mutation(
            '    case "$_pb_value" in\n'
            '        /*) : ;;\n'
            '        *)  _unleashed_pub_failed "the plugin-data base is not an absolute path"; return 0 ;;\n'
            '    esac\n',
            '    _unleashed_key "$_pb_value"\n'
            '    _pb_key="$_UNLEASHED_KEY"\n'
            '    case "$_pb_value" in\n'
            '        /*) : ;;\n'
            '        *)  _unleashed_pub_failed "the plugin-data base is not an absolute path"; return 0 ;;\n'
            '    esac\n',
            path=PUB)
        try:
            for shell in SHELLS:
                for srcs, want in (((AUTH, STORE, READER, PUB), "failed row109-untouched"),
                                   (self._sources(mutant, PUB), "failed relative_spath")):
                    shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                    body = ('_UNLEASHED_KEY=row109-untouched\n'
                            f'_unleashed_publish "{self.store}" "relative/path" 2>/dev/null\n'
                            'printf "%s %s" "$_UNLEASHED_POINTER_STATE" "$_UNLEASHED_KEY"')
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertFalse(os.path.exists(self.store),
                                     f"{shell}: E2 must compose and open NOTHING under the store")
        finally:
            os.unlink(mutant)

    # ── row 116 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_116_type_before_open_prevents_the_fifo_hang(self):
        """The publisher does not HANG on a FIFO'd transient candidate; it skips it and publishes."""
        # TMP-1: type BEFORE open — `set -C; : > fifo` never returns (the row's measured rc=124).
        # The oracle is the ABSENCE of the hang, NOT `failed`: three total attempts with a fresh
        # $RANDOM mean a correct publisher skips the FIFO'd candidate and reports `created`.
        # The candidate is made predictable by seeding RANDOM (measured reproducible in both
        # shells); the MUTANT blocking on exactly that name is what proves the prediction held.
        # A hang oracle needs a timeout, which run_shell does not carry, so this test invokes the
        # same composed source through subprocess with one.
        mutant = with_mutation(
            '        if [ -L "$_tn_p" ] || [ -e "$_tn_p" ]; then\n'
            '            continue\n'
            '        fi\n',
            '        :\n', path=PUB)

        def run_with_timeout(shell, body, srcs, timeout=8):
            src = "".join(f'. "{s}"\n' for s in srcs) + body
            try:
                p = subprocess.run([shell, "-c", src], capture_output=True, text=True,
                                   timeout=timeout)
                return p.returncode, p.stdout
            except subprocess.TimeoutExpired:
                return "TIMEOUT", ""

        def unblock_fifos():
            # The mutant's subshell is left blocked in open(2) on the FIFO after its parent is
            # killed; opening the reading end releases it so no orphan outlives the test.
            if os.path.isdir(self.store):
                for f in os.listdir(self.store):
                    p = os.path.join(self.store, f)
                    if statmod.S_ISFIFO(os.lstat(p).st_mode):
                        fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
                        os.close(fd)

        body = (f'_unleashed_create_store "{self.store}" || exit 9\n'
                f'_unleashed_key "{self.base}"\n'
                'RANDOM=42\n'
                '_row116_r1=$RANDOM\n'
                'RANDOM=42\n'
                f'/usr/bin/mkfifo "{self.store}/.pub.$$.${{_row116_r1}}.$_UNLEASHED_KEY" || exit 8\n'
                f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                'printf "%s" "$_UNLEASHED_POINTER_STATE"')
        try:
            for shell in SHELLS:
                try:
                    shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                    rc, out = run_with_timeout(shell, body, (AUTH, STORE, READER, PUB))
                    self.assertEqual((0, "created"), (rc, out),
                                     f"{shell}: shipped must skip the FIFO and publish")
                    shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                    rc, out = run_with_timeout(shell, body, self._sources(mutant, PUB))
                    self.assertEqual("TIMEOUT", rc,
                                     f"{shell}: the CONTROL did not hang (out={out!r}) — "
                                     "either the open is not reached or the candidate missed the FIFO")
                finally:
                    unblock_fifos()
        finally:
            os.unlink(mutant)

    # ── row 123 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_123_ifs_read_r_preserves_backslash_and_trailing_space(self):
        """An entry holding backslash + trailing space resolves; plain `read` mangles it ⇒ stale."""
        # TGT-1 permits both bytes. Measured (probe + this test): plain `read` yields the mangled
        # value in BOTH shells — the backslash is eaten and the trailing space IFS-stripped — so
        # ENT-2/ENT-3 fail and the store refuses a healthy entry. Row 4 is the multi-line case and
        # cannot discriminate this single-line transformation.
        mutant = with_mutation(
            '    { IFS= read -r _ae_line < "$_ae_p"; } 2>/dev/null || return 1     # (1)\n',
            '    { read _ae_line < "$_ae_p"; } 2>/dev/null || return 1     # (1)\n',
            path=READER)
        weird = os.path.join(self.home, "a\\b ")           # backslash, trailing space
        os.makedirs(weird)
        os.chmod(weird, 0o700)
        try:
            for shell in SHELLS:
                for srcs, want, want_diag in (
                        ((AUTH, STORE, READER, PUB), f"1 pointer none|{weird}", 0),
                        (self._sources(mutant, READER),
                         "0 unresolved stale|/dev/null/unresolved-plugin-base", 1)):
                    self._fresh()
                    body = ('_unleashed_key "$ROW123_T"\n'
                            f'printf "%s\\n" "$ROW123_T" > "{self.store}/base.$_UNLEASHED_KEY"\n'
                            f'chmod 600 "{self.store}/base.$_UNLEASHED_KEY"\n'
                            + RESET_C1
                            + f'_unleashed_read_store "{self.store}"\n'
                            'printf "%s %s %s|%s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" '
                            '"$_UNLEASHED_POINTER_STATE" "$_UNLEASHED_BASE_RESOLVED"')
                    rc, out, err = run_shell(shell, body, env={"ROW123_T": weird}, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(want_diag, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 129 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_129_untyped_uuid_principal_is_another_principal(self):
        """An allow ACE with an unresolved bare-UUID principal and mutating rights ⇒ stale."""
        # ACL-2/P-3a: only `user:<us>` is us; an identity the system could not resolve must not be
        # proof of ownership. The mutant reads ANY untyped principal as the effective user and the
        # component accepts.
        mutant = with_mutation(
            '        *)      _u_acl_who="" ;;      # a `group:` or UNTYPED principal is another principal: a bare\n',
            '        *)      _u_acl_who="$_U_PRINCIPAL" ;;      # a `group:` or UNTYPED principal is another principal: a bare\n',
            path=AUTH)
        answer = ("drwx------@ 2 n s 64 d\n"
                  " 0: ABCDEFAB-CDEF-ABCD-CDEF-ABCDEFABCDEF allow write,delete\n")
        try:
            for shell in SHELLS:
                for srcs, want, want_diag in (((AUTH, STORE, READER, PUB), "0 unresolved stale", 1),
                                              (self._sources(mutant, AUTH), "1 pointer none", 0)):
                    self._fresh()
                    body = (ENTRY.format(t=self.base, s=self.store) + '\n' + RESET_C1
                            + seam(answer)
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(want_diag, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 141 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_141_one_shared_platform_probe_per_resolution(self):
        """ACL-5: exactly ONE `/usr/bin/uname -s` per resolution, shared — a per-concern probe doubles it."""
        # The protocol variables are UNCHANGED under this mutant (the row says so), so the oracle is
        # the INVOCATION COUNT, measured by running the resolution under xtrace and counting
        # `/usr/bin/uname` in the trace — measured: each invocation appears exactly once in both
        # shells' traces, and nothing else in the read path spells that string. The mutant gives
        # P-2 its own memoized probe instead of sharing ACL-5's, exactly the split the row names.
        mutant = with_mutation(
            '_u_stat() {\n    if [ -n "${ZSH_VERSION:-}" ]; then\n',
            '_u_stat() {\n'
            '    if [ -z "${_U_P2_PLATFORM+set}" ]; then _U_P2_PLATFORM="$(/usr/bin/uname -s 2>/dev/null)"; fi\n'
            '    [ "$_U_P2_PLATFORM" = Darwin ] || [ "$_U_P2_PLATFORM" = Linux ] || return 1\n'
            '    if [ -n "${ZSH_VERSION:-}" ]; then\n',
            path=AUTH)
        try:
            for shell in SHELLS:
                self._fresh()
                # Entries are planted by a SEPARATE process: a same-process setup would already have
                # memoized the platform and the measured resolution would probe zero times.
                rc, out, err = run_shell(shell, ENTRY.format(t=self.base, s=self.store))
                self.assertEqual(0, rc, f"{shell}: {err}")
                counts = {}
                for arm, srcs in (("shipped", (AUTH, STORE, READER, PUB)),
                                  ("mutant", self._sources(mutant, AUTH))):
                    body = ('set -x\n'
                            f'_unleashed_read_store "{self.store}"\n'
                            'set +x\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual("1 pointer none", out,
                                     f"{shell} {arm}: the protocol outcome must be UNCHANGED")
                    counts[arm] = err.count("/usr/bin/uname")
                self.assertEqual(1, counts["shipped"], f"{shell}: shared probe must run ONCE")
                self.assertEqual(2, counts["mutant"],
                                 f"{shell}: the CONTROL did not add a second probe")
        finally:
            os.unlink(mutant)

    # ── row 148 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_148_reserved_token_in_perms_is_not_accepted_by_discard(self):
        """`group:staff deny allow` ⇒ stale; without the reserved-token check it is accepted by being thrown away."""
        # The two-verb line parses as verb `deny` + rights `allow` under the mutant, and ACL-1's
        # ignore-every-`deny` rule then discards it — acceptance THROUGH the discard rule. Row 144
        # mutates the second-field check and cannot see this: there is only one field after the verb.
        mutant = with_mutation(
            '            case "$_u13_tok" in\n'
            '                allow|deny|inherited) return 1 ;;               # a reserved token cannot BE the rights\n'
            '            esac\n',
            '            :\n', path=AUTH)
        answer = "drwx------@ 2 n s 64 d\n 0: group:staff deny allow\n"
        try:
            for shell in SHELLS:
                for srcs, want, want_diag in (((AUTH, STORE, READER, PUB), "0 unresolved stale", 1),
                                              (self._sources(mutant, AUTH), "1 pointer none", 0)):
                    self._fresh()
                    body = (ENTRY.format(t=self.base, s=self.store) + '\n' + RESET_C1
                            + seam(answer)
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C1)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(want_diag, len(err.splitlines()), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)


# ==================================================================================================
# Chunk 2
# ==================================================================================================
"""COREDEV-2617 mutant-table rows, chunk 2 — every row here is EXECUTED against the shipped
build AND a mutant build, in both shells, and the outcomes must differ (campaign hard rule 1)."""

import os
import shutil
import subprocess
import tempfile
import unittest



@unittest.skipUnless(DARWIN, "every row drives the Darwin chain authenticator")
class RowsChunk2(unittest.TestCase):
    """Mutant-table rows 2, 8, 24, 34, 49, 56, 62, 68, 74, 80, 89, 110, 117, 124, 130, 136, 142, 149."""

    def setUp(self):
        # A scratch HOME under ~/.claude, like the rest of the suite: /tmp is sticky/other-writable,
        # so PCH-1 would refuse every chain rooted there and each test would fail for a fixture
        # reason that reads exactly like a code reason (§7 step 3f(i)).
        self.home = scratch_home("rc2617.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.base = os.path.join(self.home, "base")
        os.makedirs(self.base)
        os.chmod(self.base, 0o700)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    # ── shared fixture fragments ──────────────────────────────────────────────────────────────────
    #: Create the store chain, refusing loudly if that fails — a broken fixture must not read as a
    #: refusal the test then "expects".
    MAKE = ('_unleashed_name_max "{s}" >/dev/null\n'
            '_unleashed_create_store "{s}" || exit 9\n')
    #: A conforming entry: the target's encoded name, its single line, mode 0600.
    ENTRY = ('_unleashed_key "{t}"; printf "%s\\n" "{t}" > "{s}/base.$_UNLEASHED_KEY"; '
             'chmod 600 "{s}/base.$_UNLEASHED_KEY"\n')
    #: The store-level outcome tuple. stderr is left attached so each test can count diagnostics.
    TUPLE = ('_unleashed_read_store "{s}"\n'
             'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" '
             '"$_UNLEASHED_POINTER_STATE"')
    #: Reset between a publish and a read in one body (§7 step 3f conventions).
    RESET = ('unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE '
             '_UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL\n')

    def _fresh(self):
        shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)

    def _key(self, value):
        rc, out, err = run_shell("/bin/bash", f'_unleashed_key "{value}"; printf %s "$_UNLEASHED_KEY"')
        assert rc == 0 and out, f"encoder fixture failed: {err}"
        return out

    def _entries(self):
        return sorted(f for f in os.listdir(self.store) if f.startswith("base."))

    # ── row 2 ─────────────────────────────────────────────────────────────────────────────────────
    def test_row_002_dangling_symlink_is_a_failing_entry_never_a_vanished_one(self):
        """Row 2: a dangling base.* symlink yields stale + one diagnostic; it is NOT skipped as vanished."""
        # The mutation is the one-part skip RD-9 prohibits: `[ -e ]` is FALSE for a dangling symlink,
        # so rule 0 skips the hostile entry as vanished and the conforming entry beside it WINS.
        mutant = with_mutation(
            '        if [ ! -L "$_ss_f" ] && [ ! -e "$_ss_f" ]; then',
            '        if [ ! -e "$_ss_f" ]; then', path=READER)
        try:
            setup = (self.ENTRY.format(t=self.base, s=self.store)
                     + f'ln -s "{self.home}/nonexistent" "{self.store}/base.dangling"\n')
            body = self.MAKE.format(s=self.store) + setup + self.TUPLE.format(s=self.store)
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("0 unresolved stale", out, f"{shell}: shipped: {err}")
                self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
                self._fresh()
                rc, out, err = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("1 pointer none", out,
                                 f"{shell}: the mutant did not skip the dangling symlink")
        finally:
            os.unlink(mutant)

    # ── row 8 ─────────────────────────────────────────────────────────────────────────────────────
    def test_row_008_an_0644_entry_refuses_and_a_conforming_neighbour_does_not_win(self):
        """Row 8: a 0644 entry yields stale + one diagnostic, and a conforming entry beside it does NOT win."""
        # The mutation accepts ANY entry mode (ENT-1's mode clause dropped). Alone, the 0644 entry
        # then RESOLVES; beside a conforming entry it counts as a second authenticator -> conflict.
        # Either way the shipped rule-1 outcome (stale) is gone.
        mutant = with_mutation('    [ "$_U_MODE" = 0600 ] || return 1', '    :', path=READER)
        try:
            t2 = os.path.join(self.home, "t2")
            os.makedirs(t2)
            os.chmod(t2, 0o700)
            alone = (self.ENTRY.format(t=self.base, s=self.store)
                     + f'chmod 644 "{self.store}"/base.*\n')
            beside = alone + self.ENTRY.format(t=t2, s=self.store)
            for shell in SHELLS:
                for setup, spec_want, mut_want in (
                        (alone, "0 unresolved stale", "1 pointer none"),
                        (beside, "0 unresolved stale", "0 unresolved conflict")):
                    body = self.MAKE.format(s=self.store) + setup + self.TUPLE.format(s=self.store)
                    self._fresh()
                    rc, out, err = run_shell(shell, body)
                    self.assertEqual(spec_want, out, f"{shell}: shipped: {err}")
                    self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
                    self._fresh()
                    rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                    self.assertEqual(mut_want, out, f"{shell}: the mutant kept refusing")
        finally:
            os.unlink(mutant)

    # ── row 24 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_024_an_ancestor_owned_by_another_uid_refuses_the_target_chain(self):
        """Row 24: a target ancestor owned by another uid yields stale, and a conforming entry beside does not win."""
        # Fixture: /private/var/networkd/db — ancestors /, /private, /private/var are uid-0 0755
        # (ANCHOR-1's system prefix), then networkd is _networkd-owned 0755 with no ACEs: the
        # anchor falls there, the euid test fails, and the walk never reaches db. The mutation
        # drops PCH-1's ownership clause, so the mode/ACL-clean foreign chain then AUTHENTICATES.
        anc, tgt = "/private/var/networkd", "/private/var/networkd/db"
        if not os.path.isdir(tgt) or os.path.islink(anc) or os.path.islink(tgt):
            self.skipTest("no other-uid ancestor with a stat-able child on this machine")
        st = os.stat(anc)
        if st.st_uid in (0, os.geteuid()) or (st.st_mode & 0o022) or (os.stat(tgt).st_mode & 0o022):
            self.skipTest("fixture ancestor is not another-uid with clean modes")
        mutant = with_mutation(
            '            [ "$_U_UID" = "${EUID:-$(/usr/bin/id -u)}" ] || return 1',
            '            :', path=AUTH)
        try:
            alone = self.ENTRY.format(t=tgt, s=self.store)
            beside = alone + self.ENTRY.format(t=self.base, s=self.store)
            for shell in SHELLS:
                for setup, spec_want, mut_want in (
                        (alone, "0 unresolved stale", "1 pointer none"),
                        (beside, "0 unresolved stale", "0 unresolved conflict")):
                    body = self.MAKE.format(s=self.store) + setup + self.TUPLE.format(s=self.store)
                    self._fresh()
                    rc, out, err = run_shell(shell, body)
                    self.assertEqual(spec_want, out, f"{shell}: shipped: {err}")
                    self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
                    self._fresh()
                    rc, out, _ = run_shell(shell, body, sources=(mutant, STORE, READER, PUB))
                    self.assertEqual(mut_want, out, f"{shell}: the mutant kept refusing")
        finally:
            os.unlink(mutant)

    # ── row 34 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_034_an_all_root_system_target_resolves_without_euid_ownership(self):
        """Row 34: an all-root off-HOME target authenticates and the store RESOLVES: 1 pointer none, empty stderr."""
        # ANCHOR-1 accepts a LEADING RUN of uid-0 system-prefix components, so /usr/bin — root all
        # the way down — authenticates with no euid-owned component at all. The mutation requires
        # euid ownership everywhere (prefix acceptance dropped): the whole machine then refuses,
        # from `/` on down, and the store goes stale.
        mutant = with_mutation(
            '        if [ "$_u_ac_in_prefix" = 1 ] && [ "$_U_UID" = 0 ]; then',
            '        if false; then', path=AUTH)
        try:
            body = (self.MAKE.format(s=self.store) + self.ENTRY.format(t="/usr/bin", s=self.store)
                    + self.TUPLE.format(s=self.store))
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("1 pointer none", out, f"{shell}: shipped: {err}")
                self.assertEqual("", err, f"{shell}: a resolution must be silent")
                self._fresh()
                # The mutant refuses the store chain itself (rule -1): / is root-owned too. The
                # store must be CREATED with the shipped build, then READ with the mutant, or E4
                # masks the read-side outcome.
                rc, out, err = run_shell(shell, self.MAKE.format(s=self.store)
                                         + self.ENTRY.format(t="/usr/bin", s=self.store))
                self.assertEqual(0, rc, f"{shell}: fixture: {err}")
                rc, out, err = run_shell(shell, self.TUPLE.format(s=self.store),
                                         sources=(mutant, STORE, READER, PUB))
                self.assertEqual("0 unresolved stale", out,
                                 f"{shell}: the mutant still accepted the root prefix")
                self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
        finally:
            os.unlink(mutant)

    # ── row 49 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_049_publish_then_scan_makes_the_racing_publisher_report_conflict(self):
        """Row 49: the racing publisher reports conflict, not created — only the reported state discriminates."""
        # The mutation scans BEFORE publishing (and not after): the racer's scan sees only the
        # first publisher's entry, so P3 never fires and it reports `created` from a stale count.
        # The durable file set is IDENTICAL under both orders — asserted below — so a test that
        # examined the store instead of the report could not tell them apart.
        m1 = with_mutation(
            '    if _unleashed_auth_entry "$_pb_entry"; then\n        _pb_wrote=0\n',
            '    _unleashed_scan_store "$_pb_store"\n'
            '    if _unleashed_auth_entry "$_pb_entry"; then\n        _pb_wrote=0\n', path=PUB)
        m2 = with_mutation(
            '    _unleashed_scan_store "$_pb_store"\n    if ! _unleashed_auth_entry "$_pb_entry"; then\n',
            '    if ! _unleashed_auth_entry "$_pb_entry"; then\n', path=m1)
        try:
            base_b = os.path.join(self.home, "baseB")
            os.makedirs(base_b)
            os.chmod(base_b, 0o700)
            body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                    + self.RESET
                    + f'_unleashed_publish "{self.store}" "{base_b}" 2>/dev/null\n'
                    'printf "%s" "$_UNLEASHED_POINTER_STATE"')
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("conflict", out, f"{shell}: shipped: {err}")
                spec_files = self._entries()
                self._fresh()
                rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, READER, m2))
                self.assertEqual("created", out, f"{shell}: the mutant's stale count still conflicted")
                self.assertEqual(spec_files, self._entries(),
                                 f"{shell}: the durable file set differed — the fixture no longer "
                                 "isolates the REPORT")
                self.assertEqual(2, len(spec_files), f"{shell}: both entries must be durable")
        finally:
            os.unlink(m1)
            os.unlink(m2)

    # ── row 56 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_056_a_deny_ace_is_ignored_entirely_and_the_store_resolves(self):
        """Row 56: a real `group:everyone deny delete` ACE still RESOLVES: 1 pointer none, empty stderr."""
        # ACL-1: `deny` entries are ignored ENTIRELY. The mutation refuses on ANY ACE, `deny`
        # included — exactly the over-tight reading that would kill the capability on every Mac
        # whose ${HOME} carries the stock `group:everyone deny delete` ACE.
        subprocess.run(["/bin/chmod", "+a", "group:everyone deny delete", self.base], check=True)
        mutant = with_mutation(
            '    [ "$_u13_verb" = allow ] || return 0',
            '    [ "$_u13_verb" = allow ] || return 1', path=AUTH)
        try:
            body = (self.MAKE.format(s=self.store) + self.ENTRY.format(t=self.base, s=self.store)
                    + self.TUPLE.format(s=self.store))
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("1 pointer none", out, f"{shell}: shipped: {err}")
                self.assertEqual("", err, f"{shell}: a resolution must be silent")
                self._fresh()
                rc, out, err = run_shell(shell, self.MAKE.format(s=self.store)
                                         + self.ENTRY.format(t=self.base, s=self.store))
                self.assertEqual(0, rc, f"{shell}: fixture: {err}")
                rc, out, err = run_shell(shell, self.TUPLE.format(s=self.store),
                                         sources=(mutant, STORE, READER, PUB))
                self.assertEqual("0 unresolved stale", out, f"{shell}: the mutant ignored the deny ACE")
                self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
        finally:
            os.unlink(mutant)

    # ── row 62 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_062_pid_alone_collides_with_a_same_pid_orphan_and_random_does_not(self):
        """Row 62: two same-base publishers cannot open the same temp inode — $$ alone exhausts E5 on an orphan."""
        # The fixture is a crash-orphaned transient made by the SUT's OWN namer in the SAME process
        # ($$ identical, TMP-1's collision case). Shipped, the next publish draws a fresh $RANDOM
        # and publishes; with the name reverted to $$ alone all three attempts hit the orphan's
        # inode and the publish takes E5.
        mutant = with_mutation('/.pub.$$.${RANDOM}.$_tn_key"', '/.pub.$$.$_tn_key"', path=PUB)
        try:
            body = (self.MAKE.format(s=self.store)
                    + f'_unleashed_key "{self.base}"; k="$_UNLEASHED_KEY"\n'
                    f'_unleashed_transient_name "{self.store}" "$k" || exit 8\n'
                    ': > "$_UNLEASHED_TRANSIENT"\n'
                    f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                    'printf "%s" "$_UNLEASHED_POINTER_STATE"')
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("created", out, f"{shell}: shipped: {err}")
                self.assertEqual(1, len(self._entries()), f"{shell}: the entry must be durable")
                self._fresh()
                rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, READER, mutant))
                self.assertEqual("failed", out, f"{shell}: the mutant found a unique name anyway")
                self.assertEqual([], self._entries(), f"{shell}: E5 must publish nothing")
        finally:
            os.unlink(mutant)

    # ── row 68 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_068_a_failed_enumerator_refuses_and_never_falls_back_to_mode_bits(self):
        """Row 68: an unevaluable ACL condition yields stale + one diagnostic; mode bits alone must not accept."""
        # Through the enumerator-output seam the probe FAILS on every component. The walk's mode
        # and ownership clauses all pass (the chain is genuinely healthy), so a mutant that treats
        # a failed enumerator as "fall back to the mode bits" resolves — which is exactly the
        # fail-open ACL-4 forbids.
        mutant = with_mutation(
            '|| return 1   # a failed enumerator REFUSES',
            '|| return 0   # MUTANT: fall back to the mode bits the walk already checked', path=AUTH)
        try:
            seam = '_u_acl_enumerate() { return 1; }\n'
            body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                    + self.RESET + seam + self.TUPLE.format(s=self.store))
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("0 unresolved stale", out, f"{shell}: shipped: {err}")
                self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
                self._fresh()
                rc, out, err = run_shell(shell, body, sources=(mutant, STORE, READER, PUB))
                self.assertEqual("1 pointer none", out,
                                 f"{shell}: the mutant still refused — no fallback happened")
                self.assertEqual("", err, f"{shell}: the mutant's resolution should be silent")
        finally:
            os.unlink(mutant)

    # ── row 74 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_074_the_zsh_version_guard_keeps_the_bash_arm_clean_under_set_euo(self):
        """Row 74: a bash arm runs the empty-store scan cleanly under set -euo pipefail, with no `command not found`."""
        # The guard exists FOR bash: `setopt` is a zsh builtin, so the unguarded mutant makes the
        # bash arm die at scan time under errexit. The zsh arms are identical by design — the
        # discriminating cell is bash, where the shipped build completes and the mutant aborts.
        mutant = with_mutation(
            '    if [ -n "${ZSH_VERSION:-}" ]; then\n'
            '        setopt local_options no_nomatch\n'
            '    fi\n',
            '    setopt local_options no_nomatch\n', path=READER)
        try:
            body = ('set -euo pipefail\n' + self.MAKE.format(s=self.store)
                    + self.TUPLE.format(s=self.store))
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("0 unresolved none", out, f"{shell}: shipped: {err}")
                self.assertEqual(0, rc, f"{shell}: shipped rc")
                self.assertNotIn("command not found", err, f"{shell}: shipped emitted 127s")
                self._fresh()
                rc, out, err = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                if shell.endswith("zsh"):
                    self.assertEqual("0 unresolved none", out, f"{shell}: setopt is native to zsh")
                else:
                    self.assertNotEqual(0, rc, f"{shell}: errexit must kill the mutant's scan")
                    self.assertIn("command not found", err, f"{shell}: the mutant's 127 is the signal")
                    self.assertEqual("", out, f"{shell}: the tuple must never be reached")
        finally:
            os.unlink(mutant)

    # ── row 80 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_080_a_0644_entry_with_matching_content_is_republished_as_created(self):
        """Row 80: a 0644 REGULAR entry with matching content is REPUBLISHED (created, never current); symlink-to-dir takes ST-7's failed."""
        # The mutation replaces PUB-7's write-or-skip predicate (AUTH-1's full authenticator) with
        # the weaker type-and-content test. It then skips the write, and the publish-then-scan
        # exits expose the lie: the 0644 entry fails the post-scan's own-entry check, so the
        # mutant reports `failed` while the shipped build repairs to 0600 and reports `created`.
        # MEASURED divergence from the row's second half: ST-7's `[ ! -f ]` FOLLOWS symlinks, so a
        # symlink to a REGULAR FILE is republished (`created`, link replaced by a real file) in
        # both shells; only a symlink to a NON-file (directory here) reports `failed`. The
        # symlink-to-dir shape is asserted; the row's blanket symlink claim is not true of the
        # shipped build.
        mutant = with_mutation(
            '    if _unleashed_auth_entry "$_pb_entry"; then',
            '    if [ -f "$_pb_entry" ] && IFS= read -r _pb_probe < "$_pb_entry" && '
            '[ "$_pb_probe" = "$_pb_value" ]; then', path=PUB)
        try:
            key = self._key(self.base)
            entry = os.path.join(self.store, "base." + key)
            weak = (self.ENTRY.format(t=self.base, s=self.store)
                    + f'chmod 644 "{self.store}"/base.*\n')
            body = (self.MAKE.format(s=self.store) + weak
                    + f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                    'printf "%s" "$_UNLEASHED_POINTER_STATE"')
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("created", out, f"{shell}: shipped: {err}")
                self.assertEqual(0o600, os.stat(entry).st_mode & 0o7777,
                                 f"{shell}: the republish must repair the mode")
                self._fresh()
                rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, READER, mutant))
                self.assertEqual("failed", out,
                                 f"{shell}: the weaker test skipped the write and P1 must expose it")
                self.assertEqual(0o644, os.stat(entry).st_mode & 0o7777,
                                 f"{shell}: the mutant must have written nothing")
                # ST-7's shape: a symlink to a NON-file is refused without repair, shipped build.
                self._fresh()
                sym_body = (self.MAKE.format(s=self.store)
                            + f'ln -s "{self.base}" "{self.store}/base.{key}"\n'
                            f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                            'printf "%s" "$_UNLEASHED_POINTER_STATE"')
                rc, out, err = run_shell(shell, sym_body)
                self.assertEqual("failed", out, f"{shell}: ST-7 must refuse a symlink-to-directory")
                self.assertTrue(os.path.islink(entry), f"{shell}: ST-7 must not repair")
        finally:
            os.unlink(mutant)

    # ── row 89 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_089_a_failing_target_chain_refuses_the_entry(self):
        """Row 89: an entry whose TARGET chain fails yields stale, and a conforming entry beside it does not win."""
        # The mutation applies only the entry clauses (rules 1-3's file/content/name tests) and
        # drops the target-chain walk. The fixture target is an existing 0707 directory: every
        # entry clause passes, and only the chain walk sees the other-writable bit.
        mutant = with_mutation('    _unleashed_auth_chain "$_ae_line" || return 1', '    :',
                               path=READER)
        try:
            t077 = os.path.join(self.home, "t077")
            os.makedirs(t077)
            os.chmod(t077, 0o707)
            alone = self.ENTRY.format(t=t077, s=self.store)
            beside = alone + self.ENTRY.format(t=self.base, s=self.store)
            for shell in SHELLS:
                for setup, spec_want, mut_want in (
                        (alone, "0 unresolved stale", "1 pointer none"),
                        (beside, "0 unresolved stale", "0 unresolved conflict")):
                    body = self.MAKE.format(s=self.store) + setup + self.TUPLE.format(s=self.store)
                    self._fresh()
                    rc, out, err = run_shell(shell, body)
                    self.assertEqual(spec_want, out, f"{shell}: shipped: {err}")
                    self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
                    self._fresh()
                    rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                    self.assertEqual(mut_want, out, f"{shell}: the mutant still walked the target chain")
        finally:
            os.unlink(mutant)

    # ── row 110 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_110_junk_beside_the_entries_does_not_deny_but_a_base_named_directory_does(self):
        """Row 110: junk the base.* glob does not match leaves the store RESOLVING; a directory named base.<k> goes stale."""
        # The mutation widens RD-9's enumeration to the whole directory: the junk then survives as
        # a "candidate", fails authentication, and rule 1 refuses a store the shipped build
        # resolves. The second shape — a DIRECTORY whose name the glob DOES match — must refuse
        # under both builds; it is the row's spec-side conjunction, not the discriminator.
        mutant = with_mutation('    for _ss_f in "$_ss_store"/base.*; do',
                               '    for _ss_f in "$_ss_store"/*; do', path=READER)
        try:
            junk = (self.ENTRY.format(t=self.base, s=self.store)
                    + f'printf junk > "{self.store}/notes.txt"; chmod 644 "{self.store}/notes.txt"\n'
                    f'mkdir "{self.store}/junkdir"\n')
            body = self.MAKE.format(s=self.store) + junk + self.TUPLE.format(s=self.store)
            dir_entry = (self.ENTRY.format(t=self.base, s=self.store)
                         + f'mkdir "{self.store}/base.zzz"\n')
            dir_body = self.MAKE.format(s=self.store) + dir_entry + self.TUPLE.format(s=self.store)
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("1 pointer none", out, f"{shell}: shipped: {err}")
                self.assertEqual("", err, f"{shell}: a resolution must be silent")
                self._fresh()
                rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("0 unresolved stale", out,
                                 f"{shell}: the mutant still enumerated only base.*")
                self._fresh()
                rc, out, err = run_shell(shell, dir_body)
                self.assertEqual("0 unresolved stale", out,
                                 f"{shell}: a directory named base.<k> must refuse: {err}")
                self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
        finally:
            os.unlink(mutant)

    # ── row 117 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_117_the_readers_type_guard_keeps_a_fifo_from_hanging_the_process(self):
        """Row 117: a FIFO named base.<k> yields stale + one diagnostic and the process EXITS; the symlink-only mutant blocks forever."""
        # RD-12: the TYPE is established before anything is opened. The mutation reverts to the
        # symlink-only pre-read guard, so the reader opens the FIFO and `read` blocks waiting for
        # a writer that never comes — measured as a harness timeout in both shells. This is the
        # READER's obligation: ST-7 keeps the PUBLISHER from such an entry independently (row 116).
        mutant = with_mutation('    [ -f "$_ae_p" ] || return 1', '    :', path=READER)
        try:
            setup = self.ENTRY.format(t=self.base, s=self.store)
            body = self.MAKE.format(s=self.store) + setup + (
                f'/usr/bin/mkfifo -m 600 "{self.store}/base.fifo117" || exit 7\n'
            ) + self.TUPLE.format(s=self.store)
            for shell in SHELLS:
                self._fresh()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("0 unresolved stale", out, f"{shell}: shipped: {err}")
                self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
                self._fresh()
                src = "".join(f'. "{s}"\n' for s in (AUTH, STORE, mutant, PUB)) + body
                try:
                    subprocess.run([shell, "-c", src], capture_output=True, text=True, timeout=5)
                    blocked = False
                except subprocess.TimeoutExpired:
                    blocked = True
                self.assertTrue(blocked,
                                f"{shell}: the mutant returned — the FIFO did not block, so this "
                                "fixture no longer discriminates")
        finally:
            os.unlink(mutant)

    # ── row 124 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_124_authenticate_the_existing_prefix_before_creating_anything(self):
        """Row 124: with the home root a symlink and .claude absent, the publisher creates NOTHING and reports failed."""
        # PUB-9 E4's order is the obligation: the mutation creates first, so `mkdir` runs THROUGH
        # the symlink and leaves a directory in the victim tree before the per-component
        # authentication catches up — ACL-6 forbids exactly that for a pre-creation refusal. The
        # reported state is `failed` under BOTH builds; the victim's directory is the discriminator.
        victim = os.path.join(self.home, "victim")
        symhome = os.path.join(self.home, "symhome")
        os.makedirs(victim)
        os.chmod(victim, 0o700)
        os.symlink(victim, symhome)
        sym_store = os.path.join(symhome, ".claude", "unleashed-mail", "bases")
        leak = os.path.join(victim, ".claude")
        mutant = with_mutation(
            '    _unleashed_auth_chain "$_UNLEASHED_NEAREST" || return 1        # (i)',
            '    :', path=STORE)
        try:
            body = (f'_unleashed_publish "{sym_store}" "{self.base}"\n'
                    'printf "%s" "$_UNLEASHED_POINTER_STATE"')
            for shell in SHELLS:
                shutil.rmtree(leak, ignore_errors=True)
                rc, out, err = run_shell(shell, body)
                self.assertEqual("failed", out, f"{shell}: shipped: {err}")
                self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
                self.assertFalse(os.path.lexists(leak),
                                 f"{shell}: the shipped build wrote through the symlink")
                rc, out, _ = run_shell(shell, body, sources=(AUTH, mutant, READER, PUB))
                self.assertEqual("failed", out, f"{shell}: mutant state")
                self.assertTrue(os.path.isdir(leak),
                                f"{shell}: the mutant did NOT create through the symlink — the "
                                "fixture no longer discriminates the ORDER")
        finally:
            os.unlink(mutant)
            shutil.rmtree(leak, ignore_errors=True)

    # ── row 130 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_130_the_read_status_clause_catches_a_terminal_nul_in_bash(self):
        """Row 130: a NUL-terminated no-newline entry refuses in both shells; without ENT-2(1) bash resolves — the oracle is the BASH arm."""
        # The entry holds an AUTHENTICATING target — this test's own 0700 euid-owned sandbox, per
        # the row: /private/tmp is 1777 so PCH-1 would refuse the chain with or without the
        # mutation. Under the mutation bash counts the terminal NUL as the required newline
        # (`read` drops the NUL: size = len+1 = ${#line}+1) and RESOLVES; zsh keeps the NUL and
        # still refuses on the byte count, so the zsh cells cannot discriminate — by the row's own
        # design the discriminating cell is bash.
        mutant = with_mutation('{ IFS= read -r _ae_line < "$_ae_p"; } 2>/dev/null || return 1',
                               '{ IFS= read -r _ae_line < "$_ae_p"; } 2>/dev/null || :', path=READER)
        try:
            key = self._key(self.base)
            body = self.TUPLE.format(s=self.store)
            for shell in SHELLS:
                for lib, want in ((READER, "0 unresolved stale"),
                                  (mutant, "1 pointer none" if shell.endswith("bash")
                                   else "0 unresolved stale")):
                    self._fresh()
                    os.makedirs(self.store)
                    for d in (os.path.join(self.home, ".claude"),
                              os.path.join(self.home, ".claude", "unleashed-mail"), self.store):
                        os.chmod(d, 0o700)
                    entry = os.path.join(self.store, "base." + key)
                    with open(entry, "wb") as fh:
                        fh.write(self.base.encode() + b"\x00")   # NUL, and NO newline
                    os.chmod(entry, 0o600)
                    rc, out, err = run_shell(shell, body, sources=(AUTH, STORE, lib, PUB))
                    which = "shipped" if lib is READER else "mutant"
                    self.assertEqual(want, out, f"{shell} {which}: {err}")
                    if want.endswith("stale"):
                        self.assertEqual(1, len(err.strip().splitlines()),
                                         f"{shell} {which}: one diagnostic")
        finally:
            os.unlink(mutant)

    # ── row 136 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_136_ancestors_are_made_by_absolute_path_mkdir_at_0700(self):
        """Row 136: the store outcome is NOT poisoned by a PATH-routed ancestor mkdir — the oracle is the ancestor MODE read back."""
        # ST-4 accepts 0755 ancestors, so a mutant that creates .claude and unleashed-mail through
        # a PATH shim (umask default, no -m 700) still reports `created` — the store-level outcome
        # cannot discriminate (that is row 134's point). The discriminators are the ancestor mode
        # read back and the shim's marker file.
        shim = os.path.join(self.home, "shim")
        os.makedirs(shim)
        marker = os.path.join(self.home, "shim.marker")
        with open(os.path.join(shim, "mkdir"), "w", encoding="utf-8") as fh:
            fh.write(f'#!/bin/sh\n: > "{marker}"\nexec /bin/mkdir "$@"\n')
        os.chmod(os.path.join(shim, "mkdir"), 0o755)
        mutant = with_mutation(
            '        if /bin/mkdir -m 700 "$_cs_d" 2>/dev/null; then',
            '        if { if [ "$_cs_d" = "$_cs_store" ]; then /bin/mkdir -m 700 "$_cs_d"; '
            'else mkdir "$_cs_d"; fi; } 2>/dev/null; then', path=STORE)
        try:
            top = os.path.join(self.home, ".claude")
            body = (f'umask 022\nPATH="{shim}:$PATH"; export PATH\n'
                    f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                    'printf "%s" "$_UNLEASHED_POINTER_STATE"')
            for shell in SHELLS:
                self._fresh()
                if os.path.exists(marker):
                    os.unlink(marker)
                rc, out, err = run_shell(shell, body)
                self.assertEqual("created", out, f"{shell}: shipped: {err}")
                self.assertEqual(0o700, os.stat(top).st_mode & 0o777, f"{shell}: shipped ancestor mode")
                self.assertFalse(os.path.exists(marker),
                                 f"{shell}: the shipped build consulted PATH for mkdir")
                self._fresh()
                rc, out, _ = run_shell(shell, body, sources=(AUTH, mutant, READER, PUB))
                self.assertEqual("created", out,
                                 f"{shell}: ST-4 accepts 0755 ancestors — the outcome must NOT change")
                self.assertEqual(0o755, os.stat(top).st_mode & 0o777,
                                 f"{shell}: the mutant's ancestor must carry the umask default")
                self.assertTrue(os.path.exists(marker), f"{shell}: the mutant must have used PATH")
        finally:
            os.unlink(mutant)

    # ── row 142 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_142_name_max_is_probed_exactly_once_per_publish(self):
        """Row 142: NM-1 derives exactly ONE getconf per publish; a per-component prober's count rises with the ancestors created."""
        # The probe seam is wrapped, not replaced: it still answers with the real getconf, so the
        # publish outcome is UNCHANGED (`created` in all four cells) and only the invocation count
        # discriminates — which is the row's point: 133/138 test a FAILED probe and ROUTING, and
        # neither counts.
        count = os.path.join(self.home, "probe.count")
        mutant = with_mutation(
            '        _unleashed_auth_chain "$_cs_d" || return 1',
            '        _unleashed_name_max "$_cs_d" || return 1\n'
            '        _unleashed_auth_chain "$_cs_d" || return 1', path=STORE)
        try:
            body = ('_u_name_max_probe() { printf x >> "%s"; /usr/bin/getconf NAME_MAX "$1"; }\n'
                    % count
                    + f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                    'printf "%s" "$_UNLEASHED_POINTER_STATE"')
            for shell in SHELLS:
                for lib, want_n in ((STORE, 1), (mutant, 4)):   # E3's probe + one per created dir
                    self._fresh()
                    if os.path.exists(count):
                        os.unlink(count)
                    rc, out, err = run_shell(shell, body, sources=(AUTH, lib, READER, PUB))
                    which = "shipped" if lib is STORE else "mutant"
                    self.assertEqual("created", out, f"{shell} {which}: outcome must not change: {err}")
                    got = os.stat(count).st_size if os.path.exists(count) else 0
                    self.assertEqual(want_n, got, f"{shell} {which}: probe count")
        finally:
            os.unlink(mutant)

    # ── row 149 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_149_the_ace_index_is_stripped_only_after_it_proves_decimal_and_delimited(self):
        """Row 149: ` 0:group:staff...` (no space) and ` x: ...` (non-decimal) are MALFORMED and poison the answer to stale."""
        # ACL-4/P-13: the index slot is parsed positionally and must be decimal, then `: `. The
        # mutation strips everything through the first `: ` unproven: the no-space line has no
        # `: ` at all and parses whole (principal `0:group:staff`), the non-decimal line sheds
        # ` x: ` (principal `group:staff`) — both then read as well-formed read-only ACEs and the
        # store RESOLVES. Rows 144-148 constrain only post-prefix slots and see nothing.
        mutant = with_mutation(
            '    _u13_idx="${_u13_line# }"; _u13_idx="${_u13_idx%%:*}"\n'
            "    case \"$_u13_idx\" in ''|*[!0-9]*) return 1 ;; esac          # the index must be DECIMAL\n"
            '    _u13_rest="${_u13_line# }"; _u13_rest="${_u13_rest#"$_u13_idx"}"\n'
            "    case \"$_u13_rest\" in ': '*) _u13_body=\"${_u13_rest#: }\" ;; *) return 1 ;; esac\n",
            '    _u13_body="${_u13_line#*: }"\n', path=AUTH)
        try:
            answers = (
                "drwx------@ 2 n s 64 d\n 0:group:staff allow list\n",   # no space after the colon
                "drwx------@ 2 n s 64 d\n x: group:staff allow list\n",  # non-decimal index
            )
            for shell in SHELLS:
                for answer in answers:
                    seam = ("_u_acl_enumerate() { printf %b "
                            + repr(answer).replace("'", '"') + "; }\n")
                    body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                            + self.RESET + seam + self.TUPLE.format(s=self.store))
                    self._fresh()
                    rc, out, err = run_shell(shell, body)
                    self.assertEqual("0 unresolved stale", out,
                                     f"{shell}: shipped must treat {answer!r} as malformed: {err}")
                    self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
                    self._fresh()
                    rc, out, err = run_shell(shell, body, sources=(mutant, STORE, READER, PUB))
                    self.assertEqual("1 pointer none", out,
                                     f"{shell}: the mutant still refused {answer!r}")
        finally:
            os.unlink(mutant)


# ==================================================================================================
# Chunk 3
# ==================================================================================================
#!/usr/bin/env python3
"""COREDEV-2617 mutant-table rows, chunk 3 — EXECUTED mutation tests.

Every covered-new row below was RUN: the shipped build and the mutant build, in BOTH /bin/bash and
/bin/zsh, and the outcomes differ (hard rule 1). Store-level outcomes are asserted per N6-6 — the
tuple `OK SOURCE POINTER_STATE`, never a bare "refused".
"""

import os
import shutil
import string
import subprocess
import tempfile
import threading
import time
import unittest


#: Row 19's obligation lives in the family resolver, not the four state libs.
PATHS_C3 = os.path.join(os.path.dirname(AUTH), "paths.sh")


def _upper_rows(emit):
    """The encoder's 13-line upper-case table, rebuilt exactly; `emit(ch)` yields the replacement
    emission for one upper-case letter. Rebuilding programmatically instead of pasting keeps the
    old-string in lockstep with the shipped file — with_mutation still asserts the exact match."""
    ups = string.ascii_uppercase
    rows = []
    for i in range(0, 26, 2):
        a, b = ups[i], ups[i + 1]
        rows.append(f'            {a}) _uk_out="${{_uk_out}}{emit(a)}" ;; '
                    f'{b}) _uk_out="${{_uk_out}}{emit(b)}" ;;')
    return "\n".join(rows)


UPPER_TABLE = _upper_rows(lambda c: "_c" + c.lower())


@unittest.skipUnless(DARWIN, "the Darwin arms; the Linux arms are unmeasured by design")
class RowsChunk3(unittest.TestCase):
    """Mutant-table rows 3, 9, 19, 35, 50, 57, 63, 69, 75, 81, 90, 98, 105, 111, 118, 125,
    131, 137, 143 — each one executed against the shipped build AND its mutant, both shells.

    Row 25 is deliberately ABSENT: measured in both shells, dropping TGT-1's target-symlink
    clause leaves the store-level outcome byte-identical, because the target chain walk's own
    per-component `[ -L ]` covers the final component — the row cannot discriminate a
    single-site mutation and is reported as such rather than faked. Row 150 is absent because
    test_malformed_answers_yield_the_store_level_refusal's "a later non-space line" fixture
    already discriminates its mutation (measured: spec `0 unresolved stale`, mutant
    `1 pointer none`, both shells)."""

    def setUp(self):
        # A scratch HOME so no test reads or writes the developer's real store (§7 step 3f(i)).
        self.home = scratch_home("rc3.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.target = os.path.join(self.home, "target")
        os.makedirs(self.target)
        os.chmod(self.target, 0o700)

    def tearDown(self):
        # A 0500 fixture blocks rmtree on some paths; restore modes best-effort first.
        for root, dirs, _files in os.walk(self.home):
            for d in dirs:
                try:
                    os.chmod(os.path.join(root, d), 0o700)
                except OSError:
                    pass
        shutil.rmtree(self.home, ignore_errors=True)

    # ── fixture helpers ───────────────────────────────────────────────────────────────────────────

    def _fresh_store(self):
        """(Re)create the store chain at exactly 0700, as ST-2 would."""
        shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
        for d in (os.path.join(self.home, ".claude"),
                  os.path.join(self.home, ".claude", "unleashed-mail"),
                  self.store):
            os.mkdir(d)
            os.chmod(d, 0o700)

    def _write_entry(self, value, store=None):
        """A well-formed entry for `value`: encoded name, single line, 0600 — what a conforming
        publisher would have written. The key comes from the SHIPPED encoder (the reader mutants
        under test never touch the encoder)."""
        store = store or self.store
        body = (f'_unleashed_key "{value}"\n'
                f'printf "%s\\n" "{value}" > "{store}/base.$_UNLEASHED_KEY" || exit 9\n'
                f'/bin/chmod 600 "{store}/base.$_UNLEASHED_KEY" || exit 9\n'
                'printf "%s" "$_UNLEASHED_KEY"')
        rc, out, err = run_shell("/bin/bash", body)
        self.assertEqual(0, rc, f"entry fixture failed: {err}")
        return os.path.join(store, "base." + out)

    def _read(self, shell, sources=(AUTH, STORE, READER, PUB), pre="", post=""):
        """Read the store through the production resolver; returns (stdout, stderr).
        stdout begins with `OK SOURCE POINTER_STATE|RESOLVED`."""
        body = (pre +
                f'\n_unleashed_read_store "{self.store}"\n'
                'printf "%s %s %s|%s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" '
                '"$_UNLEASHED_POINTER_STATE" "$_UNLEASHED_BASE_RESOLVED"\n' + post)
        rc, out, err = run_shell(shell, body, sources=sources)
        return out, err

    def _publish(self, shell, value, sources=(AUTH, STORE, READER, PUB), pre=""):
        """Publish `value` into the scratch store; returns (POINTER_STATE, stderr)."""
        body = (pre + f'\n_unleashed_publish "{self.store}" "{value}"\n'
                'printf "%s" "$_UNLEASHED_POINTER_STATE"')
        rc, out, err = run_shell(shell, body, sources=sources)
        return out, err

    def _entries(self):
        try:
            return sorted(f for f in os.listdir(self.store) if f.startswith("base."))
        except FileNotFoundError:
            return []

    def _case_insensitive_volume(self):
        p = os.path.join(self.home, "csprobe")
        with open(p, "w"):
            pass
        try:
            return os.path.exists(os.path.join(self.home, "CSPROBE"))
        finally:
            os.unlink(p)

    STALE = "0 unresolved stale|/dev/null/unresolved-plugin-base"
    SENTINEL = "/dev/null/unresolved-plugin-base"

    def _resolved(self):
        return f"1 pointer none|{self.target}"

    # ── row 3 ─────────────────────────────────────────────────────────────────────────────────────

    def test_row_003_relative_path_entry_refuses_store(self):
        """An entry holding a relative path yields sentinel, OK=0, SOURCE=unresolved, stale, one
        diagnostic — and a conforming entry beside it does NOT win."""
        # TGT-1's absolute-path clause. The mutant drops it; the fixture then AUTHENTICATES the
        # relative entry (cd / makes `[ -d ]` true and the chain walk composes the same absolute
        # components), so two entries authenticate and the store reports `conflict` instead of the
        # required `stale` — a good entry beside the bad one must NOT win (rule 1 before rule 2).
        mutant = with_mutation(
            '    case "$_ae_line" in\n'
            '        /*) : ;;                                     # absolute\n'
            '        *)  return 1 ;;\n'
            '    esac',
            '    :', path=READER)
        rel = self.target.lstrip("/")
        try:
            for shell in SHELLS:
                self._fresh_store()
                self._write_entry(rel)           # the malformed entry: a relative path
                self._write_entry(self.target)   # the conforming entry beside it
                out, err = self._read(shell, pre="cd / || exit 9")
                self.assertEqual(self.STALE, out, f"{shell}: spec")
                self.assertEqual(1, len(err.splitlines()), f"{shell}: exactly one diagnostic")
                out, _ = self._read(shell, pre="cd / || exit 9",
                                    sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("0 unresolved conflict|" + self.SENTINEL, out,
                                 f"{shell}: the MUTANT must accept the relative entry "
                                 "(two authenticate -> conflict), or this row cannot fail")
        finally:
            os.unlink(mutant)

    # ── row 9 ─────────────────────────────────────────────────────────────────────────────────────

    def test_row_009_trailing_slash_entry_refuses_store(self):
        """An entry holding `/a/b/` yields sentinel, OK=0, unresolved, stale, one diagnostic — and
        a conforming entry beside it does not win."""
        # Same shape as row 3, for TGT-1's trailing-slash clause: under the mutant the `<target>/`
        # entry authenticates (the chain walk tolerates the trailing slash; the key ends in `_s` so
        # ENT-3 matches), two entries authenticate, and the store reports `conflict` not `stale`.
        mutant = with_mutation(
            '    case "$_ae_line" in\n'
            '        */) return 1 ;;                              # no trailing slash\n'
            '    esac',
            '    :', path=READER)
        try:
            for shell in SHELLS:
                self._fresh_store()
                self._write_entry(self.target + "/")   # the malformed entry: a trailing slash
                self._write_entry(self.target)         # the conforming entry beside it
                out, err = self._read(shell)
                self.assertEqual(self.STALE, out, f"{shell}: spec")
                self.assertEqual(1, len(err.splitlines()), f"{shell}: exactly one diagnostic")
                out, _ = self._read(shell, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("0 unresolved conflict|" + self.SENTINEL, out,
                                 f"{shell}: the MUTANT did not accept the trailing-slash entry")
        finally:
            os.unlink(mutant)

    # ── row 19 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_019_empty_home_does_not_suppress_a_set_variable(self):
        """With HOME empty, a set CLAUDE_PLUGIN_DATA still resolves: OK=1."""
        # The obligation lives in paths.sh (the family resolver), not the four state libs: the
        # variable branch must win UNCONDITIONALLY; HOME gates only the publish side effect
        # (PUB-2). The mutant guards the whole branch on _unleashed_home_ok, so an empty HOME
        # degrades a resolved shell to the D' envelope. _UNLEASHED_PUBLISH_OK=0 is belt and braces:
        # it keeps even a misbehaving build from composing a real ${HOME} store path in this test.
        env = {"HOME": "", "CLAUDE_PLUGIN_DATA": self.target, "_UNLEASHED_PUBLISH_OK": "0"}
        body = ('printf "%s %s %s|%s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" '
                '"$_UNLEASHED_POINTER_STATE" "$_UNLEASHED_BASE_RESOLVED"')
        mutant = with_mutation(
            '        if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then',
            '        if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && _unleashed_home_ok; then',
            path=PATHS_C3)
        try:
            for shell in SHELLS:
                rc, out, err = run_shell(shell, body, env=env, sources=(PATHS_C3,))
                self.assertEqual(f"1 host-env none|{self.target}", out,
                                 f"{shell}: spec must resolve from the set variable: {err}")
                rc, out, err = run_shell(shell, body, env=env, sources=(mutant,))
                self.assertEqual("0 unresolved none|" + self.SENTINEL, out,
                                 f"{shell}: the MUTANT did not let HOME= suppress the variable")
        finally:
            os.unlink(mutant)

    # ── row 35 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_035_unwritable_target_still_resolves(self):
        """A readable but UNWRITABLE target still authenticates: OK=1, pointer, none, empty stderr;
        its writes no-op and the sourcing shell survives."""
        # Authentication is about TRUST, not utility: nothing in ENT/TGT/PCH requires the target be
        # writable. The mutant adds a writability clause; an 0500 target then refuses, which is
        # exactly the over-reach the row forbids.
        mutant = with_mutation(
            '    [ -d "$_ae_line" ] || return 1                   # names an EXISTING directory',
            '    { [ -d "$_ae_line" ] && [ -w "$_ae_line" ]; } || return 1',
            path=READER)
        # The braces matter: in `: > f 2>/dev/null` the failing redirect is processed BEFORE stderr
        # is redirected, so the shell's own "Permission denied" still escapes. The group form
        # silences it — and the shell surviving the failed write is itself half the oracle.
        post = ('\n{ : > "$_UNLEASHED_BASE_RESOLVED/probe"; } 2>/dev/null\n'
                'printf " alive"')
        try:
            for shell in SHELLS:
                self._fresh_store()
                self._write_entry(self.target)
                os.chmod(self.target, 0o500)
                try:
                    out, err = self._read(shell, post=post)
                    self.assertEqual(self._resolved() + " alive", out, f"{shell}: spec")
                    self.assertEqual("", err, f"{shell}: a resolution must be silent")
                    self.assertEqual([], os.listdir(self.target),
                                     f"{shell}: the write into the 0500 target must no-op")
                    out, _ = self._read(shell, sources=(AUTH, STORE, mutant, PUB))
                    self.assertEqual(self.STALE, out,
                                     f"{shell}: the MUTANT did not refuse the unwritable target")
                finally:
                    os.chmod(self.target, 0o700)
        finally:
            os.unlink(mutant)

    # ── row 50 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_050_store_creation_has_no_permissive_window(self):
        """No window exists in which another observer sees the store chain at 0755."""
        # `mkdir -m 700` passes the mode to mkdir(2), so the directory is 0700 from its very first
        # instant. The mutant creates then chmods — a REAL window (a whole fork+exec of /bin/chmod
        # wide) in which the directory is 0755 under umask 022. The observer is a polling thread:
        # timing-based by necessity, but the window is milliseconds wide and sampled ~60 times, so
        # a miss on every attempt is effectively impossible — and the spec side is deterministic
        # (0700 from birth means no sample can ever show anything else).
        mutant = with_mutation(
            '        if /bin/mkdir -m 700 "$_cs_d" 2>/dev/null; then',
            '        if /bin/mkdir "$_cs_d" 2>/dev/null && /bin/chmod 700 "$_cs_d" 2>/dev/null; then',
            path=STORE)
        top = os.path.join(self.home, ".claude")
        body = ('umask 022\ni=0\nwhile [ "$i" -lt 60 ]; do\n'
                f'  /bin/rm -rf "{top}"\n'
                f'  _unleashed_create_store "{self.store}" || exit 9\n'
                '  i=$((i+1))\ndone\nprintf ok')

        def observed_modes(shell, sources):
            modes, stop = set(), threading.Event()

            def watch():
                while not stop.is_set():
                    try:
                        modes.add(os.lstat(top).st_mode & 0o777)
                    except OSError:
                        pass
            t = threading.Thread(target=watch)
            t.start()
            try:
                rc, out, err = run_shell(shell, body, sources=sources)
            finally:
                stop.set()
                t.join()
            self.assertEqual("ok", out, f"{shell}: creation loop failed: {err}")
            return modes

        try:
            for shell in SHELLS:
                spec = observed_modes(shell, (AUTH, STORE, READER, PUB))
                self.assertIn(0o700, spec, f"{shell}: the observer never sampled the directory "
                                           "— the fixture cannot discriminate anything")
                self.assertEqual({0o700}, spec, f"{shell}: spec exposed a non-0700 window: {spec}")
                mut = observed_modes(shell, (AUTH, mutant, READER, PUB))
                self.assertIn(0o755, mut,
                              f"{shell}: the MUTANT's mkdir-then-chmod window went unobserved "
                              f"({mut}) — this row cannot fail")
        finally:
            os.unlink(mutant)

    # ── row 57 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_057_acl_probe_writes_nothing_anywhere(self):
        """The ACL probe creates nothing anywhere, and a pre-creation refusal creates nothing."""
        # ACL-6: authentication may not be established by attempting a write. The mutant probes by
        # write: its very first component is `/`, where the write fails, so the whole resolution
        # refuses — a healthy store degrades to `stale` — which is how a write-probing arm is
        # visible without littering. The spec side pins the other half: a full read leaves the
        # fixture tree byte-for-byte identical (no file created ANYWHERE under the scratch HOME).
        mutant = with_mutation(
            '_u_acl_ok() {\n'
            '    _u_acl_out="$(_u_acl_enumerate "$1")" || return 1   # a failed enumerator REFUSES\n'
            "    printf '%s\\n' \"$_u_acl_out\" | _u_acl_answer_ok\n"
            '}',
            '_u_acl_ok() {\n'
            '    ( umask 077; : > "$1/.row57-acl-write-probe" ) 2>/dev/null || return 1\n'
            '    /bin/rm -f -- "$1/.row57-acl-write-probe" 2>/dev/null\n'
            '    _u_acl_out="$(_u_acl_enumerate "$1")" || return 1\n'
            "    printf '%s\\n' \"$_u_acl_out\" | _u_acl_answer_ok\n"
            '}',
            path=AUTH)

        def tree():
            seen = set()
            for root, dirs, files in os.walk(self.home):
                for n in dirs + files:
                    seen.add(os.path.relpath(os.path.join(root, n), self.home))
            return seen

        try:
            for shell in SHELLS:
                self._fresh_store()
                self._write_entry(self.target)
                before = tree()
                out, err = self._read(shell)
                self.assertEqual(self._resolved(), out, f"{shell}: spec")
                self.assertEqual(before, tree(),
                                 f"{shell}: the spec resolution created or removed a file")
                out, _ = self._read(shell, sources=(mutant, STORE, READER, PUB))
                self.assertEqual(self.STALE, out,
                                 f"{shell}: the write-probing MUTANT resolved — this row cannot "
                                 "fail (ACL-6 has no teeth here)")
                self.assertEqual(before, tree(), f"{shell}: the mutant littered the fixture")
        finally:
            os.unlink(mutant)

    # ── rows 63 / 69 / 75 — the encoder, at the ENTRY level, on the real volume ──────────────────

    def _publish_pair(self, shell, first, second, sources):
        """Publish `first` then `second` (two processes, one store); returns their states."""
        self._fresh_store()
        s1, _ = self._publish(shell, first, sources=sources)
        s2, _ = self._publish(shell, second, sources=sources)
        return s1, s2

    def test_row_063_case_folding_encoder_merges_distinct_entries(self):
        """/Data/A and /Data/a produce distinct entries on a case-insensitive volume."""
        # ENC-4's teeth at the STORE level: the spec keys differ by more than case (`_ca` vs `a`),
        # so even a case-insensitive volume keeps two entries and the disagreement is REPORTED as
        # `conflict`. A case-folding encoder maps both spellings to one name: the second publisher
        # finds its own entry "already current" while holding a different base string — the exact
        # silent-second-store defect this design exists to remove.
        if not self._case_insensitive_volume():
            self.skipTest("requires a case-insensitive volume (macOS default)")
        os.makedirs(os.path.join(self.home, "Data", "A"))
        os.chmod(os.path.join(self.home, "Data"), 0o700)
        os.chmod(os.path.join(self.home, "Data", "A"), 0o700)
        val_upper = os.path.join(self.home, "Data", "A")
        val_lower = os.path.join(self.home, "Data", "a")   # the same directory, folded
        mutant = with_mutation(UPPER_TABLE, _upper_rows(lambda c: c.lower()), path=STORE)
        try:
            for shell in SHELLS:
                s1, s2 = self._publish_pair(shell, val_upper, val_lower,
                                            (AUTH, STORE, READER, PUB))
                self.assertEqual(("created", "conflict"), (s1, s2), f"{shell}: spec")
                self.assertEqual(2, len(self._entries()),
                                 f"{shell}: spec must keep two distinct entries")
                s1, s2 = self._publish_pair(shell, val_upper, val_lower,
                                            (AUTH, mutant, READER, PUB))
                self.assertEqual(("created", "current"), (s1, s2),
                                 f"{shell}: the case-folding MUTANT must merge the two spellings")
                self.assertEqual(1, len(self._entries()),
                                 f"{shell}: the MUTANT must produce one merged entry")
        finally:
            os.unlink(mutant)

    def test_row_069_underscore_lower_marker_collides_with_u_and_s(self):
        """/a_b vs /aUb, and /a/b vs /aSb, produce DISTINCT entries."""
        # `_<lower>` re-uses the `_u`/`_s` marker space: K("a_b")==K("aUb") and K("a/b")==K("aSb"),
        # so decoding is ambiguous and injectivity dies. Store-level: the second publisher of each
        # pair reports `current` against an entry holding a DIFFERENT base. This needs no special
        # volume — the collision is byte-exact.
        for name in ("a_b", "aUb", "aSb"):
            os.mkdir(os.path.join(self.home, name))
            os.chmod(os.path.join(self.home, name), 0o700)
        os.makedirs(os.path.join(self.home, "a", "b"))
        os.chmod(os.path.join(self.home, "a"), 0o700)
        os.chmod(os.path.join(self.home, "a", "b"), 0o700)
        pairs = [(os.path.join(self.home, "a_b"), os.path.join(self.home, "aUb")),
                 (os.path.join(self.home, "a", "b"), os.path.join(self.home, "aSb"))]
        mutant = with_mutation(UPPER_TABLE, _upper_rows(lambda c: "_" + c.lower()), path=STORE)
        try:
            for shell in SHELLS:
                for first, second in pairs:
                    s1, s2 = self._publish_pair(shell, first, second,
                                                (AUTH, STORE, READER, PUB))
                    self.assertEqual(("created", "conflict"), (s1, s2),
                                     f"{shell}: spec {first} vs {second}")
                    self.assertEqual(2, len(self._entries()), f"{shell}: two distinct entries")
                    s1, s2 = self._publish_pair(shell, first, second,
                                                (AUTH, mutant, READER, PUB))
                    self.assertEqual(("created", "current"), (s1, s2),
                                     f"{shell}: the `_<lower>` MUTANT must collide {second} "
                                     f"into {first}'s entry")
                    self.assertEqual(1, len(self._entries()), f"{shell}: one collided entry")
        finally:
            os.unlink(mutant)

    def test_row_075_two_pass_encoder_aliases_on_the_volume(self):
        """/Data/A and /Data/a produce distinct entries."""
        # The pre-31c two-pass form (`${v//_/_u}` then `${v//\//_s}`, no case handling) emits
        # upper-case bytes VERBATIM, so the two spellings' keys differ ONLY by case — one file on a
        # case-insensitive volume (round 31c's aliasing, executed). The spec's `_c<lower>` marker
        # keeps the names distinct beyond case. The mutant disables the walk (its loop bound goes
        # to 0) and emits the two-pass result instead — the exact normative form rounds 30-33
        # carried.
        if not self._case_insensitive_volume():
            self.skipTest("requires a case-insensitive volume (macOS default)")
        os.makedirs(os.path.join(self.home, "Data", "A"))
        os.chmod(os.path.join(self.home, "Data"), 0o700)
        os.chmod(os.path.join(self.home, "Data", "A"), 0o700)
        val_upper = os.path.join(self.home, "Data", "A")
        val_lower = os.path.join(self.home, "Data", "a")
        mutant = with_mutation(
            '    _uk_i=0\n'
            '    _uk_len=${#_uk_v}',
            '    _uk_out="${_uk_v//_/_u}"\n'
            '    _uk_out="${_uk_out//\\//_s}"\n'
            '    _uk_i=0\n'
            '    _uk_len=0',
            path=STORE)
        try:
            for shell in SHELLS:
                s1, s2 = self._publish_pair(shell, val_upper, val_lower,
                                            (AUTH, STORE, READER, PUB))
                self.assertEqual(("created", "conflict"), (s1, s2), f"{shell}: spec")
                self.assertEqual(2, len(self._entries()), f"{shell}: two distinct entries")
                s1, s2 = self._publish_pair(shell, val_upper, val_lower,
                                            (AUTH, mutant, READER, PUB))
                self.assertNotEqual("conflict", s2,
                                    f"{shell}: the two-pass MUTANT still reported the conflict — "
                                    "this row cannot fail")
                self.assertEqual(1, len(self._entries()),
                                 f"{shell}: the MUTANT's two case-variant names must alias to one "
                                 "file on this volume")
        finally:
            os.unlink(mutant)

    # ── row 81 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_081_budget_is_against_the_transient_name(self):
        """A key that fits `base.<key>` but overflows `.pub.<pid>.<uniq>.<key>` reports `failed`
        and creates nothing."""
        # NM-1 budgets the LONGEST name the publisher creates — the transient — so the refusal
        # comes at E3, BEFORE the store exists. The mutant budgets `base.<key>` instead: the same
        # publish then sails past E3, CREATES the store chain, and only the transient's open fails
        # (E6). Both report `failed`; the mutation is visible in what was created and in which
        # bounded diagnostic fired.
        # The pad is sized with the SHIPPED encoder, not a re-implementation: an earlier version of
        # this fixture recounted ENC-1 in Python and was off by one, which silently moved the key
        # onto E3's side of the boundary in BOTH builds — a fixture defect that read exactly like a
        # surviving mutant (review-verification discipline: the shipped code is the length oracle).
        rc, out, err = run_shell(
            "/bin/bash", f'_unleashed_key "{self.home}"; printf "%s" "${{#_UNLEASHED_KEY}}"')
        self.assertEqual(0, rc, err)
        pad = 250 - int(out) - 2                # enc(home) + 2 (the `_s`) + pad == 250
        self.assertGreater(pad, 0, "scratch HOME too deep for this fixture")
        value = os.path.join(self.home, "k" * pad)
        os.mkdir(value)
        os.chmod(value, 0o700)
        mutant = with_mutation(
            '    _bo_len=$(( 7 + ${#_bo_pid} + 5 + ${#_bo_key} ))',
            '    _bo_len=$(( 5 + ${#_bo_key} ))',
            path=STORE)
        try:
            for shell in SHELLS:
                self._fresh_store()
                shutil.rmtree(os.path.join(self.home, ".claude"))
                state, err = self._publish(shell, value)
                self.assertEqual("failed", state, f"{shell}: spec")
                self.assertIn("NAME_MAX here is", err, f"{shell}: E3 is the exit that must fire")
                self.assertFalse(os.path.exists(os.path.join(self.home, ".claude")),
                                 f"{shell}: E3 comes BEFORE store creation — nothing may exist")
                state, err = self._publish(shell, value, sources=(AUTH, mutant, READER, PUB))
                self.assertEqual("failed", state, f"{shell}: mutant still fails, later")
                self.assertNotIn("NAME_MAX here is", err,
                                 f"{shell}: the MUTANT must sail past E3 or this row cannot fail")
                self.assertTrue(os.path.isdir(self.store),
                                f"{shell}: the MUTANT must have created the store E3 forbids")
        finally:
            os.unlink(mutant)

    # ── row 90 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_090_inherited_read_only_ace_still_resolves(self):
        """An inherited read-only ACE, as MDM fleets carry, still RESOLVES: OK=1, pointer, none,
        empty stderr."""
        # The four INHERITANCE FLAGS are not rights. The mutant deletes their allowlist row, so a
        # propagated `allow list,search,file_inherit,directory_inherit` ACE refuses — and the
        # capability dies on every Mac that inherits ACLs. The fixture is a REAL inherited ACE
        # (chmod +a on the parent, child created after), driven through the production resolver to
        # the store-level outcome, not the arm-level verdict DarwinAclArm already covers.
        parent = os.path.join(self.home, "p_mdm")
        os.mkdir(parent)
        os.chmod(parent, 0o700)
        subprocess.run(["/bin/chmod", "+a",
                        "group:staff allow list,search,file_inherit,directory_inherit", parent],
                       check=True)
        child = os.path.join(parent, "child")
        os.mkdir(child)
        os.chmod(child, 0o700)
        mutant = with_mutation(
            "            file_inherit|directory_inherit|limit_inherit|only_inherit) : ;;\n",
            "", path=AUTH)
        try:
            for shell in SHELLS:
                self._fresh_store()
                self._write_entry(child)
                out, err = self._read(shell)
                self.assertEqual(f"1 pointer none|{child}", out, f"{shell}: spec")
                self.assertEqual("", err, f"{shell}: a resolution must be silent")
                out, _ = self._read(shell, sources=(mutant, STORE, READER, PUB))
                self.assertEqual(self.STALE, out,
                                 f"{shell}: the MUTANT (inheritance flags treated as rights) "
                                 "did not refuse — this row cannot fail")
        finally:
            os.unlink(mutant)

    # ── row 98 ────────────────────────────────────────────────────────────────────────────────────

    def test_row_098_writesecurity_in_the_allowlist_fails_open(self):
        """An `allow writesecurity` ACE for another principal yields sentinel, OK=0, unresolved,
        stale, one diagnostic — the allowlist admits exactly the seven read-only rights."""
        # N6-7's boundary from the other side: the seven-right row must not GROW. `writesecurity`
        # lets another principal rewrite the ACL itself, so a build whose allowlist admits it
        # resolves a store another uid can re-permission.
        subprocess.run(["/bin/chmod", "+a", "group:staff allow writesecurity", self.target],
                       check=True)
        mutant = with_mutation(
            '            execute|list|read|readattr|readextattr|readsecurity|search) : ;;',
            '            execute|list|read|readattr|readextattr|readsecurity|search|writesecurity) : ;;',
            path=AUTH)
        try:
            for shell in SHELLS:
                self._fresh_store()
                self._write_entry(self.target)
                out, err = self._read(shell)
                self.assertEqual(self.STALE, out, f"{shell}: spec")
                self.assertEqual(1, len(err.splitlines()), f"{shell}: exactly one diagnostic")
                out, _ = self._read(shell, sources=(mutant, STORE, READER, PUB))
                self.assertEqual(self._resolved(), out,
                                 f"{shell}: the widened-allowlist MUTANT did not resolve — "
                                 "this row cannot fail")
        finally:
            os.unlink(mutant)

    # ── row 105 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_105_own_entry_clause_must_not_skip_the_post_scan_exits(self):
        """An AUTHENTICATING own entry beside a malformed foreign entry: the ordered exit P2
        reports `stale`; an early `current` return never meets the foreign entry."""
        # Round 108's corrected fixture: the own entry must PASS the complete skip predicate (0600,
        # encoded name, single line) so PUB-7 rewrites nothing — a 0644 own entry is republished
        # and the specification itself reports `created`, which no mutation could discriminate.
        mutant = with_mutation(
            '    if _unleashed_auth_entry "$_pb_entry"; then\n'
            '        _pb_wrote=0\n'
            '    else',
            '    if _unleashed_auth_entry "$_pb_entry"; then\n'
            '        _unleashed_pub_state current\n'
            '        return 0\n'
            '    else',
            path=PUB)
        try:
            for shell in SHELLS:
                self._fresh_store()
                own = self._write_entry(self.target)          # authenticating, 0600, skip-worthy
                foreign = os.path.join(self.store, "base.zzz")
                with open(foreign, "w") as fh:                # malformed: not even absolute
                    fh.write("not-a-path\n")
                os.chmod(foreign, 0o600)
                before = os.stat(own).st_mtime_ns
                state, err = self._publish(shell, self.target)
                self.assertEqual("stale", state, f"{shell}: spec (P2, ordered)")
                self.assertEqual("", err, f"{shell}: a publisher reporting stale is silent")
                self.assertEqual(before, os.stat(own).st_mtime_ns,
                                 f"{shell}: the skip predicate passed — nothing may be rewritten")
                state, _ = self._publish(shell, self.target, sources=(AUTH, STORE, READER, mutant))
                self.assertEqual("current", state,
                                 f"{shell}: the early-return MUTANT must never meet the foreign "
                                 "entry — this row cannot fail")
        finally:
            os.unlink(mutant)

    # ── row 111 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_111_symlinked_store_ancestor_refuses(self):
        """A symlinked ancestor of the store yields sentinel, OK=0, unresolved, stale, one
        diagnostic — rule -1 via the chain walk's per-component symlink clause."""
        # Unlike row 25's target (masked by a second clause), the STORE ANCESTOR has exactly one
        # guard: the walk's `[ -L ]`. Dropping it resolves a store reached through a symlink —
        # rule -1 and RD-10(d) both die with that one line.
        real = os.path.join(self.home, "real-um")
        os.mkdir(real)
        os.chmod(real, 0o700)
        real_bases = os.path.join(real, "bases")
        os.mkdir(real_bases)
        os.chmod(real_bases, 0o700)
        top = os.path.join(self.home, ".claude")
        os.mkdir(top)
        os.chmod(top, 0o700)
        os.symlink(real, os.path.join(top, "unleashed-mail"))   # the symlinked ancestor
        self._write_entry(self.target, store=real_bases)
        mutant = with_mutation(
            '        [ -L "$_u_ac_c" ] && return 1                   # never a symbolic link',
            '        :', path=AUTH)
        try:
            for shell in SHELLS:
                out, err = self._read(shell)
                self.assertEqual(self.STALE, out, f"{shell}: spec (rule -1)")
                self.assertEqual(1, len(err.splitlines()), f"{shell}: exactly one diagnostic")
                out, _ = self._read(shell, sources=(mutant, STORE, READER, PUB))
                self.assertEqual(self._resolved(), out,
                                 f"{shell}: the MUTANT did not resolve through the symlinked "
                                 "ancestor — this row cannot fail")
        finally:
            os.unlink(mutant)

    # ── row 118 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_118_no_write_before_the_target_chain_authenticates(self):
        """A base beneath a 0775 component publishes NOTHING and reports `failed`; writing first
        leaves a durable entry every reader refuses and ST-8 forbids deleting."""
        # E2 is ordered BEFORE every write. The mutant deletes the pre-write target-chain gate;
        # P1 still reports `failed` afterwards, so the STATE alone cannot discriminate — what
        # discriminates is the store that now exists and the entry left inside it.
        bad = os.path.join(self.home, "bp")
        os.mkdir(bad)
        os.chmod(bad, 0o775)                      # group-writable: the chain must refuse it
        tgt = os.path.join(bad, "d")
        os.mkdir(tgt)
        os.chmod(tgt, 0o700)
        mutant = with_mutation(
            '    if ! _unleashed_auth_chain "$_pb_value"; then\n'
            '        _unleashed_pub_failed "the plugin-data base\'s chain does not authenticate"; return 0\n'
            '    fi',
            '    :', path=PUB)
        try:
            for shell in SHELLS:
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                state, err = self._publish(shell, tgt)
                self.assertEqual("failed", state, f"{shell}: spec (E2)")
                self.assertIn("chain does not authenticate", err, f"{shell}: E2's diagnostic")
                self.assertFalse(os.path.exists(os.path.join(self.home, ".claude")),
                                 f"{shell}: E2 composes and creates NOTHING")
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                state, err = self._publish(shell, tgt, sources=(AUTH, STORE, READER, mutant))
                self.assertEqual("failed", state, f"{shell}: the mutant fails too — later (P1)")
                self.assertIn("own plugin-state entry is missing or unusable", err,
                              f"{shell}: the MUTANT must reach P1, not E2")
                self.assertEqual(1, len(self._entries()),
                                 f"{shell}: the MUTANT must leave the durable entry the row "
                                 "forbids — otherwise this row cannot fail")
        finally:
            os.unlink(mutant)

    # ── row 125 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_125_no_rollback_of_created_ancestors(self):
        """With `.claude` creatable and `unleashed-mail` failing, the publisher reports `failed`
        and LEAVES `.claude` in place — ST-3/ST-4 forbid the plugin removing directories."""
        # The failure AFTER a first safe creation is driven through the enumerator-output seam:
        # the mid component's ACL answer fails, so E4 fires after `.claude` (and `unleashed-mail`)
        # were created. The mutant "cleans up" with rm -rf — deleting paths the plugin has no
        # right to delete. Both builds report `failed`; the directory left behind is the oracle.
        mid = os.path.join(self.home, ".claude", "unleashed-mail")
        pre = ('_u_acl_enumerate() {\n'
               f'  case "$1" in\n    "{mid}") return 1 ;;\n'
               '    *) /bin/ls -lde -- "$1" 2>/dev/null ;;\n  esac\n}')
        mutant = with_mutation(
            '    if ! _unleashed_create_store "$_pb_store"; then\n'
            '        _unleashed_pub_failed "the plugin-state store could not be created or does not authenticate"\n'
            '        return 0\n'
            '    fi',
            '    if ! _unleashed_create_store "$_pb_store"; then\n'
            '        /bin/rm -rf -- "$_cs_top" 2>/dev/null\n'
            '        _unleashed_pub_failed "the plugin-state store could not be created or does not authenticate"\n'
            '        return 0\n'
            '    fi',
            path=PUB)
        top = os.path.join(self.home, ".claude")
        try:
            for shell in SHELLS:
                shutil.rmtree(top, ignore_errors=True)
                state, err = self._publish(shell, self.target, pre=pre)
                self.assertEqual("failed", state, f"{shell}: spec (E4)")
                self.assertIn("could not be created", err, f"{shell}: E4's diagnostic")
                self.assertTrue(os.path.isdir(top),
                                f"{shell}: `.claude` must be LEFT IN PLACE on failure")
                shutil.rmtree(top, ignore_errors=True)
                state, _ = self._publish(shell, self.target, pre=pre,
                                         sources=(AUTH, STORE, READER, mutant))
                self.assertEqual("failed", state, f"{shell}: mutant also fails")
                self.assertFalse(os.path.exists(top),
                                 f"{shell}: the rollback MUTANT must have deleted `.claude` — "
                                 "otherwise this row cannot fail")
        finally:
            os.unlink(mutant)

    # ── row 131 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_131_failed_identity_probe_refuses_the_publisher(self):
        """With the identity probe failing and the enumerator present, the publisher REFUSES:
        `failed`, one diagnostic, no entry written."""
        # Driven through the IDENTITY-PROBE SEAM of §7 step 3f(iii): `id` is invoked by absolute
        # path, so an unprivileged harness cannot fail it without the seam. AUTH-1(h)'s carve-out
        # is for a platform with NO enumerator; the mutant extends it to a PRESENT-BUT-FAILED
        # probe by neutering the ACL clause when the principal cannot be resolved — fail-open.
        pre = "_u_identity_probe() { return 1; }"
        mutant = with_mutation(
            '    _u_principal || return 1',
            '    if ! { [ -n "${_U_PRINCIPAL+set}" ] || _u_principal; }; then\n'
            '        _u_acl_ok() { return 0; }\n'
            '    fi',
            path=AUTH)
        try:
            for shell in SHELLS:
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                state, err = self._publish(shell, self.target, pre=pre)
                self.assertEqual("failed", state, f"{shell}: spec")
                self.assertEqual(1, len(err.splitlines()), f"{shell}: exactly one diagnostic")
                self.assertEqual([], self._entries(), f"{shell}: no entry may be written")
                state, err = self._publish(shell, self.target, pre=pre,
                                           sources=(mutant, STORE, READER, PUB))
                self.assertEqual("created", state,
                                 f"{shell}: the carve-out MUTANT must publish into a store it "
                                 f"could not evaluate — otherwise this row cannot fail: {err}")
                self.assertEqual(1, len(self._entries()), f"{shell}: the mutant's entry")
        finally:
            os.unlink(mutant)

    # ── row 137 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_137_entry_mv_by_absolute_path_stays_atomic(self):
        """A SYNCHRONISED PATH `mv` shim removes the existing destination and blocks while the
        harness observes it ABSENT — which ST-7's absence guarantee forbids; `/bin/mv` never
        consults PATH, so the shim is unreachable in the shipped build."""
        # The synchronisation is part of the row: the shim removes the EXISTING destination,
        # signals, BLOCKS until released, then completes via the real /bin/mv — so the observation
        # is deterministic, not a race. run_shell cannot host a blocking publisher, so this test
        # builds the same sourced preamble by hand and drives it through subprocess.Popen.
        flags = os.path.join(self.home, "flags")
        shimdir = os.path.join(self.home, "bin")
        os.makedirs(flags)
        os.makedirs(shimdir)
        shim = os.path.join(shimdir, "mv")
        with open(shim, "w") as fh:
            fh.write("#!/bin/sh\n"
                     "# row 137: called as `mv -f <src> <dest>`\n"
                     f'/bin/rm -f -- "$3"\n'
                     f': > "{flags}/mv-called"\n'
                     f'while [ ! -e "{flags}/mv-go" ]; do /bin/sleep 0.02; done\n'
                     'exec /bin/mv "$@"\n')
        os.chmod(shim, 0o755)
        mutant = with_mutation(
            '        if ! /bin/mv -f "$_UNLEASHED_TRANSIENT" "$_pb_entry" >/dev/null 2>&1; then',
            '        if ! mv -f "$_UNLEASHED_TRANSIENT" "$_pb_entry" >/dev/null 2>&1; then',
            path=PUB)
        env = dict(os.environ)
        env["PATH"] = shimdir + os.pathsep + env.get("PATH", "")

        def arm(shell, sources):
            src = "".join(f'. "{s}"\n' for s in sources)
            src += (f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                    'printf "%s" "$_UNLEASHED_POINTER_STATE"')
            return subprocess.Popen([shell, "-c", src], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, env=env)

        try:
            for shell in SHELLS:
                # Fixture: a published entry whose mode was knocked to 0644, so the publisher must
                # republish it — the mv under test replaces an EXISTING destination a reader has
                # already seen.
                self._fresh_store()
                state, _ = self._publish(shell, self.target)
                self.assertEqual("created", state, f"{shell}: fixture publish")
                entry = os.path.join(self.store, self._entries()[0])
                for f in ("mv-called", "mv-go"):
                    try:
                        os.unlink(os.path.join(flags, f))
                    except FileNotFoundError:
                        pass

                os.chmod(entry, 0o644)
                proc = arm(shell, (AUTH, STORE, READER, PUB))
                try:
                    out, _ = proc.communicate(timeout=60)
                finally:
                    proc.kill()
                self.assertEqual("created", out, f"{shell}: spec republish")
                self.assertFalse(os.path.exists(os.path.join(flags, "mv-called")),
                                 f"{shell}: /bin/mv must never consult PATH")
                self.assertTrue(os.path.exists(entry), f"{shell}: spec entry present")

                os.chmod(entry, 0o644)
                proc = arm(shell, (AUTH, STORE, READER, mutant))
                absent_seen = None
                try:
                    deadline = time.time() + 30
                    while time.time() < deadline:
                        if os.path.exists(os.path.join(flags, "mv-called")):
                            break
                        time.sleep(0.01)
                    self.assertTrue(os.path.exists(os.path.join(flags, "mv-called")),
                                    f"{shell}: the PATH'd MUTANT never hit the shim — this row "
                                    "cannot fail")
                    # The synchronised observation: the shim holds the publisher mid-`mv`.
                    absent_seen = not os.path.exists(entry)
                finally:
                    with open(os.path.join(flags, "mv-go"), "w"):
                        pass
                    try:
                        out, _ = proc.communicate(timeout=60)
                    finally:
                        proc.kill()
                self.assertTrue(absent_seen,
                                f"{shell}: a reader observed the entry ABSENT mid-publish — "
                                "ST-7's absence guarantee is broken by the PATH'd mv")
                self.assertEqual("created", out, f"{shell}: the mutant completes after release")
        finally:
            os.unlink(mutant)

    # ── row 143 ───────────────────────────────────────────────────────────────────────────────────

    def test_row_143_stat_scratch_collision_diverges_the_arms(self):
        """One identical chain, two verdicts: the bash arm REFUSES and the zsh arm RESOLVES —
        AE-1's arm equivalence is the oracle, and no single-shell cell can see it."""
        # FAM-5's teeth: `_u_stat`'s bash arm gets its scratch renamed to the chain walk's
        # `_u_ac_rest`. A POSIX function has no locals, so every `_u_stat` call mid-walk overwrites
        # the walk's remaining-path state; the zsh arm uses the `zstat` builtin, never touches the
        # name, and is untouched. The assertions compare the ARMS to each other, not one arm to a
        # constant — that is what makes this row's class expensive and this test able to see it.
        mutant = with_mutation(
            '        _u_st_rest="${_u_st_raw#* }"; _U_SIZE="${_u_st_rest%% *}"; '
            '_U_UID="${_u_st_rest##* }"',
            '        _u_ac_rest="${_u_st_raw#* }"; _U_SIZE="${_u_ac_rest%% *}"; '
            '_U_UID="${_u_ac_rest##* }"',
            path=AUTH)
        try:
            self._fresh_store()
            self._write_entry(self.target)
            spec = {}
            mut = {}
            for shell in SHELLS:
                spec[shell], _ = self._read(shell)
                mut[shell], _ = self._read(shell, sources=(mutant, STORE, READER, PUB))
            self.assertEqual(spec["/bin/bash"], spec["/bin/zsh"],
                             f"AE-1: the shipped arms disagree: {spec}")
            self.assertEqual(self._resolved(), spec["/bin/bash"], "spec resolves")
            self.assertEqual(self._resolved(), mut["/bin/zsh"],
                             "the zsh arm must be UNAFFECTED — the divergence is the point")
            self.assertEqual(self.STALE, mut["/bin/bash"],
                             "the bash arm must REFUSE under the collision")
            self.assertNotEqual(mut["/bin/bash"], mut["/bin/zsh"],
                                "the MUTANT arms must diverge — this row cannot fail otherwise")
        finally:
            os.unlink(mutant)


if __name__ == "__main__":
    unittest.main()


# ==================================================================================================
# Chunk 4
# ==================================================================================================
#!/usr/bin/env python3
"""COREDEV-2617 mutant-table rows, chunk 4 — EXECUTED mutation tests.

Every covered-new row here was RUN: the shipped build and the row's mutant build, in BOTH
/bin/bash and /bin/zsh, and the outcomes differ (except where a row itself documents a
single-shell oracle — row 119). Rows whose obligation lives outside the four state libraries
are reported in the campaign table, not faked here.
"""

import os
import shutil
import tempfile
import unittest


#: The five-copy family files (rows 51/58/92/99 constrain the shipped wiring, which exists).
LIBDIR = os.path.dirname(AUTH)
PATHS_C4 = os.path.join(LIBDIR, "paths.sh")
MARKER = os.path.join(LIBDIR, "marker.sh")
CONTEXT = os.path.join(LIBDIR, "context.sh")
LOG = os.path.join(LIBDIR, "log.sh")
BRIDGE_C4 = os.path.join(LIBDIR, "agent-env-bridge.sh")
ROOT2 = os.path.dirname(os.path.dirname(LIBDIR))          # repo root, for the bridge's $2

SENTINEL = "/dev/null/unresolved-plugin-base"


@unittest.skipUnless(DARWIN, "the Darwin ACL arm; the Linux arms are unmeasured by design")
class RowsChunk4(unittest.TestCase):
    """Mutant-table rows 4, 10, 42, 51, 58, 64, 70, 76, 92, 99, 112, 119, 126, 132, 138, 144, 151."""

    #: The store-level outcome, N6-6's tuple.
    OUTP = 'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"'
    #: Reset between publisher/reader calls in one body.
    RESET = ('unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE '
             '_UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL\n')

    def setUp(self):
        # A scratch HOME under ~/.claude so no test reads or writes the developer's real store
        # (§7 step 3f(i)); the family-file tests re-point $HOME here, never at the real one.
        self.home = scratch_home("rc4.2617.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.target = os.path.join(self.home, "target")
        os.makedirs(self.target)
        os.chmod(self.target, 0o700)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    # ── shared scaffolding ────────────────────────────────────────────────────────────────────

    def _wipe(self):
        shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)

    def _mkstore(self):
        return (f'_unleashed_name_max "{self.store}" >/dev/null || exit 9\n'
                f'_unleashed_create_store "{self.store}" || exit 9\n')

    def _entry(self, t=None):
        t = t or self.target
        return (f'_unleashed_key "{t}"\n'
                f'printf "%s\\n" "{t}" > "{self.store}/base.$_UNLEASHED_KEY"\n'
                f'/bin/chmod 600 "{self.store}/base.$_UNLEASHED_KEY"\n')

    def _diags(self, err):
        """Diagnostic lines — the one-diagnostic clauses count these, never raw stderr bytes."""
        return [l for l in err.splitlines() if l.startswith("unleashed-mail:")]

    @staticmethod
    def _comps(path):
        """Components of an absolute path's chain, `/` down to and including the path (PCH-1)."""
        return 1 + len([s for s in path.split("/") if s])

    # ── row 4 ─────────────────────────────────────────────────────────────────────────────────

    def test_row_004_multiline_entry(self):
        """Row 4: a two-line entry yields sentinel, OK=0, SOURCE=unresolved, stale, one diagnostic, and a conforming entry beside it does not win."""
        # The mutation drops ENT-2 clause (2), the byte-count check — the only clause that sees
        # the second line, since `read` stops at the first newline in both shells.
        mutant = with_mutation(
            '    [ "$_U_SIZE" = "$(( _ae_bytes + 1 ))" ] || return 1                        # (2)',
            '    :                                                                          # (2)',
            path=READER)
        two_line = (f'_unleashed_key "{self.target}"\n'
                    f'printf "%s\\njunk\\n" "{self.target}" > "{self.store}/base.$_UNLEASHED_KEY"\n'
                    f'/bin/chmod 600 "{self.store}/base.$_UNLEASHED_KEY"\n')
        t2 = os.path.join(self.home, "t2")
        try:
            for shell in SHELLS:
                # The shipped build refuses with the full store-level tuple and ONE diagnostic.
                self._wipe()
                body = (self._mkstore() + two_line
                        + f'_unleashed_read_store "{self.store}"\n'
                        + self.OUTP + '; printf " %s" "$_UNLEASHED_BASE_RESOLVED"')
                rc, out, err = run_shell(shell, body)
                self.assertEqual(f"0 unresolved stale {SENTINEL}", out, f"{shell}: {err}")
                self.assertEqual(1, len(self._diags(err)), f"{shell}: diagnostic count")
                # A conforming entry BESIDE the two-line one must NOT win (rule 1).
                self._wipe()
                body = (self._mkstore() + two_line
                        + f'/bin/mkdir -p "{t2}"; /bin/chmod 700 "{t2}"\n' + self._entry(t2)
                        + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                rc, out, err = run_shell(shell, body)
                self.assertEqual("0 unresolved stale", out, f"{shell}: the good entry won")
                # The CONTROL: under the mutation the same two-line entry RESOLVES.
                self._wipe()
                body = (self._mkstore() + two_line
                        + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                rc, out, err = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("1 pointer none", out,
                                 f"{shell}: the CONTROL did not fail — clause (2) is not load-bearing")
        finally:
            os.unlink(mutant)

    # ── row 10 ────────────────────────────────────────────────────────────────────────────────

    def test_row_010_nul_entry(self):
        """Row 10: an entry holding an embedded NUL yields sentinel, OK=0, unresolved, stale, one diagnostic, and a conforming entry beside it does not win."""
        # ENT-2's NUL rejection is clauses (2)+(3) jointly — bash truncates at the NUL (caught by
        # the byte count), zsh keeps it (caught by the zsh-only test) — so "drop the NUL
        # rejection" is BOTH substitutions, chained. Each shell then needs its own fixture,
        # because the fail-open path differs: bash's truncated line matches the PLAIN key, zsh's
        # kept-NUL line matches the _x00-suffixed key (ENC-1: bytes < 0x20 encode as _x<hh>).
        m1 = with_mutation(
            '    [ "$_U_SIZE" = "$(( _ae_bytes + 1 ))" ] || return 1                        # (2)',
            '    :                                                                          # (2)',
            path=READER)
        mutant = with_mutation(
            "        case \"$_ae_line\" in *$'\\0'*) return 1 ;; esac                          # (3)",
            "        :                                                                         # (3)",
            path=m1)
        os.unlink(m1)
        # NUL-bearing entry content: <target>NUL\n, written by printf's FORMAT (both shells emit
        # a real NUL for \0 in the format string).
        nul_a = (f'_unleashed_key "{self.target}"\n'
                 f'printf "%s\\0\\n" "{self.target}" > "{self.store}/base.$_UNLEASHED_KEY"\n'
                 f'/bin/chmod 600 "{self.store}/base.$_UNLEASHED_KEY"\n')
        nul_b = (f'_unleashed_key "{self.target}"\n'
                 f'printf "%s\\0\\n" "{self.target}" > "{self.store}/base.${{_UNLEASHED_KEY}}_x00"\n'
                 f'/bin/chmod 600 "{self.store}/base.${{_UNLEASHED_KEY}}_x00"\n')
        t2 = os.path.join(self.home, "t2")
        try:
            for shell in SHELLS:
                for fixture in (nul_a, nul_b):
                    self._wipe()
                    body = (self._mkstore() + fixture
                            + f'_unleashed_read_store "{self.store}"\n'
                            + self.OUTP + '; printf " %s" "$_UNLEASHED_BASE_RESOLVED"')
                    rc, out, err = run_shell(shell, body)
                    self.assertEqual(f"0 unresolved stale {SENTINEL}", out,
                                     f"{shell}: shipped build accepted a NUL entry: {err}")
                    self.assertEqual(1, len(self._diags(err)), f"{shell}: diagnostic count")
                # A conforming entry beside the NUL one must NOT win (rule 1).
                self._wipe()
                body = (self._mkstore() + nul_a
                        + f'/bin/mkdir -p "{t2}"; /bin/chmod 700 "{t2}"\n' + self._entry(t2)
                        + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                rc, out, _ = run_shell(shell, body)
                self.assertEqual("0 unresolved stale", out, f"{shell}: the good entry won")
                # The CONTROL: fixture A fails open in bash (truncated line = plain key), fixture
                # B in zsh (kept-NUL line = _x00 key; the kernel truncates the C string at the
                # NUL, so -d and the chain walk see the real directory — measured).
                fixture = nul_a if shell == "/bin/bash" else nul_b
                self._wipe()
                body = (self._mkstore() + fixture
                        + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("1 pointer none", out,
                                 f"{shell}: the CONTROL did not fail — the NUL rejection is not load-bearing")
        finally:
            os.unlink(mutant)

    # ── row 42 ────────────────────────────────────────────────────────────────────────────────

    def test_row_042_membership_accumulator(self):
        """Row 42: two authenticating entries whose values are <S>/b* <S>/c and <S>/c — rule 2 conflict under counting; a space-delimited membership accumulator counts ONE and resolves."""
        # The documented membership form (§4.2 round-30): the accumulator holds the containing
        # value when the contained one is tested, and the trailing space-delimited run matches.
        # The containing value must be SCANNED FIRST, and it is: 'b' sorts before 'c' in the
        # encoded names.
        mutant = with_mutation(
            '            _UNLEASHED_AUTHED=$(( _UNLEASHED_AUTHED + 1 ))\n'
            '            _UNLEASHED_WINNER="$_ae_line"            # the resolved value, not the path',
            '            case " ${_UNLEASHED_ACC-} " in\n'
            '                *" $_ae_line "*) : ;;\n'
            '                *) _UNLEASHED_ACC="${_UNLEASHED_ACC-} $_ae_line"\n'
            '                   _UNLEASHED_AUTHED=$(( _UNLEASHED_AUTHED + 1 )) ;;\n'
            '            esac\n'
            '            _UNLEASHED_WINNER="$_ae_line"            # the resolved value, not the path',
            path=READER)
        v1 = f"{self.home}/b* {self.home}/c"
        v2 = f"{self.home}/c"
        seed = (f'/bin/mkdir -p "{v1}"\n'
                f'/bin/mkdir -p "{v2}"\n'
                f'_unleashed_key "{v1}"\n'
                f'printf "%s\\n" "{v1}" > "{self.store}/base.$_UNLEASHED_KEY"\n'
                f'/bin/chmod 600 "{self.store}/base.$_UNLEASHED_KEY"\n'
                f'_unleashed_key "{v2}"\n'
                f'printf "%s\\n" "{v2}" > "{self.store}/base.$_UNLEASHED_KEY"\n'
                f'/bin/chmod 600 "{self.store}/base.$_UNLEASHED_KEY"\n')
        try:
            for shell in SHELLS:
                self._wipe()
                body = (self._mkstore() + seed
                        + f'_unleashed_read_store "{self.store}"\n' + self.OUTP)
                rc, out, err = run_shell(shell, body)
                self.assertEqual("0 unresolved conflict", out, f"{shell}: {err}")
                self.assertEqual(1, len(self._diags(err)), f"{shell}: diagnostic count")
                self._wipe()
                body = (self._mkstore() + seed
                        + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("1 pointer none", out,
                                 f"{shell}: the CONTROL did not fail — the membership form was not reproduced")
        finally:
            os.unlink(mutant)

    # ── row 51 ────────────────────────────────────────────────────────────────────────────────

    def test_row_051_entries_directly_in_unleashed_mail(self):
        """Row 51: after a publish the entries live in .../unleashed-mail/bases/ and THAT directory is 0700 asserted directly; unleashed-mail itself may be 0755."""
        # The composition site is paths.sh's step-1 publish. `POINTER_STATE=created` is true of
        # both implementations (round 104) and discriminates nothing — the oracle is WHERE the
        # entry sits and the MODE of the directory holding it.
        mutant = with_mutation(
            '                _unleashed_publish "${HOME:-}/.claude/unleashed-mail/bases" "$CLAUDE_PLUGIN_DATA"',
            '                _unleashed_publish "${HOME:-}/.claude/unleashed-mail" "$CLAUDE_PLUGIN_DATA"',
            path=PATHS_C4)
        um = os.path.join(self.home, ".claude", "unleashed-mail")
        try:
            for shell in SHELLS:
                for paths_file, is_mutant in ((PATHS_C4, False), (mutant, True)):
                    self._wipe()
                    os.makedirs(um)
                    os.chmod(os.path.join(self.home, ".claude"), 0o700)
                    os.chmod(um, 0o755)          # the legacy layout ST-4 accepts
                    body = (f'export HOME="{self.home}"\n'
                            f'export CLAUDE_PLUGIN_DATA="{self.target}"\n'
                            'unset _UNLEASHED_PUBLISH_OK _UNLEASHED_BASE_OK _UNLEASHED_PATHS_SH_LOADED\n'
                            '_UNLEASHED_STATE_LOADED=1; _UNLEASHED_STATE_RC=0\n'
                            f'. "{paths_file}"\n' + self.OUTP)
                    rc, out, err = run_shell(shell, body)
                    self.assertEqual("1 host-env created", out, f"{shell}: {err}")
                    direct = [f for f in os.listdir(um) if f.startswith("base.")]
                    if not is_mutant:
                        self.assertTrue(os.path.isdir(self.store), f"{shell}: bases/ missing")
                        self.assertEqual(0o700, os.stat(self.store).st_mode & 0o777,
                                         f"{shell}: bases/ is not exactly 0700")
                        self.assertEqual(1, len([f for f in os.listdir(self.store)
                                                 if f.startswith("base.")]), f"{shell}")
                        self.assertEqual([], direct,
                                         f"{shell}: an entry sits directly in unleashed-mail")
                    else:
                        # The mutation puts the entry in the 0755 directory and the exact-0700
                        # store rule is enforced on nothing.
                        self.assertFalse(os.path.exists(self.store), f"{shell}: CONTROL made bases/")
                        self.assertEqual(1, len(direct),
                                         f"{shell}: the CONTROL did not fail")
                        self.assertEqual(0o755, os.stat(um).st_mode & 0o777, f"{shell}")
        finally:
            os.unlink(mutant)

    # ── row 58 ────────────────────────────────────────────────────────────────────────────────

    def test_row_058_config_dir_root(self):
        """Row 58: publisher and reader reach the SAME verdict in different environments."""
        # The mutation admits a second store root conditional on CLAUDE_CONFIG_DIR at both of
        # paths.sh's composition sites. ACL-7's principle at the store level: a verdict must be a
        # property of the machine, so the same store must be consulted whether or not the
        # variable is present — under the mutation a publisher that saw the variable and a reader
        # that did not use DIFFERENT stores and disagree.
        m1 = with_mutation(
            '                _unleashed_publish "${HOME:-}/.claude/unleashed-mail/bases" "$CLAUDE_PLUGIN_DATA"',
            '                _unleashed_publish "${CLAUDE_CONFIG_DIR:-${HOME:-}/.claude}/unleashed-mail/bases" "$CLAUDE_PLUGIN_DATA"',
            path=PATHS_C4)
        mutant = with_mutation(
            '            _unleashed_read_store "${HOME:-}/.claude/unleashed-mail/bases"',
            '            _unleashed_read_store "${CLAUDE_CONFIG_DIR:-${HOME:-}/.claude}/unleashed-mail/bases"',
            path=m1)
        os.unlink(m1)
        cfg = os.path.join(self.home, "cfg")

        def family(shell, paths_file, plugin_data, cfg_set):
            lines = [f'export HOME="{self.home}"',
                     'unset _UNLEASHED_PUBLISH_OK _UNLEASHED_BASE_OK _UNLEASHED_PATHS_SH_LOADED',
                     '_UNLEASHED_STATE_LOADED=1; _UNLEASHED_STATE_RC=0',
                     (f'export CLAUDE_PLUGIN_DATA="{plugin_data}"' if plugin_data
                      else 'unset CLAUDE_PLUGIN_DATA'),
                     (f'export CLAUDE_CONFIG_DIR="{cfg}"' if cfg_set
                      else 'unset CLAUDE_CONFIG_DIR'),
                     f'. "{paths_file}"',
                     self.OUTP]
            rc, out, err = run_shell(shell, "\n".join(lines))
            return out
        try:
            for shell in SHELLS:
                for paths_file, is_mutant in ((PATHS_C4, False), (mutant, True)):
                    self._wipe()
                    shutil.rmtree(cfg, ignore_errors=True)
                    os.makedirs(cfg)
                    os.chmod(cfg, 0o700)
                    pub = family(shell, paths_file, self.target, cfg_set=True)
                    self.assertEqual("1 host-env created", pub, f"{shell}: publish failed")
                    v_env = family(shell, paths_file, None, cfg_set=True)
                    v_noenv = family(shell, paths_file, None, cfg_set=False)
                    if not is_mutant:
                        self.assertEqual("1 pointer none", v_env, f"{shell}")
                        self.assertEqual(v_env, v_noenv,
                                         f"{shell}: the verdict depends on the environment")
                    else:
                        self.assertEqual("1 pointer none", v_env, f"{shell}")
                        self.assertEqual("0 unresolved none", v_noenv,
                                         f"{shell}: the CONTROL did not fail — the root is not env-conditioned")
        finally:
            os.unlink(mutant)

    # ── row 64 ────────────────────────────────────────────────────────────────────────────────

    def test_row_064_conflict_diagnostic_paths(self):
        """Row 64: no absolute path reaches stderr on a conflict."""
        # ENC-10/RD-6: an entry name is a lossless encoding of a path, and the conflict
        # diagnostic must name neither the targets nor the entry names. The mutation appends the
        # winning target to the diagnostic.
        mutant = with_mutation(
            '        _unleashed_unresolved conflict "two or more plugin-state entries disagree"',
            '        _unleashed_unresolved conflict "two or more plugin-state entries disagree: $_UNLEASHED_WINNER"',
            path=READER)
        t2 = os.path.join(self.home, "t2")
        seed = (f'/bin/mkdir -p "{t2}"; /bin/chmod 700 "{t2}"\n'
                + self._entry() + self._entry(t2))
        try:
            for shell in SHELLS:
                self._wipe()
                body = self._mkstore() + seed + f'_unleashed_read_store "{self.store}"\n' + self.OUTP
                rc, out, err = run_shell(shell, body)
                self.assertEqual("0 unresolved conflict", out, f"{shell}")
                self.assertEqual(1, len(self._diags(err)), f"{shell}: diagnostic count")
                self.assertNotIn("/", "".join(self._diags(err)),
                                 f"{shell}: an absolute path reached stderr: {err!r}")
                self._wipe()
                rc, out, err = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("0 unresolved conflict", out, f"{shell}")
                self.assertIn(self.home, err,
                              f"{shell}: the CONTROL did not fail — the diagnostic leaks nothing")
        finally:
            os.unlink(mutant)

    # ── row 70 ────────────────────────────────────────────────────────────────────────────────

    def test_row_070_orphan_transient_enumerated(self):
        """Row 70: a crash-orphaned .pub.* temporary changes no resolution."""
        # RD-9: transients lie outside the `base.*` glob BY CONSTRUCTION. The mutation widens the
        # enumeration to `.pub.*`, and the orphan then fails ENT-3's name check and poisons the
        # store (rule 1) — a resolution a conforming reader completes.
        mutant = with_mutation(
            '    for _ss_f in "$_ss_store"/base.*; do',
            '    for _ss_f in "$_ss_store"/base.* "$_ss_store"/.pub.*; do',
            path=READER)
        orphan = (f'printf "%s\\n" "{self.target}" > "{self.store}/.pub.99999.12345.k"\n'
                  f'/bin/chmod 600 "{self.store}/.pub.99999.12345.k"\n')
        try:
            for shell in SHELLS:
                self._wipe()
                body = (self._mkstore() + self._entry() + orphan
                        + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                rc, out, err = run_shell(shell, body)
                self.assertEqual("1 pointer none", out,
                                 f"{shell}: an orphaned transient changed the resolution")
                self._wipe()
                rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("0 unresolved stale", out,
                                 f"{shell}: the CONTROL did not fail — the glob is not load-bearing")
        finally:
            os.unlink(mutant)

    # ── row 76 ────────────────────────────────────────────────────────────────────────────────

    def test_row_076_bare_uname(self):
        """Row 76: publisher and reader agree under different PATHs."""
        # ACL-5 probes the platform by ABSOLUTE PATH. The mutation selects it with a bare
        # `uname`, and a PATH shim that answers `Hostile` turns a healthy resolution into a
        # refusal — the verdict then depends on PATH, which no clause may.
        mutant = with_mutation(
            '    _U_PLATFORM="$(/usr/bin/uname -s 2>/dev/null)"',
            '    _U_PLATFORM="$(uname -s 2>/dev/null)"',
            path=AUTH)
        shim = os.path.join(self.home, "shim")
        os.makedirs(shim)
        with open(os.path.join(shim, "uname"), "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nprintf 'Hostile\\n'\n")
        os.chmod(os.path.join(shim, "uname"), 0o755)
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((mutant, STORE, READER, PUB), True)):
                    # Seed in a SEPARATE shipped-build shell: ACL-5 memoizes the platform per
                    # process, so the probe under test must run in the shell whose PATH varies.
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + self._entry() + 'printf seeded')
                    self.assertEqual("seeded", out, f"{shell}: {err}")
                    reads = {}
                    for label, hostile in (("normal", False), ("hostile", True)):
                        body = ((f'PATH="{shim}:$PATH"\n' if hostile else '')
                                + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                        rc, out, _ = run_shell(shell, body, sources=srcs)
                        reads[label] = out
                    self._wipe()
                    body = (f'PATH="{shim}:$PATH"\n'
                            f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                            'printf "%s" "$_UNLEASHED_POINTER_STATE"')
                    rc, pub_hostile, _ = run_shell(shell, body, sources=srcs)
                    if not is_mutant:
                        self.assertEqual("1 pointer none", reads["normal"], f"{shell}")
                        self.assertEqual(reads["normal"], reads["hostile"],
                                         f"{shell}: the reader's verdict depends on PATH")
                        self.assertEqual("created", pub_hostile,
                                         f"{shell}: the publisher's verdict depends on PATH")
                    else:
                        self.assertEqual("1 pointer none", reads["normal"], f"{shell}")
                        self.assertEqual("0 unresolved stale", reads["hostile"],
                                         f"{shell}: the CONTROL did not fail (reader)")
                        self.assertEqual("failed", pub_hostile,
                                         f"{shell}: the CONTROL did not fail (publisher)")
        finally:
            os.unlink(mutant)

    # ── row 92 ────────────────────────────────────────────────────────────────────────────────

    def test_row_092_one_acl_walk_per_process(self):
        """Row 92: reader-path fixture — five sourced family libraries in one process perform ONE ACL walk between them."""
        # The once-per-process mechanism is `unleashed_resolve_base`'s memo in paths.sh; every
        # consumer's primitive goes through it. The oracle is the DERIVED INVOCATION COUNT,
        # measured at the enumerator-output seam (one invocation per component evaluated), which
        # is identical on both shell arms — a publisher cell would fail this row against a
        # CORRECT implementation (BUD-1), so the fixture is reader-only.
        mutant = with_mutation(
            '        [ -n "${_UNLEASHED_BASE_OK:-}" ] && return 0        # already resolved in this shell',
            '        :                                                   # re-resolve per consumer',
            path=PATHS_C4)
        cnt = os.path.join(self.home, "cnt")
        derived = 2 * self._comps(self.store) + self._comps(self.target)
        try:
            for shell in SHELLS:
                for paths_file, is_mutant in ((PATHS_C4, False), (mutant, True)):
                    self._wipe()
                    body = (self._mkstore() + self._entry()
                            + f'export HOME="{self.home}"\n'
                            'unset CLAUDE_PLUGIN_DATA _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE\n'
                            'unset _UNLEASHED_POINTER_STATE _UNLEASHED_BASE_DIAGNOSED _UNLEASHED_PATHS_SH_LOADED\n'
                            '_UNLEASHED_STATE_LOADED=1; _UNLEASHED_STATE_RC=0\n'
                            f': > "{cnt}"\n'
                            '_u_acl_enumerate() { printf x >> "' + cnt + '"; /bin/ls -lde -- "$1" 2>/dev/null; }\n'
                            f'. "{paths_file}"\n'
                            f'. "{MARKER}"\n'
                            f'. "{CONTEXT}"\n'
                            f'. "{LOG}"\n'
                            f'. "{BRIDGE_C4}" "" "{ROOT2}"\n'
                            # One primitive use per consumer library, through the shared resolver.
                            + 'unleashed_plugin_base >/dev/null\n' * 5
                            + self.OUTP)
                    rc, out, err = run_shell(shell, body)
                    self.assertEqual("1 pointer none", out, f"{shell}: {err}")
                    n = os.path.getsize(cnt)
                    if not is_mutant:
                        self.assertEqual(derived, n,
                                         f"{shell}: {n} enumerator calls, derived {derived}")
                    else:
                        self.assertEqual(6 * derived, n,
                                         f"{shell}: the CONTROL did not fail — the walk is not re-run per consumer")
        finally:
            os.unlink(mutant)

    # ── row 99 ────────────────────────────────────────────────────────────────────────────────

    def test_row_099_publish_fence(self):
        """Row 99: with _UNLEASHED_PUBLISH_OK=0 the agent fence resolves without writing any entry."""
        # PUB-1/step 1: the publish is a side effect of having resolved, and the fence turns the
        # side effect off — never the resolution. The mutation ignores the fence.
        # The fence is PUB-9's E0 branch; the mutation makes E0 unreachable so the publish runs.
        mutant = with_mutation(
            '            if [ "${_UNLEASHED_PUBLISH_OK:-1}" = 0 ]; then',
            '            if false; then',
            path=PATHS_C4)
        try:
            for shell in SHELLS:
                for paths_file, is_mutant in ((PATHS_C4, False), (mutant, True)):
                    self._wipe()
                    body = (f'export HOME="{self.home}"\n'
                            f'export CLAUDE_PLUGIN_DATA="{self.target}"\n'
                            '_UNLEASHED_PUBLISH_OK=0\n'
                            'unset _UNLEASHED_BASE_OK _UNLEASHED_PATHS_SH_LOADED\n'
                            '_UNLEASHED_STATE_LOADED=1; _UNLEASHED_STATE_RC=0\n'
                            f'. "{paths_file}"\n' + self.OUTP)
                    rc, out, err = run_shell(shell, body)
                    if not is_mutant:
                        self.assertEqual("1 host-env none", out, f"{shell}: {err}")
                        self.assertFalse(os.path.exists(self.store),
                                         f"{shell}: the fence wrote an entry")
                    else:
                        self.assertEqual("1 host-env created", out,
                                         f"{shell}: the CONTROL did not fail — the fence is not consulted")
                        self.assertEqual(1, len([f for f in os.listdir(self.store)
                                                 if f.startswith("base.")]), f"{shell}")
        finally:
            os.unlink(mutant)

    # ── row 112 ───────────────────────────────────────────────────────────────────────────────

    def test_row_112_newline_base_unpublishable(self):
        """Row 112: a base value containing a NEWLINE is UNPUBLISHABLE — OK=1, SOURCE=env, failed, one diagnostic, and NO entry or transient exists afterwards."""
        # The dangerous value must be OTHERWISE PUBLISHABLE, so the fixture is a real directory
        # with a newline in its name and the enumerator-output seam answers healthily for every
        # component (the real `ls` answer for that name is itself two lines, which would mask the
        # mutation behind an ACL refusal). The filesystem is the oracle: the E2 exit composes no
        # store path at all, while the mutant leaves a durable entry behind.
        mutant = with_mutation(
            '    case "$_pb_value" in\n'
            '        *"$_pb_nl"*) _unleashed_pub_failed "the plugin-data base contains a newline"; return 0 ;;\n'
            '    esac',
            '    :',
            path=PUB)
        os.makedirs(os.path.join(self.home, "a\nb"))
        os.chmod(os.path.join(self.home, "a\nb"), 0o700)
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, READER, mutant), True)):
                    self._wipe()
                    body = ("_u_acl_enumerate() { printf %b 'drwx------@ 2 n s 64 d\\n'; }\n"
                            f'v="$(printf %b "{self.home}/a\\nb")"\n'
                            f'_unleashed_publish "{self.store}" "$v"\n' + self.OUTP)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual("1 host-env failed", out, f"{shell}: {err}")
                    self.assertEqual(1, len(self._diags(err)), f"{shell}: diagnostic count")
                    if not is_mutant:
                        self.assertIn("contains a newline", err, f"{shell}")
                        self.assertFalse(os.path.exists(self.store),
                                         f"{shell}: the refusal left something behind")
                    else:
                        # Same protocol tuple — the discriminator is the DURABLE FILE.
                        entries = [f for f in os.listdir(self.store) if f.startswith("base.")]
                        self.assertEqual(1, len(entries),
                                         f"{shell}: the CONTROL did not fail — nothing was written")
        finally:
            os.unlink(mutant)

    # ── row 119 ───────────────────────────────────────────────────────────────────────────────

    def test_row_119_zsh_subscript_concatenation(self):
        """Row 119: out="$out[$c]" aborts zsh with a bad-math-expression error while bash yields the literal X[$c] and passes — the oracle is the ZSH arm (FAM-5 clause 0)."""
        # In zsh `$out[` opens an array subscript and the char is evaluated as MATH: '.' (present
        # in every path under ~/.claude) is a fatal math error that aborts the resolution
        # outright. In bash the brackets are literal, both sides of ENT-3 use the same broken
        # encoder, the names still match, and the resolution completes silently — so a bash-only
        # cell cannot discriminate this mutant, which is exactly what the row records.
        mutant = with_mutation(
            '                    _uk_out="${_uk_out}${_uk_c}"',
            '                    _uk_out="$_uk_out[$_uk_c]"',
            path=STORE)
        body = (f'_unleashed_publish "{self.store}" "{self.target}"\n'
                + self.RESET
                + f'_unleashed_read_store "{self.store}"\n' + self.OUTP)
        try:
            for shell in SHELLS:
                self._wipe()
                rc, out, err = run_shell(shell, body)
                self.assertEqual("1 pointer none", out, f"{shell}: {err}")
                self.assertEqual("", err, f"{shell}: a resolution must be silent")
                self._wipe()
                rc, out, err = run_shell(shell, body, sources=(AUTH, mutant, READER, PUB))
                if shell == "/bin/zsh":
                    self.assertIn("bad", err.lower(),
                                  f"{shell}: the CONTROL did not fail — no zsh math abort: {err!r}")
                    self.assertNotEqual("1 pointer none", out,
                                        f"{shell}: the aborted resolution still resolved")
                else:
                    # Documented non-discrimination: bash is self-consistent under the mutation.
                    self.assertEqual("1 pointer none", out,
                                     f"{shell}: bash unexpectedly discriminates — the row's record is wrong")
        finally:
            os.unlink(mutant)

    # ── row 126 ───────────────────────────────────────────────────────────────────────────────

    def test_row_126_probe_stdout_redirected(self):
        """Row 126: the read-only probes' stdout IS the answer — with it redirected to /dev/null the store refuses on a healthy machine (fail-closed collapse), not merely "no crash"."""
        # One substitution per probe, chained: uname, stat (bash arm), id, ls, getconf.
        m = with_mutation('_U_PLATFORM="$(/usr/bin/uname -s 2>/dev/null)"',
                          '_U_PLATFORM="$(/usr/bin/uname -s >/dev/null 2>&1)"', path=AUTH)
        for old, new in (
                ("/usr/bin/stat -f '%p %z %u' -- \"$1\" 2>/dev/null",
                 "/usr/bin/stat -f '%p %z %u' -- \"$1\" >/dev/null 2>&1"),
                ('/usr/bin/id -un 2>/dev/null', '/usr/bin/id -un >/dev/null 2>&1'),
                ('/bin/ls -lde -- "$1" 2>/dev/null', '/bin/ls -lde -- "$1" >/dev/null 2>&1')):
            m2 = with_mutation(old, new, path=m)
            os.unlink(m)
            m = m2
        auth_mutant = m
        store_mutant = with_mutation('/usr/bin/getconf NAME_MAX "$1" 2>/dev/null',
                                     '/usr/bin/getconf NAME_MAX "$1" >/dev/null 2>&1', path=STORE)
        pubstore = os.path.join(self.home, "pub", "bases")
        try:
            for shell in SHELLS:
                self._wipe()
                rc, out, err = run_shell(shell, self._mkstore() + self._entry() + 'printf seeded')
                self.assertEqual("seeded", out, f"{shell}: {err}")
                for srcs, is_mutant in (
                        ((AUTH, STORE, READER, PUB), False),
                        ((auth_mutant, store_mutant, READER, PUB), True)):
                    read_body = (f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                    rc, read_out, _ = run_shell(shell, read_body, sources=srcs)
                    shutil.rmtree(os.path.join(self.home, "pub"), ignore_errors=True)
                    pub_body = (f'_unleashed_publish "{pubstore}" "{self.target}" 2>/dev/null\n'
                                'printf "%s" "$_UNLEASHED_POINTER_STATE"')
                    rc, pub_out, _ = run_shell(shell, pub_body, sources=srcs)
                    if not is_mutant:
                        self.assertEqual("1 pointer none", read_out,
                                         f"{shell}: a healthy machine must resolve")
                        self.assertEqual("created", pub_out, f"{shell}")
                    else:
                        self.assertEqual("0 unresolved stale", read_out,
                                         f"{shell}: the CONTROL did not fail — the stdout is not the answer")
                        self.assertEqual("failed", pub_out, f"{shell}")
                        self.assertFalse(os.path.exists(pubstore),
                                         f"{shell}: the refusing publisher created the store")
        finally:
            os.unlink(auth_mutant)
            os.unlink(store_mutant)

    # ── row 132 ───────────────────────────────────────────────────────────────────────────────

    def test_row_132_reader_rewalks_a_chain(self):
        """Row 132: a reader walks each chain ONCE — a re-walk raises the derived invocation count while every protocol variable is UNCHANGED, so the oracle is the COUNT and cannot be the resolution."""
        # BUD-1's derivation, instantiated at the enumerator-output seam: the seam is invoked
        # once per component evaluated, identically on both shell arms (the arm difference is
        # `stat`, which this count deliberately excludes). Reader path: rule −1 walks the store
        # chain, the one entry walks its own chain and the target chain.
        mutant = with_mutation(
            '    _unleashed_auth_chain "${_ae_p%/*}" || return 1\n'
            '    _unleashed_auth_chain "$_ae_line" || return 1',
            '    _unleashed_auth_chain "${_ae_p%/*}" || return 1\n'
            '    _unleashed_auth_chain "${_ae_p%/*}" || return 1\n'
            '    _unleashed_auth_chain "$_ae_line" || return 1',
            path=READER)
        cnt = os.path.join(self.home, "cnt")
        derived = 2 * self._comps(self.store) + self._comps(self.target)
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, mutant, PUB), True)):
                    self._wipe()
                    body = (self._mkstore() + self._entry()
                            + f': > "{cnt}"\n'
                            '_u_acl_enumerate() { printf x >> "' + cnt + '"; /bin/ls -lde -- "$1" 2>/dev/null; }\n'
                            + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertEqual("1 pointer none", out,
                                     f"{shell}: the protocol variables must be unchanged: {err}")
                    n = os.path.getsize(cnt)
                    if not is_mutant:
                        self.assertEqual(derived, n,
                                         f"{shell}: {n} enumerator calls, derived {derived}")
                    else:
                        self.assertEqual(derived + self._comps(self.store), n,
                                         f"{shell}: the CONTROL did not fail — no extra walk was counted")
        finally:
            os.unlink(mutant)

    # ── row 138 ───────────────────────────────────────────────────────────────────────────────

    def test_row_138_cleanup_rm_via_path(self):
        """Row 138: after a failed E6 publish no .pub.* name remains, the store stays writable so the unmutated /bin/rm genuinely succeeds, and a FAILED removal changes nothing a reader sees."""
        # E6 is forced on a WRITABLE store with RLIMIT_FSIZE(0) + SIGXFSZ ignored: the zero-byte
        # transient create succeeds, the value write fails (measured: printf rc=1, size 0, rm
        # still succeeds), so the cleanup site runs. The mutation invokes that rm through PATH,
        # where a shim that exits non-zero without removing leaves the transient behind. TMP-2
        # keeps transients outside the base.* glob, so the reader outcome is identical either
        # way and the oracle is the FILE's presence.
        mutant = with_mutation(
            '            /bin/rm -f "$_UNLEASHED_TRANSIENT" >/dev/null 2>&1      # ST-7: best effort',
            '            rm -f "$_UNLEASHED_TRANSIENT" >/dev/null 2>&1      # ST-7: best effort',
            path=PUB)
        shim = os.path.join(self.home, "shim")
        os.makedirs(shim)
        with open(os.path.join(shim, "rm"), "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexit 1\n")
        os.chmod(os.path.join(shim, "rm"), 0o755)
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, READER, mutant), True)):
                    self._wipe()
                    # The shim is on PATH for BOTH builds: only the mutant consults it.
                    body = (self._mkstore()
                            + f'PATH="{shim}:$PATH"\n'
                            'trap "" XFSZ\nulimit -f 0\n'
                            f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                            'printf "STATE=%s" "$_UNLEASHED_POINTER_STATE"')
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertIn("STATE=failed", out, f"{shell}: E6 was not taken: {out!r} {err!r}")
                    pubs = [f for f in os.listdir(self.store) if f.startswith(".pub.")]
                    if not is_mutant:
                        self.assertEqual([], pubs, f"{shell}: a transient survived the cleanup")
                    else:
                        self.assertEqual(1, len(pubs),
                                         f"{shell}: the CONTROL did not fail — the shim rm was not consulted")
                    # Either way, a reader sees the SAME store-level outcome.
                    read_body = (self.RESET
                                 + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + self.OUTP)
                    rc, out, _ = run_shell(shell, read_body, sources=srcs)
                    self.assertEqual("0 unresolved none", out,
                                     f"{shell}: an orphaned transient changed what a reader sees")
        finally:
            os.unlink(mutant)

    # ── row 144 ───────────────────────────────────────────────────────────────────────────────

    def test_row_144_one_field_after_the_verb(self):
        """Row 144: `group:staff allow write list` — two non-reserved fields after the verb — yields the store-level refusal; dropping the exactly-one-field check keeps `list` and ACCEPTS."""
        # The fixture may NOT use `allow write allow list`: measured in the campaign, the second
        # `allow` lands in the <perms> slot where the RESERVED-TOKEN guard (row 148) refuses it
        # first, so specification and mutant both return 1 and that fixture cannot fail. Both
        # fields here are ordinary rights words, so only the one-field check stands in the way.
        mutant = with_mutation(
            '            [ -z "$_u13_perms" ] || return 1                    # a SECOND field after the verb',
            '            :                                                   # keep whichever field comes last',
            path=AUTH)
        answer = "drwx------@ 2 n s 64 d\\n 0: group:staff allow write list\\n"
        masked = "drwx------@ 2 n s 64 d\\n 0: group:staff allow write allow list\\n"

        def resolve(shell, srcs, ans):
            self._wipe()
            body = (f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                    + self.RESET
                    + "_u_acl_enumerate() { printf %b '" + ans + "'; }\n"
                    + f'_unleashed_read_store "{self.store}"\n' + self.OUTP)
            return run_shell(shell, body, sources=srcs)
        try:
            for shell in SHELLS:
                rc, out, err = resolve(shell, (AUTH, STORE, READER, PUB), answer)
                self.assertEqual("0 unresolved stale", out, f"{shell}: {err}")
                self.assertEqual(1, len(self._diags(err)), f"{shell}: diagnostic count")
                rc, out, _ = resolve(shell, (mutant, STORE, READER, PUB), answer)
                self.assertEqual("1 pointer none", out,
                                 f"{shell}: the CONTROL did not fail — the last field did not win")
                # The row's recorded mask, locked: with a second `allow` the reserved-token guard
                # refuses BEFORE the mutated check, so that fixture cannot discriminate.
                rc, out, _ = resolve(shell, (mutant, STORE, READER, PUB), masked)
                self.assertEqual("0 unresolved stale", out,
                                 f"{shell}: the masked fixture unexpectedly discriminates")
        finally:
            os.unlink(mutant)

    # ── row 151 ───────────────────────────────────────────────────────────────────────────────

    def test_row_151_answer_without_a_stat_line(self):
        """Row 151: an answer that is SOLELY one well-formed read-only ACE — no stat line — yields the store-level refusal; under the mutation it parses and a healthy single-entry store RESOLVES with OK=1."""
        # ACL-4: `STAT (BLANK | ACE)*` cannot accept until the mandatory initial stat line has
        # been seen. Rows 144-150 all constrain LINES and stay green under this defect; this row
        # constrains the ANSWER. The mutation lets INIT treat an ACE line as if the stat line had
        # been seen.
        mutant = with_mutation(
            '            INIT) case "$_u_ans_l" in\n'
            '                      [-dlbcps][-r][-w][-xSs][-r][-w][-xSs][-r][-w][-xTt]*) _u_ans_st=BODY ;;\n'
            '                      *) return 1 ;;\n'
            '                  esac ;;',
            '            INIT) case "$_u_ans_l" in\n'
            '                      [-dlbcps][-r][-w][-xSs][-r][-w][-xSs][-r][-w][-xTt]*) _u_ans_st=BODY ;;\n'
            '                      \' \'*) _u_ace "$_u_ans_l" || return 1\n'
            '                            _u_acl_ace_seen=1\n'
            '                            _u_acl_check_ace || return 2\n'
            '                            _u_ans_st=BODY ;;\n'
            '                      *) return 1 ;;\n'
            '                  esac ;;',
            path=AUTH)

        def resolve(shell, srcs, ans):
            self._wipe()
            body = (f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                    + self.RESET
                    + "_u_acl_enumerate() { printf %b '" + ans + "'; }\n"
                    + f'_unleashed_read_store "{self.store}"\n' + self.OUTP)
            return run_shell(shell, body, sources=srcs)
        try:
            for shell in SHELLS:
                rc, out, err = resolve(shell, (AUTH, STORE, READER, PUB),
                                       " 0: group:staff allow list\\n")
                self.assertEqual("0 unresolved stale", out, f"{shell}: {err}")
                self.assertEqual(1, len(self._diags(err)), f"{shell}: diagnostic count")
                # The same fixture with the empty answer and a blank first line must also refuse.
                for ans in ("", "\\ndrwx------@ 2 n s 64 d\\n"):
                    rc, out, _ = resolve(shell, (AUTH, STORE, READER, PUB), ans)
                    self.assertEqual("0 unresolved stale", out, f"{shell}: {ans!r}")
                rc, out, _ = resolve(shell, (mutant, STORE, READER, PUB),
                                     " 0: group:staff allow list\\n")
                self.assertEqual("1 pointer none", out,
                                 f"{shell}: the CONTROL did not fail — the stat line is not mandatory")
        finally:
            os.unlink(mutant)


if __name__ == "__main__":
    unittest.main()


# ==================================================================================================
# Chunk 5
# ==================================================================================================
"""COREDEV-2617 mutant-table rows, chunk 5 — EXECUTED mutation tests.

Each test drives the row's fixture through the SHIPPED build and the row's mutant, in BOTH shells,
and asserts the outcomes differ (a mutant nobody ran is prose, not evidence — the campaign rule).
Mutants are built from the shipped files by exact substitution (`with_mutation`) or presented
through a §7 step 3f seam; never a paraphrased copy.
"""

import os
import shutil
import tempfile
import unittest


#: The fifth resolver copy (FAM-1) — row 65's subject. It lives beside the four state libs.
BRIDGE_C5 = os.path.join(os.path.dirname(AUTH), "agent-env-bridge.sh")

#: PUB-9's declared pointer states. Row 59: every publish exit maps to exactly one of these.
DECLARED = {"created", "current", "conflict", "stale", "failed", "none"}


@unittest.skipUnless(DARWIN, "the rows drive the Darwin ACL arm, /usr/bin/stat and APFS name semantics")
class RowsChunk5(unittest.TestCase):
    """Rows 5, 12, 27, 43, 53, 59, 65, 77, 85, 93, 113, 127, 133, 139, 146."""

    def setUp(self):
        # A scratch HOME under ~/.claude so every chain walked is 0700 and euid-owned (§7 step 3f(i))
        # and no test reads or writes the developer's real store.
        self.home = scratch_home("rows5.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.target = os.path.join(self.home, "target")
        os.makedirs(self.target)
        os.chmod(self.target, 0o700)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    #: A well-formed entry beside the fixture: the target's encoded name, its single line, 0600.
    ENTRY = ('_unleashed_key "{t}"; printf "%s\\n" "{t}" > "{s}/base.$_UNLEASHED_KEY"; '
             '/bin/chmod 600 "{s}/base.$_UNLEASHED_KEY"\n')

    def _read(self, shell, setup, sources=(AUTH, STORE, READER, PUB), create=True):
        """Create the store, run `setup`, read it; -> (state tuple, reader stderr).

        `create=False` skips store creation for a mutant whose chain walk refuses EVERYTHING —
        row 27's euid-above-the-anchor mutant fails `_unleashed_create_store` too, so its leg must
        read the store the spec leg already built.
        """
        mk = (f'_unleashed_name_max "{self.store}" >/dev/null\n'
              f'_unleashed_create_store "{self.store}" || exit 9\n') if create else ''
        body = (mk
                + f'{setup}\n'
                f'_unleashed_read_store "{self.store}"\n'
                'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"')
        rc, out, err = run_shell(shell, body, sources=sources)
        self.assertNotEqual(9, rc, f"{shell}: the store could not be created: {err}")
        return out, err

    def _assert_one_diagnostic(self, err, shell):
        # RD-6/FAM-6: exactly ONE bounded line, and it never prints a path or an entry name.
        lines = [l for l in err.splitlines() if l]
        self.assertEqual(1, len(lines), f"{shell}: expected exactly one diagnostic, got {err!r}")
        self.assertNotIn(self.home, err, f"{shell}: the diagnostic leaked a path")

    # ── row 5 ─────────────────────────────────────────────────────────────────────────────────────
    def test_row_005_a_dangling_target_refuses_and_a_conforming_neighbour_does_not_win(self):
        """Row 5: a DANGLING target yields sentinel/OK=0/unresolved/stale + ONE diagnostic, and a conforming entry beside it does not win."""
        dangle = os.path.join(self.home, "vanished-target")     # never created
        setup = (self.ENTRY.format(t=self.target, s=self.store)
                 + self.ENTRY.format(t=dangle, s=self.store))
        # The row's mutant must ACCEPT a non-existent target. The shipped code refuses it TWICE —
        # TGT-1's `-d` clause and the target chain walk (whose stat of the final component fails) —
        # so "accept a non-existent target" is two exact substitutions on the shipped reader;
        # removing only one still refuses through the other, and a one-site mutant would be a
        # cannot-discriminate misreading of the row, not this mutant (hard rule 7).
        m1 = with_mutation('[ -d "$_ae_line" ] || return 1', ':', path=READER)
        try:
            m2 = with_mutation('_unleashed_auth_chain "$_ae_line" || return 1', ':', path=m1)
            try:
                for shell in SHELLS:
                    out, err = self._read(shell, setup)
                    self.assertEqual("0 unresolved stale", out, f"{shell}: spec")
                    self._assert_one_diagnostic(err, shell)
                    self.assertIn("failed authentication", err, shell)
                    # Mutant: the dangling entry now authenticates BESIDE the conforming one, so the
                    # store flips to `conflict` — the fixture discriminates, and `stale` was rule 1
                    # refusing the neighbour's win, not an accident of the dangling entry alone.
                    out, _ = self._read(shell, setup, sources=(AUTH, STORE, m2, PUB))
                    self.assertEqual("0 unresolved conflict", out,
                                     f"{shell}: the mutant did not accept the dangling target — "
                                     "this fixture cannot discriminate")
            finally:
                os.unlink(m2)
        finally:
            os.unlink(m1)

    # ── row 12 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_012_a_group_writable_target_component_refuses(self):
        """Row 12: a 0775 target component yields sentinel/OK=0/unresolved/stale + one diagnostic, and a conforming entry beside it does NOT win."""
        t2 = os.path.join(self.home, "t2")
        os.makedirs(t2)
        os.chmod(t2, 0o775)                                     # the row's exact mode
        setup = (self.ENTRY.format(t=self.target, s=self.store)
                 + self.ENTRY.format(t=t2, s=self.store))
        # PCH-1's group-writable clause, dropped. 0775 passes every OTHER clause (owner ours, not
        # other-writable, clean ACL), so only this clause separates spec from mutant.
        mutant = with_mutation('case "$_U_MODE" in *[2367]?) return 1 ;; esac', ':')
        try:
            for shell in SHELLS:
                out, err = self._read(shell, setup)
                self.assertEqual("0 unresolved stale", out, f"{shell}: spec")
                self._assert_one_diagnostic(err, shell)
                out, _ = self._read(shell, setup, sources=(mutant, STORE, READER, PUB))
                self.assertEqual("0 unresolved conflict", out,
                                 f"{shell}: the mutant did not accept the 0775 target — "
                                 "this fixture cannot discriminate")
        finally:
            os.unlink(mutant)

    # ── row 27 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_027_root_owned_components_above_the_anchor_still_resolve(self):
        """Row 27: root-owned / and /Users above the trust anchor still RESOLVE: OK=1/pointer/none, stderr empty."""
        setup = self.ENTRY.format(t=self.target, s=self.store)
        # ANCHOR-1's system-prefix acceptance, dropped: euid ownership required from `/` down. Every
        # real chain starts at root-owned `/`, so the mutant refuses the store chain at its first
        # component and rule -1 reports `stale` — which is exactly why the prefix run is accepted.
        mutant = with_mutation('if [ "$_u_ac_in_prefix" = 1 ] && [ "$_U_UID" = 0 ]; then',
                               'if false; then')
        try:
            for shell in SHELLS:
                out, err = self._read(shell, setup)
                self.assertEqual("1 pointer none", out, f"{shell}: spec must resolve: {err}")
                self.assertEqual("", err, f"{shell}: rule 3 must be silent")
                # create=False: this mutant's walk refuses every real chain, so store creation
                # would fail too — the mutant leg reads the store the spec leg just built.
                out, err = self._read(shell, setup, sources=(mutant, STORE, READER, PUB),
                                      create=False)
                self.assertEqual("0 unresolved stale", out,
                                 f"{shell}: the euid-above-the-anchor mutant did not refuse — "
                                 "this fixture cannot discriminate")
        finally:
            os.unlink(mutant)

    # ── row 43 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_043_an_entry_whose_name_does_not_encode_its_content_is_not_counted(self):
        """Row 43: a misnamed entry yields stale; a conforming entry beside it does not win and the misnamed one is NOT counted toward the conflict tally."""
        # The misnamed entry's NAME must be at least as long as its content: the reader now bounds
        # the entry size by its key length BEFORE opening it (a valid key is always >= its value,
        # since `/` -> `_s`), so a short fake name like `base.zzz` is refused by that bound and
        # ENT-3 is never reached — the mutant dropping ENT-3 then changes nothing, and the row
        # cannot fail. The real key with one character altered has the right length and is still
        # not the encoding of the content, which isolates ENT-3.
        setup = (self.ENTRY.format(t=self.target, s=self.store)
                 + f'_unleashed_key "{self.target}"; wrong="${{_UNLEASHED_KEY%?}}9"; '
                 + f'printf "%s\\n" "{self.target}" > "{self.store}/base.$wrong"; '
                 + f'/bin/chmod 600 "{self.store}/base.$wrong"')
        # ENT-3 dropped. BOTH entries hold the SAME value, so under the mutant the misnamed one is
        # COUNTED and the tally reads two distinct bases where one exists -> `conflict`. That is the
        # exact corruption ENT-3 prevents: counting entries only counts VALUES because the name is
        # an injective encoding of the content.
        mutant = with_mutation('[ "$_ae_p" = "${_ae_p%/*}/base.$_UNLEASHED_KEY" ] || return 1',
                               ':', path=READER)
        try:
            for shell in SHELLS:
                out, err = self._read(shell, setup)
                self.assertEqual("0 unresolved stale", out, f"{shell}: spec")
                self._assert_one_diagnostic(err, shell)
                out, _ = self._read(shell, setup, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("0 unresolved conflict", out,
                                 f"{shell}: the mutant did not count the misnamed entry — "
                                 "this fixture cannot discriminate")
        finally:
            os.unlink(mutant)

    # ── row 53 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_053_a_publisher_touches_only_its_own_key(self):
        """Row 53: a publisher touches only base.<key(its value)> and its own tmp."""
        body = (f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                f'_unleashed_key "{self.target}"\n'
                'printf "%s %s" "$_UNLEASHED_POINTER_STATE" "$_UNLEASHED_KEY"')
        # The mutant writes an entry that is NOT its own key. Its own post-scan P1 then reports the
        # entry missing (`failed`) and the stray file's NAME is the observable damage.
        mutant = with_mutation('_pb_entry="$_pb_store/base.$_pb_key"',
                               '_pb_entry="$_pb_store/base.x$_pb_key"', path=PUB)
        try:
            for shell in SHELLS:
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                rc, out, err = run_shell(shell, body)
                state, key = out.split()
                self.assertEqual("created", state, f"{shell}: {err}")
                # The whole store listing: exactly the publisher's own key, no transient, no other
                # name — the row's oracle is the SET of touched paths, not just "one entry".
                self.assertEqual(["base." + key], sorted(os.listdir(self.store)), shell)
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                rc, out, err = run_shell(shell, body, sources=(AUTH, STORE, READER, mutant))
                state, key = out.split()
                self.assertEqual("failed", state,
                                 f"{shell}: the not-its-own-key mutant must fail P1")
                self.assertEqual(["base.x" + key], sorted(os.listdir(self.store)),
                                 f"{shell}: the mutant's stray name is the discriminating damage")
        finally:
            os.unlink(mutant)

    # ── row 59 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_059_the_p2_exit_maps_to_the_declared_value_stale(self):
        """Row 59: every publish exit maps to a declared value — pinned at P2, the one exit no other test observes."""
        # A failing FOREIGN entry beside our own authenticated one drives P2. Every other exit
        # (E2..E6, P1, P3, P4 created/current) is pinned by an existing test; P2 was the gap a
        # dropped-enum-value mutant could hide in.
        body = (f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                f'printf "%s\\n" "not-absolute" > "{self.store}/base.rogue"; '
                f'/bin/chmod 600 "{self.store}/base.rogue"\n'
                'unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE '
                '_UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL\n'
                f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                'printf "%s" "$_UNLEASHED_POINTER_STATE"')
        mutant = with_mutation('_unleashed_pub_state stale', '_unleashed_pub_state degraded',
                               path=PUB)
        try:
            for shell in SHELLS:
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                rc, out, err = run_shell(shell, body)
                self.assertEqual("stale", out, f"{shell}: P2 must report stale: {err}")
                self.assertIn(out, DECLARED, shell)
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                rc, out, _ = run_shell(shell, body, sources=(AUTH, STORE, READER, mutant))
                self.assertNotIn(out, DECLARED,
                                 f"{shell}: the dropped-value mutant still mapped to the enum — "
                                 "this fixture cannot discriminate")
        finally:
            os.unlink(mutant)

    # ── row 65 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_065_the_bridge_reads_the_store_when_the_variable_is_empty(self):
        """Row 65: empty $1, paths.sh absent, one valid entry -> the fifth copy RESOLVES it and reports all four protocol variables, not OK=0."""
        # A fake plugin root holding ONLY the four state libs: `paths.sh absent` is the row's
        # fixture, so the bridge's guarded preference for it must fall through to _ueb_state_load.
        fakeroot = os.path.join(self.home, "fakeroot")
        os.makedirs(os.path.join(fakeroot, "scripts", "lib"))
        for lib in (AUTH, STORE, READER, PUB):
            shutil.copy(lib, os.path.join(fakeroot, "scripts", "lib"))
        home2 = os.path.join(self.home, "home2")
        store2 = os.path.join(home2, ".claude", "unleashed-mail", "bases")
        os.makedirs(store2)
        for d in (home2, os.path.join(home2, ".claude"),
                  os.path.join(home2, ".claude", "unleashed-mail"), store2):
            os.chmod(d, 0o700)
        rc, key, err = run_shell("/bin/bash",
                                 f'_unleashed_key "{self.target}"; printf "%s" "$_UNLEASHED_KEY"')
        entry = os.path.join(store2, "base." + key)
        with open(entry, "w", encoding="utf-8") as fh:
            fh.write(self.target + "\n")
        os.chmod(entry, 0o600)
        # Sourced with ARGUMENTS, exactly as the agent fence calls it; sources=() because the row is
        # about the bridge loading the machinery itself, through $2.
        body_for = lambda bridge: (f'HOME="{home2}"; export HOME\n'
                                   f'. "{bridge}" "" "{fakeroot}"\n'
                                   'printf "%s %s %s %s" "$_UNLEASHED_BASE_OK" '
                                   '"$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE" '
                                   '"$_UNLEASHED_BASE_RESOLVED"')
        # The D'-only mutant never reads the store — the round-18 fail-open -> fail-closed
        # inversion the bridge's own comment warns about.
        mutant = with_mutation('if [ "$_ueb_home_ok" = 1 ] && _ueb_state_load "${2-}"; then',
                               'if false; then', path=BRIDGE_C5)
        try:
            for shell in SHELLS:
                rc, out, err = run_shell(shell, body_for(BRIDGE_C5), sources=())
                self.assertEqual(f"1 pointer none {self.target}", out,
                                 f"{shell}: the bridge must resolve the entry: {err}")
                self.assertEqual("", err, f"{shell}: a resolution is silent")
                rc, out, err = run_shell(shell, body_for(mutant), sources=())
                self.assertEqual("0 unresolved none /dev/null/unresolved-plugin-base", out,
                                 f"{shell}: the D'-only mutant must report OK=0 — "
                                 "otherwise this fixture cannot discriminate")
                self.assertIn("CLAUDE_PLUGIN_DATA is unset", err, shell)
        finally:
            os.unlink(mutant)

    # ── row 77 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_077_a_vanished_entry_mid_scan_is_skipped_not_stale(self):
        """Row 77: an operator deleting an entry between the glob and the open does not flip a healthy store to stale."""
        # The deletion happens genuinely MID-SCAN: the enumerator seam deletes the victim when it is
        # asked about the FIRST entry's target — a component only visited while authenticating that
        # entry, after rule -1 and after the glob. Everything else gets its real answer.
        trig = os.path.join(self.home, "trigdir")
        os.makedirs(trig)
        os.chmod(trig, 0o700)
        victim = os.path.join(self.store, "base.zzzz")          # sorts AFTER base._s...
        seam = ('_u_acl_enumerate() { case "$1" in "' + trig + '") /bin/rm -f "' + victim
                + '" ;; esac; /bin/ls -lde -- "$1"; }\n')
        setup = (self.ENTRY.format(t=trig, s=self.store)
                 + f': > "{victim}"; /bin/chmod 600 "{victim}"\n'
                 + seam)
        # The mutant applies rule 1 to the vanished candidate (the skip moved below it).
        mutant = with_mutation('if [ ! -L "$_ss_f" ] && [ ! -e "$_ss_f" ]; then',
                               'if false; then', path=READER)
        try:
            for shell in SHELLS:
                out, err = self._read(shell, setup)
                self.assertEqual("1 pointer none", out, f"{shell}: spec: {err}")
                self.assertFalse(os.path.exists(victim),
                                 f"{shell}: fixture defect — the seam never deleted mid-scan, "
                                 "so this run proved nothing")
                out, _ = self._read(shell, setup, sources=(AUTH, STORE, mutant, PUB))
                self.assertEqual("0 unresolved stale", out,
                                 f"{shell}: the skip-below-rule-1 mutant did not go stale — "
                                 "this fixture cannot discriminate")
        finally:
            os.unlink(mutant)

    # ── row 85 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_085_escaped_high_bytes_keep_nfc_and_nfd_entries_distinct(self):
        """Row 85: NFC and NFD spellings of one path produce DISTINCT entries on a normalization-insensitive volume."""
        # The mutant leaves bytes >= 0x80 unescaped (control bytes still escaped — exactly the row).
        mutant = with_mutation('if [ "$_uk_n" -ge 128 ] || [ "$_uk_n" -lt 32 ]; then',
                               'if [ "$_uk_n" -lt 32 ]; then', path=STORE)
        try:
            for shell in SHELLS:
                for label, sources in (("spec", (AUTH, STORE, READER, PUB)),
                                       ("mutant", (AUTH, mutant, READER, PUB))):
                    d = os.path.join(self.home, f"norm-{label}-{os.path.basename(shell)}")
                    os.makedirs(d)
                    body = ('_unleashed_key "$(printf %b \'/caf\\xc3\\xa9\')"; k1="$_UNLEASHED_KEY"\n'
                            f': > "{d}/base.$k1"\n'
                            '_unleashed_key "$(printf %b \'/cafe\\xcc\\x81\')"; k2="$_UNLEASHED_KEY"\n'
                            f': > "{d}/base.$k2"\n'
                            'printf "%s %s" "$k1" "$k2"')
                    rc, out, err = run_shell(shell, body, sources=sources)
                    n = len(os.listdir(d))
                    if label == "spec":
                        k1, k2 = out.split()
                        self.assertNotEqual(k1, k2, shell)
                        self.assertTrue(all(ord(c) < 128 for c in k1 + k2),
                                        f"{shell}: spec keys must be pure ASCII")
                        self.assertEqual(2, n, f"{shell}: two ASCII names -> two entries")
                    else:
                        # MEASURED here: APFS identifies the NFC and NFD spellings, so the raw-byte
                        # names collapse to ONE directory entry. If this assertion fails the volume
                        # is normalization-sensitive and the row cannot discriminate on it.
                        self.assertEqual(1, n,
                                         f"{shell}: the unescaped mutant's NFC/NFD names did not "
                                         "collide — this volume cannot discriminate the row")
        finally:
            os.unlink(mutant)

    # ── row 93 ────────────────────────────────────────────────────────────────────────────────────
    def test_row_093_the_lc_all_pin_keeps_keys_byte_identical_across_shells(self):
        """Row 93: bash and zsh produce BYTE-IDENTICAL keys for a non-ASCII path."""
        # Ambient UTF-8 is the discriminating environment: with the pin, the walk is over BYTES in
        # both shells; without it, bash 3.2 slices bytes and sign-extends (measured: -61 for \\303)
        # while zsh slices CHARACTERS (measured: 233 for e-acute) — different keys, so two shells on
        # one machine would write two entries for one base and every reader would report conflict.
        body = ('LC_ALL=en_US.UTF-8; export LC_ALL\n'
                '_unleashed_key "$(printf %b \'/caf\\xc3\\xa9\')"\n'
                'printf "%s" "$_UNLEASHED_KEY"')
        spec = {}
        for shell in SHELLS:
            rc, out, err = run_shell(shell, body)
            spec[shell] = out
        self.assertEqual(spec["/bin/bash"], spec["/bin/zsh"], "spec keys must be byte-identical")
        self.assertEqual("_scaf_xc3_xa9", spec["/bin/bash"], "the BYTE-wise walk is the spec")
        mutant = with_mutation('    LC_ALL=C\n', '    :\n', path=STORE)
        try:
            got = {}
            for shell in SHELLS:
                rc, out, err = run_shell(shell, body, sources=(AUTH, mutant, READER, PUB))
                got[shell] = out
            self.assertNotEqual(got["/bin/bash"], got["/bin/zsh"],
                                f"unpinned keys agreed ({got!r}) — this fixture cannot discriminate")
        finally:
            os.unlink(mutant)

    # ── row 113 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_113_st7_refuses_symlink_directory_and_dangling_symlink_alike(self):
        """Row 113: a symlink-to-dir, a directory and a DANGLING symlink at base.<key> all report `failed` with nothing written."""
        # Three fixtures because two are caught by a test the third is not: `[ -e ]` is FALSE on a
        # dangling symlink, so the one-part mutant lets `mv -f` silently replace the link (measured)
        # while still refusing the first two fixtures.
        mutant = with_mutation(
            'if { [ -L "$_pb_entry" ] || [ -e "$_pb_entry" ]; } && [ ! -f "$_pb_entry" ]; then',
            'if [ -e "$_pb_entry" ] && [ ! -f "$_pb_entry" ]; then', path=PUB)
        pub = (f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
               'printf "%s" "$_UNLEASHED_POINTER_STATE"')

        def prime(shell, sources):
            # A fresh store with the entry published, then the entry replaced by the fixture.
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            rc, out, err = run_shell(shell, pub, sources=sources)
            self.assertEqual("created", out, f"{shell}: priming publish failed: {err}")
            (name,) = [f for f in os.listdir(self.store) if f.startswith("base.")]
            entry = os.path.join(self.store, name)
            os.remove(entry)
            return entry

        try:
            for shell in SHELLS:
                for sources, dangling_expect in (((AUTH, STORE, READER, PUB), "failed"),
                                                 ((AUTH, STORE, READER, mutant), "created")):
                    # (a) a symlink TO A DIRECTORY — a broken mv would land the transient INSIDE it
                    entry = prime(shell, sources)
                    os.symlink(self.target, entry)
                    rc, out, _ = run_shell(shell, pub, sources=sources)
                    self.assertEqual("failed", out, f"{shell}: symlink-to-dir must refuse")
                    self.assertTrue(os.path.islink(entry), f"{shell}: the link must survive")
                    self.assertEqual([], os.listdir(self.target),
                                     f"{shell}: nothing may land outside the store")
                    # (b) a DIRECTORY
                    entry = prime(shell, sources)
                    os.mkdir(entry)
                    rc, out, _ = run_shell(shell, pub, sources=sources)
                    self.assertEqual("failed", out, f"{shell}: directory must refuse")
                    self.assertEqual([], os.listdir(entry),
                                     f"{shell}: nothing may land inside the squatter")
                    # (c) a DANGLING symlink — the fixture only this row pins
                    entry = prime(shell, sources)
                    os.symlink(entry + ".gone", entry)
                    rc, out, _ = run_shell(shell, pub, sources=sources)
                    self.assertEqual(dangling_expect, out,
                                     f"{shell}: dangling-symlink outcome under {sources[3]!r}")
                    if dangling_expect == "failed":
                        self.assertTrue(os.path.islink(entry),
                                        f"{shell}: spec must leave the dangling link untouched")
                    else:
                        self.assertFalse(os.path.islink(entry),
                                         f"{shell}: the [ -e ]-only mutant was expected to let "
                                         "mv -f replace the link — it did not, so the third "
                                         "fixture no longer discriminates")
                    self.assertEqual([], [f for f in os.listdir(self.store)
                                          if f.startswith(".pub.")],
                                     f"{shell}: no transient may remain")
        finally:
            os.unlink(mutant)

    # ── row 127 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_127_no_fourth_transient_attempt(self):
        """Row 127: first three candidate names occupied and the fourth FREE -> E5 `failed`, nothing published; only this row pins TMP-1's TOTAL."""
        # Seeding RANDOM makes the publisher's draws foreseeable: sample four values, re-seed, and
        # the publisher will draw the same sequence (measured in both shells). The first three
        # candidates are pre-created; the fourth is left free so a four-attempt implementation
        # PUBLISHES where a three-attempt one takes E5 — row 116's no-hang oracle passes both.
        # TMP-1's TOTAL is now owned by the publisher's outer loop (the name helper is called with
        # a budget of 1 per attempt so a create-race loss and a presence hit share ONE budget); the
        # fourth attempt is therefore granted THERE.
        mutant = with_mutation('        while [ "$_pb_try" -lt 3 ]; do',
                               '        while [ "$_pb_try" -lt 4 ]; do', path=PUB)
        body = ('RANDOM=42\n'
                'r1=$RANDOM; r2=$RANDOM; r3=$RANDOM; r4=$RANDOM\n'
                'for r in "$r2" "$r3" "$r4"; do [ "$r1" = "$r" ] && exit 97; done\n'
                '[ "$r2" = "$r3" ] && exit 97; [ "$r2" = "$r4" ] && exit 97; '
                '[ "$r3" = "$r4" ] && exit 97\n'
                f'_unleashed_name_max "{self.store}" >/dev/null || exit 96\n'
                f'_unleashed_create_store "{self.store}" || exit 96\n'
                f'_unleashed_key "{self.target}"\n'
                f': > "{self.store}/.pub.$$.$r1.$_UNLEASHED_KEY"\n'
                f': > "{self.store}/.pub.$$.$r2.$_UNLEASHED_KEY"\n'
                f': > "{self.store}/.pub.$$.$r3.$_UNLEASHED_KEY"\n'
                'RANDOM=42\n'
                f'_unleashed_publish "{self.store}" "{self.target}"\n'
                'printf "%s" "$_UNLEASHED_POINTER_STATE"')
        try:
            for shell in SHELLS:
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                rc, out, err = run_shell(shell, body)
                self.assertNotIn(rc, (96, 97), f"{shell}: fixture defect (seed or store): {err}")
                self.assertEqual("failed", out, f"{shell}: spec must take E5: {err}")
                self.assertIn("no unique transient name", err, shell)
                self.assertEqual([], [f for f in os.listdir(self.store)
                                      if f.startswith("base.")],
                                 f"{shell}: E5 must publish nothing")
                self.assertEqual(3, len([f for f in os.listdir(self.store)
                                         if f.startswith(".pub.")]),
                                 f"{shell}: the three occupied names must survive untouched")
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                rc, out, err = run_shell(shell, body, sources=(AUTH, STORE, READER, mutant))
                self.assertNotIn(rc, (96, 97), f"{shell}: fixture defect (seed or store): {err}")
                self.assertEqual("created", out,
                                 f"{shell}: the four-attempt mutant was expected to publish on "
                                 f"the free fourth name — this fixture cannot discriminate: {err}")
        finally:
            os.unlink(mutant)

    # ── row 133 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_133_a_failed_name_max_probe_refuses_in_both_shells(self):
        """Row 133: a publish whose getconf fails REFUSES in BOTH shells; the raw-compare mutant DIVERGES (bash proceeds, zsh refuses)."""
        # The row's mutant compares against the raw probe output with neither the status check nor
        # the numeric-shape guard, expressed as `refuse if len > max`. Three exact substitutions
        # build that ONE implementation. Measured primitive: `[ 42 -gt "" ]` is status 2 in bash
        # 3.2.57 (if takes the ELSE branch -> proceed) and status 0 in zsh 5.9 (refuse) — which is
        # why the oracle must assert BOTH arms and a single-shell cell reads as a pass.
        m1 = with_mutation('    _nm_v="$(_u_name_max_probe "$_UNLEASHED_NEAREST")" || return 1\n',
                           '    _nm_v="$(_u_name_max_probe "$_UNLEASHED_NEAREST")"\n', path=STORE)
        try:
            m2 = with_mutation("        ''|*[!0-9]*) return 1 ;;\n",
                               "        ''|*[!0-9]*) : ;;\n", path=m1)
            try:
                m3 = with_mutation(
                    '    [ "$_bo_len" -le "$_UNLEASHED_NAME_MAX" ]\n',
                    '    if [ "$_bo_len" -gt "$_UNLEASHED_NAME_MAX" ] 2>/dev/null; then '
                    'return 1; fi\n', path=m2)
                try:
                    # §4.2a-S's probe seam: getconf is invoked by absolute path (N6-10), so a failed
                    # probe is only presentable by redefining the accessor. 71 is the measured
                    # status of the real getconf on a missing path.
                    body = ('_u_name_max_probe() { return 71; }\n'
                            f'_unleashed_publish "{self.store}" "{self.target}"\n'
                            'printf "%s" "$_UNLEASHED_POINTER_STATE"')
                    diverged = {"/bin/bash": "created", "/bin/zsh": "failed"}
                    for shell in SHELLS:
                        shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                        rc, out, err = run_shell(shell, body)
                        self.assertEqual("failed", out, f"{shell}: spec must fail closed: {err}")
                        self.assertEqual(1, len([l for l in err.splitlines() if l]), shell)
                        self.assertIn("NAME_MAX", err, f"{shell}: the diagnostic names the budget")
                        self.assertFalse(os.path.exists(self.store),
                                         f"{shell}: E3 precedes E4 — nothing may be created")
                        shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                        rc, out, err = run_shell(shell, body, sources=(AUTH, m3, READER, PUB))
                        self.assertEqual(diverged[shell], out,
                                         f"{shell}: the raw-compare mutant must diverge exactly "
                                         f"as measured — otherwise the row cannot discriminate")
                        self.assertEqual(shell == "/bin/bash", os.path.isdir(self.store),
                                         f"{shell}: only the proceeding bash arm creates the store")
                finally:
                    os.unlink(m3)
            finally:
                os.unlink(m2)
        finally:
            os.unlink(m1)

    # ── rows 139 and 146 share the enumerator-seam resolver driver ───────────────────────────────
    def _resolve_with_answer(self, shell, answer_esc, sources=(AUTH, STORE, READER, PUB)):
        """Publish a valid entry with the REAL enumerator, then re-resolve with EVERY component's
        ACL answer replaced by the fixture (§7 step 3f(iv))."""
        body = (f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                'unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE\n'
                'unset _UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL _U_PRINCIPAL_PROBED\n'
                '_u_acl_enumerate() { printf %b \'' + answer_esc + '\'; }\n'
                f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" '
                '"$_UNLEASHED_POINTER_STATE"')
        rc, out, err = run_shell(shell, body, sources=sources)
        return out

    # ── row 139 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_139_a_word_splitting_ace_parser_fails_open_in_zsh_only(self):
        """Row 139: a foreign allow ACE with a non-allowlisted right refuses in BOTH shells; the `for f in $line` mutant ACCEPTS in zsh while bash refuses."""
        # The mutant replaces P-13's two-layer token peel with word splitting. zsh does not split
        # an unquoted expansion (SH_WORD_SPLIT off, and IFS does not change that), so the loop sees
        # ONE field there: the verb is never found, the ACE is skipped, and the arm whose only job
        # is to refuse ACCEPTS — a publisher and reader on one machine disagreeing by shell alone.
        # Same family as row 119's `out="$out[$c]"` (array subscripting in zsh).
        with open(AUTH, encoding="utf-8") as fh:
            text = fh.read()
        start = '    _u13_rest="$_u13_body"\n'
        end = ('    case "$_u13_perms" in\n'
               "        ''|*,,*|,*|*,) return 1 ;;                              "
               "# empty, doubled, leading, trailing\n"
               '    esac\n'
               '    return 0\n')
        i = text.index(start)
        j = text.index(end, i) + len(end)
        splitting = (
            '    # MUTANT row 139: locate the verb by WORD SPLITTING. zsh does not split the\n'
            '    # unquoted expansion, so this loop sees ONE field there and every field in bash.\n'
            '    # shellcheck disable=SC2086\n'
            '    for _u13_tok in $_u13_body; do\n'
            '        _u13_n=$(( _u13_n + 1 ))\n'
            '        case "$_u13_tok" in\n'
            '            allow|deny) _u13_verb="$_u13_tok" ;;\n'
            '            inherited)  _u13_inh=1 ;;\n'
            '            *)          if [ "$_u13_n" = 1 ]; then _u13_principal="$_u13_tok"\n'
            '                        elif [ -n "$_u13_verb" ]; then _u13_perms="$_u13_tok"\n'
            '                        fi ;;\n'
            '        esac\n'
            '    done\n'
            '    return 0\n')
        mutant = with_mutation(text[i:j], splitting)
        # The same plain foreign allow ACE as row 135, carrying `add_file` — a right outside
        # ACL-2's seven-right allowlist — so the shipped arm refuses every component.
        answer = 'drwx------@ 2 n s 64 d\\n 0: group:staff allow add_file\\n'
        try:
            for shell in SHELLS:
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                self.assertEqual("0 unresolved stale", self._resolve_with_answer(shell, answer),
                                 f"{shell}: the shipped arm must refuse the hostile ACE")
            # The oracle must assert BOTH arms: a bash-only cell reads as a pass.
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            self.assertEqual(
                "0 unresolved stale",
                self._resolve_with_answer("/bin/bash", answer, sources=(mutant, STORE, READER, PUB)),
                "bash: the splitting mutant still sees every field and must refuse")
            shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
            self.assertEqual(
                "1 pointer none",
                self._resolve_with_answer("/bin/zsh", answer, sources=(mutant, STORE, READER, PUB)),
                "zsh: the splitting mutant was expected to FAIL OPEN — if it refused, this "
                "fixture cannot discriminate the row")
        finally:
            os.unlink(mutant)

    # ── row 146 ───────────────────────────────────────────────────────────────────────────────────
    def test_row_146_an_extra_field_between_principal_and_verb_refuses(self):
        """Row 146: ` 0: group:staff weird allow list` yields the store-level refusal; the ignore-unknown-fields mutant evaluates it as well formed."""
        # ACL-2's grammar is enforced POSITIONALLY; `weird` is not `inherited` and not the verb, so
        # the line is malformed and the ANSWER is poisoned (ACL-4's side). The mutant ignores any
        # unknown field before the verb, reads a well-formed read-only foreign ACE, and ACCEPTS —
        # proving the grammar is enforced rather than merely stated.
        mutant = with_mutation(
            '                *)          if [ "$_u13_n" = 1 ]; then _u13_principal="$_u13_tok"\n'
            '                            else return 1                       '
            '# unknown field before the verb\n',
            '                *)          if [ "$_u13_n" = 1 ]; then _u13_principal="$_u13_tok"\n'
            '                            else :\n')
        answer = 'drwx------@ 2 n s 64 d\\n 0: group:staff weird allow list\\n'
        try:
            for shell in SHELLS:
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                self.assertEqual("0 unresolved stale", self._resolve_with_answer(shell, answer),
                                 f"{shell}: the malformed ACE must poison the answer")
                shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)
                self.assertEqual("1 pointer none",
                                 self._resolve_with_answer(shell, answer,
                                                           sources=(mutant, STORE, READER, PUB)),
                                 f"{shell}: the ignore-unknown-fields mutant was expected to "
                                 "accept — if it refused, this fixture cannot discriminate")
        finally:
            os.unlink(mutant)


# ==================================================================================================
# Chunk 6
# ==================================================================================================
"""COREDEV-2617 mutant-table rows, chunk 6 — EXECUTED mutation tests.

Covered here: rows 6, 13, 22, 28, 45, 60, 108, 114, 128, 134, 140, 147.
Each test builds the row's mutant from the SHIPPED file with `with_mutation` (or presents the
row's fixture through a §7 step 3f seam), runs the SAME fixture against the shipped build and the
mutant build in BOTH shells, and asserts the two outcomes differ exactly as the row's oracle
states. The mutant run is each test's positive control: a fixture the mutant also satisfies is a
test that cannot fail, and reads exactly like one that passes.
"""

import os
import shutil
import tempfile
import unittest


#: Protocol-variable reset between two resolutions in ONE body (§7 step 3f).
RESET_C6 = ('unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE '
         '_UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL\n')
TUPLE_C6 = ('printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" '
         '"$_UNLEASHED_POINTER_STATE"')

#: A DELEGATING rename of the stat probe, so a fixture can present a machine state an unprivileged
#: harness cannot chmod (a group-writable `/`; a directory whose mode must change MID-publish)
#: while every other path still gets the SHIPPED probe. `typeset -f` prints the CURRENT definition
#: in both shells, so the delegate is never a paraphrased copy.
STAT_RENAME = ('_u_stat_src="$(typeset -f _u_stat)"\n'
               'eval "_u_stat_real${_u_stat_src#_u_stat}"\n')


@unittest.skipUnless(DARWIN, "every row here drives the Darwin P-2/ACL arms or Darwin chmod semantics")
class RowsChunk6(unittest.TestCase):

    MKSTORE = ('_unleashed_name_max "{s}" >/dev/null || exit 9\n'
               '_unleashed_create_store "{s}" || exit 9\n')
    #: A well-formed entry written BY HAND (not via the publisher), as ReaderOrderedRules does:
    #: the target's encoded name, its single line, an explicit mode.
    ENTRY = ('_unleashed_key "{t}"; printf "%s\\n" "{t}" > "{s}/base.$_UNLEASHED_KEY"; '
             '/bin/chmod {m} "{s}/base.$_UNLEASHED_KEY"\n')

    def setUp(self):
        # A scratch HOME under ~/.claude (§7 step 3f(i)): /tmp is 1777, so a chain under it could
        # never authenticate and every fixture would be stale for the WRONG reason.
        self.home = scratch_home("rows2617.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.base = os.path.join(self.home, "base")
        os.makedirs(self.base)
        os.chmod(self.base, 0o700)

    def tearDown(self):
        # Fixtures below lock directories down (0500 stores, 0775 ancestors, sticky bits);
        # restore owner access top-down so rmtree can clean them.
        os.chmod(self.home, 0o700)
        for dirpath, dirnames, _ in os.walk(self.home):
            for d in dirnames:
                try:
                    os.chmod(os.path.join(dirpath, d), 0o700)
                except OSError:
                    pass
        shutil.rmtree(self.home, ignore_errors=True)

    @staticmethod
    def _diags(err):
        """The resolver's own diagnostics only, never incidental shell noise."""
        return [l for l in err.splitlines() if l.startswith("unleashed-mail:")]

    def _clean(self):
        shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)

    def test_row_006_target_that_is_not_a_directory(self):
        """TGT-1: a target that EXISTS but is a regular file is a FAILING entry — stale, one diagnostic — and a conforming entry beside it does not win."""
        ftarget = os.path.join(self.home, "file-target")
        with open(ftarget, "w", encoding="utf-8") as fh:
            fh.write("x\n")
        os.chmod(ftarget, 0o600)
        # The mutant accepts any EXISTING target. The target-chain walk does NOT rescue the
        # verdict: PCH-1 refuses writability/ownership/ACL, never file TYPE, and a 0600 regular
        # file satisfies every one of those clauses — so under the mutant the entry authenticates
        # and the conforming neighbour turns the store from stale into conflict.
        mutant = with_mutation('[ -d "$_ae_line" ] || return 1',
                               '[ -e "$_ae_line" ] || return 1', path=READER)
        try:
            for shell in SHELLS:
                for libs, want in (((AUTH, STORE, READER, PUB), "0 unresolved stale"),
                                   ((AUTH, STORE, mutant, PUB), "0 unresolved conflict")):
                    self._clean()
                    body = (self.MKSTORE.format(s=self.store)
                            + self.ENTRY.format(t=ftarget, s=self.store, m=600)
                            + self.ENTRY.format(t=self.base, s=self.store, m=600)
                            + RESET_C6
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C6)
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(1, len(self._diags(err)), f"{shell}: one diagnostic")
        finally:
            os.unlink(mutant)

    def test_row_013_group_writable_target_ancestor(self):
        """ST-4/PCH-1 on the TARGET chain: a safe target beneath a 0775 ancestor is a FAILING entry — stale, one diagnostic — and a conforming entry beside it does not win."""
        gw = os.path.join(self.home, "gw")
        target = os.path.join(gw, "t")
        os.makedirs(target)
        os.chmod(target, 0o700)
        os.chmod(gw, 0o775)
        mutant = with_mutation('case "$_U_MODE" in *[2367]?) return 1 ;; esac   # group-writable',
                               'case "$_U_MODE" in *[2367]?) : ;; esac   # group-writable',
                               path=AUTH)
        try:
            for shell in SHELLS:
                for libs, want in (((AUTH, STORE, READER, PUB), "0 unresolved stale"),
                                   ((mutant, STORE, READER, PUB), "0 unresolved conflict")):
                    self._clean()
                    body = (self.MKSTORE.format(s=self.store)
                            + self.ENTRY.format(t=target, s=self.store, m=600)
                            + self.ENTRY.format(t=self.base, s=self.store, m=600)
                            + RESET_C6
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C6)
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(1, len(self._diags(err)), f"{shell}: one diagnostic")
        finally:
            os.unlink(mutant)

    def test_row_022_group_writable_ancestor_in_the_entry_chain(self):
        """PCH-1 over the WHOLE chain, parent included: a 0775 grandparent (unleashed-mail/) refuses as stale with one diagnostic."""
        # The 0775 component sits ABOVE the store, so rule −1's chain walk is what refuses it —
        # distinct from the 0755-store fixture (store's OWN exact mode) and from StoreCreation's
        # group-writable-ancestor test, which pins the CREATE refusal, not the reader outcome.
        mid = os.path.join(self.home, ".claude", "unleashed-mail")
        mutant = with_mutation('case "$_U_MODE" in *[2367]?) return 1 ;; esac   # group-writable',
                               'case "$_U_MODE" in *[2367]?) : ;; esac   # group-writable',
                               path=AUTH)
        try:
            for shell in SHELLS:
                for libs, want, ndiag in (((AUTH, STORE, READER, PUB), "0 unresolved stale", 1),
                                          ((mutant, STORE, READER, PUB), "1 pointer none", 0)):
                    self._clean()
                    body = (self.MKSTORE.format(s=self.store)
                            + self.ENTRY.format(t=self.base, s=self.store, m=600)
                            + f'/bin/chmod 775 "{mid}"\n'
                            + RESET_C6
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C6)
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(ndiag, len(self._diags(err)), f"{shell}: diagnostics")
        finally:
            os.unlink(mutant)

    def test_row_028_group_writable_system_prefix(self):
        """ANCHOR-1 exempts the system prefix from OWNERSHIP only, never from the writability clauses: a group-writable `/` refuses everything — stale, one diagnostic."""
        # `/` cannot be chmod'ed by an unprivileged harness (N6-10), so the fixture presents it
        # through a DELEGATING stat wrapper: every path gets the shipped probe; `/` alone reports
        # mode 0775 (its real uid 0 and size pass through). The MUTATION stays in the shipped
        # file: it grants the writability clauses ANCHOR-1's uid-0 prefix exemption.
        wrap = (STAT_RENAME
                + '_u_stat() {\n'
                  '  _u_stat_real "$1" || return 1\n'
                  '  if [ "$1" = / ]; then _U_MODE=0775; fi\n'
                  '  return 0\n'
                  '}\n')
        mutant = with_mutation(
            'case "$_U_MODE" in *[2367]?) return 1 ;; esac   # group-writable',
            'case "$_U_MODE" in *[2367]?) { [ "$_u_ac_in_prefix" = 1 ] && [ "$_U_UID" = 0 ]; } '
            '|| return 1 ;; esac   # group-writable', path=AUTH)
        try:
            for shell in SHELLS:
                for libs, want, ndiag in (((AUTH, STORE, READER, PUB), "0 unresolved stale", 1),
                                          ((mutant, STORE, READER, PUB), "1 pointer none", 0)):
                    self._clean()
                    body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                            + wrap + RESET_C6
                            + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C6)
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(ndiag, len(self._diags(err)), f"{shell}: diagnostics")
        finally:
            os.unlink(mutant)

    def test_row_045_encoder_forks_zero_times(self):
        """ENC-2: the key derivation forks ZERO times — under `ulimit -u 1` every fork fails, and the shipped encoder still derives the exact key while a command-substitution variant cannot."""
        # Scoped to the KEY DERIVATION alone (the row's own scoping): the body calls
        # `_unleashed_key`, not the resolver, whose ACL enumerator legitimately forks.
        mutant = with_mutation('printf -v _uk_n "%d" "\'$_uk_c"',
                               '_uk_n="$(printf "%d" "\'$_uk_c")"', path=STORE)
        body = ('ulimit -u 1 2>/dev/null || { printf CANNOT-LIMIT; exit 0; }\n'
                '_unleashed_key /tmp/abc 2>/dev/null\n'
                'printf "%s" "$_UNLEASHED_KEY"')
        try:
            for shell in SHELLS:
                rc, out, err = run_shell(shell, body)
                self.assertEqual("_stmp_sabc", out,
                                 f"{shell}: the shipped encoder must derive the key with no fork available: {err}")
                rc, out, err = run_shell(shell, body, sources=(AUTH, mutant, READER, PUB))
                self.assertNotEqual("_stmp_sabc", out,
                                    f"{shell}: the CONTROL did not fail — the fork barrier is not discriminating")
        finally:
            os.unlink(mutant)

    def test_row_060_post_scan_stale_exit_maps_to_stale(self):
        """PUB-9 P2: a publish that sees a FAILING entry beside its own reports `stale` — the exact enum value §6 derives, not a neighbouring one."""
        # E2/E3 -> failed, P3 -> conflict and P4 -> created/current are already pinned by the
        # PublisherAndEndToEnd and seam tests; P2 -> stale had no executed pin at all.
        mutant = with_mutation('_unleashed_pub_state stale',
                               '_unleashed_pub_state conflict', path=PUB)
        try:
            for shell in SHELLS:
                for libs, want in (((AUTH, STORE, READER, PUB), "stale"),
                                   ((AUTH, STORE, READER, mutant), "conflict")):
                    self._clean()
                    # base.junk: name is no encoding of its content and the content fails TGT-1,
                    # so it is a FAILING entry; the second publish's own entry authenticates.
                    body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                            f'printf "junk\\n" > "{self.store}/base.junk"; '
                            f'/bin/chmod 600 "{self.store}/base.junk"\n'
                            + RESET_C6
                            + f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                            'printf "%s" "$_UNLEASHED_POINTER_STATE"')
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(want, out, f"{shell}: {err}")
        finally:
            os.unlink(mutant)

    def test_row_108_failed_publish_diagnoses_every_invocation(self):
        """PUB-11: every publish exit reporting `failed` emits EXACTLY ONE stderr line, on EVERY invocation — a store at a refusing mode never fails in silence."""
        # A 0500 store passes E4's chain (0500 is neither group- nor other-writable) and fails at
        # E6: the transient cannot be created in an unwritable directory. Nothing repairs it, so
        # the SAME exit fires on every invocation — each must diagnose, once.
        e1 = os.path.join(self.home, "err1")
        e2 = os.path.join(self.home, "err2")
        mutant = with_mutation(
            "    printf 'unleashed-mail: plugin-state publication failed: %s\\n' \"$1\" >&2",
            "    :", path=PUB)
        try:
            for shell in SHELLS:
                for libs, counts in (((AUTH, STORE, READER, PUB), (1, 1)),
                                     ((AUTH, STORE, READER, mutant), (0, 0))):
                    self._clean()
                    body = (self.MKSTORE.format(s=self.store)
                            + f'/bin/chmod 500 "{self.store}"\n'
                            + f'_unleashed_publish "{self.store}" "{self.base}" 2>"{e1}"\n'
                            'printf "%s|" "$_UNLEASHED_POINTER_STATE"\n'
                            + RESET_C6
                            + f'_unleashed_publish "{self.store}" "{self.base}" 2>"{e2}"\n'
                            'printf "%s" "$_UNLEASHED_POINTER_STATE"')
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual("failed|failed", out, f"{shell}: {err}")
                    for path, wantn in zip((e1, e2), counts):
                        with open(path, encoding="utf-8") as fh:
                            lines = fh.read().splitlines()
                        self.assertEqual(wantn, len(lines), f"{shell}: {path}: {lines}")
                    os.chmod(self.store, 0o700)
        finally:
            os.unlink(mutant)

    def test_row_114_mode_is_compared_on_all_twelve_bits(self):
        """P-2/ST-3/ENT-1: a `chmod 1700` store and a `chmod 4600` entry both refuse as stale — a nine-bit comparison reports 700/600 for exactly these fixtures and resolves."""
        # BOTH P-2 arms are mutated to a nine-bit mask, because each arm alone would leave the
        # other shell discriminating and the divergence invisible to a single-arm test.
        t2 = os.path.join(self.home, "t2")
        os.makedirs(t2)
        os.chmod(t2, 0o700)
        m1 = with_mutation('$(( ${_u_h[mode]} & 4095 ))', '$(( ${_u_h[mode]} & 511 ))', path=AUTH)
        m2 = with_mutation('_U_MODE="${_U_MODE: -4}"', '_U_MODE="0${_U_MODE: -3}"', path=m1)
        try:
            for shell in SHELLS:
                # (a) the sticky store: rule −1's exact-0700 clause.
                for libs, want in (((AUTH, STORE, READER, PUB), "0 unresolved stale"),
                                   ((m2, STORE, READER, PUB), "1 pointer none")):
                    self._clean()
                    body = (self.MKSTORE.format(s=self.store)
                            + self.ENTRY.format(t=self.base, s=self.store, m=600)
                            + f'/bin/chmod 1700 "{self.store}"\n'
                            + RESET_C6 + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C6)
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(want, out, f"{shell} store-1700: {err}")
                # (b) the setuid entry beside a conforming one: rule 1, and the conforming
                # entry must NOT win.
                for libs, want in (((AUTH, STORE, READER, PUB), "0 unresolved stale"),
                                   ((m2, STORE, READER, PUB), "0 unresolved conflict")):
                    self._clean()
                    body = (self.MKSTORE.format(s=self.store)
                            + self.ENTRY.format(t=t2, s=self.store, m=4600)
                            + self.ENTRY.format(t=self.base, s=self.store, m=600)
                            + RESET_C6 + f'_unleashed_read_store "{self.store}"\n' + TUPLE_C6)
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(want, out, f"{shell} entry-4600: {err}")
        finally:
            os.unlink(m2)
            os.unlink(m1)

    def test_row_128_failed_cleanup_rm_stays_one_diagnostic_and_inert(self):
        """ST-7/PUB-11: when bases/ loses write permission AFTER the transient exists, the cleanup `rm` fails — still `failed` with EXACTLY ONE diagnostic, the leftover `.pub.*` is never enumerated, and the prior resolution is unchanged."""
        # The moment "after the transient is created" is P-4's mode READBACK: the delegating stat
        # wrapper chmods bases/ to 0500 when it sees the transient's own path, then answers with
        # the shipped probe — so the mv and then the rm both fail on a directory that was
        # writable when the transient was made. The mutant is the row's named defect: treating
        # the failed cleanup as a failure OF THE PUBLISH, which emits a second diagnostic.
        t2 = os.path.join(self.home, "t2")
        os.makedirs(t2)
        os.chmod(t2, 0o700)
        e1 = os.path.join(self.home, "err1")
        wrap = (STAT_RENAME
                + '_u_stat() {\n'
                  '  case "$1" in\n'
                  f'    */.pub.*) /bin/chmod 500 "{self.store}" ;;\n'
                  '  esac\n'
                  '  _u_stat_real "$1"\n'
                  '}\n')
        mutant = with_mutation(
            '        if ! /bin/mv -f "$_UNLEASHED_TRANSIENT" "$_pb_entry" >/dev/null 2>&1; then\n'
            '            /bin/rm -f "$_UNLEASHED_TRANSIENT" >/dev/null 2>&1\n',
            '        if ! /bin/mv -f "$_UNLEASHED_TRANSIENT" "$_pb_entry" >/dev/null 2>&1; then\n'
            '            /bin/rm -f "$_UNLEASHED_TRANSIENT" >/dev/null 2>&1 || '
            '_unleashed_pub_failed "the plugin-state transient could not be removed"\n', path=PUB)
        try:
            for shell in SHELLS:
                for libs, wantn in (((AUTH, STORE, READER, PUB), 1),
                                    ((AUTH, STORE, READER, mutant), 2)):
                    self._clean()
                    body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                            + wrap + RESET_C6
                            + f'_unleashed_publish "{self.store}" "{t2}" 2>"{e1}"\n'
                            'printf "%s|" "$_UNLEASHED_POINTER_STATE"\n'
                            + f'/bin/chmod 700 "{self.store}"\n'
                            + 'eval "_u_stat${_u_stat_src#_u_stat}"\n'  # restore the shipped probe
                            + RESET_C6
                            + f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                            + 'printf "%s %s %s %s" "$_UNLEASHED_BASE_OK" '
                              '"$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE" '
                              '"$_UNLEASHED_BASE_RESOLVED"')
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(f"failed|1 pointer none {self.base}", out, f"{shell}: {err}")
                    with open(e1, encoding="utf-8") as fh:
                        lines = fh.read().splitlines()
                    self.assertEqual(wantn, len(lines), f"{shell}: {lines}")
                    leftovers = [f for f in os.listdir(self.store) if f.startswith(".pub.")]
                    self.assertEqual(1, len(leftovers),
                                     f"{shell}: the failed rm must leave the transient behind")
        finally:
            os.unlink(mutant)

    def test_row_134_store_mkdir_by_absolute_path(self):
        """PUB-11/ST-2: the store mkdir never goes through PATH — a PATH shim whose mkdir ignores `-m` is never consulted by the shipped publisher, while the mutant's 0755 store poisons EVERY subsequent read (stale, one diagnostic, same on a second run)."""
        # ST-4 ACCEPTS the umask-default 0755 for ancestors and ST-3 REFUSES it for bases/, and
        # ST-3 forbids repair — so the poisoning is DURABLE, which the second read pins.
        shim = os.path.join(self.home, "shim")
        os.makedirs(shim)
        os.chmod(shim, 0o700)
        log = os.path.join(self.home, "mkdir-consulted")
        with open(os.path.join(shim, "mkdir"), "w", encoding="utf-8") as fh:
            fh.write('#!/bin/sh\nprintf x >> "%s"\nif [ "$1" = "-m" ]; then shift 2; fi\n'
                     'exec /bin/mkdir "$@"\n' % log)
        os.chmod(os.path.join(shim, "mkdir"), 0o755)
        mutant = with_mutation('if /bin/mkdir -m 700 "$_cs_d" 2>/dev/null; then',
                               'if mkdir -m 700 "$_cs_d" 2>/dev/null; then', path=STORE)
        e1 = os.path.join(self.home, "err1")
        e2 = os.path.join(self.home, "err2")
        try:
            for shell in SHELLS:
                cases = (((AUTH, STORE, READER, PUB),
                          "created|1 pointer none|1 pointer none", 0o700, False, (0, 0)),
                         ((AUTH, mutant, READER, PUB),
                          "created|0 unresolved stale|0 unresolved stale", 0o755, True, (1, 1)))
                for libs, want, mode, consulted, counts in cases:
                    self._clean()
                    if os.path.exists(log):
                        os.unlink(log)
                    body = ('umask 022\n'
                            f'PATH="{shim}:$PATH"; export PATH\n'
                            f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                            'printf "%s|" "$_UNLEASHED_POINTER_STATE"\n'
                            + RESET_C6
                            + f'_unleashed_read_store "{self.store}" 2>"{e1}"\n'
                            'printf "%s %s %s|" "$_UNLEASHED_BASE_OK" '
                            '"$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"\n'
                            + RESET_C6
                            + f'_unleashed_read_store "{self.store}" 2>"{e2}"\n'
                            + TUPLE_C6)
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(want, out, f"{shell}: {err}")
                    self.assertEqual(mode, os.stat(self.store).st_mode & 0o7777,
                                     f"{shell}: store mode")
                    self.assertEqual(consulted, os.path.exists(log),
                                     f"{shell}: PATH-shim consultation")
                    for path, wantn in zip((e1, e2), counts):
                        with open(path, encoding="utf-8") as fh:
                            lines = fh.read().splitlines()
                        self.assertEqual(wantn, len(lines), f"{shell}: {path}: {lines}")
        finally:
            os.unlink(mutant)

    def test_row_140_principal_resolved_once_per_resolution(self):
        """BUD-1/P-3a: exactly ONE `id -un` per resolution, counted at the IDENTITY-PROBE seam itself — a per-component mutant multiplies the count while every protocol variable is UNCHANGED, so the count is the only oracle that can see it."""
        # The counter wraps `_u_identity_probe`, NOT the ACL enumerator: row 132's extra chain
        # walk raises the `ls -lde` count too, so an enumerator-counting harness would pass that
        # row while counting no `id` at all — the defect round 110 fixed in BUD-1.
        cnt = os.path.join(self.home, "idprobe-count")
        m1 = with_mutation('    [ "${_U_PRINCIPAL_PROBED:-}" = 1 ] && return 0', '    :', path=AUTH)
        m2 = with_mutation('        _u_stat "$_u_ac_c" || return 1                  # must exist',
                           '        _u_principal || return 1\n'
                           '        _u_stat "$_u_ac_c" || return 1                  # must exist',
                           path=m1)
        try:
            for shell in SHELLS:
                self._clean()
                rc, out, err = run_shell(
                    shell, f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                           'printf "%s" "$_UNLEASHED_POINTER_STATE"')
                self.assertEqual("created", out, f"{shell}: fixture publish failed: {err}")
                seam = (f': > "{cnt}"\n'
                        '_u_identity_probe() { printf "x\\n" >> "' + cnt
                        + '"; /usr/bin/id -un 2>/dev/null; }\n')
                body = (seam + RESET_C6
                        + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + TUPLE_C6)
                for libs, ok in (((AUTH, STORE, READER, PUB), lambda n: n == 1),
                                 ((m2, STORE, READER, PUB), lambda n: n > 1)):
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual("1 pointer none", out,
                                     f"{shell}: the protocol variables must be UNCHANGED: {err}")
                    with open(cnt, encoding="utf-8") as fh:
                        n = len(fh.read().splitlines())
                    self.assertTrue(ok(n), f"{shell}: id -un probe count {n}")
        finally:
            os.unlink(m2)
            os.unlink(m1)

    def test_row_147_duplicate_inherited_token_through_the_seam(self):
        """ACL-2/ACL-4 at STORE level: an ACE with a DOUBLED `inherited` before the verb is unevaluable — stale through the production resolver — while a mutant that absorbs the extra token evaluates it as well-formed read-only and RESOLVES."""
        # `inherited` as field 1 is the row's other shape; under this same absorbing mutant the
        # missing principal still refuses it, so the DOUBLED token is the discriminating fixture
        # — the same masking that made row 144's control unable to fail (see the unit-level note
        # in test_control_a_positional_verb_parser_fails_open_on_an_inherited_ace). That
        # `/bin/ls -lde` never emits this shape is NOT a reason to accept it: the seam exists
        # precisely because an arm that predicts a healthy enumerator is not enforcing a grammar.
        mutant = with_mutation(
            '                inherited)  if [ "$_u13_n" = 1 ] || [ "$_u13_inh" = 1 ]; '
            'then return 1; fi\n'
            '                            _u13_inh=1 ;;                       '
            '# optional, singular, never field 1',
            '                inherited)  _u13_inh=1 ;;', path=AUTH)
        seam = ('_u_acl_enumerate() { printf %b "drwx------@ 2 n s 64 d\\n'
                ' 0: group:staff inherited inherited allow list\\n"; }\n')
        try:
            for shell in SHELLS:
                for libs, want in (((AUTH, STORE, READER, PUB), "0 unresolved stale"),
                                   ((mutant, STORE, READER, PUB), "1 pointer none")):
                    self._clean()
                    body = (f'_unleashed_publish "{self.store}" "{self.base}" 2>/dev/null\n'
                            + seam + RESET_C6
                            + f'_unleashed_read_store "{self.store}" 2>/dev/null\n' + TUPLE_C6)
                    rc, out, err = run_shell(shell, body, sources=libs)
                    self.assertEqual(want, out, f"{shell}: {err}")
        finally:
            os.unlink(mutant)


if __name__ == "__main__":
    unittest.main()
