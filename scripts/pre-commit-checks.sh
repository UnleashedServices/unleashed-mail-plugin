#!/bin/bash
# Pre-commit checks: run linting, tests, and build verification
# Exits non-zero to BLOCK commits if critical issues are found
#
# This script targets the UnleashedMail Xcode project (NOT a SwiftPM package).
# In other repos it does PII scanning only and skips Swift-build/test gracefully.

echo "🔍 Running pre-commit checks..."

EXIT_CODE=0

# COREDEV-2324: shared marker writer for the Stop-gate (build marker). Sourced
# defensively — absence must not break the commit hook.
# MAJ-6 caveat: these marker writes only reach the Claude Code Stop-gate when this git hook runs with
# CLAUDE_PLUGIN_DATA exported to the SAME value the plugin's hooks see (~/.claude/plugins/data/{id}). A git
# hook does not inherit it, so by default marker.sh falls back to ~/.claude/unleashed-mail and the Stop
# gate (which runs as a plugin hook, under plugins/data/{id}) never sees these markers — the writes are a
# harmless local no-op for the gate. To wire them up, export CLAUDE_PLUGIN_DATA in your git-hook env.
_PCC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/lib/marker.sh
[ -f "$_PCC_DIR/lib/marker.sh" ] && . "$_PCC_DIR/lib/marker.sh"

# Detect whether we're in the UnleashedMail Xcode project
HAS_XCODEPROJ=false
if [ -d "Unleashed Mail.xcodeproj" ]; then
    HAS_XCODEPROJ=true
fi

# --- 1. SwiftLint check (Xcode project only) ---
if [ "$HAS_XCODEPROJ" = true ]; then
    if command -v swiftlint >/dev/null; then
        echo "📏 Running SwiftLint..."
        LINT_OUTPUT=$(swiftlint --quiet 2>&1)
        LINT_EXIT=$?

        # This is the FULL-PROJECT lint, so its verdict is authoritative (no per-file
        # masking) — it's the writer that clears the per-file hook's fail-closed lint
        # marker so the Stop-gate sentinel can release (codex + gemini PR #12).
        if [ $LINT_EXIT -ne 0 ]; then
            echo "❌ SwiftLint errors found:"
            echo "$LINT_OUTPUT"
            echo "💡 Run 'swiftlint --fix' to auto-fix some issues"
            EXIT_CODE=1
            command -v marker_write >/dev/null 2>&1 && marker_write lint fail
        else
            echo "✅ SwiftLint passed"
            command -v marker_write >/dev/null 2>&1 && marker_write lint pass
        fi
    else
        echo "⚠️  SwiftLint not installed — install with 'brew install swiftlint'"
    fi
else
    echo "⏭️  Skipping SwiftLint (not in Unleashed Mail Xcode project)"
fi

# --- 2. Build check (Xcode project only) ---
if [ "$HAS_XCODEPROJ" = true ]; then
    echo "🔨 Running build check..."
    BUILD_OUTPUT=$(xcodebuild build \
        -scheme "Unleashed Mail" \
        -destination 'platform=macOS' \
        -quiet 2>&1)
    BUILD_EXIT=$?

    if [ $BUILD_EXIT -ne 0 ]; then
        echo "❌ Build failed:"
        echo "$BUILD_OUTPUT" | tail -30
        EXIT_CODE=1
        command -v marker_write >/dev/null 2>&1 && marker_write build fail
    else
        echo "✅ Build succeeded"
        command -v marker_write >/dev/null 2>&1 && marker_write build pass
    fi
else
    echo "⏭️  Skipping build check (not in Unleashed Mail Xcode project)"
fi

# --- 3. Test subset check (Xcode project only) ---
if [ "$HAS_XCODEPROJ" = true ]; then
    echo "🧪 Running test subset (Database + Mock)..."
    TEST_OUTPUT=$(xcodebuild test \
        -scheme "Unleashed Mail" \
        -destination 'platform=macOS' \
        -only-testing:"Unleashed MailTests/DatabaseTests" \
        -only-testing:"Unleashed MailTests/MockServicesTests" \
        -quiet 2>&1)
    TEST_EXIT=$?

    if [ $TEST_EXIT -ne 0 ]; then
        echo "❌ Tests failed:"
        echo "$TEST_OUTPUT" | tail -30
        EXIT_CODE=1
    else
        echo "✅ Tests passed"
    fi
else
    echo "⏭️  Skipping tests (not in Unleashed Mail Xcode project)"
fi

