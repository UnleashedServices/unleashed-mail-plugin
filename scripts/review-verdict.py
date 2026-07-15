#!/usr/bin/env python3
"""Persisted, plan-digest-bound Combined-verdict artifact for the Plan Review Gate.

The gate (`/gemini-review` + `/codex-review` -> `/review-synthesis`) produces a Combined verdict.
This tool PERSISTS that verdict as a structured artifact bound to the exact bytes of the plan it
approved, so `implement`'s Phase-1 gate can VERIFY deterministically — not by re-reading prose —
that:
  (a) a Combined verdict artifact exists for this plan,
  (b) it is an APPROVING verdict (APPROVE / APPROVE_WITH_NOTES), and
  (c) the plan has NOT changed since approval (raw-byte digest match -> prevents approve-then-edit).

Usage:
  write  --plan PATH --verdict V --reviewer name=STATUS[:TRANSCRIPT] [--reviewer ...] [--round N]
  verify --plan PATH

`verify` exits 0 iff a valid, approving, digest-matching artifact exists; non-zero otherwise
(fail closed) with a one-line reason on stderr. The artifact is stored in a private `.verdicts/`
dir beside the plan (0700, no-symlink, atomic write, 0600 file) and is git-ignored session state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

SCHEMA_VERSION = 1
APPROVING = {"APPROVE", "APPROVE_WITH_NOTES"}
# The full set of Combined-verdict values /review-synthesis can emit (for validation).
VERDICTS = APPROVING | {"REQUEST_CHANGES", "DISAGREEMENT", "MISSING"}  # MISSING = reviewer did not return (non-approving only)
# The mandatory dual-review pair (CLAUDE.md Plan Review Gate). An APPROVING artifact must record
# BOTH, distinct, each approving — a reviewer can never stand in for the other, and the caller's
# combined `verdict` can never override a reviewer that actually rejected. (A future user-authorized
# waiver — AGENT_CONTRACTS §2 — would extend this with a recorded WAIVED marker, not weaken it.)
REQUIRED_REVIEWERS = {"gemini", "codex"}


def _quorum_problem(verdict, reviewers) -> "str | None":
    """Reason string if an APPROVING verdict is NOT backed by a genuine dual approval (both required
    reviewers present, DISTINCT, each approving); else None. Non-approving verdicts record whatever
    ran and are never gate-passing, so they skip this. Enforced at BOTH write and verify so neither a
    mis-recording caller nor a hand-tampered artifact can manufacture a false approval."""
    if verdict not in APPROVING:
        return None
    if not isinstance(reviewers, list):
        return "artifact reviewers is not a list"
    names = [str(r.get("name", "")).strip().lower() for r in reviewers if isinstance(r, dict)]
    if len(names) != len(reviewers):
        return "malformed reviewer entries"
    if len(set(names)) < len(names):
        return "duplicate reviewer names — one reviewer cannot stand in for the other"
    missing = REQUIRED_REVIEWERS - set(names)
    if missing:
        return f"missing required reviewer(s) {sorted(missing)} — the mandatory gate is gemini + codex"
    bad = [f"{r.get('name')}={r.get('status')}" for r in reviewers
           if str(r.get("status", "")).strip().upper() not in APPROVING]
    if bad:
        return "an APPROVING combined verdict requires EVERY reviewer to approve; got " + ", ".join(bad)
    # An APPROVING artifact must EVIDENCE each approval. Without this, `--reviewer gemini=APPROVE`
    # with no `:TRANSCRIPT` at all produced a GATE OK — the caller's bare assertion, with nothing
    # recorded that anyone could later audit. Non-approving verdicts deliberately skip this: a
    # MISSING/failed reviewer legitimately HAS no transcript, and that record is the point.
    #
    # HONEST BOUND: this does NOT stop a determined caller (`printf x > f.txt` yields a non-empty
    # digest and passes). It raises the floor against an accidental one and completes the audit
    # trail. Content validation would be the real control — see COREDEV-2497.
    missing_t = [str(r.get("name")) for r in reviewers
                 if not str(r.get("transcriptSha256", "")).strip()]
    if missing_t:
        return ("an APPROVING combined verdict requires a transcript per reviewer; missing for "
                + ", ".join(sorted(missing_t)))
    return None


def _sha256_bytes(path: str) -> str:
    """Raw-byte SHA-256 of a file (never text-normalized — a whitespace edit must change it)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _verdict_path(plan_path: str) -> str:
    """`<plan-dir>/.verdicts/<plan-basename>.verdict.json` — co-located with the plan it binds."""
    plan_path = os.path.abspath(plan_path)
    return os.path.join(os.path.dirname(plan_path), ".verdicts",
                        os.path.basename(plan_path) + ".verdict.json")


