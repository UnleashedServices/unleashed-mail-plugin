#!/usr/bin/env python3
"""`agy` is RETIRED: the plugin ships no `agy` launch at all (COREDEV-2887; formerly COREDEV-2875 §2.1, M7).

Until COREDEV-2887 the Gemini arm ran the Antigravity CLI, and this gate required every shipped `agy` launch to
resolve the newest model first. The arm now runs the `gemini` CLI through an adapter and an isolation harness, and
the `agy` scripts are gone — so a surviving `agy` recipe would launch an unisolated reviewer that has no read-only
mode, against a resolver that no longer exists. NOTHING is approved any more: every unit of shipped text that names
`agy` must be listed by exact text in the closed `EXEMPTIONS`, with a reason, or the gate fails.

A DECLARATION, NOT A DETECTOR. Five review rounds (r6-r10) each found a new way past a home-built shell matcher, so
this gate parses no shell: it finds UNITS and requires each to be declared, whatever quoting or syntax it is in.

UNITS -- the word `agy` (not part of a longer name or path component, except a final `/agy`) in:
  * a markdown inline code span that is launch-shaped by plain whitespace tokens: a prompt mode flag
    followed by any token, or a continuation flag. Prose that names a flag ("`agy -p` writes 0 bytes") is
    not a unit -- a declared boundary (plan §6);
  * a markdown fenced line, in a backtick or tilde fence under CommonMark's closing rule, except a
    whole-line comment;
  * any line of any other shipped file, except a whole-line comment.
Skipping a whole-line comment is safe only at top level: a `#` that begins a line INSIDE a multi-line
quoted string or heredoc is data, and a command substitution on it runs. The gate does not track quote
state, so that form is a declared boundary (plan §6, COREDEV-2876).

`test_doc_gates`' raw-launch gate for the gemini-review skill reads the SAME units (`import test_agy_recipe_gate`)
and requires the skill to have none.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCANNED = (
    "skills",
    "agents",
    "scripts",
    "hooks",
    "CLAUDE.md",
    "AGENT_CONTRACTS.md",
    "README.md",
)

AGY_WORD = re.compile(r"(?<![\w.-])(?:\S*/)?agy(?![\w.-])")
PROMPT_MODES = ("-p", "--print", "--prompt", "-i", "--prompt-interactive")
CONTINUATION = ("-c", "--continue", "--conversation")
# A fence opener/closer: up to three spaces, then three or more backticks or tildes (CommonMark).
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")

# NO APPROVED TEMPLATES (COREDEV-2887). The checked forms this gate once approved resolved the model through
# `scripts/review/agy-newest-model.sh`, which no longer ships; approving them now would let a resurrected
# recipe launch an unisolated `agy` against a missing resolver. `DeclarationControls` asserts they are undeclared.

# THE CLOSED EXEMPTION LIST: (file, the unit's EXACT text, reason). Keyed by text, never by line number,
# so a line shift costs nothing; any edit to an exempt unit fails the gate until it is re-entered here.
REASONS = frozenset(
    {
        "message or comment text",  # agy named inside a string or prose, not run
        "a refusal of the retired CLI",  # a rule that REJECTS an agy grant
    }
)
EXEMPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "scripts/pty-capture.py",
        "Some CLIs (OpenAI `codex exec`; the retired Antigravity `agy`) only emit their output to a",
        "message or comment text",
    ),
    (
        "scripts/review-verdict.py",
        '"review — `agy` writes exactly 0 bytes from a non-TTY on failure)")',
        "message or comment text",
    ),
    (
        "scripts/validate-plugin-assembly.py",
        '"agy": "any agy invocation outside the isolation harness — agy has NO read-only mode",',
        "a refusal of the retired CLI",
    ),
    (
        "scripts/validate-plugin-assembly.py",
        "The old rule deny-listed a fixed set of command names — git, gh, codex, agy, kimi, rm, sudo — and",
        "message or comment text",
    ),
)


def _flagish(token: str, flags: tuple[str, ...]) -> bool:
    value = token.strip("'\"()$`;|&")
    return any(value == flag or value.startswith(flag + "=") for flag in flags)


def inline_is_unit(span: str) -> bool:
    found = AGY_WORD.search(span)
    if not found:
        return False
    tokens = span[found.start() :].split()
    return any(
        _flagish(token, CONTINUATION)
        or (_flagish(token, PROMPT_MODES) and index + 1 < len(tokens))
        for index, token in enumerate(tokens)
    )


def units(path: str, text: str):
    """Yield (line number, unit text) for every unit in one file."""
    lines = text.splitlines()
    if path.endswith(".md"):
        fence: tuple[str, int] | None = None
        for number, line in enumerate(lines, 1):
            marker = FENCE.match(line)
            if fence is None and marker:
                fence = (marker.group(1)[0], len(marker.group(1)))
                continue
            # CommonMark: a CLOSING fence is the same character, at least as long, and NOTHING but
            # whitespace after it. "```not-a-close" is fence content, so a launch after it stays visible.
            if (
                fence is not None
                and marker
                and marker.group(1)[0] == fence[0]
                and len(marker.group(1)) >= fence[1]
                and not marker.group(2).strip()
            ):
                fence = None
                continue
            if fence is not None:
                if not line.lstrip().startswith("#") and AGY_WORD.search(line):
                    yield number, line.strip()
            else:
                for span in re.findall(r"`([^`]+)`", line):
                    if inline_is_unit(span):
                        yield number, span.strip()
    else:
        for number, line in enumerate(lines, 1):
            if not line.lstrip().startswith("#") and AGY_WORD.search(line):
                yield number, line.strip()


def shipped_files(root: Path = REPO) -> list[str]:
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", *SCANNED],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [
        path
        for path in listed
        if not path.startswith("scripts/tests/") and "callers-scan" not in path
    ]


def shipped_units(root: Path = REPO):
    for path in shipped_files(root):
        try:
            text = (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, unit in units(path, text):
            yield path, number, unit


def undeclared(found, exemptions=EXEMPTIONS):
    exempt = {(path, text) for path, text, _ in exemptions}
    return [
        (path, number, unit)
        for path, number, unit in found
        if (path, unit) not in exempt
    ]


class RecipeGate(unittest.TestCase):
    """The shipped tree: every `agy` unit declared, and the exemption list closed and live."""

    maxDiff = None

    def test_no_shipped_unit_launches_the_retired_cli(self):
        missing = undeclared(list(shipped_units()))
        self.assertEqual(
            [],
            missing,
            "\n".join(
                f"{path}:{number}: `{unit}` names the retired `agy` CLI. The Gemini arm runs through "
                "scripts/review/capture-gemini-review.sh; remove the launch, or, if it is only text, add an "
                "EXEMPTIONS entry with a reason"
                for path, number, unit in missing
            ),
        )

    def test_every_exemption_names_a_live_unit_with_a_known_reason(self):
        live = {(path, unit) for path, _, unit in shipped_units()}
        for path, text, reason in EXEMPTIONS:
            with self.subTest(path=path, unit=text):
                self.assertIn(reason, REASONS)
                self.assertIn(
                    (path, text),
                    live,
                    "a stale exemption: no shipped unit has this exact text",
                )


class DeclarationControls(unittest.TestCase):
    """The declaration cannot pass by declaring everything, nor by failing everything."""

    def assertUndeclared(self, text: str) -> None:
        self.assertEqual(
            [("x.sh", 1, text)],
            undeclared([("x.sh", 1, text)]),
            f"an agy launch passed undeclared: {text!r}",
        )

    def test_every_launch_shape_is_undeclared(self):
        for text in (
            'agy -p "…"',
            "agy -p ping",
            "agy -i $PROMPT",
            "agy -c",
            "agy --add-dir d -c",
            "agy",
            "agy --add-dir d --conversation 123",
            'agy -p "Explain --help in agy"',
            "env agy -p ping",
            "MODEL=old agy -p ping",
            'echo "$(agy -p ping)"',
            "agy models",
            "agy --version",
        ):
            with self.subTest(text=text):
                self.assertUndeclared(text)

    def test_the_formerly_approved_checked_forms_are_undeclared(self):
        """What COREDEV-2875 approved resolved its model through a script that no longer ships."""
        for text in (
            (
                'MODEL="$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/agy-newest-model.sh")" && agy --model "$MODEL" '
                '--add-dir "$(pwd)" --print-timeout 28m -p "Read and follow .agy-prompt-${TICKET}r${ROUND}.md"'
            ),
            (
                'MODEL="$(bash scripts/review/agy-newest-model.sh)" && python3 pty-capture.py --allocated '
                '"$GEMINI_TRANSCRIPT" -- agy --model "$MODEL" --add-dir "$(pwd)" -p "Read and follow x.md"'
            ),
        ):
            with self.subTest(text=text[:60]):
                self.assertUndeclared(text)

    def test_units_are_found_however_the_markdown_hides_them(self):
        cases = {
            # a tilde fence is a fence
            "~~~sh\nagy -p ping\n~~~\n": ["agy -p ping"],
            # codex r12: a marker with trailing text does NOT close the fence
            "```sh\n```not-a-close\nagy -p ping\n```\n": ["agy -p ping"],
            "~~~sh\n~~~not-a-close\nagy -p ping\n~~~\n": ["agy -p ping"],
            # a shorter or different marker does not close it either
            "````sh\n```\nagy -p ping\n````\n": ["agy -p ping"],
            "```sh\n~~~\nagy -p ping\n```\n": ["agy -p ping"],
            # codex r10: the comment ends the continued command; the agy line is a unit of its own
            "```sh\ncommand -v \\\n# comment\nagy -p ping\n```\n": ["agy -p ping"],
            # launch-shaped inline spans are units; a prose span naming a flag is not
            'Run `agy -p "|"` now.\n': ['agy -p "|"'],
            'Run `echo "$(agy -p ping)"` now.\n': ['echo "$(agy -p ping)"'],
            "Note `agy -p` writes 0 bytes; `agy models` lists names.\n": [],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(expected, [unit for _, unit in units("x.md", text)])

    def test_an_edited_exempt_unit_fails_until_it_is_re_entered(self):
        if not EXEMPTIONS:
            self.skipTest("no exemptions declared")
        path, text, _ = EXEMPTIONS[0]
        self.assertEqual([], undeclared([(path, 1, text)]))
        self.assertEqual([(path, 1, text + " x")], undeclared([(path, 1, text + " x")]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
