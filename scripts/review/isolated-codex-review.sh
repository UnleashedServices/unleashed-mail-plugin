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
    git worktree remove --force "$SCR/tree" >/dev/null 2>&1
    rm -rf "$SCR"
}
trap cleanup EXIT

BEFORE="$(git status --porcelain)"

SHA="$(git rev-parse HEAD)"
git worktree add --detach "$SCR/tree" "$SHA" >/dev/null 2>&1 \
    || { echo "could not create the review checkout" >&2; exit 1; }
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
    if [ -r "$PLAN_SNAPSHOT" ]; then
        EXPECTED_PLAN_SHA="$(python3 "${SCRIPT_DIR}/stage-bound-plan.py" \
            --tree "$TREE" --rel "$PLAN_REL" --snapshot "$PLAN_SNAPSHOT" --record "${OUT}.plan")" \
            || exit 1
    else
        echo "note: no bound plan snapshot beside the transcript; staging the working-tree plan" >&2
        EXPECTED_PLAN_SHA="$(python3 "${SCRIPT_DIR}/stage-bound-plan.py" \
            --tree "$TREE" --rel "$PLAN_REL" --live "$PLAN_REL")" \
            || { echo "could not place the bound plan in the review checkout" >&2; exit 1; }
    fi
fi

# --- rewrite absolute repo paths in the prompt to point at the checkout ------------------------
mkdir -p "$(dirname "$TREE/$PROMPT_REL")"
sed "s#$REPO#$TREE#g" "$PROMPT_REL" > "$TREE/$PROMPT_REL"
if grep -q "$REPO" "$TREE/$PROMPT_REL"; then
    echo "prompt still references the real worktree after rewrite" >&2; exit 1
fi
BYTES="$(wc -c < "$TREE/$PROMPT_REL" | tr -d ' ')"
[ "$BYTES" -ge 1 ] || { echo "assembled prompt is empty" >&2; exit 1; }
PROMPT_TREE_SHA="$(_sha256 "$TREE/$PROMPT_REL")" || exit 1

# The reserved leaf must be EMPTY (see the gemini harness for the shorter-second-write hazard).
if [ -s "$OUT" ]; then
    echo "refusing to reuse a non-empty reserved leaf: $OUT" >&2
    exit 1
fi
TREE_BASELINE="$(git -C "$TREE" status --porcelain 2>/dev/null || true)"

# --- run codex from INSIDE the checkout, so the plan it opens is the staged, authenticated one ---
# `-s read-only` keeps codex from writing; running in $TREE keeps it from reading the live, swappable
# plan. The prompt text is fed as codex's argument, exactly as capture-codex-review.sh did — only the
# working directory and the plan bytes change.
( cd "$TREE" && python3 "$PLUGIN_WRITER" --timeout "$TIMEOUT" --allocated "$OUT" -- \
    codex exec -c model_reasoning_effort=xhigh -s read-only "$(cat "$TREE/$PROMPT_REL")" ) >/dev/null 2>&1
RC=$?

# --- basis check: the plan and prompt codex read must be unchanged; nothing new may appear -------
AFTER="$(git status --porcelain)"
if [ "$BEFORE" != "$AFTER" ]; then
    echo "GATE FAILED — the reviewer MUTATED the real working tree during the review:" >&2
    diff <(printf '%s\n' "$BEFORE") <(printf '%s\n' "$AFTER") >&2
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
TREE_AFTER="$(git -C "$TREE" status --porcelain 2>/dev/null || true)"
DIRTY="$(printf '%s\n' "$TREE_AFTER" | grep -vxF -- "$TREE_BASELINE" || true)"
if [ -n "$DIRTY" ]; then
    { echo "GATE FAILED — the reviewer WROTE inside the disposable checkout (round void):"
      printf '%s\n' "$DIRTY"; } >&2
    exit 3
fi

BYTES_OUT="$(wc -c < "$OUT" 2>/dev/null | tr -d ' ')"
VERDICT="$(grep -aE '^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$' "$OUT" 2>/dev/null | tail -1)"
echo "EXIT=$RC BYTES=${BYTES_OUT:-0} TREE=clean VERDICT=${VERDICT:-<none — FAILED REVIEW>}"
exit "$RC"
