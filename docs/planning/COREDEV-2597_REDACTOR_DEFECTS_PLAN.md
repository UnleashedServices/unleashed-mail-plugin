# Redactor Defects Plan

**Status:** Planning — round 3, awaiting re-gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29 (round 3)
**Ticket:** `COREDEV-2597` — `hook_redact_pii` corrupts ordinary prose and truncates on invalid UTF-8
**Epic:** `COREDEV-2582` — Opus 5 readiness and autonomous end-to-end mode
**Branch:** `feat/COREDEV-2597-redactor-defects`
**Target version:** `2.6.1` → **`2.6.2`** (patch: bug fixes, no asset-count change).
**Sequencing:** 2.6.1 is **already released** (COREDEV-2602, commit `04f906d`) — neither this plan nor
`CI_WORKFLOW_HARDENING_PLAN.md` can take it. Both branch from 2.6.1 and are independent: **whichever
merges first is `2.6.2`; the second rebases and becomes `2.6.3`.** Do not hard-code the number in a
commit message or a test until the merge order is known.
**Blocks:** `DECISION_JOURNAL_PLAN.md` (`COREDEV-2585`) — split out of it on the **independent**
recommendation of both plan reviewers, which also resolves that plan's scope contradiction ("no change
to the reviewer capture pipeline" vs. modifying `capture.py`'s redactor). §4.5 records the drift that
split left behind.
**Also sequenced against:** `COREDEV-2604` modifies `capture.py` too. Land this first — it is a
contained regex/locale fix; 2604 restructures the failure-reporting path.

---

## 1. Context

`hook_redact_pii` is the plugin's redaction helper. It is **not** a PII scrubber — it is a
secret-shape scrubber, and that limitation is owned by `COREDEV-2585`'s design, not by this ticket.
This ticket fixes three defects in what it *does* claim to do.

These are **live bugs, not future risk.** `mcp/review-synthesizer/capture.py:159-161` already runs
model-authored `finding` / `evidence` / `fix` prose through the same patterns on every reviewer capture,
so reviewer evidence is being corrupted today. It is live on the shell side too: a realistic denial
reason `{"reason":"denied for ~alice and ~alice/.ssh/id_rsa and ~500ms budget"}` through
`scripts/permission-denied-log.sh` writes `~[redacted] budget` into the log right now.

All three were found by executing the shipped function, and both plan reviewers reproduced them
independently.

## 2. Scope

**In:** three defects in `scripts/lib/hook-io.sh::hook_redact_pii` (two of which are mirrored in
`mcp/review-synthesizer/capture.py::redact_pii`), tests on both sides, and the shared parity fixture
that keeps the two implementations from re-diverging (§4.4).

**Out:** making the redactor an actual PII scrubber. It provably leaves personal names, phone numbers,
SSNs, postal addresses, `ghp_` PATs, `AKIA…` keys and `password=…` untouched. That limitation is
`COREDEV-2585`'s to design around (pointers, not prose) and **must not** be quietly widened here —
broadening the pattern set is how §4.1's corruption class was introduced in the first place.

