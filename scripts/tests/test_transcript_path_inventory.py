#!/usr/bin/env python3
"""M3.1 drift proof for COREDEV-2619's frozen transcript-path inventory."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import unittest
import unittest.mock
from collections import Counter
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO / "docs/planning/COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json"
FROZEN_COMMIT = "78e28f26cb56572b22fe1635552dd10fa95bdb48"
EXPECTED_LITERALS = ("/tmp/" + "agy-out.txt", "/tmp/" + "codex-out.txt")
# The two literals above are a BLACKLIST, and blacklists re-open: a sibling spelling -- the same
# tmp path with a digit appended before the extension -- matched none of them and sailed past
# every guard here (PR #63 review, gap 24). The example is described rather than written out,
# because writing it would trip this very check: that is the guard working, and it did.
# This pattern closes that family. Verified against the tree: it matches EXACTLY the two literals
# already classified and introduces no new site, so the frozen 31-site totals are unaffected.
#
# NOT the principled fix. The scanner's own lesson is to invert a blacklist into an ALLOWLIST -- deny
# every hardcoded /tmp transcript path and let the quote-keep manifest be the only exemption. The tree
# carries ten distinct `/tmp/*.txt` spellings (ping, packages, safe, copy, security, ...), so that
# inversion means reclassifying all of them and re-deriving the frozen manifest. Tracked separately;
# this closes the named sibling hazard without pretending to be the inversion.
EXPECTED_LITERAL_PATTERN = re.compile(r"/tmp/(?:agy|codex)-out\d*\.txt")
EXPECTED_TOTALS = {"sites": 31, "files": 13, "rewrite": 21, "quote-keep": 10}
EXPECTED_SCAN_EXCLUSIONS = {
    "docs/planning/COREDEV-2619_PER_RUN_TRANSCRIPT_PATHS_PLAN.md",
}
EXPECTED_FILE_COUNTS = {
    "CHANGELOG.md": {"sites": 1, "rewrite": 0, "quote-keep": 1},
    "README.md": {"sites": 1, "rewrite": 1, "quote-keep": 0},
    "docs/audits/PLUGIN_AUDIT_2026-07-19.md": {"sites": 4, "rewrite": 0, "quote-keep": 4},
    "docs/planning/COREDEV-2497_VERIFY_TRANSCRIPTS_PLAN.md": {
        "sites": 1,
        "rewrite": 0,
        "quote-keep": 1,
    },
    "docs/planning/HANDOFF.md": {"sites": 1, "rewrite": 0, "quote-keep": 1},
    "docs/planning/OCTO_ADOPTION_PLAN.md": {"sites": 1, "rewrite": 0, "quote-keep": 1},
    "scripts/pty-capture.py": {"sites": 3, "rewrite": 3, "quote-keep": 0},
    "scripts/review-verdict.py": {"sites": 1, "rewrite": 0, "quote-keep": 1},
    "scripts/tests/test_review_verdict.py": {"sites": 1, "rewrite": 0, "quote-keep": 1},
    "skills/brainstorm/SKILL.md": {"sites": 2, "rewrite": 2, "quote-keep": 0},
    "skills/codex-review/SKILL.md": {"sites": 5, "rewrite": 5, "quote-keep": 0},
    "skills/gemini-review/SKILL.md": {"sites": 5, "rewrite": 5, "quote-keep": 0},
    "skills/review-synthesis/SKILL.md": {"sites": 5, "rewrite": 5, "quote-keep": 0},
}
EXPECTED_CONTRACT_COUNTS = {
    "S-CAPTURE": 9,
    "S-PRECLEAN": 3,
    "S-THREAD": 15,
    "S-WRAPPER": 1,
}
EXPECTED_SCHEMA_VERSION = 2
# COREDEV-2798.  These files are PREPENDED TO — CHANGELOG.md gains a section per release and
# README.md gains a What's-New entry — so every physical line below the insertion point shifts and a
# line pin in them is a value that goes stale on a schedule.  Regenerating the frozen manifest each
# release is not the repair: it would make the tree authoritative over the assertion meant to detect
# the tree changing.  For these files identity is CONTENT-ADDRESSED, and the manifest's `line`,
# `destination.line`, `precedingAnchorLine` and `followingAnchorLine` are re-derived HINTS rather
# than assertions.  Every other file keeps its line assertion unchanged.
#
# Frozen HERE rather than read from the manifest, for the same reason EXPECTED_LITERALS is: an oracle
# derived from the data under test cannot detect that data changing.
PREPEND_ONLY_FILES = frozenset({"CHANGELOG.md", "README.md"})
SHA256_LENGTH = 64


def _payload_lines(raw: bytes) -> list[bytes]:
    """Return physical-line payloads without their CR/LF terminators."""
    payloads = []
    for line in raw.splitlines(keepends=True):
        if line.endswith(b"\r\n"):
            payloads.append(line[:-2])
        elif line.endswith((b"\n", b"\r")):
            payloads.append(line[:-1])
        else:
            payloads.append(line)
    return payloads


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _destination_path(site: dict) -> str:
    """Where a rewrite's destination content lives, which is not always its source file.

    Defaults to the site's own `path`, so every pre-existing record means exactly what it did. A
    rewrite whose destination later moved to another file — as the codex capture body did when it
    became `scripts/review/capture-codex-review.sh` (COREDEV-2642) — sets `destination.path`. Without
    it the only ways to record that move were to point the destination at a line that merely MENTIONS
    the rule, or to delete the site and edit the frozen counts; the first is a contract check passing
    on prose, and the second loses the record that the rewrite happened at all.
    """
    return site["destination"].get("path", site["path"])


def _destination_payloads(site: dict) -> list[bytes]:
    return [payload.encode("utf-8") for payload in site["destination"]["payloads"]]


def _destination_sha256(payloads: list[bytes]) -> str:
    return _sha256(b"\n".join(payloads))


def _sequence_positions(lines: list[bytes], payloads: list[bytes]) -> list[int]:
    width = len(payloads)
    return [
        index
        for index in range(len(lines) - width + 1)
        if lines[index : index + width] == payloads
    ]


def _load_manifest() -> dict:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _tracked_tree() -> dict[str, list[bytes]]:
    completed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    paths = set(completed.stdout.decode("utf-8", errors="surrogateescape").rstrip("\0").split("\0"))
    # Include this step's untracked deliverables so the human can run M3.1 before staging them.
    paths.update(
        {
            str(MANIFEST_PATH.relative_to(REPO)),
            str(Path(__file__).resolve().relative_to(REPO)),
        }
    )
    return {
        path: _payload_lines((REPO / path).read_bytes())
        for path in sorted(paths)
        if path and (REPO / path).is_file()
    }


def _site_key(site: dict) -> tuple[str, int]:
    return site["path"], site["line"]


def _quote_keep_positions(site: dict, lines: list[bytes]) -> list[int]:
    """1-based line numbers whose whole payload hashes to the site's frozen sourceSha256."""
    return [
        index
        for index, payload in enumerate(lines, 1)
        if _sha256(payload) == site["sourceSha256"]
    ]


