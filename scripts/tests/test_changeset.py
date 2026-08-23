#!/usr/bin/env python3
"""Base resolution and refusal in `changeset.sh` — a file no test had ever executed.

`scripts/review/changeset.sh` is `pr-review` Step 1: it resolves the review base and reports the
changeset the entire review is then performed against. Its only gate in CI is the
`shellcheck scripts/review/*.sh` step — a linter, which passes on every mutant below. Deleting the
proper-ancestor check leaves the whole suite green while `changeset.sh files` prints its heading and
NO FILES: `pr-review` approves having inspected nothing (P1, reproduced).

Every cell asserts the DIAGNOSTIC or the FILE LIST, never merely the exit status. The empty-range
fail-open exits 0, and the mutants that do exit non-zero mostly die at the NEXT guard
(`resolved base is not a commit`), so a cell checking only `returncode` passes against them and
proves nothing. Each refusal cell is paired with a MUTANT CONTROL that removes the guard and shows
the fail-open actually happening — without it, a cell cannot distinguish a working guard from a
script that refuses everything.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHANGESET = REPO / "scripts" / "review" / "changeset.sh"
FINGERPRINT = REPO / "scripts" / "review" / "tree-fingerprint.sh"

GIT = shutil.which("git")

# A `git` that fails only for `diff`, so `_diff_or_die` can be reached with base resolution intact.
GIT_DIFF_FAILS = """#!/usr/bin/env bash
if [ "${{1-}}" = "diff" ]; then echo "fatal: simulated diff failure" >&2; exit 128; fi
exec {real} "$@"
"""


@unittest.skipUnless(CHANGESET.is_file(), "changeset.sh not present")
@unittest.skipUnless(GIT and shutil.which("bash"), "needs git and bash")
class ChangesetFixture(unittest.TestCase):
    """A throwaway origin + worktree, hermetic against the developer's own git configuration."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="changeset-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        # HOME is redirected so neither the fixture nor the run under test can read — or be steered
        # by — the developer's ~/.gitconfig (hooks, aliases, init.defaultBranch, merge drivers).
        self.home = self.d / "home"
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.pop("XDG_CONFIG_HOME", None)
        # LC_ALL is pinned because cells below assert on system error text (`No such file or
        # directory`); under a translated locale those assertions would quietly stop discriminating.
        self.env.update(HOME=str(self.home), GIT_CONFIG_NOSYSTEM="1", LC_ALL="C", LANG="C")

    def git(self, *args, cwd=None):
        return subprocess.run(
            [GIT, "-c", "user.email=t@example.invalid", "-c", "user.name=T",
             "-c", "commit.gpgsign=false", "-c", "gc.auto=0", *args],
            cwd=str(cwd if cwd is not None else self.wt), env=self.env,
            capture_output=True, text=True, check=True,
        )

    def commit(self, name, text="x\n"):
        (self.wt / name).write_text(text, encoding="utf-8")
        self.git("add", "--", name)
        self.git("commit", "-qm", "add " + name)

    def build(self):
        """`origin` + a `1.04/feature` branch two commits ahead of `main`.

        This is the shape `detect_base` is written for: the version branch `1.04.0000` is a proper
        ancestor, so an unmutated run resolves `origin/1.04.0000` and reports both feature commits.
        """
        self.origin = self.d / "origin.git"
        self.wt = self.d / "wt"
        self.git("init", "-q", "--bare", str(self.origin), cwd=self.d)
        self.git("init", "-q", "-b", "main", str(self.wt), cwd=self.d)
        self.commit("a.txt")
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin", "main")
        self.git("branch", "1.04.0000")
        self.git("push", "-q", "origin", "1.04.0000")
        self.git("checkout", "-q", "-b", "1.04/feature")
        self.commit("b.txt")
        self.commit("c.txt")

    def run_changeset(self, mode, script=None, env=None, cwd=None):
        result = subprocess.run(
            ["bash", str(script or CHANGESET), mode],
            cwd=str(cwd if cwd is not None else self.wt), env=env if env is not None else self.env,
            capture_output=True, text=True, check=False, input="",
        )
        return result, result.stdout + result.stderr

    def mutant(self, old, new, *, count=1):
        """A copy of `changeset.sh` with `old` replaced by `new`, beside the sibling it sources.

        The replacement is asserted to land exactly `count` times and to PRESERVE THE LINE COUNT: a
        mutation that changes the file's length is a different experiment, because it reddens
        line-pinned tests for reachability rather than for the behaviour under test.
        """
        mdir = self.d / "mutant"
        mdir.mkdir(exist_ok=True)
        original = CHANGESET.read_text(encoding="utf-8")
        self.assertEqual(count, original.count(old),
                         "anchor %r appears %d times, expected %d"
                         % (old, original.count(old), count))
        mutated = original.replace(old, new)
        self.assertEqual(original.count("\n"), mutated.count("\n"),
                         "the mutation changed the line count")
        path = mdir / "changeset.sh"
        path.write_text(mutated, encoding="utf-8")
        shutil.copy2(FINGERPRINT, mdir / "tree-fingerprint.sh")
        return path


