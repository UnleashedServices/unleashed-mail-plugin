#!/usr/bin/env python3
"""COREDEV-2503 F4 — quote/escape/operator-aware scanner that lists the WRITE-TARGET file words of a bash
command. Replaces sensitive-file-guard.sh's O(n^2) `_split_segments` per-char loop AND its quote-blind
`grep` extractions (redirects, rm/interpreter basenames, cp/mv operands), which BOTH over-asked on a
*quoted* operator (`echo '> Keychain.swift'`) and bypassed on a mid-word quote (`rm Key"chain".swift`).

Contract: read the command on stdin; print each candidate write-target word NEWLINE-delimited on stdout, fully
DE-QUOTED (so `Key"chain".swift` -> `Keychain.swift`). The caller (the guard) filters by its own
sensitive-basename policy and emits the ask. Exit 0 on success; exit 3 on an internal parse failure so the
guard can fail CLOSED (deny) rather than exit-0-without-decision. Whole-pipeline O(n): one linear lexer pass,
no quadratic accumulation.

Coverage (adversarial sweep, codex review of #53): redirect writes incl. `>&`(file form, not fd-dup);
`--` end-of-options; command wrappers (env/sudo/nice/timeout/nohup/doas/arch/xcrun/taskset/chrt/...) with
their arg/positional consumption; brace-group `{ …; }`; command-substitution/expansion inside a target
(`$(…)`, backticks, trailing subshell `)`, brace suffix) via a substring scan for old-grep parity; verbs
rm/mv/cp/ln/install/ditto/rsync/tee/sponge/sed-i/dd/truncate/touch/find(+ `-exec CMD …`)/patch(+
`--output=`/`--reject-file`)/git(rm|mv|checkout --|restore); fetch-to-file `curl -o/--output` and
`wget -O/--output-document` incl. clustered short forms (`curl -so F`); and interpreters bash/sh/python/perl/ruby(-e; -E is
encoding)/node/osascript/awk(`print > "f"`), INCLUDING versioned executables (`python3.12`, `node20`). Shell
reserved-word prefixes (`! rm X`, `if rm X; then …`) are unwrapped. Input redirects (`tee out < K.swift`) are
reads, not writes — their source is NOT emitted.

Best-effort by design: a determined adversary can hide a target from ANY textual heuristic (base64,
indirection). Deliberately NOT modeled (documented gaps, no worse than the old grep): runtime GLOB/wildcard
metachars (`rm Key?.swift`, `[K]eychain.swift`) and brace expansion that splits the stem from the extension
(`Keychain.{swift,bak}`); read-vs-write discrimination INSIDE arbitrary interpreter code (a referenced file
over-asks — the fail-SAFE direction); BROAD tree operations that do not NAME a file (`git restore .`,
`rm -rf <dir>`) — out of scope for a basename policy exactly as a bare directory delete is (a `.`/directory
pathspec cannot be enumerated without repo access); and ARCHIVE EXTRACTION (`tar -x`, `unzip`) whose written
names come from the archive, not the command line, so a basename policy cannot enumerate them (same class as
`rm -rf <dir>`; `curl -O`/`wget`'s URL-derived remote-name is likewise unnamable on the command line). This closes the quote-blindness + O(n^2)-timeout
fail-opens, the sweep's write classes, and catches accidental writes.
"""
from __future__ import annotations

import re
import shlex
import sys

# File extensions the interpreter-inline-code / eval scan treats as candidate file words (coupled to the
# guard's sensitive set by TYPE, not by the full basename policy which stays in bash).
_CODE_SCAN_EXTS = ("swift", "entitlements", "plist", "pbxproj", "mobileprovision", "xcodeproj")
# Extract WHOLE path-like tokens ending in a candidate extension from inline code (`open("X.swift")`), so
# the basename is `OAuthService.swift.bak` not the `.swift` prefix substring (matches the old grep).
_CODE_FILE_RE = re.compile(r"[A-Za-z0-9._/-]+\.(?:%s)[A-Za-z0-9._-]*" % "|".join(_CODE_SCAN_EXTS))

# Operators, longest first so `>>`/`>|`/`&&`/`||`/`|&`/`<<-` win over their shorter prefixes.
_OPS = (">>", ">|", "&>>", "&>", "<<<", "<<-", "<<", "<&", ">&", "&&", "||", "|&", ";;", "|", "&", ";", "(", ")", "{", "}", "<", ">")


_ANSI_C = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n", "r": "\r",
           "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}


def _decode_ansi_c(s: str) -> str:
    """Decode a bash ANSI-C `$'…'` body — `\\n`, `\\t`, `\\xHH`, octal `\\NNN`, `\\uHHHH`, `\\UHHHHHHHH` — so
    `$'Keychain\\x2eswift'` becomes `Keychain.swift` (codex review of #53)."""
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c != "\\" or i + 1 >= n:
            out.append(c); i += 1; continue
        nxt = s[i + 1]
        if nxt in _ANSI_C:
            out.append(_ANSI_C[nxt]); i += 2
        elif nxt in ("x", "u", "U"):
            width = {"x": 2, "u": 4, "U": 8}[nxt]
            j = i + 2; h = ""
            while j < n and len(h) < width and s[j] in "0123456789abcdefABCDEF":
                h += s[j]; j += 1
            if h:
                try:
                    out.append(chr(int(h, 16)))
                except (ValueError, OverflowError):
                    out.append(nxt)
                i = j
            else:
                out.append(nxt); i += 2
        elif nxt in "01234567":
            j = i + 1; o = ""
            while j < n and len(o) < 3 and s[j] in "01234567":
                o += s[j]; j += 1
            out.append(chr(int(o, 8) & 0xFF)); i = j
        else:
            out.append(nxt); i += 2                       # unknown escape -> the literal char
    return "".join(out)


