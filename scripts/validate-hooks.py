#!/usr/bin/env python3
"""validate-hooks.py — COREDEV-2338.

Static integrity check for `hooks/hooks.json`: every hook the plugin declares must
actually be able to FIRE. `validate-plugin-assembly.py` only JSON-loads the manifest, and
`scripts/test-hooks.sh` hardcodes the script paths it exercises — so neither catches a
renamed/missing hook script, an invalid event name (a hook that silently NEVER fires), or
a typo'd tool matcher (a PreToolUse/PostToolUse hook that matches nothing). This does.

Checks:
  * top-level `hooks` is an object;
  * every event key is a real, CC-supported event (KNOWN_EVENTS) — else it never fires;
  * every tool matcher (PreToolUse/PostToolUse/PostToolUseFailure) is a known tool name
    or a valid regex — catches `Bsh`, `Write|Edti`, etc.;
  * every hook entry is `type: command` with a non-empty command and (if present) a
    positive numeric timeout;
  * every command references an existing, non-empty `scripts/<file>`;
  * `bash -n` parses every referenced shell script (tied to the manifest, not the broad
    shellcheck glob).

stdlib ONLY (python3 is already a hard dep via the review-synthesizer MCP).

Usage:
  python3 scripts/validate-hooks.py [--root .] [--strict]
    default   warn  — print problems, exit 0  (pre-commit)
    --strict        — print problems, exit 1  (CI)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Supported Claude Code hook events. Source: https://code.claude.com/docs/en/hooks.md and
# https://code.claude.com/docs/en/plugins-reference.md (verified 2026-06-27, Claude Code
# 2.1.x). An event NOT in this set will silently never fire. If CI fails here on an event
# you intend to use, confirm it against the docs above and add it in the SAME PR.
KNOWN_EVENTS = {
    "SessionStart", "SessionEnd", "Setup",
    "UserPromptSubmit", "UserPromptExpansion",
    "PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch",
    "PermissionRequest", "PermissionDenied",
    "Notification", "MessageDisplay",
    "Stop", "StopFailure",
    "SubagentStart", "SubagentStop",
    "PreCompact", "PostCompact",
    "CwdChanged", "FileChanged",
}

# Events whose `matcher` selects a TOOL by name — a typo'd tool name = a dead hook.
TOOL_MATCHER_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure"}

# Core Claude Code tool names a tool-matcher may reference. MCP tools use the
# `mcp__server__tool` form and are matched via regex (the regex branch below), so they are
# allowed through without being enumerated here. If a new core tool is added, list it here.
KNOWN_TOOLS = {
    "Task", "Bash", "Glob", "Grep", "Read", "Edit", "MultiEdit", "Write",
    "NotebookEdit", "WebFetch", "WebSearch", "TodoWrite", "ExitPlanMode",
}

# A matcher of the simple `Tool|Tool|…` alternation form (no regex metacharacters): each
# token must be a real tool name, so this is where tool-name typos are caught.
SIMPLE_ALT = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:\|[A-Za-z][A-Za-z0-9]*)*$")
SCRIPT_REF = re.compile(r"scripts/([A-Za-z0-9._-]+)")


def validate_matcher(event: str, matcher: str, where: str, problems: list[str]) -> None:
    """Validate a hook matcher. Empty == match-all (always valid)."""
    if matcher == "":
        return
    # Claude Code matches `matcher` as a regex, so it must compile (catches `^(Read`,
    # unbalanced groups, etc.). Checked for EVERY event, not just tool-matcher ones.
    try:
        re.compile(matcher)
    except re.error as exc:
        problems.append(f"{where}: matcher {matcher!r} is not a valid regex ({exc})")
        return
    if event not in TOOL_MATCHER_EVENTS:
        # Stop / SessionStart / SubagentStart|Stop / … take empty or agent-type/source
        # matchers (open-ended) — a compilable value is all we can assert.
        return
    # Tool-name typo trap, ONLY for the simple `Tool|Tool|…` form. A matcher that uses
    # regex syntax (anchors, groups, `.`, `*`, …) is taken as an intentional pattern and
    # only compile-checked above — we cannot distinguish a regex typo (`Edti.*`) from
    # intent, so grouped regexes like `^(Read|Write)$` are accepted, never falsely rejected.
    if not SIMPLE_ALT.match(matcher):
        return
    for token in matcher.split("|"):
        if token not in KNOWN_TOOLS:
            problems.append(
                f"{where}: matcher token {token!r} is not a known tool — it will match nothing "
                f"(known: {', '.join(sorted(KNOWN_TOOLS))}; if it is a new tool, add it to KNOWN_TOOLS)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate hooks/hooks.json manifest integrity.")
    ap.add_argument("--root", default=None, help="plugin repo root (default: parent of scripts/)")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on any problem (CI)")
    ap.add_argument("--require-manifest", action="store_true",
                    help="treat a missing hooks/hooks.json as a problem (CI for a plugin that ships hooks)")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    manifest = root / "hooks" / "hooks.json"
    problems: list[str] = []

    # A plugin need not ship hooks — absence is valid by default. Under --require-manifest
    # (CI for a plugin known to ship hooks) a missing manifest is a problem: deleting it
    # would silently disable every declared hook event while the path-hardcoded harness
    # could still pass.
    if not manifest.is_file():
        if args.require_manifest:
            print("hooks: 1 problem(s):")
            print("  ❌ hooks/hooks.json is MISSING — --require-manifest set; all declared hook "
                  "events would be disabled.")
            if args.strict:
                print("— failing (strict).")
                return 1
            print("— warn mode (not blocking; pass --strict to enforce).")
            return 0
        print("✅ OK — no hooks/hooks.json (plugin ships no hooks)")
        return 0

    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        print(f"hooks: hooks/hooks.json — invalid JSON ({exc})")
        return 1 if args.strict else 0

    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        problems.append("hooks/hooks.json: top-level `hooks` object missing or not an object")
        hooks = {}

    events = 0
    invocations = 0
    referenced: set[Path] = set()

    for event, entries in hooks.items():
        events += 1
        where_ev = f"hooks.{event}"
        if event not in KNOWN_EVENTS:
            problems.append(
                f"{where_ev}: unknown hook event {event!r} — it will NEVER fire. If this is a "
                f"newly-supported Claude Code event, verify against the docs URL in this script "
                f"and add it to KNOWN_EVENTS.")
        if not isinstance(entries, list):
            problems.append(f"{where_ev}: value must be a list of hook entries")
            continue
        for idx, entry in enumerate(entries):
            where = f"{where_ev}[{idx}]"
            if not isinstance(entry, dict):
                problems.append(f"{where}: entry must be an object")
                continue
            matcher = entry.get("matcher", "")
            if not isinstance(matcher, str):
                problems.append(f"{where}: `matcher` must be a string")
            else:
                validate_matcher(event, matcher, where, problems)
            hlist = entry.get("hooks")
            if not isinstance(hlist, list) or not hlist:
                problems.append(f"{where}: `hooks` must be a non-empty list")
                continue
            for hidx, hook in enumerate(hlist):
                whereh = f"{where}.hooks[{hidx}]"
                if not isinstance(hook, dict):
                    problems.append(f"{whereh}: must be an object")
                    continue
                invocations += 1
                if hook.get("type") != "command":
                    problems.append(
                        f"{whereh}: unsupported hook type {hook.get('type')!r} (expected 'command')")
                timeout = hook.get("timeout")
                if "timeout" in hook and not (isinstance(timeout, (int, float))
                                              and not isinstance(timeout, bool) and timeout > 0):
                    problems.append(f"{whereh}: `timeout` must be a positive number")
                cmd = hook.get("command", "")
                if not isinstance(cmd, str) or not cmd.strip():
                    problems.append(f"{whereh}: `command` missing/empty")
                    continue
                m = SCRIPT_REF.search(cmd)
                if not m:
                    problems.append(f"{whereh}: command references no scripts/<file> ({cmd!r})")
                    continue
                spath = root / "scripts" / m.group(1)
                if not spath.is_file():
                    problems.append(f"{whereh}: references missing script scripts/{m.group(1)}")
                elif spath.stat().st_size == 0:
                    problems.append(f"{whereh}: references empty script scripts/{m.group(1)}")
                else:
                    referenced.add(spath)

    # `bash -n` every referenced shell script (parse check tied to the manifest).
    bash = shutil.which("bash")
    parsed = 0
    if bash:
        for spath in sorted(referenced):
            try:
                res = subprocess.run([bash, "-n", str(spath)], capture_output=True, text=True)
            except OSError as exc:
                problems.append(f"scripts/{spath.name}: could not run bash -n ({exc})")
                continue
            parsed += 1
            if res.returncode != 0:
                problems.append(f"scripts/{spath.name}: bash -n failed ({res.stderr.strip()})")
    else:
        print("  (note: bash not found — skipped `bash -n` parse checks)")

    summary = (f"{events} events, {invocations} invocations, "
               f"{len(referenced)} scripts, {parsed} parse-checked")
    if not problems:
        print(f"✅ OK — hooks manifest ({summary})")
        return 0

    print(f"hooks: {len(problems)} problem(s) [{summary}]:")
    for problem in problems:
        print(f"  ❌ {problem}")
    if args.strict:
        print("— failing (strict).")
        return 1
    print("— warn mode (not blocking; pass --strict to enforce).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
