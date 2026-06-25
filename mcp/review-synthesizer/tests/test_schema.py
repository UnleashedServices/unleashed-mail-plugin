"""Schema validation / quarantine behaviour (schema.parse_finding)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema import CATEGORY_FAMILY, DISPLAY_BUCKET, Finding, SchemaError, parse_finding  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