def _parse_heredoc_delim(cmd: str, pos: int) -> tuple[str, int]:
    """After a `<<`/`<<-`, parse the delimiter (bare / quoted / backslashed) and return (delim, index_after
    the delimiter — still on the SAME line). The body is consumed later, at the next newline, so redirects
    or args that follow `<<DELIM` on the same line (`cat <<EOF > file`) are still parsed (codex review #53)."""
    n = len(cmd)
    j = pos
    while j < n and cmd[j] in " \t":
        j += 1
    # parse a FULL shell word as the delimiter, applying quote removal — bash accepts `<<EOF+`, `<<E@F`,
    # `<<'E O F'`, `<<E\ F`, `<<EO'F'`. The prior alnum/`_-.` char class truncated `EOF+` to `EOF`, so the
    # real terminator line `EOF+` never matched and every following command was swallowed as body (A4).
    delim: list[str] = []
    while j < n:
        c = cmd[j]
        if c in " \t\r\n" or c in "|&;()<>":
            break                                    # unquoted whitespace/metacharacter ends the word
        if c == "'":
            k = cmd.find("'", j + 1)
            if k == -1:
                k = n
            delim.append(cmd[j + 1:k]); j = k + 1
        elif c == '"':
            k = j + 1
            while k < n and cmd[k] != '"':
                if cmd[k] == "\\" and k + 1 < n and cmd[k + 1] in '"$`\\':
                    delim.append(cmd[k + 1]); k += 2
                else:
                    delim.append(cmd[k]); k += 1
            j = k + 1
        elif c == "\\":
            if j + 1 < n:
                delim.append(cmd[j + 1]); j += 2
            else:
                j += 1
        else:
            delim.append(c); j += 1
    return "".join(delim), j


def _consume_heredoc_body(cmd: str, pos: int, delim: str, strip_tabs: bool) -> tuple[str, int]:
    """From `pos` (start of the first body line) read lines up to a line == `delim` (leading tabs stripped
    for `<<-`). Returns (body, index after the terminator line)."""
    n = len(cmd)
    k = pos
    body_lines: list[str] = []
    while k <= n:
        le = cmd.find("\n", k)
        if le == -1:
            le = n
        line = cmd[k:le]
        cand = line.lstrip("\t") if strip_tabs else line
        # tolerate a CRLF terminator: `EOF\r` must still match the `EOF` delimiter, else the heredoc never
        # closes and the rest of the command is swallowed as body (a write after it bypasses — gemini #53).
        if cand.rstrip("\r") == delim:
            return "\n".join(body_lines), (le + 1 if le < n else n)
        body_lines.append(line)
        if le == n:
            break
        k = le + 1
    return "\n".join(body_lines), n

_REDIR_WRITE = (">", ">>", ">|", "&>", "&>>")   # active redirect operators whose following WORD is written
# every operator whose following WORD is a redirect TARGET/SOURCE (not a command operand): the write forms
# above PLUS `>&`(file form) and the input forms `<`/`<&`/`<<<`. Used to drop redirect words from operand
# lists so an INPUT redirect (`tee out < Keychain.swift`) does not over-ask on the read source.
_REDIR_ANY = (">", ">>", ">|", "&>", "&>>", ">&", "<", "<&", "<<<")
_STMT_SEP = (";", "&&", "||", "&", ";;", "\n")   # statement boundaries (NOT `|` — a pipeline stays together)

# verb -> write-target rule
_DELETE_ALL = {"rm", "unlink", "shred", "rmdir"}          # every non-flag operand
_MOVE_ALL = {"mv", "rename"}                              # every non-flag operand (source removed + dest)
_DEST_LAST = {"cp", "install", "ln", "ditto", "rsync"}   # dest = -t DIR, else last non-flag operand
_TEE = {"tee", "sponge"}                                 # every non-flag operand (`sponge FILE` writes FILE)
_TRUNCATE = {"truncate"}                                 # non-flag operands (skip -s SIZE / -r REF value args)
_AWK = {"awk", "gawk", "mawk", "nawk"}                   # `print > "f"` inside the program string writes files
_INLINE_SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "python", "python2", "python3", "osascript"}
_INLINE_ALWAYS = {"eval", "source", "."}                # run an arbitrary string/file -> scan it
# command wrappers that exec a FOLLOWING command; the real write verb is the wrapped word. `_PREFIX_1POS`
# additionally consume ONE leading non-option positional (timeout DURATION, chrt PRIORITY, taskset MASK).
_PREFIXES = {"env", "command", "sudo", "nice", "ionice", "time", "builtin", "exec", "stdbuf", "setsid",
             "nohup", "doas", "timeout", "arch", "xcrun", "unbuffer", "catchsegv", "chrt", "taskset", "run0"}
