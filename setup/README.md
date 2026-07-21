# setup/ — review-toolchain bootstrap

Helper scripts for standing up the plan-review gate (`codex` + `agy`) in a fresh
remote/CI environment, and for (re)generating the Antigravity credential it needs.

No script contains secrets — they only move credentials the environment already
holds (env vars, the macOS Keychain, or a completed agy login) into the place each
CLI reads.

## The `agy` credential format (important)

`agy`'s credential is **not** a raw Google-OAuth blob. Its token file
(`~/.gemini/antigravity-cli/antigravity-oauth-token`, path also given by
`$AGY_CREDS_PATH`) is:

```json
{ "auth_method": "consumer",
  "token": { "access_token": "…", "expiry": "2026-…Z",
             "refresh_token": "…", "token_type": "Bearer" } }
```

`AGY_CREDS` is the **base64 of that file**. The `auth_method` field is the
critical part: it's what lets agy **refresh** an expired access token. A raw
`oauth_creds.json`-style blob (`access_token`/`refresh_token`/`expiry_date`/`scope`
at top level, no `auth_method`) is what breaks things — agy reads it, finds no
auth method, logs `keyringAuth: failed to get oauth params: unknown auth method`,
and falls back to an interactive browser login it can't complete headlessly.

**Failure mode this caused:** such a blob "works" only until its ~1-hour access
token expires; then agy can't refresh (no `auth_method`) and can never recover.
On a headless/Linux host agy uses file storage and reads that file directly; on
macOS it uses the login Keychain (service `gemini`, accounts
`<email>:accessToken` / `:refreshToken` / `:tokenExpiry`).

## `install-review-clis.sh` — run **in the remote environment**

Idempotent bootstrap. Reads env vars the environment injects and:

1. installs the Codex CLI (`@openai/codex`) and seeds `~/.codex/auth.json` from
   `$CODEX_AUTH_JSON` (+ writes `~/.codex/config.toml`: `gpt-5.6-sol`, effort `xhigh`);
2. seeds Antigravity (`agy`) creds from `$AGY_CREDS` (agy itself ships in the image);
3. installs the `unleashed-mail` Claude Code plugin from this repo's marketplace.

```bash
bash setup/install-review-clis.sh
# verify:
codex exec -c model_reasoning_effort=low -s read-only "reply with: pong"   # -> pong
agy -p ping                                                                # -> pong
claude plugin list                                                         # -> unleashed-mail@… enabled
```

If `agy -p ping` still shows a login URL, `$AGY_CREDS` is stale or the wrong
shape (see above) — regenerate it below.

## Getting / regenerating `AGY_CREDS`

### A. From any file-mode host where agy is already logged in (easiest)

On Linux/headless hosts (including this environment) agy writes the token file
directly, so extraction is one line:

```bash
bash setup/get-agy-creds.sh          # validates the envelope, prints AGY_CREDS
```

Because agy auto-refreshes, this env's file stays current — re-run any time to
pull a fresh `AGY_CREDS`.

### B. From your Mac's Keychain

```bash
bash setup/extract-agy-auth-macos.sh            # or: … you@example.com
```

Reads the `gemini` Keychain entries and rebuilds the envelope (with `expiry` set
in the past so agy refreshes on first use). macOS will prompt to allow Keychain
access — click Allow.

### C. Fresh login (only if the refresh token was revoked)

Run a real agy login on a **file-storage host** (this env is one) so agy writes a
correct token file:

```bash
python3 setup/agy-login.py &                     # prints the Google URL to /tmp/agy-login.out
# open that URL in a browser (target account), approve within ~60s, then:
printf '%s' '<code-from-antigravity.google/oauth-callback?code=…>' > /tmp/agy-login.code
bash setup/get-agy-creds.sh                       # -> new AGY_CREDS
```

⚠️ `AGY_CREDS` contains a live OAuth refresh token — set it only in the
environment's secret store; never paste it into chat, tickets, or screenshots.
Keep `AGY_CREDS_PATH=~/.gemini/antigravity-cli/antigravity-oauth-token`.

## Storing all credentials for re-provisioning

The environment injects three credentials. All extractors below print to stdout —
capture them into your **secret manager** (never plaintext/chat). They are live
credentials.

| Env var | What | Durable? | Re-extract with |
|---------|------|----------|-----------------|
| `CODEX_AUTH_JSON` | base64 of `~/.codex/auth.json` (ChatGPT-mode, has refresh_token) | ✅ auto-refreshes | `bash setup/get-codex-creds.sh` |
| `AGY_CREDS` (+ `AGY_CREDS_PATH`) | base64 of agy's token file (`auth_method`+`token`) | ✅ auto-refreshes **once auth_method is present** | `bash setup/get-agy-creds.sh` (see §A–C above) |
| `GH_TOKEN` | GitHub token (fine-grained `github_pat_…` here) | ✅ until PAT expiry; `ghs_…` variants are ~1h and not worth storing | `bash setup/get-github-token.sh` |

Notes:
- **codex** and **GitHub** were already correct in this environment — just store
  the values. Only **agy** needed the format fix documented above (the injected
  blob lacked `auth_method`).
- `~/.codex/config.toml` (model `gpt-5.6-sol`, effort `xhigh`) is config, not a
  secret — `install-review-clis.sh` recreates it, so it doesn't need storing.
- To re-provision a fresh environment, set these env vars and run
  `bash setup/install-review-clis.sh`.
