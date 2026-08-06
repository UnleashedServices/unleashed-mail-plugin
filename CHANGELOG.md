# Changelog

All notable changes to the **unleashed-mail** Claude Code plugin are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Plugin
releases use the `MAJOR.MINOR.PATCH` version in `.claude-plugin/plugin.json` (distinct
from the host app's `MAJOR.MINORRELEASE.YYMMBB` scheme in `docs/VERSIONING.md`).

> **Maintenance:** add every change under `[Unreleased]` as you make it, grouped by
> *Added / Changed / Fixed / Removed*. When you bump `plugin.json`, move the
> `[Unreleased]` items under a new dated `[x.y.z]` heading and start a fresh
> `[Unreleased]`.

## [Unreleased]

## [2.7.0] — 2026-08-06

`COREDEV-2642` — remediation of four independent reviews (a deep review, a 34-commit audit, and two
PR #63 bot passes) run over the permission surface and transcript-handling code that shipped in
2.6.7 (`COREDEV-2619`/`COREDEV-2639`/`COREDEV-2497`). **Minor bump, not patch:** the entrypoint-only
grant policy is a new, enforced capability (`validate-plugin-assembly.py` now rejects a whole class
of grant it previously allowed), and three of the changes below are caller-visible breaks in existing
usage, not just internal hardening.

**Gate disclosure.** This release is **not** gated by the mandatory pre-implementation plan-review
process — it is post-implementation review of already-shipped code, which is evidence but not a
substitute for the "before implementation" gate CLAUDE.md mandates. The three tickets 2.6.7 shipped
under a passing gate (`COREDEV-2619`, `COREDEV-2639`, `COREDEV-2497`) are unaffected by that
disclosure; it applies to `COREDEV-2642` itself. See
`docs/planning/COREDEV-2642_PR63_REMEDIATION_HANDOFF.md` §7 for the full per-ticket table.

### Security

- **Every model-invocable skill's grants replaced wildcards with exact entrypoints.** A
  model-invocable skill can be entered by the model's own decision — one that content in a reviewed
  file can steer — so everything a skill lists is pre-approved with **no user gesture**. Four
  wildcards were broad enough to matter:
  - `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)` had pre-approved the destructive cleanup tool's
    `--apply` flag and `pty-capture.py <any path> -- <any command>` — arbitrary child execution
    writing anywhere. Removed from `codex-review`, `gemini-review` and `review-synthesis`.
  - `Bash(codex *)` allowed any codex invocation, including `-s danger-full-access`, outside every
    wrapper. Replaced by `scripts/review/audit-codex.sh`, which hard-codes `-s read-only` and
    `xhigh` and takes the reviewer from a closed allowlist.
  - `Bash(agy *)` let `agy` run outside its isolation harness — `agy` has no read-only mode and has
    already once implemented a plan instead of reviewing it (2.6.4, `COREDEV-2607`). Replaced by
    `scripts/review/preflight-agy.sh`, which takes no caller input at all.
  - `Bash(git *)` on `pr-review` was every git command, including `reset`/`clean`/`push`, on a skill
    that reads untrusted PR content. Replaced by `scripts/review/changeset.sh`.

  Bare `Write` became `Write(docs/planning/**)`, and bare `Agent` became the enumerated agent types
  each skill body actually spawns (both the bare and the `unleashed-mail:`-namespaced spellings, since
  a consumer install resolves either), in `brainstorm`, `implement` and `pr-review`.

  **Supersedes the 2.6.7 record for `implement` and `pr-review`.** The 2.6.7 entry above is an
  unedited historical record of what 2.6.7 shipped (`Bash(python3 …/review-verdict.py *)` on
  `implement`, `Bash(git *)` on `pr-review`) — read this entry, not that one, for their current
  grants: both now hold `Read, Grep, Glob, Agent(<enumerated types>)` plus one scoped `Bash` grant
  onto `scripts/review/*` (`resolve-plan-gate.sh` for `implement`, `changeset.sh` for `pr-review`).
  `implement` also dropped a dead `review-verdict.py *` grant left over after its verify moved into
  `resolve-plan-gate.sh` — pre-approving the artifact writer inside the gate skill whose own prose
  forbids running the gate there.

- **`validate-plugin-assembly.py` now enforces the entrypoint-only policy** rather than merely
  modeling it: hard failure for bare `Write`/`Edit`/`Agent`/`Bash`, VCS and reviewer-CLI wildcards, and
  a wildcard in the *script path* of a `bash`/`python3` grant; advisory warning for toolchain
  trampolines (`xcrun`, `swift`, `xcodebuild`), which are the real build tools the knowledge skills
  describe rather than a reviewer-CLI escape hatch. The reviewer that opened this work named three
  skills; the validator found **17 further instances across 8 knowledge skills** — this repo's own
  rule ("don't grant unscoped `Bash`/`Write`/`Edit` on a pure-knowledge skill") being broken in the
  tree that states it. All are reference skills, so the grants are simply gone.

- **The seven advisory toolchain grants are gone too, after measuring what they bought.**
  `macos-debugging`, `spm-management` and `swift-tdd` held `Bash(xcodebuild *)` / `Bash(xcrun *)` /
  `Bash(swift *)`. **Three were dead** — the command appears nowhere in the skill body, and
  `spm-management` granted `Bash(swift *)` while its own prose says the `swift` CLI does not apply to
  this project. **Every live one sits inside a compound block** (`set -o pipefail` … `| tail`), which
  Claude Code decomposes per subcommand, so `set -o pipefail`, `tee` and `tail` being ungranted meant
  the block prompted regardless: the grant never pre-approved the thing it existed for. The skills
  keep working and cost nothing measurable; the advisory tier stays as a tripwire for *new* grants
  rather than a standing exception list, and a test now asserts the shipped tree carries zero
  advisories — counting the skills it walked, so an empty walk cannot pass for a clean one.

- **`spm-management` no longer documents an unbounded derived-data wipe.**
  `rm -rf ~/Library/Developer/Xcode/DerivedData/*` deletes the build state of every Xcode project on
  the machine, unrecoverably, as the remedy for one project's packages failing to resolve. Scoped to
  `DerivedData/Unleashed_Mail-*`, with Xcode's own Clean Build Folder named as the route that needs no
  shell at all. The command was never granted — this is about what a model-reachable skill *teaches*.

- **The review prompt operand is contained to the repository.** The capture helpers are the exact
  entrypoints the bullets above introduced — and both are reached from model-invocable skills that
  pre-approve `capture-*-review.sh *`, so the *model* picks the operand. The helpers checked only
  that the file was readable, then fed `$(cat "$PROMPT")` to the reviewer CLI verbatim: `../secret`,
  or a symlink to one, was exfiltrated to a third-party service by a skill the model can enter on its
  own. `scripts/review/bind-prompt.py` now refuses any operand that is a symlink, is not a regular
  file, is empty, or resolves outside the repository — **before** the CLI is launched, which is the
  only point at which refusing still means anything.

- **The reviewer sub-agents no longer inherit `Bash`.** `security-reviewer`, `concurrency-reviewer`,
  `ux-perf-reviewer` and `accessibility-auditor` are read-only by contract and by prose, and all four
  only ever ran `grep -rn` — but `tools:` listed `Bash`, which is unscoped by construction: a sub-agent
  tool list takes bare names, so `Bash` there is *every* command. Since `swift-reviewer` spawns all
  four, a prompt-injected finding in a reviewed file reached arbitrary execution through an agent whose
  own description says it audits for exactly that. The four now list `Read, Grep, Glob`;
  `swift-reviewer` keeps `Bash` (it genuinely needs it) and gained `disallowedTools: Write, Edit,
  NotebookEdit`.

- **The binding sidecars are written with `O_NOFOLLOW | O_EXCL`.** The shell wrote
  `<transcript>.promptsha256` with a plain `>` redirect, in a file whose neighbours use `O_NOFOLLOW`
  against precisely this threat: a same-account process that plants a symlink there first has the
  target truncated with the gate's privileges. `O_EXCL` as well, because a sidecar that already exists
  belongs to another run and silently overwriting it destroys that run's binding.

### Fixed

- **Transcript-freshness gate no longer depends on how a path is spelled.** The layout comparison was
  lexical, so `…/HASH/./f.txt`, `…/HASH/../HASH/f.txt`, and a symlinked *ancestor* directory each
  opened the identical file while comparing unequal — the same bytes accepted or refused by
  punctuation. Closed by `dirname`-only `realpath` resolution: the ancestry is resolved, the leaf
  never is, so a symlinked *leaf* is still refused.
- **A case-mangled path bypassed the same check.** The layout comparison was case-SENSITIVE while
  this gate runs on default-case-insensitive APFS, so `…/Unleashed-Mail/…` opened the identical file
  and classified as legacy. Closed separately, by comparing casefolded — not by the resolution change
  above.
- **TOCTOU: the gate validated one file and recorded another's digest.** Freshness opened the
  transcript, validated it and closed it; the caller then hashed the PATH again. Between those two the
  leaf can be re-pointed, so the artifact could record as reviewed evidence the digest of a file that
  never passed the check. The digest is now read from the SAME `O_NOFOLLOW` descriptor the check
  `fstat`'d, and freshness hands the caller back that path and digest rather than letting it re-resolve
  the name.
- **A symlinked allocator *parent* let a reserved leaf resolve outside its layout.** Separate fix,
  separate mechanism: the allocator now checks the parent with `lstat`, not `stat`.
- **`cleanup --check` reported green for a state `--apply` refuses only after deleting 39 files.**
  `--check` never ran the emptiness scan that `--apply` used to decide whether to proceed, so a file
  dropped between the two calls meant a green check followed by a destructive partial apply. Both
  paths now share one predicate, and the orchestrator refuses **before** the unlink phase.
- **A reused allocated transcript leaf could resurrect the previous round's verdict.** The allocator's
  reservation mode preserved the file (no `O_CREAT`) but also left it untruncated (no `O_TRUNC`), so a
  round that wrote fewer bytes than a prior one left the earlier tail in place — a failed review could
  read back as `VERDICT: APPROVE`. Fixed with `ftruncate` after the write (preserving the reservation
  invariant `O_TRUNC` would have broken), plus a wrapper-level refusal of any non-empty reserved leaf.
- **Two concurrent review rounds could cross-wire prompt and transcript.** Both recipes wrote to a
  fixed `.agy-prompt.md` / `.codex-prompt.md`; a second round overwriting the shared prompt before the
  first wrapper read it made the first round's transcript describe the *other* plan under its own
  ticket and round. Both recipes now derive the prompt filename from the round identity (see Changed,
  below) and bind the run to its plan before capture starts: `<transcript>.plan` records the plan's
  digest, and `review-verdict.py write` **refuses** an approving verdict whose per-run transcript is
  bound to a different plan. The `.promptsha256` sidecar alone did not do this — nothing ever read it,
  so transcripts captured against an unrelated ticket still produced `GATE OK — APPROVE`. "Detectable"
  is only true if something looks; the plan sidecar is the half that looks.
- **The gate verified the plan and never re-checked the evidence.** Every transcript check —
  freshness, layout, the `O_NOFOLLOW` descriptor digest, and the plan binding above — ran at **write**
  and was never re-run. `verify` re-read exactly one thing, the plan. So `transcriptSha256` was
  recorded in the artifact and no code path ever compared it back: after a passing gate, overwriting an
  approved transcript with `VERDICT: REQUEST_CHANGES` still produced `GATE OK — APPROVE`. The exposed
  window is write→verify, which is the entire implementation phase, since `implement` checks the gate
  at its Phase 1. `verify` now re-reads each recorded transcript through the same single `O_NOFOLLOW`
  descriptor the write path used and refuses on a mismatch. **Absence stays tolerated** — transcripts
  live in a purgeable XDG state directory, and macOS has already destroyed 105 of this project's
  transcripts in one sweep; failing a real approval because its evidence aged out is a false
  `GATE FAILED`, which is its own outage. A transcript that is still there and no longer matches is a
  different claim, and that one is refused. Found by running the chain end to end rather than by
  reading it: this is the third digest in this codebase that was written and never read (the other two,
  `.promptsha256` and the pre-TOCTOU freshness digest, are also closed in this release).
- **The cleanup tool removed files by name after validating them by descriptor.** `_preflight_files`
  resolves each of the 39 targets, proves each is a regular file and proves each is beneath the state
  root — and the removal loop then re-walked the resolved *string*, so every component was looked up
  again. Renaming one parent directory between the two walks retargets all 39 unlinks, and the state
  root lives under `~/.local/state`, which needs no privilege to write. Both phases now open the
  parent chain once with `O_DIRECTORY | O_NOFOLLOW`, hold those descriptors for the whole phase, and
  remove through `dir_fd` — so the object inspected is the object removed. The proof runs the swap
  against the fixed code and against the pre-fix primitive in the same instant: the old one deletes 39
  bystander files and reports success.
- **The `agy` preflight graded the CLI on its output without checking its exit status.** An `agy` that
  printed text containing `pong` and then exited non-zero — or a wrapper that timed out after emitting
  it — was reported `healthy`. The preflight is what decides whether the mandatory gate may run at
  all, so it fails closed on a non-zero capture regardless of what landed in the file.
- **The grant validator's command normalization could be walked around with a wrapper.** It reduced a
  `Bash(...)` specifier to a basename to catch `env git push` and friends, but unwrapped only a fixed
  list — so `sudo -u nobody git *` normalized to `sudo` and passed. Any wrapper outside the known list
  now rejects rather than normalizes, and the check is scoped to specifiers containing `*`, since the
  policy is about unbounded breadth (`Bash(codex --version)` is exact and fine).
- **`codex-review`'s audit recipe failed outright on Linux.** `mktemp -t codex-audit` is a BSD
  shorthand GNU `mktemp` rejects; fixed with the portable full-path template form (the commonly
  suggested `-t name.XXXXXX` only half-works — BSD treats the `X`s as literal and appends its own
  suffix — so the proof checks the produced name, not just the exit code).

### Changed

- **Breaking: `pty-capture.py` requires an out-path.** The `/tmp/pty-out.txt` default is removed — a
  run that died before writing left the *previous* run's bytes at that shared path for the next reader
  to trust, and two concurrent captures overwrote each other. Every caller in the tree already passed
  an explicit path; callers outside the tree must now do the same.
- **Breaking: both review recipes require a per-round prompt file**, `.codex-prompt-${TICKET}r${ROUND}.md`
  / `.agy-prompt-${TICKET}r${ROUND}.md`, in place of the shared `.codex-prompt.md` / `.agy-prompt.md`.
  337 of 339 prompt files on disk were already per-round names before this change; the shared spelling
  was the anomaly and is no longer accepted.
- **Breaking: the gemini arm's default model is now `gemini-3.6-flash-high`**, replacing
  `gemini-3.1-pro-high` — the model `isolated-agy-review.sh`'s own comment already claimed to run,
  and the arm that `isolated-agy-review.sh`'s own comment records as failing to emit a parseable
  verdict in 5 of 6 rounds — a rationale that had sat directly above the line still defaulting to
  the model it rejected. A
  fallback still reaches the old model via the wrapper's `MODEL` override (editing `settings.json` is
  now inert, since the wrapper always passes `--model`).
- **Five inline skill recipes extracted to granted helper scripts** — `capture-codex-review.sh`,
  `capture-gemini-review.sh`, `resolve-plan-gate.sh` (`implement`'s Design Gate), and
  `persist-verdict.sh` (shared by `review-synthesis` and `brainstorm`). Each inline recipe was a
  *compound* shell command (functions, branches, loops), which Claude Code decomposes and wants a
  grant per subcommand — so none of them matched a scoped `allowed-tools` shape and every gate round
  re-prompted. As a side effect, `capture-codex-review.sh`'s new prompt-readable check caught a real
  bug: `$(cat .codex-prompt.md)` expands empty on a missing file, so every codex capture proof had
  been running against an empty prompt.
- **The Plan Review Gate now has an end-to-end suite** (`scripts/tests/test_end_to_end_gate.py`, 13
  scenarios). Every other suite here tests one script; nothing spanned snapshot → allocate → bind →
  capture → write → verify → resolve, which is where the gate's guarantees actually live. It runs the
  real allocator, `bind-prompt.py`, `pty-capture.py`, `review-verdict.py` and `resolve-plan-gate.sh`
  against a real git repository, stubbing only `codex` and `agy` — the two things that leave the
  machine — by putting them earlier on `PATH` rather than patching the helpers, so the helpers run
  their real argv. It found the verify-time evidence gap above, which no per-script test could see
  because each script was individually correct.
- **The callers-scan exemption manifest now ships, and CI runs the scan that needs it.**
  `scripts/review/callers-scan-exemptions.tsv` was previously unshipped, so
  `callers_scan.py --root .` exited 2 before scanning a single line — and CI only ever invoked
  `--help`, which loads no manifest, so nothing caught this. The manifest is generated by a separate
  maintainer tool (`generate-callers-exemptions.py`, deliberately outside the scanned module: a
  scanner that can derive or widen its own exemptions cannot fail closed) and validated against the
  production parser before writing.
- `mktemp` invocations made GNU/BSD-portable across the affected recipes (see Fixed).

### Notes

- Asset counts are unchanged: **21 agents · 21 skills · 0 commands · 1 MCP server**. No agent or
  skill was added or removed in this release.

## [2.6.7] — 2026-08-03

### Fixed

- **Review transcripts are allocated per run and freshness-bound** (`COREDEV-2619`): both recipes reserve distinct leaves, carry each path unchanged through capture, synthesis and artifact recording, and validate its capture identity and nanosecond mtime against its own pre-dispatch launch record on both digest paths. The explicitly armed release tool deletes only the closed 39-file manifest, then its nine empty parents; its assertion/mutation suite covers set equality, forbidden primitives, containment, types, preservation, directory pruning and release metadata.

  Per-run paths prevent accidental transcript collisions and stale reuse; they do not make the gate tamper-proof, establish operator provenance, or protect a host where an attacker controls a state-directory ancestor.
  The existing `${CLAUDE_PLUGIN_ROOT}` allowed-tools grants are retained because Claude Code 2.1.0 and later expand that placeholder.

### Changed

- **Effort is inherited, not pinned; three workflow skills became model-invocable** (`COREDEV-2639`): every agent and skill now **omits `effort:`** and follows the session level, and CI accepts exactly `absent | xhigh | max` — a blanket `effort: xhigh` had been silently *capping* `max` sessions, because frontmatter effort overrides the session in both directions. Separately, `disable-model-invocation` was removed from `brainstorm`, `implement` and `pr-review`, so those three workflows can now be opened by the model rather than only by an explicit human invocation.

  **Permission consequence, and what was done about it.** Making those three skills model-invocable means their pre-approval grants can activate with no user gesture — a window the model can open by deciding a task "is an implementation". The grants were therefore SCOPED in the same release (`COREDEV-2642`): `implement` now holds `Read, Grep, Glob, Agent, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review-verdict.py *)` and `pr-review` holds `Read, Grep, Glob, Agent, Bash(git *)`. Blanket `Write`/`Edit`/`Bash` are gone; `implement` never used them itself, because it delegates every file write to `db-engineer`/`logic-engineer`/`ui-engineer` via `Agent`. `allowed-tools` is a pre-approval grant rather than a restriction, so narrowing it disables nothing — those calls simply need the normal user gesture. Note also what the effort "floor" is **not**: it constrains what may be written into an asset, not runtime effort — no in-plugin mechanism raises a `low` session, and `CLAUDE_CODE_EFFORT_LEVEL` outranks frontmatter regardless (AGENT_CONTRACTS §11).

- **Plan-review verification hardening plan** (`COREDEV-2497`): documentation only — the plan and its review record. No shipped behaviour change; recorded here because the 2.6.7 entry previously omitted it entirely.


## [2.6.6] — 2026-07-31

### Changed

- **`AGENT_CONTRACTS.md` §13 narrowed to client-facing output** (`COREDEV-2605`, plan reviewed over 19 rounds — but **it shipped without an approving round**: round 19's verdict on these bytes was codex `REQUEST_CHANGES` (3 High + 1 Medium), with the gemini arm emitting no parseable verdict line. The earlier wording, "plan gated over 19 review rounds", claimed a pass the plan's own status line does not record). **This is a scope narrowing, not a relaxation** — the five capture-roster reviewers' machine contracts are untouched and still mandatory; §13 simply stops claiming to govern them.

  §13's scope was a prose paragraph, and a paragraph listing the four intended surfaces as *"out of scope"* and the five reviewers as *"in scope"* would have passed every gate while asserting the exact inverse. It is now a **parseable four-column table** — `surface_id | producer_id | scope | anchor` — that is the only scope statement:
  exclusive and normative, with exactly nine approved triples, every field from a finite allowlist, and any unknown key or catch-all row a hard failure.

  Each row carries a repository **anchor** (`path:line`), because binding a token to a token still left every `surface_id` free to be defined elsewhere: `verdict-report` could be redefined as the JSON passed to the synthesizer while every check passed.
  The anchor's **path is pinned** to a canonical map; only its **line** is resolution-driven, and the gate walks up from the surface's fingerprint to its nearest enclosing real heading, fence-aware.

- **The payload-region invariant moved verbatim to §5 (Code Review Pipeline)**, where the contract it
  protects lives, together with the precedence rule and the six machine contracts it enumerates. §13
  keeps a one-sentence pointer.

### Added

- **§14 Blocked Subagent Handoff Contract** — the `BLOCKED — <reason>` prefix now has its own section
  rather than living inside a style section. It is used for diagnostic confirmation and Jira-tool
  failure: a subagent pausing to hand control back for external action.
- Gates in `scripts/tests/test_doc_gates.py`: a **fail-closed** `_scope_rows` parser (the previous
  `_rows` matched numbered rule rows only and, given a scope table, silently returned the rules), an
  `in`-set/`VALID_AGENTS` **disjointness** gate read from `capture.py` rather than restated, and the
  anchor-resolution gate.
- `mcp/review-synthesizer/tests/test_capture.py`: **isolated** payload-region regressions, one per
  independent rejection cause plus a positive control. `extract_status` stops on *either* prose or
  fenced content, so a single combined fixture passes against a parser that handles only one.

### Verification

Each rule is asserted to carry **exactly one** classifier from `{Adapted, Adopted, Restated
positively}` — membership, not a fixed token per rule, because §4.4 expressly permits the narrowing to
change any of them. Proved by mutation against the live gate: repointing an anchor to a non-nearest
heading, to a file's sole H1, or off its canonical path all **fail**; re-pairing a producer fails;
stripping a classifier fails; removing a rule row fails; adding `swift-reviewer` to `VALID_AGENTS`
fails. The two **positive** cases pass: changing a rule's classifier within the vocabulary, and adding
an unrelated captured specialist to `VALID_AGENTS`.

> The disjointness choice is load-bearing and was caught by that second positive case. The gate first
> asserted the `out` set **equals** `VALID_AGENTS`; the plan had explicitly rejected equality because it
> couples §13 to every future captured specialist. The positive mutant failed, and the gate was
> corrected to disjointness.

## [2.6.5] — 2026-07-31

### Fixed

- **Plugin state split across two base directories** (`COREDEV-2617`, plan reviewed over **18** rounds, not the 19 previously claimed here — and **it shipped without a reproducing approval**: round 18's double approval failed re-run at the byte-identical digest, and the re-run found a real fail-open→fail-closed regression in the agent fence).
  `CLAUDE_PLUGIN_DATA` is exported to hook and MCP subprocesses but **not** to an ordinary shell. Every
  library fell back to `${HOME}/.claude/unleashed-mail`, so a marker, log or snapshot written outside a
  hook went to a *different* directory than the one the hooks read — and neither could see the other.
  Quality markers set by a hook were invisible to a manual run, and vice versa.

  **The fix is D′: an unresolved base persists nothing.** The base resolves *only* from
  `CLAUDE_PLUGIN_DATA`; when that is unset or empty the libraries return a **poisoned sentinel**,
  `/dev/null/unresolved-plugin-base`. `/dev/null` is a character device, so every path beneath it is
  `ENOTDIR` — `mkdir`, `mktemp`, redirects and opens all fail harmlessly at a fixed, greppable location,
  and an *unguarded* caller can never compose a root path such as `/logs`. Returning the empty string
  would have done exactly that. Writers (`marker_write`, `log_append`, the round-binding mutators)
  become no-ops and return success, so no consumer's primary behaviour changes.

  Resolution is **eager and process-stable** — once, at source time, into shell variables
  (`_UNLEASHED_BASE_RESOLVED` / `_UNLEASHED_BASE_OK`), because a value first assigned inside
  `$(marker_dir)` lives in that subshell and is gone on return. Consumers whose behaviour differs when
  unresolved branch on `_UNLEASHED_BASE_OK`, never on a string comparison against the sentinel.
  Exactly **one** diagnostic is emitted per process, whether or not `scripts/lib/paths.sh` is present.

  **⚠️ State written before this fix may live in a second directory.** To find it:

  ```bash
  ls -la ~/.claude/unleashed-mail/          # the legacy fallback store
  ls -la ~/.claude/plugins/data/unleashed-mail-*/   # where hooks actually wrote
  ```

  Nothing is migrated automatically — the two stores can disagree, and picking a winner silently is
  what this ticket exists to stop. Inspect both and delete or merge deliberately.

### Added

- `scripts/lib/agent-env-bridge.sh` — one documented bridge for carrying `CLAUDE_PLUGIN_DATA` into an
  agent's Bash-tool shell, replacing per-agent copy-pasted exports. The fence passes both the data value
  and the plugin root as positional arguments, because only the exact `${…}` tokens are substituted and
  only in agent content.
- `scripts/tests/test_plugin_state_base.py` — 12 proofs: the six-cell resolution matrix
  (`paths.sh` present/absent × variable set/empty/unset, in Bash **and** zsh), no-persistence, nothing
  created at `/`, every path primitive returning the sentinel, and a lexical drift check with an
  enumerated allowlist. The drift check is proved to discriminate: it fails on a planted bypass.

### Changed

- `scripts/tests/test_shell_primitive_drift.py` — the base-path matrix now expects the sentinel for
  unset and set-but-empty. The legacy `${HOME}`-based expansion is asserted **present in `paths.sh`**
  (where its `:-` and `${HOME:-}` guarantees stay locked) and **absent from the three libraries**, since
  that fallback *was* the second store.

### Known limitation

- The drift check is a **lexical** detector, not a proof of accessor-only provenance. Path provenance is
  not statically decidable in Bash — a runtime-assembled variable name evades any static scan. It
  catches the failure this ticket is about: a copy-pasted resolver in a new primitive.

## [2.6.4] — 2026-07-30

Two fixes that landed after the 2.6.3 bump and were previously unrecorded. Both were found by using
the plan-review gate on itself rather than by a planned audit.

### Fixed

- **The gemini reviewer could write to the tree it was reviewing, and did** (`COREDEV-2607`). On
  2026-07-29 a plan review *implemented* the plan instead of reviewing it: 6 shipped scripts modified,
  5 files created, including a stray `marketplace.json` at the repo root. It emitted no `VERDICT:` line
  so the gate failed closed — the fortunate failure mode — but the edits persisted and were reverted by
  hand. The concurrent `codex` review recorded that it had re-anchored its citations against committed
  HEAD; nothing in the gate design *required* that.
  New `scripts/review/isolated-agy-review.sh` points the reviewer at a **disposable detached checkout**
  of the reviewed commit and asserts the real working tree is unchanged afterwards — a tree mutation
  **fails the round** rather than being cleaned up silently, which is `AGENT_CONTRACTS.md` §2 step 0b
  applied to the reviewer instead of the author. Four flags were tested and rejected as non-solutions
  (`agy` alone, `--mode plan`, `--sandbox`, `--sandbox --mode plan` — all four created the file and
  exited 0); the header records them so they are not re-tried. Isolation, not constraint, because `agy`
  has no read-only mode — the asymmetry with `codex`, which the gate already runs `-s read-only`.
- **Secret redaction let four Unicode fold codepoints into an ASCII value class** (`COREDEV-2609`),
  the residual the 2.6.2 entry recorded as still open. U+0130, U+0131, U+017F and U+212A now ride in the
  secret **payload** class in both the shell and Python redactors. The **anchor** is deliberately *not*
  widened: widening an unanchored prefix is what corrupted ordinary prose in the first place, whereas
  widening an *anchored* rule's payload cannot. Held by the `redactor_model.py` equivalence gate on both
  `sed` engines.

### Changed

- The 2.6.2 entry's closing line "Residual shared miss: COREDEV-2609" is superseded by the fix above.
  Left in place rather than edited — a changelog records what was true at the time.

## [2.6.3] — 2026-07-30

CI & workflow hardening — plan `docs/planning/CI_WORKFLOW_HARDENING_PLAN.md`, batching
COREDEV-2598 + COREDEV-2600 + COREDEV-2603, five review rounds. Implemented ahead of a final
dual-gate APPROVE at the maintainer's explicit direction; recorded as a workflow exception, not a
passed gate.

### Fixed

- **The PreCompact hook leaked to stderr** (COREDEV-2600). Its inline round scanner was missing two
  guards the shared `context_highest_round` has, so a `round-<20-digit>` directory — producible
  through shipped code via `UNLEASHED_REVIEW_ROUND` — printed `integer expression expected`,
  violating the stderr-clean fail-open invariant. It also recorded `"09"` where the shared helper
  returns `"9"`. Both asserted, including the JSON **type**: the field is a string, and a test that
  accepted either would miss a serialisation change.
- **`marker_mtime` returned its failure sentinel on FreeBSD** (COREDEV-2600). It branched on
  `uname == Darwin`, assuming only Darwin has BSD `stat`. A `0` there is not benign:
  `stop-quality-marker-gate.sh` computes `AGE=999999` from it and **skips the gate entirely**, so a
  platform quirk silently disabled a quality gate. `scripts/test-hooks.sh` carried its own diverged
  copy of the same shape — the harness that would have proved the fix was itself carrying the defect.
- **A genuine plan approval could not survive the mandated worktree move** (COREDEV-2603). Approval
  was bound to `os.path.realpath(plan)` — one developer's disk layout.

### Changed

- Plan identity in the verdict artifact is **repo-relative** when the plan is in a git repo, absolute
  otherwise, recorded as `planPathKind` and enforced on verify. `schemaVersion` 2 → 3, so the existing
  hard comparison rejects stale artifacts; deliberately no compatibility branch, because a v2 artifact
  without the field is the one shape where verify would compare a relative string against an absolute
  one and pass by accident. This does **not** make the artifact portable — `.verdicts/` is git-ignored
  by design, so CI and a second developer still cannot verify, and the docs now say so.
- The plugin-data base path is single-sourced in `scripts/lib/paths.sh`. Every caller keeps the inline
  expansion as a fallback: these libs are sourced standalone, and aborting on a missing `paths.sh`
  would convert three independent fail-open paths into one shared point of failure.

### Added

- **`load-check` CI job** + `scripts/ci-load-check.sh` (COREDEV-2598). Installs the checkout's own
  bytes via a scratch marketplace, proves byte identity with a per-run sentinel, drives the MCP server
  from its **own installed declaration**, and asserts the hook-manifest shape. Four mutants, each
  mapped to the assertion it fails; the mapping records one assertion that is *not* provable and is
  labelled defence-in-depth rather than claimed.
- Drift guards (`scripts/tests/test_shell_primitive_drift.py`): no `uname == Darwin` mtime branch
  anywhere under `scripts/`, the base expansion identical across all three libs with its `${HOME:-}`
  guard, no single-dash `${CLAUDE_PLUGIN_DATA-…}` default, and CI pin hygiene (no action pinned to two
  SHAs, no mutable `@vN` tags, all `CLAUDE_CODE_VERSION` pins agreeing).
- The worktree-before-plan ordering, documented on all five operator entry points with a doc gate, plus
  the plan-freeze rule: a review cannot approve a plan edited mid-round.

## [2.6.2] — 2026-07-29

Redactor defects (COREDEV-2597) — plan `docs/planning/COREDEV-2597_REDACTOR_DEFECTS_PLAN.md`, five
review rounds. Implemented ahead of a final dual-gate APPROVE at the maintainer's explicit direction;
recorded as a workflow exception, not a passed gate.

### Fixed

- `hook_redact_pii` corrupted ordinary prose. The `sk-` rule had no leading boundary and fired
  mid-word (`task-oriented` → `ta[redacted-secret]`), and the `~` rule matched any `~`-prefixed token,
  deleting the quantitative detail engineering rationale is made of (`~500ms`, `~40 percent`,
  `~40/60 split`) plus Swift's `~Copyable`/`~Escapable`.
- **Five leak classes**, each reproduced before being fixed: `api<U+00A0>key: <secret>` and
  `bearer<U+00A0><token>` (Python's `\s` accepts 23 codepoints POSIX `[[:space:]]` under `LC_ALL=C`
  does not); `api key:\n<value>` (`sed` is line-oriented and the newline fold ran *after* the rules);
  the compound `/Users/nick<U+00A0>api key: <secret>` (the shell over-consumed and ate the `api`
  anchor, so the rule never fired); `user@2x.png.example.com` — a **routable address** preserved
  entirely because the retina-exemption lookahead's `\b` was satisfied by the following dot; and
  `~Copyable-alice`, which **leaked a real username** for the same reason.
- `tr` ran outside `LC_ALL=C`, so a single invalid UTF-8 byte aborted it — truncating the message and
  leaking `tr: Illegal byte sequence` to stderr, against the repo's stderr-clean invariant.
  `permission-denied-log.sh` and `stop-failure-log.sh` already did this correctly.

### Changed

- The `sk-`/`pk_` boundary is **asymmetric**: underscore is a boundary before `sk-` (an identifier
  cannot contain `-`, so `OPENAI_KEY_sk-proj-…` redacts) and is not before `pk_` (the SQL/GRDB
  primary-key convention, so `orders_pk_customer_id_idx` survives). Keeps both properties rather than
  trading one for the other.
- The `~` rule requires a home-*path* shape (`[A-Za-z_]` + `/`), matching the definition
  `schema.py` already shipped. **Accepted residual:** a bare `~alice` with no path is no longer
  redacted — it is regex-indistinguishable from `~ten`/`~Copyable`, and both are pinned by tests so a
  future widening trips a gate.
- Whitespace is canonicalised on **both** sides *before* any rule runs. Not a widening: no pattern
  changes, only the input domain.
- `re.IGNORECASE` removed from Python's `_APIKEY`/`_BEARER` — it did *Unicode* case-folding, matching
  U+0130/U+0131/U+212A in the literals and admitting four codepoints into an ASCII value class, which
  emitted `[redacted-key]` immediately *before* live secret material. Residual shared miss: COREDEV-2609.
- Python's secret rule uses two sequential passes, not one combined alternation, which matched
  greedily from the leading prefix and disagreed with the shell.

### Added

- `mcp/review-synthesizer/redactor_fixture.py` — the single canonical parity vector list, with
  *generators* for the unbounded classes, since three root causes cannot be closed by any list.
- `mcp/review-synthesizer/redactor_model.py` — the mechanical closure: over a seeded corpus the only
  divergence must be the one documented exemption, `UNEXPLAINED == 0`. 40,000 inputs clean.
- `redactor-equivalence` CI job on **`ubuntu-latest` and `macos-latest`**. Both, deliberately: the
  `tr` root cause inverts between GNU and BSD, so a single-platform run is half a result — and the
  half that passes is the half that hides it.
- 26 parity tests with ten named mutation proofs, each rejecting a plausible wrong implementation
  rather than a `git revert`.

## [2.6.1] — 2026-07-29

Agent output style (COREDEV-2602) — plan `docs/planning/AGENT_OUTPUT_STYLE_PLAN.md`, approved through
the dual gate (gemini APPROVE + codex APPROVE_WITH_NOTES) after eleven rounds.

### Added
- `AGENT_CONTRACTS.md` **§13 Agent Output Style** — ten rules adapted from `ayghri/i-have-adhd` (MIT,
  pinned at `07684c4a`). Two adopted, seven adapted, one restated positively. Adapted rather than
  migrated: four upstream rules would have damaged machine-consumed output.
- The **payload-region invariant** — between the `Status:` line and the final fenced JSON block, nothing
  but detail fields and blank lines. Not a style preference: it is
  `capture.py::extract_status`'s behaviour, and violating it yields `None` → no sidecar →
  `UNATTRIBUTED` → a re-dispatch or `NEEDS DISCUSSION`.
- A precedence clause naming all six machine contracts the style rules must yield to, and 14 doc-gate
  tests (per-rule **row-scoped**, per-contract **section-scoped**), each mutation-proved.

### Notes
- Enforcement is documentary. `COREDEV-2604` covers the mechanical guard (report the cause, route it,
  feed it to the retry); `COREDEV-2599` covers measuring whether agents actually comply.

## [2.6.0] — 2026-07-29

Opus 5 alignment (COREDEV-2583) — plan `docs/planning/OPUS5_ALIGNMENT_PLAN.md`, approved through the
dual plan-review gate (gemini APPROVE + codex APPROVE, digest-bound) after five rounds.

### Added
- `effort: xhigh` on all 21 agents and all 21 skills, with a hard CI assertion on both axes and on the
  §11 policy sentence. Nothing set `effort` before, so every asset ran at the session's level.
- A `warnings` channel in `validate-plugin-assembly.py`: prints, never affects the exit code. Used to
  report `permissionMode`/`mcpServers`/`hooks`, which Claude Code ignores for plugin sub-agents.
- `KNOWN_SKILL_KEYS` + `check_skill_fields` — skills had no frontmatter key validation at all. Derived
  from the pinned 2.1.220 schema; `disallowedTools` is accepted (it is the runtime's canonical alias),
  `allowedTools` is rejected (it is genuinely inert).
- AGENT_CONTRACTS §5 now declares the subagent spawn-depth dependency and the ≥ 2.1.219 floor.

### Changed
- **Model tiering is three tiers**, set by consequence of being wrong rather than cost:
  `security-reviewer`, `prompt-review`, `concurrency-reviewer` → `opus` (3); orchestrator and
  implementation/diagnostic engineers → `inherit` (11); first-pass reviewers, personas and fixed-scope
  managers → `sonnet` (7). §11's rationale is rewritten; the old one argued from cost.
- `MODEL_ALIASES` is the pinned runtime's table verbatim, so `opus[1m]`/`sonnet[1m]`/`fable[1m]`, `best`
  and `opusplan` validate. `haiku[1m]`, `best[1m]`, `opusplan[1m]`, `inherit[1m]` and `default` are
  rejected — they are not in the table. The model-id regex is untouched, so COREDEV-2503 F10 holds.
- The difflib tool-name typo guard is advisory (a warning) rather than a hard failure: the allowlist is
  inherently incomplete, so a false reject blocked real tools while a missed typo merely fails at runtime.
- CI pins Claude Code 2.1.220 (was 2.1.209, eleven releases below the Opus 5 floor).

### Fixed
- `TaskOutput` and `EnterPlanMode` were **false-rejected** as typos of `BashOutput`/`ExitPlanMode`.
- `MultiEdit` is removed from `KNOWN_TOOLS` **and** hard-rejected — dropping it alone is a no-op because
  unknown tools are accepted, which had left `agents/jira-manager.md`'s deny-list entry a silent no-op.
  That entry is removed. Stale-tool messages are now per-tool; the shared one asserted "the dispatcher is
  `Agent`, not `MultiEdit`", which is nonsense.
- Four documentation defects, each now gated by a mutation-proved test: README's false "all five review
  agents now run on `opus`"; CLAUDE.md's incomplete alias list and missing effort guidance; the
  alias-versus-version-pin conflation in CLAUDE.md and AGENT_CONTRACTS; and a superseded
  `claude-sonnet-4-6` id in `agents/ai-engineer.md`.

## [2.5.3] — 2026-07-20

Correctness-audit remediation (COREDEV-2525) — 49 findings from `docs/audits/PLUGIN_AUDIT_2026-07-19.md`
(10 major, 29 minor, 10 info), none caught by the shipped validators. No agents/skills added (21/21/0/1).

### Fixed
- **Review-synthesizer gate fail-opens** (MAJ-4/5): `is_abs_or_traversal` now rejects tilde/home paths
  (`~/…`, `~user/…`), and the `synthesize.py` CLI refuses to scope explicit findings against the bundled
  demo changeset (and exits 2 on unknown flags) instead of silently printing APPROVE.
- **`/implement` `$ARGUMENTS` shell injection** (MAJ-9): the Design Gate binds the argument once via a
  quoted heredoc, so quotes / `$( )` / backticks in it are literal data; multi-line values are refused.
- **Stale plan-review transcripts** (MAJ-10): `/gemini-review` + `/codex-review` `rm -f` their fixed
  `/tmp` transcript path before each dispatch, so a never-started/killed wrapper leaves it absent
  (→ MISSING → fail-closed) instead of a previous round's APPROVE.
- **`CLAUDE_PLUGIN_DATA` split** (MAJ-6): `swift-reviewer`'s Step-2 Bash fences export the placeholder so
  the capture-collection path resolves the same reviews dir the hooks wrote to.
- **`AGENT_CONTRACTS` drift** (MAJ-1/2): §11 model tiers aligned to the shipped frontmatter; §5 step 2
  rewritten to the shipped ratchet (a capture never certifies).
- **Pre-commit PII scan was a no-op** (MAJ-7): rewritten to a correct `grep -nE` scan over all staged
  text files (advisory) plus enforcing `gitleaks --staged`.
- **Skill/agent grant over-reach** (MAJ-8, MIN-27/28): eight knowledge skills no longer pre-approve
  unscoped `Bash`; five no longer grant `Write`/`Edit`; the review workflow skills gained scoped grants.
- Numerous doc-drift, dead-reference, case-sensitivity (sensitive-file-guard), fetch-to-file
  (bash-write-scan), hook-matcher (MultiEdit symmetry, no-op removal, timeouts), and stale-plan-status
  fixes (MIN-1/3/4/5/6/7/8/9/10/11/13/15/17/25/26/29; INF-1/3/4/5/6/7/10).

### Added
- Validator coverage for what previously drifted silently: §11 model-tier alignment, the six-copy
  reviewer roster, hook `matcher`-key typos, agent `skills:` and `.mcp.json` path resolution, and
  manifest-description + CHANGELOG-entry counts. 15 new regression tests across the MCP and scripts suites.

## [2.5.2] — 2026-07-17

### Fixed
- **Plugin scripts unreachable in consumer installs** (COREDEV-2504): the plan-gate script references in
  agent/skill bodies used the shell-fallback spelling `${CLAUDE_PLUGIN_ROOT:-.}`, which Claude Code does
  **not** substitute (only the exact `${CLAUDE_PLUGIN_ROOT}` token is substituted inline in agent/skill
  content) — so it reached the shell literally and resolved to `.` (the consumer app repo, which ships none
  of these scripts), making every reviewer read as "missing" and the fail-closed Plan Review Gate
  un-passable in any consumer install. Reverted the 8 sites to the bare token (this corrects the F6
  regression in 2.5.1, which had introduced `:-.` at `swift-reviewer.md` Step-4). Also raised `codex-review`'s
  pty capture timeout 600→1200 s to survive mandated `xhigh` runs, and added a mutation-proved doc-gate test
  (`test_doc_gates.py`) whose contract regex enforces the exact `${CLAUDE_PLUGIN_ROOT}` token — flagging the
  `:-.`/`:?` fallback, suffix typos, unbraced, brace-spacing, and case variants, while documenting the
  identifier-typo / unicode-homoglyph boundary as out of scope.

## [2.5.1] — 2026-07-16

### Fixed
- **Quality/review-gate fail-open remediation** (COREDEV-2503): a v2.5.0 audit surfaced fail-opens in the
  gates this plugin ships (the repo's own validators don't cover gate logic). All 14 confirmed findings are
  closed, each with a regression test that fails when the fix is reverted; two audit items were excluded
  after verification (a SIGPIPE claim refuted; a "dropped parity rule" reclassified as gate-drift, F9):
  - **F1** `review-verdict.py` — removed the `captureId` short-circuit that let two forged distinct
    captureIds behind one identical transcript manufacture a passing gemini+codex approval; the
    content-digest floor now always runs.
  - **F2/F3** `review-synthesizer` — one shared `is_abs_or_traversal` helper (folds separators) closes the
    backslash-traversal `changed_files` bypass and quarantines absolute/`..` finding paths instead of
    demoting them to a bogus provisional APPROVE.
  - **F4/F12** `sensitive-file-guard.sh` — replaced the O(n²) parser + quote-blind greps with one structured
    quote/escape/operator-aware linear lexer (`lib/bash-write-scan.py`): fixes the timeout fail-open, the
    quoted-operator over-ask and mid-word-quote bypass, adds the missing write-form arms
    (subshell/`sed -i`/`>|`/`find -delete`/`xargs`/`dd`), corrects the exit-code contract (`ask`=exit-0,
    parse-failure=exit-2 deny), and adds a 256 KiB DoS backstop.
  - **F5** Stop-gate sentinel is now keyed by session (not just repo+commit), `chmod 600`, with an
    all-session reset on a passing marker.
  - **F6** `swift-reviewer` Step-4 fails closed (build-verify fence + `exit "$BUILD_VERIFY"`) so
    build/lint/test can't silently skip. **F8** bounded secure read. **F10** anchored model-id regex.
    **F11** `capture.py` `O_NOFOLLOW|O_EXCL` writers. **F13** CFR state-machine contradictions. **F9**
    provider-parity gate drift.
  - **B1** pty `--timeout=N` form. **B2** verify-path stray-reviewer reject. **B4** stale-`Task` reject.
    **B6** `build-verify.sh` compiles once (`build-for-testing`/`test-without-building`). **B7** CFR
    drift-guard. (B3 dropped — no real duplication; B5/B8 deferred to a follow-up.)

## [2.5.0] — 2026-07-16

### Added
- **Plan Review Gate made usable end-to-end and hardened** (COREDEV-2492): `/implement` now resolves a
  feature name or path to *the* tracked plan (exact-stem match; a pure substring must be named
  explicitly), refuses anything outside `docs/planning/` (realpath containment — closes the
  `..`/symlink/symlinked-root and same-basename bypasses), and deterministically verifies a
  plan-digest-bound Combined-verdict artifact via [`scripts/review-verdict.py`](scripts/review-verdict.py)
  before any code is written. The artifact requires a non-empty, real-SHA-256, DISTINCT transcript per
  reviewer (by capture path / wrapper capture-id, falling back to digest), a validated combined verdict,
  and the mandatory gemini+codex identities — enforced identically at write and verify, so neither a
  mis-recording caller nor a hand-tampered artifact can manufacture a false approval. `pty-capture.py`
  emits a `<out>.captureid` per run for that provenance.
- **P0 audit remediation** (COREDEV-2486): fixed six fleet-wide silent-failure classes — sub-agent
  `tools:`/`disallowedTools:` frontmatter (removing the silently-ignored `allowed-tools` key), positional
  SwiftLint invocation, the PostToolUse JSON contract, plugin-scoped reviewer-capture prefixing,
  gitleaks secret-scanning (checksum-pinned) + `SECURITY.md`, and the org rename to UnleashedServices.

### Changed
- **Dropped the unimplementable scripted `WAIVED` path** (COREDEV-2493): `AGENT_CONTRACTS.md` §2 had
  promised a user-authorized `WAIVED:` marker that nothing implemented and nothing could — "only the
  user may waive" is unenforceable when the agent is the process running the script. Removed rather than
  faked; §2 now documents the real recovery (the user chooses; a workflow exception is recorded without
  claiming the gate passed). `agy` gets `--print-timeout 18m` so a real plan review no longer dies at the
  5-minute default, and the wrapper timeout sits above it so a diagnosable error survives.
- **Review tooling refreshed to Codex `gpt-5.6-sol` @ `xhigh`** (COREDEV-2495): Codex 5.6 "Sol"
  (`codex-cli` 0.144.4). The upgrade silently reset the config's reasoning effort to `low`, so every
  review recipe now passes `-c model_reasoning_effort=xhigh` explicitly — resilient to that reset and
  correct on any machine, instead of trusting a config value the upgrade proved fragile.
- **`swift-reviewer` Step 4 extracted to a shipped, unit-tested script** (COREDEV-2489 / Item 5):
  the inline build / lint / test block moved to [`scripts/review/build-verify.sh`](scripts/review/build-verify.sh)
  (reads the Step-1 `$CHANGED` list on stdin; `✅`/`❌` per gate; exits non-zero if any hard gate failed).
  Saves ~0.3k tokens/review-spawn (~24 lines; 4–5k is the projected total once all four inline blocks are extracted) and makes the gate logic testable — `scripts/tests/test_build_verify.py`
  covers it with mocked `xcodebuild`/`swiftlint` (runs in CI without a toolchain). `pr-review` now relies
  on that single Step-4 run instead of launching its own `xcodebuild test`, **deduping the double
  test-suite run**. Only the self-contained Step-4 block was extracted; the `$CHANGED`/`$BASE_BRANCH`
  state-sharing steps stay inline, and a **canary** (`scripts/review/README.md`) covers the live-review
  verification neither the gate nor unit tests can do autonomously.
- Org/marketplace renamed to `UnleashedServices/unleashed-mail-plugin` — see the README install
  section for the one-time migration from the old `npranson-unleashed-mail-plugin` marketplace.
- `AGENT_CONTRACTS.md` §9/§10 updated to the omit-`tools:`-to-inherit-MCP mechanism (portable across
  install prefixes; restricted via `disallowedTools`), with `prompt-review`'s deliberate Bash drop noted.
- **The 3 orchestration commands are now skills** (COREDEV-2489 / P2-16): `brainstorm`, `implement`,
  and `pr-review` moved from `commands/*.md` to `skills/<name>/SKILL.md` as `disable-model-invocation`
  skills (custom commands have merged into skills). The `/unleashed-mail:brainstorm | implement |
  pr-review` invocations are unchanged. Asset counts are now **21 agents · 21 skills · 0 commands · 1 MCP**.
- **Enforcement hooks now default to their active modes** (COREDEV-2489 / audit hooks-scripts.5).
  `sensitive-file-guard.sh` defaults to `ask` (was `warn`) — editing a sensitive file
  (Keychain/OAuth/entitlements/DB/WebView) now surfaces a permission prompt; in non-interactive /
  `dontAsk` / `-p` contexts the "ask" **denies** the operation that would prompt (the intended
  fail-safe). Opt out with `UNLEASHED_SENSITIVE_GUARD_MODE=warn|off`. `stop-quality-marker-gate.sh`
  defaults to `enforce` (was `warn`) — a lint-fail marker now blocks the turn once
  (`decision:block`+`reason`, fail-open + TTL/commit-guarded). Opt out with
  `UNLEASHED_STOP_GATE_MODE=warn|off`.

### Fixed
- **Secret scanning now gates `alpha`** (COREDEV-2494): the `plugin-ci.yml` triggers filtered on `main`
  only, so 56 of `alpha`'s 57 commits merged with **zero checks** — every audit PR targeted `alpha` and
  reported "no checks". `claude plugin validate` (added in #36) and actionlint (#31) had therefore never
  executed on the branch they were added to. Triggers are now `[main, alpha]`, and `SECURITY.md` records it.
- **`firebase-debug.log` secret-scan exemption is commit-scoped** (COREDEV-2494): it was a blanket path
  allowlist, so a brand-new credential committed into that exact filename scanned clean — a permanent blind
  spot on precisely the filename that caused the original leak. Now pinned to the two commits the file ever
  existed in; verified against gitleaks 8.30.1 that a new secret in that filename is still caught.
- **`swift-lint-check.sh` respects `swiftlint:disable` directives** (COREDEV-2494): waived lines no longer
  produce false blocks. The waiver must NAME the rule, and a trailing ` - <rationale>` (this project's
  mandated convention) is no longer parsed as a rule list. A broken/misconfigured SwiftLint CLI now falls
  back to the greps instead of silently disarming the Stop gate. Force-try/cast elevation is production-only.
- **`pty-capture.py` runs on macOS system Python again** (COREDEV-2494): a PEP-604 `X | None` annotation
  (added in #30) is a syntax error on 3.9.6, crashing every PTY-wrapped review capture.

## [2.4.2] — 2026-06-27

Hook-manifest integrity gate (COREDEV-2338). Surfaced while auditing whether the plugin's hooks
actually "hold": the behavioral harness (`scripts/test-hooks.sh`) and `validate-plugin-assembly.py`
gate hook *scripts* and JSON-parse the manifest, but nothing checked that `hooks/hooks.json` can
actually fire — a renamed/missing hook script, an invalid event name, or a typo'd tool matcher all
passed CI. Reviewed with Codex (converged REQUEST_CHANGES → APPROVE over three rounds). No
agents/skills/commands added (counts stay 21 · 18 · 3 · 1).

### Added
- **`scripts/validate-hooks.py`** (stdlib-only) — static integrity check of `hooks/hooks.json`:
  every event key must be in a `KNOWN_EVENTS` allowlist (hard-fail on unknown/typo'd events, which
  would never fire); tool matchers of the simple `Tool|Tool` form must reference known tools
  (catches `Bsh`, `Write|Edti`) while regex matchers like `^(Read|Write)$` are compile-checked, not
  falsely rejected; every `command` must resolve to an existing, non-empty `scripts/<file>`;
  `bash -n` parses each referenced script; `--require-manifest` fails when a hooks-shipping plugin's
  manifest is missing.
- **CI gate** in `.github/workflows/plugin-ci.yml` — runs `validate-hooks.py --root . --strict
  --require-manifest` before the existing `test-hooks.sh` harness.
- **Pre-commit wiring** in `scripts/pre-commit-checks.sh` — runs the validator in warn mode
  alongside the other plugin validators.

### Changed
- **`scripts/test-hooks.sh`** — documented its coverage boundary: it hardcodes hook-script paths, so
  the manifest↔script linkage, event names, and matcher tokens are gated by `validate-hooks.py`; the
  PostToolUse `swift-lint-check.sh` hook is not behaviorally simulated on the Linux CI runner.
- **Plugin bumped to 2.4.2.** `README.md` H1 + What's-New updated; asset counts unchanged.

## [2.4.1] — 2026-06-27

Host-app documentation sync (COREDEV-2335) — corrects seven stale/contradictory spots where the
plugin's docs/agents had drifted from the host app (`Unleashed Mail`). Each finding was independently
verified against both repos and adversarially cross-checked before editing. Plugin-only scope (no
app-repo edits); no agents/skills/commands added (counts stay 21 · 18 · 3 · 1). (An eighth audit
finding — the reviewer Output-Contract capture claim — was already resolved by COREDEV-2328 in 2.4.0
and needed no change.)

### Changed
- **Review-command invocation model** — bare workspace names (`/gemini-review`, `/codex-review`,
  `/create-feature-plan`) are documented as **canonical** across the plugin's docs, agents, and
  skills; the plugin's `/unleashed-mail:*` forms remain as the bundled alias (`review-synthesis`
  stays namespaced — it has no bare workspace copy). Per user decision.
- **Build-number mechanism** reworded everywhere from "Scheme Pre-Action on Archive" to a **Run
  Script Build Phase on the app target** (install/Archive builds only, **not** a Pre-Action — a
  Pre-Action bumps one archive too late; see `docs/VERSIONING.md`). The Post-Action commit/push
  script is retained.
- **Plugin bumped to 2.4.1.** `README.md` H1 + What's-New updated; asset counts unchanged.

### Fixed
- **SwiftLint merge gate** — replaced bare `swiftlint --strict` with the app's two-pronged gate
  (changed-file `swiftlint --strict <files>` + whole-repo `swiftlint lint --strict --baseline
  swiftlint-baseline.json`; the committed baseline suppresses the pre-existing `NSRegularExpression`
  backlog — COREDEV-2290) across 11 references; running the bare whole-repo form would have failed
  every gate.
- **Stale build number** `1.02.260501` → `1.02.260601`; `Config/Base.xcconfig` flagged authoritative
  so the literal can't silently re-drift.
- **Obsolete dual email-detail guidance** removed across the plugin docs, agents, and skills
  (`CLAUDE.md`, `README`, `swift-reviewer`, `ui-engineer`, `accessibility-auditor`,
  `accessibility-patterns`); `SimpleEmailWebView` is the sole production renderer (`EmailWebView`
  was removed). `swift-reviewer`'s verify step now runs **both** SwiftLint arms (changed-file
  strict + whole-repo baseline), matching the host app's gate.
- **Commit/ticket policy** in `AGENT_CONTRACTS.md` and `commands/implement.md` made **mandatory**
  (was "optional"), matching the host app's `type(COREDEV-XXXX): description` rule.
- **Stale plugin self-references** `v2.2.2` → current (`codex-review` skill, AGENT_CONTRACTS
  cross-references).
- **`set -o pipefail`** added to six piped-`xcodebuild` blocks (`commands/implement.md`,
  `commands/pr-review.md`, `swift-tdd`, `spm-management`, `xcode-build-fixer`) so a failing
  build/test isn't masked by `| tail`.
- **Synthesizer test count** `78` → `159` in the live `README.md` reference (verified: the suite
  runs 159).

## [2.4.0] — 2026-06-27

### Added
- **`prompt-review` — static AI-prompt / call-site reviewer, fully wired into the review pipeline**
  (COREDEV-2330 agent + COREDEV-2329 wiring; under Epic COREDEV-2126 GARI safety). A read-only 5th
  specialist reviewer that statically audits AI prompts and provider call sites (jailbreak/injection
  surface, missing refusal paths, format/context leaks, unsanitized ingress of untrusted email/web
  content, inline prompts outside `PromptRegistry`, unscoped tools, PII-in-logs). It ends its report
  with a fenced ` ```json ` findings array + a `Status:` line and is now a first-class member of the
  deterministic pipeline: a new **`ai-safety`** category family (10 categories) + `DISPLAY_BUCKET`
  ("AI Prompt Safety") and `prompt-review` ownership in `mcp/review-synthesizer/` (`schema.py`,
  `synthesize.py`, the manual-fallback `README.md`); added to the `swift-reviewer` Step-2 panel
  (owner of the `ai-flow` structural subsystem), the status-read recipe, and the consolidated report;
  added to both SubagentStop/SubagentStart capture allowlists + `VALID_AGENTS`; and to
  `/unleashed-mail:pr-review`, `/unleashed-mail:implement`, `agent-orchestration`, `AGENT_CONTRACTS.md`,
  and the Codex review mirror. Agent count **20 → 21** (README + `plugin.json` already bumped with the
  agent; no plugin version bump — hooks/schema aren't asset-counted). Tests cover the capture, the
  category↔schema **exact-equality** invariant (guards the silent-drop trap), and `ai-safety`
  routing/render. Plan-review gate: codex `APPROVE_WITH_NOTES` + gemini `APPROVE_WITH_NITS`.
- **Reviewer-capture round binding — a stable per-cycle signal from `SubagentStart`** (COREDEV-2326,
  closes Epic COREDEV-2321). The SubagentStop reviewer capture's round was previously only *inferred*
  (`capture.py:select_round`), which cannot perfectly group cycles under interleaved timing — a late
  reviewer from an earlier cycle could mis-bucket into a later round. A new **`SubagentStart` producer
  hook** (`scripts/capture-reviewer-round-start.sh` + a `SubagentStart` entry in `hooks/hooks.json`)
  now *freezes* the round for each of the four specialist reviewers **at spawn**, keyed by its unique
  `agent_id`, in a per-checkout binding file under `.state/`; the SubagentStop capture
  (`scripts/capture-reviewer-verdict.sh`) looks it up by the **same** `agent_id` and exports
  `UNLEASHED_REVIEW_ROUND`, so each capture lands in its **originating** round regardless of
  completion order, then consume-once clears the binding. New `scripts/lib/context.sh` helpers
  (`context_highest_round` — decimal-normalized; `context_review_round_bind`/`_lookup`/`_clear`;
  TTL + bounded `.state` sweep). Observe-only and fail-open end-to-end: an absent/stale/foreign-slug
  binding, a missing `python3`/`date`, or `UNLEASHED_REVIEW_ROUND_SIGNAL=off` all fall back to the
  shipped `capture.py` inference; an explicitly-set `UNLEASHED_REVIEW_ROUND` is never clobbered. No
  change to `capture.py`'s consumption logic, the findings-array shape, or the SubagentStop contract.
  PII-free (only a slug token, opaque ids, an int, and an epoch are persisted). The round number
  mirrors `capture.select_round` (advance past a final prior slot, else reuse), so a same-round repair
  re-run overwrites the empty slot rather than splitting the cycle. Tests: `test-hooks.sh`
  104 → **132** (interleaving fix, repair/per-agent reuse, stale/cross-agent isolation, decimal
  arithmetic, consume-once, kill switch, explicit-not-clobbered, producer exclusions, zsh-NOMATCH) and
  `test_capture.py`
  143 → **144** (override↔dedup round-trip). Plan-review: codex `APPROVE_WITH_NOTES` + gemini
  `APPROVE` (`docs/planning/REVIEW_ROUND_PRODUCER_PLAN.md`). No version or asset-count change (hooks
  are not counted by the version-sync validator).

### Changed
- **review-synthesizer now consolidates overlapping AI-safety ↔ security findings into one
  `prompt-review`-owned row** (`mcp/review-synthesizer/synthesize.py`, COREDEV-2332; follow-up to
  COREDEV-2329, parent COREDEV-2126). When `prompt-review` and another reviewer flag the **same
  defect on the same lines** in their own taxonomies — `pii-log-leak` vs `privacy`,
  `unsanitized-ingress` vs `webview`/`html-sanitization`, `unscoped-tool` vs `privacy` — the
  consolidated report previously showed **two** rows and the `ai-safety` ownership branch never
  fired. Added those as **category-level** `_OWNERSHIP_MERGE_PAIRS` (not family-level — an unrelated
  `jailbreak-surface`↔`oauth` or `unsanitized-ingress`↔`network` overlap deliberately stays two
  rows), so the pair now clusters into a single row routed to `prompt-review` while every fix is
  still cross-linked (cluster-not-collapse — no finding is ever dropped), and a co-located **security
  blocker still leads the row text and still gates the verdict**. Tests: `test_synthesize.py`
  151 → **159** (per-pair positive, `network`/unrelated negatives, non-overlap, mixed-severity
  blocker-survives). No version or asset-count change (synthesizer-internal). Plan-review gate: codex
  + gemini both `APPROVE`.
- **Reviewer Output-Contract status is now persisted through the SubagentStop capture path**
  (`mcp/review-synthesizer/capture.py`, COREDEV-2328). Each captured reviewer's `Status:`
  (`COMPLETE | BLOCKED | PARTIAL` + BLOCKED/PARTIAL detail fields) is written to a self-describing
  **sibling `<agent>.status` JSON** beside its `<agent>.json` findings — PII-redacted, observe-only,
  fail-open; the findings-array shape and all its consumers (`is_final_capture`, `synthesize._load`)
  are unchanged. Extraction is **CommonMark-fence-aware** and constrained to the report's top-level
  Output-Contract trailer (a `Status:` inside a code fence or behind prose is never taken) and
  ReDoS-safe. `swift-reviewer` Step 2 now reads the sidecar from the same round as the findings (via
  a new portable, unit-tested `context_latest_round_dir` helper in `scripts/lib/context.sh`),
  validates the sidecar's `agent`+`status`, and honours `BLOCKED`/`PARTIAL` on the pre-collected
  capture path too — degrading to face value when the sidecar is absent/corrupt/unrecognized (never
  a false fail-closed). Closes the Item-12 gap where a captured `BLOCKED` reviewer could read as a
  clean `[]`. No version or asset-count change (the `synthesize.py`/`schema.py` interface and the
  SubagentStop hook contract are untouched).

### Fixed
- **`ai-engineer` doc drift — removed two non-existent Swift symbols from the agent docs**
  (COREDEV-2331, parent COREDEV-1834; surfaced during the `prompt-review` plan-review). `agents/ai-engineer.md`
  documented the GARI provider/tool API using `HTTPBasedAIProvider` and `AIToolDefinition`, **neither of
  which exists in `Sources/`** — an engineer (or the `ai-engineer` agent) following the docs literally
  would emit non-compiling code. Fixed across the plugin: `HTTPBasedAIProvider` is now consistently
  labelled **PLANNED (COREDEV-1837), not yet built** — same treatment `AISafetyPipeline` already had —
  while today's reality (cloud providers inherit `BaseAIProvider` + conform to `AIProviderProtocol`,
  own their `URLSession`, and use a per-provider `buildRequestBody(...)`) is stated plainly; the
  fabricated `AIToolDefinition` is replaced with the real `AITool` schema + `ToolHandlerProtocol` /
  `Set<AgentTool>` / `ToolCall` model registered via `ToolRegistry.register(_:)`. Adjacent fabricated
  examples (`AIAgentPipeline(provider:…)`/`execute(operation:…)`, the closure-handler registration, the
  test snippets) were corrected to the real `configure(...)` + `execute(input:configuration:)` shape so
  no doc snippet emits non-compiling code. Swept the same drift from `CLAUDE.md`, `agents/logic-engineer.md`,
  `AGENT_CONTRACTS.md`, `README.md`, the `swiftlint-config` sample lint message, and the `prompt-review`
  agent's own guardrail. Docs-only — no behaviour, version, or asset-count change. Plan-review gate:
  codex + gemini both `APPROVE`.
- **`<agent>.status` sidecar write hardened** (`capture.py`, PR #16 review) — `_write_status` now
  builds the payload as `{**status, "agent": agent}` (explicit `agent` **last**) instead of
  `dict(agent=agent, **status)`, so the trusted hook-allowlisted `agent` can never be collided-over
  or silently overwritten by a future transcript-derived `status` key (today the pinned
  `_STATUS_FIELDS` carry none — behaviourally identical, just collision-proof). Added a regression
  test asserting a duplicate (skipped) SubagentStop **preserves** an existing `BLOCKED`/`PARTIAL`
  sidecar untouched (`test_capture.py`, 142 → 143), pinning the early-return ordering that the
  Item-12 guarantee depends on. Added a `context_latest_round_dir` leading-zero test
  (`test-hooks.sh`, 103 → 104) that locks the base-10 (non-octal) `[ -gt ]` round comparison —
  `round-08`/`round-09` order numerically and never raise a `value too great for base` error — so a
  future refactor to `(( … ))` arithmetic can't silently regress it.

## [2.3.1] — 2026-06-26

### Added
- **Plan-review synthesis skill** (`/unleashed-mail:review-synthesis`,
  `skills/review-synthesis/SKILL.md`) — a read-only skill that combines the two captured
  plan-review transcripts (gemini → `/tmp/agy-out.txt`, codex → `/tmp/codex-out.txt`) into one
  auditable **Combined verdict** block (`APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES |
  DISAGREEMENT`; normalizes the CLI's `NITS → NOTES`; references findings by location/topic, never
  echoing PII; surfaces a one-approve / one-reject split as `DISAGREEMENT` rather than averaging; a
  missing/empty transcript can never claim `APPROVE`). Kept **distinct** from the code-review
  `synthesize_review` MCP enum (`APPROVE_WITH_SUGGESTIONS` / `NEEDS_DISCUSSION`). Wired into
  `AGENT_CONTRACTS.md §2` as plan-review step 3a, with one-line pointers in `gemini-review` /
  `codex-review`.
- **Reviewer Output-Contract status enum** — the four specialist reviewers (`security`,
  `concurrency`, `ux-perf`, `accessibility`) now emit a `Status: COMPLETE | BLOCKED | PARTIAL` line
  (immediately before their JSON findings array, which stays the final block) that is **orthogonal**
  to the findings, so a reviewer that *couldn't run* returns `BLOCKED` + `[]` instead of an empty
  `[]` that reads as a clean pass.
- **Decision-support option tables** in `/unleashed-mail:brainstorm` — a design-phase **Step 4b**
  that, only on a genuine architectural fork, presents 2–4 options in a comparison table (with a
  mandatory **Parity-Impact** column, S/M/L effort, a `(Recommended)` row, no emoji) and calls
  `AskUserQuestion` to record the chosen fork before the plan document. `AskUserQuestion` added to the
  command's `allowed-tools`.

### Changed
- **`swift-reviewer` Step 5 consumes the reviewer status.** `BLOCKED` routes to NEEDS DISCUSSION as a
  Needs-Confirmation uncertainty — **not** a `category: verification` blocker (which is
  confirmed-by-construction → REQUEST CHANGES); `PARTIAL` keeps the completed-scope findings and
  records a non-gating `verification` warning (escalated to NEEDS DISCUSSION if a Remaining file is
  structural). No synthesizer (Python) change. `skills/agent-orchestration/SKILL.md` handoff and
  `AGENT_CONTRACTS.md §5` updated to match.
- **Plugin bumped to 2.3.1.** `README.md` (H1, the `20 agents · 18 skills · 3 commands · 1 MCP
  server` counts, What's-New, architecture skill list, and Skills table) and
  `.claude-plugin/marketplace.json` reflect the new `review-synthesis` skill (skills 17 → 18).

## [2.3.0] — 2026-06-25

### Added
- **Deterministic review synthesizer (MCP).** A local, zero-dependency stdio MCP
  server at `mcp/review-synthesizer/` that performs the orchestrator's Step-5
  synthesis in code instead of LLM prose: schema validation/quarantine, scope filter
  (changeset + `structural-pipeline` carve-out), category-aware dedup with line-range
  overlap and cross-family ownership routing (cluster-and-cross-link, never silently
  drop), a provisional verdict, and `blockersToVerify` for the agent to confirm.
  Declared in the root `.mcp.json`; exposed to `swift-reviewer` as
  `mcp__plugin_unleashed-mail_review-synthesizer__synthesize_review`.
- **Unit tests** for the synthesizer (`mcp/review-synthesizer/tests/`, 78 stdlib
  `unittest` cases): schema edge cases, dedup/ownership/scope/verdict, render
  (findings-only, no leaked verdict), tool-input validation, and the MCP JSON-RPC
  protocol (initialize / tools.list / tools.call / ping, non-object & non-JSON
  resilience, quarantine-not-crash). Run:
  `python3 -m unittest discover -s mcp/review-synthesizer/tests`.
- **Bundled test fixtures** at `mcp/review-synthesizer/samples/` (sample findings +
  `changed_files.txt`); the standalone `synthesize.py` CLI and the README examples use them.
- **Design notes** in `mcp/review-synthesizer/README.md` — the hybrid architecture, the
  server↔agent division of labour, and the authoritative dedup rules.

### Changed
- **`swift-reviewer` Step 5 now delegates synthesis to the MCP tool.** The agent
  passes the reviewers' JSON findings to the synthesizer (which dedups/merges in
  code), then owns the **verify gate** (open each `blockersToVerify` `file:line`,
  confirm) and the **final verdict** — a clean split, since the server has no repo
  access. Falls back to applying the documented rules manually if the tool is
  unavailable.
- **Review-agent system overhaul.** Reviewers (`security`, `concurrency`, `ux-perf`,
  `accessibility`) now end with a structured JSON findings array
  (`severity · confidence · sourceAgent · category · file · line · lineEnd · scope ·
  finding · evidence · fix`) instead of a prose/markdown table; `swift-reviewer`
  cross-references and deduplicates across them. `concurrency-reviewer` broadened to
  the **correctness owner** (logic/error-handling). Provider-parity, test-coverage,
  and build/lint/test now emit gating `verification` rows. Added a **verify gate**
  (confirm blockers against the code before REQUEST CHANGES; unconfirmable →
  NEEDS DISCUSSION) and **structural-pipeline** whole-pipeline review for changes to
  key subsystems. `accessibility-auditor` moved to `opus` (all five review agents now
  `opus`).
- **AGENT_CONTRACTS.md §5** (Code Review Pipeline) and the README architecture/agents
  sections document the synthesizer step and the verify-gate split.
- **`.gitignore`** now ignores Python bytecode (`__pycache__/`, `*.py[cod]`) for the
  bundled stdlib MCP server.

### Fixed (PR review — Codex / Gemini / Copilot)
- **`synthesize_review` validates its inputs and fails closed.** `findings` and
  `changed_files` are required and type-checked; a missing, non-array `findings` or a
  missing/non-`list[str]` `changed_files` is rejected with JSON-RPC `-32602` instead of
  being coerced or defaulted — previously a string (or omitted) `changed_files`
  collapsed the scope set, mis-scoping every finding to pre-existing and letting a real
  blocker reach a provisional APPROVE.
- **Malformed JSON-RPC `params` (e.g. an array) returns `-32602`**, not a `-32603` crash.
- **Protocol-version negotiation** — `initialize` returns a version the server actually
  supports instead of echoing an arbitrary client-supplied one.
- **`id: null` is a request, not a notification** — it now receives a reply (JSON-RPC).
- **The verify gate gates on ANY blocker in a cluster**, not just the ownership-routed
  lead (consistent with `blockersToVerify`).
- **The standalone CLI `_load` quarantines** unreadable / malformed / wrong-shape
  findings files instead of crashing; deterministic file-descriptor close
  (`with open(..., encoding="utf-8")`).
- **Consolidated-table cells are escaped** — a `|` or newline in a reviewer's
  `finding`/`fix` no longer injects spurious columns/rows into the Markdown table.
- **Accessibility ownership ties resolve to `accessibility-auditor`** regardless of
  input order — a `ux-perf` row tagged `a11y` no longer outranks the auditor.
- **Empty-array JSON-RPC `params` is rejected** (`-32602`) instead of being coerced to `{}`.
- **Quarantined findings fail closed** — a schema-invalid row (e.g. a typo'd `category`
  on a real blocker) forces `NEEDS_DISCUSSION` instead of letting the provisional verdict
  be a clean `APPROVE`, so a parse slip can't silently turn a blocker into an approval.
- **Corrected the plugin MCP tool name** to `mcp__plugin_unleashed-mail_review-synthesizer__synthesize_review`
  — Claude Code preserves hyphens in plugin/server names (only chars outside `[A-Za-z0-9_-]`
  become `_`), so the earlier all-underscore form would not have matched the real tool.
- **Orchestrator global gates always gate (P1).** `verification` (build/lint/test),
  `parity`, and `test-coverage` findings aren't tied to a changed file — their `file`
  is a scheme/target/label — so they now gate regardless of the diff. Previously a red
  build emitted as a `verification` blocker was scoped out to pre-existing and the
  provisional verdict came back `APPROVE` with no `blockersToVerify`. The `swift-reviewer`
  verify gate also now treats these self-emitted rows as confirmed-by-construction (it
  ran the command) — it gates them without trying to `Read` a scheme:0 location and never
  downgrades them to NEEDS DISCUSSION.
- **The consolidated row leads with the blocker's text** in an ownership-routed cluster
  (e.g. a security `keychain` warning that owns a `token-race` blocker) — a 🔴 row no
  longer reads as the lower-severity owner with the blocker hidden behind a category name.
- **A missing reviewer routes to NEEDS DISCUSSION as an uncertainty, not a `verification`
  blocker** — reconciles the fail-closed path with the verification-gate carve-out (which
  treats `verification` rows as confirmed-by-construction → REQUEST CHANGES).
- **MCP robustness (per spec):** the `findings` input schema is fully permissive
  (`items: {}` — accept any JSON) so a malformed row, even a non-object like
  `null`/string/array, reaches the server and is quarantined individually instead of
  being rejected client-side (which would defeat quarantine); the tool result mirrors the
  provisional verdict + `blockersToVerify` into the text `content` (not only
  `structuredContent`) for clients that don't surface structured output; and the stdio
  loop uses `readline()` to avoid the read-ahead buffering that can deadlock a pipe.
- **UTF-8 + doc consistency:** the stdio server (and its subprocess test) pin UTF-8 so
  the report emoji survive a non-UTF-8 locale (minimal CI containers); the server
  README's fallback scope rule and the `agent-orchestration` skill are updated to match
  the always-gate and missing-reviewer behaviours above.
- **Reviewer paths are canonicalised before scoping** — leading/trailing whitespace, a
  leading `./`, and Windows backslashes are normalised on both the finding's `file` and
  the `$CHANGED` set, so `./Unleashed Mail/…`, `A.swift `, or `Sources\A.swift` matches
  `git diff --name-only` output instead of mis-scoping a real changeset blocker to
  pre-existing.
- **CLI fails closed on a bad `--changed`** — an explicit but missing/typo'd path now
  exits `2` instead of scoping every finding to pre-existing and exiting `0` APPROVE. The
  stdio server also pins `stderr` and uses `errors="replace"` so a malformed byte on the
  pipe degrades to U+FFFD rather than crashing `readline()`.
- Removed the superseded `prototypes/hybrid-review-synthesizer/` sandbox — a buggier
  duplicate of the shipped server; its design is captured in the server's README.

## [2.2.4] — 2026-06-25

### Added
- Shared PTY capture wrapper (`scripts/pty-capture.py`) so the `codex-review` and
  `gemini-review` CLIs render reliably from non-TTY contexts; surfaced in the README
  skills table.
