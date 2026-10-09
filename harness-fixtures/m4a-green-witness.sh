#!/usr/bin/env bash
# COREDEV-2780 M4a, cell 17 — the GREEN witness. It exists only to be observed `clean` once
# `trunk-check` is a required context, and is closed as soon as that state is recorded. NEVER MERGED.
set -euo pipefail

witness="m4a-green"
printf '%s\n' "${witness}"
