#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-M5 skill recipe proof pairs."""

from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from .test_m5_wrapper_contract import (
        CODEX_BEGIN,
        CODEX_END,
        CODEX_SKILL,
        GEMINI_BEGIN,
        GEMINI_END,
        GEMINI_SKILL,
        RECIPE_WRAPPER_STUB,
        REVIEW,
        WRAPPER_PATH,
        M5WrapperFixture,
        _extract_recipe,
        _replace_once,
    )
except ImportError:  # Direct execution from scripts/tests.
    from test_m5_wrapper_contract import (
        CODEX_BEGIN,
        CODEX_END,
        CODEX_SKILL,
        GEMINI_BEGIN,
        GEMINI_END,
        GEMINI_SKILL,
        RECIPE_WRAPPER_STUB,
        REVIEW,
        WRAPPER_PATH,
        M5WrapperFixture,
        _extract_recipe,
        _replace_once,
    )


CAPTURE_CODEX = WRAPPER_PATH.parent / "capture-codex-review.sh"


class M57AndM59RecipeProofs(M5WrapperFixture):
    """M5.7 and M5.9 for both arms.

    The codex arm's capture moved out of its SKILL body into `capture-codex-review.sh`, so the rules
    these cells mutate — the operand guards and the LITERAL reviewer identity handed to the allocator —
    now live in that script for codex and still inline for gemini. Each mutation therefore names WHERE
    its rule lives rather than the test inferring it, and the recipe under test stays the shipped one.
    """

    def recipe_sources(self) -> Dict[str, str]:
        return {
            "codex": _extract_recipe(CODEX_SKILL, CODEX_BEGIN, CODEX_END),
            "gemini": _extract_recipe(GEMINI_SKILL, GEMINI_BEGIN, GEMINI_END),
        }

    @staticmethod
    def capture_helper_source() -> str:
        return CAPTURE_CODEX.read_text(encoding="utf-8")

    def run_recipe(
        self,
        recipe: str,
        label: str,
        ticket: Optional[str],
        round_value: Optional[str],
        reviewer_value: str = "runtime-agent-value",
        helper_source: Optional[str] = None,
    ) -> Tuple[subprocess.CompletedProcess, Path]:
        plugin = self.root / (label + "-plugin")
        review_dir = plugin / "scripts" / REVIEW
        review_dir.mkdir(parents=True)
        wrapper = review_dir / WRAPPER_PATH.name
        wrapper.write_text(RECIPE_WRAPPER_STUB, encoding="utf-8")
        wrapper.chmod(0o755)
        # The codex recipe reaches the allocator THROUGH this helper, so it has to be staged beside the
        # stub — real by default, mutated when a cell is proving one of the rules it carries.
        helper = review_dir / CAPTURE_CODEX.name
        helper.write_text(
            self.capture_helper_source() if helper_source is None else helper_source,
            encoding="utf-8",
        )
        helper.chmod(0o755)
        # The helper refuses an unreadable or empty prompt, which is a guard the inline recipe never
        # had; these cells are about operands and identity, so give it a valid prompt to get past it.
        prompt = self.root / ".codex-prompt.md"
        if not prompt.exists():
            prompt.write_text("# recipe fixture prompt\n", encoding="utf-8")
        recipe_log = self.root / (label + "-recipe.args")

        env = dict(os.environ)
        env.pop("TICKET", None)
        env.pop("ROUND", None)
        env.update(
            {
                "HOME": str(self.home),
                "TMPDIR": str(self.root),
                "CLAUDE_PLUGIN_ROOT": str(plugin),
                "M5_RECIPE_LOG": str(recipe_log),
                "REVIEWER": reviewer_value,
            }
        )
        if ticket is not None:
            env["TICKET"] = ticket
        if round_value is not None:
            env["ROUND"] = round_value

        result = subprocess.run(
            [str(self.real_bash), "-c", recipe],
            cwd=str(self.root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return result, recipe_log

    @staticmethod
    def recipe_arguments(path: Path) -> List[str]:
        if not path.exists():
            return []
        return [
            item.decode("utf-8")
            for item in path.read_bytes().split(b"\0")
            if item
        ]

    def assert_required_inputs(
        self,
        recipes: Dict[str, str],
        label: str,
        helpers: Optional[Dict[str, str]] = None,
    ) -> None:
        helpers = helpers or {}
        for reviewer, recipe in recipes.items():
            cases = ((None, "RoundBound"), ("TicketBound", None))
            for index, (ticket, round_value) in enumerate(cases):
                case_label = label + "-" + reviewer + "-" + str(index)
                result, log = self.run_recipe(
                    recipe,
                    case_label,
                    ticket,
                    round_value,
                    helper_source=helpers.get(reviewer),
                )
                self.assertNotEqual(0, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertNotEqual("", result.stderr)
                self.assertFalse(log.exists(), "allocation ran with a missing input")

    def assert_literal_reviewers(
        self,
        recipes: Dict[str, str],
        label: str,
        helpers: Optional[Dict[str, str]] = None,
    ) -> None:
        helpers = helpers or {}
        for reviewer, recipe in recipes.items():
            result, log = self.run_recipe(
                recipe,
                label + "-" + reviewer,
                "TicketLiteral",
                "RoundLiteral",
                helper_source=helpers.get(reviewer),
            )
            self.assertEqual(73, result.returncode, result.stderr)
            self.assertEqual(
                ["TicketLiteral", "RoundLiteral", reviewer],
                self.recipe_arguments(log),
            )

    def test_M5_7_assertion_both_recipes_fail_before_missing_input_allocation(self) -> None:
        self.assert_required_inputs(self.recipe_sources(), "required-positive")

    def test_M5_7_each_missing_input_guard_removal_is_rejected(self) -> None:
        recipes = self.recipe_sources()
        # Same guard, two homes: gemini still declares it inline with `:`/`:?`, codex declares it in
        # the helper with an explicit test so it can report which operand is missing.
        guards = {
            "gemini": {
                "ticket": ': "${TICKET:?bind TICKET to the --ticket operand}"\n',
                "round": ': "${ROUND:?bind ROUND to the --round operand}"\n',
            },
            "codex": {
                "ticket": '[ -n "$TICKET" ] || die "bind TICKET to the --ticket operand"\n',
                "round": '[ -n "$ROUND" ]  || die "bind ROUND to the --round operand"\n',
            },
        }
        for reviewer, recipe in recipes.items():
            for field, guard in guards[reviewer].items():
                with self.subTest(reviewer=reviewer, field=field):
                    mutated = dict(recipes)
                    helpers = {}
                    if reviewer == "codex":
                        helpers[reviewer] = _replace_once(
                            self.capture_helper_source(), guard, ""
                        )
                    else:
                        mutated[reviewer] = _replace_once(recipe, guard, "")
                    with self.assertRaises(AssertionError):
                        self.assert_required_inputs(
                            mutated,
                            "required-" + reviewer + "-" + field,
                            helpers=helpers,
                        )

    def test_M5_9_assertion_each_recipe_passes_its_literal_identity(self) -> None:
        self.assert_literal_reviewers(self.recipe_sources(), "literal-positive")

    def test_M5_9_runtime_derived_identity_mutations_are_rejected(self) -> None:
        recipes = self.recipe_sources()
        # The anchor text is IDENTICAL for both arms — only the file it lives in differs. codex's
        # identity is compiled into the committed helper now, which is strictly stronger than a skill
        # body, but the property is the same: the allocator must receive the name as a literal, or one
        # arm could allocate under the other's and a single review would satisfy both halves.
        for reviewer, recipe in recipes.items():
            old = '"$TICKET" "$ROUND" ' + reviewer
            new = '"$TICKET" "$ROUND" "$REVIEWER"'
            with self.subTest(reviewer=reviewer):
                mutated = dict(recipes)
                helpers = {}
                if reviewer == "codex":
                    helpers[reviewer] = _replace_once(
                        self.capture_helper_source(), old, new
                    )
                else:
                    mutated[reviewer] = _replace_once(recipe, old, new)
                with self.assertRaises(AssertionError):
                    self.assert_literal_reviewers(
                        mutated,
                        "literal-runtime-" + reviewer,
                        helpers=helpers,
                    )


REPO = Path(__file__).resolve().parents[2]
GRANT = re.compile(r"Bash\(([^)]*)\)")
HELPER_PREFIX = "${CLAUDE_PLUGIN_ROOT}/scripts/review/"

GRANTED_RECIPES = (
    (
        "skills/review-synthesis/SKILL.md",
        "# COREDEV2619_SYNTHESIS_PERSIST_BEGIN",
        "# COREDEV2619_SYNTHESIS_PERSIST_END",
    ),
    (
        "skills/brainstorm/SKILL.md",
        "# COREDEV2619_BRAINSTORM_PERSIST_BEGIN",
        "# COREDEV2619_BRAINSTORM_PERSIST_END",
    ),
    (
        "skills/codex-review/SKILL.md",
        CODEX_BEGIN,
        CODEX_END,
    ),
)


def _logical_commands(recipe: str) -> List[str]:
    """Commands in a recipe, with line continuations joined and comments dropped."""
    joined = re.sub(r"\\\n\s*", " ", recipe)
    return [
        line.strip()
        for line in joined.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


class GrantedRecipeShapeProofs(unittest.TestCase):
    """Gaps 7-9 and bot thread 7: the block every gate round must run prompted every time.

    Each persistence recipe used to define shell functions and branch, so it was a COMPOUND command.
    Claude Code decomposes those and requires a rule per subcommand
    (code.claude.com/docs/en/permissions), which is why no single `allowed-tools` Bash shape could
    cover them and the operator was pushed toward a blanket `Bash` grant.

    Asserted here: each recipe is ONE command, and it invokes a script under a directory the same
    skill's own `allowed-tools` grants by prefix. This is the STRUCTURAL precondition, deliberately
    not a reimplementation of the host's matcher — a test that guessed at quote handling would be
    asserting my model of Claude Code rather than the property that made the recipe uncoverable.
    """

    def _grants(self, source: str) -> List[str]:
        for line in source.splitlines():
            if line.startswith("allowed-tools:"):
                return GRANT.findall(line)
        raise AssertionError("skill declares no allowed-tools line")

    def test_each_extracted_recipe_is_one_granted_helper_call(self) -> None:
        for relative, begin, end in GRANTED_RECIPES:
            with self.subTest(skill=relative):
                path = REPO / relative
                source = path.read_text(encoding="utf-8")
                commands = _logical_commands(_extract_recipe(path, begin, end))

                self.assertEqual(
                    1, len(commands), f"{relative}: recipe is {len(commands)} commands, not one"
                )
                command = commands[0]
                for operator in ("&&", "||", ";", "|"):
                    self.assertNotIn(
                        operator,
                        command,
                        f"{relative}: a shell operator makes this a compound command again",
                    )
                self.assertTrue(
                    command.startswith('bash "' + HELPER_PREFIX),
                    f"{relative}: recipe does not invoke a scripts/review helper by bare token: "
                    f"{command!r}",
                )

                covering = [
                    grant
                    for grant in self._grants(source)
                    if grant.endswith("*") and command.startswith("bash " + grant[: -len("*")])
                    or grant.startswith("bash " + HELPER_PREFIX)
                ]
                self.assertTrue(
                    covering,
                    f"{relative}: allowed-tools has no Bash grant covering {HELPER_PREFIX}",
                )

    def test_the_helper_the_recipes_call_is_committed_and_executable(self) -> None:
        helper = REPO / "scripts" / "review" / "persist-verdict.sh"
        self.assertTrue(helper.is_file(), "the recipes call a script that is not in the repo")
        self.assertTrue(os.access(helper, os.X_OK), "the shipped helper is not executable")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
