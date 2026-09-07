#!/usr/bin/env bash
# DELIBERATELY LINT-CLEAN, and that is the point.
#
# COREDEV-2780 §7 cell 2, the RETARGET case. This PR is opened against `main`, observed, then
# RETARGETED to `alpha` with `gh pr edit --base alpha`. The head SHA never changes; only the base
# does. What must change is the RANGE `trunk check` is given, because the range is resolved as
# HEAD^1 of the recomputed `refs/pull/N/merge` — the NEW base's tip.
#
# The file is clean so that BOTH runs are green and the only thing that differs between them is the
# resolved range, printed by the `guard-empty-diff` step as `changed:` lines. A red run would work
# too but would confound "the range moved" with "a finding appeared".
#
# It is shellcheck-clean on purpose (quoted expansion, braced reference), so trunk genuinely lints
# it and reports no findings — as opposed to a file type with no applicable linters, where a green
# run would mean "checked nothing", the exact false pass this ticket exists to prevent.
set -euo pipefail
target="${1:?usage: m3-retarget-probe.sh <target>}"
printf 'retarget probe: %s\n' "${target}"
