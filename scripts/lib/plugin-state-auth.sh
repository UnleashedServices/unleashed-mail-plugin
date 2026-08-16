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

# ── PF-1 — the per-chain PREFETCH CACHE: the same calls, without the forks ────────────────────────
# `_unleashed_auth_chain` learns about a component through exactly TWO accessors, and each of them
# FORKS: `_u_stat` runs `/usr/bin/stat` and `_u_acl_enumerate` runs `/bin/ls -lde`. A nine-component
# store chain is therefore eighteen processes, and a reader walks THREE chains per resolution — a
# reader authenticates 24 components and a publish 45. Measured on this machine (medians of 20
# INTERLEAVED runs of `. scripts/lib/marker.sh` under a scratch HOME — the two builds alternate, so
# machine drift lands on both — bash 3.2.57 / zsh 5.9), before this change and after it:
#     no store, nothing to authenticate ....   8.1 /  8.3 ms bash,   9.1 /  9.1 ms zsh   (the floor)
#     store present, reader path .......... 246.8 /139.7 ms bash,  144.1 /105.5 ms zsh   1.77x / 1.37x
#     publish, entry already current ...... 685.3 /353.8 ms bash,  371.0 /256.9 ms zsh   1.94x / 1.44x
# It is NOT the 5-10x the fork count suggests, and the reason is MEASURED rather than argued: with
# `_u_acl_ok`'s body replaced by `return 0` — every enumeration, every parse and both of its
# subshells gone — the bash reader still costs 74.5 ms against this build's 132.6 ms in the same
# regime, so what is left is not `stat` and `ls`. It is `_u_acl_ok`'s own shape: a command
# substitution and a pipeline, two SUBSHELL forks per component.
#
# ── PF-2 — the PIPELINE, removed; the COMMAND SUBSTITUTION, deliberately kept ─────────────────────
# PF-1 left the second of those two subshells in place. PF-2 removes it: `_u_acl_answer_ok`'s machine
# is now reachable as `_u_acl_answer_ok_var`, which takes the answer as an ARGUMENT and splits it with
# parameter expansion, so `_u_acl_ok` calls it directly instead of piping into it. The stdin entry
# point is retained verbatim as a wrapper — the answer-shape obligations feed it by pipe. Measured in
# the same interleaved regime (MEANS of 10 runs, this build against its parent commit):
#     no store, nothing to authenticate ....   8.6 /  8.6 ms bash,   9.3 /  9.0 ms zsh   (the floor)
#     store present, reader path .......... 135.0 /105.6 ms bash,  101.7 / 84.2 ms zsh   1.28x / 1.21x
#     publish, entry already current ...... 341.1 /258.6 ms bash,  253.9 /203.6 ms zsh   1.32x / 1.25x
# A publish makes 69 `_u_acl_ok` calls (counted, not derived), and after PF-2 the PARSE is FREE: with
# `_u_acl_answer_ok_var` ablated to `return 0` the bash publish moves 249.6 -> 251.3 ms, which is
# 0.99x and therefore no effect at all. What is left inside `_u_acl_ok` is the command substitution
# alone, worth 89 ms of the 252 ms bash publish (`_u_acl_ok` ablated entirely to `return 0`:
# 252.1 -> 163.1 ms, 1.55x).
#
# THAT LAST SUBSHELL IS LOAD-BEARING AND STAYS. Serving the answer from `_U_ACL_CACHE` inside
# `_u_acl_ok` — the obvious way to remove it, measured at a further 1.33x — was BUILT, and it
# FAILS OPEN: `_u_chain_prefetch` fills the cache from the real `/bin/ls` whether or not a fixture has
# redefined `_u_acl_enumerate`, so the lookup serves the machine's own answer PAST the fixture. On the
# store fixture used above, three hostile seams the shipped build REFUSES (`stale`) were all ACCEPTED
# (`OK=1`) by that variant: a failing enumerator, a `group:staff allow write,delete` ACE, and a
# duplicate-verb answer. Removing it therefore requires migrating the SEAM's contract from stdout to a
# variable, and with it every `_u_acl_enumerate` fixture in the obligation suite — which is a change to
# what the obligations test, not to plumbing. See PF-1's note on `_u_acl_cache_get` below.
#
# What is removed is the FORK, never the CALL. `_u_chain_prefetch` runs ONE `/usr/bin/stat` and ONE
# `/bin/ls -lde -d` over every component of the chain that is about to be walked and parses both into
# two caches; each accessor consults its cache FIRST and, on a miss for ANY reason whatsoever, runs
# exactly the command it runs today. Three properties are load-bearing, and each is a property of
# WHERE the lookup sits rather than a claim about this implementation:
#   * THE ACCESSORS REMAIN THE SEAMS. §7 step 3f(iii)/(iv) present a fixture by REDEFINING `_u_stat`
#     or `_u_acl_enumerate`, and a redefinition replaces the very body the cache lookup lives in — so
#     a fixture still decides the predicate completely and the prefetched record is simply never read.
#   * THE CALL COUNT IS UNCHANGED. Every obligation that counts calls to either accessor counts the
#     same number after this change; only what happens inside the accessor differs.
#   * A MISS IS THE SHIPPED CODE PATH, byte for byte. Every guard below therefore fails onto
#     CORRECTNESS rather than onto speed: a component the batch could not describe is fetched exactly
#     as it was before, one fork at a time.
#
# THE CACHE IS PER CHAIN — not per process, and not per resolution. `_u_chain_prefetch` rebuilds both
# caches from empty every time it runs, and `_u_probes_reset` clears them at each resolution entry
# point for the same reason the principal/platform/euid caches are cleared there: these libraries are
# SOURCED into a consumer's shell, so a caller can pre-set ANY variable, and a cache a caller can seed
# is not a cache. Between the two, a cached record can only ever have been written by the prefetch of
# the chain being walked right now.
#
# WHY NO `_u_stat` OUTSIDE A WALK CAN COLLIDE WITH A STALE RECORD. Every path a prefetch caches is a
# component of a chain, and every chain's terminal component is `-d`-tested by its caller before
# `_unleashed_auth_chain` is entered (`_unleashed_nearest_existing`, the three `[ -d ]` guards in
# `_unleashed_create_store`, `_unleashed_store_ok`, `_unleashed_auth_entry`'s TGT-1 clause and the
# publisher's E2 clause), and an interior component must be a directory to have children. The
# `_u_stat` calls that happen OUTSIDE a walk are all on REGULAR FILES — the entry (`[ -f ]` first),
# its ENT-2c re-test, `/dev/fd/9`, and the publisher's transient — so none of them can name a cached
# path, and each one still forks exactly as it does today.
# BOTH CACHES CARRY THE SAME FRAMING, and it is not `<path><TAB><fields>`: a record keyed by a
# leading path is claimed by a PREFIX test, and a prefix test cannot be made exact when one key may
# be an ancestor of another. The framing is instead
#
#     <NL> <RS> <path> <NL> <payload line> <NL> [<payload line> <NL>]...
#
# repeated, with a leading <NL> so that EVERY header is preceded by one, <RS> = `\001`. A lookup is
# then the three parameter expansions in the getters below and it is EXACT, because:
#   * <RS> occurs in the cache ONLY at the start of a header. A component containing `\001` or a
#     newline abandons the batch entirely (see `_u_chain_prefetch`), the stat payload is four numeric
#     fields, and no line `/bin/ls -lde` prints can begin with `\001` — its first line begins with
#     `ls -l`'s TYPE character and every later line with a space.
#   * `<NL><RS><path><NL>` therefore occurs iff a header for EXACTLY that path was written, so the
#     match is on the whole path between two delimiters, never on a prefix or a suffix of one.
#   * components are distinct strings, so distinct headers.
# The separators are ANSI-C literals rather than a `printf -v` because a literal is a constant and a
# builtin call is not — NOT because the builtin was slow: measured over 4000 calls in bash 3.2, the
# `printf -v` form cost 0.0114 ms against 0.0102 ms for these literals and a 0.0089 ms empty-function
# floor, which is 0.0012 ms and is not a reason for anything. `$'\001'` is understood by both target
# shells (measured: length 1 in bash 3.2.57 and zsh 5.9).
# THEY ARE SET UNCONDITIONALLY, every call. A "already derived" flag, or trusting a value that is
# already there, would put the cache's framing under a caller's control — the same defect that a
# pre-set `_U_PRINCIPAL_PROBED` was.
_u_pf_sep() {
    _u_pf_nl='
'
    _u_pf_rs=$'\001'
}

