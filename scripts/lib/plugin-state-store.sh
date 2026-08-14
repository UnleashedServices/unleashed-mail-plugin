# shellcheck shell=bash
# COREDEV-2617 §7 step 3a — the entry-key encoder, the store, and the NAME_MAX budget.
#
# DARWIN ARMS ONLY. The Linux arms of P-2, ACL-3 and P-4 are deliberately unmeasured (§4.2a-P) and
# this file does not guess them; `scripts/review/linux-primitive-probe.sh` exists to measure them and
# its output must be transcribed into the plan before a Linux arm is built.
#
# WHAT THIS FILE IS
# §4.2a lets a shell that never receives the plugin-data environment variable — the one `paths.sh`
# resolves, unspelled here because N5's lexical-drift check allowlists by FILE and a new primitive
# should not be on that list — discover the base by reading a store of entries under
# ${HOME}/.claude/unleashed-mail/bases/. Each publisher writes ONE entry whose
# NAME is an injective encoding of the base value it holds, so publishers with different bases never
# write the same path and a conflict is a property of the directory, derived at read time. There is no
# lock: a trap set in a function fires at function return in zsh and at process exit in bash, and a
# shell has one EXIT slot the caller usually owns, so a lock in a sourced library cannot be reliably
# released.
#
# EVERY SCRATCH VARIABLE CARRIES ITS FUNCTION'S PREFIX (FAM-5). A POSIX shell function has no locals
# and these libs are SOURCED into a consumer's shell, so every helper shares one namespace with every
# other helper AND with the consumer. This is not style: naming P-2's bash-arm scratch the same as the
# chain walk's loop variable made bash REFUSE and zsh RESOLVE the identical real chain, because the
# zsh arm uses the `zstat` builtin and never touches that name. A collision only one arm has is a
# divergence no single-arm test can see.

# ── ENC-1..ENC-5 — the entry-key encoder (Invariant P) ────────────────────────────────────────────
# K(v) is a SINGLE left-to-right walk over the BYTES of v with LC_ALL=C in force, emitting for each
# byte exactly one of four disjoint markers and otherwise that byte unchanged:
#     _ -> _u   /  -> _s   upper C -> _c<lower(C)>   byte >= 0x80 or < 0x20 -> _x<hh>
# There is no fifth marker, no case folding and no locale dependence. Decoding is unambiguous, so K is
# injective: `_` is always followed by exactly one of u/s/c/x, `c` consumes one further byte and `x`
# consumes two. 0x7F (DEL) is emitted UNCHANGED — the four rows above are the whole table.
#
# Result in _UNLEASHED_KEY. ZERO FORKS: no command substitution, no external program (ENC-2).
_unleashed_key() {
    _uk_v="$1"
    _uk_out=""
    # ENC-3: record LC_ALL's exact entry state and restore it on every path by which this ends.
    # An EMPTY LC_ALL is not the same as an absent one, so the two cases are distinguished.
    if [ -n "${LC_ALL+set}" ]; then _uk_lc_set=1; _uk_lc_val="$LC_ALL"; else _uk_lc_set=0; fi
    LC_ALL=C

    _uk_i=0
    _uk_len=${#_uk_v}
    while [ "$_uk_i" -lt "$_uk_len" ]; do
        _uk_c=${_uk_v:$_uk_i:1}
        case "$_uk_c" in
            _)  _uk_out="${_uk_out}_u" ;;
            /)  _uk_out="${_uk_out}_s" ;;
            A) _uk_out="${_uk_out}_ca" ;; B) _uk_out="${_uk_out}_cb" ;;
            C) _uk_out="${_uk_out}_cc" ;; D) _uk_out="${_uk_out}_cd" ;;
            E) _uk_out="${_uk_out}_ce" ;; F) _uk_out="${_uk_out}_cf" ;;
            G) _uk_out="${_uk_out}_cg" ;; H) _uk_out="${_uk_out}_ch" ;;
            I) _uk_out="${_uk_out}_ci" ;; J) _uk_out="${_uk_out}_cj" ;;
            K) _uk_out="${_uk_out}_ck" ;; L) _uk_out="${_uk_out}_cl" ;;
            M) _uk_out="${_uk_out}_cm" ;; N) _uk_out="${_uk_out}_cn" ;;
            O) _uk_out="${_uk_out}_co" ;; P) _uk_out="${_uk_out}_cp" ;;
            Q) _uk_out="${_uk_out}_cq" ;; R) _uk_out="${_uk_out}_cr" ;;
            S) _uk_out="${_uk_out}_cs" ;; T) _uk_out="${_uk_out}_ct" ;;
            U) _uk_out="${_uk_out}_cu" ;; V) _uk_out="${_uk_out}_cv" ;;
            W) _uk_out="${_uk_out}_cw" ;; X) _uk_out="${_uk_out}_cx" ;;
            Y) _uk_out="${_uk_out}_cy" ;; Z) _uk_out="${_uk_out}_cz" ;;
            *)
                # P-7: the byte's value without a fork. bash SIGN-EXTENDS `printf '%d' "'c"` for
                # bytes >= 0x80 (measured: -61 for \303 in bash, 195 in zsh), so the mask is
                # mandatory and not defensive. `printf -v` assigns without a subshell in BOTH shells;
                # `n=$(printf ...)` would fork and break ENC-2's zero-fork requirement.
                printf -v _uk_n "%d" "'$_uk_c"
                _uk_n=$(( _uk_n & 255 ))
                # P-3: decimal constants only. A bare 0NNN inside $(( )) is octal in bash and DECIMAL
                # in zsh — $((0777)) is 511 and 777 respectively.
                if [ "$_uk_n" -ge 128 ] || [ "$_uk_n" -lt 32 ]; then
                    printf -v _uk_hh "%02x" "$_uk_n"
                    _uk_out="${_uk_out}_x${_uk_hh}"
                else
                    _uk_out="${_uk_out}${_uk_c}"
                fi
                ;;
        esac
        _uk_i=$(( _uk_i + 1 ))
    done

    if [ "$_uk_lc_set" = 1 ]; then LC_ALL="$_uk_lc_val"; else unset LC_ALL; fi
    _UNLEASHED_KEY="$_uk_out"
}

