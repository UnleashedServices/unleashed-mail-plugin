# shellcheck shell=bash
# COREDEV-2617 §7 step 3b — the shared chain authenticator and the Darwin ACL arm.
#
# DARWIN ARMS ONLY (see plugin-state-store.sh). On any other platform the ACL condition is
# UNEVALUABLE and the component REFUSES, which is ACL-4.
#
# AUTH-1: "authenticates" denotes ONE predicate over a single entry, implemented by ONE function that
# both the publisher and the reader call. A second predicate, or a weaker variant at any call site, is
# forbidden — there is no clause an implementation may apply on one side and not the other.
#
# Every scratch variable carries its function's prefix (FAM-5); see plugin-state-store.sh for why.

# ── P-2 — mode, size AND owning uid, in ONE lstat call per component ──────────────────────────────
# -> _U_MODE (four octal digits, TWELVE bits), _U_SIZE, _U_UID. Non-zero if the path does not exist.
#
# TWELVE bits, not nine: `chmod 4600` reports `600` from a nine-bit mask, so a setuid entry would
# satisfy "mode exactly 0600" and a sticky directory "exactly 0700".
# `-L` ON THE ZSH ARM IS LOAD-BEARING: without it the two arms measure DIFFERENT FILES. On a symlink
# to a 0700 directory the bash arm returns the LINK's own mode and its target-string length while
# `zstat` without -L returns the TARGET's; on a dangling symlink the bash arm succeeds and `zstat`
# without -L fails outright. `/usr/bin/stat` is lstat by default; `zstat` follows by default.
_u_stat() {
    if [ -n "${ZSH_VERSION:-}" ]; then
        zmodload zsh/stat 2>/dev/null
        # `zstat -H _u_h` populates the associative array `_u_h`; shellcheck models bash and cannot
        # see that assignment, so SC2154 here is a false positive about a zsh builtin.
        zstat -L -H _u_h -- "$1" 2>/dev/null || return 1
        # shellcheck disable=SC2154
        printf -v _U_MODE "%04o" $(( ${_u_h[mode]} & 4095 ))
        _U_SIZE=${_u_h[size]}; _U_UID=${_u_h[uid]}
    else
        # Darwin: `%p` is the full mode; the twelve bits are its LAST FOUR octal digits.
        _u_st_raw="$(/usr/bin/stat -f '%p %z %u' -- "$1" 2>/dev/null)" || return 1
        [ -n "$_u_st_raw" ] || return 1
        _U_MODE="${_u_st_raw%% *}"; _U_MODE="${_U_MODE: -4}"
        _u_st_rest="${_u_st_raw#* }"; _U_SIZE="${_u_st_rest%% *}"; _U_UID="${_u_st_rest##* }"
    fi
    return 0
}

# ── ACL-5 — the platform, probed at most ONCE per resolution and shared ───────────────────────────
# The RECOGNISED names are exactly `Darwin` and `Linux`. A probe that FAILS refuses (it may be failing
# because the machine is hostile); a probe that SUCCEEDS and prints any other name is a platform with
# NO enumerator, which is the condition AUTH-1(h)'s publisher carve-out is for.
# BUD-1 derives this count as 0 or 1: one iff at least one component is evaluated.
_u_platform() {
    [ -n "${_U_PLATFORM+set}" ] && return "${_U_PLATFORM_RC:-0}"
    _U_PLATFORM="$(/usr/bin/uname -s 2>/dev/null)" || { _U_PLATFORM=""; _U_PLATFORM_RC=1; return 1; }
    case "$_U_PLATFORM" in
        Darwin|Linux) _U_PLATFORM_RC=0 ;;
        *)            _U_PLATFORM_RC=2 ;;      # recognised as "no enumerator exists here"
    esac
    return "$_U_PLATFORM_RC"
}

