from rich.console import Console

import pyos
from pyos import tasks

console = Console()
config = {"name": "pgrep", "description": "Find PythonOS tasks by name (pgrep <word>); shows their ids for kill."}


def execute(args=None):
    if not args:
        console.print("[bold red]Usage:[/bold red] pgrep <word>")
        return False
    word = " ".join(args).lower()
    found = [r for r in tasks.listing(pyos.userinfo()[0]) if word in (r["cmd"] or r["name"]).lower()]
    for row in found:
        console.print(f"{row['pid']:>6}  {row['cmd'] or row['name']}", markup=False, highlight=False)
    return bool(found)
