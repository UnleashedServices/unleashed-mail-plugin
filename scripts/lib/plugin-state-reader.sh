# shellcheck shell=bash
# COREDEV-2617 §7 step 3c — the store scan and the ORDERED reader rules −1 through 4.
#
# Requires plugin-state-auth.sh and plugin-state-store.sh to be sourced first.
#
# THE ORDER IS NORMATIVE AND THE RULES ARE NUMBERED FROM −1, NOT 0. RD-2 prohibits a "rules 0-4"
# enumeration anywhere, because it silently drops the store-authentication rule — and a reader that
# skips rule −1 examines entries inside a store it never checked.
#
#   rule −1  the STORE itself fails ST-3 or its chain           -> stale
#   rule  0  a candidate that vanished between glob and open    -> SKIPPED, it is not an entry
#   rule  1  any surviving entry fails authentication           -> stale
#   rule  2  two or more surviving entries authenticate         -> conflict
#   rule  3  exactly one authenticates                          -> RESOLVE
#   rule  4  zero survive, or the store does not exist           -> none
#
# Every scratch variable carries its function's prefix (FAM-5).

# ── ENT-1..ENT-3, TGT-1 and the two chains — AUTH-1's ONE predicate ───────────────────────────────
# $1 = the entry path. 0 = authenticates. Publisher and reader call THIS, with no weaker variant at
# either call site: there is no clause an implementation may apply on one side and not the other.
_unleashed_auth_entry() {
    _ae_p="$1"

    # ENT-1 — the file clauses. The TYPE is established BEFORE anything is opened: a FIFO is not a
    # symlink, so a `[ -L ]`-only guard passes it and the read then BLOCKS FOREVER waiting for a
    # writer (measured, rc=124 at a 5s timeout in both shells). The resolver runs at SOURCE TIME in
    # every process that loads a family file, so one FIFO named `base.*` would hang every hook.
    [ -L "$_ae_p" ] && return 1                      # a symlink is a FAILING entry, never skipped
    [ -f "$_ae_p" ] || return 1                      # regular file only — directory, FIFO, socket out
    _u_stat "$_ae_p" || return 1
    [ "$_U_MODE" = 0600 ] || return 1                # TWELVE bits: `chmod 4600` must not pass as 0600
    { _u_euid && [ "$_U_UID" = "$_U_EUID" ]; } || return 1

    # ENT-2 — exactly one line, and exactly its bytes. All THREE clauses are required and each covers
    # a case the others miss: (1) `rc=0` catches a TERMINAL NUL and an empty file in BOTH shells,
    # (2) the byte count catches a mid-line or leading NUL in BASH (which truncates at the NUL, so
    # the file is longer than the line), (3) the zsh-only NUL test catches the same in ZSH (which
    # keeps the NUL, so the byte count matches).
    # THE READ IS BOUNDED BEFORE IT HAPPENS. ENT-2 requires size == len(line)+1 and ENT-3 requires
    # the NAME to be the encoded CONTENT — so a valid entry's byte size can never exceed the length
    # of its own key: every marker the encoder emits is at least as long as the byte it encodes,
    # so len(value) <= len(key). An entry larger than len(key)+1 cannot authenticate whatever it
    # holds, and is refused from `_U_SIZE` (already fetched by P-2) WITHOUT being opened. Without
    # this, a 0600 owner-created or corrupted `base.*` with a huge or sparse payload and no newline
    # makes `read` consume the whole file first — and this runs at SOURCE TIME in every hook and
    # SessionStart, so one such entry hangs all of them (codex, PR #67). The name is used as the
    # bound because it is the one fact about the file that cannot be forged without also failing
    # ENT-3.
    _ae_name="${_ae_p##*/}"; _ae_name="${_ae_name#base.}"
    [ "$_U_SIZE" -le "$(( ${#_ae_name} + 1 ))" ] || return 1
    # ENT-2b — THE READ IS BOUND TO THE OBJECT THAT WAS VALIDATED. Everything above stat'ed the
    # PATHNAME; a plain `read < "$p"` then opened the pathname a SECOND time, and same-uid interference
    # substituting the entry between the two — a FIFO, whose read-open BLOCKS every hook at source
    # time; a large regular file, which the pre-read size bound above never saw — was read instead of
    # what was checked (codex, PR #67 pass 7). So the entry is opened ONCE, and type, size and owner
    # are validated ON THE DESCRIPTOR before anything is read through it, with the read itself
    # bounded to the largest size a valid entry can have. The two arms differ only in what the shell
    # can do: zsh's `sysopen -o nonblock` never blocks on a FIFO and `zstat -f` reports the open
    # object exactly (mode included); bash 3.2 has no non-blocking open, so a FIFO substituted in
    # this window still blocks it — P-5's stated residual, mirrored here rather than claimed closed —
    # while `/dev/fd/N` (measured on Darwin) reports the open object's TYPE, SIZE and UID but its
    # MODE as the open flags, so mode stays validated on the pathname above and is not re-read.
    _ae_bound=$(( ${#_ae_name} + 1 ))
    _ae_ino="$_U_INO"                       # the inode ENT-1 validated; the opened object must BE it
    if [ -n "${ZSH_VERSION:-}" ]; then
        zmodload zsh/system 2>/dev/null || return 1
        # `sysopen` needs an explicit descriptor: allocate a free one, close it, reuse the number.
        # THE STDERR REDIRECT SITS ON A GROUP: `exec {fd}<file 2>/dev/null` with no command applies
        # EVERY redirection to the shell permanently — the first draft of this line silently sent the
        # sourcing shell's stderr to /dev/null for the rest of the process (measured: xtrace went dark).
        { exec {_ae_fd}</dev/null; } 2>/dev/null || return 1
        exec {_ae_fd}<&-
        sysopen -r -o nonblock -u "$_ae_fd" -- "$_ae_p" 2>/dev/null || return 1
        _ae_ok=0; _ae_raw=""
        # TYPE, UID and SIZE of the open object — the same three the bash arm validates through
        # /dev/fd, and NOT the mode: ENT-1 owns the mode clause and validated it on the pathname, and
        # a second copy here would MASK ENT-1's clause from its own mutant (rows 8 and 114 stopped
        # discriminating under zsh when the first draft re-checked 0600 on the descriptor).
        # shellcheck disable=SC2154  # _u_h is populated by `zstat -H`, a zsh builtin shellcheck cannot model
        # THE OPENED OBJECT IS THE VALIDATED OBJECT: same inode as ENT-1 stat'ed. That binds every
        # clause ENT-1 validated on the pathname — mode included — to the descriptor without a second
        # copy of any of them (a second mode check here masked ENT-1's own mutants, rows 8/114); a
        # same-uid replacement of any kind, mode or content, is a different inode and is refused
        # (codex, PR #67 pass 11).
        if _u_euid && zstat -f "$_ae_fd" -H _u_h 2>/dev/null \
            && [ "${_u_h[inode]}" = "$_ae_ino" ] \
            && [ "$(( ${_u_h[mode]} & 8#170000 ))" = "$(( 8#100000 ))" ] \
            && [ "${_u_h[uid]}" = "$_U_EUID" ] \
            && [ "${_u_h[size]}" -le "$_ae_bound" ]; then
            _U_SIZE=${_u_h[size]}
            # One bounded read; sysread returns 5 on an empty object.
            if sysread -s "$_ae_bound" -i "$_ae_fd" _ae_raw 2>/dev/null; then _ae_ok=1; fi
        fi
        exec {_ae_fd}<&-
        [ "$_ae_ok" = 1 ] || return 1
        # THE LINE IS THE CONTENT UP TO THE FIRST NEWLINE, exactly what `IFS= read -r` delivers — so
        # clause (2) below, and only clause (2), refuses a second line (row 4's mutant must be able
        # to fail here as it does in bash); (1) is that a newline exists at all.
        case "$_ae_raw" in *$'\n'*) _ae_line="${_ae_raw%%$'\n'*}" ;; *) return 1 ;; esac    # (1)
        _u_entry_path_still_bare "$_ae_p" || return 1
    else
        _ae_ok=0
        # `2>/dev/null` on the OUTER group: a refused open reports on the shell's stderr BEFORE the
        # inner group's own redirections apply, and that message names the path — a lossless encoding
        # of the target (measured, both shells).
        { { _u_euid && [ -f /dev/fd/9 ] && _u_stat /dev/fd/9 \
              && [ "$_U_INO" = "$_ae_ino" ] \
              && [ "$_U_UID" = "$_U_EUID" ] \
              && [ "$_U_SIZE" -le "$_ae_bound" ] \
              && IFS= read -r -n "$_ae_bound" -u 9 _ae_line && _ae_ok=1; } 9<"$_ae_p"; } 2>/dev/null
        [ "$_ae_ok" = 1 ] || return 1                                                      # (1)
        _u_entry_path_still_bare "$_ae_p" || return 1
    fi
    # (2) is a BYTE comparison, and `${#var}` counts CHARACTERS under a UTF-8 locale — so a base
    # such as `/café` reads as 14 characters against a 15-byte line, the equality fails, and every
    # non-ASCII base marks its own store `stale` (codex, PR #67; reproduced in both shells under
    # C.UTF-8). The length is therefore taken under LC_ALL=C, with the caller's locale saved and
    # restored exactly as ENC-3 requires of the encoder — an EMPTY LC_ALL is not an absent one.
    if [ -n "${LC_ALL+set}" ]; then _ae_lc_set=1; _ae_lc_val="$LC_ALL"; else _ae_lc_set=0; fi
    # A CALLER MAY HAVE MADE `LC_ALL` READONLY, and then this assignment is FATAL, not scoped: measured,
    # `readonly LC_ALL=C.UTF-8` followed by sourcing killed the shell outright in both shells — before
    # the protocol variables were established, so a hook died instead of resolving (codex, PR #67 pass
    # 23 — reproduced). The assignment is attempted in a form whose failure is survivable, and its
    # SUCCESS is then checked: if the locale could not be set to C, the byte-oriented walk below would
    # be wrong, so the caller's own value is left alone and _ae_lc_ro records it for the one place
    # that must then take a different route.
    # THE ASSIGNMENT IS NOT ATTEMPTED WHEN THE CALLER MADE `LC_ALL` READONLY. Measured: bash aborts the
    # shell on an assignment to a readonly variable and NO shell-level guard survives it — not `if !`,
    # not `{ …; } || true`; only a subshell survives, and a subshell cannot set the locale for the walk
    # that follows. So the attribute is read FIRST, with the same `declare -p`/`typeset -p` parse the
    # instance stamp uses (measured to detect it in both shells, and not to misfire on a writable one).
    # If it is readonly and already C or POSIX the walk is byte-oriented anyway and proceeds; if it is
    # readonly and something else, the byte semantics ENC-1 requires cannot be established, so this
    # REFUSES rather than encoding under a locale that would make the walk character-oriented — the
    # `/café` defect ENC-3 exists to prevent. Nothing is fatal either way (codex, PR #67 pass 23 —
    # reproduced: `readonly LC_ALL=C.UTF-8` killed the sourcing shell in BOTH shells).
    # THE PROBE MUST NOT FORK. ENC-2 requires the key derivation to fork ZERO times so it still works
    # under fork exhaustion (`ulimit -u 1`), and row 045 pins that — my first version of this guard read
    # the attribute with `$( declare -p … )`, which IS a fork, and row 045 caught it. Both probes below
    # are builtins: zsh reports the attribute in `${(t)var}` (measured: `scalar-readonly-special`), and
    # bash has no such introspection in 3.2, so it uses `unset -v`, which on a readonly FAILS
    # NON-FATALLY there (measured) while an assignment would kill the shell. The zsh form is inside a
    # single-quoted `eval` because bash cannot PARSE `${(t)…}` — verified that a file containing it
    # parses in both shells.
    _ae_lc_ro=0
    if [ -n "${ZSH_VERSION:-}" ]; then
        eval 'case "${(t)LC_ALL}" in *readonly*) _ae_lc_ro=1 ;; esac'
    elif [ "$_ae_lc_set" = 1 ]; then
        unset -v LC_ALL 2>/dev/null || _ae_lc_ro=1
    fi
    case "$_ae_lc_ro" in
        1)
            case "${_ae_lc_val:-}" in
                # 2 = LEAVE IT ENTIRELY ALONE. Not 0: 0 means "was unset, so unset it again" and
                # `unset` of a readonly is fatal in zsh (measured — it killed the shell on the
                # RESTORE after this branch had correctly survived the assignment).
                # ONLY `C` AND `POSIX`. `C.UTF-8` is a UTF-8 locale, so the walk is CHARACTER-wise
                # there, not byte-wise: measured, a readonly `C.UTF-8` encoded `/café` as
                # `_scaf_xc3` in bash and `_scaf_xe9` in zsh against the correct `_scaf_xc3_xa9`
                # — a different key per shell for one directory, which is ENC-1 injectivity gone.
                # I had listed it as acceptable in the first version of this guard; the keys said
                # otherwise, which is why this checks the OUTPUT and not merely that nothing died.
                C|POSIX) _ae_lc_set=2 ;;
                *) return 1 ;;
            esac ;;
        *) LC_ALL=C ;;
    esac
    _ae_bytes=${#_ae_line}
    # RESTORED AS AN EXPORT. bash's only fork-free readonly probe is `unset -v`, and a successful
    # unset destroys the EXPORT attribute: measured, an exported `LC_ALL` came back as a plain
    # shell variable, so every child these libraries fork — `/usr/bin/stat`, `/bin/ls -le`,
    # `/usr/bin/getconf` — ran under the caller's `LANG` instead of their `LC_ALL`. ENC-3 says the
    # entry state is restored EXACTLY, and the export attribute is part of that state.
    # STATED DEVIATION, measured and deliberate: a caller whose `LC_ALL` was SET BUT NOT EXPORTED
    # gets it exported on return, because bash 3.2 offers no fork-free way to tell the two apart
    # (`export` and `typeset -x` both succeed on a readonly, so neither can even probe; `compgen
    # -e` needs a command substitution, which ENC-2 forbids). An unexported `LC_ALL` is
    # pathological — it is an environment variable by convention — and exporting it makes the
    # children agree with the shell that spawned them, where dropping the export makes them
    # disagree silently. zsh keeps the attribute through `${(t)…}` and never unsets.
    case "$_ae_lc_set" in 1) LC_ALL="$_ae_lc_val"; export LC_ALL ;; 0) unset LC_ALL ;; esac
    [ "$_U_SIZE" = "$(( _ae_bytes + 1 ))" ] || return 1                        # (2)
    if [ -n "${ZSH_VERSION:-}" ]; then
        case "$_ae_line" in *$'\0'*) return 1 ;; esac                          # (3)
    fi

    # TGT-1 — the content clauses on that single line.
    case "$_ae_line" in
        /*) : ;;                                     # absolute
        *)  return 1 ;;
    esac
    case "$_ae_line" in
        */) return 1 ;;                              # no trailing slash
    esac
    [ -d "$_ae_line" ] || return 1                   # names an EXISTING directory
    [ -L "$_ae_line" ] && return 1                   # which is not itself a symlink

    # ENT-3 — the NAME is the encoded CONTENT. Because key() is injective over values, two entries
    # with different names necessarily hold different values, so COUNTING ENTRIES counts distinct
    # base values and no target string is ever accumulated or compared (ENC-5).
    _unleashed_key "$_ae_line"
    [ "$_ae_p" = "${_ae_p%/*}/base.$_UNLEASHED_KEY" ] || return 1

    # PCH-1 — the entry's OWN chain and the TARGET chain, one walk each, no clause on one that the
    # other lacks. ANCHOR-1's ownership and the ACL clauses ride along inside the walk.
    _unleashed_auth_chain "${_ae_p%/*}" || return 1
    _unleashed_auth_chain "$_ae_line" || return 1
    return 0
}

