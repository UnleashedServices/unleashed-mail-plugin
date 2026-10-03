#!/usr/bin/env python3
"""COREDEV-2850 plan §6 step 3 — the JUDGE for the probe PR's observations.

Evidence under `docs/planning/evidence/` is inert unless a test names it. This module reads
`COREDEV-2850-probe-observations.json` (probe PR #103, never merged) and refuses it when it no
longer certifies the gate that ships:

* each observation's action inputs must hash to the contract's `action_inputs_digest`, under the
  pinned action — the parity judge's `inputs:` clause, because an observation made with a different
  literal certifies a gate that no longer exists;
* each run must have concluded the way its cell claims;
* a GREEN must report no new issue, and each RED must be bound to named findings of ONE category,
  so a red cannot be an infrastructure failure and a security red cannot be a lint red;
* cell 1's probe file must be the recorded reproduction of the over-reach, so green cannot mean
  "already formatted";
* the cells a never-merged PR cannot reach stay DEFERRED, never quietly closed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
RECORD_PATH = REPO / "docs/planning/evidence/COREDEV-2850-probe-observations.json"
ROLLOUT_PATH = REPO / "docs/planning/evidence/COREDEV-2780-rollout.json"
_CONTRACT = yaml.safe_load(
    (REPO / "docs/planning/COREDEV-2780-contract.yaml").read_text(encoding="utf-8")
)
ACTION_PIN = _CONTRACT["action_pin"]
EXPECTED_INPUTS_DIGEST = _CONTRACT["action_inputs_digest"]
# Hand-listed, as cell 4(d) lists them: trunk's `is_security` flag is absent from both secret
# scanners, so it cannot select this set.
SECURITY_LINTERS = frozenset({"bandit", "checkov", "gitleaks", "trufflehog", "zizmor"})
FORMATTERS = frozenset({"black", "isort", "prettier", "shfmt", "taplo"})
# observation key -> (the conclusion its cell claims, the category its red must be bound to)
EXPECTED = {
    "cell1and2b": ("success", None),
    "cell2": ("failure", "lint"),
    "cell3": ("failure", "security"),
}


def _reproduction() -> dict:
    rollout = json.loads(ROLLOUT_PATH.read_text(encoding="utf-8"))
    reproduction: dict = rollout["cell3DiffScopeControls"]["theGateDOESOverReach"][
        "reproduction"
    ]
    return reproduction


def _inputs_problems(key: str, inputs: dict) -> list[str]:
    problems = []
    canonical = inputs.get("canonical") or ""
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != inputs.get("digest"):
        problems.append(
            f"{key}: the recorded digest does not match the recorded canonical form"
        )
    elif inputs.get("digest") != EXPECTED_INPUTS_DIGEST:
        problems.append(
            f"{key}: observed under {canonical!r}, which is not what the shipped workflow now "
            "passes — re-run the probe"
        )
    if inputs.get("uses") != ACTION_PIN:
        problems.append(
            f"{key}: ran {inputs.get('uses')!r}, not the pinned {ACTION_PIN!r}"
        )
    return problems


def _red_problems(key: str, category: str, obs: dict) -> list[str]:
    problems = []
    new = (obs.get("trunkSummary") or {}).get("newIssues") or {}
    if set(new) != {category}:
        problems.append(f"{key}: new issues {new} are not {category}-only")
    findings = (obs.get("boundDiagnostic") or {}).get("findings") or []
    if not findings:
        problems.append(
            f"{key}: a red bound to no finding could be an infrastructure failure"
        )
    for finding in findings:
        linter = str(finding.get("linter", ""))
        if not (
            finding.get("path")
            and isinstance(finding.get("line"), int)
            and isinstance(finding.get("column"), int)
            and "/" in linter
        ):
            problems.append(
                f"{key}: finding {finding} names no file, line and linter ID"
            )
        if (linter.partition("/")[0] in SECURITY_LINTERS) != (category == "security"):
            problems.append(f"{key}: finding {linter} is not a {category} finding")
    return problems


def probe_problems(record: dict) -> list[str]:
    """Everything that stops the record certifying the shipped gate; empty when it does."""
    problems = []
    observations = record.get("observations") or {}
    for key, (conclusion, category) in EXPECTED.items():
        obs = observations.get(key)
        if not obs:
            problems.append(f"{key}: no observation recorded")
            continue
        problems += _inputs_problems(key, obs.get("actionInputs") or {})
        runs = obs.get("runs") or []
        if not runs:
            problems.append(f"{key}: no run recorded")
        for run in runs:
            if run.get("checkRunConclusion") != conclusion:
                problems.append(
                    f"{key}: check run {run.get('checkRunId')} concluded "
                    f"{run.get('checkRunConclusion')!r}, not {conclusion!r}"
                )
            if run.get("appSlug") != "github-actions":
                problems.append(
                    f"{key}: check run {run.get('checkRunId')} was not GitHub Actions"
                )
        if category is None:
            new = (obs.get("trunkSummary") or {}).get("newIssues")
            if new:
                problems.append(f"{key}: a GREEN observation reported new issues {new}")
        else:
            problems += _red_problems(key, category, obs)

    reproduction = _reproduction()
    cell1 = ((observations.get("cell1and2b") or {}).get("probeEdits") or {}).get(
        "cell1"
    ) or {}
    if cell1.get("path") != reproduction["file"]:
        problems.append(
            f"cell1: probed {cell1.get('path')!r}, not the recorded reproduction "
            f"{reproduction['file']!r} — green could mean 'already formatted'"
        )
    recorded = {
        name
        for line in reproduction["result"]
        for name in FORMATTERS
        if line.rstrip().endswith(name)
    }
    if not recorded or set(cell1.get("recordedPreExistingFormatterFindings") or []) != (
        recorded
    ):
        problems.append(
            f"cell1: claims pre-existing {cell1.get('recordedPreExistingFormatterFindings')}, "
            f"the reproduction records {sorted(recorded)}"
        )

    cell5 = (record.get("localObservations") or {}).get("cell5") or {}
    if not (cell5.get("hookBlocked") and cell5.get("otherChecksPassed")):
        problems.append(
            "cell5: the hook did not block the staged commit on formatting alone"
        )
    if not {f.get("linter") for f in cell5.get("findings") or []} <= FORMATTERS:
        problems.append("cell5: the hook blocked on something other than formatting")

    for cell in ("cell6", "cell2bCanaryHalf"):
        if "DEFERRED" not in str((record.get("deferred") or {}).get(cell, "")):
            problems.append(
                f"{cell}: a never-merged PR cannot reach the canary, so it must stay DEFERRED"
            )
    return problems


class TheProbeObservationsCertifyTheShippedGate(unittest.TestCase):
    """The recorded probe is accepted, and each way it could stop certifying the gate is refused."""

    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(RECORD_PATH.read_text(encoding="utf-8"))

    def _mutated(self, mutate) -> list[str]:
        record = copy.deepcopy(self.record)
        mutate(record)
        return probe_problems(record)

    def test_the_recorded_probe_is_accepted(self):
        self.assertEqual([], probe_problems(self.record))

    def test_a_record_whose_digest_does_not_match_its_canonical_form_is_refused(self):
        def mutate(r):
            r["observations"]["cell2"]["actionInputs"]["digest"] = "0" * 64

        self.assertIn(
            "cell2: the recorded digest does not match the recorded canonical form",
            self._mutated(mutate),
        )

    def test_an_observation_under_a_different_literal_is_refused(self):
        """Self-consistent but stale: the hook literal, with a digest that matches it."""

        def mutate(r):
            canonical = (
                '{"arguments":"--filter=-markdown-link-check","save-annotations":true}'
            )
            inputs = r["observations"]["cell1and2b"]["actionInputs"]
            inputs["canonical"] = canonical
            inputs["digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        self.assertTrue(
            any(
                p.startswith("cell1and2b: observed under") and "re-run the probe" in p
                for p in self._mutated(mutate)
            )
        )

    def test_a_run_of_an_unpinned_action_is_refused(self):
        def mutate(r):
            r["observations"]["cell3"]["actionInputs"][
                "uses"
            ] = "trunk-io/trunk-action@v1"

        self.assertTrue(
            any(
                p.startswith("cell3: ran 'trunk-io/trunk-action@v1'")
                for p in self._mutated(mutate)
            )
        )

    def test_a_green_cell_whose_run_failed_is_refused(self):
        def mutate(r):
            r["observations"]["cell1and2b"]["runs"][0]["checkRunConclusion"] = "failure"

        self.assertTrue(
            any(
                "concluded 'failure', not 'success'" in p for p in self._mutated(mutate)
            )
        )

    def test_a_green_that_reported_new_issues_is_refused(self):
        def mutate(r):
            r["observations"]["cell1and2b"]["trunkSummary"]["newIssues"] = {"lint": 1}

        self.assertIn(
            "cell1and2b: a GREEN observation reported new issues {'lint': 1}",
            self._mutated(mutate),
        )

    def test_a_red_bound_to_no_finding_is_refused(self):
        def mutate(r):
            r["observations"]["cell2"]["boundDiagnostic"]["findings"] = []

        self.assertIn(
            "cell2: a red bound to no finding could be an infrastructure failure",
            self._mutated(mutate),
        )

    def test_a_security_red_that_was_really_a_lint_red_is_refused(self):
        def mutate(r):
            obs = r["observations"]["cell3"]
            obs["boundDiagnostic"]["findings"][0]["linter"] = "shellcheck/SC2086"
            obs["trunkSummary"]["newIssues"] = {"lint": 1, "security": 1}

        problems = self._mutated(mutate)
        self.assertIn(
            "cell3: finding shellcheck/SC2086 is not a security finding", problems
        )
        self.assertTrue(any(p.startswith("cell3: new issues") for p in problems))

    def test_a_probe_of_a_file_that_was_not_the_recorded_reproduction_is_refused(self):
        def mutate(r):
            r["observations"]["cell1and2b"]["probeEdits"]["cell1"][
                "path"
            ] = "CHANGELOG.md"

        self.assertTrue(
            any(
                p.startswith("cell1: probed 'CHANGELOG.md'")
                for p in self._mutated(mutate)
            )
        )

    def test_a_hook_block_on_something_other_than_formatting_is_refused(self):
        def mutate(r):
            r["localObservations"]["cell5"]["findings"].append(
                {"path": "x.sh", "linter": "shellcheck/SC2086"}
            )

        self.assertIn(
            "cell5: the hook blocked on something other than formatting",
            self._mutated(mutate),
        )

    def test_the_canary_cells_cannot_be_quietly_closed(self):
        def mutate(r):
            r["deferred"]["cell6"] = "observed via the check-runs API"

        self.assertIn(
            "cell6: a never-merged PR cannot reach the canary, so it must stay DEFERRED",
            self._mutated(mutate),
        )


if __name__ == "__main__":
    unittest.main()
