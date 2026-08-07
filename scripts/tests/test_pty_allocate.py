#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-ALLOC proof cells (M1.1 through M1.20)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import stat
import string
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO = Path(__file__).resolve().parents[2]
PTY = REPO / "scripts" / "pty-capture.py"
RUN_A = "0123456789abcdeffedcba9876543210"
RUN_B = "ffeeddccbbaa99887766554433221100"


def _load():
    spec = importlib.util.spec_from_file_location("pty_capture_allocate_under_test", PTY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _read_umask() -> int:
    current = os.umask(0)
    os.umask(current)
    return current


def _parent_mode_complement_cases():
    """Derive, rather than enumerate, both arms × the full S_IMODE complement."""
    for arm in ("xdg", "fallback"):
        for mode in range(0o10000):
            if mode != 0o700:
                yield arm, mode


def _owner_bit_clearing_umasks():
    for mask in range(0o1000):
        if mask & 0o700:
            yield mask


class AllocatorFixture(unittest.TestCase):
    def setUp(self):
        self.mod = _load()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)

    def tearDown(self):
        self.temp.cleanup()

    def env_for(self, base: Path | None = None) -> dict[str, str]:
        env = {"HOME": str(self.home)}
        if base is not None:
            env["XDG_STATE_HOME"] = str(base)
        return env

    def fallback_base(self) -> Path:
        return self.home / ".local" / "state"

    @staticmethod
    def parent_for(base: Path, repo_hash: str = "hash") -> Path:
        return base / "unleashed-mail" / "review-transcripts" / repo_hash

    def prepare_parent(self, base: Path, repo_hash: str = "hash") -> Path:
        base.mkdir(mode=0o755, parents=True, exist_ok=True)
        os.chmod(base, 0o755)
        parent = base
        for component in ("unleashed-mail", "review-transcripts", repo_hash):
            parent = parent / component
            parent.mkdir(mode=0o700, exist_ok=True)
            os.chmod(parent, 0o700)
        return parent

    def allocate(
        self,
        *,
        base: Path | None = None,
        repo_hash: str = "hash",
        ticket: str = "COREDEV-2619",
        round_value: str = "1",
        reviewer: str = "codex",
    ) -> Path:
        path = self.mod.allocate_transcript(
            repo_hash,
            ticket,
            round_value,
            reviewer,
            environ=self.env_for(base),
            diagnostic_stream=io.StringIO(),
        )
        return Path(path)

    @staticmethod
    def basename(mod, ticket: str, round_value: str, reviewer: str, run_id: str) -> str:
        return mod._allocation_basename(ticket, round_value, reviewer, run_id)

    def cli_args(
        self,
        *,
        repo_hash: str = "hash",
        ticket: str = "COREDEV-2619",
        round_value: str = "1",
        reviewer: str = "codex",
    ) -> list[str]:
        return [
            "--allocate",
            "--repo-hash",
            repo_hash,
            "--ticket",
            ticket,
            "--round",
            round_value,
            "--reviewer",
            reviewer,
        ]

    def invoke_cli(self, args: list[str], env: dict[str, str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = self.mod.cli_main(args, environ=env)
        return status, stdout.getvalue(), stderr.getvalue()


class M1AtomicReservationTests(AllocatorFixture):
    def test_M1_1_sentinel_collision_preserves_bytes_and_allocates_a_different_leaf(self):
        """Rejects overwrite, truncate, or reuse of an already-reserved sentinel leaf."""
        base = self.root / "state"
        parent = self.prepare_parent(base)
        sentinel = parent / self.basename(self.mod, "COREDEV-2619", "1", "codex", RUN_A)
        sentinel.write_bytes(b"sentinel-bytes")
        os.chmod(sentinel, 0o600)

        with mock.patch.object(self.mod, "_generate_run_id", side_effect=(RUN_A, RUN_B)):
            allocated = self.allocate(base=base)

        self.assertEqual(allocated.name, self.basename(self.mod, "COREDEV-2619", "1", "codex", RUN_B))
        self.assertEqual(sentinel.read_bytes(), b"sentinel-bytes")

    def test_M1_10_and_M1_14_creation_flags_are_atomic_on_the_actual_leaf_and_launch_calls(self):
        """Rejects O_EXCL-only, check-then-create, and truncating launch-record opens."""
        base = self.root / "state"
        self.prepare_parent(base)
        real_open = os.open
        calls = []

        def open_spy(path, flags, mode=0o777, *args, **kwargs):
            calls.append((os.fspath(path), flags, mode))
            return real_open(path, flags, mode, *args, **kwargs)

        with mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A), \
                mock.patch.object(self.mod.os, "open", side_effect=open_spy):
            allocated = self.allocate(base=base)

        leaf_calls = [call for call in calls if call[0] == str(allocated)]
        launch_calls = [call for call in calls if call[0] == str(allocated) + ".launch"]
        leaf_creates = [call for call in leaf_calls if call[1] & os.O_CREAT]
        launch_creates = [call for call in launch_calls if call[1] & os.O_CREAT]
        self.assertEqual(1, len(leaf_creates))
        self.assertEqual(1, len(launch_creates))
        for _path, flags, requested_mode in leaf_creates + launch_creates:
            self.assertEqual(os.O_CREAT | os.O_EXCL, flags & (os.O_CREAT | os.O_EXCL))
            self.assertFalse(flags & os.O_TRUNC)
            self.assertEqual(0o600, requested_mode)

    def test_M1_6_launch_collision_is_never_truncated_and_retries_with_a_new_pair(self):
        """Rejects a launch writer that truncates its sentinel or leaves the orphan leaf."""
        base = self.root / "state"
        parent = self.prepare_parent(base)
        first_leaf = parent / self.basename(self.mod, "COREDEV-2619", "1", "codex", RUN_A)
        launch_sentinel = Path(str(first_leaf) + ".launch")
        launch_sentinel.write_bytes(b"launch-sentinel")
        os.chmod(launch_sentinel, 0o600)

        with mock.patch.object(self.mod, "_generate_run_id", side_effect=(RUN_A, RUN_B)):
            allocated = self.allocate(base=base)

        self.assertEqual(RUN_B, allocated.name.removesuffix(".txt").rsplit("-", 1)[1])
        self.assertEqual(b"launch-sentinel", launch_sentinel.read_bytes())
        self.assertFalse(first_leaf.exists(), "launch collision must remove its just-created leaf")

    def test_M1_7_launch_payload_is_the_filename_run_id_as_exactly_one_line(self):
        """Rejects a payload with a different ID, uppercase, extra lines, or trailing content."""
        base = self.root / "state"
        with mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A):
            allocated = self.allocate(base=base)
        self.assertEqual((RUN_A + "\n").encode("ascii"), Path(str(allocated) + ".launch").read_bytes())
        self.assertEqual(RUN_A, allocated.stem.rsplit("-", 1)[1])

    def test_M1_11_and_M1_15_exactly_eight_collisions_fail_and_name_parent_on_stderr(self):
        """Rejects any retry bound other than eight and a generic or stdout diagnostic."""
        base = self.root / "state"
        parent = self.prepare_parent(base)
        run_ids = [f"{index:032x}" for index in range(self.mod.ALLOCATION_ATTEMPTS)]
        for run_id in run_ids:
            leaf = parent / self.basename(self.mod, "COREDEV-2619", "1", "codex", run_id)
            leaf.write_bytes(b"sentinel")
            os.chmod(leaf, 0o600)

        generator = mock.Mock(side_effect=run_ids)
        with mock.patch.object(self.mod, "_generate_run_id", generator):
            status, stdout, stderr = self.invoke_cli(self.cli_args(), self.env_for(base))

        self.assertNotEqual(0, status)
        self.assertEqual("", stdout)
        self.assertIn(str(parent), stderr)
        self.assertIn(str(self.mod.ALLOCATION_ATTEMPTS), stderr)
        self.assertEqual(8, generator.call_count)
        self.assertTrue(all(path.read_bytes() == b"sentinel" for path in parent.glob("*.txt")))