# ── RD-9 — enumerate exactly `<store>/base.*` ─────────────────────────────────────────────────────
# `.pub.<pid>.<uniq>.<key>` transients lie outside this glob BY CONSTRUCTION, so a crash-orphaned
# temporary is never enumerated and changes no resolution.
#
# The zsh guard is load-bearing: an unmatched glob is an ERROR there by default, and this runs at
# SOURCE TIME, so an empty store would abort the sourcing shell. `local_options` scopes the setopt to
# this function so a consumer's own options are untouched.
#
# Rule 0's skip test is EXACTLY `[ ! -L ] && [ ! -e ]`, both parts required. A one-part `[ -e ]` is
# prohibited anywhere in the reader: `[ -e ]` is FALSE for a dangling symlink, so the one-part form
# would skip a hostile entry that must be refused.
_unleashed_scan_store() {
    _ss_store="$1"
    _UNLEASHED_SURVIVORS=0                           # entries that did not vanish
    _UNLEASHED_AUTHED=0                              # of those, how many authenticate
    _UNLEASHED_FAILED=0                              # of those, how many do not
    _UNLEASHED_WINNER=""
    # GLOBBING IS FORCED ON FOR THIS SCAN, AND THE CALLER'S SETTING RESTORED. The store is enumerated
    # by a pattern, so a caller who disabled globbing — `set -f`, zsh `setopt noglob`, the defensive
    # `set -euf` idiom in a wrapper, or an inherited `SHELLOPTS=noglob` (bash imports it at startup) —
    # left the pattern unexpanded: the literal `<store>/base.*` reached the loop, failed rule 0 as
    # "vanished", and a HEALTHY store reported ZERO entries — `OK=0 SOURCE=unresolved` with no repair
    # notice, in both shells (codex, PR #67 pass 17 — reproduced). zsh's `local_options` restores the
    # shell's options at function return; bash has no such scope, so the flag is saved and restored
    # explicitly, including on every `return` below.
    if [ -n "${ZSH_VERSION:-}" ]; then
        setopt local_options no_nomatch glob        # `no_noglob` is NOT a zsh option name — measured:
                                                    # `setopt: no such option: no_noglob`, so the option
                                                    # never changed and the zsh arm stayed broken.
        _ss_noglob=0
    else
        case $- in *f*) _ss_noglob=1; set +f ;; *) _ss_noglob=0 ;; esac
        # `failglob` IS A SEPARATE OPTION AND IT IS FATAL HERE. With an authenticated but EMPTY store,
        # bash's `failglob` aborts on the unmatched `base.*` before the loop can apply its own
        # vanished-entry rule — so sourcing the resolver in a strict shell killed the hook instead of
        # returning the documented empty-store resolution (codex, PR #67 pass 23 — reproduced). Turning
        # off `noglob` alone was not enough; both are saved and restored.
        _ss_failglob=0
        if shopt -q failglob 2>/dev/null; then _ss_failglob=1; shopt -u failglob 2>/dev/null || :; fi
    fi
    for _ss_f in "$_ss_store"/base.*; do
        # bash expands an unmatched glob to the PATTERN ITSELF, so a literal `base.*` reaches here
        # when the store is empty; it satisfies neither test below and is skipped as vanished.
        if [ ! -L "$_ss_f" ] && [ ! -e "$_ss_f" ]; then
            continue                                 # rule 0: vanished, therefore NOT an entry
        fi
        _UNLEASHED_SURVIVORS=$(( _UNLEASHED_SURVIVORS + 1 ))
        if _unleashed_auth_entry "$_ss_f"; then
            _UNLEASHED_AUTHED=$(( _UNLEASHED_AUTHED + 1 ))
            _UNLEASHED_WINNER="$_ae_line"            # the resolved value, not the path
        else
            _UNLEASHED_FAILED=$(( _UNLEASHED_FAILED + 1 ))
        fi
    done
    [ "${_ss_failglob:-0}" = 1 ] && shopt -s failglob 2>/dev/null || :
    [ "${_ss_noglob:-0}" = 1 ] && set -f          # restore the caller's `noglob`; zsh did it at return
    return 0
}

