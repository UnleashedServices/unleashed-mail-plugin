#!/usr/bin/env bash
# Run a codex plan review against an ISOLATED checkout with the bound plan staged (COREDEV-2642, P1).
#
# THE DEFECT THIS EXISTS FOR
# The gemini arm was hardened to review a disposable detached checkout with the authenticated
# `.planbytes` staged in, so a plan edited after binding cannot reach the reviewer. The codex arm never
# got it: `capture-codex-review.sh` ran `codex exec … -s read-only` in the LIVE working tree, and the
# plan file codex opened was the live, mutable one. An A->B->A swap during codex's read window let codex
# review substituted bytes while `.plan` and the live plan both still hashed A, and `review-verdict`
# authenticates only the live plan — so the artifact attested a plan the reviewer never read
# (PR #63 recheck, P1, reproduced end to end). This is the same isolation the gemini arm already had;
# the staging now lives in the SHARED `stage-bound-plan.py` so the two arms cannot drift again.
#
# codex is `-s read-only`, so unlike agy it cannot write the tree — the COREDEV-2607 write hazard does
# not apply. What it needs from isolation is to READ the authenticated bytes, not the swappable live
# file. The basis check afterwards is defence in depth, not the primary guard.
#
# Usage: isolated-codex-review.sh <prompt-file> <allocated-path> [timeout-seconds] [plan-file]
#   <prompt-file>  path to the review prompt, RELATIVE TO THE REPO ROOT (e.g. .codex-prompt-2597r4.md)
#   <allocated-path>  exact reserved transcript leaf received from allocate-transcript.sh
# Exit: 0 review captured · 1 setup/prompt failure · 3 round VOID (the reviewed basis was mutated)
set -uo pipefail

_sha256() { python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }

[ "$#" -ge 2 ] || { echo "usage: $0 <prompt-file> <allocated-path> [timeout] [plan]" >&2; exit 1; }
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
. "${SCRIPT_DIR}/tree-fingerprint.sh"
PLUGIN_WRITER="${SCRIPT_DIR}/../pty-capture.py"
PROMPT_REL="$1"
OUT="$2"
TIMEOUT="${3:-1200}"   # matches capture-codex-review.sh; xhigh reasoning runs to ~12 min
PLAN_REL="${4-}"

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO="$PWD"
CALLER_PWD="$PWD"
cd "$REPO" || exit 1
[ -r "$PROMPT_REL" ] || { echo "prompt not readable: $REPO/$PROMPT_REL" >&2; exit 1; }

