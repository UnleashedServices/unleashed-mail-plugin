#!/usr/bin/env python3
"""COREDEV-2780 cells 1 and 5 — the JUDGE for `trunk-parity-harness.yml`'s evidence.

A Python unittest cannot run a composite action: `uses:` is resolved by the Actions runner. So the
WORKFLOW is the sensor — it runs the pinned action against per-event fixtures with an instrumented
launcher and publishes the captured argv and the pre/post tree hashes — and this file is the judge.

WHAT EACH CELL NEEDS FROM THE ARTIFACT
  cell 1  the `--upstream` the action passed to Trunk must equal, BYTE FOR BYTE, what the shared
          resolver produced. Two independently correct-looking resolvers drift, and a guard that
          checks a DIFFERENT range than the one linted asserts nothing about the lint.
  cell 5  no tracked file's bytes may change, and no autofix may be applied. Narrower than "the job
          never mutates the tree", which is false — the pinned action itself creates `.trunk/setup-ci`
          and appends to `.git/info/exclude`.

THE ARTIFACT IS NOT IN THE REPOSITORY UNTIL THE HARNESS HAS RUN. M2c is not complete until a real run
on `harness-base` / `harness/**` produces one and it is accepted against this schema. Until then the
schema and discrimination tests below run against synthetic records, and the acceptance test SKIPS
rather than passing vacuously — a cell that silently passes with no evidence is exactly the sink this
plan keeps repairing.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO / "docs/planning/evidence"
ARGUMENTS_LITERAL = "--filter=-markdown-link-check"


def parity_problems(record: dict) -> list[str]:
    """Cells 1 and 5 against one harness record. Diagnostics, so each case dies for its own reason."""
    problems: list[str] = []

    if record.get("schemaVersion") != 1:
        problems.append("schema: unexpected schemaVersion")
    event = record.get("event")
    if event not in ("pull_request", "push"):
        problems.append(f"schema: unsupported event {event!r}")

    raw = (record.get("resolver") or {}).get("raw", "")
    if not raw.startswith("upstream="):
        problems.append("resolver: did not emit an `upstream=` line")
        resolved = None
    else:
        resolved = raw[len("upstream=") :].strip()
        if not resolved:
            problems.append("resolver: emitted an empty upstream")

    invocations = record.get("invocations") or []
    if not invocations:
        problems.append("argv: the launcher recorded no invocation at all")
    # `locate_trunk.sh` calls the launcher once as `<launcher> version` before the check, so the check
    # is selected by its argv rather than by assuming a single invocation.
    checks = [argv for argv in invocations if argv and argv[0] == "check"]
    if len(checks) != 1:
        problems.append(
            f"argv: expected exactly one `check` invocation, found {len(checks)}"
        )
    else:
        argv = checks[0]
        if "--all" in argv:
            # push.sh's zero-`before` branch. A whole-tree run is the 9027-finding gate §1 forbids.
            problems.append("argv: the action ran `--all`")
        if "--fix" in argv:
            problems.append("argv: the action ran `--fix`")
        if "--upstream" not in argv:
            problems.append("argv: the action passed no `--upstream`")
        elif resolved is not None:
            passed = argv[argv.index("--upstream") + 1]
            if passed != resolved:
                # THE PARITY ASSERTION. Byte-for-byte, not "both look like a SHA".
                problems.append(
                    f"parity: the action linted {passed!r} while the guard resolved {resolved!r}"
                )
        if ARGUMENTS_LITERAL not in argv:
            problems.append(
                "argv: §6.4's declared exclusion did not reach the command line"
            )

    tree = record.get("tree") or {}
    problems.extend(
        f"tree: `{key}` is missing"
        for key in ("pre", "post", "fixturePre", "fixturePost")
        if not tree.get(key)
    )
    if tree.get("pre") and tree.get("post") and tree["pre"] != tree["post"]:
        problems.append("cell 5: a tracked file's bytes changed during the run")
    if (
        tree.get("fixturePre")
        and tree.get("fixturePost")
        and tree["fixturePre"] != tree["fixturePost"]
    ):
        problems.append(
            "cell 5: the deliberately-fixable fixture was rewritten — autofix is enabled"
        )

    inputs = record.get("actionInputs") or {}
    if not inputs.get("digest"):
        problems.append("inputs: the harness recorded no action-input digest")
    if "trunk-io/trunk-action@" not in inputs.get("uses", ""):
        problems.append("inputs: the harness did not record which action it ran")

    return problems


def _clean_record(event: str = "pull_request") -> dict:
    upstream = "a" * 40
    return {
        "schemaVersion": 1,
        "event": event,
        "ref": "harness-base",
        "sha": "b" * 40,
        "resolver": {"raw": f"upstream={upstream}"},
        "invocations": [
            ["version"],
            [
                "check",
                "--ci",
                "--upstream",
                upstream,
                "--github-commit",
                "c" * 40,
                "--github-annotate-file=/tmp/x",
                ARGUMENTS_LITERAL,
            ],
        ],
        "tree": {
            "pre": "t1",
            "post": "t1",
            "fixture": "harness-fixtures/fixable.sh",
            "fixturePre": "f1",
            "fixturePost": "f1",
        },
        "actionInputs": {
            "canonical": "{}",
            "digest": "d" * 64,
            "uses": "trunk-io/trunk-action@" + "e" * 40,
        },
    }


class TheJudgeDiscriminates(unittest.TestCase):
    """Every wrong implementation the harness exists to catch, and its own diagnostic."""

    def test_a_clean_record_is_a_passing_positive_control(self):
        self.assertEqual([], parity_problems(_clean_record()))

    def test_a_range_mismatch_is_the_cell_1_failure(self):
        """The guard checking a different range than the action lints is the whole point."""
        record = _clean_record()
        record["invocations"][1][3] = "9" * 40
        problems = parity_problems(record)
        self.assertTrue(any(p.startswith("parity:") for p in problems), problems)

    def test_an_all_run_is_caught(self):
        record = _clean_record("push")
        record["invocations"][1].append("--all")
        self.assertIn("argv: the action ran `--all`", parity_problems(record))

    def test_an_autofix_run_is_caught_twice_over(self):
        """Once by the argv and once by the fixture bytes — the positive control cell 5 requires."""
        record = _clean_record()
        record["invocations"][1].append("--fix")
        record["tree"]["fixturePost"] = "f2"
        record["tree"]["post"] = "t2"
        problems = parity_problems(record)
        self.assertIn("argv: the action ran `--fix`", problems)
        self.assertIn(
            "cell 5: the deliberately-fixable fixture was rewritten — autofix is enabled",
            problems,
        )
        self.assertIn("cell 5: a tracked file's bytes changed during the run", problems)

    def test_a_recorder_that_never_delegated_is_not_mistaken_for_a_clean_tree(self):
        """A record-and-exit launcher leaves the fixture trivially unchanged. It is caught because the
        harness must show a `check` invocation carrying the declared exclusion — a fixture that is
        unchanged because NOTHING RAN is the sink problem wearing a different hat."""
        record = _clean_record()
        record["invocations"] = [["version"]]
        problems = parity_problems(record)
        self.assertTrue(
            any("expected exactly one `check` invocation" in p for p in problems),
            problems,
        )

    def test_a_missing_upstream_is_caught(self):
        record = _clean_record()
        record["invocations"][1] = ["check", "--ci", ARGUMENTS_LITERAL]
        self.assertIn(
            "argv: the action passed no `--upstream`", parity_problems(record)
        )

    def test_a_dropped_exclusion_literal_is_caught(self):
        record = _clean_record()
        record["invocations"][1].remove(ARGUMENTS_LITERAL)
        self.assertIn(
            "argv: §6.4's declared exclusion did not reach the command line",
            parity_problems(record),
        )

    def test_an_empty_resolver_output_is_caught(self):
        record = _clean_record()
        record["resolver"]["raw"] = ""
        self.assertIn(
            "resolver: did not emit an `upstream=` line", parity_problems(record)
        )


class TheResolverNeedsOnlyWhatGitHubProvides(unittest.TestCase):
    """REGRESSION: the guard runs OUTSIDE the action and gets none of the action's variables.

    The first real PR run failed here. `pull_request.sh` reads
    `GITHUB_EVENT_PULL_REQUEST_NUMBER`, which is NOT a GitHub-provided variable -- `action.yaml`
    SYNTHESISES it from `github.event.pull_request.number` for the scripts it runs. The resolver
    transcribed the action's LOGIC faithfully and inherited an ENVIRONMENT that is not there, so it
    fell through to the base-SHA fallback, found that unset too, and failed closed on every PR.

    C5 forbids an `env:` block in the shipped workflows, so supplying the action's variables was never
    an available fix. These cases therefore run the resolver with ONLY what GitHub gives every step.
    """

    RESOLVER = REPO / "scripts/ci/resolve-trunk-range.sh"

    def _fixture(self, tmp):
        """A repo whose HEAD is a merge commit, as `refs/pull/N/merge` is."""
        root = Path(tmp)

        def run(*args):
            subprocess.run(
                ["git", "-C", str(root), *args], check=True, capture_output=True
            )

        run("init", "-q", "-b", "main", ".")
        run("config", "user.email", "t@t")
        run("config", "user.name", "t")
        (root / "f").write_text("base\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "base")
        run("checkout", "-qb", "topic")
        (root / "f").write_text("base\nchange\n", encoding="utf-8")
        run("commit", "-qam", "change")
        run("checkout", "-q", "main")
        (root / "g").write_text("other\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "other")
        run("merge", "-q", "--no-ff", "topic", "-m", "merge")
        return root

    def _resolve(self, root, **env):
        environment = {"PATH": os.environ["PATH"], "HOME": str(root)}
        environment.update(env)
        return subprocess.run(
            ["bash", str(self.RESOLVER)],
            check=False,
            cwd=str(root),
            capture_output=True,
            text=True,
            env=environment,
        )

    def test_a_pull_request_resolves_with_no_action_supplied_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            expected = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD^1"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            completed = self._resolve(
                root, GITHUB_EVENT_NAME="pull_request", GITHUB_REF_NAME="84/merge"
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("upstream=" + expected, completed.stdout.strip())

    def test_the_merge_ref_is_detected_by_pattern_not_by_the_pr_number(self):
        """Any `<n>/merge` works, because the number itself is never needed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            for ref in ("1/merge", "84/merge", "99999/merge"):
                with self.subTest(ref=ref):
                    completed = self._resolve(
                        root, GITHUB_EVENT_NAME="pull_request", GITHUB_REF_NAME=ref
                    )
                    self.assertEqual(0, completed.returncode)
                    self.assertTrue(completed.stdout.startswith("upstream="))

    def test_a_zero_before_push_still_fails_closed(self):
        """The branch that would send the action down its `--all` path."""
        with tempfile.TemporaryDirectory() as tmp:
            completed = self._resolve(
                self._fixture(tmp),
                GITHUB_EVENT_NAME="push",
                GITHUB_REF_NAME="main",
                GITHUB_EVENT_BEFORE="0" * 40,
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("--all", completed.stderr)

    def test_unsupported_events_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            for event in ("workflow_dispatch", "merge_group", "schedule"):
                with self.subTest(event=event):
                    completed = self._resolve(root, GITHUB_EVENT_NAME=event)
                    self.assertNotEqual(0, completed.returncode)
                    self.assertIn("unsupported event", completed.stderr)


class TheHarnessEvidenceIsAcceptedAgainstTheSchema(unittest.TestCase):
    """M2c's acceptance step. SKIPS until a real run has produced evidence — never passes vacuously."""

    def test_every_recorded_parity_artifact_is_clean(self):
        records = (
            sorted(EVIDENCE_DIR.glob("parity-*.json")) if EVIDENCE_DIR.exists() else []
        )
        if not records:
            self.skipTest(
                "no parity evidence yet — M2c is not complete until the harness has run on "
                "`harness-base` / `harness/**` and its artifact is committed under "
                "docs/planning/evidence/. Cells 1 and 5 stay unowned until then."
            )
        seen = set()
        for path in records:
            with self.subTest(evidence=path.name):
                record = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual([], parity_problems(record))
                seen.add(record["event"])
        # Both event paths through the pinned action must be exercised: they take different branches.
        self.assertEqual(
            {"pull_request", "push"},
            seen,
            "both event paths must be observed — they resolve their ranges differently",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
