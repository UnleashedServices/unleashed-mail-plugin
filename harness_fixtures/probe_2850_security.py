"""COREDEV-2850 probe (cell 3): ONE new security finding, bound by its bandit ID. Never merged."""

import subprocess


def run(command: str) -> int:
    """Run a command through the shell, which bandit reports as B602."""
    return subprocess.call(command, shell=True)
