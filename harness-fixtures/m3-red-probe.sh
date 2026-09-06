#!/usr/bin/env bash
# DELIBERATELY LINT-FAILING. This file exists to make `trunk-check` go red on a PR that is never
# merged, which is the only way to observe whether the gate is STRICT or merely advisory:
#
#   advisory : Trunk step fails -> job conclusion failure -> WORKFLOW RUN still succeeds
#   strict   : Trunk step fails -> job conclusion failure -> WORKFLOW RUN fails too
#
# A GREEN run cannot tell those apart, because with no findings both conclude success. That is why
# M3 requires a deliberately red run per base and not just a passing one.
#
# SC2086 (unquoted expansion) and SC2250 (unbraced reference) are both deliberate.
probe=$1
echo $probe
