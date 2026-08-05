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


class M57AndM59RecipeProofs(M5WrapperFixture):
    def recipe_sources(self) -> Dict[str, str]:
        return {
            "codex": _extract_recipe(CODEX_SKILL, CODEX_BEGIN, CODEX_END),
            "gemini": _extract_recipe(GEMINI_SKILL, GEMINI_BEGIN, GEMINI_END),
        }

    def run_recipe(
        self,
        recipe: str,
        label: str,
        ticket: Optional[str],
        round_value: Optional[str],
        reviewer_value: str = "runtime-agent-value",
    ) -> Tuple[subprocess.CompletedProcess, Path]:
        plugin = self.root / (label + "-plugin")
        review_dir = plugin / "scripts" / REVIEW
        review_dir.mkdir(parents=True)
        wrapper = review_dir / WRAPPER_PATH.name
        wrapper.write_text(RECIPE_WRAPPER_STUB, encoding="utf-8")
        wrapper.chmod(0o755)
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

    def assert_required_inputs(self, recipes: Dict[str, str], label: str) -> None:
        for reviewer, recipe in recipes.items():
            cases = ((None, "RoundBound"), ("TicketBound", None))
            for index, (ticket, round_value) in enumerate(cases):
                case_label = label + "-" + reviewer + "-" + str(index)
                result, log = self.run_recipe(
                    recipe,
                    case_label,
                    ticket,
                    round_value,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertNotEqual("", result.stderr)
                self.assertFalse(log.exists(), "allocation ran with a missing input")

    def assert_literal_reviewers(self, recipes: Dict[str, str], label: str) -> None:
        for reviewer, recipe in recipes.items():
            result, log = self.run_recipe(
                recipe,
                label + "-" + reviewer,
                "TicketLiteral",
                "RoundLiteral",
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
        guards = {
            "ticket": ': "${TICKET:?bind TICKET to the --ticket operand}"\n',
            "round": ': "${ROUND:?bind ROUND to the --round operand}"\n',
        }
        for reviewer, recipe in recipes.items():
            for field, guard in guards.items():
                with self.subTest(reviewer=reviewer, field=field):
                    mutated = dict(recipes)
                    mutated[reviewer] = _replace_once(recipe, guard, "")
                    with self.assertRaises(AssertionError):
                        self.assert_required_inputs(
                            mutated,
                            "required-" + reviewer + "-" + field,
                        )

    def test_M5_9_assertion_each_recipe_passes_its_literal_identity(self) -> None:
        self.assert_literal_reviewers(self.recipe_sources(), "literal-positive")

    def test_M5_9_runtime_derived_identity_mutations_are_rejected(self) -> None:
        recipes = self.recipe_sources()
        for reviewer, recipe in recipes.items():
            old = '"$TICKET" "$ROUND" ' + reviewer
            new = '"$TICKET" "$ROUND" "$REVIEWER"'
            with self.subTest(reviewer=reviewer):
                mutated = dict(recipes)
                mutated[reviewer] = _replace_once(recipe, old, new)
                with self.assertRaises(AssertionError):
                    self.assert_literal_reviewers(
                        mutated,
                        "literal-runtime-" + reviewer,
                    )


REPO = Path(__file__).resolve().parents[2]
GRANT = re.compile(r"Bash\(([^)]*)\)")
HELPER_PREFIX = "${CLAUDE_PLUGIN_ROOT}/scripts/review/"

PERSISTENCE_RECIPES = (
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
)


def _logical_commands(recipe: str) -> List[str]:
    """Commands in a recipe, with line continuations joined and comments dropped."""
    joined = re.sub(r"\\\n\s*", " ", recipe)
    return [
        line.strip()
        for line in joined.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


class PersistenceRecipeGrantProofs(unittest.TestCase):
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

    def test_each_persistence_recipe_is_one_granted_helper_call(self) -> None:
        for relative, begin, end in PERSISTENCE_RECIPES:
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
