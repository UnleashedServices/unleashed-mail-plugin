# Security Policy

## Reporting a vulnerability

Please report suspected security issues **privately** — do not open a public issue.
Use GitHub's private vulnerability reporting for this repository
(**Security → Report a vulnerability**), or contact the maintainer directly.
You should receive an acknowledgement within a few business days.

## Secret scanning

CI runs a history-aware [gitleaks](https://github.com/gitleaks/gitleaks) scan
(`.github/workflows/plugin-ci.yml`, the `secret-scan` job) over the **full git history**
on every push to `main` and every pull request **targeting `main`** (the workflow's
`push`/`pull_request` triggers filter on `main`). The ruleset extends the gitleaks default;
the configuration and the accepted-exposure allowlist live in [`.gitleaks.toml`](.gitleaks.toml).

Run it locally before pushing:

```bash
gitleaks git --config .gitleaks.toml .
```

## Known / accepted historical exposure

This repository is public and distributed via `claude plugin marketplace add`. In March 2026 a
debug log was briefly committed and then removed from `HEAD` (commit `1f18944`, "remove sensitive
data from public repo"). The team has decided **not to rewrite git history** — a rewrite would
invalidate every existing clone, fork, and open PR. Instead the exposed identifiers are treated as
public and rotated on the provider side:

- **`firebase-debug.log`** (added in `edc27bf`, deleted in `1f18944`) — the logged API endpoints and
  OAuth scopes are treated as public. It remains retrievable from history.
- **GCP project id `emailwithai-476119`** (the Gmail Pub/Sub push topic), replaced with a placeholder
  in `HEAD`. A project id is not itself a credential, but the associated Pub/Sub topic and any OAuth
  client should be reviewed/rotated on the GCP side and treated as if public.

Both are allowlisted in `.gitleaks.toml` so the scan passes on the existing history while still
failing on any **new** secret — or any *other* historical secret not on the allowlist.

Tracking: COREDEV-2486 (2026-07-14 plugin audit, finding `critic.1`).
