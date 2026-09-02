#!/usr/bin/env bash
# COREDEV-2801 §3b — warn when the plugin version a session is RUNNING lags what `origin/main` serves.
#
# THE BOOTSTRAP PROBLEM, AND WHY THIS LIVES IN THE CHECKOUT. A session bound to a stale install cannot
# execute a detector shipped only in a later version of the plugin. This script is not shipped by the
# plugin — it lives in the repository and runs from it, so it is current regardless of which install a
# session loaded. It needs no session environment and no plugin code.
#
# THE REPOSITORY ROOT IS AN EXPLICIT OPERAND, NEVER AN AMBIENT VARIABLE.
# `git -C "${CLAUDE_PROJECT_DIR}" show …` is correct for `SessionStart` and WRONG for the other caller:
# git does not set that variable for hooks, it sets the hook's WORKING DIRECTORY. Three cases follow
# and only the first is benign — unset without `nounset` leaves `git -C ""`, which happens to work;
# unset under `set -u` aborts before anything is classified; and NON-EMPTY BUT INHERITED FROM ANOTHER
# PROJECT points git at the wrong repository, which is either a silent misclassification or a false
# comparison against a foreign manifest. So each caller passes the root it knows:
#   .claude/settings.json SessionStart  ->  "${CLAUDE_PROJECT_DIR}"
#   .githooks/pre-commit                ->  "$(git rev-parse --show-toplevel)"
#
# `expected` IS READ FROM `origin/main`, NOT THE WORKTREE OR THE INDEX. This repository's rule is that
# every shipping change bumps the version, so the working tree sits one bump AHEAD of anything a
# consumer can pull for the whole life of a feature branch — reading it would warn on every developer's
# machine, permanently, which is the "red by default" trap that trains people to ignore a signal.
#
# SILENT MEANS SILENT: it emits nothing and records nothing. Only row 7 warns, and it never blocks.
#
# Usage:
#   detect-plugin-version-drift.sh <repo-root>                   # plain: one warning line on stdout
#   detect-plugin-version-drift.sh <repo-root> --session-start   # hook: reads JSON stdin, dedups,
#                                                                # emits {"systemMessage": "…"}
# Exit: ALWAYS 0. This is a diagnostic, not a gate.

set -uo pipefail

root="${1-}"
mode="${2-}"

# Table A row 1 by CLASSIFICATION rather than by accident: a missing, empty or non-repository operand
# has no `expected` to compare against, so it is silent — the same outcome as an unreadable manifest.
if [[ -z ${root} ]] || [[ ! -d ${root} ]]; then
	exit 0
fi

expected_json="$(git -C "${root}" show origin/main:.claude-plugin/plugin.json 2>/dev/null)" || exit 0
[[ -n ${expected_json} ]] || exit 0

installed_record="${HOME}/.claude/plugins/installed_plugins.json"

# THE COMPARISON WRITES TO A FILE RATHER THAN INTO `$( ... )`.
# bash 3.2 -- which is what macOS still ships, and therefore what BOTH of this detector's callers
# run on a developer machine -- CANNOT PARSE a quoted heredoc inside a command substitution when the
# body contains an apostrophe or an unbalanced paren: it matches the closing `)` before processing
# the heredoc. So the substitution became a SYNTAX ERROR the moment a prose comment in the Python
# body used an apostrophe. CI runs bash 5 and parses it happily, so this would have shipped green
# and been broken on every machine that actually runs the hooks. Measured: bash 3.2.57 fails.
tmp_out="$(mktemp "${TMPDIR:-/tmp}/unleashed-drift.XXXXXX")" || exit 0
trap 'rm -f "${tmp_out}"' EXIT

EXPECTED_JSON="${expected_json}" INSTALLED_RECORD="${installed_record}" OUT_FILE="${tmp_out}" \
	python3 <<'PY' 2>/dev/null
import json, os, re, sys

SEMVER = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


def parse(value):
    """SemVer 2.0.0, or None. Row 4's 'comparable' means exactly this."""
    if not isinstance(value, str):
        return None
    m = SEMVER.match(value.strip())
    if not m:
        return None
    pre = m.group("pre")
    return (int(m.group("major")), int(m.group("minor")), int(m.group("patch")), pre)


def precedence(v):
    """SemVer precedence. Build metadata is IGNORED, which is why row 5 exists: two versions can be
    of equal precedence and yet not be the same string."""
    major, minor, patch, pre = v
    if pre is None:
        return (major, minor, patch, 1, ())
    parts = []
    for part in pre.split("."):
        parts.append((0, int(part), "") if part.isdigit() else (1, 0, part))
    return (major, minor, patch, 0, tuple(parts))


