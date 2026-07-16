# Security Policy

## Reporting a vulnerability

Please report suspected security issues **privately** — do not open a public issue.
Use GitHub's private vulnerability reporting for this repository
(**Security → Report a vulnerability**), or contact the maintainer directly.
You should receive an acknowledgement within a few business days.

## Secret scanning

CI runs a history-aware [gitleaks](https://github.com/gitleaks/gitleaks) scan
(`.github/workflows/plugin-ci.yml`, the `secret-scan` job) over the **full git history**
on every push to `main` or `alpha`, and every pull request **targeting `main` or `alpha`**
(the workflow's `push`/`pull_request` triggers filter on those two branches). `alpha` is the
integration branch releases are cut from; until COREDEV-2494 the triggers filtered on `main`
alone, so PRs into `alpha` — which is most of them — ran no scan at all. The ruleset extends the gitleaks default;
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

The `firebase-debug.log` exemption is **commit-scoped** to the only two commits that file ever
existed in (`edc27bf` added it, `1f18944` removed it), so a new secret committed into that exact
filename **is still caught**. Until COREDEV-2494 it was a blanket path exemption, which made this
paragraph's guarantee untrue for precisely the filename most likely to reappear from a `firebase`
CLI run. Any change to that exemption must keep it commit-scoped.

Tracking: COREDEV-2486 (2026-07-14 plugin audit, finding `critic.1`).
