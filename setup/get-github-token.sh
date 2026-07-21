#!/usr/bin/env bash
# get-github-token.sh — print the GitHub token to store as GH_TOKEN for
# re-provisioning.
#
#   bash setup/get-github-token.sh          # -> prints the token to stdout
#
# In this managed environment there is no `gh` CLI; GitHub auth is a token in
# $GH_TOKEN (git operations also go through a local auth proxy). Store the token
# value and re-inject it as GH_TOKEN.
#
#   github_pat_… / ghp_…  -> fine-grained / classic PAT: durable until expiry (worth storing)
#   ghs_…                 -> GitHub App installation token: ~1h, auto-provisioned (NOT worth storing)
#
# The token grants repo access — store only in a secret manager; never paste it
# into chat/tickets/screenshots.
set -uo pipefail
tok="${GH_TOKEN:-${GITHUB_TOKEN:-}}"

if [ -z "$tok" ]; then
  echo "No GH_TOKEN / GITHUB_TOKEN in the environment." >&2
  exit 1
fi

case "$tok" in
  ghs_*) echo "NOTE: ghs_ = short-lived App installation token (~1h); the platform re-issues it per session, so storing it is pointless." >&2 ;;
  ghp_*|github_pat_*) echo "OK: durable PAT (store it)." >&2 ;;
  *) echo "NOTE: unrecognized token prefix; verify its lifetime before relying on a stored copy." >&2 ;;
esac

printf '%s\n' "$tok"
