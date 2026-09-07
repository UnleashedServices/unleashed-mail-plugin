# `harness-fixtures/` — the parity harness's working directory

This directory exists so the branches below have something to diff against. The harness itself
stages `fixable.sh` at RUNTIME (deliberately mis-indented, `git add --force`d) — it is not
committed here, because the point is to observe what the pinned Trunk action does to a file it
finds newly tracked.

## `harness-base` and `harness/**` are PERMANENT repository citizens

`.github/workflows/trunk-parity-harness.yml` fires on:

    pull_request:  branches: [harness-base]
    push:          branches: ['harness/**']

Those are REAL events on purpose. `workflow_dispatch` is not usable here: the pinned action maps it
to `check-mode=all` — the very mode banned from `trunk-check` — and `GITHUB_EVENT_NAME` cannot be
overridden, so a dispatch-driven harness would measure a mode the gate never runs.

Deleting these branches is a CHANGE, not tidying. They are needed again at every Dependabot bump of
the Trunk action pin, to re-derive the extension-point enumeration that cells 1 and 5 depend on.

## The push observation needs a SECOND push, and that is not a workaround

GitHub sends an all-zero `before` when a branch is **created**. `scripts/ci/resolve-trunk-range.sh`
fails closed on that (correctly — at the pinned SHA the action's `push.sh` would otherwise diff
against the empty tree), so the harness's Trunk step is SKIPPED on the branch-creating push and the
artifact records `outcome: skipped`, `invocations: []`, `resolver.raw: ""`.

That artifact measures NOTHING and must not be accepted as M2c evidence — it is precisely the
"produced is not accepted" case the milestone was written to reject. The real push observation comes
from a subsequent push to an already-existing `harness/**` branch, where `before` is a real SHA.
