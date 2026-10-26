#!/usr/bin/env python3
"""Regenerate `scripts/review/callers-scan-exemptions.tsv` — a MAINTAINER tool, never production.

`callers_scan.py` states that the residual manifest is maintained outside it and that production never
derives or widens it automatically, because a scanner that can write its own exemptions cannot fail
closed: every new REJECT would exempt itself. That rule is why this is a separate file that
`callers_scan` does not import and does not know about (`test_callers_scan` asserts the non-import).

It is deliberately a thin shell over the production predicates rather than a second implementation of
them: the manifest must be the EXACT complement of what production selects, so re-deriving `is_candidate`
here would create a second thing to keep in sync — which is the defect that has bitten the duplicated
frozen digests in this same module more than once.

Run it LAST, after every other edit in a change is final. The record identity is
`(path, FINAL line number, SHA-256(payload))` and is deliberately NOT shift-stable: inserting a single
line above a residual candidate invalidates its record, which is the property that makes an exemption
bind to one reviewed line rather than to a moving target.

    python3 scripts/review/generate-callers-exemptions.py            # write the manifest
    python3 scripts/review/generate-callers-exemptions.py --check    # exit 1 if it would change

`--check` is for CI: it never writes, so a pipeline cannot regenerate its way to green.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PRODUCTION = REPO / "scripts" / "review" / "callers_scan.py"


def _load_production():
    spec = importlib.util.spec_from_file_location("_callers_scan_for_generation", PRODUCTION)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {PRODUCTION}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_manifest(module, files) -> bytes:
    """The byte-sorted complement: every candidate that is NOT an exact production."""
    records = sorted(
        module.Exemption(
            path,
            line_number,
            module.hashlib.sha256(payload).hexdigest(),
        ).serialize()
        for path in files
        for line_number, payload in enumerate(module.physical_lines(files[path]), start=1)
        if module.is_candidate(path, payload) and not module.is_exact_production(payload)
    )
    return b"" if not records else b"\n".join(records) + b"\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the manifest on disk differs; never write",
    )
    arguments = parser.parse_args(argv)

    module = _load_production()
    root = arguments.root.resolve()
    files = module.read_tracked_files(root)
    manifest = build_manifest(module, files)

    # Parse what we are about to write with the PRODUCTION parser: canonical records, byte-sorted,
    # unique, LF-terminated. A generator that emits something production would reject is worse than
    # no generator, because the failure surfaces at gate time rather than here.
    module.parse_exemption_manifest(manifest)

    destination = root / module.EXEMPTION_PATH
    current = destination.read_bytes() if destination.is_file() else None
    if arguments.check:
        if current == manifest:
            print(f"callers-scan-exemptions: up to date ({manifest.count(chr(10).encode())} records)")
            return 0
        print(
            "callers-scan-exemptions: OUT OF DATE — regenerate with "
            "`python3 scripts/review/generate-callers-exemptions.py`",
            file=sys.stderr,
        )
        return 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(manifest)
    print(f"callers-scan-exemptions: wrote {len(manifest.splitlines())} records to {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
