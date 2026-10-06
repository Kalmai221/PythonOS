import shlex
import time

import pyos.stdio as stdio
from pyos import textcmd

config = {"name": "watch", "description": "Run a command again and again (watch [-n seconds] <command>); Ctrl+C stops."}


def execute(args=None):
    import shell
    options, rest = textcmd.flags(args, with_value="n")
    try:
        seconds = max(1, min(3600, int(options.get("n") or 2)))
    except ValueError:
        seconds = 2
    if not rest:
        textcmd.console.print("[bold red]Usage:[/bold red] watch [-n seconds] <command>   (Ctrl+C stops)")
        return False
    line = shlex.join(rest)
    try:
        while True:
            stdio.clear_screen(scrollback=False)
            textcmd.console.print(f"[dim]Every {seconds}s: {line}   (Ctrl+C stops)[/dim]\n")
            shell.run_line(line)
            time.sleep(seconds)
    except KeyboardInterrupt:
        textcmd.console.print()
    return True
