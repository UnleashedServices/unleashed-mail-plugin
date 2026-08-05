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
# Selection anchors.  A bare `-review` was over-selecting badly: it matches `security-reviewer`,
# `pr-review` and `code-review` anywhere in prose, so the tree yielded 1409 candidates against 14 real
# invocations, and the residual manifest that must be reviewed by hand came to ~1395 rows (PR #63
# review, gap on `callers_scan.py:269`).  Naming the two review commands instead drops the unrelated
# review words while keeping every spelling of a real one.  Measured over the tracked tree:
#
#     /unleashed-mail: + -review                    1409 candidates, 14 exact productions
#     /unleashed-mail: only                          103 candidates, 14 exact productions
#     /unleashed-mail: + /gemini-review /codex-review  195 candidates, 14 exact productions
#     /unleashed-mail: + gemini-review codex-review    268 candidates, 14 exact productions   <- this
#
# The slash-prefixed variant is smaller but narrows further than the defect warrants: it stops
# selecting `unleashed-mail:gemini-review …` and a bare `gemini-review --ticket …`, both of which are
# documented-invocation spellings this scanner exists to reject.  The set below is a strict SUBSET of
# the old one, so nothing that was covered becomes uncovered except the false positives, and all four
# historical bypasses still select on `/unleashed-mail:`.
ANCHORS = (b"/unleashed-mail:", b"gemini-review", b"codex-review")
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
        169,
        "gemini",
        "6e9ac7efd288872063808b04a0a8e7a400f6bf1cdbed50790cecb0617fdda778",
        "fb16dd012eec99f71ec273b8b15784d63ad30ca115bd2cece2edf73684b88c66",
    ),
    MigrationDestination(
        "skills/implement/SKILL.md",
        169,
        "codex",
        "6e9ac7efd288872063808b04a0a8e7a400f6bf1cdbed50790cecb0617fdda778",
        "fb16dd012eec99f71ec273b8b15784d63ad30ca115bd2cece2edf73684b88c66",
    ),
    MigrationDestination(
        "skills/implement/SKILL.md",
        180,
        "gemini",
        "5b97f8b731626d15f40fa04ffe97fd1dc248f58513a4d0c8731b53c4834827b3",
        "0800c16ca0f8760d6663dda202a48545d4f616f94a3b14ae319e1a7754a0d09a",
    ),
    MigrationDestination(
        "skills/implement/SKILL.md",
        180,
        "codex",
        "5b97f8b731626d15f40fa04ffe97fd1dc248f58513a4d0c8731b53c4834827b3",
        "0800c16ca0f8760d6663dda202a48545d4f616f94a3b14ae319e1a7754a0d09a",
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


# Invisible and direction-control sequences that can sit INSIDE a spelled invocation while
# defeating the ASCII anchor test below: `/unleashed-mail:gemini<ZWSP>-review` renders as the
# command to a human but `b"...gemini-review" in payload` is False, so the line was never a
# candidate and the scanner's default-DENY never applied to it (PR #63 review, gap 25).
_INVISIBLE_SEQUENCES = (
    b"\x00",              # NUL
    b"\xe2\x80\x8b",      # U+200B ZERO WIDTH SPACE
    b"\xe2\x80\x8c",      # U+200C ZERO WIDTH NON-JOINER
    b"\xe2\x80\x8d",      # U+200D ZERO WIDTH JOINER
    b"\xef\xbb\xbf",      # U+FEFF ZERO WIDTH NO-BREAK SPACE / BOM
    b"\xe2\x80\xaa",      # U+202A..U+202E embeddings and overrides
    b"\xe2\x80\xab",
    b"\xe2\x80\xac",
    b"\xe2\x80\xad",
    b"\xe2\x80\xae",
    b"\xe2\x81\xa6",      # U+2066..U+2069 isolates
    b"\xe2\x81\xa7",
    b"\xe2\x81\xa8",
    b"\xe2\x81\xa9",
)


def strip_invisible(payload: bytes) -> bytes:
    """Remove invisible/bidi sequences so an anchor cannot be split by one."""
    for sequence in _INVISIBLE_SEQUENCES:
        payload = payload.replace(sequence, b"")
    return payload


def is_candidate(path: str, payload: bytes) -> bool:
    if path == EXEMPTION_PATH:
        return False
    # Re-test ONLY when normalisation actually CHANGED the line. Selecting every line that merely
    # CONTAINS an invisible byte would sweep in the plan documents that discuss CRLF/BOM handling
    # and carry those bytes as examples -- an earlier version of this fix did exactly that and
    # turned hundreds of prose lines into rejects. What matters is whether removing them REVEALS an
    # invocation that was hidden; nothing else about selection changes.
    #
    # Invalid UTF-8 needs no arm: the anchors are ASCII byte sequences, so surrounding undecodable
    # bytes cannot conceal one -- `anchor in payload` still matches through them.
    normalized = strip_invisible(payload)
    if normalized != payload and any(anchor in normalized for anchor in ANCHORS):
        return True
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
