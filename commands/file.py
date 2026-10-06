import os

from rich.console import Console

import pyos.fs as fs
from pyos.filetypes import describe

console = Console()
config = {"name": "file", "description": "Say what a file is, from its first bytes (file <path>...)."}


def execute(args=None):
    if not args:
        console.print("[bold red]Usage:[/bold red] file <path>...")
        return False
    ok = True
    for name in args:
        try:
            path = fs.resolve(name)
            if os.path.isdir(path):
                console.print(f"{name}: folder", markup=False)
                continue
            with open(path, "rb") as f:
                head = f.read(4096)
            console.print(f"{name}: {describe(head, name)}", markup=False, highlight=False)
        except Exception as e:                             # noqa: BLE001
            console.print(f"[bold red]file: {name}: {fs.errtext(e)}[/bold red]")
            ok = False
    return ok
