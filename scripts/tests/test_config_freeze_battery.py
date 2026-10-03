#!/usr/bin/env python3
"""COREDEV-2860, cell 8(f) and plan §6 step 2a — the adjudication mutant battery, run against the REAL
functions in `test_trunk_check_workflow`, never against a model.

The plan's mutant table was measured on an in-memory MODEL of the aggregate. A model can quietly disagree
with what ships; this module is what stops it. Every mutant patches EXACTLY ONE production helper — the
helpers were split along decision lines precisely so this is possible — and every row is observed EXACTLY
as the plan writes it: a REFUSE row requires `ConfigFreezeRefusal` with the row's operand, reason and (for
kind rows) subtype, and NO content read beyond the named background member; a MEMBER row observes
membership and nothing else. An observation stricter than the written rule hides the very gap the rule
leaves open — that happened four times while this table was being designed.

A mutant failing NO row is a missing row. A mutant failing a different set than recorded means the model
and the implementation diverged: find out why — do not edit the set to match.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import pathlib
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import suppress
from typing import Any

import test_trunk_check_workflow as t
import yaml

W = t._WORKSPACE
BACKGROUND = frozenset(
    {".gitleaks.toml", ".gitleaksignore"}
)  # one PRESENT, one ABSENT optional


# ---- the fixture ------------------------------------------------------------------------------------


def symlinked_outer(tmp: pathlib.Path) -> pathlib.Path:
    """The fixture's OUTER directory, reached through a symlink on EVERY platform.

    macOS gives this for free (`$TMPDIR` is under `/var -> /private/var`) and Linux does not, so the
    `resolve-one-side` mutant was measured on macOS as failing nearly every row, and on the Linux CI
    runner it failed only the rows `resolve-alike` fails: resolving one side IS resolving both when no
    ancestor of the anchor is a link. One fixture, two oracles. Planting the link here makes the mutant
    discriminate identically everywhere, and models the real case of a checkout under a symlinked path.
    """
    target = tmp / "outer-target"
    target.mkdir()
    link = tmp / "outer"
    link.symlink_to(target)
    return link


def build(outer: pathlib.Path) -> pathlib.Path:
    """One outer directory holding sibling `real/ws` and `outside`, plus `alias -> real` ABOVE the anchor,
    so row 29's alternate spelling exists on every platform (Linux has no `/var -> /private/var`).
    """
    ws, outside = outer / "real" / "ws", outer / "outside"
    for d in (
        "policy",
        "real_dir",
        "locked",
        "locked2",
        "locked3",
        "policy_dir",
        "dirA",
        "dirB",
        "coll_a",
        "coll_b",
        "forge",
    ):
        (ws / d).mkdir(parents=True)
    (outside / "child").mkdir(parents=True)
    (outer / "alias").symlink_to(outer / "real")
    for f in (
        outside / "security.toml",
        outside / "config.toml",
        ws / ".gitleaks.toml",
        ws / "policy" / "plain.toml",
        ws / "policy" / "other.toml",
        ws / "plain_file",
        ws / "a..b.toml",
        ws / ".hidden.toml",
        ws / "locked" / "inner.toml",
        ws / "locked2" / "inner.toml",
        ws / "locked3" / "inner.toml",
        ws / "policy_dir" / "a.toml",
        ws / "devnode",
        ws / "outsider.toml",
    ):
        f.write_text("x\n", encoding="utf-8")
    for name in ("fa.toml", "fb.toml"):
        (ws / name).write_text("same\n", encoding="utf-8")
    for d in ("dirA", "dirB"):
        (ws / d / "x.toml").write_text("same\n", encoding="utf-8")
    (ws / "policy" / "security.toml").symlink_to(outside / "security.toml")
    (ws / "sym_dir").symlink_to(outside)
    (ws / "plink").symlink_to(outside / "child")
    (ws / "dangle").symlink_to(outer / "does_not_exist")
    os.mkfifo(ws / "pipe")
    digest = hashlib.sha256(b"policy bytes").hexdigest()
    for d in ("coll_a", "coll_b"):
        (ws / d / "x.toml").write_bytes(b"policy bytes")
    (ws / "coll_a:tree").write_text(
        "x.toml:" + digest, encoding="utf-8"
    )  # vs a LINE-format tree
    (ws / "coll_b:tree").write_text(
        json.dumps(["x.toml", digest], separators=(",", ":")), encoding="utf-8"
    )  # vs a JSON-record tree
    return ws


def trunk_for(operand: str) -> str:
    """The row's operand through the shape that carries it: a relative one as `direct_config`, every
    other one as an `environment[].value` (a `${workspace}` token, or an absolute path).
    """
    if not operand.startswith(W) and not operand.startswith("/"):
        definition: dict[str, Any] = {"name": "probe", "direct_config": operand}
    else:
        definition = {
            "name": "probe",
            "environment": [{"name": "PROBE", "value": operand}],
        }
    return str(yaml.safe_dump({"lint": {"definitions": [definition]}}))


# ---- the rows: (operand, kind, expectation) — kind/expectation follow the plan's observation rules -----

ROWS: dict[int, tuple[Any, str, Any]] = {
    1: (W + "/policy/security.toml", "REFUSE", ("symlink", None)),
    2: (W + "/sym_dir/config.toml", "REFUSE", ("symlink", None)),
    3: (W + "/plink/../security.toml", "REFUSE", ("dotdot", None)),
    4: (W + "/real_dir/../security.toml", "REFUSE", ("dotdot", None)),
    5: (W + "/../outside.toml", "REFUSE", ("dotdot", None)),
    6: (W + "/.", "ROOT", None),
    7: (W + "_extra/x.toml", "OUT", None),
    8: (W + "/policy/plain.toml", "MEMBER", "policy/plain.toml"),
    9: (W + "/no_such_dir/absent.toml", "MEMBER", "no_such_dir/absent.toml"),
    10: (W + "/ordinary.toml", "CED", "ordinary.toml"),
    11: (W + "/plain_file/x.toml", "MEMBER", "plain_file/x.toml"),
    12: (W + "/a..b.toml", "MEMBER", "a..b.toml"),
    13: (W + "/.hidden.toml", "MEMBER", ".hidden.toml"),
    14: (W + "/./policy/other.toml", "MEMBER", "policy/other.toml"),
    15: ("policy/rel.toml", "CED", "policy/rel.toml"),
    16: (
        W + "/locked/inner.toml",
        "REFUSE_INJECTED",
        ("lstat-error", "EIO", "locked/inner.toml", errno.EIO),
    ),
    17: (W + "/policy_dir", "CED_DIR", "policy_dir"),
    18: (W + "/dangle/x.toml", "REFUSE", ("symlink", None)),
    19: (W + "/maybe_dir", "MISSING_VS_EMPTY", "maybe_dir"),
    20: ((W + "/dirA", W + "/dirB"), "DIFFER", None),
    21: (W + "/pipe", "REFUSE", ("unsupported-kind", "fifo")),
    22: (W + "/sock", "REFUSE", ("unsupported-kind", "socket")),
    23: (
        ((W + "/coll_a", W + "/coll_a:tree"), (W + "/coll_b", W + "/coll_b:tree")),
        "PAIRS",
        None,
    ),
    24: (W + "/forge", "TWO_STATES", None),
    25: (W + "/devnode", "REFUSE_DEVICE", ("unsupported-kind", "char-device")),
    26: ((W + "/fa.toml", W + "/fb.toml"), "DIFFER", None),
    27: ((W + "/gone_a.toml", W + "/gone_b.toml"), "DIFFER", None),
    28: (
        W + "/locked2/inner.toml",
        "REFUSE_INJECTED",
        ("lstat-error", "EACCES", "locked2/inner.toml", errno.EACCES),
    ),
    # `_walk`'s OWN error handling, isolated: the error is on an ANCESTOR and the leaf stats cleanly.
    # Rows 16 and 28 inject at the leaf, where `_digest_of_member` re-checks independently — so a walk
    # that treated every error as absent was MASKED there and measured as failing no row at all.
    30: (
        W + "/locked3/inner.toml",
        "REFUSE_INJECTED",
        ("lstat-error", "EIO", "/locked3", errno.EIO),
    ),
    # Round-13 obligation: an absolute operand reaching the workspace by ANOTHER SPELLING. Lexical
    # containment is a spelling, not an inode, so it is recorded OUT OF SCOPE although samefile() is true.
    29: ("ALIAS:/outsider.toml", "OUT", None),
}


def _agg(ws: pathlib.Path, operand: str) -> tuple:
    return tuple(t._aggregate(ws, trunk_for(operand), BACKGROUND))


def _digest(ws: pathlib.Path, operand: str) -> str:
    return str(t._config_tree_digest(ws, trunk_for(operand), BACKGROUND))


def _kind_patches(kind: str, want: Any) -> list:
    """The fault or kind a REFUSE row injects through `_lstat` — carrying the filename, as a real error
    does, and a device kind, which needs root to create for real."""
    real_lstat = t._lstat
    if kind == "REFUSE_INJECTED":
        suffix, code = want[2], want[3]

        def injected(path: Any) -> Any:
            if str(path).endswith(suffix):
                raise OSError(code, os.strerror(code), str(path))
            return real_lstat(path)

        return [unittest.mock.patch.object(t, "_lstat", injected)]
    if kind == "REFUSE_DEVICE":

        def as_device(path: Any) -> Any:
            result = real_lstat(path)
            if pathlib.Path(path).name == "devnode":
                return os.stat_result((stat.S_IFCHR | 0o644, *tuple(result)[1:]))
            return result

        return [unittest.mock.patch.object(t, "_lstat", as_device)]
    return []


def _observe_refuse(
    ws: pathlib.Path, operand: str, kind: str, want: Any, reads: list
) -> bool:
    """`ConfigFreezeRefusal` with the row's operand, reason and (kind rows) subtype — and NO content read
    beyond the named background members. An incidental exception never counts."""
    reason, subtype = want[0], want[1]
    allowed = {str(ws / rel) for rel in BACKGROUND}
    patches = _kind_patches(kind, want)
    for patch in patches:
        patch.start()
    try:
        _agg(ws, operand)
    except t.ConfigFreezeRefusal as refusal:
        return (
            refusal.operand == operand
            and refusal.reason == reason
            and (subtype is None or refusal.subtype == subtype)
            and set(reads) <= allowed
        )
    else:
        return False
    finally:
        for patch in reversed(patches):
            patch.stop()


def _observe_ced(ws: pathlib.Path, operand: str, kind: str, want: Any) -> bool:
    if want not in _agg(ws, operand)[0]:
        return False
    target = (ws / want / "b.toml") if kind == "CED_DIR" else (ws / want)
    target.unlink(missing_ok=True)
    states = [_digest(ws, operand)]
    for text in ("first\n", "second\n"):
        target.write_text(text, encoding="utf-8")
        states.append(_digest(ws, operand))
    target.unlink()
    states.append(_digest(ws, operand))
    return states[0] != states[1] != states[2] != states[3]


def _observe_missing_vs_empty(ws: pathlib.Path, operand: str, want: Any) -> bool:
    directory = ws / want
    if directory.exists():
        directory.rmdir()
    absent = _digest(ws, operand)
    directory.mkdir()
    empty = _digest(ws, operand)
    directory.rmdir()
    return absent != empty


def _observe_two_states(ws: pathlib.Path, operand: str) -> bool:
    forge = ws / "forge"
    for f in forge.iterdir():
        f.unlink()
    (forge / "a").write_bytes(b"C1")
    (forge / "b").write_bytes(b"C2")
    first = _digest(ws, operand)
    for f in forge.iterdir():
        f.unlink()
    (forge / ("a:" + hashlib.sha256(b"C1").hexdigest() + "\nb")).write_bytes(b"C2")
    forged = _digest(ws, operand)
    for f in forge.iterdir():
        f.unlink()
    return first != forged


def _observe_membership(ws: pathlib.Path, operand: Any, kind: str, want: Any) -> bool:
    members, out = _agg(ws, operand)
    if kind == "ROOT":
        return "." not in members and not out
    if kind == "OUT":
        strays = (m for m in members if m not in BACKGROUND)
        return out == [operand] and not any(
            m.endswith(("outsider.toml", "x.toml")) for m in strays
        )
    return want in members


def _observe(ws: pathlib.Path, operand: Any, kind: str, want: Any, reads: list) -> bool:
    """One observer per row KIND, dispatched — the plan's observation rule for that kind, and no other."""
    observers = {
        "REFUSE": lambda: _observe_refuse(ws, operand, kind, want, reads),
        "ROOT": lambda: _observe_membership(ws, operand, kind, want),
        "OUT": lambda: _observe_membership(ws, operand, kind, want),
        "MEMBER": lambda: _observe_membership(ws, operand, kind, want),
        "CED": lambda: _observe_ced(ws, operand, kind, want),
        "MISSING_VS_EMPTY": lambda: _observe_missing_vs_empty(ws, operand, want),
        "DIFFER": lambda: _digest(ws, operand[0]) != _digest(ws, operand[1]),
        "PAIRS": lambda: all(_digest(ws, a) != _digest(ws, b) for a, b in operand),
        "TWO_STATES": lambda: _observe_two_states(ws, operand),
    }
    family = (
        "REFUSE"
        if kind.startswith("REFUSE")
        else ("CED" if kind.startswith("CED") else kind)
    )
    return bool(observers[family]())


