#!/usr/bin/env bash
# Run a Gemini plan review through the `gemini` CLI WITHOUT letting it write to the tree under review
# (COREDEV-2887; the isolation design is COREDEV-2607's).
#
# WHY ISOLATION, EVEN THOUGH THE CLI HAS A READ-ONLY MODE
# `--approval-mode plan` refuses writes only while the model STAYS in plan mode. Headless, the policy
# engine auto-approves `exit_plan_mode`, and leaving switches to YOLO, which auto-approves every tool.
# Observed 2026-10-14 (plan §1 F4): asked to leave plan mode and write, `gemini-3.1-pro-preview` did —
# it created a file, ran a shell command and overwrote another, all in a scratch directory. A reviewer
# that decides to implement the plan instead of reviewing it is the COREDEV-2607 failure (`agy`
# implemented a plan on 2026-07-29: 6 scripts modified, 5 files created).
#
# SO THREE LAYERS, ONE GUARANTEE:
#   1. `--approval-mode plan` — first line.
#   2. `gemini-review-policy.toml`, loaded per run with `--policy`: priority-999 DENY on
#      `exit_plan_mode`, `write_file`, `replace` and `run_shell_command`. Denied tools are withheld from
#      the model (observed: it reported `exit_plan_mode` "not available"), closing the YOLO path.
#   3. THE GUARANTEE: the reviewer runs against a disposable private checkout of the reviewed commit, and
#      both the real tree and that checkout are fingerprinted before and after. Any change VOIDS the
#      round (exit 3) rather than being cleaned up — the rule `AGENT_CONTRACTS.md` §2 step 0b applies to
#      the author, applied to the reviewer. Layers 1 and 2 reduce how often this fires; they do not
#      replace it.
#
# THE MODEL THAT ANSWERED IS ASSERTED. The CLI can fall back or route to another model mid-session
# (plan §1 F5). `gemini-review-run.py` runs it with `-o json` and refuses the round unless
# `stats.models` names exactly the requested model; routing is also switched off for the disposable
# workspace (`.gemini/settings.json`, staged below).
#
# Usage: isolated-gemini-review.sh <prompt-file> <allocated-path> [timeout-seconds] [plan-file]
#   <prompt-file>  path to the review prompt, RELATIVE TO THE REPO ROOT (e.g. .agy-prompt-2597r4.md)
#   <allocated-path>  exact reserved transcript leaf received from allocate-transcript.sh
# Exit: 0 review captured · 1 setup/prompt failure · 3 round VOID — the reviewer mutated the working
#       tree, modified the round's staged basis (plan or prompt) inside the disposable checkout, or
#       wrote anything else there (the COREDEV-2607 signature) · 4 the answering model could not be
#       confirmed (gemini-review-run.py), so the capture is not a review
set -uo pipefail

# NO BYTECODE FROM THIS HARNESS, ANYWHERE (COREDEV-2650; extended after PR #81 review).
# The reviewer subshell below sets this too — that is the load-bearing one, because a `.pyc` inside
# the DISPOSABLE checkout is read as reviewer tampering and voids the round. Setting it here as well
# covers this script's OWN python helpers (containment.py, stage-bound-plan.py, stage-prompt.py),
# which write into the LIVE checkout's `scripts/review/__pycache__/`.
# STATED PRECISELY, because the review comment that prompted this inferred more than holds: a live-tree
# `.pyc` canNOT void a round. `__pycache__/` is gitignored (.gitignore:38) and `tree_fingerprint`
# hashes HEAD + `status --porcelain` + TRACKED content + git metadata, so an ignored untracked file is
# invisible to it. Measured: the live fingerprint was byte-identical before, during and after a
# synthetic `.pyc` was planted. This is hygiene and defence-in-depth, not a fix for an observed void.
export PYTHONDONTWRITEBYTECODE=1

_sha256() { python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }

