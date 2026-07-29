# Redactor Defects Plan

**Status:** Planning — awaiting dual plan-review gate
**Created:** 2026-07-29
**Last Updated:** 2026-07-29
**Ticket:** `COREDEV-2597` — `hook_redact_pii` corrupts ordinary prose and truncates on invalid UTF-8
**Epic:** `COREDEV-2582` — Opus 5 readiness and autonomous end-to-end mode
**Branch:** `feat/COREDEV-2597-redactor-defects`
**Target version:** `2.6.0` → **`2.6.1`** (patch: bug fixes, no asset-count change).
**Blocks:** `DECISION_JOURNAL_PLAN.md` (`COREDEV-2585`) — split out of it on the **independent**
recommendation of both plan reviewers, which also resolves that plan's scope contradiction ("no change
to the reviewer capture pipeline" vs. modifying `capture.py`'s redactor).
**Sequencing:** `COREDEV-2604` also modifies `capture.py`. Land this first — it is a contained
regex/locale fix; 2604 restructures the failure-reporting path.

---

## 1. Context

`hook_redact_pii` is the plugin's redaction helper. It is **not** a PII scrubber — it is a
secret-shape scrubber, and that limitation is owned by `COREDEV-2585`'s design, not by this ticket.
This ticket fixes three defects in what it *does* claim to do.

These are **live bugs, not future risk.** `mcp/review-synthesizer/capture.py:159-161` already runs
model-authored `finding` / `evidence` / `fix` prose through the same patterns on every reviewer capture,
so reviewer evidence is being corrupted today.

All three were found by executing the shipped function, and both plan reviewers reproduced them
independently.

## 2. Scope

**In:** three defects in `scripts/lib/hook-io.sh::hook_redact_pii` (two of which are mirrored in
`mcp/review-synthesizer/capture.py::redact_pii`), and tests on both sides.

**Out:** making the redactor an actual PII scrubber. It provably leaves personal names, phone numbers,
SSNs, postal addresses, `ghp_` PATs, `AKIA…` keys and `password=…` untouched. That limitation is
`COREDEV-2585`'s to design around (pointers, not prose) and **must not** be quietly widened here —
broadening the pattern set is how §4.1's corruption class was introduced in the first place.

**Explicitly out of scope, decided rather than overlooked:** the two **deliberate** Python-only
exemptions at `capture.py:51-58` — `_EMAIL`'s `@2x` retina-filename lookahead and `_TILDE`'s
`~Copyable`/`~Escapable` lookahead. They are commented as intentional and tested. This plan does **not**
port them to the shell side; that divergence is real but separate, and `COREDEV-2600` owns keeping the
two implementations from drifting further.

## 3. Guiding principle

> **A redactor that damages correct text is worse than one that misses a secret.** A missed secret is a
> known, bounded gap that the design works around; corrupted text is silent data loss in the artifact
> the reader is relying on. Every fix below narrows a pattern or fixes a locale bug — **none widens what
> is matched.**

Corollary: every fix needs a **positive control**. A test that only proves `task-oriented` survives
would also pass if redaction were disabled entirely — which is the exact failure mode the reviewers
flagged when this was still part of 2585.

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

**Fix.** Require a non-word character (or start-of-string) before the prefix. Do **not** widen the
trailing class. POSIX ERE has no `\b`, so the shell side needs an explicit alternation or a
`[^A-Za-z0-9]` guard with the boundary character preserved in the replacement; the Python side can use
`(?<![A-Za-z0-9])`.

**Note for the implementer.** The shell and Python fixes are **not** textually identical — ERE lacks
lookbehind. Whatever form is chosen, the two must agree behaviourally, which is what the parity test
below asserts.

**Proof.** Preservation cases for all four words above, **plus positive controls** proving a real
`sk-proj-abcdefgh12345678` and `pk_live_abcdefgh12345678` are still redacted, on **both**
implementations. Revert either fix → its side fails.

### 4.2 — The `~` rule has no path context and eats approximations (High)

**Root cause.** `scripts/lib/hook-io.sh:231`:

```sh
-e 's#~[A-Za-z0-9._-]+#~[redacted]#g' \
```

Intended for `~username` home-directory paths, it matches any `~`-prefixed token. Verified:

| input | output |
|---|---|
| `~500ms` | `~[redacted]` |
| `~2x faster` | `~[redacted] faster` |
| `~40 percent` | `~[redacted] percent` |

This is the sharpest of the three for `COREDEV-2585`: engineering rationale is full of `~Nms` / `~N%`,
so the redactor **silently deletes exactly the quantitative justification** a decision journal exists to
preserve.

**Fix.** Require the home-path shape the rule is actually for — a `~user` followed by a path separator,
or at minimum a leading boundary plus a non-digit first character. **A digit immediately after `~` is
never a username.**

**Proof.** Preservation for `~500ms`, `~2x`, `~40 percent`; **positive control** that `~alice/secrets`
is still redacted. Both implementations.

