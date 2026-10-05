from rich.console import Console

import pyos
from core import sysupdate

console = Console()
config = {"name": "rollback", "description": "Go back to the version before the last update (administrators only)."}


def execute(args=None):
    if pyos.userinfo()[1] != "admin":
        console.print("[bold red]rollback: only an administrator can change the installed version[/bold red]")
        return False
    if sysupdate.packaged_version() is None:
        console.print("[yellow]This is a source checkout; use git to go back to an earlier version.[/yellow]")
        return False
    from pyos import audit
    audit.record("rollback of the system update", level="WARN")
    return sysupdate.rollback()
