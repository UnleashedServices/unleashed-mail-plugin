#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-FRESH proof pairs and closed M4 matrix."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import itertools
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


REPO = Path(__file__).resolve().parents[2]
VERDICT_PATH = REPO / "scripts" / "review-verdict.py"
ALLOCATOR_PATH = REPO / "scripts" / "pty-capture.py"

MUTATION_KINDS = (
    "timing-negative",
    "timing-positive",
    "mtime-equality",
    "absent",
    "mismatched",
    "empty",
    "malformed",
    "record-precedes-dispatch",
    "sidecar-varied",
)
DIGEST_PATHS = ("snapshot-sidecar", "reviewed-sha256")
TRANSCRIPT_POSITIONS = ("FIRST", "SECOND")
M4_CASES = tuple(
    itertools.product(MUTATION_KINDS, DIGEST_PATHS, TRANSCRIPT_POSITIONS)
)
M4_TOTAL = (
    len(MUTATION_KINDS) * len(DIGEST_PATHS) * len(TRANSCRIPT_POSITIONS)
)

ACCEPTED_KINDS = {
    "timing-positive",
    "mtime-equality",
    "record-precedes-dispatch",
    "sidecar-varied",
}
RUN_IDS = (
    "0123456789abcdef0123456789abcdef",
    "fedcba9876543210fedcba9876543210",
)
BASE_MTIME_NS = 1_700_000_000_000_000_000
MALFORMED_RECORDS = (
    RUN_IDS[0].upper().encode("ascii") + b" gemini\n",
    RUN_IDS[0].encode("ascii") + b" gemini",
    RUN_IDS[0].encode("ascii") + b" gemini\ntrailing",
    RUN_IDS[0].encode("ascii") + b" gemini\n" + RUN_IDS[0].encode("ascii") + b" gemini\n",
    b"abc\n",
    b"g" * len(RUN_IDS[0]) + b" gemini\n",
)


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise AssertionError("mutation anchor must occur exactly once: " + repr(old))
    return source.replace(old, new, 1)


def _verdict_module():
    """The SHIPPED `review-verdict.py`, so fixtures derive a plan identity instead of restating one."""
    return _load_module(VERDICT_PATH, "verdict-identity")


