#!/usr/bin/env python3
"""`validate-plan-citations.py --fix-citations` FAILS when an anchor cannot be repaired.

THE FINDING (codex, PR #67 pass 9). An anchor that matched zero or several lines was reported as
`STALE RULE` and then fell through to the ordinary lint — which can pass, because the citation may
still point at ONE line that matches — so a caller read "fixed" off exit 0 while nothing had been
rewritten. The repair now exits 1 with `PLAN CITATION REPAIR FAILED` in that case; a clean plan
still repairs-and-lints to exit 0.

The fixture is a COPY of the real plan (the linter's cross-file rules resolve against `--repo .`,
so the run's cwd is the repository root); the duplicate is the §5 inert-gate anchor appended at EOF,
which is exactly "one anchor, two matches".

ONE NEGATION EXEMPTS ONE REFERENCE (codex, PR #67 pass 13 — reproduced). The correction exemption
(`… does not exist`) was scoped to the sentence, and a symmetric clause split still handed the text
BETWEEN two citations to both of them: `§9.9z of the journal plan does not exist, but this rule relies
on §9.8z of the journal plan.` exempted §9.8z on §9.9z's negation. The window is asymmetric now — a
POST-position negation belongs to the citation it follows, a PRE-position form to the 40 characters
before — so §9.8z is reported and §9.9z is not. The control (the POST regex applied to the pre-window
as well) is RUN on the same fixture and reports neither. The plain lint is used, not `--fix-citations`:
the inserted lines shift the copy's internal line pins, so the run fails on those too and only the two
named `[cite-external]` lines are asserted.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINTER = os.path.join(REPO, "scripts", "validate-plan-citations.py")
PLAN = os.path.join(REPO, "docs", "planning", "COREDEV-2617_PLUGIN_STATE_BASE_DIR_PLAN.md")
ANCHOR = "| The gate goes inert"


class FixCitationsExitCode(unittest.TestCase):
    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="plan-lint.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.copy = os.path.join(self.scratch, "plan.md")
        shutil.copy(PLAN, self.copy)

    def _run(self):
        return subprocess.run(["python3", LINTER, self.copy, "--fix-citations"],
                              cwd=REPO, capture_output=True, text=True, check=False)

    def test_an_ambiguous_anchor_fails_the_repair(self):
        with open(self.copy, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        hits = [l for l in lines if l.startswith(ANCHOR)]
        self.assertEqual(1, len(hits), f"the fixture plan must carry the anchor exactly once: {len(hits)}")
        with open(self.copy, "a", encoding="utf-8") as fh:
            fh.write(hits[0] + "\n")                        # now two lines match the §5 rule
        p = self._run()
        self.assertNotEqual(0, p.returncode, f"an unrepaired anchor exited 0:\n{p.stdout}{p.stderr}")
        self.assertIn("PLAN CITATION REPAIR FAILED", p.stdout, p.stdout + p.stderr)
        self.assertIn("§5 inert-gate row", p.stdout, "the failure does not name the ambiguous rule")

    def test_a_clean_plan_repairs_and_lints_to_exit_0(self):
        p = self._run()
        self.assertEqual(0, p.returncode, f"the untouched plan copy did not pass:\n{p.stdout}{p.stderr}")
        self.assertNotIn("PLAN CITATION REPAIR FAILED", p.stdout)
        self.assertIn("plan lint OK", p.stdout, p.stdout)


class OneNegationExemptsOneReference(unittest.TestCase):
    """The pass-13 laundering shape: one negation, TWO external references in one sentence."""

    SENTENCE = "§9.9z of the journal plan does not exist, but this rule relies on §9.8z of the journal plan.\n\n"
    HEADING = "## 5. Risk register"
    REPORTED_98 = "§9.8z of the journal plan does NOT exist"
    REPORTED_99 = "§9.9z of the journal plan does NOT exist"
    # The shipped exemption test, and the control's: the POST-position regex run over the PRE window too,
    # which hands `does not exist` — sitting between the two citations — to §9.8z as well.
    EXEMPTION_OLD = "            if _POST_NEGATION.search(post) or _PRE_NEGATION.search(pre):\n"
    EXEMPTION_NEW = "            if _POST_NEGATION.search(pre + post) or _PRE_NEGATION.search(pre):\n"

    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="plan-lint.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.copy = os.path.join(self.scratch, "plan.md")
        with open(PLAN, encoding="utf-8") as fh:
            src = fh.read()
        self.assertEqual(1, src.count(self.HEADING), "the fixture plan must carry the §5 heading exactly once")
        self.assertNotIn("§9.9z", src)
        self.assertNotIn("§9.8z", src)
        with open(self.copy, "w", encoding="utf-8") as fh:
            fh.write(src.replace(self.HEADING, self.SENTENCE + self.HEADING, 1))

    def _lint(self, linter=LINTER):
        """The plain lint of the copy — cwd is the repository root, so `--repo .` resolves the journal plan."""
        p = subprocess.run(["python3", linter, self.copy], cwd=REPO, capture_output=True, text=True, check=False)
        return p.returncode, p.stdout + p.stderr

    def _control_linter(self):
        with open(LINTER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.EXEMPTION_OLD), "the exemption line is not unique — the control is not the control")
        control = os.path.join(self.scratch, "validate-plan-citations-symmetric.py")
        with open(control, "w", encoding="utf-8") as fh:
            fh.write(text.replace(self.EXEMPTION_OLD, self.EXEMPTION_NEW, 1))
        return control

    def test_one_negation_does_not_exempt_two_references_in_a_sentence(self):
        rc, out = self._lint()
        self.assertNotEqual(0, rc, f"the fabricated §9.8z passed the lint:\n{out}")
        self.assertIn(self.REPORTED_98, out, f"§9.8z was exempted by §9.9z's negation:\n{out}")
        self.assertNotIn(self.REPORTED_99, out, f"§9.9z's own correction was reported as a claim:\n{out}")
        # The control: the negation between the citations exempts BOTH — neither is reported (measured), and
        # the run still exits non-zero on the shifted internal pins, so the status alone is not the oracle.
        rc2, out2 = self._lint(self._control_linter())
        self.assertNotEqual(0, rc2, out2)
        self.assertNotIn(self.REPORTED_98, out2,
                         f"the CONTROL (symmetric window) still reported §9.8z — the fixture is not the finding:\n{out2}")
        self.assertNotIn(self.REPORTED_99, out2, out2)



def _load_linter(path=None):
    """The validator is a script, not a module — load it by path so the predicate can be exercised
    directly. Everything else in this file drives it as a subprocess; these cells are about one
    regex's SCOPE, which a subprocess cannot show.

    `path` loads a MUTATED copy under its own module name, so a control and the specification can be
    held in one process at the same time (a shared name would return the first one from the cache and
    the control would silently be the specification)."""
    import importlib.util
    src = path or os.path.join(REPO, "scripts", "validate-plan-citations.py")
    name = "unleashed_plan_citations" if path is None else "upc_" + os.path.basename(src).replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PreNegationSeesOnlyWhatItsSliceContains(unittest.TestCase):
    """codex, PR #67 pass 18 — `_PRE_NEGATION` was written as `no §`, but `_sentence_around` ends the
    pre-slice AT the citation, so the slice never contains the `§`: the one form that alternative
    existed for (`cites no §9.9z of …`) could not match it, the reference was treated as live, and the
    CI plan gate failed on a valid document. Reproduced at the function level before the fix —
    pre=`'The design cites no '`, post=`' of the journal plan …'`, neither matching.

    The four cells below are the whole predicate: the two that MUST exempt, and the two that must NOT,
    because a negation matcher that exempts too much silently stops checking live citations. The
    anchoring to the slice's end is what the fourth cell holds — an unrelated `no` earlier in the
    sentence must not exempt the citation that follows it.
    """

    def _exempt(self, sentence):
        start = sentence.index("\u00a79.9z")
        end = start + len("\u00a79.9z")
        lint = _load_linter()
        post, pre = lint._sentence_around(sentence, start, end, [])
        return bool(lint._PRE_NEGATION.search(pre) or lint._POST_NEGATION.search(post))

    def test_a_citation_negated_only_by_a_preceding_no_is_exempt(self):
        self.assertTrue(self._exempt("The design cites no \u00a79.9z of the journal plan as authority."),
                        "the form the `no \u00a7` alternative was written for is still not exempt")

    def test_there_is_no_remains_exempt(self):
        self.assertTrue(self._exempt("There is no \u00a79.9z in that document."))

    def test_a_negation_that_modifies_something_else_does_not_exempt(self):
        r"""codex, PR #67 pass 19 — the FIRST fix anchored only its leading alternative and left
        `there is no|there was no` trailing and unanchored, so `there is no doubt: see §9.9z` exempted a
        live citation: the exact failure the anchoring was added to prevent, in the same commit that
        explained why it mattered. There is now ONE alternative, `\bno\s*$`, which subsumes both."""
        self.assertFalse(self._exempt("there is no doubt: see \u00a79.9z of the journal plan"),
                         "a negation modifying another noun exempted the citation after it")

    def test_a_live_citation_is_still_checked(self):
        self.assertFalse(self._exempt("See \u00a79.9z for the encoder rule."),
                         "a live citation was exempted — the linter would stop checking it")

    def test_an_unrelated_no_earlier_in_the_sentence_does_not_exempt(self):
        self.assertFalse(self._exempt("There are no fewer than three reasons; \u00a79.9z governs."),
                         "an unrelated `no` exempted a live citation — the matcher is not anchored")


class PostNegationStopsAtASubordinateClause(unittest.TestCase):
    r"""codex, PR #67 pass 20 — the post-citation slice ran to the end of the sentence, so a clause
    about something else laundered a fabricated citation: `This rule relies on §9.9z of the journal
    plan because the fallback does not exist.` was exempt, and the linter stopped checking a reference
    the sentence RELIES ON. The slice is now cut at a SUBORDINATING CONJUNCTION, because such a clause
    is about its own subject; `, which does not exist` — the form a real correction uses — is kept,
    because a relative pronoun refers BACK to the citation.

    The mutation is the cut itself (`post = _SUBORDINATOR.split(post, 1)[0]` removed), and it is applied
    to a COPY of the linter loaded by path, so both builds run the same predicate on the same strings.
    EVERY subordinator in the alternation is exercised: the pattern lists eight, and a cell that runs
    one proves one — the enumeration-is-not-the-class defect this campaign has hit before.
    """

    CUT = "    post = _SUBORDINATOR.split(post, 1)[0]\n"
    #: The two forms that MUST stay exempt. `, which …` is what a correction looks like; a negation that
    #: sits BEFORE the subordinator is inside the kept slice and must survive the cut.
    KEPT = ("This rule relies on §9.9z of the journal plan, which does not exist.",
            "§9.9z of the journal plan does not exist, because it was never written.")

    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="plan-lint.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.shipped = _load_linter()
        with open(LINTER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.CUT),
                         "the post-slice is not cut at a subordinating conjunction — a clause about "
                         "something else can exempt the citation it follows")
        copy = os.path.join(self.scratch, "validate-plan-citations-uncut.py")
        with open(copy, "w", encoding="utf-8") as fh:
            fh.write(text.replace(self.CUT, "", 1))
        self.mutant = _load_linter(copy)

    def _exempt(self, mod, sentence):
        start = sentence.index("§9.9z")
        end = start + len("§9.9z")
        post, pre = mod._sentence_around(sentence, start, end, [])
        return bool(mod._PRE_NEGATION.search(pre) or mod._POST_NEGATION.search(post))

    def test_a_negation_inside_a_subordinate_clause_does_not_exempt(self):
        for sub in ("because", "since", "so that", "although", "though", "unless", "whereas",
                    "as long as"):
            sentence = (f"This rule relies on §9.9z of the journal plan {sub} the fallback "
                        f"does not exist.")
            with self.subTest(subordinator=sub):
                self.assertFalse(self._exempt(self.shipped, sentence),
                                 f"`{sub}` laundered a fabricated citation the sentence relies on")
                self.assertTrue(self._exempt(self.mutant, sentence),
                                f"the CONTROL did not fail for `{sub}` — the uncut slice did not "
                                f"exempt it either, so this cell measures nothing")

    def test_a_relative_clause_correction_is_still_exempt(self):
        for sentence in self.KEPT:
            with self.subTest(sentence=sentence):
                self.assertTrue(self._exempt(self.shipped, sentence),
                                "the cut removed a correction the linter must not report")
                self.assertTrue(self._exempt(self.mutant, sentence),
                                "the fixture is not the finding: the uncut build did not exempt it either")


class ATopLevelSectionIsACitableShape(unittest.TestCase):
    """codex, PR #67 pass 20 — `EXTERNAL_RULES` required a DOT, so `§99 of the journal plan` produced
    ZERO checks and no problem, while the journal's own headings are `## 1` … `## 4`: the one citation
    form the pattern could not see was the one naming a whole section. Two halves, two mutants — the
    pattern (`\\d+(?:\\.\\d+[a-z]?)?`) and the heading lookup (`(?:[ .—-]|$)`), which accepts a
    top-level heading that ENDS THE LINE.

    Driven as a subprocess, like the other external-citation cells, because what is being asserted is
    what the RUN reports; the assertion COUNT is asserted beside it, so "not reported" cannot pass by
    the citation never having been checked.
    """

    HEADING = "## 5. Risk register"
    DOTTED_NEW = ('(r"§(\\d+(?:\\.\\d+[a-z]?)?) of the journal plan", '
                  '"docs/planning/DECISION_JOURNAL_PLAN.md", "journal plan"),')
    DOTTED_OLD = ('(r"§(\\d+\\.\\d+[a-z]?) of the journal plan", '
                  '"docs/planning/DECISION_JOURNAL_PLAN.md", "journal plan"),')
    HEAD_NEW = 'if re.search(rf"^#{{2,4}} {re.escape(sec)}(?:[ .—-]|$)", doc, re.M):'
    HEAD_OLD = 'if re.search(rf"^#{{2,4}} {re.escape(sec)}[ .—-]", doc, re.M):'

    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="plan-lint.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        with open(PLAN, encoding="utf-8") as fh:
            self.src = fh.read()
        self.assertEqual(1, self.src.count(self.HEADING),
                         "the fixture plan must carry the §5 heading exactly once")

    def _plan_citing(self, sec, name):
        """A copy of the plan with ONE sentence citing `§<sec> of the journal plan` inserted."""
        self.assertNotIn(f"§{sec} of the journal plan", self.src,
                         f"the plan already cites §{sec} — the fixture would not be the finding")
        path = os.path.join(self.scratch, name)
        sentence = f"The design follows §{sec} of the journal plan.\n\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.src.replace(self.HEADING, sentence + self.HEADING, 1))
        return path

    def _mutant(self, old, new, name):
        with open(LINTER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(old), f"the pinned line is not unique: {old!r}")
        path = os.path.join(self.scratch, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new, 1))
        return path

    def _lint(self, plan, linter=LINTER, repo=REPO):
        p = subprocess.run(["python3", linter, plan, "--repo", repo],
                           cwd=REPO, capture_output=True, text=True, check=False)
        out = p.stdout + p.stderr
        counts = [int(w) for l in out.splitlines() if "assertions" in l
                  for w in l.replace(",", " ").split() if w.isdigit()]
        return out, counts[-1] if counts else -1

    def test_an_absent_top_level_section_is_now_checked_and_reported(self):
        plan = self._plan_citing("99", "plan-99.md")
        msg = "§99 of the journal plan does NOT exist"
        out, n = self._lint(plan)
        self.assertIn(msg, out, f"a fabricated top-level citation was not reported:\n{out}")
        out2, n2 = self._lint(plan, self._mutant(self.DOTTED_NEW, self.DOTTED_OLD, "dotted-only.py"))
        self.assertNotIn(msg, out2,
                         f"the CONTROL did not fail — the dotted-only pattern reported it anyway:\n{out2}")
        self.assertEqual(n - 1, n2,
                         f"the dotted-only build checked the same number of things ({n2} vs {n}) — the "
                         f"citation was not being counted, so 'not reported' proves nothing")

    def test_a_real_top_level_section_passes_and_is_counted(self):
        # The honest control: §4 IS a heading in the journal (`## 4. Findings, fixes, and proofs`), so
        # the new pattern must CHECK it and find it. The count is asserted because "not reported" is
        # also what a citation nobody looked at produces.
        plan = self._plan_citing("4", "plan-4.md")
        out, n = self._lint(plan)
        self.assertNotIn("§4 of the journal plan does NOT exist", out,
                         f"a REAL top-level section was reported as fabricated:\n{out}")
        _, n2 = self._lint(plan, self._mutant(self.DOTTED_NEW, self.DOTTED_OLD, "dotted-only-4.py"))
        self.assertEqual(n - 1, n2, f"§4 was not checked by the shipped build ({n} vs {n2})")

    def test_a_heading_that_ends_the_line_is_found(self):
        # The second half. The journal's real headings all carry `. `, so the `$` branch needs a
        # synthetic journal: `## 7` ends its line, `## 8. Named` does not.
        repo = os.path.join(self.scratch, "synthrepo")
        os.makedirs(os.path.join(repo, "docs", "planning"))
        with open(os.path.join(repo, "docs", "planning", "DECISION_JOURNAL_PLAN.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("# Journal\n\n## 7\n\nbody\n\n## 8. Named\n")
        strict = self._mutant(self.HEAD_NEW, self.HEAD_OLD, "heading-strict.py")
        for sec, ends_the_line in (("7", True), ("8", False)):
            plan = self._plan_citing(sec, f"plan-syn-{sec}.md")
            msg = f"§{sec} of the journal plan does NOT exist"
            out, _ = self._lint(plan, repo=repo)
            self.assertNotIn(msg, out, f"§{sec} was reported although the synthetic journal has it:\n{out}")
            out2, _ = self._lint(plan, strict, repo=repo)
            if ends_the_line:
                self.assertIn(msg, out2,
                              f"the CONTROL did not fail — the strict lookup found `## {sec}` anyway:\n{out2}")
            else:
                self.assertNotIn(msg, out2,
                                 f"the strict lookup lost a heading with a trailing `. ` — the mutation "
                                 f"is not isolated to the line-ending form:\n{out2}")


if __name__ == "__main__":
    unittest.main()
