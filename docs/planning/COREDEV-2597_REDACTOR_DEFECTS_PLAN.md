# Redactor Defects Plan

**Status:** Planning — round 2, awaiting re-gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29 (round 2)
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

**Fix — the boundary class is a decision, stated explicitly.** Require start-of-string or a
**non-alphanumeric** character before the prefix, preserving that character in the replacement:

```sh
shell   -e 's#(^|[^A-Za-z0-9])(sk-|pk_)[A-Za-z0-9._-]{8,}#\1[redacted-secret]#g' \
python  _SECRET = re.compile(r"(?<![A-Za-z0-9])(?:sk-|pk_)[A-Za-z0-9._-]{8,}")
```

**Underscore counts as a boundary, so `foo_sk-abcdefgh123` IS redacted.** This is deliberate.
`_sk-` and `_pk_` are not natural prose or identifier shapes (identifiers cannot contain `-`;
hyphenated words do not contain `_`), whereas concatenated leak shapes such as `OPENAI_KEY_sk-proj-…`
and `backup_sk-live-….json` are plausible and would silently survive a `\W` guard. **Accepted cost,
recorded so it is visible:** a SQL-style name like `orders_pk_customer_id_idx` redacts to
`orders_[redacted-secret]`. `pk_` is the conventional primary-key prefix, so this can appear in
reviewer evidence about a GRDB schema — see §5 and §8.

**Non-ASCII is deliberately not in the guard.** Under `LC_ALL=C` (hook-io.sh:227) POSIX ERE cannot
express a Unicode word class, so adding one would break the shell/Python parity §4.4 exists to
guarantee. Both runtimes already agree that `cafésk-abcdefgh123` redacts.

> *Round-2 correction.* Round 1's text said "require a non-word character" (= `[^A-Za-z0-9_]`) in prose
> while prescribing `[^A-Za-z0-9]` (underscore permitted) in the regex — **the paragraph contradicted
> itself**, and an implementer could satisfy either reading. The contradiction, not the choice, was the
> defect. A reviewer preferring the strict `\W` policy may say so — but then both the prose *and* the
> regex must move together.
>
> A round-1 reviewer also reported that the guard "omits non-ASCII", citing `café-sk-…`. **Refuted by
> execution:** the character immediately before `sk-` there is the hyphen, which no candidate guard
> treats as a word character. Under true adjacency (`cafésk-…`) both candidate guards behave
> identically. The claim cannot be demonstrated by any two-way comparison of the proposed guards.

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
- **sub-threshold negative:** `sk-abcdefg` unchanged
- **policy-sensitive rows** (pin the §4.1 decision): `foo_sk-abcdefgh123` → redacted;
  `orders_pk_customer_id_idx` → redacted

**Anti-implementation controls — both must FAIL, and this is the mutation proof for §4.1:**
1. an implementation that drops `\1` from the shell replacement (eats the boundary character);
2. an implementation anchored only at `^` (leaves `token sk-abcdefgh123` fully unredacted).

Round 1's controls pass both. §6's blanket "revert it and the test fails" does **not** close this,
because neither mutant is a revert.

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
- **The label must live in its own `-e`.** BSD `sed` rejects `:t;s/…`.
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

**This is a consistency fix, not a new policy.** `mcp/review-synthesizer/schema.py:200-201` already
ships and tests this exact definition: *"A plain `~backup.swift` (tilde with no following `/`) is a
legal repo filename and is NOT matched — only a home-dir REFERENCE."* `capture.py:57`'s own positive
control is `~alice/Library/…`, with a path. `hook-io.sh:216-217`'s purpose clause is path-shaped
(`/Users/<name>/…`, `-archivePath`). No shipped test anywhere asserts a bare `~alice` is redacted.
Both reviewers and the round-1 plan missed this precedent two files away.

**Proof.** Round 1's sole positive control `~alice/secrets` cannot discriminate — it redacts
identically under the shipped buggy rule *and* both candidates. Required, on **both** implementations:

- **positive** (fail if redaction is disabled): `~alice/secrets` → `~[redacted]/secrets`;
  `~root/.ssh/id_rsa` → `~[redacted]/.ssh/id_rsa`; `(~bob/tmp)` → `(~[redacted]/tmp)` (punctuation
  prefix); `x-~carol/y` → `x-~[redacted]/y` (proves `-` is a boundary, so `--flag=~user/…` redacts);
  `see /Users/nick/z and ~nick/z` → both halves redacted in one pass
