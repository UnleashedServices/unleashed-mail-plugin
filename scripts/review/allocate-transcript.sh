#!/usr/bin/env bash
# shellcheck shell=bash

set -euo pipefail

usage() {
    printf 'usage: allocate-transcript.sh <ticket> <round> <reviewer>\n' >&2
}

if [ "$#" -ne 3 ]; then
    usage
    exit 2
fi

ticket="$1"
round_value="$2"
reviewer="$3"
if [ -z "$ticket" ] || [ -z "$round_value" ] || [ -z "$reviewer" ]; then
    usage
    exit 2
fi

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
LIB="${UNLEASHED_LIB_DIR:-$(CDPATH='' cd -- "${SCRIPT_DIR}/../lib" && pwd)}"

# shellcheck source=scripts/lib/context.sh
. "${LIB}/context.sh"

if repo_hash="$(context_repo_hash)"; then
    :
else
    status="$?"
    exit "$status"
fi

if allocator_output="$(
    python3 "${SCRIPT_DIR}/../pty-capture.py" \
        --allocate \
        --repo-hash "$repo_hash" \
        --ticket "$ticket" \
        --round "$round_value" \
        --reviewer "$reviewer"
)"; then
    :
else
    status="$?"
    exit "$status"
fi

if [[ "$allocator_output" == *$'\n'* || "$allocator_output" != UNLEASHED_TRANSCRIPT=?* ]]; then
    printf 'allocate-transcript: allocator returned an invalid marker stream\n' >&2
    exit 1
fi

printf '%s\n' "$allocator_output"