# ── ST-3 — rule −1, the store itself ──────────────────────────────────────────────────────────────
# Evaluated BEFORE any entry is touched, and evaluated even when the store is empty. A store in any
# non-conforming state is REFUSED: never chmod'ed, never repaired, never deleted.
# A store that does not exist AT ALL is NOT a refusal — that is rule 4.
_unleashed_store_ok() {
    _so_s="$1"
    [ -L "$_so_s" ] && return 1                      # tested without following
    [ -d "$_so_s" ] || return 1
    _u_stat "$_so_s" || return 1
    [ "$_U_MODE" = 0700 ] || return 1                # EXACTLY 0700, twelve bits
    { _u_euid && [ "$_U_UID" = "$_U_EUID" ]; } || return 1
    _unleashed_auth_chain "$_so_s" || return 1       # `/` down to and including bases/
    return 0
}

# AN EQUAL INODE IS NOT A BARE PATHNAME. ENT-2b binds the descriptor to the inode ENT-1 validated, which
# proves the bytes read came from that object — it does NOT prove `base.<key>` is still the non-symlink
# regular file ENT-1 requires. Measured (DEBUG-trap fixture, PR #67 pass 15, codex): a same-uid process
# renames the validated entry aside and drops a symlink to it at the entry name between ENT-1 and the
# open; the descriptor still has exactly that inode, so type, owner, size and content all pass and the
# read was ACCEPTED while the surviving store entry is a link ENT-1 forbids — and every later consumer
# opening that name leaves the store. So the pathname is re-tested after the read: a link, or a name
# that no longer denotes the validated inode, fails the read (rule ENT-2c).
# It SAVES AND RESTORES the four `_u_stat` outputs: clause (2) below compares `_U_SIZE` — in the zsh arm
# the size of the AUTHENTICATED DESCRIPTOR — against the line it read, and a helper that re-stats the
# pathname would silently substitute the pathname's current size for it, weakening the very clause it
# runs beside. (Caught while writing this one, not by a reviewer.)
_u_entry_path_still_bare() {
    [ -L "$1" ] && return 1
    _ue_m="${_U_MODE:-}"; _ue_s="${_U_SIZE:-}"; _ue_u="${_U_UID:-}"; _ue_i="${_U_INO:-}"
    if _u_stat "$1" && [ "$_U_INO" = "$_ae_ino" ]; then _ue_rc=0; else _ue_rc=1; fi
    _U_MODE="$_ue_m"; _U_SIZE="$_ue_s"; _U_UID="$_ue_u"; _U_INO="$_ue_i"
    return "$_ue_rc"
}


