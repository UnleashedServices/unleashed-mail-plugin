# COREDEV-2691 §1 — the auth-chain seam

**Status:** Planning, revision 9 · **Ticket:** COREDEV-2691 (High) · **Branch:** `feat/COREDEV-2691-auth-seam`

> **Gate history.** r1: codex `REQUEST_CHANGES`, agy `APPROVE_WITH_NOTES`, kimi `APPROVE_WITH_NOTES`.
> r2: both `REQUEST_CHANGES`. r3 (frozen `05cc76e`): both `REQUEST_CHANGES`. r4 (frozen `02a13b8`):
> agy `APPROVE_WITH_NOTES`, codex and kimi `REQUEST_CHANGES` — but both named the SAME two items and
> gave a smallest-change-to-approve list, which revision 5 applied. r5 (frozen `a9b8771`): agy and
> kimi `APPROVE_WITH_NOTES`, codex `REQUEST_CHANGES` on ONE remaining one-line defect. Revision 6
> is that line. r6 (frozen `cdf8b59`): agy `APPROVE_WITH_NOTES`; codex confirmed the seam correct
> after 22 further attacks per shell and found NO ninth defect, leaving one internal
> contradiction between §2 and §7.2, which revision 7 removed. r7 (frozen `67096c5`): codex
> `APPROVE`, agy `APPROVE_WITH_NOTES` — but the REPRODUCTION round on byte-identical input
> flipped codex to `REQUEST_CHANGES` on a fourth requirement-with-different-force defect that
> both approving runs had certified clean. Revision 8 fixes it. One approving round is not a
> gate pass, and this plan is now the third instance on this campaign proving that. r8 (frozen
> `1eccbe5`): agy `APPROVE_WITH_NOTES`, codex `REQUEST_CHANGES` on a FIFTH instance of the same
> class — §2's own observation mechanism erased the fork §5 and §7 require it to detect.
> Revision 9 splits it into two passes. Every claim below was re-measured in this worktree; where a reviewer and I
> disagreed, the measurement is shown.
>
> **Process note:** I edited §3 *while* r2 was reading, so codex's r2 verdict names the final hash and
> agy's targets the earlier bytes. That was my error — the plan is frozen for r3 and will not change
> until both verdicts are in.
>
> **A production defect fell out of this review and is now COREDEV-2761** (High): on Linux, publishing
> any base path containing `.`, `..` or `//` fails outright with a false diagnostic. See §5.

## 1. The problem, stated as a consequence

`_unleashed_auth_chain` refuses unconditionally on every non-Darwin platform. The gating `validate`
job is `ubuntu-latest`; the only macOS leg (`redactor-equivalence`) is push-to-main and not required.
So on **every pull request**, the reader's entry authentication, the publisher's value-validation
**refusal arms**, and the store's encoder locale guards are exercised by **no check that can fail**.

Two regressions that would merge green today:

* relaxing the reader's mode compare from twelve bits to nine lets a `chmod 4600` **setuid** entry
  authenticate;
* returning `C.UTF-8` to the encoder's accepted locale list makes one directory encode three
  different ways, destroying ENC-1 injectivity.

