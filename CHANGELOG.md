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
substitute for the "before implementation" gate CLAUDE.md mandates.

**Correction (PR #63 recheck).** An earlier version of this paragraph called `COREDEV-2619`,
`COREDEV-2639` and `COREDEV-2497` "the three tickets 2.6.7 shipped under a passing gate". None of the
three supports that, and for 2619 it contradicted **this PR's own banner**, which states plainly that
it shipped under an explicit maintainer exception with no Combined-verdict artifact. This is
merge-decision evidence, so it is restated per ticket:

| ticket | actual gate status on the shipped bytes |
|---|---|
| `COREDEV-2619` | **maintainer exception, not a passing gate.** Its plan's status line reads `NOT GATED`; the approving rounds never landed simultaneously and there is no artifact under `docs/planning/.verdicts/`. |
| `COREDEV-2639` | **no plan-gate evidence exists.** There is no `COREDEV-2639` plan in `docs/planning/`, so there was nothing to gate. The "full gate green" recorded in Jira was a validator/test sweep, later relabelled a Plan Review Gate pass without supporting evidence. |
| `COREDEV-2497` | **re-gate required**, by its own plan's status line. Earlier rounds gated earlier bytes; the current ones have not been re-gated, and its implementation has not landed. |

See `docs/planning/COREDEV-2642_PR63_REMEDIATION_HANDOFF.md` §7 for the full per-ticket table.

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

- **The prompt/plan binding now binds the bytes the reviewer actually consumed.** The first version
  hashed the prompt and the plan *independently*, which is two correct digests of the wrong pairing: a
  prompt reading `REVIEW TARGET: PLAN_B.md` bound cleanly against `--plan PLAN_A.md`, and
  `review-verdict.py write` produced an `APPROVE` artifact for Plan A off a review of Plan B. Three
  mechanisms, closed together because each one's failure is the others' silent success:
  - **Agreement.** The prompt must name the plan it is bound to, and must not name a different
    `*_PLAN.md`. The rule is symmetric on purpose — requiring only "does it name the right plan"
    accepts a prompt that names both and asks about the other.
  - **A per-run snapshot.** `bind-prompt.py` copies the validated bytes to `<transcript>.prompt` under
    `O_EXCL`, and both capture arms feed *that* to the reviewer. Previously the wrapper re-`cat`ed the
    caller's path **after** the binder had blessed it, so a swap in between changed what the reviewer
    read while both sidecars still described the old bytes.
  - **Per-run, not per-round.** The prompt *filename* derives from ticket and round only, so two
    invocations sharing both shared one file — which the existing concurrency test could not see,
    because it compares round 7 against round 8. The snapshot is keyed by the transcript's unique run
    identity instead.

  `review-verdict.py write` now also checks the snapshot against `.promptsha256`, which nothing had
  ever read. (`cmd_verify` is deliberately untouched — that is `COREDEV-2497`'s territory.)

- **A NUL byte in the prompt made the validated bytes differ from the delivered ones.** The capture
  helpers hand the snapshot to the reviewer through `$(cat …)`, and Bash command substitution *silently
  deletes* NULs — so a prompt naming `A_PLAN.md` normally while spelling its instruction as
  `B_PL\0AN.md` bound cleanly against A (the agreement check saw a token that is not a plan name) and
  Codex then received the joined `B_PLAN.md`. A review of B could support A's approval. Refused at the
  source: a review prompt containing a NUL is never legitimate, and escaping it per call site would
  leave every transport added later needing its own defence.

- **`changeset.sh` accepted a version ref that shared no history.** A stale or orphaned
  `${prefix}.0000` resolves as a commit — passing the existence check added earlier the same day — while
  having no common ancestor, so the diff fell through to `HEAD~1` and reviewed only the last commit of a
  multi-commit branch. It now requires a merge base, which is what a base actually is. Reproduced
  against a genuine orphan branch.

- **One review arm could satisfy the mandatory two-arm gate.** Two separately allocated **Gemini**
  runs supplied as `gemini=` and `codex=` passed everything — freshness, the plan binding, and the
  distinct path/digest/captureId rules — because every one of those asks whether the two entries
  *differ*, and two real Gemini runs do. Nothing asked what either transcript **was**. The allocator
  encodes the reviewer in the filename it reserves, so the evidence already carried the answer; it was
  never read. Now compared, for approving verdicts only — a non-approving record blocks `implement`
  whatever its labels say, so refusing one would discard a legitimate `REQUEST_CHANGES`.

- **Three defects in the Gemini harness, all created by this release's own fixes:**
  - **A failed review reported success.** The capture status was saved in `RC` and then discarded by a
    successful diagnostic `echo`, so an `agy` exiting 23 printed `EXIT=23 … FAILED REVIEW` while the
    helper returned 0 — leaving the caller unable to distinguish a completed review from an auth,
    model or timeout failure.
  - **The mutation detector cried wolf on the harness's own input.** Staging the bound plan
    deliberately dirties the disposable checkout — that *is* the detached-HEAD fix — but the check
    still compared against `HEAD`, so a reviewer that wrote nothing was reported as having written,
    with the plan listed. It now baselines the tree after staging. This is the `COREDEV-2607` detector;
    one that fires on its own inputs is one nobody reads.
  - **The plan copy re-opened a mutable path.** A plan edited after binding and restored before
    synthesis could reach the reviewer while both the sidecar and the final digest described the
    restored bytes; the `cmp` beside it re-read that same path, so it only confirmed two reads agreed.
    `bind-prompt.py` now retains the exact bytes it hashed in `<transcript>.planbytes` and the harness
    stages those, falling back to the path with a warning rather than silently accepting less.

- **Containment resolved the working directory, not the repository.** `repository_root()` was
  `realpath(getcwd())`, so a wrapper launched from `scripts/` treated *that* as the repository and
  refused every plan in the tree — breaking the capture, audit, snapshot and persistence entrypoints at
  once, since all four share the helper. It resolves `git rev-parse --show-toplevel` now, and **fails
  closed outside a worktree**: with no repository there is no boundary to enforce, and falling back to
  the working directory would restore exactly this bug. This is the fourth false refusal this recheck
  surfaced — each one a guard right about the danger and wrong about the boundary.

- **Shell operators after an allowlisted wrapper went unexamined.** Reaching an in-root entrypoint was
  treated as the whole answer, so `&& rm *`, `; rm -rf *`, `$(rm *)`, a redirection and a pipe all
  passed while strict CI reported the tree clean — the policy promises one exact reviewed entrypoint,
  and that promise only holds if nothing can be appended to it. **Stated residual:** a compound grant
  with *no* wildcard is still exempt, because the analysis is scoped to wildcards by an explicit
  decision recorded in the module; a test now pins that boundary so it cannot be mistaken for covered.

- **An allocation base owned by another user was accepted.** `os.access` answers "may I write here",
  never "is this mine" — so an attacker-created mode-0777 directory under `/tmp` passed, and the
  allocator then placed its 0700 subtree beneath a parent whose owner could rename or replace it
  between allocation and capture. The nearest existing ancestor must now be owned by this user or by
  root; root-owned ancestors like `/tmp` are the normal case and are not attacker-controlled.

- **A digest-suffixed legacy transcript was mistaken for an allocation.** Classification keyed on any
  basename ending `-<32 hex>.txt` — and the classifier's own docstring names the realistic collision,
  `review-<md5>.txt`, MD5 hex being exactly 32 characters. Such a file was then required to carry a
  `.launch` and rejected without one, making a legitimate custom or historical transcript unusable.
  Narrowed to the whole allocator shape, `<ticket>r<round>-<reviewer>-<32 hex>.txt`. This keeps the
  property that docstring refuses to give up — the basename travels with the file, so an allocated
  transcript that was copied or moved still classifies as per-run, which conditioning on the
  *directory* would have lost.

- **Four hardening gaps in the allocated-capture path.** All reproduced:
  - **A hard link at the reserved leaf rewrote whatever shared the inode.** A hard link *is* a regular
    file, so `O_NOFOLLOW` and the `S_ISREG` check both accepted one; the `fchmod`/write/`ftruncate`
    then operated on the linked target. Reproduced by linking an 18-byte file at the reserved path and
    watching it become the capture at mode 0600. The allocator creates its leaf with exactly one link,
    so a second is never legitimate — now refused, with the victim's bytes asserted intact.
  - **A missing or empty launch record wasted a whole review.** `review-verdict.py` already rejected
    such a transcript, but only at *write* time — so a 20–30 minute review ran to completion, exited 0,
    and was then discarded. The same precondition is now checked before the reviewer launches, asserted
    on the child never running.
  - **A case-mangled protected root slipped past containment.** `commonpath` is case-sensitive and APFS
    is not, so `$HOME/.CLAUDE/…` compared unequal while opening the same directory; `realpath` doesn't
    help because it preserves the caller's spelling. Containment is now answered by **inode** where the
    paths exist, with a casefolded lexical fallback where they don't.
  - **The allocated leaf was `realpath`'d after its symlink check.** `islink()` then `realpath()` is a
    lookup-then-lookup pair, so a symlink planted between them was followed and every check ran against
    the attacker's target. The leaf name is now kept and opened `O_NOFOLLOW` — the same discipline the
    freshness TOCTOU fix established. The *ancestry* is still resolved; that is a different question.

- **The plan binding compared digests only, and hashed a truncated snapshot.** Two more defects in
  the write path:
  - **Byte-identical plans crossed.** Two distinct plans with the same contents share a digest, so a
    transcript captured for plan A satisfied an approval for plan B while the binding *recorded* — and
    ignored — the repo-relative identity that tells them apart. The identity is now compared **when it
    carries a directory**, which is what `bind-prompt.py` always writes; a bare basename cannot
    discriminate either way and is left alone, preserving the documented reason the check was
    digest-only (it must not depend on the directory each step ran from).
  - **A prompt over 64 KiB could never be approved.** The snapshot was hashed through the capped
    trusted-read helper, so an oversized-but-valid prompt hashed only its prefix and the write reported
    the snapshot as modified. The cap bounds untrusted *parsing*; a digest reads every byte and keeps
    none, so it is not what the cap protects. Now streamed. A guard that refuses correct work is a
    guard someone switches off.

- **Three narrowing side-effects of this release's own grant tightening.** Scoping the review skills'
  permissions made two documented flows *less* usable, and a base-resolution fallback hid a narrowed
  review:
  - **`changeset.sh` invented a base.** When neither `origin/main` nor a local `main` resolved, it
    returned the literal string `main` as though resolution had succeeded; `files`/`stat` then fell
    through to `HEAD~1` and reviewed only the last commit of a multi-commit branch, while `untested`
    emitted nothing and exited 0. Reproduced on a two-commit branch with no remote. It now fails
    explicitly — silently narrowing a review's scope is worse than refusing it, because the reviewer
    reports a clean pass over work it never saw.
  - **The documented Gemini model fallback did not match its own grant.**
    `MODEL=gemini-2.5-pro bash …` is an assignment-prefixed command shape, which
    `Bash(bash …/capture-gemini-review.sh *)` does not cover — so the fallback reintroduced the very
    prompt the narrowed grants removed. The model is now operand 6.
  - **Neither review skill could write the prompt file it requires.** Both bodies mandate creating
    `.codex-prompt-*` / `.agy-prompt-*` before invoking the capture helper, and neither granted a
    `Write`. The mandatory first step therefore prompted or was denied *before* the pre-approved
    capture command could run. Added narrowly, as the exact per-round filename shape.

- **Absolute paths defeated two fixes from earlier the same day, and broke a third flow.** All three
  are the same omission: a fix written for the relative spelling of an operand that is also accepted
  absolute.
  - `bind-prompt.py`'s plan-agreement check compared an absolute reference against a repo-relative
    identity, so it **refused the repository's own plan** when the prompt named it absolutely — which
    is exactly what `skills/gemini-review/SKILL.md` requires the generated prompt to do. That aborted
    the documented capture flow before the reviewer launched. A false refusal is not the safe
    direction: it breaks the gate for correct input, which is how guards get switched off.
  - `isolated-agy-review.sh` pasted the operand into `"$TREE/$PLAN_REL"`, so an absolute path built a
    nested destination like `$TREE/Users/…/docs/planning/X.md` while the rewritten prompt still pointed
    `agy` at `$TREE/docs/planning/X.md`. The copy landed where the reviewer never looks and it read the
    committed plan again — the defect the copy was added to fix, alive for one spelling.
  - The CI whitespace gate hard-coded `origin/main`. This repo has an `alpha` integration branch, so an
    alpha-targeting PR would have diffed the whole `main..alpha` history and failed every unrelated
    alpha change on one pre-existing issue — the re-litigation its own comment disclaimed. It now uses
    the workflow's real base ref.

- **Three holes in fixes shipped earlier in this same release.** Each was found by the PR's own
  recheck, reproduced, and closed:
  - **The prompt binding was skipped when its sidecar was absent**, so deleting `.promptsha256` turned
    the check off — the identical "absent means unchecked" fail-open the plan binding beside it exists
    to close, reintroduced one field over. It is now required for a per-run transcript; both sidecars
    are written together by `bind-prompt.py`, so a transcript carrying only `.plan` was never produced
    by the capture helper.
  - **The entrypoint allowlist matched `${CLAUDE_PLUGIN_ROOT}/` as a substring**, so
    `${CLAUDE_PLUGIN_ROOT}/../evil.sh`, a `..` chain deeper in the path, and even
    `/tmp/x/${CLAUDE_PLUGIN_ROOT}/evil.sh` all passed. The allowlist's justification is that these
    scripts ship in this repo and are reviewed with it; a path leaving the plugin root has neither
    property. Now anchored at the start and `..`-free.
  - **The writer-agent deny-list required only the bare spelling.** A consumer install resolves
    `unleashed-mail:<name>` too, so denying one left the other reachable — the same both-spellings
    rule the skills' own `Agent(...)` grants already follow.

- **The `agy` preflight ran a mutation-capable agent in the reviewed checkout.** It launched
  `agy -p "ping"` in the caller's working directory — the tree under review — while the same skill
  documents that `agy` has no read-only mode and has already once implemented a plan instead of
  reviewing it (2.6.4, `COREDEV-2607`). A stub touching a file in its working directory left that file
  in the checkout and the preflight still printed `healthy`. Two fixes, because they fail separately:
  the ping now runs in a fresh empty scratch directory (it needs no repository at all), **and** the
  checkout is fingerprinted with `git status --porcelain` around the capture, so a build that writes by
  absolute path is *detected* rather than merely made unlikely — isolation alone would have left that
  case silent. The failure report names only what changed, since the whole status buries one new entry
  in whatever was already dirty.

- **The cleanup tool opened each parent 39 times while claiming it opened them once.**
  `held_manifest_parents` looped over the 39 manifest entries, so the nine directories were opened up
  to six times each at different instants — and a swap landing between two of those opens split the
  run across two generations: five validated originals survived while five same-named files in the
  replacement directory were deleted, and the function reported success. The docstring asserted the
  property the loop did not implement. It now opens the nine unique parents once each, and the
  occupant scan runs **through those held descriptors**, immediately before the first unlink, inside
  one session that also spans the directory removal.

  **Stated ceiling, because narrowing is not closing.** An occupant arriving *after* the final check
  is unobservable at that check, by construction: the run still refuses, but the 39 files are already
  gone, so the refusal reports rather than prevents. Eliminating that would require the whole
  sequence to be atomic, which it cannot be. What is guaranteed — and proved — is that an occupant
  present *before* the run costs nothing: 39 of 39 files survive the refusal. The ceiling is recorded
  as an executable test so a reader cannot mistake it for covered.

  The occupant refusal deliberately lives in the orchestrator, **not** in `delete_leak_files`, whose
  contract is narrower on purpose: it deletes exactly the literal manifest and nothing of the same
  filename family, and that is only provable on a tree that *has* such a neighbour.

- **The prompt/plan agreement check compared basenames, and short sidecar writes went unnoticed.**
  Two defects in the binding shipped earlier the same day:
  - **Basename collision.** A prompt explicitly targeting `docs/planning/b/SAME_PLAN.md` was accepted
    while `--plan` named `docs/planning/a/SAME_PLAN.md`, because both acceptance and conflict detection
    reduced references to the basename — the same shortcut the *artifact's* plan identity was fixed for
    in PR #41, repeated one layer up. References are now compared as full normalized repo-relative
    paths, and a basename-only reference is refused as ambiguous when more than one plan answers to it
    rather than guessed.
  - **Short writes.** `os.write` can return a partial count without raising, and a file-size limit
    raises `EFBIG` on macOS. Either way a truncated `.prompt` snapshot was left on disk while
    `bind-prompt.py` exited 0 — and a truncated snapshot still clears the Gemini arm's 1,000-byte
    floor, so a reviewer would consume a cut-off prompt and only the digest check would notice, a full
    round later. Both shapes now refuse **and unlink the partial**, reproduced under a 2 KiB
    `RLIMIT_FSIZE`.

- **Removing `Bash` from two reviewers broke audit steps their bodies still needed.** The tool-list
  change was right; the justification was not. The note added beside it claimed every command in those
  bodies "was a `grep -rn`" — measured against the dominant pattern, not the whole set.
  `security-reviewer` still called `cat .gitignore | grep …` and `cat *.entitlements || find …`;
  `concurrency-reviewer` still called `plutil`. `Grep` executes none of those, so **those audit
  sections would have produced nothing while the reviewer reported a complete review** — a silent gap,
  which is worse than the escalation path the removal closed, because nothing announces it. All three
  are now explicit `Glob`/`Read`/`Grep` steps, the notes carry the correction, and
  `validate-plugin-assembly.py` fails if any agent without `Bash` documents a command only a shell
  could run.

- **The Gemini arm reviewed the committed plan while its binding named the working-tree one.**
  `isolated-agy-review.sh` builds its review tree with `git worktree add --detach … $(git rev-parse
  HEAD)`, so `agy` read the **committed** plan; `bind-prompt.py` hashed the **working-tree** plan into
  `<transcript>.plan`. With uncommitted edits — the normal state during the documented review
  iteration — the transcript approved one version while the artifact recorded it as evidence for
  another. Two correct digests describing different bytes, the same pairing failure as the prompt/plan
  binding one layer down. The bound plan is now copied into the review checkout and verified with
  `cmp`, so the reviewer reads exactly what the sidecar attests to. Copying rather than refusing keeps
  the iterate-then-review loop working, and makes the binding *true* rather than merely checkable.

- **The `implement` recipe substituted the user's argument into shell syntax.** It bound the argument
  through a quoted heredoc, which correctly kept metacharacters (`"`, `$( )`, backticks) as literal
  data. What that could not defend was the **delimiter**: the placeholder is substituted *textually
  across the whole fence before the shell runs*, so an argument containing a line equal to the heredoc
  delimiter closed the body early and every following line was parsed as a shell command — and with the
  skill model-invocable, that needed no user gesture. No quoting fixes it, because the fault sits one
  level above the quoting. The recipe no longer substitutes the argument at all: the model resolves the
  plan with `Glob`/`Read` and passes the concrete path as one operand, which `resolve-plan-gate.sh` now
  accepts (STDIN is kept for callers already binding a heredoc, and both paths were verified to produce
  identical output on four inputs). A test asserts no shell fence in the skill contains the placeholder,
  and that no fence contains `<<` at all — a differently-named delimiter would be just as matchable.

- **`swift-reviewer` could spawn every file-writing agent.** Its `tools:` lists bare `Agent`, because a
  sub-agent tool list takes bare names — `Agent(type)` is silently ignored there — so it reached all
  twelve agents holding `Write`/`Edit` or inheriting everything. Spawned from `pr-review` while that
  skill processes untrusted PR content, a prompt-injected finding could have steered it into
  `ui-engineer` or `db-engineer` and written to the tree with no user gesture. All twelve are now denied
  by name.

  That is a deny-list, and a deny-list re-opens the moment someone adds a writer agent. So
  `validate-plugin-assembly.py` **recomputes** the writer set from the agents on disk and fails if any
  is missing from the deny list — proved by adding a thirteenth writer and watching CI reject it. The
  five read-only reviewers this agent actually spawns stay reachable.

- **The gate's plan-state entrypoints wrote wherever they were pointed.** `brainstorm` is
  model-invocable and pre-approves both the snapshot and the persistence command, so the *model* picks
  `--plan`. Neither enforced containment: any existing file on disk was accepted, the snapshot sidecar
  landed beside it, and even a **non-approving** persist created and chmod'd a `.verdicts` directory
  there — reproduced against `/tmp`, walking past the skill's apparent `Write(docs/planning/**)`
  boundary with no user gesture. Both now require a non-symlink regular plan under `docs/planning` in
  this repository, via the shared `containment.py` (which grew an `--under` subtree check), and the
  snapshot step moved behind a new exact entrypoint, `scripts/review/snapshot-plan.sh`.

  The containment is in the entrypoints, **not** in `review-verdict.py`: that tool has a designed and
  tested behaviour for a plan outside any git repo, and it is also the maintainer's own CLI. What has
  to be bounded is the pre-approved path the model can enter. This is the fourth entrypoint to need
  the same rule, which is why it lives in one module.

- **An approving verdict could rest on legacy transcripts that nothing checked.**
  `_is_per_run_transcript` is the switch deciding whether the freshness check **and** the plan binding
  run at all, so a transcript failing it was exempt from both — and the shapes it exempts are the fixed
  shared-`/tmp` reviewer outputs an older plugin version left behind. Two stale files could therefore be
  labelled `APPROVE`, combined with a fresh snapshot of the current plan, and produce a gate-passing
  artifact for a plan nobody reviewed. An approving write now requires allocator-shaped evidence for
  every reviewer. Legacy paths remain readable for **non-approving** records, which block `implement`
  regardless and would otherwise be discarded for no security benefit.

  The check runs **after** the quorum and identity rules, which own "no transcript for this reviewer",
  "duplicate capture ID" and "empty transcript". Placed before them it answered all three with "not
  allocator-shaped" — true, but it tells the operator to re-capture when the real fault was a missing
  operand; two existing tests caught that regression.

  Every fixture in `test_review_verdict.py` used bare `transcript.txt`-style names, which is precisely
  why no test caught the hole: the suite only ever exercised the exempt path. They now build allocated
  transcripts through one shared helper, with launch records and plan bindings.

- **`audit-codex.sh` accepted arbitrary model-controlled operands.** It allowlisted the reviewer name
  and then folded everything after it into the external prompt with `$*`. Reproduced with an exact
  stub: `/etc/passwd` was accepted, exit 0, and so was a plain `ignore prior instructions …` operand,
  which is prompt injection rather than a filename. `-s read-only` prevents writes; it is not a
  repository-read boundary and does nothing about disclosure to a third-party service. Operands must
  now be non-symlink regular files beneath the physical repository root, and the prompt is built from
  the *validated* output one path per line, so boundaries survive.

  The containment rule moved into `scripts/review/containment.py`, shared with `bind-prompt.py`. That
  sharing **is** the fix: the identical hole was closed on the prompt operand a day earlier and this
  sibling — written in the same batch — did not inherit it, because the rule lived inside one script.

- **The entrypoint-only grant policy was fail-open, and is now default-deny.** It deny-listed a fixed
  set of command names and passed everything else. Measured probes producing zero problems *and* zero
  warnings: `Bash(python3 -c *)`, `Bash(sh -c *)`, `Bash(cp *)`, `Bash(mv *)`, `Bash(tee *)`,
  `Bash(find *)`, `Bash(curl *)`, `Bash(chmod *)`. `python3 -c *` is arbitrary code execution; the
  interpreter branch only looked for a wildcard in the *script path*, and `-c` is not a path. A
  wildcard `Bash` grant on a model-reachable skill is now refused unless it invokes an **exact** script
  beneath `${CLAUDE_PLUGIN_ROOT}` — those wrappers ship in this repo, are reviewed with it, and bound
  their own operands, which is the property that makes a trailing wildcard acceptable there and
  nowhere else. Interpreter code/module/stdin modes are named explicitly. The trampoline advisory tier
  became a hard refusal in the same change; nothing shipped depends on it. **This supersedes the
  "advisory warning for toolchain trampolines" sentence above.**

  One shipped grant this rejects: `swiftlint-config`'s `Bash(swiftlint *)` — its own body runs
  `swiftlint --fix`, a source mutator, pre-approved on a model-invocable skill. Removed.

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

- **`audit-codex.sh` snapshots its operands, closing a validate-then-open disclosure race.** It
  validated each operand with `containment.py` (non-symlink, regular, in-repo) and then handed codex the
  live repo-relative PATH, which codex opened later. A same-account process that replaced an accepted
  file with a symlink to an outside secret between the check and the open had `codex exec -s read-only`
  follow it and disclose the outside file (PR #63 recheck, P1, reproduced). New `snapshot-operands.py`
  validates AND reads each operand through one `O_NOFOLLOW` descriptor into a private disposable tree,
  and codex is pointed at those immutable copies — no later swap can change what it reads, and a swap
  landing during the read is refused rather than followed. Because the snapshot paths are absolute, this
  also fixes the separate report that a relative operand did not resolve when the wrapper ran from a
  subdirectory. The fixture that reproduced it no longer writes a stray symlink into the repo root — it
  builds a throwaway git repo instead.
- **The codex review arm now reviews an isolated checkout, so a plan swap cannot forge its verdict.**
  `capture-codex-review.sh` ran `codex exec … -s read-only` in the LIVE working tree, so the plan file
  codex opened was the mutable one. An A→B→A swap during codex's read window let it review substituted
  bytes while `.plan` and the live plan both still hashed A, and `review-verdict` authenticates only
  the live plan — so the artifact attested a plan the reviewer never read (PR #63 recheck, P1,
  reproduced end to end). The gemini arm already isolated its review into a detached checkout with the
  authenticated `.planbytes` staged; the codex arm never inherited it — the exact "a rule that lives in
  one script is a rule the next entrypoint will not have" failure. New `isolated-codex-review.sh` runs
  codex against a disposable detached checkout, and the plan staging both arms use is now the shared
  `stage-bound-plan.py` (authenticate `.planbytes` against `.plan`, read once through `O_NOFOLLOW`,
  write through a no-follow descriptor walk) — so the fix cannot diverge between the arms again. The M5
  transcript-path contract and the threading fixtures now assert both arms symmetrically, and a
  cross-arm test drives the same substitution attack through each.
- **The model-reachable grant validator closed three fail-open spellings.** (PR #63 recheck, P2, all
  measured passing.) (1) A shell operator glued to the entrypoint with no space —
  `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/x.py;rm -rf /)` — rode inside a single word that the post-target
  operand scan never inspected; the scan now runs over *every* Bash specifier, wildcard or not,
  rejecting `;`, `|`, backtick, redirection, `&`, and `$(` (which never appear in a legitimate
  one-command grant, while `${CLAUDE_PLUGIN_ROOT}` and a trailing `*` still do). (2) `_bash_specifiers`
  extracted with `Bash\(([^)]*)\)`, stopping at the first `)`, so `Bash(… $(rm) *)` dropped its
  trailing `*` and skipped analysis as "bounded"; extraction now walks balanced parens. (3) The
  bare-name refusal was exact-string, so `Write(**)`, `Write(/**)`, `Edit(**)`, `NotebookEdit(**)` and
  `Agent(*)` slipped past it despite pre-approving the same surface as the bare grant — a full-breadth
  scope is now refused explicitly. The previously-documented "no-wildcard compound is exempt" boundary
  was itself the first fail-open and is now closed; a genuinely bounded *single* command
  (`Bash(command -v codex)`) stays exempt.
- **Gemini plan staging can no longer be tricked into writing outside its disposable checkout.**
  `git worktree add --detach` materializes committed tree entries, so a plan path recorded in HEAD as a
  **symlink** (or under a symlinked parent) was recreated in the throwaway checkout, and the staging
  `open(destination, "wb")` wrote *through* it — a same-account attacker whose HEAD carried
  `docs/planning/X_PLAN.md -> /outside/victim` had the victim overwritten with the staged bytes
  (PR #63 recheck, P1, reproduced). Staging is now a descriptor walk: every directory component is
  opened `O_DIRECTORY|O_NOFOLLOW` (a symlinked parent fails `ELOOP`), and the leaf is
  unlink-without-following then created `O_CREAT|O_EXCL|O_NOFOLLOW`, so a materialized symlink is
  removed as a link and never traversed. Both the authenticated-snapshot and live-plan fallback paths
  go through it.
- **`pty-capture.py` no longer rewrites a hard-linked victim on the non-allocated path.** The fresh
  path opened `O_CREAT|O_TRUNC` while the `nlink != 1` guard was gated on `allocated` — and `O_TRUNC`
  empties a pre-existing file at `open()`, before any `fstat`, so a hard link planted at the
  predictable capture/`.captureid` path was truncated to zero on the way in and the guard never ran
  (PR #63 recheck, P2, reproduced: `PRECIOUS OUTSIDE DATA` became the capture). The path now opens
  without `O_TRUNC`, the `nlink != 1` refusal is unconditional and runs before any write, and the
  existing `ftruncate` bounds an honest single-linked overwrite — closing the hole while keeping the
  legitimate stale-file overwrite behaviour that `O_EXCL` would have broken.
- **A reviewer that mutates its disposable checkout VOIDS the round — including the invisible case.**
  `isolated-agy-review.sh` printed an informational note when the reviewer wrote inside the disposable
  copy and returned success; worse, the note's baseline diff is *status-line* based, so a reviewer that
  rewrote the already-`M` **staged plan** and then emitted `VERDICT: APPROVE` produced a valid-looking
  capture with **no note at all** — a review of substituted bytes approving the original plan, which
  synthesis cannot catch because it validates the `.plan` record against the untouched live plan
  (PR #63 recheck, P1; both shapes reproduced). Now the round's **basis is content-verified**: the
  staged plan must still hash to the digest its `.plan` record attests to, the assembled prompt must
  still hash to what the harness wrote (the old diff *excluded* the prompt's basename, hiding prompt
  tampering by construction), and **any** other post-baseline write voids the round with exit 3 —
  writing files is the COREDEV-2607 agent-mode signature, and a review produced that way is
  untrustworthy whether or not the copy is discarded. The harness's own staged inputs stay exempt via
  the post-staging baseline, so clean rounds are unaffected. Revert-proof: the pre-fix harness fails
  exactly the three new tests.
- **Plan references survive a space in the repository's own path.** `bind-prompt.py`'s token regex
  matched a character allowlist without the space, so an absolute reference under
  `/Users/me/My Projects/repo/…` was captured from AFTER the space and the disagreement check refused
  the documented capture flow — the gemini skill *requires* absolute plan paths in generated prompts —
  before either reviewer launched. Absolute references under the repository are now matched WHOLE,
  anchored on the known root (the one string that makes an embedded space unambiguous), and masked
  before the conservative token sweep handles relative and prose references. The refusal for a
  genuinely different plan now names its full identity instead of a truncated fragment. Ships with a
  permanent revert-proof: the suite runs the old extraction against the spaced fixture and asserts it
  still fails.
- **The Plan Review Gate anchors at the worktree root and honors the caller's spelling.**
  `resolve-plan-gate.sh` evaluated everything — the direct file test, the name-branch glob, the `ls`
  diagnostic, and the `verify` exec — against the caller's working directory, so from a repository
  subdirectory the documented root-relative operand fell through to name resolution and a valid,
  gated plan was reported as "No plan matches". Now: `cd` to `git rev-parse --show-toplevel`
  (fail-closed outside a worktree), with the operand interpreted against the caller's directory
  first, the root second, and refused as AMBIGUOUS (exit 2) when the two name different files. An
  absolute in-repo operand — previously refused as "not a tracked plan" purely for its spelling — now
  resolves, and a `..`-wearing spelling is collapsed physically first, so it is classified by its
  true identity rather than caught wearing the prefix. The symlinked-planning-root proof became a
  double-mutant: two independent mechanisms now refuse it, so single mutants are asserted as defence
  in depth and the pair is proved by the double admitting.
- **The spawner check's writer predicate now means "can modify the checkout".** It tested only
  `Write`/`Edit` — by substring, so a `NotebookEdit` deny satisfied an `Edit` probe — and its spawner
  detection skipped omitted-`tools:` agents entirely. Three shapes escaped: `jira-manager` (denies the
  file editors, inherits unrestricted `Bash`), any `memory:` agent (auto-enabled Write never appears
  in `tools:`), and `modern-standards-planner` as an undetected inherit-all *spawner*. The predicate
  is now token-exact over live tools (grants-or-everything minus denies) against
  `{Write, Edit, NotebookEdit, Bash}`; `memory:` counts as Write; inherit-all agents count as holding
  `Agent`. Agent changes to match the honest policy: `jira-manager` **denies `Bash`** (the caller now
  passes the PR URL; its Atlassian-MCP mutation of Jira is unchanged and by design),
  `modern-standards-planner` denies the `Agent` tool it never used, and `swift-reviewer` denies
  spawning itself. `check_bashless_agents_run_no_shell` now scopes by live Bash too, so a
  bashless-BY-DENIAL agent's shell recipes are swept like any other — which is what caught
  `jira-manager`'s own `gh pr view` instruction. `AGENT_CONTRACTS.md`'s capability row is updated,
  dropping a `MultiEdit` deny it claimed while the agent file never carried it (Claude Code removed
  that tool; the stale-name rule rejects denying it).
- **The staged plan snapshot is authenticated against its own record before the reviewer sees it.**
  `isolated-agy-review.sh` copied `<transcript>.planbytes` into the review checkout and then `cmp`'d
  the copy against its source — a comparison between two reads of the same mutable file. A same-account
  process rewriting `.planbytes` between `bind-prompt.py` returning and the staging copy was read by
  both, so they agreed and `agy` reviewed substituted bytes; nothing downstream noticed, because
  `review-verdict.py` validates the `.plan` RECORD against the live plan and never hashes `.planbytes`.
  The resulting transcript could approve the ORIGINAL plan. The record held the honest digest the whole
  time and nothing read it — the fifth "recorded and never compared" in this release. Now one
  `O_NOFOLLOW` descriptor is read once, hashed, compared to `.plan`, and those same bytes are written,
  so there is no second open to race.
- **A plan path relative to the CALLER's directory no longer refuses the round.** `bind-prompt.py`
  resolves the plan operand against the caller's working directory; `isolated-agy-review.sh` had already
  `cd`'d to the repository root and reinterpreted the same string there, so
  `../docs/planning/X_PLAN.md` passed from a subdirectory bound successfully and then died with
  `plan not readable` before the reviewer launched. Resolved against the caller first, the root second,
  and refused only when the two name genuinely different files. **A guard that rejects correct work is
  one an operator switches off** — the fifth false refusal this recheck surfaced.
- **`gemini-review` no longer documents running a script it does not grant.** Four executable lines told
  the model to invoke `scripts/review/isolated-agy-review.sh` directly, which the skill's
  `allowed-tools` does not cover, so the documented flow prompted or was denied; and the
  three-argument shape they used omitted the plan operand, which skips snapshot staging and makes `agy`
  review the COMMITTED plan instead of the uncommitted edits under review. All now route through the
  granted `capture-gemini-review.sh`. A new sweep asserts the property for **every** skill: the previous
  check enumerated specific recipes, and an enumeration cannot fail on the entry nobody added.
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
- **The Plan Review Gate now has an end-to-end suite** (`scripts/tests/test_end_to_end_gate.py`, 10
  scenarios). Every other suite here tests one script; nothing spanned snapshot → allocate → bind →
  capture → write → verify → resolve, which is where the gate's guarantees actually live. It runs the
  real allocator, `bind-prompt.py`, `pty-capture.py`, `review-verdict.py` and `resolve-plan-gate.sh`
  against a real git repository, stubbing only `codex` and `agy` — the two things that leave the
  machine — by putting them earlier on `PATH` rather than patching the helpers, so the helpers run
  their real argv. Each scenario gets its own repository, because the hand run that produced the file
  reported a FALSE failure when one scenario inherited another's tampering.

  It **independently reproduced `COREDEV-2497` §4.1** — `verify` re-reads the plan and nothing else, so
  an approved transcript can be rewritten and the gate still prints `GATE OK`. That defect was already
  known and planned; the suite did not discover it. It is **not fixed here**: that plan has not passed
  its gate (last round: both arms `REQUEST_CHANGES`), and it specifies behaviour an ad-hoc fix would
  get wrong — a missing transcript must fail with a distinct `MISSING` cause, and the recorded path
  must be resolved exactly once, behind named seams. An ad-hoc fix was written during this work and
  **reverted** for exactly those reasons. The defect is pinned by
  `test_the_gate_still_accepts_altered_evidence_COREDEV_2497`, which asserts the current, defective
  behaviour and fails — deliberately — the day `COREDEV-2497` lands.
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
