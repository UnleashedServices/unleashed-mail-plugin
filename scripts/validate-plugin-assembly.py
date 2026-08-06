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
import os
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
# §4.4 (COREDEV-2583): transcribed VERBATIM from Claude Code 2.1.220's alias table (`h1e`),
# plus `inherit` — a sub-agent-only value the runtime handles separately and which is NOT in
# that table. Re-check this set on every CLI pin bump (.github/workflows/plugin-ci.yml).
#   h1e = ["sonnet","opus","haiku","fable","best","sonnet[1m]","opus[1m]","fable[1m]","opusplan"]
# Note there is NO `default`, and only sonnet/opus/fable take the `[1m]` long-context suffix.
# The bracketed forms are LITERAL set members, never synthesised by stripping a suffix — a
# "strip then re-validate the base" rule would over-accept haiku[1m]/best[1m]/opusplan[1m]/
# inherit[1m], none of which the runtime recognises. The model-id regex below is unchanged, so
# COREDEV-2503 F10 anchoring is untouched: a supported bracketed alias short-circuits on exact
# membership, and an unsupported one falls through and is rejected because the regex character
# class contains no `[`/`]`.
MODEL_ALIASES = {
    "sonnet", "opus", "haiku", "fable", "best", "opusplan",
    "sonnet[1m]", "opus[1m]", "fable[1m]",
    "inherit",
}
# Built-in tool names an agent may list. The MCP namespace is install-defined and NOT
# enumerable, so `mcp__*` entries are always accepted; an unknown non-mcp entry is accepted
# too (it may be a newer tool), but a CLOSE typo of a known tool is flagged — a misspelled
# tool name silently disables that tool (mirrors validate-hooks.py's difflib guard).
KNOWN_TOOLS = {
    "Read", "Write", "Edit", "NotebookEdit", "Bash", "BashOutput",
    "Glob", "Grep", "Agent", "WebFetch", "WebSearch", "TodoWrite",
    "Skill", "SlashCommand", "EnterPlanMode", "ExitPlanMode", "KillShell", "AskUserQuestion",
    # §4.5 (COREDEV-2583): current built-ins that were previously accepted only as "unknown",
    # two of which the difflib guard actively FALSE-REJECTED (`TaskOutput` as a typo of
    # `BashOutput`, `EnterPlanMode` of `ExitPlanMode`).
    "TaskOutput", "TaskStop", "ToolSearch", "Monitor", "SendMessage", "Artifact",
    "EnterWorktree", "ExitWorktree", "PowerShell", "Workflow", "ScheduleWakeup",
    "CronCreate", "CronList", "CronDelete",
}

# B4 (COREDEV-2503): stale/invalid tool names to HARD-reject. Merely dropping `Task` from KNOWN_TOOLS is a
# no-op — an unknown tool is accepted unless `difflib` finds a close match, and `Task` has none. The
# sub-agent dispatcher is `Agent`, never `Task` (AGENT_CONTRACTS §9; validate-hooks.py agrees).
# §4.5 (COREDEV-2583) adds `MultiEdit`: it is no longer a real tool, and merely DROPPING it from
# KNOWN_TOOLS is a no-op for the same reason `Task` was — an unknown entry is accepted, and
# difflib finds no close match. Without the hard reject, the live deny-list entry at
# agents/jira-manager.md:15 would stay a silent no-op line.
STALE_TOOLS = {"Task", "MultiEdit"}
# Why each name is rejected — a shared message would be FALSE for one of them ("the dispatcher
# is `Agent`, not `MultiEdit`" is nonsense). Keyed lowercase to match the case-insensitive check.
_STALE_TOOL_REASONS = {
    "task": "the sub-agent dispatcher is `Agent`, not `Task` (AGENT_CONTRACTS §9)",
    "multiedit": "`MultiEdit` was removed from Claude Code; use `Edit` (COREDEV-2583 §4.5)",
}
_STALE_TOOLS_LOWER = {t.lower() for t in STALE_TOOLS}   # case-insensitive membership (gemini review #53)


