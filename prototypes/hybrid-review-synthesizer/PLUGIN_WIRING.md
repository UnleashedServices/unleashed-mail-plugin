# Wiring the synthesizer into the plugin as an MCP server

What/where/how, concretely. Nothing here is hypothetical — `mcp_server.py` in this
directory is a working stdio MCP server (verified with a real `initialize` →
`tools/list` → `tools/call` handshake).

## What kind of server

A **local stdio MCP server**. MCP-over-stdio is newline-delimited JSON-RPC 2.0, so
`mcp_server.py` implements it with the **standard library only** — no `mcp` SDK, no
`uvx`, no pip — matching the plugin's existing all-stdlib scripts (`pty-capture.py`).
It exposes one tool, `synthesize_review`, that wraps the deterministic
`synthesize.py`.

Not HTTP/SSE, not remote. Pure compute, no network, no secrets → stdio is the right
transport.

## Where it's "hosted"

**Nowhere central — it runs as a subprocess on whatever machine runs Claude Code**
(a dev laptop, or CI). Claude Code spawns it when the plugin is enabled, talks to it
over stdin/stdout, and tears it down with the session. There is no port, no deploy,
no auth, no uptime to manage. "Hosting" = the plugin ships the script; Claude Code
launches it on demand.

(If you ever wanted a *team-shared* synthesizer — one canonical ruleset everyone
hits — you'd switch the same code to `streamable-http` transport and deploy it once.
Unnecessary for pure compute; it would add a network + ops surface for no benefit.)

## How — three edits to the plugin

### 1. Move the synthesizer under the plugin

```
unleashed-mail-plugin/
└── mcp/
    └── review-synthesizer/
        ├── mcp_server.py      # the stdio server (this dir's file)
        ├── synthesize.py      # deterministic dedup/verdict
        └── schema.py          # canonical Finding schema + strict tool def
```

### 2. Declare the server — root `.mcp.json` (new file)

```json
{
  "mcpServers": {
    "review-synthesizer": {
      "command": "python3",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/review-synthesizer/mcp_server.py"]
    }
  }
}
```

- `${CLAUDE_PLUGIN_ROOT}` resolves to the plugin's install dir on any machine.
- It auto-starts when the plugin is enabled — no install step.
- (Equivalent alternative: an `mcpServers` block inside `.claude-plugin/plugin.json`.
  Keep it in `.mcp.json` to keep the manifest clean.)

### 3. Let `swift-reviewer` call it

The plugin name is `unleashed-mail` and the server key is `review-synthesizer`, so
Claude Code exposes the tool as (non-alphanumeric → `_`):

```
mcp__plugin_unleashed_mail_review_synthesizer__synthesize_review
```

In `agents/swift-reviewer.md` frontmatter:

```yaml
allowed-tools: Read, Bash, Grep, Glob, Agent, mcp__plugin_unleashed_mail_review_synthesizer__synthesize_review
```

And Step 5 collapses from prose dedup rules to one call:

> ### Step 5: Synthesize (deterministic)
> Collect the four reviewers' JSON arrays plus your `parity` / `test-coverage` /
> `verification` rows. Call
> `mcp__plugin_unleashed_mail_review_synthesizer__synthesize_review` with
> `{ findings: [...all rows...], changed_files: [...$CHANGED...] }`. It returns the
> consolidated report (markdown) and a structured verdict — **use its verdict as the
> review verdict.** The dedup, ownership routing, scope filter, and verify gate run
> in code, so they can't silently drop a finding or gate on an unverified one.

The reviewer agents (`security-reviewer.md`, etc.) are **unchanged** — they still
emit the same JSON findings array. Only the orchestrator's Step-5 *logic* moves from
prose into the tool.

## Test it the way Claude Code will

```bash
cd mcp/review-synthesizer
# minimal smoke test — should print a JSON-RPC reply naming the server:
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}}' | python3 mcp_server.py
# full handshake + a real synthesize call: see the driver in the chat / README
claude --debug   # surfaces MCP server init errors if the spawn fails
```

## Option B — official SDK + uvx (if you prefer not to hand-roll JSON-RPC)

Same architecture, fewer lines, but adds a toolchain dependency (`uv`/`uvx` or a
vendored `mcp`):

```python
# mcp_server_fastmcp.py
from mcp.server.fastmcp import FastMCP        # high-level API
from synthesize import synthesize, render_markdown
from schema import parse_finding

mcp = FastMCP("review-synthesizer")

@mcp.tool()
def synthesize_review(findings: list[dict], changed_files: list[str]) -> str:
    """Deterministically merge reviewer findings into one verdict + report."""
    parsed, bad = [], []
    for d in findings:
        try: parsed.append(parse_finding(d))
        except Exception as e: bad.append((d, str(e)))
    return render_markdown(synthesize(parsed, set(changed_files), quarantined=bad))

if __name__ == "__main__":
    mcp.run()   # stdio by default
```

```json
{ "mcpServers": { "review-synthesizer": {
    "command": "uvx", "args": ["--with", "mcp", "python", "${CLAUDE_PLUGIN_ROOT}/mcp/review-synthesizer/mcp_server_fastmcp.py"]
}}}
```

**Recommendation:** ship the **stdlib server** (Option A, `mcp_server.py`). It keeps
the plugin's zero-install, bare-`python3` property; the JSON-RPC surface it
implements is tiny and stable. Reach for FastMCP only if the protocol surface grows
(resources, prompts, progress streaming).

## Gotchas (from the Claude Code MCP docs)

- **stdout is the protocol channel.** Never `print()` to it — logs go to stderr
  (the server already does this).
- **Startup failures are silent** until you run `claude --debug`. Smoke-test the
  handshake first.
- **cwd isn't the plugin dir.** `mcp_server.py` does `sys.path.insert(0, <its dir>)`
  so `import synthesize` works regardless of where Claude Code launches it.
- **Interpreter:** `python3` must be on PATH. If that's unreliable in your fleet,
  pin an absolute interpreter or use the `uvx` form.
