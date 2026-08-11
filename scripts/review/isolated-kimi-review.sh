#!/usr/bin/env bash
# Run a Kimi (K3) plan review WITHOUT letting it write to the tree under review, and PROVE the
# reasoning effort it actually used.
#
# WHY THIS EXISTS AT ALL, AND WHY IN THE REPO
# An earlier copy of this harness ran for a whole campaign out of a session scratchpad under /tmp and
# was destroyed when the scratchpad was cleared, along with the plan validator. This repo already
# carries that lesson for review transcripts; a harness that gates a plan is at least as load-bearing,
# so it lives beside `isolated-agy-review.sh` and `isolated-codex-review.sh`.
#
# WHY ISOLATION
# `kimi` is an agent and can write. The defect this guards is COREDEV-2607: on 2026-07-29 a plan review
# IMPLEMENTED the plan instead of reviewing it — 6 shipped scripts modified, 5 files created. The
# reviewer therefore sees a DISPOSABLE detached checkout of the reviewed commit, and the real working
# tree is asserted unchanged afterwards. A mutation FAILS the round rather than being cleaned up.
#
# WHY THE EFFORT ASSERTION
# `--output-format stream-json` does NOT expose the effort a run used, and the config sets it in TWO
# places (a per-model `default_effort` and a global `[thinking] effort`), so a hand-edit to one is
# invisible. The tier a run really used is recorded in that session's wire log as `thinkingEffort`.
# A review whose tier cannot be asserted is not evidence about that tier, so this exits 4 rather than
# reporting a number it never verified.
#
# THE FAILURE MODES THIS ENCODES, EACH MEASURED ON THIS TICKET
#   * A round is VOID if the worktree changes during the review. Kimi's round-37 run tripped this
#     because the author committed while it was still reading — the harness was right and the author
#     was wrong. Hold tree edits until every arm has landed.
#   * Kimi reads the commit it is GIVEN. When a prompt pinned a stale commit, kimi noticed the
#     mismatch, trusted the pin over the working tree, and reviewed a three-round-old document. The
#     BASIS line below records what was staged; it does NOT prove what the reviewer chose to read.
#   * `EXIT=1` with a large transcript is usually the billing-cycle quota (a 403 in the tail), not a
#     review failure. Check the tail before treating it as one.
#
# Usage: isolated-kimi-review.sh <prompt-file> <out-transcript> <commit> [timeout-seconds]
#   <prompt-file>  path to the review prompt, RELATIVE TO THE REPO ROOT
#   <out-transcript>  where to write the transcript — NEVER under /tmp
# Exit: 0 captured · 1 setup failure · 3 round VOID (tree or staged basis mutated) · 4 effort unassertable
set -uo pipefail

[ "$#" -ge 3 ] || { echo "usage: $0 <prompt-file> <out-transcript> <commit> [timeout]" >&2; exit 1; }
PROMPT_REL="$1"; OUT="$2"; COMMIT="$3"; TIMEOUT="${4:-3300}"
PLAN_REL="docs/planning/COREDEV-2617_PLUGIN_STATE_BASE_DIR_PLAN.md"

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repo" >&2; exit 1; }
cd "$REPO" || exit 1
[ -r "$PROMPT_REL" ] || { echo "prompt not readable: $REPO/$PROMPT_REL" >&2; exit 1; }

case "$OUT" in
    /tmp/*|/private/tmp/*)
        echo "refusing to write the transcript under /tmp — macOS has destroyed campaign transcripts there" >&2
        exit 1 ;;
esac
mkdir -p "$(dirname -- "$OUT")" || exit 1

_sha256() { python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }

# Fingerprint the REAL tree before handing anything to the reviewer.
BEFORE="$(git status --porcelain | LC_ALL=C sort | shasum -a 256 | cut -d' ' -f1)"

TREE="$(mktemp -d "${TMPDIR:-/tmp}/kimi-review.XXXXXX")" || exit 1
cleanup() {
    git worktree remove --force "$TREE/tree" >/dev/null 2>&1 || :
    rm -rf "$TREE" 2>/dev/null || :
}
trap cleanup EXIT INT TERM HUP

git worktree add --detach "$TREE/tree" "$COMMIT" >/dev/null 2>&1 || {
    echo "worktree add failed for $COMMIT" >&2; exit 1; }
[ -r "$TREE/tree/$PLAN_REL" ] || { echo "plan missing in the staged checkout" >&2; exit 1; }
BASIS="$(_sha256 "$TREE/tree/$PLAN_REL")"

( cd "$TREE/tree" && timeout "$TIMEOUT" kimi -p "$(cat "$REPO/$PROMPT_REL")" --output-format text ) > "$OUT" 2>&1
STATUS=$?

AFTER_BASIS="$(_sha256 "$TREE/tree/$PLAN_REL" 2>/dev/null || echo MISSING)"
AFTER="$(git status --porcelain | LC_ALL=C sort | shasum -a 256 | cut -d' ' -f1)"

if [ "$BEFORE" != "$AFTER" ]; then
    echo "ROUND VOID: the real worktree was mutated during the review" >&2
    echo "  (if that was your own commit, the round is still void — hold edits until every arm lands)" >&2
    exit 3
fi
if [ "$BASIS" != "$AFTER_BASIS" ]; then
    echo "ROUND VOID: the reviewer modified the staged plan — COREDEV-2607 signature" >&2
    exit 3
fi

# Effort assertion, from the wire log of the session this run created. `session.resume_hint` in the
# transcript names the session; the newest wire.jsonl is the one this run just wrote.
WIRE="$(ls -t "$HOME"/.kimi-code/sessions/*/session_*/agents/main/wire.jsonl 2>/dev/null | head -1)"
EFFORTS=""
[ -n "$WIRE" ] && EFFORTS="$(grep -o '"thinkingEffort":"[a-z]*"' "$WIRE" 2>/dev/null \
    | sed 's/.*:"//;s/"//' | LC_ALL=C sort -u | tr '\n' ',')"

printf 'EXIT=%s BYTES=%s TREE=clean BASIS=%s EFFORT=%s\n' \
    "$STATUS" "$(wc -c < "$OUT" | tr -d ' ')" "${BASIS:0:12}" "${EFFORTS:-UNKNOWN}"

if [ "$EFFORTS" != "max," ]; then
    echo "EFFORT NOT ASSERTED AS max (saw: ${EFFORTS:-none}) — this run is not evidence about max" >&2
    exit 4
fi
exit "$STATUS"
