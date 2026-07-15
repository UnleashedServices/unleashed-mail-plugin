#!/bin/bash
# Classify each UNRESOLVED reviewer's on-disk capture for swift-reviewer's Step 5 (COREDEV-2490).
#
# THE INVARIANT THIS ENFORCES
# ---------------------------
#   A persisted capture may RATCHET a review toward caution. It may NEVER CERTIFY completion.
#   Only an in-session reviewer report can produce a clean pass.
#
# Why the fix lives here (the consumer) and not in the capture producer: `context_latest_round_dir`
# (scripts/lib/context.sh:130, `[ -f "$d/$agent.json" ] || continue`) selects the highest round holding
# the agent's findings and SILENTLY SKIPS rounds where the agent wrote nothing — so absence at round N
# resolves to PRESENCE at round N-1. The reader never sees the round the producer failed in, so no
# producer-side artifact can signal anything on the very path where the producer is failing. Three
# designs died learning that (see docs/planning/COREDEV-2490_*).
#
# INPUT   stdin, one agent name per line: the reviewers the orchestrator DOES hold an in-session report
#         (with a readable `Status:`) for. The script classifies the COMPLEMENT — everyone you did NOT
#         name. **Empty stdin therefore means "I hold nothing" and classifies ALL FIVE.**
#
#         THE POLARITY IS DELIBERATE AND LOAD-BEARING (COREDEV-2490 adversarial pass). The first cut
#         took the UNRESOLVED names on stdin, which made the DEFAULT "nothing to act on": an attacker
#         reproduced a clean pass for a reviewer that never ran, without touching this script at all —
#         `printf '%s\n' "${UNRESOLVED[@]}"` with an unset array emits ONE BLANK LINE, the loop skips
#         it, and the script exits 0. Worse, `UNRESOLVED` could never be assigned: every Bash block is
#         a fresh shell, so a name the model reasoned out cannot survive into the pipeline.
#         Inverting it makes silence FAIL CLOSED: saying nothing classifies everyone, and only a
#         POSITIVE, in-band assertion of what you hold can shrink the roster. That is the design's own
#         principle — positive attribution — finally applied to its own invocation.
# OUTPUT  RATCHET     <agent> BLOCKED <blockerDescription>   (the ONLY trusted on-disk state)
#         UNATTRIBUTED <agent> <reason>                      (EVERYTHING else)
#         REMAINING    <agent> <files...>                    (a parsed PARTIAL's structural scope;
#                                                             information to preserve, NOT attribution)
# EXIT    0 nothing to act on (ONLY when you named all five as held) · 2 ratchet lines only ·
#         3 at least one UNATTRIBUTED (dominates) · 4 a HELD name was unknown or duplicated
#         Any OTHER exit, or output that disagrees with the exit code, is a FAILURE the caller must
#         treat as missing-reviewer uncertainty — never as "nothing to act on". Exit 4 exists so a
#         TYPO in a held name can never silently resolve a reviewer: it routes to the same
#         uncertainty branch as any unexpected exit.
#
# This script NEVER prints TRUST. By design no on-disk artifact earns it.
set -uo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
CTX="$_DIR/lib/context.sh"
[ -f "$CTX" ] || CTX="scripts/lib/context.sh"
# shellcheck source=scripts/lib/context.sh
. "$CTX"

# The reviewer allowlist, mirroring capture.py VALID_AGENTS (:53-59). An unknown name is REJECTED and
# never path-joined — the roster is model-assembled, so it is untrusted input.
_VALID="security-reviewer concurrency-reviewer ux-perf-reviewer accessibility-auditor prompt-review"

BASE="$(context_reviews_dir)/$(context_branch_slug "$(context_branch)")"
SAW_RATCHET=0
SAW_UNATTRIBUTED=0

