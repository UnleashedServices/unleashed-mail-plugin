#!/usr/bin/env python3
"""COREDEV-2619 S-RELEASE assertion/mutation proof pairs.

Every destructive exercise in this module is confined to a synthetic state
tree created by ``tempfile.TemporaryDirectory``.  The production cleanup is
never invoked with an implicit or real HOME-derived path.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path, PurePosixPath
from types import ModuleType, SimpleNamespace
from typing import Callable, Dict, Iterable, List, Sequence, Tuple
from unittest import mock


REPO = Path(__file__).resolve().parents[2]
PRODUCTION_PATH = REPO / "scripts" / "review" / "cleanup_coredev_2619_leaks.py"
PLAN_PATH = REPO / "docs" / "planning" / "COREDEV-2619_PER_RUN_TRANSCRIPT_PATHS_PLAN.md"
PLUGIN_PATH = REPO / ".claude-plugin" / "plugin.json"
README_PATH = REPO / "README.md"
CHANGELOG_PATH = REPO / "CHANGELOG.md"

BASELINE_VERSION = (2, 6, 6)
CEILING_SENTENCE = (
    "Per-run paths prevent accidental transcript collisions and stale reuse; "
    "they do not make the gate tamper-proof, establish operator provenance, or "
    "protect a host where an attacker controls a state-directory ancestor."
)
RETAINED_GRANTS_SENTENCE = (
    "The existing `${CLAUDE_PLUGIN_ROOT}` allowed-"
    "tools grants are retained because "
    "Claude Code 2.1.0 and later expand that placeholder."
)
CEILING_CLAUSES = (
    "prevent accidental transcript collisions and stale reuse",
    "do not make the gate tamper-proof",
    "establish operator provenance",
    "protect a host where an attacker controls a state-directory ancestor",
)


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise AssertionError("could not load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


production = _load_module(PRODUCTION_PATH, "coredev2619_release_cleanup")
PRODUCTION_SOURCE = PRODUCTION_PATH.read_text(encoding="utf-8")


def _plan_manifest() -> Tuple[Tuple[str, str], ...]:
    source = PLAN_PATH.read_text(encoding="utf-8")
    start = source.index('10. **`S-RELEASE`**')
    end = source.index("This is the closed output", start)
    entries = re.findall(
        r"^\s+- \*\*([^*]+)\*\* — `([^`]+)`$",
        source[start:end],
        flags=re.MULTILINE,
    )
    if len(entries) != 39:
        raise AssertionError("S-RELEASE must carry exactly 39 typed manifest entries")
    return tuple(entries)


PLAN_MANIFEST = _plan_manifest()
EXPECTED_PATHS = tuple(path for _expected_type, path in PLAN_MANIFEST)
EXPECTED_TYPES = {path: expected_type for expected_type, path in PLAN_MANIFEST}
EXPECTED_DIRECTORIES = tuple(
    sorted(
        {PurePosixPath(path).parent.as_posix() for path in EXPECTED_PATHS},
        key=lambda path: (-len(PurePosixPath(path).parts), os.fsencode(path)),
    )
)


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise AssertionError("mutation anchor must occur exactly once: " + repr(old))
    return source.replace(old, new, 1)


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError("expected one function named " + name)
    return matches[0]


def _call_leaf(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _assert_literal_unlink_source_contract(source: str) -> None:
    tree = ast.parse(source, filename=str(PRODUCTION_PATH), feature_version=9)
    delete_function = _function(tree, "delete_leak_files")
    unlink_function = _function(tree, "unlink_regular_file")

    literal_loops = [
        node
        for node in ast.walk(delete_function)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Name)
        and node.iter.id == "LEAK_MANIFEST"
    ]
    if len(literal_loops) != 1:
        raise AssertionError("file deletion must iterate LEAK_MANIFEST literally once")

    forbidden = {
        "call",
        "glob",
        "popen",
        "Popen",
        "remove",
        "removedirs",
        "rename",
        "renames",
        "replace",
        "rglob",
        "rmdir",
        "rmtree",
        "run",
        "system",
    }
    phase_calls = [
        _call_leaf(node)
        for function in (delete_function, unlink_function)
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
    ]
    used_forbidden = sorted(set(phase_calls) & forbidden)
    if used_forbidden:
        raise AssertionError("forbidden file-deletion primitive: " + ", ".join(used_forbidden))

    unlink_calls = [
        node
        for node in ast.walk(unlink_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "unlink"
    ]
    if len(unlink_calls) != 1:
        raise AssertionError("non-recursive unlink routine must call os.unlink exactly once")


def _version(value: str) -> Tuple[int, int, int]:
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", value)
    if match is None:
        raise AssertionError("not a semantic version: " + repr(value))
    return tuple(int(group) for group in match.groups())  # type: ignore[return-value]


def _first_match(pattern: str, source: str, label: str) -> str:
    match = re.search(pattern, source, flags=re.MULTILINE)
    if match is None:
        raise AssertionError("missing " + label)
    return match.group(1)


def _latest_changelog_release(changelog: str) -> Tuple[str, str]:
    heading = re.search(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\].*$", changelog, re.MULTILINE)
    if heading is None:
        raise AssertionError("CHANGELOG has no release heading")
    following = re.search(
        r"^## \[[0-9]+\.[0-9]+\.[0-9]+\].*$",
        changelog[heading.end() :],
        re.MULTILINE,
    )
    end = len(changelog) if following is None else heading.end() + following.start()
    return heading.group(1), changelog[heading.start() : end]


def _assert_release_metadata_contract(plugin: str, readme: str, changelog: str) -> None:
    plugin_version = json.loads(plugin)["version"]
    if _version(plugin_version) <= BASELINE_VERSION:
        raise AssertionError("plugin version must be greater than 2.6.6")

    readme_h1 = _first_match(
        r"^# UnleashedMail — Claude Code Plugin v([0-9]+\.[0-9]+\.[0-9]+)$",
        readme,
        "README H1 version",
    )
    readme_latest = _first_match(
        r"^### v([0-9]+\.[0-9]+\.[0-9]+)$",
        readme,
        "README newest-version heading",
    )
    changelog_version, newest_entry = _latest_changelog_release(changelog)
    if (readme_h1, readme_latest, changelog_version) != (
        plugin_version,
        plugin_version,
        plugin_version,
    ):
        raise AssertionError("release version fields are not synchronized")
    # These two are COREDEV-2619 disclosures — the honest ceiling on what per-run paths buy, and why
    # the `${CLAUDE_PLUGIN_ROOT}` grants were retained rather than removed. They are checked against the
    # WHOLE changelog, not the newest entry.
    #
    # Newest-entry was wrong in both directions once a later release landed. It would force every
    # future release to repeat 2619's ceiling verbatim whether or not it shipped anything related —
    # and worse, the retained-grants sentence became FALSE at 2.7.0, where those grants were REPLACED
    # by exact entrypoints rather than retained. A disclosure that must be restated to stay green is a
    # disclosure that will eventually be restated untruthfully.
    #
    # What must hold permanently is that neither statement is ever DELETED from the record, and that
    # nothing anywhere claims the grants were inert. That is what is asserted.
    if CEILING_SENTENCE not in changelog:
        raise AssertionError("CHANGELOG is missing the exact ceiling sentence")
    if RETAINED_GRANTS_SENTENCE not in changelog:
        raise AssertionError("CHANGELOG is missing the retained-grants sentence")

    for paragraph in re.split(r"\n\s*\n", changelog):
        if "${CLAUDE_PLUGIN_ROOT}" in paragraph and "inert" in paragraph.casefold():
            raise AssertionError("CHANGELOG claims retained grants were inert")


class SyntheticStateTreeMixin:
    def make_state_tree(
        self,
        filename_family_canary: bool = False,
        root_canary: bool = False,
    ) -> Tuple[Path, Dict[str, Path]]:
        temporary = tempfile.TemporaryDirectory(prefix="coredev-2619-release-")
        self.addCleanup(temporary.cleanup)
        temporary_root = Path(temporary.name)
        state_root = (
            temporary_root
            / "synthetic-home"
            / ".local"
            / "state"
            / "unleashed-mail"
            / "review-transcripts"
        )
        state_root.mkdir(parents=True)
        objects = {}  # type: Dict[str, Path]
        for relative_path in EXPECTED_PATHS:
            target = state_root.joinpath(*PurePosixPath(relative_path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((relative_path + "\n").encode("ascii"))
            objects[relative_path] = target

        if filename_family_canary:
            canary = state_root / EXPECTED_DIRECTORIES[0] / "COREDEV-9999r1-codex-unlisted.txt"
            canary.write_bytes(b"unlisted filename-family canary\n")
            objects["family-canary"] = canary
        if root_canary:
            canary = state_root / "unlisted-root-canary.keep"
            canary.write_bytes(b"unlisted root canary\n")
            objects["root-canary"] = canary
        return state_root, objects

    def assert_all_manifest_paths_exist(self, state_root: Path) -> None:
        for relative_path in EXPECTED_PATHS:
            self.assertTrue(
                state_root.joinpath(*PurePosixPath(relative_path).parts).exists(),
                relative_path,
            )


class ReleaseCleanupProofs(SyntheticStateTreeMixin, unittest.TestCase):
    maxDiff = None

    def assert_file_deletion_contract(
        self,
        cleaner: Callable[[Path], object],
    ) -> None:
        state_root, objects = self.make_state_tree(filename_family_canary=True)
        root_before = os.stat(str(state_root), follow_symlinks=False)
        report = cleaner(state_root)

        self.assertTrue(state_root.is_dir(), "the state root must survive")
        root_after = os.stat(str(state_root), follow_symlinks=False)
        self.assertEqual(
            (root_before.st_dev, root_before.st_ino),
            (root_after.st_dev, root_after.st_ino),
            "recursive deletion/root replacement must change this identity",
        )
        self.assertEqual(
            Counter(EXPECTED_PATHS),
            Counter(report.attempted_relative_paths),
            "attempted deletion multiset must equal the plan manifest",
        )
        self.assertEqual(
            set(EXPECTED_PATHS),
            set(report.attempted_relative_paths),
            "attempted deletion set must equal the plan manifest",
        )
        for relative_path in EXPECTED_PATHS:
            self.assertFalse(
                state_root.joinpath(*PurePosixPath(relative_path).parts).exists(),
                relative_path,
            )
        self.assertTrue(objects["family-canary"].is_file())
        for relative_directory in EXPECTED_DIRECTORIES:
            self.assertTrue(
                state_root.joinpath(*PurePosixPath(relative_directory).parts).is_dir()
            )

    def test_M2_25_literal_manifest_and_nonrecursive_unlink_assertions_hold(self) -> None:
        self.assertEqual(39, len(PLAN_MANIFEST))
        self.assertEqual({"regular file"}, set(EXPECTED_TYPES.values()))
        self.assertEqual(9, len(EXPECTED_DIRECTORIES))
        self.assertEqual(
            PLAN_MANIFEST,
            tuple(
                (entry.expected_type, entry.relative_path)
                for entry in production.LEAK_MANIFEST
            ),
        )
        self.assertEqual(EXPECTED_DIRECTORIES, production.EMPTY_DIRECTORY_MANIFEST)
        _assert_literal_unlink_source_contract(PRODUCTION_SOURCE)
        self.assert_file_deletion_contract(production.delete_leak_files)

    def test_M2_25_filename_family_glob_mutation_is_rejected(self) -> None:
        def glob_mutant(state_root: Path) -> object:
            root_metadata = os.stat(str(state_root), follow_symlinks=False)
            removed = []  # type: List[str]
            for target in state_root.rglob("*.txt*"):
                if target.is_file():
                    removed.append(target.relative_to(state_root).as_posix())
                    target.unlink()
            return SimpleNamespace(
                attempted_relative_paths=tuple(removed),
                root_identity=(root_metadata.st_dev, root_metadata.st_ino),
            )

        with self.assertRaises(AssertionError):
            self.assert_file_deletion_contract(glob_mutant)

    def test_M2_25_recursive_root_deletion_mutation_is_rejected(self) -> None:
        def recursive_root_mutant(state_root: Path) -> object:
            root_metadata = os.stat(str(state_root), follow_symlinks=False)
            shutil.rmtree(state_root)
            return SimpleNamespace(
                attempted_relative_paths=EXPECTED_PATHS,
                root_identity=(root_metadata.st_dev, root_metadata.st_ino),
            )

        with self.assertRaises(AssertionError):
            self.assert_file_deletion_contract(recursive_root_mutant)

    def test_M2_25_forbidden_primitive_source_mutations_are_rejected(self) -> None:
        # Indented one level deeper than it used to be: the removal loop now runs inside the
        # `held_manifest_parents` block. A stale anchor here is not a cosmetic miss — it would make
        # every mutation below a no-op, and four mutants that change nothing all "fail" the contract
        # for free. `_replace_once` raising on a zero-hit anchor is what surfaced it.
        loop_anchor = (
            "        for entry in LEAK_MANIFEST:\n"
            "            attempted.append(entry.relative_path)\n"
        )
        mutations = {
            "filename-glob": _replace_once(
                PRODUCTION_SOURCE,
                loop_anchor,
                "        for entry in root.rglob(\"*.txt*\"):\n"
                "            attempted.append(str(entry))\n",
            ),
            # Re-anchored when the removal phase moved onto parent descriptors: the primitive is now
            # `os.unlink(name, dir_fd=...)`, so the pre-descriptor anchor matched nothing and
            # `_replace_once` refused rather than silently mutating no bytes — which is exactly why
            # it raises on a zero-hit anchor instead of returning the source unchanged.
            "directory-removal": _replace_once(
                PRODUCTION_SOURCE,
                "    os.unlink(name, dir_fd=descriptor)\n",
                "    os.rmdir(name, dir_fd=descriptor)\n",
            ),
            "root-replacement": _replace_once(
                PRODUCTION_SOURCE,
                "    os.unlink(name, dir_fd=descriptor)\n",
                "    os.replace(name, \"..\", src_dir_fd=descriptor)\n",
            ),
            "shell": _replace_once(
                PRODUCTION_SOURCE,
                "    os.unlink(name, dir_fd=descriptor)\n",
                "    os.system(\"rm -f -- \" + name)\n",
            ),
        }
        for label, mutant in mutations.items():
            with self.subTest(mutation=label), self.assertRaises(AssertionError):
                _assert_literal_unlink_source_contract(mutant)

    def test_M2_25_canonical_escape_mutation_fails_before_any_unlink(self) -> None:
        state_root, objects = self.make_state_tree()
        outside = state_root.parents[4] / "outside-target.txt"
        outside.write_bytes(b"outside must survive\n")
        victim = objects[EXPECTED_PATHS[0]]
        victim.unlink()
        victim.symlink_to(outside)

        with self.assertRaisesRegex(production.CleanupError, "escapes the state root"):
            production.delete_leak_files(state_root)

        self.assertTrue(victim.is_symlink())
        self.assertEqual(b"outside must survive\n", outside.read_bytes())
        for relative_path in EXPECTED_PATHS[1:]:
            self.assertTrue(objects[relative_path].is_file())

    def test_M2_25_type_mismatch_mutation_fails_before_any_unlink(self) -> None:
        state_root, objects = self.make_state_tree()
        victim = objects[EXPECTED_PATHS[-1]]
        victim.unlink()
        victim.mkdir()

        with self.assertRaisesRegex(production.CleanupError, "type mismatch"):
            production.delete_leak_files(state_root)

        self.assertTrue(victim.is_dir())
        for relative_path in EXPECTED_PATHS[:-1]:
            self.assertTrue(objects[relative_path].is_file())

    def test_M2_25_full_cleanup_preserves_root_canary_and_removes_exactly_nine_dirs(self) -> None:
        state_root, objects = self.make_state_tree(root_canary=True)
        root_before = os.stat(str(state_root), follow_symlinks=False)

        report = production.cleanup_coredev_2619_leaks(state_root)

        root_after = os.stat(str(state_root), follow_symlinks=False)
        self.assertEqual(
            (root_before.st_dev, root_before.st_ino),
            (root_after.st_dev, root_after.st_ino),
        )
        self.assertEqual(Counter(EXPECTED_PATHS), Counter(report.attempted_relative_paths))
        self.assertEqual(EXPECTED_DIRECTORIES, report.removed_directories)
        self.assertEqual(9, len(report.removed_directories))
        self.assertTrue(objects["root-canary"].is_file())
        for relative_directory in EXPECTED_DIRECTORIES:
            self.assertFalse(
                state_root.joinpath(*PurePosixPath(relative_directory).parts).exists()
            )

    def test_M2_25_directory_omission_mutation_is_rejected_before_deletion(self) -> None:
        state_root, _objects = self.make_state_tree()
        with mock.patch.object(
            production,
            "EMPTY_DIRECTORY_MANIFEST",
            production.EMPTY_DIRECTORY_MANIFEST[:-1],
        ):
            with self.assertRaisesRegex(production.CleanupError, "9 unique paths"):
                production.cleanup_coredev_2619_leaks(state_root)
        self.assert_all_manifest_paths_exist(state_root)

    def test_M2_25_deepest_first_assertion_rejects_shallow_first_mutation(self) -> None:
        state_root, _objects = self.make_state_tree()
        nested_root = state_root / "ordering-fixture"
        (nested_root / "parent" / "child").mkdir(parents=True)
        # `(satisfied, actually removed)` — the two differ when an entry was already absent, which is
        # what lets `--apply` report removals it performed instead of removals it attempted.
        removed, rmdired = production._remove_empty_directories(
            nested_root,
            ("parent", "parent/child"),
        )
        self.assertEqual(("parent/child", "parent"), removed)
        self.assertEqual(("parent/child", "parent"), rmdired)

        mutant_source = _replace_once(
            PRODUCTION_SOURCE,
            "    return -len(relative.parts), os.fsencode(relative.as_posix())\n",
            "    return len(relative.parts), os.fsencode(relative.as_posix())\n",
        )
        with tempfile.TemporaryDirectory(prefix="coredev-2619-order-mutant-") as raw:
            mutant_path = Path(raw) / "cleanup_mutant.py"
            mutant_path.write_text(mutant_source, encoding="utf-8")
            mutant = _load_module(mutant_path, "coredev2619_shallow_first_mutant")
            mutant_root = Path(raw) / "mutant-root"
            (mutant_root / "parent" / "child").mkdir(parents=True)
            with self.assertRaisesRegex(mutant.CleanupError, "not empty"):
                mutant._remove_empty_directories(
                    mutant_root,
                    ("parent", "parent/child"),
                )

    def test_M2_25_nonempty_directory_mutation_stops_without_recursing(self) -> None:
        state_root, _objects = self.make_state_tree()
        blocking_directory = state_root.joinpath(
            *PurePosixPath(EXPECTED_DIRECTORIES[0]).parts
        )
        nested_canary = blocking_directory / "unlisted" / "keep.txt"
        nested_canary.parent.mkdir()
        nested_canary.write_bytes(b"must survive\n")
        root_before = os.stat(str(state_root), follow_symlinks=False)

        # The refusal now happens BEFORE the unlink phase, so its message is the pre-unlink one.
        # This assertion used to read "not empty" and then require every manifest file to be GONE —
        # it was pinning the defect: apply deleted all 39 files and only then refused, so a directory
        # that could never be emptied still cost the whole tree (deep review, P2).
        with self.assertRaisesRegex(production.CleanupError, "refusing to delete anything"):
            production.cleanup_coredev_2619_leaks(state_root)

        root_after = os.stat(str(state_root), follow_symlinks=False)
        self.assertEqual(
            (root_before.st_dev, root_before.st_ino),
            (root_after.st_dev, root_after.st_ino),
        )
        self.assertEqual(b"must survive\n", nested_canary.read_bytes())
        for relative_path in EXPECTED_PATHS:
            self.assertTrue(
                state_root.joinpath(*PurePosixPath(relative_path).parts).exists(),
                f"{relative_path} was deleted by a run that then refused — refusal must cost nothing",
            )
        for relative_directory in EXPECTED_DIRECTORIES:
            self.assertTrue(
                state_root.joinpath(*PurePosixPath(relative_directory).parts).is_dir()
            )

    def test_cli_requires_apply_and_uses_only_the_explicit_synthetic_root(self) -> None:
        state_root, objects = self.make_state_tree(root_canary=True)
        fake_home = state_root.parents[4] / "different-synthetic-home"
        fake_home.mkdir()
        home_canary = fake_home / "must-not-be-read-or-removed"
        home_canary.write_bytes(b"fake HOME canary\n")
        environment = dict(os.environ)
        environment["HOME"] = str(fake_home)

        refused = subprocess.run(
            [sys.executable, str(PRODUCTION_PATH), "--state-root", str(state_root)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=False,
            text=True,
        )
        self.assertEqual(2, refused.returncode)
        self.assert_all_manifest_paths_exist(state_root)

        applied = subprocess.run(
            [
                sys.executable,
                str(PRODUCTION_PATH),
                "--state-root",
                str(state_root),
                "--apply",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=False,
            text=True,
        )
        self.assertEqual(0, applied.returncode, applied.stderr)
        self.assertIn("removed 39 of 39 manifest files and 9 of 9 empty manifest directories",
                      applied.stdout)
        self.assertTrue(objects["root-canary"].is_file())
        self.assertEqual(b"fake HOME canary\n", home_canary.read_bytes())


class ReleaseMetadataProofs(unittest.TestCase):
    def release_sources(self) -> Tuple[str, str, str]:
        return (
            PLUGIN_PATH.read_text(encoding="utf-8"),
            README_PATH.read_text(encoding="utf-8"),
            CHANGELOG_PATH.read_text(encoding="utf-8"),
        )

    def test_M2_14_version_increase_and_ceiling_assertions_hold(self) -> None:
        _assert_release_metadata_contract(*self.release_sources())

    def test_M2_14_synchronized_version_decrease_mutation_is_rejected(self) -> None:
        plugin, readme, changelog = self.release_sources()
        plugin_object = json.loads(plugin)
        current = plugin_object["version"]
        plugin_object["version"] = "2.6.5"
        plugin_mutant = json.dumps(plugin_object)
        readme_mutant = _replace_once(
            readme,
            "Plugin v" + current,
            "Plugin v2.6.5",
        )
        readme_mutant = _replace_once(
            readme_mutant,
            "### v" + current,
            "### v2.6.5",
        )
        changelog_mutant = _replace_once(
            changelog,
            "## [" + current + "]",
            "## [2.6.5]",
        )

        with self.assertRaisesRegex(AssertionError, "greater than 2.6.6"):
            _assert_release_metadata_contract(
                plugin_mutant,
                readme_mutant,
                changelog_mutant,
            )

    def test_M2_14_each_ceiling_clause_deletion_mutation_is_rejected(self) -> None:
        plugin, readme, changelog = self.release_sources()
        for clause in CEILING_CLAUSES:
            with self.subTest(clause=clause):
                mutant = _replace_once(changelog, clause, "[deleted ceiling clause]")
                with self.assertRaisesRegex(AssertionError, "ceiling sentence"):
                    _assert_release_metadata_contract(plugin, readme, mutant)

    def test_M2_17_retained_grants_sentence_deletion_mutation_is_rejected(self) -> None:
        plugin, readme, changelog = self.release_sources()
        mutant = _replace_once(changelog, RETAINED_GRANTS_SENTENCE, "")
        with self.assertRaisesRegex(AssertionError, "retained-grants sentence"):
            _assert_release_metadata_contract(plugin, readme, mutant)

    def test_M2_17_inert_grants_claim_mutation_is_rejected_independently(self) -> None:
        plugin, readme, changelog = self.release_sources()
        inert_claim = (
            "\n\nThe existing `${CLAUDE_PLUGIN_ROOT}` allowed-"
            "tools grants were inert."
        )
        mutant = _replace_once(
            changelog,
            RETAINED_GRANTS_SENTENCE,
            RETAINED_GRANTS_SENTENCE + inert_claim,
        )
        self.assertIn(RETAINED_GRANTS_SENTENCE, mutant)
        with self.assertRaisesRegex(AssertionError, "claims retained grants were inert"):
            _assert_release_metadata_contract(plugin, readme, mutant)




class ResumeAndCheckProofs(SyntheticStateTreeMixin, unittest.TestCase):
    """PR #63 review, gap 5 — the tool was all-or-abort with no dry run and no resume.

    A single failed unlink (EACCES, I/O error, concurrent removal) left entries 1..n-1 deleted, and
    every later invocation then aborted at preflight on "manifest target is unavailable" — so the
    REMAINING leaks could never be removed by the sanctioned tool again, forcing exactly the ad-hoc
    `rm` in a sensitive directory that the closed-manifest design exists to prevent.
    """

    maxDiff = None

    def test_apply_resumes_after_a_partial_run(self) -> None:
        state_root, _objects = self.make_state_tree()
        for relative_path in EXPECTED_PATHS[:9]:
            state_root.joinpath(*PurePosixPath(relative_path).parts).unlink()

        code = production.main(["--state-root", str(state_root), "--apply"])

        self.assertEqual(0, code, "a partially-cleaned tree must still be completable")
        for relative_path in EXPECTED_PATHS:
            self.assertFalse(
                state_root.joinpath(*PurePosixPath(relative_path).parts).exists(), relative_path
            )

    def test_apply_resumes_after_a_run_that_died_in_the_DIRECTORY_phase(self) -> None:
        """The half the first resumability fix missed (found by Kimi K3-max).

        `delete_leak_files` tolerated an already-deleted FILE, but `_preflight_directories` still
        aborted on the first directory a previous run had already removed — so a run that died
        during directory removal left the tool unrecoverable exactly as before, and the commit
        claiming resumability did not achieve it. Reproduced: 0 files remaining, 4 of 9 directories
        gone, `--apply` exited 1 and removed nothing.
        """
        state_root, _objects = self.make_state_tree()
        for relative_path in EXPECTED_PATHS:
            state_root.joinpath(*PurePosixPath(relative_path).parts).unlink()
        for directory in EXPECTED_DIRECTORIES[:4]:
            (state_root / directory).rmdir()

        code = production.main(["--state-root", str(state_root), "--apply"])

        self.assertEqual(0, code, "a run that died mid-directory-phase must be completable")
        for directory in EXPECTED_DIRECTORIES:
            self.assertFalse((state_root / directory).exists(), directory)

    def test_directory_absence_tolerance_still_fails_closed_on_a_type_mismatch(self) -> None:
        """Absence is satisfied; a DIRECTORY replaced by a FILE still aborts with nothing removed.

        NAMED FOR WHAT IT PROVES. It does NOT isolate `_preflight_directories`' S_ISDIR check:
        deleting that check keeps this green, because `_preflight_files` then aborts anyway —
        `lstat` on a manifest file whose parent is now a regular file raises ENOTDIR, not
        FileNotFoundError, so the absence tolerance does not swallow it. The S_ISDIR check is
        defence-in-depth here, and this fixture cannot discriminate it. Claiming otherwise would
        make this a proof of something it does not establish.
        """
        state_root, _objects = self.make_state_tree()
        target = state_root / EXPECTED_DIRECTORIES[0]
        shutil.rmtree(target)
        target.write_text("not a directory", encoding="utf-8")

        code = production.main(["--state-root", str(state_root), "--apply"])

        self.assertEqual(1, code, "a manifest directory of the wrong type must still fail closed")
        self.assertTrue(target.is_file(), "the mismatched object itself must be untouched")
        # The load-bearing assertion is that NOTHING was removed — a rejected tree must be left
        # exactly as found, whichever preflight rejected it.
        # Only the files OUTSIDE the replaced directory — `rmtree` above necessarily removed the
        # manifest files that lived inside it, so requiring all 39 would be unsatisfiable.
        outside = [p for p in EXPECTED_PATHS if not p.startswith(EXPECTED_DIRECTORIES[0] + "/")]
        self.assertTrue(outside, "fixture invalid: no files outside the replaced directory")
        for relative_path in outside:
            self.assertTrue(
                state_root.joinpath(*PurePosixPath(relative_path).parts).exists(),
                "preflight must reject the tree BEFORE the file phase runs: " + relative_path,
            )

    def test_check_reports_without_removing_anything(self) -> None:
        state_root, _objects = self.make_state_tree()

        code = production.main(["--state-root", str(state_root), "--check"])

        self.assertEqual(0, code)
        self.assert_all_manifest_paths_exist(state_root)
        for directory in EXPECTED_DIRECTORIES:
            self.assertTrue((state_root / directory).is_dir(), directory)

    def test_check_and_apply_together_are_refused(self) -> None:
        state_root, _objects = self.make_state_tree()

        code = production.main(["--state-root", str(state_root), "--check", "--apply"])

        self.assertEqual(2, code, "an ambiguous destructive/read-only request must refuse")
        self.assert_all_manifest_paths_exist(state_root)

    def test_tolerating_absence_does_not_weaken_the_preflight_type_guard(self) -> None:
        """Absence is satisfied, a WRONG TYPE still aborts — and aborts BEFORE any deletion.

        The discriminating detail is that the mismatch is placed mid-manifest, not first. Asserting
        only "exit 1, target intact" does NOT test the preflight guard: `unlink_regular_file` has its
        own S_ISREG check, so removing the preflight guard entirely still yields exit 1 with the
        directory intact. That version of this test passed under mutation — the outcome was preserved
        by a different mechanism than the one named. With the mismatch at index 20, preflight rejecting
        the whole tree means the first 20 files SURVIVE; without it, they are deleted before the
        downstream guard trips. That difference is what makes this a proof rather than a coincidence.
        """
        state_root, _objects = self.make_state_tree()
        mismatch_index = 20
        target = state_root.joinpath(*PurePosixPath(EXPECTED_PATHS[mismatch_index]).parts)
        target.unlink()
        target.mkdir()

        code = production.main(["--state-root", str(state_root), "--apply"])

        self.assertEqual(1, code, "a manifest target of the wrong type must still fail closed")
        self.assertTrue(target.is_dir(), "the mismatched object itself must be untouched")
        for relative_path in EXPECTED_PATHS[:mismatch_index]:
            self.assertTrue(
                state_root.joinpath(*PurePosixPath(relative_path).parts).exists(),
                "preflight must reject the tree BEFORE deleting anything: " + relative_path,
            )


class CheckApplyAgreementProofs(SyntheticStateTreeMixin, unittest.TestCase):
    """`--check` must never report green for a state `--apply` refuses (deep review, P2).

    `--check` never ran the emptiness scan; `--apply` deleted all 39 files and only THEN refused a
    non-empty directory. A file dropped in between — a concurrent review run is enough — produced a
    green check followed by a destructive partial apply. The check is the signal an operator uses to
    decide the destructive half is safe, so a false green there is worse than no check at all.
    """

    def _run_cli(self, state_root: Path, *flags: str):
        return subprocess.run(
            [sys.executable, str(PRODUCTION_PATH), "--state-root", str(state_root), *flags],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_check_and_apply_agree_on_a_clean_tree(self):
        state_root, _objects = self.make_state_tree()
        check = self._run_cli(state_root, "--check")
        self.assertEqual(0, check.returncode, check.stderr)

        apply_result = self._run_cli(state_root, "--apply")
        self.assertEqual(0, apply_result.returncode, apply_result.stderr)

    def test_an_unaccounted_child_makes_check_refuse_too(self):
        """The asymmetry itself: same tree, and the two halves must reach the same verdict."""
        state_root, _objects = self.make_state_tree()
        intruder = state_root / EXPECTED_DIRECTORIES[0] / "concurrent-review-run.txt"
        intruder.write_bytes(b"a round that started between check and apply\n")

        check = self._run_cli(state_root, "--check")
        self.assertNotEqual(0, check.returncode, "check reported green for a state apply refuses")
        self.assertIn("NOT SAFE TO APPLY", check.stderr)
        self.assertIn("concurrent-review-run.txt", check.stderr)

    def test_apply_refuses_before_deleting_anything(self):
        """The load-bearing half: refusal must cost nothing.

        Asserted on the FILES, not on the exit code — refusing after the unlink phase also exits
        non-zero, which is exactly the behaviour being fixed.
        """
        state_root, _objects = self.make_state_tree()
        intruder = state_root / EXPECTED_DIRECTORIES[0] / "concurrent-review-run.txt"
        intruder.write_bytes(b"dropped in before apply\n")

        result = self._run_cli(state_root, "--apply")
        self.assertNotEqual(0, result.returncode)
        self.assert_all_manifest_paths_exist(state_root)
        self.assertTrue(intruder.exists(), "the intruder must not be touched either")

    def test_manifest_subdirectories_do_not_count_as_unexpected(self):
        """A parent holding only manifest CHILDREN still reaches empty — the directory phase is
        deepest-first — so counting them as unexpected would refuse every legitimate run."""
        state_root, _objects = self.make_state_tree()
        unexpected = production.unexpected_directory_occupants(state_root)
        self.assertEqual({}, unexpected, f"a clean manifest tree must have no unexpected children: {unexpected}")


def _path_based_removal_mutant() -> ModuleType:
    """The pre-fix removal primitive: validate and unlink the RESOLVED PATH STRING.

    Faithful rather than convenient — the descriptors are still opened and held, exactly as the
    fixed code does; only the two syscalls that actually touch the filesystem go back to naming a
    path. So any divergence this mutant shows is attributable to the `dir_fd` removal and to nothing
    else that changed in this commit.
    """
    source = _replace_once(
        PRODUCTION_SOURCE,
        "            descriptor, name = holders[entry.relative_path]\n",
        "            descriptor, name = -1, str(resolved_targets[entry.relative_path])\n",
    )
    source = _replace_once(
        source,
        "    metadata = os.lstat(name, dir_fd=descriptor)\n    if not stat.S_ISREG",
        "    metadata = os.lstat(name)\n    if not stat.S_ISREG",
    )
    source = _replace_once(source, "    os.unlink(name, dir_fd=descriptor)\n", "    os.unlink(name)\n")

    mutant_path = Path(tempfile.mkdtemp(prefix="coredev-2619-mutant-")) / "path_based_removal.py"
    mutant_path.write_text(source, encoding="utf-8")
    return _load_module(mutant_path, "coredev2619_path_based_removal")


class DescriptorStabilityProofs(SyntheticStateTreeMixin, unittest.TestCase):
    """The removal phase must act on the objects it validated, not on their names (deep review, P2).

    `_preflight_files` resolves each target, proves it is a regular file and proves it is beneath the
    state root — and the removal loop then re-walked the resolved STRING. Every component gets looked
    up again, so a rename of one parent directory between the two walks silently retargets all 39
    unlinks. The transcript state root lives under `~/.local/state`, a same-account-writable tree, so
    the swap needs no privilege; and `--apply` gives 39 consecutive chances to land it.
    """

    def _swap_the_parent_aside(self, state_root: Path, directory: str):
        """Move one manifest directory away and stand a fresh one, full of decoys, in its place.

        The decoys stand in for a CONCURRENT review run's transcripts: files that are validly named,
        that the manifest names too, and that this cleanup has no business deleting because they are
        not the objects it inspected.
        """
        original = state_root / directory
        moved = state_root / (directory + ".moved")
        original.rename(moved)
        original.mkdir()
        under = [path for path in EXPECTED_PATHS if PurePosixPath(path).parent.as_posix() == directory]
        decoys = {}
        for relative_path in under:
            decoy = original / PurePosixPath(relative_path).name
            decoy.write_bytes(b"a concurrent run's transcript - must survive\n")
            decoys[relative_path] = decoy
        survivors = {path: moved / PurePosixPath(path).name for path in under}
        return survivors, decoys

    def _delete_with_a_swap_mid_phase(self, module: ModuleType, directory: str):
        state_root, _objects = self.make_state_tree()
        real_classifier = module._present_through_descriptors
        swapped = {}

        def classify_then_swap(holders):
            present = real_classifier(holders)
            # The exact window the finding names: preflight has spoken, nothing is deleted yet.
            swapped.update(zip(("originals", "decoys"), self._swap_the_parent_aside(state_root, directory)))
            return present

        module._present_through_descriptors = classify_then_swap
        self.addCleanup(setattr, module, "_present_through_descriptors", real_classifier)
        try:
            module.delete_leak_files(state_root)
            refused = None
        except module.CleanupError as error:
            refused = str(error)
        return swapped["originals"], swapped["decoys"], refused

    def test_a_parent_swapped_mid_phase_cannot_retarget_the_unlinks(self):
        directory = EXPECTED_DIRECTORIES[0]
        originals, decoys, refused = self._delete_with_a_swap_mid_phase(production, directory)

        self.assertIsNone(refused, "the validated objects are still there to remove")
        for relative_path, decoy in decoys.items():
            self.assertTrue(decoy.is_file(), "a bystander file was deleted: " + relative_path)
        for relative_path, original in originals.items():
            self.assertFalse(original.exists(), "the validated object survived: " + relative_path)

    def test_the_path_based_primitive_deletes_the_bystanders_instead(self):
        """The discrimination. Without this the test above passes on a filesystem that never raced.

        Same tree, same swap, same instant — only the two syscalls differ. The mutant destroys every
        decoy and leaves every object it actually inspected untouched, which is the failure inverted
        exactly: it deleted 39 files belonging to somebody else and reported success.
        """
        directory = EXPECTED_DIRECTORIES[0]
        mutant = _path_based_removal_mutant()
        originals, decoys, refused = self._delete_with_a_swap_mid_phase(mutant, directory)

        self.assertIsNone(refused, "the mutant reports success — that is the defect")
        self.assertTrue(
            all(not decoy.exists() for decoy in decoys.values()),
            "the path-based primitive must delete the bystanders (else this proves nothing)",
        )
        self.assertTrue(
            all(original.is_file() for original in originals.values()),
            "the path-based primitive must leave the validated objects behind",
        )



class HeldDescriptorRaceProofs(SyntheticStateTreeMixin, unittest.TestCase):
    """What the held-descriptor session guarantees — and, explicitly, what it cannot (PR #63 recheck).

    Two defects were reported together. The first is fully closed: `held_manifest_parents` said it
    opened each parent "once" and looped over `LEAK_MANIFEST`, so the nine directories were opened up
    to six times each, at different instants, and a swap between two of them split the run across two
    generations. It now opens the nine unique parents once each.

    The second — an occupant arriving between the scan and the unlinks — is NARROWED, not eliminated,
    and saying otherwise would be the same overclaim this release keeps correcting. The check now runs
    through the held descriptors immediately before the first unlink, so it cannot be defeated by a
    directory SWAP and there is no re-resolution between the answer and the act. But a file created
    after the last possible observation is unobservable at that point, by construction. The test below
    records that ceiling as an executable fact rather than leaving a reader to assume it is covered.
    """

    def _cleanup(self, root):
        return production.cleanup_coredev_2619_leaks(root)

    def _survivors(self, root):
        return sum(1 for relative in EXPECTED_PATHS
                   if root.joinpath(*PurePosixPath(relative).parts).exists())

    def test_an_occupant_present_before_the_run_costs_nothing(self):
        """THE GUARANTEE. This is the case an operator can actually rely on."""
        state_root, _objects = self.make_state_tree()
        (state_root / EXPECTED_DIRECTORIES[0] / "arrived.txt").write_bytes(b"concurrent run\n")

        with self.assertRaises(production.CleanupError):
            self._cleanup(state_root)
        self.assertEqual(39, self._survivors(state_root),
                         "a refusal must delete nothing — that is the whole point of checking first")

    def test_an_unbound_state_root_is_refused_rather_than_reported_clean(self):
        """Resumability made "everything absent" indistinguishable from "wrong directory".

        `allow_absent=True` is what lets a half-finished `--apply` be re-run — an entry already gone is
        the goal state. But it also meant a mistyped `--state-root` pointing at ANY existing directory
        satisfied all 39 files and all nine directories vacuously, so the run exited 0 and reported the
        leak removed while the real transcripts sat untouched elsewhere (PR #63 recheck, P2). A cleanup
        that cannot fail cannot be trusted when it passes.
        """
        wrong = Path(tempfile.mkdtemp(prefix="not-the-state-root-"))
        self.addCleanup(shutil.rmtree, wrong, ignore_errors=True)
        with self.assertRaises(production.CleanupError) as caught:
            self._cleanup(wrong)
        self.assertIn("unbound state root", str(caught.exception))

    def test_the_canonical_root_is_accepted_even_when_already_empty(self):
        """The binding must not break resumability: a COMPLETED cleanup legitimately leaves the
        canonical `unleashed-mail/review-transcripts` directory empty, and re-running must still say so
        rather than refusing."""
        base = Path(tempfile.mkdtemp(prefix="canonical-root-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        canonical = base / "unleashed-mail" / "review-transcripts"
        canonical.mkdir(parents=True)
        production._require_bound_state_root(canonical.resolve())  # must not raise

    def test_a_noncanonical_root_holding_manifest_entries_is_still_accepted(self):
        """The second half of the two-sided binding: the fixtures' throwaway roots are not named
        `review-transcripts`, and a genuinely resumable run always has entries left — so the presence of
        a manifest entry is itself the evidence that this is the tree the manifest describes."""
        state_root, _objects = self.make_state_tree()
        production._require_bound_state_root(Path(state_root).resolve())  # must not raise

    def test_the_nine_parents_are_opened_once_each_not_once_per_entry(self):
        """The first defect, asserted on the mechanism rather than on a comment.

        Counting opens is what distinguishes the fix from the version whose docstring already claimed
        it: that one looped over the 39 entries while saying "once".
        """
        opened = []
        real_open = os.open

        def counting_open(path, flags, *args, **kwargs):
            if flags & getattr(os, "O_DIRECTORY", 0):
                opened.append(path)
            return real_open(path, flags, *args, **kwargs)

        state_root, _objects = self.make_state_tree()
        os.open = counting_open
        try:
            self._cleanup(state_root)
        finally:
            os.open = real_open

        parents = {PurePosixPath(p).parent.as_posix() for p in EXPECTED_PATHS}
        self.assertEqual(9, len(parents))
        # NOT-PER-ENTRY, asserted as a CONSTANT (PR #63 recheck, P3). `assertLess(len(opened), 39)` had a
        # margin of 3 over the real 36 and never checked the named property — a regression to per-entry
        # opening for one lightly-populated parent could stay under 39 and pass. The cleanup descends
        # each chain twice (a file-unlink pass and a directory-removal pass), opening dirs RELATIVE to a
        # descriptor, so `opened` carries component NAMES and each leaf-parent component appears exactly
        # TWICE regardless of how many entries sit beneath it. The invariant that rules out "once per
        # entry" is that this count is the SAME small constant for every parent despite their differing
        # entry counts — a per-entry regression would make the busier parents show more.
        from collections import Counter

        opened_names = Counter(PurePosixPath(p).name for p in opened)
        leaf_counts = {PurePosixPath(parent).name: opened_names[PurePosixPath(parent).name]
                       for parent in parents}
        self.assertEqual(
            {2}, set(leaf_counts.values()),
            f"leaf-parent opens are not the constant two-pass count — per-entry regression? {leaf_counts}",
        )
        # And the parents do NOT all hold the same number of entries, so a constant open count genuinely
        # rules out per-entry scaling rather than coinciding with a uniform tree.
        entries_per_parent = Counter(PurePosixPath(p).parent.as_posix() for p in EXPECTED_PATHS)
        self.assertGreater(len(set(entries_per_parent.values())), 1,
                           "the fixture's parents must have DIFFERING entry counts for this proof to bite")

    def test_an_occupant_arriving_after_the_final_check_is_NOT_caught(self):
        """THE CEILING, recorded deliberately. This test passing is not a bug.

        A file created after the last observation cannot be seen at that observation. The run still
        refuses — the directory phase catches it — but the 39 files are already gone by then, so the
        refusal is a report rather than a prevention. Narrowing the window is all a check can do here;
        eliminating it would need the whole run to be atomic, which it cannot be.

        If this ever starts FAILING, something made the sequence atomic and this test should be
        replaced by the stronger guarantee, not deleted.
        """
        state_root, _objects = self.make_state_tree()
        occupant = state_root / EXPECTED_DIRECTORIES[0] / "arrived-late.txt"
        real_present = production._present_through_descriptors

        def arrive_then_classify(holders):
            occupant.write_bytes(b"raced the check\n")
            return real_present(holders)

        production._present_through_descriptors = arrive_then_classify
        self.addCleanup(setattr, production, "_present_through_descriptors", real_present)

        with self.assertRaises(production.CleanupError):
            self._cleanup(state_root)
        self.assertEqual(0, self._survivors(state_root),
                         "documented ceiling: the unlinks complete before the directory phase refuses")
        self.assertTrue(occupant.exists(), "the bystander itself is never touched")


if __name__ == "__main__":
    unittest.main()


class ApplyReportsWhatItRemoved(unittest.TestCase):
    """`--apply` printed ATTEMPTED counts under the word "removed" (PR #63 recheck, P2).

    A root that merely ENDS in `unleashed-mail/review-transcripts` — a stale XDG base, say — is
    accepted by the suffix binding, because a completed cleanup legitimately leaves that directory
    empty and the tool must stay idempotent. On such a root the run removed nothing and reported
    "removed 39 manifest files and 9 empty manifest directories". A message claiming more than the
    code did is worse than no message: it reads as "the leaks are gone" when they are untouched.

    The binding itself is not tightened, because the filesystem cannot distinguish a finished cleanup
    from a wrong root — so the run says exactly that instead of implying the former.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="cleanup-report-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.wrong = Path(self.tmp) / "stale-xdg" / "unleashed-mail" / "review-transcripts"
        self.wrong.mkdir(parents=True, mode=0o700)

    def _apply(self, root: Path):
        return subprocess.run(
            [sys.executable, str(PRODUCTION_PATH), "--apply", "--state-root", str(root)],
            capture_output=True, text=True, check=False,
        )

    def test_a_canonically_named_but_EMPTY_root_reports_zero_and_says_why(self):
        result = self._apply(self.wrong)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("removed 0 of 39 manifest files", result.stdout)
        self.assertIn("0 of 9 empty manifest directories", result.stdout)
        self.assertIn("same result a WRONG state root produces", result.stdout,
                      "a zero-removal run must not read as a completed cleanup")
        self.assertNotIn("removed 39 manifest files", result.stdout)

    def test_a_REAL_root_still_reports_its_removals_and_the_note_is_absent(self):
        """Discrimination: the note must appear only when nothing was removed."""
        fixture = ReleaseCleanupProofs("run")
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        state_root, _objects = fixture.make_state_tree()
        result = self._apply(state_root)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("removed 39 of 39 manifest files", result.stdout)
        self.assertNotIn("same result a WRONG state root produces", result.stdout)
