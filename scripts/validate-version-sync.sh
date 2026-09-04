#!/usr/bin/env bash
# validate-version-sync.sh — Phase 0, Item 1 (COREDEV-2322)
#
# Asserts the plugin's version + asset counts are in sync across their sources of
# truth, so a bump to one place can't silently drift from the others:
#   1. .claude-plugin/plugin.json  "version"
#   2. README.md  H1            "… Plugin vX.Y.Z"
#   3. README.md  newest         "### vX.Y.Z"  (What's New)
#   4. README.md  bold counts    "**N agents · N skills · N commands · N MCP server(s)**"
#                                vs the files actually on disk + .mcp.json
#   5. .claude-plugin/marketplace.json  the entry's "version"
#
# Scope: the unleashed-mail PLUGIN repo only (run from the HAS_XCODEPROJ=false
# branch of pre-commit-checks.sh).
#
# SOURCE 5 IS LOAD-BEARING, and its absence was the root cause of a recurring
# reversion (COREDEV-2801). When a marketplace entry declares no "version", Claude
# Code resolves the installed version down a fallback that takes the FIRST entry of a
# raw directory read of the plugin cache — no sort, no semver comparison. On the
# maintainer's machine index 0 was 2.7.0, so every registry rebuild reinstated 2.7.0
# while origin/main was many releases ahead. Declaring the version pins the choice; this
# check keeps it from drifting from plugin.json, which is the only reason it works.
#
# Modes (env):
#   VERSION_SYNC_ENFORCE=warn   (default) — print mismatches, exit 0  (pre-commit)
#   VERSION_SYNC_ENFORCE=strict           — print mismatches, exit 1  (CI)
#   SKIP_PLUGIN_VALIDATORS=1              — hard bypass, exit 0
set -euo pipefail

[[ ${SKIP_PLUGIN_VALIDATORS:-0} == "1" ]] && {
	echo "⏭️  validate-version-sync: skipped (SKIP_PLUGIN_VALIDATORS=1)"
	exit 0
}

# Self-locate the repo root (parent of scripts/) so it runs from any CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENFORCE="${VERSION_SYNC_ENFORCE:-warn}"

errors=0
fail() {
	echo "❌ $*"
	errors=$((errors + 1))
}

PLUGIN_JSON="$ROOT/.claude-plugin/plugin.json"
README="$ROOT/README.md"
MCP_JSON="$ROOT/.mcp.json"

[[ -f $PLUGIN_JSON ]] || fail "missing .claude-plugin/plugin.json"
[[ -f $README ]] || fail "missing README.md"

# --- versions ---------------------------------------------------------------
# plugin.json is the comparison anchor.
PLUGIN_VERSION="$(grep -m1 -oE '"version"[[:space:]]*:[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' "$PLUGIN_JSON" 2>/dev/null |
	grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
# Read THE first Markdown H1 line (the title), then require the version to be in IT — so
# a later heading like `# Legacy Plugin vX.Y.Z` can't satisfy the gate when the real
# title drops the version (codex PR #11).
README_H1_LINE="$(grep -m1 -E '^#[[:space:]]' "$README" 2>/dev/null || true)"
README_H1="$(printf '%s\n' "$README_H1_LINE" | grep -oE 'Plugin v[0-9]+\.[0-9]+\.[0-9]+' | head -1 | sed 's/Plugin v//' || true)"
README_WHATSNEW="$(grep -m1 -oE '^### v[0-9]+\.[0-9]+\.[0-9]+' "$README" 2>/dev/null | sed 's/^### v//' || true)"

[[ -n $PLUGIN_VERSION ]] || fail "could not parse version from plugin.json"
[[ -n $README_H1 ]] || fail "could not parse 'Plugin vX.Y.Z' from README H1"
[[ -n $README_WHATSNEW ]] || fail "could not parse newest '### vX.Y.Z' from README"

[[ $PLUGIN_VERSION == "$README_H1" ]] ||
	fail "version drift: README H1 v$README_H1 != plugin.json $PLUGIN_VERSION — bump README H1"
[[ $PLUGIN_VERSION == "$README_WHATSNEW" ]] ||
	fail "version drift: newest README '### v$README_WHATSNEW' != plugin.json $PLUGIN_VERSION — add a What's-New entry"

# 5. marketplace.json — the pull signal AND the version resolver's input (COREDEV-2801).
MARKETPLACE_JSON="${ROOT}/.claude-plugin/marketplace.json"
if [[ -f ${MARKETPLACE_JSON} ]]; then
	MARKETPLACE_VERSION="$(grep -m1 -oE '"version"[[:space:]]*:[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' "${MARKETPLACE_JSON}" 2>/dev/null |
		grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
	[[ -n ${MARKETPLACE_VERSION} ]] ||
		fail "marketplace.json declares no version — without it the installed version is chosen by raw directory order (COREDEV-2801)"
	[[ ${MARKETPLACE_VERSION} == "${PLUGIN_VERSION}" ]] ||
		fail "version drift: marketplace.json ${MARKETPLACE_VERSION} != plugin.json ${PLUGIN_VERSION} — bump marketplace.json"
else
	fail "missing .claude-plugin/marketplace.json"
fi

