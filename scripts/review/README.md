# `scripts/review/` — extracted review-orchestration scripts

Shipped, unit-tested scripts extracted from `swift-reviewer`'s inline shell (audit Item 5). Moving the
logic out of the agent body saves ~0.3k tokens per review spawn (~24 lines; the 4–5k figure was the projected total for extracting all four inline blocks — this PR extracts only the Step-4 build gate) and makes it testable.

## `build-verify.sh` — Step 4 build / lint / test gate

Reads the changed-file list (newline-separated, repo-relative — swift-reviewer's Step-1 `$CHANGED`) on
**stdin** and runs, per `AGENT_CONTRACTS.md §5`:

1. `xcodebuild build` (hard gate)
2. SwiftLint two-arm merge gate — changed-`.swift` `--strict` + whole-repo `--strict --baseline` (hard)
3. `xcodebuild test` (hard gate)
4. missing-test-file scan (non-gating ⚠️ warning)

Prints `✅`/`❌` per gate and **exits non-zero if any hard gate failed**. Overridable via `SCHEME` /
`DESTINATION` / `BASELINE` env vars. Consumed by `swift-reviewer` Step 4; `pr-review` relies on that
single run rather than launching its own `xcodebuild test` (dedups the double test-suite run).

```bash
printf '%s\n' "$CHANGED" | bash "${CLAUDE_PLUGIN_ROOT}/scripts/review/build-verify.sh"
```

## Verifying (the logic is unit-tested; the live orchestration needs a canary)

The **script logic** — gate aggregation, changed-`.swift` filtering (existing files only), the empty-set
xargs guard, the missing-test scan — is covered by `scripts/tests/test_build_verify.py` with mocked
`xcodebuild`/`swiftlint`, so it runs in CI **without an Xcode toolchain**:

```bash
python3 -m unittest discover -s scripts/tests
```

What a unit test **cannot** prove is that `swift-reviewer` still *orchestrates* correctly end-to-end
(both plan-review reviewers flagged this — there is no installed-plugin E2E harness). **Canary — run once
against the real app before relying on it:**

1. In the app repo, on a branch with a few changed `.swift` files, run `build-verify.sh` directly:
   `git diff --name-only <base>...HEAD | bash "$CLAUDE_PLUGIN_ROOT/scripts/review/build-verify.sh"` —
   confirm it prints the three `✅`/`❌` gates and the exit code matches (0 iff build+lint+tests pass).
2. Invoke the `swift-reviewer` agent on that same PR and confirm its **Step 4** section reports
   build/lint/test exactly as before (the unified verdict still folds in a failing gate as a blocker).
3. Confirm `pr-review` no longer spawns a second `xcodebuild test` (one test run total for a PR review).

If step 2 shows any orchestration drift, revert the `swift-reviewer.md` Step-4 wiring to the inline block
(the extraction is isolated to that one section) and reopen the Item-5 follow-up.
