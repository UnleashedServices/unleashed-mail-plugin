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
import errno
import stat
import sys
from typing import NamedTuple

SCHEMA_VERSION = 3
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

# F8 (COREDEV-2503): upper bound for a trusted regular-file read (sidecar digest / small artifact). A
# size-only fstat check races a grow-after-check; `_read_regular_file` instead reads cap+1 and refuses on
# overflow. 64 KiB is orders of magnitude above any real digest sidecar or verdict artifact.
_MAX_TRUSTED_READ_BYTES = 65536


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
    # B2 (COREDEV-2503): reject STRAY reviewers too. This shared enforcer (write + verify) checked only for
    # MISSING required reviewers; `_reviewer_identity_problem` (write path) rejected strays but verify did
    # not, so a `{gemini, codex, mallory}` set could pass verification. Mirror the stray check here so BOTH
    # paths agree — an unknown name can't pad the quorum.
    strays = set(names) - REQUIRED_REVIEWERS
    if strays:
        return (f"reviewer(s) {sorted(strays)} are not part of the gate "
                f"({', '.join(sorted(REQUIRED_REVIEWERS))})")
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
    # 3. Content-digest floor — ALWAYS runs (COREDEV-2503 F1). A prior version treated a full set of
    #    distinct captureIds as AUTHORITATIVE and returned None HERE, skipping this floor. But captureId has
    #    no authenticity binding (`_provenance` only checks it is a non-empty string; it is read verbatim
    #    from a `.captureid` sidecar or hand-written into the artifact), so two DISTINCT FORGED captureIds
    #    behind ONE identical transcript bypassed the only control that catches "same content = one review
    #    standing in for two" -> GATE OK / APPROVE, exit 0. The floor now runs unconditionally; captureId
    #    distinctness (checked above) SUPPLEMENTS it, never replaces it. The benign false-negative (two
    #    byte-identical SEPARATE reviews rejected) is astronomically rare and fail-closed. Real authenticity
    #    binding is deferred to COREDEV-2497 content validation.
    _digests = [str(r.get("transcriptSha256", "")).strip().lower() for r in _dicts]
    if len(set(_digests)) < len(_digests):
        return ("an APPROVING combined verdict requires a DISTINCT transcript per reviewer — the same "
                "transcript content is recorded for more than one reviewer, i.e. one review standing in for two")
    return None


# S-FRESH applies to the per-run allocator layout introduced by COREDEV-2619. Historical callers and
# unit fixtures outside that layout remain readable, while every allocator-produced path is required to
# carry its own run-bound launch record. The allocator draws exactly 16 bytes and hex-encodes them.
_RUN_ID_HEX_LENGTH = 16 * 2
_TRANSCRIPT_RUN_ID = re.compile(
    r"-([0-9a-f]{" + str(_RUN_ID_HEX_LENGTH) + r"})\.txt\Z"
)
# The FULL allocator basename, used for CLASSIFICATION. `_TRANSCRIPT_RUN_ID` matches any name ending
# `-<32 hex>.txt`, which the docstring below names as colliding with digest-suffixed files like
# `review-<md5>.txt` — MD5 hex being exactly 32 characters. Such a file was then REQUIRED to carry a
# `.launch` and rejected without one, so a legitimate custom or historical transcript became
# unusable (PR #63 recheck, P2).
#
# Narrowing to the whole allocator shape — `<ticket>r<round>-<reviewer>-<32 hex>.txt` — removes that
# collision WITHOUT the fail-open the docstring rightly refuses: the basename travels with the file,
# so an allocated transcript that was copied or moved still classifies as per-run. That is exactly the
# property conditioning on the DIRECTORY would have lost.
_ALLOCATOR_BASENAME = re.compile(
    r"\A[A-Za-z0-9][A-Za-z0-9._-]*r[0-9]+-(?P<reviewer>[A-Za-z0-9][A-Za-z0-9-]*)-[0-9a-f]{"
    + str(_RUN_ID_HEX_LENGTH) + r"}\.txt\Z"
)
# `<32 hex run id> <reviewer>\n`. The reviewer field is what makes the identity ALLOCATOR-ATTESTED
# rather than parsed out of a filename the caller supplies (PR #63 recheck, P1). `pty-capture.py`
# writes it and carries a matching `_LAUNCH_RECORD_RE`; `test_doc_gates` pins the two together.
_LAUNCH_RECORD = re.compile(
    rb"\A([0-9a-f]{" + str(_RUN_ID_HEX_LENGTH).encode("ascii")
    + rb"}) ([A-Za-z0-9][A-Za-z0-9-]*)\n\Z"
)

def _sha256_bytes(path: str) -> str:
    """Raw-byte SHA-256 of a file (never text-normalized — a whitespace edit must change it)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_descriptor(descriptor: int) -> str:
    """Raw-byte SHA-256 of an ALREADY-OPEN descriptor — the same bytes `_sha256_bytes` would produce
    for that file, but bound to the OPEN FILE rather than to a name that can be re-pointed.

    `pread` rather than `read`: it takes an explicit offset, so the caller's descriptor offset is
    untouched and this can never disturb a later `fstat`/read by whoever owns the descriptor.
    """
    h = hashlib.sha256()
    offset = 0
    while True:
        chunk = os.pread(descriptor, 65536, offset)
        if not chunk:
            return h.hexdigest()
        offset += len(chunk)
        h.update(chunk)


class _VerifiedTranscript(NamedTuple):
    """The canonical path and raw-byte digest of the descriptor the freshness check VALIDATED.

    The gate's evidence must be the file that passed the check, so both fields are produced from the
    one descriptor rather than re-derived from the name afterwards (see `_regular_file_info`).
    """

    path: str
    sha256: str


def _read_regular_file(path: str) -> str | None:
    """Read `path` only if it is a REGULAR file, refusing a symlink or a FIFO/device. O_NOFOLLOW makes
    the symlink refusal ATOMIC at open (no islink()-then-open() TOCTOU window); O_NONBLOCK avoids blocking
    on a pre-created FIFO; an fstat S_ISREG check then rejects a FIFO/device an attacker planted at the
    predictable path. Returns the text, or None on any of those, so a pre-seeded non-regular sidecar can
    never be trusted as provenance (round 4 + round 5: codex)."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        with os.fdopen(fd, "r", encoding="utf-8") as fh:
            fd = -1  # fdopen owns it now; the finally must not double-close
            # F8 (COREDEV-2503): bound the read. A size-only fstat check races a grow-after-check, so read
            # cap+1 and refuse on overflow — a huge regular sidecar is not a genuine provenance digest, and
            # this also caps memory on a pathological file. (Chars, not bytes; utf-8 keeps this ~cap-bounded.)
            data = fh.read(_MAX_TRUSTED_READ_BYTES + 1)
            if len(data) > _MAX_TRUSTED_READ_BYTES:
                return None
            return data
    except (OSError, UnicodeDecodeError):
        # invalid-UTF-8 bytes in a sidecar are "not a genuine digest" — return None (controlled
        # fail-closed/skip), never a traceback (round 7: codex).
        return None
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


