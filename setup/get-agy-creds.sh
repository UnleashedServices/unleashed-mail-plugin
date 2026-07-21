#!/usr/bin/env bash
# get-agy-creds.sh — print AGY_CREDS (base64 of agy's token file) from a host
# where agy is logged in in FILE-STORAGE mode (Linux / headless / no-keyring —
# e.g. this remote environment). That file is the exact artifact the environment
# needs; base64 of it IS AGY_CREDS.
#
#   bash setup/get-agy-creds.sh            # -> prints AGY_CREDS to stdout
#
# NOTE: on macOS agy stores its login in the Keychain and this file does NOT
# exist — use setup/extract-agy-auth-macos.sh there, or run a file-mode login
# (see setup/README.md "Re-generating AGY_CREDS").
#
# The correct file/envelope shape (verified) is:
#   {"auth_method":"consumer","token":{"access_token","expiry","refresh_token","token_type"}}
# The auth_method field is the critical part — without it agy cannot refresh and
# logs "unknown auth method", which is what a raw oauth_creds.json blob is missing.
set -uo pipefail
TOK="${1:-$HOME/.gemini/antigravity-cli/antigravity-oauth-token}"

if [ ! -f "$TOK" ]; then
  echo "No token file at: $TOK" >&2
  echo "agy isn't logged in here in file mode. See setup/README.md." >&2
  exit 1
fi

# Validate the envelope agy actually needs, so we never emit a blob that will
# silently fail to authenticate.
python3 - "$TOK" >&2 <<'PY' || { echo "Refusing to emit an invalid AGY_CREDS." >&2; exit 1; }
import json,sys
d=json.load(open(sys.argv[1]))
assert d.get("auth_method"), "FAIL: missing 'auth_method' (this file will not authenticate)"
t=d.get("token") or {}
for k in ("access_token","refresh_token"):
    assert t.get(k), f"FAIL: token.{k} missing"
print(f"OK: auth_method={d['auth_method']!r}, token keys={sorted(t)}")
PY

# portable base64 (macOS BSD base64 has no -w flag; strip any wrapping)
base64 < "$TOK" | tr -d '\n'; echo
