#!/usr/bin/env bash
# COREDEV-2780 M4a, cell 17 — the RED witness. DELIBERATELY LINT-FAILING, and NEVER MERGED.
#
# `trunk-check` is a required context in ruleset `Control`. This PR exists to be observed, read-only,
# as `blocked` with the blocking check named `trunk-check` — the one observation that verifies the
# ruleset's BEHAVIOUR as an enforcement rather than what it contains.
#
# This commit was made through the GitHub contents API, not a local `git commit`, so the local
# pre-commit trunk gate (which correctly refuses it) was never bypassed with --no-verify.
#
# SC2086 (unquoted expansion) and SC2250 (unbraced reference) are both deliberate.
witness=$1
echo $witness