def _resolved_site_key(site: dict, tree: dict[str, list[bytes]]) -> tuple[str, int]:
    """The site's LIVE key: content-addressed in prepend-only files, declared elsewhere.

    Used for the observed-vs-declared literal set comparison, which is otherwise line-keyed and so
    reports both a missing and a surviving literal for every prepend (COREDEV-2798).  Falls back to
    the declared line when the content is absent or ambiguous, so that the dedicated per-site checks
    below emit the specific diagnostic instead of this set difference emitting a confusing pair.
    """
    if site["path"] not in PREPEND_ONLY_FILES:
        return _site_key(site)
    lines = tree.get(site["path"])
    if lines is None:
        return _site_key(site)
    positions = _quote_keep_positions(site, lines)
    return (site["path"], positions[0]) if len(positions) == 1 else _site_key(site)


def _destination_occurrences(site: dict, destination_lines: list[bytes]) -> list[int]:
    """0-based start offsets at which the frozen destination payload block occurs."""
    return _sequence_positions(destination_lines, _destination_payloads(site))


def _legacy_source_survives(site: dict, lines: list[bytes]) -> bool:
    """Does the deliberately-deleted legacy source payload still exist in its own file?

    A module-level predicate rather than an inline `any(...)` so cell 7's control can MUTATE it —
    the restored-legacy-source case also reds through the independent observed-literal census, so
    "the case is red" proves reachability, not discrimination.  Deleting this branch must make its
    diagnostic disappear, and only a separately addressable branch can be shown to do that.
    """
    return any(_sha256(payload) == site["sourceSha256"] for payload in lines)


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != SHA256_LENGTH:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _derived_file_counts(sites: list[dict]) -> dict[str, dict[str, int]]:
    counts = {}
    for site in sites:
        entry = counts.setdefault(site["path"], {"sites": 0, "rewrite": 0, "quote-keep": 0})
        entry["sites"] += 1
        if site.get("class") in ("rewrite", "quote-keep"):
            entry[site["class"]] += 1
    return counts


