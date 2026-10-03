#!/usr/bin/env bash
# COREDEV-2850 probe (cell 2): ONE new lint finding, bound by file, line and column. Never merged.
set -euo pipefail
target="${1:-.}"
ls $target
