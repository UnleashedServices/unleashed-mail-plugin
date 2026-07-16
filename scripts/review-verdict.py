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
import re
import sys

SCHEMA_VERSION = 2
APPROVING = {"APPROVE", "APPROVE_WITH_NOTES"}
# SHA-256 of zero bytes. `agy` writes EXACTLY 0 bytes from a non-TTY when a review fails, so this digest
# is the signature of a FAILED review, never a review. The parse-time size check only guards the WRITE
# path — an artifact written before that check existed, or hand-edited after a zero-byte capture, still
# carried this value and passed verify (codex, #41 review). Rejecting the constant closes both paths.
_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_SHA256_HEX = re.compile(r"\A[0-9a-f]{64}\Z")
# The full set of Combined-verdict values /review-synthesis can emit (for validation).
# A single REVIEWER's status is a DIFFERENT vocabulary from a COMBINED verdict: MISSING is a reviewer
# status (it never returned), DISAGREEMENT is a combined outcome (the two reviewers differed). Neither
# crosses over. Conflating them (the old single `VERDICTS` set) let `--verdict MISSING` and
# `--reviewer x=DISAGREEMENT` through — a reviewer cannot "disagree" and a combined verdict is never
# MISSING (full review, #42).
REVIEWER_STATUSES = APPROVING | {"REQUEST_CHANGES", "MISSING"}
# The top-level `verdict` is a COMBINED verdict, a DIFFERENT vocabulary from a reviewer's status:
# DISAGREEMENT is a combined outcome, MISSING is a reviewer status, and neither crosses over. Kept
# distinct so a stale/tampered `verdict` (a list, a dict, a bare reviewer status) is named as corrupt
# rather than crashing or being silently misclassified (codex, #42 review).
COMBINED_VERDICTS = APPROVING | {"REQUEST_CHANGES", "DISAGREEMENT"}
# ONE phrasing for what MISSING means, shared by every branch that reports it. `review-synthesis`
# normalizes BOTH "reviewer never returned" AND "empty / unparseable transcript" to MISSING (its table,
# SKILL.md:48), so no branch may assert "never ran" as fact. A CONSTANT because the two branches that
# say it DID diverge: I fixed the wording in the single-reviewer branch and left the mixed branch
# claiming "never ran" for a whole round, because I fixed the site I was looking at (codex, #42 review).
_MISSING_MEANS = "no usable verdict — the reviewer never ran, OR its transcript was empty/unparseable"
  # MISSING = reviewer did not return (non-approving only)
# The mandatory dual-review pair (CLAUDE.md Plan Review Gate). An APPROVING artifact must record
# BOTH, distinct, each approving — a reviewer can never stand in for the other, and the caller's
# combined `verdict` can never override a reviewer that actually rejected.
#
# There is NO waiver status, by decision (COREDEV-2493): "only the user may waive" is unenforceable
# here — the agent is the process running this script, so any waiver flag it could be asked to supply,
# it can supply unprompted. An unavailable reviewer is handled OUT of band by the user (see
# "Preflight & unavailable-reviewer recovery" in AGENT_CONTRACTS §2), and such an exception is recorded
# in the plan's progress log WITHOUT an approving artifact — never as a gate-passing verdict here.
REQUIRED_REVIEWERS = {"gemini", "codex"}