def _write_text_nofollow(path: str, text: str) -> None:
    """Write `text` to `path` at 0600 refusing to follow a symlink — O_NOFOLLOW makes it atomic. The
    `.tmp.<pid>` staging name is predictable, so a same-account attacker could pre-plant it as a symlink;
    `open(path, "w")` would then write THROUGH it to the link target with the gate process's privileges
    (round 8: codex). The `opener` keeps single-close ownership."""
    # NO O_TRUNC, and an EXPLICIT link-count check (PR #63 recheck, P2). A HARD LINK is a regular file,
    # so `O_NOFOLLOW` accepts one — and `O_TRUNC` empties the target AT open(), before any `fstat` can
    # look. A same-account attacker who pre-planted `<dest>.tmp.<pid>` as a hard link to a file they
    # wanted destroyed got it emptied on the way in, whatever this function decided afterwards. The same
    # pair of mistakes was found and fixed in `pty-capture.py`'s non-allocated write; this writer kept
    # them. Opening without O_TRUNC lets the `st_nlink` check refuse a linked victim with its bytes
    # intact, and the explicit `ftruncate` below bounds an honest overwrite exactly as O_TRUNC would.
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)

    def _op(p, _f):
        fd = os.open(p, flags, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise OSError(errno.ENOTSUP, "refusing a non-regular verdict target", p)
            if info.st_nlink != 1:
                raise OSError(
                    errno.EMLINK,
                    f"refusing to write through a hard-linked path ({info.st_nlink} links)",
                    p,
                )
            os.ftruncate(fd, 0)
            os.fchmod(fd, 0o600)
        except BaseException:
            os.close(fd)
            raise
        return fd

    with open(path, "w", encoding="utf-8", opener=_op) as fh:
        fh.write(text)


#: The private per-plan state directory. Named once so the descriptor writer and the two path helpers
#: cannot disagree about which directory they are creating.
VERDICT_DIR_NAME = ".verdicts"


def _plan_directory_fd(plan: str) -> "int | None":
    """A descriptor for the plan's directory, reached WITHOUT following a symlink at any component.

    THE PATHNAME IS NOT A PIN (PR #63 recheck, P1 — reproduced). The granted wrappers validate the
    plan with `containment.py` and hand this program the resolved path, but resolution happens again
    HERE, in a second process: a same-account swap of `docs/planning` for a symlink in that window made
    every state write follow the new ancestor. Reproduced end to end — `snapshot-plan.sh` returned 0
    having created `.verdicts/` and the digest sidecar inside an outside directory. Passing the
    realpath removed the "two different strings" half of that finding and could not remove this half,
    because a string cannot pin an inode across an exec.

    Walking down from the repository root with `O_DIRECTORY|O_NOFOLLOW` does pin it: a symlinked
    component fails ELOOP whenever it was planted, and every write below goes through the descriptor
    rather than through the name.

    Returns None when the plan is not inside a git worktree. That is `review-verdict.py`'s designed,
    tested behaviour for a plan outside any repository — it is the maintainer's own CLI as well as the
    gate's — and the granted wrappers, which are what the model can reach, refuse that case before
    calling it.
    """
    absolute = os.path.abspath(plan)
    root = _repo_root(absolute)
    if root is None:
        return None
    directory = os.path.dirname(absolute)
    relative = os.path.relpath(directory, root)
    components = [c for c in relative.split(os.sep) if c and c != os.curdir]
    if os.pardir in components:
        return None
    dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
    try:
        for component in components:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=dir_fd,
            )
            os.close(dir_fd)
            dir_fd = next_fd
    except OSError as error:
        os.close(dir_fd)
        raise SystemExit(
            f"review-verdict: refusing to reach plan state through a symlinked path component: "
            f"{directory}: {error}"
        ) from error
    return dir_fd