def _contract_problems(location: str, contracts: list[str], payloads: list[bytes]) -> list[str]:
    problems = []
    joined = b"\n".join(payloads)
    if "S-PRECLEAN" in contracts and (
        b"rm -f" in joined or any(literal.encode("utf-8") in joined for literal in EXPECTED_LITERALS)
    ):
        problems.append(f"{location}: destination violates S-PRECLEAN")
    # The wrapper is named, not path-spelled. The single S-WRAPPER destination moved into
    # `capture-codex-review.sh`, which resolves the allocator as a SIBLING (`${SCRIPT_DIR}/…`), so the
    # old `scripts/review/` prefix no longer appears at the call site even though the call is the same.
    # This does accept more strings than the prefix did — a bare prose mention would match — but the
    # only site carrying S-WRAPPER also carries S-CAPTURE, so its destination must additionally show
    # `--allocated`, and a comment mentioning the wrapper does not.
    if "S-WRAPPER" in contracts and b"allocate-transcript.sh" not in joined:
        problems.append(f"{location}: destination lacks S-WRAPPER allocation")
    # `CODEX_TRANSCRIPT` joins `GEMINI_TRANSCRIPT` as accepted evidence: the codex arm now hands its
    # allocated leaf to `isolated-codex-review.sh` exactly as the gemini arm hands it to
    # `isolated-agy-review.sh` (COREDEV-2642, P1 — the `--allocated` write moved into the shared
    # isolation harness for both arms), so the capture recipe shows the threaded transcript name rather
    # than `--allocated` directly. Symmetric with the gemini whitelist entry.
    if "S-CAPTURE" in contracts and not any(
        token in joined
        for token in (b"--allocated", b"GEMINI_TRANSCRIPT", b"CODEX_TRANSCRIPT", b"allocated", b"reserved")
    ):
        problems.append(f"{location}: destination lacks S-CAPTURE evidence")
    # `REVIEWER_SPEC` replaces `PERSIST_SPEC`: the synthesis recipe no longer classifies the spec
    # itself — `persist-verdict.sh` does — so what the destination binds is the opaque argument the
    # skill received, which is the value that carries the allocated path. Same evidence, one name
    # further upstream. Enumerated rather than a `_SPEC` pattern, so a new spelling has to be added
    # deliberately instead of matching by accident.
    if "S-THREAD" in contracts and not any(
        token in joined
        for token in (b"TRANSCRIPT", b"allocated", b"REVIEWER_SPEC")
    ):
        problems.append(f"{location}: destination lacks S-THREAD evidence")
    return problems


def _manifest_problems(manifest: dict) -> list[str]:
    problems = []
    if manifest.get("schemaVersion") != EXPECTED_SCHEMA_VERSION:
        problems.append(f"schemaVersion must be {EXPECTED_SCHEMA_VERSION}")
    if manifest.get("ticket") != "COREDEV-2619" or manifest.get("step") != "S-INVENTORY":
        problems.append("ticket/step identity drifted")
    if manifest.get("frozenCommit") != FROZEN_COMMIT:
        problems.append("frozenCommit drifted")
    if set(manifest.get("scanExclusions", ())) != EXPECTED_SCAN_EXCLUSIONS:
        problems.append("scan exclusions drifted")
    if manifest.get("expectedTotals") != EXPECTED_TOTALS:
        problems.append("locked totals drifted")
    if manifest.get("expectedFileCounts") != EXPECTED_FILE_COUNTS:
        problems.append("locked per-file counts drifted")

    sites = manifest.get("sites")
    if not isinstance(sites, list):
        return problems + ["sites must be a list"]

    locations = [site.get("location") for site in sites if isinstance(site, dict)]
    if len(locations) != len(set(locations)):
        problems.append("site locations are not unique")

    class_counts = Counter()
    contract_counts = Counter()
    destination_identities = []
    for site in sites:
        if not isinstance(site, dict):
            problems.append(f"site is not an object: {site!r}")
            continue
        path = site.get("path")
        line = site.get("line")
        location = site.get("location", f"{path}:{line}")
        if location != f"{path}:{line}":
            problems.append(f"{location}: location must equal path:line")
        if not isinstance(path, str) or not isinstance(line, int) or line < 1:
            problems.append(f"{location}: path and positive physical line are required")
        classification = site.get("class")
        expected = EXPECTED_FILE_COUNTS.get(path, {}).get(classification, 0)
        if classification not in ("rewrite", "quote-keep") or expected == 0:
            problems.append(f"{location}: class {classification!r} contradicts the frozen file class")
        else:
            class_counts[classification] += 1
        reason = site.get("reason")
        if not isinstance(reason, str) or not reason.strip() or "\n" in reason or "\r" in reason:
            problems.append(f"{location}: reason must be one nonempty line")
        if not _is_sha256(site.get("sourceSha256")):
            problems.append(f"{location}: sourceSha256 is not lowercase SHA-256")

        contracts = site.get("contracts")
        anchor_keys = (
            "precedingAnchorLine",
            "precedingAnchorSha256",
            "followingAnchorLine",
            "followingAnchorSha256",
        )
        if classification == "rewrite":
            if not isinstance(contracts, list) or not contracts:
                problems.append(f"{location}: rewrite lacks an owning contract label")
                contracts = []
            else:
                contract_counts.update(contracts)
            for key in anchor_keys:
                if key not in site:
                    problems.append(f"{location}: rewrite lacks {key}")
            for key in ("precedingAnchorSha256", "followingAnchorSha256"):
                if key in site and not _is_sha256(site[key]):
                    problems.append(f"{location}: {key} is not lowercase SHA-256")

            destination = site.get("destination")
            if not isinstance(destination, dict):
                problems.append(f"{location}: rewrite lacks its frozen destination")
                continue
            destination_line = destination.get("line")
            raw_payloads = destination.get("payloads")
            if not isinstance(destination_line, int) or destination_line < 1:
                problems.append(f"{location}: destination line must be positive")
            if (
                not isinstance(raw_payloads, list)
                or not raw_payloads
                or any(
                    not isinstance(payload, str)
                    or not payload
                    or "\n" in payload
                    or "\r" in payload
                    for payload in raw_payloads
                )
            ):
                problems.append(f"{location}: destination payloads must be nonempty physical lines")
                continue
            payloads = [payload.encode("utf-8") for payload in raw_payloads]
            payload_sha256 = destination.get("payloadSha256")
            if not _is_sha256(payload_sha256):
                problems.append(f"{location}: destination payloadSha256 is not lowercase SHA-256")
            elif payload_sha256 != _destination_sha256(payloads):
                problems.append(f"{location}: destination payloadSha256 does not hash its payload block")
            if any(
                literal.encode("utf-8") in payload
                for literal in EXPECTED_LITERALS
                for payload in payloads
            ):
                problems.append(f"{location}: destination retains a legacy output literal")
            problems.extend(_contract_problems(location, contracts, payloads))
            destination_path = destination.get("path", path)
            if not isinstance(destination_path, str) or not destination_path:
                problems.append(f"{location}: destination path must be a nonempty string")
            destination_identities.append(
                (destination_path, destination_line, payload_sha256)
            )
        elif any(key in site for key in ("contracts", "destination") + anchor_keys):
            problems.append(f"{location}: quote-keep must not carry rewrite-only fields")

    if len(destination_identities) != len(set(destination_identities)):
        problems.append("rewrite destination identities are not unique")
    derived_totals = {
        "sites": len(sites),
        "files": len({site.get("path") for site in sites if isinstance(site, dict)}),
        "rewrite": class_counts["rewrite"],
        "quote-keep": class_counts["quote-keep"],
    }
    if derived_totals != EXPECTED_TOTALS:
        problems.append(f"site-derived totals drifted: {derived_totals!r}")
    if _derived_file_counts(sites) != EXPECTED_FILE_COUNTS:
        problems.append("site-derived per-file counts drifted")
    if dict(sorted(contract_counts.items())) != EXPECTED_CONTRACT_COUNTS:
        problems.append(f"owning-contract counts drifted: {dict(contract_counts)!r}")
    return problems


