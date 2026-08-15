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
    [ "$_U_UID" = "${EUID:-$(/usr/bin/id -u)}" ] || return 1

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
    IFS= read -r _ae_line < "$_ae_p" || return 1     # (1)
    # (2) is a BYTE comparison, and `${#var}` counts CHARACTERS under a UTF-8 locale — so a base
    # such as `/café` reads as 14 characters against a 15-byte line, the equality fails, and every
    # non-ASCII base marks its own store `stale` (codex, PR #67; reproduced in both shells under
    # C.UTF-8). The length is therefore taken under LC_ALL=C, with the caller's locale saved and
    # restored exactly as ENC-3 requires of the encoder — an EMPTY LC_ALL is not an absent one.
    if [ -n "${LC_ALL+set}" ]; then _ae_lc_set=1; _ae_lc_val="$LC_ALL"; else _ae_lc_set=0; fi
    LC_ALL=C
    _ae_bytes=${#_ae_line}
    if [ "$_ae_lc_set" = 1 ]; then LC_ALL="$_ae_lc_val"; else unset LC_ALL; fi
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
    if [ -n "${ZSH_VERSION:-}" ]; then
        setopt local_options no_nomatch
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
    [ "$_U_UID" = "${EUID:-$(/usr/bin/id -u)}" ] || return 1
    _unleashed_auth_chain "$_so_s" || return 1       # `/` down to and including bases/
    return 0
}

# ── The ordered reader ────────────────────────────────────────────────────────────────────────────
# Sets the four protocol variables and emits AT MOST ONE diagnostic. Rule 3 emits NONE — a resolution
# is the ordinary case and must be silent.
_unleashed_read_store() {
    _rs_store="$1"
    _u_probes_reset                                  # no inherited probe state is honoured

    if [ ! -e "$_rs_store" ] && [ ! -L "$_rs_store" ]; then
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
