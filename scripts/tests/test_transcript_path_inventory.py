#!/usr/bin/env python3
"""M3.1 drift proof for COREDEV-2619's frozen transcript-path inventory."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import unittest
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO / "docs/planning/COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json"
FROZEN_COMMIT = "78e28f26cb56572b22fe1635552dd10fa95bdb48"
EXPECTED_LITERALS = ("/tmp/" + "agy-out.txt", "/tmp/" + "codex-out.txt")
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


def _manifest_problems(manifest: dict) -> list[str]:
    problems = []
    if manifest.get("schemaVersion") != 1:
        problems.append("schemaVersion must be 1")
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
            else:
                contract_counts.update(contracts)
            for key in anchor_keys:
                if key not in site:
                    problems.append(f"{location}: rewrite lacks {key}")
            for key in ("precedingAnchorSha256", "followingAnchorSha256"):
                if key in site and not _is_sha256(site[key]):
                    problems.append(f"{location}: {key} is not lowercase SHA-256")
        elif any(key in site for key in ("contracts",) + anchor_keys):
            problems.append(f"{location}: quote-keep must not carry rewrite-only fields")

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
    exclusions = set(manifest["scanExclusions"])
    return {
        (path, line_number)
        for path, lines in tree.items()
        if path not in exclusions
        for line_number, payload in enumerate(lines, 1)
        if any(literal in payload for literal in literals)
    }


def _tree_problems(manifest: dict, tree: dict[str, list[bytes]]) -> list[str]:
    problems = []
    sites = manifest["sites"]
    expected_sites = {_site_key(site) for site in sites}
    observed_sites = _observed_literal_sites(manifest, tree)
    for path, line in sorted(expected_sites - observed_sites):
        problems.append(f"{path}:{line}: classified output literal is missing")
    for path, line in sorted(observed_sites - expected_sites):
        problems.append(f"{path}:{line}: unclassified output literal")

    rewrite_lines = {}
    for site in sites:
        if site["class"] == "rewrite":
            rewrite_lines.setdefault(site["path"], set()).add(site["line"])

    for site in sites:
        location = site["location"]
        lines = tree.get(site["path"])
        if lines is None:
            problems.append(f"{location}: classified file is missing")
            continue
        if site["line"] > len(lines):
            problems.append(f"{location}: physical line is missing")
            continue
        if _sha256(lines[site["line"] - 1]) != site["sourceSha256"]:
            problems.append(f"{location}: source payload hash drifted")
        if site["class"] != "rewrite":
            continue

        preceding = site["line"] - 1
        while preceding in rewrite_lines[site["path"]]:
            preceding -= 1
        following = site["line"] + 1
        while following in rewrite_lines[site["path"]]:
            following += 1
        if preceding != site["precedingAnchorLine"] or following != site["followingAnchorLine"]:
            problems.append(f"{location}: stored anchor lines do not bracket the frozen rewrite cluster")
            continue
        if preceding < 1 or following > len(lines):
            problems.append(f"{location}: context anchor is missing")
            continue
        if _sha256(lines[preceding - 1]) != site["precedingAnchorSha256"]:
            problems.append(f"{location}: preceding context anchor drifted")
        if _sha256(lines[following - 1]) != site["followingAnchorSha256"]:
            problems.append(f"{location}: following context anchor drifted")
    return problems


class M3_1_InventoryDrift(unittest.TestCase):
    """Freeze the pre-rewrite source identities that later steps must replace in place."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = _load_manifest()
        cls.tree = _tracked_tree()

    def test_manifest_reproduces_the_locked_section_7_inventory(self):
        self.assertEqual([], _manifest_problems(self.manifest))

    def test_current_tree_matches_every_frozen_source_identity(self):
        self.assertEqual([], _tree_problems(self.manifest, self.tree))

    def test_each_site_deletion_is_detected_at_that_identity(self):
        for site in self.manifest["sites"]:
            with self.subTest(location=site["location"]):
                mutated = dict(self.tree)
                lines = list(mutated[site["path"]])
                del lines[site["line"] - 1]
                mutated[site["path"]] = lines
                problems = _tree_problems(self.manifest, mutated)
                self.assertTrue(
                    any(problem.startswith(site["location"] + ":") for problem in problems),
                    f"deleting {site['location']} was not attributed to that identity: {problems}",
                )

    def test_each_rewrite_relocation_is_detected_with_counts_unchanged(self):
        rewrites = [site for site in self.manifest["sites"] if site["class"] == "rewrite"]
        self.assertEqual(EXPECTED_TOTALS["rewrite"], len(rewrites))
        for site in rewrites:
            with self.subTest(location=site["location"]):
                mutated = dict(self.tree)
                lines = list(mutated[site["path"]])
                moved = lines.pop(site["line"] - 1)
                lines.append(moved)
                mutated[site["path"]] = lines
                self.assertEqual(
                    len(_observed_literal_sites(self.manifest, self.tree)),
                    len(_observed_literal_sites(self.manifest, mutated)),
                )
                problems = _tree_problems(self.manifest, mutated)
                self.assertTrue(
                    any(problem.startswith(site["location"] + ":") for problem in problems),
                    f"relocating {site['location']} was not attributed to that identity: {problems}",
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
            f"SECURITY.md:{new_line}: unclassified output literal",
            _tree_problems(self.manifest, mutated),
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
