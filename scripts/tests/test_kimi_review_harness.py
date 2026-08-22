#!/usr/bin/env python3
"""`isolated-kimi-review.sh` — the mutation gates, driven end to end with a stub `kimi`.

Every scenario runs the WORKTREE's harness against a PRIVATE clone of this repository, with a stub
`kimi` on PATH whose behaviour is chosen by `KIMI_STUB_MODE`. The stub prints the session-id line and
a verdict; the effort cannot be asserted from a stub, so a run whose mutation gates all pass ends
`EXIT=… TREE=clean … EFFORT=UNKNOWN` and exit 4 — that pair IS "the gates passed". Every mutation the
harness documents (COREDEV-2607 shapes in the disposable checkout, a commit in the live tree, an
edited prompt) must exit 3 with its own message; a git-config write inside the disposable checkout
must stay there. PROMPT= on the summary line is the digest of the ARGUMENT the reviewer received (the
snapshot's bytes with trailing newlines stripped by command substitution), not of the prompt file; a
transcript operand that only PHYSICALLY resolves under /tmp — `..` traversal in an absolute path, or a
symlinked parent — is refused; and a live tracked file hidden with `update-index --assume-unchanged`
before it is edited still voids the round.

THE PROMPT OPERAND IS CONTAINED and the transcript never lands in the compared tree (codex, PR #67 pass
12): `../secret.txt`, an in-repo symlink to `/etc/hosts`, and a transcript path inside the live checkout
each exit 1 with their own message BEFORE the reviewer runs — the stub leaves an invocation marker on
every run, and these assert the marker is absent and the transcript was never created.

AND A REFUSED TRANSCRIPT OPERAND CREATES NOTHING (codex, PR #67 pass 13): the parent used to be `mkdir -p`'d
BEFORE the physical resolution and the refusals, so `<clone>/new/nested/kimi.txt` left `<clone>/new/nested/`
inside the live tree and `<scratch>/other/link/deep/kimi.txt` (the link into `<clone>/.git`) left
`<clone>/.git/deep/` — both invisible to `status`, which lists no empty directory. The physical path is now
computed without creating anything; the control — the `mkdir -p` restored ahead of the resolution — is RUN
on the same operands and does create them.

AND THE RECONSTRUCTED PATH IS NORMALISED (codex, PR #67 pass 14): the re-appended missing tail was kept
VERBATIM, so `<scratch>/missing/../repo/README.md` (with `<scratch>/repo` the live checkout and `missing`
absent) passed the repository-prefix refusal, `mkdir -p` created `missing`, and the transcript was written
INTO the live checkout — over a TRACKED file — before the post-run fingerprint voided the round. It is refused
now, before the reviewer, creating nothing; the control (the `normpath` line deleted) is RUN and does all of it.

AND SO IS A LEADING `//`, AND THE PHYSICAL PREFIX IS TESTED ON ITS OWN (codex sweep, PR #67 pass 14, two
more findings). `os.path.normpath` PRESERVES exactly two leading slashes, so an operand whose nearest
EXISTING ancestor is `/` reconstructed as `//tmp/x` / `//<repo>/tracked` — matching neither prefix refusal
while the kernel resolves both to exactly those places; the line collapses `^//+` now, and the control
(the `re.sub` removed, the `normpath` kept) is RUN and overwrites the tracked README.md. And the `|| exit 1`
after the reconstruction was INERT — an assignment takes the status of its LAST command substitution,
`basename` — so a `cd -P` that could not enter its target was ignored and the operand was silently
RE-ROOTED at `/`; the prefix is captured and tested on its own, and the control (the single-assignment
form restored) is RUN on an unenterable 0000 parent and writes the transcript where the operand never named.

THE EFFORT EVIDENCE IS BOUND TO THE ONE SESSION THE RUN CREATED (codex, PR #67 pass 11): the set
difference of `$HOME/.kimi-code/sessions/*/session_*` before and after the run — never a session id read
out of the transcript, which is reviewer-controlled text. Exactly one new session with a `max` wire log
asserts `max` (exit 0); an older session's id QUOTED in the transcript, with no session created, is not
evidence (`EFFORT=UNKNOWN`, exit 4) — the previous grep-based selection would have returned that older
session's `max`, and a control carrying that selection is RUN and does; two new sessions fail closed.
Every run here has `HOME` re-pointed at a scratch directory, so the sessions the stub creates, and the
sessions the harness lists, are never the developer's real `~/.kimi-code`.

Linux-safe: git, bash, python3 only. The transcript is written under ~/.claude — the harness refuses
/tmp, and CI's TMPDIR is /tmp.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HARNESS = os.path.join(REPO, "scripts", "review", "isolated-kimi-review.sh")
SOURCE_PROMPT = os.path.join(REPO, ".review-prompt-2617r123.md")
DEFAULT_PLAN = "docs/planning/COREDEV-2617_PLUGIN_STATE_BASE_DIR_PLAN.md"
# A DIFFERENT DIRECTORY, not just a different basename: both accepted operands used to live
# under `docs/planning/`, so an implementation that hard-coded that prefix and used only the
# basename passed every assertion — and would have failed on the real `docs/audits/` operand
# this branch is reviewed with (codex, PR #69 round 6).
# THE SAME BASENAME, a DIFFERENT DIRECTORY, and different bytes. Distinct basenames still let a
# basename-only implementation pass by resolving the leaf against any directory; only a shared
# basename forces the digest to depend on the FULL path (codex, PR #69 round 7).
# The alternate shares BOTH the basename and the immediate parent, differing only in a HIGHER
# ancestor. Sharing the basename alone still let an implementation using the last TWO path
# components pass; only this forces the digest to depend on the FULL path (codex, round 8).
ALT_PLAN = "archive/" + DEFAULT_PLAN
SESSION = "session_00000000-0000-4000-8000-000000000001"
#: A session that exists BEFORE the run (the test creates it), and the one/two the stub creates DURING it.
OLD_SESSION = "session_11111111-1111-4111-8111-111111111111"
NEW_SESSION = "session_22222222-2222-4222-8222-222222222222"
NEW_SESSION_2 = "session_33333333-3333-4333-8333-333333333333"

KIMI_STUB = f"""#!/usr/bin/env bash
# cwd = the harness's DISPOSABLE checkout; $KIMI_STUB_CLONE = the live fixture repository.
# EVERY invocation leaves a marker under the scratch, whatever the mode: an operand the harness must
# refuse is refused BEFORE the reviewer is launched, and "the stub did not run" is asserted on this file.
printf '%s\\n' "$$" >> "$KIMI_STUB_SCRATCH/kimi-invoked"
case "${{KIMI_STUB_MODE:-clean}}" in
  clean) ;;
  gitkill)       rm -rf .git; echo x > IMPLEMENTED.sh ;;
  commit-hide)   echo x >> README.md
                 git -c user.email=r@r -c user.name=r -c commit.gpgsign=false commit -qam hide ;;
  nested-ignore) mkdir impl; printf '*\\n' > impl/.gitignore; echo x > impl/x.sh ;;
  live-commit)   git -C "$KIMI_STUB_CLONE" -c commit.gpgsign=false commit -q --allow-empty -m mid ;;
  prompt-edit)   printf '\\nEDITED\\n' >> "$KIMI_STUB_CLONE/.review-prompt-x.md" ;;
  hookspath)     git config core.hooksPath /evil/hooks
                 printf 'HOOKSPATH=%s\\n' "$(git config --get core.hooksPath)" ;;
  record-arg)    printf '%s' "$2" > "$KIMI_STUB_SCRATCH/received.bin" ;;   # $1=-p, $2=the prompt text
  record-checkout) # what the REVIEWER actually sees: its cwd's HEAD and the plan bytes there
                 git rev-parse HEAD > "$KIMI_STUB_SCRATCH/seen-head" 2>/dev/null
                 shasum -a 256 "$KIMI_STUB_PLAN" 2>/dev/null | cut -d' ' -f1 \
                   > "$KIMI_STUB_SCRATCH/seen-plan" ;;
  fail-nonzero)  printf 'reviewer failed\\n' >&2; exit 7 ;;
  slow)          sleep 30 ;;
  assume-unchanged-live)
                 git -C "$KIMI_STUB_CLONE" update-index --assume-unchanged README.md
                 echo x >> "$KIMI_STUB_CLONE/README.md" ;;
  # The session-binding modes write under $HOME — the harness's HOME, re-pointed at the scratch by the test.
  new-max)       mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  new-high)      mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 printf '{{"type":"llm.request","thinkingEffort":"high"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  quote-old)     printf 'As in {OLD_SESSION} earlier\\n' ;;      # creates NOTHING; quotes a pre-existing session
  foreign-only)  # a stranger's session: correct shape, but recorded under a DIFFERENT cwd
                 mkdir -p "$HOME/.kimi-code/sessions/wd_foreign/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"/nowhere/else"}}\\n' > "$HOME/.kimi-code/sessions/wd_foreign/{NEW_SESSION}/state.json"
                 printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_foreign/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  no-state)      # a new session with NO state.json at all: provenance is unknowable, not assumed
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  workdir-max)   # THE EIGHTH AXIS: the REAL majority schema, which records `workDir`, not `cwd`
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"workDir":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  alias-conflict) # two recorded cwds that DISAGREE: ambiguous provenance, not resolvable by order
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s","workDir":"/nowhere/else"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  mixed-nofield) # max request + a request with NO tier: the round cannot account for the second
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 {{ printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n'
                    printf '{{"type":"llm.request"}}\\n'
                 }} > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  mixed-nonstr)  # max request + a request whose tier is a NUMBER, not a string
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 {{ printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n'
                    printf '{{"type":"llm.request","thinkingEffort":123}}\\n'
                 }} > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  mixed-nultier) # max request + a tier of "m\\u0000ax": NOT "max" in Python, but bash DELETES NUL
                 # in command substitution, so it arrives at the gate as exactly `max,`.
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 {{ printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n'
                    printf '{{"type":"llm.request","thinkingEffort":"m\\u0000ax"}}\\n'
                 }} > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  dup-type)      # a high request HIDDEN by a duplicate `type` name: last-wins makes it stop
                 # looking like a request at all.
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 {{ printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n'
                    printf '{{"type":"llm.request","thinkingEffort":"high","type":"metadata"}}\\n'
                 }} > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  dup-tier)      # one request naming TWO tiers: last-wins rewrites high to max
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 {{ printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n'
                    printf '{{"type":"llm.request","thinkingEffort":"high","thinkingEffort":"max"}}\\n'
                 }} > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  dup-cwd)       # duplicate `cwd` in state.json: last-wins collapses it to ONE key BEFORE the
                 # conflicting-alias guard can see a conflict, so that guard could never fire.
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"/nowhere/else","cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  slow-loud)     # a TIMED-OUT round that nevertheless emitted bytes AND created a session, so it
                 # reaches the WIRE block (pty-capture writes the partial transcript on timeout).
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl"
                 printf 'partial output before the hang\\n'
                 sleep 30 ;;
  mixed-badutf8) # max request + a request whose TYPE carries an invalid UTF-8 byte. Replacement
                 # decoding would make this parse as a DIFFERENT record type and skip it silently.
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 {{ printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n'
                    printf '{{"type":"llm.requ\\377st","thinkingEffort":"high"}}\\n'
                 }} > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  mixed-malform) # max request + an UNPARSEABLE line: the natural way to hide a low-tier request
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 {{ printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n'
                    printf '{{not json\\n'
                 }} > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  bind-only)     # THE MODEL NEVER RAN: profile.bind records the CONFIGURED tier, nothing was asked
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 {{ printf '{{"type":"metadata"}}\\n'
                    printf '{{"type":"profile.bind","modelAlias":"kimi-code/k3","thinkingEffort":"max"}}\\n'
                    printf '{{"type":"permission.set_mode","mode":"auto"}}\\n'
                 }} > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  malformed-alias) # OUR cwd in one alias, a NON-STRING in another: must not be waved through
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s","workDir":12345}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl" ;;
  empty-plus-one) # THE SEVENTH AXIS: no transcript bytes AND exactly one new session
                 mkdir -p "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main"
                 printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/state.json"
                 printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/{NEW_SESSION}/agents/main/wire.jsonl"
                 exit 0 ;;   # ...and print NOTHING, so the capture is empty
  two-new)       for s in {NEW_SESSION} {NEW_SESSION_2}; do
                   mkdir -p "$HOME/.kimi-code/sessions/wd_new/$s/agents/main"
                   printf '{{"cwd":"%s"}}\\n' "$PWD" > "$HOME/.kimi-code/sessions/wd_new/$s/state.json"
                   printf '{{"type":"llm.request","thinkingEffort":"max"}}\\n' > "$HOME/.kimi-code/sessions/wd_new/$s/agents/main/wire.jsonl"
                 done ;;
  # ── modes that attack the POST-RUN probes, which had no cell in either direction ─────────────
  basis-destroy) # Delete the LIVE repository's loose object for the plan blob. The post-run
                 # `git cat-file blob "$SHA:$PLAN_REL"` then answers nothing and AFTER_BASIS becomes
                 # the literal string `MISSING`. This is the reachable shape of BASIS != AFTER_BASIS:
                 # the two are NOT both read from the same live object, because the second read has a
                 # `|| echo MISSING` fallback that a reviewer can provoke.
                 _obj="$(git -C "$KIMI_STUB_CLONE" rev-parse "HEAD:$KIMI_STUB_PLAN" 2>/dev/null)"
                 [ -n "$_obj" ] && rm -f "$KIMI_STUB_CLONE/.git/objects/${{_obj:0:2}}/${{_obj:2}}"
                 : ;;
  selfdestruct-tree) # The reviewer DELETES its own checkout. `disposable_fingerprint` then fails
                 # at its `os.path.isdir` precondition and returns 1, which is the only way the
                 # probe reports failure: `os.walk` swallows permission errors by default, so a
                 # merely UNREADABLE tree yields an empty listing and exit 0 (measured — it is
                 # caught by the content comparison instead, three lines further down).
                 cd .. && rm -rf tree ;;
  livegitkill)   rm -rf "$KIMI_STUB_CLONE/.git" ;;   # the LIVE checkout can no longer be fingerprinted
