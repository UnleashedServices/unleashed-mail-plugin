#!/usr/bin/env python3
"""Runnable COREDEV-2619 S-M5 wrapper argument proof pairs."""

from __future__ import annotations

import subprocess
import unittest

try:
    from .test_m5_wrapper_contract import (
        CONTEXT_PATH,
        PATHS_PATH,
        REVIEWER_FLAG,
        M5WrapperFixture,
        _replace_once,
    )
except ImportError:  # Direct execution from scripts/tests.
    from test_m5_wrapper_contract import (
        CONTEXT_PATH,
        PATHS_PATH,
        REVIEWER_FLAG,
        M5WrapperFixture,
        _replace_once,
    )


class M53NamespaceProofs(M5WrapperFixture):
    def test_M5_3_assertion_helper_value_is_exact_and_stable(self) -> None:
        self.assert_hash_contract(self.wrapper_source, "hash-positive")

    def test_M5_3_mutations_bypass_change_or_ticket_mix_are_rejected(self) -> None:
        hash_argument = '        --repo-hash "$repo_hash" \\\n'
        mutations = {
            "helper-bypass": _replace_once(
                self.wrapper_source,
                'repo_hash="$(context_repo_hash)"',
                'repo_hash="Hardcoded.Hash"',
            ),
            "hash-substring": _replace_once(
                self.wrapper_source,
                hash_argument,
                '        --repo-hash "${repo_hash%%-*}" \\\n',
            ),
            "ticket-mixed": _replace_once(
                self.wrapper_source,
                hash_argument,
                '        --repo-hash "${repo_hash}-${ticket}" \\\n',
            ),
        }
        for label, source in mutations.items():
            with self.subTest(mutation=label):
                with self.assertRaises(AssertionError):
                    self.assert_hash_contract(source, "hash-" + label)


class M54CheckoutNamespaceProofs(M5WrapperFixture):
    def assert_checkout_namespace_contract(self, source: str, label: str) -> None:
        wrapper, _allocator, library = self.make_wrapper_tree(
            label,
            wrapper_source=source,
            context_source=CONTEXT_PATH.read_text(encoding="utf-8"),
        )
        (library / PATHS_PATH.name).write_text(
            PATHS_PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        env, _context_log, allocator_log = self.environment(label)

        checkouts = (
            self.root / (label + "-checkout-a"),
            self.root / (label + "-checkout-b"),
        )
        for checkout in checkouts:
            checkout.mkdir()
            initialized = subprocess.run(
                ["git", "init", "-q", str(checkout)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            result = self.invoke(
                wrapper,
                ["TicketSame", "RoundSame", "ReviewerSame"],
                env,
                cwd=str(checkout),
            )
            self.assertEqual(0, result.returncode, result.stderr)

        records = self.records(allocator_log)
        self.assertEqual(2, len(records))
        hashes = [record["argv"][2] for record in records]
        self.assertTrue(all(hashes))
        self.assertNotEqual(hashes[0], hashes[1])

    def test_M5_4_assertion_two_checkouts_receive_distinct_namespaces(self) -> None:
        self.assert_checkout_namespace_contract(
            self.wrapper_source,
            "checkout-positive",
        )

    def test_M5_4_constant_namespace_mutation_is_rejected(self) -> None:
        mutant = _replace_once(
            self.wrapper_source,
            'repo_hash="$(context_repo_hash)"',
            'repo_hash="fixed-checkout-hash"',
        )
        with self.assertRaises(AssertionError):
            self.assert_checkout_namespace_contract(mutant, "checkout-constant")


class M511SignatureProofs(M5WrapperFixture):
    def test_M5_11_assertion_exact_three_fields_and_no_invalid_allocation(self) -> None:
        self.assert_signature_contract(self.wrapper_source, "signature-positive")

    def test_M5_11_arity_empty_and_positional_mapping_mutations_are_rejected(self) -> None:
        empty_check = (
            'if [ -z "$ticket" ] || [ -z "$round_value" ] || '
            '[ -z "$reviewer" ]; then'
        )
        reviewer_argument = '        ' + REVIEWER_FLAG + ' "$reviewer"'
        mutations = {
            "extra-accepted": _replace_once(
                self.wrapper_source,
                '[ "$#" -ne 3 ]',
                '[ "$#" -lt 3 ]',
            ),
            "empty-ticket-accepted": _replace_once(
                self.wrapper_source,
                empty_check,
                'if [ -z "$reviewer" ]; then',
            ),
            "ticket-from-round": _replace_once(
                self.wrapper_source,
                '        --ticket "$ticket"',
                '        --ticket "$round_value"',
            ),
            "round-from-agent": _replace_once(
                self.wrapper_source,
                '        --round "$round_value"',
                '        --round "$reviewer"',
            ),
            "reviewer-from-ticket": _replace_once(
                self.wrapper_source,
                reviewer_argument,
                '        ' + REVIEWER_FLAG + ' "$ticket"',
            ),
        }
        for label, source in mutations.items():
            with self.subTest(mutation=label):
                with self.assertRaises(AssertionError):
                    self.assert_signature_contract(source, "signature-" + label)


class M512AllocatorShapeProofs(M5WrapperFixture):
    def test_M5_12_assertion_allocator_receives_the_exact_cli_shape(self) -> None:
        self.assert_allocator_shape(self.wrapper_source, "shape-positive")

    def test_M5_12_flag_and_extra_base_mutations_are_rejected(self) -> None:
        reviewer_argument = '        ' + REVIEWER_FLAG + ' "$reviewer"'
        hash_argument = '        --repo-hash "$repo_hash" \\\n'
        mutations = {
            "allocate-renamed": _replace_once(
                self.wrapper_source,
                "        --allocate \\\n",
                "        --reserve \\\n",
            ),
            "hash-flag-renamed": _replace_once(
                self.wrapper_source,
                "        --repo-hash \"$repo_hash\" \\\n",
                "        --hash \"$repo_hash\" \\\n",
            ),
            "ticket-flag-renamed": _replace_once(
                self.wrapper_source,
                '        --ticket "$ticket"',
                '        --issue "$ticket"',
            ),
            "round-flag-renamed": _replace_once(
                self.wrapper_source,
                '        --round "$round_value"',
                '        --iteration "$round_value"',
            ),
            "reviewer-flag-renamed": _replace_once(
                self.wrapper_source,
                reviewer_argument,
                '        --agent "$reviewer"',
            ),
            "base-added": _replace_once(
                self.wrapper_source,
                hash_argument,
                hash_argument + '        --base "$XDG_STATE_HOME" \\\n',
            ),
        }
        for label, source in mutations.items():
            with self.subTest(mutation=label):
                with self.assertRaises(AssertionError):
                    self.assert_allocator_shape(source, "shape-" + label)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