def _ensure_secure_dir(d: str) -> None:
    """Create `d` as a private 0700 dir, refusing a symlink or a non-dir occupant (no-symlink /
    regular-target checks — session-scoping alone doesn't stop a pre-planted symlink)."""
    if os.path.islink(d):
        raise SystemExit(f"review-verdict: refusing symlinked verdict dir: {d}")
    if os.path.exists(d):
        if not os.path.isdir(d):
            raise SystemExit(f"review-verdict: verdict path exists and is not a directory: {d}")
    else:
        os.makedirs(d, mode=0o700, exist_ok=True)
    os.chmod(d, 0o700)
    # Make the dir self-ignoring so the "per-session, never committed" guarantee holds in ANY consumer
    # repo — the plugin's own .gitignore does not apply where the plugin is loaded from the cache (e.g.
    # the app repo's docs/planning/.verdicts/), where a routine `git add docs/` would otherwise commit an
    # approving artifact and satisfy `implement`'s verify in every clone (PR #39 review).
    gi = os.path.join(d, ".gitignore")
    if not os.path.exists(gi):
        try:
            with open(gi, "w", encoding="utf-8") as fh:
                fh.write("*\n")
        except OSError:
            pass


def _parse_reviewer(spec: str) -> dict:
    """`name=STATUS[:TRANSCRIPT_PATH]` -> {name, status, transcriptSha256?}."""
    if "=" not in spec:
        raise SystemExit(f"review-verdict: --reviewer must be name=STATUS[:TRANSCRIPT], got {spec!r}")
    name, rest = spec.split("=", 1)
    status, _, transcript = rest.partition(":")
    name, status = name.strip(), status.strip().upper()
    if not name or status not in VERDICTS:
        raise SystemExit(f"review-verdict: reviewer {name!r} has invalid status {status!r}")
    out = {"name": name, "status": status}
    if transcript:
        if not os.path.isfile(transcript):
            raise SystemExit(f"review-verdict: reviewer {name!r} transcript not found: {transcript}")
        if os.path.getsize(transcript) == 0:
            # An EMPTY transcript is a FAILED review, never a review. Only `isfile` was checked, so a
            # 0-byte file recorded transcriptSha256 = e3b0c442…855 (the empty-string digest) and
            # sailed through — the exact "a missing/empty transcript is never APPROVE" rule this
            # artifact exists to record. `agy` writes precisely 0 bytes from a non-TTY on failure.
            raise SystemExit(f"review-verdict: reviewer {name!r} transcript is EMPTY: {transcript}")
        out["transcriptSha256"] = _sha256_bytes(transcript)
    return out


def cmd_write(args: argparse.Namespace) -> int:
    plan = args.plan
    if not os.path.isfile(plan):
        raise SystemExit(f"review-verdict: plan not found: {plan}")
    verdict = args.verdict.strip().upper()
    if verdict not in VERDICTS:
        raise SystemExit(f"review-verdict: --verdict must be one of {sorted(VERDICTS)}, got {verdict!r}")
    reviewers = [_parse_reviewer(s) for s in (args.reviewer or [])]
    if len(reviewers) < 2:
        # The gate is a DUAL review — a single reviewer can never carry an approval artifact.
        raise SystemExit("review-verdict: at least two reviewers (gemini + codex) are required")
    problem = _quorum_problem(verdict, reviewers)
    if problem:
        raise SystemExit("review-verdict: refusing to write an approving artifact — " + problem)
    artifact = {
        "schemaVersion": SCHEMA_VERSION,
        "planPath": os.path.relpath(os.path.abspath(plan)),
        "planSha256": _sha256_bytes(plan),
        "verdict": verdict,
        "reviewers": reviewers,
        "round": args.round,
        "createdAt": args.created_at or "",   # caller passes an ISO stamp; scripts can't read the clock
    }
    dest = _verdict_path(plan)
    _ensure_secure_dir(os.path.dirname(dest))
    if os.path.islink(dest):
        raise SystemExit(f"review-verdict: refusing to overwrite a symlinked artifact: {dest}")
    tmp = f"{dest}.tmp.{os.getpid()}"
    old_umask = os.umask(0o077)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(artifact, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, dest)
    finally:
        os.umask(old_umask)
        try:
            os.remove(tmp)
        except OSError:
            pass
    print(f"review-verdict: wrote {verdict} artifact bound to {plan} ({artifact['planSha256'][:12]}…)")
    return 0


