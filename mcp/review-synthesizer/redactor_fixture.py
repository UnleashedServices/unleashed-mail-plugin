#!/usr/bin/env python3
"""Canonical shell/Python redactor parity fixture (COREDEV-2597 §4.4).

THE SINGLE SOURCE. `tests/test_redactor_parity.py` imports this module and drives BOTH
implementations from it — `scripts/lib/hook-io.sh::hook_redact_pii` and
`capture.py::redact_pii`. Do not duplicate these vectors into a per-side test: rounds 3 and 4 of
the plan review each found divergences a per-rule fixture had filed under the wrong rule and never
generated.

WHY THIS IS NOT JUST A LIST
---------------------------
Three of the nine known divergence root causes have UNBOUNDED generators, so no list of inputs can
close the set:

  * the `_EMAIL` `@Nx` exemption   = 104 ASCII case spellings of the image extensions
                                     x unbounded `[0-9]+` x arbitrary local part
                                     x any codepoint outside `[A-Za-z0-9.-]`
  * the whitespace classes          = 4 slots x 23 codepoints x unbounded run length
  * the (now deleted) tilde lookahead was 2 keywords x ~969k trailing codepoints

So this file carries (a) representative rows, (b) GENERATORS for the unbounded classes, and
(c) the nine MUST-AGREE negative controls — inputs that look like they should diverge and do not.
Without (c) the fixture drifts toward over-exempting. The mechanical closure argument lives in
`redactor_model.py`; this fixture is the human-readable half.

Non-ASCII vectors are built with `chr()`/`\\u` ON PURPOSE — pasting characters like U+212A or
U+0131 as source literals can silently normalise them to ASCII, which makes the fixture
under-test without ever failing.
"""
from __future__ import annotations

# --- codepoint sets, enumerated rather than sampled -----------------------------------------
# The 23 codepoints Python's `\s` accepts that POSIX `[[:space:]]` under LC_ALL=C does not.
# Closed by enumeration over all of 0x110000 (Python side) and a byte-scan of 0x01-0xFF (shell).
UNICODE_WS = (
    [chr(c) for c in range(0x1C, 0x20)]
    + [chr(0x85), chr(0xA0), chr(0x1680)]
    + [chr(c) for c in range(0x2000, 0x200B)]
    + [chr(0x2028), chr(0x2029), chr(0x202F), chr(0x205F), chr(0x3000)]
)
assert len(UNICODE_WS) == 23, f"expected 23 codepoints, got {len(UNICODE_WS)}"

# NOT Unicode White_Space — must pass through BOTH implementations untouched.
NOT_WS = [chr(0x200B), chr(0xFEFF), chr(0x180E)]

# The image extensions the `_EMAIL` retina exemption accepts, case-insensitively.
RETINA_EXTS = ("png", "jpg", "jpeg", "gif", "pdf", "webp", "heic", "tif", "tiff")

SECRET = "AKIAIOSFODNN7EXAMPLE"
TOKEN20 = "T" * 24


