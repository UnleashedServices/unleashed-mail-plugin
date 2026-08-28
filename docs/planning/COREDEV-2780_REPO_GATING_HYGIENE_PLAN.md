# Repo Gating Hygiene Plan — trunk in CI, pin drift, and stale install resolution

**Status:** Planning
**Created:** 2026-08-28
**Last Updated:** 2026-08-28
**Basis:** `c913303` (origin/main, plugin 2.8.3) · **Tickets:** COREDEV-2780, COREDEV-2798, COREDEV-2801

## Overview

Three defects that share one shape: **a static assertion about the tree, or about which bytes are
running, that is either absent, self-invalidating, or authoritative over the truth it should track.**

| ticket | defect | today |
|---|---|---|
| COREDEV-2780 | 20 trunk linters configured, wired into **nothing** | bad lints merge freely |
| COREDEV-2798 | the COREDEV-2619 inventory pins line numbers in files that are *prepended to* | **every release** reds the test |
| COREDEV-2801 | a plugin version no source serves is still reachable | fixes silently do not reach sessions |

They are planned together because fixing them separately would produce three near-identical
arguments about "assertions that must stay green without becoming noise", and because 2798's fix is
a precondition for 2780 — turning on a blocking gate over a test that reds every release would make
the gate the problem.

## Approach

### §1. COREDEV-2780 — trunk gates the DIFF, never the tree

**The measurement that constrains everything.** `trunk check --all` on a clean tree at `c913303`:

    Checked 226 files
    240 unformatted files · 562 security issues · 9027 lint issues (3968 auto-fixable)

