#!/usr/bin/env bash
# extract-agy-auth-macos.sh
# Run on the Mac where Antigravity (`agy`) is LOGGED IN. Extracts agy's stored
# OAuth token, validates it, and prints (and copies) it as AGY_CREDS — ready to
# paste into the environment. NO interactive login required as long as a valid
# token already lives on the Mac.
#
#   bash extract-agy-auth-macos.sh            # -> prints AGY_CREDS, copies to clipboard
#
# ── Where agy keeps the token on macOS (verified 2026-07) ────────────────────
# agy stores its login through go-keyring, which on macOS is the login Keychain:
#   service = "gemini",  account = "antigravity"
# go-keyring base64-encodes the secret and stores it with a "go-keyring-base64:"
# PREFIX. The decoded secret is the envelope agy needs:
#   {"auth_method":"consumer","token":{"access_token","expiry","refresh_token","token_type"}}
# So AGY_CREDS (= base64 of that JSON) is simply the keychain value with the
# "go-keyring-base64:" prefix stripped off — no re-encoding required.
#
# The `auth_method` field is what lets agy REFRESH; a raw oauth_creds.json blob
# lacks it, so once the ~1h access token expires agy logs "unknown auth method"
# and can never recover. This script validates auth_method + refresh_token are
# present before emitting anything, so it never hands back a blob that will
# silently fail to authenticate.
#
# ── Why this is the cheap path ───────────────────────────────────────────────
# Minting a NEW refresh token needs an interactive Google consent (an OAuth rule
# we can't skip), and spinning up an environment to do it costs time + compute.
# But you rarely need a new one: a token with `auth_method` auto-refreshes forever
# (Google doesn't rotate the refresh token per refresh — agy just re-mints the
# access token on use). This pulls that still-valid token off the Mac in ~2s, so
# the login flow stays a true last resort — only when Google has actually REVOKED
# the refresh token (password change, >6 months unused, or per-client token cap).
#
# Output holds a live OAuth refresh token — set it only in the environment's
# secret store; never paste it into chat/tickets/screenshots.
set -uo pipefail

SERVICE="gemini"
ACCOUNT="antigravity"

if ! command -v security >/dev/null 2>&1; then
  echo "This script is for macOS (needs the 'security' Keychain tool)." >&2
  echo "On a Linux/file-mode host use setup/get-agy-creds.sh instead." >&2
  exit 1
fi

# macOS may prompt "security wants to use your confidential information" — Allow.
RAW="$(security find-generic-password -a "$ACCOUNT" -s "$SERVICE" -w 2>/dev/null || true)"

if [ -z "$RAW" ]; then
  echo "No agy Keychain entry (service=$SERVICE, account=$ACCOUNT)." >&2
  echo "Confirm agy is logged in on this Mac:  agy -p ping   (expect 'pong')" >&2
  echo "Inspect what's stored:  security dump-keychain 2>/dev/null | grep -iE 'gemini|antigravity'" >&2
  exit 1
fi

# go-keyring prefixes base64-encoded secrets. Strip it -> that IS AGY_CREDS.
# If (unexpectedly) unprefixed, the value is raw JSON, so base64 it ourselves.
case "$RAW" in
  go-keyring-base64:*) CREDS="${RAW#go-keyring-base64:}" ;;
  *)                   CREDS="$(printf '%s' "$RAW" | base64 | tr -d '\n')" ;;
esac

# Validate the decoded envelope is the refreshable shape agy needs.
if ! printf '%s' "$CREDS" | base64 -d 2>/dev/null | /usr/bin/python3 - <<'PY' >/dev/null 2>&1
import json,sys
d=json.load(sys.stdin)
assert d.get("auth_method"), "missing auth_method"
t=d.get("token") or {}
assert t.get("access_token") and t.get("refresh_token"), "missing token fields"
PY
then
  echo "Found a Keychain entry but it is NOT the refreshable envelope" >&2
  echo "(needs auth_method + token.refresh_token). The stored login may be" >&2
  echo "revoked/incomplete — run 'agy -p ping'; if it shows a login URL, a" >&2
  echo "one-time re-login is required (OAuth won't mint a refresh token otherwise)." >&2
  exit 1
fi

if command -v pbcopy >/dev/null 2>&1; then
  printf '%s' "$CREDS" | pbcopy && echo "✅ AGY_CREDS copied to clipboard (valid, refreshable)" >&2
else
  echo "OK: extracted a valid, refreshable AGY_CREDS" >&2
fi

echo >&2
echo "── Set these in the environment's variables ─────────────────────────" >&2
echo "AGY_CREDS=$CREDS"
echo "AGY_CREDS_PATH=~/.gemini/antigravity-cli/antigravity-oauth-token" >&2
echo "─────────────────────────────────────────────────────────────────────" >&2
echo "(Then in the environment: agy -p ping  should print 'pong'.)" >&2