def observe(ws: pathlib.Path, n: int) -> bool:
    """True when row `n` holds — observed exactly as the plan writes it, no stricter and no looser."""
    operand, kind, want = ROWS[n]
    if n == 29:
        operand = str(ws.parents[1] / "alias" / "ws" / "outsider.toml")
    reads: list = []
    real_read = t._read_member

    def spy(path: Any) -> bytes:
        reads.append(str(path))
        return bytes(real_read(path))

    with unittest.mock.patch.object(t, "_read_member", spy):
        try:
            return _observe(ws, operand, kind, want, reads)
        except (t.ConfigFreezeRefusal, OSError):
            return False


def baseline_holds(ws: pathlib.Path) -> bool:
    """The background alone must SUCCEED — or every REFUSE row would pass vacuously."""
    try:
        t._aggregate(ws, "", BACKGROUND)
    # ANY failure of the background alone is a baseline failure, whatever its type.
    except Exception:  # noqa: BLE001
        return False
    return True


# ---- the mutants: each patches EXACTLY ONE production helper ------------------------------------------


def _resolve_contained(alike):
    def contained(path, anchor):
        resolved = pathlib.Path(path).resolve()
        base = pathlib.Path(anchor).resolve() if alike else pathlib.Path(anchor)
        try:
            return (
                tuple(
                    pathlib.PurePosixPath(resolved.relative_to(base).as_posix()).parts
                )
                if resolved != base
                else ()
            )
        except ValueError:
            return None

    return contained


