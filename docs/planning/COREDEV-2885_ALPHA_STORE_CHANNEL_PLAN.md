# COREDEV-2885 — An install channel for `alpha`: the marketplace's ref must decide the plugin's ref

**Status:** Planning, revision 4. **The Q1/Q2 stopping rule fired after round 3**: rounds 2 and 3 both found Q1 = 0.
Revision 4 applies round 3's three Q2 corrections WITHOUT a further round, so it is ungated. The gate is NOT passed:
codex `REQUEST_CHANGES` (instrument findings only), and gemini never ran (agy unavailable). Passing it needs the
maintainer's decision.
**Ticket:** COREDEV-2885 (Epic COREDEV-2485). Follows COREDEV-2883, which set the branch flow to
`main` > `alpha` > feature work.
**Branch / worktree:** `feat/COREDEV-2885-alpha-store-channel`, `.claude/worktrees/2885-alpha-channel`, cut
from `origin/alpha` at `91ee033`.
**Prerequisite:** COREDEV-2883 (PR #121, into `alpha`). It introduces the `CLAUDE.md` "Branch flow"
bullet and the five-sync-point Versioning text that §3.5 edits. Implementation rebases onto `alpha`
after #121 merges (§5 step 2).

## Review log

- **Round 3 (revision 3), codex `REQUEST_CHANGES`, Q1: 0, Q2: 3.** These were the second consecutive
  zero-Q1 findings, so the stopping rule fired. Applied in revision 4, not re-reviewed:
  1. **(Q2) The W negatives could pass without exercising B′.** If the marketplace clone stayed at A/A3,
     whose `github` entry still selects `main`, they would report `main`'s SHA and no sentinel anyway.
     A3's "still listed" check had the same gap. **Fix:** after every `marketplace update`, the clone's
     HEAD and manifest are asserted to be the intended fixture BEFORE the plugin update is judged, and
     every command must exit 0 (§4, "The rule for every step").
  2. **(Q2) F4 said relative sources work "only" through Git, while F3 used a local directory.** **Fix:**
     F4 distinguishes Git-backed cached installs, local-directory loading, and URL (bare-manifest)
     marketplaces, which cannot use relative sources.
  3. **(Q2) V2's lead sentence promised three different assertions, but V2a and V2b share one.** **Fix:**
     reworded. The cells were already right.
- **Round 2 (revision 2), codex `REQUEST_CHANGES`, Q1: 0, Q2: 2.** No shipping defect remained. Both
  findings were real instrument defects.
  1. **(Q2) W1′ and W2′ ran after B, so they had the wrong baseline.** B had already installed
     `2.8.32-witness-b`. B′ then carried `main`'s version, which DIFFERS from the installed one, so F6's
     equal-version skip could not apply. Even a skip would have kept B's bytes, not `main`'s. **Fix:** each
     control is now its own witness branch and its own config, initialized at A (or A2 → A3). B′ is
     applied directly to that `main`-version install.
  2. **(Q2) V2c could go green.** `ci-load-check.sh` registers its scratch copy as a LOCAL-DIRECTORY
     marketplace (it removes `.git`), and the docs say such plugins can be read in place. A sentinel planted
     after install could then appear in the "installed" tree through the alias. **Fix:** V2c now installs
     from a SECOND scratch tree. It has the same marketplace name, `"./"` source and version, but no
     sentinel, while the sentinel stays planted in the original. Step 4 must then report it absent,
     whatever the cache does.
- **Round 1 (revision 1), codex `REQUEST_CHANGES`, Q1: 1, Q2: 3.** All four findings were real.
  1. **(Q1) §0 promised "every existing install" while §6 excluded the maintainer's own.** That install is
     keyed `npranson-unleashed-mail-plugin`, but its clone's `marketplace.json` now says
     `unleashedservices-unleashed-mail-plugin`. **Fix:** §0 now names that registration explicitly. F10
     records that it resolves and updates today, contrary to `README.md`'s migration note. Witness W2 (§4)
     reproduces its exact history (registered under the old name, the file renamed later) and then
     applies the change.
  2. **(Q2) V3 was not a migration witness.** Its "point the marketplace at another clone" step was
     unspecified, and remove/add would uninstall (F8), so a fresh install could pass as a migration. Its
     local-directory fixture may also load in place (the docs, "edit plugins in place on a shared
     directory"), so the unbumped red control was not established. **Fix:** V3 is replaced by W1 and W2.
     These are Git-backed, on a throwaway remote branch. They keep one registration, key and scope
     throughout, record version, SHA and install path before and after, and carry bumped and unbumped
     controls. F3 is relabelled as a local-directory approximation.
  3. **(Q2) V2's existing sentinel mutant can no longer reach step 4.** It is a `source: github` mutant, so
     the new pre-install source assertion intercepts it. **Fix:** that mutant is re-mapped to the source
     assertion, and a new mutant V2c reaches the byte witness by passing the source assertion and then
     installing a tree without the sentinel.
  4. **(Q2) §3.5 targeted text that does not exist on `91ee033`.** The text arrives with COREDEV-2883
     (#121). **Fix:** #121 is a stated prerequisite, above and in §5.
- **Round 1, gemini: no review.** `agy` 1.3.3 failed its preflight three times: a 0-byte ping, with the
  `streamGenerateContent` call for `gemini-3.8-flash-high` unanswered within 60 s. Auth and `agy models`
  were healthy. No gemini round ran on revision 1.

## 0. The defect, and what "fixed" means

Work now lands on `alpha` and reaches `main` only by promotion (COREDEV-2883). But the plugin store can
only ever install `main`'s code, so unreleased work cannot be tested through an install. The maintainer's
words: "the custom store only downloads from main, so we'll need to make sure that when we test, the new
code is on main."

Adding the marketplace at `alpha` does not help. **Measured (F1):** a marketplace added as
`UnleashedServices/unleashed-mail-plugin#alpha` is cloned from `alpha`, yet the plugin it installs is
`main`'s commit. This is a trap as well as a gap: the `#alpha` form looks like it works.

**Fixed means:**
1. A machine that adds the marketplace at `#alpha` installs `alpha`'s plugin bytes, at `alpha`'s version.
2. A machine whose marketplace has no ref keeps installing `main`'s bytes, and updates in place with no
   manual migration. This covers BOTH kinds of registration that exist:
   - one keyed by the file's current name, `unleashedservices-unleashed-mail-plugin`;
   - one keyed by the file's former name, `npranson-unleashed-mail-plugin`. That is the maintainer's own
     install (F10).
3. A promotion (`alpha` → `main`) never conflicts over, and never needs a per-branch edit to, the store
   manifest.
4. CI proves the shipped manifest installs the checkout's own bytes, with no rewrite of the source field.

## 1. Verified facts (2026-10-12, Claude Code 2.1.296, against `alpha` `91ee033` and `main` `a100645`)

Every probe ran under `CLAUDE_CONFIG_DIR=<scratch>`, so the maintainer's real plugin configuration was
never touched. **F0:** that isolation holds. A fresh config dir lists only the built-in
`anthropic-plugin-directory`, and the real `~/.claude/plugins/known_marketplaces.json` was unchanged.

- **F1. The plugin entry pins `main` independently of the marketplace's ref.** `.claude-plugin/marketplace.json`'s
  entry is `{"source":"github","repo":"UnleashedServices/unleashed-mail-plugin"}`, with no `ref`. Probe 1
  (a Git-backed marketplace) ran `claude plugin marketplace add 'UnleashedServices/unleashed-mail-plugin#alpha'`
  and then installed:
  - the marketplace was recorded as `{"source":"github",...,"ref":"alpha"}` and cloned at `alpha`;
  - the installed `gitCommitSha` was `a100645`, **`main`'s tip**, not `alpha`'s `91ee033`.

  `alpha` and `main` had byte-identical trees, so the SHA, not the content, is the discriminator. The docs
  agree: a `github` plugin source with no `ref` "defaults to the repository default branch".
- **F2. A plugin entry that pins `ref: alpha` installs `alpha`.** Probe 2a used a separate marketplace
  named `unleashed-mail-alpha` whose entry is `{"source":"github",...,"ref":"alpha"}`. It installed
  `gitCommitSha` `91ee033`, which equals `origin/alpha`.
- **F3. A relative source `"./"` is accepted.** This was observed only through a LOCAL-DIRECTORY
  marketplace, which is an approximation. Probe 3b used a clone of `91ee033` with the entry's source set to
  `"./"` and both versions set to `2.8.32-probe`, committed as `c1f2b80`. It installed version
  `2.8.32-probe` at `gitCommitSha` `c1f2b80`, into the cache path `…/unleashed-mail/2.8.32-probe`.
  - The docs say local-directory relative plugins can load in place without a version bump, so this probe
    does NOT establish the Git-backed update path. W1 and W2, with their controls W1′ and W2′ (§4), do.
  - `scripts/ci-load-check.sh` has relied on `"./"` since COREDEV-2598, and records that absolute and `../`
    sources are rejected (verified there on 2.1.220).
- **F4. The marketplace's ref decides what a relative source resolves to: INFERRED from F1 + F3.** The docs
  say a relative path "is resolved relative to the marketplace root". It needs the marketplace's FILES:
  - it works for a Git-backed marketplace, whose files are a clone, cached on install;
  - it works for a local-directory marketplace (F3), whose files may be read in place;
  - it does NOT work for a URL marketplace, which serves a bare manifest with no tree.

  This plan's channels are Git-backed. F1 shows a `#alpha` marketplace is cloned at `alpha`. The CLI rejects `file://` URLs
  (`Invalid marketplace source format`), so a Git-backed probe needs a pushed ref. W1 and C1 (§4) observe
  it end to end.
- **F5. A marketplace declared only in settings is not materialized non-interactively.** Probe 2 declared
  `unleashed-mail-alpha` in `extraKnownMarketplaces`, with a `git` source plus `ref` and `path`.
  `claude plugin marketplace list` did not show it, `marketplace update` said "not found", and install
  failed. The docs say team members are PROMPTED when they trust a folder. `claude plugin marketplace add`
  has no subdirectory option (its flags: `--scope`, `--sparse`, `--json`, `--claudeai`).
- **F6. Release channels, per the docs.** "Each channel must resolve to a different version … If two refs
  resolve to the same version string, Claude Code treats them as identical and skips the update." The
  version is resolved from `plugin.json` first, then the marketplace entry, then the git SHA. A marketplace
  source supports `ref` but not `sha`; a plugin source supports both.
- **F7. The entry's `version` is load-bearing (COREDEV-2801).** `validate-version-sync.sh` source 5 requires
  `marketplace.json`'s entry version to equal `plugin.json`'s. Without it, the installed version is chosen
  by raw cache-directory order, and an old version came back. Any design must keep that entry correct on
  the branch it is read from.
- **F8. Removing a marketplace uninstalls the plugins installed from it** (docs, "Manage marketplaces").
- **F9. A local copy can be tested without the store** (docs): `claude --plugin-dir <dir>` takes precedence
  over an installed plugin of the same name for that session, and `/reload-plugins` picks up edits.
- **F10. A registration keyed by the file's FORMER name resolves and updates today.** In the maintainer's
  real registry (read-only), `known_marketplaces.json` has `npranson-unleashed-mail-plugin` with source
  `{"source":"github","repo":"npranson/unleashed-mail-plugin"}`, last updated 2026-10-10T09:20:29Z.
  - Its clone's `.claude-plugin/marketplace.json` declares `"name": "unleashedservices-unleashed-mail-plugin"`.
  - `installed_plugins.json` shows `unleashed-mail@npranson-unleashed-mail-plugin` at user scope updated to
    `2.8.31` (`gitCommitSha` `665796e`, `main`'s tip then) at 2026-10-10T09:21:26Z.
  - `README.md`'s migration note says such an install "will stop resolving". The registry shows otherwise
    for updates under the `github` source. W2 measures it under both sources before the README is
    changed.

## 2. Design: a relative source, so the marketplace's ref decides the plugin's ref

Change the one entry's `source` in `.claude-plugin/marketplace.json` from
`{"source":"github","repo":"UnleashedServices/unleashed-mail-plugin"}` to `"./"`. Nothing else in the file
changes. In particular, the name `unleashedservices-unleashed-mail-plugin` and the entry `version` stay.

| Channel | How a machine joins it | What it installs |
|---|---|---|
| stable | `claude plugin marketplace add UnleashedServices/unleashed-mail-plugin` (every existing install) | `main`'s tree at `main`'s version |
| alpha | `claude plugin marketplace add UnleashedServices/unleashed-mail-plugin#alpha` | `alpha`'s tree at `alpha`'s version |

**Why this meets §0:**
1. A `#alpha` marketplace is cloned at `alpha` (F1), and `"./"` installs that clone's tree (F3, F4;
   observed Git-backed by W1 and C1).
2. A no-ref marketplace is cloned at `main` and installs `main`'s tree: the same bytes it installs today, by
   a different route.
   - The entry version still moves with every bump, so the pull signal (F7) is unchanged.
   - The registration is not touched, so its key, whichever of the two it is, stays the same.
   - W1 (current key) and W2 (former key) observe an in-place update across the source change.
3. The file is identical on both branches except the version, which already differs per branch and is
   already validated per branch (F7). A promotion carries `alpha`'s copy to `main` with no edit.
4. `scripts/ci-load-check.sh` stops rewriting the source, because the shipped value is already `"./"`.

**Channel switching.** Both channels share one marketplace name, so a machine follows one channel at a time.
Switching is `marketplace remove` and then `add` at the other ref, followed by a reinstall, because removal
uninstalls (F8). This is documented in the README. For a quick test of a single branch, `--plugin-dir` (F9)
stays the lighter option.

**Versions across channels (F6).** Per-PR bumps (CLAUDE.md "Versioning") keep `alpha`'s version ahead of
`main`'s between promotions. Right after a promotion they are equal, and so are the trees. A switch is a
fresh install, not an update, so the "same version skips the update" rule never strands a machine on the
wrong bytes.

### 2.1 Alternatives considered

- **A second marketplace inside this repo (`channels/alpha/`, entry `ref: alpha`).** Rejected. F2 shows the
  entry works, but the marketplace needs a `path` source, and F5 shows such a source materializes only
  through an interactive trust prompt, with no CLI form. Two plugins named `unleashed-mail` could also be
  enabled at once, duplicating every skill and agent. Its one advantage, per-project channel choice, is
  not asked for.
- **A separate marketplace repo (the docs' stable/latest pattern).** Rejected. Its entry `version` would have
  to be hand-synced across repositories on every `alpha` bump, and F7 shows a stale or missing entry version
  is exactly the COREDEV-2801 failure.
- **`"ref": "alpha"` in this repo's entry.** Rejected. It must differ between `alpha` and `main`, so every
  promotion would conflict or carry the wrong value onto `main`.
- **Leaving it to `--plugin-dir`.** Kept as the documented lightweight path (F9), but it does not answer the
  maintainer's request to test through the store.

## 3. Changes

1. **`.claude-plugin/marketplace.json`:** the entry's `source` becomes `"./"`.
2. **`scripts/ci-load-check.sh`:** stop rewriting `source`, but keep the marketplace-name rewrite, which
   avoids collision with a real install. Assert instead that the shipped source IS `"./"`, and fail
   otherwise, BEFORE any install. Rewrite the header's point 1 and the "FIDELITY GAP" note, because the gap
   is closed rather than annotated. Update the mutant table to match §4 V2.
3. **`scripts/validate-plugin-assembly.py`:** assert that the entry's source is exactly `"./"`, with the
   reason stated (§0's property 1).
4. **`README.md`:**
   - Add a "Release channels" subsection to the install section. It covers stable (the default), how to
     join alpha, how to switch and why a switch reinstalls, and `--plugin-dir`.
   - Correct the "Migrating from the old `npranson-unleashed-mail-plugin` marketplace" note to whatever W2
     observes, instead of the untested "will stop resolving".
5. **`CLAUDE.md` "Branch flow" (from COREDEV-2883):** replace "COREDEV-2885 tracks an install channel for
   `alpha`; until then …" with the channel's join command.
6. **Version bump** to the next free patch at merge time: 2.8.34 if COREDEV-2884's 2.8.33 lands first. That
   means five sync points plus a CHANGELOG entry, and `marketplace.json` itself is the shipped change.

## 4. Verification cells (each must be seen red, for the stated reason)

**V1–V2, local.**
- **V1:** `validate-plugin-assembly.py --strict` passes with `"./"`. Mutate the entry back to the `github`
  object, and it reds with the new reason.
- **V2:** `ci-load-check.sh` passes on the branch. Three mutants, with this assertion mapping:
  - **V2a:** the shipped source is mutated back to `github`. It reds at the new source assertion, before any
    install.
  - **V2b:** the existing "equal versions" mutant, also `github`. It now reds at the SAME source assertion,
    and is recorded so; it no longer reaches step 4.
  - **V2c (new):** the sentinel is planted in the checkout's scratch copy as usual. The install, however,
    comes from a SECOND scratch tree with the same marketplace name, `"./"` source and version, but no
    sentinel. That models "the install did not come from this checkout". It passes the source assertion
    and installs, then must red at step 4's byte witness: "sentinel ABSENT from the installed tree". It
    cannot be fooled by in-place loading, because the installed tree never had the sentinel. This keeps
    the byte witness discriminating once the source assertion is in front of it.
- **The existing `hooks` and `.mcp.json` mutants** must still red at their current steps.

**W1–W2: Git-backed migration witnesses, before merge.**
- **Where they run.** On four throwaway remote branches, one per witness (table below). Their commits are
  created through the GitHub contents API, because the intermediate states deliberately fail the
  version-sync validator and hooks are never bypassed. They are never merged, and are deleted afterwards.
- **Config isolation.** Each witness runs in its own `CLAUDE_CONFIG_DIR`, kept under `~/.claude/handoffs/`
  rather than the session scratchpad, which is reaped.
- **The rule for every step.** The registration is never removed or re-added. Each step runs only
  `claude plugin marketplace update <key>` and then `claude plugin update unleashed-mail@<key>`, and every
  command must exit 0.
  1. **Precondition, between the two commands:** the marketplace clone (`installLocation` in that config's
     `known_marketplaces.json`) has HEAD equal to the intended fixture commit. Its `marketplace.json` has
     the intended `name`, `source` and `version`, and its sentinel file contains the sentinel if and only
     if the fixture plants one. A step whose clone did not move is VOID, not a pass. This is what makes the
     negative controls and A3 discriminating.
  2. **Then** record the marketplace key, scope, version, `gitCommitSha`, `installPath`, and the presence of
     the sentinel in `installPath`.
- **Four independent witnesses.** Each has its own throwaway branch and its own config dir, and is
  initialized from `main`'s state. No control inherits another's install.

  | Witness | Branch | Key at install | History |
  |---|---|---|---|
  | W1 | `test/COREDEV-2885-w1` | current | A, then B |
  | W1′ | `test/COREDEV-2885-w1n` | current | A, then B′ |
  | W2 | `test/COREDEV-2885-w2` | former | A2, then A3, then B |
  | W2′ | `test/COREDEV-2885-w2n` | former | A2, then A3, then B′ |

  - **Commit A** is the branch at `main`'s state (`github` source).
  - **A2** is A with the file's `name` set to `npranson-unleashed-mail-plugin`.
  - **A3** restores the name to `unleashedservices-unleashed-mail-plugin`, still on `github`.
  - **B:** source `"./"`; `plugin.json` and the entry version set to `2.8.32-witness-b`; a sentinel planted
    in `scripts/precompact-snapshot.sh`.
  - **B′:** B with the version left at `main`'s, and the SAME sentinel.
- **Install step (every witness):** `marketplace add UnleashedServices/unleashed-mail-plugin#<branch>` at A
  or A2, then install. Expect `main`'s SHA and version (F1), and no sentinel. The key is whatever the file
  then declares: the current name for W1/W1′, the former one for W2/W2′.
- **W2 and W2′, step A3. Observe today's behaviour.** Does `marketplace update <former key>` succeed, and
  is the plugin still listed and enabled under the former key (`claude plugin list --json`)?
  - The version cannot move here: under `github`, the fetched plugin is always `main`'s, at `main`'s
    version. So this step tests resolution, not update; F10's real update came from a `main` bump.
  - It answers README's "will stop resolving" either way.
- **Positive (W1, W2), after B:** expect the same key and scope, version `2.8.32-witness-b`, `gitCommitSha`
  equal to B, and the sentinel present.
- **Negative (W1′, W2′), after B′:** B′'s version equals the installed `main` version. The update must be
  SKIPPED (F6), leaving `main`'s SHA and NO sentinel, although B′ carries one. This shows that the version,
  not the source change alone, is what moves an existing install. That is exactly the bump discipline
  this design relies on.
- **Before / after recording.** All W rows are written to the ticket and to a handoff file, with the raw
  `installed_plugins.json` entries.

**After merge.**
- **C1, after merge to `alpha` (live, isolated config):** `marketplace add`
  `UnleashedServices/unleashed-mail-plugin#alpha`, then install. Assert that `gitCommitSha` equals
  `origin/alpha`'s tip and that the version equals `alpha`'s `plugin.json`.
- **C2, after the promotion that ships this (fresh install):** `marketplace add`
  `UnleashedServices/unleashed-mail-plugin` with no ref, then install. Assert that `gitCommitSha` equals
  `origin/main`'s tip. Before promotion this passes trivially through the `github` source, so it is
  recorded only after.
- **C3, the live migration (in-place update):** an isolated config installed from no-ref `main` BEFORE the
  promotion, and kept. After the promotion, run update. Assert the same key, the new version, and `main`'s
  new SHA. C2 is a fresh install; C3 is the existing-install path that §0 property 2 promises.

## 5. Rollout

1. Gate this plan with dual review, reproduced on byte-identical bytes, then synthesize and persist the
   verdict.
2. Rebase onto `alpha` after COREDEV-2883 (#121) merges. Run W1, W1′, W2 and W2′, each on its own witness
   branch. If the A3 step of W2 or W2′ shows the former key already fails under `github`, stop and report
   before changing anything: that is a pre-existing defect, outside this plan.
3. Implement §3, and run V1–V2.
4. Run the full local gate, then `codex review --base origin/alpha`.
5. Open a PR into `alpha`. **Merge needs the maintainer's word.** Then observe C1, and create C3's
   pre-promotion install.
6. At the next promotion (`alpha` → `main`, maintainer's word), observe C2 and C3.
7. Record every observation on the ticket. Tell the maintainer how to put their machine on `alpha`, and
   that their project-scope install in the app repo follows the same marketplace.

## 6. Out of scope, and boundaries stated rather than covered

- **Per-project channel choice** (one project on `alpha`, another on stable, on the same machine). It needs
  two marketplace names (§2.1, first alternative). It is not requested.
- **Security of the `alpha` channel.** `alpha` carries unreleased, reviewed-but-unpromoted work. Only
  machines that opt in with `#alpha` receive it, and nothing auto-enrolls a machine.
- **The maintainer's project-scope install** (`2.8.25`, in the app repo) is stale for reasons that predate
  this plan (a pin, per COREDEV-2801's notes). It follows the same marketplace, and is reported, not
  changed.