class TheReviewBaseMustBeAProperAncestorOfHead(ChangesetFixture):
    """`changeset.sh:61-64`. The guard that stops an empty diff range.

    `git merge-base A B` succeeds whenever the two share ANY common ancestor, which a version branch
    that has advanced past — or been fast-forwarded onto — the feature branch still does. The base
    then "resolves", the diff range collapses, and the review covers nothing.
    """

    def setUp(self):
        super().setUp()
        self.build()

    def test_a_version_base_FAST_FORWARDED_TO_HEAD_is_rejected(self):
        """The equality clause (`:64`). A base that IS HEAD is an ancestor of HEAD, so
        `--is-ancestor` alone accepts it and the range is still empty."""
        self.git("branch", "-f", "1.04.0000", "HEAD")
        self.git("push", "-qf", "origin", "1.04.0000")
        result, out = self.run_changeset("files")
        self.assertEqual(0, result.returncode, out)
        self.assertNotIn("Base: origin/1.04.0000", out)
        self.assertIn("b.txt", out)
        self.assertIn("c.txt", out)

    def test_the_equality_clause_REMOVED_reports_an_empty_changeset(self):
        """The mutant control for the cell above: without it, that cell would also pass against a
        `_usable_base` that rejected everything."""
        self.git("branch", "-f", "1.04.0000", "HEAD")
        self.git("push", "-qf", "origin", "1.04.0000")
        script = self.mutant(
            '    [ "$(git rev-parse "$1")" != "$(git rev-parse HEAD)" ]',
            "    true",
        )
        result, out = self.run_changeset("files", script=script)
        self.assertEqual(0, result.returncode, out)
        self.assertIn("Base: origin/1.04.0000", out)
        self.assertNotIn("b.txt", out)
        self.assertNotIn("c.txt", out)

    def test_a_version_base_ADVANCED_PAST_the_branch_is_rejected(self):
        """`--is-ancestor` (`:63`), isolated from the equality clause: this base is a DESCENDANT of
        HEAD, so it is not equal to HEAD and only the ancestry question rejects it."""
        self.git("branch", "-f", "1.04.0000", "HEAD")
        self.git("checkout", "-q", "1.04.0000")
        self.commit("d.txt")
        self.git("checkout", "-q", "1.04/feature")
        self.git("push", "-qf", "origin", "1.04.0000")
        result, out = self.run_changeset("files")
        self.assertEqual(0, result.returncode, out)
        self.assertNotIn("Base: origin/1.04.0000", out)
        self.assertIn("b.txt", out)
        self.assertIn("c.txt", out)

    def test_the_is_ancestor_check_REMOVED_reports_an_empty_changeset(self):
        """The mutant control for the cell above."""
        self.git("branch", "-f", "1.04.0000", "HEAD")
        self.git("checkout", "-q", "1.04.0000")
        self.commit("d.txt")
        self.git("checkout", "-q", "1.04/feature")
        self.git("push", "-qf", "origin", "1.04.0000")
        script = self.mutant(
            '    git merge-base --is-ancestor "$1" HEAD >/dev/null 2>&1 || return 1',
            "    :",
        )
        result, out = self.run_changeset("files", script=script)
        self.assertEqual(0, result.returncode, out)
        self.assertIn("Base: origin/1.04.0000", out)
        self.assertNotIn("b.txt", out)
        self.assertNotIn("c.txt", out)

    def test_a_USABLE_version_base_is_still_accepted(self):
        """The positive control: the guard must not reject the ordinary case it exists to serve."""
        result, out = self.run_changeset("files")
        self.assertEqual(0, result.returncode, out)
        self.assertIn("Base: origin/1.04.0000", out)
        self.assertIn("b.txt", out)
        self.assertIn("c.txt", out)