# A `_U_STAT_CACHE` hit. The payload is `<mode> <size> <uid> <ino>`, in `_u_stat`'s own order, with
# the mode ALREADY reduced to its last four octal digits by the prefetch — which is exactly what
# `_u_stat`'s bash arm computes and exactly what the zsh arm's `%04o` of `mode & 4095` produces
# (measured: `40755` -> both give `0755`; `104600` -> both give `4600`). A hit therefore answers
# IDENTICALLY in both shells, which is why the lookup sits inside both arms rather than in front of
# them, and why the reduction is done once at prefetch rather than once per lookup.
_u_stat_cache_get() {
    [ -n "${_U_STAT_CACHE:-}" ] || return 1
    _u_pf_sep
    _u_sg_h="$_u_pf_nl$_u_pf_rs$1$_u_pf_nl"
    # A MISS IS "THE PREFIX STRIP CHANGED NOTHING", not a separate `case` search: `${v#*h}` returns
    # `v` unchanged exactly when `h` does not occur, and a hit always removes at least the header, so
    # the equality test is exact and the ~1 KB cache is scanned once instead of twice.
    _u_sg_v="${_U_STAT_CACHE#*"$_u_sg_h"}"
    [ "$_u_sg_v" = "$_U_STAT_CACHE" ] && return 1
    _u_sg_v="${_u_sg_v%%"$_u_pf_nl"*}"
    _U_MODE="${_u_sg_v%% *}"; _u_sg_v="${_u_sg_v#* }"
    _U_SIZE="${_u_sg_v%% *}"; _u_sg_v="${_u_sg_v#* }"
    _U_UID="${_u_sg_v%% *}"; _U_INO="${_u_sg_v##* }"
    return 0
}

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
        # PF-1 — the prefetched record first, and the SAME record in both arms. The lookup is written
        # once per arm rather than once in front of them so that the two arms stay textually
        # symmetric: an arm that could reach the fork without consulting the cache, or consult a
        # cache the other arm does not, is exactly the FAM-5 class of divergence no single-arm test
        # can see. On a miss the arm below runs unchanged.
        _u_stat_cache_get "$1" && return 0
        zmodload zsh/stat 2>/dev/null
        # `zstat -H _u_h` populates the associative array `_u_h`; shellcheck models bash and cannot
        # see that assignment, so SC2154 here is a false positive about a zsh builtin.
        zstat -L -H _u_h -- "$1" 2>/dev/null || return 1
        # shellcheck disable=SC2154
        printf -v _U_MODE "%04o" $(( ${_u_h[mode]} & 4095 ))
        _U_SIZE=${_u_h[size]}; _U_UID=${_u_h[uid]}; _U_INO=${_u_h[inode]}
    else
        _u_stat_cache_get "$1" && return 0                  # PF-1, the same lookup as the zsh arm
        # Darwin: `%p` is the full mode; the twelve bits are its LAST FOUR octal digits. `%i` is the
        # inode — ENT-2b binds the OPENED object to it (measured: /dev/fd/N reports the open object's
        # inode, size and uid, but its mode as the open flags and its device as fdesc's).
        _u_st_raw="$(/usr/bin/stat -f '%p %z %u %i' -- "$1" 2>/dev/null)" || return 1
        [ -n "$_u_st_raw" ] || return 1
        _U_MODE="${_u_st_raw%% *}"; _U_MODE="${_U_MODE: -4}"
        _u_st_rest="${_u_st_raw#* }"; _U_SIZE="${_u_st_rest%% *}"
        _u_st_rest="${_u_st_rest#* }"; _U_UID="${_u_st_rest%% *}"; _U_INO="${_u_st_rest##* }"
    fi
    return 0
}

