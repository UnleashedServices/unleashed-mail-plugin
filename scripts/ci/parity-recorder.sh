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
#   PARITY_ARGV_FILE   append one JSON array per invocation
#   PARITY_REAL_TRUNK  the genuine Trunk binary to delegate to
#
# `setup/locate_trunk.sh` invokes the launcher once as `<launcher> version` before the check, so every
# invocation is recorded, not just the linting one — the judge selects the `check` invocation by its
# argv rather than assuming there is exactly one.

set -euo pipefail

argv_file="${PARITY_ARGV_FILE:?PARITY_ARGV_FILE must name a file}"
real_trunk="${PARITY_REAL_TRUNK:?PARITY_REAL_TRUNK must name the genuine Trunk binary}"

# One JSON array per line. Encoded with python3 so an argument containing a quote, a backslash or a
# space round-trips exactly — the comparison downstream is BYTE-FOR-BYTE, and a hand-rolled quoting
# scheme here would silently normalise the very bytes under test.
python3 -c '
import json, sys
with open(sys.argv[1], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[2:]) + "\n")
' "${argv_file}" "$@"

exec "${real_trunk}" "$@"