class TheChangesetOperandGuards(ChangesetFixture):
    """`changeset.sh:40-45`. The mode allowlist and the repository precondition."""

    def setUp(self):
        super().setUp()
        self.build()

    def test_an_UNKNOWN_mode_is_refused(self):
        result, out = self.run_changeset("bogusmode")
        self.assertNotEqual(0, result.returncode, out)
        self.assertIn("pr-review changeset: usage: changeset.sh files|stat|untested|base", out)

    def test_NO_operand_is_refused(self):
        result = subprocess.run(
            ["bash", str(CHANGESET)], cwd=str(self.wt), env=self.env,
            capture_output=True, text=True, check=False, input="",
        )
        out = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, out)
        self.assertIn("pr-review changeset: usage: changeset.sh files|stat|untested|base", out)

    def test_running_OUTSIDE_a_repository_is_refused(self):
        """The refusal is matched through the `die()` PREFIX, not the bare phrase.

        `git rev-parse` emits its own `fatal: not a git repository (or any of the parent
        directories)` when this guard is removed, so a cell asserting the bare phrase is satisfied by
        GIT'S message and passes against the mutant. Measured: with the guard deleted this cell
        survived until the assertion was pinned to `pr-review changeset:`.
        """
        plain = self.d / "plain"
        plain.mkdir()
        result, out = self.run_changeset("files", cwd=plain)
        self.assertNotEqual(0, result.returncode, out)
        self.assertIn("pr-review changeset: not a git repository", out)

    def test_the_repository_check_REMOVED_dies_somewhere_else(self):
        """The mutant control. It also shows why the exit status cannot carry this cell: without the
        guard the run still exits non-zero, at the unresolvable-base refusal further down."""
        script = self.mutant(
            'git rev-parse --git-dir >/dev/null 2>&1 || die "not a git repository"', ':')
        plain = self.d / "plain2"
        plain.mkdir()
        result, out = self.run_changeset("files", script=script, cwd=plain)
        self.assertNotEqual(0, result.returncode, out)
        self.assertNotIn("pr-review changeset: not a git repository", out)


class TheUnresolvableBaseIsRefused(ChangesetFixture):
    """`changeset.sh:115`. With no remote and no local `main`, `detect_base` returns the empty
    string rather than inventing `main` — and the caller must stop there.

    Asserting only `returncode != 0` proves nothing: with this condition removed the run still
    exits 1, at the `resolved base is not a commit` backstop two lines later. The cell therefore
    also asserts that the backstop is NOT what fired.
    """

    def setUp(self):
        super().setUp()
        self.wt = self.d / "norem"
        self.git("init", "-q", "-b", "feature", str(self.wt), cwd=self.d)
        self.commit("a.txt")
        self.commit("b.txt")

    def test_a_branch_with_no_resolvable_base_is_refused(self):
        result, out = self.run_changeset("files")
        self.assertNotEqual(0, result.returncode, out)
        self.assertIn("pr-review changeset: could not resolve a base branch", out)
        self.assertIn("refusing to review a narrowed range", out)
        self.assertNotIn("resolved base is not a commit", out)
        self.assertNotIn("=== Changed files ===", out)

    def test_the_refusal_REMOVED_falls_through_to_the_backstop(self):
        """The mutant control: it distinguishes the guard under test from the next one."""
        script = self.mutant(
            '[ -n "$BASE_BRANCH" ] || die "could not resolve a base branch',
            '[ -n "$BASE_BRANCH" ] || : "could not resolve a base branch',
        )
        result, out = self.run_changeset("files", script=script)
        self.assertNotEqual(0, result.returncode, out)
        self.assertNotIn("refusing to review a narrowed range", out)
        self.assertIn("resolved base is not a commit", out)