# Read a sidecar ONCE and print `agent<TAB>status<TAB>blockerDescription<TAB>remaining`.
# Prints nothing (exit 1) on ANY failure — an unparseable sidecar is UNATTRIBUTED anyway, so this never
# needs to raise, and the caller treats "no output" as corrupt.
#
# HARDENED at R7 (codex, found BY EXECUTION): the first version checked only existence/readability and
# then ran an UNBOUNDED `json.load` — up to THREE times per sidecar. Pointed at `/dev/zero` it never
# terminated (killed at 1s); a FIFO blocks in `open()`; a huge valid document exhausts memory. A hang is
# not "UNATTRIBUTED", it is the gate wedging, which violates the fail-safe semantics. So:
#   * regular files ONLY  (no FIFO/device/directory), and never follow a symlink
#   * hard size cap BEFORE reading
#   * parse EXACTLY once, with typed validation
_MAX_SIDECAR_BYTES=65536
_read_sidecar() {
    _MAX_SIDECAR_BYTES="$_MAX_SIDECAR_BYTES" python3 - "$1" <<'PY' 2>/dev/null
import json, os, stat as _stat, sys

path = sys.argv[1]
cap = int(os.environ.get("_MAX_SIDECAR_BYTES", "65536"))

# Open ONCE, then validate THAT DESCRIPTOR — never re-resolve the pathname (codex R8).
# The previous version lstat'ed the path and then re-open()ed it: between those two syscalls the file
# can be swapped for a FIFO or a symlink, restoring the blocking/following behaviour the lstat was
# supposed to prevent. A TOCTOU in a capture dir is not hypothetical — the dir is written by hooks
# concurrently with reviews.
#   O_NOFOLLOW  -> refuse a symlink at open() itself
#   O_NONBLOCK  -> a FIFO with no writer returns instead of blocking forever
try:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
except OSError:
    sys.exit(1)
try:
    st = os.fstat(fd)                      # fstat the OPEN fd: no second path resolution
    if not _stat.S_ISREG(st.st_mode):      # FIFO, device, dir -> not a sidecar
        sys.exit(1)
    if st.st_size > cap:                   # bounded BEFORE reading
        sys.exit(1)
    raw = os.read(fd, cap + 1)
    if len(raw) > cap:
        sys.exit(1)
finally:
    os.close(fd)

try:
    # STRICT utf-8 (codex R8): errors="replace" would accept structurally-valid JSON containing invalid
    # UTF-8 rather than classifying it as corrupt, which is not what the contract claims.
    d = json.loads(raw.decode("utf-8"))
except Exception:
    sys.exit(1)
if not isinstance(d, dict):
    sys.exit(1)

def s(key):
    """STRINGS ONLY. Every field the producer persists is a capped string — `_STATUS_FIELDS` values go
    through `cap(redact_pii(field[1]), STATUS_FIELD_CAP)` (capture.py:362). So a list/dict/bool **or a
    number** is malformed input, not something to coerce: an int `remaining` is not a file list, and
    silently str()-ing it would invent a contract the producer never offers (codex R8 — my first fix
    rejected list/dict/bool but still coerced numerics)."""
    v = d.get(key)
    if not isinstance(v, str):
        return ""
    return v.replace("\t", " ").replace("\n", " ").replace("\r", " ").strip()

print("\t".join((s("agent"), s("status"), s("blockerDescription"), s("remaining"))))
PY
}

# Echo a REJECTED name only after stripping control characters. The roster is model-assembled, so a
# name may carry a CR/TAB/escape; printing it raw lets it break the one-directive-per-line grammar
# (`security-reviewer<CR>forged` renders as two lines). It could never CERTIFY — UNATTRIBUTED only ever
# adds work — but the grammar should hold regardless of the input.
_printable() {
    printf '%s' "$1" | tr -d '[:cntrl:]'
}

emit_unattributed() {
    printf 'UNATTRIBUTED %s %s\n' "$(_printable "$1")" "$2"
    SAW_UNATTRIBUTED=1
}

