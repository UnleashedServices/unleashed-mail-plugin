#!/usr/bin/env bash
# Run a gemini (`agy`) plan review WITHOUT letting it write to the tree under review (COREDEV-2607).
#
# THE DEFECT THIS EXISTS FOR
# `agy` is not read-only, and there is no flag that makes it so. On 2026-07-29 a plan review
# IMPLEMENTED the plan instead of reviewing it: 6 shipped scripts modified, 5 files created, including
# a stray `marketplace.json` at the repo root. It emitted no `VERDICT:` line, so the gate failed closed
# — the fortunate failure mode — but the edits persisted and had to be reverted by hand. The concurrent
# `codex` review recorded "Concurrent implementation edits appeared during review, so citations were
# rechecked against committed HEAD"; its verdict was trustworthy only because it independently
# re-anchored. Nothing in the gate design required that.
#
# FLAGS THAT DO NOT WORK — TESTED, DO NOT RE-TRY THEM
# Each was run against a scratch dir with the prompt "Create a file named PROOF.txt … Do it now.":
#   agy (no flags)            -> file created
#   agy --mode plan           -> file created
#   agy --sandbox             -> file created
#   agy --sandbox --mode plan -> file created
# All four exited 0. `--help` describes `--mode` as "agent execution mode (accept-edits, plan)" and
# `--sandbox` as "Run in a sandbox with terminal restrictions enabled"; neither restricts file writes
# in print mode. This is the asymmetry with `codex`, which the gate already runs `-s read-only`.
#
# SO: ISOLATE, DO NOT CONSTRAIN. The reviewer is pointed at a disposable detached checkout of the
# reviewed commit, and the real working tree is asserted unchanged afterwards. A tree mutation FAILS
# the round rather than being cleaned up silently — the same rule `AGENT_CONTRACTS.md` §2 step 0b
# applies to the author, applied to the reviewer.
#
# Usage: isolated-agy-review.sh <prompt-file> <allocated-path> [timeout-seconds] [plan-file]
#   <prompt-file>  path to the review prompt, RELATIVE TO THE REPO ROOT (e.g. .agy-prompt-2597r4.md)
#   <allocated-path>  exact reserved transcript leaf received from allocate-transcript.sh
# Exit: 0 review captured · 1 setup/prompt failure · 3 round VOID — the reviewer mutated the working
#       tree, modified the round's staged basis (plan or prompt) inside the disposable checkout, or
#       wrote anything else there (a reviewer in agent mode is the COREDEV-2607 signature)
set -uo pipefail

# NO BYTECODE FROM THIS HARNESS, ANYWHERE (COREDEV-2650; extended after PR #81 review).
# The reviewer subshell below sets this too — that is the load-bearing one, because a `.pyc` inside
# the DISPOSABLE checkout is read as reviewer tampering and voids the round. Setting it here as well
# covers this script's OWN python helpers (containment.py, stage-bound-plan.py, stage-prompt.py),
# which write into the LIVE checkout's `scripts/review/__pycache__/`.
# STATED PRECISELY, because the review comment that prompted this inferred more than holds: a live-tree
# `.pyc` canNOT void a round. `__pycache__/` is gitignored (.gitignore:38) and `tree_fingerprint`
# hashes HEAD + `status --porcelain` + TRACKED content + git metadata, so an ignored untracked file is
# invisible to it. Measured: the live fingerprint was byte-identical before, during and after a
# synthetic `.pyc` was planted. This is hygiene and defence-in-depth, not a fix for an observed void.
export PYTHONDONTWRITEBYTECODE=1


_sha256() { python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }

[ "$#" -ge 2 ] || { echo "usage: $0 <prompt-file> <allocated-path> [timeout]" >&2; exit 1; }
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
. "${SCRIPT_DIR}/tree-fingerprint.sh"
PLUGIN_WRITER="${SCRIPT_DIR}/../pty-capture.py"
PROMPT_REL="$1"
OUT="$2"
TIMEOUT="${3:-1800}"   # must EXCEED agy --print-timeout (28m=1680s) or the wrapper kills a live run
PLAN_REL="${4-}"       # optional: the plan the run is BOUND to (see the copy below)
# Reviewer model. Switched from gemini-3.1-pro to gemini-3.6-flash-high after that arm failed to emit a
# parseable verdict in 5 of 6 rounds (invented tokens REJECTED/PASS, two degenerations leaking
# system-prompt tokens, two runs that implemented the plan instead of reviewing it). Those are token-level
# and agent-mode failures, not reasoning failures — but they void rounds either way. `agy models` lists the
# valid names; the isolation harness and the $HOME leak monitor stay regardless of model, because the
# implement-instead-of-review failure comes from agy's agent mode, not from the model.
#
# For three months this comment described that switch while the line below still read
# `gemini-3.1-pro-high`, so every wrapper round ran the arm documented as failing (PR #63 review, item
# 8; deep review, P2). The default now matches the rationale, and `test_doc_gates` pins the two to each
# other so they cannot drift apart again. Replacing this arm entirely is planned separately
# (`docs/planning/KIMI_REVIEW_ARM_PLAN.md`) — a future plan is not a fix for the arm shipping today.
MODEL="${MODEL:-gemini-3.6-flash-high}"

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO="$PWD"
# CAPTURED BEFORE THE `cd`. `bind-prompt.py` accepted the plan operand relative to the CALLER'S
# directory; this script then changed to the repository root and reinterpreted the same string there,
# so a plan the binder had just accepted became unreadable here (PR #63 recheck, P2 — see the
# resolution below).
CALLER_PWD="$PWD"
cd "$REPO" || exit 1
[ -r "$PROMPT_REL" ] || { echo "prompt not readable: $REPO/$PROMPT_REL" >&2; exit 1; }

# Repo-relative identity of $1 interpreted against base $2, or non-zero if it does not exist there or
# resolves outside the repository. Only the PARENT is resolved through `pwd -P`: a symlinked leaf must
# still reach the readability check rather than be laundered into a clean-looking relative path here.
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

# --- before: fingerprint the real tree --------------------------------------------------------
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

# --- disposable detached checkout at the exact reviewed commit --------------------------------
SHA="$(git rev-parse HEAD)"
# A PRIVATE clone, never a linked worktree — a linked worktree's `.git` points into the maintainer's
# real repository and every git operation the reviewer runs lands there (see disposable_checkout in
# tree-fingerprint.sh; adversarial verification, PR #67 pass 6).
disposable_checkout "$REPO" "$SHA" "$SCR/tree" \
    || { echo "could not create the private review checkout" >&2; exit 1; }
TREE="$SCR/tree"