def _startswith_contained(path, anchor):
    text, base = str(path), str(anchor)
    if not text.startswith(base):
        return None
    rest = [p for p in text[len(base) :].split("/") if p not in ("", ".")]
    return tuple(rest)


def _normpath_join(real):
    def join(operand, anchor):
        return pathlib.PurePosixPath(os.path.normpath(str(real(operand, anchor))))

    return join


def _refuse_dot_join(real):
    def join(operand, anchor):
        raw = operand.replace(W, str(anchor))
        if "." in raw.split("/"):
            raise t.ConfigFreezeRefusal(operand, "dotdot")
        return real(operand, anchor)

    return join


def _walk_leaf_only(anchor, parts, operand):
    current = pathlib.Path(anchor)
    for index, part in enumerate(parts):
        current = current / part
        try:
            mode = t._lstat(current).st_mode
        except OSError as error:
            if error.errno in t._ABSENT_ERRNOS:
                return
            raise t.ConfigFreezeRefusal(
                operand, "lstat-error", t._errno_name(error)
            ) from error
        if index == len(parts) - 1 and stat.S_ISLNK(mode):
            raise t.ConfigFreezeRefusal(operand, "symlink")


def _walk_literal(anchor, parts, operand):
    current = pathlib.Path(anchor)
    for part in parts:
        current = current / part
        if stat.S_ISLNK(t._lstat(current).st_mode):
            raise t.ConfigFreezeRefusal(operand, "symlink")


