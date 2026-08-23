#!/usr/bin/env bash
# Prove the plugin LOADS, not merely that it validates (COREDEV-2598).
#
# `claude plugin validate --strict .` is SCHEMA validation. It cannot see load-layer breakage: a
# duplicate declaration, a manifest the loader rejects, an MCP server that never starts. The upstream
# this pattern is adopted from (ayghri/i-have-adhd, MIT) records exactly that — a duplicate hooks
# declaration that validated cleanly and shipped.
#
# WHY THIS IS NOT UPSTREAM'S RECIPE
# Upstream does `claude plugin marketplace add "$GITHUB_WORKSPACE"` and greps for `✔ enabled`. Both
# steps are wrong HERE, and each was reproduced before this script was written:
#
#   1. Our marketplace entry is {"source":"github","repo":"UnleashedServices/…"}, not "./". Adding the
#      workspace directly makes the CLI GIT-CLONE main into the cache and report `enabled: true` — it
#      installed v2.5.3 over a branch at 2.6.1, and the branch's own plan files were absent from the
#      installed tree. A green check over the wrong bytes is worse than no check. Upstream can use its
#      recipe only because its source IS "./".
#   2. `enabled` is REGISTRY state. Verified: with `.mcp.json` repointed at a nonexistent file the
#      install still exits 0 and reports enabled, and the reported `mcpServers` still contains a
#      literal unexpanded ${CLAUDE_PLUGIN_ROOT} — an echo of the manifest, not runtime state. And
#      issue #61's own duplicate-hooks defect installs, reports enabled, AND passes
#      `validate --strict`, because that error surfaces on RELOAD.
#
# So: install the checkout's own BYTES (proved by a per-run sentinel, not by a version number that
# main and the branch usually share), then assert the MCP server actually starts FROM ITS OWN
# DECLARATION, and assert the hook-manifest shape the CLI never exposes.
#
# MUTANT -> ASSERTION MAPPING, as EXECUTED. Recorded because the plan spent two rounds claiming a
# one-to-one mapping it did not have, and because an assertion no mutant reaches is decoration.
#
#   mutant                                            fails at              status
#   ------------------------------------------------  --------------------  -----------------------
#   plugin.json gains a `hooks` key (#61's defect)    step 4, `errors`      PROVED
#   .mcp.json repointed at a nonexistent file         step 5, handshake     PROVED
#   marketplace source left as `github`               step 4, version       PROVED
#   ...same, with versions made EQUAL                 step 4, SENTINEL      PROVED  <- the important one
#
# THE SENTINEL RUN IS THE ONE THAT MATTERS. With the versions deliberately equal — which is the normal
# case, since main and a branch share a version for any change that does not bump one — the version
# smoke check PASSES and the sentinel is the only assertion that detects remote bytes. Executed: it
# installed 2.5.3 from main, the version check was satisfied, and the sentinel caught it. A version
# check alone would have shipped this.
#
# ONE ASSERTION IS NOT PROVED, AND IS LABELLED RATHER THAN CLAIMED: step 6's `plugin.json has no
# hooks key`. On 2.1.220 the CLI already reports that defect in `list --json`'s `errors` array, so
# step 4 fires first and step 6 is unreachable by any mutant. It stays as defence-in-depth — if a
# future CLI stops surfacing it, step 6 still catches it — but do NOT record it as mutation-proved.
#
# Usage: ci-load-check.sh [--keep]      (--keep leaves the scratch dirs for inspection)
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

WORK="$(mktemp -d)"
SRC="$WORK/plugin-src"
export CLAUDE_CONFIG_DIR="$WORK/claude-config"
mkdir -p "$CLAUDE_CONFIG_DIR"

cleanup() { [ "$KEEP" = "1" ] || rm -rf "$WORK"; }
trap cleanup EXIT

fail() { printf 'LOAD CHECK FAILED — %s\n' "$*" >&2; exit 1; }
step() { printf '\n== %s\n' "$*"; }

MARKET_NAME="ci-load-check-$$"
# Unique per run. GITHUB_RUN_ID/ATTEMPT in CI; PID + epoch locally. A remote clone cannot contain it.
SENTINEL="ci-load-sentinel:${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-$$}-$(date +%s 2>/dev/null || echo 0)"