def _quorum_problem(verdict, reviewers) -> str | None:
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
    # `isinstance(..., str)`, NOT `.get(k, "")`: the default applies only when the key is ABSENT, so an
    # explicit `"transcriptSha256": null` returned None and `str(None)` -> "None", which is truthy and
    # sailed straight through. A hand-tampered artifact is exactly the threat this check exists for, so
    # the one shape an attacker would hand-write must not be the one that passes. (gemini, #41 review.)
    missing_t = [str(r.get("name")) for r in reviewers
                 if not (isinstance(r.get("transcriptSha256"), str)
                         and r["transcriptSha256"].strip())]
    if missing_t:
        return ("an APPROVING combined verdict requires a transcript per reviewer; missing for "
                + ", ".join(sorted(missing_t)))
    empty_t = [str(r.get("name")) for r in reviewers
               if str(r.get("transcriptSha256", "")).strip().lower() == _EMPTY_SHA256]
    if empty_t:
        return ("an APPROVING combined verdict requires a NON-EMPTY transcript; the empty-file digest "
                "was recorded for " + ", ".join(sorted(empty_t)) + " (a 0-byte capture is a FAILED "
                "review — `agy` writes exactly 0 bytes from a non-TTY on failure)")
    # DISTINCT EVIDENCE, not just distinct names. The duplicate-name check above says "one reviewer
    # cannot stand in for the other" — but it only inspects the LABEL. Recording the same transcript for
    # both (`gemini=APPROVE:/tmp/agy-out.txt` + `codex=APPROVE:/tmp/agy-out.txt`, one copy-paste slip in
    # the documented two-file flow) produced a GATE OK in which ONE review backed BOTH approvals
    # (codex, #41 review — reproduced). Every prior check passed because they all compare labels.
    #
    # AFTER the empty check ON PURPOSE: two 0-byte transcripts are identical AND empty, and "your
    # transcript is empty" is the actionable diagnosis (0 bytes is agy's failure signature) —
    # "duplicate" would misdirect. Specific beats general.
    # A digest must LOOK like one. Non-empty + distinct + not-the-empty-hash still admitted
    # `transcriptSha256: "x"` / `"y"` — two distinct non-empty strings — and produced GATE OK on a
    # hand-edited artifact (codex, #41 review — reproduced). Hand-tampering is this check's stated threat
    # model, so "any non-empty string is evidence" was never good enough. sha256 hex is exactly 64
    # lowercase hex chars; anything else was never produced by `_sha256_bytes`.
    _malformed_t = sorted(_n for _n, _d in
                          ((str(r.get("name")), str(r.get("transcriptSha256", "")).strip().lower())
                           for r in reviewers if isinstance(r, dict))
                          if not _SHA256_HEX.match(_d))
    if _malformed_t:
        return ("an APPROVING combined verdict requires a real SHA-256 transcript digest (64 hex chars); "
                "malformed for " + ", ".join(_malformed_t))
    _dicts = [r for r in reviewers if isinstance(r, dict)]
    # A present-but-non-STRING provenance field is tamper garbage. Guard it for TWO reasons: (a) a list
    # or dict is unhashable, so `set(...)` below would CRASH with TypeError instead of failing closed —
    # the exact non-hashable class already fixed for the top-level verdict (gemini, #41 review); and (b)
    # silently dropping a non-string value would let a tamperer set one reviewer's path/id to `[]` to
    # make it "absent" and slip past the distinctness checks. So: only STRINGS participate, and a
    # present non-string field is CORRUPT.
    def _provenance(field):
        vals, malformed = [], False
        for r in _dicts:
            if field in r:
                v = r[field]
                if isinstance(v, str) and v:
                    vals.append(v)
                elif v:                       # present, truthy, and not a usable string -> tampered
                    malformed = True
        return vals, malformed

    # 1. Distinct capture PATHS. The same transcript FILE recorded for two reviewers is the real
    #    accidental mistake (one copy-paste in the documented two-file flow), and it is provenance, not
    #    content: catch it by path so two genuinely-separate reviews with identical bytes are NOT
    #    falsely rejected (full review, #41). Check duplicates among the paths that ARE present — NOT
    #    gated on every reviewer having one (the earlier `== len(_dicts)` guard was all-or-nothing: a
    #    tampered artifact with one path-less entry skipped the check even with duplicates among the
    #    rest — gemini, #41 review). A legit approving artifact has a distinct path per reviewer.
    _paths, _paths_bad = _provenance("transcriptPath")
    if _paths_bad:
        return "an APPROVING combined verdict has a non-string transcriptPath — corrupt/tampered artifact"
    if len(set(_paths)) < len(_paths):
        return ("an APPROVING combined verdict requires a DISTINCT transcript per reviewer — the same "
                "transcript FILE is recorded for more than one reviewer, i.e. one review standing in for two")
    # 2. Distinct capture IDs. A capture ID is a per-run token, so a repeat = one wrapper run claimed
    #    twice — caught among the IDs that ARE present, same anti-all-or-nothing reasoning as paths.
    _cids, _cids_bad = _provenance("captureId")
    if _cids_bad:
        return "an APPROVING combined verdict has a non-string captureId — corrupt/tampered artifact"
    if len(set(_cids)) < len(_cids):
        return ("an APPROVING combined verdict requires a DISTINCT capture per reviewer — the same "
                "capture ID is recorded for more than one reviewer")
    # 3. Capture IDs are AUTHORITATIVE only when EVERY reviewer has a distinct one: then two byte-identical
    #    transcripts from distinct runs are legitimately two reviews, so skip the content-based floor.
    #    Requiring all-present HERE is correct (unlike the duplicate checks) — a partial set cannot vouch
    #    for the reviewer that has none, so it must not license bypassing the digest floor.
    if _cids and len(_cids) == len(_dicts) and len(set(_cids)) == len(_dicts):
        return None
    # 3. Fallback (no capture IDs): distinct DIGESTS. Has a benign false-negative — two byte-identical
    #    separate reviews are rejected — but that is astronomically rare, and pty-capture's capture IDs
    #    (path 2) lift it whenever present.
    _digests = [str(r.get("transcriptSha256", "")).strip().lower() for r in _dicts]
    if len(set(_digests)) < len(_digests):
        return ("an APPROVING combined verdict requires a DISTINCT transcript per reviewer — the same "
                "transcript content is recorded for more than one reviewer, i.e. one review standing in for two")
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
    """`name=STATUS[:TRANSCRIPT_PATH]` -> {name, status, transcriptSha256?, transcriptPath?, captureId?}."""
    if "=" not in spec:
        raise SystemExit(f"review-verdict: --reviewer must be name=STATUS[:TRANSCRIPT], got {spec!r}")
    name, rest = spec.split("=", 1)
    status, _, transcript = rest.partition(":")
    name, status = name.strip(), status.strip().upper()
    if not name or status not in REVIEWER_STATUSES:
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
        # PROVENANCE beyond content-inequality (full review, #41). Record the canonical capture PATH,
        # and a wrapper-produced capture ID when `pty-capture.py` left one beside the transcript
        # (`<transcript>.captureid`). Content-inequality alone cannot tell two genuinely-separate
        # reviews that happen to be byte-identical from one file reused for both; a distinct path (the
        # common accidental case) and a distinct capture ID (a per-run token) can. Both optional and
        # auto-discovered — no caller/skill change needed; absent -> the digest floor still applies.
        out["transcriptPath"] = os.path.realpath(transcript)
        _cid = transcript + ".captureid"
        if os.path.isfile(_cid) and os.path.getsize(_cid) > 0:
            with open(_cid, encoding="utf-8") as _fh:
                _v = _fh.read().strip()
            if _v:
                out["captureId"] = _v
    return out