def _walk_any_error_absent(anchor, parts, operand):
    current = pathlib.Path(anchor)
    for part in parts:
        current = current / part
        try:
            mode = t._lstat(current).st_mode
        except OSError:
            return
        if stat.S_ISLNK(mode):
            raise t.ConfigFreezeRefusal(operand, "symlink")


def _walk_propagating(anchor, parts, operand):
    current = pathlib.Path(anchor)
    for part in parts:
        current = current / part
        try:
            mode = t._lstat(current).st_mode
        except OSError as error:
            if error.errno in t._ABSENT_ERRNOS:
                return
            raise
        if stat.S_ISLNK(mode):
            raise t.ConfigFreezeRefusal(operand, "symlink")


def _walk_exists_first(real):
    def walk(anchor, parts, operand):
        if not pathlib.Path(
            anchor, *parts
        ).exists():  # follows links: a dangling one reads as missing
            return
        real(anchor, parts, operand)

    return walk


def _adjudicate_wrapping(rule):
    real = t._adjudicate

    def adjudicate(operand, anchor):
        verdict, rel = real(operand, anchor)
        if verdict == "member" and rule(anchor, rel):
            return ("root", None)  # silently not a member, and nothing recorded
        return verdict, rel

    return adjudicate


def _read_then_adjudicate(real):
    def adjudicate(operand, anchor):
        with suppress(OSError):
            t._read_member(pathlib.Path(str(t._join(operand, anchor))))
        return real(operand, anchor)

    return adjudicate