# wrappers that ALWAYS carry exactly one leading positional before the verb (timeout DURATION, chrt PRIO).
# taskset is handled separately: its MASK positional is present only in the bare form (absent with -c/-p).
_PREFIX_1POS = {"timeout", "chrt"}
# per-prefix options that consume a SEPARATE-form value arg (so the value is not mistaken for the verb).
_PREFIX_VAL_OPTS = {
    "env": {"-u", "-C", "-P", "--unset", "--chdir", "--path"},
    "nice": {"-n", "--adjustment"},
    "doas": {"-u", "-C", "-a"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "arch": {"-e", "-u"},
    "taskset": {"-c", "-p", "--cpu-list", "--pid"},
    "xcrun": {"--sdk", "--toolchain"},
    "sudo": {"-u", "--user", "-g", "--group", "-U", "--other-user", "-C", "--close-from", "-p", "--prompt",
             "-r", "--role", "-t", "--type", "-R", "--chroot", "-D", "--chdir", "-T", "--command-timeout"},
    "ionice": {"-c", "--class", "-n", "--classdata", "-p", "--pid"},
}
# shell reserved words that precede a command (`! rm X`, `if rm X; then …`, `while rm X; do …`,
# `function f { … }`): strip them so the real verb surfaces instead of `!`/`if`/`while` (codex review #53).
_SHELL_KEYWORDS = {"!", "if", "then", "elif", "else", "while", "until", "do", "function", "coproc"}
# a function-definition header `name()` / `name(){` — strip it so the body command is scanned
# (`f(){ rm K.swift; }; f` deletes K.swift when called). codex review of #53.
_FUNC_DEF_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\(\)\{?$")
# interpreter stems, for normalizing versioned executables (`python3.12`->`python`, `node20`->`node`).
_INTERP_STEMS = {"python", "ruby", "node", "nodejs", "perl", "bash", "sh", "zsh", "dash", "ksh",
                 "osascript", "awk", "gawk", "mawk", "nawk"}


def _tokenize(cmd: str) -> list[list[dict]]:
    """One linear pass. Returns a list of STATEMENTS; each statement is a list of tokens. A token is
    {"k": "W"|"O", "dq": <dequoted text>, "raw": <as written>} for a word, or {"k": "O", "op": <operator>}.
    Quote/escape aware: a `>`/`;`/`|` inside quotes or after a backslash is a LITERAL word char, never an
    operator. A `#` starting a word (unquoted) begins a comment to end-of-line."""
    statements: list[list[dict]] = []
    toks: list[dict] = []
    w_dq: list[str] = []          # dequoted chars of the current word
    w_raw: list[str] = []         # raw chars of the current word
    in_word = False
    pending_heredocs: list = []   # (delim, strip_tabs) awaiting their body at the next unquoted newline
    i, n = 0, len(cmd)

    def flush_word():
        nonlocal in_word
        if in_word:
            toks.append({"k": "W", "dq": "".join(w_dq), "raw": "".join(w_raw)})
            w_dq.clear(); w_raw.clear()
            in_word = False

    def end_statement():
        flush_word()
        if toks:
            statements.append(list(toks))
            toks.clear()

    while i < n:
        c = cmd[i]
        # --- unquoted comment: `#` at a word boundary runs to end of line ---
        if c == "#" and not in_word:
            while i < n and cmd[i] != "\n":
                i += 1
            continue
        # --- whitespace (unquoted) ends a word. `\r` too: a CRLF command must not glue `\r` onto a word
        #     (`Keychain.swift\r` would miss the basename policy — gemini review of #53). ---
        if c in " \t\r":
            flush_word()
            i += 1
            continue
        if c == "\n":
            if pending_heredocs:
                # consume each pending heredoc body (in order) starting AFTER this newline — the redirect/
                # args on the `cmd <<EOF > file` line were already tokenized, so they are preserved — then
                # end the statement (codex review #53).
                flush_word()          # flush the last word on this line (e.g. the redirect TARGET) BEFORE
                pos = i + 1           # the H tokens, so `>` is followed by its target word, not by `H`
                for delim, strip_tabs in pending_heredocs:
                    body, pos = _consume_heredoc_body(cmd, pos, delim, strip_tabs)
                    toks.append({"k": "H", "body": body})
                pending_heredocs = []
                end_statement()
                i = pos
            else:
                end_statement()
                i += 1
            continue
        # --- backslash escape (outside quotes): next char is a literal word char ---
        if c == "\\":
            # `\<newline>` (and CRLF `\<\r\n>`) is a LINE CONTINUATION — bash removes the pair, joining the
            # word across the break (`rm Keychain.\<nl>swift` -> `Keychain.swift`). Don't emit the newline
            # (write_targets discards newline-bearing targets, which would drop the name) — codex review #53.
            if i + 1 < n and cmd[i + 1] == "\n":
                i += 2
                continue
            if i + 2 < n and cmd[i + 1] == "\r" and cmd[i + 2] == "\n":
                i += 3
                continue
            if i + 1 < n:
                w_dq.append(cmd[i + 1]); w_raw.append(c + cmd[i + 1]); in_word = True
                i += 2
            else:
                w_raw.append(c); w_dq.append(c); in_word = True
                i += 1
            continue
        # --- ANSI-C quoting `$'…'`: bash decodes escapes BEFORE running the command, so `rm $'K\x2eswift'`
        #     deletes `K.swift`. Decode the body (respecting `\'` inside) — codex review of #53. ---
        if c == "$" and i + 1 < n and cmd[i + 1] == "'":
            j = i + 2
            while j < n and cmd[j] != "'":
                j += 2 if (cmd[j] == "\\" and j + 1 < n) else 1
            w_dq.append(_decode_ansi_c(cmd[i + 2:j])); w_raw.append(cmd[i:min(j + 1, n)]); in_word = True
            i = j + 1
            continue
        # --- single quotes: everything literal to the next ' ---
        if c == "'":
            j = cmd.find("'", i + 1)
            if j == -1:      # unterminated -> take the rest literally (fail toward a word, not a crash)
                j = n
            w_dq.append(cmd[i + 1:j]); w_raw.append(cmd[i:min(j + 1, n)]); in_word = True
            i = j + 1
            continue
        # --- double quotes: \ escapes " $ ` \ ; else literal, to the next unescaped " ---
        if c == '"':
            j = i + 1
            buf_dq: list[str] = []
            buf_raw = ['"']
            while j < n and cmd[j] != '"':
                if cmd[j] == "\\" and j + 1 < n and cmd[j + 1] == "\n":
                    buf_raw.append(cmd[j:j + 2]); j += 2         # `\<nl>` line continuation inside "" (codex #53)
                elif cmd[j] == "\\" and j + 2 < n and cmd[j + 1] == "\r" and cmd[j + 2] == "\n":
                    buf_raw.append(cmd[j:j + 3]); j += 3         # CRLF continuation
                elif cmd[j] == "\\" and j + 1 < n and cmd[j + 1] in '"$`\\':
                    buf_dq.append(cmd[j + 1]); buf_raw.append(cmd[j:j + 2]); j += 2
                else:
                    buf_dq.append(cmd[j]); buf_raw.append(cmd[j]); j += 1
            buf_raw.append('"' if j < n else "")
            w_dq.append("".join(buf_dq)); w_raw.append("".join(buf_raw)); in_word = True
            i = j + 1
            continue
        # --- unquoted command substitution: keep `$(...)` / `` `...` `` as ONE word so an internal space
        #     or operator is NOT statement structure and a name inside survives to the substring scan ---
        if c == "`":
            j = i + 1
            while j < n and cmd[j] != "`":
                j += 2 if (cmd[j] == "\\" and j + 1 < n) else 1
            span = cmd[i:min(j + 1, n)]
            w_dq.append(span); w_raw.append(span); in_word = True
            i = j + 1
            continue
        if c == "$" and i + 1 < n and cmd[i + 1] == "(":
            depth = 1; j = i + 2
            while j < n and depth:
                if cmd[j] == "(":
                    depth += 1
                elif cmd[j] == ")":
                    depth -= 1
                j += 1
            span = cmd[i:j]
            w_dq.append(span); w_raw.append(span); in_word = True
            i = j
            continue
        # --- operators (unquoted) ---
        matched = None
        for op in _OPS:
            if cmd.startswith(op, i):
                matched = op
                break
        if matched is not None:
            if matched in ("(", ")", "{", "}") and in_word:
                # a `(`/`)`/`{`/`}` ATTACHED to a word is part of a code token (`unlink(X.swift)`) or brace
                # expansion (`Keychain.swift{,.bak}`), NOT a group — only a STANDALONE one is a boundary.
                w_dq.append(c); w_raw.append(c); in_word = True
                i += 1
                continue
            if matched == "{" and any(t["k"] == "W" for t in toks):
                # `{` in ARGUMENT position (a verb already present, e.g. `cp {a,b}.swift dst`) is brace
                # expansion, not a `{ …; }` group — keep it as a literal word char.
                w_dq.append(c); w_raw.append(c); in_word = True
                i += 1
                continue
            flush_word()
            if matched in ("<<", "<<-"):     # heredoc: record the delimiter; the BODY is consumed at the
                delim, after = _parse_heredoc_delim(cmd, i + len(matched))   # next newline, so a redirect
                if delim:                    # or arg after `<<DELIM` on THIS line is still parsed
                    pending_heredocs.append((delim, matched == "<<-"))
                    i = after
                else:
                    toks.append({"k": "O", "op": matched}); i += len(matched)
                continue
            if matched in ("(", ")"):        # standalone grouping: statement boundary, drop the token
                end_statement()
            elif matched == "{":             # command-position `{ list; }` group open -> drop the boundary
                pass                         # (arg-position `{` was kept literal above)
            elif matched == "}":             # standalone group close -> drop the boundary (never a verb)
                end_statement()
            elif matched in _STMT_SEP:
                end_statement()
            else:
                toks.append({"k": "O", "op": matched})
            i += len(matched)
            continue
        # --- ordinary word char ---
        w_dq.append(c); w_raw.append(c); in_word = True
        i += 1

    end_statement()
    return statements


def _basecmd(word: str) -> str:
    """Basename of a command word, dropping a `/usr/bin/` path prefix. `env`-style names stay as-is."""
    return word.rsplit("/", 1)[-1]


def _strip_prefixes(words: list[str]) -> list[str]:
    """Drop leading `VAR=val` assignments and command prefixes (env/sudo/command/…), consuming the option
    args that env-style prefixes eat (`env -u NAME`, `env -C DIR`, `nice -n 5`), so the real verb surfaces."""
    idx = 0
    while idx < len(words):
        w = words[idx]
        base = _basecmd(w)
        if w == "function":                          # `function NAME [()] { body }` -> skip the keyword AND
            idx += 2 if idx + 1 < len(words) else 1   # the NAME/header word so the body command surfaces
            continue
        if w in _SHELL_KEYWORDS or w == "{":
            idx += 1; continue                       # `!`/`if`/`while`/… or a group `{` open
        if _FUNC_DEF_RE.match(w):
            idx += 1; continue                       # `name()` / `name(){` header -> scan the body that follows
        if "=" in w and not w.startswith("-") and w.split("=", 1)[0].isidentifier() and base == w:
            idx += 1; continue                       # VAR=val assignment
        if base in _PREFIXES:
            probe = False
            split_string = False
            val_consumed = False
            val_opts = _PREFIX_VAL_OPTS.get(base, ())
            # single-letter forms of the value-taking options, for CLUSTERED short opts (`sudo -Su USER`,
            # where `-u` is last so its value is the next token) — codex/gemini review of #53.
            val_letters = {o[1] for o in val_opts if len(o) == 2 and o[0] == "-"}
            idx += 1
            # consume this prefix's option-args that take a following token
            while idx < len(words) and words[idx].startswith("-"):
                opt = words[idx]
                idx += 1
                if base == "command" and opt in ("-v", "-V"):
                    probe = True                      # `command -v rm X` LOOKS UP rm; it does not run it
                elif base == "xcrun" and opt in ("-f", "--find"):
                    probe = True                      # `xcrun -f rm` prints rm's PATH; it does not run it
                elif base == "env" and opt in ("-S", "--split-string"):
                    split_string = True               # the REMAINING tokens are the command string
                    break
                elif opt in val_opts:                 # option that consumes a separate-form value arg
                    if idx < len(words):
                        idx += 1; val_consumed = True
                elif len(opt) > 2 and not opt.startswith("--"):
                    # clustered short opts: the FIRST value-taking letter consumes a value. If it is the
                    # LAST char the value is the NEXT token (`sudo -Su USER`); if more follows it is an
                    # ATTACHED value (`sudo -uUSER`) and no extra token is consumed (codex/gemini #53).
                    cluster = opt[1:]
                    for _pos, _ch in enumerate(cluster):
                        if _ch in val_letters:
                            if _pos == len(cluster) - 1 and idx < len(words):
                                idx += 1; val_consumed = True
                            break
            if probe:
                return []                             # a probe executes nothing -> no write target
            if split_string:
                rest = words[idx:]
                if rest and " " in rest[0]:           # `env -S 'rm X'` -> the quoted split-string is the cmd
                    try:                              # shlex so a quoted arg with spaces stays ONE token
                        rest = shlex.split(rest[0]) + rest[1:]   # (`env -S 'rm "a b.swift"'`, gemini #53)
                    except ValueError:                # unbalanced quotes -> best-effort whitespace split
                        rest = rest[0].split() + rest[1:]
                return _strip_prefixes(rest)          # the split command may carry its own VAR=val/env prefix
            if idx < len(words) and not words[idx].startswith("-") and (
                base in _PREFIX_1POS                          # `timeout DURATION cmd` / `chrt PRIO cmd`
                or (base == "taskset" and not val_consumed)   # bare `taskset MASK cmd` (absent when -c/-p given)
            ):
                idx += 1
            continue
        break
    return words[idx:]


def _has_inline_code(words: list[str], verb: str) -> bool:
    """True if an interpreter statement carries INLINE CODE (so a file NAMED INSIDE it is a write target).
    Shells + python use `-c`; perl/ruby use `-e`/`-E`; node uses `-e`/`-p`/`--eval`/`--print`. A shell `-e`
    is errexit, NOT code. Handles clustered short flags (`-xc`, `-we`) and code adjacent to the flag
    (`-c"..."`)."""
    if verb == "perl":                               # perl `-e` AND `-E` both run inline code
        code_flags = ("e", "E")
    elif verb == "ruby":                             # ruby `-e` is code; `-E`/`-K` are ENCODING (take an arg)
        code_flags = ("e",)
    elif verb in ("node", "nodejs"):
        code_flags = ("e", "p")
    elif verb == "osascript":                        # osascript's inline flag is `-e`, not `-c`
        code_flags = ("e",)
    else:                                            # shells + python
        code_flags = ("c",)
    for w in words[1:]:
        if not w.startswith("-") or w.startswith("--"):
            # node long-form inline code: `--eval`/`--print`, ALSO the documented `=` form `--eval=CODE`
            # (codex review #53 — the bare-equality check missed it).
            if verb in ("node", "nodejs") and w.split("=", 1)[0] in ("--eval", "--print"):
                return True
            continue
        cluster = w[1:]
        # code adjacent (`-c"..."`, `-ceval`): the flag letter, then more chars
        for cf in code_flags:
            pos = cluster.find(cf)
            if pos != -1:
                return True
    return False


# `${var:-DEFAULT}` / `${var:=DEFAULT}` / `${var:+ALT}` (and the colon-less forms): capture the DEFAULT/ALT
# value so `rm ${x:-Info.plist}` isn't emitted as `-Info.plist` (the `:-` glue breaks an EXACT basename
# match). codex review of #53.
_PARAM_EXPANSION = re.compile(r"\$\{[A-Za-z_]\w*(?:\[[^\]]*\])?:?[-=+?]([^}]*)\}")


def _files_in_word(word: str) -> list[str]:
    """Extension-shaped path tokens in a word: the direct matches PLUS the default/alternate value of any
    `${var:-…}` parameter expansion (whose `:-`/`:=` operator otherwise glues onto the name)."""
    files = _CODE_FILE_RE.findall(word)
    for default in _PARAM_EXPANSION.findall(word):
        files += _CODE_FILE_RE.findall(default)
    return files


def _emit_scan_words(words: list[str], out: list[str]) -> None:
    """Extract file-extension-shaped path tokens from inline-code / eval operands (a sensitive name is a
    SUBSTRING of the de-quoted code, e.g. `open("OAuthService.swift","w")`)."""
    for w in words:
        out.extend(_files_in_word(w))


def _emit_target(word: str, out: list[str]) -> None:
    """Emit ONE write-target word: the literal (basename-matched by the guard) PLUS any extension-shaped
    token embedded in it. The embedded scan gives old-grep parity for command-substitution / expansion
    forms whose literal basename slips the policy: `$(printf Keychain.swift)` and `` `echo K.swift` `` (the
    trailing `)`/`` ` `` glue on), a trailing subshell paren (`(rm K.swift)` -> `K.swift)`), a brace suffix
    (`K.swift{,.bak}`), and a `${var:-DEFAULT}` default value. A determined adversary can still hide a name
    (base64/indirection) — the module is best-effort by contract."""
    if word:
        out.append(word)
    out.extend(_files_in_word(word))


def _is_fd_ref(word: str) -> bool:
    """A `>&`/`<&` operand that is a file-DESCRIPTOR reference (`>&2`, `>&-`, `>&2-`), not a filename — so
    `echo x >&2` / `2>&1` are fd dup/close (no file write), while `echo x >& log` truncates `log`."""
    return word == "-" or re.fullmatch(r"\d+-?", word) is not None


def _targets_nonflag(operands: list[str], out: list[str]) -> None:
    """Emit every non-flag operand as a write target, honoring the `--` end-of-options marker: operands
    after the first bare `--` are targets even if they start with `-` (`rm -- -Keychain.swift`)."""
    after_dd = False
    for o in operands:
        if after_dd:
            _emit_target(o, out)
        elif o == "--":
            after_dd = True
        elif not o.startswith("-"):
            _emit_target(o, out)


_GIT_VAL_OPTS = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
# `git checkout`/`restore` options that consume a following NAME (a branch/ref/file, NOT a pathspec target).
_GIT_CO_VAL_OPTS = {"-s", "--source", "--pathspec-from-file", "-b", "-B", "-t", "--track", "--orphan", "--conflict"}


def _looks_like_code_file(word: str) -> bool:
    """True if a word carries a guard-relevant file extension — used to tell a `git checkout` PATHSPEC
    (`git checkout Keychain.swift`, overwrites the file) from a BRANCH/ref name (`git checkout main`)."""
    return _CODE_FILE_RE.search(word) is not None


def _scan_git(operands: list[str], out: list[str]) -> None:
    """git subcommands that WRITE/DELETE working-tree files: `git rm` (delete), `git mv` (source removed +
    dest written), and the working-tree overwrites `git checkout [<ref>] [--] <path>` / `git restore
    <path>` (both discard local edits). A bare `git checkout <branch>` is a branch switch — no target; so
    without `--`, a checkout operand is treated as a pathspec only when it LOOKS like a file (gemini review
    of #53). A broad `.`/directory pathspec names no file and is out of scope (see the module docstring)."""
    i, n = 0, len(operands)
    while i < n and operands[i].startswith("-"):     # skip git's own global opts to reach the subcommand
        i += 2 if operands[i] in _GIT_VAL_OPTS else 1
    if i >= n:
        return
    sub, rest = operands[i], operands[i + 1:]
    if sub in ("rm", "mv"):
        _targets_nonflag(rest, out)                  # rm: every path; mv: source(s) removed + dest written
    elif sub in ("checkout", "restore"):
        if "--" in rest:                             # explicit pathspec after `--` -> all are targets
            for o in rest[rest.index("--") + 1:]:
                _emit_target(o, out)
        else:                                        # no `--`: emit pathspec operands (restore: all;
            skip = False                             # checkout: only file-shaped ones, to skip branch names)
            for o in rest:
                if skip:
                    skip = False
                elif o in _GIT_CO_VAL_OPTS:
                    skip = True
                elif not o.startswith("-") and (sub == "restore" or _looks_like_code_file(o)):
                    _emit_target(o, out)


# xargs's OWN options that take a separate-form argument (`-n 1`, `-I {}`, `--max-args 1`).
_XARGS_ARG_OPTS = {"-n", "-L", "-I", "-P", "-s", "-E", "-e", "-d", "-a",
                   "--max-args", "--max-lines", "--replace", "--max-procs", "--max-chars",
                   "--eof", "--delimiter", "--arg-file"}


def _strip_xargs_opts(operands: list[str]) -> list[str]:
    """Skip xargs's OWN options (and a separate-form arg) so the CHILD command word surfaces — otherwise
    `xargs -n 1 rm` / `xargs -I{} rm {}` / `xargs -0 -P4 rm` read `-n`/`-I{}`/`-0` as the verb and the
    sensitive-write bypasses the guard (COREDEV-2503 F12, codex review of #53)."""
    i, n = 0, len(operands)
    while i < n:
        o = operands[i]
        if o == "--":
            return operands[i + 1:]
        if not o.startswith("-"):
            return operands[i:]
        if o in _XARGS_ARG_OPTS:       # separate-form arg: `-n 1`, `-I {}`, `--max-args 1`
            i += 2
        else:                          # `--opt=val`, attached short arg (`-n1`/`-I{}`), or a no-arg/cluster flag
            i += 1
    return []


def _norm_interp(verb: str) -> str:
    """Map a versioned interpreter basename to its stem so `python3.12`/`ruby3.3`/`node20`/`perl5.38` reach
    the inline-code arm. Rewrites ONLY when the stem is a known interpreter (so `sha256`/`s3` are untouched)."""
    m = re.match(r"^([a-z]+?)[0-9][0-9.]*$", verb)
    return m.group(1) if m and m.group(1) in _INTERP_STEMS else verb


def _sed_is_inplace(operands: list[str]) -> bool:
    """True if a sed invocation edits its file operands IN PLACE (`-i`, `--in-place`, clustered `-ni`)."""
    return any(
        o == "--in-place" or o.startswith("--in-place=")
        or (o.startswith("-") and not o.startswith("--") and "i" in o[1:])
        for o in operands
    )


def _command_writes_operands(sub: list[str]) -> bool:
    """True if a command WRITES/DELETES its file operands — used for a child whose operands are not
    statically visible: an xargs child (operands from stdin) or a `find -exec` child (operands are the
    matched `{}` files). Kept CONSISTENT with the main-dispatch write verbs so `xargs touch`/`find -exec
    patch` don't bypass: delete/move/tee/dest-copy, `truncate`, in-place `sed`, `touch`, `patch`, and a
    git WRITE subcommand (rm/mv/checkout/restore) — but NOT a read like `git log` (gemini review of #53)."""
    if not sub:
        return False
    subverb = _basecmd(sub[0])
    if subverb in _DELETE_ALL or subverb in _MOVE_ALL or subverb in _TEE or subverb in _DEST_LAST or subverb in _TRUNCATE:
        return True
    if subverb in ("touch", "patch", "dd"):           # dd writes via `of=` (codex review of #53)
        return True
    if subverb == "sed":
        return _sed_is_inplace(sub[1:])
    if subverb == "git":                              # skip git's global opts to reach the subcommand
        i, gn = 1, len(sub)                            # (`git -C DIR rm …`) — codex review of #53
        while i < gn and sub[i].startswith("-"):
            i += 2 if sub[i] in _GIT_VAL_OPTS else 1
        return i < gn and _basecmd(sub[i]) in ("rm", "mv", "checkout", "restore")
    return False


def _scan_fetch_output(operands: list[str], out: list[str], long_flags: tuple[str, ...],
                       short_letter: str) -> None:
    """MIN-15: emit the output-file target of a download-to-file (`curl -o F`, `wget -O F`). `long_flags`
    are the `--long` forms that take the path; `short_letter` is the value-taking short option (curl `o`,
    wget `O`). Handles `-o F`, attached `-oF`, `--output=F`, AND a short CLUSTER ending in the letter
    (`curl -so F` / `-fsSo F`) — the exact `curl -so OAuthService.swift URL` form the guard was missing.
    `curl -O`/`wget`'s URL-derived remote-name forms name no local path here and are intentionally left
    to the best-effort contract (over-ask is the fail-SAFE direction)."""
    emit_next = False
    for o in operands:
        if emit_next:
            _emit_target(o, out)
            emit_next = False
        elif o in long_flags:
            emit_next = True
        elif any(o.startswith(lf + "=") for lf in long_flags):
            _emit_target(o.split("=", 1)[1], out)
        elif o.startswith("-") and not o.startswith("--") and short_letter in o[1:]:
            rest = o[o.index(short_letter, 1) + 1:]
            if rest:
                _emit_target(rest, out)          # attached value: `-oF` / `-soF`
            else:
                emit_next = True                 # letter is last in the cluster -> value is the next arg


def _scan_command(words: list[str], out: list[str], all_words: list[str], heredoc_bodies: list[str],
                  emitted_all: list | None = None) -> None:
    """Extract the write targets of ONE command (a pipeline stage, or a `find -exec` sub-command). Applies
    prefix/keyword stripping, then dispatches on the verb."""
    words = _strip_prefixes(words)
    if not words:
        return
    verb = _basecmd(words[0])
    iverb = _norm_interp(verb)                        # versioned interpreter -> stem (for the interp arms)
    operands = words[1:]

    if verb in _DELETE_ALL or verb in _MOVE_ALL or verb in _TEE:
        _targets_nonflag(operands, out)
    elif verb in _TRUNCATE:
        skip = False; after_dd = False
        for o in operands:
            if skip:
                skip = False
            elif after_dd:
                _emit_target(o, out)
            elif o == "--":
                after_dd = True
            elif o in ("-s", "--size", "-r", "--reference"):
                skip = True
            elif not o.startswith("-"):
                _emit_target(o, out)
    elif verb in _DEST_LAST:
        tdir = ""; last = ""; skip = False; after_dd = False
        for o in operands:
            if skip:
                tdir = o; skip = False
            elif after_dd:
                last = o
            elif o == "--":
                after_dd = True
            elif o in ("-t", "--target-directory"):
                skip = True
            elif o.startswith("--target-directory="):
                tdir = o.split("=", 1)[1]
            elif not o.startswith("-"):
                last = o
        _emit_target(tdir or last, out)
        if verb == "rsync" and "--remove-source-files" in operands:
            _targets_nonflag(operands, out)          # `rsync --remove-source-files` DELETES the sources
    elif verb == "touch":
        skip = False; after_dd = False
        for o in operands:
            if skip:
                skip = False
            elif after_dd:
                _emit_target(o, out)
            elif o == "--":
                after_dd = True
            elif o in ("-r", "--reference", "-d", "--date", "-t"):
                skip = True
            elif o.startswith("--reference=") or o.startswith("--date="):
                pass
            elif not o.startswith("-"):
                _emit_target(o, out)
    elif verb == "sed":
        if _sed_is_inplace(operands):
            _targets_nonflag(operands, out)
    elif verb == "patch":
        emit_next = False; skip = False
        for o in operands:
            if emit_next:
                _emit_target(o, out); emit_next = False       # `-o`/`-r` value is a WRITTEN file
            elif skip:
                skip = False
            elif o in ("-o", "--output", "-r", "--reject-file"):
                emit_next = True                              # output file / hunk-failure reject file
            elif o.startswith("--output=") or o.startswith("--reject-file="):
                _emit_target(o.split("=", 1)[1], out)
            elif (o.startswith("-o") or o.startswith("-r")) and len(o) > 2:
                _emit_target(o[2:], out)                     # attached short form `-oFILE`/`-rFILE`
            elif o in ("-i", "--input", "-p", "--strip", "-B", "--prefix", "-D", "--ifdef",
                       "-F", "--fuzz", "-z", "--suffix", "-Y", "--basename-prefix", "-V", "--version-control"):
                skip = True
            elif not o.startswith("-"):
                _emit_target(o, out)                          # the patched file (modified in place)
    elif verb == "curl":
        _scan_fetch_output(operands, out, ("--output",), "o")   # `curl -o F URL` fetches remote -> F
    elif verb == "wget":
        _scan_fetch_output(operands, out, ("--output-document",), "O")  # `wget -O F URL`
    elif verb == "git":
        _scan_git(operands, out)
    elif verb == "trap":
        # `trap 'ACTION' SIGSPEC…` runs ACTION when the signal fires (e.g. a deferred `rm K.swift` on EXIT)
        # — scan the ACTION string as a command. Skip query forms (`-p`/`-l`) and reset/ignore (`-`/'')
        # (codex review of #53).
        action = None
        for o in operands:
            if o == "--" or (o.startswith("-") and len(o) > 1):
                continue                                      # -p (print), -l (list), or `--`
            action = o
            break
        if action and action != "-":
            out.extend(write_targets(action))                # the action is itself a command string
    elif iverb in _AWK:
        prog = None; uses_progfile = False; skip = False
        for o in operands:
            if skip:
                skip = False
            elif o in ("-f", "--file"):
                uses_progfile = True; skip = True
            elif o in ("-v", "--assign", "-F", "--field-separator"):
                skip = True                                   # separate-form value (`-F ','`) — consume it
            elif o.startswith("-f"):                          # so it isn't mistaken for the program (gemini #53)
                uses_progfile = True
            elif o.startswith("-"):
                pass
            elif prog is None:
                prog = o                                      # first non-option operand is the awk program
        if prog and not uses_progfile and ">" in prog:        # `print > "f"` / `printf >> "f"` write files
            _emit_scan_words([prog], out)
    elif verb == "dd":
        for o in operands:
            if o.startswith("of="):
                _emit_target(o[3:], out)
    elif verb == "find":
        # First scan every `-exec/-ok CMD … ;|+` sub-command (`find . -exec rm K.swift \;`) and note whether
        # any MODIFIES the matched files (rm/mv/sed -i/…) — if so, the matched START PATHS are writes too.
        exec_writes = False
        m = 0
        while m < len(operands):
            if operands[m] in ("-exec", "-execdir", "-ok", "-okdir"):
                sub: list[str] = []
                j = m + 1
                while j < len(operands) and operands[j] not in (";", "+"):
                    if operands[j] != "{}":
                        sub.append(operands[j])
                    j += 1
                if sub:
                    _scan_command(sub, out, all_words, [], emitted_all)
                    exec_writes = exec_writes or _command_writes_operands(_strip_prefixes(sub))
                m = j + 1
            else:
                m += 1
        # If the files are actually deleted/modified (`-delete`, or a writing `-exec`), emit the STARTING
        # POINTS (leading non-option operands, after find's global options) + `-name`/`-path` values as
        # targets (codex review of #53). A read-only exec (`-exec grep …`) modifies nothing -> no over-ask.
        if exec_writes or any(o == "-delete" for o in operands):
            gi = 0
            while gi < len(operands):
                o = operands[gi]
                if o in ("-H", "-L", "-P"):
                    gi += 1                          # no-arg global option
                elif o == "-D":
                    gi += 2                          # `-D debugoptions`
                elif o.startswith("-O"):
                    gi += 1                          # `-Olevel`
                elif o == "--":
                    gi += 1                          # end-of-options: keep collecting start paths (codex #53)
                elif o.startswith("-") or o in ("(", "!", ","):
                    break                            # the expression begins here
                else:
                    _emit_target(o, out); gi += 1    # a starting point
            for k in range(len(operands) - 1):
                if operands[k] in ("-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename"):
                    _emit_target(operands[k + 1], out)
    elif verb == "xargs":
        sub = _strip_prefixes(_strip_xargs_opts(operands))   # skip xargs's own options, THEN wrappers
        _scan_command(sub, out, all_words, heredoc_bodies, emitted_all)   # A7: scan the child's STATIC args
        if _command_writes_operands(sub):                                #     + inline `-c`/`-e` code
            # input words come from the pipe/stdin (not statically visible) — fail closed by treating every
            # literal word in the whole pipeline as a candidate. Emit all_words AT MOST ONCE per statement:
            # N xargs stages each copying O(N) words is O(N^2) and blew the 10s hook budget (A3, codex/audit
            # of #53); the final dedup makes one emission byte-identical to N.
            if emitted_all is None or not emitted_all:
                out.extend(all_words)
                if emitted_all is not None:
                    emitted_all.append(True)
    elif verb in _INLINE_ALWAYS:
        _emit_scan_words(operands, out)
        _emit_scan_words(heredoc_bodies, out)
    elif iverb in _INLINE_SHELLS or iverb in ("perl", "ruby", "nodejs", "node"):
        # inline code via a -c/-e flag OR a heredoc body (`python3 <<PY … PY`) feeding the interpreter
        if _has_inline_code(words, iverb) or heredoc_bodies:
            _emit_scan_words(operands, out)
            _emit_scan_words(heredoc_bodies, out)


def _scan_statement(stmt: list[dict], out: list[str]) -> None:
    # 1) redirect targets apply regardless of verb: the WORD after >, >>, >|, &>, &>> — and after `>&`
    #    UNLESS it is an fd reference (`>&2`/`>&-`), which is a dup/close not a file write.
    for k in range(len(stmt) - 1):
        t = stmt[k]
        if t["k"] != "O" or stmt[k + 1]["k"] != "W":
            continue
        nxt = stmt[k + 1]["dq"]
        if t["op"] in _REDIR_WRITE:
            _emit_target(nxt, out)
        elif t["op"] == ">&" and not _is_fd_ref(nxt):
            _emit_target(nxt, out)                   # `>& file` redirects BOTH streams to (truncates) file

    # 2) split the statement into pipeline-commands at `|`/`|&`. DROP the word after any redirect operator
    #    (it is a redirect target/source, not a command operand) so an INPUT redirect (`tee out < K.swift`)
    #    does not leak the read source into an operand list and over-ask. Keep all words for the xargs scan.
    all_words = [t["dq"] for t in stmt if t["k"] == "W"]
    heredoc_bodies = [t["body"] for t in stmt if t["k"] == "H"]
    cmds: list[list[str]] = [[]]
    after_redir = False; herestring_next = False
    for t in stmt:
        if t["k"] == "O" and t["op"] in ("|", "|&"):
            cmds.append([]); after_redir = False; herestring_next = False
        elif t["k"] == "O":
            after_redir = t["op"] in _REDIR_ANY
            herestring_next = t["op"] == "<<<"
        elif t["k"] == "W":
            if after_redir:
                if herestring_next:
                    # `bash <<< 'rm K.swift'` / `python3 <<< '…'` feed the here-string to the interpreter as
                    # CODE via stdin — scan it like a heredoc body, not as an inert read source (codex #53).
                    heredoc_bodies.append(t["dq"])
                after_redir = False; herestring_next = False
            else:
                cmds[-1].append(t["dq"])

    emitted_all: list = []          # per-statement: emit the xargs fail-closed all_words at most once (A3)
    for words in cmds:
        _scan_command(words, out, all_words, heredoc_bodies, emitted_all)


def _iter_command_subs(cmd: str):
    """Yield the inner text of each EXECUTED command substitution — `$(...)` (balanced) and `` `...` `` —
    skipping ones inside SINGLE quotes (literal, never executed). Double-quoted subs DO execute, so they
    are yielded. Lets write_targets recurse into a writer nested in a substitution (`echo "$(rm X)"`)."""
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        if c == "'":                                 # single-quoted: literal, no substitution
            j = cmd.find("'", i + 1)
            i = n if j == -1 else j + 1
            continue
        if c == "\\":
            i += 2
            continue
        if c == "`":
            j = i + 1
            while j < n and cmd[j] != "`":
                j += 2 if (cmd[j] == "\\" and j + 1 < n) else 1
            yield cmd[i + 1:j]
            i = j + 1
            continue
        if c == "$" and i + 1 < n and cmd[i + 1] == "(":
            # balance parens, but SKIP quoted/backticked spans and `\`-escapes so a quoted `)` inside the
            # sub (`$(printf ')'; rm K.swift)`) is not mistaken for the closer (codex review of #53).
            depth = 1; j = i + 2; s = j
            while j < n and depth:
                cj = cmd[j]
                if cj == "\\":
                    j += 2; continue
                if cj == "'":
                    k = cmd.find("'", j + 1); j = n if k == -1 else k + 1; continue
                if cj == '"':
                    j += 1
                    while j < n and cmd[j] != '"':
                        j += 2 if (cmd[j] == "\\" and j + 1 < n) else 1
                    j += 1; continue
                if cj == "`":
                    k = j + 1
                    while k < n and cmd[k] != "`":
                        k += 2 if (cmd[k] == "\\" and k + 1 < n) else 1
                    j = k + 1; continue
                if cj == "(":
                    depth += 1
                elif cj == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            yield cmd[s:j]
            i = j + 1
            continue
        i += 1


def write_targets(cmd: str, _depth: int = 0) -> list[str]:
    """The de-quoted write-target words of `cmd` (deduped, no empties, no embedded newlines). Recurses into
    executed command substitutions so a writer nested in `$()`/backticks is caught regardless of the outer
    verb (`echo "$(rm K.swift)"` deletes K.swift). Depth-bounded as a cheap runaway guard."""
    out: list[str] = []
    for stmt in _tokenize(cmd):
        _scan_statement(stmt, out)
    if _depth < 24:
        for inner in _iter_command_subs(cmd):
            out.extend(write_targets(inner, _depth + 1))
    seen: set[str] = set()
    return [t for t in out if t and "\n" not in t and not (t in seen or seen.add(t))]


def main() -> int:
    import os
    if os.environ.get("_BWS_FORCE_FAIL"):   # test seam: exercise the guard's exit-2 fail-closed deny path
        return 3
    try:
        cmd = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception:
        return 3
    try:
        # Newline-delimited (a bash var/`$()` cannot hold a NUL); a target word with an embedded newline is
        # pathological and is dropped by write_targets.
        sys.stdout.write("\n".join(write_targets(cmd)))
        return 0
    except Exception:
        return 3   # internal parse failure -> guard fails CLOSED (deny)


if __name__ == "__main__":
    sys.exit(main())