[[ $# -ge 2 ]] || {
	echo "usage: $0 <prompt-file> <allocated-path> [timeout]" >&2
	exit 1
}
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
. "${SCRIPT_DIR}/tree-fingerprint.sh"
PLUGIN_WRITER="${SCRIPT_DIR}/../pty-capture.py"
PROMPT_REL="$1"
OUT="$2"
TIMEOUT="${3:-1800}" # the whole review's wall clock; the `gemini` CLI has no print-timeout of its own
PLAN_REL="${4-}"     # optional: the plan the run is BOUND to (see the copy below)
# Reviewer model: the `DEFAULT_MODEL` below (COREDEV-2887). 3.1 Pro was retired from `agy`, whose
# remaining flash family the maintainer judged short of Pro for gate reviews and which stopped answering
# on 2026-10-12. The `gemini` CLI has NO model-listing command, so there is nothing to resolve from: the
# default is this one literal, and a retired preview fails the preflight and the round CLOSED with the
# model's name (gemini-review-run.py). An explicit MODEL — the capture wrapper's sixth operand — still
# wins for a one-round override.
DEFAULT_MODEL="gemini-3.1-pro-preview"
if [[ -n ${MODEL:-} ]]; then
	MODEL_SOURCE=override
else
	MODEL="${DEFAULT_MODEL}"
	MODEL_SOURCE=default
fi
# ONE TOKEN, WHATEVER ITS SOURCE (COREDEV-2875 §2.1). The id reaches the CLI's argv and the `.model` record
# below, so a newline, a space, a control byte or a leading `-` must never get that far. The capture
# wrapper checks its sixth operand the same way before allocating; this check is the one that also covers
# an environment MODEL, which the capture wrapper never sees.
case "${MODEL}" in
'' | [!A-Za-z0-9]* | *[!A-Za-z0-9._-]*)
	printf 'GATE FAILED — the model id %q is not one token ([A-Za-z0-9][A-Za-z0-9._-]{0,127})\n' "${MODEL}" >&2
	exit 1
	;;