# --- Phase 1: read the HELD names off stdin and validate them -------------------------------------
# A held name must be an exact, known reviewer, named at most once. A typo or a repeat is exit 4 (the
# caller's "any unexpected outcome is uncertainty" branch), never a silent resolution.
HELD=""
BAD_HELD=""
while IFS= read -r held || [ -n "$held" ]; do
    held="${held%$'\r'}"
    held="${held#"${held%%[![:space:]]*}"}"
    held="${held%"${held##*[![:space:]]}"}"
    [ -n "$held" ] || continue
    _ok=0
    for _v in $_VALID; do
        if [ "$_v" = "$held" ]; then _ok=1; break; fi
    done
    if [ "$_ok" -eq 0 ]; then
        BAD_HELD="$BAD_HELD $(_printable "$held")"
        continue
    fi
    # duplicate?
    for _h in $HELD; do
        if [ "$_h" = "$held" ]; then BAD_HELD="$BAD_HELD dup:$held"; _ok=0; break; fi
    done
    [ "$_ok" -eq 1 ] && HELD="$HELD $held"
done

if [ -n "$BAD_HELD" ]; then
    printf 'ROSTER-INPUT-INVALID%s\n' "$BAD_HELD"
    exit 4
fi

# Echo what was consumed, so the transcript records WHICH reviewers were asserted as held rather than
# leaving it to be inferred. An empty list is stated explicitly — it is the fail-closed default.
printf 'ROSTER-INPUT: held =%s\n' "${HELD:- (none)}"

# --- Phase 2: classify the COMPLEMENT -------------------------------------------------------------
for agent in $_VALID; do
    _is_held=0
    for _h in $HELD; do
        if [ "$_h" = "$agent" ]; then _is_held=1; break; fi
    done
    [ "$_is_held" -eq 1 ] && continue
    # $agent comes from $_VALID itself, so it needs no trimming or allowlisting — the untrusted input
    # (the HELD list) was validated in phase 1. This is the other half of inverting the polarity: the
    # names we classify are now OURS, not the model's.
    rd="$(context_latest_round_dir "$BASE" "$agent" 2>/dev/null)"
    if [ -z "$rd" ]; then
        # No round holds this agent's findings at all. The OLD Step-2 loop swallowed exactly this case
        # with `[ -n "$rd" ] || continue`, so a wholly-missing reviewer never reached the gate.
        emit_unattributed "$agent" "no-round-dir"
        continue
    fi

    sc="$rd/$agent.status"
    if [ ! -e "$sc" ]; then
        # Genuinely absent. Covers pre-2328 rounds, a silently failed _write_status, and a deleted
        # sidecar alike. v3 died trying to tell those apart; here they collapse, so the design never
        # asks a question the filesystem cannot answer — all of them are UNATTRIBUTED either way.
        emit_unattributed "$agent" "no-sidecar"
        continue
    fi
    if [ ! -r "$sc" ]; then
        # Present but unreadable (permissions). Distinct reason so an operator can tell a broken box
        # from a missing capture; the DIRECTIVE is identical, so nothing safety-relevant rides on it.
        # (codex R6: the spec listed `unreadable` but the prototype folded it into `no-sidecar`.)
        emit_unattributed "$agent" "unreadable"
        continue
    fi

    # ONE bounded parse per sidecar (R7). No output => unreadable/non-regular/oversized/corrupt.
    if ! _fields="$(_read_sidecar "$sc")" || [ -z "$_fields" ]; then
        emit_unattributed "$agent" "corrupt-sidecar"
        continue
    fi
    sc_agent="${_fields%%$'\t'*}"; _rest2="${_fields#*$'\t'}"
    status="${_rest2%%$'\t'*}";   _rest3="${_rest2#*$'\t'}"
    desc="${_rest3%%$'\t'*}"
    remaining="${_rest3#*$'\t'}"

    if [ -z "$sc_agent" ]; then
        emit_unattributed "$agent" "corrupt-sidecar"
        continue
    fi
    if [ "$sc_agent" != "$agent" ]; then
        # A sidecar claiming a different agent must never speak for this one.
        emit_unattributed "$agent" "agent-mismatch"
        continue
    fi

    if [ "$status" = "BLOCKED" ]; then
        # The ONLY on-disk state that is honoured — and only because BLOCKED cannot be a DOWNGRADE of
        # anything, so acting on it is the sole genuinely monotone move. It ratchets; it never certifies.
        [ -n "$desc" ] || desc="(no blockerDescription recorded)"
        # _printable on $desc too: it and $remaining are the ONLY transcript-derived (i.e.
        # prompt-injectable) fields in the output, and they were the two emitted RAW — ESC/FF
        # survive the producer's newline folding. Neither can CERTIFY (there is no TRUST token to
        # forge, and every forgeable directive only ADDS caution), but the grammar claim above
        # should hold on the paths carrying the MOST attacker-controlled text, not the least.
        printf 'RATCHET %s BLOCKED %s\n' "$agent" "$(_printable "$desc")"
        SAW_RATCHET=1
        continue
    fi

    if [ "$status" = "PARTIAL" ]; then
        # PARTIAL does not certify => UNATTRIBUTED. But its structural scope IS safety information (a
        # held PARTIAL with structural remaining escalates to NEEDS DISCUSSION, swift-reviewer.md:423),
        # and this script is the ONLY sidecar reader — so if it does not forward `remaining`, nothing
        # can preserve it. Discard the ATTRIBUTION, never the INFORMATION.
        emit_unattributed "$agent" "partial-does-not-certify"
        [ -n "$remaining" ] && printf 'REMAINING %s %s\n' "$agent" "$(_printable "$remaining")"
        continue
    fi

    if [ "$status" = "COMPLETE" ]; then
        emit_unattributed "$agent" "complete-does-not-certify"
        continue
    fi

    emit_unattributed "$agent" "unknown-status"
done

# Exit 3 dominates: any single unattributed reviewer means work remains, whatever else was found.
[ "$SAW_UNATTRIBUTED" -eq 1 ] && exit 3
[ "$SAW_RATCHET" -eq 1 ] && exit 2
exit 0
