#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-CALLERS proof cells M5.13/M5.14/M5.15b."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType


REPO = Path(__file__).resolve().parents[2]
PRODUCTION_PATH = REPO / "scripts" / "review" / "callers_scan.py"
PRODUCTION_REL = "scripts/review/callers_scan.py"
TEST_REL = "scripts/tests/test_callers_scan.py"
EXEMPTION_PATH = "scripts/review/callers-scan-exemptions.tsv"
PENDING_PATHS = (PRODUCTION_REL, TEST_REL)


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


production = load_module(PRODUCTION_PATH, "coredev2619_callers_scan")


# This matcher is deliberately test-local.  It does not import production's regex,
# anchors, productions, candidate selector, prefix stripper, or matcher.
REFERENCE_ANCHORS = (b"/unleashed-mail:", b"gemini-review", b"codex-review")
REFERENCE_PREFIX = re.compile(
    br"\A(?:(?:[ \t]{0,3}(?:[-+*]|[0-9]+[.)])[ \t]+)|"
    br"(?:[ \t]{0,3}>[ \t]?)|(?: {4}|\t))*"
)
REFERENCE_PRODUCTIONS = frozenset(
    {
        b"/unleashed-mail:gemini-review --ticket <T> --round <N> <plan>",
        b"/unleashed-mail:codex-review --ticket <T> --round <N> <plan>",
    }
)


def reference_lines(payload: bytes) -> list[bytes]:
    if not payload:
        return []
    lines = payload.split(b"\n")
    if payload.endswith(b"\n"):
        lines.pop()
    return lines


def encode_lines(original: bytes, lines: list[bytes]) -> bytes:
    result = b"\n".join(lines)
    if original.endswith(b"\n"):
        result += b"\n"
    return result


def reference_strip(payload: bytes) -> bytes:
    match = REFERENCE_PREFIX.match(payload)
    if match is None:  # pragma: no cover - an anchored repeat always matches
        raise AssertionError("reference prefix did not match")
    return payload[match.end() :]


def reference_is_candidate(path: str, payload: bytes) -> bool:
    return path != EXEMPTION_PATH and any(
        anchor in payload for anchor in REFERENCE_ANCHORS
    )


def reference_is_exact(payload: bytes) -> bool:
    return reference_strip(payload) in REFERENCE_PRODUCTIONS


@dataclass(frozen=True, order=True)
class ReferenceIdentity:
    path: str
    line_number: int
    payload_sha256: str

    def serialize(self) -> bytes:
        return (
            self.path.encode("utf-8")
            + b"\t"
            + str(self.line_number).encode("ascii")
            + b"\t"
            + self.payload_sha256.encode("ascii")
        )


@dataclass(frozen=True)
class ReferenceCandidate:
    path: str
    line_number: int
    payload: bytes

    @property
    def identity(self) -> ReferenceIdentity:
        return ReferenceIdentity(
            self.path,
            self.line_number,
            hashlib.sha256(self.payload).hexdigest(),
        )


def reference_candidates(files: dict[str, bytes]) -> tuple[ReferenceCandidate, ...]:
    candidates: list[ReferenceCandidate] = []
    for path in sorted(files, key=os.fsencode):
        for line_number, payload in enumerate(reference_lines(files[path]), start=1):
            if reference_is_candidate(path, payload):
                candidates.append(ReferenceCandidate(path, line_number, payload))
    return tuple(candidates)


def reference_manifest(files: dict[str, bytes]) -> bytes:
    records = sorted(
        candidate.identity.serialize()
        for candidate in reference_candidates(files)
        if not reference_is_exact(candidate.payload)
    )
    return b"" if not records else b"\n".join(records) + b"\n"


def load_final_tree() -> dict[str, bytes]:
    """The INDEPENDENT reference inventory — which must not be steerable by the ambient environment.

    `git -C <root>` selects a directory, not an index: with `GIT_INDEX_FILE` pointing at another
    worktree's index this helper silently inventoried 13 FEWER files, and the "final tree matches an
    independent reference" proof stayed GREEN in both states — so the reference it compared against
    was the poisoned one (codex, PR #69 round 10, reproduced). A reference that the thing under test
    can influence is not a reference.
    """
    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"],
        check=True,
        capture_output=True,
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    )
    files: dict[str, bytes] = {}
    for encoded_path in result.stdout.split(b"\x00"):
        if not encoded_path:
            continue
        path = os.fsdecode(encoded_path)
        absolute = REPO / path
        files[path] = (
            os.fsencode(os.readlink(absolute))
            if absolute.is_symlink()
            else absolute.read_bytes()
        )
    for path in PENDING_PATHS:
        files[path] = (REPO / path).read_bytes()
    return files


@dataclass(frozen=True)
class ReferenceDestination:
    path: str
    source_line: int
    reviewer: str
    preceding_sha256: str
    following_sha256: str

    @property
    def command(self) -> bytes:
        return (
            f"/unleashed-mail:{self.reviewer}-review "
            "--ticket <T> --round <N> <plan>"
        ).encode("ascii")