# ── P-9 — the nearest EXISTING ancestor, fork-free ────────────────────────────────────────────────
# Terminates at `/`, which always exists, so there is no unbounded loop on a pathological input.
_unleashed_nearest_existing() {
    _ne_d="$1"
    while [ ! -d "$_ne_d" ]; do
        case "$_ne_d" in
            */*) _ne_d="${_ne_d%/*}"; [ -n "$_ne_d" ] || _ne_d=/ ;;
            *)   _ne_d=/; break ;;
        esac
    done
    _UNLEASHED_NEAREST="$_ne_d"
}

# ── NM-1 / PUB-9 E3 — the name-length budget, FAIL CLOSED ─────────────────────────────────────────
# $1 = the store directory, which may not exist yet. Sets _UNLEASHED_NAME_MAX, or returns non-zero to
# take E3. The numeric guard is NOT redundant with the status check: with an empty value
# `[ 42 -gt "" ]` is status 2 in bash 3.2.57 — so an `if` takes the ELSE branch and a publisher would
# PROCEED — and status 0 in zsh 5.9, so it would refuse. The same code, opposite outcomes, which is
# why the value is validated before it is ever compared.
_unleashed_name_max() {
    _unleashed_nearest_existing "$1"
    # The directory operand is MANDATORY: the bare command exits 64. Absolute path, never via PATH.
    _nm_v="$(/usr/bin/getconf NAME_MAX "$_UNLEASHED_NEAREST" 2>/dev/null)" || return 1
    case "$_nm_v" in
        ''|*[!0-9]*) return 1 ;;
    esac
    _UNLEASHED_NAME_MAX="$_nm_v"
    return 0
}

# TMP-1's transient is the LONGEST name a publisher creates: `.pub.<pid>.<uniq>.<key>` is
# 5 + len(pid) + 1 + len(uniq) + 1 + len(key) = 7 + len(pid) + len(uniq) + len(key) bytes. <uniq> is
# $RANDOM: decimal, at most five digits, and the budget uses that FIXED MAXIMUM width so the answer
# does not depend on which value this process drew.
_unleashed_budget_ok() {
    _bo_key="$1"
    _bo_pid="$$"
    _bo_len=$(( 7 + ${#_bo_pid} + 5 + ${#_bo_key} ))
    [ "$_bo_len" -le "$_UNLEASHED_NAME_MAX" ]
}

# ── ST-2 — creating the store ─────────────────────────────────────────────────────────────────────
# PUB-9 E4 orders this in THREE steps and the order is load-bearing: (i) authenticate every EXISTING
# component from `/` downward BEFORE creating anything — with HOME a symlink to /victim and .claude
# absent, an implementation that creates first runs `mkdir "$HOME/.claude"` THROUGH the symlink and
# leaves /victim/.claude behind before reporting `failed`; (ii) create each missing component in turn,
# authenticating the chain through it immediately after; (iii) authenticate the completed chain,
# because a freshly created store can inherit a default ACL that ST-3 refuses.
#
# THE UNIT IS THE CHAIN, NOT THE COMPONENT: ANCHOR-1 accepts a leading run of uid-0 system-prefix
# components and requires euid ownership from the trust anchor downward, so whether a given uid is
# acceptable depends on what came before it in the walk.
#
# `mkdir` is invoked BY ABSOLUTE PATH, as every read probe already is (PUB-11). ST-3 requires bases/
# to be exactly 0700 and forbids ever repairing or deleting it, so a `mkdir` from a PATH entry that
# did not apply `-m 700` would create a store EVERY READER REFUSES FOREVER.
_unleashed_create_store() {
    _cs_store="$1"
    _cs_mid="${_cs_store%/*}"          # ${HOME}/.claude/unleashed-mail
    _cs_top="${_cs_mid%/*}"            # ${HOME}/.claude

    _unleashed_nearest_existing "$_cs_store"
    _unleashed_auth_chain "$_UNLEASHED_NEAREST" || return 1        # (i)

    for _cs_d in "$_cs_top" "$_cs_mid" "$_cs_store"; do            # (ii)
        if [ -d "$_cs_d" ]; then
            continue                   # authenticated by (i), or by an earlier iteration
        fi
        if /bin/mkdir -m 700 "$_cs_d" 2>/dev/null; then
            :
        elif [ -d "$_cs_d" ]; then
            # Lost the race to a concurrent publisher. ST-2: a component that already exists is used
            # as it stands, and "already exists" includes exists BY THE TIME THE mkdir RAN — a mkdir
            # that fails because the component now exists is NOT a failure to create it. Measured:
            # `mkdir -m 700 d` on an existing d exits 1 with `File exists` in both shells, so the
            # exit status ALONE cannot tell the two cases apart and the re-test is what distinguishes
            # them.
            :
        else
            return 1                   # E4: a missing component genuinely cannot be created
        fi
        _unleashed_auth_chain "$_cs_d" || return 1
    done

    _unleashed_auth_chain "$_cs_store" || return 1                 # (iii)
    return 0
}