class M1ComponentAndLayoutTests(AllocatorFixture):
    def test_M1_5_and_M1_8_shared_validator_sweeps_both_grammar_halves(self):
        """Rejects unanchored regexes, partial valid alphabets, and acceptance of dot/dot-dot."""
        valid_characters = set(string.ascii_letters + string.digits + "._-")
        self.assertEqual(65, len(valid_characters))
        for character in valid_characters:
            self.assertTrue(self.mod.is_valid_transcript_component("A" + character + "A"), repr(character))
        for codepoint in range(128):
            character = chr(codepoint)
            if character not in valid_characters:
                self.assertFalse(self.mod.is_valid_transcript_component(character), repr(character))
        for value in (".", "..", "A/../../escape", "valid\nextra", "é"):
            self.assertFalse(self.mod.is_valid_transcript_component(value), repr(value))

    def test_M1_5_and_M1_8_allocator_decision_is_bound_to_the_shared_validator(self):
        """Rejects an unused correct validator beside divergent inline production logic."""
        base = self.root / "state"
        fields = ("ticket", "round_value", "reviewer")
        for field in fields:
            kwargs = {"ticket": "T", "round_value": "1", "reviewer": "codex"}
            target = kwargs[field]
            real_validator = self.mod.is_valid_transcript_component

            def reject_target(value, target=target):
                return False if value == target else real_validator(value)

            with self.subTest(field=field, forced="reject"), \
                    mock.patch.object(self.mod, "is_valid_transcript_component", side_effect=reject_target), \
                    mock.patch.object(self.mod, "_generate_run_id") as generator:
                with self.assertRaises(self.mod.AllocationError):
                    self.allocate(base=base, **kwargs)
                generator.assert_not_called()

            kwargs[field] = "bad value"

            def accept_target(value):
                return True if value == "bad value" else real_validator(value)

            # THE ROUND HAS A SECOND SHARED VALIDATOR, and the binding property covers it too. The
            # generic grammar accepts `[A-Za-z0-9._-]+`, so a round like `round-1` allocated a leaf that
            # `review-verdict.py` refuses only AFTER a full review has run — `is_valid_round_component`
            # is the named validator that closes that (PR #63 recheck, P2). It is patched alongside the
            # generic one so this cell still proves "the allocator's decision is bound to the shared
            # validators", rather than proving the round is unconstrained.
            patches = [mock.patch.object(self.mod, "is_valid_transcript_component",
                                         side_effect=accept_target)]
            if field == "round_value":
                patches.append(mock.patch.object(self.mod, "is_valid_round_component",
                                                 side_effect=accept_target))

            with self.subTest(field=field, forced="accept"), \
                    contextlib.ExitStack() as stack, \
                    mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A):
                for patch in patches:
                    stack.enter_context(patch)
                allocated = self.allocate(base=base, **kwargs)
                self.assertIn("bad value", allocated.name)

    def test_the_round_validator_is_stricter_than_the_generic_one(self):
        """The round's extra rule must be REAL, not merely present (PR #63 recheck, P2).

        `round-1` satisfies the generic component grammar — that is exactly why it allocated a leaf
        `review-verdict.py` could never accept, after paying for the review. This asserts the two
        validators genuinely differ, so folding the round rule back into the generic one fails here.
        """
        for accepted_by_both in ("1", "42", "007"):
            self.assertTrue(self.mod.is_valid_transcript_component(accepted_by_both))
            self.assertTrue(self.mod.is_valid_round_component(accepted_by_both))
        for generic_only in ("round-1", "1a", "v2", "1.0", "_1"):
            self.assertTrue(self.mod.is_valid_transcript_component(generic_only),
                            f"{generic_only!r} should still satisfy the GENERIC grammar")
            self.assertFalse(self.mod.is_valid_round_component(generic_only),
                             f"{generic_only!r} is not a numeric round and must be refused")

    def test_M1_9_supplied_components_are_echoed_in_the_fixed_layout(self):
        """Rejects inferred, dropped, reordered, or rewritten ticket/round/reviewer fields."""
        base = self.root / "state"
        with mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A):
            allocated = self.allocate(
                base=base,
                repo_hash="repoABC",
                ticket="COREDEV-9999",
                round_value="42",
                reviewer="gemini",
            )
        canonical_base = Path(os.path.realpath(base))
        self.assertEqual(
            canonical_base / "unleashed-mail" / "review-transcripts" / "repoABC"
            / f"COREDEV-9999r42-gemini-{RUN_A}.txt",
            allocated,
        )

    def test_M1_13_safe_symlink_bases_emit_the_canonical_target_on_both_arms(self):
        """Rejects the old shortened layout and emission of a lexical symlink spelling."""
        target = self.root / "canonical-xdg"
        target.mkdir(mode=0o755)
        xdg_link = self.root / "xdg-link"
        xdg_link.symlink_to(target, target_is_directory=True)
        with mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A):
            xdg_path = self.allocate(base=xdg_link)
        canonical_target = Path(os.path.realpath(target))
        self.assertEqual(
            self.parent_for(canonical_target) / self.basename(self.mod, "COREDEV-2619", "1", "codex", RUN_A),
            xdg_path,
        )

        fallback_target = self.root / "canonical-fallback"
        fallback_target.mkdir(mode=0o755)
        local = self.home / ".local"
        local.mkdir(mode=0o700)
        (local / "state").symlink_to(fallback_target, target_is_directory=True)
        with mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_B):
            fallback_path = self.allocate()
        canonical_fallback = Path(os.path.realpath(fallback_target))
        self.assertEqual(
            self.parent_for(canonical_fallback)
            / self.basename(self.mod, "COREDEV-2619", "1", "codex", RUN_B),
            fallback_path,
        )

    def test_M1_19_basename_boundary_reserves_sibling_headroom_before_generation_per_input(self):
        """Rejects PC_NAME_MAX without suffix headroom, a tighter cap, and late retry-loop checks.

        The reservation is read from production's own `DERIVED_SIBLING_SUFFIXES` rather than restated
        as `.captureid`. It was restated, and when the capture helpers began writing a LONGER sibling
        (`.promptsha256`) this cell kept passing while a basename at the boundary could allocate and
        then fail to write that sibling (deep review, codex inline). A hardcoded copy cannot see the
        tuple grow; the assertion below now exercises whichever suffix is currently longest.
        """
        for field in ("ticket", "round_value", "reviewer"):
            with self.subTest(field=field):
                positive_base = self.root / f"positive-{field}"
                positive_parent = self.prepare_parent(positive_base)
                longest_sibling = max(self.mod.DERIVED_SIBLING_SUFFIXES, key=len)
                limit = os.pathconf(positive_parent, "PC_NAME_MAX") - len(longest_sibling)
                kwargs = {"ticket": "T", "round_value": "1", "reviewer": "c"}
                fixed_length = len(
                    self.basename(self.mod, kwargs["ticket"], kwargs["round_value"], kwargs["reviewer"], RUN_A)
                ) - len(kwargs[field])
                # DIGITS for the round, `x` elsewhere: this cell is about the basename LENGTH boundary,
                # and the round now has a numeric grammar (PR #63 recheck, P2), so padding it with `x`
                # would fail for a reason this cell does not test.
                filler = "9" if field == "round_value" else "x"
                kwargs[field] = filler * (limit - fixed_length)
                self.assertGreater(len(kwargs[field]), 0)

                with mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A) as positive_generator:
                    allocated = self.allocate(base=positive_base, **kwargs)
                self.assertEqual(limit, len(allocated.name))
                self.assertTrue(Path(str(allocated) + ".launch").exists())
                for suffix in self.mod.DERIVED_SIBLING_SUFFIXES:
                    sibling = Path(str(allocated) + suffix)
                    sibling.write_text("sibling\n", encoding="ascii")
                    self.assertTrue(
                        sibling.exists(),
                        f"derived sibling {suffix} must fit at the positive boundary",
                    )
                positive_generator.assert_called_once()

                negative_base = self.root / f"negative-{field}"
                negative_parent = self.prepare_parent(negative_base)
                too_long = dict(kwargs)
                # Same filler as above: an `x` on the round would be refused by the numeric grammar
                # BEFORE the length check, so the assertion below would read the wrong refusal.
                too_long[field] += filler
                with mock.patch.object(self.mod, "_generate_run_id") as negative_generator:
                    with self.assertRaises(self.mod.AllocationError) as caught:
                        self.allocate(base=negative_base, **too_long)
                negative_generator.assert_not_called()
                self.assertIn(str(limit), str(caught.exception))
                self.assertTrue(negative_parent.is_dir(), "length check belongs after parent creation")
                self.assertEqual([], list(negative_parent.iterdir()))


