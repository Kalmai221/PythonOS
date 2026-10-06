import sys

import pyos.stdio as stdio
from pyos import paging, textcmd

config = {"name": "less", "description": "Read a file or piped text one screen at a time (less [file]); the same as more.", "alias": ["more"]}


def execute(args=None):
    text = textcmd.read_text(args, "less")
    if text is None:
        return False
    real = sys.stdout._real if hasattr(sys.stdout, "_real") else sys.stdout
    if not real.isatty() or stdio.read_stdin() is not None and not args:
        textcmd.console.print(text, markup=False, highlight=False, end="")
        return True
    pager = paging.Pager(real.write, input)
    pager.write(text if text.endswith("\n") else text + "\n")
    return True
