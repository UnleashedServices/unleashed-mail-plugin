#!/usr/bin/env python3
"""Every agy launch the plugin ships resolves the newest model first (COREDEV-2875 §2.1, cell M7).

A DECLARATION, NOT A DETECTOR. Five review rounds (r6-r10) each found a new way past a home-built shell
matcher -- suffix filtering, quoted prompts, flag prefixes, a whole-line `--help` exemption, quoted command
substitutions, comment-joined continuations. A detector decides "is this a launch?", so it fails OPEN on
every form it does not model. This gate parses no shell. Every UNIT of shipped text that names agy must
FULLY match an approved template, or be listed by exact text in the closed `EXEMPTIONS` with a reason.
Anything else fails, whatever quoting or syntax it is written in.

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

`test_doc_gates`' raw-checkout warning gate reads the SAME units (`import test_agy_recipe_gate`).
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

# THE APPROVED TEMPLATES. Each must match a unit FULLY (`re.fullmatch`), so nothing can be appended.
_DQ = r'"(?:[^"`$\\]|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)*"'  # double-quoted; parameter expansion only
_BARE = r"""[^\s"'`;&|<>$()\\]+"""
_ARG = r'(?:"\$\(pwd\)"|' + _DQ + "|" + _BARE + ")"
_ARGS = r"(?P<args>(?: " + _ARG + r")*)"
_RESOLVE = (
    r'MODEL="\$\(bash (?:[^\s"\'`;&|$()<>\\]*/|"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/review/)'
    r'agy-newest-model\.sh"?\)" && '
)
TEMPLATES = (
    ("checked form", re.compile(_RESOLVE + r'agy --model "\$MODEL"' + _ARGS)),
    (
        "checked form, PTY-wrapped",
        re.compile(
            _RESOLVE
            + r"python3 (?:[^\s\"'`;&|$()<>\\]*/)?pty-capture\.py(?: (?:--timeout [0-9]+|"
            + _DQ
            + "|"
            + _BARE
            + r'))* -- agy --model "\$MODEL"'
            + _ARGS
        ),
    ),
    ("non-session command", re.compile(r"agy (?:models|--help|-h|--version)")),
)
# NO ARGUMENT MAY SET A MODEL: `"$MODEL"` must be the only model the launch can run (codex r11). The test
# is on the argument's UNQUOTED value, because shell quote removal turns `"--model=old"` and `"--model" x`
# into real options (codex r12). A quoted prompt that merely mentions `--model` is not an option.
_MODEL_OPTION = re.compile(r"-{1,2}model(?:=|$)")
_ARG_TOKEN = re.compile(_ARG)

# THE CLOSED EXEMPTION LIST: (file, the unit's EXACT text, reason). Keyed by text, never by line number,
# so a line shift costs nothing; any edit to an exempt unit fails the gate until it is re-entered here.
REASONS = frozenset(
    {
        "historical demonstration",  # a failed invocation the docs record on purpose
        "message or comment text",  # agy named inside a string or prose, not run
        "behaviour-tested launch",  # a real launch whose resolution an executed test proves
        "presence probe",  # checks agy exists; starts no session
    }
)
EXEMPTIONS: tuple[tuple[str, str, str], ...] = (
    # -- historical demonstration (4) --
    (
        "skills/gemini-review/SKILL.md",
        'agy -p "..."',
        "historical demonstration",
    ),
    (
        "skills/gemini-review/SKILL.md",
        'agy -p "..." > /tmp/out.txt',
        "historical demonstration",
    ),
    (
        "skills/gemini-review/SKILL.md",
        'agy -p "..." | tee /tmp/out.txt',
        "historical demonstration",
    ),
    (
        "skills/gemini-review/SKILL.md",
        'script -q out.txt agy -p "..."',
        "historical demonstration",
    ),
    # -- behaviour-tested launch (3) --
    (
        "scripts/review/agy-newest-model.sh",
        'listing = subprocess.run(["agy", "models"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,',
        "behaviour-tested launch",
    ),
    (
        "scripts/review/isolated-agy-review.sh",
        'agy --add-dir "$TREE" --model "$MODEL" --print-timeout 28m -p "Read and follow $TREE/$PROMPT_REL") >/dev/null',
        "behaviour-tested launch",
    ),
    (
        "scripts/review/preflight-agy.sh",
        '(cd "$SCRATCH" && python3 "${SCRIPTS_DIR}/pty-capture.py" --timeout 60 "$PING" -- agy --model "${MODEL}" -p "ping") ||',
        "behaviour-tested launch",
    ),
    # -- presence probe (1) --
    (
        "scripts/review/preflight-agy.sh",
        'command -v agy >/dev/null 2>&1 || die "agy is not on PATH — the gate is fail-closed, not waived"',
        "presence probe",
    ),
    # -- message or comment text (24) --
    (
        "scripts/pty-capture.py",
        "Some CLIs (Antigravity `agy`, OpenAI `codex exec`) only emit their output to a",
        "message or comment text",
    ),
    (
        "scripts/review-verdict.py",
        '"review — `agy` writes exactly 0 bytes from a non-TTY on failure)")',
        "message or comment text",
    ),
    (
        "scripts/review/agy-newest-model.sh",
        '"the measured <id>TAB<label> listing (a PTY-attached agy fuses escapes to the newest entry)")',
        "message or comment text",
    ),
    (
        "scripts/review/agy-newest-model.sh",
        'fail("`agy models` lists no gemini-<major>[.<minor>]-flash-high model; pass one explicitly")',
        "message or comment text",
    ),
    (
        "scripts/review/agy-newest-model.sh",
        'fail(f"`agy models` did not finish within {timeout:g}s")',
        "message or comment text",
    ),
    (
        "scripts/review/agy-newest-model.sh",
        'fail(f"`agy models` exited {listing.returncode}")',
        "message or comment text",
    ),
    (
        "scripts/review/agy-newest-model.sh",
        'fail(f"`agy models` line {number} is not <id>TAB<label>: {line!r}")',
        "message or comment text",
    ),
    (
        "scripts/review/agy-newest-model.sh",
        'fail(f"`agy models` lists {ident!r}, a flash-high id in an unrecognized version form, so the "',
        "message or comment text",
    ),
    (
        "scripts/review/agy-newest-model.sh",
        'fail(f"`agy models` printed a forbidden byte 0x{byte:02x} at offset {offset}; its stdout is not "',
        "message or comment text",
    ),
    (
        "scripts/review/agy-newest-model.sh",
        'fail(f"could not run `agy models`: {error}")',
        "message or comment text",
    ),
    (
        "scripts/review/capture-gemini-review.sh",
        'TIMEOUT="${5-1800}" # must EXCEED agy --print-timeout (28m=1680s) or the wrapper kills a live run',
        "message or comment text",
    ),
    (
        "scripts/review/isolated-agy-review.sh",
        'TIMEOUT="${3:-1800}" # must EXCEED agy --print-timeout (28m=1680s) or the wrapper kills a live run',
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'This is the COREDEV-2607 failure mode. Do not run a review with this agy build.\\n' >&2",
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'agy preflight: %s\\n' \"$1\" >&2",
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'agy preflight: FAILED — agy MUTATED the working tree during a ping:\\n' >&2",
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'agy preflight: FAILED — agy left the checkout unreadable (its Git metadata is gone or\\n' >&2",
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'agy preflight: FAILED — could not fingerprint the checkout before the ping.\\n' >&2",
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'agy preflight: healthy\\n'",
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'agy preflight: no model resolved (agy-newest-model.sh, above) — the ping did not run\\n' >&2",
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'agy preflight: no pong in %s — agy is unavailable or unauthenticated. Run `agy` interactively\\n' \"$PING\" >&2",
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'agy preflight: the capture exited non-zero — treating agy as UNAVAILABLE regardless of\\n' >&2",
        "message or comment text",
    ),
    (
        "scripts/review/preflight-agy.sh",
        "printf 'corrupt). Do not run a review with this agy build.\\n' >&2",
        "message or comment text",
    ),
    (
        "scripts/validate-plugin-assembly.py",
        '"agy": "any agy invocation outside the isolation harness — agy has NO read-only mode",',
        "message or comment text",
    ),
    (
        "scripts/validate-plugin-assembly.py",
        "The old rule deny-listed a fixed set of command names — git, gh, codex, agy, kimi, rm, sudo — and",
        "message or comment text",
    ),
)


def _model_option_in(args: str) -> bool:
    for token in _ARG_TOKEN.findall(args):
        value = token[1:-1] if token.startswith('"') and token.endswith('"') else token
        if _MODEL_OPTION.match(value):
            return True
    return False


def approved(text: str) -> str | None:
    """The approved template `text` fully matches, or None."""
    for name, template in TEMPLATES:
        match = template.fullmatch(text)
        if match and not (
            "args" in template.groupindex
            and _model_option_in(match.group("args") or "")
        ):
            return name
    return None


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
        if not approved(unit) and (path, unit) not in exempt
    ]


