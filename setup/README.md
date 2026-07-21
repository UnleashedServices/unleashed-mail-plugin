# setup/ — review-toolchain bootstrap

Helper scripts for standing up the plan-review gate (`codex` + `agy`) in a fresh
remote/CI environment, and for refreshing the Antigravity credentials it depends on.

Neither script contains secrets — they only move credentials the environment
already holds (env vars, or the macOS Keychain) into the place each CLI reads.

## `install-review-clis.sh` — run **in the remote environment**

Idempotent bootstrap. Reads env vars the environment injects and:

1. installs the Codex CLI (`@openai/codex`) and seeds `~/.codex/auth.json` from
   `$CODEX_AUTH_JSON` (+ writes `~/.codex/config.toml`: `gpt-5.6-sol`, effort `xhigh`);
2. seeds Antigravity (`agy`) OAuth creds from `$AGY_CREDS` (agy itself ships in the image);
3. installs the `unleashed-mail` Claude Code plugin from this repo's marketplace.

```bash
bash setup/install-review-clis.sh
```

Verify:

```bash
codex exec -c model_reasoning_effort=low -s read-only "reply with: pong"   # -> pong
agy -p ping                                                                # -> pong
claude plugin list                                                         # -> unleashed-mail@… enabled
```

> `codex` authenticates from the injected `$CODEX_AUTH_JSON`. `agy` on a headless
> host prefers the OS keyring and only falls back to a file under specific
> conditions, so if `agy -p ping` still shows a login URL the injected `$AGY_CREDS`
> is stale — refresh it with the script below.

## `extract-agy-auth-macos.sh` — run **on a Mac where `agy` is logged in**

Locates agy's OAuth creds (login Keychain first, then the on-disk fallbacks),
validates the blob, and prints `AGY_CREDS` (base64) + `AGY_CREDS_PATH` ready to
paste into the environment's variable/secret config.

```bash
bash setup/extract-agy-auth-macos.sh
```

⚠️ Its output includes a live OAuth refresh token — set it only in the
environment's secret store; never paste it into chat, tickets, or screenshots.
