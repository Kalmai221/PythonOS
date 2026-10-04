import os
from rich.console import Console
import pyos.fs as fs

console = Console()
config = {"name": "touch", "description": "Create an empty file or update its timestamp (touch <file>)."}


def execute(args=None):
    if not args:
        console.print("[bold red]Usage:[/bold red] touch <file>")
        return
    for name in args:
        try:
            path = fs.resolve(name, write=True)
            with open(path, "a"):
                os.utime(path, None)
        except Exception as e:
            console.print(f"[bold red]touch: {name}: {e}[/bold red]")