# --- 3b. Plugin self-validation (plugin repo only — COREDEV-2322 Phase 0) ---
# Runs when NOT in the Xcode app project, i.e. in the unleashed-mail plugin repo.
# Warn mode here (advisory, never blocks the commit); CI runs these in --strict.
if [ "$HAS_XCODEPROJ" = false ]; then
    # Resolve via the repo root so a symlinked git hook ($0 = the symlink) still finds
    # the validators (gemini PR #11); fall back to the script's own dir (NOT
    # dirname+/scripts, which would double to scripts/scripts).
    if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
        SCRIPTS_DIR="$REPO_ROOT/scripts"
    else
        SCRIPTS_DIR="$(dirname "$0")"
    fi
    if [ -f "$SCRIPTS_DIR/validate-version-sync.sh" ]; then
        echo "🧩 Validating plugin version sync..."
        VERSION_SYNC_ENFORCE=warn bash "$SCRIPTS_DIR/validate-version-sync.sh" || true
    fi
    if [ -f "$SCRIPTS_DIR/validate-plugin-assembly.py" ] && command -v python3 >/dev/null; then
        echo "🧩 Validating plugin assembly (frontmatter + manifests)..."
        python3 "$SCRIPTS_DIR/validate-plugin-assembly.py" || true
    fi
    if [ -f "$SCRIPTS_DIR/validate-hooks.py" ] && command -v python3 >/dev/null; then
        echo "🧩 Validating hooks manifest (events + matchers + script refs)..."
        python3 "$SCRIPTS_DIR/validate-hooks.py" || true
    fi
fi

# --- 4. Secret / PII scan in staged files (universal, ADVISORY) ---
# MAJ-7: the previous scan was a complete no-op — it only inspected *.swift files (this plugin repo has
# none), its email/alternation patterns used ERE syntax under BRE `grep` so they could never match, and it
# never set EXIT_CODE so it could not block. It is replaced by a correct `grep -nE` scan over ALL staged
# TEXT files. It is ADVISORY (warn) by design: this repo legitimately contains secret-SHAPED test fixtures
# and redaction-regex literals, so a hard block here would false-positive constantly. The ENFORCING gate is
# `gitleaks --staged` below (which honours .gitleaks.toml's allowlist) when installed, plus the history-aware
# gitleaks job in CI. See CLAUDE.md and SECURITY.md.
echo "🔒 Scanning staged files for secrets / PII (advisory)..."
if command -v git >/dev/null; then
    # ERE patterns (grep -nE) — portable across GNU and BSD grep (no `\|`/`\{n\}` BRE forms).
    SECRET_PATTERNS=(
        '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'                                 # email
        '[Bb][Ee][Aa][Rr][Ee][Rr][[:space:]]+[A-Za-z0-9._-]{20,}'                        # bearer token
        'eyJ[A-Za-z0-9._-]{10,}'                                                          # JWT
        '(sk-|pk_)[A-Za-z0-9._-]{16,}'                                                    # sk-/pk_ secret
        '[Aa][Pp][Ii][_-]?[Kk][Ee][Yy][[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{12,}'   # api key = <value>
    )
    FOUND_PII=0
    # Null-delimited paths so "Unleashed Mail/..." with embedded spaces survives (word-splitting would skip them).
    while IFS= read -r -d '' file; do
        [ -f "$file" ] || continue
        grep -Iq . "$file" 2>/dev/null || continue   # `-I` => skip binary files (no text line)
        for pattern in "${SECRET_PATTERNS[@]}"; do
            if grep -nE "$pattern" "$file" >/dev/null 2>&1; then
                echo "⚠️  Possible secret/PII in $file (pattern: $pattern)"
                echo "   Review: use environment variables / secure storage, or allowlist a known-safe fixture in .gitleaks.toml."
                FOUND_PII=1
            fi
        done
    done < <(git diff --cached --name-only -z --diff-filter=ACM)

    # Enforcing pass: gitleaks honours .gitleaks.toml (fixtures/history allowlisted there), so it can BLOCK
    # a real staged secret without false-positiving on this repo. Only runs when installed; a tooling error
    # (unsupported subcommand, bad config) must NOT block a commit — only a clean "leaks found" (exit 1) does.
    if command -v gitleaks >/dev/null 2>&1; then
        echo "🔒 Running gitleaks on staged changes..."
        # gitleaks reorganized its CLI across v8: `git --staged` (>=8.19) replaced `protect --staged`.
        if gitleaks git --help >/dev/null 2>&1; then
            GL_CMD=(gitleaks git --staged)
        else
            GL_CMD=(gitleaks protect --staged)
        fi
        "${GL_CMD[@]}" --no-banner --redact --config .gitleaks.toml >/dev/null 2>&1
        GL_RC=$?
        if [ "$GL_RC" -eq 1 ]; then
            echo "❌ gitleaks flagged a staged secret. Run '${GL_CMD[*]} --verbose' to see it."
            echo "   If it is a known-safe fixture, allowlist it in .gitleaks.toml."
            EXIT_CODE=1
        elif [ "$GL_RC" -ne 0 ]; then
            echo "⚠️  gitleaks could not run cleanly (exit $GL_RC) — skipping enforcement (CI runs the authoritative scan)."
        else
            echo "✅ gitleaks: no staged secrets"
        fi
    elif [ "$FOUND_PII" -eq 1 ]; then
        echo "   (gitleaks not installed — the pattern scan above is advisory only; CI runs the enforcing scan.)"
    fi
fi

# --- Summary ---
if [ $EXIT_CODE -eq 0 ]; then
    echo "🎉 All pre-commit checks passed!"
else
    echo "❌ Pre-commit checks failed. Please fix the issues above."
fi

exit $EXIT_CODE
