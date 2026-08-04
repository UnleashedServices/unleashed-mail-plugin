#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-M5 skill recipe proof pairs."""

from __future__ import annotations

import os
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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