def _record_without_rel(kind):
    real = t._record

    def record(k, rel, digest):
        if k == kind:
            return json.dumps([k, digest], separators=(",", ":"))
        return real(k, rel, digest)

    return record


def _colon_record(kind, rel, digest):
    return (
        f"{rel}:missing"
        if kind == "missing"
        else (f"{rel}:tree:{digest}" if kind == "tree" else f"{rel}:{digest}")
    )


def _line_tree_entry(relative, digest):
    return f"{relative}:{digest}"


def _missing_as_empty_tree(real):
    def member(anchor, rel, operand):
        if (
            not (pathlib.Path(anchor) / str(rel)).exists()
            and not (pathlib.Path(anchor) / str(rel)).is_symlink()
        ):
            return t._record(
                "tree", rel, hashlib.sha256(b"").hexdigest()
            )  # the FULL empty-tree record
        return real(anchor, rel, operand)

    return member


def _blacklist_subtype(mode):
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    return None


def _reasonless_init(self, operand, reason, subtype=None):
    Exception.__init__(self, operand)
    self.operand, self.reason, self.subtype = operand, None, subtype


def _wrapping_read(real):
    def read(path):
        try:
            return real(path)
        except OSError as error:
            raise t.ConfigFreezeRefusal(str(path), "unsupported-kind") from error

    return read