# ---------------------------------------------------------------------------------------------
step "1. copy the checkout and rewrite the copy's marketplace source to \"./\""
# NEVER mutate $REPO itself. rsync if present (CI), else cp -R.
if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude '.git' "$REPO/" "$SRC/" || fail "rsync of the checkout failed"
else
    mkdir -p "$SRC" && (cd "$REPO" && tar cf - --exclude='./.git' .) | (cd "$SRC" && tar xf -) \
        || fail "copy of the checkout failed"
fi
python3 - "$SRC/.claude-plugin/marketplace.json" "$MARKET_NAME" <<'PY' || fail "marketplace rewrite failed"
import json, sys
path, name = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    m = json.load(fh)
m["name"] = name          # scratch marketplace, so it cannot collide with a real installation
for p in m.get("plugins", []):
    # "./" is the ONLY expressible local form: absolute paths and ../-relative sources are both
    # rejected by the loader (`plugins.0.source: Invalid input`), verified on 2.1.220.
    p["source"] = "./"
with open(path, "w", encoding="utf-8") as fh:
    json.dump(m, fh, indent=2)
print(f"  marketplace -> {name}, source -> ./")
PY

# FIDELITY GAP, stated so nobody "fixes" it back: CI now tests a manifest differing from the shipped
# one by one field, so the `source: github` path is never exercised here. That path is GitHub's job.
step "2. plant the per-run sentinel in a provably-shipped file"
# hooks/hooks.json:101 invokes precompact-snapshot.sh from ${CLAUDE_PLUGIN_ROOT}, so if it is missing
# from the install the plugin is broken anyway. A trailing shell comment cannot affect behaviour.
CARRIER="$SRC/scripts/precompact-snapshot.sh"
[ -f "$CARRIER" ] || fail "sentinel carrier missing from the copy: scripts/precompact-snapshot.sh"
printf '\n# %s\n' "$SENTINEL" >> "$CARRIER"
bash -n "$CARRIER" || fail "sentinel broke the carrier's syntax"
echo "  planted: $SENTINEL"

step "3. install from the scratch marketplace into a scratch CLAUDE_CONFIG_DIR"
# Gate on `install` + `list --json`, never on `add`: `marketplace add` exits 0 and prints
# "✔ Successfully added" even for manifests `claude plugin validate` rejects (verified on 2.1.220).
claude plugin marketplace add "$SRC" >/dev/null 2>&1 || fail "marketplace add failed"
claude plugin install "unleashed-mail@$MARKET_NAME" >/dev/null 2>&1 \
    || fail "plugin install failed (this is the load layer schema validation cannot reach)"

step "4. assert on PARSED JSON — id, enabled, errors, version, and the sentinel"
LIST="$WORK/list.json"
claude plugin list --json 2>/dev/null > "$LIST" || fail "plugin list --json failed"
# Run the assertions as their OWN command and check the status in THIS shell. `X="$(… || fail …)"`
# does not work: `fail` runs in the command-substitution SUBSHELL, so it prints and exits the
# subshell while the parent carries on with an empty X — the script then reported a SECOND, bogus
# failure from a later assertion. Found by a mutant, which is the point of running them.
python3 - "$LIST" "$MARKET_NAME" "$SRC" > "$WORK/installpath" <<'PY'
import json, sys
list_path, market, src = sys.argv[1], sys.argv[2], sys.argv[3]
with open(list_path, encoding="utf-8") as fh:
    data = json.load(fh)
rows = data if isinstance(data, list) else data.get("plugins", data)
want = f"unleashed-mail@{market}"
hits = [p for p in rows if p.get("id") == want]
if len(hits) != 1:
    sys.exit(f"expected exactly one {want}; got {len(hits)}")
p = hits[0]
if p.get("enabled") is not True:
    sys.exit(f"enabled is {p.get('enabled')!r}, not True")
# A reviewer observed enabled:true alongside a NON-EMPTY errors array during a cache refresh, so the
# shape exists. Without this the machine-readable gate can approve an entry the CLI calls broken.
if p.get("errors"):
    sys.exit(f"entry reports errors: {p['errors']!r}")
with open(f"{src}/.claude-plugin/plugin.json", encoding="utf-8") as fh:
    expected_version = json.load(fh)["version"]
