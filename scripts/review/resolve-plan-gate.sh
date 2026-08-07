#!/usr/bin/env bash
# Resolve THE plan for a named feature and verify its Combined-verdict artifact. Fail-closed.
#
# WHY THIS EXISTS
# This was a ~135-line compound block in `skills/implement/SKILL.md`: it defined functions, branched,
# built arrays and shelled out to `tr`/`ls`, so it matched none of that skill's `allowed-tools` Bash
# shapes. Claude Code decomposes a compound command and wants a rule per subcommand, so the one block
# that MUST run before any implementation prompted for permission every time (PR #63 review; the
# scoping in gap 1 is what exposed it). As one committed script the fence reduces to a single granted
# call — and the guards below become testable, which as inline shell they never were.
#
# Usage:
#   resolve-plan-gate.sh <plan>     # the feature name or plan path, as ONE operand (documented form)
#   resolve-plan-gate.sh            # ...or on STDIN, for callers that already bind a heredoc
#
# THE ARGUMENT ARRIVES ON STDIN, NEVER AS AN ARGV OPERAND. Callers bind it with a QUOTED heredoc, so
# shell metacharacters in it (`"`, `$( )`, backticks) are LITERAL data that never reaches a shell in
# syntax position (MAJ-9). Splicing it into argv would re-open the original injection: the slash
# argument is substituted TEXTUALLY into the skill body before the shell runs.
#
# Exit: 0 gate passed · 1 refused / no plan / gate failed · 2 ambiguous, the caller must name one.
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SCRIPTS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)" || exit 1

# ONE OPERAND, OR STDIN. The operand form is now the documented one and STDIN is kept for callers that
# already bind a heredoc.
#
# WHY THE HEREDOC IS NO LONGER THE RECIPE (PR #63 recheck, P1). The STDIN design was chosen so shell
# metacharacters in the argument stayed literal data, and it does that. What it could not defend was the
# DELIMITER: `implement` spliced `$ARGUMENTS` into a `<<'"'"'UM_IMPLEMENT_ARG_EOF'"'"'` body, so an argument
# containing a line exactly equal to that delimiter closed the heredoc early and every line after it was
# parsed as a shell command — before this script existed to guard anything. A quoted delimiter disables
# expansion inside the body; it does not stop the body from ending. No quoting fixes that, because the
# fault is textual substitution of untrusted text into shell SYNTAX, one level above the quoting.
#
# The recipe therefore no longer substitutes the argument at all: the caller resolves the plan itself
# and passes the concrete path here, where the containment below governs it exactly as before.
if [ "$#" -gt 1 ]; then
    echo "REFUSED: takes at most one operand — the plan name or path." >&2
    exit 1
elif [ "$#" -eq 1 ]; then
    ARG="$1"
else
    # `$(cat)` strips trailing newlines exactly as the heredoc command substitution it replaced did, so a
    # well-formed single-line argument is unchanged and a crafted multi-line one still shows its newline.
    ARG="$(cat)"
fi

# A slash argument is single-line; reject a multi-line value (only a crafted paste produces one, and it is
# never a valid feature name or plan path) so a newline cannot smuggle a second line past the heredoc.
if [ "$ARG" != "${ARG%%$'\n'*}" ]; then
    echo "REFUSED: multi-line argument is not a valid plan name/path." >&2
    exit 1
fi

# ANCHOR AT THE WORKTREE ROOT, REMEMBERING WHERE THE CALLER STOOD (PR #63 recheck, P2).
# Everything below — the direct file test, the glob fallback, the `ls` in the no-match diagnostic, and
# the `.verdicts` lookup inside `review-verdict.py verify` — used to be evaluated against the CALLER'S
# working directory. From a repository subdirectory the documented root-relative operand
# `docs/planning/X_PLAN.md` therefore existed nowhere, fell through to name resolution, and the glob
# (evaluated in the same wrong place) matched nothing: a valid, gated plan reported as "No plan
# matches". Reproduced from a `sub/` directory. A guard that refuses correct work is one an operator
# switches off. FAILS CLOSED outside a worktree: with no repository there is no docs/planning to
# contain plans to, and falling back to the working directory is the exact bug being fixed.
CALLER_PWD="$PWD"
TOP="$(git rev-parse --show-toplevel 2>/dev/null)" || TOP=""
if [ -z "$TOP" ]; then
    echo "REFUSED: not inside a Git worktree — the Plan Review Gate anchors at the repository root." >&2
    exit 1
fi
TOP="$(CDPATH='' cd -- "$TOP" && pwd -P)" || exit 1
cd "$TOP" || exit 1