def mutants() -> dict:
    """name -> list of (attribute, replacement) patches. ONE decision each; the one compound control is
    labelled and exempt (round 13)."""
    return {
        "resolve-alike (containment only)": [("_contained", _resolve_contained(True))],
        "resolve-one-side (containment only)": [
            ("_contained", _resolve_contained(False))
        ],
        "normpath before adjudication": [("_join", _normpath_join(t._join))],
        "leaf-only link test": [("_walk", _walk_leaf_only)],
        "startswith containment": [("_contained", _startswith_contained)],
        "no lstat error handling": [("_walk", _walk_literal)],
        "discard direct children": [
            ("_adjudicate", _adjudicate_wrapping(lambda a, rel: len(rel.parts) < 2))
        ],
        "ENOENT only": [("_ABSENT_ERRNOS", frozenset({errno.ENOENT}))],
        "EACCES as absent": [
            ("_ABSENT_ERRNOS", frozenset({errno.ENOENT, errno.ENOTDIR, errno.EACCES}))
        ],
        "`..` as a substring": [
            (
                "_refuse_dotdot",
                lambda parts, operand: (
                    (_ for _ in ()).throw(t.ConfigFreezeRefusal(operand, "dotdot"))
                    if any(".." in p for p in parts)
                    else None
                ),
            )
        ],
        "skip dotfiles": [
            (
                "_adjudicate",
                _adjudicate_wrapping(
                    lambda a, rel: any(p.startswith(".") for p in rel.parts)
                ),
            )
        ],
        "refuse a `.` component": [("_join", _refuse_dot_join(t._join))],
        # Patches the REGISTRY: `_REFERENCE_SHAPES` holds the extractor OBJECTS captured at import, so
        # patching the module attributes `_from_direct_config(s)` would leave this mutant a silent no-op —
        # which is exactly how it first measured as "fails no row".
        "drop operands lacking ${workspace}": [
            (
                "_REFERENCE_SHAPES",
                {
                    "direct_config": lambda d: [],
                    "direct_configs": lambda d: [],
                    "environment": t._from_environment,
                    "commands.run": t._from_commands,
                },
            )
        ],
        "any lstat error as absent": [("_walk", _walk_any_error_absent)],
        "propagate the lstat error": [("_walk", _walk_propagating)],
        "omit DERIVED directories": [
            (
                "_adjudicate",
                _adjudicate_wrapping(
                    lambda a, rel: (pathlib.Path(a) / str(rel)).is_dir()
                ),
            )
        ],
        "exists() before walking": [("_walk", _walk_exists_first(t._walk))],
        "missing as the empty-tree record": [
            ("_digest_of_member", _missing_as_empty_tree(t._digest_of_member))
        ],
        "directory record without rel": [("_record", _record_without_rel("tree"))],
        "file record without rel": [("_record", _record_without_rel("file"))],
        "missing record without rel": [("_record", _record_without_rel("missing"))],
        "read unsupported kinds": [("_unsupported_subtype", lambda mode: None)],
        "refuse only AFTER reading": [
            ("_unsupported_subtype", lambda mode: None),
            ("_read_member", _wrapping_read(t._read_member)),
        ],
        "blacklist FIFO and socket": [("_unsupported_subtype", _blacklist_subtype)],
        "read the operand before adjudicating": [
            ("_adjudicate", _read_then_adjudicate(t._adjudicate))
        ],
        "a refusal without its reason": [
            ("ConfigFreezeRefusal.__init__", _reasonless_init)
        ],
        "colon-joined member records": [("_record", _colon_record)],
        "colon-joined tree entries": [("_tree_entry", _line_tree_entry)],
        # HISTORICAL regression control, exempt from the one-decision rule (round 13): revision 10's
        # encoding changed BOTH levels at once; the two isolated operators above cover each decision.
        "revision 10's encoding (compound)": [
            ("_record", _colon_record),
            ("_tree_entry", _line_tree_entry),
        ],
    }


def _patchers(name: str) -> list:
    out: list[Any] = []
    for attribute, replacement in mutants()[name]:
        if attribute == "ConfigFreezeRefusal.__init__":
            out.append(
                unittest.mock.patch.object(
                    t.ConfigFreezeRefusal, "__init__", replacement
                )
            )
        elif isinstance(replacement, dict):
            out.append(
                unittest.mock.patch.dict(getattr(t, attribute), replacement, clear=True)
            )
        else:
            out.append(unittest.mock.patch.object(t, attribute, replacement))
    return out


