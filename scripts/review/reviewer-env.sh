# shellcheck shell=bash
# The Gemini arm's own process environment (COREDEV-2887, PR #124 review). Sourced FIRST — before any external
# command runs — by every entrypoint: `capture-gemini-review.sh`, `isolated-gemini-review.sh` and
# `preflight-gemini.sh`. The working directory of almost everything they run is a checkout of the reviewed branch,
# so nothing that resolves FROM the working directory may decide what runs:
#
# 1. PATH KEEPS ONLY ABSOLUTE ENTRIES OUTSIDE THE LIVE CHECKOUT. A relative entry (`.`, `bin`, an empty one)
#    resolves from the working directory, and an absolute entry inside the checkout (a direnv `PATH_add bin`) is
#    the branch's to populate; through either, a committed `python3`, `git` or `gemini` would run as the arm's
#    own. The checkout is found from `.git` with shell builtins alone, because nothing may be looked up on PATH
#    before PATH is safe.
# 2. EVERY `python3` THIS SHELL RUNS IS ISOLATED, including those inside the libraries it sources
#    (`tree-fingerprint.sh`), because a function outranks PATH lookup. `python3 -c` and a `python3 -` heredoc put
#    the working directory FIRST on the import path, so a `json.py` or `hashlib.py` committed at the repository
#    root replaced the standard library inside the context-file scan and the tree fingerprints (reproduced on
#    3.14). `-I` drops that entry and ignores `PYTHONPATH`, `PYTHONHOME` and the user's site directory; `-B` keeps
#    the no-bytecode rule, which `-I` would otherwise drop because it also ignores `PYTHONDONTWRITEBYTECODE`.
#    A process that is not this shell — the adapter, which `pty-capture.py` executes — passes `-I -B` itself.
#
# NOT COVERED: a symlinked `python3` or `git` in an outside PATH directory whose TARGET is inside the checkout
# (the adapter checks the resolved target of the `gemini` it runs), and a separate `bash` process this shell starts
# (`allocate-transcript.sh`), which does not inherit the function. The same inline-Python exposure elsewhere in the
# plugin — the other arms' harnesses, the hook libraries — is COREDEV-2891.

_re_top="$(pwd -P)"
while [[ -n ${_re_top} && ! -e ${_re_top}/.git ]]; do
	_re_top="${_re_top%/*}"
done
_re_kept=""
_re_rest="${PATH-}:"
while [[ -n ${_re_rest} ]]; do
	_re_entry="${_re_rest%%:*}"
	_re_rest="${_re_rest#*:}"
	[[ ${_re_entry} == /* ]] || continue
	if [[ -n ${_re_top} ]]; then
		_re_real="$(CDPATH='' cd -P -- "${_re_entry}" 2>/dev/null && pwd -P)" || _re_real="${_re_entry}"
		if [[ ${_re_real} == "${_re_top}" || ${_re_real} == "${_re_top}"/* ]]; then
			continue
		fi
	fi
	_re_kept="${_re_kept:+${_re_kept}:}${_re_entry}"
done
PATH="${_re_kept}"
export PATH
unset _re_top _re_kept _re_rest _re_entry _re_real

python3() { command python3 -I -B "$@"; }