# §4.6 (COREDEV-2583): DERIVED from Claude Code 2.1.220's skill/command frontmatter schema,
# not hand-written. The schema runs from `name` to `improved_by`; the agent schema begins after
# it (its own `name` is described "Agent identifier"). Re-derive on every CLI pin bump.
#
# `disallowedTools` IS legal here — the runtime declares it verbatim as "Canonical (normalized)
# alias of `disallowed-tools`". An earlier draft of this ticket asserted the opposite and would
# have REJECTED A LEGAL FIELD. `allowedTools` is the genuinely inert camelCase form: a
# delimiter-anchored search of the same schema finds no such key at all.
KNOWN_SKILL_KEYS = {
    "name", "description", "model",
    "allowed-tools", "disallowed-tools", "disallowedTools",
    "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable",
    "effort", "shell", "version", "when_to_use", "paths",
    "agent", "context", "background", "hooks", "fallback",
    "created_by", "improved_by",
    # accepted in the wild and harmless; not worth false-rejecting over
    "license", "metadata",
}


def check_skill_fields(rel: Path, fm: dict[str, str], problems: list[str],
                       warnings: list[str]) -> None:
    """Skill/command frontmatter validation (§4.6).

    Deliberately NOT symmetric with `check_agent_fields`: an unknown key here is a WARNING,
    not a problem. `KNOWN_SKILL_KEYS` is derived from one pinned CLI and the surface moves, so
    a hard reject would block a legitimate new key in CI — the same trade §4.5 settled for
    `KNOWN_TOOLS`. Only the one key proven inert gets a hard error.
    """
    check_model_reachable_grants(rel, fm, problems, warnings)

    for key in fm:
        if key in KNOWN_SKILL_KEYS:
            continue
        if key == "allowedTools":
            problems.append(
                f"{rel}: `allowedTools` is not a skill key and is silently IGNORED — the "
                f"kebab form `allowed-tools` is the real one. (Note `disallowedTools` IS a "
                f"legal alias of `disallowed-tools`; only the 'allowed' side is inert.)")
            continue
        warnings.append(f"{rel}: unknown skill frontmatter key `{key}` (advisory — the skill "
                        f"schema moves between CLI releases; verify against the pinned version)")


# Grants that must never appear on a MODEL-REACHABLE skill. Every tool a skill lists is pre-approved
# with no user gesture, and a model-invocable skill can be entered by the model's own decision — one
# that content in a reviewed file can steer. So a broad grant here is not "convenience", it is a
# capability handed to an attacker-influenceable path (deep review, P1).
#
# An ALLOWLIST of shapes would be wrong here: the danger is unbounded breadth, and breadth has many
# spellings. This is a deny-list of the specific unbounded forms, each with the reason it is unbounded.
BROAD_MODEL_REACHABLE_GRANTS = {
    "Write": "bare `Write` pre-approves writing ANY path — scope it, e.g. `Write(docs/planning/**)`",
    "Edit": "bare `Edit` pre-approves editing ANY path — scope it",
    "NotebookEdit": "bare `NotebookEdit` pre-approves editing any notebook — scope it",
    "Bash": "bare `Bash` pre-approves EVERY command",
    "Agent": (
        "bare `Agent` pre-approves spawning ANY subagent, including ones that write files — "
        "enumerate the types this body actually spawns, e.g. `Agent(db-engineer)`"
    ),
}

# Command prefixes that are unbounded even when written as `Bash(... *)`. A VCS wildcard is the worst
# of these: `Bash(git *)` is every git command, including `reset --hard`, `clean` and `push`, plus the
# git-to-shell trampolines (aliases, `-c core.pager=…`). A bare interpreter or reviewer-CLI wildcard is
# the same problem one layer down.
BROAD_BASH_PREFIXES = {
    "git": "every git command, including reset/clean/push — call an audited read-only wrapper instead",
    "gh": "every GitHub CLI command, including merges and releases",
    "codex": "any codex invocation, including `-s danger-full-access`, outside every wrapper",
    "agy": "any agy invocation outside the isolation harness — agy has NO read-only mode",
    "kimi": "any kimi invocation outside a harness",
    "rm": "unbounded deletion",
    "sudo": "privilege escalation",
}


