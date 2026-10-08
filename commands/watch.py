import shlex
import time

import pyos.fs as fs
import pyos.stdio as stdio
from pyos import filewatch, textcmd

config = {"name": "watch", "description": "Run a command again and again (watch [-n seconds] [-f path] <command>); with -f it runs again when that file or folder changes. Ctrl+C stops."}

USAGE = "[bold red]Usage:[/bold red] watch [-n seconds] [-f file-or-folder] <command>   (Ctrl+C stops)"


def execute(args=None):
    import shell
    options, rest = textcmd.flags(args, with_value="nf")
    try:
        seconds = max(1, min(3600, int(options.get("n") or 2)))
    except ValueError:
        seconds = 2
    if not rest:
        textcmd.console.print(USAGE)
        return False
    line = shlex.join(rest)
    watched = None
    if options.get("f"):
        try:
            watched = fs.resolve(str(options["f"]))
        except Exception as e:                                          # noqa: BLE001 - say it the way every command does
            textcmd.console.print(f"[bold red]watch: {options['f']}: {fs.errtext(e)}[/bold red]")
            return False

    def show(why):
        stdio.clear_screen(scrollback=False)
        textcmd.console.print(f"[dim]{why}: {line}   (Ctrl+C stops)[/dim]\n")
        shell.run_line(line)

    try:
        if watched:
            changes = filewatch.changes(watched)
            while True:
                show(f"When {options['f']} changes")
                next(changes)
        while True:
            show(f"Every {seconds}s")
            time.sleep(seconds)
    except (KeyboardInterrupt, StopIteration):
        textcmd.console.print()
    return True
