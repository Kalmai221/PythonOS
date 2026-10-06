from rich.console import Console
import pyos
from core import persist

console = Console()
config = {
    "name": "persist",
    "description": "Keep your accounts and files across restarts of the live system: persist [status|list|create|resize|migrate].",
    "alias": ["storage"],
    "exports": ["iso"],
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
        rest = [a for a in args[1:] if a != "--encrypt"]
        return persist.create(rest[0] if rest else None, encrypt="--encrypt" in args)
    if sub == "resize":
        return persist.resize()
    if sub == "migrate":
        return persist.migrate(args[1] if len(args) > 1 else None)
    console.print("[red]Usage:[/red] persist \\[status|list|create \\[--encrypt] \\[device]|resize|migrate \\[device]]")
    return False
