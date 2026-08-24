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
#: — see `inverted_redirect` below. A hand-kept list of the files a rule applies to is a
#: blacklist wearing a different hat: it silently stops covering whatever is added next.
def _shipped_shell() -> "list[Path]":
    #: RECURSIVE, and extension-agnostic where the tree needs it. Three directory patterns is the
    #: same allowlist mistake one level up — `scripts/<new-dir>/*.sh` would be invisible. And
    #: `.githooks/pre-commit` is SHIPPED executable bash with no `.sh` suffix, outside `scripts/`
    #: entirely (kimi, local round); the breadth control below could never notice its absence.
    #: This derivation was recursive once before and a bulk `git checkout` reverted it silently
    #: while the fix was reported as landed — hence the explicit assertion in the control.
    found = set(REPO.glob("scripts/**/*.sh"))
    extra = REPO / ".githooks" / "pre-commit"
    if extra.is_file():
        found.add(extra)
    return sorted(q.relative_to(REPO) for q in found)


#: A redirect into ANY path-bearing target, followed LATER on the same line by `2>/dev/null` — the
#: inverted order. The open error escapes to the real stderr before the suppression takes effect.
#:
#: A HAND-ROLLED SCANNER, not a regex (COREDEV-2691). This predicate was a regex through four
#: quote/target-shape defects, each fixed by widening it: it required a temp-ish NAME (blind to
#: `>> "$LOGDIR/stop-gate.log"` in a file it already policed); then DOUBLE QUOTES (blind to
#: `> $VAR`); then it desynced on an ODD number of `"` inside a single-quoted run; then it required
#: the target to be ONE wholly-quoted or wholly-bare word, so codex's `> "$LOGDIR"/stop-gate.log`
#: — a target CONCATENATED from a quoted and an unquoted segment, the idiom this tree already uses
#: at eleven sites — slipped past. Measured, with a directory planted at that path:
#:
#:     w.sh: line 3: /…/logs/stop-gate.log: Is a directory
#:
#: while the correct order prints nothing; a sixth writer in that style left the sweep GREEN.
#:
#: The fourth REGEX widening was built and rejected, not skipped. Accepting a multi-segment word
#: needs a nested quantifier (`(?:dq|sq|bare+)*`), which backtracks catastrophically: on
#: `swift-lint-check.sh:7` — an ordinary 96-char COMMENT containing `->` — it doubled per character,
#: 0.2 ms at 40 chars to 12.5 s at 56, and four real tree lines blew past a 2 s cap. Atomic groups
#: (`(?>…)`, `*+`) fix the blowup but need Python 3.11+: `re.compile` raises
#: `re.error: unknown extension ?>` on macOS stock 3.9.6, the interpreter this repo keeps the
#: `py39-smoke` CI job for. The scanner is linear, uses no `re` extensions, and runs on 3.9.6.
#:
#: The quoting rules are now three explicit branches rather than state implied by whichever
#: alternation happened to consume, and the walk can be extended to carry state across
#: `\`-continuations, which no per-line pattern can do. (No shipped redirect spans one today.)
#:
#: STILL NOT COMPLETE, and must not be described as such: `$( … )` inside `"…"` re-enters shell
#: quoting, which this flat scanner does not model either — `hook-io.sh:161`'s shape still evades
#: it. That class stays ticketed, with its known-gap cell below so it is not rediscovered as a
#: surprise.
_META = frozenset(" \t<>;&|()")
#: An operator that sends stderr to `/dev/null`, then OPTIONAL whitespace, then the target,
#: optionally quoted. Every spelling accepted here was measured leaking the expanded path when the
#: output open comes first, AND measured quiet in the correct order — both halves matter, because
#: an operator that leaks in BOTH orders is not an ordering defect at all:
#:
#:     2>/dev/null   2> /dev/null   2>"/dev/null"   2>'/dev/null'   (kimi, local round)
#:     2>|/dev/null  2>>/dev/null                                   (codex, PR #78)
#:     &>/dev/null   >&/dev/null    2<>/dev/null                    (agy + codex, PR #78)
#:
#: `>|` overrides noclobber, `>>` appends, `&>`/`>&` take stdout with them and `2<>` opens
#: read-write; all of them still open `/dev/null` on fd 2, so all of them still suppress.
#:
#: NOT accepted, each for a MEASURED reason:
#:   * `2>&-` — closing stderr suppresses nothing. The path escapes in BOTH orders under both
#:     shells, so there is no ordering to fix and flagging one order would send the next reader to
#:     swap two things that leak either way.
#:   * `2>>|` — NOT legal bash. `bash 3.2.57: syntax error near unexpected token '|'`, in both
#:     orders. An earlier revision of this comment called it "legal shell … measured to leak" and
#:     a cell asserted it: the measurement behind that claim only checked that stderr was
#:     NON-EMPTY, and a syntax error makes stderr non-empty. All three review arms caught it
#:     independently. A leak test must match the PATH, not merely observe output.
_SUPPRESSION = re.compile(
    r"""[ \t]+(?:2>>|2>\||2<>|2>|&>|>&)[ \t]*"""
    r"""(?:"/dev/null"|'/dev/null'|/dev/null)(?![\w/])""")