**REVISED (codex r2 #5):** revision 1 claimed "publisher value validation" generally. What this plan
can actually deliver on Linux is the **refusal** arms. The success arms are blocked by COREDEV-2761
and are named as out of scope in §6 rather than implied.

## 2. What must NOT be done, and the criterion that replaces it

Removing the fifteen class decorators wholesale is measurably wrong — forcing the platform gate to
refuse while leaving the Python `DARWIN` flag true gives `44` store failures and `119` mutant
failures, and the store suite's own decorator message records that this shipped once and went red.

But "do not narrow *any* decorator" (revision 1) is false: `test_e2_an_unpublishable_value_writes_nothing_at_all`
is refused by E2 value validation before any chain call.

**The criterion, and the evidence required for it (agy r2 #4, codex r2 #3).** A cell may move to the
ungated class only with a recorded matrix row:

| column | meaning |
|---|---|
| cell | the test id |
| paired mutant | the exact mutant row that must redden it |
| shells | which arms run, and why any is excluded |
| expected ordered calls | the full transcript, with duplicates |
| direct forks | absolute-path forks observed |
| disposition | move / keep gated, with the reason |

Evidence is produced for **both** the shipped and the mutant path, in **each shell that row
declares** — not unconditionally in both. §7.2 lets a cell be zsh-only where §5's forks force it,
and revision 6 still demanded evidence in both shells here, so an implementation could not
satisfy the two literally (codex r6). The declared set is the contract in both places:

**TWO SEPARATE PASSES, because one pass cannot do both jobs (codex, r8).** Revision 8 said to
replace `_unleashed_auth_chain` *and* `_u_stat` with sentinels and then read the `execve` trace —
but replacing `_u_stat` **erases the very fork the trace is supposed to detect**. Measured: bash's
shipped `_u_stat` forks `/usr/bin/stat -f`; with a sentinel in its place the fork is gone from the
trace, so the harness would have declared a bash ENT-1 cell movable when it is not. The observation
mechanism destroyed its own evidence.

1. **A sentinel pass** may replace both functions, and establishes the ordered call transcripts.
2. **A separate `strace -f` pass on Ubuntu keeps the build-under-test's REAL `_u_stat`** — only
   `_unleashed_auth_chain` stays seamed, or `_u_stat` is wrapped so it still delegates to the
   original. Function replacement cannot intercept an absolute-path fork, so this pass is the only
   thing that can see one.
3. A cell moves only when that independent real-`_u_stat` trace contains **no §5 NON-PORTABLE fork**
   for that declared shell, and the sentinel pass's transcripts **match the row's expected ordered
   calls**;
4. a **detector control** that must violate one of those expectations — otherwise the harness cannot
   fail and proves nothing.

**Why not "all traces empty" (codex, reproduction round).** Revision 7 said exactly that, and it
contradicted §5, which lists portable forks as reachable and blocking nothing. The consequence was
not cosmetic: `_u_euid` is an **ENT-1 clause** (`plugin-state-reader.sh:33`) and it forks
`/usr/bin/id -u` (`plugin-state-auth.sh:206`), so an empty-trace rule made **every ENT-1 cell
un-movable — the plan's headline deliverable, forbidden by the plan's own evidence rule.** Two
approving arms had already certified this section clean; a reproduction run on byte-identical input
found it. The rule is now about *which* forks appear, not whether any do.

### The candidate set, MEASURED

Revision 3 declined to name rows, and both r3 arms called that an un-auditable deferral. It is now
measured. Method: mutate the platform gate to refuse (`Darwin` → `LinuxSm`, line-count preserving)
on a real Darwin box, run each suite verbose, and record which cells still pass. A cell that passes
while the chain refuses is a **candidate**; a cell that fails depends on a chain that authenticates
and stays gated.

**`test_plugin_state_store.py` — 16 candidates**

```
test_control_accepting_any_non_space_line_as_the_stat_line_fails_open
test_every_ace_shape                     test_every_answer_shape
test_control_a_blacklist_of_mutating_rights_fails_open
test_control_a_positional_verb_parser_fails_open_on_an_inherited_ace
test_the_eight_fixtures_the_rule_distinguishes
test_del_byte_is_emitted_unchanged       test_injective_over_the_adversarial_corpus
test_keys_are_byte_identical_across_both_shells
test_lc_all_is_restored_in_both_entry_states
test_output_alphabet_is_0x20_to_0x7f_and_never_upper_case
test_a_failed_name_max_probe_refuses_the_publish
test_budget_boundary_is_exact            test_getconf_failure_refuses_rather_than_meaning_unlimited
test_e2_an_unpublishable_value_writes_nothing_at_all
test_a_group_writable_ancestor_refuses
```

**`test_plugin_state_mutants.py` — 16 candidates**: the E2 unpublishable-value cell (PUB-9), the
`HOME`-empty resolution cell, ENC-2 (fork-free key derivation), row 85 (NFC/NFD), row 93
(byte-identical keys), row 188b, and rows 156, 157, 158, 166, 167, 170, 173, 174, 175, 176.

This **independently confirms the ticket's "16 rows"** — eleven pure shell-semantics rows plus 85,
93 and the encoder/publish cells — which revision 3 correctly refused to assert without evidence.

### Two traps this measurement does NOT clear

1. **Vacuous passes, and there are at least two.** Under LINUX-SIM *everything* refuses, so a cell
   asserting a refusal can pass for the wrong reason. Both were confirmed by running them with a
   HEALTHY fixture in the mutated tree, where they should have passed *and did not need to*:
   * `test_a_group_writable_ancestor_refuses` — home at `0700`, i.e. no group-writable ancestor at
     all, still yields `refused` in both shells (agy and kimi, independently).
   * `test_a_failed_name_max_probe_refuses_the_publish` — with a **working** probe, still `failed`
     and nothing created, in both shells (kimi). Revision 4 named only the first suspect; the trap
     is broader than one cell.
   Passing under LINUX-SIM makes a cell a **candidate, not a decision** — each needs the §2 detector
   control proving it fails when its own guard is removed.
2. **Per-method granularity is not per-row.** The mutants suite reports zero methods `ok` when read
   naively because a single failing `subTest` fails the whole method; the sixteen above are whole
   methods that pass. Any future claim about an individual *row* inside a multi-row method needs
   per-row evidence, which this measurement does not provide.

Row 85 (NFC/NFD) additionally needs re-verification on a real runner before it moves — it asserts a
normalization-insensitive-volume property that a Linux filesystem may not share.

## 3. The seam — third spelling, and why the first two failed

`run_shell` sources the libraries then appends the body, so a body-level redefinition overrides the
shipped function for every later call, including calls from inside library functions. Measured with
the platform gate mutated to refuse (`Darwin` → `LinuxSm`, line-count preserving): shipped chain
`refuses`, redefined chain `ok`, in both bash 3.2.57 and zsh 5.9. codex reproduced this independently
against the real `_unleashed_create_store` (`rc=0 seam_calls=2`).

The seam must be **recording and fail-closed** (codex r1 #4): an unconditional `return 0` lets a
caller that *stops calling the guard* pass.

**Three spellings were drafted and executed. The first two are wrong:**

| spelling | bash 3.2 | zsh 5.9 | verdict |
|---|---|---|---|
| `case "$1" in $_SEAM_ALLOWED)`, `\|`-separated | refuses everything | refuses everything | `\|` is literal in an expanded variable |
| `for a in $_SEAM_ALLOWED_LIST; [ "$1" = "$a" ]` | works | refuses everything | zsh does not word-split unquoted parameters |
| newline-delimited membership | **false ALLOW** | **false ALLOW** | a single argument `/a␤/b` matches two separate entries |

The third was mine, "verified" in revision 2 — against paths *I* chose, not against the input class
this suite actually exercises. **Embedded-newline values are explicitly in scope**, so the collision
is reachable, not theoretical. Measured: `/a␤/b` returns ALLOW in both shells.

**The form this plan adopts (codex r2 #1), measured correct in both shells:**

```sh
_unleashed_auth_chain() {
    { [ "$#" -eq 1 ] && [ -n "$1" ]; } || return 1     # arity AND non-empty
    [ -n "${_SEAM_CALLS:-}" ] || return 1              # an UNSET log aborts under set -u
    printf '%s\0' "$1" >> "$_SEAM_CALLS" || return 1   # a recording that FAILED is not a pass
    [ "$1" = "${_SEAM_A1:-}" ] && return 0             # STRING equality, not pattern matching
    [ "$1" = "${_SEAM_A2:-}" ] && return 0
    [ "$1" = "${_SEAM_A3:-}" ] && return 0
    return 1
}
```

**`case` had to go — the fifth defect, and the sixth.** Revision 4 used quoted `case` alternatives.
Two independent problems, one from each arm, both measured here:

* **`nocasematch` (codex r4 #1).** `case` does *pattern matching*, and bash's inherited
  `shopt -s nocasematch` makes it case-INSENSITIVE: an allowlist of `/Case/Sensitive` then allows
  `/case/sensitive`. Measured ALLOW in bash with the option set, refuse in zsh. This is not
  hypothetical for this repo — the encoder already saves, clears and restores `nocasematch`
  precisely because it is treated as adversarial inherited state.
* **`set -u` (kimi r4 #2).** An unset `_SEAM_A2` does **not** quietly expand to empty under `set -u`;
  it aborts the shell (`unbound variable`, rc=127). Fail-closed in effect but a loud abort rather
  than a refusal — and this suite has `set -eu` sourcing conventions.

`[ "$1" = "${_SEAM_An:-}" ]` fixes both at once: `[ = ]` is string equality, so no globbing option
can reach it, and `:-` makes an unset slot an empty string rather than an error. Measured in both
shells: wrong case refuses, exact matches, unset slots are inert under `set -u`.

**An eighth defect, and the same shape as the sixth (codex r5).** The `-n "$1"` and `${_SEAM_An:-}`
guards fixed unset *allowlist slots* under `set -u` — and left the log variable itself unguarded, so
an unset `_SEAM_CALLS` still aborted the shell instead of refusing. Measured under `set -eu`: bash
`unbound variable`, zsh `parameter not set`, both killing the process before the cell could observe
anything; with `[ -n "${_SEAM_CALLS:-}" ] || return 1` both return `call_rc=1` and survive.

Fixing one instance of a class and leaving its sibling is the defect this campaign has hit more than
any other. It happened here, inside the fix for that very class.

**Eight defects across six revisions of a ten-line function.** Every one was found by EXECUTING it
against inputs the *suite* uses rather than inputs I chose — none by reading. That is the
transferable lesson, and it is why this section carries its measurements inline.

**The `-n` guard is not decoration (agy r3 #1, codex r3 #3 — found independently).** An unset
`_SEAM_A2`/`_SEAM_A3` expands to the empty string, so `_unleashed_auth_chain ""` matches an unset
slot and returns 0. That is exactly the mutant shape the seam exists to catch — a caller passing an
uninitialised path variable. Measured in both shells: without `-n`, empty ALLOWs; with it, empty
refuses while a declared path still authenticates. **This is the fourth defect found in the seam
spelling across four revisions**; each earlier one was also "verified" before the next round broke
it, which is why the spelling now carries its measurement inline.

* **Quoted** alternatives, so a glob or newline in `$1` is compared literally.
* **NUL-framed** log, so one call with an embedded newline is distinguishable from two calls —
  `printf '%s\n'` cannot make that distinction.
* **Checked** redirect: measured, the unchecked form returns `0` while failing to record
  (`_SEAM_CALLS=/dev/null/nope`), so a cell could assert against a transcript that was never written.

**Assertions are ordered transcripts with multiplicity (codex r2 #4).** A healthy full-reader cell
calls the chain for the store, then the store again as the entry's parent, then the target. Comparing
the *set* `{store, target}` is unchanged when either store call is deleted, so a set comparison does
not prove what §3 exists to prove. Cells compare the exact ordered NUL-separated transcript.

**The allowlist must include ancestors (agy r2 #2).** Library functions authenticate ancestors before
targets — `_pb_anc`, `_UNLEASHED_NEAREST`, `_so_s`, the entry's parent. A cell allowing only its
target fails at the first ancestor, for a reason unrelated to its assertion. Each cell declares its
full expected ancestor set, and the declared set *is* the assertion.

## 4. Fixture requirements

**A correction carried from r1:** `_unleashed_key` **assigns** `_UNLEASHED_KEY`; it does not print.
`base.$(_unleashed_key "<value>")` yields `base.` — measured. Use `_unleashed_key "$v"` then
`base.$_UNLEASHED_KEY`.

True preconditions for a legitimate entry, each verified by a probe that refused without it:

1. Name is `base.$_UNLEASHED_KEY` after calling `_unleashed_key "<value>"`.
2. Value is an **existing directory** — `[ -d "$_ae_line" ]` was the last command before `return 1`
   in a `set -x` trace, and refused three early probes.
3. Entry mode exactly **`0600`** (`0644` refuses — measured).
4. Entry content is the value **with a trailing newline** (omitting it refuses — measured).
5. Regular file, not a symlink, owned by the effective uid.
6. A working numeric `_u_euid`; for zsh cells, `zsh/stat` and `zsh/system` must load.
7. `LC_ALL` explicitly controlled. A cell relying on `C.UTF-8` mutant behaviour must **prove that
   locale exists on the runner** first.
8. For **full-reader** cells only, the store is a non-symlink, euid-owned `0700` directory.

Under a fail-closed seam the intermediate `.claude` modes matter only for paths a cell allows;
keeping them `0700` is fixture fidelity, not a precondition (codex r1 #5).

Every cell asserts its own fixture: the legitimate entry **authenticates** in the same run in which
the hostile one is refused.

## 5. Platform surface — five forks, not one

| site | fork | reachable via | portable? |
|---|---|---|---|
| `plugin-state-auth.sh:163` | `/usr/bin/stat -f '%p %z %u %i'` | `_u_stat`, **bash arm only** | zsh arm is portable |
| `plugin-state-auth.sh:523` | `/usr/bin/stat -f '%p %z %u %i %N'` | `_u_chain_prefetch` | no |
| `plugin-state-publisher.sh:245-246` | `/usr/bin/stat -f '%d %i'` | E2b identity probe, **both shells** | no |
| `plugin-state-auth.sh:469`, `:560` | `/bin/ls -lde` | `_u_acl_enumerate`, prefetch | no — `-e` is BSD-only |
| `plugin-state-auth.sh:225` | `/usr/bin/dsmemberutil` | `_u_identity_uuid_probe` | no — macOS-only binary |

Rows 4 and 5 were missed by revisions 1 and 2 (agy r2 #3). They sit behind the chain, so the seam
covers them for seamed cells — but any cell reaching them *without* the seam is Darwin-only, and the
§2 matrix must record that. kimi additionally established that `dsmemberutil` is **unreachable under
the seam at all**, because `_u_principal` is only called by the stubbed chain — so row 5 constrains
only un-seamed cells.

**These five are the NON-PORTABLE forks (codex r3 #4).** Other absolute-path forks are reachable and
are *portable*, so they block nothing — but they belong in the matrix's "direct forks" column so a
reader can tell "checked, fine" from "not checked":

| site | fork | portable? |
|---|---|---|
| `plugin-state-auth.sh:205` | `/usr/bin/id -u` (`_u_euid`) | yes — POSIX flag |
| `plugin-state-auth.sh:196` | `/usr/bin/id -un` (`_u_principal`) | yes — POSIX flag |
| `plugin-state-auth.sh:182` | `/usr/bin/uname -s` (`_u_platform`) | yes — POSIX flag |
| `plugin-state-store.sh:177` | `/usr/bin/getconf NAME_MAX` | yes — POSIX |

agy r3 #3 listed these as inventory gaps; they are gaps in the *column*, not blockers. Verified: each
uses POSIX flags, unlike `stat -f` (BSD format vs GNU file-system) and `ls -e` (BSD-only).

**Row 3 is a production defect, now COREDEV-2761.** Under GNU coreutils `-f` means *file-system*
information, so the probe fails, both variables are empty, and the publisher refuses with "the
plugin-data base's spelling and its normalised form name different directories" — which is false; the
probe simply could not run. Measured: `gstat -f '%d %i' -- /tmp` → rc=1. **On Linux, publishing any
base path containing `.`, `..` or `//` fails.**

**REVISED (codex r2 #2):** excluding "normalisation-success cells" is not sufficient. The same probe
is reached by **mutant** paths of retained cells — row 184 removes the folded-root refusal and expects
a poison entry, but on GNU `stat` it stops at the fork before reaching its oracle. Those mutants are
excluded too, and named in the §2 matrix as blocked-by-COREDEV-2761 rather than silently skipped.

## 6. Scope

**In scope**

* A `SeamedChain` mixin: the §3 seam, ordered-transcript assertions, and the §4 fixture builder.
* An **ungated** class covering, under the seam: reader ENT-1 clauses; publisher E2 **refusal** arms
  (relative path and embedded newline ONLY — see the exclusions below); encoder locale guards.
* Each cell paired with the mutant that must redden it, with its shells stated.
* Cells passing the §2 criterion moved out of Darwin-gated classes, each with its matrix row.

**Explicitly OUT of scope**

* Publisher **normalisation-success** cells on Linux, and the retained mutants that reach the same
  fork — blocked by COREDEV-2761.
* **The folded-root refusal arm, and row 184 with it (codex r3 #2).** Revision 3 kept the refusal in
  scope while excluding the mutant that must redden it — an internal inconsistency, since every cell
  requires a reddening mutant. Row 184 deletes the folded-value guard and then reaches the same
  incompatible identity probe before producing its poison-entry oracle, so on GNU `stat` shipped and
  mutant both stop at `failed` and the cell cannot discriminate. Both stay Darwin-gated.

  **Revision 4 added this exclusion and then left the arm in the in-scope list** — the same defect
  codex raised against revision 3, surviving verbatim into the next revision because I wrote the
  exclusion without deleting the inclusion. Both arms caught it again. "Value normalising to `/`" IS
  the folded-root arm (`plugin-state-publisher.sh:187` is the only such refusal, and row 184's mutant
  deletes exactly the block containing it), so it is now removed from §6's in-scope list rather than
  contradicted two bullets later.
* **Trailing-slash refusal**, for the same reason (kimi r4 #1). No mutant row deletes the
  spelling-level guard, and a guard-deletion mutant for `/a/` folds to `/a`, differs from the
  spelling, and therefore reaches the COREDEV-2761 fork — shipped and mutant both end `failed` with
  nothing written, which does not discriminate on Linux. It may return to scope only when paired
  with a row-109-shaped mutant (derive-then-refuse), which discriminates without reaching the fold.
* Row 181's one-directory/one-entry invariant, which stays Darwin-gated; PR CI still cannot catch
  deletion of the lexical fold. Named here so the gap is visible rather than implied.
* The portable path-identity accessor itself — that is COREDEV-2761's fix.
* Every COREDEV-2760 item. Mixing them repeats PR #78's failure mode, where one PR carried guards,
  fixes and a release and took thirteen review rounds. **This change does one thing.**
* The Linux ACL carve-out; the platform gate is unchanged.

## 7. Verification

1. Every new cell has a paired mutant that reddens it — line-count preserving, restored with
   `shutil.copy2` so the **mode** survives, confirmed with `git diff --summary`.
2. **Executed-shell assertions, reconciled with zsh-only cells (agy r2 #6).** Revision 2 contradicted
   itself: §5 makes some cells zsh-only while §7 demanded "no arm skipped". The rule is: each cell
   **declares** its shell set, and CI asserts the *declared* set ran — not that every cell ran in both.
   A cell silently losing an arm still fails, which is what the assertion is for.
3. Green **unchanged on Darwin**; this adds coverage and alters no existing outcome.
4. CI's `validate` job (ubuntu) shows the new class **running**, with the executed count asserted.
5. Every moved cell ships its §2 matrix row, including the `strace` evidence and the detector control.
6. The full local gate (`~/.claude/handoffs/gate.sh`) with the exit code propagated —
   `bash gate.sh > log 2>&1; rc=$?`, never through `tee`, which returned tee's status over a RED gate
   during the v2.8.2 cut.

## 8. Risks

* **The seam proves the caller, not the chain.** Everything inside the chain — component symlink
  refusal, ancestor mode and ownership, principal handling, ACL evaluation, prefetch — stays
  Darwin-only. The Darwin-gated classes are not weakened.
* **A seam that is too generous hides what it tests.** This was revision 1's real defect, and the
  spelling was wrong twice more after that. The adopted form fails closed on arity, on an unrecorded
  call, and on any undeclared path.
* **I verified the seam against inputs I chose.** Twice. The suite's own input classes — embedded
  newlines, globs, spaces — are the set to verify against, and they are now the ones used.
* **zsh-only cells abandon the arm macOS actually runs (kimi).** Restricting a cell to zsh to dodge
  `_u_stat`'s bash fork leaves ENT-2b's bash arm — the `/dev/fd/9` inode binding and bounded
  `read -u 9` at `plugin-state-reader.sh:107-111` — covered only by the push-to-main macOS leg. The
  hooks in production run bash. Every zsh-only cell must say so at the cell, and the matrix records
  it, so this is a stated trade rather than an accident.
* **Scope shrank under review.** Revision 1 promised Linux coverage that §5 shows is unreachable.
  Cutting it and filing COREDEV-2761 is the honest outcome; promising it would have been worse.