def _read_state_file(plan: str, name: str) -> "bytes | None":
    """Read `<plan dir>/.verdicts/<name>` through the same no-follow walk the writes use.

    THE READ PATH WAS NOT COVERED BY THE WRITE FIX (PR #63 recheck, P1). `_write_state_file` pinned the
    directory for `snapshot` and `write`, and `verify` still reopened the artifact by pathname — so the
    identical ancestor swap produced `GATE OK` against a DIFFERENT plan and its matching artifact, and
    restoring the ancestor afterwards left `implement` proceeding on a plan nothing had verified. That
    is the same sidecar-family mistake this campaign keeps making: the fix was applied to the members
    in front of me rather than to the family, and the read half was reported separately.

    Returns None when the file is absent, unreadable, or not a regular file. Raises SystemExit through
    `_plan_directory_fd` when a component is a symlink — refusing is right here: a verification that
    cannot prove WHICH file it read must not pass.
    """
    parent_fd = _plan_directory_fd(plan)
    if parent_fd is None:
        return _read_regular_file_bytes(
            os.path.join(os.path.dirname(os.path.abspath(plan)), VERDICT_DIR_NAME, name)
        )
    try:
        state_fd = os.open(
            VERDICT_DIR_NAME,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except OSError:
        return None
    finally:
        os.close(parent_fd)
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            dir_fd=state_fd,
        )
    except OSError:
        return None
    finally:
        os.close(state_fd)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        chunks = []
        while True:
            chunk = os.read(descriptor, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except OSError:
        return None
    finally:
        os.close(descriptor)


def _write_state_file(plan: str, name: str, text: str) -> str:
    """Create `<plan dir>/.verdicts/` and write `name` into it, never following a symlink.

    Both state writes had the same shape — `_ensure_secure_dir` on a NAME, then a path-based temp
    write and `os.replace` — so both followed a substituted ancestor. They share this one descriptor
    walk now, which is also why a third state file cannot quietly opt out.
    """
    parent_fd = _plan_directory_fd(plan)
    verdict_dir = os.path.join(os.path.dirname(os.path.abspath(plan)), VERDICT_DIR_NAME)
    if parent_fd is None:
        # No repository: the documented path-based behaviour, unchanged.
        _ensure_secure_dir(verdict_dir)
        dest = os.path.join(verdict_dir, name)
        if os.path.islink(dest):
            raise SystemExit(f"review-verdict: refusing to overwrite a symlinked state file: {dest}")
        tmp = f"{dest}.tmp.{os.getpid()}"
        old_umask = os.umask(0o077)
        try:
            _write_text_nofollow(tmp, text)
            os.replace(tmp, dest)
        finally:
            os.umask(old_umask)
            try:
                os.remove(tmp)
            except OSError:
                pass
        return dest

    old_umask = os.umask(0o077)
    try:
        try:
            os.mkdir(VERDICT_DIR_NAME, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        info = os.stat(VERDICT_DIR_NAME, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode):
            raise SystemExit(
                f"review-verdict: refusing a symlinked or non-directory verdict dir: {verdict_dir}"
            )
        state_fd = os.open(
            VERDICT_DIR_NAME,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    finally:
        os.umask(old_umask)
        os.close(parent_fd)

    old_umask = os.umask(0o077)
    tmp_name = f"{name}.tmp.{os.getpid()}"
    try:
        os.fchmod(state_fd, 0o700)
        _write_self_ignore(state_fd)
        _write_text_at(state_fd, tmp_name, text)
        os.replace(tmp_name, name, src_dir_fd=state_fd, dst_dir_fd=state_fd)
    finally:
        os.umask(old_umask)
        try:
            os.unlink(tmp_name, dir_fd=state_fd)
        except OSError:
            pass
        os.close(state_fd)
    return os.path.join(verdict_dir, name)


def _write_self_ignore(state_fd: int) -> None:
    """`.gitignore` holding `*`, created through the descriptor, never through a dangling link."""
    try:
        descriptor = os.open(
            ".gitignore",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=state_fd,
        )
    except OSError:
        return                                   # already present, or a link we must not write through
    try:
        os.write(descriptor, b"*\n")
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _write_text_at(state_fd: int, name: str, text: str) -> None:
    """Write `text` to `name` under `state_fd` at 0600, refusing a symlink or a hard-linked victim."""
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=state_fd,
    )
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.ENOTSUP, "refusing a non-regular state target", name)
        if info.st_nlink != 1:
            raise OSError(errno.EMLINK, "refusing a hard-linked state target", name)
        os.ftruncate(descriptor, 0)
        os.fchmod(descriptor, 0o600)
        payload = text.encode("utf-8")
        written = 0
        while written < len(payload):
            written += os.write(descriptor, payload[written:])
    finally:
        os.close(descriptor)


def _verdict_path(plan_path: str) -> str:
    """`<plan-dir>/.verdicts/<plan-basename>.verdict.json` — co-located with the plan it binds."""
    plan_path = os.path.abspath(plan_path)
    return os.path.join(os.path.dirname(plan_path), VERDICT_DIR_NAME,
                        os.path.basename(plan_path) + ".verdict.json")


def _reviewed_sha_sidecar(plan_path: str) -> str:
    """`<plan-dir>/.verdicts/<plan-basename>.reviewed-sha256` — the pre-review plan digest, snapshotted
    at gate LAUNCH by the `snapshot` subcommand so a LATER, separate `write` invocation can bind the
    approval to the bytes the reviewers saw. A shell variable cannot carry the digest across Claude Code
    tool invocations, so the earlier `REVIEWED_PLAN_SHA256=…` shell-local expanded EMPTY at write time
    (round 4: codex). Session state, git-ignored beside the artifact."""
    plan_path = os.path.abspath(plan_path)
    return os.path.join(os.path.dirname(plan_path), VERDICT_DIR_NAME,
                        os.path.basename(plan_path) + ".reviewed-sha256")


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
    # `lexists` + O_EXCL, NOT `exists` + `open(…, "w")` (PR #63 recheck, P2). `os.path.exists` is FALSE
    # for a DANGLING symlink, so a pre-planted `.verdicts/.gitignore -> /somewhere/victim` took the
    # write branch and `open(…, "w")` created and wrote THROUGH the link with this process's privileges.
    # `lexists` sees the link itself so the branch is not taken, and O_CREAT|O_EXCL|O_NOFOLLOW makes the
    # create-or-refuse atomic rather than a check followed by an unprotected open.
    gi = os.path.join(d, ".gitignore")
    if not os.path.lexists(gi):
        try:
            descriptor = os.open(
                gi,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except OSError:
            return
        try:
            os.write(descriptor, b"*\n")
        except OSError:
            pass
        finally:
            os.close(descriptor)


def _repo_root(path: str) -> str | None:
    """Nearest ancestor of `path` containing a `.git` entry, or None.

    `.git` must be accepted as a FILE as well as a directory: in a `git worktree` it is a file
    containing `gitdir: …`. A directory-only check resolves a nested worktree to the PARENT checkout,
    which would make every worktree share one identity — the exact confusion this change exists to
    remove. Verified: this worktree's `.git` is a file.
    """
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _plan_identity(path: str) -> tuple[str, str]:
    """(identity, kind) — the plan's identity for the artifact binding.

    Repo-relative when the plan is inside a git repo, absolute otherwise. Repo-relative is what lets a
    genuine approval survive the worktree move `CLAUDE.md` mandates: the artifact records
    `docs/planning/X_PLAN.md`, not a path on one developer's disk. It still distinguishes two plans
    that share a basename in different directories, which is the property PR #41 added and must not
    regress.

    The escape guard is DEFENCE-IN-DEPTH and is deliberately NOT claimed as mutation-proved: given
    `_repo_root` returns an ANCESTOR of the resolved path, `relpath` cannot produce a `..`, and when no
    root is found the function returns absolute before reaching the guard. Removing the guard is
    therefore unobservable today (executed both ways: byte-identical). It stays because a future
    `_repo_root` that returned a non-ancestor would make it load-bearing, and because emitting a
    `../`-prefixed identity would be far worse than the cost of two comparisons.
    """
    real = os.path.realpath(path)
    root = _repo_root(real)
    if root is None:
        return real, "absolute"
    rel = os.path.relpath(real, os.path.realpath(root))
    if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
        return real, "absolute"
    return rel.replace(os.sep, "/"), "repo-relative"


def _is_per_run_transcript(path: str) -> bool:
    """Return whether `path` has the allocator name or state-root-relative directory shape.

    Classification decides whether the launch-record freshness check runs at all, so every way of
    spelling an allocated path that still OPENS the allocated file must classify as per-run.
    Two ways did not (PR #63 review):

    * **Case.** The comparisons below were case-sensitive, but this gate runs on macOS, where APFS
      is case-insensitive by default. `…/Unleashed-Mail/…` opens the identical file while failing
      both branches, so the transcript was treated as legacy and the check never ran — readmitting
      exactly the stale/foreign transcript acceptance the check exists to reject. Compare casefolded.
    * **A sibling launch record is itself proof of per-run provenance.** Adding it as a third
      branch closes the residual spellings without enumerating them. The direction is safe:
      planting a `.launch` beside a genuinely legacy transcript only makes the gate STRICTER,
      because the record must then validate rather than being skipped.

    **The filename branch is deliberately not conditioned on the directory** (PR #63 review, item 4).
    It means any basename ending `-<32 lowercase hex>.txt` takes the per-run branch wherever it lives,
    so a transcript outside the allocator directory that happens to match — a digest-suffixed name like
    `review-<md5>.txt` is the realistic collision, MD5 hex being exactly 32 characters — is now required
    to carry a `.launch` and is REJECTED without one.

    That is accepted, because the alternative is a fail-open. Requiring the layout as well would make a
    genuinely allocated transcript that was copied or moved out of `unleashed-mail/review-transcripts/`
    classify as legacy and skip the check entirely, which is precisely the stale/foreign acceptance the
    check exists to reject — and moving a file is far easier than the collision it would guard against.
    A false positive here costs a re-run through the allocator, which is the mandated path anyway; the
    recovery is to rename the file, never to plant a `.launch` beside it, since a hand-written record
    would forge exactly the provenance this check verifies.

    **The ANCESTRY is resolved; the leaf never is.** The layout comparison used the lexical parents, so
    the same file classified differently depending only on how its path was spelled: `…/HASH/./f.txt`,
    `…/HASH/../HASH/f.txt` and a symlinked ancestor all opened the identical bytes while failing the
    comparison, and a layout-placed transcript with no allocator filename and no `.launch` therefore
    skipped the freshness check entirely (deep review; reproduced for all three spellings).

    Resolving `dirname(path)` fixes all three at once — `realpath` both normalizes `.`/`..` and follows
    a symlinked ancestor. It is NOT the defect this function's history warns about: that one resolved
    the WHOLE path, which walked a symlinked LEAF out of the layout and skipped the check. The leaf's
    own name and link-ness are untouched here, so the `islink` refusal below still sees it.

    `hash_directory` is the per-run repo-hash component, not the repository root (Rovo thread 3).
    """
    hash_directory = os.path.realpath(os.path.dirname(path))
    transcripts_directory = os.path.dirname(hash_directory)
    product_directory = os.path.dirname(transcripts_directory)
    return (
        _ALLOCATOR_BASENAME.match(os.path.basename(path)) is not None
        or (
            os.path.basename(transcripts_directory).casefold() == "review-transcripts"
            and os.path.basename(product_directory).casefold() == "unleashed-mail"
        )
        or os.path.lexists(path + ".launch")
    )


def _read_launch_record(launch_path: str):
    """Return (run ID, attested reviewer, descriptor metadata, problem) for one launch-record line.

    ONE parser returns BOTH fields. The freshness check needs the run id and the identity check needs
    the reviewer, and giving each its own copy of this reader meant the record grammar had to be
    tightened twice — the same divergence-between-two-arms defect the shared staging helpers exist to
    prevent, in the file that adjudicates them (PR #63 recheck).
    """
    launch_fd = -1
    try:
        launch_fd = os.open(
            launch_path,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
    except FileNotFoundError:
        return None, None, None, "launch record is absent: " + launch_path
    except OSError:
        return None, None, None, "launch record is unreadable or non-regular: " + launch_path

    try:
        launch_info = os.fstat(launch_fd)
        if not stat.S_ISREG(launch_info.st_mode):
            return None, None, None, "launch record is unreadable or non-regular: " + launch_path
        with os.fdopen(launch_fd, "rb") as stream:
            launch_fd = -1
            # Run id + space + reviewer + newline; 128 bounds a planted file while fitting any name.
            record = stream.read(128)
            if record == b"":
                return None, None, None, "launch record is EMPTY: " + launch_path
            record_match = _LAUNCH_RECORD.fullmatch(record)
            if record_match is None:
                return None, None, None, "launch record is malformed: " + launch_path
    except OSError:
        return None, None, None, "launch record is unreadable or non-regular: " + launch_path
    finally:
        if launch_fd >= 0:
            try:
                os.close(launch_fd)
            except OSError:
                pass

    return (
        record_match.group(1).decode("ascii"),
        record_match.group(2).decode("ascii"),
        launch_info,
        None,
    )


def _regular_file_info(path: str):
    """Return (descriptor metadata, raw-byte digest, problem), refusing symlinks and non-regular files.

    The digest is read from the SAME descriptor the metadata came from, and that is the whole point of
    returning it here. Returning only the metadata and letting the caller hash the PATH afterwards was a
    TOCTOU (PR #63 review): `_transcript_freshness_problem` validated this descriptor, closed it, and
    `_sha256_bytes` then re-opened the NAME — so a local attacker able to swap the leaf in that window
    got a gate that checked file A and recorded file B's digest as the reviewed evidence. Everything the
    caller is told about the transcript now comes from one O_NOFOLLOW open.
    """
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            return None, None, "transcript is unreadable or non-regular: " + path
        return info, _sha256_descriptor(descriptor), None
    except OSError:
        return None, None, "transcript is unreadable or non-regular: " + path
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _transcript_freshness_problem(transcript: str):
    """Return (failure, verified transcript) for one per-run transcript — (None, record) when the
    record is valid, (reason, None) when it is not, and (None, None) for a legacy path the check
    does not govern.

    Each call derives and opens its own sibling record; neither the other reviewer nor the reviewed-plan
    snapshot can become the anchor.

    The second element exists so the CALLER never has to resolve or open `transcript` again. Handing
    back only a reason meant the digest recorded as evidence came from a second, independent lookup of
    the same name, which is a check-then-use race on the gate's own evidence (PR #63 review, item 1).
    """
    # Classify on the LEXICAL path, BEFORE resolving it. Resolving first was the defect: a symlink
    # at an allocated path resolves out of the `unleashed-mail/review-transcripts/…` layout, so it
    # classified as legacy and the entire freshness check was skipped. Reproduced by the reviewer —
    # an allocated-looking symlink plus a matching `.launch` returned None and let `write` hash the
    # symlink's target, reintroducing stale/foreign transcript acceptance for that per-run path.
    if not _is_per_run_transcript(transcript):
        return None, None
    # Having classified it as per-run, refuse a symlink outright rather than validating the record
    # against one file and hashing another. A reserved leaf is a regular file the allocator created;
    # a symlink in its place is never legitimate, so this is fail-closed by construction.
    if os.path.islink(transcript):
        return "per-run transcript is a symbolic link: " + transcript, None
    # DO NOT RESOLVE THE LEAF. `islink()` then `realpath()` is a lookup-then-lookup pair: a same-account
    # process that plants a symlink between the two has it FOLLOWED, and every check below then runs
    # against the attacker's target instead of the allocated path — a foreign transcript with a matching
    # `.launch` and `.plan` passed as valid evidence (PR #63 recheck, P2). Keeping the allocated name is
    # also what the freshness TOCTOU fix already established: `_regular_file_info` opens it with
    # `O_NOFOLLOW` and everything downstream comes from that one descriptor, so a symlink planted later
    # fails the open rather than being resolved through.
    #
    # The ANCESTRY is still resolved (in `_is_per_run_transcript`) — that is the layout question, and it
    # is a different one from "which file is the leaf".

    filename_match = _TRANSCRIPT_RUN_ID.search(os.path.basename(transcript))
    if filename_match is None:
        return "per-run transcript filename has no canonical run ID: " + transcript, None
    filename_run_id = filename_match.group(1)
    launch_path = transcript + ".launch"
    record_run_id, _attested, launch_info, launch_problem = _read_launch_record(launch_path)
    if launch_problem is not None:
        return launch_problem, None

    if record_run_id != filename_run_id:
        return "launch record run ID does not match transcript filename: " + launch_path, None

    transcript_info, transcript_sha256, transcript_problem = _regular_file_info(transcript)
    if transcript_problem is not None:
        return transcript_problem, None

    transcript_mtime_ns = transcript_info.st_mtime_ns
    launch_mtime_ns = launch_info.st_mtime_ns
    if transcript_mtime_ns < launch_mtime_ns:
        return (
            "transcript is OLDER than its launch record "
            + f"({transcript_mtime_ns} < {launch_mtime_ns}): "
            + transcript
        ), None
    return None, _VerifiedTranscript(transcript, transcript_sha256)


_PLAN_BINDING = re.compile(rb"\A([0-9a-f]{64})  (.+)\n\Z")


def _plan_binding_problem(transcript: str, plan: str, plan_digest: str):
    """Refuse a per-run transcript that reviewed a DIFFERENT plan.

    The capture helpers write `<transcript>.promptsha256` and `<transcript>.plan`. The first was
    written and never read by anything — so transcripts allocated for an unrelated ticket, with
    sidecars naming unrelated prompts, still produced `GATE OK — APPROVE` for this plan: freshness
    proved the transcript was fresh, and the snapshot proved the PLAN was unedited, but nothing
    connected the two (deep review, P1). Freshness answers "is this transcript from a real, recent
    run"; this answers "a run of WHAT".

    Absent binding is refused rather than skipped, for per-run transcripts only — a legacy transcript
    the freshness check does not govern has no binding to check and never had one.
    """
    binding_path = transcript + ".plan"
    record = _read_regular_file_bytes(binding_path)
    if record is None:
        return (
            "per-run transcript has no plan binding: " + binding_path
            + " — re-capture it with the current capture helper, which records what it reviewed"
        )
    match = _PLAN_BINDING.fullmatch(record)
    if match is None:
        return "plan binding is malformed: " + binding_path
    bound_digest = match.group(1).decode("ascii")
    bound_plan = match.group(2).decode("utf-8", "replace")

    # `.planbytes` IS READ HERE — it was written and never read, which is this branch's own recurring
    # defect (PR #63 recheck, P1). `bind-prompt.py` keeps the exact bytes it hashed beside the record,
    # both isolation harnesses stage THOSE bytes, and until now nothing downstream ever compared them
    # to the record again. So a `.planbytes` rewritten after binding — without a matching edit to
    # `.plan` — fed the reviewer substituted bytes and left an artifact that still validated.
    #
    # HONEST SCOPE, because the reviewer's finding names a stronger attack than this closes. A
    # same-account process that replaces BOTH sidecars coherently and restores BOTH before the verdict
    # is written is NOT defended against here, and cannot be by any file-based binding: every anchor
    # this program could read is a file that same attacker can rewrite and restore, including the
    # transcript whose digest the artifact records. That is the same residual `audit-codex.sh` states
    # for its snapshot re-check — an attacker at that privilege can edit these scripts. What IS closed
    # is the whole uncoordinated family: a snapshot substituted and left, or restored while the record
    # was not, in either order.
    snapshot_path = transcript + ".planbytes"
    # STREAM IT, exactly as the prompt-snapshot check below already does — and this is a regression I
    # introduced, in the one file that carries the comment warning about it. `_read_regular_file_bytes`
    # caps at `_MAX_TRUSTED_READ_BYTES + 1` to bound UNTRUSTED PARSING of small sidecars; hashing a
    # plan through it truncates every plan over 64 KiB to its prefix, so the digest could never match
    # and EVERY approving persist for such a plan was rejected as a modified snapshot. Five plans in
    # this checkout are over the cap (the largest is 204 KB), so this was not hypothetical. A digest
    # reads every byte and holds none of them, which is why the cap does not apply to it.
    if _read_regular_file_bytes(snapshot_path) is None:
        return (
            "per-run transcript has no bound plan snapshot: " + snapshot_path
            + " — the binder writes it beside the record, so absence means it was removed. "
            "Re-capture the round through the capture helpers."
        )
    snapshot_digest = _sha256_regular_file(snapshot_path)
    if snapshot_digest is None:
        return "the bound plan snapshot became unreadable: " + snapshot_path
    if snapshot_digest != bound_digest:
        return (
            "the bound plan snapshot does not match its own record: " + snapshot_path
            + " hashes " + snapshot_digest[:12] + "…, " + binding_path + " records "
            + bound_digest[:12] + "… — the bytes the reviewer was fed are not the bytes the binding "
            "attests to"
        )

    # The DIGEST is the binding; the recorded path is diagnostic only. Comparing paths as well would
    # make the check depend on the working directory the capture and the write happened to run from,
    # and a path that merely LOOKS right proves nothing about the bytes anyway. Digest equality is
    # what answers "did this review read what is being approved" — and it composes exactly with the
    # snapshot check next to it, which answers "is the plan still those bytes".
    # THE IDENTITY TOO, not only the digest. Two distinct plans with byte-identical contents share a
    # digest, so a transcript captured for plan A satisfied an approval for plan B while this check
    # recorded — and ignored — the full repo-relative identity that distinguishes them. Same lesson as
    # PR #41's artifact fix and this morning's basename collision: equal bytes are not one plan.
    # ONLY WHEN THE RECORDED VALUE CAN DISCRIMINATE. The comment below is right that the digest is the
    # binding and that comparing paths in general would make this depend on the directory each step ran
    # from — that decision stands. What it missed is the case where the digest CANNOT discriminate: two
    # distinct plans with byte-identical contents share one, so a transcript captured for plan A
    # satisfied an approval for plan B (PR #63 recheck).
    #
    # A recorded value carrying a DIRECTORY is exactly what tells those two apart, and `bind-prompt.py`
    # always writes one (`os.path.relpath(plan, repo_root)`). A bare basename is under-specified — it
    # cannot distinguish them either way — so it is left alone rather than guessed at, which also keeps
    # pre-binding captures readable.
    # EVERY recorded identity is compared — there is no separator exemption (PR #63 recheck).
    # The `os.sep in bound_plan` guard was meant to leave under-specified legacy bindings alone, but
    # `bind-prompt.py` writes `os.path.relpath(plan, root)`, and for a plan at the REPOSITORY ROOT that
    # is a bare basename with no separator. So the exemption covered bindings the CURRENT binder
    # produces: two root-level plans with identical bytes both skipped this check, the equal digest
    # passed, and a transcript bound to `A_PLAN.md` approved `B_PLAN.md`. Reproduced.
    #
    # Comparing unconditionally is also the right direction for the legacy case the guard was written
    # for: a transcript whose recorded identity does not match the plan being written is refused rather
    # than accepted on a digest alone, and the operator re-captures. A transcript with NO binding at all
    # is a different branch above, which still names it explicitly.
    # A WHITESPACE-ONLY RECORDED IDENTITY IS NOT AN ABSENT ONE (PR #63 recheck, P2). `.strip()` turned
    # `<digest>   \n` into `""`, and the empty string then took the "no identity recorded" branch — so
    # the identity comparison this block exists for could be switched off by writing a blank path into
    # the record. That is the same "absent means unchecked" shape as a deleted sidecar, spelled with a
    # space, and it reopens exactly the byte-identical-plans bypass the comparison was added to close.
    # The binding grammar requires a non-empty field, so a blank one is malformed, not legacy.
    if bound_plan is not None and bound_plan != "" and not bound_plan.strip():
        return (
            "transcript binding records a BLANK plan identity: " + binding_path
            + " — the field is present but empty, which cannot be compared against the plan being "
            "written. Re-capture the round through the capture helpers."
        )
    bound_identity = bound_plan.strip() if bound_plan else ""
    if bound_identity:
        plan_identity, _kind = _plan_identity(plan)
        if os.path.normpath(bound_identity) != os.path.normpath(plan_identity):
            return (
                "transcript is bound to a different plan: " + binding_path + " records "
                + bound_identity + ", the verdict is being written for " + plan_identity
            )
    if bound_digest != plan_digest:
        return (
            "transcript reviewed different bytes than this verdict approves: " + binding_path
            + " records " + bound_digest[:12] + "… (" + bound_plan + "), the plan being written is "
            + plan_digest[:12] + "…"
        )
    # THE PROMPT SNAPSHOT, checked here because nothing else ever read `.promptsha256`.
    # `bind-prompt.py` writes both the snapshot the reviewer was fed and its digest; until now the
    # digest was recorded and never compared, which is the same "written and never read" shape as the
    # other two sidecars. This is a WRITE-time check — `cmd_verify` is COREDEV-2497's territory and is
    # deliberately untouched.
    snapshot = transcript + ".prompt"
    # REQUIRED, not optional. Skipping when the sidecar is absent meant deleting `.promptsha256` turned
    # the check off — the same "absent means unchecked" fail-open the plan binding above was written to
    # close, reintroduced one field over (PR #63 recheck). Both sidecars are written together by
    # `bind-prompt.py`, so a per-run transcript missing this one was not captured by the current helper.
    recorded = _read_regular_file_bytes(transcript + ".promptsha256")
    if recorded is None:
        return (
            "per-run transcript has no prompt binding: " + transcript + ".promptsha256"
            + " — re-capture it with the current capture helper, which records the prompt it fed"
        )
    match = _PLAN_BINDING.fullmatch(recorded)
    if match is None:
        return "prompt binding is malformed: " + transcript + ".promptsha256"
    # STREAM IT. `_read_regular_file_bytes` caps at `_MAX_TRUSTED_READ_BYTES + 1`, so a legitimate
    # prompt above that cap hashed only its prefix and this reported the snapshot as modified —
    # an otherwise valid approving review could never be persisted (PR #63 recheck). The cap exists to
    # bound TRUSTED PARSING of small sidecars; a digest reads every byte and holds none of them, so it
    # is not the thing the cap protects against.
    actual_digest = _sha256_regular_file(snapshot)
    if actual_digest is None:
        return (
            "the prompt snapshot the reviewer was fed is missing: " + snapshot
            + " — re-capture the round rather than writing a verdict for evidence that is gone"
        )
    actual = actual_digest.encode("ascii")
    if actual != match.group(1):
        return (
            "the prompt snapshot no longer matches the digest recorded when it was bound ("
            + snapshot + ") — the bytes the reviewer saw are not the bytes on disk"
        )
    return None


def _reviewer_identity_mismatch(reviewers) -> "str | None":
    """Refuse a transcript whose ALLOCATED identity is not the reviewer it is declared as.

    THE QUORUM BYPASS (PR #63 recheck, P1 — reproduced). Two separately allocated GEMINI runs supplied
    as `gemini=APPROVE:` and `codex=APPROVE:` passed everything: freshness, the plan binding, and the
    distinct path/digest/captureId rules — because every one of those asks whether the two entries
    DIFFER, and two real gemini runs do. Nothing asked what either transcript actually was. So one arm
    satisfied the mandatory two-arm gate, which is the single thing the gate exists to require.

    The allocator encodes the reviewer in the filename it reserves, so the answer is already carried by
    the evidence — it just was not read. That is the same "recorded and never compared" shape as the
    prompt digest and the bound plan identity, both closed earlier in this release.

    THE FILENAME WAS THE ONLY WITNESS, AND A RENAME DEFEATED IT IN BOTH DIRECTIONS (PR #63 recheck,
    P1 — both reproduced end to end, yielding `GATE OK — APPROVE [gemini, codex]` from two genuine
    GEMINI captures with Codex never running):

      * OUT OF THE GRAMMAR. This function was the only reader of the reviewer, and it `continue`d when
        `_ALLOCATOR_BASENAME` did not match — while the approving-evidence gate admitted the file on the
        looser `_is_per_run_transcript` (name OR directory layout OR a `.launch` sibling) and freshness
        keyed off a bare run-id suffix search. Three checks, three definitions of "allocated". The old
        docstring's premise — that approving evidence is always allocator-shaped, so no approving
        transcript reaches here unreadable — is exactly what failed.
      * INSIDE THE GRAMMAR. A canonical name with the reviewer field swapped satisfied everything,
        because the `.launch` record bound the run id and nothing else. Tightening this function to
        require the grammar would have closed the first and left the second untouched.

    So the identity is read from the ALLOCATOR'S RECORD, which the caller does not write: `.launch` now
    carries `<run id> <reviewer>`, and a rename cannot change it. A transcript whose record is absent or
    unparseable is REFUSED rather than skipped — "absent means unchecked" is the fail-open shape this
    whole family of bindings exists to close, and this function is only reached for approving verdicts.
    """
    for reviewer in reviewers:
        if not isinstance(reviewer, dict):
            continue
        declared = str(reviewer.get("name", "")).strip().casefold()
        transcript = reviewer.get("transcriptPath")
        if not declared or not isinstance(transcript, str) or not transcript:
            continue

        _run_id, attested, _info, problem = _read_launch_record(transcript + ".launch")
        if problem is not None:
            return (
                f"{declared!r}'s transcript carries no usable allocator record, so its identity cannot "
                f"be attested: {problem}. Re-capture the round through the capture helpers."
            )
        if attested.casefold() != declared:
            return (
                f"transcript allocated for {attested!r} is declared as {declared!r}: {transcript}"
                " — one arm cannot stand in for the other, which is the whole point of a dual review"
            )
        # The filename is the caller's spelling; when it is allocator-shaped it must AGREE with the
        # record. A mismatch means one of the two was rewritten, which is the rename attack itself.
        match = _ALLOCATOR_BASENAME.match(os.path.basename(transcript))
        if match is not None and match.group("reviewer").casefold() != attested.casefold():
            return (
                f"transcript filename says {match.group('reviewer')!r} but its allocator record "
                f"attests {attested!r}: {transcript} — the leaf was renamed"
            )
    return None


def _sha256_regular_file(path: str):
    """SHA-256 of a whole regular file through one O_NOFOLLOW descriptor, or None if unreadable.

    Separate from `_read_regular_file_bytes` on purpose: that one bounds how much UNTRUSTED text is
    parsed, which a digest never does — it consumes every byte and keeps none.
    """
    descriptor = -1
    try:
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        return _sha256_descriptor(descriptor)
    except OSError:
        return None
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _read_regular_file_bytes(path: str):
    """Raw bytes of a regular file, refusing a symlink or non-regular target. None on any of those."""
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        return os.pread(descriptor, _MAX_TRUSTED_READ_BYTES + 1, 0)
    except OSError:
        return None
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
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
            raise SystemExit(
                f"review-verdict: reviewer {name!r} transcript is EMPTY and therefore MISSING: "
                + transcript
            )
        freshness_problem, verified = _transcript_freshness_problem(transcript)
        if freshness_problem is not None:
            raise SystemExit(
                f"review-verdict: reviewer {name!r} transcript failed freshness: "
                + freshness_problem
            )
        # A per-run transcript's evidence is read off the descriptor freshness VALIDATED — never by
        # naming the file a second time. `verified` is None only for a legacy path the check does not
        # govern, where there is no earlier validation for a second lookup to diverge from.
        # THE LEGACY BRANCH GETS THE SAME DESCRIPTOR DISCIPLINE (PR #63 recheck, P2). `_sha256_bytes`
        # is an ordinary blocking, symlink-following open, taken AFTER the `isfile`/size checks — so a
        # same-account process could substitute a FIFO and wedge `persist-verdict.sh` with no timeout,
        # or substitute a symlink and have the artifact record the digest of an unrelated file. The
        # branch is reachable for NON-APPROVING legacy records, which the allocated-evidence rule does
        # not cover. `_sha256_regular_file` opens once with `O_NOFOLLOW|O_NONBLOCK` and refuses a
        # non-regular target, exactly as the per-run branch already does.
        legacy_digest = None if verified is not None else _sha256_regular_file(transcript)
        if verified is None and legacy_digest is None:
            raise SystemExit(
                f"review-verdict: reviewer {name!r} transcript is unreadable or not a regular file: "
                + transcript
            )
        out["transcriptSha256"] = (
            verified.sha256 if verified is not None else legacy_digest
        )
        # PROVENANCE beyond content-inequality (full review, #41). Record the canonical capture PATH,
        # and a wrapper-produced capture ID when `pty-capture.py` left one beside the transcript
        # (`<transcript>.captureid`). Content-inequality alone cannot tell two genuinely-separate
        # reviews that happen to be byte-identical from one file reused for both; a distinct path (the
        # common accidental case) and a distinct capture ID (a per-run token) can. Both optional and
        # auto-discovered — no caller/skill change needed; absent -> the digest floor still applies.
        out["transcriptPath"] = (
            verified.path if verified is not None else os.path.realpath(transcript)
        )
        _cid = transcript + ".captureid"
        # Read the sidecar with O_NOFOLLOW so a SYMLINK is refused ATOMICALLY at open. A pre-seeded
        # `<transcript>.captureid` symlink (attacker-chosen value) would otherwise be trusted as
        # authoritative provenance and make two copied transcripts look like distinct runs. An
        # islink()-then-open() precheck has a TOCTOU race — a local attacker owning the predictable /tmp
        # dir can swap a regular file for a symlink between the check and the open; O_NOFOLLOW closes that
        # window (a genuine pty-capture sidecar is a real regular file) (round 3 + round 4: codex).
        _cap = _read_regular_file(_cid)
        if _cap is not None:
            _v = _cap.strip()
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


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Record the plan's CURRENT digest to the `.reviewed-sha256` sidecar. Run at gate LAUNCH, BEFORE
    dispatching /gemini-review + /codex-review, so `write` (a later invocation) binds the approval to
    exactly these bytes. Overwrites any prior snapshot atomically — re-run it whenever the plan is
    revised in response to feedback."""
    plan = args.plan
    if not os.path.isfile(plan):
        raise SystemExit(f"review-verdict: plan not found: {plan}")
    digest = _sha256_bytes(plan)
    _write_state_file(plan, os.path.basename(_reviewed_sha_sidecar(plan)), digest + "\n")
    print(f"review-verdict: snapshotted reviewed plan digest {digest[:12]}… for {plan}")
    return 0


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
    # `is not None`, not truthiness: OMITTING the flag (default None) legitimately skips the check
    # (backward-compatible), but passing it EMPTY (`--reviewed-sha256 ""`, e.g. an unset shell var)
    # must FAIL loudly — a falsy-skip would silently disable the binding and record an approval bound
    # to no reviewed bytes, exactly what the flag defends against (round 1: gemini + codex).
    # Hash the plan ONCE and reuse it for BOTH the reviewed-digest check and the artifact's `planSha256`
    # below. Re-reading the file for the artifact would reopen a TOCTOU: a plan edited between the check
    # and artifact construction would pass `--reviewed-sha256` on the old bytes yet record the new,
    # unreviewed digest, which `verify` would then accept (round 3: codex).
    plan_sha = _sha256_bytes(plan)
    # The reviewed-digest BINDING applies ONLY to an APPROVING verdict — that is the one bound to the bytes
    # the reviewers saw. A non-approving verdict blocks `implement` regardless, so a stale/absent snapshot
    # must NOT affect it: gating the whole block on APPROVING stops a REQUEST_CHANGES after a plan edit from
    # aborting on the digest mismatch (round 7: codex).
    if verdict in APPROVING:
        # Resolve the reviewed digest from EITHER the explicit --reviewed-sha256 flag (an EMPTY value fails
        # loudly rather than silently skipping — round 1) OR the `snapshot`-written sidecar (the normal
        # flow; a shell var can't cross tool invocations — round 4). The sidecar is read via
        # _read_regular_file: O_NOFOLLOW closes the islink()-then-open() TOCTOU race and fstat rejects a
        # planted FIFO (round 5).
        expected = None
        if getattr(args, "reviewed_sha256", None) is not None:
            expected = args.reviewed_sha256.strip().lower()
            if not _SHA256_HEX.match(expected):
                raise SystemExit(f"review-verdict: --reviewed-sha256 must be 64 hex chars, got {expected!r}")
        else:
            # THROUGH THE SAME WALK as the artifact read and both writes — the third member of this
            # family, found by sweeping rather than by a report. `_read_regular_file` closes the
            # islink-then-open race on the LEAF; the ancestor swap it cannot see is what redirected
            # the other two (PR #63 recheck, P1).
            _raw = _read_state_file(plan, os.path.basename(_reviewed_sha_sidecar(plan)))
            # UNDECODABLE BYTES MEAN "NO BINDING", exactly as `_read_regular_file` treated them — a
            # decision made with codex in round 7, and the fail-closed "requires a reviewed-plan
            # digest" is the message that tells the operator to re-run `snapshot`. Decoding with
            # `errors="replace"` instead turned garbage into a present-but-corrupt string and changed
            # that diagnostic; the pinned test caught it. Same refusal either way, different guidance.
            _snap = None
            if _raw is not None:
                try:
                    _snap = _raw.decode("utf-8")
                except UnicodeDecodeError:
                    _snap = None
            if _snap is not None:
                expected = _snap.strip().lower()
                if not _SHA256_HEX.match(expected):
                    raise SystemExit("review-verdict: snapshot sidecar is corrupt (not 64 hex chars): "
                                     + _reviewed_sha_sidecar(plan))
        # FAIL CLOSED: no binding at all (snapshot skipped/removed/symlinked/FIFO) leaves the review->write
        # window open — a caller could review v1, edit to v2, and write an APPROVE bound only to v2, which
        # `verify` then accepts (round 6: codex).
        if expected is None:
            raise SystemExit(
                "review-verdict: an APPROVING verdict requires a reviewed-plan digest, but none is "
                "available (no snapshot sidecar and no --reviewed-sha256). Run `review-verdict.py snapshot "
                f"--plan {plan}` BEFORE dispatching the reviews. Refusing to bind an approval to unreviewed bytes.")
        if plan_sha != expected:
            raise SystemExit(
                "review-verdict: the plan CHANGED between review and write — refusing to record an "
                f"approval bound to bytes the reviewers never saw (reviewed {expected[:12]}…, now "
                f"{plan_sha[:12]}…). Re-run the reviews and `snapshot` on the current plan.")
    reviewers = [_parse_reviewer(s) for s in (args.reviewer or [])]
    # WHAT did each transcript review? Freshness proves a transcript is a real, recent run; the
    # snapshot proves the PLAN is unedited. Neither connects the two, so transcripts captured for an
    # unrelated ticket satisfied this plan's gate (deep review, P1). Applies to APPROVING verdicts:
    # a non-approving one blocks `implement` regardless, and refusing it on a binding problem would
    # stop a legitimate REQUEST_CHANGES from being recorded.
    if verdict in APPROVING:
        for reviewer in reviewers:
            transcript = reviewer.get("transcriptPath")
            if not transcript or not _is_per_run_transcript(transcript):
                continue
            binding_problem = _plan_binding_problem(transcript, plan, plan_sha)
            if binding_problem is not None:
                raise SystemExit(
                    f"review-verdict: reviewer {reviewer['name']!r} transcript is not bound to this "
                    "plan: " + binding_problem
                )
    if len(reviewers) < 2:
        # The gate is a DUAL review — a single reviewer can never carry an approval artifact.
        raise SystemExit("review-verdict: at least two reviewers (gemini + codex) are required")
    id_problem = _reviewer_identity_problem(reviewers)
    if id_problem:
        raise SystemExit("review-verdict: refusing to write a malformed artifact — " + id_problem)
    problem = _quorum_problem(verdict, reviewers)
    if problem:
        raise SystemExit("review-verdict: refusing to write an approving artifact — " + problem)
    # ALLOCATOR-SHAPED OR NOTHING, for an approving verdict — and deliberately LAST.
    #
    # `_is_per_run_transcript` is the switch deciding whether freshness AND the plan binding run at
    # all, so a transcript failing it was exempt from BOTH. The shapes it exempts are the fixed
    # the fixed shared-`/tmp` reviewer outputs an older plugin version left behind, so two stale
    # legacy files could be labelled APPROVE, combined with a fresh snapshot of the current plan, and
    # produce a gate-passing artifact for a plan nobody reviewed (PR #63 recheck, P1 — reproduced).
    #
    # Legacy paths stay readable for NON-approving records: those block `implement` anyway, and
    # refusing them would discard a legitimate REQUEST_CHANGES captured before the migration.
    #
    # ORDER: after the quorum and identity rules, which own "no transcript for this reviewer",
    # "duplicate capture ID" and "empty transcript". Placed before them this answered all three with
    # "not allocator-shaped" — true, but it tells the operator to re-capture when the real fault was a
    # missing operand. Two existing tests caught that regression.
    # WHAT each transcript IS, not merely that the two differ. Every distinctness rule above compares
    # the entries to EACH OTHER; this compares each one to ITSELF.
    #
    # ORDER, for the second time in this file: placed before the quorum and distinctness rules it
    # answered "the same transcript given to both reviewers" with "mislabelled", which is true but
    # useless — the caller's actual mistake was reusing one file, and four tests that name that rule
    # caught the regression. The specific diagnosis wins; this is the residue.
    if verdict in APPROVING:
        # APPROVING ONLY, matching the asymmetry the allocated-evidence rule already uses. The bypass
        # this closes is "one arm satisfies the mandatory TWO-arm gate", which is a property of an
        # APPROVAL — a non-approving record blocks `implement` whatever its labels say, so refusing one
        # would discard a legitimate REQUEST_CHANGES for no gain. Two tests that pin the non-approving
        # asymmetry caught this scope error.
        # ORDER, for the THIRD time in this function. The allocated-evidence rule runs BEFORE the
        # identity check because the identity check now REFUSES a transcript whose `.launch` is absent
        # (PR #63 recheck, P1) — which is every legacy path. Run second, it answered "this is a legacy
        # transcript" with "its identity cannot be attested": true, but it names the wrong rule and
        # leaves the coarser one unreachable, so a later relaxation of the identity check would silently
        # change what legacy paths are allowed to do. The test that pins the legacy rule caught this.
        for reviewer in reviewers:
            transcript = reviewer.get("transcriptPath")
            if not _is_per_run_transcript(str(transcript)):
                raise SystemExit(
                    "review-verdict: an APPROVING verdict requires ALLOCATED evidence, but "
                    f"{reviewer.get('name')}'s transcript is not allocator-shaped: {transcript!r}. "
                    "A legacy/fixed transcript path is exempt from BOTH the freshness check and the "
                    "plan binding, so an approval backed by one attests to nothing. Re-capture the "
                    "round through `capture-codex-review.sh` / `capture-gemini-review.sh`.")
        mismatch = _reviewer_identity_mismatch(reviewers)
        if mismatch:
            raise SystemExit(
                "review-verdict: refusing to write a mislabelled artifact — " + mismatch
            )
    artifact = {
        "schemaVersion": SCHEMA_VERSION,
        # REPO-RELATIVE when the plan is inside a git repo, absolute otherwise (COREDEV-2603).
        # It was `os.path.realpath`, which bound the approval to one developer's disk layout: the
        # worktree move `CLAUDE.md` MANDATES then failed the gate on a genuine five-round approval
        # with byte-identical plan content (COREDEV-2583). Repo-relative still distinguishes two
        # plans that share a basename in different directories — the property PR #41 added — because
        # `docs/planning/a/SAME_PLAN.md` != `docs/planning/b/SAME_PLAN.md`.
        # This does NOT make the artifact portable: `.verdicts/` is git-ignored at the repo root and
        # self-ignored by `_ensure_secure_dir`, so CI and a second developer still cannot verify.
        # That is by design (PR #39) and out of scope here.
        "planPath": _plan_identity(plan)[0],
        # Which form the line above chose. Without it, verify could compare a relative string against
        # an absolute one and pass or fail by ACCIDENT — the one shape a compatibility branch would
        # have to allow, which is why SCHEMA_VERSION went 2 -> 3 instead.
        "planPathKind": _plan_identity(plan)[1],
        "planSha256": plan_sha,   # the SAME bytes the reviewed-digest check validated above (no re-read)
        "verdict": verdict,
        "reviewers": reviewers,
        "round": args.round,
        "createdAt": args.created_at or "",   # caller passes an ISO stamp; scripts can't read the clock
    }
    _write_state_file(
        plan,
        os.path.basename(_verdict_path(plan)),
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
    )
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
    # READ THROUGH THE SAME NO-FOLLOW WALK THE WRITES USE (PR #63 recheck, P1). The `islink` checks
    # below were a pathname pre-check, so a same-account swap of a plan ANCESTOR between them and the
    # open sent verification at a different directory entirely — `GATE OK` against another plan and its
    # matching artifact, with the ancestor restored afterwards. `_read_state_file` opens the artifact
    # relative to a descriptor obtained by walking from the repository root, so no component can be
    # substituted between the walk and the read.
    try:
        raw = _read_state_file(plan, os.path.basename(dest))
    except SystemExit as refusal:
        return _fail(str(refusal).replace("review-verdict: ", ""))
    if raw is None:
        return _fail(f"no Combined-verdict artifact for this plan (run the gate first): {dest}")
    try:
        art = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
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
    identity, kind = _plan_identity(plan)
    recorded_kind = art.get("planPathKind")
    if recorded_kind not in ("repo-relative", "absolute"):
        return _fail(f"artifact has a missing or unknown planPathKind ({recorded_kind!r}) — "
                     "re-run the gate (schemaVersion 3 requires it)")
    if recorded_kind != kind:
        return _fail(f"artifact records a {recorded_kind} plan identity but this plan resolves as "
                     f"{kind} — re-run the gate here rather than comparing across forms")
    if identity != str(art.get("planPath", "")):
        return _fail(f"artifact was written for a different plan ({art.get('planPath')!r}), "
                     f"not {identity}")
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
                        "plan has since changed (binds approval to the reviewed bytes). Omit it to auto-"
                        "read the `snapshot` sidecar (the normal gate flow)")
    w.add_argument("--round", type=int, default=None)
    w.add_argument("--created-at", default=None, help="ISO-8601 timestamp (caller supplies the clock)")
    w.set_defaults(func=cmd_write)
    s = sub.add_parser("snapshot", help="record the plan's pre-review digest at gate launch (for write)")
    s.add_argument("--plan", required=True)
    s.set_defaults(func=cmd_snapshot)
    v = sub.add_parser("verify", help="fail closed unless an approving, digest-matching artifact exists")
    v.add_argument("--plan", required=True)
    v.set_defaults(func=cmd_verify)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
