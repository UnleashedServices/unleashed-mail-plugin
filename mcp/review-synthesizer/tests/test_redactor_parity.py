#!/usr/bin/env python3
"""Shell/Python redactor parity gate (COREDEV-2597 §4.4).

Drives BOTH implementations from the single canonical fixture in `redactor_fixture.py` — this is
the only place the two are compared, deliberately, because a per-side test cannot see divergence.

Mutation proofs this suite carries (each named test rejects a specific plausible-wrong
implementation, not merely a `git revert` — §3's second corollary):

  * drop `\\1` from a shell replacement        -> test_delimiters_are_byte_identical
  * anchor the secret rule only at `^`          -> test_secret_midstring_positive_controls
  * use `{9,}` instead of `{8,}`                -> test_secret_threshold_pair
  * a Unicode-aware Python guard `(?<!\\w)`      -> test_true_adjacency_non_ascii
  * ONE combined alternation instead of two     -> test_sequential_secret_passes
  * delete `-e ':t' -e 'tt'` from the tilde     -> test_tilde_loop
  * `[A-Za-z]` instead of `[A-Za-z_]`           -> test_tilde_underscore_leading_username
  * fold whitespace AFTER the rules             -> test_canonicalisation_closes_unicode_ws
  * re-add `re.IGNORECASE`                      -> test_no_unicode_case_folding
  * re-widen the tilde rule                     -> test_tilde_accepted_residuals
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PKG))
sys.path.insert(0, PKG)

import capture as C  # noqa: E402
import redactor_fixture as F  # noqa: E402

HOOK_IO = os.path.join(REPO, "scripts", "lib", "hook-io.sh")


def shell_redact(value: str) -> str:
    """Run the SHIPPED shell redactor. Never reimplement it here — that would test a copy."""
    return subprocess.run(
        ["bash", "-c", f'. "{HOOK_IO}"; hook_redact_pii "$1"', "_", value],
        capture_output=True, text=True,
    ).stdout


@unittest.skipUnless(os.path.exists(HOOK_IO), "hook-io.sh not found")
class RedactorParity(unittest.TestCase):
    """The whole fixture, both engines."""

    def test_must_agree_vectors_are_byte_identical(self):
        mismatches = []
        for value, note in F.MUST_AGREE:
            sh, py = shell_redact(value), C.redact_pii(value)
            if sh != py:
                mismatches.append(f"{value!r} ({note})\n     shell  {sh!r}\n     python {py!r}")
        self.assertEqual(
            [], mismatches,
            "shell/Python divergence on inputs required to agree:\n  " + "\n  ".join(mismatches),
        )

    def test_the_one_permanent_exemption_still_diverges(self):
        """If these start AGREEING the exemption was silently dropped, which is also a defect."""
        for value, note in F.EXEMPT:
            with self.subTest(value=value):
                sh, py = shell_redact(value), C.redact_pii(value)
                self.assertNotEqual(sh, py, f"exemption vanished for {value!r} ({note})")
                self.assertIn("[redacted-email]", sh, "shell should redact the asset filename")
                self.assertEqual(value, py, "Python should preserve the asset filename")

    def test_retina_generator_surface(self):
        """The exemption is an unbounded CLASS; sample every axis, not a memorised list."""
        for value in F.retina_generator():
            with self.subTest(value=value):
                self.assertEqual(value, C.redact_pii(value), "Python must preserve the whole class")


class SecretRule(unittest.TestCase):
    def test_secret_threshold_pair(self):
        """Rejects a `{9,}` mutant: 8 redacts, 7 does not."""
        self.assertEqual("[redacted-secret]", C.redact_pii("sk-abcdefgh"))
        self.assertEqual("sk-abcdefg", C.redact_pii("sk-abcdefg"))

    def test_secret_midstring_positive_controls(self):
        """Rejects a `^`-only mutant, which would leave a real secret untouched."""
        self.assertEqual("token [redacted-secret]", C.redact_pii("token sk-abcdefgh123"))
        self.assertEqual("token=[redacted-secret]", C.redact_pii("token=sk-abcdefgh123"))

    def test_delimiters_are_byte_identical(self):
        """Rejects a mutant that drops `\\1` and eats the boundary character."""
        self.assertEqual("([redacted-secret])", C.redact_pii("(pk_abcdefgh123)"))
        self.assertEqual("x-[redacted-secret]", C.redact_pii("x-sk-abcdefgh123"))

    def test_asymmetric_boundary_policy(self):
        """Underscore IS a boundary before sk-, and is NOT before pk_. Opposite directions."""
        self.assertEqual("foo_[redacted-secret]", C.redact_pii("foo_sk-abcdefgh123"))
        self.assertEqual("OPENAI_KEY_[redacted-secret]",
                         C.redact_pii("OPENAI_KEY_sk-proj-abcdefgh12345678"))
        self.assertEqual("orders_pk_customer_id_idx", C.redact_pii("orders_pk_customer_id_idx"))
        self.assertEqual("idx_pk_customer_id_lookup", C.redact_pii("idx_pk_customer_id_lookup"))

    def test_sequential_secret_passes(self):
        """Rejects ONE combined alternation, which matches greedily from the leading prefix."""
        self.assertEqual("[redacted-secret][redacted-secret]",
                         C.redact_pii("pk_abcdefgh-sk-ijklmnop"))

    def test_true_adjacency_non_ascii(self):
        """Rejects a Unicode-aware `(?<!\\w)` guard, which would preserve this entirely."""
        self.assertEqual("café[redacted-secret]", C.redact_pii("cafésk-abcdefgh123"))


class TildeRule(unittest.TestCase):
    def test_tilde_loop(self):
        """Rejects deleting `-e ':t' -e 'tt'`: a bare `g` leaves the second reference intact."""
        self.assertEqual("~[redacted]/~[redacted]/x", shell_redact("~a/~b/x"))
        self.assertEqual("~[redacted]/~[redacted]/x", C.redact_pii("~a/~b/x"))

    def test_tilde_underscore_leading_username(self):
        """Rejects an `[A-Za-z]` mutant, which would miss a valid contract input."""
        self.assertEqual("~[redacted]/x", C.redact_pii("~_daemon/x"))

    def test_tilde_requires_a_following_slash(self):
        self.assertEqual("~[redacted]/secrets", C.redact_pii("~alice/secrets"))
        self.assertEqual("~[redacted]/.ssh/id_rsa", C.redact_pii("~root/.ssh/id_rsa"))

    def test_tilde_preserves_approximations_and_swift(self):
        for v in ("~500ms", "~2x faster", "~40 percent", "~L147", "~Copyable", "~Escapable",
                  "~40/60 split", "split ~50/50", "cost ~$5"):
            with self.subTest(v=v):
                self.assertEqual(v, C.redact_pii(v))

    def test_tilde_accepted_residuals(self):
        """DELIBERATE. A bare `~user` and a digit-leading name are regex-indistinguishable from
        `~ten`/`~Copyable`, so catching them re-creates the corruption class this ticket removed.
        Changing these two lines is a SCOPE decision, not a bug fix — see COREDEV-2597 §2."""
        self.assertEqual("~alice", C.redact_pii("~alice"))
        self.assertEqual("~9lives/x", C.redact_pii("~9lives/x"))

    def test_tilde_before_secret_ordering_is_pinned(self):
        """Both rules match this input; the shipped order decides. Reordering changes output."""
        self.assertEqual("~[redacted]/", C.redact_pii("~sk-abcdefgh123/"))


class Canonicalisation(unittest.TestCase):
    def test_canonicalisation_closes_unicode_ws(self):
        """Rejects folding AFTER the rules, and rejects folding only \\n\\r\\t."""
        for ws in F.UNICODE_WS:
            with self.subTest(cp=f"U+{ord(ws):04X}"):
                self.assertEqual("[redacted-key]", C.redact_pii(f"api{ws}key: {F.SECRET}"))
                self.assertEqual("[redacted-token]", C.redact_pii(f"bearer{ws}{F.TOKEN20}"))

    def test_newline_spanning_secrets_are_caught(self):
        self.assertEqual("[redacted-key]", C.redact_pii("api\nkey: " + F.SECRET))
        self.assertEqual("[redacted-key]", C.redact_pii("api key:\n  s3cr3t-value"))

    def test_non_whitespace_codepoints_pass_through(self):
        """ZWSP/BOM/U+180E are NOT Unicode White_Space. Folding them would be a real widening."""
        for ws in F.NOT_WS:
            with self.subTest(cp=f"U+{ord(ws):04X}"):
                self.assertEqual(f"a{ws}b", C.redact_pii(f"a{ws}b"))

    def test_fold_is_one_to_one_not_run_collapsing(self):
        """`tr` is 1:1, so CRLF becomes TWO spaces. Rejects re-adding `+` to the Python fold."""
        self.assertEqual("a  b", C.redact_pii("a\r\nb"))


class UnicodeCaseFolding(unittest.TestCase):
    def test_no_unicode_case_folding(self):
        """Rejects re-adding `re.IGNORECASE`, which silently folds U+0131/U+0130/U+212A.

        Vectors are built with chr() and NOT pasted as source literals — pasting U+212A or
        U+0131 can normalise them to ASCII, and the assertion then proves nothing. This test
        failed exactly that way when first written.
        """
        dotless_i, kelvin = chr(0x0131), chr(0x212A)
        v1 = f"ap{dotless_i}_key: SECRETVALUE"
        v2 = f"api{kelvin}ey=SECRETVALUE"
        self.assertNotEqual(v1, "api_key: SECRETVALUE", "vector normalised to ASCII — test is inert")
        self.assertNotEqual(v2, "apiKey=SECRETVALUE", "vector normalised to ASCII — test is inert")
        self.assertEqual(v1, C.redact_pii(v1))
        self.assertEqual(v2, C.redact_pii(v2))
    def test_ascii_case_still_matches(self):
        self.assertEqual("[redacted-key]", C.redact_pii("API KEY: " + F.SECRET))
        self.assertEqual("[redacted-token]", C.redact_pii("BEARER " + F.TOKEN20))

    def test_bearer_literals_have_no_non_ascii_fold(self):
        """NEGATIVE CONTROL — b/e/a/r have no non-ASCII folds, so this must be preserved."""
        self.assertEqual("bKarer " + F.TOKEN20, C.redact_pii("bKarer " + F.TOKEN20))


class EmailLookahead(unittest.TestCase):
    def test_routable_address_is_not_exempted(self):
        """WAS A PYTHON LEAK: the lookahead's `\\b` was satisfied by the following dot, so a real
        address survived redaction entirely."""
        self.assertEqual("[redacted-email]", C.redact_pii("user@2x.png.example.com"))
        self.assertEqual("[redacted-email]", C.redact_pii("AppIcon@2x.png.bak"))

    def test_negative_controls(self):
        self.assertEqual("[redacted-email]", C.redact_pii("AppIcon@2X.png"))
        self.assertEqual("[redacted-email]", C.redact_pii("user@2xmail.com"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class EquivalenceModel(unittest.TestCase):
    """`redactor_model.py` is the mechanical closure argument (COREDEV-2597 §4.5).

    A static fixture cannot gate three unbounded generators, so the real invariant is an
    equivalence: the ONLY divergence between the two implementations is the `@Nx` retina lookahead.
    This runs a small corpus in-suite; CI runs a large one on both `ubuntu-latest` and
    `macos-latest`, because one known root cause (`tr` on invalid UTF-8) INVERTS by platform.
    """

    def test_equivalence_holds_on_a_seeded_corpus(self):
        import redactor_model as M
        self.assertEqual(0, M.run(count=1500, seed=20260729, verbose=False),
                         "UNEXPLAINED divergence — a new root cause exists; see stderr")

    def test_the_classifier_calls_the_shipped_function(self):
        """The classifier MUST NOT reimplement the pipeline.

        It did, in the first version of redactor_model.py, and that made the gate partially inert:
        two of four deliberate regressions (reverting the sequential secret passes, deleting the
        whitespace canonicalisation) changed the real output but not the reimplementation, which
        absorbed them as 'explained'. This asserts the classifier is sensitive to `redact_pii`'s
        BODY, not just to its compiled patterns.
        """
        import redactor_model as M
        probe = "pk_abcdefgh-sk-ijklmnop"
        real_shell = shell_redact(probe)
        # sanity: undisturbed, this input agrees, so it is not already "explained"
        self.assertEqual(real_shell, C.redact_pii(probe))
        original = C.redact_pii
        try:
            C.redact_pii = lambda s: "MUTANT"  # noqa: E731 - deliberate body swap
            self.assertFalse(
                M._email_lookahead_explains(probe, real_shell, "MUTANT"),
                "classifier ignored a mutated redact_pii body — it is reimplementing the pipeline",
            )
        finally:
            C.redact_pii = original


class COREDEV2609_ValueClassFolds(unittest.TestCase):
    """The api-key/bearer PAYLOAD carries the four fold codepoints; the ANCHOR does not.

    §3 forbids widening, because widening is how the `sk-`/`~` corruption classes were introduced.
    But those rules were UNANCHORED — a bare prefix could land mid-word. `_APIKEY`/`_BEARER` are
    anchored by a literal, so extending the PAYLOAD class cannot make correct text match: the
    `api key:` / `bearer ` anchor still has to be present. Widening the ANCHOR would be the same
    shape of change that caused the original corruption, so it is deliberately not done.
    """

    LONGS, DOTLESS, KELVIN = chr(0x017F), chr(0x0131), chr(0x212A)

    def test_the_worst_shape_is_closed(self):
        """Without the fold codepoints in the payload class the match STOPS at the first one and
        emits `[redacted-key]` immediately followed by LIVE SECRET MATERIAL — which passes any
        assertion of the form `'[redacted-key]' in output`."""
        v = f"api key: SECRET{self.LONGS}MORE"
        out = C.redact_pii(v)
        self.assertEqual("[redacted-key]", out)
        self.assertNotIn("MORE", out, "secret tail survived the placeholder")

    def test_bearer_payload_too(self):
        v = "bearer " + "a" * 19 + self.LONGS
        self.assertEqual("[redacted-token]", C.redact_pii(v))

    def test_fold_chars_mid_payload(self):
        v = f"api key: A{self.KELVIN}B{self.DOTLESS}CDEFGH"
        self.assertEqual("[redacted-key]", C.redact_pii(v))

    def test_the_anchor_is_NOT_widened(self):
        """ACCEPTED RESIDUAL, pinned. Changing these is a scope decision, not a bug fix: it widens
        the ANCHOR, and the residual is an evasion vector (someone must deliberately spell the
        literal with a fold-equivalent) rather than accidental leakage."""
        for v in (f"ap{self.DOTLESS}_key: SECRETVALUE", f"api{self.KELVIN}ey=SECRETVALUE"):
            with self.subTest(v=v):
                self.assertEqual(v, C.redact_pii(v))

    def test_correct_text_is_untouched_by_the_widening(self):
        """The whole safety argument: the anchor must still be present, so ordinary prose containing
        `api`, `key` or a lone fold character cannot match."""
        for v in ("the api keyboard is nice", "apiary keeper",
                  f"a {self.LONGS} standalone char", "bearer short"):
            with self.subTest(v=v):
                self.assertEqual(v, C.redact_pii(v))


class TestS3EquivalenceGateExitCode(unittest.TestCase):
    """S3 (COREDEV-2654): `redactor_model.run()`'s exit code is a REAL CI GATE — plugin-ci.yml runs
    `redactor_model.py --count 40000 --seed 20260729` and `--count 20000 --seed 31337` as two steps
    and gates on the status. Its fail-OPEN direction was unpinned: turning the unexplained-divergence
    `return 1` into `return 0` left the whole suite green, so a NEW root cause of shell/Python
    divergence could land with both CI steps passing.

    The corpus and the shell are patched out deliberately: this cell is about the EXIT CODE and the
    three-way classification (agree / exempt / unexplained), not about the redactors themselves —
    those are compared for real by the rest of this file, driven from the canonical fixture. A cell
    that shelled out 40000 times to assert `return 1` would be pinning the wrong thing slowly."""

    CORPUS = ["alpha beta", "gamma delta"]

    def _run(self, shell_out, explains=None):
        import redactor_model as M
        patches = [
            mock.patch.object(M, "build_corpus", lambda count, seed: list(self.CORPUS)),
            mock.patch.object(M, "shell_redact_batch", shell_out),
        ]
        if explains is not None:
            patches.append(mock.patch.object(M, "_email_lookahead_explains", explains))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as st:
            for p in patches:
                st.enter_context(p)
            st.enter_context(contextlib.redirect_stdout(out))
            st.enter_context(contextlib.redirect_stderr(err))
            rc = M.run(count=2, seed=1, verbose=False)
        return rc, out.getvalue(), err.getvalue()

    def test_full_agreement_exits_zero(self):
        rc, out, err = self._run(lambda vs: [C.redact_pii(v) for v in vs])
        self.assertIn("EQUIVALENCE HOLDS", out)
        self.assertIn("UNEXPLAINED         : 0", out)
        self.assertEqual(rc, 0, "a corpus the two implementations agree on must exit 0")
        self.assertEqual(err, "", "agreement must not write to stderr")

    def test_unexplained_divergence_exits_one_and_is_named(self):
        # THE fail-open direction. Without this, `return 1` -> `return 0` is a silent CI no-op.
        rc, out, err = self._run(lambda vs: ["TOTALLY-DIFFERENT" for _ in vs])
        self.assertIn("UNEXPLAINED         : 2", out)
        self.assertIn("a NEW root cause exists", err)
        self.assertIn("TOTALLY-DIFFERENT", err, "the diagnostic must show the diverging output")
        self.assertIn("alpha beta", err, "the diagnostic must show the offending input")
        self.assertEqual(rc, 1, "an unexplained divergence must FAIL the CI gate")

    def test_explained_divergence_is_exempt_and_still_exits_zero(self):
        # The narrowing half: a divergence the retina-lookahead exemption fully explains must NOT
        # red the gate, else the permanent exemption would break CI on every run. Asserting only
        # the failure direction would be satisfied by `return 1` unconditionally.
        rc, out, err = self._run(lambda vs: ["TOTALLY-DIFFERENT" for _ in vs],
                                 explains=lambda value, sh, py: True)
        self.assertIn("exempt (@Nx lookahead): 2", out)
        self.assertIn("UNEXPLAINED         : 0", out)
        self.assertIn("EQUIVALENCE HOLDS", out)
        self.assertEqual(rc, 0, "a fully-explained divergence must still exit 0")

    def test_verbose_prints_every_divergence_not_just_the_first_25(self):
        # The truncation arm: non-verbose caps the dump at 25 and says how many more. A silent cap
        # would make a 200-divergence regression look like a 25-divergence one.
        import redactor_model as M
        with mock.patch.object(M, "build_corpus", lambda count, seed: [f"v{i}" for i in range(30)]), \
             mock.patch.object(M, "shell_redact_batch", lambda vs: ["X" for _ in vs]):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(M.run(count=30, seed=1, verbose=False), 1)
            self.assertIn("… and 5 more (--verbose for all)", err.getvalue())
            out2, err2 = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out2), contextlib.redirect_stderr(err2):
                self.assertEqual(M.run(count=30, seed=1, verbose=True), 1)
            self.assertNotIn("more (--verbose for all)", err2.getvalue())
            self.assertGreater(err2.getvalue().count("shell "), err.getvalue().count("shell "))