class M1ParentRoleTests(AllocatorFixture):
    def test_M1_2_absent_nested_parent_and_each_fixed_component_are_created_0700(self):
        """Rejects makedirs defaults and a test that observes only a pre-created parent."""
        base = self.root / "state"
        base.mkdir(mode=0o755)
        with mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A):
            self.allocate(base=base)
        current = base
        for component in ("unleashed-mail", "review-transcripts", "hash"):
            current = current / component
            self.assertEqual(0o700, _mode(current))

    def test_M1_3_parent_mode_complement_is_generated_over_full_S_IMODE_space_for_both_arms(self):
        """Rejects privacy-only or sampled-mode checks such as only testing 0755."""
        checked = 0
        for arm, mode in _parent_mode_complement_cases():
            metadata = SimpleNamespace(st_mode=stat.S_IFDIR | mode, st_uid=os.geteuid())
            try:
                self.mod._validate_existing_private_directory(f"/{arm}/parent", metadata)
            except self.mod.AllocationError:
                checked += 1
            else:
                self.fail(f"{arm} parent mode {mode:#06o} was accepted")
        self.assertEqual(2 * (len(range(0o10000)) - 1), checked)
        for arm in ("xdg", "fallback"):
            metadata = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=os.geteuid())
            self.mod._validate_existing_private_directory(f"/{arm}/parent", metadata)

    def test_M1_3_and_M1_4_parent_validator_is_used_on_the_final_parent_on_both_base_arms(self):
        """Rejects a correct but unused helper beside inline mode/owner logic."""
        for arm in ("xdg", "fallback"):
            base = self.root / f"{arm}-state" if arm == "xdg" else self.fallback_base()
            parent = self.prepare_parent(base)
            real_validator = self.mod._validate_existing_private_directory

            def reject_final(path, metadata=None, parent=parent):
                if os.path.realpath(path) == os.path.realpath(parent):
                    raise self.mod.AllocationError("forced final-parent rejection")
                return real_validator(path, metadata)

            with self.subTest(arm=arm), \
                    mock.patch.object(self.mod, "_validate_existing_private_directory", side_effect=reject_final):
                with self.assertRaisesRegex(self.mod.AllocationError, "forced final-parent rejection"):
                    self.allocate(base=base if arm == "xdg" else None)

    def test_M1_4_wrong_owner_sweep_covers_root_and_nonroot_foreign_uids_on_both_arms(self):
        """Rejects mode-only and reject-root-only ownership implementations."""
        euid = os.geteuid()
        foreign_uids = []
        if euid != 0:
            foreign_uids.append(0)
        nonroot = next(uid for uid in range(1, 4) if uid != euid)
        foreign_uids.append(nonroot)
        self.assertTrue(foreign_uids)
        for arm in ("xdg", "fallback"):
            for uid in foreign_uids:
                metadata = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=uid)
                with self.subTest(arm=arm, uid=uid), self.assertRaises(self.mod.AllocationError):
                    self.mod._validate_existing_private_directory(f"/{arm}/parent", metadata)


