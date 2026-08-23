"""COREDEV-2617 — D′: an unresolved plugin-data base persists nothing.

N1  the six-cell resolution matrix (paths.sh present/absent × variable set/empty/unset)
N2  an unresolved base performs no persistent WRITE, and creates nothing at `/`
N3  the libs delegate to paths.sh, and still work when it is absent
N4  every path-returning primitive returns the poisoned sentinel when unresolved
N5  the identifier CLAUDE_PLUGIN_DATA is expanded only at enumerated sites
N6  the agent-env bridge re-resolves from the value it exports, even after an earlier resolution
    in the same shell (with_mutation control: the bridge's reset line deleted)

Each cell starts a FRESH SHELL that sets the environment and *then* sources: resolution is eager and
process-stable, so mutating the environment after sourcing cannot change the resolved base. A test
that exported first would be testing its own ordering, not the contract.
"""
import atexit
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


# A process-lifetime scratch HOME. It is deliberately EMPTY: the point is a home with no
# plugin-state store, not a fixture (see the HOME note in run()).
_SANDBOX_HOME = tempfile.mkdtemp(prefix="plugin-state-base-home.")
atexit.register(shutil.rmtree, _SANDBOX_HOME, True)


def run(script, env=None, shell="bash", libdir=None):
    """Run `script` in a fresh shell with a clean environment."""
    e = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_PLUGIN_ROOT")}
    e["_LIBDIR"] = libdir or LIB
    # COREDEV-2617 §4.2a: these cells source family libs with the variable SET, which publishes
    # into ${HOME}/.claude/unleashed-mail/bases/. This suite tests the D′ envelope, not the store,
    # so publication is off — a real HOME must never receive an entry from a test cell (codex,
    # PR #67). Cells that need to assert on the store set _UNLEASHED_PUBLISH_OK themselves.
    e.setdefault("_UNLEASHED_PUBLISH_OK", "0")
    # ...and HOME is sandboxed, because suppressing PUBLICATION is not the same as suppressing
    # DISCOVERY. Every cell here asserts the D-prime envelope — "no CLAUDE_PLUGIN_DATA means
    # unresolved" — and once COREDEV-2617 shipped, a developer's REAL ${HOME} holds a populated
    # store, so the resolver legitimately resolves a real base and 26 of these cells fail. They
    # passed before only because no store existed anywhere yet; CI stays green because a Linux
    # runner has no store either, so this could not surface there. Measured on a machine with a
    # live store: real HOME -> 26 failures, scratch HOME -> 14 tests OK. A cell that needs the
    # store sets HOME itself.
    e["HOME"] = _SANDBOX_HOME          # NOT setdefault: `e` is seeded from os.environ, which has HOME
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