# COPY THE BOUND PLAN INTO THE CHECKOUT. The tree above is detached at HEAD, so `agy` reads the
# COMMITTED plan — while `bind-prompt.py` hashed the WORKING-TREE plan into `<transcript>.plan`. With
# uncommitted edits, which is the normal state during the documented review iteration, the transcript
# approved the committed version and the artifact recorded it as evidence for the edited one: two
# correct digests describing different bytes (PR #63 recheck, P1).
#
# Copying rather than refusing keeps the iterate-then-review loop working, and it makes the binding
# TRUE rather than merely checkable — the reviewer now reads exactly the bytes the sidecar attests to.
if [ -n "$PLAN_REL" ]; then
    # NORMALIZE AGAINST THE CALLER, THEN THE ROOT. Two spellings reached this line and each broke a
    # different way:
    #   * an ABSOLUTE in-repo path pasted into "$TREE/$PLAN_REL" built a nested destination like
    #     `$TREE/Users/…/docs/planning/X.md` while the rewritten prompt still pointed `agy` at
    #     `$TREE/docs/planning/X.md`, so the copy landed where the reviewer never looks and it read the
    #     COMMITTED plan again — the very defect the copy was added to fix; and
    #   * a CALLER-RELATIVE path such as `../docs/planning/X_PLAN.md` passed from `scripts/`, which
    #     `bind-prompt.py` had already accepted, died here as "plan not readable" because this script had
    #     `cd`'d to the root first. Reproduced from `scripts/` (PR #63 recheck, P2).
    #
    # Caller-relative is tried FIRST because the binder is the authority on what was bound. Root-relative
    # stays as a fallback so callers that pass a root-relative path from a subdirectory keep working, and
    # the ambiguous case — both exist and name DIFFERENT files — is refused rather than silently resolved
    # to whichever branch happens to be tested first.
    PLAN_OPERAND="$PLAN_REL"
    FROM_CALLER="$(resolve_in_repo "$PLAN_OPERAND" "$CALLER_PWD")" || FROM_CALLER=""
    FROM_ROOT="$(resolve_in_repo "$PLAN_OPERAND" "$REPO")" || FROM_ROOT=""
    if [ -n "$FROM_CALLER" ] && [ -n "$FROM_ROOT" ] && [ "$FROM_CALLER" != "$FROM_ROOT" ]; then
        echo "ambiguous plan operand: '$PLAN_OPERAND' names $FROM_CALLER from the caller's directory" >&2
        echo "and $FROM_ROOT from the repository root — pass an absolute path" >&2
        exit 1
    fi
    PLAN_REL="${FROM_CALLER:-$FROM_ROOT}"
    [ -n "$PLAN_REL" ] \
        || { echo "plan not readable, or outside the repository: $PLAN_OPERAND" >&2; exit 1; }
    [ -r "$PLAN_REL" ] || { echo "plan not readable: $REPO/$PLAN_REL" >&2; exit 1; }
    # The staging destination is built by a DESCRIPTOR WALK inside the python below, not a `mkdir -p` +
    # `open("$TREE/$PLAN_REL")`. the detached checkout MATERIALIZES committed tree entries — so if
    # HEAD records the plan path as a SYMLINK (or any parent as one), the checkout recreates that link,
    # and a plain open followed it to overwrite an outside victim. Reproduced: HEAD carries
    # `docs/planning/X_PLAN.md -> /outside/victim`, the live worktree replaces it with a real plan, and
    # staging clobbered the victim (PR #63 recheck, P1). Every component is now opened O_NOFOLLOW and
    # the leaf is unlinked-then-O_EXCL-created, so no symlink is ever traversed.
    # STAGE THE BINDER'S SNAPSHOT, not the live path. `bind-prompt.py` kept the exact bytes it hashed
    # in `<transcript>.planbytes`; copying the working-tree path instead re-read a mutable source, so a
    # plan edited after binding and restored before synthesis could reach the reviewer while both the
    # sidecar and the final digest described the restored bytes. The old `cmp` re-opened that same path
    # and so proved only that two reads agreed at copy time (PR #63 recheck, P1).
    PLAN_SNAPSHOT="${OUT}.planbytes"
    # STAGING IS THE SHARED HELPER, not inline python — the codex arm ran in the live tree because the
    # gemini fix lived only here, and a rule in one script is a rule the next entrypoint will not have.
    # `stage-bound-plan.py` authenticates the snapshot against its `.plan` record, reads it once through
    # an O_NOFOLLOW descriptor, and writes it through a no-follow descriptor walk (a materialized symlink
    # leaf or parent is refused). It prints the digest of what it staged, which anchors the post-run
    # basis check below (PR #63 recheck, P1).
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

# --- authenticate the bound prompt, rewrite paths, prepend the guard, stage it ------------------
# ONE SHARED HELPER, for the same reason plan staging is shared: this used to be `sed` plus inline
# python in each harness, and the two arms drifted. `stage-prompt.py` authenticates the snapshot
# against `<transcript>.promptsha256` BEFORE transforming it (the staging path never compared them, so
# a snapshot rewritten after binding and restored before synthesis had the reviewer read substituted
# instructions), substitutes the repository path as LITERAL BYTES (the `sed "s#…#…#"` expression was
# assembled from a path, so a checkout containing `#` aborted every capture), prepends the read-only
# guard, enforces the size floor, and writes through a no-follow descriptor walk (PR #63 recheck, P1+P2).
#
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
    --tree "$TREE" --rel "$PROMPT_REL" --repo "$REPO" --guard --min-bytes 1000)" || exit 1

