import time

from pyos import textcmd

config = {"name": "time", "description": "Run a command and say how long it took (time <command> [arguments])."}


def execute(args=None):
    import shell
    if not args:
        textcmd.console.print("[bold red]Usage:[/bold red] time <command> [arguments]")
        return False
    import shlex
    start = time.perf_counter()
    status = shell.run_line(shlex.join(args))
    textcmd.console.print(f"[dim]took {time.perf_counter() - start:.2f} seconds[/dim]")
    return status in (0, None)
