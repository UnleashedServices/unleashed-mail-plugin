#!/usr/bin/env bash
# DELIBERATELY LINT-FAILING. This file exists to be REJECTED by `trunk check` on a PR targeting
# `alpha`, proving the required context can actually fail there — not merely that it went green
# while failures were suppressed.
#
# It is never merged: the check runs on the PR head, so no broken commit reaches a protected branch.
# The unquoted expansion below is shellcheck SC2086, and the brace-less reference is SC2250.
set -euo pipefail
target=$1
echo $target