*) ;;
esac
if [[ ${#MODEL} -gt 128 ]]; then
	echo "GATE FAILED — the model id is longer than 128 characters" >&2
	exit 1
fi

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO="${PWD}"
# CAPTURED BEFORE THE `cd`. `bind-prompt.py` accepted the plan operand relative to the CALLER'S
# directory; this script then changed to the repository root and reinterpreted the same string there,
# so a plan the binder had just accepted became unreadable here (PR #63 recheck, P2 — see the
# resolution below).
CALLER_PWD="${PWD}"
cd "${REPO}" || exit 1
[[ -r ${PROMPT_REL} ]] || {
	echo "prompt not readable: ${REPO}/${PROMPT_REL}" >&2
	exit 1
}

# Repo-relative identity of $1 interpreted against base $2, or non-zero if it does not exist there or
# resolves outside the repository. Only the PARENT is resolved through `pwd -P`: a symlinked leaf must
# still reach the readability check rather than be laundered into a clean-looking relative path here.
resolve_in_repo() {
	local candidate="$1" base="$2" parent leaf
	case "${candidate}" in /*) ;; *) candidate="${base}/${candidate}" ;; esac
	[[ -e ${candidate} ]] || return 1
	parent="$(CDPATH='' cd -- "$(dirname -- "${candidate}")" 2>/dev/null && pwd -P)" || return 1
	leaf="${parent}/$(basename -- "${candidate}")"
	case "${leaf}" in
	"${REPO}"/*) printf '%s\n' "${leaf#"${REPO}"/}" ;;
	*) return 1 ;;
	esac
}

SCR="$(mktemp -d)"
# shellcheck disable=SC2329 # invoked by the EXIT trap below
cleanup() {
	rm -rf "${SCR}"
}
trap cleanup EXIT

# --- before: fingerprint the real tree --------------------------------------------------------
# CONTENT-AWARE, NOT STATUS-CATEGORY-ONLY (PR #63 recheck, P1). `git status --porcelain` emits one
# line per path, so a reviewer editing an ALREADY-DIRTY tracked file left the line byte-identical
# and this comparison — the gate-bearing COREDEV-2607 detector, whose failure VOIDS the round —
# saw nothing. The same defect was found and fixed in the (retired) `agy` preflight first; the fix did not
# reach here, so the rule now lives in `tree-fingerprint.sh` and all three source it.
BEFORE_STATUS="$(git status --porcelain)"
if ! BEFORE="$(tree_fingerprint "${REPO}")"; then
	echo "GATE FAILED — could not fingerprint the live checkout before the review" >&2
	exit 3
fi

# --- disposable detached checkout at the exact reviewed commit --------------------------------
SHA="$(git rev-parse HEAD)"
# A PRIVATE clone, never a linked worktree — a linked worktree's `.git` points into the maintainer's
# real repository and every git operation the reviewer runs lands there (see disposable_checkout in
# tree-fingerprint.sh; adversarial verification, PR #67 pass 6).
disposable_checkout "${REPO}" "${SHA}" "${SCR}/tree" ||
	{
		echo "could not create the private review checkout" >&2
		exit 1
	}
TREE="${SCR}/tree"

# A REVIEWED TREE CANNOT CONFIGURE ITS REVIEWER, checked FIRST — before the plan or the prompt is staged
# (codex, plan round 3). The CLI reads a workspace `.gemini/` (settings: MCP servers, tools, approval) and a
# workspace `.env` (endpoint, credentials, flags), so a committed entry of either would configure the reviewer,
# and a symlink there could redirect the settings write below. Neither this repository nor UnleashedMail
# commits one (checked 2026-10-14). A committed `.mcp.json` is NOT refused: the CLI does not read it (plan §1
# F13 B). Env files ABOVE the tree are the adapter's check, in the reviewer's own working directory.
if [[ -e "${TREE}/.env" ]] || [[ -L "${TREE}/.env" ]]; then
	echo "GATE FAILED — the reviewed tree commits a .env entry; refusing to let it configure the reviewer" >&2
	exit 1
fi
if [[ -e "${TREE}/.gemini" ]] || [[ -L "${TREE}/.gemini" ]]; then
	echo "GATE FAILED — the reviewed tree already has a .gemini entry; refusing to configure the reviewer through it" >&2
	exit 1
fi
# NOR CAN IT INSTRUCT ITS REVIEWER (codex, PR #124 review, P1). The CLI loads every `GEMINI.md` in the workspace
# — the root and, by discovery, its subdirectories — into the reviewer's context with every prompt. Measured on
# 0.64.0: a committed `GEMINI.md` saying "reply PINEAPPLE" made 3.1 Pro answer PINEAPPLE to a `pong` ping, and
# STILL did with `context.fileName` set to another name, because that setting only ADDS names to the default
# list (`setGeminiMdFilename`). So a committed context file, at any depth, refuses the round. Matched
# case-insensitively: on a case-insensitive filesystem the CLI's existence check finds `gemini.md` too. A
# listing that fails refuses as well. Neither this repository nor UnleashedMail commits one (checked 2026-10-14).
# EVERY CONFIGURED NAME, NOT ONLY THE DEFAULT (PR #124 review, P1): the operator's user, system or system-default
# settings can ADD context names (`context.fileName`, e.g. `AGENTS.md`), and a committed file under any of them
# is loaded the same way, so the scan matches each configured name too. Settings that cannot be read or parsed
# refuse, rather than shrinking the scan to the default. (Extension-supplied names are moot: the adapter runs
# with `--extensions none`.)
if ! python3 - "${TREE}" <<'PY'; then
import json
import os
import re
import subprocess
import sys


def strip_comments(text):
    """Drop // and /* */ comments outside JSON strings — the CLI's settings files are JSON with comments."""
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            match = re.compile(r'"(?:\\.|[^"\\])*"').match(text, i)
            if not match:
                return text
            out.append(match.group(0))
            i = match.end()
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def settings_paths():
    """The settings files the CLI reads besides the staged workspace one: system defaults, user, system."""
    system = os.environ.get("GEMINI_CLI_SYSTEM_SETTINGS_PATH") or (
        "/Library/Application Support/GeminiCli/settings.json"
        if sys.platform == "darwin"
        else "/etc/gemini-cli/settings.json"
    )
    defaults = os.environ.get("GEMINI_CLI_SYSTEM_DEFAULTS_PATH") or os.path.join(
        os.path.dirname(system), "system-defaults.json"
    )
    home = os.environ.get("HOME", "")
    user = os.path.join(home, ".gemini", "settings.json") if home else ""
    return [path for path in (defaults, user, system) if path]


names = {"gemini.md"}
for path in settings_paths():
    if not os.path.exists(path):
        continue
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.loads(strip_comments(handle.read()))
    except (OSError, ValueError) as error:
        sys.exit(f"GATE FAILED — could not read {path} to learn its context file names: {error}")
    context = data.get("context") if isinstance(data, dict) else None
    configured = context.get("fileName") if isinstance(context, dict) else None
    for name in [configured] if isinstance(configured, str) else configured if isinstance(configured, list) else []:
        cleaned = os.path.normpath(str(name).strip()).lower() if str(name).strip() else ""
        if cleaned and cleaned != ".":
            names.add(cleaned.removeprefix("./"))

env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
try:
    listed = subprocess.run(
        ["git", "-C", sys.argv[1], "ls-files", "-z"], env=env, capture_output=True, check=True
    ).stdout
except (OSError, subprocess.CalledProcessError) as error:
    sys.exit(f"GATE FAILED — could not list the reviewed tree for context files: {error}")
hits = []
for raw in listed.split(b"\0"):
    path = raw.decode("utf-8", "surrogateescape").lower()
    if path and any(path == name or path.endswith("/" + name) for name in names):
        hits.append(raw.decode("utf-8", "replace"))
if hits:
    sys.exit(
        "GATE FAILED — the reviewed tree commits a Gemini context file ("
        + hits[0]
        + "); its instructions would reach the reviewer with every prompt"
    )
PY
	exit 1
fi

# COPY THE BOUND PLAN INTO THE CHECKOUT. The tree above is detached at HEAD, so `agy` reads the
# COMMITTED plan — while `bind-prompt.py` hashed the WORKING-TREE plan into `<transcript>.plan`. With
# uncommitted edits, which is the normal state during the documented review iteration, the transcript
# approved the committed version and the artifact recorded it as evidence for the edited one: two
# correct digests describing different bytes (PR #63 recheck, P1).
#
# Copying rather than refusing keeps the iterate-then-review loop working, and it makes the binding
# TRUE rather than merely checkable — the reviewer now reads exactly the bytes the sidecar attests to.
if [[ -n ${PLAN_REL} ]]; then
	# NORMALIZE AGAINST THE CALLER, THEN THE ROOT. Two spellings reached this line and each broke a
	# different way:
	#   * an ABSOLUTE in-repo path pasted into "$TREE/$PLAN_REL" built a nested destination like
	#     `$TREE/Users/…/docs/planning/X.md` while the rewritten prompt still pointed `agy` at
	#     `$TREE/docs/planning/X.md`, so the copy landed where the reviewer never looks and it read the
	#     COMMITTED plan again — the very defect the copy was added to fix; and
	#   * a CALLER-RELATIVE path such as `../docs/planning/X_PLAN.md` passed from `scripts/`, which
	#     `bind-prompt.py` had already accepted, died here as "plan not readable" because this script had
	#     `cd`'d to the root first. Reproduced from `scripts/` (PR #63 recheck, P2).
	#
	# Caller-relative is tried FIRST because the binder is the authority on what was bound. Root-relative
	# stays as a fallback so callers that pass a root-relative path from a subdirectory keep working, and
	# the ambiguous case — both exist and name DIFFERENT files — is refused rather than silently resolved
	# to whichever branch happens to be tested first.
	PLAN_OPERAND="${PLAN_REL}"
	FROM_CALLER="$(resolve_in_repo "${PLAN_OPERAND}" "${CALLER_PWD}")" || FROM_CALLER=""
	FROM_ROOT="$(resolve_in_repo "${PLAN_OPERAND}" "${REPO}")" || FROM_ROOT=""
	if [[ -n ${FROM_CALLER} ]] && [[ -n ${FROM_ROOT} ]] && [[ ${FROM_CALLER} != "${FROM_ROOT}" ]]; then
		echo "ambiguous plan operand: '${PLAN_OPERAND}' names ${FROM_CALLER} from the caller's directory" >&2
		echo "and ${FROM_ROOT} from the repository root — pass an absolute path" >&2
		exit 1
	fi
	PLAN_REL="${FROM_CALLER:-${FROM_ROOT}}"
	[[ -n ${PLAN_REL} ]] ||
		{
			echo "plan not readable, or outside the repository: ${PLAN_OPERAND}" >&2
			exit 1
		}
	[[ -r ${PLAN_REL} ]] || {
		echo "plan not readable: ${REPO}/${PLAN_REL}" >&2
		exit 1
	}
	# The staging destination is built by a DESCRIPTOR WALK inside the python below, not a `mkdir -p` +
	# `open("$TREE/$PLAN_REL")`. the detached checkout MATERIALIZES committed tree entries — so if
	# HEAD records the plan path as a SYMLINK (or any parent as one), the checkout recreates that link,
	# and a plain open followed it to overwrite an outside victim. Reproduced: HEAD carries
	# `docs/planning/X_PLAN.md -> /outside/victim`, the live worktree replaces it with a real plan, and
	# staging clobbered the victim (PR #63 recheck, P1). Every component is now opened O_NOFOLLOW and
	# the leaf is unlinked-then-O_EXCL-created, so no symlink is ever traversed.
	# STAGE THE BINDER'S SNAPSHOT, not the live path. `bind-prompt.py` kept the exact bytes it hashed
	# in `<transcript>.planbytes`; copying the working-tree path instead re-read a mutable source, so a
	# plan edited after binding and restored before synthesis could reach the reviewer while both the
	# sidecar and the final digest described the restored bytes. The old `cmp` re-opened that same path
	# and so proved only that two reads agreed at copy time (PR #63 recheck, P1).
	PLAN_SNAPSHOT="${OUT}.planbytes"
	# STAGING IS THE SHARED HELPER, not inline python — the codex arm ran in the live tree because the
	# gemini fix lived only here, and a rule in one script is a rule the next entrypoint will not have.
	# `stage-bound-plan.py` authenticates the snapshot against its `.plan` record, reads it once through
	# an O_NOFOLLOW descriptor, and writes it through a no-follow descriptor walk (a materialized symlink
	# leaf or parent is refused). It prints the digest of what it staged, which anchors the post-run
	# basis check below (PR #63 recheck, P1).
	# THE BOUND SNAPSHOT IS MANDATORY (PR #63 recheck, P1). `bind-prompt.py` writes `.planbytes` and
	# `.plan` together, so absence is tampering, not legacy — and the fallback it used to take quietly
	# re-read the LIVE, mutable plan. That made `rm` the cheapest attack on the strongest binding in the
	# chain: bind plan A, delete the snapshot, point the live plan at B, and the reviewer read B while
	# `review-verdict` (which requires `.plan` and never reads `.planbytes`) approved A.
	#
	# The requirement is UNCONDITIONAL. It was first scoped to captures carrying a `.launch` record, on
	# the theory that a direct or legacy call had no binder run — but this harness only ever invokes
	# `pty-capture --allocated`, which itself refuses a leaf whose `.launch` is absent or malformed. The
	# scoped condition was therefore true in every run that could complete, and the live-plan fallback
	# was unreachable: a weaker path nobody could take, waiting for an edit to re-expose it.
	if [[ ! -r ${PLAN_SNAPSHOT} ]]; then
		echo "GATE FAILED — no bound plan snapshot beside the transcript: ${PLAN_SNAPSHOT}" >&2
		echo "(the binder writes it with .plan; absence means it was removed. Re-capture the round.)" >&2
		exit 1
	fi
	EXPECTED_PLAN_SHA="$(python3 "${SCRIPT_DIR}/stage-bound-plan.py" \
		--tree "${TREE}" --rel "${PLAN_REL}" --snapshot "${PLAN_SNAPSHOT}" --record "${OUT}.plan")" ||
		exit 1
fi

# --- authenticate the bound prompt, rewrite paths, prepend the guard, stage it ------------------
# ONE SHARED HELPER, for the same reason plan staging is shared: this used to be `sed` plus inline
# python in each harness, and the two arms drifted. `stage-prompt.py` authenticates the snapshot
# against `<transcript>.promptsha256` BEFORE transforming it (the staging path never compared them, so
# a snapshot rewritten after binding and restored before synthesis had the reviewer read substituted
# instructions), substitutes the repository path as LITERAL BYTES (the `sed "s#…#…#"` expression was
# assembled from a path, so a checkout containing `#` aborted every capture), prepends the read-only
# guard, enforces the size floor, and writes through a no-follow descriptor walk (PR #63 recheck, P1+P2).
#
# THE PROMPT BINDING IS MANDATORY, exactly as the plan snapshot is (PR #63 recheck, P1). This branched
# on the sidecar's presence and staged the snapshot UNAUTHENTICATED when it was absent — the same
# "absent means unchecked" fail-open, reachable by one `rm`. `bind-prompt.py` writes `.prompt` and
# `.promptsha256` together and `pty-capture --allocated` refuses a leaf without a `.launch`, so no run
# that could complete ever needed the fallback.
if [[ ! -r "${OUT}.promptsha256" ]]; then
	echo "GATE FAILED — no prompt binding beside the transcript: ${OUT}.promptsha256" >&2
	echo "(the binder writes it with .prompt; absence means it was removed. Re-capture the round.)" >&2
	exit 1
fi
PROMPT_TREE_SHA="$(python3 "${SCRIPT_DIR}/stage-prompt.py" \
	--snapshot "${PROMPT_REL}" --record "${OUT}.promptsha256" \
	--tree "${TREE}" --rel "${PROMPT_REL}" --repo "${REPO}" --guard --min-bytes 1000)" || exit 1

# --- run --------------------------------------------------------------------------------------
# The reserved leaf must be EMPTY. It is created 0-byte by the allocator, and nothing but this
# capture may write it. A non-empty leaf means it has already been used, and reusing it is how a
# failed round gets reported as an approval: `--allocated` deliberately omits O_CREAT (to preserve
# the reservation), so before PR #63 it also omitted truncation, and a shorter second write left the
# first round's tail — including its `VERDICT:` line — for the `tail -1` below to find. Reproduced:
# a 19-byte failed round left 55 bytes reading `VERDICT: APPROVE`. pty-capture.py now ftruncates, so
# this is defence in depth; it also catches the case where the leaf was written by something else
# entirely. Refuse rather than clean: deleting the leaf would destroy the reservation, and silently
# overwriting would hide that the caller reused a path it should have re-allocated.
if [[ -s ${OUT} ]]; then
	echo "refusing to reuse a non-empty reserved leaf: ${OUT}" >&2
	# shellcheck disable=SC2312 # a diagnostic byte count; its failure only blanks part of the message
	echo "(it already holds $(wc -c <"${OUT}" | tr -d ' ') bytes — allocate a fresh leaf for this round)" >&2
	exit 1
fi
# ROUTING OFF, FOR THIS WORKSPACE ONLY (plan §1 F5). Plan-mode model routing can hand turns to Flash; the
# adapter would then refuse the round, so routing is switched off where it applies — the disposable
# checkout's own `.gemini/settings.json` — and never in the operator's global settings. Staged BEFORE the
# baseline below, so it is part of what the harness placed and a reviewer edit to it still voids the round.
# A committed `.gemini` entry was refused right after the checkout was created, above.
# FILE FILTERING OFF TOO (local codex diff review, P2). The CLI's file tools honour `.gitignore` and
# `.geminiignore` by default, and the staged prompt sits at its state-directory path mirrored under the tree:
# with `XDG_STATE_HOME=$HOME/logs` a reviewed repo's `logs/` rule hid it, and the reviewer could not read its
# own task (reproduced: `UNREADABLE` by default, the file's word with filtering off). This checkout holds only
# committed files plus what the harness staged, so nothing in it is legitimately ignored — and a committed
# `.geminiignore` must not be able to hide the plan from the reviewer either.
if ! python3 - "${TREE}" <<'PY'; then
import os
import sys

tree = sys.argv[1]
os.mkdir(os.path.join(tree, ".gemini"), 0o700)
path = os.path.join(tree, ".gemini", "settings.json")
payload = (
    b'{"general": {"plan": {"modelRouting": false}}, '
    b'"context": {"fileFiltering": {"respectGitIgnore": false, "respectGeminiIgnore": false}}}\n'
)
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
try:
    os.write(fd, payload)
finally:
    os.close(fd)
PY
	echo "GATE FAILED — could not stage the reviewer's workspace settings" >&2
	exit 1
fi

# The baseline: everything the HARNESS put in the tree (the prompt, the staged plan), by CONTENT.
# Anything different after the run is the reviewer's doing. NOT `git status`, which the reviewer
# controls (see disposable_fingerprint), and NOT `|| true` — a probe that fails is not a clean tree
# (adversarial verification, PR #67 pass 6: this baseline still carried the fallback the post-review
# probe below had lost in PR #63).
if ! TREE_BASELINE="$(disposable_fingerprint "${TREE}")"; then
	echo "GATE FAILED — could not fingerprint the disposable checkout before the review" >&2
	exit 1
fi

# THE MODEL IS RECORDED BESIDE THE TRANSCRIPT, NEVER IN IT (COREDEV-2875 §2.1). A banner line inside the
# transcript made a silent reviewer's transcript non-empty, and `review-verdict.py` refuses an approval only
# for a ZERO-byte transcript (codex r4) — so the transcript stays the reviewer's bytes alone, and the
# `<id>TAB<source>` line goes to `${OUT}.model`. It records the model selected for an ATTEMPTED launch:
# pty-capture.py validates the reservation and `.launch` after this point, so a launch it refuses leaves a
# `.model` beside an empty (MISSING) transcript. It is a record for the operator, not gate evidence.
# ONE OPEN, O_EXCL | O_NOFOLLOW — the primitive of bind-prompt.py's write_sidecar_bytes. NOT `set -C`:
# bash's noclobber refuses only an existing REGULAR file and opens a FIFO, which hangs here before the PTY
# timeout has started (codex r5; measured). Any existing entry at the name refuses the round.
if ! python3 - "${OUT}.model" "${MODEL}" "${MODEL_SOURCE}" <<'PY'; then
import os
import sys

path, model, source = sys.argv[1:4]
payload = f"{model}\t{source}\n".encode("ascii")
try:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
except FileExistsError:
    sys.exit(f"an entry already exists at {path} — refusing to write the model record through it")
except OSError as error:
    sys.exit(f"could not create {path}: {error}")
written = 0
try:
    while written < len(payload):
        count = os.write(descriptor, payload[written:])
        if count <= 0:
            raise OSError(f"wrote {count} bytes")
        written += count
except OSError as error:
    os.close(descriptor)
    try:
        os.unlink(path)
    except OSError:
        pass
    sys.exit(f"could not write {path} in full ({written} of {len(payload)} bytes: {error}); removed it")
os.close(descriptor)
PY
	echo "GATE FAILED — could not record the round's model beside the transcript: ${OUT}.model" >&2
	exit 1
fi

# Preserve the allocator's reserved leaf for pty-capture.py --allocated to open.
# stdout only is silenced; pty-capture's STDERR passes through so its diagnostics (timeout notice,
# allocated-leaf/launch refusal reasons, capture-write failures) reach the operator instead of the
# round ending as a bare EXIT=n with the reason discarded (2026-08-17 audit, AF-10). The transcript
# itself still goes to $OUT, not to either stream.
# PYTHON BYTECODE IS NOT A REVIEWER MUTATION (COREDEV-2650; it voided COREDEV-2711 r1 and r8).
# A reviewer that IMPORTS a repo module to reproduce a measured claim — the single best thing a
# reviewer can do, and what this round's prompt asks for — makes CPython write `__pycache__/*.pyc`
# beside the source. This harness fingerprints the disposable checkout afterwards, so that
# bytecode read as `ROUND VOID: the reviewer left edits … COREDEV-2607 signature` and threw away a
# valid review whose finding was independently confirmed by another arm. At r8 it voided TWO of
# the three arms this way — agy and kimi — leaving the round resting on codex alone. The check
# is right and
# keeps its teeth; what was wrong is letting the artefact exist. Suppress it at the source rather
# than excluding a path from the manifest — an exclusion is a blacklist a real mutation could hide
# behind, and `scripts/__pycache__/` is exactly where it would hide.
# THE DIAGNOSTICS FILE MUST NOT EXIST YET. The adapter creates it exclusively and refuses silently when it
# cannot — silently because any text it printed would reach the transcript — so the entry is named HERE, and
# no review (and no quota) is spent on a round that could not record its diagnostics.
if [[ -e "${OUT}.diag" ]] || [[ -L "${OUT}.diag" ]]; then
	echo "GATE FAILED — an entry already exists at ${OUT}.diag; refusing to launch a review that cannot record its diagnostics" >&2
	exit 1
fi
# THE REVIEWER IS THE ADAPTER, not the CLI directly: it asserts the answering model and writes only the
# response text, which is the transcript (gemini-review-run.py). The policy is read from THIS checkout's
# scripts, never from the disposable tree the reviewer can see. The CLI's stderr goes to `${OUT}.diag` and
# NEVER to the transcript: pty-capture records stdout and stderr together, so stderr text could otherwise
# supply an anchored `VERDICT:` (codex, plan round 1). `.diag` is created exclusively by the adapter, so a
# pre-existing entry there refuses the round rather than being written through.
(cd "${TREE}" && export PYTHONDONTWRITEBYTECODE=1 && python3 "${PLUGIN_WRITER}" --timeout "${TIMEOUT}" --allocated "${OUT}" -- \
	python3 "${SCRIPT_DIR}/gemini-review-run.py" --model "${MODEL}" --policy "${SCRIPT_DIR}/gemini-review-policy.toml" \
	--diagnostics "${OUT}.diag" -- \
	"Read and follow ${TREE}/${PROMPT_REL}") >/dev/null
RC=$?

# --- after: the assertion that would have caught COREDEV-2607 --------------------------------
if ! AFTER="$(tree_fingerprint "${REPO}")"; then
	{
		echo "GATE FAILED — could not fingerprint the live checkout after the review (round"
		echo "void). A reviewer that breaks the checkout must not pass as a clean tree."
	} >&2
	exit 3
fi
if [[ ${BEFORE} != "${AFTER}" ]]; then
	echo "GATE FAILED — the reviewer MUTATED the working tree during the review:" >&2
	# The first line of the fingerprint is the pre-run HEAD; `$'\n'`, not `\n` — inside a pattern `\n`
	# is a literal `n` (measured: it stripped at the first `n` of the status text).
	tree_fingerprint_report "${REPO}" "${BEFORE_STATUS}" "${BEFORE%%$'\n'*}"
	echo "(round is void — see COREDEV-2607)" >&2
	exit 3
fi

# THE ROUND'S BASIS MUST SURVIVE THE ROUND (PR #63 recheck, P1). A reviewer that rewrote the staged
# plan and then emitted `VERDICT: APPROVE` produced a valid-looking capture of a review of DIFFERENT
# bytes, while synthesis validates only the `.plan` record against the live plan — which nobody
# touched. And the status diff below could not even SEE it: `git status --porcelain` is STATUS-line
# based, and the staged plan is already `M` in the baseline, so re-modifying its content changes
# nothing the diff compares. Reproduced both ways. So the basis files are verified by CONTENT against
# the digests recorded before launch — the same digest the `.plan` record attests to, now checked at a
# third point in the round's life.
if [[ -n ${PLAN_REL} ]]; then
	ACTUAL_PLAN_SHA="$(_sha256 "${TREE}/${PLAN_REL}" 2>/dev/null)" || ACTUAL_PLAN_SHA="unreadable"
	if [[ ${ACTUAL_PLAN_SHA} != "${EXPECTED_PLAN_SHA}" ]]; then
		{
			echo "GATE FAILED — the STAGED PLAN was modified during the review (round void):"
			echo "(staged ${EXPECTED_PLAN_SHA}, post-run ${ACTUAL_PLAN_SHA} — the transcript reviewed"
			echo "bytes the binding does not attest to; see COREDEV-2607 for why this voids the round)"
		} >&2
		exit 3
	fi
fi
ACTUAL_PROMPT_SHA="$(_sha256 "${TREE}/${PROMPT_REL}" 2>/dev/null)" || ACTUAL_PROMPT_SHA="unreadable"
if [[ ${ACTUAL_PROMPT_SHA} != "${PROMPT_TREE_SHA}" ]]; then
	echo "GATE FAILED — the assembled PROMPT was modified during the review (round void)" >&2
	exit 3
fi
# ANY other write inside the disposable copy voids the round too — no longer a note. Writing files is
# the COREDEV-2607 signature (a reviewer in agent mode, implementing instead of reviewing), and a
# review produced that way is untrustworthy whether or not the copy is discarded afterwards. The
# earlier informational form existed because comparing against HEAD reported the HARNESS'S OWN staged
# input as a reviewer write — a detector that cries wolf on its own inputs is one nobody reads. That
# concern is solved by the POST-STAGING BASELINE, not by softening the verdict: everything the harness
# placed is in the baseline, so anything beyond it is the reviewer's doing, and it fails the round.
# (The old form also excluded the prompt's basename from the diff — which would have HIDDEN a reviewer
# tampering with any file sharing that name. The content checks above cover the prompt now.)
# A FAILED STATUS IS NOT A CLEAN TREE (PR #63 recheck, P2). `|| true` turned a `git status` failure
# into an EMPTY string, and comparing empty against the non-empty baseline yields an empty `DIRTY` —
# so a shell-capable reviewer that removed or corrupted the checkout's `.git` file broke the very
# detector meant to catch it and the round returned 0 with `VERDICT: APPROVE`. The basis files can be
# byte-identical throughout, so nothing else notices. Any non-zero status here VOIDS the round.
if ! TREE_AFTER="$(disposable_fingerprint "${TREE}")"; then
	{
		echo "GATE FAILED — could not re-read the disposable checkout after the review (round"
		echo "void). A reviewer that breaks the checkout must not pass as a clean tree."
	} >&2
	exit 3
fi
if [[ ${TREE_BASELINE} != "${TREE_AFTER}" ]]; then
	{
		echo "GATE FAILED — the reviewer left edits inside the disposable checkout (round void — agent-mode"
		echo "behaviour, the COREDEV-2607 signature):"
		printf '%s\n' "${TREE_BASELINE}" | diff - <(printf '%s\n' "${TREE_AFTER}") | sed 's/^/  /' || :
	} >&2
	exit 3
fi

# A REFUSED RUN IS EXPLAINED HERE, outside the PTY. The adapter writes its refusal only to `${OUT}.diag`,
# leaving the transcript EMPTY (MISSING downstream, codex plan round 3), so the operator reads the reason from
# this script's stderr instead.
if [[ ${RC} -ne 0 ]]; then
	REFUSAL="$(grep -a '^GEMINI ARM FAILED' "${OUT}.diag" 2>/dev/null | tail -1)"
	printf 'gemini arm (%s): %s\n' "${MODEL}" "${REFUSAL:-the review ended (exit ${RC}) without an adapter refusal — timed out or killed; see ${OUT}.diag}" >&2
fi
BYTES_OUT="$(wc -c 2>/dev/null <"${OUT}" | tr -d ' ')"
# Anchored, never a loose `grep VERDICT:` — that matches the prompt's own echoed template in a
# timed-out transcript and reads as a real verdict.
VERDICT="$(grep -aE '^VERDICT: (APPROVE|APPROVE_WITH_NOTES|REQUEST_CHANGES)[[:space:]]*$' "${OUT}" 2>/dev/null | tail -1)"
echo "EXIT=${RC} BYTES=${BYTES_OUT:-0} TREE=clean MODEL=${MODEL} VERDICT=${VERDICT:-<none — FAILED REVIEW>}"
# RETURN IT. The status was captured in `RC` and then thrown away by the successful `echo` above, so a
# stub exiting 23 printed `EXIT=23 … FAILED REVIEW` while this script — and `capture-gemini-review.sh`
# with it — reported success. The caller then could not tell a completed review from an auth, model or
# timeout failure, which is exactly the distinction the gate depends on (PR #63 recheck, P2). The
# mutation detector above keeps its own separate exit path; this only propagates the CAPTURE status.
exit "${RC}"