def _normalized_command_words(specifier: str) -> list[str]:
    """The specifier's words with shell wrappers stripped and the executable reduced to a basename.

    The deny-list compared the FIRST token literally, so every one of `Bash(env git *)`,
    `Bash(command git *)`, `Bash(GIT_DIR=/tmp git *)` and `Bash(/usr/bin/git *)` spelled an unbounded
    git grant that validation accepted — `command` is not `git` (deep review, P2). All four were
    exercised against the checker and produced no problem.

    Deliberately conservative: it unwraps only the prefixes that are themselves command runners or
    assignments, and stops at the first real word. It is not a shell parser, and a grant that needs
    one is a grant that should not be written.
    """
    words = specifier.strip().split()
    # `sudo`/`doas` are deliberately NOT unwrapped — they are themselves in the deny-list, so leaving
    # them as the resolved command rejects them outright.
    wrappers = {"env", "command", "builtin", "exec", "nohup", "time", "nice", "xargs"}
    index = 0
    while index < len(words):
        word = words[index]
        # `VAR=value` assignments precede the command they run.
        if "=" in word and not word.startswith("-") and word.split("=", 1)[0].isidentifier():
            index += 1
            continue
        base = word.rsplit("/", 1)[-1]
        if base in wrappers:
            # A FLAGGED wrapper is not analysable without knowing which flags take arguments — my
            # first version skipped `-u` but not its operand, so `sudo -u x git *` resolved to `x`
            # and was accepted. Refuse rather than guess: `None` means "cannot normalize", and the
            # caller rejects. A grant that needs a shell parser is a grant not worth writing.
            if index + 1 < len(words) and words[index + 1].startswith("-"):
                return None
            index += 1
            continue
        return [base] + words[index + 1:]
    return []


def _bash_specifiers(value: str) -> list[str]:
    """Every `Bash(...)` specifier in an `allowed-tools` value."""
    return re.findall(r"Bash\(([^)]*)\)", value)


# Trampolines: a wildcard on these runs arbitrary code one layer down (`xcrun python3 …`, `swift run`,
# an xcodebuild Run-Script phase). They are ADVISORY rather than hard failures because they are the
# build tooling these skills exist to describe, and failing them would trade a real workflow for a
# theoretical one. Surfaced so the breadth is a decision rather than an oversight.
TRAMPOLINE_BASH_PREFIXES = {
    "xcrun": "runs any tool in the toolchain, e.g. `xcrun python3 -c …`",
    "swift": "`swift run` executes arbitrary package code",
    "xcodebuild": "build phases execute arbitrary Run-Script code",
}


_INTERPRETERS = ("bash", "sh", "zsh", "python3", "python", "perl", "ruby", "node")
# `-c` code, `-m` module, `-` stdin: the shapes that turn an interpreter grant into arbitrary execution.
_INTERPRETER_CODE_MODES = ("-c", "-m", "-i", "-e", "--command", "--eval")


def _wildcard_bash_problem(specifier: str) -> str | None:
    """DEFAULT-DENY. Return why this wildcard grant is refused, or None if it is on the allowlist.

    THE POLICY THIS REPLACES WAS FAIL-OPEN, AND MEASURED SO (PR #63 recheck, P2).
    The old rule deny-listed a fixed set of command names — git, gh, codex, agy, kimi, rm, sudo — and
    let everything else through. Exact probes producing NO problem and NO warning included:

        Bash(python3 -c *)   Bash(sh -c *)   Bash(cp *)   Bash(mv *)
        Bash(tee *)          Bash(find *)    Bash(curl *) Bash(chmod *)

    `python3 -c *` is arbitrary code execution; the interpreter special-case only looked for a wildcard
    in the SCRIPT PATH, and `-c` is not a path, so it fell through the `continue`. A policy advertised
    in the CHANGELOG as "a new, enforced capability" that accepts `sh -c *` enforces very little, and
    the release notes leaned on that claim to justify a minor bump.

    So the shape is inverted: a wildcard `Bash` grant on a model-reachable skill is REFUSED unless it
    is an interpreter invoking an EXACT script beneath `${CLAUDE_PLUGIN_ROOT}`. Those wrappers are in
    this repo, reviewed with it, and each one contains its own operands — which is the property that
    makes the trailing `*` acceptable there and nowhere else. Adding a new allowed shape now requires
    editing this function, which is the point: the list is the decision record.
    """
    head = _normalized_command_words(specifier)
    if head is None:
        return ("a flagged command wrapper cannot be analysed safely, so it is refused. "
                "Name the command directly.")
    if not head:
        return "the grant has no command at all, so it pre-approves anything"

    command = head[0]
    if command in _INTERPRETERS:
        if len(head) < 2:
            return f"a bare `{command}` wildcard pre-approves any program it can be asked to run"
        target = head[1]
        # Code/module/stdin modes are the arbitrary-execution shapes. They are NOT script paths, and
        # the previous rule's "is there a `*` in the path" question never applied to them.
        if target in _INTERPRETER_CODE_MODES or target == "-" or target.startswith("-"):
            return (f"`{command} {target}` is an interpreter code/module/stdin mode — that is "
                    "arbitrary code execution, not a call to a reviewed script")
        if "*" in target:
            return ("the wildcard is in the SCRIPT PATH, so it pre-approves every script in that "
                    "directory (including destructive ones). Name the exact entrypoint.")
        if "${CLAUDE_PLUGIN_ROOT}/" not in target:
            return (f"only an exact script beneath `${{CLAUDE_PLUGIN_ROOT}}` may carry a trailing "
                    f"wildcard; `{target}` is outside the plugin and is not reviewed with it")
        return None  # the allowlisted shape: exact plugin-root wrapper, operands bounded by the script

    if command in BROAD_BASH_PREFIXES:
        return f"that is {BROAD_BASH_PREFIXES[command]}"
    if command in TRAMPOLINE_BASH_PREFIXES:
        return f"that {TRAMPOLINE_BASH_PREFIXES[command]}"
    # DEFAULT DENY. Everything not named above lands here — which is the whole correction.
    return (f"wildcard `Bash({command} …)` is not an exact plugin-root wrapper. Model-reachable "
            "grants are default-deny: call a reviewed script under `${CLAUDE_PLUGIN_ROOT}`, or write "
            "the exact command with no wildcard.")


