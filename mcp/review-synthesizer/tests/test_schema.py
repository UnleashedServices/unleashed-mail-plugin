"""Schema validation / quarantine behaviour (schema.parse_finding)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema import (CATEGORY_FAMILY, DISPLAY_BUCKET, Finding, SchemaError,  # noqa: E402
                    canonical_path, parse_finding)


def good(**over):
    d = dict(severity="warning", confidence="high", sourceAgent="security-reviewer",
             category="keychain", file="F.swift", line=10, lineEnd=12,
             finding="f", evidence="e", fix="x")
    d.update(over)
    return d


class TestParseFinding(unittest.TestCase):
    def test_valid(self):
        f = parse_finding(good())
        self.assertIsInstance(f, Finding)
        self.assertEqual(f.scope, "changeset")          # default
        self.assertEqual(f.family, "security")
        self.assertEqual(f.bucket, "Security")

    def test_not_a_dict_quarantines(self):
        with self.assertRaises(SchemaError):
            parse_finding([1, 2, 3])

    def test_missing_required_field(self):
        d = good()
        del d["fix"]
        with self.assertRaises(SchemaError):
            parse_finding(d)

    def test_bad_enums(self):
        for k, v in (("severity", "huge"), ("confidence", "meh"), ("category", "nope")):
            with self.assertRaises(SchemaError):
                parse_finding(good(**{k: v}))

    def test_non_string_field_quarantines(self):
        # the bug Codex caught: sourceAgent:int passed, then crashed rendering
        with self.assertRaises(SchemaError):
            parse_finding(good(sourceAgent=123))

    def test_empty_file_rejected(self):
        with self.assertRaises(SchemaError):
            parse_finding(good(file="   "))

    def test_digit_string_line_accepted(self):
        f = parse_finding(good(line="42", lineEnd="42"))   # reviewer-recall tolerance
        self.assertEqual((f.line, f.lineEnd), (42, 42))

    def test_whitespace_around_digit_string_is_tolerated(self):
        f = parse_finding(good(line=" 42 ", lineEnd="42\n"))
        self.assertEqual((f.line, f.lineEnd), (42, 42))

    def test_file_path_is_stored_trimmed(self):
        # "A.swift " must equal "A.swift" in $CHANGED, or a changeset blocker mis-scopes
        self.assertEqual(parse_finding(good(file="  A.swift  ")).file, "A.swift")

    def test_leading_dotslash_is_stripped(self):
        # reviewers copying from `find .` / `grep … .` produce ./-prefixed paths
        self.assertEqual(parse_finding(good(file="./Sources/A.swift")).file, "Sources/A.swift")
        self.assertEqual(parse_finding(good(file="././A.swift")).file, "A.swift")

    def test_backslashes_normalized_to_forward_slashes(self):
        self.assertEqual(parse_finding(good(file="Sources\\A.swift")).file, "Sources/A.swift")
        self.assertEqual(parse_finding(good(file=".\\A.swift")).file, "A.swift")

    def test_non_decimal_digit_string_rejected(self):
        # '²'.isdigit() is True but int('²') raises — isdecimal rejects it cleanly
        with self.assertRaises(SchemaError):
            parse_finding(good(line="²", lineEnd="1"))

    def test_float_line_rejected(self):
        # 1.9 must NOT silently truncate to line 1
        with self.assertRaises(SchemaError):
            parse_finding(good(line=1.9, lineEnd=1.9))

    def test_bool_line_rejected(self):
        with self.assertRaises(SchemaError):
            parse_finding(good(line=True, lineEnd=True))

    def test_nondigit_string_line_rejected(self):
        with self.assertRaises(SchemaError):
            parse_finding(good(line="x", lineEnd="1"))

    def test_negative_line_rejected(self):
        with self.assertRaises(SchemaError):
            parse_finding(good(line=-1, lineEnd=-1))

    def test_inverted_range_rejected(self):
        with self.assertRaises(SchemaError):
            parse_finding(good(line=50, lineEnd=40))

    def test_scope_validation(self):
        self.assertEqual(parse_finding(good(scope="structural-pipeline")).scope, "structural-pipeline")
        with self.assertRaises(SchemaError):
            parse_finding(good(scope="weird"))

    def test_every_category_has_a_display_bucket(self):
        for cat, fam in CATEGORY_FAMILY.items():
            self.assertIn(fam, DISPLAY_BUCKET, f"{cat} → family {fam} has no display bucket")


class TestNoDeadStrictToolForm(unittest.TestCase):
    def test_report_finding_tool_removed(self):
        # The strict-tool `REPORT_FINDING_TOOL` form was dead (its only consumer, a `reviewers.py`
        # API-tool-call path, never existed). Removed in Item 17 — guard against re-introduction.
        import schema
        self.assertFalse(hasattr(schema, "REPORT_FINDING_TOOL"))




class TestS7CanonicalPathDotsOnlyCollapse(unittest.TestCase):
    """S7 (COREDEV-2654): `canonical_path`'s dots-only collapse (schema.py:158) had NO direct cell —
    it was reached only incidentally through two of its four consumers, and `synthesize.py:270`
    inherited it untested.

    The collapse is what MAKES the two empty-changeset refusals work. Both of them test
    `{p for p in (canonical_path(c) for c in changed) if p}` for emptiness, so a `.`-only changeset
    is caught only because `canonical_path(".")` is FALSY. Remove the collapse and `{"."}` is a
    non-empty set of a truthy key: both refusals pass it through, nothing matches the placeholder,
    every finding scopes to pre-existing, and the verdict is a bogus APPROVE. Pinning it here pins
    the premise those guards rest on rather than re-deriving it at each call site."""

    #: `...` and `..` are in this list because `canonical_path` COLLAPSES them, not because they are
    #: placeholders — `...` is a legal POSIX filename that git emits verbatim (codex, PR #77). The
    #: list describes SHIPPED BEHAVIOUR; removing an entry without changing `schema.py` would just
    #: make the suite red. See the note at schema.py's collapse for why it was left alone.
    DOTS_ONLY = [".", "/", "./", "./.", ".//", "...", "..", "  .  ", "././", "//", ".\\", "\\"]

    def test_every_dots_only_spelling_collapses_to_empty(self):
        for raw in self.DOTS_ONLY:
            with self.subTest(raw=raw):
                self.assertEqual(canonical_path(raw), "",
                                 f"{raw!r} is a current-dir placeholder, never a real diff line")
                self.assertFalse(canonical_path(raw),
                                 "the refusal guards test FALSINESS — an empty string is the contract")

    def test_a_real_path_containing_dots_is_preserved(self):
        # The narrowing half. A collapse that returned "" for anything containing a dot would erase
        # ordinary filenames and scope every finding out — the same fail-open, arrived at backwards.
        for raw, want in [("Sources/Auth.swift", "Sources/Auth.swift"),
                          ("./Sources/Auth.swift", "Sources/Auth.swift"),
                          ("Sources/./Auth.swift", "Sources/Auth.swift"),
                          ("Sources//Auth.swift", "Sources/Auth.swift"),
                          ("a.b.c.swift", "a.b.c.swift"),
                          (".hidden/Auth.swift", ".hidden/Auth.swift"),
                          ("Sources/../Auth.swift", "Sources/../Auth.swift"),
                          ("/Users/n/Auth.swift", "/Users/n/Auth.swift")]:
            with self.subTest(raw=raw):
                self.assertEqual(canonical_path(raw), want)

    def test_a_dot_segment_preserves_the_traversal_it_is_not_responsible_for(self):
        # `..` is deliberately PRESERVED — `is_abs_or_traversal`, not this function, rejects
        # traversal. If the collapse swallowed `..` the traversal guard would receive a clean path
        # and admit it. The two functions must not both try to own this.
        self.assertEqual(canonical_path("../Auth.swift"), "../Auth.swift")
        self.assertTrue(canonical_path("/abs/Auth.swift").startswith("/"),
                        "a leading / must survive — capture.py's PII redactor keys on it")


class TestS7SynthesizeConsumerInheritsTheCollapse(unittest.TestCase):
    """S7 cont. — the untested consumer, `synthesize.py:270`. `synthesize()` is a library entry
    point: the MCP tool and the CLI both call it AFTER their own refusal, but a direct caller has
    no such guard, so the canonicalisation at :270 is the only thing standing between a
    placeholder changeset and a silently mis-scoped verdict."""

    def test_a_dot_only_changeset_scopes_nothing_into_gating(self):
        import synthesize as SY
        from schema import parse_finding as pf
        blocker = pf(dict(severity="blocker", confidence="high", sourceAgent="security-reviewer",
                          category="credential", file="A.swift", line=1, lineEnd=1,
                          finding="hardcoded key", evidence="e", fix="x"))
        r = SY.synthesize([blocker], {"."})
        self.assertEqual(r.clusters, [], "a placeholder changeset must gate nothing")
        self.assertEqual(len(r.pre_existing), 1)
        # `Review` deliberately does not expose the canonicalised set, so this cell can only observe
        # the OUTCOME. What pins :270 itself is the sibling cell below: `./A.swift` matching
        # `A.swift` is possible only if :270 canonicalised the changeset.

    def test_the_same_finding_gates_when_the_changeset_names_its_file(self):
        # Control — without it the cell above is satisfied by a synthesize() that gates NOTHING.
        import synthesize as SY
        from schema import parse_finding as pf
        blocker = pf(dict(severity="blocker", confidence="high", sourceAgent="security-reviewer",
                          category="credential", file="A.swift", line=1, lineEnd=1,
                          finding="hardcoded key", evidence="e", fix="x"))
        r = SY.synthesize([blocker], {"./A.swift"})
        self.assertEqual(len(r.clusters), 1, "a noncanonical but REAL entry must still match")
        self.assertEqual(r.pre_existing, [])
        self.assertEqual(r.verdict.decision, "REQUEST_CHANGES")


if __name__ == "__main__":
    unittest.main()
