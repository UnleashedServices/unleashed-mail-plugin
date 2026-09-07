#!/usr/bin/env bash
# The instrumented launcher for `trunk-parity-harness.yml` — RECORD, then DELEGATE.
#
# WHY IT DELEGATES RATHER THAN EXITING ZERO (cell 5).
# Cell 1 only needs the argv the pinned action passes to Trunk, so a launcher that records and exits 0
# would satisfy it. For cell 5 that is NO STIMULUS AT ALL: the claim is "the job introduces no
# tracked-source mutation", and a fixture is trivially unchanged when nothing ran — the harness would
# report green whether or not real Trunk would have rewritten it. A sensor that cannot register the
# thing it watches for is the sink problem wearing a different hat. So this records and then runs the
# REAL Trunk, and cell 5 carries a positive control: enabling autofix must change the fixture.
#
# THIS IS THE ONE LEGITIMATE USE OF `trunk-path`. §1's C4 forbids that input in the shipped workflows
# precisely because it names the executed launcher; here the point IS to name it, and this harness is
# non-required and emits no gating context.
#
# Environment (the harness is not governed by C5 — the shipped workflows are):
#   PARITY_ARGV_FILE    append one JSON array per invocation
#   PARITY_REAL_TRUNK   the genuine Trunk binary to delegate to
#   PARITY_PRIMARY_LOG  where to tee the `check` invocation's own output
#
# WHY THE `check` INVOCATION IS TEE'D RATHER THAN exec'd.
# `action.outcome` alone cannot distinguish "Trunk evaluated the fixture and found it mis-indented"
# from "Trunk reached its `check` argv and then aborted — a linter download, a cache fetch — while the
# `if: always()` autofix control still succeeded and changed the fixture". Both worlds write
# `failure`, so the judge accepted a record whose primary never linted anything. Capturing the
# primary's own output lets the assembler bind the outcome to a NAMED diagnostic on the fixture, which
# only the first world can produce. `version` still `exec`s: it emits no diagnostic and needs none.
#
# `setup/locate_trunk.sh` invokes the launcher once as `<launcher> version` before the check, so every
# invocation is recorded, not just the linting one — the judge selects the `check` invocation by its
# argv rather than assuming there is exactly one.

set -euo pipefail

argv_file="${PARITY_ARGV_FILE:?PARITY_ARGV_FILE must name a file}"
real_trunk="${PARITY_REAL_TRUNK:?PARITY_REAL_TRUNK must name the genuine Trunk binary}"
# Unconditional, so a step that forgets to set it fails loudly here rather than silently recording a
# record with no diagnostic. Each invoking step gets its OWN log; they must not share one.
primary_log="${PARITY_PRIMARY_LOG:?PARITY_PRIMARY_LOG must name a file}"

# One JSON array per line. Encoded with python3 so an argument containing a quote, a backslash or a
# space round-trips exactly — the comparison downstream is BYTE-FOR-BYTE, and a hand-rolled quoting
# scheme here would silently normalise the very bytes under test.
python3 -c '
import json, sys
with open(sys.argv[1], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[2:]) + "\n")
' "${argv_file}" "$@"

# `set -e` would abort before PIPESTATUS could be read, and `pipefail` would hand back tee's status
# for a failing Trunk, so the guard is deliberate: the exit code MUST be Trunk's own, or the recorded
# `action.outcome` stops describing Trunk.
if [[ ${1:-} == "check" ]]; then
	set +e
	"${real_trunk}" "$@" 2>&1 | tee -- "${primary_log}"
	trunk_status="${PIPESTATUS[0]}"
	set -e
	exit "${trunk_status}"
fi

exec "${real_trunk}" "$@"
