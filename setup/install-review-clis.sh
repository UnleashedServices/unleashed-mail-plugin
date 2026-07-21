#!/usr/bin/env bash
# install-review-clis.sh — bootstrap the plan-review toolchain in a remote/CI env.
#
# Idempotent. Run once per fresh environment (e.g. from a SessionStart hook or by
# hand). It:
#   1. installs the Codex CLI (@openai/codex) and seeds ~/.codex/auth.json from
#      $CODEX_AUTH_JSON (base64 of a ChatGPT-mode auth.json);
#   2. seeds the Antigravity (agy) OAuth creds from $AGY_CREDS (base64 of the
#      Google OAuth token JSON) — agy itself is pre-installed in the image;
#   3. installs the unleashed-mail Claude Code plugin from this repo's marketplace.
#
# Contains NO secrets: it only reads credentials the environment injects as env
# vars and writes them to each CLI's own credential file. Never echoes values.
#
# NOTE: agy on a headless host loads its token from the OS keyring first and only
# falls back to a file in specific conditions; if `agy -p ping` still asks you to
# log in after this runs, the injected $AGY_CREDS is stale — re-extract fresh
# creds from a logged-in Mac with setup/extract-agy-auth-macos.sh and update the
# environment variable.
set -uo pipefail
umask 077

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
log() { printf '  %s\n' "$*"; }

b64_to_file() {  # $1=base64 value, $2=dest path — decode without echoing
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  printf '%s' "$1" | base64 -d > "$dest" || return 1
  chmod 600 "$dest"
}

echo "== codex =="
if command -v codex >/dev/null 2>&1; then
  log "already installed: $(codex --version 2>&1 | head -1)"
elif npm install -g @openai/codex >/tmp/codex-install.log 2>&1; then
  log "installed via npm: $(codex --version 2>&1 | head -1)"
elif command -v bun >/dev/null 2>&1 && bun install -g @openai/codex >>/tmp/codex-install.log 2>&1; then
  log "installed via bun: $(codex --version 2>&1 | head -1)"
else
  log "ERROR: codex install failed (see /tmp/codex-install.log)"
fi
if [ -n "${CODEX_AUTH_JSON:-}" ]; then
  if b64_to_file "$CODEX_AUTH_JSON" "$HOME/.codex/auth.json"; then
    log "seeded ~/.codex/auth.json"
  else
    log "ERROR: could not decode \$CODEX_AUTH_JSON"
  fi
  # Documented config for this ChatGPT-auth install (skills/codex-review/SKILL.md).
  if [ ! -f "$HOME/.codex/config.toml" ]; then
    printf 'model = "gpt-5.6-sol"\nmodel_reasoning_effort = "xhigh"\n' > "$HOME/.codex/config.toml"
    log "wrote ~/.codex/config.toml (model=gpt-5.6-sol, effort=xhigh)"
  fi
else
  log "WARN: \$CODEX_AUTH_JSON not set — skipping codex auth seed"
fi

echo "== agy =="
if command -v agy >/dev/null 2>&1; then
  log "installed: $(agy --version 2>&1 | head -1)"
else
  log "WARN: agy binary not found on PATH (expected to be pre-installed)"
fi
if [ -n "${AGY_CREDS:-}" ]; then
  # $AGY_CREDS_PATH may contain a literal ~ — expand it to $HOME.
  agy_token_path="${AGY_CREDS_PATH:-$HOME/.gemini/antigravity-cli/antigravity-oauth-token}"
  agy_token_path="${agy_token_path/#\~/$HOME}"
  b64_to_file "$AGY_CREDS" "$agy_token_path" && log "seeded ${agy_token_path/#$HOME/~}"
  b64_to_file "$AGY_CREDS" "$HOME/.gemini/oauth_creds.json" && log "seeded ~/.gemini/oauth_creds.json"
else
  log "WARN: \$AGY_CREDS not set — skipping agy auth seed"
fi
# Model pin per skills/gemini-review/SKILL.md.
if [ ! -f "$HOME/.gemini/settings.json" ]; then
  mkdir -p "$HOME/.gemini"
  printf '{ "model": { "name": "gemini-3.1-pro" } }\n' > "$HOME/.gemini/settings.json"
  log "wrote ~/.gemini/settings.json (model=gemini-3.1-pro)"
fi

echo "== unleashed-mail plugin =="
if command -v claude >/dev/null 2>&1; then
  mkt="unleashedservices-unleashed-mail-plugin"
  if claude plugin marketplace list 2>/dev/null | grep -q "$mkt"; then
    log "marketplace already registered: $mkt"
  else
    claude plugin marketplace add "$REPO_ROOT" >/dev/null 2>&1 \
      && log "added marketplace: $mkt ($REPO_ROOT)" \
      || log "ERROR: could not add marketplace from $REPO_ROOT"
  fi
  if claude plugin list 2>/dev/null | grep -q "unleashed-mail@$mkt"; then
    log "plugin already installed: unleashed-mail@$mkt"
  else
    claude plugin install "unleashed-mail@$mkt" --scope user >/dev/null 2>&1 \
      && log "installed plugin: unleashed-mail@$mkt" \
      || log "ERROR: plugin install failed"
  fi
else
  log "WARN: claude CLI not found — cannot install the plugin"
fi

echo "== done =="
