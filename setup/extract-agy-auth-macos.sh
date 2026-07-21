#!/usr/bin/env bash
# extract-agy-auth-macos.sh
# Run on the Mac where Antigravity (`agy`) is LOGGED IN. Reconstructs the token
# envelope agy needs and prints it base64-encoded, ready to paste into the
# environment as AGY_CREDS.
#
#   bash extract-agy-auth-macos.sh
#
# Background (verified 2026-07): agy's on-disk / injected credential is NOT a raw
# Google-OAuth blob. It is:
#   {"auth_method":"consumer","token":{"access_token","expiry","refresh_token","token_type"}}
# The `auth_method` field is what lets agy REFRESH; a raw oauth_creds.json blob
# lacks it, so once the ~1h access token expires agy logs "unknown auth method"
# and can never recover. On macOS agy keeps these in the login Keychain under
# service "gemini" (accounts "<email>:accessToken/refreshToken/tokenExpiry"),
# not in a file — so we read those and rebuild the envelope.
#
# We deliberately set expiry in the past so agy refreshes on first use (proven to
# work) — this sidesteps any Keychain expiry-format differences; only the
# refresh_token + auth_method actually need to be correct.
#
# Output holds a live OAuth refresh token — set it only in the environment's
# secret store; never paste it into chat/tickets/screenshots.
set -uo pipefail

EMAIL="${1:-}"
# Discover the logged-in email from the Keychain if not passed as $1.
if [ -z "$EMAIL" ]; then
  EMAIL=$(security dump-keychain 2>/dev/null \
    | grep -oE '"acct"<blob>="[^"]+:accessToken"' \
    | sed -E 's/.*="([^"]+):accessToken"/\1/' | head -1)
fi
if [ -z "$EMAIL" ]; then
  echo "Could not find a 'gemini' Keychain entry (<email>:accessToken)." >&2
  echo "Pass your account email explicitly:  bash $0 you@example.com" >&2
  echo "Or confirm agy is logged in:  agy -p ping   (expect 'pong')" >&2
  exit 1
fi
echo "Using account: $EMAIL" >&2

# macOS may prompt "security wants to use your confidential information" — Allow.
kc() { security find-generic-password -s gemini -a "$1" -w 2>/dev/null; }
ACCESS=$(kc "${EMAIL}:accessToken")
REFRESH=$(kc "${EMAIL}:refreshToken")

if [ -z "$REFRESH" ]; then
  echo "No refresh token in Keychain for $EMAIL under service 'gemini'." >&2
  echo "Inspect with:  security dump-keychain | grep -iE 'gemini|antigravity'" >&2
  exit 1
fi

AGY_CREDS=$(ACCESS="$ACCESS" REFRESH="$REFRESH" /usr/bin/python3 - <<'PY'
import os, json, base64
env = {
    "auth_method": "consumer",
    "token": {
        "access_token": os.environ.get("ACCESS", ""),
        "expiry": "2000-01-01T00:00:00Z",   # past -> agy refreshes on first use
        "refresh_token": os.environ["REFRESH"],
        "token_type": "Bearer",
    },
}
print(base64.b64encode(json.dumps(env).encode()).decode())
PY
)

echo >&2
echo "── Set this in the environment's variables ──────────────────────────" >&2
echo "AGY_CREDS=$AGY_CREDS"
echo "AGY_CREDS_PATH=~/.gemini/antigravity-cli/antigravity-oauth-token" >&2
echo "─────────────────────────────────────────────────────────────────────" >&2
echo "(Then in the environment: agy -p ping  should print 'pong'.)" >&2