# ── ACL-5 — the platform, probed at most ONCE per resolution and shared ───────────────────────────
# The RECOGNISED names are exactly `Darwin` and `Linux`. A probe that FAILS refuses (it may be failing
# because the machine is hostile); a probe that SUCCEEDS and prints any other name is a platform with
# NO enumerator, which is the condition AUTH-1(h)'s publisher carve-out is for.
# BUD-1 derives this count as 0 or 1: one iff at least one component is evaluated.
_u_platform() {
    # Cached only within ONE resolution — see `_u_probes_reset` above for why an inherited flag
    # or value is never honoured.
    [ "${_U_PLATFORM_PROBED:-}" = 1 ] && return "${_U_PLATFORM_RC:-0}"
    _U_PLATFORM_PROBED=1
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
# THE EFFECTIVE UID, and never `$EUID`. bash 3.2 — the `/bin/bash` a macOS hook runs — IMPORTS EUID
# from the environment as an ordinary exported variable (measured: `env EUID=4242 bash -c 'echo $EUID'`
# prints 4242; zsh sets its own and is unaffected), so `${EUID:-$(/usr/bin/id -u)}` let the parent
# decide the answer to every ownership test: a healthy store read `stale` and a publish `failed`
# (codex sweep, PR #67 pass 14 — reproduced). The fix is not to consult that variable at all. Same
# IDENTITY-PROBE SEAM rule as `_u_identity_probe`: absolute path, so no PATH manipulation can make it
# fail, and a fixture presenting a failed probe must redefine this accessor.
_u_euid_probe() {
    /usr/bin/id -u 2>/dev/null
}
_u_euid() {
    # Cached only within ONE resolution, exactly like `_u_principal`: `_u_probes_reset` clears the flag
    # at the entry points, so honouring it here can never honour a caller's.
    [ "${_U_EUID_PROBED:-}" = 1 ] && return 0
    _U_EUID="$(_u_euid_probe)" || { unset _U_EUID; return 1; }
    case "$_U_EUID" in ''|*[!0-9]*) unset _U_EUID; return 1 ;; esac
    _U_EUID_PROBED=1
    return 0
}
# THE EFFECTIVE USER'S UUID, the second half of P-3a. `/bin/ls -lde` renders an ACE's principal as
# `user:<name>` when the system can resolve the identity and as a BARE UUID when it cannot — and on
# some hosts (a mobile or directory account) the EFFECTIVE USER'S OWN ACE renders as the UUID. A parser
# that treated every bare UUID as foreign refused a legitimate self-ACE and an authoritative publisher
# reported `failed` (external audit of PR #67, finding 1). Resolved ONCE per resolution, by absolute
# path, one fork; anything but a single well-formed UUID leaves it EMPTY, and an empty value means "no
# bare UUID is self" — fail closed, exactly as before.
_u_identity_uuid_probe() {
    /usr/bin/dsmemberutil getuuid -U "$1" 2>/dev/null
}

