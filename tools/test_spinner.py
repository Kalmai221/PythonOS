#!/usr/bin/env python3
"""pyos/spinner.py: the Linux text console (live ISO, virtual machines) and serial consoles get the plain line spinner because their font has no
Braille; terminal windows keep the dots; PYTHONOS_SPINNER overrides; every console.status(...) follows it without changing its callers."""
import io
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)
os.chdir(REPO)

from rich.console import Console  # noqa: E402

import pyos  # noqa: E402,F401  (importing it installs the patch)
from pyos import spinner  # noqa: E402


class Stream:
    def __init__(self, encoding):
        self.encoding = encoding


def main():
    utf8 = Stream("utf-8")
    # the Linux console and the plain terminals: no Braille
    for term in ("linux", "vt100", "VT220", "dumb", "ansi"):
        assert spinner.ascii_only({"TERM": term}, utf8), term
    # terminal windows and SSH keep the dots
    for term in ("xterm-256color", "xterm", "screen-256color", "tmux-256color", "alacritty", ""):
        assert not spinner.ascii_only({"TERM": term}, utf8), term
    # a terminal that cannot print Braille at all (a legacy code page)
    assert spinner.ascii_only({"TERM": "xterm"}, Stream("cp1252")) and not spinner.ascii_only({"TERM": "xterm"}, Stream(None))
    # the override wins both ways
    assert spinner.ascii_only({"TERM": "xterm", "PYTHONOS_SPINNER": "ascii"}, utf8)
    assert not spinner.ascii_only({"TERM": "linux", "PYTHONOS_SPINNER": "unicode"}, utf8)
    # kind() and the yaspin spinner follow the environment
    saved = {k: os.environ.get(k) for k in ("TERM", "PYTHONOS_SPINNER")}
    try:
        os.environ.pop("PYTHONOS_SPINNER", None)
        os.environ["TERM"] = "linux"
        assert spinner.kind() == "line" and spinner.yaspin_spinner().frames == ["-", "\\", "|", "/"]
        # every console.status gets the plain spinner, a caller that names its own spinner keeps it
        console = Console(file=io.StringIO(), force_terminal=True)
        assert Console._pyos_spinner is True
        assert console.status("working").renderable.name == "line"
        assert console.status("working", spinner="moon").renderable.name == "moon"
        os.environ["TERM"] = "xterm-256color"
        os.environ["PYTHONOS_SPINNER"] = "unicode"                 # (a Windows test machine's stdout may be a legacy code page, which asks for plain)
        assert spinner.kind() == "dots" and console.status("working").renderable.name == "dots"
        assert all(ord(c) >= 0x2800 for c in spinner.yaspin_spinner().frames[0])
        # unpatch gives Rich's own status back; patching twice changes nothing
        before = Console.status
        spinner.patch()
        assert Console.status is before
        spinner.unpatch()
        os.environ.pop("PYTHONOS_SPINNER", None)
        os.environ["TERM"] = "linux"
        assert console.status("x").renderable.name == "dots" and Console._pyos_spinner is False        # Rich's own, whatever the screen
        spinner.patch()
        assert console.status("x").renderable.name == "line"
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    print("spinners: all checks passed")


if __name__ == "__main__":
    main()
