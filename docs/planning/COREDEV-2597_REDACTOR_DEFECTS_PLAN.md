# Redactor Defects Plan

**Status:** Planning — round 5, awaiting re-gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29 (round 5)
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
**scope, not impossibility** — §4.6's audit shows corruption IS reachable by two routes, but is not
observed, and the fix belongs with the `_EMAIL` rule rather than a ticket whose three defects are all
in `_SECRET`/`_TILDE`/`tr`. *(Round 3 said "no shell caller carries an asset filename into a consumed
artifact", which its own §4.6 table contradicts. Corrected there and here.)* Do **not** repeat the
claim that POSIX ERE cannot express it — that is false, and a two-pass protect/restore in one
`sed -E` reproduces the Python semantics byte-for-byte.
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

**Third corollary, added in round 5 — canonicalisation is not widening.** §3's "never widen" was
blocking three leak fixes at once. The resolution, stated as a rule rather than as a one-off exception:

> A leak may be closed by **canonicalising the input before any rule runs**, provided no redaction
> pattern is altered. Canonicalisation changes the input domain, not the match set.

This is the principle under which §8's fold-order change is legal, and it closes RC-A, RC-B and RC-C
together. It does **not** license widening a pattern; the secret-before-email reordering was rejected
under the unchanged rule (§4.4).

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

python  _SECRET_SK = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9._-]{8,}")
        _SECRET_PK = re.compile(r"(?<![A-Za-z0-9_])pk_[A-Za-z0-9._-]{8,}")
        # TWO sequential passes, sk- then pk_, mirroring the shell fragment order.
        text = _SECRET_SK.sub("[redacted-secret]", text)
        text = _SECRET_PK.sub("[redacted-secret]", text)
