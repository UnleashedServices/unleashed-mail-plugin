#!/usr/bin/env bash
# Execute COREDEV-2617 §4.2a-P's LINUX-ARM primitives and print what they actually return.
#
# WHY THIS EXISTS
# §4.2a-P records a measured value for every primitive it states — except the Linux arms, which were
# written from documentation because the development machine is Darwin. Two independent plan reviewers
# reached the same verdict on that: §4.2a-S plus §4.2a-P is NOT sufficient to implement §4.2a on Linux,
# because P-2's Linux format, ACL-3's `getfacl` grammar, and P-4's behaviour under a POSIX default ACL
# are all unexecuted. A format written from documentation is what produced every defect P-2 has had:
# its first version returned decimal where the other arm returned octal, its second stripped the setuid
# bit, and its third measured the symlink instead of the target.
#
# So this script does not assert anything. It RUNS the primitives on a real Linux box and prints the
# outputs, and §4.2a-P records what it prints. Nothing here is a test that can pass or fail; it is a
# measurement whose result is transcribed into the plan by a human.
#
# Run it on the CI runner (see .github/workflows/plugin-ci.yml) or on any Linux host:
#     bash scripts/review/linux-primitive-probe.sh
#
# It writes only under a temporary directory it creates, and removes it on exit.
set -uo pipefail

printf '=== COREDEV-2617 §4.2a-P — Linux arm measurements ===\n'
printf 'uname -s   : %s\n' "$(/usr/bin/uname -s 2>&1)"
printf 'stat       : %s\n' "$(/usr/bin/stat --version 2>&1 | head -1)"
printf 'getfacl    : %s\n' "$(/usr/bin/getfacl --version 2>&1 | head -1)"
printf 'bash       : %s\n' "${BASH_VERSION:-unknown}"
printf 'zsh        : %s\n' "$(zsh --version 2>&1 || echo 'not installed')"
printf '\n'

W="$(mktemp -d)" || exit 1
trap 'rm -rf "$W"' EXIT INT TERM HUP
cd "$W" || exit 1

# ---------------------------------------------------------------- P-2, the Linux accessor
# The PROPERTY the plan requires: ONE lstat call returning the twelve mode bits as four octal digits,
# the size in bytes, and the owning uid — agreeing digit for digit with the zsh arm on every fixture.
mkdir -p d0700 d1700 d2700 && chmod 0700 d0700 && chmod 1700 d1700 && chmod 2700 d2700
: > f0600 && chmod 0600 f0600
: > f4600 && chmod 4600 f4600
ln -s d0700 link_to_dir
ln -s /nonexistent dangling

printf -- '--- P-2 Linux arm candidates (does any format give 12 bits, size and uid in ONE call?) ---\n'
for p in d0700 d1700 d2700 f0600 f4600 link_to_dir dangling; do
    a=$(/usr/bin/stat -c '%a %s %u' -- "$p" 2>&1)
    f=$(/usr/bin/stat -c '%f %s %u' -- "$p" 2>&1)
    printf '%-12s  -c %%a: %-18s  -c %%f(hex): %s\n' "$p" "$a" "$f"
done
printf '\nNOTE: `%%a` is documented as "access rights in octal"; whether it prints the setuid/setgid/sticky\n'
printf 'bits, and whether it zero-pads to four digits, is exactly what this probe exists to establish.\n'
printf 'If it does not, the plan must use `%%f` (hex st_mode) masked to 12 bits, or a second format.\n\n'

printf -- '--- P-2 lstat semantics (must NOT follow the link, to match zstat -L) ---\n'
printf 'link_to_dir  -c %%a %%s: %s   (a followed stat would report the DIRECTORY 700)\n' \
    "$(/usr/bin/stat -c '%a %s' -- link_to_dir 2>&1)"
# stat is run SEPARATELY and its status saved first: a `$?` passed as the next printf argument
# reports the status of the command BEFORE the printf, not of the stat inside `$(...)`, so a
# failing dangling-symlink stat — the exact behaviour this line exists to measure — would still
# print exit=0 and the Linux arm would be designed from wrong evidence (codex, PR #67).
_dg_out="$(/usr/bin/stat -c '%a %s' -- dangling 2>&1)"; _dg_rc=$?
printf 'dangling     -c %%a %%s: %s   exit=%s   (must SUCCEED; zstat without -L fails here)\n' \
    "$_dg_out" "$_dg_rc"
printf '\n'