# ── The probe caches, and why NO inherited state is honoured ──────────────────────────────────────
# These libs are SOURCED into a consumer's shell, so ANY variable — the principal, the platform,
# and any flag that says "already probed" — may already exist there: inherited, exported, or set
# by a hostile caller. Round one of this defect trusted the VALUE's presence (a pre-set
# `_U_PRINCIPAL=daemon` was accepted and would have exempted a foreign `user:daemon` ACE); round
# two moved the trust to a FLAG — and a pre-set `_U_PRINCIPAL_PROBED=1` beside the value bypassed
# the probe just as completely (codex, PR #67, twice; both reproduced). A cache key a caller can
# set is not a cache key. So the caches are RESET at every resolution entry point —
# `_unleashed_read_store` and `_unleashed_publish` call `_u_probes_reset` first — and the flags
# below mean only "probed DURING this resolution". A caller-set flag is discarded before it can
# be consulted; a caller-set value is overwritten by the probe.
_u_probes_reset() {
    unset _U_PRINCIPAL _U_PRINCIPAL_UUID _U_PRINCIPAL_PROBED _U_PLATFORM _U_PLATFORM_PROBED _U_PLATFORM_RC
    unset _U_EUID _U_EUID_PROBED
    # PF-1's two prefetch caches, for EXACTLY the reason above and no other: `_U_STAT_CACHE` and
    # `_U_ACL_CACHE` are ordinary variables in a sourced library, so a caller can arrive holding a
    # record that says a component is 0700 and euid-owned, or an ACL answer with no foreign ACE in
    # it. Cleared here, a caller's record is discarded before any accessor can consult it; rebuilt
    # from empty by `_u_chain_prefetch`, it can only ever describe the chain being walked now. This
    # is the principal/platform/euid rule applied to the two caches that answer FOR a component
    # rather than about the process.
    unset _U_STAT_CACHE _U_ACL_CACHE
}