def failing_rows(ws: pathlib.Path, name: str | None) -> tuple:
    """(baseline_holds, sorted failing rows) for the correct procedure (`name=None`) or one mutant."""
    patches = _patchers(name) if name else []
    for p in patches:
        p.start()
    try:
        ok = baseline_holds(ws)
        fails = [n for n in ROWS if n != 21 and not observe(ws, n)]
    finally:
        for p in reversed(patches):
            p.stop()
    if not _row_21_in_child(name):
        fails.append(21)
    return ok, sorted(fails)


def _row_21_in_child(name: str | None) -> bool:
    """Row 21 runs in a CHILD under a timeout: a fall-through to `read_bytes()` on a FIFO blocks forever,
    and in-process that would hang the suite instead of reddening it. A timeout is a FAILURE.
    """
    code = (
        "import sys, pathlib, tempfile; sys.path.insert(0, sys.argv[1]);"
        "import test_config_freeze_battery as b\n"
        "name = sys.argv[2] or None\n"
        "with tempfile.TemporaryDirectory() as tmp:\n"
        "    ws = b.build(b.symlinked_outer(pathlib.Path(tmp)))\n"
        "    patches = b._patchers(name) if name else []\n"
        "    [p.start() for p in patches]\n"
        "    print('OK' if b.observe(ws, 21) else 'FAIL')\n"
    )
    try:
        done = subprocess.run(  # noqa: PLW1510 — stdout is the oracle, not the exit status
            [
                sys.executable,
                "-c",
                code,
                str(pathlib.Path(__file__).parent),
                name or "",
            ],
            capture_output=True,
            text=True,
            timeout=10,  # a correct refusal is immediate; the margin is for a slow runner, not a slow refusal
        )
    except subprocess.TimeoutExpired:
        return False
    return done.stdout.strip() == "OK"


def _sock(ws: pathlib.Path) -> socket.socket:
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(ws / "sock"))
    return listener


def measure() -> dict:
    """{name-or-None: (baseline_holds, failing rows)} over a fresh fixture per implementation."""
    results = {}
    for name in [None, *mutants()]:
        with tempfile.TemporaryDirectory() as tmp:
            ws = build(symlinked_outer(pathlib.Path(tmp)))
            listener = _sock(ws)
            try:
                results[name] = failing_rows(ws, name)
            finally:
                listener.close()
    return results


# ---- the shipped oracle: MEASURED against the real code, never transcribed from the model ---------------
#
# Where these differ from the plan's original MODEL table, the cause was found rather than the set edited
# to match (§6 step 2a): the model's `resolve()` operators also skipped the walk, which made them impure
# (codex, r13) — the true containment-only operator fails 1-5, 18 and the alias row 29, and leaves the
# injected-error rows alone; the model's two `lstat` scopes ("the row's own walk" / "every member") are ONE
# decision here, because one `_walk` serves both sources, so there are 29 operators and it fails at the
# BASELINE; and row 30 was ADDED because a walk treating every error as absent was masked at the leaf by
# `_digest_of_member`'s independent re-check and measured as failing no row.
EXPECTED = {
    "resolve-alike (containment only)": (True, frozenset({1, 2, 3, 4, 5, 18, 29})),
    "resolve-one-side (containment only)": (
        True,
        frozenset(
            {
                1,
                2,
                3,
                4,
                5,
                6,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                30,
            }
        ),
    ),
    "normpath before adjudication": (True, frozenset({3, 4, 5})),
    "leaf-only link test": (True, frozenset({2, 18})),
    "startswith containment": (True, frozenset({7})),
    "no lstat error handling": (
        False,
        frozenset(
            {
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
            }
        ),
    ),
    "discard direct children": (
        True,
        frozenset({10, 12, 13, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27}),
    ),
    "ENOENT only": (True, frozenset({11})),
    "EACCES as absent": (True, frozenset({28})),
    "`..` as a substring": (True, frozenset({12})),
    "skip dotfiles": (True, frozenset({13})),
    "refuse a `.` component": (True, frozenset({6, 14})),
    "drop operands lacking ${workspace}": (True, frozenset({15})),
    "any lstat error as absent": (True, frozenset({30})),
    "propagate the lstat error": (True, frozenset({16, 28, 30})),
    "omit DERIVED directories": (True, frozenset({17, 20, 24})),
    "exists() before walking": (True, frozenset({18})),
    "missing as the empty-tree record": (True, frozenset({19})),
    "directory record without rel": (True, frozenset({20})),
    "file record without rel": (True, frozenset({26})),
    "missing record without rel": (True, frozenset({27})),
    "read unsupported kinds": (True, frozenset({21, 22, 25})),
    "refuse only AFTER reading": (True, frozenset({21, 22, 25})),
    "blacklist FIFO and socket": (True, frozenset({25})),
    "read the operand before adjudicating": (
        True,
        frozenset({1, 2, 3, 4, 5, 16, 18, 21, 22, 25, 28, 30}),
    ),
    "a refusal without its reason": (
        True,
        frozenset({1, 2, 3, 4, 5, 16, 18, 21, 22, 25, 28, 30}),
    ),
    "colon-joined member records": (True, frozenset({23})),
    "colon-joined tree entries": (True, frozenset({24})),
    "revision 10's encoding (compound)": (True, frozenset({23, 24})),
}