**Out, and accepted deliberately (§4.2's residual):** a bare `~alice` with no following path stops
being redacted. It is regex-indistinguishable from `~ten` / `~half` / `~Copyable` — the same shape —
so any rule that catches it necessarily re-creates the corruption class this ticket exists to remove.
This is the same class of miss §2 already concedes for plain personal names. §4.2 pins it with a test
so it is a reviewed decision rather than an accident.

**Out, narrowed in round 2:** the `_EMAIL` `@2x` retina-filename exemption at `capture.py:51-53` is
not ported to the shell side. *(Round 1 said "the two Python-only exemptions". The `_TILDE`
`~Copyable`/`~Escapable` exemption is **dissolved** by §4.2's strict rule rather than excluded — it
becomes dead code and is deleted. Only the `@2x` half remains out of scope.)* The honest reason is
**caller impact, not expressibility**: §4.6's caller audit shows no shell caller carries an asset
filename into a consumed artifact. Do **not** repeat the claim that POSIX ERE cannot express it — that
is false, and a two-pass protect/restore in one `sed -E` reproduces the Python semantics byte-for-byte.
`scripts/lib/hook-io.sh:221-224`'s comment must be corrected on both counts when this lands.

**Ownership — settled in round 2.** §4.4's parity fixture **stays in this ticket.** Both plan
reviewers concurred, and `CI_WORKFLOW_HARDENING_PLAN.md` §2 already disclaims the redactor explicitly:
`COREDEV-2600` covers the base-path copies, the round scanners and the `mtime` idioms **only**.
*(Round 1 said the opposite here, contradicting both this plan's own §4.4 and the sibling plan. That
sentence is deleted; see §10.)*

## 3. Guiding principle

> **A redactor that damages correct text is worse than one that misses a secret.** A missed secret is a
> known, bounded gap that the design works around; corrupted text is silent data loss in the artifact
> the reader is relying on. Every fix below narrows a pattern or fixes a locale bug — **none widens what
> is matched.**

Corollary: every fix needs a **positive control**. A test that only proves `task-oriented` survives
would also pass if redaction were disabled entirely — which is the exact failure mode the reviewers
flagged when this was still part of 2585.

**Second corollary, added in round 2 and load-bearing: a mutation proof must reject *plausible wrong
implementations*, not only reverts.** Round 1's proofs failed this. Two independently plausible
implementations of §4.1 pass every test round 1 enumerated while leaving a real secret unredacted. A
test set that only survives `git revert` is not a proof.

---

## 4. Findings, fixes, and proofs

### 4.1 — The `sk-`/`pk_` rule has no leading boundary and fires mid-word (High)

**Root cause.** `scripts/lib/hook-io.sh:234`:

```sh
-e 's#(sk-|pk_)[A-Za-z0-9._-]{8,}#[redacted-secret]#g' \
```

There is no leading word boundary, so the literal `sk-` inside an ordinary hyphenated word matches.
Verified by execution:

| input | output |
|---|---|
| `task-oriented` | `ta[redacted-secret]` |
| `risk-assessment` | `ri[redacted-secret]` |
| `disk-utilization` | `di[redacted-secret]` |
| `desk-checking` | `de[redacted-secret]` |

Mirrored at `capture.py:61` (`_SECRET`), so reviewer `finding`/`evidence`/`fix` prose is corrupted the
same way today.

**Fix — the boundary class is a decision, and it is ASYMMETRIC between the two prefixes.** Require
start-of-string or a boundary character before the prefix, preserving that character in the
replacement — but the boundary class differs per prefix, because the two prefixes have different
collision profiles:

```sh
shell   -e 's#(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{8,}#\1[redacted-secret]#g' \
        -e 's#(^|[^A-Za-z0-9_])pk_[A-Za-z0-9._-]{8,}#\1[redacted-secret]#g' \
python  _SECRET = re.compile(r"(?:(?<![A-Za-z0-9])sk-|(?<![A-Za-z0-9_])pk_)[A-Za-z0-9._-]{8,}")
```

**Underscore IS a boundary before `sk-`, and is NOT before `pk_`.** Rationale, per prefix:

- **`sk-`** — an identifier cannot contain `-`, so `foo_sk-…` is never a real identifier, while
  concatenated leak shapes such as `OPENAI_KEY_sk-proj-…` and `backup_sk-live-….json` are plausible.
  Underscore-as-boundary costs nothing here and catches the leak.
- **`pk_`** — `_pk_` **is** the conventional SQL/GRDB primary-key shape, so `orders_pk_customer_id_idx`
  and `idx_pk_customer_id_lookup` are ordinary reviewer evidence in exactly the repo this plugin
  serves. Treating underscore as a boundary there would corrupt correct text, which §3 forbids. And a
  `pk_` value is a *publishable* key by convention — the lower-stakes half of the pair.

Verified on both engines across ten vectors, with exact shell/Python parity: `OPENAI_KEY_sk-proj-…`
redacts, `orders_pk_customer_id_idx` and `idx_pk_customer_id_lookup` are **preserved**,
`pk_live_abcdefgh12345678` still redacts at start-of-string, and `(pk_abcdefgh123)` still redacts
after punctuation.

> *Round-3 change, and it removes a cost rather than trading one.* Round 2 used **one** guard for both
> prefixes and recorded `orders_pk_customer_id_idx → orders_[redacted-secret]` as an accepted cost,
> raising it in §8 as the thing reviewers should contest. A reviewer contested it and proposed
> splitting the policy per prefix. Executed: the asymmetric rule keeps every leak case **and** every
> identifier case. The §8 question dissolves rather than being answered — there is no trade left.

**Non-ASCII is deliberately not in the guard, and the guard class is `[^A-Za-z0-9]` / `[^A-Za-z0-9_]`
— ASCII, spelled out.** Do not write `\W` for it anywhere: in Python `\W` is Unicode-aware by default
and would behave differently. Under `LC_ALL=C` (hook-io.sh:227) POSIX ERE cannot express a Unicode word
class at all, so a Unicode-aware Python guard would break the shell/Python parity §4.4 exists to
guarantee. Both runtimes as specified agree that `cafésk-abcdefgh123` → `café[redacted-secret]`.

> *Round-2 correction, refined in round 3.* Round 1's text said "require a non-word character" in prose
> while prescribing a different class in the regex — **the paragraph contradicted itself**, and an
> implementer could satisfy either reading. The contradiction, not the choice, was the defect.
>
> A round-1 reviewer also reported that the guard "omits non-ASCII", citing `café-sk-…`. **Refuted by
> execution:** the character immediately before `sk-` there is the hyphen, which no candidate ASCII
> guard treats as a word character. Under true adjacency (`cafésk-…`) both candidate ASCII guards
> behave identically — and independently confirmed by the other reviewer, which also supplied the
> mechanism: under `LC_ALL=C` the `é`'s second UTF-8 byte (`0xA9`) is not alphanumeric, so it acts as
> the boundary.
>
> **Round-3 narrowing of that refutation.** It holds only between the two *ASCII* classes. If `\W` is
> read as Python's Unicode-aware class, the accent **does** decide: `(?<!\w)` preserves
> `cafésk-abcdefgh123` entirely while the ASCII guard redacts it (executed). That is why the class is
> now spelled out literally above, and why §4.4's fixture carries a true-adjacency row — so a
> Unicode-aware Python mutant cannot pass unnoticed.

**Proof — the round-1 set was insufficient and is replaced.** Round 1 named only the two
start-of-string controls `sk-proj-abcdefgh12345678` and `pk_live_abcdefgh12345678`, which never
exercise the `[^A-Za-z0-9]` alternation branch or delimiter preservation. Two plausible implementations
pass that set while leaking a real secret. Required set, on **both** implementations:

- **preservation:** `task-oriented`, `risk-assessment`, `disk-utilization`, `desk-checking`
- **guard-branch:** `Xsk-abcdefgh123` and `9sk-abcdefgh123` survive (letter/digit guard)
- **mid-string positive controls** (exercise the non-`^` branch and delimiter preservation):
  `token sk-abcdefgh123` → `token [redacted-secret]`; `token=sk-abcdefgh123` →
  `token=[redacted-secret]`; `(pk_abcdefgh123)` → `([redacted-secret])` — the surrounding delimiter
  must be **byte-identical** in the output
- **both-branches-in-one-pass:** `sk-abcdefgh123 sk-abcdefgh123` → `[redacted-secret] [redacted-secret]`
- **start-of-string:** `sk-proj-abcdefgh12345678`, `pk_live_abcdefgh12345678`
- **threshold pair — both required, one on each side of `{8,}`:** `sk-abcdefgh` (payload exactly **8**)
  → redacted; `sk-abcdefg` (payload **7**) → unchanged
- **asymmetric-policy rows** (pin §4.1's per-prefix decision, and they must move in opposite
  directions): `foo_sk-abcdefgh123` → **redacted**; `OPENAI_KEY_sk-proj-abcdefgh12345678` →
  `OPENAI_KEY_[redacted-secret]`; `orders_pk_customer_id_idx` → **preserved**;
  `idx_pk_customer_id_lookup` → **preserved**
- **true-adjacency non-ASCII row:** `cafésk-abcdefgh123` → `café[redacted-secret]` on **both** engines.
  This is the row that rejects a Unicode-aware Python guard, which would preserve it entirely.

**Anti-implementation controls — all four must FAIL, and this is the mutation proof for §4.1:**
1. an implementation that drops `\1` from the shell replacement (eats the boundary character);
2. an implementation anchored only at `^` (leaves `token sk-abcdefgh123` fully unredacted);
3. a `{9,}` threshold mutant — rejected only by the exactly-8 positive above. *Every* round-2 positive
   carried at least 11 payload characters while the only negative carried 7, so a `{9,}` mutant passed
   the entire round-2 set while violating the retained `{8,}` contract;
4. a Unicode-aware Python guard (`(?<!\w)`) — rejected only by the true-adjacency row above.

Round 1's controls pass mutants 1 and 2; round 2's pass mutants 3 and 4. §6's blanket "revert it and
the test fails" closes none of them, because no mutant is a revert. **This list is the concrete
instance of §3's second corollary; treat it as the template for the other sections.**

### 4.2 — The `~` rule has no path context and eats approximations (High)

**Root cause.** `scripts/lib/hook-io.sh:231`:

```sh
-e 's#~[A-Za-z0-9._-]+#~[redacted]#g' \
```

Intended for `~username` home-directory paths, it matches any `~`-prefixed token. Verified:

| input | output | why it matters |
|---|---|---|
| `~500ms` | `~[redacted]` | deletes latency figures |
| `~2x faster` | `~[redacted] faster` | deletes ratios |
| `~40 percent` | `~[redacted] percent` | deletes percentages |
| `~40/60 split` | `~[redacted]/60 split` | **defeats a slash-only rule** |
| `~L147` | `~[redacted]` | **defeats a non-digit-only rule** — this is the shape of reviewer line refs |
| `~Copyable` | `~[redacted]` | corrupts Swift syntax (16 in-tree occurrences) |

This is the sharpest of the three for `COREDEV-2585`: engineering rationale is full of `~Nms` / `~N%`,
so the redactor **silently deletes exactly the quantitative justification** a decision journal exists to
preserve.

**Fix — one contract, not a choice. The conjunction of both reviewers' rules.** Redact `~user` only
in home-*path* position: a leading token boundary, a first character in `[A-Za-z_]`, **and** a
following `/`.

```sh
shell   -e ':t' -e 's#(^|[^A-Za-z0-9_])~[A-Za-z_][A-Za-z0-9._-]*/#\1~[redacted]/#' -e 'tt' \
python  _TILDE = re.compile(r"(?<![A-Za-z0-9_])~[A-Za-z_][A-Za-z0-9._-]*(?=/)")
```

Three things about that shell form are load-bearing and must not be "simplified":

- **The `:t` / `tt` loop replaces the `g` flag and is mandatory.** With a bare `g`, `sed` resumes
  scanning *after* the previous match and can no longer see the boundary character, so `~a/~b/x`
  yields `~[redacted]/~b/x` while Python's lookbehind catches both — a silent divergence that lands
  straight in §4.4's parity fixture. Verified: with the loop, parity is exact on all vectors.
- **The label must live in its own `-e`, and getting this wrong fails SILENTLY.** BSD `sed` does not
  reject `-e ':t;s#…#…#'` — it **exits 0**, prints `unused label 't;s#…#…#'` to stderr, and performs
  **no substitution at all** (executed: input `a` comes back as `a`). Inside `hook_redact_pii`, whose
  `2>/dev/null` suppresses that diagnostic, the combined form would silently disable the whole rule.
  That is strictly more dangerous than a rejection, so the test must assert redaction *happened*, not
  merely that the command exited 0.
- **The replacement keeps the trailing `/`.** Drop it and `~alice/secrets` mangles to
  `~[redacted]secrets`.

> *Round-2 resolution of a direct reviewer conflict.* Round 1 offered two options and asked reviewers
> to choose; the reviewers chose **opposite** ones, and mutually exclusively — one's mandated test was
> unsatisfiable under the other's rule. Settled by execution: **neither rule alone is adequate.**
> Slash-only corrupts `~40/60 split`, `~1/2 of the rows`, `split ~50/50`, `~2x/day`. Non-digit-only
> corrupts 57 occurrences across 33 distinct tokens in this repo's own text, including `~Copyable`
> (×16), `~Escapable` (×6) and ~20 `~L<line>` references — which is literally the format of the
> reviewer `evidence` text `capture.py` redacts. The conjunction closes both classes. The claim that
> requiring a slash is "too strict" is refuted quantitatively; the measurement runs the other way.
>
> Neither reviewer noticed that **a leading-boundary guard is what creates the parity bug** (`~a/~b/x`),
> so adopting either recommendation verbatim would have shipped a §4.4 failure. Hence the loop.

**The slash requirement is a consistency fix, not a new policy — but the precedent covers only that
half.** `mcp/review-synthesizer/schema.py:200-201` already ships and tests the principle: *"A plain
`~backup.swift` (tilde with no following `/`) is a legal repo filename and is NOT matched — only a
home-dir REFERENCE."* `capture.py:57`'s own positive control is `~alice/Library/…`, with a path.
`hook-io.sh:216-217`'s purpose clause is path-shaped (`/Users/<name>/…`, `-archivePath`). No shipped
test anywhere asserts a bare `~alice` is redacted. Both reviewers and the round-1 plan missed this
precedent two files away.

> *Round-3 narrowing.* Round 2 called this "this exact definition". It is not. `schema.py:202`'s actual
> rule is `^~[^/]+/`, which accepts **any** non-slash first character — including a digit, so it would
> match `~9lives/x` and `~40/60`. It is precedent for **requiring the slash**, and precedent for
> nothing else. The `[A-Za-z_]` first-character class is this plan's own addition, justified below on
> corpus evidence rather than on precedent. Do not cite `schema.py` for it.

**Proof.** Round 1's sole positive control `~alice/secrets` cannot discriminate — it redacts
identically under the shipped buggy rule *and* both candidates. Required, on **both** implementations:

- **positive** (fail if redaction is disabled): `~alice/secrets` → `~[redacted]/secrets`;
  `~root/.ssh/id_rsa` → `~[redacted]/.ssh/id_rsa`; `(~bob/tmp)` → `(~[redacted]/tmp)` (punctuation
  prefix); `x-~carol/y` → `x-~[redacted]/y` (proves `-` is a boundary, so `--flag=~user/…` redacts);
  `~_daemon/x` → `~[redacted]/x` — **underscore-leading, and required**: every other positive starts
  with a letter, so without this row a `[A-Za-z]` mutant passes the whole set while missing a valid
  contract input; `see /Users/nick/z and ~nick/z` → both halves redacted in one pass
- **loop assertion:** `~a/~b/x` → `~[redacted]/~[redacted]/x`. Delete `-e ':t' -e 'tt'` and this must
  fail. This is §4.2's mutation proof. Assert the **redacted output**, not the exit status — see the
  silent-no-op note above.
- **preservation** (fail if the rule is widened back): `~500ms`, `~2x faster`, `~40 percent`,
  `~ten minutes`, `~half the rows`, `takes ~one second`, `~L147`, `~Copyable`, `~Escapable`,
  `~40/60 split`, `~1/2 of the rows`, `split ~50/50`, `~1a2b`, `cost ~$5`, `~/Documents`,
  `backup~alice/x` (embedded `~` must not match)
- **pinned accepted-gap control #2 — the digit-leading username:** assert `~9lives/x` is **preserved**,
  with an inline comment recording it as a deliberate residual of the `[A-Za-z_]` first-character
  class. Round 2 discussed this gap in §8 but never pinned it, so nothing stopped a later widening.
  `~1a2b` does not cover it — that input has no slash and would be preserved by the slash requirement
  alone, so it cannot discriminate the first-character class.
- **pinned accepted-gap control:** assert `hook_redact_pii "~alice"` == `~alice` and
  `redact_pii("~alice")` == `~alice`, with the inline comment: *"Deliberate. A bare `~user` with no
  path is regex-indistinguishable from `~ten`/`~half`/`~Copyable` — identical shape. §2 already accepts
  that this redactor leaves plain personal names untouched. Changing this line is a scope decision, not
  a bug fix."* This replaces the round-1 reviewer request for a bare-`~username` **positive** control,
  which is unsatisfiable under this rule by construction and would force the corruption back.

**Knock-on:** the strict rule makes `capture.py:58`'s `(?!(?:Copyable|Escapable)\b)` lookahead dead
code. Delete it and its 56-57 comment; §4.4's exemption set shrinks accordingly.

### 4.3 — `LC_ALL=C` misses `tr`, so invalid UTF-8 truncates and leaks stderr (High)

**Root cause.** `scripts/lib/hook-io.sh:227,236`. `LC_ALL=C` is applied to `sed`; the trailing
`| tr '\n\r\t' '   '` runs **unlocalised**, and the `2>/dev/null` binds to `sed` only. Under a UTF-8
locale a single invalid byte makes BSD `tr` abort:

- stdout is **truncated at the bad byte** — everything after it is lost;
- `tr: Illegal byte sequence` **escapes to stderr**, contradicting the repo's stderr-clean/fail-open
  invariant (`scripts/lib/log.sh:11-12`).

Isolating the stages confirms `sed` handled the bytes fine; `tr` is what aborts.

**Fix.** `LC_ALL=C tr … 2>/dev/null`. The precedent is already in-tree and correct at
`scripts/stop-failure-log.sh:33` and `scripts/permission-denied-log.sh:31` — which is what shows the
omission inside the helper is an oversight, not a convention.

**Proof — round 1's was inert on CI and is replaced.** CI is `ubuntu-latest` **only**
(`plugin-ci.yml:30`, `:164`, `:203`; no `macos-*` anywhere, and the repo runs no tests on macOS).
**GNU `tr` is not multibyte-aware**: it passes invalid bytes straight through, exits 0, writes nothing
to stderr, and produces byte-identical output with and without `LC_ALL=C`. So on the only platform CI
runs, the unfixed function already satisfies all three assertions round 1 proposed — **both halves of
the fix are unobservable, and reverting the whole thing stays green.**

*(Round 1 stated this defect as `LC_ALL`-only. It is broader: the `2>/dev/null` half is equally
unprovable under GNU, because GNU `tr` never writes to stderr for this input.)*

The required mutation proof is a **`tr`-shadow test that behaves identically on BSD and GNU**. Add it
to `scripts/test-hooks.sh` (reuse the `bash -c` + function-shadow pattern at `:529`/`:534`):

1. run the helper in a subshell with ambient `LC_ALL` set to a bogus sentinel (e.g. `zz_ZZ.UTF-8`) —
   **mandatory**: with an ambient `C` locale the *unfixed* code passes the locale assertion;
2. shadow `tr` with a function that does **two** things, then delegates via `builtin command tr "$@"`:
   - writes `"${LC_ALL-<unset>}"` to a **file** — not stderr, because the fix's own `2>/dev/null`
     would swallow a stderr probe;
   - **unconditionally emits a known marker to stderr** (e.g. `SHADOW_STDERR_MARKER`);
3. assert the probe file contains exactly `C` **and** the helper's captured stderr is empty, and that
   normal redaction output is unchanged.

**The stderr marker is what makes the redirect half provable, and round 2 omitted it.** Without it the
shadow never writes to stderr on ordinary input, so a mutant that correctly adds `LC_ALL=C` but drops
`2>/dev/null` records `C`, produces unchanged output, and shows empty stderr — passing both
assertions. That was verified by execution against round 2's design; the redirect at `hook-io.sh:236`
was mutation-unproved. With the marker, all four cases separate cleanly:

| implementation | probe | stderr | outcome |
|---|---|---|---|
| **fixed** (`LC_ALL=C tr … 2>/dev/null`) | `C` | empty | **passes both** |
| locale added, redirect dropped | `C` | `SHADOW_STDERR_MARKER` | fails the **stderr** assertion |
| redirect added, locale dropped | `zz_ZZ.UTF-8` | empty | fails the **locale** assertion |
| shipped (neither) | `zz_ZZ.UTF-8` | `SHADOW_STDERR_MARKER` | fails both |

Each half of the fix is now independently rejected by its own mutant — which is the property round 2
claimed and did not have. **All three traps are stated because any one of them silently re-hollows the
proof.** Add a one-line comment on the test noting that the shadow is a shell *function*, so a future
refactor to `/usr/bin/tr` would make it go green vacuously.

Keep the invalid-UTF-8 case, but demote it from *the* mutation proof to a **BSD-only behavioural
check**, gated on a `tr --version` probe so it is *skipped*, not vacuous, on GNU. Also fix its weak
assertion: "the literal address is absent" passes **by truncation** on BSD. The discriminating form is
"`[redacted-email]` IS present **and** the trailing `end` survives".

**The fix still ships.** The defect is live where these hooks actually run — the developer's macOS
host, for a plugin that drives a native macOS app. Only the *proof* was inert; do not read this finding
as a reason to downgrade §4.3.

**Note for the implementer.** Shell-only. The Python side has a different ingress: it must be proven to
**replace** the bad byte without truncating later text, which is a separate assertion, not the same one.

### 4.4 — The two implementations can silently re-diverge (Medium)

**Root cause.** The shell and Python redactors are independent code. They already disagree, and §4.1
and §4.2 require *textually different* fixes on each side (ERE has no lookbehind), which is precisely
what creates the risk. Nothing detects further drift.

**Fix.** A **shared fixture list** exercised by both suites, asserting identical output except for an
explicitly enumerated exemption set.

**What the fixture can and cannot guarantee — corrected in round 2.** Round 1 claimed *"Adding an
exemption to one side without updating the list fails CI."* That is **false**, and was refuted by
execution: adding an exemption for an input the list does not name leaves the guard green while the two
implementations genuinely disagree. **No finite fixture can close this.** The honest guarantee:

> The fixture detects divergence **only on the inputs it lists**. Its guarantee is therefore procedural
> as much as mechanical: the list is the single canonical source **imported** by
> `mcp/review-synthesizer/tests/test_capture.py` and by the shell harness — not duplicated — so an
> exemption must be added to the list to be tested at all. Seed it with every input the two
> implementations' patterns can distinguish today, and require a fixture entry in the same commit as
> any new exemption.

**Exemption shape:** each exempted input pins the expected `(shell, python)` output **pair**. Do not
use a skip-list — a skip makes exemption *removal* invisible (demonstrated: dropping `Escapable` from
`_TILDE` passes a skip-style guard and fails an assert-style one).

**There is NO surviving tilde divergence — after §4.2 the two tilde rules agree exactly.**

> *Round-3 correction of a self-contradiction round 2 introduced.* Round 2's §4.4 claimed the
> slash-joined Swift form `~Copyable/~Escapable` was "the one surviving tilde divergence", on the
> grounds that Python's `Copyable|Escapable` lookahead preserves it and ERE cannot express one. But
> §4.2 **deletes that lookahead** as dead code. Executed with the new rules on both sides and the
> lookahead removed: shell gives `~[redacted]/~Escapable` and Python gives `~[redacted]/~Escapable` —
> identical. The plan was simultaneously deleting the mechanism and citing it. There is no tilde
> exemption to enumerate.

**The enumerated exemption set is therefore exactly two entries**, both genuine and both verified:

1. `_EMAIL`'s `@Nx` retina-filename exemption (`capture.py:51-53`) — Python preserves `Icon@2x.png`,
   shell redacts it (§2 keeps this out of scope on the caller-impact evidence in §4.6).
2. Whitespace folding — `a\n\n\tb` → shell `a   b`, Python `a b`.

Do not add a tilde entry, and do not claim the tilde rules are merely "behaviourally equivalent" —
after §4.2 they are byte-identical on every fixture, which is a stronger and checkable property.

**Run the full pipeline, not isolated rules.** §4.2's rule executes *before* §4.1's in the same `sed`
invocation and changes what text §4.1 sees. The fixture must drive the whole `hook_redact_pii` /
`redact_pii` entry point, or rule-ordering regressions slip through. Include the `~a/~b/x` adjacency
vector — that is the input that catches an implementer who reflexively adds a boundary guard.

**Proof — production-side, because the fixture *is* the deliverable.** §6's blanket "revert the fix and
the test must fail" is vacuous here: reverting the fixture merely deletes the assertion.

1. Apply §4.1's boundary fix to **one** implementation only, leaving the other shipped → the parity
   test must fail, naming `task-oriented` / `risk-assessment` / `disk-utilization` / `desk-checking`.
2. Delete an enumerated exemption from `capture.py` → the parity assertion must fail because the
   exemption no longer holds.

### 4.5 — The 2585 split left drift behind (Low–Medium, documentation integrity)

**Root cause.** The commit that split these defects out of `DECISION_JOURNAL_PLAN.md` was
**header-only** (61 insertions, all in the top 5 lines and the file tail). Its header says
`COREDEV-2597` "is no longer in this plan's scope" while **six body passages** still instruct an
implementer to do this ticket's work.

*(Round 1's reviewer cited one line. There are six, plus two header-metadata fields — fixing only the
cited line would read as resolved while the drift survives in five places.)*

**Fix.** In `DECISION_JOURNAL_PLAN.md`, mark superseded — in one pass, because they cross-reference:
§4.7 Fix part 1; §4.7 Proof; the §5 risk row; §6's `§4.7–§4.11` mutation-proof range; §7 step 1
(replace with "verified `COREDEV-2597` dependency landed"); and §8 Q1 (which points at §7 step 1 and
would otherwise dangle). Add the redactor fixes to §2's **Out** list, add `COREDEV-2597` to
**Depends on**, and reconcile the release chain.

**Do not over-delete.** §4.7's (a)/(b)/(c) diagnosis and its "what will NOT catch a leak" note are
load-bearing for 2585's own §3 argument and §5 risk row, and this plan explicitly disclaims that scope
(§2). Deleting all of §4.7 would drop a control neither plan then owns.

**Urgency.** 2585 is `⏸️ PAUSED — Do not implement`, so nothing is being executed today and there is no
shipped-asset consequence. But the pause is temporary by design (2583 → 2584 → 2585): when it unpauses,
whoever picks it up reads §7 step 1 as their first instruction and re-does this ticket's regex work.
The pause defers the cost, it does not remove it. A six-line doc edit now beats a duplicated
implementation two tickets from now.

### 4.6 — Caller audit: what actually flows through the shell redactor (evidence, not a fix)

Round 1 had no caller audit, which is why the `@2x` question could not be settled on evidence. There
are exactly **four** shell callers of `hook_redact_pii`:

| caller | field | can it carry `@`/`~` literals? |
|---|---|---|
| `permission-denied-log.sh:35` | `reason` | **Yes — genuinely free text.** Writes to `logs/denied-commands.jsonl` |
| `stop-failure-log.sh:33` | `error_type` / `error` | **No — structurally.** Post-clamped by `tr -cd 'A-Za-z0-9_.-'`, which strips `~` and `@` regardless of what arrives |
| `precompact-snapshot.sh:35` | `PLAN` | **Yes, in principle** — see below. Constrained to a `docs/planning/*_PLAN.md` path, but the glob restricts only the *suffix*, not the basename's characters |
| `sessionstart-restore.sh:77` | session hint | **Yes, by consuming the above.** Composed from `ticket`, `branch_slug`, `round` (all constrained) **and the `plan` value produced by the row above**. This is the one caller whose output reaches model context |

> *Round-3 correction — round 2's version of this table was materially wrong, and the error mattered
> because it carried the severity argument.* Round 2 asserted the last two rows were **structurally
> incapable** of carrying these literals. Refuted by execution: `docs/planning/AppIcon@2x.png_PLAN.md`
> satisfies the `*_PLAN.md` glob, and the shipped redactor turns it into
> `docs/planning/[redacted-email]_PLAN.md`. That value is persisted by the PreCompact hook, read back
> without validation, and injected into model context — so the two rows claimed to be incapable are in
> fact a **producer/consumer pair**, and the only one that is structurally safe is `stop-failure-log`.
>
> Round 2 also said `denied-commands.jsonl` has **"no reader anywhere in the repo"**. Also false:
> `log_append` reads it for rotation (`log.sh:40`) and the hook suite reads it (`test-hooks.sh:507`).
> And a diagnostic log is a human-consumed artifact whether or not a parser exists.

**What the corrected audit does and does not support.** It does **not** support "structurally
impossible", and the honest position is weaker: **no realistic plan filename contains `@` or `~`, and
nothing enforces that.** Every `*_PLAN.md` in-tree is `[A-Z0-9_-]+_PLAN.md`. So the residual risk is a
naming convention nobody has broken, not a guarantee — which is enough to keep `@2x` out of scope
under §3 (the fix would widen nothing, but the corruption has no realistic trigger), and **not** enough
to call the row incapable.

**Caveat, stated rather than hidden:** this samples *this* repo (40 live records, zero `~`, zero `@`).
The plugin's target is the Swift app repo, where `icon_512x512@2x.png` assets genuinely exist. A
`[Sensitive File]` denial on an asset write would produce a corrupted line there. The cheap check
before implementation is `grep -c '@\|~' denied-commands.jsonl` in the app repo's plugin-data dir.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| A narrowed pattern stops redacting a real secret | **High if unguarded** | §3's corollary: every fix ships a positive control. A preservation-only test would pass with redaction disabled entirely. |
| A proof is green on CI while proving nothing | **High — realised in round 1** | §4.3's GNU/BSD gap and §4.1's two passing-but-wrong implementations were both found only by execution. Every proof below names the mutant it rejects. |
| The shell and Python fixes diverge because ERE lacks lookbehind | Medium | §4.4's parity fixture asserts behavioural agreement, not textual identity — and runs the full pipeline, not isolated rules |
| §4.1's boundary policy corrupts a legitimate SQL identifier | **Low — eliminated in round 3** | The asymmetric rule preserves `orders_pk_customer_id_idx` and `idx_pk_customer_id_lookup` while still redacting `OPENAI_KEY_sk-proj-…`. Both directions are pinned as fixture rows, so a later collapse back to one uniform guard trips a test |
| A per-prefix rule is "simplified" back to one uniform guard | Medium | The two asymmetric-policy fixture rows move in **opposite** directions, so no single guard can satisfy both |
| §4.2's accepted gap (bare `~alice`) is later "fixed" by widening | Medium | Pinned negative control + inline comment + §2 entry, so re-widening fails CI rather than passing silently |
| Fixing `tr` changes output for existing callers | Low | Only affects inputs containing invalid UTF-8, which currently **truncate** — any change is strictly an improvement |
| Scope creep into "make it a real PII scrubber" | Medium | §2 excludes it explicitly; that limitation is `COREDEV-2585`'s to design around |
| Conflict with `COREDEV-2604` in `capture.py` | Medium | Land this first; 2604 restructures reporting, this touches only the regexes |
| No macOS/BSD coverage in CI at all | **Medium — structural** | §4.3's shadow test is engine-agnostic by design. The repo's own precedent (`plugin-ci.yml:158-164`, `py39-smoke`) is to simulate platform concerns on Ubuntu rather than add a runner; adding `macos-latest` is out of scope here |

## 6. Verification

```bash
python3 scripts/validate-plugin-assembly.py --root . --strict
python3 scripts/validate-hooks.py --root . --strict --require-manifest
VERSION_SYNC_ENFORCE=strict bash scripts/validate-version-sync.sh
bash scripts/test-hooks.sh
python3 -m unittest discover -s mcp/review-synthesizer/tests
python3 -m unittest discover -s scripts/tests
shellcheck -s bash -S warning scripts/*.sh scripts/lib/*.sh scripts/review/*.sh .githooks/pre-commit
```

Baselines **as measured at `696a036`**: `test-hooks.sh` **302**, synthesizer **191**, scripts **280**,
counts `21/21/0/1`. These are **floors, not equalities** — re-derive at implementation time and record
the new numbers; a *lower* count is the failure signal. Always print `pwd` and `git rev-parse HEAD`
beside a measurement: the stale main checkout reports 227, and a bare number with no commit anchor is
how round 1 shipped a stale 269.

*(Round 1 said 269. That was the true v2.6.0 baseline; `04f906d` added 11 tests for COREDEV-2602 the
commit before these plans were written. `CI_WORKFLOW_HARDENING_PLAN.md:178` inherited the identical
error and is corrected in the same pass.)*

**Mutation proof required for every fix, and it must reject plausible wrong implementations, not just
reverts** (§3's second corollary):

- **§4.1–§4.3:** revert the fix → the new test must fail. **Plus** §4.1's two named anti-implementation
  mutants (drop `\1`; anchor only at `^`) must both be rejected, and §4.2's loop mutant (delete
  `-e ':t' -e 'tt'`) must fail on `~a/~b/x`.
- **§4.4:** the fix *is* the test, so "revert it" is vacuous. Its proof is **production-side** — see
  §4.4's two mutations.

**Portability assertion.** Put the full §4.1/§4.2 vector tables into `scripts/test-hooks.sh` rather
than a scratch script: CI runs that harness on `ubuntu-latest`, which makes CI itself the GNU-engine
proof for regex forms developed against BSD `sed`.

## 7. Implementation order

1. **First:** grep both suites for existing assertions that depend on `~<word>` or mid-word `sk-`
   being redacted. §4.2 changes behaviour a shipped test may encode.
2. §4.3 — the `tr` locale/stderr fix + the engine-agnostic shadow test (shell only; no regex semantics).
3. §4.1 — the `sk-`/`pk_` boundary, both sides, with the full control set and both anti-implementation
   mutants.
4. §4.2 — the strict `~` contract, both sides, including deletion of `capture.py:58`'s dead lookahead.
5. §4.4 — the shared parity fixture (last of the code, so it can enumerate the real exemption set).
6. §4.5 — the `DECISION_JOURNAL_PLAN.md` supersede pass (documentation only; may land in parallel).
7. Correct `scripts/lib/hook-io.sh:221-224`'s comment (exemption count + the false expressibility claim).
8. Version bump to **2.6.2** (or 2.6.3 — see header sequencing) + CHANGELOG.

## 8. Open questions — all three answered in round 2

1. **Should the shell side gain the two Python exemptions (`@2x`, `~Copyable`)?**
   **Answered — split.** The `~Copyable`/`~Escapable` half is **dissolved**, not ported: §4.2's strict
   rule preserves them as a side effect, so `capture.py:58`'s lookahead becomes dead code and is
   deleted. The `@2x` half stays out, on **caller-impact** evidence (§4.6), not expressibility — the
   two-pass ERE workaround provably works and the "POSIX ERE cannot express it" claim must be struck
   wherever it appears.
2. **How strict should the `~` fix be?**
   **Answered — the conjunction:** leading boundary + first char `[A-Za-z_]` + required following `/`.
   Neither reviewer's rule alone survives execution (§4.2). Accepted residual: bare `~alice`, pinned by
   a negative control. The documented threat (`/Users/<name>/…`, `-archivePath`) is covered by the
   untouched `/Users/` and `/home/` rules.
3. **Does §4.4's parity fixture belong here or in `COREDEV-2600`?**
   **Answered — here.** Both reviewers concurred and `CI_WORKFLOW_HARDENING_PLAN.md` §2 already
   disclaims the redactor.

4. **Round 2's question — is redacting `orders_pk_customer_id_idx` an acceptable cost of treating
   underscore as a boundary?**
   **DISSOLVED in round 3, not answered.** A reviewer proposed splitting the policy per prefix, and
   execution shows that keeps *both* properties: `OPENAI_KEY_sk-proj-…` still redacts, and both SQL
   identifiers are preserved. There is no trade to make, so the question no longer has a subject.
   §4.1 now specifies the asymmetric rule and pins both directions as fixtures.
5. **Round 2's second question — is `~9lives/x` reachable enough to matter?**
   **Answered — accept the miss, and pin it.** Digit-leading accounts require `useradd --badname`;
   `NAME_REGEX` and 134/134 local accounts are letter- or underscore-first. Widening to a slash-only
   rule to catch it necessarily reintroduces the measured `~40/60`, `~1/2` and `~2x/day` corruption,
   which §3 forbids. Both reviewers independently reached this conclusion. §4.2 now carries an explicit
   `~9lives/x` preservation control so the residual is a tested decision rather than an omission —
   round 2 discussed the gap but never pinned it.

**New for round 3 — asked, then answered rather than left open.** The asymmetric §4.1 rule is the one
genuinely novel construct here, and it is two `-e` fragments rather than one, so the obvious risk is an
interaction between them: could the `sk-` fragment consume a boundary character the `pk_` fragment then
needs? **Executed across eight adjacency and ordering vectors — zero parity mismatches**, including the
worst case `sk-abcdefgh123_pk_abcdefgh123`, where the `sk-` payload legitimately swallows the `_pk_`
(because `_` is inside the payload class `[A-Za-z0-9._-]`) and both engines agree. Those eight vectors
are added to §4.4's fixture so the property is enforced rather than remembered:

`sk-… pk_…` · `pk_… sk-…` · `sk-…,pk_…` · `a sk-… pk_… b` · `_pk_abcdefgh123` (preserved) ·
`_sk-abcdefgh123` (redacted) · `sk-abcdefgh123_pk_abcdefgh123` · `(sk-…)(pk_…)`

**What is still worth a reviewer's attention:** the two fragments must run in the same `sed`
invocation as §4.2's tilde loop, and §4.4's fixture drives the whole `hook_redact_pii` entry point
precisely so a cross-rule ordering regression surfaces. If a reviewer can construct an input where
tilde-then-secret ordering changes the result, that is the highest-value finding available in round 3.

## 9. Notes

- Every claim was verified by executing the shipped function; both plan reviewers reproduced all three
  defects independently while reviewing `COREDEV-2585`.
- The redactor is **not** a PII scrubber and this ticket does not make it one — see §2.
- `scripts/stop-failure-log.sh:33` and `scripts/permission-denied-log.sh:31` already apply `LC_ALL=C` to
  their own `tr`, which is the evidence that §4.3 is an oversight rather than a deliberate choice.
- `mcp/review-synthesizer/schema.py:200-201` already defines a home-dir reference as tilde **plus a
  slash**. §4.2 brings the redactor into line with a definition this repo already ships and tests —
  it is not a third rule.
- Regex work was developed against **BSD `sed`** (no GNU `sed` on the dev host). Every construct used is
  POSIX-portable by design, and §6's portability assertion makes CI the GNU proof.

## 10. Gate history — what each round changed

**gemini `APPROVE_WITH_NOTES` · codex `REQUEST_CHANGES` (7 findings).** Both reviewers independently
reproduced all three defects by execution; the diagnosis was never in dispute — the **implementation
contract** was.

Every finding was then re-verified by execution before this plan was touched. **Six of eleven findings
across the two plans needed correcting**, and in four cases the verification found something materially
stronger than the reviewer had:

| finding | verdict | what actually held |
|---|---|---|
| stale version + baseline | **confirmed** | …and the identical stale 269 sits in the sibling plan (§6) |
| `tr` proof inert on CI | **confirmed** | …and **both** halves of the fix are unobservable under GNU, not just `LC_ALL` (§4.3) |
| boundary omits `_` / non-ASCII | **partial** | non-ASCII **refuted** — the hyphen decided the example. The real defect was the paragraph contradicting itself, plus two passing-but-leaking implementations (§4.1) |
| Swift corruption is a live defect | **partial** | asymmetry real; the impact claim **fails** — 3 of 4 callers cannot carry the literals, the 4th writes a file nothing reads (§4.6) |
| must pick a tilde contract | **confirmed** | …and `schema.py:200-201` already ships the definition both reviewers argued about (§4.2) |
| §4.4 ownership contradiction | **partial** | right defect, **wrong section**: §4.4 was already correct; §2 was the culprit, and the plan gave three different answers (§2) |
| sibling split not reflected | **confirmed** | one cited site; there are **six** plus two header fields (§4.5) |

**Two changes would have shipped wrong by adopting the reviews verbatim:** editing §4.4 (already
correct) instead of §2, and adding a leading-boundary guard to the `~` rule — which *creates* a
shell/Python parity bug (`~a/~b/x`) that §4.4 exists to catch.

**The direct reviewer conflict on §8 Q2 was resolved against both reviewers**, in favour of the
conjunction of their rules, on measured corpus evidence (§4.2).

### Round 2 outcome

**gemini `APPROVE` · codex `REQUEST_CHANGES` (7 findings).**

gemini independently re-executed all three of round 2's load-bearing refutations and confirmed each,
supplying a better mechanism for one of them (under `LC_ALL=C` the `é`'s second UTF-8 byte `0xA9` is
what acts as the boundary). It also confirmed both §4.1 anti-implementation mutants were genuinely
rejected.

**codex found three real defects that a 13-agent verification sweep had missed**, which is the reason
the dual gate exists. All seven findings were re-verified by execution; **six confirmed, one refuted**:

| # | finding | verdict | round-3 change |
|---|---|---|---|
| 1 | §4.3's shadow never proves the **stderr** half — a `LC_ALL=C`-but-no-`2>/dev/null` mutant passes both assertions | **confirmed** | shadow now emits a stderr marker; four-case table in §4.3 separates the halves |
| 2 | §4.6's caller audit is materially wrong | **confirmed** | `AppIcon@2x.png_PLAN.md` passes the glob and reaches model context; "no reader" also false. Table rewritten, claim weakened from *structurally impossible* to *unenforced convention* |
| 3 | §4.4 cites a lookahead §4.2 deletes | **confirmed** | self-contradiction removed; there is **no** surviving tilde divergence, exemption set is exactly two |
| 4 | `schema.py` is not "the exact definition" | **confirmed** | its rule is `^~[^/]+/` — precedent for the slash only; `[A-Za-z_]` is this plan's own addition |
| 5 | proof tables still admit plausible wrong implementations | **confirmed** | added the exactly-8 threshold positive, `~_daemon/x`, and the `~9lives/x` pin; mutant list grew to four |
| 6 | the non-ASCII refutation is ASCII-only | **confirmed** | a Unicode-aware `(?<!\w)` *preserves* `cafésk-…`; class now spelled out literally, true-adjacency row added |
| 7 | BSD `sed` "rejects" the combined label | **REFUTED as stated, and the truth is worse** | it exits **0**, warns `unused label`, and performs **no substitution** — a silent no-op the helper's own `2>/dev/null` would hide |

**One codex finding was wrong and is not adopted.** It placed upstream's
`claude plugin marketplace add "$GITHUB_WORKSPACE"` at line 25 and `claude plugin list` at line 27.
Fetched and checked: `marketplace add` is line **27**, `plugin list` is line **29**, and line 25 is the
`export CLAUDE_CONFIG_DIR`. The sibling plan's citation stands unchanged.

**codex's asymmetric-boundary recommendation was adopted and is the round's best outcome.** Round 2
asked reviewers to contest a stated trade; the reviewer contested it and proposed splitting the policy
per prefix. Executed, it keeps every leak case *and* every identifier case, so §8 Q4 dissolved instead
of being answered — a strictly better result than either side's opening position.