def _observed_literal_sites(manifest: dict, tree: dict[str, list[bytes]]) -> set[tuple[str, int]]:
    literals = tuple(literal.encode("utf-8") for literal in EXPECTED_LITERALS)
    pattern = re.compile(EXPECTED_LITERAL_PATTERN.pattern.encode("ascii"))
    exclusions = set(manifest["scanExclusions"])
    return {
        (path, line_number)
        for path, lines in tree.items()
        if path not in exclusions
        for line_number, payload in enumerate(lines, 1)
        if any(literal in payload for literal in literals) or pattern.search(payload)
    }


def _tree_problems(manifest: dict, tree: dict[str, list[bytes]]) -> list[str]:
    problems = []
    sites = manifest["sites"]
    # COREDEV-2798: keyed on the site's RESOLVED line, so a prepend that shifts a quote-keep literal
    # does not report it simultaneously missing (declared line) and surviving (observed line).
    quote_keep_sites = {
        _resolved_site_key(site, tree) for site in sites if site["class"] == "quote-keep"
    }
    observed_sites = _observed_literal_sites(manifest, tree)
    for path, line in sorted(quote_keep_sites - observed_sites):
        problems.append(f"{path}:{line}: quote-keep output literal is missing")
    for path, line in sorted(observed_sites - quote_keep_sites):
        problems.append(f"{path}:{line}: output literal survives outside the quote-keep set")

    for site in sites:
        location = site["location"]
        lines = tree.get(site["path"])
        if lines is None:
            problems.append(f"{location}: classified file is missing")
            continue
        if site["class"] == "quote-keep":
            if site["path"] in PREPEND_ONLY_FILES:
                # Identity is the payload, not its position.  EXACTLY ONE, never "at least one":
                # a duplicated source line would otherwise satisfy the assertion while leaving the
                # site genuinely ambiguous, and the two counts get their own diagnostics so cells 6
                # and 7 discriminate the branch under test rather than a sibling.
                positions = _quote_keep_positions(site, lines)
                if not positions:
                    problems.append(f"{location}: quote-keep payload hash drifted")
                elif len(positions) > 1:
                    problems.append(f"{location}: quote-keep payload hash is not unique")
            elif site["line"] > len(lines):
                problems.append(f"{location}: quote-keep physical line is missing")
            elif _sha256(lines[site["line"] - 1]) != site["sourceSha256"]:
                problems.append(f"{location}: quote-keep payload hash drifted")
            continue

        if _legacy_source_survives(site, lines):
            problems.append(f"{location}: legacy source payload survives")

        destination = site["destination"]
        # The legacy-source check above is about the SOURCE file; the destination may live elsewhere.
        destination_lines = tree.get(_destination_path(site))
        if destination_lines is None:
            problems.append(f"{location}: destination file is missing: {_destination_path(site)}")
            continue
        expected_payloads = _destination_payloads(site)
        if _destination_path(site) in PREPEND_ONLY_FILES:
            # Content-addressed: `destination.line` is a hint here, so a prepend that shifts the
            # block is not drift.  Deleting or editing the block still reds, because the block then
            # occurs zero times.  Same exactly-one rule, with its own two diagnostics.
            occurrences = _destination_occurrences(site, destination_lines)
            if not occurrences:
                problems.append(f"{location}: destination payload block is missing")
            elif len(occurrences) > 1:
                problems.append(f"{location}: destination payload block is not unique")
            else:
                start = occurrences[0]
                problems.extend(
                    _contract_problems(
                        location,
                        site["contracts"],
                        destination_lines[start : start + len(expected_payloads)],
                    )
                )
            continue
        start = destination["line"] - 1
        stop = start + len(expected_payloads)
        if stop > len(destination_lines):
            problems.append(
                f"{location}: destination at final line {destination['line']} is missing"
            )
            continue
        actual_payloads = destination_lines[start:stop]
        if actual_payloads != expected_payloads:
            problems.append(
                f"{location}: destination payload drifted at final line {destination['line']}"
            )
        else:
            problems.extend(_contract_problems(location, site["contracts"], actual_payloads))
    return problems


