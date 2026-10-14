#!/usr/bin/env python3
"""The executed mutant table for the Gemini arm (COREDEV-2887 plan §4, §5.3).

Each mutant deletes or weakens ONE control in the shipped scripts, and the §4 cells it names must go RED.
An anchor that does not match exactly once is reported as OPERATOR BROKEN, never as a kill, so a no-op
mutation cannot pass. Every file is restored byte-for-byte after each mutant (the digest is asserted).

Not a unittest module (it is not named `test_*`): it re-runs suites once per mutant, so it is run by hand
before a change to the arm ships, and its output is recorded in the PR.

Usage: PYTHONDONTWRITEBYTECODE=1 python3 scripts/tests/mutate_gemini_cli_arm.py <repo root> [mutant name ...]
Exit:  0 every mutant was killed · 1 a mutant survived or an anchor was broken
"""

import hashlib
import os
import subprocess  # nosec B404 — re-runs this interpreter's unittest with fixed arguments
import sys
from pathlib import Path

A = "scripts/review/gemini-review-run.py"
H = "scripts/review/isolated-gemini-review.sh"
P = "scripts/review/preflight-gemini.sh"
T = "scripts.tests.test_gemini_cli_arm."
MUTANTS = [
    (
        "stderr reaches the PTY",
        A,
        "    if not _redirect_stderr(args.diagnostics):\n        return 4",
        "    if False:\n        return 4",
        [
            T + "G2NothingUnvalidatedReachesTheTranscript",
            T + "G6RefusedReviewerStaysMissing",
        ],
    ),
    (
        "JSON error ignored",
        A,
        "    if error:\n        kind",
        "    if False:\n        kind",
        [T + "G2NothingUnvalidatedReachesTheTranscript"],
    ),
    (
        "model assertion dropped",
        A,
        "    if answered != [args.model]:",
        "    if False:",
        [T + "G2NothingUnvalidatedReachesTheTranscript"],
    ),
    (
        "keys truncated before comparing",
        A,
        "sorted(str(m) for m in models)",
        "sorted(str(m)[:80] for m in models)",
        [T + "G2NothingUnvalidatedReachesTheTranscript"],
    ),
    (
        "CR normalization dropped",
        A,
        '    response = response.replace("\\r\\n", "\\n").replace("\\r", "\\n")\n',
        "",
        [T + "G3TheTranscriptIsTheNormalizedResponse"],
    ),
    (
        "MCP allowlist dropped",
        A,
        '        "--allowed-mcp-server-names",\n        "unleashed-mail-no-mcp-" + secrets.token_hex(16),\n',
        "",
        [T + "G4aWhatTheCliReceives"],
    ),
    (
        "fixed MCP sentinel",
        A,
        '"unleashed-mail-no-mcp-" + secrets.token_hex(16)',
        '"unleashed-mail-no-mcp-" + "0" * 32',
        [T + "G4aTheMcpSentinelIsFreshPerRun"],
    ),
    (
        "trust env dropped",
        A,
        '    env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"\n',
        "",
        [T + "G4aWhatTheCliReceives"],
    ),
    (
        "routing-off not staged",
        H,
        """b'{"general": {"plan": {"modelRouting": false}}, '""",
        """b'{"general": {"plan": {}}, '""",
        [T + "G4aWhatTheCliReceives"],
    ),
    (
        "file filtering left on",
        H,
        '"respectGitIgnore": false, "respectGeminiIgnore": false',
        '"respectGitIgnore": true, "respectGeminiIgnore": true',
        [T + "G4aWhatTheCliReceives"],
    ),
    (
        "diag opened without O_EXCL",
        A,
        "os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr",
        "os.O_WRONLY | os.O_CREAT | getattr",
        [T + "G4bTheDiagnosticsFile"],
    ),
    (
        "harness diag pre-check dropped",
        H,
        'if [[ -e "${OUT}.diag" ]] || [[ -L "${OUT}.diag" ]]; then',
        "if false; then",
        [T + "G4bTheHarnessNamesTheDiagnostics"],
    ),
    (
        "committed .env check dropped",
        H,
        'if [[ -e "${TREE}/.env" ]] || [[ -L "${TREE}/.env" ]]; then',
        "if false; then",
        [T + "G7AReviewedTreeCannotConfigureItsReviewer"],
    ),
    (
        "committed .gemini check dropped",
        H,
        'if [[ -e "${TREE}/.gemini" ]] || [[ -L "${TREE}/.gemini" ]]; then',
        "if false; then",
        [T + "G7AReviewedTreeCannotConfigureItsReviewer"],
    ),
    (
        "ancestor env walk dropped",
        A,
        "    foreign = _foreign_env_file(Path.cwd())",
        "    foreign = None",
        [T + "G7bNoForeignEnvironmentFile"],
    ),
    (
        "disposable-tree comparison dropped",
        H,
        'if [[ ${TREE_BASELINE} != "${TREE_AFTER}" ]]; then',
        "if false; then",
        [T + "G1IsolationCatchesAWriter"],
    ),
    (
        "live-tree comparison dropped",
        H,
        'if [[ ${BEFORE} != "${AFTER}" ]]; then',
        "if false; then",
        [T + "G1IsolationCatchesAWriter"],
    ),
    (
        "preflight failure omits the model",
        P,
        "printf 'gemini preflight (%s): the capture exited %s — %s\\n' \"${MODEL:-<no model>}\"",
        "printf 'gemini preflight %.0s: the capture exited %s — %s\\n' \"${MODEL:-<no model>}\"",
        [T + "G5Preflight"],
    ),
    (
        "preflight substring pong",
        P,
        're.fullmatch(r"(?i)pong[.!]?", open(sys.argv[1], errors="replace").read().strip())',
        're.search(r"(?i)pong", open(sys.argv[1], errors="replace").read())',
        [T + "G5Preflight"],
    ),
    (
        "harness refusal not explained",
        H,
        "\tprintf 'gemini arm (%s): %s\\n' \"${MODEL}\"",
        "\t: printf 'gemini arm (%s): %s\\n' \"${MODEL}\"",
        [T + "G6RefusedReviewerStaysMissing"],
    ),
    (
        "a second allowlist value, equals form",
        A,
        '        "--allowed-mcp-server-names",\n',
        '        "--allowed-mcp-server-names=attacker",\n        "--allowed-mcp-server-names",\n',
        [T + "G4aWhatTheCliReceives"],
    ),
    (
        "a constant reported verdict",
        H,
        (
            'VERDICT="$(grep -aE '
            "'^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$'"
            ' "${OUT}" 2>/dev/null | tail -1)"'
        ),
        'VERDICT="VERDICT: APPROVE"',
        [T + "G3bTheHarnessReportsTheResponsesVerdict"],
    ),
    (
        "preflight die omits the model",
        P,
        '\tprintf \'gemini preflight (%s): %s\\n\' "${MODEL:-<no model>}" "$1" >&2',
        "\tprintf 'gemini preflight: %s\\n' \"$1\" >&2",
        [T + "G5Preflight"],
    ),
    (
        "--skip-trust=false appended",
        A,
        '        "--skip-trust",  #',
        '        "--skip-trust=false",\n        "--skip-trust",  #',
        [T + "G4aWhatTheCliReceives"],
    ),
    (
        "--diagnostics forwarded in equals form",
        A,
        '        "-o",\n        "json",',
        '        "--diagnostics=" + args.diagnostics,\n        "-o",\n        "json",',
        [T + "G4aWhatTheCliReceives"],
    ),
    (
        "staged-plan check dropped",
        H,
        'if [[ ${ACTUAL_PLAN_SHA} != "${EXPECTED_PLAN_SHA}" ]]; then',
        "if false; then",
        [T + "G1IsolationCatchesAWriter"],
    ),
    (
        "no-pong line omits the model",
        P,
        "printf 'gemini preflight (%s): no pong in %s",
        "printf 'gemini preflight %.0s: no pong in %s",
        [T + "G5Preflight"],
    ),
    (
        "initial fingerprint failure omits the model",
        P,
        "printf 'gemini preflight (%s): FAILED — could not fingerprint the checkout before the ping",
        "printf 'gemini preflight %.0s: FAILED — could not fingerprint the checkout before the ping",
        [T + "G5Preflight"],
    ),
    (
        "context-file refusal dropped",
        H,
        'if hits:\n    sys.exit(\n        "GATE FAILED — the reviewed tree commits a Gemini context file ("',
        'if False:\n    sys.exit(\n        "GATE FAILED — the reviewed tree commits a Gemini context file ("',
        [T + "G7AReviewedTreeCannotConfigureItsReviewer"],
    ),
    (
        "extensions left enabled",
        A,
        '        "--extensions",\n        "none",\n',
        "",
        [T + "G4aWhatTheCliReceives"],
    ),
    (
        "stdout left unbounded",
        A,
        "        if total > _STDOUT_CAP:",
        "        if False:",
        [T + "G2NothingUnvalidatedReachesTheTranscript"],
    ),
    (
        "configured context names ignored",
        H,
        '            names.add(cleaned.removeprefix("./"))',
        "            pass",
        [T + "G7AReviewedTreeCannotConfigureItsReviewer"],
    ),
]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_one(root: Path, mutant: tuple[str, str, str, str, list[str]]) -> bool:
    """Apply one mutant, run its cells, restore the file byte-for-byte. True when the mutant was killed."""
    name, path, old, new, cells = mutant
    target = root / path
    original = target.read_text(encoding="utf-8")
    before = _digest(target)
    if original.count(old) != 1:
        print(f"OPERATOR BROKEN  {name}: anchor occurs {original.count(old)} times")
        return False
    try:
        target.write_text(original.replace(old, new), encoding="utf-8")
        result = subprocess.run(  # nosec B603 — this interpreter, fixed arguments
            [sys.executable, "-m", "unittest", *cells],
            cwd=root,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    finally:
        target.write_text(original, encoding="utf-8")
        if _digest(target) != before:
            raise SystemExit(f"{path} was NOT restored byte-for-byte")
    killed = result.returncode != 0
    print(f"{'RED (killed)' if killed else 'GREEN — SURVIVED':18} {name}")
    return killed


def main() -> int:
    """Run every mutant (or the named ones) and report survivors and broken anchors."""
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    only = set(sys.argv[2:])
    bad = 0
    for mutant in MUTANTS:
        if only and mutant[0] not in only:
            continue
        if not _run_one(root, mutant):
            bad += 1
    print(f"survivors/broken: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