def _subst_end(line, i, n):
    """Index just past the `)` closing the `$(` that starts at `i`, QUOTE-AWARE.

    Blind depth counting ends the substitution at a quoted paren — `$(echo ")")` and
    `$(echo ')')` both closed early, truncating what got scanned (gemini and codex, PR #78).
    There were TWO such loops, one here and one in the double-quote branch of the scanner; the
    second was left blind when the first was fixed, so they are now the same code.
    """
    depth, j = 0, i
    while j < n:
        ch = line[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "'":
            k = line.find("'", j + 1)
            j = n if k < 0 else k + 1
            continue
        if ch == '"':
            j += 1
            while j < n and line[j] != '"':
                j += 2 if line[j] == "\\" else 1
            j += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


def _word(line, i, n):
    """Consume ONE shell word from i; return (end, interpolates)."""
    start, var = i, False
    while i < n:
        c = line[i]
        if c == "\\":
            i += 2
        elif c == "'":
            j = line.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif c == '"':
            i += 1
            while i < n and line[i] != '"':
                var = var or line[i] == "$"
                i += 2 if line[i] == "\\" else 1
            i += 1
        elif c == "`":
            # Legacy `` `cmd` `` substitution is an interpolated target too (codex, local round).
            var = True
            j = line.find("`", i + 1)
            i = n if j < 0 else j + 1
        elif c == "$" and i + 1 < n and line[i + 1] == "(":
            # `$(cmd)` as part of the target: consume the balanced parens rather than stopping at
            # `(` (all three local arms). The tree's own idiom is `p="$(marker_path lint)"`.
            # QUOTE-AWARE paren counting (agy, local round). Blind counting ends the substitution
            # at a quoted `)` — `$(echo ")")` closed at the wrong paren, the word split, and the
            # leak was missed entirely.
            var = True
            i = _subst_end(line, i + 1, n)
        elif c in _META:
            break
        else:
            # `~` at the START of a word expands to the operator's HOME — the exact PII this guards.
            var = var or c == "$" or (c == "~" and i == start)
            i += 1
    return i, var


#: What ENDS a simple command, and therefore ends the reach of its redirections. `#` starts a
#: comment at a word boundary, which ends the command just as surely.
_CMD_END = frozenset(";&|)#")


def _suppressed_after(line, i, n):
    """True if a stderr suppression follows on the SAME simple command, past intervening words.

    Bash lets redirections and ordinary words interleave freely in a simple command, and applies
    every redirection left-to-right regardless of the order they are written in:

        printf x > "$tmp" < "$input" 2>/dev/null      further REDIRECT between   (codex, PR #78)
        printf x > "$tmp" ignored    2>/dev/null      ordinary WORD between      (codex, PR #78)

    Both open `$tmp` before stderr is suppressed and both were MEASURED to leak the expanded path.
    Requiring the suppression immediately after the target missed the first; requiring every
    intervening token to be a redirect missed the second. So: consume tokens of EITHER kind and
    stop at a command boundary — a redirect in the NEXT command suppresses nothing here, and
    `cmd > "$tmp"; echo hi 2>/dev/null` is an unconditional leak of a different shape, not this one.

    "A COMMAND BOUNDARY" HERE MEANS A LEXICAL ONE, which is weaker than it sounds and is stated
    plainly rather than implied: `_CMD_END` is tested against raw characters, so a `;` or `|`
    INSIDE an unquoted `${X:-a|b}` ends the scan even though bash does not end the command there,
    and the leak is missed. Likewise `<(…)` stops the scan dead. Both were measured leaking
    (agy + codex, PR #78); NEITHER shape occurs anywhere in the shipped tree, and closing them
    needs brace-balancing and process-substitution parsing that this deliberately flat scanner
    does not do. Ticketed on COREDEV-2760 with the here-doc and line-continuation classes, which
    are line-local for the same reason.
    """
    while True:
        if _SUPPRESSION.match(line, i):
            return True
        j = i
        while j < n and line[j] in " \t":
            j += 1
        if j >= n or line[j] in _CMD_END:
            return False
        if line[j] in "<>":                       # a further redirection: operator, then target
            j += 1
            while j < n and line[j] in "<>&|":
                j += 1
            while j < n and line[j] in " \t":
                j += 1
        j, _ = _word(line, j, n)                  # the target, or the ordinary word
        if j <= i:
            return False
        i = j


def inverted_redirect(line):
    """Column of an output redirect opening an interpolated target BEFORE `2>/dev/null`, else None.

    RETURNS A COLUMN, WHICH MAY BE 0 — callers must test `is not None`, never truthiness.
    """
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == "\\":
            i += 2
        elif c == "#" and (i == 0 or line[i - 1] in " \t;&|("):
            return None                     # a shell COMMENT starts here; nothing after it executes
        elif c == "'":
            j = line.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif c == "`":
            # RECURSE into legacy `` `cmd` `` too (codex, PR #78). Skipping it meant
            # ``B=`wc -c < "$OUT" 2>/dev/null` `` — a real leak, measured — returned None, while the
            # identical `$( … )` form was caught. Same substitution, same rule.
            j = line.find("`", i + 1)
            if j < 0:
                i = n
            else:
                hit = inverted_redirect(line[i + 1:j])
                if hit is not None:
                    return i + 1 + hit
                i = j + 1
        elif c == '"':
            # A `$( … )` INSIDE double quotes RE-ENTERS shell quoting, and a redirect in there is a
            # real redirect. This was pinned as a known gap until it was measured biting shipped
            # code: three of the four inverted INPUT redirects fixed in this commit sit inside
            # `"$( … )"` (`wc -c < "$OUT" 2>/dev/null`), so a sweep that skipped quoted regions
            # wholesale could not enforce its own rule on them. The substitution body is scanned
            # recursively; everything else inside the quotes is still literal.
            i += 1
            while i < n and line[i] != '"':
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == "$" and i + 1 < n and line[i + 1] == "(":
                    end = _subst_end(line, i + 1, n)
                    hit = inverted_redirect(line[i + 2:end - 1])
                    if hit is not None:
                        return i + 2 + hit
                    i = end
                    continue
                i += 1
            i += 1
        elif c in "<>":
            # INPUT OPENS TOO (codex, PR #78). `< "$path" 2>/dev/null` opens the path BEFORE the
            # suppression is installed, so an unreadable or missing file prints the expanded path
            # exactly as an output open does — measured in bash, and `log.sh:216-218` already
            # states the rule in prose ("`2>/dev/null` BEFORE the `<` input redirect"). Four
            # shipped lines carried the inverted form; they are fixed in this same commit.
            # `<<` heredoc and `<<<` here-string open no named path, so they are skipped.
            op = i
            if c == "<" and i + 1 < n and line[i + 1] == "<":
                i += 2
                if i < n and line[i] == "<":
                    i += 1
                continue
            i += 1
            if c == ">" and i < n and line[i] == ">":
                i += 1
            fd_dup = False
            if c == ">" and i < n and line[i] == "|":   # `>|` overrides noclobber, still opens
                i += 1
            elif i < n and line[i] == "&":             # `>&`/`<&` is fd-dup when the word is a digit
                i += 1
                fd_dup = True
            while i < n and line[i] in " \t":
                i += 1
            start = i
            i, var = _word(line, i, n)
            if fd_dup and re.fullmatch(r"\d+|-", line[start:i]):
                continue
            if i > start and var and _suppressed_after(line, i, n):
                return op
        else:
            i += 1
    return None


#: BASH only. `git` is REQUIRED by exactly two cells — the stop-gate pair, which builds a real
#: repo fixture — and gating the CLASS on it silently removed the marker cells and the whole
#: family sweep in any bash-equipped image without git (codex, PR #78); a new git-dependent
#: fixture must not narrow what was already covered.
#:
#: "Required" is the precise word, and an earlier revision here wrongly said the other five are
#: "pure filesystem work" (codex + kimi, PR #78). Three of them are; the two marker cells DO
#: reach `git` through `marker.sh:209` and `:267`, which tolerate its absence — measured with a
#: PATH holding every executable EXCEPT git: `marker_repo_hash` fell back to its pure-bash djb2
#: hash and the commit probe returned `unknown`, and all five cells passed. So the split is safe
#: for the reason stated, but not for the reason first written down.
@unittest.skipUnless(shutil.which("bash"), "needs bash")
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

    @unittest.skipUnless(shutil.which("git"), "builds a real repo fixture")
    def test_the_stop_gate_warn_log_does_not_leak_its_path_to_stderr(self):
        result = self._stop_gate_warn_onto_a_directory()
        self.assertEqual("", result.stderr,
                         f"the warn-log open failure leaked its path to stderr:\n{result.stderr}")

    @unittest.skipUnless(shutil.which("git"), "builds a real repo fixture")
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
                # `is not None`, NOT truthiness — a redirect at COLUMN 0 returns 0,
                # which `if` discards. `> "$HOME/leak" 2>/dev/null` at the start of a
                # line was silently skipped by the shipped sweep (codex, local round).
                if inverted_redirect(line) is not None:
                    offenders.append(f"{rel}:{number}: {line.strip()}")
        self.assertEqual([], offenders,
                         "these writers redirect into a temp file BEFORE suppressing stderr, so an "
                         "open failure prints the full path:\n  " + "\n  ".join(offenders))

    def test_the_sweep_would_catch_an_inverted_writer(self):
        """The sweep's own control: it must actually match the shape it claims to reject."""
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$_rb_path.tmp.$$" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect(
            "if [ -n \"$_STMP\" ] && printf '%s' \"$C\" > \"$_STMP\" 2>/dev/null; then"))
        # THE ONE THE NARROW PATTERN MISSED (COREDEV-2691) — an APPEND, to a target with no temp
        # marker in its name, in a file this suite already policed. Both narrowings had to go.
        self.assertIsNotNone(inverted_redirect('    >> "$LOGDIR/stop-gate.log" 2>/dev/null || true'))
        self.assertIsNotNone(inverted_redirect('cmd > "$COVERAGE_OUT" 2>/dev/null'))
        # UNQUOTED targets (gemini, PR #78) — the leak is the ORDER, not the quoting.
        self.assertIsNotNone(inverted_redirect('printf x > $tmp 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x >> $LOGDIR/stop-gate.log 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > ${TMP}.$$ 2>/dev/null'))
        # A redirect GLUED to the preceding word is still a redirect and still leaks. The obvious
        # "require a delimiter before >" widening drops these, and this tree already uses the
        # spaceless idiom (`9>"$_wt_p"`, `2>"$4/err"`).
        self.assertIsNotNone(inverted_redirect('printf x>"$tmp" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x> $LOG 2>/dev/null'))
        # CONCATENATED targets (codex, PR #78) — a word built from a quoted segment glued to an
        # unquoted one. Bash expands the whole word and names the resulting path when the open
        # fails, exactly as for a single-segment target; measured with a directory planted at it.
        # `"$VAR"/literal` is the tree's own idiom (eleven sites), so this is the shape a writer
        # added tomorrow is most likely to use.
        self.assertIsNotNone(inverted_redirect('printf x > "$LOGDIR"/stop-gate.log 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > /var/log/"$NAME" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$DIR""$NAME" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > $DIR"/x.log" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$DIR"\'/y.log\' 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('    >> "$LOGDIR"/stop-gate.log 2>/dev/null || true'))
        self.assertIsNotNone(inverted_redirect('printf x > "${LOGDIR}"/a.log 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x>"$LOGDIR"/a.log 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$DIR"/"sub dir"/f.json 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('cmd 1> "$DIR"/o.log 2>/dev/null'))
        # ...and the CORRECT order with a concatenated target must still not match.
        self.assertIsNone(inverted_redirect('printf x 2>/dev/null > "$LOGDIR"/a.log'))
        # A target that interpolates NOTHING leaks no operator path — `$` is what makes it PII.
        self.assertIsNone(inverted_redirect("printf x > '/tmp/lit' 2>/dev/null"))
        self.assertIsNone(inverted_redirect('cmd >&2 2>/dev/null'))
        # A QUOTED target CONTAINING SPACES must survive the widening — the obvious `"?`-based
        # form silently drops it, and this path is ordinary on macOS.
        self.assertIsNotNone(inverted_redirect('printf x > "$HOME/Application Support/s.json" 2>/dev/null'))
        # A literal `>` INSIDE a quoted string is not a redirect. This is what the quote-state
        # prefix buys over a delimiter class.
        self.assertIsNone(inverted_redirect('log "moved $a -> $b" 2>/dev/null'))
        self.assertIsNone(inverted_redirect('printf "a > $b\\n" 2>/dev/null'))
        # SINGLE-QUOTED text before the redirect (codex, PR #78). An ODD number of `"` inside a
        # single-quoted run desynced the old prefix; these redden against it and pass here.
        self.assertIsNotNone(inverted_redirect('printf \'%s:"x\' "$v" > "$tmp" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('awk -F\'"\' \'{print $2}\' "$in" >> $LOG 2>/dev/null'))
        # An escaped `\"` INSIDE a double-quoted run — closed as a side effect, so pin it.
        self.assertIsNotNone(inverted_redirect(r'grep -o "\"$f\":\"[^\"]*\"" "$p" > "$tmp" 2>/dev/null'))
        # A literal `>` inside SINGLE quotes is not a redirect either.
        self.assertIsNone(inverted_redirect("log 'moved $a > $b' 2>/dev/null"))
        # THE TRADE, recorded rather than silently made: a redirect inside a DEFERRED single-quoted
        # body is now invisible, because the body is one single-quoted run to this pattern. No such
        # site exists today — all three traps in the tree (precompact-snapshot.sh, changeset.sh,
        # linux-primitive-probe.sh) redirect nothing — and the class is ticketed.
        self.assertIsNone(inverted_redirect("""trap 'printf x > "$T" 2>/dev/null' EXIT"""))
        self.assertIsNone(inverted_redirect("""eval 'printf x > "$T" 2>/dev/null'"""))
        # THIS GAP IS CLOSED, and the cell is inverted to prove it. `$( )` inside `"…"` re-enters
        # shell quoting, and the sweep used to skip quoted regions wholesale. It was pinned as an
        # accepted trade until it was measured biting SHIPPED code: three of the four inverted
        # INPUT redirects fixed in this same commit sit inside `"$( … )"`, so the sweep could not
        # have enforced its own rule on them. Reverting any of the four is now caught.
        # Note this line also carries a real OUTER redirect, which is what is reported.
        self.assertIsNotNone(
            inverted_redirect('clean="$(printf \'%s\' "$s" | tr -d \'"\' )" > "$tmp" 2>/dev/null'))
        self.assertIsNotNone(
            inverted_redirect('BYTES="$(wc -c < "$OUT" 2>/dev/null | tr -d \' \')"'),
            "an inverted redirect INSIDE a substitution must be caught")
        self.assertIsNone(
            inverted_redirect('BYTES="$(wc -c 2>/dev/null < "$OUT" | tr -d \' \')"'),
            "the correct order inside a substitution must NOT be flagged")
        # ── SHAPES FOUND BY THE LOCAL REVIEW ROUND (codex / agy / kimi, all three arms) ──
        # A match at COLUMN ZERO. The scanner returns a column, and the caller used truthiness, so
        # 0 was discarded — a live bug in the shipped sweep, not a gap.
        self.assertEqual(0, inverted_redirect('> "$HOME/leak" 2>/dev/null'),
                         "a redirect at column 0 must report column 0, not None")
        # TILDE expands to the operator's HOME — the exact PII this suite guards.
        self.assertIsNotNone(inverted_redirect('printf x > ~/leak 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > ~root/leak 2>/dev/null'))
        # `>|` overrides noclobber and STILL opens the named path.
        self.assertIsNotNone(inverted_redirect('printf x >| "$TMP" 2>/dev/null'))
        # `>&` is fd-duplication ONLY when its word is digits or `-`; with a path it opens one.
        self.assertIsNotNone(inverted_redirect('printf x >& "$HOME/leak" 2>/dev/null'))
        self.assertIsNone(inverted_redirect('printf x >&2 2>/dev/null'))
        self.assertIsNone(inverted_redirect('printf x >&- 2>/dev/null'))
        # The SUPPRESSION's legal spellings. Every one of these was MEASURED to leak the expanded
        # path when the output open comes first; none is exotic.
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" 2> /dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" 2>"/dev/null"'))
        self.assertIsNotNone(inverted_redirect("printf x > \"$tmp\" 2>'/dev/null'"))
        # `2>|` (noclobber override) and `2>>` (append) still open /dev/null for stderr, so they
        # still suppress — and the scanner already treats `>|` as path-opening one level up, so
        # recognizing it there and not here was an inconsistency, not a judgement (codex, PR #78).
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" 2>|/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" 2>| /dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" 2>>/dev/null'))
        # `&>` and `>&` carry stdout along but still put /dev/null on fd 2, and `2<>` opens it
        # read-write. All three measured leaking with the open first and quiet in the correct
        # order (agy + codex, PR #78). `&>` is the idiomatic spelling and appears in this tree.
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" &>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" >&/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" 2<>/dev/null'))
        # `2>>|` is NOT legal bash — `syntax error near unexpected token '|'`, in both orders.
        # This cell asserted the opposite for one round, on a measurement that only checked
        # stderr was non-empty; the syntax error itself made it non-empty.
        self.assertIsNone(inverted_redirect('printf x > "$tmp" 2>>| /dev/null'))
        # NOT `2>&-`. Closing stderr suppresses nothing: measured, the path escapes in BOTH orders,
        # so it is an unconditional leak of a different class and calling it an ordering defect
        # would send the next reader to reorder a line that would still leak afterwards.
        self.assertIsNone(inverted_redirect('printf x > "$tmp" 2>&-'))
        # ORDINARY WORDS may sit between the redirect and the suppression (codex, PR #78). Bash
        # applies every redirection of a simple command left-to-right wherever it is written, so
        # this opens `$HOME/blocked` first and leaks — MEASURED, `bash: …/blocked: Is a directory`.
        self.assertIsNotNone(inverted_redirect('printf x > "$HOME/leak" ignored 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" --flag=v -q 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" < "$in" word 2>/dev/null'))
        # ...but the scan must STOP at a real command boundary. These do leak, and worse — nothing
        # suppresses them at all — but they are not INVERTED order, and reporting them as such
        # would tell the next reader to swap two things that are already in the only order there is.
        self.assertIsNone(inverted_redirect('printf x > "$tmp"; echo hi 2>/dev/null'))
        self.assertIsNone(inverted_redirect('printf x > "$tmp" && echo hi 2>/dev/null'))
        self.assertIsNone(inverted_redirect('printf x > "$tmp" | cat 2>/dev/null'))
        self.assertIsNone(inverted_redirect('printf x > "$tmp" & echo hi 2>/dev/null'))
        self.assertIsNone(inverted_redirect('( printf x > "$tmp" ) 2>/dev/null'))
        self.assertIsNone(inverted_redirect('printf x > "$tmp"  # 2>/dev/null in a comment'))
        # `$(cmd)` as the target: `(` is a metacharacter, so the word parse used to stop dead.
        # The tree's own idiom is `p="$(marker_path lint)"`.
        self.assertIsNotNone(inverted_redirect('printf x > $(marker_path lint) 2>/dev/null'))
        # A shell COMMENT executes nothing — and this repo writes long comments in shipped shell,
        # including ones QUOTING the wrong order. Flagging those would red CI on documentation.
        self.assertIsNone(inverted_redirect('# printf x > "$tmp" 2>/dev/null'))
        self.assertIsNone(
            inverted_redirect('    # WRONG ORDER: printf x > "$tmp" 2>/dev/null leaks'))
        # A `#` mid-word is NOT a comment introducer in shell.
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp"#frag 2>/dev/null'))
        # A QUOTED paren inside `$( … )` must not end the substitution early (agy, local round).
        # Blind depth counting closed at the wrong `)`, split the word, and missed the leak.
        self.assertIsNotNone(inverted_redirect('echo x > $(echo ")") 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect("echo x > $(echo ')') 2>/dev/null"))
        # KNOWN GAP, pinned: a here-doc BODY is data, but the sweep is line-local and cannot know
        # it is inside one. Ticketed with the `$( )`-inside-`"…"` class.
        self.assertIsNotNone(inverted_redirect('usage: tool > "$OUT" 2>/dev/null'))

        # ...and the correct order still must not match, in either redirect form.
        self.assertIsNone(inverted_redirect('printf x 2>/dev/null > "$tmp"'))
        self.assertIsNone(inverted_redirect('tail -n 5 "$p" 2>/dev/null > "$tmp"'))
        self.assertIsNone(inverted_redirect('    2>/dev/null >> "$LOGDIR/stop-gate.log" || true'))
        # A bare `2>/dev/null` with no output redirect at all must not match — the `>` inside it is
        # not an output redirect, and a pattern that thought so would flag most of the tree.
        self.assertIsNone(inverted_redirect('mkdir -p "$LOGDIR" 2>/dev/null || exit 0'))

    def test_the_sweep_covers_the_whole_shipped_shell_tree(self):
        """The derivation's own control. If `_shipped_shell()` ever returns a short or empty list the
        sweep above passes vacuously — which is precisely how the hand-written five-file list hid a
        real leak. Assert it reaches a realistic breadth AND names the files that carry the rule."""
        found = {rel.as_posix() for rel in _shipped_shell()}
        self.assertGreater(len(found), 15, f"suspiciously few shell files swept: {sorted(found)}")
        self.assertIn(".githooks/pre-commit", found,
                      "shipped executable bash without a `.sh` suffix must still be swept")
        self.assertTrue(any("/" in r.split("scripts/", 1)[-1].rstrip(".sh") for r in found
                            if r.startswith("scripts/") and r.count("/") > 1),
                        "the derivation must RECURSE — a flat glob silently drops nested dirs")
        for required in ("scripts/lib/marker.sh", "scripts/lib/context.sh", "scripts/lib/log.sh",
                         "scripts/precompact-snapshot.sh", "scripts/stop-quality-marker-gate.sh"):
            self.assertIn(required, found, "the original five must still be swept")


if __name__ == "__main__":
    unittest.main()