def _rows():
    """(input, must_agree, note). must_agree=False marks the one permanent exemption."""
    r = []
    add = lambda i, agree=True, note="": r.append((i, agree, note))

    # --- 4.1  the sk-/pk_ boundary, and its ASYMMETRY ---------------------------------------
    for w in ("task-oriented", "risk-assessment", "disk-utilization", "desk-checking"):
        add(w, note="4.1 corruption class — must survive intact")
    add("Xsk-abcdefgh123", note="4.1 letter guard")
    add("9sk-abcdefgh123", note="4.1 digit guard")
    add("token sk-abcdefgh123", note="4.1 mid-string, space delimiter preserved")
    add("token=sk-abcdefgh123", note="4.1 mid-string, '=' delimiter preserved")
    add("(pk_abcdefgh123)", note="4.1 punctuation delimiter preserved byte-identically")
    add("sk-abcdefgh123 sk-abcdefgh123", note="4.1 both branches in one pass")
    add("sk-proj-abcdefgh12345678", note="4.1 start-of-string")
    add("pk_live_abcdefgh12345678", note="4.1 start-of-string")
    add("sk-abcdefgh", note="4.1 threshold: payload exactly 8 -> REDACTED")
    add("sk-abcdefg", note="4.1 threshold: payload 7 -> preserved. Rejects a {9,} mutant")
    # the asymmetry: these two must move in OPPOSITE directions
    add("foo_sk-abcdefgh123", note="4.1 underscore IS a boundary before sk- -> redacted")
    add("OPENAI_KEY_sk-proj-abcdefgh12345678", note="4.1 the leak shape underscore-as-boundary catches")
    add("orders_pk_customer_id_idx", note="4.1 underscore is NOT a boundary before pk_ -> PRESERVED")
    add("idx_pk_customer_id_lookup", note="4.1 second SQL identifier, preserved")
    add("cafésk-abcdefgh123", note="4.1 true adjacency — rejects a Unicode-aware Python guard")
    # sequential-vs-combined: rejects a single combined alternation in Python
    add("pk_abcdefgh-sk-ijklmnop", note="4.1 BOTH prefixes in one token — rejects a combined alternation")
    add("~a/pk_abcdefgh-sk-ijklmnop", note="4.1 same, through the full pipeline (tilde fires first)")
    add("sk-abcdefgh123_pk_abcdefgh123", note="4.1 sk- payload legitimately swallows the _pk_")

    # --- 4.2  the tilde home-PATH contract ---------------------------------------------------
    for w in ("~500ms", "~2x faster", "~40 percent", "~ten minutes", "~half the rows",
              "takes ~one second", "~L147", "~Copyable", "~Escapable", "~40/60 split",
              "~1/2 of the rows", "split ~50/50", "~1a2b", "cost ~$5", "~/Documents"):
        add(w, note="4.2 approximation/Swift/ratio — must survive")
    add("backup~alice/x", note="4.2 embedded ~ must not match (boundary)")
    add("~alice/secrets", note="4.2 positive")
    add("~root/.ssh/id_rsa", note="4.2 positive")
    add("(~bob/tmp)", note="4.2 punctuation prefix")
    add("x-~carol/y", note="4.2 '-' is a boundary, so --flag=~user/... still redacts")
    add("~_daemon/x", note="4.2 underscore-leading username — rejects an [A-Za-z] mutant")
    add("~a/~b/x", note="4.2 THE LOOP ASSERTION. Delete -e ':t' -e 'tt' and this fails")
    add("see /Users/nick/z and ~nick/z", note="4.2 both halves in one pass")
    add("~alice", note="4.2 ACCEPTED RESIDUAL — bare ~user, no path, deliberately preserved")
    add("~9lives/x", note="4.2 ACCEPTED RESIDUAL — digit-leading username, deliberately preserved")
    add("~Copyable-alice", note="4.2 was a Python leak (lookahead \\b); the strict rule removes it")
    add("~sk-abcdefgh123/", note="4.2 RULE ORDERING PIN — tilde runs before secret")

    # --- RC-A / RC-B / RC-C  the canonicalisation pre-pass -----------------------------------
    for ws in UNICODE_WS:
        add(f"api{ws}key: {SECRET}", note="RC-A slot 1 — api<WS>key")
        add(f"api key{ws}: {SECRET}", note="RC-A slot 2 — key<WS>:")
        add(f"api key:{ws}{SECRET}", note="RC-A slot 3 — :<WS>value")
        add(f"bearer{ws}{TOKEN20}", note="RC-A slot 4 — bearer<WS>token")
        add(f"/Users/alice{ws}secret", note="RC-B negated class, polarity inverts")
        add(f"/Users/nick{ws}api key: {SECRET}", note="RC-B compound — over-consumption ate the anchor")
    add("api\nkey: " + SECRET, note="RC-C sed is line-oriented")
    add("api key:\n  s3cr3t-value", note="RC-C the natural config layout")
    add("Authorization: Bearer\n  " + TOKEN20, note="RC-C soft-wrapped header")
    for ws in NOT_WS:
        add(f"a{ws}b", note="NEGATIVE CONTROL — not Unicode White_Space, must pass through")
        add(f"api{ws}key: {SECRET}", note="NEGATIVE CONTROL — ZWSP/BOM must NOT be folded")

    # --- RC-D / RC-E  Unicode case-folding (Python narrowed to ASCII) ------------------------
    add("api Key: " + SECRET, note="RC-D ASCII case — both redact")
    add(f"ap{chr(0x0131)}_key: SECRETVALUE", note="RC-D dotless i — Python must NOT fold it")
    add(f"api{chr(0x212A)}ey=SECRETVALUE", note="RC-D Kelvin sign — Python must NOT fold it")
    add(f"api key: SECRET{chr(0x017F)}MORE", note="RC-E value class — SHARED MISS, see COREDEV-2609")
    add("bearer " + "a" * 19 + chr(0x017F), note="RC-E value class, bearer side")
    add("bKarer " + TOKEN20, note="NEGATIVE CONTROL — b/e/a/r have no non-ASCII fold; both preserve")

    # --- RC-H  fold arity --------------------------------------------------------------------
    add("a\r\nb", note="RC-H every CRLF — tr is 1:1, so two spaces")
    add("a\n\n\tb", note="RC-H run of separators")

    # --- _EMAIL: the one permanent exemption, plus the leaks that are NOT exempt -------------
    add("AppIcon@2x.png", agree=False, note="EXEMPT — POSIX ERE has no lookahead")
    add("Icon@10x.PNG", agree=False, note="EXEMPT — unbounded [0-9]+ and case-insensitive ext")
    add("a/AppIcon@3x.webp", agree=False, note="EXEMPT — mid-path")
    add("user@2x.png.example.com", note="WAS A PYTHON LEAK (routable address) — now both redact")
    add("AppIcon@2x.png.bak", note="F2 — trailing dot no longer satisfies the guard")
    add("AppIcon@2X.png", note="NEGATIVE CONTROL — capital X is outside (?i:), both redact")
    add("user@2xmail.com", note="NEGATIVE CONTROL — domain is not <digits>x.<ext>")
    add("Icon@2x.pngsk-TOPSECRET1", note="NEGATIVE CONTROL — shared bug, not a divergence")

    # --- untouched rules ---------------------------------------------------------------------
    add("nick@example.com", note="email")
    add("/Users/nick/x.swift", note="/Users path")
    add("/home/nick/x", note="/home path")
    add("eyJhbGciOiJIUzI1NiJ9", note="jwt")
    add("bearer " + TOKEN20, note="bearer")
    add("api key: " + SECRET, note="api key")
    add("sk-ABCDEFGKHIJ", note="NEGATIVE CONTROL — no IGNORECASE on _SECRET")
    add("~Copyable2", note="NEGATIVE CONTROL")
    add("~copyable", note="NEGATIVE CONTROL")
    add("plain text with no secrets", note="control")
    add("", note="empty input")
    return r


