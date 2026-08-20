#!/usr/bin/env bash
# One implementation of "did anything in this checkout change while the reviewer ran".
#
# WHY THIS IS SHARED AND NOT COPIED (PR #63 recheck, P1/P2). The COREDEV-2607 detector — a reviewer in
# agent mode that IMPLEMENTS the plan instead of reviewing it — exists in three places: the agy
# preflight and both isolation harnesses. Each fingerprinted with `git status --porcelain` alone, which
# reports ONE LINE PER PATH (` M file`): editing an ALREADY-DIRTY tracked file leaves that line
# byte-identical, so the before/after compared equal while the bytes changed.
#
# That was found and fixed in the preflight first, as a local shell function. The two harnesses — where
# the detector is gate-bearing and its failure VOIDS the round — kept the status-only comparison, which
# is the same "a rule that lives in one script is a rule the next entrypoint will not have" failure this
# repo keeps recording. The rule lives here now, and all three source it.
#
# Pairing the status with `git diff HEAD` folds the actual content of every tracked change into the
# fingerprint. A created or removed path still moves a status line; the diff covers the case the status
# line cannot see. Untracked files are the residual: `??` announces one, but a second edit to an
# already-untracked file is invisible to both halves. The harnesses close that separately, by verifying
# the round's BASIS files (plan, prompt) against the digests recorded before launch.

# Print the content-aware fingerprint of the checkout rooted at $1.
# THE DEFAULT UNTRACKED MODE, DELIBERATELY — this function fingerprints the LIVE checkout.
#
# Git collapses an untracked directory to a single `?? dir/` line, which hides a file created beneath
# one; `--untracked-files=all` expands it, and that IS the right answer for the disposable review
# checkout, where the harnesses use it (PR #63 recheck, P2). It is the wrong answer here: the allocator
# writes its own per-run files — the reserved leaf, `.captureid`, the sidecars — into the transcript
# state tree BETWEEN this function's before and after calls, and when that tree sits inside the
# repository (`XDG_STATE_HOME` under the checkout, which the harness fixtures use and a developer may
# too) every one of them appears as a new line and VOIDS a clean round. Reproduced: six harness tests
# failed with `GATE FAILED — the reviewer MUTATED the working tree` naming a `.captureid` the harness
# itself had just created.
#
# RESIDUAL, stated rather than traded away: a reviewer writing inside an ALREADY-untracked directory of
# the live checkout is not seen here. The `git diff HEAD` half below covers every tracked change, the
# disposable checkout — where the reviewer actually runs — is compared with `-uall`, and the round's
# basis files are content-verified against their recorded digests. A guard that fails every honest
# round is one that gets switched off, which is the worse failure.
# A FAILED PROBE IS NOT A CLEAN TREE — the LIVE-checkout half of the same finding (PR #63 recheck, P1).
# Both commands suppressed their status, so a shell-capable reviewer that deleted or corrupted the live
# checkout's `.git` through an absolute path made BOTH fail: the fingerprint became the bare record
# separator, identical to the one taken before, and the comparison found no mutation. Reproduced by the
# reviewer. The disposable-checkout probe was fixed for exactly this one commit earlier and this one
# was not — the sibling-sweep failure this campaign keeps repeating.
#
# Returns non-zero when either probe fails; callers treat that as a void round, never as a clean tree.
tree_fingerprint() {
    # HEAD FIRST. `status --porcelain` and `diff HEAD` are both EMPTY before and after a clean commit
    # made during the review — the working tree matches the (new) HEAD — so an author who edited and
    # committed while the arms ran left the fingerprint byte-identical, and the round certified a review
    # of a repository that had changed under it, contrary to the "an author commit voids the round"
    # rule the harnesses print. The resolved commit is part of the checkout's identity (codex, PR #67
    # pass 8 — reproduced).
    _u_git -C "$1" rev-parse HEAD 2>/dev/null || return 1
    _u_git -C "$1" status --porcelain 2>/dev/null || return 1
    printf '\036\n'   # a record separator so the halves cannot alias across the boundary
    # THE CONTENT OF EVERY TRACKED FILE, HASHED — NOT `git diff HEAD`. Both `status` and `diff` consult
    # the live INDEX, and a reviewer that can address the live checkout can switch that index off for a
    # file: `git -C <live> update-index --assume-unchanged f` then edit `f` leaves status and diff EMPTY
    # while HEAD stands still — the fingerprint was identical before and after and the round certified
    # a modified real worktree (codex, PR #67 pass 10 — reproduced). `git ls-files` still LISTS such a
    # file (the flag hides changes, not membership), so its working-tree bytes are hashed directly:
    # type, mode, size and sha256 per path (a deleted or replaced file records as such), paths JSON-
    # encoded as in disposable_fingerprint. This is strictly stronger than `diff HEAD` (which it
    # replaces): a content, mode or type change to any tracked file moves it, index flags or not.
    _tracked_content_fingerprint "$1" || return 1
    printf '\036\n'
    # THE EXCLUSION METADATA A REVIEWER COULD USE TO HIDE AN UNTRACKED FILE FROM `status`: the repo's
    # own `.git/info/exclude` and `.git/config` (`core.excludesFile`) — tracked `.gitignore` files are
    # already covered above, and the configured `core.excludesFile` and every file that contributes config
    # — including the global and system ones — are recorded by `_u_git_metadata_fingerprint` below.
    _u_git_metadata_fingerprint "$1" || return 1
    printf '\036\n'
    _u_acl_fingerprint "$1" || return 1
    # THE ONE GITIGNORED PATH THAT IS GATE-BEARING. `docs/planning/.verdicts/` holds the Combined-verdict
    # artefact the plan gate READS, and it is ignored at the repo root — so a reviewer with a shell that
    # wrote a forged approval there was invisible to both halves above (adversarial verification, PR #67
    # pass 6). Only the synthesis step writes it, after both arms have landed, so during a round it must
    # not change. Fingerprinted by CONTENT through the same helper the disposable checkout uses. Other
    # ignored paths (`__pycache__`, the transcript state tree when it sits inside the checkout) are NOT
    # included: the harness's own python and allocator write there between the before and after calls,
    # and a guard that voids every honest round is one that gets switched off. That residual is stated.
    # The ROOT of `.verdicts` is recorded by its OWN lstat — type, mode, and a link's target — and not
    # only its children: `[ -d ]` follows a symlink, and a reviewer that replaced the directory with a
    # symlink to an identical copy left the walk unchanged, while every no-follow verdict operation
    # afterwards refuses the link and the gate stays unusable until repaired (codex, PR #67 pass 10;
    # with this repository's own `.verdicts/` ignore rule the swap also surfaced as `?? docs/` in the
    # status half, but the fingerprint must not depend on the spelling of an ignore rule).
    if [ -e "$1/docs/planning/.verdicts" ] || [ -L "$1/docs/planning/.verdicts" ]; then
        printf '\036\n'
        _u_lstat_record "$1/docs/planning/.verdicts" || return 1
        if [ -d "$1/docs/planning/.verdicts" ]; then
            disposable_fingerprint "$1/docs/planning/.verdicts" || return 1
        fi
    fi
}

