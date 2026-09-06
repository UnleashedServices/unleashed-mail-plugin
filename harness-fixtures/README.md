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