def _completed_positive_tree(
    manifest: dict, tree: dict[str, list[bytes]]
) -> dict[str, list[bytes]]:
    """Materialize only exact legacy-source gaps for mutation-test discrimination.

    The real-tree assertion never uses this fixture.  It lets the 21 mutation
    cases begin from a passing positive even while an implementation step still
    carries its frozen source.  A missing destination whose source is already
    gone is deliberately not repaired here.
    """
    completed = {path: list(lines) for path, lines in tree.items()}
    for site in manifest["sites"]:
        if site["class"] != "rewrite":
            continue
        lines = completed[site["path"]]
        source_positions = [
            index
            for index, payload in enumerate(lines)
            if _sha256(payload) == site["sourceSha256"]
        ]
        if not source_positions:
            continue
        if len(source_positions) != 1:
            raise AssertionError(f"{site['location']}: source payload is not unique")
        payloads = _destination_payloads(site)
        destination_lines = completed[_destination_path(site)]
        if _sequence_positions(destination_lines, payloads):
            del lines[source_positions[0]]
        else:
            lines[source_positions[0] : source_positions[0] + 1] = payloads
    return completed


def _nonempty_line_count(tree: dict[str, list[bytes]]) -> int:
    return sum(bool(payload) for lines in tree.values() for payload in lines)


def _occupied_destination_count(manifest: dict, tree: dict[str, list[bytes]]) -> int:
    occupied = 0
    for site in manifest["sites"]:
        if site["class"] != "rewrite":
            continue
        # DELIBERATELY WEAK, and POSITIONAL ONLY.  This counter exists so the deletion mutation can
        # be shown NOT to be caught by a guard that merely counts occupied slots — that is what forces
        # the payload comparison to be the thing doing the discriminating.  Content-addressing it
        # would make it re-implement the real check and red for the same reason as the assertion under
        # test: the confounded control this suite repairs in cells 6 and 7.
        #
        # A POSITIONAL control is therefore meaningless for a content-addressed site, whose declared
        # line is an explicitly stale hint (COREDEV-2798) — reading that line measures an unrelated
        # slot.  Those sites are skipped, and the deletion case keeps its other two weak controls,
        # the observed-literal set and the nonempty-line count, both of which do survive the mutation.
        if _destination_path(site) in PREPEND_ONLY_FILES:
            continue
        lines = tree[_destination_path(site)]
        width = len(site["destination"]["payloads"])
        start = site["destination"]["line"] - 1
        slot = lines[start : start + width]
        if len(slot) == width and all(slot):
            occupied += 1
    return occupied