try:
    expected_raw = json.loads(os.environ["EXPECTED_JSON"]).get("version")
except Exception:
    sys.exit(0)                                   # row 1 — malformed manifest
expected = parse(expected_raw)
if expected is None:
    sys.exit(0)                                   # rows 1/4 — no usable expected value

try:
    with open(os.environ["INSTALLED_RECORD"], encoding="utf-8") as handle:
        record = json.load(handle)
except Exception:
    sys.exit(0)                                   # row 2 — unreadable record
if not isinstance(record, dict):
    sys.exit(0)                                   # row 2 — unrecognised schema

# THE RECORD'S ACTUAL SHAPE, READ FROM A REAL MACHINE RATHER THAN ASSUMED:
#     {"version": 2, "plugins": {"<name>@<marketplace>": [{"scope": …, "version": …, …}, …]}}
# The first draft of this detector assumed {scope: {name: info}} and was therefore SILENT FOREVER —
# inert on exactly the machines it exists to warn, which is the same failure class as reading the
# wrong repository. Verified against `~/.claude/plugins/installed_plugins.json`, where the entry that
# prompted COREDEV-2801 is `unleashed-mail@npranson-unleashed-mail-plugin` at 2.7.0.
plugins = record.get("plugins")
if not isinstance(plugins, dict):
    sys.exit(0)                                   # row 2 — unrecognised schema

# Evaluated PER INSTALL ENTRY; the hook warns if ANY entry reaches row 7. One plugin key can carry
# several installs (different scopes), so the value is a list.
entries = []
for key, installs in plugins.items():
    if str(key).split("@", 1)[0] != "unleashed-mail":
        continue                                  # row 3 — the entry is absent
    if isinstance(installs, dict):
        installs = [installs]                     # tolerate a single-object form
    if not isinstance(installs, list):
        continue                                  # row 2 for this key
    for info in installs:
        if not isinstance(info, dict):
            continue
        entries.append((info.get("scope") or "?", key, info.get("version")))

if not entries:
    sys.exit(0)                                   # row 3

behind = []
for scope, name, version in entries:
    installed = parse(version)
    if installed is None:
        continue                                  # row 4 — not comparable
    if precedence(installed) == precedence(expected):
        # row 5 (equal precedence, different identity) and row 6 (exact identity) are both silent.
        continue
    if precedence(installed) < precedence(expected):
        behind.append(f"{scope}:{name} {version}")   # row 7 — the drift this exists for
    # row 8 (installed > expected) is silent: a locally newer install is not drift, and warning here
    # would fire on every development clone.

if behind:
    with open(os.environ["OUT_FILE"], "w", encoding="utf-8") as handle:
        handle.write(
            "unleashed-mail: " + ", ".join(sorted(behind))
            + f" is behind origin/main {expected_raw} — "
            + "run `claude plugin update unleashed-mail` to pick up fixes already released"
        )
PY

warning="$(cat "${tmp_out}")"

# Silent rows produce no output at all, and take no other action.
[[ -n ${warning} ]] || exit 0

if [[ ${mode} != "--session-start" ]]; then
	printf '%s\n' "${warning}"
	exit 0
fi

# ---- SessionStart: dedup per session per retention window, then emit the hook's own protocol -------
#
# THE MARKER ENCODES THE WINDOW IN ITS NAME so a live marker is never unlinked. An age-based sweep
# races with itself: two invocations of the same session both stat an aged marker, A unlinks and
# recreates it, B's already-decided unlink removes A's FRESH marker, and B's O_EXCL create then
# succeeds — so both warn in the same new window. With the window in the name the sweep removes only
# strictly older buckets and the decision is a single O_EXCL create.
#
# `session_id` is documented as OPAQUE with no filename-safety contract, so it is HASHED: raw, a `/`
# or an over-long component makes marker creation fail, and a detector that fails open warns on every
# single session start.
state_base="${XDG_STATE_HOME:-${HOME}/.local/state}"
marker_dir="${state_base}/unleashed-mail/drift-warned"

