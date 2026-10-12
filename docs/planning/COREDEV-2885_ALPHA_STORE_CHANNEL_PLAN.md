# COREDEV-2885 — An install channel for `alpha`: the marketplace's ref must decide the plugin's ref

**Status:** Planning, revision 1. Not yet gated.
**Ticket:** COREDEV-2885 (Epic COREDEV-2485). Follows COREDEV-2883, which set the branch flow to
`main` > `alpha` > feature work.
**Branch / worktree:** `feat/COREDEV-2885-alpha-store-channel`, `.claude/worktrees/2885-alpha-channel`, cut
from `origin/alpha` at `91ee033`.

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
2. A machine that adds it with no ref (every existing install) keeps installing `main`'s bytes, with no
   manual migration.
3. A promotion (`alpha` → `main`) never conflicts over, and never needs a per-branch edit to, the store
   manifest.
4. CI proves the shipped manifest installs the checkout's own bytes, with no rewrite of the source field.

## 1. Verified facts (2026-10-12, Claude Code 2.1.296, against `alpha` `91ee033` and `main` `a100645`)

Every probe ran under `CLAUDE_CONFIG_DIR=<scratch>`, so the maintainer's real plugin configuration was
never touched. **F0:** that isolation holds. A fresh config dir lists only the built-in
`anthropic-plugin-directory`, and the real `~/.claude/plugins/known_marketplaces.json` was unchanged.

- **F1. The plugin entry pins `main` independently of the marketplace's ref.** `.claude-plugin/marketplace.json`'s
  entry is `{"source":"github","repo":"UnleashedServices/unleashed-mail-plugin"}`, with no `ref`. Probe 1 ran
  `claude plugin marketplace add 'UnleashedServices/unleashed-mail-plugin#alpha'` and then installed:
  - the marketplace was recorded as `{"source":"github",...,"ref":"alpha"}` and cloned at `alpha`;
  - the installed `gitCommitSha` was `a100645`, **`main`'s tip**, not `alpha`'s `91ee033`.

  `alpha` and `main` had byte-identical trees, so the SHA, not the content, is the discriminator. The docs
  agree: a `github` plugin source with no `ref` "defaults to the repository default branch".
- **F2. A plugin entry that pins `ref: alpha` installs `alpha`.** Probe 2a used a separate marketplace
  named `unleashed-mail-alpha` whose entry is `{"source":"github",...,"ref":"alpha"}`. It installed
  `gitCommitSha` `91ee033`, which equals `origin/alpha`.
- **F3. A relative source `"./"` is accepted and installs the marketplace's OWN tree.** Probe 3b used a clone
  of `91ee033` with the entry's source set to `"./"` and both versions set to `2.8.32-probe`, committed as
  `c1f2b80` on a branch `probe`. It installed version `2.8.32-probe` at `gitCommitSha` `c1f2b80`, which is
  the clone's own commit, not either remote branch. `scripts/ci-load-check.sh` has relied on `"./"` since
  COREDEV-2598, and records that absolute and `../` sources are rejected (`plugins.0.source: Invalid
  input`, verified there on 2.1.220).
- **F4. The marketplace's ref decides what a relative source resolves to.** The docs say a relative path
  "is resolved relative to the marketplace root" and "only work[s] when the marketplace is added via Git".
  F1 shows a `#alpha` marketplace is cloned at `alpha`. So under `"./"`, a `#alpha` marketplace installs
  `alpha`'s tree. **This combination is INFERRED from F1 + F3, not yet observed end to end:** the CLI
  rejects `file://` URLs (`Invalid marketplace source format`), so it could not be probed without pushing.
  §4 cell C1 observes it live.
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

## 2. Design: a relative source, so the marketplace's ref decides the plugin's ref

Change the one entry's `source` in `.claude-plugin/marketplace.json` from
`{"source":"github","repo":"UnleashedServices/unleashed-mail-plugin"}` to `"./"`. Nothing else in the file
changes. In particular, the name `unleashedservices-unleashed-mail-plugin` and the entry `version` stay.

| Channel | How a machine joins it | What it installs |
|---|---|---|
| stable | `claude plugin marketplace add UnleashedServices/unleashed-mail-plugin` (every existing install) | `main`'s tree at `main`'s version |
| alpha | `claude plugin marketplace add UnleashedServices/unleashed-mail-plugin#alpha` | `alpha`'s tree at `alpha`'s version |