class M3_1_InventoryDrift(unittest.TestCase):
    """Bind every frozen source identity to its exact final destination."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.manifest = _load_manifest()
        cls.tree = _tracked_tree()
        cls.completed_tree = _completed_positive_tree(cls.manifest, cls.tree)

    def test_manifest_reproduces_the_locked_section_7_inventory(self):
        self.assertEqual([], _manifest_problems(self.manifest))

    def test_current_tree_matches_every_frozen_destination_identity(self):
        self.assertEqual([], _tree_problems(self.manifest, self.tree))

    def test_manifest_derived_completed_tree_is_a_passing_positive_control(self):
        self.assertEqual([], _tree_problems(self.manifest, self.completed_tree))

    def test_each_rewrite_destination_deletion_is_detected_with_counts_unchanged(self):
        rewrites = [site for site in self.manifest["sites"] if site["class"] == "rewrite"]
        self.assertEqual(EXPECTED_TOTALS["rewrite"], len(rewrites))
        baseline_literals = _observed_literal_sites(self.manifest, self.completed_tree)
        baseline_nonempty = _nonempty_line_count(self.completed_tree)
        baseline_occupied = _occupied_destination_count(self.manifest, self.completed_tree)
        positional_rewrites = sum(
            1 for site in rewrites if _destination_path(site) not in PREPEND_ONLY_FILES
        )
        # Every rewrite except the content-addressed ones, which this positional control skips.
        self.assertEqual(EXPECTED_TOTALS["rewrite"] - 1, positional_rewrites)
        self.assertEqual(positional_rewrites, baseline_occupied)
        for site in rewrites:
            with self.subTest(location=site["location"]):
                mutated = dict(self.completed_tree)
                lines = list(mutated[_destination_path(site)])
                width = len(site["destination"]["payloads"])
                if _destination_path(site) in PREPEND_ONLY_FILES:
                    occurrences = _destination_occurrences(site, lines)
                    self.assertEqual(1, len(occurrences))
                    start = occurrences[0]
                else:
                    start = site["destination"]["line"] - 1
                self.assertEqual(_destination_payloads(site), lines[start : start + width])
                line_count = len(lines)
                # Delete the expected payload while retaining nonempty physical
                # slots, so a guard that only counts sites/lines still passes.
                for offset in range(width):
                    lines[start + offset] = (
                        f"# M3.1 deleted destination {site['location']} part {offset + 1}"
                    ).encode("utf-8")
                mutated[_destination_path(site)] = lines
                self.assertEqual(line_count, len(lines))
                self.assertEqual(baseline_nonempty, _nonempty_line_count(mutated))
                self.assertEqual(
                    baseline_occupied,
                    _occupied_destination_count(self.manifest, mutated),
                )
                self.assertEqual(
                    baseline_literals,
                    _observed_literal_sites(self.manifest, mutated),
                )
                problems = _tree_problems(self.manifest, mutated)
                if _destination_path(site) in PREPEND_ONLY_FILES:
                    expected = f"{site['location']}: destination payload block is missing"
                else:
                    expected = (
                        f"{site['location']}: destination payload drifted at final line "
                        f"{site['destination']['line']}"
                    )
                self.assertIn(expected, problems)

    def test_each_rewrite_same_file_relocation_is_detected_with_counts_unchanged(self):
        rewrites = [site for site in self.manifest["sites"] if site["class"] == "rewrite"]
        self.assertEqual(EXPECTED_TOTALS["rewrite"], len(rewrites))
        baseline_literals = _observed_literal_sites(self.manifest, self.completed_tree)
        for site in rewrites:
            with self.subTest(location=site["location"]):
                if _destination_path(site) in PREPEND_ONLY_FILES:
                    # COREDEV-2798: identity here is the payload, not its position, so a same-file
                    # relocation is exactly what a prepend does and is DELIBERATELY not drift.  The
                    # discrimination this case supplies for line-addressed destinations is supplied
                    # for these by the deletion case above (the block then occurs zero times) and by
                    # the duplicate case (two occurrences), both of which still red.
                    continue
                mutated = dict(self.completed_tree)
                lines = list(mutated[_destination_path(site)])
                original_payload_counts = Counter(lines)
                start = site["destination"]["line"] - 1
                width = len(site["destination"]["payloads"])
                moved = lines[start : start + width]
                self.assertEqual(_destination_payloads(site), moved)
                del lines[start : start + width]
                if start == len(lines):
                    lines[0:0] = moved
                else:
                    lines.extend(moved)
                mutated[_destination_path(site)] = lines
                self.assertEqual(
                    original_payload_counts,
                    Counter(lines),
                    "same-file relocation must preserve aggregate payload counts",
                )
                self.assertEqual(
                    baseline_literals,
                    _observed_literal_sites(self.manifest, mutated),
                )
                problems = _tree_problems(self.manifest, mutated)
                self.assertIn(
                    f"{site['location']}: destination payload drifted at final line "
                    f"{site['destination']['line']}",
                    problems,
                )

    def test_reclassification_in_either_direction_is_detected(self):
        for site_index, site in enumerate(self.manifest["sites"]):
            with self.subTest(location=site["location"]):
                mutated = copy.deepcopy(self.manifest)
                mutated_site = mutated["sites"][site_index]
                mutated_site["class"] = "quote-keep" if site["class"] == "rewrite" else "rewrite"
                problems = _manifest_problems(mutated)
                self.assertTrue(
                    any(problem.startswith(site["location"] + ":") for problem in problems),
                    f"reclassifying {site['location']} was not attributed to that identity: {problems}",
                )

    def test_new_literal_outside_the_closed_set_is_detected(self):
        mutated = dict(self.tree)
        lines = list(mutated["SECURITY.md"])
        new_line = len(lines) + 1
        lines.append(EXPECTED_LITERALS[0].encode("utf-8"))
        mutated["SECURITY.md"] = lines
        self.assertIn(
            f"SECURITY.md:{new_line}: output literal survives outside the quote-keep set",
            _tree_problems(self.manifest, mutated),
        )


class M1_ContentAddressedPrependOnlySites(unittest.TestCase):
    """COREDEV-2798 cells 6 and 7 — identity is CLASS-SPECIFIC, and the demotion is SCOPED.

    Cell 6 (quote-keep) and cell 7 (rewrite) each prove the same three things for their class: a
    prepend passes with NO manifest edit; a content change reds; and a DUPLICATE reds — the last
    because "at least one" would accept an ambiguous site, and three wrong implementations passed
    the revision-2 form of these cells.  Every case asserts its OWN diagnostic rather than merely
    that the case is red: several of these mutations also trip the independent observed-literal
    census, so redness alone proves reachability and not discrimination.
    """

    PREPEND = [
        b"## [9.9.9] - 2099-01-01",
        b"",
        b"### Added",
        b"",
        b"- A synthetic release section, to shift every physical line below it.",
        b"",
    ]

    @classmethod
    def setUpClass(cls):
        cls.manifest = _load_manifest()
        cls.tree = _tracked_tree()
        # Selected by LITERAL PATH, never through PREPEND_ONLY_FILES.  Deriving the fixtures from
        # the constant under test would make this class unable to see that constant being wrong —
        # the same oracle-from-the-data-under-test defect COREDEV-2798 exists to remove.  With
        # literals, emptying the constant makes these cases FAIL rather than vanish.
        cls.quote_keep = next(
            site
            for site in cls.manifest["sites"]
            if site["class"] == "quote-keep" and site["path"] == "CHANGELOG.md"
        )
        cls.rewrite = next(
            site
            for site in cls.manifest["sites"]
            if site["class"] == "rewrite" and _destination_path(site) == "README.md"
        )

    def _prepended(self, path: str) -> dict[str, list[bytes]]:
        """The real tree with a synthetic section prepended to `path` — nothing else changed."""
        mutated = dict(self.tree)
        # After the title block, exactly as a release does; the offset is irrelevant to the assertion.
        mutated[path] = list(self.PREPEND) + list(self.tree[path])
        return mutated

    def _problems_for(self, site: dict, problems: list[str]) -> list[str]:
        return [problem for problem in problems if problem.startswith(site["location"] + ":")]

    # ---- the property the ticket exists for -------------------------------------------------

    def test_baseline_real_tree_is_clean(self):
        self.assertEqual([], _tree_problems(self.manifest, self.tree))

    def test_quote_keep_survives_a_prepend_with_no_manifest_edit(self):
        path = self.quote_keep["path"]
        baseline = _quote_keep_positions(self.quote_keep, self.tree[path])
        self.assertEqual(1, len(baseline), "fixture must start from exactly one occurrence")
        mutated = self._prepended(path)
        # The literal really did move: this case would be vacuous if it had not.  Anchored to the
        # TREE's current position, never to the manifest's declared line — that line is a hint here,
        # and a test that assumes it is live cannot survive the very prepend it exists to allow.
        self.assertEqual(
            [baseline[0] + len(self.PREPEND)],
            _quote_keep_positions(self.quote_keep, mutated[path]),
        )
        self.assertEqual([], _tree_problems(self.manifest, mutated))

    def test_rewrite_destination_survives_a_prepend_with_no_manifest_edit(self):
        path = _destination_path(self.rewrite)
        baseline = _destination_occurrences(self.rewrite, self.tree[path])
        self.assertEqual(1, len(baseline), "fixture must start from exactly one occurrence")
        mutated = self._prepended(path)
        self.assertEqual(
            [baseline[0] + len(self.PREPEND)],
            _destination_occurrences(self.rewrite, mutated[path]),
        )
        self.assertEqual([], _tree_problems(self.manifest, mutated))

    # ---- cell 6: quote-keep, three wrong implementations ------------------------------------

    def test_quote_keep_content_change_is_detected(self):
        site = self.quote_keep
        mutated = dict(self.tree)
        lines = list(self.tree[site["path"]])
        position = _quote_keep_positions(site, lines)[0]
        lines[position - 1] = b"# COREDEV-2798 mutated quote-keep payload"
        mutated[site["path"]] = lines
        self.assertIn(
            f"{site['location']}: quote-keep payload hash drifted",
            _tree_problems(self.manifest, mutated),
        )

    def test_quote_keep_duplicate_source_line_is_detected(self):
        """Kills "at least one": a duplicated payload leaves the site genuinely ambiguous."""
        site = self.quote_keep
        mutated = dict(self.tree)
        lines = list(self.tree[site["path"]])
        position = _quote_keep_positions(site, lines)[0]
        lines.insert(position, lines[position - 1])
        mutated[site["path"]] = lines
        self.assertEqual(2, len(_quote_keep_positions(site, mutated[site["path"]])))
        self.assertIn(
            f"{site['location']}: quote-keep payload hash is not unique",
            _tree_problems(self.manifest, mutated),
        )

    def test_line_addressed_quote_keep_still_asserts_its_line(self):
        """The demotion is SCOPED: a non-prepend-only site keeps its line assertion."""
        site = next(
            candidate
            for candidate in self.manifest["sites"]
            if candidate["class"] == "quote-keep"
            and candidate["path"] not in ("CHANGELOG.md", "README.md")
        )
        mutated = dict(self.tree)
        mutated[site["path"]] = list(self.PREPEND) + list(self.tree[site["path"]])
        problems = self._problems_for(site, _tree_problems(self.manifest, mutated))
        self.assertIn(f"{site['location']}: quote-keep payload hash drifted", problems)

    # ---- cell 7: rewrite, three wrong implementations ---------------------------------------

    def test_rewrite_destination_payload_change_is_detected(self):
        site = self.rewrite
        path = _destination_path(site)
        mutated = dict(self.tree)
        lines = list(self.tree[path])
        start = _destination_occurrences(site, lines)[0]
        lines[start] = b"# COREDEV-2798 mutated destination payload"
        mutated[path] = lines
        self.assertIn(
            f"{site['location']}: destination payload block is missing",
            _tree_problems(self.manifest, mutated),
        )

    def test_rewrite_duplicate_destination_block_is_detected(self):
        site = self.rewrite
        path = _destination_path(site)
        mutated = dict(self.tree)
        lines = list(self.tree[path])
        start = _destination_occurrences(site, lines)[0]
        width = len(_destination_payloads(site))
        lines[start:start] = lines[start : start + width]
        mutated[path] = lines
        self.assertEqual(2, len(_destination_occurrences(site, mutated[path])))
        self.assertIn(
            f"{site['location']}: destination payload block is not unique",
            _tree_problems(self.manifest, mutated),
        )

    def test_restored_legacy_source_diagnostic_is_load_bearing(self):
        """The r3 lesson: this case ALSO reds through the independent literal census.

        Restoring a legacy source reintroduces its output literal, so the observed-literal census
        fires too and the case is red either way.  It is therefore not enough that the case is red:
        the SPECIFIC diagnostic must be emitted, AND deleting the branch that emits it must make it
        disappear.  Without the second half, deleting the assertion would leave the case red and this
        control would still "pass" — reachability mistaken for discrimination.
        """
        site = self.rewrite
        # A restored legacy source is a line carrying the retired output literal.  Its exact bytes
        # are unrecoverable from a hash, so the fixture supplies the line and the manifest copy is
        # re-pinned to it: the same two observable consequences, constructed rather than guessed.
        restored = b"Transcripts are written to /tmp/" + b"agy-out.txt by the capture wrapper."
        manifest = copy.deepcopy(self.manifest)
        mutated_site = next(
            entry for entry in manifest["sites"] if entry["location"] == site["location"]
        )
        mutated_site["sourceSha256"] = _sha256(restored)

        mutated = dict(self.tree)
        lines = list(self.tree[site["path"]])
        lines.insert(site["line"] - 1, restored)
        mutated[site["path"]] = lines
        self.assertTrue(_legacy_source_survives(mutated_site, mutated[site["path"]]))

        diagnostic = f"{site['location']}: legacy source payload survives"
        problems = _tree_problems(manifest, mutated)
        self.assertIn(diagnostic, problems)
        # The confounder is real and present, which is what makes the mutation below necessary.
        self.assertTrue(
            any("output literal survives outside the quote-keep set" in problem for problem in problems),
            "the independent literal census must also fire, or this control is not confounded",
        )

        with unittest.mock.patch.object(
            sys.modules[__name__], "_legacy_source_survives", lambda site, lines: False
        ):
            without_branch = _tree_problems(manifest, mutated)
        self.assertNotIn(diagnostic, without_branch)
        self.assertNotEqual(
            [], without_branch, "the case must stay red for its other reason"
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
