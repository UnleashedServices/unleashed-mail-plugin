#!/usr/bin/env bash
# COREDEV-2879 §5 step 6 — the live retarget WITNESS. Opened green against main, then retargeted to
# alpha so the deciding trunk-check run can be observed: its action-echoed upstream must be on
# alpha's first-parent chain, or the run must be red naming STALE MERGE REF. NEVER MERGED.
set -euo pipefail

witness="coredev-2879-retarget"
printf '%s\n' "${witness}"