# Repo-relative identity of $1 interpreted against base $2, or non-zero. Only the PARENT is resolved
# physically — a symlinked LEAF must still reach `_contained` below, which refuses it with the specific
# uncontained diagnostic rather than a generic miss. Same helper shape as `isolated-agy-review.sh`,
# for the same reason: an operand's meaning must not depend on where the caller happened to stand.
resolve_in_repo() {
    local candidate="$1" base="$2" parent leaf
    case "$candidate" in /*) ;; *) candidate="$base/$candidate" ;; esac
    [ -f "$candidate" ] || return 1
    parent="$(CDPATH='' cd -- "$(dirname -- "$candidate")" 2>/dev/null && pwd -P)" || return 1
    leaf="$parent/$(basename -- "$candidate")"
    case "$leaf" in
        "$TOP"/*) printf '%s\n' "${leaf#"$TOP"/}" ;;
        *) return 1 ;;
    esac
}

# PHYSICAL CONTAINMENT — the one guard, used by BOTH resolution branches.
#
# The plan's BYTES must live under <repo-root>/docs/planning. Everything else here is convenience; this
# is the tracked-plan mandate (CLAUDE.md) and it has been bypassed four different ways, each time
# because the previous guard checked a PROXY for containment instead of containment:
#   /tmp/OUTSIDE_PLAN.md                        -> `-f` accepts any existing file      (textual fix)
#   docs/planning/../../evil/OUTSIDE_PLAN.md    -> `..` wears the prefix               (added `..` case)
#   docs/planning/EVIL_PLAN.md -> /tmp/...      -> a symlink wears the prefix          (added realpath)
#   docs/planning -> /tmp/...                   -> a symlinked ROOT: realpath'ing the BASE resolved it
#                                                  through the same link, so both sides matched
# Resolve the plan, but anchor the base to the PHYSICAL repo root and do NOT resolve the base itself —
# then a symlinked docs/planning cannot launder its own target. (codex, #41 review; all reproduced.)
_contained() {
    python3 - "$1" <<'PYEOF'
import os, sys
root = os.path.realpath(".")
base = os.path.join(root, "docs", "planning")   # deliberately NOT realpath'd
real = os.path.realpath(sys.argv[1])
sys.exit(0 if real == base or real.startswith(base + os.sep) else 1)
PYEOF
}
_refuse_uncontained() {
    { echo "REFUSED: '$1' does not live under <repo-root>/docs/planning."
      echo "A tracked plan's BYTES must be in the repo — a symlink, a ../ escape, or a symlinked"
      echo "docs/planning is not a tracked plan (CLAUDE.md's Plan Review Gate)."; } >&2
    exit 1
}

PLAN=""
# The operand is tried against the CALLER'S directory first — the invoker is the authority on what it
# meant — then against the root, so the documented root-relative spelling works from anywhere. Both
# resolving to DIFFERENT files is refused rather than silently decided by branch order. This also
# accepts an absolute in-repo path, which the old prefix test refused as "not a tracked plan" purely
# for its spelling — the same absolute-spelling false refusal already fixed in the capture harness.
FROM_CALLER="$(resolve_in_repo "$ARG" "$CALLER_PWD")" || FROM_CALLER=""
FROM_ROOT="$(resolve_in_repo "$ARG" "$TOP")" || FROM_ROOT=""
if [ -n "$FROM_CALLER" ] && [ -n "$FROM_ROOT" ] && [ "$FROM_CALLER" != "$FROM_ROOT" ]; then
    { echo "AMBIGUOUS: '$ARG' names $FROM_CALLER from the invoking directory and $FROM_ROOT from the"
      echo "repository root — name one of them unambiguously."; } >&2
    exit 2
fi
REL="${FROM_CALLER:-$FROM_ROOT}"
if [ -n "$REL" ]; then
    case "$REL" in
        docs/planning/*PLAN*.md) ;;
        *) { echo "REFUSED: '$ARG' is not a tracked plan."
             echo "The Plan Review Gate requires a repo-relative docs/planning/*PLAN*.md (CLAUDE.md)."; } >&2
           exit 1 ;;
    esac
    _contained "$REL" || _refuse_uncontained "$ARG"
    PLAN="$REL"
elif [ -f "$ARG" ]; then
    # It EXISTS by the root/absolute interpretation but does not resolve into this repository — a
    # /tmp plan, or a `..` spelling that escapes. Keep the explicit refusals these spellings have
    # always produced, rather than letting an out-of-tree file fall through to fuzzy name matching.
    _p="${ARG#./}"
    case "$_p" in
        docs/planning/*PLAN*.md) _refuse_uncontained "$ARG" ;;
        *) { echo "REFUSED: '$ARG' is not a tracked plan."
             echo "The Plan Review Gate requires a repo-relative docs/planning/*PLAN*.md (CLAUDE.md)."; } >&2
           exit 1 ;;
    esac
else
    # One tr, not two: `[:upper:]`->`[:lower:]` positionally, then ` `/`.`/`-` -> `_` (gemini, #41).
    # THE DASH MUST COME LAST: in a tr SET a dash BETWEEN two characters is a RANGE, so ` -.` meant
    # space(32)..dot(46) — 15 characters — and `/implement "c+dark"` then matched C-DARK_PLAN.md, i.e.
    # the gate verified a plan nobody named (gemini, #41 review). Trailing `-` is a literal.
    KEY=$(printf '%s' "$ARG" | tr '[:upper:] .-' '[:lower:]___')
    # THE CONTENT GUARD IS LOAD-BEARING AND IS THE LOOP'S GATE — do not "simplify" it to `-n "$KEY"`.
    # `[[ "$b" == *""* ]]` matches EVERY plan, so an empty KEY resolves to the first plan on disk: a
    # fail-OPEN. `-n` alone is not enough either — `tr` maps ' ', '-' and '.' to '_' BEFORE this runs, so
    # ARGUMENTS=" " yields KEY="_", which is non-empty and `*_*` matches most plan filenames. `*[!_]*`
    # states the real property ("not composed solely of what tr just mapped to _") and is
    # locale-independent, where the earlier `*[a-z0-9]*` was an ASCII proxy that refused `日本語`.
    # EXACT STEM matches are collected separately from mere SUBSTRING matches. A unique substring used
    # to resolve silently as identity — `/implement mode` picked DARK_MODE_PLAN.md — so a coincidental
    # fragment could satisfy the gate against a plan the user did not name (full review, #41). Now a
    # full/exact feature name always wins, and a pure substring must be named explicitly.
    #
    # For each plan, three stems the arg may exactly equal:
    #   full   — the basename minus the `_PLAN.md` suffix            (coredev_2328_reviewer_status_capture)
    #   desc   — full minus a leading `coredev_<digits>_` ticket     (reviewer_status_capture)
    #   ticket — the `coredev_<digits>` prefix alone                 (coredev_2328)
    EXACT=(); SUBSTR=()
    if [[ "$KEY" == *[!_]* ]]; then
        for p in docs/planning/*PLAN*.md; do
            [ -e "$p" ] || continue                 # unmatched glob stays literal -> skip
            # THE SAME CONTAINMENT GUARD AS THE DIRECT BRANCH. Without it `/implement evil` selected
            # `docs/planning/EVIL_PLAN.md -> /tmp/OUTSIDE_PLAN.md` and returned GATE OK — the direct
            # branch refused that exact symlink while the glob branch happily took it (codex, #41
            # review; reproduced). Filtering here so an out-of-tree symlink cannot even reach a match.
            _contained "$p" || continue
            # `b` is the NORMALIZED basename: tr already mapped ` `/`.`/`-` -> `_`, so `.md` is `_md`
            # here and the suffix to strip is `_plan_md`, not `_plan.md`.
            b=$(printf '%s' "${p##*/}" | tr '[:upper:] .-' '[:lower:]___')
            full="${b%_plan_md}"
            desc="$full"; ticket=""
            case "$full" in
                coredev_[0-9]*)
                    rest="${full#coredev_}"      # 2328_reviewer_status_capture
                    ticket="coredev_${rest%%_*}" # coredev_2328
                    desc="${rest#*_}"            # reviewer_status_capture
                    ;;
            esac
            if [ "$KEY" = "$full" ] || [ "$KEY" = "$desc" ] || [ "$KEY" = "$ticket" ]; then
                EXACT+=("$p")
            elif [[ "$b" == *"$KEY"* ]]; then
                SUBSTR+=("$p")
            fi
        done
    fi
    # Prefer EXACT: a full name wins over any coincidental substring.
    if [ "${#EXACT[@]}" -gt 1 ]; then
        { echo "AMBIGUOUS: '$ARG' exactly names ${#EXACT[@]} plans — name a path:"; printf '%s\n' "${EXACT[@]}"; } >&2
        exit 2
    elif [ "${#EXACT[@]}" -eq 1 ]; then
        PLAN="${EXACT[0]}"
    elif [ "${#SUBSTR[@]}" -ge 1 ]; then
        # A PURE SUBSTRING is NOT identity. Do not auto-resolve it — the gate would then verify a plan
        # the user only partially named. Require an exact name (full review, #41).
        { echo "No plan is named exactly '$ARG'. Did you mean one of these? Name it exactly:"
          printf '%s\n' "${SUBSTR[@]}"; } >&2
        exit 2
    fi
    # No EXACT and no SUBSTR -> empty PLAN -> the fail-closed branch below.
fi
if [ -z "$PLAN" ]; then
    # exit 1, and to stderr: the old form fell through with `ls`'s status, which is 0 whenever ANY
    # plan exists — so a FAILED resolution reported success.
    { echo "No plan matches '$ARG'. Available:"; ls docs/planning/*PLAN*.md 2>/dev/null; } >&2
    exit 1
fi

echo "Plan: $PLAN"
# Verify the persisted, digest-bound verdict for THAT plan.
exec python3 "${SCRIPTS_DIR}/review-verdict.py" verify --plan "$PLAN"
