import sys

from pyos import stdio

config = {
    "name": "clear",
    "description": "Clears the screen and its scrollback (clear -x keeps the scrollback)"
}


def execute(args=None):
    flags = [a for a in (args or []) if a.startswith("-")]
    stdio.clear_screen(scrollback="-x" not in flags)