# Independent copy of the frozen 78e28f2 source identities.  Tests use this
# table to locate and mutate destinations without consulting production's table.
DESTINATIONS = (
    ReferenceDestination(
        "skills/create-feature-plan/SKILL.md",
        81,
        "gemini",
        "1ce5a2d7d373ab419b116a97a14dd59994df2f36238e3ee65d6623ca5c4e150d",
        "a72073877a5870be01aa4c9ba347995d463b7721aa76e039d6923850e45248fe",
    ),
    ReferenceDestination(
        "skills/create-feature-plan/SKILL.md",
        81,
        "codex",
        "1ce5a2d7d373ab419b116a97a14dd59994df2f36238e3ee65d6623ca5c4e150d",
        "a72073877a5870be01aa4c9ba347995d463b7721aa76e039d6923850e45248fe",
    ),
    ReferenceDestination(
        "AGENT_CONTRACTS.md",
        99,
        "gemini",
        "d3fa68e8648033ceb93f2530a658d911fcfd1e3af0a1a020305261ae5e1d81d3",
        "c64d8498c05505db8e51fbc1deb220e889c8c1df7a00158879bb786c1f9aee0b",
    ),
    ReferenceDestination(
        "AGENT_CONTRACTS.md",
        100,
        "codex",
        "d3fa68e8648033ceb93f2530a658d911fcfd1e3af0a1a020305261ae5e1d81d3",
        "c64d8498c05505db8e51fbc1deb220e889c8c1df7a00158879bb786c1f9aee0b",
    ),
    ReferenceDestination(
        "skills/brainstorm/SKILL.md",
        178,
        "gemini",
        "ada3ae7255db128cf4053c2055873b6b4db382d5b1ad5f4c34dbd4df980c8e1a",
        "83bb5acac65b191a7ce344a258afab5af1f825e94099102615de1965c89c6972",
    ),
    ReferenceDestination(
        "skills/brainstorm/SKILL.md",
        178,
        "codex",
        "ada3ae7255db128cf4053c2055873b6b4db382d5b1ad5f4c34dbd4df980c8e1a",
        "83bb5acac65b191a7ce344a258afab5af1f825e94099102615de1965c89c6972",
    ),
    ReferenceDestination(
        "agents/modern-standards-planner.md",
        42,
        "gemini",
        "7c2392ea5c6ec5c93c80e7463397ee4ebb96df68d6182e4acc5148c68d351d48",
        "b692d6f1a64c321889e36fd5d03ff26676394f71d180428ec25d6f0c446fc089",
    ),
    ReferenceDestination(
        "agents/modern-standards-planner.md",
        43,
        "codex",
        "7c2392ea5c6ec5c93c80e7463397ee4ebb96df68d6182e4acc5148c68d351d48",
        "b692d6f1a64c321889e36fd5d03ff26676394f71d180428ec25d6f0c446fc089",
    ),
    ReferenceDestination(
        "skills/implement/SKILL.md",
        169,
        "gemini",
        "6e9ac7efd288872063808b04a0a8e7a400f6bf1cdbed50790cecb0617fdda778",
        "fb16dd012eec99f71ec273b8b15784d63ad30ca115bd2cece2edf73684b88c66",
    ),
    ReferenceDestination(
        "skills/implement/SKILL.md",
        169,
        "codex",
        "6e9ac7efd288872063808b04a0a8e7a400f6bf1cdbed50790cecb0617fdda778",
        "fb16dd012eec99f71ec273b8b15784d63ad30ca115bd2cece2edf73684b88c66",
    ),
    ReferenceDestination(
        "skills/implement/SKILL.md",
        180,
        "gemini",
        "5b97f8b731626d15f40fa04ffe97fd1dc248f58513a4d0c8731b53c4834827b3",
        "0800c16ca0f8760d6663dda202a48545d4f616f94a3b14ae319e1a7754a0d09a",
    ),
    ReferenceDestination(
        "skills/implement/SKILL.md",
        180,
        "codex",
        "5b97f8b731626d15f40fa04ffe97fd1dc248f58513a4d0c8731b53c4834827b3",
        "0800c16ca0f8760d6663dda202a48545d4f616f94a3b14ae319e1a7754a0d09a",
    ),
)


def destination_groups() -> dict[tuple[str, str, str], list[ReferenceDestination]]:
    groups: dict[tuple[str, str, str], list[ReferenceDestination]] = defaultdict(list)
    for destination in DESTINATIONS:
        groups[
            (
                destination.path,
                destination.preceding_sha256,
                destination.following_sha256,
            )
        ].append(destination)
    for group in groups.values():
        group.sort(
            key=lambda item: (
                item.source_line,
                0 if item.reviewer == "gemini" else 1,
            )
        )
    return groups


def destination_positions(
    testcase: unittest.TestCase, files: dict[str, bytes]
) -> dict[tuple[str, int, str], int]:
    positions: dict[tuple[str, int, str], int] = {}
    for (path, preceding, following), group in destination_groups().items():
        lines = reference_lines(files[path])
        digests = [hashlib.sha256(line).hexdigest() for line in lines]
        expected = [destination.command for destination in group]
        matches: list[int] = []
        for preceding_index, digest in enumerate(digests):
            if digest != preceding:
                continue
            for following_index in range(preceding_index + 1, len(lines)):
                if digests[following_index] != following:
                    continue
                actual = [
                    reference_strip(line)
                    for line in lines[preceding_index + 1 : following_index]
                ]
                if actual == expected:
                    matches.append(preceding_index + 1)
        testcase.assertEqual(1, len(matches), (path, group, matches))
        for offset, destination in enumerate(group):
            positions[(path, destination.source_line, destination.reviewer)] = (
                matches[0] + offset
            )
    testcase.assertEqual(12, len(positions))
    return positions


def identity_for(path: str, zero_based_line: int, payload: bytes) -> ReferenceIdentity:
    return ReferenceIdentity(
        path,
        zero_based_line + 1,
        hashlib.sha256(payload).hexdigest(),
    )


class TheManifestPathDecodeIsPinned(unittest.TestCase):
    """The canonical-encoding guard in `callers_scan.py` cannot be reached — so pin what makes it so.

    `_manifest_path` decodes with `("utf-8", "strict")` and then re-checks that re-encoding matches
    the original bytes. That second check is UNSATISFIABLE while the first is strict: strict decoding
    already rejects overlong forms, surrogates and invalid bytes, so whatever survives is canonical.
    Measured: zero counterexamples across every 1- and 2-byte sequence, and every classic
    non-canonical form is refused by the decode itself.

    A sweep flagged the re-check as an untested guard. It is untested because NO INPUT CAN REACH IT.
    Deleting it would remove insurance against someone later relaxing the decode; writing a covering
    cell for it is impossible. So this pins the PRECONDITION instead — relax the decode and the first
    cell fails, which is exactly the moment the guard stops being dead and needs a real test.
    """

    def test_the_manifest_path_decode_is_strict(self):
        source = (Path(__file__).resolve().parents[1] / "review" / "callers_scan.py").read_text(
            encoding="utf-8")
        self.assertIn('decode("utf-8", "strict")', source,
                      "the manifest-path decode is no longer strict — the canonical-encoding "
                      "re-check below it is now REACHABLE and needs its own test")

    def test_strict_decoding_makes_the_recheck_unsatisfiable(self):
        """The measurement behind the claim, kept executable rather than asserted in a comment."""
        for raw in (b"\xc0\xaf", b"\xc0\x80", b"\xed\xa0\x80", b"\xf8\x88\x80\x80\x80"):
            with self.subTest(raw=raw):
                with self.assertRaises(UnicodeDecodeError):
                    raw.decode("utf-8", "strict")
        for raw in (b"docs/planning/X.md", "caf\u00e9/plan.md".encode(), b"\xef\xbb\xbf"):
            with self.subTest(raw=raw):
                self.assertEqual(raw, raw.decode("utf-8", "strict").encode("utf-8"))