def check_model_reachable_grants(rel: Path, fm: dict[str, str], problems: list[str],
                                 warnings: list[str] | None = None) -> None:
    """Reject broad write/VCS/agent grants on a skill the MODEL can invoke (deep review, P1).

    `disable-model-invocation: true` opts a skill out — a user-invoked-only skill still pre-approves
    its tools, but only after a human typed its name, which is the gesture the model-reachable case
    lacks. Scoped forms are accepted: the check is on unbounded BREADTH, not on the tool.
    """
    if str(fm.get("disable-model-invocation", "")).strip().lower() == "true":
        return
    granted = fm.get("allowed-tools")
    if not granted:
        return

    entries = [entry.strip() for entry in re.split(r",(?![^(]*\))", granted) if entry.strip()]
    for entry in entries:
        if entry in BROAD_MODEL_REACHABLE_GRANTS:
            problems.append(
                f"{rel}: model-invocable skill grants bare `{entry}` — "
                f"{BROAD_MODEL_REACHABLE_GRANTS[entry]}"
            )

    for specifier in _bash_specifiers(granted):
        # Only UNBOUNDED grants are in scope. A specifier with no wildcard pre-approves exactly one
        # command string — `Bash(command -v codex)`, `Bash(codex --version)` — which is bounded by
        # construction and visible in review. Analysing those rejected both of the shipped preflight
        # probes. Whether a bounded-but-dangerous exact command (`Bash(git reset --hard)`) belongs on
        # a model-invocable skill is a DIFFERENT policy and is deliberately not claimed here.
        if "*" not in specifier:
            continue
        problem = _wildcard_bash_problem(specifier)
        if problem is not None:
            problems.append(
                f"{rel}: model-invocable skill grants `Bash({specifier})` — {problem}"
            )


def skill_preload_list(fm: dict[str, str]) -> list[str]:
    """Normalize a `skills:` frontmatter value (inline `[a, b]`, comma, or accumulated block-list) into
    skill names, tolerating an optional `unleashed-mail:`/`<plugin>:` namespace prefix (MIN-22)."""
    raw = fm.get("skills", "")
    if raw in ("", ">", "|", ">-", "|-"):
        return []
    out = []
    for entry in (t.strip().strip("[]").lstrip("-").strip() for t in raw.split(",")):
        if not entry:
            continue
        out.append(entry.split(":", 1)[1] if ":" in entry else entry)  # drop a plugin prefix
    return out


