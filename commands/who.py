from rich.console import Console

import pyos
from pyos import tasks

console = Console()
config = {"name": "who", "description": "Show who is logged in and where (who).", "alias": ["users"]}


def execute(args=None):
    shown = {(row["user"], "tty1") for row in tasks.listing(pyos.userinfo()[0]) if row["kind"] == "shell"}
    if not shown:
        shown.add((pyos.userinfo()[0], "tty1"))
    for user, tty in sorted(shown):
        console.print(f"{user:<16}{tty}", markup=False, highlight=False)
    return True