**Why this meets §0:**
1. A `#alpha` marketplace is cloned at `alpha` (F1), and `"./"` installs that clone's tree (F3, F4).
2. A no-ref marketplace is cloned at `main` and installs `main`'s tree: the same bytes it installs today, by
   a different route. The entry version still moves with every bump, so the pull signal (F7) is unchanged.
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
  not asked for. It stays a possible follow-up.
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
   otherwise, so a regression to `github` reds CI at the load layer. The header's point 1 and the "FIDELITY
   GAP" note are rewritten. The gap is closed, not annotated. The mutant table's `github` row stays as a
   regression mutant.
3. **`scripts/validate-plugin-assembly.py`:** assert that the entry's source is exactly `"./"`, with the
   reason stated (§0's property 1).
4. **`README.md`:** a "Release channels" subsection in the install section. It covers stable (default), how to
   join alpha, how to switch and why a switch reinstalls, and `--plugin-dir`.
5. **`CLAUDE.md` "Branch flow":** replace "COREDEV-2885 tracks an install channel for `alpha`; until then …"
   with the channel's join command.
6. **Version bump** to the next free patch at merge time: 2.8.34 if COREDEV-2884's 2.8.33 lands first. That
   means five sync points plus a CHANGELOG entry, and `marketplace.json` itself is the shipped change.

## 4. Verification cells (each must be seen red, for the stated reason)

**Before merge (local):**
- **V1:** `validate-plugin-assembly.py --strict` passes with `"./"`. Mutate the entry back to the `github`
  object, and it reds with the new reason.
- **V2:** `ci-load-check.sh` passes on the branch. Mutate the shipped source back to `github`, and it reds
  at the new source assertion (before any install). The existing sentinel mutant still reds at step 4.
- **V3: the migration witness, isolated config.**
  1. Install from a local-path marketplace built from `main` (`github` source), which records the current
     stable install.
  2. Point the marketplace at a local clone of this branch (`"./"`, bumped version) and run
     `claude plugin marketplace update` and `claude plugin update`.
  3. Assert that the installed version is the new one and that the sentinel planted in the clone is present
     in `installPath`.

  Red control: with the version NOT bumped, the update is skipped (F6), so the assertion must fail.

**After merge to `alpha` (live, isolated config, read-only against the repo):**
- **C1:** `marketplace add UnleashedServices/unleashed-mail-plugin#alpha`, then install. Assert that
  `gitCommitSha` equals `origin/alpha`'s tip and that the version equals `alpha`'s `plugin.json`. This
  observes F4 end to end.
- **C2:** `marketplace add UnleashedServices/unleashed-mail-plugin` (no ref), then install. Assert that
  `gitCommitSha` equals `origin/main`'s tip. Until promotion, `main` still has the `github` source, so this
  cell is re-run after the promotion that ships this change.

## 5. Rollout

1. Gate this plan with dual review, reproduced on byte-identical bytes, then synthesize and persist the
   verdict.
2. Implement §3 and run §4 V1–V3.
3. Run the full local gate, then `codex review --base origin/alpha`.
4. Open a PR into `alpha`. **Merge needs the maintainer's word.** Then observe C1.
5. At the next promotion (`alpha` → `main`, maintainer's word), observe C2. Until then, existing installs are
   untouched, because `main` keeps the old entry.
6. Record C1 and C2 on the ticket. Tell the maintainer how to put their machine on `alpha`, and note that
   their project-scope install in the app repo follows the same marketplace.

## 6. Out of scope, and boundaries stated rather than covered

- **Per-project channel choice** (one project on `alpha`, another on stable, on the same machine). It needs
  two marketplace names (§2.1, first alternative). It is not requested.
- **Security of the `alpha` channel.** `alpha` carries unreleased, reviewed-but-unpromoted work. Only
  machines that opt in with `#alpha` receive it, and nothing auto-enrolls a machine.
- **A marketplace whose recorded name differs from the file's `name`.** The maintainer's own install is
  keyed `npranson-unleashed-mail-plugin` (from the repo's former owner) while the file says
  `unleashedservices-unleashed-mail-plugin`. That predates this plan and is unchanged by it. V3 runs on the
  file's name, and §5 step 6 re-adds the marketplace, which normalizes the key.