class M1EntropyAndModeTests(AllocatorFixture):
    def test_M1_12_leaf_mode_is_achieved_0600(self):
        """Rejects the conventional 0666 creation request and outcome 0644."""
        allocated = self.allocate(base=self.root / "state")
        self.assertEqual(0o600, _mode(allocated))

    def test_M1_16_unstubbed_source_is_fresh_per_run_and_per_retry_attempt(self):
        """Rejects one ID per metadata tuple or one ID per run reused on retry."""
        base = self.root / "state"
        first = self.allocate(base=base)
        second = self.allocate(base=base)
        self.assertNotEqual(first, second)

        generated = []
        real_generate = self.mod._generate_run_id
        real_open = os.open
        forced_collision = False

        def observe_generation():
            run_id = real_generate()
            generated.append(run_id)
            return run_id

        def collide_once(path, flags, mode=0o777, *args, **kwargs):
            nonlocal forced_collision
            is_leaf_create = str(path).endswith(".txt") and not str(path).endswith(".launch") \
                and flags & os.O_CREAT and flags & os.O_EXCL
            if is_leaf_create and not forced_collision:
                forced_collision = True
                raise FileExistsError(path)
            return real_open(path, flags, mode, *args, **kwargs)

        with mock.patch.object(self.mod, "_generate_run_id", side_effect=observe_generation), \
                mock.patch.object(self.mod.os, "open", side_effect=collide_once):
            retried = self.allocate(base=base)
        self.assertEqual(2, len(generated))
        self.assertNotEqual(generated[0], generated[1])
        self.assertEqual(generated[1], retried.stem.rsplit("-", 1)[1])

    def test_M1_17_run_id_is_direct_lowercase_hex_of_at_least_16_interposed_CSPRNG_bytes(self):
        """Rejects hashing, truncation, repetition, or mixing the draw with clock/pid/counter state."""
        base = self.root / "state"
        calls = []

        def draw(byte_count):
            self.assertGreaterEqual(byte_count, 16)
            source = bytes((index * 17 + 3) % 256 for index in range(byte_count))
            calls.append(source)
            return source

        with mock.patch.object(self.mod.os, "urandom", side_effect=draw):
            allocated = self.allocate(base=base)
        self.assertEqual(1, len(calls))
        run_id = allocated.stem.rsplit("-", 1)[1]
        self.assertEqual(calls[0].hex(), run_id)
        self.assertEqual(run_id.lower(), run_id)

    def test_M1_20_leaf_fchmod_uses_the_held_fd_and_never_path_chmod(self):
        """Rejects close-then-chmod(path), even though its final mode can also be 0600."""
        base = self.root / "state"
        real_fchmod = os.fchmod
        real_fstat = os.fstat
        calls = []

        def fchmod_spy(fd, mode):
            calls.append((fd, mode, real_fstat(fd).st_ino))
            return real_fchmod(fd, mode)

        def forbidden_chmod(*_args, **_kwargs):
            raise AssertionError("allocator must not use path-based chmod")

        with mock.patch.object(self.mod.os, "fchmod", side_effect=fchmod_spy), \
                mock.patch.object(self.mod.os, "chmod", side_effect=forbidden_chmod):
            allocated = self.allocate(base=base)
        self.assertGreaterEqual(len(calls), 2, "leaf and launch record both tighten by descriptor")
        self.assertEqual(0o600, calls[0][1])
        self.assertEqual(allocated.stat().st_ino, calls[0][2])

    def test_M1_20_failed_leaf_fchmod_unlinks_reservation_allocates_nothing_and_restores_umask(self):
        """Rejects propagation that leaves the failed leaf behind or retries another run ID."""
        base = self.root / "state"
        parent = self.prepare_parent(base)
        observed_open_fd = []
        real_fstat = os.fstat
        entry_umask = 0o027
        previous = os.umask(entry_umask)
        try:
            def fail_fchmod(fd, _mode_value):
                observed_open_fd.append(real_fstat(fd).st_ino)
                raise PermissionError("forced leaf fchmod failure")

            with mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A) as generator, \
                    mock.patch.object(self.mod.os, "fchmod", side_effect=fail_fchmod):
                status, stdout, stderr = self.invoke_cli(self.cli_args(), self.env_for(base))
            self.assertNotEqual(0, status)
            self.assertEqual("", stdout)
            self.assertIn("forced leaf fchmod failure", stderr)
            self.assertTrue(observed_open_fd, "fchmod must receive a still-open descriptor")
            generator.assert_called_once()
            self.assertEqual([], list(parent.iterdir()))
            self.assertEqual(entry_umask, _read_umask())
        finally:
            os.umask(previous)