# ── P-3a — the ACL principal ──────────────────────────────────────────────────────────────────────
# SCOPE: the DARWIN arm only, and only when its enumerator is present. The Linux arm does not compare
# principal NAMES at all, so it needs no principal and never runs this probe.
# Resolved ONCE per resolution, never once per component. `$USER` may not be used: it is inherited
# from the environment and ACL-7 forbids a verdict that differs between a plugin hook and a git hook.
_u_identity_probe() {
    /usr/bin/id -un 2>/dev/null
}

_u_principal() {
    [ -n "${_U_PRINCIPAL+set}" ] && return 0
    # §7 step 3f(iii) — the IDENTITY-PROBE SEAM, same principle: `/usr/bin/id` is invoked by
    # absolute path, so no unprivileged harness can make it fail by manipulating PATH, and a
    # fixture presenting a FAILED probe is only reachable by redefining this accessor.
    _U_PRINCIPAL="$(_u_identity_probe)" || { unset _U_PRINCIPAL; return 1; }
    # The obvious spelling of "a single non-empty line" is BROKEN and silently rejects everything:
    #     case "$v" in *"$(printf '\n')"*) ...
    # command substitution STRIPS trailing newlines, so `$(printf '\n')` is the EMPTY STRING and the
    # pattern degenerates to `*`, matching every input. A variable holding a literal newline works.
    _u_pr_nl='
'
    case "$_U_PRINCIPAL" in
        ''|*"$_u_pr_nl"*) unset _U_PRINCIPAL; return 1 ;;
    esac
    return 0
}

# ── P-13 — the ACE LINE parser ────────────────────────────────────────────────────────────────────
# STRICTLY a line parser: ONE argument, no line number, no classification. `_u_acl_answer_ok` decides
# WHICH lines are ACE lines; this decides whether ONE of them is well formed.
#
# ACL-2's grammar is exactly ` <decimal n>: <principal> [inherited] <allow|deny> <perms>` and EVERY
# SLOT is enforced positionally. Scanning for the verb cannot detect a duplicate: with
# `group:staff allow add_file allow list` a scanning parser discarded `add_file` and read the ACE as
# read-only `list`. No word splitting is used anywhere — zsh does not split unquoted parameter
# expansions and setting IFS does not change that, so `for f in $line` yields ONE field in zsh and
# every field in bash, which made this arm ACCEPT a hostile ACL in zsh while bash refused it.
_u_ace() {
    _u13_line="$1"
    _u13_idx="${_u13_line# }"; _u13_idx="${_u13_idx%%:*}"
    case "$_u13_idx" in ''|*[!0-9]*) return 1 ;; esac          # the index must be DECIMAL
    _u13_rest="${_u13_line# }"; _u13_rest="${_u13_rest#"$_u13_idx"}"
    case "$_u13_rest" in ': '*) _u13_body="${_u13_rest#: }" ;; *) return 1 ;; esac

    _u13_principal=""; _u13_verb=""; _u13_perms=""; _u13_inh=0; _u13_n=0
    _u13_rest="$_u13_body"
    while [ -n "$_u13_rest" ]; do
        _u13_tok="${_u13_rest%% *}"
        case "$_u13_rest" in *" "*) _u13_rest="${_u13_rest#* }" ;; *) _u13_rest="" ;; esac
        [ -n "$_u13_tok" ] || continue                          # a repeated space is not a field
        _u13_n=$(( _u13_n + 1 ))
        if [ -z "$_u13_verb" ]; then
            case "$_u13_tok" in
                allow|deny) _u13_verb="$_u13_tok" ;;
                inherited)  if [ "$_u13_n" = 1 ] || [ "$_u13_inh" = 1 ]; then return 1; fi
                            _u13_inh=1 ;;                       # optional, singular, never field 1
                *)          if [ "$_u13_n" = 1 ]; then _u13_principal="$_u13_tok"
                            else return 1                       # unknown field before the verb
                            fi ;;
            esac
        else
            [ -z "$_u13_perms" ] || return 1                    # a SECOND field after the verb
            case "$_u13_tok" in
                allow|deny|inherited) return 1 ;;               # a reserved token cannot BE the rights
            esac
            _u13_perms="$_u13_tok"
        fi
    done
    [ -n "$_u13_verb" ] || return 1
    [ -n "$_u13_principal" ] || return 1
    case "$_u13_perms" in
        ''|*,,*|,*|*,) return 1 ;;                              # empty, doubled, leading, trailing
    esac
    return 0
}