# ── RD-8: "does not exist AT ALL" ────────────────────────────────────────────────────────────────
# True iff the store is genuinely absent: walking its path from `/` down, every prefix that exists is a
# searchable directory and the first missing component is simply missing. `[ ! -e store ]` alone is
# NOT that test — it is also false when an ANCESTOR exists but cannot be searched (`~/.claude` at
# 0600), and that store is not absent, it is HIDDEN: rule −1's chain walk is what must judge it, and it
# refuses (`stale`, so the SessionStart repair notice fires) where rule 4 would have said `none` and
# stayed silent (codex, PR #67 pass 8 — reproduced). A prefix that exists as a symlink, a non-directory,
# or an unsearchable directory therefore returns 1 here and falls through to rule −1.
_unleashed_store_absent() {
    _sa_rest="${1#/}"; _sa_p=""
    while [ -n "$_sa_rest" ]; do
        case "$_sa_rest" in
            */*) _sa_c="${_sa_rest%%/*}"; _sa_rest="${_sa_rest#*/}" ;;
            *)   _sa_c="$_sa_rest"; _sa_rest="" ;;
        esac
        [ -n "$_sa_c" ] || continue
        _sa_p="$_sa_p/$_sa_c"
        [ -L "$_sa_p" ] && return 1                            # exists as a symlink → not absent
        [ -e "$_sa_p" ] || return 0                            # this component is missing → absent
        { [ -d "$_sa_p" ] && [ -x "$_sa_p" ]; } || return 1    # exists, but not a searchable directory
    done
    return 1                                                   # the store exists
}

