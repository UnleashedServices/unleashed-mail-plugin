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
import sys
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
    # TRACKED, not globbed — the same policy the entrypoint census in the sibling module already
    # states, and the two were using OPPOSITE policies in one PR. The rule is about files that
    # SHIP: a developer's untracked scratch `scripts/review/probe.sh` does not ship, and globbing
    # let one red the required check locally. Measured: dropping an inverted redirect into an
    # untracked file was swept before this change and is invisible after it (codex, PR #78).
    #
    # NUL-delimited, because a tracked path may contain a space. The breadth control below asserts
    # this set EQUALS an independent git query, which is the only form that cannot silently narrow.
    # ...WHERE GIT EXISTS. Switching this census from a glob to `git ls-files` broke the
    # bash-equipped, git-less environment the class two hundred lines below deliberately supports
    # — `FileNotFoundError`, two errors, in the exact configuration a previous round of this PR
    # created the git-skip split to protect (codex, PR #78). "Tracked" is a REFINEMENT that only
    # has meaning where git does; without it, every `.sh` on disk is the best available answer to
    # "what ships", and the untracked-scratch exclusion is simply unavailable rather than fatal.
    if shutil.which("git"):
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z", "scripts/*.sh", "scripts/**/*.sh",
             ".githooks/pre-commit"],
            capture_output=True, text=True, check=True).stdout.split("\0")
        return sorted(Path(rel) for rel in out if rel)
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
#: THE PER-LINE LIMIT CUTS BOTH WAYS, and this note recorded only one of them. `cond` and
#: `stderr_off` reset at every PHYSICAL line while redirect detection does not, so besides the
#: false negatives already ticketed there are FALSE POSITIVES: a `\`-continuation loses an
#: already-installed suppression, and a multi-line `[[ … ]]` loses its comparison context — both
#: measured QUIET in bash and both flagged. The same root cause reaches the SIBLING module:
#: `test_plugin_state_base.py`'s composer scan cannot see a composer name split across a
#: continuation. All three members are on COREDEV-2760 together, because line joining changes
#: reported columns and `COMPOSES_UNDER_SENTINEL` is keyed on line numbers.
#:
#: STILL NOT COMPLETE, and must not be described as such — but the gaps are NOT the ones this
#: prologue used to name. It claimed `$( … )` inside `"…"` still evaded the scanner and cited
#: `hook-io.sh:161`; that class was closed (the double-quote branch recurses into `$( … )` and
#: into the legacy backtick spelling), the cell below asserts the closure in capitals, and
#: `hook-io.sh:161` carries no redirect at all so it was never an exemplar. It also promised a
#: "known-gap cell below" that does not exist. Three false statements in four lines, in the
#: prologue a reader meets first.
#:
#: WHAT IS ACTUALLY OPEN, all measured and all on COREDEV-2760: an unquoted `${X:-a|b}` ends the
#: scan at a character bash does not treat as a boundary; `<(…)` stops it dead; a `\`-continuation
#: and a here-doc body are invisible because the scan is per-line; `VAR=$(cmd > p) 2>…` needs the
#: `)` of `$(` told apart from a subshell's; `>/dev/null 2>&1` is not recognised as installing the
#: suppression because fd-1 state is not tracked; and `stderr_off` escapes a subshell.
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
#: PLATFORM-DIVERGENT, and accepted because of it: `2>&-` and `2</dev/null`.
#: On LINUX both suppress — measured in CI, inverted-leaks=True correct-leaks=False for each — so
#: the inverted order is a real ordering defect there. On macOS bash 3.2 both leak in BOTH orders.
#: I declined them twice on that macOS-only measurement, once for `2>&-` early in the campaign and
#: once for `2<` in review, calling each "not a suppression". That was PLATFORM-BLIND, not wrong
#: arithmetic: the same command has different behaviour on the two systems this plugin runs on, and
#: a guard that protects only the machine I happened to measure on is not a guard. The criterion
#: cell below caught it on its first CI run, which is the whole reason it exists.
#:
#: NOT accepted, for a reason that does not vary by platform:
#:   * `2>>|` — NOT legal bash. `syntax error near unexpected token '|'`, in both orders. An
#:     earlier revision of this comment called it "legal shell … measured to leak" and a cell
#:     asserted it: the measurement behind that claim only checked that stderr was NON-EMPTY, and
#:     a syntax error makes stderr non-empty. All three review arms caught it independently.
#:     A leak test must match the PATH, not merely observe output.
_SUPPRESSION = re.compile(
    r"""[ \t]+(?:2>&-|(?:2>>|2>\||2<>|2>|2<|&>|>&)[ \t]*"""
    r"""(?:"/dev/null"|'/dev/null'|/dev/null))(?![\w/])""")


