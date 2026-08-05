#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-CALLERS proof cells M5.13/M5.14/M5.15b."""

from __future__ import annotations

import hashlib
import importlib.util
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
REFERENCE_ANCHORS = (b"/unleashed-mail:", b"-review")
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
    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"],
        check=True,
        capture_output=True,
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

        hooks_lines = reference_lines(files["hooks/hooks.json"])
        self.assertEqual(hooks_lines[120], hooks_lines[132])
        self.assertEqual(hooks_lines[119], hooks_lines[131])
        self.assertEqual(hooks_lines[121], hooks_lines[133])
        hook_records = {
            candidate.identity
            for candidate in reference_candidates(files)
            if candidate.path == "hooks/hooks.json"
            and candidate.line_number in (121, 133)
        }
        self.assertEqual(2, len(hook_records))

        implement_candidates = [
            candidate
            for candidate in reference_candidates(files)
            if candidate.path == "skills/implement/SKILL.md"
            and b"/unleashed-mail:review-synthesis" in candidate.payload
        ]
        self.assertTrue(implement_candidates)
        shifted = min(implement_candidates, key=lambda item: item.line_number)
        self.assertEqual(169, shifted.line_number)
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
        payload = b"dynamic ${kind}-review invocation\n"
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
        files = {"docs/selection.md": b"a -review mention with only one anchor\n"}
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
            "docs/a.md": b"plain\nresidual -review mention\n",
            "docs/literal.md": (
                b"/unleashed-mail:codex-review --ticket <T> --round <N> <plan>\n"
            ),
        }
        manifest = reference_manifest(baseline)
        parsed = production.parse_exemption_manifest(manifest)
        self.assertTrue(production.scan_files(baseline, parsed).ok)

        mutations = []
        added = dict(baseline)
        added["docs/new.md"] = b"new -review candidate\n"
        mutations.append(added)
        removed = dict(baseline)
        removed["docs/a.md"] = b"plain\n"
        mutations.append(removed)
        changed = dict(baseline)
        changed["docs/a.md"] = b"plain\nchanged -review mention\n"
        mutations.append(changed)
        duplicated = dict(baseline)
        duplicated["docs/a.md"] += b"residual -review mention\n"
        mutations.append(duplicated)
        shifted = dict(baseline)
        shifted["docs/a.md"] = b"inserted\n" + shifted["docs/a.md"]
        mutations.append(shifted)

        for files in mutations:
            with self.subTest(files=files):
                self.assertFalse(production.scan_files(files, parsed).ok)

    def test_M5_13_blanket_exemption_is_not_a_wildcard(self):
        payload = b"dynamic -review carrier"
        files = {"docs/dynamic.md": payload + b"\n"}
        wildcard = production.Exemption(
            "*", 1, hashlib.sha256(payload).hexdigest()
        )
        report = production.scan_files(files, (wildcard,))
        self.assertEqual(1, len(report.rejected))
        self.assertEqual((wildcard,), report.unmatched_exemptions)

    def test_M5_13_rewritten_synthesis_candidate_uses_its_final_payload_identity(self):
        files = load_final_tree()
        path = "skills/review-synthesis/SKILL.md"
        lines = reference_lines(files[path])
        # Constructed, not spelled: a bare transcript-path literal here would be a NEW
        # unclassified site and M3.1 would (correctly) reject it as inventory drift.
        source_token = b"--reviewer gemini=<GEMINI_STATUS>:" + b"/tmp/" + b"agy-out.txt"
        destination_token = b'--reviewer "$GEMINI_PERSIST_SPEC"'
        indexes = [index for index, line in enumerate(lines) if destination_token in line]
        self.assertEqual(1, len(indexes))
        index = indexes[0]
        final_identity = identity_for(path, index, lines[index])
        stale_payload = lines[index].replace(destination_token, source_token)
        stale_identity = identity_for(path, index, stale_payload)

        parsed = self.assert_manifest_is_exact_complement(files, reference_manifest(files))
        serialized = {item.serialize() for item in parsed}
        self.assertIn(final_identity.serialize(), serialized)
        self.assertNotIn(stale_identity.serialize(), serialized)
        self.assertTrue(production.scan_files(files, parsed).ok)

    def test_M5_13_whole_context_relocation_fails_at_every_other_line(self):
        original = load_final_tree()["hooks/hooks.json"]
        original_lines = reference_lines(original)
        source_start = 119  # final physical lines 120-122, candidate at 121
        block = original_lines[source_start : source_start + 3]
        files = {"hooks/hooks.json": original}
        parsed = production.parse_exemption_manifest(reference_manifest(files))
        old_identity = identity_for("hooks/hooks.json", source_start + 1, block[1])
        self.assertTrue(production.scan_files(files, parsed).ok)

        tested = 0
        for target_start in range(0, len(original_lines) - 2):
            remaining = original_lines[:source_start] + original_lines[source_start + 3 :]
            insertion = min(target_start, len(remaining))
            relocated = remaining[:insertion] + block + remaining[insertion:]
            new_candidate_index = insertion + 1
            if new_candidate_index + 1 == old_identity.line_number:
                continue
            mutated = {"hooks/hooks.json": encode_lines(original, relocated)}
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


class M514InvocationSyntaxTests(CallersScanProof):
    def test_M5_14_review_recipes_require_inputs_and_literal_reviewer(self):
        recipes = {
            "gemini": "skills/gemini-review/SKILL.md",
            "codex": "skills/codex-review/SKILL.md",
        }
        for reviewer, path in recipes.items():
            with self.subTest(reviewer=reviewer):
                payload = (REPO / path).read_bytes()
                lines = reference_lines(payload)
                invocation = (
                    f"/unleashed-mail:{reviewer}-review "
                    "--ticket <T> --round <N> <plan>"
                ).encode("ascii")
                wrapper_call = (
                    b'bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/allocate-transcript.sh" '
                    + b'"$TICKET" "$ROUND" '
                    + reviewer.encode("ascii")
                )
                self.assertIn(invocation, lines)
                self.assertIn(wrapper_call, lines)
                allocation_calls = [
                    line for line in lines if b"allocate-transcript.sh" in line
                ]
                self.assertEqual([wrapper_call], allocation_calls)
                self.assertNotIn(b'"$REVIEWER"', wrapper_call)
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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