# Repo-relative identity of $1 against base $2, or non-zero. Same helper shape as the gemini harness:
# an operand's meaning must not depend on where the caller stood. Only the PARENT is resolved
# physically, so a symlinked leaf still reaches the readability check rather than being laundered.
resolve_in_repo() {
    local candidate="$1" base="$2" parent leaf
    case "$candidate" in /*) ;; *) candidate="$base/$candidate" ;; esac
    [ -e "$candidate" ] || return 1
    parent="$(CDPATH='' cd -- "$(dirname -- "$candidate")" 2>/dev/null && pwd -P)" || return 1
    leaf="$parent/$(basename -- "$candidate")"
    case "$leaf" in
        "$REPO"/*) printf '%s\n' "${leaf#"$REPO"/}" ;;
        *) return 1 ;;
    esac
}

SCR="$(mktemp -d)"
cleanup() {
    rm -rf "$SCR"
}
trap cleanup EXIT

# CONTENT-AWARE, NOT STATUS-CATEGORY-ONLY (PR #63 recheck, P1). `git status --porcelain` emits one
# line per path, so a reviewer editing an ALREADY-DIRTY tracked file left the line byte-identical
# and this comparison — the gate-bearing COREDEV-2607 detector, whose failure VOIDS the round —
# saw nothing. The same defect was found and fixed in `preflight-agy.sh` first; the fix did not
# reach here, so the rule now lives in `tree-fingerprint.sh` and all three source it.
BEFORE_STATUS="$(git status --porcelain)"
if ! BEFORE="$(tree_fingerprint "$REPO")"; then
    echo "GATE FAILED — could not fingerprint the live checkout before the review" >&2
    exit 3
fi

SHA="$(git rev-parse HEAD)"
# A PRIVATE clone, never a linked worktree — a linked worktree's `.git` points into the maintainer's
# real repository and every git operation the reviewer runs lands there (see disposable_checkout in
# tree-fingerprint.sh; adversarial verification, PR #67 pass 6).
disposable_checkout "$REPO" "$SHA" "$SCR/tree" \
    || { echo "could not create the private review checkout" >&2; exit 1; }
TREE="$SCR/tree"

# --- stage the bound plan into the checkout (shared, authenticated, no-follow) ----------------
if [ -n "$PLAN_REL" ]; then
    PLAN_OPERAND="$PLAN_REL"
    FROM_CALLER="$(resolve_in_repo "$PLAN_OPERAND" "$CALLER_PWD")" || FROM_CALLER=""
    FROM_ROOT="$(resolve_in_repo "$PLAN_OPERAND" "$REPO")" || FROM_ROOT=""
    if [ -n "$FROM_CALLER" ] && [ -n "$FROM_ROOT" ] && [ "$FROM_CALLER" != "$FROM_ROOT" ]; then
        echo "ambiguous plan operand: '$PLAN_OPERAND' names $FROM_CALLER from the caller's directory" >&2
        echo "and $FROM_ROOT from the repository root — pass an absolute path" >&2
        exit 1
    fi
    PLAN_REL="${FROM_CALLER:-$FROM_ROOT}"
    [ -n "$PLAN_REL" ] || { echo "plan not readable, or outside the repository: $PLAN_OPERAND" >&2; exit 1; }
    [ -r "$PLAN_REL" ] || { echo "plan not readable: $REPO/$PLAN_REL" >&2; exit 1; }
    PLAN_SNAPSHOT="${OUT}.planbytes"
    # THE BOUND SNAPSHOT IS MANDATORY (PR #63 recheck, P1). `bind-prompt.py` writes `.planbytes` and
    # `.plan` together, so absence is tampering, not legacy — and the fallback it used to take quietly
    # re-read the LIVE, mutable plan. That made `rm` the cheapest attack on the strongest binding in the
    # chain: bind plan A, delete the snapshot, point the live plan at B, and the reviewer read B while
    # `review-verdict` (which requires `.plan` and never reads `.planbytes`) approved A.
    #
    # The requirement is UNCONDITIONAL. It was first scoped to captures carrying a `.launch` record, on
    # the theory that a direct or legacy call had no binder run — but this harness only ever invokes
    # `pty-capture --allocated`, which itself refuses a leaf whose `.launch` is absent or malformed. The
    # scoped condition was therefore true in every run that could complete, and the live-plan fallback
    # was unreachable: a weaker path nobody could take, waiting for an edit to re-expose it.
    if [ ! -r "$PLAN_SNAPSHOT" ]; then
        echo "GATE FAILED — no bound plan snapshot beside the transcript: ${PLAN_SNAPSHOT}" >&2
        echo "(the binder writes it with .plan; absence means it was removed. Re-capture the round.)" >&2
        exit 1
    fi
    EXPECTED_PLAN_SHA="$(python3 "${SCRIPT_DIR}/stage-bound-plan.py" \
        --tree "$TREE" --rel "$PLAN_REL" --snapshot "$PLAN_SNAPSHOT" --record "${OUT}.plan")" \
        || exit 1
fi

# --- authenticate the bound prompt, rewrite paths, stage it ------------------------------------
# The SAME shared helper the gemini arm uses (see its comment for the two defects this closes: the
# unauthenticated snapshot re-read, and the `sed` expression assembled from a path that aborted every
# capture on a checkout containing `#`). No `--guard` here: codex runs `-s read-only`, so the
# read-only instruction the gemini guard supplies is enforced by the sandbox instead of by prose.
# `--max-bytes` is the AUTHORITATIVE argv-cap check: the capture wrapper's pre-allocation check measures
# the RAW prompt, and path substitution grows it, so this — measuring the assembled bytes that actually
# reach `codex exec` as a single argument — is what must hold. 120 KiB leaves headroom under Linux's
# 128 KiB `MAX_ARG_STRLEN` (PR #63 recheck).
# THE PROMPT BINDING IS MANDATORY, exactly as the plan snapshot is (PR #63 recheck, P1). This branched
# on the sidecar's presence and staged the snapshot UNAUTHENTICATED when it was absent — the same
# "absent means unchecked" fail-open, reachable by one `rm`. `bind-prompt.py` writes `.prompt` and
# `.promptsha256` together and `pty-capture --allocated` refuses a leaf without a `.launch`, so no run
# that could complete ever needed the fallback.
if [ ! -r "${OUT}.promptsha256" ]; then
    echo "GATE FAILED — no prompt binding beside the transcript: ${OUT}.promptsha256" >&2
    echo "(the binder writes it with .prompt; absence means it was removed. Re-capture the round.)" >&2
    exit 1
fi
PROMPT_TREE_SHA="$(python3 "${SCRIPT_DIR}/stage-prompt.py" \
    --snapshot "$PROMPT_REL" --record "${OUT}.promptsha256" \
    --tree "$TREE" --rel "$PROMPT_REL" --repo "$REPO" --min-bytes 1 --max-bytes 122880)" || exit 1

# The reserved leaf must be EMPTY (see the gemini harness for the shorter-second-write hazard).
if [ -s "$OUT" ]; then
    echo "refusing to reuse a non-empty reserved leaf: $OUT" >&2
    exit 1
fi
# By CONTENT, and fail closed — not `git status`, which the reviewer controls, and not `|| true`
# (see disposable_fingerprint; adversarial verification, PR #67 pass 6).
if ! TREE_BASELINE="$(disposable_fingerprint "$TREE")"; then
    echo "GATE FAILED — could not fingerprint the disposable checkout before the review" >&2; exit 1
fi

# --- run codex from INSIDE the checkout, so the plan it opens is the staged, authenticated one ---
# `-s read-only` keeps codex from writing; running in $TREE keeps it from reading the live, swappable
# plan. The prompt text is fed as codex's argument, exactly as capture-codex-review.sh did — only the
# working directory and the plan bytes change.
# `--` ends option parsing so the prompt is always a positional: the codex arm stages the RAW prompt
# (no --guard prefix — the sandbox enforces read-only instead of prose), so a prompt file that opens
# with a Markdown bullet ("- item") would otherwise be parsed as a flag and fail the round after a
# leaf was allocated and the checkout built (2026-08-17 audit, AF-11).
# stdout only is silenced; pty-capture's stderr diagnostics pass through (AF-10) — see the agy arm.
( cd "$TREE" && python3 "$PLUGIN_WRITER" --timeout "$TIMEOUT" --allocated "$OUT" -- \
    codex exec -c model_reasoning_effort=xhigh -s read-only -- "$(cat "$TREE/$PROMPT_REL")" ) >/dev/null
RC=$?

# --- basis check: the plan and prompt codex read must be unchanged; nothing new may appear -------
if ! AFTER="$(tree_fingerprint "$REPO")"; then
    { echo "GATE FAILED — could not fingerprint the live checkout after the review (round"
      echo "void). A reviewer that breaks the checkout must not pass as a clean tree."; } >&2
    exit 3
fi
if [ "$BEFORE" != "$AFTER" ]; then
    echo "GATE FAILED — the reviewer MUTATED the real working tree during the review:" >&2
    # The first line of the fingerprint is the pre-run HEAD; `$'\n'`, not `\n` — inside a pattern `\n`
    # is a literal `n` (measured: it stripped at the first `n` of the status text).
    tree_fingerprint_report "$REPO" "$BEFORE_STATUS" "${BEFORE%%$'\n'*}"
    exit 3
fi
if [ -n "$PLAN_REL" ]; then
    ACTUAL_PLAN_SHA="$(_sha256 "$TREE/$PLAN_REL" 2>/dev/null)" || ACTUAL_PLAN_SHA="unreadable"
    if [ "$ACTUAL_PLAN_SHA" != "$EXPECTED_PLAN_SHA" ]; then
        echo "GATE FAILED — the STAGED PLAN was modified during the review (round void)" >&2
        exit 3
    fi
fi
ACTUAL_PROMPT_SHA="$(_sha256 "$TREE/$PROMPT_REL" 2>/dev/null)" || ACTUAL_PROMPT_SHA="unreadable"
if [ "$ACTUAL_PROMPT_SHA" != "$PROMPT_TREE_SHA" ]; then
    echo "GATE FAILED — the assembled PROMPT was modified during the review (round void)" >&2
    exit 3
fi
# A FAILED STATUS IS NOT A CLEAN TREE (PR #63 recheck, P2). `|| true` turned a `git status` failure
# into an EMPTY string, and comparing empty against the non-empty baseline yields an empty `DIRTY` —
# so a shell-capable reviewer that removed or corrupted the checkout's `.git` file broke the very
# detector meant to catch it and the round returned 0 with `VERDICT: APPROVE`. The basis files can be
# byte-identical throughout, so nothing else notices. Any non-zero status here VOIDS the round.
if ! TREE_AFTER="$(disposable_fingerprint "$TREE")"; then
    { echo "GATE FAILED — could not re-read the disposable checkout after the review (round"
      echo "void). A reviewer that breaks the checkout must not pass as a clean tree."; } >&2
    exit 3
fi
if [ "$TREE_BASELINE" != "$TREE_AFTER" ]; then
    { echo "GATE FAILED — the reviewer left edits inside the disposable checkout (round void):"
      printf '%s\n' "$TREE_BASELINE" | diff - <(printf '%s\n' "$TREE_AFTER") | sed 's/^/  /' || :; } >&2
    exit 3
fi

BYTES_OUT="$(wc -c 2>/dev/null < "$OUT" | tr -d ' ')"
VERDICT="$(grep -aE '^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$' "$OUT" 2>/dev/null | tail -1)"
echo "EXIT=$RC BYTES=${BYTES_OUT:-0} TREE=clean VERDICT=${VERDICT:-<none — FAILED REVIEW>}"
exit "$RC"