def _fail(reason: str) -> int:
    sys.stderr.write(f"review-verdict: GATE FAILED — {reason}\n")
    return 1


def cmd_verify(args: argparse.Namespace) -> int:
    plan = args.plan
    if not os.path.isfile(plan):
        return _fail(f"plan not found: {plan}")
    dest = _verdict_path(plan)
    # Refuse a symlinked .verdicts dir too (write already does) — otherwise `dest` could resolve to a
    # regular file OUTSIDE the plan directory through the link and satisfy the gate (PR #39 review).
    if os.path.islink(os.path.dirname(dest)):
        return _fail(f"refusing symlinked verdict dir: {os.path.dirname(dest)}")
    if os.path.islink(dest) or not os.path.isfile(dest):
        return _fail(f"no Combined-verdict artifact for this plan (run the gate first): {dest}")
    try:
        with open(dest, encoding="utf-8") as fh:
            art = json.load(fh)
    except (OSError, ValueError) as e:
        return _fail(f"artifact unreadable/corrupt: {e}")
    if not isinstance(art, dict) or art.get("schemaVersion") != SCHEMA_VERSION:
        return _fail(f"artifact schemaVersion != {SCHEMA_VERSION} (stale format — re-run the gate)")
    if art.get("verdict") not in APPROVING:
        return _fail(f"verdict is {art.get('verdict')!r}, not an approving verdict — gate not passed")
    reviewers = art.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) < 2:
        return _fail("artifact does not record the required dual review")
    # A genuine dual approval — both required reviewers, distinct, each approving. Catches a
    # hand-tampered artifact (e.g. verdict flipped to APPROVE while the reviewer statuses still
    # say REQUEST_CHANGES, or one reviewer duplicated so the other never ran).
    problem = _quorum_problem(art.get("verdict"), reviewers)
    if problem:
        return _fail("approval not backed by a genuine dual review — " + problem)
    # The artifact must have been written FOR this plan — a copied/renamed artifact whose bytes happen
    # to match a different plan must not satisfy the gate (PR #39 review). Compare basenames (relpath is
    # CWD-dependent; the artifact is co-located with its plan, so the basename is the stable binding).
    if os.path.basename(str(art.get("planPath", ""))) != os.path.basename(plan):
        return _fail(f"artifact was written for a different plan ({art.get('planPath')!r}), not {plan}")
    current = _sha256_bytes(plan)
    if current != art.get("planSha256"):
        return _fail("plan has CHANGED since approval (digest mismatch) — re-run the gate on the "
                     "current plan (approve-then-edit is blocked)")
    who = ", ".join(f"{r.get('name')}={r.get('status')}" for r in reviewers)
    print(f"review-verdict: GATE OK — {art['verdict']} on {plan} [{who}]")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Plan Review Gate — persisted Combined-verdict artifact.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write", help="persist a Combined-verdict artifact bound to a plan")
    w.add_argument("--plan", required=True)
    w.add_argument("--verdict", required=True)
    w.add_argument("--reviewer", action="append", help="name=STATUS[:TRANSCRIPT] (repeatable; >=2)")
    w.add_argument("--round", type=int, default=None)
    w.add_argument("--created-at", default=None, help="ISO-8601 timestamp (caller supplies the clock)")
    w.set_defaults(func=cmd_write)
    v = sub.add_parser("verify", help="fail closed unless an approving, digest-matching artifact exists")
    v.add_argument("--plan", required=True)
    v.set_defaults(func=cmd_verify)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