def _backtick_end(line, i, n):
    """Index of the backtick CLOSING the one at `i`, skipping escaped ones, or -1.

    ``B=`printf '\\`'; wc -c < "$p" 2>/dev/null` `` is valid bash and leaks, but a raw
    `line.find` stopped at the escaped literal and skipped the executable remainder, so the
    scanner returned None (codex, PR #78). Same hole inside double quotes.
    """
    j = i + 1
    while j < n:
        if line[j] == "\\":
            j += 2
            continue
        if line[j] == "`":
            return j
        j += 1
    return -1


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
            # THE THIRD SITE. `_backtick_end` was written for the two sites in the scanner loop and
            # this one kept its raw `find`, so an escaped literal backtick inside a substitution
            # used AS THE TARGET ended the word early and the leak returned None (codex, PR #78).
            # Third time in this PR that one construct had several spellings and I fixed some of
            # them: the fix is to route every site through one helper, not to patch the next one.
            var = True
            j = _backtick_end(line, i, n)
            i = n if j < 0 else j + 1
        elif c == "$" and i + 1 < n and line[i + 1] == "'":
            # ANSI-C quoting ONLY. `> $'$HOME/blocked'` opens a file literally named
            # `$HOME/blocked`; a failed open prints that text, not the operator's home — measured —
            # so flagging it reported PII that cannot be there.
            #
            # `$"…"` IS NOT THE SAME and must not be folded in. Locale-translated double quotes
            # still perform parameter expansion, so `> $"$HOME/blocked"` opens the EXPANDED home
            # path and leaks it — measured. The previous revision treated both spellings as literal
            # and so turned a fix for one into a false negative for the other (codex, PR #78).
            # ESCAPE-AWARE, unlike the plain `'…'` branch above — and that difference is the
            # point: inside `'…'` a backslash is literal and nothing can escape the closing quote,
            # while `$'…'` processes `\'`. `> $'foo\''"$HOME/x" 2>/dev/null` is valid bash and
            # leaks; scanning to the next RAW quote stopped at the escaped one and swallowed the
            # real interpolation that followed (codex, PR #78). Fourth site of "find the closing
            # delimiter without honouring escapes" in this file — the other three were backticks.
            close, _j = -1, i + 2
            while _j < n:
                if line[_j] == "\\":
                    _j += 2
                    continue
                if line[_j] == "'":
                    close = _j
                    break
                _j += 1
            i = n if close < 0 else close + 1
        elif c == "$" and i + 1 < n and line[i + 1] == '"':
            i += 1                                 # fall into the double-quote scan below, which
            continue                               # tracks `$` and sets `var` correctly
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

    Two pieces of state are carried across the scan, both added to stop the sweep redding CI on
    correct shipped code (codex, PR #78):

    `cond`   — depth of `[[ … ]]`, where `<` and `>` are LEXICOGRAPHIC COMPARISONS, not redirects.
               `[[ z > "$HOME" ]] 2>/dev/null` opens nothing and was measured quiet, yet it was
               reported at column 5. A shipped conditional in that shape would have failed the
               family sweep.
    `stderr_off` — whether a suppression is ALREADY installed earlier in this same simple command.
               `printf x 2>/dev/null > "$HOME/x" 2>/dev/null` is measured QUIET: the first
               redirect takes effect before the open, so the later one is belt-and-braces, not an
               inversion. Deciding from a trailing suppression alone called that safe ordering a
               defect. Reset at every command boundary, because the next command starts clean.
    """
    i, n = 0, len(line)
    cond, stderr_off = 0, False
    # A REDIRECTION-ONLY `exec` IS PERMANENT. `exec 2>/dev/null; printf x > "$p" 2>/dev/null` has
    # the second open already quiet, because that `exec` redirected the SHELL's stderr rather than
    # one command's — so clearing the state at the `;` reported a safe line (codex, PR #78). Once
    # seen, the state survives every boundary on the line.
    # ...AND ONLY WHEN IT TOUCHES FD 2. `exec 1>/dev/null` redirects stdout permanently and says
    # nothing about stderr, so treating it as persistence made a LATER command's ordinary
    # suppression outlive its own `;` and hid a real leak (codex, PR #78). A previous round added
    # this flag to fix a false positive and made it too broad in the same stroke.
    # ...and the LAST one wins. `exec 2>/dev/null; exec 2>&1; …` RESTORES fd 2, so the
    # persistence must end there — a line-wide boolean computed from the first `exec` kept a later
    # command's temporary suppression alive and hid a real leak (codex, PR #78). Fourth time on
    # this PR that redirect state was right in one direction and wrong in the other, which is why
    # every one of these now carries a paired assertion.
    # ...and it applies FORWARD ONLY. A line-wide prescan let an `exec` at the END of the line
    # silence a leak written BEFORE it — `printf x > "$p" 2>/dev/null; exec 2>/dev/null` is
    # measured leaking and returned None (codex, PR #78). Redirections do not act backwards.
    # Each mark records where an fd-2 `exec` sits and what it left fd 2 pointing at; the boundary
    # consults only the marks that precede it.
    _exec_marks = [(_m.start(), _m.group(1).strip(";").strip("\"'").endswith("/dev/null"))
                   for _m in re.finditer(
                       r"(?:^|[;&|]\s*)exec\s+((?:2[<>]|&>|>&)[^\s;|&]*)", line)]

    def _persisted(at):
        state = False
        for _pos, _on in _exec_marks:
            if _pos >= at:
                break
            state = _on
        return state
    while i < n:
        c = line[i]
        if c == "\\":
            i += 2
        elif c == "#" and (i == 0 or line[i - 1] in " \t;&|()"):
            return None                     # a shell COMMENT starts here; nothing after it executes
        elif c == "'":
            j = line.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif c == "`":
            # RECURSE into legacy `` `cmd` `` too (codex, PR #78). Skipping it meant
            # ``B=`wc -c < "$OUT" 2>/dev/null` `` — a real leak, measured — returned None, while the
            # identical `$( … )` form was caught. Same substitution, same rule.
            j = _backtick_end(line, i, n)
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
                if line[i] == "`":
                    # ...and the LEGACY spelling of the same thing. `$( … )` inside `"…"` was
                    # recursed into while `` `…` `` inside `"…"` was walked straight past, so
                    # ``B="`wc -c < "$OUT" 2>/dev/null`"`` returned None while the `$( … )` form
                    # was caught (codex, PR #78). Two spellings of one construct must not have
                    # two behaviours — that asymmetry is what this file keeps being bitten by.
                    close = _backtick_end(line, i, n)
                    if close < 0:
                        i = n
                        break
                    hit = inverted_redirect(line[i + 1:close])
                    if hit is not None:
                        return i + 1 + hit
                    i = close + 1
                    continue
                i += 1
            i += 1
        elif line.startswith("[[", i) and (i == 0 or line[i - 1] in " \t;&|(") :
            cond += 1
            i += 2
        elif line.startswith("]]", i) and cond:
            cond -= 1
            i += 2
        elif (c in ";|" or (c == "&" and line[i + 1:i + 2] != ">")) and not _persisted(i):
            stderr_off = False                 # a new command inherits none of the old redirects
            i += 1
        elif c in "<>" and cond:
            i += 1                             # a comparison inside `[[ … ]]`, not a redirect
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
            # `<>` OPENS READ-WRITE AND IS ONE OPERATOR. Leaving the `>` half to be re-processed
            # made `printf x 2<>/dev/null > "$p" 2>/dev/null` parse as two redirects, so
            # `stderr_off` was never set for the `2<>` and the later SAFE open was reported as
            # inverted (codex, PR #78) — a false positive created by adding `2<>` to the
            # suppression set two commits ago without teaching the parser the same spelling.
            if c == "<" and i < n and line[i] == ">":
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
            if fd_dup and line[start:i] == "-":
                # CLOSING fd 2 installs the suppression on Linux exactly as redirecting it does,
                # so the state must record it — otherwise the matcher accepts `2>&-` at the end of
                # a command while the scanner refuses to believe an earlier `2>&-` covers a later
                # open, which is the same one-way-state defect in a new place.
                m = re.search(r"(?:^|[\s;&|()])(\d+)$", line[:op])
                if (m.group(1) if m else "") == "2":
                    stderr_off = True
                continue
            if fd_dup and re.fullmatch(r"\d+|-", line[start:i]):
                # A DUPLICATION ONTO FD 2 UNDOES AN EARLIER SUPPRESSION.
                # `printf x 2>/dev/null 2>&1 > "$p" 2>/dev/null` puts the UNsuppressed stdout
                # back on fd 2 before the open, so the failed open is exposed again — yet
                # `stderr_off` stayed set from the first redirect and the leak returned None
                # (codex, PR #78). Treating every duplication as irrelevant is what made the
                # state one-way, and one-way state is a false-negative engine.
                m = re.search(r"(?:^|[\s;&|()])(\d+)$", line[:op])
                if (m.group(1) if m else "") == "2":
                    stderr_off = False
                continue
            if line[start:i].strip("\"'") == "/dev/null":
                # THIS redirect is the suppression. It counts as covering the rest of the command
                # only if it is on fd 2 (`2>`, `2<>`) or takes stdout with it (`&>`, `>&`).
                # A REAL IO-NUMBER TOKEN, not just trailing digits. `printf x $2>/dev/null >
                # "$HOME/leak" 2>/dev/null` has `$2` as an ARGUMENT and the `>` as an fd-1
                # redirect, so the later open still leaks — but the digits of `$2` were read as
                # the fd, `stderr_off` was set, and the leak returned None. A regression from the
                # stderr-state fix earlier in this same PR (codex, PR #78): an IO number must be
                # a word of its own, so require a delimiter before it.
                m = re.search(r"(?:^|[\s;&|()])(\d+)$", line[:op])
                fd = m.group(1) if m else ""
                if fd == "2" or (op and line[op - 1] == "&") or line[op + 1:op + 2] == "&":
                    stderr_off = True
                continue
            if i > start and var and not stderr_off and _suppressed_after(line, i, n):
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
        # body is invisible, because the body is one single-quoted run to this pattern.
        #
        # The justification is stated BY SHAPE, because the hand-listed version was wrong twice
        # over: it said "all three traps in the tree … redirect nothing" when the tree holds TWELVE
        # executable trap sites, and one of the three it named — `precompact-snapshot.sh:67`,
        # `trap 'rm -f "$TMP" 2>/dev/null' EXIT` — does carry a redirect. The conclusion survives
        # on the shape: no deferred single-quoted body in this tree OPENS A PATH before suppressing
        # stderr (that trap's redirect is a bare suppression with no open), and the `trap <function>`
        # sites defer to function bodies that live on their own, swept, lines. An enumeration is
        # not a class — the file says so elsewhere, and then did this.
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
        # EXEC PERSISTENCE IS ABOUT FD 2 ONLY. `exec 1>/dev/null` says nothing about stderr, so
        # a LATER command's ordinary suppression must still expire at its own `;` — measured
        # leaking. The previous round added the persistence flag to kill a false positive and made
        # it too broad in the same stroke.
        self.assertIsNotNone(inverted_redirect(
            'exec 1>/dev/null; printf x 2>/dev/null; printf y > "$HOME/leak" 2>/dev/null'))
        self.assertIsNone(
            inverted_redirect('exec 2>/dev/null; printf x > "$HOME/leak" 2>/dev/null'))
        self.assertIsNone(
            inverted_redirect('exec &>/dev/null; printf x > "$HOME/leak" 2>/dev/null'))
        # ...and only FORWARD. An `exec` at the end of the line cannot silence a leak written
        # before it; redirections do not act backwards. Measured leaking, returned None.
        self.assertIsNotNone(inverted_redirect(
            'printf a 2>/dev/null; printf x > "$HOME/leak" 2>/dev/null; exec 2>/dev/null'))
        # ...and the LAST exec touching fd 2 decides. `exec 2>/dev/null; exec 2>&1; …` RESTORES
        # stderr, so a later command's own suppression must expire normally again - measured
        # leaking through stdout. A line-wide boolean taken from the FIRST exec kept it alive.
        self.assertIsNotNone(inverted_redirect(
            'exec 2>/dev/null; exec 2>&1; printf a 2>/dev/null; '
            'printf x > "$HOME/leak" 2>/dev/null'))
        self.assertIsNone(inverted_redirect(
            'exec 2>&1; exec 2>/dev/null; printf x > "$HOME/leak" 2>/dev/null'))
        # A `#` AFTER `)` STARTS A COMMENT. `(:)# printf x > "$HOME/leak" 2>/dev/null` runs only
        # the subshell - measured quiet - and was reported, so a shipped line in that shape would
        # have failed the sweep. Third narrowing of the same boundary set.
        self.assertIsNone(inverted_redirect('(:)# printf x > "$HOME/leak" 2>/dev/null'))
        # A REDIRECTION-ONLY `exec` IS PERMANENT, so the state must survive the boundary after it.
        # Measured quiet; clearing at the `;` reported a safe line.
        self.assertIsNone(
            inverted_redirect('exec 2>/dev/null; printf x > "$HOME/leak" 2>/dev/null'))
        # ...but an ORDINARY command before a `;` must still reset it, or the fix is a blanket pass.
        self.assertIsNotNone(
            inverted_redirect('printf x 2>/dev/null; printf y > "$HOME/leak" 2>/dev/null'))
        # ANSI-C quoting PROCESSES ESCAPES, unlike plain `'...'`. Scanning to the next raw quote
        # stopped at the escaped one and swallowed the real interpolation after it. Measured leaking.
        self.assertIsNotNone(inverted_redirect(
            "printf x > $'foo\\''\"$HOME/leak\" 2>/dev/null"))
        # `2>&-` and `2</dev/null` ARE suppressions on Linux — measured in CI, quiet in the
        # correct order and leaking in this one — so the inverted order is a real defect there.
        # These two cells asserted the opposite for several rounds on a macOS-only measurement.
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" 2>&-'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" 2</dev/null'))
        # ...and installed FIRST, each covers the later open, so neither is reported.
        self.assertIsNone(inverted_redirect('printf x 2>&- > "$tmp"'))
        self.assertIsNone(inverted_redirect('printf x 2</dev/null > "$tmp"'))
        # ORDINARY WORDS may sit between the redirect and the suppression (codex, PR #78). Bash
        # applies every redirection of a simple command left-to-right wherever it is written, so
        # this opens `$HOME/blocked` first and leaks — MEASURED, `bash: …/blocked: Is a directory`.
        self.assertIsNotNone(inverted_redirect('printf x > "$HOME/leak" ignored 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" --flag=v -q 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x > "$tmp" < "$in" word 2>/dev/null'))
        # ...but the scan must STOP at a real command boundary. For the `;`, `&&`, `|` and `&`
        # members these DO leak, and worse — nothing suppresses them at all — but they are not
        # INVERTED order, and reporting them as such would tell the next reader to swap two things
        # already in the only order there is.
        #
        # THE SUBSHELL MEMBER IS HERE FOR THE OPPOSITE REASON, and the comment used to cover it
        # with the sentence above, which is false about it: `( printf x > "$tmp" ) 2>/dev/null` is
        # measured QUIET. A redirection written on a compound command is installed before the group
        # body runs, so the trailing suppression DOES cover the open. `)` belongs in `_CMD_END`
        # because the redirect covers the group, not because nothing suppresses it. Right
        # assertion, inverted reason — which is how a later round talks itself into "fixing" it.
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

        # ── FALSE POSITIVES THAT WOULD RED CI ON CORRECT SHIPPED CODE (codex, PR #78) ──
        # Inside `[[ … ]]`, `<` and `>` are lexicographic COMPARISONS. Measured quiet — bash opens
        # nothing — yet this was reported at column 5, so a shipped conditional in that shape would
        # have failed the family sweep.
        self.assertIsNone(inverted_redirect('[[ z > "$HOME" ]] 2>/dev/null'))
        self.assertIsNone(inverted_redirect('[[ "$a" < "$b/x" ]] 2>/dev/null'))
        # ...but a single `[ … ]` is an ordinary command where `>` IS a redirect, and a `[[ … ]]`
        # that closes must stop protecting what follows it.
        self.assertIsNotNone(inverted_redirect('[ -n "$v" ] && printf x > "$tmp" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('[[ -n "$v" ]] && printf x > "$tmp" 2>/dev/null'))
        # A suppression ALREADY INSTALLED before the open covers it: measured QUIET. The trailing
        # repeat is belt-and-braces, not an inversion, and reporting it sends the reader to "fix"
        # an ordering that is already correct.
        self.assertIsNone(inverted_redirect('printf x 2>/dev/null > "$tmp" 2>/dev/null'))
        self.assertIsNone(inverted_redirect('printf x &>/dev/null > "$tmp" 2>/dev/null'))
        # ...and it must NOT carry across a command boundary — the next command starts clean.
        self.assertIsNotNone(inverted_redirect('a 2>/dev/null; printf x > "$tmp" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('a 2>/dev/null | printf x > "$tmp" 2>/dev/null'))
        # `<>` IS ONE OPERATOR. Leaving its `>` half to be re-parsed as a second redirect meant
        # `2<>/dev/null` never registered as a suppression, and the later SAFE open was reported.
        # Measured quiet in bash. A false positive created by adding `2<>` to the suppression set
        # without teaching the parser the same spelling.
        self.assertIsNone(inverted_redirect('printf x 2<>/dev/null > "$HOME/leak" 2>/dev/null'))
        # ...and `2<>` must still COUNT as a suppression when it comes after the open.
        self.assertIsNotNone(inverted_redirect('printf x > "$HOME/leak" 2<>/dev/null'))
        # ANSI-C QUOTING IS LITERAL. `$'$HOME/x'` names a file literally called `$HOME/x`; a
        # failed open prints that text, NOT the operator's home — measured. Treating the leading
        # `$` as interpolation reported PII that cannot be there. The plain single-quoted
        # equivalent on the line below was already accepted, so this was an inconsistency.
        self.assertIsNone(inverted_redirect("printf x > $'$HOME/leak' 2>/dev/null"))
        # ...but `$"…"` IS NOT THE SAME CONSTRUCT, and this cell asserted that it was for one
        # round. Locale-translated double quotes still perform parameter expansion, so the open
        # uses the EXPANDED home path and leaks it - measured. Folding the two spellings together
        # turned a fix for one into a false negative for the other.
        self.assertIsNotNone(inverted_redirect('printf x > $"$HOME/leak" 2>/dev/null'))
        # ...while a REAL expansion in the same position still flags.
        self.assertIsNotNone(inverted_redirect('printf x > $HOME/leak 2>/dev/null'))
        # THE THIRD BACKTICK SITE: a substitution used as the TARGET kept a raw `find`, so an
        # escaped literal backtick ended the word early. Measured leaking.
        self.assertIsNotNone(inverted_redirect(
            "printf x > `printf '\\`' >/dev/null; printf \"$HOME/leak\"` 2>/dev/null"))
        # A DUPLICATION ONTO FD 2 UNDOES AN EARLIER SUPPRESSION. Measured: the open error comes
        # back out, because `2>&1` puts the UNsuppressed stdout on fd 2 before the open. State
        # that only ever turns on is a false-negative engine.
        self.assertIsNotNone(
            inverted_redirect('printf x 2>/dev/null 2>&1 > "$HOME/leak" 2>/dev/null'))
        # ...while a duplication that leaves fd 2 alone must NOT reopen the state.
        self.assertIsNone(
            inverted_redirect('printf x 2>/dev/null 1>&2 > "$HOME/leak" 2>/dev/null'))
        # An ESCAPED backtick is data, not the closing delimiter. Measured valid bash, and it
        # leaks: `bash: …/nope/x: No such file or directory`. Scanning to the next RAW backtick
        # stopped at the literal and skipped the executable remainder.
        self.assertIsNotNone(inverted_redirect(
            "B=`printf '\\`'; wc -c < \"$O\" 2>/dev/null`"))
        # `$2` IS AN EXPANSION, NOT AN IO NUMBER. `printf x $2>/dev/null > "$HOME/leak"
        # 2>/dev/null` passes `$2` as an argument and redirects fd 1; the later open still leaks.
        # Reading the `2` of `$2` as the fd marked stderr already-suppressed and returned None —
        # a regression introduced by the stderr-state fix earlier in this same PR.
        self.assertIsNotNone(inverted_redirect('printf x $2>/dev/null > "$HOME/leak" 2>/dev/null'))
        self.assertIsNotNone(inverted_redirect('printf x "$v"2>/dev/null > "$t" 2>/dev/null'))
        # ...while a genuine IO number, standing as its own word, still counts.
        self.assertIsNone(inverted_redirect('printf x 2>/dev/null > "$t" 2>/dev/null'))
        self.assertIsNone(inverted_redirect('printf x; cmd 2>/dev/null > "$t" 2>/dev/null'))
        # A LEGACY substitution inside double quotes is the same construct as `$( … )` there, and
        # measured the same leak: `bash: …/nope/x: No such file or directory`. It was walked past
        # while `"$( … )"` was recursed into — two spellings of one construct, two behaviours.
        self.assertIsNotNone(inverted_redirect('BYTES="`wc -c < "$OUT" 2>/dev/null`"'))
        self.assertIsNone(inverted_redirect('BYTES="`wc -c 2>/dev/null < "$OUT"`"'))

    def test_every_accepted_suppression_is_one_and_every_rejected_one_is_not(self):
        """The allowlist checked against its CRITERION, not member by member.

        An operator belongs in `_SUPPRESSION` if and only if it makes the open error disappear
        when written FIRST and lets it through when written LAST. Curating the list one finding
        at a time is how `2>>|` got in on a bad measurement and how `2<` was proposed on a false
        premise: both leak in BOTH orders, so neither is a suppression and neither has an ordering
        to fix. This cell runs the criterion over every spelling the file has an opinion about, so
        a wrong entry cannot survive review again.
        """
        target = self.scratch / "home" / "blocked"
        target.mkdir(exist_ok=True)

        def leaks(line):
            script = self.scratch / "supp.sh"
            script.write_text("#!/bin/bash\n" + line + "\n", encoding="utf-8")
            r = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=self.env)
            return str(self.scratch / "home") in (r.stdout + r.stderr)

        # SUPPRESSES ON LINUX, LEAKS BOTH WAYS ON macOS bash 3.2 — measured on both. The scanner
        # is platform-independent and must protect the stricter platform, so these are accepted
        # everywhere. Naming them here is what keeps "accepted although it does not suppress on
        # THIS machine" from becoming a silent exception.
        PLATFORM_DIVERGENT = {"2>&-", "2</dev/null"}
        # `2>>| /dev/null` is in this list so the criterion has a REJECT case and stays two-sided:
        # it is not legal bash, so it suppresses nowhere and must not be accepted. Without it every
        # member is expected-accepted and a wrongly-widened `_SUPPRESSION` would sail through.
        for op in ("2>/dev/null", "2>|/dev/null", "2>>/dev/null", "&>/dev/null",
                   ">&/dev/null", "2<>/dev/null", "2</dev/null", "2>&-", "2>>| /dev/null"):
            with self.subTest(operator=op):
                inverted = leaks('printf x > "$HOME/blocked" ' + op)
                correct = leaks("printf x " + op + ' > "$HOME/blocked"')
                suppresses_here = inverted and not correct
                accepted = inverted_redirect('printf x > "$t" ' + op) is not None
                self.assertEqual(
                    suppresses_here or op in PLATFORM_DIVERGENT, accepted,
                    f"{op!r} on {sys.platform}: bash says inverted-leaks={inverted} "
                    f"correct-leaks={correct} (a suppression here is True/False); scanner "
                    f"accepts={accepted}; platform-divergent={op in PLATFORM_DIVERGENT}. "
                    f"Accept an operator if it suppresses on ANY supported platform — a guard that "
                    f"protects only the machine it was measured on is not a guard. Reject it only "
                    f"if it leaks in both orders EVERYWHERE, or is not legal shell.")
                # NOTE, deliberately not an assertion: on Linux these two DO suppress, so
                # `suppresses_here` is True there and False here. "Divergent" is a property of the
                # SET of platforms, and no single run can see both. An earlier draft failed the
                # cell when a divergent operator suppressed locally — which would have red every
                # Linux run, the platform the required check uses.

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