# The two operators that patch more than one helper. Each is one CONCEPTUAL decision implemented in two
# places, labelled rather than hidden (round 13 required the compound encoding control to be exempt).
COMPOUND = {
    "refuse only AFTER reading": "disabling the pre-read refusal AND adding a post-read one is one choice",
    "revision 10's encoding (compound)": "a HISTORICAL regression control; the two isolated operators cover each half",
}


class Cell8f_TheAdjudicationBatteryRunsAgainstTheRealCode(unittest.TestCase):
    """§6 step 2a: every mutant, applied to the REAL functions, fails EXACTLY its recorded rows."""

    @classmethod
    def setUpClass(cls):
        cls.results = measure()

    def test_the_correct_procedure_passes_the_baseline_and_every_row(self):
        self.assertEqual((True, []), self.results[None])

    def test_the_fixture_anchor_has_a_symlinked_ancestor_on_this_platform(self):
        """The discrimination between `resolve-alike` and `resolve-one-side` exists ONLY when an
        ancestor of the anchor is a link. Without this control, a fixture that lost its link would
        reproduce the Linux-only false oracle silently, on every platform."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = build(symlinked_outer(pathlib.Path(tmp)))
            self.assertNotEqual(
                ws, ws.resolve(), "the anchor must not be its own realpath"
            )
            self.assertTrue(
                any(p.is_symlink() for p in ws.parents), "no symlinked ancestor"
            )

    def test_every_mutant_fails_exactly_its_recorded_rows(self):
        """A mutant failing a DIFFERENT set means the model and the code diverged: find out why — do not
        edit EXPECTED to match."""
        self.assertEqual(
            set(EXPECTED),
            set(mutants()),
            "every operator needs a recorded set, and vice versa",
        )
        for name, (baseline, rows) in EXPECTED.items():
            with self.subTest(mutant=name):
                ok, fails = self.results[name]
                self.assertEqual((baseline, rows), (ok, frozenset(fails)))

    def test_no_mutant_fails_no_row(self):
        """A mutant failing NO row is a missing row — or a no-op operator, which is how the
        `${workspace}`-dropping mutant first measured, before it patched the registry it reads.
        """
        for name in mutants():
            with self.subTest(mutant=name):
                ok, fails = self.results[name]
                self.assertTrue(fails or not ok, f"{name} is caught by nothing")

    def test_every_operator_changes_exactly_one_decision_unless_labelled(self):
        for name, patches in mutants().items():
            with self.subTest(mutant=name):
                if name in COMPOUND:
                    self.assertGreater(len(patches), 1)
                else:
                    self.assertEqual(
                        1,
                        len(patches),
                        "an impure operator's failure set measures nothing",
                    )


if __name__ == "__main__":
    for key, (ok, fails) in measure().items():
        print(
            f"{(key or 'CORRECT'):42s} baseline={'ok' if ok else 'FAIL':4s} fails={fails}"
        )
