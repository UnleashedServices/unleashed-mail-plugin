#!/usr/bin/env python3
# agy-login.py — drive a non-interactive agy OAuth login inside a PTY on a
# headless/file-storage host, so agy writes its own correctly-formatted token
# file (which base64-encodes into AGY_CREDS via setup/get-agy-creds.sh).
#
# Why this exists: agy's print-mode login prints the Google URL as plain text
# and accepts the authorization code on stdin, but the interactive TUI needs a
# real terminal and the print-mode auth wait is a fixed ~60s. This driver runs
# agy under a PTY, mirrors its output (ANSI-stripped) to OUT_FILE so the URL can
# be read, and submits the code the moment it appears in CODE_FILE.
#
# Procedure:
#   1. python3 setup/agy-login.py        (starts it; keep it running)
#   2. read the Google URL from /tmp/agy-login.out and open it in a browser
#      signed in as the target account; approve.
#   3. the browser lands on antigravity.google/oauth-callback?code=... — copy the
#      code value and:  printf '%s' '<CODE>' > /tmp/agy-login.code
#   4. agy exchanges the code and writes ~/.gemini/antigravity-cli/antigravity-oauth-token
#   5. bash setup/get-agy-creds.sh   ->  your new AGY_CREDS
#
# The ~60s window runs from when agy prints the URL, so have the browser ready.
import os, pty, select, time, re

OUT_FILE  = os.environ.get("AGY_LOGIN_OUT",  "/tmp/agy-login.out")
CODE_FILE = os.environ.get("AGY_LOGIN_CODE", "/tmp/agy-login.code")
MAX_SECS  = int(os.environ.get("AGY_LOGIN_MAX_SECS", "1800"))
ANSI = re.compile(rb'\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[=>]|\x1b\][^\x07]*\x07|\r')

for f in (OUT_FILE, CODE_FILE, CODE_FILE + ".sent"):
    try: os.remove(f)
    except OSError: pass

pid, fd = pty.fork()
if pid == 0:
    os.environ["TERM"] = "xterm-256color"
    os.execvp("agy", ["agy", "--print-timeout", "20m", "-p", "ping"])
    os._exit(127)

start, sent = time.time(), False
with open(OUT_FILE, "ab", buffering=0) as out:
    while time.time() - start < MAX_SECS:
        try:
            r, _, _ = select.select([fd], [], [], 0.5)
        except (InterruptedError, OSError):
            continue
        if fd in r:
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            out.write(ANSI.sub(b'', data))
        if not sent and os.path.exists(CODE_FILE):
            code = open(CODE_FILE).read().strip()
            if code:
                os.write(fd, (code + "\n").encode())
                out.write(b"\n[agy-login: submitted code]\n")
                os.rename(CODE_FILE, CODE_FILE + ".sent")
                sent = True
        try:
            if os.waitpid(pid, os.WNOHANG)[0] == pid:
                out.write(b"\n[agy-login: agy exited]\n")
                break
        except ChildProcessError:
            break
try: os.close(fd)
except OSError: pass