### 4.3 — `LC_ALL=C` misses `tr`, so invalid UTF-8 truncates and leaks stderr (High)

**Root cause.** `scripts/lib/hook-io.sh:227,236`. `LC_ALL=C` is applied to `sed`; the trailing
`| tr '\n\r\t' '   '` runs **unlocalised**, and the `2>/dev/null` binds to `sed` only. Under a UTF-8
locale a single invalid byte makes `tr` abort:

- stdout is **truncated at the bad byte** — everything after it is lost;
- `tr: Illegal byte sequence` **escapes to stderr**, contradicting the repo's stderr-clean/fail-open
  invariant (`scripts/lib/log.sh:11-12`).

Isolating the stages confirms `sed` handled the bytes fine; `tr` is what aborts.

**Fix.** `LC_ALL=C tr … 2>/dev/null`. The precedent is already in-tree and correct at
`scripts/stop-failure-log.sh:33` and `scripts/permission-denied-log.sh:31` — which is what shows the
omission inside the helper is an oversight, not a convention.

**Note for the implementer.** Shell-only. The Python side has a different ingress: it must be proven to
**replace** the bad byte without truncating later text, which is a separate assertion, not the same one.

**Proof.** Feed `name \xff\xfe jane.doe@corp.com end`: assert the text **after** the bad byte survives,
the embedded email is still redacted, and **stderr is empty**. Python ingress asserted separately.

### 4.4 — The two implementations can silently re-diverge (Medium)

**Root cause.** The shell and Python redactors are independent code. They already disagree on three of
four probe inputs (the two deliberate exemptions plus whitespace folding: `a\n\n\tb` → shell `a   b`,
Python `a b`). Nothing detects further drift.

**Fix.** A **shared fixture list** exercised by both suites, asserting identical output except for an
explicitly enumerated, commented exemption set. Adding an exemption to one side without updating the
list fails CI.

**Note for the reviewer.** This overlaps `COREDEV-2600` (the general drift guard). Scope here is **only
the redactor pair**; 2600 owns the base-path copies and the round scanners. If 2600 lands first, this
becomes a fixture contribution rather than new machinery.

**Proof.** Add an exemption to one side only → the parity test fails naming the input.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| A narrowed pattern stops redacting a real secret | **High if unguarded** | §3's corollary: every fix ships a positive control. A preservation-only test would pass with redaction disabled entirely. |
| The shell and Python fixes diverge because ERE lacks lookbehind | Medium | §4.1's note; §4.4's parity fixture asserts behavioural agreement rather than textual identity. |
| Fixing `tr` changes output for existing callers | Low | Only affects inputs containing invalid UTF-8, which currently **truncate** — any change is strictly an improvement. Existing capped callers are unaffected. |
| Scope creep into "make it a real PII scrubber" | Medium | §2 excludes it explicitly; that limitation is `COREDEV-2585`'s to design around. |
| Conflict with `COREDEV-2604` in `capture.py` | Medium | Land this first; 2604 restructures reporting, this touches only the regexes. |

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

Baselines to hold: `test-hooks.sh` **302**, synthesizer **191**, scripts **269**, counts `21/21/0/1`.

**Mutation proof required for every fix** (§4.1–§4.4): revert it and the new test must fail — including
the positive controls, which must fail if redaction is disabled rather than merely narrowed.

## 7. Implementation order

1. §4.3 — the `tr` locale/stderr fix (shell only; smallest, no regex semantics).
2. §4.1 — the `sk-`/`pk_` boundary, both sides, with positive controls.
3. §4.2 — the `~` path context, both sides, with positive controls.
4. §4.4 — the shared parity fixture.
5. Version bump to 2.6.1 + CHANGELOG.

## 8. Open questions for the reviewers

1. **Should the shell side gain the two Python exemptions (`@2x`, `~Copyable`)?** They are deliberate
   and tested in Python and absent in shell, so `Icon@2x.png` → `[redacted-email]` and `~Copyable` →
   `~[redacted]` through any shell caller. This plan leaves them out to keep the diff to proven defects,
   but the asymmetry is a live corruption of Swift identifiers in exactly the repo this plugin serves.
2. **How strict should the `~` fix be?** "Non-digit first character" fixes the measured cases cheaply;
   "requires a following `/`" is stricter and truer to the rule's intent but would stop redacting a bare
   `~alice` with no path. Which is preferred?
3. **Does §4.4's parity fixture belong here or in `COREDEV-2600`?** Putting it here gets the guard
   sooner; putting it there keeps all drift machinery in one place.

## 9. Notes

- Every claim was verified by executing the shipped function; both plan reviewers reproduced all three
  defects independently while reviewing `COREDEV-2585`.
- The redactor is **not** a PII scrubber and this ticket does not make it one — see §2.
- `scripts/stop-failure-log.sh:33` and `scripts/permission-denied-log.sh:31` already apply `LC_ALL=C` to
  their own `tr`, which is the evidence that §4.3 is an oversight rather than a deliberate choice.
