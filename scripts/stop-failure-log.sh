#!/usr/bin/env bash
# StopFailure diagnostic log (Item 10, COREDEV-2325).
#
# Observe-only telemetry: on a turn-ending API error, append ONE bounded JSONL line
# carrying ONLY the coarse error ENUM (rate_limit · overloaded · authentication_failed ·
# billing_error · server_error · max_output_tokens · unknown · …). The enum is PII-free
# by construction; we NEVER read or log the free-text error_message / error_details /
# last_assistant_message (they can embed /Users/<name>/… paths or tokens).
#
# StopFailure output and exit code are IGNORED by Claude Code, so this is pure side-effect
# and safe to ship enabled. Reads the type defensively as `error_type` then `error`
# (a safe superset across CC builds).
#
# Kill switch:  UNLEASHED_FAILURE_LOG=off  -> exit 0
set -uo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/hook-io.sh
. "$_DIR/lib/hook-io.sh"
# shellcheck source=scripts/lib/log.sh
. "$_DIR/lib/log.sh"

[ "${UNLEASHED_FAILURE_LOG:-on}" = "off" ] && exit 0

hook_io_read

ETYPE="$(hook_str error_type)"
[ -n "$ETYPE" ] || ETYPE="$(hook_str error)"
# error_type is documented as a coarse enum, but the defensive `.error` fallback can carry
# free text on some builds. REDACT first (matching every sibling hook), THEN clamp to the
# enum charset + cap — `tr -cd` alone would strip delimiters yet KEEP a username/email/JWT
# payload (e.g. `/Users/john.doe/x` -> `Usersjohn.doex`). Redact-then-clamp leaks neither.
ETYPE="$(hook_redact_pii "$ETYPE" | LC_ALL=C tr -cd 'A-Za-z0-9_.-' | cut -c1-40)"
[ -n "$ETYPE" ] || ETYPE="unknown"

log_append "error-log.jsonl" "$(printf '{"ts":"%s","type":"%s"}' "$(log_ts)" "$ETYPE")"
exit 0