def _reviewer_identity_problem(reviewers: list[dict]) -> str | None:
    """Reason string if the reviewer SET is malformed regardless of verdict: a duplicate name, a stray
    reviewer, or a missing mandatory reviewer. Enforced at WRITE so an artifact verify would call corrupt
    can never be created in the first place (full review, #42 — write/verify symmetry). Statuses/names
    are already validated by `_parse_reviewer`; this is about identity."""
    names = [str(r.get("name", "")).strip().lower() for r in reviewers]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        return f"duplicate reviewer(s) {dupes} — one reviewer cannot be recorded twice"
    strays = sorted(set(names) - REQUIRED_REVIEWERS)
    if strays:
        return (f"reviewer(s) {strays} are not part of the gate "
                f"({', '.join(sorted(REQUIRED_REVIEWERS))})")
    missing = sorted(REQUIRED_REVIEWERS - set(names))
    if missing:
        return f"missing mandatory reviewer(s) {missing} — the gate is {', '.join(sorted(REQUIRED_REVIEWERS))}"
    return None


def cmd_write(args: argparse.Namespace) -> int:
    plan = args.plan
    if not os.path.isfile(plan):
        raise SystemExit(f"review-verdict: plan not found: {plan}")
    verdict = args.verdict.strip().upper()
    if verdict not in COMBINED_VERDICTS:
        raise SystemExit(f"review-verdict: --verdict must be one of {sorted(COMBINED_VERDICTS)}, "
                         f"got {verdict!r} (that vocabulary is combined verdicts; MISSING is a reviewer "
                         "status, not a combined verdict)")
    # DIGEST-BEFORE-DISPATCH (#44 review §4). The plan digest is computed HERE, at write, which is AFTER
    # the reviewers ran — so a plan edited between review and write would bind approval to bytes the
    # reviewers never saw ("review v1, edit to v2, write approves v2"). When the caller snapshots the
    # plan's digest BEFORE dispatching the reviews and passes it as --reviewed-sha256, refuse to write
    # unless the plan is STILL those exact bytes. `verify` already re-checks the digest after write; this
    # closes the review->write window in front of it.
    if getattr(args, "reviewed_sha256", None):
        expected = args.reviewed_sha256.strip().lower()
        if not _SHA256_HEX.match(expected):
            raise SystemExit(f"review-verdict: --reviewed-sha256 must be 64 hex chars, got {expected!r}")
        actual = _sha256_bytes(plan)
        if actual != expected:
            raise SystemExit(
                "review-verdict: the plan CHANGED between review and write — refusing to record an "
                f"approval bound to bytes the reviewers never saw (reviewed {expected[:12]}…, now "
                f"{actual[:12]}…). Re-run the reviews on the current plan.")
    reviewers = [_parse_reviewer(s) for s in (args.reviewer or [])]
    if len(reviewers) < 2:
        # The gate is a DUAL review — a single reviewer can never carry an approval artifact.
        raise SystemExit("review-verdict: at least two reviewers (gemini + codex) are required")
    id_problem = _reviewer_identity_problem(reviewers)
    if id_problem:
        raise SystemExit("review-verdict: refusing to write a malformed artifact — " + id_problem)
    problem = _quorum_problem(verdict, reviewers)
    if problem:
        raise SystemExit("review-verdict: refusing to write an approving artifact — " + problem)
    artifact = {
        "schemaVersion": SCHEMA_VERSION,
        # REALPATH, not a CWD-relative relpath: the binding must distinguish two plans that share a
        # basename in different directories (`docs/planning/a/SAME_PLAN.md` vs `.../b/SAME_PLAN.md`).
        # relpath is CWD-dependent, which is why verify previously fell back to comparing basenames —
        # and that let an artifact copied between two same-named plans with identical bytes verify the
        # wrong one (full review, #41). realpath is absolute+canonical, so it is CWD-independent AND
        # directory-distinguishing. The artifact is git-ignored session state, so embedding an absolute
        # path is fine; a repo move simply invalidates it (re-run the gate), which is correct.
        "planPath": os.path.realpath(plan),
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
    _verdict = art.get("verdict")
    # A membership test on a non-string crashes: `[1,2] not in APPROVING` raises TypeError (unhashable),
    # taking down verify with a traceback instead of a controlled failure (codex, #42 review). And a
    # verdict OUTSIDE the combined vocabulary (a stale `WAIVED`, a bare reviewer status) is a corrupt
    # artifact, not a recoverable one — say so once, here, before anything reasons about it.
    if not isinstance(_verdict, str) or _verdict not in COMBINED_VERDICTS:
        return _fail(f"artifact verdict {_verdict!r} is not a recognized combined verdict "
                     f"({', '.join(sorted(COMBINED_VERDICTS))}) — corrupt or stale; re-run the gate")
    if _verdict not in APPROVING:
        # NAME the reviewers that never ran. Without this the message for "the two reviewers disagreed"
        # and "a reviewer CLI was unavailable" is byte-identical, so an implementer cannot tell which
        # `implement` recovery branch they are in and defaults to the wrong one — "iterate the plan +
        # gate" — which cannot work, because there is no plan problem to iterate (codex, #42 review).
        # `or []` only rescues FALSY junk: a tampered `reviewers: 5` / `true` is truthy and non-iterable,
        # so it reached the loop and raised TypeError (gemini, #42 review). It still exited non-zero —
        # a crash is not a pass — but a traceback is not a diagnosable failure, and the isinstance guard
        # below (which would have caught it) never ran because this hint is computed first.
        _revs = art.get("reviewers")
        if not isinstance(_revs, list):
            # Do NOT coerce to [] and carry on. `reviewers: 5` is a corrupt artifact, but coercing made
            # every downstream count zero, so the hint fell through and reported an ordinary
            # non-approving verdict — the same "never guess" invariant this branch exists to enforce,
            # broken by the guard I added to stop it crashing (gemini, #42 review). Fixing the crash and
            # keeping the silence just moved the failure from loud to quiet.
            return _fail(f"verdict is {art.get('verdict')!r}, not an approving verdict — gate not passed"
                         " — artifact is CORRUPT: reviewers is not a list, so nothing about this "
                         "artifact can be trusted; re-run the gate")

        def _name(r):
            """Readable reviewer name, or "" when absent/null/non-string.

            FOURTH instance of the `.get`-default trap in this file (gemini, #42 review): `str(r.get(
            "name"))` renders an explicit `"name": null` as the STRING "None", so the hint named a
            reviewer that does not exist — "None recorded MISSING (never ran)". Same normalization as
            `_status`; an unreadable NAME is as corrupt as an unreadable STATUS, and the invariant is the
            same: never guess.
            """
            v = r.get("name")
            return v.strip() if isinstance(v, str) and v.strip() else ""

        def _status(r):
            """Normalized status, or "" when the field is absent/null/non-string.

            NOT `str(r.get("status", ""))`: `.get(k, default)` returns the default only when the key is
            ABSENT — an explicit `"status": null` returns None, and `str(None)` is the STRING "None".
            That classified a null-status reviewer as a rejection and reported `gemini=NONE (ran, wants
            plan changes)` — fabricating a fact about a reviewer whose status is simply unusable
            (gemini, #42 review). This is the same `.get`-default trap already annotated on
            `transcriptSha256` in `_quorum_problem`; normalizing in one place stops the third instance.
            """
            v = r.get("status")
            return v.strip().upper() if isinstance(v, str) else ""

        # A status we cannot read is not a verdict. Say the artifact is corrupt; never guess.
        # That applies to an unreadable ENTRY exactly as much as an unreadable STATUS: filtering
        # non-dicts out silently let `reviewers: ["gemini-approved-trust-me", {...}]` skip the CORRUPT
        # branch and report "codex recorded MISSING ... NOT a plan problem" — a confident claim derived
        # from an artifact one of whose entries is garbage (pre-merge audit). Same invariant, one commit
        # after I wrote it down.
        _dicts = [r for r in _revs if isinstance(r, dict)]
        # USE THE DEFINED VOCABULARY. `REVIEWER_STATUSES` sits at the top of this file and the hint never
        # consulted it: `rejecting` was a CATCH-ALL for "not approving and not MISSING", so any status
        # outside the vocabulary was reported as a considered rejection (gemini AND codex, #42 review —
        # both found this independently, which is why it is the root cause and not a nit):
        #     INVALID_STATUS -> "gemini=INVALID_STATUS (ran, wants plan changes — address them)"
        #     WAIVED         -> same. And WAIVED is not hypothetical: THIS PR removes it, so artifacts
        #                       written before it carry a status this code no longer recognizes.
        #     lgtm           -> "gemini=LGTM (ran, wants plan changes)"
        # An unrecognized status is not a rejection; it is an artifact we cannot read.
        _unknown_status = sorted(f"{_name(r)}={_status(r)}" for r in _dicts
                                 if _name(r) and _status(r) and _status(r) not in REVIEWER_STATUSES)
        _bad_status = sorted(_name(r) for r in _dicts if _name(r) and not _status(r))
        _bad_names = sum(1 for r in _dicts if not _name(r))
        _bad_entries = len(_revs) - len(_dicts)
        # The artifact must record the MANDATORY pair. `_quorum_problem` enforces this for APPROVING
        # verdicts only, so `--reviewer gemni=MISSING` (a plain typo) was accepted here and produced
        # "gemni recorded MISSING (never ran)" — recovery advice about a reviewer that does not exist
        # (codex, #42 review).
        _names_l = [_name(r).lower() for r in _dicts if _name(r)]
        _known = set(_names_l)
        _absent_required = sorted(REQUIRED_REVIEWERS - _known)
        # DUPLICATES and STRAYS are corrupt here too. `_quorum_problem` rejects both, but only for
        # APPROVING verdicts, so a non-approving artifact sailed through and this hint then spoke
        # confidently about it (codex, #42 review):
        #   gemini=MISSING + gemini=REQUEST_CHANGES -> "gemini=REQUEST_CHANGES (ran, wants plan changes)
        #                                              AND gemini recorded MISSING" — gemini both ran
        #                                              and did not run, from one artifact.
        #   octo=MISSING (a stray)                  -> "octo recorded MISSING ... see 'Unavailable
        #                                              reviewer'" — recovery advice for a reviewer that
        #                                              is not part of the gate at all.
        _dupes = sorted({n for n in _names_l if _names_l.count(n) > 1})
        _strays = sorted(_known - REQUIRED_REVIEWERS)
        _corrupt = []
        if _unknown_status:
            _corrupt.append(f"{', '.join(_unknown_status)} is not a recognized status "
                            f"({', '.join(sorted(REVIEWER_STATUSES))})")
        if _bad_status:
            _corrupt.append(f"{', '.join(_bad_status)} has an absent/null/non-string status")
        if _bad_names:
            _corrupt.append(f"{_bad_names} reviewer entr"
                            f"{'y has' if _bad_names == 1 else 'ies have'} no readable name")
        if _bad_entries:
            _corrupt.append(f"{_bad_entries} reviewer entr"
                            f"{'y is' if _bad_entries == 1 else 'ies are'} not an object")
        if _dupes:
            _corrupt.append(f"{', '.join(_dupes)} appears more than once — one reviewer cannot both "
                            "run and not run")
        if _strays:
            _corrupt.append(f"{', '.join(_strays)} is not part of the gate "
                            f"({', '.join(sorted(REQUIRED_REVIEWERS))})")
        # NO `and not _corrupt` guard: for a typo BOTH facts are the diagnosis — `gemni` is a stray AND
        # `gemini` is absent. Suppressing the second because the first fired reported half of it and made
        # the reader work out the rest.
        if _absent_required:
            _corrupt.append(f"does not record the mandatory reviewer(s) {_absent_required} "
                            f"(recorded: {sorted(_known) or 'none'} — a typo?)")
        absent = sorted(_name(r) for r in _dicts if _name(r) and _status(r) == "MISSING")
        # A reviewer that RAN and rejected is a plan problem, and must not be masked by a MISSING peer.
        # The `in REVIEWER_STATUSES` filter is redundant BY CONSTRUCTION — `_unknown_status` above short-circuits
        # to the CORRUPT branch first, so this line is unreachable with a status outside the vocabulary,
        # and no test pins it (reverting it to the old catch-all fails nothing). Kept anyway, and said
        # plainly rather than dressed up as coverage: it makes this line's contract readable on its own,
        # which is exactly what the catch-all version lacked.
        rejecting = sorted(f"{_name(r)}={_status(r)}" for r in _dicts
                           if _name(r) and _status(r) in REVIEWER_STATUSES and _status(r) not in APPROVING
                           and _status(r) != "MISSING")
        if _corrupt:
            hint = (f" — artifact is CORRUPT: {'; '.join(_corrupt)} — so no reviewer classification here"
                    " can be trusted; re-run the gate")
        elif absent and rejecting:
            # MIXED. Saying "not a plan problem" here would tell the implementer to ignore real,
            # actionable feedback from the reviewer that DID run (codex, #42 review). Both are true and
            # both must be resolved.
            hint = (f" — TWO SEPARATE problems: {', '.join(rejecting)} (ran, wants plan changes — address"
                    f" them) AND {', '.join(absent)} recorded MISSING ({_MISSING_MEANS} — see"
                    " 'Unavailable reviewer' in the implement skill). Resolving either one alone will NOT"
                    " pass the gate")
        elif absent:
            # NOT "never ran". `review-synthesis` maps BOTH "reviewer never returned" AND "empty /
            # unparseable transcript" to MISSING (its normalization table, SKILL.md:48), so asserting
            # "never ran" states one of two possible facts as certain — and they need different
            # recoveries (install/authenticate the CLI vs re-capture the review). What IS common to both,
            # and is the load-bearing half, is that no plan edit clears either (codex, #42 review).
            hint = (f" — {', '.join(absent)} recorded MISSING: {_MISSING_MEANS}. Either way this is NOT"
                    " a plan problem, so iterating the plan cannot clear it; see 'Unavailable reviewer' in"
                    " the implement skill")
        else:
            hint = ""
        return _fail(f"verdict is {art.get('verdict')!r}, not an approving verdict — gate not passed{hint}")
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
    # to match a different plan must not satisfy the gate (PR #39 review). Compare the FULL realpath,
    # not the basename: two plans that share a basename in different dirs (with identical bytes, so the
    # digest also matches) would otherwise be interchangeable, and an artifact copied between them
    # verified the wrong one (full review, #41; reproduced). realpath is CWD-independent.
    if os.path.realpath(plan) != str(art.get("planPath", "")):
        return _fail(f"artifact was written for a different plan ({art.get('planPath')!r}), "
                     f"not {os.path.realpath(plan)}")
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
    w.add_argument("--reviewed-sha256", default=None,
                   help="the plan's SHA-256 as snapshotted BEFORE the reviews ran; write aborts if the "
                        "plan has since changed (binds approval to the reviewed bytes)")
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
