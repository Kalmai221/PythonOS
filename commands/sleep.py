import time
from rich.console import Console
from pyos import jobs

console = Console()
config = {"name": "sleep", "description": "Wait for some seconds (sleep 5). Handy with & and ;, e.g. sleep 5 && echo done"}


def execute(args=None):
    try:
        seconds = float(args[0]) if args else None
    except ValueError:
        seconds = None
    if seconds is None or seconds < 0:
        console.print("[bold red]Usage:[/bold red] sleep <seconds>")
        return False
    end = time.time() + seconds
    while time.time() < end:
        if jobs.cancelled():                 # a background job that was killed stops waiting
            return False
        time.sleep(min(0.2, max(0.0, end - time.time())))
    return True
