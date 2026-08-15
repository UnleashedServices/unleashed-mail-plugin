# shellcheck shell=bash
# COREDEV-2617 §7 step 3d — the publisher: publish-then-scan, and PUB-9's ORDERED exits.
#
# Requires plugin-state-auth.sh, plugin-state-store.sh and plugin-state-reader.sh.
#
# A publisher runs where the plugin-data variable IS set: it records its base value in the store so
# that a shell which never receives that variable — a git hook, an ordinary terminal — can discover
# it. It then SCANS and reports what it saw. It does not refuse: it has already resolved.
#
# PUB-9's exits are ORDERED, first match wins, and every one maps to exactly one state:
#   E0 publishing disabled                      -> none
#   E1 HOME unusable                            -> failed   (no ${HOME} path composed at all)
#   E2 own value not publishable, or its TARGET CHAIN fails  -> failed  (no key derived, nothing opened)
#   E3 the NAME_MAX budget cannot be satisfied  -> failed
#   E4 the store chain cannot be made or fails  -> failed
#   E5 no unique transient name in THREE total attempts      -> failed
#   E6 the transient write or the rename fails  -> failed
#   E7 otherwise: scan, and take the ordered POST-SCAN exits
# and the post-scan exits, also ordered:
#   P1 our own entry is missing   -> failed      (whether or not this process wrote it)
#   P2 else any entry fails auth  -> stale
#   P3 else two or more authenticate -> conflict
#   P4 else created / current, per the write decision
#
# Every scratch variable carries its function's prefix (FAM-5).

# ── TMP-1 — the transient's name ──────────────────────────────────────────────────────────────────
# `.pub.<pid>.<uniq>.<key>`. `$$` ALONE IS NOT SUFFICIENT: concurrent subshells inherit the same `$$`
# in both shells, so two of them would collide on one name. `<uniq>` is `$RANDOM`, which both target
# shells provide, and the budget uses its fixed five-digit maximum width.
#
# AT MOST THREE ATTEMPTS IN TOTAL — the initial one plus two retries — and then the publisher stops.
# "Three attempts" is the whole budget, not three retries after an initial try.
_unleashed_transient_name() {
    _tn_store="$1"; _tn_key="$2"; _tn_try=0
    while [ "$_tn_try" -lt 3 ]; do
        _tn_try=$(( _tn_try + 1 ))
        _tn_p="$_tn_store/.pub.$$.${RANDOM}.$_tn_key"
        # TYPE BEFORE OPEN, then `set -C`. Both are required and neither is sufficient: `set -C`
        # alone BLOCKS on a FIFO rather than failing (measured, rc=124 in both shells), and the
        # presence test alone loses the race against a concurrent create. Their composition still
        # leaves the window P-5 states — absent at the test, a FIFO before the redirect — which no
        # POSIX shell redirect can close, and which is an accepted limit of the same-uid trust model
        # rather than a requirement this rule states and does not meet.
        if [ -L "$_tn_p" ] || [ -e "$_tn_p" ]; then
            continue
        fi
        _UNLEASHED_TRANSIENT="$_tn_p"
        return 0
    done
    return 1                                          # E5
}

# ── P-4 — create the transient at exactly 0600, without touch, chmod or mktemp ────────────────────
# `(umask 077; : > "$tmp")` in a SUBSHELL so the caller's umask is untouched. The mode is READ BACK,
# because a POSIX default ACL on the parent supplies permissions umask does not mask — reachable on
# a store ACL-3 accepts — and a transient that is not exactly 0600 becomes an entry that is not.
_unleashed_write_transient() {
    _wt_p="$1"; _wt_value="$2"
    ( set -C; umask 077; : > "$_wt_p" ) 2>/dev/null || return 1
    printf '%s\n' "$_wt_value" > "$_wt_p" 2>/dev/null || return 1
    _u_stat "$_wt_p" || return 1
    [ "$_U_MODE" = 0600 ] || return 1                 # E6: readback, not assumption
    return 0
}

# ── The publish ───────────────────────────────────────────────────────────────────────────────────
# $1 = the store directory, $2 = this process's base value. Sets the four protocol variables.
# PUB-11: the MUTATING commands have both streams redirected and their outcome observed through their
# EXIT STATUS, never their output; they are invoked BY ABSOLUTE PATH, as every read probe is.
_unleashed_publish() {
    _pb_store="$1"; _pb_value="$2"; _pb_wrote=0
    _u_probes_reset                                  # no inherited probe state is honoured

    # E2 — the precondition. The publisher publishes NOTHING unless its own value satisfies TGT-1 in
    # full AND the TARGET CHAIN authenticates. No key is derived and nothing is opened under the
    # store, so this exit is the one that composes no store path at all.
    case "$_pb_value" in
        /*) : ;;
        *)  _unleashed_pub_failed "the plugin-data base is not an absolute path"; return 0 ;;
    esac
    case "$_pb_value" in
        */) _unleashed_pub_failed "the plugin-data base has a trailing slash"; return 0 ;;
    esac
    # A LITERAL newline in a variable, not `$(printf '\n')`: command substitution STRIPS trailing
    # newlines, so that spelling is the EMPTY STRING, the pattern degenerates to `*`, and EVERY value
    # is rejected as containing a newline. P-3a's note in plugin-state-auth.sh records this trap and
    # it was reproduced here anyway — measured, the first version of this function refused a perfectly
    # ordinary base path in both shells.
    _pb_nl='