class CallersScanProof(unittest.TestCase):
    maxDiff = None

    def assert_manifest_is_exact_complement(
        self, files: dict[str, bytes], manifest: bytes
    ) -> tuple[object, ...]:
        self.assertEqual(reference_manifest(files), manifest)
        parsed = production.parse_exemption_manifest(manifest)
        self.assertEqual(
            manifest,
            b"" if not parsed else b"\n".join(item.serialize() for item in parsed) + b"\n",
        )
        expected = {
            candidate.identity.serialize()
            for candidate in reference_candidates(files)
            if not reference_is_exact(candidate.payload)
        }
        self.assertEqual(expected, {item.serialize() for item in parsed})
        return parsed

    def assert_scan_matches_reference(
        self, files: dict[str, bytes], manifest: bytes
    ) -> object:
        parsed = self.assert_manifest_is_exact_complement(files, manifest)
        report = production.scan_files(files, parsed)
        expected_candidates = reference_candidates(files)
        self.assertEqual(
            [
                (candidate.path, candidate.line_number, candidate.payload)
                for candidate in expected_candidates
            ],
            [
                (candidate.path, candidate.line_number, candidate.payload)
                for candidate in report.candidates
            ],
        )
        self.assertTrue(report.ok, (report.rejected, report.unmatched_exemptions))
        # zip(strict=) is 3.10+; macOS ships 3.9.6 and this repo targets it (COREDEV-2494).
        self.assertEqual(len(expected_candidates), len(report.candidates),
                         'candidate count differs between reference and production')
        for expected, actual in zip(expected_candidates, report.candidates):
            expected_disposition = (
                production.Disposition.ALLOW
                if reference_is_exact(expected.payload)
                else production.Disposition.EXEMPT
            )
            self.assertIs(expected_disposition, actual.disposition)
        return report

    def assert_mutation_reaches_destination_validation(
        self,
        files: dict[str, bytes],
        mutated_identity: ReferenceIdentity | None = None,
    ) -> None:
        # This is intentionally rebuilt from the mutated tree on every call.  A
        # stale manifest would let line shifts pre-empt M5.15b's named assertion.
        manifest = reference_manifest(files)
        parsed = self.assert_manifest_is_exact_complement(files, manifest)
        report = production.scan_files(files, parsed)
        self.assertTrue(report.ok, (report.rejected, report.unmatched_exemptions))
        if mutated_identity is not None:
            matches = [
                candidate
                for candidate in reference_candidates(files)
                if candidate.identity == mutated_identity
            ]
            self.assertEqual(1, len(matches))
            self.assertFalse(reference_is_exact(matches[0].payload))
            self.assertIn(mutated_identity.serialize(), {item.serialize() for item in parsed})
        self.assertTrue(production.validate_migration_destinations(files))


