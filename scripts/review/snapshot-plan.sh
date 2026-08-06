#!/usr/bin/env bash
# Record a plan's pre-review digest — the contained entrypoint for the gate's `snapshot` step.
#
# WHY THIS EXISTS
# `brainstorm` is model-invocable and granted
# `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py snapshot *)`, so the MODEL chose the
# `--plan` operand and nothing bounded it: any existing file on disk was accepted, and the snapshot
# sidecar was written beside it. Together with the same hole in `persist-verdict.sh` that walked
# straight past the skill's apparent `Write(docs/planning/**)` boundary, with no user gesture
# (PR #63 recheck, P1 — reproduced against a file under `/tmp`).
#
# The containment lives here rather than in `review-verdict.py` because that tool has a designed and
# tested behaviour for a plan outside any git repo, and it is also the maintainer's own CLI. What has
# to be bounded is the pre-approved path the model can enter — which is exactly the entrypoint-only
# grant policy this release enforces elsewhere.
#
# Usage:
#   snapshot-plan.sh <plan>       # a non-symlink regular file under docs/planning in THIS repository
#
# Exit: review-verdict's status, or 1 on a refused operand. Nothing is written on refusal.
set -uo pipefail

die() { printf 'snapshot-plan: %s\n' "$1" >&2; exit 1; }

PLAN="${1-}"
[ -n "$PLAN" ] || die "name the plan to snapshot, e.g. docs/planning/COREDEV-1234_PLAN.md"
[ "$#" -eq 1 ] || die "takes exactly one operand — the plan; got $#"

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SCRIPTS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)" || exit 1

# The SAME module `bind-prompt.py` and `audit-codex.sh` use. Sharing it is the point: the identical
# hole has now been found on four separate entrypoints, each time because the rule lived in one script.
python3 "${SCRIPT_DIR}/containment.py" --tool "snapshot-plan" --label "plan" \
    --under "docs/planning" -- "$PLAN" >/dev/null \
    || die "refusing to snapshot: the plan is not an in-repo docs/planning file (see above)"

exec python3 "${SCRIPTS_DIR}/review-verdict.py" snapshot --plan "$PLAN"
