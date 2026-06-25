"""Two ways to feed findings into the synthesizer — the "hybrid" seam.

PATH A — keep the markdown reviewers (today's Claude Code agents). They already
end their report with a JSON findings array; this just validates it on ingest.
No API key, no `anthropic` install. This is the recommended hybrid: portable
markdown reviewers + deterministic coded synthesis.

PATH B — drive a reviewer through the Anthropic API with GUARANTEED schema-valid
output. Use this only if/when you move a reviewer off markdown into the coded
harness. Requires `pip install anthropic` and ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json

from schema import (
    REPORT_FINDING_TOOL,
    REPORT_FINDINGS_SCHEMA,
    Finding,
    parse_finding,
)


# --------------------------------------------------------------------------- #
# PATH A — ingest the markdown reviewers' JSON (no deps, no key)
# --------------------------------------------------------------------------- #

def load_reviewer_json(path: str) -> tuple[list[Finding], list[tuple[dict, str]]]:
    raw = json.load(open(path))
    items = raw["findings"] if isinstance(raw, dict) else raw
    good, bad = [], []
    for d in items:
        try:
            good.append(parse_finding(d))
        except Exception as exc:  # noqa: BLE001 - quarantine
            bad.append((d, str(exc)))
    return good, bad


# --------------------------------------------------------------------------- #
# PATH B — run a reviewer via the API with a guaranteed-valid schema
# --------------------------------------------------------------------------- #

REVIEWER_SYSTEM = {
    "security-reviewer": (
        "You are the security reviewer for UnleashedMail (macOS, Swift). Review the "
        "changed files for credential exposure, OAuth, Keychain, WKWebView injection, "
        "CI, entitlements, SQLCipher, and HTML sanitization. Emit one finding object "
        "per issue using the schema; use only your category vocabulary."
    ),
    # ... concurrency-reviewer, ux-perf-reviewer, accessibility-auditor analogous.
}


def run_reviewer_structured(agent: str, changed_files_blob: str,
                            model: str = "claude-opus-4-8") -> list[Finding]:
    """Structured-output form: ``output_config.format`` makes the first text block
    a schema-valid ``{"findings": [...]}``. This is the path the claude-api skill
    recommends for 'return one validated object'."""
    import anthropic  # lazy — only needed on PATH B

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=16000,
        system=REVIEWER_SYSTEM[agent],
        messages=[{"role": "user", "content": changed_files_blob}],
        output_config={"format": {"type": "json_schema", "schema": REPORT_FINDINGS_SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return [parse_finding(d) for d in json.loads(text)["findings"]]


def run_reviewer_strict_tool(agent: str, changed_files_blob: str,
                             model: str = "claude-opus-4-8") -> list[Finding]:
    """Strict-tool form: the model calls ``report_finding`` once per finding, and
    ``strict: true`` guarantees each ``tool_use.input`` validates. Collect them in
    a manual loop (omitted: feeding tool_result back until end_turn)."""
    import anthropic  # lazy

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=16000,
        system=REVIEWER_SYSTEM[agent] + " Call report_finding once per issue.",
        messages=[{"role": "user", "content": changed_files_blob}],
        tools=[REPORT_FINDING_TOOL],
        tool_choice={"type": "any"},  # must call a tool; parallel calls allowed
    )
    return [parse_finding(b.input) for b in resp.content if b.type == "tool_use"]