# THE PAYLOAD IS READ HERE, NOT INSIDE PYTHON. `python3 <<'PY'` redirects python's stdin to the
# HEREDOC, so `json.load(sys.stdin)` there reads the program text rather than the hook's JSON — it
# fails, `session_id` falls back to the empty string, and every session then shares one marker named
# for sha256(""). Dedup silently becomes GLOBAL instead of per-session: the first session to start in
# a seven-day window warns, and every other session on the machine stays quiet. Caught by inspecting
# the marker NAMES; "it warned once" looked correct and was correct for the wrong reason.
# A TTY ON STDIN MEANS NOBODY PIPED A PAYLOAD, so there is nothing to read and `cat` would block
# forever — reproduced: a manual `--session-start` run hangs until interrupted (gemini, PR #84).
#
# The obvious repair is to substitute an empty payload, and it is WRONG: `session_id` would then be
# the empty string, every marker would be named for sha256("") and the per-session dedup this file
# exists to provide would silently become global — the exact defect the comment above describes. A
# TTY means a human is running this by hand, so it degrades to the plain-text path instead: same
# warning, no marker, no protocol output that no hook is there to consume.
if [[ -t 0 ]]; then
	printf '%s\n' "${warning}"
	exit 0
fi
hook_payload="$(cat)"

WARNING="${warning}" MARKER_DIR="${marker_dir}" HOOK_PAYLOAD="${hook_payload}" python3 <<'PY' 2>/dev/null
import hashlib, json, os, pathlib, re, sys, time

try:
    payload = json.loads(os.environ.get("HOOK_PAYLOAD") or "{}")
except Exception:
    payload = {}
session_id = payload.get("session_id") if isinstance(payload, dict) else None
session_id = session_id if isinstance(session_id, str) else ""

# Fixed seven-day buckets from the epoch — NOT a rolling window anchored on the marker's own mtime,
# which would make the promise unstatable. The cost is honest and stated: a session started just
# before a boundary can warn twice within minutes.
window = int(time.time()) // 604800

marker_dir = pathlib.Path(os.environ["MARKER_DIR"])
digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
marker = marker_dir / f"{digest}.{window}"

try:
    marker_dir.mkdir(parents=True, exist_ok=True)
    # O_EXCL BEFORE the warning: two concurrent invocations of one session race here, and the loser
    # goes silent rather than warning twice.
    os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
except FileExistsError:
    sys.exit(0)
except OSError:
    # A state directory we cannot write is not a reason to spam every session start.
    sys.exit(0)

# A SessionStart hook's PLAIN STDOUT is injected into the agent's CONTEXT; only `systemMessage` is
# shown to the human as a notice.
#
# EMITTED BEFORE THE SWEEP, AND FLUSHED. The hook is declared with `timeout: 5`; the sweep below is
# O(directory) and on a machine that has accumulated a backlog it is the slowest thing here. Ordering
# the decision and the warning ahead of it means a timeout kill during cleanup costs that session
# nothing but the cleanup — the warning it was run to produce has already been written.
print(json.dumps({"systemMessage": os.environ["WARNING"]}), flush=True)

# Cleanup removes markers from any PRIOR window — which is not the same statement as "older than
# seven days": just after a boundary a marker seconds old belongs to a prior bucket and goes.
#
# SWEEP EVERY SESSION'S MARKERS, not just this one's (codex, PR #84). Each session has a distinct
# digest, so a per-digest glob only ever tidied a session that RESUMED in a later window — markers for
# sessions that never resume accumulated forever, one inode per session, on exactly the machines a
# persistently stale install keeps warning. The retention promise was stated and not kept.
#
# Safe against the O_EXCL protocol precisely because the window is in the NAME: only buckets STRICTLY
# OLDER than the current one are removed, so no live marker of any session is touched, and there is
# nothing to race with a concurrent create.
#
# THE SHAPE GUARD IS LOAD-BEARING NOW THAT THE GLOB IS WIDE. Scoped to one digest, the name was its
# own filter; unscoped, this loop unlinks in a directory it no longer wholly owns. Only names this
# script could itself have written are candidates — anything else is left alone rather than left to
# the accident of whether its suffix happens to parse as an integer.
#
# Bounds growth only WHILE THE INSTALL IS STALE: the silent path exits before this block by contract
# (SILENT MEANS SILENT), so markers left by an install that is then updated are swept by nothing and
# remain. That residue is bounded by one window's sessions, and is stated rather than fixed here.
marker_name = re.compile(r"\A[0-9a-f]{64}\.([0-9]+)\Z")
for stale in marker_dir.glob("*.*"):
    matched = marker_name.match(stale.name)
    if matched is None:
        continue
    try:
        if int(matched.group(1)) < window:
            stale.unlink()
    except (ValueError, OSError):
        pass
PY
exit 0
