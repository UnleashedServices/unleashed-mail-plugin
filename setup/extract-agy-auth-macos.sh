#!/usr/bin/env bash
# extract-agy-auth-macos.sh
# Run on the Mac where Antigravity (`agy`) is LOGGED IN.
# It locates agy's OAuth credentials (macOS login Keychain first, then the
# on-disk fallbacks) and prints them base64-encoded, ready to paste into the
# remote environment as AGY_CREDS.
#
#   Usage:  bash extract-agy-auth-macos.sh
#
# The output contains a live OAuth refresh token — treat it like a password,
# don't paste it into chat/Slack/screenshots. Set it only in the environment's
# secret/env-var configuration.
set -uo pipefail

# A valid agy creds blob is the Google OAuth token JSON: it must carry both an
# access_token and a refresh_token. This guards against grabbing an unrelated
# keychain item (e.g. MCP tokens) that happens to share a service name.
is_valid() {
  printf '%s' "$1" | grep -q '"access_token"' && printf '%s' "$1" | grep -q '"refresh_token"'
}

emit() {
  local json="$1" src="$2"
  is_valid "$json" || return 1
  local b64 exp
  b64=$(printf '%s' "$json" | base64 | tr -d '\n')
  exp=$(printf '%s' "$json" | sed -n 's/.*"expiry_date"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' | head -1)
  echo
  echo "✅ Found agy credentials via: $src"
  [ -n "$exp" ] && echo "   (access_token expiry_date field: $exp — the refresh_token renews it automatically)"
  echo
  echo "── Paste these into the remote environment's variables ──────────────"
  echo
  echo "AGY_CREDS=$b64"
  echo "AGY_CREDS_PATH=~/.gemini/antigravity-cli/antigravity-oauth-token"
  echo
  echo "─────────────────────────────────────────────────────────────────────"
  echo "(Leave GEMINI_OAUTH_CREDS alone — despite the name it holds the codex"
  echo " ChatGPT auth, not agy's Google OAuth creds.)"
  return 0
}

echo "Searching for Antigravity (agy) credentials on this Mac…"

# 1) On-disk fallbacks (present when the keyring was unavailable at login time).
for f in "$HOME/.gemini/antigravity-cli/antigravity-oauth-token" \
         "$HOME/.gemini/oauth_creds.json"; do
  [ -f "$f" ] || continue
  echo "  • file: $f"
  emit "$(cat "$f")" "$f" && exit 0
done

# 2) macOS login Keychain (primary store on macOS: codeassistclient.KeyringTokenStorage).
#    Try service-only first (fewest prompts), then narrow by account name.
#    macOS will pop a "security wants to use your confidential information" dialog —
#    click Allow (or "Always Allow").
for svc in antigravity-cli antigravity gemini-cli codeassist code_assist; do
  # service-only
  s=$(security find-generic-password -s "$svc" -w 2>/dev/null || true)
  if [ -n "$s" ]; then
    echo "  • keychain: service=$svc"
    emit "$s" "keychain service=$svc" && exit 0
  fi
  for acct in oauth_token oauth-token oauth_creds token; do
    s=$(security find-generic-password -s "$svc" -a "$acct" -w 2>/dev/null || true)
    [ -n "$s" ] || continue
    echo "  • keychain: service=$svc account=$acct"
    emit "$s" "keychain service=$svc account=$acct" && exit 0
  done
done

# 3) Nothing matched — help identify the right item (attribute-only, no secret, no prompt).
echo
echo "❌ Could not auto-locate agy credentials."
echo "   First confirm agy is logged in:   agy -p ping     (should print 'pong')"
echo
echo "   Then list candidate Keychain items (this shows names only, not secrets):"
echo "     security dump-keychain 2>/dev/null | grep -iE 'antigravity|gemini|codeassist|jetski' "
echo
echo "   Send me the service ('svce') / account ('acct') it shows and I'll adjust the script."
exit 1
