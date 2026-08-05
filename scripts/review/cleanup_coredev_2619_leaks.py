#!/usr/bin/env python3
"""Remove only the closed COREDEV-2619 transcript-leak manifest.

This is an intentionally one-shot release tool.  It never discovers deletion
targets and it never derives a state root from HOME.  The maintainer must first
verify the closed manifest against the real filesystem, then pass that exact
state root explicitly with ``--state-root ... --apply``.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


REGULAR_FILE = "regular file"


@dataclass(frozen=True)
class ManifestEntry:
    relative_path: str
    expected_type: str


@dataclass(frozen=True)
class FileDeletionReport:
    attempted_relative_paths: Tuple[str, ...]
    root_identity: Tuple[int, int]


@dataclass(frozen=True)
class CleanupReport:
    attempted_relative_paths: Tuple[str, ...]
    removed_directories: Tuple[str, ...]
    root_identity: Tuple[int, int]


class CleanupError(RuntimeError):
    """The closed cleanup contract could not be completed safely."""


# Closed output of the two identified runaway review runs (rounds 25 and 36).
# Keep the expected object type beside every literal path: this is deliberately
# not a filename family, prefix, suffix, regular expression, or discovered set.
LEAK_MANIFEST = (
    ManifestEntry("38483bff6fb293c5b0f90254466c52bc06a785e7/COREDEV-9999r1-codex-429f9c747d18a3f8bbe32656b947d884.txt", REGULAR_FILE),
    ManifestEntry("38483bff6fb293c5b0f90254466c52bc06a785e7/COREDEV-9999r1-codex-429f9c747d18a3f8bbe32656b947d884.txt.captureid", REGULAR_FILE),
    ManifestEntry("38483bff6fb293c5b0f90254466c52bc06a785e7/COREDEV-9999r1-codex-429f9c747d18a3f8bbe32656b947d884.txt.launch", REGULAR_FILE),
    ManifestEntry("38483bff6fb293c5b0f90254466c52bc06a785e7/COREDEV-9999r1-gemini-407dab25213096ed784af0b230e1f845.txt", REGULAR_FILE),
    ManifestEntry("38483bff6fb293c5b0f90254466c52bc06a785e7/COREDEV-9999r1-gemini-407dab25213096ed784af0b230e1f845.txt.captureid", REGULAR_FILE),
    ManifestEntry("38483bff6fb293c5b0f90254466c52bc06a785e7/COREDEV-9999r1-gemini-407dab25213096ed784af0b230e1f845.txt.launch", REGULAR_FILE),
    ManifestEntry("4c5e3e4c560819f8de798b1a20f7959b037b0de888dc89e561ad3840a3f68076/COREDEV-2619r1-gemini-25ec588d03bc3789.txt", REGULAR_FILE),
    ManifestEntry("4c5e3e4c560819f8de798b1a20f7959b037b0de888dc89e561ad3840a3f68076/COREDEV-2619r1-gemini-25ec588d03bc3789.txt.launch", REGULAR_FILE),
    ManifestEntry("738b2f6174a7aed615fa597d3847744862d4d5f8/COREDEV-9999r1-codex-0b4ee67fd1233a726932d81748fec7e3.txt", REGULAR_FILE),
    ManifestEntry("738b2f6174a7aed615fa597d3847744862d4d5f8/COREDEV-9999r1-codex-0b4ee67fd1233a726932d81748fec7e3.txt.captureid", REGULAR_FILE),
    ManifestEntry("738b2f6174a7aed615fa597d3847744862d4d5f8/COREDEV-9999r1-codex-0b4ee67fd1233a726932d81748fec7e3.txt.launch", REGULAR_FILE),
    ManifestEntry("738b2f6174a7aed615fa597d3847744862d4d5f8/COREDEV-9999r1-gemini-55fa0328fa731a38b618702fd1180f6b.txt", REGULAR_FILE),
    ManifestEntry("738b2f6174a7aed615fa597d3847744862d4d5f8/COREDEV-9999r1-gemini-55fa0328fa731a38b618702fd1180f6b.txt.captureid", REGULAR_FILE),
    ManifestEntry("738b2f6174a7aed615fa597d3847744862d4d5f8/COREDEV-9999r1-gemini-55fa0328fa731a38b618702fd1180f6b.txt.launch", REGULAR_FILE),
    ManifestEntry("9aa62bb321c69d0c52f62c9fcc86f13b005ee36a/COREDEV-9999r1-codex-96c2ca473f971e90f0855291e2528296.txt", REGULAR_FILE),
    ManifestEntry("9aa62bb321c69d0c52f62c9fcc86f13b005ee36a/COREDEV-9999r1-codex-96c2ca473f971e90f0855291e2528296.txt.captureid", REGULAR_FILE),
    ManifestEntry("9aa62bb321c69d0c52f62c9fcc86f13b005ee36a/COREDEV-9999r1-codex-96c2ca473f971e90f0855291e2528296.txt.launch", REGULAR_FILE),
    ManifestEntry("9aa62bb321c69d0c52f62c9fcc86f13b005ee36a/COREDEV-9999r1-gemini-36c5cb831b7f164e5b0ee2934a72b789.txt", REGULAR_FILE),
    ManifestEntry("9aa62bb321c69d0c52f62c9fcc86f13b005ee36a/COREDEV-9999r1-gemini-36c5cb831b7f164e5b0ee2934a72b789.txt.captureid", REGULAR_FILE),
    ManifestEntry("9aa62bb321c69d0c52f62c9fcc86f13b005ee36a/COREDEV-9999r1-gemini-36c5cb831b7f164e5b0ee2934a72b789.txt.launch", REGULAR_FILE),
    ManifestEntry("abc/123r1-gemini-ffcfde63ee0d2fb407da00e6c927dd50.txt", REGULAR_FILE),
    ManifestEntry("abc/123r1-gemini-ffcfde63ee0d2fb407da00e6c927dd50.txt.launch", REGULAR_FILE),
    ManifestEntry("bcda793b5bdcbb9dcb2592246b9a9003385e9e38/COREDEV-9999r1-codex-b18361e095b72d10f336be81e5e40f9e.txt", REGULAR_FILE),
    ManifestEntry("bcda793b5bdcbb9dcb2592246b9a9003385e9e38/COREDEV-9999r1-codex-b18361e095b72d10f336be81e5e40f9e.txt.captureid", REGULAR_FILE),
    ManifestEntry("bcda793b5bdcbb9dcb2592246b9a9003385e9e38/COREDEV-9999r1-codex-b18361e095b72d10f336be81e5e40f9e.txt.launch", REGULAR_FILE),
    ManifestEntry("bcda793b5bdcbb9dcb2592246b9a9003385e9e38/COREDEV-9999r1-gemini-ebaee05047f913a2cb91d58d98ae19bc.txt", REGULAR_FILE),
    ManifestEntry("bcda793b5bdcbb9dcb2592246b9a9003385e9e38/COREDEV-9999r1-gemini-ebaee05047f913a2cb91d58d98ae19bc.txt.captureid", REGULAR_FILE),
    ManifestEntry("bcda793b5bdcbb9dcb2592246b9a9003385e9e38/COREDEV-9999r1-gemini-ebaee05047f913a2cb91d58d98ae19bc.txt.launch", REGULAR_FILE),
    ManifestEntry("df56ce6d9d5c6b55e47e23f1db46fdec52ed2f6e/COREDEV-9999r1-codex-88708cc3e0afb43207fe39196d5058af.txt", REGULAR_FILE),
    ManifestEntry("df56ce6d9d5c6b55e47e23f1db46fdec52ed2f6e/COREDEV-9999r1-codex-88708cc3e0afb43207fe39196d5058af.txt.captureid", REGULAR_FILE),
    ManifestEntry("df56ce6d9d5c6b55e47e23f1db46fdec52ed2f6e/COREDEV-9999r1-codex-88708cc3e0afb43207fe39196d5058af.txt.launch", REGULAR_FILE),
    ManifestEntry("df56ce6d9d5c6b55e47e23f1db46fdec52ed2f6e/COREDEV-9999r1-gemini-c3c1095a91cdb0527230e6d5a38639be.txt", REGULAR_FILE),
    ManifestEntry("df56ce6d9d5c6b55e47e23f1db46fdec52ed2f6e/COREDEV-9999r1-gemini-c3c1095a91cdb0527230e6d5a38639be.txt.captureid", REGULAR_FILE),
    ManifestEntry("df56ce6d9d5c6b55e47e23f1db46fdec52ed2f6e/COREDEV-9999r1-gemini-c3c1095a91cdb0527230e6d5a38639be.txt.launch", REGULAR_FILE),
    ManifestEntry("h1/t1rr1-n1-d535d109b8cc53426b150f67546cc59a.txt", REGULAR_FILE),
    ManifestEntry("h1/t1rr1-n1-d535d109b8cc53426b150f67546cc59a.txt.captureid", REGULAR_FILE),
    ManifestEntry("h1/t1rr1-n1-d535d109b8cc53426b150f67546cc59a.txt.launch", REGULAR_FILE),
    ManifestEntry("testhash/COREDEV-9999r1-codex-d4053b6b18a8dcb719bffb5a7f1118f7.txt", REGULAR_FILE),
    ManifestEntry("testhash/COREDEV-9999r1-codex-d4053b6b18a8dcb719bffb5a7f1118f7.txt.launch", REGULAR_FILE),
)


# The distinct manifest parents, kept literal and already ordered deepest first
# (all nine happen to be at the same depth, with bytewise order as the tie-break).
EMPTY_DIRECTORY_MANIFEST = (
    "38483bff6fb293c5b0f90254466c52bc06a785e7",
    "4c5e3e4c560819f8de798b1a20f7959b037b0de888dc89e561ad3840a3f68076",
    "738b2f6174a7aed615fa597d3847744862d4d5f8",
    "9aa62bb321c69d0c52f62c9fcc86f13b005ee36a",
    "abc",
    "bcda793b5bdcbb9dcb2592246b9a9003385e9e38",
    "df56ce6d9d5c6b55e47e23f1db46fdec52ed2f6e",
    "h1",
    "testhash",
)


def _identity(path: Path) -> Tuple[int, int]:
    metadata = os.stat(str(path), follow_symlinks=False)
    return metadata.st_dev, metadata.st_ino


def _canonical_state_root(state_root: Path) -> Tuple[Path, Tuple[int, int]]:
    supplied = Path(state_root)
    try:
        supplied_metadata = os.lstat(str(supplied))
    except OSError as error:
        raise CleanupError("state root is unavailable: " + str(supplied)) from error
    if not stat.S_ISDIR(supplied_metadata.st_mode):
        raise CleanupError("state root is not a real directory: " + str(supplied))

    try:
        canonical = supplied.resolve(strict=True)
    except OSError as error:
        raise CleanupError("state root cannot be resolved: " + str(supplied)) from error
    return canonical, _identity(canonical)


def _pure_relative_path(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        not value
        or relative.is_absolute()
        or relative.as_posix() != value
        or any(part in ("", ".", "..") for part in relative.parts)
    ):
        raise CleanupError("manifest path is not canonical and relative: " + repr(value))
    return relative


def _resolve_beneath(root: Path, relative_path: str) -> Path:
    relative = _pure_relative_path(relative_path)
    candidate = root.joinpath(*relative.parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise CleanupError("manifest target is unavailable: " + relative_path) from error
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise CleanupError("manifest target escapes the state root: " + relative_path) from error
    if resolved == root:
        raise CleanupError("manifest target resolves to the state root: " + relative_path)
    return resolved


def _describe_type(mode: int) -> str:
    if stat.S_ISREG(mode):
        return REGULAR_FILE
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symbolic link"
    if stat.S_ISFIFO(mode):
        return "FIFO"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character device"
    if stat.S_ISBLK(mode):
        return "block device"
    return "unknown object"


def _directory_sort_key(relative_path: str) -> Tuple[int, bytes]:
    relative = _pure_relative_path(relative_path)
    return -len(relative.parts), os.fsencode(relative.as_posix())


def _validate_closed_manifests() -> None:
    manifest_paths = tuple(entry.relative_path for entry in LEAK_MANIFEST)
    if len(manifest_paths) != 39 or len(set(manifest_paths)) != 39:
        raise CleanupError("the closed leak manifest must contain 39 unique paths")
    if any(entry.expected_type != REGULAR_FILE for entry in LEAK_MANIFEST):
        raise CleanupError("every closed leak-manifest entry must expect a regular file")

    derived_directories = {
        _pure_relative_path(entry.relative_path).parent.as_posix()
        for entry in LEAK_MANIFEST
    }
    if len(EMPTY_DIRECTORY_MANIFEST) != 9 or len(set(EMPTY_DIRECTORY_MANIFEST)) != 9:
        raise CleanupError("the empty-directory manifest must contain 9 unique paths")
    if set(EMPTY_DIRECTORY_MANIFEST) != derived_directories:
        raise CleanupError("the empty-directory manifest must equal the leak-manifest parents")
    if tuple(sorted(EMPTY_DIRECTORY_MANIFEST, key=_directory_sort_key)) != EMPTY_DIRECTORY_MANIFEST:
        raise CleanupError("the empty-directory manifest is not ordered deepest first")


def _preflight_directories(
    root: Path,
    relative_directories: Sequence[str],
    require_empty: bool,
) -> Dict[str, Path]:
    resolved_directories = {}  # type: Dict[str, Path]
    nonempty = []  # type: List[str]
    for relative_path in relative_directories:
        resolved = _resolve_beneath(root, relative_path)
        lexical = root.joinpath(*_pure_relative_path(relative_path).parts)
        try:
            metadata = os.lstat(str(lexical))
        except OSError as error:
            raise CleanupError("manifest directory is unavailable: " + relative_path) from error
        if not stat.S_ISDIR(metadata.st_mode):
            raise CleanupError(
                "manifest directory type mismatch for "
                + relative_path
                + ": expected directory, found "
                + _describe_type(metadata.st_mode)
            )
        if require_empty:
            try:
                with os.scandir(str(resolved)) as children:
                    if next(children, None) is not None:
                        nonempty.append(relative_path)
            except OSError as error:
                raise CleanupError("could not inspect manifest directory: " + relative_path) from error
        resolved_directories[relative_path] = resolved

    if nonempty:
        raise CleanupError(
            "refusing directory removal because the following manifest directories are not empty: "
            + ", ".join(nonempty)
        )
    return resolved_directories


def _preflight_files(root: Path, allow_absent: bool = False) -> Tuple[Dict[str, Path], List[str]]:
    """Resolve every manifest target, optionally tolerating ones that are already gone.

    `allow_absent` makes the run RESUMABLE. Without it a single failed unlink — EACCES, an I/O
    error, a concurrent removal — was terminal for the tool: entries 1..n-1 were already deleted,
    so every later invocation aborted here on "manifest target is unavailable", and the remaining
    leaked transcripts could never be removed by the sanctioned tool again. That forces exactly the
    ad-hoc `rm` in a sensitive directory that the closed-manifest design exists to prevent
    (PR #63 review, gap 5).

    An already-absent leaf is treated as SATISFIED, never as an error — the goal state is "this
    file does not exist", and it does not. Everything else stays fail-closed: a type mismatch or a
    path escaping the state root still raises, because those mean the tree is not what the frozen
    manifest describes and deleting anything would be unsafe.

    lstat is checked BEFORE resolution on purpose: `_resolve_beneath` uses `resolve(strict=True)`,
    which also fails for a dangling symlink. Only a genuine ENOENT on the LEXICAL path counts as
    absent; a symlink whose target is missing is still a type mismatch and must be reported.
    """
    resolved_targets = {}  # type: Dict[str, Path]
    already_absent = []  # type: List[str]
    for entry in LEAK_MANIFEST:
        lexical = root.joinpath(*_pure_relative_path(entry.relative_path).parts)
        try:
            metadata = os.lstat(str(lexical))
        except FileNotFoundError:
            if allow_absent:
                already_absent.append(entry.relative_path)
                continue
            raise CleanupError("manifest target is unavailable: " + entry.relative_path)
        except OSError as error:
            raise CleanupError("manifest target is unavailable: " + entry.relative_path) from error
        resolved = _resolve_beneath(root, entry.relative_path)
        actual_type = _describe_type(metadata.st_mode)
        if actual_type != entry.expected_type:
            raise CleanupError(
                "manifest target type mismatch for "
                + entry.relative_path
                + ": expected "
                + entry.expected_type
                + ", found "
                + actual_type
            )
        resolved_targets[entry.relative_path] = resolved
    return resolved_targets, already_absent


def unlink_regular_file(target: Path) -> None:
    """Unlink one already-resolved regular file; never remove a directory."""

    metadata = os.lstat(str(target))
    if not stat.S_ISREG(metadata.st_mode):
        raise CleanupError(
            "target changed type before unlink: "
            + str(target)
            + " is "
            + _describe_type(metadata.st_mode)
        )
    os.unlink(str(target))


def delete_leak_files(state_root: Path) -> FileDeletionReport:
    """Delete the 39 literal manifest files and nothing else."""

    _validate_closed_manifests()
    root, root_identity = _canonical_state_root(state_root)
    _preflight_directories(root, EMPTY_DIRECTORY_MANIFEST, require_empty=False)
    # Resumable: entries already gone are satisfied, not failures. See _preflight_files.
    resolved_targets, already_absent = _preflight_files(root, allow_absent=True)

    attempted = []  # type: List[str]
    for entry in LEAK_MANIFEST:
        attempted.append(entry.relative_path)
        if entry.relative_path not in resolved_targets:
            continue  # already absent — the goal state for this entry is reached
        try:
            unlink_regular_file(resolved_targets[entry.relative_path])
        except CleanupError:
            raise
        except OSError as error:
            raise CleanupError("could not unlink manifest target: " + entry.relative_path) from error

    expected = tuple(entry.relative_path for entry in LEAK_MANIFEST)
    if Counter(attempted) != Counter(expected) or set(attempted) != set(expected):
        raise CleanupError("attempted deletion targets do not equal the closed leak manifest")
    if _identity(root) != root_identity:
        raise CleanupError("state-root identity changed during file deletion")
    return FileDeletionReport(tuple(attempted), root_identity)


def remove_empty_directory(target: Path) -> None:
    """Remove one preflighted empty directory without recursion."""

    os.rmdir(str(target))


def _remove_empty_directories(
    state_root: Path,
    relative_directories: Iterable[str],
) -> Tuple[str, ...]:
    root, root_identity = _canonical_state_root(state_root)
    ordered = tuple(sorted(tuple(relative_directories), key=_directory_sort_key))
    if len(ordered) != len(set(ordered)):
        raise CleanupError("empty-directory removal targets contain duplicates")
    resolved = _preflight_directories(root, ordered, require_empty=False)

    removed = []  # type: List[str]
    for relative_path in ordered:
        try:
            with os.scandir(str(resolved[relative_path])) as children:
                if next(children, None) is not None:
                    raise CleanupError(
                        "refusing directory removal because the manifest directory is not empty: "
                        + relative_path
                    )
        except CleanupError:
            raise
        except OSError as error:
            raise CleanupError(
                "could not inspect manifest directory: " + relative_path
            ) from error
        try:
            remove_empty_directory(resolved[relative_path])
        except OSError as error:
            raise CleanupError("could not remove empty manifest directory: " + relative_path) from error
        removed.append(relative_path)

    if _identity(root) != root_identity:
        raise CleanupError("state-root identity changed during empty-directory removal")
    return tuple(removed)


def cleanup_coredev_2619_leaks(state_root: Path) -> CleanupReport:
    """Run the closed file cleanup, then remove exactly its nine empty parents."""

    file_report = delete_leak_files(state_root)
    removed_directories = _remove_empty_directories(
        state_root,
        EMPTY_DIRECTORY_MANIFEST,
    )
    expected_directories = tuple(
        sorted(EMPTY_DIRECTORY_MANIFEST, key=_directory_sort_key)
    )
    if removed_directories != expected_directories or len(removed_directories) != 9:
        raise CleanupError("removed directories do not equal the closed 9-entry manifest")
    _root, root_identity = _canonical_state_root(state_root)
    if root_identity != file_report.root_identity:
        raise CleanupError("state-root identity changed across cleanup phases")
    return CleanupReport(
        file_report.attempted_relative_paths,
        removed_directories,
        root_identity,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-root",
        required=True,
        type=Path,
        help="explicit review-transcripts state root; HOME is never consulted",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="required acknowledgement that the closed manifest was verified first",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="read-only preflight: report what WOULD be removed and what is already gone; deletes nothing",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(None if argv is None else list(argv))
    if arguments.check and arguments.apply:
        print("cleanup refused: --check and --apply are mutually exclusive", file=sys.stderr)
        return 2
    if arguments.check:
        # Read-only. The tool is destructive and one-shot, so there must be a way to SEE the state
        # it would act on without acting (PR #63 review, gap 5). Nothing here mutates the tree.
        try:
            _validate_closed_manifests()
            root, _identity_unused = _canonical_state_root(arguments.state_root)
            _preflight_directories(root, EMPTY_DIRECTORY_MANIFEST, require_empty=False)
            present, absent = _preflight_files(root, allow_absent=True)
        except (CleanupError, OSError) as error:
            print("cleanup check failed: " + str(error), file=sys.stderr)
            return 1
        print(
            "check: "
            + str(len(present))
            + " of "
            + str(len(LEAK_MANIFEST))
            + " manifest files present and removable, "
            + str(len(absent))
            + " already absent"
        )
        for relative_path in sorted(absent):
            print("  already absent: " + relative_path)
        return 0
    if not arguments.apply:
        print("cleanup refused: pass --apply only after independent manifest verification", file=sys.stderr)
        return 2
    try:
        report = cleanup_coredev_2619_leaks(arguments.state_root)
    except (CleanupError, OSError) as error:
        print("cleanup refused: " + str(error), file=sys.stderr)
        return 1
    print(
        "removed "
        + str(len(report.attempted_relative_paths))
        + " manifest files and "
        + str(len(report.removed_directories))
        + " empty manifest directories"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
