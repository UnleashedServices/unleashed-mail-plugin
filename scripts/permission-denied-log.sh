#!/usr/bin/env bash
# PermissionDenied diagnostic log (Item 10, COREDEV-2325).
#
# Observe-only audit of AUTO-MODE permission-classifier denials (NOT manual user denials,
# NOT the Item-3 sensitive-file guard's `ask` prompts — those emit `ask`, not `deny`).
# Logs the `tool_name` plus a SANITIZED, capped denial `reason` (free-text classifier
# explanation). It deliberately NEVER reads `tool_input` — that is where a secret / token /
# file path would live. `reason` is run through `hook_redact_pii` (emails, home-dir
# usernames, JWTs, secrets) and truncated before persisting.
#
# Output/exit are ignored by CC (the denial already happened); pure side-effect.
#
# Kill switch:  UNLEASHED_DENY_LOG=off  -> exit 0
set -uo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
. "$_DIR/lib/hook-io.sh"
# shellcheck source=scripts/lib/log.sh
. "$_DIR/lib/log.sh"

[ "${UNLEASHED_DENY_LOG:-on}" = "off" ] && exit 0

hook_io_read

# tool_name (a simple identifier). Read it STRUCTURALLY top-level via hook_str (jq->python3,
# NEVER grep) — hook_tool_name's grep fallback would scan the whole JSON and could pick up a
# nested tool_input.tool_name, persisting it here. If no JSON engine exists, hook_str returns
# empty and we exit 0 (fail-open, log nothing) rather than risk a tool_input read.
TOOL="$(hook_str tool_name)"
TOOL="$(printf '%s' "$TOOL" | LC_ALL=C tr -cd 'A-Za-z0-9_.-' | cut -c1-40)"
[ -n "$TOOL" ] || exit 0

# reason is FREE TEXT -> redact PII, cap, json-escape. tool_input is never read.
REASON="$(hook_redact_pii "$(hook_str reason)")"
REASON="${REASON:0:200}"   # bash substring (char-aware, no cut subprocess / BSD `cut -c` quirk)
[ -n "$REASON" ] || REASON="unknown"
REASON_JSON="$(json_escape "$REASON")"

log_append "denied-commands.jsonl" "$(printf '{"ts":"%s","tool":"%s","reason":%s}' "$(log_ts)" "$TOOL" "$REASON_JSON")"
exit 0
