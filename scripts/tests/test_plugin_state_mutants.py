#!/usr/bin/env python3
"""COREDEV-2617 — the mutant table, EXECUTED.

Each test builds one row's mutation against the SHIPPED shell (by exact substring, or through a
step-3f seam), runs the row's fixture against the shipped build and the mutant build in BOTH
bash 3.2.57 and zsh 5.9, and asserts the outcomes DIFFER. A row whose two builds agree cannot fail
and proves nothing — four such rows were found while writing these and are recorded in the plan
campaign's findings file rather than faked here.

Assembled from six parallel drafting agents; every row carries the run evidence its drafter measured,
and THIS suite's own run is the gate — the evidence informed assembly, it is not the verification.
Rows 156-162 (PR #67, codex pass 7) were added afterwards as `RowsPass7`, at the end of the file;
rows 163-164 (PR #67, codex pass 8), row 165 (PR #67, codex pass 9), rows 166-168 (PR #67, codex
pass 11), row 169 (external audit of PR #67, finding 1) and row 170 (PR #67, codex pass 12 — which also
RESHAPED rows 158 and 167: paths.sh's definition block is now unconditional, so those mutations ADD a
guard where the specification has none) and row 171 (PR #67, codex pass 13 — a component that APPEARED
between E4's steps (i) and (ii)) joined that class, as did rows 172-173 (PR #67, codex pass 14 — the
machinery RE-SOURCED rather than trusted because it is present, and the instance stamp set once, errexit-safe
and global under zsh; that pass also RESHAPED rows 92, 157 and 159, whose fixtures had relied on the resolver
KEEPING a seam or a mutant machinery file sourced ahead of it), and finally rows 174-177 (the codex sweep of
PR #67 pass 14: the library directory not derived through PATH, sourcing surviving `set -e` when the stamp
arrives through the environment, the readonly-attribute test reading the FLAG LETTERS only, and the effective
uid PROBED rather than read from `$EUID` — which bash 3.2, the `/bin/bash` a macOS hook runs, imports from
the environment). That sweep also re-pinned rows 7, 23, 24 and 166, whose anchors quote text it rewrote.
Row 178 (PR #67, codex pass 15) closes the last of ENT-2b's residuals: an equal INODE is not a bare
PATHNAME, so the entry name is re-tested after the read (ENT-2c). It also RESHAPED rows 160 and 168 —
160's slice now runs through the re-test that closes the bash arm, and 168 removes EVERY binding to
`_ae_ino` (the re-test refused 168's copy on its own the moment it landed, which is how the third clause
was found). Rows 179-183 (PR #67, codex pass 17) are `RowsPass17` at the end of the file, and they are
all ORDINARY-ENVIRONMENT rows — a caller with globbing off, a plugin-data directory that does not exist
yet, a `.` or `..` in the value, two hooks publishing at once, and a harness that clears HOME. Row 183
is the one row here whose fix is a STATED FACT rather than a behaviour: no post-startup test separates
zsh's passwd-filled `HOME` from a caller who set it, so that row pins the statement and mutates the
opt-out that is the actual protection.

Rows 186-188 (PR #67, codex pass 23) join `RowsPass17` and are ONE CLASS with row 179: inherited shell
state the libraries never neutralised. `failglob` is a separate bash option from row 179's `noglob` and
is FATAL on an empty store; `nocasematch` makes the encoder's upper-case `case` arms match lower-case
bytes, so `/a` and `/A` collide and ENC-1's injectivity is gone; and a READONLY `LC_ALL` cannot be
assigned to at all — the assignment kills the shell in both, and no shell-level guard survives it — so
the attribute is DETECTED fork-free instead, `C.UTF-8` is REFUSED because it is a UTF-8 locale, and an
accepted readonly `C` is left entirely alone (a third restore state, because `unset` of a readonly is
fatal in zsh). Each of those three was reproduced before its fix and each mutation below was checked to
DISCRIMINATE by a per-mutation sweep — every mutation of a shipped file fails its row when neutered.
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
        # (The owner clause reads the euid through `_u_euid` since PR #67 pass 14 — bash 3.2 IMPORTS
        # `$EUID` from the environment, so `${EUID:-…}` let the parent decide it, row 177. The MUTATION
        # is unchanged: the entry's owner check is dropped.)
        mutant = with_mutation(
            '    [ "$_U_MODE" = 0600 ] || return 1                # TWELVE bits: `chmod 4600` must not pass as 0600\n'
            '    { _u_euid && [ "$_U_UID" = "$_U_EUID" ]; } || return 1\n',
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
        # (Same rule, re-pinned on the `_u_euid` spelling PR #67 pass 14 introduced — row 177.)
        mutant = with_mutation(
            '            { _u_euid && [ "$_U_UID" = "$_U_EUID" ]; } || return 1\n',
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
        # RE-PINNED (PR #67 pass 17, row 179): the scan's `setopt` line now also carries `glob`, and
        # the mutation drops `no_nomatch` ALONE rather than the whole line — dropping the line would
        # take the glob-forcing with it and this row would then be discriminating on row 179's rule
        # as well as its own.
        mutant = with_mutation('setopt local_options no_nomatch glob', 'setopt local_options glob',
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
        #
        # THE MUTATION COVERS BOTH SPELLINGS OF THE ENUMERATOR, and it must. PF-1 added a second one:
        # `_u_chain_prefetch` runs `/bin/ls -lde -d` over the whole chain and `_u_acl_enumerate`
        # serves that answer from the cache. Mutating only the per-path spelling left the batch on
        # `/bin/ls`, every component hit the cache, `getfacl` was never reached and the two builds
        # AGREED — a row that had stopped discriminating while still passing its own anchor check.
        # So the PATH-selected enumerator is planted at both sites. With the fake `getfacl` on PATH
        # the batch answers `garbage`, which names no component, so the ACL cache is discarded and
        # every component falls through to the per-path mutant — which is the machine the row is
        # about.
        m1 = with_mutation(
            '    /bin/ls -lde -- "$1" 2>/dev/null\n}\n',
            '    if command -v getfacl >/dev/null 2>&1; then getfacl -- "$1" 2>/dev/null; '
            'else /bin/ls -lde -- "$1" 2>/dev/null; fi\n}\n',
            path=AUTH)
        mutant = with_mutation(
            '    _u_cp_ls="$(/bin/ls -lde -d -- "$@" 2>/dev/null)" || _u_cp_ls=""\n',
            '    if command -v getfacl >/dev/null 2>&1; then\n'
            '        _u_cp_ls="$(getfacl -- "$@" 2>/dev/null)" || _u_cp_ls=""\n'
            '    else\n'
            '        _u_cp_ls="$(/bin/ls -lde -d -- "$@" 2>/dev/null)" || _u_cp_ls=""\n'
            '    fi\n',
            path=m1)
        os.unlink(m1)
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
        # RE-PINNED (PR #67 pass 17, row 182): the post-scan's own-entry check is now captured in
        # `_pb_own` ahead of E7b's single rescan, so the P1 branch tests that variable. The MUTATION
        # is unchanged in meaning — P1 fires only when this process wrote.
        mutant = with_mutation(
            '    if [ "$_pb_own" = 0 ]; then\n',
            '    if [ "$_pb_wrote" = 1 ] && [ "$_pb_own" = 0 ]; then\n',
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
        # RE-PINNED (PR #67 pass 17, row 182): the own-entry verdict is `_pb_own` now, decided before
        # E7b's rescan. The mutation still SWAPS P1 and P2, which is this row's whole content.
        mutant = with_mutation(
            '    if [ "$_pb_own" = 0 ]; then\n'
            '        _unleashed_pub_failed "this process\'s own plugin-state entry is missing or unusable"   # P1\n'
            '    elif [ "$_UNLEASHED_FAILED" -gt 0 ]; then\n'
            '        _unleashed_pub_state stale                                                             # P2\n',
            '    if [ "$_UNLEASHED_FAILED" -gt 0 ]; then\n'
            '        _unleashed_pub_state stale                                                             # P2\n'
            '    elif [ "$_pb_own" = 0 ]; then\n'
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
        """An entry holding backslash + trailing space resolves in both shells; in BASH a plain `read` mangles it ⇒ stale. The zsh arm reads raw bytes through `sysread` (ENT-2b) and has no `read` to mutate — its half asserts the SPEC only (plan row 160 records this consequence)."""
        # TGT-1 permits both bytes. Measured (probe + this test): under bash's ENT-2b arm a plain
        # `read -n … -u 9` yields the mangled value — the backslash is eaten and the trailing space
        # IFS-stripped — so ENT-2/ENT-3 fail and the store refuses a healthy entry. Row 4 is the
        # multi-line case and cannot discriminate this single-line transformation. zsh's arm has
        # no `IFS= read -r` at all (`sysread` delivers the bytes untouched), so the mutation has
        # no target there and both builds resolve; that half is the specification's behaviour only.
        mutant = with_mutation(
            'IFS= read -r -n "$_ae_bound" -u 9 _ae_line',
            'read -n "$_ae_bound" -u 9 _ae_line',
            path=READER)
        weird = os.path.join(self.home, "a\\b ")           # backslash, trailing space
        os.makedirs(weird)
        os.chmod(weird, 0o700)
        try:
            for shell in SHELLS:
                bash = shell.endswith("bash")
                for srcs, want, want_diag in (
                        ((AUTH, STORE, READER, PUB), f"1 pointer none|{weird}", 0),
                        (self._sources(mutant, READER),
                         ("0 unresolved stale|/dev/null/unresolved-plugin-base" if bash
                          else f"1 pointer none|{weird}"),
                         1 if bash else 0)):
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
        # ACL-2/P-3a: only `user:<us>` — or a bare UUID EQUAL to the effective user's resolved UUID
        # (row 169; external audit of PR #67, finding 1) — is us; an identity the system could not
        # resolve must not be proof of ownership. The fixture's UUID is not the effective user's, so
        # the UUID-self clause misses and the specification refuses. The mutant reads ANY bare UUID
        # as the effective user (the clause replaced by an unconditional `return 0`) and the
        # component accepts. Anchored on the CURRENT clause line, whole.
        mutant = with_mutation(
            '            [ -n "${_U_PRINCIPAL_UUID:-}" ] && [ "$_u13_principal" = "$_U_PRINCIPAL_UUID" ] '
            '&& return 0 ;;\n',
            '            return 0 ;;\n',
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
        # Row 56 puts a REAL `group:everyone deny delete` ACE on `base`; rmtree cannot unlink it
        # and, with ignore_errors, said nothing — measured, every run left `~/.claude/rc2617.*/base`
        # behind (42 on one machine). Strip every ACL and restore 0700 first, then remove LOUDLY.
        if DARWIN:
            for root, dirs, _files in os.walk(self.home):
                for d in dirs:
                    subprocess.run(["/bin/chmod", "-N", os.path.join(root, d)],
                                   check=False, capture_output=True)
        for root, dirs, _files in os.walk(self.home):
            for d in dirs:
                try:
                    os.chmod(os.path.join(root, d), 0o700)
                except OSError:
                    pass
        shutil.rmtree(self.home)

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
        # (Same rule, re-pinned on the `_u_euid` spelling PR #67 pass 14 introduced — row 177.)
        mutant = with_mutation(
            '            { _u_euid && [ "$_U_UID" = "$_U_EUID" ]; } || return 1',
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
        # RE-PINNED (PR #67 pass 17, row 182): the post-scan is now `scan; capture; maybe rescan`, so
        # m2 removes the FIRST (post-)scan only — which is the whole of this row's mutation, "scan
        # before publishing and not after". E7b's rescan is unreachable in this fixture (the racer's
        # own entry authenticates and nothing failed), so removing it as well would change nothing.
        m2 = with_mutation(
            '    _unleashed_scan_store "$_pb_store"\n'
            '    _pb_own=0; _unleashed_auth_entry "$_pb_entry" && _pb_own=1\n'
            '    if [ "$_pb_own" = 0 ] || [ "$_UNLEASHED_FAILED" -gt 0 ]; then\n',
            '    _pb_own=0; _unleashed_auth_entry "$_pb_entry" && _pb_own=1\n'
            '    if [ "$_pb_own" = 0 ] || [ "$_UNLEASHED_FAILED" -gt 0 ]; then\n', path=m1)
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
        # RE-PINNED (PR #67 pass 17, row 179): the guarded block now carries the glob-forcing and a
        # bash `else` arm, so the anchor is SLICED from the current file — `if` line through its `fi`
        # — rather than quoted, and the mutation replaces the whole block with the unguarded `setopt`
        # the row is about. `_ss_noglob=0` is kept so the restore line below it stays well-defined.
        with open(READER, encoding="utf-8") as fh:
            _r74 = fh.read()
        _r74_i = _r74.index('    if [ -n "${ZSH_VERSION:-}" ]; then\n        setopt local_options')
        _r74_j = _r74.index('\n    fi\n', _r74_i) + len('\n    fi\n')
        mutant = with_mutation(
            _r74[_r74_i:_r74_j],
            '    setopt local_options no_nomatch glob\n    _ss_noglob=0\n', path=READER)
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
        """Row 117: a FIFO named base.<k> yields stale + one diagnostic and the process EXITS promptly in both shells; in BASH the symlink-only mutant blocks forever. zsh half subsumed by ENT-2b / row 160: its arm opens with `sysopen -o nonblock`, so a FIFO cannot hang zsh with or without the `[ -f ]` guard, and that half asserts the SPEC only."""
        # RD-12: the TYPE is established before anything is opened. The mutation reverts to the
        # symlink-only pre-read guard, so bash's reader opens the FIFO (`9<`) and blocks waiting
        # for a writer that never comes — measured as a harness timeout. In zsh ENT-2b's
        # non-blocking open returns at once and `zstat -f` refuses the FIFO's type, so the mutant
        # returns `stale` exactly as the specification does; the hang oracle is bash-only. This is
        # the READER's obligation: ST-7 keeps the PUBLISHER from such an entry independently (row 116).
        mutant = with_mutation('    [ -f "$_ae_p" ] || return 1', '    :', path=READER)
        try:
            setup = self.ENTRY.format(t=self.base, s=self.store)
            body = self.MAKE.format(s=self.store) + setup + (
                f'/usr/bin/mkfifo -m 600 "{self.store}/base.fifo117" || exit 7\n'
            ) + self.TUPLE.format(s=self.store)
            for shell in SHELLS:
                self._fresh()
                # The specification must RETURN — a hang here is the defect, so it runs under the
                # same timeout the mutant does.
                src = "".join(f'. "{s}"\n' for s in (AUTH, STORE, READER, PUB)) + body
                try:
                    p = subprocess.run([shell, "-c", src], capture_output=True, text=True, timeout=5)
                    out, err = p.stdout, p.stderr
                except subprocess.TimeoutExpired:
                    self.fail(f"{shell}: the SHIPPED reader hung on the FIFO")
                self.assertEqual("0 unresolved stale", out, f"{shell}: shipped: {err}")
                self.assertEqual(1, len(err.strip().splitlines()), f"{shell}: one diagnostic")
                if not shell.endswith("bash"):
                    continue                    # zsh: no hang either way — see the docstring
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
        # The bash arm's read is bound to descriptor 9 (ENT-2b); the mutation swallows the read's
        # status inside that arm so `_ae_ok=1` is reached whether or not a newline was seen.
        mutant = with_mutation('&& IFS= read -r -n "$_ae_bound" -u 9 _ae_line && _ae_ok=1',
                               '&& { IFS= read -r -n "$_ae_bound" -u 9 _ae_line || :; } && _ae_ok=1',
                               path=READER)
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

    @staticmethod
    def _slice_lines(path, head, tail):
        """The CURRENT text of `path` from the unique `head` through the first `tail` after it."""
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        assert text.count(head) == 1, f"head anchor not unique in {path}: {head!r}"
        start = text.index(head)
        assert tail in text[start:], f"tail anchor not found after the head in {path}: {tail!r}"
        end = text.index(tail, start) + len(tail)
        old = text[start:end]
        assert text.count(old) == 1, f"sliced block not unique in {path}"
        return old

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
        # PF-2 re-anchored the pattern, and ONLY the pattern: `_u_acl_ok` now calls the answer machine
        # by argument instead of piping into it, so the two arms below carry that spelling. What the
        # mutant DOES is untouched — it still prepends a write probe to an otherwise shipped body,
        # and it is still the write, not the shape, that this row makes visible.
        mutant = with_mutation(
            '_u_acl_ok() {\n'
            '    _u_acl_out="$(_u_acl_enumerate "$1")" || return 1   # a failed enumerator REFUSES\n'
            '    _u_acl_answer_ok_var "$_u_acl_out"                  # PF-2: the same machine, without the pipe\n'
            '}',
            '_u_acl_ok() {\n'
            '    ( umask 077; : > "$1/.row57-acl-write-probe" ) 2>/dev/null || return 1\n'
            '    /bin/rm -f -- "$1/.row57-acl-write-probe" 2>/dev/null\n'
            '    _u_acl_out="$(_u_acl_enumerate "$1")" || return 1\n'
            '    _u_acl_answer_ok_var "$_u_acl_out"\n'
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
        # The bash arm's parse is two lines since `%i`/`_U_INO` joined the record (PR #67 pass 11);
        # the scratch is renamed on BOTH, sliced from the CURRENT file so a field added to the
        # record cannot strand the row on a stale spelling (it did, once).
        # PF-1 CHANGED WHEN THAT ARM IS REACHED, not whether the collision would bite. The prefetch
        # serves the walk's `_u_stat` calls from `_U_STAT_CACHE`, so on a chain the batch can
        # describe, NEITHER arm's per-path parse runs mid-walk and the collision has nothing to
        # overwrite — measured: with only the rename below, both mutant arms RESOLVED and this row
        # stopped discriminating while still passing its own anchor check. The mutant therefore also
        # turns the prefetch off, which is the condition under which the per-path parse is reached
        # (an unbatchable component, a `stat` that could not answer). That second mutation is
        # SHELL-AGNOSTIC — one call site, no arm mentions it — so the arm divergence the assertions
        # below demand can still only come from the collision, and the oracle is unchanged: the two
        # MUTANT ARMS are compared to each other, never to a constant.
        parse = self._slice_lines(AUTH, '        _u_st_rest="${_u_st_raw#* }"; _U_SIZE="${_u_st_rest%% *}"\n',
                                  '_U_INO="${_u_st_rest##* }"\n')
        self.assertEqual(2, parse.count("\n"), parse)
        m1 = with_mutation(parse, parse.replace("_u_st_rest", "_u_ac_rest"), path=AUTH)
        mutant = with_mutation('    _u_chain_prefetch "$1"\n', '    :\n', path=m1)
        os.unlink(m1)
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
    """Mutant-table rows 4, 10, 42, 51, 58, 64, 70, 76, 92, 99, 112, 119, 126, 132, 138, 144, 151, 153, 154, 155."""

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
        """Row 51: after a publish the entries live in .../unleashed-mail/bases/ and THAT directory is 0700 asserted directly; unleashed-mail itself may be 0755 as a PARENT, but is never itself the store."""
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
                    # The mutation now ALSO fails on state, not only on location: publishing into
                    # `unleashed-mail` at 0755 is refused since the publisher applies ST-3 through the
                    # reader's own `_unleashed_store_ok` (the Fable pre-merge review of 22f9cdf found
                    # the publisher never applied that test — a 0750/0755/0701 store was written into
                    # while every reader reported `stale`, silently). The docstring's old premise that
                    # `created` "discriminates nothing" held only while that gap existed; the oracle
                    # below — WHERE the entry sits and the MODE of the holding directory — is unchanged
                    # and still carries the row.
                    self.assertEqual("1 host-env failed" if is_mutant else "1 host-env created", out,
                                     f"{shell}: {err}")
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
                        # The mutation targets the 0755 directory, so ST-3 refuses it and NOTHING is
                        # written — which is the rule's actual requirement ("no file is written into
                        # it"). Before the publisher applied ST-3 the entry landed there instead; both
                        # outcomes discriminate, and this one is the correct behaviour.
                        self.assertFalse(os.path.exists(self.store), f"{shell}: CONTROL made bases/")
                        self.assertEqual([], direct,
                                         f"{shell}: the CONTROL did not fail — an entry was written "
                                         f"into a 0755 directory that ST-3 requires be refused")
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
        # The once-per-process guard is pid + the marker FUNCTION (PR #67 pass 11) — anchored on the
        # CURRENT guard line, whole, so a comment or clause rewrite cannot strand the row on a
        # pattern that no longer matches (this row was stranded once, on the pid-only spelling).
        mutant = with_mutation(
            '        [ "${_UNLEASHED_BASE_PID:-}" = "$$" ] && command -v _unleashed_resolved_in_process '
            '>/dev/null 2>&1 && return 0\n',
            '        :                                                   # re-resolve per consumer\n',
            path=PATHS_C4)
        cnt = os.path.join(self.home, "cnt")
        derived = 2 * self._comps(self.store) + self._comps(self.target)
        # BOTH BUILDS LIVE IN A SHADOW LIB, with the family files beside them: since PR #67 pass 12 every
        # family file sources paths.sh UNCONDITIONALLY from its own directory, so a mutant paths.sh
        # sourced first and then the REAL marker.sh would have the real paths.sh redefine the guard and
        # the control could not fail (measured: 22 for both builds). And since PR #67 pass 14 the resolver
        # RE-SOURCES the four machinery files beside it whenever they are readable, so a counting seam
        # defined in the fixture BEFORE `. paths.sh` is replaced by the real enumerator before the first
        # walk (measured: 0 for the shipped build). The seam is therefore APPENDED to each shadow's own
        # `plugin-state-auth.sh` — a later definition in the same file wins, so every re-source
        # re-installs it — and each build sources its own set.
        seam = '\n_u_acl_enumerate() { printf x >> "' + cnt + '"; /bin/ls -lde -- "$1" 2>/dev/null; }\n'
        shadows = {}
        for build in ("spec", "mut"):
            root = os.path.join(self.home, f"shadow-{build}"); lib = os.path.join(root, "scripts", "lib")
            shutil.copytree(os.path.dirname(PATHS_C4), lib)
            with open(os.path.join(lib, "plugin-state-auth.sh"), "a", encoding="utf-8") as fh:
                fh.write(seam)
            if build == "mut":
                shutil.copyfile(mutant, os.path.join(lib, "paths.sh"))
            shadows[build] = (root, lib)
        try:
            for shell in SHELLS:
                for is_mutant in (False, True):
                    root, lib = shadows["mut" if is_mutant else "spec"]
                    self._wipe()
                    body = (self._mkstore() + self._entry()
                            + f'export HOME="{self.home}"\n'
                            'unset CLAUDE_PLUGIN_DATA _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE\n'
                            'unset _UNLEASHED_POINTER_STATE _UNLEASHED_BASE_DIAGNOSED _UNLEASHED_PATHS_SH_LOADED\n'
                            '_UNLEASHED_STATE_LOADED=1; _UNLEASHED_STATE_RC=0\n'
                            f': > "{cnt}"\n'
                            f'. "{lib}/paths.sh"\n'
                            f'. "{lib}/marker.sh"\n'
                            f'. "{lib}/context.sh"\n'
                            f'. "{lib}/log.sh"\n'
                            f'. "{lib}/agent-env-bridge.sh" "" "{root}"\n'
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
                        # More than ONE walk, in whole walks: 10× here (the eager resolve of every
                        # re-sourced paths.sh plus the five primitive calls) — the exact multiple depends
                        # on how many family files re-source paths.sh, the claim does not.
                        self.assertGreater(n, derived, f"{shell}: the CONTROL did not fail — the walk is not re-run per consumer")
                        self.assertEqual(0, n % derived, f"{shell}: {n} enumerator calls is not a whole number of walks of {derived}")
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
                ("/usr/bin/stat -f '%p %z %u %i' -- \"$1\" 2>/dev/null",      # `%i`: PR #67 pass 11
                 "/usr/bin/stat -f '%p %z %u %i' -- \"$1\" >/dev/null 2>&1"),
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
        # E6 is forced on a WRITABLE store with RLIMIT_FSIZE(0): the zero-byte transient create
        # succeeds and the value write fails with EFBIG (measured: printf rc=1, size 0, rm still
        # succeeds), so the cleanup site runs. The create-and-write subshell IGNORES SIGXFSZ
        # itself so the limit surfaces as EFBIG and not as a signal death; the fixture's
        # `trap "" XFSZ` is belt-and-braces. The mutation invokes that rm through PATH,
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

    # ── row 153 ───────────────────────────────────────────────────────────────────────────────

    def test_row_153_value_written_through_a_second_open(self):
        """Row 153: the value is written THROUGH the descriptor the exclusive create returned; a symlink substituted at the transient's name the instant it exists leaves the victim UNTOUCHED, and the two-open mutant overwrites it."""
        # The interleaving is deterministic, not raced: a DEBUG trap on the publishing shell fires
        # before every simple command and substitutes a symlink to the victim the first time an EMPTY
        # regular transient exists — that is, after the create and before the write, in both builds.
        # bash needs `set -T` (functrace) or the trap is not inherited by functions and subshells;
        # zsh's fires inside the create-and-write subshell (measured, both shells: spec victim intact
        # rc=1, mutant victim overwritten). The `! -L` guard stops the trap re-firing on its own link.
        # Both builds report `failed` — the P-4 readback of the substituted symlink refuses at E6 and
        # the ST-7 cleanup removes the link — so the oracle is the VICTIM's content, not the state.
        # The OLD text is the SHIPPED create-and-write block, sliced from the CURRENT file between
        # two anchors — the subshell's opening line and the `esac` that closes its status `case` —
        # so a comment or capture rewrite inside the block cannot silently strand this row on a
        # pattern that no longer matches (it drifted twice on PR #67). Both anchors must be unique.
        with open(PUB, encoding="utf-8") as fh:
            pub_text = fh.read()
        head_153 = "    ( umask 077; set -C; trap '' XFSZ; _wt_opened=0\n"
        tail_153 = '    esac\n'
        self.assertEqual(1, pub_text.count(head_153), "row 153: the subshell's opening line is not unique")
        start_153 = pub_text.index(head_153)
        end_153 = pub_text.index(tail_153, start_153) + len(tail_153)
        old_153 = pub_text[start_153:end_153]
        self.assertEqual(1, pub_text.count(old_153), "row 153: the sliced block is not unique")
        self.assertIn('9>"$_wt_p"', old_153)
        self.assertIn('case $_wt_rc in', old_153)
        mutant = with_mutation(
            old_153,
            '    ( set -C; umask 077; : > "$_wt_p" ) 2>/dev/null || return 2\n'
            '    printf \'%s\\n\' "$_wt_value" > "$_wt_p" 2>/dev/null || return 1\n',
            path=PUB)
        victim = os.path.join(self.home, "victim")
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, READER, mutant), True)):
                    self._wipe()
                    with open(victim, "w", encoding="utf-8") as fh:
                        fh.write("VICTIM\n")
                    body = (self._mkstore()
                            + '[ -n "${BASH_VERSION:-}" ] && set -T\n'
                            + 'trap \'if [ -n "${_UNLEASHED_TRANSIENT:-}" ] && [ -f "$_UNLEASHED_TRANSIENT" ] '
                              '&& [ ! -L "$_UNLEASHED_TRANSIENT" ] && [ ! -s "$_UNLEASHED_TRANSIENT" ]; then '
                              '/bin/rm -f "$_UNLEASHED_TRANSIENT"; '
                              f'/bin/ln -s "{victim}" "$_UNLEASHED_TRANSIENT"; fi\' DEBUG\n'
                            + f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                            + 'trap - DEBUG\n'
                              'printf "STATE=%s" "$_UNLEASHED_POINTER_STATE"')
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    with open(victim, encoding="utf-8") as fh:
                        got = fh.read()
                    self.assertIn("STATE=failed", out,
                                  f"{shell}: the substituted symlink was not refused at E6: {out!r} {err!r}")
                    if not is_mutant:
                        self.assertEqual("VICTIM\n", got,
                                         f"{shell}: the write FOLLOWED a symlink substituted after the create")
                        # E6 publishes nothing: the refused readback never reaches the rename.
                        bases = [f for f in os.listdir(self.store) if f.startswith("base.")]
                        self.assertEqual([], bases, f"{shell}: E6 left a base.* entry behind: {bases}")
                    else:
                        self.assertEqual(self.target + "\n", got,
                                         f"{shell}: the CONTROL did not fail — the fixture never interleaved "
                                         f"between the mutant's two opens: {got!r}")
                    pubs = [f for f in os.listdir(self.store) if f.startswith(".pub.")]
                    self.assertEqual([], pubs, f"{shell}: the substituted link survived the E6 cleanup")
        finally:
            os.unlink(mutant)

    # ── row 154 ───────────────────────────────────────────────────────────────────────────────

    def test_row_154_refused_create_name_exists_is_a_lost_race(self):
        """Row 154: an exclusive create refused because the name now EXISTS is a LOST RACE — the attempt is consumed and the next name tried, so three plants end as E5 with THREE planted files; the mutant reports the FIRST refusal as E6 after ONE planted file."""
        # The interleaving is deterministic, not raced: a DEBUG trap on the publishing shell
        # (`set -T` in bash so functions and subshells inherit it) plants an empty 0600 regular file
        # at the transient's name the instant `_wt_p` equals `_UNLEASHED_TRANSIENT` and the name is
        # still absent — true only AFTER TMP-1's presence test has passed and BEFORE the `9>` open.
        # Measured, both shells: the plant lands in the publishing shell itself, before the
        # create-and-write subshell is entered (`_wt_opened` still unset), so `set -C` refuses the
        # open and the name exists. The trap plants ONCE per name: without that guard the mutant's
        # ST-7 cleanup removes the planted file, the condition holds again, and the trap plants a
        # SECOND time on the same name after the exit was already taken (measured: 2 plants, 1
        # orphan). Both builds report `failed`; the oracle is the diagnostic's text and the count
        # of planted files — the counter file, because E6's cleanup unlinks what it planted.
        # (A `$RANDOM` repeat across the three draws would spend an attempt on the presence test
        # without a plant; two equal 16-bit draws in three is a ~1e-4 event, not a flake source.)
        mutant = with_mutation(
            '        2) if [ -L "$_wt_p" ] || [ -e "$_wt_p" ]; then return 2; fi; return 1 ;;\n',
            '        2) return 1 ;;\n',
            path=PUB)
        plants = os.path.join(self.home, "plants")
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, READER, mutant), True)):
                    self._wipe()
                    if os.path.exists(plants):
                        os.unlink(plants)
                    body = (self._mkstore()
                            # A SEEDED $RANDOM makes the three transient names a fixed, distinct sequence in
                            # both shells (row 116 does the same); unseeded, a ~1e-4 repeat would spend an
                            # attempt on the presence test without firing the trap and skew the count.
                            + 'RANDOM=2617\n'
                            + '[ -n "${BASH_VERSION:-}" ] && set -T\n'
                            + 'trap \'if [ -n "${_wt_p:-}" ] && [ "$_wt_p" = "${_UNLEASHED_TRANSIENT:-}" ] '
                              '&& [ "$_wt_p" != "${_t154_last:-}" ] '
                              '&& [ ! -e "$_wt_p" ] && [ ! -L "$_wt_p" ]; then '
                              '_t154_last="$_wt_p"; (umask 077; : > "$_wt_p"); '
                              f'printf "%s\\n" "$_wt_p" >> "{plants}"; fi\' DEBUG\n'
                            + f'_unleashed_publish "{self.store}" "{self.target}"\n'
                            + 'trap - DEBUG\n'
                              'printf "STATE=%s" "$_UNLEASHED_POINTER_STATE"')
                    rc, out, err = run_shell(shell, body, sources=srcs)
                    self.assertIn("STATE=failed", out, f"{shell}: not `failed`: {out!r} {err!r}")
                    diags = self._diags(err)
                    self.assertEqual(1, len(diags), f"{shell}: not exactly one diagnostic: {err!r}")
                    planted = []
                    if os.path.exists(plants):
                        with open(plants, encoding="utf-8") as fh:
                            planted = [l for l in fh.read().splitlines() if l]
                    pubs = sorted(f for f in os.listdir(self.store) if f.startswith(".pub."))
                    bases = [f for f in os.listdir(self.store) if f.startswith("base.")]
                    self.assertEqual([], bases, f"{shell}: a failed publish left a base.* entry: {bases}")
                    if not is_mutant:
                        # E5: three names, each planted once, each refused as a lost race.
                        self.assertIn("no unique transient name", diags[0],
                                      f"{shell}: the exhausted lost races were not E5: {diags[0]!r}")
                        self.assertEqual(3, len(planted),
                                         f"{shell}: the trap did not plant three times: {planted}")
                        self.assertEqual(sorted(os.path.basename(p) for p in planted), pubs,
                                         f"{shell}: the store does not hold exactly the three plants: {pubs}")
                    else:
                        # E6 after the FIRST refusal — and its cleanup unlinks the one plant.
                        self.assertIn("could not be written at 0600", diags[0],
                                      f"{shell}: the CONTROL did not fail — the refusal was not E6: {diags[0]!r}")
                        self.assertEqual(1, len(planted),
                                         f"{shell}: the CONTROL did not stop at one plant: {planted}")
                        self.assertEqual([], pubs, f"{shell}: E6's cleanup left a transient: {pubs}")
        finally:
            os.unlink(mutant)

    # ── row 155 ───────────────────────────────────────────────────────────────────────────────

    def test_row_155_refused_create_name_absent_is_e6(self):
        """Row 155: an exclusive create refused while the name stays ABSENT (the store made 0500, EACCES) is E6 on the FIRST attempt — one diagnostic naming the 0600 write, no transient anywhere; the mutant spends all three attempts on it and surfaces as E5."""
        # Row 154's trap condition, but the trap makes the STORE unwritable instead of planting a
        # file: the `9>` open is refused and the name stays absent. Once per name, as in row 154,
        # so the marker file counts names, not DEBUG firings; the mutant consumes three names and
        # the marker holds three, the specification stops at one. `_wipe` runs with the store back
        # at 0700, restored in a `finally`, so the harness leaves nothing behind.
        mutant = with_mutation(
            '        2) if [ -L "$_wt_p" ] || [ -e "$_wt_p" ]; then return 2; fi; return 1 ;;\n',
            '        2) return 2 ;;\n',
            path=PUB)
        fired = os.path.join(self.home, "fired")
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, READER, mutant), True)):
                    if os.path.isdir(self.store):
                        os.chmod(self.store, 0o700)
                    self._wipe()
                    if os.path.exists(fired):
                        os.unlink(fired)
                    body = (self._mkstore()
                            # A SEEDED $RANDOM makes the three transient names a fixed, distinct sequence in
                            # both shells (row 116 does the same); unseeded, a ~1e-4 repeat would spend an
                            # attempt on the presence test without firing the trap and skew the count.
                            + 'RANDOM=2617\n'
                            + '[ -n "${BASH_VERSION:-}" ] && set -T\n'
                            + 'trap \'if [ -n "${_wt_p:-}" ] && [ "$_wt_p" = "${_UNLEASHED_TRANSIENT:-}" ] '
                              '&& [ "$_wt_p" != "${_t155_last:-}" ] '
                              '&& [ ! -e "$_wt_p" ] && [ ! -L "$_wt_p" ]; then '
                              f'_t155_last="$_wt_p"; /bin/chmod 500 "{self.store}"; '
                              f'printf "%s\\n" "$_wt_p" >> "{fired}"; fi\' DEBUG\n'
                            + f'_unleashed_publish "{self.store}" "{self.target}"\n'
                            + 'trap - DEBUG\n'
                              'printf "STATE=%s" "$_UNLEASHED_POINTER_STATE"')
                    try:
                        rc, out, err = run_shell(shell, body, sources=srcs)
                        names = []
                        if os.path.exists(fired):
                            with open(fired, encoding="utf-8") as fh:
                                names = [l for l in fh.read().splitlines() if l]
                        self.assertTrue(names, f"{shell}: the trap never fired inside the write")
                        self.assertEqual(0o500, os.stat(self.store).st_mode & 0o777,
                                         f"{shell}: the store was not made unwritable")
                        self.assertIn("STATE=failed", out, f"{shell}: not `failed`: {out!r} {err!r}")
                        diags = self._diags(err)
                        self.assertEqual(1, len(diags), f"{shell}: not exactly one diagnostic: {err!r}")
                        pubs = [f for f in os.listdir(self.store) if f.startswith(".pub.")]
                        self.assertEqual([], pubs, f"{shell}: a transient exists under a refused create: {pubs}")
                        if not is_mutant:
                            self.assertIn("could not be written at 0600", diags[0],
                                          f"{shell}: a refusal with the name absent was not E6: {diags[0]!r}")
                            self.assertEqual(1, len(names),
                                             f"{shell}: E6 did not stop at the first attempt: {names}")
                        else:
                            self.assertIn("no unique transient name", diags[0],
                                          f"{shell}: the CONTROL did not fail — the refusal was not spent as E5: "
                                          f"{diags[0]!r}")
                            self.assertEqual(3, len(names),
                                             f"{shell}: the CONTROL did not consume three attempts: {names}")
                    finally:
                        if os.path.isdir(self.store):
                            os.chmod(self.store, 0o700)
        finally:
            os.unlink(mutant)
            if os.path.isdir(self.store):
                os.chmod(self.store, 0o700)

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
        # RE-PINNED (pass 23): the assignment moved into a `case` arm when the encoder learned to
        # detect a READONLY `LC_ALL` instead of assigning to it — bash dies outright on that
        # assignment. Same rule, same mutation, new site; the oracle below is unchanged.
        mutant = with_mutation('        *) LC_ALL=C ;;\n', '        *) : ;;\n', path=STORE)
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
            'if [ -L "$_pb_entry" ] || { [ -e "$_pb_entry" ] && [ ! -f "$_pb_entry" ]; }; then',
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