class RecipeGate(unittest.TestCase):
    """The shipped tree: every unit approved or exempt, and the exemption list closed and live."""

    maxDiff = None

    def test_every_shipped_agy_unit_uses_the_checked_form_or_is_exempt(self):
        missing = undeclared(list(shipped_units()))
        self.assertEqual(
            [],
            missing,
            "\n".join(
                f"{path}:{number}: `{unit}` launches agy without resolving its model first. Use the checked "
                f'form (MODEL="$(bash …/agy-newest-model.sh)" && agy --model "$MODEL" …), or add an EXEMPTIONS '
                f"entry with a reason"
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
                self.assertIsNone(approved(text), "an approved form needs no exemption")


class DeclarationControls(unittest.TestCase):
    """Cell M7: the declaration cannot pass by approving everything, nor by failing everything."""

    def assertUnapproved(self, text: str) -> None:
        self.assertIsNone(
            approved(text),
            f"approved a launch that does not resolve its model: {text!r}",
        )

    def test_bare_and_prefixed_launches_are_not_approved(self):
        for text in (
            'agy -p "…"',
            "agy -p ping",
            "agy -i $PROMPT",
            "agy -c",
            "agy --add-dir d -c",
            "agy",
            "agy --add-dir d",
            "agy --add-dir d --continue",
            "agy --add-dir d --conversation 123",
            # codex r9: the `--help` hiders and the prefixed forms
            'agy -p "Explain --help in agy"',
            "agy -p ping # check --help later",
            "agy -p ping && agy --help",
            'agy --add-dir "$(pwd)" -p "Explain --help in agy"',
            "env agy -p ping",
            "MODEL=old agy -p ping",
            "command agy -p ping",
            # codex r10
            'echo "$(agy -p ping)"',
            'result="$(agy --add-dir "$(pwd)" -p ping)"',
            'agy -p "|"',
            'agy -p "|" --add-dir "$(pwd)"',
            # non-session forms with something appended
            "agy models; agy -p x",
            "agy --version && agy -c",
        ):
            with self.subTest(text=text):
                self.assertUnapproved(text)

    def test_nothing_can_be_appended_to_the_checked_form(self):
        resolve = 'MODEL="$(bash scripts/review/agy-newest-model.sh)"'
        for text in (
            f'{resolve} && agy --model "$MODEL" -p x; agy -p y',
            f'{resolve} && agy --model "$MODEL" -p "$(cat f)"',
            f'{resolve} ; agy --model "$MODEL" -p x',
            f"{resolve} && agy --model old -p x",
            'MODEL="$(bash "${EVIL}/agy-newest-model.sh")" && agy --model "$MODEL" -p y',
            (
                'MODEL="$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/agy-newest-model.sh"; agy -p x)" && '
                'agy --model "$MODEL" -p y'
            ),
        ):
            with self.subTest(text=text):
                self.assertUnapproved(text)

    def test_no_second_model_option_quoted_or_not(self):
        resolve = 'MODEL="$(bash scripts/review/agy-newest-model.sh)" && '
        pty = resolve + "python3 scripts/pty-capture.py out -- "
        for prefix in (resolve, pty):
            for extra in (
                '--model "$OTHER_MODEL"',
                "--model=gemini-3.6-flash-high",
                "-model old",
                "--model old",
                # codex r12: shell quote removal makes these real options
                '"--model" "$OTHER_MODEL"',
                '"--model=gemini-3.6-flash-high"',
                '"-model" old',
            ):
                with self.subTest(prefix=prefix[-25:], extra=extra):
                    self.assertUnapproved(f'{prefix}agy --model "$MODEL" {extra} -p x')

    def test_the_approved_forms_pass(self):
        for text, expected in (
            (
                (
                    'MODEL="$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/agy-newest-model.sh")" && agy --model "$MODEL" '
                    '--add-dir "$(pwd)" --print-timeout 28m -p "Read and follow .agy-prompt-${TICKET}r${ROUND}.md"'
                ),
                "checked form",
            ),
            (
                'MODEL="$(bash scripts/review/agy-newest-model.sh)" && agy --model "$MODEL" -i "x"',
                "checked form",
            ),
            # a quoted prompt that merely MENTIONS --model is not an option
            (
                'MODEL="$(bash scripts/review/agy-newest-model.sh)" && agy --model "$MODEL" -p "explain --model"',
                "checked form",
            ),
            (
                (
                    'MODEL="$(bash scripts/review/agy-newest-model.sh)" && python3 pty-capture.py --allocated '
                    '"$GEMINI_TRANSCRIPT" -- agy --model "$MODEL" --add-dir "$(pwd)" -p "Read and follow x.md"'
                ),
                "checked form, PTY-wrapped",
            ),
            ("agy models", "non-session command"),
            ("agy --version", "non-session command"),
        ):
            with self.subTest(text=text):
                self.assertEqual(expected, approved(text))

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
