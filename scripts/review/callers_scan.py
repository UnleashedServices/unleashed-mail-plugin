#!/usr/bin/env python3
"""Fail-closed scanner for documented plan-review skill invocations.

The residual exemption manifest is intentionally maintained outside this module.  It is
bound to final physical line numbers and payload digests, so production never derives or
widens it automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping, Sequence


EXEMPTION_PATH = "scripts/review/callers-scan-exemptions.tsv"
ANCHORS = (b"/unleashed-mail:", b"-review")
MARKDOWN_PREFIX = re.compile(
    br"\A(?:(?:[ \t]{0,3}(?:[-+*]|[0-9]+[.)])[ \t]+)|"
    br"(?:[ \t]{0,3}>[ \t]?)|(?: {4}|\t))*"
)
PRODUCTIONS = frozenset(
    {
        b"/unleashed-mail:gemini-review --ticket <T> --round <N> <plan>",
        b"/unleashed-mail:codex-review --ticket <T> --round <N> <plan>",
    }
)


class Disposition(Enum):
    ALLOW = "allow"
    EXEMPT = "exempt"
    REJECT = "reject"


# M5.13 mutates this decision itself.  Keep the non-match default explicit: adding
# named bypasses instead would turn the allowlist back into an incomplete blacklist.
DEFAULT_NON_MATCH_DISPOSITION = Disposition.REJECT


class ManifestError(ValueError):
    """The exemption manifest is not in its one canonical form."""


@dataclass(frozen=True, order=True)
class Exemption:
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
class Candidate:
    path: str
    line_number: int
    payload: bytes
    disposition: Disposition

    @property
    def identity(self) -> Exemption:
        return Exemption(
            self.path,
            self.line_number,
            hashlib.sha256(self.payload).hexdigest(),
        )


@dataclass(frozen=True)
class ScanReport:
    candidates: tuple[Candidate, ...]
    unmatched_exemptions: tuple[Exemption, ...]

    @property
    def rejected(self) -> tuple[Candidate, ...]:
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.disposition is Disposition.REJECT
        )

    @property
    def ok(self) -> bool:
        return not self.rejected and not self.unmatched_exemptions


@dataclass(frozen=True)
class MigrationDestination:
    path: str
    frozen_source_line: int
    reviewer: str
    preceding_sha256: str
    following_sha256: str

    @property
    def command(self) -> bytes:
        return (
            f"/unleashed-mail:{self.reviewer}-review "
            "--ticket <T> --round <N> <plan>"
        ).encode("ascii")


# Frozen at 78e28f26cb56572b22fe1635552dd10fa95bdb48.  Adjacent source
# lines share the nearest unchanged anchors; reviewer order disambiguates them.
MIGRATION_DESTINATIONS = (
    MigrationDestination(
        "skills/create-feature-plan/SKILL.md",
        81,
        "gemini",
        "1ce5a2d7d373ab419b116a97a14dd59994df2f36238e3ee65d6623ca5c4e150d",
        "a72073877a5870be01aa4c9ba347995d463b7721aa76e039d6923850e45248fe",
    ),
    MigrationDestination(
        "skills/create-feature-plan/SKILL.md",
        81,
        "codex",
        "1ce5a2d7d373ab419b116a97a14dd59994df2f36238e3ee65d6623ca5c4e150d",
        "a72073877a5870be01aa4c9ba347995d463b7721aa76e039d6923850e45248fe",
    ),
    MigrationDestination(
        "AGENT_CONTRACTS.md",
        99,
        "gemini",
        "d3fa68e8648033ceb93f2530a658d911fcfd1e3af0a1a020305261ae5e1d81d3",
        "c64d8498c05505db8e51fbc1deb220e889c8c1df7a00158879bb786c1f9aee0b",
    ),
    MigrationDestination(
        "AGENT_CONTRACTS.md",
        100,
        "codex",
        "d3fa68e8648033ceb93f2530a658d911fcfd1e3af0a1a020305261ae5e1d81d3",
        "c64d8498c05505db8e51fbc1deb220e889c8c1df7a00158879bb786c1f9aee0b",
    ),
    MigrationDestination(
        "skills/brainstorm/SKILL.md",
        178,
        "gemini",
        "ada3ae7255db128cf4053c2055873b6b4db382d5b1ad5f4c34dbd4df980c8e1a",
        "83bb5acac65b191a7ce344a258afab5af1f825e94099102615de1965c89c6972",
    ),
    MigrationDestination(
        "skills/brainstorm/SKILL.md",
        178,
        "codex",
        "ada3ae7255db128cf4053c2055873b6b4db382d5b1ad5f4c34dbd4df980c8e1a",
        "83bb5acac65b191a7ce344a258afab5af1f825e94099102615de1965c89c6972",
    ),
    MigrationDestination(
        "agents/modern-standards-planner.md",
        42,
        "gemini",
        "7c2392ea5c6ec5c93c80e7463397ee4ebb96df68d6182e4acc5148c68d351d48",
        "b692d6f1a64c321889e36fd5d03ff26676394f71d180428ec25d6f0c446fc089",
    ),
    MigrationDestination(
        "agents/modern-standards-planner.md",
        43,
        "codex",
        "7c2392ea5c6ec5c93c80e7463397ee4ebb96df68d6182e4acc5148c68d351d48",
        "b692d6f1a64c321889e36fd5d03ff26676394f71d180428ec25d6f0c446fc089",
    ),
    MigrationDestination(
        "skills/implement/SKILL.md",
        161,
        "gemini",
        "c8107787ff2a6e3a566b3678d2ecb3f71bd8e0b1803eadd43e4d9a1e21e2b84c",
        "8f2c267ed2a52efdb9058e8d2df61d5f9be1cba8f5dd272e67ca5286f715a2e8",
    ),
    MigrationDestination(
        "skills/implement/SKILL.md",
        161,
        "codex",
        "c8107787ff2a6e3a566b3678d2ecb3f71bd8e0b1803eadd43e4d9a1e21e2b84c",
        "8f2c267ed2a52efdb9058e8d2df61d5f9be1cba8f5dd272e67ca5286f715a2e8",
    ),
    MigrationDestination(
        "skills/implement/SKILL.md",
        172,
        "gemini",
        "64a5b5cc04ca3e38bf91dafec7017d0ae05e9418da09c89aedffd1350a1e308b",
        "d3e61adc1a2e7bd4942d0915c2b351b65021fa681370b22129866fea543a865f",
    ),
    MigrationDestination(
        "skills/implement/SKILL.md",
        172,
        "codex",
        "64a5b5cc04ca3e38bf91dafec7017d0ae05e9418da09c89aedffd1350a1e308b",
        "d3e61adc1a2e7bd4942d0915c2b351b65021fa681370b22129866fea543a865f",
    ),
)


def physical_lines(payload: bytes) -> list[bytes]:
    """Split LF-delimited physical lines, retaining every other payload byte."""

    if not payload:
        return []
    lines = payload.split(b"\n")
    if payload.endswith(b"\n"):
        lines.pop()
    return lines


def strip_markdown_prefix(payload: bytes) -> bytes:
    match = MARKDOWN_PREFIX.match(payload)
    assert match is not None
    return payload[match.end() :]


def is_candidate(path: str, payload: bytes) -> bool:
    if path == EXEMPTION_PATH:
        return False
    return any(anchor in payload for anchor in ANCHORS)


def is_exact_production(payload: bytes) -> bool:
    return strip_markdown_prefix(payload) in PRODUCTIONS


def _validate_manifest_path(path_bytes: bytes) -> str:
    if not path_bytes or path_bytes.startswith(b"/") or path_bytes.endswith(b"/"):
        raise ManifestError("manifest path must be a normalized repo-relative path")
    if b"\x00" in path_bytes:
        raise ManifestError("manifest path contains a forbidden byte")
    components = path_bytes.split(b"/")
    if any(component in (b"", b".", b"..") for component in components):
        raise ManifestError("manifest path is not normalized")
    try:
        path = path_bytes.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise ManifestError("manifest path is not UTF-8") from error
    if path.encode("utf-8") != path_bytes:
        raise ManifestError("manifest path is not canonically encoded")
    return path


def parse_exemption_manifest(payload: bytes) -> tuple[Exemption, ...]:
    if b"\r" in payload:
        raise ManifestError("manifest must use LF line endings")
    if payload and not payload.endswith(b"\n"):
        raise ManifestError("manifest must terminate every record with LF")

    raw_records = payload[:-1].split(b"\n") if payload else []
    exemptions: list[Exemption] = []
    previous: bytes | None = None
    for raw_record in raw_records:
        if raw_record.count(b"\t") != 2:
            raise ManifestError("manifest records require exactly three TSV fields")
        path_bytes, line_bytes, digest_bytes = raw_record.split(b"\t")
        path = _validate_manifest_path(path_bytes)
        if re.fullmatch(br"[1-9][0-9]*", line_bytes) is None:
            raise ManifestError("manifest line number is not canonical")
        if re.fullmatch(br"[0-9a-f]{64}", digest_bytes) is None:
            raise ManifestError("manifest digest is not lowercase SHA-256")
        exemption = Exemption(path, int(line_bytes), digest_bytes.decode("ascii"))
        if exemption.serialize() != raw_record:
            raise ManifestError("manifest record is not canonical")
        if previous is not None and raw_record <= previous:
            raise ManifestError("manifest records must be unique and byte-sorted")
        previous = raw_record
        exemptions.append(exemption)
    return tuple(exemptions)


def scan_files(
    files: Mapping[str, bytes], exemptions: Sequence[Exemption]
) -> ScanReport:
    exemption_set = set(exemptions)
    consumed: set[Exemption] = set()
    candidates: list[Candidate] = []

    for path in sorted(files, key=os.fsencode):
        for line_number, payload in enumerate(physical_lines(files[path]), start=1):
            if not is_candidate(path, payload):
                continue
            identity = Exemption(path, line_number, hashlib.sha256(payload).hexdigest())
            if is_exact_production(payload):
                disposition = Disposition.ALLOW
            elif identity in exemption_set:
                disposition = Disposition.EXEMPT
                consumed.add(identity)
            else:
                disposition = DEFAULT_NON_MATCH_DISPOSITION
            candidates.append(Candidate(path, line_number, payload, disposition))

    unmatched = tuple(sorted(exemption_set - consumed))
    return ScanReport(tuple(candidates), unmatched)


def _migration_groups() -> dict[tuple[str, str, str], list[MigrationDestination]]:
    groups: dict[tuple[str, str, str], list[MigrationDestination]] = defaultdict(list)
    for destination in MIGRATION_DESTINATIONS:
        key = (
            destination.path,
            destination.preceding_sha256,
            destination.following_sha256,
        )
        groups[key].append(destination)
    for destinations in groups.values():
        destinations.sort(
            key=lambda item: (
                item.frozen_source_line,
                0 if item.reviewer == "gemini" else 1,
            )
        )
    return groups


def validate_migration_destinations(files: Mapping[str, bytes]) -> tuple[str, ...]:
    errors: list[str] = []
    for (path, preceding, following), destinations in _migration_groups().items():
        if path not in files:
            errors.append(f"missing migration file: {path}")
            continue
        lines = physical_lines(files[path])
        digests = [hashlib.sha256(line).hexdigest() for line in lines]
        preceding_indexes = [
            index for index, digest in enumerate(digests) if digest == preceding
        ]
        following_indexes = [
            index for index, digest in enumerate(digests) if digest == following
        ]
        expected = [destination.command for destination in destinations]
        matches: list[tuple[int, int]] = []
        for preceding_index in preceding_indexes:
            for following_index in following_indexes:
                if following_index <= preceding_index:
                    continue
                actual = [
                    strip_markdown_prefix(line)
                    for line in lines[preceding_index + 1 : following_index]
                ]
                if actual == expected:
                    matches.append((preceding_index, following_index))
        if len(matches) != 1:
            source_lines = ",".join(
                str(destination.frozen_source_line) for destination in destinations
            )
            errors.append(
                f"{path}: frozen source region {source_lines} has "
                f"{len(matches)} conforming destinations (expected 1)"
            )
    return tuple(errors)


def read_tracked_files(root: Path) -> dict[str, bytes]:
    result = subprocess.run(
        ["git", "-C", os.fspath(root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        diagnostic = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git ls-files failed: {diagnostic}")

    files: dict[str, bytes] = {}
    for encoded_path in result.stdout.split(b"\x00"):
        if not encoded_path:
            continue
        path = os.fsdecode(encoded_path)
        absolute = root / path
        if absolute.is_symlink():
            files[path] = os.fsencode(os.readlink(absolute))
        else:
            try:
                files[path] = absolute.read_bytes()
            except OSError as error:
                raise RuntimeError(f"cannot read tracked path {path}: {error}") from error
    return files


def _print_report(report: ScanReport, migration_errors: Iterable[str]) -> bool:
    ok = report.ok
    for candidate in report.rejected:
        print(
            f"REJECT {candidate.path}:{candidate.line_number}: "
            f"{candidate.payload.decode('utf-8', 'backslashreplace')}",
            file=sys.stderr,
        )
    for exemption in report.unmatched_exemptions:
        print(
            f"UNMATCHED {exemption.path}:{exemption.line_number}: "
            f"{exemption.payload_sha256}",
            file=sys.stderr,
        )
    for error in migration_errors:
        ok = False
        print(f"MIGRATION {error}", file=sys.stderr)
    return ok


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path)
    arguments = parser.parse_args(argv)

    root = arguments.root.resolve()
    manifest = arguments.manifest or root / EXEMPTION_PATH
    try:
        manifest_payload = manifest.read_bytes()
        exemptions = parse_exemption_manifest(manifest_payload)
        files = read_tracked_files(root)
    except (OSError, ManifestError, RuntimeError) as error:
        print(f"callers-scan: {error}", file=sys.stderr)
        return 2

    report = scan_files(files, exemptions)
    migration_errors = validate_migration_destinations(files)
    return 0 if _print_report(report, migration_errors) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