# ==================================================================================================
# Pass 7 — rows 156-162 (PR #67, codex pass 7)
# ==================================================================================================
# The seven rows codex's seventh pass added: three inheritable-flag guards (156-158), the errexit
# path through the publish (159), the entry read through a SECOND open of its pathname (160), the
# log stamp (161) and zsh's special parameters in the family writers (162). Every row was RUN
# against the shipped build and its mutant in both shells before assembly; the run below is the gate.

import json
import os
import re
import shutil
import subprocess
import stat as statmod
import unittest


#: The five resolver copies FAM-1 names, and the four machinery files each of them loads.
FAMILY_P7 = ("paths.sh", "marker.sh", "log.sh", "context.sh", "agent-env-bridge.sh")
MACHINERY_P7 = ("plugin-state-auth.sh", "plugin-state-store.sh",
                "plugin-state-reader.sh", "plugin-state-publisher.sh")
#: The SessionStart hook (row 165) — a bash script that sources `lib/` relative to ITS OWN directory.
SESSIONSTART_P7 = os.path.join(os.path.dirname(LIBDIR), "sessionstart-restore.sh")


@unittest.skipUnless(DARWIN, "every row here drives the Darwin store/ACL arm, /dev/fd or zsh 5.9 semantics")
class RowsPass7(unittest.TestCase):
    """Mutant-table rows 156-178 (156-173, the pass-14 codex sweep's 174-177, then pass 15's 178)."""

    #: The store-level outcome, N6-6's tuple.
    OUTP = 'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"'

    def setUp(self):
        # A scratch HOME under ~/.claude (§7 step 3f(i)) so the chain authenticates and no test
        # reads or writes the developer's real store; every fixture re-points $HOME here.
        self.home = scratch_home("rp7.2617.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.target = os.path.join(self.home, "target")
        os.makedirs(self.target)
        os.chmod(self.target, 0o700)

    def tearDown(self):
        os.chmod(self.home, 0o700)
        for dirpath, dirnames, _ in os.walk(self.home):
            for d in dirnames:
                try:
                    os.chmod(os.path.join(dirpath, d), 0o700)
                except OSError:
                    pass
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

    @staticmethod
    def _diags(err):
        """Diagnostic lines — the one-diagnostic clauses count these, never raw stderr bytes."""
        return [l for l in err.splitlines() if l.startswith("unleashed-mail:")]

    def _shadow(self, name, files):
        """A plugin root holding ONLY `files` under scripts/lib — {basename: source path}.

        The family files locate paths.sh and the machinery from their OWN directory, so a mutant
        copy must sit BESIDE byte-identical copies of everything else it loads (row 46 does the
        same); a mutant left in the temp dir with_mutation returns would degrade to the D′ envelope
        for the wrong reason — the machinery it could not find — and the row would not be testing
        its mutation.
        """
        root = os.path.join(self.home, name)
        sl = os.path.join(root, "scripts", "lib")
        os.makedirs(sl)
        for base, src in files.items():
            shutil.copy(src, os.path.join(sl, base))
        return root

    @staticmethod
    def _slice(path, head, tail, after_head=False):
        """The CURRENT text of `path` from the unique `head` through the first `tail` after it.

        Rows whose mutation replaces a whole block build the OLD text this way rather than from a
        literal copy, so a comment or capture rewrite inside the block cannot strand the row on a
        pattern that no longer matches (row 153 drifted twice on PR #67). The head must be unique
        and so must the resulting slice — with_mutation asserts the latter again. `after_head`
        starts the slice AFTER the head line, keeping that line in both builds.
        """
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        assert text.count(head) == 1, f"head anchor not unique in {path}: {head!r}"
        start = text.index(head) + (len(head) if after_head else 0)
        assert tail in text[start:], f"tail anchor not found after the head in {path}: {tail!r}"
        end = text.index(tail, start) + len(tail)
        old = text[start:end]
        assert text.count(old) == 1, f"sliced block not unique in {path}"
        return old

    #: paths.sh's definition block is a BARE `{ … }` group (PR #67 pass 12) — every guard tried on it
    #: trusted something an environment can carry. The head of the paragraph that says so, the
    #: group's opening line, and its closing line before the eager call: rows 158/167/170 WRAP the
    #: block in the guard each row names, so the mutation ADDS a guard where the specification has none.
    DEFS_HEAD = "# THE DEFINITIONS BELOW ARE UNCONDITIONAL"
    DEFS_OPEN = "\n{\n"
    DEFS_CLOSE = "}\n# EAGER — at source time"

    def _guarded_paths(self, guard):
        """A copy of paths.sh whose definition block is wrapped in `guard` … `fi`.

        Two substitutions on the same copy, both anchored on the CURRENT file: the opening `{` —
        sliced from the paragraph head through the brace, so the paragraph's wording is asserted
        present but not repeated here — becomes the guard line, and the closing `}` before the
        eager `unleashed_resolve_base` call becomes `fi`. The eager call stays OUTSIDE the guarded
        region, exactly as the shipped call stays outside the group, so under a satisfied guard it
        runs whatever `unleashed_resolve_base` the shell already had — nothing (rows 158/167) or an
        inherited one (row 170). Both shells must parse the result. The caller unlinks it.
        """
        opening = self._slice(PATHS_C4, self.DEFS_HEAD, self.DEFS_OPEN)
        self.assertTrue(opening.endswith("\n{\n"), opening[-60:])
        self.assertTrue(guard.startswith("if ") and guard.endswith("; then\n"), guard)
        first = with_mutation(opening, opening[:-len("{\n")] + guard, path=PATHS_C4)
        try:
            mutant = with_mutation(self.DEFS_CLOSE, "fi\n# EAGER — at source time", path=first)
        finally:
            os.unlink(first)
        for shell in SHELLS:
            p = subprocess.run([shell, "-n", mutant], capture_output=True, text=True)
            self.assertEqual(0, p.returncode, f"{shell}: the guarded mutant does not parse: {p.stderr!r}")
        return mutant

    @staticmethod
    def _run_with_timeout(shell, body, srcs, timeout=8):
        """run_shell with a hang oracle: ('TIMEOUT', '', '') when the shell does not return."""
        src = "".join(f'. "{s}"\n' for s in srcs) + body
        try:
            p = subprocess.run([shell, "-c", src], capture_output=True, text=True, timeout=timeout)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            return "TIMEOUT", "", ""

    # ── row 156 ───────────────────────────────────────────────────────────────────────────────

    def test_row_156_resolution_is_keyed_on_process_identity_not_an_inherited_flag(self):
        """Row 156: `_UNLEASHED_BASE_OK=1` inherited by a CHILD shell that sources a resolver copy with the variable unset and no store — the specification resolves afresh (`_UNLEASHED_BASE_PID` ≠ `$$`): OK=0, the sentinel, `marker_dir` beneath the sentinel, ONE diagnostic; the flag-keyed mutant skips resolution, `_UNLEASHED_BASE_RESOLVED` stays UNSET and `marker_dir` prints `/.state` — the ROOT path. All five resolver copies, both shells."""
        # Each copy's guard is exercised only where that copy is the resolver in force: paths.sh
        # sourced directly; the four fallback copies sourced from a shadow root WITHOUT paths.sh
        # (N1's "paths.sh absent" cell) so their own three-step resolution runs. With paths.sh
        # beside them their guard is unreachable — paths.sh resolves first and sets the pid — and
        # a mutant there could not fail. Measured, both shells, all five: spec `0|<sentinel>`
        # (+ `<sentinel>/.state` for marker.sh) with one diagnostic; mutant `1|UNSET` (+ `/.state`)
        # and no diagnostic at all.
        # The CURRENT guards (pid + the marker function, PR #67 pass 11) are the anchors — the whole
        # guard clause, without the trailing comment on the family lines, which differs per file.
        old_paths = ('        [ "${_UNLEASHED_BASE_PID:-}" = "$$" ] && command -v _unleashed_resolved_in_process '
                     '>/dev/null 2>&1 && return 0\n')
        new_paths = '        [ -n "${_UNLEASHED_BASE_OK:-}" ] && return 0\n'
        old_fam = ('if [ "${_UNLEASHED_BASE_PID:-}" != "$$" ] || ! command -v _unleashed_resolved_in_process '
                   '>/dev/null 2>&1; then')
        new_fam = 'if [ -z "${_UNLEASHED_BASE_OK:-}" ]; then'
        machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
        for fam in FAMILY_P7:
            is_paths = fam == "paths.sh"
            mutant = with_mutation(old_paths if is_paths else old_fam,
                                   new_paths if is_paths else new_fam,
                                   path=os.path.join(LIBDIR, fam))
            try:
                spec_root = self._shadow(f"spec-{fam}", dict(machinery, **{fam: os.path.join(LIBDIR, fam)}))
                mut_root = self._shadow(f"mut-{fam}", dict(machinery, **{fam: mutant}))
                for shell in SHELLS:
                    for root, is_mutant in ((spec_root, False), (mut_root, True)):
                        self._wipe()                                # no store anywhere under HOME
                        f = os.path.join(root, "scripts", "lib", fam)
                        src = (f'. "{f}" "" "{root}"' if fam == "agent-env-bridge.sh" else f'. "{f}"')
                        body = ('unset CLAUDE_PLUGIN_DATA\n' + src + '\n'
                                'printf "%s|%s" "${_UNLEASHED_BASE_OK-UNSET}" '
                                '"${_UNLEASHED_BASE_RESOLVED-UNSET}"'
                                + ('; printf "|%s" "$(marker_dir)"' if fam == "marker.sh" else ""))
                        rc, out, err = run_shell(shell, body, sources=(),
                                                 env={"HOME": self.home, "_UNLEASHED_BASE_OK": "1"})
                        diags = self._diags(err)
                        if not is_mutant:
                            want = f"0|{SENTINEL}" + (f"|{SENTINEL}/.state" if fam == "marker.sh" else "")
                            self.assertEqual(want, out, f"{shell} {fam}: {err!r}")
                            self.assertEqual(1, len(diags), f"{shell} {fam}: not one diagnostic: {err!r}")
                        else:
                            want = "1|UNSET" + ("|/.state" if fam == "marker.sh" else "")
                            self.assertEqual(want, out,
                                             f"{shell} {fam}: the CONTROL did not fail — the inherited "
                                             f"flag did not skip resolution: {out!r} {err!r}")
                            self.assertEqual([], diags, f"{shell} {fam}: a skipped resolution diagnosed")
                        self.assertFalse(os.path.exists(self.store), f"{shell} {fam}: a store appeared")
            finally:
                os.unlink(mutant)

    # ── row 157 ───────────────────────────────────────────────────────────────────────────────

    def test_row_157_machinery_loaded_means_the_functions_exist_not_a_flag(self):
        """Row 157: `_UNLEASHED_STATE_LOADED=1 _UNLEASHED_STATE_RC=0` inherited by a child that sources paths.sh with the variable unset — the specification loads the four libraries (RE-SOURCED from the files beside the resolver whenever they are readable, and keyed on `command -v` of their entry functions only where they are not — pass 14) and resolves (OK=0, the sentinel, one diagnostic, nothing `command not found`); the flag-keyed mutant reports the machinery present, the reader branch calls an undefined `_unleashed_read_store` — `command not found` on stderr, every protocol variable UNSET, and a `set -u` consumer aborts before its next statement. Both shells."""
        # THE MUTATION is the flag short-circuit restored at the TOP of the loader — before the readable
        # files are sourced — which is where the pass-7 defect lived. (Until pass 14 it replaced the
        # `command -v` presence check; that check now runs only when the files are unreadable, so a flag
        # planted there is unreachable in this fixture and the control could not fail — measured.)
        mutant = with_mutation(
            '        _usm_d="$_UNLEASHED_LIB_DIR"; _usm_readable=1\n',
            '        [ -n "${_UNLEASHED_STATE_LOADED:-}" ] && return "${_UNLEASHED_STATE_RC:-0}"\n'
            '        _usm_d="$_UNLEASHED_LIB_DIR"; _usm_readable=1\n',
            path=PATHS_C4)
        env = {"HOME": self.home, "_UNLEASHED_STATE_LOADED": "1", "_UNLEASHED_STATE_RC": "0"}
        try:
            machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
            spec_root = self._shadow("spec157", dict(machinery, **{"paths.sh": PATHS_C4}))
            mut_root = self._shadow("mut157", dict(machinery, **{"paths.sh": mutant}))
            for shell in SHELLS:
                for root, is_mutant in ((spec_root, False), (mut_root, True)):
                    self._wipe()
                    paths = os.path.join(root, "scripts", "lib", "paths.sh")
                    body = ('unset CLAUDE_PLUGIN_DATA\n'
                            f'. "{paths}"\n'
                            'printf "%s|%s|%s" "${_UNLEASHED_BASE_OK-UNSET}" '
                            '"${_UNLEASHED_BASE_RESOLVED-UNSET}" "${_UNLEASHED_BASE_SOURCE-UNSET}"')
                    rc, out, err = run_shell(shell, body, sources=(), env=env)
                    # The `set -u` consumer: its next statement must be reached.
                    body_u = ('set -u\nunset CLAUDE_PLUGIN_DATA\n'
                              f'. "{paths}"\n'
                              'printf "%s" "$_UNLEASHED_BASE_OK"; printf " END"')
                    rc_u, out_u, err_u = run_shell(shell, body_u, sources=(), env=env)
                    if not is_mutant:
                        self.assertEqual(f"0|{SENTINEL}|unresolved", out, f"{shell}: {err!r}")
                        self.assertEqual(1, len(self._diags(err)), f"{shell}: not one diagnostic: {err!r}")
                        self.assertNotIn("command not found", err, f"{shell}: {err!r}")
                        self.assertEqual((0, "0 END"), (rc_u, out_u), f"{shell}: set -u consumer: {err_u!r}")
                    else:
                        self.assertEqual("UNSET|UNSET|UNSET", out,
                                         f"{shell}: the CONTROL did not fail — the inherited flag did "
                                         f"not report the machinery loaded: {out!r} {err!r}")
                        self.assertIn("command not found", err, f"{shell}: {err!r}")
                        self.assertEqual([], self._diags(err), f"{shell}: {err!r}")
                        self.assertNotEqual(0, rc_u, f"{shell}: the set -u consumer did not abort: {out_u!r}")
                        self.assertNotIn("END", out_u, f"{shell}: the set -u consumer reached its next statement")
        finally:
            os.unlink(mutant)

    # ── row 158 ───────────────────────────────────────────────────────────────────────────────

    def test_row_158_paths_sh_body_is_guarded_on_a_function_not_an_inheritable_flag(self):
        """Row 158: `_UNLEASHED_PATHS_SH_LOADED=1` inherited by a child that sources paths.sh — the specification (whose definition block is UNCONDITIONAL) defines its functions and resolves (`unleashed_plugin_base` prints the sentinel here); under the mutation — a flag guard WRAPPED around the definition block — the file defines NOTHING and `unleashed_plugin_base` is `command not found`. Both shells. (Reshaped in pass 12: the mutation ADDS a guard where the specification has none.)"""
        # The mutant wraps the bare `{ … }` definition group in `if [ -z "$FLAG" ]; then … fi`
        # (`_guarded_paths`, anchored on the CURRENT file's paragraph head, brace and closing line).
        # The eager `unleashed_resolve_base` call sits OUTSIDE the group in both builds, so under
        # the mutant it is the first `command not found` (at source time) and the primitive the
        # second — measured, both shells: spec `<sentinel>|0|0` + one diagnostic; mutant `|127|UNSET`,
        # two `command not found`, no diagnostic.
        mutant = self._guarded_paths('if [ -z "${_UNLEASHED_PATHS_SH_LOADED:-}" ]; then\n')
        env = {"HOME": self.home, "_UNLEASHED_PATHS_SH_LOADED": "1"}
        try:
            machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
            spec_root = self._shadow("spec158", dict(machinery, **{"paths.sh": PATHS_C4}))
            mut_root = self._shadow("mut158", dict(machinery, **{"paths.sh": mutant}))
            for shell in SHELLS:
                for root, is_mutant in ((spec_root, False), (mut_root, True)):
                    self._wipe()
                    paths = os.path.join(root, "scripts", "lib", "paths.sh")
                    body = ('unset CLAUDE_PLUGIN_DATA\n'
                            f'. "{paths}"\n'
                            'unleashed_plugin_base; printf "|%s|%s" "$?" "${_UNLEASHED_BASE_OK-UNSET}"')
                    rc, out, err = run_shell(shell, body, sources=(), env=env)
                    if not is_mutant:
                        self.assertEqual(f"{SENTINEL}|0|0", out, f"{shell}: {err!r}")
                        self.assertEqual(1, len(self._diags(err)), f"{shell}: not one diagnostic: {err!r}")
                        self.assertNotIn("command not found", err, f"{shell}: {err!r}")
                    else:
                        self.assertEqual("|127|UNSET", out,
                                         f"{shell}: the CONTROL did not fail — the inherited flag did "
                                         f"not suppress the file's body: {out!r} {err!r}")
                        self.assertIn("command not found", err, f"{shell}: {err!r}")
                        self.assertEqual([], self._diags(err), f"{shell}: {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 159 ───────────────────────────────────────────────────────────────────────────────

    def test_row_159_the_transient_write_status_is_captured_errexit_safe(self):
        """Row 159: the family sourced under `set -eu` with the transient's WRITE refused (RLIMIT_FSIZE 0: the exclusive create succeeds, the value write fails EFBIG — E6): the specification reports `failed` with its one diagnostic, cleans the transient up, and the sourcing shell REACHES its next statement; under the bare `cmd; _pb_wrc=$?` capture the shell EXITS non-zero at the call — before the diagnostic, before the cleanup, before `END`. Both shells."""
        # The plan's reproduction made the store unwritable after E4; the create-refused shape is
        # rows 154/155's fixture and needs a DEBUG trap. RLIMIT_FSIZE(0) reaches the same capture
        # through E6 without one — row 138's fixture — and the create-and-write subshell already
        # ignores SIGXFSZ so the limit surfaces as EFBIG (printf rc 1) and not as a signal death.
        # Measured, both shells: spec `STATE=failed OK=1 … END`, rc 0, one diagnostic naming the
        # 0600 write, no transient left; mutant rc 1 (the function's own return, the status the
        # bare call hands errexit), EMPTY stdout, no diagnostic, and the transient orphaned because
        # the E6 cleanup after the capture never ran. Nothing in the limited shell writes a FILE:
        # its streams are run_shell's pipes and RLIMIT_FSIZE governs regular files only.
        mutant = with_mutation(
            '            _unleashed_write_transient "$_UNLEASHED_TRANSIENT" "$_pb_value" && _pb_wrc=0 || _pb_wrc=$?\n',
            '            _unleashed_write_transient "$_UNLEASHED_TRANSIENT" "$_pb_value"; _pb_wrc=$?\n',
            path=PUB)
        # THE PUBLISHER UNDER TEST IS THE ONE THE RESOLVER LOADS: since PR #67 pass 14 paths.sh re-sources
        # the four machinery files beside it whenever they are readable, so a mutant publisher sourced
        # into the fixture BEFORE `. paths.sh` was replaced by the shipped one and the control could not
        # fail (measured). Each build is a shadow root — the machinery, with its own publisher, beside
        # paths.sh — and the fixture sources paths.sh alone.
        machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
        spec_root = self._shadow("spec159", dict(machinery, **{"paths.sh": PATHS_C4}))
        mut_root = self._shadow("mut159", dict(machinery, **{"plugin-state-publisher.sh": mutant, "paths.sh": PATHS_C4}))
        try:
            for shell in SHELLS:
                for root, is_mutant in ((spec_root, False), (mut_root, True)):
                    self._wipe()
                    body = ('set -eu\n'
                            f'export HOME="{self.home}"\n'
                            f'export CLAUDE_PLUGIN_DATA="{self.target}"\n'
                            'trap "" XFSZ\nulimit -f 0\n'
                            f'. "{os.path.join(root, "scripts", "lib", "paths.sh")}"\n'
                            + 'printf "STATE=%s OK=%s SRC=%s" "$_UNLEASHED_POINTER_STATE" '
                              '"$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE"\n'
                              'printf " END"')
                    rc, out, err = run_shell(shell, body, sources=())
                    diags = self._diags(err)
                    pubs = ([f for f in os.listdir(self.store) if f.startswith(".pub.")]
                            if os.path.isdir(self.store) else [])
                    bases = ([f for f in os.listdir(self.store) if f.startswith("base.")]
                             if os.path.isdir(self.store) else [])
                    self.assertEqual([], bases, f"{shell}: E6 published an entry: {bases}")
                    if not is_mutant:
                        self.assertEqual(0, rc, f"{shell}: the sourcing shell did not survive: {err!r}")
                        self.assertEqual("STATE=failed OK=1 SRC=host-env END", out, f"{shell}: {err!r}")
                        self.assertEqual(1, len(diags), f"{shell}: not one diagnostic: {err!r}")
                        self.assertIn("could not be written at 0600", diags[0], f"{shell}: not E6: {diags[0]!r}")
                        self.assertEqual([], pubs, f"{shell}: the E6 cleanup left a transient: {pubs}")
                    else:
                        self.assertNotEqual(0, rc, f"{shell}: the CONTROL did not fail — the bare "
                                                   f"capture did not abort the errexit sourcer: {out!r}")
                        self.assertEqual("", out, f"{shell}: the shell reached a statement after the bare call")
                        self.assertEqual([], diags, f"{shell}: the diagnostic was reached: {err!r}")
                        self.assertEqual(1, len(pubs), f"{shell}: the aborted publish did not orphan its transient: {pubs}")
        finally:
            os.unlink(mutant)

    # ── row 160 ───────────────────────────────────────────────────────────────────────────────

    def test_row_160_the_entry_is_read_through_the_descriptor_ent_2b_validated(self):
        """Row 160: a DEBUG trap substitutes the entry the instant ENT-1 has validated it and before it is opened — a large regular file, a symlink to a foreign file, a vanished entry, and in zsh a FIFO: the specification refuses each as a failing entry (`stale`, ONE sanitised diagnostic naming no path) and returns promptly, its read bound to the descriptor it validated; under the second-open `read < "$p"` mutant the large file is READ — a large file whose FIRST LINE is a valid target RESOLVES (`1 pointer none`) although its size exceeds anything a valid entry can be, the row's plain 200 000-byte file reaches the byte-count clause with all 200 000 bytes, the foreign file's first line is consumed — and in zsh the FIFO BLOCKS the resolver. bash's FIFO case is P-5's stated residual and is not run. Both shells for the other cases."""
        # THE INTERLEAVING IS DETERMINISTIC: the trap is keyed on `_ae_bound` being set — the
        # assignment that immediately precedes the ENT-2b open in BOTH builds (the mutation keeps
        # that line and replaces the arm after it) — and on the entry still being the small regular
        # file ENT-1 validated, so it fires exactly once, after P-2's pathname stat and before any
        # open; `set -T` in bash so the trap reaches into functions (rows 153-155 do the same).
        # WHY THE DISCRIMINATING LARGE FILE CARRIES A VALID FIRST LINE: with the row's plain shape
        # both builds end `stale` — the specification refuses on the descriptor's size, the mutant
        # reads 200 000 bytes and fails clause (2) — so the RESULT cannot fail; the read itself is
        # still observed (`${#_ae_line}` is 0 in the specification, 200 000 in the mutant). With a
        # valid target as line 1 the mutant's second-open read passes clause (2) — `_U_SIZE` is
        # the ORIGINAL entry's size, stat'ed on the pathname — and everything after it, and the
        # store RESOLVES to a file that was never what ENT-1 validated. Measured, both shells.
        # The slice starts after `_ae_bound=` (the trap's key, kept in both builds) and so takes the
        # `_ae_ino=` capture (PR #67 pass 11) along with the two arms: the mutant reads through a
        # second open and validates NOTHING on a descriptor, so it has no inode to bind to either.
        # It runs THROUGH the `_u_entry_path_still_bare` call that closes the bash arm (PR #67 pass 15,
        # row 178): that call belongs to the read, and a mutant that read through a second open and
        # then re-tested the pathname would be a build nobody proposed.
        old = self._slice(READER,
                          '    _ae_bound=$(( ${#_ae_name} + 1 ))\n',
                          '        [ "$_ae_ok" = 1 ] || return 1                                                      # (1)\n'
                          '        _u_entry_path_still_bare "$_ae_p" || return 1\n'
                          '    fi\n',
                          after_head=True)
        self.assertTrue(old.startswith('    _ae_ino="$_U_INO"'), old[:80])
        self.assertIn('    if [ -n "${ZSH_VERSION:-}" ]; then\n        zmodload zsh/system', old)
        self.assertIn("sysopen", old)
        self.assertIn('9<"$_ae_p"', old)
        self.assertEqual(2, old.count("_u_entry_path_still_bare"), "both arms' pathname re-tests must be in the slice")
        self.assertNotIn("_ae_bytes", old, "the slice ran past the arms into clause (2)")
        mutant = with_mutation(old, '    { IFS= read -r _ae_line < "$_ae_p"; } 2>/dev/null || return 1\n',
                               path=READER)
        big = os.path.join(self.home, "big")
        with open("/etc/hosts", "rb") as fh:
            hosts_first = len(fh.readline().rstrip(b"\n"))
        substitutes = (
            ("large",       f'/bin/mv -f "{big}" "$_ae_p"'),
            ("large-plain", f'/bin/mv -f "{big}" "$_ae_p"'),
            ("symlink",     '/bin/rm -f "$_ae_p"; /bin/ln -s /etc/hosts "$_ae_p"'),
            ("vanished",    '/bin/rm -f "$_ae_p"'),
            ("fifo",        '/bin/rm -f "$_ae_p"; /usr/bin/mkfifo "$_ae_p"'),
        )

        def unblock_fifo():
            # A mutant killed at the timeout may leave a reader parked in open(2) on the FIFO;
            # opening the write end releases it. ENXIO when nothing is parked there.
            if os.path.isdir(self.store):
                for f in os.listdir(self.store):
                    p = os.path.join(self.store, f)
                    if statmod.S_ISFIFO(os.lstat(p).st_mode):
                        try:
                            fd = os.open(p, os.O_WRONLY | os.O_NONBLOCK)
                            os.close(fd)
                        except OSError:
                            pass

        try:
            for shell in SHELLS:
                bash = shell.endswith("bash")
                for case, sub in substitutes:
                    if case == "fifo" and bash:
                        continue                # P-5's residual: the shipped bash arm blocks too
                    for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                            ((AUTH, STORE, mutant, PUB), True)):
                        self._wipe()
                        if case.startswith("large"):
                            with open(big, "w", encoding="utf-8") as fh:
                                if case == "large":
                                    fh.write(self.target + "\n")
                                fh.write("a" * 200000 + "\n")
                            os.chmod(big, 0o600)
                        body = (self._mkstore() + self._entry()
                                + '[ -n "${BASH_VERSION:-}" ] && set -T\n'
                                + 'trap \'if [ -n "${_ae_bound:-}" ] && [ -z "${_t160_done:-}" ] '
                                  '&& [ -f "${_ae_p:-}" ] && [ ! -L "$_ae_p" ] '
                                  '&& [ "$(/usr/bin/stat -f %z "$_ae_p")" -lt 100 ]; then '
                                  '_t160_done=1; ' + sub + '; fi\' DEBUG\n'
                                + f'_unleashed_read_store "{self.store}"\n'
                                + 'trap - DEBUG\n'
                                + 'printf "%s %s %s %s|%s|%s" "$_UNLEASHED_BASE_OK" '
                                  '"$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE" '
                                  '"$_UNLEASHED_BASE_RESOLVED" "${#_ae_line}" "${_t160_done:-0}"')
                        try:
                            rc, out, err = self._run_with_timeout(shell, body, srcs)
                        finally:
                            unblock_fifo()
                        tag = f"{shell} {case} {'mutant' if is_mutant else 'shipped'}"
                        if is_mutant and case == "fifo":
                            self.assertEqual("TIMEOUT", rc,
                                             f"{tag}: the CONTROL did not block — the second open "
                                             f"of the FIFO returned: {out!r} {err!r}")
                            continue
                        self.assertNotEqual("TIMEOUT", rc, f"{tag}: the resolver hung")
                        stale = f"0 unresolved stale {SENTINEL}"
                        if not is_mutant:
                            self.assertEqual(f"{stale}|0|1", out,
                                             f"{tag}: not refused as a failing entry, or the trap did "
                                             f"not fire, or the substitute was READ: {out!r} {err!r}")
                            lines = err.splitlines()
                            self.assertEqual(1, len(lines), f"{tag}: not exactly one stderr line: {err!r}")
                            self.assertTrue(lines[0].startswith("unleashed-mail:"), f"{tag}: {err!r}")
                            self.assertNotIn(self.store, err, f"{tag}: the store path reached stderr")
                            self.assertNotIn(self.target, err, f"{tag}: the target path reached stderr")
                        elif case == "large":
                            self.assertEqual(f"1 pointer none {self.target}|{len(self.target)}|1", out,
                                             f"{tag}: the CONTROL did not fail — the substituted large "
                                             f"file was not read through the second open: {out!r} {err!r}")
                            self.assertEqual("", err, f"{tag}: {err!r}")
                        elif case == "large-plain":
                            self.assertEqual(f"{stale}|200000|1", out,
                                             f"{tag}: the CONTROL did not READ the 200 000 bytes: {out!r}")
                        elif case == "symlink":
                            self.assertEqual(f"{stale}|{hosts_first}|1", out,
                                             f"{tag}: the CONTROL did not read the foreign file's first line: {out!r}")
                        else:                   # vanished: both builds refuse — not the discriminating case
                            self.assertEqual(f"{stale}|0|1", out, f"{tag}: {out!r} {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 161 ───────────────────────────────────────────────────────────────────────────────

    def test_row_161_every_log_record_carries_base_resolution(self):
        """Row 161: `log_append` fed the four producers' record shapes plus `{}` and `{  }` under `host-env` and under `pointer` (variable unset, one authenticating entry): every persisted line parses as JSON and carries `"base_resolution"` naming the resolution that ran; a pre-stamped line and a non-object line are written unchanged. With the writer's stamp removed the producer shapes persist WITHOUT the field, so a `pointer` record is indistinguishable from a `host-env` one. Both shells."""
        # The four shapes are the producers' printf formats verbatim (stop-failure-log.sh,
        # permission-denied-log.sh, build-failure-log.sh, swift-build-verify.sh). The stamp is
        # exactly the `case "$line" in … esac` block in log_append and the mutation deletes it.
        mutant = with_mutation(
            '    case "$line" in\n'
            '        *\'"base_resolution"\'*) : ;;                       # the producer stamped it itself\n'
            '        \\{*\\})\n'
            '            body="${line#\\{}"; body="${body%\\}}"\n'
            '            case "$body" in\n'
            '                *[!\\ ]*) line="{${body},\\"base_resolution\\":\\"${_UNLEASHED_BASE_SOURCE:-unresolved}\\"}" ;;\n'
            '                *)       line="{\\"base_resolution\\":\\"${_UNLEASHED_BASE_SOURCE:-unresolved}\\"}" ;;\n'
            '            esac ;;\n'
            '    esac\n',
            '', path=LOG)
        shapes = (
            '"$(printf \'{"ts":"%s","type":"%s"}\' "$(log_ts)" "unknown")"',
            '"$(printf \'{"ts":"%s","tool":"%s","reason":%s}\' "$(log_ts)" "Bash" \'"denied"\')"',
            '"$(printf \'{"ts":"%s","kind":"build","class":"%s","failed":true}\' "$(log_ts)" "xcodebuild-build")"',
            '"$(printf \'{"ts":"%s","kind":"build","class":"%s","failed":false}\' "$(log_ts)" "swift-build")"',
            "'{}'",
            "'{  }'",
        )
        prestamped = '{"ts":"pre","base_resolution":"pre-stamped"}'
        nonobject = "[1,2]"
        try:
            for shell in SHELLS:
                for log, is_mutant in ((LOG, False), (mutant, True)):
                    self._wipe()
                    shutil.rmtree(os.path.join(self.target, "logs"), ignore_errors=True)
                    # host-env FIRST: its publish is what gives the pointer run its one entry.
                    for mode, want_tuple in (("host-env", "1 host-env created"), ("pointer", "1 pointer none")):
                        setenv = (f'export HOME="{self.home}"\n'
                                  + (f'export CLAUDE_PLUGIN_DATA="{self.target}"\n' if mode == "host-env"
                                     else 'unset CLAUDE_PLUGIN_DATA\n'))
                        calls = "".join(f'log_append {mode}.jsonl {s}\n' for s in shapes)
                        calls += f"log_append {mode}.jsonl '{prestamped}'\nlog_append {mode}.jsonl '{nonobject}'\n"
                        body = (setenv
                                + "".join(f'. "{s}"\n' for s in (AUTH, STORE, READER, PUB, PATHS_C4, log))
                                + calls + self.OUTP)
                        rc, out, err = run_shell(shell, body, sources=())
                        tag = f"{shell} {mode} {'mutant' if is_mutant else 'shipped'}"
                        self.assertEqual(want_tuple, out, f"{tag}: {err!r}")
                        self.assertEqual("", err, f"{tag}: {err!r}")
                        p = os.path.join(self.target, "logs", f"{mode}.jsonl")
                        self.assertTrue(os.path.exists(p), f"{tag}: nothing persisted")
                        with open(p, encoding="utf-8") as fh:
                            lines = fh.read().splitlines()
                        self.assertEqual(len(shapes) + 2, len(lines), f"{tag}: {lines}")
                        for line in lines[:len(shapes)]:
                            d = json.loads(line)          # every producer line parses, both builds
                            self.assertIsInstance(d, dict, f"{tag}: {line!r}")
                            if not is_mutant:
                                self.assertEqual(mode, d.get("base_resolution"),
                                                 f"{tag}: unstamped or mis-stamped: {line!r}")
                            else:
                                self.assertNotIn("base_resolution", d,
                                                 f"{tag}: the CONTROL did not fail — still stamped: {line!r}")
                        self.assertEqual(prestamped, lines[len(shapes)], f"{tag}: a pre-stamped line was rewritten")
                        self.assertEqual(nonobject, lines[len(shapes) + 1], f"{tag}: a non-object line was rewritten")
        finally:
            os.unlink(mutant)

    # ── row 162 ───────────────────────────────────────────────────────────────────────────────

    def test_row_162_family_writers_avoid_zsh_special_parameters(self):
        """Row 162: under ZSH with the variable set, `marker_write lint fail; marker_status lint` prints `fail`, `log_append` persists its line, `context_review_round_bind` prints a round that `context_review_round_lookup` reads back, and PATH is intact afterwards (`command -v ls`); with the old `status`/`path` names restored in a writer, zsh reports `read-only variable: status` and the sourcing script STOPS at `marker_write` with nothing written, `local path` empties PATH inside `log_append` so `mkdir` is not found and its line is never persisted, and inside `context_review_round_bind` so its binding is never published and the lookup reads nothing. bash is unaffected by every one of these mutations — its half asserts the four builds behave identically, which is why every writer test until now passed."""
        # One mutation per writer, each the CONSISTENT restore of the pre-fix names over that
        # function's whole text (sliced from the current file): a `local` line mutated alone would
        # leave `_mw_status` dangling and break BASH too, and the row's whole point is a defect
        # bash cannot see. Measured: bash prints `ms=[fail] rb=[1] rl=[1] ls=[/bin/ls]` and
        # persists all three under all four builds; zsh — spec identical to bash; marker mutant:
        # `marker_write:2: read-only variable: status`, EMPTY stdout (zsh abandons the script,
        # rc 0), no marker; log mutant: the tuple intact, no log file; context mutant: `rl=[]`,
        # only a `.tmp.<pid>` under .state (its `mv` was not found either).
        old_mw = self._slice(MARKER, "marker_write() {\n", "\n}\n")
        self.assertIn("_mw_status", old_mw); self.assertIn("_mw_path", old_mw)
        m_marker = with_mutation(old_mw, old_mw.replace("_mw_status", "status").replace("_mw_path", "path"),
                                 path=MARKER)
        old_la = self._slice(LOG, "log_append() {\n", "\n}\n")
        self.assertIn("_la_path", old_la)
        m_log = with_mutation(old_la, old_la.replace("_la_path", "path"), path=LOG)
        old_rb = self._slice(CONTEXT, "context_review_round_bind() {\n", "\n}\n")
        self.assertIn("_rb_path", old_rb)
        m_ctx = with_mutation(old_rb, old_rb.replace("_rb_path", "path"), path=CONTEXT)
        builds = (("shipped", (MARKER, LOG, CONTEXT)),
                  ("marker",  (m_marker, LOG, CONTEXT)),
                  ("log",     (MARKER, m_log, CONTEXT)),
                  ("context", (MARKER, LOG, m_ctx)))
        state = os.path.join(self.target, ".state")
        logp = os.path.join(self.target, "logs", "r162.jsonl")
        expect = "ms=[fail] rb=[1] rl=[1] ls=[/bin/ls]"
        try:
            for shell in SHELLS:
                zsh = shell.endswith("zsh")
                for build, fam in builds:
                    self._wipe()
                    for d in ("logs", ".state", "reviews"):
                        shutil.rmtree(os.path.join(self.target, d), ignore_errors=True)
                    body = (f'export HOME="{self.home}"\nexport CLAUDE_PLUGIN_DATA="{self.target}"\n'
                            + "".join(f'. "{s}"\n' for s in (AUTH, STORE, READER, PUB, PATHS_C4) + fam)
                            + 'marker_write lint fail\n'
                              'ms="$(marker_status lint)"\n'
                              'log_append r162.jsonl \'{"ts":"t"}\'\n'
                              'rb="$(context_review_round_bind security-reviewer agent-162 sess-162)"\n'
                              'rl="$(context_review_round_lookup security-reviewer agent-162 sess-162)"\n'
                              'printf "ms=[%s] rb=[%s] rl=[%s] ls=[%s]" "$ms" "$rb" "$rl" "$(command -v ls)"')
                    rc, out, err = run_shell(shell, body, sources=())
                    tag = f"{shell} {build}"
                    markers = ([f for f in os.listdir(state) if f.startswith("quality-marker-lint-")]
                               if os.path.isdir(state) else [])
                    bindings = ([f for f in os.listdir(state)
                                 if f.startswith("review-round-") and f.endswith(".json")]
                                if os.path.isdir(state) else [])
                    logged = os.path.exists(logp)
                    if not zsh or build == "shipped":
                        self.assertEqual(expect, out, f"{tag}: {err!r}")
                        self.assertEqual("", err, f"{tag}: {err!r}")
                        self.assertEqual(1, len(markers), f"{tag}: marker not written: {markers}")
                        self.assertTrue(logged, f"{tag}: log line not persisted")
                        self.assertEqual(1, len(bindings), f"{tag}: binding not published: {bindings}")
                        with open(logp, encoding="utf-8") as fh:
                            self.assertEqual({"ts": "t", "base_resolution": "host-env"}, json.loads(fh.read()))
                    elif build == "marker":
                        self.assertIn("read-only variable: status", err,
                                      f"{tag}: the CONTROL did not fail — zsh accepted `local status`: {err!r}")
                        self.assertEqual("", out, f"{tag}: the script survived the read-only assignment: {out!r}")
                        self.assertEqual([], markers, f"{tag}: a marker was written: {markers}")
                    elif build == "log":
                        self.assertEqual(expect, out, f"{tag}: the other writers were disturbed: {out!r} {err!r}")
                        self.assertFalse(logged, f"{tag}: the CONTROL did not fail — `local path` "
                                                 f"did not empty PATH for the log writer")
                    else:                       # context
                        self.assertTrue(out.startswith("ms=[fail] rb=["), f"{tag}: {out!r} {err!r}")
                        self.assertIn("rl=[] ls=[/bin/ls]", out,
                                      f"{tag}: the CONTROL did not fail — the binding was published "
                                      f"and read back, or PATH did not recover: {out!r}")
                        self.assertEqual([], bindings, f"{tag}: a binding was published: {bindings}")
                        self.assertIn("command not found", err, f"{tag}: {err!r}")
        finally:
            for m in (m_marker, m_log, m_ctx):
                os.unlink(m)

    # ── row 163 ───────────────────────────────────────────────────────────────────────────────

    def test_row_163_a_hidden_store_is_rule_minus_one_not_rule_four(self):
        """Row 163: the store exists with one authenticating entry and `${HOME}/.claude` is `chmod 600` (exists, not searchable): the specification takes rule −1 — `stale`, one diagnostic, `OK=0` — because the store is HIDDEN, not absent; under `[ ! -e ] && [ ! -L ]` on the full path the reader reports `none` ("does not exist") — the outcome SessionStart's repair notice does not fire on. A genuinely absent store (`unleashed-mail/` missing under a searchable `.claude`) reports `none` in BOTH builds. Both shells."""
        # `[ -e ]` and `[ -L ]` both need SEARCH permission on every ancestor to answer, so on a
        # 0600 `.claude` they are both false for a store that exists — "absent" and "hidden" are
        # indistinguishable to the full-path test, and only RD-8's walk (which stops at the first
        # component that exists but is not a searchable directory) tells them apart. The store and
        # its entry are built with `.claude` searchable, then `.claude` is closed and REOPENED in a
        # finally so the scratch home can be swept. Measured, both shells: spec hidden
        # `0 unresolved stale` + one diagnostic naming "not usable"; mutant hidden
        # `0 unresolved none` + one diagnostic naming "does not exist"; absent `0 unresolved none`
        # under both builds.
        mutant = with_mutation(
            '    if _unleashed_store_absent "$_rs_store"; then\n',
            '    if [ ! -e "$_rs_store" ] && [ ! -L "$_rs_store" ]; then\n',
            path=READER)
        claude_dir = os.path.join(self.home, ".claude")
        read = (f'export HOME="{self.home}"\n'
                f'_unleashed_read_store "{self.store}"\n' + self.OUTP)
        try:
            for shell in SHELLS:
                for reader, is_mutant in ((READER, False), (mutant, True)):
                    srcs = (AUTH, STORE, reader, PUB)
                    self._wipe()
                    rc, out, err = run_shell(shell, f'export HOME="{self.home}"\n' + self._mkstore()
                                             + self._entry(), sources=srcs)
                    self.assertEqual(0, rc, f"{shell}: the fixture store could not be built: {err!r}")
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    # (a) HIDDEN: the store exists, its grandparent is not searchable.
                    os.chmod(claude_dir, 0o600)
                    try:
                        rc, out, err = run_shell(shell, read, sources=srcs)
                    finally:
                        os.chmod(claude_dir, 0o700)
                    diags = self._diags(err)
                    self.assertEqual(1, len(diags), f"{tag}: not one diagnostic: {err!r}")
                    self.assertNotIn(self.home, err, f"{tag}: the diagnostic leaked a path")
                    if not is_mutant:
                        self.assertEqual("0 unresolved stale", out,
                                         f"{tag}: a hidden store was not refused by rule -1: {out!r} {err!r}")
                        self.assertIn("is not usable", diags[0], f"{tag}: not rule -1's line: {diags[0]!r}")
                    else:
                        self.assertEqual("0 unresolved none", out,
                                         f"{tag}: the CONTROL did not fail — the full-path test told "
                                         f"a hidden store from an absent one: {out!r} {err!r}")
                        self.assertIn("does not exist", diags[0], f"{tag}: not rule 4's line: {diags[0]!r}")
                    # The store was never touched by either build: still one entry, still 0700.
                    self.assertEqual(1, len([f for f in os.listdir(self.store) if f.startswith("base.")]), tag)
                    # (b) genuinely ABSENT: `unleashed-mail/` missing under a searchable `.claude`.
                    shutil.rmtree(os.path.join(claude_dir, "unleashed-mail"))
                    rc, out, err = run_shell(shell, read, sources=srcs)
                    self.assertEqual("0 unresolved none", out, f"{tag}: an absent store is rule 4: {out!r} {err!r}")
                    self.assertEqual(1, len(self._diags(err)), f"{tag}: not one diagnostic: {err!r}")
                    self.assertIn("does not exist", err, f"{tag}: {err!r}")
        finally:
            os.unlink(mutant)
            if os.path.isdir(claude_dir):
                os.chmod(claude_dir, 0o700)

    # ── row 164 ───────────────────────────────────────────────────────────────────────────────

    def test_row_164_a_symlink_at_base_key_is_refused_not_repaired(self):
        """Row 164: `base.<key>` is a SYMLINK to a regular `0600` file elsewhere holding the publisher's own base: the specification refuses at ST-7 — `failed`, one diagnostic, the symlink UNTOUCHED, no transient left; under `[ ! -f ]` alone (`-f` FOLLOWS the link) the publisher `mv -f`s its transient over the link and reports `created`, and `base.<key>` is now a regular file. Both shells."""
        # THE GUARD IS REACHED: a symlink entry fails ENT-1 in `_unleashed_auth_entry` (the
        # write-or-skip test before ST-7), so the publisher takes the write branch and ST-7 is the
        # next test — the specification's diagnostic is ST-7's own line ("exists and is not a
        # regular file"), which is the proof. Row 113 pins the symlink-to-DIRECTORY, directory and
        # DANGLING shapes; only this row pins the shape `[ ! -f ]` cannot see — a link to a regular
        # file. Measured, both shells: spec `1 host-env failed`, one diagnostic, link intact, no
        # `.pub.*`; mutant `1 host-env created`, no diagnostic, `base.<key>` a regular file, the
        # linked-to file untouched either way (mv replaces the link, not what it points at).
        mutant = with_mutation(
            '        if [ -L "$_pb_entry" ] || { [ -e "$_pb_entry" ] && [ ! -f "$_pb_entry" ]; }; then\n',
            '        if { [ -L "$_pb_entry" ] || [ -e "$_pb_entry" ]; } && [ ! -f "$_pb_entry" ]; then\n',
            path=PUB)
        elsewhere = os.path.join(self.home, "elsewhere")
        real = os.path.join(elsewhere, "real")
        publish = (f'export HOME="{self.home}"\n'
                   f'_unleashed_publish "{self.store}" "{self.target}"\n' + self.OUTP)
        try:
            for shell in SHELLS:
                for pub, is_mutant in ((PUB, False), (mutant, True)):
                    srcs = (AUTH, STORE, READER, pub)
                    self._wipe()
                    shutil.rmtree(elsewhere, ignore_errors=True)
                    rc, key, err = run_shell(shell, f'export HOME="{self.home}"\n' + self._mkstore()
                                             + f'_unleashed_key "{self.target}"\nprintf "%s" "$_UNLEASHED_KEY"',
                                             sources=srcs)
                    self.assertEqual(0, rc, f"{shell}: the fixture store could not be built: {err!r}")
                    self.assertTrue(key, f"{shell}: no key derived")
                    os.makedirs(elsewhere, mode=0o700)
                    with open(real, "w", encoding="utf-8") as fh:
                        fh.write(self.target + "\n")               # the publisher's OWN base value
                    os.chmod(real, 0o600)
                    entry = os.path.join(self.store, "base." + key)
                    os.symlink(real, entry)
                    rc, out, err = run_shell(shell, publish, sources=srcs)
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    diags = self._diags(err)
                    pubs = [f for f in os.listdir(self.store) if f.startswith(".pub.")]
                    self.assertEqual([], pubs, f"{tag}: a transient was left behind: {pubs}")
                    with open(real, encoding="utf-8") as fh:
                        self.assertEqual(self.target + "\n", fh.read(), f"{tag}: the linked-to file was written")
                    if not is_mutant:
                        self.assertEqual("1 host-env failed", out, f"{tag}: ST-7 did not refuse: {out!r} {err!r}")
                        self.assertEqual(1, len(diags), f"{tag}: not one diagnostic: {err!r}")
                        self.assertIn("exists and is not a regular file", diags[0],
                                      f"{tag}: not ST-7's line — the guard was not what refused: {diags[0]!r}")
                        self.assertNotIn(self.home, err, f"{tag}: the diagnostic leaked a path")
                        self.assertTrue(os.path.islink(entry), f"{tag}: the symlink at base.<key> was replaced")
                        self.assertEqual(real, os.readlink(entry), f"{tag}: the link was re-pointed")
                    else:
                        self.assertEqual("1 host-env created", out,
                                         f"{tag}: the CONTROL did not fail — `[ ! -f ]` alone refused "
                                         f"the link: {out!r} {err!r}")
                        self.assertEqual([], diags, f"{tag}: {err!r}")
                        self.assertFalse(os.path.islink(entry), f"{tag}: the link survived the mutant's mv -f")
                        self.assertTrue(os.path.isfile(entry), f"{tag}: base.<key> is not a regular file")
                        with open(entry, encoding="utf-8") as fh:
                            self.assertEqual(self.target + "\n", fh.read(), f"{tag}: not the transient's bytes")
        finally:
            os.unlink(mutant)

    # ── row 165 ───────────────────────────────────────────────────────────────────────────────

    def _hook(self, script, source, extra_env=None):
        """Run the SessionStart hook once: HOME = the scratch, `CLAUDE_PLUGIN_DATA` = t1, stdin = the
        SessionStart JSON. Returns (rc, stdout, stderr). bash only — the hook is a bash script."""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("_UNLEASHED") and k not in ("CLAUDE_PLUGIN_DATA", "UNLEASHED_COMPACT_RESTORE",
                                                               "HOOK_STDIN", "_HOOK_IO_READ_DONE")}
        env.update({"HOME": self.home, "CLAUDE_PLUGIN_DATA": self.target})
        env.update(extra_env or {})
        p = subprocess.run(["/bin/bash", script], input=json.dumps({"source": source}),
                           capture_output=True, text=True, env=env, timeout=30)
        return p.returncode, p.stdout, p.stderr

    def test_row_165_the_sessionstart_notice_is_evaluated_before_the_source_filter(self):
        """Row 165: a store in `conflict` (two entries): the SessionStart hook run with `{"source":"clear"}`, with `{"source":"weird"}` and with `{"source":"clear"}` + `UNLEASHED_COMPACT_RESTORE=off` — the specification emits the notice (`base store is conflict`) on every one; under the mutation (the source filter's branch back to a bare `exit 0`) `clear` and `weird` are silent. A `created` store stays silent on `clear` in both builds. The hook is bash; the helper publish runs in bash."""
        # THE MUTANT MUST FIND `lib/`: the hook resolves `_DIR` from its own `BASH_SOURCE[0]` and sources
        # `$_DIR/lib/hook-io.sh` + `$_DIR/lib/context.sh`, so a mutant copy left where with_mutation puts it
        # would fail to load the resolver, see `none`, and be silent for the WRONG reason. The copy is
        # placed at `<scratch>/scripts/sessionstart-restore.sh` with `<scratch>/scripts/lib` a SYMLINK to
        # the real lib — `cd "$(dirname …)" && pwd` does not resolve the link, so `$_DIR/lib/…` reads
        # through it (measured). The kill-switch cell PROVES the machinery loaded under the mutant: its
        # `_ss_exit` is untouched by this mutation and it emits the notice only if the resolver saw the
        # conflict. Measured (bash): spec `clear`/`weird`/`off` all carry `base store is conflict`, `created`
        # on `clear` prints nothing; mutant `clear` and `weird` print NOTHING, `off` still carries the notice.
        t2 = os.path.join(self.home, "target2")
        os.makedirs(t2)
        os.chmod(t2, 0o700)
        mut_root = os.path.join(self.home, "mut", "scripts")
        os.makedirs(mut_root)
        lib_link = os.path.join(mut_root, "lib")
        os.symlink(LIBDIR, lib_link)
        mutant_tmp = with_mutation('    *) _ss_exit ;;\n', '    *) exit 0 ;;\n', path=SESSIONSTART_P7)
        mutant = os.path.join(mut_root, "sessionstart-restore.sh")
        shutil.move(mutant_tmp, mutant)
        publish_t2 = (f'export HOME="{self.home}"\n'
                      f'_unleashed_publish "{self.store}" "{t2}"\n' + self.OUTP)
        NOTICE = "base store is conflict"
        try:
            self._row_165_cells(SESSIONSTART_P7, mutant, publish_t2, NOTICE)
        finally:
            # BEFORE tearDown: its chmod sweep FOLLOWS a directory symlink and would set the REAL
            # scripts/lib to 0700 (measured — it did, once). The link is removed here, first.
            os.unlink(lib_link)

    def _row_165_cells(self, shipped, mutant, publish_t2, NOTICE):
        for script, is_mutant in ((shipped, False), (mutant, True)):
            tag = "mutant" if is_mutant else "shipped"
            # (a) CONFLICT: t2 already published; the hook's own resolver publishes t1 beside it.
            self._wipe()
            rc, out, err = run_shell("/bin/bash", publish_t2)
            self.assertEqual("1 host-env created", out, f"{tag}: the fixture store could not be seeded: {err!r}")
            results = {}
            for cell, source, extra in (("clear", "clear", None), ("weird", "weird", None),
                                        ("off", "clear", {"UNLEASHED_COMPACT_RESTORE": "off"})):
                rc, out, err = self._hook(script, source, extra)
                self.assertEqual(0, rc, f"{tag} {cell}: the hook did not exit 0: {err!r}")
                self.assertNotIn("command not found", err, f"{tag} {cell}: the hook did not find its lib/: {err!r}")
                results[cell] = out
            entries = sorted(f for f in os.listdir(self.store) if f.startswith("base."))
            self.assertEqual(2, len(entries), f"{tag}: the store is not in conflict (two entries): {entries}")
            # The kill-switch cell is untouched by the mutation: it carries the notice in BOTH builds,
            # which is also the proof that the resolver loaded and observed the conflict under the mutant.
            self.assertIn(NOTICE, results["off"], f"{tag} off: {results['off']!r}")
            self.assertIn('"hookEventName":"SessionStart"', results["off"], f"{tag} off: {results['off']!r}")
            if not is_mutant:
                self.assertIn(NOTICE, results["clear"], f"{tag} clear: the notice never reached a `clear` session: {results['clear']!r}")
                self.assertIn(NOTICE, results["weird"], f"{tag} weird: the notice never reached an unknown source: {results['weird']!r}")
            else:
                self.assertEqual("", results["clear"],
                                 f"{tag} clear: the CONTROL did not fail — the bare `exit 0` still emitted: {results['clear']!r}")
                self.assertEqual("", results["weird"],
                                 f"{tag} weird: the CONTROL did not fail — the bare `exit 0` still emitted: {results['weird']!r}")
            # (b) CREATED: no store at all, so the hook's publish creates it fresh — silent on `clear` in both builds.
            self._wipe()
            rc, out, err = self._hook(script, "clear")
            self.assertEqual(0, rc, f"{tag} created: {err!r}")
            self.assertEqual("", out, f"{tag} created: a `created` store must stay silent on `clear`: {out!r}")
            entries = [f for f in os.listdir(self.store) if f.startswith("base.")]
            self.assertEqual(1, len(entries), f"{tag} created: the hook did not publish exactly one entry: {entries}")

    # ── row 166 ───────────────────────────────────────────────────────────────────────────────

    #: Row 166's exec'd resolver copies and the base primitive each exposes. agent-env-bridge.sh
    #: takes positional arguments and is not sourced by an exec'd hook shell, so it is not run here.
    ROW_166 = (("paths.sh", "unleashed_plugin_base"), ("marker.sh", "marker_base"),
               ("log.sh", "log_base"), ("context.sh", "context_base"))

    def _row_166_cell(self, shell, body):
        """One wrapper shell. The environment carries NONE of the protocol variables in: what the
        exec'd shell inherits must come from the wrapper's own `set -a`, or the row measures the
        test runner's environment. Returns (rc, stdout, stderr)."""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("_UNLEASHED") and k != "CLAUDE_PLUGIN_DATA"}
        p = subprocess.run([shell, "-c", body], capture_output=True, text=True, env=env, timeout=30)
        return p.returncode, p.stdout, p.stderr

    def test_row_166_an_inherited_resolution_is_discarded_by_the_readonly_instance_check(self):
        """Row 166: a wrapper shell under `set -a` sources a resolver copy with `CLAUDE_PLUGIN_DATA=<a>`, sets `<b>` and `exec`s a hook shell that sources the same file — the specification resolves afresh (the hook prints `<b>`) in both shells; under the mutation (the readonly-attribute instance check removed) the bash hook keeps `<a>` — bash's `set -a` exported the marker function too, and pid + function alone are satisfied across `exec`. A subshell prints `<a>` and a fork+exec child prints `<b>` in BOTH builds. zsh cannot carry a function across `exec`, so its mutant hook already resolves afresh on the pid + function key: the zsh half asserts `<b>` in both builds and does not discriminate (measured; the plan row's parenthesis names bash as the carrier)."""
        # THE MUTATION is the whole instance-check block — `if [ -n "${_UNLEASHED_BASE_INSTANCE+set}" ]`
        # through its `fi` — sliced from the CURRENT file. Each copy is exercised where it is the
        # resolver in force (row 156's shape): paths.sh with the machinery beside it; the family
        # files from a shadow root WITHOUT paths.sh, so their own instance check and fallback guard
        # run rather than paths.sh's. `_UNLEASHED_PUBLISH_OK=0`: E0, so no cell writes a store.
        # Measured, all four files: bash exec spec `b` / mutant `a`; zsh exec `b` / `b`; subshell
        # `a` / `a` (the readonly attribute survives a fork, and so do `$$` and the function);
        # fork+exec child `b` / `b` (a fresh pid resolves afresh from its own environment).
        a = os.path.join(self.home, "base-a")
        b = os.path.join(self.home, "base-b")
        os.makedirs(a)
        os.makedirs(b)
        head = 'if [ -n "${_UNLEASHED_BASE_INSTANCE+set}" ]; then\n'
        machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
        for fam, prim in self.ROW_166:
            src = os.path.join(LIBDIR, fam)
            # (The block gained a `_ubi_decl` capture and its cleanup in PR #67 pass 14 — row 176 —
            # so the tail anchor is the cleanup line before the `fi`, not the `esac` itself.)
            block = self._slice(src, head, '    unset _ubi_decl 2>/dev/null || :\nfi\n')
            self.assertIn("declare -p _UNLEASHED_BASE_INSTANCE", block, block)
            self.assertIn("unset -f _unleashed_resolved_in_process", block, block)
            mutant = with_mutation(block, "", path=src)
            try:
                # machinery + THIS file only: paths.sh is present exactly when it is the file under test.
                spec_root = self._shadow(f"spec166-{fam}", dict(machinery, **{fam: src}))
                mut_root = self._shadow(f"mut166-{fam}", dict(machinery, **{fam: mutant}))
                for shell in SHELLS:
                    bash = shell.endswith("bash")
                    for root, is_mutant in ((spec_root, False), (mut_root, True)):
                        f = os.path.join(root, "scripts", "lib", fam)
                        hook = f'. "{f}"; printf %s "$({prim})"'
                        wrap = (f'set -a; export HOME="{self.home}" CLAUDE_PLUGIN_DATA="{a}" '
                                f'_UNLEASHED_PUBLISH_OK=0; . "{f}"; set +a; export CLAUDE_PLUGIN_DATA="{b}"; ')
                        cells = {
                            "exec":     wrap + f"exec {shell} -c '{hook}'",
                            "subshell": wrap + f"( {hook} )",
                            # no `set -a`: plain exports, a NEW process (fork+exec), same file.
                            "forkexec": (f'export HOME="{self.home}" CLAUDE_PLUGIN_DATA="{a}" '
                                         f'_UNLEASHED_PUBLISH_OK=0; . "{f}"; export CLAUDE_PLUGIN_DATA="{b}"; '
                                         f"{shell} -c '{hook}'"),
                        }
                        for cell, body in cells.items():
                            self._wipe()
                            rc, out, err = self._row_166_cell(shell, body)
                            tag = f"{fam} {shell} {'mutant' if is_mutant else 'shipped'} {cell}"
                            self.assertEqual(0, rc, f"{tag}: rc {rc}: {err!r}")
                            self.assertNotIn("command not found", err, f"{tag}: {err!r}")
                            self.assertEqual([], self._diags(err), f"{tag}: a resolved base diagnosed: {err!r}")
                            self.assertFalse(os.path.exists(self.store), f"{tag}: E0 wrote a store")
                            if cell == "subshell":
                                self.assertEqual(a, out, f"{tag}: a subshell is the same instance and keeps "
                                                         f"its resolution in both builds: {out!r}")
                            elif cell == "forkexec":
                                self.assertEqual(b, out, f"{tag}: a fresh process resolves afresh from its "
                                                         f"own environment in both builds: {out!r}")
                            elif not is_mutant:
                                self.assertEqual(b, out, f"{tag}: the exec'd hook kept the wrapper's stale "
                                                         f"base — the inherited resolution was trusted: {out!r} {err!r}")
                            elif bash:
                                self.assertEqual(a, out, f"{tag}: the CONTROL did not fail — without the "
                                                         f"instance check the exec'd bash hook still resolved "
                                                         f"afresh: {out!r} {err!r}")
                            else:
                                # zsh: no function crosses exec, so pid + function already miss and the
                                # mutant resolves afresh too — asserted, not claimed as discrimination.
                                self.assertEqual(b, out, f"{tag}: {out!r} {err!r}")
            finally:
                os.unlink(mutant)

    # ── row 167 ───────────────────────────────────────────────────────────────────────────────

    def test_row_167_the_paths_sh_body_guard_is_the_complete_api_not_one_exportable_function(self):
        """Row 167: a bash parent sources paths.sh and `export -f unleashed_resolve_base`; a child sources paths.sh — the specification (unconditional definitions) defines the whole API: `unleashed_plugin_base` prints the sentinel (variable unset, no store) or the base (variable set), `unleashed_base_ok` is defined; under the mutation — a one-function guard WRAPPED around the definition block — the block is skipped, the imported resolver runs alone from the eager call — `command not found` on stderr — and `unleashed_plugin_base` is undefined: EMPTY output, `unleashed_base_ok` UNDEFINED. bash only: zsh cannot export functions. (Reshaped in pass 12: the mutation ADDS the guard.)"""
        # Measured: spec `<sentinel>|defined` (unset cell) and `<target>|defined` (set cell), no
        # `command not found`; mutant `|UNDEFINED` in both cells, and in the unset cell the imported
        # resolver's `_unleashed_home_ok` is `command not found` at source time (the set cell's E0
        # fence returns before it, and the primitive's own 127 is silenced by the cell's redirect).
        mutant = self._guarded_paths('if ! command -v unleashed_resolve_base >/dev/null 2>&1; then\n')
        try:
            machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
            spec_root = self._shadow("spec167", dict(machinery, **{"paths.sh": PATHS_C4}))
            mut_root = self._shadow("mut167", dict(machinery, **{"paths.sh": mutant}))
            child = ('printf "%s|%s" "$(unleashed_plugin_base 2>/dev/null)" '
                     '"$(command -v unleashed_base_ok >/dev/null && echo defined || echo UNDEFINED)"')
            for root, is_mutant in ((spec_root, False), (mut_root, True)):
                paths = os.path.join(root, "scripts", "lib", "paths.sh")
                for cell, pre, want in (("unset", "unset CLAUDE_PLUGIN_DATA\n", SENTINEL),
                                        ("set", f'export CLAUDE_PLUGIN_DATA="{self.target}" '
                                                '_UNLEASHED_PUBLISH_OK=0\n', self.target)):
                    self._wipe()
                    body = (pre + f'. "{paths}"\n'
                            'export -f unleashed_resolve_base\n'
                            f"/bin/bash -c '. \"{paths}\"; {child}'")
                    rc, out, err = run_shell("/bin/bash", body, sources=(), env={"HOME": self.home})
                    tag = f"{'mutant' if is_mutant else 'shipped'} {cell}"
                    if not is_mutant:
                        self.assertEqual(f"{want}|defined", out, f"{tag}: {err!r}")
                        self.assertNotIn("command not found", err, f"{tag}: {err!r}")
                    else:
                        self.assertEqual("|UNDEFINED", out,
                                         f"{tag}: the CONTROL did not fail — the one-function guard still "
                                         f"defined the API in the child: {out!r} {err!r}")
                        if cell == "unset":
                            self.assertIn("command not found", err, f"{tag}: {err!r}")
                    self.assertFalse(os.path.exists(self.store), f"{tag}: a store appeared")
        finally:
            os.unlink(mutant)

    # ── row 168 ───────────────────────────────────────────────────────────────────────────────

    #: The pathname re-test's own inode clause (PR #67 pass 15, row 178), and the shape without it.
    #: Row 168's mutation removes EVERY binding to `_ae_ino`, so "the opened entry must be the inode
    #: ENT-1 validated" is tested against a build that binds to it nowhere — otherwise the re-test
    #: refuses row 168's copy on its own and the row would stop discriminating (it did: the row failed
    #: the moment the re-test landed, which is how the third clause was found).
    ROW_168_PATH_INODE = '    if _u_stat "$1" && [ "$_U_INO" = "$_ae_ino" ]; then _ue_rc=0; else _ue_rc=1; fi\n'
    ROW_168_PATH_INODE_GONE = '    if _u_stat "$1"; then _ue_rc=0; else _ue_rc=1; fi\n'

    def test_row_168_the_opened_entry_must_be_the_inode_ent_1_validated(self):
        """Row 168: a DEBUG trap (`set -T` in bash) replaces the entry with a 0644 COPY of itself — same bytes, same size, same owner, a different inode — the instant ENT-1 has validated it and before ENT-2b opens it: the specification refuses (`stale`, one sanitised diagnostic) because the opened inode is not the validated one; under the mutation (EVERY binding to `_ae_ino` removed — both descriptor arms and the pathname re-test ENT-2c added in PR #67 pass 15) type, uid and size all still match on the descriptor, the copy authenticates and the store RESOLVES to a world-readable entry (`1 pointer none`). Row 160's large-file substitution stays refused under this mutant in both builds — its size differs. Both shells."""
        # THE INTERLEAVING IS DETERMINISTIC (row 160's shape): keyed on `_ae_bound` being set — the
        # line before `_ae_ino=` — and a once-flag, the trap fires before `_ae_ino="$_U_INO"` runs;
        # `_U_INO` is ENT-1's pathname stat, untouched by the cp/chmod/mv, so `_ae_ino` is the
        # ORIGINAL inode in both builds and the open that follows finds the copy. Measured, both
        # shells: spec `0 unresolved stale <sentinel>` and the entry is 0644 afterwards (the
        # substitution happened); mutant `1 pointer none <target>`, empty stderr.
        m1 = with_mutation('            && [ "${_u_h[inode]}" = "$_ae_ino" ] \\\n', '', path=READER)
        m2 = with_mutation('              && [ "$_U_INO" = "$_ae_ino" ] \\\n', '', path=m1)
        m3 = with_mutation(self.ROW_168_PATH_INODE, self.ROW_168_PATH_INODE_GONE, path=m2)
        with open(m3, encoding="utf-8") as fh:
            self.assertNotIn('"$_ae_ino"', fh.read(), "an inode clause survived the triple mutation")
        copy = ('/bin/cp "$_ae_p" "$_ae_p.n"; /bin/chmod 644 "$_ae_p.n"; /bin/mv -f "$_ae_p.n" "$_ae_p"')
        big = os.path.join(self.home, "big")
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, m3, PUB), True)):
                    self._wipe()
                    body = (self._mkstore() + self._entry()
                            + '[ -n "${BASH_VERSION:-}" ] && set -T\n'
                            + 'trap \'if [ -n "${_ae_bound:-}" ] && [ -z "${_t168_done:-}" ] '
                              '&& [ -f "${_ae_p:-}" ]; then _t168_done=1; ' + copy + '; fi\' DEBUG\n'
                            + f'_unleashed_read_store "{self.store}"\n'
                            + 'trap - DEBUG\n'
                            + 'printf "%s %s %s %s|%s|%s" "$_UNLEASHED_BASE_OK" '
                              '"$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE" '
                              '"$_UNLEASHED_BASE_RESOLVED" "${_t168_done:-0}" '
                              f'"$(/usr/bin/stat -f %Lp "{self.store}"/base.* 2>/dev/null)"')
                    rc, out, err = self._run_with_timeout(shell, body, srcs)
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    self.assertNotEqual("TIMEOUT", rc, f"{tag}: the resolver hung")
                    if not is_mutant:
                        self.assertEqual(f"0 unresolved stale {SENTINEL}|1|644", out,
                                         f"{tag}: not refused, or the trap did not fire, or the copy was "
                                         f"not what was opened: {out!r} {err!r}")
                        diags = self._diags(err)
                        self.assertEqual(1, len(diags), f"{tag}: not one diagnostic: {err!r}")
                        self.assertEqual(1, len(err.splitlines()), f"{tag}: {err!r}")
                        self.assertNotIn(self.store, err, f"{tag}: the store path reached stderr")
                        self.assertNotIn(self.target, err, f"{tag}: the target path reached stderr")
                    else:
                        self.assertEqual(f"1 pointer none {self.target}|1|644", out,
                                         f"{tag}: the CONTROL did not fail — without the inode clause the "
                                         f"0644 copy did not authenticate: {out!r} {err!r}")
                        self.assertEqual("", err, f"{tag}: {err!r}")
                # Row 160's discriminating substitute — a 0600 file whose first line is the target
                # followed by 200 000 bytes — stays refused under THIS mutant: its size exceeds the
                # bound ENT-2b still validates on the descriptor. The inode clause is not what refuses it.
                self._wipe()
                with open(big, "w", encoding="utf-8") as fh:
                    fh.write(self.target + "\n" + "a" * 200000 + "\n")
                os.chmod(big, 0o600)
                body = (self._mkstore() + self._entry()
                        + '[ -n "${BASH_VERSION:-}" ] && set -T\n'
                        + 'trap \'if [ -n "${_ae_bound:-}" ] && [ -z "${_t168_done:-}" ] '
                          '&& [ -f "${_ae_p:-}" ] && [ "$(/usr/bin/stat -f %z "$_ae_p")" -lt 100 ]; then '
                          f'_t168_done=1; /bin/mv -f "{big}" "$_ae_p"; fi\' DEBUG\n'
                        + f'_unleashed_read_store "{self.store}"\n'
                        + 'trap - DEBUG\n'
                        + 'printf "%s %s %s|%s|%s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_POINTER_STATE" '
                          '"$_UNLEASHED_BASE_RESOLVED" "${#_ae_line}" "${_t168_done:-0}"')
                rc, out, err = self._run_with_timeout(shell, body, (AUTH, STORE, m3, PUB))
                self.assertEqual(f"0 stale {SENTINEL}|0|1", out,
                                 f"{shell} mutant, row 160's large file: not refused on size alone: {out!r} {err!r}")
        finally:
            os.unlink(m1)
            os.unlink(m2)
            os.unlink(m3)

    # ── row 169 ───────────────────────────────────────────────────────────────────────────────

    #: The UUID-self clause of `_u_acl_check_ace` — the one line row 169 removes and row 129 inverts.
    UUID_SELF_CLAUSE = ('            [ -n "${_U_PRINCIPAL_UUID:-}" ] && [ "$_u13_principal" = "$_U_PRINCIPAL_UUID" ] '
                        '&& return 0 ;;\n')

    def test_row_169_a_bare_uuid_equal_to_the_effective_users_resolved_uuid_is_self(self):
        """Row 169: the enumerator seam presents ` 0: <UUID> allow write` where `<UUID>` is `/usr/bin/dsmemberutil getuuid -U "$(/usr/bin/id -un)"` on THIS host — a mutating right, so a FOREIGN reading refuses: the specification treats it as SELF and the component AUTHENTICATES (the store resolves `1 pointer none`; the publisher publishes `created`); under the mutation (the UUID-self clause removed — every bare UUID foreign, the pre-audit behaviour) it REFUSES (`0 unresolved stale`, `failed`, one diagnostic). A DIFFERENT UUID with the same right refuses in BOTH builds (row 129). Both shells. Skipped, never faked, on a host whose `dsmemberutil` returns no 8-4-4-4-12 UUID."""
        # THE UUID IS PROBED AT TEST TIME by the same absolute-path command the library's own probe
        # runs, so the fixture is the effective user's rendering on this machine and not a constant.
        # Measured, both shells: spec own-UUID `1 pointer none` / `created`, no diagnostic; mutant
        # own-UUID `0 unresolved stale` / `failed`, one diagnostic; foreign UUID refuses in both builds.
        try:
            user = subprocess.run(["/usr/bin/id", "-un"], capture_output=True, text=True, check=True).stdout.strip()
            probe = subprocess.run(["/usr/bin/dsmemberutil", "getuuid", "-U", user],
                                   capture_output=True, text=True, check=False)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            self.skipTest(f"the effective user's UUID cannot be probed on this host: {exc}")
        uuid = probe.stdout.strip()
        if probe.returncode != 0 or not re.fullmatch(r"[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", uuid):
            self.skipTest(f"dsmemberutil returned no 8-4-4-4-12 UUID for the effective user: {probe.stdout!r} {probe.stderr!r}")
        foreign = "ABCDEFAB-CDEF-ABCD-CDEF-ABCDEFABCDEF"
        self.assertNotEqual(uuid.upper(), foreign)
        mutant = with_mutation(self.UUID_SELF_CLAUSE, '            : ;;\n', path=AUTH)
        pubstore = os.path.join(self.home, "pub", "bases")
        reset = ('unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE '
                 '_UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL\n')
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((mutant, STORE, READER, PUB), True)):
                    for who, principal in (("own", uuid), ("foreign", foreign)):
                        self._wipe()
                        shutil.rmtree(os.path.join(self.home, "pub"), ignore_errors=True)
                        body = (self._mkstore() + self._entry() + reset
                                + seam(f"drwx------@ 2 n s 64 d\n 0: {principal} allow write\n")
                                + f'_unleashed_read_store "{self.store}"\n' + self.OUTP
                                + '\n' + reset
                                + f'_unleashed_publish "{pubstore}" "{self.target}"\n'
                                + 'printf "|%s" "$_UNLEASHED_POINTER_STATE"')
                        rc, out, err = run_shell(shell, body, sources=srcs, env={"HOME": self.home})
                        tag = f"{shell} {'mutant' if is_mutant else 'shipped'} {who}"
                        diags = self._diags(err)
                        if who == "own" and not is_mutant:
                            self.assertEqual("1 pointer none|created", out,
                                             f"{tag}: the effective user's own UUID was read as FOREIGN: {out!r} {err!r}")
                            self.assertEqual([], diags, f"{tag}: {err!r}")
                            self.assertTrue(os.path.isdir(pubstore), f"{tag}: the publisher did not publish")
                        else:
                            self.assertEqual("0 unresolved stale|failed", out,
                                             (f"{tag}: the CONTROL did not fail — without the UUID-self clause the "
                                              f"own UUID still authenticated: {out!r} {err!r}") if who == "own" else
                                             f"{tag}: a foreign UUID with a mutating right authenticated: {out!r} {err!r}")
                            self.assertEqual(2, len(diags), f"{tag}: not one diagnostic per refusing entry point: {err!r}")
                            self.assertFalse(os.path.exists(pubstore), f"{tag}: the refusing publisher created the store")
                        self.assertNotIn(self.store, err, f"{tag}: the store path reached stderr")
        finally:
            os.unlink(mutant)


    # ── row 170 ───────────────────────────────────────────────────────────────────────────────

    #: The complete-API guard the definition block carried before PR #67 pass 12 — restored verbatim
    #: as row 170's mutation. bash `set -a` exports every function defined while it is active, so
    #: "all six names are present" is satisfiable by an environment.
    ROW_170_GUARD = (
        'if ! { command -v unleashed_resolve_base >/dev/null 2>&1 && command -v unleashed_plugin_base >/dev/null 2>&1 \\\n'
        '    && command -v unleashed_base_ok >/dev/null 2>&1 && command -v _unleashed_load_state_machinery >/dev/null 2>&1 \\\n'
        '    && command -v _unleashed_home_ok >/dev/null 2>&1 && command -v unleashed_plugin_legacy_base >/dev/null 2>&1; }; then\n')
    #: The attacker: the resolver and the primitive REDEFINED in the parent while `set -a` is still
    #: on, so bash exports them beside the four genuine names the earlier source already exported.
    ROW_170_ATTACKER = (
        'unleashed_resolve_base() { _UNLEASHED_BASE_RESOLVED=/attacker; _UNLEASHED_BASE_OK=1; '
        '_UNLEASHED_BASE_SOURCE=host-env; _UNLEASHED_POINTER_STATE=none; _UNLEASHED_BASE_PID=$$; '
        '_unleashed_resolved_in_process() { :; }; }; '
        'unleashed_plugin_base() { printf /attacker; }')

    def test_row_170_the_definition_block_is_unconditional_not_guarded_on_the_complete_api(self):
        """Row 170: a bash parent under `set -a` sources paths.sh (a genuine base in `CLAUDE_PLUGIN_DATA`, E0), then REDEFINES `unleashed_resolve_base` and `unleashed_plugin_base` to answer `/attacker` — all six API names are now exported — and `exec`s a child that sources paths.sh (and, separately, marker.sh) with the genuine base still in its environment: the specification prints the genuine base — the child's definitions are its own and the imported ones are replaced; under the mutation (the six-function guard restored around the block) the block is skipped, the EAGER call — outside the block in both builds — runs the INHERITED resolver, and the child prints `/attacker`. bash only: zsh's `set -a` exports no functions, so its child never holds the imported API (measured: `<b>` in both builds)."""
        # THE MECHANISM IS IN THE ORACLE: each cell prints the value the child INHERITED (the parent's
        # genuine resolution — `<b>`, made before the attacker was defined), then the primitive, then
        # `_UNLEASHED_BASE_RESOLVED` after sourcing. Measured, bash: spec `<b>|<b>|<b>` in both cells;
        # mutant `<b>|/attacker|/attacker` in both — the resolved value CHANGED inside the child, so
        # the inherited resolver RAN there, and it can only have run from paths.sh's eager call, which
        # sits outside the guarded region. marker.sh sources paths.sh unconditionally from its own
        # directory, so its cell runs against a shadow lib whose paths.sh is the mutant (row 156's
        # shape); with the variable set and E0 no cell touches the store or loads the machinery.
        b = os.path.join(self.home, "base-b")
        os.makedirs(b)
        mutant = self._guarded_paths(self.ROW_170_GUARD)
        try:
            machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
            fam = {"paths.sh": PATHS_C4, "marker.sh": os.path.join(LIBDIR, "marker.sh")}
            spec_root = self._shadow("spec170", dict(machinery, **fam))
            mut_root = self._shadow("mut170", dict(machinery, **dict(fam, **{"paths.sh": mutant})))
            for root, is_mutant in ((spec_root, False), (mut_root, True)):
                paths = os.path.join(root, "scripts", "lib", "paths.sh")
                marker = os.path.join(root, "scripts", "lib", "marker.sh")
                for cell, hook in (("paths.sh", f'. "{paths}"; printf "%s|%s" "$(unleashed_plugin_base)" '
                                                '"$_UNLEASHED_BASE_RESOLVED"'),
                                   ("marker.sh", f'. "{marker}"; printf "%s|%s" "$(marker_base)" '
                                                 '"$_UNLEASHED_BASE_RESOLVED"')):
                    self._wipe()
                    body = (f'set -a; export HOME="{self.home}" CLAUDE_PLUGIN_DATA="{b}" _UNLEASHED_PUBLISH_OK=0; '
                            f'. "{paths}"; {self.ROW_170_ATTACKER}; set +a; '
                            f'exec /bin/bash -c \'printf "%s|" "$_UNLEASHED_BASE_RESOLVED"; {hook}\'')
                    rc, out, err = self._row_166_cell("/bin/bash", body)
                    tag = f"{'mutant' if is_mutant else 'shipped'} {cell}"
                    self.assertEqual(0, rc, f"{tag}: rc {rc}: {err!r}")
                    self.assertNotIn("command not found", err, f"{tag}: {err!r}")
                    self.assertEqual([], self._diags(err), f"{tag}: a resolved base diagnosed: {err!r}")
                    self.assertFalse(os.path.exists(self.store), f"{tag}: E0 wrote a store")
                    self.assertTrue(out.startswith(f"{b}|"),
                                    f"{tag}: the child did not inherit the parent's genuine resolution — "
                                    f"the fixture is not the finding: {out!r}")
                    if not is_mutant:
                        self.assertEqual(f"{b}|{b}|{b}", out,
                                         f"{tag}: the child kept an imported definition or an imported "
                                         f"resolution: {out!r} {err!r}")
                    else:
                        self.assertEqual(f"{b}|/attacker|/attacker", out,
                                         f"{tag}: the CONTROL did not fail — under the restored complete-API "
                                         f"guard the child still defined its own resolver, or the eager call "
                                         f"did not run the inherited one: {out!r} {err!r}")
        finally:
            os.unlink(mutant)


    # ── row 171 ───────────────────────────────────────────────────────────────────────────────

    #: The step-(ii) "present now" clause of `_unleashed_create_store` — the block that decides whether
    #: a component present at (ii) was WALKED by (i) or APPEARED since. Head and tail are unique in the
    #: shipped file; the slice is asserted unique again by `_slice` and by with_mutation.
    ROW_171_HEAD = '            case "$_UNLEASHED_NEAREST" in\n'
    ROW_171_TAIL = '            esac\n'

    def test_row_171_a_component_present_at_step_ii_is_not_authenticated_by_being_present(self):
        """Row 171: `.claude` is ABSENT when E4 step (i) authenticates the nearest existing ancestor; a DEBUG trap plants it as a SYMLINK to an outside directory the instant (i) has completed and before (ii) reaches the component: the specification refuses (non-zero) with the outside directory EMPTY — the newly present component is authenticated with the no-follow chain predicate before anything is created beneath it; under the mutation (a present component is treated as already authenticated, `case … esac` → `:`) the next component `unleashed-mail` is created THROUGH the link inside the outside directory and only (iii) reports the failure. A normal creation (no trap) succeeds in both builds. Both shells."""
        # THE INTERLEAVING IS DETERMINISTIC, NOT RACED (rows 153/160's shape): the trap fires before
        # every simple command; its condition is satisfied for the first time before (ii)'s first
        # `[ -d "$_cs_d" ]` — `_cs_top` and `_UNLEASHED_NEAREST` are set, `_cs_d` is `.claude` (so (i)
        # has RETURNED, successfully: a refusing (i) never reaches the loop and the link is never
        # planted, which the WHERE= assertion would report), `.claude` still absent — so (i) walked
        # `<home>` (asserted: NEAREST == home) and (ii) finds `.claude` present, a symlink `-d` follows.
        # `set -T` in bash so the trap reaches into the function. Measured, both shells: spec rc=1,
        # `<outside>` empty, `.claude` the planted link, WHERE=<home>/.claude; mutant rc=1,
        # `<outside>/unleashed-mail` a 0700 directory — the refusal path itself created outside the
        # store. The oracle is the OUTSIDE directory, not the status: both builds return 1, the
        # mutant's from (iii) after the damage is done.
        old = self._slice(STORE, self.ROW_171_HEAD, self.ROW_171_TAIL)
        self.assertIn('"$_cs_d"|"$_cs_d"/*) : ;;', old)
        self.assertIn('*) _unleashed_auth_chain "$_cs_d" || return 1 ;;', old)
        self.assertEqual(4, len(old.splitlines()), old)
        mutant = with_mutation(old, '            :\n', path=STORE)
        outside = os.path.join(self.home, "outside")
        top = os.path.join(self.home, ".claude")
        leak = os.path.join(outside, "unleashed-mail")
        os.makedirs(outside, mode=0o700)
        os.chmod(outside, 0o700)

        def reset():
            if os.path.islink(top):
                os.unlink(top)
            self._wipe()
            for f in os.listdir(outside):
                shutil.rmtree(os.path.join(outside, f), ignore_errors=True)

        trapped = ('unset _cs_top _cs_d _UNLEASHED_NEAREST _t171_done _t171_where\n'
                   '[ -n "${BASH_VERSION:-}" ] && set -T\n'
                   'trap \'if [ -z "${_t171_done:-}" ] && [ -n "${_cs_top:-}" ] && [ -n "${_cs_d:-}" ] '
                   '&& [ -n "${_UNLEASHED_NEAREST:-}" ] && [ ! -e "$_cs_top" ]; then '
                   f'_t171_done=1; _t171_where="$_cs_d"; /bin/ln -s "{outside}" "$_cs_top"; fi\' DEBUG\n'
                   f'_unleashed_create_store "{self.store}"; _t171_rc=$?\n'
                   'trap - DEBUG\n'
                   'printf "RC=%s NEAREST=%s WHERE=%s" "$_t171_rc" "$_UNLEASHED_NEAREST" "$_t171_where"')
        normal = f'_unleashed_create_store "{self.store}"; printf "RC=%s" "$?"'
        try:
            for shell in SHELLS:
                for store_lib, is_mutant in ((STORE, False), (mutant, True)):
                    srcs = (AUTH, store_lib, READER, PUB)
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    reset()
                    rc, out, err = run_shell(shell, trapped, sources=srcs)
                    self.assertEqual(0, rc, f"{tag}: the fixture shell failed: {err!r}")
                    self.assertNotIn("command not found", err, f"{tag}: {err!r}")
                    # The fixture interleaved where the row says: (i) walked <home> with .claude
                    # absent, and the link is what (ii) then found.
                    self.assertEqual(f"RC=1 NEAREST={self.home} WHERE={top}", out,
                                     f"{tag}: E4 did not refuse, (i) did not walk the scratch home with "
                                     f".claude absent, or the link was not planted as (ii) reached `.claude` "
                                     f"— the fixture is not the finding: {out!r} {err!r}")
                    self.assertTrue(os.path.islink(top),
                                    f"{tag}: the trap never planted the link — the fixture did not interleave")
                    self.assertEqual(outside, os.readlink(top), f"{tag}: the link points elsewhere")
                    created = sorted(os.listdir(outside))
                    if not is_mutant:
                        self.assertEqual([], created,
                                         f"{tag}: the refusal path created OUTSIDE the store through the "
                                         f"planted link: {created}")
                    else:
                        self.assertTrue(os.path.isdir(leak) and not os.path.islink(leak),
                                        f"{tag}: the CONTROL did not fail — the mutant did not create "
                                        f"`unleashed-mail` through the link: {created}")
                        self.assertEqual(0o700, statmod.S_IMODE(os.stat(leak).st_mode),
                                        f"{tag}: not the store's mkdir -m 700 that made it")
                    # A normal creation succeeds in BOTH builds — the mutation removes a check, it
                    # does not break the store.
                    reset()
                    rc, out, err = run_shell(shell, normal, sources=srcs)
                    self.assertEqual(0, rc, f"{tag}: normal creation shell failed: {err!r}")
                    self.assertEqual("RC=0", out, f"{tag}: a normal creation did not succeed: {out!r} {err!r}")
                    self.assertTrue(os.path.isdir(self.store) and not os.path.islink(top),
                                    f"{tag}: the store was not created")
                    self.assertEqual(0o700, statmod.S_IMODE(os.stat(self.store).st_mode), f"{tag}: store mode")
                    self.assertEqual([], os.listdir(outside), f"{tag}: a normal creation wrote outside")
        finally:
            os.unlink(mutant)
            if os.path.islink(top):
                os.unlink(top)

    # ── row 172 ───────────────────────────────────────────────────────────────────────────────

    #: The attacker: `_unleashed_read_store` REDEFINED in the parent while `set -a` is still on, so bash
    #: exports it beside the four genuine machinery names the earlier source already exported. It answers
    #: `/attacker` — the value the child must never adopt.
    ROW_172_ATTACKER = ('_unleashed_read_store() { _UNLEASHED_BASE_RESOLVED=/attacker; _UNLEASHED_BASE_OK=1; '
                        '_UNLEASHED_BASE_SOURCE=pointer; _UNLEASHED_POINTER_STATE=none; }')
    #: The old presence-first early return, restored in front of the readable-source block of each loader.
    ROW_172_GUARD = ('if command -v _unleashed_key >/dev/null 2>&1 && command -v _unleashed_auth_chain >/dev/null 2>&1 \\\n'
                     '{ind}    && command -v _unleashed_read_store >/dev/null 2>&1 && command -v _unleashed_publish >/dev/null 2>&1; then\n'
                     '{ind}    return 0\n'
                     '{ind}fi\n')

    def _row_172_mutant(self, fam):
        """A copy of family file `fam` whose loader trusts PRESENT functions before re-sourcing the files:
        the old `if command -v … ; then return 0; fi` inserted immediately before the loader's
        `if [ "$_…_readable" = 1 ]; then` line — the shape every loader had until pass 14."""
        var = "_usm_readable" if fam == "paths.sh" else ("_ueb_readable" if fam == "agent-env-bridge.sh" else "_upb_readable")
        ind = "        " if fam == "paths.sh" else "    "
        anchor = f'{ind}if [ "${var}" = 1 ]; then\n'
        return with_mutation(anchor, ind + self.ROW_172_GUARD.format(ind=ind) + anchor, path=os.path.join(LIBDIR, fam))

    def test_row_172_the_machinery_is_re_sourced_not_trusted_because_it_is_present(self):
        """Row 172 (codex, PR #67 pass 14, finding — the loader kept an IMPORTED `_unleashed_read_store`): a bash parent under `set -a` sources a resolver copy (no `CLAUDE_PLUGIN_DATA`, no store — the machinery loads and every function is exported), then REDEFINES `_unleashed_read_store` to answer `/attacker` and `exec`s a child that sources the same copy: the specification RE-SOURCES the four machinery files beside the resolver whenever they are readable — the child prints the sentinel with `OK=0` (or, with a real base published, that base — never `/attacker`); under the mutation (the old presence-first `command -v … && return 0` restored ahead of the re-source) the child trusts the import and prints `/attacker` with `OK=1`. All five resolver copies, each where it is the resolver in force; the marker.sh-beside-paths.sh cell as the reproduction ran it; bash only (zsh's `set -a` exports no functions, so its child never holds the import — measured: the sentinel in both builds)."""
        # THE MUTANT MUST SIT BESIDE READABLE MACHINERY: the specification falls back to present functions
        # only when the files are NOT readable, so a mutant left in a bare temp dir would take that branch
        # in both builds and could not fail — which is exactly why the shadow-lib pattern (row 156's) is
        # required. paths.sh is exercised in a shadow with the machinery; the four family files in a
        # shadow WITHOUT paths.sh, so their own loader runs (row 156's shape); and marker.sh BESIDE the
        # (spec/mutant) paths.sh, which is the reproduction as it was run. Measured, bash, all cells:
        # spec `ok=1|<sentinel>` (`unleashed_base_ok` false → prints 1); mutant `ok=0|/attacker`.
        # The store cell: the parent PUBLISHES `<b>` (variable set, E4 creates the store), the attacker is
        # planted, the variable is unset, and the child reads the STORE — spec `<b>` (source `pointer`),
        # mutant `/attacker`. `_UNLEASHED_PUBLISH_OK=0` everywhere else, so no other cell writes a store.
        machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
        marker = os.path.join(LIBDIR, "marker.sh")
        b = os.path.join(self.home, "base-b")
        os.makedirs(b)
        os.chmod(b, 0o700)
        probe = 'unleashed_base_ok; printf "ok=%s|%s" "$?" "$_UNLEASHED_BASE_RESOLVED"'
        for fam in FAMILY_P7:
            mutant = self._row_172_mutant(fam)
            try:
                if fam == "paths.sh":
                    files = dict(machinery, **{"marker.sh": marker})
                else:
                    files = dict(machinery)                          # WITHOUT paths.sh: the copy's own loader runs
                spec_root = self._shadow(f"spec172-{fam}", dict(files, **{fam: os.path.join(LIBDIR, fam)}))
                mut_root = self._shadow(f"mut172-{fam}", dict(files, **{fam: mutant}))
                for root, is_mutant in ((spec_root, False), (mut_root, True)):
                    f = os.path.join(root, "scripts", "lib", fam)
                    src = f'. "{f}" "" "{root}"' if fam == "agent-env-bridge.sh" else f'. "{f}"'
                    cells = {"self": src}
                    if fam == "paths.sh":
                        cells["marker.sh beside paths.sh"] = f'. "{os.path.join(root, "scripts", "lib", "marker.sh")}"'
                    for cell, child_src in cells.items():
                        self._wipe()
                        body = (f'set -a; export HOME="{self.home}" _UNLEASHED_PUBLISH_OK=0; unset CLAUDE_PLUGIN_DATA; '
                                f'{src}; {self.ROW_172_ATTACKER}; set +a; '
                                f"exec /bin/bash -c '{child_src}; {probe}'")
                        rc, out, err = self._row_166_cell("/bin/bash", body)
                        tag = f"{fam} {'mutant' if is_mutant else 'shipped'} [{cell}]"
                        self.assertEqual(0, rc, f"{tag}: rc {rc}: {err!r}")
                        self.assertNotIn("command not found", err, f"{tag}: {err!r}")
                        self.assertFalse(os.path.exists(self.store), f"{tag}: E0 wrote a store")
                        if not is_mutant:
                            self.assertEqual(f"ok=1|{SENTINEL}", out,
                                             f"{tag}: the child adopted an IMPORTED reader's answer — the "
                                             f"present machinery was trusted instead of re-sourced: {out!r} {err!r}")
                        else:
                            self.assertEqual("ok=0|/attacker", out,
                                             f"{tag}: the CONTROL did not fail — under the restored presence-first "
                                             f"guard the child still re-sourced the machinery: {out!r} {err!r}")
                    # The store cell — paths.sh only: a REAL base published by the parent must come back from
                    # the store in the child, never the import's answer.
                    if fam == "paths.sh":
                        self._wipe()
                        body = (f'set -a; export HOME="{self.home}" CLAUDE_PLUGIN_DATA="{b}"; '
                                f'{src}; printf "%s|" "$_UNLEASHED_POINTER_STATE"; {self.ROW_172_ATTACKER}; '
                                f'unset CLAUDE_PLUGIN_DATA; set +a; '
                                f"exec /bin/bash -c '{src}; {probe}; printf \"|%s\" \"$_UNLEASHED_BASE_SOURCE\"'")
                        rc, out, err = self._row_166_cell("/bin/bash", body)
                        tag = f"{fam} {'mutant' if is_mutant else 'shipped'} [store]"
                        self.assertEqual(0, rc, f"{tag}: rc {rc}: {err!r}")
                        self.assertNotIn("command not found", err, f"{tag}: {err!r}")
                        self.assertTrue(out.startswith("created|"),
                                        f"{tag}: the parent did not publish `<b>` — the fixture is not the finding: {out!r} {err!r}")
                        if not is_mutant:
                            self.assertEqual(f"created|ok=0|{b}|pointer", out,
                                             f"{tag}: the child did not read the published base back from the store: {out!r} {err!r}")
                        else:
                            self.assertEqual("created|ok=0|/attacker|pointer", out,
                                             f"{tag}: the CONTROL did not fail — the child did not adopt the import: {out!r} {err!r}")
            finally:
                os.unlink(mutant)
        # zsh does not export functions under `set -a`: the import never reaches the child, and BOTH builds
        # print the sentinel — asserted, so the bash-only claim above is measured rather than assumed.
        mutant = self._row_172_mutant("paths.sh")
        try:
            spec_root = self._shadow("spec172-zsh", dict(machinery, **{"paths.sh": PATHS_C4}))
            mut_root = self._shadow("mut172-zsh", dict(machinery, **{"paths.sh": mutant}))
            for root, is_mutant in ((spec_root, False), (mut_root, True)):
                f = os.path.join(root, "scripts", "lib", "paths.sh")
                self._wipe()
                body = (f'set -a; export HOME="{self.home}" _UNLEASHED_PUBLISH_OK=0; unset CLAUDE_PLUGIN_DATA; '
                        f'. "{f}"; {self.ROW_172_ATTACKER}; set +a; '
                        f"exec /bin/zsh -c '. \"{f}\"; {probe}'")
                rc, out, err = self._row_166_cell("/bin/zsh", body)
                self.assertEqual((0, f"ok=1|{SENTINEL}"), (rc, out),
                                 f"zsh {'mutant' if is_mutant else 'shipped'}: the zsh child held the import — "
                                 f"the bash-only claim is wrong: {out!r} {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 173 ───────────────────────────────────────────────────────────────────────────────

    #: The instance stamp as shipped (pass 14) — set once, only when absent, global under zsh — in the
    #: two files the row's mutant reverts; `{ind}` is the file's indentation. The old stamp was one line.
    ROW_173_STAMP = ('{ind}if [ -z "${{_UNLEASHED_BASE_INSTANCE+set}}" ]; then\n'
                     '{ind}    if [ -n "${{ZSH_VERSION:-}}" ]; then typeset -g -r _UNLEASHED_BASE_INSTANCE=1 2>/dev/null; '
                     'else readonly _UNLEASHED_BASE_INSTANCE=1 2>/dev/null; fi\n'
                     '{ind}fi\n')
    ROW_173_OLD = '{ind}readonly _UNLEASHED_BASE_INSTANCE=1 2>/dev/null\n'

    def _row_173_mutant(self, fam):
        ind = "        " if fam == "paths.sh" else "    "
        return with_mutation(self.ROW_173_STAMP.format(ind=ind), self.ROW_173_OLD.format(ind=ind),
                             path=os.path.join(LIBDIR, fam))

    def test_row_173_the_instance_stamp_is_set_once_errexit_safe_and_global_under_zsh(self):
        """Row 173 (codex, PR #67 pass 14, finding — the readonly stamp re-applied under `set -e`, and function-local under zsh): (i) `set -e; . paths.sh` (base A) then `. agent-env-bridge.sh <B> <root>` — the bridge re-resolves an already-stamped instance — the specification's sourcing shell SURVIVES and holds `<B>` in both shells; under the mutation (the stamp restored to the bare `readonly _UNLEASHED_BASE_INSTANCE=1 2>/dev/null` in paths.sh and the bridge) bash treats the second `readonly` as a FATAL assignment error and the shell EXITS non-zero, while zsh survives — because there (ii) the resolver's stamp was FUNCTION-LOCAL: after `. paths.sh` alone, `typeset -p _UNLEASHED_BASE_INSTANCE` shows the global `-r` attribute in the specification and `no such variable` under the mutant; (iv) the bridge sourced alone TWICE with differing values (its stamp is at file top level, so it was global in zsh already) EXITS the errexit shell under the mutant in BOTH shells and survives in the specification. (iii) The instance check the stamp serves still holds in both builds: a `set -a` wrapper's exec'd bash child sees `declare -x` (value inherited without the attribute) and, after `. paths.sh`, `declare -r`."""
        # Measured: (i) bash spec rc 0 `SURVIVED <b>`, mutant rc 1 with EMPTY output; zsh rc 0 `SURVIVED <b>`
        # in both builds. (ii) zsh spec `typeset -r _UNLEASHED_BASE_INSTANCE=1`, mutant `no such variable`
        # (rc 1); bash `declare -r …` in both. (iii) `declare -x` then `declare -r` in both builds. (iv) spec
        # rc 0 `SURVIVED <b>` in both shells; mutant rc 1, empty, in both. Both mutant files sit in ONE
        # shadow lib beside the shipped machinery and family (row 92's shape), and every cell runs with a
        # protocol-clean environment (`_row_166_cell`) so nothing inherited stands in for the stamp.
        a = os.path.join(self.home, "base-a"); b = os.path.join(self.home, "base-b")
        os.makedirs(a); os.makedirs(b)
        m_paths = self._row_173_mutant("paths.sh")
        m_bridge = self._row_173_mutant("agent-env-bridge.sh")
        try:
            everything = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7 + FAMILY_P7}
            spec_root = self._shadow("spec173", everything)
            mut_root = self._shadow("mut173", dict(everything, **{"paths.sh": m_paths, "agent-env-bridge.sh": m_bridge}))
            # The bridge ALONE (paths.sh absent) — the fifth resolver copy in force, its own top-level stamp.
            spec_alone = self._shadow("spec173-alone", dict(everything, **{"agent-env-bridge.sh": os.path.join(LIBDIR, "agent-env-bridge.sh")}))
            mut_alone = self._shadow("mut173-alone", dict(everything, **{"agent-env-bridge.sh": m_bridge}))
            for r in (spec_alone, mut_alone):
                os.unlink(os.path.join(r, "scripts", "lib", "paths.sh"))
            env = f'export HOME="{self.home}" CLAUDE_PLUGIN_DATA="{a}" _UNLEASHED_PUBLISH_OK=0'
            for root, alone, is_mutant in ((spec_root, spec_alone, False), (mut_root, mut_alone, True)):
                paths = os.path.join(root, "scripts", "lib", "paths.sh")
                bridge = os.path.join(root, "scripts", "lib", "agent-env-bridge.sh")
                bridge_alone = os.path.join(alone, "scripts", "lib", "agent-env-bridge.sh")
                tag0 = "mutant" if is_mutant else "shipped"
                for shell in SHELLS:
                    bash = shell.endswith("bash")
                    # (i) errexit sourcer: paths.sh (A) then the bridge (B) — a re-resolution of a stamped instance.
                    self._wipe()
                    rc, out, err = self._row_166_cell(shell, f'set -e; {env}; . "{paths}"; . "{bridge}" "{b}" "{root}"; '
                                                             f'printf "SURVIVED %s" "$_UNLEASHED_BASE_RESOLVED"')
                    tag = f"{tag0} {shell} (i)"
                    if not is_mutant or not bash:
                        self.assertEqual((0, f"SURVIVED {b}"), (rc, out),
                                         f"{tag}: the errexit sourcing shell did not survive the bridge's "
                                         f"re-resolution, or did not hold <b>: {rc} {out!r} {err!r}")
                    else:
                        self.assertNotEqual(0, rc, f"{tag}: the CONTROL did not fail — bash survived a second "
                                                   f"bare `readonly` under set -e: {out!r} {err!r}")
                        self.assertEqual("", out, f"{tag}: the shell reached its next statement: {out!r}")
                    # (iv) the bridge alone, twice, with differing values — its own top-level stamp re-applied.
                    self._wipe()
                    rc, out, err = self._row_166_cell(shell, f'set -e; export HOME="{self.home}"; . "{bridge_alone}" "{a}" "{alone}"; '
                                                             f'. "{bridge_alone}" "{b}" "{alone}"; printf "SURVIVED %s" "$_UNLEASHED_BASE_RESOLVED"')
                    tag = f"{tag0} {shell} (iv)"
                    if not is_mutant:
                        self.assertEqual((0, f"SURVIVED {b}"), (rc, out), f"{tag}: {rc} {out!r} {err!r}")
                    else:
                        self.assertNotEqual(0, rc, f"{tag}: the CONTROL did not fail — the bridge's second bare "
                                                   f"`readonly` did not exit the errexit shell: {out!r} {err!r}")
                        self.assertEqual("", out, f"{tag}: the shell reached its next statement: {out!r}")
                    # (ii) after paths.sh alone, the stamp is a GLOBAL readonly (zsh: `typeset -p` shows -r).
                    self._wipe()
                    show = "declare -p" if bash else "typeset -p"
                    rc, out, err = self._row_166_cell(shell, f'{env}; . "{paths}"; {show} _UNLEASHED_BASE_INSTANCE')
                    tag = f"{tag0} {shell} (ii)"
                    if bash or not is_mutant:
                        self.assertEqual(0, rc, f"{tag}: {out!r} {err!r}")
                        self.assertRegex(out, r"^(declare|typeset) -[a-z]*r[a-z]* _UNLEASHED_BASE_INSTANCE=",
                                         f"{tag}: the stamp is not a global readonly after sourcing: {out!r}")
                    else:
                        self.assertNotEqual(0, rc, f"{tag}: the CONTROL did not fail — zsh holds a global "
                                                   f"stamp under the function-local `readonly`: {out!r}")
                        self.assertIn("no such variable", err, f"{tag}: {err!r}")
                # (iii) bash: the readonly attribute does not cross exec — the child sees `-x`, then `-r` after sourcing.
                self._wipe()
                rc, out, err = self._row_166_cell("/bin/bash", f'set -a; {env}; . "{paths}"; set +a; '
                                                               f"exec /bin/bash -c 'declare -p _UNLEASHED_BASE_INSTANCE; "
                                                               f'. "{paths}"; declare -p _UNLEASHED_BASE_INSTANCE\'')
                tag = f"{tag0} bash (iii)"
                self.assertEqual(0, rc, f"{tag}: {out!r} {err!r}")
                lines = out.splitlines()
                self.assertEqual(2, len(lines), f"{tag}: {out!r}")
                self.assertRegex(lines[0], r'^declare -x _UNLEASHED_BASE_INSTANCE="1"$',
                                 f"{tag}: the exec'd child inherited the ATTRIBUTE, or not the value: {lines[0]!r}")
                self.assertRegex(lines[1], r'^declare -r _UNLEASHED_BASE_INSTANCE="1"$',
                                 f"{tag}: sourcing in the child did not stamp its own instance: {lines[1]!r}")
        finally:
            os.unlink(m_paths); os.unlink(m_bridge)

    # ── row 174 ───────────────────────────────────────────────────────────────────────────────

    #: The library directory each resolver copy derives, and the indentation of the block that derives
    #: it. agent-env-bridge.sh is NOT here: it takes the plugin root as a positional argument and
    #: derives no directory of its own.
    ROW_174_FILES = (("paths.sh", "_UNLEASHED_LIB_DIR", "    "),
                     ("marker.sh", "_upb_d", ""),
                     ("log.sh", "_upb_d", ""),
                     ("context.sh", "_UNLEASHED_CONTEXT_LIB_DIR", ""))
    #: The PATH-resolved one-liner every copy carried until pass 14 — `dirname` is an EXTERNAL command.
    ROW_174_OLD = '{ind}{v}="$(cd "$(dirname "${{BASH_SOURCE[0]:-$0}}")" 2>/dev/null && pwd)" || {v}="."\n'
    #: The parent supplies a tampered machinery namespace under `set -a` AND the PATH it is found on.
    ROW_174_ATTACKER = ('_unleashed_key() { :; }; _unleashed_auth_chain() { :; }; _unleashed_publish() { :; }; '
                        '_unleashed_read_store() { _UNLEASHED_BASE_RESOLVED=/attacker; _UNLEASHED_BASE_OK=1; '
                        '_UNLEASHED_BASE_SOURCE=pointer; _UNLEASHED_POINTER_STATE=none; }')

    def _row_174_mutant(self, fam, var, ind):
        """A copy of `fam` whose lib-directory derivation is the PATH-resolved `dirname` one-liner."""
        src = os.path.join(LIBDIR, fam)
        old = self._slice(src, f'{ind}{var}="${{BASH_SOURCE[0]:-$0}}"\n',
                          f'{ind}[ -n "${var}" ] || {var}="."\n')
        self.assertIn("cd -P", old, old)                 # the shipped derivation is a BUILTIN cd …
        self.assertNotIn("dirname", old, old)            # … and consults no external command at all
        return with_mutation(old, self.ROW_174_OLD.format(ind=ind, v=var), path=src)

    def test_row_174_the_library_directory_is_not_derived_through_path(self):
        """Row 174 (codex sweep, PR #67 pass 14, finding — the lib directory came from `dirname`, and PATH decides where `dirname` is): a bash parent under `set -a` exports a tampered `_unleashed_read_store` answering `/attacker`, drops `/usr/bin` from PATH and `exec`s a child that sources a resolver copy sitting BESIDE the four machinery files: the specification derives the directory by parameter expansion and builtin `cd -P`/`pwd -P`, finds the machinery beside itself, RE-SOURCES it, and answers the sentinel (`ok=1`); under the mutation (the `dirname` one-liner restored) `dirname` is not found, the directory falls back to the caller's CWD, the four libraries "are not readable" although they sit right beside the file, the loader's presence fallback trusts the import, and the child answers `/attacker` (`ok=0`) with `dirname: command not found` on stderr. All four deriving copies. And the honest control, BOTH shells: with a normal PATH and no shadow, a genuine `CLAUDE_PLUGIN_DATA` still resolves through every copy."""
        # Measured, all four files: shipped `ok=1|<sentinel>` with ONE diagnostic and no `command not
        # found`; mutant `ok=0|/attacker`, no diagnostic, `dirname: command not found` on stderr. The CWD
        # is a scratch directory holding no libraries — that is what the mutant's fallback resolves to,
        # and it is set explicitly rather than inherited from the test runner. `_UNLEASHED_PUBLISH_OK=0`
        # (E0) and no store, so no cell writes one.
        cwd = os.path.join(self.home, "cwd174")
        os.makedirs(cwd)
        probe = 'unleashed_base_ok; printf "ok=%s|%s" "$?" "$_UNLEASHED_BASE_RESOLVED"'
        machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
        for fam, var, ind in self.ROW_174_FILES:
            mutant = self._row_174_mutant(fam, var, ind)
            try:
                # The shadow holds the four machinery files and NOTHING else besides the copy under test,
                # so each copy's own derivation and loader are the ones in force (row 156's shape): with
                # paths.sh beside a family file, paths.sh would resolve first and the family copy's
                # derivation would be unreachable — a mutant there could not fail.
                spec_root = self._shadow(f"spec174-{fam}", dict(machinery, **{fam: os.path.join(LIBDIR, fam)}))
                mut_root = self._shadow(f"mut174-{fam}", dict(machinery, **{fam: mutant}))
                for root, is_mutant in ((spec_root, False), (mut_root, True)):
                    f = os.path.join(root, "scripts", "lib", fam)
                    self._wipe()
                    body = (f'cd "{cwd}" || exit 9; set -a; export HOME="{self.home}" _UNLEASHED_PUBLISH_OK=0; '
                            f'unset CLAUDE_PLUGIN_DATA; {self.ROW_174_ATTACKER}; set +a; '
                            f"PATH=/bin exec /bin/bash -c '. \"{f}\"; {probe}'")
                    rc, out, err = self._row_166_cell("/bin/bash", body)
                    tag = f"{fam} {'mutant' if is_mutant else 'shipped'}"
                    self.assertEqual(0, rc, f"{tag}: rc {rc}: {out!r} {err!r}")
                    self.assertFalse(os.path.exists(self.store), f"{tag}: E0 wrote a store")
                    if not is_mutant:
                        self.assertEqual(f"ok=1|{SENTINEL}", out,
                                         f"{tag}: the child adopted the IMPORTED reader's answer — the "
                                         f"libraries beside it were not found: {out!r} {err!r}")
                        self.assertNotIn("command not found", err, f"{tag}: {err!r}")
                        self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
                    else:
                        self.assertEqual("ok=0|/attacker", out,
                                         f"{tag}: the CONTROL did not fail — with `/usr/bin` off PATH the "
                                         f"`dirname` derivation still found the libraries: {out!r} {err!r}")
                        self.assertIn("dirname", err,
                                      f"{tag}: `dirname` was found after all — the fixture is not the "
                                      f"finding: {err!r}")
                        self.assertEqual([], self._diags(err), f"{tag}: {err!r}")
            finally:
                os.unlink(mutant)
        # THE HONEST CONTROL, both shells: nothing above is bought at the price of the normal case — the
        # shipped derivation still finds the libraries beside every copy, from a foreign CWD, and a
        # genuine `CLAUDE_PLUGIN_DATA` resolves through all four.
        b = os.path.join(self.home, "base-174")
        os.makedirs(b)
        os.chmod(b, 0o700)
        for fam, _, _ in self.ROW_174_FILES:
            for shell in SHELLS:
                self._wipe()
                rc, out, err = self._row_166_cell(
                    shell, f'cd "{cwd}" || exit 9; export HOME="{self.home}" CLAUDE_PLUGIN_DATA="{b}" '
                           f'_UNLEASHED_PUBLISH_OK=0; . "{os.path.join(LIBDIR, fam)}"; {probe}')
                self.assertEqual((0, f"ok=0|{b}"), (rc, out),
                                 f"{fam} {shell}: the shipped derivation did not resolve a genuine base "
                                 f"from a foreign cwd: {rc} {out!r} {err!r}")

    # ── row 175 ───────────────────────────────────────────────────────────────────────────────

    #: The discard branch of the instance check, `|| :` on BOTH unsets (pass 14); the mutant drops them.
    #: zsh's `unset -f` returns 1 for a function that is not defined — and in a shell that has just
    #: inherited the stamp through the environment, that function is exactly what is NOT defined.
    ROW_175_LINE = ('        *)  unset -f _unleashed_resolved_in_process 2>/dev/null || :; _UNLEASHED_BASE_PID=; '
                    'unset _UNLEASHED_BASE_INSTANCE 2>/dev/null || : ;;\n')
    ROW_175_OLD = ('        *)  unset -f _unleashed_resolved_in_process 2>/dev/null; _UNLEASHED_BASE_PID=; '
                   'unset _UNLEASHED_BASE_INSTANCE 2>/dev/null ;;\n')

    def test_row_175_sourcing_survives_errexit_when_the_stamp_arrives_through_the_environment(self):
        """Row 175 (codex sweep, PR #67 pass 14, finding — `unset -f` on an undefined function returns 1 in zsh): a shell with `set -e` and `_UNLEASHED_BASE_INSTANCE=1` in its ENVIRONMENT (a value without the attribute — the inherited shape the check exists to discard) sources each of the five resolver copies: the specification's shell SURVIVES and holds the genuine base in both shells; under the mutation (the `|| :` dropped from both unsets in the discard branch) the ZSH shell dies at the `unset -f` — rc non-zero, nothing sourced, no base — while bash is unaffected (its `unset -f` returns 0), which is asserted rather than claimed. Under `setopt err_return` the zsh mutant returns out of the sourced file instead of exiting: the shell survives with the base UNSET, which is the same defect in its second spelling."""
        # Measured, all five copies: (i) `set -e` — spec rc 0 `SURVIVED <b>` in both shells; mutant zsh
        # rc 1 with EMPTY output, bash rc 0 `SURVIVED <b>` (no discrimination, asserted). (ii) zsh
        # `setopt err_return` — spec `SURVIVED <b>`; mutant rc 0 but `SURVIVED ` with an empty base.
        b = os.path.join(self.home, "base-175")
        os.makedirs(b)
        os.chmod(b, 0o700)
        everything = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7 + FAMILY_P7}
        spec_root = self._shadow("spec175", everything)
        show = 'printf "SURVIVED %s" "$_UNLEASHED_BASE_RESOLVED"'
        for fam in FAMILY_P7:
            mutant = with_mutation(self.ROW_175_LINE, self.ROW_175_OLD, path=os.path.join(LIBDIR, fam))
            try:
                mut_root = self._shadow(f"mut175-{fam}", dict(everything, **{fam: mutant}))
                for root, is_mutant in ((spec_root, False), (mut_root, True)):
                    f = os.path.join(root, "scripts", "lib", fam)
                    src = (f'. "{f}" "{b}" "{root}"' if fam == "agent-env-bridge.sh" else f'. "{f}"')
                    env = (f'export HOME="{self.home}" _UNLEASHED_PUBLISH_OK=0 _UNLEASHED_BASE_INSTANCE=1; '
                           + ('unset CLAUDE_PLUGIN_DATA; ' if fam == "agent-env-bridge.sh"
                              else f'export CLAUDE_PLUGIN_DATA="{b}"; '))
                    for shell in SHELLS:
                        bash = shell.endswith("bash")
                        self._wipe()
                        rc, out, err = self._row_166_cell(shell, f'set -e; {env}{src}; {show}')
                        tag = f"{fam} {shell} {'mutant' if is_mutant else 'shipped'} (set -e)"
                        if not is_mutant or bash:
                            self.assertEqual((0, f"SURVIVED {b}"), (rc, out),
                                             f"{tag}: the errexit sourcing shell did not survive an "
                                             f"inherited stamp, or did not resolve: {rc} {out!r} {err!r}")
                        else:
                            self.assertNotEqual(0, rc, f"{tag}: the CONTROL did not fail — zsh survived "
                                                       f"`unset -f` on an undefined function: {out!r} {err!r}")
                            self.assertEqual("", out, f"{tag}: the shell reached its next statement: {out!r}")
                    # (ii) zsh `setopt err_return`: the mutant RETURNS out of the sourced file — the shell
                    # lives, the base does not.
                    self._wipe()
                    rc, out, err = self._row_166_cell("/bin/zsh", f'setopt err_return; {env}{src}; {show}')
                    tag = f"{fam} zsh {'mutant' if is_mutant else 'shipped'} (err_return)"
                    if not is_mutant:
                        self.assertEqual((0, f"SURVIVED {b}"), (rc, out), f"{tag}: {rc} {out!r} {err!r}")
                    else:
                        self.assertEqual("SURVIVED ", out,
                                         f"{tag}: the CONTROL did not fail — the sourcing completed and "
                                         f"the base was resolved anyway: {rc} {out!r} {err!r}")
            finally:
                os.unlink(mutant)

    # ── row 176 ───────────────────────────────────────────────────────────────────────────────

    #: The readonly-attribute test as shipped — the FLAG LETTERS only, everything from the first
    #: ` _UNLEASHED_BASE_INSTANCE` dropped before the match; the mutant restores the whole-line patterns.
    ROW_176_SHIPPED = ('    _ubi_decl="$( { declare -p _UNLEASHED_BASE_INSTANCE 2>/dev/null || typeset -p _UNLEASHED_BASE_INSTANCE 2>/dev/null; } )"\n'
                       '    case "${_ubi_decl%% _UNLEASHED_BASE_INSTANCE*}" in\n'
                       '        "declare -"*r*|"typeset -"*r*|"export -"*r*|readonly) : ;;\n')
    ROW_176_OLD = ('    case "$( { declare -p _UNLEASHED_BASE_INSTANCE 2>/dev/null || typeset -p _UNLEASHED_BASE_INSTANCE 2>/dev/null; } )" in\n'
                   '        "declare -"*r*" _UNLEASHED_BASE_INSTANCE="*|"typeset -"*r*" _UNLEASHED_BASE_INSTANCE="*|"export -"*r*" _UNLEASHED_BASE_INSTANCE="*|"readonly "*) : ;;\n')
    #: The crafted VALUE that supplies both the `r` and the name to a whole-line match, beside a complete
    #: inherited resolution: `exec` preserves `$$`, and bash `set -a` carries the marker function across.
    ROW_176_CRAFTED = "r _UNLEASHED_BASE_INSTANCE="

    def test_row_176_the_readonly_attribute_test_reads_the_flag_letters_only(self):
        """Row 176 (codex sweep, PR #67 pass 14, finding — the attribute test globbed the whole `declare -p` line, and the VALUE is attacker-supplied): a bash parent under `set -a` publishes a complete inherited resolution — `_UNLEASHED_BASE_RESOLVED=/attacker`, `_UNLEASHED_BASE_PID=$$`, the marker function — and sets `_UNLEASHED_BASE_INSTANCE='r _UNLEASHED_BASE_INSTANCE='`, then `exec`s a child that sources a resolver copy: the specification strips everything from the first ` _UNLEASHED_BASE_INSTANCE` before matching, sees `declare -x`, DISCARDS the inherited resolution and re-resolves from the environment (`<b>`); under the mutation (the whole-line patterns restored) the crafted value supplies the `r` and the name, the attribute-less inherited value passes as READONLY, the pid + marker guard is satisfied across `exec`, and the child keeps `/attacker`. All four exec'd resolver copies; bash only, and the zsh half is asserted non-discriminating (its `set -a` exports no functions). The honest control: a GENUINE in-process stamp is still honoured — paths.sh, then marker.sh, then log.sh in one shell with `CLAUDE_PLUGIN_DATA` changed in between resolves ONCE, and the stamp carries the `-r` attribute, in both shells and both builds."""
        # Measured, all four files: bash spec `<b>`, mutant `/attacker`; zsh `<b>` in both builds.
        # The honest control: `<a>|declare -r` (bash) / `<a>|typeset -r` (zsh) in both builds — the base
        # did NOT follow `CLAUDE_PLUGIN_DATA` to `<b>`, which is what "resolved once" means here.
        a = os.path.join(self.home, "base-176a")
        b = os.path.join(self.home, "base-176b")
        os.makedirs(a); os.makedirs(b)
        os.chmod(a, 0o700); os.chmod(b, 0o700)
        machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
        for fam, prim in self.ROW_166:
            mutant = with_mutation(self.ROW_176_SHIPPED, self.ROW_176_OLD, path=os.path.join(LIBDIR, fam))
            try:
                spec_root = self._shadow(f"spec176-{fam}", dict(machinery, **{fam: os.path.join(LIBDIR, fam)}))
                mut_root = self._shadow(f"mut176-{fam}", dict(machinery, **{fam: mutant}))
                for root, is_mutant in ((spec_root, False), (mut_root, True)):
                    f = os.path.join(root, "scripts", "lib", fam)
                    for shell in SHELLS:
                        self._wipe()
                        body = (f'set -a; export HOME="{self.home}" _UNLEASHED_PUBLISH_OK=0 '
                                f'CLAUDE_PLUGIN_DATA="{b}"; _unleashed_resolved_in_process() {{ :; }}; '
                                f'export _UNLEASHED_BASE_RESOLVED=/attacker _UNLEASHED_BASE_OK=1 '
                                f'_UNLEASHED_BASE_SOURCE=host-env _UNLEASHED_POINTER_STATE=none '
                                f'_UNLEASHED_BASE_PID=$$ '
                                f'_UNLEASHED_BASE_INSTANCE="{self.ROW_176_CRAFTED}"; set +a; '
                                f"exec {shell} -c '. \"{f}\"; printf %s \"$({prim})\"'")
                        rc, out, err = self._row_166_cell(shell, body)
                        tag = f"{fam} {shell} {'mutant' if is_mutant else 'shipped'}"
                        self.assertEqual(0, rc, f"{tag}: rc {rc}: {out!r} {err!r}")
                        self.assertFalse(os.path.exists(self.store), f"{tag}: E0 wrote a store")
                        if not is_mutant or shell.endswith("zsh"):
                            self.assertEqual(b, out,
                                             f"{tag}: the crafted VALUE passed the attribute test and the "
                                             f"inherited resolution was kept: {out!r} {err!r}")
                        else:
                            self.assertEqual("/attacker", out,
                                             f"{tag}: the CONTROL did not fail — under the whole-line "
                                             f"patterns the crafted value did not pass as readonly: "
                                             f"{out!r} {err!r}")
                # THE HONEST CONTROL — a genuine in-process stamp is still honoured. Runs against BOTH
                # builds and does not discriminate (a real `declare -r` matches either pattern); its job
                # is to prove the fix did not turn every legitimate second sourcing into a re-resolution.
                for root, is_mutant in ((spec_root, False), (mut_root, True)):
                    if fam != "paths.sh":
                        continue                     # the three-file chain is paths.sh -> marker.sh -> log.sh
                    paths = os.path.join(root, "scripts", "lib", "paths.sh")
                    for shell in SHELLS:
                        self._wipe()
                        show = "declare -p" if shell.endswith("bash") else "typeset -p"
                        rc, out, err = self._row_166_cell(
                            shell, f'export HOME="{self.home}" CLAUDE_PLUGIN_DATA="{a}" _UNLEASHED_PUBLISH_OK=0; '
                                   f'. "{paths}"; export CLAUDE_PLUGIN_DATA="{b}"; '
                                   f'. "{os.path.join(LIBDIR, "marker.sh")}"; . "{os.path.join(LIBDIR, "log.sh")}"; '
                                   f'printf "%s|" "$_UNLEASHED_BASE_RESOLVED"; {show} _UNLEASHED_BASE_INSTANCE')
                        tag = f"honest {shell} {'mutant' if is_mutant else 'shipped'}"
                        self.assertEqual(0, rc, f"{tag}: rc {rc}: {out!r} {err!r}")
                        self.assertTrue(out.startswith(f"{a}|"),
                                        f"{tag}: the genuine in-process stamp was discarded and the base "
                                        f"re-resolved to the NEW environment value: {out!r} {err!r}")
                        self.assertRegex(out.split("|", 1)[1],
                                         r"^(declare|typeset) -[a-z]*r[a-z]* _UNLEASHED_BASE_INSTANCE=",
                                         f"{tag}: the stamp does not carry the readonly attribute: {out!r}")
            finally:
                os.unlink(mutant)

    # ── row 177 ───────────────────────────────────────────────────────────────────────────────

    #: The ownership test as shipped — the euid through the `_u_euid` accessor and its probe seam; the
    #: mutant restores `$EUID`, which bash 3.2 IMPORTS from the environment as an ordinary variable.
    ROW_177_SHIPPED = '            { _u_euid && [ "$_U_UID" = "$_U_EUID" ]; } || return 1\n'
    ROW_177_OLD = '            [ "$_U_UID" = "${EUID:-$(/usr/bin/id -u)}" ] || return 1\n'

    def test_row_177_the_effective_uid_is_probed_never_read_from_euid(self):
        """Row 177 (codex sweep, PR #67 pass 14, finding — bash 3.2, the `/bin/bash` a macOS hook runs, imports `$EUID` from the environment): with `env EUID=4242` a full publish + read cycle still resolves and publishes under the specification, which probes `/usr/bin/id -u` through `_u_euid_probe`; under the mutation (`${EUID:-$(/usr/bin/id -u)}` restored at the chain's ownership test) the bash cycle fails closed on a PERFECTLY HEALTHY store — publish `failed`, nothing read — because the parent decided the answer to every ownership test. zsh sets its own `EUID` and is unaffected, which is asserted rather than claimed. Three further cells on the SHIPPED build: without `EUID` the two builds are identical (the mutation is inert until the environment is tampered with); a fixture that makes `_u_euid_probe` FAIL refuses the chain (fail-closed, both shells); and a caller-preset `_U_EUID`/`_U_EUID_PROBED` is NOT honoured — `_u_probes_reset` clears the flag at the entry points, so the cache cannot be seeded from outside."""
        # Measured: `EUID=4242` bash — spec `pub=created|1 pointer none`, no diagnostic; mutant
        # `pub=failed|0 unresolved none`, two diagnostics. `EUID=4242` zsh — `pub=created|1 pointer none`
        # in BOTH builds (no discrimination). No `EUID` — `pub=created|1 pointer none` in both builds,
        # both shells. Probe seam failing — `pub=failed`, both shells. Caller-preset cache — `pub=created`.
        self.assertEqual("4242", subprocess.run(["env", "EUID=4242", "/bin/bash", "-c", "echo $EUID"],
                                                capture_output=True, text=True).stdout.strip(),
                         "this bash does not import EUID from the environment — the fixture is not the finding")
        mutant = with_mutation(self.ROW_177_SHIPPED, self.ROW_177_OLD, path=AUTH)
        cycle = (f'_unleashed_publish "{self.store}" "{self.target}"\n'
                 'printf "pub=%s|" "$_UNLEASHED_POINTER_STATE"\n'
                 'unset _UNLEASHED_BASE_OK _UNLEASHED_BASE_SOURCE _UNLEASHED_POINTER_STATE '
                 '_UNLEASHED_BASE_DIAGNOSED _U_PRINCIPAL\n'
                 f'_unleashed_read_store "{self.store}"\n' + self.OUTP)
        try:
            for shell in SHELLS:
                bash = shell.endswith("bash")
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((mutant, STORE, READER, PUB), True)):
                    for tampered in (True, False):
                        self._wipe()
                        env = {"HOME": self.home}
                        if tampered:
                            env["EUID"] = "4242"
                        rc, out, err = run_shell(shell, cycle, sources=srcs, env=env)
                        tag = (f"{shell} {'mutant' if is_mutant else 'shipped'} "
                               f"{'EUID=4242' if tampered else 'no EUID'}")
                        if is_mutant and tampered and bash:
                            self.assertEqual("pub=failed|0 unresolved none", out,
                                             f"{tag}: the CONTROL did not fail — `$EUID` from the "
                                             f"environment did not decide the ownership test: {out!r} {err!r}")
                            self.assertEqual(2, len(self._diags(err)),
                                             f"{tag}: not one diagnostic per refusing entry point: {err!r}")
                        else:
                            self.assertEqual("pub=created|1 pointer none", out,
                                             f"{tag}: a healthy store did not publish and read back: "
                                             f"{out!r} {err!r}")
                            self.assertEqual([], self._diags(err), f"{tag}: {err!r}")
                # THE SEAM IS HONOURED, FAIL-CLOSED: a fixture whose `_u_euid_probe` fails must refuse the
                # chain, not fall back to anything. Shipped build only — the mutant has no such seam.
                self._wipe()
                rc, out, err = run_shell(shell, '_u_euid_probe() { return 1; }\n' + cycle,
                                         sources=(AUTH, STORE, READER, PUB), env={"HOME": self.home})
                self.assertTrue(out.startswith("pub=failed|"),
                                f"{shell}: a failed euid probe did not refuse the chain — the seam is not "
                                f"honoured, or something else answered the ownership test: {out!r} {err!r}")
                # …AND THE CACHE CANNOT BE SEEDED FROM OUTSIDE: `_u_probes_reset` clears the flag at the
                # entry points, so a caller-set `_U_EUID` never stands in for the probe.
                self._wipe()
                rc, out, err = run_shell(shell, '_U_EUID=4242; _U_EUID_PROBED=1\n' + cycle,
                                         sources=(AUTH, STORE, READER, PUB), env={"HOME": self.home})
                self.assertEqual("pub=created|1 pointer none", out,
                                 f"{shell}: a caller-preset `_U_EUID` was honoured — the cache is keyed on "
                                 f"state the entry point does not reset: {out!r} {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 178 ───────────────────────────────────────────────────────────────────────────────

    #: The two call sites of the pathname re-test (ENT-2c). The shipped line is IDENTICAL in both
    #: arms, so each anchor carries the line that follows it — `else` for the zsh arm, `fi` for bash.
    ROW_178_ZSH_CALL = '        _u_entry_path_still_bare "$_ae_p" || return 1\n    else\n'
    ROW_178_ZSH_GONE = '    else\n'
    ROW_178_BASH_CALL = '        _u_entry_path_still_bare "$_ae_p" || return 1\n    fi\n'
    ROW_178_BASH_GONE = '    fi\n'
    #: The helper's save/restore of `_u_stat`'s four outputs. Cell (iii) drops it, so the helper's own
    #: re-stat CLOBBERS `_U_SIZE` — which clause (2), immediately below the call, compares against the
    #: line that was read (in the zsh arm `_U_SIZE` is the AUTHENTICATED DESCRIPTOR's size).
    ROW_178_SAVE = ('    _ue_m="${_U_MODE:-}"; _ue_s="${_U_SIZE:-}"; _ue_u="${_U_UID:-}"; _ue_i="${_U_INO:-}"\n'
                    '    if _u_stat "$1" && [ "$_U_INO" = "$_ae_ino" ]; then _ue_rc=0; else _ue_rc=1; fi\n'
                    '    _U_MODE="$_ue_m"; _U_SIZE="$_ue_s"; _U_UID="$_ue_u"; _U_INO="$_ue_i"\n')
    ROW_178_SAVE_GONE = '    if _u_stat "$1" && [ "$_U_INO" = "$_ae_ino" ]; then _ue_rc=0; else _ue_rc=1; fi\n'

    #: `mv` the validated entry aside and drop a SYMLINK to it at the entry name. The descriptor the
    #: read is bound to still has exactly `_ae_ino` — the bytes DID come from the validated object —
    #: while the name ENT-1 validated is now a link ENT-1 forbids.
    ROW_178_SWAP = '/bin/mv -f "$_ae_p" "$_ae_p.moved"; /bin/ln -s "$_ae_p.moved" "$_ae_p"'
    #: Cell (i)'s window: after ENT-1 (`_ae_bound` is set on the line before `_ae_ino=`) and before the
    #: open, while the entry is still the non-symlink regular file ENT-1 validated.
    ROW_178_BEFORE_OPEN = '[ -n "${_ae_bound:-}" ] && [ -f "${_ae_p:-}" ] && [ ! -L "$_ae_p" ]'
    #: Cell (iii)'s window: after the READ (`_ae_ok` is set by it) and before the re-test.
    ROW_178_AFTER_READ = '[ "${_ae_ok:-0}" = 1 ]'

    def _row_178_trap(self, when, action):
        """A once-firing DEBUG trap (rows 160/168's mechanism), keyed on `when` and a done-flag."""
        return ('[ -n "${BASH_VERSION:-}" ] && set -T\n'
                "trap 'if " + when + ' && [ -z "${_t178_done:-}" ]; then _t178_done=1; '
                + action + "; fi' DEBUG\n")

    #: The store tuple plus whether the trap fired.
    ROW_178_OUT = ('trap - DEBUG\n'
                   'printf "%s %s %s %s|%s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" '
                   '"$_UNLEASHED_POINTER_STATE" "$_UNLEASHED_BASE_RESOLVED" "${_t178_done:-0}"')

    def _row_178_shape(self):
        """(the symlinked names, the other names) of the store as the round left it."""
        if not os.path.isdir(self.store):
            return [], []
        names = sorted(os.listdir(self.store))
        return ([n for n in names if os.path.islink(os.path.join(self.store, n))],
                [n for n in names if not os.path.islink(os.path.join(self.store, n))])

    def test_row_178_an_equal_inode_is_not_a_bare_pathname(self):
        """Row 178 (codex, PR #67 pass 15 — reproduced): between ENT-1 and the open, a same-uid process renames the validated entry aside and drops a SYMLINK to it at the entry name. ENT-2b binds the descriptor to `_ae_ino` and the link resolves to exactly that inode, so type, owner, size and content ALL pass on the descriptor — (i) the specification refuses anyway (`0 unresolved stale <sentinel>`, one sanitised diagnostic) because the pathname is re-tested after the read (ENT-2c: a link, or a name that no longer denotes the validated inode, fails the read), while an untouched FRESH store still resolves `1 pointer none`; (ii) under the mutation (both `_u_entry_path_still_bare` calls removed) the swap is ACCEPTED — `1 pointer none` — although the surviving store entry is a symlink ENT-1 forbids and every later consumer that opens that name leaves the store; (iii) under a mutation of the HELPER that drops the save/restore of `_u_stat`'s four outputs, its own re-stat clobbers `_U_SIZE`, and clause (2) then compares the line against the PATHNAME's current size: a two-line entry truncated to its first line after the read AUTHENTICATES (`1 pointer none`) where the specification refuses it — the helper would weaken the clause it runs beside. That clobbering mutant STILL refuses cell (i)'s swap, so (iii) is isolated to the save/restore. Both shells; every cell gets a FRESH store."""
        # THE INTERLEAVING IS DETERMINISTIC (rows 160/168's shape). Cell (i)'s trap is keyed on
        # `_ae_bound` being set — the line before `_ae_ino=` — plus the entry still being the
        # non-symlink regular file ENT-1 validated, so it fires exactly once, after ENT-1 and before
        # the open. `_unleashed_scan_store` expanded its glob before the body ran, so the `.moved`
        # file the swap leaves behind is NOT a second candidate in this scan.
        # Cell (iii)'s trap is keyed on `_ae_ok`, which the read itself sets, so it fires between the
        # read and the re-test; it truncates THROUGH the same name (`>` keeps the inode), so the
        # re-test's own inode clause still passes and only the size substitution can decide.
        # Measured, both shells: (i) spec `0 unresolved stale <sentinel>|1` with the store left holding
        # one symlink and one `.moved` regular file, fresh store `1 pointer none <target>|0`;
        # (ii) mutant `1 pointer none <target>|1`, empty stderr; (iii) spec `0 unresolved stale|1`,
        # clobbering mutant `1 pointer none <target>|1`, and that mutant still refuses (i).
        # THE SHIPPED SHAPE FIRST, so a reader that no longer carries ENT-2c fails HERE — on the rule —
        # rather than inside `with_mutation` on an anchor that no longer matches (the failure mode this
        # suite has hit before: a control built from a pattern that does not match cannot fail).
        with open(READER, encoding="utf-8") as fh:
            shipped = fh.read()
        self.assertEqual(2, shipped.count('_u_entry_path_still_bare "$_ae_p" || return 1'),
                         "the shipped reader does not re-test the entry pathname in BOTH arms (ENT-2c)")
        self.assertIn(self.ROW_178_SAVE, shipped,
                      "the re-test no longer saves and restores `_u_stat`'s four outputs")
        m_zsh = with_mutation(self.ROW_178_ZSH_CALL, self.ROW_178_ZSH_GONE, path=READER)
        m_nocall = with_mutation(self.ROW_178_BASH_CALL, self.ROW_178_BASH_GONE, path=m_zsh)
        m_clobber = with_mutation(self.ROW_178_SAVE, self.ROW_178_SAVE_GONE, path=READER)
        with open(m_nocall, encoding="utf-8") as fh:
            self.assertNotIn('_u_entry_path_still_bare "$_ae_p"', fh.read(),
                             "a pathname re-test survived the double mutation")
        with open(m_clobber, encoding="utf-8") as fh:
            clob = fh.read()
        self.assertEqual(2, clob.count('_u_entry_path_still_bare "$_ae_p"'),
                         "cell (iii) removed the calls as well — it is not a mutation of the HELPER")
        self.assertNotIn('_ue_m="${_U_MODE:-}"', clob, "the save/restore survived cell (iii)'s mutation")
        # Cell (iii)'s entry holds TWO lines, which clause (2) exists to refuse; the truncation source
        # holds only the first, and `>` truncates through the name so the inode never moves.
        short = os.path.join(self.home, "short")
        with open(short, "w", encoding="utf-8") as fh:
            fh.write(self.target + "\n")
        trunc = os.path.join(self.home, "trunc.sh")
        with open(trunc, "w", encoding="utf-8") as fh:
            fh.write('#!/bin/sh\ncat "$1" > "$2"\n')
        os.chmod(trunc, 0o755)
        two_line = (f'_unleashed_key "{self.target}"\n'
                    f'printf "%s\\n%s\\n" "{self.target}" "x" > "{self.store}/base.$_UNLEASHED_KEY"\n'
                    f'/bin/chmod 600 "{self.store}/base.$_UNLEASHED_KEY"\n')
        swap_body = (self._mkstore() + self._entry()
                     + self._row_178_trap(self.ROW_178_BEFORE_OPEN, self.ROW_178_SWAP)
                     + f'_unleashed_read_store "{self.store}"\n' + self.ROW_178_OUT)
        stale = f"0 unresolved stale {SENTINEL}"
        resolved = f"1 pointer none {self.target}"
        try:
            for shell in SHELLS:
                # ── (i) the swap is refused, and (ii) the call-less mutant accepts it ─────────────
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, m_nocall, PUB), True)):
                    self._wipe()
                    rc, out, err = self._run_with_timeout(shell, swap_body, srcs)
                    tag = f"{shell} swap {'mutant' if is_mutant else 'shipped'}"
                    self.assertNotEqual("TIMEOUT", rc, f"{tag}: the resolver hung")
                    links, others = self._row_178_shape()
                    # THE FIXTURE IS THE FINDING, asserted on BOTH builds: the entry name is a symlink
                    # afterwards, and the object it names survived beside it.
                    self.assertEqual(1, len(links), f"{tag}: the swap left no symlink: {links} {others}")
                    self.assertTrue(any(n.endswith(".moved") for n in others),
                                    f"{tag}: the renamed original is gone: {others}")
                    if not is_mutant:
                        self.assertEqual(f"{stale}|1", out,
                                         f"{tag}: an entry whose NAME became a symlink to the validated "
                                         f"inode was accepted, or the trap did not fire: {out!r} {err!r}")
                        diags = self._diags(err)
                        self.assertEqual(1, len(diags), f"{tag}: not one diagnostic: {err!r}")
                        self.assertEqual(1, len(err.splitlines()), f"{tag}: {err!r}")
                        self.assertNotIn(self.store, err, f"{tag}: the store path reached stderr")
                        self.assertNotIn(self.target, err, f"{tag}: the target path reached stderr")
                    else:
                        self.assertEqual(f"{resolved}|1", out,
                                         f"{tag}: the CONTROL did not fail — without the pathname re-test "
                                         f"the symlinked entry did not authenticate: {out!r} {err!r}")
                        self.assertEqual("", err, f"{tag}: {err!r}")
                # THE HONEST CONTROL, on a store nothing has interfered with — a re-test that refused
                # those would void every ordinary resolution. (The first draft of this control read a
                # store the swap had already symlinked, and would have passed for the wrong reason.)
                self._wipe()
                rc, out, err = self._run_with_timeout(
                    shell, self._mkstore() + self._entry()
                    + f'_unleashed_read_store "{self.store}"\n' + self.ROW_178_OUT,
                    (AUTH, STORE, READER, PUB))
                self.assertEqual(f"{resolved}|0", out,
                                 f"{shell}: a FRESH untouched store no longer resolves — the pathname "
                                 f"re-test refuses honest entries: {out!r} {err!r}")
                self.assertEqual([], self._diags(err), f"{shell}: {err!r}")
                links, others = self._row_178_shape()
                self.assertEqual(([], 1), (links, len(others)),
                                 f"{shell}: the honest round did not leave one plain entry: {links} {others}")
                # ── (iii) the helper must not clobber `_u_stat`'s outputs ─────────────────────────
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, m_clobber, PUB), True)):
                    self._wipe()
                    body = (self._mkstore() + two_line
                            + self._row_178_trap(self.ROW_178_AFTER_READ,
                                                 f'"{trunc}" "{short}" "$_ae_p"')
                            + f'_unleashed_read_store "{self.store}"\n' + self.ROW_178_OUT)
                    rc, out, err = self._run_with_timeout(shell, body, srcs)
                    tag = f"{shell} clobber {'mutant' if is_mutant else 'shipped'}"
                    self.assertNotEqual("TIMEOUT", rc, f"{tag}: the resolver hung")
                    if not is_mutant:
                        self.assertEqual(f"{stale}|1", out,
                                         f"{tag}: a TWO-LINE entry authenticated, or the truncation did "
                                         f"not happen: {out!r} {err!r}")
                        self.assertEqual(1, len(self._diags(err)), f"{tag}: not one diagnostic: {err!r}")
                    else:
                        self.assertEqual(f"{resolved}|1", out,
                                         f"{tag}: the CONTROL did not fail — a helper that re-stats the "
                                         f"pathname without restoring `_U_SIZE` did not substitute the "
                                         f"truncated size into clause (2): {out!r} {err!r}")
                        self.assertEqual("", err, f"{tag}: {err!r}")
                # …AND CELL (iii) IS ISOLATED: the clobbering mutant still refuses cell (i)'s swap, so
                # it is the save/restore that (iii) measures and not a re-test that stopped running.
                self._wipe()
                rc, out, err = self._run_with_timeout(shell, swap_body, (AUTH, STORE, m_clobber, PUB))
                self.assertEqual(f"{stale}|1", out,
                                 f"{shell}: the clobbering mutant also stopped refusing the swap — cell "
                                 f"(iii) is not isolated to the save/restore: {out!r} {err!r}")
        finally:
            for m in (m_zsh, m_nocall, m_clobber):
                os.unlink(m)