So **`--all` must never be the gate.** It would red `main` and every PR on day one, and a gate that
is red by default trains people to ignore it — the exact failure COREDEV-2641's plan-citation linter
already demonstrates in this repo (it fails on 26 of 27 plans and was therefore never adopted into
the local gate, which is how a shifted line pin reached CI red on PR #67).

**The gate is diff-scoped.** `trunk check` with no `--all` checks changed files against the merge
base. New and changed code must be clean; the 9027-issue backlog stays with COREDEV-2787 and blocks
nobody.

**Required, not advisory.** The ticket asks the question; this plan answers it. An advisory lint job
is a job people stop reading — and this repo's own posture is that every other validator runs in
strict/error-promoting mode (`--strict` on assembly and hooks, `VERSION_SYNC_ENFORCE=strict`,
`claude plugin validate --strict`, `shellcheck -S warning`). Advisory would make trunk the only
non-binding check on the board.

**Two things must be true before it is required**, and both are cells in §5:

1. `trunk check` on a PR touching only unrelated files must **pass** — i.e. the backlog genuinely
   does not leak into diff scope. If it does, the diff scoping is not what it claims.
2. A deliberately bad file must **fail** it. A gate that cannot fail is not a gate — the defect
   COREDEV-2711 r17 caught in its own §7.17.

**Explicitly out of scope:** remediating the 9027 findings (COREDEV-2787) and the scheduled
markdown-link-check job (COREDEV-2778).

### §2. COREDEV-2798 — stop pinning line numbers into prepend-only files

`docs/planning/COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json` freezes 31 sites by **line number** plus
`sourceSha256`. Two pin into `CHANGELOG.md` and `README.md` — the two files a release *prepends* to.
Measured on the 2.8.3 release: the pins moved +25 and +26 lines, content unchanged, and
`M3_1_InventoryDrift` failed. `sourceSha256` matched at the new line in both cases, which is how the
correct pins were derived.

**The line number is the defect.** It restates a location another file owns, and it added nothing —
the hash already located both sites uniquely.

**Fix: content-addressed for prepend-only files.** For sites whose `path` is `CHANGELOG.md` or
`README.md`, the assertion becomes "exactly one line in this file hashes to `sourceSha256`", and the
recorded `line` is a **hint that the test re-derives**, not an assertion. The identity assertion is
strictly preserved: a genuine content change still has no matching hash and still fails.

**Rejected alternative — exempt the two files.** That weakens the check to nothing for them; the
inventory exists precisely to notice when this content changes.

**Rejected alternative — a regeneration script only.** `generate-callers-exemptions.py` proves the
pattern works and is worth adding *as well*, but on its own it makes a human re-run a command every
release to keep a green test green, which is the same tax in a different currency.

### §3. COREDEV-2801 — a version no source serves must not be reachable

**Cause not identified. This plan does not pretend otherwise.** Four hypotheses were tested and
eliminated (stale scopes; stale fork; a release/tag pin; VS Code caching) — recorded on the ticket so
they are not re-tried. What is established:

* `2.7.0` exists in exactly one file, `~/.claude/plugins/installed_plugins.json`, and in no
  marketplace record, catalog cache, or editor storage;
* `main` has not served it since `13d5c2b` (Aug 7);
* that file **is** rewritten by updates — and the 2.7.0 entries survive the rewrite untouched;
* four live sessions were bound to it.

**So this section plans a DIAGNOSTIC and a DETECTOR, not a fix.** Planning a remedy for an
unidentified cause is how COREDEV-2711 revision 3 shipped a design built on a mis-measurement.

* **§3a — the experiment (blocking for any remedy).** `claude plugin update` at **user scope**,
  outside any project, then re-read the record. Both entries advancing and staying advanced ⇒
  scope-local updates, and the remedy is documentation plus cache pruning. A 2.7.0 entry reappearing
  ⇒ something writes it, and the long-lived sessions are the first suspect. **No remedy is designed
  until this runs.**
* **§3b — the detector, which is useful either way.** A preflight comparing the *loaded* plugin
  version against the repo's `plugin.json`, emitting a diagnostic on mismatch. This is what would
  have surfaced COREDEV-2769 immediately instead of costing a mis-measured plan revision — a session
  bound to a stale install is now the leading explanation for it, and nothing announced the binding.

## Milestones

- [ ] M1: Fix COREDEV-2798 first — content-addressed pins for prepend-only files, plus cells proving
      a relocation passes and a real content change still fails.
- [ ] M2: Add the trunk job to `plugin-ci.yml`, **diff-scoped**, initially `continue-on-error: true`,
      and observe it across at least two real PRs.
- [ ] M3: Promote to required once M2 shows no backlog leakage; add the required context to ruleset
      `Control` **only after** the job has produced check runs (dropping/adding a context before the
      workflow emits it is how `main` was once made unmergeable — see COREDEV-2767).
- [ ] M4: Run §3a's experiment and record the outcome on COREDEV-2801.
- [ ] M5: Implement §3b's version-mismatch detector.

M3 is deliberately gated on evidence from M2 rather than scheduled.

## Files Changed

* `.github/workflows/plugin-ci.yml` — new diff-scoped trunk job
* `scripts/tests/test_transcript_path_inventory.py` — content-addressed assertion for prepend-only files
* `docs/planning/COREDEV-2619_TRANSCRIPT_PATH_INVENTORY.json` — `line` demoted to a hint for those sites
* `CLAUDE.md` — add `trunk check` to the pre-commit validate list
* a preflight script for §3b (path TBD pending §3a)

## Testing

1. **Diff scoping is real** — a PR touching one clean file passes with the 9027-issue backlog present.
2. **The gate bites** — a deliberately bad file fails it. Paired with (1) in the same run, so a
   gate that passes everything and a gate that fails everything are both caught.
3. **Relocation passes** — prepending to `CHANGELOG.md` leaves the inventory green with no edit.
4. **Content change still fails** — editing a pinned line's *content* still reds the inventory. This
   is the cell that proves the fix did not simply weaken the check.
5. **Version-mismatch detector fires** — a session pinned to an older install emits the diagnostic;
   a matching one emits nothing.

Cells 3 and 4 are a pair on purpose: (3) alone would pass against a check that asserts nothing.

## Notes

**Sequencing is the substance of this plan.** M1 before M2 because a blocking gate over a
release-breaking test is worse than no gate. M2 before M3 because required-before-observed is how
this repo previously made `main` unmergeable. §3a before any 2801 remedy because the cause is
genuinely unknown.

**Review arms must run SERIALLY** (COREDEV-2772): concurrent arms mutate the shared `.git` that the
tree fingerprint hashes, and all three r13 arms on COREDEV-2711 voided that way. Serial re-runs were
clean three for three.

**Open question for review.** §1 asserts diff-scoped-and-required is better than all-scoped-and-
advisory. The alternative — advisory over the full tree, to keep the backlog visible — is not
obviously wrong, and I would rather it be argued than assumed.
