#!/usr/bin/env bash
# COREDEV-2780 M4 — the deliberately RED observation on ALPHA under the post-COREDEV-2850 bytes.
# DELIBERATELY LINT-FAILING, and NEVER MERGED. M4 requires a strict green AND a deliberate red
# trunk-check on BOTH bases; alpha's red was last observed under the pre-2850 workflow (#97). This
# PR supplies it under the current bytes, and with trunk-check now required it is observed BLOCKED.
#
# Made through the GitHub contents API, so the local pre-commit trunk gate was never bypassed.
# SC2086 (unquoted expansion) and SC2250 (unbraced reference) are both deliberate.
witness=$1
echo $witness
