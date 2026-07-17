#!/usr/bin/env python3
"""COREDEV-2503 F4 — quote/escape/operator-aware scanner that lists the WRITE-TARGET file words of a bash
command. Replaces sensitive-file-guard.sh's O(n^2) `_split_segments` per-char loop AND its quote-blind
`grep` extractions (redirects, rm/interpreter basenames, cp/mv operands), which BOTH over-asked on a
*quoted* operator (`echo '> Keychain.swift'`) and bypassed on a mid-word quote (`rm Key"chain".swift`).

Contract: read the command on stdin; print each candidate write-target word NUL-delimited on stdout, fully
DE-QUOTED (so `Key"chain".swift` -> `Keychain.swift`). The caller (the guard) filters by its own
sensitive-basename policy and emits the ask. Exit 0 on success; exit 3 on an internal parse failure so the
guard can fail CLOSED (deny) rather than exit-0-without-decision. Whole-pipeline O(n): one linear lexer pass,
no quadratic accumulation.

Best-effort by design: a determined adversary can hide a target from ANY textual heuristic (base64,
indirection). This closes the quote-blindness + O(n^2)-timeout fail-opens and catches accidental writes.
"""
from __future__ import annotations

import re
import sys

# File extensions the interpreter-inline-code / eval scan treats as candidate file words (coupled to the
# guard's sensitive set by TYPE, not by the full basename policy which stays in bash).
_CODE_SCAN_EXTS = ("swift", "entitlements", "plist", "pbxproj", "mobileprovision", "xcodeproj")
# Extract WHOLE path-like tokens ending in a candidate extension from inline code (`open("X.swift")`), so
# the basename is `OAuthService.swift.bak` not the `.swift` prefix substring (matches the old grep).
_CODE_FILE_RE = re.compile(r"[A-Za-z0-9._/-]+\.(?:%s)[A-Za-z0-9._-]*" % "|".join(_CODE_SCAN_EXTS))

# Operators, longest first so `>>`/`>|`/`&&`/`||`/`|&`/`<<-` win over their shorter prefixes.
_OPS = (">>", ">|", "&>>", "&>", "<<<", "<<-", "<<", "<&", ">&", "&&", "||", "|&", ";;", "|", "&", ";", "(", ")", "<", ">")


def _parse_heredoc_delim(cmd: str, pos: int) -> tuple[str, int]:
    """After a `<<`/`<<-`, parse the delimiter (bare / quoted / backslashed) and return (delim, index_after
    the delimiter — still on the SAME line). The body is consumed later, at the next newline, so redirects
    or args that follow `<<DELIM` on the same line (`cat <<EOF > file`) are still parsed (codex review #53)."""
    n = len(cmd)
    j = pos
    while j < n and cmd[j] in " \t":
        j += 1
    if j < n and cmd[j] in "'\"":
        q = cmd[j]; j += 1; s = j
        while j < n and cmd[j] != q:
            j += 1
        return cmd[s:j], (j + 1 if j < n else j)
    if j < n and cmd[j] == "\\":
        j += 1
    s = j
    while j < n and (cmd[j].isalnum() or cmd[j] in "_-."):
        j += 1
    return cmd[s:j], j


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
        if cand == delim:
            return "\n".join(body_lines), (le + 1 if le < n else n)
        body_lines.append(line)
        if le == n:
            break
        k = le + 1
    return "\n".join(body_lines), n

_REDIR_WRITE = (">", ">>", ">|", "&>", "&>>")   # active redirect operators whose following WORD is written
_STMT_SEP = (";", "&&", "||", "&", ";;", "\n")   # statement boundaries (NOT `|` — a pipeline stays together)