_u_principal() {
    # Cached only within ONE resolution: the entry points reset this flag before any walk begins,
    # so honouring it here cannot honour a caller's. P-3a: resolved once per resolution, not per
    # component.
    [ "${_U_PRINCIPAL_PROBED:-}" = 1 ] && return 0
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
    # The UUID: accepted only in the exact 8-4-4-4-12 hex shape, ONE line; anything else is "none".
    _U_PRINCIPAL_UUID="$(_u_identity_uuid_probe "$_U_PRINCIPAL")" || _U_PRINCIPAL_UUID=""
    case "$_U_PRINCIPAL_UUID" in
        [0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]-[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]-[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]-[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]-[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]) : ;;
        *) _U_PRINCIPAL_UUID="" ;;
    esac
    _U_PRINCIPAL_PROBED=1
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
#
# PF-2 — ONE state machine, TWO entry points. The answer always reaches `_u_acl_ok` ALREADY IN A
# VARIABLE — it is what the enumerator's command substitution captured, whatever the enumerator was —
# so the shipped predicate calls `_u_acl_answer_ok_var` and walks that variable with parameter
# expansion. `_u_acl_ok` does NOT read `_U_ACL_CACHE`; see the note on `_u_acl_cache_get` for why.
# `_u_acl_answer_ok` is retained as a THIN WRAPPER over the identical machine, and its STDIN CONTRACT
# is unchanged, because the answer-shape obligations feed it by pipe.
#
# THE LINE SPLIT IS EXACTLY `IFS= read -r`'s, and the equivalence is the reason the wrapper can
# delegate rather than duplicate: `read` yields one line per <NL>, yields a final unterminated line
# through its `|| [ -n ... ]` arm, and yields NOTHING for empty input. `${rest%%<NL>*}` /
# `${rest#*<NL>}` under `while [ -n "$rest" ]` yields the same sequence for every input, and the ONE
# input where the two differ — `""` against `"\n"` — reaches `[ "$_u_ans_st" = BODY ]` in state INIT
# either way and refuses either way. A TRAILING NEWLINE IS THEREFORE IMMATERIAL, which is what makes
# the captured `$(...)` value (all trailing newlines stripped) and the piped `printf '%s\n'` form
# decide identically.
#
# THE NEWLINE IS A VARIABLE HOLDING A LITERAL ONE, never `$(printf '\n')`: command substitution
# STRIPS trailing newlines, so that spelling is the EMPTY STRING and `*""*` matches every input.
# This codebase has been bitten by it twice (`_u_principal`'s line test, and `_u_pf_sep`).
_u_acl_answer_ok_var() {                                        # $1: the enumerator's answer
    _u_ans_st=INIT
    _u_ans_nl='
'
    _u_ans_rest="$1"
    while [ -n "$_u_ans_rest" ]; do
        case "$_u_ans_rest" in
            *"$_u_ans_nl"*) _u_ans_l="${_u_ans_rest%%"$_u_ans_nl"*}"
                            _u_ans_rest="${_u_ans_rest#*"$_u_ans_nl"}" ;;
            *)              _u_ans_l="$_u_ans_rest"; _u_ans_rest="" ;;
        esac
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

# The STDIN entry point, unchanged in contract: it reads the whole answer into one variable and
# delegates. Its own scratch names (`_u_ans_in`, `_u_ans_rl`, `_u_ans_wnl`) are distinct from the
# machine's, so the delegation cannot clobber what it is still holding. Rebuilding the text line by
# line appends a trailing newline the input may not have had, which by the equivalence above cannot
# change a verdict.
_u_acl_answer_ok() {                                            # stdin: the enumerator's answer
    _u_ans_wnl='
'
    _u_ans_in=""
    while IFS= read -r _u_ans_rl || [ -n "$_u_ans_rl" ]; do
        _u_ans_in="$_u_ans_in$_u_ans_rl$_u_ans_wnl"
    done
    _u_acl_answer_ok_var "$_u_ans_in"
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
        user:*) _u_acl_who="${_u13_principal#user:}"; [ "$_u_acl_who" = "$_U_PRINCIPAL" ] && return 0 ;;
        group:*) : ;;                 # a `group:` principal is another principal
        *)  # UNTYPED: a bare UUID. It is SELF iff it equals the effective user's RESOLVED UUID (P-3a's
            # second probe, non-empty) — the rendering some hosts give the effective user's own ACE.
            # Any other bare UUID is an identity the system could not resolve, and the fail-closed
            # reading — foreign — is the only safe one (row 129; external audit of PR #67, finding 1).
            [ -n "${_U_PRINCIPAL_UUID:-}" ] && [ "$_u13_principal" = "$_U_PRINCIPAL_UUID" ] && return 0 ;;
    esac
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
#
# PF-1 — the prefetched answer is consulted HERE, inside the seam, and never in `_u_acl_ok`. That
# placement is the whole safety argument: a fixture presents its answer by REDEFINING this function,
# which removes the lookup along with the fork, so a fixture's answer is still the only answer the
# predicate can see. A lookup in `_u_acl_ok` would have served a cached `/bin/ls` answer PAST a
# fixture and silently disarmed every enumerator-output obligation.
#
# PF-2 MEASURED THAT, rather than leaving it as an argument. The variant was built — a cache getter
# writing `_U_ACL_OUT` and consulted at the top of `_u_acl_ok` — and it is 1.33x faster and WRONG:
# against one healthy store, `_u_acl_enumerate() { return 1; }`, a `group:staff allow write,delete`
# answer and a duplicate-verb answer each resolved `OK=1` where the shipped build refuses `stale`.
# Three fixtures, three fail-opens. The lookup stays inside the accessor.
_u_acl_cache_get() {
    [ -n "${_U_ACL_CACHE:-}" ] || return 1
    _u_pf_sep
    _u_ag_h="$_u_pf_nl$_u_pf_rs$1$_u_pf_nl"
    _u_ag_out="${_U_ACL_CACHE#*"$_u_ag_h"}"             # everything after this component's header
    [ "$_u_ag_out" = "$_U_ACL_CACHE" ] && return 1      # unchanged == the header is not there
    case "$_u_ag_out" in *"$_u_pf_rs"*) _u_ag_out="${_u_ag_out%%"$_u_pf_rs"*}" ;; esac   # to the next
    printf '%s' "$_u_ag_out"
    return 0
}