# ── The ordered reader ────────────────────────────────────────────────────────────────────────────
# Sets the four protocol variables and emits AT MOST ONE diagnostic. Rule 3 emits NONE — a resolution
# is the ordinary case and must be silent.
_unleashed_read_store() {
    _rs_store="$1"
    _u_probes_reset                                  # no inherited probe state is honoured

    if _unleashed_store_absent "$_rs_store"; then
        _unleashed_unresolved none "the plugin-state store does not exist"     # rule 4
        return 0
    fi
    if ! _unleashed_store_ok "$_rs_store"; then
        _unleashed_unresolved stale "the plugin-state store is not usable"     # rule −1
        return 0
    fi

    _unleashed_scan_store "$_rs_store"

    if [ "$_UNLEASHED_FAILED" -gt 0 ]; then                                    # rule 1
        # Fires HOWEVER MANY entries authenticate: one bad entry refuses the whole store, so a good
        # entry sitting beside a failing one must NOT win.
        _unleashed_unresolved stale "a plugin-state entry failed authentication"
    elif [ "$_UNLEASHED_AUTHED" -ge 2 ]; then                                  # rule 2
        # The diagnostic names NEITHER the target paths NOR the entry names: an entry name is a
        # lossless encoding of a path, so printing one leaks the path it encodes (ENC-10, RD-6).
        _unleashed_unresolved conflict "two or more plugin-state entries disagree"
    elif [ "$_UNLEASHED_AUTHED" = 1 ]; then                                    # rule 3
        _UNLEASHED_BASE_RESOLVED="$_UNLEASHED_WINNER"
        _UNLEASHED_BASE_OK=1
        _UNLEASHED_BASE_SOURCE=pointer
        _UNLEASHED_POINTER_STATE=none
    else                                                                       # rule 4
        _unleashed_unresolved none "no plugin-state entry is present"
    fi
    return 0
}