def check_agent_fields(rel: Path, fm: dict[str, str], problems: list[str],
                       warnings: list[str]) -> None:
    """Agent-only frontmatter validation: unknown keys, model alias, tool-name typos.

    Skills/commands are intentionally exempt — `allowed-tools` is a real key for them.

    `problems` FAIL the build under --strict; `warnings` never affect the exit code
    (COREDEV-2583 §4.7). The split exists because two checks here are advisory by design:
    keys Claude Code ignores for plugin sub-agents, and difflib's typo guard over an
    inherently incomplete tool allowlist.
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

    # §4.7: these ARE legal sub-agent keys, but Claude Code IGNORES all three for PLUGIN
    # sub-agents (security). Nothing is broken today — no agent uses them — but they are
    # exactly what someone reaches for when building an autonomous mode, and the failure is
    # silent. Advisory, not a problem: the key itself is valid.
    for key in ("permissionMode", "mcpServers", "hooks"):
        if key in fm:
            warnings.append(
                f"{rel}: `{key}` is IGNORED for plugin sub-agents (Claude Code security "
                f"exemption) — it will silently have no effect. For permissions use a "
                f"PermissionRequest hook in hooks/hooks.json; for MCP scope use "
                f"`disallowedTools`.")

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
        # normalize YAML flow-list (`[Task]`, `[Task, Read]`) and block-list (`- Task`) syntax before the
        # stale/typo checks — the plain `val.split(",")` scalar form otherwise missed `[Task]`/`- Task`,
        # letting a stale `Task` tool through in list form (audit of #53).
        for entry in (t.strip().strip("[]").lstrip("-").strip() for t in val.split(",")):
            if not entry or entry.startswith("mcp__") or entry in KNOWN_TOOLS:
                continue
            if entry.lower() in _STALE_TOOLS_LOWER:  # B4: hard-reject a known-stale name (difflib wouldn't
                # flag it). Case-INSENSITIVE so `task`/`TASK` can't slip past the exact-`Task` check (gemini #53).
                reason = _STALE_TOOL_REASONS.get(entry.lower(), "it is not a valid tool name")
                problems.append(f"{rel}: `{field}` entry `{entry}` is a stale/invalid tool name — {reason}")
                continue
            # §4.5: ADVISORY, not a hard failure. `KNOWN_TOOLS` is inherently incomplete — the
            # built-in surface moves — so a near-miss is as likely to be a NEW tool as a typo. The
            # guard was false-rejecting real tools (`TaskOutput` as a typo of `BashOutput`,
            # `EnterPlanMode` of `ExitPlanMode`). A missed typo merely passes as unknown and fails
            # at runtime; a false reject blocks a legitimate tool in CI. Hard rejection is reserved
            # for the explicit `STALE_TOOLS` set above.
            near = difflib.get_close_matches(entry, KNOWN_TOOLS, n=1, cutoff=0.7)
            if near:
                warnings.append(f"{rel}: `{field}` entry `{entry}` looks like a typo of "
                                f"`{near[0]}` (advisory — if `{entry}` is a real tool, ignore)")


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
    block_scalar_keys: set[str] = set()
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
            if val in (">", "|", ">-", "|-"):
                block_scalar_keys.add(key)           # `key: |`/`>` body is PROSE — space-join, never comma
            current = key
        elif current is not None and line.strip() and (
                line[:1].isspace()
                or (line.lstrip().startswith("- ") and current not in block_scalar_keys)
                or (line.rstrip() == "-" and current not in block_scalar_keys)):
            # continuation / block-scalar body / block-LIST item -> the key has content.
            # MIN-21: a COLUMN-0 block-list item (`tools:\n- Read\n- Task`) is legal YAML that PyYAML and
            # Claude Code read as `['Read','Task']`, but the old `line[:1].isspace()`-only gate dropped the
            # whole list (leaving `tools: ''`), so a stale `Task`/typo in a column-0 list bypassed
            # check_agent_fields. Treat a column-0 `- item` under a non-block-scalar key as a list item too.
            body = line.strip()
            is_list_item = body.startswith("-") and current not in block_scalar_keys
            if is_list_item:                         # block-list item: drop a trailing YAML inline comment
                hp = body.find(" #")                 # (`- Task # legacy`) so it doesn't hide a stale tool
                if hp != -1:
                    body = body[:hp].rstrip()
            if fm.get(current, "") in ("", ">", "|", ">-", "|-"):
                fm[current] = body
            elif is_list_item:
                # ACCUMULATE every subsequent block-LIST item, comma-joined — a multi-line YAML block list
                # (`tools:\n  - Read\n  - Task`) otherwise recorded only its FIRST item, so a stale tool past
                # line 1 escaped validation (gemini #53). Matches the flow-list form.
                fm[current] = fm[current] + ", " + body
            else:
                # a block SCALAR (`description: |`) or wrapped value: SPACE-join, not comma — comma-joining
                # prose corrupts the text (gemini review of #53).
                fm[current] = fm[current] + " " + body
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


# §11 (Model Tiering Policy) in AGENT_CONTRACTS.md files every agent under exactly one `model:` tier.
# MAJ-1: the table drifted from the shipped frontmatter (docs-engineer/jira-manager/release-manager pinned
# `sonnet` while §11 filed them under `inherit`) with no CI signal. Parse the two rows and assert the tier
# equals each agent's frontmatter `model:` (default `inherit`), and that the two sets are the same agents.
_TIER_ROW = re.compile(r"^\|[^|]*\|\s*`([a-z]+)`[^|]*\|\s*([^|]+?)\s*\|\s*$")
_AGENT_TOKEN = re.compile(r"[a-z][a-z0-9-]*")


def check_effort_policy(root: Path, asset_efforts: dict[str, str], problems: list[str]) -> None:
    """§4.3 (COREDEV-2583) — assert the effort FLOOR on BOTH axes and in the policy text.

    The floor is a floor, not a pin. Assets INHERIT the session effort by omitting `effort:`,
    so a `max` session runs its subagents at `max` instead of being silently pulled down to
    `xhigh` — which is what a hard `effort: xhigh` pin did, because frontmatter effort overrides
    the session in BOTH directions (verified against code.claude.com/docs/en/sub-agents).
    What is forbidden is a DOWNWARD pin: if an asset states an effort at all it must be `xhigh`
    or `max`, so no asset can quietly run below the floor.

    Sibling of `check_model_tiering`, and deliberately a HARD assertion rather than a warning: a
    silently under-powered gate is exactly the defect §4.1 exists to close, and it is invisible
    at runtime. With `effort` load-bearing, an asset that silently loses its pin — or a new asset
    landing without one — must fail CI, not merely be noted.

    Mutation proof: pin `effort: high` (or any level below the floor) on any single agent or
    skill, or delete the §11 effort-policy sentence, and strict validation fails naming the file.
    Omitting `effort:` is legal and is the default — that is inheritance, not drift.
    """
    ALLOWED_PINS = {"xhigh", "max"}
    for rel, effort in sorted(asset_efforts.items()):
        if effort and effort not in ALLOWED_PINS:
            problems.append(
                f"{rel}: `effort: {effort}` is BELOW the floor — omit `effort:` to inherit the "
                f"session level, or pin `xhigh`/`max`. A downward pin silently under-powers the "
                f"asset and is invisible at runtime "
                f"(AGENT_CONTRACTS §11 effort policy; COREDEV-2583 §4.1)")

    contracts = root / "AGENT_CONTRACTS.md"
    if not contracts.is_file():
        return                      # check_model_tiering already reports the missing file
    try:
        content = contracts.read_text(encoding="utf-8-sig")
    except OSError:
        return
    # The policy sentence must SAY xhigh — otherwise the docs and the assets could drift apart
    # while both halves individually look fine, which is the §3 failure this ticket exists to end.
    if "no agent or skill pins an effort below `xhigh`" not in content:
        problems.append(
            "AGENT_CONTRACTS.md §11: the effort policy line is missing or does not state "
            "the floor — expected the sentence \"no agent or skill pins an effort below `xhigh`\"")


def check_model_tiering(root: Path, agent_models: dict[str, str], problems: list[str]) -> None:
    contracts = root / "AGENT_CONTRACTS.md"
    rel = "AGENT_CONTRACTS.md"
    if not contracts.is_file():
        problems.append(f"{rel}: missing (the Model Tiering Policy §11 lives here)")
        return
    try:
        content = contracts.read_text(encoding="utf-8-sig")
    except OSError as e:
        problems.append(f"{rel}: cannot read ({e})")
        return
    in_section = False
    tier_of: dict[str, str] = {}
    rows = 0
    for ln in content.splitlines():
        if ln.startswith("## "):
            in_section = ln.strip().startswith("## 11.")
            continue
        if not in_section:
            continue
        m = _TIER_ROW.match(ln)
        if not m:
            continue
        model, agents_cell = m.group(1), m.group(2)
        rows += 1
        for name in _AGENT_TOKEN.findall(agents_cell):
            if name in tier_of and tier_of[name] != model:
                problems.append(f"{rel} §11: `{name}` appears under two tiers (`{tier_of[name]}`/`{model}`)")
            tier_of[name] = model
    if rows < 2:
        problems.append(f"{rel} §11: could not parse the Model Tiering table (found {rows} tier row(s))")
        return
    for stem, model in sorted(agent_models.items()):
        tier = tier_of.get(stem)
        if tier is None:
            problems.append(f"{rel} §11: agent `{stem}` (model: {model}) is missing from the tiering table")
        elif tier != model:
            problems.append(f"{rel} §11: agent `{stem}` is filed under `{tier}` but its frontmatter pins "
                            f"`model: {model}` — align §11 or the agent")
    for name in sorted(set(tier_of) - set(agent_models)):
        problems.append(f"{rel} §11: tiering table lists `{name}` but agents/{name}.md does not exist")


def check_reviewer_roster(root: Path, agent_names: set[str], problems: list[str]) -> None:
    """MIN-16: the five-reviewer roster is hardcoded in six places with no cross-check. A reviewer rename
    edits one (e.g. the SKILL.md registry) and leaves the others stale — the unanchored hooks matchers stop
    matching, capture.py rejects the new name, and swift-reviewer Step-5 exits UNATTRIBUTED for a reviewer
    that ran (fail-closed but undiagnosable). Assert all six agree and each name exists as an agent."""
    sources: dict[str, "set[str] | None"] = {}

    def read(rel: str) -> "str | None":
        try:
            return (root / rel).read_text(encoding="utf-8-sig")
        except OSError:
            return None

    t = read("scripts/review/reviewer-roster.sh")
    if t is not None:
        m = re.search(r'_VALID="([^"]+)"', t)
        sources["reviewer-roster.sh:_VALID"] = set(m.group(1).split()) if m else None

    t = read("mcp/review-synthesizer/capture.py")
    if t is not None:
        m = re.search(r"VALID_AGENTS\s*=\s*\((.*?)\)", t, re.DOTALL)
        sources["capture.py:VALID_AGENTS"] = set(re.findall(r'"([a-z][a-z0-9-]*)"', m.group(1))) if m else None

    t = read("hooks/hooks.json")
    if t is not None:
        try:
            data = json.loads(t)
            hooks = data.get("hooks", {}) if isinstance(data, dict) else {}
        except ValueError:
            hooks = {}
        for ev in ("SubagentStart", "SubagentStop"):
            got: "set[str] | None" = None
            entries = hooks.get(ev) if isinstance(hooks.get(ev), list) else []
            for entry in entries:
                matcher = entry.get("matcher", "") if isinstance(entry, dict) else ""
                mm = re.search(r"\(([a-z0-9-]+(?:\|[a-z0-9-]+)+)\)", matcher)
                if mm:
                    got = set(mm.group(1).split("|"))
            sources[f"hooks.json:{ev}"] = got

    for fn in ("scripts/capture-reviewer-round-start.sh", "scripts/capture-reviewer-verdict.sh"):
        t = read(fn)
        if t is not None:
            m = re.search(r"^\s*([a-z][a-z0-9-]*(?:\|[a-z][a-z0-9-]*)+)\)\s*;;", t, re.MULTILINE)
            sources[fn.rsplit("/", 1)[-1] + ":case"] = set(m.group(1).split("|")) if m else None

    for k, v in sources.items():
        if v is None:
            problems.append(f"reviewer-roster: could not extract the reviewer set from `{k}`")
    parsed = {k: v for k, v in sources.items() if v is not None}
    if len(parsed) < 2:
        return
    ref_key = next(iter(parsed))
    ref = parsed[ref_key]
    for k, v in parsed.items():
        if v != ref:
            problems.append(f"reviewer-roster: `{k}` roster {sorted(v)} != `{ref_key}` {sorted(ref)}")
    for name in sorted(ref - agent_names):
        problems.append(f"reviewer-roster: `{name}` is rostered but agents/{name}.md does not exist")


def check_mcp_server_paths(root: Path, problems: list[str]) -> None:
    """MIN-23: .mcp.json is only JSON-parsed; nothing checks that each server's command/args target
    (`${CLAUDE_PLUGIN_ROOT}/mcp/.../mcp_server.py`) resolves to an existing, non-empty file. A path typo
    keeps every validator and the pinned-path MCP test suite green while the shipped server never starts."""
    mcp = root / ".mcp.json"
    if not mcp.is_file():
        return
    try:
        data = json.loads(mcp.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return  # JSON validity is already reported by the manifest loop
    servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
    root_str = str(root)
    for name, cfg in (servers.items() if isinstance(servers, dict) else []):
        if not isinstance(cfg, dict):
            continue
        toks = [cfg["command"]] if isinstance(cfg.get("command"), str) else []
        toks += [a for a in cfg.get("args", []) if isinstance(a, str)] if isinstance(cfg.get("args"), list) else []
        for tok in toks:
            if "${CLAUDE_PLUGIN_ROOT}" not in tok:
                continue
            relpath = tok.replace("${CLAUDE_PLUGIN_ROOT}", "").lstrip("/")
            target = root / relpath
            if not (str(target.resolve()) + os.sep).startswith(root_str + os.sep):
                problems.append(f".mcp.json: server `{name}` target {tok!r} escapes the plugin root")
            elif not target.is_file():
                problems.append(f".mcp.json: server `{name}` references missing file {relpath} ({tok!r})")
            elif target.stat().st_size == 0:
                problems.append(f".mcp.json: server `{name}` references empty file {relpath}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate unleashed-mail plugin assets.")
    ap.add_argument("--root", default=None, help="plugin repo root (default: parent of scripts/)")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on any problem (CI)")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    problems: list[str] = []
    warnings: list[str] = []            # never affect the exit code (COREDEV-2583 §4.7)
    agent_models: dict[str, str] = {}   # stem -> effective model (default "inherit"); fed to §11 tier check
    asset_efforts: dict[str, str] = {}  # rel path -> declared effort (""=absent); fed to the §4.3 check

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
        asset_efforts[str(rel)] = fm.get("effort", "").strip()   # §4.3
        if not is_agent:
            check_skill_fields(rel, fm, problems, warnings)   # §4.6
        if is_agent:
            check_agent_fields(rel, fm, problems, warnings)
            # The frontmatter `name` is the identifier Claude Code registers; if it diverges from the
            # filename stem, the registry set-equality check (keyed on stems) would enforce the wrong
            # identifier. Require them equal.
            if has(fm, "name") and fm["name"] != path.stem:
                problems.append(f"{rel}: agent `name: {fm['name']}` != filename stem `{path.stem}`")
            # Record the effective model (omitted `model:` defaults to `inherit`) for the §11 tier check.
            agent_models[path.stem] = fm.get("model", "").strip() or "inherit"
        # MIN-22: a `skills:` preload must resolve to skills/<name>/SKILL.md on disk, else the preload
        # silently never happens (a typo'd/renamed skill ships with no CI signal — the silent-load-failure
        # class this validator exists to catch). Applies to agents (and any skill that preloads siblings).
        for skill_name in skill_preload_list(fm):
            if not (root / "skills" / skill_name / "SKILL.md").is_file():
                problems.append(f"{rel}: `skills:` preload `{skill_name}` has no skills/{skill_name}/SKILL.md")

    # agents/*.md and skills/*/SKILL.md require name+description.
    agents = sorted((root / "agents").glob("*.md"))
    skills = sorted((root / "skills").glob("*/SKILL.md"))
    commands = sorted((root / "commands").glob("*.md"))

    for p in agents:
        check_frontmatter(p, require_name=True, is_agent=True)
    # The orchestration registry must list exactly the set of agents that exist.
    check_agent_registry(root, {p.stem for p in agents}, problems)
    # §11 Model Tiering must equal the shipped frontmatter (MAJ-1); the reviewer roster must agree across
    # its six hardcoded copies (MIN-16); .mcp.json server paths must resolve on disk (MIN-23).
    check_model_tiering(root, agent_models, problems)
    check_reviewer_roster(root, {p.stem for p in agents}, problems)
    check_mcp_server_paths(root, problems)
    for p in skills:
        check_frontmatter(p, require_name=True)
    # commands: name is the filename — require description + a kebab-case stem.
    for p in commands:
        check_frontmatter(p, require_name=False)
        if not KEBAB.match(p.stem):
            problems.append(f"{p.relative_to(root)}: command filename stem `{p.stem}` is not kebab-case")

    # §4.3 MUST run after EVERY asset has been walked — agents, skills and commands all feed
    # `asset_efforts`. Called any earlier it silently checks only the agents walked so far, which
    # is how the first cut of this check passed while a skill's pin was missing.
    check_effort_policy(root, asset_efforts, problems)

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
    for warning in warnings:
        print(f"  ⚠️  {warning}")

    if not problems:
        suffix = f" — {len(warnings)} warning(s)" if warnings else ""
        print(f"✅ OK — plugin assembly ({summary}){suffix}")
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