_u_acl_enumerate() {
    _u_acl_cache_get "$1" && return 0
    /bin/ls -lde -- "$1" 2>/dev/null
}

_u_acl_ok() {
    _u_acl_out="$(_u_acl_enumerate "$1")" || return 1   # a failed enumerator REFUSES
    _u_acl_answer_ok_var "$_u_acl_out"                  # PF-2: the same machine, without the pipe
}

# ── PF-1 — ONE lstat and ONE enumeration for the whole chain ──────────────────────────────────────
# $1 = the chain the walk is about to make. Fills `_U_STAT_CACHE` and `_U_ACL_CACHE`, or leaves either
# EMPTY — which is not a failure and is never reported as one, because an empty cache is a total miss
# and a total miss is the shipped per-component behaviour. This function returns 0 always: it decides
# nothing, and a prefetch that decided anything would be a second predicate, which AUTH-1 forbids.
#
# ACL-6 still holds: `stat` and `ls` create no file and no byte anywhere.
_u_chain_prefetch() {
    _U_STAT_CACHE=""; _U_ACL_CACHE=""          # ONE chain at a time; never accumulated across walks
    _u_pf_sep
    _u_cp_path="$1"

    # (1) THE COMPONENT LIST, derived by the SAME loop the walk below uses — the `//` collapse, the
    # `${acc:-/}` root and the trailing-slash handling are copied clause for clause, because a list
    # that differed from the walk's would prefetch one path and answer for another. The positional
    # parameters carry it: they are the one list structure bash 3.2 and zsh index identically, and
    # `set --` here rebinds only THIS function's own arguments.
    set --
    _u_cp_acc=""; _u_cp_rest="$_u_cp_path"
    while :; do
        case "$_u_cp_rest" in //*) _u_cp_rest="/${_u_cp_rest#//}"; continue ;; esac
        _u_cp_c="${_u_cp_acc:-/}"
        # UNFRAMEABLE COMPONENTS ABANDON THE WHOLE BATCH, both halves of it. A newline in a component
        # would split one `stat` record or one `ls` block into two and let a record answer for a path
        # that is not its own; `\001` would collide with the ACL cache's header framing. Neither is
        # worth a special case: the walk then runs exactly as it ran before this change.
        case "$_u_cp_c" in
            *"$_u_pf_nl"*|*"$_u_pf_rs"*) return 0 ;;
        esac
        set -- "$@" "$_u_cp_c"
        [ -n "$_u_cp_rest" ] || break
        _u_cp_rest="${_u_cp_rest#/}"
        [ -n "$_u_cp_rest" ] || break
        _u_cp_seg="${_u_cp_rest%%/*}"; _u_cp_acc="$_u_cp_acc/$_u_cp_seg"
        case "$_u_cp_rest" in *"/"*) _u_cp_rest="/${_u_cp_rest#*/}" ;; *) _u_cp_rest="" ;; esac
    done
    [ "$#" -gt 0 ] || return 0

    # (2) ONE lstat over every component. `/usr/bin/stat` is lstat by default, which is the property
    # `_u_stat`'s own bash arm depends on, and the same absolute path is used for the same reason.
    # A PARTIAL answer is KEPT: `stat` exits non-zero when an operand is missing but still prints a
    # correct line for every operand that is not, and a record is only ever found by its own path, so
    # a component absent from the output simply misses and is fetched per-path exactly as before.
    # THE NAME IS THE REMAINDER, NOT A FIELD: `%N` is placed last precisely because a path may
    # contain spaces and the four fields before it may not, so the line is split on the first four
    # spaces and everything after them is the path, verbatim as the operand was given.
    _u_cp_st="$(/usr/bin/stat -f '%p %z %u %i %N' -- "$@" 2>/dev/null)" || :
    _u_cp_out=""
    _u_cp_rest="$_u_cp_st"
    while [ -n "$_u_cp_rest" ]; do
        case "$_u_cp_rest" in
            *"$_u_pf_nl"*) _u_cp_line="${_u_cp_rest%%"$_u_pf_nl"*}"; _u_cp_rest="${_u_cp_rest#*"$_u_pf_nl"}" ;;
            *)             _u_cp_line="$_u_cp_rest"; _u_cp_rest="" ;;
        esac
        _u_cp_f="$_u_cp_line"; _u_cp_bad=0
        _u_cp_m="${_u_cp_f%% *}"; case "$_u_cp_f" in *" "*) _u_cp_f="${_u_cp_f#* }" ;; *) _u_cp_bad=1 ;; esac
        _u_cp_z="${_u_cp_f%% *}"; case "$_u_cp_f" in *" "*) _u_cp_f="${_u_cp_f#* }" ;; *) _u_cp_bad=1 ;; esac
        _u_cp_u="${_u_cp_f%% *}"; case "$_u_cp_f" in *" "*) _u_cp_f="${_u_cp_f#* }" ;; *) _u_cp_bad=1 ;; esac
        _u_cp_i="${_u_cp_f%% *}"; case "$_u_cp_f" in *" "*) _u_cp_f="${_u_cp_f#* }" ;; *) _u_cp_bad=1 ;; esac
        [ "$_u_cp_bad" = 0 ] || continue                # a line with fewer than five fields is dropped
        [ -n "$_u_cp_f" ] || continue
        # The TWELVE bits, as `_u_stat`'s bash arm takes them: the last four octal digits of `%p`.
        # `#?` removes one CHARACTER in both shells, where `${v: -4}` is the bash arm's spelling and
        # this record is served to both.
        while [ "${#_u_cp_m}" -gt 4 ]; do _u_cp_m="${_u_cp_m#?}"; done
        _u_cp_out="$_u_cp_out$_u_pf_nl$_u_pf_rs$_u_cp_f$_u_pf_nl$_u_cp_m $_u_cp_z $_u_cp_u $_u_cp_i$_u_pf_nl"
    done
    _U_STAT_CACHE="$_u_cp_out"

    # (3) ONE enumeration over every component, mapped back to the components by the path each block
    # names. UNLIKE the stat batch this is ALL-OR-NOTHING: a non-zero exit, a block whose path
    # matches no component (a symbolic link renders as `<path> -> <target>` and matches none), a
    # component claimed twice, or any component with no block at all discards the WHOLE cache and
    # every component is enumerated singly, exactly as before. Correctness first, speed second.
    #
    # A BATCHED BLOCK IS NOT BYTE-IDENTICAL to a single-operand one — `ls` sizes its columns to the
    # widest operand, so the link-count field is padded differently — and that is immaterial, which
    # was MEASURED rather than assumed: over five ACL shapes (no ACL, a read-only foreign ACE, a
    # mutating foreign ACE, an own-user ACE, thirteen stacked ACEs) in both shells, the cached block
    # and the freshly forked one differ only in runs of spaces and `_u_acl_answer_ok` returns the
    # SAME status for both, rc=2 included. Nothing downstream reads a column: `_u_acl_answer_ok`
    # recognises the first line by the mode field at its start and every later line by its leading
    # space, and `_u_ace` splits fields on runs of spaces.
    _u_cp_ls="$(/bin/ls -lde -d -- "$@" 2>/dev/null)" || _u_cp_ls=""
    [ -n "$_u_cp_ls" ] || return 0
    _u_cp_out=""; _u_cp_claim=""; _u_cp_have=0; _u_cp_cur=""; _u_cp_ok=1
    _u_cp_rest="$_u_cp_ls"
    while [ -n "$_u_cp_rest" ]; do
        case "$_u_cp_rest" in
            *"$_u_pf_nl"*) _u_cp_line="${_u_cp_rest%%"$_u_pf_nl"*}"; _u_cp_rest="${_u_cp_rest#*"$_u_pf_nl"}" ;;
            *)             _u_cp_line="$_u_cp_rest"; _u_cp_rest="" ;;
        esac
        case "$_u_cp_line" in
            ' '*|'')                                    # an ACE line, or a blank: same block
                [ -n "$_u_cp_cur" ] || { _u_cp_ok=0; break; }
                _u_cp_out="$_u_cp_out$_u_cp_line$_u_pf_nl" ;;
            *)                                          # a stat line: a new block, and whose?
                # The component the line NAMES. `ls` sorts its operands, so position proves nothing;
                # the LAST match wins because the component list is in walk order and a chain's
                # components strictly increase in length, so "last" is "longest". Even a mismatch
                # that survived the claim test below could not change a verdict: `_u_acl_ok` is a
                # predicate on the ANSWER alone and the walk accepts iff EVERY component's answer
                # passes, so permuting answers among one chain's components preserves that
                # conjunction exactly. The claim test is kept anyway — a mis-assignment is a fact
                # about the batch, and a batch that cannot be trusted is not used.
                _u_cp_cur=""
                for _u_cp_k in "$@"; do
                    case "$_u_cp_line" in *" $_u_cp_k") _u_cp_cur="$_u_cp_k" ;; esac
                done
                [ -n "$_u_cp_cur" ] || { _u_cp_ok=0; break; }
                case "$_u_cp_claim" in
                    *"$_u_pf_rs$_u_cp_cur$_u_pf_rs"*) _u_cp_ok=0; break ;;
                esac
                _u_cp_claim="$_u_cp_claim$_u_pf_rs$_u_cp_cur$_u_pf_rs"
                _u_cp_have=$(( _u_cp_have + 1 ))
                _u_cp_out="$_u_cp_out$_u_pf_nl$_u_pf_rs$_u_cp_cur$_u_pf_nl$_u_cp_line$_u_pf_nl" ;;
        esac
    done
    if [ "$_u_cp_ok" = 1 ] && [ "$_u_cp_have" = "$#" ]; then
        _U_ACL_CACHE="$_u_cp_out"
    fi
    return 0
}

