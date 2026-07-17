#!/usr/bin/env python3
"""validate-plugin-assembly.py — Phase 0, Item 2 (COREDEV-2322).

Treats the unleashed-mail plugin's own assets as software: every agent/skill/command
must have well-formed YAML frontmatter, and every JSON manifest must parse. Catches the
silent-load-failure class (a dropped `description` => a skill that never auto-triggers; a
non-kebab name; an unparseable manifest) at commit/PR time instead of at runtime.

Design constraints (from the plan):
  * stdlib ONLY — no PyYAML (python3 is already a hard dep via the review-synthesizer MCP).
    Frontmatter is hand-parsed (top-level keys + block scalars), which is all we need here.
  * unleashed uses Claude Code AUTO-DISCOVERY, so there is NO "registered in plugin.json"
    cross-check (plugin.json does not list agents/skills/commands) — that octo check would
    false-positive here and is deliberately omitted.

Required frontmatter (verified against the repo):
  * agents/*.md         -> name (kebab-case) + description
  * skills/*/SKILL.md   -> name (kebab-case) + description
  * commands/*.md       -> description   (name is derived from the FILENAME; the stem must be kebab-case)

Usage:
  python3 scripts/validate-plugin-assembly.py [--root .] [--strict]
    default     warn  — print problems, exit 0  (pre-commit)
    --strict          — print problems, exit 1  (CI)
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOP_KEY = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")  # column-0 key: value

# Documented sub-agent frontmatter fields (code.claude.com/docs/en/sub-agents, 2026-07-14).
# `allowed-tools` is DELIBERATELY absent: it is a skills/commands key, NOT a sub-agent key —
# using it in an agent silently nullifies every tool restriction (the agent inherits ALL tools).
# This whole check exists to stop that recurring (audit pm-diagnostic.1 / orchestration.1).
KNOWN_AGENT_KEYS = {
    "name", "description", "tools", "disallowedTools", "model", "permissionMode",
    "maxTurns", "skills", "mcpServers", "hooks", "memory", "background",
    "effort", "isolation", "color", "initialPrompt",
}
MODEL_ALIASES = {"sonnet", "opus", "haiku", "fable", "inherit"}
# Built-in tool names an agent may list. The MCP namespace is install-defined and NOT
# enumerable, so `mcp__*` entries are always accepted; an unknown non-mcp entry is accepted
# too (it may be a newer tool), but a CLOSE typo of a known tool is flagged — a misspelled
# tool name silently disables that tool (mirrors validate-hooks.py's difflib guard).
KNOWN_TOOLS = {
    "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "BashOutput",
    "Glob", "Grep", "Agent", "WebFetch", "WebSearch", "TodoWrite",
    "Skill", "SlashCommand", "ExitPlanMode", "KillShell", "AskUserQuestion",
}

# B4 (COREDEV-2503): stale/invalid tool names to HARD-reject. Merely dropping `Task` from KNOWN_TOOLS is a
# no-op — an unknown tool is accepted unless `difflib` finds a close match, and `Task` has none. The
# sub-agent dispatcher is `Agent`, never `Task` (AGENT_CONTRACTS §9; validate-hooks.py agrees).
STALE_TOOLS = {"Task"}


def check_agent_fields(rel: Path, fm: dict[str, str], problems: list[str]) -> None:
    """Agent-only frontmatter validation: unknown keys, model alias, tool-name typos.

    Skills/commands are intentionally exempt — `allowed-tools` is a real key for them.
    """
    for key in fm:
        if key in KNOWN_AGENT_KEYS:
            continue
        hint = ""
        if key == "allowed-tools":
            hint = (" — `allowed-tools` is a skills/commands key; sub-agents use "
                    "`tools`/`disallowedTools`. As written the restriction is silently "
                    "ignored and the agent inherits ALL tools.")
        problems.append(f"{rel}: unknown agent frontmatter key `{key}`{hint}")

    model = fm.get("model", "")
    # A concrete model id (e.g. `claude-opus-4-8`) is allowed; a bare unknown alias is not. F10
    # (COREDEV-2503): `re.fullmatch` anchors BOTH ends — the prior `re.match` (start-only, no end anchor)
    # accepted a valid prefix + trailing garbage/newline (`claude-opus-4-8 rm -rf`). `\Z`-style fullmatch,
    # not `$` (which allows a terminal newline). The trailing `[a-z0-9-]*` allows ids ending in a letter.
    if model and model not in MODEL_ALIASES and not re.fullmatch(r"[a-z]+-[a-z0-9-]*\d[a-z0-9-]*", model):
        problems.append(
            f"{rel}: `model: {model}` is not a known alias {sorted(MODEL_ALIASES)} or a model id")

    for field in ("tools", "disallowedTools"):
        val = fm.get(field, "")
        if val in ("", ">", "|", ">-", "|-"):
            continue
        for entry in (t.strip() for t in val.split(",")):
            if not entry or entry.startswith("mcp__") or entry in KNOWN_TOOLS:
                continue
            if entry in STALE_TOOLS:  # B4: hard-reject a known-stale name (difflib wouldn't flag it)
                problems.append(f"{rel}: `{field}` entry `{entry}` is a stale/invalid tool name — the "
                                f"sub-agent dispatcher is `Agent`, not `{entry}` (AGENT_CONTRACTS §9)")
                continue
            near = difflib.get_close_matches(entry, KNOWN_TOOLS, n=1, cutoff=0.7)
            if near:
                problems.append(f"{rel}: `{field}` entry `{entry}` looks like a typo of `{near[0]}`")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Return {key: value} for the leading `---`…`---` block, or None if absent.

    Handles inline values and block scalars (`key: >` / `key: |` followed by indented
    lines): such a key is recorded with a non-empty sentinel if it has indented content.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fm: dict[str, str] = {}
    i, n = 1, len(lines)
    current: str | None = None
    while i < n:
        line = lines[i]
        if line.strip() == "---":
            return fm
        m = TOP_KEY.match(line)
        if m and not line[:1].isspace():
            key, val = m.group(1), m.group(2).strip()
            # Quoted value: extract up to the matching closing quote, dropping any
            # trailing ` # comment` (a `#` inside the quotes is literal). This must
            # handle `name: "x" # note`, where the value no longer *ends* with a quote
            # (codex/gemini PR #11). Unquoted: strip a YAML comment so `description: #
            # TODO` reads as empty and `name: good-agent # note` validates.
            if val[:1] in ('"', "'"):
                end = val.find(val[0], 1)
                if end != -1:
                    val = val[1:end].strip()
                else:
                    # Unterminated quote (`description: "unfinished`) is malformed YAML;
                    # treat as empty so the required-field check flags it (codex PR #11).
                    val = ""
            elif val.startswith("#"):
                val = ""
            else:
                hashpos = val.find(" #")
                if hashpos != -1:
                    val = val[:hashpos].strip()
            fm[key] = val  # may be "", ">", "|", or an inline value
            current = key
        elif current is not None and line.strip() and line[:1].isspace():
            # continuation / block-scalar body -> the key has content
            if fm.get(current, "") in ("", ">", "|", ">-", "|-"):
                fm[current] = line.strip()
        i += 1
    return None  # no closing '---'


def has(fm: dict[str, str], key: str) -> bool:
    v = fm.get(key, "")
    return v not in ("", ">", "|", ">-", "|-")


# The agent-orchestration skill's "## Agent Registry" section documents every agent in
# markdown tables. Its first column (a `backtick`-wrapped agent name) must be EXACTLY the set
# of agents/*.md stems — so a new/renamed/removed agent can't drift out of the orchestration
# doc, and no table row can name an agent that doesn't exist (audit orchestration.2 / P1c-10).
REGISTRY_ROW = re.compile(r"^\|\s*`([a-z][a-z0-9-]*)`\s*\|")


def check_agent_registry(root: Path, agent_names: set[str], problems: list[str]) -> None:
    reg = root / "skills" / "agent-orchestration" / "SKILL.md"
    rel = "skills/agent-orchestration/SKILL.md"
    if not reg.is_file():
        problems.append(f"{rel}: missing (the agent registry lives here)")
        return
    try:
        content = reg.read_text(encoding="utf-8-sig")
    except OSError as e:
        problems.append(f"{rel}: cannot read ({e})")
        return
    # Capture the "## Agent Registry" section: its heading through the next top-level "## ".
    # Sub-headings ("### …") stay inside the section; only a new "## " ends it. Collect rows in a
    # LIST (not a set) so a name registered twice — possibly with contradictory guidance in each
    # row — is caught rather than silently collapsing.
    in_section = False
    rows: list[str] = []
    for ln in content.splitlines():
        if ln.startswith("## "):
            in_section = ln.strip() == "## Agent Registry"
            continue
        if in_section:
            m = REGISTRY_ROW.match(ln)
            if m:
                rows.append(m.group(1))
    registered = set(rows)
    for name in sorted({n for n in rows if rows.count(n) > 1}):
        problems.append(f"{rel}: agent `{name}` is listed more than once in the Agent Registry tables")
    for name in sorted(agent_names - registered):
        problems.append(f"{rel}: agent `{name}` is missing from the Agent Registry tables")
    for name in sorted(registered - agent_names):
        problems.append(f"{rel}: Agent Registry lists `{name}` but agents/{name}.md does not exist")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate unleashed-mail plugin assets.")
    ap.add_argument("--root", default=None, help="plugin repo root (default: parent of scripts/)")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on any problem (CI)")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    problems: list[str] = []

    def check_frontmatter(path: Path, require_name: bool, is_agent: bool = False) -> None:
        rel = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8-sig")  # utf-8-sig strips a BOM (PR #11)
        except OSError as e:
            problems.append(f"{rel}: cannot read ({e})")
            return
        fm = parse_frontmatter(text)
        if fm is None:
            problems.append(f"{rel}: missing or unterminated YAML frontmatter (`---` block)")
            return
        if not has(fm, "description"):
            problems.append(f"{rel}: frontmatter missing non-empty `description`")
        if require_name:
            if not has(fm, "name"):
                problems.append(f"{rel}: frontmatter missing non-empty `name`")
            elif not KEBAB.match(fm["name"]):
                problems.append(f"{rel}: `name: {fm['name']}` is not kebab-case")
        if is_agent:
            check_agent_fields(rel, fm, problems)
            # The frontmatter `name` is the identifier Claude Code registers; if it diverges from the
            # filename stem, the registry set-equality check (keyed on stems) would enforce the wrong
            # identifier. Require them equal.
            if has(fm, "name") and fm["name"] != path.stem:
                problems.append(f"{rel}: agent `name: {fm['name']}` != filename stem `{path.stem}`")

    # agents/*.md and skills/*/SKILL.md require name+description.
    agents = sorted((root / "agents").glob("*.md"))
    skills = sorted((root / "skills").glob("*/SKILL.md"))
    commands = sorted((root / "commands").glob("*.md"))

    for p in agents:
        check_frontmatter(p, require_name=True, is_agent=True)
    # The orchestration registry must list exactly the set of agents that exist.
    check_agent_registry(root, {p.stem for p in agents}, problems)
    for p in skills:
        check_frontmatter(p, require_name=True)
    # commands: name is the filename — require description + a kebab-case stem.
    for p in commands:
        check_frontmatter(p, require_name=False)
        if not KEBAB.match(p.stem):
            problems.append(f"{p.relative_to(root)}: command filename stem `{p.stem}` is not kebab-case")

    # JSON manifests must parse. plugin.json + marketplace.json are required;
    # .mcp.json + hooks/hooks.json are optional — validated only when present (the
    # plan lists hooks.json as JSON-loaded; PR #11). `ValueError` also catches a
    # UTF-8 BOM/decode error, not just `JSONDecodeError` (which subclasses it).
    required_manifests = [
        root / ".claude-plugin" / "plugin.json",
        root / ".claude-plugin" / "marketplace.json",
    ]
    optional_manifests = [
        root / ".mcp.json",
        root / "hooks" / "hooks.json",
    ]
    parsed = 0
    total_manifests = len(required_manifests)
    for m in required_manifests:
        if not m.exists():
            problems.append(f"{m.relative_to(root)}: missing")
            continue
        try:
            data = json.loads(m.read_text(encoding="utf-8-sig"))
            parsed += 1
        except (OSError, ValueError) as e:
            problems.append(f"{m.relative_to(root)}: invalid JSON ({e})")
            continue
        # The plugin manifest must carry its required metadata, not merely be valid
        # JSON (plan Item 2; codex PR #11). version is also gated by version-sync.
        if m.name == "plugin.json":
            if not isinstance(data, dict):
                problems.append(f"{m.relative_to(root)}: not a JSON object")
            else:
                for field in ("name", "version", "description"):
                    fv = data.get(field)
                    if not (isinstance(fv, str) and fv.strip()):
                        problems.append(f"{m.relative_to(root)}: missing/empty required field `{field}`")
    for m in optional_manifests:
        if not m.is_file():
            continue
        total_manifests += 1
        try:
            json.loads(m.read_text(encoding="utf-8-sig"))
            parsed += 1
        except (OSError, ValueError) as e:
            problems.append(f"{m.relative_to(root)}: invalid JSON ({e})")

    summary = (f"{len(agents)} agents, {len(skills)} skills, {len(commands)} commands, "
               f"{parsed}/{total_manifests} manifests")
    if not problems:
        print(f"✅ OK — plugin assembly ({summary})")
        return 0

    print(f"plugin-assembly: {len(problems)} problem(s) [{summary}]:")
    for p in problems:
        print(f"  ❌ {p}")
    if args.strict:
        print("— failing (strict).")
        return 1
    print("— warn mode (not blocking; pass --strict to enforce).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