# --- run --------------------------------------------------------------------------------------
# The reserved leaf must be EMPTY. It is created 0-byte by the allocator, and nothing but this
# capture may write it. A non-empty leaf means it has already been used, and reusing it is how a
# failed round gets reported as an approval: `--allocated` deliberately omits O_CREAT (to preserve
# the reservation), so before PR #63 it also omitted truncation, and a shorter second write left the
# first round's tail — including its `VERDICT:` line — for the `tail -1` below to find. Reproduced:
# a 19-byte failed round left 55 bytes reading `VERDICT: APPROVE`. pty-capture.py now ftruncates, so
# this is defence in depth; it also catches the case where the leaf was written by something else
# entirely. Refuse rather than clean: deleting the leaf would destroy the reservation, and silently
# overwriting would hide that the caller reused a path it should have re-allocated.
if [ -s "$OUT" ]; then
    echo "refusing to reuse a non-empty reserved leaf: $OUT" >&2
    echo "(it already holds $(wc -c < "$OUT" | tr -d ' ') bytes — allocate a fresh leaf for this round)" >&2
    exit 1
fi
# The baseline: everything the HARNESS put in the tree (the prompt, the staged plan), by CONTENT.
# Anything different after the run is the reviewer's doing. NOT `git status`, which the reviewer
# controls (see disposable_fingerprint), and NOT `|| true` — a probe that fails is not a clean tree
# (adversarial verification, PR #67 pass 6: this baseline still carried the fallback the post-review
# probe below had lost in PR #63).
if ! TREE_BASELINE="$(disposable_fingerprint "$TREE")"; then
    echo "GATE FAILED — could not fingerprint the disposable checkout before the review" >&2; exit 1
fi

# Preserve the allocator's reserved leaf for pty-capture.py --allocated to open.
# stdout only is silenced; pty-capture's STDERR passes through so its diagnostics (timeout notice,
# allocated-leaf/launch refusal reasons, capture-write failures) reach the operator instead of the
# round ending as a bare EXIT=n with the reason discarded (2026-08-17 audit, AF-10). The transcript
# itself still goes to $OUT, not to either stream.
# PYTHON BYTECODE IS NOT A REVIEWER MUTATION (COREDEV-2650; it voided COREDEV-2711 r1 and r8).
# A reviewer that IMPORTS a repo module to reproduce a measured claim — the single best thing a
# reviewer can do, and what this round's prompt asks for — makes CPython write `__pycache__/*.pyc`
# beside the source. This harness fingerprints the disposable checkout afterwards, so that
# bytecode read as `ROUND VOID: the reviewer left edits … COREDEV-2607 signature` and threw away a
# valid review whose finding was independently confirmed by another arm. At r8 it voided TWO of
# the three arms this way — agy and kimi — leaving the round resting on codex alone. The check
# is right and
# keeps its teeth; what was wrong is letting the artefact exist. Suppress it at the source rather
# than excluding a path from the manifest — an exclusion is a blacklist a real mutation could hide
# behind, and `scripts/__pycache__/` is exactly where it would hide.
( cd "$TREE" && export PYTHONDONTWRITEBYTECODE=1 && python3 "$PLUGIN_WRITER" --timeout "$TIMEOUT" --allocated "$OUT" -- \
    agy --add-dir "$TREE" --model "$MODEL" --print-timeout 28m -p "Read and follow $TREE/$PROMPT_REL" ) >/dev/null
RC=$?

# --- after: the assertion that would have caught COREDEV-2607 --------------------------------
if ! AFTER="$(tree_fingerprint "$REPO")"; then
    { echo "GATE FAILED — could not fingerprint the live checkout after the review (round"
      echo "void). A reviewer that breaks the checkout must not pass as a clean tree."; } >&2
    exit 3
fi
if [ "$BEFORE" != "$AFTER" ]; then
    echo "GATE FAILED — the reviewer MUTATED the working tree during the review:" >&2
    # The first line of the fingerprint is the pre-run HEAD; `$'\n'`, not `\n` — inside a pattern `\n`
    # is a literal `n` (measured: it stripped at the first `n` of the status text).
    tree_fingerprint_report "$REPO" "$BEFORE_STATUS" "${BEFORE%%$'\n'*}"
    echo "(round is void — see COREDEV-2607)" >&2
    exit 3