# ── PCH-1 + ANCHOR-1 — one walk, both chains ──────────────────────────────────────────────────────
# $1 = an absolute path whose chain is walked, `/` down to and including $1 itself. Every component
# must exist, not be a symbolic link, not be group- or other-writable, satisfy ANCHOR-1's ownership
# rule and satisfy the ACL condition. Neither chain carries a clause the other lacks.
_unleashed_auth_chain() {
    # THIS BUILD IS DARWIN-ONLY, AND SAYS SO RATHER THAN IMPLYING OTHERWISE. AUTH-1(h) grants a
    # PUBLISHER a carve-out on a platform where no enumerator EXISTS (a successful `uname` naming
    # neither Darwin nor Linux); the reader never gets it. Honouring that needs a publisher/reader
    # role threaded through this walk, and it is DELIBERATELY DEFERRED with the Linux arms — plan
    # rows 106/107/120/121 are recorded as unbuildable under this scope for exactly that reason.
    # So every non-Darwin outcome refuses uniformly here, publisher and reader alike, and
    # `_u_platform`'s distinct "no enumerator" status is kept ONLY so the future carve-out has
    # something to branch on. codex (PR #67, #6) is right that the surrounding contract describes a
    # carve-out this branch does not honour; the resolution is to state the gap, not to build the
    # carve-out into an arm that has no enumerator to guard.
    _u_platform
    case "$?" in
        0) [ "$_U_PLATFORM" = Darwin ] || return 1 ;;   # Linux arms are not built (§4.2a-P)
        *) return 1 ;;   # a FAILED probe (1) or an ENUMERATOR-LESS platform (2): both refuse
    esac
    # `_u_principal` decides for itself whether it is cached (on ITS OWN flag); a presence test on
    # the variable here would re-open the pre-set-value bypass that codex found (PR #67, #5).
    _u_principal || return 1
    # PF-1 — one lstat and one enumeration for the whole chain, taken before the walk reads its first
    # component. It sits BELOW the platform gate, not above it, because both batch programs are the
    # DARWIN arm's: on a platform this build refuses there is nothing to prefetch and this line has
    # forked nothing. It cannot refuse and cannot accept; the walk below is unchanged and still asks
    # the same two accessors about every component in the same order.
    _u_chain_prefetch "$1"

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
            { _u_euid && [ "$_U_UID" = "$_U_EUID" ]; } || return 1
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