# verb -> write-target rule
_DELETE_ALL = {"rm", "unlink", "shred", "rmdir"}          # every non-flag operand
_MOVE_ALL = {"mv", "rename"}                              # every non-flag operand (source removed + dest)
_DEST_LAST = {"cp", "install", "ln"}                     # dest = -t DIR, else last non-flag operand
_TEE = {"tee"}                                           # every non-flag operand
_INLINE_SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "python", "python2", "python3", "osascript"}
_INLINE_ALWAYS = {"eval", "source", "."}                # run an arbitrary string/file -> scan it
_PREFIXES = {"env", "command", "sudo", "nice", "ionice", "time", "builtin", "exec", "stdbuf", "setsid"}


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
        # --- whitespace (unquoted) ends a word ---
        if c in " \t":
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
            if i + 1 < n:
                w_dq.append(cmd[i + 1]); w_raw.append(c + cmd[i + 1]); in_word = True
                i += 2
            else:
                w_raw.append(c); w_dq.append(c); in_word = True
                i += 1
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
                if cmd[j] == "\\" and j + 1 < n and cmd[j + 1] in '"$`\\':
                    buf_dq.append(cmd[j + 1]); buf_raw.append(cmd[j:j + 2]); j += 2
                else:
                    buf_dq.append(cmd[j]); buf_raw.append(cmd[j]); j += 1
            buf_raw.append('"' if j < n else "")
            w_dq.append("".join(buf_dq)); w_raw.append("".join(buf_raw)); in_word = True
            i = j + 1
            continue
        # --- operators (unquoted) ---
        matched = None
        for op in _OPS:
            if cmd.startswith(op, i):
                matched = op
                break
        if matched is not None:
            if matched in ("(", ")") and in_word:
                # a `(`/`)` ATTACHED to a word is part of a code token (`unlink(X.swift)`), NOT a subshell
                # group — only a STANDALONE `( … )` (at a command boundary) is grouping to strip.
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
        if "=" in w and not w.startswith("-") and w.split("=", 1)[0].isidentifier() and base == w:
            idx += 1; continue                       # VAR=val assignment
        if base in _PREFIXES:
            probe = False
            split_string = False
            idx += 1
            # consume this prefix's option-args that take a following token
            while idx < len(words) and words[idx].startswith("-"):
                opt = words[idx]
                idx += 1
                if base == "command" and opt in ("-v", "-V"):
                    probe = True                      # `command -v rm X` LOOKS UP rm; it does not run it
                elif base == "env" and (opt in ("-S", "--split-string")):
                    split_string = True               # the REMAINING tokens are the command string
                    break
                elif base == "env" and opt in ("-u", "-C", "-P", "--unset", "--chdir", "--path"):
                    if idx < len(words):
                        idx += 1                      # these env options consume a following arg
                elif base == "nice" and opt in ("-n", "--adjustment"):
                    if idx < len(words):
                        idx += 1
            if probe:
                return []                             # a probe executes nothing -> no write target
            if split_string:
                rest = words[idx:]
                if rest and " " in rest[0]:           # `env -S 'rm X'` -> the quoted split-string is the cmd
                    rest = rest[0].split() + rest[1:]
                return _strip_prefixes(rest)          # the split command may carry its own VAR=val/env prefix
            continue
        break
    return words[idx:]


def _has_inline_code(words: list[str], verb: str) -> bool:
    """True if an interpreter statement carries INLINE CODE (so a file NAMED INSIDE it is a write target).
    Shells + python use `-c`; perl/ruby use `-e`/`-E`; node uses `-e`/`-p`/`--eval`/`--print`. A shell `-e`
    is errexit, NOT code. Handles clustered short flags (`-xc`, `-we`) and code adjacent to the flag
    (`-c"..."`)."""
    if verb in ("perl", "ruby"):
        code_flags = ("e", "E")
    elif verb in ("node", "nodejs"):
        code_flags = ("e", "p")
    else:                                            # shells + python + osascript
        code_flags = ("c",)
    for w in words[1:]:
        if not w.startswith("-") or w.startswith("--"):
            if w in ("--eval", "--print") and verb in ("node", "nodejs"):
                return True
            continue
        cluster = w[1:]
        # code adjacent (`-c"..."`, `-ceval`): the flag letter, then more chars
        for cf in code_flags:
            pos = cluster.find(cf)
            if pos != -1:
                return True
    return False


