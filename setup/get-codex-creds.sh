#!/usr/bin/env bash
# get-codex-creds.sh — print CODEX_AUTH_JSON (base64 of ~/.codex/auth.json) to
# store for re-provisioning a future environment.
#
#   bash setup/get-codex-creds.sh          # -> prints CODEX_AUTH_JSON to stdout
#
# codex auth is ChatGPT-mode (auth.json carries a refresh_token + account_id), so
# a stored value keeps working — codex refreshes the access token itself. The
# environment already injects this as $CODEX_AUTH_JSON and seeds it to
# ~/.codex/auth.json; this script just re-emits the current (freshest) value.
#
# Output holds live OAuth tokens — store only in a secret manager; never paste
# into chat/tickets/screenshots.
set -uo pipefail
AUTH="${1:-$HOME/.codex/auth.json}"

if [ ! -f "$AUTH" ]; then
  echo "No codex auth at: $AUTH" >&2
  echo "Run 'codex login' or seed CODEX_AUTH_JSON first." >&2
  exit 1
fi

python3 - "$AUTH" >&2 <<'PY' || { echo "Refusing to emit invalid CODEX_AUTH_JSON." >&2; exit 1; }
import json,sys
d=json.load(open(sys.argv[1]))
t=d.get("tokens") or {}
assert t.get("refresh_token"), "FAIL: no tokens.refresh_token (not a durable ChatGPT auth)"
print(f"OK: auth_mode={d.get('auth_mode')!r}, token keys={sorted(t)}")
PY

# portable base64 (macOS BSD base64 has no -w flag; strip any wrapping)
base64 < "$AUTH" | tr -d '\n'; echo