```

**Python must use two sequential passes, not one combined alternation — this is load-bearing.** A
single `(?:(?<!…)sk-|(?<!…)pk_)[A-Za-z0-9._-]{8,}` looks equivalent and is not: it matches
left-to-right and greedily, so on `pk_abcdefgh-sk-ijklmnop` it consumes the whole value from the
leading `pk_` and emits **one** replacement, while the shell's two fragments replace the `sk-` run
first and then the remaining `pk_`, emitting **two**:

| input | shell (two fragments) | Python, combined regex | Python, sequential |
|---|---|---|---|
| `pk_abcdefgh-sk-ijklmnop` | `[redacted-secret][redacted-secret]` | `[redacted-secret]` ✗ | `[redacted-secret][redacted-secret]` ✓ |
| `~a/pk_abcdefgh-sk-ijklmnop` | `~a/[redacted-secret][redacted-secret]` | `~a/[redacted-secret]` ✗ | matches shell ✓ |

Neither output leaks — both redact — but they **differ**, which is a §4.4 parity failure in the
implementation this plan itself prescribes. Verified across 16 vectors: the combined form mismatches on
2, the sequential form on **0**. *(Round 3 specified the combined form. A reviewer constructed the
counterexample; the eight adjacency vectors round 3 added did not cover it, because none placed both
prefixes inside one contiguous token.)* Both counterexamples are now required fixture rows.

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

**The exemption set is exactly TWO — but only after seven ALIGNMENTS, and it is closed by
construction rather than by enumeration.** *(Round 3 said two; round 4 said five; both were built by
whack-a-mole and both were wrong. Round 5 replaces the search with a model.)*

An exhaustive sweep built a **9-delta parameterised model of the shell** and validated it two ways over
a 40,000-input seeded corpus: with all deltas ON it equals `hook_redact_pii` byte-for-byte (0
mismatches); with all deltas OFF it equals `redact_pii` byte-for-byte (0 mismatches). Divergence is
therefore a *derivable function of the two pattern sets*, not a search result. Attributing all 13,950
observed divergences against the full 2⁹ delta powerset gave **0 unexplained**.

**Nine root causes. Seven are ALIGNED (must become byte-identical); two are permanent exemptions.**

| RC | cause | direction | disposition |
|---|---|---|---|
| A | Python `\s` vs POSIX `[[:space:]]` in the 3 `_APIKEY` slots + 1 `_BEARER` slot | **LEAK** | align |
| B | same class difference in `_USERS`/`_HOME` **negated** classes — polarity inverts, shell over-consumes and eats the `api`/`bearer` anchor | **compound LEAK** | align |
| C | `sed` is line-oriented and `tr` runs *after* it | **LEAK** | align |
| D | `re.IGNORECASE` folds `_APIKEY`'s literals (`i`←U+0130/U+0131, `k`←U+212A) | **LEAK** | align — narrow Python |
| E | `re.IGNORECASE` widens the value class `[A-Za-z0-9._-]` by {U+0130, U+0131, U+017F, U+212A} | **LEAK — worst shape** | align — narrow Python |
| F | `_EMAIL` `@Nx` retina lookahead (POSIX ERE has none) | corruption | **EXEMPT** (F2/F5/F6 align) |
| G | `_TILDE` `~Copyable`/`~Escapable` lookahead | corruption | **EXEMPT** (G2 aligns) |
| H | fold arity — `tr` is 1:1, Python's `[\r\n\t]+` collapses runs | cosmetic | align — drop the `+` |
| I | `tr` runs outside `LC_ALL=C` (`hook-io.sh:236`) | corruption | align — this is §4.3 |

**RC-E is the worst shape in the sweep** and deserves naming: the value-tail form emits
`[redacted-key]` *immediately followed by live secret material*, so it passes any assertion of the form
`'[redacted-key]' in output`. Any test written that way is worthless here.

**Three of the nine have UNBOUNDED generators, which is why enumerating inputs could never terminate:**

- **F** = 104 ASCII case spellings of `png|jpe?g|gif|pdf|webp|heic|tiff?` (plus U+0130/U+0131 for the
  `i` of `heic`) × unbounded `[0-9]+` × arbitrary local part × any codepoint outside `[A-Za-z0-9.-]`.
- **G** = 2 keywords × (end-of-input ∪ every codepoint outside Unicode `\w`), firing mid-string
  (`x~Copyable`) and after a second tilde (`~~Copyable`) too.
- **A/B/C** = slot × 23 codepoints × unbounded run length.

**The fixture must therefore assert the RULE, not a list of inputs.** Write the two exemptions as
generators, exactly as above.

**Nine MUST-AGREE negative controls are mandatory**, because each looks like it should diverge and does
not — without them the fixture drifts toward over-exempting: `AppIcon@2X.png` (capital `X` sits outside
the `(?i:)` group), `user@2xmail.com`, `~Copyable2`, `~copyable`, `bKarer …`, `sk-ABCDEFGKHIJ`,
`a\x0b\x0cb`, `api<U+200B>key:…`, `Icon@2x.pngsk-TOPSECRET1`.

**Two sub-shapes are real defects, not exemptions, and both are Python-side leaks:**

- **F2** — `user@2x.png.example.com`, a routable address, is **preserved entirely** by Python: the
  lookahead's terminating `\b` is satisfied by the following `.`. Fix: `\b` → `(?![A-Za-z0-9.-])`.
  Verified against 12 must-stay-exempt and 7 must-redact cases, 19/19 correct.
- **G2** — exactly 2 codepoints (`-`, `.`) are both outside `\w` and inside the tilde body class, so
  `~Copyable-alice` **leaks a real username**. Fix: `\b` → `(?![A-Za-z0-9._-])`.

**F3 survives the F2 fix and stays exempt** — for `<local>@<N>x.<ext>@<real-domain>` the two sides
redact *different, partially overlapping spans*. Record it so nobody later "fixes" the shell by
widening its email pattern.

**F4 is cross-rule and emits DIFFERENT placeholders** (`~[redacted-email]` vs `~[redacted]@2x.png`), so
an assertion of the form "both contain `[redacted]`" misses it entirely. A per-rule fixture files this
under "email" and never generates it — which is precisely how rounds 3 and 4 missed it.

**REJECTED, with evidence, so it is not re-proposed:** moving the SECRET rule ahead of the EMAIL rule.
It was executed. It does close the F5 leak, but it destroys legitimate addresses —
`support@sk-corp.com` → `support@[redacted-secret]` — and creates a new divergence. Trading a leak for
corruption is exactly what §3 forbids.

**Honest limits.** All of the above is a **BSD-sed** result; `gsed` is absent on the dev host and CI is
Ubuntu/GNU, so RC-I *inverts* by platform. NUL bytes, lone surrogates, and the Python-side `cap()` /
`normalize_file()` wrappers were not swept. See §4.5 for the mechanical check that closes the GNU gap.

**Run the full pipeline, not isolated rules.** §4.2's rule executes *before* §4.1's in the same `sed`
invocation and changes what text §4.1 sees. The fixture must drive the whole `hook_redact_pii` /
`redact_pii` entry point, or rule-ordering regressions slip through. Include the `~a/~b/x` adjacency
vector — that is the input that catches an implementer who reflexively adds a boundary guard.

**Rule ordering is load-bearing, and until round 3 it was unpinned.** A reviewer constructed the input
that proves it: **`~sk-abcdefgh123/`** is matched by *both* rules, and the order decides which wins.

| ordering | result |
|---|---|
| tilde first (**the shipped order**) | `~[redacted]/` |
| secret first | `~[redacted-secret]/` |

Executed on both engines; shell and Python agree **under each ordering**, so this is not a parity bug
today — it is an invariant nothing asserts. The shipped order is already tilde-before-secret in both
implementations (`hook-io.sh:231` before `:234`; `capture.py:83` `_TILDE` before `:86` `_SECRET`), and
**§4.1's new `pk_` fragment must be inserted after the tilde loop, not before it.**

Required: pin `~sk-abcdefgh123/` → `~[redacted]/` and `~sk-abcdefgh123/more` → `~[redacted]/more` as
fixture rows, and state the ordering as a contract in both files' comments. Either output redacts the
secret, so neither is a leak — but an implementer who reorders the fragments silently changes shipped
output, and if they reorder only one side the two implementations diverge.

**Proof — production-side, because the fixture *is* the deliverable.** §6's blanket "revert the fix and
the test must fail" is vacuous here: reverting the fixture merely deletes the assertion.

1. Apply §4.1's boundary fix to **one** implementation only, leaving the other shipped → the parity
   test must fail, naming `task-oriented` / `risk-assessment` / `disk-utilization` / `desk-checking`.
2. Delete an enumerated exemption from `capture.py` → the parity assertion must fail because the
   exemption no longer holds.

### 4.5 — Mechanical closure of the exemption set (new in round 5)

**A static fixture table cannot close this and must not be the gate.** Three of the nine root causes
have unbounded generators (§4.4), so any list of inputs is incomplete by kind — which is exactly why
rounds 3 and 4 each found more divergences than the previous enumeration claimed existed.

**Ship the model and the seeded corpus as a CI job, on `ubuntu-latest` AND `macos-latest`**, asserting:

1. `shell_model(x) == hook_redact_pii(x)` for every `x` in a fixed 40k seeded corpus. **This is the
   load-bearing assertion** — it fails the moment either implementation gains a behaviour the model
   does not encode, which is precisely the statement "a new root cause exists". It converts *"did we
   find them all?"* into a checkable equivalence.
2. `py_model(x) == redact_pii(x)` on the same corpus.
3. Post-alignment, every `shell != python` case is attributable to the email or tilde lookahead, and
   `UNEXPLAINED == 0`.

Running (1) on both platforms also settles the BSD/GNU question mechanically instead of by argument —
which matters because RC-I *inverts* by platform. The §4.4 table then serves its proper role: human
documentation of the exemptions, not the proof.

**Harness gotcha that must be in the test file's comment:** U+212A and U+0131 written as source
literals **silently normalise to ASCII** in some toolchains. Build every non-ASCII vector with `chr()`
or the fixture under-tests without failing. Two sweep agents hit this.

**Attribution gotcha:** leave-one-out attribution manufactures phantom root causes whenever two deltas
are *conjunctively* required — it reported 32 false residuals that the full 2⁹ powerset reduced to 0.
Any future sweep must attribute against the powerset.

### 4.6 — The 2585 split left drift behind (Low–Medium, documentation integrity)

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

### 4.7 — Caller audit: what actually flows through the shell redactor (evidence, not a fix)

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
impossible". The honest position: **no plan filename in-tree contains `@` or `~`, and nothing enforces
that.** *(Round 3 claimed every `*_PLAN.md` matches `[A-Z0-9_-]+_PLAN.md`. False —
`COREDEV-2333_RELEASE_2.4.0_PLAN.md` contains dots. The narrower claim is the one the evidence
supports, and it is enough.)*

**And the `@2x` scope decision is restated to match, because round 3's rationale contradicted its own
table.** §2 said "no shell caller carries an asset filename into a consumed artifact"; §4.6 then showed
free-text diagnostic consumption **and** a PreCompact→SessionStart path reaching model context, and
conceded a target-app asset denial would corrupt a line. Those cannot both stand. The decision and its
real reason:

> `@2x` stays out of scope **not** because corruption is impossible — it is possible, by two routes —
> but because it is **not observed** (40 live records, zero `@`, zero `~`; no in-tree plan filename
> carries either) and because the fix belongs with the `_EMAIL` rule rather than in a ticket whose
> three defects are all in `_SECRET`/`_TILDE`/`tr`. It is a **deferral on scope**, not a dismissal on
> impossibility. §4.4 entry 1 keeps it enumerated so it cannot be forgotten.

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

- **§4.1–§4.3:** revert the fix → the new test must fail. **Plus** §4.1's **four** named anti-implementation
  mutants — drop `\1`; anchor only at `^`; a `{9,}` threshold; a Unicode-aware Python guard — must all
  be rejected, **and** the combined-alternation Python form must fail on `pk_abcdefgh-sk-ijklmnop`; and
  §4.2's loop mutant (delete `-e ':t' -e 'tt'`) must fail on `~a/~b/x`.
- **§4.4:** the fix *is* the test, so "revert it" is vacuous. Its proof is **production-side** — see
  §4.4's two mutations.

**Portability assertion.** Put the full §4.1/§4.2 vector tables into `scripts/test-hooks.sh` rather
than a scratch script: CI runs that harness on `ubuntu-latest`, which makes CI itself the GNU-engine
proof for regex forms developed against BSD `sed`.

## 7. Implementation order

1. **First:** grep both suites for assertions that depend on `~<word>` or mid-word `sk-` being
   redacted, **and for any assertion of the form `'[redacted-key]' in output`** — RC-E proves that
   shape is worthless here, because the placeholder can be emitted immediately before live secret
   material.
2. §4.3 — the `tr` locale/stderr fix (RC-I) + the engine-agnostic shadow test.
3. **§8's canonicalisation pre-pass** — `\n\r\t` **plus the 23 Unicode space codepoints**, on both
   sides, before any rule runs. Closes RC-A, RC-B and RC-C together, changing no pattern.
4. §4.1 — the asymmetric `sk-`/`pk_` boundary, both sides (Python: **two sequential passes**), with the
   full control set and all four anti-implementation mutants plus the combined-alternation parity mutant.
5. §4.2 — the strict `~` contract, both sides, including deletion of `capture.py:58`'s dead lookahead.
6. **RC-D + RC-E** — narrow Python: drop `re.IGNORECASE` from `_APIKEY`/`_BEARER`, spell literals as
   ASCII classes. **File the shared-miss security follow-up in the same commit** (§8).
7. **F2 + G2** — narrow the two lookaheads: `_EMAIL` `\b` → `(?![A-Za-z0-9.-])`,
   `_TILDE` `\b` → `(?![A-Za-z0-9._-])`. Both close real Python-side leaks.
8. **RC-H** — drop the `+` from Python's `re.sub(r"[\r\n\t]+", …)`. Do **not** use `tr -s`, which
   would squeeze pre-existing literal spaces.
9. §4.4 — the shared parity fixture, written as **generators plus the nine negative controls**.
10. §4.5 — the model-equivalence CI job on both `ubuntu-latest` and `macos-latest`. **Re-run the whole
    sweep under GNU `sed` before freezing the fixture** — every result to date is BSD-only.
11. §4.6 — the `DECISION_JOURNAL_PLAN.md` supersede pass (docs only; may land in parallel).
12. Correct `scripts/lib/hook-io.sh:221-224`'s comment, **and the stale top-level parity commentary in
    `capture.py`** — round 4 named only the shell comment.
13. Version bump to **2.6.2** (or 2.6.3 — see header sequencing) + CHANGELOG.

## 8. Open questions

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

**Round 3's question — can rule ordering change the result?** **Answered: yes**, and it is now pinned.
A reviewer constructed `~sk-abcdefgh123/`, which both the tilde and secret rules match; tilde-first
gives `~[redacted]/`, secret-first gives `~[redacted-secret]/`. Neither leaks, both engines agree under
each ordering, and the shipped order is already tilde-first — so it was an unpinned invariant, now a
fixture row (§4.4).

**Round 4's question — should `hook_redact_pii` fold newlines before `sed`? ANSWERED YES by both
reviewers independently — and the agreed answer is INSUFFICIENT.**

Both reviewers ruled the same way, with sound reasoning (it changes no pattern; the boundary anchors
`(^|[^…])` mean a folded newline merely shifts the match branch; a secret wrapped across a newline is
not "correct text" that must be preserved). Executed and confirmed: 0 correct-text regressions across
the wrapped-correct-text corpus, and two real leaks closed.

**But folding only `\n\r\t` closes 1 of the 3 root causes in that class.** Executed:

| case | shipped | fold `\n\r\t` (as approved) | fold + the 23 Unicode spaces |
|---|---|---|---|
| `api<U+00A0>key: <secret>` | leak | **still leaks** | `[redacted-key]` |
| `api key:\n <secret>` | leak | `[redacted-key]` | `[redacted-key]` |
| `/Users/nick<U+00A0>api key: <secret>` | leak | **still leaks** | `[redacted-key]` |

**So §8 is widened: canonicalise `\n\r\t` PLUS the 23 codepoints in Python's `\s` that POSIX
`[[:space:]]` under `LC_ALL=C` does not accept** — U+001C–001F, U+0085, U+00A0, U+1680, U+2000–200A,
U+2028, U+2029, U+202F, U+205F, U+3000. The set is closed by enumeration over all of 0x110000 on the
Python side and by a byte-scan of 0x01–0xFF on the shell side; the difference is exactly 23. Negative
controls U+200B, U+FEFF and U+180E must **agree unchanged** — they are not Unicode `White_Space`.

*This is the clearest evidence in the whole ticket for sweeping rather than iterating: a direct question
was put to both reviewers, they agreed with each other, and the agreed fix was one third of the answer.
Neither had enumerated the whitespace axis.*

**New for round 5 — the one thing this plan now asks reviewers to weigh.** Aligning RC-D and RC-E
requires **narrowing Python** (dropping `re.IGNORECASE` from `_APIKEY`/`_BEARER` and spelling the
literals as ASCII classes). That is §3-compliant — it widens nothing — but it converts RC-E's
*divergence* into a **shared miss**: after the fix, *both* implementations leak
`api key: SECRET<U+017F>MORE`. The plan states this rather than hiding it, and it needs its own security
ticket. **Is converting a one-sided leak into a two-sided one the right call, or should `_APIKEY`/
`_BEARER` gain explicit ASCII-plus-fold classes on both sides instead?**

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

### Round 3 outcome

**gemini `APPROVE_WITH_NOTES` · codex `REQUEST_CHANGES` (4 findings).** All re-verified by execution.

**gemini answered §8's ninth-vector question with a real construction** — `~sk-abcdefgh123/`, matched by
both the tilde and secret rules, where ordering decides the winner. Confirmed on both engines; the
shipped order is already tilde-first in both implementations, so it is an unpinned invariant rather
than a live bug. Now pinned (§4.4), with the instruction that §4.1's `pk_` fragment goes *after* the
tilde loop.

**codex found a parity bug in round 3's own prescribed implementation** — the highest-value finding of
the round, and one the eight adjacency vectors added in round 3 did not cover:

| # | finding | verdict | round-4 change |
|---|---|---|---|
| 1 | a ninth ordering vector breaks shell/Python parity | **confirmed** | `pk_abcdefgh-sk-ijklmnop` → shell 2 replacements, combined-regex Python 1. **Python now uses two sequential passes** mirroring the shell fragment order; 0 mismatches across 16 vectors (was 2) |
| 2 | the exemption set is not exactly two | **3 of 4 confirmed** | three leak-direction divergences found (`Bearer\n…`, `api\nkey:`, NBSP). Set is now **five**, and entries 3–4 are closable by folding newlines *before* `sed` — raised in §8, not assumed, because it widens matching. The fourth example (`apiKey=`) is **REFUTED** — both sides redact it |
| 3 | §2's rationale contradicts §4.6's own table | **confirmed** | and the `[A-Z0-9_-]+_PLAN.md` claim is false (`COREDEV-2333_RELEASE_2.4.0_PLAN.md` has dots). `@2x` is now a **deferral on scope**, not a dismissal on impossibility |
| 4 | mutation accounting stale in §6/§7 | **confirmed** | "two"/"both" → **four**, plus the combined-alternation parity mutant |

**Process failure on my side, recorded because it invalidates a round.** The sibling plan was edited
*while its codex review was running*, and that reviewer correctly refused: *"A mandatory digest-bound
review cannot approve a moving target."* **The plan must be frozen for the duration of a review round.**
That is the same discipline `COREDEV-2607` demands of the reviewer, applied to the author.

### Round 4 outcome, and the sweep that replaced the enumeration

**gemini `APPROVE_WITH_NOTES` · codex `REQUEST_CHANGES` (2 findings).** Both confirmed the plan was
frozen (codex checked the target's SHA-256 twice mid-review and found it unchanged), closing round 3's
blocker. codex additionally ran **2,954 constructed adjacency and ordering vectors** against round 4's
sequential-passes fix and found the two engines agreed on all of them.

Both codex findings were confirmed by execution:

| # | finding | round-5 change |
|---|---|---|
| 1 | the five-entry exemption set is still materially incomplete — 7 more divergences, from Unicode `\s` and `re.IGNORECASE` | **all 7 reproduced.** Triggered the sweep below |
| 2 | a new fixture row gives the isolated-rule result, not the full-pipeline result §4.4 mandates | confirmed — `~a/pk_…-sk-…` yields `~[redacted]/[redacted-secret][redacted-secret]` through the real pipeline. The table is now labelled fragment-only, with the full-pipeline output pinned separately |

**Then the enumeration was abandoned for a model.** Rounds 3 and 4 each found more divergences than the
previous round claimed existed (2 → 5 → 12). That is a search that does not terminate, so an exhaustive
sweep built a **9-delta parameterised model of the shell** instead, validated byte-for-byte against
both implementations over a 40,000-input seeded corpus (0 mismatches in each direction). Divergence
became a derivable function of the two pattern sets; attributing all 13,950 observed divergences against
the full 2⁹ powerset left **0 unexplained**. §4.4 now carries nine root causes and two permanent
exemptions, expressed as **generators**, because three of the nine are provably unbounded.

**What the sweep found that four review rounds had not:**

- **Two real Python-side leaks.** `user@2x.png.example.com` — a routable address — is preserved
  entirely, because the retina lookahead's `\b` is satisfied by the following `.`. And
  `~Copyable-alice` leaks a real username, because exactly two codepoints (`-`, `.`) are both outside
  Unicode `\w` and inside the tilde body class.
- **The fix both reviewers approved was one third of the answer.** Folding `\n\r\t` before `sed` closes
  RC-C but leaves RC-A and RC-B — the Unicode-whitespace forms — leaking. §8 records the executed
  three-way comparison.
- **RC-E, the worst shape found:** the value-tail form emits `[redacted-key]` immediately followed by
  live secret material, so it passes any `'[redacted-key]' in output` assertion. §7 step 1 now greps
  the suites for exactly that shape.
- **A harmful recommendation, rejected with evidence.** One sweep agent proposed reordering SECRET
  ahead of EMAIL as "a pure reordering". Executed: it destroys legitimate addresses
  (`support@sk-corp.com` → `support@[redacted-secret]`). Trading a leak for corruption is what §3
  forbids; the rejection is recorded so it is not re-proposed.
- **Three corrections to the sweep's own agents**, made by its synthesis stage: the bearer
  case-folding attribution was wrong (`b`/`e`/`a`/`r` have no non-ASCII folds — `bKarer …` agrees on
  both sides); leave-one-out attribution manufactured 32 phantom residuals that the powerset reduced to
  0; and one divergence class (`heic` fold inside the `(?i:)` group) appeared in no agent's report.

**The honest limit, stated rather than buried:** every result is **BSD-sed only** — `gsed` is absent on
the dev host while CI is Ubuntu/GNU, and RC-I *inverts* by platform. §4.5's model-equivalence CI job on
both runners is what closes that, and §7 step 10 requires re-running the sweep under GNU `sed` before
the fixture is frozen.
