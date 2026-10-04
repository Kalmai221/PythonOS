from rich.console import Console
import pyos
from core import persist

console = Console()
config = {
    "name": "persist",
    "description": "Keep your accounts and files across restarts of the live system: persist [status|list|create].",
    "alias": ["storage"],
}


def execute(args=None):
    sub = (args[0].lower() if args else "status")
    if sub == "status":
        persist.status()
        return True
    if pyos.userinfo()[1] != "admin":
        console.print("[bold red]persist: only an administrator can set up storage[/bold red]")
        return False
    if sub in ("list", "disks"):
        persist.list_candidates()
        return True
    if sub in ("create", "setup"):
        return persist.create(args[1] if len(args) > 1 else None)
    console.print("[red]Usage:[/red] persist \\[status|list|create \\[device]]")
    return False
