# COREDEV-2691 §1 — the auth-chain seam

**Status:** Planning, revision 3 · **Ticket:** COREDEV-2691 (High) · **Branch:** `feat/COREDEV-2691-auth-seam`

> **Gate history.** r1: codex `REQUEST_CHANGES`, agy `APPROVE_WITH_NOTES`. r2: both `REQUEST_CHANGES`.
> Revision 3 answers r2. Every claim below was re-measured in this worktree; where a reviewer and I
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

Evidence is produced by, for **both** the shipped and the mutant path, in **both** shells:

1. replacing `_unleashed_auth_chain` and `_u_stat` with NUL-recording sentinels;
2. capturing `execve` with `strace -f` on Ubuntu — **function replacement cannot intercept an
   absolute-path fork** such as `/usr/bin/stat`, so a shell-level sentinel alone is not evidence;
3. requiring all traces to be empty for a "moves" disposition;
4. a **detector control** that deliberately moves the cell's early return later and must produce a
   non-empty trace — otherwise the harness cannot fail and proves nothing.

The plan commits to the criterion and the matrix. It does **not** assert a count: revision 1's "16
rows" was carried from the ticket and is unaudited (codex r2 #3). Row 85 (NFC/NFD) additionally
needs re-verification on a real runner before it moves.

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
    [ "$#" -eq 1 ] || return 1                        # wrong arity is a defect, not a pass
    printf '%s\0' "$1" >> "$_SEAM_CALLS" || return 1  # a recording that FAILED is not a pass
    case "$1" in
        "$_SEAM_A1"|"$_SEAM_A2"|"$_SEAM_A3") return 0 ;;   # exact, QUOTED alternatives
        *) return 1 ;;
    esac
}
```

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
§2 matrix must record that.

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
  (relative path, trailing slash, embedded newline, value normalising to `/`); encoder locale guards.
* Each cell paired with the mutant that must redden it, with its shells stated.
* Cells passing the §2 criterion moved out of Darwin-gated classes, each with its matrix row.

**Explicitly OUT of scope**

* Publisher **normalisation-success** cells on Linux, and the retained mutants that reach the same
  fork — blocked by COREDEV-2761.
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
* **Scope shrank under review.** Revision 1 promised Linux coverage that §5 shows is unreachable.
  Cutting it and filing COREDEV-2761 is the honest outcome; promising it would have been worse.
