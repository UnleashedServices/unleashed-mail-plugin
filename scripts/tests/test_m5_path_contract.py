#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-M5 path propagation proof pairs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from . import test_transcript_path_threading as threading
except ImportError:  # Direct execution from scripts/tests.
    import test_transcript_path_threading as threading


REPO = Path(__file__).resolve().parents[2]
REVIEW = "review"
REVIEWER_FLAG = "--" + REVIEW + "er"

FAKE_WRITER = r'''#!/bin/sh
: > "${M5_WRITER_LOG:?}"
for argument in "$@"; do
    printf '%s\0' "$argument" >> "$M5_WRITER_LOG"
done
'''


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise AssertionError(
            "mutation anchor must occur exactly once: " + repr(old)
        )
    return source.replace(old, new, 1)


class M5PathFixture(threading.TranscriptThreadingFixture):
    maxDiff = None

    def capture_source(self, reviewer: str) -> str:
        if reviewer == "gemini":
            return threading.extract_recipe(
                threading.GEMINI_SKILL,
                threading.GEMINI_BEGIN,
                threading.GEMINI_END,
            )
        if reviewer == "codex":
            return threading.extract_recipe(
                threading.CODEX_SKILL,
                threading.CODEX_BEGIN,
                threading.CODEX_END,
            )
        raise AssertionError("unsupported reviewer fixture: " + reviewer)

    def run_capture_source(
        self,
        reviewer: str,
        recipe: str,
        base: Path,
        use_xdg: bool = True,
        home: Optional[Path] = None,
    ) -> Tuple[str, dict, List[List[str]]]:
        for log in (self.capture_log, self.helper_log):
            if log.exists():
                log.unlink()
        result = threading.run_checked(
            [str(self.real_bash), "-c", recipe],
            self.reviewed,
            self.environment(
                base,
                reviewer,
                use_xdg=use_xdg,
                home=home,
            ),
        )
        self.assertEqual(0, result.returncode, result.stderr)

        marker_prefix = "UNLEASHED_TRANSCRIPT="
        markers = [
            line
            for line in result.stdout.splitlines()
            if line.startswith(marker_prefix)
        ]
        self.assertEqual(1, len(markers), result.stdout)
        allocated = markers[0][len(marker_prefix):]
        records = [
            json.loads(line)
            for line in self.capture_log.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(1, len(records), records)
        helper_records = []
        if self.helper_log.exists():
            helper_records = [
                json.loads(line)
                for line in self.helper_log.read_text(encoding="utf-8").splitlines()
            ]
        return allocated, records[0], helper_records

    def assert_capture_uses_emitted_path(
        self,
        reviewer: str,
        recipe: str,
        base: Path,
        use_xdg: bool = True,
        home: Optional[Path] = None,
    ) -> str:
        allocated, capture, helper_records = self.run_capture_source(
            reviewer,
            recipe,
            base,
            use_xdg=use_xdg,
            home=home,
        )
        argv = capture["argv"]
        allocated_index = argv.index("--allocated")
        self.assertEqual(allocated, argv[allocated_index + 1])
        self.assertEqual(1, argv.count(allocated))
        self.assertTrue(Path(allocated).is_file())

        if reviewer == "gemini":
            self.assertEqual(1, len(helper_records), helper_records)
            self.assertEqual(allocated, helper_records[0][2])
        else:
            self.assertEqual([], helper_records)
        return allocated

    def captured_pair(
        self,
        base: Path,
        use_xdg: bool = True,
        home: Optional[Path] = None,
    ) -> Tuple[str, str]:
        gemini_path = self.assert_capture_uses_emitted_path(
            "gemini",
            self.capture_source("gemini"),
            base,
            use_xdg=use_xdg,
            home=home,
        )
        codex_path = self.assert_capture_uses_emitted_path(
            "codex",
            self.capture_source("codex"),
            base,
            use_xdg=use_xdg,
            home=home,
        )
        return gemini_path, codex_path

    def assert_consumer_artifact(
        self,
        artifact: dict,
        argv: List[str],
        gemini_path: str,
        codex_path: str,
    ) -> None:
        self.assert_artifact_paths(artifact, gemini_path, codex_path)
        self.assertEqual(
            [
                "gemini=APPROVE:" + gemini_path,
                "codex=APPROVE:" + codex_path,
            ],
            self.reviewer_values(argv),
        )

    @staticmethod
    def write_transcript(path: Path, reviewer: str) -> None:
        """Write a transcript AND the sidecars an allocated one carries.

        An approving write now requires allocator-shaped evidence, and an allocator-shaped NAME
        without a `.launch` is refused by design — that combination is how a digest-suffixed file
        outside the allocator directory is kept from passing for allocated. Cells here hand-build
        their transcripts, so they must supply what the allocator and capture helper would have:
        otherwise a re-derivation mutant is rejected by the evidence rule before the M5 assertion can
        observe the wrong path, and the mutation stops isolating its own variable.
        """
        path.write_text(
            reviewer + " result\nVERDICT: APPROVE\n",
            encoding="utf-8",
        )
        run_id = path.stem.rsplit("-", 1)[-1]
        launch = Path(str(path) + ".launch")
        launch.write_text(run_id + "\n", encoding="utf-8")
        stamp = path.stat().st_mtime_ns
        os.utime(launch, ns=(stamp - 1_000_000, stamp - 1_000_000))

    def fake_writer_arguments(
        self,
        recipe: str,
        bindings: Dict[str, str],
        label: str,
        helper_source: Optional[str] = None,
    ) -> List[str]:
        fake_bin = self.root / (label + "-bin")
        fake_bin.mkdir()
        fake_python = fake_bin / "python3"
        fake_python.write_text(FAKE_WRITER, encoding="utf-8")
        fake_python.chmod(0o755)
        log = self.root / (label + "-writer.args")

        plugin_root = REPO if helper_source is None else self.stage_plugin_root(helper_source)
        env = dict(os.environ)
        env.update(
            {
                "HOME": str(self.home),
                "TMPDIR": str(self.tmpdir),
                "CLAUDE_PLUGIN_ROOT": str(plugin_root),
                "M5_WRITER_LOG": str(log),
                "PATH": str(fake_bin) + os.pathsep + env.get("PATH", ""),
            }
        )
        env.update(bindings)
        result = subprocess.run(
            [str(self.real_bash), "-c", recipe],
            cwd=str(self.reviewed),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(log.is_file())
        return [
            item.decode("utf-8")
            for item in log.read_bytes().split(b"\0")
            if item
        ]

    @staticmethod
    def reviewer_arguments(argv: List[str]) -> List[str]:
        return [
            argv[index + 1]
            for index, argument in enumerate(argv)
            if argument == REVIEWER_FLAG
        ]

    def synthesis_source(self) -> str:
        return threading.extract_recipe(
            threading.SYNTHESIS_SKILL,
            threading.SYNTHESIS_BEGIN,
            threading.SYNTHESIS_END,
        )

    def brainstorm_source(self) -> str:
        return threading.extract_recipe(
            threading.BRAINSTORM_SKILL,
            threading.BRAINSTORM_BEGIN,
            threading.BRAINSTORM_END,
        )

    def capture_helper_source(self, reviewer: str = "codex") -> str:
        """The committed capture helper the named arm's recipe now calls."""
        path = threading.CAPTURE_CODEX if reviewer == "codex" else threading.CAPTURE_GEMINI
        return path.read_text(encoding="utf-8")

    def persist_helper_source(self) -> str:
        """The committed `persist-verdict.sh`.

        Both persistence recipes now reduce to one call to this script, so the rules it enforces —
        first-delimiter parsing, empty-leaf classification — are mutated HERE rather than in the
        recipe strings. The recipes keep their own mutants for what they still decide: which spec
        each reviewer flag is bound to.
        """
        return threading.PERSIST_HELPER.read_text(encoding="utf-8")


class M51AndM52PropagationProofs(M5PathFixture):
    def test_M5_1_assertion_both_capture_arms_preserve_every_base_form(self) -> None:
        xdg_target = self.root / "canonical XDG target:=one"
        xdg_target.mkdir()
        xdg_link = self.root / "lexical XDG link"
        xdg_link.symlink_to(xdg_target, target_is_directory=True)

        fallback_target = self.root / "canonical fallback target:=two"
        (fallback_target / ".local" / "state").mkdir(parents=True)
        fallback_link = self.root / "lexical fallback home"
        fallback_link.symlink_to(fallback_target, target_is_directory=True)

        cases = (
            (
                "hostile",
                self.root / "state space\tglob[*]?\\single' double\" colon: equals=",
                True,
                self.home,
            ),
            ("terminal-space", self.root / "terminal-space ", True, self.home),
            ("terminal-tab", self.root / "terminal-tab\t", True, self.home),
            ("xdg-link", xdg_link, True, self.home),
            ("fallback-link", self.root / "unused XDG", False, fallback_link),
        )
        for label, base, use_xdg, home in cases:
            for reviewer in ("gemini", "codex"):
                with self.subTest(base=label, reviewer=reviewer):
                    allocated = self.assert_capture_uses_emitted_path(
                        reviewer,
                        self.capture_source(reviewer),
                        base,
                        use_xdg=use_xdg,
                        home=home,
                    )
                    if label == "xdg-link":
                        self.assertTrue(
                            allocated.startswith(str(xdg_target.resolve()) + os.sep)
                        )
                        self.assertNotIn(str(xdg_link), allocated)
                    if label == "fallback-link":
                        expected = (fallback_target / ".local" / "state").resolve()
                        self.assertTrue(allocated.startswith(str(expected) + os.sep))
                        self.assertNotIn(str(fallback_link), allocated)

    def test_M5_2_rederived_capture_target_mutations_are_rejected(self) -> None:
        # Same property for both arms — the capture must open the leaf the allocator EMITTED, not one
        # it re-derives. BOTH now carry it in their own committed helper, so both mutants replace the
        # staged script rather than the recipe text; the recipes under test stay the shipped ones.
        mutations = {
            # The timeout operand is deliberately NOT part of either anchor. The mutation under test
            # is the re-derived transcript PATH; including the timeout pinned an unrelated literal,
            # so retuning it broke this test for a reason it does not test (PR #63 review, gap 12).
            "codex": (
                '--allocated "$CODEX_TRANSCRIPT" -- \\\n',
                '--allocated "${XDG_STATE_HOME}/derived-codex.txt" -- \\\n',
            ),
            # Re-anchored when the arm began handing the prompt SNAPSHOT instead of the caller's
            # path: the operand is now `"${GEMINI_TRANSCRIPT}.prompt"`. The mutant is unchanged in
            # spirit — it re-derives the TRANSCRIPT operand, which is what M5.2 forbids — and the
            # snapshot operand is left intact so the mutation still isolates that one variable.
            # Anchored on the FINAL exec, which is unique. The helper grew a `MODEL_OVERRIDE` branch
            # that repeats the operand pair, so the bare pair now occurs twice and `_replace_once`
            # refused rather than mutating an arbitrary one — the zero/two-hit guard doing its job.
            "gemini": (
                'exec bash "${SCRIPT_DIR}/isolated-agy-review.sh" "${GEMINI_TRANSCRIPT}.prompt" '
                '"$GEMINI_TRANSCRIPT" "$TIMEOUT" "$PLAN"',
                'exec bash "${SCRIPT_DIR}/isolated-agy-review.sh" "${GEMINI_TRANSCRIPT}.prompt" '
                '"${XDG_STATE_HOME}/derived-gemini.txt" "$TIMEOUT" "$PLAN"',
            ),
        }
        for reviewer, (old, new) in mutations.items():
            with self.subTest(reviewer=reviewer):
                self.install_capture_helper(
                    _replace_once(self.capture_helper_source(reviewer), old, new), reviewer
                )
                try:
                    with self.assertRaises(AssertionError):
                        self.assert_capture_uses_emitted_path(
                            reviewer,
                            self.capture_source(reviewer),
                            self.root / ("mutation base " + reviewer),
                        )
                finally:
                    # Restore INLINE, not via addCleanup: cleanups run after tearDown, by which point
                    # the staged plugin directory no longer exists.
                    self.install_capture_helper(self.capture_helper_source(reviewer), reviewer)


class M56ConsumerProofs(M5PathFixture):
    def test_M5_6_assertion_both_consumers_preserve_the_emitted_paths(self) -> None:
        gemini_path, codex_path = self.captured_pair(
            self.root / "consumer base:=with spaces"
        )
        synthesis_artifact, synthesis_argv = self.run_synthesis(
            "gemini=APPROVE:" + gemini_path,
            "codex=APPROVE:" + codex_path,
            "APPROVE",
        )
        self.assert_consumer_artifact(
            synthesis_artifact,
            synthesis_argv,
            gemini_path,
            codex_path,
        )
        brainstorm_artifact, brainstorm_argv = self.run_brainstorm_persistence(
            gemini_path,
            codex_path,
        )
        self.assert_consumer_artifact(
            brainstorm_artifact,
            brainstorm_argv,
            gemini_path,
            codex_path,
        )

    def test_M5_6_each_consumer_rederivation_mutation_is_rejected(self) -> None:
        gemini_path, codex_path = self.captured_pair(
            self.root / "consumer mutation base:="
        )
        # ALLOCATOR-SHAPED derived name. An approving write now refuses any transcript that is not
        # (PR #63 recheck, P1), so a plain `derived-*.txt` made the recipe exit non-zero and the
        # mutation stopped isolating its own variable — the rejection came from the evidence rule
        # rather than from the path re-derivation this cell exists to detect. The name is what makes
        # it allocator-shaped; it is still the WRONG path, which is the property under test.
        derived = self.root / ("COREDEV-2619r9-gemini-" + "c" * 32 + ".txt")
        self.write_transcript(derived, "derived gemini")
        self.bind_transcript_to_plan(str(derived))

        synthesis_old = (
            "    " + REVIEWER_FLAG + ' "$GEMINI_REVIEWER_SPEC" \\\n'
        )
        synthesis_new = (
            "    "
            + REVIEWER_FLAG
            + ' "gemini=APPROVE:${M5_DERIVED_PATH}" \\\n'
        )
        synthesis = _replace_once(
            self.synthesis_source(),
            synthesis_old,
            synthesis_new,
        )
        synthesis_artifact, synthesis_argv = self.run_persistence_recipe(
            synthesis,
            {
                "COMBINED_VERDICT": "APPROVE",
                "GEMINI_REVIEWER_SPEC": "gemini=APPROVE:" + gemini_path,
                "CODEX_REVIEWER_SPEC": "codex=APPROVE:" + codex_path,
                "M5_DERIVED_PATH": str(derived),
            },
        )
        with self.assertRaises(AssertionError):
            self.assert_consumer_artifact(
                synthesis_artifact,
                synthesis_argv,
                gemini_path,
                codex_path,
            )

        brainstorm_old = (
            "    "
            + REVIEWER_FLAG
            + ' "gemini=${GEMINI_STATUS}:${GEMINI_TRANSCRIPT}" \\\n'
        )
        brainstorm_new = (
            "    "
            + REVIEWER_FLAG
            + ' "gemini=APPROVE:${M5_DERIVED_PATH}" \\\n'
        )
        brainstorm = _replace_once(
            self.brainstorm_source(),
            brainstorm_old,
            brainstorm_new,
        )
        brainstorm_artifact, brainstorm_argv = self.run_persistence_recipe(
            brainstorm,
            {
                "COMBINED_VERDICT": "APPROVE",
                "GEMINI_STATUS": "APPROVE",
                "GEMINI_TRANSCRIPT": gemini_path,
                "CODEX_STATUS": "APPROVE",
                "CODEX_TRANSCRIPT": codex_path,
                "M5_DERIVED_PATH": str(derived),
            },
        )
        with self.assertRaises(AssertionError):
            self.assert_consumer_artifact(
                brainstorm_artifact,
                brainstorm_argv,
                gemini_path,
                codex_path,
            )


class M510SynthesisShapeProofs(M5PathFixture):
    def synthesis_bindings(
        self,
        gemini_path: Path,
        codex_path: Path,
        verdict: str,
    ) -> Dict[str, str]:
        return {
            "PLAN_PATH": str(self.reviewed / "FEATURE_PLAN.md"),
            "COMBINED_VERDICT": verdict,
            "GEMINI_REVIEWER_SPEC": "gemini=APPROVE:" + str(gemini_path),
            "CODEX_REVIEWER_SPEC": "codex=APPROVE:" + str(codex_path),
        }

    def assert_synthesis_shape(
        self, recipe: str, label: str, helper_source: Optional[str] = None
    ) -> None:
        base = self.root / (label + " delimiter:=base=more:still")
        base.mkdir()
        gemini_path = base / "gemini:=path=tail.txt"
        codex_path = base / "codex:=path=tail.txt"
        self.write_transcript(gemini_path, "gemini")
        self.write_transcript(codex_path, "codex")
        bindings = self.synthesis_bindings(gemini_path, codex_path, "APPROVE")
        argv = self.fake_writer_arguments(recipe, bindings, label, helper_source=helper_source)
        self.assertEqual(
            [
                bindings["GEMINI_REVIEWER_SPEC"],
                bindings["CODEX_REVIEWER_SPEC"],
            ],
            self.reviewer_arguments(argv),
        )

    def test_M5_10_assertion_first_delimiters_preserve_the_complete_paths(self) -> None:
        self.assert_synthesis_shape(self.synthesis_source(), "shape-positive")

    def test_M5_10_last_colon_split_mutation_is_rejected(self) -> None:
        # The split now lives in `persist-verdict.sh`, so the mutant replaces the HELPER the shipped
        # recipe calls rather than the recipe text. Same rule, same rejection, one copy of it.
        mutant = _replace_once(
            self.persist_helper_source(),
            'transcript="${rest#*:}"',
            'transcript="${rest##*:}"',
        )
        with self.assertRaises(AssertionError):
            self.assert_synthesis_shape(
                self.synthesis_source(), "shape-last-colon", helper_source=mutant
            )


class M515ArtifactProofs(M5PathFixture):
    def assert_artifact_case(
        self,
        label: str,
        base: Path,
        use_xdg: bool,
        home: Path,
    ) -> Tuple[str, str]:
        gemini_path, codex_path = self.captured_pair(
            base,
            use_xdg=use_xdg,
            home=home,
        )
        artifact, argv = self.run_synthesis(
            "gemini=APPROVE:" + gemini_path,
            "codex=APPROVE:" + codex_path,
            "APPROVE",
        )
        self.assert_consumer_artifact(
            artifact,
            argv,
            gemini_path,
            codex_path,
        )
        return gemini_path, codex_path

    def test_M5_15_assertion_canonical_emission_becomes_artifact_path(self) -> None:
        xdg_target = self.root / "artifact canonical XDG target"
        xdg_target.mkdir()
        xdg_link = self.root / "artifact lexical XDG link"
        xdg_link.symlink_to(xdg_target, target_is_directory=True)

        fallback_target = self.root / "artifact canonical fallback target"
        (fallback_target / ".local" / "state").mkdir(parents=True)
        fallback_link = self.root / "artifact lexical fallback home"
        fallback_link.symlink_to(fallback_target, target_is_directory=True)

        cases = (
            ("xdg", xdg_link, True, self.home, xdg_target.resolve()),
            (
                "fallback",
                self.root / "unused artifact XDG",
                False,
                fallback_link,
                (fallback_target / ".local" / "state").resolve(),
            ),
        )
        for label, base, use_xdg, home, canonical in cases:
            with self.subTest(base=label):
                gemini_path, codex_path = self.assert_artifact_case(
                    label,
                    base,
                    use_xdg,
                    home,
                )
                prefix = str(canonical) + os.sep
                self.assertTrue(gemini_path.startswith(prefix))
                self.assertTrue(codex_path.startswith(prefix))

    def test_M5_15_rederived_artifact_argument_mutation_is_rejected(self) -> None:
        gemini_path, codex_path = self.captured_pair(
            self.root / "artifact mutation base:="
        )
        # ALLOCATOR-SHAPED derived name. An approving write now refuses any transcript that is not
        # (PR #63 recheck, P1), so a plain `derived-*.txt` made the recipe exit non-zero and the
        # mutation stopped isolating its own variable — the rejection came from the evidence rule
        # rather than from the path re-derivation this cell exists to detect. The name is what makes
        # it allocator-shaped; it is still the WRONG path, which is the property under test.
        derived = self.root / ("COREDEV-2619r9-gemini-" + "a" * 32 + ".txt")
        self.write_transcript(derived, "artifact derived gemini")
        self.bind_transcript_to_plan(str(derived))
        old = "    " + REVIEWER_FLAG + ' "$GEMINI_REVIEWER_SPEC" \\\n'
        new = (
            "    "
            + REVIEWER_FLAG
            + ' "gemini=APPROVE:${M5_DERIVED_PATH}" \\\n'
        )
        mutant = _replace_once(self.synthesis_source(), old, new)
        artifact, argv = self.run_persistence_recipe(
            mutant,
            {
                "COMBINED_VERDICT": "APPROVE",
                "GEMINI_REVIEWER_SPEC": "gemini=APPROVE:" + gemini_path,
                "CODEX_REVIEWER_SPEC": "codex=APPROVE:" + codex_path,
                "M5_DERIVED_PATH": str(derived),
            },
        )
        with self.assertRaises(AssertionError):
            self.assert_consumer_artifact(
                artifact,
                argv,
                gemini_path,
                codex_path,
            )


class M517EmptyTranscriptProofs(M5PathFixture):
    def assert_empty_classification(
        self, recipe: str, label: str, helper_source: Optional[str] = None
    ) -> None:
        base = self.root / (label + " empty base")
        base.mkdir()
        gemini_path = base / "gemini-empty.txt"
        gemini_path.touch()
        codex_path = base / "codex-full.txt"
        self.write_transcript(codex_path, "codex")
        bindings = {
            "PLAN_PATH": str(self.reviewed / "FEATURE_PLAN.md"),
            "COMBINED_VERDICT": "DISAGREEMENT",
            "GEMINI_REVIEWER_SPEC": "gemini=APPROVE:" + str(gemini_path),
            "CODEX_REVIEWER_SPEC": "codex=APPROVE:" + str(codex_path),
        }
        argv = self.fake_writer_arguments(recipe, bindings, label, helper_source=helper_source)
        self.assertEqual(
            ["gemini=MISSING", bindings["CODEX_REVIEWER_SPEC"]],
            self.reviewer_arguments(argv),
        )

    def test_M5_17_assertion_empty_allocated_leaf_is_missing(self) -> None:
        self.assert_empty_classification(self.synthesis_source(), "empty-positive")

    def test_M5_17_exists_instead_of_nonempty_mutation_is_rejected(self) -> None:
        # `-s` (non-empty) vs `-e` (exists) now lives in the helper: an allocated-but-EMPTY leaf is a
        # FAILED review, and a mutant that only checks existence would count it as one that happened.
        old = 'if [ "$status" = MISSING ] || [ ! -s "$transcript" ]; then'
        new = 'if [ "$status" = MISSING ] || [ ! -e "$transcript" ]; then'
        mutant = _replace_once(self.persist_helper_source(), old, new)
        with self.assertRaises(AssertionError):
            self.assert_empty_classification(
                self.synthesis_source(), "empty-exists", helper_source=mutant
            )


class PersistedRecipeDriftProofs(M5PathFixture):
    """The drift that four copies of one rule produced, and that collapsing them to one removes.

    `review-synthesis/SKILL.md` documents `<reviewer>=MISSING` **without** a `:transcript` path as the
    recovery form for a reviewer that never ran. Its own inline copy of the parser required a colon and
    rejected exactly that form — the shipped recipe contradicted the shipped instructions two screens
    below it. `persist-verdict.sh` had already been fixed; the inline copy had not, because there were
    four of them.
    """

    def test_bare_missing_reviewer_is_the_documented_recovery_form(self) -> None:
        base = self.root / "bare missing base"
        base.mkdir()
        codex_path = base / "codex-full.txt"
        self.write_transcript(codex_path, "codex")
        bindings = {
            "PLAN_PATH": str(self.reviewed / "FEATURE_PLAN.md"),
            # A reviewer that never ran cannot yield an approving COMBINED verdict, so the recovery
            # form is only reachable on a non-approving one — asserting it on APPROVE would be
            # asserting the fail-closed rule is broken.
            "COMBINED_VERDICT": "DISAGREEMENT",
            "GEMINI_REVIEWER_SPEC": "gemini=MISSING",
            "CODEX_REVIEWER_SPEC": "codex=APPROVE:" + str(codex_path),
        }
        argv = self.fake_writer_arguments(self.synthesis_source(), bindings, "bare-missing")
        self.assertEqual(
            ["gemini=MISSING", bindings["CODEX_REVIEWER_SPEC"]],
            self.reviewer_arguments(argv),
        )

    def test_colon_requiring_parser_mutation_is_rejected(self) -> None:
        """The inline copy's rule, restored into the helper, must fail this."""
        mutant = _replace_once(
            self.persist_helper_source(),
            "        MISSING) status=MISSING; transcript=\"\" ;;\n",
            "",
        )
        base = self.root / "bare missing mutant base"
        base.mkdir()
        codex_path = base / "codex-full.txt"
        self.write_transcript(codex_path, "codex")
        bindings = {
            "PLAN_PATH": str(self.reviewed / "FEATURE_PLAN.md"),
            "COMBINED_VERDICT": "DISAGREEMENT",
            "GEMINI_REVIEWER_SPEC": "gemini=MISSING",
            "CODEX_REVIEWER_SPEC": "codex=APPROVE:" + str(codex_path),
        }
        with self.assertRaises(AssertionError):
            self.fake_writer_arguments(
                self.synthesis_source(),
                bindings,
                "bare-missing-mutant",
                helper_source=mutant,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