class N2bNoCompositionUnderAnUnresolvedBase(unittest.TestCase):
    """D-prime, asserted by COMPOSITION rather than by outcome — the whole family, in one shape.

    `N2NoPersistence` above names all four writers but can only FAIL for one of them. Measured by
    mutating each guard to `:` (line-count preserving) and running that class:

        marker.sh:261   (marker_write)                14 tests OK  -- UNCOVERED
        log.sh:197      (log_append)                  14 tests OK  -- UNCOVERED
        context.sh:500  (context_review_round_clear)  14 tests OK  -- UNCOVERED
        context.sh:355  (_context_round_sweep)        14 tests OK  -- inert while :419 stands
        context.sh:419  (context_review_round_bind)   FAILED (1)   -- covered

    Why the existing cells cannot see it: `test_writers_are_no_ops_and_succeed` asserts `rc=0`, which
    the mutants also return; `test_nothing_is_created_at_root` probes `/.state`, `/logs`, `/reviews`,
    but the unresolved sentinel is `/dev/null/unresolved-plugin-base`, so nothing lands at `/` either
    way. Only `bind` is caught, and only because its `printf` runs after the failed write.

    The discriminating signal is not the outcome but the ATTEMPT: with the guard gone, the writer
    composes a path under the sentinel and calls `mkdir -p /dev/null/unresolved-plugin-base/...`,
    which fails with ENOTDIR. The round is then safe only by accident of `/dev/null` not being a
    directory — the accident `stop-quality-marker-gate.sh`'s own comment says the design must not
    depend on. Shimming `mkdir`/`rm` on PATH and counting invocations sees the attempt itself.
    """

    #: Every writer that carries a D-prime guard, with the command that reaches it. Derived by
    #: `grep -rn unleashed_base_ok scripts/ --include='*.sh'`, not from memory.
    WRITERS = (
        ("marker.sh:261", "marker.sh", "marker_write lint fail"),
        ("log.sh:197", "log.sh", 'log_append probe.jsonl \'{"x":1}\''),
        ("context.sh:419", "context.sh", "context_review_round_bind security-reviewer a1 s1"),
        ("context.sh:500", "context.sh", "context_review_round_clear a1"),
    )

    #: The sentinel an unresolved base composes against. Any argument naming it is a composition that
    #: should never have happened.
    SENTINEL = "/dev/null/unresolved-plugin-base"

    def setUp(self):
        self.shim = tempfile.mkdtemp(prefix="dprime-shim.")
        self.addCleanup(shutil.rmtree, self.shim, ignore_errors=True)
        self.calls = os.path.join(self.shim, "calls.log")
        for name in ("mkdir", "rm", "mv"):
            real = shutil.which(name) or f"/bin/{name}"
            path = os.path.join(self.shim, name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/usr/bin/env bash\n"
                         f'printf "%s %s\\n" "{name}" "$*" >> "{self.calls}"\n'
                         f'exec "{real}" "$@"\n')
            os.chmod(path, 0o755)

    def _composition_attempts(self, lib, call, libdir=None):
        """Run `call` with an unresolved base and return the shimmed invocations naming the sentinel."""
        open(self.calls, "w").close()
        env = {"PATH": self.shim + os.pathsep + os.environ.get("PATH", os.defpath)}
        run(f'. "$_LIBDIR/{lib}"; {call}', env=env, libdir=libdir)
        with open(self.calls, encoding="utf-8") as fh:
            return [line.strip() for line in fh if self.SENTINEL in line]

    def test_no_writer_composes_a_path_under_the_unresolved_sentinel(self):
        for label, lib, call in self.WRITERS:
            with self.subTest(writer=label):
                attempts = self._composition_attempts(lib, call)
                self.assertEqual([], attempts,
                                 f"{label} composed a path under the unresolved-base sentinel: "
                                 f"{attempts}")

    def test_the_shim_SEES_a_composition_when_the_guard_is_removed(self):
        """The control, and it is what makes the cell above worth anything.

        Without it, a shim that recorded nothing — a broken PATH, a writer that never runs — would
        report an empty list and read as a pass. Each guard is deleted in a COPY of the library
        (line-count preserving) and the attempt must then be visible. `context.sh:355` is excluded:
        it is unreachable while `:419` stands, so its deletion is behaviour-preserving by
        construction — a rule-6 inert member, pinned by that fact rather than by a behavioural cell.
        """
        removable = {
            "marker.sh:261": ("marker.sh", "marker_write lint fail"),
            "log.sh:197": ("log.sh", 'log_append probe.jsonl \'{"x":1}\''),
            "context.sh:419": ("context.sh", "context_review_round_bind security-reviewer a1 s1"),
            "context.sh:500": ("context.sh", "context_review_round_clear a1"),
        }
        guard = "    unleashed_base_ok || return 0"
        for label, (lib, call) in removable.items():
            with self.subTest(writer=label):
                line_no = int(label.split(":")[1])
                mutant_dir = os.path.join(self.shim, "lib-" + label.replace(".", "_").replace(":", "_"))
                shutil.copytree(LIB, mutant_dir)
                target = os.path.join(mutant_dir, lib)
                with open(target, encoding="utf-8") as fh:
                    lines = fh.readlines()
                self.assertTrue(lines[line_no - 1].startswith(guard),
                                f"{label}: line {line_no} is not the D-prime guard, it is "
                                f"{lines[line_no - 1]!r} — the family census is stale")
                lines[line_no - 1] = "    :\n"
                with open(target, "w", encoding="utf-8") as fh:
                    fh.writelines(lines)
                attempts = self._composition_attempts(lib, call, libdir=mutant_dir)
                self.assertNotEqual([], attempts,
                                    f"CONTROL FAILED — with {label} deleted the shim saw no "
                                    f"composition under {self.SENTINEL}, so the cell above cannot "
                                    f"distinguish a working guard from a silent shim")


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
        "scripts/tests/test_plugin_state_mutants.py": "sets/unsets it for fixtures — a test harness exercising the resolver, not a primitive re-deriving the base",
        "scripts/tests/test_plugin_state_store.py": "sets/unsets it for the `set -eu` scenario sweep — a test harness exercising the resolver, not a primitive re-deriving the base",
        "scripts/tests/test_writer_redirect_order.py": "sets it to a scratch base so `marker_path` resolves inside the fixture — a test harness exercising the resolver, not a primitive re-deriving the base",
        "scripts/pre-commit-checks.sh": "comments only",
        # PUB-9 E2a's rationale has to name the variable to say what it names — the directory the HOST
        # will use, which on a first session does not exist yet. The publisher receives the VALUE as
        # `$2` and expands the identifier nowhere; `COMMENT_ONLY` below asserts exactly that, so this
        # entry buys a comment and not an exemption. (PR #67 pass 17: the fix's own comment tripped
        # this scan, which is a lexical detector and does not read shell syntax.)
        "scripts/lib/plugin-state-publisher.sh": "comments only — E2a/E2b's rationale names the "
                                                 "variable; the value arrives as $2",
        "agents/swift-reviewer.md": "MAJ-6 bridge injection sites — the substitution points",
        "scripts/validate-plan-citations.py": "a citation-assertion PATTERN, not an expansion — the "
                                              "linter searches the PLAN for this text and never "
                                              "reads the variable",
    }

    #: Allowlist entries whose justification is "comments only". An allowlist entry is a hole in the
    #: scan, and for these two the hole is meant to be exactly as wide as a comment — so the claim is
    #: ASSERTED rather than trusted: every occurrence must be on a line whose first non-blank
    #: character is `#`. A later edit that expands the identifier in code in one of these files fails
    #: here, where the enumerated exemption would otherwise have hidden it.
    COMMENT_ONLY = ("scripts/pre-commit-checks.sh", "scripts/lib/plugin-state-publisher.sh")

    def test_comment_only_allowlist_entries_really_are_comments(self):
        for rel in self.COMMENT_ONLY:
            self.assertIn(rel, self.ALLOWLIST, f"{rel} is not allowlisted at all")
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            hits = [l for l in lines if re.search(r"\bCLAUDE_PLUGIN_DATA\b", l)]
            self.assertTrue(hits, f"{rel}: no occurrence at all — the allowlist entry is dead and "
                                  f"should be removed rather than left as a standing exemption")
            code = [l for l in hits if not l.lstrip().startswith("#")]
            self.assertEqual([], code,
                             f"{rel} is allowlisted as COMMENTS ONLY but expands the identifier in "
                             f"code: {code}")

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