- **loop assertion:** `~a/~b/x` → `~[redacted]/~[redacted]/x`. Delete `-e ':t' -e 'tt'` and this must
  fail. This is §4.2's mutation proof.
- **preservation** (fail if the rule is widened back): `~500ms`, `~2x faster`, `~40 percent`,
  `~ten minutes`, `~half the rows`, `takes ~one second`, `~L147`, `~Copyable`, `~Escapable`,
  `~40/60 split`, `~1/2 of the rows`, `split ~50/50`, `~1a2b`, `cost ~$5`, `~/Documents`,
  `backup~alice/x` (embedded `~` must not match)
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
2. shadow `tr` with a function that writes `"${LC_ALL-<unset>}"` to a **file** — not stderr, because
   the fix's own `2>/dev/null` would swallow a stderr probe — then `builtin command tr "$@"`;
3. assert the file contains exactly `C`; assert the helper's captured stderr is empty; assert normal
   redaction output is unchanged.

Verified: unfixed fails both assertions, fixed passes both, on BSD and GNU alike. **Both traps above
are stated because either one silently re-hollows the proof.** Add a one-line comment on the test
noting that the shadow is a shell *function*, so a future refactor to `/usr/bin/tr` would make it go
green vacuously.

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

**The one surviving tilde divergence, recorded honestly.** Under §4.2's rule the shell/Python tilde gap
collapses from "shell corrupts every `~Word`" to a single enumerable case: the slash-joined Swift form
`~Copyable/~Escapable`, where Python's lookahead preserves it and ERE cannot. Zero occurrences in-tree
today, but it is plausible reviewer shorthand. **List exactly that input in the exemption set; do not
claim byte-identical tilde rules.** Whitespace folding is a third enumerated exemption
(`a\n\n\tb` → shell `a   b`, Python `a b`).

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
| `permission-denied-log.sh:35` | `reason` | **Yes — the only genuinely free text.** Writes to `logs/denied-commands.jsonl`, which has **no reader anywhere in the repo**, and `:11` documents that Claude Code ignores this hook's output |
| `stop-failure-log.sh:33` | `error_type` / `error` | No — post-clamped by `tr -cd 'A-Za-z0-9_.-'`, which strips `~` and `@` regardless |
| `sessionstart-restore.sh:77` | session hint | No — composed only from `ticket` (`COREDEV-NNNN`/`vX.Y.Z`/`1.0X`/`unknown`), `branch_slug` (that or a hex hash), a repo-relative `docs/planning/*_PLAN.md` path, and an integer round. **This is the one caller whose output reaches model context** |
| `precompact-snapshot.sh:35` | `PLAN` | No — the same constrained plan path |

This is what converts a contested "High — live corruption" into a documented Medium: the asymmetry is
real, but the only caller that can carry an asset filename writes to a file nothing reads. Keep this
table — it is the audit trail, and it is also the reason §2's `@2x` exclusion is defensible.

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
| §4.1's underscore boundary redacts a legitimate SQL identifier | Medium | Accepted and pinned: `orders_pk_customer_id_idx` is a fixture row with its expected output, so the decision is visible and a change trips a test. Raised for reviewers in §8 |
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

**New for round 2 — the one thing reviewers should actively contest.** §4.1's boundary class treats
underscore as a boundary, so `foo_sk-…` redacts and `orders_pk_customer_id_idx` redacts with it. The
alternative (`\W`, underscore is a word character) preserves the SQL identifier but lets
`OPENAI_KEY_sk-proj-…` survive. The plan picks leak-prevention over identifier preservation and pins
both rows as fixtures. **Is that the right trade for a repo whose reviewer evidence discusses GRDB
schemas?**

**Second, narrower:** §4.2's rule leaves `~9lives/x` unredacted (digit-leading username + slash). The
argument for `[A-Za-z_]` is `useradd`/`adduser` `NAME_REGEX` and 134/134 local accounts being letter-
or underscore-first. Some systems permit digit-leading names via `useradd --badname`. **If that is
considered reachable, the fallback is the slash-only rule plus explicit fraction preservation** — which
costs `~40/60`, `~1/2`, `~50/50`.

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

## 10. Round-1 gate outcome and what changed

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