# One line per TRACKED path (git ls-files -z): type, mode, size, sha256 (or link target / MISSING),
# JSON-encoded path. Fails closed if the listing or any read fails.
_tracked_content_fingerprint() {
    # python runs the listing itself (checked), so a failed `git ls-files` FAILS this probe rather than
    # yielding an empty list that reads as "no tracked files".
    python3 - "$1" <<'PY' || return 1
import hashlib, json, os, stat, subprocess, sys
root = sys.argv[1]
# THE UNION of index-tracked and HEAD-tracked paths: `ls-files` derives membership from the mutable
# INDEX, so a path staged for deletion (`git rm --cached`) and ignored was omitted while status stayed
# `D  path` before and after a reviewer rewrote its working-tree file (codex, PR #67 pass 11 —
# reproduced). HEAD's tree cannot be edited without moving HEAD, which the first line records.
GIT = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", root]
r = subprocess.run(GIT + ["ls-files", "-z"], capture_output=True)
if r.returncode != 0:
    sys.exit(1)
names = set(x for x in r.stdout.split(b"\0") if x)
# THE STAGED OBJECT IDS, not merely index MEMBERSHIP. `ls-files` names the paths; it does not say what
# bytes are staged for them. In a checkout that starts `MM f`, a reviewer can swap the staged blob with
# `git update-index --cacheinfo` and leave the working tree alone: status prints the same two letters,
# every leaf digest above is unchanged, and the fingerprint was byte-identical while `git show :f`
# returned different bytes — silently corrupting what the maintainer commits next (codex, PR #67 pass 15
# — reproduced). `--stage` prints `<mode> <oid> <stage>\t<path>`, which is exactly that missing half.
rs = subprocess.run(GIT + ["ls-files", "--stage", "-z"], capture_output=True)
if rs.returncode != 0:
    sys.exit(1)
staged = sorted(os.fsdecode(x) for x in rs.stdout.split(b"\0") if x)
r2 = subprocess.run(GIT + ["ls-tree", "-r", "-z", "--name-only", "HEAD"], capture_output=True)
if r2.returncode == 0:                      # an unborn HEAD has no tree; that is not a failure
    names.update(x for x in r2.stdout.split(b"\0") if x)
# THE ANCESTOR DIRECTORIES OF EVERY TRACKED PATH, BY LSTAT — mode and type. `git status` says nothing
# about a directory's own metadata, and hashing only the leaves left `chmod 777 scripts` invisible: the
# round certified a live tree whose formerly protected directory was now world-writable (codex, PR #67
# pass 13 — reproduced). Directories are recorded once each, before the leaves.
# THE CHECKOUT ROOT ITSELF IS ONE OF THEM: the walk above stopped where `dirname` became empty, so
# the root was never recorded and `chmod 777 <checkout>` passed every gate (codex, PR #67 pass 14 —
# reproduced). It is recorded as ".".
# EVERY RECORD CARRIES THE OBJECT'S IDENTITY — device, inode, link count. Mode+size+content let a
# tracked file be replaced by a HARD LINK to an external file with identical bytes: status stayed
# clean and the record was unchanged, while a later write through either name silently changed the
# other (codex, PR #67 pass 14 — reproduced). Identity is stable across a clean round — nothing the
# harness does re-creates a tracked object — and it is not content, so it changes exactly when the
# object was swapped.
def ident(st):
    return "%d:%d:%d" % (st.st_dev, st.st_ino, st.st_nlink)
dirs = set(["."])
for raw in names:
    p = os.path.dirname(os.fsdecode(raw))
    while p:
        dirs.add(p); p = os.path.dirname(p)
out = ["INDEX %s" % s for s in staged]
for rel in sorted(dirs):
    full = os.path.join(root, rel)
    try:
        st = os.lstat(full)
    except FileNotFoundError:
        out.append("MISSING-DIR %s" % json.dumps(rel)); continue
    mode = "%04o" % stat.S_IMODE(st.st_mode)
    if stat.S_ISLNK(st.st_mode):
        out.append("DL %s %s %s -> %s" % (mode, ident(st), json.dumps(rel), json.dumps(os.readlink(full))))
    else:
        out.append("D %s %s %s" % (mode, ident(st), json.dumps(rel)))
for raw in sorted(names):
    rel = os.fsdecode(raw)
    full = os.path.join(root, rel)
    try:
        st = os.lstat(full)
    except FileNotFoundError:
        out.append("MISSING %s" % json.dumps(rel)); continue
    mode = "%04o" % stat.S_IMODE(st.st_mode)
    if stat.S_ISLNK(st.st_mode):
        out.append("L %s %s %s -> %s" % (mode, ident(st), json.dumps(rel), json.dumps(os.readlink(full))))
    elif stat.S_ISREG(st.st_mode):
        h = hashlib.sha256()
        with open(full, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        out.append("F %s %d %s %s %s" % (mode, st.st_size, h.hexdigest(), ident(st), json.dumps(rel)))
    else:
        out.append("O %s %s %s" % (mode, ident(st), json.dumps(rel)))
sys.stdout.write("\n".join(out) + ("\n" if out else ""))
PY
}

# `<label> <record>` for a path that exists, `<label> ABSENT` otherwise; a present-but-unreadable file fails.
# THE RECORD IS TAKEN BY LSTAT — type, mode, identity, and a link's target — before any content is hashed:
# hashing through the name followed a symlink, so `.git/config` replaced by a symlink to an external copy
# with identical bytes produced the same digest, and Git then read its settings (`core.hooksPath` among
# them) from outside the checkout (codex, PR #67 pass 14 — reproduced). A regular file records its
# content digest; a link records its target and the digest of what the target resolves to, so a link
# whose external target is later edited is caught as well.
# ONE RECORD PER PATH, in ONE python invocation: `<path> <record>` for a path that exists, `<path>
# ABSENT` otherwise, and a present-but-unreadable regular file FAILS (a void round, never a clean tree).
# `--dir <path>` additionally records every entry of that directory (sorted, not descended) — the shape
# the hooks directories need. THE RECORD IS TAKEN BY LSTAT before any content is hashed: hashing through
# the name followed a symlink, so `.git/config` replaced by a symlink to an external byte-identical copy
# produced the same digest while Git read `core.hooksPath` and friends from outside the checkout (codex,
# PR #67 pass 14 — reproduced). A link records its target AND the digest of what the target resolves to,
# so an edit to the external target is caught as well.
_u_hash_if_present() {
    python3 - "$@" <<'PY'
import hashlib, json, os, stat, sys
def digest(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
def rec(p):
    try:
        st = os.lstat(p)
    except OSError:
        return "ABSENT"
    mode = "%04o" % stat.S_IMODE(st.st_mode)
    ident = "%d:%d:%d" % (st.st_dev, st.st_ino, st.st_nlink)
    if stat.S_ISLNK(st.st_mode):
        try:
            d = digest(p)
        except OSError:
            d = "UNREADABLE-TARGET"
        return "L %s %s -> %s %s" % (mode, ident, json.dumps(os.readlink(p)), d)
    if stat.S_ISREG(st.st_mode):
        try:
            return "F %s %s %d %s" % (mode, ident, st.st_size, digest(p))
        except OSError:
            return None                      # present but unreadable -> fail closed
    return "O %s %s" % (mode, ident)
args = sys.argv[1:]
targets, i, seen = [], 0, set()
while i < len(args):
    if args[i] == "--dir":
        targets.append((args[i + 1], True)); i += 2
    else:
        targets.append((args[i], False)); i += 1
out = []
for p, expand in targets:
    key = (os.path.realpath(p), expand)
    if key in seen:                          # a configured hooksPath that IS the default one
        continue
    seen.add(key)
    r = rec(p)
    if r is None:
        sys.exit(1)
    out.append("%s %s" % (p, r))
    if not expand:
        continue
    try:
        names = sorted(os.listdir(p))
    except OSError:
        continue                             # absent or unreadable: the record above already says so
    for n in names:
        r = rec(os.path.join(p, n))
        if r is None:
            sys.exit(1)
        out.append("%s %s" % (os.path.join(p, n), r))
sys.stdout.write("\n".join(out) + ("\n" if out else ""))
PY
}

# EVERY GIT PROBE OF THE LIVE CHECKOUT GOES THROUGH THIS. `--no-optional-locks` so a probe never writes
# the live index, and `core.fsmonitor=false` so a reviewer-planted fsmonitor hook is not EXECUTED by our
# own AFTER take — it would run as us, inside the tree being measured (codex sweep, PR #67 pass 14).
_u_git() {
    git --no-optional-locks -c core.fsmonitor=false "$@"
}

# THE GIT METADATA THAT GOVERNS THIS CHECKOUT, resolved THROUGH GIT rather than by assuming `$1/.git` is
# a directory. In a LINKED WORKTREE — which is where this campaign's own reviews run — `.git` is a FILE
# and the real directories are elsewhere, so the two literal paths this used to hash were recorded
# ABSENT and the protection was inert exactly where it was needed: `git -C <live> config core.hooksPath`
# passed every gate (codex sweep, PR #67 pass 14 — reproduced). Recorded: the `.git` entry itself, the
# per-worktree gitdir and the common dir, `config` (+ `config.worktree`), `info/exclude`,
# `info/attributes`, `objects/info/alternates`, `HEAD` (a retarget to another branch at the same sha
# moves no other record), and every entry of the hooks directories that will actually run — a
# `pre-commit` planted there needs no config change and fires on the maintainer's next commit.
# RESIDUAL, stated: `packed-refs` and `logs/` are NOT recorded (an auto-gc repack would void an honest
# round). The global and system config files ARE recorded, via `--show-origin`.
_u_git_metadata_fingerprint() {
    _ugm_root="$1"
    _ugm_git="$(_u_git -C "$_ugm_root" rev-parse --absolute-git-dir 2>/dev/null)" || return 1
    [ -n "$_ugm_git" ] || return 1
    _ugm_common="$(_u_git -C "$_ugm_root" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || _ugm_common=""
    if [ -z "$_ugm_common" ]; then           # git < 2.31 has no --path-format
        _ugm_common="$(_u_git -C "$_ugm_root" rev-parse --git-common-dir 2>/dev/null)" || _ugm_common=""
        case "$_ugm_common" in ''|/*) : ;; *) _ugm_common="$_ugm_root/$_ugm_common" ;; esac
    fi
    [ -n "$_ugm_common" ] || _ugm_common="$_ugm_git"
    # EVERY CONFIG-REFERENCED PATH IS READ WITH `--path`, which is how GIT reads it. A plain `--get`
    # returns the unexpanded text, so the supported tilde form `~/hooks` was fingerprinted as
    # `<root>/~/hooks` — a directory that does not exist — while git executed `$HOME/hooks/pre-commit`:
    # editing that hook left both fingerprints identical (codex, PR #67 pass 15 — reproduced). A
    # relative value stays relative to the working tree, which is what git does with it.
    _ugm_hooks="$(_u_git -C "$_ugm_root" config --path --get core.hooksPath 2>/dev/null)" || _ugm_hooks=""
    case "$_ugm_hooks" in ''|/*) : ;; *) _ugm_hooks="$_ugm_root/$_ugm_hooks" ;; esac
    # THE FILES CONFIG POINTS AT, not just the config text that names them. `core.excludesFile` hides an
    # untracked file from `status`, so a reviewer who adds one line to an external excludes file and
    # creates the matching file leaves status empty and the tracked-content half untouched; recording
    # the config text alone did not see the exclusion change (codex, PR #67 pass 15 — reproduced on a
    # filesystem where a directory's link count does not track its entries; on APFS the root record
    # happened to move, which is an accident of the filesystem, not a protection).
    _ugm_excl="$(_u_git -C "$_ugm_root" config --path --get core.excludesFile 2>/dev/null)" || _ugm_excl=""
    case "$_ugm_excl" in ''|/*) : ;; *) _ugm_excl="$_ugm_root/$_ugm_excl" ;; esac
    _ugm_attr="$(_u_git -C "$_ugm_root" config --path --get core.attributesFile 2>/dev/null)" || _ugm_attr=""
    case "$_ugm_attr" in ''|/*) : ;; *) _ugm_attr="$_ugm_root/$_ugm_attr" ;; esac
    set -- "$_ugm_root/.git" "$_ugm_git" "$_ugm_common" \
           "$_ugm_common/config" "$_ugm_git/config.worktree" \
           "$_ugm_common/info/exclude" "$_ugm_common/info/attributes" \
           "$_ugm_common/objects/info/alternates" "$_ugm_git/HEAD" \
           --dir "$_ugm_common/hooks"
    [ -n "$_ugm_hooks" ] && set -- "$@" --dir "$_ugm_hooks"
    [ -n "$_ugm_excl" ] && set -- "$@" "$_ugm_excl"
    [ -n "$_ugm_attr" ] && set -- "$@" "$_ugm_attr"
    # ...AND EVERY FILE THAT CONTRIBUTES CONFIG AT ALL. `include.path` / `includeIf` pull settings from
    # another file — measured: an included file setting `core.hooksPath` wins, and the repository's own
    # `config` shows only the `include.path` line — and the global and system files are equally able to
    # set `core.hooksPath` for this checkout. `--show-origin` names them all, which closes the
    # "a file outside the repository is not covered" residual this function used to carry.
    _ugm_origins="$(_u_git -C "$_ugm_root" config --list --show-origin --name-only -z 2>/dev/null | tr '\0' '\n' | sed -n 's/^file://p' | LC_ALL=C sort -u)" || _ugm_origins=""
    # `--show-origin` PRINTS THE REPOSITORY'S OWN FILES RELATIVE. Measured in a plain checkout: the
    # repo config comes back as `.git/config`, and a relatively-included file as `.git/../inc.cfg`.
    # Fed verbatim, those resolve against the RECORDER's cwd, so this block recorded `.git/config
    # ABSENT` — the one file it exists to cover — and a relative `include.path` was not covered at all
    # (found by the test author while pinning this block, not by a reviewer). Relative origins are
    # therefore resolved against the checkout root, which is what git resolved them against.
    # RESIDUAL, stated: the global (`~/.gitconfig`) and system config files ARE hashed, because a
    # reviewer runs at the same uid and `core.hooksPath` set there governs this checkout — the cost is
    # that an unrelated edit to them mid-round voids the round, and an unreadable one fails it closed.
    if [ -n "$_ugm_origins" ]; then
        while IFS= read -r _ugm_o; do
            [ -n "$_ugm_o" ] || continue
            case "$_ugm_o" in /*) : ;; *) _ugm_o="$_ugm_root/$_ugm_o" ;; esac
            set -- "$@" "$_ugm_o"
        done <<ORIGINS
$_ugm_origins
ORIGINS
    fi
    _u_hash_if_present "$@" || return 1
}

# THE ACLs. macOS keeps them OUTSIDE st_mode, so `chmod +a 'everyone allow write,delete,add_file'` on a
# tracked file, a tracked directory or the checkout root left every record above byte-identical (codex
# sweep, PR #67 pass 14 — reproduced), re-opening for ACEs the write-access class pass 13 closed for
# mode bits. `find -acl` names exactly the paths that carry one — normally NONE, so this is one exec —
# and `ls -lde` renders each ACE. Where the probe does not exist (Linux CI) the line says so rather than
# claiming a clean answer.
_u_acl_fingerprint() {
    if [ ! -x /usr/bin/find ] || [ "$(/usr/bin/uname -s 2>/dev/null)" != Darwin ]; then
        printf 'ACL-PROBE unsupported\n'
        return 0
    fi
    # `|| :` — the callers run under `set -o pipefail` and `find` exits non-zero on any unreadable
    # directory it walked past; a probe that voids an honest round is a probe that gets switched off.
    { /usr/bin/find "$1" -acl -print 2>/dev/null || :; } | LC_ALL=C sort | while IFS= read -r _uacl_p; do
        printf 'ACL %s\n' "$_uacl_p"
        /bin/ls -lde -- "$_uacl_p" 2>/dev/null | sed -n 's/^[[:space:]]*\([0-9][0-9]*: .*\)$/ACE \1/p'
    done
    printf 'ACL-PROBE done\n'
}

# The lstat record of ONE path (not descended): type, mode, and a link's target, JSON-encoded.
_u_lstat_record() {
    python3 - "$1" <<'PY' || return 1
import json, os, stat, sys
p = sys.argv[1]; st = os.lstat(p); mode = "%04o" % stat.S_IMODE(st.st_mode)
if stat.S_ISLNK(st.st_mode):
    print("ROOT L %s %s -> %s" % (mode, json.dumps(p), json.dumps(os.readlink(p))))
elif stat.S_ISDIR(st.st_mode):
    print("ROOT D %s %s" % (mode, json.dumps(p)))
else:
    print("ROOT O %s %s" % (mode, json.dumps(p)))
PY
}

# Build a PRIVATE disposable checkout of commit $2 of the repository at $1, at path $3 (must not exist).
#
# NOT `git worktree add`. A linked worktree's `.git` is a FILE pointing INTO THE MAINTAINER'S REAL
# REPOSITORY, and every git operation a shell-capable reviewer runs inside it lands there: `git config
# core.hooksPath` from the disposable checkout wrote the LIVE repo's `.git/config`, so the maintainer's
# next real commit would have run a reviewer-planted hook; `git commit`/`git stash`/`update-ref` wrote
# refs and objects into the shared database (the "dangling commits survive" note the agy harness carried
# was this same class); and repointing the `.git` file made every later `git status` answer about a
# DIFFERENT repository (adversarial verification, PR #67 pass 6 — reproduced). A `git clone --local`
# would HARDLINK the object files, and a hardlinked object rewritten in the clone is rewritten in the
# source; `--shared` publishes the source's path in `objects/info/alternates`. So: `git init`, then FETCH
# the one commit over the local transport (upload-pack on the source is read-only; a detached source
# HEAD is advertised, so the harnesses' `git rev-parse HEAD` is always fetchable — measured), then a
# detached checkout. No remote, no alternates, no hardlinks; `FETCH_HEAD` — the one file that names the
# source path — is removed. The reviewer's git is fully usable and fully private. Measured: 3.8 MB and
# under a second for this repository.
# THE GIT ENVIRONMENT IS SANITISED AT THE SHARED BOUNDARY, not in one caller.
# `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_SYSTEM=/dev/null` do NOT remove `GIT_CONFIG_COUNT`,
# whose indexed `GIT_CONFIG_KEY_n`/`VALUE_n` pairs arrive as command-line config and outrank both.
# That is not merely a data leak: with `url.<ext::cmd>.insteadOf` plus `protocol.ext.allow=always`
# it is CODE EXECUTION through the same URL-resolution transport `fetch` uses (codex, PR #69
# round 5, reproduced — output from an injected `/bin/echo` appeared in git's protocol error).
# Only the kimi harness cleared the namespace, while all three call this helper, so agy and codex
# were still exposed. Sanitising here covers every caller and cannot be forgotten by the next one.
_tf_sanitize_git_env() {
    while IFS='=' read -r _tf_v _; do
        case "$_tf_v" in GIT_*) unset "$_tf_v" ;; esac
    done <<TFEOF
$(env)
TFEOF
    unset _tf_v
}

disposable_checkout() {
    _tf_sanitize_git_env
    _dc_repo="$1"; _dc_sha="$2"; _dc_dest="$3"
    [ ! -e "$_dc_dest" ] || return 1
    # HOOKS ARE DISABLED EXPLICITLY for every command here. `checkout` fires `post-checkout`, and
    # this runs BEFORE the caller captures its baseline, so a hook firing inside the private tree is
    # mutation the baseline would then record as pristine. The caller clears the whole `GIT_*`
    # namespace, which is the primary defence; `-c core.hooksPath=/dev/null` is the second, because
    # `core.hooksPath` also reaches git through config FILES this harness does not own
    # (codex, PR #69 round 3 — reproduced via GIT_CONFIG_COUNT).
    # THE CHECKOUT IS BUILT WITH NO INHERITED EXECUTABLE CONFIGURATION.
    # `-c core.hooksPath=/dev/null` disables HOOKS and nothing else, and round 4 reproduced a
    # smudge FILTER executing during checkout with hooks already disabled: global and system
    # config still define `filter.*`, `core.attributesFile`, `insteadOf` and friends, and a filter
    # runs a shell command over the bytes on their way into the tree. Measured on this machine,
    # `filter.lfs.process` and three siblings were reachable from ~/.gitconfig with hooksPath
    # disabled, and empty once GIT_CONFIG_GLOBAL/SYSTEM point at /dev/null.
    #   * GIT_CONFIG_GLOBAL/GIT_CONFIG_SYSTEM=/dev/null removes both files, so no filter, attribute
    #     or url-rewrite definition survives to be triggered by a `.gitattributes` in the commit;
    #   * `--template=` gives `init` an EMPTY template, so no hooks or config are copied in;
    #   * core.attributesFile and core.hooksPath are pinned as well, belt and braces.
    _dc_gitenv="GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null"
    _dc_git="env $_dc_gitenv git -c core.hooksPath=/dev/null -c core.attributesFile=/dev/null"
    $_dc_git init -q --template= -- "$_dc_dest" >/dev/null 2>&1 || return 1
    $_dc_git -C "$_dc_dest" fetch -q --no-tags -- "$_dc_repo" "$_dc_sha" >/dev/null 2>&1 || return 1
    $_dc_git -C "$_dc_dest" checkout -q --detach FETCH_HEAD >/dev/null 2>&1 || return 1
    rm -f "$_dc_dest/.git/FETCH_HEAD"
    [ "$(git -C "$_dc_dest" rev-parse HEAD 2>/dev/null)" = "$_dc_sha" ] || return 1
}

# Content fingerprint of a DISPOSABLE checkout rooted at $1 — every path beneath it except `.git`,
# with its type, permission bits, size and content hash (the target, for a symlink), one line per
# entry, sorted. Compared for EQUALITY around the reviewer's run; a `diff` of the two outputs is the
# report.
#
# NEVER `git status`. Status is METADATA THE REVIEWER CONTROLS: after editing a file a reviewer can
# `git commit` it (status clean), `git update-index --assume-unchanged`/`--skip-worktree` it (hidden),
# drop a nested self-ignoring `.gitignore` or an `info/exclude` rule beside new files (not `??`), or
# `git stash` (working files revert; the edits live on in the reviewer's private clone). Every one of
# those passed the previous status-based probe (adversarial verification, PR #67 pass 6 — reproduced),
# and a probe that FAILED (`.git` deleted) had already been turned into an empty baseline by `|| true`
# in one harness (codex, PR #67). Hashing the bytes of what is actually in the tree is not something the
# reviewer can talk git out of. `.git` is recorded as an ENTRY — its type, and its bytes when it is a
# gitfile — but NOT descended: git's own bookkeeping (the `index` stat cache on every `git status` the
# reviewer runs) would void every honest round, and in a PRIVATE checkout nothing under `.git` can reach
# the maintainer; while a reviewer that DELETES or REPOINTS `.git` has still written inside the checkout
# and is caught. RESIDUAL, stated: an edit that is REVERTED before the run ends (edit; `git checkout
# --`) leaves no trace here; this detects edits that SURVIVE the run.
# THE SERIALISATION IS INJECTIVE: path and link-target fields are JSON-encoded (pure ASCII, quoted,
# escaped). A line-oriented record with a RAW path was not — a reviewer that deleted `b` and renamed
# `a` to `a<newline><b's whole record>` produced byte-identical output, and the before/after gate in
# all three harnesses accepted the altered checkout (codex, PR #67 pass 9 — reproduced).
disposable_fingerprint() {
    python3 - "$1" <<'PY' || return 1
import hashlib, json, os, stat, sys
root = sys.argv[1]
if not os.path.isdir(root):
    sys.exit(1)
lines = []
for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
    if dirpath == root:
        # `.git` is listed as an entry below but never descended.
        dirnames[:] = [d for d in dirnames if d != ".git"]
        if ".git" not in filenames and os.path.lexists(os.path.join(root, ".git")):
            filenames = filenames + [".git"]
    dirnames.sort()
    for name in sorted(dirnames + filenames):
        full = os.path.join(dirpath, name)
        rel = os.path.relpath(full, root)
        st = os.lstat(full)
        mode = "%04o" % stat.S_IMODE(st.st_mode)
        q = json.dumps(rel)                       # ensure_ascii: one unambiguous, newline-free token
        if stat.S_ISLNK(st.st_mode):
            lines.append("L %s %s -> %s" % (mode, q, json.dumps(os.readlink(full))))
        elif stat.S_ISDIR(st.st_mode):
            lines.append("D %s %s" % (mode, q))
        elif stat.S_ISREG(st.st_mode):
            h = hashlib.sha256()
            with open(full, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 16), b""):
                    h.update(chunk)
            lines.append("F %s %d %s %s" % (mode, st.st_size, h.hexdigest(), q))
        else:
            lines.append("O %s %s" % (mode, q))
sys.stdout.write("\n".join(lines) + ("\n" if lines else ""))
PY
}

# Print the human-readable summary of what changed between two fingerprints, to stderr.
# $1 = checkout root, $2 = the status portion captured before the run.
tree_fingerprint_report() {
    _tf_after_status="$(_u_git -C "$1" status --porcelain 2>/dev/null)"
    # Only what CHANGED at the STATUS level, for a readable summary — printing the whole status (or the
    # whole diff) buries the one new line. A content-only edit to an already-dirty file shows no new
    # status line, so say so rather than printing nothing.
    _tf_new="$(printf '%s\n' "$_tf_after_status" | grep -vxF -- "$2" || true)"
    if [ -n "$_tf_new" ]; then
        printf '%s\n' "$_tf_new" >&2
    else
        # No new status line: either the CONTENT of an already-modified file changed, or — the case a
        # clean commit mid-round produces — HEAD itself moved. Say which, from the fingerprint's own
        # first line ($3 = the HEAD recorded before the run, when the caller has it).
        if [ -n "${3:-}" ] && [ "$(_u_git -C "$1" rev-parse HEAD 2>/dev/null)" != "$3" ]; then
            printf '(no new status line — HEAD moved from %s to %s: a commit was made during the review)\n' \
                "$3" "$(_u_git -C "$1" rev-parse HEAD 2>/dev/null)" >&2
        else
            printf '(no new status line — the CONTENT of an already-modified tracked file changed)\n' >&2
        fi
    fi
}