# --- asset counts (README bold line vs disk) --------------------------------
# Anchor on the bold counts line so historical "(up from X)" prose never matches.
COUNTS_LINE="$(grep -m1 -E '^\*\*[0-9]+ agents' "$README" 2>/dev/null || true)"
[[ -n $COUNTS_LINE ]] || fail "could not find the '**N agents · N skills · N commands …**' line in README"

# BSD wc left-pads with spaces — coerce to an integer via arithmetic ($(( )) ).
count_files() {
	local n
	n="$(find "$1" -mindepth "${3:-1}" -maxdepth "${4:-1}" -name "$2" 2>/dev/null | wc -l || true)"
	echo "$((n))"
}
readme_count() { printf '%s\n' "$COUNTS_LINE" | grep -oE "[0-9]+ $1" | head -1 | grep -oE '^[0-9]+' || true; }

DISK_AGENTS="$(count_files "$ROOT/agents" '*.md')"
DISK_SKILLS="$(count_files "$ROOT/skills" 'SKILL.md' 1 2)"
DISK_COMMANDS="$(count_files "$ROOT/commands" '*.md')"

check_count() { # readme_token  disk_value
	local token="$1" disk="$2" rd
	rd="$(readme_count "$token")"
	[[ -n $rd ]] || {
		fail "README counts line missing '$token'"
		return
	}
	[[ $rd == "$disk" ]] || fail "count drift: README says $rd $token, disk has $disk"
}
check_count "agents" "$DISK_AGENTS"
check_count "skills" "$DISK_SKILLS"
check_count "commands" "$DISK_COMMANDS"

# MCP-server count: whenever .mcp.json is part of the plugin, the README token must
# be present AND match — a dropped token is real drift (codex PR #11). utf-8-sig is
# BOM-safe (gemini PR #11). (allow the optional plural "servers")
README_MCP="$(printf '%s\n' "$COUNTS_LINE" | grep -oE '[0-9]+ MCP servers?' | head -1 | grep -oE '^[0-9]+' || true)"
if [[ -f $MCP_JSON ]]; then
	if command -v python3 >/dev/null 2>&1; then
		DISK_MCP="$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1], encoding="utf-8-sig")).get("mcpServers",{})))' "$MCP_JSON" 2>/dev/null || echo "")"
		if [[ -z $DISK_MCP ]]; then
			fail ".mcp.json present but unparseable for MCP-server count"
		elif [[ $DISK_MCP -gt 0 && -z $README_MCP ]]; then
			fail "count drift: .mcp.json defines $DISK_MCP MCP server(s) but the README counts line has no 'N MCP server' token"
		elif [[ -n $README_MCP && $README_MCP != "$DISK_MCP" ]]; then
			fail "count drift: README says $README_MCP MCP server(s), .mcp.json defines $DISK_MCP"
		fi
	fi
elif [[ -n $README_MCP && $README_MCP != "0" ]]; then
	fail "count drift: README says $README_MCP MCP server(s), but .mcp.json is missing"
fi

# --- manifest descriptions + CHANGELOG entry (MIN-24) -----------------------
# The asset counts are ALSO hardcoded in plugin.json and marketplace.json `description` — the text
# actually rendered on the marketplace listing — but the gate above only checked the README bold line,
# so adding agent #22 with a README edit left the manifests advertising the old count. And no gate
# asserted a CHANGELOG entry for the release, despite CLAUDE.md's mandatory "Bump + CHANGELOG on release".
MARKETPLACE_JSON="${ROOT}/.claude-plugin/marketplace.json"
check_desc_counts() { # file  label
	local file="$1" label="$2" a s
	[[ -f $file ]] || return 0
	a="$(grep -oE '[0-9]+ specialized agents' "$file" | head -1 | grep -oE '^[0-9]+' || true)"
	s="$(grep -oE '[0-9]+ skills' "$file" | head -1 | grep -oE '^[0-9]+' || true)"
	[[ -z $a || $a == "$DISK_AGENTS" ]] || fail "count drift: $label description says $a specialized agents, disk has $DISK_AGENTS"
	[[ -z $s || $s == "$DISK_SKILLS" ]] || fail "count drift: $label description says $s skills, disk has $DISK_SKILLS"
}
check_desc_counts "$PLUGIN_JSON" "plugin.json"
check_desc_counts "$MARKETPLACE_JSON" "marketplace.json"

CHANGELOG="$ROOT/CHANGELOG.md"
if [[ -f $CHANGELOG ]]; then
	grep -qE "^##[[:space:]]+\[$PLUGIN_VERSION\]" "$CHANGELOG" ||
		fail "CHANGELOG.md has no '## [$PLUGIN_VERSION]' entry (bump + CHANGELOG on release — CLAUDE.md)"
else
	fail "missing CHANGELOG.md (version-sync asserts a '## [x.y.z]' entry per release)"
fi

# --- result -----------------------------------------------------------------
if [[ $errors -eq 0 ]]; then
	echo "✅ version-sync OK — plugin $PLUGIN_VERSION == README (H1 & What's-New); counts ${DISK_AGENTS}/${DISK_SKILLS}/${DISK_COMMANDS}${README_MCP:+/${README_MCP}} match disk"
	exit 0
fi

echo "—"
if [[ $ENFORCE == "strict" ]]; then
	echo "❌ version-sync: $errors problem(s) (strict) — failing."
	exit 1
fi
echo "⚠️  version-sync: $errors problem(s) (warn mode — not blocking; set VERSION_SYNC_ENFORCE=strict to enforce)."
exit 0