if p.get("version") != expected_version:
    sys.exit(f"installed version {p.get('version')!r} != checkout {expected_version!r}")
ip = p.get("installPath")
if not ip:
    sys.exit("no installPath reported")
print(ip)
PY
JSON_RC=$?
[ "$JSON_RC" = "0" ] || fail "JSON assertions failed (see the reason above)"
INSTALL_PATH="$(cat "$WORK/installpath")"
[ -n "$INSTALL_PATH" ] || fail "installPath empty after successful JSON assertions"
echo "  installPath: $INSTALL_PATH"

# THE BYTE-IDENTITY ASSERTION. Version equality is only a smoke check: main and the branch share a
# version for every change that does not bump one, so a source:github regression would install remote
# bytes and still pass a version check.
grep -qF "$SENTINEL" "$INSTALL_PATH/scripts/precompact-snapshot.sh" 2>/dev/null \
    || fail "sentinel ABSENT from the installed tree — the install did not come from this checkout"
echo "  sentinel present in the installed tree"

step "5. drive the MCP server FROM ITS OWN INSTALLED DECLARATION"
# Reading the declaration rather than a known path is load-bearing: hard-coding
# <installPath>/mcp/review-synthesizer/mcp_server.py would still start the real server when
# .mcp.json is repointed, so the mutant that repoints it would go green.
python3 - "$INSTALL_PATH" <<'PY' || fail "MCP handshake failed"
import json, os, subprocess, sys
root = sys.argv[1]
with open(os.path.join(root, ".mcp.json"), encoding="utf-8") as fh:
    servers = json.load(fh)["mcpServers"]
if list(servers) != ["review-synthesizer"]:
    sys.exit(f"unexpected mcpServers keys: {list(servers)}")
decl = servers["review-synthesizer"]
argv = [decl["command"]] + [a.replace("${CLAUDE_PLUGIN_ROOT}", root) for a in decl.get("args", [])]
msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "ci-load-check", "version": "1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
]
payload = "".join(json.dumps(m) + "\n" for m in msgs)
proc = subprocess.run(argv, input=payload, capture_output=True, text=True, timeout=30)
got = {}
for line in proc.stdout.splitlines():
    line = line.strip()
    if not line:
        continue
    m = json.loads(line)
    if "error" in m:
        sys.exit(f"MCP error reply: {m['error']!r}")
    got[m.get("id")] = m.get("result", {})
if 1 not in got:
    sys.exit(f"no initialize response (stderr: {proc.stderr[:200]!r})")
if not got[1].get("protocolVersion"):
    sys.exit("no protocolVersion negotiated")
if got[1].get("serverInfo", {}).get("name") != "review-synthesizer":
    sys.exit(f"unexpected serverInfo: {got[1].get('serverInfo')!r}")
names = [t["name"] for t in got.get(2, {}).get("tools", [])]
if names != ["synthesize_review"]:
    sys.exit(f"unexpected tools: {names}")
print(f"  MCP OK: proto={got[1]['protocolVersion']} tools={names}")
PY

step "6. hook-manifest shape, against the INSTALLED tree"
# The CLI exposes no reload/hook-load surface, so assert the shape that breaks it. #61's defect is a
# `hooks` key in plugin.json: hooks/hooks.json is auto-loaded, and re-declaring it silently drops the
# WHOLE hook set — while still installing, still reporting enabled, and still passing validate --strict.
python3 - "$INSTALL_PATH" <<'PY' || fail "plugin.json hooks-key assertion failed"
import json, sys
root = sys.argv[1]
with open(f"{root}/.claude-plugin/plugin.json", encoding="utf-8") as fh:
    manifest = json.load(fh)
if "hooks" in manifest:
    sys.exit("plugin.json declares `hooks` — hooks/hooks.json is auto-loaded, and re-declaring it "
             "silently drops the entire hook set (upstream issue #61)")
print("  plugin.json has no `hooks` key")
PY
python3 "$INSTALL_PATH/scripts/validate-hooks.py" --root "$INSTALL_PATH" --strict --require-manifest \
    || fail "validate-hooks.py failed against the INSTALLED tree"

printf '\nLOAD CHECK PASSED — installed from this checkout, MCP handshake OK, hook manifest OK\n'