VECTORS = _rows()

#: Inputs where the two implementations are REQUIRED to agree byte-for-byte.
MUST_AGREE = [(i, n) for (i, a, n) in VECTORS if a]
#: The single permanent exemption class — shell redacts, Python preserves.
EXEMPT = [(i, n) for (i, a, n) in VECTORS if not a]


def retina_generator():
    """Yield the `_EMAIL` exemption's reachable surface — a GENERATOR, not a list.

    The class is unbounded: 104 ASCII case spellings x unbounded digit prefix x arbitrary local
    part x any trailing codepoint outside `[A-Za-z0-9.-]`. This samples each axis so the fixture
    exercises the shape rather than a handful of memorised strings.
    """
    import itertools

    for ext in RETINA_EXTS:
        # every ASCII case spelling of this extension
        for bits in itertools.product(*((c.lower(), c.upper()) for c in ext)):
            yield f"Icon@2x.{''.join(bits)}"
    for digits in ("0", "1", "2", "3", "10", "007", "1234567890"):
        yield f"Icon@{digits}x.png"
    for local in ("a", "A1", "first.last", "a+tag", "a_b", "a-b", "9"):
        yield f"{local}@2x.png"
    for trail in ("", " ", ")", "]", '"', "é"):
        yield f"Icon@2x.png{trail}"


if __name__ == "__main__":  # pragma: no cover - manual inspection aid
    print(f"{len(VECTORS)} vectors: {len(MUST_AGREE)} must-agree, {len(EXEMPT)} exempt")
    print(f"retina generator yields {sum(1 for _ in retina_generator())} inputs")