class M1UmaskAndConcurrencyTests(AllocatorFixture):
    def test_M1_18_owner_bit_clearing_umask_sweep_achieves_modes_and_restores_each_entry_value(self):
        """Rejects relying on requested mkdir/open modes under any owner-bit-clearing umask."""
        original = _read_umask()
        try:
            for mask in _owner_bit_clearing_umasks():
                base = self.root / "umasks" / f"m{mask:03o}" / "deep"
                os.umask(mask)
                with mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A):
                    allocated = self.allocate(base=base)
                if _read_umask() != mask:
                    self.fail(f"entry umask {mask:#05o} was not restored")
                current = self.root / "umasks" / f"m{mask:03o}"
                for component in ("deep", "unleashed-mail", "review-transcripts", "hash"):
                    current = current / component
                    if _mode(current) != 0o700:
                        self.fail(f"{current} was {_mode(current):#06o} under umask {mask:#05o}")
                self.assertEqual(0o600, _mode(allocated))
                self.assertEqual(0o600, _mode(Path(str(allocated) + ".launch")))
        finally:
            os.umask(original)

    def test_M1_18_every_created_directory_is_0700_as_soon_as_mkdir_publishes_it_on_both_arms(self):
        """Rejects post-publication chmod correction and os.makedirs intermediate defaults."""
        for arm in ("xdg", "fallback"):
            home = self.root / f"home-{arm}"
            home.mkdir(mode=0o700)
            base = self.root / f"absent-{arm}" / "a" / "b" if arm == "xdg" else home / ".local" / "state"
            env = {"HOME": str(home)}
            if arm == "xdg":
                env["XDG_STATE_HOME"] = str(base)
            real_mkdir = os.mkdir
            published = []

            def mkdir_spy(path, mode=0o777, *args, **kwargs):
                result = real_mkdir(path, mode, *args, **kwargs)
                published.append((Path(path), mode, stat.S_IMODE(os.stat(path).st_mode)))
                return result

            with self.subTest(arm=arm), \
                    mock.patch.object(self.mod.os, "mkdir", side_effect=mkdir_spy), \
                    mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A):
                self.mod.allocate_transcript(
                    "hash",
                    "COREDEV-2619",
                    "1",
                    "codex",
                    environ=env,
                    diagnostic_stream=io.StringIO(),
                )
            self.assertTrue(published)
            for path, requested, achieved in published:
                self.assertEqual(0o700, requested, str(path))
                self.assertEqual(0o700, achieved, str(path))

    def test_M1_18_launch_is_closed_then_owner_reopened_with_mode_and_payload_before_marker(self):
        """Rejects marker emission before the launch record is durable enough for owner reopen."""
        base = self.root / "state"
        events = []
        launch_fds = set()
        real_open = os.open
        real_close = os.close

        def open_spy(path, flags, mode=0o777, *args, **kwargs):
            path_string = os.fspath(path)
            is_launch = path_string.endswith(".launch")
            if is_launch and flags & os.O_CREAT:
                events.append("launch-create")
            elif is_launch:
                launch_path = Path(path_string)
                self.assertEqual(0o600, _mode(launch_path))
                self.assertEqual((RUN_A + "\n").encode("ascii"), launch_path.read_bytes())
                events.append("launch-reopen")
            fd = real_open(path, flags, mode, *args, **kwargs)
            if is_launch and flags & os.O_CREAT:
                launch_fds.add(fd)
            return fd

        def close_spy(fd):
            if fd in launch_fds:
                events.append("launch-close")
                launch_fds.remove(fd)
            return real_close(fd)

        class MarkerStream(io.StringIO):
            def write(self, value):
                if value.startswith("UNLEASHED_TRANSCRIPT="):
                    events.append("marker")
                return super().write(value)

        stdout = MarkerStream()
        with mock.patch.object(self.mod.os, "open", side_effect=open_spy), \
                mock.patch.object(self.mod.os, "close", side_effect=close_spy), \
                mock.patch.object(self.mod, "_generate_run_id", return_value=RUN_A), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            status = self.mod.cli_main(self.cli_args(), environ=self.env_for(base))
        self.assertEqual(0, status)
        self.assertLess(events.index("launch-create"), events.index("launch-close"))
        self.assertLess(events.index("launch-close"), events.index("launch-reopen"))
        self.assertLess(events.index("launch-reopen"), events.index("marker"))

    def test_M1_18_synchronized_first_run_processes_get_distinct_leaves_on_both_arms_and_parent_case(self):
        """Rejects race-fragile first-run mkdir logic and process-local run identifiers."""
        cases = []
        xdg_absent = self.root / "race-xdg" / "a" / "b"
        cases.append(("xdg-absent", {"HOME": str(self.home), "XDG_STATE_HOME": str(xdg_absent)}))

        fallback_home = self.root / "race-fallback-home"
        fallback_home.mkdir(mode=0o700)
        cases.append(("fallback-absent", {"HOME": str(fallback_home)}))

        existing_xdg = self.root / "race-existing-xdg"
        existing_xdg.mkdir(mode=0o755)
        cases.append(("nested-parent-absent", {"HOME": str(self.home), "XDG_STATE_HOME": str(existing_xdg)}))

        waiter = """\
import os
import pathlib
import sys
import time

pathlib.Path(os.environ["READY"]).touch()
go = pathlib.Path(os.environ["GO"])
deadline = time.monotonic() + 10
while not go.exists() and time.monotonic() < deadline:
    time.sleep(0.01)
if not go.exists():
    raise SystemExit("barrier timeout")
os.execv(sys.executable, [sys.executable, os.environ["PTY"]] + sys.argv[1:])
"""
        for case_name, base_env in cases:
            with self.subTest(case=case_name):
                go = self.root / f"{case_name}.go"
                processes = []
                ready_paths = []
                for index in range(2):
                    ready = self.root / f"{case_name}.{index}.ready"
                    ready_paths.append(ready)
                    env = dict(os.environ)
                    env.update(base_env)
                    env.update({"READY": str(ready), "GO": str(go), "PTY": str(PTY)})
                    processes.append(
                        subprocess.Popen(
                            [sys.executable, "-c", waiter, *self.cli_args()],
                            cwd=str(REPO),
                            env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                    )
                deadline = time.monotonic() + 10
                while not all(path.exists() for path in ready_paths) and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(all(path.exists() for path in ready_paths), "both allocators reached the barrier")
                go.touch()
                results = [process.communicate(timeout=15) for process in processes]
                self.assertEqual([0, 0], [process.returncode for process in processes], results)
                markers = [stdout.strip() for stdout, _stderr in results]
                self.assertTrue(all(marker.startswith("UNLEASHED_TRANSCRIPT=") for marker in markers), results)
                paths = [Path(marker.split("=", 1)[1]) for marker in markers]
                self.assertNotEqual(paths[0], paths[1])
                self.assertTrue(all(path.exists() and Path(str(path) + ".launch").exists() for path in paths))


def _rmtree_quiet(path: str) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


class SymlinkedAllocatorParentProofs(unittest.TestCase):
    """PR #63 second-round review: `os.stat()` followed a symlinked state component.

    `$XDG_STATE_HOME/unleashed-mail` being a SYMLINK to a 0700 same-owner directory satisfied every
    check, because `os.stat()` reports the TARGET. The mode of the target says nothing about who can
    replace the link — and whoever can replace it retargets every future allocation. `lstat` reports
    S_IFLNK, so the existing S_ISDIR test rejects it with no new branch.
    """

    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location("_pc_symlink_parent", str(PTY))
        self.mod = importlib.util.module_from_spec(spec)
        sys.modules["_pc_symlink_parent"] = self.mod
        spec.loader.exec_module(self.mod)
        self.root = tempfile.mkdtemp()
        self.addCleanup(_rmtree_quiet, self.root)

    def test_a_real_private_directory_is_accepted(self) -> None:
        """Deletion test: the guard must be conditional, not reject every directory."""
        path = os.path.join(self.root, "real")
        os.mkdir(path, 0o700)
        self.mod._validate_existing_private_directory(path)

    def test_a_symlink_to_a_private_directory_is_rejected(self) -> None:
        target = os.path.join(self.root, "target")
        os.mkdir(target, 0o700)
        link = os.path.join(self.root, "link")
        os.symlink(target, link)
        with self.assertRaises(self.mod.AllocationError):
            self.mod._validate_existing_private_directory(link)

    def test_a_loose_mode_directory_is_still_rejected(self) -> None:
        """The pre-existing 0700 requirement must survive the lstat change."""
        path = os.path.join(self.root, "loose")
        os.mkdir(path, 0o755)
        with self.assertRaises(self.mod.AllocationError):
            self.mod._validate_existing_private_directory(path)

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
