#!/usr/bin/env bash
# swift-reviewer Step 4 / pr-review — Build + Lint + Test verification (AGENT_CONTRACTS §5).
#
# Reads the changed-file list (newline-separated, repo-relative — the `$CHANGED` that swift-reviewer
# Step 1 produces) on STDIN, then runs the three hard gates + the missing-test check:
#   1. xcodebuild build            (hard gate)
#   2. SwiftLint two-arm merge gate: changed-.swift `--strict` + whole-repo `--strict --baseline` (hard)
#   3. xcodebuild test             (hard gate)
#   4. missing-test-file scan      (non-gating ⚠️ warning)
# Prints ✅/❌ per gate and EXITS NON-ZERO if ANY hard gate failed, so a caller (swift-reviewer,
# pr-review) can gate on the exit code instead of re-parsing prose — and both can share this one run
# rather than each spawning their own xcodebuild (dedups the "tests run twice" path).
#
# Env overrides (defaults match the app project; overridable for tests / non-default schemes):
#   SCHEME       (default "Unleashed Mail")
#   DESTINATION  (default "platform=macOS")
#   BASELINE     (default "swiftlint-baseline.json")
set -o pipefail   # REQUIRED: without it, `| tail` returns tail's 0 and masks a failing xcodebuild/swiftlint.

SCHEME="${SCHEME:-Unleashed Mail}"
DESTINATION="${DESTINATION:-platform=macOS}"
BASELINE="${BASELINE:-swiftlint-baseline.json}"

# Changed files on stdin (portable; no arg-length limit, no shared-shell-state assumption).
CHANGED="$(cat)"

# --- 1. Build — must succeed (paths contain spaces; quote the scheme) ---
# B6 (COREDEV-2503): `build-for-testing` compiles the app AND the test targets ONCE; step 3 then runs
# `test-without-building`, so the sources are compiled a single time (the plain `build` + `test` pair
# recompiled everything twice).
xcodebuild build-for-testing -scheme "$SCHEME" -destination "$DESTINATION" 2>&1 | tail -10
BUILD=$?; [ "$BUILD" -eq 0 ] && echo "✅ build" || echo "❌ build FAILED (exit $BUILD)"

# --- 2. SwiftLint — both arms of the merge gate ---
#   (1) changed .swift files `--strict` (warnings→errors); keep only paths that still exist (a
#       deleted/renamed-away file has nothing to lint); the empty-set guard skips xargs entirely
#       (BSD/macOS-safe — no GNU-only `-r`).
#   (2) whole-repo `--strict --baseline` so only NEW violations fail (existing backlog baselined).
CHANGED_SWIFT=$(printf '%s\n' "$CHANGED" | { grep -E '\.swift$' || true; } | while IFS= read -r f; do
    [ -f "$f" ] && printf '%s\n' "$f"
done)
if [ -n "$CHANGED_SWIFT" ]; then
    printf '%s\n' "$CHANGED_SWIFT" | tr '\n' '\0' | xargs -0 swiftlint --strict --quiet 2>&1 | tail -20
    CHANGED_LINT=$?
else
    CHANGED_LINT=0
fi
swiftlint lint --strict --baseline "$BASELINE" --quiet 2>&1 | tail -20; BASELINE_LINT=$?
LINT=$(( CHANGED_LINT | BASELINE_LINT ))
[ "$LINT" -eq 0 ] && echo "✅ lint" || echo "❌ lint FAILED (changed=$CHANGED_LINT baseline=$BASELINE_LINT)"

# --- 3. Tests — must pass (reuse the build-for-testing product; do NOT recompile — B6) ---
xcodebuild test-without-building -scheme "$SCHEME" -destination "$DESTINATION" 2>&1 | tail -30
TEST=$?; [ "$TEST" -eq 0 ] && echo "✅ tests" || echo "❌ tests FAILED (exit $TEST)"

# --- 4. Missing-test-file scan (non-gating warning) ---
printf '%s\n' "$CHANGED" | while IFS= read -r f; do
    [ -z "$f" ] && continue
    case "$f" in
        "Unleashed Mail/Sources/"*.swift)
            test_path="$(printf '%s' "$f" | sed 's|Unleashed Mail/Sources/|Unleashed MailTests/|;s|\.swift$|Tests.swift|')"
            [ -f "$test_path" ] || echo "⚠️  Missing test file: $test_path → source $f"
            ;;
    esac
done

# Exit non-zero if any HARD gate failed (build / lint / test). The missing-test scan is advisory.
if [ "$BUILD" -ne 0 ] || [ "$LINT" -ne 0 ] || [ "$TEST" -ne 0 ]; then
    exit 1
fi
exit 0