# ---------------------------------------------------------------- P-4 under a POSIX default ACL
# The claim under test: `(umask 077; : > tmp)` yields 0600. A DEFAULT ACL on the parent supplies
# permissions umask does not mask, and ACL-3 ACCEPTS a store carrying only an unnamed default entry,
# so this combination is reachable on a store the design considers valid.
printf -- '--- P-4 under a POSIX default ACL (the case ACL-3 accepts) ---\n'
mkdir -p acldir && chmod 0700 acldir
if /usr/bin/setfacl -d -m group::r-- acldir 2>/dev/null; then
    ( umask 077; : > acldir/tmp )
    printf 'default:group::r-- set; (umask 077; : > tmp) yields mode %s\n' \
        "$(/usr/bin/stat -c '%a' -- acldir/tmp 2>&1)"
    printf 'getfacl of the parent:\n'; /usr/bin/getfacl -pc acldir 2>&1 | sed 's/^/  /'
    printf 'getfacl of the new file:\n'; /usr/bin/getfacl -pc acldir/tmp 2>&1 | sed 's/^/  /'
else
    printf 'setfacl unavailable or refused — P-4 under a default ACL REMAINS UNMEASURED\n'
fi
printf '\n'

# ---------------------------------------------------------------- ACL-3's getfacl grammar
# ACL-3 refuses IFF a named entry carries `w` AND the corresponding mask permits `w`. Both halves and
# the exact output shape are unexecuted; these four fixtures are the ones the rule distinguishes.
printf -- '--- ACL-3 grammar: the four fixtures the rule must tell apart ---\n'
mk() { mkdir -p "$1" && chmod 0700 "$1"; }
mk acl_none
mk acl_named_w_mask_w   && /usr/bin/setfacl -m u:daemon:rw- acl_named_w_mask_w 2>/dev/null
mk acl_named_w_mask_r   && /usr/bin/setfacl -m u:daemon:rw- acl_named_w_mask_r 2>/dev/null \
                        && /usr/bin/setfacl -m m::r-- acl_named_w_mask_r 2>/dev/null
mk acl_default_named_w  && /usr/bin/setfacl -d -m u:daemon:rw- acl_default_named_w 2>/dev/null
# The UNNAMED default classes. These are the cases ACL-3 got wrong twice: the mask does NOT apply to
# the `other` class at all, and a minimal default ACL may omit the mask entirely, so a rule that
# conditions either on a mask fails OPEN and every child a consumer creates inherits the grant.
mk acl_defgroup_nomask  && /usr/bin/setfacl -d -m g::rwx acl_defgroup_nomask 2>/dev/null
mk acl_defgroup_mask_w  && /usr/bin/setfacl -d -m g::rwx acl_defgroup_mask_w 2>/dev/null \
                        && /usr/bin/setfacl -d -m m::rwx acl_defgroup_mask_w 2>/dev/null
mk acl_defother_w       && /usr/bin/setfacl -d -m o::rwx acl_defother_w 2>/dev/null \
                        && /usr/bin/setfacl -d -m m::r-x acl_defother_w 2>/dev/null
# Does a child actually inherit the grant? This is the consequence the rule exists to prevent, so
# measure it rather than reasoning about it.
for d in acl_defgroup_nomask acl_defother_w; do
    ( umask 077; mkdir -p "$d/child" 2>/dev/null )
    printf 'child of %s -> mode %s\n' "$d" "$(/usr/bin/stat -c '%a' -- "$d/child" 2>&1)"
    /usr/bin/getfacl -pc "$d/child" 2>&1 | sed 's/^/    /'
done
for d in acl_none acl_named_w_mask_w acl_named_w_mask_r acl_default_named_w \
         acl_defgroup_nomask acl_defgroup_mask_w acl_defother_w; do
    printf '%s (ACL-3 verdict: %s)\n' "$d" \
        "$(case $d in
             acl_none) echo ACCEPT ;;
             acl_named_w_mask_w) echo REFUSE ;;
             acl_named_w_mask_r) echo 'ACCEPT — the mask conjunct is NOT satisfied' ;;
             acl_default_named_w) echo 'REFUSE — default: entries are checked like access entries' ;;
             acl_defgroup_nomask) echo 'REFUSE — unnamed owning-group default with NO mask; an absent mask masks nothing' ;;
             acl_defgroup_mask_w) echo 'REFUSE — unnamed owning-group default, mask permits w' ;;
             acl_defother_w) echo 'REFUSE UNCONDITIONALLY — the mask does not apply to the other class' ;;
           esac)"
    /usr/bin/getfacl -pc "$d" 2>&1 | sed 's/^/    /'
done
printf '\n'

printf -- '--- ACL-3: does getfacl emit any allow/deny token? (the forbidden gloss assumes it does) ---\n'
if /usr/bin/getfacl -pc acl_named_w_mask_w 2>/dev/null | grep -q 'allow\|deny'; then
    printf 'YES — the platform-independent gloss would find tokens here\n'
else
    printf 'NO — POSIX getfacl emits no allow/deny token, so a gloss-derived implementation finds\n'
    printf '     zero ACEs and refuses NOTHING on this platform. This is the fail-open ACL-1 forbids.\n'
fi
printf '\n=== end of measurements — transcribe these into §4.2a-P ===\n'