class M513CallersScanTests(CallersScanProof):
    def test_M5_13_final_tree_matches_independent_reference(self):
        files = load_final_tree()
        files[EXEMPTION_PATH] = (
            b"ignored /unleashed-mail:${kind}-review eval sh -c \"$cmd\" $cmd\n"
        )
        manifest = reference_manifest(files)

        self.assert_scan_matches_reference(files, manifest)
        self.assertEqual((), production.validate_migration_destinations(files))
        self.assertEqual(12, len(destination_positions(self, files)))

        # Identical residual payloads at different physical lines must yield DISTINCT manifest
        # identities. Located by search rather than pinned to one file's line numbers: this was
        # `hooks/hooks.json` lines 121/133, a matcher regex naming `security-reviewer` and
        # `prompt-review`, which the narrowed anchors deliberately stop selecting — it is not an
        # invocation of anything. The property is about the identity tuple, not about that file.
        repeated = defaultdict(list)
        for candidate in reference_candidates(files):
            if not reference_is_exact(candidate.payload):
                repeated[(candidate.path, candidate.payload)].append(candidate.line_number)
        duplicates = sorted(
            (path, payload, tuple(sorted(numbers)))
            for (path, payload), numbers in repeated.items()
            if len(numbers) > 1
        )
        self.assertTrue(
            duplicates,
            "no residual payload occurs twice, so distinct-identity would prove nothing",
        )
        duplicate_path, _duplicate_payload, duplicate_lines = duplicates[0]
        duplicate_records = {
            candidate.identity
            for candidate in reference_candidates(files)
            if candidate.path == duplicate_path
            and candidate.line_number in duplicate_lines
        }
        self.assertEqual(len(duplicate_lines), len(duplicate_records))

        implement_candidates = [
            candidate
            for candidate in reference_candidates(files)
            if candidate.path == "skills/implement/SKILL.md"
            and b"/unleashed-mail:review-synthesis" in candidate.payload
        ]
        self.assertTrue(implement_candidates)
        shifted = min(implement_candidates, key=lambda item: item.line_number)
        # The line number is DERIVED, not frozen. It was pinned at 169 and broke the moment the Phase-1
        # fence moved into a script — a frozen number here asserts the file's current layout, while the
        # property under test is that the manifest binds the identity at the payload's ACTUAL line and
        # not at the one before it. Confirm the derivation against the tree, then test that property.
        self.assertEqual(
            shifted.payload,
            reference_lines(files[shifted.path])[shifted.line_number - 1],
            "the derived line does not carry the payload it was derived from",
        )
        stale = ReferenceIdentity(
            shifted.path, shifted.line_number - 1, shifted.identity.payload_sha256
        )
        parsed = production.parse_exemption_manifest(manifest)
        serialized = {item.serialize() for item in parsed}
        self.assertIn(shifted.identity.serialize(), serialized)
        self.assertNotIn(stale.serialize(), serialized)

    def test_M5_13_real_markdown_prefixes_pass_but_trailing_tokens_reject(self):
        command = next(iter(sorted(REFERENCE_PRODUCTIONS)))
        prefixes = (
            b"",
            b"- ",
            b"+ ",
            b"* ",
            b"1. ",
            b"23) ",
            b"> ",
            b"   > ",
            b"    ",
            b"\t",
            b"   > 2.     ",
        )
        files = {
            f"docs/positive-{index}.md": prefix + command + b"\n"
            for index, prefix in enumerate(prefixes)
        }
        report = production.scan_files(files, ())
        self.assertTrue(report.ok)
        self.assertEqual(len(prefixes), len(report.candidates))
        self.assertTrue(all(reference_is_exact(item.payload) for item in reference_candidates(files)))

        malformed = {"docs/trailing.md": command + b" extra\n"}
        self.assertFalse(reference_is_exact(command + b" extra"))
        rejected = production.scan_files(malformed, ())
        self.assertEqual(1, len(rejected.rejected))

    def test_M5_13_retains_all_four_historical_bypasses_as_rejections(self):
        bypasses = (
            b'/unleashed-mail:${kind}-review --ticket <T> --round <N> <plan>',
            b'eval "/unleashed-mail:codex-review --ticket <T> --round <N> <plan>"',
            b'sh -c "$cmd" # /unleashed-mail:codex-review',
            b'$cmd # /unleashed-mail:gemini-review',
        )
        files = {
            f"docs/bypass-{index}.md": payload + b"\n"
            for index, payload in enumerate(bypasses)
        }
        candidates = reference_candidates(files)
        self.assertEqual(4, len(candidates))
        self.assertTrue(all(not reference_is_exact(item.payload) for item in candidates))
        report = production.scan_files(files, ())
        self.assertEqual(4, len(report.rejected))

    def test_M5_13_only_the_exact_metadata_path_is_excluded(self):
        payload = b"dynamic /unleashed-mail:${kind}-review invocation\n"
        files = {
            EXEMPTION_PATH: payload,
            "docs/callers-scan-exemptions.tsv": payload,
            "scripts/review/nested/callers-scan-exemptions.tsv": payload,
        }
        reference = reference_candidates(files)
        self.assertEqual(2, len(reference))
        report = production.scan_files(files, ())
        self.assertEqual(
            {item.path for item in reference},
            {item.path for item in report.rejected},
        )

    def test_M5_13_mutation_flips_the_production_nonmatch_default(self):
        source = PRODUCTION_PATH.read_text(encoding="utf-8")
        original = "DEFAULT_NON_MATCH_DISPOSITION = Disposition.REJECT"
        replacement = "DEFAULT_NON_MATCH_DISPOSITION = Disposition.ALLOW"
        self.assertEqual(1, source.count(original))
        files = {"docs/dynamic.md": b"$cmd # /unleashed-mail:codex-review\n"}
        self.assertEqual(1, len(reference_candidates(files)))
        self.assertFalse(production.scan_files(files, ()).ok)

        with tempfile.TemporaryDirectory(prefix=".callers-default-mutant-", dir=REPO) as raw:
            mutant_path = Path(raw) / "callers_scan.py"
            mutant_path.write_text(source.replace(original, replacement), encoding="utf-8")
            mutant = load_module(mutant_path, "coredev2619_default_mutant")
            try:
                mutant_report = mutant.scan_files(files, ())
                self.assertTrue(mutant_report.ok)
                self.assertIs(mutant.Disposition.ALLOW, mutant_report.candidates[0].disposition)
            finally:
                sys.modules.pop("coredev2619_default_mutant", None)

    def test_M5_13_production_selection_mutation_disagrees_with_reference(self):
        source = PRODUCTION_PATH.read_text(encoding="utf-8")
        original = "return any(anchor in payload for anchor in ANCHORS)"
        replacement = "return all(anchor in payload for anchor in ANCHORS)"
        self.assertEqual(1, source.count(original))
        files = {"docs/selection.md": b"a codex-review mention with only one anchor\n"}
        self.assertEqual(1, len(reference_candidates(files)))
        self.assertEqual(1, len(production.scan_files(files, ()).candidates))

        with tempfile.TemporaryDirectory(prefix=".callers-selection-mutant-", dir=REPO) as raw:
            mutant_path = Path(raw) / "callers_scan.py"
            mutant_path.write_text(source.replace(original, replacement), encoding="utf-8")
            mutant = load_module(mutant_path, "coredev2619_selection_mutant")
            try:
                self.assertEqual(0, len(mutant.scan_files(files, ()).candidates))
            finally:
                sys.modules.pop("coredev2619_selection_mutant", None)

    def test_M5_13_anchors_select_review_commands_but_not_unrelated_review_words(self):
        """The narrowing's own claim, line by line: only false positives left scope.

        A bare `-review` matched `security-reviewer`, `pr-review`, `code-review`, `prompt-review` and
        even `--reviewer` anywhere in prose. Each `ignored` payload below is asserted to have been
        selected by the OLD anchors, so this is a list of things that genuinely left scope — not a
        list of things that were never in it.
        """
        selected = (
            b"/unleashed-mail:gemini-review --ticket <T> --round <N> <plan>",
            b"/unleashed-mail:review-synthesis --plan <plan>",
            b"run gemini-review before implementing",
            b"unleashed-mail:codex-review --ticket <T>",
            b"$cmd # /unleashed-mail:gemini-review",
        )
        ignored = (
            b"the security-reviewer subagent",
            b"a pr-review checklist",
            b"see the code-review skill",
            b"prompt-review is the fifth reviewer",
            b'"matcher": "(unleashed-mail:)?(security-reviewer|prompt-review)"',
            b"--reviewer gemini=APPROVE:/path/to/transcript",
        )
        for payload in selected:
            self.assertTrue(production.is_candidate("docs/x.md", payload), payload)
            self.assertTrue(reference_is_candidate("docs/x.md", payload), payload)
        for payload in ignored:
            self.assertFalse(production.is_candidate("docs/x.md", payload), payload)
            self.assertFalse(reference_is_candidate("docs/x.md", payload), payload)
            self.assertTrue(
                any(anchor in payload for anchor in (b"/unleashed-mail:", b"-review")),
                b"this payload was never selected by the old anchors either: " + payload,
            )

    def test_M5_13_narrowing_is_a_strict_subset_that_keeps_every_real_invocation(self):
        """Over the real tree: nothing newly selected, and no exact production dropped."""
        files = load_final_tree()

        def positions(predicate) -> set:
            return {
                (path, number)
                for path in sorted(files)
                if path != EXEMPTION_PATH
                for number, payload in enumerate(reference_lines(files[path]), start=1)
                if predicate(path, payload)
            }

        old = positions(
            lambda _path, payload: any(
                anchor in payload for anchor in (b"/unleashed-mail:", b"-review")
            )
        )
        new = positions(production.is_candidate)
        exact = positions(lambda _path, payload: reference_is_exact(payload))

        self.assertTrue(exact, "no exact production in the tree — retention would be vacuous")
        self.assertLess(new, old, "the narrowed set must be a STRICT subset of the old one")
        self.assertLessEqual(exact, new, "a real invocation left the scanner's scope")

    def test_shipped_manifest_is_the_exact_complement_of_the_tracked_tree(self):
        """The manifest that SHIPS, not one derived inside the test.

        Every other cell here builds its manifest from `reference_manifest(...)`, so the file on disk
        was never checked by anything — and it was absent for the whole of PR #63, which made
        production `callers_scan.py --root .` exit 2 before it scanned a single line. A scanner whose
        real invocation cannot run is not a fail-closed scanner.
        """
        shipped = REPO / EXEMPTION_PATH
        self.assertTrue(shipped.is_file(), f"{EXEMPTION_PATH} is not shipped")
        files = load_final_tree()
        self.assertEqual(
            reference_manifest(files).decode("utf-8").splitlines(),
            shipped.read_bytes().decode("utf-8").splitlines(),
            "the shipped manifest is not the exact complement — regenerate it with "
            "scripts/review/generate-callers-exemptions.py, LAST, after every other edit",
        )

    def test_production_never_reaches_the_generator(self):
        """`callers_scan` must not be able to widen its own exemptions.

        The generator is a maintainer tool in the same directory; if production ever imported it, a
        new REJECT could exempt itself and the default-DENY would be decorative.
        """
        source = PRODUCTION_PATH.read_text(encoding="utf-8")
        for token in ("generate-callers-exemptions", "generate_callers_exemptions", "build_manifest"):
            self.assertNotIn(
                token, source, f"production references the generator via {token!r}"
            )

    def test_M5_13_manifest_parser_rejects_every_noncanonical_record(self):
        digest = b"a" * 64
        canonical = b"a.md\t1\t" + digest + b"\n"
        production.parse_exemption_manifest(canonical)
        production.parse_exemption_manifest(b"a\\b.md\t1\t" + digest + b"\n")
        noncanonical = (
            b"/a.md\t1\t" + digest + b"\n",
            b"./a.md\t1\t" + digest + b"\n",
            b"a/../b.md\t1\t" + digest + b"\n",
            b"a//b.md\t1\t" + digest + b"\n",
            b"a.md/\t1\t" + digest + b"\n",
            b"a.md\t1\n",
            b"a.md\t1\textra\t" + digest + b"\n",
            b"a.md\t0\t" + digest + b"\n",
            b"a.md\t+1\t" + digest + b"\n",
            b"a.md\t01\t" + digest + b"\n",
            b"a.md\t1\t" + b"A" * 64 + b"\n",
            b"a.md\t1\t" + b"a" * 63 + b"\n",
            canonical + canonical,
            b"b.md\t1\t" + digest + b"\n" + canonical,
            canonical.replace(b"\n", b"\r\n"),
            canonical[:-1],
        )
        for payload in noncanonical:
            with self.subTest(payload=payload):
                with self.assertRaises(production.ManifestError):
                    production.parse_exemption_manifest(payload)

    def test_M5_13_bound_manifest_rejects_add_remove_change_duplicate_and_line_move(self):
        baseline = {
            "docs/a.md": b"plain\nresidual codex-review mention\n",
            "docs/literal.md": (
                b"/unleashed-mail:codex-review --ticket <T> --round <N> <plan>\n"
            ),
        }
        manifest = reference_manifest(baseline)
        parsed = production.parse_exemption_manifest(manifest)
        self.assertTrue(production.scan_files(baseline, parsed).ok)

        mutations = []
        added = dict(baseline)
        added["docs/new.md"] = b"new codex-review candidate\n"
        mutations.append(added)
        removed = dict(baseline)
        removed["docs/a.md"] = b"plain\n"
        mutations.append(removed)
        changed = dict(baseline)
        changed["docs/a.md"] = b"plain\nchanged codex-review mention\n"
        mutations.append(changed)
        duplicated = dict(baseline)
        duplicated["docs/a.md"] += b"residual codex-review mention\n"
        mutations.append(duplicated)
        shifted = dict(baseline)
        shifted["docs/a.md"] = b"inserted\n" + shifted["docs/a.md"]
        mutations.append(shifted)

        for files in mutations:
            with self.subTest(files=files):
                self.assertFalse(production.scan_files(files, parsed).ok)

    def test_M5_13_blanket_exemption_is_not_a_wildcard(self):
        payload = b"dynamic codex-review carrier"
        files = {"docs/dynamic.md": payload + b"\n"}
        wildcard = production.Exemption(
            "*", 1, hashlib.sha256(payload).hexdigest()
        )
        report = production.scan_files(files, (wildcard,))
        self.assertEqual(1, len(report.rejected))
        self.assertEqual((wildcard,), report.unmatched_exemptions)

    def test_M5_13_rewritten_candidates_use_their_final_payload_identity(self):
        """A line COREDEV-2619 rewrote is in the manifest under its FINAL digest, never its old one.

        Driven from the frozen M3.1 inventory instead of a hand-built token pair. The old fixture
        rebuilt the pre-rewrite payload by substituting `--reviewer "$GEMINI_PERSIST_SPEC"` back to a
        `/tmp` spelling in `skills/review-synthesis/SKILL.md`; a bare `--reviewer` flag is not an
        invocation of a review skill and the narrowed anchors no longer select it, which would have
        left the proof asserting things about a line outside the scanner's scope. The inventory is the
        independent record of what each rewritten payload used to be, so it supplies the stale digest.
        """
        files = load_final_tree()
        inventory = json.loads(
            (REPO / "docs" / "planning" / "COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json").read_text(
                encoding="utf-8"
            )
        )
        parsed = self.assert_manifest_is_exact_complement(files, reference_manifest(files))
        serialized = {item.serialize() for item in parsed}

        checked = 0
        for site in inventory["sites"]:
            if site.get("class") != "rewrite":
                continue
            destination = site["destination"]
            # A rewrite's destination is not always in its source file: the codex capture body moved
            # into `capture-codex-review.sh`, and reading the source file at the destination's line
            # numbers would silently land on unrelated lines and skip them.
            destination_path = destination.get("path", site["path"])
            lines = reference_lines(files[destination_path])
            for offset in range(len(destination["payloads"])):
                line_number = destination["line"] + offset
                payload = lines[line_number - 1]
                if not reference_is_candidate(destination_path, payload):
                    continue
                if reference_is_exact(payload):
                    continue
                final_identity = identity_for(destination_path, line_number - 1, payload)
                stale_identity = ReferenceIdentity(
                    destination_path, line_number, site["sourceSha256"]
                )
                self.assertNotEqual(
                    final_identity.payload_sha256,
                    stale_identity.payload_sha256,
                    "the rewrite left the payload unchanged, so this line proves nothing",
                )
                self.assertIn(final_identity.serialize(), serialized)
                self.assertNotIn(stale_identity.serialize(), serialized)
                checked += 1

        self.assertGreater(
            checked, 0, "no rewritten line is in the scanner's scope — the proof would be vacuous"
        )
        self.assertTrue(production.scan_files(files, parsed).ok)

    def test_M5_13_whole_context_relocation_fails_at_every_other_line(self):
        # Host file pinned, candidate line found by SEARCH. This was `hooks/hooks.json` with a frozen
        # `source_start = 119`; the narrowed anchors stop selecting that file at all, and a proof that
        # dies when an unrelated selection rule changes was pinned to the wrong thing. What it needs is
        # any file long enough to offer >100 insertion points with a residual candidate that has a line
        # of context either side — `scripts/pty-capture.py` has exactly one, so a failed relocation can
        # only be that identity moving.
        path = "scripts/pty-capture.py"
        original = load_final_tree()[path]
        original_lines = reference_lines(original)
        residual = [
            index
            for index, line in enumerate(original_lines)
            if 0 < index < len(original_lines) - 1
            and reference_is_candidate(path, line)
            and not reference_is_exact(line)
        ]
        self.assertEqual(
            1, len(residual), "the host must carry exactly one relocatable residual candidate"
        )
        source_start = residual[0] - 1
        block = original_lines[source_start : source_start + 3]
        files = {path: original}
        parsed = production.parse_exemption_manifest(reference_manifest(files))
        old_identity = identity_for(path, source_start + 1, block[1])
        self.assertTrue(production.scan_files(files, parsed).ok)

        tested = 0
        for target_start in range(0, len(original_lines) - 2):
            remaining = original_lines[:source_start] + original_lines[source_start + 3 :]
            insertion = min(target_start, len(remaining))
            relocated = remaining[:insertion] + block + remaining[insertion:]
            new_candidate_index = insertion + 1
            if new_candidate_index + 1 == old_identity.line_number:
                continue
            mutated = {path: encode_lines(original, relocated)}
            self.assertFalse(production.scan_files(mutated, parsed).ok)
            tested += 1
        self.assertGreater(tested, 100)

    def test_M5_13_scanner_succeeds_without_the_frozen_historical_object(self):
        files = load_final_tree()
        files[EXEMPTION_PATH] = reference_manifest(files)
        # The metadata path is excluded, so adding its final bytes cannot change the complement.
        self.assertEqual(files[EXEMPTION_PATH], reference_manifest(files))

        with tempfile.TemporaryDirectory(prefix=".callers-shallow-", dir=REPO) as raw:
            root = Path(raw)
            for path, payload in files.items():
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "one-object fixture",
                ],
                check=True,
            )
            historical = subprocess.run(
                ["git", "-C", str(root), "cat-file", "-e", "23c5a5a^{commit}"],
                check=False,
                capture_output=True,
            )
            self.assertNotEqual(0, historical.returncode)
            result = subprocess.run(
                [sys.executable, str(PRODUCTION_PATH), "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)

    def test_git_selection_env_cannot_steer_the_inventory(self):
        """`GIT_INDEX_FILE` must not change what production or the reference helper inventories.

        `git -C <root>` selects a DIRECTORY, not an index. Under a sibling worktree's index the
        scanner reported a different file set — passing a manifest it should have rejected — and the
        reference helper silently lost 13 files while its own proof stayed GREEN (codex, PR #69
        rounds 9-10). Both are asserted here, because before this test the sanitisation could be
        DELETED without any focused regression failing, which is the same as not having it.
        """
        # THE POISON INDEX IS BUILT HERE, not borrowed from the machine. Depending on a sibling
        # worktree existing meant this test SKIPPED on CI — which checks out with `fetch-depth: 0`
        # and creates no worktrees — so the regression was absent exactly where it matters most
        # (codex, PR #69 round 11: "skipped 'no sibling worktree index'… OK (skipped=1)").
        import tempfile
        with tempfile.TemporaryDirectory() as decoy:
            sp_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            subprocess.run(["git", "init", "-q", decoy], check=True, env=sp_env)
            (Path(decoy) / "only-in-the-decoy.txt").write_text("decoy\n", encoding="utf-8")
            subprocess.run(["git", "-C", decoy, "add", "-A"], check=True,
                           capture_output=True, env=sp_env)
            poison_index = str(Path(decoy) / ".git" / "index")
            self.assertTrue(os.path.exists(poison_index), "failed to build a decoy index")

            control = load_final_tree()
            saved = dict(os.environ)
            try:
                os.environ["GIT_INDEX_FILE"] = poison_index
                poisoned = load_final_tree()
            finally:
                os.environ.clear()
                os.environ.update(saved)
            # EXACT inventories, not their sizes: equal-length but different file sets passed the
            # length oracle (codex demonstrated `{'a'} vs {'b'}` as "equal"). Same reason the BASIS
            # oracle had to assert the digest rather than merely that two digests matched.
            self.assertEqual(
                sorted(control), sorted(poisoned),
                "the reference inventory changed under a poisoned GIT_INDEX_FILE — it is not "
                "independent of the thing it is meant to check")
            self.assertIn("only-in-the-decoy.txt", os.listdir(decoy),
                          "FIXTURE IS VACUOUS — the decoy has no distinguishing file")
            self.assertNotIn("only-in-the-decoy.txt", control,
                             "FIXTURE IS VACUOUS — the decoy's file is already in the real tree, so "
                             "a poisoned inventory would be indistinguishable")

            script = REPO / "scripts" / "review" / "callers_scan.py"
            manifest = REPO / "scripts" / "review" / "callers-scan-exemptions.tsv"
            argv = [sys.executable, str(script), "--root", str(REPO), "--manifest", str(manifest)]
            clean = subprocess.run(argv, capture_output=True)
            dirty = subprocess.run(argv, capture_output=True,
                                   env=dict(os.environ, GIT_INDEX_FILE=poison_index))
            self.assertEqual(0, clean.returncode,
                             f"CONTROL FAILED — the shipped manifest must pass:\n"
                             f"{clean.stderr.decode('utf-8', 'replace')[:400]}")
            self.assertEqual(clean.returncode, dirty.returncode,
                             f"the production scan changed verdict under a poisoned index "
                             f"(clean={clean.returncode} poisoned={dirty.returncode})")


class M514InvocationSyntaxTests(CallersScanProof):
    def test_M5_14_review_recipes_require_inputs_and_literal_reviewer(self):
        """Each arm allocates exactly once, under its own LITERAL name.

        The two arms keep that call in different files now: codex's capture moved into
        `scripts/review/capture-codex-review.sh` so its recipe could be one granted command
        (COREDEV-2642), while gemini's is still inline. `allocates_in` names the file to read rather
        than the test assuming the skill — a version that kept assuming it would have gone looking for
        the call in the skill, not found it, and reported a missing allocation for a call that moved.
        """
        recipes = {
            "gemini": {
                "skill": "skills/gemini-review/SKILL.md",
                "allocates_in": "scripts/review/capture-gemini-review.sh",
                "wrapper_call": (
                    b'if TRANSCRIPT_MARKER="$(bash "${SCRIPT_DIR}/allocate-transcript.sh" '
                    b'"$TICKET" "$ROUND" gemini)"; then'
                ),
            },
            "codex": {
                "skill": "skills/codex-review/SKILL.md",
                "allocates_in": "scripts/review/capture-codex-review.sh",
                "wrapper_call": (
                    b'if TRANSCRIPT_MARKER="$(bash "${SCRIPT_DIR}/allocate-transcript.sh" '
                    b'"$TICKET" "$ROUND" codex)"; then'
                ),
            },
        }
        for reviewer, spec in recipes.items():
            with self.subTest(reviewer=reviewer):
                payload = (REPO / spec["skill"]).read_bytes()
                allocating = (REPO / spec["allocates_in"]).read_bytes()
                invocation = (
                    f"/unleashed-mail:{reviewer}-review "
                    "--ticket <T> --round <N> <plan>"
                ).encode("ascii")
                wrapper_call = spec["wrapper_call"]

                self.assertIn(invocation, reference_lines(payload))
                self.assertIn(wrapper_call, reference_lines(allocating))
                allocation_calls = [
                    line
                    for line in reference_lines(allocating)
                    if b"allocate-transcript.sh" in line and not line.lstrip().startswith(b"#")
                ]
                self.assertEqual([wrapper_call], allocation_calls)
                self.assertIn(reviewer.encode("ascii"), wrapper_call)
                # Assert against the FILE, not against `wrapper_call`: a check that the literal defined
                # ten lines above does not contain `"$REVIEWER"` is true no matter what ships.
                self.assertNotIn(
                    b'"$REVIEWER"',
                    allocating,
                    f"{spec['allocates_in']} derives the reviewer name at runtime",
                )
                # The skill must not ALSO allocate — one call per round, wherever it lives.
                if spec["allocates_in"] != spec["skill"]:
                    self.assertEqual(
                        [],
                        [
                            line
                            for line in reference_lines(payload)
                            if b"allocate-transcript.sh" in line
                            and not line.lstrip().startswith(b"#")
                        ],
                        f"{spec['skill']} allocates as well as its helper",
                    )
                self.assertIn(b"If either is absent, stop before allocation.", payload)

    def test_M5_14_each_destination_requires_ticket_and_round_flags_by_name(self):
        baseline = load_final_tree()
        positions = destination_positions(self, baseline)
        mutations = (
            (b"--ticket", b"--issue"),
            (b"--round", b"--iteration"),
            (b"--ticket ", b""),
            (b"--round ", b""),
        )

        for destination in DESTINATIONS:
            key = (destination.path, destination.source_line, destination.reviewer)
            for old, new in mutations:
                with self.subTest(destination=key, flag=old):
                    files = dict(baseline)
                    lines = reference_lines(files[destination.path])
                    index = positions[key]
                    self.assertEqual(1, lines[index].count(old))
                    lines[index] = lines[index].replace(old, new)
                    files[destination.path] = encode_lines(files[destination.path], lines)
                    identity = identity_for(destination.path, index, lines[index])
                    self.assert_mutation_reaches_destination_validation(files, identity)


class M515bFullInvocationShapeTests(CallersScanProof):
    def test_M5_15b_positive_maps_all_twelve_context_bound_destinations(self):
        files = load_final_tree()
        positions = destination_positions(self, files)
        self.assertEqual(12, len(positions))
        self.assert_scan_matches_reference(files, reference_manifest(files))
        self.assertEqual((), production.validate_migration_destinations(files))

    def test_M5_15b_deleting_each_destination_fails_after_manifest_rebuild(self):
        baseline = load_final_tree()
        positions = destination_positions(self, baseline)
        for destination in DESTINATIONS:
            key = (destination.path, destination.source_line, destination.reviewer)
            with self.subTest(destination=key):
                files = dict(baseline)
                lines = reference_lines(files[destination.path])
                lines.pop(positions[key])
                files[destination.path] = encode_lines(files[destination.path], lines)
                self.assert_mutation_reaches_destination_validation(files)

    def test_M5_15b_missing_operands_and_trailing_operand_cannot_be_exempted(self):
        baseline = load_final_tree()
        positions = destination_positions(self, baseline)
        mutations = (
            (b"/unleashed-mail:", b"/"),
            (b"--ticket <T> ", b""),
            (b"--ticket <T>", b"--ticket"),
            (b"--round <N> ", b""),
            (b"--round <N>", b"--round"),
            (b" <plan>", b""),
            (b"<plan>", b"<plan> trailing"),
        )
        for destination in DESTINATIONS:
            key = (destination.path, destination.source_line, destination.reviewer)
            for old, new in mutations:
                with self.subTest(destination=key, mutation=old):
                    files = dict(baseline)
                    lines = reference_lines(files[destination.path])
                    index = positions[key]
                    self.assertEqual(1, lines[index].count(old))
                    lines[index] = lines[index].replace(old, new)
                    files[destination.path] = encode_lines(files[destination.path], lines)
                    identity = identity_for(destination.path, index, lines[index])
                    self.assert_mutation_reaches_destination_validation(files, identity)

    def test_M5_15b_same_reviewer_relocation_preserves_count_but_fails_identity(self):
        baseline = load_final_tree()
        positions = destination_positions(self, baseline)
        path = "skills/implement/SKILL.md"
        first_key = (path, 169, "codex")
        second_key = (path, 180, "codex")
        first = positions[first_key]
        second = positions[second_key]
        self.assertLess(first, second)

        files = dict(baseline)
        lines = reference_lines(files[path])
        command = lines.pop(first)
        adjusted_second = second - 1
        self.assertEqual(reference_strip(command), reference_strip(lines[adjusted_second]))
        lines.insert(adjusted_second + 1, command)
        files[path] = encode_lines(files[path], lines)

        before_count = sum(
            candidate.payload == command
            for candidate in reference_candidates({path: baseline[path]})
        )
        after_count = sum(
            candidate.payload == command for candidate in reference_candidates({path: files[path]})
        )
        self.assertEqual(before_count, after_count)
        self.assert_mutation_reaches_destination_validation(files)

    def test_M5_15b_each_dual_source_join_fails_after_manifest_rebuild(self):
        baseline = load_final_tree()
        positions = destination_positions(self, baseline)
        dual_sources = (
            ("skills/create-feature-plan/SKILL.md", 81),
            ("skills/brainstorm/SKILL.md", 178),
            ("skills/implement/SKILL.md", 169),
            ("skills/implement/SKILL.md", 180),
        )
        for path, source_line in dual_sources:
            with self.subTest(path=path, source_line=source_line):
                files = dict(baseline)
                lines = reference_lines(files[path])
                gemini = positions[(path, source_line, "gemini")]
                codex = positions[(path, source_line, "codex")]
                self.assertEqual(gemini + 1, codex)
                lines[gemini] = lines[gemini] + b" " + lines[codex]
                lines.pop(codex)
                files[path] = encode_lines(files[path], lines)
                identity = identity_for(path, gemini, lines[gemini])
                self.assert_mutation_reaches_destination_validation(files, identity)




class EvasiveSelectionProofs(unittest.TestCase):
    """PR #63 review, gap 25 — candidate selection was the scanner's one default-ALLOW step.

    Everything below `is_candidate` is deny-by-default, but a line that SPELLS an invocation while
    defeating the ASCII anchor test never reached it: a zero-width space inside `gemini-review`, a
    bidi override, a BOM, a NUL, or a non-UTF-8 document all render as the command to a human while
    `b"/unleashed-mail:gemini-review" in payload` is False. Selection must therefore fail CLOSED.
    """

    def test_plain_invocation_is_still_selected(self) -> None:
        self.assertTrue(production.is_candidate("docs/x.md", b"/unleashed-mail:gemini-review --ticket X"))

    def test_every_format_character_is_normalized_not_a_curated_list(self) -> None:
        """A finite list of sequences was a finite list of bypasses (PR #63 recheck, P2).

        The old `_INVISIBLE_SEQUENCES` enumerated fourteen UTF-8 sequences, so an invocation split by
        any OTHER invisible format character rendered like the documented command while neither the raw
        nor the normalized bytes contained an anchor — the line never became a candidate and the
        default-reject policy was skipped entirely. Verified for U+2060 and U+00AD, neither of which
        was on the list. The rule is now the general category `Cf`, so a new spelling cannot be found
        by picking a character nobody enumerated.

        U+2064 is included as a character that was in NO version of the old list, so this fails against
        any reintroduced enumeration rather than only against the exact two the reviewer named.
        """
        for codepoint, name in ((0x2060, "WORD JOINER"), (0x00AD, "SOFT HYPHEN"),
                                (0x2064, "INVISIBLE PLUS"), (0x200B, "ZWSP (was listed)")):
            with self.subTest(character=name):
                # A ticket operand, NOT one of the legacy fixed-transcript output literals: COREDEV-2619's
                # inventory tracks every occurrence of those, so naming one here — even in a comment —
                # fails the quote-keep contract for a reason this cell does not test. (It did.)
                hidden = f"gemini{chr(codepoint)}-review --ticket COREDEV-1".encode("utf-8")
                self.assertNotIn(b"gemini-review", hidden, "the fixture must actually hide the anchor")
                self.assertTrue(
                    production.is_candidate("docs/x.md", hidden),
                    f"an invocation split by {name} evaded selection entirely",
                )

    def test_undecodable_bytes_survive_normalization_unchanged(self) -> None:
        """The decode/strip/encode round trip must not corrupt a non-UTF-8 document.

        `surrogateescape` is what makes that true; without it the payload the caller compares against
        would differ from the file's bytes for reasons unrelated to invisibles.
        """
        payload = b"\xff\xfe gemini-review --ticket X \x80"
        self.assertEqual(payload, production.strip_invisible(payload))
        self.assertTrue(production.is_candidate("docs/x.md", payload))

    def test_ordinary_prose_is_still_not_selected(self) -> None:
        """The deletion test: the guard must be conditional, not select everything."""
        self.assertFalse(production.is_candidate("docs/x.md", b"This line mentions nothing relevant."))

    def test_an_invocation_hidden_by_an_invisible_char_is_selected(self) -> None:
        """Normalisation must REVEAL an anchor that the raw byte test missed."""
        # A ZWSP must sit INSIDE **every** anchor. `is_candidate` tests them with `any()`,
        # and ANCHORS are two coarse substrings (`/unleashed-mail:` and `-review`), so
        # breaking only one still matches the other. That is a real robustness property of
        # the coarse anchors — evasion has to defeat ALL of them. Two earlier versions of
        # this fixture proved nothing, and the validity assertion below caught both.
        hidden = "/unleashed-mail\u200b:gemini-rev\u200biew --ticket X".encode("utf-8")
        self.assertFalse(
            any(anchor in hidden for anchor in production.ANCHORS),
            "fixture invalid: the raw anchors must NOT match, or this proves nothing",
        )
        self.assertTrue(production.is_candidate("docs/x.md", hidden))

    def test_prose_merely_containing_an_invisible_char_is_not_selected(self) -> None:
        """The discrimination that matters — and the reason the first fix was wrong.

        Selecting every line that CONTAINS such a byte swept in the plan documents that discuss
        CRLF/BOM handling and carry those bytes as examples: hundreds of prose lines became
        rejects. Only a line where stripping them REVEALS an invocation may be selected.
        """
        for label, payload in {
            "bom in prose": "prose \ufeff more prose".encode("utf-8"),
            "nul in prose": b"prose \x00 more prose",
            "invalid utf-8": b"prose \xff\xfe more prose",
            "zwsp in prose": "prose \u200b more prose".encode("utf-8"),
        }.items():
            with self.subTest(label=label):
                self.assertFalse(
                    production.is_candidate("docs/x.md", payload),
                    label + " does not hide an invocation and must not be selected",
                )

    def test_the_exemption_manifest_itself_is_still_excluded(self) -> None:
        """Failing closed must not start scanning the exemption file and recursing on itself."""
        self.assertFalse(
            production.is_candidate(production.EXEMPTION_PATH, b"/unleashed-mail:gemini-review")
        )




class DefaultIgnorableIsTheWholeInvisibleClass(unittest.TestCase):
    """`Cf` alone left four other general categories able to split an anchor (PR #63 recheck, P2).

    The property that means "renders as nothing" is `Default_Ignorable_Code_Point`, and it reaches into
    `Mn`, `Lo` and unassigned `Cn` blocks that `Cf` does not contain. U+3164 HANGUL FILLER is the
    classic case: category `Lo`, zero width, and it was passed through untouched.

    The table in the module is the RESIDUE — the DI code points not already covered by `Cf` or the
    variation selectors. This cell recomputes that difference from the DI ranges instead of restating
    the table, so a table that drifts from the property fails here rather than silently narrowing.
    """

    #: DerivedCoreProperties.txt, `Default_Ignorable_Code_Point`.
    RANGES = (
        (0x00AD, 0x00AD), (0x034F, 0x034F), (0x061C, 0x061C), (0x115F, 0x1160),
        (0x17B4, 0x17B5), (0x180B, 0x180F), (0x200B, 0x200F), (0x202A, 0x202E),
        (0x2060, 0x206F), (0x3164, 0x3164), (0xFE00, 0xFE0F), (0xFEFF, 0xFEFF),
        (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8), (0x1BCA0, 0x1BCA3), (0x1D173, 0x1D17A),
        (0xE0000, 0xE0FFF),
    )

    def test_every_default_ignorable_code_point_is_treated_as_invisible(self):
        for low, high in self.RANGES:
            for code_point in range(low, high + 1):
                with self.subTest(code_point=hex(code_point)):
                    self.assertTrue(production._is_invisible(chr(code_point)))

    def test_an_anchor_split_by_a_HANGUL_FILLER_is_still_found(self):
        """The end-to-end consequence, in the category `Cf` does not reach.

        `Lo` and zero width: an invocation spelled with one between two characters of the anchor
        renders identically to the plain one and was not selected as a candidate.
        """
        anchor = sorted(production.ANCHORS)[0]
        split = anchor[:1] + "ㅤ".encode("utf-8") + anchor[1:]
        self.assertNotIn(anchor, split, "the fixture did not actually split the anchor")
        self.assertIn(anchor, production.strip_invisible(split))
        self.assertTrue(production.is_candidate("scripts/probe.sh", split),
                        "an invocation hidden behind a HANGUL FILLER was not selected")

    def test_ordinary_text_is_untouched(self):
        """Discrimination: the normalisation must remove the invisible class, not mangle content.

        A combining ACUTE ACCENT is `Mn` like the Khmer inherent vowels, and it is NOT default-ignorable
        — stripping by category would have taken it too.
        """
        payload = "café́ — ordinary prose".encode("utf-8")
        self.assertEqual(payload, production.strip_invisible(payload))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