class N6BridgeReResolves(unittest.TestCase):
    """The bridge establishes the ENVIRONMENT'S base, so it discards this instance's earlier resolution.

    Sourced after paths.sh had already resolved `<a>` in the same shell, the bridge exports `<b>` and
    then sources paths.sh again; paths.sh's once-per-instance guard (pid + the marker function) would
    treat the earlier resolution as current — `CLAUDE_PLUGIN_DATA=<b>` beside
    `_UNLEASHED_BASE_RESOLVED=<a>` (codex, PR #67 pass 12 — reproduced). The bridge clears the marker
    function and the pid before it sources paths.sh, so the eager resolve runs again from the value it
    just exported. Linux-safe: `_UNLEASHED_PUBLISH_OK=0` (E0) and the variable is set in every cell, so
    no store is read, written, or needed; the scratch HOME is under ~/.claude only for hygiene.
    """

    #: The reset the bridge performs right after exporting the value — the control deletes exactly this.
    #: (`|| :` since PR #67 pass 14: zsh's `unset -f` returns 1 for a function that is not defined, and
    #: under `set -e` that killed the sourcing — row 175. The line the control deletes is the same one.)
    RESET_LINE = "unset -f _unleashed_resolved_in_process 2>/dev/null || :; _UNLEASHED_BASE_PID=\n"

    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="bridge-reresolve.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.a = os.path.join(self.scratch, "base-a")
        self.b = os.path.join(self.scratch, "base-b")
        os.mkdir(self.a)
        os.mkdir(self.b)

    def _control_bridge(self):
        """A copy of the bridge with its reset line deleted — asserted present exactly once first, so a
        control built from a pattern that no longer matches cannot silently pass as 'discriminating'."""
        src = os.path.join(LIB, "agent-env-bridge.sh")
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.RESET_LINE), "the bridge's reset line is not unique — the control anchor drifted")
        control = os.path.join(self.scratch, "agent-env-bridge.control.sh")
        with open(control, "w", encoding="utf-8") as fh:
            fh.write(text.replace(self.RESET_LINE, "", 1))
        return control

    def _cell(self, shell, bridge):
        # The bridge takes ($1 = the value to export, $2 = the plugin root it sources paths.sh from);
        # the shipped paths.sh is sourced FIRST so the shell already holds a resolution of <a>.
        script = (f'export HOME="{self.scratch}" CLAUDE_PLUGIN_DATA="{self.a}" _UNLEASHED_PUBLISH_OK=0; '
                  f'. "{LIB}/paths.sh"; . "{bridge}" "{self.b}" "{ROOT}"; '
                  'printf "%s|%s" "$CLAUDE_PLUGIN_DATA" "$_UNLEASHED_BASE_RESOLVED"')
        return run(script, shell=shell)

    def test_the_bridge_re_resolves_after_an_earlier_resolution_in_the_same_shell(self):
        control = self._control_bridge()
        for shell in ("bash", "zsh"):
            if not shutil.which(shell):
                self.skipTest(f"{shell} not available")
            with self.subTest(shell=shell, build="shipped"):
                r = self._cell(shell, os.path.join(LIB, "agent-env-bridge.sh"))
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertNotIn("command not found", r.stderr)
                self.assertEqual(f"{self.b}|{self.b}", r.stdout,
                                 "the bridge exported <b> but the shell kept its earlier resolution of <a>: "
                                 f"{r.stdout!r} {r.stderr!r}")
            with self.subTest(shell=shell, build="control"):
                r = self._cell(shell, control)
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertEqual(f"{self.b}|{self.a}", r.stdout,
                                 "the CONTROL did not fail — without the reset line the bridge still "
                                 f"re-resolved, so this test cannot discriminate: {r.stdout!r} {r.stderr!r}")
            self.assertFalse(os.path.exists(os.path.join(self.scratch, ".claude")),
                             f"{shell}: E0 must leave no store under the scratch HOME")


if __name__ == "__main__":
    unittest.main()