fi

# THE ROUND'S BASIS MUST SURVIVE THE ROUND (PR #63 recheck, P1). A reviewer that rewrote the staged
# plan and then emitted `VERDICT: APPROVE` produced a valid-looking capture of a review of DIFFERENT
# bytes, while synthesis validates only the `.plan` record against the live plan — which nobody
# touched. And the status diff below could not even SEE it: `git status --porcelain` is STATUS-line
# based, and the staged plan is already `M` in the baseline, so re-modifying its content changes
# nothing the diff compares. Reproduced both ways. So the basis files are verified by CONTENT against
# the digests recorded before launch — the same digest the `.plan` record attests to, now checked at a
# third point in the round's life.
if [ -n "$PLAN_REL" ]; then
    ACTUAL_PLAN_SHA="$(_sha256 "$TREE/$PLAN_REL" 2>/dev/null)" || ACTUAL_PLAN_SHA="unreadable"
    if [ "$ACTUAL_PLAN_SHA" != "$EXPECTED_PLAN_SHA" ]; then
        { echo "GATE FAILED — the STAGED PLAN was modified during the review (round void):"
          echo "(staged ${EXPECTED_PLAN_SHA}, post-run ${ACTUAL_PLAN_SHA} — the transcript reviewed"
          echo "bytes the binding does not attest to; see COREDEV-2607 for why this voids the round)"; } >&2
        exit 3
    fi
fi
ACTUAL_PROMPT_SHA="$(_sha256 "$TREE/$PROMPT_REL" 2>/dev/null)" || ACTUAL_PROMPT_SHA="unreadable"
if [ "$ACTUAL_PROMPT_SHA" != "$PROMPT_TREE_SHA" ]; then
    echo "GATE FAILED — the assembled PROMPT was modified during the review (round void)" >&2
    exit 3
fi
# ANY other write inside the disposable copy voids the round too — no longer a note. Writing files is
# the COREDEV-2607 signature (a reviewer in agent mode, implementing instead of reviewing), and a
# review produced that way is untrustworthy whether or not the copy is discarded afterwards. The
# earlier informational form existed because comparing against HEAD reported the HARNESS'S OWN staged
# input as a reviewer write — a detector that cries wolf on its own inputs is one nobody reads. That
# concern is solved by the POST-STAGING BASELINE, not by softening the verdict: everything the harness
# placed is in the baseline, so anything beyond it is the reviewer's doing, and it fails the round.
# (The old form also excluded the prompt's basename from the diff — which would have HIDDEN a reviewer
# tampering with any file sharing that name. The content checks above cover the prompt now.)
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
    { echo "GATE FAILED — the reviewer left edits inside the disposable checkout (round void — agent-mode"
      echo "behaviour, the COREDEV-2607 signature):"
      printf '%s\n' "$TREE_BASELINE" | diff - <(printf '%s\n' "$TREE_AFTER") | sed 's/^/  /' || :; } >&2
    exit 3
fi

BYTES_OUT="$(wc -c 2>/dev/null < "$OUT" | tr -d ' ')"
# Anchored, never a loose `grep VERDICT:` — that matches the prompt's own echoed template in a
# timed-out transcript and reads as a real verdict.
VERDICT="$(grep -aE '^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$' "$OUT" 2>/dev/null | tail -1)"
echo "EXIT=$RC BYTES=${BYTES_OUT:-0} TREE=clean VERDICT=${VERDICT:-<none — FAILED REVIEW>}"
# RETURN IT. The status was captured in `RC` and then thrown away by the successful `echo` above, so a
# stub exiting 23 printed `EXIT=23 … FAILED REVIEW` while this script — and `capture-gemini-review.sh`
# with it — reported success. The caller then could not tell a completed review from an auth, model or
# timeout failure, which is exactly the distinction the gate depends on (PR #63 recheck, P2). The
# mutation detector above keeps its own separate exit path; this only propagates the CAPTURE status.
exit "$RC"
