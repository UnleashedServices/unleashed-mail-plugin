#!/usr/bin/env python3
"""The codex arm must review the authenticated bound plan, not the live, swappable file.

THE FINDING (PR #63 recheck, P1). `capture-codex-review.sh` ran `codex exec … -s read-only` in the LIVE
working tree, so the plan file codex opened was the mutable one. An A->B->A swap during codex's read
window let it review substituted bytes while `.plan` and the live plan both still hashed A, and
`review-verdict` authenticates only the live plan — so the artifact attested a plan the reviewer never
read. The gemini arm already isolated its review into a detached checkout with the authenticated
`.planbytes` staged; the codex arm never inherited it. It now runs `isolated-codex-review.sh`, which
uses the SHARED `stage-bound-plan.py` — so the fix cannot diverge between the two arms again.

The codex stub reads the plan from its cwd, exactly as `codex exec` does, and records what it saw.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAPTURE = REPO / "scripts" / "review" / "capture-codex-review.sh"

COMMITTED = "COMMITTED VERSION"
EDITED = "EDITED VERSION - not committed"
PROMPT_BODY = "Review the plan for correctness, security and completeness.\n" * 40

# codex exec is invoked by pty-capture as `codex exec -c … -s read-only "<prompt>"`, run from the
# disposable checkout. The stub records BOTH the plan bytes it sees AND its working directory — the
# directory is the deterministic discriminator: under isolation codex runs in a throwaway detached
# worktree, never the repo root, so the live plan it would otherwise open is out of reach.
CODEX_STUB = """#!/usr/bin/env bash
{ pwd; tail -1 docs/planning/FEATURE_PLAN.md 2>/dev/null || echo "<absent>"; } > "$UM_CODEX_SAW"
printf 'VERDICT: APPROVE\\n'
"""

# A REVIEWER THAT MISBEHAVES. The stub above only ever writes OUTSIDE the checkout, so it can never
# take any of the harness's six post-run round-VOID branches — which is why, before these cells, the
# codex arm had no test asserting that machinery at all while its agy twin had seven. Measured on
# PR #69: forcing the arm to VOID unconditionally (`if true`) left all fourteen codex-arm tests
# green, and a reachability probe showed the post-run block executes thirteen times across the suite
# with nothing asserting on it in either direction.
MUTATING_CODEX_STUB = """#!/usr/bin/env bash
%s
printf 'VERDICT: APPROVE\\n'
"""


class CodexReviewsTheBoundPlan(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="codex-bound-plan-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "docs" / "planning").mkdir(parents=True)
        self.plan = self.root / "docs" / "planning" / "FEATURE_PLAN.md"
        self.plan.write_text(f"# Plan\n{COMMITTED}\n", encoding="utf-8")
        prompt = self.root / ".codex-prompt-COREDEV-9999r1.md"
        prompt.write_text(PROMPT_BODY + "REVIEW TARGET: docs/planning/FEATURE_PLAN.md\n",
                          encoding="utf-8")
        for command in (["git", "init", "-q", "."],
                        ["git", "config", "user.email", "probe@test"],
                        ["git", "config", "user.name", "probe"],
                        ["git", "add", "-A"],
                        ["git", "commit", "-qm", "init"]):
            subprocess.run(command, cwd=self.root, check=True)
        # The uncommitted edit — the normal state during review iteration.
        self.plan.write_text(f"# Plan\n{EDITED}\n", encoding="utf-8")

        stubs = self.root / ".stubs"
        stubs.mkdir()
        (stubs / "codex").write_text(CODEX_STUB, encoding="utf-8")
        (stubs / "codex").chmod(0o755)

        self.saw = Path(tempfile.mkdtemp(prefix="codex-saw-")) / "SEEN.txt"
        self.addCleanup(shutil.rmtree, self.saw.parent, ignore_errors=True)
        self.env = dict(os.environ)
        self.env["PATH"] = f"{stubs}{os.pathsep}{self.env['PATH']}"
        self.env["XDG_STATE_HOME"] = str(self.root / "state")
        self.env["UM_CODEX_SAW"] = str(self.saw)
        self.env["UM_LIVE_ROOT"] = str(self.root)

    def capture(self, round_value: str):
        return subprocess.run(
            ["bash", str(CAPTURE), "COREDEV-9999", round_value,
             ".codex-prompt-COREDEV-9999r1.md", "docs/planning/FEATURE_PLAN.md", "30"],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=False, input="",
        )

    def install_mutating_stub(self, body: str) -> None:
        """Replace the well-behaved codex stub with one that tampers, then prints an APPROVAL.

        The approval matters: every cell below asserts the round is VOIDED despite the reviewer
        reporting success, which is the property the guards exist for.
        """
        stub = self.root / ".stubs" / "codex"
        stub.write_text(MUTATING_CODEX_STUB % body, encoding="utf-8")
        stub.chmod(0o755)

    def assert_voided(self, result, needle: str) -> None:
        self.assertEqual(3, result.returncode,
                         f"the round was not VOIDED (rc={result.returncode}):\n"
                         f"{result.stdout}{result.stderr}")
        self.assertIn(needle, result.stderr,
                      f"VOIDED, but not for the expected reason:\n{result.stdout}{result.stderr}")
        self.assertNotIn("TREE=clean", result.stdout,
                         f"a VOIDED round still printed a clean-tree summary:\n{result.stdout}")

    def test_a_reviewer_that_MUTATES_THE_LIVE_TREE_voids_the_round(self):
        """isolated-codex-review.sh:168 — the live working tree must be untouched by the review."""
        self.install_mutating_stub('printf \'x\\n\' > "$UM_LIVE_ROOT/EVIL-LIVE.txt"')
        self.assert_voided(self.capture("1"), "MUTATED the real working tree")

    def test_a_reviewer_that_REWRITES_THE_STAGED_PLAN_voids_the_round(self):
        """isolated-codex-review.sh:177 — the plan the round certifies must be the plan codex read.

        This is the COREDEV-2607 signature: a reviewer that edits the staged plan mid-review makes
        the artifact attest bytes nobody reviewed.
        """
        self.install_mutating_stub("printf 'TAMPERED\\n' >> docs/planning/FEATURE_PLAN.md")
        self.assert_voided(self.capture("1"), "STAGED PLAN was modified")

    def test_a_reviewer_that_REWRITES_ITS_OWN_PROMPT_voids_the_round(self):
        """isolated-codex-review.sh:183 — the assembled prompt must be unchanged after the run.

        The file to tamper with is the ASSEMBLED prompt, not the source name. `PROMPT_REL` is the
        absolute path of the transcript's `.prompt` snapshot, so `stage-prompt.py` recreates that
        whole absolute path as nested directories inside the checkout and stages the assembled body
        at `$TREE/<abs path>`. That deep copy is both what codex is handed (`cat "$TREE/$PROMPT_REL"`)
        and what this guard hashes.

        Writing to the `.codex-prompt-*.md` at the checkout root instead would tamper with a git
        artifact of this fixture — which the harness correctly ignores, and which VOIDs the round for
        the unrelated disposable-edit reason. That mistake is worth naming: the first draft of this
        cell did exactly that, went red, and looked like a defect in the guard.
        """
        self.install_mutating_stub(
            r"""find . -name '*.txt.prompt' -type f -print0 |"""
            "\n" + r"""  while IFS= read -r -d '' f; do printf 'TAMPERED\n' >> "$f"; done""")
        self.assert_voided(self.capture("1"), "assembled PROMPT was modified")

    def test_a_reviewer_that_WRITES_SCRATCH_IN_THE_CHECKOUT_voids_the_round(self):
        """isolated-codex-review.sh:197 — a read-only review may leave nothing behind."""
        self.install_mutating_stub("printf 'x\\n' > SCRATCH-FROM-REVIEWER.txt")
        self.assert_voided(self.capture("1"), "left edits inside the disposable checkout")

    def test_a_reviewer_that_DELETES_DOT_GIT_voids_the_round(self):
        """Destroying `.git` VOIDs the round — via the CONTENT comparison, not the fail-closed arm.

        Named for what it actually exercises. `disposable_fingerprint` walks the tree and lists
        `.git` as an entry without descending it, so removing `.git` does not make the fingerprint
        FAIL — it makes it DIFFER, and line 197 catches that. Disabling line 197 turns this cell red,
        which is how the distinction was established rather than assumed.
        """
        self.install_mutating_stub("rm -rf .git")
        self.assert_voided(self.capture("1"), "left edits inside the disposable checkout")

    def test_a_reviewer_that_MAKES_THE_CHECKOUT_UNFINGERPRINTABLE_voids_the_round(self):
        """isolated-codex-review.sh:192 — a fingerprint that cannot be TAKEN is not a clean tree.

        Named for the mechanism, not for permissions: the checkout is made UNFINGERPRINTABLE by a
        path longer than PATH_MAX, NOT by `chmod`. See the comment in the body for why.

        This is the fail-closed arm proper. `disposable_fingerprint` hashes every regular file, so a
        file the walk cannot open raises and the helper returns non-zero. Before it fail-closed, a
        `|| true` turned that into an EMPTY string which compared equal to an empty baseline — so a
        reviewer that broke the detector passed with an APPROVAL.
        """
        # The failure must NOT depend on permission bits. `chmod 000` does not stop UID 0, so under
        # root — which is normal in CI containers — the file is read anyway, the fingerprint SUCCEEDS,
        # the round VOIDs for the ordinary content-difference reason, and this cell both fails and
        # stops exercising the branch it exists for. Found independently by two reviewers on PR #70.
        #
        # `@unittest.skipIf(root)` was the other suggestion and is rejected deliberately: it would
        # leave this guard untested in exactly the environment CI runs, which is the
        # "covered only by a test that can skip" class this whole sweep was built to find.
        #
        # A path longer than PATH_MAX fails for every uid. Each `mkdir`/`cd` is short and succeeds,
        # but the ABSOLUTE path the walk reconstructs exceeds the limit, so `lstat`/`open` raises and
        # `disposable_fingerprint` returns non-zero. Measured here: 3700 chars against PATH_MAX 1024.
        # It must also NOT be the plan or the prompt: making either unreadable trips the earlier
        # staged-plan / staged-prompt digest guards, so the round would VOID for the wrong reason.
        self.install_mutating_stub(
            'd=dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd\n'
            'for i in $(seq 1 40); do mkdir -p "$d" && cd "$d" || break; done\n'
            "printf 'x\\n' > deep.txt")
        result = self.capture("1")
        self.assertEqual(3, result.returncode,
                         f"an unfingerprintable checkout did not VOID the round:\n"
                         f"{result.stdout}{result.stderr}")
        self.assertIn("could not re-read the disposable checkout", result.stderr,
                      f"VOIDED, but not through the fail-closed arm:\n{result.stdout}{result.stderr}")

    def test_codex_reviews_an_isolated_checkout_not_the_live_repo(self):
        """The deterministic isolation property (PR #63 recheck, P1).

        Under isolation codex runs in a disposable detached worktree, so the plan it opens is the
        authenticated staged copy — a swap of the LIVE plan cannot reach it. The stub records its cwd:
        if codex ran in the repo root (`self.root`), it was reading the live, swappable file, which is
        the defect. The reverted, pre-isolation arm runs codex in the live tree and fails here.
        """
        result = self.capture("1")
        self.assertTrue(self.saw.is_file(),
                        f"the stub never ran — the harness refused first: {result.stdout}{result.stderr}")
        cwd_line, plan_line = self.saw.read_text(encoding="utf-8").splitlines()[:2]
        self.assertNotEqual(
            os.path.realpath(cwd_line), os.path.realpath(self.root),
            "codex ran in the live repo root, not an isolated checkout — the live plan was reachable",
        )
        # And what it read there is the authenticated bound plan (the uncommitted EDITED bytes).
        self.assertEqual(EDITED, plan_line.strip(),
                         "codex did not read the authenticated bound plan in its checkout")

    def test_an_oversized_prompt_is_refused_BEFORE_a_leaf_is_allocated(self):
        """codex receives the prompt as ONE argv element (PR #63 recheck).

        Linux caps a single argument at `MAX_ARG_STRLEN` (32 x PAGE_SIZE = 128 KiB) regardless of the
        far larger `ARG_MAX`, so an oversized bound prompt made the `execvp` inside `pty-capture.py`
        fail with E2BIG — after a transcript leaf had been reserved and a disposable worktree built.
        The check runs before allocation, so a round that cannot run consumes nothing. The gemini arm is
        unaffected: it passes `-p "Read and follow <path>"` and the reviewer opens the file itself.
        """
        big = self.root / ".codex-prompt-COREDEV-9999r5.md"
        big.write_text("x" * 130_000 + "\nREVIEW TARGET: docs/planning/FEATURE_PLAN.md\n",
                       encoding="utf-8")
        result = subprocess.run(
            ["bash", str(CAPTURE), "COREDEV-9999", "5",
             ".codex-prompt-COREDEV-9999r5.md", "docs/planning/FEATURE_PLAN.md", "30"],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=False, input="",
        )
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("ONE argument", result.stdout + result.stderr)
        # Nothing consumed: no reserved leaf anywhere under the state root.
        state = self.root / "state"
        allocated = list(state.rglob("*.txt")) if state.exists() else []
        self.assertEqual([], allocated, f"a leaf was reserved for a round that cannot run: {allocated}")

    def test_a_live_plan_diverging_from_the_staged_bytes_does_not_reach_codex(self):
        """The A->B->A property, made DETERMINISTIC (PR #63 recheck, P1).

        A concurrent swap is timing-flaky — a test that can pass against the broken code proves nothing
        (the reviewer's own "weak tests" finding). Instead the divergence is arranged statically: after
        the binding captures the authenticated `.planbytes` (EDITED), the LIVE plan is overwritten with
        B and left that way for the whole capture. Under isolation codex reads the staged EDITED bytes
        from its checkout; the reverted live-tree arm reads B. The `.plan`/`.planbytes` the binder wrote
        still attest EDITED either way, which is exactly what makes the live-tree read a wrong-verdict
        hole. We assert codex never sees B.

        To arrange staged=EDITED while live=B, the binding must run against EDITED first. The capture
        binds against whatever the live plan is at call time, so a fixture cannot both bind EDITED and
        present B before the call. Instead this drives `isolated-codex-review.sh` directly with a
        pre-built transcript whose `.planbytes` are EDITED, then points the live plan at B.
        """
        import hashlib

        allocated = Path(tempfile.mkdtemp(prefix="codex-alloc-"))
        self.addCleanup(shutil.rmtree, allocated, ignore_errors=True)
        out = allocated / "COREDEV-9999-r2-codex.txt"
        out.touch()
        # A CANONICAL launch record: 32 hex digits and a newline. `pty-capture` validates the record's
        # grammar before spawning, because "regular and nonempty" let a `not-a-run-id` record burn a
        # full review the verdict writer then discarded (PR #63 recheck, P2).
        (allocated / (out.name + ".launch")).write_text("a" * 32 + " codex\n", encoding="utf-8")
        edited = f"# Plan\n{EDITED}\n".encode("utf-8")
        (allocated / (out.name + ".plan")).write_text(
            f"{hashlib.sha256(edited).hexdigest()}  docs/planning/FEATURE_PLAN.md\n", encoding="utf-8")
        (allocated / (out.name + ".planbytes")).write_bytes(edited)
        prompt = allocated / "prompt.md"
        prompt.write_text(PROMPT_BODY + "REVIEW TARGET: docs/planning/FEATURE_PLAN.md\n",
                          encoding="utf-8")
        (allocated / (out.name + ".prompt")).write_bytes(prompt.read_bytes())
        # The binder writes `.promptsha256` beside `.prompt`, and staging now REQUIRES it — the
        # "no digest, stage it unauthenticated" fallback was the same fail-open as a missing
        # `.planbytes` (PR #63 recheck, P1).
        (allocated / (out.name + ".promptsha256")).write_text(
            hashlib.sha256(prompt.read_bytes()).hexdigest() + "  prompt.md\n", encoding="utf-8")

        # The live plan now diverges to B; the authenticated staged bytes are EDITED.
        self.plan.write_text("# Plan\nVERSION B (SUBSTITUTED)\n", encoding="utf-8")

        harness = REPO / "scripts" / "review" / "isolated-codex-review.sh"
        result = subprocess.run(
            ["bash", str(harness), str(allocated / (out.name + ".prompt")), str(out), "30",
             "docs/planning/FEATURE_PLAN.md"],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=False, input="",
        )
        self.assertTrue(self.saw.is_file(), result.stdout + result.stderr)
        seen = self.saw.read_text(encoding="utf-8")
        self.assertNotIn("SUBSTITUTED", seen,
                         "codex read the diverged LIVE plan B, not the authenticated staged EDITED bytes")
        self.assertIn(EDITED, seen)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