esac
printf '{SESSION}\\nVERDICT: APPROVE\\n'
"""


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "needs git and bash")
class KimiHarnessMutationGates(unittest.TestCase):
    def setUp(self):
        base = os.path.expanduser("~/.claude")
        os.makedirs(base, mode=0o700, exist_ok=True)
        self.scratch = tempfile.mkdtemp(prefix="kimi-harness.", dir=base)
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.clone = os.path.join(self.scratch, "repo")
        subprocess.run(["git", "clone", "-q", REPO, self.clone], check=True, capture_output=True)
        git = ["git", "-C", self.clone]
        subprocess.run(git + ["config", "user.email", "fixture@test"], check=True)
        subprocess.run(git + ["config", "user.name", "fixture"], check=True)
        # A shallow SOURCE (CI's default depth-1 checkout) makes the harness's `disposable_checkout`
        # fetch fail — "shallow roots are not allowed to be updated" (measured, git 2.54) — even for a
        # commit made on top of it. An orphan root carries the same tree with a complete history.
        subprocess.run(git + ["checkout", "-q", "--orphan", "fixture"], check=True)
        prompt = os.path.join(self.clone, ".review-prompt-x.md")
        # The prompt must NAME the document the BASIS certifies — the harness refuses otherwise, so
        # that a round cannot review one file while certifying another (codex, PR #69 round 2). Every
        # fixture prompt therefore states the plan path it is reviewing, exactly as a real one must.
        _plan_line = "Plan under review: " + DEFAULT_PLAN + "\n"
        if os.path.isfile(SOURCE_PROMPT) and os.path.getsize(SOURCE_PROMPT) >= 1000:
            with open(SOURCE_PROMPT, "r", encoding="utf-8") as src, \
                 open(prompt, "w", encoding="utf-8") as fh:
                fh.write(_plan_line)
                fh.write(src.read())
        else:
            with open(prompt, "w", encoding="utf-8") as fh:
                fh.write(_plan_line)
                fh.write("Review the plan for correctness, security and completeness.\n" * 40)
        # An ALTERNATE committed plan with DIFFERENT bytes, and a prompt that declares it. Without
        # one, the only positive digest oracle used DEFAULT_PLAN and the only alternate operand
        # (README.md) was refused before the digest — so an implementation that ALWAYS hashes the
        # default passed every assertion (codex, PR #69 round 5).
        # A THIRD plan at an UNPREDICTABLE path. Two fixed operands can always be special-cased —
        # codex showed a mutant branching on the first path component that satisfied both — and so
        # can three, and four. What cannot be special-cased is a path the implementation could not
        # know at authoring time, so this one is derived from the per-run scratch name (codex,
        # PR #69 round 9). It is the same assertion, made unguessable.
        # ...and its STRICT SUFFIX is another tracked plan with different bytes. A random path alone
        # was still satisfied by an implementation that strips a leading component: it resolved to
        # something that happened to be right for all three operands (codex, PR #69 round 10). With
        # the suffix being DEFAULT_PLAN, any generic "drop the first component" resolves the WRONG
        # tracked file and the digest disagrees — and the prefix stays unguessable, so a hard-coded
        # strip cannot target it either.
        self.rand_plan = "r%s/%s" % (os.path.basename(self.scratch)[-8:], DEFAULT_PLAN)
        # A FOURTH operand with a DIFFERENT BASENAME. The other three deliberately share one, to
        # kill basename-only resolution — but that let a resolver key on THAT basename, use the full
        # path for it and strip otherwise, passing all three (codex, PR #69 round 11, raised as a
        # note rather than a finding). Varying the basename too closes it.
        self.odd_plan = "docs/audits/COREDEV-2654_ODD_%s.md" % os.path.basename(self.scratch)[-6:]
        odd_abs = os.path.join(self.clone, self.odd_plan)
        os.makedirs(os.path.dirname(odd_abs), exist_ok=True)
        with open(odd_abs, "w", encoding="utf-8") as fh:
            fh.write("ODD-BASENAME PLAN — distinct bytes again.\n")
        with open(os.path.join(self.clone, ".review-prompt-odd.md"), "w", encoding="utf-8") as fh:
            fh.write("Plan under review: " + self.odd_plan + "\n")
            fh.write("Review the odd-basename plan.\n" * 40)
        rand_abs = os.path.join(self.clone, self.rand_plan)
        os.makedirs(os.path.dirname(rand_abs), exist_ok=True)
        with open(rand_abs, "w", encoding="utf-8") as fh:
            fh.write("UNPREDICTABLE PLAN %s — distinct bytes.\n" % self.rand_plan)
        with open(os.path.join(self.clone, ".review-prompt-rand.md"), "w", encoding="utf-8") as fh:
            fh.write("Plan under review: " + self.rand_plan + "\n")
            fh.write("Review the unpredictable plan.\n" * 40)
        alt_abs = os.path.join(self.clone, ALT_PLAN)
        os.makedirs(os.path.dirname(alt_abs), exist_ok=True)
        with open(alt_abs, "w", encoding="utf-8") as fh:
            fh.write("ALTERNATE PLAN — distinct bytes so the digest cannot coincide.\n")
        with open(os.path.join(self.clone, ".review-prompt-alt.md"), "w", encoding="utf-8") as fh:
            fh.write("Plan under review: " + ALT_PLAN + "\n")
            fh.write("Review the alternate plan.\n" * 40)
        with open(os.path.join(self.clone, ".gitignore"), "a", encoding="utf-8") as fh:
            fh.write(".review-prompt-x.md\n.review-prompt-alt.md\n.review-prompt-rand.md\n.review-prompt-odd.md\n.review-prompt-nul.md\n.review-prompt-nonul.md\n")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], check=True)
        # A SECOND COMMIT that CHANGES the default plan's bytes. Without it every cell passed the
        # literal "HEAD" as the commit operand and computed every expectation from `HEAD:` too — so
        # an implementation that IGNORES $SHA and hard-codes HEAD satisfied all four path operands
        # (codex, PR #69 round 13 at effort=max; two xhigh rounds had approved this). Varying the
        # COMMIT axis is what that sampling missed.
        self.first_sha = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True,
                                        text=True, check=True).stdout.strip()
        with open(os.path.join(self.clone, DEFAULT_PLAN), "a", encoding="utf-8") as fh:
            fh.write("A LATER REVISION — these bytes exist only at HEAD, not at first_sha.\n")
        subprocess.run(git + ["add", "-A"], check=True, capture_output=True)
        subprocess.run(git + ["-c", "commit.gpgsign=false", "commit", "-qm", "second"],
                       check=True, capture_output=True)
        status = subprocess.run(git + ["status", "--porcelain"], capture_output=True, text=True, check=True)
        self.assertEqual("", status.stdout, "the fixture clone must start clean (the prompt is ignored)")
        bindir = os.path.join(self.scratch, "bin")
        os.mkdir(bindir)
        stub = os.path.join(bindir, "kimi")
        with open(stub, "w", encoding="utf-8") as fh:
            fh.write(KIMI_STUB)
        os.chmod(stub, 0o755)
        # HOME IS THE SCRATCH for every run: the harness lists `$HOME/.kimi-code/sessions/*/session_*`
        # before and after the reviewer, and the stub's session-binding modes create sessions there.
        # A real `~/.kimi-code` (dozens of sessions on a developer machine) must never be listed,
        # written, or — through a concurrent real session — mistaken for this run's evidence. Git
        # identity comes from the clone's own config, so no HOME-level gitconfig is needed.
        self.home = os.path.join(self.scratch, "home")
        os.mkdir(self.home)
        self.env = dict(os.environ)
        self.env["HOME"] = self.home
        self.env["PATH"] = bindir + os.pathsep + self.env.get("PATH", "")
        self.env["KIMI_STUB_CLONE"] = self.clone
        self.env["KIMI_STUB_SCRATCH"] = self.scratch
        self.prompt = prompt

    def _run(self, mode, out=None, harness=HARNESS, prompt=".review-prompt-x.md",
             plan=None, env=None, commit="HEAD", timeout=60):
        """`plan` names the 5th operand (the BASIS target); `env` replaces the child environment.

        Both exist for the round-2 guards: the operand must be the document the PROMPT names, and a
        poisoned git environment must not be able to redirect which repository the BASIS is read
        from. Callers that pass neither get the harness's own default, as before.
        """
        out = out or os.path.join(self.scratch, f"out-{mode}.txt")
        child_env = dict(env or self.env, KIMI_STUB_MODE=mode,
                         KIMI_STUB_PLAN=(plan or DEFAULT_PLAN))
        argv = ["bash", harness, prompt, out, commit, str(timeout)]
        if plan is not None:
            argv.append(plan)
        p = subprocess.run(argv, cwd=self.clone, env=child_env,
                           capture_output=True, text=True, check=False, input="")
        return p, out

    def _stub_ran(self):
        """True when the stub `kimi` was invoked at least once during this test (its marker file exists)."""
        return os.path.exists(os.path.join(self.scratch, "kimi-invoked"))

    def _wire(self, wd, session):
        """The wire-log path of `session` under `wd` in the SCRATCH home."""
        return os.path.join(self.home, ".kimi-code", "sessions", wd, session, "agents", "main", "wire.jsonl")

    def _seed_session(self, wd, session, effort="max"):
        path = self._wire(wd, session)
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"type":"llm.request","thinkingEffort":"%s"}\n' % effort)
        return path

    def _assert_void(self, mode, message):
        p, _ = self._run(mode)
        self.assertEqual(3, p.returncode, f"{mode}: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn(message, p.stderr, f"{mode}: {p.stderr!r}")
        self.assertNotIn("TREE=clean", p.stdout, f"{mode}: a void round printed the clean summary")
        return p

    def test_clean_run_passes_every_gate_and_stops_only_at_the_effort_assertion(self):
        self.assertFalse(self._stub_ran(), "the invocation marker pre-exists — the refusal tests' oracle is void")
        p, out = self._run("clean")
        self.assertTrue(self._stub_ran(), "the stub ran but left no marker — the refusal tests could not tell")
        self.assertEqual(4, p.returncode, f"clean: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r"^EXIT=0 BYTES=\d+ TREE=clean BASIS=[0-9a-f]{12} PROMPT=[0-9a-f]{12} EFFORT=UNKNOWN\(self-reported\) WIRE=$")
        self.assertIn("EFFORT NOT ASSERTED", p.stderr)
        with open(out, encoding="utf-8") as fh:
            transcript = fh.read()
        self.assertIn(SESSION, transcript)
        self.assertIn("VERDICT: APPROVE", transcript)

    def test_deleting_dot_git_and_creating_a_file_in_the_disposable_checkout_voids(self):
        p = self._assert_void("gitkill", "left edits inside the disposable checkout")
        self.assertIn('"IMPLEMENTED.sh"', p.stderr, "the diff must name the created file")

    def test_committing_an_edit_inside_the_disposable_checkout_voids(self):
        p = self._assert_void("commit-hide", "left edits inside the disposable checkout")
        self.assertIn('"README.md"', p.stderr, "the diff must name the edited file")

    def test_a_nested_self_ignoring_gitignore_voids(self):
        p = self._assert_void("nested-ignore", "left edits inside the disposable checkout")
        self.assertIn('"impl/x.sh"', p.stderr, "the diff must name the file the nested .gitignore hid")

    def test_a_commit_in_the_live_repository_voids(self):
        self._assert_void("live-commit", "real worktree was mutated")

    def test_editing_the_prompt_file_during_the_review_voids(self):
        self._assert_void("prompt-edit", "prompt file changed")

    def test_a_hooksPath_write_stays_inside_the_private_disposable_checkout(self):
        p, out = self._run("hookspath")
        self.assertEqual(4, p.returncode, f"hookspath: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn("TREE=clean", p.stdout)
        with open(out, encoding="utf-8") as fh:
            self.assertIn("HOOKSPATH=/evil/hooks", fh.read(), "the stub's write never happened")
        live = subprocess.run(["git", "-C", self.clone, "config", "--get", "core.hooksPath"],
                              capture_output=True, text=True, check=False)
        self.assertEqual("", live.stdout.strip(), "the reviewer's git-config write reached the LIVE repository")
        self.assertNotEqual(0, live.returncode)

    def test_prompt_digest_is_of_the_argument_the_reviewer_received_not_the_file(self):
        """The stub records `$2` (the `-p` argument) byte-for-byte; PROMPT= must be ITS sha256 — and,
        because the file ends in newlines that command substitution strips, NOT the file's digest.
        The prompt is git-ignored in the fixture, so appending to it does not dirty the tree."""
        with open(self.prompt, "ab") as fh:
            fh.write(b"\n\n")
        with open(self.prompt, "rb") as fh:
            file_bytes = fh.read()
        self.assertTrue(file_bytes.endswith(b"\n"))
        p, _ = self._run("record-arg")
        self.assertEqual(4, p.returncode, f"record-arg: rc {p.returncode}\n{p.stdout}{p.stderr}")
        m = re.search(r"\bPROMPT=([0-9a-f]{12})\b", p.stdout)
        self.assertIsNotNone(m, p.stdout)
        with open(os.path.join(self.scratch, "received.bin"), "rb") as fh:
            received = fh.read()
        self.assertEqual(file_bytes.rstrip(b"\n"), received,
                         "the reviewer did not receive the snapshot's bytes (minus trailing newlines)")
        self.assertEqual(hashlib.sha256(received).hexdigest()[:12], m.group(1),
                         "PROMPT= is not the digest of the argument the reviewer received")
        self.assertNotEqual(hashlib.sha256(file_bytes).hexdigest()[:12], m.group(1),
                            "PROMPT= equals the FILE's digest — but the reviewer never received the file's "
                            "trailing newlines, so that digest describes bytes it did not review")

    def _assert_tmp_refused(self, out, leaf):
        for physical in ("/tmp", "/private/tmp"):
            self.assertFalse(os.path.lexists(os.path.join(physical, leaf)), f"stale {leaf} under {physical}")
        p, _ = self._run("clean", out=out)
        self.assertEqual(1, p.returncode, f"rc {p.returncode} for {out}\n{p.stdout}{p.stderr}")
        self.assertIn("refusing to write the transcript under /tmp", p.stderr, p.stderr)
        self.assertNotIn("TREE=clean", p.stdout)
        for physical in ("/tmp", "/private/tmp"):
            self.assertFalse(os.path.lexists(os.path.join(physical, leaf)),
                             f"the refused transcript was written anyway: {physical}/{leaf}")

    def test_an_absolute_transcript_path_traversing_into_tmp_is_refused(self):
        """An ABSOLUTE operand whose `..` segments physically resolve under /tmp (`/…/scratch/../../tmp/x`)
        matched neither `/tmp/*` nor `/private/tmp/*` before the parent was resolved with `cd -P`."""
        leaf = f"kimi-x-{os.path.basename(self.scratch)}.txt"
        physical_scratch = os.path.realpath(self.scratch)
        out = os.path.join(physical_scratch, os.path.relpath("/tmp", physical_scratch), leaf)
        self.assertTrue(out.startswith("/") and "/../" in out and not out.startswith("/tmp/"), out)
        self.assertEqual(os.path.realpath("/tmp"), os.path.dirname(os.path.realpath(out)))
        self._assert_tmp_refused(out, leaf)

    def test_a_transcript_path_through_a_symlinked_parent_into_tmp_is_refused(self):
        """`<scratch>/link -> /tmp`; `<scratch>/link/x` is lexically under ~/.claude and physically under /tmp."""
        leaf = f"kimi-y-{os.path.basename(self.scratch)}.txt"
        link = os.path.join(self.scratch, "link")
        os.symlink("/tmp", link)
        out = os.path.join(link, leaf)
        self.assertFalse(out.startswith("/tmp/") or out.startswith("/private/tmp/"), out)
        self.assertEqual(os.path.realpath("/tmp"), os.path.dirname(os.path.realpath(out)))
        self._assert_tmp_refused(out, leaf)

    def test_a_live_tracked_file_hidden_by_assume_unchanged_then_edited_voids(self):
        """The reviewer flags a LIVE tracked file `--assume-unchanged` (status and `diff HEAD` go blind)
        and then edits it: the content-hashing live probe still sees the edit and voids the round."""
        self._assert_void("assume-unchanged-live", "real worktree was mutated")
        # The premise: the index-based views were indeed blind to the edit that voided the round.
        st = subprocess.run(["git", "-C", self.clone, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertNotIn("README.md", st.stdout, "status still saw the edit — the fixture is not the finding")
        with open(os.path.join(self.clone, "README.md"), "rb") as fh:
            self.assertTrue(fh.read().endswith(b"x\n"), "the stub's edit did not land in the live README.md")

    # ── the operands are contained BEFORE the reviewer runs (codex, PR #67 pass 12) ───────────

    def _assert_refused_before_launch(self, p, out, message):
        self.assertEqual(1, p.returncode, f"rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn(message, p.stderr, p.stderr)
        self.assertNotIn("TREE=clean", p.stdout, "a refused operand printed the clean summary")
        self.assertFalse(self._stub_ran(), "the reviewer was launched on a refused operand")
        self.assertFalse(os.path.lexists(out), f"the refused run created the transcript: {out}")

    def test_a_prompt_operand_that_traverses_out_of_the_repo_is_refused(self):
        """`../secret.txt` — a readable regular file one level ABOVE the clone (`<scratch>/secret.txt`):
        a bare `[ -r ]` followed it and sent its bytes to the reviewer as the prompt. The containment
        helper resolves it outside the repository root and refuses; nothing downstream runs."""
        secret = os.path.join(self.scratch, "secret.txt")
        with open(secret, "w", encoding="utf-8") as fh:
            fh.write("this file lives outside the fixture repository\n" * 5)
        self.assertEqual(os.path.dirname(self.clone), os.path.dirname(secret))
        self.assertTrue(os.path.isfile(os.path.join(self.clone, "..", "secret.txt")), "the fixture is not the finding")
        p, out = self._run("clean", prompt="../secret.txt")
        self._assert_refused_before_launch(p, out, "outside the repository")

    def test_a_prompt_operand_that_is_a_symlink_is_refused(self):
        """`.link-prompt.md -> /etc/hosts` INSIDE the clone: lexically in-repo, readable, non-empty —
        and a symbolic link, which the containment helper refuses before resolving anything else."""
        link = os.path.join(self.clone, ".link-prompt.md")
        os.symlink("/etc/hosts", link)
        self.assertTrue(os.path.islink(link) and os.path.isfile(link), "the fixture is not the finding: /etc/hosts unreadable")
        p, out = self._run("clean", prompt=".link-prompt.md")
        self._assert_refused_before_launch(p, out, "symbolic link")

    def test_a_transcript_inside_the_live_checkout_is_refused(self):
        """A transcript operand physically INSIDE the live checkout (`<clone>/docs/planning/.verdicts/kimi.txt`)
        would be written into the very tree the round is fingerprinted against — voiding a clean round as a
        live mutation the harness itself caused, and overwriting a tracked file if one were named."""
        out = os.path.join(self.clone, "docs", "planning", ".verdicts", "kimi.txt")
        self.assertFalse(os.path.lexists(out))
        p, _ = self._run("clean", out=out)
        self._assert_refused_before_launch(p, out, "inside the live checkout")

    # ── a refused transcript operand creates NOTHING (codex, PR #67 pass 13) ──────────────────

    # The first line of the create-nothing resolution; the control puts the PREVIOUS `mkdir -p` of the
    # operand's parent back in front of it, exactly where it used to run.
    RESOLUTION_HEAD = '_out_dir="$(dirname -- "$OUT")"; _out_missing=""\n'
    MKDIR_FIRST = 'mkdir -p "$(dirname -- "$OUT")" || exit 1\n'

    def _mkdir_first_control(self):
        with open(HARNESS, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.RESOLUTION_HEAD), "the resolution's head line is not unique")
        # The shipped order: the parent is created AFTER the refusals, and only there.
        self.assertEqual(1, text.count(self.MKDIR_FIRST), "the shipped harness should mkdir the parent exactly once")
        self.assertLess(text.index(self.RESOLUTION_HEAD), text.index(self.MKDIR_FIRST),
                        "the shipped harness creates the parent BEFORE resolving it — the control is the shipped build")
        return self._laid_out_harness(text.replace(self.RESOLUTION_HEAD, self.MKDIR_FIRST + self.RESOLUTION_HEAD, 1))

    def _refused_creates(self, out, probe, harness=HARNESS):
        """Run with transcript operand `out`; assert it is refused as inside the live checkout, before the
        reviewer, with no transcript. Returns whether `probe` (the first component the operand would have
        created) exists afterwards — the ONLY thing that differs between the shipped build and the control."""
        self.assertFalse(os.path.lexists(probe), f"the fixture pre-creates {probe}")
        p, _ = self._run("clean", out=out, harness=harness)
        self._assert_refused_before_launch(p, out, "inside the live checkout")
        # `status` lists no EMPTY directory, so a created parent is invisible to it in both builds — the
        # premise of the finding, asserted rather than assumed: the oracle must be the directory itself.
        st = subprocess.run(["git", "-C", self.clone, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, f"status sees the refused operand's parent: {st.stdout!r}")
        return os.path.lexists(probe)

    def test_a_refused_transcript_operand_creates_no_directories(self):
        """`<clone>/new/nested/kimi.txt`: neither `new/` nor `new/nested/` exists after the refusal — the
        physical path was computed by resolving the nearest EXISTING ancestor and re-appending the missing
        tail, not by creating it. The control (`mkdir -p` restored ahead of the resolution) refuses with the
        same message and the same status, and leaves `<clone>/new/nested/` behind (measured)."""
        out = os.path.join(self.clone, "new", "nested", "kimi.txt")
        probe = os.path.join(self.clone, "new")
        self.assertFalse(self._refused_creates(out, probe),
                         "the refusal left the operand's missing parents inside the live checkout")
        self.assertFalse(os.path.lexists(os.path.join(self.clone, "new", "nested")))
        control = self._mkdir_first_control()
        self.assertTrue(self._refused_creates(out, probe, harness=control),
                        "the CONTROL (parent created first) did not leave `new/` behind — the fixture is not the finding")
        self.assertTrue(os.path.isdir(os.path.join(self.clone, "new", "nested")))

    def test_a_symlinked_parent_into_dot_git_creates_nothing_there(self):
        """`<scratch>/other/link -> <clone>/.git`; the operand `<scratch>/other/link/deep/kimi.txt` is lexically
        outside the clone and physically inside its `.git`: refused, and `<clone>/.git/deep` does not exist —
        an `mkdir -p` of the operand's parent would have created it THROUGH the link, in the repository
        database, before the refusal (the control does — measured)."""
        other = os.path.join(self.scratch, "other")
        os.makedirs(other)
        link = os.path.join(other, "link")
        os.symlink(os.path.join(self.clone, ".git"), link)
        self.assertTrue(os.path.islink(link) and os.path.isdir(link), "the fixture is not the finding")
        out = os.path.join(link, "deep", "kimi.txt")
        self.assertFalse(out.startswith(self.clone + os.sep), out)               # lexically outside …
        self.assertEqual(os.path.join(os.path.realpath(self.clone), ".git", "deep"),
                         os.path.dirname(os.path.realpath(out)))                  # … physically in .git
        probe = os.path.join(self.clone, ".git", "deep")
        self.assertFalse(self._refused_creates(out, probe),
                         "the refusal created a directory inside the live checkout's .git through the link")
        control = self._mkdir_first_control()
        self.assertTrue(self._refused_creates(out, probe, harness=control),
                        "the CONTROL (parent created first) did not create `.git/deep` — the fixture is not the finding")

    # ── the reconstructed physical path is NORMALISED before the refusals (codex, PR #67 pass 14) ──

    # The normalisation line, as shipped; the control DELETES it (the pre-fix resolution kept the missing
    # tail verbatim, `..` segments included). The line also collapses a leading `//` — `os.path.normpath`
    # PRESERVES exactly two leading slashes, and that half has its own control below, which removes the
    # `re.sub` and keeps the `normpath`.
    NORMPATH_LINE = ('''OUT="$(python3 -c 'import os, re, sys; '''
                     '''print(re.sub(r"^//+", "/", os.path.normpath(sys.argv[1])))' "$OUT")" || exit 1\n''')

    def _no_normpath_control(self):
        with open(HARNESS, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.NORMPATH_LINE), "the normalisation line is not unique — the control is not the control")
        # The shipped order: the reconstruction, THEN the normalisation, THEN the repository-prefix refusal.
        self.assertLess(text.index(self.RESOLUTION_HEAD), text.index(self.NORMPATH_LINE))
        self.assertLess(text.index(self.NORMPATH_LINE), text.index('    "$REPO_P"/*)\n'))
        return self._laid_out_harness(text.replace(self.NORMPATH_LINE, "", 1))

    def test_a_transcript_operand_traversing_through_a_missing_directory_into_the_live_checkout_is_refused(self):
        """codex, PR #67 pass 14 — `<scratch>/missing/../repo/README.md`, where `<scratch>/repo` IS the live
        checkout and `<scratch>/missing` does not exist: the nearest-existing-ancestor reconstruction stopped
        at `<scratch>` and re-appended `missing/../repo/README.md` VERBATIM, so the result did not match
        `"$REPO_P"/*`, `mkdir -p` then created `missing`, and the kernel resolved the write INTO the live
        checkout — a TRACKED file was overwritten by the transcript before the post-run fingerprint voided the
        round. The reconstructed path is now `os.path.normpath`-ed: refused as inside the live checkout, before
        the reviewer, with `missing` never created and README.md untouched. Mutant: the normalisation line
        deleted — the operand is ACCEPTED, `<scratch>/missing` is created, the reviewer runs, README.md is
        overwritten with the transcript, and only then is the round VOIDed (rc 3) — measured."""
        readme = os.path.join(self.clone, "README.md")
        with open(readme, "rb") as fh:
            original = fh.read()
        self.assertTrue(original, "the fixture's README.md is empty")
        missing = os.path.join(self.scratch, "missing")
        out = os.path.join(missing, "..", "repo", "README.md")
        # The premise: lexically it does not start with the clone; physically (once `missing` existed) it
        # would be the tracked file itself; and `missing` does not exist yet.
        self.assertFalse(out.startswith(self.clone + os.sep), out)
        self.assertEqual(os.path.realpath(readme), os.path.realpath(out))
        self.assertFalse(os.path.lexists(missing), "the fixture pre-creates `missing`")
        p, _ = self._run("clean", out=out)
        self._assert_refused_before_launch(p, out, "inside the live checkout")
        self.assertFalse(os.path.lexists(missing), "the refusal created the missing traversal component")
        with open(readme, "rb") as fh:
            self.assertEqual(original, fh.read(), "the refused run overwrote the tracked file")
        st = subprocess.run(["git", "-C", self.clone, "status", "--porcelain"], capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, f"the refused run dirtied the live checkout: {st.stdout!r}")
        # The control: the normalisation removed. The SAME operand is accepted — `missing` is created, the
        # reviewer runs, the transcript lands ON README.md, and the round is voided only afterwards.
        control = self._no_normpath_control()
        p, _ = self._run("clean", out=out, harness=control)
        self.assertEqual(3, p.returncode,
                         f"the CONTROL did not accept the operand and void the round after the fact — the fixture "
                         f"is not the finding: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn("real worktree was mutated", p.stderr, p.stderr)
        self.assertTrue(self._stub_ran(), "the CONTROL refused before launch — the fixture is not the finding")
        self.assertTrue(os.path.isdir(missing), "the CONTROL did not create `missing` — the fixture is not the finding")
        with open(readme, "rb") as fh:
            overwritten = fh.read()
        self.assertNotEqual(original, overwritten, "the CONTROL did not overwrite README.md — the fixture is not the finding")
        self.assertIn(SESSION.encode(), overwritten, "README.md was not overwritten WITH the transcript")
        st = subprocess.run(["git", "-C", self.clone, "status", "--porcelain"], capture_output=True, text=True, check=True)
        self.assertIn(" M README.md", st.stdout, f"the CONTROL's overwrite is not a live tracked change: {st.stdout!r}")

    # ── a leading `//` survives normalisation, and the physical prefix is TESTED (pass 14 sweep) ──

    #: The normalisation line WITHOUT its `//` collapse — the shape that shipped between the pass-14
    #: `normpath` fix and this sweep. `os.path.normpath` PRESERVES exactly two leading slashes (POSIX
    #: leaves that spelling implementation-defined), so when the nearest EXISTING ancestor is `/` the
    #: reconstruction produced `//tmp/x` / `//<repo>/tracked` and neither prefix refusal matched.
    NORMPATH_NO_COLLAPSE = ('''OUT="$(python3 -c 'import os, sys; '''
                            '''print(os.path.normpath(sys.argv[1]))' "$OUT")" || exit 1\n''')

    def _no_collapse_control(self):
        with open(HARNESS, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.NORMPATH_LINE),
                         "the normalisation line is not unique — the control is not the control")
        self.assertIn('re.sub(r"^//+", "/"', self.NORMPATH_LINE)
        return self._laid_out_harness(text.replace(self.NORMPATH_LINE, self.NORMPATH_NO_COLLAPSE, 1))

    def test_an_operand_whose_nearest_existing_ancestor_is_the_root_collapses_its_leading_slashes(self):
        """codex sweep, PR #67 pass 14, finding K1 — when the operand's nearest EXISTING ancestor is `/`,
        the reconstruction is `pwd -P` (`/`) + `/` + the missing tail, i.e. `//missing/../tmp/x`, and
        `os.path.normpath` PRESERVES the two leading slashes: the result matched neither the `/tmp/*` nor
        the `"$REPO_P"/*` refusal while the kernel resolves both to exactly those places. Both spellings
        are refused now, before the reviewer, creating nothing. Mutant: the `re.sub(r"^//+", "/", …)`
        removed and `os.path.normpath` kept — the repository operand is ACCEPTED, the reviewer runs, the
        transcript lands ON the tracked README.md and the round is voided only afterwards (measured).

        The `/tmp` spelling is asserted on the SHIPPED side only: completing its control would write the
        transcript into the real /tmp, which is the one place this repository forbids. It is the same
        line, the same `case "$OUT" in <prefix>/*)`, and the repository spelling — the damaging half,
        since it overwrites a TRACKED file — carries the control."""
        # The premise the whole finding rests on, pinned here rather than assumed: normpath keeps `//`.
        self.assertTrue(os.path.normpath("//missing14/../tmp/k.txt").startswith("//"),
                        "this python's normpath collapses `//` — the fixture is not the finding")
        # …and the operand's FIRST component must be absent, or the walk stops below `/`, the prefix is
        # never `/`, and no `//` is ever produced — the fixture would pass for the wrong reason.
        missing = f"/missing-{os.path.basename(self.scratch)}"
        self.assertFalse(os.path.lexists(missing), f"the fixture's missing component exists: {missing}")
        # (a) the /tmp spelling — refused, and nothing appears under either physical spelling of /tmp.
        leaf = f"kimi-k1-{os.path.basename(self.scratch)}.txt"
        self._assert_tmp_refused(os.path.join(missing, "..", "tmp", leaf), leaf)
        self.assertFalse(os.path.lexists(missing), f"the refused run created `{missing}`")
        # (b) the live-checkout spelling — refused, README.md untouched, the component never created.
        readme = os.path.join(self.clone, "README.md")
        with open(readme, "rb") as fh:
            original = fh.read()
        self.assertTrue(original, "the fixture's README.md is empty")
        out = os.path.join(missing, "..", os.path.realpath(self.clone).lstrip("/"), "README.md")
        self.assertFalse(out.startswith(self.clone + os.sep), out)          # lexically outside …
        self.assertEqual(os.path.realpath(readme), os.path.realpath(out))    # … physically the tracked file
        p, _ = self._run("clean", out=out)
        self._assert_refused_before_launch(p, out, "inside the live checkout")
        self.assertFalse(os.path.lexists(missing), f"the refused run created `{missing}`")
        with open(readme, "rb") as fh:
            self.assertEqual(original, fh.read(), "the refused run overwrote the tracked file")
        st = subprocess.run(["git", "-C", self.clone, "status", "--porcelain"],
                            capture_output=True, text=True, check=True)
        self.assertEqual("", st.stdout, f"the refused run dirtied the live checkout: {st.stdout!r}")
        # The control: the `//` collapse removed. The SAME operand is accepted, the reviewer runs, and
        # the transcript is written over README.md — the round is voided only after the damage.
        control = self._no_collapse_control()
        p, _ = self._run("clean", out=out, harness=control)
        self.assertEqual(3, p.returncode,
                         f"the CONTROL did not accept the `//`-prefixed operand and void the round after "
                         f"the fact — the fixture is not the finding: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn("real worktree was mutated", p.stderr, p.stderr)
        self.assertTrue(self._stub_ran(), "the CONTROL refused before launch — the fixture is not the finding")
        with open(readme, "rb") as fh:
            overwritten = fh.read()
        self.assertNotEqual(original, overwritten, "the CONTROL did not overwrite README.md")
        self.assertIn(SESSION.encode(), overwritten, "README.md was not overwritten WITH the transcript")

    # The physical prefix, captured and tested on ITS OWN; the control restores the single assignment
    # whose trailing `|| exit 1` was INERT — for an assignment the status is that of the LAST command
    # substitution, which is `basename`.
    OUT_BASE_TESTED = (
        '''_out_base="$(CDPATH='' cd -P -- "$_out_dir" 2>/dev/null && pwd -P)" || _out_base=""\n'''
        '''[ -n "$_out_base" ] || { echo "cannot enter the transcript's physical parent: $_out_dir" >&2; exit 1; }\n'''
        '''OUT="$_out_base/${_out_missing}$(basename -- "$OUT")"\n''')
    OUT_BASE_OLD = ('''OUT="$(CDPATH='' cd -P -- "$_out_dir" 2>/dev/null && pwd -P)'''
                    '''/${_out_missing}$(basename -- "$OUT")" || exit 1\n''')

    def _inert_status_control(self):
        with open(HARNESS, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.OUT_BASE_TESTED),
                         "the physical-prefix block is not unique — the control is not the control")
        return self._laid_out_harness(text.replace(self.OUT_BASE_TESTED, self.OUT_BASE_OLD, 1))

    @unittest.skipIf(os.geteuid() == 0, "root enters a 0000 directory, so the fixture is not the finding")
    def test_a_transcript_parent_that_cannot_be_entered_is_refused_not_re_rooted(self):
        """codex sweep, PR #67 pass 14, finding K2 — the `|| exit 1` after the physical-prefix
        reconstruction was INERT: an assignment takes the status of its LAST command substitution, which
        was `basename`, so a `cd -P` that could not enter its target was ignored, the empty prefix
        silently RE-ROOTED the operand at `/`, and the reviewer was launched on a path the operand never
        named. The prefix is captured and tested on its own now. Mutant: the single-assignment form with
        the trailing `|| exit 1` restored — the operand is accepted, the reviewer runs, and the transcript
        is written to `/` + the missing tail (measured).

        The fixture is an operand whose nearest EXISTING ancestor is a directory this process cannot
        `cd` into (mode 0000), and whose missing tail is the scratch directory's own path minus its
        leading `/` — so the re-rooted spelling is a REAL, writable place the operand never named."""
        nocd = os.path.join(self.scratch, "nocd")
        os.mkdir(nocd)
        os.chmod(nocd, 0o000)
        self.addCleanup(os.chmod, nocd, 0o700)               # LIFO: before the scratch is removed
        rerooted = os.path.join(os.path.realpath(self.scratch), "k2", "kimi.txt")
        out = os.path.join(nocd, os.path.relpath(rerooted, "/"))
        self.assertTrue(os.path.isdir(nocd), "the fixture's unenterable parent must still stat as a directory")
        self.assertFalse(os.path.lexists(os.path.dirname(rerooted)), "the fixture pre-creates the re-rooted parent")
        p, _ = self._run("clean", out=out)
        self._assert_refused_before_launch(p, out, "cannot enter the transcript's physical parent")
        self.assertFalse(os.path.lexists(os.path.dirname(rerooted)),
                         "the refused run created the RE-ROOTED parent — the operand was resolved at `/`")
        # The control: the inert `|| exit 1` restored. The same operand is ACCEPTED, the reviewer runs,
        # and the transcript lands at `/` + the missing tail — a place the operand never named.
        control = self._inert_status_control()
        p, _ = self._run("clean", out=out, harness=control)
        self.assertEqual(4, p.returncode,
                         f"the CONTROL did not accept the operand — the fixture is not the finding: "
                         f"rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn("TREE=clean", p.stdout, p.stdout + p.stderr)
        self.assertTrue(self._stub_ran(), "the CONTROL refused before launch — the fixture is not the finding")
        self.assertTrue(os.path.isfile(rerooted),
                        f"the CONTROL did not write the transcript at the re-rooted path {rerooted}")
        with open(rerooted, encoding="utf-8") as fh:
            self.assertIn(SESSION, fh.read(), "the re-rooted file is not this run's transcript")

    # ── the effort assertion is bound to the ONE session this run created ─────────────────────

    def test_exactly_one_new_session_with_a_max_wire_log_asserts_max(self):
        """The stub creates ONE session under the scratch HOME during the run, with `thinkingEffort:max`
        in its wire log: EFFORT=max, and the harness exits with the reviewer's own status (0)."""
        self.assertFalse(os.path.exists(os.path.join(self.home, ".kimi-code")), "no session before the run")
        p, _ = self._run("new-max")
        self.assertEqual(0, p.returncode, f"new-max: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r"^EXIT=0 BYTES=\d+ TREE=clean BASIS=[0-9a-f]{12} PROMPT=[0-9a-f]{12} EFFORT=max,\(self-reported\) WIRE=[0-9a-f]{12}$")
        self.assertNotIn("EFFORT NOT ASSERTED", p.stderr)
        self.assertTrue(os.path.isfile(self._wire("wd_new", NEW_SESSION)), "the stub's session did not land under the scratch HOME")

    def _quote_old(self, harness):
        """A `max` session exists BEFORE the run; the stub QUOTES its id and creates no session. Returns
        the completed process, after asserting the premise: the transcript carries the quoted id."""
        self._seed_session("wd_old", OLD_SESSION)
        p, out = self._run("quote-old", harness=harness)
        with open(out, encoding="utf-8") as fh:
            self.assertIn(OLD_SESSION, fh.read(), "the fixture is not the finding: the transcript does not quote the old id")
        self.assertFalse(os.path.exists(os.path.join(self.home, ".kimi-code", "sessions", "wd_new")),
                         "quote-old must create no session")
        return p

    def test_an_older_sessions_id_quoted_in_the_transcript_is_not_evidence(self):
        """No session was created during the run, so there is no evidence — whatever the transcript says.
        The pre-existing session's `max` log is NOT consulted: EFFORT=UNKNOWN and exit 4."""
        p = self._quote_old(HARNESS)
        self.assertEqual(4, p.returncode, f"quote-old: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r"^EXIT=0 BYTES=\d+ TREE=clean BASIS=[0-9a-f]{12} PROMPT=[0-9a-f]{12} EFFORT=UNKNOWN\(self-reported\) WIRE=$")
        self.assertIn("EFFORT NOT ASSERTED", p.stderr)

    # The set-difference selection, as shipped — replaced by the control with the PREVIOUS selection: the
    # first `session_<uuid>` grep'd out of the transcript, then that session's wire log.
    SET_DIFFERENCE_HEAD = 'SESSIONS_AFTER="$(ls -d "$HOME"/.kimi-code/sessions/*/session_* 2>/dev/null | LC_ALL=C sort)"\n'
    SET_DIFFERENCE_TAIL = '    [ -r "$_w" ] && WIRE="$_w"\nfi\n'
    TRANSCRIPT_GREP = ('SESSION_ID="$(grep -m1 -oE \'session_[0-9a-f-]{36}\' "$OUT" 2>/dev/null || true)"\n'
                       'WIRE=""\n'
                       'if [ -n "$SESSION_ID" ]; then\n'
                       '    for _w in "$HOME"/.kimi-code/sessions/*/"$SESSION_ID"/agents/main/wire.jsonl; do\n'
                       '        [ -r "$_w" ] && { WIRE="$_w"; break; }\n'
                       '    done\n'
                       'fi\n')

    def _control_harness(self):
        """A copy of the harness with the transcript-grep selection in place of the set difference, laid
        out as `<scratch>/scripts/review/isolated-kimi-review.sh` beside `tree-fingerprint.sh` and
        `containment.py` (the prompt-operand gate, PR #67 pass 12 — the control must reach the reviewer,
        so it needs the same helpers beside it) and under `<scratch>/scripts/pty-capture.py` — the
        harness resolves all three from its OWN directory."""
        with open(HARNESS, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.SET_DIFFERENCE_HEAD), "the set-difference head is not unique")
        start = text.index(self.SET_DIFFERENCE_HEAD)
        self.assertIn(self.SET_DIFFERENCE_TAIL, text[start:], "the set-difference tail was not found after its head")
        end = text.index(self.SET_DIFFERENCE_TAIL, start) + len(self.SET_DIFFERENCE_TAIL)
        block = text[start:end]
        self.assertEqual(1, text.count(block), "the set-difference block is not unique")
        self.assertIn("NEW_SESSIONS", block)
        return self._laid_out_harness(text.replace(block, self.TRANSCRIPT_GREP, 1))

    def _laid_out_harness(self, text):
        """`text` written as `<scratch>/scripts/review/isolated-kimi-review.sh`, beside copies of the helpers
        the harness resolves from its OWN directory (`tree-fingerprint.sh`, `containment.py`) and under
        `<scratch>/scripts/pty-capture.py`. One control per test: the directory must not pre-exist."""
        review_dir = os.path.join(self.scratch, "scripts", "review")
        os.makedirs(review_dir)
        for helper in ("tree-fingerprint.sh", "containment.py"):
            shutil.copy(os.path.join(REPO, "scripts", "review", helper), review_dir)
        shutil.copy(os.path.join(REPO, "scripts", "pty-capture.py"), os.path.join(self.scratch, "scripts"))
        control = os.path.join(review_dir, "isolated-kimi-review.sh")
        with open(control, "w", encoding="utf-8") as fh:
            fh.write(text)
        return control

    def test_the_control_with_the_transcript_grep_selection_certifies_the_quoted_session(self):
        """The CONTROL — the previous, transcript-grep selection — on the SAME quote-old fixture returns the
        older session's `max` and exits 0: it certifies this run on another run's evidence (measured).
        That is the defect; the shipped set difference above does not do it."""
        p = self._quote_old(self._control_harness())
        self.assertEqual(0, p.returncode,
                         f"the CONTROL did not certify the quoted session — the fixture is not the finding: "
                         f"rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r" EFFORT=max,\(self-reported\) WIRE=[0-9a-f]{12}$")

    def test_two_new_sessions_are_not_evidence(self):
        """Two sessions created during the run (a concurrent run's shape), both `max`: no single session is
        this run's, so EFFORT=UNKNOWN and exit 4 — never `max` on the strength of either."""
        p, _ = self._run("two-new")
        self.assertEqual(4, p.returncode, f"two-new: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r" EFFORT=UNKNOWN\(self-reported\) WIRE=$")
        self.assertIn("EFFORT NOT ASSERTED", p.stderr)
        for s in (NEW_SESSION, NEW_SESSION_2):
            self.assertTrue(os.path.isfile(self._wire("wd_new", s)), f"the stub did not create {s}")

    # ── what the effort token is EVIDENCE OF, said on the line itself ─────────────────────────────

    #: The summary line as shipped, and the bare `EFFORT=%s` the control restores. The digest line is
    #: part of the pin: a control that kept it while dropping the label would still print the digest.
    SUMMARY = ('WIRE_SHA=""\n'
               '[ -n "$WIRE" ] && WIRE_SHA="$(python3 -c \'import hashlib,sys; '
               'print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())\' "$WIRE" 2>/dev/null)"\n'
               '\n'
               "printf 'EXIT=%s BYTES=%s TREE=clean BASIS=%s PROMPT=%s EFFORT=%s(self-reported) WIRE=%s\\n' \\\n"
               '    "$STATUS" "$(wc -c < "$OUT" | tr -d \' \')" "${BASIS:0:12}" "${PROMPT_SHA:0:12}" '
               '"${EFFORTS:-UNKNOWN}" "${WIRE_SHA:0:12}"\n')
    SUMMARY_OLD = ("printf 'EXIT=%s BYTES=%s TREE=clean BASIS=%s PROMPT=%s EFFORT=%s\\n' \\\n"
                   '    "$STATUS" "$(wc -c < "$OUT" | tr -d \' \')" "${BASIS:0:12}" "${PROMPT_SHA:0:12}" '
                   '"${EFFORTS:-UNKNOWN}"\n')

    def test_the_effort_token_is_labelled_self_reported_and_digests_the_wire_log_it_read(self):
        """codex, PR #67 pass 15 — the wire log lives INSIDE the session tree of the process it describes,
        under the same `$HOME` and the same uid, and that process has a shell: it can rewrite the file to
        say `max` before this grep reads it, and no file under a HOME it can write authenticates anything
        against it. There is no channel at the same uid that would. So the token says what it is —
        `EFFORT=<v>(self-reported)` — and the digest of the bytes THIS run actually read is printed
        beside it, so a later dispute has something fixed to point at. The exit-4 assertion is unchanged
        and still earns its keep against the failure it was written for: a run whose wire log says `high`
        is refused as evidence about `max`. Mutant: the bare `EFFORT=%s` restored — the line carries
        neither the label nor the digest, and reads as an assertion about the run."""
        wire = self._wire("wd_new", NEW_SESSION)
        p, _ = self._run("new-high", out=os.path.join(self.scratch, "out-high-shipped.txt"))
        self.assertEqual(4, p.returncode, f"new-high: rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn("EFFORT NOT ASSERTED AS max (saw: high,)", p.stderr,
                      f"a `high` wire log was accepted as evidence about max: {p.stderr!r}")
        self.assertTrue(os.path.isfile(wire),
                        "the stub's `high` session did not land under the scratch HOME — there is no "
                        "wire log for the digest to be OF")
        with open(wire, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()[:12]
        self.assertRegex(p.stdout,
                         r"^EXIT=0 BYTES=\d+ TREE=clean BASIS=[0-9a-f]{12} PROMPT=[0-9a-f]{12} "
                         r"EFFORT=high,\(self-reported\) WIRE=" + digest + "$")
        # The control: the bare token — no label, no digest (which is what the line said before).
        control = self._laid_out_harness(self._summary_control_text())
        shutil.rmtree(os.path.join(self.home, ".kimi-code"))     # so the control's run creates it afresh
        p2, _ = self._run("new-high", out=os.path.join(self.scratch, "out-high-control.txt"),
                          harness=control)
        self.assertEqual(4, p2.returncode,
                         f"the CONTROL did not reach the summary — the fixture is not the finding: "
                         f"rc {p2.returncode}\n{p2.stdout}{p2.stderr}")
        self.assertRegex(p2.stdout, r" EFFORT=high,$")
        self.assertNotIn("self-reported", p2.stdout,
                         "the CONTROL still labelled the token — it is not the pre-fix line")
        self.assertNotIn("WIRE=", p2.stdout, "the CONTROL still printed a digest")

    def _summary_control_text(self):
        """The harness text with the shipped summary block replaced by the bare `EFFORT=%s` line."""
        with open(HARNESS, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(1, text.count(self.SUMMARY), "the summary block is not unique — re-derive the pin")
        return text.replace(self.SUMMARY, self.SUMMARY_OLD, 1)


    def test_a_prompt_that_does_not_name_the_operand_is_refused(self):
        """The BASIS must certify the document the prompt actually asks for.

        `README.md` is a tracked regular blob and passes every mode/blob gate, so proving
        "committed file" proved nothing about WHICH committed file (codex, PR #69 round 2). The
        control is the same run with the operand the prompt names: it must get PAST this refusal,
        or the cell is measuring nothing.
        """
        p, out = self._run("clean", plan="README.md")
        self.assertIn("refusing to review one document and certify another", p.stderr,
                      f"a mismatched operand was accepted: rc {p.returncode}\n{p.stderr}")
        self.assertIn("README.md", p.stderr, "the refusal must name the operand it rejected")
        self.assertNotEqual(0, p.returncode)

        control, _ = self._run("clean", plan=DEFAULT_PLAN)
        self.assertNotIn("refusing to review one document", control.stderr,
                         "CONTROL FAILED — the named operand was refused too, so the check above "
                         f"is not discriminating:\n{control.stderr}")

    def test_git_selection_env_cannot_redirect_the_basis(self):
        """A poisoned git environment must not change the BYTES the round certifies.

        The oracle is the `BASIS=<digest>` token on the CLEAN SUMMARY, not the `BASIS plan = <path>`
        diagnostic. An earlier version of this test compared the path line — which is identical in
        both runs by construction, so it reported equality even when the digests differed and could
        not have detected the defect it was written for (codex, PR #69 round 3). It also poisoned
        toward THIS repository, where the plan bytes are the same, so there was nothing to see.

        So: a genuinely separate repository whose plan bytes DIFFER, the poison derived from the
        fixture's own env, both runs required to reach the clean summary, and the digests compared.
        """
        other = os.path.join(self.scratch, "otherrepo")
        os.makedirs(other)
        git = ["git", "-C", other, "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(["git", "init", "-q", other], check=True)
        os.makedirs(os.path.dirname(os.path.join(other, DEFAULT_PLAN)), exist_ok=True)
        with open(os.path.join(other, DEFAULT_PLAN), "w", encoding="utf-8") as fh:
            fh.write("DIFFERENT PLAN BYTES — this repository was never reviewed.\n")
        subprocess.run(git + ["add", "-A"], check=True, capture_output=True)
        subprocess.run(git + ["-c", "commit.gpgsign=false", "commit", "-qm", "other"],
                       check=True, capture_output=True)

        clean, _ = self._run("clean")
        basis_clean = self._basis_digest(clean)
        self.assertIsNotNone(basis_clean,
                             f"CONTROL FAILED — the clean run never printed a summary:\n{clean.stdout}{clean.stderr}")

        poisoned_env = dict(self.env)
        poisoned_env["GIT_DIR"] = os.path.join(other, ".git")
        poisoned_env["GIT_WORK_TREE"] = other
        poisoned_env["GIT_CONFIG_COUNT"] = "1"
        poisoned_env["GIT_CONFIG_KEY_0"] = "core.hooksPath"
        poisoned_env["GIT_CONFIG_VALUE_0"] = os.path.join(self.scratch, "attacker-hooks")
        poisoned, _ = self._run("clean", env=poisoned_env)
        basis_poisoned = self._basis_digest(poisoned)
        self.assertIsNotNone(basis_poisoned,
                             f"the poisoned run never reached the summary, so the digests were never "
                             f"compared:\n{poisoned.stdout}{poisoned.stderr}")
        self.assertEqual(basis_clean, basis_poisoned,
                         "a poisoned git environment changed the BASIS digest the round certifies")

        # THE POSITIVE ORACLE. `clean == poisoned` and `clean != decoy` are both satisfied by an
        # implementation that consistently digests the WRONG file — hashing README.md every time
        # would pass both (codex, PR #69 round 4). So assert what the digest must actually BE:
        # the blob of the reviewed plan at the reviewed commit, computed here independently of the
        # harness.
        import hashlib
        expected = hashlib.sha256(subprocess.check_output(
            ["git", "-C", self.clone, "show", f"HEAD:{DEFAULT_PLAN}"])).hexdigest()[:12]
        self.assertEqual(expected, basis_clean,
                         "the BASIS is not the digest of the reviewed plan's blob — it certifies "
                         "some other bytes, consistently")

        # THE DIGEST MUST FOLLOW THE OPERAND. Everything above still passes an implementation that
        # always hashes DEFAULT_PLAN, because DEFAULT_PLAN is the only operand that reaches the
        # digest in those cells. So run an ACCEPTED alternate and require its own blob.
        alt, _ = self._run("clean", prompt=".review-prompt-alt.md", plan=ALT_PLAN)
        basis_alt = self._basis_digest(alt)
        self.assertIsNotNone(basis_alt,
                             f"the alternate-plan run never reached the summary:\n{alt.stdout}{alt.stderr}")
        expected_alt = hashlib.sha256(subprocess.check_output(
            ["git", "-C", self.clone, "show", f"HEAD:{ALT_PLAN}"])).hexdigest()[:12]
        self.assertEqual(expected_alt, basis_alt,
                         "the BASIS did not follow the plan operand — it certifies the same bytes "
                         "whatever it is asked to certify")
        self.assertNotEqual(basis_clean, basis_alt,
                            "FIXTURE IS VACUOUS — the two plans digest identically")

        # THE UNGUESSABLE OPERAND. This is the assertion a hard-coded implementation cannot satisfy
        # by construction, whatever mapping it hard-codes.
        rand, _ = self._run("clean", prompt=".review-prompt-rand.md", plan=self.rand_plan)
        basis_rand = self._basis_digest(rand)
        self.assertIsNotNone(basis_rand,
                             f"the unpredictable-plan run never reached the summary:\n{rand.stdout}{rand.stderr}")
        expected_rand = hashlib.sha256(subprocess.check_output(
            ["git", "-C", self.clone, "show", f"HEAD:{self.rand_plan}"])).hexdigest()[:12]
        self.assertEqual(expected_rand, basis_rand,
                         "the BASIS did not follow an operand the implementation could not have "
                         "anticipated — the digest is not derived from the full path")

        odd, _ = self._run("clean", prompt=".review-prompt-odd.md", plan=self.odd_plan)
        basis_odd = self._basis_digest(odd)
        self.assertIsNotNone(basis_odd,
                             f"the odd-basename run never reached the summary:\n{odd.stdout}{odd.stderr}")
        expected_odd = hashlib.sha256(subprocess.check_output(
            ["git", "-C", self.clone, "show", f"HEAD:{self.odd_plan}"])).hexdigest()[:12]
        self.assertEqual(expected_odd, basis_odd,
                         "the BASIS did not follow an operand whose BASENAME differs from the others")

        # THE COMMIT AXIS. Same plan path, an EARLIER commit: the digest must be that commit's blob,
        # not HEAD's. This is the assertion a hard-coded-HEAD resolver cannot satisfy.
        older, _ = self._run("clean", commit=self.first_sha)
        basis_older = self._basis_digest(older)
        self.assertIsNotNone(basis_older,
                             f"the earlier-commit run never reached the summary:\n{older.stdout}{older.stderr}")
        expected_older = hashlib.sha256(subprocess.check_output(
            ["git", "-C", self.clone, "show", f"{self.first_sha}:{DEFAULT_PLAN}"])).hexdigest()[:12]
        expected_head = hashlib.sha256(subprocess.check_output(
            ["git", "-C", self.clone, "show", f"HEAD:{DEFAULT_PLAN}"])).hexdigest()[:12]
        self.assertNotEqual(expected_older, expected_head,
                            "FIXTURE IS VACUOUS — the plan's bytes are identical at both commits, so "
                            "a hard-coded HEAD would be indistinguishable")
        self.assertEqual(expected_older, basis_older,
                         "the BASIS did not follow the COMMIT operand — it certifies HEAD whatever "
                         "commit it is asked to certify")

        # ...and the fixture must be capable of showing a difference, or the equality above is
        # vacuous: the decoy's plan bytes must digest differently.
        with open(os.path.join(other, DEFAULT_PLAN), "rb") as fh:
            other_digest = hashlib.sha256(fh.read()).hexdigest()[:12]
        self.assertNotEqual(basis_clean, other_digest,
                            "FIXTURE IS VACUOUS — the decoy repository's plan digests the same as "
                            "the real one, so redirection would be invisible")

    def test_the_reviewer_sees_the_commit_the_basis_certifies(self):
        """Binding the BASIS blob is not the same as putting the reviewer in that commit.

        The round-13 cell proved the DIGEST followed the commit operand — and a mutant that computes
        the BASIS from the right commit while checking out HEAD passed it anyway
        (`basis_oracle=PASS reviewer_bytes=WRONG`, codex round 14 at max). So this asserts what the
        reviewer's own working directory contains, recorded by the stub from inside it.
        """
        proc, _ = self._run("record-checkout", commit=self.first_sha)
        seen_head = os.path.join(self.scratch, "seen-head")
        seen_plan = os.path.join(self.scratch, "seen-plan")
        self.assertTrue(os.path.exists(seen_head),
                        f"the stub never recorded its checkout:\n{proc.stdout}{proc.stderr}")
        with open(seen_head, encoding="utf-8") as fh:
            self.assertEqual(self.first_sha, fh.read().strip(),
                             "the reviewer was placed in a different commit than the BASIS certifies")
        expected = hashlib.sha256(subprocess.check_output(
            ["git", "-C", self.clone, "show", f"{self.first_sha}:{DEFAULT_PLAN}"])).hexdigest()
        with open(seen_plan, encoding="utf-8") as fh:
            self.assertEqual(expected, fh.read().strip(),
                             "the plan bytes in the reviewer's checkout are not the certified ones")

    def test_a_prompt_containing_a_nul_is_refused(self):
        """Command substitution DELETES NULs, so the reviewer would get different bytes than are bound.

        `bind-prompt.py` already refuses this for the plan skills; the kimi harness did not, and the
        divergence was measured: documented length 91, bash argv length 90, bytes_equal=False
        (codex, PR #69 round 14 at max). The control is an ordinary prompt of the SAME length with
        no NUL — it must still be accepted, or this cell proves only that the harness refuses things.
        """
        nul_prompt = ".review-prompt-nul.md"
        with open(os.path.join(self.clone, nul_prompt), "wb") as fh:
            fh.write(b"Plan under review: " + DEFAULT_PLAN.encode() + b"\n")
            fh.write(b"body with a NUL\x00 inside\n" * 20)
        proc, _ = self._run("clean", prompt=nul_prompt)
        self.assertNotEqual(0, proc.returncode,
                            f"a prompt containing a NUL was accepted:\n{proc.stdout}{proc.stderr}")
        self.assertIn("NUL", proc.stderr,
                      f"the refusal did not name the cause:\n{proc.stderr}")

        control_prompt = ".review-prompt-nonul.md"
        with open(os.path.join(self.clone, control_prompt), "wb") as fh:
            fh.write(b"Plan under review: " + DEFAULT_PLAN.encode() + b"\n")
            fh.write(b"body with a NUL. inside\n" * 20)      # same shape, no NUL
        control, _ = self._run("clean", prompt=control_prompt)
        self.assertNotIn("NUL", control.stderr,
                         f"CONTROL FAILED — an ordinary prompt was refused as containing a NUL:\n"
                         f"{control.stderr}")
        # "did not mention NUL" is not "was accepted" — a run that dies for ANY other reason also
        # omits the word, so the control proved nothing about the guard (codex, PR #69 round 15).
        # Require it to get PAST the binder and reach the capture summary.
        self.assertIn("BASIS=", control.stdout,
                      f"CONTROL FAILED — the ordinary prompt never reached the capture, so this cell "
                      f"does not show the guard admits valid prompts:\n{control.stdout}{control.stderr}")

    def test_a_nonzero_reviewer_status_is_preserved(self):
        """Every stub mode terminated with an approving printf, so no failing reviewer was sampled."""
        proc, _ = self._run("fail-nonzero")
        self.assertNotEqual(0, proc.returncode,
                            f"a reviewer exiting 7 was reported as success:\n{proc.stdout}{proc.stderr}")
        # `TREE=clean` is a statement about the FINGERPRINT — the reviewer mutated nothing — and is
        # correct here. The reviewer's own status is carried separately, and that is what must
        # survive. (My first assertion conflated the two and would have "fixed" correct behaviour.)
        self.assertIn("EXIT=7", proc.stdout,
                      f"the reviewer's exit status was not carried into the summary:\n{proc.stdout}")

    def test_a_timeout_is_reported_and_not_silently_clean(self):
        """The timeout was hard-coded to 60 in every cell, so the timeout path was never exercised."""
        proc, _ = self._run("slow", timeout=2)
        self.assertNotEqual(0, proc.returncode,
                            f"a timed-out round reported success:\n{proc.stdout}{proc.stderr}")
        self.assertIn("EXIT=124", proc.stdout,
                      f"a timeout was not reported as 124 in the summary:\n{proc.stdout}")
        self.assertIn("BYTES=0", proc.stdout,
                      "a timed-out round should have captured no transcript bytes")

    def test_a_foreign_session_is_not_this_runs_evidence(self):
        """A stranger's concurrent session must not be read as this round's effort.

        Set difference cannot tell it from ours — reproduced in round 16 as
        `reviewer_sessions_created=0 foreign_sessions_created=1 would_pass_max_gate=yes`. Provenance
        now comes from the launch: kimi files each session under a namespace derived from its cwd,
        and this harness launches from a unique per-invocation directory.
        """
        p, _ = self._run("foreign-only")
        self.assertNotRegex(p.stdout, r"EFFORT=max",
                            f"a foreign session was certified as this run's effort:\n{p.stdout}")

    def test_a_session_without_recorded_provenance_is_not_this_runs_evidence(self):
        """No `state.json` means the cwd is unknowable — which must fail closed, not default to ours.

        The foreign-session cell alone did not cover this: that fixture HAS a state.json recording a
        different cwd, so a variant that treats an unreadable state as "ours" passed it. Found by
        mutating toward the pre-round-16 count-only selection.
        """
        p, _ = self._run("no-state")
        self.assertNotRegex(p.stdout, r"EFFORT=max",
                            f"a session with no recorded cwd was treated as this run's:\n{p.stdout}")

    def test_an_empty_capture_with_one_new_session_is_not_evidence(self):
        """The seventh axis: (empty transcript, exactly one new session).

        Cells covered (nonempty, one) and (empty, zero); the combination the guard actually decides
        was never sampled, so the guard had no regression (codex, PR #69 round 16).
        """
        p, _ = self._run("empty-plus-one")
        self.assertNotRegex(p.stdout, r"EFFORT=max",
                            f"an empty capture certified an effort from a session it did not "
                            f"produce:\n{p.stdout}")

    def test_the_real_workdir_schema_is_accepted_as_this_runs_evidence(self):
        """THE EIGHTH AXIS: state-schema variation across Kimi versions.

        Real sessions record the cwd under `workDir` (the 0.32.0-era schema this repo's own
        KIMI_REVIEW_ARM_PLAN pins as the baseline) or under `cwd` (the newer `version=2` schema).
        Measured across 63 stored sessions on the development machine: 38 `workDir` to 25 `cwd`,
        never both. The round-16 filter read only `cwd`/`workingDirectory`, so it rejected the
        MAJORITY of real sessions and broke the arm closed with `EFFORT=UNKNOWN` exit 4
        (codex, PR #69 round 17).

        This is the first POSITIVE provenance cell. Every other one asserts a rejection, so a
        filter that rejects EVERYTHING satisfied all of them - which is precisely how a
        fail-closed break survived three rounds of adversarial review. Dropping `workDir` from
        the accepted spellings turns this red.
        """
        self.assertFalse(os.path.exists(os.path.join(self.home, ".kimi-code")), "no session before the run")
        p, _ = self._run("workdir-max")
        self.assertEqual(0, p.returncode,
                         f"a valid max-effort round on the majority schema exited nonzero - the arm "
                         f"fails closed on real input:\n{p.stdout}{p.stderr}")
        self.assertRegex(p.stdout, r"^EXIT=0 BYTES=\d+ TREE=clean BASIS=[0-9a-f]{12} "
                                   r"PROMPT=[0-9a-f]{12} EFFORT=max,\(self-reported\) WIRE=[0-9a-f]{12}$")
        self.assertNotIn("EFFORT NOT ASSERTED", p.stderr)

    def test_conflicting_recorded_cwd_aliases_fail_closed(self):
        """Two aliases naming DIFFERENT directories cannot both be this run's provenance.

        Accepting all three spellings invites a first-truthy read, which a crafted `state.json`
        steers just by choosing which alias to populate: put ours in the alias that wins and a
        stranger's in the other. Disagreement is unknowable, and unknowable fails closed.
        Mutating the parser back to first-truthy (`d.get("cwd") or ... or d.get("workDir")`)
        turns this red while the positive cell above stays green.
        """
        p, _ = self._run("alias-conflict")
        self.assertNotRegex(p.stdout, r"EFFORT=max",
                            f"an ambiguous provenance record was resolved by alias precedence "
                            f"instead of failing closed:\n{p.stdout}")

    def test_a_malformed_alias_fails_closed_rather_than_being_ignored(self):
        """A non-string alias makes the record unreadable as written - which is unknowable, not ours.

        `{"cwd": <ours>, "workDir": 12345}` names our directory in one alias and garbage in another.
        Ignoring the bad alias accepts it; that is the permissive direction, and it was also
        UNDETECTABLE - mutation gate C deleted the type check and every cell still passed, so the
        first draft of this fix shipped a guard no test could fail on. Failing closed is both safer
        and observable: mutating this back to "ignore non-strings" turns this cell red while the
        `workdir-max` and `alias-conflict` cells stay green.
        """
        p, _ = self._run("malformed-alias")
        self.assertNotRegex(p.stdout, r"EFFORT=max",
                            f"a state.json with a non-string alias was accepted as this run's "
                            f"provenance instead of failing closed:\n{p.stdout}")

    def test_a_configured_tier_is_not_evidence_that_the_model_ran(self):
        """THE NINTH AXIS: the effort token proves CONFIGURATION, not EXECUTION.

        `thinkingEffort` appears in six record types across the real store, and only `llm.request`
        means the model was actually asked at that tier. `profile.bind` is written when the session
        binds its profile, before any inference — a statement of intent.

        Two REAL sessions in this harness's own `wd_tree_*` namespace hold exactly
        `metadata` + `profile.bind` + `permission.set_mode`, with zero `llm.request` records, and the
        unfiltered extraction reported `max,` and PASSED the gate — certifying a tier for a round in
        which the model was never called. Seven of 63 real sessions carry an effort token with no
        `llm.request` at all.

        The filter was checked in both directions against the real store before shipping: 51 sessions
        yielded `max,` unfiltered and 49 do filtered, and the only two that change are exactly those
        two zero-inference sessions. Deleting the `d.get("type")!="llm.request"` guard turns this red.
        """
        p, _ = self._run("bind-only")
        self.assertNotRegex(p.stdout, r"EFFORT=max",
                            f"a round in which the model never ran was certified at the tier its "
                            f"profile was merely BOUND to:\n{p.stdout}")
        self.assertNotEqual(0, p.returncode,
                            f"a round with no inference exited success:\n{p.stdout}{p.stderr}")

    def _assert_unknown_not_max(self, mode, what):
        """A round whose wire log this harness cannot fully account for is not evidence about max."""
        p, _ = self._run(mode)
        self.assertNotRegex(p.stdout, r"EFFORT=max",
                            f"{what} still certified max — the mixed known/unknown axis is "
                            f"fail-OPEN:\n{p.stdout}")
        self.assertNotEqual(0, p.returncode,
                            f"{what} exited success:\n{p.stdout}{p.stderr}")

    def test_a_request_with_no_recorded_tier_forces_unknown(self):
        """THE NINTH AXIS, second half: mixed KNOWN and UNKNOWN requests (codex, PR #69 round 18).

        Skipping an unreadable `llm.request` is fail-OPEN: if an earlier request recorded `max`, the
        surviving set is still exactly `max,` and the gate passes. Reproduced by the reviewer as
        `unknown_missing_field EFFORTS=max, would_max_gate_pass=yes`.

        Strictness is free: the real store has 12094 non-empty wire lines, ZERO unparseable and ZERO
        `llm.request` records lacking a valid string tier, and the filtered distribution over 63 real
        logs is unchanged at 49/7/6/1.
        """
        self._assert_unknown_not_max("mixed-nofield", "a request with no recorded tier")

    def test_a_request_with_a_nonstring_tier_forces_unknown(self):
        """`{"type":"llm.request","thinkingEffort":123}` — a tier that cannot be read as written.

        A separate code path from the missing-field case: the key is present and truthy, so a guard
        keyed only on presence would pass it through.
        """
        self._assert_unknown_not_max("mixed-nonstr", "a request with a non-string tier")

    def test_an_unparseable_wire_record_forces_unknown(self):
        """An unreadable line is how a low-tier request would be HIDDEN from the set.

        The wire log is written by the reviewed process at the same uid (see the self-reported
        caveat), so emitting one malformed line is the cheapest way to drop a `high` request while
        leaving the `max` ones visible. Skipping it certifies `max,`.
        """
        self._assert_unknown_not_max("mixed-malform", "an unparseable wire record")

    def test_invalid_utf8_cannot_reclassify_a_request_away(self):
        """A corrupt byte must not silently turn a request into "some other record type".

        `errors="replace"` maps an invalid byte to U+FFFD, so `{"type":"llm.requ\\xffst",...}` PARSES
        — as a non-request. It is then skipped, and an earlier `max` survives to pass the gate.
        Reproduced by codex (PR #69 round 19) as `EFFORTS=max, would_max_gate_pass=yes`.

        This is the round-18 hiding place reached through a different door: that fix assumed
        "unreadable" meant "unparseable", but replacement decoding makes a corrupt record readable
        and RECLASSIFIED. Reading raw bytes puts invalid UTF-8 back on the UNKNOWN path.

        Mutating the open back to `open(path, errors="replace")` turns this cell red while every
        other effort cell stays green — the byte here is inside the `type` value, so no other
        fixture reaches it.
        """
        self._assert_unknown_not_max("mixed-badutf8",
                                     "a request reclassified by an invalid UTF-8 byte")

    def test_a_nul_in_the_tier_cannot_become_max_in_transit(self):
        """The tier is validated in PYTHON but transported through COMMAND SUBSTITUTION, and bash
        deletes NUL bytes. `"m\\u0000ax"` parses as `m\\x00ax` — provably not `max` — passes an
        `isinstance(v,str) and v` check, and arrives at the gate as exactly `max,` (codex, PR #69
        round 20: `parsed='m\\x00ax' exact_max=False ... shell_EFFORTS=max, length=4 gate=PASS`).

        The check and the use were in two languages with different string semantics. The tier is now
        constrained to bytes that mean the same thing on both sides: ASCII, alphabetic, lower-case —
        structural, not a vocabulary of known tiers.
        """
        self._assert_unknown_not_max("mixed-nultier", "a tier whose NUL is deleted in transit")

    def test_a_duplicate_type_cannot_hide_a_request(self):
        """`{"type":"llm.request","thinkingEffort":"high","type":"metadata"}` — last-wins makes an
        explicit `high` request stop looking like a request, so the earlier `max` stands alone."""
        self._assert_unknown_not_max("dup-type", "a request hidden by a duplicate `type`")

    def test_a_duplicate_tier_cannot_rewrite_the_tier(self):
        """One request naming TWO tiers. `json.loads` is last-wins, which is silent rewriting."""
        self._assert_unknown_not_max("dup-tier", "a tier rewritten by a duplicate name")

    def test_a_duplicate_cwd_cannot_bypass_the_alias_guard(self):
        """The conflicting-alias guard could not fire, because last-wins collapsed the conflict first.

        `{"cwd":"/nowhere/else","cwd":"<ours>"}` reaches the guard as a single `cwd` — so the guard
        that refuses DISAGREEING aliases never saw a disagreement. Walking around a guard by
        preventing it from seeing its own input is the same shape as the round-19 reclassification.
        """
        self._assert_unknown_not_max("dup-cwd", "a duplicate `cwd` collapsed before the guard")

    def test_a_timeout_that_emitted_bytes_is_still_not_a_pass(self):
        """A timed-out round CAN reach the effort block — the claim that it cannot was false.

        `pty-capture.py` deliberately writes the partial transcript on timeout (its own comments at
        lines 21, 404, 612), and the WIRE block never inspects `STATUS`. So `[ -s "$OUT" ]` is
        satisfiable with `STATUS=124`, reproduced by codex as
        `STATUS=124 OUT_BYTES=53239 reaches_WIRE_block=yes`. This cell exists because the audit
        claimed the opposite and was wrong; the safety property — a timed-out round is never a pass —
        is real and is what is asserted here.
        """
        p, _ = self._run("slow-loud", timeout=2)
        self.assertNotEqual(0, p.returncode,
                            f"a timed-out round that emitted bytes reported success:\n{p.stdout}{p.stderr}")
        self.assertIn("EXIT=124", p.stdout,
                      f"a timeout was not reported as 124:\n{p.stdout}")

    def _basis_digest(self, proc):
        """The `BASIS=<digest>` token from the CLEAN SUMMARY on stdout — never the path diagnostic."""
        m = re.search(r"\bBASIS=([0-9a-f]{12})\b", proc.stdout or "")
        return m.group(1) if m else None

    # ── the plan operand's spelling (harness lines 59-68) ─────────────────────────────────────────

    def test_a_plan_operand_that_escapes_the_repository_is_refused(self):
        """`isolated-kimi-review.sh:59-68`. The plan operand is MODEL-CHOSEN — `codex-review/SKILL.md`
        says the stand-in is invoked "always passing <plan>" — and it is what the BASIS digest
        certifies. An operand that escapes the checkout makes the printed BASIS attest to bytes
        outside the reviewed commit, the same class the prompt operand's containment already closed.

        Each case asserts the DIAGNOSTIC, never merely `rc != 0`: with the containment removed the
        run still fails, further on and for an unrelated reason, so an exit-status cell proves
        nothing about this guard.
        """
        for operand, message in (
            ("/etc/passwd", "plan operand must be repository-relative, not absolute"),
            ("../../etc/passwd", "plan operand must not traverse upward"),
            ("docs/planning/../../../etc/passwd", "plan operand must not traverse upward"),
            ("", "plan operand must not be empty"),
            ("docs/planning/a\nb.md", "plan operand must not contain control characters"),
        ):
            with self.subTest(operand=operand):
                p, _ = self._run("clean", plan=operand)
                self.assertEqual(1, p.returncode, p.stdout + p.stderr)
                self.assertIn(message, p.stderr, p.stderr)
                self.assertFalse(self._stub_ran(),
                                 "the reviewer was launched on an uncontained plan operand")

    def test_a_CONTAINED_plan_operand_is_not_refused_by_the_spelling_check(self):
        """The discrimination control: without it the cell above would also pass against a harness
        that refused every plan operand it was given."""
        p, _ = self._run("clean")
        self.assertNotIn("plan operand must", p.stderr, p.stderr)

    def test_a_plan_that_is_a_SYMLINK_in_the_reviewed_commit_is_refused(self):
        """`isolated-kimi-review.sh:259`. `git cat-file blob` on a mode-120000 entry returns its
        TARGET PATH, so without the mode check the BASIS digest certifies the string `/etc/hosts`
        rather than any plan at all — and the reviewer is launched anyway."""
        link_rel = "docs/planning/SYMLINK_PLAN.md"
        os.symlink("/etc/hosts", os.path.join(self.clone, link_rel))
        prompt = ".review-prompt-sym.md"
        with open(os.path.join(self.clone, prompt), "w", encoding="utf-8") as fh:
            fh.write("Plan under review: " + link_rel + "\n")
            fh.write("Review the symlinked plan.\n" * 40)
        with open(os.path.join(self.clone, ".gitignore"), "a", encoding="utf-8") as fh:
            fh.write(prompt + "\n")
        git = ["git", "-C", self.clone]
        subprocess.run(git + ["add", "-A"], check=True, capture_output=True)
        subprocess.run(git + ["-c", "commit.gpgsign=false", "commit", "-qm", "symlink plan"],
                       check=True, capture_output=True)
        mode = subprocess.check_output(
            git + ["ls-tree", "--format=%(objectmode)", "HEAD", "--", link_rel], text=True).strip()
        self.assertEqual("120000", mode,
                         "the fixture is not the finding: the plan is not a committed symlink")
        p, out = self._run("clean", prompt=prompt, plan=link_rel)
        self._assert_refused_before_launch(p, out, "plan is a symlink in the reviewed commit")
        self.assertIsNone(self._basis_digest(p),
                          "a symlink plan reached the summary — its BASIS certifies the TARGET path")

    # ── the private scratch allocation (harness line 121) ─────────────────────────────────────────

    def test_a_failed_scratch_allocation_is_refused_not_run_with_an_EMPTY_tree(self):
        """`isolated-kimi-review.sh:121`. A failed `mktemp -d` must abort the round.

        Without the `|| exit 1` the harness proceeds with `TREE=""`: it copies the prompt snapshot to
        `/prompt.snapshot`, then reports "prompt unreadable" — naming the wrong cause entirely — and
        the EXIT trap's `rm -rf "$TREE"` is a no-op, so where `/` is writable the snapshot leaks.
        """
        env = dict(self.env)
        env["TMPDIR"] = os.path.join(self.scratch, "no-such-tmpdir")   # deliberately absent
        p, _ = self._run("clean", env=env)
        self.assertNotEqual(0, p.returncode, p.stdout + p.stderr)
        self.assertFalse(self._stub_ran(), "the reviewer was launched without a scratch directory")
        self.assertNotIn("TREE=clean", p.stdout, "a failed allocation printed the clean summary")
        # THE DISCRIMINATOR, and the reason the three assertions above are not enough. With `|| exit 1`
        # weakened to `|| :` the round STILL exits non-zero, STILL never launches the reviewer and
        # STILL prints no clean summary — so all three pass against the mutant and it survives
        # (measured). What actually changes is the CAUSE the operator is told: the mutant runs on with
        # `TREE=""`, tries `cp -- … "/prompt.snapshot"`, and reports `prompt unreadable: <path>` —
        # blaming a prompt file that is perfectly readable. Naming the wrong cause is the defect.
        self.assertNotIn("prompt unreadable", p.stderr,
                         f"the run continued past a failed scratch allocation and misreported the "
                         f"cause as an unreadable prompt:\n{p.stderr}")

    # ── the post-run probes: a tree that cannot be read is not evidence ───────────────────────────

    def test_a_disposable_checkout_that_cannot_be_RE_READ_after_the_review_voids(self):
        """`isolated-kimi-review.sh:364`. FAIL CLOSED — a tree that cannot be READ is not evidence.

        `|| true` here once turned a failed probe into an EMPTY string, which compares equal to a
        clean baseline, so all three mutation checks passed and a reviewer that corrupted its own
        checkout and wrote whatever it liked was certified (codex, PR #67).

        WHAT THE FIXTURE HAD TO BE, and why it is not the obvious one. Making the checkout merely
        UNREADABLE (`chmod 000 .`) does NOT reach this arm: `disposable_fingerprint` walks with
        `os.walk`, which swallows permission errors by default, so it returns an EMPTY listing and
        exit 0. Measured — the round is still voided, but by the content comparison three lines
        below, and a cell built on that fixture would pin the wrong guard. Deleting the checkout
        makes the probe's `os.path.isdir` precondition false, which is the arm under test.

        Deleting is also uid-independent, so this cell needs no root skip: a `chmod`-based fixture
        would have silently stopped testing anything for a developer running as root.
        """
        p, _ = self._run("selfdestruct-tree")
        self.assertEqual(3, p.returncode, f"rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn("could not be re-read after the review", p.stderr, p.stderr)
        self.assertNotIn("the reviewer left edits inside the disposable checkout", p.stderr,
                         "the content-comparison path fired instead — this cell is not pinning line 364")
        self.assertNotIn("TREE=clean", p.stdout, "a void round printed the clean summary")

    def test_a_reviewer_that_destroys_the_LIVE_git_dir_voids_the_round(self):
        """`isolated-kimi-review.sh:356`. The LIVE checkout's post-review fingerprint must fail
        CLOSED, and be distinguishable from the mutation verdict three lines below it."""
        p, _ = self._run("livegitkill")
        self.assertEqual(3, p.returncode, f"rc {p.returncode}\n{p.stdout}{p.stderr}")
        self.assertIn("could not fingerprint the live checkout after the review", p.stderr, p.stderr)
        self.assertNotIn("the real worktree was mutated", p.stderr,
                         "the line-369 path fired instead — this cell is not pinning line 356")
        self.assertNotIn("TREE=clean", p.stdout, "a void round printed the clean summary")

    def test_a_reviewer_that_destroys_the_BASIS_OBJECT_voids_the_round(self):
        """`isolated-kimi-review.sh:373` — the COREDEV-2607 staged-basis signature.

        The sweep called this branch unreachable, on the grounds that BASIS and AFTER_BASIS are read
        from the same git object. That holds on the stub axis but not in general: AFTER_BASIS is
        computed with `2>/dev/null … || echo MISSING`, so it becomes the literal string `MISSING`
        whenever the live repository stops answering for that blob after the run — which a reviewer
        with write access to the checkout can arrange. That is what the stub mode does.

        THE BLOB IS MADE LOOSE ON PURPOSE. A local `git clone` HARDLINKS the source object store, so
        whether this blob is loose or packed is inherited from whatever state the source repo happened
        to be in — and `git gc --auto` can repack it at any time, after which deleting the loose path
        is a silent no-op and the round reaches the ordinary exit 4 instead of the asserted void
        (codex, PR #73). Committing unique bytes writes a brand-new object, which git always writes
        loose, so the fixture no longer depends on the clone's storage layout. The premise is then
        ASSERTED rather than assumed.
        """
        marker = f"\n<!-- basis-destroy {os.getpid()} -->\n"
        plan_path = os.path.join(self.clone, DEFAULT_PLAN)
        with open(plan_path, "a", encoding="utf-8") as fh:
            fh.write(marker)
        git = ["git", "-C", self.clone]
        subprocess.run(git + ["add", "--", DEFAULT_PLAN], check=True, capture_output=True)
        subprocess.run(git + ["-c", "commit.gpgsign=false", "commit", "-qm", "unique basis"],
                       check=True, capture_output=True)
        blob = subprocess.check_output(
            git + ["rev-parse", f"HEAD:{DEFAULT_PLAN}"], text=True).strip()
        loose = os.path.join(self.clone, ".git", "objects", blob[:2], blob[2:])
        self.assertTrue(os.path.isfile(loose),
                        f"the basis blob {blob[:12]} is not a loose object, so the stub's delete would "
                        f"be a no-op and this cell would pass for the wrong reason")
        self._assert_void("basis-destroy", "modified the staged plan")


if __name__ == "__main__":
    unittest.main()