# ==================================================================================================
# Chunk 8 — PR #67 pass 17
# ==================================================================================================
# Rows 179-183. Every row here is TM-4 C1 material: an ordinary environment, no adversary, and a
# user-visible outcome — a healthy store that reads as empty, a first session that never seeds the
# store, one directory that publishes three entries, two ordinary hooks that report a repair state at
# each other, and a harness whose HOME sandbox is a sandbox in bash only. Each defect was REPRODUCED
# before its fix, and each mutation below restores the pre-fix code exactly.

import pwd
import time


@unittest.skipUnless(DARWIN, "the Darwin chain/ACL arm and the Darwin store; on Linux every publish cell is `failed` by design")
class RowsPass17(unittest.TestCase):
    """Mutant-table rows 179-188 (PR #67, codex passes 17, 20 and 23, plus 185's pre-merge review)."""

    #: N6-6's store-level tuple, and the publisher's one-word state.
    OUTP = 'printf "%s %s %s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_SOURCE" "$_UNLEASHED_POINTER_STATE"'
    PSTATE = 'printf "%s" "$_UNLEASHED_POINTER_STATE"'

    def setUp(self):
        # A scratch HOME under ~/.claude (§7 step 3f(i)) so every chain authenticates and no cell
        # reads or writes the developer's real store.
        self.home = scratch_home("rp17.2617.")
        self.store = os.path.join(self.home, ".claude", "unleashed-mail", "bases")
        self.target = os.path.join(self.home, "target")
        os.makedirs(self.target)
        os.chmod(self.target, 0o700)

    def tearDown(self):
        # Row 181 leaves a 0600 directory and row 180 a 0777 one; restore both before the rmtree, or
        # the fixture leaks into $HOME exactly as the ACL fixtures once did.
        os.chmod(self.home, 0o700)
        for dirpath, dirnames, _ in os.walk(self.home):
            for d in dirnames:
                try:
                    os.chmod(os.path.join(dirpath, d), 0o700)
                except OSError:
                    pass
        shutil.rmtree(self.home, ignore_errors=True)

    # ── shared scaffolding ────────────────────────────────────────────────────────────────────

    def _wipe(self):
        shutil.rmtree(os.path.join(self.home, ".claude"), ignore_errors=True)

    def _mkstore(self):
        return (f'_unleashed_name_max "{self.store}" >/dev/null || exit 9\n'
                f'_unleashed_create_store "{self.store}" || exit 9\n')

    def _entry(self, t=None, mode="600"):
        t = t or self.target
        return (f'_unleashed_key "{t}"\n'
                f'printf "%s\\n" "{t}" > "{self.store}/base.$_UNLEASHED_KEY"\n'
                f'/bin/chmod {mode} "{self.store}/base.$_UNLEASHED_KEY"\n')

    def _names(self):
        """The durable entries in the store, sorted — never the transients."""
        if not os.path.isdir(self.store):
            return []
        return sorted(f for f in os.listdir(self.store) if f.startswith("base."))

    @staticmethod
    def _diags(err):
        return [l for l in err.splitlines() if l.startswith("unleashed-mail:")]

    def _shadow(self, name, files):
        """A plugin root holding ONLY `files` under scripts/lib — {basename: source path}.

        Row 156's shape, and row 183 needs it: a mutated `paths.sh` alone in the directory
        `with_mutation` returns finds none of the machinery beside it, degrades to the D′ envelope for
        the wrong reason and publishes nothing in EITHER build — a control that cannot fail.
        """
        root = os.path.join(self.home, name, "scripts", "lib")
        os.makedirs(root)
        for base, src in files.items():
            shutil.copy(src, os.path.join(root, base))
        return root

    @staticmethod
    def _slice(path, head, tail):
        """The CURRENT text of `path` from the unique `head` through the first `tail` after it."""
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        assert text.count(head) == 1, f"head anchor not unique in {path}: {head!r}"
        start = text.index(head)
        assert tail in text[start:], f"tail anchor not found after the head in {path}: {tail!r}"
        end = text.index(tail, start) + len(tail)
        old = text[start:end]
        assert text.count(old) == 1, f"sliced block not unique in {path}"
        return old

    # ── row 179 ───────────────────────────────────────────────────────────────────────────────

    #: The scan's glob-forcing block — sliced from the head of its paragraph through the `for` line —
    #: and the pre-fix shape: a zsh arm that sets `no_nomatch` ALONE (which does not turn globbing back
    #: on) and no bash arm at all.
    ROW_179_HEAD = "    # GLOBBING IS FORCED ON FOR THIS SCAN"
    ROW_179_TAIL = '    fi\n    for _ss_f in "$_ss_store"/base.*; do\n'
    ROW_179_OLD = ('    if [ -n "${ZSH_VERSION:-}" ]; then\n'
                   '        setopt local_options no_nomatch\n'
                   '    fi\n'
                   '    for _ss_f in "$_ss_store"/base.*; do\n')
    #: …and the restore of the caller's own flag, which the mutation drops with it.
    ROW_179_RESTORE = ("    [ \"${_ss_noglob:-0}\" = 1 ] && set -f          "
                       "# restore the caller's `noglob`; zsh did it at return\n")
    #: Globbing OFF, spelled as each shell spells it. zsh's own name for the option is `noglob`;
    #: `no_noglob` is NOT an option name there (measured: `setopt: no such option: no_noglob`), which
    #: is why the first attempt at this fix moved the bash arm only.
    NOGLOB = {"/bin/bash": "set -f\n", "/bin/zsh": "setopt noglob\n"}
    #: The FUNCTIONAL probe for "globbing is still off". NOT `$-`: zsh reports `noglob` as `F` and not
    #: `f`, so a flag-letter test reads as restored under zsh when nothing was restored at all.
    GLOB_PROBE = 'printf "%s|" /etc/ho*\n'

    def _row_179_mutant(self):
        block = self._slice(READER, self.ROW_179_HEAD, self.ROW_179_TAIL)
        first = with_mutation(block, self.ROW_179_OLD, path=READER)
        try:
            return with_mutation(self.ROW_179_RESTORE, "", path=first)
        finally:
            os.unlink(first)

    def test_row_179_the_store_scan_forces_globbing_on_and_restores_the_callers_setting(self):
        """Row 179 (codex, PR #67 pass 17 — reproduced): a caller with globbing DISABLED — `set -f`, zsh `setopt noglob`, the defensive `set -euf` idiom in a wrapper, or an inherited `SHELLOPTS=noglob` — reads a store holding one valid entry: the specification forces globbing on for the scan and resolves (`1 pointer none`, no diagnostic) in both shells; under the mutation (the forcing removed, the zsh arm back to `no_nomatch` alone and the bash flag save/restore gone) the pattern `<store>/base.*` reaches the loop LITERAL, fails rule 0 as "vanished", and a HEALTHY store reports `0 unresolved none` with the "no plugin-state entry is present" notice — the wrong answer, and one SS-1 is specified to stay silent on. Both shells; the bash arm again with `SHELLOPTS=noglob` carried in from the environment. Three cells hold in BOTH builds, so nothing here is bought with a regression: the caller's `noglob` is still in force after the read (`/etc/ho*` stays literal — asserted FUNCTIONALLY, because zsh reports the option as `F` and a `$-` test reads as restored when nothing was), an EMPTY store still reports `none`, and a caller who left globbing ON keeps it on and still resolves."""
        # Measured, both shells: (i) shipped `1 pointer none` with ZERO diagnostics, mutant
        # `0 unresolved none` with ONE ("no plugin-state entry is present"). (iv) bash + SHELLOPTS:
        # `1 pointer none` / `0 unresolved none`. (ii) `/etc/ho*|` in both builds under noglob and
        # `/etc/hosts|/etc/hosts.equiv|` with globbing on. (iii) empty store `0 unresolved none`, one
        # diagnostic, in both builds. A PUBLISH under `noglob` is NOT a cell: its own-entry check runs
        # on the composed pathname and not through the glob, so both builds report `created` (measured)
        # — a cell that cannot fail, recorded here rather than written.
        # THE SHIPPED SHAPE FIRST (row 178's convention), so a reader that no longer forces the glob
        # fails HERE — on the rule — and not inside `with_mutation` on an anchor that stopped matching.
        with open(READER, encoding="utf-8") as fh:
            shipped = fh.read()
        self.assertIn("setopt local_options no_nomatch glob", shipped,
                      "the shipped scan does not force globbing ON in the zsh arm (RD-9)")
        self.assertIn("case $- in *f*) _ss_noglob=1; set +f ;;", shipped,
                      "the shipped scan does not save and clear the caller's `-f` in the bash arm (RD-9)")
        self.assertIn(self.ROW_179_RESTORE, shipped,
                      "the shipped scan does not restore the caller's `noglob` (RD-9)")
        mutant = self._row_179_mutant()
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, mutant, PUB), True)):
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    # (i) a HEALTHY store read by a caller who has globbing off.
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + self._entry() + self.NOGLOB[shell]
                                             + f'_unleashed_read_store "{self.store}"\n' + self.OUTP,
                                             sources=srcs)
                    if not is_mutant:
                        self.assertEqual("1 pointer none", out,
                                         f"{tag}: a healthy store did not resolve under noglob: {out!r} {err!r}")
                        self.assertEqual([], self._diags(err), f"{tag}: {err!r}")
                    else:
                        self.assertEqual("0 unresolved none", out,
                                         f"{tag}: the CONTROL did not fail — the literal pattern still "
                                         f"reached the loop and the store still read as empty: {out!r} {err!r}")
                        self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
                        self.assertIn("no plugin-state entry is present", err,
                                      f"{tag}: the healthy store was not reported as empty: {err!r}")
                    # (ii) the caller's globbing is STILL OFF afterwards — in both builds.
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + self._entry() + self.NOGLOB[shell]
                                             + f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                             + self.GLOB_PROBE + self.OUTP, sources=srcs)
                    self.assertTrue(out.startswith("/etc/ho*|"),
                                    f"{tag}: the scan left the caller's globbing ON: {out!r}")
                    # …and the probe can fail: with globbing left ON the same pattern expands.
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + self._entry()
                                             + f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                             + self.GLOB_PROBE + self.OUTP, sources=srcs)
                    self.assertFalse(out.startswith("/etc/ho*|"),
                                     f"{tag}: the glob probe does not discriminate — it stayed literal "
                                     f"with globbing ON: {out!r}")
                    self.assertTrue(out.startswith("/etc/ho"), f"{tag}: {out!r}")
                    # (v) the honest control: with globbing ON the store resolves in both builds.
                    self.assertTrue(out.endswith("1 pointer none"),
                                    f"{tag}: a healthy store did not resolve with globbing on: {out!r} {err!r}")
                    # (iii) an EMPTY store still reports `none` under noglob, in both builds — the
                    # forced glob must not turn the unmatched pattern into a phantom entry.
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + self.NOGLOB[shell]
                                             + f'_unleashed_read_store "{self.store}"\n' + self.OUTP,
                                             sources=srcs)
                    self.assertEqual("0 unresolved none", out, f"{tag}: empty store: {out!r} {err!r}")
                    self.assertEqual(1, len(self._diags(err)), f"{tag}: empty store: {err!r}")
                # (iv) bash imports SHELLOPTS at startup, so a wrapper that exported it disables
                # globbing before the first sourced line runs. zsh has no such import.
                if shell == "/bin/bash":
                    for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                            ((AUTH, STORE, mutant, PUB), True)):
                        self._wipe()
                        rc, out, err = run_shell(shell, self._mkstore() + self._entry()
                                                 + f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                                 + self.OUTP, sources=srcs, env={"SHELLOPTS": "noglob"})
                        want = "0 unresolved none" if is_mutant else "1 pointer none"
                        note = ("the CONTROL did not fail — an inherited SHELLOPTS=noglob no longer "
                                "empties the scan") if is_mutant else "an inherited SHELLOPTS=noglob emptied the scan"
                        self.assertEqual(want, out, f"{shell} SHELLOPTS {'mutant' if is_mutant else 'shipped'}: "
                                                    f"{note}: {out!r} {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 180 ───────────────────────────────────────────────────────────────────────────────

    #: E2a's creation block — the `[ ! -e ] && [ ! -L ]` head through its own `fi`. RE-PINNED (pass 17
    #: follow-up): the block now authenticates the PARENT before it creates anything and creates under
    #: `umask 077`, so it is SLICED from the current file rather than quoted — a comment rewrite inside
    #: it must not strand this row on a pattern that no longer matches.
    #: RE-PINNED again (pass 22): E2b's fold now runs BEFORE this block, so creation operates on
    #: `_pb_folded` — the lexically folded path — rather than the caller's spelling. That reordering is
    #: the fix for a refusal that created directories through a symlink and outside the chain.
    ROW_180_HEAD = '    if [ ! -e "$_pb_folded" ] && [ ! -L "$_pb_folded" ]; then\n'
    ROW_180_TAIL = '\n    fi\n'
    #: The two halves the follow-up added, each mutable on its own so each is measured on its own.
    ROW_180_UMASK = '        ( umask 077; /bin/mkdir -p -- "$_pb_folded" ) >/dev/null 2>&1 || :\n'
    ROW_180_UMASK_GONE = '        /bin/mkdir -p -- "$_pb_folded" >/dev/null 2>&1 || :\n'
    #: The authentication half, as it stands after pass 19: the walk to the NEAREST EXISTING ancestor
    #: replaced the immediate parent, because with two or more missing components the parent is itself
    #: absent and the chain refused it — publication `failed` on every run of a fresh install.
    ROW_180_PARENT = ('        _pb_anc="$_pb_folded"\n'
                      '        while [ ! -e "$_pb_anc" ] && [ ! -L "$_pb_anc" ]; do\n'
                      '            _pb_up="${_pb_anc%/*}"; [ -n "$_pb_up" ] || _pb_up=/\n'
                      '            [ "$_pb_up" != "$_pb_anc" ] || break\n'
                      '            _pb_anc="$_pb_up"\n'
                      '        done\n'
                      '        if ! _unleashed_auth_chain "$_pb_anc"; then\n'
                      '            _unleashed_pub_failed "the plugin-data base does not exist and its nearest'
                      ' existing ancestor does not authenticate"; return 0\n'
                      '        fi\n')

    def _row_180_block(self):
        with open(PUB, encoding="utf-8") as fh:
            text = fh.read()
        assert text.count(self.ROW_180_HEAD) == 1, "E2a's creation guard is not unique"
        i = text.index(self.ROW_180_HEAD)
        return text[i:text.index(self.ROW_180_TAIL, i) + len(self.ROW_180_TAIL)]

    def test_row_180_a_plugin_data_base_that_does_not_exist_yet_is_created_not_refused(self):
        """Row 180 (codex, PR #67 pass 17 — reproduced; re-pinned after the follow-up that closed this row's own two findings): `CLAUDE_PLUGIN_DATA` names a directory nothing has written to yet — the ordinary state of a FIRST SESSION, since this library's own writers create it lazily with `mkdir -p` moments later: the specification authenticates the PARENT, creates the directory at 0700 and publishes (`created`, stderr SILENT), a second process reports `current`, and a reader with no variable resolves it (`1 pointer <base>`); under the mutation (E2a's whole creation block removed) EVERY run reports `failed` with a publication-failure line on stderr, the store is never seeded, and the reader answers `0 unresolved none`. TWO FURTHER MUTANTS, one per half of the follow-up, because the first version of this fix shipped both defects and this row is what found them: (a) with the `umask 077` subshell dropped, a fresh install under `umask 002` creates the base 0775, its OWN chain then refuses it, and the publish reports `failed` on that hook and every later one — the specification creates 0700 and publishes under either umask; (b) with the `mkdir` moved back above the parent authentication, an other-writable parent gets the directory CREATED and only then refused — a write outside the store performed by the refusal path, which PUB-9 E4 step (i) forbids on the store chain — where the specification refuses with nothing on disk. Both shells throughout. Four refusal controls hold on the shipped build: a FILE at the base, a SYMLINK to a directory, a DANGLING symlink (whose target is NOT created) and an other-writable parent each report `failed` with one diagnostic and leave no store. The `-L` half of the creation guard is stated rather than claimed: `/bin/mkdir -p` on a dangling symlink creates nothing in either build (measured), so that half does not discriminate at the outcome level and no cell here pretends it does."""
        # Measured, both shells. SHIPPED: fresh `created` at 0700, silent, then `current`, reader
        # `1 pointer <b>`; `umask 002` `created` at 0700; 0777 parent `failed`, nothing created, no
        # store, "…does not exist and its parent does not authenticate".
        # m_none  : `failed` + 1 diagnostic on both runs, `0 unresolved none`, nothing created.
        # m_umask : fresh `created` at 0755; `umask 002` `failed` at 0775 — the base is left behind
        #           group-writable, so every later hook fails on it too.
        # m_order : 0777 parent `failed` WITH the directory created (the state is the same; the
        #           FILESYSTEM is the discriminator, as in row 1's mtime cell).
        block = self._row_180_block()
        # The guard now walks to the NEAREST EXISTING ancestor before authenticating: pinning the
        # immediate parent was the shape that failed for two or more missing components (codex pass 19).
        self.assertIn('while [ ! -e "$_pb_anc" ] && [ ! -L "$_pb_anc" ]', block,
                      "the creation guard no longer walks up to an existing ancestor")
        self.assertIn("_unleashed_auth_chain \"$_pb_anc\"", block,
                      "E2a no longer authenticates the parent before creating the base (PUB-9 E2a)")
        self.assertIn(self.ROW_180_UMASK, block,
                      "E2a no longer creates the base under `umask 077` (PUB-9 E2a)")
        mutant = with_mutation(block, "", path=PUB)
        m_umask = with_mutation(self.ROW_180_UMASK, self.ROW_180_UMASK_GONE, path=PUB)
        m_order = with_mutation(self.ROW_180_PARENT + self.ROW_180_UMASK,
                                self.ROW_180_UMASK + self.ROW_180_PARENT, path=PUB)
        try:
            self._row_180_halves(m_umask, m_order)
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, READER, mutant), True)):
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    self._wipe()
                    base = os.path.join(self.home, f"first-session-{os.path.basename(shell)}")
                    shutil.rmtree(base, ignore_errors=True)
                    rc, out, err = run_shell(shell, f'_unleashed_publish "{self.store}" "{base}"\n' + self.PSTATE,
                                             sources=srcs)
                    rc2, out2, err2 = run_shell(shell, f'_unleashed_publish "{self.store}" "{base}"\n' + self.PSTATE,
                                                sources=srcs)
                    rc3, out3, err3 = run_shell(shell, f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                                + self.OUTP + ' ; printf " %s" "$_UNLEASHED_BASE_RESOLVED"',
                                                sources=srcs)
                    if not is_mutant:
                        self.assertEqual("created", out, f"{tag}: a base that does not exist yet did not "
                                                         f"publish: {out!r} {err!r}")
                        self.assertEqual("", err, f"{tag}: the first session's stderr was not silent: {err!r}")
                        self.assertTrue(os.path.isdir(base) and not os.path.islink(base),
                                        f"{tag}: the base was not created")
                        self.assertEqual(0o700, statmod.S_IMODE(os.stat(base).st_mode),
                                         f"{tag}: the created base is not 0700 — E2a's `umask 077` "
                                         f"subshell is what makes this independent of the caller's umask")
                        self.assertEqual("current", out2, f"{tag}: the second run rewrote or refused: {out2!r}")
                        self.assertEqual(f"1 pointer none {base}", out3, f"{tag}: {out3!r} {err3!r}")
                    else:
                        self.assertEqual("failed", out, f"{tag}: the CONTROL did not fail — a base that does "
                                                        f"not exist yet still published: {out!r} {err!r}")
                        self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
                        self.assertFalse(os.path.exists(base), f"{tag}: the mutant created the base after all")
                        self.assertEqual("failed", out2, f"{tag}: {out2!r}")
                        self.assertEqual(f"0 unresolved none {SENTINEL}", out3,
                                         f"{tag}: the store was seeded anyway: {out3!r} {err3!r}")
                # ── the refusal controls, on the SHIPPED build ────────────────────────────────
                afile = os.path.join(self.home, "a-file")
                with open(afile, "w", encoding="utf-8") as fh:
                    fh.write("x\n")
                realdir = os.path.join(self.home, "a-real-dir")
                os.makedirs(realdir, exist_ok=True)
                os.chmod(realdir, 0o700)
                link = os.path.join(self.home, "a-link")
                victim = os.path.join(self.home, "victim-that-must-not-be-created")
                wwpar = os.path.join(self.home, "other-writable-parent")
                shutil.rmtree(wwpar, ignore_errors=True)
                os.makedirs(wwpar)
                os.chmod(wwpar, 0o777)
                for label, setup, value in (
                        ("a FILE at the base", lambda: None, afile),
                        ("a SYMLINK at the base", lambda: os.symlink(realdir, link), link),
                        ("a DANGLING symlink at the base", lambda: os.symlink(victim, link), link),
                        ("an other-writable parent", lambda: None, os.path.join(wwpar, "b"))):
                    self._wipe()
                    if os.path.islink(link):
                        os.unlink(link)
                    setup()
                    rc, out, err = run_shell(shell, f'_unleashed_publish "{self.store}" "{value}"\n' + self.PSTATE)
                    tag = f"{shell} control [{label}]"
                    self.assertEqual("failed", out, f"{tag}: an unusable base was published: {out!r} {err!r}")
                    self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
                    self.assertFalse(os.path.exists(self.store), f"{tag}: a refused publish created the store")
                    self.assertFalse(os.path.exists(victim),
                                     f"{tag}: `mkdir -p` followed a dangling symlink and created its target")
                    self.assertTrue(os.path.isfile(afile), f"{tag}: the file at the base was replaced")
                if os.path.islink(link):
                    os.unlink(link)
                os.chmod(wwpar, 0o700)
        finally:
            for m in (mutant, m_umask, m_order):
                os.unlink(m)

    def _row_180_halves(self, m_umask, m_order):
        """The two cells for the halves the follow-up added — the umask, and the ordering.

        Kept beside the row rather than folded into its loop because each has its OWN mutant and its
        own discriminator: the umask cell discriminates on the base's MODE and then on the state it
        causes, the ordering cell on whether a directory exists after a refusal (the state is `failed`
        in both builds — a cell that compared only the state would prove nothing here).
        """
        for shell in SHELLS:
            # (a) THE UMASK. A fresh install under `umask 002`: 0700 and `created` under the
            # specification; 0775 and `failed` under the mutant, because the base's own chain walk
            # refuses a group-writable directory — and the directory is LEFT behind, so every later
            # hook fails on it too.
            for label, srcs, want, want_mode in (("shipped", (AUTH, STORE, READER, PUB), "created", 0o700),
                                                 ("mutant", (AUTH, STORE, READER, m_umask), "failed", 0o775)):
                self._wipe()
                b = os.path.join(self.home, f"umask002-{label}-{os.path.basename(shell)}")
                shutil.rmtree(b, ignore_errors=True)
                rc, out, err = run_shell(shell, "umask 002\n"
                                         + f'_unleashed_publish "{self.store}" "{b}"\n' + self.PSTATE,
                                         sources=srcs)
                tag = f"{shell} umask002 {label}"
                self.assertTrue(os.path.isdir(b), f"{tag}: nothing was created")
                self.assertEqual(want_mode, statmod.S_IMODE(os.stat(b).st_mode),
                                 f"{tag}: base mode {oct(statmod.S_IMODE(os.stat(b).st_mode))}")
                if label == "shipped":
                    self.assertEqual("created", out, f"{tag}: {out!r} {err!r}")
                    self.assertEqual("", err, f"{tag}: {err!r}")
                else:
                    self.assertEqual("failed", out,
                                     f"{tag}: the CONTROL did not fail — a base created with the "
                                     f"ambient umask still authenticated: {out!r} {err!r}")
                    self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
            # (b) THE ORDERING. An other-writable parent: both builds report `failed`, and the
            # discriminator is the FILESYSTEM — the specification creates nothing, the mutant
            # (mkdir moved above the parent authentication) leaves a directory it then refuses.
            for label, srcs, want_created in (("shipped", (AUTH, STORE, READER, PUB), False),
                                              ("mutant", (AUTH, STORE, READER, m_order), True)):
                self._wipe()
                par = os.path.join(self.home, f"wwpar-{label}-{os.path.basename(shell)}")
                shutil.rmtree(par, ignore_errors=True)
                os.makedirs(par)
                os.chmod(par, 0o777)
                child = os.path.join(par, "b")
                try:
                    rc, out, err = run_shell(shell, f'_unleashed_publish "{self.store}" "{child}"\n'
                                             + self.PSTATE, sources=srcs)
                    tag = f"{shell} 0777-parent {label}"
                    self.assertEqual("failed", out, f"{tag}: an unauthenticated parent published: {out!r} {err!r}")
                    self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
                    self.assertFalse(os.path.exists(self.store), f"{tag}: the refusal created a store")
                    if want_created:
                        self.assertTrue(os.path.isdir(child),
                                        f"{tag}: the CONTROL did not fail — `mkdir` above the parent "
                                        f"authentication left nothing on disk: {err!r}")
                    else:
                        self.assertFalse(os.path.exists(child),
                                         f"{tag}: the refusal path created a directory under an "
                                         f"other-writable parent: {err!r}")
                finally:
                    os.chmod(par, 0o700)

    # ── row 181 ───────────────────────────────────────────────────────────────────────────────

    #: E2b's normalisation, sliced from the first line of the fold through the assignment that installs
    #: its result. The pre-fix shape is its ABSENCE: the caller's spelling reaches the encoder.
    #: RE-PINNED (pass 17 follow-up): the fold is LEXICAL now — a `while` over `/`-separated segments —
    #: because this row's own cross-shell finding killed the `cd -P`/`pwd -P` version.
    ROW_181_HEAD = '    _pb_norm=""; _pb_rest="${_pb_value#/}"\n'
    # The tail moved when the fold gained its same-inode check: the block now ends at the assignment
    # BACK to `_pb_value`, so slicing it out still removes the whole fold — the loop, the folded-path
    # `-d` test and the inode verification — and leaves the caller's raw spelling as the key, which is
    # exactly the pre-fix behaviour this row discriminates against. Measured after re-pinning.
    ROW_181_TAIL = '    _pb_value="$_pb_folded"\n'

    def test_row_181_one_directory_publishes_one_entry_whatever_the_caller_spelled(self):
        """Row 181 (codex, PR #67 pass 17 — reproduced; re-pinned after the follow-up this row's own finding forced): four spellings of ONE directory — `<d>/sub`, `<d>/./sub`, `<d>/x/../sub`, `<d>//sub` — published by four fresh processes into one store: the specification folds the value LEXICALLY before deriving the key — a `while` over `/`-separated segments that drops `''` and `.` and pops on `..`, no fork and no `cd` — so the store holds ONE entry, the runs report `created` then `current` three times, and a reader answers `1 pointer <d>/sub`, IDENTICALLY IN BOTH SHELLS; under the mutation (the fold removed) the key is an injective encoding of the SPELLING, so the store holds FOUR entries, three runs report `conflict`, and every later reader is permanently `0 unresolved conflict` — a state only a manual delete clears. THE FIRST VERSION OF THIS FIX USED `cd -P`/`pwd -P`, and this row measured what that cost: bash returns the spelling it was asked for and zsh returns the ON-DISK case, so one mis-cased `CLAUDE_PLUGIN_DATA` published by a bash hook and a zsh shell left TWO entries and a permanent conflict that did not exist before the fix. That cell is kept as a REGRESSION GUARD and now asserts ONE entry. ENC-4's case-folding cost stands and is asserted as accepted behaviour in BOTH shells: `SUB` beside `sub` still publishes a second entry and still conflicts. One control on the residual the fold declares: a value whose PARENT is a symlink is refused by the chain walk (`failed`) in both builds, so not resolving symlinks cannot publish a base the chain would reject."""
        # Measured, both shells: shipped 1 entry, `created current current current`, read
        # `1 pointer none <d>/sub`; mutant 4 entries, `created conflict conflict conflict`, read
        # `0 unresolved conflict`. Case: `created conflict`, 2 entries, in BOTH shells. Cross-shell
        # mis-cased: `created current`, ONE entry (two under the `cd -P` version). Symlinked parent:
        # `failed`, "chain does not authenticate", in both builds.
        # THE 0600-DIRECTORY CELL IS REMOVED, and this is why rather than a silent deletion: the
        # `cd -P` version refused an unenterable base because it could not enter it, and a LEXICAL
        # fold never enters anything — measured, both builds now report `created` for a 0600 base, so
        # the cell no longer discriminates and would be a check that cannot fail. (The refusal it
        # asserted, "cannot be resolved to a physical path", no longer exists in the publisher.)
        d = os.path.join(self.home, "d")
        sub = os.path.join(d, "sub")
        os.makedirs(sub)
        os.makedirs(os.path.join(d, "x"))
        for p in (d, sub, os.path.join(d, "x")):
            os.chmod(p, 0o700)
        spellings = (sub, f"{d}/./sub", f"{d}/x/../sub", f"{d}//sub")
        with open(PUB, encoding="utf-8") as fh:
            pub = fh.read()
        self.assertIn(self.ROW_181_HEAD, pub,
                      "the shipped publisher no longer folds the base value before deriving its key "
                      "(PUB-9 E2b)")
        self.assertIn("'..')   _pb_norm=\"${_pb_norm%/*}\" ;;", pub,
                      "E2b's fold no longer pops on `..`")
        # …and it is LEXICAL: no `cd`, no `pwd`, no fork on this path. Pinned as an absence because the
        # `cd -P` version was correct in bash and wrong in zsh, and nothing but a shell-by-shell run
        # would have shown that — the absence is the fix.
        self.assertNotIn("_pb_phys", pub,
                         "E2b resolves the base through `cd -P`/`pwd -P` again — that version returns "
                         "the caller's spelling in bash and the ON-DISK case in zsh, so one value "
                         "published by the two shells leaves two entries and a permanent conflict")
        block = self._slice(PUB, self.ROW_181_HEAD, self.ROW_181_TAIL)
        mutant = with_mutation(block, "", path=PUB)
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, READER, mutant), True)):
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    self._wipe()
                    states = []
                    for v in spellings:
                        rc, out, err = run_shell(shell, f'_unleashed_publish "{self.store}" "{v}" 2>/dev/null\n'
                                                 + self.PSTATE, sources=srcs)
                        states.append(out)
                    rc, out, err = run_shell(shell, f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                             + self.OUTP + ' ; printf " %s" "$_UNLEASHED_BASE_RESOLVED"',
                                             sources=srcs)
                    if not is_mutant:
                        self.assertEqual(["created", "current", "current", "current"], states,
                                         f"{tag}: four spellings of one directory did not settle: {states}")
                        self.assertEqual(1, len(self._names()),
                                         f"{tag}: one directory left {self._names()}")
                        self.assertEqual(f"1 pointer none {sub}", out, f"{tag}: {out!r} {err!r}")
                    else:
                        self.assertEqual(["created", "conflict", "conflict", "conflict"], states,
                                         f"{tag}: the CONTROL did not fail — the spellings did not each "
                                         f"publish their own entry: {states}")
                        self.assertEqual(4, len(self._names()), f"{tag}: {self._names()}")
                        self.assertEqual(f"0 unresolved conflict {SENTINEL}", out, f"{tag}: {out!r} {err!r}")
                    # THE RESIDUAL THE FOLD DECLARES, asserted in both builds: it does not resolve
                    # symlinks, and it does not have to — a value whose PARENT is a symlink is refused
                    # by the chain walk (PCH-1 admits no symlinked component), so the fold cannot
                    # publish a base the chain would reject.
                    self._wipe()
                    lnk = os.path.join(self.home, "lnk-parent")
                    if not os.path.islink(lnk):
                        os.symlink(d, lnk)
                    rc, out, err = run_shell(shell, f'_unleashed_publish "{self.store}" "{lnk}/sub"\n'
                                             + self.PSTATE, sources=srcs)
                    self.assertEqual("failed", out,
                                     f"{tag}: a base reached through a symlinked parent published: "
                                     f"{out!r} {err!r}")
                    self.assertIn("chain does not authenticate", err, f"{tag}: {err!r}")
                    self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
            # ── ENC-4's ACCEPTED residual, measured on the SHIPPED build ──────────────────────
            # The volume decides what these cells MEAN, so it is probed and both kinds are asserted
            # rather than one being skipped: a skip here would report the whole row as skipped on a
            # case-sensitive volume and hide the discriminating cells above that had already passed.
            upper = os.path.join(d, "SUB")
            case_insensitive = os.path.exists(upper)
            if case_insensitive:
                # `SUB` and `sub` are ONE directory, and the fold does not touch case, so the
                # mis-cased value publishes a SECOND entry and conflicts — the cost ENC-4 declares —
                # IN BOTH SHELLS. (Under the `cd -P` version zsh reported `current` with one entry
                # here, which is what made that version shell-dependent.)
                per_shell = (("/bin/bash", ["created", "conflict"], 2),
                             ("/bin/zsh", ["created", "conflict"], 2))
                cross, cross_n = ["created", "current"], 1
                why = "the case-folding cost ENC-4 declares has changed, or it now differs by shell"
            else:
                # A case-SENSITIVE volume: `SUB` does not exist, so it is a different directory and
                # two entries are the CORRECT answer in both shells — and the two shells agree.
                os.makedirs(upper)
                os.chmod(upper, 0o700)
                per_shell = (("/bin/bash", ["created", "conflict"], 2),
                             ("/bin/zsh", ["created", "conflict"], 2))
                cross, cross_n = ["created", "current"], 1
                why = "on a case-sensitive volume two directories must produce two entries"
            for shell, want_states, want_entries in per_shell:
                self._wipe()
                states = [run_shell(shell, f'_unleashed_publish "{self.store}" "{v}" 2>/dev/null\n' + self.PSTATE)[1]
                          for v in (sub, upper)]
                self.assertEqual(want_states, states, f"{shell}: {why}: {states}")
                self.assertEqual(want_entries, len(self._names()), f"{shell}: {self._names()}")
            # THE REGRESSION GUARD, which is why this cell exists at all: ONE mis-cased value
            # published by BOTH shells must leave ONE entry. Under the `cd -P` version it left two —
            # bash published `<d>/SUB` and zsh published `<d>/sub` — a permanent conflict the fix
            # introduced and this cell measured. A lexical fold cannot reintroduce it: it never asks
            # the filesystem what the path is called.
            self._wipe()
            states = [run_shell(shell, f'_unleashed_publish "{self.store}" "{upper}" 2>/dev/null\n' + self.PSTATE)[1]
                      for shell in SHELLS]
            self.assertEqual(cross, states,
                             f"the two shells disagreed on ONE value: {states} (case-insensitive "
                             f"volume: {case_insensitive})")
            self.assertEqual(cross_n, len(self._names()),
                             f"one value published by two shells left {self._names()}")
            # The control that makes that cell a finding and not a fixture artefact: with the value
            # spelled as it is on disk, the two shells publish ONE entry.
            self._wipe()
            states = [run_shell(shell, f'_unleashed_publish "{self.store}" "{sub}" 2>/dev/null\n' + self.PSTATE)[1]
                      for shell in SHELLS]
            self.assertEqual(["created", "current"], states, f"{states}")
            self.assertEqual(1, len(self._names()), f"{self._names()}")
        finally:
            os.unlink(mutant)

    # ── row 182 ───────────────────────────────────────────────────────────────────────────────

    #: E7b's post-scan, and the pre-fix shape: one scan, one authentication, and the repair state
    #: reported from it.
    ROW_182_SHIPPED = ('    _unleashed_scan_store "$_pb_store"\n'
                       '    _pb_own=0; _unleashed_auth_entry "$_pb_entry" && _pb_own=1\n'
                       '    if [ "$_pb_own" = 0 ] || [ "$_UNLEASHED_FAILED" -gt 0 ]; then\n'
                       '        _unleashed_scan_store "$_pb_store"\n'
                       '        _pb_own=0; _unleashed_auth_entry "$_pb_entry" && _pb_own=1\n'
                       '    fi\n'
                       '    if [ "$_pb_own" = 0 ]; then\n')
    ROW_182_OLD = ('    _unleashed_scan_store "$_pb_store"\n'
                   '    if ! _unleashed_auth_entry "$_pb_entry"; then\n')

    #: Counting delegates for the two functions the post-scan calls, built by COPYING the shipped
    #: definitions (never paraphrasing them) exactly as row 7's stat wrapper does. `_ae_bound` is
    #: cleared at entry so the trap below can key on the window between ENT-1's stat and the open —
    #: the variable survives the previous call otherwise, and the trap then fires before the stat,
    #: where a substituted entry is simply the entry that gets validated (measured: the swap landed
    #: and BOTH builds still reported `created`).
    ROW_182_COUNT = (
        'if [ -n "${ZSH_VERSION:-}" ]; then functions -c _unleashed_auth_entry _uae_real; '
        'functions -c _unleashed_scan_store _uss_real; else '
        'eval "$(declare -f _unleashed_auth_entry | /usr/bin/sed \'1s/_unleashed_auth_entry/_uae_real/\')"; '
        'eval "$(declare -f _unleashed_scan_store | /usr/bin/sed \'1s/_unleashed_scan_store/_uss_real/\')"; fi\n'
        '_uae_n=0; _uss_n=0\n'
        '_unleashed_auth_entry() { unset _ae_bound; _uae_n=$(( _uae_n + 1 )); _uae_real "$@"; }\n'
        '_unleashed_scan_store() { _uss_n=$(( _uss_n + 1 )); _uss_real "$@"; }\n')
    #: What a CONCURRENT publisher of the same base does: replace the entry with an identical-content
    #: copy at a NEW inode. `cp -p` then `mv -f`, so the surviving entry is valid in every clause and
    #: only ENT-2b's inode binding rejects the object this process opened.
    ROW_182_SWAP = '/bin/cp -p "$_ae_p" "$_ae_p.swap" && /bin/mv -f "$_ae_p.swap" "$_ae_p"'
    #: The state, whether the trap fired, and how many times the store was scanned.
    ROW_182_OUT = ('trap - DEBUG\n'
                   'printf "%s|%s|%s" "$_UNLEASHED_POINTER_STATE" "${_tdone:-0}" "${_uss_n:-0}"')

    def _row_182_trap(self, nth):
        """Swap the entry inside the `nth` call to `_unleashed_auth_entry`, between ENT-1 and the open."""
        return ('[ -n "${BASH_VERSION:-}" ] && set -T\n'
                'trap \'if [ "${_uae_n:-0}" = ' + str(nth) + ' ] && [ -n "${_ae_bound:-}" ] '
                '&& [ -f "${_ae_p:-}" ] && [ ! -L "$_ae_p" ] && [ -z "${_tdone:-}" ]; then _tdone=1; '
                + self.ROW_182_SWAP + "; fi' DEBUG\n")

    def _row_182_concurrent(self, shell, srcs, trials, n):
        """`trials` rounds of `n` simultaneous publishers of ONE base into a FRESH store.

        Returns (repair-state count, the states). A repair state is `stale`, `failed` or `conflict`:
        every one of these processes publishes the SAME value, so `created`/`current` are the only
        correct answers and anything else is the race being reported to the user.

        THE START BARRIER IS LOAD-BEARING for the mutant arm, not decoration: spawned and left to
        start when they may, the sixty-four publishers overlap only partly and the pre-fix rate fell
        to 5 of 64 on one run (measured) — a population cell whose control can quietly stop failing.
        Each process spins on a gate file, so all `n` reach the publish within microseconds of each
        other; with it the pre-fix rate is 11-38 of 64 and the fixed one 0-2.
        """
        gate = os.path.join(self.home, "row182.gate")
        src = "".join(f'. "{s}"\n' for s in srcs)
        body = (src + f'while [ ! -e "{gate}" ]; do :; done\n'
                + f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n' + self.PSTATE)
        repair, states = 0, []
        for _ in range(trials):
            self._wipe()
            if os.path.exists(gate):
                os.unlink(gate)
            procs = [subprocess.Popen([shell, "-c", body], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True) for _ in range(n)]
            time.sleep(0.25)                      # every process is spinning on the gate by now
            open(gate, "w").close()
            out = [p.communicate(timeout=60)[0] for p in procs]
            states.extend(out)
            repair += sum(1 for s in out if s in ("stale", "failed", "conflict"))
        return repair, states

    def test_row_182_one_rescan_before_a_repair_state_is_reported(self):
        """Row 182 (codex, PR #67 pass 17 — reproduced): two ORDINARY hooks publishing the SAME base into a fresh store race each other — the second `mv` replaces the entry between the post-scan's stat and its open, ENT-2b's inode binding correctly rejects the object that was opened, and the publisher reported a repair state although the surviving entry is valid and both processes agree on its content. A `DEBUG` trap makes the interleaving deterministic by performing exactly that replacement (an identical-content copy at a new inode) inside one authentication: (i) swapped during the post-SCAN, the specification rescans and reports `created` while the mutation (the rescan removed) reports `stale`; (ii) swapped during the OWN-ENTRY check, the specification reports `created` and the mutation `failed`. EXACTLY ONE retry, counted through a delegating wrapper: one scan on a healthy publish in both builds, two on the repair path, never three. Two controls hold in both builds, so the retry converts the transient case only: a genuinely corrupt sibling entry still reports `stale` (and the specification still scans exactly twice), and two publishers of DIFFERENT bases still report `conflict`. Both shells. THE POPULATION MEASUREMENT IS NO LONGER PART OF THIS CELL: it moved to `test_row_182_population_the_rescan_converts_most_of_the_race`, opt-in behind `UNLEASHED_POPULATION_SAMPLING=1`, because it is a stochastic benchmark and it made this cell non-deterministic (COREDEV-2765). Everything above is deterministic and unconditional."""
        # Measured, both shells: (i) shipped `created|1|2`, mutant `stale|1|1`; (ii) shipped
        # `created|1|2`, mutant `failed|1|1`; healthy `created|0|1` in both; corrupt sibling
        # `stale|0|2` shipped and `stale|0|1` mutant; two bases `conflict|0|1` in both.
        other = os.path.join(self.home, "other-base")
        os.makedirs(other)
        os.chmod(other, 0o700)
        with open(PUB, encoding="utf-8") as fh:
            pub = fh.read()
        self.assertIn(self.ROW_182_SHIPPED, pub,
                      "the shipped publisher no longer rescans once before reporting a repair state "
                      "(PUB-9 E7b)")
        # Counted on the CALL, not on an indented spelling of it: `'    x'` is a substring of
        # `'        x'`, so summing two indentation-prefixed counts double-counts the deeper one.
        self.assertEqual(2, pub.count('_unleashed_scan_store "$_pb_store"'),
                         "the publisher does not scan the store exactly TWICE — E7b is one retry, "
                         "never a loop")
        mutant = with_mutation(self.ROW_182_SHIPPED, self.ROW_182_OLD, path=PUB)
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, READER, mutant), True)):
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    # (i) and (ii) — the deterministic interleavings. Call 1 is PUB-7's write-or-skip
                    # check (the entry does not exist yet, so it returns before the window opens),
                    # call 2 is the post-scan's, call 3 the own-entry check.
                    for nth, cell, mutant_state in ((2, "scan-phase swap", "stale"),
                                                    (3, "own-entry swap", "failed")):
                        self._wipe()
                        body = (self.ROW_182_COUNT + self._row_182_trap(nth)
                                + f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                                + self.ROW_182_OUT)
                        rc, out, err = self._run_182(shell, body, srcs)
                        self.assertNotEqual("TIMEOUT", rc, f"{tag} [{cell}]: the publisher hung")
                        self.assertTrue(out.split("|")[1] == "1",
                                        f"{tag} [{cell}]: the trap did not fire — the fixture is not the "
                                        f"finding: {out!r} {err!r}")
                        if not is_mutant:
                            self.assertEqual("created|1|2", out,
                                             f"{tag} [{cell}]: a valid surviving entry was reported as a "
                                             f"repair state, or the store was scanned other than twice: "
                                             f"{out!r} {err!r}")
                        else:
                            self.assertEqual(f"{mutant_state}|1|1", out,
                                             f"{tag} [{cell}]: the CONTROL did not fail — without the "
                                             f"rescan the transient replacement was not reported as a "
                                             f"repair state: {out!r} {err!r}")
                    # A healthy publish scans ONCE in both builds: the retry is on the repair path only.
                    self._wipe()
                    rc, out, err = self._run_182(shell, self.ROW_182_COUNT
                                                 + f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                                                 + self.ROW_182_OUT, srcs)
                    self.assertEqual("created|0|1", out, f"{tag}: a healthy publish: {out!r} {err!r}")
                    # CONTROL: a genuinely corrupt sibling entry still reports `stale` — the retry
                    # converts a transient replacement, never an entry that cannot authenticate.
                    self._wipe()
                    body = (self.ROW_182_COUNT
                            + f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                            + self._entry(t=other, mode="644")
                            + '_uae_n=0; _uss_n=0\n'
                            + f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                            + self.ROW_182_OUT)
                    rc, out, err = self._run_182(shell, body, srcs)
                    want = "stale|0|2" if not is_mutant else "stale|0|1"
                    self.assertEqual(want, out,
                                     f"{tag}: a corrupt sibling must still report `stale`, and the "
                                     f"specification must scan exactly twice doing it: {out!r} {err!r}")
                    # CONTROL: two publishers of DIFFERENT bases still report `conflict`, with no retry.
                    self._wipe()
                    body = (self.ROW_182_COUNT
                            + f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                            + '_uae_n=0; _uss_n=0\n'
                            + f'_unleashed_publish "{self.store}" "{other}" 2>/dev/null\n'
                            + self.ROW_182_OUT)
                    rc, out, err = self._run_182(shell, body, srcs)
                    self.assertEqual("conflict|0|1", out,
                                     f"{tag}: two bases must still conflict, without a rescan: {out!r} {err!r}")
        finally:
            os.unlink(mutant)

    #: Opt-in, and the reason is measured. COREDEV-2765: five ISOLATED runs of the combined cell on
    #: one unchanged tree gave four SKIPs and one PASS at 52.7-67.8s each, and under full-suite load
    #: the ticket recorded two consecutive FAILs on that same tree. Both outcomes come from the one
    #: stochastic sample below, and in a log neither is distinguishable from a real regression.
    #:
    #: THE DISCRIMINATION IS NOT MEASURED HERE. `test_row_182_one_rescan_before_a_repair_state_is_
    #: reported` proves it deterministically with a DEBUG trap, unconditionally, in both shells, and
    #: that cell runs first. What this one adds is the QUANTITATIVE claim — that the retry converts
    #: most of the population rather than only the interleaving the trap constructs. That is worth
    #: measuring and is not worth a non-deterministic verdict on every pull request.
    #:
    #: Concurrency, 8x8 per arm, in two regimes. WITHOUT a start barrier (processes spawned and left
    #: to start when they may): shipped bash 0,0,0,2 and zsh 1,1,2,3 across four runs; mutant bash
    #: 5,21,23,27 and zsh 19,24,29 — the 5 is why the barrier exists, a control that quietly stopped
    #: failing. WITH the barrier every process spins until one gate file appears: mutant bash
    #: 12,17,23,25 and zsh 25,31,34,35,38; shipped 0-2. The shipped arm is BOUNDED, not zero: a
    #: publisher that loses the race a SECOND time inside the rescan still reports the repair state,
    #: which is what "exactly one retry, never a loop" costs and what this cell records.
    POPULATION_SAMPLING = os.environ.get("UNLEASHED_POPULATION_SAMPLING") == "1"

    @unittest.skipUnless(POPULATION_SAMPLING,
                         "stochastic population benchmark; opt in with "
                         "UNLEASHED_POPULATION_SAMPLING=1 (COREDEV-2765)")
    def test_row_182_population_the_rescan_converts_most_of_the_race(self):
        """PUB-9 E7b, corroboration: over 64 concurrent publishers the rescan must bound the repair
        rate at <= 6 and beat the build without it. A BENCHMARK — the correctness claim is proved
        deterministically by the DEBUG-trap cell above, which is unconditional."""
        mutant = with_mutation(self.ROW_182_SHIPPED, self.ROW_182_OLD, path=PUB)
        try:
            for shell in SHELLS:
                # ── the population measurement: 8 trials of 8 concurrent publishers ───────────
                # THE POPULATION CELL RESAMPLES, because what it measures is a RACE and a race is not
                # on demand: measured, the mutant's rate over 64 publishers ranges 11-38 on a busy
                # machine and fell below 5 on a quiet one, which failed this cell on a build whose
                # shipped and mutant behaviour were both correct. A stochastic assertion that fails at
                # random is worse than none — it teaches everyone to re-run until green. So it takes up
                # to three samples and passes on the first that discriminates; only a mutant that never
                # produces the race in 192 publishers fails, which is the case this cell exists to catch.
                # The DETERMINISTIC cells above are what proves the rescan works; this one corroborates.
                # THE RACE GOT RARER BECAUSE THE CODE GOT FASTER. This cell samples a window — the gap
                # between the post-scan's stat and its open — and PF-2 cut the publish path by ~1.3x, which
                # shrinks exactly that window: measured, the same command passed 13/13 against the previous
                # build and 9/13 against this one, with the mutant producing 0-1 repair states per 192
                # publishers where this floor needs 5. That is the race becoming harder to observe, NOT the
                # rescan failing — the DETERMINISTIC cells above, which prove discrimination, run first and
                # always pass. So when five samples cannot make the mutant race at all, this cell SKIPS and
                # says so, rather than failing a correct build: a red test that means "your machine was
                # quiet" teaches everyone to re-run until green, and then nobody reads it.
                for _attempt in range(5):
                    ship, _ = self._row_182_concurrent(shell, (AUTH, STORE, READER, PUB), 8, 8)
                    mut, _ = self._row_182_concurrent(shell, (AUTH, STORE, READER, mutant), 8, 8)
                    if mut >= 5:
                        break
                else:
                    self.skipTest(
                        f"{shell}: five samples of 64 concurrent publishers produced at most {mut} repair "
                        f"states WITHOUT the rescan, so the population comparison has nothing to measure "
                        f"on this machine; the deterministic DEBUG-trap cells above already proved the "
                        f"discrimination and they ran")
                self.assertLessEqual(ship, 6,
                                     f"{shell}: {ship} of 64 concurrent publishers reported a repair state "
                                     f"WITH the rescan (measured range 0-3); the retry is not converting "
                                     f"the transient case")
                self.assertLess(ship, mut, f"{shell}: shipped {ship}, mutant {mut}")
        finally:
            os.unlink(mutant)

    @staticmethod
    def _run_182(shell, body, srcs, timeout=60):
        src = "".join(f'. "{s}"\n' for s in srcs) + body
        try:
            p = subprocess.run([shell, "-c", src], capture_output=True, text=True, timeout=timeout)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            return "TIMEOUT", "", ""

    # ── row 183 ───────────────────────────────────────────────────────────────────────────────

    #: E0, the publication opt-out — the ONLY protection that holds in both shells — and the mutation
    #: that removes it. There is no mutation of E1's HOME predicate that discriminates under zsh:
    #: that is the point of the row.
    ROW_183_E0 = '            if [ "${_UNLEASHED_PUBLISH_OK:-1}" = 0 ]; then\n'
    ROW_183_E0_GONE = '            if false; then\n'

    def test_row_183_the_publication_opt_out_is_the_protection_e1_cannot_be_under_zsh(self):
        """Row 183 (codex, PR #67 pass 17 — reproduced): zsh initialises `HOME` from the PASSWD DATABASE before any sourced line runs — `env -i /bin/zsh` reports `HOME=/Users/<u>` where `env -i /bin/bash` reports it unset (measured, and asserted here against the passwd entry) — so PUB-9 E1's "HOME is empty or not absolute" refusal is UNREACHABLE for an ABSENT `HOME` under zsh, and a harness that clears `HOME` to prevent persistent writes is protected in bash and not in zsh. That divergence is a STATED FACT of the arm, not a bug with a fix: no post-startup test can distinguish "zsh filled it in" from "the caller set HOME to the passwd value", and this row asserts it rather than mutating it — under `env -i`, with publication disabled so nothing is written, `_unleashed_home_ok` REFUSES in bash and ACCEPTS in zsh. E1 is still reachable in BOTH shells for a `HOME` that is set and EMPTY (`failed`, one diagnostic), which is asserted so the divergence is bounded to the absent case. THE PROTECTION IS THE EXPLICIT OPT-OUT, and that is what carries the mutant: with `_UNLEASHED_PUBLISH_OK=0` the specification publishes nothing and creates no store under a scratch `HOME` in both shells (`none`), while the mutation (E0 removed) publishes and leaves a store holding one entry. The honest control: without the opt-out both builds publish `created`, so the cell measures the opt-out and not a resolver that stopped working."""
        # Measured, both shells: (i) `env -i bash` HOME UNSET, `env -i zsh` HOME=<passwd>; an in-shell
        # `unset HOME` leaves it UNSET in BOTH, so the initialisation is a startup property.
        # (ii) `env -i` + E0: bash HOME_REFUSED, zsh HOME_OK, `none`, nothing written.
        # (iii) HOME='' : `failed` + one diagnostic in both shells. (iv) opt-out: shipped
        # `none` with no store; mutant `created` with one entry. (v) no opt-out: `created` in both.
        # The real store is asserted absent after the `env -i` cells: those run with the passwd HOME
        # in force under zsh, and only E0 keeps them from writing there.
        real = os.path.join(pwd.getpwuid(os.getuid()).pw_dir, ".claude", "unleashed-mail")
        real_before = os.path.exists(real)
        base = os.path.join(self.home, "base-183")
        os.makedirs(base)
        os.chmod(base, 0o700)
        machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
        # THE FIX HERE IS A STATED FACT, so the stating is what this row pins first: E1's precondition
        # must SAY it cannot detect an absent HOME under zsh and must name the opt-out that can. A
        # predicate that silently implies otherwise is the defect, and it has no behavioural mutant.
        with open(PATHS_C4, encoding="utf-8") as fh:
            paths = fh.read()
        self.assertIn("IT CANNOT DETECT AN ABSENT `HOME` UNDER ZSH", paths,
                      "PUB-9 E1's precondition no longer states the zsh divergence it cannot detect")
        self.assertIn("_UNLEASHED_PUBLISH_OK=0", paths,
                      "E1's precondition no longer names the opt-out that IS the protection")
        mutant = with_mutation(self.ROW_183_E0, self.ROW_183_E0_GONE, path=PATHS_C4)
        try:
            spec_root = self._shadow("spec183", dict(machinery, **{"paths.sh": PATHS_C4}))
            mut_root = self._shadow("mut183", dict(machinery, **{"paths.sh": mutant}))
            # (i) the shells' own HOME initialisation, at startup and after an explicit unset.
            for shell, want in (("/bin/bash", "UNSET"), ("/bin/zsh", pwd.getpwuid(os.getuid()).pw_dir)):
                p = subprocess.run([shell, "-c", 'printf "%s" "${HOME-UNSET}"'],
                                   capture_output=True, text=True, env={})
                self.assertEqual(want, p.stdout,
                                 f"{shell}: `env -i` HOME is {p.stdout!r}, not {want!r} — the arm "
                                 f"divergence this row states does not hold on this machine")
                p = subprocess.run([shell, "-c", 'unset HOME 2>/dev/null; printf "%s" "${HOME-UNSET}"'],
                                   capture_output=True, text=True)
                self.assertEqual("UNSET", p.stdout,
                                 f"{shell}: an in-shell `unset HOME` was refilled — the divergence is "
                                 f"not confined to startup: {p.stdout!r}")
            # (ii) the predicate's verdict under `env -i`, with E0 in force so nothing is written.
            for shell, want in (("/bin/bash", "HOME_REFUSED"), ("/bin/zsh", "HOME_OK")):
                p = subprocess.run(
                    [shell, "-c", f'. "{spec_root}/paths.sh"; _unleashed_home_ok && printf HOME_OK || printf HOME_REFUSED; '
                                  'printf "|%s" "$_UNLEASHED_POINTER_STATE"'],
                    capture_output=True, text=True,
                    env={"_UNLEASHED_PUBLISH_OK": "0", "CLAUDE_PLUGIN_DATA": base})
                self.assertEqual(f"{want}|none", p.stdout,
                                 f"{shell}: E1's precondition under `env -i`: {p.stdout!r} {p.stderr!r}")
            self.assertEqual(real_before, os.path.exists(real),
                             "an `env -i` cell wrote to the REAL store — the opt-out did not hold")
            # (iii) E1 is still reachable in both shells for a HOME that is set and EMPTY.
            for shell in SHELLS:
                p = subprocess.run([shell, "-c", f'. "{spec_root}/paths.sh"; ' + self.PSTATE],
                                   capture_output=True, text=True,
                                   env={"HOME": "", "CLAUDE_PLUGIN_DATA": base, "PATH": "/usr/bin:/bin"})
                self.assertEqual("failed", p.stdout, f"{shell}: an empty HOME did not take E1: {p.stdout!r}")
                self.assertEqual(1, len(self._diags(p.stderr)), f"{shell}: {p.stderr!r}")
            # (iv) THE OPT-OUT — and (v) the honest control beside it.
            for label, root in (("shipped", spec_root), ("mutant", mut_root)):
                for shell in SHELLS:
                    for optout in (True, False):
                        h = os.path.join(self.home, f"h183-{label}-{os.path.basename(shell)}-{int(optout)}")
                        shutil.rmtree(h, ignore_errors=True)
                        os.makedirs(h)
                        os.chmod(h, 0o700)
                        env = {"HOME": h, "CLAUDE_PLUGIN_DATA": base, "PATH": "/usr/bin:/bin"}
                        if optout:
                            env["_UNLEASHED_PUBLISH_OK"] = "0"
                        p = subprocess.run([shell, "-c", f'. "{root}/paths.sh"; ' + self.PSTATE],
                                           capture_output=True, text=True, env=env)
                        st = os.path.join(h, ".claude", "unleashed-mail", "bases")
                        names = sorted(f for f in os.listdir(st)) if os.path.isdir(st) else []
                        tag = f"{shell} {label} {'opt-out' if optout else 'no opt-out'}"
                        if not optout:
                            self.assertEqual("created", p.stdout,
                                             f"{tag}: the resolver did not publish at all — the opt-out "
                                             f"cells above would measure nothing: {p.stdout!r} {p.stderr!r}")
                            self.assertEqual(1, len(names), f"{tag}: {names}")
                        elif label == "shipped":
                            self.assertEqual("none", p.stdout,
                                             f"{tag}: `_UNLEASHED_PUBLISH_OK=0` did not suppress the "
                                             f"publish: {p.stdout!r} {p.stderr!r}")
                            self.assertFalse(os.path.exists(os.path.join(h, ".claude")),
                                             f"{tag}: the opt-out composed a ${{HOME}} path anyway: {names}")
                            self.assertEqual("", p.stderr, f"{tag}: E0 must be silent: {p.stderr!r}")
                        else:
                            self.assertEqual("created", p.stdout,
                                             f"{tag}: the CONTROL did not fail — publication was still "
                                             f"suppressed with E0 removed: {p.stdout!r} {p.stderr!r}")
                            self.assertEqual(1, len(names),
                                             f"{tag}: the CONTROL did not write a store: {names}")
        finally:
            os.unlink(mutant)
        self.assertEqual(real_before, os.path.exists(real),
                         "this row wrote to the REAL plugin-state store")

    # ── row 184 ───────────────────────────────────────────────────────────────────────────────

    #: The re-application of E2's constraints to the FOLDED value — the `case` block, head through its
    #: `esac`. Sliced, not quoted: the block carries a paragraph that will be edited again.
    ROW_184_HEAD = '    case "$_pb_folded" in\n'
    ROW_184_TAIL = '    esac\n'
    #: Values that FOLD to the filesystem root. Both exist, so neither is refused before the fold: `/.`
    #: drops a `.` segment and `/Users/..` pops the only segment it has.
    ROW_184_ROOT = ("/.", "/Users/..")

    def _row_184_block(self):
        with open(PUB, encoding="utf-8") as fh:
            text = fh.read()
        assert text.count(self.ROW_184_HEAD) == 1, (
            "the publisher does not re-apply E2's constraints to the FOLDED value exactly once "
            "(PUB-9 E2b) — without them a value that folds to `/` writes an entry its own post-scan "
            "then refuses, and every later reader is `stale`")
        i = text.index(self.ROW_184_HEAD)
        return text[i:text.index(self.ROW_184_TAIL, i) + len(self.ROW_184_TAIL)]

    #: Row 185's mutation: the ST-3 guard the publisher applies to an EXISTING store, via the reader's
    #: own predicate. Removing it restores the state the Fable pre-merge review of 22f9cdf found.
    ROW_185_GUARD = ('    if [ -e "$_pb_store" ] || [ -L "$_pb_store" ]; then\n'
                     '        if ! _unleashed_store_ok "$_pb_store"; then\n'
                     '            _unleashed_pub_failed "the plugin-state store is not a usable 0700 directory"; return 0\n'
                     '        fi\n'
                     '    fi\n')

    @unittest.skipUnless(DARWIN, "the store's chain and ACL arms are Darwin-only in this build")
    def test_row_185_the_publisher_applies_st_3_to_an_existing_store(self):
        """Row 185 (Fable pre-merge review of 22f9cdf — reproduced): ST-3 says `bases/` is acceptable
        only at EXACTLY 0700 and that a store in any other state is refused, "never chmod'ed, never
        repaired, never deleted, AND NO FILE IS WRITTEN INTO IT", and PUB-9 E4 says the publisher
        refuses. `_unleashed_create_store` authenticates the CHAIN, which refuses group- or
        other-WRITABLE components — it never applied the exact-0700 test to `bases/` itself. So a store
        at 0750, 0755 or 0701 (readable, not writable) was ACCEPTED and WRITTEN INTO while the reader's
        `_unleashed_store_ok`, which does apply ST-3, refused it: the publisher reported `created` with
        ZERO diagnostics and one entry on disk, and every later reader reported `ok=0 state=stale`,
        permanently and silently. The specification refuses with one diagnostic and NOTHING written;
        under the mutation the entry is written and the disagreement returns.

        The fix shares ONE predicate between publisher and reader rather than restating the rule, which
        is why this row asserts the two sides AGREE: a second copy of a rule is a second thing to drift.
        0770 is included as a control — it was already refused, by the chain's group-writable clause,
        so it discriminates nothing here and is asserted equal in both builds.
        """
        mutant = with_mutation(self.ROW_185_GUARD, "", path=PUB)
        try:
            for shell in SHELLS:
                for pub_file, is_mutant in ((PUB, False), (mutant, True)):
                    for mode, discriminating in (("700", False), ("750", True), ("755", True),
                                                 ("701", True), ("770", False)):
                        self._wipe()
                        os.makedirs(self.store)
                        os.chmod(os.path.join(self.home, ".claude"), 0o700)
                        os.chmod(os.path.dirname(self.store), 0o700)
                        os.chmod(self.store, int(mode, 8))
                        srcs = (AUTH, STORE, READER, pub_file)
                        body = (f'export HOME="{self.home}"\n'
                                f'_unleashed_publish "{self.store}" "{self.target}" 2>/dev/null\n'
                                'printf "%s" "$_UNLEASHED_POINTER_STATE"\n')
                        rc, out, err = run_shell(shell, body, sources=srcs)
                        entries = [f for f in os.listdir(self.store) if f.startswith("base.")]
                        tag = f"{shell} mode={mode} {'mutant' if is_mutant else 'shipped'}"
                        if mode == "700":
                            self.assertEqual("created", out, f"{tag}: a healthy 0700 store must publish: {err}")
                            self.assertEqual(1, len(entries), f"{tag}")
                        elif not discriminating:
                            self.assertEqual("failed", out,
                                             f"{tag}: 0770 is group-writable and the CHAIN refuses it in "
                                             f"both builds: {err}")
                            self.assertEqual([], entries, f"{tag}")
                        elif is_mutant:
                            self.assertEqual("created", out,
                                             f"{tag}: the CONTROL did not fail — without the ST-3 guard a "
                                             f"{mode} store must be accepted, which is the defect: {err}")
                            self.assertEqual(1, len(entries),
                                             f"{tag}: the CONTROL did not fail — no entry was written into "
                                             f"a {mode} store")
                        else:
                            self.assertEqual("failed", out,
                                             f"{tag}: ST-3 requires a {mode} store be refused: {err}")
                            self.assertEqual([], entries,
                                             f"{tag}: ST-3 requires that NO FILE be written into a {mode} "
                                             f"store, and one was")
        finally:
            os.unlink(mutant)

    def test_row_184_the_folded_value_faces_e2s_constraints_again(self):
        """Row 184 (codex, PR #67 pass 20 — reproduced): E2's constraints were applied to the caller's SPELLING, and the fold can produce a shape they already rejected — `/.` and `/Users/..` both fold to `/`, which is absolute and has no trailing segment but IS a trailing slash. The specification re-applies them to the FOLDED value and refuses before anything is written: `failed`, one diagnostic naming the root, and an EMPTY store, so a later reader reports `none`; under the mutation (the re-application removed) the publisher derives the key of `/`, writes `base._s` holding `/`, and its own post-scan then refuses that entry by TGT-1's trailing-slash clause — the publish reports `failed` HAVING LEFT THE ENTRY BEHIND, and every later reader is `stale` until someone deletes it by hand. **The state string is `failed` in BOTH builds**, so this row's oracle is the STORE and the reader's verdict, never the word: "failed with nothing written" and "failed with a poison entry" are the same word and opposite outcomes. Two positive controls, both in both builds: `<h>/safe/..`, a `..` that folds to a REAL directory, still publishes `created`, and the three ordinary spellings still fold to ONE entry with the reader resolving — so the refusal is scoped to the shape that cannot be an entry, not to `..` in general. Both shells."""
        # Measured, both shells: shipped `/.` and `/Users/..` -> `failed`, 0 entries, reader
        # `0 unresolved none`, diagnostic "the plugin-data base normalises to the filesystem root";
        # mutant -> `failed`, ONE entry `base._s` whose content is `/`, reader `0 unresolved stale`,
        # diagnostic "this process's own plugin-state entry is missing or unusable" (P1 — the publisher
        # refusing the entry it had just written). Controls in both builds: `<h>/safe/..` `created` with
        # the entry naming `<h>`; `<h>/safe/../safe` `created`; three spellings `created current current`
        # with ONE entry and `1 pointer none`.
        block = self._row_184_block()
        self.assertIn('_unleashed_pub_failed "the plugin-data base normalises to the filesystem root"', block,
                      "the folded value no longer faces E2's root/trailing-slash constraints (PUB-9 E2b)")
        safe = os.path.join(self.home, "safe")
        os.makedirs(safe)
        os.chmod(safe, 0o700)
        d = os.path.join(self.home, "d184")
        sub = os.path.join(d, "sub")
        os.makedirs(sub)
        os.makedirs(os.path.join(d, "x"))
        for p in (d, sub, os.path.join(d, "x")):
            os.chmod(p, 0o700)
        mutant = with_mutation(block, "", path=PUB)
        try:
            for shell in SHELLS:
                for srcs, is_mutant in (((AUTH, STORE, READER, PUB), False),
                                        ((AUTH, STORE, READER, mutant), True)):
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    for value in self.ROW_184_ROOT:
                        self._wipe()
                        rc, out, err = run_shell(shell, f'_unleashed_publish "{self.store}" "{value}"\n'
                                                 + self.PSTATE, sources=srcs)
                        # THE STATE IS THE SAME IN BOTH BUILDS — asserted, so the row cannot be read as
                        # discriminating on a word it does not discriminate on.
                        self.assertEqual("failed", out, f"{tag} [{value}]: {out!r} {err!r}")
                        self.assertEqual(1, len(self._diags(err)), f"{tag} [{value}]: {err!r}")
                        rc2, out2, err2 = run_shell(shell, f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                                    + self.OUTP, sources=srcs)
                        if not is_mutant:
                            self.assertEqual([], self._names(),
                                             f"{tag} [{value}]: a refusal wrote an entry: {self._names()}")
                            self.assertIn("normalises to the filesystem root", err, f"{tag}: {err!r}")
                            self.assertEqual("0 unresolved none", out2,
                                             f"{tag} [{value}]: {out2!r} {err2!r}")
                        else:
                            self.assertEqual(["base._s"], self._names(),
                                             f"{tag} [{value}]: the CONTROL did not fail — the folded "
                                             f"root was refused without the re-application: {self._names()}")
                            with open(os.path.join(self.store, "base._s"), encoding="utf-8") as fh:
                                self.assertEqual("/\n", fh.read(), f"{tag} [{value}]: entry content")
                            self.assertEqual("0 unresolved stale", out2,
                                             f"{tag} [{value}]: the poison entry did not poison the "
                                             f"read: {out2!r} {err2!r}")
                    # CONTROL 1: a `..` that folds to a REAL directory still publishes, in both builds.
                    for value, want_content in ((f"{safe}/..", self.home), (f"{safe}/../safe", safe)):
                        self._wipe()
                        rc, out, err = run_shell(shell, f'_unleashed_publish "{self.store}" "{value}"\n'
                                                 + self.PSTATE, sources=srcs)
                        self.assertEqual("created", out,
                                         f"{tag} [{value}]: a legitimate `..` was refused: {out!r} {err!r}")
                        names = self._names()
                        self.assertEqual(1, len(names), f"{tag} [{value}]: {names}")
                        with open(os.path.join(self.store, names[0]), encoding="utf-8") as fh:
                            self.assertEqual(want_content + "\n", fh.read(),
                                             f"{tag} [{value}]: the entry does not name the folded directory")
                    # CONTROL 2: the ordinary spellings still fold to ONE entry and still resolve.
                    self._wipe()
                    states = [run_shell(shell, f'_unleashed_publish "{self.store}" "{v}" 2>/dev/null\n'
                                        + self.PSTATE, sources=srcs)[1]
                              for v in (sub, f"{d}/./sub", f"{d}/x/../sub")]
                    self.assertEqual(["created", "current", "current"], states, f"{tag}: {states}")
                    self.assertEqual(1, len(self._names()), f"{tag}: {self._names()}")
                    rc, out, err = run_shell(shell, f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                             + self.OUTP, sources=srcs)
                    self.assertEqual("1 pointer none", out, f"{tag}: {out!r} {err!r}")
        finally:
            os.unlink(mutant)

    # ── row 186 ───────────────────────────────────────────────────────────────────────────────

    #: The scan's `failglob` guard — sliced from the head of its paragraph through the one-liner that
    #: saves and clears the option — and the restore, which the mutation drops with it. SLICED, not
    #: quoted: the paragraph is prose and will be edited again, and a quoted anchor would strand this
    #: row on a comment rewrite (rows 180 and 184's convention).
    ROW_186_HEAD = "        # `failglob` IS A SEPARATE OPTION AND IT IS FATAL HERE."
    ROW_186_TAIL = ('        if shopt -q failglob 2>/dev/null; then _ss_failglob=1; '
                    'shopt -u failglob 2>/dev/null || :; fi\n')
    ROW_186_RESTORE = '    [ "${_ss_failglob:-0}" = 1 ] && shopt -s failglob 2>/dev/null || :\n'
    #: Turn `failglob` on where the shell HAS the option. zsh has no such option at all — measured:
    #: `shopt` is not a zsh builtin (`command not found: shopt`) and `setopt failglob` answers
    #: `no such option: failglob` — so the zsh arm of every cell below runs with the option ABSENT and
    #: is asserted EQUAL in both builds rather than claimed to discriminate.
    ROW_186_ON = "shopt -s failglob 2>/dev/null || :\n"
    #: The FUNCTIONAL probe for "the caller's `failglob` is still in force", run in a SUBSHELL because
    #: the option's whole effect is to destroy the command list that expands an unmatched pattern.
    #: NOT `shopt -q failglob`: row 179's lesson is that an option's NAME and its EFFECT are different
    #: things. Under zsh it always answers GLOB-FAILED — the default `nomatch` makes every unmatched
    #: glob an error there — so it discriminates in bash ONLY, which cell (iv) proves by producing
    #: GLOB-OK from it under bash and asserts equal-in-both-builds under zsh.
    ROW_186_PROBE = ('( for _p186 in /nonexistent-186/base.*; do :; done ) 2>/dev/null '
                     '&& printf "GLOB-OK|" || printf "GLOB-FAILED|"\n')
    #: The store-level tuple with the UNSET case spelled out. The defect this row measures does not
    #: give a WRONG answer, it gives NO ANSWER — and `"$_UNLEASHED_BASE_OK"` renders unset and empty
    #: identically, so an oracle built on the class's own OUTP would read the kill as `"  "` and could
    #: not tell it from a resolver that set every variable to the empty string.
    ROW_186_OUT = ('printf "%s %s %s" "${_UNLEASHED_BASE_OK-U}" "${_UNLEASHED_BASE_SOURCE-U}" '
                   '"${_UNLEASHED_POINTER_STATE-U}"')
    #: The same tuple for the paths.sh route, which is what a hook actually runs.
    ROW_186_PATHS_OUT = ('printf "%s|%s|%s" "${_UNLEASHED_BASE_OK-U}" "${_UNLEASHED_BASE_SOURCE-U}" '
                        '"${_UNLEASHED_POINTER_STATE-U}"')

    def _row_186_mutant(self):
        block = self._slice(READER, self.ROW_186_HEAD, self.ROW_186_TAIL)
        first = with_mutation(block, "", path=READER)
        try:
            return with_mutation(self.ROW_186_RESTORE, "", path=first)
        finally:
            os.unlink(first)

    def test_row_186_the_store_scan_neutralises_failglob_as_well_as_noglob(self):
        """Row 186 (codex, PR #67 pass 23 — reproduced): `failglob` is a SEPARATE bash option from the `noglob` row 179 fixed, and on an authenticated but EMPTY store it is FATAL, not merely wrong — bash aborts the whole command list on the unmatched `<store>/base.*` before the loop can apply rule 0's vanished-entry test, so `_unleashed_scan_store` never returns and the ordered reader never sets a single protocol variable. Measured through the paths.sh route a hook actually runs: the specification answers `0|unresolved|none` with the one "no plugin-state entry is present" notice, while the mutant (the `failglob` save/clear and its restore removed, `noglob` untouched) leaves `_UNLEASHED_BASE_OK`, `_UNLEASHED_BASE_SOURCE`, `_UNLEASHED_POINTER_STATE` and `_UNLEASHED_BASE_RESOLVED` ALL UNSET, emits NO diagnostic, and prints bash's own `no match:` line naming the store — a consumer that calls `unleashed_base_ok` then reads an unset variable, and under `set -e` the sourcing shell EXITS (rc=1, no output at all). bash only: zsh has no `failglob`, so its arm is asserted EQUAL in both builds rather than claimed to discriminate. Three cells hold in BOTH builds so nothing is bought with a regression: the caller's `failglob` is still in force after the read (asserted FUNCTIONALLY, in a subshell, because the option's effect is to kill the shell that expands the pattern), a caller who never set it does NOT acquire it, and a HEALTHY store still resolves `1 pointer none` under `failglob` — the row is scoped to the empty store, which is what a first session has."""
        # Measured, both shells: (i) direct `_unleashed_read_store`, empty store, failglob on —
        # shipped `0 unresolved none` + 1 diagnostic in both shells; mutant bash `U U U`, ZERO
        # diagnostics, `no match:` on stderr; mutant zsh `0 unresolved none` + 1 diagnostic (equal).
        # (ii) paths.sh — shipped `0|unresolved|none` + 1 diagnostic; mutant bash `U|U|U`, 0
        # diagnostics, `no match:`; mutant zsh equal to shipped. (iii) `set -e` — shipped rc=0 with the
        # tuple; mutant bash rc=1 and EMPTY stdout, the shell gone; mutant zsh equal. (iv) the probe:
        # `GLOB-FAILED|` after the read in both builds when the caller had failglob, `GLOB-OK|` in bash
        # when the caller did not (so the probe discriminates), `GLOB-FAILED|` in zsh either way.
        # (v) a healthy store: `1 pointer none` in all four arms.
        # THE SHIPPED SHAPE FIRST (rows 178/179's convention), so a scan that stops guarding `failglob`
        # fails HERE — on the rule — and not inside `with_mutation` on an anchor that stopped matching.
        with open(READER, encoding="utf-8") as fh:
            shipped = fh.read()
        self.assertIn("if shopt -q failglob 2>/dev/null; then _ss_failglob=1;", shipped,
                      "the shipped scan does not save and clear the caller's `failglob` (RD-9)")
        self.assertIn(self.ROW_186_RESTORE, shipped,
                      "the shipped scan does not restore the caller's `failglob` (RD-9)")
        # zsh HAS NO SUCH OPTION — the stated fact the zsh arm rests on, measured rather than assumed.
        p = subprocess.run(["/bin/zsh", "-c", "setopt failglob"], capture_output=True, text=True)
        self.assertNotEqual(0, p.returncode, "zsh accepted `setopt failglob` — the zsh arm of this row "
                                             "is asserted equal on the premise that it cannot")
        self.assertIn("no such option", p.stderr, f"zsh: {p.stderr!r}")
        real = os.path.join(pwd.getpwuid(os.getuid()).pw_dir, ".claude", "unleashed-mail")
        real_before = os.path.exists(real)
        mutant = self._row_186_mutant()
        no_restore = with_mutation(self.ROW_186_RESTORE, "", path=READER)
        try:
            machinery = {f: os.path.join(LIBDIR, f) for f in MACHINERY_P7}
            roots = {
                "shipped": self._shadow("spec186", dict(machinery, **{"paths.sh": PATHS_C4})),
                "mutant": self._shadow("mut186", dict(machinery, **{
                    "plugin-state-reader.sh": mutant, "paths.sh": PATHS_C4})),
            }
            for shell in SHELLS:
                bash = shell == "/bin/bash"
                for srcs, label in (((AUTH, STORE, READER, PUB), "shipped"),
                                    ((AUTH, STORE, mutant, PUB), "mutant")):
                    is_mutant = label == "mutant"
                    kills = is_mutant and bash          # the defect is bash-only
                    tag = f"{shell} {label}"
                    # (i) an EMPTY authenticated store read by a caller who set `failglob`.
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + self.ROW_186_ON
                                             + f'_unleashed_read_store "{self.store}"\n'
                                             + self.ROW_186_OUT, sources=srcs)
                    if not kills:
                        self.assertEqual("0 unresolved none", out,
                                         f"{tag}: an empty store did not resolve under failglob: "
                                         f"{out!r} {err!r}")
                        self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
                    else:
                        self.assertEqual("U U U", out,
                                         f"{tag}: the CONTROL did not fail — the unmatched pattern no "
                                         f"longer aborted the scan and the reader still answered: "
                                         f"{out!r} {err!r}")
                        self.assertEqual([], self._diags(err),
                                         f"{tag}: the CONTROL did not fail — the kill emitted a "
                                         f"diagnostic, so it was not a kill: {err!r}")
                        self.assertIn("no match:", err,
                                      f"{tag}: bash did not report the failed expansion: {err!r}")
                    # (ii) THE HOOK ROUTE — paths.sh, sourced, with a scratch HOME and no
                    # CLAUDE_PLUGIN_DATA, which is exactly step 2 of the resolver.
                    h = os.path.join(self.home, f"h186-{label}-{os.path.basename(shell)}")
                    shutil.rmtree(h, ignore_errors=True)
                    bases = os.path.join(h, ".claude", "unleashed-mail", "bases")
                    os.makedirs(bases)
                    for d in (h, os.path.dirname(os.path.dirname(bases)),
                              os.path.dirname(bases), bases):
                        os.chmod(d, 0o700)
                    p = subprocess.run(
                        [shell, "-c", self.ROW_186_ON + f'. "{roots[label]}/paths.sh"\n'
                         + self.ROW_186_PATHS_OUT],
                        capture_output=True, text=True, env={"HOME": h, "PATH": "/usr/bin:/bin"})
                    if not kills:
                        self.assertEqual("0|unresolved|none", p.stdout,
                                         f"{tag}: the hook route did not resolve an empty store under "
                                         f"failglob: {p.stdout!r} {p.stderr!r}")
                        self.assertEqual(1, len(self._diags(p.stderr)), f"{tag}: {p.stderr!r}")
                    else:
                        self.assertEqual("U|U|U", p.stdout,
                                         f"{tag}: the CONTROL did not fail — the hook route still set "
                                         f"the protocol variables: {p.stdout!r} {p.stderr!r}")
                        self.assertEqual([], self._diags(p.stderr),
                                         f"{tag}: the CONTROL did not fail: {p.stderr!r}")
                        self.assertIn("no match:", p.stderr, f"{tag}: {p.stderr!r}")
                    # (iii) UNDER `set -e` THE SHELL ITSELF GOES.
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + "set -e\n" + self.ROW_186_ON
                                             + f'_unleashed_read_store "{self.store}"\n'
                                             + self.ROW_186_OUT, sources=srcs)
                    if not kills:
                        self.assertEqual(0, rc, f"{tag}: `set -e` aborted a healthy read: {err!r}")
                        self.assertEqual("0 unresolved none", out, f"{tag}: {out!r} {err!r}")
                    else:
                        self.assertNotEqual(0, rc,
                                            f"{tag}: the CONTROL did not fail — the sourcing shell "
                                            f"survived `set -e`: rc={rc} {out!r} {err!r}")
                        self.assertEqual("", out,
                                         f"{tag}: the CONTROL did not fail — the shell was still "
                                         f"alive to print: {out!r}")
                    # (iv) THE CALLER'S OPTION SURVIVES — in BOTH builds, so the fix is not bought
                    # with a regression; and the probe is shown to be able to answer GLOB-OK.
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + self.ROW_186_ON
                                             + f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                             + self.ROW_186_PROBE + self.ROW_186_OUT, sources=srcs)
                    self.assertTrue(out.startswith("GLOB-FAILED|"),
                                    f"{tag}: the scan cleared the caller's failglob: {out!r}")
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore()
                                             + f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                             + self.ROW_186_PROBE + self.ROW_186_OUT, sources=srcs)
                    want = "GLOB-OK|" if bash else "GLOB-FAILED|"
                    self.assertTrue(out.startswith(want),
                                    f"{tag}: a caller who never set failglob {'acquired it' if bash else 'diverged'}"
                                    f" — under bash this is also the proof the probe discriminates: {out!r}")
                    self.assertTrue(out.endswith("0 unresolved none"), f"{tag}: {out!r} {err!r}")
                    # (v) THE HONEST CONTROL: a HEALTHY store resolves under failglob in both builds —
                    # the glob matches, so nothing in this row is about a store that has an entry.
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + self._entry() + self.ROW_186_ON
                                             + f'_unleashed_read_store "{self.store}"\n'
                                             + self.ROW_186_OUT, sources=srcs)
                    self.assertEqual("1 pointer none", out,
                                     f"{tag}: a healthy store did not resolve under failglob: "
                                     f"{out!r} {err!r}")
                    self.assertEqual([], self._diags(err), f"{tag}: {err!r}")
                # (vi) THE RESTORE GETS ITS OWN MUTATION. Cell (iv) above holds in both builds — the
                # whole-guard mutant never clears the option, so it has nothing to put back and the
                # cell cannot see the restore. Measured with a per-mutation sweep, not assumed: with
                # the restore line alone removed, a bash caller who had `failglob` loses it across an
                # ordinary read, which is the same class of defect pointing at the CALLER instead of
                # at the store.
                for rd, label in ((READER, "shipped"), (no_restore, "no-restore")):
                    self._wipe()
                    rc, out, err = run_shell(shell, self._mkstore() + self.ROW_186_ON
                                             + f'_unleashed_read_store "{self.store}" 2>/dev/null\n'
                                             + self.ROW_186_PROBE + self.ROW_186_OUT,
                                             sources=(AUTH, STORE, rd, PUB))
                    if not bash:
                        self.assertTrue(out.startswith("GLOB-FAILED|"),
                                        f"{shell} {label}: the zsh arm must be equal in both builds "
                                        f"— it has no `failglob` to lose: {out!r}")
                    elif label == "shipped":
                        self.assertTrue(out.startswith("GLOB-FAILED|"),
                                        f"{shell}: the scan did not restore the caller's failglob: {out!r}")
                    else:
                        self.assertTrue(out.startswith("GLOB-OK|"),
                                        f"{shell}: the CONTROL did not fail — the caller's `failglob` "
                                        f"survived without the restore line: {out!r}")
                    self.assertTrue(out.endswith("0 unresolved none"), f"{shell} {label}: {out!r} {err!r}")
        finally:
            os.unlink(mutant)
            os.unlink(no_restore)
        self.assertEqual(real_before, os.path.exists(real),
                         "this row wrote to the REAL plugin-state store")

    # ── row 187 ───────────────────────────────────────────────────────────────────────────────

    #: The encoder's `nocasematch` guard and its restore, quoted exactly — two lines of CODE, not
    #: prose, so a comment rewrite cannot strand them and a code rewrite SHOULD fail here loudly.
    ROW_187_GUARD = ('    _uk_nocase=0\n'
                     '    if [ -z "${ZSH_VERSION:-}" ] && shopt -q nocasematch 2>/dev/null; then\n'
                     '        _uk_nocase=1; shopt -u nocasematch 2>/dev/null || :\n'
                     '    fi\n')
    ROW_187_RESTORE = '    [ "${_uk_nocase:-0}" = 1 ] && shopt -s nocasematch 2>/dev/null || :\n'
    ROW_187_ON = "shopt -s nocasematch 2>/dev/null || :\n"
    #: The FUNCTIONAL probe for `nocasematch` — a `case` that can only match with the option on. Not
    #: `shopt -q`: this row is about what `case` DOES, so what `case` does is what is measured.
    ROW_187_PROBE = 'case ABC in abc) printf "NOCASE-ON|" ;; *) printf "NOCASE-OFF|" ;; esac\n'
    #: THE ORACLE IS THE KEYS. `/a` and `/A` are the collision, and `/café` shows the blast radius:
    #: EVERY lowercase letter takes an upper-case arm, so the damage is not one pair.
    ROW_187_KEYS = ('_unleashed_key /a; printf "%s|" "$_UNLEASHED_KEY"\n'
                    '_unleashed_key /A; printf "%s|" "$_UNLEASHED_KEY"\n'
                    '_u187=$(printf %b "/caf\\xc3\\xa9")\n'
                    '_unleashed_key "$_u187"; printf "%s" "$_UNLEASHED_KEY"\n')
    #: The canonical answer — what zsh gives, what bash gives with the option off, and what the
    #: specification gives with it on.
    ROW_187_CANON = "_sa|_s_ca|_scaf_xc3_xa9"

    def test_row_187_the_encoders_case_arms_are_forced_case_sensitive(self):
        """Row 187 (codex, PR #67 pass 23 — reproduced): the encoder's walk is a `case` with one arm per UPPER-case letter, and bash's `nocasematch` makes those arms match the LOWER-case bytes too — so with the option inherited from the caller `/a` and `/A` BOTH encode to `_s_ca` and ENC-1's injectivity, which every later step assumes, is simply gone. It is not one pair: `/café` encodes to `_s_cc_ca_cf_xc3_xa9` under the mutation, every lower-case letter having taken an upper-case arm. The user-visible consequence is a store that disagrees with itself — measured end to end, the publisher derives the wrong key, authenticates its OWN wrong key and reports `created` with zero diagnostics, and then every ordinary hook (which has no `nocasematch`) computes the canonical key, finds the ENT-3 name/content pair inconsistent and reports `0 unresolved stale`, permanently and silently. THE ORACLE IS THE KEYS, not that nothing died: every cell here "survives" in both builds. A SECOND mutation pins the other half of the guard — with the restore alone removed the keys are right and the CALLER's `nocasematch` is left switched off, which is the same class of defect pointing the other way. Both shells: zsh has no `nocasematch` for `case`, so its arm is asserted EQUAL in both builds, and the honest control is bash with the option OFF, where every build agrees on the canonical keys."""
        # Measured, both shells: (i) bash + nocasematch — shipped `_sa|_s_ca|_scaf_xc3_xa9`, mutant
        # `_s_ca|_s_ca|_s_cc_ca_cf_xc3_xa9`; zsh identical in both builds. (ii) end-to-end — shipped
        # `created` then `1 pointer none` with 0 diagnostics; mutant bash `created` then
        # `0 unresolved stale` with 1 diagnostic; mutant zsh equal to shipped. (iii) the restore —
        # shipped leaves `NOCASE-ON`, the restore-only mutant leaves `NOCASE-OFF`; both leave
        # `NOCASE-OFF` for a caller who never set it. (iv) control: option off, `_sa|_s_ca|_scaf…`
        # in every build and both shells.
        with open(STORE, encoding="utf-8") as fh:
            shipped = fh.read()
        self.assertIn(self.ROW_187_GUARD, shipped,
                      "the shipped encoder does not force its `case` arms case-sensitive (ENC-1)")
        self.assertIn(self.ROW_187_RESTORE, shipped,
                      "the shipped encoder does not restore the caller's `nocasematch` (ENC-3)")
        # zsh HAS NO `shopt` AT ALL — the premise the zsh arm's equality rests on.
        p = subprocess.run(["/bin/zsh", "-c", "shopt -q nocasematch"], capture_output=True, text=True)
        self.assertNotEqual(0, p.returncode, "zsh has a working `shopt` — the zsh arm of this row is "
                                             "asserted equal on the premise that it does not")
        half = with_mutation(self.ROW_187_GUARD, "", path=STORE)
        try:
            # THE MUTATION IS THE WHOLE GUARD — detection, disable AND restore — because that is the
            # pre-fix file; removing only the disable would leave a restore that switches the option
            # ON for a caller who never had it, which is a different defect.
            mutant = with_mutation(self.ROW_187_RESTORE, "", path=half)
            no_restore = with_mutation(self.ROW_187_RESTORE, "", path=STORE)
            try:
                for shell in SHELLS:
                    bash = shell == "/bin/bash"
                    for srcs, label in (((AUTH, STORE, READER, PUB), "shipped"),
                                        ((AUTH, mutant, READER, PUB), "mutant")):
                        is_mutant = label == "mutant"
                        breaks = is_mutant and bash
                        tag = f"{shell} {label}"
                        # (i) THE KEYS, with the caller's `nocasematch` in force.
                        rc, out, err = run_shell(shell, self.ROW_187_ON + self.ROW_187_KEYS,
                                                 sources=srcs)
                        if not breaks:
                            self.assertEqual(self.ROW_187_CANON, out,
                                             f"{tag}: the walk was not byte-exact under nocasematch: "
                                             f"{out!r} {err!r}")
                        else:
                            k_lower, k_upper, k_cafe = out.split("|")
                            self.assertEqual(k_lower, k_upper,
                                             f"{tag}: the CONTROL did not fail — `/a` and `/A` still "
                                             f"encoded differently, so this fixture measures nothing: "
                                             f"{out!r}")
                            self.assertEqual("_s_ca", k_lower, f"{tag}: {out!r}")
                            self.assertEqual("_s_cc_ca_cf_xc3_xa9", k_cafe,
                                             f"{tag}: the CONTROL did not fail — the damage was not "
                                             f"the whole lower-case alphabet: {out!r}")
                        # (iv) THE HONEST CONTROL: with the option OFF every build agrees.
                        rc, out, err = run_shell(shell, self.ROW_187_KEYS, sources=srcs)
                        self.assertEqual(self.ROW_187_CANON, out,
                                         f"{tag}: the keys diverged with `nocasematch` OFF — this row "
                                         f"is then measuring something other than the option: "
                                         f"{out!r} {err!r}")
                        # (ii) END TO END: a publisher that inherited the option, and an ordinary hook.
                        self._wipe()
                        rc, out, err = run_shell(shell, self._mkstore() + self.ROW_187_ON
                                                 + f'_unleashed_publish "{self.store}" "{self.target}"\n'
                                                 + self.PSTATE, sources=srcs)
                        self.assertEqual("created", out,
                                         f"{tag}: the publish did not report `created`, so the read "
                                         f"below would measure a store nobody wrote: {out!r} {err!r}")
                        self.assertEqual([], self._diags(err),
                                         f"{tag}: the wrong key was published WITH a diagnostic: {err!r}")
                        self.assertEqual(1, len(self._names()), f"{tag}: {self._names()}")
                        rc, out, err = run_shell(shell, f'_unleashed_read_store "{self.store}"\n'
                                                 + self.OUTP, sources=srcs)
                        if not breaks:
                            self.assertEqual("1 pointer none", out,
                                             f"{tag}: an ordinary hook did not resolve the store the "
                                             f"publisher had just created: {out!r} {err!r}")
                            self.assertEqual([], self._diags(err), f"{tag}: {err!r}")
                        else:
                            self.assertEqual("0 unresolved stale", out,
                                             f"{tag}: the CONTROL did not fail — the ordinary hook "
                                             f"agreed with the publisher's wrong key: {out!r} {err!r}")
                            self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
                    # (iii) THE RESTORE — its own mutation, because a guard that disables and never
                    # restores is the same defect pointing at the caller instead of at the store.
                    for st, label in ((STORE, "shipped"), (no_restore, "no-restore")):
                        rc, out, err = run_shell(shell, self.ROW_187_ON + self.ROW_187_PROBE,
                                                 sources=(AUTH, st, READER, PUB))
                        base = out                    # what the option does BEFORE the encoder runs
                        rc, out, err = run_shell(shell, self.ROW_187_ON
                                                 + '_unleashed_key /a\n' + self.ROW_187_PROBE,
                                                 sources=(AUTH, st, READER, PUB))
                        if not bash:
                            self.assertEqual("NOCASE-OFF|", base, f"{shell}: zsh has no nocasematch")
                            self.assertEqual(base, out, f"{shell} {label}: the zsh arm must be equal")
                        else:
                            self.assertEqual("NOCASE-ON|", base,
                                             f"{shell}: the probe does not discriminate — `case` did "
                                             f"not match case-insensitively with the option ON: {base!r}")
                            if label == "shipped":
                                self.assertEqual("NOCASE-ON|", out,
                                                 f"{shell}: the encoder left the caller's nocasematch "
                                                 f"switched off: {out!r}")
                            else:
                                self.assertEqual("NOCASE-OFF|", out,
                                                 f"{shell}: the CONTROL did not fail — the caller's "
                                                 f"nocasematch survived without the restore: {out!r}")
                        # …and a caller who never set it does NOT acquire it, in every build.
                        rc, out, err = run_shell(shell, '_unleashed_key /a\n' + self.ROW_187_PROBE,
                                                 sources=(AUTH, st, READER, PUB))
                        self.assertEqual("NOCASE-OFF|", out,
                                         f"{shell} {label}: the encoder switched `nocasematch` ON for "
                                         f"a caller who did not have it: {out!r}")
            finally:
                os.unlink(no_restore)
                os.unlink(mutant)
        finally:
            os.unlink(half)

    # ── row 188 ───────────────────────────────────────────────────────────────────────────────

    #: The readonly-`LC_ALL` guard, at BOTH sites — the encoder's walk and the reader's byte count.
    #: Sliced from the flag's initialisation through the `case` that ends in the assignment, so the
    #: mutation can put the pre-fix `LC_ALL=C` back exactly where it was.
    ROW_188_HEADS = {STORE: "    _uk_lc_ro=0\n", READER: "    _ae_lc_ro=0\n"}
    ROW_188_TAILS = {STORE: "        *) LC_ALL=C ;;\n    esac\n",
                     READER: "        *) LC_ALL=C ;;\n    esac\n"}
    #: The accepted-locale arm and the THIRD state (`2` = leave it entirely alone), which the two
    #: remaining mutations attack: (b) puts `C.UTF-8` back on the accepted list, (c) makes the
    #: readonly-`C` path restore by UNSETTING — `unset` of a readonly is fatal in zsh.
    ROW_188_ACCEPT = {STORE: "                C|POSIX) _uk_lc_set=2 ;;\n",
                      READER: "                C|POSIX) _ae_lc_set=2 ;;\n"}
    ROW_188_ACCEPT_UTF8 = {STORE: "                C|POSIX|C.UTF-8) _uk_lc_set=2 ;;\n",
                           READER: "                C|POSIX|C.UTF-8) _ae_lc_set=2 ;;\n"}
    ROW_188_UNSET = {STORE: "                C|POSIX) _uk_lc_set=0 ;;\n",
                     READER: "                C|POSIX) _ae_lc_set=0 ;;\n"}
    #: The bash probe, and the FORKING probe my own first version of this guard used. ENC-2 requires
    #: the key derivation to fork ZERO times and row 045 pins it; this mutation is that first version.
    ROW_188_PROBE = ('    elif [ "$_uk_lc_set" = 1 ]; then\n'
                     '        unset -v LC_ALL 2>/dev/null || _uk_lc_ro=1\n'
                     '    fi\n')
    ROW_188_FORKING = ('    elif [ "$_uk_lc_set" = 1 ]; then\n'
                       '        case "$( declare -p LC_ALL 2>/dev/null )" in\n'
                       '            *"declare -r"*) _uk_lc_ro=1 ;;\n'
                       '        esac\n'
                       '    fi\n')
    #: `/café` as raw bytes, and the answer the byte-wise walk owes for it.
    ROW_188_CAFE = '_u188=$(printf %b "/caf\\xc3\\xa9")\n'
    ROW_188_CAFE_KEY = "_scaf_xc3_xa9"

    def _row_188_key_body(self, value, locale_line):
        """Derive one key under `locale_line`, then report LC_ALL and that the shell is still here.

        The marker is on its OWN LINE because bash does not kill the SHELL on an assignment to a
        readonly — it destroys the enclosing command LIST, `||` arm and all (measured), so a fallback
        spelled on the same line as the call would not run either and the two failure modes would be
        indistinguishable from a caller's point of view.
        """
        return (locale_line
                + f'if _unleashed_key "{value}"; then printf "key=%s|" "$_UNLEASHED_KEY"; '
                  'else printf "key=REFUSED|"; fi\n'
                + 'printf "LC=%s|ALIVE" "${LC_ALL-UNSET}"\n')

    def test_row_188_a_readonly_lc_all_is_detected_never_assigned_to(self):
        """Row 188 (codex, PR #67 pass 23 — reproduced): ENC-3 pins `LC_ALL` to `C` for the byte-wise walk and for the reader's byte count, and a caller may have made `LC_ALL` READONLY — measured, `readonly LC_ALL=C.UTF-8` followed by sourcing was FATAL in both shells, and no shell-level guard survives it (`if !` and `{ …; } || true` both die; only a subshell does, and a subshell cannot set the locale for the walk that follows). The specification DETECTS the attribute instead, fork-free and per shell, and this row pins the three things each of which was a defect in an intermediate version of the fix. ONE: ENC-2 is preserved — the probe forks ZERO times, so the key is still derived under `ulimit -u 1` (the first version read the attribute with `$( declare -p LC_ALL )`, and that mutation produces NO key at all in bash). TWO: `C.UTF-8` REFUSES rather than proceeding — it is a UTF-8 locale, and with it back on the accepted list one directory encodes THREE ways, `_scaf_xc3` in bash and `_scaf_xe9` in zsh against the correct `_scaf_xc3_xa9`; every case "survives", so a survival-only oracle passes that build and the oracle here is the KEYS. THREE: a readonly `C` is left ENTIRELY alone on exit — not unset, not reassigned — because `unset` of a readonly is fatal in zsh, and the mutation that restores by unsetting kills the shell one line after the bug it was written to fix would have. Both shells, and both sites: the reader's byte-count block carries the same guard, and the same two mutations there leave every protocol variable UNSET in bash and kill the zsh shell outright on a store that the specification resolves `1 pointer none`. The honest control throughout is a WRITABLE `LC_ALL`, where every build agrees."""
        # Measured, both shells. Encoder, readonly LC_ALL=C: shipped `key=_stmp_sabc|LC=C|ALIVE` with
        # EMPTY stderr; (a) bash `LC=C|ALIVE` with no `key=` at all — the command list destroyed — and
        # zsh DEAD (rc=1, no output); (c) bash `key=_stmp_sabc|LC=C|ALIVE` but a stray
        # `unset: LC_ALL: cannot unset: readonly variable` on stderr, zsh DEAD.
        # Encoder, readonly LC_ALL=C.UTF-8: shipped `key=REFUSED|…|ALIVE` in both shells;
        # (b) bash `key=_scaf_xc3`, zsh `key=_scaf_xe9` — divergent, and neither the correct key.
        # ENC-2 under `ulimit -u 1` with LC_ALL SET: shipped `_stmp_sabc` in both shells;
        # (d) bash produces nothing, zsh unchanged (the mutation is in the bash arm only).
        # Reader, readonly LC_ALL=C over a store built by a SEPARATE process: shipped
        # `1 pointer none` with empty stderr; (a) bash `U U U` + shell error, zsh DEAD; (c) bash
        # resolves but with a stray shell error, zsh DEAD. Reader, readonly C.UTF-8: shipped
        # `0 unresolved stale` + one diagnostic, both shells.
        for path, name in ((STORE, "encoder"), (READER, "reader")):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn(self.ROW_188_ACCEPT[path], text,
                          f"the {name}'s readonly-LC_ALL guard no longer accepts exactly C and POSIX "
                          f"and leaves the variable entirely alone (ENC-3)")
            # A LITERAL `C.UTF-8)` APPEARS IN THE READER'S PROSE ("…reproduced in both shells under
            # C.UTF-8)."), so the check is on the ARM, not on the string — a bare substring test here
            # would fail on a comment and pass on nothing.
            self.assertNotIn(self.ROW_188_ACCEPT_UTF8[path], text,
                             f"the {name} accepts a readonly `C.UTF-8`, under which the walk is "
                             f"CHARACTER-wise and one directory encodes differently per shell (ENC-1)")
        # THE PRIMITIVES THIS ROW RESTS ON, measured rather than assumed: an assignment to a readonly
        # `LC_ALL` is fatal in both shells even for the SAME value, and `unset` of one is fatal in zsh
        # while bash 3.2 fails it non-fatally — which is why the two shells probe differently.
        for shell in SHELLS:
            p = subprocess.run([shell, "-c", "readonly LC_ALL=C; LC_ALL=C; printf ALIVE"],
                               capture_output=True, text=True)
            self.assertEqual("", p.stdout,
                             f"{shell}: assigning a readonly its own value was survivable here — the "
                             f"defect this row measures cannot occur on this machine: {p.stdout!r}")
        p = subprocess.run(["/bin/bash", "-c",
                            "readonly LC_ALL=C; unset -v LC_ALL 2>/dev/null || printf RO; printf ALIVE"],
                           capture_output=True, text=True)
        self.assertEqual("ROALIVE", p.stdout, f"bash `unset -v` on a readonly: {p.stdout!r}")
        p = subprocess.run(["/bin/zsh", "-c", "readonly LC_ALL=C; unset LC_ALL 2>/dev/null; printf ALIVE"],
                           capture_output=True, text=True)
        self.assertEqual("", p.stdout,
                         f"zsh survived `unset` of a readonly — the third state (`2`, leave it alone) "
                         f"would then be unmotivated: {p.stdout!r}")
        muts = {}
        try:
            for path in (STORE, READER):
                block = self._slice(path, self.ROW_188_HEADS[path], self.ROW_188_TAILS[path])
                muts[(path, "a")] = with_mutation(block, "    LC_ALL=C\n", path=path)
                muts[(path, "b")] = with_mutation(self.ROW_188_ACCEPT[path],
                                                  self.ROW_188_ACCEPT_UTF8[path], path=path)
                muts[(path, "c")] = with_mutation(self.ROW_188_ACCEPT[path],
                                                  self.ROW_188_UNSET[path], path=path)
            muts[(STORE, "d")] = with_mutation(self.ROW_188_PROBE, self.ROW_188_FORKING, path=STORE)
            for shell in SHELLS:
                bash = shell == "/bin/bash"
                # ── the ENCODER site ─────────────────────────────────────────────────────────────
                for build in ("shipped", "a", "b", "c", "d"):
                    st = STORE if build == "shipped" else muts[(STORE, build)]
                    srcs = (AUTH, st, READER, PUB)
                    tag = f"{shell} encoder/{build}"
                    # (1) a readonly `C` — the accepted locale, the walk proceeds, and the variable is
                    #     left ENTIRELY alone: still `C`, never unset, never reassigned.
                    rc, out, err = run_shell(shell, self._row_188_key_body("/tmp/abc",
                                                                           "readonly LC_ALL=C\n"),
                                             sources=srcs)
                    if build == "a":
                        if bash:
                            self.assertEqual("LC=C|ALIVE", out,
                                             f"{tag}: the CONTROL did not fail — the unguarded "
                                             f"assignment did not destroy the caller's command list: "
                                             f"{out!r} {err!r}")
                        else:
                            self.assertEqual("", out,
                                             f"{tag}: the CONTROL did not fail — zsh survived the "
                                             f"unguarded assignment: {out!r} {err!r}")
                    elif build == "c":
                        if bash:
                            self.assertEqual("key=_stmp_sabc|LC=C|ALIVE", out, f"{tag}: {out!r} {err!r}")
                            self.assertNotEqual("", err,
                                                f"{tag}: the CONTROL did not fail — restoring by "
                                                f"unsetting a readonly was silent in bash: {err!r}")
                        else:
                            self.assertEqual("", out,
                                             f"{tag}: the CONTROL did not fail — zsh survived `unset` "
                                             f"of a readonly on the restore: {out!r} {err!r}")
                    else:
                        self.assertEqual("key=_stmp_sabc|LC=C|ALIVE", out,
                                         f"{tag}: a readonly `C` did not derive the key and leave "
                                         f"LC_ALL alone: {out!r} {err!r}")
                        self.assertEqual("", err, f"{tag}: the accepted path must be silent: {err!r}")
                    # (2) a readonly `C.UTF-8` — REFUSED, because the byte semantics ENC-1 needs
                    #     cannot be established. The oracle is the KEY, never survival.
                    rc, out, err = run_shell(shell, self.ROW_188_CAFE
                                             + self._row_188_key_body("$_u188",
                                                                      "readonly LC_ALL=C.UTF-8\n"),
                                             sources=srcs)
                    if build == "a":
                        self.assertEqual("LC=C.UTF-8|ALIVE" if bash else "", out,
                                         f"{tag}: the CONTROL did not fail: {out!r} {err!r}")
                    elif build == "b":
                        key = out.split("|")[0]
                        self.assertEqual("key=_scaf_xc3" if bash else "key=_scaf_xe9", key,
                                         f"{tag}: the CONTROL did not fail — a readonly `C.UTF-8` did "
                                         f"not make the walk character-wise: {out!r} {err!r}")
                        self.assertNotEqual(f"key={self.ROW_188_CAFE_KEY}", key,
                                            f"{tag}: the CONTROL did not fail — the accepted UTF-8 "
                                            f"locale still produced the byte-wise key: {out!r}")
                    else:
                        self.assertEqual("key=REFUSED|LC=C.UTF-8|ALIVE", out,
                                         f"{tag}: a readonly UTF-8 locale was not refused: "
                                         f"{out!r} {err!r}")
                    # (3) ENC-2 — the probe forks ZERO times, so the key survives fork exhaustion.
                    #     Scoped to the shipped build and to mutation (d), the FORKING probe: (a) and
                    #     (c) have their own cells above and would fail this one for their own reasons,
                    #     which would make a green cell here unreadable. `LC_ALL` must be SET for the
                    #     bash arm's probe to run at all — with it ABSENT the probe is not reached, so
                    #     that variant is asserted EQUAL rather than claimed to discriminate.
                    if build in ("shipped", "d"):
                        for loc, label in (("readonly LC_ALL=C\n", "readonly-C"),
                                           ("LC_ALL=en_US.UTF-8\n", "writable-UTF-8"),
                                           ("unset LC_ALL 2>/dev/null\n", "absent")):
                            rc, out, err = run_shell(
                                shell, 'ulimit -u 1 2>/dev/null || { printf CANNOT-LIMIT; exit 0; }\n'
                                       + loc + '_unleashed_key /tmp/abc 2>/dev/null\n'
                                       'printf "%s" "${_UNLEASHED_KEY-UNSET}"', sources=srcs)
                            if out == "CANNOT-LIMIT":
                                continue
                            if build == "d" and bash and label != "absent":
                                self.assertNotEqual("_stmp_sabc", out,
                                                    f"{tag} [{label}]: the CONTROL did not fail — a "
                                                    f"FORKING probe still derived the key with no fork "
                                                    f"available, so ENC-2 is not being measured: {out!r}")
                            else:
                                self.assertEqual("_stmp_sabc", out,
                                                 f"{tag} [{label}]: the key was not derived under "
                                                 f"`ulimit -u 1`: {out!r} {err!r}")
                    # (4) THE HONEST CONTROL — a WRITABLE `LC_ALL`. Every build agrees, so every cell
                    #     above is scoped to the READONLY case and to nothing else.
                    rc, out, err = run_shell(shell, self.ROW_188_CAFE
                                             + self._row_188_key_body("$_u188",
                                                                      "LC_ALL=en_US.UTF-8\n"),
                                             sources=srcs)
                    self.assertEqual(f"key={self.ROW_188_CAFE_KEY}|LC=en_US.UTF-8|ALIVE", out,
                                     f"{tag}: a WRITABLE locale must behave identically in every "
                                     f"build — this row measures the readonly case: {out!r} {err!r}")
                # ── the READER site ──────────────────────────────────────────────────────────────
                # The store is built by a SEPARATE process on purpose: building it in the same shell
                # leaves `_UNLEASHED_KEY` already correct, and ENT-3's re-derivation then passes on a
                # STALE value even when the encoder refused — a fixture that hides exactly the
                # difference this cell exists to see (caught while writing this row).
                for build in ("shipped", "a", "b", "c"):
                    rd = READER if build == "shipped" else muts[(READER, build)]
                    srcs = (AUTH, STORE, rd, PUB)
                    tag = f"{shell} reader/{build}"
                    for loc, healthy in (("readonly LC_ALL=C\n", True),
                                         ("readonly LC_ALL=C.UTF-8\n", False)):
                        self._wipe()
                        rc0, _, err0 = run_shell("/bin/bash", self._mkstore() + self._entry())
                        self.assertEqual(0, rc0, f"{tag}: the fixture store was not built: {err0!r}")
                        rc, out, err = run_shell(shell, loc
                                                 + f'_unleashed_read_store "{self.store}"\n'
                                                 + self.ROW_186_OUT, sources=srcs)
                        if build == "a":
                            self.assertEqual("U U U" if bash else "", out,
                                             f"{tag} [{loc.strip()}]: the CONTROL did not fail — the "
                                             f"unguarded assignment left the reader able to answer: "
                                             f"{out!r} {err!r}")
                            self.assertEqual([], self._diags(err), f"{tag}: {err!r}")
                        elif build == "c" and healthy:
                            if bash:
                                self.assertEqual("1 pointer none", out, f"{tag}: {out!r} {err!r}")
                                self.assertNotEqual("", err,
                                                    f"{tag}: the CONTROL did not fail — restoring by "
                                                    f"unsetting was silent in bash: {err!r}")
                            else:
                                self.assertEqual("", out,
                                                 f"{tag}: the CONTROL did not fail — zsh survived "
                                                 f"`unset` of a readonly: {out!r} {err!r}")
                        elif healthy:
                            self.assertEqual("1 pointer none", out,
                                             f"{tag}: a readonly `C` did not resolve a healthy store: "
                                             f"{out!r} {err!r}")
                            self.assertEqual("", err, f"{tag}: {err!r}")
                        else:
                            # A readonly UTF-8 locale REFUSES: the byte count clause (2) needs byte
                            # semantics, so the entry fails and rule 1 reports `stale` with its one
                            # diagnostic. Mutation (b) is asserted EQUAL here and NOT discriminating —
                            # the encoder's own refusal at ENT-3 already fail-closes the read, which
                            # is why (b)'s discriminating site is the KEY and not the resolution.
                            self.assertEqual("0 unresolved stale", out,
                                             f"{tag}: a readonly UTF-8 locale was not refused by the "
                                             f"reader: {out!r} {err!r}")
                            self.assertEqual(1, len(self._diags(err)), f"{tag}: {err!r}")
        finally:
            for m in muts.values():
                os.unlink(m)

    @unittest.skipUnless(DARWIN, "the store's chain and ACL arms are Darwin-only in this build")
    def test_row_188b_the_locale_probe_restores_the_export_attribute(self):
        """Row 188b (found while pinning row 188, by measurement, not by review): bash's only fork-free
        readonly probe is `unset -v`, and a SUCCESSFUL unset destroys the EXPORT attribute — so an
        exported `LC_ALL` came back as a plain shell variable and every child these libraries fork
        (`/usr/bin/stat`, `/bin/ls -le`, `/usr/bin/getconf`) ran under the caller's `LANG` instead of
        their `LC_ALL`. ENC-3 restores the entry state EXACTLY, and the export attribute is part of it.

        The oracle is the ENVIRONMENT, not the value: the value survived the defect untouched, so a
        cell that compared `$LC_ALL` would have passed against the broken build. STATED DEVIATION,
        asserted here so it cannot drift silently: a caller whose `LC_ALL` was set but NOT exported
        gets it exported on return, because bash 3.2 has no fork-free way to distinguish the two.
        """
        mutant = with_mutation('LC_ALL="$_uk_lc_val"; export LC_ALL ;;',
                               'LC_ALL="$_uk_lc_val" ;;', path=STORE)
        try:
            for shell in SHELLS:
                for store_file, is_mutant in ((STORE, False), (mutant, True)):
                    body = ('export LC_ALL=en_US.UTF-8\n'
                            '_unleashed_key /tmp/abc >/dev/null 2>&1\n'
                            'printf "%s|%s" "$LC_ALL" "$(env | grep -c \'^LC_ALL=\')"\n')
                    rc, out, err = run_shell(shell, body, sources=(AUTH, store_file))
                    tag = f"{shell} {'mutant' if is_mutant else 'shipped'}"
                    if shell.endswith("zsh") or not is_mutant:
                        self.assertEqual("en_US.UTF-8|1", out,
                                         f"{tag}: the caller's exported LC_ALL must survive as an EXPORT: {err}")
                    else:
                        self.assertEqual("en_US.UTF-8|0", out,
                                         f"{tag}: the CONTROL did not fail — without the `export` on restore "
                                         f"bash must leave LC_ALL out of the environment: {err}")
        finally:
            os.unlink(mutant)


if __name__ == "__main__":
    unittest.main()