def _load_module(path: Path, label: str):
    module_name = "m4_" + "".join(
        character if character.isalnum() else "_" for character in label
    )
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise AssertionError("could not load allocator module " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def write_prompt_binding(transcript) -> None:
    """Write the `.prompt` snapshot and `.promptsha256` that `bind-prompt.py` produces alongside `.plan`.

    `write` REQUIRES the prompt binding for a per-run transcript rather than skipping when it is
    absent — skipping meant deleting the sidecar turned the check off, the same "absent means
    unchecked" fail-open the plan binding exists to close (PR #63 recheck). All three sidecars are
    written together by the capture helper, so a fixture producing only `.plan` models a transcript no
    helper ever made.
    """
    payload = b"review prompt\n"
    Path(str(transcript) + ".prompt").write_bytes(payload)
    Path(str(transcript) + ".promptsha256").write_text(
        hashlib.sha256(payload).hexdigest() + "  prompt.md\n", encoding="utf-8"
    )


class _MarkerObserver(io.StringIO):
    """Asserts the reopened record before the marker, using the ALLOCATOR'S OWN grammar.

    The expected bytes are not spelled out here: the record is matched with the module's compiled
    `_LAUNCH_RECORD_RE` and its groups compared to the run id and reviewer this allocation was asked
    for. Restating the layout would make this observer fail on a grammar change instead of on the
    ordering property it exists to prove.
    """

    def __init__(
        self,
        test: unittest.TestCase,
        expected_run_id: str,
        expected_reviewer: str,
        record_grammar,
    ) -> None:
        super().__init__()
        self.test = test
        self.expected_run_id = expected_run_id
        self.expected_reviewer = expected_reviewer
        self.record_grammar = record_grammar
        self.marker_paths = []  # type: List[Path]
        self.events = []  # type: List[str]
        self.real_open = os.open
        self.real_close = os.close

    def write(self, value: str) -> int:
        marker = "UNLEASHED_TRANSCRIPT="
        if value.startswith(marker):
            transcript = Path(value[len(marker):].rstrip("\n"))
            launch = Path(str(transcript) + ".launch")
            self.events.append("marker")
            self.test.assertTrue(
                launch.is_file(),
                "the launch record must exist before the allocation marker permits dispatch",
            )
            descriptor = self.real_open(
                str(launch),
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                payload = os.read(descriptor, 128)
            finally:
                self.real_close(descriptor)
            match = self.record_grammar.fullmatch(payload)
            self.test.assertIsNotNone(
                match,
                "the owner must be able to reopen the closed, run-bound record before dispatch; "
                "what it read does not satisfy the allocator's own grammar: " + repr(payload),
            )
            self.test.assertEqual(
                (self.expected_run_id, self.expected_reviewer),
                (match.group(1).decode("ascii"), match.group(2).decode("ascii")),
                "the reopened record must bind THIS run and THIS reviewer",
            )
            self.marker_paths.append(transcript)
        return super().write(value)


class FreshnessFixture(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(
            prefix=".m4-freshness-proof-",
            dir=str(REPO),
        )
        self.root = Path(self.temporary.name)
        self.verdict_source = VERDICT_PATH.read_text(encoding="utf-8")
        self.allocator_source = ALLOCATOR_PATH.read_text(encoding="utf-8")
        self.case_number = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def next_case_root(self, label: str) -> Path:
        self.case_number += 1
        root = self.root / (str(self.case_number) + "-" + label)
        root.mkdir(parents=True)
        return root

    def write_script(self, source: str, label: str, filename: str) -> Path:
        directory = self.root / ("source-" + label)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        path.write_text(source, encoding="utf-8")
        return path

    @staticmethod
    def invoke(
        script: Path,
        args: Sequence[str],
        extra_environment: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        environment = dict(os.environ)
        if extra_environment:
            environment.update(extra_environment)
        return subprocess.run(
            [sys.executable, str(script)] + list(args),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def set_mtime_ns(self, path: Path, value: int) -> None:
        os.utime(str(path), ns=(value, value))
        self.assertEqual(
            value,
            path.stat().st_mtime_ns,
            "the proof filesystem must preserve the requested nanosecond boundary",
        )

    def create_transcript(
        self,
        parent: Path,
        reviewer: str,
        run_id: str,
        content: bytes,
    ) -> Path:
        parent.mkdir(parents=True, exist_ok=True)
        # The real allocator requires each shared state-directory component to be private. A manual
        # companion transcript must preserve that invariant when the other reviewer is allocator-driven.
        os.chmod(parent, 0o700)
        os.chmod(parent.parent, 0o700)
        os.chmod(parent.parent.parent, 0o700)
        path = parent / ("COREDEV-2619r9-" + reviewer + "-" + run_id + ".txt")
        path.write_bytes(content)
        launch = Path(str(path) + ".launch")
        # `<run id> <reviewer>` — the allocator records the reviewer so the gate reads the identity
        # from evidence the caller did not write (PR #63 recheck, P1).
        launch.write_bytes((run_id + " " + reviewer + "\n").encode("ascii"))
        os.chmod(path, 0o600)
        os.chmod(launch, 0o600)
        # Equality is the neutral valid baseline: comparator-polarity mutants aimed at the selected
        # reviewer cannot be rejected accidentally by the untouched companion reviewer.
        self.set_mtime_ns(launch, BASE_MTIME_NS + 150_000_000)
        self.set_mtime_ns(path, BASE_MTIME_NS + 150_000_000)
        return path

    def allocate_with_observer(
        self,
        source: str,
        case_root: Path,
        reviewer: str,
        run_id: str,
        label: str,
    ) -> Path:
        script = self.write_script(source, "allocator-" + label, "pty-capture.py")
        module = _load_module(script, "allocator_" + label + "_" + str(self.case_number))
        module._generate_run_id = lambda: run_id

        home = case_root / "home"
        state = case_root / "state"
        home.mkdir(mode=0o700)
        environment = {
            "HOME": str(home),
            "XDG_STATE_HOME": str(state),
        }
        observer = _MarkerObserver(self, run_id, reviewer, module._LAUNCH_RECORD_RE)
        events = observer.events
        launch_descriptors = set()
        launch_create_flags = []  # type: List[int]
        real_open = os.open
        real_close = os.close

        def open_spy(path, flags, mode=0o777, *args, **kwargs):
            descriptor = real_open(path, flags, mode, *args, **kwargs)
            path_string = os.fsdecode(path)
            if path_string.endswith(".launch"):
                if flags & os.O_CREAT:
                    events.append("launch-create")
                    launch_descriptors.add(descriptor)
                    launch_create_flags.append(flags)
                else:
                    events.append("launch-reopen")
            return descriptor

        def close_spy(descriptor):
            if descriptor in launch_descriptors:
                events.append("launch-close")
                launch_descriptors.remove(descriptor)
            return real_close(descriptor)

        argv = [
            "--allocate",
            "--repo-hash",
            "RepoHash09",
            "--ticket",
            "COREDEV-2619",
            "--round",
            "9",
            "--reviewer",
            reviewer,
        ]
        with mock.patch.object(module.os, "open", open_spy), mock.patch.object(
            module.os, "close", close_spy
        ), contextlib.redirect_stdout(observer):
            status = module.cli_main(argv, environ=environment)

        self.assertEqual(0, status)
        self.assertEqual(1, len(observer.marker_paths), observer.getvalue())
        self.assertEqual(1, len(launch_create_flags), events)
        self.assertTrue(launch_create_flags[0] & os.O_EXCL, events)
        self.assertFalse(launch_create_flags[0] & os.O_TRUNC, events)
        self.assertLess(events.index("launch-create"), events.index("launch-close"))
        self.assertLess(events.index("launch-close"), events.index("launch-reopen"))
        self.assertLess(events.index("launch-reopen"), events.index("marker"))
        return observer.marker_paths[0]

    def configure_kind(
        self,
        kind: str,
        transcript: Path,
        run_id: str,
        malformed_payload: Optional[bytes],
    ) -> None:
        launch = Path(str(transcript) + ".launch")
        if kind == "timing-negative":
            self.set_mtime_ns(transcript, BASE_MTIME_NS + 100_000_000)
            self.set_mtime_ns(launch, BASE_MTIME_NS + 200_000_000)
        elif kind == "timing-positive":
            self.set_mtime_ns(launch, BASE_MTIME_NS + 100_000_000)
            self.set_mtime_ns(transcript, BASE_MTIME_NS + 200_000_000)
        elif kind == "mtime-equality":
            self.set_mtime_ns(launch, BASE_MTIME_NS + 150_000_000)
            self.set_mtime_ns(transcript, BASE_MTIME_NS + 150_000_000)
        elif kind == "absent":
            launch.unlink()
        elif kind == "mismatched":
            other = RUN_IDS[1] if run_id == RUN_IDS[0] else RUN_IDS[0]
            # Reviewer field retained: this cell isolates a mismatched RUN ID, and dropping the
            # field would make it a malformed-record case testing a different rule.
            launch.write_bytes((other + " " + transcript.name.split("-")[2] + "\n").encode("ascii"))
            self.set_mtime_ns(launch, BASE_MTIME_NS + 100_000_000)
        elif kind == "empty":
            launch.write_bytes(b"")
            self.set_mtime_ns(launch, BASE_MTIME_NS + 100_000_000)
        elif kind == "malformed":
            if malformed_payload is None:
                raise AssertionError("malformed cells require an explicit payload")
            launch.write_bytes(malformed_payload)
            self.set_mtime_ns(launch, BASE_MTIME_NS + 100_000_000)
        elif kind in ("record-precedes-dispatch", "sidecar-varied"):
            self.set_mtime_ns(launch, BASE_MTIME_NS + 100_000_000)
            self.set_mtime_ns(transcript, BASE_MTIME_NS + 200_000_000)
        else:
            raise AssertionError("unknown M4 mutation kind: " + kind)

    def run_matrix_cell(
        self,
        verdict_script: Path,
        kind: str,
        digest_path: str,
        position: str,
        allocator_source: Optional[str] = None,
        malformed_payload: Optional[bytes] = None,
        sidecar_offset_ns: int = 300_000_000,
    ) -> subprocess.CompletedProcess:
        label = "-".join((kind, digest_path, position.lower()))
        case_root = self.next_case_root(label)
        plan = case_root / "COREDEV-2619_PLAN.md"
        plan.write_text("# Plan\nS-FRESH proof bytes.\n", encoding="utf-8")
        transcript_parent = (
            case_root
            / "state"
            / "unleashed-mail"
            / "review-transcripts"
            / "RepoHash09"
        )

        transcripts = []  # type: List[Path]
        reviewers = ("gemini", "codex")
        target_index = TRANSCRIPT_POSITIONS.index(position)
        for index, reviewer in enumerate(reviewers):
            content = (
                reviewer + " distinct review body\nVERDICT: APPROVE\n"
            ).encode("utf-8")
            if kind == "record-precedes-dispatch" and index == target_index:
                transcript = self.allocate_with_observer(
                    self.allocator_source if allocator_source is None else allocator_source,
                    case_root,
                    reviewer,
                    RUN_IDS[index],
                    label,
                )
                transcript.write_bytes(content)
            else:
                transcript = self.create_transcript(
                    transcript_parent,
                    reviewer,
                    RUN_IDS[index],
                    content,
                )
            transcripts.append(transcript)

        # Every per-run transcript now carries a `.plan` binding — the capture helpers write it, and
        # `write` refuses an APPROVING verdict without one. These cells are about the LAUNCH record,
        # so give each transcript a valid binding and let the kind under test be the only variable.
        plan_digest = hashlib.sha256(plan.read_bytes()).hexdigest()
        # The identity is DERIVED from the module under test, never restated as `plan.name`. The bare
        # basename used to be accepted because the binding comparison exempted separator-free records —
        # an exemption that also let a transcript bound to one root-level plan approve another with the
        # same bytes, so it was removed (PR #63 recheck). Restating the identity here would make these
        # cells fail on the BINDING instead of on the launch record they exist to test, which is the
        # "a new check steals a more specific rule's diagnostic" trap this file has hit before.
        plan_identity, _kind = _verdict_module()._plan_identity(str(plan))
        for transcript in transcripts:
            Path(str(transcript) + ".plan").write_text(
                f"{plan_digest}  {plan_identity}\n", encoding="utf-8"
            )
            write_prompt_binding(transcript)

        self.configure_kind(
            kind,
            transcripts[target_index],
            RUN_IDS[target_index],
            malformed_payload,
        )

        snapshot_needed = digest_path == "snapshot-sidecar" or kind == "sidecar-varied"
        if snapshot_needed:
            snapshot = self.invoke(verdict_script, ["snapshot", "--plan", str(plan)])
            self.assertEqual(0, snapshot.returncode, snapshot.stderr)

        sidecar = (
            plan.parent
            / ".verdicts"
            / (plan.name + ".reviewed-sha256")
        )
        if kind == "sidecar-varied":
            self.assertTrue(sidecar.is_file())
            self.set_mtime_ns(sidecar, BASE_MTIME_NS + sidecar_offset_ns)

        args = [
            "write",
            "--plan",
            str(plan),
            "--verdict",
            "APPROVE",
        ]
        for reviewer, transcript in zip(reviewers, transcripts):
            args.extend(
                ["--reviewer", reviewer + "=APPROVE:" + str(transcript)]
            )
        if digest_path == "reviewed-sha256":
            args.extend(
                ["--reviewed-sha256", hashlib.sha256(plan.read_bytes()).hexdigest()]
            )
        return self.invoke(
            verdict_script,
            args,
            {"M4_PLAN": str(plan)},
        )

    def assert_matrix_cell(
        self,
        verdict_script: Path,
        kind: str,
        digest_path: str,
        position: str,
        allocator_source: Optional[str] = None,
        malformed_payload: Optional[bytes] = None,
        sidecar_offset_ns: int = 300_000_000,
    ) -> None:
        result = self.run_matrix_cell(
            verdict_script,
            kind,
            digest_path,
            position,
            allocator_source=allocator_source,
            malformed_payload=malformed_payload,
            sidecar_offset_ns=sidecar_offset_ns,
        )
        output = result.stdout + result.stderr
        if kind in ACCEPTED_KINDS:
            self.assertEqual(0, result.returncode, output)
        else:
            self.assertNotEqual(0, result.returncode, output)

    def assert_real_kind(self, kind: str) -> None:
        malformed_payloads = MALFORMED_RECORDS if kind == "malformed" else (None,)
        sidecar_offsets = (
            (50_000_000, 200_000_000, 300_000_000)
            if kind == "sidecar-varied"
            else (300_000_000,)
        )
        for digest_path in DIGEST_PATHS:
            for position in TRANSCRIPT_POSITIONS:
                for malformed_payload in malformed_payloads:
                    for sidecar_offset in sidecar_offsets:
                        with self.subTest(
                            kind=kind,
                            digest=digest_path,
                            position=position,
                            malformed=malformed_payload,
                            sidecar_offset=sidecar_offset,
                        ):
                            self.assert_matrix_cell(
                                VERDICT_PATH,
                                kind,
                                digest_path,
                                position,
                                malformed_payload=malformed_payload,
                                sidecar_offset_ns=sidecar_offset,
                            )

    def assert_verdict_mutations_rejected(
        self,
        kind: str,
        mutations: Iterable[Tuple[str, str]],
    ) -> None:
        malformed_payload = MALFORMED_RECORDS[0] if kind == "malformed" else None
        for mutation_label, source in mutations:
            script = self.write_script(
                source,
                "verdict-" + mutation_label,
                "review-verdict.py",
            )
            for digest_path in DIGEST_PATHS:
                for position in TRANSCRIPT_POSITIONS:
                    with self.subTest(
                        mutation=mutation_label,
                        digest=digest_path,
                        position=position,
                    ):
                        with self.assertRaises(AssertionError):
                            self.assert_matrix_cell(
                                script,
                                kind,
                                digest_path,
                                position,
                                malformed_payload=malformed_payload,
                            )

    def verdict_mutations(self, kind: str) -> List[Tuple[str, str]]:
        source = self.verdict_source
        if kind == "timing-negative":
            return [
                (
                    "older-polarity-flipped",
                    _replace_once(
                        source,
                        "    if transcript_mtime_ns < launch_mtime_ns:\n",
                        "    if transcript_mtime_ns > launch_mtime_ns:\n",
                    ),
                ),
                (
                    "integer-second-comparison",
                    _replace_once(
                        source,
                        "    transcript_mtime_ns = transcript_info.st_mtime_ns\n"
                        "    launch_mtime_ns = launch_info.st_mtime_ns\n",
                        "    transcript_mtime_ns = int(transcript_info.st_mtime)\n"
                        "    launch_mtime_ns = int(launch_info.st_mtime)\n",
                    ),
                ),
            ]
        if kind == "timing-positive":
            return [
                (
                    "newer-rejected",
                    _replace_once(
                        source,
                        "    if transcript_mtime_ns < launch_mtime_ns:\n",
                        "    if transcript_mtime_ns != launch_mtime_ns:\n",
                    ),
                )
            ]
        if kind == "mtime-equality":
            return [
                (
                    "equality-rejected",
                    _replace_once(
                        source,
                        "    if transcript_mtime_ns < launch_mtime_ns:\n",
                        "    if transcript_mtime_ns <= launch_mtime_ns:\n",
                    ),
                )
            ]
        record_error_anchor = {
            "absent": (
                "        return None, None, None, \"launch record is absent: \" + launch_path\n",
                "absent-accepted",
            ),
            "empty": (
                "                return None, None, None, \"launch record is EMPTY: \" + launch_path\n",
                "empty-record-accepted",
            ),
            "malformed": (
                "                return None, None, None, \"launch record is malformed: \" + launch_path\n",
                "malformed-record-accepted",
            ),
        }
        if kind in record_error_anchor:
            anchor, label = record_error_anchor[kind]
            indentation = anchor[: len(anchor) - len(anchor.lstrip())]
            # The mutant synthesises BOTH record fields from the FILENAME — which is precisely the
            # defect the reviewer field exists to close, and is what makes this a fail-open rather
            # than a crash. Synthesising only the run id would leave the reviewer `None`, and the
            # identity check downstream would kill the mutant on a rule this cell is not testing.
            fake_success = (
                indentation
                + "return (\n"
                + indentation
                + "    _TRANSCRIPT_RUN_ID.search(\n"
                + indentation
                + "        os.path.basename(launch_path[:-len(\".launch\")])\n"
                + indentation
                + "    ).group(1),\n"
                + indentation
                + "    _ALLOCATOR_BASENAME.match(\n"
                + indentation
                + "        os.path.basename(launch_path[:-len(\".launch\")])\n"
                + indentation
                + "    ).group(\"reviewer\"),\n"
                + indentation
                + "    os.stat(launch_path[:-len(\".launch\")]),\n"
                + indentation
                + "    None,\n"
                + indentation
                + ")\n"
            )
            return [(label, _replace_once(source, anchor, fake_success))]
        if kind == "mismatched":
            anchor = (
                "        return \"launch record run ID does not match transcript filename: \" "
                "+ launch_path, None\n"
            )
            return [
                (
                    "mismatch-accepted",
                    _replace_once(source, anchor, "        return None, None\n"),
                )
            ]
        if kind == "sidecar-varied":
            return [
                (
                    "snapshot-sidecar-used-as-anchor",
                    _replace_once(
                        source,
                        "    launch_mtime_ns = launch_info.st_mtime_ns\n",
                        "    launch_mtime_ns = os.stat(\n"
                        "        _reviewed_sha_sidecar(os.environ[\"M4_PLAN\"])\n"
                        "    ).st_mtime_ns\n",
                    ),
                )
            ]
        raise AssertionError("no verdict mutation for " + kind)


class M4ClosedMatrixProofs(FreshnessFixture):
    def assert_closed_matrix(
        self,
        mutation_kinds: Sequence[str],
        cases: Sequence[Tuple[str, str, str]],
    ) -> None:
        expected = set(
            itertools.product(MUTATION_KINDS, DIGEST_PATHS, TRANSCRIPT_POSITIONS)
        )
        derived_total = (
            len(mutation_kinds)
            * len(DIGEST_PATHS)
            * len(TRANSCRIPT_POSITIONS)
        )
        self.assertEqual(set(MUTATION_KINDS), set(mutation_kinds))
        self.assertEqual(expected, set(cases))
        self.assertEqual(derived_total, len(cases))
        self.assertEqual(len(cases), len(set(cases)))

    def test_M4_matrix_assertion_is_the_closed_derived_cross_product(self) -> None:
        self.assertEqual(M4_TOTAL, len(M4_CASES))
        self.assert_closed_matrix(MUTATION_KINDS, M4_CASES)

    def test_every_mutation_kind_is_actually_exercised_by_a_test(self) -> None:
        """The matrix test above asserts ALGEBRA over constants and drives no execution.

        `M4_TOTAL == len(M4_CASES)` and the cross-product equality hold no matter whether any cell
        ever runs, so DELETING a kind's proof class — or letting it silently skip — leaves the
        matrix green while its cells stop being exercised (PR #63 review, gap 22). Bind the
        enumeration to the tests that consume it: every kind in MUTATION_KINDS must appear as an
        argument to one of the kind-driving helpers somewhere in this module.

        Read statically from this file's own AST rather than by running the suite, because the
        failure mode being caught is a test that no longer runs — a dynamic probe would simply not
        observe it.
        """
        import ast as _ast

        source = Path(__file__).read_text(encoding="utf-8")
        exercised = set()
        for node in _ast.walk(_ast.parse(source)):
            if not isinstance(node, _ast.Call):
                continue
            function = node.func
            if not isinstance(function, _ast.Attribute):
                continue
            if function.attr not in (
                "assert_real_kind",
                "assert_verdict_mutations_rejected",
                "verdict_mutations",
            ):
                continue
            for argument in node.args:
                if isinstance(argument, _ast.Constant) and isinstance(argument.value, str):
                    exercised.add(argument.value)

        self.assertEqual(
            set(MUTATION_KINDS),
            exercised & set(MUTATION_KINDS),
            "a kind in MUTATION_KINDS is no longer exercised by any test in this module",
        )
        self.assertFalse(
            exercised - set(MUTATION_KINDS),
            "a test drives a kind that is not in MUTATION_KINDS, so the matrix understates coverage",
        )

    def test_no_mutation_kind_is_silently_skipped_at_runtime(self) -> None:
        """The other half of the same failure mode — and the half the AST check cannot see.

        `test_every_mutation_kind_is_actually_exercised_by_a_test` reads this module's AST, so it
        catches a kind whose proof class was DELETED. It cannot catch a class that still exists and
        skips at runtime: the string literal is still there, so the kind still looks exercised.
        Verified blind — decorating a kind's class with `@unittest.skip` left the whole suite green.

        Gap 22 named "a deleted OR SKIPPED kind", so closing only the deletion half and calling it
        closed was the same error the fix was meant to prevent.

        Runs the kind-driving classes in-process and asserts none of their tests skipped. Note a
        skip is legitimate elsewhere in this repo (the zsh-agreement test skips where zsh is absent),
        so this is deliberately scoped to the M4 kind proofs rather than a blanket no-skip rule.
        """
        import unittest as _unittest

        module = sys.modules[__name__]
        loader = _unittest.TestLoader()
        suite = _unittest.TestSuite()
        for name in dir(module):
            candidate = getattr(module, name)
            if not isinstance(candidate, type) or not issubclass(candidate, _unittest.TestCase):
                continue
            if candidate is type(self) or not name.startswith(("M4", "SFresh")):
                continue          # exclude this class, or the run would recurse into itself
            suite.addTests(loader.loadTestsFromTestCase(candidate))

        self.assertGreater(suite.countTestCases(), 0, "no kind-proof classes were collected")
        result = _unittest.TestResult()
        suite.run(result)

        self.assertEqual(
            [], [str(test) for test, _reason in result.skipped],
            "a mutation-kind proof skipped at runtime — the matrix would stay green while its "
            "cells stopped running",
        )

    def test_M4_matrix_missing_factor_mutation_is_rejected(self) -> None:
        kinds = MUTATION_KINDS[:-1]
        cases = tuple(itertools.product(kinds, DIGEST_PATHS, TRANSCRIPT_POSITIONS))
        with self.assertRaises(AssertionError):
            self.assert_closed_matrix(kinds, cases)


class M4TimingNegativeProofs(FreshnessFixture):
    def test_M4_timing_negative_assertion_strictly_older_rejects(self) -> None:
        self.assert_real_kind("timing-negative")

    def test_M4_timing_negative_polarity_and_second_precision_mutations_are_rejected(self) -> None:
        self.assert_verdict_mutations_rejected(
            "timing-negative", self.verdict_mutations("timing-negative")
        )


class M4TimingPositiveProofs(FreshnessFixture):
    def test_M4_timing_positive_assertion_newer_accepts(self) -> None:
        self.assert_real_kind("timing-positive")

    def test_M4_timing_positive_rejection_mutation_is_rejected(self) -> None:
        self.assert_verdict_mutations_rejected(
            "timing-positive", self.verdict_mutations("timing-positive")
        )


class M4MtimeEqualityProofs(FreshnessFixture):
    def test_M4_mtime_equality_assertion_equal_accepts(self) -> None:
        self.assert_real_kind("mtime-equality")

    def test_M4_mtime_equality_less_or_equal_mutation_is_rejected(self) -> None:
        self.assert_verdict_mutations_rejected(
            "mtime-equality", self.verdict_mutations("mtime-equality")
        )


class M4AbsentRecordProofs(FreshnessFixture):
    def test_M4_absent_assertion_missing_record_rejects(self) -> None:
        self.assert_real_kind("absent")

    def test_M4_absent_fail_open_mutation_is_rejected(self) -> None:
        self.assert_verdict_mutations_rejected(
            "absent", self.verdict_mutations("absent")
        )


class M4MismatchedRecordProofs(FreshnessFixture):
    def test_M4_mismatched_assertion_wrong_run_id_rejects(self) -> None:
        self.assert_real_kind("mismatched")

    def test_M4_mismatched_binding_bypass_mutation_is_rejected(self) -> None:
        self.assert_verdict_mutations_rejected(
            "mismatched", self.verdict_mutations("mismatched")
        )


class M4EmptyRecordProofs(FreshnessFixture):
    def test_M4_empty_assertion_empty_record_rejects(self) -> None:
        self.assert_real_kind("empty")

    def test_M4_empty_record_bypass_mutation_is_rejected(self) -> None:
        self.assert_verdict_mutations_rejected(
            "empty", self.verdict_mutations("empty")
        )


class M4MalformedRecordProofs(FreshnessFixture):
    def test_M4_malformed_assertion_exact_lowercase_single_line_grammar(self) -> None:
        self.assert_real_kind("malformed")

    def test_M4_malformed_grammar_bypass_mutation_is_rejected(self) -> None:
        self.assert_verdict_mutations_rejected(
            "malformed", self.verdict_mutations("malformed")
        )


class M4RecordPrecedesDispatchProofs(FreshnessFixture):
    def test_M4_record_precedes_dispatch_assertion_for_every_digest_and_position(self) -> None:
        self.assert_real_kind("record-precedes-dispatch")

    def test_M4_marker_before_record_and_nonexclusive_create_mutations_are_rejected(self) -> None:
        marker_before_record = _replace_once(
            self.allocator_source,
            "        try:\n"
            "            launch_created = _create_launch_record(path + \".launch\", run_id, reviewer)\n",
            "        sys.stdout.write(ALLOCATION_MARKER + path + \"\\n\")\n"
            "        sys.stdout.flush()\n"
            "        try:\n"
            "            launch_created = _create_launch_record(path + \".launch\", run_id, reviewer)\n",
        )
        nonexclusive_create = _replace_once(
            self.allocator_source,
            "    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, \"O_NOFOLLOW\", 0)\n",
            "    flags = os.O_WRONLY | os.O_CREAT | getattr(os, \"O_NOFOLLOW\", 0)\n",
        )
        for label, source in (
            ("marker-before-record", marker_before_record),
            ("nonexclusive-record", nonexclusive_create),
        ):
            for digest_path in DIGEST_PATHS:
                for position in TRANSCRIPT_POSITIONS:
                    with self.subTest(
                        mutation=label,
                        digest=digest_path,
                        position=position,
                    ):
                        with self.assertRaises(AssertionError):
                            self.assert_matrix_cell(
                                VERDICT_PATH,
                                "record-precedes-dispatch",
                                digest_path,
                                position,
                                allocator_source=source,
                            )


class M4SidecarVariedProofs(FreshnessFixture):
    def test_M4_sidecar_varied_assertion_sidecar_time_never_anchors_freshness(self) -> None:
        self.assert_real_kind("sidecar-varied")

    def test_M4_sidecar_written_after_transcript_anchor_mutation_is_rejected(self) -> None:
        self.assert_verdict_mutations_rejected(
            "sidecar-varied", self.verdict_mutations("sidecar-varied")
        )


class SFreshAdditionalProofs(FreshnessFixture):
    def test_per_transcript_lookup_assertion_second_record_is_checked_independently(self) -> None:
        for digest_path in DIGEST_PATHS:
            self.assert_matrix_cell(
                VERDICT_PATH,
                "mismatched",
                digest_path,
                "SECOND",
            )

    def test_per_transcript_lookup_once_per_run_mutation_is_rejected(self) -> None:
        # The mutation is confined to WHICH launch record is looked up. `verified` is dropped so the
        # digest and path still come from this reviewer's own transcript: were the first transcript's
        # evidence carried into the second reviewer's record, the artifact would be refused by the
        # distinct-evidence check and this proof would witness that rejection instead of the
        # once-per-run one it is named for.
        mutant = _replace_once(
            self.verdict_source,
            "        freshness_problem, verified = _transcript_freshness_problem(transcript)\n",
            "        global _first_freshness_transcript\n"
            "        try:\n"
            "            freshness_transcript = _first_freshness_transcript\n"
            "        except NameError:\n"
            "            _first_freshness_transcript = transcript\n"
            "            freshness_transcript = transcript\n"
            "        freshness_problem, _ = _transcript_freshness_problem(freshness_transcript)\n"
            "        verified = None\n",
        )
        script = self.write_script(
            mutant,
            "once-per-run-record",
            "review-verdict.py",
        )
        for digest_path in DIGEST_PATHS:
            with self.subTest(digest=digest_path):
                with self.assertRaises(AssertionError):
                    self.assert_matrix_cell(
                        script,
                        "mismatched",
                        digest_path,
                        "SECOND",
                    )

    def run_empty_transcript(self, source: str, label: str) -> subprocess.CompletedProcess:
        script = self.write_script(source, label, "review-verdict.py")
        case_root = self.next_case_root(label)
        plan = case_root / "PLAN.md"
        plan.write_text("# Plan\n", encoding="utf-8")
        parent = (
            case_root
            / "state"
            / "unleashed-mail"
            / "review-transcripts"
            / "RepoHash09"
        )
        empty = self.create_transcript(parent, "gemini", RUN_IDS[0], b"")
        other = self.create_transcript(
            parent,
            "codex",
            RUN_IDS[1],
            b"codex rejection body\nVERDICT: REQUEST_CHANGES\n",
        )
        return self.invoke(
            script,
            [
                "write",
                "--plan",
                str(plan),
                "--verdict",
                "REQUEST_CHANGES",
                "--reviewer",
                "gemini=REQUEST_CHANGES:" + str(empty),
                "--reviewer",
                "codex=REQUEST_CHANGES:" + str(other),
            ],
        )

    def test_allocated_empty_transcript_assertion_classifies_as_missing(self) -> None:
        result = self.run_empty_transcript(
            self.verdict_source,
            "empty-transcript-assertion",
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("EMPTY", output)
        self.assertIn("MISSING", output)

    def test_allocated_empty_transcript_guard_removal_mutation_is_rejected(self) -> None:
        mutant = _replace_once(
            self.verdict_source,
            "        if os.path.getsize(transcript) == 0:\n",
            "        if False and os.path.getsize(transcript) == 0:\n",
        )
        result = self.run_empty_transcript(mutant, "empty-transcript-guard-removed")
        with self.assertRaises(AssertionError):
            output = result.stdout + result.stderr
            self.assertNotEqual(0, result.returncode, output)
            self.assertIn("MISSING", output)

    def run_duplicate_evidence(self, source: str, label: str) -> subprocess.CompletedProcess:
        script = self.write_script(source, label, "review-verdict.py")
        case_root = self.next_case_root(label)
        plan = case_root / "PLAN.md"
        plan.write_text("# Plan\n", encoding="utf-8")
        parent = (
            case_root
            / "state"
            / "unleashed-mail"
            / "review-transcripts"
            / "RepoHash09"
        )
        shared = self.create_transcript(
            parent,
            "gemini",
            RUN_IDS[0],
            b"one review cannot back two approvals\nVERDICT: APPROVE\n",
        )
        digest = hashlib.sha256(plan.read_bytes()).hexdigest()
        # A valid plan binding, so the quorum check is the only thing this cell can fail on. Without
        # it the bypass mutant is refused by the binding instead, and the proof would witness the
        # wrong rejection.
        # A VALID binding, derived rather than restated: this cell isolates the QUORUM rule, so the
        # plan binding must not be a second reason to refuse. `plan.name` was accepted only while the
        # binding comparison exempted separator-free records (PR #63 recheck).
        shared_identity, _kind = _verdict_module()._plan_identity(str(plan))
        Path(str(shared) + ".plan").write_text(f"{digest}  {shared_identity}\n", encoding="utf-8")
        write_prompt_binding(shared)
        return self.invoke(
            script,
            [
                "write",
                "--plan",
                str(plan),
                "--verdict",
                "APPROVE",
                "--reviewer",
                "gemini=APPROVE:" + str(shared),
                "--reviewer",
                "codex=APPROVE:" + str(shared),
                "--reviewed-sha256",
                digest,
            ],
        )

    def test_distinct_evidence_assertion_survives_added_freshness_check(self) -> None:
        result = self.run_duplicate_evidence(
            self.verdict_source,
            "distinct-evidence-assertion",
        )
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)

    def test_distinct_evidence_bypass_mutation_is_rejected(self) -> None:
        """Isolates the QUORUM rule, which now needs BOTH guards disabled to observe.

        A second mechanism began covering this case: the reviewer-identity check refuses a transcript
        whose allocated name is not the reviewer it is declared as, and one shared transcript is
        necessarily mislabelled for one of the two arms. With only `_quorum_problem` disabled the write
        still failed — correct behaviour, but it stopped this cell from saying anything about the rule
        it is named for. Disabling both restores that isolation; it does not weaken the shipped code,
        where either guard alone rejects the duplicate (PR #63 recheck).
        """
        mutant = _replace_once(
            self.verdict_source,
            "    problem = _quorum_problem(verdict, reviewers)\n",
            "    problem = None\n",
        )
        mutant = _replace_once(
            mutant,
            "        mismatch = _reviewer_identity_mismatch(reviewers)\n",
            "        mismatch = None\n",
        )
        result = self.run_duplicate_evidence(mutant, "distinct-evidence-bypassed")
        with self.assertRaises(AssertionError):
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)




def _rmtree_quiet(path: str) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


class ClassifierBypassProofs(unittest.TestCase):
    """PR #63 review: two spellings that OPEN an allocated transcript but skipped the gate.

    Both reached the same skip through different doors, so both are proved against the real
    classifier rather than a fixture — the defect was that classification ran on the WRONG
    string (post-realpath) and with the wrong comparison (case-sensitive on a case-insensitive
    filesystem), and only the real function can witness that.
    """

    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location(
            "_rv_classifier", str(VERDICT_PATH)
        )
        cls.rv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.rv)

    def setUp(self) -> None:
        self.root = tempfile.mkdtemp()
        self.addCleanup(_rmtree_quiet, self.root)
        self.layout = os.path.join(
            self.root, "unleashed-mail", "review-transcripts", "abcdef123456"
        )
        os.makedirs(self.layout)

    def test_case_mangled_layout_still_classifies_as_per_run(self) -> None:
        """macOS APFS is case-insensitive, so this spelling opens the identical file."""
        mangled = os.path.join(
            self.root, "Unleashed-Mail", "Review-Transcripts", "abcdef123456", "out.TXT"
        )
        self.assertTrue(
            self.rv._is_per_run_transcript(mangled),
            "a case-mangled spelling opens the same file and must not be treated as legacy",
        )

    def test_sibling_launch_record_alone_classifies_as_per_run(self) -> None:
        """The fail-closed branch: a `.launch` beside a file is proof of per-run provenance."""
        odd = os.path.join(self.root, "not-the-usual-shape.txt")
        open(odd, "w").close()
        self.assertFalse(self.rv._is_per_run_transcript(odd))
        open(odd + ".launch", "w").close()
        self.assertTrue(
            self.rv._is_per_run_transcript(odd),
            "a sibling launch record must force the record to be validated, never skipped",
        )

    def test_equivalent_spellings_of_one_file_all_reach_the_gate(self) -> None:
        """The same bytes must not be accepted or rejected based on how the path was spelled.

        The layout comparison used the LEXICAL parents, so `…/HASH/./f.txt`, `…/HASH/../HASH/f.txt`
        and a symlinked ancestor each opened the identical file while failing the comparison — and a
        layout-placed transcript with no allocator filename and no `.launch` therefore skipped the
        freshness check entirely (deep review; all three reproduced).

        Asserted on the FRESHNESS OUTCOME, not on the classifier alone: classification is a mechanism,
        and the property that matters is that the gate runs.
        """
        foreign = os.path.join(self.layout, "foreign.txt")
        with open(foreign, "w") as handle:
            handle.write("stale foreign content\nVERDICT: APPROVE\n")
        ancestor_link = os.path.join(self.root, "link-to-transcripts")
        os.symlink(os.path.join(self.root, "unleashed-mail", "review-transcripts"), ancestor_link)

        spellings = {
            "canonical": foreign,
            "dot segment": os.path.join(self.layout, ".", "foreign.txt"),
            "dotdot round-trip": os.path.join(
                self.layout, "..", os.path.basename(self.layout), "foreign.txt"
            ),
            "symlinked ancestor": os.path.join(
                ancestor_link, os.path.basename(self.layout), "foreign.txt"
            ),
        }
        for label, spelling in spellings.items():
            with self.subTest(spelling=label):
                self.assertTrue(
                    os.path.samefile(spelling, foreign),
                    "the fixture must name the SAME file, or this proves nothing",
                )
                problem, verified = self.rv._transcript_freshness_problem(spelling)
                self.assertIsNotNone(
                    problem,
                    f"the {label} spelling skipped the freshness gate for a file the canonical "
                    "spelling rejects",
                )
                self.assertIsNone(verified)

    def test_resolving_the_ancestry_does_not_resolve_the_leaf(self) -> None:
        """The deletion test for the fix: it must not become the defect it replaced.

        Resolving the WHOLE path is what walked a symlinked LEAF out of the layout and skipped the
        check. Only `dirname` is resolved, so the leaf's own link-ness is still visible.
        """
        outside = os.path.join(self.root, "outside.txt")
        with open(outside, "w") as handle:
            handle.write("foreign\n")
        link = os.path.join(self.layout, "gemini-" + "f" * 32 + ".txt")
        os.symlink(outside, link)
        open(link + ".launch", "w").close()

        problem, _ = self.rv._transcript_freshness_problem(link)
        self.assertIsNotNone(problem)
        self.assertIn("symbolic link", problem)

    def test_symlinked_allocated_path_fails_closed_instead_of_skipping(self) -> None:
        """Classifying after realpath let a symlink escape the layout and skip the whole check."""
        foreign = os.path.join(self.root, "foreign.txt")
        with open(foreign, "w") as handle:
            handle.write("stale foreign content\n")
        link = os.path.join(self.layout, "gemini-" + "f" * 32 + ".txt")
        os.symlink(foreign, link)
        open(link + ".launch", "w").close()

        problem, verified = self.rv._transcript_freshness_problem(link)
        self.assertIsNotNone(
            problem, "a symlinked per-run transcript must never return None (check skipped)"
        )
        self.assertIn("symbolic link", problem)
        self.assertIsNone(
            verified, "a refused transcript must never hand back evidence to record"
        )


class SFreshDescriptorBindingProofs(FreshnessFixture):
    """PR #63 remediation item 1 — the check validated one file and the digest recorded another.

    `_transcript_freshness_problem` opened the transcript, validated it and closed it; `_parse_reviewer`
    then hashed the PATH. Between those two the name can be re-pointed, so the artifact could record as
    reviewed evidence the digest of a file that never passed the check.

    The window opens the instant validation reads the descriptor's metadata, so that is where these
    proofs swap the leaf: everything the gate says about the transcript afterwards must come from the
    descriptor it already holds, not from the name. Triggering on `fstat` rather than on the closing of
    the descriptor is deliberate — a re-open placed BETWEEN the fstat and the return would sit inside
    the window but before any close, and a close-triggered swap would sail past it.
    """

    ORIGINAL = b"gemini distinct review body\nVERDICT: APPROVE\n"
    SWAPPED = b"attacker substituted body\nVERDICT: APPROVE\n"

    def assert_digest_binds_to_validated_descriptor(self, source: str, label: str) -> None:
        case_root = self.next_case_root(label)
        transcript = self.create_transcript(
            case_root / "state" / "unleashed-mail" / "review-transcripts" / "RepoHash09",
            "gemini",
            RUN_IDS[0],
            self.ORIGINAL,
        )
        swapped = case_root / "swapped.txt"
        swapped.write_bytes(self.SWAPPED)
        self.assertNotEqual(
            hashlib.sha256(self.ORIGINAL).hexdigest(),
            hashlib.sha256(self.SWAPPED).hexdigest(),
            "the two bodies must differ, or a swap is unobservable and this proves nothing",
        )

        script = self.write_script(source, "descriptor-" + label, "review-verdict.py")
        module = _load_module(script, "descriptor_" + label + "_" + str(self.case_number))

        watched = set()  # type: set
        real_open = os.open
        real_fstat = os.fstat

        def open_spy(path, flags, mode=0o777, *args, **kwargs):
            descriptor = real_open(path, flags, mode, *args, **kwargs)
            if os.fsdecode(path) == str(transcript):
                watched.add(descriptor)
            return descriptor

        def fstat_spy(descriptor, *args, **kwargs):
            info = real_fstat(descriptor, *args, **kwargs)
            if descriptor in watched:
                watched.discard(descriptor)
                os.replace(str(swapped), str(transcript))
            return info

        with mock.patch.object(module.os, "open", open_spy), mock.patch.object(
            module.os, "fstat", fstat_spy
        ):
            parsed = module._parse_reviewer("gemini=APPROVE:" + str(transcript))

        self.assertEqual(
            self.SWAPPED,
            transcript.read_bytes(),
            "the leaf was never actually swapped, so the window was never opened",
        )
        self.assertEqual(
            hashlib.sha256(self.ORIGINAL).hexdigest(),
            parsed["transcriptSha256"],
            "the artifact recorded the digest of a file the freshness check never validated",
        )

    def test_digest_assertion_binds_to_the_descriptor_the_check_validated(self) -> None:
        self.assert_digest_binds_to_validated_descriptor(self.verdict_source, "assertion")

    def test_reopen_by_path_mutations_are_rejected(self) -> None:
        """Both places the re-open can creep back: the caller, and the validator's own return."""
        mutations = (
            (
                "caller-rehashes-the-path",
                _replace_once(
                    self.verdict_source,
                    "        out[\"transcriptSha256\"] = (\n"
                    "            verified.sha256 if verified is not None else _sha256_bytes(transcript)\n"
                    "        )\n",
                    "        out[\"transcriptSha256\"] = _sha256_bytes(transcript)\n",
                ),
            ),
            (
                "validator-rehashes-the-path",
                _replace_once(
                    self.verdict_source,
                    "        return info, _sha256_descriptor(descriptor), None\n",
                    "        return info, _sha256_bytes(path), None\n",
                ),
            ),
        )
        for label, mutant in mutations:
            with self.subTest(mutation=label):
                with self.assertRaises(AssertionError):
                    self.assert_digest_binds_to_validated_descriptor(mutant, label)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class PlanBindingProofs(FreshnessFixture):
    """A fresh review of ANOTHER target must not satisfy this plan's gate (deep review, P1).

    `.promptsha256` was written by the capture helpers and read by NOTHING. The reviewer reproduced
    `GATE OK — APPROVE` for plan A using two freshly allocated transcripts from an unrelated ticket:
    freshness proved both were real recent runs, the snapshot proved plan A was unedited, and no check
    connected the two. Freshness answers "is this a real run"; this answers "a run of WHAT".
    """

    def write_with_binding(self, label: str, bound_digest, verdict: str = "APPROVE",
                           bind_to_this_plan: bool = False, bound_identity: str = None):
        case_root = self.next_case_root(label)
        plan = case_root / "PLAN.md"
        plan.write_text("# Plan\nthe bytes being approved\n", encoding="utf-8")
        plan_digest = hashlib.sha256(plan.read_bytes()).hexdigest()
        parent = case_root / "state" / "unleashed-mail" / "review-transcripts" / "RepoHash09"

        # THE IDENTITY DEFAULTS TO THIS PLAN'S, so each cell varies ONE thing. Every case used to record
        # the placeholder `some-plan.md`, which only passed because the binding comparison exempted
        # separator-free records — the same exemption that let a transcript bound to one root-level plan
        # approve another with identical bytes (PR #63 recheck). With the exemption gone, a placeholder
        # identity would make every cell fail on the identity rather than on the variable it isolates.
        identity = bound_identity
        if identity is None:
            identity, _kind = _verdict_module()._plan_identity(str(plan))

        transcripts = []
        for index, reviewer in enumerate(("gemini", "codex")):
            transcript = self.create_transcript(
                parent, reviewer, RUN_IDS[index],
                (reviewer + " review\nVERDICT: APPROVE\n").encode("utf-8"),
            )
            recorded = plan_digest if bind_to_this_plan else bound_digest
            if recorded is not None:
                Path(str(transcript) + ".plan").write_text(
                    f"{recorded}  {identity}\n", encoding="utf-8"
                )
                write_prompt_binding(transcript)
            transcripts.append(transcript)

        arguments = ["write", "--plan", str(plan), "--verdict", verdict]
        for reviewer, transcript in zip(("gemini", "codex"), transcripts):
            arguments += ["--reviewer", reviewer + "=APPROVE:" + str(transcript)]
        arguments += ["--reviewed-sha256", plan_digest]
        return self.invoke(VERDICT_PATH, arguments), plan_digest

    def test_a_transcript_bound_to_this_plan_is_accepted(self):
        """The positive control. Without it the refusals below could be refusing everything.

        This asserts a SUCCESSFUL approving write — the first version of this cell asserted a
        refusal, which made it a duplicate of the negative case wearing the positive case's name.
        """
        result, _ = self.write_with_binding("binding-positive", None, bind_to_this_plan=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_a_transcript_reviewing_another_plan_cannot_approve_this_one(self):
        other = hashlib.sha256(b"a completely different plan\n").hexdigest()
        result, _ = self.write_with_binding("binding-other-plan", other)
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("different bytes than this verdict approves", output)

    def test_a_transcript_bound_to_a_DIFFERENT_plan_identity_is_refused(self):
        """The separator-free exemption is gone (PR #63 recheck).

        `bind-prompt.py` records `relpath(plan, root)`, which for a plan at the repository ROOT is a
        bare basename. The old `os.sep in bound_plan` guard therefore skipped exactly the bindings the
        current binder produces for root-level plans — so two such plans with IDENTICAL bytes both
        passed the digest check and a transcript bound to `A_PLAN.md` approved `B_PLAN.md`. Here the
        digest matches and only the identity differs, so nothing but the identity rule can refuse it.
        """
        result, _ = self.write_with_binding(
            "binding-other-identity", None, bind_to_this_plan=True,
            bound_identity="A_PLAN.md",
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("bound to a different plan", output)

    def test_an_absent_binding_is_refused_rather_than_skipped(self):
        result, _ = self.write_with_binding("binding-absent", None)
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("no plan binding", output)

    def test_a_nonapproving_verdict_is_still_recordable_without_a_binding(self):
        """Refusing REQUEST_CHANGES on a binding problem would block the gate from recording a
        rejection — the one verdict that must always be writable."""
        result, _ = self.write_with_binding(
            "binding-rejection", None, verdict="REQUEST_CHANGES"
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
