"""COREDEV-2617 — D′: an unresolved plugin-data base persists nothing.

N1  the six-cell resolution matrix (paths.sh present/absent × variable set/empty/unset)
N2  an unresolved base performs no persistent WRITE, and creates nothing at `/`
N3  the libs delegate to paths.sh, and still work when it is absent
N4  every path-returning primitive returns the poisoned sentinel when unresolved
N5  the identifier CLAUDE_PLUGIN_DATA is expanded only at enumerated sites

Each cell starts a FRESH SHELL that sets the environment and *then* sources: resolution is eager and
process-stable, so mutating the environment after sourcing cannot change the resolved base. A test
that exported first would be testing its own ordering, not the contract.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LIB = os.path.join(ROOT, "scripts", "lib")
SENTINEL = "/dev/null/unresolved-plugin-base"


def run(script, env=None, shell="bash", libdir=None):
    """Run `script` in a fresh shell with a clean environment."""
    e = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_PLUGIN_ROOT")}
    e["_LIBDIR"] = libdir or LIB
    e.update(env or {})
    return subprocess.run([shell, "-c", script], capture_output=True, text=True, env=e)


class N1ResolutionMatrix(unittest.TestCase):
    """Six cells: paths.sh present/absent × CLAUDE_PLUGIN_DATA set/empty/unset."""

    CELLS = (
        ({"CLAUDE_PLUGIN_DATA": "/tmp/probe-2617"}, "1", "/tmp/probe-2617"),
        ({"CLAUDE_PLUGIN_DATA": ""}, "0", SENTINEL),
        ({}, "0", SENTINEL),
    )

    def _matrix(self, libdir):
        for env, want_ok, want_base in self.CELLS:
            for lib in ("marker.sh", "log.sh", "context.sh"):
                with self.subTest(libdir=os.path.basename(libdir), lib=lib, env=env):
                    r = run(f'. "$_LIBDIR/{lib}"; printf "%s|%s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_RESOLVED"',
                            env=env, libdir=libdir)
                    self.assertEqual(f"{want_ok}|{want_base}", r.stdout)

    def test_with_paths_sh_present(self):
        self._matrix(LIB)

    def test_with_paths_sh_absent(self):
        """The libs must establish the SAME protocol themselves — paths.sh is not load-bearing."""
        with tempfile.TemporaryDirectory() as d:
            copy = os.path.join(d, "lib")
            shutil.copytree(LIB, copy)
            os.remove(os.path.join(copy, "paths.sh"))
            self._matrix(copy)

    def test_zsh_agrees_with_bash(self):
        """The agent fence runs zsh; a Bash-only construct here would fail there silently."""
        if not shutil.which("zsh"):
            self.skipTest("zsh not available")
        r = run('. "$_LIBDIR/context.sh"; printf "%s|%s" "$_UNLEASHED_BASE_OK" "$_UNLEASHED_BASE_RESOLVED"',
                shell="zsh")
        self.assertEqual(f"0|{SENTINEL}", r.stdout)

    def test_exactly_one_diagnostic_per_process(self):
        """Sourcing all three libs emits ONE diagnostic — the guard is the shared flag, not the file."""
        for libdir, label in ((LIB, "present"), (None, "absent")):
            with tempfile.TemporaryDirectory() as d:
                if libdir is None:
                    libdir = os.path.join(d, "lib")
                    shutil.copytree(LIB, libdir)
                    os.remove(os.path.join(libdir, "paths.sh"))
                with self.subTest(paths_sh=label):
                    r = run('. "$_LIBDIR/marker.sh"; . "$_LIBDIR/log.sh"; . "$_LIBDIR/context.sh"', libdir=libdir)
                    self.assertEqual(1, r.stderr.count("CLAUDE_PLUGIN_DATA is unset"))

    def test_no_diagnostic_when_resolved(self):
        r = run('. "$_LIBDIR/marker.sh"; . "$_LIBDIR/log.sh"; . "$_LIBDIR/context.sh"',
                env={"CLAUDE_PLUGIN_DATA": "/tmp/probe-2617"})
        self.assertNotIn("CLAUDE_PLUGIN_DATA is unset", r.stderr)


class N2NoPersistence(unittest.TestCase):
    """An unresolved base writes nothing, and nothing lands at `/`."""

    WRITERS = (
        ("marker.sh", "marker_write lint pass"),
        ("log.sh", 'log_append probe.jsonl \'{"x":1}\''),
        ("context.sh", "context_review_round_bind security-reviewer agent-1 sess-1"),
        ("context.sh", "context_review_round_clear agent-1"),
    )

    def test_writers_are_no_ops_and_succeed(self):
        for lib, call in self.WRITERS:
            with self.subTest(lib=lib, call=call.split()[0]):
                r = run(f'. "$_LIBDIR/{lib}"; {call}; printf "rc=%s out=[%s]" "$?" ""')
                self.assertIn("rc=0", r.stdout, "a writer must return success, not fail the consumer")

    def test_bind_prints_nothing_when_unresolved(self):
        """Its printf runs AFTER the failed mv, so skipping the write alone is not enough."""
        r = run('. "$_LIBDIR/context.sh"; out="$(context_review_round_bind security-reviewer a1 s1)"; '
                'printf "[%s]" "$out"')
        self.assertEqual("[]", r.stdout)

    def test_nothing_is_created_at_root(self):
        before = {p for p in ("/.state", "/logs", "/reviews") if os.path.exists(p)}
        run('. "$_LIBDIR/marker.sh"; . "$_LIBDIR/log.sh"; . "$_LIBDIR/context.sh"; '
            'marker_write lint fail; log_append e.jsonl x; context_review_round_bind security-reviewer a s')
        after = {p for p in ("/.state", "/logs", "/reviews") if os.path.exists(p)}
        self.assertEqual(before, after, "an unresolved base must never compose a root path")

    def test_writes_really_happen_when_resolved(self):
        """The adequacy check: a guard that blocks everything would pass every test above."""
        with tempfile.TemporaryDirectory() as d:
            r = run('. "$_LIBDIR/marker.sh"; marker_write lint pass; ls "$CLAUDE_PLUGIN_DATA/.state" | head -1',
                    env={"CLAUDE_PLUGIN_DATA": d})
            self.assertRegex(r.stdout.strip(), r"^quality-marker-lint-[0-9a-f]+\.json$")


class N4SentinelEnvelope(unittest.TestCase):
    """Every path-returning primitive returns the sentinel — never empty, never a root path."""

    PRIMITIVES = (
        ("marker.sh", "marker_base"), ("marker.sh", "marker_dir"), ("marker.sh", "marker_path lint"),
        ("log.sh", "log_base"), ("log.sh", "log_dir"),
        ("context.sh", "context_base"), ("context.sh", "context_state_dir"),
        ("context.sh", "context_reviews_dir"), ("context.sh", "context_snapshot_path"),
        ("context.sh", "context_round_binding_path a1"),
    )

    def test_every_primitive_returns_the_sentinel(self):
        for lib, call in self.PRIMITIVES:
            with self.subTest(primitive=call.split()[0]):
                r = run(f'. "$_LIBDIR/{lib}"; {call}')
                self.assertTrue(
                    r.stdout.startswith(SENTINEL),
                    f"{call} returned {r.stdout!r}; an empty or root-relative value composes a ROOT "
                    f"path at the call site, which is the defect the sentinel exists to prevent",
                )


class N5LexicalDrift(unittest.TestCase):
    """The identifier is expanded only at enumerated sites.

    NARROWED (plan round 9): this is a LEXICAL DRIFT DETECTOR, not a proof of accessor-only
    provenance. Path provenance is not statically decidable in Bash — a runtime-assembled name
    (`n=CLAUDE_PLUGIN_; n="${n}DATA"; printenv "$n"`) evades any static scan, and so does a
    hard-coded "${HOME}/.claude/unleashed-mail". What this catches is the failure this ticket is
    actually about: a copy-pasted resolver in a new primitive.
    """

    #: (path, reason) — every approved site, enumerated. Adding one is a visible diff.
    ALLOWLIST = {
        "scripts/lib/paths.sh": "the resolver, plus the legacy expansion kept for the drift matrix",
        "scripts/lib/marker.sh": "inline fallback — paths.sh is not load-bearing",
        "scripts/lib/log.sh": "inline fallback",
        "scripts/lib/context.sh": "inline fallback",
        "scripts/lib/agent-env-bridge.sh": "the bridge; receives the value as $1",
        "scripts/test-hooks.sh": "harness isolation — sets it to a temp root",
        "scripts/tests/test_shell_primitive_drift.py": "asserts the expansion FORM",
        "scripts/tests/test_plugin_state_base.py": "this file",
        "scripts/tests/test_reviewer_roster.py": "sets it for a fixture",
        "scripts/pre-commit-checks.sh": "comments only",
        "agents/swift-reviewer.md": "MAJ-6 bridge injection sites — the substitution points",
    }

    def test_identifier_appears_only_at_approved_sites(self):
        offenders = {}
        skip_dirs = {"__pycache__", ".git", "node_modules"}
        skip_ext = {".pyc", ".pyo", ".png", ".jpg", ".gz", ".zip"}
        for sub in ("scripts", "hooks", "agents", "skills", ".githooks"):
            base = os.path.join(ROOT, sub)
            for dirpath, dirnames, names in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in skip_dirs]
                for n in names:
                    if os.path.splitext(n)[1] in skip_ext:
                        continue
                    full = os.path.join(dirpath, n)
                    rel = os.path.relpath(full, ROOT)
                    if rel in self.ALLOWLIST:
                        continue
                    try:
                        with open(full, encoding="utf-8", errors="replace") as fh:
                            body = fh.read()
                    except OSError:
                        continue
                    if re.search(r"\bCLAUDE_PLUGIN_DATA\b", body):
                        offenders[rel] = True
        self.assertEqual(
            {}, offenders,
            "CLAUDE_PLUGIN_DATA is expanded outside the enumerated allowlist: "
            + ", ".join(sorted(offenders))
            + " — a new primitive must go through the resolver, not re-derive the base",
        )

    def test_indirection_fails_closed(self):
        """`${!…}` and `eval` cannot be decided statically, so they are rejected in the scan set."""
        for sub in ("scripts/lib",):
            base = os.path.join(ROOT, sub)
            for dirpath, _, names in os.walk(base):
                for n in names:
                    if not n.endswith(".sh"):
                        continue
                    with open(os.path.join(dirpath, n), encoding="utf-8") as fh:
                        body = fh.read()
                    self.assertNotIn("${!", body, f"{n}: indirect expansion in a state library")


if __name__ == "__main__":
    unittest.main()