# The unresolved exit, in one place so the four variables can never be set inconsistently.
# FAM-6: exactly ONE diagnostic per process, guarded by the shared flag rather than by this function,
# so the count holds whether or not paths.sh was found.
_unleashed_unresolved() {
    _UNLEASHED_BASE_RESOLVED="${_UNLEASHED_BASE_SENTINEL:-/dev/null/unresolved-plugin-base}"
    _UNLEASHED_BASE_OK=0
    _UNLEASHED_BASE_SOURCE=unresolved
    _UNLEASHED_POINTER_STATE="$1"
    if [ -z "${_UNLEASHED_BASE_DIAGNOSED:-}" ]; then
        _UNLEASHED_BASE_DIAGNOSED=1
        # THE PREFIX IS SUPPLIED BY THE CALLER and this file never names the environment variable.
        # That is a separation of concerns, not a workaround: the reader knows about the STORE,
        # and which variable was unset is `paths.sh`'s business. It also keeps N5's lexical drift
        # check tight — a new primitive that spells the identifier would have to be allowlisted,
        # and N5 exists precisely to stop a new primitive re-deriving the base.
        printf 'unleashed-mail: %s%s; plugin state will not be read or written this run\n' \
            "${_UNLEASHED_UNRESOLVED_PREFIX:-}" "$2" >&2
    fi
    return 0
}