class ChangesetRefusesAnUnreadableDiff(ChangesetFixture):
    """`changeset.sh:139-140`. `_diff_or_die` is the last refusal between a real git error and
    `pr-review` reporting a clean pass over a changeset it never read.

    The section heading is printed BEFORE the diff runs, so a cell asserting only that output
    appeared passes against the mutant; and `untested` exits 0 either way. The message is the
    discriminator.
    """

    def setUp(self):
        super().setUp()
        self.build()
        self.stub = self.d / "stub"
        self.stub.mkdir()
        shim = self.stub / "git"
        shim.write_text(GIT_DIFF_FAILS.format(real=GIT), encoding="utf-8")
        shim.chmod(0o755)
        # `os.defpath` rather than `""` — see the note in test_isolated_harness_preconditions.py.
        self.shim_env = dict(self.env,
                             PATH=str(self.stub) + os.pathsep + self.env.get("PATH", os.defpath))

    def test_every_diffing_mode_refuses_rather_than_narrowing(self):
        for mode in ("files", "stat", "untested"):
            with self.subTest(mode=mode):
                result, out = self.run_changeset(mode, env=self.shim_env)
                self.assertNotEqual(0, result.returncode, out)
                self.assertIn("refusing to report a narrowed range", out)

    def test_the_refusal_REMOVED_reports_an_empty_changeset_and_exits_zero(self):
        """The mutant control: without it, the cell above would pass against a script that refused
        every diff, including the ones it should report."""
        script = self.mutant('|| die "could not diff', '|| : "could not diff')
        result, out = self.run_changeset("files", script=script, env=self.shim_env)
        self.assertEqual(0, result.returncode, out)
        self.assertNotIn("refusing to report a narrowed range", out)
        self.assertIn("=== Changed files ===", out)


class TheScratchAllocationIsGuarded(ChangesetFixture):
    """`changeset.sh:158-159`. `untested` writes the diff to a scratch file so the failure lands in
    the shell that can stop — which only works if the allocation itself is checked.

    TMPDIR points at a directory that DOES NOT EXIST rather than an unwritable one: an unwritable
    directory is still writable to uid 0, so that fixture would silently stop testing anything in a
    root CI container.
    """

    def setUp(self):
        super().setUp()
        self.build()
        self.tmp_env = dict(self.env, TMPDIR=str(self.d / "no-such-directory"))

    def test_an_unallocatable_scratch_file_is_refused(self):
        result, out = self.run_changeset("untested", env=self.tmp_env)
        self.assertNotEqual(0, result.returncode, out)
        self.assertIn("pr-review changeset: could not allocate a scratch file for the changed-file list", out)

    def test_the_allocation_check_REMOVED_loses_the_DIAGNOSTIC_not_the_exit_status(self):
        """The mutant control — and it documents a limit worth stating plainly.

        Removing this check does NOT produce a clean exit 0. `$CHANGED_LIST` is then the empty
        string, bash refuses the `> ""` redirect on the next line and again at `done < ""`, and the
        script ends non-zero on the status of that last failed redirect. So the EXIT STATUS DOES NOT
        DISTINGUISH the guard from its absence, and a cell asserting only `returncode != 0` would
        pass against the mutant — which is exactly why the cell above asserts the message.

        What the guard actually buys is the named failure and an intentional stop: the mutant
        reports two cryptic `No such file or directory` lines against an empty filename, at line
        numbers pointing at the redirect rather than the allocation, and never says that the scratch
        file could not be allocated. (Measured, not assumed: the first draft of this cell asserted
        exit 0 and was wrong.)
        """
        script = self.mutant(
            '|| die "could not allocate a scratch file',
            '|| : "could not allocate a scratch file',
        )
        result, out = self.run_changeset("untested", script=script, env=self.tmp_env)
        self.assertNotEqual(0, result.returncode, out)
        self.assertNotIn("could not allocate a scratch file", out)
        self.assertIn("No such file or directory", out)


if __name__ == "__main__":
    unittest.main()