'
    case "$_pb_value" in
        *"$_pb_nl"*) _unleashed_pub_failed "the plugin-data base contains a newline"; return 0 ;;
    esac
    if [ ! -d "$_pb_value" ] || [ -L "$_pb_value" ]; then
        _unleashed_pub_failed "the plugin-data base is not an existing directory"; return 0
    fi
    if ! _unleashed_auth_chain "$_pb_value"; then
        _unleashed_pub_failed "the plugin-data base's chain does not authenticate"; return 0
    fi

    _unleashed_key "$_pb_value"
    _pb_key="$_UNLEASHED_KEY"

    # E3 — the budget, BEFORE the store is created: the probe comes first so a name that cannot fit
    # never causes a directory to be made.
    # Two DIFFERENT failures, reported as what they are: a probe that could not answer is not a
    # name that is too long, and a user cannot act on the wrong one (codex, PR #67). Both fail
    # closed; the over-budget line carries the attempted and allowed lengths so the path can be
    # shortened by a known amount.
    if ! _unleashed_name_max "$_pb_store"; then
        _unleashed_pub_failed "the NAME_MAX probe (/usr/bin/getconf) failed or returned a non-number"; return 0
    fi
    if ! _unleashed_budget_ok "$_pb_key"; then
        _unleashed_pub_failed "the entry name would be $(( 7 + ${#$} + 5 + ${#_pb_key} )) bytes; NAME_MAX here is $_UNLEASHED_NAME_MAX"; return 0
    fi

    # E4 — the store chain, in PUB-9's three-step order. Ancestors this publisher already created are
    # LEFT IN PLACE on failure: ST-3/ST-4 forbid the plugin removing directories, and a rollback
    # would be the plugin deleting paths it does not own. They are 0700 and euid-owned, so leaving
    # them is harmless and the next run reuses them.
    if ! _unleashed_create_store "$_pb_store"; then
        _unleashed_pub_failed "the plugin-state store could not be created or does not authenticate"
        return 0
    fi

    _pb_entry="$_pb_store/base.$_pb_key"

    # PUB-7's write-or-skip decision. When the existing entry ALREADY authenticates, a publish writes
    # NOTHING — PUB-4 and row 1's mtime case require zero writes on the `current` path.
    if _unleashed_auth_entry "$_pb_entry"; then
        _pb_wrote=0
    else
        # ST-7 — if anything is PRESENT at base.<key> and is not a regular non-symlink file, the
        # publisher does not attempt repair: it writes nothing and reports `failed`.
        if { [ -L "$_pb_entry" ] || [ -e "$_pb_entry" ]; } && [ ! -f "$_pb_entry" ]; then
            _unleashed_pub_failed "the plugin-state entry exists and is not a regular file"; return 0
        fi
        _unleashed_transient_name "$_pb_store" "$_pb_key" || {
            _unleashed_pub_failed "no unique transient name within three attempts"; return 0; }
        if ! _unleashed_write_transient "$_UNLEASHED_TRANSIENT" "$_pb_value"; then
            /bin/rm -f "$_UNLEASHED_TRANSIENT" >/dev/null 2>&1      # ST-7: best effort
            _unleashed_pub_failed "the plugin-state transient could not be written at 0600"; return 0
        fi
        # The rename is what makes publication atomic — `mv` in the SAME directory, so no reader that
        # has already seen the entry observes it absent.
        if ! /bin/mv -f "$_UNLEASHED_TRANSIENT" "$_pb_entry" >/dev/null 2>&1; then
            /bin/rm -f "$_UNLEASHED_TRANSIENT" >/dev/null 2>&1
            _unleashed_pub_failed "the plugin-state entry could not be published"; return 0
        fi
        _pb_wrote=1
    fi

    # E7 — publish-then-scan. The publisher applies the SAME ordered reader rules, then the ordered
    # POST-SCAN exits. It does not refuse: it reports what it saw.
    _unleashed_scan_store "$_pb_store"
    if ! _unleashed_auth_entry "$_pb_entry"; then
        _unleashed_pub_failed "this process's own plugin-state entry is missing or unusable"   # P1
    elif [ "$_UNLEASHED_FAILED" -gt 0 ]; then
        _unleashed_pub_state stale                                                             # P2
    elif [ "$_UNLEASHED_AUTHED" -ge 2 ]; then
        _unleashed_pub_state conflict                                                          # P3
    elif [ "$_pb_wrote" = 1 ]; then
        _unleashed_pub_state created                                                           # P4
    else
        _unleashed_pub_state current                                                           # P4
    fi
    return 0
}

# A publisher has already resolved, so its base is the value it holds — the state it reports is about
# the STORE, not about its own resolution.
_unleashed_pub_state() {
    _UNLEASHED_BASE_RESOLVED="$_pb_value"
    _UNLEASHED_BASE_OK=1
    _UNLEASHED_BASE_SOURCE='host-env'
    _UNLEASHED_POINTER_STATE="$1"
    return 0
}

# PUB-11: every publish exit that reports `failed` emits EXACTLY ONE bounded line on stderr naming
# which exit it was; every other outcome is silent. A publisher that observes `conflict` or `stale`
# emits nothing — the one-diagnostic-per-refusal rules are READER rules, and a publisher has already
# resolved.
_unleashed_pub_failed() {
    _UNLEASHED_BASE_RESOLVED="$_pb_value"
    _UNLEASHED_BASE_OK=1
    _UNLEASHED_BASE_SOURCE='host-env'
    _UNLEASHED_POINTER_STATE=failed
    printf 'unleashed-mail: plugin-state publication failed: %s\n' "$1" >&2
    return 0
}
