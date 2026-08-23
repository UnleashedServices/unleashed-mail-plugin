#!/usr/bin/env python3
"""The state writers must suppress stderr BEFORE opening their temp file.

`scripts/precompact-snapshot.sh:70-72` states the rule normatively:

    `2>/dev/null` BEFORE `> "$TMP"` so an open failure (state dir unwritable) is suppressed too
    (bash applies redirects left-to-right; a trailing `2>/dev/null` would let the open error —
    which echoes the full PII-bearing tmp path — reach stderr).

Three of the five writers shipped with the order INVERTED — `marker.sh`, `context.sh` and
`stop-quality-marker-gate.sh` — and nothing anywhere observed it. Reproduced before fixing, with a
DIRECTORY planted at the exact temp name so the open fails EISDIR:

    SHIPPED : marker.sh: line 274: /Users/<name>/…/quality-marker-lint-<hash>.json.tmp.<pid>: Is a directory
    FIXED   : (stderr empty)

The leaked path carries the operator's home directory, and hooks write to the user's terminal.

Two cells, deliberately: a BEHAVIOURAL one that drives a real writer into a real open failure, and a
LEXICAL sweep over the whole family. The behavioural cell is the evidence; the sweep is what stops a
sixth writer being added tomorrow with the order flipped, which is how three of these five got here.

The EISDIR fixture is uid-independent — no `chmod`, so no root skip. A permissions-based fixture
would silently stop testing anything for uid 0.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: DERIVED FROM THE TREE, not enumerated (COREDEV-2691). The first version of this sweep listed five
#: writers by hand and scoped the pattern to temp-file names; both narrowings let a real leak through
#: — see INVERTED below. A hand-kept list of the files a rule applies to is a blacklist wearing a
#: different hat: it silently stops covering whatever is added next.
def _shipped_shell() -> "list[Path]":
    return sorted(
        rel
        for pattern in ("scripts/*.sh", "scripts/lib/*.sh", "scripts/review/*.sh")
        for rel in (q.relative_to(REPO) for q in REPO.glob(pattern))
    )


#: A redirect into ANY path-bearing target, followed LATER on the same line by `2>/dev/null` — the
#: inverted order. The open error escapes to the real stderr before the suppression takes effect.
#:
#: WIDENED (COREDEV-2691). The original pattern required the target to contain `tmp`/`TMP`/`STMP`,
#: which made the sweep blind to `>> "$LOGDIR/stop-gate.log" 2>/dev/null` in the very file it already
#: policed — `stop-quality-marker-gate.sh`, whose sibling site at :130 this suite was written for.
#: Measured on the shipped hook with a directory planted at the log path:
#:
#:     stop-quality-marker-gate.sh: line 143: /…/<plugin-data>/logs/stop-gate.log: Is a directory
#:
#: The leak is the PATH, not the temp-ness of the path, so the pattern keys on the redirect shape:
#: any `>`/`>>` into a quoted target that interpolates a variable, with the suppression trailing.
#: WIDENED AGAIN (COREDEV-2691, gemini on PR #78): the first widening still required the target to
#: be DOUBLE-QUOTED, so `> $VAR 2>/dev/null` was invisible. The leak is the redirect ORDER, not the
#: quoting — measured with a directory planted at the target, an unquoted inverted redirect prints
#: the full expanded path to stderr exactly as the quoted one does.
#:
#: The `>` must sit OUTSIDE any double-quoted string — that, not a "preceded by a delimiter" rule,
#: is what separates a real redirect from a literal `->` inside a log message. Measured: the
#: delimiter form drops `printf x>"$tmp" 2>/dev/null`, and this tree already uses that spaceless
#: idiom (`9>"$_wt_p"`, `2>"$4/err"`). Matched per LINE — the sweep iterates splitlines() — so `^`
#: anchors correctly without re.MULTILINE.
#:   `\d?>>?`  optional fd digit, so `1>` and `9>` count
#:   quoted branch keeps `[^"]*` so a target with SPACES survives ("$HOME/Application Support/…")
INVERTED = re.compile(
    r'^(?:[^"]|"[^"]*")*?\d?>>?[ \t]*(?:"[^"]*\$[^"]*"|[^"\s]*\$[^"\s]*)[ \t]+2>/dev/null')


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "needs bash and git")
class TheWritersSuppressStderrBeforeOpening(unittest.TestCase):
    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = Path(tempfile.mkdtemp(prefix="redirect-order.", dir=base))
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        (self.scratch / "home").mkdir()
        (self.scratch / "data").mkdir()
        # `XDG_CONFIG_HOME` goes too: redirecting HOME alone is NOT hermetic, because git also reads
        # `$XDG_CONFIG_HOME/git/config` and it wins (measured — gemini raised this on the sibling file
        # in PR #73; this file had the same hole).
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("GIT_") and k != "XDG_CONFIG_HOME"}
        self.env.update(HOME=str(self.scratch / "home"),
                        CLAUDE_PLUGIN_DATA=str(self.scratch / "data"),
                        LC_ALL="C", LANG="C",
                        # PUBLICATION OFF. These cells assert that stderr is EMPTY, and sourcing a
                        # family lib with the variable set publishes into the store — which emits
                        # `unleashed-mail: plugin-state publication failed: …` whenever the chain does
                        # not authenticate. On Linux it NEVER authenticates: `plugin-state-auth.sh`
                        # refuses on every non-Darwin platform by design, so the diagnostic is
                        # unconditional there and the empty-stderr assertion cannot hold. Reproduced
                        # locally by forcing that gate to refuse — the failure is byte-identical to
                        # the one CI produced (codex, PR #74). `test_plugin_state_base.py`'s own
                        # `run()` helper sets this for the same reason.
                        _UNLEASHED_PUBLISH_OK="0")

    def _marker_write_onto_a_directory(self, library: Path):
        """Drive `marker_write` with a DIRECTORY planted at the exact temp name it will open.

        `$$` is the sourcing shell's pid, so the collision has to be created by that same shell —
        hence the whole fixture is one script rather than a setup step plus a call.
        """
        script = self.scratch / "drive.sh"
        script.write_text(
            '#!/usr/bin/env bash\n'
            '. "$1"\n'
            'p="$(marker_path lint)"\n'
            'mkdir -p "$(dirname "$p")"\n'
            'mkdir -p "${p}.tmp.$$"\n'
            'marker_write lint fail\n',
            encoding="utf-8")
        return subprocess.run(["bash", str(script), str(library)],
                              capture_output=True, text=True, env=self.env, check=False)

    def test_an_unopenable_temp_file_does_not_leak_its_path_to_stderr(self):
        result = self._marker_write_onto_a_directory(REPO / "scripts" / "lib" / "marker.sh")
        self.assertEqual("", result.stderr,
                         f"the open failure leaked the temp path to stderr:\n{result.stderr}")

    def test_the_INVERTED_order_leaks_the_path(self):
        """The mutant control. Without it this cell could not distinguish a correct redirect order
        from a writer that never opens anything — and it is what proves the fixture actually
        provokes an open failure rather than quietly succeeding."""
        library = REPO / "scripts" / "lib" / "marker.sh"
        text = library.read_text(encoding="utf-8")
        good = '"${_UNLEASHED_BASE_SOURCE:-unresolved}" 2>/dev/null > "$tmp"'
        bad = '"${_UNLEASHED_BASE_SOURCE:-unresolved}" > "$tmp" 2>/dev/null'
        self.assertEqual(1, text.count(good), "mutation anchor is not unique")
        mutant = self.scratch / "marker-inverted.sh"
        mutated = text.replace(good, bad, 1)
        self.assertEqual(text.count("\n"), mutated.count("\n"), "the mutation changed the line count")
        mutant.write_text(mutated, encoding="utf-8")
        result = self._marker_write_onto_a_directory(mutant)
        self.assertIn("Is a directory", result.stderr,
                      f"CONTROL FAILED — the inverted order did not leak, so the fixture is not "
                      f"provoking an open failure and the cell above proves nothing:\n{result.stderr!r}")
        self.assertIn(".tmp.", result.stderr,
                      f"CONTROL FAILED — the leak did not name the temp path:\n{result.stderr!r}")

    def _stop_gate_warn_onto_a_directory(self, mutate=None):
        """Drive the Stop gate's WARN branch with a DIRECTORY planted at its log FILE path.

        The second behavioural site (COREDEV-2691), deliberately an APPEND to a NON-temp target —
        the shape this suite's first sweep could not see, in the very file it already policed.

        The whole `scripts/` tree is COPIED into the scratch and the mutation applied to the copy.
        A hook resolves its libraries from `BASH_SOURCE[0]`, so a mutant written anywhere else
        cannot source `lib/hook-io.sh` and dies before reaching the redirect — which reads as "no
        leak" and would make the control pass while proving nothing. Copying is also what keeps the
        real worktree untouched.

        A seeded FAILING lint marker is what carries execution into the warn branch; without it the
        hook exits early and the cell is vacuous. The control below is what proves it got there.
        """
        root = self.scratch / "scripts"
        if not root.exists():
            shutil.copytree(REPO / "scripts", root, symlinks=True)
        hook = root / "stop-quality-marker-gate.sh"
        if mutate is not None:
            text = hook.read_text(encoding="utf-8")
            good, bad = mutate
            self.assertEqual(1, text.count(good), "mutation anchor is not unique")
            mutated = text.replace(good, bad, 1)
            self.assertEqual(text.count("\n"), mutated.count("\n"),
                             "the mutation changed the line count")
            hook.write_text(mutated, encoding="utf-8")
        driver = self.scratch / "drive-stop-gate.sh"
        driver.write_text(
            "#!/usr/bin/env bash\n"
            '. "$1/lib/marker.sh"\n'
            'L="$(marker_base)/logs"\n'
            'mkdir -p "$L"\n'
            'mkdir -p "$L/stop-gate.log"\n'          # a DIRECTORY where the log FILE goes
            "marker_write lint fail >/dev/null 2>&1\n"
            'printf %s "$2" | bash "$1/stop-quality-marker-gate.sh"\n',
            encoding="utf-8")
        payload = '{"hook_event_name":"Stop","session_id":"s1","transcript_path":"/x/t.jsonl"}'
        env = dict(self.env, CLAUDE_PLUGIN_ROOT=str(root.parent),
                   UNLEASHED_STOP_GATE_MODE="warn")
        # CWD IS LOAD-BEARING HERE (codex, PR #78). `stop-quality-marker-gate.sh:49` exits when
        # `git rev-parse --short HEAD` finds no commit — 94 lines BEFORE the redirect under test.
        # A child inherits the caller's CWD, so running this module from outside a checkout made
        # the positive cell below pass without exercising anything, while its control failed with
        # empty stderr. Reproduced exactly as reported; and running a single cell with `-k` or from
        # an IDE gave a genuine FALSE GREEN, because the control was not there to redden.
        #
        # A SCRATCH ANCHOR, not `cwd=REPO`: measured, `cwd=REPO` only narrows the trigger from "any
        # non-repo CWD" to "REPO has no HEAD commit", and a tree exported without `.git` still
        # passed hollow ON A LEAKING TREE. The anchor is a repo this fixture owns, so it holds
        # regardless of how the checkout was obtained. It does NOT weaken the copied-tree isolation:
        # the hook still resolves its libraries from its own location, which is the copy.
        # `_marker_write_onto_a_directory` deliberately does NOT get this — measured CWD-independent.
        anchor = self.scratch / "anchor"
        if not anchor.exists():
            anchor.mkdir()
            # `-c user.email/user.name` because setUp redirects HOME and drops XDG_CONFIG_HOME, so
            # there is no global git identity to fall back on.
            subprocess.run(["git", "init", "-q", "."], cwd=str(anchor),
                           capture_output=True, text=True, env=self.env, check=True)
            subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=a",
                            "commit", "-q", "--allow-empty", "-m", "seed"],
                           cwd=str(anchor), capture_output=True, text=True,
                           env=self.env, check=True)
        return subprocess.run(["bash", str(driver), str(root), payload], cwd=str(anchor),
                              capture_output=True, text=True, env=env, check=False)

    _WARN_LOG_GOOD = '    2>/dev/null >> "$LOGDIR/stop-gate.log" || true'
    _WARN_LOG_BAD = '    >> "$LOGDIR/stop-gate.log" 2>/dev/null || true'

    def test_the_stop_gate_warn_log_does_not_leak_its_path_to_stderr(self):
        result = self._stop_gate_warn_onto_a_directory()
        self.assertEqual("", result.stderr,
                         f"the warn-log open failure leaked its path to stderr:\n{result.stderr}")

    def test_the_INVERTED_warn_log_order_leaks_the_path(self):
        """The control, and the reproduction of the shipped defect. Measured before the fix, from
        inside a hook: `stop-quality-marker-gate.sh: line 143:
        /…/<plugin-data>/logs/stop-gate.log: Is a directory`."""
        result = self._stop_gate_warn_onto_a_directory(
            mutate=(self._WARN_LOG_GOOD, self._WARN_LOG_BAD))
        self.assertIn("Is a directory", result.stderr,
                      f"CONTROL FAILED — the inverted order did not leak, so the fixture never "
                      f"reached the warn branch and the cell above proves nothing:\n{result.stderr!r}")
        self.assertIn("stop-gate.log", result.stderr,
                      f"CONTROL FAILED — the leak did not name the log path:\n{result.stderr!r}")

    def test_NO_writer_in_the_family_carries_the_inverted_order(self):
        """The family sweep. Three of these five shipped inverted while the rule sat in a comment in
        the fourth; a rule that lives only in prose is not enforced. This is what a sixth writer
        added tomorrow has to pass."""
        offenders = []
        for rel in _shipped_shell():
            path = REPO / rel
            if not path.is_file():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if INVERTED.search(line):
                    offenders.append(f"{rel}:{number}: {line.strip()}")
        self.assertEqual([], offenders,
                         "these writers redirect into a temp file BEFORE suppressing stderr, so an "
                         "open failure prints the full path:\n  " + "\n  ".join(offenders))

    def test_the_sweep_would_catch_an_inverted_writer(self):
        """The sweep's own control: it must actually match the shape it claims to reject."""
        self.assertRegex('printf x > "$tmp" 2>/dev/null', INVERTED)
        self.assertRegex('printf x > "$_rb_path.tmp.$$" 2>/dev/null', INVERTED)
        self.assertRegex("if [ -n \"$_STMP\" ] && printf '%s' \"$C\" > \"$_STMP\" 2>/dev/null; then", INVERTED)
        # THE ONE THE NARROW PATTERN MISSED (COREDEV-2691) — an APPEND, to a target with no temp
        # marker in its name, in a file this suite already policed. Both narrowings had to go.
        self.assertRegex('    >> "$LOGDIR/stop-gate.log" 2>/dev/null || true', INVERTED)
        self.assertRegex('cmd > "$COVERAGE_OUT" 2>/dev/null', INVERTED)
        # UNQUOTED targets (gemini, PR #78) — the leak is the ORDER, not the quoting.
        self.assertRegex('printf x > $tmp 2>/dev/null', INVERTED)
        self.assertRegex('printf x >> $LOGDIR/stop-gate.log 2>/dev/null', INVERTED)
        self.assertRegex('printf x > ${TMP}.$$ 2>/dev/null', INVERTED)
        # A redirect GLUED to the preceding word is still a redirect and still leaks. The obvious
        # "require a delimiter before >" widening drops these, and this tree already uses the
        # spaceless idiom (`9>"$_wt_p"`, `2>"$4/err"`).
        self.assertRegex('printf x>"$tmp" 2>/dev/null', INVERTED)
        self.assertRegex('printf x> $LOG 2>/dev/null', INVERTED)
        # A QUOTED target CONTAINING SPACES must survive the widening — the obvious `"?`-based
        # form silently drops it, and this path is ordinary on macOS.
        self.assertRegex('printf x > "$HOME/Application Support/s.json" 2>/dev/null', INVERTED)
        # A literal `>` INSIDE a quoted string is not a redirect. This is what the quote-state
        # prefix buys over a delimiter class.
        self.assertNotRegex('log "moved $a -> $b" 2>/dev/null', INVERTED)
        self.assertNotRegex('printf "a > $b\\n" 2>/dev/null', INVERTED)
        # ...and the correct order still must not match, in either redirect form.
        self.assertNotRegex('printf x 2>/dev/null > "$tmp"', INVERTED)
        self.assertNotRegex('tail -n 5 "$p" 2>/dev/null > "$tmp"', INVERTED)
        self.assertNotRegex('    2>/dev/null >> "$LOGDIR/stop-gate.log" || true', INVERTED)
        # A bare `2>/dev/null` with no output redirect at all must not match — the `>` inside it is
        # not an output redirect, and a pattern that thought so would flag most of the tree.
        self.assertNotRegex('mkdir -p "$LOGDIR" 2>/dev/null || exit 0', INVERTED)

    def test_the_sweep_covers_the_whole_shipped_shell_tree(self):
        """The derivation's own control. If `_shipped_shell()` ever returns a short or empty list the
        sweep above passes vacuously — which is precisely how the hand-written five-file list hid a
        real leak. Assert it reaches a realistic breadth AND names the files that carry the rule."""
        found = {rel.as_posix() for rel in _shipped_shell()}
        self.assertGreater(len(found), 15, f"suspiciously few shell files swept: {sorted(found)}")
        for required in ("scripts/lib/marker.sh", "scripts/lib/context.sh", "scripts/lib/log.sh",
                         "scripts/precompact-snapshot.sh", "scripts/stop-quality-marker-gate.sh"):
            self.assertIn(required, found, "the original five must still be swept")


if __name__ == "__main__":
    unittest.main()