# ── ACL-4 — the ANSWER-level state machine, `STAT (BLANK | ACE)*` ─────────────────────────────────
# Acceptance is impossible until the ONE mandatory initial stat line has been seen. Line-level
# classification is NOT whole-answer parsing: it makes each line's kind decidable in isolation while
# leaving the ANSWER's shape unconstrained, and an answer consisting solely of a well-formed read-only
# ACE was accepted, so a healthy single-entry store resolved with OK=1 instead of refusing.
# The stat line is RECOGNISED POSITIVELY as `ls -l`'s mode field — "any line not starting with a
# space" accepted `garbage` as a stat line.
_u_acl_answer_ok() {                                            # stdin: the enumerator's answer
    _u_ans_st=INIT
    while IFS= read -r _u_ans_l || [ -n "$_u_ans_l" ]; do
        case "$_u_ans_st" in
            INIT) case "$_u_ans_l" in
                      [-dlbcps][-r][-w][-xSs][-r][-w][-xSs][-r][-w][-xTt]*) _u_ans_st=BODY ;;
                      *) return 1 ;;
                  esac ;;
            BODY) case "$_u_ans_l" in
                      '')   : ;;                                # BLANK
                      ' '*) _u_ace "$_u_ans_l" || return 1
                            _u_acl_ace_seen=1
                            _u_acl_check_ace || return 2 ;;     # 2 = a REFUSING ACE, not malformed
                      *)    return 1 ;;                         # a SECOND non-space line
                  esac ;;
        esac
    done
    [ "$_u_ans_st" = BODY ] || return 1                          # an EMPTY answer never reached BODY
    return 0
}

# ACL-1/ACL-2's verdict on ONE parsed ACE. `deny` entries are ignored ENTIRELY on every platform.
# For each `allow` ACE whose principal is not the effective user, REFUSE unless EVERY right named is
# one of exactly seven. This is an ALLOWLIST: a right nobody enumerated must REFUSE, and a blacklist
# of mutating rights is forbidden in any form. The four INHERITANCE FLAGS are not rights and are
# excluded from the test — without that exclusion an inherited read-only ACE refuses and the
# capability dies on every Mac that inherits ACLs.
_u_acl_check_ace() {
    [ "$_u13_verb" = allow ] || return 0
    case "$_u13_principal" in
        user:*) _u_acl_who="${_u13_principal#user:}" ;;
        *)      _u_acl_who="" ;;      # a `group:` or UNTYPED principal is another principal: a bare
    esac                              # UUID is an identity the system could not resolve, and the
    [ "$_u_acl_who" = "$_U_PRINCIPAL" ] && return 0             # fail-closed reading is the only safe one
    _u_acl_r_rest="$_u13_perms"
    while [ -n "$_u_acl_r_rest" ]; do
        _u_acl_r="${_u_acl_r_rest%%,*}"
        case "$_u_acl_r_rest" in *,*) _u_acl_r_rest="${_u_acl_r_rest#*,}" ;; *) _u_acl_r_rest="" ;; esac
        case "$_u_acl_r" in
            execute|list|read|readattr|readextattr|readsecurity|search) : ;;
            file_inherit|directory_inherit|limit_inherit|only_inherit) : ;;
            *) return 1 ;;
        esac
    done
    return 0
}