def _emit_scan_words(words: list[str], out: list[str]) -> None:
    """Extract file-extension-shaped path tokens from inline-code / eval operands (a sensitive name is a
    SUBSTRING of the de-quoted code, e.g. `open("OAuthService.swift","w")`)."""
    for w in words:
        out.extend(_CODE_FILE_RE.findall(w))


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


def _scan_statement(stmt: list[dict], out: list[str]) -> None:
    # 1) active-redirect targets apply regardless of verb (the WORD after >, >>, >|, &>, &>>)
    for k in range(len(stmt) - 1):
        t = stmt[k]
        if t["k"] == "O" and t["op"] in _REDIR_WRITE and stmt[k + 1]["k"] == "W":
            out.append(stmt[k + 1]["dq"])

    # 2) split the statement into pipeline-commands at `|`/`|&`, keep all words for the xargs scan
    all_words = [t["dq"] for t in stmt if t["k"] == "W"]
    heredoc_bodies = [t["body"] for t in stmt if t["k"] == "H"]
    cmds: list[list[str]] = [[]]
    for t in stmt:
        if t["k"] == "O" and t["op"] in ("|", "|&"):
            cmds.append([])
        elif t["k"] == "W":
            cmds[-1].append(t["dq"])

    for words in cmds:
        words = _strip_prefixes(words)
        if not words:
            continue
        verb = _basecmd(words[0])
        operands = words[1:]

        if verb in _DELETE_ALL or verb in _MOVE_ALL or verb in _TEE:
            out.extend(o for o in operands if not o.startswith("-"))
        elif verb in _DEST_LAST:
            tdir = ""; last = ""; skip = False
            for o in operands:
                if skip:
                    tdir = o; skip = False; continue
                if o in ("-t", "--target-directory"):
                    skip = True
                elif o.startswith("--target-directory="):
                    tdir = o.split("=", 1)[1]
                elif o.startswith("-"):
                    pass
                else:
                    last = o
            out.append(tdir or last)
        elif verb == "touch":
            skip = False
            for o in operands:
                if skip:
                    skip = False; continue
                if o in ("-r", "--reference", "-d", "--date", "-t"):
                    skip = True
                elif o.startswith("--reference=") or o.startswith("--date="):
                    pass
                elif o.startswith("-"):
                    pass
                else:
                    out.append(o)
        elif verb == "sed":
            inplace = any(
                o == "--in-place" or o.startswith("--in-place=")
                or (o.startswith("-") and not o.startswith("--") and "i" in o[1:])
                for o in operands
            )
            if inplace:
                out.extend(o for o in operands if not o.startswith("-"))
        elif verb == "dd":
            for o in operands:
                if o.startswith("of="):
                    out.append(o[3:])
        elif verb == "find":
            destructive = any(o in ("-delete", "-exec", "-execdir", "-ok", "-okdir") for o in operands)
            if destructive:
                for m in range(len(operands) - 1):
                    if operands[m] in ("-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename"):
                        out.append(operands[m + 1])
        elif verb in ("xargs",):
            sub = _strip_prefixes(_strip_xargs_opts(operands))   # skip xargs's own options, THEN wrappers
            subverb = _basecmd(sub[0]) if sub else ""
            if subverb in _DELETE_ALL or subverb in _MOVE_ALL or subverb in _TEE or subverb in _DEST_LAST:
                # input words come from the pipe/stdin (not statically visible) — fail closed by treating
                # every literal word in the whole pipeline as a candidate.
                out.extend(all_words)
        elif verb in _INLINE_ALWAYS:
            _emit_scan_words(operands, out)
            _emit_scan_words(heredoc_bodies, out)
        elif verb in _INLINE_SHELLS or verb in ("perl", "nodejs", "node"):
            # inline code via a -c/-e flag OR a heredoc body (`python3 <<PY … PY`) feeding the interpreter
            if _has_inline_code(words, verb) or heredoc_bodies:
                _emit_scan_words(operands, out)
                _emit_scan_words(heredoc_bodies, out)


def write_targets(cmd: str) -> list[str]:
    """The de-quoted write-target words of `cmd` (deduped, no empties, no embedded newlines)."""
    out: list[str] = []
    for stmt in _tokenize(cmd):
        _scan_statement(stmt, out)
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