# The ACL condition on ONE component. 0 = accepted, non-zero = refused.
# ACL-6: this writes nothing — it creates no file and no byte anywhere, and never inside the path
# being validated. Authentication may not be established by attempting a write.
# §7 step 3f(iv) — THE ENUMERATOR-OUTPUT SEAM. Production and the harness call the SAME accessor;
# the harness makes a fixture available by REDEFINING this function after sourcing, which is why the
# seam is a function and not an environment variable. ACL-7 forbids conditioning any branch of the
# predicate on the environment — a verdict must be a property of the MACHINE — and an `if [ -n
# "$SOME_VAR" ]` here would be exactly that. Redefinition changes which accessor exists, not what the
# predicate consults.
#
# The seam is what makes the malformed-answer obligations RUNNABLE at all: `chmod +a` followed by
# `/bin/ls -lde` cannot emit a duplicate verb, an empty rights field, a non-decimal index or a second
# stat line, so without it those rows could be unit-tested as strings but never produce a
# store-level outcome through the production resolver.
_u_acl_enumerate() {
    /bin/ls -lde -- "$1" 2>/dev/null
}

_u_acl_ok() {
    _u_acl_out="$(_u_acl_enumerate "$1")" || return 1   # a failed enumerator REFUSES
    printf '%s\n' "$_u_acl_out" | _u_acl_answer_ok
}

# ── PCH-1 + ANCHOR-1 — one walk, both chains ──────────────────────────────────────────────────────
# $1 = an absolute path whose chain is walked, `/` down to and including $1 itself. Every component
# must exist, not be a symbolic link, not be group- or other-writable, satisfy ANCHOR-1's ownership
# rule and satisfy the ACL condition. Neither chain carries a clause the other lacks.
_unleashed_auth_chain() {
    _u_platform
    case "$?" in
        0) [ "$_U_PLATFORM" = Darwin ] || return 1 ;;   # Linux arms are not built (§4.2a-P)
        *) return 1 ;;                                  # failed or enumerator-less: UNEVALUABLE
    esac
    [ -n "${_U_PRINCIPAL+set}" ] || _u_principal || return 1

    _u_ac_in_prefix=1                  # ANCHOR-1: we begin inside the SYSTEM PREFIX run
    _u_ac_acc=""; _u_ac_rest="$1"
    while :; do
        case "$_u_ac_rest" in //*) _u_ac_rest="/${_u_ac_rest#//}"; continue ;; esac
        _u_ac_c="${_u_ac_acc:-/}"                       # THIS iteration's component (P-8)

        _u_stat "$_u_ac_c" || return 1                  # must exist
        [ -L "$_u_ac_c" ] && return 1                   # never a symbolic link
        case "$_U_MODE" in *[2367]?) return 1 ;; esac   # group-writable
        case "$_U_MODE" in *[2367])  return 1 ;; esac   # other-writable
        # ANCHOR-1: accept a LEADING RUN of system-prefix components (uid 0, and the two clauses
        # above). The TRUST ANCHOR is the first component that is not one; from it downward every
        # component must be euid-owned. A root-owned ${HOME} that satisfies the system-prefix test
        # REMAINS IN THE PREFIX and the anchor falls on the first component below it that does not.
        if [ "$_u_ac_in_prefix" = 1 ] && [ "$_U_UID" = 0 ]; then
            :
        else
            _u_ac_in_prefix=0
            [ "$_U_UID" = "${EUID:-$(/usr/bin/id -u)}" ] || return 1
        fi
        _u_acl_ok "$_u_ac_c" || return 1

        [ -n "$_u_ac_rest" ] || break
        _u_ac_rest="${_u_ac_rest#/}"
        [ -n "$_u_ac_rest" ] || break
        _u_ac_seg="${_u_ac_rest%%/*}"; _u_ac_acc="$_u_ac_acc/$_u_ac_seg"
        case "$_u_ac_rest" in *"/"*) _u_ac_rest="/${_u_ac_rest#*/}" ;; *) _u_ac_rest="" ;; esac
    done
    return 0
}
